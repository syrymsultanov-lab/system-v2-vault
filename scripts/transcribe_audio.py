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
import subprocess
import sys
import time
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


def transcribe(file_path: Path) -> str:
    size_mb = file_path.stat().st_size / 1024 / 1024
    if size_mb > 25:
        raise RuntimeError(
            f"{file_path.name}: {size_mb:.1f} MB > 25 MB Whisper limit. "
            "Split via ffmpeg: ffmpeg -i input.mp3 -f segment -segment_time 600 out_%03d.mp3"
        )

    cmd = [
        "curl", "-sS", "--fail-with-body",
        "--max-time", "900",
        "--retry", "3",
        "--retry-delay", "5",
        "--retry-connrefused",
        "-X", "POST",
        WHISPER_URL,
        "-H", f"Authorization: Bearer {OPENAI_KEY}",
        "-F", f"file=@{file_path}",
        "-F", f"model={MODEL}",
        "-F", f"language={LANGUAGE}",
        "-F", "response_format=verbose_json",
        "-F", "temperature=0",
    ]

    last_err = ""
    for attempt in (1, 2, 3):
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=1000)
            if res.returncode == 0:
                data = json.loads(res.stdout)
                out_lines = [f"# Transcript: {file_path.name}", f"Duration: {data.get('duration', 0):.1f}s", ""]
                if "segments" in data:
                    for seg in data["segments"]:
                        ts = f"[{seg['start']:.1f}-{seg['end']:.1f}]"
                        out_lines.append(f"{ts} {seg['text'].strip()}")
                else:
                    out_lines.append(data.get("text", ""))
                return "\n".join(out_lines)
            last_err = res.stderr or res.stdout
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            last_err = str(e)
        if attempt < 3:
            print(f"    retry {attempt}/3 after error: {last_err[:200]}", flush=True)
            time.sleep(5 * attempt)
    raise RuntimeError(f"Whisper failed after 3 attempts: {last_err[:500]}")


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
