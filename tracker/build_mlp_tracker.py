"""Build / refresh Final_MLP_Tracker.xlsx from mlp_data.json.

Usage:  python build_mlp_tracker.py
        python build_mlp_tracker.py --set <subitem_id> "Claude working on it" | "Claude is done" | ...
        python build_mlp_tracker.py --ask <subitem_id> "<question for the user>"
        python build_mlp_tracker.py --answer <subitem_id> "<the user's answer>"   (--set-answers to rewrite the cell)
        python build_mlp_tracker.py --folder <subitem_id> "<project folder>"
        python build_mlp_tracker.py --set-questions|--clear-questions <subitem_id> ["<text>"]
        python build_mlp_tracker.py --started|--finished <subitem_id> "YYYY-MM-DD[ HH:MM]"   (fix a timestamp)
        python build_mlp_tracker.py --automation Running|Stopped   (user typed "start" / "stop"; shown on Overview)
        python build_mlp_tracker.py --queue "<id>,<id>,..."   (set Claude's work order, Next Up column)

Sheets:
- Overview: count tiles, status colour guide, how to use, Claude's MLPs with start/finish times.
- MLPs: one row per open Final MLP (non-approved in monday); Notes, Questions, Project Folder and
  Claude Started/Finished are kept on every refresh (matched by monday subitem ID).
- History: newest first, with date and time: new MLPs, Claude started / finished building, questions,
  monday status changes, removals.
"""
import json
import re
import os
from datetime import date, datetime, timedelta

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # run with python -I: the script folder is not on the path
import settings  # noqa: E402  (page folders, 2026-11-24)

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "mlp_data.json")
OUT = os.path.join(HERE, "Final_MLP_Tracker.xlsx")
# used when Excel holds OUT locked and cannot be released; merged back on the next successful save
PENDING = os.path.join(HERE, "Final_MLP_Tracker (pending).xlsx")
MONDAY = "https://a3-brands.monday.com/boards/{board}/pulses/{item}"

# Column order on the MLPs sheet (left = most useful). Every column is found by its header name,
# so the order can change without breaking refreshes.
COLS = [
    ("#", 5, "Row number. Sorted by dealership (A-Z); inside each dealership: Claude's, not started, then the rest, by due date."),
    ("Dealer", 22, "Dealership the MLP belongs to."),
    ("MLP", 26, "The model landing page (the parent item in monday)."),
    ("Type", 11, "MLP or City Page (city pages: subitems of the \"City Pages\" item, user 2026-11-13)."),
    ("monday Status", 19, "Status from monday. Pick a new one from the dropdown to update it yourself: your choice is kept on every refresh until monday's own status changes. (This only changes the Excel; monday is never changed.)"),
    ("Claude Status", 19, "Claude's own progress: Not started / Claude working on it / Claude is done. Colour guide: Overview sheet."),
    ("Next Up", 9, "Claude's work queue: Now = being built, then 1, 2, 3... Revisions come first, then Assigned MLPs. Type other numbers to reorder (within revisions / within new MLPs); your order is kept on refresh."),
    ("Your Next Step", 46, "What YOU need to do for this MLP right now (upload which images, paste the fields, post the note, answer questions) - or Nothing. Claude keeps it current on every update."),
    ("Due Date", 12, "Due Date from monday."),
    ("Days Left", 9, "Days until the due date. Red = overdue, yellow = due today."),
    ("Notes", 36, "Yours (only you write here). Anything you type here is kept on every refresh."),
    ("Claude's Notes", 50, "Claude's decisions (Decided: ...) and what each revision changed (Revision #N done: ...), dated. Written by Claude."),
    ("Claude Started", 17, "When Claude started building this MLP."),
    ("Claude Finished", 17, "When Claude finished building this MLP (files ready for you to upload / paste)."),
    ("Platform", 24, "The dealer's CMS, from monday's 'Dealer Login and Setup' board (CMS column). Dealer Inspire = paste 3 CMS fields (HTML/CSS/JS); every other CMS = paste 1 file."),
    ("Revisions", 55, "Revisions QA requested on your Final MLP or Final Mobile Check subitem in monday (status 'Needs Revision', or a new comment after your 'ready for review' post), newest last. Claude picks them up and rebuilds."),
    ("Project Folder", 40, "Click to open the build folder on this PC."),
    ("Live URL", 34, "Page link from monday's Link column (once it exists)."),
    ("monday", 9, "Click to open the item in monday (Claude only reads monday)."),
    ("Date Assigned", 13, "Date Assigned from monday."),
    ("First Seen", 12, "Hidden helper: date this MLP first appeared in the tracker (new MLPs show in red that day)."),
    ("Subitem ID", 13, "monday Final MLP subitem id (used by Claude's commands)."),
    ("monday Last Read", 16, "Hidden helper: the status monday had at the last refresh (used to tell your dropdown changes apart from monday changes)."),
    ("Revision Seen", 16, "Hidden helper: the last monday comment already logged as a revision."),
]
HEADERS = [c[0] for c in COLS]
C = {name: i + 1 for i, name in enumerate(HEADERS)}
STATUS_FILL = {
    "Assigned": "D9E1F2",
    "Not started": "F2F2F2",
    "Claude working on it": "FCE4D6",
    "Claude is done": "C6EFCE",
    "Working on it": "FFE699",
    "Waiting for Review": "E4D2F5",
    "On-Hold": "D9D9D9",
    "Stuck": "F8CBAD",
    "Approved": "A9D08E",
    "Needs Revision": "F4B6C2",
    "Revision needed": "F4B6C2",
}
# monday Status cells: strong, distinct colours with white bold text, close to monday.com's own (user, 2026-11-13:
# "change the color of it so that it will be easy to understand"). Claude Status keeps the soft STATUS_FILL colours.
MONDAY_FILL = {
    "Assigned": "2F75B5",            # blue    - assigned, not started
    "Working on it": "F28C28",       # orange  - in progress
    "Waiting for Review": "7B4FC4",  # purple  - with QA
    "Needs Revision": "D6304A",      # red     - QA sent changes
    "On-Hold": "7F7F7F",             # grey    - paused
    "Stuck": "8B0000",               # dark red - blocked
    "Approved": "2E8B3E",            # green   - done
}
# Choices in the monday Status dropdown (user, 2026-11-12: "put a drop down ... where I can update it manually")
MONDAY_CHOICES = ["Assigned", "Working on it", "Waiting for Review", "Needs Revision", "On-Hold", "Stuck", "Approved"]
STATUS_MEANING = {
    "Assigned": "monday: assigned, nobody has started it.",
    "Not started": "Claude: has not started this MLP.",
    "Claude working on it": "Claude: building it now.",
    "Claude is done": "Claude: built and checked. Files are in the project folder, ready for you to upload / paste.",
    "Revision needed": "Claude: QA asked for a revision on monday; Claude will apply it next (see Revisions column).",
    "Working on it": "You are working on it (from monday).",
    "Waiting for Review": "Submitted, waiting for review (from monday).",
    "Needs Revision": "QA sent it back with changes (from monday).",
    "On-Hold": "Paused (from monday).",
    "Stuck": "Blocked (from monday).",
    "Approved": "Approved (set by you; the row leaves the tracker once monday says Approved too).",
}
ROW_TINT = {"Claude working on it": "FFF8F3", "Claude is done": "F3FBF5", "Revision needed": "FFF0F3"}
# Local-only statuses Claude sets. They survive a refresh while monday still says "Assigned".
CLAUDE_STATUSES = ("Claude working on it", "Claude is done", "Revision needed")
# raw monday updates (comments + replies) of each Final MLP subitem, written by the refresh (REFRESH.md step 2b)
UPDATES = os.path.join(HERE, "updates_raw.json")
LIVE = os.path.join(HERE, "live_checks.json")
# automation on/off (user, 2026-11-12: "stop" stops it, "start" starts it); set with --automation Running|Stopped
STATE = os.path.join(HERE, "automation_state.json")
FONT = "Segoe UI"
NAVY = "1E2A44"
ACCENT = "2F5597"
MUTED = "6B7280"
HEADER_ROW = 4
thin = Side(style="thin", color="D9DEE7")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
LINK = dict(name=FONT, size=10, color="0563C1", underline="single")
# column groups shown above the MLPs headers (row 3)
GROUPS = [
    ("MLP", ("#", "Dealer", "MLP", "Type"), "E7ECF5"),
    ("STATUS & QUEUE", ("monday Status", "Claude Status", "Next Up", "Your Next Step"), "DCE6F7"),
    ("DUE", ("Due Date", "Days Left"), "E5F0E8"),
    ("NOTES", ("Notes", "Claude's Notes"), "FFF3D6"),
    ("DETAILS  (click + above to open)", ("Claude Started", "Claude Finished", "Platform", "Revisions",
                                          "Project Folder", "Live URL", "monday", "Date Assigned", "First Seen", "Subitem ID",
                                          "monday Last Read", "Revision Seen"), "EEEEEE"),
]


def load_state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except (OSError, ValueError):
        return {"state": "Stopped", "since": None}


def rev_number_in_notes(hist_rows, cnotes):
    """Highest 'Revision #N' found in this page's notes / History (0 if none)."""
    import re as _re
    txt = " ".join(str(h[3]) for h in hist_rows) + " " + str(cnotes or "")
    return max([int(n) for n in _re.findall(r"[Rr]evision #(\d+)", txt)] or [0])


def queue_bucket(i):
    """0 = building now, 1 = revision waiting, 2 = new MLP not started; None = not in Claude's queue."""
    if i["claude"] == "Claude working on it":
        return 0
    if i["claude"] == "Revision needed":
        return 1
    if i["claude"] == "Not started" and i["status"] == "Assigned":
        return 2
    return None


def to_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date() if s else None


def as_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str) and v:
        try:
            return to_date(v[:10])
        except ValueError:
            return None
    return v


TSTATE = os.path.join(HERE, "tracker_state.json")
CONFIG = os.path.join(HERE, "tracker_config.json")
PREV_KEYS = ("notes", "cnotes", "first_seen", "dealer", "mlp", "folder", "status", "claude", "monday_read", "questions",
             "started", "finished", "answers", "revisions", "rev_seen", "live", "next", "posted", "due",
             "rev_status")   # rev_status kept across runs (2026-11-23) so "fixed by you" reads the real value after a restart


def excel_enabled():
    """tracker_config.json {"excel": false} = web app only, no workbook (user 2026-11-13)."""
    try:
        return bool(json.load(open(CONFIG, encoding="utf-8")).get("excel", True))
    except (OSError, ValueError):
        return True


def _when(v):
    if isinstance(v, str) and len(v) >= 16 and v[4] == "-":
        try:
            return datetime.strptime(v[:16], "%Y-%m-%d %H:%M")
        except ValueError:
            return v
    if isinstance(v, str) and len(v) == 10 and v[4] == "-":
        try:
            return to_date(v)
        except ValueError:
            return v
    return v


def _ser(v):
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def load_previous():
    """State from tracker_state.json + history.json (falls back to the workbook on the first run)."""
    prev, history = (_load_previous_xlsx() if not os.path.exists(TSTATE) else ({}, []))
    if os.path.exists(TSTATE):
        for r in json.load(open(TSTATE, encoding="utf-8")).get("items", []):
            prev[int(r["subitem_id"])] = {k: _when(r.get(k)) for k in PREV_KEYS}
    hist_file = os.path.join(HERE, "history.json")
    if os.path.exists(hist_file):
        history = [[_when(w) if isinstance(w, str) else w, d, m, t, st] for w, d, m, t, st in json.load(open(hist_file, encoding="utf-8"))]
    return prev, history


