"""Batch city pages (user, 2026-11-20: "go ahead with 1, 2 and 3" - #3 "build similar pages as a batch").

Pages under the same monday parent item (e.g. One Legacy Motors "Month 3-4 - We Buy Page [NOV-DEC]": 6 cities) share
one design. Step 1 "sample": Claude builds the FIRST page fully and writes a reusable copy script next to it.
The user looks at the sample in the tracker. Step 2 "copy": Claude makes every other page from the sample with that
page's own content doc (much cheaper than full builds), each with SEO fix, QA sweep, Final mobile check and pack.

State: webapp/batches.json  {parent item_id: {sample, dealer, parent, sids, started, copy_started}}
"""
import json
import os
from datetime import datetime
from pathlib import Path

APP = Path(__file__).resolve().parent
FILE = APP / "batches.json"
STATE = APP.parent / "tracker_state.json"


def _read(p, default):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return default


def load():
    return _read(FILE, {})


def save(d):
    tmp = FILE.with_suffix(".tmp")
    json.dump(d, open(tmp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    os.replace(tmp, FILE)


def pending(i):
    return i.get("claude") == "Not started" and i.get("status") in ("Assigned", "Working on it")


def group(item_id):
    """All city pages under one monday parent, in monday order (subitem id)."""
    items = _read(STATE, {}).get("items", [])
    g = [i for i in items if str(i.get("item_id")) == str(item_id) and i.get("type") == "City Page"]
    return sorted(g, key=lambda i: int(i["subitem_id"]))


def state():
    """For /api/state: each batch + whether the sample is done and which pages are still to copy."""
    out = {}
    for pid, b in load().items():
        g = {str(i["subitem_id"]): i for i in group(pid)}
        s = g.get(str(b.get("sample")))
        todo = [int(x) for x in b.get("sids", []) if str(x) != str(b.get("sample")) and str(x) in g and pending(g[str(x)])]
        out[pid] = {**b, "sample_name": (s or {}).get("mlp"), "sample_claude": (s or {}).get("claude"),
                    "sample_done": bool(s) and s.get("claude") == "Claude is done",
                    "todo": todo}
    return out


def _common(sid):
    return ("SEO auto-fix: python seo_fix.py '<project folder>' --sid " + str(sid) + ". Then the QA sweep, then the Final "
            "mobile check ({FMC}): fix every FIX line and run it again until there are none, and check the "
            "qa/final-mobile/390-*.png screenshots against the 'Mobile (Final Mobile Check)' rules in "
            "_mlp-toolkit/qa_feedback.md. Register the folder (build_mlp_tracker.py --folder), make the upload pack "
            "(production.py pack), write what you did and every 'Decided: ...' with build_mlp_tracker.py --note, and mark "
            "it 'Claude is done'. ")


def _copy_common(sid, sample_name):
    """Copied city pages (user, 2026-11-20): "you dont need to check them one by one. you just need to check the design
    of that 1 page and implement it to others. Just be mindful of their content since every city have a different
    content." The design was checked on the sample - each copy gets a CONTENT check, not a full design QA."""
    return ("SEO auto-fix: python seo_fix.py '<project folder>' --sid " + str(sid) + ". The design was already checked on "
            "the sample " + str(sample_name) + " - do NOT run the full QA sweep, Final mobile check or screenshot review "
            "for this page. Do a CONTENT check instead: (1) no word of the sample's city/state is left anywhere (text, "
            "headings, meta title/description, alt text, image file names, links/URLs); (2) every heading and paragraph of "
            "this page's content doc is on the page word for word, nothing from the sample's doc remains, nothing missing; "
            "(3) same sections, classes and buttons as the sample (only text/city differs); (4) button links point to this "
            "city's/dealer's URLs from the doc. Only when this page's text is clearly longer or shorter than the sample's in "
            "a section (about 30% or more, or an extra/missing item in a list or grid) look at that section in Edge at 1920 "
            "and 390 and fix it the sample's way. Register the folder (build_mlp_tracker.py --folder), make the upload pack "
            "(production.py pack), write what you did and every 'Decided: ...' with build_mlp_tracker.py --note (say "
            "'Content checked; design from the sample'), and mark it 'Claude is done'. ")


def sample_prompt(item_id, base_prompt):
    """base_prompt = server.build_prompt() for the first page. Adds the batch part."""
    g = group(item_id)
    todo = [i for i in g if pending(i)]
    first, rest = todo[0], todo[1:]
    b = load()
    b[str(item_id)] = {"sample": int(first["subitem_id"]), "dealer": first["dealer"], "parent": first.get("item_id"),
                       "sids": [int(i["subitem_id"]) for i in todo], "started": datetime.now().strftime("%Y-%m-%d %H:%M")}
    save(b)
    names = ", ".join(i["mlp"] for i in rest)
    return first, base_prompt.replace("Finish with a short plain report.", "") + (
        f" BATCH SAMPLE: this page is the sample for a batch of {len(todo)} city pages under the same monday parent "
        f"(the others: {names}). They share this design and differ only in the city and their own content doc. After the "
        "page is done, write a reusable script batch_from_sample.py in the dealer's city-pages folder (next to the city "
        "folders): python batch_from_sample.py '<sample folder>' '<new city folder>' makes the new page from the sample "
        "using the new folder's content-doc.txt - swap the city everywhere, replace every content block with the doc's "
        "text word for word, copy assets and cms-fields under the new city's names, and STOP with a clear error if the "
        "doc's structure does not match the sample (never guess). Test it once into a temporary folder and delete that "
        "folder. Do not build the other pages - the user looks at the sample first, then presses 'Copy sample' in the "
        "tracker. Put 'Batch sample for " + str(len(todo)) + " pages - batch_from_sample.py ready' in the note. "
        "Finish with a short plain report.")


def ensure(item_id):
    """No batch yet but a page of this group is already built (e.g. Start built Kansas City first): use the newest
    built page as the sample for the pages that are not started."""
    b = load()
    if str(item_id) in b and b[str(item_id)].get("sample"):
        return
    g = group(item_id)
    done = [i for i in g if i.get("claude") == "Claude is done"]
    todo = [i for i in g if pending(i)]
    if not done or not todo:
        return
    s = done[-1]
    b[str(item_id)] = {"sample": int(s["subitem_id"]), "dealer": s["dealer"], "parent": s.get("item_id"),
                       "sids": [int(s["subitem_id"])] + [int(i["subitem_id"]) for i in todo],
                       "started": datetime.now().strftime("%Y-%m-%d %H:%M"), "from_done_page": True}
    save(b)


def copy_prompt(item_id, fmc):
    ensure(item_id)
    b = load().get(str(item_id))
    if not b:
        return None, None, 0
    st = state().get(str(item_id)) or {}
    g = {str(i["subitem_id"]): i for i in group(item_id)}
    todo = [g[str(s)] for s in st.get("todo", [])]
    if not todo:
        return None, None, 0
    sample = g.get(str(b["sample"])) or {}
    lst = "; ".join(f"{i['mlp']} (subitem {i['subitem_id']})" for i in todo)
    n = len(todo)
    name = f"{b['dealer']} - {n} city pages from {sample.get('mlp', 'the sample')}"
    return name, (
        f"batch copy  (sent from the MLP Tracker 'Copy sample' button). The user checked the sample page "
        f"{b['dealer']} - {sample.get('mlp')} (subitem {b['sample']}). Make these {n} city pages from it, one at a time, "
        f"in this order: {lst}. For EACH page: mark it with build_mlp_tracker.py --set <subitem id> 'Claude working on it'; "
        "make its folder next to the sample's; download its content doc from monday (Link column, Google Drive) into "
        "content-doc.txt; run batch_from_sample.py from the dealer's city-pages folder (if that script is not there yet, "
        "first write it from the sample: python batch_from_sample.py '<sample folder>' '<new city folder>' swaps the city "
        "everywhere, puts the doc's text in word for word, copies assets and cms-fields under the new names, and STOPS "
        "with a clear error when the doc does not match the sample) (if the script stops because this "
        "doc differs, fix the script or build this page the normal way - decide by the QA rules, never ask); then "
        + _copy_common("<subitem id>", sample.get("mlp")) +
        "In each note also write 'Copied from the sample " + str(sample.get("mlp")) + " (batch)'. Report progress with "
        f"python progress.py '<dealer> - <city>' '<step>' '<k>/{n}'. Never touch the sample page or any other page. "
        "monday is READ-ONLY. If a monday connector call fails run python monday_health.py connector error "
        "'<short error>'. Finish with a short plain report: which pages are done and anything QA should know."), n


def mark_copy(item_id):
    b = load()
    if str(item_id) in b:
        b[str(item_id)]["copy_started"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save(b)
