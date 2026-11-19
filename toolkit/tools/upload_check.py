"""Pre-upload check for assets/webp before they go to the Dealer Inspire media library.

WordPress answers "The server cannot process the image" when its image library runs
out of memory or time while building thumbnails. That is a server-side failure, most
often from many large files processed at once, so this tool keeps every file cheap to
process and splits the upload into small batches:

  - longest edge <= 1920 (the library rejects bigger) and <= 4 megapixels
  - simple lossy VP8 WebP: no animation, EXIF, XMP or ICC chunks (VP8X is allowed only for alpha)
  - alpha only where an image really has transparency
  - file size <= 600 KB

Usage:  python tools/upload_check.py [batch_size]     # default batch size 8
Exit code 1 if any file fails; batches go to assets/upload-batches.txt.
"""

import sys
from pathlib import Path

from PIL import Image

MAX_EDGE = 1920
MAX_PIXELS = 4_000_000
MAX_BYTES = 600 * 1024


def chunks(data: bytes) -> list[str]:
    """RIFF chunk ids of a WebP file."""
    out, i = [], 12
    while i + 8 <= len(data):
        cid = data[i:i + 4].decode("latin-1")
        size = int.from_bytes(data[i + 4:i + 8], "little")
        out.append(cid)
        i += 8 + size + (size & 1)
    return out


def check(f: Path) -> list[str]:
    data = f.read_bytes()
    problems = []
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return ["not a WebP file"]
    ids = chunks(data)
    for bad in ("ANIM", "ANMF", "EXIF", "XMP ", "ICCP"):
        if bad in ids:
            problems.append(f"has {bad.strip()} chunk")
    if "VP8L" in ids and "ALPH" not in ids:
        problems.append("lossless (VP8L); re-encode lossy")
    with Image.open(f) as im:
        w, h = im.size
        if max(w, h) > MAX_EDGE:
            problems.append(f"{w}x{h} over {MAX_EDGE}px")
        if w * h > MAX_PIXELS:
            problems.append(f"{w * h / 1e6:.2f} MP over {MAX_PIXELS / 1e6:.1f} MP")
        if im.mode == "RGBA" and im.getchannel("A").getextrema()[0] == 255:
            problems.append("alpha channel is fully opaque; save as RGB")
    if len(data) > MAX_BYTES:
        problems.append(f"{len(data) // 1024} KB over {MAX_BYTES // 1024} KB")
    return problems


def main() -> int:
    batch = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    root = Path(__file__).resolve().parent.parent
    files = sorted((root / "assets" / "webp").glob("*.webp"))
    failed = 0
    for f in files:
        p = check(f)
        if p:
            failed += 1
            print(f"FAIL {f.name}: {'; '.join(p)}")
    lines = []
    for n in range(0, len(files), batch):
        group = files[n:n + batch]
        lines.append(f"Batch {n // batch + 1} ({len(group)} files, "
                     f"{sum(g.stat().st_size for g in group) // 1024} KB)")
        lines += [f"  {g.name}" for g in group]
    (root / "assets" / "upload-batches.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{len(files)} files, {failed} failed; "
          f"{(len(files) + batch - 1) // batch} batches of up to {batch} in assets/upload-batches.txt")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
