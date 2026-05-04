#!/usr/bin/env python3
"""Upsert n8n workflows by name.

Usage:
    python scripts/upsert_wf.py WF3 WF13

If a workflow with the same name exists: deactivate -> PUT -> activate.
Otherwise: POST -> activate.
"""
import json, re, sys, urllib.request, urllib.error
from pathlib import Path

env = {}
env_path = Path(__file__).parent.parent / ".env"
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()

N8N_KEY  = env["N8N_API_KEY"]
N8N_BASE = env.get("N8N_URL", "https://n8n.sairateam.com").rstrip("/") + "/api/v1"

env.setdefault("OPENAI_MODEL",    "gpt-4.1-mini")
env.setdefault("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions")

_PURE_RE  = re.compile(r'^=\{\{\s*\$env\.(\w+)\s*\}\}$')
_MIXED_RE = re.compile(r'\$env\.(\w+)')

def resolve_str(s: str) -> str:
    m = _PURE_RE.match(s)
    if m:
        return env.get(m.group(1), s)
    def _replace(m):
        val = env.get(m.group(1), f"$env.{m.group(1)}")
        return f"'{val}'"
    return _MIXED_RE.sub(_replace, s)

def deep_resolve(obj):
    if isinstance(obj, dict):
        return {k: deep_resolve(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deep_resolve(i) for i in obj]
    if isinstance(obj, str):
        return resolve_str(obj)
    return obj

def n8n(method, path, data=None):
    url  = f"{N8N_BASE}{path}"
    body = json.dumps(data).encode() if data is not None else None
    req  = urllib.request.Request(
        url, data=body,
        headers={"X-N8N-API-KEY": N8N_KEY, "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"n8n {method} {path} -> {e.code}: {e.read().decode()}") from e

def get_existing():
    resp = n8n("GET", "/workflows?limit=250")
    return {w["name"]: w for w in resp.get("data", [])}

def upsert(json_path: Path, existing: dict):
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    name = raw["name"]
    resolved = raw
    for key in ("id", "versionId", "meta", "active", "tags", "createdAt", "updatedAt", "pinData", "shared", "triggerCount", "isArchived"):
        resolved.pop(key, None)

    if name in existing:
        wf_id = existing[name]["id"]
        was_active = existing[name].get("active", False)
        print(f"  EXISTS {name}  id={wf_id}  active={was_active}")
        if was_active:
            try:
                n8n("POST", f"/workflows/{wf_id}/deactivate")
                print(f"  DEACT  {wf_id}")
            except RuntimeError as e:
                print(f"  WARN   deactivate failed: {e}")
        n8n("PUT", f"/workflows/{wf_id}", resolved)
        print(f"  PUT    {wf_id}")
        n8n("POST", f"/workflows/{wf_id}/activate")
        print(f"  ACTIVE {wf_id}")
        return wf_id

    resp  = n8n("POST", "/workflows", resolved)
    wf_id = resp["id"]
    print(f"  CREATE {name}  id={wf_id}")
    n8n("POST", f"/workflows/{wf_id}/activate")
    print(f"  ACTIVE {wf_id}")
    return wf_id

WF_DIR = Path(__file__).parent.parent / "SYSTEM_V2_n8n_workflows_JSON" / "workflows"
prefixes = sys.argv[1:]
if not prefixes:
    print("Usage: upsert_wf.py WF3 WF13 ...")
    sys.exit(1)

existing = get_existing()
print(f"Existing workflows in n8n: {len(existing)}\n")

for prefix in prefixes:
    matches = sorted(WF_DIR.glob(f"{prefix}_*.json"))
    if not matches:
        print(f"  NOT FOUND: {prefix}")
        continue
    try:
        upsert(matches[0], existing)
    except RuntimeError as e:
        print(f"  ERROR {prefix}: {e}")

print("\nDone.")
