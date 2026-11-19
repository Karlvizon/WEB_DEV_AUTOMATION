"""SEO auto-fix (user, 2026-11-17: "every SEO revision that can be edited in HTML like the H1 revision. Can you fix
those through automation?").

Fixes only what can be changed in the HTML without changing how the page looks:
  1. ALL-CAPS headings -> Title Case in the HTML + class "seo-uc" with `text-transform: uppercase` in the page CSS
     (user rule 2026-11-14/17: normal text in the HTML, uppercase via CSS - screen readers, search results).
     Only headings typed fully in caps; acronyms/units/brand marks keep their caps (features._OK_CAPS).
  2. Missing space where two parts of a heading meet ("2027 GMC Terrain</span><span>Cherry Hill" -> "Terrain Cherry"),
     user rule 2026-11-13.
  3. Images with no alt attribute -> alt = the nearest heading above them.
Not automatic (copy or design decisions, stay as Check in the SEO review tab): meta title/description length, vague
link text, heading level jumps, more than one H1, headings only partly in caps, QA's URL changes.

Every copy of the page is edited the same way: preview.html (+ any top-level source .html), cms-fields/ and
to-post/2-paste-into-cms/ (.html and .css). Before saving, the fixed page is opened in Edge at 1920 and 390 and every
heading must read and measure the same as before (only the added spaces may differ); a heading that changed is left
alone. Originals are backed up in qa/seo-fix-<time>/.

  python seo_fix.py "<page folder>" [--dry] [--sid <monday subitem id>]   (--sid writes a Claude's Notes line)
Prints one JSON line: {"fixed": n, "caps": [...], "spaces": [...], "alts": n, "skipped": [...], "files": [...]}
"""
import html as htmllib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "webapp"))
import settings  # noqa: E402
from features import _OK_CAMEL, _OK_CAPS  # noqa: E402  (same allowlists as the SEO check)

SMALL = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into", "nor", "of", "on", "or", "per", "the",
         "to", "vs", "via", "with"}
BRANDS = {b.lower(): b for b in re.findall(r"[A-Za-z]+", _OK_CAMEL.pattern) if re.search(r"[a-z][A-Z]|^[a-z]+[A-Z]", b)}
HEAD_RE = re.compile(r"(<script\b.*?</script\s*>|<style\b.*?</style\s*>)|<(h[1-6])\b([^>]*)>(.*?)</\2\s*>", re.S | re.I)
JOIN_TAGS = r"(?:span|b|strong|em|i|a|div|p|small|sup|mark)"
UC_CLASS = "seo-uc"


def plain(inner):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<br\s*/?>", " ", re.sub(r"<(?!br)[^>]+>", "", inner, flags=re.I), flags=re.I))).strip()


def fully_caps(text):
    words = re.findall(r"[A-Za-z][A-Za-z'’]*", text)
    big = [w for w in words if len(w) >= 3 and re.sub("['’]", "", w) not in _OK_CAPS]
    return bool(big) and not re.search(r"[a-z]", text)


def title_word(w, first):
    if re.search(r"\d", w):
        return w                                   # ZR2, 6.2L, AT4, 4X4
    core = re.sub("['’].*$", "", w)
    if core in _OK_CAPS or (len(w) == 1 and w != "A"):
        return w                                   # acronyms, "S Appearance Package"
    lw = w.lower()
    if lw in BRANDS:
        return BRANDS[lw]                          # ONSTAR -> OnStar
    if lw in SMALL and not first:
        return lw
    return w[0].upper() + w[1:].lower()


def to_title(inner):
    """Title Case the text parts of a heading's inner HTML; tags and entities stay as they are."""
    state = {"first": True}

    def seg(text):
        def word(m):
            if m.group(0).startswith("&"):
                return m.group(0)
            before, after = text[:m.start()], text[m.end():]
            if re.search(r"[A-Za-z](?:&rsquo;|&#8217;|&#x2019;|&#39;|&apos;)$", before, re.I):
                return m.group(0).lower()            # "CAPTAIN&rsquo;S" -> "Captain&rsquo;s"
            joined = (re.search(r"[-/](?:&#8203;|​)?$", before) or re.match(r"(?:&#8203;|​)?/", after)   # "Built-In", "On/Off"
                      or re.search(r"[:—|]\s*$", before))                  # "A New Era: The Best"
            out = title_word(m.group(0), state["first"] or bool(joined))
            state["first"] = False
            return out
        res = re.sub(r"&#?\w+;|[A-Za-z0-9][A-Za-z0-9'’]*", word, text)
        if re.search(r"[:—|]\s*$", text):
            state["first"] = True                    # word after a colon / dash starts a new phrase
        return res

    parts = re.split(r"(<[^>]+>)", inner)
    return "".join(p if p.startswith("<") else seg(p) for p in parts)


