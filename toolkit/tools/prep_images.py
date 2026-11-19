"""Cut every Figma image fill to exactly the area its frame shows, then write assets/webp/.

For each job: take the frame's visible area from tools/_work/source/<src>.png (crop % from the
Figma design context, or object-fit:cover), keep its native pixels (fitted inside 1920x1080),
and save it with the frame's aspect, so the page shows it with object-fit:cover and nothing is cut.

Blurry rule (user, 2026-11-10): an image is blurry when it is shown larger than its file at 1920
(frame px / file px > 0.9). Only those regions are upscaled x2, with the A3 Brands AIO tools
upscaler (user, 2026-11-11), one at a time, then rendered at the frame's design size.
Frames taller than 1080 at output are written as two stacked halves (<out>-a / <out>-b, the top
one 1px taller).

Usage:  python tools/prep_images.py            (all jobs)
        python tools/prep_images.py name ...   (some jobs)
"""
import base64
import io
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools/_work/source"
UP = ROOT / "tools/_work/upscaled"
OUT = ROOT / "assets/webp"
API = "https://a3brands-aiotools.vercel.app/api/upscale"
C = "cover"

# figma/jobs.json: {"jobs": {"<out>": ["<source>", frame_w, frame_h, "cover" | [iw, ih, il, it]]},
#                   "whole": {"<out>": "<source>"}}   (whole = file kept as is: hero for mobile, cut-outs, arrow)
_J = json.loads((ROOT / "figma/jobs.json").read_text(encoding="utf8"))
JOBS = {k: (v[0], v[1], v[2], v[3] if v[3] == C else tuple(v[3])) for k, v in _J["jobs"].items()}
WHOLE = _J.get("whole", {})


def region(W, H, fw, fh, crop):
    if crop == C:
        s = max(fw / W, fh / H)
        w, h = fw / s, fh / s
        return (W - w) / 2, (H - h) / 2, w, h
    iw, ih, il, it = crop
    return -il / iw * W, -it / ih * H, 100 / iw * W, 100 / ih * H


def remote_x2(im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    mime = "image/png"
    if buf.tell() > 3_000_000:
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=95)
        mime = "image/jpeg"
    body = json.dumps({"image": f"data:{mime};base64," + base64.b64encode(buf.getvalue()).decode(),
                       "scale": 2, "faceEnhance": False}).encode()
    req = urllib.request.Request(API, data=body, headers={"content-type": "application/json", "user-agent": "Mozilla/5.0"})
    for attempt in range(12):
        try:
            url = json.loads(urllib.request.urlopen(req, timeout=300).read())["url"]
            break
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            code = getattr(e, "code", 0)
            if attempt >= (11 if code == 429 else 3):
                raise
            print(f"  upscaler error {code or e}, waiting {30 + attempt * 15}s", flush=True)
            time.sleep(30 + attempt * 15)
    time.sleep(8)
    data = urllib.request.urlopen(urllib.request.Request(url, headers={"user-agent": "Mozilla/5.0"}), timeout=300).read()
    return Image.open(io.BytesIO(data)).convert("RGB")


def save_webp(im, name, q=85):
    out = OUT / f"{name}.webp"
    im.save(out, "WEBP", quality=q, method=6)
    while out.stat().st_size > 600 * 1024 and q > 60:
        q -= 5
        im.save(out, "WEBP", quality=q, method=6)
    return f"{im.size[0]}x{im.size[1]} q{q} {out.stat().st_size // 1024}KB"


def flat(im):
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.getchannel("A"))
        return bg
    return im.convert("RGB")


def job(name, src, fw, fh, crop, report):
    im = flat(Image.open(SRC / f"{src}.png"))
    W, H = im.size
    x, y, w, h = region(W, H, fw, fh, crop)
    box = (max(0, round(x)), max(0, round(y)), min(W, round(x + w)), min(H, round(y + h)))
    part = im.crop(box)
    if box != (round(x), round(y), round(x + w), round(y + h)):
        canvas = Image.new("RGB", (round(w), round(h)), (255, 255, 255))
        canvas.paste(part, (box[0] - round(x), box[1] - round(y)))
        part = canvas
    ratio = fw / part.size[0]
    blurry = ratio > 0.9
    tag = "native"
    if blurry:
        cache = UP / f"{name}.png"
        if cache.exists():
            part = Image.open(cache).convert("RGB")
        else:
            try:
                part = remote_x2(part)
                part.save(cache)
                tag = "upscaled"
            except Exception as e:
                tag = f"UPSCALE-FAILED({e})"
        if tag == "native":
            tag = "upscaled"
    k = min(part.size[0] / fw, 1920 / fw)
    if fh * k > 1080 and 1080 / fh >= 1.0:
        k = 1080 / fh  # fits inside 1080 tall and still >= 1 file px per design px: no split needed
    ow, oh = round(fw * k), round(fh * k)
    img = part.resize((ow, oh), Image.LANCZOS)
    if oh > 1080:
        top = oh // 2 + 1
        a = save_webp(img.crop((0, 0, ow, top)), f"{name}-a")
        b = save_webp(img.crop((0, oh - (oh - top) - 1, ow, oh)), f"{name}-b")
        report.append(f"{name:20} {fw}x{fh} region {part.size[0]}x{part.size[1]} ratio {ratio:.2f} {tag} halves {a} | {b}")
    else:
        report.append(f"{name:20} {fw}x{fh} region {round(w)}x{round(h)} ratio {ratio:.2f} {tag} -> {save_webp(img, name)}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    UP.mkdir(parents=True, exist_ok=True)
    names = sys.argv[1:] or list(JOBS) + list(WHOLE)
    report = []
    for n in names:
        if n in WHOLE:
            im = Image.open(SRC / f"{WHOLE[n]}.png")
            if im.mode == "RGBA" and im.getchannel("A").getextrema()[0] == 255:
                im = im.convert("RGB")
            w, h = im.size
            s = min(1.0, 1920 / w, 1080 / h)
            if s < 1:
                im = im.resize((round(w * s), round(h * s)), Image.LANCZOS)
            out = OUT / f"{n}.webp"
            im.save(out, "WEBP", quality=85, method=6, exact=im.mode == "RGBA")
            report.append(f"{n:20} whole {im.size[0]}x{im.size[1]} {out.stat().st_size // 1024}KB")
        else:
            job(n, *JOBS[n], report)
        print(report[-1], flush=True)
    (ROOT / "qa").mkdir(exist_ok=True)
    (ROOT / "qa/images.txt").write_text("\n".join(report) + "\n", encoding="utf8")


if __name__ == "__main__":
    main()
