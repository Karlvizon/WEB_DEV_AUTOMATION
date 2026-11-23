"""Refresh the MLP tracker straight from monday - no Claude run, no tokens (user, 2026-11-13: "lets do number 1").

Does REFRESH.md steps 1-5 in Python with the user's own monday API token, READ-ONLY:
  1  subitem boards of the Main workspace      2  the owner's Final MLP + City Page subitems
  2b updates on those subitems (revisions)      3  mlp_data.json (+ approved list)   3b CMS list when a dealer is missing
  intake for new Assigned MLPs (brief.json; Figma / content doc are opened on "start")
  4  build_mlp_tracker.py                       4c project_folders.json status + cleanup_approved.py --delete
  5  short report, logged with summary.py --log

Token: environment variable MONDAY_API_TOKEN, or the file %APPDATA%\\MLP Tracker\\monday_token.txt (one line).
The token is only sent to api.monday.com. Every request is a query - mutations are refused before sending.

Usage: python refresh_monday.py            (full refresh)
       python refresh_monday.py --check    (only test the token: prints whose token it is)
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "mlp_data.json"
API = "https://api.monday.com/v2"
WORKSPACE = 4849162
CMS_BOARD = 18392876953
SKIP = ("Admin", "Content", "SEO", "Account Management", "Dealer Login", "GA4", "Looker", "Mailing",
        "SEO Implementation", "November", "Monthly Report", "DL Board Template")
PY = sys.executable
sys.path.insert(0, str(Path(__file__).resolve().parent))   # -I drops the script folder from sys.path
import settings  # noqa: E402  (tracker_config.json, Settings tab)
TOKEN_FILE = settings.TOKEN_FILE


def token():
    t = settings.token()
    if not t:
        sys.exit(f"No monday token. Put it in {TOKEN_FILE} (one line) - monday: profile picture > Developers > My access tokens.")
    return t


TOKEN = None


def gql(query, variables=None, tries=4):
    """One READ-ONLY monday query. Refuses anything that is not a query."""
    q = query.strip()
    if re.search(r"\bmutation\b", q, re.I) or not (q.startswith("{") or q.startswith("query")):
        raise RuntimeError("refresh_monday.py only reads monday - refused a non-query request")
    body = json.dumps({"query": q, "variables": variables or {}}).encode("utf-8")
    for n in range(tries):
        req = urllib.request.Request(API, data=body, method="POST", headers={
            "Authorization": TOKEN, "Content-Type": "application/json", "API-Version": "2025-04"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                out = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                sys.exit("monday refused the token (401). Check monday_token.txt.")
            if e.code in (429, 500, 502, 503, 504) and n < tries - 1:
                time.sleep(10 * (n + 1))
                continue
            raise
        errs = out.get("errors") or []
        if errs:
            wait = max([(e.get("extensions") or {}).get("retry_in_seconds") or 0 for e in errs] + [0])
            if n < tries - 1 and (wait or any("complexity" in str(e).lower() or "rate" in str(e).lower() for e in errs)):
                time.sleep(min(60, wait or 15))
                continue
            raise RuntimeError(f"monday error: {json.dumps(errs)[:400]}")
        return out["data"]
    raise RuntimeError("monday did not answer")


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def link_url(text):
    text = (text or "").strip()
    m = re.search(r"https?://\S+", text)      # "Title, City | Dealer - https://..." -> the URL
    if m:
        return m.group(0)
    if " - " in text:
        return text.split(" - ", 1)[1].strip()
    return text


# ---------------------------------------------------------------- steps 1 + 2
def signature():
    """Cheap change check for auto-update (user, 2026-11-13: "update if it was updated on monday").
    ONE monday call (A3 = Pro plan: 10,000 calls a day for the whole account): every subitem under the parent items of
    your open pages (Final MLP, Final Mobile Check, city pages...) with its last-change time and newest comments/replies.
    Same answer = nothing changed on your pages. New assignments elsewhere are caught by the full refresh every 30 min."""
    import hashlib
    try:
        parents = sorted({int(i["item_id"]) for i in json.load(open(DATA, encoding="utf-8")).get("items", []) if i.get("item_id")})
    except (OSError, ValueError):
        parents = []
    if not parents:
        return {"sig": "none", "subitems": 0}
    d = gql("query($ids:[ID!]) { items(ids:$ids, limit:100) { id subitems { id updated_at updates(limit:3) { id updated_at } } } }",
            {"ids": [str(p) for p in parents]})
    parts = []
    for it in d["items"]:
        for sub in it.get("subitems") or []:
            parts.append(f'{sub["id"]}:{sub["updated_at"]}:' + ",".join(f'{u["id"]}@{u["updated_at"]}' for u in sub.get("updates") or []))
    new = new_assignments()
    parts += [f"new:{i}" for i in new]   # a page assigned to you that the tracker doesn't know yet -> full refresh now
    parts.sort()
    return {"sig": hashlib.sha1("|".join(parts).encode()).hexdigest(), "subitems": len(parts), "new": new}


BOARDS_CACHE = HERE / "webapp" / "subitem_boards.json"


def new_assignments(minutes=20):
    """New assignments within about 2 minutes (user, 2026-11-19: "can we make the update live?" - Mulberry, FL waited
    for the 30-minute full check). ONE monday call: the activity log of every dealer's subitem board for the last
    `minutes`; "add_owner" events for the owner = a subitem was just assigned to you. Returns the ids the
    tracker doesn't know yet (not in assigned.json / mlp_data.json). Never raises: the normal check must keep working."""
    try:
        boards = json.loads(BOARDS_CACHE.read_text(encoding="utf-8"))
        owner = str(int(settings.get("owner_id") or 0))
        if not boards or owner == "0":
            return []
        known = set()
        try:
            for p in json.load(open(HERE / "webapp" / "assigned.json", encoding="utf-8")).get("projects", []):
                known |= {int(s["subitem_id"]) for s in p.get("subitems", [])}
        except (OSError, ValueError, KeyError):
            pass
        try:
            d = json.load(open(DATA, encoding="utf-8"))
            known |= {int(i["subitem_id"]) for k in ("items", "approved") for i in d.get(k, []) if i.get("subitem_id")}
        except (OSError, ValueError):
            pass
        since = datetime.fromtimestamp(time.time() - minutes * 60, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = gql('query($ids:[ID!], $f:ISO8601DateTime) { boards(ids:$ids, limit:100) { activity_logs(from:$f, limit:100) '
                '{ event data } } }', {"ids": boards, "f": since})
        new = set()
        for b in r["boards"]:
            for a in b.get("activity_logs") or []:
                if a.get("event") != "add_owner":   # the assignment itself ("subscribe" also happens on mentions)
                    continue
                data = json.loads(a.get("data") or "{}")
                pid = data.get("pulse_id") or data.get("item_id")
                if str(data.get("subscribed_id")) == owner and pid and int(pid) not in known:
                    new.add(int(pid))
        return sorted(new)
    except Exception:
        return []


def subitem_boards():
    d = gql("query($w:[ID!]) { boards(workspace_ids:$w, limit:500) { id name } }", {"w": [int(settings.get("workspace_id"))]})
    skip = settings.get("skip_boards") or SKIP
    out = []
    for b in d["boards"]:
        n = b["name"]
        if n.startswith("Subitems of ") and not any(s.lower() in n.lower() for s in skip):
            out.append(b["id"])
    try:   # the 2-minute check reads this list instead of asking monday for it again
        BOARDS_CACHE.write_text(json.dumps(out), encoding="utf-8")
    except OSError:
        pass
    return out


ITEM_FIELDS = '''id name parent_item { id name board { id name } }
  column_values(ids:["status","date0","date_mkyp4bky","link_mkypndq6"]) { id text }'''


def owner_subitems(boards, owner_id):
    rules = '[{column_id:"person", compare_value:["person-%d"], operator:any_of}]' % owner_id
    found = []
    for ids in chunks(boards, 25):
        d = gql('query($ids:[ID!]) { boards(ids:$ids, limit:100) { id items_page(limit:200, query_params:{rules:%s}) '
                '{ cursor items { %s } } } }' % (rules, ITEM_FIELDS), {"ids": ids})
        for b in d["boards"]:
            page = b["items_page"]
            found += page["items"]
            cur = page.get("cursor")
            while cur:
                nx = gql('query($c:String!) { next_items_page(limit:200, cursor:$c) { cursor items { %s } } }' % ITEM_FIELDS, {"c": cur})
                found += nx["next_items_page"]["items"]
                cur = nx["next_items_page"].get("cursor")
    return found


def to_record(it):
    p = it.get("parent_item") or {}
    pname = (p.get("name") or "").strip()
    # a city page = parent named "City Pages" OR a subitem named after a place ("Orlando, FL", "Kansas City, MO/KS").
    # 2026-11-20: One Legacy Motors' city pages sit under "Month 3-4 - We Buy Page [NOV-DEC]" and were skipped.
    city = "city page" in pname.lower() or bool(re.search(r",\s*[A-Z]{2}\b", it.get("name") or ""))
    if not city and "final mlp" not in (it.get("name") or "").lower():
        return None
    cv = {c["id"]: c.get("text") or "" for c in it.get("column_values") or []}
    rec = {"subitem_id": int(it["id"]), "dealer": (p.get("board") or {}).get("name", "").strip(),
           "board_id": int((p.get("board") or {}).get("id") or 0), "item_id": int(p.get("id") or 0),
           "mlp": (it["name"].strip() if city else pname), "status": cv.get("status") or "",
           "assigned": cv.get("date0") or None, "due": cv.get("date_mkyp4bky") or None,
           "live_url": link_url(cv.get("link_mkypndq6")), "type": "City Page" if city else "MLP"}
    return rec


SIDE_TASKS = ("final mlp", "final mobile check", "metatags & metadata", "seo review", "site live")


def save_unplaced(raw):
    """Never drop an assignment silently (user, 2026-11-20 #1 - One Legacy Motors' 6 city pages were missing because
    their parent was not named "City Pages"). Every subitem assigned to the owner that is NOT a tracker page and NOT one
    of the known side tasks, and not Approved yet, goes to webapp/unplaced.json -> one amber line in the tracker."""
    out = []
    for it in raw:
        name = (it.get("name") or "").strip()
        cv = {c["id"]: c.get("text") or "" for c in it.get("column_values") or []}
        status = (cv.get("status") or "").strip()
        if to_record(it) or name.lower() in SIDE_TASKS or status == "Approved":
            continue
        p = it.get("parent_item") or {}
        out.append({"subitem_id": int(it["id"]), "name": name, "status": status or "-", "parent": (p.get("name") or "").strip(),
                    "item_id": int(p.get("id") or 0), "dealer": ((p.get("board") or {}).get("name") or "").strip(),
                    "board_id": int((p.get("board") or {}).get("id") or 0)})
    out = list({u["subitem_id"]: u for u in out}.values())
    f = HERE / "webapp" / "unplaced.json"
    json.dump({"checked_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "items": out},
              open(f.with_suffix(".tmp"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    os.replace(f.with_suffix(".tmp"), f)
    if out:
        print(f"  {len(out)} assigned task(s) the tracker could not place: " + "; ".join(f"{u['dealer']} - {u['name']}" for u in out))


def save_assigned(raw):
    """Assigned tab (user, 2026-11-18: "add a tab for assigned projects even the projects that is not done yet or claude
    is not working for it yet"): EVERY subitem assigned to the owner (Final MLP, Final Mobile Check, Metatags & Metadata,
    SEO Review, Site Live, city pages...), grouped by project. Same data as the full refresh - no extra monday call."""
    projects = {}
    for it in raw:
        p = it.get("parent_item") or {}
        if not p.get("id"):
            continue
        cv = {c["id"]: c.get("text") or "" for c in it.get("column_values") or []}
        pr = projects.setdefault(p["id"], {"item_id": int(p["id"]), "project": (p.get("name") or "").strip(),
                                           "dealer": (p.get("board") or {}).get("name", "").strip(),
                                           "board_id": int((p.get("board") or {}).get("id") or 0), "subitems": []})
        if any(s["subitem_id"] == int(it["id"]) for s in pr["subitems"]):
            continue
        pr["subitems"].append({"subitem_id": int(it["id"]), "name": (it.get("name") or "").strip(),
                               "status": (cv.get("status") or "").strip(), "assigned": cv.get("date0") or None,
                               "due": cv.get("date_mkyp4bky") or None})
    out = {"refreshed_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "projects": list(projects.values())}
    f = HERE / "webapp" / "assigned.json"
    json.dump(out, open(f.with_suffix(".tmp"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    os.replace(f.with_suffix(".tmp"), f)


# ---------------------------------------------------------------- step 2b
UPD = '''updates(limit:15) { id created_at creator { id name } text_body assets { id name public_url }
  replies { id created_at creator { id name } text_body } }'''


def parent_updates(parent_ids):
    items = []
    for ids in chunks(sorted(set(parent_ids)), 10):
        d = gql('query($ids:[ID!]) { items(ids:$ids) { id subitems { id name column_values(ids:["status","person"]) { id text } %s } } }' % UPD,
                {"ids": [str(i) for i in ids]})
        items += d["items"]
    return {"items": items}


# ---------------------------------------------------------------- step 3b
def refresh_cms():
    """Dealer Login and Setup board: CMS name + CMS link (the column's URL) + the item id (= Credentials button, 2026-11-20)."""
    d = gql('query { boards(ids:[%d]) { items_page(limit:500) { items { id name column_values(ids:["link_mkzsam3e"]) { text value } } } } }' % CMS_BOARD)
    cms, links = {}, {}
    for it in d["boards"][0]["items_page"]["items"]:
        cv = it["column_values"][0] if it["column_values"] else {}
        t = (cv.get("text") or "").strip()
        try:
            url = (json.loads(cv.get("value") or "null") or {}).get("url") or ""
        except ValueError:
            url = ""
        name = it["name"].strip()
        if t:
            cms[name] = t.split(" - ", 1)[0].strip()
        links[name] = {"cms": url.strip() if url.strip().lower().startswith("http") else "", "item": str(it["id"])}
    json.dump({"source": f"monday board 'Dealer Login and Setup' ({CMS_BOARD}), column CMS (link_mkzsam3e)",
               "checked_at": date.today().isoformat(), "board": CMS_BOARD, "cms": cms, "links": links},
              open(HERE / "cms_directory.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return len(cms)


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def run(*args):
    r = subprocess.run([PY, "-I", *[str(a) for a in args]], cwd=str(HERE), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    global TOKEN
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    TOKEN = token()
    if "--signature" in sys.argv:
        print(json.dumps(signature()))
        return
    if "--check" in sys.argv:
        me = gql("{ me { id name } }")["me"]
        print(f"Token OK - monday user: {me['name']} ({me['id']})")
        return
    if "--usage" in sys.argv:            # monday API calls used today by the whole account (Settings tab)
        d = gql("{ platform_api { daily_limit { base } daily_analytics { by_day { day usage } } } }")["platform_api"]
        days = (d.get("daily_analytics") or {}).get("by_day") or []
        print(json.dumps({"limit": (d.get("daily_limit") or {}).get("base"), "days": days[:7]}))
        return
    old = json.load(open(DATA, encoding="utf-8")) if DATA.exists() else {}
    owner, owner_id = settings.get("owner_name"), int(settings.get("owner_id") or 0)
    if not owner_id:   # first refresh on this PC: the monday user of the token owns the tracker
        me = gql("{ me { id name } }")["me"]
        owner, owner_id = me["name"], int(me["id"])
        settings.save({"owner_name": owner, "owner_id": owner_id})
        print(f"First refresh: tracker owner set to {owner} ({owner_id}) from your monday token")
    t0 = time.time()
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S}  refresh (direct, read-only)")

    boards = subitem_boards()
    raw = owner_subitems(boards, owner_id)
    recs = [r for r in (to_record(i) for i in raw) if r]
    recs = list({r["subitem_id"]: r for r in recs}.values())
    # Final Mobile Check subitems (same query, no extra monday call): an MLP whose Final MLP is Approved stays in the
    # tracker while its Final Mobile Check still needs work (user, 2026-11-16: 2026 Buick Envision had a Final Mobile
    # Check revision but was dropped because the Final MLP was approved).
    fmc = {}
    for it in raw:
        if (it.get("name") or "").strip().lower() == "final mobile check" and it.get("parent_item"):
            cv = {c["id"]: c.get("text") or "" for c in it.get("column_values") or []}
            fmc[int(it["parent_item"]["id"])] = {"status": cv.get("status") or "", "id": int(it["id"])}
    print(f"  {len(boards)} dealer boards read, {len(recs)} Final MLP / city page subitems of {owner}")
    save_assigned(raw)
    save_unplaced(raw)

    old_items = {int(i["subitem_id"]): i for i in old.get("items", [])}
    old_appr = {int(a["subitem_id"]): a for a in old.get("approved", [])}
    # An MLP counts as Approved only when BOTH its Final MLP and its Final Mobile Check are Approved on monday
    # (user, 2026-11-16: "it will not be set to approved not until the Final MLP and the Final Mobile check" are approved).
    # No Final Mobile Check assigned to the owner = nothing to wait for.
    def mobile_open(r):
        f = fmc.get(r["item_id"])
        if r["type"] != "MLP" or r["status"] != "Approved" or not f:
            return None
        return f if f["status"] != "Approved" else None
    for r in recs:
        f = mobile_open(r)
        if f:
            r.update({"status": f["status"], "mobile_only": True, "final_mlp_status": "Approved", "fmc_subitem_id": f["id"]})
    items = [r for r in recs if r["status"] != "Approved"]
    approved = []
    for r in recs:
        if r["status"] != "Approved":
            continue
        a = {k: r[k] for k in ("dealer", "mlp", "subitem_id", "item_id", "board_id", "assigned", "due", "live_url")}
        prev = old_appr.get(r["subitem_id"])
        a["first_seen_approved"] = (prev or {}).get("first_seen_approved") or date.today().isoformat()
        a["approved_before_tracking"] = (prev or {}).get("approved_before_tracking", r["subitem_id"] not in old_items)
        if r["type"] == "City Page":
            a["type"] = "City Page"
        approved.append(a)
    items.sort(key=lambda i: (i["dealer"].lower(), i["type"] != "MLP", i["mlp"]))

    added = [i for i in items if i["subitem_id"] not in old_items]
    gone = [old_items[s] for s in old_items if s not in {i["subitem_id"] for i in items}]
    changed = [(old_items[i["subitem_id"]]["status"], i) for i in items
               if i["subitem_id"] in old_items and old_items[i["subitem_id"]].get("status") != i["status"]]

    data = {"owner": owner, "owner_id": owner_id, "checked_at": date.today().isoformat(),
            "items": items, "refreshed_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "approved": approved}
    tmp = DATA.with_suffix(".tmp")
    json.dump(data, open(tmp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    os.replace(tmp, DATA)

    # 2b revisions
    upd_file = HERE / "_updates_query.json"
    json.dump(parent_updates([i["item_id"] for i in items]), open(upd_file, "w", encoding="utf-8"), ensure_ascii=False)
    code, out = run(HERE / "make_updates_raw.py", upd_file)
    upd_file.unlink(missing_ok=True)
    if code:
        print("  ! make_updates_raw.py failed:\n" + out[-800:])

    # 3b CMS list only when a dealer is missing
    try:
        cmsf = json.load(open(HERE / "cms_directory.json", encoding="utf-8"))
    except (OSError, ValueError):
        cmsf = {}
    known = {norm(k) for k in cmsf.get("cms", {})}
    # at most once a day: a dealer that is not on the Dealer Login board (e.g. Dalton Toyota) would otherwise re-trigger it
    if "links" not in cmsf or (cmsf.get("checked_at") != date.today().isoformat() and any(norm(i["dealer"]) not in known for i in items)):
        print(f"  CMS list refreshed ({refresh_cms()} dealers) - a dealer was missing")

    # intake for new Assigned MLPs
    for i in added:
        if i["type"] == "MLP" and i["status"] == "Assigned":
            d = gql('query($ids:[ID!]) { items(ids:$ids) { updates(limit:30) { id created_at creator { name } text_body body } } }',
                    {"ids": [str(i["subitem_id"])]})
            f = HERE / "_intake_query.json"
            json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False)
            code, out = run(HERE / "production.py", "intake", f, i["dealer"], i["mlp"])
            f.unlink(missing_ok=True)
            print(f"  intake {i['dealer']} - {i['mlp']}: {'ok' if code == 0 else 'FAILED'}")

    # 4 build the tracker
    code, out = run(HERE / "build_mlp_tracker.py")
    if code:
        print("  ! build_mlp_tracker.py failed:\n" + out[-1500:])
        sys.exit(1)

    # 4c project folder status + clean-up of approved projects
    pf = HERE / "project_folders.json"
    cfg = json.load(open(pf, encoding="utf-8"))
    by_key = {(r["dealer"], r["mlp"]): r["status"] for r in recs}
    newly_approved = 0
    for e in cfg["projects"]:
        st = by_key.get((e["dealer"], e["mlp"]))
        if st and e.get("status") != st:
            newly_approved += st == "Approved"
            if e.get("status") == "Approved":     # back from Approved (Final Mobile Check revision): clean again later
                e.pop("cleaned", None)
            e["status"] = st
    json.dump(cfg, open(pf, "w", encoding="utf-8"), indent=1)
    cleanup = ""
    if any(e.get("status") == "Approved" and not e.get("cleaned") for e in cfg["projects"]):
        code, cleanup = run(HERE / "cleanup_approved.py", "--delete")

    # 5 report
    st = json.load(open(HERE / "tracker_state.json", encoding="utf-8"))
    revs = [i for i in st["items"] if (i.get("claude") or "").startswith("Revision")]
    lines = [f"Rows: {len(items)} ({sum(i['type'] == 'MLP' for i in items)} MLPs, {sum(i['type'] == 'City Page' for i in items)} city pages); approved list: {len(approved)}",
             "Added: " + (", ".join(f"{i['dealer']} {i['mlp']} ({i['status']})" for i in added) or "none"),
             "Left the tracker: " + (", ".join(f"{g['dealer']} {g['mlp']}" for g in gone) or "none"),
             "Status changes: " + (", ".join(f"{i['dealer']} {i['mlp']}: {a} -> {i['status']}" for a, i in changed) or "none"),
             "Revisions open: " + (", ".join(f"{i['dealer']} {i['mlp']}" for i in revs) or "none")]
    if cleanup.strip():
        lines.append("Clean-up: " + cleanup.strip().splitlines()[-1][:200])
    lines.append(f"Done in {time.time() - t0:.0f}s, no Claude tokens used.")
    print("\n".join("  " + l for l in lines))
    short = f"Refresh (direct): {len(items)} rows; added {len(added)}, left {len(gone)}, status changes {len(changed)}, revisions open {len(revs)}"
    if added or gone or changed:                 # quiet refreshes are not logged (keeps "Other work" honest)
        run(HERE / "summary.py", "--log", short)


if __name__ == "__main__":
    main()