def add_space(inner):
    """Insert a space where text ending in a letter/number meets a tag run followed by a letter/number."""
    parts = re.split(r"(<[^>]+>)", inner)
    out, n = [], 0
    i = 0
    while i < len(parts):
        p = parts[i]
        if p.startswith("<"):
            j = i
            while j < len(parts) and (parts[j].startswith("<") or parts[j] == ""):
                j += 1
            run = parts[i:j]
            prev = "".join(out)
            nxt = parts[j] if j < len(parts) else ""
            joins = any(re.match(rf"</?{JOIN_TAGS}\b", t, re.I) for t in run) and not any(re.match(r"<br\b", t, re.I) for t in run)
            if joins and re.search(r"[A-Za-z0-9.,]$", re.sub(r"<[^>]+>", "", prev)) and re.match(r"[A-Za-z0-9]", nxt):
                out.append(" ")
                n += 1
            out.extend(run)
            i = j
            continue
        out.append(p)
        i += 1
    return "".join(out), n


def with_class(attrs):
    m = re.search(r"""\bclass\s*=\s*(["'])(.*?)\1""", attrs, re.S)
    if m:
        if UC_CLASS in m.group(2).split():
            return attrs
        return attrs[:m.start(2)] + (m.group(2) + " " + UC_CLASS).strip() + attrs[m.end(2):]
    return attrs + f' class="{UC_CLASS}"'


def transform(src, skip_caps=(), skip_space=()):
    """-> (new html, report). skip_* = heading plain texts to leave alone (failed the look check)."""
    rep = {"caps": [], "spaces": [], "alts": 0}
    heads = []                                     # (position, plain text) for alt text

    def head(m):
        if m.group(1):
            return m.group(1)
        tag, attrs, inner = m.group(2), m.group(3), m.group(4)
        txt = plain(inner)
        heads.append((m.start(), txt))
        if txt not in skip_space:
            inner2, n = add_space(inner)
            if n:
                rep["spaces"].append(txt)
                inner = inner2
        if fully_caps(plain(inner)) and txt not in skip_caps:
            new = to_title(inner)
            if new != inner:
                rep["caps"].append([txt, plain(new)])
                inner, attrs = new, with_class(attrs)
        return f"<{tag}{attrs}>{inner}</{tag}>"

    out = HEAD_RE.sub(head, src)

    def img(m):
        if re.search(r"\balt\s*=", m.group(0), re.I):
            return m.group(0)
        pos = m.start()
        above = [t for p, t in heads if p < pos and t]
        src_m = re.search(r"""\bsrc\s*=\s*["']([^"']+)""", m.group(0))
        alt = above[-1] if above else (re.sub(r"[-_]+", " ", Path(src_m.group(1)).stem).strip().capitalize() if src_m else "")
        if not alt:
            return m.group(0)
        rep["alts"] += 1
        return m.group(0)[:4] + f' alt="{htmllib.escape(alt[:110], quote=True)}"' + m.group(0)[4:]

    parts = re.split(r"(<script\b.*?</script\s*>|<style\b.*?</style\s*>)", out, flags=re.S | re.I)
    # positions for "nearest heading above" are in the pre-sub text; close enough because heads only grow by a few chars
    out = "".join(p if re.match(r"<(script|style)\b", p, re.I) else re.sub(r"<img\b[^>]*>", img, p, flags=re.I) for p in parts)
    return out, rep


def page_id(src):
    m = re.search(r"#([A-Za-z][\w-]*)\s*[{,\s]", "".join(re.findall(r"<style\b[^>]*>(.*?)</style>", src, re.S | re.I)))
    if m:
        return m.group(1)
    m = re.search(r"""<div\b[^>]*\bid\s*=\s*["']([^"']+)""", src, re.I)
    return m.group(1) if m else None


def css_rule(pid):
    return (f"\n/* SEO: these headings are Title Case in the HTML and shown in caps here (screen readers, search results) */\n"
            f"#{pid}#{pid} .{UC_CLASS}, #{pid}#{pid} .{UC_CLASS} * {{ text-transform: uppercase !important; }}\n")


def add_css_html(src, pid):
    if f".{UC_CLASS}" in re.sub(r"class=[\"'][^\"']*[\"']", "", src) or not pid:
        return src
    styles = list(re.finditer(r"</style\s*>", src, re.I))
    if styles:
        k = styles[-1].start()
        return src[:k] + css_rule(pid) + src[k:]
    m = re.search(rf"""<div\b[^>]*\bid\s*=\s*["']{re.escape(pid)}["'][^>]*>""", src, re.I)
    return src[:m.end()] + f"<style>{css_rule(pid)}</style>" + src[m.end():] if m else src


def page_files(folder):
    f = Path(folder)
    htmls = [p for p in [f / "preview.html"] + sorted(f.glob("*.html")) if p.is_file() and "before" not in p.name and "seo-check" not in p.name]
    css = []
    for d in (f / "cms-fields", f / "to-post" / "2-paste-into-cms"):
        if d.is_dir():
            htmls += sorted(d.glob("*.html"))
            css += sorted(d.glob("*.css"))
    return list(dict.fromkeys(htmls)), css


