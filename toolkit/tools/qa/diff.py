"""Pixel diff of each Figma section render against the page screenshot.
Each render is auto-aligned within +-16px of its nominal page position, then the
mean absolute difference (0-255) and the worst 100px bands are reported.
usage: python -I diff.py page.png"""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
page = np.asarray(Image.open(sys.argv[1]).convert("RGB")).astype(np.int16)
SECTIONS = [  # file, nominal x, y on the page (Figma frame 1:547 coordinates)
    ("s01-hero", 0, 0), ("s02-stats", 76, 2200), ("s03-bands", 76, 2419), ("s04-cta1", 0, 4741), ("s05-performance", 0, 4941), ("s06-splits", 80, 7800),
    ("s08-technology", 76, 9666), ("s09-charging", 0, 12105), ("s10-interior", 76, 13432), ("s11-exterior", 76, 16046), ("s12-face", 80, 17831),
    ("s13-wheels", 0, 18523), ("s14-safety", 0, 19865), ("s15-gallery", 0, 21427), ("s16-trims", 80, 23260), ("s17-ctabar", 0, 24289), ("s18-disclaimer", 80, 24489)]
SEO = float((ROOT / "qa/seo-delta.txt").read_text()) if (ROOT / "qa/seo-delta.txt").exists() else 0
SECTIONS = [(n, x, y + SEO if y >= 24489 else y) for n, x, y in SECTIONS]
out = ROOT / "qa/visual-diff"; out.mkdir(parents=True, exist_ok=True)
def score(F, x, y):
    h, w = F.shape[:2]
    if y < 0 or x < 0 or y + h > page.shape[0] or x + w > page.shape[1]: return 1e9
    return np.abs(page[y:y + h, x:x + w] - F).mean()
report = []
for name, nx, ny in SECTIONS:
    _im = Image.open(ROOT / f"figma/{name}.png").convert("RGBA"); _bg = Image.new("RGBA", _im.size, (255, 255, 255, 255)); _bg.alpha_composite(_im)
    F = np.asarray(_bg.convert("RGB")).astype(np.int16)
    h, w = F.shape[:2]
    Fs = F[::4, ::4]
    best = None
    for dy in range(-24, 25, 2):
        for dx in range(-24, 25, 2):
            x, y = int(round(nx)) + dx, int(round(ny)) + dy
            if y < 0 or x < 0 or y + h > page.shape[0] or x + w > page.shape[1]: continue
            s = np.abs(page[y:y + h:4, x:x + w:4] - Fs).mean()
            if best is None or s < best[0]: best = (s, x, y)
    _, bx, by = best
    best = min(((score(F, bx + a, by + c), bx + a, by + c) for a in range(-2, 3) for c in range(-2, 3)))
    s, x, y = best
    D = np.abs(page[y:y + h, x:x + w] - F).mean(axis=2)
    bands = sorted(((D[i:i + 100].mean(), i) for i in range(0, h, 100)), reverse=True)[:4]
    Image.fromarray(np.clip(D * 3, 0, 255).astype(np.uint8)).save(out / f"{name}-diff.png")
    Image.fromarray(page[y:y + h, x:x + w].astype(np.uint8)).save(out / f"{name}-page.png")
    r = {"section": name, "offset": [round(x - nx, 1), round(y - ny, 1)], "mean": round(float(s), 2),
         "hot_bands": [[int(i), round(float(v), 1)] for v, i in bands]}
    report.append(r)
    print(f"{name:24} offset {r['offset']}  mean diff {r['mean']:6.2f}  hot bands (y:mean) " + "  ".join(f"{i}:{v}" for i, v in r["hot_bands"]))
json.dump(report, open(ROOT / "qa/report-visual-diff.json", "w"), indent=1)
