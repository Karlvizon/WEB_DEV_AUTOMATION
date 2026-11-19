"""Claude Code status line -> Web Dev Tracker "Claude usage" chip (user, 2026-11-19: "can we add a feature on the web dev
tracker on how many percent is claude code before we reach the limit").

Claude Code runs this as its statusLine command (~/.claude/settings.json) and passes the documented status-line JSON on
stdin. For Pro / Max plans it holds rate_limits.five_hour / seven_day {used_percentage, resets_at (epoch s)} - the same
numbers /usage shows. We save them to <app dir>/claude_usage.json (plat.app_dir(): %APPDATA%\\MLP Tracker on Windows,
~/Library/Application Support/MLP Tracker on Mac) and print one short line for Claude Code's own status bar.
Never fails loudly: any problem -> a plain line, the old file is kept.
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import plat
    OUT = plat.app_dir() / "claude_usage.json"
except Exception:   # pragma: no cover - plat.py missing
    OUT = Path(os.environ.get("APPDATA", str(Path.home()))) / "MLP Tracker" / "claude_usage.json"


def main():
    try:   # Windows consoles default to cp1252; Claude Code reads the line as UTF-8
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        data = {}
    rl = data.get("rate_limits") or {}
    win = {}
    for k in ("five_hour", "seven_day"):
        w = rl.get(k) or {}
        if w.get("used_percentage") is not None:
            win[k] = {"used": round(float(w["used_percentage"]), 1), "resets_at": w.get("resets_at")}
    if win:
        try:
            OUT.parent.mkdir(parents=True, exist_ok=True)
            tmp = OUT.with_suffix(".tmp")
            tmp.write_text(json.dumps({"at": int(time.time()), **win,
                                       "model": (data.get("model") or {}).get("display_name")}), encoding="utf-8")
            os.replace(tmp, OUT)
        except OSError:
            pass
    parts = []
    if "five_hour" in win:
        parts.append(f"5h {win['five_hour']['used']:.0f}%")
    if "seven_day" in win:
        parts.append(f"week {win['seven_day']['used']:.0f}%")
    model = (data.get("model") or {}).get("display_name") or "Claude"
    print(f"{model}" + (" · " + " · ".join(parts) if parts else ""))


if __name__ == "__main__":
    main()
