"""Build assets/webp/ from the Figma image fills.

Source per image: tools/_work/upscaled/<name>.png when it exists (only the blurry ones
are upscaled, user rule 2026-11-10), else tools/_work/source/<name>.png.
Every file is fitted inside 1920x1080 (Dealer Inspire media-library limit), saved as a
plain lossy WebP (q85, method 6, no metadata). Opaque RGBA is flattened to RGB.
Files ending in -m are mobile crops made by tools/mobile_crops.py.

Usage:  python tools/build_webp.py [name ...]
"""
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC, UP, OUT = ROOT / "tools/_work/source", ROOT / "tools/_work/upscaled", ROOT / "assets/webp"
FIT_W, FIT_H = 1920, 1080


def build(name: str, q: int = 85) -> str:
    src = UP / f"{name}.png"
    tag = "upscaled"
    if not src.exists():
        src, tag = SRC / f"{name}.png", "source"
    im = Image.open(src)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA")
    if im.mode == "RGBA" and im.getchannel("A").getextrema()[0] == 255:
        im = im.convert("RGB")
    w, h = im.size
    s = min(1.0, FIT_W / w, FIT_H / h)
    if s < 1:
        im = im.resize((round(w * s), round(h * s)), Image.LANCZOS)
    out = OUT / f"{name}.webp"
    im.save(out, "WEBP", quality=q, method=6, exact=im.mode == "RGBA")
    while out.stat().st_size > 600 * 1024 and q > 60:
        q -= 5
        im.save(out, "WEBP", quality=q, method=6, exact=im.mode == "RGBA")
    return f"{name:22} {tag:8} {w}x{h} -> {im.size[0]}x{im.size[1]} q{q} {out.stat().st_size // 1024}KB"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    names = sys.argv[1:] or sorted(p.stem for p in SRC.glob("*.png") if not p.stem.endswith("-orig"))
    for n in names:
        print(build(n), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
