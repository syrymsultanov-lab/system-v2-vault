#!/usr/bin/env python3
"""Patch TG Conversation Inbound to do reactive AI reply inline.

Appends nodes after 50_Touch_Contact:
  60_Fetch_Partner -> 65_Fetch_Settings -> 70_Fetch_Inbound -> 75_Fetch_Outbound
  -> 80_Build_Prompt -> 85_OpenAI_Chat -> 90_Parse_AI_JSON -> 95_If_Reply_OK
  -> 100_TG_Send -> 105_Insert_Outbound -> 110_Log_AI_Run -> 115_Update_Contact
  on false branch -> 120_Log_Failure

Latency: 3-5 sec end-to-end. No cron involved.
"""
import json, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).parent.parent
env = {}
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()

N8N_KEY = env["N8N_API_KEY"]
N8N_BASE = "https://n8n.sairateam.com/api/v1"
INBOUND_ID = "EEMvbCJaiN8affDR"

def n8n(method, path, data=None):
    url = f"{N8N_BASE}{path}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        url, data=body,
        headers={"X-N8N-API-KEY": N8N_KEY, "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} -> {e.code}: {e.read().decode()}") from e

def strip_readonly(wf):
    allowed = {"name", "nodes", "connections", "settings", "staticData"}
    out = {k: v for k, v in wf.items() if k in allowed}
    out.setdefault("settings", {})
    return out

SB_HEADERS = {
    "parameters": [
        {"name": "apikey", "value": "={{ $env.SUPABASE_SERVICE_ROLE_KEY }}"},
        {"name": "Authorization", "value": "={{ 'Bearer ' + $env.SUPABASE_SERVICE_ROLE_KEY }}"},
    ]
}
SB_HEADERS_WRITE = {
    "parameters": SB_HEADERS["parameters"] + [
        {"name": "Content-Type", "value": "application/json"},
    ]
}

BUILD_PROMPT_CODE = r"""
const c = $('25_Check_Contact').item.json.contact;
const p = (($('60_Fetch_Partner').item.json.body) || [])[0] || {};
const s = (($('65_Fetch_Settings').item.json.body) || [])[0] || {};
const inbound = (($('70_Fetch_Inbound').item.json.body) || []).map(m => ({ ts: m.created_at, role: 'lead', text: m.body }));
const outbound = (($('75_Fetch_Outbound').item.json.body) || []).map(m => ({ ts: m.created_at, role: 'ai', text: m.body }));
const history = inbound.concat(outbound).sort((a,b) => a.ts.localeCompare(b.ts));
const aiName = s.ai_assistant_name || 'AI ассистент';
const state = c.ai_state || 'greeting';

const systemPrompt = `Ты — ${aiName}, AI ассистент партнёра InCruises ${p.name || ''}. Краток, тёплый тон.

# Compliance
- Никогда не обещай гарантированный доход.
- Избегай scarcity-фраз.
- На STOP — action='stop', intent='stop'.

# Стиль
- Короткие ответы 1-2 предложения, 1 вопрос в конце.
- Без markdown, без эмодзи.

# Этапы
greeting -> qualification -> presentation -> q_and_a -> objection -> close.
Текущий: ${state}. Двигайся последовательно.

# Эскалация (escalate=true)
- agressive/negative -> escalate_reason='negative'
- ready_to_pay -> escalate_reason='ready_to_pay'
- media -> escalate_reason='media'
- low confidence -> escalate_reason='low_confidence'

Контакт: ${c.name || ''}, timezone ${c.timezone || 'Asia/Almaty'}.

Верни строго JSON по schema.`;

const histText = history.length === 0 ? '(история пуста)' : history.map(m => '[' + m.role + '] ' + m.text).join('\n');
const userPrompt = 'История диалога:\n' + histText + '\n\nСгенерируй следующее сообщение.';

const schema = {
  name: 'ai_reply',
  strict: true,
  schema: {
    type: 'object',
    additionalProperties: false,
    required: ['action','text','intent','escalate','escalate_reason','sentiment','confidence','next_state'],
    properties: {
      action: { type: 'string', enum: ['reply','defer','stop'] },
      text: { type: 'string' },
      intent: { type: 'string', enum: ['qualification','ready_to_pay','objection','media_received','stop','other'] },
      escalate: { type: 'boolean' },
      escalate_reason: { type: 'string', enum: ['negative','ready_to_pay','low_confidence','no_kb','media','none'] },
      sentiment: { type: 'string', enum: ['positive','neutral','negative'] },
      confidence: { type: 'number', minimum: 0, maximum: 1 },
      next_state: { type: 'string', enum: ['greeting','qualification','presentation','q_and_a','objection','close','paused','escalated','cold'] }
    }
  }
};

const openai_body = {
  model: 'gpt-4.1-mini',
  temperature: 0.3,
  messages: [
    { role: 'system', content: systemPrompt },
    { role: 'user', content: userPrompt }
  ],
  response_format: { type: 'json_schema', json_schema: schema }
};

return [{ json: {
  contact_id: c.id,
  partner_id: c.partner_id,
  contact_name: c.name,
  contact_messenger: c.messenger,
  contact_handle: c.messenger_handle,
  contact_phone: c.phone,
  contact_tg_chat_id: c.tg_chat_id,
  current_state: state,
  openai_body
} }];
"""

