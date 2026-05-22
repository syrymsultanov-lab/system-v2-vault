#!/usr/bin/env python3
"""Chunk KB sources from obsidian-vault/docs/ and POST to WF14 ingest webhook.

KB rule (2026-05-21, Сырым): canonical sources are ONLY obsidian-vault/docs/.
reference/, projects/, .kb_extracted/, Файлы с Google диска/ — НЕ источник KB.
Meta-files (README.md, Questions for Saira.md, Saira Interview Questions.md)
исключены — содержат TODO/драфт, не факты.

Chunking: ~1000 chars on paragraph/blank-line boundaries.
Idempotent: DELETE existing rows for source before re-ingest.
Batches: 80 chunks per webhook POST (OpenAI batch embed handles it).
"""
import json, re, sys, urllib.request, urllib.error, urllib.parse
from pathlib import Path

ROOT = Path(__file__).parent.parent
env = {}
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()

SUPABASE_URL = env["SUPABASE_URL"]
SR_KEY = env["SUPABASE_SERVICE_ROLE_KEY"]
WEBHOOK = "https://n8n.sairateam.com/webhook/kb-ingest"
MAX_CHARS = 1000
BATCH_SIZE = 80

KB_SOURCES = [
    "obsidian-vault/docs/101RU_SIMPLE_COMPANY_PRESENTATION.md",
    "obsidian-vault/docs/104RU_3.2_INDEPENDENT_PARTNER_AGREEMENT.md",
    "obsidian-vault/docs/106RU_3.2_MEMBER_AGREEMENT.md",
    "obsidian-vault/docs/109RU_INCOME_AND_INCENTIVE_OVERVIEW.md",
    "obsidian-vault/docs/214RU_INCOME_AND_INCENTIVE_GUIDE.md",
    "obsidian-vault/docs/503RU_PAYMENT_AGREEMENT.md",
    "obsidian-vault/docs/InCruises Ranks.md",
    "obsidian-vault/docs/Presentation Script.md",
    "obsidian-vault/docs/Company Facts.md",
]

def strip_md_noise(text: str) -> str:
    text = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, count=1, flags=re.DOTALL)
    text = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), text)
    text = re.sub(r"^\s*##\s*Связи\s*\n(?:^[ \t]*[-*].*\n?)+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*Page\s+\d+\s*$", "", text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r"\f", "\n\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def chunk_text(text: str) -> list[str]:
    text = strip_md_noise(text)
    paras = re.split(r"\n\s*\n", text)
    chunks, buf = [], ""
    for p in paras:
        p = p.strip()
        if not p:
            continue
        if len(p) > MAX_CHARS * 1.5:
            sentences = re.split(r"(?<=[.!?])\s+", p)
            for s in sentences:
                if len(buf) + len(s) + 1 > MAX_CHARS and buf:
                    chunks.append(buf.strip())
                    buf = s
                else:
                    buf = (buf + " " + s) if buf else s
            continue
        if len(buf) + len(p) + 2 > MAX_CHARS and buf:
            chunks.append(buf.strip())
            buf = p
        else:
            buf = (buf + "\n\n" + p) if buf else p
    if buf.strip():
        chunks.append(buf.strip())
    return [c for c in chunks if len(c) >= 40]

def http(method, url, headers, body=None, timeout=300):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {url} -> {e.code}: {e.read().decode()}") from e

def delete_source(source: str):
    http(
        "DELETE",
        f"{SUPABASE_URL}/rest/v1/kb_chunks?source=eq.{urllib.parse.quote(source)}",
        {"apikey": SR_KEY, "Authorization": f"Bearer {SR_KEY}"},
    )

def post_batch(source: str, chunk_offset: int, batch: list[str]):
    http(
        "POST", WEBHOOK,
        {"Content-Type": "application/json"},
        {"source": source, "chunk_offset": chunk_offset, "chunks": batch},
    )

def ingest_source(rel: str):
    path = ROOT / rel
    if not path.exists():
        print(f"  SKIP (missing): {rel}")
        return
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw = path.read_text(encoding="cp1251", errors="ignore")
    chunks = chunk_text(raw)
    if not chunks:
        print(f"  SKIP (empty): {rel}")
        return
    delete_source(rel)
    total = len(chunks)
    print(f"  {rel}: {total} chunks", flush=True)
    for off in range(0, total, BATCH_SIZE):
        batch = chunks[off:off+BATCH_SIZE]
        post_batch(rel, off, batch)
        print(f"    batch {off}-{off+len(batch)-1} OK", flush=True)

if __name__ == "__main__":
    targets = sys.argv[1:] or KB_SOURCES
    for rel in targets:
        ingest_source(rel)
    print("Done.")
