#!/usr/bin/env python3
"""Patch AI Conversation Loop (add 85_Log_AI_Job_Run + last_outbound_at) and
rewrite WF9 Outbound Message Dispatcher to actually send via Telegram.

NO $env inlining. Workflow JSON stays portable per memory feedback_n8n_deploy_no_inline_env.
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

LOOP_ID = "GunZRf38lPvApSnD"
WF9_ID = "I6m8cSqkX1M3zpyC"

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
    """Strict allowlist — n8n PUT accepts only name/nodes/connections/settings/staticData."""
    allowed = {"name", "nodes", "connections", "settings", "staticData"}
    out = {k: v for k, v in wf.items() if k in allowed}
    out.setdefault("settings", {})
    return out

# ---------------------------------------------------------------------------
# 1. Patch AI Conversation Loop
# ---------------------------------------------------------------------------
def patch_loop():
    wf = n8n("GET", f"/workflows/{LOOP_ID}")
    nodes = wf["nodes"]
    connections = wf["connections"]

    # 1a. Update 80_Update_Contact body: add last_outbound_at
    for n in nodes:
        if n["name"] == "80_Update_Contact":
            n["parameters"]["jsonBody"] = (
                "={{ JSON.stringify({ "
                "ai_state: $('60_Parse_AI_JSON').item.json.ai_reply.next_state, "
                "last_outbound_at: new Date().toISOString(), "
                "do_not_contact: ($('60_Parse_AI_JSON').item.json.ai_reply.intent === 'stop') ? true : undefined "
                "}) }}"
            )
            break

    # 1b. Insert 85_Log_AI_Job_Run node
    log_node = {
        "id": "log-ai-run",
        "name": "85_Log_AI_Job_Run",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [900, -60],
        "parameters": {
            "method": "POST",
            "url": "={{ $env.SUPABASE_URL + '/rest/v1/ai_job_runs' }}",
            "options": {"response": {"response": {"fullResponse": True}}},
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "apikey", "value": "={{ $env.SUPABASE_SERVICE_ROLE_KEY }}"},
                {"name": "Authorization", "value": "={{ 'Bearer ' + $env.SUPABASE_SERVICE_ROLE_KEY }}"},
                {"name": "Content-Type", "value": "application/json"},
            ]},
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": (
                "={{ JSON.stringify({ "
                "job_id: null, "
                "status: 'success', "
                "input: { contact_id: $('60_Parse_AI_JSON').item.json.contact_id, model: 'gpt-4.1-mini', source: 'conversation_loop' }, "
                "output: { "
                "model: 'gpt-4.1-mini', "
                "prompt_tokens: (($('60_Parse_AI_JSON').item.json.ai_usage && $('60_Parse_AI_JSON').item.json.ai_usage.prompt_tokens) || 0), "
                "completion_tokens: (($('60_Parse_AI_JSON').item.json.ai_usage && $('60_Parse_AI_JSON').item.json.ai_usage.completion_tokens) || 0), "
                "cost_usd: ((($('60_Parse_AI_JSON').item.json.ai_usage && $('60_Parse_AI_JSON').item.json.ai_usage.prompt_tokens) || 0) * 0.00000015 + "
                "(($('60_Parse_AI_JSON').item.json.ai_usage && $('60_Parse_AI_JSON').item.json.ai_usage.completion_tokens) || 0) * 0.0000006) "
                "} }) }}"
            ),
        },
    }
    # Position 80_Update_Contact at [780,-60], insert log_node at [900,-60], shift 90/91 right
    # nodes_existing positions: 70 (560,-60), 80 (780,-60), 90 (1000,-60)
    # New flow: 70 -> 85 -> 80 -> 90
    # Move 80 to [1000,-60], 85 stays at [900,-60], 90 to [1220,-60], 91 to [1440,-60]
    pos_shifts = {
        "85_Log_AI_Job_Run": [900, -60],
        "80_Update_Contact": [1100, -60],
        "90_If_Escalate":    [1320, -60],
        "91_Notify_TG":      [1540, -60],
    }
    if not any(n["name"] == "85_Log_AI_Job_Run" for n in nodes):
        nodes.append(log_node)
    for n in nodes:
        if n["name"] in pos_shifts:
            n["position"] = pos_shifts[n["name"]]

    # 1c. Rewire connections: 70 -> 85 -> 80
    connections["70_Insert_Outbound"] = {
        "main": [[{"node": "85_Log_AI_Job_Run", "type": "main", "index": 0}]]
    }
    connections["85_Log_AI_Job_Run"] = {
        "main": [[{"node": "80_Update_Contact", "type": "main", "index": 0}]]
    }

    # 1d. PUT
    wf = strip_readonly(wf)
    n8n("PUT", f"/workflows/{LOOP_ID}", wf)
    print(f"LOOP patched: 85_Log_AI_Job_Run inserted, 80 jsonBody +last_outbound_at")

# ---------------------------------------------------------------------------
# 2. Rewrite WF9 Outbound Message Dispatcher
# ---------------------------------------------------------------------------
def rewrite_wf9():
    wf = n8n("GET", f"/workflows/{WF9_ID}")

    new_nodes = [
        {
            "id": "schedule",
            "name": "01_Schedule_Trigger",
            "type": "n8n-nodes-base.scheduleTrigger",
            "typeVersion": 1.2,
            "position": [-1000, 0],
            "parameters": {"rule": {"interval": [{"field": "minutes", "minutesInterval": 1}]}},
        },
        {
            "id": "fetch-outbound",
            "name": "10_Fetch_Outbound",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [-780, 0],
            "parameters": {
                "method": "GET",
                "url": "={{ $env.SUPABASE_URL + '/rest/v1/outbound_messages?select=id,partner_id,channel,to_address,body,status&status=in.(queued,dry_run,approved)&order=created_at.asc&limit=20' }}",
                "options": {"response": {"response": {"fullResponse": True}}},
                "sendHeaders": True,
                "headerParameters": {"parameters": [
                    {"name": "apikey", "value": "={{ $env.SUPABASE_SERVICE_ROLE_KEY }}"},
                    {"name": "Authorization", "value": "={{ 'Bearer ' + $env.SUPABASE_SERVICE_ROLE_KEY }}"},
                ]},
            },
        },
        {
            "id": "split-outbound",
            "name": "15_Split",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [-560, 0],
            "parameters": {
                "jsCode": "return (Array.isArray($json.body) ? $json.body : []).map(m => ({ json: m }));"
            },
        },
        {
            "id": "fetch-contact",
            "name": "20_Fetch_Contact",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [-340, 0],
            "parameters": {
                "method": "GET",
                "url": "={{ $env.SUPABASE_URL + '/rest/v1/contacts?select=id,tg_chat_id,messenger,messenger_handle,do_not_contact&partner_id=eq.' + $json.partner_id + '&messenger=eq.' + $json.channel + '&messenger_handle=eq.' + encodeURIComponent($json.to_address) + '&limit=1' }}",
                "options": {"response": {"response": {"fullResponse": True}}},
                "sendHeaders": True,
                "headerParameters": {"parameters": [
                    {"name": "apikey", "value": "={{ $env.SUPABASE_SERVICE_ROLE_KEY }}"},
                    {"name": "Authorization", "value": "={{ 'Bearer ' + $env.SUPABASE_SERVICE_ROLE_KEY }}"},
                ]},
            },
        },
        {
            "id": "merge-context",
            "name": "25_Merge_Context",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [-120, 0],
            "parameters": {
                "jsCode": (
                    "const out = $('15_Split').item.json;\n"
                    "const contacts = ($json.body || []);\n"
                    "const c = contacts[0] || null;\n"
                    "return [{ json: {\n"
                    "  outbound_id: out.id,\n"
                    "  partner_id: out.partner_id,\n"
                    "  channel: out.channel,\n"
                    "  body: out.body,\n"
                    "  to_address: out.to_address,\n"
                    "  contact_id: c ? c.id : null,\n"
                    "  tg_chat_id: c ? c.tg_chat_id : null,\n"
                    "  do_not_contact: c ? c.do_not_contact : null,\n"
                    "  can_send: !!(c && c.tg_chat_id && !c.do_not_contact && out.channel === 'telegram')\n"
                    "} }];"
                )
            },
        },
        {
            "id": "if-can-send",
            "name": "30_If_Can_Send",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2.2,
            "position": [100, 0],
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                    "combinator": "and",
                    "conditions": [
                        {
                            "id": "c1",
                            "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                            "leftValue": "={{ $json.can_send }}",
                            "rightValue": "",
                        }
                    ],
                },
            },
        },
        {
            "id": "tg-send",
            "name": "40_TG_Send",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [320, -100],
            "parameters": {
                "method": "POST",
                "url": "={{ 'https://api.telegram.org/bot' + $env.TG_CONVERSATION_BOT_TOKEN + '/sendMessage' }}",
                "options": {"response": {"response": {"fullResponse": True}}},
                "sendHeaders": True,
                "headerParameters": {"parameters": [
                    {"name": "Content-Type", "value": "application/json"},
                ]},
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify({ chat_id: $json.tg_chat_id, text: $json.body }) }}",
                "continueOnFail": True,
            },
        },
        {
            "id": "mark-sent",
            "name": "50_Mark_Sent",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [540, -100],
            "parameters": {
                "method": "PATCH",
                "url": "={{ $env.SUPABASE_URL + '/rest/v1/outbound_messages?id=eq.' + $('25_Merge_Context').item.json.outbound_id }}",
                "options": {"response": {"response": {"fullResponse": True}}},
                "sendHeaders": True,
                "headerParameters": {"parameters": [
                    {"name": "apikey", "value": "={{ $env.SUPABASE_SERVICE_ROLE_KEY }}"},
                    {"name": "Authorization", "value": "={{ 'Bearer ' + $env.SUPABASE_SERVICE_ROLE_KEY }}"},
                    {"name": "Content-Type", "value": "application/json"},
                ]},
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": (
                    "={{ JSON.stringify({ "
                    "status: (($json.body && $json.body.ok) ? 'sent' : 'failed'), "
                    "sent_at: new Date().toISOString() "
                    "}) }}"
                ),
            },
        },
        {
            "id": "mark-skipped",
            "name": "55_Mark_Skipped",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [320, 100],
            "parameters": {
                "method": "PATCH",
                "url": "={{ $env.SUPABASE_URL + '/rest/v1/outbound_messages?id=eq.' + $json.outbound_id }}",
                "options": {"response": {"response": {"fullResponse": True}}},
                "sendHeaders": True,
                "headerParameters": {"parameters": [
                    {"name": "apikey", "value": "={{ $env.SUPABASE_SERVICE_ROLE_KEY }}"},
                    {"name": "Authorization", "value": "={{ 'Bearer ' + $env.SUPABASE_SERVICE_ROLE_KEY }}"},
                    {"name": "Content-Type", "value": "application/json"},
                ]},
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify({ status: 'skipped' }) }}",
            },
        },
        {
            "id": "log-skip",
            "name": "60_Log_Skip",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [540, 100],
            "parameters": {
                "method": "POST",
                "url": "={{ $env.SUPABASE_URL + '/rest/v1/events_log' }}",
                "options": {"response": {"response": {"fullResponse": True}}},
                "sendHeaders": True,
                "headerParameters": {"parameters": [
                    {"name": "apikey", "value": "={{ $env.SUPABASE_SERVICE_ROLE_KEY }}"},
                    {"name": "Authorization", "value": "={{ 'Bearer ' + $env.SUPABASE_SERVICE_ROLE_KEY }}"},
                    {"name": "Content-Type", "value": "application/json"},
                ]},
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": (
                    "={{ JSON.stringify({ "
                    "partner_id: $('25_Merge_Context').item.json.partner_id, "
                    "actor: 'system', "
                    "event: 'outbound_skipped', "
                    "payload: { outbound_id: $('25_Merge_Context').item.json.outbound_id, reason: ($('25_Merge_Context').item.json.do_not_contact ? 'do_not_contact' : ($('25_Merge_Context').item.json.tg_chat_id ? 'wrong_channel' : 'no_tg_chat_id')), channel: $('25_Merge_Context').item.json.channel } "
                    "}) }}"
                ),
            },
        },
    ]

    new_connections = {
        "01_Schedule_Trigger": {"main": [[{"node": "10_Fetch_Outbound", "type": "main", "index": 0}]]},
        "10_Fetch_Outbound":    {"main": [[{"node": "15_Split", "type": "main", "index": 0}]]},
        "15_Split":             {"main": [[{"node": "20_Fetch_Contact", "type": "main", "index": 0}]]},
        "20_Fetch_Contact":     {"main": [[{"node": "25_Merge_Context", "type": "main", "index": 0}]]},
        "25_Merge_Context":     {"main": [[{"node": "30_If_Can_Send", "type": "main", "index": 0}]]},
        "30_If_Can_Send": {
            "main": [
                [{"node": "40_TG_Send", "type": "main", "index": 0}],
                [{"node": "55_Mark_Skipped", "type": "main", "index": 0}],
            ]
        },
        "40_TG_Send":     {"main": [[{"node": "50_Mark_Sent", "type": "main", "index": 0}]]},
        "55_Mark_Skipped":{"main": [[{"node": "60_Log_Skip", "type": "main", "index": 0}]]},
    }

    wf["nodes"] = new_nodes
    wf["connections"] = new_connections
    wf = strip_readonly(wf)
    n8n("PUT", f"/workflows/{WF9_ID}", wf)
    print(f"WF9 rewritten: TG sendMessage dispatch via $env.TG_CONVERSATION_BOT_TOKEN")

if __name__ == "__main__":
    patch_loop()
    rewrite_wf9()
    print("Done.")