PARSE_AI_CODE = r"""
const upstream = $('80_Build_Prompt').item.json;
const resp = $json;
if (resp.error || (resp.body && resp.body.error)) {
  return [{ json: { ...upstream, ai_error: (resp.body && resp.body.error) || resp.error || resp.statusCode || 'unknown', ai_reply: null } }];
}
const raw = resp.body && resp.body.choices && resp.body.choices[0] && resp.body.choices[0].message && resp.body.choices[0].message.content;
let parsed = null;
try { parsed = JSON.parse(raw); } catch (e) { return [{ json: { ...upstream, ai_error: 'parse_failed: ' + e.message, ai_raw: raw, ai_reply: null } }]; }
return [{ json: { ...upstream, ai_reply: parsed, ai_raw: raw, ai_usage: resp.body && resp.body.usage } }];
"""

def build_new_nodes():
    return [
        {
            "id": "fetch-partner",
            "name": "60_Fetch_Partner",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [680, -120],
            "parameters": {
                "method": "GET",
                "url": "={{ $env.SUPABASE_URL + '/rest/v1/partners?select=id,name,referral_url&id=eq.' + $('25_Check_Contact').item.json.contact.partner_id }}",
                "options": {"response": {"response": {"fullResponse": True}}},
                "sendHeaders": True,
                "headerParameters": SB_HEADERS,
            },
        },
        {
            "id": "fetch-settings",
            "name": "65_Fetch_Settings",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [900, -120],
            "parameters": {
                "method": "GET",
                "url": "={{ $env.SUPABASE_URL + '/rest/v1/partner_settings?select=ai_assistant_name,ai_tone,ai_language&partner_id=eq.' + $('25_Check_Contact').item.json.contact.partner_id }}",
                "options": {"response": {"response": {"fullResponse": True}}},
                "sendHeaders": True,
                "headerParameters": SB_HEADERS,
            },
        },
        {
            "id": "fetch-inbound-hist",
            "name": "70_Fetch_Inbound",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [1120, -120],
            "parameters": {
                "method": "GET",
                "url": "={{ (() => { const c = $('25_Check_Contact').item.json.contact; const handles = [c.phone, c.messenger_handle, String(c.tg_chat_id||'')].filter(Boolean).map(h => '\"' + h + '\"').join(','); return $env.SUPABASE_URL + '/rest/v1/inbound_messages?select=body,from_address,direction,created_at&partner_id=eq.' + c.partner_id + '&from_address=in.(' + handles + ')&order=created_at.desc&limit=10' })() }}",
                "options": {"response": {"response": {"fullResponse": True}}},
                "sendHeaders": True,
                "headerParameters": SB_HEADERS,
            },
        },
        {
            "id": "fetch-outbound-hist",
            "name": "75_Fetch_Outbound",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [1340, -120],
            "parameters": {
                "method": "GET",
                "url": "={{ (() => { const c = $('25_Check_Contact').item.json.contact; const handles = [c.phone, c.messenger_handle].filter(Boolean).map(h => '\"' + h + '\"').join(','); return $env.SUPABASE_URL + '/rest/v1/outbound_messages?select=body,to_address,status,created_at&partner_id=eq.' + c.partner_id + '&to_address=in.(' + handles + ')&order=created_at.desc&limit=10' })() }}",
                "options": {"response": {"response": {"fullResponse": True}}},
                "sendHeaders": True,
                "headerParameters": SB_HEADERS,
            },
        },
        {
            "id": "build-prompt",
            "name": "80_Build_Prompt",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [1560, -120],
            "parameters": {"jsCode": BUILD_PROMPT_CODE},
        },
        {
            "id": "openai-chat",
            "name": "85_OpenAI_Chat",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [1780, -120],
            "parameters": {
                "method": "POST",
                "url": "https://api.openai.com/v1/chat/completions",
                "options": {"response": {"response": {"fullResponse": True}}, "timeout": 25000},
                "sendHeaders": True,
                "headerParameters": {"parameters": [
                    {"name": "Authorization", "value": "={{ 'Bearer ' + $env.OPENAI_API_KEY }}"},
                    {"name": "Content-Type", "value": "application/json"},
                ]},
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify($json.openai_body) }}",
            },
        },
        {
            "id": "parse-ai",
            "name": "90_Parse_AI_JSON",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [2000, -120],
            "parameters": {"jsCode": PARSE_AI_CODE},
        },
        {
            "id": "if-reply-ok",
            "name": "95_If_Reply_OK",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2.2,
            "position": [2220, -120],
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                    "combinator": "and",
                    "conditions": [
                        {
                            "id": "ok",
                            "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                            "leftValue": "={{ !!($json.ai_reply && $json.ai_reply.text && $json.ai_reply.action === 'reply') }}",
                            "rightValue": "",
                        }
                    ],
                },
            },
        },
        {
            "id": "tg-send",
            "name": "100_TG_Send",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [2440, -240],
            "parameters": {
                "method": "POST",
                "url": "={{ 'https://api.telegram.org/bot' + $env.TG_CONVERSATION_BOT_TOKEN + '/sendMessage' }}",
                "options": {"response": {"response": {"fullResponse": True}}, "timeout": 10000},
                "sendHeaders": True,
                "headerParameters": {"parameters": [
                    {"name": "Content-Type", "value": "application/json"},
                ]},
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify({ chat_id: $json.contact_tg_chat_id, text: $json.ai_reply.text }) }}",
                "continueOnFail": True,
            },
        },
        {
            "id": "insert-outbound",
            "name": "105_Insert_Outbound",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [2660, -240],
            "parameters": {
                "method": "POST",
                "url": "={{ $env.SUPABASE_URL + '/rest/v1/outbound_messages' }}",
                "options": {"response": {"response": {"fullResponse": True}}},
                "sendHeaders": True,
                "headerParameters": {"parameters": SB_HEADERS_WRITE["parameters"] + [{"name": "Prefer", "value": "return=representation"}]},
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": (
                    "={{ JSON.stringify({ "
                    "partner_id: $('90_Parse_AI_JSON').item.json.partner_id, "
                    "channel: 'telegram', "
                    "to_address: ($('90_Parse_AI_JSON').item.json.contact_handle || ''), "
                    "body: $('90_Parse_AI_JSON').item.json.ai_reply.text, "
                    "status: (($json.body && $json.body.ok) ? 'sent' : 'failed'), "
                    "sent_at: new Date().toISOString() "
                    "}) }}"
                ),
            },
        },
        {
            "id": "log-ai-run",
            "name": "110_Log_AI_Run",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [2880, -240],
            "parameters": {
                "method": "POST",
                "url": "={{ $env.SUPABASE_URL + '/rest/v1/ai_job_runs' }}",
                "options": {"response": {"response": {"fullResponse": True}}},
                "sendHeaders": True,
                "headerParameters": SB_HEADERS_WRITE,
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": (
                    "={{ JSON.stringify({ "
                    "job_id: null, "
                    "status: 'success', "
                    "input: { contact_id: $('90_Parse_AI_JSON').item.json.contact_id, model: 'gpt-4.1-mini', source: 'inbound_reactive' }, "
                    "output: { "
                    "model: 'gpt-4.1-mini', "
                    "prompt_tokens: (($('90_Parse_AI_JSON').item.json.ai_usage && $('90_Parse_AI_JSON').item.json.ai_usage.prompt_tokens) || 0), "
                    "completion_tokens: (($('90_Parse_AI_JSON').item.json.ai_usage && $('90_Parse_AI_JSON').item.json.ai_usage.completion_tokens) || 0), "
                    "cost_usd: ((($('90_Parse_AI_JSON').item.json.ai_usage && $('90_Parse_AI_JSON').item.json.ai_usage.prompt_tokens) || 0) * 0.00000015 + "
                    "(($('90_Parse_AI_JSON').item.json.ai_usage && $('90_Parse_AI_JSON').item.json.ai_usage.completion_tokens) || 0) * 0.0000006) "
                    "} }) }}"
                ),
            },
        },
        {
            "id": "update-contact",
            "name": "115_Update_Contact",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [3100, -240],
            "parameters": {
                "method": "PATCH",
                "url": "={{ $env.SUPABASE_URL + '/rest/v1/contacts?id=eq.' + $('90_Parse_AI_JSON').item.json.contact_id }}",
                "options": {"response": {"response": {"fullResponse": True}}},
                "sendHeaders": True,
                "headerParameters": SB_HEADERS_WRITE,
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": (
                    "={{ JSON.stringify({ "
                    "ai_state: $('90_Parse_AI_JSON').item.json.ai_reply.next_state, "
                    "last_outbound_at: new Date().toISOString(), "
                    "updated_at: new Date().toISOString(), "
                    "do_not_contact: ($('90_Parse_AI_JSON').item.json.ai_reply.intent === 'stop') ? true : undefined "
                    "}) }}"
                ),
            },
        },
        {
            "id": "log-fail",
            "name": "120_Log_Failure",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [2440, 0],
            "parameters": {
                "method": "POST",
                "url": "={{ $env.SUPABASE_URL + '/rest/v1/events_log' }}",
                "options": {"response": {"response": {"fullResponse": True}}},
                "sendHeaders": True,
                "headerParameters": SB_HEADERS_WRITE,
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": (
                    "={{ JSON.stringify({ "
                    "partner_id: $('90_Parse_AI_JSON').item.json.partner_id, "
                    "actor: 'system', "
                    "event: 'ai_reply_failed_reactive', "
                    "payload: { contact_id: $('90_Parse_AI_JSON').item.json.contact_id, ai_error: ($('90_Parse_AI_JSON').item.json.ai_error || 'no_reply'), ai_raw: ($('90_Parse_AI_JSON').item.json.ai_raw || null) } "
                    "}) }}"
                ),
            },
        },
    ]

