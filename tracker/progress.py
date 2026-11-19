"""Tell the web app which page and step Claude is on while "start" runs (user, 2026-11-13: "Progress while Start runs").

Usage: python progress.py "<Dealer> - <MLP>" "<step>" ["<n>/<total>"]
Steps (use these words): Picked up | Reading QA / brief | Building | Fixing revision | SEO auto-fix | QA check | Final mobile check | Before/after |
                         Upload pack | Done | Queue empty
Example: python progress.py "Huston Chevrolet - 2026 Chevrolet Blazer" "QA check" "2/5"
Writes webapp/progress.json; the page header shows it next to the Start job.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

if len(sys.argv) < 3:
    sys.exit(__doc__)
out = Path(__file__).resolve().parent / "webapp" / "progress.json"
data = {"page": sys.argv[1], "step": sys.argv[2], "pos": sys.argv[3] if len(sys.argv) > 3 else "",
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
tmp = str(out) + ".tmp"
json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
os.replace(tmp, out)
print(f"progress: {data['page']} - {data['step']} {data['pos']}".strip())
