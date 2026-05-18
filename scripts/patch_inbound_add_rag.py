#!/usr/bin/env python3
"""Add RAG retrieval to TG Conversation Inbound reactive pipeline.

Adds between 75_Fetch_Outbound and 80_Build_Prompt:
  76_Embed_Query  -> OpenAI embeddings on last inbound text
  77_RAG_Retrieve -> RPC match_kb_chunks(query_embedding, top_k=5, partner_id)

Modifies 80_Build_Prompt to inject retrieved chunks into systemPrompt.
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
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} -> {e.code}: {e.read().decode()}") from e

def strip_readonly(wf):
    allowed = {"name", "nodes", "connections", "settings", "staticData"}
    out = {k: v for k, v in wf.items() if k in allowed}
    out.setdefault("settings", {})
    return out

SB_HEADERS = [
    {"name": "apikey", "value": "={{ $env.SUPABASE_SERVICE_ROLE_KEY }}"},
    {"name": "Authorization", "value": "={{ 'Bearer ' + $env.SUPABASE_SERVICE_ROLE_KEY }}"},
    {"name": "Content-Type", "value": "application/json"},
]

EMBED_QUERY_NODE = {
    "id": "embed-query",
    "name": "76_Embed_Query",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.2,
    "position": [1440, -120],
    "parameters": {
        "method": "POST",
        "url": "https://api.openai.com/v1/embeddings",
        "options": {"response": {"response": {"fullResponse": True}}, "timeout": 15000},
        "sendHeaders": True,
        "headerParameters": {"parameters": [
            {"name": "Authorization", "value": "={{ 'Bearer ' + $env.OPENAI_API_KEY }}"},
            {"name": "Content-Type", "value": "application/json"},
        ]},
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({ model: 'text-embedding-3-small', input: ($('25_Check_Contact').item.json.parsed.text || '') }) }}",
    },
}

RAG_RETRIEVE_NODE = {
    "id": "rag-retrieve",
    "name": "77_RAG_Retrieve",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.2,
    "position": [1500, -120],
    "parameters": {
        "method": "POST",
        "url": "={{ $env.SUPABASE_URL + '/rest/v1/rpc/match_kb_chunks' }}",
        "options": {"response": {"response": {"fullResponse": True}}, "timeout": 10000},
        "sendHeaders": True,
        "headerParameters": {"parameters": SB_HEADERS},
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": (
            "={{ JSON.stringify({ "
            "p_query_embedding: $json.body.data[0].embedding, "
            "p_top_k: 5, "
            "p_partner_id: $('25_Check_Contact').item.json.contact.partner_id "
            "}) }}"
        ),
    },
}

BUILD_PROMPT_CODE_WITH_RAG = r"""
const c = $('25_Check_Contact').item.json.contact;
const p = (($('60_Fetch_Partner').item.json.body) || [])[0] || {};
const s = (($('65_Fetch_Settings').item.json.body) || [])[0] || {};
const inbound = (($('70_Fetch_Inbound').item.json.body) || []).map(m => ({ ts: m.created_at, role: 'lead', text: m.body }));
const outbound = (($('75_Fetch_Outbound').item.json.body) || []).map(m => ({ ts: m.created_at, role: 'ai', text: m.body }));
const history = inbound.concat(outbound).sort((a,b) => a.ts.localeCompare(b.ts));
const aiName = s.ai_assistant_name || 'AI ассистент';
const state = c.ai_state || 'greeting';

const ragRows = (($('77_RAG_Retrieve').item.json.body) || []);
const ragBlock = ragRows.length === 0
  ? '(нет релевантных фрагментов)'
  : ragRows.map((r, i) => `[KB-${i+1}] ${r.content}`).join('\n\n');

