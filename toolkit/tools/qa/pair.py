"""Figma-over-page comparison crop. usage: python -I pair.py out.png figmafile secx secy x0 y0 x1 y1 [scale]
(x/y in section-render coordinates; secx/secy = render origin on the page)"""
import sys
from PIL import Image
from pathlib import Path
R = Path(__file__).resolve().parents[2]
out, f, sx, sy, x0, y0, x1, y1 = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:9])
sc = float(sys.argv[9]) if len(sys.argv) > 9 else 1
im = Image.open(R / f"figma/{f}.png").convert("RGBA"); bg = Image.new("RGBA", im.size, "white"); bg.alpha_composite(im)
pg = Image.open(R / "qa/shots/desk-1920.png").convert("RGB")
a = bg.convert("RGB").crop((x0, y0, x1, y1)); b = pg.crop((x0 + sx, y0 + sy, x1 + sx, y1 + sy))
c = Image.new("RGB", (x1 - x0, 2 * (y1 - y0) + 6), "red"); c.paste(a, (0, 0)); c.paste(b, (0, y1 - y0 + 6))
c.resize((int(c.width * sc), int(c.height * sc))).save(out)
