"""The "summary" command (user, 2026-11-13) and the Status block of the Summary sheet.

Usage:  python summary.py                -> today's summary in the user's format
        python summary.py 2026-11-12     -> the shift that started that date at 7 PM (to 3 AM next day); status = now
        python summary.py --detail [date] -> every History row of the day as well
        python summary.py --log "<what was done>" [--date YYYY-MM-DD] [--time HH:MM]
                                         -> add a line to work_log.md (work that is not an MLP History event)

Format (user, 2026-11-13: "Im done with MLP / Waiting for review MLP: (Dealership) (Model) / MLP is done but not yet
posted" - "its up to you how you will enhance it"): groups by where each MLP stands, dealership then model:
  Finished today, SEO revisions (2026-11-17), Approved today, Needs you (only real blockers), Waiting for review, Ready to post (revisions / new pages; big city batches on one line), Working on it now,
  Needs revision, Not started yet, On hold. No clock times, and only monday work (user 2026-11-14): tracker / tool
  / rule work from work_log.md is NOT in the summary (it still shows on the Activity tab).
"""
import re
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The user's shift (2026-11-13: "what we did from 7pm to 3am"): a summary covers 19:00 -> 03:00 the next morning.
sys.path.insert(0, str(Path(__file__).resolve().parent))   # -I drops the script folder from sys.path
import settings  # noqa: E402  (tracker_config.json, Settings tab)
SHIFT_START, SHIFT_HOURS = int(settings.get("shift_start")), int(settings.get("shift_hours"))
LOG = HERE / "work_log.md"
NOT_POSTED = ("Assigned", "Working on it", "Needs Revision")


def is_posted(i):
    """You pressed "Mark as posted" after Claude's last finish (user, 2026-11-13). A later revision makes it un-posted."""
    p = str(i.get("posted") or "")[:16]
    return bool(p) and p >= str(i.get("finished") or "")[:16]


def is_revision(i):
    """The page Claude just finished was a QA revision (not a new page)."""
    return i["monday"] == "Needs Revision" or "Revision #" in str(i.get("cnotes") or "")


def needs_you(items):
    """Only what really needs the user and is not posting (user, 2026-11-16: "Waiting on you" repeated Ready to post):
    a question, a missing link or images. Posting is in "Ready to post"; "Say 'start'" pages are Claude's queue."""
    out = OrderedDict()
    for i in sorted(items, key=lambda x: (x["dealer"].lower(), x["mlp"])):
        s = next_step(i)
        if s.startswith(("Nothing", "Say 'start'", "Open the to-post folder")) or (i["claude"] == "Claude is done" and i["monday"] in NOT_POSTED):
            continue
        out.setdefault(i["dealer"], []).append(f"{i['mlp']}: {s}")
    return out


def fold_batches(groups, limit=4):
    """A dealer with more than `limit` pages in one group (e.g. 11 city pages) becomes one line."""
    out = OrderedDict()
    for dealer, models in groups.items():
        if len(models) > limit and dealer.endswith(" - City Pages"):
            notes = {m.split("  (")[1].rstrip(")") for m in models if "  (" in m}
            names = "; ".join(m.split("  (")[0] for m in models)
            out[dealer] = [f"{len(models)} city pages" + (f"  ({notes.pop()})" if len(notes) == 1 else "") + f": {names}"]
        else:
            out[dealer] = models
    return out


def status_groups(items):
    """items: dicts with dealer, mlp, monday (monday status), claude (Claude Status).
    Returns OrderedDict title -> OrderedDict dealer -> [model (note)]."""
    order = [
        ("Waiting for review", lambda i: (i["monday"] == "Waiting for Review" and i["claude"] != "Claude working on it")
         or (is_posted(i) and i["monday"] in NOT_POSTED), lambda i: "posted - monday not updated yet" if i["monday"] in NOT_POSTED else None),
        ("Ready to post", lambda i: i["claude"] == "Claude is done" and i["monday"] in NOT_POSTED,
         lambda i: "revision - post it" if is_revision(i) else "new - upload & post"),
        ("Working on it now", lambda i: i["claude"] == "Claude working on it", None),
        ("Needs revision (not started yet)", lambda i: i["claude"] == "Revision needed" and i["monday"] != "Waiting for Review", None),
        ("Not started yet", lambda i: i["claude"] == "Not started" and i["monday"] in ("Assigned", "Working on it", "Needs Revision"), None),
        ("On hold", lambda i: i["monday"] == "On-Hold", None),
    ]
    out = OrderedDict((t, OrderedDict()) for t, _, _ in order)
    for i in sorted(items, key=lambda x: (x["dealer"].lower(), x["mlp"])):
        for title, test, note in order:
            if test(i):
                n = note(i) if note else None
                out[title].setdefault(i["dealer"], []).append(i["mlp"] + (f"  ({n})" if n else ""))
                break
    return out


