#!/usr/bin/env python3
"""Patch TG Conversation Inbound (EEMvbCJaiN8affDR):
  Fix 35_Log_Unhandled jsonBody — events_log has no partner_id column.
  Map to actual schema: entity_type, entity_id, event, actor, actor_id, payload.

Discovered 2026-05-25 via smoke (execution 120757):
  PGRST204 "Could not find the 'partner_id' column of 'events_log' in the schema cache".
  Audit log for unknown TG senders silently failed. AI block worked, log did not.
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


NEW_JSON_BODY = (
    "={{ JSON.stringify({ "
    "entity_type: 'contact', "
    "entity_id: ($json.contact && $json.contact.id) || null, "
    "actor: 'lead', "
    "actor_id: ($json.contact && $json.contact.id) || null, "
    "event: ($json.contact_found ? 'tg_inbound_blocked' : 'tg_inbound_unknown_sender'), "
    "payload: { "
    "from_handle: $json.parsed.from_handle, "
    "from_id: $json.parsed.from_id, "
    "chat_id: $json.parsed.chat_id, "
    "text: $json.parsed.text, "
    "has_media: $json.parsed.has_media, "
    "is_start: $json.parsed.is_start, "
    "start_payload: $json.parsed.start_payload, "
    "contact_found: $json.contact_found, "
    "allowed: $json.allowed "
    "} "
    "}) }}"
)


def patch():
    wf = n8n("GET", f"/workflows/{WF_ID}")
    nodes = wf["nodes"]

    target = None
    for n in nodes:
        if n["name"] == "35_Log_Unhandled":
            target = n
            break
    if target is None:
        raise SystemExit("35_Log_Unhandled not found")

    target["parameters"]["jsonBody"] = NEW_JSON_BODY

    wf_out = strip_readonly(wf)
    n8n("PUT", f"/workflows/{WF_ID}", wf_out)

    wf_after = n8n("GET", f"/workflows/{WF_ID}")
    node_after = next(n for n in wf_after["nodes"] if n["name"] == "35_Log_Unhandled")
    assert "partner_id" not in node_after["parameters"]["jsonBody"], "verify FAIL: partner_id still present"
    assert "entity_type: 'contact'" in node_after["parameters"]["jsonBody"], "verify FAIL: entity_type missing"
    print("[OK] 35_Log_Unhandled jsonBody fixed — partner_id removed, entity_type/entity_id/actor_id added")


if __name__ == "__main__":
    patch()
