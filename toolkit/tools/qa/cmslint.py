"""Lint the three CMS field files for Page Composer safety.
usage: python -I tools/qa/cmslint.py"""
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import os
import json
_P = json.loads((ROOT / "project.json").read_text(encoding="utf8"))
F = Path(os.environ["CMSDIR"]) if os.environ.get("CMSDIR") else ROOT / ("cms-fields" if _P.get("platform") == "dealer-inspire" else "tools/_work/fields")
css = (F / "{{NAME}}.css").read_text(encoding="utf-8")
html = (F / "{{NAME}}.html").read_text(encoding="utf-8")
js = (F / "{{NAME}}.js").read_text(encoding="utf-8")
ID = "#{{ID}}"
problems = []


def check(cond, msg):
    if not cond:
        problems.append(msg)


for name, text in (("css", css), ("html", html), ("js", js)):
    lines = text.replace("\r\n", "\n").split("\n")
    check(not any(l.strip() == "" for l in lines[:-1]), f"{name}: blank line")
    check(all(ord(c) < 128 for c in text), f"{name}: non-ASCII character")
    check(not _P.get("cdn") or "assets/webp/" not in text, f"{name}: local image path")
    check("<!--" not in text and "/*" not in text, f"{name}: comment")
    check(not re.search(r"(?<![:\"'])//", text), f"{name}: // comment")
check("<script" not in html, "html: carries a script block")
check(html.count("<style>") == 1 and html.count("</style>") == 1 and css.strip() in html, "html: must carry the CSS in exactly one <style> block (identical to the CSS field)")
check(html.index("<style>") > html.index('id="{{ID}}"') and html.index("</style>") < html.find('<div class="{{P}}-wrap"'), "html: the <style> block must sit inside the wrapper, before the markup")
check("style=" not in re.sub(r"<style>.*?</style>", "", html, flags=re.S), "html: inline style attribute (use a CSS class)")
check("<style" not in css and "<script" not in css and "<script" not in js and "<style" not in js and "<script" not in html, "a field carries another field's tags")
if _P.get("fonts", "google") == "google":
    check("@font-face" not in css, "css: @font-face (this page loads its font from Google Fonts)")
    check(re.match(r'<div class="main-div" id="{{ID}}">\r?\n<link rel="stylesheet" href="https://fonts\.googleapis\.com/css2\?family=[A-Za-z+]+:[^"<>]*&amp;display=swap">', html), "html: the Google Fonts <link> must be the first element inside the wrapper")
check("MEDIA-LIBRARY-URL-PENDING" not in css + html + js, "fields: image URLs still use the placeholder media-library pattern (waiting for the Drive Philly upload URL)")
check("@import" not in css, "css: @import (blocked by security filters; fonts are a <link> in the HTML field)")
for pat, why in ((r"expression\s*\(|javascript:|behavior\s*:|-moz-binding|</?style|</?script", "css: security-filter trigger"),):
    check(not re.search(pat, css, re.I), why)
check("<br" not in html, "html: <br> (WordPress strips it; use block spans or separate paragraphs)")
# JS patterns that WordPress / host security filters (WAF, OWASP CRS) block when the field is saved
BLOCKED = {
    r"\b(setTimeout|setInterval|eval|Function|alert|prompt|confirm)\s*\(": "timer/eval call (OWASP 941390); use CP.later",
    r"\bnew\s+Date\b|\bDate\.now\b|\.(getDay|getTime|getHours|getDate)\s*\(":"Date/clock API (blocked on hustoncdjr.com 2026-11-06, OWASP 932); highlight statically",
    r"fromCharCode|\batob\s*\(|\bunescape\s*\(|\\x[0-9a-fA-F]{2}|\\u00": "string obfuscation",
    r"\b(createElement|appendChild|insertBefore|replaceChild|cloneNode|insertAdjacentHTML)\b": "DOM injection; put the markup in the HTML field",
    r"document\s*\.\s*(cookie|write|location|domain)|\.(innerHTML|outerHTML|parentNode)\b|location\s*\.\s*href": "OWASP 941180 keyword",
    r"[\s;(,=]on[a-zA-Z]{3,25}\s*=[^=]": "on<event>= handler pattern (OWASP 941120)",
    r"https?://|javascript:|<|&": "URL, javascript: or raw < / &",
    r"=>|\blet\b|\bconst\b|`|\bclass\s+\w|\basync\b|\bawait\b": "ES2015+ syntax (keep ES5 for old CMS editors and minifiers)",
    r"\bconsole\b|\bwindow\s*\.|\bself\s*\.|\btop\s*\.|\bdocument\s*\[": "global object access the WAF may score (console/window/top)",
    r"\|\|": "|| (SQL concat operator, OWASP 942 scores it); use nested ifs",
    r"''|\"\"": "empty string literal (SQLi probe pattern '' )",
    r"'\s*[+:?]\s*'|'\s*(or|and|union|select|true|false)\b|\b(or|and|union|select|true|false)\s*'": "quote/operator/quote or quoted SQL keyword (OWASP 942 tautology/probing)",
    r"\b(union|select|insert|drop|delete|update|exec|sleep|benchmark|waitfor)\s*\(|\bselect\b.+\bfrom\b": "SQL keyword pattern (OWASP 942)",
    r"--|/\*|\*/|#": "SQL comment characters",
    r"\bsrc\s*=|\bhref\s*=|\.src\b|\.href\b|\bimport\b|\brequire\s*\(": "URL/script loading pattern",
    r"(?<!prototype)\.(closest|matches|includes|startsWith|endsWith|find|findIndex|append|prepend|replaceWith|before|after|forEach)\s*\(|\bArray\.from\b|\bObject\.assign\b|\bPromise\b|\bfetch\s*\(|\bSymbol\b|\bnew\s+(Map|Set)\b": "post-ES5 API (use CP.up instead of closest, Array.prototype.forEach.call for NodeLists)",
}
for pat, why in BLOCKED.items():
    for n, line in enumerate(js.splitlines(), 1):
        if re.search(pat, line):
            problems.append(f"js line {n}: {why}: {line.strip()[:70]}")
