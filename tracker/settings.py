"""Shared settings for the MLP tracker (user, 2026-11-13: "lets add a setting in web app").

Values live in tracker_config.json (edited on the web app's Settings tab). Every script reads them through get().
The monday API token is NOT in tracker_config.json: it stays in %APPDATA%\\MLP Tracker\\monday_token.txt (or the
MONDAY_API_TOKEN environment variable) and the web app only ever shows its last 4 characters.
"""
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "tracker_config.json"
import plat  # noqa: E402   (Windows: %APPDATA%\MLP Tracker - Mac: ~/Library/Application Support/MLP Tracker)
TOKEN_FILE = plat.app_dir() / "monday_token.txt"

DEFAULTS = {
    "excel": False,
    "owner_name": "",   # filled from your monday token on the first refresh
    "owner_id": 0,
    "workspace_id": 4849162,
    "skip_boards": ["Admin", "Content", "SEO", "Account Management", "Dealer Login", "GA4", "Looker", "Mailing",
                    "SEO Implementation", "November", "Monthly Report", "DL Board Template"],
    "shift_start": 19,
    "shift_hours": 8,
    "mlp_root": "",      # empty = <folder that holds MLP Automation>\MLP
    "city_root": "",     # empty = <folder that holds MLP Automation>\CITY PAGES
    "toolkit_root": "",  # empty = MLP Automation\toolkit
    "platform_overrides": {},
    # auto-update + pop-ups (user, 2026-11-13: "build it with pop ups")
    "watch_enabled": True,
    "watch_minutes": 3,   # team default (2026-11-19): every tracker shares the account's 10,000 monday calls/day
    "watch_when": "shift",
    "alert_revision": True,
    "alert_new": True,
    "alert_approved": True,
    "alert_due": True,
    "fix_from_popup": True,
    "auto_qa": True,
    "qa_report_day": "Fri",     # weekly QA report is made after this day's shift (user 2026-11-14)            # run the QA sweep by itself on every ready page that changed (user 2026-11-14)
    "alert_claude_done": True,
    # "new version available" (user, 2026-11-19 #8): the shared folder (Google Drive for desktop / OneDrive / network)
    # where the team zips + latest.json are published. Teammates: the folder they get updates from. Lead: the builder
    # (make_team_package.py) copies the new zips there. Empty = no update check.
    "updates_folder": "",  # pop-up when a Start / Fix it now run finishes or stops on its own     # "Fix it now" button on revision pop-ups (always asks before Claude starts)
}

# what the Settings tab may change, with a type check each
TYPES = {"owner_name": str, "owner_id": int, "workspace_id": int, "skip_boards": list, "shift_start": int,
         "shift_hours": int, "mlp_root": str, "city_root": str, "toolkit_root": str, "platform_overrides": dict,
         "watch_enabled": bool, "watch_minutes": int, "watch_when": str, "alert_revision": bool, "alert_new": bool,
         "alert_approved": bool, "alert_due": bool, "fix_from_popup": bool, "alert_claude_done": bool, "auto_qa": bool, "qa_report_day": str,
         "updates_folder": str}
PLATFORMS = ["Dealer Inspire", "DealerOn", "DDC", "Dealer.com", "Apollo", "Dealer eProcess", "Sincro", "Fox Dealer",
             "Dealer Spike", "Other"]


def load():
    try:
        cfg = json.load(open(CONFIG, encoding="utf-8"))
    except (OSError, ValueError):
        cfg = {}
    out = dict(DEFAULTS)
    out.update({k: v for k, v in cfg.items() if v is not None})
    base = HERE.parent                                   # the MLP Automation folder
    out["toolkit_root"] = out.get("toolkit_root") or str(base / "toolkit")
    out["mlp_root"] = out.get("mlp_root") or str(base.parent / "MLP")
    out["city_root"] = out.get("city_root") or str(base.parent / "CITY PAGES")
    return out


def get(key):
    return load().get(key, DEFAULTS.get(key))


