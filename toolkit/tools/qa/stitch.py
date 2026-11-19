import sys
from PIL import Image
out = sys.argv[1]
parts = []
for a in sys.argv[2:]:
    f, skip = a.rsplit(":", 1)
    im = Image.open(f).convert("RGB")
    parts.append(im.crop((0, int(skip), im.width, im.height)))
W = parts[0].width; H = sum(p.height for p in parts)
img = Image.new("RGB", (W, H)); y = 0
for p in parts: img.paste(p, (0, y)); y += p.height
img.save(out)
