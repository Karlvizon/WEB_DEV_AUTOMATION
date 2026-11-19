"""Split preview.html into the three CMS editor fields.

The CMS page editor has separate CSS, HTML and JS fields:

    cms-fields/{{NAME}}.html  wrapper + font <link> + <style> CSS + markup -> HTML field
    cms-fields/{{NAME}}.css   the same CSS, raw, no @import               -> CSS field
    cms-fields/{{NAME}}.js    raw JS, behaviour only                      -> JS field

The HTML field carries the CSS (user decision 2026-10-27: "lets proceed with the
html and css in one file for the cms fields"), because on Dealer Inspire sites the
Page Composer CSS field is never output (its slot stays empty on every page).
The CSS field keeps an identical copy because every field must have content;
identical rules cannot conflict.

Every CSS rule is scoped to the wrapper's unique id (#{{ID}}), so the
theme's CSS cannot restyle the page and the page's CSS cannot touch the site.

Local image paths (assets/webp/NAME) are rewritten to the Dealer Inspire media
library URL (CDN + NAME) in the exported fields; preview.html keeps the local
paths so it works offline.

preview.html is the only working file: a full document whose <body> holds only
the page wrapper. This tool reads that wrapper and never writes preview.html.
Re-run it after every edit.

Usage:  python tools/split_fields.py
"""

import json
import re
from pathlib import Path

LF = chr(10)
PROJ = json.loads((Path(__file__).resolve().parent.parent / "project.json").read_text(encoding="utf8"))
CDN = PROJ.get("cdn") or "assets/webp/"
ONEFILE = PROJ.get("platform") != "dealer-inspire"
LOCAL = "assets/webp/"
UNIQUE_ID = "#{{ID}}"


def cms_css(css: str) -> str:
    """CSS field version: the formatted CSS. No @import: security filters (OWASP
    941170) block "@import url(" on save, which leaves the CSS field empty. The
    Google Fonts stylesheet is a <link> tag at the top of the HTML field instead."""
    css = css.strip(LF)
    assert "@import" not in css, "no @import in the CSS field (fonts are a <link> in the HTML field)"
    assert UNIQUE_ID in css and ".main-div" not in css, "CSS must be scoped to the unique id"
    return css


def split(text: str) -> tuple[str, str, str]:
    """Return (css, html_field, js) from the combined single-file page."""
    s_open = text.index("<style>")
    s_close = text.index("</style>", s_open)
    j_open = text.index("<script>")
    j_close = text.index("</script>", j_open)

    css = text[s_open + len("<style>"):s_close].strip(LF)
    js = text[j_open + len("<script>"):j_close].strip(LF)
    # the HTML field: wrapper, font link, the <style> CSS block and the markup; only the script is left out
    html = (text[:j_open].rstrip(LF) + LF + text[j_close + len("</script>"):].lstrip(LF)).rstrip(LF)

    assert "<script" not in html, "the HTML field still carries a script block"
    css, html, js = (part.replace(LOCAL, CDN) for part in (css, html, js))
    css = cms_css(css)
    assert html.count("<style>") == 1 and css in html, "the HTML field must carry the CSS in exactly one <style> block"
    assert html.index("<style>") > html.index('id="{{ID}}"'), "the <style> block must sit inside the wrapper"
    assert "<script" not in js and "<style" not in css, "a field carries another field's tags"
    if PROJ.get("cdn"):
        assert LOCAL not in css + html + js, "a local image path survived the export"
    return css, html, js


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    src = root / "preview.html"
    out_dir = root / ("tools/_work/fields" if ONEFILE else "cms-fields")
    out_dir.mkdir(parents=True, exist_ok=True)

    raw = src.read_text(encoding="utf-8")
    nl = "\r\n" if "\r\n" in raw else LF
    doc = raw.replace("\r\n", LF)
    # the page is everything inside <body>; the <head> (viewport, reset) is preview-only
    body = doc[doc.index("<body>") + len("<body>"):doc.rindex("</body>")].strip(LF)
    assert body.startswith('<div class="main-div" id="{{ID}}">'), "body must hold only the page wrapper"
    css, html, js = split(body)

    for name, part in (("{{NAME}}.css", css), ("{{NAME}}.html", html),
                       ("{{NAME}}.js", js)):
        (out_dir / name).write_text((part + LF).replace(LF, nl), encoding="utf-8",
                                    newline="")
        lines = part.count(LF) + 1
        print(f"{name:15} {lines:5} lines  {len(part)/1024:7.1f} KB")

    if ONEFILE:
        one = root / "cms-fields"
        one.mkdir(exist_ok=True)
        page = body.replace(LOCAL, CDN) if PROJ.get("cdn") else body
        (one / "{{NAME}}.html").write_text((page + LF).replace(LF, nl), encoding="utf-8", newline="")
        print(f"one-file page: {one / '{{NAME}}.html'}  ({len(page)/1024:.1f} KB: wrapper + font link + <style> + markup + <script>)")
        print(f"(three-field copies for the lint/placement tests: {out_dir})")
    print(f"\nwritten to {out_dir} from {src.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