check(js.lstrip().startswith("(function () {") and js.rstrip().endswith("})();"), "js: must be one IIFE")
check("data-cp-ready" in js, "js: missing the run-once guard (data-cp-ready on the wrapper); a field output twice would bind every listener twice")
check("CP.start(tries - 1)" in js, "js: missing the retry for when the HTML field is not in the DOM yet")
check(css.count("{") == css.count("}"), "css: unbalanced braces")
check(js.count("{") == js.count("}") and js.count("(") == js.count(")"), "js: unbalanced braces/parens")
# every selector scoped to the id
body = re.sub(r"@font-face\s*\{[^{}]*\}", "", css)
body = re.sub(r"@(media|supports)[^{]*\{", "", body)
body = re.sub(r'@import\s+url\("[^"]*"\)\s*;', "", body)
for block in re.findall(r"([^{}]+)\{[^{}]*\}", body):
    for sel in block.split(","):
        sel = sel.strip()
        if sel and not sel.startswith(ID):
            problems.append(f"css: unscoped selector {sel[:60]}")
# inline elements must not be separated by line breaks
check(not re.search(r"</(a|button|span|b)>\s*\n\s*<(a|button|span|b)[\s>]", html), "html: line break between adjacent inline elements")
# balanced tags, unique ids
class P(HTMLParser):
    VOID = {"img", "br", "input", "meta", "link", "hr", "source"}

    def __init__(self):
        super().__init__(); self.stack = []; self.ids = []; self.bad = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if "id" in d: self.ids.append(d["id"])
        if tag not in self.VOID: self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag: self.bad.append(tag)
        else: self.stack.pop()


p = P(); p.feed(html)
check(not p.bad and not p.stack, f"html: unbalanced tags {p.bad[:3]} {p.stack[:3]}")
dup = [k for k, v in Counter(p.ids).items() if v > 1]
check(not dup, f"html: duplicate ids {dup}")
check(html.startswith('<div class="main-div" id="{{ID}}">') and html.rstrip().endswith("</div>"), "html: wrapper must open and close the field")
check(html.count("<h1") == 1, "html: exactly one h1")
imgs = re.findall(r"<img [^>]*>", html)
check(all('alt="' in i for i in imgs), "html: img without alt")
links = re.findall(r"<a [^>]*>", html)
check(all('target="_blank"' in a and 'rel="noopener"' in a for a in links), "html: link without target=_blank rel=noopener")
check(not re.search(r"href=\"[^\"]*&(?!amp;)", html), "html: unescaped & in a URL")
todo = re.findall(r'data-todo-link="([^"]+)"', html)
check(not todo, "html: %d buttons still have no link from the user (%s)" % (len(todo), ", ".join(sorted(set(todo)))))
check('href="#"' not in html, "html: placeholder href=#")
print("\n".join(problems) or "CMS lint: clean")
print(f"css {len(css.splitlines())} lines, html {len(html.splitlines())} lines ({len(imgs)} images, {len(links)} links), js {len(js.splitlines())} lines")
(ROOT / "qa/cmslint.txt").write_text(("\n".join(problems) or "clean") + "\n", encoding="utf-8")
raise SystemExit(1 if problems else 0)
