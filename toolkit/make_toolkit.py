"""Rebuild the shared MLP toolkit from a finished reference project.

Turns the project's tools/ and its preview.html CSS/JS into templates with these tokens:
  {{ID}}    page-unique wrapper id        (e.g. hc-2026-compass)
  {{P}}     class prefix, no dash         (e.g. cmp)
  {{NAME}}  cms-fields file base name     (e.g. compass)
  {{CDN}}   media-library URL folder      (Dealer Inspire only; '' for one-file sites)
new_project.py fills them back in for a new page.

usage: python make_toolkit.py "<Projects folder>/Huston CDJR/2026 Jeep Compass, Huston CDJR" hc-2026-compass cmp compass
"""
import re
import shutil
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
SKIP_DIRS = {"node_modules", "_work", "models", "__pycache__"}
SKIP_FILES = {"vehicle-bbox.json"}


def templ(text: str, pid: str, pfx: str, name: str, cdn: str) -> str:
    text = text.replace(pid, "{{ID}}")
    if cdn:
        text = text.replace(cdn, "{{CDN}}")
    text = re.sub(rf"(?<![A-Za-z0-9_]){pfx}(?=-|\b)", "{{P}}", text)
    text = re.sub(rf"\b{name}\.(css|html|js)\b", r"{{NAME}}.\1", text)
    return text


def main() -> None:
    src, pid, pfx, name = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
    split = (src / "tools/split_fields.py").read_text(encoding="utf8")
    m = re.search(r'CDN = "([^"]+)"', split)
    cdn = m.group(1) if m else ""
    out = KIT / "tools"
    if out.exists():
        shutil.rmtree(out)
    for f in (src / "tools").rglob("*"):
        rel = f.relative_to(src / "tools")
        if any(p in SKIP_DIRS for p in rel.parts) or f.name in SKIP_FILES or f.is_dir():
            continue
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if f.suffix in (".py", ".js", ".sh", ".json", ".md", ".ps1"):
            dst.write_text(templ(f.read_text(encoding="utf8"), pid, pfx, name, cdn), encoding="utf8")
        else:
            shutil.copy2(f, dst)
    nm = src / "tools/qa/node_modules"
    if nm.exists() and not (KIT / "node_modules").exists():
        shutil.copytree(nm, KIT / "node_modules")
    html = (src / "preview.html").read_text(encoding="utf8")
    css = html[html.index("<style>\n#") + 8: html.index("</style>\n<div class=")]
    js = html[html.index("<script>\n") + 9: html.rindex("</script>")]
    comp = KIT / "components"
    comp.mkdir(exist_ok=True)
    (comp / "components.css").write_text(templ(css, pid, pfx, name, cdn), encoding="utf8")
    (comp / "components.js").write_text(templ(js, pid, pfx, name, cdn), encoding="utf8")
    (comp / "reference-page.html").write_text(templ(html, pid, pfx, name, cdn), encoding="utf8")
    print("toolkit rebuilt from", src.name, "| CDN", cdn or "-")


if __name__ == "__main__":
    main()
