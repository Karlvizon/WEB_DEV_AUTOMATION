"""Web app features added 2026-11-13 (user: "build it with pop ups. also build the Summary button, Progress while Start
runs, QA patterns panel, Show the Start job's cost, Mark pages as posted ... direct me to the folder of the dealership in
VS code").

- Auto-update: every few minutes a cheap read-only check asks monday whether anything changed (refresh_monday.py
  --signature); only then the full refresh runs. Afterwards the tracker is compared before/after and Windows pop-ups
  are sent (toast.ps1) for revisions, new pages, approvals and due dates.
- Claude runs: the stream-json output of `claude -p` is turned into a readable log, live activity, and a cost record
  (webapp/jobs/costs.json). progress.py lets Claude say which page / step it is on (webapp/progress.json).
- QA patterns from the history's "Revision requested" rows, labelled with production.py's QA rules.
- Shift summary text (summary.py), open a dealer folder in VS Code.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

APP = Path(__file__).resolve().parent
HERE = APP.parent
sys.path.insert(0, str(HERE))
import settings  # noqa: E402
import plat  # noqa: E402   (Windows / Mac differences, 2026-11-19)

STATE, HIST = HERE / "tracker_state.json", HERE / "history.json"
JOBS = APP / "jobs"
WATCH = APP / "watch.json"
COSTS = JOBS / "costs.json"
PROGRESS = APP / "progress.json"
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PY = sys.executable


def read_json(p, default):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(p, data):
    tmp = Path(str(p) + ".tmp")
    json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def now_s():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------- pop-ups
def toast(title, body, anchor="", fix_sid=None):
    """Windows pop-up; clicking it opens the tracker (on the given tab). fix_sid adds a "Fix it now" button that opens
    the page on that revision and asks before Claude starts (user, 2026-11-13: "Fix it now on revision pop-ups")."""
    extra = []
    if fix_sid and settings.get("fix_from_popup"):
        extra = ["-Action2", "Fix it now", "-Url2", f"http://127.0.0.1:8765/#fix={fix_sid}"]
    plat.notify(title, body, f"http://127.0.0.1:8765/{('#' + anchor) if anchor else ''}", extra, APP / "toast.ps1")


# ---------------------------------------------------------------- auto-update (watcher)
AUTO = {"proc": None, "busy": False}
FULL_EVERY = 30          # minutes: a full refresh at least this often catches new assignments on any board
OFF_SHIFT_EVERY = 30     # minutes: outside the shift the check still runs this often (2026-11-20: One Legacy Motors
                         # pages assigned 09:48 only showed at 19:01 because nothing was checked off-shift)


def in_window(cfg, now=None):
    if cfg.get("watch_when") == "always":
        return True
    now = now or datetime.now()
    h = ((now.hour - int(cfg["shift_start"])) % 24) + now.minute / 60
    return h < int(cfg["shift_hours"])


def snapshot():
    st = read_json(STATE, {})
    items = {str(i["subitem_id"]): i for i in st.get("items", [])}
    appr = {str(a["subitem_id"]) for a in st.get("approved", [])}
    return items, appr


def alerts_for(before, after, cfg):
    (b_items, b_appr), (a_items, a_appr) = before, after
    out = []
    for sid, i in a_items.items():
        name = f"{i['dealer']} - {i['mlp']}"
        old = b_items.get(sid)
        if old is None:
            if cfg.get("alert_new"):
                out.append(("New page assigned to you", f"{name} ({i['status']}, due {i.get('due') or '-'})", "assigned"))
            continue
        rev_now = i.get("claude") == "Revision needed" or i.get("status") == "Needs Revision"
        rev_before = old.get("claude") == "Revision needed" or old.get("status") == "Needs Revision"
        # Final Mobile Check revisions get their own pop-up, also when the page already had a revision open
        # (user, 2026-11-16: "if there is a revision for final mobile check include it on the MLP tracker so that I can see it")
        mob = lambda it: sum(1 for l in str(it.get("revisions") or "").splitlines() if re.match(r"\[[^\]]*\]\s*Final Mobile Check - ", l))
        new_mobile = mob(i) > mob(old)
        if cfg.get("alert_revision") and new_mobile:
            out.append(("QA asked for a Final Mobile Check revision", f"{name} (phone view)", f"item={sid}", sid))
        elif cfg.get("alert_revision") and rev_now and not rev_before:
            out.append(("QA asked for a revision", name, f"item={sid}", sid))
    if cfg.get("alert_approved"):
        for sid in a_appr - b_appr:
            if sid in b_items:
                i = b_items[sid]
                out.append(("Approved", f"{i['dealer']} - {i['mlp']}", "approved"))
    return out


def revision_cost_hint():
    """Average cost of finished Claude revision runs (for the confirm box), or None."""
    rows = [r for r in read_json(COSTS, []) if r.get("action") == "fix" and r.get("cost_usd") and r.get("status") == "finished"]
    return round(sum(r["cost_usd"] for r in rows) / len(rows), 2) if rows else None


def due_alerts(cfg, w):
    if not cfg.get("alert_due"):
        return []
    today = date.today().isoformat()
    sent = w.setdefault("alerted_due", {})
    out = []
    for sid, i in snapshot()[0].items():
        dl = i.get("days_left")
        if dl is not None and 0 <= dl <= 1 and i.get("status") not in ("Waiting for Review", "On-Hold", "Approved") and sent.get(sid) != today:
            sent[sid] = today
            out.append((f"Due {'today' if dl == 0 else 'tomorrow'}", f"{i['dealer']} - {i['mlp']} ({i['status']})", "all"))
    for k in [k for k, v in sent.items() if v < (date.today() - timedelta(days=3)).isoformat()]:
        sent.pop(k)
    return out


def send_alerts(alerts):
    if not alerts:
        return
    if len(alerts) <= 3:
        for al in alerts:
            toast(al[0], al[1], al[2], al[3] if len(al) > 3 else None)
            time.sleep(1)
    else:
        toast(f"{len(alerts)} updates in the Web Dev Tracker", "; ".join(f"{al[0]}: {al[1]}" for al in alerts)[:280], "all")
        for al in alerts:                        # revisions still get their own pop-up with "Fix it now"
            if len(al) > 3:
                time.sleep(1)
                toast(al[0], al[1], al[2], al[3])


def run_refresh(reason, log_name="auto-refresh.log"):
    """Full direct refresh with before/after alerts. Returns (ok, summary line)."""
    cfg = settings.load()
    before = snapshot()
    JOBS.mkdir(exist_ok=True)
    log = JOBS / log_name
    with open(log, "w", encoding="utf-8") as f:
        f.write(f"{now_s()}  auto-update: {reason}\n\n")
        f.flush()
        p = subprocess.Popen([PY, "-I", str(HERE / "refresh_monday.py")], cwd=str(HERE), stdout=f, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, creationflags=NOWIN)
        AUTO["proc"] = p
        try:
            code = p.wait(timeout=600)
        except subprocess.TimeoutExpired:
            p.kill()
            code = -1
        AUTO["proc"] = None
    out = log.read_text(encoding="utf-8", errors="ignore").splitlines()
    line = next((l.strip() for l in out if l.strip().startswith("Rows:")), "")
    if code == 0:
        send_alerts(alerts_for(before, snapshot(), cfg))
    return code == 0, line or (out[-1] if out else "")


def watch_state():
    w = read_json(WATCH, {})
    w["connector"] = read_json(APP / "monday_health.json", {}).get("connector")
    cfg = settings.load()
    w["enabled"] = bool(cfg.get("watch_enabled")) and bool(settings.token())
    w["in_window"] = in_window(cfg)
    w["busy"] = AUTO["busy"]
    w.pop("sig", None)
    w.pop("alerted_due", None)
    return w


def new_during_job(w):
    """Quick read-only check while a Claude run is going: pop-up for each page newly assigned on monday (once)."""
    r = subprocess.run([PY, "-I", str(HERE / "refresh_monday.py"), "--signature"], cwd=str(HERE), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=90, creationflags=NOWIN)
    w["last_check"] = now_s()
    if r.returncode == 0:
        new = json.loads(r.stdout.strip().splitlines()[-1]).get("new") or []
        told = set(w.get("told_new") or [])
        fresh = [i for i in new if str(i) not in told]
        if fresh and settings.get("alert_new") is not False:
            toast("New page assigned on monday", f"{len(fresh)} new page(s) - they appear in the tracker when the "
                  "current Claude run ends.", "assigned")
        w["told_new"] = sorted(told | {str(i) for i in new})[-200:]
    write_json(WATCH, w)


def watcher(job_running):
    """Background loop started by server.py. job_running() -> True while a manual refresh job runs."""
    while True:
        time.sleep(15)
        try:
            cfg = settings.load()
            daily_jobs(cfg)                              # backup once a day + end-of-shift report (any hour)
            w = read_json(WATCH, {})
            force = w.pop("force", False)                # "Check monday now" works any time, even outside the shift
            full = force == "full"                       # header Refresh: full re-read even if the quick check sees no change
            if not settings.token() or (not force and not cfg.get("watch_enabled")):
                continue
            last = w.get("last_check")
            every = max(1, int(cfg.get("watch_minutes") or 2)) if in_window(cfg) else OFF_SHIFT_EVERY
            if not force and last and datetime.now() - datetime.strptime(last, "%Y-%m-%d %H:%M:%S") < timedelta(minutes=every):
                continue
            if job_running():
                # 2026-11-20: a 72-minute Start run used to pause every check. Still ask monday for NEW assignments
                # (read-only, no tracker files touched) and pop up; the full refresh follows when the run ends,
                # because the saved signature is left alone and differs then.
                new_during_job(w)
                continue
            AUTO["busy"] = True
            r = subprocess.run([PY, "-I", str(HERE / "refresh_monday.py"), "--signature"], cwd=str(HERE), capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=90, creationflags=NOWIN)
            w["last_check"] = now_s()
            if r.returncode != 0:
                w["error"] = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-1:] or ["check failed"]
                w["error"] = w["error"][0][:200]
            else:
                w.pop("error", None)
                res = json.loads(r.stdout.strip().splitlines()[-1])
                sig = res["sig"]
                last_full = w.get("last_full")
                stale = not last_full or datetime.now() - datetime.strptime(last_full, "%Y-%m-%d %H:%M:%S") >= timedelta(minutes=FULL_EVERY)
                changed = sig != w.get("sig")          # compared BEFORE saving (the label always said "30-minute" before)
                if changed or stale or full:
                    first = w.get("sig") is None
                    w["sig"] = sig
                    write_json(WATCH, w)
                    why = ("first check" if first else "you pressed Refresh" if full
                           else "new page assigned on monday" if changed and res.get("new")
                           else "monday changed" if changed else f"{FULL_EVERY}-minute full check (new assignments)")
                    ok, line = run_refresh(why)
                    w = read_json(WATCH, w)
                    w["last_full"] = now_s()
                    if why not in (f"{FULL_EVERY}-minute full check (new assignments)", "you pressed Refresh"):
                        w["last_change"] = now_s()
                    w["last_result"] = line if ok else "refresh failed - see the auto-refresh log"
            alerts = due_alerts(cfg, w)
            write_json(WATCH, w)
            send_alerts(alerts)
        except Exception as e:  # never let the loop die
            w = read_json(WATCH, {})
            w["error"] = f"{type(e).__name__}: {e}"[:200]
            write_json(WATCH, w)
        finally:
            AUTO["busy"] = False


def save_claude_usage(windows):
    """Same file as claude_usage_statusline.py, from a tracker Claude run's rate_limit_event (utilization 0-1)."""
    out = {}
    for k in ("five_hour", "seven_day"):
        w = windows.get(k) or {}
        if w.get("utilization") is not None:
            out[k] = {"used": round(float(w["utilization"]) * 100, 1), "resets_at": w.get("resetsAt")}
    if not out:
        return
    try:
        f = plat.app_dir() / "claude_usage.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps({"at": int(time.time()), **out, "model": "tracker run"}), encoding="utf-8")
        os.replace(tmp, f)
    except OSError:
        pass


