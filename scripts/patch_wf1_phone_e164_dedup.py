#!/usr/bin/env python3
"""Patch WF1 — Lead Intake:
  Fix dedup by normalizing phone to E.164 in `Normalize Input` jsCode.

Discovered 2026-05-26: 2 form-submits 45 min apart (Салтанат Кенигесова)
produced 2 separate leads/contacts/outbounds because:
  - submit #1 phone='77080277396' (no +)
  - submit #2 phone='+77080277396'
  - old normalize: replace(/[^\\d+]/g, '') -> strings differ -> dedup misses

Fix:
  - strip ALL non-digit (drop +)
  - if 11 digits start with '8' -> replace '8' with '7' (RU/KZ)
  - prepend '+' -> stable E.164
Result: both inputs -> '+77080277396'.
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
TARGET_NAME_SUBSTR = "WF1"


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


NEW_JS = """const body = $json.body ?? $json;
const clean = (v) => (v ?? '').toString().trim();
const email = clean(body.email).toLowerCase();
// Phone -> E.164: strip non-digits, normalize KZ/RU leading 8->7, prepend +
let digits = clean(body.phone).replace(/\\D/g, '');
if (digits.length === 11 && digits.startsWith('8')) digits = '7' + digits.slice(1);
const phone = digits ? '+' + digits : '';
return [{
  partner_id: clean(body.partner_id),
  name: clean(body.name),
  last_name: clean(body.last_name),
  phone,
  email,
  country: clean(body.country),
  city: clean(body.city),
  messenger: clean(body.messenger),
  messenger_handle: clean(body.messenger_handle),
  consent: body.consent === true || body.consent === 'true',
  consent_at: body.consent ? (body.consent_at || new Date().toISOString()) : null,
  source: clean(body.source) || 'landing',
  channel: clean(body.channel) || 'web',
  received_at: new Date().toISOString()
}];"""


def find_wf():
    wfs = n8n("GET", "/workflows")
    data = wfs.get("data", wfs) if isinstance(wfs, dict) else wfs
    matches = [w for w in data if TARGET_NAME_SUBSTR in w.get("name", "") and "Lead Intake" in w.get("name", "")]
    if not matches:
        raise SystemExit(f"No workflow matching '{TARGET_NAME_SUBSTR}' + 'Lead Intake' found")
    if len(matches) > 1:
        raise SystemExit(f"Ambiguous: {[w['name'] for w in matches]}")
    return matches[0]["id"], matches[0]["name"]


def patch():
    wf_id, wf_name = find_wf()
    print(f"[..] Target: {wf_name} (id={wf_id})")
    wf = n8n("GET", f"/workflows/{wf_id}")
    nodes = wf["nodes"]

    target = next((n for n in nodes if n["name"] == "Normalize Input"), None)
    if target is None:
        raise SystemExit("Normalize Input not found")

    old_code = target["parameters"].get("jsCode", "")
    if "digits.startsWith('8')" in old_code and "'+' + digits" in old_code:
        print("[OK] Already patched — no-op")
        return

    target["parameters"]["jsCode"] = NEW_JS

    wf_out = strip_readonly(wf)
    n8n("PUT", f"/workflows/{wf_id}", wf_out)

    wf_after = n8n("GET", f"/workflows/{wf_id}")
    node_after = next(n for n in wf_after["nodes"] if n["name"] == "Normalize Input")
    code_after = node_after["parameters"]["jsCode"]
    assert "digits.startsWith('8')" in code_after, "verify FAIL: KZ normalize missing"
    assert "'+' + digits" in code_after, "verify FAIL: E.164 prefix missing"
    assert "replace(/\\D/g, '')" in code_after, "verify FAIL: strip non-digits missing"
    print("[OK] WF1 Normalize Input patched — phone normalized to E.164")


if __name__ == "__main__":
    patch()