def project_folder(dealer, mlp, folder=None):
    if folder and Path(str(folder)).exists():
        return Path(str(folder))
    try:
        import json
        for e in json.load(open(HERE / "project_folders.json", encoding="utf-8"))["projects"]:
            if e["dealer"] == dealer and e["mlp"] == mlp and Path(e["folder"]).exists():
                return Path(e["folder"])
    except (OSError, ValueError, KeyError):
        pass
    return None


def open_questions(text):
    """Numbered questions still needing an answer (FYI lines don't count)."""
    import re
    lines = [l for l in str(text or "").splitlines() if l.strip()]
    nums = [l for l in lines if re.match(r"\d+\.\s", l) and "FYI" not in l]
    return len(nums) if nums else (1 if lines else 0)


def next_step(i):
    """'Your Next Step' (user, 2026-11-13): exactly what the user has to do for this MLP, or that nothing is needed.
    i: dealer, mlp, monday, claude, questions, answers, folder, platform."""
    steps = []
    if is_posted(i) and i["monday"] in NOT_POSTED:
        return f"Nothing - you posted it ({str(i.get('posted'))[:16]}); set monday to Waiting for Review if it isn't yet."
    folder = project_folder(i["dealer"], i["mlp"], i.get("folder"))
    if i["claude"] == "Claude is done" and i["monday"] in NOT_POSTED and folder and (folder / "to-post" / "README.txt").exists():
        first = (folder / "to-post" / "README.txt").read_text(encoding="utf-8").splitlines()
        steps.append("Open the to-post folder and follow README.txt: " + " ".join(l.strip() for l in first[2:4] if l.strip())[:160])
    elif i["claude"] == "Claude is done" and i["monday"] in NOT_POSTED:
        up = None
        if folder and (folder / "to-upload.txt").exists():
            up = [l.strip() for l in (folder / "to-upload.txt").read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
        if up is None:
            n = len(list((folder / "assets" / "webp").glob("*.webp"))) if folder else 0
            img = f"Upload all {n} images in assets/webp (batches in assets/upload-batches.txt)" if n else "Upload the images in assets/webp"
        elif up:
            img = f"Upload {len(up)} new image{'s' if len(up) > 1 else ''}: " + ", ".join(up)
        else:
            img = "No new images"
        one_file = "1 file" in str(i.get("platform") or "")
        paste = "paste the page file into the CMS" if one_file else "paste the 3 CMS fields (cms-fields/)"
        post = "post ready-for-review.txt on monday" if folder and (folder / "ready-for-review.txt").exists() else "set monday to Waiting for Review"
        steps.append(f"{img}; {paste}; {post}.")
    q = open_questions(i.get("questions"))
    if q and not i.get("answers"):
        steps.append(f"Answer {q} question{'s' if q > 1 else ''} in the Questions column.")
    elif q:
        steps.append("Check the Questions column (answer what is still open).")
    if steps:
        return " ".join(steps)
    if i["monday"] == "Waiting for Review" and i["claude"] != "Claude working on it":
        return "Nothing - with QA."
    return {
        "Claude working on it": "Nothing - Claude is working on it.",
        "Revision needed": "Say 'start' - Claude will do the revision.",
        "Not started": "Say 'start' - Claude will build it." if i["monday"] in ("Assigned", "Working on it", "Needs Revision") else "Nothing.",
    }.get(i["claude"], "Nothing - with QA." if i["monday"] == "Waiting for Review" else "Nothing - on hold." if i["monday"] == "On-Hold" else "Nothing.")


def waiting_on_you(items):
    """dealer -> [model: step] for every MLP whose next step needs the user."""
    out = OrderedDict()
    for i in sorted(items, key=lambda x: (x["dealer"].lower(), x["mlp"])):
        s = next_step(i)
        if not s.startswith("Nothing"):
            out.setdefault(i["dealer"], []).append(f"{i['mlp']}: {s}")
    return out


def tracker_items():
    """Items from tracker_state.json (web app era, 2026-11-13); the workbook is only a fallback."""
    import json
    sf = HERE / "tracker_state.json"
    if sf.exists():
        st = json.load(open(sf, encoding="utf-8"))
        return [{"dealer": i["dealer"] + (" - City Pages" if i.get("type") == "City Page" else ""), "mlp": i["mlp"], "monday": i["status"],
                 "claude": i["claude"], "questions": i.get("questions"), "answers": i.get("answers"), "folder": i.get("folder"),
                 "platform": i.get("platform"), "posted": i.get("posted"), "finished": i.get("finished"),
                 "cnotes": i.get("cnotes")} for i in st.get("items", [])], None
    from openpyxl import load_workbook
    wb = load_workbook(HERE / "Final_MLP_Tracker.xlsx", read_only=True, data_only=True)
    rows = list(wb["MLPs"].iter_rows(values_only=True))
    hdr = next(r for r in rows if r and "Dealer" in r and "MLP" in r)
    c = {k: hdr.index(k) for k in ("Dealer", "MLP", "Type", "monday Status", "Claude Status", "Questions", "Answers", "Project Folder", "Platform") if k in hdr}
    g = lambda r, k: r[c[k]] if k in c else None
    return [{"dealer": g(r, "Dealer") + (" - City Pages" if g(r, "Type") == "City Page" else ""), "mlp": g(r, "MLP"), "monday": g(r, "monday Status"), "claude": g(r, "Claude Status"),
             "questions": g(r, "Questions"), "answers": g(r, "Answers"), "folder": g(r, "Project Folder"), "platform": g(r, "Platform")}
            for r in rows[rows.index(hdr) + 1:] if r and g(r, "MLP")], wb


def when(v):
    if isinstance(v, datetime):
        return v
    try:
        return datetime.strptime(str(v)[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def shift_of(t):
    """Shift key = the date the shift started (7 PM); anything from 19:00 to 18:59 next day belongs to it."""
    from datetime import timedelta
    return (t - timedelta(hours=SHIFT_START)).date()


def in_shift(t):
    from datetime import timedelta
    start = datetime.combine(shift_of(t), datetime.min.time()) + timedelta(hours=SHIFT_START)
    return t < start + timedelta(hours=SHIFT_HOURS)


def history_rows(wb, day):
    """History rows of the shift that started on `day` at 7 PM: (inside 7pm-3am, outside)."""
    import json
    hf = HERE / "history.json"   # 2026-11-13: history lives in history.json (Activity tab)
    src = json.load(open(hf, encoding="utf-8")) if hf.exists() else list(wb["History"].iter_rows(values_only=True))[1:]
    rows = [r for r in src if r[0] and when(r[0])]
    mine = [r for r in rows if str(shift_of(when(r[0]))) == day]
    return [r for r in mine if in_shift(when(r[0]))], [r for r in mine if not in_shift(when(r[0]))]


def day_finished(hist, all_hist=None):
    """Finished / Approved / Posted this shift, from History: dealer -> [model (what)].
    User 2026-11-14: no times, and only work done on / updated on monday."""
    fin, appr, posted = OrderedDict(), OrderedDict(), OrderedDict()
    all_hist = sorted(all_hist or hist, key=lambda r: str(r[0]))
    for when, dealer, mlp, what, _st in sorted(hist, key=lambda r: str(r[0])):
        w = str(what or "")
        grp = dealer + (" - City Pages" if re.search(r", [A-Z]{2}$", str(mlp)) else "")
        if w.startswith("Claude finished"):
            kind = w.replace("Claude finished ", "").split(" (")[0].split(" - ")[0]
            if kind.startswith("building"):
                # a "finish" after a QA revision request (since the last finish) is a revision, not a new build
                mine = [r for r in all_hist if r[1] == dealer and r[2] == mlp and str(r[0]) < str(when)]
                last_fin = max([str(r[0]) for r in mine if str(r[3]).startswith("Claude finished")] or [""])
                rev = any(str(r[3]).startswith("Revision requested") and str(r[0]) > last_fin for r in mine)
                kind = "QA revision" if rev else "new page built"
            else:
                kind = "QA " + kind
            line = f"{mlp}  ({kind})"
            if line not in fin.get(grp, []):
                fin.setdefault(grp, []).append(line)
        elif w.startswith("Removed from tracker"):
            appr.setdefault(dealer, []).append(mlp)
        elif w.startswith("You marked it as posted"):
            if mlp not in posted.get(grp, []):
                posted.setdefault(grp, []).append(mlp)
        elif w.startswith("You undid 'posted'") and mlp in posted.get(grp, []):
            posted[grp].remove(mlp)
    return fin, appr, OrderedDict((k, v) for k, v in posted.items() if v)


def seo_done(hist):
    """SEO revisions done this shift (user, 2026-11-17: "in the shift summary also show the SEO revision that was done
    during the shift"): dealer -> [model  (what changed)], from the seo_fix.py History rows (Claude note + Auto-fix)."""
    found = OrderedDict()
    for _t, dealer, mlp, what, _st in sorted(hist, key=lambda r: str(r[0])):
        w = str(what or "")
        if w.startswith("SEO auto-fix on "):          # web app Auto-fix button: "SEO auto-fix on <dealer> - <mlp>: n fix(es)"
            m = re.match(r"SEO auto-fix on (.+?) - (.+): (\d+) fix", w)
            if m and int(m.group(3)):
                found.setdefault((m.group(1), m.group(2)), {})["total"] = int(m.group(3))
        elif "SEO auto-fix:" in w and dealer:         # seo_fix.py --sid writes a Claude note on the page
            d = found.setdefault((dealer, mlp), {})
            for key, pat in (("caps", r"(\d+) ALL-CAPS heading"), ("spaces", r"space added in (\d+)"), ("alts", r"alt text added to (\d+)")):
                m = re.search(pat, w)
                if m:
                    d[key] = int(m.group(1))
    out = OrderedDict()
    for (dealer, mlp), d in sorted(found.items(), key=lambda kv: (kv[0][0].lower(), kv[0][1])):
        n = lambda k, one, many: f"{d[k]} {one if d[k] == 1 else many}"
        bits = [n("caps", "ALL-CAPS heading -> Title Case", "ALL-CAPS headings -> Title Case")] if d.get("caps") else []
        bits += [n("spaces", "heading space added", "heading spaces added")] if d.get("spaces") else []
        bits += [n("alts", "image alt text added", "image alt texts added")] if d.get("alts") else []
        rest = d.get("total", 0) - sum(d.get(k, 0) for k in ("caps", "spaces", "alts"))
        if rest > 0:   # the History copy of the note is cut short, so the Auto-fix count fills the gap
            bits.append(f"{rest} more SEO fix{'es' if rest > 1 else ''}" if bits else n("total", "SEO fix", "SEO fixes"))
        grp = dealer + (" - City Pages" if re.search(r", [A-Z]{2}$", str(mlp)) else "")
        out.setdefault(grp, []).append(f"{mlp}  ({'; '.join(bits)})" if bits else mlp)
    return out


def blogs_published(day):
    """Blogs set to Published on monday during the shift (user, 2026-11-18: "also include all the published blog to the
    shift summary"): dealer -> [title], from the blog boards' Status change time (webapp/blogs.py, fresh monday read)."""
    try:
        sys.path.insert(0, str(HERE / "webapp"))
        import blogs
        import json, time
        try:   # a monday read under 5 min old is reused (a fresh read takes ~20 s)
            age = time.time() - json.loads(blogs.MCACHE.read_text(encoding="utf-8")).get("at", 0)
        except Exception:
            age = 1e9
        items = blogs._monday(blogs.config(), fresh=age > 300).get("items", [])
    except Exception:
        return OrderedDict()
    out = OrderedDict()
    for b in sorted(items, key=lambda x: (x["dealer"].lower(), x["name"])):
        t = when(b.get("status_at"))
        if b.get("status") in ("Published",) and t and str(shift_of(t)) == day:
            out.setdefault(b["dealer"], []).append(b["name"])
    return out


def log_entries():
    """All work_log.md lines as (datetime, text)."""
    import re
    if not LOG.exists():
        return []
    out, day = [], None
    for line in LOG.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            day = line[3:].strip()
        elif day and line.startswith("- "):
            m = re.match(r"- (\d{1,2}:\d{2}) (.*)", line)
            if m:
                out.append((datetime.strptime(f"{day} {m.group(1).zfill(5)}", "%Y-%m-%d %H:%M"), m.group(2)))
    return sorted(out)


def log_lines(day):
    """work_log lines of the shift that started on `day`: (inside 7pm-3am, outside)."""
    mine = [(t, x) for t, x in log_entries() if str(shift_of(t)) == day]
    fmt = lambda t, x: f"{t.strftime('%H:%M')} {x}"
    return [fmt(t, x) for t, x in mine if in_shift(t)], [fmt(t, x) for t, x in mine if not in_shift(t)]


def add_log(text, day, at):
    lines = LOG.read_text(encoding="utf-8").splitlines() if LOG.exists() else ["# Work log (non-MLP work, newest day first)"]
    head, entry = f"## {day}", f"- {at} {text}"
    if head in lines:
        i = lines.index(head) + 1
        while i < len(lines) and lines[i].startswith("- "):
            i += 1
        lines.insert(i, entry)
    else:
        lines[1:1] = ["", head, entry]
    LOG.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print("logged:", day, entry)


def render(title, groups):
    out = [f"{title}:"]
    if not groups:
        out.append("    (none)")
    for dealer, models in groups.items():
        out.append(f"    {dealer}")
        out += [f"        {m}" for m in models]
    return out


def main():
    a = sys.argv[1:]
    if a and a[0] == "--log":
        day = a[a.index("--date") + 1] if "--date" in a else datetime.now().strftime("%Y-%m-%d")
        at = a[a.index("--time") + 1] if "--time" in a else datetime.now().strftime("%H:%M")
        add_log(a[1], day, at)
        return
    detail = "--detail" in a
    a = [x for x in a if x != "--detail"]
    day = a[0] if a else str(shift_of(datetime.now()))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    items, wb = tracker_items()
    hist, hist_out = history_rows(wb, day)
    import json
    hf = HERE / "history.json"
    all_hist = [r for r in (json.load(open(hf, encoding="utf-8")) if hf.exists() else []) if r[0]]
    fin, appr, posted = day_finished(hist + hist_out, all_hist)
    d = datetime.strptime(day, "%Y-%m-%d")
    # user 2026-11-14: "remove the time" + "only talks about what is done in monday or what is updated on monday"
    # -> no clock times anywhere, and no tracker / tool / rule work (work_log.md stays for the Activity tab only).
    lines = [f"Summary - {d.strftime('%a %b')} {d.day} shift - {settings.get('owner_name')}", ""]
    lines += render("Done (finished this shift)", fin) + [""]
    seo = seo_done(hist + hist_out)
    if seo:
        lines += render("SEO revisions (done this shift)", fold_batches(seo)) + [""]
    pub = blogs_published(day)
    if pub:
        n = sum(len(v) for v in pub.values())
        lines += render(f"Blogs published ({n})", pub) + [""]
    if posted:
        lines += render("Posted (uploaded + pasted in the CMS)", posted) + [""]
    if appr:
        lines += render("Approved on monday", appr) + [""]
    ny = needs_you(items)
    if ny:
        lines += render("Needs you", ny) + [""]
    for title, groups in status_groups(items).items():
        if title == "Ready to post":
            flat = [m for ms in groups.values() for m in ms]
            rv = sum("(revision" in m for m in flat)
            title = (f"Ready to post ({rv} revision{'s' if rv != 1 else ''}, {len(flat) - rv} new page{'s' if len(flat) - rv != 1 else ''})"
                     if flat else "Ready to post")
            groups = fold_batches(groups)
            if flat:
                lines += render(title, groups) + [""]
            continue
        if groups or title == "Waiting for review":
            lines += render(title + " (now)", fold_batches(groups)) + [""]
    if detail:
        lines += ["Every MLP event of the shift (History):"]
        lines += [f"    {r[1]} - {r[2]}: {r[3]}" for r in sorted(hist + hist_out, key=lambda r: str(r[0]))]
    while lines and not lines[-1]:
        lines.pop()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
