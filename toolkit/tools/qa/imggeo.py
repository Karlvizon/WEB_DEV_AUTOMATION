"""SIFT image geometry: for every image frame on the 1920 page, estimate the
scale / rotation / shift between the page render and the Figma render of the
same box. Figma renders are pasted at their diff-aligned page positions."""
import json, math
from pathlib import Path
import cv2, numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
page = np.asarray(Image.open(ROOT / "qa/shots/desk-1920.png").convert("RGB"))
SEO = int(round(float((ROOT / "qa/seo-delta.txt").read_text())))
SECTIONS = [("s01-hero", 0, 0), ("s02-stats", 76, 2204), ("s03-bands", 76, 2423), ("s04-cta1", 0, 4741), ("s05-performance", 0, 4941), ("s06-splits", 80, 7800),
    ("s08-technology", 76, 9670), ("s09-charging", 0, 12105), ("s10-interior", 76, 13436), ("s11-exterior", 76, 16050), ("s12-face", 80, 17831),
    ("s13-wheels", 0, 18523), ("s14-safety", 0, 19865), ("s15-gallery", 0, 21427), ("s16-trims", 80, 23260), ("s17-ctabar", 0, 24289 + SEO), ("s18-disclaimer", 80, 24493 + SEO)]
canvas = Image.new("RGBA", (page.shape[1], page.shape[0]), (255, 255, 255, 255))
for n, x, y in SECTIONS:
    canvas.alpha_composite(Image.open(ROOT / f"figma/{n}.png").convert("RGBA"), (x, y))
fig = np.asarray(canvas.convert("RGB"))
Image.fromarray(fig).save(ROOT / "qa/visual-diff/figma-full.png")
sift = cv2.SIFT_create(3000); bf = cv2.BFMatcher()
rows = []; worst = 0
for b in [b for b in json.load(open(ROOT / "qa/imgboxes-1920.json")) if b["x"] >= 0 and b["x"] + b["w"] <= 1920]:
    x0, y0, x1, y1 = int(b["x"]) + 6, int(b["y"]) + 6, int(b["x"] + b["w"]) - 6, int(b["y"] + b["h"]) - 6
    if x1 - x0 < 40 or y1 - y0 < 40: continue
    A = cv2.cvtColor(page[y0:y1, x0:x1], cv2.COLOR_RGB2GRAY); B = cv2.cvtColor(fig[y0:y1, x0:x1], cv2.COLOR_RGB2GRAY)
    k1, d1 = sift.detectAndCompute(A, None); k2, d2 = sift.detectAndCompute(B, None)
    if d1 is None or d2 is None or len(k1) < 8 or len(k2) < 8: rows.append(f"{b['src']:36} too few features"); continue
    good = [m for m, n in bf.knnMatch(d1, d2, k=2) if m.distance < 0.7 * n.distance]
    if len(good) < 8: rows.append(f"{b['src']:36} too few matches ({len(good)})"); continue
    M, inl = cv2.estimateAffinePartial2D(np.float32([k1[m.queryIdx].pt for m in good]), np.float32([k2[m.trainIdx].pt for m in good]), method=cv2.RANSAC, ransacReprojThreshold=2)
    s = math.hypot(M[0, 0], M[1, 0]); rot = math.degrees(math.atan2(M[1, 0], M[0, 0]))
    # shift of the frame centre
    cx, cy = (x1 - x0) / 2, (y1 - y0) / 2
    sx, sy = M[0, 0] * cx + M[0, 1] * cy + M[0, 2] - cx, M[1, 0] * cx + M[1, 1] * cy + M[1, 2] - cy
    bad = abs(s - 1) > 0.01 or abs(rot) > 0.3 or math.hypot(sx, sy) > 3
    worst += bad
    rows.append(f"{'BAD ' if bad else 'ok  '}{b['src']:36} inliers {int(inl.sum()):4}  scale {s:.4f}  rot {rot:+.2f}  shift ({sx:+.1f},{sy:+.1f})")
print("\n".join(rows)); print(f"\n{len(rows)} image frames checked, {worst} off (scale>1%, rot>0.3deg or shift>3px)")
open(ROOT / "qa/imggeo.txt", "w").write("\n".join(rows) + f"\n{len(rows)} checked, {worst} off\n")
