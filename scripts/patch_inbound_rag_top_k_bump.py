#!/usr/bin/env python3
"""Bump 77_RAG_Retrieve p_top_k 5 -> 10.

Reason: Q «нет круга» / «структура в глубину» — RAG miss на mlm_context Гл.7/11.
top_k=5 (3 canonical + 2 mlm) недостаточно. top_k=10 (6 canonical + 4 mlm by default ratio).
Idempotent.
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

N8N_URL = env["N8N_URL"]
N8N_KEY = env["N8N_API_KEY"]
WF_ID = "EEMvbCJaiN8affDR"

def n8n(method, path, data=None):
    url = f"{N8N_URL}/api/v1{path}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        url, data=body,
        headers={"X-N8N-API-KEY": N8N_KEY, "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} -> {e.code}: {e.read().decode()}") from e

NEW_JSON_BODY = "={{ JSON.stringify({ p_query_embedding: $json.body.data[0].embedding, p_top_k: 10, p_partner_id: $('25_Check_Contact').item.json.contact.partner_id }) }}"

wf = n8n("GET", f"/workflows/{WF_ID}")
nodes = wf["nodes"]
patched = False
for node in nodes:
    if node["name"] == "77_RAG_Retrieve":
        old = node["parameters"].get("jsonBody", "")
        node["parameters"]["jsonBody"] = NEW_JSON_BODY
        patched = True
        print(f"OLD: {old}")
        print(f"NEW: {NEW_JSON_BODY}")
        break
if not patched:
    raise RuntimeError("77_RAG_Retrieve not found")

put_body = {
    "name": wf["name"],
    "nodes": nodes,
    "connections": wf["connections"],
    "settings": wf.get("settings", {}),
}
n8n("PUT", f"/workflows/{WF_ID}", put_body)
print(f"Patched 77_RAG_Retrieve in WF {WF_ID}: top_k=5 -> 10")