def patch():
    wf = n8n("GET", f"/workflows/{INBOUND_ID}")
    existing_names = {n["name"] for n in wf["nodes"]}
    new_nodes = [n for n in build_new_nodes() if n["name"] not in existing_names]
    wf["nodes"].extend(new_nodes)

    wf["connections"]["50_Touch_Contact"] = {"main": [[{"node": "60_Fetch_Partner", "type": "main", "index": 0}]]}
    wf["connections"]["60_Fetch_Partner"]  = {"main": [[{"node": "65_Fetch_Settings", "type": "main", "index": 0}]]}
    wf["connections"]["65_Fetch_Settings"] = {"main": [[{"node": "70_Fetch_Inbound", "type": "main", "index": 0}]]}
    wf["connections"]["70_Fetch_Inbound"]  = {"main": [[{"node": "75_Fetch_Outbound", "type": "main", "index": 0}]]}
    wf["connections"]["75_Fetch_Outbound"] = {"main": [[{"node": "80_Build_Prompt", "type": "main", "index": 0}]]}
    wf["connections"]["80_Build_Prompt"]   = {"main": [[{"node": "85_OpenAI_Chat", "type": "main", "index": 0}]]}
    wf["connections"]["85_OpenAI_Chat"]    = {"main": [[{"node": "90_Parse_AI_JSON", "type": "main", "index": 0}]]}
    wf["connections"]["90_Parse_AI_JSON"]  = {"main": [[{"node": "95_If_Reply_OK", "type": "main", "index": 0}]]}
    wf["connections"]["95_If_Reply_OK"] = {
        "main": [
            [{"node": "100_TG_Send", "type": "main", "index": 0}],
            [{"node": "120_Log_Failure", "type": "main", "index": 0}],
        ]
    }
    wf["connections"]["100_TG_Send"]         = {"main": [[{"node": "105_Insert_Outbound", "type": "main", "index": 0}]]}
    wf["connections"]["105_Insert_Outbound"] = {"main": [[{"node": "110_Log_AI_Run", "type": "main", "index": 0}]]}
    wf["connections"]["110_Log_AI_Run"]      = {"main": [[{"node": "115_Update_Contact", "type": "main", "index": 0}]]}

    wf = strip_readonly(wf)
    n8n("PUT", f"/workflows/{INBOUND_ID}", wf)
    print("Inbound patched: reactive AI reply pipeline appended after 50_Touch_Contact")

if __name__ == "__main__":
    patch()
