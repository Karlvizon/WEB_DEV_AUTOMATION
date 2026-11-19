"""Pixel diff of every Figma sub-section against the 1920 page screenshot, plus SIFT image geometry.

Figma: tools/_work/figma/full.png (1:1 render of frame 1:2) and figma/abs.txt (absolute node boxes).
Page:  qa/shots/d1920.png (node tools/qa/fullshot.js 1920 qa/shots/d1920.png).
Each sub-section (top-level sections; the sub-frames of Capability / Design / Technology / Trim)
is placed at its Figma y + the section's measured shift (qa/shifts.json from textpos.js: the
deliberate desktop spacing rules move whole sections), then aligned within +-16px.
Reports mean absolute difference (0-255) and the worst 100px band per section, writes side-by-side
pairs to qa/visual-diff/, and for every image box larger than 200x150 estimates scale / rotation /
shift between page and Figma with SIFT + RANSAC (affine, partial).
usage: python -I tools/qa/pixeldiff.py
"""
import json
import math
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ROOT = Path(__file__).resolve().parents[2]
fig = np.asarray(Image.open(ROOT / "tools/_work/figma/full.png").convert("RGB"))  # uint8: light on memory (user PC rule 2026-11-11)
page = np.asarray(Image.open(ROOT / "qa/shots/d1920.png").convert("RGB"))
shifts = json.loads((ROOT / "qa/shifts.json").read_text())
CATS = set(json.loads((ROOT / "project.json").read_text(encoding="utf8"))["figma"].get("groups", []))
nodes = []
for l in (ROOT / "figma/abs.txt").read_text(encoding="utf8").splitlines():
    m = re.match(r"\s*(\d+) (\S+)\s+(\S+) x\s*(-?[\d.]+) y\s*(-?[\d.]+) w\s*([\d.]+) h\s*([\d.]+)\s*(.*)", l)
    if not m:
        continue
    d, nid, kind, x, y, w, h, name = m.groups()
    nodes.append((int(d), nid, kind, float(x), float(y), float(w), float(h), name.strip()))
parent_of_depth3 = {}
cur2 = None
for d, nid, kind, *_ in nodes:
    if d == 2:
        cur2 = nid
    if d == 3:
        parent_of_depth3[nid] = cur2
secs = [n for n in nodes if (n[0] == 2 and n[1] not in CATS) or (n[0] == 3 and parent_of_depth3.get(n[1]) in CATS)]
secs.sort(key=lambda n: n[4])
out = ROOT / "qa/visual-diff"
out.mkdir(parents=True, exist_ok=True)
report, last = [], 0.0


def score(F, x, y):
    h, w = F.shape[:2]
    if y < 0 or x < 0 or y + h > page.shape[0] or x + w > page.shape[1]:
        return 1e9
    return np.abs(page[y:y + h:2, x:x + w:2].astype(np.int16) - F[::2, ::2]).mean()


