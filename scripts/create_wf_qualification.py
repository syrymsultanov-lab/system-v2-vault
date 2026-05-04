#!/usr/bin/env python3
"""Creates Lead Qualification Pipeline workflow in n8n."""
import json, os, sys, urllib.request, urllib.error
from pathlib import Path

env = {}
env_path = Path(__file__).parent.parent / ".env"
for line in env_path.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()

N8N_KEY = env["N8N_API_KEY"]
SB_KEY = env["SUPABASE_SERVICE_KEY"]
SB_URL = "https://njwraxmlzglmofxiwmxs.supabase.co"

def sb_headers():
    return [
        {"name": "apikey", "value": SB_KEY},
        {"name": "Authorization", "value": f"Bearer {SB_KEY}"},
        {"name": "Content-Type", "value": "application/json"},
    ]

def sb_read_headers():
    return [
        {"name": "apikey", "value": SB_KEY},
        {"name": "Authorization", "value": f"Bearer {SB_KEY}"},
    ]

def patch_headers():
    return sb_headers() + [{"name": "Prefer", "value": "return=minimal"}]

workflow = {
    "name": "Lead Qualification Pipeline v1",
    "nodes": [
        {
            "id": "node-trigger",
            "name": "Every 30s",
            "type": "n8n-nodes-base.scheduleTrigger",
            "typeVersion": 1.2,
            "position": [0, 0],
            "parameters": {
                "rule": {"interval": [{"field": "seconds", "secondsInterval": 30}]}
            },
        },
        {
            "id": "node-claim",
            "name": "Claim next job",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [220, 0],
            "parameters": {
                "method": "POST",
                "url": f"{SB_URL}/rest/v1/rpc/claim_next_ai_job",
                "sendHeaders": True,
                "headerParameters": {"parameters": sb_headers()},
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={}",
                "options": {},
            },
        },
        {
            "id": "node-if-job",
            "name": "Job found?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [440, 0],
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                    "conditions": [
                        {
                            "id": "c1",
                            "leftValue": "={{ $json.id }}",
                            "rightValue": "",
                            "operator": {"type": "string", "operation": "notEmpty"},
                        }
                    ],
                    "combinator": "and",
                }
            },
        },
        {
            "id": "node-get-lead",
            "name": "Get lead",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [660, -80],
            "parameters": {
                "method": "GET",
                "url": f"={SB_URL}/rest/v1/leads?id=eq.{{{{ $json.target_id }}}}&select=id,partner_id,name,phone,email,source,status,notes",
                "sendHeaders": True,
                "headerParameters": {"parameters": sb_read_headers()},
                "options": {},
            },
        },
        {
            "id": "node-merge",
            "name": "Merge job + lead",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [880, -80],
            "parameters": {
                "jsCode": (
                    "const job = $('Claim next job').first().json;\n"
                    "const arr = $input.first().json;\n"
                    "const lead = Array.isArray(arr) ? arr[0] : arr;\n"
                    "if (!lead || !lead.id) return [{ json: { ...job, _lead_missing: true } }];\n"
                    "return [{ json: { ...job, lead } }];"
                )
            },
        },
        {
            "id": "node-if-lead",
            "name": "Lead exists?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [1100, -80],
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                    "conditions": [
                        {
                            "id": "c2",
                            "leftValue": "={{ $json._lead_missing }}",
                            "rightValue": True,
                            "operator": {"type": "boolean", "operation": "notEquals"},
                        }
                    ],
                    "combinator": "and",
                }
            },
        },
        {
            "id": "node-ai",
            "name": "AI qualification",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [1320, -160],
            "parameters": {
                "method": "POST",
                "url": "https://api.openai.com/v1/chat/completions",
                "sendHeaders": True,
                "headerParameters": {
                    "parameters": [
                        {"name": "Authorization", "value": "=Bearer {{$env.OPENAI_API_KEY}}"},
                        {"name": "Content-Type", "value": "application/json"},
                    ]
                },
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": (
                    "={{ JSON.stringify({"
                    " model: 'gpt-4.1-mini', temperature: 0.2,"
                    " response_format: { type: 'json_object' },"
                    " messages: ["
                    "  { role: 'system', content: 'You are a lead qualification assistant for InCruises MLM."
                    " Return ONLY valid JSON: {\"score\": 0-100, \"status\": \"new\"|\"qualified\"|\"lost\","
                    " \"priority\": 1|2|3, \"reason\": \"short explanation in Russian\"}."
                    " score 70+ → qualified priority 1, 40-69 → new priority 2, <40 → lost priority 3. No markdown.' },"
                    "  { role: 'user', content: JSON.stringify({"
                    "   name: $json.lead.name, phone: $json.lead.phone,"
                    "   email: $json.lead.email, source: $json.lead.source,"
                    "   status: $json.lead.status }) }"
                    " ]"
                    "}) }}"
                ),
                "options": {},
            },
        },
        {
            "id": "node-parse",
            "name": "Parse AI result",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [1540, -160],
            "parameters": {
                "jsCode": (
                    "const prev = $('Merge job + lead').first().json;\n"
                    "const raw = $input.first().json;\n"
                    "try {\n"
                    "  const p = JSON.parse(raw.choices[0].message.content);\n"
                    "  return [{ json: { job_id: prev.id, lead_id: prev.target_id,\n"
                    "    status: p.status || 'new', priority: p.priority || 2,\n"
                    "    notes: p.reason || '', ai_result: p } }];\n"
                    "} catch(e) {\n"
                    "  return [{ json: { job_id: prev.id, lead_id: prev.target_id, _parse_error: e.message } }];\n"
                    "}"
                )
            },
        },
        {
            "id": "node-update-lead",
            "name": "Update lead",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [1760, -160],
            "parameters": {
                "method": "PATCH",
                "url": f"={SB_URL}/rest/v1/leads?id=eq.{{{{ $json.lead_id }}}}",
                "sendHeaders": True,
                "headerParameters": {"parameters": patch_headers()},
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": (
                    "={{ JSON.stringify({ status: $json.status, priority: $json.priority,"
                    " notes: $json.notes, updated_at: new Date().toISOString() }) }}"
                ),
                "options": {},
            },
        },
        {
            "id": "node-job-done",
            "name": "Mark job succeeded",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [1980, -160],
            "parameters": {
                "method": "PATCH",
                "url": f"={SB_URL}/rest/v1/ai_jobs?id=eq.{{{{ $('Parse AI result').first().json.job_id }}}}",
                "sendHeaders": True,
                "headerParameters": {"parameters": patch_headers()},
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": (
                    "={{ JSON.stringify({ status: 'succeeded',"
                    " result: $('Parse AI result').first().json.ai_result,"
                    " updated_at: new Date().toISOString() }) }}"
                ),
                "options": {},
            },
        },
        {
            "id": "node-job-fail",
            "name": "Mark job failed",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [1320, 80],
            "parameters": {
                "method": "PATCH",
                "url": f"={SB_URL}/rest/v1/ai_jobs?id=eq.{{{{ $json.id }}}}",
                "sendHeaders": True,
                "headerParameters": {"parameters": patch_headers()},
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify({ status: 'failed', updated_at: new Date().toISOString() }) }}",
                "options": {},
            },
        },
    ],
    "connections": {
        "Every 30s": {"main": [[{"node": "Claim next job", "type": "main", "index": 0}]]},
        "Claim next job": {"main": [[{"node": "Job found?", "type": "main", "index": 0}]]},
        "Job found?": {
            "main": [
                [{"node": "Get lead", "type": "main", "index": 0}],
                [],
            ]
        },
        "Get lead": {"main": [[{"node": "Merge job + lead", "type": "main", "index": 0}]]},
        "Merge job + lead": {"main": [[{"node": "Lead exists?", "type": "main", "index": 0}]]},
        "Lead exists?": {
            "main": [
                [{"node": "AI qualification", "type": "main", "index": 0}],
                [{"node": "Mark job failed", "type": "main", "index": 0}],
            ]
        },
        "AI qualification": {"main": [[{"node": "Parse AI result", "type": "main", "index": 0}]]},
        "Parse AI result": {"main": [[{"node": "Update lead", "type": "main", "index": 0}]]},
        "Update lead": {"main": [[{"node": "Mark job succeeded", "type": "main", "index": 0}]]},
    },
    "settings": {"executionOrder": "v1"},
}

payload = json.dumps(workflow).encode()
req = urllib.request.Request(
    "https://n8n.sairateam.com/api/v1/workflows",
    data=payload,
    headers={"X-N8N-API-KEY": N8N_KEY, "Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req) as r:
        body = json.loads(r.read())
        print(f"OK id={body['id']} name={body['name']}")
except urllib.error.HTTPError as e:
    print(f"ERROR {e.code}: {e.read().decode()}", file=sys.stderr)
    sys.exit(1)
