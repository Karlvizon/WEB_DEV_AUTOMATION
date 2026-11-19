"""Record whether the claude.ai monday connector works, so the tracker header can show it (user 2026-11-13 improvement #5).

Usage: python monday_health.py connector ok
       python monday_health.py connector error "<short error>"
Claude runs this whenever a monday connector (mcp__claude_ai_monday_com__*) call fails, and again with "ok" when it works.
The API-token side is tracked by the auto-update watcher (watch.json), not here.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent / "webapp" / "monday_health.json"
if len(sys.argv) < 3 or sys.argv[1] != "connector" or sys.argv[2] not in ("ok", "error"):
    sys.exit(__doc__)
d = {}
if OUT.exists():
    try:
        d = json.load(open(OUT, encoding="utf-8"))
    except ValueError:
        d = {}
d["connector"] = {"state": sys.argv[2], "msg": (sys.argv[3] if len(sys.argv) > 3 else "")[:200],
                  "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
tmp = str(OUT) + ".tmp"
json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
os.replace(tmp, OUT)
print("monday connector:", sys.argv[2])
