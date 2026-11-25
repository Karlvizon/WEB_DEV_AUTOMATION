"""Production helpers (user, 2026-11-13: "build the Production features").

  python production.py pack "<project folder>"          -> to-post/ upload pack (images in batches of 8, CMS fields, monday note)
  python production.py triage "<revision.txt>"           -> checklist.md next to it: QA's points numbered + matched to known fixes
  python production.py dealer "<dealer name>"            -> what the dealer's last page used (fonts, CTA links, CDN, colours)
  python production.py intake "<saved monday updates json>" "<dealer>" "<mlp>"
                                                         -> new project folder + brief.json from the monday brief (+ dealer base)
Before/after images: node "<toolkit>/tools/qa/beforeafter.js" (see that file).
"""
import json
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parent))   # -I drops the script folder from sys.path
import settings  # noqa: E402  (tracker_config.json, Settings tab)
MLP_ROOT = Path(settings.get("mlp_root"))

# ---------------------------------------------------------------- revision triage
RULES = [  # (keywords, label) - QA points that came back before (qa_feedback.md); first match wins
    (("gradient",), "KNOWN: mobile photo fade into the panel, no edge strip (Gladiator/Durango fix)"),
    (("hero title", "hero"), "KNOWN: hero per Figma - sizes, gaps, rule reaching the end of the title"),
    (("upscale", "blurry", "pixelated", "low quality", "low-quality"), "KNOWN: upscale the visible area with the A3 upscaler"),
    (("space above the mlp", "top margin", "left margin"), "KNOWN: MLP top margin = left margin"),
    (("title in the mlp", "missing title", "title of the mlp"), "KNOWN: MLP content title (h2, same size, bold)"),
    (("font style", "same font", "font size"), "KNOWN: disclaimer font/size = MLP content"),
    (("asterisk",), "KNOWN: asterisks only where a disclaimer backs them (add or remove)"),
    (("zoom-in", "zoom in"), "KNOWN: mobile zoom crop (-m) around the subject"),
    (("zoom out", "cut off", "cropped"), "KNOWN: show the whole vehicle (zoom out)"),
    (("reduce the spacing", "less space", "too far"), "KNOWN: tighten spacing (20px rhythm)"),
    (("add some space", "add more space", "more space", "add space"), "KNOWN: add 20px space"),
    (("three lines", "two lines", "one line", "fit within"), "KNOWN: line wrapping per Figma"),
    (("incorrect mlp content", "wrong content", "correct one"), "KNOWN: check the content doc (right model/dealer)"),
    (("duplicate", "twice", "repeated"), "KNOWN: remove the duplicate"),
    (("disclaimer",), "KNOWN: disclaimer wording/format"),
    (("link", "cta", "button"), "check: links/buttons (dealer's own site, new tab)"),
]


def split_points(text):
    t = re.sub(r"\s+", " ", text).strip()
    t = re.sub(r"^.*?revision from .*? at \d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}\S*\s*", "", t)
    t = re.sub(r"^Hello\s+@[^-]+-\s*", "", t, flags=re.I)
    t = re.sub(r"\s*(Thank you!?|Thanks!?)\s*(cc\s.*)?$", "", t, flags=re.I)
    ps = ""
    m = re.search(r"\bPS:\s*(.*)$", t)
    if m:
        ps, t = m.group(1).strip(), t[:m.start()].strip()
    parts = re.split(r"\s(?=\d{1,2}\.\s)", " " + t)
    pts = [re.sub(r"^\d{1,2}\.\s*", "", p).strip(" .") for p in parts if p.strip()]
    return pts, ps


def label(point):
    low = point.lower()
    for keys, lab in RULES:
        if any(k in low for k in keys):
            return lab
    return "NEW: not in the QA list yet - add it to qa_feedback.md after fixing"


def triage_text(text):
    pts, ps = split_points(text)
    return [(n, p, label(p)) for n, p in enumerate(pts, 1)], ps


