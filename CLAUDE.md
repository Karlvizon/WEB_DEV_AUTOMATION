# MLP Automation (team copy)

You are helping a member of the web team build and revise their assigned **Final MLP** pages and city pages from
monday.com. Their progress lives in the **Web Dev Tracker** web app (http://127.0.0.1:8765, started by
`tracker\start_tracker.cmd` on Windows or `tracker/start_tracker.command` on a Mac). The tracker engine is
`tracker\build_mlp_tracker.py`; it writes `tracker\tracker_state.json` and `tracker\history.json`. Everything you need
is in this folder.

**Windows or Mac:** this folder works on both. On a Mac, run `python3` wherever these notes say `python`, and write
paths with `/` instead of `\`.

## Start of every session

1. Settings come from the tracker's Settings tab (`tracker\tracker_config.json`, read through `tracker\settings.py`):
   owner name / monday ID (filled from their token on the first refresh), shift hours, folders, toolkit.
   Never use names, IDs or folders from examples in these notes.
2. Before any build or revision, read `my build rules\MY CLAUDE MEMORY.md` and EVERY file it links - the person's
   own Claude memory, chosen on the tracker's Settings tab (My build memory); it wins over generic defaults, QA's rules
   still apply on top. When a QA revision teaches a new rule, also add it to the linked file it fits best (or
   `my build rules\learned.md`). Also load the person's OWN build rules (see `my build rules\HOW TO ADD YOUR BUILD MEMORY.md`):
   their personal Claude memory, every `.md`/`.txt` in `my build rules\`, and any slash command those rules name.
   If none exist, ask about their standards before the first build and save the answers in `my build rules\`.
3. Read `toolkit\qa_feedback.md` (what QA keeps sending back) and, before marking a page done, the dealer's section
   in `tracker\webapp\dealer_lessons.md` (made by the tracker before every Start / Fix run). Say "Dealer lessons
   checked" in the tracker note.
4. Follow `tracker\REFRESH.md` for refresh, start, revisions, upload packs and the QA sweep.

## Control words

- **refresh**: `python tracker\refresh_monday.py` (reads monday with their token, updates the tracker). Report changes.
- **start**: `python tracker\build_mlp_tracker.py --automation Running`, then work the queue: revisions first, then new
  Assigned pages, one at a time. **stop**: stop at once and run `--automation Stopped`.
- **summary**: `python tracker\summary.py` and relay it as-is (monday work of the shift, no times).
- Show what you do in the tracker: `python tracker\session_progress.py "<task>" "<step>" ["n/total"]` at each step,
  `--done "<what was done>"` at the end.

## Hard rules

- **monday.com is READ-ONLY.** Never create, change or delete anything there; never post comments or updates. The
  "ready for review" note goes to the upload pack; the person posts it themselves.
- **One page at a time.** Revisions before new pages, but never interrupt the page in progress.
- **No questions to the person while working a page:** decide by `toolkit\qa_feedback.md`, then the Figma, then the
  OEM site, and log "Decided: ..." in the tracker note (`build_mlp_tracker.py --note <id> "..."`).
- **Every QA revision becomes a lesson:** after fixing it, add each QA point to `toolkit\qa_feedback.md` (or add this
  page to the existing line) before calling the revision done.
- If a monday connector call fails: `python tracker\monday_health.py connector error "<short error>"`.

## Tracker commands (run in `tracker\`)

```
python build_mlp_tracker.py --set <subitem_id> "Claude working on it" | "Claude is done"
python build_mlp_tracker.py --note <subitem_id> "Revision #N done: ..."
python build_mlp_tracker.py --folder <subitem_id> "<project folder>"
python build_mlp_tracker.py --automation Running | Stopped
python production.py pack "<project folder>"          upload pack (to-post\) after every build / revision
node "<toolkit>\tools\qa\qa_sweep.js" "<project folder>"   QA sweep before marking a page done
python seo_fix.py "<project folder>" [--dry]           SEO auto-fix: Title Case headings (caps via CSS), heading spaces, alt text
```