const systemPrompt = `Ты — ${aiName}, AI ассистент партнёра InCruises ${p.name || ''}. Тёплый тон, на «вы».

# База знаний (ЕДИНСТВЕННЫЙ источник фактов о InCruises — компенсация, продукт, условия, цены, ранги)
${ragBlock}

# Антигаллюцинация (КРИТИЧНО)
- Используй ТОЛЬКО факты из «База знаний» выше. Не додумывай, не угадывай, не расшифровывай аббревиатуры по аналогии.
- Если в КБ нет точного ответа — НЕ выдумывай. Верни короткий честный «уточню у партнёра» и escalate=true, escalate_reason='no_kb'.
- Числа, проценты, названия рангов, условия — только из КБ.

# Compliance
- Никогда не обещай гарантированный доход.
- Избегай scarcity-фраз («места ограничены», «успей сегодня»).
- На STOP / «не пишите» — action='stop', intent='stop'.

# Стиль и длина (в зависимости от этапа)
- greeting — 1-2 предложения + 1 короткий warm-up вопрос.
- qualification — 2-3 предложения + 1 фокусный вопрос (только если действительно нужно уточнить факт).
- presentation — 3-6 предложений: расскажи продукт/возможность из КБ. Вопрос НЕ обязателен; можно закончить мягким CTA («хочешь подробнее про X?») — но НЕ каждый раз.
- q_and_a — отвечай по сути, развёрнуто. БЕЗ обязательного вопроса в конце. Дай юзеру вести.
- objection — разбери возражение из КБ, согласись с эмоцией, дай факты. БЕЗ контрвопроса.
- close — 1 закрывающий вопрос (готов / когда удобно созвон).
- Без markdown, без эмодзи, без bullet-листов.
- Пиши живо, как опытный консультант — короткими абзацами, не сухо.

# Антипаттерны (НЕ делай)
- НЕ задавай вопрос в каждом сообщении. Если этап q_and_a/objection/presentation — вопрос опционален.
- НЕ повторяй уже отвеченные юзером факты ("ты сказал, что..."). Двигайся вперёд.
- НЕ давай длинных списков 1.2.3. — это переписка в мессенджере, не email.

# Этапы
greeting -> qualification -> presentation -> q_and_a -> objection -> close.
Текущий: ${state}. Двигайся последовательно.

# Эскалация (escalate=true)
- agressive/negative -> escalate_reason='negative'
- ready_to_pay -> escalate_reason='ready_to_pay'
- media (голос/фото/видео) -> escalate_reason='media'
- confidence <0.6 -> escalate_reason='low_confidence'
- нет в КБ -> escalate_reason='no_kb'

Контакт: ${c.name || ''}, timezone ${c.timezone || 'Asia/Almaty'}.
Реферал партнёра: ${p.referral_url || '(не задан)'}.

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
  rag_count: ragRows.length,
  openai_body
} }];
"""

def patch():
    wf = n8n("GET", f"/workflows/{INBOUND_ID}")
    nodes = wf["nodes"]
    by_name = {n["name"]: n for n in nodes}

    if "76_Embed_Query" not in by_name:
        nodes.append(EMBED_QUERY_NODE)
    if "77_RAG_Retrieve" not in by_name:
        nodes.append(RAG_RETRIEVE_NODE)

    for n in nodes:
        if n["name"] == "80_Build_Prompt":
            n["parameters"]["jsCode"] = BUILD_PROMPT_CODE_WITH_RAG

    pos_shifts = {
        "76_Embed_Query":   [1440, -120],
        "77_RAG_Retrieve":  [1560, -120],
        "80_Build_Prompt":  [1680, -120],
        "85_OpenAI_Chat":   [1900, -120],
        "90_Parse_AI_JSON": [2120, -120],
        "95_If_Reply_OK":   [2340, -120],
        "100_TG_Send":      [2560, -240],
        "105_Insert_Outbound":[2780, -240],
        "110_Log_AI_Run":   [3000, -240],
        "115_Update_Contact":[3220, -240],
        "120_Log_Failure":  [2560, 0],
    }
    for n in nodes:
        if n["name"] in pos_shifts:
            n["position"] = pos_shifts[n["name"]]

    wf["connections"]["75_Fetch_Outbound"] = {"main": [[{"node": "76_Embed_Query", "type": "main", "index": 0}]]}
    wf["connections"]["76_Embed_Query"]    = {"main": [[{"node": "77_RAG_Retrieve", "type": "main", "index": 0}]]}
    wf["connections"]["77_RAG_Retrieve"]   = {"main": [[{"node": "80_Build_Prompt", "type": "main", "index": 0}]]}

    wf = strip_readonly(wf)
    n8n("PUT", f"/workflows/{INBOUND_ID}", wf)
    print("Inbound patched: 76_Embed_Query + 77_RAG_Retrieve + RAG-aware 80_Build_Prompt")

if __name__ == "__main__":
    patch()