def validate(changes):
    """Return (clean dict, error or None) for values sent from the Settings tab."""
    clean = {}
    for k, v in changes.items():
        if k not in TYPES:
            return None, f"unknown setting: {k}"
        t = TYPES[k]
        try:
            if t is bool:
                v = v if isinstance(v, bool) else str(v).strip().lower() in ("1", "true", "yes", "on")
            elif t is int:
                v = int(str(v).strip())
            elif t is str:
                v = str(v).strip()
            elif t is list:
                v = [s.strip() for s in (v if isinstance(v, list) else str(v).split(",")) if str(s).strip()]
            elif t is dict:
                if not isinstance(v, dict):
                    raise ValueError
                v = {str(a).strip(): str(b).strip() for a, b in v.items() if str(a).strip() and str(b).strip()}
        except (TypeError, ValueError):
            return None, f"{k}: wrong value"
        if k == "shift_start" and not 0 <= v <= 23:
            return None, "Shift start must be an hour from 0 to 23"
        if k == "shift_hours" and not 1 <= v <= 16:
            return None, "Shift length must be 1 to 16 hours"
        if k in ("mlp_root", "city_root", "toolkit_root") and not Path(v).is_dir():
            return None, f"Folder not found: {v}"
        if k == "watch_minutes" and v not in (1, 2, 5, 10, 15):
            return None, "Check every 1, 2, 5, 10 or 15 minutes"
        if k == "watch_when" and v not in ("shift", "always"):
            return None, "Auto-update runs during your shift or always"
        if k == "owner_name" and not v:
            return None, "Your monday name can't be empty"
        clean[k] = v
    return clean, None


def save(changes):
    clean, err = validate(changes)
    if err:
        return err
    try:
        cfg = json.load(open(CONFIG, encoding="utf-8"))
    except (OSError, ValueError):
        cfg = {}
    cfg.update(clean)
    tmp = CONFIG.with_suffix(".tmp")
    json.dump(cfg, open(tmp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    os.replace(tmp, CONFIG)
    return None


def token():
    t = os.environ.get("MONDAY_API_TOKEN", "").strip()
    if not t and TOKEN_FILE.exists():
        t = TOKEN_FILE.read_text(encoding="utf-8").strip()
    return t


def save_token(t):
    t = (t or "").strip()
    if len(t) < 20 or any(c.isspace() for c in t):
        return "That doesn't look like a monday token (it's one long line with no spaces)."
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(t + "\n", encoding="utf-8")
    return None


FIGMA_TOKEN_FILE = plat.app_dir() / "figma_token.txt"   # Figma key (2026-11-20): read-only design measurements, no Claude tokens


def figma_token():
    t = os.environ.get("FIGMA_TOKEN", "").strip()
    if not t and FIGMA_TOKEN_FILE.exists():
        t = FIGMA_TOKEN_FILE.read_text(encoding="utf-8").strip()
    return t


def save_figma_token(t):
    t = (t or "").strip()
    if len(t) < 20 or any(c.isspace() for c in t):
        return "That doesn't look like a Figma key (it's one long line with no spaces, usually starting with figd_)."
    FIGMA_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    FIGMA_TOKEN_FILE.write_text(t + chr(10), encoding="utf-8")
    return None


# When the Figma key expires (user, 2026-11-20: "if the token is nearly expired give notification to the tracker").
# Figma does not tell the API when a key expires, so the date the user saw in Figma is kept here (no secret in it).
FIGMA_META = plat.app_dir() / "figma_key.json"
FIGMA_REFUSED = plat.app_dir() / "figma_refused.txt"


def figma_meta():
    try:
        return json.loads(FIGMA_META.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_figma_meta(expires, saved=None):
    """expires = 'YYYY-MM-DD' from Figma, or '' = not given (then 90 days after saving is assumed and shown as a guess)."""
    from datetime import date, timedelta
    m = figma_meta()
    if saved:
        m["saved"] = saved
    m.setdefault("saved", date.today().isoformat())
    if expires:
        m["expires"], m["estimated"] = expires, False
    elif saved or not m.get("expires"):
        m["expires"], m["estimated"] = (date.fromisoformat(m["saved"]) + timedelta(days=90)).isoformat(), True
    FIGMA_META.parent.mkdir(parents=True, exist_ok=True)
    FIGMA_META.write_text(json.dumps(m), encoding="utf-8")
    return m


def figma_hint():
    t = figma_token()
    return ("..." + t[-4:]) if t else ""


def token_hint():
    t = token()
    return ("..." + t[-4:]) if t else ""
