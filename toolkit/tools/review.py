"""Build review.html in the project folder: one page to review a finished MLP quickly
(user, 2026-11-12: "Review page for each project").

Usage: python tools/review.py            (run from the project folder, after the QA)

Shows: deliverables (CMS file(s), WebP count/size), Figma design and built page side by side (desktop) plus the
390px mobile page, every link on the page (flags off-site / missing ones), the tracker's Questions / Answers /
Revisions for this MLP, the pre-flight result, and the result line of every QA file in qa/.
Screenshots: qa/desk.png and qa/m390.png are reused when newer than preview.html, otherwise taken with
tools/qa/fullshot.js. Review images are written as JPEG to qa/review/.
"""
import html
import json
import re
import subprocess
import urllib.parse
from datetime import datetime
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ROOT = Path.cwd()
PROJ = json.loads((ROOT / "project.json").read_text(encoding="utf8"))
QA = ROOT / "qa"
OUT = QA / "review"
OUT.mkdir(parents=True, exist_ok=True)
TRACKER = (lambda _p: Path(_p.read_text(encoding="utf-8").strip()) if _p.exists() else Path(__file__).resolve().parents[2] / "tracker")((Path(__import__("os").environ["APPDATA"]) if __import__("sys").platform == "win32" else Path.home() / "Library" / "Application Support") / "MLP Tracker" / "tracker_path.txt") / "Final_MLP_Tracker.xlsx"
E = html.escape


def shot(width, name):
    png = QA / name
    prev = ROOT / "preview.html"
    if not png.exists() or png.stat().st_mtime < prev.stat().st_mtime:
        subprocess.run(["node", str(ROOT / "tools/qa/fullshot.js"), str(width), str(png)], check=True, cwd=ROOT)
    return png


def jpg(src, name, width):
    if not src or not Path(src).exists():
        return None
    im = Image.open(src).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(OUT / name, "JPEG", quality=82, optimize=True)
    return f"qa/review/{name}"


def kb(n):
    return f"{n / 1024:.0f} KB" if n < 1024 * 1024 else f"{n / 1048576:.1f} MB"


# deliverables
cms = sorted((ROOT / "cms-fields").glob("*")) if (ROOT / "cms-fields").exists() else []
webp = sorted((ROOT / "assets" / "webp").glob("*.webp")) if (ROOT / "assets" / "webp").exists() else []
deliv = "".join(f"<li><code>cms-fields/{E(f.name)}</code> ({kb(f.stat().st_size)})</li>" for f in cms)
deliv += f"<li><code>assets/webp/</code>: {len(webp)} images, {kb(sum(f.stat().st_size for f in webp))} in total</li>"

# screenshots
fig = jpg(ROOT / "tools/_work/figma/full.png", "figma.jpg", 960)
desk = jpg(shot(1920, "desk.png"), "page-1920.jpg", 960)
mob = jpg(shot(390, "m390.png"), "page-390.jpg", 390)

# links
site = (urllib.parse.urlsplit(PROJ.get("site") or "").hostname or "").removeprefix("www.")
main = next((f for f in cms if f.suffix == ".html"), ROOT / "preview.html")
src = main.read_text(encoding="utf8", errors="replace")
rows, seen = [], {}
for m in re.finditer(r'<a\b([^>]*)>(.*?)</a>', src, re.S | re.I):
    href = re.search(r'href="([^"]*)"', m.group(1))
    href = html.unescape(href.group(1)) if href else ""
    label = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(2))).strip()) or "(image/icon link)"
    is_btn = bool(re.search(r'class="[^"]*(btn|cta)', m.group(1), re.I))
    key = (label, href, is_btn)
    seen[key] = seen.get(key, 0) + 1
for (label, href, is_btn), n in seen.items():
    h = (urllib.parse.urlsplit(href).hostname or "").removeprefix("www.")
    if not href or href == "#" or "data-todo-link" in href:
        flag, cls = "MISSING", "bad"
    elif h and site and h != site and not h.endswith("." + site):
        flag, cls = (f"BUTTON to other site ({h})", "bad") if is_btn else (f"text link, other site ({h})", "muted")
    else:
        flag, cls = "dealer site", "ok"
    rows.append(f'<tr><td>{E(label)}</td><td class="n">{n}</td><td><a href="{E(href)}" target="_blank">{E(href)}</a></td>'
                f'<td class="{cls}">{flag}</td></tr>')

