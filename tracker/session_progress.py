"""Show in the web app what Claude is doing from a VS Code / terminal session (user, 2026-11-13: "when you are doing
something show it in MLP tracker if its about the MLP tracker or other related to it").

Usage: python session_progress.py "<what Claude is working on>" "<step>" ["<n>/<total>"] [--next "<step> | <step> | ..."]
       (--next = the steps still to come; shown under "Next" in the tracker's Now & Next card, user 2026-11-17)
       python session_progress.py --done "<what was finished>"     (clears the chip and logs it to work_log.md)
Writes webapp/session_progress.json; the header shows "Claude (VS Code): ..." while it is fresh (under 30 min old).
Start-button jobs keep using progress.py; this file is separate so the two never overwrite each other.
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "webapp" / "session_progress.json"


def write(data):
    tmp = str(OUT) + ".tmp"
    json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, OUT)


if len(sys.argv) >= 3 and sys.argv[1] == "--done":
    write({"task": sys.argv[2], "step": "Done", "pos": "", "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    subprocess.run([sys.executable, str(HERE / "summary.py"), "--log", sys.argv[2]], cwd=HERE)
    print("session: done -", sys.argv[2])
elif len(sys.argv) >= 3:
    args, nxt = sys.argv[1:], []
    if "--next" in args:
        k = args.index("--next")
        nxt = [x.strip() for x in (args[k + 1] if k + 1 < len(args) else "").split("|") if x.strip()]
        args = args[:k] + args[k + 2:]
    elif OUT.exists():   # same task: keep the planned steps, minus the one now running
        try:
            old = json.load(open(OUT, encoding="utf-8"))
            if old.get("task") == args[0]:
                nxt = [x for x in old.get("next", []) if x.lower() != args[1].lower()]
        except ValueError:
            pass
    pos = args[2] if len(args) > 2 else ""
    write({"task": args[0], "step": args[1], "pos": pos, "next": nxt, "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    print(f"session: {args[0]} - {args[1]} {pos}".strip() + (f" (next: {' | '.join(nxt)})" if nxt else ""))
else:
    sys.exit(__doc__)
