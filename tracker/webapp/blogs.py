"""Blogs tab (user, 2026-11-17): the blog folders grouped under the dealerships assigned to you for blogs.

Blogs live in one folder each under the blogs folder (default D:/WORK FOLDER/Blogs): cms.html + preview.html + images/.
A blog belongs to a dealer when its cms.html links to the dealer's website (domains in blog_dealers.json),
or, for a dealer with no domain yet, when the dealer's name is in the blog title or the cms.html text.
The dealer list is ../blog_dealers.json (edit it when the assignment changes). Read-only: nothing here changes a file.
"""
import json
import os
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "blog_dealers.json"
DEFAULT_DIR = r"D:\WORK FOLDER\Blogs"
LINK = re.compile(r"https?://(?:www\.)?([a-z0-9.-]+)", re.I)


def config():
    try:
        c = json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        c = {}
    c.setdefault("folder", DEFAULT_DIR)
    c.setdefault("dealers", [])
    return c


def _key(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _blog(path):
    cms = path / "cms.html"
    text = cms.read_text(encoding="utf-8", errors="ignore") if cms.is_file() else ""
    hosts = {}
    for h in LINK.findall(text):
        h = h.lower()
        if "dealerinspire" in h or "dealer.com" in h or "amazonaws" in h or "youtube" in h or "google" in h:
            continue   # image hosts / embeds, not the dealer's own site
        hosts[h] = hosts.get(h, 0) + 1
    files = [f for f in (path / "images").glob("*") if f.is_file()] if (path / "images").is_dir() else []
    times = [f.stat().st_mtime for f in path.glob("*") if f.is_file()] or [path.stat().st_mtime]
    title = re.sub(r"\s+", " ", path.name).strip()
    half = len(title) // 2
    if len(title) % 2 == 0 and title[:half] == title[half:]:
        title = title[:half]   # folder name pasted twice ("...SUV!2027 Audi Q3...SUV!")
    return {"name": path.name, "title": title,
            "hosts": sorted(hosts, key=lambda h: -hosts[h]), "text": _key(re.sub(r"<[^>]+>", " ", text)),
            "has_cms": cms.is_file(), "has_preview": (path / "preview.html").is_file(), "images": len(files),
            "changed": datetime.fromtimestamp(max(times)).strftime("%Y-%m-%d %H:%M")}


def _match(b, dealers):
    for i, d in enumerate(dealers):   # 1) the dealer's own website is linked most in the blog
        doms = [x.lower().removeprefix("www.") for x in d.get("domains", [])]
        if b["hosts"] and b["hosts"][0] in doms:
            return i
    for i, d in enumerate(dealers):   # 2) any of its websites linked
        doms = [x.lower().removeprefix("www.") for x in d.get("domains", [])]
        if any(h in doms for h in b["hosts"]):
            return i
    title = _key(b["title"])
    for i, d in enumerate(dealers):   # 3) the dealer's name in the title or the blog text
        names = [_key(n) for n in [d["name"]] + d.get("aliases", [])]
        if any(n and (n in title or n in b["text"]) for n in names):
            return i
    return None


# ---- monday links (user, 2026-11-17: "a button where it will direct me to the monday location") ----
# Blogs are subitems on one board per dealer in the "Content Team Workspace" (monday_workspace in blog_dealers.json).
# Read-only, cached in blog_monday.json for 30 minutes (Refresh on the tab reads monday again).
MCACHE = HERE / "blog_monday.json"
# columns of the blog boards (same template on every dealer board)
COLS = {"status": "color_mkys6rqp", "date": "date_mkysvqwz", "live": "text_mkyws26", "doc": "file_mkyxkbm6", "writer": "multiple_person_mkys9nyb"}
YOUR_TURN = ["For Web Posting"]   # the web posting step = ours (2026-11-17); change in blog_dealers.json "your_turn"
DONE = ["Published"]
MLOCK = threading.Lock()


def _gql(query):
    sys.path.insert(0, str(HERE.parent))
    import refresh_monday as rm   # read-only helper: refuses anything that is not a query
    if not rm.TOKEN:
        rm.TOKEN = rm.token()
    return rm.gql(query)


def _changed_at(cols):
    """When the Status column last changed, local time "YYYY-MM-DD HH:MM" (monday stores changed_at in UTC)."""
    try:
        v = json.loads(next(x["value"] for x in cols if x["id"] == COLS["status"]) or "{}")
        t = datetime.fromisoformat(v["changed_at"].replace("Z", "+00:00"))
        return t.astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def _monday(c, fresh=False):
    with MLOCK:
        try:
            m = json.loads(MCACHE.read_text(encoding="utf-8"))
        except Exception:
            m = {}
        ws = c.get("monday_workspace")
        if not ws or (not fresh and m.get("ws") == ws and time.time() - m.get("at", 0) < 1800):
            return m
        try:
            boards = _gql("query { account { slug } boards(workspace_ids:[%d], limit:500) { id name } }" % int(ws))
            slug = boards["account"]["slug"]
            names = {_key(n): d["name"] for d in c["dealers"] for n in [d["name"]] + d.get("aliases", []) + d.get("monday", [])}
            mine = {b["id"]: names[_key(b["name"])] for b in boards["boards"] if _key(b["name"]) in names}
            out = {"ws": ws, "at": time.time(), "slug": slug, "boards": {}, "items": []}
            ids = list(mine)
            for k in range(0, len(ids), 10):
                d = _gql('query { boards(ids:[%s]) { id items_page(limit:500) { items { subitems { id name board { id } '
                         'column_values(ids:[%s]) { id text value } } } } } }' % (",".join(ids[k:k + 10]), ",".join(f'"{v}"' for v in COLS.values())))
                for b in d["boards"]:
                    dealer = mine[b["id"]]
                    out["boards"][dealer] = f"https://{slug}.monday.com/boards/{b['id']}"
                    for it in b["items_page"]["items"]:
                        for si in it.get("subitems") or []:
                            cv = {x["id"]: x["text"] for x in si["column_values"]}
                            row = {"dealer": dealer, "name": si["name"], "key": _key(si["name"]),
                                   "url": f"https://{slug}.monday.com/boards/{si['board']['id']}/pulses/{si['id']}"}
                            row.update({k: (cv.get(v) or "").strip() for k, v in COLS.items()})
                            row["status_at"] = _changed_at(si["column_values"])   # shift summary: published this shift
                            out["items"].append(row)
            MCACHE.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
            return out
        except BaseException as e:   # no token / offline: keep the last links, say why
            m["error"] = str(e)[:160]
            return m


def _find(title, dealer, items):
    k = _key(title)
    pool = [x for x in items if x["dealer"] == dealer] or items
    for x in pool:
        if x["key"] == k:
            return x
    words = set(k.split())   # titles differ a little (":" "?" dropped in folder names)
    best, score = None, 0.0
    for x in pool:
        w = set(x["key"].split())
        s = len(words & w) / max(len(words | w), 1)
        if s > score:
            best, score = x, s
    return best if score >= 0.75 else None


def blogs_by_dealer(fresh=False):
    c = config()
    root = Path(c["folder"])
    dealers = c["dealers"]
    out = [{"name": d["name"], "cms": d.get("cms", ""), "blogs": []} for d in dealers]
    other = []
    if root.is_dir():
        for p in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if not p.is_dir() or p.name.startswith((".", "_")):
                continue
            b = _blog(p)
            i = _match(b, dealers)
            site = b["hosts"][0] if b["hosts"] else ""
            row = {k: b[k] for k in ("name", "title", "has_cms", "has_preview", "images", "changed")} | {"site": site}
            (out[i]["blogs"] if i is not None else other).append(row)
    for d in out:
        d["blogs"].sort(key=lambda r: r["changed"], reverse=True)
    other.sort(key=lambda r: r["changed"], reverse=True)
    m = _monday(c, fresh)
    turn = c.get("your_turn") or YOUR_TURN
    pick = lambda x: {k: x.get(k, "") for k in ("name", "url", "status", "date", "live", "doc", "writer")}
    yours = 0
    for d in out:
        d["monday"] = (m.get("boards") or {}).get(d["name"], "")
        mine = [x for x in m.get("items") or [] if x["dealer"] == d["name"]]
        used = set()
        for b in d["blogs"]:   # built blogs (a folder in the Blogs folder) + their monday item
            x = _find(b["title"], d["name"], mine)
            if x:
                used.add(x["url"])
                b.update(monday=x["url"], status=x["status"], pub=x["date"], live=x.get("live", ""), doc=x.get("doc", ""))
            else:
                b["nomatch"] = bool(m.get("items"))
            b["turn"] = b.get("status") in turn
        rest = [pick(x) for x in mine if x["url"] not in used]   # on monday, no folder yet
        for x in rest:
            x["turn"] = x["status"] in turn
        d["upcoming"] = sorted([x for x in rest if x["status"] not in DONE], key=lambda x: (not x["turn"], x["date"] or "9999"))
        d["published"] = sorted([x for x in rest if x["status"] in DONE], key=lambda x: x["date"], reverse=True)
        d["total"] = len(d["blogs"]) + len(rest)
        yours += sum(1 for x in d["blogs"] + d["upcoming"] if x.get("turn"))
    return {"folder": str(root), "found": root.is_dir(), "dealers": out, "other": other, "your_turn": yours,
            "turn_labels": turn, "monday_error": m.get("error", "")}


# ---- Blog check (2026-11-17): the blog rules (memory: blog-deliverable-format, blog-keep-doc-bold) on cms.html ----
def check_blog(name):
    import urllib.request
    from concurrent.futures import ThreadPoolExecutor
    f = blog_path(name)
    if not f:
        return {"error": "not found in the blogs folder"}
    out = []
    cms, prev = f / "cms.html", f / "preview.html"
    out.append("OK  preview.html" if prev.is_file() else "FIX no preview.html")
    if not cms.is_file():
        return {"ok": True, "lines": out + ["FIX no cms.html"]}
    t = cms.read_text(encoding="utf-8", errors="ignore")
    add = lambda bad, fix, ok: out.append(fix if bad else ok)
    add(re.search(r"<h1[\s>]", t, re.I), "FIX cms.html has an H1 - leave the title out (the CMS title field holds it)", "OK  no H1 (title goes in the CMS title field)")
    add(re.search(r"\n[ \t]*\n", t), "FIX blank lines in cms.html - WordPress turns them into empty paragraphs", "OK  no blank lines")
    left = re.findall(r"\[(?:IMAGE|LINK|URL|TODO|INSERT)[^\]]*\]|\bTODO\b|\bXXX\b|\{\{[^}]*\}\}|lorem ipsum", t, re.I)
    add(left, f"FIX leftover placeholders: {', '.join(sorted(set(left))[:5])}", "OK  no placeholders")
    notes = re.findall(r">\s*(Note:|Image Alt Text:)", t, re.I)
    add(notes, f"FIX writer instruction lines left in ({', '.join(sorted(set(notes)))})", "OK  no writer notes")
    imgs = re.findall(r"<img[^>]+src=[\"']([^\"']+)", t, re.I)
    local = [u for u in imgs if not u.lower().startswith("http")]
    add(local, f"FIX images with local paths (upload them and use the hosted URL): {', '.join(u.split('/')[-1] for u in local[:5])}", f"OK  {len(imgs)} images use hosted URLs")
    noalt = re.findall(r"<img(?![^>]*\balt=[\"'][^\"']+)[^>]*>", t, re.I)
    add(noalt, f"FIX {len(noalt)} image(s) without alt text", "OK  every image has alt text")
    web = [u for u in imgs if u.startswith("http")]

    def head(u):
        try:
            r = urllib.request.Request(u, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(r, timeout=10) as x:
                return u, x.status
        except Exception as e:
            return u, getattr(e, "code", 0) or str(e)[:40]
    with ThreadPoolExecutor(6) as ex:
        bad = [(u, s) for u, s in ex.map(head, web[:40]) if s != 200]
    add(bad, f"FIX {len(bad)} image(s) not loading: " + "; ".join(f"{u.split('/')[-1]} ({s})" for u, s in bad[:4]), f"OK  all {len(web)} hosted images load")
    links = re.findall(r"<a[^>]+href=[\"']([^\"']*)", t, re.I)
    badl = [h for h in links if not h or h == "#" or not re.match(r"(https?:|mailto:|tel:|/)", h)]
    add(badl, f"FIX {len(badl)} empty or broken link(s): {', '.join(h or '(empty)' for h in badl[:4])}", f"OK  {len(links)} links look right")
    strong = len(re.findall(r"<(strong|b)[\s>]", t, re.I))
    add(not strong, "CHECK no bold text - every bold run in the Google Doc must be bold (read the .docx, not plain text)", f"OK  {strong} bold runs (compare with the doc)")
    for lab in ("Also Read:", "Read Next:"):
        if lab.lower() in t.lower() and not re.search(r"<(strong|b)[^>]*>\s*" + re.escape(lab), t, re.I):
            out.append(f"FIX '{lab}' label is not bold")
    if "mercedesbenzfwb.com" in t and re.search(r"<strong>", t):
        out.append("FIX Mercedes-Benz of Fort Walton Beach: use the inline-styled <strong> (plain <strong> does not show bold there)")
    fixes = sum(1 for l in out if l.startswith("FIX"))
    out.append(f"RESULT {fixes} FIX line(s)" if fixes else "RESULT no FIX lines - ready to post")
    return {"ok": True, "lines": out}


def blog_path(name, file=None):
    """Folder (or a file in it) of one blog, only inside the blogs folder."""
    root = Path(config()["folder"]).resolve()
    p = (root / str(name or "")).resolve()
    if p.parent != root or not p.is_dir():
        return None
    if file:
        p = p / file
        return p if p.is_file() else None
    return p


def open_blog(name, what):
    if what == "vscode":   # user, 2026-11-17: "a button where it will go to the VS code project when it is built"
        import subprocess
        import features
        p = blog_path(name)
        if not p:
            return {"error": "not found in the blogs folder"}
        subprocess.Popen([features.vscode(), str(p)], creationflags=features.NOWIN,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"ok": True, "msg": f"Opening {p.name} in VS Code"}
    p = blog_path(name, {"preview": "preview.html", "cms": "cms.html"}.get(what)) if what != "folder" else blog_path(name)
    if not p:
        return {"error": "not found in the blogs folder"}
    features.plat.open_path(p)
    return {"ok": True}


def blog_html(name):
    p = blog_path(name, "cms.html")
    return {"text": p.read_text(encoding="utf-8", errors="ignore")} if p else {"error": "no cms.html in this blog folder"}


# ---- Pop-up when a blog becomes your turn (user, 2026-11-17: picks 1, 3, 4 + 2) ----
SEEN = HERE / "blog_seen.json"
WATCH_MIN = 10   # minutes between monday reads for the blog pop-up (only inside the shift window)


def turn_items(r):
    out = []
    for k, d in enumerate(r["dealers"], 1):
        for b in d["blogs"]:
            if b.get("turn") and b.get("monday"):
                out.append({"url": b["monday"], "name": b["title"], "dealer": d["name"], "no": k, "built": True})
        for x in d["upcoming"]:
            if x.get("turn"):
                out.append({"url": x["url"], "name": x["name"], "dealer": d["name"], "no": k, "built": False})
    return out


def watch_loop(features, settings):
    """Background thread (server.py): pop-up for each blog that newly reached a your-turn status."""
    last = 0.0
    while True:
        time.sleep(30)
        try:
            cfg = settings.load()
            if not settings.token() or not cfg.get("watch_enabled") or not features.in_window(cfg):
                continue
            if time.time() - last < WATCH_MIN * 60:
                continue
            last = time.time()
            r = blogs_by_dealer(fresh=True)
            if r.get("monday_error"):
                continue
            now = turn_items(r)
            try:
                seen = json.loads(SEEN.read_text(encoding="utf-8"))
            except Exception:
                seen = None
            SEEN.write_text(json.dumps({"urls": [x["url"] for x in now], "at": time.strftime("%Y-%m-%d %H:%M:%S")}), encoding="utf-8")
            if seen is None:
                continue   # first run: remember what is already your turn, no pop-up storm
            new = [x for x in now if x["url"] not in set(seen.get("urls", []))]
            if len(new) == 1:
                x = new[0]
                features.toast(f"Blog ready for you: {x['dealer']}", x["name"] + (" - built, ready to post" if x["built"] else " - click Build it"), f"blogs={x['no']}")
            elif new:
                features.toast(f"{len(new)} blogs ready for you", "; ".join(f"{x['dealer']}: {x['name']}" for x in new)[:280], "blogs")
        except Exception:
            pass


# ---- "Build it" (Claude builds the blog from its Google Doc) ----
def folder_name(title):
    return re.sub(r"\s+", " ", re.sub(r'[<>:"/\|?*]', "", title)).strip().rstrip(".")


def build_prompt(url):
    try:
        m = json.loads(MCACHE.read_text(encoding="utf-8"))
    except Exception:
        return None, None
    x = next((i for i in m.get("items", []) if i["url"] == url), None)
    if not x:
        return None, None
    c = config()
    folder = Path(c["folder"]) / folder_name(x["name"])
    home = Path.home()
    same = [p.name for p in Path(c["folder"]).iterdir() if p.is_dir()] if Path(c["folder"]).is_dir() else []
    name = f"{x['dealer']} - {x['name']}"
    return name, (
        f"blog  (sent from the Web Dev Tracker 'Build it' button). Build ONE dealer blog post: '{x['name']}' for {x['dealer']} "
        f"(monday item {url}, status {x['status']}, publication date {x.get('date') or '-'}). Source Google Doc: {x.get('doc') or 'MISSING - stop and report it'}.\n"
        f"Folder: {folder} (create it). Deliver exactly as the user's blog rules say:\n"
        "- preview.html (full page, local image paths) and cms.html (body only, hosted image URLs, no blank lines, no H1 - "
        "the CMS title field holds the title). No other HTML files.\n"
        "- Every bold run in the doc must be bold: download the .docx (Google Drive download_file_content) and read the bold "
        "runs from word/document.xml - the plain-text reader drops bold. Include 'Also Read:' / 'Read Next:' labels. Skip the "
        "writer instruction lines ('Note:', 'Image Alt Text:'), but use the Image Alt Text lines as the images' alt text.\n"
        "- Images: take them from the .docx (word/media) or from images/original if the user put them there; save originals in "
        "images/original and upload-ready WebP (max 1920x1080) in images/webp.\n"
        f"- Hosted image URLs: copy the upload URL pattern from another built blog of {x['dealer']} in {c['folder']} (its cms.html), "
        f"or from the *media-url.md memory files under {home / '.claude' / 'projects'} (folders named d--WORK-FOLDER-Blogs-*). "
        "Use this month's upload path and the WebP file names.\n"
        f"- Follow the CMS format rules in {home / '.claude' / 'memory' / 'topics' / 'wordpress-deployment-format.md'} and "
        f"{home / '.claude' / 'projects' / 'd--WORK-FOLDER' / 'memory' / 'projects' / 'Blog Template'} (cms-formats.md) and "
        "any dealer quirk in the memory files (e.g. Mercedes-Benz of Fort Walton Beach needs the inline-styled <strong>).\n"
        f"Then run the blog check: python -I \"{HERE / 'blogs.py'}\" check \"{folder.name}\" - fix every FIX line and run it "
        "again until there are none. monday is READ-ONLY. No questions to the user - decide by these rules and say what you "
        f"decided in the report. Report progress with: python progress.py '{name}' '<step>' '<n>/5' (steps: Reading the doc, "
        "Images, Building HTML, Blog check, Done). Finish with a short plain report: folder, image count, check result, anything "
        f"the user must do (upload the images in images/webp before pasting cms.html). Existing blog folders: {', '.join(same[:40])}.")


if __name__ == "__main__":   # python blogs.py check "<blog folder name>"
    if len(sys.argv) >= 3 and sys.argv[1] == "check":
        r = check_blog(sys.argv[2])
        print("\n".join(r.get("lines") or [r.get("error", "?")]))