# tracker notes
notes = {}
try:
    from openpyxl import load_workbook
    ws = load_workbook(TRACKER, read_only=True)["MLPs"]
    head = [c.value for c in next(ws.iter_rows(min_row=4, max_row=4))]
    for r in ws.iter_rows(min_row=5, values_only=True):
        d = dict(zip(head, r))
        if str(d.get("Subitem ID")) == str(PROJ.get("monday_subitem")):
            notes = d
            break
except Exception as e:
    notes = {"Questions": f"(tracker not readable: {e})"}


def block(title, text, cls):
    if not text:
        return f'<div class="note"><h3>{title}</h3><p class="muted">None</p></div>'
    items = "".join(f"<li>{E(t)}</li>" for t in str(text).split("\n") if t.strip())
    return f'<div class="note {cls}"><h3>{title}</h3><ul>{items}</ul></div>'


# QA results
qa_rows = []
for f in sorted(QA.glob("*.txt")):
    t = f.read_text(encoding="utf8", errors="replace").strip()
    last = t.splitlines()[-1] if t else "(empty)"
    bad = re.search(r"\b(WRONG|FAIL|fault[s]? [1-9]|[1-9]\d* faults|error[s]? [1-9]|QUESTION)\b", t, re.I)
    qa_rows.append(f'<details><summary><b>{E(f.stem)}</b> <span class="{"warn" if bad else "ok"}">'
                   f'{"check" if bad else "ok"}</span> {E(last[:200])}</summary><pre>{E(t[:20000])}</pre></details>')

# "ready for review" note to paste on the Final MLP in monday (user, 2026-11-12). The user posts it; Claude never
# writes to monday. Addressed to whoever posted the brief (first build) or asked for the revision (revision).
# For a revision, Claude lists what it changed in qa/revision_done.txt (one line per change).
CC = "cc: @Jericho Gane @Quality Assurance Team"   # the team's usual cc line on ready-for-review posts
try:   # your own monday ID (Settings tab / first refresh) - your own posts are not "the author"
    OWNER_ID = str(json.loads((TRACKER.parent / "tracker_config.json").read_text(encoding="utf8")).get("owner_id") or "")
except Exception:
    OWNER_ID = ""
author, reviser = "Quality Assurance Team", None
try:
    raw = json.loads((TRACKER.parent / "updates_raw.json").read_text(encoding="utf8")).get(str(PROJ.get("monday_subitem")), {})
    raw = raw.get("Final MLP", {}).get("updates", []) if isinstance(raw, dict) else raw
    first = sorted((u for u in raw if str((u.get("creator") or {}).get("id")) != OWNER_ID), key=lambda u: u["created_at"])
    if first:
        author = first[0]["creator"]["name"]
except Exception:
    pass
revs = [t for t in str(notes.get("Revisions") or "").split("\n") if t.startswith("[")]
if revs:
    m = re.match(r"\[[^\]]*\]\s*(Final MLP|Final Mobile Check)\s*-\s*([^:]+):", revs[-1])
    if m:
        reviser = m.group(2).strip()
done_f = QA / "revision_done.txt"
done = [l.strip() for l in done_f.read_text(encoding="utf8").splitlines() if l.strip()] if done_f.exists() else []
live = notes.get("Live URL")
if reviser:
    body = (f"@{reviser} - The revisions for the {PROJ.get('title')} are done:\n\n"
            + ("\n".join(f"{n}. {t}" for n, t in enumerate(done, 1)) if done else "(list the changes)")
            + (f"\n\nPage: {live}" if live else "") + f"\n\nThis is ready for review. Thanks!\n\n{CC}")
else:
    body = (f"@{author} - The {PROJ.get('title')} Final MLP is ready for review. Thanks!"
            + (f"\n\nPage: {live}" if live else "") + f"\n\n{CC}")
(ROOT / "ready-for-review.txt").write_text(body, encoding="utf8")
note_html = (f'<h2>Ready-for-review note (paste it on the Final MLP in monday)</h2><div class="card">'
             f'<pre id="note">{E(body)}</pre><button type="button" onclick="navigator.clipboard.writeText('
             f'document.getElementById(\'note\').innerText);this.textContent=\'Copied\'">Copy</button></div>')