def claude_usage():
    """Claude plan usage (user, 2026-11-19: "how many percent is claude code before we reach the limit"): the % of the
    5-hour and weekly limits, saved by claude_usage_statusline.py (Claude Code's status line, the documented source).
    A window whose reset time has passed counts as 0% (fresh). None until a Claude Code session has reported once."""
    try:
        d = json.loads((plat.app_dir() / "claude_usage.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    now, out = time.time(), {"at": d.get("at"), "age_min": int((time.time() - (d.get("at") or 0)) / 60)}
    for k in ("five_hour", "seven_day"):
        w = d.get(k)
        if not w:
            continue
        reset = w.get("resets_at")
        fresh = bool(reset and now >= float(reset))
        out[k] = {"used": 0.0 if fresh else float(w.get("used") or 0), "resets_at": reset, "reset_passed": fresh}
    return out if ("five_hour" in out or "seven_day" in out) else None


UPD = {"at": 0, "info": None}


def update_info():
    """"New version available" (user, 2026-11-19 #8): the shared updates folder holds latest.json (written by
    make_team_package.py next to the zips). Newer than tracker/VERSION.txt -> the header shows a notice. Checked at
    most every 10 minutes; no VERSION.txt (the lead's own tracker) or no folder = nothing to show."""
    if time.time() - UPD["at"] < 600:
        return UPD["info"]
    UPD["at"], info = time.time(), None
    try:
        folder = Path(settings.get("updates_folder") or "")
        mine = (HERE / "VERSION.txt").read_text(encoding="utf-8").strip() if (HERE / "VERSION.txt").exists() else ""
        if str(folder) not in ("", ".") and mine and (folder / "latest.json").exists():
            latest = json.loads((folder / "latest.json").read_text(encoding="utf-8"))
            if str(latest.get("version", "")) > mine:
                info = {"version": latest["version"], "mine": mine, "folder": str(folder),
                        "file": latest.get("windows" if plat.IS_WIN else "mac") or ""}
    except (OSError, ValueError, KeyError):
        info = None
    UPD["info"] = info
    return info


def open_updates():
    info = update_info()
    if not info:
        return {"error": "No newer version in the updates folder"}
    f = Path(info["folder"]) / info["file"]
    plat.open_path(f.parent if not f.exists() else info["folder"])
    return {"ok": True, "msg": f"Opened the updates folder - unzip {info['file'] or 'the new zip'} and double-click SETUP"}


def auto_running():
    p = AUTO["proc"]
    return p is not None and p.poll() is None


# ---------------------------------------------------------------- Claude runs: readable log, activity, cost
def _short(name, inp):
    inp = inp or {}
    if name == "Bash":
        return (inp.get("description") or inp.get("command") or "")[:140]
    for k in ("file_path", "path", "pattern", "skill", "url", "query"):
        if inp.get(k):
            return str(inp[k])[:140]
    return ""


def start_claude(cmd, log_path, job):
    """Run claude -p with stream-json; a thread writes a readable log and fills job['activity'/'tokens'/'result']."""
    f = open(log_path, "a", encoding="utf-8")
    p = subprocess.Popen(cmd + ["--output-format", "stream-json", "--verbose"], cwd=str(HERE), stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=NOWIN,
                         text=True, encoding="utf-8", errors="replace", bufsize=1, **plat.group_kwargs())
    job.update({"activity": "Starting Claude Code…", "tokens": {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}, "result": None})

    def reader():
        seen = set()
        for line in p.stdout:
            try:
                ev = json.loads(line)
            except ValueError:
                f.write(line)
                f.flush()
                continue
            t = ev.get("type")
            if t == "rate_limit_event":   # plan usage from the run itself -> the header "Claude usage" chip (2026-11-19)
                save_claude_usage((ev.get("rate_limit_info") or {}).get("unifiedWindows") or {})
                continue
            if t == "assistant":
                msg = ev.get("message") or {}
                mid = msg.get("id")
                u = msg.get("usage") or {}
                if mid and mid not in seen:
                    seen.add(mid)
                    tk = job["tokens"]
                    tk["input"] += u.get("input_tokens") or 0
                    tk["output"] += u.get("output_tokens") or 0
                    tk["cache_read"] += u.get("cache_read_input_tokens") or 0
                    tk["cache_write"] += u.get("cache_creation_input_tokens") or 0
                for c in msg.get("content") or []:
                    if c.get("type") == "text" and c.get("text", "").strip():
                        f.write(f"\n{datetime.now():%H:%M}  {c['text'].strip()}\n")
                        job["activity"] = c["text"].strip().splitlines()[0][:160]
                    elif c.get("type") == "tool_use":
                        s = _short(c.get("name"), c.get("input"))
                        f.write(f"{datetime.now():%H:%M}  -> {c.get('name')}: {s}\n")
                        job["activity"] = f"{c.get('name')}: {s}"[:160]
            elif t == "result":
                job["result"] = {"cost_usd": ev.get("total_cost_usd"), "turns": ev.get("num_turns"),
                                 "duration_s": round((ev.get("duration_ms") or 0) / 1000), "subtype": ev.get("subtype"),
                                 "usage": ev.get("usage") or {}}
                f.write(f"\n{now_s()}  Finished ({ev.get('subtype')}): {ev.get('num_turns')} turns, "
                        f"about ${ev.get('total_cost_usd') or 0:.2f} at API prices\n")
                if ev.get("result"):
                    f.write("\n" + str(ev["result"]).strip() + "\n")
                job["result_text"] = str(ev.get("result") or "")
            f.flush()
        p.wait()
        f.close()
        record_cost(job)
        finished_popup(job)

    threading.Thread(target=reader, daemon=True).start()
    return p


def finished_popup(job):
    """Pop-up when Claude finishes or stops on its own (user, 2026-11-13: "A pop-up when Claude finishes")."""
    if job.get("stopped_by_user") or not settings.get("alert_claude_done"):
        return
    r = job.get("result") or {}
    ok = r.get("subtype") == "success"
    what = f"revision for {job.get('page')}" if job.get("action") == "fix" else f"build of {job.get('page')}" if job.get("action") == "build" else f"the blog {job.get('page')}" if job.get("action") == "blog" else ("the queue" if job.get("action") == "start" else job.get("action"))
    text = " ".join((job.get("result_text") or job.get("activity") or "").split())
    cost = f" (about ${r['cost_usd']:.2f})" if r.get("cost_usd") else ""
    if ok:
        title = f"Claude finished {what}"
        body = (text[:220] + ("..." if len(text) > 220 else "")) or "Done - check the page and post it."
    else:
        title = f"Claude stopped before finishing {what}"
        body = ("Reason: " + str(r.get("subtype")) if r.get("subtype") else "It ended without a result") + " - open the log in the tracker."
    anchor = f"item={job.get('sid')}" if job.get("action") in ("fix", "build") and job.get("sid") else "post"
    if job.get("action") == "blog":
        anchor = "blogs"
    toast(title, body + cost, anchor)


def record_cost(job):
    r = job.get("result") or {}
    tk = dict(job.get("tokens") or {})
    u = r.get("usage") or {}
    if u:
        tk = {"input": u.get("input_tokens") or 0, "output": u.get("output_tokens") or 0,
              "cache_read": u.get("cache_read_input_tokens") or 0, "cache_write": u.get("cache_creation_input_tokens") or 0}
    started = job.get("started")
    mins = None
    try:
        mins = round((datetime.now() - datetime.strptime(started, "%Y-%m-%d %H:%M:%S")).total_seconds() / 60, 1)
    except (TypeError, ValueError):
        pass
    rec = {"action": job.get("action"), "started": started, "ended": now_s(), "minutes": mins,
           "status": "finished" if r.get("subtype") == "success" else ("stopped" if not r else r.get("subtype")),
           "cost_usd": r.get("cost_usd"), "turns": r.get("turns"), "tokens": tk}
    JOBS.mkdir(exist_ok=True)
    rows = read_json(COSTS, [])
    rows.insert(0, rec)
    write_json(COSTS, rows[:300])


def costs_view():
    rows = read_json(COSTS, [])
    def tot(since):
        sel = [r for r in rows if str(r.get("started") or "") >= since]
        return {"runs": len(sel), "cost_usd": round(sum(r.get("cost_usd") or 0 for r in sel), 2),
                "minutes": round(sum(r.get("minutes") or 0 for r in sel)),
                "output_tokens": sum((r.get("tokens") or {}).get("output", 0) for r in sel)}
    today = date.today()
    week = (today - timedelta(days=today.weekday())).isoformat()
    month = today.replace(day=1).isoformat()
    return {"runs": rows[:30], "week": tot(week), "month": tot(month), "all": tot("")}


def progress_for(job_started):
    p = read_json(PROGRESS, {})
    if p and job_started and str(p.get("at", "")) >= str(job_started):
        return p
    return None


# ---------------------------------------------------------------- QA patterns
def qa_patterns():
    sys.path.insert(0, str(HERE))
    from production import triage_text  # noqa: E402
    hist = read_json(HIST, [])
    today = date.today()
    week = (today - timedelta(days=today.weekday())).isoformat()
    month = (today - timedelta(days=30)).isoformat()
    labels, new_points = {}, []
    for when, dealer, mlp, what, _st in hist:
        m = re.match(r"Revision requested on monday \(([^)]+)\) by ([^:]+): (.*)", str(what), re.S)
        if not m:
            continue
        kind, text, day = m.group(1), m.group(3), str(when)[:10]
        pts, _ps = triage_text(text)
        for _n, point, lab in pts:
            if lab.startswith("NEW"):
                new_points.append({"date": day, "page": f"{dealer} - {mlp}", "kind": kind, "point": point[:220]})
                continue
            key = lab.replace("KNOWN: ", "").replace("check: ", "")
            e = labels.setdefault(key, {"label": key, "week": 0, "month": 0, "total": 0, "mobile": 0, "last": "", "pages": []})
            e["total"] += 1
            e["week"] += day >= week
            e["month"] += day >= month
            e["mobile"] += "Mobile" in kind
            if day >= e["last"]:
                e["last"], e["last_page"] = day, f"{dealer} - {mlp}"
            pg = f"{dealer} - {mlp}"
            if pg not in e["pages"]:
                e["pages"].append(pg)
    rows = sorted(labels.values(), key=lambda e: (-e["month"], -e["total"], e["label"]))
    return {"labels": rows, "new": new_points[:20],
            "revisions": sum(1 for r in hist if str(r[3]).startswith("Revision requested on monday"))}


# ---------------------------------------------------------------- weekly QA-mistakes report (user 2026-11-14: "3")
QA_TYPES = [   # (type, keywords) - first match wins; order matters ("center the headline" = alignment, not copy)
    ("Hero", ("hero",)),
    ("Copy & content", ("msrp", "price", "honda", "toyota", "brand name", "typo", "model year")),
    ("Spacing & alignment", ("spacing", "space between", "more space", "add space", "add some space", "gap", "margin",
                             "padding", "align", "center", "centre", "move ", "move downward", "move upward", "two rows",
                             "rows", "column", "crowded", "too far", "tight")),
    ("Fonts & text size", ("font", "text size", "bold", "uppercase", "title case", "three lines", "two lines", "one line",
                           "fit within")),
    ("Disclaimers & asterisks", ("disclaimer", "asterisk", "*")),
    ("Images & photos", ("image", "photo", "picture", "zoom", "crop", "blurry", "upscale", "pixelated", "gradient",
                         "cut off", "background")),
    ("Links & buttons", ("link", "cta", "button")),
    ("Copy & content", ("change", "replace", "title", "headline", "wording", "msrp", "price", "trim", "typo", "year",
                        "honda", "toyota", "brand", "h2", "h3", "meta", "content", "add a space", "word", "missing")),
]


def qa_type(point):
    low = point.lower()
    for name, keys in QA_TYPES:
        if any(k in low for k in keys):
            return name
    return "Other"


def _rev_fulltext(folder, day, kind, short):
    """The whole QA comment from the project's revisions folder when History holds a cut-off copy."""
    if not folder:
        return short
    base = Path(folder) / "revisions"
    if base.is_dir():
        tag = kind.replace(" ", "-")
        for d in sorted(base.glob(f"{day}_{tag}*")):
            f = d / "revision.txt"
            if f.exists():
                txt = f.read_text(encoding="utf-8", errors="ignore")
                norm = lambda t: re.sub(r"[^a-z0-9]", "", t.lower())
                if norm(short)[:80] in norm(txt) and len(txt) > len(short):   # same comment, longer copy
                    return txt.strip()
    return short


def qa_report(week=None):
    """Weekly QA-mistakes report: what QA sent back in one week (Mon-Sun), by type, dealer and page, compared with
    the week before. City pages share one master, so one comment sent to several cities counts once."""
    sys.path.insert(0, str(HERE))
    from production import split_points, label  # noqa: E402
    hist = read_json(HIST, [])
    st = read_json(STATE, {})
    folders = {(i["dealer"], i["mlp"]): i.get("folder") for i in st.get("items", [])}
    try:
        day0 = datetime.strptime(str(week), "%Y-%m-%d").date() if week else date.today()
    except ValueError:
        day0 = date.today()
    start = day0 - timedelta(days=day0.weekday())
    weeks = {"this": (start, start + timedelta(days=6)), "prev": (start - timedelta(days=7), start - timedelta(days=1))}
    seen, pts = set(), {"this": [], "prev": []}
    first = None
    for when, dealer, mlp, what, _st in hist:
        m = re.match(r"Revision requested on monday \(([^)]+)\) by ([^:]+): (.*)", str(what), re.S)
        if not m:
            continue
        d = datetime.strptime(str(when)[:10], "%Y-%m-%d").date()
        first = min(first or d, d)
        wk = next((k for k, (a, b) in weeks.items() if a <= d <= b), None)
        if not wk:
            continue
        kind, by, text = m.group(1), m.group(2).strip(), m.group(3)
        city = bool(re.search(r", [A-Z]{2}$", str(mlp)))
        if re.search(r"instructions for building the landing page|here is the backend access", text, re.I):
            continue                                  # the build brief, not a QA revision
        cut = len(text) in (199, 200)                 # History used to keep only 200 characters
        text = _rev_fulltext(folders.get((dealer, mlp)), str(d), kind, text)
        cut = cut and len(text) <= 200
        points, _ps = split_points(text)
        for n, p in enumerate(points):
            p = re.sub(r"\s+", " ", p).strip()
            p = re.sub(r"^(hello|hi)\s+@[^-]*-?\s*", "", p, flags=re.I).strip()
            p = re.sub(r"^(@\S+(?: (?!Please|Kindly|Could|Can)[A-Z][a-z]+)*\s+)+", "", p).strip()   # leading @mentions ("@Web Development Team")
            p = re.sub(r"\s*(thank you!?|thanks!?)\s*(cc[:\s].*)?$", "", p, flags=re.I).strip()
            if len(p) < 4 or re.fullmatch(r"(kindly|please)?\s*review and apply the following revisions\.?|hello.*|hi .*", p, re.I):
                continue
            if cut and n == len(points) - 1:
                p += " …"
            norm = re.sub(r"\b(arcadia|avon park|davenport|four corners|frostproof|lake placid|lakeland|meade/haines city|okeechobee|parrish)\b", "<city>", p.lower())
            # city pages: the same comment goes to every city (cut at different places), so match by sender + point no.
            key = (wk, dealer, f"city|{kind}|{by}|{n}|{norm[:30]}" if city else f"{mlp}|{kind}|{norm}", str(d))
            page = f"{dealer} - City Pages" if city else f"{dealer} - {mlp}"
            if key in seen:
                for x in pts[wk]:
                    if city and x["key"] == key and mlp not in x["cities"]:
                        x["cities"].append(mlp)
                continue
            seen.add(key)
            lab = label(p)
            pts[wk].append({"key": key, "date": str(d), "dealer": dealer, "page": page, "kind": kind, "by": by,
                            "point": p[:300], "type": qa_type(p), "mobile": "Mobile" in kind,
                            "known": lab.startswith("KNOWN"), "lesson": lab.replace("KNOWN: ", "").replace("check: ", ""),
                            "cities": [mlp] if city else []})
    cur, prev = pts["this"], pts["prev"]
    types = {}
    for x in cur + prev:
        t = types.setdefault(x["type"], {"type": x["type"], "this": 0, "prev": 0, "pages": [], "examples": [], "mobile": 0})
        if x in cur:
            t["this"] += 1
            t["mobile"] += x["mobile"]
            if x["page"] not in t["pages"]:
                t["pages"].append(x["page"])
            if len(t["examples"]) < 3:
                t["examples"].append(f'{x["page"]}: {x["point"][:140]}')
        else:
            t["prev"] += 1
    dealers = {}
    for x in cur:
        e = dealers.setdefault(x["dealer"], {"dealer": x["dealer"], "points": 0, "pages": [], "types": {}})
        e["points"] += 1
        e["types"][x["type"]] = e["types"].get(x["type"], 0) + 1
        if x["page"] not in e["pages"]:
            e["pages"].append(x["page"])
    for e in dealers.values():
        e["top"] = max(e["types"].items(), key=lambda kv: kv[1])[0]
    pages = {}
    for x in cur:
        pages[x["page"]] = pages.get(x["page"], 0) + 1
    first_seen = {}
    for when, dealer, mlp, what, _st in hist:   # first day each lesson was raised, over the whole history
        m2 = re.match(r"Revision requested on monday \(([^)]+)\) by ([^:]+): (.*)", str(what), re.S)
        if not m2:
            continue
        for p in split_points(m2.group(3))[0]:
            lab = label(p)
            if lab.startswith("KNOWN"):
                key2 = lab.replace("KNOWN: ", "")
                first_seen[key2] = min(first_seen.get(key2, "9999"), str(when)[:10])
    repeat = {}
    for x in cur:   # QA raised it again on a later day than the first time - the build rule did not stop it
        if x["known"] and x["date"] > first_seen.get(x["lesson"], "9999"):
            r = repeat.setdefault(x["lesson"], {"lesson": x["lesson"], "count": 0, "pages": []})
            r["count"] += 1
            if x["page"] not in r["pages"]:
                r["pages"].append(x["page"])
    a, b = weeks["this"]
    out = {"week_start": str(a), "week_end": str(b), "prev_start": str(weeks["prev"][0]), "first_data": str(first or ""),
           "kpi": {"points": len(cur), "prev_points": len(prev), "comments": len({(x["dealer"], x["page"], x["date"], x["kind"]) for x in cur}),
                   "pages": len(pages), "dealers": len(dealers), "mobile": sum(x["mobile"] for x in cur)},
           "types": sorted(types.values(), key=lambda t: (-t["this"], -t["prev"], t["type"])),
           "dealers": sorted(dealers.values(), key=lambda e: -e["points"]),
           "pages": sorted(({"page": k, "points": v} for k, v in pages.items()), key=lambda p: -p["points"])[:8],
           "repeat": sorted(repeat.values(), key=lambda r: -r["count"]),
           "other": [x for x in cur if x["type"] == "Other"],
           "points": [{k: v for k, v in x.items() if k != "key"} for x in cur]}
    out["text"] = qa_report_text(out)
    return out


LESSONS_FILE = APP / "dealer_lessons.md"


def dealer_lessons():
    """Per dealer: the QA lessons that came back most (all history). Written to webapp/dealer_lessons.md before every
    Claude job so the build checks them (user 2026-11-14: feed the QA report back into the builds)."""
    sys.path.insert(0, str(HERE))
    from production import split_points, label  # noqa: E402
    per, seen = {}, set()
    for when, dealer, mlp, what, _st in read_json(HIST, []):
        m = re.match(r"Revision requested on monday \(([^)]+)\) by ([^:]+): (.*)", str(what), re.S)
        if not m or re.search(r"instructions for building the landing page|backend access", m.group(3), re.I):
            continue
        city = bool(re.search(r", [A-Z]{2}$", str(mlp)))
        page = f"{dealer} - City Pages" if city else str(mlp)
        for n, p in enumerate(split_points(m.group(3))[0]):
            p = re.sub(r"\s+", " ", p).strip()
            p = re.sub(r"^((Hello|Hi)\s+)?(@[A-Z][\w.]*(?: (?!Please|Kindly|Could|Can)[A-Z][\w.]*)*\s*-?\s*)+", "", p).strip()
            p = re.sub(r"\s*(Thank you!?|Thanks!?)\s*(cc[:\s].*)?$", "", p, flags=re.I).strip()
            if len(p) < 4 or re.match(r"(kindly|please)?\s*review and apply", p, re.I):
                continue
            key = (dealer, str(when)[:10], m.group(2), n) if city else (dealer, mlp, str(when)[:10], p.lower())
            if key in seen:
                continue
            seen.add(key)
            lab = label(p)
            name = lab.replace("KNOWN: ", "").replace("check: ", "") if not lab.startswith("NEW") else qa_type(p) + " (no rule yet)"
            if name.startswith("Other"):
                continue                               # cannot be acted on (cut-off fragments, greetings)
            d = per.setdefault(dealer, {})
            e = d.setdefault(name, {"count": 0, "pages": [], "days": set(), "last": "", "said": ""})
            e["count"] += 1
            e["days"].add(str(when)[:10])
            if page not in e["pages"]:
                e["pages"].append(page)
            if str(when) >= e["last"]:
                e["last"], e["said"] = str(when), p[:160]
    return per


def write_dealer_lessons():
    per = dealer_lessons()
    out = ["# Lessons QA keeps sending back, per dealer", "",
           f"Made by the tracker from every QA revision ({now_s()[:16]}). Before you mark a page done, check every lesson",
           "listed for its dealer - these are the comments QA sent on this dealer's pages, most frequent first.",
           "Full rules and fixes: _mlp-toolkit/qa_feedback.md.", ""]
    for dealer in sorted(per, key=lambda d: -sum(e["count"] for e in per[d].values())):
        rows = sorted(per[dealer].items(), key=lambda kv: (-kv[1]["count"], -len(kv[1]["pages"])))[:8]
        out.append(f"## {dealer}")
        for name, e in rows:
            again = " - CAME BACK" if len(e["days"]) > 1 or len(e["pages"]) > 1 else ""
            out.append(f"- {name}: {e['count']}x on {', '.join(e['pages'][:4])}{again}. QA: \"{e['said']}\"")
        out.append("")
    LESSONS_FILE.write_text("\n".join(out), encoding="utf-8")
    return per


def dealer_lessons_text(dealer):
    """The lessons block for one dealer (for the 'Fix it now' prompt)."""
    try:
        txt = LESSONS_FILE.read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.search(r"^## " + re.escape(dealer) + r"\n(.*?)(?=^## |\Z)", txt, re.S | re.M)
    return m.group(1).strip() if m else ""


def qa_report_text(r):
    """Plain text of the report, for the Copy button (weekly update to the team)."""
    k = r["kpi"]
    fmt = lambda s: datetime.strptime(s, "%Y-%m-%d").strftime("%b %d").replace(" 0", " ")
    diff = k["points"] - k["prev_points"]
    lines = [f"QA report - week of {fmt(r['week_start'])} to {fmt(r['week_end'])} - {settings.get('owner_name')}", "",
             f"{k['points']} QA points on {k['pages']} page(s) from {k['dealers']} dealer(s)"
             + (f" ({'+' if diff > 0 else ''}{diff} vs the week before)" if k["prev_points"] else "")
             + (f"; {k['mobile']} on mobile" if k["mobile"] else ""), ""]
    if r["types"]:
        lines.append("What QA sent back most:")
        for t in [t for t in r["types"] if t["this"]]:
            tr = "" if not t["prev"] else (" (up from %d)" % t["prev"] if t["this"] > t["prev"] else " (down from %d)" % t["prev"] if t["this"] < t["prev"] else " (same)")
            lines.append(f"  - {t['type']}: {t['this']}{tr}")
        lines.append("")
    if r["dealers"]:
        lines.append("By dealer:")
        lines += [f"  - {e['dealer']}: {e['points']} point(s) on {len(e['pages'])} page(s), mostly {e['top']}" for e in r["dealers"]]
        lines.append("")
    if r["repeat"]:
        lines.append("Came back after QA first raised it (the rule needs tightening):")
        lines += [f"  - {x['lesson']}: {x['count']} time(s) - {', '.join(x['pages'][:4])}" for x in r["repeat"]]
    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------- dealer card (user, 2026-11-13: "1,2,3,5")
def dealer_card(name):
    """Everything known about a dealer: fonts, button links, image URL pattern, colours, platform, pages."""
    from production import dealer_base  # noqa: E402
    st = read_json(STATE, {})
    items = [i for i in st.get("items", []) if i["dealer"] == name]
    appr = [a for a in st.get("approved", []) if a["dealer"] == name]
    try:
        base = dealer_base(name) or {}
    except Exception:
        base = {}
    plat = next((i.get("platform") for i in items if i.get("platform")), "")
    if not plat:
        ov = (settings.get("platform_overrides") or {}).get(name)
        plat = ov or ""
    folder = dealer_folder(name, "MLP")
    city = dealer_folder(name, "City Page")
    lk = (st.get("dealer_links") or {}).get(name) or {}
    return {"dealer": name, "platform": plat, "cms_url": lk.get("cms") or "", "cred_url": lk.get("cred") or "", "fonts": base.get("fonts") or [], "cta_links": base.get("cta_links") or {},
            "cdn": base.get("cdn") or "", "colours": base.get("colours") or [], "from_project": base.get("from_project") or "",
            "folder": str(folder) if folder else "", "city_folder": str(city) if city else "",
            "open": [{"sid": i["subitem_id"], "mlp": i["mlp"], "status": i["status"], "due": i.get("due"), "type": i.get("type")} for i in items],
            "approved": [{"mlp": a["mlp"], "live_url": a.get("live_url"), "type": a.get("type"), "first_seen": a.get("first_seen_approved"),
                          "before": a.get("approved_before_tracking")} for a in appr]}


# ---------------------------------------------------------------- shift summary, VS Code
def shift_summary(day=None):
    args = [PY, "-I", str(HERE / "summary.py")] + ([day] if day and re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) else [])
    r = subprocess.run(args, cwd=str(HERE), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                       creationflags=NOWIN)
    return {"text": (r.stdout or "").strip() or (r.stderr or "").strip()}


def vscode():
    return plat.vscode()


def dealer_folder(dealer, kind="MLP"):
    cfg = settings.load()
    root = Path(cfg["city_root"] if kind == "City Page" else cfg["mlp_root"])
    cand = root / dealer
    if cand.is_dir():
        return cand
    # fall back to a folder whose name matches loosely (e.g. "Huston CDJR" vs "Huston CDJR ")
    want = re.sub(r"[^a-z0-9]", "", dealer.lower())
    if root.is_dir():
        for d in root.iterdir():
            if d.is_dir() and re.sub(r"[^a-z0-9]", "", d.name.lower()) == want:
                return d
    return None


def open_in_vscode(dealer, kind="MLP"):
    d = dealer_folder(dealer, kind)
    if not d:
        return {"error": f"No folder for {dealer} yet"}
    subprocess.Popen([vscode(), str(d)], creationflags=NOWIN, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True, "msg": f"Opening {d} in VS Code"}


# ---------------------------------------------------------------- daily backup + restore (user, 2026-11-13: "1,2,5,6")
BACKUPS = HERE / "backups"
KEEP_DAYS = 14
BACKUP_FILES = ["tracker_state.json", "history.json", "mlp_data.json", "project_folders.json", "tracker_config.json",
                "work_log.md", "automation_state.json", "cms_directory.json", "webapp/jobs/costs.json", "webapp/watch.json",
                "webapp/seo_reviewed.json"]


def _backup_sources():
    src = {f.replace("/", "__"): HERE / f for f in BACKUP_FILES}
    src["qa_feedback.md"] = Path(settings.get("toolkit_root")) / "qa_feedback.md"
    return src


def backup(name=None):
    """Copy the tracker's data files (notes, history, settings, QA rules) into backups/<name>/."""
    name = name or date.today().isoformat()
    d = BACKUPS / name
    d.mkdir(parents=True, exist_ok=True)
    files = {}
    for key, src in _backup_sources().items():
        if src.exists():
            shutil.copy2(src, d / key)
            files[key] = str(src)
    write_json(d / "manifest.json", {"created": now_s(), "files": files})
    return d


def prune_backups():
    """Keep the newest 14 daily backups and the newest 5 safety copies made before a restore."""
    if not BACKUPS.is_dir():
        return
    daily = sorted(p for p in BACKUPS.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name))
    safety = sorted(p for p in BACKUPS.iterdir() if p.is_dir() and p.name.startswith("before-restore-"))
    manual = sorted(p for p in BACKUPS.iterdir() if p.is_dir() and p.name.startswith("manual-"))
    for p in daily[:-KEEP_DAYS] + safety[:-5] + manual[:-10]:
        shutil.rmtree(p, ignore_errors=True)