def triage(rev_txt):
    rev_txt = Path(rev_txt)
    text = rev_txt.read_text(encoding="utf-8")
    items, ps = triage_text(text)
    shots = sorted(x.name for x in rev_txt.parent.glob("*.png"))
    head = text.splitlines()[0] if text else ""
    out = [f"# QA checklist - {head}", ""]
    for n, p, lab in items:
        out.append(f"- [ ] {n}. {p}\n      -> {lab}")
    if ps:
        out += ["", f"PS from QA: {ps}"]
    out += ["", "Screenshots (in QA's order): " + (", ".join(shots) or "none"),
            "Tick each point, then write what changed with: build_mlp_tracker.py --note <id> \"Revision #N done: ...\""]
    (rev_txt.parent / "checklist.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    return items


# ---------------------------------------------------------------- upload pack
def apollo_style():
    import importlib.util
    sp = importlib.util.spec_from_file_location("apollo_style", str(Path(settings.get("toolkit_root")) / "tools" / "apollo_style.py"))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def is_apollo(proj):
    """Apollo CMS page? project.json "cms", else the tracker's platform for this folder / dealer (monday CMS list)."""
    try:
        pj = json.load(open(proj / "project.json", encoding="utf-8"))
        if "apollo" in str(pj.get("cms") or "").lower():
            return True
        dealer = pj.get("dealer")
    except (OSError, ValueError):
        dealer = None
    try:
        st = json.load(open(HERE / "tracker_state.json", encoding="utf-8"))
        for i in st.get("items", []):
            if (i.get("folder") and Path(i["folder"]) == proj) or (dealer and i.get("dealer") == dealer):
                if str(i.get("platform") or "").lower().startswith("apollo"):
                    return True
    except (OSError, ValueError):
        pass
    return False


CODE_LABEL = {".html": "HTML", ".css": "CSS", ".js": "JS"}


def _keep_baseline(proj, out):
    """What is in the CMS now = the paste files of the pack QA reviewed. When a new revision folder appears, the old pack's
    paste files are kept in qa/cms-baseline/ (tagged with that revision), so later packs for the same revision compare
    against what is live, not against an unposted rebuild."""
    revs = sorted(d.name for d in (proj / "revisions").iterdir() if d.is_dir()) if (proj / "revisions").exists() else []
    if not revs:
        return None
    base, old = proj / "qa" / "cms-baseline", out / "2-paste-into-cms"
    tag = base / "_revision.txt"
    if tag.exists() and tag.read_text(encoding="utf-8").strip() == revs[-1]:
        return base
    if not old.is_dir():
        return base if base.is_dir() else None   # older baseline is the best guess left
    if base.exists():
        shutil.rmtree(base)
    shutil.copytree(old, base)
    imgs = sorted(f.name for f in (out / "1-upload-images").rglob("*") if f.is_file()) if (out / "1-upload-images").is_dir() else []
    (base / "_images.txt").write_text("\n".join(imgs), encoding="utf-8")   # images already uploaded for the reviewed version
    tag.write_text(revs[-1], encoding="utf-8")
    return base


def cms_changes(paste, base, images):
    """Per CMS field: changed (+ lines) / no change / new, for the revision note (user, 2026-11-25: "put a description in
    the revision what to put in the CMS ... if you change the HTML indicate it")."""
    import difflib
    rows = []
    known = set((base / "_images.txt").read_text(encoding="utf-8").split("\n")) if base and (base / "_images.txt").exists() else None
    n_images = len([n for n in images if n not in known]) if known is not None else len(images)
    for f in sorted(paste.glob("*.*"), key=lambda f: ({".html": 0, ".css": 1, ".js": 2}.get(f.suffix.lower(), 3), f.name)):
        lab = CODE_LABEL.get(f.suffix.lower()) or f.stem.replace("-", " ").capitalize().replace("url", "URL")
        o = base / f.name if base else None
        if not o or not o.exists():
            rows.append({"file": f.name, "label": lab, "state": "new" if base else "paste"})
            continue
        a, b = o.read_text(encoding="utf-8", errors="replace").splitlines(), f.read_text(encoding="utf-8", errors="replace").splitlines()
        if a == b:
            rows.append({"file": f.name, "label": lab, "state": "same"})
        else:
            n = sum(1 for l in difflib.unified_diff(a, b, lineterm="", n=0) if l[:1] in "+-" and not l.startswith(("+++", "---")))
            rows.append({"file": f.name, "label": lab, "state": "changed", "lines": n})
    parts = [f"{r['label']} changed ({r['lines']} line{'s' if r['lines'] != 1 else ''}) - paste it" if r["state"] == "changed"
             else f"{r['label']} new - paste it" if r["state"] == "new" else f"{r['label']} no change - skip"
             for r in rows if r["state"] != "paste"]
    parts.append(f"{n_images} new image{'s' if n_images != 1 else ''} to upload" if n_images else "no new images")
    line = ("CMS: " + " | ".join(parts)) if base else ""
    if base and not any(r["state"] in ("changed", "new") for r in rows):
        line += " (nothing to paste)"
    return {"revision": bool(base), "fields": rows, "images": n_images, "line": line}


def pack(project):
    proj = Path(project)
    out = proj / "to-post"
    base = _keep_baseline(proj, out)
    if out.exists():
        shutil.rmtree(out)
    imgs_dir = out / "1-upload-images"
    listed = None
    tu = proj / "to-upload.txt"
    if tu.exists():
        listed = [l.strip() for l in tu.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    webp = proj / "assets" / "webp"
    files = [webp / n for n in listed] if listed is not None else sorted(webp.glob("*.webp"))
    files = [f for f in files if f.exists()]
    apollo = is_apollo(proj)
    ap = apollo_style() if apollo else None
    bgs = ap.jpeg_bg(proj) if apollo else {}
    jpeg_warn = []
    for k, f in enumerate(files):
        b = imgs_dir / f"batch-{k // 8 + 1:02d}"
        b.mkdir(parents=True, exist_ok=True)
        if apollo:   # Apollo rule (user, 2026-11-20): images must be JPEG
            w = ap.to_jpeg(f, b / ap.jpeg_name(f.name), bgs.get(f.name, bgs.get("*")))
            if w:
                jpeg_warn.append(w)
        else:
            shutil.copy2(f, b / f.name)
    cms = proj / "cms-fields"
    paste = out / "2-paste-into-cms"
    paste.mkdir(parents=True, exist_ok=True)
    fields = sorted(cms.glob("*.*")) if cms.exists() else []
    for f in fields:
        shutil.copy2(f, paste / f.name)
    if apollo:   # Apollo rules (user, 2026-11-20): image names -> .jpg, and the style inside a <script> (no bare <style>)
        for f in paste.glob("*.html"):
            t = f.read_text(encoding="utf-8")
            w = ap.wrap(ap.jpeg_html(t))
            if ap.has_bare_style(w) or ap.non_jpeg_refs(w):
                raise SystemExit(f"Apollo check failed in {f.name}: bare <style> or not-JPEG image {ap.non_jpeg_refs(w)[:5]}")
            if w != t:
                f.write_text(w, encoding="utf-8")
                (cms / f.name).write_text(w, encoding="utf-8")   # keep cms-fields the same as what gets pasted
    note = proj / "ready-for-review.txt"
    if note.exists():
        shutil.copy2(note, out / "3-post-on-monday.txt")
    ba = proj / "before-after"
    if ba.exists():
        shutil.copytree(ba, out / "4-before-after")
    code = [f for f in fields if f.suffix in (".html", ".css", ".js")]   # page-url.txt etc. are not CMS fields
    one_file = len(code) == 1
    steps = [f"UPLOAD PACK - {proj.name}  ({datetime.now():%Y-%m-%d %H:%M})", ""]
    if files:
        nb = (len(files) + 7) // 8
        steps.append(f"1. Upload {len(files)} image{'s' if len(files) != 1 else ''} from 1-upload-images, one batch folder at a time ({nb} batch{'es' if nb != 1 else ''} of up to 8).")
        steps.append("   If one fails: delete the half-made entry in the media library first, upload it alone, then tell Claude.")
    else:
        steps.append("1. No new images to upload.")
    if one_file:
        steps.append(f"2. Paste 2-paste-into-cms/{code[0].name} into the page (Text/HTML view).")
    elif code:
        steps.append("2. Paste the 3 fields from 2-paste-into-cms: " + ", ".join(f.name for f in code) + " (HTML into HTML, CSS into CSS, JS into JS).")
    if (cms / "page-url.txt").exists():
        steps.append("   Page URL (page settings): " + (cms / "page-url.txt").read_text(encoding="utf-8").strip())
    revs = sorted((d.name for d in (proj / "revisions").iterdir() if d.is_dir()), reverse=True) if (proj / "revisions").exists() else []
    newest_day = revs[0][:10] if revs else ""
    mobile_rev = any(r.startswith(newest_day) and r.endswith("Final-Mobile-Check") for r in revs)   # Final mobile check (2026-11-16)
    if note.exists():
        where = "Final MLP and Final Mobile Check subitems" if mobile_rev else "Final MLP subitem"
        try:   # Final MLP already approved, only the Final Mobile Check is open (2026-11-16)
            st = json.load(open(HERE / "tracker_state.json", encoding="utf-8"))
            if any(i.get("mobile_only") and Path(i.get("folder") or "-") == proj for i in st.get("items", [])):
                where = "Final Mobile Check subitem (the Final MLP is already approved)"
        except (OSError, ValueError):
            pass
        steps.append(f"3. Post 3-post-on-monday.txt as the update on the {where}" + (" and attach the images in 4-before-after." if ba.exists() else "."))
    steps.append("4. Set monday to Waiting for Review.")
    if apollo:
        steps.insert(1, "Apollo: the images are JPEG (.jpg) and the style is inside a <script> - upload and paste them as they are.")
        steps += [""] + ["CHECK: " + w for w in jpeg_warn]
        for w in jpeg_warn:
            print("WARNING", w)
    ch = cms_changes(paste, base, [f.name for f in imgs_dir.rglob("*") if f.is_file()] if imgs_dir.is_dir() else [])
    (out / "cms-changes.json").write_text(json.dumps(ch, indent=1), encoding="utf-8")
    if ch["line"]:
        steps[1:1] = ["", "WHAT TO CHANGE IN THE CMS (this revision vs the version QA reviewed):", "  " + ch["line"], ""]
        print(ch["line"])
    (out / "README.txt").write_text("\n".join(steps) + "\n", encoding="utf-8")
    return out, len(files), one_file


# ---------------------------------------------------------------- dealer base
CTA = ("View Inventory", "Get A Quote", "Get a Quote", "Value Your Trade", "Get Pre-Approved", "Get Pre-Qualified", "Schedule Service", "Order Parts")


def dealer_base(dealer):
    cfg = json.load(open(HERE / "project_folders.json", encoding="utf-8"))
    cands = [Path(e["folder"]) for e in cfg["projects"] if e["dealer"].lower() == dealer.lower() and Path(e["folder"]).exists()]
    cands = [c for c in cands if (c / "cms-fields").exists()]
    if not cands:
        return None
    best = max(cands, key=lambda c: max(f.stat().st_mtime for f in (c / "cms-fields").glob("*.*")))
    html = "\n".join(f.read_text(encoding="utf-8", errors="ignore") for f in (best / "cms-fields").glob("*.html"))
    css = "\n".join(f.read_text(encoding="utf-8", errors="ignore") for f in (best / "cms-fields").glob("*.css")) or html
    fonts = re.findall(r"family=([A-Za-z+]+)", html)
    if not fonts:   # one-file pages: take the font-family names used in the CSS
        fonts = [f for f in re.findall(r"""font-family:\s*["']?([A-Za-z][A-Za-z0-9 ]+)""", css) if f.lower() not in ("inherit", "arial", "helvetica", "sans-serif") and not f.startswith("var")]
    links = {}
    for href, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        t = re.sub(r"<[^>]+>|&[a-z]+;|\s+", " ", txt).strip()
        for c in CTA:
            if t.lower().startswith(c.lower()) and c.title() not in links:
                links[c.title()] = href.replace("&amp;", "&")
    cdn = re.findall(r"(https://[^\"')\s]+/uploads/\d{4}/\d{2}/)", html)
    colours = re.findall(r"--[\w-]+:\s*(#[0-9a-fA-F]{3,6})", css)
    base = {"dealer": dealer, "from_project": str(best), "fonts": sorted(set(f.replace("+", " ") for f in fonts)),
            "cta_links": links, "cdn": cdn[0] if cdn else None, "colours": list(dict.fromkeys(colours))[:8],
            "platform_files": len(list((best / "cms-fields").glob("*.*")))}
    return base


# ---------------------------------------------------------------- intake
def parse_brief(updates):
    """updates: monday updates (with HTML body), any order. Reads the build brief (the post with a Figma link):
    only VISIBLE links count - briefs carry hidden, empty <a> leftovers from editing (Durango's pointed to the Cherokee Figma)."""
    brief = {"figma": None, "content_doc": None, "landing_url": None, "links": {}, "meta_title": None, "meta_description": None,
             "warnings": [], "source_update": None}
    vis = lambda h: [(a, re.sub(r"<[^>]+>|\ufeff|\s+", " ", t).strip()) for a, t in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', h, re.S)
                     if re.sub(r"<[^>]+>|\ufeff|\s", "", t)]
    for u in sorted(updates, key=lambda x: x.get("created_at") or ""):
        body = (u.get("body") or "").replace("&amp;", "&")
        if "figma.com" not in body or brief["figma"]:
            continue
        brief["source_update"] = u.get("id")
        blocks = re.split(r"</p>|<br\s*/?>", body)
        for k, b in enumerate(blocks):
            text = re.sub(r"<[^>]+>|\ufeff", " ", b)
            text = re.sub(r"\s+", " ", text).strip()
            links = [a for a, t in vis(b) if "monday.com/users" not in a]
            lab = re.match(r"([A-Za-z0-9 &'/().-]{2,60}?)\s*:", text)
            lab = lab.group(1).strip() if lab else ""
            if re.match(r"(?i)^(https?|button links?|links?)$", lab):
                lab = ""
            nxt_lab = re.match(r"\s*([A-Za-z0-9 &'/().-]{2,60}?)\s*:", re.sub(r"<[^>]+>|﻿", " ", blocks[k + 1]) if k + 1 < len(blocks) else "")
            if not links and lab and k + 1 < len(blocks) and not (nxt_lab and not nxt_lab.group(1).lower().startswith("http")):          # label line, link on the next block
                links = [a for a, t in vis(blocks[k + 1]) if "monday.com/users" not in a]
            for a in links:
                if "figma.com" in a and not brief["figma"]:
                    brief["figma"] = a
                elif re.search(r"docs\.google\.com/document|drive\.google\.com/file", a) and not brief["content_doc"]:
                    brief["content_doc"] = a
            if not links:
                if lab.lower().startswith("meta title"):
                    brief["meta_title"] = text.split(":", 1)[1].strip()
                elif lab.lower().startswith("meta description"):
                    brief["meta_description"] = text.split(":", 1)[1].strip()
                continue
            if lab and not re.search(r"figma|content|structure|url", lab, re.I):
                brief["links"].setdefault(lab.title() if lab.isupper() else lab, links[0])
            elif re.search(r"structure|url of the landing", lab + " " + text, re.I) and not brief["landing_url"]:
                brief["landing_url"] = links[0]
        if not brief["landing_url"]:
            m = re.search(r"Structure of the URL[^<]*</p>\s*<a[^>]+href=\"([^\"]+)\"", body)
            brief["landing_url"] = m.group(1) if m else None
    host = re.sub(r"^https?://(www\.)?", "", brief["landing_url"] or "").split("/")[0]
    for k, v in brief["links"].items():
        h = re.sub(r"^https?://(www\.)?", "", v).split("/")[0]
        if host and h != host:
            brief["warnings"].append(f"{k} points to {h}, not {host} - use the dealer's own page (rule 2026-11-10)")
    return brief


def intake(updates_file, dealer, mlp):
    data = json.load(open(updates_file, encoding="utf-8"))
    data = data.get("data", data)
    ups = []
    for it in data.get("items", []):
        ups += it.get("updates") or []
    brief = parse_brief(ups)
    folder = MLP_ROOT / dealer / f"{mlp}, {dealer}"
    folder.mkdir(parents=True, exist_ok=True)
    base = dealer_base(dealer)
    if base:
        brief["dealer_base"] = base
        for k, v in base["cta_links"].items():      # fill missing CTA links from the dealer's last page, marked as such
            brief["links"].setdefault(k, v)
            brief.setdefault("links_from_last_page", []).append(k) if k not in brief["links"] or brief["links"][k] == v else None
    brief["intake_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    (folder / "brief.json").write_text(json.dumps(brief, indent=1, ensure_ascii=False), encoding="utf-8")
    cfg = json.load(open(HERE / "project_folders.json", encoding="utf-8"))
    if not any(e["dealer"] == dealer and e["mlp"] == mlp for e in cfg["projects"]):
        cfg["projects"].append({"dealer": dealer, "mlp": mlp, "folder": str(folder), "status": "Assigned"})
        json.dump(cfg, open(HERE / "project_folders.json", "w", encoding="utf-8"), indent=1)
    return folder, brief


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "pack":
        out, n, one = pack(sys.argv[2])
        print(f"{out}  ({n} images, {'1 page file' if one else 'CMS fields'})")
    elif cmd == "triage":
        for n, p, lab in triage(sys.argv[2]):
            print(f"{n}. {p[:90]}\n   -> {lab}")
    elif cmd == "dealer":
        print(json.dumps(dealer_base(sys.argv[2]), indent=1, ensure_ascii=False))
    elif cmd == "intake":
        f, b = intake(sys.argv[2], sys.argv[3], sys.argv[4])
        print(f, json.dumps({k: b[k] for k in ("figma", "content_doc", "links")}, indent=1))
    else:
        print(__doc__)