pane = lambda title, img: (f'<div class="pane"><h3>{title}</h3><div class="scroll">'
                           + (f'<img src="{img}" alt="{title}">' if img else '<p class="muted">not available</p>') + "</div></div>")
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Review - {E(PROJ.get('title', ''))}</title><style>
body{{margin:0;font:14px/1.45 Arial,sans-serif;background:#f4f5f7;color:#1d1d1f}} main{{max-width:1500px;margin:auto;padding:20px 16px 60px}}
h1{{margin:0 0 4px;font-size:24px}} h2{{margin:28px 0 10px;font-size:18px;border-bottom:2px solid #1f3864;padding-bottom:4px}}
.muted{{color:#777}} .card{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:14px 16px}}
.cmp{{display:grid;grid-template-columns:1fr 1fr 300px;gap:12px}} .pane h3{{margin:0 0 6px;font-size:14px}}
.scroll{{height:80vh;overflow:auto;background:#fff;border:1px solid #ccc}} .scroll img{{width:100%;display:block}}
table{{border-collapse:collapse;width:100%;background:#fff}} td,th{{border:1px solid #ddd;padding:5px 8px;text-align:left;vertical-align:top;word-break:break-all}}
th{{background:#1f3864;color:#fff}} td.n{{text-align:center}} .ok{{color:#2e7d32;font-weight:bold}} .warn{{color:#b26a00;font-weight:bold}} .bad{{color:#c62828;font-weight:bold}}
.notes{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}} .note{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:10px 14px}}
.note h3{{margin:0 0 6px;font-size:14px}} .note.q{{background:#fff8e1}} .note.a{{background:#eef7ea}} .note.r{{background:#fdecef}}
details{{background:#fff;border:1px solid #ddd;border-radius:6px;margin:6px 0;padding:6px 10px}} pre{{white-space:pre-wrap;font-size:12px;max-height:400px;overflow:auto}}
label{{font-size:13px}} @media(max-width:900px){{.cmp,.notes{{grid-template-columns:1fr}}}}
</style></head><body><main>
<h1>{E(PROJ.get('title', ''))} &middot; {E(PROJ.get('dealer', ''))}</h1>
<p class="muted">{E(PROJ.get('location', ''))} &middot; platform: {E(PROJ.get('platform', ''))} &middot; page id <code>{E(PROJ.get('id', ''))}</code>
 &middot; review built {datetime.now():%b %d, %Y %I:%M %p}</p>
{note_html}
<h2>Deliverables</h2><div class="card"><ul>{deliv}</ul></div>
<h2>Figma vs page</h2><p><label><input type="checkbox" id="sync" checked> Scroll the Figma and desktop panes together</label></p>
<div class="cmp">{pane('Figma (1920)', fig)}{pane('Page desktop (1920)', desk)}{pane('Page mobile (390)', mob)}</div>
<h2>Questions, answers and revisions</h2><div class="notes">{block('Questions', notes.get('Questions'), 'q')}
{block('Your answers', notes.get('Answers'), 'a')}{block('Revisions from monday', notes.get('Revisions'), 'r')}</div>
<h2>Links on the page ({len(rows)})</h2><table><tr><th>Button / link</th><th>Times</th><th>URL</th><th>Check</th></tr>{''.join(rows)}</table>
<h2>QA results</h2>{''.join(qa_rows) or '<p class="muted">No QA files yet.</p>'}
</main><script>
const panes=[...document.querySelectorAll('.scroll')].slice(0,2);let lock=false;
panes.forEach((p,i)=>p.addEventListener('scroll',()=>{{if(!document.getElementById('sync').checked||lock)return;lock=true;
const o=panes[1-i],f=p.scrollTop/Math.max(1,p.scrollHeight-p.clientHeight);o.scrollTop=f*(o.scrollHeight-o.clientHeight);
requestAnimationFrame(()=>lock=false);}}));
</script></body></html>"""
(ROOT / "review.html").write_text(page, encoding="utf8")
print("wrote", ROOT / "review.html", "| links", len(rows), "| qa files", len(qa_rows))
