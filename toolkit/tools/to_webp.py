"""Re-encode assets/source images to WebP with neither edge over MAX_EDGE px.

The Dealer Inspire media library rejects an upload whose longest edge exceeds
1920px ("exceeds the maximum image dimensions of 1920px"), so anything larger
silently never reaches the library and the page 404s on it. 1920 itself passes.

Resizing happens from the PNG source rather than the existing WebP, so the
image is only lossily encoded once. Source PNGs live in assets/source and are kept for re-encoding.

Usage:  python tools/to_webp.py [name ...]            # default: every source
"""

import sys
from pathlib import Path

from PIL import Image

MAX_EDGE = 1920
QUALITY = 85
METHOD = 6


def capped(size: tuple[int, int]) -> tuple[int, int]:
    """Scale proportionally so the longest edge is MAX_EDGE, or leave as is."""
    w, h = size
    if max(w, h) <= MAX_EDGE:
        return w, h
    scale = MAX_EDGE / max(w, h)
    return max(1, round(w * scale)), max(1, round(h * scale))


def convert(src: Path, out: Path) -> tuple[tuple[int, int], tuple[int, int], int]:
    with Image.open(src) as im:
        if im.mode in ("P", "LA"):
            im = im.convert("RGBA")
        elif im.mode not in ("RGB", "RGBA", "L"):
            im = im.convert("RGB")
        if im.mode == "RGBA" and im.getchannel("A").getextrema()[0] == 255:
            im = im.convert("RGB")
        before = im.size
        after = capped(before)
        if after != before:
            im = im.resize(after, Image.LANCZOS)
        has_alpha = im.mode == "RGBA"
        im.save(out, "WEBP", quality=QUALITY, method=METHOD, exact=has_alpha)
    return before, after, out.stat().st_size


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    src_dir = root / "assets" / "source"
    out_dir = root / "assets" / "webp"
    out_dir.mkdir(parents=True, exist_ok=True)

    if len(sys.argv) > 1:
        files = [src_dir / (n if n.endswith(".png") else n + ".png") for n in sys.argv[1:]]
        for f in files:
            if not f.is_file():
                print(f"source not found: {f}")
                return 1
    else:
        files = sorted(src_dir.glob("*.png"))

    changed = 0
    for src in files:
        out = out_dir / (src.stem + ".webp")
        before, after, size = convert(src, out)
        note = "unchanged" if before == after else "resized"
        if before != after:
            changed += 1
        print(f"{note:9} {src.stem:24} {before[0]}x{before[1]} -> {after[0]}x{after[1]}"
              f"  {size/1024:.0f}KB")

    print(f"\n{len(files)} file(s), {changed} resized to fit {MAX_EDGE}px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
