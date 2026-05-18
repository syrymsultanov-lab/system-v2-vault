#!/usr/bin/env python3
"""Patch WF TG Conversation Inbound:
  Task #3 — 110_Log_AI_Run: write structured AI fields to ai_job_runs.output
  Task #2 — add 45_If_Has_Media branch: media -> escalation reply, skip OpenAI
  Task #5 — 115_Update_Contact: bump updated_at to close Loop race window
"""
import json, urllib.request, urllib.parse
from pathlib import Path

ROOT = Path(__file__).parent.parent
env = {}
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()

N8N = env["N8N_URL"]
API_KEY = env["N8N_API_KEY"]
TG_GROUP = env["TG_GROUP_CHAT_ID"]
WF_ID = "EEMvbCJaiN8affDR"

def api(method, path, body=None):
    import urllib.error
    url = f"{N8N}/api/v1{path}"
    headers = {"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"n8n {method} {path} -> {e.code}: {e.read().decode()}") from e

wf = api("GET", f"/workflows/{WF_ID}")
nodes = wf["nodes"]
conns = wf["connections"]

def find(name):
    for i, n in enumerate(nodes):
        if n["name"] == name:
            return i, n
    raise KeyError(name)

# ---------- Task #3: 110_Log_AI_Run extended output ----------
_, log_node = find("110_Log_AI_Run")
log_body = (
    "={{ JSON.stringify({"
    " job_id: null,"
    " status: 'success',"
    " input: {"
    "   contact_id: $('90_Parse_AI_JSON').item.json.contact_id,"
    "   model: 'gpt-4.1-mini',"
    "   source: 'inbound_reactive'"
    " },"
    " output: {"
    "   model: 'gpt-4.1-mini',"
    "   prompt_tokens: (($('90_Parse_AI_JSON').item.json.ai_usage && $('90_Parse_AI_JSON').item.json.ai_usage.prompt_tokens) || 0),"
    "   completion_tokens: (($('90_Parse_AI_JSON').item.json.ai_usage && $('90_Parse_AI_JSON').item.json.ai_usage.completion_tokens) || 0),"
    "   cost_usd: ((($('90_Parse_AI_JSON').item.json.ai_usage && $('90_Parse_AI_JSON').item.json.ai_usage.prompt_tokens) || 0) * 0.00000015"
    "             + (($('90_Parse_AI_JSON').item.json.ai_usage && $('90_Parse_AI_JSON').item.json.ai_usage.completion_tokens) || 0) * 0.0000006),"
    "   action: ($('90_Parse_AI_JSON').item.json.ai_reply && $('90_Parse_AI_JSON').item.json.ai_reply.action) || null,"
    "   intent: ($('90_Parse_AI_JSON').item.json.ai_reply && $('90_Parse_AI_JSON').item.json.ai_reply.intent) || null,"
    "   sentiment: ($('90_Parse_AI_JSON').item.json.ai_reply && $('90_Parse_AI_JSON').item.json.ai_reply.sentiment) || null,"
    "   confidence: ($('90_Parse_AI_JSON').item.json.ai_reply && $('90_Parse_AI_JSON').item.json.ai_reply.confidence) != null ? $('90_Parse_AI_JSON').item.json.ai_reply.confidence : null,"
    "   escalate: ($('90_Parse_AI_JSON').item.json.ai_reply && $('90_Parse_AI_JSON').item.json.ai_reply.escalate) === true,"
    "   escalate_reason: ($('90_Parse_AI_JSON').item.json.ai_reply && $('90_Parse_AI_JSON').item.json.ai_reply.escalate_reason) || null,"
    "   next_state: ($('90_Parse_AI_JSON').item.json.ai_reply && $('90_Parse_AI_JSON').item.json.ai_reply.next_state) || null,"
    "   reply_length: ($('90_Parse_AI_JSON').item.json.ai_reply && $('90_Parse_AI_JSON').item.json.ai_reply.text) ? $('90_Parse_AI_JSON').item.json.ai_reply.text.length : 0"
    " }"
    "}) }}"
)
log_node["parameters"]["jsonBody"] = log_body

# ---------- Task #5: 115_Update_Contact + updated_at ----------
_, upd_node = find("115_Update_Contact")
upd_body = (
    "={{ JSON.stringify({"
    " ai_state: $('90_Parse_AI_JSON').item.json.ai_reply.next_state,"
    " last_outbound_at: new Date().toISOString(),"
    " updated_at: new Date().toISOString(),"
    " do_not_contact: ($('90_Parse_AI_JSON').item.json.ai_reply.intent === 'stop') ? true : undefined"
    "}) }}"
)
upd_node["parameters"]["jsonBody"] = upd_body

# Also bump updated_at in 120_Log_Failure path so Loop won't retry stuck failures every cron
# Add separate 121_Bump_Updated node
_, fail_node = find("120_Log_Failure")

# ---------- Task #2: media branch ----------
# Insert 45_If_Has_Media between 40_Insert_Inbound and 50_Touch_Contact
# True branch: 46_TG_Send_Escalation -> 47_Insert_Outbound -> 48_Notify_Partner_Group -> 49_Update_Contact_Escalated -> END
# False branch: 50_Touch_Contact (existing flow)

_TYPE_VERSIONS = {
    "n8n-nodes-base.if": 2.2,
    "n8n-nodes-base.httpRequest": 4.2,
    "n8n-nodes-base.code": 2,
    "n8n-nodes-base.webhook": 2,
}

def make_node(name, ntype, params, pos):
    return {
        "parameters": params,
        "id": name.lower().replace("_", "-"),
        "name": name,
        "type": ntype,
        "typeVersion": _TYPE_VERSIONS.get(ntype, 1),
        "position": pos,
    }

_, insert_inbound = find("40_Insert_Inbound")
_, touch_contact = find("50_Touch_Contact")
base_x = insert_inbound["position"][0]
base_y = insert_inbound["position"][1]

if_media = make_node(
    "45_If_Has_Media",
    "n8n-nodes-base.if",
    {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
            "combinator": "and",
            "conditions": [{
                "id": "media",
                "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                "leftValue": "={{ !!($('10_Parse_Update').item.json.has_media && !$('10_Parse_Update').item.json.text) }}",
                "rightValue": "",
            }],
        }
    },
    [base_x + 220, base_y],
)