def list_backups():
    out = []
    if BACKUPS.is_dir():
        for p in sorted((p for p in BACKUPS.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True):
            m = read_json(p / "manifest.json", {})
            size = sum(f.stat().st_size for f in p.iterdir() if f.is_file())
            out.append({"name": p.name, "created": m.get("created", ""), "files": len(m.get("files", {})), "kb": round(size / 1024)})
    return out


def restore(name, lock_path):
    d = BACKUPS / str(name)
    if not re.fullmatch(r"[\w-]+", str(name)) or not d.is_dir():
        return {"error": "backup not found"}
    m = read_json(d / "manifest.json", {})
    for _ in range(60):                              # same lock the engine and web edits use
        if not lock_path.exists() or time.time() - lock_path.stat().st_mtime > 300:
            break
        time.sleep(1)
    else:
        return {"error": "the tracker is busy - try again in a minute"}
    safety = backup(f"before-restore-{datetime.now():%Y%m%d-%H%M%S}")
    lock_path.write_text(f"restore {now_s()}")
    try:
        n = 0
        for key, target in m.get("files", {}).items():
            if (d / key).exists():
                shutil.copy2(d / key, target)
                n += 1
    finally:
        try:
            lock_path.unlink()
        except OSError:
            pass
    prune_backups()
    return {"ok": True, "msg": f"Restored {n} files from {name}. What you had before is saved as {safety.name}."}


# ---------------------------------------------------------------- end-of-shift report
REPORTS = HERE / "shift-reports"


def copy_to_clipboard(path):
    plat.copy_file_to_clipboard(path)


def shift_report_due(cfg, now=None):
    """The date (shift start) whose shift has ended and has no report yet, else None."""
    now = now or datetime.now()
    start, hrs = int(cfg["shift_start"]), int(cfg["shift_hours"])
    day = (now - timedelta(hours=start)).date()
    end = datetime.combine(day, datetime.min.time()) + timedelta(hours=start + hrs)
    if now < end:
        day -= timedelta(days=1)                     # current shift still running: the previous one is the last ended
    return day.isoformat()


def sync_team_rules_if_changed():
    """When the main QA rules file changed, copy its new lessons into the team's copy (2026-11-14). Adds only."""
    try:
        main = Path(settings.get("toolkit_root")) / "qa_feedback.md"
        m = int(main.stat().st_mtime)
        w = read_json(WATCH, {})
        if w.get("rules_synced") == m:
            return
        r = subprocess.run([PY, "-I", str(HERE / "sync_team_rules.py")], cwd=str(HERE), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60, creationflags=NOWIN)
        if r.returncode == 0:
            w = read_json(WATCH, {})
            w["rules_synced"] = m
            write_json(WATCH, w)
            n = re.search(r"Added (\d+)", r.stdout or "")
            if n and int(n.group(1)):
                subprocess.run([PY, "-I", str(HERE / "summary.py"), "--log", f"Team QA rules file: {n.group(1)} new lesson(s) copied from the main rules"],
                               cwd=str(HERE), capture_output=True, creationflags=NOWIN)
    except Exception:
        pass


# ---- Figma key expiry (user, 2026-11-20: "if the token is nearly expired give notification to the tracker")
def figma_key_status():
    """{state: none|ok|soon|expired|refused, days, expires, estimated} - 'soon' = 7 days or less left."""
    if not settings.figma_token():
        return {"state": "none"}
    m = settings.figma_meta()
    if not m.get("expires"):
        m = settings.save_figma_meta("")                 # key saved before the expiry date existed: assume 90 days
    out = {"expires": m["expires"], "estimated": bool(m.get("estimated"))}
    try:
        days = (date.fromisoformat(m["expires"]) - date.today()).days
    except ValueError:
        days = None
    out["days"] = days
    if settings.FIGMA_REFUSED.exists():
        out["state"] = "refused"
    elif days is not None and days < 0:
        out["state"] = "expired"
    elif days is not None and days <= 7:
        out["state"] = "soon"
    else:
        out["state"] = "ok"
    return out


def figma_key_alerts():
    """Once a day ask Figma if the key still works (one small read, no Claude tokens), then one pop-up per step:
    7 days left, 1 day left, expired, refused. A new key (new expiry date) starts the steps again."""
    if not settings.figma_token():
        return
    w = read_json(WATCH, {})
    today = date.today().isoformat()
    if w.get("figma_checked") != today:
        try:
            subprocess.run([PY, "-I", str(Path(settings.get("toolkit_root")) / "tools" / "figma_layout.py"), "--check"],
                           capture_output=True, text=True, timeout=60, creationflags=NOWIN)
        except Exception:
            pass
        w = read_json(WATCH, {})
        w["figma_checked"] = today
        write_json(WATCH, w)
    s = figma_key_status()
    step = {"refused": "refused", "expired": "expired"}.get(s["state"])
    if s["state"] == "soon":
        step = "1day" if s.get("days", 9) <= 1 else "7days"
    if not step:
        return
    sent = w.get("figma_alerts") or {}
    k = f"{s.get('expires')}|{step}"
    if sent.get(k):
        return
    msg = {"refused": "Figma refused the key, so the spacing check vs Figma is paused. Make a new key in Figma and paste it in Settings.",
           "expired": "The Figma key has expired, so the spacing check vs Figma is paused. Make a new key in Figma and paste it in Settings.",
           "1day": "The Figma key expires tomorrow. Make a new key in Figma and paste it in Settings > Figma connection.",
           "7days": f"The Figma key expires in {s.get('days')} days ({s.get('expires')}). Make a new one in Figma and paste it in Settings > Figma connection."}[step]
    toast("Figma key", msg, "settings")
    sent[k] = now_s()
    w = read_json(WATCH, {})
    w["figma_alerts"] = sent
    write_json(WATCH, w)


def daily_jobs(cfg):
    sync_team_rules_if_changed()
    try:
        figma_key_alerts()
    except Exception:
        pass
    try:
        if not (BACKUPS / date.today().isoformat()).exists():
            backup()
            prune_backups()
    except Exception:
        pass
    try:
        w = read_json(WATCH, {})
        day = shift_report_due(cfg)
        done = w.get("reports") or []
        if day in done:
            return
        REPORTS.mkdir(exist_ok=True)
        f = REPORTS / f"{day} shift.txt"
        if not f.exists():
            text = shift_summary(day).get("text") or ""
            if not text.strip():
                return
            f.write_text(text + "\n", encoding="utf-8")
            if not done:                              # first run ever: just file the last shift, no pop-up
                w["reports"] = [day]
                write_json(WATCH, w)
                return
            copy_to_clipboard(f)
            toast("Shift done - summary copied", f"Paste it anywhere (Ctrl+V). Saved as shift-reports/{f.name}", "activity")
            weekly_qa_report(cfg, day)
        w["reports"] = (done + [day])[-60:]
        write_json(WATCH, w)
    except Exception:
        pass


WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def weekly_qa_report(cfg, day):
    """After the shift that starts on the chosen weekday (Settings, default Fri): save the week's QA report and pop up.
    Clicking the pop-up opens the QA report tab (Copy report button there), so the shift summary on the clipboard stays."""
    try:
        d = datetime.strptime(day, "%Y-%m-%d").date()
        if WEEKDAYS[d.weekday()] != str(cfg.get("qa_report_day") or "Fri")[:3].title():
            return
        r = qa_report(day)
        name = f"{r['week_start']} QA report.txt"
        (REPORTS / name).write_text(r["text"] + "\n", encoding="utf-8")
        k = r["kpi"]
        top = next((t["type"] for t in r["types"] if t["this"]), "none")
        toast("Weekly QA report ready", f"{k['points']} QA points this week, most: {top}. Click to open and copy it.", "qareport")
    except Exception:
        pass


# ---------------------------------------------------------------- since your last shift (user 2026-11-14)
SEEN = APP / "seen.json"
SINCE_KINDS = [  # (group, test on the History text)
    ("New pages assigned", lambda t: t.startswith("New MLP assigned")),
    ("QA revisions", lambda t: t.startswith("Revision requested on monday") and
     not re.search(r"instructions for building the landing page|backend access", t, re.I)),   # the build brief is not news
    ("Approved", lambda t: t.startswith("Removed from tracker")),
    ("Due dates moved", lambda t: t.startswith("Due date moved")),
    ("Status changed on monday", lambda t: t.startswith("monday status changed") and
     not t.endswith(("-> Working on it", "-> Waiting for Review"))),   # your own moves are not news
]


def since_last_shift():
    """monday news since the end of your last shift (or since you last pressed 'Got it', if later)."""
    cfg = settings.load()
    start, hrs = int(cfg["shift_start"]), int(cfg["shift_hours"])
    now = datetime.now()
    cur = datetime.combine((now - timedelta(hours=start)).date(), datetime.min.time()) + timedelta(hours=start)
    prev_end = cur - timedelta(days=1) + timedelta(hours=hrs)
    ack = read_json(SEEN, {}).get("ack")
    since = max(prev_end.strftime("%Y-%m-%d %H:%M:%S"), ack or "")
    groups = {g: [] for g, _f in SINCE_KINDS}
    for when, dealer, mlp, what, _st in read_json(HIST, []):
        if str(when) <= since:
            continue
        t = str(what or "")
        for g, f in SINCE_KINDS:
            if f(t):
                short = re.sub(r"^Revision requested on monday \(([^)]+)\) by ([^:]+): ", r"\2 (\1): ", t)
                short = re.sub(r"^monday status changed: ", "", short).replace("Due date moved on monday: ", "")
                short = re.sub(r"^New MLP assigned ?", "", short).replace("Removed from tracker (Approved in monday or unassigned)", "approved")
                groups[g].append({"when": str(when)[:16], "page": f"{dealer} - {mlp}", "text": short[:220]})
                break
    for g in groups.values():   # city pages: the same comment goes to every city -> one line "City Pages (10)"
        keep, cities = [], {}
        for x in sorted(g, key=lambda x: x["when"], reverse=True):
            m = re.match(r"^(.*?\): )?(.*)$", x["text"], re.S)
            body = re.sub(r"^((Hello|Hi)\s+)?(@[A-Z][\w.]*(?: [A-Z][\w.]*)*\s*-?\s*)+", "", m.group(2)).strip()
            body = re.sub(r"\s*(Thank you!?|Thanks!?)\s*(cc[:\s].*)?$", "", body, flags=re.I).strip()
            x["text"] = (m.group(1) or "") + (body[:1].upper() + body[1:] if body else "")
            dealer, page = x["page"].split(" - ", 1)
            if re.search(r", [A-Z]{2}$", page):
                norm = x["text"].replace(page.rsplit(", ", 1)[0], "<city>")
                k = (dealer, x["when"], norm[:norm.find(": ") + 40] if ": " in norm else norm[:50])
                if k in cities:
                    cities[k]["n"] += 1
                    cities[k]["page"] = f"{dealer} - City Pages ({cities[k]['n']})"
                    cities[k]["text"] = cities[k]["norm"]
                    continue
                x["n"], x["norm"] = 1, norm.replace("<city>", "[city]")
                cities[k] = x
            keep.append(x)
        g[:] = keep
    revised = {x["page"] for x in groups["QA revisions"]}   # "-> Needs Revision" repeats the QA comment line
    groups["Status changed on monday"] = [x for x in groups["Status changed on monday"]
                                         if not (x["text"].endswith("-> Needs Revision") and x["page"] in revised)]
    first = since == prev_end.strftime("%Y-%m-%d %H:%M:%S")
    return {"since": since, "title": "Since your last shift" if first else "New since you last looked",
            "groups": [{"name": g, "items": v} for g, v in groups.items() if v],
            "count": sum(len(v) for v in groups.values())}


def since_ack():
    write_json(SEEN, {"ack": now_s()})
    return {"ok": True}


def shift_reports():
    if not REPORTS.is_dir():
        return []
    return [{"name": p.stem, "path": str(p)} for p in sorted(REPORTS.glob("*.txt"), reverse=True)[:20]]


# ---------------------------------------------------------------- QA pre-check before "posted"
PRECHECK = threading.Lock()


QA_RES = APP / "qa_results.json"
QA_ALL = {"running": False, "done": 0, "total": 0, "page": ""}


def _pmtime(folder):
    try:
        return int((Path(folder) / "preview.html").stat().st_mtime)
    except (OSError, TypeError):
        return None


def _rules_mtime():
    """When the QA rules (qa_sweep.js / final_mobile_check.js) last changed - a saved result older than that is out of date too."""
    qa = Path(settings.get("toolkit_root")) / "tools" / "qa"
    return max([int((qa / n).stat().st_mtime) for n in ("qa_sweep.js", "final_mobile_check.js") if (qa / n).exists()] or [0])


def needs_phone_check(folder):
    """The page had a Final Mobile Check revision -> Mark as posted also runs the Final mobile check (user, 2026-11-16)."""
    rv = Path(folder) / "revisions" if folder else None
    try:
        return bool(rv and rv.is_dir() and any(d.is_dir() and d.name.endswith("Final-Mobile-Check") for d in rv.iterdir()))
    except OSError:
        return False


def _fresh(r, folder):
    return (bool(r) and r.get("mtime") == _pmtime(folder) and int(r.get("rules") or 0) >= _rules_mtime()
            and (r.get("phone") or not needs_phone_check(folder)))


def qa_summary(items):
    """Per page: the last QA sweep result, and whether the page changed since (improvement #4, 2026-11-13)."""
    res, out = read_json(QA_RES, {}), {}
    for i in items:
        f = i.get("folder")
        r = res.get(str(f)) if f else None
        if not r:
            continue
        fresh = _fresh(r, f)
        out[str(i["subitem_id"])] = {"n": len(r.get("fixes") or []), "checked": r.get("checked"), "at": r.get("at"),
                                     "fresh": fresh, "fixes": (r.get("fixes") or [])[:8]}
    return out


def qa_all(jobs):
    """Run the QA sweep on several pages, one after another, in the background. jobs = [(label, folder), ...]."""
    if QA_ALL["running"]:
        return {"error": "a QA check of all pages is already running"}
    todo = [(l, f) for l, f in jobs if f and (Path(f) / "preview.html").exists()]
    QA_ALL.update(running=True, done=0, total=len(todo), page="")

    def work():
        try:
            for label, f in todo:
                QA_ALL["page"] = label
                precheck(f, use_cache=True, wait=True)
                QA_ALL["done"] += 1
        finally:
            QA_ALL.update(running=False, page="")
    threading.Thread(target=work, daemon=True).start()
    return {"ok": True, "msg": f"QA check started for {len(todo)} page(s) - the badges fill in as each one finishes"}


# ---------------------------------------------------------------- posting helpers (user 2026-11-14: "1 and 2")
UPLOADS = APP / "upload_progress.json"
PASTE_LABEL = {".html": "HTML", ".css": "CSS", ".js": "JS"}


def _pack_dir(folder):
    d = Path(folder) / "to-post" if folder else None
    return d if d and d.is_dir() else None


def pack_summary(items):
    """For every page with an upload pack: the files to paste (copy buttons), the monday note and the image batches
    (with the ticks you set). Ticks reset when the pack is rebuilt (README.txt changes)."""
    ticks, out = read_json(UPLOADS, {}), {}
    for i in items:
        d = _pack_dir(i.get("folder"))
        if not d:
            continue
        stamp = int((d / "README.txt").stat().st_mtime) if (d / "README.txt").exists() else 0
        t = ticks.get(str(i["subitem_id"])) or {}
        done = t.get("done", []) if t.get("stamp") == stamp else []
        paste = d / "2-paste-into-cms"
        files = []
        if paste.is_dir():
            order = {".html": 0, ".css": 1, ".js": 2}
            for f in sorted(paste.iterdir(), key=lambda f: (order.get(f.suffix.lower(), 3), f.name)):
                if f.is_file():
                    lab = PASTE_LABEL.get(f.suffix.lower()) or f.stem.replace("-", " ").capitalize()
                    files.append({"name": f.name, "label": lab, "kb": round(f.stat().st_size / 1024)})
        up = d / "1-upload-images"
        batches = [{"name": b.name, "count": sum(1 for x in b.iterdir() if x.is_file()), "done": b.name in done}
                   for b in sorted(up.iterdir()) if b.is_dir()] if up.is_dir() else []
        nf = d / "3-post-on-monday.txt"
        out[str(i["subitem_id"])] = {"files": files, "note": nf.exists(), "batches": batches,
                                     "notes": list(split_note(nf.read_text(encoding="utf-8", errors="replace"))) if nf.exists() else [],
                                     "ba": len(list((d / "4-before-after").glob("*.png"))) if (d / "4-before-after").is_dir() else 0}
    return out


NOTE_SUBS = ("Final MLP", "Final Mobile Check")


def split_note(text):
    """One monday note per subitem (user, 2026-11-16: QA reads the Final MLP and the Final Mobile Check threads
    separately). Claude's note has a "Final MLP" and a "Final Mobile Check" heading line; each note keeps the greeting,
    its own points (numbered from 1), the page link, sign-off and cc. "Also fixed..." goes with the Final MLP note.
    Returns {} when the note is not split by subitem (one note is enough then)."""
    lines = text.splitlines()
    heads = [k for k, l in enumerate(lines) if l.strip() in NOTE_SUBS]
    if len({lines[k].strip() for k in heads}) < 2:
        return {}
    tail_at = next((k for k, l in enumerate(lines) if k > heads[0] and l.strip().startswith("Page:")), len(lines))
    also_at = next((k for k, l in enumerate(lines) if heads[0] < k < tail_at and l.strip().lower().startswith("also ")), tail_at)
    head, tail = lines[:heads[0]], lines[tail_at:]
    while head and not head[-1].strip():
        head = head[:-1]
    parts = {}
    for n, k in enumerate(heads):
        end = min([h for h in heads if h > k] + [also_at])
        parts[lines[k].strip()] = [l for l in lines[k + 1:end]]
    also = lines[also_at:tail_at] if also_at < tail_at else []

    def renumber(block, start=1):
        out, n = [], start
        for l in block:
            m = re.match(r"(\s*)\d+\.\s+(.*)", l)
            if m:
                out.append(f"{m.group(1)}{n}. {m.group(2)}")
                n += 1
            else:
                out.append(l)
        return out, n

    notes = {}
    for sub in NOTE_SUBS:
        if sub not in parts:
            continue
        hd = [re.sub(r"The revisions for (.+?) are done:", rf"The {sub} revisions for \1 are done:", l) for l in head]
        body, nxt = renumber([l for l in parts[sub]])
        while body and not body[-1].strip():
            body = body[:-1]
        extra = []
        if sub == "Final MLP" and also:
            extra, _ = renumber(also, nxt)
            extra = [""] + extra
            while extra and not extra[-1].strip():
                extra = extra[:-1]
        notes[sub] = "\n".join(hd + [""] + body + extra + [""] + tail).strip() + "\n"
    return notes


def pack_text(folder, name):
    """Text of one paste file or the monday note ("@note", or "@note:Final MLP" / "@note:Final Mobile Check" for the
    note of one subitem) - only files inside this page's to-post folder."""
    d = _pack_dir(folder)
    if not d:
        return None
    name = str(name)
    if name.startswith("@note"):
        f = d / "3-post-on-monday.txt"
        if not f.is_file():
            return None
        txt = f.read_text(encoding="utf-8", errors="replace")
        sub = name.split(":", 1)[1] if ":" in name else ""
        return split_note(txt).get(sub, txt) if sub else txt
    f = d / "2-paste-into-cms" / Path(name).name
    return f.read_text(encoding="utf-8", errors="replace") if f.is_file() else None


def batch_tick(sid, folder, batch, done):
    d = _pack_dir(folder)
    if not d:
        return {"error": "no upload pack"}
    stamp = int((d / "README.txt").stat().st_mtime) if (d / "README.txt").exists() else 0
    ticks = read_json(UPLOADS, {})
    t = ticks.get(str(sid)) or {}
    cur = set(t.get("done", [])) if t.get("stamp") == stamp else set()
    (cur.add if done else cur.discard)(str(batch))
    ticks[str(sid)] = {"stamp": stamp, "done": sorted(cur)}
    write_json(UPLOADS, ticks)
    return {"ok": True}


AUTOQA = {"sid": None, "page": ""}


def auto_qa_loop(state_file, claude_running):
    """Run the QA sweep by itself on every ready-to-post page whose saved result is missing or older than the page
    (user 2026-11-14). Waits until the page has not changed for 2 minutes and no Claude job is running, then checks
    one page at a time, so the badge is always current and 'Mark as posted' never waits."""
    while True:
        time.sleep(30)
        try:
            if not settings.get("auto_qa") or claude_running() or QA_ALL["running"]:
                continue
            res = read_json(QA_RES, {})
            for i in read_json(state_file, {}).get("items", []):
                if not (i.get("claude") == "Claude is done" and i.get("status") in ("Assigned", "Working on it", "Needs Revision")):
                    continue
                if i.get("posted") and str(i["posted"])[:16] >= str(i.get("finished") or "")[:16]:
                    continue
                f = i.get("folder")
                m = _pmtime(f)
                if not m or time.time() - m < 120:
                    continue
                if _fresh(res.get(str(f)), f):
                    continue
                AUTOQA.update(sid=i["subitem_id"], page=f"{i.get('dealer')} - {i.get('mlp')}")
                try:
                    precheck(f, wait=True)
                finally:
                    AUTOQA.update(sid=None, page="")
                break                                   # one page per round; the next round picks the next one
        except Exception:  # never let the loop die
            AUTOQA.update(sid=None, page="")


# Figma link per page (2026-11-20, Figma spacing check): city pages and newer pages have their Figma link only in the
# monday update. Copy it into <folder>/figma/link.txt so tools/figma_layout.py (run by qa_sweep.js) can read the design.
FIGMA_RE = re.compile(r"https?://(?:www[.])?figma[.]com/(?:design|file)/[A-Za-z0-9]+[^\s\"'<>)]*")


def save_figma_links():
    upd = read_json(HERE / "updates_raw.json", {})
    n = 0
    for i in read_json(STATE, {}).get("items", []):
        f = i.get("folder")
        if not f or not (Path(f) / "preview.html").exists():
            continue
        src = upd.get(str(i.get("subitem_id"))) or upd.get(str(i.get("item_id")))
        links = FIGMA_RE.findall(json.dumps(src or {}, ensure_ascii=False).replace(chr(92) + "n", " "))
        if not links:
            continue
        best = next((l for l in links if "node-id=" in l), links[0]).rstrip("\\.,;")
        lt = Path(f) / "figma" / "link.txt"
        try:
            if lt.exists() and lt.read_text(encoding="utf-8").strip() == best:
                continue
            lt.parent.mkdir(parents=True, exist_ok=True)
            lt.write_text(best + chr(10), encoding="utf-8")
            n += 1
        except OSError:
            pass
    return n


def precheck(folder, use_cache=False, wait=False):
    """Run the QA sweep (qa_sweep.js) on the project before you mark it posted. One at a time (one Edge).
    use_cache: reuse the saved result when preview.html has not changed since (bulk 'mark as posted')."""
    if folder and use_cache:
        r = read_json(QA_RES, {}).get(str(folder))
        if _fresh(r, folder):
            return {"ok": True, "fixes": r.get("fixes") or [], "checked": r.get("checked"), "cached": r.get("at")}
    if not folder or not (Path(folder) / "preview.html").exists():
        return {"ok": True, "skipped": "no preview.html in the project folder - nothing to check"}
    script = Path(settings.get("toolkit_root")) / "tools" / "qa" / "qa_sweep.js"
    if not script.exists():
        return {"ok": True, "skipped": "QA sweep script not found"}
    if not PRECHECK.acquire(blocking=wait, timeout=600 if wait else -1):
        return {"error": "a QA check is already running - wait a moment"}
    try:
        save_figma_links()
    except Exception:
        pass
    try:
        r = subprocess.run(["node", str(script), str(folder)], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=300, creationflags=NOWIN)
    except subprocess.TimeoutExpired:
        return {"error": "the QA check took too long"}
    finally:
        PRECHECK.release()
    lines = [l.strip() for l in (r.stdout or "").splitlines() if l.strip().startswith(("OK", "FIX"))]
    out = {"ok": True, "fixes": [l[3:].strip() for l in lines if l.startswith("FIX")], "checked": len(lines)}
    phone = needs_phone_check(folder)
    if phone:   # Final mobile check on pages QA sent back from the Final Mobile Check (phones 390/375/430)
        fmc = Path(settings.get("toolkit_root")) / "tools" / "qa" / "final_mobile_check.js"
        if fmc.exists():
            if not PRECHECK.acquire(blocking=True, timeout=600):
                return {"error": "a QA check is already running - wait a moment"}
            try:
                r2 = subprocess.run(["node", str(fmc), str(folder)], capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", timeout=300, creationflags=NOWIN)
                pl = [l.strip() for l in (r2.stdout or "").splitlines() if l.strip().startswith(("OK", "FIX"))]
                out["fixes"] += ["Phone: " + l[3:].strip() for l in pl if l.startswith("FIX")]
                out["checked"] += len(pl)
                out["phone"] = True
            except subprocess.TimeoutExpired:
                out["fixes"].append("Phone: the Final mobile check took too long - run it again")
            finally:
                PRECHECK.release()
    if lines:   # remember it for the row badge and for bulk 'mark as posted'
        res = read_json(QA_RES, {})
        res[str(folder)] = {"at": now_s(), "mtime": _pmtime(folder), "rules": _rules_mtime(), "fixes": out["fixes"],
                            "checked": out["checked"], "phone": bool(out.get("phone"))}
        write_json(QA_RES, res)
    return out


# ===== SEO review tab (user, 2026-11-17: "add a tab for SEO review when there is a revision about the page") =====
# Every page in the tracker that got a QA revision is listed with an automatic SEO check of its current paste files
# (meta title/description, URL, one H1, heading order, Title Case headings, glued words, alt text, link text) and the
# revision points that touch SEO. "Mark SEO reviewed" stores the latest revision name, so a new revision brings it back.
SEO_SEEN = APP / "seo_reviewed.json"
SEO_KEYS = ("seo", "meta", "title tag", "page title", "description", "url", "slug", "canonical", "h1", "h2", "h3", "h4",
            "heading", "header", "headline", "alt", "keyword", "schema", "capitaliz", "uppercase", "title case",
            "all caps", "link", "anchor", "redirect", "index")
_OK_CAPS = set("ACTIV HEMI AWD FWD RWD SRT LED SUV SUVS MSRP CDJR GMC RAM USB GPS EPA MPG BMW AMG SRX XLT LTZ RST ZR2 TRX EV "
               "AT4 HD LB CPO VIN APR ADAS RV SXT GTS TPMS NHTSA IIHS II III IV VI HP DOHC SOHC CVT AM PM FAQ FAQS DDC CTA "
               "NAV AKG MOAB DSSV TNGA XSE XLE USA AL GA FL TX CA NY NJ PA MS AZ NV OH MI IL NC SC TN VA KY LA OK AR "
               "GLC GLE GLS GLA GLB CLA CLE EQS EQE EQB MBUX HVAC SEL XRT".split())
_OK_CAMEL = re.compile(r"^(my[A-Z]\w*|CarPlay|OnStar|SiriusXM|eTorque|MyLink|LaneSense|ParkSense|ParkView|IntelliBeam|"
                       r"QuietTuning|WildPeak|BlueCruise|SmartWay|AutoStick|TowMax|MultiPro|PowerShift|DuraMax|EcoBoost|"
                       r"SelecTerrain|ProGrade|SafetySense|SmartSense|HondaSense|MaxCare|iPhone|YouTube|WiFi|McKinney|"
                       r"McAllen|DeSoto|LaGrange|DeKalb|MBUX|eSUV|CarBravo|TurboMax|MultiStow|MultiPro)$")
_JOIN = "\x00"   # marks where an element starts inside a heading: a word joined there with no space is "glued"
_VAGUE = ("click here", "here", "read more", "learn more", "more")


def _seo_files(folder):
    """The page's current paste files: to-post/2-paste-into-cms first, then cms-fields, then preview.html."""
    f = Path(folder)
    for d in (f / "to-post" / "2-paste-into-cms", f / "cms-fields"):
        if d.is_dir():
            htmls = sorted(d.glob("*.html"), key=lambda p: p.stat().st_size, reverse=True)
            if htmls:
                return d, htmls[0]
    return (f, f / "preview.html") if (f / "preview.html").is_file() else (None, None)


def _seo_parse(html):
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.skip, self.heads, self.imgs, self.links, self.cur, self.link = 0, [], [], [], None, None

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag in ("style", "script", "noscript"):
                self.skip += 1
                return
            if self.cur and tag in ("span", "b", "strong", "em", "a", "div", "p") and self.cur[1]:
                self.cur[1].append(_JOIN)
            if tag in ("h1", "h2", "h3", "h4", "h5", "h6") and not self.cur:
                self.cur = [tag, []]
            elif tag == "br" and self.cur:
                self.cur[1].append(" ")
            elif tag == "img":
                self.imgs.append(a)
                if self.link is not None and a.get("alt"):
                    self.link[1].append(a["alt"])
            elif tag == "a":
                self.link = [a, []]

        def handle_endtag(self, tag):
            if tag in ("style", "script", "noscript"):
                self.skip = max(0, self.skip - 1)
            elif self.cur and tag == self.cur[0]:
                self.heads.append((tag, "".join(self.cur[1])))
                self.cur = None
            elif tag == "a" and self.link is not None:
                self.links.append((self.link[0], " ".join("".join(self.link[1]).split())))
                self.link = None

        def handle_data(self, data):
            if self.skip:
                return
            if self.cur:
                self.cur[1].append(data)
            if self.link is not None:
                self.link[1].append(data)

    p = P()
    p.feed(html)
    return p


def seo_check(folder):
    """Automatic SEO check of one page's current files -> ([{lvl: fix|check, msg}], info). One line per problem type."""
    out = []
    add = lambda lvl, msg: out.append({"lvl": lvl, "msg": msg})
    eg = lambda xs: "; ".join(xs[:3]) + (f"; +{len(xs) - 3} more" if len(xs) > 3 else "")
    d, page = _seo_files(folder) if folder and Path(folder).is_dir() else (None, None)
    if not page:
        return [{"lvl": "check", "msg": "No page files found to check (no to-post, cms-fields or preview.html)."}], None
    rd = lambda n: (d / n).read_text(encoding="utf-8", errors="ignore").strip() if (d / n).is_file() else None
    title, desc, url = rd("meta-title.txt"), rd("meta-description.txt"), rd("page-url.txt")
    if title is None and desc is None:
        if url is not None:   # city pages carry meta files; older MLP packs never had them
            add("check", "No meta title / description files in the pack - make sure the CMS page has both.")
    elif title is None:
        add("check", "No meta-title.txt - make sure the CMS page has a meta title.")
    elif not title:
        add("fix", "Meta title is empty.")
    elif len(title) > 60:
        add("check", f"Meta title is {len(title)} characters - search results cut it near 60: \"{title}\"")
    elif len(title) < 25:
        add("check", f"Meta title is short ({len(title)} characters): \"{title}\"")
    if desc is None:
        if title is not None:
            add("check", "No meta-description.txt - make sure the CMS page has a meta description.")
    elif not desc:
        add("fix", "Meta description is empty.")
    elif len(desc) > 160:
        add("check", f"Meta description is {len(desc)} characters - search results cut it near 160.")
    elif len(desc) < 70:
        add("check", f"Meta description is short ({len(desc)} characters).")
    if url:
        path = re.sub(r"^https?://[^/]+", "", url.split()[0])
        if re.search(r"[A-Z _]", path):
            add("fix", f"Page URL has capitals, spaces or underscores: {url}")
    p = _seo_parse(page.read_text(encoding="utf-8", errors="ignore"))
    zw = lambda x: re.sub("[​-‍﻿]", "", x)
    heads = [(t, re.sub(r"\s+", " ", zw(x).replace(_JOIN, "")).strip(), zw(x)) for t, x in p.heads]
    h1 = [h for h in heads if h[0] == "h1"]
    if len(h1) > 1:
        add("fix", f"{len(h1)} H1 headings - a page should have one: " + eg([f'"{h[1][:50]}"' for h in h1]))
    elif not h1:
        add("check", "No H1 in the page - fine only if the site template gives the page its H1.")
    last, caps_h, glued_h, jumps, empty = 1, [], [], [], []
    for t, txt, raw in heads:
        lvl = int(t[1])
        if not txt:
            empty.append(t.upper())
            continue
        if lvl > last + 1:
            jumps.append(f"H{last} -> {t.upper()} \"{txt[:40]}\"")
        last = lvl
        caps = [m.group(0) for m in re.finditer(r"\b[A-Z][A-Z'’]{2,}\b(?![®™℠])", re.sub(r"\([A-Z][A-Z0-9]{1,6}\)", "", txt))  # "(FCA)" acronym   # X-MODE® = brand mark, keeps caps
                if re.sub("['’]", "", m.group(0)) not in _OK_CAPS]
        if caps:
            caps_h.append(f"{t.upper()} \"{txt[:45]}\"")
        glued = [m.group(1) for m in re.finditer(r"([A-Za-z]*[a-z]{2}[A-Z][A-Za-z]*)(.?)", txt)
                 if m.group(2) not in "®™℠" or not m.group(2)]   # brand words followed by (R)/TM are fine
        glued = [g for g in glued if not _OK_CAMEL.match(g)]
        glued += [f"{a}|{b}" for a, b in re.findall("([A-Za-z0-9.,]+)" + _JOIN + "([A-Za-z0-9]+)", raw)]
        glued += re.findall(r"[a-z][.,!?:;][A-Za-z]", txt)
        if glued:
            glued_h.append(f"{t.upper()} \"{txt[:50]}\" ({', '.join(dict.fromkeys(glued[:3]))})")
    if empty:
        add("fix", f"{len(empty)} empty heading(s): {', '.join(empty[:5])}")
    if glued_h:
        add("fix", f"{len(glued_h)} heading(s) missing a space between words: {eg(glued_h)}")
    if caps_h:
        add("fix", f"{len(caps_h)} heading(s) typed in ALL CAPS - write Title Case, uppercase via CSS: {eg(caps_h)}")
    if jumps:
        add("check", f"{len(jumps)} heading level jump(s) (skips a level): {eg(jumps)}")
    no_alt = [i.get("src", "")[-40:] for i in p.imgs if "alt" not in i]
    if no_alt:
        add("fix", f"{len(no_alt)} image(s) with no alt text: {eg(no_alt)}")
    empty_alt = sum(1 for i in p.imgs if "alt" in i and not (i.get("alt") or "").strip())
    if empty_alt:
        add("check", f"{empty_alt} image(s) with empty alt - fine for decoration only, describe real photos.")
    bare = [a.get("href", "")[:50] for a, txt in p.links if not txt and not a.get("aria-label") and not a.get("title")]
    if bare:
        add("fix", f"{len(bare)} link(s) with no text: {eg(bare)}")
    vague = [f"\"{txt}\"" for a, txt in p.links if txt.lower() in _VAGUE]
    if vague:
        add("check", f"{len(vague)} link(s) with vague text ({', '.join(dict.fromkeys(vague))}) - say where the link goes.")
    return out, {"file": str(page), "title": title, "desc": desc, "url": url, "headings": [[t, x] for t, x, _r in heads][:40]}


def _page_text(folder):
    """Everything a QA SEO point could quote, normalised: the page's visible text + URL + meta title/description."""
    import html as _h
    sys.path.insert(0, str(HERE))
    d, page = _seo_files(folder)
    if not page:
        return ""
    src = page.read_text(encoding="utf-8", errors="ignore")
    src = re.sub(r"<(script|style)\b.*?</\1\s*>", " ", src, flags=re.S | re.I)
    txt = _h.unescape(re.sub(r"<br\s*/?>", " ", re.sub(r"<(?!br)[^>]+>", " ", src, flags=re.I), flags=re.I))
    extra = " ".join((d / n).read_text(encoding="utf-8", errors="ignore") for n in ("page-url.txt", "meta-title.txt", "meta-description.txt")
                     if (d / n).is_file())
    return _norm_q(txt + " " + extra)


def _norm_q(t):
    t = re.sub("[​-‍﻿]", "", str(t)).replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", t).strip().lower()


def _qa_point_done(point, text):
    """True/False when QA quoted the new value (URL, heading, title) and we can look for it; None = nothing to look for."""
    quotes = [q.strip() for q in re.findall(r"[\"“]([^\"“”]{3,220})[\"”]", point)]
    if not quotes or not text:
        return None
    return all(_norm_q(q).rstrip("/.") in text for q in quotes)


def _rev_dirs(it):
    """Every QA revision folder of a page: <page folder>/revisions/* and the tracker's revisions/<subitem id>/*."""
    out = []
    for base in ([Path(it["folder"]) / "revisions"] if it.get("folder") else []) + [HERE / "revisions" / str(it["subitem_id"])]:
        if base.is_dir():
            out += [d for d in base.iterdir() if d.is_dir() and (d / "revision.txt").is_file()]
    return sorted({d.name: d for d in out}.values(), key=lambda d: d.name, reverse=True)


def _city_slug(mlp):
    return re.sub(r"[^a-z0-9]+", "-", str(mlp).lower()).strip("-")          # "Buena Vista, GA" -> "buena-vista-ga"


def _qa_points(raw):
    """QA's numbered points of one revision.txt -> [(n, point)] (an intro line before "1." is not a point)."""
    sys.path.insert(0, str(HERE))
    from production import split_points  # noqa: E402
    pts, _ps = split_points(raw)
    nums = len(re.findall(r"(?:^|\s)\d{1,2}\.\s+[A-Z]", raw))
    off = max(0, len(pts) - nums) if nums else 0
    return [(n, re.sub(r"\s+", " ", pt).strip()) for n, pt in enumerate(pts, 1 - off)]


_QUOTE = re.compile(r"[\"“]([^\"“”]{3,220})[\"”]")


def _quote_rx(q, src_city=None):
    """Regex for a quoted value; for a revision copied from another city page, that city's name/slug is a wildcard."""
    nq = _norm_q(q).rstrip("/.")
    rx = re.escape(nq)
    if src_city:
        name = _norm_q(src_city.split(",")[0])
        for tok in sorted({re.escape(_city_slug(src_city)), re.escape(_city_slug(name)), re.escape(name)}, key=len, reverse=True):
            rx = rx.replace(tok, r"[\w .'/-]{2,40}?")
    return rx


def _seo_point(pt, text, heads_text, src_city=None):
    """-> (is_seo, done). SEO = SEO words, or a quoted value that is (or belongs in) a heading, URL or meta title
    ("change this section to "Why Auburn Drivers Choose"" is an H2 change). done = every quoted value is on the page."""
    low = pt.lower()
    quotes = [q.strip() for q in _QUOTE.findall(pt)]
    kw = any(re.search(r"\b" + re.escape(k), low) for k in SEO_KEYS)
    rxs = [_quote_rx(q, src_city) for q in quotes]
    in_heads = any(re.search(rx, heads_text) for rx in rxs) if heads_text else False
    heading_ask = bool(quotes) and re.search(r"\b(section|title|headline|heading|header)\b", low)
    if not (kw or in_heads or heading_ask):
        return False, None
    if not quotes or not text:
        return True, None
    return True, all(re.search(rx, text) for rx in rxs)


def _seo_qa(it, items, text, heads_text):
    """QA's SEO revision points for one page, newest revision first. A city page whose comment only says "apply the same
    revision from the Auburn, AL page" gets Auburn's points, checked against this city's own name/URL."""
    out = []
    for d in _rev_dirs(it)[:4]:
        raw = (d / "revision.txt").read_text(encoding="utf-8", errors="ignore")
        if re.search(r"instructions for building the landing page|here is the backend access", raw, re.I):
            continue                                   # the build brief, not a QA revision
        src, src_city = None, None
        m = re.search(r"same revision(?:s)? (?:from|as|on) (?:the )?(.+?) (?:city )?page", raw, re.I)
        if m:
            name = m.group(1).strip().lower()
            src = next((o for o in items if o is not it and o["dealer"] == it["dealer"] and str(o["mlp"]).lower().startswith(name)), None)
        if src:
            sd = next((x for x in _rev_dirs(src) if x.name.split("_")[0] <= d.name.split("_")[0]), None)
            if not sd:
                continue
            raw, src_city = (sd / "revision.txt").read_text(encoding="utf-8", errors="ignore"), src["mlp"]
        for n, pt in _qa_points(raw):
            seo, done = _seo_point(pt, text, heads_text, src_city)
            if seo:
                out.append({"rev": d.name, "n": n, "point": pt[:300], "done": done, "from": src_city})
    return out


def seo_review():
    """SEO tab (calm version, user 2026-11-17: "I want to see if there are seo that needs revision ... not too
    overwhelming"). Every tracker page with files gets one automatic status:
      fix     - something needs an SEO fix: a red item from the automatic check, or QA's SEO request not in the page yet
      working - QA sent an SEO revision and Claude has not finished it
      done    - nothing needs fixing
    Amber items from the check are suggestions only (copy/design calls) and never make a page "fix"."""
    sys.path.insert(0, str(HERE))
    from production import split_points  # noqa: E402
    import hashlib
    st = read_json(STATE, {})
    seen = read_json(SEO_SEEN, {})
    pages = []
    for it in st.get("items", []):
        folder = it.get("folder")
        if not folder or not Path(folder).is_dir():
            continue
        issues, info = seo_check(folder)
        if not info:
            continue
        text = _page_text(folder)
        heads_text = _norm_q(" ".join(h for _t, h in info["headings"]) + " " + " ".join(str(info.get(k) or "") for k in ("url", "title", "desc")))
        qa = _seo_qa(it, st.get("items", []), text, heads_text)
        fixes = [i["msg"] for i in issues if i["lvl"] == "fix"]
        tips = [i["msg"] for i in issues if i["lvl"] == "check"]
        pending = it.get("claude") in ("Revision needed", "Claude working on it")
        not_done = [p for p in qa if p["done"] is False]
        if pending and qa:
            status = "working"
        elif fixes or not_done:
            status = "fix"
        else:
            status = "done"
        needs = fixes + [f"QA asked: {p['point']}" for p in not_done]
        sig = hashlib.sha1("|".join(needs).encode("utf-8")).hexdigest()[:12]   # "Mark reviewed" lasts until the problems change
        pages.append({"sig": sig, "reviewed": status == "fix" and seen.get(str(it["subitem_id"])) == sig,"sid": it["subitem_id"], "dealer": it["dealer"], "mlp": it["mlp"], "status": status,
                      "city": bool(re.search(r", [A-Z]{2}$", str(it.get("mlp")))), "needs": needs, "tips": tips,
                      "qa": qa, "auto": _seo_auto_count(folder) if fixes else 0, "info": info, "monday": it.get("status")})
    order = {"fix": 0, "working": 1, "done": 2}
    pages.sort(key=lambda x: (order[x["status"]], x["dealer"], x["mlp"]))
    count = {k: sum(1 for x in pages if x["status"] == k and not x["reviewed"]) for k in order}
    count["reviewed"] = sum(1 for x in pages if x["reviewed"])
    return {"pages": pages, "count": count, "to_review": count["fix"]}


def _seo_auto_count(folder):
    """How many SEO fixes seo_fix.py can make in the HTML (no browser - just the plan)."""
    try:
        sys.path.insert(0, str(HERE))
        import seo_fix  # noqa: E402
        htmls, _css = seo_fix.page_files(folder) if folder and Path(folder).is_dir() else ([], [])
        if not htmls:
            return 0
        _new, rep = seo_fix.transform(htmls[0].read_text(encoding="utf-8", errors="ignore"))
        return len(rep["caps"]) + len(rep["spaces"]) + rep["alts"]
    except Exception:   # noqa: BLE001 - the tab must still load
        return 0


def seo_autofix(items):
    """Run seo_fix.py on each page (one at a time); -> per-page results. items = [(sid, dealer, mlp, folder)]."""
    out = []
    for sid, dealer, mlp, folder in items:
        r = subprocess.run([sys.executable, str(HERE / "seo_fix.py"), str(folder), "--sid", str(sid)], cwd=str(HERE),
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            res = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            res = {"fixed": 0, "error": (r.stderr or r.stdout or "no output")[-300:]}
        res.update({"sid": sid, "page": f"{dealer} - {mlp}"})
        out.append(res)
    return out


def seo_mark(sids, last_revs, done=True):
    """Mark pages SEO reviewed (or undo). sids/last_revs are parallel lists so a city batch is one click."""
    seen = read_json(SEO_SEEN, {})
    for sid, last in zip(sids, last_revs):
        if done:
            seen[str(sid)] = str(last)
        else:
            seen.pop(str(sid), None)
    write_json(SEO_SEEN, seen)
    return {"ok": True}
