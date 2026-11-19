"""Delete the build/QA byproducts of APPROVED MLP projects, keep the deliverables.

User rule, 2026-11-12: "once the page or website is approve delete all the files under that project that is not
needed but left the files that is important".

Usage:  python cleanup_approved.py            -> dry run: what would be kept / deleted per approved project
        python cleanup_approved.py --delete   -> deletes

Acts only on entries of project_folders.json whose status is "Approved" (Claude sets it from monday on refresh).
KEEP: preview.html (or the page .html on older projects without one), cms-fields/, the uploaded images
(assets/webp/ or loose assets/*.webp; images-to-upload/, upload-to-cms/, upload-missing-images/ on older projects),
ready-for-review.txt, project.json, brief.json / brief.md.
DELETE: everything else (qa/, tools/, figma/, review.html, working images, Figma PNGs).
REFERENCE projects (named in the build rules: Trax, Optiq, Yukon) also keep their small tool scripts
(tools/**/*.py|js|sh|json); only their heavy folders (_work, models, node_modules, __pycache__) and other files go.
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEEP_FILES = {"preview.html", "ready-for-review.txt", "project.json", "brief.json", "brief.md"}
KEEP_DIRS = {"cms-fields", "images-to-upload", "upload-to-cms", "upload-missing-images"}
SCRIPT_EXT = {".py", ".js", ".sh", ".json"}
HEAVY = {"_work", "models", "node_modules", "__pycache__"}


def size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def plan(proj: Path, reference: bool):
    keep, drop = [], []
    has_preview = (proj / "preview.html").exists()
    for item in sorted(proj.iterdir()):
        n = item.name
        if item.is_file():
            page_html = n.endswith(".html") and n != "review.html" and not has_preview
            (keep if n in KEEP_FILES or page_html else drop).append(item)
        elif n in KEEP_DIRS:
            keep.append(item)
        elif n == "assets":
            for a in sorted(item.iterdir()):
                (keep if a.name == "webp" or (a.is_file() and a.suffix == ".webp") else drop).append(a)
        elif n == "tools" and reference:
            for d in sorted(item.rglob("*")):
                rel = d.relative_to(item).parts
                if any(p in HEAVY for p in rel[:-1]):
                    continue  # inside a heavy folder that is dropped whole
                if d.is_dir() and d.name in HEAVY:
                    drop.append(d)
                elif d.is_file() and d.suffix not in SCRIPT_EXT:
                    drop.append(d)
            keep.append(item / "(scripts only)")
        else:
            drop.append(item)
    return keep, drop


sys.path.insert(0, str(Path(__file__).resolve().parent))   # -I drops the script folder from sys.path
import settings  # noqa: E402  (tracker_config.json, Settings tab)
TOOLKIT = Path(settings.get("toolkit_root"))


def archive_scripts(proj: Path, label: str, do: bool) -> int:
    """Copy the project's own tool scripts (.py/.js/.sh, incl. tools/_work/*.py) to
    _mlp-toolkit/from-projects/<label>/ before tools/ is deleted, skipping files identical to the toolkit's copy.
    Keeps every script the build rules refer to (e.g. region_upscale.py, _dens.js, gen.py) at a few KB."""
    tools = proj / "tools"
    if not tools.exists():
        return 0
    n = 0
    for f in tools.rglob("*"):
        rel = f.relative_to(tools)
        if not f.is_file() or f.suffix not in {".py", ".js", ".sh"} or any(p in {"node_modules", "models", "__pycache__"} for p in rel.parts):
            continue
        if "_work" in rel.parts and f.suffix != ".py":
            continue
        same = TOOLKIT / "tools" / rel
        if same.exists() and same.read_bytes() == f.read_bytes():
            continue
        if do:
            dst = TOOLKIT / "from-projects" / label / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
        n += 1
    return n


def rescue(proj: Path, keep, drop, do: bool) -> list:
    """Images the page uses (named in cms-fields) that exist only inside folders being deleted are copied to
    assets/webp first, so the kept project always holds every image of the live page."""
    import re
    names = set()
    for f in (proj / "cms-fields").glob("*"):
        names |= set(re.findall(r"[\w.-]+\.(?:webp|png|jpe?g|svg|gif)", f.read_text(encoding="utf-8", errors="ignore")))
    kept = set()
    for k in keep:
        if k.is_dir():
            kept |= {p.name for p in k.rglob("*") if p.is_file()}
        elif k.is_file():
            kept.add(k.name)
    saved = []
    for n in sorted(names - kept):
        for d in drop:
            hits = list(d.rglob(n)) if d.is_dir() else ([d] if d.name == n else [])
            if hits:
                if do:
                    (proj / "assets/webp").mkdir(parents=True, exist_ok=True)
                    shutil.copy2(hits[0], proj / "assets/webp" / n)
                saved.append(n)
                break
    missing = sorted(names - kept - set(saved))
    return saved, missing


def main() -> None:
    if not (HERE / "project_folders.json").exists():   # new PC: no projects listed yet, nothing to clean
        print("Clean-up: no project folders listed yet")
        return
    cfg = json.load(open(HERE / "project_folders.json", encoding="utf-8"))
    do = "--delete" in sys.argv
    total = 0.0
    for e in cfg["projects"]:
        if e.get("status") != "Approved" or e.get("cleaned"):
            continue
        proj = Path(e["folder"])
        if not proj.exists():
            print(f"!! missing folder: {proj}")
            continue
        keep, drop = plan(proj, e.get("reference", False))
        mb = sum(size(d) for d in drop) / 2**20
        total += mb
        print(f"== {e['dealer']} | {e['mlp']}")
        print("   keep:  ", ", ".join(str(k.relative_to(proj)) for k in keep))
        print(f"   delete ({mb:.0f} MB):", ", ".join(str(d.relative_to(proj)) for d in drop)[:500])
        saved, missing = rescue(proj, keep, drop, do)
        if saved:
            print(f"   rescued {len(saved)} page images into assets/webp first")
        if missing:
            print(f"   !! {len(missing)} page images not found anywhere in the project - skipped this project:", missing[:5])
            continue
        label = f"{e['dealer']} - {e['mlp']}"
        print(f"   {archive_scripts(proj, label, do)} project-only scripts {'copied' if do else 'to copy'} to _mlp-toolkit/from-projects/{label}")
        if do:
            for d in drop:
                if d.is_dir():
                    shutil.rmtree(d)
                elif d.exists():
                    d.unlink()
            e["cleaned"] = True
    if do:
        json.dump(cfg, open(HERE / "project_folders.json", "w", encoding="utf-8"), indent=1)
    print(f"\n{'DELETED' if do else 'would delete'}: {total / 1024:.2f} GB")


if __name__ == "__main__":
    main()
