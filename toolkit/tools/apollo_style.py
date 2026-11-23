"""Apollo CMS rules for the paste file and the upload images.

1. Paste-file STRUCTURE (user, 2026-11-20: "from now on when building a website under the cms of apollo this is how the
   code structure must be", reference = Volvo Cars of Queens "Research Hub"). One file, in this order:
     a. <script> const css = `...readable CSS...`; -> a <style> element added to <head>. Fonts come in as @import at the
        top of the CSS (no <link> tags). No bare <style> anywhere.
     b. the page markup, its outer wrapper carrying the class "main-div" (the CMS fixes below skip anything inside it).
     c. <script> holding the page's own JS, then the Apollo CMS fixes (APOLLO_FIX): drop the CMS's own H1, force the
        CMS wrappers full-bleed, hide the smart-search dropdown at <=1200px, demote the CMS header h2 / overlay h2 /
        h5-h6 widgets - re-run on DOMContentLoaded, load and DOM changes.
2. JPEG images (user, 2026-11-20: "New rule for Apollo CMS the images must be in jpeg format"): every image uploaded to
   Apollo is a .jpg, and the paste file points to the .jpg names (no .webp / .png left).
   JPEG has no transparency: a transparent image is flattened onto the colour behind it on the page. Give that colour in
   project.json "jpeg_bg": {"<file name>": "#rrggbb"} (or "*" for all); without it, white is used and a WARNING is printed.

    python -I apollo_style.py <file.html> [...]       -> Apollo structure + .webp/.png -> .jpg in each file, in place
    python -I apollo_style.py --check <file.html>     -> exit 1 if the structure is wrong or a .webp/.png image is there
    python -I apollo_style.py --jpeg <project folder> -> assets/jpg/*.jpg from assets/webp/*.webp (same names, .jpg)

From Python: wrap(html), structure_problems(html), has_bare_style(html), jpeg_html(html), non_jpeg_refs(html),
jpeg_name(name), to_jpeg(src, dst, bg) -> warning or None, jpeg_bg(project_folder) -> {name: (r, g, b)}.
"""
import json
import re
import sys
from pathlib import Path

STYLE = re.compile(r"<style[^>]*>(.*?)</style>", re.S | re.I)
SCRIPT = re.compile(r"<script>(.*?)</script>", re.S | re.I)
LINK = re.compile(r"<link\b[^>]*>\n?", re.I)
IMG_EXT = re.compile(r"\.(webp|png)\b", re.I)
JPEG_QUALITY = 90
CSS_HEAD = "    const css = `"

# The Apollo CMS fixes from the user's reference page, run after the page's own JS.
APOLLO_FIX = r"""(function () {
    /* ---- Apollo CMS fixes (user's reference structure, 2026-11-20). Each step only touches CMS chrome outside .main-div and is idempotent. */

    /* 1. Drop the CMS's own <h1>: the page supplies its own H1, two H1s would ship otherwise. */
    function dropCmsH1() {
        var nodes = document.querySelectorAll('body .CE.heading-h1, body .heading-h1');
        for (var i = 0; i < nodes.length; i++) {
            var el = nodes[i];
            if (el.closest && el.closest('.main-div')) continue;
            if (el.parentNode) el.parentNode.removeChild(el);
        }
    }

    /* 2. Force the CMS wrappers full-bleed: an inline !important outranks the CMS's own stylesheet. */
    var FORCE = [
        ['#content',                           {'max-width': '100%', 'width': '100%', 'padding': '0'}],
        ['#content .region, .default_padding', {'padding': '0'}],
        ['.mw_full',                           {'width': '100%'}]
    ];

    function forceWrappers() {
        for (var i = 0; i < FORCE.length; i++) {
            var sel = FORCE[i][0], props = FORCE[i][1];
            var nodes = document.querySelectorAll(sel);
            for (var j = 0; j < nodes.length; j++) {
                for (var p in props) {
                    if (props.hasOwnProperty(p)) {
                        nodes[j].style.setProperty(p, props[p], 'important');
                    }
                }
            }
        }
    }

    /* 3. Hide the CMS smart-search dropdown on tablet/mobile, re-checked whenever the viewport crosses 1200px. */
    var SEARCH_SEL = '#header_smart_search_dropdown.closed, .header_smart_search_dropdown';
    var tabletDown = window.matchMedia('(max-width: 1200px)');

    function toggleSearch() {
        var nodes = document.querySelectorAll(SEARCH_SEL);
        for (var i = 0; i < nodes.length; i++) {
            if (tabletDown.matches) {
                nodes[i].style.setProperty('display', 'none', 'important');
            } else {
                nodes[i].style.removeProperty('display');
            }
        }
    }

    if (tabletDown.addEventListener) {
        tabletDown.addEventListener('change', toggleSearch);
    } else if (tabletDown.addListener) {
        tabletDown.addListener(toggleSearch);   /* Safari < 14 */
    }

    /* 4-6. Swap CMS chrome headings for a plain tag (same attributes and children) so they leave the heading outline. */
    function swapTag(selector, tag) {
        var nodes = document.querySelectorAll(selector);
        for (var i = 0; i < nodes.length; i++) {
            var el = nodes[i];
            if (el.closest && el.closest('.main-div')) continue;
            var n = document.createElement(tag);
            for (var a = 0; a < el.attributes.length; a++) {
                n.setAttribute(el.attributes[a].name, el.attributes[a].value);
            }
            while (el.firstChild) n.appendChild(el.firstChild);
            if (el.parentNode) el.parentNode.replaceChild(n, el);
        }
    }

    function demoteCmsHeadings() {
        swapTag('h2.header_logo_content', 'div');            /* header logo: an <h2> holding only an <img> */
        swapTag('h2#searchOverlay__overlayHeading', 'p');    /* search overlay title */
        swapTag('h5, h6', 'div');                            /* hours / holiday hover widgets; pages use h1-h4 only */
    }

    function apply() { dropCmsH1(); forceWrappers(); toggleSearch(); demoteCmsHeadings(); }

    /* Run now for markup already parsed, then again as the CMS finishes. */
    apply();
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', apply);
    }
    window.addEventListener('load', apply);

    /* The CMS header widgets can render (or re-render) after load, so re-run on DOM changes. */
    if (window.MutationObserver) {
        var mo = new MutationObserver(function () { apply(); });
        mo.observe(document.documentElement, { childList: true, subtree: true });
    }
})();"""


