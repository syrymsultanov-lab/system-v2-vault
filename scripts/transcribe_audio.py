#!/usr/bin/env python3
"""Transcribe audio files via OpenAI Whisper API.

Source:  obsidian-vault/reference/interviews/raw/*.{mp3,m4a,ogg,wav,webm}
Output:  obsidian-vault/reference/interviews/transcripts/<name>.txt

Usage:
  python scripts/transcribe_audio.py                 # all unprocessed files
  python scripts/transcribe_audio.py <file.mp3>      # specific file
  python scripts/transcribe_audio.py --force         # re-transcribe all

Cost: $0.006/min (whisper-1). 40 min audio ≈ $0.24.
Max file size: 25 MB (Whisper API limit). For longer — split with ffmpeg.

Idempotent: skips files where transcript already exists (unless --force).
"""
import json
import mimetypes
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "obsidian-vault/reference/interviews/raw"
DST = ROOT / "obsidian-vault/reference/interviews/transcripts"
DST.mkdir(parents=True, exist_ok=True)
SRC.mkdir(parents=True, exist_ok=True)

env = {}
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()

OPENAI_KEY = env["OPENAI_API_KEY"]
WHISPER_URL = "https://api.openai.com/v1/audio/transcriptions"
MODEL = "whisper-1"
LANGUAGE = "ru"
SUPPORTED = {".mp3", ".m4a", ".mp4", ".ogg", ".wav", ".webm", ".mpga", ".mpeg", ".flac"}


def build_multipart(file_path: Path, fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    body = bytearray()
    for k, v in fields.items():
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'.encode()
    mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    body += f"Content-Type: {mime}\r\n\r\n".encode()
    body += file_path.read_bytes()
    body += f"\r\n--{boundary}--\r\n".encode()
    return bytes(body), boundary


def transcribe(file_path: Path) -> str:
    size_mb = file_path.stat().st_size / 1024 / 1024
    if size_mb > 25:
        raise RuntimeError(
            f"{file_path.name}: {size_mb:.1f} MB > 25 MB Whisper limit. "
            "Split via ffmpeg: ffmpeg -i input.mp3 -f segment -segment_time 600 out_%03d.mp3"
        )

    fields = {
        "model": MODEL,
        "language": LANGUAGE,
        "response_format": "verbose_json",
        "temperature": "0",
    }
    body, boundary = build_multipart(file_path, fields)

    req = urllib.request.Request(
        WHISPER_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {OPENAI_KEY}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Whisper error {e.code}: {e.read().decode()}") from e

    out_lines = [f"# Transcript: {file_path.name}", f"Duration: {data.get('duration', 0):.1f}s", ""]
    if "segments" in data:
        for seg in data["segments"]:
            ts = f"[{seg['start']:.1f}-{seg['end']:.1f}]"
            out_lines.append(f"{ts} {seg['text'].strip()}")
    else:
        out_lines.append(data.get("text", ""))
    return "\n".join(out_lines)


def process(file_path: Path, force: bool):
    out_path = DST / f"{file_path.stem}.md"
    if out_path.exists() and not force:
        print(f"  SKIP (exists): {out_path.name}")
        return
    size_mb = file_path.stat().st_size / 1024 / 1024
    print(f"  {file_path.name} ({size_mb:.1f} MB) ...", flush=True)
    text = transcribe(file_path)
    out_path.write_text(text, encoding="utf-8")
    print(f"    -> {out_path.name} ({len(text)} chars)")


def main():
    args = sys.argv[1:]
    force = "--force" in args
    args = [a for a in args if not a.startswith("--")]

    if args:
        targets = [Path(a) if Path(a).is_absolute() else (ROOT / a) for a in args]
    else:
        targets = sorted(
            f for f in SRC.iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED
        )

    if not targets:
        print(f"No audio files in {SRC}. Drop .mp3/.m4a/.ogg there or pass a path.")
        return

    for t in targets:
        if not t.exists():
            print(f"  SKIP (missing): {t}")
            continue
        process(t, force)
    print("Done.")


if __name__ == "__main__":
    main()
