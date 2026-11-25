"""MLP Tracker web app (Phase 1) - runs locally, replaces the Excel workbook (user, 2026-11-13).

Start:  python webapp/server.py      (or double-click start_tracker.cmd)  ->  http://127.0.0.1:8765
Reads the files the automation (Claude Code) writes: tracker_state.json, history.json, work_log.md, project folders.
Writes only what the user edits (Notes, Next Up, monday Status override) into tracker_state.json, under the same
.tracker.lock the engine uses, so a refresh never overwrites an edit. Listens on 127.0.0.1 only. monday is never touched.
"""
import json
import mimetypes
import os
import re
import shutil
import sys
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

APP = Path(__file__).resolve().parent
HERE = APP.parent
STATE, HIST, LOG = HERE / "tracker_state.json", HERE / "history.json", HERE / "work_log.md"
AUTO, LOCK = HERE / "automation_state.json", HERE / ".tracker.lock"
sys.path.insert(0, str(HERE))
import settings  # noqa: E402
import plat  # noqa: E402   (Windows / Mac differences, 2026-11-19)
sys.path.insert(0, str(APP))
import features  # noqa: E402
import blogs  # noqa: E402   (Blogs tab, 2026-11-17)
import buildmemory  # noqa: E402   (Settings > My build memory, 2026-11-19)
import batch  # noqa: E402   (batch city pages: sample first, then copy, 2026-11-20)


def roots():
    c = settings.load()
    return [Path(c["mlp_root"]), Path(c["city_root"]), HERE]
FILE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".txt", ".md"}
PORT = 8765


def read_json(p, default):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return default


def work_log():
    out, day = [], None
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                day = line[3:].strip()
            elif day and line.startswith("- "):
                m = re.match(r"- (\d{1,2}:\d{2}) (.*)", line)
                if m:
                    out.append([f"{day} {m.group(1).zfill(5)}", m.group(2)])
    return out


def version():
    return max((p.stat().st_mtime for p in (STATE, HIST, LOG, AUTO) if p.exists()), default=0)


def allowed(p):
    try:
        rp = Path(p).resolve()
    except OSError:
        return False
    return any(str(rp).lower().startswith(str(r).lower()) for r in roots()) and rp.suffix.lower() in FILE_EXT and rp.is_file()