def _pretty_css(css):
    """One rule per line, so the CSS reads as CSS inside the script."""
    css = css.strip("\n")
    if css.count("\n") > 5:          # already laid out - keep it
        return "\n".join(l.rstrip() for l in css.split("\n"))
    out, depth, buf = [], 0, ""
    for ch in css:
        buf += ch
        if ch == "{":
            depth += 1
            if depth > 1 or buf.lstrip().startswith("@"):
                out.append("  " * (depth - 1) + buf.strip()); buf = ""
        elif ch == "}":
            depth -= 1
            out.append("  " * depth + buf.strip()); buf = ""
    if buf.strip():
        out.append(buf.strip())
    return "\n".join(l for l in out if l)


def _font_imports(links):
    out = []
    for l in links:
        if re.search(r'rel=["\']?stylesheet', l, re.I):
            m = re.search(r'href=["\']([^"\']+)["\']', l)
            if m:
                out.append('@import url("%s");' % m.group(1).replace("&amp;", "&"))
    return out


def _add_main_div(markup):
    """Give the outer wrapper (the first element) the class main-div."""
    m = re.search(r"<(div|section|main|article)\b([^>]*)>", markup)
    if not m:
        return '<div class="main-div">\n' + markup + "\n</div>"
    attrs = m.group(2)
    if re.search(r'class="[^"]*\bmain-div\b', attrs):
        return markup
    if 'class="' in attrs:
        attrs = attrs.replace('class="', 'class="main-div ', 1)
    else:
        attrs = ' class="main-div"' + attrs
    return markup[:m.start()] + "<%s%s>" % (m.group(1), attrs) + markup[m.end():]


