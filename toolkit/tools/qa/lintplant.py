"""Prove cmslint.py works: plant one violation at a time in a copy of the CMS fields and
check that the lint fails for every one of them (and passes on the clean copy).
usage: python tools/qa/lintplant.py"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import json
SRC = ROOT / ("cms-fields" if json.loads((ROOT / "project.json").read_text(encoding="utf8")).get("platform") == "dealer-inspire" else "tools/_work/fields")
LINT = ROOT / "tools/qa/cmslint.py"
NL = chr(10)
PLANTS = [
    ("js", "setTimeout", lambda s: s.replace("CP.ready(function", "setTimeout(function () {}, 5); CP.ready(function", 1)),
    ("js", "line comment", lambda s: s.replace("(function () {", "(function () { // note", 1)),
    ("js", "blank line", lambda s: s.replace(NL, NL + NL, 1)),
    ("js", "innerHTML", lambda s: s.replace("var CP = {", "document.body.innerHTML; var CP = {", 1)),
    ("js", "double pipe", lambda s: s.replace("var CP = {", "var q = 1 || 2; var CP = {", 1)),
    ("js", "new Date", lambda s: s.replace("var CP = {", "var d = new Date(); var CP = {", 1)),
    ("js", "raw less-than", lambda s: s.replace("var CP = {", "var q = 1 < 2; var CP = {", 1)),
    ("css", "unscoped selector", lambda s: s + NL + "body{margin:0 !important;}"),
    ("css", "css comment", lambda s: s.replace("{", "{/* x */", 1)),
    ("css", "@import", lambda s: "@import url(x.css);" + NL + s),
    ("html", "br tag", lambda s: s.replace("</h1>", "<br></h1>", 1)),
    ("html", "todo link", lambda s: s.replace('class="{{P}}-btn" href="', 'class="{{P}}-btn" data-todo-link="Get A Quote" href="', 1)),
    ("html", "html comment", lambda s: s.replace("<section", "<!-- x --><section", 1)),
    ("html", "inline style", lambda s: s.replace('<p class="{{P}}-hero__p"', '<p style="color:red" class="{{P}}-hero__p"', 1)),
    ("html", "local image path", lambda s: s.replace("{{CDN}}", "assets/webp/", 1)),
    ("html", "duplicate id", lambda s: s.replace('<div class="{{P}}-wrap">', '<div class="{{P}}-wrap"><i id="{{ID}}"></i>', 1)),
]


def lint(folder: Path) -> bool:
    env = dict(os.environ, CMSDIR=str(folder))
    return subprocess.run([sys.executable, "-I", str(LINT)], env=env, capture_output=True, text=True).returncode == 0


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="lintplant-"))
    shutil.copytree(SRC, tmp, dirs_exist_ok=True)
    ok = lint(tmp)
    print("clean copy:", "pass" if ok else "FAIL")
    caught = 0
    for kind, name, fn in PLANTS:
        shutil.copytree(SRC, tmp, dirs_exist_ok=True)
        f = tmp / f"compass.{kind}"
        before = f.read_text(encoding="utf-8")
        after = fn(before)
        assert after != before, name
        f.write_text(after, encoding="utf-8")
        hit = not lint(tmp)
        caught += hit
        print(f"{'caught ' if hit else 'MISSED '} {kind:4} {name}")
    shutil.copytree(SRC, tmp, dirs_exist_ok=True)
    print(f"{caught}/{len(PLANTS)} planted violations caught; clean copy {'passes' if ok else 'fails'}")
    return 0 if ok and caught == len(PLANTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
