#!/usr/bin/env python3
"""Ingest KB markdown files into kb_chunks with OpenAI embeddings.

Chunks each file by ~500-token windows on paragraph boundaries.
Uses text-embedding-3-small (1536 dims).
Source = relative path; partner_id = NULL (system-wide).

Idempotent per file: deletes existing rows for the source first.
"""
import json, urllib.request, urllib.error, re, sys
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
OPENAI_KEY = env["OPENAI_API_KEY"]
EMBED_MODEL = "text-embedding-3-small"

KB_FILES = [
    "obsidian-vault/reference/InCruises Knowledge Base.md",
    "obsidian-vault/reference/InCruises Compensation Plan.md",
    "obsidian-vault/reference/Business Rules.md",
    "obsidian-vault/projects/AI Agent Answers.md",
]

# ---------------------------------------------------------------------------
# Chunking — paragraph aware, soft cap ~500 tokens (~2000 chars)
# ---------------------------------------------------------------------------
MAX_CHARS = 2000

def chunk_markdown(text: str) -> list[str]:
    paras = re.split(r"\n\s*\n", text)
    chunks, buf = [], ""
    for p in paras:
        p = p.strip()
        if not p:
            continue
        if len(buf) + len(p) + 2 > MAX_CHARS and buf:
            chunks.append(buf.strip())
            buf = p
        else:
            buf = (buf + "\n\n" + p) if buf else p
    if buf.strip():
        chunks.append(buf.strip())
    return chunks

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def http(method, url, headers, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {url} -> {e.code}: {e.read().decode()}") from e

def embed_batch(texts: list[str]) -> list[list[float]]:
    resp = http(
        "POST",
        "https://api.openai.com/v1/embeddings",
        {
            "Authorization": f"Bearer {OPENAI_KEY}",
            "Content-Type": "application/json",
        },
        {"model": EMBED_MODEL, "input": texts},
    )
    return [d["embedding"] for d in resp["data"]]

def sb_delete_source(source: str):
    http(
        "DELETE",
        f"{SUPABASE_URL}/rest/v1/kb_chunks?source=eq.{urllib.parse.quote(source)}",
        {
            "apikey": SR_KEY,
            "Authorization": f"Bearer {SR_KEY}",
        },
    )

def sb_insert_rows(rows: list[dict]):
    http(
        "POST",
        f"{SUPABASE_URL}/rest/v1/kb_chunks",
        {
            "apikey": SR_KEY,
            "Authorization": f"Bearer {SR_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        rows,
    )

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
import urllib.parse

def ingest_file(rel_path: str):
    path = ROOT / rel_path
    if not path.exists():
        print(f"  SKIP (missing): {rel_path}")
        return
    text = path.read_text(encoding="utf-8")
    chunks = chunk_markdown(text)
    if not chunks:
        print(f"  SKIP (empty): {rel_path}")
        return
    print(f"  {rel_path}: {len(chunks)} chunks")
    embeddings = embed_batch(chunks)
    sb_delete_source(rel_path)
    rows = [
        {
            "source": rel_path,
            "chunk_index": i,
            "content": c,
            "embedding": e,
            "partner_id": None,
            "metadata": {"char_len": len(c)},
        }
        for i, (c, e) in enumerate(zip(chunks, embeddings))
    ]
    sb_insert_rows(rows)
    print(f"    inserted {len(rows)} rows")

if __name__ == "__main__":
    targets = sys.argv[1:] or KB_FILES
    print(f"Ingesting {len(targets)} KB file(s)...\n")
    for rel in targets:
        ingest_file(rel)
    print("\nDone.")