esc_text = "Секунду, передаю это Сайре — она ответит лично."

tg_send_esc = make_node(
    "46_TG_Send_Escalation",
    "n8n-nodes-base.httpRequest",
    {
        "method": "POST",
        "url": "={{ 'https://api.telegram.org/bot' + $env.TG_CONVERSATION_BOT_TOKEN + '/sendMessage' }}",
        "options": {},
        "sendHeaders": True,
        "headerParameters": {"parameters": [{"name": "Content-Type", "value": "application/json"}]},
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({ chat_id: $('25_Check_Contact').item.json.contact.tg_chat_id, text: '" + esc_text + "' }) }}",
    },
    [base_x + 440, base_y - 120],
)

ins_outbound_esc = make_node(
    "47_Insert_Outbound_Escalation",
    "n8n-nodes-base.httpRequest",
    {
        "method": "POST",
        "url": "={{ $env.SUPABASE_URL + '/rest/v1/outbound_messages' }}",
        "options": {},
        "sendHeaders": True,
        "headerParameters": {"parameters": [
            {"name": "apikey", "value": "={{ $env.SUPABASE_SERVICE_ROLE_KEY }}"},
            {"name": "Authorization", "value": "={{ 'Bearer ' + $env.SUPABASE_SERVICE_ROLE_KEY }}"},
            {"name": "Content-Type", "value": "application/json"},
        ]},
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({ partner_id: $('25_Check_Contact').item.json.contact.partner_id, channel: 'telegram', to_address: ($('10_Parse_Update').item.json.from_handle || String($('10_Parse_Update').item.json.from_id)), body: '" + esc_text + "', status: 'sent', sent_at: new Date().toISOString() }) }}",
    },
    [base_x + 660, base_y - 120],
)

