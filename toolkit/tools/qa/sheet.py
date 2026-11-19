"""Lay a tall screenshot out as side-by-side columns for review.
usage: python -I sheet.py in.png out_prefix cols_per_sheet col_height"""
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGB"); pre = sys.argv[2]; cols = int(sys.argv[3]); ch = int(sys.argv[4])
segs = [im.crop((0, y, im.width, min(im.height, y + ch))) for y in range(0, im.height, ch)]
for s in range(0, len(segs), cols):
    group = segs[s:s + cols]
    sheet = Image.new("RGB", (len(group) * (im.width + 20), ch), "red")
    for i, g in enumerate(group): sheet.paste(g, (i * (im.width + 20), 0))
    sheet.save(f"{pre}{s // cols}.png"); print(f"{pre}{s // cols}.png", sheet.size)