def item_detail(sid):
    st = read_json(STATE, {})
    it = next((i for i in st.get("items", []) if str(i["subitem_id"]) == str(sid)), None)
    if not it:
        return {"error": "not found"}
    folder = Path(it["folder"]) if it.get("folder") and Path(it["folder"]).is_dir() else None
    rev_dirs = []
    for base in ([folder / "revisions"] if folder else []) + [HERE / "revisions" / str(sid)]:
        if base.is_dir():
            rev_dirs += [d for d in base.iterdir() if d.is_dir()]
    revs = []
    for d in sorted(rev_dirs, key=lambda x: x.name, reverse=True):
        rd = lambda n: (d / n).read_text(encoding="utf-8", errors="ignore") if (d / n).exists() else ""
        revs.append({"name": d.name, "revision": rd("revision.txt"), "checklist": rd("checklist.md"),
                     "images": [str(x) for x in sorted(d.iterdir()) if x.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif")]})
    det = {"item": it, "folder": str(folder) if folder else None, "revisions": revs, "before_after": [], "review_note": "",
           "to_post": None, "to_upload": []}
    if folder:
        ba = folder / "before-after"
        if ba.is_dir():
            det["before_after"] = [str(x) for x in sorted(ba.glob("*.png"))]
        if (folder / "ready-for-review.txt").exists():
            det["review_note"] = (folder / "ready-for-review.txt").read_text(encoding="utf-8", errors="ignore")
        if (folder / "to-post" / "README.txt").exists():
            det["to_post"] = (folder / "to-post" / "README.txt").read_text(encoding="utf-8", errors="ignore")
        if (folder / "to-upload.txt").exists():
            det["to_upload"] = [l.strip() for l in (folder / "to-upload.txt").read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    return det


def edit_state(sid, field, value):
    """User edits -> tracker_state.json under the engine's lock (the engine reads them back on every run)."""
    if field not in ("notes", "next", "posted"):   # "status" removed (user, 2026-11-16): monday is the only place to change it
        return {"error": "field not editable"}
    for _ in range(60):
        if not LOCK.exists() or time.time() - LOCK.stat().st_mtime > 300:
            break
        time.sleep(1)
    else:
        return {"error": "the automation is updating the tracker - try again in a moment"}
    LOCK.write_text(f"webapp {os.getpid()} {datetime.now():%Y-%m-%d %H:%M:%S}")
    try:
        st = read_json(STATE, {})
        for it in st.get("items", []):
            if str(it["subitem_id"]) == str(sid):
                if field == "next":
                    value = int(value) if str(value).strip().isdigit() else (None if not str(value).strip() else value)
                if field == "posted":                 # True = posted now (user, 2026-11-13: "Mark pages as posted")
                    value = datetime.now().strftime("%Y-%m-%d %H:%M") if value else None
                it[field] = value if value != "" else None
                break
        else:
            return {"error": "not found"}
        tmp = str(STATE) + ".tmp"
        json.dump(st, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, STATE)
        hist = read_json(HIST, [])
        hist.insert(0, [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), it["dealer"], it["mlp"],
                        ("You marked it as posted (uploaded + pasted in the CMS)" if field == "posted" and value else
                         "You undid 'posted'" if field == "posted" else
                         f"You changed {'Notes' if field == 'notes' else 'Next Up' if field == 'next' else 'monday Status'} in the web app" +
                         (f": {value}" if field != "notes" else "")), it.get("claude")])
        json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        if field == "posted":                     # recompute "Your next step" right away (engine reads 'posted' back)
            threading.Thread(target=lambda: subprocess.run([sys.executable, "-I", str(HERE / "build_mlp_tracker.py")], cwd=str(HERE),
                             capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)), daemon=True).start()
        return {"ok": True}
    finally:
        try:
            LOCK.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------- Phase 2: run Claude Code from the page (2026-11-13)
import subprocess
import threading

CLAUDE = plat.claude_exe()   # found on this PC / Mac (was a fixed Windows path)
JOBS = APP / "jobs"
JOB = {"proc": None, "action": None, "started": None, "log": None, "ended": None, "code": None}
JLOCK = threading.Lock()
BASE_TOOLS = ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "mcp__claude_ai_monday_com__all_api_read"]
PROMPTS = {
    "refresh": (
        "refresh  (sent from the MLP Tracker web app). Follow REFRESH.md in this folder exactly: steps 1 to 5, including "
        "2b revisions, 4c clean-up, city pages and the production routine for new MLPs. monday is READ-ONLY - only use the "
        "monday all_api_read tool, never write to monday. Run build_mlp_tracker.py once at the end (Excel is off; the web "
        "app shows tracker_state.json). Log the refresh with summary.py --log. Finish with a short plain report.",
        BASE_TOOLS, 80),
    "start": (
        "start  (sent from the MLP Tracker web app). Set the automation to Running and work the queue top-down exactly as "
        "REFRESH.md and the MLP build standards say (revisions first, then Assigned MLPs; QA sweep before marking done; "
        "upload pack + before/after + Claude's Notes after every revision; no questions to the user - decide by the QA "
        "rules). EVERY revision (Final MLP, Final Mobile Check or City Page) also gets the Final mobile check after the QA "
        "sweep: run {FMC}, fix every FIX line and run it again until there are none, then look at "
        "the qa/final-mobile/390-*.png screenshots against the 'Mobile (Final Mobile Check)' rules in _mlp-toolkit/qa_feedback.md "
        "and fix what fails; write 'Final mobile check: passed (390/375/430) ...' in the revision note. monday is READ-ONLY. Stop when the queue is empty or when automation_state.json says Stopped. "
        "SEO auto-fix (every build and every revision, after the page is built/fixed and before the QA sweep): run python seo_fix.py '<project folder>' --sid <subitem id> - it turns ALL-CAPS headings into Title Case with CSS uppercase, adds missing spaces in headings and missing alt text, in every copy of the page, and checks the look. Re-run split_fields/production.py pack only if you change preview.html afterwards. "
        "CITY PAGES - design once, content per page (user rule 2026-11-20): when 2 or more city pages of the same dealer are in the queue (new or the same QA revision), build or fix ONE first and give that one the full design check (QA sweep + Final mobile check + screenshots). Make or fix the others from it and give each only a CONTENT check: none of the first page's city/state left (text, headings, meta, alt, file names, URLs), its own content doc word for word (nothing missing, nothing from the other doc), same sections/classes/buttons, its own links; look at a section in Edge (1920 + 390) only when its text is clearly longer/shorter than the checked page's (about 30%+, or an extra/missing list item). Note: 'Content checked; design from <checked page>'. "
        "Before marking any page done, open webapp/dealer_lessons.md and check every lesson listed for that page's "
        "dealer (what QA keeps sending back) - fix any that fail, and write 'Dealer lessons checked' in the note. "
        "If a monday connector call fails run: python monday_health.py connector error '<short error>' (and "
        "python monday_health.py connector ok once one works again). "
        "Report progress to the web app at every step with: python progress.py '<Dealer> - <MLP>' '<step>' '<n>/<total>' "
        "(steps: Picked up, Reading QA / brief, Building, Fixing revision, SEO auto-fix, QA check, Final mobile check, Before/after, Upload pack, Done; "
        "'-' 'Queue empty' at the end). Finish with a short plain report.",
        BASE_TOOLS + ["Skill", "WebFetch", "mcp__claude_ai_Google_Drive__read_file_content", "mcp__claude_ai_Google_Drive__search_files",
                      "mcp__figma__create_session", "mcp__figma__get_metadata", "mcp__figma__get_design_context", "mcp__figma__get_screenshot",
                      "ReadMcpResourceTool"], 400),
}


def has_token():
    return bool(settings.token())


# ---------------------------------------------------------------- Settings tab (user, 2026-11-13)
def qa_file():
    return Path(settings.get("toolkit_root")) / "qa_feedback.md"


def settings_view():
    c = settings.load()
    st = read_json(STATE, {})
    dealers = {}
    for i in st.get("items", []) + st.get("approved", []):
        if i.get("platform") or i["dealer"] not in dealers:
            dealers[i["dealer"]] = dealers.get(i["dealer"]) or i.get("platform") or ""
    qf = qa_file()
    return {"config": {k: c.get(k) for k in settings.TYPES}, "token_hint": settings.token_hint(), "figma_hint": settings.figma_hint(), "figma_meta": features.figma_key_status(),
            "token_file": str(settings.TOKEN_FILE), "platforms": settings.PLATFORMS,
            "dealers": [{"dealer": d, "platform": p} for d, p in sorted(dealers.items(), key=lambda x: x[0].lower())],
            "qa_path": str(qf), "qa_text": qf.read_text(encoding="utf-8") if qf.exists() else "",
            "config_file": str(settings.CONFIG)}


def check_token():
    r = subprocess.run([sys.executable, "-I", str(HERE / "refresh_monday.py"), "--check"], cwd=str(HERE),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    out = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
    return r.returncode == 0, (out[-1] if out else "no answer")


def save_token(t):
    old = settings.token() if settings.TOKEN_FILE.exists() else ""
    err = settings.save_token(t)
    if err:
        return {"error": err}
    ok, msg = check_token()
    if not ok:                                  # keep the old token when the new one is refused
        if old:
            settings.TOKEN_FILE.write_text(old + chr(10), encoding="utf-8")
        else:
            settings.TOKEN_FILE.unlink(missing_ok=True)
        return {"error": "monday refused that token - nothing changed. " + msg}
    log_history("monday token updated on the Settings tab")
    return {"ok": True, "msg": msg}


# ---------------------------------------------------------------- new-user setup (2026-11-23, user: "add like a log in
# form ... for new users so that before they enter the interface everything is already set up"). Not a password login:
# a first-open form that fills the monday token (-> your name + id), folders and shift, and checks the tools.
def setup_status():
    c = settings.load()
    folders = {k: {"path": c.get(k) or "", "ok": bool(c.get(k)) and Path(c.get(k)).is_dir()}
               for k in ("mlp_root", "city_root", "toolkit_root")}
    tools = {"claude": Path(CLAUDE).exists() or bool(shutil.which("claude")),
             "vscode": Path(plat.vscode()).exists() or bool(shutil.which("code")),
             "node": bool(shutil.which("node")),
             "toolkit_qa": (Path(c.get("toolkit_root") or ".") / "tools" / "qa").is_dir()}
    tok = has_token()
    # an existing install that already works (token + your name) counts as set up - the form is for new users only
    done = bool(c.get("setup_done")) or (tok and bool(c.get("owner_name")) and int(c.get("owner_id") or 0) > 0)
    return {"done": done, "token": tok, "token_hint": settings.token_hint(), "owner_name": c.get("owner_name") or "",
            "owner_id": c.get("owner_id") or 0, "folders": folders, "tools": tools,
            "shift_start": c.get("shift_start"), "shift_hours": c.get("shift_hours"),
            "token_file": str(settings.TOKEN_FILE)}


def setup_save(body):
    """One step of the setup form: {"step": "token"|"folders"|"shift"|"finish", ...}."""
    step = body.get("step")
    if step == "token":
        if body.get("token"):
            r = save_token(body.get("token"))
            if r.get("error"):
                return r
        elif not has_token():
            return {"error": "Paste your monday token first."}
        ok, msg = check_token()                    # "Token OK - monday user: Name (12345)"
        m = re.search(r"monday user: (.+) \((\d+)\)", msg or "")
        if not ok or not m:
            return {"error": "monday did not answer with your name: " + (msg or "no answer")}
        err = settings.save({"owner_name": m.group(1).strip(), "owner_id": int(m.group(2))})
        return {"error": err} if err else {"ok": True, "owner_name": m.group(1).strip(), "owner_id": int(m.group(2))}
    if step == "folders":
        ch = {}
        for k in ("mlp_root", "city_root", "toolkit_root"):
            v = str(body.get(k) or "").strip().strip('"')
            if not v:
                return {"error": "Fill in every folder."}
            if not Path(v).is_dir():
                if k != "toolkit_root" and body.get("create"):
                    try:
                        Path(v).mkdir(parents=True, exist_ok=True)
                    except OSError as e:
                        return {"error": f"Could not make {v}: {e}"}
                else:
                    return {"error": f"Folder not found: {v}" + ("" if k == "toolkit_root" else " - tick 'Make missing folders' to create it"),
                            "missing": k}
            ch[k] = v
        err = settings.save(ch)
        return {"error": err} if err else {"ok": True}
    if step == "shift":
        err = settings.save({"shift_start": body.get("shift_start"), "shift_hours": body.get("shift_hours")})
        return {"error": err} if err else {"ok": True}
    if step == "finish":
        st = setup_status()
        if not st["token"] or not st["owner_name"]:
            return {"error": "The monday step is not finished yet."}
        if not all(f["ok"] for f in st["folders"].values()):
            return {"error": "A folder is still missing - go back to Folders."}
        err = settings.save({"setup_done": True})
        if err:
            return {"error": err}
        log_history(f"New-user setup finished for {st['owner_name']}")
        return {"ok": True}
    return {"error": "unknown setup step"}


# ---------------------------------------------------------------- Figma key (2026-11-20, user: "lets proceed with figma key")
def figma_tool():
    return Path(settings.get("toolkit_root")) / "tools" / "figma_layout.py"


def check_figma():
    try:
        r = subprocess.run([sys.executable, "-I", str(figma_tool()), "--check"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as e:
        return False, str(e)
    out = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
    return r.returncode == 0, (out[-1] if out else "no answer")


def save_figma_token(t, expires=""):
    old = settings.figma_token() if settings.FIGMA_TOKEN_FILE.exists() else ""
    err = settings.save_figma_token(t)
    if err:
        return {"error": err}
    ok, msg = check_figma()
    if not ok:                                  # keep the old key when the new one is refused
        if old:
            settings.FIGMA_TOKEN_FILE.write_text(old + chr(10), encoding="utf-8")
            check_figma()                       # re-check the old key so the red "refused" line is only shown when it is true
        else:
            settings.FIGMA_TOKEN_FILE.unlink(missing_ok=True)
            settings.FIGMA_REFUSED.unlink(missing_ok=True)
        return {"error": "Figma refused that key - nothing changed. " + msg}
    settings.save_figma_meta(expires_ok(expires), saved=time.strftime("%Y-%m-%d"))   # new key = new expiry date
    log_history("Figma key saved on the Settings tab")
    return {"ok": True, "msg": msg}


def expires_ok(s):
    s = (s or "").strip()
    return s if re.fullmatch(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]", s) else ""


def save_figma_expiry(s):
    if not settings.figma_token():
        return {"error": "Save the Figma key first."}
    m = settings.save_figma_meta(expires_ok(s))
    return {"ok": True, "msg": "Expiry date saved: " + m["expires"] + (" (a guess - 90 days after saving)" if m.get("estimated") else "")}


def save_settings(changes):
    err = settings.save(changes or {})
    if err:
        return {"error": err}
    if "platform_overrides" in (changes or {}):   # rebuild so the Platform column shows it right away
        subprocess.Popen([sys.executable, "-I", str(HERE / "build_mlp_tracker.py")], cwd=str(HERE),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    log_history("Settings changed: " + ", ".join(sorted(changes)))
    return {"ok": True, "msg": "Settings saved"}


def save_qa(text):
    qf = qa_file()
    if not isinstance(text, str) or not text.strip():
        return {"error": "The QA rules can't be empty"}
    if qf.exists():                              # one backup of the previous version
        qf.with_name("qa_feedback.bak.md").write_text(qf.read_text(encoding="utf-8"), encoding="utf-8")
    qf.write_text(text.replace(chr(13) + chr(10), chr(10)), encoding="utf-8")
    log_history("QA rules (qa_feedback.md) edited on the Settings tab")
    return {"ok": True, "msg": "QA rules saved (previous version kept as qa_feedback.bak.md)"}


# ---------------------------------------------------------------- reconnect after a restart (user, 2026-11-16, update 3)
# A restart of the server (code reload, keep-alive) used to forget a Claude job that was still running: Stop and the
# header could not see it. Each job's process id is saved in jobs/current.json; on start-up the server picks it up again.
JOB_FILE = JOBS / "current.json"


class PidProc:
    """Stand-in for a Popen of a job started by an earlier server: poll() / pid / returncode (plat.exit_code:
    Windows API on Windows, a signal-0 check on Mac)."""
    def __init__(self, pid):
        self.pid, self.returncode = int(pid), None

    def poll(self):
        if self.returncode is not None:
            return self.returncode
        code = plat.exit_code(self.pid)
        if code is None:
            return None
        self.returncode = code
        return self.returncode


def save_job_file(p):
    try:
        JOBS.mkdir(exist_ok=True)
        keep = {k: JOB.get(k) for k in ("action", "started", "log", "claude", "page", "sid", "chain")}
        JOB_FILE.write_text(json.dumps(dict(keep, pid=p.pid), ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def reattach_job():
    """On start-up: a job from before the restart that is still running becomes the current job again."""
    j = read_json(JOB_FILE, None)
    if not j or not j.get("pid"):
        return
    out = plat.process_name(j["pid"])                 # tasklist on Windows, ps on Mac
    exe = "claude" if j.get("claude") else "python"
    if exe not in out:                                    # finished (or the id now belongs to something else)
        JOB_FILE.unlink(missing_ok=True)
        return
    with JLOCK:
        JOB.update({"proc": PidProc(j["pid"]), "action": j.get("action"), "started": j.get("started"), "log": j.get("log"),
                    "ended": None, "code": None, "claude": j.get("claude"), "page": j.get("page"), "sid": j.get("sid"),
                    "activity": "Still running from before the tracker restarted (live details come back with the next job)",
                    "tokens": None, "result": None, "stopped_by_user": False, "reattached": True, "chain": j.get("chain")})
        if j.get("chain"):   # a Start queue run survived the restart: keep the queue going after it
            c = j["chain"][6:] if str(j["chain"]).startswith("blogs:") else None
            CHAIN.update({"on": True, "tried": [[j.get("action"), str(j.get("sid") or "")]], "pos": 1, "total": 1, "runs": 1, "started": j.get("started"), "cms": c})
    try:
        with open(j["log"], "a", encoding="utf-8") as f:
            f.write(chr(10) + f"{datetime.now():%Y-%m-%d %H:%M:%S}  tracker restarted - reconnected to this job (pid {j['pid']})" + chr(10))
    except (OSError, TypeError):
        pass


def restore_last_job():
    """On start-up with nothing running (2026-11-20 bug scan): bring back the last finished Claude run from
    jobs/costs.json, so the header still says "Last start: finished 20:02 (log)" after a restart instead of nothing."""
    if JOB.get("action"):
        return
    rows = read_json(JOBS / "costs.json", [])
    if not rows or not rows[0].get("started"):
        return
    r = rows[0]
    try:
        log = JOBS / f"{datetime.strptime(r['started'], '%Y-%m-%d %H:%M:%S'):%Y%m%d-%H%M%S}-{r.get('action')}.log"
    except ValueError:
        return
    with JLOCK:
        JOB.update({"proc": None, "action": r.get("action"), "started": r["started"], "ended": r.get("ended") or r["started"],
                    "code": 0 if r.get("status") == "finished" else 1, "log": str(log) if log.exists() else None,
                    "claude": True, "page": None, "activity": None, "tokens": r.get("tokens"), "result": None})


def job_state():
    with JLOCK:
        p = JOB["proc"]
        running = p is not None and p.poll() is None
        if p is not None and not running and JOB["ended"] is None:
            JOB["ended"], JOB["code"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S"), p.returncode
            JOB_FILE.unlink(missing_ok=True)
            if JOB.get("action") == "refresh" and not JOB.get("claude"):   # header Refresh: loud if it failed (2026-11-25)
                tail = ""
                if JOB.get("log") and Path(JOB["log"]).exists():
                    tail = (Path(JOB["log"]).read_text(encoding="utf-8", errors="ignore").strip().splitlines() or [""])[-1]
                features.note_refresh(p.returncode == 0, tail)
            if JOB.get("action") == "start":   # the queue run is over: the header no longer says RUNNING (2026-11-19)
                threading.Thread(target=lambda: subprocess.run(
                    [sys.executable, "-I", str(HERE / "build_mlp_tracker.py"), "--automation", "Stopped"],
                    capture_output=True, cwd=str(HERE)), daemon=True).start()
        tail = ""
        if JOB["log"] and Path(JOB["log"]).exists():
            tail = "\n".join(Path(JOB["log"]).read_text(encoding="utf-8", errors="ignore").splitlines()[-40:])
        return {"running": running or CHAIN["on"], "proc_running": running, "action": "start" if JOB.get("chain") or CHAIN["on"] else JOB["action"],
                "unit": JOB["action"], "queue": {"pos": CHAIN["pos"], "total": CHAIN["total"], "cms": CHAIN.get("cms")} if CHAIN["on"] else None,
                "started": JOB["started"], "ended": JOB["ended"],
                "code": JOB["code"], "log": tail, "direct": has_token(), "activity": JOB.get("activity"),
                "tokens": JOB.get("tokens"), "result": JOB.get("result"), "claude": JOB.get("claude", False),
                "progress": features.progress_for(JOB["started"]) if JOB.get("claude") else None,
                "auto_refreshing": features.auto_running(), "page": JOB.get("page") if JOB.get("action") in ("fix", "fixgroup", "build", "blog", "batch", "batch-copy") else None}


def session_state():
    """What Claude is doing from VS Code (session_progress.py); shown while under 30 min old (Done: 10 min)."""
    s = read_json(Path(__file__).resolve().parent / "session_progress.json", {})
    try:
        age = (datetime.now() - datetime.strptime(s.get("at", ""), "%Y-%m-%d %H:%M:%S")).total_seconds() / 60
    except ValueError:
        return None
    return s if age < (10 if s.get("step") == "Done" else 30) else None


def log_history(text):
    hist = read_json(HIST, [])
    hist.insert(0, [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "", "", text, ""])
    json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=0)


def fmc_cmd():
    """Final mobile check command (2026-11-16), from Settings > Folders so the team copy points at its own toolkit."""
    return f'node "{Path(settings.get("toolkit_root")).as_posix()}/tools/qa/final_mobile_check.js" "<project folder>"'


def fix_prompt(sid):
    it = next((i for i in read_json(STATE, {}).get("items", []) if str(i["subitem_id"]) == str(sid)), None)
    if not it:
        return None, None
    name = f"{it['dealer']} - {it['mlp']}"
    lessons = features.dealer_lessons_text(it["dealer"])
    return name, (
        f"fix  (sent from the MLP Tracker 'Fix it now' button). Work ONLY the QA revision for {name} (subitem {sid}"
        f"{', a city page' if it.get('type') == 'City Page' else ''}"
        f"{'; its Final MLP is already approved - only the Final Mobile Check revision is open, change only what that asks and post only on the Final Mobile Check subitem' if it.get('mobile_only') else ''}) exactly as REFRESH.md and the MLP build standards say: read "
        "the newest revision in revisions/<id>/ (checklist.md + QA screenshots), fix every point, run the QA sweep, then the "
        "Final mobile check (on every revision, desktop ones too): run " + fmc_cmd() + ", fix every "
        "FIX line and run it again until there are none, look at the qa/final-mobile/390-*.png screenshots against the "
        "'Mobile (Final Mobile Check)' rules in _mlp-toolkit/qa_feedback.md and fix what fails (progress step 'Final mobile "
        "check'), put 'Final mobile check: passed (390/375/430) ...' in the note, make "
        "SEO auto-fix (every build and every revision, after the page is built/fixed and before the QA sweep): run python seo_fix.py '<project folder>' --sid <subitem id> - it turns ALL-CAPS headings into Title Case with CSS uppercase, adds missing spaces in headings and missing alt text, in every copy of the page, and checks the look. Re-run split_fields/production.py pack only if you change preview.html afterwards. "
        "before/after images, rebuild the upload pack (production.py pack), write 'Revision #N done: ...' with "
        "the 'CMS: ...' line production.py pack prints (which CMS fields changed and need pasting - user, 2026-11-25) "
        "in it, with "
        "build_mlp_tracker.py --note, and mark it 'Claude is done'. No questions to the user - decide by the QA rules. "
        + (f"Before marking it done, also check these lessons QA keeps sending back for {it['dealer']} (fix any that fail, "
           f"write 'Dealer lessons checked' in the note): {lessons} " if lessons else "") +
        "monday is READ-ONLY. If a monday connector call fails run python monday_health.py connector error '<short error>'. "
        "Do not start any other page. Report progress at every step with: python progress.py "
        f"'{name}' '<step>' '1/1'. Finish with a short plain report.")


def build_prompt(sid):
    """"Start now" on a pending page (user, 2026-11-19: "add a start now button for the projects that are pending"):
    Claude builds THIS page only, like a page picked from the Start queue, then stops."""
    it = next((i for i in read_json(STATE, {}).get("items", []) if str(i["subitem_id"]) == str(sid)), None)
    if not it:
        return None, None
    name = f"{it['dealer']} - {it['mlp']}"
    city = it.get("type") == "City Page"
    lessons = features.dealer_lessons_text(it["dealer"])
    return name, (
        f"build  (sent from the MLP Tracker 'Start now' button). Build ONLY {name} (subitem {sid}"
        f"{', a city page' if city else ''}) - this one page, then stop. Do not start any other page and do not change "
        "the automation state. First mark it with build_mlp_tracker.py --set " + str(sid) + " 'Claude working on it'. "
        "Build it exactly as REFRESH.md and the MLP build standards say for a new page from the queue: read the brief and "
        "the content doc on monday (production intake), the Figma, and the dealer's last page"
        + (" (city page: clone the dealer's latest approved city page and swap the city and the content - see the city "
           "pages part of REFRESH.md and the dealer's city-page project memory)" if city else "") + ". " +
        "SEO auto-fix (after the page is built, before the QA sweep): run python seo_fix.py '<project folder>' --sid "
        f"{sid}. Then the QA sweep, then the Final mobile check: run {fmc_cmd()}, fix every FIX line and run it again "
        "until there are none, look at the qa/final-mobile/390-*.png screenshots against the 'Mobile (Final Mobile "
        "Check)' rules in _mlp-toolkit/qa_feedback.md and fix what fails. "
        + (f"Before marking it done, check these lessons QA keeps sending back for {it['dealer']} (fix any that fail, "
           f"write 'Dealer lessons checked' in the note): {lessons} " if lessons else "") +
        "Register the folder (build_mlp_tracker.py --folder), make the upload pack (production.py pack), write what you "
        "built and every 'Decided: ...' with build_mlp_tracker.py --note, and mark it 'Claude is done'. No questions to "
        "the user - decide by the QA rules, then the Figma. monday is READ-ONLY. If a monday connector call fails run "
        "python monday_health.py connector error '<short error>'. Report progress at every step with: python progress.py "
        f"'{name}' '<step>' '1/1'. Finish with a short plain report.")


# ---------------------------------------------------------------- Start = one page per run (2026-11-25)
# user, 2026-11-25 ("go ahead with 1, 2 and 4"): the last Start runs took 111 and 126 minutes for 5 pages and blocked
# everything else. Now Start works the queue as a chain of short runs: one page (or one city-page batch / one dealer's
# city revisions) per Claude run, a quick monday check between runs (new revisions jump ahead), then the next run starts
# by itself - until the queue is empty or Stop. An empty queue does not start Claude at all.
CHAIN = {"on": False, "tried": [], "pos": 0, "total": 0, "started": None, "cms": None}   # cms set = a Blogs CMS queue
_s = PROMPTS["start"][0]
CITY_RULE = _s[_s.index("CITY PAGES - design once"):_s.index("Before marking any page done")]


def automation_running():
    return read_json(HERE / "automation_state.json", {}).get("state") == "Running"


def queue_units():
    """Claude's queue as runs, in order: revisions first, then new pages; each by due date. [(action, sid, name)]"""
    items = read_json(STATE, {}).get("items", [])
    due = lambda i: str(i.get("due") or "9999")
    units = []
    revs = sorted([i for i in items if i.get("claude") == "Revision needed" and i.get("status")], key=due)
    city_revs = {}
    for i in revs:
        if i.get("type") == "City Page":
            city_revs.setdefault(i["dealer"], []).append(i)
    seen = set()
    for i in revs:
        g = city_revs.get(i["dealer"]) if i.get("type") == "City Page" else None
        if g and len(g) > 1:                      # one dealer's city revisions together (design once, content per page)
            if i["dealer"] not in seen:
                seen.add(i["dealer"])
                units.append(("fixgroup", ",".join(str(x["subitem_id"]) for x in g), f"{i['dealer']} - {len(g)} city page revisions"))
        else:
            units.append(("fix", str(i["subitem_id"]), f"{i['dealer']} - {i['mlp']}"))
    new = sorted([i for i in items if batch.pending(i)], key=due)
    seen = set()
    for i in new:
        if i.get("type") == "City Page":
            pid = str(i.get("item_id"))
            if pid in seen:
                continue
            g = batch.group(pid)
            todo = [x for x in g if batch.pending(x)]
            if any(x.get("claude") == "Claude is done" for x in g):   # sample already built -> copy the rest from it
                seen.add(pid)
                units.append(("batch-copy", pid, f"{i['dealer']} - {len(todo)} city page(s) from the sample"))
                continue
            if len(todo) > 1:                                        # build the sample first, the copy run follows
                seen.add(pid)
                units.append(("batch", pid, f"{i['dealer']} - city page sample ({len(todo)} pages)"))
                continue
        units.append(("build", str(i["subitem_id"]), f"{i['dealer']} - {i['mlp']}"))
    return units


def blog_units(cms):
    """Blogs tab Start per CMS (user, 2026-11-26: "put a start button beside the name of the cms for it to start creating
    the blogs for that cms"): every blog of that CMS's dealers that is your turn on monday (For Web Posting / For SEO
    Review), has no folder yet and has a Google Doc - oldest publication date first. [("blog", monday url, name)]"""
    r = blogs.blogs_by_dealer()
    xs = [(x.get("date") or "9999", d["name"], x) for d in r["dealers"] if (d.get("cms") or "") == cms and d.get("auto", True)
          for x in d.get("upcoming") or [] if x.get("turn") and x.get("doc")]
    return [("blog", x["url"], f"{dn} - {x['name']}") for _, dn, x in sorted(xs, key=lambda y: (y[0], y[1]))]


def fixgroup_prompt(sids):
    """One dealer's open city-page revisions in one run (the CITY PAGES rule needs them together)."""
    items = {str(i["subitem_id"]): i for i in read_json(STATE, {}).get("items", [])}
    g = [items[s] for s in sids.split(",") if s in items]
    if not g:
        return None, None
    name0, base = fix_prompt(g[0]["subitem_id"])
    n, dealer = len(g), g[0]["dealer"]
    lst = "; ".join(f"{i['mlp']} (subitem {i['subitem_id']})" for i in g)
    flow = base.split("exactly as REFRESH.md", 1)[1].replace("Do not start any other page.", "Do not start any page outside this list.")
    flow = flow.replace(f"'{name0}' '<step>' '1/1'", f"'<dealer> - <city>' '<step>' '<k>/{n}'")
    return f"{dealer} - {n} city page revisions", (
        f"fix group  (sent from the MLP Tracker Start queue). Work ONLY the open QA revisions of these {n} city pages of "
        f"{dealer}: {lst}. {CITY_RULE}For each page follow this flow exactly as REFRESH.md" + flow)


def chain_end(why):
    if not CHAIN["on"]:
        return
    CHAIN["on"] = False
    subprocess.run([sys.executable, "-I", str(HERE / "build_mlp_tracker.py"), "--automation", "Stopped"], capture_output=True, cwd=str(HERE))
    n = CHAIN.get("runs", 0)
    cms, CHAIN["cms"] = CHAIN.get("cms"), None
    log_history((f"Blogs Start ({cms})" if cms else "Start queue") + f" {why}" + (f" after {n} run(s)" if n else ""))
    if n and why != "stopped by you" and settings.get("alert_claude_done"):
        if cms:
            features.toast(f"{cms} blogs done", f"{n} blog(s) built - check the Blogs tab.", "blogs")
        else:
            features.toast("Start queue done", f"{n} page(s) - check Ready to post.", "post")


def chain_next():
    """Start the next run of the queue. Returns the run_action answer, or None when the queue is done."""
    while CHAIN["on"]:
        if not automation_running():
            chain_end("stopped")
            return None
        units = [u for u in (blog_units(CHAIN["cms"]) if CHAIN.get("cms") else queue_units()) if [u[0], u[1]] not in CHAIN["tried"]]
        if not units:
            chain_end("finished - the queue is empty")
            return None
        act, sid, name = units[0]
        CHAIN["tried"].append([act, sid])
        CHAIN["pos"], CHAIN["total"] = len(CHAIN["tried"]), len(CHAIN["tried"]) + len(units) - 1
        r = run_action(act, sid, chain=True)
        if r.get("ok"):
            CHAIN["runs"] = CHAIN.get("runs", 0) + 1
            return r
        log_history(f"Start queue skipped {name}: {r.get('error')}")
    return None


def chain_loop():
    """Background: when a queue run ends, check monday once (new revisions go first), then start the next run.
    Runs whether or not the tracker page is open."""
    while True:
        time.sleep(10)
        try:
            if not CHAIN["on"] or job_state()["proc_running"]:
                continue
            if JOB.get("stopped_by_user"):
                chain_end("stopped by you")
                continue
            if has_token() and not CHAIN.get("cms"):   # blog queue: no MLP monday check between blogs
                while features.AUTO["busy"] or features.auto_running():
                    time.sleep(5)
                features.AUTO["busy"] = True
                try:
                    ok, line = features.run_refresh("Start queue: checking monday before the next page")
                    features.note_refresh(ok, line)
                finally:
                    features.AUTO["busy"] = False
            if CHAIN["on"] and not job_state()["proc_running"]:
                chain_next()
        except Exception as e:   # never let the loop die
            try:
                log_history(f"Start queue error: {type(e).__name__}: {e}"[:200])
            except Exception:
                pass


def run_action(action, sid=None, chain=False):
    if action == "stop":
        with JLOCK:
            p = JOB["proc"]
        if p is not None and p.poll() is None:
            JOB["stopped_by_user"] = True                 # no "Claude stopped" pop-up for your own Stop
            plat.kill_tree(p.pid)
        CHAIN["on"] = False
        subprocess.run([sys.executable, "-I", str(HERE / "build_mlp_tracker.py"), "--automation", "Stopped"], capture_output=True, cwd=str(HERE))
        log_history("Stop pressed in the web app (any running Claude job was halted)")
        return {"ok": True, "msg": "Stopped"}
    if action == "start":   # one page per run, the next starts by itself (2026-11-25)
        if job_state()["proc_running"] or CHAIN["on"]:
            return {"error": "Start is already working the queue - wait for it or press Stop"}
        if not queue_units():
            return {"ok": True, "msg": "Nothing in Claude's queue - Claude was not started"}
        try:
            features.write_dealer_lessons()
        except Exception:
            pass
        subprocess.run([sys.executable, "-I", str(HERE / "build_mlp_tracker.py"), "--automation", "Running"], capture_output=True, cwd=str(HERE))
        CHAIN.update({"on": True, "tried": [], "pos": 0, "total": 0, "runs": 0, "started": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        log_history("Start pressed in the web app - Claude works the queue one page per run")
        r = chain_next()
        return r or {"ok": True, "msg": "Nothing in Claude's queue - Claude was not started"}
    if action == "blogcms":   # Blogs tab: Start beside a CMS name (2026-11-26) - sid = the CMS name
        if job_state()["proc_running"] or CHAIN["on"]:
            return {"error": "Claude is already working - wait for it or press Stop"}
        if not blogs.auto_ok(sid):
            return {"error": f"{sid} is not compatible with automation - build these blogs by hand"}
        n = len(blog_units(sid or ""))
        if not n:
            return {"ok": True, "msg": f"No {sid} blogs to build - none is your turn without a folder"}
        subprocess.run([sys.executable, "-I", str(HERE / "build_mlp_tracker.py"), "--automation", "Running"], capture_output=True, cwd=str(HERE))
        CHAIN.update({"on": True, "tried": [], "pos": 0, "total": 0, "runs": 0, "cms": sid,
                      "started": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        log_history(f"Blogs Start pressed for {sid} - Claude builds {n} blog(s), one per run")
        r = chain_next()
        return r or {"ok": True, "msg": f"No {sid} blogs could be started"}
    if action not in PROMPTS and action not in ("fix", "fixgroup", "build", "blog", "batch", "batch-copy"):
        return {"error": "unknown action"}
    if job_state()["proc_running"] or (CHAIN["on"] and not chain and action != "refresh"):
        if action == "blog":
            return {"error": f"a '{JOB['action']}' job is running - build the blog when it is done (or press Stop)"}
        if action == "fix" and (JOB.get("chain") or JOB.get("action") == "start"):
            return {"error": "Start is already running - it works revisions first, so this one is in its queue"}
        if action in ("build", "batch", "batch-copy"):
            return {"error": f"Claude is already working ({'the Start queue' if JOB.get('chain') or JOB['action'] == 'start' else JOB.get('page') or JOB['action']}) "
                             "- press Start now again when it is done, or press Stop first"}
        return {"error": f"a '{JOB['action']}' job is already running - wait for it or press Stop"}
    if action in ("fix", "fixgroup", "build", "batch", "batch-copy"):
        try:
            features.write_dealer_lessons()          # fresh per-dealer QA lessons for this run (2026-11-14)
            try:
                features.save_figma_links()          # Figma link per page for the spacing check (2026-11-20)
            except Exception:
                pass
        except Exception:
            pass
    if action == "fix":
        name, prompt = fix_prompt(sid)
        if not prompt:
            return {"error": "page not found in the tracker"}
    if action == "fixgroup":   # Start queue: one dealer's city-page revisions together (2026-11-25)
        name, prompt = fixgroup_prompt(sid)
        if not prompt:
            return {"error": "those pages are not on the tracker"}
    if action == "build":   # "Start now" on a pending page (2026-11-19)
        name, prompt = build_prompt(sid)
        if not prompt:
            return {"error": "page not found in the tracker"}
    if action == "batch":   # batch step 1 (2026-11-20): sid = monday parent item id; build the first page as the sample
        todo = [i for i in batch.group(sid) if batch.pending(i)]
        if len(todo) < 2:
            return {"error": "a batch needs at least 2 city pages that are not started yet"}
        name, base = build_prompt(todo[0]["subitem_id"])
        first, prompt = batch.sample_prompt(sid, base)
        name += " (batch sample)"
    if action == "batch-copy":   # batch step 2: the other pages from the sample
        name, prompt, n_copy = batch.copy_prompt(sid, fmc_cmd())
        if not prompt:
            return {"error": "nothing to copy - the other pages are already started or done"}
        batch.mark_copy(sid)
    if action == "blog":   # Blogs tab "Build it" (2026-11-17): sid = the blog's monday item URL
        name, prompt = blogs.build_prompt(sid)
        if prompt == "":
            return {"error": f"{name}: this dealer's CMS (DealerOn / MotiveHQ) is not compatible with automation - build it by hand"}
        if not prompt:
            return {"error": "blog not found on monday - press Refresh on the Blogs tab"}
    if action == "refresh" and features.auto_running():
        return {"error": "the auto-update is refreshing right now - it will be done in a few seconds"}
    if chain and action in ("fix", "build"):   # the page's place in the queue for the Now card ("page 2/5")
        prompt = prompt.replace("'<step>' '1/1'", f"'<step>' '{CHAIN['pos']}/{CHAIN['total']}'")
    if chain:
        prompt = prompt.replace("(sent from the MLP Tracker 'Fix it now' button)", "(sent from the MLP Tracker Start queue)").replace(
            "(sent from the MLP Tracker 'Start now' button)", "(sent from the MLP Tracker Start queue)")
    if action == "fix":
        tools, turns = PROMPTS["start"][1], 250
    elif action == "fixgroup":
        tools, turns = PROMPTS["start"][1], 400
    elif action in ("build", "batch", "batch-copy"):   # + Google Drive download for the content doc (city pages / MLP content)
        tools, turns = PROMPTS["start"][1] + ["mcp__claude_ai_Google_Drive__download_file_content",
                                              "mcp__claude_ai_Google_Drive__get_file_metadata"], 300
        if action == "batch-copy":
            turns = min(900, 80 + 110 * n_copy)
    elif action == "blog":
        tools, turns = PROMPTS["start"][1] + ["mcp__claude_ai_Google_Drive__download_file_content",
                                              "mcp__claude_ai_Google_Drive__get_file_metadata"], 150
    else:
        prompt, tools, turns = PROMPTS[action]
        prompt = prompt.replace("{FMC}", fmc_cmd())
    direct = action == "refresh" and has_token()   # 2026-11-13: refresh reads monday directly (no Claude, no tokens)
    cmd = ([sys.executable, "-I", str(HERE / "refresh_monday.py")] if direct else
           [CLAUDE, "-p", prompt, "--allowedTools", " ".join(tools), "--max-turns", str(turns)])
    JOBS.mkdir(exist_ok=True)
    log = JOBS / f"{datetime.now():%Y%m%d-%H%M%S}-{action}.log"
    with open(log, "w", encoding="utf-8") as f0:
        f0.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {action} started from the web app\n\n")
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with JLOCK:
        JOB.update({"action": action, "started": started, "log": str(log), "ended": None, "code": None, "claude": not direct,
                    "activity": None, "tokens": None, "result": None, "result_text": None, "stopped_by_user": False,
                    "page": name if action in ("fix", "fixgroup", "build", "blog", "batch", "batch-copy") else None,
                    "chain": ("blogs:" + CHAIN["cms"]) if chain and CHAIN.get("cms") else chain,
                    "sid": sid if action in ("fix", "build", "blog") else first["subitem_id"] if action == "batch" else None})
    if direct:
        f = open(log, "a", encoding="utf-8")
        p = subprocess.Popen(cmd, cwd=str(HERE), stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), **plat.group_kwargs())
    else:
        p = features.start_claude(cmd, log, JOB)     # readable log + live activity + cost record (webapp/jobs/costs.json)
    with JLOCK:
        JOB["proc"] = p
        save_job_file(p)
    who = "reading monday directly (no Claude)" if direct else "Claude Code is working in the background"
    if chain and CHAIN.get("cms"):
        log_history(f"Blogs Start ({CHAIN['cms']}) {CHAIN['pos']}/{CHAIN['total']}: Claude started on the blog {name}")
        return {"ok": True, "msg": f"Claude is building {CHAIN['cms']} blogs: {name} ({CHAIN['pos']} of {CHAIN['total']})"}
    if chain:
        log_history(f"Start queue run {CHAIN['pos']}/{CHAIN['total']}: Claude started on {name}")
        return {"ok": True, "msg": f"Start: Claude is on {name} ({CHAIN['pos']} of {CHAIN['total']}) - one page per run"}
    if action == "blog":
        log_history(f"Build it: Claude started on the blog {name}")
        return {"ok": True, "msg": f"Claude is building the blog {name} - follow it in the header"}
    if action == "fix":
        with JLOCK:
            JOB["page"] = name
        log_history(f"Fix it now: Claude started on the revision for {name}")
        return {"ok": True, "msg": f"Claude is fixing {name} - follow it in the header"}
    if action in ("batch", "batch-copy"):
        log_history(f"Batch: Claude started {name}")
        return {"ok": True, "msg": f"Claude is working: {name} - follow it in the header"}
    if action == "build":
        with JLOCK:
            JOB["page"] = name
        log_history(f"Start now: Claude started building {name}")
        return {"ok": True, "msg": f"Claude is building {name} - follow it in the header"}
    log_history(f"{action.capitalize()} pressed in the web app - {who}")
    return {"ok": True, "msg": f"{action.capitalize()} started - {who}"}


def claude_target(sid=None, dealer=None):
    """"Open in Claude Code" target: a page (key = subitem id) or a whole dealer (key = "dealer:<name>").
    Returns (key, title, item or None, dealer name)."""
    items = read_json(STATE, {}).get("items", [])
    if sid not in (None, ""):
        it = next((i for i in items if str(i["subitem_id"]) == str(sid)), None)
        return (str(sid), f"{it['dealer']} - {it['mlp']}", it, it["dealer"]) if it else (None, None, None, None)
    if dealer and any(i["dealer"] == dealer for i in items):
        return "dealer:" + dealer, dealer, None, dealer
    return None, None, None, None


def claude_open(sid=None, dealer=None):
    """"Open in VS Code" (2026-11-24, was "Open in Claude Code"; user: "opening the VS code where the project is. The
    project specifically, not the parent folder"): opens only the page's own folder in VS Code - no Claude Code chat
    link, never the dealer folder. A page without its own folder yet gets a message instead."""
    key, title, it, dealer = claude_target(sid, dealer)
    if not it:
        return {"error": "That page is not on the tracker"}
    folder = features.page_folder(it)
    if not folder:
        return {"error": f"{title} has no folder yet - it gets one when the page is built"}
    subprocess.Popen([features.vscode(), str(folder)], creationflags=0x08000000,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log_history(f"Opened in VS Code: {title}")
    return {"ok": True, "msg": f"Opening {folder.name} in VS Code"}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            return self.send(200, (APP / "index.html").read_bytes(), "text/html; charset=utf-8")
        if u.path == "/api/memory/scan":   # Settings > My build memory: the Claude memory on this computer
            return self.send(200, buildmemory.scan())
        if u.path == "/api/assigned":   # Assigned tab (2026-11-18): every monday subitem assigned to you, by project
            a = read_json(APP / "assigned.json", {})
            mine = {int(i["subitem_id"]): i for i in read_json(STATE, {}).get("items") or [] if i.get("subitem_id")}
            for p in a.get("projects") or []:
                for s in p["subitems"]:
                    t = mine.get(s["subitem_id"])
                    if t:   # this subitem is a tracker row (Final MLP / city page): where Claude is on it
                        s["claude"] = t.get("claude") or ""
            return self.send(200, a)
        if u.path == "/api/blogs":   # Blogs tab: blog folders under your blog dealers (2026-11-17)
            return self.send(200, blogs.blogs_by_dealer(fresh=bool(q.get("fresh"))))
        if u.path == "/api/blog-html":   # copy button: the blog's cms.html
            return self.send(200, blogs.blog_html((q.get("name") or [""])[0]))
        if u.path == "/api/version":
            features.page_seen()   # the tracker page is open -> pop-ups allowed (popups_only_when_open)
            return self.send(200, {"v": version(), "job": job_state(), "watch": features.watch_state(), "session": session_state(),
                                   "qa_all": dict(features.QA_ALL), "auto_qa": dict(features.AUTOQA)})
        if u.path == "/api/since":   # monday news since your last shift
            return self.send(200, features.since_last_shift())
        if u.path == "/api/seo-review":   # SEO review tab: pages that got a QA revision + automatic SEO check (2026-11-17)
            return self.send(200, features.seo_review())
        if u.path == "/api/qa-report":   # weekly QA-mistakes report (2026-11-14)
            return self.send(200, features.qa_report(q.get("week", [""])[0]))
        if u.path == "/api/summary":
            return self.send(200, features.shift_summary(q.get("date", [""])[0]))
        if u.path == "/api/fix-cost":
            return self.send(200, {"avg": features.revision_cost_hint()})
        if u.path == "/api/dealer":
            return self.send(200, features.dealer_card(q.get("name", [""])[0]))
        if u.path == "/api/qa-patterns":
            return self.send(200, features.qa_patterns())
        if u.path == "/api/costs":
            return self.send(200, features.costs_view())
        if u.path == "/api/backups":
            return self.send(200, {"backups": features.list_backups(), "folder": str(features.BACKUPS)})
        if u.path == "/api/monday-usage":
            r = subprocess.run([sys.executable, "-I", str(HERE / "refresh_monday.py"), "--usage"], cwd=str(HERE), capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            try:
                return self.send(200, json.loads(r.stdout.strip().splitlines()[-1]))
            except (ValueError, IndexError):
                return self.send(200, {"error": "could not read monday usage"})
        if u.path == "/api/shift-reports":
            return self.send(200, {"reports": features.shift_reports()})
        if u.path == "/api/job":
            return self.send(200, job_state())
        if u.path == "/api/settings":
            return self.send(200, settings_view())
        if u.path == "/api/setup-status":   # new-user setup form (2026-11-23)
            return self.send(200, setup_status())
        if u.path == "/api/state":
            return self.send(200, {"state": read_json(STATE, {}), "history": read_json(HIST, [])[:800], "worklog": work_log(),
                                   "automation": read_json(AUTO, {}), "v": version(),
                                   "shift": {k: settings.get(k) for k in ("shift_start", "shift_hours")},
                                   "qa": features.qa_summary(read_json(STATE, {}).get("items") or []),
                                   "packs": features.pack_summary(read_json(STATE, {}).get("items") or []),
                                   "update": features.update_info(), "claude_usage": features.claude_usage(),
                                   "batches": batch.state(), "unplaced": read_json(APP / "unplaced.json", {}),
                                   "figma_key": features.figma_key_status()})
        if u.path == "/api/item":
            return self.send(200, item_detail(q.get("sid", [""])[0]))
        if u.path == "/file":
            p = q.get("p", [""])[0]
            if not allowed(p):
                return self.send(403, {"error": "not allowed"})
            ctype = mimetypes.guess_type(p)[0] or "application/octet-stream"
            if ctype.startswith("text/"):
                ctype += "; charset=utf-8"
            return self.send(200, Path(p).read_bytes(), ctype)
        self.send(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        origin = self.headers.get("Origin") or ""
        if origin and origin not in (f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"):
            return self.send(403, {"error": "changes are only accepted from the tracker page"})   # no other site can post here
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self.send(400, {"error": "bad json"})
        if u.path == "/api/memory/save":
            return self.send(200, buildmemory.save(body.get("paths") or []))
        if u.path == "/api/memory/paste":
            return self.send(200, buildmemory.paste(body.get("text") or ""))
        if u.path == "/api/memory/check":
            return self.send(200, buildmemory.check())
        if u.path == "/api/open-updates":   # "New version" notice in the header (2026-11-19)
            return self.send(200, features.open_updates())
        if u.path == "/api/claude-open":   # "Open in VS Code" button / row icon (page folder only, 2026-11-24)
            return self.send(200, claude_open(body.get("sid"), body.get("dealer")))
        if u.path == "/api/run":
            return self.send(200, run_action(body.get("action"), body.get("sid")))
        if u.path == "/api/settings":
            return self.send(200, save_settings(body.get("changes")))
        if u.path == "/api/token":
            return self.send(200, save_token(body.get("token")))
        if u.path == "/api/setup":           # new-user setup form, one step at a time (2026-11-23)
            return self.send(200, setup_save(body))
        if u.path == "/api/figma-token":
            return self.send(200, save_figma_token(body.get("token"), body.get("expires")))
        if u.path == "/api/figma-expiry":
            return self.send(200, save_figma_expiry(body.get("expires")))
        if u.path == "/api/figma-token/test":
            ok, msg = check_figma()
            return self.send(200, {"ok": True, "msg": msg} if ok else {"error": msg})
        if u.path == "/api/token/test":
            ok, msg = check_token()
            return self.send(200, {"ok": True, "msg": msg} if ok else {"error": msg})
        if u.path == "/api/qa":
            return self.send(200, save_qa(body.get("text")))
        if u.path == "/api/vscode":
            return self.send(200, features.open_in_vscode(str(body.get("dealer") or ""), body.get("type") or "MLP"))
        if u.path == "/api/backup":
            d = features.backup(f"manual-{datetime.now():%Y%m%d-%H%M%S}")
            return self.send(200, {"ok": True, "msg": f"Backup saved ({d.name})"})
        if u.path == "/api/restore":
            r = features.restore(str(body.get("name") or ""), LOCK)
            if r.get("ok"):
                log_history(f"Restored the tracker data from backup {body.get('name')}")
            return self.send(200, r)
        if u.path == "/api/precheck":
            det = item_detail(body.get("sid"))
            if det.get("error"):
                return self.send(200, det)
            return self.send(200, features.precheck(det.get("folder"), use_cache=bool(body.get("cache"))))
        if u.path == "/api/since-ack":
            return self.send(200, features.since_ack())
        if u.path == "/api/seo-fix":   # SEO tab "Auto-fix": seo_fix.py on the chosen pages (2026-11-17)
            if job_state()["running"] and JOB.get("claude"):
                return self.send(200, {"error": "Claude is working on a page right now - try again when the run is done"})
            st = read_json(STATE, {})
            want = {str(x) for x in body.get("sids") or []}
            todo = [(i["subitem_id"], i["dealer"], i["mlp"], i["folder"]) for i in st.get("items", [])
                    if str(i["subitem_id"]) in want and i.get("folder") and Path(i["folder"]).is_dir()]
            res = features.seo_autofix(todo)
            for r in res:
                if r.get("fixed"):
                    log_history(f"SEO auto-fix on {r['page']}: {r['fixed']} fix(es)")
            return self.send(200, {"ok": True, "results": res, "fixed": sum(r.get("fixed", 0) for r in res)})
        if u.path == "/api/seo-mark":   # "Mark SEO reviewed" / undo (one page or a city batch)
            return self.send(200, features.seo_mark(body.get("sids") or [], body.get("revs") or [], bool(body.get("done", True))))
        if u.path == "/api/pack-text":   # copy buttons: one paste file or the monday note
            det = item_detail(body.get("sid"))
            txt = None if det.get("error") else features.pack_text(det.get("folder"), body.get("name"))
            return self.send(200, {"ok": True, "text": txt} if txt is not None else {"error": "file not found in the upload pack"})
        if u.path == "/api/batch-tick":   # "images uploaded" tick per batch folder
            det = item_detail(body.get("sid"))
            if det.get("error"):
                return self.send(200, det)
            return self.send(200, features.batch_tick(body.get("sid"), det.get("folder"), body.get("batch"), bool(body.get("done"))))
        if u.path == "/api/qa-all":   # QA sweep on several pages in the background (row badges)
            jobs = []
            for sid in body.get("sids") or []:
                det = item_detail(sid)
                if not det.get("error"):
                    jobs.append((f"{det['item'].get('dealer')} - {det['item'].get('mlp')}", det.get("folder")))
            return self.send(200, features.qa_all(jobs))
        if u.path == "/api/test-popup":
            features.toast("Web Dev Tracker test", "Pop-ups are working. Click to open the tracker.", "settings")
            return self.send(200, {"ok": True, "msg": "Test pop-up sent - look at the bottom-right of your screen"})
        if u.path == "/api/check-now":
            w = features.read_json(features.WATCH, {})
            full = bool(body.get("full"))   # header Refresh (user 2026-11-20): always re-read everything from monday
            w["force"] = "full" if full else True
            features.write_json(features.WATCH, w)
            if JOB.get("action") == "refresh" and job_state()["running"]:
                return self.send(200, {"ok": True, "msg": "A monday refresh is already running"})
            return self.send(200, {"ok": True, "msg": "Refreshing everything from monday - takes about a minute" if full
                                   else "Checking monday now - the tracker updates if anything changed"})
        if u.path == "/api/edit":
            return self.send(200, edit_state(body.get("sid"), body.get("field"), body.get("value")))
        if u.path == "/api/blog-check":   # Blogs tab: check cms.html before posting
            return self.send(200, blogs.check_blog(body.get("name")))
        if u.path == "/api/blog-open":   # Blogs tab: preview.html / folder
            return self.send(200, blogs.open_blog(body.get("name"), str(body.get("what") or "")))
        if u.path == "/api/open":
            det = item_detail(body.get("sid"))
            folder = det.get("folder")
            what = str(body.get("what") or "")
            target = {"folder": folder, "topost": os.path.join(folder, "to-post") if folder else None}.get(what)
            if folder and what.startswith("batch:"):   # open one image batch folder (drag the files into the media library)
                target = os.path.join(folder, "to-post", "1-upload-images", os.path.basename(what[6:]))
            if what == "preview":   # the page itself in the default browser (user, 2026-11-16)
                f = os.path.join(folder, "preview.html") if folder else None
                if f and os.path.isfile(f):
                    plat.open_path(f)
                    return self.send(200, {"ok": True})
                return self.send(404, {"error": "no preview.html in the project folder"})
            if target and os.path.isdir(target):
                plat.open_path(target)
                return self.send(200, {"ok": True})
            return self.send(404, {"error": "folder not found"})
        self.send(404, {"error": "not found"})


if __name__ == "__main__":
    try:   # tools copied into project folders find the tracker through this pointer
        _ptr = plat.app_dir()
        _ptr.mkdir(parents=True, exist_ok=True)
        (_ptr / "tracker_path.txt").write_text(str(HERE), encoding="utf-8")
    except OSError:
        pass
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    try:
        reattach_job()
        restore_last_job()
    except Exception as e:                                 # never block the tracker from starting
        print("reattach skipped:", e, flush=True)
    threading.Thread(target=features.watcher, args=(lambda: job_state()["running"] and JOB.get("action") == "refresh",),
                     daemon=True).start()              # auto-update from monday + pop-ups (Settings tab)
    threading.Thread(target=chain_loop, daemon=True).start()   # Start queue: next run when one ends (2026-11-25)
    threading.Thread(target=blogs.watch_loop, args=(features, settings), daemon=True).start()   # blog pop-ups (2026-11-17)
    threading.Thread(target=features.auto_qa_loop, args=(STATE, lambda: job_state()["running"] and JOB.get("claude")),
                     daemon=True).start()              # QA sweep by itself on ready pages that changed (2026-11-14)
    print(f"Web Dev Tracker web app on http://127.0.0.1:{PORT}  (Ctrl+C to stop)", flush=True)
    if "--open" in sys.argv:
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{PORT}")
    srv.serve_forever()
