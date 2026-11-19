"""Small JPG thumbnails of the device-matrix screenshots for qa/index.html (one image at a time, low memory)."""
import gc
from pathlib import Path
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "qa/screens"
OUT.mkdir(exist_ok=True)
for p in sorted((ROOT / "qa/shots").glob("*x*.png")):
    im = Image.open(p)
    W, H = im.size
    w = min(W, 480)
    h = round(H * w / W)
    im = im.convert("RGB").resize((w, h), Image.BOX)
    im.save(OUT / f"device-{p.stem}.jpg", quality=78)
    print(p.stem, w, h, flush=True)
    del im
    gc.collect()