def write_state(items, prev, data, platforms):
    """tracker_state.json: everything the web app shows (and the engine's kept values)."""
    out = []
    today = date.today()
    for i in items:
        p = prev.get(i["subitem_id"]) or {}
        rec = {k: _ser(p.get(k)) for k in PREV_KEYS}
        # the page's own folder, also when no note saved it (2026-11-24: "QA not run" although preview.html was there)
        f = settings.page_folder(i["dealer"], i["mlp"], i.get("type", "MLP"), rec.get("folder"))
        if f:
            rec["folder"] = str(f)
        due = to_date(i["due"]) if i.get("due") else None
        rec.update({"subitem_id": i["subitem_id"], "item_id": i.get("item_id"), "board_id": i.get("board_id"), "dealer": i["dealer"],
                    "mlp": i["mlp"], "type": i.get("type", "MLP"), "status": i["status"], "monday_read": i.get("monday_read", i["status"]),
                    "claude": i["claude"], "next": i.get("next"), "due": i.get("due"), "assigned": i.get("assigned"),
                    "live_url": i.get("live_url"), "platform": platform_for(i["dealer"], platforms),
                    "mobile_only": i.get("mobile_only"), "final_mlp_status": i.get("final_mlp_status"),
                    "fmc_subitem_id": i.get("fmc_subitem_id"),
                    "days_left": (due - today).days if due else None,
                    "monday_url": MONDAY.format(board=i.get("board_id"), item=i.get("item_id")),
                    "next_step": _next_step({"dealer": i["dealer"], "mlp": i["mlp"], "monday": i["status"], "claude": i["claude"],
                                             "questions": p.get("questions"), "answers": p.get("answers"), "folder": rec.get("folder"),
                                             "platform": platform_for(i["dealer"], platforms),
                                             "posted": _ser(p.get("posted")), "finished": _ser(p.get("finished"))})})
        out.append(rec)
    st = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "refreshed_at": data.get("refreshed_at"),
          "owner": data.get("owner"), "automation": load_state(), "items": out, "approved": data.get("approved") or [],
          "dealer_links": dealer_links({i["dealer"] for i in items} | {a["dealer"] for a in (data.get("approved") or []) if a.get("dealer")})}
    tmp = TSTATE + ".tmp"
    json.dump(st, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    os.replace(tmp, TSTATE)


def _load_previous_xlsx():
    """Return {subitem_id: {...kept values...}} and the old history rows (5 columns, newest first)."""
    prev, history = {}, []
    src = OUT
    if os.path.exists(PENDING) and (not os.path.exists(OUT) or os.path.getmtime(PENDING) > os.path.getmtime(OUT)):
        src = PENDING
    if not os.path.exists(src):
        return prev, history
    wb = load_workbook(src)
    ws = wb["MLPs"]
    col = {ws.cell(HEADER_ROW, c).value: c for c in range(1, ws.max_column + 1)}

    def get(r, name):
        return ws.cell(r, col[name]).value if name in col else None

    for r in range(HEADER_ROW + 1, ws.max_row + 1):
        sid = get(r, "Subitem ID")
        if not sid or not str(sid).isdigit():
            continue
        prev[int(sid)] = rec = {
            "notes": get(r, "Notes"), "cnotes": get(r, "Claude's Notes"), "first_seen": get(r, "First Seen"), "dealer": get(r, "Dealer"),
            "mlp": get(r, "MLP"), "folder": get(r, "Project Folder"),
            "status": get(r, "monday Status") if "monday Status" in col else get(r, "Status"),
            "claude": get(r, "Claude Status"), "monday_read": get(r, "monday Last Read"),
            "questions": get(r, "Questions"), "started": get(r, "Claude Started"),
            "finished": get(r, "Claude Finished"), "answers": get(r, "Answers"),
            "revisions": get(r, "Revisions"), "rev_seen": get(r, "Revision Seen"), "live": get(r, "Live Check"),
            "next": get(r, "Next Up"),
        }
        if get(r, "Answers"):   # 2026-11-13: Answers column removed - keep the old answers in Claude's Notes
            moved = chr(10).join("Your answer: " + l for l in str(get(r, "Answers")).splitlines() if l.strip())
            rec["cnotes"] = (str(rec.get("cnotes") or get(r, "Claude's Notes") or "") + chr(10) + moved).strip()
        if not rec.get("cnotes") and rec.get("notes"):   # 2026-11-13: Claude's lines move out of the user's Notes
            mine = [l for l in str(rec["notes"]).splitlines() if "] Decided" in l or "] Revision #" in l]
            if mine:
                rec["cnotes"] = chr(10).join(mine)
                rest = [l for l in str(rec["notes"]).splitlines() if l not in mine]
                rec["notes"] = chr(10).join(rest) or None
        if not rec["claude"]:   # migrate the old single Status column
            rec["claude"] = rec["status"] if rec["status"] in CLAUDE_STATUSES else "Not started"
            if rec["status"] in CLAUDE_STATUSES:
                rec["status"] = "Assigned"
    if "History" in wb.sheetnames:
        h = wb["History"]
        heads = [c.value for c in h[1]]
        rows = []
        for row in h.iter_rows(min_row=2, values_only=True):
            if not any(v is not None for v in row):
                continue
            row = list(row)
            if heads[:2] == ["Date", "Change"]:   # v1 layout: Date, Change, Dealer, MLP, Status (oldest first)
                row = [row[0], row[2], row[3], row[1], row[4]]
            what = str(row[3] or "")
            if what.startswith("Status:") and what.endswith("-> Claude working on it"):
                row[3] = "Claude started building this MLP"
            elif what.startswith("Status:") and what.endswith("-> Claude is done"):
                row[3] = "Claude finished building this MLP (files ready to upload)"
            rows.append(row[:5])
        if heads[:2] == ["Date", "Change"]:
            rows.reverse()
        history = rows
    hist_file = os.path.join(HERE, "history.json")   # 2026-11-13: History lives in history.json (Activity tab shows it)
    if os.path.exists(hist_file):
        history = []
        for w, d, m, t, st in json.load(open(hist_file, encoding="utf-8")):
            try:
                w = datetime.strptime(w, "%Y-%m-%d %H:%M:%S") if isinstance(w, str) and len(w) > 10 else w
            except ValueError:
                pass
            history.append([w, d, m, t, st])
    return prev, history


CMS_DIR = os.path.join(HERE, "cms_directory.json")
_DROP = {"of", "the", "national", "city", "sierra", "-", "and", "&"}


def _norm(name):
    import re
    words = re.sub(r"[^a-z0-9 ]+", " ", (name or "").lower().replace("mercedes-benz", "mercedes benz")).split()
    return [w for w in words if w not in _DROP]


def load_platforms():
    """{normalised dealer words: CMS name} from cms_directory.json (monday Dealer Login and Setup board)."""
    if os.path.exists(CMS_DIR):
        d = json.load(open(CMS_DIR, encoding="utf-8")).get("cms", {})
        return [(set(_norm(k)), v) for k, v in d.items() if v]
    return []


def _platform_overrides():
    try:
        return json.load(open(CONFIG, encoding="utf-8")).get("platform_overrides") or {}
    except (OSError, ValueError):
        return {}


def platform_for(dealer, platforms):
    """Best match of the MLP board's dealer name against the monday CMS directory (Settings overrides first)."""
    ov = _platform_overrides().get(dealer)
    if ov:
        return f"{ov} (3 CMS fields)" if ov == "Dealer Inspire" else f"{ov} (1 file)"
    want = set(_norm(dealer))
    best, score = None, 0.0
    for words, cms in platforms:
        if not words or not want:
            continue
        s = len(want & words) / len(want | words)
        if want <= words or words <= want:
            s += 0.5
        if s > score:
            best, score = cms, s
    if not best or score < 0.6:
        return "? (not in monday CMS list)"
    return f"{best} (3 CMS fields)" if best == "Dealer Inspire" else f"{best} (1 file)"


def dealer_links(dealers):
    """{dealer: {"cms": CMS login URL, "cred": monday item on Dealer Login and Setup}} - same name matching as platform_for.
    Only links are kept; usernames/passwords stay on monday (user, 2026-11-20)."""
    try:
        d = json.load(open(CMS_DIR, encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    board, pairs = d.get("board") or 18392876953, [(set(_norm(k)), v) for k, v in (d.get("links") or {}).items()]
    out = {}
    for dealer in dealers:
        want = set(_norm(dealer))
        best, score = None, 0.0
        for words, v in pairs:
            if not words or not want:
                continue
            sc = len(want & words) / len(want | words) + (0.5 if (want <= words or words <= want) else 0)
            if sc > score:
                best, score = v, sc
        if best and score >= 0.6:
            out[dealer] = {"cms": best.get("cms") or "", "cred": MONDAY.format(board=board, item=best["item"]) if best.get("item") else ""}
    return out


def style_header(cell):
    cell.font = Font(name=FONT, bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor=NAVY)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = BORDER


def fmt_when(v):
    return "mmm d, h:mm AM/PM" if isinstance(v, datetime) else "mmm d, yyyy"


def flatten(updates):
    """Comments + replies as a flat list sorted by time."""
    posts = []
    for u in updates or []:
        for x in [u] + list(u.get("replies") or []):
            posts.append({"id": str(x.get("id")), "at": x.get("created_at") or "",
                          "by": (x.get("creator") or {}).get("name") or "?",
                          "by_id": str((x.get("creator") or {}).get("id") or ""),
                          "text": (x.get("text_body") or "").strip(),
                          "assets": [{"name": a.get("name") or f"asset-{a.get('id')}", "url": a.get("public_url") or a.get("url")}
                                     for a in (u.get("assets") or []) if a] if x is u else []})
    posts.sort(key=lambda x: x["at"])
    return posts


def for_someone_else(text, owner_name):
    """True when a comment greets other people only (user, 2026-11-23: "Hello @Mark Ross Canaoay - please create a
    metatags and run an SEO review" put 10 finished Mercedes-Benz of Columbus city pages back in Claude's queue).
    Only the part before "cc:" counts; a comment with no @ at all is still read as a revision."""
    head = re.split(r"\bcc\s*:", text or "", maxsplit=1, flags=re.I)[0]
    if "@" not in head:
        return False
    low = head.lower()
    ours = [n.lower() for n in (owner_name or "").split()[:1] if n] + [(owner_name or "").lower(), "web development", "web dev"]
    return not any(n and n in low for n in ours)


def monday_local(at):
    """monday created_at (UTC, '2026-11-23T10:26:00.000Z') -> local datetime, or None."""
    try:
        return datetime.fromisoformat(str(at).replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
    except ValueError:
        return None


def latest_revision(posts, owner_id, status, owner_last, owner_name=None):
    """Return {key, at, by, text, assets} for a revision request on one subitem, or None.

    A revision = a comment or reply by someone other than the owner, posted after the owner's latest
    post on the MLP's Final MLP / Final Mobile Check subitems (the "ready for review"), or the
    subitem's monday status "Needs Revision". Comments addressed only to other people are not revisions."""
    own = [owner_last] if owner_last else []
    others = [x for x in posts if x["by_id"] != str(owner_id) and not for_someone_else(x["text"], owner_name)]
    after = [x for x in others if own and x["at"] > max(own)]
    if not after and status == "Needs Revision" and others:
        after = [others[-1]]
    if not after and status == "Needs Revision":
        return {"key": "status-needs-revision-" + str(owner_last or ""), "at": "", "by": "monday", "assets": [],
                "text": "monday status is Needs Revision (no comment found; check the item)."}
    if not after:
        return None
    last = after[-1]
    text = "\n".join(" ".join(x["text"].split()) for x in after)
    return {"key": last["id"], "at": last["at"][:16].replace("T", " "), "at_raw": last["at"], "by": last["by"], "text": text,
            "assets": [a for x in after for a in x["assets"] if a]}


def timed(v):
    """True when v carries a real clock time (old rows only stored the date)."""
    return isinstance(v, datetime) and (v.hour, v.minute) != (0, 0)


def save_revision(folder, sid, source, rev):
    """Save a revision's text and its monday screenshots (download only; monday is never changed).
    Goes to <project folder>/revisions/<date>_<source>/, or mlp_tracker/revisions/<subitem>/ without a folder."""
    import re
    import urllib.request
    base = folder if folder and os.path.isdir(str(folder)) else os.path.join(HERE, "revisions", str(sid))
    day = (rev.get("at") or date.today().isoformat())[:10]
    sub = f"{day}_{source.replace(' ', '-')}"
    out = os.path.join(base, "revisions", sub) if base == folder else os.path.join(base, sub)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "revision.txt"), "w", encoding="utf-8") as f:
        f.write(f"{source} revision from {rev['by']} at {rev.get('at')}\n\n{rev['text']}\n")
    try:   # production feature (2026-11-13): numbered checklist matched to known QA fixes
        import sys as _sys
        if HERE not in _sys.path:
            _sys.path.insert(0, HERE)
        import production
        production.triage(os.path.join(out, "revision.txt"))
    except Exception as e:
        print("triage skipped:", e)
    for n, a in enumerate(rev.get("assets") or [], 1):
        if not a.get("url"):
            continue
        name = re.sub(r'[^\w.\- ]+', "_", a["name"])[:80]
        try:
            req = urllib.request.Request(a["url"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r, open(os.path.join(out, f"{n:02d}_{name}"), "wb") as f:
                f.write(r.read())
        except Exception as e:
            with open(os.path.join(out, "download-errors.txt"), "a", encoding="utf-8") as f:
                f.write(f"{a['name']}: {e}\n")
    return out


def took(start, end):
    """'1h 05m' between two datetimes (None if unknown)."""
    if not timed(start) or not timed(end):
        return None
    m = int((end - start).total_seconds() // 60)
    return f"{m // 60}h {m % 60:02d}m"


def main(set_status=None, extra=None):
    data = json.load(open(DATA, encoding="utf-8"))
    checked = data.get("checked_at") or date.today().isoformat()
    now = datetime.now().replace(second=0, microsecond=0)
    prev, history = load_previous()
    first_run = not prev and not history
    items = data["items"]
    current_ids = {i["subitem_id"] for i in items}
    events = []

    # Pages that leave the tracker keep their last tracker record in removed_items.json, so a page that comes back
    # (Final MLP approved but its Final Mobile Check needs a revision - 2026 Buick Envision, 2026-11-16) keeps its
    # notes, project folder, Claude status and the QA comments already seen.
    removed_file = os.path.join(HERE, "removed_items.json")
    removed = json.load(open(removed_file, encoding="utf-8")) if os.path.exists(removed_file) else {}
    came_back = set()
    for sid in current_ids:
        if sid not in prev and str(sid) in removed:
            prev[sid] = {k: _when(removed[str(sid)].get(k)) for k in PREV_KEYS}
            removed.pop(str(sid))
            came_back.add(sid)
    if os.path.exists(TSTATE):
        for r in json.load(open(TSTATE, encoding="utf-8")).get("items", []):
            if int(r["subitem_id"]) not in current_ids:
                removed[str(r["subitem_id"])] = r
    tmp = removed_file + ".tmp"
    json.dump(removed, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=0, default=str)
    os.replace(tmp, removed_file)
    for i in items:
        if i["subitem_id"] in came_back:
            # its earlier "Removed from tracker" was not a real approval - reword it so the summary, Activity and
            # Weekly chart do not count it as Approved (they read lines starting "Removed from tracker")
            for r in history:
                if r[1] == i["dealer"] and r[2] == i["mlp"] and str(r[3]).startswith("Removed from tracker"):
                    r[3] = "Left the tracker for a while - not approved yet (came back: " + (
                        "Final Mobile Check still open)" if i.get("mobile_only") else "still open on monday)")
                    break
            why = (f"Back in the tracker: Final MLP is approved but the Final Mobile Check is {i['status']}"
                   if i.get("mobile_only") else "Back in the tracker")
            events.append([now, i["dealer"], i["mlp"], why, i["status"]])

    def by_id(sid):
        it = next((i for i in items if i["subitem_id"] == sid), None)
        if not it:
            raise SystemExit(f"Subitem {sid} not found in mlp_data.json")
        return it

    for i in items:
        p = prev.get(i["subitem_id"]) or {}
        i["claude"] = p.get("claude") or ("Claude is done" if i["status"] in ("Waiting for Review", "Needs Revision") else "Not started")
    if set_status:
        sid, new = set_status
        it = by_id(sid)
        p = prev.setdefault(sid, {"status": it["status"], "claude": it["claude"]})
        if new not in CLAUDE_STATUSES + ("Not started",):
            raise SystemExit("--set only sets Claude Status: Not started | Claude working on it | Claude is done | Revision needed")
        old = it["claude"]
        it["claude"] = new
        # revision rounds = earlier "Claude started revision" events of this MLP (one round can hold several QA comments)
        mine = [h for h in history if h[1] == it["dealer"] and h[2] == it["mlp"]]
        nrev = sum(1 for h in mine if str(h[3]).startswith("Claude started revision")) + 1
        # 2026-11-13: notes sometimes count rounds the tracker never logged ("Revision #2 done" while History said #1);
        # the round number is the highest either side has seen + 1, so History and notes agree.
        nrev = max(nrev, rev_number_in_notes(mine, p.get("cnotes")) + 1)
        # the latest "Claude started ..." event of this MLP tells whether a revision run is open
        last_start = next((h for h in mine if str(h[3]).startswith("Claude started")), None)
        in_rev = bool(last_start and "revision" in str(last_start[3]))
        if new == "Claude working on it" and old == "Revision needed":
            events.append([now, it["dealer"], it["mlp"], f"Claude started revision #{nrev}", new])
        elif new == "Claude working on it" and not p.get("started"):
            p["started"] = now
            events.append([now, it["dealer"], it["mlp"], "Claude started building this MLP", new])
        elif new == "Claude is done" and in_rev and old == "Claude working on it":
            # fixed 2026-11-13: no longer needs a recorded first-build finish (MLPs built before the tracker were logged as builds)
            d = took(last_start[0], now)
            label = str(last_start[3]).replace("Claude started ", "")
            events.append([now, it["dealer"], it["mlp"],
                           f"Claude finished {label}" + (f" (took {d})" if d else "") + " - files ready to upload", new])
        elif new == "Claude is done":
            p["started"] = p.get("started") or now
            p["finished"] = now
            d = took(p["started"], now)
            events.append([now, it["dealer"], it["mlp"], "Claude finished building this MLP (files ready to upload)"
                           + (f" - took {d}" if d else ""), new])
        p["claude"] = new
    forced = None
    if extra and extra[0] == "automation":
        st = {"start": "Running", "running": "Running", "stop": "Stopped", "stopped": "Stopped"}.get(extra[2].strip().lower())
        if not st:
            raise SystemExit("--automation Running | Stopped")
        json.dump({"state": st, "since": now.isoformat(timespec="minutes")}, open(STATE, "w", encoding="utf-8"))
        events.append([now, "-", "-", "Automation " + ("started (you typed start)" if st == "Running" else "stopped (you typed stop)"), st])
        extra = None
    elif extra and extra[0] == "queue":    # --queue "<id>,<id>,..." : explicit work order
        forced = {int(x): n for n, x in enumerate(extra[2].replace(" ", "").split(",")) if x}
        extra = None
    # --batch file.json: [[kind, sid, text], ...] applied in ONE run (one Excel close/reopen, user 2026-11-13)
    batch = [extra] if extra and extra[0] not in ("automation", "queue", "batch") else []
    if extra and extra[0] == "batch":
        batch = [tuple(x) for x in json.load(open(extra[2], encoding="utf-8"))]
    for kind, sid, text in batch:
        sid = int(sid)
        it = by_id(sid)
        p = prev.setdefault(sid, {"status": it["status"], "claude": it["claude"]})
        if kind == "claude-silent":   # fix a Claude Status without logging a build (pages built before the tracker)
            p["claude"] = text
            it["claude"] = text
            continue
        if kind == "note":
            # user 2026-11-13: "Once you are done doing the revision put on the note on what did you change"
            # The note uses the tracker's round number (the open "Claude started revision #N"), so they never disagree.
            mine = [h for h in history + events if h[1] == it["dealer"] and h[2] == it["mlp"]]
            open_rev = next((h for h in sorted(mine, key=lambda h: str(h[0]), reverse=True) if str(h[3]).startswith("Claude started")), None)
            m = re.match(r"Claude started revision #(\d+)", str(open_rev[3])) if open_rev else None
            if m:
                text = re.sub(r"Revision #\d+", f"Revision #{m.group(1)}", text, count=1)
            old = p.get("cnotes")
            p["cnotes"] = (old + chr(10) if old else "") + f"[{date.today().isoformat()}] {text}"
            events.append([now, it["dealer"], it["mlp"], "Claude note: " + text[:150], it["claude"]])
        if kind == "folder":
            p["folder"] = text
        elif kind == "ask":
            old = p.get("questions")
            p["questions"] = (old + chr(10) if old else "") + f"[{date.today().isoformat()}] {it['mlp']}: {text}"
            events.append([now, it["dealer"], it["mlp"], "Question for you: " + text[:150], it["claude"]])
        elif kind == "answer":
            old = p.get("answers")
            p["answers"] = (old + chr(10) if old else "") + f"[{date.today().isoformat()}] {text}"
            events.append([now, it["dealer"], it["mlp"], "Your answer recorded: " + text[:150], it["claude"]])
        elif kind == "set-answers":
            p["answers"] = text or None
        elif kind == "set-questions":
            p["questions"] = text or None
        elif kind == "clear-questions":
            p["questions"] = None
        elif kind in ("started", "finished"):
            p[kind] = datetime.strptime(text, "%Y-%m-%d %H:%M") if " " in text else to_date(text)
    platforms = load_platforms()

    # monday Status dropdown: keep a value the user picked in Excel until monday's own status changes
    for i in items:
        p = prev.get(i["subitem_id"]) or {}
        i["monday_read"] = i["status"]
        shown, last_read = p.get("status"), p.get("monday_read")
        if shown and last_read and shown != last_read:
            if i["status"] == last_read:      # user changed it in Excel, monday unchanged -> keep the user's choice
                text = f"monday Status set by you in Excel: {last_read} -> {shown}"
                if not any(h[2] == i["mlp"] and h[3] == text for h in history):
                    events.append([now, i["dealer"], i["mlp"], text, shown])
                i["status"] = shown
                p["status"] = shown           # no "monday status changed" event for the user's own edit
            else:                             # monday moved on -> monday wins
                p["status"] = last_read

    # Revisions requested on monday (read-only) on the owner's "Final MLP" and "Final Mobile Check" subitems
    # (user, 2026-11-12). updates_raw.json: {"<Final MLP subitem id>": {"Final MLP": {"status", "updates"},
    #                                                                  "Final Mobile Check": {"status", "updates"}}}
    raw = json.load(open(UPDATES, encoding="utf-8")) if os.path.exists(UPDATES) else {}
    owner = data.get("owner_id")
    for i in items:
        sid = i["subitem_id"]
        p = prev.get(sid)
        if p is None:                      # brand-new row: nothing built yet, so nothing to revise
            continue
        src = raw.get(str(sid)) or {}
        if isinstance(src, list):          # plain list = Final MLP updates only
            src = {"Final MLP": {"status": i["status"], "updates": src}}
        src.setdefault("City Page" if i.get("type") == "City Page" else "Final MLP", {"status": i["status"], "updates": []})
        posts = {k: flatten(v.get("updates")) for k, v in src.items()}
        owner_last = max([x["at"] for ps in posts.values() for x in ps if x["by_id"] == str(owner)] or [""])
        if i.get("type") == "City Page":   # city pages are copies of one master: your reply on ANY city covers them all (2026-11-13)
            sib = [x["at"] for j in items if j.get("type") == "City Page" and j["item_id"] == i["item_id"]
                   for v in (raw.get(str(j["subitem_id"])) or {}).values() if isinstance(v, dict)
                   for x in flatten(v.get("updates")) if x["by_id"] == str(owner)]
            owner_last = max([owner_last] + sib)
        seen = set(filter(None, str(p.get("rev_seen") or "").split(",")))
        # when Claude last finished work on this page (a revision or the build); a QA comment older than that is
        # already handled (user, 2026-11-23: "If we already fix the revision you dont need to work on it")
        fin = [h[0] for h in history + events if h[1] == i["dealer"] and h[2] == i["mlp"] and isinstance(h[0], datetime)
               and (str(h[3]).startswith("Claude finished") or str(h[3]).startswith("Claude note: Revision #"))]
        claude_done_at = max(fin) if fin else None
        for name in ("Final MLP", "City Page", "Final Mobile Check"):   # City Page: comments on the city subitem itself (2026-11-13)
            if name not in src:
                continue
            if name == "Final MLP" and i.get("mobile_only"):   # Final MLP already approved - only the mobile check is open
                continue
            st = src[name].get("status") if name == "Final Mobile Check" else i["status"]
            rev = latest_revision(posts[name], owner, st, owner_last, data.get("owner"))
            if not rev or rev["key"] in seen:
                continue
            seen.add(rev["key"])
            posted_at = monday_local(rev.get("at_raw"))
            if posted_at and claude_done_at and posted_at < claude_done_at:
                continue                   # Claude already fixed this one (just not uploaded yet) - not a new revision
            line = f"[{rev['at'] or date.today().isoformat()}] {name} - {rev['by']}: {rev['text'][:900]}"
            saved = save_revision(p.get("folder"), sid, name, rev)
            if saved:
                line += f" (saved with {len(rev['assets'])} screenshot(s) in {saved})"
            p["revisions"] = (str(p["revisions"]) + chr(10) if p.get("revisions") else "") + line
            if i["claude"] != "Claude working on it":
                i["claude"] = p["claude"] = "Revision needed"
                p["rev_status"] = i["status"]   # monday status when the revision came in (see "fixed by you" below)
            events.append([now, i["dealer"], i["mlp"], f"Revision requested on monday ({name}) by {rev['by']}: "
                           + rev["text"][:1500], "Revision needed"])   # full text for the weekly QA report (2026-11-14)
        p["rev_seen"] = ",".join(sorted(seen)) or None

    # Revision fixed by the user (user, 2026-11-13: "Once I'm waiting for review the one that has revision you dont need to
    # work for it since I already fixed it"). The item moved to Waiting for Review after the revision came in -> Claude's tag
    # becomes "Claude is done" so it leaves Claude's queue. A QA comment posted while the item is already Waiting for Review
    # (rev_status == Waiting for Review) is still a real revision and stays.
    for i in items:
        p = prev.get(i["subitem_id"])
        if p is None or i["claude"] != "Revision needed" or i["status"] != "Waiting for Review":
            continue
        if p.get("rev_status") == "Waiting for Review":
            continue
        i["claude"] = p["claude"] = "Claude is done"
        p["rev_status"] = None
        events.append([now, i["dealer"], i["mlp"], "Revision fixed by you (monday: Waiting for Review) - Claude does not need to work on it",
                       "Claude is done"])

    # Live page checks (live_check_all.py writes live_checks.json)
    lc = {}   # live page checks switched off (user 2026-11-13)
    for i in items:
        c = lc.get(str(i["subitem_id"]))
        i["live"], i["live_age"] = None, None
        if c and c.get("url") == i.get("live_url"):
            d = to_date(c["at"][:10])
            i["live_age"] = (date.today() - d).days
            i["live"] = f"{c['verdict']}  |  checked {d:%b} {d.day}" + ("" if c["verdict"].startswith("LIVE OK") else "".join(chr(10) + x for x in (c.get("details") or [])[:3]))
            old = str((prev.get(i["subitem_id"]) or {}).get("live") or "").split(" (")[0].split("  |  ")[0]
            if old != c["verdict"]:
                events.append([now, i["dealer"], i["mlp"], f"Live page check: {c['verdict']}", i["claude"]])
        elif i.get("live_url"):
            i["live"] = "Not checked yet"

    # Claude's work queue (Next Up): building now, then revisions, then new Assigned MLPs.
    # Inside each group the user's own numbers (typed in Excel) or --queue order win, then due date.
    def qkey(i):
        n = (prev.get(i["subitem_id"]) or {}).get("next")
        n = n if isinstance(n, (int, float)) else 10 ** 6
        if forced is not None:
            n = forced.get(i["subitem_id"], 10 ** 4 + (n if n < 10 ** 6 else 10 ** 5))
        return (queue_bucket(i), n, i["due"] or "9999-12-31", (i["dealer"] or "").lower(), i["mlp"])
    k = 0
    for i in items:
        i["next"] = None
    for i in sorted((i for i in items if queue_bucket(i) is not None), key=qkey):
        if queue_bucket(i) == 0:
            i["next"] = "Now"
        else:
            k += 1
            i["next"] = k

    for i in items:
        p = prev.get(i["subitem_id"])
        if p is None or not p.get("mlp") and not p.get("status"):
            label = "Initial load" if first_run else "New MLP assigned"
            if i.get("assigned"):
                label += f" (assigned in monday {i['assigned']})"
            events.append([now, i["dealer"], i["mlp"], label, i["status"]])
        elif p.get("status") and p["status"] != i["status"]:
            events.append([now, i["dealer"], i["mlp"], f"monday status changed: {p['status']} -> {i['status']}", i["status"]])
        if p and p.get("due") and i.get("due") and str(p["due"])[:10] != str(i["due"])[:10]:   # 2026-11-14 (since last shift)
            events.append([now, i["dealer"], i["mlp"], f"Due date moved on monday: {str(p['due'])[:10]} -> {str(i['due'])[:10]}", i["status"]])
    for sid, p in prev.items():
        if sid not in current_ids and p.get("mlp"):
            events.append([now, p.get("dealer"), p.get("mlp"),
                           "Removed from tracker (Approved in monday or unassigned)", p.get("status")])
    history = events + history

    order = {"Claude working on it": 0, "Assigned": 1, "Working on it": 2, "Waiting for Review": 3,
             "On-Hold": 4, "Stuck": 4, "Claude is done": 5}
    # Always grouped by dealership (user, 2026-11-11), then Claude's / not started / the rest, then due date.
    corder = {"Claude working on it": 0, "Revision needed": 0, "Not started": 1, "Claude is done": 2}
    items = sorted(items, key=lambda i: ((i["dealer"] or "").lower(), corder.get(i["claude"], 1), order.get(i["status"], 3),
                                         i["due"] or "9999-12-31", i["mlp"]))

    for i in items:
        pp = prev.get(i["subitem_id"]) or {}
        i["_q"], i["_a"], i["_f"], i["_pf"] = pp.get("questions"), pp.get("answers"), pp.get("folder"), platform_for(i["dealer"], platforms)
        i["_n"], i["_cn"], i["_rev"] = pp.get("notes"), pp.get("cnotes"), pp.get("revisions")
    for i in items:   # Claude Status lives in prev too (the state file keeps it)
        prev.setdefault(i["subitem_id"], {})["claude"] = i["claude"]
    json.dump([[_ser(w), d, m, t, st] for w, d, m, t, st in history],
              open(os.path.join(HERE, "history.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    write_state(items, prev, data, platforms)
    if not excel_enabled():
        added = sum(1 for i in items if i["subitem_id"] not in prev)
        print(json.dumps({"saved": TSTATE, "rows": len(items), "excel": False}))
        return
    wb = Workbook()
    ov = wb.active
    ov.title = "Overview"
    build_mlps(wb.create_sheet("MLPs"), items, prev, platforms, checked, first_run, data)
    build_overview(ov, items, prev, checked, data)
    build_summary(wb.create_sheet("Activity"), history, items)
    build_views(wb, items, history, "Activity")
    build_approved(wb, data, history, [n for n in wb.sheetnames if n.startswith("Waiting for Review")][0])
    wb.active = 0

    saved = OUT
    try:
        wb.save(OUT)
        if os.path.exists(PENDING):
            os.remove(PENDING)
    except PermissionError:
        wb.save(PENDING)
        saved = PENDING
        print("NOTE: Final_MLP_Tracker.xlsx is open in Excel and could not be released; this update is in "
              "'Final_MLP_Tracker (pending).xlsx' and moves into the main file on the next run after Excel closes it.")
    added = sum(1 for i in items if i["subitem_id"] not in prev)
    removed = sum(1 for sid, p in prev.items() if sid not in current_ids and p.get("mlp"))
    print(json.dumps({"saved": saved, "rows": len(items), "added": added if not first_run else 0,
                      "removed": removed, "first_run": first_run}))


def build_mlps(ws, items, prev, platforms, checked, first_run, data):
    ws.sheet_view.showGridLines = False
    ncol = len(COLS)
    last_col = get_column_letter(ncol)
    # row 1: title banner, row 2: subtitle, row 3: column groups, row 4: headers
    for c in range(1, ncol + 1):
        ws.cell(1, c).fill = PatternFill("solid", fgColor=NAVY)
    ws["A1"] = f"  Final MLPs  -  {data['owner']}"
    ws["A1"].font = Font(name=FONT, size=15, bold=True, color="FFFFFF")
    ws["A1"].alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 32
    st = load_state()
    ws["A2"] = (f"  {len(items)} open MLPs (not yet Approved in monday)   |   Last refresh: {data.get('refreshed_at') or checked}"
                f"   |   Automation: {st['state'].upper()}   |   monday is read-only   |   Hover a column title for what it means")
    ws["A2"].font = Font(name=FONT, size=9, italic=True, color=MUTED)
    ws.row_dimensions[2].height = 20
    for label, names, color in GROUPS:
        cols = [C[n] for n in names if n in C]
        a, b = min(cols), max(cols)
        cell = ws.cell(3, a, label)
        cell.font = Font(name=FONT, size=8, bold=True, color="3B4A66")
        cell.alignment = Alignment(horizontal="center", vertical="center")
        for c in range(a, b + 1):
            ws.cell(3, c).fill = PatternFill("solid", fgColor=color)
            ws.cell(3, c).border = Border(left=Side(style="thin", color="FFFFFF"), right=Side(style="thin", color="FFFFFF"))
        if b > a:
            ws.merge_cells(start_row=3, start_column=a, end_row=3, end_column=b)
    ws.row_dimensions[3].height = 18
    ws.row_dimensions[HEADER_ROW].height = 34
    for c, (name, width, tip) in enumerate(COLS, 1):
        cell = ws.cell(HEADER_ROW, c, name)
        style_header(cell)
        cell.comment = Comment(tip, "Tracker")
        ws.column_dimensions[get_column_letter(c)].width = width

    def L(name):
        return get_column_letter(C[name])

    band, prev_dealer, shade = False, None, None
    for n, i in enumerate(items, 1):
        r = HEADER_ROW + n
        p = prev.get(i["subitem_id"], {})
        new_group = i["dealer"] != prev_dealer
        if new_group:
            band = not band
        prev_dealer = i["dealer"]
        shade = "FFFFFF" if band else "F5F7FB"
        first_seen = as_date(p.get("first_seen")) or to_date(checked)
        due = L("Due Date")
        vals = {
            "#": n, "Dealer": i["dealer"], "MLP": i["mlp"], "Type": i.get("type", "MLP"), "monday Status": i["status"], "Claude Status": i["claude"],
            "Next Up": i.get("next"),
            "Due Date": to_date(i["due"]), "Days Left": f'=IF({due}{r}="","",{due}{r}-TODAY())',
            "Claude Started": p.get("started"), "Claude Finished": p.get("finished"),
            "Platform": platform_for(i["dealer"], platforms), "Notes": p.get("notes"), "Claude's Notes": p.get("cnotes"),
            "Revisions": p.get("revisions"), "Revision Seen": p.get("rev_seen"),
            "Your Next Step": _next_step({"dealer": i["dealer"], "mlp": i["mlp"], "monday": i["status"], "claude": i["claude"], "questions": p.get("questions"),
                                          "answers": p.get("answers"), "folder": p.get("folder"), "platform": platform_for(i["dealer"], platforms)}),
            "Project Folder": p.get("folder"), "Live URL": i["live_url"] or None, "monday": "Open",
            "Date Assigned": to_date(i["assigned"]), "First Seen": first_seen, "Subitem ID": i["subitem_id"],
            "monday Last Read": i.get("monday_read", i["status"]),
        }
        tint = ROW_TINT.get(i["claude"]) or shade
        sep = Side(style="medium", color="8EA2C8") if new_group and n > 1 else thin
        for name, v in vals.items():
            cell = ws.cell(r, C[name], v)
            cell.font = Font(name=FONT, size=10, color="1F2937")
            cell.border = Border(left=thin, right=thin, top=sep, bottom=thin)
            cell.alignment = Alignment(vertical="center", wrap_text=name in ("Questions", "Answers", "Revisions", "Notes", "Claude's Notes", "MLP", "Dealer", "Live Check", "Platform", "Your Next Step"))
            cell.fill = PatternFill("solid", fgColor=tint)
        if not new_group:   # same look as the status tabs (user 2026-11-13): dealer shown once per group;
            # the name stays in the cell (filters, sorting and Claude's scripts read it) but takes the row colour
            ws.cell(r, C["Dealer"]).font = Font(name=FONT, size=10, color=tint)
        else:
            ws.cell(r, C["Dealer"]).font = Font(name=FONT, size=10, bold=True, color="1F2937")
            ws.cell(r, C["Dealer"]).alignment = Alignment(vertical="top", wrap_text=True)
        for name in ("Due Date", "Date Assigned", "First Seen"):
            ws.cell(r, C[name]).number_format = "mmm d, yyyy"
        for name in ("Claude Started", "Claude Finished"):
            ws.cell(r, C[name]).number_format = fmt_when(ws.cell(r, C[name]).value)
        for name in ("#", "Days Left", "monday", "Next Up", "Due Date", "Subitem ID"):
            ws.cell(r, C[name]).alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(r, C["#"]).font = Font(name=FONT, size=9, color="9CA3AF")
        ws.cell(r, C["Days Left"]).number_format = "0;-0;0"
        stc = ws.cell(r, C["Claude Status"])
        stc.fill = PatternFill("solid", fgColor=STATUS_FILL.get(i["claude"], "FFFFFF"))
        stc.font = Font(name=FONT, size=10, bold=True, color="808080" if i["claude"] == "Not started" else "000000")
        stc.alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(r, C["monday Status"]).alignment = Alignment(horizontal="center", vertical="center")
        nx = ws.cell(r, C["Next Up"])
        if i.get("next") == "Now":
            nx.fill = PatternFill("solid", fgColor="C55A11")
            nx.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
        elif i.get("next"):
            nx.fill = PatternFill("solid", fgColor="F4B6C2" if queue_bucket(i) == 1 else "D9E1F2")
            nx.font = Font(name=FONT, size=11, bold=True, color="9C0006" if queue_bucket(i) == 1 else ACCENT)
        if i["claude"] in CLAUDE_STATUSES:
            ws.cell(r, C["MLP"]).font = Font(name=FONT, size=10, bold=True)
        if i["live_url"]:
            ws.cell(r, C["Live URL"]).hyperlink = i["live_url"]
            ws.cell(r, C["Live URL"]).font = Font(**LINK)
        if p.get("folder"):
            fc = ws.cell(r, C["Project Folder"])
            fc.hyperlink = "file:///" + str(p["folder"]).replace("\\", "/")
            fc.font = Font(**LINK)
        if p.get("revisions"):
            v = ws.cell(r, C["Revisions"])
            v.fill = PatternFill("solid", fgColor="FBE2E6")
            v.font = Font(name=FONT, size=10, color="9C0006")
        lines = max([sum(max(1, len(t) // w + 1) for t in str(p.get(k) or "").split(chr(10))) if p.get(k) else 1
                     for k, w in (("questions", 60), ("answers", 48), ("revisions", 60))]
                    + [len(str(i.get("live") or "").split(chr(10)))])
        ws.row_dimensions[r].height = max(22, min(14 * lines + 6, 300))
        fold = p.get("folder")
        if fold and os.path.isdir(str(fold)):
            ws.cell(r, C["MLP"]).hyperlink = str(fold)
            ws.cell(r, C["MLP"]).font = Font(name=FONT, size=10, color="1F2937", underline="single")
        link = ws.cell(r, C["monday"])
        link.hyperlink = MONDAY.format(board=i["board_id"], item=i["item_id"])
        link.font = Font(**LINK)
        if first_seen == to_date(checked) and not first_run:
            ws.cell(r, C["MLP"]).font = Font(name=FONT, size=10, bold=True, color="C00000")
    last = HEADER_ROW + len(items)
    if items:
        mrng = f"{L('monday Status')}{HEADER_ROW + 1}:{L('monday Status')}{last}"
        dv = DataValidation(type="list", formula1='"' + ",".join(MONDAY_CHOICES) + '"', allow_blank=False,
                            showErrorMessage=True, errorTitle="monday Status", error="Pick a status from the list.",
                            promptTitle="monday Status", prompt="Pick a status. Kept until monday's own status changes.", showInputMessage=True)
        ws.add_data_validation(dv)
        dv.add(mrng)
        for val in MONDAY_CHOICES:     # colours follow the value, so a dropdown change recolours the cell
            ws.conditional_formatting.add(mrng, CellIsRule(operator="equal", formula=[f'"{val}"'],
                                          fill=PatternFill("solid", fgColor=MONDAY_FILL[val], bgColor=MONDAY_FILL[val]), font=Font(bold=True, color="FFFFFF")))
        for r in range(HEADER_ROW + 1, last + 1):
            ws.cell(r, C["monday Status"]).font = Font(name=FONT, size=10, bold=True)
        ws.column_dimensions[L("monday Last Read")].hidden = True
        ws.column_dimensions[L("Revision Seen")].hidden = True
        ws.column_dimensions[L("First Seen")].hidden = True
    from openpyxl.worksheet.properties import Outline
    ws.sheet_properties.outlinePr = Outline(summaryBelow=True, summaryRight=False)
    for c in range(C["Claude Started"], len(HEADERS) + 1):
        d = ws.column_dimensions[get_column_letter(c)]
        d.outlineLevel, d.hidden = 1, True
    for name in ("First Seen", "monday Last Read", "Revision Seen"):   # Live Check: live verification declined 2026-11-13
        d = ws.column_dimensions[L(name)]
        d.outlineLevel, d.hidden = 2, True
        rng = f"{L('Days Left')}{HEADER_ROW + 1}:{L('Days Left')}{last}"
        from openpyxl.formatting.rule import FormulaRule
        dl, md0 = f"{L('Days Left')}{HEADER_ROW + 1}", f"${L('monday Status')}{HEADER_ROW + 1}"
        # overdue = past due AND the next move is ours (QA review / on hold do not count) - user 2026-11-13
        ws.conditional_formatting.add(rng, FormulaRule(formula=[f'AND(ISNUMBER({dl}),{dl}<0,{md0}<>"Waiting for Review",{md0}<>"On-Hold")'],
                                      fill=PatternFill("solid", fgColor="F8CBAD", bgColor="F8CBAD"), font=Font(color="9C0006", bold=True), stopIfTrue=True))
        ws.conditional_formatting.add(rng, FormulaRule(formula=[f'AND(ISNUMBER({dl}),{dl}<0)'], font=Font(color="808080", italic=True), stopIfTrue=True))
        ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=["0"],
                                      fill=PatternFill("solid", fgColor="FFE699"), font=Font(color="7F6000", bold=True)))
        ws.auto_filter.ref = f"A{HEADER_ROW}:{last_col}{last}"
    ws.freeze_panes = ws.cell(HEADER_ROW + 1, C["monday Status"])
    ws.sheet_view.zoomScale = 90
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.sheet_properties.tabColor = ACCENT
    ws.print_title_rows = f"{HEADER_ROW}:{HEADER_ROW}"


def _section(ov, row, title, sub=None):
    ov.cell(row, 2, title).font = Font(name=FONT, size=13, bold=True, color=NAVY)
    for c in range(2, 8):
        ov.cell(row, c).border = Border(bottom=Side(style="medium", color=ACCENT))
    if sub:
        ov.cell(row, 5, sub).font = Font(name=FONT, size=9, italic=True, color=MUTED)
        ov.cell(row, 5).alignment = Alignment(horizontal="right")
        ov.merge_cells(start_row=row, start_column=5, end_row=row, end_column=7)
    ov.row_dimensions[row].height = 24
    return row + 1


def _table_row(ov, row, values, zebra):
    for c, v in values:
        cell = ov.cell(row, c, v)
        cell.font = Font(name=FONT, size=10, color="1F2937")
        cell.alignment = Alignment(vertical="center")
        cell.border = Border(bottom=Side(style="thin", color="E5E7EB"))
        if zebra:
            cell.fill = PatternFill("solid", fgColor="F7F9FC")
    ov.row_dimensions[row].height = 20


def build_overview(ov, items, prev, checked, data):
    ov.sheet_view.showGridLines = False
    ov.sheet_properties.tabColor = NAVY
    for col, w in zip("ABCDEFGH", (2, 40, 24, 24, 24, 18, 30, 2)):
        ov.column_dimensions[col].width = w
    # title banner
    for c in range(1, 9):
        ov.cell(1, c).fill = PatternFill("solid", fgColor=NAVY)
        ov.cell(2, c).fill = PatternFill("solid", fgColor=NAVY)
    ov["B1"] = "MLP Tracker"
    ov["B1"].font = Font(name=FONT, size=22, bold=True, color="FFFFFF")
    ov["B1"].alignment = Alignment(vertical="bottom")
    ov["B2"] = f"{data['owner']}   |   Final MLPs from monday (read-only: this file never changes monday)"
    ov["B2"].font = Font(name=FONT, size=10, color="C9D3E6")
    ov["B2"].alignment = Alignment(vertical="top")
    ov.row_dimensions[1].height = 40
    ov.row_dimensions[2].height = 24
    # automation state banner (item 1)
    st = load_state()
    running = st["state"] == "Running"
    since = ""
    if st.get("since"):
        s = datetime.fromisoformat(st["since"])
        since = f"since {s:%b} {s.day}, {s:%I:%M %p}".replace(" 0", " ")
    color = "548235" if running else "C00000"
    ov.cell(4, 2, ("●  AUTOMATION RUNNING" if running else "■  AUTOMATION STOPPED"))
    ov.cell(4, 2).font = Font(name=FONT, size=14, bold=True, color="FFFFFF")
    ov.cell(4, 4, f"{since}   |   " + ("type 'stop' to stop Claude" if running else "type 'start' to let Claude build"))
    ov.cell(4, 4).font = Font(name=FONT, size=10, color="FFFFFF")
    for c in range(2, 8):
        ov.cell(4, c).fill = PatternFill("solid", fgColor=color)
        ov.cell(4, c).alignment = Alignment(vertical="center", indent=1 if c == 2 else 0)
    ov.merge_cells("B4:C4")
    ov.merge_cells("D4:G4")
    ov.row_dimensions[4].height = 34
    ov.cell(5, 2, f"Last refresh from monday: {data.get('refreshed_at') or checked}   |   "
                  "type 'refresh' to update this file from monday (refresh never starts building)")
    ov.cell(5, 2).font = Font(name=FONT, size=9, italic=True, color=MUTED)
    ov.merge_cells("B5:G5")

    mcol, ccol = get_column_letter(C["monday Status"]), get_column_letter(C["Claude Status"])
    st_rng = f"MLPs!${ccol}$5:${ccol}$500"
    md_rng = f"MLPs!${mcol}$5:${mcol}$500"
    nst = lambda sts: sum(1 for i in items if i["status"] in sts)
    you = sum(1 for i in items if not _next_step({"dealer": i["dealer"], "mlp": i["mlp"], "monday": i["status"], "claude": i["claude"],
                                                  "questions": i.get("_q"), "answers": i.get("_a"), "folder": i.get("_f"), "platform": i.get("_pf")}).startswith("Nothing"))
    cnt = lambda v: f'COUNTIF({md_rng},"{v}")'
    asg = ("Assigned", "Working on it", "Stuck")
    tiles = [
        ("OPEN MLPs", f"=COUNTA(MLPs!${get_column_letter(C['MLP'])}$5:${get_column_letter(C['MLP'])}$500)", "1E2A44", "MLPs"),
        ("ASSIGNED", "=" + "+".join(cnt(v) for v in asg), MONDAY_FILL["Assigned"], f"Assigned ({nst(asg)})"),
        ("NEEDS REVISION", "=" + cnt("Needs Revision"), MONDAY_FILL["Needs Revision"], f"Needs Revision ({nst(('Needs Revision',))})"),
        ("WAITING FOR REVIEW", "=" + cnt("Waiting for Review"), MONDAY_FILL["Waiting for Review"], f"Waiting for Review ({nst(('Waiting for Review',))})"),
        ("WAITING ON YOU", you, "C00000", "Activity"),
        ("OVERDUE (on us)", f'=COUNTIFS(MLPs!${get_column_letter(C["Days Left"])}$5:${get_column_letter(C["Days Left"])}$500,"<0",{md_rng},"<>Waiting for Review",{md_rng},"<>On-Hold")', "C00000", "MLPs"),
        ("APPROVED", len(data.get("approved") or []), MONDAY_FILL["Approved"], f"Approved ({len(data.get('approved') or [])})"),
        ("DONE, NOT YET POSTED", sum(1 for i in items if i["claude"] == "Claude is done" and i["status"] in ("Assigned", "Working on it", "Needs Revision")), "548235", "MLPs"),
    ]
    gap = Side(style="thick", color="FFFFFF")
    for k, (label, f, color, target) in enumerate(tiles):
        c = 2 + k % 4
        row = 7 + (k // 4) * 3
        lab = ov.cell(row, c, label)
        lab.font = Font(name=FONT, size=8, bold=True, color=color)
        lab.fill = PatternFill("solid", fgColor="F4F6FA")
        lab.alignment = Alignment(vertical="bottom", indent=1)
        lab.border = Border(top=Side(style="thick", color=color), left=gap, right=gap)
        val = ov.cell(row + 1, c, f)
        val.font = Font(name=FONT, size=24, bold=True, color=color)
        val.fill = PatternFill("solid", fgColor="F4F6FA")
        val.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        val.border = Border(left=gap, right=gap)
        if "BUILD TIME" in label:
            val.number_format = "[h]:mm"
        for cell in (lab, val):     # click a tile to open its sheet (2026-11-13)
            from openpyxl.worksheet.hyperlink import Hyperlink
            cell.hyperlink = Hyperlink(ref=cell.coordinate, location=f"'{target}'!A1")
        lab.value = label + "  >"
        ov.row_dimensions[row].height = 22
        ov.row_dimensions[row + 1].height = 38
    r = 7 + ((len(tiles) + 3) // 4) * 3 + 1

    # Up next (item 2): Claude's queue
    queue = sorted((i for i in items if i.get("next")), key=lambda i: (0 if i["next"] == "Now" else i["next"]))
    r = _section(ov, r, "Up next for Claude", "order = Next Up column on the MLPs sheet (type numbers there to reorder)")
    for c, h in ((2, "#  MLP"), (3, "Dealer"), (4, "Why"), (5, "Claude Status"), (6, "Due"), (7, "Platform")):
        style_header(ov.cell(r, c, h))
    ov.row_dimensions[r].height = 22
    plat = load_platforms()
    for k, i in enumerate(queue[:12]):
        r += 1
        why = {0: "Building now", 1: "Revision (goes first)", 2: "New MLP"}[queue_bucket(i)]
        _table_row(ov, r, ((2, f"{i['next']}   {i['mlp']}"), (3, i["dealer"]), (4, why), (5, i["claude"]),
                           (6, to_date(i["due"])), (7, platform_for(i["dealer"], plat))), k % 2)
        ov.cell(r, 2).font = Font(name=FONT, size=10, bold=True, color="9C0006" if queue_bucket(i) == 1 else NAVY)
        ov.cell(r, 5).fill = PatternFill("solid", fgColor=STATUS_FILL.get(i["claude"], "FFFFFF"))
        ov.cell(r, 5).font = Font(name=FONT, size=9, bold=True)
        ov.cell(r, 6).number_format = "mmm d"
        ov.cell(r, 6).alignment = Alignment(horizontal="left", vertical="center")
        if i["due"] and to_date(i["due"]) < date.today():
            ov.cell(r, 6).font = Font(name=FONT, size=10, bold=True, color="C00000")
    if not queue:
        r += 1
        ov.cell(r, 2, "Nothing in the queue.").font = Font(name=FONT, size=10, italic=True, color=MUTED)
    if len(queue) > 12:
        r += 1
        ov.cell(r, 2, f"+ {len(queue) - 12} more on the MLPs sheet").font = Font(name=FONT, size=9, italic=True, color=MUTED)
    r += 2

    # colour guide: two columns of chips
    r = _section(ov, r, "Status colours", "monday Status and Claude Status")
    guide = list(STATUS_MEANING.items())
    half = (len(guide) + 1) // 2
    for k, (stname, meaning) in enumerate(guide):
        row = r + (k % half)
        c = 2 if k < half else 5
        chip = ov.cell(row, c, stname)
        mon = stname in MONDAY_FILL and stname != "Not started"
        chip.fill = PatternFill("solid", fgColor=MONDAY_FILL[stname] if mon else STATUS_FILL[stname])
        chip.font = Font(name=FONT, size=9, bold=True, color="FFFFFF" if mon else "000000")
        chip.alignment = Alignment(horizontal="center", vertical="center")
        chip.border = Border(top=Side(style="thick", color="FFFFFF"), bottom=Side(style="thick", color="FFFFFF"))
        m = ov.cell(row, c + 1, meaning)
        m.font = Font(name=FONT, size=9, color="374151")
        m.alignment = Alignment(wrap_text=True, vertical="center")
        ov.merge_cells(start_row=row, start_column=c + 1, end_row=row, end_column=c + 2 if c == 5 else c + 2)
        ov.row_dimensions[row].height = 30
    r += half + 1

    r = _section(ov, r, "How to use")
    tips = [
        ("start / stop", "Type 'start' and Claude works the queue (Up next), one MLP at a time. Type 'stop' and Claude stops at once. The banner at the top shows which."),
        ("refresh", "Type 'refresh' to update this file from monday. It only reads monday; it does not build, revise or re-check live pages."),
        ("MLPs sheet", "One row per open Final MLP, grouped by dealership (A-Z). monday Status (dropdown, yours to change) and Claude Status (Claude's progress)."),
        ("Next Up", "Claude's work order. Revisions first, then new MLPs. Type different numbers to reorder; your order is kept."),
        ("Revisions", "Pink cells: changes QA asked for on your Final MLP / Final Mobile Check. The row turns 'Revision needed'."),
        ("Notes", "Yours - type anything; a refresh never overwrites it. Claude writes only in Claude's Notes (decisions, what each revision changed)."),
        ("Approved", "Every Final MLP / city page approved in monday, with its live page and folder."),
        ("Status sheets", "Assigned / Needs Revision / Waiting for Review: view-only lists by monday status (count on the tab), grouped by dealership, overdue in red. Type on the MLPs sheet."),
        ("Activity", "One tab for the record: waiting on you, work per week (chart), what we finished each 7 PM - 3 AM shift, and the full history (filterable, at the bottom)."),
        ("File open?", "If this file is open during an update, Claude saves and reopens it (your typed edits are kept)."),
    ]
    for k, (head, t) in enumerate(tips):
        r += 1
        h = ov.cell(r, 2, head)
        h.font = Font(name=FONT, size=10, bold=True, color=ACCENT)
        h.alignment = Alignment(vertical="top")
        c = ov.cell(r, 3, t)
        c.font = Font(name=FONT, size=10, color="374151")
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ov.merge_cells(start_row=r, start_column=3, end_row=r, end_column=7)
        ov.row_dimensions[r].height = 30 if len(t) > 100 else 17
    ov.sheet_view.zoomScale = 100
    ov.page_setup.fitToWidth = 1
    ov.page_setup.fitToHeight = 0
    ov.sheet_properties.pageSetUpPr.fitToPage = True


def build_history(h, history):
    h.sheet_view.showGridLines = False
    h.sheet_properties.tabColor = "7F7F7F"
    for c, t in enumerate(["Date & Time", "Dealer", "MLP", "What happened", "Status"], 1):
        style_header(h.cell(1, c, t))
    h.row_dimensions[1].height = 26
    for row in history:
        h.append(row)
    for c, w in enumerate([22, 22, 26, 90, 22], 1):
        h.column_dimensions[get_column_letter(c)].width = w
    styles = (("Claude started", True, "C55A11"), ("Claude finished", True, "548235"), ("Question", False, "7F6000"),
              ("Your answer", False, "375623"), ("New MLP", True, "2F5597"), ("Revision", True, "9C0006"),
              ("Automation", True, "7030A0"), ("Removed", False, "808080"), ("Live page", False, "1F6F8B"))
    for n, row in enumerate(h.iter_rows(min_row=2)):
        for cell in row:
            cell.font = Font(name=FONT, size=10, color="1F2937")
            cell.alignment = Alignment(vertical="top", wrap_text=cell.column == 4)
            cell.border = Border(bottom=Side(style="thin", color="E5E7EB"))
            if n % 2:
                cell.fill = PatternFill("solid", fgColor="F7F9FC")
        d = row[0]
        if isinstance(d.value, str) and len(d.value) == 10:
            try:
                d.value = to_date(d.value)
            except ValueError:
                pass
        d.number_format = "mmm d, yyyy  h:mm AM/PM" if isinstance(d.value, datetime) else "mmm d, yyyy"
        d.font = Font(name=FONT, size=9, color=MUTED)
        what = str(row[3].value or "")
        for prefix, bold, color in styles:
            if what.startswith(prefix):
                row[3].font = Font(name=FONT, size=10, bold=bold, color=color)
                break
    h.freeze_panes = "A2"
    h.auto_filter.ref = f"A1:E{max(h.max_row, 2)}"


def _next_step(i):
    import sys as _sys
    if HERE not in _sys.path:
        _sys.path.insert(0, HERE)
    from summary import next_step
    return next_step(i)


def build_views(wb, items, history, before):
    """Read-only view sheets by monday status (user, 2026-11-13: "separate sheet for the pages that is waiting for review,
    assigned, and revision" - "lets try it"). Rebuilt on every update; typing stays on the MLPs sheet."""
    today = date.today()
    views = [
        ("Assigned", ("Assigned", "Working on it", "Stuck"), MONDAY_FILL["Assigned"],
         [("Dealer", 22), ("MLP", 26), ("monday", 14), ("Due", 12), ("Days Left", 9), ("Claude Status", 18), ("Your Next Step", 55), ("Claude's Notes", 55), ("Notes", 30)]),
        ("Needs Revision", ("Needs Revision",), MONDAY_FILL["Needs Revision"],
         [("Dealer", 22), ("MLP", 26), ("Due", 12), ("Days Left", 9), ("What QA asked", 70), ("What Claude changed", 60), ("Claude Status", 18), ("Your Next Step", 50)]),
        ("City Pages", None, "A9180B",
         [("Dealer", 22), ("City", 26), ("monday", 14), ("Due", 12), ("Days Left", 9), ("Claude Status", 18), ("Your Next Step", 50), ("Claude's Notes", 55), ("Notes", 30)]),
        ("Waiting for Review", ("Waiting for Review",), MONDAY_FILL["Waiting for Review"],
         [("Dealer", 22), ("MLP", 26), ("Live page", 46), ("Days waiting", 11), ("Due", 12), ("Your Next Step", 30), ("Claude's Notes", 60), ("Notes", 30)]),
    ]
    def since_wfr(it):
        for when, dealer, mlp, what, _st in history:      # newest first
            if dealer == it["dealer"] and mlp == it["mlp"] and str(what).endswith("-> Waiting for Review"):
                w = when if isinstance(when, datetime) else None
                if w is None:
                    try:
                        w = datetime.strptime(str(when)[:16], "%Y-%m-%d %H:%M")
                    except ValueError:
                        return None
                return (today - w.date()).days
        return None
    pos = wb.sheetnames.index(before)
    for title, statuses, color, cols in views:
        rows = [i for i in items if (i.get("type") == "City Page" if statuses is None else i["status"] in statuses)]
        rows.sort(key=lambda i: ((i["dealer"] or "").lower(), i["due"] or "9999-12-31", i["mlp"]))
        s = wb.create_sheet(f"{title} ({len(rows)})", pos)
        pos += 1
        s.sheet_properties.tabColor = color
        s.sheet_view.showGridLines = False
        t = s.cell(1, 1, f"{title}  -  {len(rows)} {'page' if statuses is None else 'item'}{'s' if len(rows) != 1 else ''}   (view only - type on the MLPs sheet; rebuilt on every update)")
        t.font = Font(name=FONT, size=13, bold=True, color="FFFFFF")
        for c in range(1, len(cols) + 1):
            s.cell(1, c).fill = PatternFill("solid", fgColor=color)
        s.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(cols))
        s.row_dimensions[1].height = 26
        for c, (name, w) in enumerate(cols, 1):
            style_header(s.cell(2, c, name))
            s.column_dimensions[get_column_letter(c)].width = w
        prev_dealer, r = None, 2
        for i in rows:
            r += 1
            due = to_date(i["due"]) if i["due"] else None
            left = (due - today).days if due else None
            notes = str(i.get("_n") or "")
            cnotes = str(i.get("_cn") or "")
            changed = chr(10).join(l for l in cnotes.splitlines() if "Revision" in l and "done" in l)
            asked = ""
            try:
                import production
                lines = []
                for entry in str(i.get("_rev") or "").splitlines()[-2:]:
                    pts, _ps = production.triage_text(entry)
                    lines += [f"{n}. {pt[:80]}  -> {lab.split(': ', 1)[-1][:60]}" for n, pt, lab in pts]
                asked = chr(10).join(lines)
            except Exception:
                asked = chr(10).join(str(i.get("_rev") or "").splitlines()[-3:])
            nxt = _next_step({"dealer": i["dealer"], "mlp": i["mlp"], "monday": i["status"], "claude": i["claude"], "questions": i.get("_q"),
                              "answers": i.get("_a"), "folder": i.get("_f"), "platform": i.get("_pf")})
            vals = {"Dealer": i["dealer"] if i["dealer"] != prev_dealer else "", "MLP": i["mlp"] + ("  (city page)" if i.get("type") == "City Page" else ""), "City": i["mlp"], "monday": i["status"], "Due": due,
                    "Days Left": left, "Claude Status": i["claude"], "Your Next Step": nxt, "Notes": notes or None, "Claude's Notes": cnotes or None,
                    "What QA asked": asked or None, "What Claude changed": changed or None,
                    "Live page": i["live_url"] or None, "Days waiting": since_wfr(i)}
            prev_dealer = i["dealer"]
            for c, (name, _w) in enumerate(cols, 1):
                x = s.cell(r, c, vals.get(name))
                x.font = Font(name=FONT, size=10, color="1F2937", bold=(name in ("Dealer", "MLP")))
                x.alignment = Alignment(vertical="top", wrap_text=name in ("Your Next Step", "Notes", "Claude's Notes", "What QA asked", "What Claude changed", "MLP", "Dealer"))
                x.border = Border(bottom=Side(style="thin", color="E5E7EB"))
                if name == "Due" and due:
                    x.number_format = "mmm d, yyyy"
                if name == "Days Left" and left is not None and left < 0 and i["status"] not in ("Waiting for Review", "On-Hold", "Approved"):
                    x.font = Font(name=FONT, size=10, bold=True, color="C00000")
                if name == "monday" and i["status"] in MONDAY_FILL:
                    x.fill = PatternFill("solid", fgColor=MONDAY_FILL[i["status"]])
                    x.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
                if name == "Live page" and i["live_url"]:
                    x.hyperlink = i["live_url"]
                    x.font = Font(**LINK)
            if left is not None and left < 0 and i["status"] not in ("Waiting for Review", "On-Hold", "Approved"):
                s.cell(r, 2).font = Font(name=FONT, size=10, bold=True, color="C00000")
            longest = max(len(str(vals.get(n) or "")) // max(8, int(w * 1.1)) + str(vals.get(n) or "").count(chr(10)) + 1 for n, w in cols)
            s.row_dimensions[r].height = max(18, min(15 * longest, 300))
        if not rows:
            s.cell(3, 1, "Nothing here right now.").font = Font(name=FONT, size=10, italic=True, color=MUTED)
        s.freeze_panes = "C3"


def build_approved(wb, data, history, after):
    """Approved Final MLPs of the owner (user, 2026-11-13: "include here the approved pages that is under the owner.
    Create a separate sheet for those already approved"). From mlp_data.json "approved" (kept on every refresh)."""
    app = sorted(data.get("approved") or [], key=lambda a: (a["dealer"].lower(), a["mlp"]))
    removed = {}
    for when, dealer, mlp, what, _st in history:
        if str(what).startswith("Removed from tracker"):
            removed.setdefault((dealer, mlp), str(when)[:10])
    s = wb.create_sheet(f"Approved ({len(app)})", wb.sheetnames.index(after) + 1)
    s.sheet_properties.tabColor = MONDAY_FILL["Approved"]
    s.sheet_view.showGridLines = False
    cols = [("Dealer", 24), ("MLP", 30), ("Assigned", 12), ("Due", 12), ("Approved (seen)", 15), ("Live page", 58), ("monday", 9), ("Project folder (kept files)", 18)]
    t = s.cell(1, 1, f"Approved  -  {len(app)} Final MLPs approved in monday ({data.get('owner') or ''})   (view only; rebuilt on every refresh)")
    t.font = Font(name=FONT, size=13, bold=True, color="FFFFFF")
    for c in range(1, len(cols) + 1):
        s.cell(1, c).fill = PatternFill("solid", fgColor=MONDAY_FILL["Approved"])
    s.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(cols))
    s.row_dimensions[1].height = 26
    for c, (n, w) in enumerate(cols, 1):
        style_header(s.cell(2, c, n))
        s.column_dimensions[get_column_letter(c)].width = w
    try:
        folders = {(e["dealer"], e["mlp"]): e["folder"] for e in json.load(open(os.path.join(HERE, "project_folders.json"), encoding="utf-8"))["projects"]}
    except (OSError, ValueError):
        folders = {}
    r, prev_d = 2, None
    for a in app:
        r += 1
        seen = removed.get((a["dealer"], a["mlp"])) or a.get("first_seen_approved")
        before = a.get("approved_before_tracking") and not removed.get((a["dealer"], a["mlp"]))
        vals = [a["dealer"] if a["dealer"] != prev_d else "", a["mlp"], to_date(a["assigned"]) if a.get("assigned") else None,
                to_date(a["due"]) if a.get("due") else None, "before Nov 13" if before else (to_date(seen) if seen else None), a.get("live_url"), "Open", None]
        prev_d = a["dealer"]
        for c, v in enumerate(vals, 1):
            x = s.cell(r, c, v)
            x.font = Font(name=FONT, size=10, color="1F2937", bold=c in (1, 2))
            x.border = Border(bottom=Side(style="thin", color="E5E7EB"))
            x.alignment = Alignment(vertical="top")
            if c in (3, 4, 5) and v:
                x.number_format = "mmm d, yyyy"
        if a.get("live_url"):
            s.cell(r, 6).hyperlink = a["live_url"]
            s.cell(r, 6).font = Font(**LINK)
        s.cell(r, 7).hyperlink = MONDAY.format(board=a["board_id"], item=a["item_id"])
        s.cell(r, 7).font = Font(**LINK)
        f = folders.get((a["dealer"], a["mlp"]))
        if f and os.path.isdir(f):
            s.cell(r, 8, "Open folder").hyperlink = f
            s.cell(r, 8).font = Font(**LINK)
    if not app:
        s.cell(3, 1, "No approved MLPs yet.").font = Font(name=FONT, size=10, italic=True, color=MUTED)
    s.freeze_panes = "C3"


def build_weekly(wb, history, after):
    """Weekly chart (user, 2026-11-13: "a chart for the weekly task done"): per week (Mon-Sun) builds finished,
    revisions finished, approvals (MLPs leaving the tracker as Approved) and other work (work_log.md)."""
    import re
    from datetime import timedelta
    from openpyxl.chart import BarChart, Reference
    wk = lambda d: d - timedelta(days=d.weekday())
    weeks = {}
    def add(d, k):
        w = weeks.setdefault(wk(d), {"b": 0, "r": 0, "c": 0, "a": 0, "o": 0})
        w[k] += 1
    for when, _d, _m, what, _st in history:
        w = when if isinstance(when, datetime) else None
        if w is None:
            try:
                w = datetime.strptime(str(when)[:10], "%Y-%m-%d")
            except ValueError:
                continue
        t = str(what)
        if t.startswith("Claude finished") and re.search(r", [A-Z]{2}$", str(_m or "")):
            add(w.date(), "c")
        elif t.startswith("Claude finished building"):
            add(w.date(), "b")
        elif t.startswith("Claude finished revision"):
            add(w.date(), "r")
        elif t.startswith("Removed from tracker"):
            add(w.date(), "a")
    log = os.path.join(HERE, "work_log.md")
    if os.path.exists(log):
        day = None
        for line in open(log, encoding="utf-8").read().splitlines():
            m = re.match(r"## (\d{4}-\d{2}-\d{2})", line)
            if m:
                day = date.fromisoformat(m.group(1))
            elif day and line.startswith("- "):
                add(day, "o")
    s = wb.create_sheet("Weekly", wb.sheetnames.index(after) + 1)
    s.sheet_properties.tabColor = "1E2A44"
    s.sheet_view.showGridLines = False
    s.cell(1, 1, "Weekly work done (Mon - Sun)   |   rebuilt on every update").font = Font(name=FONT, size=13, bold=True, color=NAVY)
    heads = ["Week of", "MLP builds", "MLP revisions", "City pages done", "Approved", "Other work"]
    for c, h in enumerate(heads, 1):
        style_header(s.cell(3, c, h))
        s.column_dimensions[get_column_letter(c)].width = 18
    rows = sorted(weeks)[-12:]
    for k, w in enumerate(rows):
        v = weeks[w]
        s.cell(4 + k, 1, w).number_format = "mmm d, yyyy"
        for c, key in enumerate(("b", "r", "c", "a", "o"), 2):
            s.cell(4 + k, c, v[key]).alignment = Alignment(horizontal="center")
    if rows:
        ch = BarChart()
        ch.type, ch.grouping, ch.overlap = "col", "clustered", 0
        ch.title, ch.y_axis.title = "Work done per week", "Count"
        ch.height, ch.width = 9, 22
        data = Reference(s, min_col=2, max_col=6, min_row=3, max_row=3 + len(rows))
        cats = Reference(s, min_col=1, min_row=4, max_row=3 + len(rows))
        ch.add_data(data, titles_from_data=True)
        ch.set_categories(cats)
        for ser, color in zip(ch.series, ("2F75B5", "D6304A", "A9180B", "2E8B3E", "A6A6A6")):
            ser.graphicalProperties.solidFill = color
            ser.graphicalProperties.line.solidFill = color
        s.add_chart(ch, "H3")
    note = 5 + len(rows)
    s.cell(note, 1, "Approved counts MLPs that left the tracker as Approved (dated from Nov 13 on); earlier approvals have no date in monday's data.").font = Font(name=FONT, size=9, italic=True, color=MUTED)


def write_weekly(s, history, r0):
    """Weekly block on the Activity tab: builds / revisions / city pages / approvals / other work per week + chart."""
    import re
    from datetime import timedelta
    from openpyxl.chart import BarChart, Reference
    wk = lambda d: d - timedelta(days=d.weekday())
    weeks = {}
    def add(d, k):
        weeks.setdefault(wk(d), {"b": 0, "r": 0, "c": 0, "a": 0, "o": 0})[k] += 1
    for when, _d, _m, what, _st in history:
        w = when if isinstance(when, datetime) else None
        if w is None:
            try:
                w = datetime.strptime(str(when)[:10], "%Y-%m-%d")
            except ValueError:
                continue
        t = str(what)
        if t.startswith("Claude finished") and re.search(r", [A-Z]{2}$", str(_m or "")):
            add(w.date(), "c")
        elif t.startswith("Claude finished building"):
            add(w.date(), "b")
        elif t.startswith("Claude finished revision"):
            add(w.date(), "r")
        elif t.startswith("Removed from tracker"):
            add(w.date(), "a")
    log = os.path.join(HERE, "work_log.md")
    if os.path.exists(log):
        day = None
        for line in open(log, encoding="utf-8").read().splitlines():
            m = re.match(r"## (\d{4}-\d{2}-\d{2})", line)
            if m:
                day = date.fromisoformat(m.group(1))
            elif day and line.startswith("- "):
                add(day, "o")
    x = s.cell(r0, 1, "Work per week (Mon - Sun)")
    x.font = Font(name=FONT, size=12, bold=True, color=NAVY)
    heads = ["Week of", "MLP builds", "MLP revisions", "City pages done", "Approved", "Other work"]
    for c, h in enumerate(heads, 1):
        style_header(s.cell(r0 + 1, c, h))
    rows = sorted(weeks)[-12:]
    for k, w in enumerate(rows):
        s.cell(r0 + 2 + k, 1, w).number_format = "mmm d, yyyy"
        for c, key in enumerate(("b", "r", "c", "a", "o"), 2):
            s.cell(r0 + 2 + k, c, weeks[w][key]).alignment = Alignment(horizontal="center")
    r = r0 + 2 + len(rows)
    if rows:
        ch = BarChart()
        ch.type, ch.grouping, ch.overlap = "col", "clustered", 0
        ch.title, ch.y_axis.title = "Work done per week", "Count"
        ch.height, ch.width = 8, 24
        ch.add_data(Reference(s, min_col=2, max_col=6, min_row=r0 + 1, max_row=r - 1), titles_from_data=True)
        ch.set_categories(Reference(s, min_col=1, min_row=r0 + 2, max_row=r - 1))
        for ser, color in zip(ch.series, ("2F75B5", "D6304A", "A9180B", "2E8B3E", "A6A6A6")):
            ser.graphicalProperties.solidFill = color
            ser.graphicalProperties.line.solidFill = color
        s.add_chart(ch, f"A{r + 1}")
        r += 17                                  # room for the chart
    s.cell(r, 1, "Approved = MLPs that left the tracker as Approved (dated from Nov 13 on).").font = Font(name=FONT, size=9, italic=True, color=MUTED)
    return r + 1


def write_history(s, history, r0):
    """Full history at the bottom of the Activity tab (newest first, filterable)."""
    x = s.cell(r0, 1, "Full history (newest first)  -  use the filter buttons to search")
    x.font = Font(name=FONT, size=12, bold=True, color=NAVY)
    hr = r0 + 1
    for c, t in enumerate(["Date & Time", "Dealer", "MLP", "What happened", "Status"], 1):
        style_header(s.cell(hr, c, t))
    styles = (("Claude started", True, "C55A11"), ("Claude finished", True, "548235"), ("Question", False, "7F6000"),
              ("Your answer", False, "375623"), ("New MLP", True, "2F5597"), ("Revision", True, "9C0006"),
              ("Automation", True, "7030A0"), ("Removed", False, "808080"), ("Claude note", False, "1F6F8B"))
    for n, row in enumerate(history):
        r = hr + 1 + n
        for c, v in enumerate(row[:5], 1):
            cell = s.cell(r, c, v)
            cell.font = Font(name=FONT, size=10, color="1F2937")
            cell.alignment = Alignment(vertical="top", wrap_text=c == 4)
            cell.border = Border(bottom=Side(style="thin", color="E5E7EB"))
            if n % 2:
                cell.fill = PatternFill("solid", fgColor="F7F9FC")
        d = s.cell(r, 1)
        if isinstance(d.value, str) and len(d.value) == 10:
            try:
                d.value = to_date(d.value)
            except ValueError:
                pass
        d.number_format = "mmm d, yyyy  h:mm AM/PM" if isinstance(d.value, datetime) else "mmm d, yyyy"
        d.font = Font(name=FONT, size=9, color=MUTED)
        what = str(row[3] or "")
        for prefix, bold, color in styles:
            if what.startswith(prefix):
                s.cell(r, 4).font = Font(name=FONT, size=10, bold=bold, color=color)
                break
    s.auto_filter.ref = f"A{hr}:E{hr + max(1, len(history))}"


def build_summary(s, history, items=()):
    """Summary sheet (user, 2026-11-13): per day, newest first, what we finished - Claude's finished builds/revisions
    from History plus every line of work_log.md (other work: rules, automation, clean-ups, multi-project fixes)."""
    import re
    from datetime import date as _date
    days = {}
    for when, dealer, mlp, what, _st in history:
        if not str(what or "").startswith("Claude finished"):
            continue
        w = when if isinstance(when, datetime) else None
        if w is None:
            try:
                w = datetime.strptime(str(when)[:16], "%Y-%m-%d %H:%M")
            except ValueError:
                continue
        days.setdefault((w - timedelta(hours=19)).date(), []).append((w.strftime("%H:%M"), f"{dealer} - {mlp}", str(what), w))
    log = os.path.join(HERE, "work_log.md")
    if os.path.exists(log):
        day = None
        for line in open(log, encoding="utf-8").read().splitlines():
            m = re.match(r"## (\d{4}-\d{2}-\d{2})", line)
            if m:
                day = _date.fromisoformat(m.group(1))
            elif day and line.startswith("- "):
                t = re.match(r"- (\d{1,2}:\d{2}) (.*)", line)
                at, text = (t.group(1).zfill(5), t.group(2)) if t else ("00:00", line[2:])
                w = datetime.combine(day, datetime.strptime(at, "%H:%M").time())
                days.setdefault((w - timedelta(hours=19)).date(), []).append((at, "Automation / other", text, w))
    s.sheet_view.showGridLines = False
    s.sheet_properties.tabColor = "548235"
    for col, wdt in zip("ABCDEF", (20, 34, 62, 62, 20, 16)):
        s.column_dimensions[col].width = wdt
    t = s.cell(1, 1, "Activity  -  waiting on you, work per week, finished by shift (7 PM - 3 AM) and the full history   |   type 'summary' for the current shift")
    t.font = Font(name=FONT, size=14, bold=True, color=NAVY)
    s.merge_cells("A1:C1")
    s.row_dimensions[1].height = 26
    r = 2
    # Status now (user format, 2026-11-13): where every open MLP stands, dealership -> model
    import sys as _sys
    if HERE not in _sys.path:
        _sys.path.insert(0, HERE)
    from summary import status_groups
    from summary import waiting_on_you
    groups = status_groups([{"dealer": i["dealer"], "mlp": i["mlp"], "monday": i["status"], "claude": i["claude"]} for i in items])
    you = waiting_on_you([{"dealer": i["dealer"], "mlp": i["mlp"], "monday": i["status"], "claude": i["claude"], "questions": i.get("_q"),
                           "answers": i.get("_a"), "folder": i.get("_f"), "platform": i.get("_pf")} for i in items])
    r += 1
    h = s.cell(r, 1, "Waiting on you (your next step)")
    h.font = Font(name=FONT, size=11, bold=True, color="FFFFFF")
    for c in range(1, 4):
        s.cell(r, c).fill = PatternFill("solid", fgColor="C00000")
    s.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
    s.row_dimensions[r].height = 22
    for dealer, steps in you.items():
        for st in steps:
            r += 1
            s.cell(r, 2, dealer).font = Font(name=FONT, size=10, bold=True, color="1F2937")
            x = s.cell(r, 3, st)
            x.font = Font(name=FONT, size=10, color="1F2937")
            x.alignment = Alignment(wrap_text=True, vertical="top")
            s.cell(r, 2).alignment = Alignment(vertical="top")
            s.row_dimensions[r].height = max(16, 15 * (len(st) // 66 + 1))
    if not you:
        r += 1
        s.cell(r, 2, "Nothing - all clear.").font = Font(name=FONT, size=10, italic=True, color=MUTED)
    r = write_weekly(s, history, r + 2)
    r += 1
    sec = s.cell(r, 1, "Finished by shift (7 PM - 3 AM, newest first)")
    sec.font = Font(name=FONT, size=12, bold=True, color=NAVY)
    for d in sorted(days, reverse=True):
        rows = sorted(days[d], key=lambda x: x[3])
        e = d + timedelta(days=1)
        r += 1
        h = s.cell(r, 1, f"Shift {d.strftime('%a %b')} {d.day}, 7 PM  to  {e.strftime('%a %b')} {e.day}, 3 AM  -  {len(rows)} finished")
        h.font = Font(name=FONT, size=11, bold=True, color="FFFFFF")
        for c in range(1, 4):
            s.cell(r, c).fill = PatternFill("solid", fgColor=NAVY)
        s.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
        s.row_dimensions[r].height = 22
        r += 1
        for c, head in enumerate(["Time", "Dealer / MLP", "What we finished"], 1):
            x = s.cell(r, c, head)
            x.font = Font(name=FONT, size=9, bold=True, color=MUTED)
            x.border = Border(bottom=Side(style="thin", color="D9DEE7"))
        for n, (at, area, text, _w) in enumerate(rows):
            r += 1
            for c, v in enumerate([at, area, text], 1):
                x = s.cell(r, c, v)
                x.font = Font(name=FONT, size=10, color="1F2937", bold=(c == 2 and area != "Automation / other"))
                x.alignment = Alignment(vertical="top", wrap_text=(c == 3))
                x.border = Border(bottom=Side(style="thin", color="EEF1F5"))
                if n % 2:
                    x.fill = PatternFill("solid", fgColor="F7F9FC")
            s.row_dimensions[r].height = max(16, 15 * (len(text) // 66 + 1))
        r += 1
    if not days:
        r += 1
        s.cell(r, 1, "Nothing finished yet.").font = Font(name=FONT, size=10, italic=True, color=MUTED)
    write_history(s, history, r + 2)
    s.freeze_panes = "A2"


def excel(action):
    """Save+close the workbook if Excel has it open (keeps typed Notes), or reopen it afterwards."""
    import subprocess
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        os.path.join(HERE, "excel_open.ps1"), "-Path", OUT, "-Action", action],
                       capture_output=True, text=True, timeout=120)
    return r.stdout.strip()


def is_locked():
    if not os.path.exists(OUT):
        return False
    try:
        with open(OUT, "r+b"):
            return False
    except PermissionError:
        return True


if __name__ == "__main__":
    import sys
    arg = extra = None
    flags = ("--set", "--ask", "--answer", "--set-answers", "--folder", "--clear-questions", "--set-questions", "--started", "--finished", "--note")
    if len(sys.argv) >= 3 and sys.argv[1] == "--batch":
        extra = ("batch", None, sys.argv[2])
    elif len(sys.argv) >= 3 and sys.argv[1] in ("--automation", "--queue"):
        extra = (sys.argv[1][2:], None, sys.argv[2])
    elif len(sys.argv) >= 3 and sys.argv[1] in flags:
        sid, text = int(sys.argv[2]), (sys.argv[3] if len(sys.argv) > 3 else "")
        if sys.argv[1] == "--set":
            arg = (sid, text)
        else:
            extra = (sys.argv[1][2:], sid, text)
    reopen = False
    LOCK = os.path.join(HERE, ".tracker.lock")
    import time as _t
    for _ in range(60):   # wait up to 2 minutes for another session's run to finish
        if not os.path.exists(LOCK) or _t.time() - os.path.getmtime(LOCK) > 300:
            break
        _t.sleep(2)
    else:
        raise SystemExit("Another session is updating the tracker right now (.tracker.lock) - try again in a minute.")
    open(LOCK, "w").write(f"{os.getpid()} {datetime.now():%Y-%m-%d %H:%M:%S}")
    if excel_enabled() and is_locked():
        reopen = excel("release") in ("closed", "closed-protected")
    try:
        main(arg, extra)
    finally:
        try:
            os.remove(LOCK)
        except OSError:
            pass
        if reopen:
            excel("reopen")
