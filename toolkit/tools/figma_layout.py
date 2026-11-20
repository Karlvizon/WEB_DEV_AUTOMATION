"""Save a page's Figma design measurements (user, 2026-11-20: "lets proceed with figma key").

Reads the page's Figma with the user's own Figma key (REST API, read-only, no Claude tokens) and saves
<project>/figma/layout.json: for the desktop frame (and the phone frame when the Figma has one) every text
with its box and the space above it (to the nearest thing above it that is not its own background).
qa_sweep.js compares those numbers with the built page ("CHECK spacing vs Figma").

usage:  python -I figma_layout.py "<project folder>" [figma link] [--force]
        python -I figma_layout.py --check            (is the key saved and accepted?)
Key:    environment variable FIGMA_TOKEN, or %APPDATA%\\MLP Tracker\\figma_token.txt (one line).
Link:   the link given, else project.json "figma" {file, frame}, else brief.json "figma", else figma/link.txt
        (the tracker copies it there from the monday update).
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def app_dir():
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", str(Path.home()))) / "MLP Tracker"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "MLP Tracker"
    return Path.home() / ".config" / "mlp-tracker"


def token():
    t = os.environ.get("FIGMA_TOKEN", "").strip()
    f = app_dir() / "figma_token.txt"
    if not t and f.exists():
        t = f.read_text(encoding="utf-8").strip()
    return t


def api(path):
    req = urllib.request.Request("https://api.figma.com/v1/" + path, headers={"X-Figma-Token": token()})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:          # Figma rate limit - wait and try again
                time.sleep(int(e.headers.get("Retry-After") or 20))
                continue
            if e.code in (401, 403):
                sys.exit("Figma refused the key (%d) - check it on the Settings tab." % e.code)
            if e.code == 404:
                sys.exit("Figma file not found (404) - the key's account may not have access to this Figma.")
            raise


def parse_link(u):
    """figma.com/design/KEY/name?node-id=1-559 (or /file/, /branch/BRANCHKEY/) -> (key, '1:559' or None)"""
    m = re.search(r"figma\.com/(?:design|file|proto)/([A-Za-z0-9]+)(?:/[^?#]*?/branch/([A-Za-z0-9]+))?", u or "")
    if not m:
        return None, None
    n = re.search(r"node-id=([0-9]+)[-:%3A]+([0-9]+)", u)
    return (m.group(2) or m.group(1)), (n.group(1) + ":" + n.group(2) if n else None)


def find_link(folder, given):
    if given:
        return parse_link(given)
    pj = folder / "project.json"
    if pj.exists():
        f = json.loads(pj.read_text(encoding="utf-8")).get("figma")
        if isinstance(f, dict) and f.get("file"):
            return f["file"], f.get("frame")
        if isinstance(f, str):
            return parse_link(f)
    bj = folder / "brief.json"
    if bj.exists():
        f = json.loads(bj.read_text(encoding="utf-8")).get("figma")
        if isinstance(f, dict):
            f = f.get("url") or f.get("link") or json.dumps(f)
        k = parse_link(f or "")
        if k[0]:
            return k
    lt = folder / "figma" / "link.txt"          # written by the tracker from the monday update (city pages, newer pages)
    if lt.exists():
        return parse_link(lt.read_text(encoding="utf-8").strip())
    return None, None


FRAMEISH = {"FRAME", "COMPONENT", "INSTANCE", "SECTION", "GROUP"}
SHAPES = {"RECTANGLE", "ELLIPSE", "VECTOR", "BOOLEAN_OPERATION", "STAR", "LINE", "POLYGON", "REGULAR_POLYGON"}


def visible_paint(paints):
    for p in paints or []:
        if p.get("visible") is False or p.get("opacity", 1) <= 0.02:
            continue
        if p.get("type") == "IMAGE" or str(p.get("type", "")).startswith("GRADIENT"):
            return True
        if p.get("type") == "SOLID":
            c = p.get("color", {})
            if c.get("a", 1) * p.get("opacity", 1) <= 0.02:
                continue
            if c.get("r", 0) > 0.99 and c.get("g", 0) > 0.99 and c.get("b", 0) > 0.99:
                continue                                   # white = page background (the page check skips white too)
            return True
    return False


def frame_layout(fr):
    ox, oy = fr["absoluteBoundingBox"]["x"], fr["absoluteBoundingBox"]["y"]
    W = fr["absoluteBoundingBox"]["width"]
    texts, boxes = [], []

    def walk(n, anc, clip):
        if n.get("visible") is False or n.get("opacity", 1) <= 0.02:
            return
        b = n.get("absoluteBoundingBox")
        if not b:
            return
        x, y, w, h = b["x"] - ox, b["y"] - oy, b["width"], b["height"]
        if clip:                                           # cut to the clipping parent (cropped photos)
            cx, cy, cw, ch = clip
            x2, y2 = min(x + w, cx + cw), min(y + h, cy + ch)
            x, y = max(x, cx), max(y, cy)
            w, h = x2 - x, y2 - y
            if w <= 1 or h <= 1:
                return
        box = (round(x, 1), round(y, 1), round(w, 1), round(h, 1))
        t = n.get("type")
        if t == "TEXT":
            s = re.sub(r"\s+", " ", n.get("characters", "")).strip()
            if s:
                texts.append({"t": s[:120], "box": box, "anc": anc, "id": n["id"], "size": (n.get("style") or {}).get("fontSize")})
                boxes.append((box, n["id"]))
            return
        if t in SHAPES and (visible_paint(n.get("fills")) or visible_paint(n.get("strokes"))):
            boxes.append((box, n["id"]))
        elif t in FRAMEISH and visible_paint(n.get("fills")):
            boxes.append((box, n["id"]))
        kids = n.get("children") or []
        nclip = box if n.get("clipsContent") else clip
        for k in kids:
            walk(k, anc + [n["id"]], nclip)

    for k in fr.get("children") or []:
        walk(k, [fr["id"]], (0, 0, W, fr["absoluteBoundingBox"]["height"]))
    # space above each text: nearest box above it that overlaps it sideways and is not one of its own backgrounds
    out = []
    for t in texts:
        x, y, w, h = t["box"]
        anc = set(t["anc"])
        best = None
        for (bx, by, bw, bh), bid in boxes:
            if bid == t["id"] or bid in anc:
                continue
            if by + bh > y + 2 or min(x + w, bx + bw) - max(x, bx) <= 0:
                continue
            if bx <= x and by <= y and bx + bw >= x + w and by + bh >= y + h:   # a box behind the text (not a parent in Figma)
                continue
            best = by + bh if best is None else max(best, by + bh)
        out.append({"t": t["t"], "x": x, "y": y, "w": w, "h": h, "size": t["size"],
                    "gap": None if best is None else round(y - best, 1)})
    return {"name": fr.get("name"), "id": fr["id"], "w": W, "h": fr["absoluteBoundingBox"]["height"], "texts": out}


def pick_frames(doc):
    if doc.get("type") in ("CANVAS", "DOCUMENT"):
        cands = []

        def gather(n, d):
            for k in n.get("children") or []:
                if k.get("visible") is False:
                    continue
                if k.get("type") in ("FRAME", "COMPONENT", "INSTANCE") and k.get("absoluteBoundingBox"):
                    cands.append(k)
                elif k.get("type") in ("SECTION", "CANVAS") and d < 3:
                    gather(k, d + 1)
        gather(doc, 0)
    else:
        cands = [doc]
    wb = lambda f: f["absoluteBoundingBox"]["width"]
    hb = lambda f: f["absoluteBoundingBox"]["height"]
    desk = [f for f in cands if wb(f) >= 1000]
    mob = [f for f in cands if 320 <= wb(f) <= 500 and hb(f) > 1500]
    return (max(desk, key=hb) if desk else None), (max(mob, key=hb) if mob else None)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--check" in sys.argv:
        if not token():
            sys.exit("No Figma key saved yet.")
        mark = app_dir() / "figma_refused.txt"     # the tracker shows a red "Figma key refused" line while this exists
        try:
            me = api("me")
        except SystemExit as e:
            if "refused" in str(e):
                mark.parent.mkdir(parents=True, exist_ok=True)
                mark.write_text(time.strftime("%Y-%m-%d %H:%M") + " " + str(e), encoding="utf-8")
            raise
        mark.unlink(missing_ok=True)
        print("Figma OK - connected as %s" % (me.get("handle") or "your account"))
        return
    if not args:
        sys.exit(__doc__)
    folder = Path(args[0])
    out = folder / "figma" / "layout.json"
    if out.exists() and "--force" not in sys.argv:
        print("SKIP figma/layout.json already saved (use --force to read the Figma again)")
        return
    if not token():
        sys.exit("SKIP no Figma key saved (Settings > Figma connection)")
    key, node = find_link(folder, args[1] if len(args) > 1 else None)
    if not key:
        sys.exit("SKIP no Figma link for this page (project.json / brief.json)")
    if not node:
        node = api("files/%s?depth=1" % key)["document"]["children"][0]["id"]   # first page of the file
    data = api("files/%s/nodes?ids=%s" % (key, urllib.parse.quote(node)))
    doc = (data.get("nodes", {}).get(node) or {}).get("document")
    if not doc:
        sys.exit("SKIP Figma node %s not found in the file" % node)
    if doc.get("type") not in ("CANVAS",) and (doc.get("absoluteBoundingBox") or {}).get("width", 0) < 1000:
        # a link to a small frame/section: read the whole page it sits on instead
        pg = api("files/%s?depth=1" % key)["document"]["children"]
        doc = (api("files/%s/nodes?ids=%s" % (key, urllib.parse.quote(pg[0]["id"]))).get("nodes", {}).get(pg[0]["id"]) or {}).get("document") or doc
    desk, mob = pick_frames(doc)
    if not desk:
        sys.exit("SKIP no desktop frame (1000px or wider) found in the Figma")
    res = {"source": {"file": key, "node": node, "lastModified": data.get("lastModified")},
           "saved": time.strftime("%Y-%m-%d %H:%M"), "desktop": frame_layout(desk)}
    if mob:
        res["mobile"] = frame_layout(mob)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("OK  saved figma/layout.json - desktop %s (%d texts)%s" % (
        res["desktop"]["name"], len(res["desktop"]["texts"]),
        (", phone %s (%d texts)" % (res["mobile"]["name"], len(res["mobile"]["texts"]))) if mob else ", no phone frame"))


if __name__ == "__main__":
    main()