placed = []
for d, nid, kind, x, y, w, h, name in secs:
    if kind != "fram" or w < 300 or h < 40:
        continue
    sh = shifts.get(nid, last)
    last = sh
    X, Y, W, H = int(round(x)), int(round(y)), int(round(w)), int(round(h))
    F = fig[Y:Y + H, X:X + min(W, 1920 - X)].astype(np.int16)
    best = None
    for dy in range(-16, 17, 2):
        for dx in range(-4, 5, 2):
            s = score(F, X + dx, int(round(Y + sh)) + dy)
            if best is None or s < best[0]:
                best = (s, dx, dy)
    s, dx, dy = best
    for ddy in (-1, 1):
        s2 = score(F, X + dx, int(round(Y + sh)) + dy + ddy)
        if s2 < s:
            s, dy = s2, dy + ddy
    py = int(round(Y + sh)) + dy
    P = page[py:py + F.shape[0], X + dx:X + dx + F.shape[1]].astype(np.int16)
    s = np.abs(P - F).mean()
    diff = np.abs(P - F).mean(axis=(1, 2))
    bands = [(diff[i:i + 100].mean(), i) for i in range(0, max(1, len(diff) - 99), 50)]
    worst = max(bands)
    report.append(f"{nid:7} {name[:34]:34} {W}x{H}  shift {sh:+5.0f} align dx {dx:+d} dy {dy:+d}  mean diff {s:5.1f}  worst band {worst[0]:5.1f} @ +{worst[1]}px")
    pair = np.concatenate([F, np.full((F.shape[0], 12, 3), (255, 0, 255), np.int16), P], axis=1).astype(np.uint8)
    Image.fromarray(pair).resize((pair.shape[1] // 3, max(1, pair.shape[0] // 3))).save(out / f"{nid.replace(':', '-')}.png")
    placed.append((nid, X, Y, sh + dy, dx))

# SIFT geometry per image box (Figma rectangle / image nodes)
sift = cv2.SIFT_create(nfeatures=1500)
geo = []
for d, nid, kind, x, y, w, h, name in nodes:
    if kind not in ("roun", "rect", "fram") or w < 200 or h < 150:
        continue
    if not (name.startswith("Rectangle") or name.startswith("image") or name in ("Hero", "Discover Explore", "Content", "Design 2", "Technology 3", "Technology 8")):
        continue
    sec = max([p for p in placed if p[2] <= y + 1], key=lambda p: p[2], default=None)
    if not sec:
        continue
    _, _, _, dy, dx = sec
    X, Y, W, H = int(round(x)), int(round(y)), int(round(w)), int(round(h))
    F = fig[Y:Y + H, X:X + W].astype(np.uint8)
    py = int(round(Y + dy))
    P = page[py:py + H, X + dx:X + dx + W].astype(np.uint8)
    if P.shape != F.shape or F.size == 0:
        continue
    g1, g2 = cv2.cvtColor(F, cv2.COLOR_RGB2GRAY), cv2.cvtColor(P, cv2.COLOR_RGB2GRAY)
    k1, d1 = sift.detectAndCompute(g1, None)
    k2, d2 = sift.detectAndCompute(g2, None)
    if d1 is None or d2 is None or len(k1) < 8 or len(k2) < 8:
        continue
    m = cv2.BFMatcher().knnMatch(d1, d2, k=2)
    good = [a for a, b in (mm for mm in m if len(mm) == 2) if a.distance < 0.7 * b.distance]
    if len(good) < 8:
        continue
    A, inl = cv2.estimateAffinePartial2D(np.float32([k1[g.queryIdx].pt for g in good]), np.float32([k2[g.trainIdx].pt for g in good]), method=cv2.RANSAC, ransacReprojThreshold=3)
    if A is None:
        continue
    sc = math.hypot(A[0, 0], A[1, 0])
    rot = math.degrees(math.atan2(A[1, 0], A[0, 0]))
    cx, cy = W / 2, H / 2
    mx = A[0, 0] * cx + A[0, 1] * cy + A[0, 2] - cx
    my = A[1, 0] * cx + A[1, 1] * cy + A[1, 2] - cy
    flag = "ok " if abs(sc - 1) <= 0.01 and abs(rot) <= 0.3 and abs(mx) <= 3 and abs(my) <= 3 else "BAD"
    geo.append(f"{flag} {nid:7} {name[:22]:22} {W}x{H}  scale {sc:.4f}  rot {rot:+.2f}deg  shift {mx:+.1f},{my:+.1f}px  ({int(inl.sum())}/{len(good)} inliers)")

txt = "PIXEL DIFF (mean abs 0-255 per section)\n" + "\n".join(report) + "\n\nIMAGE GEOMETRY (SIFT, page vs Figma)\n" + "\n".join(geo)
(ROOT / "qa/pixeldiff.txt").write_text(txt + "\n", encoding="utf8")
print(txt)
bad = sum(1 for g in geo if g.startswith("BAD"))
print(f"\n{len(report)} sections diffed, {len(geo)} image boxes measured, {bad} outside scale 1% / rot 0.3deg / shift 3px")
