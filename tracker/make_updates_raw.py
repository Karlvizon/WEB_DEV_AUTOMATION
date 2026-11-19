"""Turn a saved monday read-only query result into updates_raw.json for the revision check.

Usage: python make_updates_raw.py <saved query result .json/.txt>

The query (REFRESH.md step 2b) lists the parent items' subitems with their updates:
  { items(ids:[<parent item ids>]) { id subitems { id name column_values(ids:["status","person"]) { id text }
      updates(limit:15) { id created_at creator { id name } text_body assets { id name public_url }
        replies { id created_at creator { id name } text_body } } } } }

Output: {"<Final MLP subitem id>": {"Final MLP": {"status", "updates"}, "Final Mobile Check": {"status", "updates"}}}
Only subitems assigned to the owner are kept (Final MLP is matched by its subitem id in mlp_data.json).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
data = json.load(open(os.path.join(HERE, "mlp_data.json"), encoding="utf-8"))
owner = data.get("owner") or ""
tracked = {str(i["subitem_id"]): i for i in data["items"]}
mlp_parent = {str(i["item_id"]): str(i["subitem_id"]) for i in data["items"] if i.get("type", "MLP") == "MLP"}   # city pages (2026-11-13) share a parent
src = json.load(open(sys.argv[1], encoding="utf-8"))
src = src.get("data", src)
out = {}
for it in src.get("items", []):
    for sub in it.get("subitems") or []:
        name = (sub.get("name") or "").strip()
        cv = {c["id"]: c.get("text") or "" for c in sub.get("column_values") or []}
        sid = str(sub["id"])
        if sid in tracked:
            fid, key = sid, ("City Page" if tracked[sid].get("type") == "City Page" else "Final MLP")
        elif name.lower() == "final mobile check" and owner.lower() in cv.get("person", "").lower() and str(it["id"]) in mlp_parent:
            fid, key = mlp_parent[str(it["id"])], "Final Mobile Check"
        else:
            continue
        rec = out.setdefault(fid, {})
        ups = []
        for u in sub.get("updates") or []:
            ups.append({"id": u["id"], "created_at": u["created_at"], "creator": u.get("creator") or {},
                        "text_body": u.get("text_body") or "", "assets": u.get("assets") or [],
                        "replies": [{"id": r["id"], "created_at": r["created_at"], "creator": r.get("creator") or {},
                                     "text_body": r.get("text_body") or ""} for r in u.get("replies") or []]})
        rec[key] = {"status": cv.get("status"), "updates": ups}
json.dump(out, open(os.path.join(HERE, "updates_raw.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(json.dumps({fid: {k: [v["status"], len(v["updates"])] for k, v in r.items()} for fid, r in out.items()}, indent=0))
