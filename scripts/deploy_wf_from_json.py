#!/usr/bin/env python3
"""Deploy n8n workflows from JSON files with $env.* inlining.

Usage:
    python scripts/deploy_wf_from_json.py            # deploys all in DEPLOY_ORDER
    python scripts/deploy_wf_from_json.py WF1 WF5    # deploys specific WFs

Skips WFs already present in n8n (matched by name).
"""
import json, re, sys, urllib.request, urllib.error
from pathlib import Path

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------
env = {}
env_path = Path(__file__).parent.parent / ".env"
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()

N8N_KEY  = env["N8N_API_KEY"]
N8N_BASE = "https://n8n.sairateam.com/api/v1"

# Defaults for optional vars
env.setdefault("OPENAI_MODEL",    "gpt-4.1-mini")
env.setdefault("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions")

# ---------------------------------------------------------------------------
# $env.* resolver
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# n8n API helpers
# ---------------------------------------------------------------------------
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
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"n8n {method} {path} -> {e.code}: {e.read().decode()}") from e

def get_existing():
    resp = n8n("GET", "/workflows?limit=200")
    return {w["name"]: w["id"] for w in resp.get("data", [])}

# ---------------------------------------------------------------------------
# Deploy one workflow
# ---------------------------------------------------------------------------
def deploy(json_path: Path, existing: dict) -> str | None:
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    name = raw["name"]

    if name in existing:
        print(f"  SKIP  {name}  (id={existing[name]})")
        return existing[name]

    resolved = deep_resolve(raw)
    for key in ("id", "versionId", "meta", "active"):
        resolved.pop(key, None)

    resp   = n8n("POST", "/workflows", resolved)
    wf_id  = resp["id"]
    print(f"  CREATE {name}  id={wf_id}")

    n8n("POST", f"/workflows/{wf_id}/activate")
    print(f"  ACTIVE {wf_id}")
    return wf_id

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
WF_DIR = Path(__file__).parent.parent / "SYSTEM_V2_n8n_workflows_JSON" / "workflows"

# WF3 already deployed; WF8/WF10/WF11 need missing tables — skipped for now
DEPLOY_ORDER = ["WF1", "WF2", "WF4", "WF5", "WF6", "WF9", "WF12"]

prefixes = sys.argv[1:] if len(sys.argv) > 1 else DEPLOY_ORDER
existing = get_existing()
print(f"Existing workflows in n8n: {len(existing)}\n")

for prefix in prefixes:
    matches = sorted(WF_DIR.glob(f"{prefix}_*.json"))
    if not matches:
        print(f"  NOT FOUND: {prefix}")
        continue
    try:
        deploy(matches[0], existing)
    except RuntimeError as e:
        print(f"  ERROR {prefix}: {e}")

print("\nDone.")
