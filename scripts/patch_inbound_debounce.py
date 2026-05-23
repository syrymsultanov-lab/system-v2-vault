#!/usr/bin/env python3
"""Patch WF TG Conversation Inbound (EEMvbCJaiN8affDR) — add double-reply debounce.

Inserts 3 nodes between 40_Insert_Inbound and 45_If_Has_Media:
  42_Wait_Debounce       : Wait 1.5 sec
  43_Debounce_Check      : HTTP POST Supabase RPC should_process_inbound_now(msg_id)
  44_If_Latest           : IF returned TRUE → continue, FALSE → end

Closes race: 2 inbound from same chat_id within <2s — only newest reaches AI.
RPC was created via migration `debounce_inbound_helper_function` (2026-05-23).

Idempotent — checks if nodes exist before adding.
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
SUPABASE_URL = env["SUPABASE_URL"]
SR_KEY = env["SUPABASE_SERVICE_ROLE_KEY"]


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


WAIT_NODE = {
    "id": "42-wait-debounce",
    "name": "42_Wait_Debounce",
    "type": "n8n-nodes-base.wait",
    "typeVersion": 1.1,
    "position": [340, 80],
    "parameters": {"amount": 1.5, "unit": "seconds"},
}

CHECK_NODE = {
    "id": "43-debounce-check",
    "name": "43_Debounce_Check",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.2,
    "position": [480, 80],
    "parameters": {
        "method": "POST",
        "url": f"{SUPABASE_URL}/rest/v1/rpc/should_process_inbound_now",
        "sendHeaders": True,
        "headerParameters": {
            "parameters": [
                {"name": "apikey", "value": SR_KEY},
                {"name": "Authorization", "value": f"Bearer {SR_KEY}"},
                {"name": "Content-Type", "value": "application/json"},
            ]
        },
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": '={{ JSON.stringify({ p_msg_id: $(\'40_Insert_Inbound\').item.json.body[0].id }) }}',
        "options": {"response": {"response": {"responseFormat": "json"}}},
    },
}

IF_NODE = {
    "id": "44-if-latest",
    "name": "44_If_Latest",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2.2,
    "position": [620, 80],
    "parameters": {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
            "combinator": "and",
            "conditions": [
                {
                    "id": "is-latest",
                    "leftValue": "={{ $json }}",
                    "rightValue": True,
                    "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                }
            ],
        },
        "options": {},
    },
}


def patch():
    wf = n8n("GET", f"/workflows/{WF_ID}")
    nodes = wf["nodes"]
    conns = wf["connections"]

    # Upsert each debounce node (add if missing, overwrite parameters if exists)
    desired = {n["name"]: n for n in (WAIT_NODE, CHECK_NODE, IF_NODE)}
    for i, n in enumerate(nodes):
        if n["name"] in desired:
            nodes[i] = desired[n["name"]]
            print(f"  ~ updated node: {n['name']}")
    existing = {n["name"] for n in nodes}
    for name, node in desired.items():
        if name not in existing:
            nodes.append(node)
            print(f"  + added node: {name}")

    # Rewire: 40_Insert_Inbound was -> 45_If_Has_Media
    # New flow: 40_Insert_Inbound -> 42_Wait_Debounce -> 43_Debounce_Check -> 44_If_Latest
    #          44_If_Latest [TRUE]  -> 45_If_Has_Media
    #          44_If_Latest [FALSE] -> (no connection = workflow ends)
    conns["40_Insert_Inbound"] = {
        "main": [[{"node": "42_Wait_Debounce", "type": "main", "index": 0}]]
    }
    conns["42_Wait_Debounce"] = {
        "main": [[{"node": "43_Debounce_Check", "type": "main", "index": 0}]]
    }
    conns["43_Debounce_Check"] = {
        "main": [[{"node": "44_If_Latest", "type": "main", "index": 0}]]
    }
    conns["44_If_Latest"] = {
        "main": [
            [{"node": "45_If_Has_Media", "type": "main", "index": 0}],  # TRUE branch
            [],  # FALSE branch — no connection, ends here
        ]
    }

    wf_out = strip_readonly(wf)
    n8n("PUT", f"/workflows/{WF_ID}", wf_out)

    # Verify
    wf_after = n8n("GET", f"/workflows/{WF_ID}")
    nodes_after = {n["name"] for n in wf_after["nodes"]}
    conn_after = wf_after["connections"]

    for name in ("42_Wait_Debounce", "43_Debounce_Check", "44_If_Latest"):
        assert name in nodes_after, f"verify FAIL: {name} missing after PUT"

    assert conn_after["40_Insert_Inbound"]["main"][0][0]["node"] == "42_Wait_Debounce"
    assert conn_after["44_If_Latest"]["main"][0][0]["node"] == "45_If_Has_Media"

    print("[OK] debounce nodes inserted + connections rewired")
    print("Flow: 40_Insert_Inbound -> 42_Wait(1.5s) -> 43_Check_RPC -> 44_If_Latest [TRUE] -> 45_If_Has_Media")


if __name__ == "__main__":
    patch()
