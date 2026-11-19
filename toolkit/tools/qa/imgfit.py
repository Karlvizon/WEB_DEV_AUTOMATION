"""Check an image box against the Figma render with SIFT: render the source with the
Figma crop (w,h,l,t in % of the box), then estimate scale/rotation/shift between that
and the same box in the Figma screenshot.
Usage: python -I imgfit.py figma.png bx by bw bh source.png w h l t"""
import sys, math
import cv2, numpy as np
from PIL import Image
fig, bx, by, bw, bh, src, w, h, l, t = sys.argv[1:11]
bx, by, bw, bh = map(float, (bx, by, bw, bh)); w, h, l, t = map(float, (w, h, l, t))
F = np.array(Image.open(fig).convert("RGB"))[int(by):int(by + bh), int(bx):int(bx + bw)]
S = Image.open(src).convert("RGB")
iw, ih = round(bw * w / 100), round(bh * h / 100)
S = S.resize((iw, ih), Image.LANCZOS)
canvas = Image.new("RGB", (int(bw), int(bh)), (0, 0, 0))
canvas.paste(S, (round(bw * l / 100), round(bh * t / 100)))
R = np.array(canvas)
sift = cv2.SIFT_create(4000)
g1, g2 = cv2.cvtColor(R, cv2.COLOR_RGB2GRAY), cv2.cvtColor(F, cv2.COLOR_RGB2GRAY)
k1, d1 = sift.detectAndCompute(g1, None); k2, d2 = sift.detectAndCompute(g2, None)
m = cv2.BFMatcher().knnMatch(d1, d2, k=2)
good = [a for a, b in m if a.distance < 0.7 * b.distance]
p1 = np.float32([k1[a.queryIdx].pt for a in good]); p2 = np.float32([k2[a.trainIdx].pt for a in good])
M, inl = cv2.estimateAffinePartial2D(p1, p2, method=cv2.RANSAC, ransacReprojThreshold=2)
s = math.hypot(M[0, 0], M[1, 0]); rot = math.degrees(math.atan2(M[1, 0], M[0, 0]))
print(f"matches {len(good)} inliers {int(inl.sum())} scale {s:.4f} rot {rot:.3f}deg shift ({M[0,2]:.1f},{M[1,2]:.1f})")
