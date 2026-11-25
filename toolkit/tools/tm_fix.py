"""Trademark symbols the size of the live Mercedes-Benz of Alexandria GLS page (user, 2026-11-25: "gets the size of the
trademark symbol here and implement it to our pages that has trademark symbol and use it for the future pages").

GLS standard (measured on https://www.mercedesalexandria.com/2027-mercedes-benz-gls-suv-alexandria/): the drawn (R) is about
HALF the text size wide (11.9px on 24px text, 7.9px on 16px, 18.7px on 40px headings). Brand fonts like MB Corpo already draw a
small raised (R) at full text size - there the symbol keeps the text's own font and size. Fonts that draw a big (R) (Arial,
Roboto, Helvetica, Honda/Subaru/Hyundai fonts...) get font-size 0.5/ratio em + vertical-align super.

What it does for one page folder:
  1. wraps every bare (R)/TM in the HTML text (cms-fields/*.html + preview.html) in <span class="<P>-r"> (a <sup>(R)</sup> too)
  2. measures the page font's (R) at 1em (tools/qa/tm_measure.js) and works out the rule
  3. writes the rule into EVERY copy: cms-fields *.css, the <style> inside the cms-fields HTML (DI pages carry a CSS copy in
     the HTML field - 2026-11-25 a CSS-only fix never reached the live page because of it), preview.html, tools/page.css
Usage: python -I tm_fix.py "<project folder>" [--dry]
Notes: text built by tools/gen.py is not re-wrapped there - the tracker note says so. qa_sweep.js checks the result.
"""
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYM = {"®": "&reg;", "&reg;": "&reg;", "&#174;": "&reg;", "™": "&trade;", "&trade;": "&trade;", "&#8482;": "&trade;"}
SYM_RE = re.compile(r"®|&reg;|&#174;|™|&trade;|&#8482;")


def prefix_of(proj):
    m = re.search(r'class="([a-z0-9]+)-wrap\b', (proj / "preview.html").read_text(encoding="utf-8", errors="replace"))
    return m.group(1) if m else None


def wrap_html(text, P):
    """Wrap bare symbols in text (not in tags, <script>, <style>, <head>, <title>, <textarea>). Returns (text, count)."""
    span = f'<span class="{P}-r">'
    text, n0 = re.subn(r"<sup>\s*(®|&reg;|&#174;|™|&trade;|&#8482;)\s*</sup>", lambda m: f"{span}{SYM[m.group(1)]}</span>", text)
    out, skip, n = [], None, n0
    parts = re.split(r"(<[^>]+>)", text)
    for k, t in enumerate(parts):
        if t.startswith("<"):
            low = t.lower()
            m = re.match(r"<\s*(script|style|head|title|textarea)\b", low)
            if m and not skip:
                skip = m.group(1)
            elif skip and re.match(rf"<\s*/\s*{skip}\b", low):
                skip = None
            out.append(t)
            continue
        if skip or not SYM_RE.search(t):
            out.append(t)
            continue
        prev = parts[k - 1] if k else ""
        if prev == span and SYM_RE.fullmatch(t.strip() or "x"):   # already <span class="P-r">(R)</span>
            out.append(t)
            continue
        t2, c = SYM_RE.subn(lambda m: f"{span}{SYM[m.group(0)]}</span>", t)
        out.append(t2)
        n += c
    return "".join(out), n


def rule_body(r1):
    base = "display:inline !important;font-family:inherit !important;font-weight:inherit !important;color:inherit !important;letter-spacing:inherit !important;"
    if r1 is None or r1 <= 0.6:   # the font draws a small raised (R) itself (MB Corpo: 0.47-0.50) -> same size as the text
        return base + "font-size:1em !important;line-height:inherit !important;vertical-align:baseline !important;"
    em = round(0.5 / r1, 2)       # big (R) glyph -> shrink to half the text width and raise it
    return base + f"font-size:{em}em !important;line-height:0 !important;vertical-align:super !important;"


def set_rule(text, P, sel, body, is_css):
    """Replace the body of every .P-r rule; add one when the CSS has none. Returns (text, how)."""
    pat = re.compile(r"([^{}]*?(?:span)?\." + re.escape(P) + r"-r\s*)\{[^}]*\}")
    if pat.search(text):
        return pat.sub(lambda m: m.group(1) + "{" + body + "}", text), "replaced"
    rule = f"{sel}{{{body}}}"
    if is_css:
        return text.rstrip() + "\n/* (R)/TM like the live Mercedes-Benz of Alexandria GLS page (tm_fix.py 2026-11-25) */\n" + rule + "\n", "added"
    if "</style>" in text:
        i = text.index("</style>")
        return text[:i] + rule + "\n" + text[i:], "added"
    m = re.search(r"const css\s*=\s*`", text)   # Apollo one-file pages: CSS inside a <script> template string
    if m:
        j = text.index("`", m.end())
        return text[:j] + "\n" + rule + "\n" + text[j:], "added"
    return text, "no css"


def main():
    proj = Path(sys.argv[1]).resolve()
    dry = "--dry" in sys.argv
    P = prefix_of(proj)
    if not P:
        sys.exit("SKIP no <prefix>-wrap in preview.html")
    files = sorted((proj / "cms-fields").glob("*.html")) + [proj / "preview.html"]
    css_files = sorted((proj / "cms-fields").glob("*.css")) + ([proj / "tools" / "page.css"] if (proj / "tools" / "page.css").exists() else [])
    bk = proj / "qa" / f"backup-before-tm-fix-{time.strftime('%Y%m%d-%H%M')}"
    report = []
    new = {}
    for f in files:
        t, n = wrap_html(f.read_text(encoding="utf-8"), P)
        new[f] = t
        report.append(f"{f.name}: wrapped {n}")
    if not dry:
        bk.mkdir(parents=True, exist_ok=True)
        for f in files + css_files:
            shutil.copy2(f, bk / (f.parent.name + "__" + f.name))
        for f, t in new.items():
            f.write_text(t, encoding="utf-8", newline="\n")
    r = subprocess.run(["node", str(HERE / "qa" / "tm_measure.js"), str(proj), P], capture_output=True, text=True, encoding="utf-8", timeout=180)
    try:
        m = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        sys.exit("measure failed: " + (r.stderr or r.stdout)[-300:])
    r1 = m.get("all")
    if m.get("r1") and len(m["r1"]) > 1:   # several fonts: use the body font (most symbols)
        report.append("fonts: " + ", ".join(f"{k} {v}" for k, v in m["r1"].items()))
    body = rule_body(r1)
    sel = f"#{m['id']} .{P}-wrap .{P}-r" if m.get("id") else f".{P}-wrap .{P}-wrap .{P}-r"
    for f in files + css_files:
        t = new.get(f) if dry and f in new else f.read_text(encoding="utf-8")
        t2, how = set_rule(t, P, sel, body, f.suffix == ".css")
        if f.name.endswith(".html") and how == "no css":
            continue   # an HTML field without any CSS in it
        if not dry and t2 != t:
            f.write_text(t2, encoding="utf-8", newline="\n")
        report.append(f"{f.name}: rule {how}")
    print(f"OK  {proj.name}: prefix {P}, {m.get('n')} (R) measured, font (R) at 1em = {r1} -> "
          + (f"font-size {round(0.5 / r1, 2)}em + super" if r1 and r1 > 0.6 else "same font + size as the text (GLS)"))
    print("    " + " | ".join(report))
    if not dry:
        print("    backup: " + str(bk))


if __name__ == "__main__":
    main()