notify_partner = make_node(
    "48_Notify_Partner_Media",
    "n8n-nodes-base.httpRequest",
    {
        "method": "POST",
        "url": "={{ 'https://api.telegram.org/bot' + $env.TG_BOT_TOKEN + '/sendMessage' }}",
        "options": {},
        "sendHeaders": True,
        "headerParameters": {"parameters": [{"name": "Content-Type", "value": "application/json"}]},
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({ chat_id: " + TG_GROUP + ", text: '⚠️ AI escalation: media от лида\\nКонтакт: ' + ($('25_Check_Contact').item.json.contact.name || '(no name)') + '\\nTG: ' + ($('10_Parse_Update').item.json.from_handle || $('10_Parse_Update').item.json.from_id) + '\\nПричина: получено медиа (фото/голос/видео/файл), AI не обрабатывает' }) }}",
    },
    [base_x + 880, base_y - 120],
)

upd_contact_esc = make_node(
    "49_Update_Contact_Escalated",
    "n8n-nodes-base.httpRequest",
    {
        "method": "PATCH",
        "url": "={{ $env.SUPABASE_URL + '/rest/v1/contacts?id=eq.' + $('25_Check_Contact').item.json.contact.id }}",
        "options": {},
        "sendHeaders": True,
        "headerParameters": {"parameters": [
            {"name": "apikey", "value": "={{ $env.SUPABASE_SERVICE_ROLE_KEY }}"},
            {"name": "Authorization", "value": "={{ 'Bearer ' + $env.SUPABASE_SERVICE_ROLE_KEY }}"},
            {"name": "Content-Type", "value": "application/json"},
        ]},
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({ ai_state: 'escalated', last_inbound_at: new Date().toISOString(), last_outbound_at: new Date().toISOString(), updated_at: new Date().toISOString() }) }}",
    },
    [base_x + 1100, base_y - 120],
)

# Remove old nodes with same names if present (idempotent)
existing_names = {"45_If_Has_Media", "46_TG_Send_Escalation", "47_Insert_Outbound_Escalation", "48_Notify_Partner_Media", "49_Update_Contact_Escalated"}
nodes[:] = [n for n in nodes if n["name"] not in existing_names]
nodes.extend([if_media, tg_send_esc, ins_outbound_esc, notify_partner, upd_contact_esc])

# Rewire connections:
# Currently 40_Insert_Inbound -> 50_Touch_Contact. Insert 45_If_Has_Media in between.
# 45 false -> 50_Touch_Contact (normal)
# 45 true -> 46 -> 47 -> 48 -> 49 (END)
old_from_40 = conns.get("40_Insert_Inbound", {})
conns["40_Insert_Inbound"] = {"main": [[{"node": "45_If_Has_Media", "type": "main", "index": 0}]]}
conns["45_If_Has_Media"] = {
    "main": [
        # output 0 = true branch
        [{"node": "46_TG_Send_Escalation", "type": "main", "index": 0}],
        # output 1 = false branch -> resume normal flow to 50_Touch_Contact
        [{"node": "50_Touch_Contact", "type": "main", "index": 0}],
    ]
}
conns["46_TG_Send_Escalation"] = {"main": [[{"node": "47_Insert_Outbound_Escalation", "type": "main", "index": 0}]]}
conns["47_Insert_Outbound_Escalation"] = {"main": [[{"node": "48_Notify_Partner_Media", "type": "main", "index": 0}]]}
conns["48_Notify_Partner_Media"] = {"main": [[{"node": "49_Update_Contact_Escalated", "type": "main", "index": 0}]]}
# 49 has no outgoing -> end of branch

# Push update
update_payload = {
    "name": wf["name"],
    "nodes": nodes,
    "connections": conns,
    "settings": wf.get("settings", {}),
}
res = api("PUT", f"/workflows/{WF_ID}", update_payload)
print("WF updated. nodes:", len(res["nodes"]))
print("Active:", res.get("active"))
