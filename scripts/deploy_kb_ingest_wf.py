#!/usr/bin/env python3
"""Create WF14 KB Ingest — webhook receives {source, chunks:[str]},
embeds via OpenAI text-embedding-3-small, inserts to kb_chunks.
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

PREP_CODE = r"""
const src = $json.body.source;
const offset = Number($json.body.chunk_offset || 0);
const chunks = $json.body.chunks || [];
return [{ json: { source: src, chunk_offset: offset, chunks: chunks } }];
"""

EMBED_BODY = (
    "={{ JSON.stringify({ model: 'text-embedding-3-small', input: $json.chunks }) }}"
)

BUILD_ROW_CODE = r"""
const upstream = $('10_Prep_Chunks').item.json;
const data = ($json.body && $json.body.data) || [];
const rows = upstream.chunks.map((c, i) => ({
  source: upstream.source,
  chunk_index: upstream.chunk_offset + i,
  content: c,
  embedding: data[i] ? data[i].embedding : null,
  partner_id: null,
  metadata: { char_len: c.length }
}));
return [{ json: { rows: rows, inserted_count: rows.length } }];
"""

wf_body = {
    "name": "WF14 — KB Ingest",
    "nodes": [
        {
            "id": "webhook",
            "name": "01_Webhook",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 2,
            "position": [-700, 0],
            "webhookId": "kb-ingest-7f4b2a91",
            "parameters": {
                "httpMethod": "POST",
                "path": "kb-ingest",
                "responseMode": "lastNode",
                "options": {},
            },
        },
        {
            "id": "prep",
            "name": "10_Prep_Chunks",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [-480, 0],
            "parameters": {"jsCode": PREP_CODE},
        },
        {
            "id": "embed",
            "name": "20_OpenAI_Embed",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [-260, 0],
            "parameters": {
                "method": "POST",
                "url": "https://api.openai.com/v1/embeddings",
                "options": {"response": {"response": {"fullResponse": True}}, "timeout": 60000},
                "sendHeaders": True,
                "headerParameters": {"parameters": [
                    {"name": "Authorization", "value": "={{ 'Bearer ' + $env.OPENAI_API_KEY }}"},
                    {"name": "Content-Type", "value": "application/json"},
                ]},
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": EMBED_BODY,
            },
        },
        {
            "id": "buildrow",
            "name": "30_Build_Row",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [-40, 0],
            "parameters": {"jsCode": BUILD_ROW_CODE},
        },
        {
            "id": "insert",
            "name": "40_Insert_Chunk",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [180, 0],
            "parameters": {
                "method": "POST",
                "url": "={{ $env.SUPABASE_URL + '/rest/v1/kb_chunks' }}",
                "options": {"response": {"response": {"fullResponse": True}}},
                "sendHeaders": True,
                "headerParameters": {"parameters": [
                    {"name": "apikey", "value": "={{ $env.SUPABASE_SERVICE_ROLE_KEY }}"},
                    {"name": "Authorization", "value": "={{ 'Bearer ' + $env.SUPABASE_SERVICE_ROLE_KEY }}"},
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "Prefer", "value": "return=minimal"},
                ]},
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify($json.rows) }}",
            },
        },
    ],
    "connections": {
        "01_Webhook":     {"main": [[{"node": "10_Prep_Chunks", "type": "main", "index": 0}]]},
        "10_Prep_Chunks": {"main": [[{"node": "20_OpenAI_Embed", "type": "main", "index": 0}]]},
        "20_OpenAI_Embed":{"main": [[{"node": "30_Build_Row", "type": "main", "index": 0}]]},
        "30_Build_Row":   {"main": [[{"node": "40_Insert_Chunk", "type": "main", "index": 0}]]},
    },
    "settings": {},
}

existing = n8n("GET", "/workflows?limit=200")
match = next((w for w in existing.get("data", []) if w["name"] == wf_body["name"]), None)
if match:
    wf_id = match["id"]
    n8n("PUT", f"/workflows/{wf_id}", wf_body)
    print(f"UPDATE {wf_id}")
else:
    resp = n8n("POST", "/workflows", wf_body)
    wf_id = resp["id"]
    print(f"CREATE {wf_id}")

if not match or not match.get("active"):
    n8n("POST", f"/workflows/{wf_id}/activate")
    print("ACTIVATED")

print(f"Webhook: https://n8n.sairateam.com/webhook/kb-ingest")
