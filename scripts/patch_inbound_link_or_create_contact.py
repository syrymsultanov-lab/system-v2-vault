#!/usr/bin/env python3
"""Patch TG Conversation Inbound (EEMvbCJaiN8affDR):
  Replace 20_Find_Contact GET-only lookup with POST to RPC link_tg_contact_by_handle.
  RPC atomically: (1) find by chat_id, (2) link by handle (form lead), (3) create fresh.

Closes blocker discovered 2026-05-23:
  New TG users hitting bot via landing-form deep-link were silently dropped at
  30_If_Allowed because their contact didn't exist in DB.

RPC was created in migration `tg_lead_to_contact_bridge`.
Idempotent — overwrite same parameters on each run.
"""
import json
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).parent.parent
env = {}
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()

N8N_BASE = f"{env['N8N_URL']}/api/v1"
N8N_KEY = env["N8N_API_KEY"]
WF_ID = "EEMvbCJaiN8affDR"


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


NEW_FIND_CONTACT_PARAMS = {
    "method": "POST",
    "url": "={{ $env.SUPABASE_URL + '/rest/v1/rpc/link_tg_contact_by_handle' }}",
    "sendBody": True,
    "specifyBody": "json",
    "jsonBody": (
        "={{ JSON.stringify({ "
        "p_chat_id: $('10_Parse_Update').item.json.chat_id, "
        "p_handle: $('10_Parse_Update').item.json.from_handle, "
        "p_name: $('10_Parse_Update').item.json.from_username "
        "}) }}"
    ),
    "options": {
        "response": {
            "response": {
                "fullResponse": True
            }
        }
    },
    "sendHeaders": True,
    "headerParameters": {
        "parameters": [
            {"name": "apikey", "value": "={{ $env.SUPABASE_SERVICE_ROLE_KEY }}"},
            {"name": "Authorization", "value": "={{ 'Bearer ' + $env.SUPABASE_SERVICE_ROLE_KEY }}"},
            {"name": "Content-Type", "value": "application/json"},
        ]
    },
}


def patch():
    wf = n8n("GET", f"/workflows/{WF_ID}")
    nodes = wf["nodes"]

    target = None
    for n in nodes:
        if n["name"] == "20_Find_Contact":
            target = n
            break
    if target is None:
        raise SystemExit("20_Find_Contact not found")

    target["parameters"] = NEW_FIND_CONTACT_PARAMS

    wf_out = strip_readonly(wf)
    n8n("PUT", f"/workflows/{WF_ID}", wf_out)

    wf_after = n8n("GET", f"/workflows/{WF_ID}")
    node_after = next(n for n in wf_after["nodes"] if n["name"] == "20_Find_Contact")
    assert node_after["parameters"]["method"] == "POST", "verify FAIL: method not POST"
    assert "rpc/link_tg_contact_by_handle" in node_after["parameters"]["url"], "verify FAIL: URL wrong"
    print("[OK] 20_Find_Contact -> POST /rpc/link_tg_contact_by_handle")
    print("Flow: bot inbound → atomic link/create contact → process normally")


if __name__ == "__main__":
    patch()