def snap(files):
    tk = settings.get("toolkit_root")
    r = subprocess.run(["node", str(HERE / "seo_heading_snap.js"), tk] + [str(x) for x in files], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode:
        raise RuntimeError("look check failed to run: " + (r.stderr or r.stdout)[-300:])
    return json.loads(r.stdout)


def look_check(main, new_src, rep):
    """Render before/after; -> (caps texts that changed look, space texts that changed more than a space)."""
    tmp = main.with_name(main.stem + ".seo-check.html")
    tmp.write_text(new_src, encoding="utf-8")
    try:
        s = snap([main, tmp])
    finally:
        tmp.unlink(missing_ok=True)
    a, b = s[str(main)], s[str(tmp)]
    bad_caps, bad_space = set(), set()
    caps_old = {o for o, _n in rep["caps"]}
    for w in ("1920", "390"):
        if len(a[w]) != len(b[w]):
            return caps_old, set(rep["spaces"])        # headings added/removed by scripts: change nothing
        for (t1, x1, w1, h1), (t2, x2, w2, h2) in zip(a[w], b[w]):
            same = x1 == x2 and abs(w1 - w2) <= 1 and abs(h1 - h2) <= 1
            if same:
                continue
            spaced = re.sub(r"\s", "", x1) == re.sub(r"\s", "", x2)
            key = next((o for o in caps_old if re.sub(r"\W", "", o.upper()) == re.sub(r"\W", "", x1.upper())), None)
            if key and not spaced:
                bad_caps.add(key)
            elif not spaced:
                bad_space.update(o for o in rep["spaces"] if re.sub(r"\W", "", o.upper()) == re.sub(r"\W", "", x1.upper()))
    return bad_caps, bad_space


def fix(folder, dry=False):
    folder = Path(folder)
    htmls, css = page_files(folder)
    if not htmls:
        return {"fixed": 0, "error": "no page files"}
    main = htmls[0]
    src = main.read_text(encoding="utf-8", errors="ignore")
    new, rep = transform(src)
    skipped = []
    if (rep["caps"] or rep["spaces"]) and not dry:
        bad_caps, bad_space = look_check(main, add_css_html(new, page_id(src)) if rep["caps"] else new, rep)
        if bad_caps or bad_space:
            skipped = [f"left as is (the look changed): {t}" for t in sorted(bad_caps | bad_space)]
            new, rep = transform(src, bad_caps, bad_space)
    total = len(rep["caps"]) + len(rep["spaces"]) + rep["alts"]
    result = {"fixed": total, "caps": rep["caps"], "spaces": rep["spaces"], "alts": rep["alts"], "skipped": skipped, "files": []}
    if not total or dry:
        return result
    bak = folder / "qa" / f"seo-fix-{datetime.now():%Y%m%d-%H%M%S}"
    for p in htmls + css:
        s = p.read_text(encoding="utf-8", errors="ignore")
        bad_caps = {t for t in (x.split(": ", 1)[1] for x in skipped)}
        if p.suffix == ".html":
            out, _r = transform(s, bad_caps, bad_caps)
            if rep["caps"]:
                out = add_css_html(out, page_id(s))
        else:
            pid = page_id("<style>" + s + "</style>")
            out = s if (not rep["caps"] or f".{UC_CLASS}" in s or not pid) else s.rstrip("\n") + "\n" + css_rule(pid)
        if out != s:
            dest = bak / p.relative_to(folder)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)
            p.write_text(out, encoding="utf-8")
            result["files"].append(str(p.relative_to(folder)))
    result["backup"] = str(bak)
    return result


def note_text(r):
    bits = []
    if r["caps"]:
        bits.append(f"{len(r['caps'])} ALL-CAPS heading(s) -> Title Case in the HTML, caps kept via CSS (" +
                    "; ".join(f'"{n}"' for _o, n in r["caps"][:3]) + (" ..." if len(r["caps"]) > 3 else "") + ")")
    if r["spaces"]:
        bits.append(f"space added in {len(r['spaces'])} heading(s) (" + "; ".join(f'"{t}"' for t in r["spaces"][:2]) + ")")
    if r["alts"]:
        bits.append(f"alt text added to {r['alts']} image(s)")
    s = "SEO auto-fix: " + "; ".join(bits) + ". Look checked at 1920/390 (headings unchanged)."
    if r["skipped"]:
        s += f" Left for review: {len(r['skipped'])}."
    return s + " Re-paste the page's HTML field."   # build_mlp_tracker --note adds the date itself


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    sid = args[args.index("--sid") + 1] if "--sid" in args else None
    r = fix(args[0], dry="--dry" in args)
    if sid and r.get("fixed") and "--dry" not in args:
        subprocess.run([sys.executable, str(HERE / "build_mlp_tracker.py"), "--note", str(sid), note_text(r)], cwd=str(HERE),
                       capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        r["note"] = note_text(r)
    print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
