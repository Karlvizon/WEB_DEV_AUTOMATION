"""Write figma/texts.json: every visible Figma text node of frame 1:2 (2027 Jeep Gladiator)
with absolute x/y/w/h in the 1920-wide frame, plus "g" = the sub-section it belongs to
(top-level section, or the sub-frame inside Capability / Design / Technology / Trim),
so the text-position check can separate deliberate spacing changes from real errors."""
import re, json, html
from pathlib import Path
root = Path(__file__).resolve().parent.parent

PROJ = json.loads((root / "project.json").read_text(encoding="utf-8"))
FRAME = PROJ["figma"]["frame"]
CATS = set(PROJ["figma"].get("groups", []))
xml = (root / "figma" / ("meta-" + FRAME.replace(":", "-") + ".xml")).read_text(encoding="utf-8")
stack = [(0.0, 0.0, False, None, None)]
texts, out = [], []
for m in re.finditer(r'<(/?)(\w[\w-]*)([^>]*?)(/?)>', xml):
    close, tag, attrs, selfc = m.groups()
    if close:
        stack.pop(); continue
    a = dict(re.findall(r'([\w-]+)="([^"]*)"', attrs))
    px, py, phid, pg, pid = stack[-1]
    nid = a.get("id")
    if nid == FRAME:
        x = y = 0.0
    else:
        x, y = px + float(a.get("x", 0)), py + float(a.get("y", 0))
    hid = phid or a.get("hidden") == "true"
    depth = len(stack) - 1
    g = pg
    if depth == 2:
        g = nid
    if depth == 3 and pid in CATS:
        g = nid
    if not hid:
        out.append(f'{depth:2} {nid:8} {tag[:4]} x{x:7.1f} y{y:8.1f} w{float(a.get("width",0)):7.1f} h{float(a.get("height",0)):7.1f}  {a.get("name","")[:50]}')
        if tag == "text":
            texts.append({"id": nid, "g": g or nid, "x": x, "y": y, "w": float(a["width"]), "h": float(a["height"]), "name": html.unescape(a["name"])})
    if not selfc:
        stack.append((x, y, hid, g, nid))
(root / "figma/abs.txt").write_text("\n".join(out), encoding="utf-8")
(root / "figma/texts.json").write_text(json.dumps(texts, indent=0), encoding="utf-8")
print(len(out), "nodes", len(texts), "texts", len({t["g"] for t in texts}), "groups")
