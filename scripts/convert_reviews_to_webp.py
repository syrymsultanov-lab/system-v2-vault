#!/usr/bin/env python3
"""Convert raw review photos → optimized webp 800x800 1:1 center-crop.

Source: obsidian-vault/reference/reviews/raw/*.jpeg
Output: assets/images/reviews/<slug>.webp
Target: < 100 KB per file, quality 80.
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).parent.parent
SRC = ROOT / "obsidian-vault/reference/reviews/raw"
DST = ROOT / "assets/images/reviews"
DST.mkdir(parents=True, exist_ok=True)

SIZE = 800
QUALITY = 80

NAME_MAP = {
    "Baktigul_Kadyralieva": "baktigul-k",
    "Botagoz_Aitkalieva": "botagoz-a",
    "Symbat_Aubakirova": "symbat-a",
    "Nadyra_Narimbetova": "nadyra-n",
    "Laura_Abuova": "laura-a",
    "Meerim_Aibashova": "meerim-a",
}

def smart_crop_square(img: Image.Image) -> Image.Image:
    """Square crop. For portrait (h>w) bias to top (face area). For landscape — true center."""
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    if h > w:
        top = int((h - side) * 0.08)
    else:
        top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))

def process(jpeg_path: Path, slug: str):
    img = Image.open(jpeg_path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img = smart_crop_square(img)
    img = img.resize((SIZE, SIZE), Image.LANCZOS)
    out = DST / f"{slug}.webp"
    q = QUALITY
    while q >= 60:
        img.save(out, "WEBP", quality=q, method=6)
        size_kb = out.stat().st_size / 1024
        if size_kb < 100:
            break
        q -= 5
    print(f"  {jpeg_path.name} -> {out.name} ({size_kb:.1f} KB, q={q})")
    return size_kb

if __name__ == "__main__":
    total = 0
    for raw_name, slug in NAME_MAP.items():
        jpeg = SRC / f"{raw_name}.jpeg"
        if not jpeg.exists():
            print(f"  SKIP: {jpeg.name} (missing)")
            continue
        total += process(jpeg, slug)
    print(f"Total: {total:.1f} KB")
