#!/usr/bin/env python3
"""FTP-deploy reviews.html + assets/images/reviews/*.webp to Hostinger public_html.

Creds from .env. Uses stdlib ftplib (no curl dependency).
Idempotent: STOR overwrites existing files.
"""
import ftplib
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
env = {}
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()

HOST = env["FTP_HOST"]
USER = env["FTP_USER"]
PASS = env["FTP_PASS"]
PORT = int(env.get("FTP_PORT", "21"))
REMOTE_BASE = env.get("FTP_PATH", "domains/sairateam.com/public_html").rstrip("/")

UPLOADS = [
    ("reviews.html", f"{REMOTE_BASE}/reviews.html"),
    ("assets/images/reviews/baktigul-k.webp", f"{REMOTE_BASE}/assets/images/reviews/baktigul-k.webp"),
    ("assets/images/reviews/botagoz-a.webp", f"{REMOTE_BASE}/assets/images/reviews/botagoz-a.webp"),
    ("assets/images/reviews/symbat-a.webp", f"{REMOTE_BASE}/assets/images/reviews/symbat-a.webp"),
    ("assets/images/reviews/nadyra-n.webp", f"{REMOTE_BASE}/assets/images/reviews/nadyra-n.webp"),
    ("assets/images/reviews/laura-a.webp", f"{REMOTE_BASE}/assets/images/reviews/laura-a.webp"),
    ("assets/images/reviews/meerim-a.webp", f"{REMOTE_BASE}/assets/images/reviews/meerim-a.webp"),
]

def ensure_dir(ftp: ftplib.FTP, remote_path: str):
    """Create remote dir chain if missing."""
    parts = remote_path.strip("/").split("/")
    cur = ""
    for p in parts:
        cur = f"{cur}/{p}" if cur else f"/{p}"
        try:
            ftp.cwd(cur)
        except ftplib.error_perm:
            ftp.mkd(cur)
            ftp.cwd(cur)
    ftp.cwd("/")

def upload(ftp: ftplib.FTP, local: str, remote: str):
    local_path = ROOT / local
    if not local_path.exists():
        print(f"  SKIP (missing): {local}")
        return
    remote_dir = "/".join(remote.split("/")[:-1])
    ensure_dir(ftp, remote_dir)
    with local_path.open("rb") as fh:
        ftp.storbinary(f"STOR /{remote}", fh)
    print(f"  {local} -> /{remote} ({local_path.stat().st_size} bytes)")

def main():
    print(f"Connecting {USER}@{HOST}:{PORT}")
    with ftplib.FTP() as ftp:
        ftp.connect(HOST, PORT, timeout=60)
        ftp.login(USER, PASS)
        ftp.set_pasv(True)
        for local, remote in UPLOADS:
            upload(ftp, local, remote)
        print("Done.")

if __name__ == "__main__":
    main()
