"""Build qa/index.html: QA summary, raw results, Figma vs page section pairs, device-matrix thumbnails."""
import json, html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PROJ = json.loads((ROOT / "project.json").read_text(encoding="utf8"))
Q = ROOT / "qa"


def txt(name):
    p = Q / name
    return html.escape(p.read_text(encoding="utf-8", errors="replace")) if p.exists() else "(not run)"


def last(name):
    t = txt(name).strip().splitlines()
    return t[-1] if t else "(empty)"


def count(name, prefix):
    return sum(1 for l in txt(name).splitlines() if l.startswith(prefix))


SUMMARY = [
    ("Text positions vs Figma (true 1920 viewport)", last("textpos.txt")),
    ("Pixel diff + image geometry (SIFT)", last("pixeldiff.txt")),
    ("Computed styles vs Figma", last("stylecheck.txt") + " &middot; planted run: " + last("stylecheck-plant.txt")),
    ("Desktop vertical gaps (1920)", "largest visible gap " + str(max([int(l.split()[0]) for l in txt("gaps-desk.txt").splitlines() if l.strip()[:1].isdigit()] or [0])) + " px"),
    ("Resize sweep 320&ndash;3840", last("sweep.txt")),
    ("Zoom (1920/1440/1366 screens, 25&ndash;200%)", f"{count('zoom.txt', 'ok')} of {len(txt('zoom.txt').splitlines())} ok"),
    ("Mobile buttons (90px header + 60px bottom bar)", f"{sum(1 for l in txt('mobile.txt').splitlines() if 'all 13 buttons fully visible' in l)} of 7 viewports pass"),
    ("Mobile images", f"{sum(1 for l in txt('mobile-images.txt').splitlines() if 'all content images whole' in l)} of 5 widths pass"),
    ("Carousel and interactions", last("interact.txt")),
    ("Carousel mouse drag / click", f"{sum(1 for l in txt('cdrag.txt').splitlines() if ' ok' in l)} ok lines"),
    ("CMS placements", f"{sum(1 for l in txt('cmsplace.txt').splitlines() if ' 0 differ' in l)} of 12 placements identical to preview"),
    ("CMS lint", txt("cmslint.txt").strip() + " &middot; " + last("lintplant.txt")),
    ("Live theme injection (dealer site page, new page not published yet)",
     "<br>".join(l[:260] for l in txt("livesim.txt").splitlines() if l[:1].isdigit())),
]
rows = "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in SUMMARY)
pairs = "".join(f"<figure><a href='visual-diff/{p.name}'><img src='visual-diff/{p.name}' loading='lazy' alt='{p.stem}'></a><figcaption>Figma node {p.stem.replace('-', ':')} (left Figma, right page)</figcaption></figure>"
                for p in sorted((Q / "visual-diff").glob("*.png")))
shots = sorted((Q / "screens").glob("device-*.jpg"), key=lambda p: -int(p.stem.split("-")[1].split("x")[0]))
gallery = "".join(f"<figure class='dev'><a href='screens/{p.name}'><img src='screens/{p.name}' loading='lazy' alt='{p.stem}'></a><figcaption>{p.stem.replace('device-', '')}</figcaption></figure>" for p in shots)
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{PROJ["title"]} {PROJ["dealer"]} QA</title>
<style>
body{{margin:0;padding:24px 16px 64px;font:15px/1.5 "Segoe UI",Roboto,Arial,sans-serif;color:#1d2430;background:#f6f7f9}}
main{{max-width:1200px;margin:0 auto}} h1{{font-size:26px;margin:0 0 4px}} h2{{font-size:19px;margin:36px 0 10px;border-bottom:2px solid #006;padding-bottom:4px}}
table{{border-collapse:collapse;width:100%;background:#fff}} td{{border:1px solid #dde1e7;padding:6px 10px;vertical-align:top}} td:first-child{{width:32%;font-weight:600}}
pre{{background:#fff;border:1px solid #dde1e7;padding:10px;overflow:auto;max-height:420px;font-size:12px}}
.grid{{display:flex;flex-wrap:wrap;gap:14px}} figure{{margin:0;background:#fff;border:1px solid #dde1e7;padding:6px}} figure img{{display:block;max-width:100%}}
.pairs figure{{width:100%}} .dev{{width:180px}} .dev img{{width:100%;height:420px;object-fit:cover;object-position:top}} figcaption{{font-size:12px;color:#555;margin-top:4px}}
</style></head><body><main>
<h1>{PROJ["title"]} &mdash; {PROJ["dealer"]}, {PROJ["location"]} &mdash; QA</h1>
<p>Figma {PROJ["figma"]["file"]} (frame {PROJ["figma"]["frame"]}). Source: preview.html; deliverable: cms-fields/.</p>
<h2>Summary</h2><table>{rows}</table>
<h2>Device matrix (full-page, scaled)</h2><div class="grid">{gallery}</div>
<h2>Figma vs page, per section (1920)</h2><div class="grid pairs">{pairs}</div>
<h2>Pixel diff and image geometry</h2><pre>{txt('pixeldiff.txt')}</pre>
<h2>Text positions</h2><pre>{txt('textpos.txt')}</pre>
<h2>Computed styles</h2><pre>{txt('stylecheck.txt')}</pre>
<h2>Desktop gaps</h2><pre>{txt('gaps-desk.txt')}</pre>
<h2>Zoom</h2><pre>{txt('zoom.txt')}</pre>
<h2>Mobile buttons and spacing</h2><pre>{txt('mobile.txt')}</pre>
<h2>Mobile images</h2><pre>{txt('mobile-images.txt')}</pre>
<h2>Interactions</h2><pre>{txt('interact.txt')}</pre><pre>{txt('cdrag.txt')}</pre>
<h2>CMS placements</h2><pre>{txt('cmsplace.txt')}</pre>
<h2>Live theme injection</h2><pre>{txt('livesim.txt')}</pre>
<h2>Resize sweep</h2><pre>{txt('sweep.txt')}</pre>
</main></body></html>
"""
(Q / "index.html").write_text(page, encoding="utf-8")
print("wrote", Q / "index.html")
