"""Upscale the photos qa_sweep.js flags as blurry (2026-11-13, Final MLP automation).

Input: the JSON printed by tools/qa/blurry_list.js ({"<webp name>": <displayed width at 1920>}).
For each file in assets/webp/: the A3 Brands AIO upscaler x2 (Real-ESRGAN, user rule 2026-11-11), then resize to the
displayed width (longest edge capped at 1920, so displayed / file is about 1.0) and save as plain lossy WebP q85.
One image at a time (PC rule). The old file is kept in tools/_work/pre-upscale/. Prints the names it replaced.

Usage:  python upscale_stretched.py "<project folder>" "<json or path to json>"
"""
import base64, io, json, shutil, sys, time, urllib.error, urllib.request
from pathlib import Path
from PIL import Image

API = "https://a3brands-aiotools.vercel.app/api/upscale"


def remote_x2(im):
    buf = io.BytesIO(); im.save(buf, "PNG"); mime = "image/png"
    if buf.tell() > 6_000_000:
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=95); mime = "image/jpeg"
    body = json.dumps({"image": f"data:{mime};base64," + base64.b64encode(buf.getvalue()).decode(), "scale": 2, "faceEnhance": False}).encode()
    req = urllib.request.Request(API, data=body, headers={"content-type": "application/json", "user-agent": "Mozilla/5.0"})
    for attempt in range(12):
        try:
            url = json.loads(urllib.request.urlopen(req, timeout=300).read())["url"]; break
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 11: raise
            print(f"  rate-limited, waiting {30 + attempt * 15}s", flush=True); time.sleep(30 + attempt * 15)
    time.sleep(8)
    data = urllib.request.urlopen(urllib.request.Request(url, headers={"user-agent": "Mozilla/5.0"}), timeout=300).read()
    return Image.open(io.BytesIO(data)).convert("RGB")


def main():
    proj = Path(sys.argv[1]); arg = sys.argv[2]
    jobs = json.loads(Path(arg).read_text(encoding="utf-8") if Path(arg).exists() else arg)
    webp, keep = proj / "assets" / "webp", proj / "tools" / "_work" / "pre-upscale"
    keep.mkdir(parents=True, exist_ok=True)
    done = []
    for name, dw in jobs.items():
        f = webp / name
        if not f.exists():
            print(f"SKIP {name}: not in assets/webp"); continue
        src = keep / name if (keep / name).exists() else f  # always start from the original file
        orig = Image.open(src); alpha = orig.getchannel("A") if orig.mode in ("RGBA", "LA") else None
        im = orig.convert("RGB"); w, h = im.size
        tw = min(int(dw), 1920 if w >= h else int(1920 * w / h))
        if tw <= w:
            print(f"SKIP {name}: already {w}px wide (needs {dw})"); continue
        print(f"{name}: {w}x{h} -> x2 -> {tw}px wide", flush=True)
        try:
            up = remote_x2(im)
        except Exception as e:  # service down: keep the old file, report it
            print(f"FAIL {name}: {e}"); continue
        out = up.resize((tw, round(h * tw / w)), Image.LANCZOS)
        if max(out.size) > 1920:
            s = 1920 / max(out.size); out = out.resize((round(out.size[0] * s), round(out.size[1] * s)), Image.LANCZOS)
        if alpha is not None:  # cut-outs keep their transparency (the upscaler returns RGB only)
            out = out.convert("RGBA"); out.putalpha(alpha.resize(out.size, Image.LANCZOS))
        if not (keep / name).exists():
            shutil.copy2(f, keep / name)
        out.save(f, "WEBP", quality=85, method=6)
        done.append(name)
    print("REPLACED " + json.dumps(done))


if __name__ == "__main__":
    main()