def wrap(html):
    """A one-file page (font <link> + <style> + markup + <script>) -> the Apollo structure. Already-converted -> as is."""
    if CSS_HEAD in html and not STYLE.search(html):
        return html
    links = LINK.findall(html)
    css = "\n".join(m.group(1) for m in STYLE.finditer(html))
    js = [m.group(1).strip("\n") for m in SCRIPT.finditer(html) if m.group(1).strip()]
    markup = SCRIPT.sub("", STYLE.sub("", LINK.sub("", html)))
    markup = re.sub(r"\n{2,}", "\n", markup).strip("\n")
    head = _font_imports(links)
    body = "\n".join(head + [_pretty_css(css)])
    body = body.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${").replace("</", "<\\/")
    body = "\n".join(("      " + l) if l else l for l in body.split("\n"))
    top = ("<script>\n" + CSS_HEAD + "\n" + body + "\n    `;\n"
           "    const style = document.createElement('style');\n"
           "    style.type = 'text/css';\n"
           "    style.appendChild(document.createTextNode(css));\n"
           "    document.head.appendChild(style);\n</script>")
    bottom = "<script>\n" + "\n\n".join(js + [APOLLO_FIX]) + "\n</script>"
    return top + "\n" + _add_main_div(markup) + "\n" + bottom


def structure_problems(html):
    """What is not in the Apollo structure (empty list = ok)."""
    p = []
    t = html.strip()
    if STYLE.search(html):
        p.append("bare <style> (the CSS goes in the top <script> as const css)")
    if not t.startswith("<script>\n" + CSS_HEAD):
        p.append("does not start with the <script> const css = `...`")
    if LINK.search(html):
        p.append("<link> tag left (fonts go in the CSS as @import)")
    if not re.search(r'class="[^"]*\bmain-div\b', html):
        p.append("no main-div wrapper")
    if "function dropCmsH1()" not in html or "MutationObserver" not in html:
        p.append("Apollo CMS fixes missing from the last <script>")
    if not t.endswith("</script>"):
        p.append("does not end with the <script>")
    return p


def has_bare_style(html):
    # the CSS sits in a JS template literal with "</" escaped, so a real <style> tag never appears in a converted page
    return bool(STYLE.search(html))


# ---------------------------------------------------------------- JPEG images
def jpeg_name(name):
    return IMG_EXT.sub(".jpg", name)


def jpeg_html(html):
    """Every image file name / link in the page -> .jpg (src, srcset, CSS url(), IMAGE-LINK placeholders)."""
    html = re.sub(r'type=(["\'])image/(webp|png)\1', r'type=\1image/jpeg\1', html, flags=re.I)
    return re.sub(r"([\w%-])\.(webp|png)\b", r"\1.jpg", html, flags=re.I)


def non_jpeg_refs(html):
    return sorted(set(m.group(0) for m in re.finditer(r"[\w%./-]+\.(webp|png)\b", html, re.I)))


def _rgb(v):
    if isinstance(v, (list, tuple)):
        return tuple(int(x) for x in v[:3])
    v = str(v).lstrip("#")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def jpeg_bg(proj):
    try:
        pj = json.loads((Path(proj) / "project.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: _rgb(v) for k, v in (pj.get("jpeg_bg") or {}).items()}


def to_jpeg(src, dst, bg=None):
    """Save src as a JPEG (quality 90, 4:4:4, progressive). Returns a warning text when a transparent image had to be
    flattened onto white because no background colour was given."""
    from PIL import Image
    im = Image.open(src)
    warn = None
    if im.mode in ("RGBA", "LA", "P") and (im.mode != "P" or "transparency" in im.info):
        rgba = im.convert("RGBA")
        if rgba.getchannel("A").getextrema()[0] < 255:
            if bg is None:
                warn = f"{Path(src).name} is transparent - flattened onto WHITE; set project.json jpeg_bg for it"
            base = Image.new("RGBA", rgba.size, tuple(bg or (255, 255, 255)) + (255,))
            base.alpha_composite(rgba)
            im = base
    im = im.convert("RGB")
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, "JPEG", quality=JPEG_QUALITY, subsampling=0, optimize=True, progressive=True)
    return warn


def jpeg_folder(proj):
    proj = Path(proj)
    bgs = jpeg_bg(proj)
    out = []
    for f in sorted((proj / "assets" / "webp").glob("*.*")):
        if f.suffix.lower() in (".webp", ".png", ".jpg", ".jpeg"):
            w = to_jpeg(f, proj / "assets" / "jpg" / jpeg_name(f.name), bgs.get(f.name, bgs.get("*")))
            out.append((f.name, w))
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--jpeg"]:
        for p in args[1:]:
            for name, w in jpeg_folder(p):
                print(("WARNING " + w) if w else ("jpg: " + jpeg_name(name)))
        sys.exit(0)
    check = args[:1] == ["--check"]
    bad = 0
    for p in (args[1:] if check else args):
        f = Path(p)
        t = f.read_text(encoding="utf-8")
        if check:
            for prob in structure_problems(t):
                print("APOLLO STRUCTURE:", prob, "-", f)
                bad += 1
            refs = non_jpeg_refs(t)
            if refs:
                print("NOT JPEG (Apollo images must be .jpg):", f, refs[:5])
                bad += 1
        else:
            n = wrap(jpeg_html(t))
            if n != t:
                f.write_text(n, encoding="utf-8")
            print(("updated" if n != t else "already ok") + ":", f)
    sys.exit(1 if bad else 0)
