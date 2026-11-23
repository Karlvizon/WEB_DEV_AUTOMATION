"""Start a new MLP project from the shared toolkit.

1. Create the project folder and put a project.json in it (see project.example.json).
2. python "<toolkit>/new_project.py" "<Work folder>/<year make model>, <Dealer>"

It copies tools/ (tokens {{ID}} {{P}} {{NAME}} {{CDN}} filled in from project.json), the shared
node_modules for the QA scripts, makes assets/webp, cms-fields, figma, qa, and writes a starter
preview.html: the component library (components/components.css + .js) inside the page wrapper,
with an empty <div class="P-wrap"> for the markup. Re-running it refreshes tools/ only; it never
overwrites an existing preview.html.
"""
import json
import shutil
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent


def fill(text: str, p: dict) -> str:
    return (text.replace("{{ID}}", p["id"]).replace("{{P}}", p["prefix"])
            .replace("{{NAME}}", p["name"]).replace("{{CDN}}", p.get("cdn", "")))


def main() -> None:
    root = Path(sys.argv[1])
    proj = json.loads((root / "project.json").read_text(encoding="utf8"))
    for k in ("id", "prefix", "name", "title", "dealer", "location", "platform", "figma"):
        assert k in proj, f"project.json needs '{k}'"
    assert proj["platform"] in ("dealer-inspire", "one-file"), "platform: dealer-inspire | one-file"
    cms_dir = (lambda _p: Path(_p.read_text(encoding="utf-8").strip()) if _p.exists() else Path(__file__).resolve().parents[2] / "tracker")((Path(__import__("os").environ["APPDATA"]) if __import__("sys").platform == "win32" else Path.home() / "Library" / "Application Support") / "MLP Tracker" / "tracker_path.txt") / "cms_directory.json"
    if cms_dir.exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location("trk", cms_dir.parent / "build_mlp_tracker.py")
        trk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(trk)
        cms = trk.platform_for(proj["dealer"], trk.load_platforms())
        want = "dealer-inspire" if cms.startswith("Dealer Inspire") else "one-file"
        assert not cms.startswith("?"), f"{proj['dealer']} is not in monday's CMS list (Dealer Login and Setup board) - check it first"
        assert proj["platform"] == want, f"monday says {proj['dealer']} uses {cms}: set platform to '{want}' in project.json"
        print(f"CMS check: {proj['dealer']} -> {cms} (monday Dealer Login and Setup)")
        name = cms.split(" (")[0]
        if proj.get("cms") != name:   # e.g. "Apollo" -> split_fields.py puts the style inside a <script> (rule 2026-11-20)
            proj["cms"] = name
            (root / "project.json").write_text(json.dumps(proj, indent=1, ensure_ascii=False), encoding="utf8")
    if proj["platform"] == "dealer-inspire":
        assert proj.get("cdn", "").startswith("https://"), "Dealer Inspire pages need the media-library 'cdn' folder URL"
    for d in ("assets/webp", "cms-fields", "figma", "qa/shots", "tools/_work/source"):
        (root / d).mkdir(parents=True, exist_ok=True)
    for f in (KIT / "tools").rglob("*"):
        if f.is_dir():
            continue
        dst = root / "tools" / f.relative_to(KIT / "tools")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if f.suffix in (".py", ".js", ".sh", ".json", ".md", ".ps1"):
            dst.write_text(fill(f.read_text(encoding="utf8"), proj), encoding="utf8")
        else:
            shutil.copy2(f, dst)
    nm = root / "tools/qa/node_modules"
    if not nm.exists():
        shutil.copytree(KIT / "node_modules", nm)
    prev = root / "preview.html"
    if not prev.exists():
        css = fill((KIT / "components/components.css").read_text(encoding="utf8"), proj)
        js = fill((KIT / "components/components.js").read_text(encoding="utf8"), proj)
        P = proj["prefix"]
        prev.write_text(
            "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{proj['title']}, {proj['dealer']} - preview</title>\n"
            "<style>html,body{margin:0;padding:0;}</style>\n</head>\n<body>\n"
            f"<div class=\"main-div\" id=\"{proj['id']}\">\n"
            "<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?family=Roboto:ital,wght@0,300;0,400;0,500;0,700;1,300;1,400&amp;display=swap\">\n"
            f"<style>\n{css.strip()}\n</style>\n<div class=\"{P}-wrap\">\n</div>\n<script>\n{js.strip()}\n</script>\n</div>\n</body>\n</html>\n",
            encoding="utf8")
    print(f"ready: {root}  (id {proj['id']}, prefix {proj['prefix']}-, platform {proj['platform']})")


if __name__ == "__main__":
    main()
