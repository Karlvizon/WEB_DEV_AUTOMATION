> **Team copy.** These are the team lead's tracker notes. "The user" below = the team lead who set each rule; they
> apply to everyone. `<toolkit>` = the `toolkit` folder of MLP Automation (Settings tab > Folders shows the path).
> Folders and names come from YOUR Settings tab, never from the examples here.

# Refresh the Final MLP tracker

**THE TRACKER IS A LOCAL WEB APP (user, 2026-11-13: "lets proceed with phase 1 and after that we will only use the web app"):**
http://127.0.0.1:8765 - desktop shortcut "MLP Tracker" (start_tracker.cmd starts webapp/server.py hidden if needed).
`build_mlp_tracker.py` is the engine: it writes tracker_state.json + history.json (tracker_config.json {"excel": false} =
no workbook; set true to produce Excel again). The page reloads itself when those files change. The user edits Notes,
Next Up and monday Status in the web app (saved into tracker_state.json under .tracker.lock; the engine keeps them).
The old workbook and excel_open.ps1 were removed 2026-11-13 (web app only; history is in history.json). Wherever this file says
"workbook", "sheet", "tab" or "Excel", read: the web app (same tabs: All, Waiting on you, Assigned, Needs Revision,
City Pages, Waiting for Review, Approved, Activity).
Phase 2 (2026-11-13): the page header has Refresh / Start / Stop buttons. Refresh and Start run this routine through
headless `claude -p` (webapp/server.py run_action, read-only monday tool only, one job at a time, log in webapp/jobs/);
Stop kills the job and sets the automation to Stopped. The server starts with Windows (Startup shortcut
"MLP Tracker server"). A headless run must follow the same rules: monday read-only, no questions, light on the PC.
**Direct refresh (2026-11-13, user: "lets do number 1"):** `python refresh_monday.py` does steps 1-5 in Python with the
user's own monday API token (%APPDATA%\MLP Tracker\monday_token.txt or env MONDAY_API_TOKEN), no Claude, no tokens,
read-only (mutations refused). The Refresh button uses it when the token exists, else falls back to headless Claude.
`--check` tests the token. Intake still writes brief.json; Figma / content doc are opened on "start".
**Settings tab (2026-11-13, user: "add a setting in web app"):** owner name / person id, workspace id, boards to skip,
shift hours, folder roots, dealer platform overrides and the QA rules file (qa_feedback.md) are edited on the web app's
Settings tab (http://127.0.0.1:8765/#settings). They live in tracker_config.json and every script reads them through
settings.py - change them there, not in the code. The monday token is set/tested there too (stored only in its own file).
**Auto-update + page features (2026-11-13, user: "build it with pop ups ..."; "the refresh button is not necessary"):**
- No Refresh button any more. webapp/features.py watcher: every N minutes (Settings; default 2, during the shift) it runs
  `refresh_monday.py --signature` (board change times + newest comments, ~2 s, read-only); only when that changed it runs
  the full direct refresh, then Windows pop-ups (webapp/toast.ps1) for: revision, new page, approved, due today/tomorrow.
  "Check monday now" on the Settings tab forces a check at any hour. Typing "refresh" in Claude Code still works.
- Start runs Claude with stream-json: readable log, live activity, tokens, and a cost record in webapp/jobs/costs.json
  (Activity tab "Claude runs and cost"). **During "start", report progress at every step:**
  `python progress.py "<Dealer> - <MLP>" "<step>" "<n>/<total>"` (Picked up, Reading QA / brief, Building, Fixing revision,
  QA check, Before/after, Upload pack, Done; "-" "Queue empty" at the end).
- "Mark as posted" (row + detail): tracker_state `posted` timestamp, kept by the engine (PREV_KEYS); counts while it is
  newer than Claude's last finish, so a new revision un-posts it. Next step then says nothing to do; summary lists it under
  Waiting for review ("posted - monday not updated yet").
- Activity tab: shift summary button (summary.py, with Copy), QA patterns (history "Revision requested" rows labelled
  with production.py RULES; unmatched points listed), Claude runs and cost. "VS Code" buttons open the dealer folder
  (mlp_root/<dealer>, or city_root for city pages).
**Safety + shift features (2026-11-13, user: "1,2,5,6"):**
- Daily backup (webapp/features.py daily_jobs): backups/<date>/ = tracker_state, history, mlp_data, project_folders,
  tracker_config, work_log, automation_state, cms_directory, costs, watch + qa_feedback.md; keeps 14 days (+5 safety copies
  made before a restore, +10 manual). Restore / Back up now on the Settings tab. Never delete backups/ in a clean-up.
- End of shift: when the shift ends the summary is saved to shift-reports/<shift date> shift.txt, copied to the clipboard,
  and a pop-up says so (Activity tab lists saved reports).
- "Mark as posted" first runs the QA sweep (qa_sweep.js, ~5-60 s) and lists any FIX lines before you confirm.
- Keep-alive: Task Scheduler task "MLP Tracker keep-alive" runs keepalive.py every minute (and at log-on); it starts
  webapp/server.py when 127.0.0.1:8765 does not answer. Restart the server = just stop it; it is back within a minute.
**monday API budget (2026-11-13):** A3 is on the Pro plan = 10,000 monday API calls per day for the WHOLE account
(personal tokens count; usage was 200-1,300/day). Keep the tracker lean: the change check is TWO calls
(`refresh_monday.py --signature` = subitems + newest comments under the parent items of your open pages, plus - since
2026-11-19, user: "can we make the update live?" - the activity log of every dealer subitem board for the last 20 min:
an `add_owner` event for you on a subitem the tracker doesn't know = new page assigned, so it shows within ~2 minutes
instead of waiting for the 30-minute check; board list cached in webapp/subitem_boards.json by every full refresh).
A full refresh (~10 calls) runs only when that changes or every 30 minutes, no `me` call except --check. Truly instant
(monday webhooks) is not possible: monday cannot reach a tracker that only runs on 127.0.0.1.
`--usage` prints the account's daily use (shown on the Settings tab).
**"Fix it now" (2026-11-13):** revision pop-ups carry a "Fix it now" button (Settings switch fix_from_popup) that opens
/#fix=<id>; the page asks first, then POST /api/run {action:"fix", sid} runs headless Claude on THAT revision only
(server.py fix_prompt: checklist -> fixes -> QA sweep -> before/after -> pack -> --note "Revision #N done" -> Claude is done,
progress.py at each step). Refused while Start runs (Start does revisions first). Cost shows as "fix" in costs.json.


Run in Claude Code by typing **"refresh"**. There is no automatic schedule: the tracker updates only when the user asks
(user, 2026-11-12). Old backups and schedule files were deleted (user, 2026-11-12).

**Control words (user, 2026-11-12):** "stop" = stop the automation immediately and wait. "start" = start/resume the
automation (builds and revisions). "refresh" = only update the Excel from monday (steps 1-4 and 5); it does not build,
work revisions, or run step 4b live checks unless the user asks.

**"summary" (user, 2026-11-13):** list everything we did during the shift, **7 PM to 3 AM** (user: "what we did from 7pm
to 3am"); after midnight that is the shift that started the evening before. "summary for <date>" = the shift that started
that date at 7 PM. Work outside those hours is listed separately at the end, properly organised. It does
not refresh or build. Run `python summary.py [YYYY-MM-DD]` (tracker History rows for the day + `work_log.md`) and give
the user the list in the user's format (2026-11-13), each group as Dealership then its models:
I'm done with (finished that day) / Waiting for review / MLP is done but not yet posted (upload & post, or revision ready -
post it) / Working on it now / Needs revision / Not started yet / On hold / Other work. `summary.py` prints exactly this;
`--detail` adds every History row. The Summary sheet shows the same groups at the top (Status now).
**Work log:** whenever Claude finishes a piece of work that is not an MLP History event (rule changes, tracker/automation
changes, clean-ups, fixes across several projects, a refresh's findings), log it right away:
`python summary.py --log "<what was done, plain words>"`. MLP events (build started/finished, revisions, questions,
answers, monday status changes) are already in the history (history.json, shown at the bottom of the Activity tab) with date and time.

**No questions to the user (2026-11-13):** decide with QA's rules (`_mlp-toolkit/qa_feedback.md`), then the Figma; record
"Decided: ..." in the Claude's Notes column with `--note` (the Notes column is the user's only). **After every revision:** `--note <id> "Revision #N done: <what changed>"`.
Several tracker changes at once: `--batch file.json` ([[kind, id, text], ...]) = one Excel close/reopen.
**City pages are part of this automation (user, 2026-11-13: "dont create a separate automation we will include it on the
MLP automation"):**
- Step 2 query: also keep the owner's subitems whose PARENT item is named "City Pages" (one subitem per city). Run the
  step-2 query with only the person rule (no name rule) and keep `name contains "Final MLP"` OR `parent_item.name contains
  "City Page"`. In mlp_data.json a city is an item with `"type": "City Page"`, `mlp` = the city ("Frostproof, FL"),
  `item_id` = the City Pages item; Approved cities go to "approved" with the same type.
- Step 2b: include the City Pages parent ids; make_updates_raw.py maps each city by its own subitem id ("City Page").
  A QA comment on a city after your last post on ANY city of that item = revision (one reply covers all cities).
- Folders: `<City pages folder (Settings tab)>\<Dealer>\<City>` (slash removed: "MeadeHaines City, FL"); add them to project_folders.json
  with `"type": "City Page"`. Build rules: the dealer's city-page master (Huston CDJR: Frostproof - see its project memory
  huston-cdjr-city-pages): fix the master, then carry the same change to every city of that dealer, and list all updated
  cities in the review note / Claude's Notes.

**Production routine (user, 2026-11-13: "build the Production features"):**
- New MLP intake (on refresh, for every new Assigned MLP): read its Final MLP subitem updates with `body`
  (`{ items(ids:[<subitem>]) { updates(limit:30) { id created_at creator{name} text_body body } } }`), save the result,
  run `python production.py intake <saved.json> "<Dealer>" "<MLP>"` -> project folder + brief.json (visible links only;
  hidden leftover links ignored; cross-dealer links flagged) + the dealer's last page as the base (fonts, CTA links, CDN,
  colours). Then open the Figma and content doc with the MCP tools to confirm both load, so "start" builds right away.
- Revisions: `save_revision` writes `checklist.md` (QA's points numbered, each matched to a known fix or marked NEW);
  the Needs Revision sheet shows it. NEW points go into `_mlp-toolkit/qa_feedback.md` after the fix.
  **MANDATORY (user, 2026-11-13: "make sure that you are saving all the revision in your memory ... so we will not do the same
  mistake again"):** a revision is NOT done until every QA point in it is in `qa_feedback.md` as a general lesson (what went wrong,
  the QA quote, the rule for next time). Points already listed: add the MLP name to that line. If it can be checked by code, add
  it to `qa_sweep.js` too. Say "Lessons saved: ..." in the revision note.
- When a build or revision is done: before/after images for each fixed point
  (`node _mlp-toolkit/tools/qa/beforeafter.js "<project>" "<old preview>" 1920 "<n-label>|<selector>" ...`, mobile at 390),
  then `python production.py pack "<project>"` -> `to-post/` (images in batches of 8, CMS fields, monday note,
  before/after, README). Your Next Step points to it.
- Tracker data keeps the owner's Approved Final MLPs (`mlp_data.json` "approved": dealer, mlp, subitem_id, item_id,
  board_id, assigned, due, live_url) for the Approved sheet; the Weekly sheet charts builds / revisions / approvals / other work.
**QA sweep (user, 2026-11-13):** before marking any build or revision "Claude is done", run
`node "<toolkit>/tools/qa/qa_sweep.js" "<project folder>"` and fix every FIX line (points QA keeps
sending back: hero per Figma + rule to the end of the title, MLP top margin = left margin + title, mobile photo fade,
blurry photos, disclaimer font, photo touching a band). List: `_mlp-toolkit/qa_feedback.md`. On "start", pages whose
files are not yet posted are swept and fixed too (free to change before upload).
**Final mobile check on every revision (user, 2026-11-16: "include Final mobile check in automation if there is
revisions"):** after the fixes and the QA sweep, every revision (Final MLP, Final Mobile Check or City Page; Start and
"Fix it now" alike) runs `node "<toolkit>/tools/qa/final_mobile_check.js" "<project folder>"` (phones 390/375/430: sideways scroll, content
cut off, images not loading, blurry photos, tiny text, small tap targets, one-word heading lines, script errors) and
saves screenshots to `<project>/qa/final-mobile/`. Fix every FIX line and run it again until none are left, then look
at the 390 screenshots against the "Mobile (Final Mobile Check)" rules in `_mlp-toolkit/qa_feedback.md` and fix what
fails. Progress step "Final mobile check". The revision note says "Final mobile check: passed (390/375/430) ...".
The upload pack (production.py pack) says to post the update on the Final Mobile Check subitem too when the newest
revision came from it.
**Final Mobile Check revisions are shown on their own (user, 2026-11-16: "if there is a revision for final mobile check
include it on the MLP tracker so that I can see it"):** web app row label "Final Mobile Check" (red, open) or "Post on
Final Mobile Check too" (amber, fixed but not posted), a "Mobile revisions" tile + tab, a banner with QA's phone points in
the page panel, revision sections marked "Phone view", and their own pop-up "QA asked for a Final Mobile Check revision"
(also when the page already had a Final MLP revision open). Read from the engine's Revisions lines (index.html mobileRev).
Same day ("What if we just remove the need revision and put Final MLP revision and Mobile revision?"): the web app no
longer shows monday's "Needs Revision" - the monday column shows "Final MLP revision" and/or "Mobile revision" (or "City
page revision") for the current round, red while Claude still has to fix it, grey once fixed and waiting to be posted.
Tabs "Final MLP revision" (#revision) + "Mobile revision" (#mobile) replace "Needs Revision"; tile "Mobile revision".
monday itself is unchanged (still Needs Revision there; the status override list keeps it).
**Posting made easier (user, 2026-11-16):** Ready to post is split into revisions (first) and new pages, sorted by due
date (dealer with the soonest page first); each row has NEW / REVISION #N and the post card says "Post on: ...".
"Preview" (post card + page panel) opens the page's preview.html in the default browser ("Post one by one" was tried and
removed the same day - user: "lets remove that"). When the revision note in to-post/3-post-on-monday.txt has both a "Final MLP" and a "Final Mobile Check"
heading line, the card shows one copy button per subitem (features.split_note) - keep writing those two headings.
qa_sweep.js (390/1024) and final_mobile_check.js flag a short phrase split at "&" ("Build &" / "Price") as FIX.
**Removed from the web app on purpose (user, 2026-11-16 - do not add back without asking):** Next Up "#" column (Claude
orders the queue itself), image batch ticks, all tiles except Overdue (shown only when something is late), "Run QA check
on all" (the auto QA loop does it), tabs "Waiting on you" / "Claude to fix" / "Assigned" (status tab; the 2026-11-18 Assigned side tab is a different, requested view), the panel's "Copy review note" +
note block (same text as the card's Copy note), VS Code and "Mark all posted" on dealer rows (VS Code stays in the page
panel), "Post one by one", the monday status pencil (status changes only on monday; /api/edit refuses "status"). "Since your last shift" is one line with Show / Got it. Kept on purpose: QA report, Calendar,
Activity, Preview, Mark as posted (review after a week of use).
**Your Next Step / to-upload.txt (user, 2026-11-13):** when a build or revision is done, write `to-upload.txt` in the
project folder (one new image file name per line; empty with a # comment when there are none). The tracker's "Your Next
Step" column and the summary's "Waiting on you" use it.

**Automation state + queue (user, 2026-11-12):** on "stop" run `python build_mlp_tracker.py --automation Stopped`, on
"start" run `--automation Running` (red/green banner on Overview, logged in History). The MLPs sheet "Next Up" column is
Claude's work order (Now = building, then revisions, then new Assigned MLPs); the user may type numbers there to reorder,
and they are kept. `--queue "<id>,<id>,..."` sets the order. On "start", work the queue top-down. Set `refreshed_at`
("YYYY-MM-DD HH:MM") in mlp_data.json on every refresh. 

Rules: monday.com is **read-only**. Never create, update, or delete anything in monday.

## Steps for Claude

1. Get the subitem board IDs in the Main workspace (4849162):
   `{ boards(workspace_ids:[4849162], limit:500) { id name } }`. Keep the boards named `Subitems of ...`
   (skip Admin/Content/SEO/Account Management/Dealer Login/GA4/Looker/Mailing/SEO Implementation/
   November Report/DL Board Template). New dealer boards appear here automatically.
2. Query them in batches of ~60 with `all_api_read`:
   ```graphql
   query($ids:[ID!]) { boards(ids:$ids, limit:100) { id items_page(limit:200, query_params:{rules:[
     {column_id:"person", compare_value:["person-<your monday ID>"], operator:any_of},
     {column_id:"name", compare_value:["Final MLP"], operator:contains_text}]}) {
     items { id parent_item { id name board { id name } }
       column_values(ids:["status","date0","date_mkyp4bky","link_mkypndq6"]) { id text } } } } }
   ```
   Columns: `status` = Status, `date0` = Date Assigned, `date_mkyp4bky` = Due Date, `link_mkypndq6` = Link.
2b. Revisions (user, 2026-11-12: revisions on the **Final MLP** and **Final Mobile Check** subitems assigned to
   the owner). For the parent items of the kept Final MLPs, read their subitems and comments (read-only):
   ```graphql
   { items(ids:[<parent item ids>]) { id subitems { id name column_values(ids:["status","person"]) { id text }
       updates(limit:15) { id created_at creator { id name } text_body assets { id name public_url }
         replies { id created_at creator { id name } text_body } } } } }
   ```
   - Interactive refresh: save the result to a file and run `python make_updates_raw.py <file>`.
   - Headless refresh (no shell): write `updates_raw.json` yourself in this shape, one entry per Final MLP:
     `{"<Final MLP subitem id>": {"Final MLP": {"status": "...", "updates": [...]}, "Final Mobile Check": {"status": "...", "updates": [...]}}}`
     Include "Final Mobile Check" only when the owner is in its person column. Each update keeps (assets with public_url, needed to download the screenshots)
     `id, created_at, creator{id,name}, text_body, assets, replies[{id, created_at, creator, text_body}]`; to keep the
     file small, keep only the owner's latest post and everything posted after it (text_body cut to 1500 characters).
   `build_mlp_tracker.py` then flags a revision when a non-owner comments after the owner's latest post on either
   subitem, or a subitem's status is `Needs Revision`: Revisions column + History, Claude Status -> "Revision needed".
3. Drop items whose Status is `Approved` - EXCEPT an MLP whose Final MLP is Approved while its **Final Mobile Check**
   (owner in its person column) is `Needs Revision` (user, 2026-11-16: the 2026 Buick Envision mobile revision was missing
   because the Final MLP was approved). Keep it with `status` = the Final Mobile Check status, `"mobile_only": true`,
   `"final_mlp_status": "Approved"`, `"fmc_subitem_id"`, and keep it (not in "approved") while that subitem is not Approved.
   **Rule (user, 2026-11-16): an MLP is Approved only when BOTH the Final MLP and the Final Mobile Check are Approved** -
   any other Final Mobile Check status (Needs Revision, Waiting for Review, Working on it, blank...) keeps the page open.
   An MLP with no Final Mobile Check assigned to the owner follows the Final MLP alone. If a page comes back after being
   removed, the engine rewords its old "Removed from tracker" History line so it is not counted as an approval.
   refresh_monday.py does this from the same subitem query; the engine restores its notes from removed_items.json
   (every page that leaves the tracker is archived there) and only reads its Final Mobile Check comments.
   Original rule: drop items whose Status is `Approved`. Rewrite `mlp_data.json` (same shape): `checked_at` = today,
   one entry per item: `subitem_id`, `dealer` (parent board name), `board_id` (parent board id),
   `item_id` (parent item id), `mlp` (parent item name), `status`, `assigned`, `due`,
   `live_url` (the URL part after " - " in the Link text, or the whole text if it is just a URL).
3b. Only when needed (user, 2026-11-12): skip this step unless an MLP's dealer is missing from `cms_directory.json`
   (its Platform shows "? (not in monday CMS list)") or the user asks. Then refresh the CMS list (read-only): query board 18392876953 ("Dealer Login and Setup") with
   `{ boards(ids:[18392876953]) { items_page(limit:500) { items { name column_values(ids:["link_mkzsam3e"]) { text } } } } }`
   The CMS name is the text before " - " in the CMS column (e.g. "DealerOn - https://cms.dealeron.com/" -> "DealerOn").
   Rewrite `cms_directory.json` as {"source": ..., "checked_at": today, "cms": {"<dealer name>": "<CMS>"}} (skip blank CMS).
   The Platform column matches MLP dealers to these names (Dealer Inspire = 3 CMS fields, anything else = 1 file).
4. Run `python build_mlp_tracker.py` in this folder. If the workbook is open in Excel the save fails;
   tell the user to close it and retry.
   Batch tracker changes: every run saves, closes and reopens the workbook in the user's Excel, so make the edits first
   and run the build once at the end (2026-11-13: a burst of ~15 runs left a blank Excel window).
   Notes, Project Folder, Questions and Claude's statuses ("Claude working on it" / "Claude is done")
   are kept automatically. Platform comes from `cms_directory.json` (step 3b; "?" = dealer not in that list yet).
   Other commands: `--set <id> "<status>"` ("Claude working on it" stamps Claude Started, "Claude is done"
   stamps Claude Finished, both logged in History with date and time), `--folder <id> "<path>"`,
   `--ask <id> "<question>"`, `--answer <id> "<user answer>"`, `--set-questions` / `--clear-questions <id>`, `--started` / `--finished <id> "YYYY-MM-DD[ HH:MM]"`.
   Workbook sheets: Overview (counts, colour guide, how to use), MLPs, Summary (what we finished each day, newest
   first: Claude's finished builds/revisions from History + every work_log.md line), History (newest first).
4b. (Live page checks were switched off on 2026-11-13; live_check_all.py and the Live Check column are gone.)
4c. Clean up approved projects (user, 2026-11-12: "once the page or website is approve delete all the files under that
   project that is not needed but left the files that is important"). In `project_folders.json` (monday Final MLP ->
   project folder), set each entry's `status` to its monday status from step 2 (the query also returns Approved items);
   add an entry whenever a new project folder is started. Then run `python cleanup_approved.py --delete`: for every
   Approved, not yet `cleaned` project it keeps preview.html, cms-fields/, the uploaded images (assets/webp/), 
   ready-for-review.txt, project.json, brief.*; copies page images found only in working folders into assets/webp first;
   copies the project's own scripts to `<toolkit>\from-projects\<dealer> - <mlp>\`; deletes the rest
   (qa/, tools/, figma/, working images). A project with page images it can't find is skipped and reported.
5. Report: rows now, what was added, what was removed (Approved), status changes (Activity tab, full history), and any cleanup.

**monday connector health (2026-11-13):** when a monday connector call (mcp__claude_ai_monday_com__*) fails, run
`python monday_health.py connector error "<short error>"`; after one works again, `python monday_health.py connector ok`.
The header chip "monday · token · connector" shows it (token side comes from the auto-update watcher).

**Dealer lessons + team rules (2026-11-14):** before every Start / Fix it now run the tracker writes
`webapp/dealer_lessons.md` (per dealer, the QA lessons that came back most); check the page's dealer section before marking
it done and write "Dealer lessons checked" in the note. When `_mlp-toolkit/qa_feedback.md` changes, `sync_team_rules.py`
copies new lessons into the team copy (`MLP Automation/qa_feedback.md`, adds only, backup first).

## Assigned tab (2026-11-18)
- Side icon "Assigned" (next to Approved), asked for by the user on 2026-11-18: "add a tab for assigned projects even the
  projects that is not done yet or claude is not working for it yet". It is NOT the status tab "Assigned" removed on 2026-11-16:
  this one lists EVERY monday subitem assigned to the owner, one row per project (parent item), not only the Final MLP /
  city page rows the tracker works on: Final MLP, Final Mobile Check, Metatags & Metadata, SEO Review, Site Live, city pages.
- Data: refresh_monday.py save_assigned() writes webapp/assigned.json from the same query as the full refresh (no extra
  monday call), so it is as fresh as the last full refresh (every 30 min in the shift, or right away when monday changes).
  /api/assigned adds each tracker row's Claude state (tag "Claude: ..." opens the page panel; "not a Claude task" otherwise).
- Open projects (any subitem not Approved, blank status counts as open) are grouped by dealer, soonest due first; each open
  subitem is a chip with its monday status colour + due date (red = late); approved subitems are one "✓ n approved" note;
  11+ city pages fold to one chip per status. Projects with every subitem approved are folded under "Done". Search works here.

## Blogs tab (2026-11-17)
- Rule 2026-11-19 (user): a blog in **For SEO Review** can be published like **For Web Posting** - your turn, Build it, pop-up;
  the chip still says "For SEO Review" (user: "it must still show SEO review but can be publish") with a green
  "can publish" tag. Set in blog_dealers.json "your_turn".
- Rule 2026-11-20 (user): "If they are seo review and already have a live link we dont need to do them they are
  consider done". A For SEO Review blog with a Live URL on monday is done: not your turn, no pop-up, listed under
  "Published / done", grey "done · live" tag instead of "can publish". Code: blogs.is_done (webapp/blogs.py).
- Side icon "Blogs" (next to Approved). Lists the blog folders in D:\WORK FOLDER\Blogs under the 20 dealerships assigned
  for blogs, numbered as in the assignment list. Buttons per blog: Preview (preview.html), Copy HTML (cms.html), Folder.
- Dealer list: blog_dealers.json (name, website domains, aliases). A blog goes to the dealer whose website its cms.html
  links most; dealers without a known domain match by name. Dealers with no blogs sit on one "No blogs yet" line;
  blogs for dealers not on the list are folded under "Other dealers' blogs".
- Code: webapp/blogs.py (read-only), /api/blogs, /api/blog-html, /api/blog-open. Team package ships blogs.py with an
  empty blog_dealers.json (each person fills their own).
- monday links (2026-11-17): each blog has a yellow "monday" button that opens its subitem on the dealer's blog board in
  the Content Team Workspace (monday_workspace in blog_dealers.json), and shows its monday status and publication date.
  Each dealer card has "monday ↗" for the dealer's blog board (names in "No blogs yet" link there too). Read-only,
  cached in webapp/blog_monday.json for 30 min; Refresh on the tab reads monday again. A dealer whose monday board
  name differs from the list name needs an alias in blog_dealers.json.

## Simpler look (2026-11-17, user: "Can you make it simple some of the content are overwhelming. And for the SEO simplify it
## also but dont remove a feature") - nothing removed, only folded or merged:
- Dealers with one page in a stage: no separate dealer row; the dealer name sits small above the page name (still opens
  the dealer card). Dealers with 2+ pages keep their header row (big batches still fold).
- Ready-to-post card: Copy HTML / CSS / JS, Preview, Upload pack, Mark as posted stay visible; Copy meta description /
  meta title / page URL / monday note fold under "More: meta, page URL, monday note".
- monday status colours: "Color key" toggle above the list (was always open).
- Header monday chip: one dot (worst of token/connector) + "OK"/"needs a look" + last check time; details on hover.
- Now & Next: one quiet line when Claude is idle and the queue is empty.
- SEO tab: "Mark reviewed" is back (it was dropped in the calm version): on a fix card it moves the page to Done as
  "reviewed by you" with Undo, until the problems change (signature of the problem list in webapp/seo_reviewed.json).
  City pages of one dealer that need a fix share one card with "Auto-fix N on M pages" + "Mark all N reviewed".
- seo_fix.py notes no longer start with a doubled date.

## Now & Next card (2026-11-17)
- User: "put a section where it will show what you are working on and whats next". Card at the top of the All tab
  (#nownext, hidden on other tabs), refreshed by every 4-second poll.
- NOW: the Start/Fix run's page + step chips (progress.py steps: Picked up, Reading QA / brief, Building or Fixing
  revision, SEO auto-fix, QA check, Final mobile check, Before/after, Upload pack, Done; done = green, current = blue),
  run time; and Claude's VS Code task from session_progress.py (or "Just finished ..." for 10 min).
- NEXT: the VS Code task's planned steps (session_progress.py ... --next "a | b | c"; a later call for the same task
  keeps them, minus the step now running) and Claude's queue in work order: revisions first, then new pages / city
  pages; "Next Up" numbers, then due date (first 4, "+N more"). Click a page to open it. Empty queue shows a tick.
- Code: index.html showNowNext / claudeQueue / RUN_STEPS. No new API (uses /api/version job + session).

## SEO review tab (2026-11-17)
- **QA's SEO revisions section (same day, user: "the revision part is not showing why is that?")** - visible card under
  the status line: every SEO point QA sent, newest revision first, chip Done ✓ / Not done / Check by hand; city pages with
  the same points are one block ("11/11 done"). Why it was missing before: (1) city comments that only say "apply the same
  revision from the Auburn, AL page" had no points - now they take that page's points, checked with the city name/slug as a
  wildcard; (2) revisions stored in mlp_tracker/revisions/<subitem id> were not read - now both places are; (3) only SEO
  keywords counted - now a quoted value that is/belongs in a heading, URL or meta title counts too ("change this section to
  "..."" = H2 change); (4) done pages showed QA only as a hover badge. Build briefs are skipped. Code: features._rev_dirs /
  _seo_qa / _seo_point / _quote_rx; index.html seoRevs.
- **Calm version (same day, user: "I want to see if there are seo that needs revision can you make it look that it is not
  too overwhelming?")** - replaces the per-page lists and the manual "Mark SEO reviewed" buttons below. Covers every
  tracker page with files (not only revised ones). Each page gets an automatic status: **fix** (a red item from the check,
  or QA's SEO request whose quoted value - URL, heading, title - is not in the page files yet), **working** (QA sent an SEO
  point and Claude has not finished the revision), **done**. Top line: "N pages need an SEO fix" or "No SEO fixes needed ✓";
  icon badge = pages needing a fix. Fix pages = one card with short problems (full text on hover), Auto-fix button, "What's
  on the page" fold (meta, URL, headings, tips). Done pages fold into one line; city pages of a dealer are one row; "QA's
  SEO request done ✓" when the quoted value was found. Amber items are "tips", never a revision. Code: features.seo_review
  / _qa_point_done / _page_text; index.html seoView. seo_reviewed.json + /api/seo-mark are no longer used by the page.
  ALL-CAPS check now skips words followed by ®/™ (brand marks such as X-MODE®).
- User: "add a tab for SEO review when there is a revision about the page". Side icon "SEO review" (magnifier, between
  Blogs and QA report); its count = revised pages not yet marked reviewed.
- Lists every tracker page with a revisions folder (or monday status Needs Revision). Per page: QA's points that touch SEO
  (blue "QA #n", keywords in features.SEO_KEYS) + an automatic check of the current paste files (to-post/2-paste-into-cms,
  else cms-fields, else preview.html): meta title (~60) and description (~160) length, page URL format, one H1, heading
  level jumps, ALL-CAPS heading text, glued words, images without alt, empty/vague link text. One line per problem type
  (red Fix / amber Check). "Meta and headings" folds out the title, description, URL and heading outline.
- City pages of one dealer fold into one card with "Mark all N reviewed". "Mark SEO reviewed" stores the latest revision
  folder name in webapp/seo_reviewed.json (backed up daily); a new revision brings the page back. Reviewed pages sit folded
  at the bottom with Undo.
- Code: features.seo_check / seo_review / seo_mark, /api/seo-review, /api/seo-mark. The caps/camel allowlists mirror
  qa_sweep.js - add a brand word in both places if it shows as a false Fix.
- SEO auto-fix (2026-11-17, user: "every SEO revision that can be edited in HTML like the H1 revision. Can you fix those
  through automation?"): seo_fix.py "<folder>" [--dry] [--sid N]. Fixes only what keeps the look: fully ALL-CAPS headings
  -> Title Case + class seo-uc (rule `#id#id .seo-uc{text-transform:uppercase!important}` added to every <style>/.css),
  missing space where heading parts meet, missing alt (= nearest heading above). Edits preview.html, top-level .html,
  cms-fields/ and to-post/2-paste-into-cms/ the same way; originals in qa/seo-fix-<time>/. Look check: seo_heading_snap.js
  renders before/after at 1920/390 - every heading must read and measure the same (spaces aside), else that heading is
  left alone. --sid writes a Claude's Notes line. Runs in every Start/Fix run (prompt step before the QA sweep); the SEO
  tab shows "Auto-fix N" per page / city batch (/api/seo-fix, refused while a Claude run is going).
  Not automatic (copy/design calls, stay as Check): meta lengths, vague link text, heading level jumps, several H1s,
  headings only partly in caps, QA's URL changes. Tested on copies of GMC Terrain (36 fixes) and RAM 1500 (48): pixel-
  identical at 1920/390; a second run finds nothing.

## Name (2026-11-17)
- The web app is called **Web Dev Tracker** (was MLP Tracker): page title, header, logo "WD", pop-ups, desktop shortcut.
  Kept on purpose: the task "MLP Tracker keep-alive", the %APPDATA%\MLP Tracker folder (monday token), file and folder names.
- Blogs tab v2 (2026-11-17, user: "do the fixes and enhancement" + "put all the blogs ... where the list of the dealership under me"):
  every one of the 20 dealer cards lists ALL its monday blogs: Your turn, Built (folder in the Blogs folder),
  Coming up (not Published; first 4, rest folded), Published (folded). Status chips coloured (BSC in index.html),
  "late" in red when the publication date passed and it is not Published, Doc (Google Doc) and Live links,
  "not found on monday" / "no live URL" flags, Check button (blogs.check_blog: H1, blank lines, placeholders,
  writer notes, local image paths, alt text, images load, links, bold, Also Read/Read Next bold, Mercedes FWB strong).
  Blogs icon count = your-turn blogs; "Your turn:" line jumps to the dealer card; your-turn blogs show on the Calendar.
  Decided: "For Web Posting" = your turn (the web posting step); change with "your_turn": [...] in blog_dealers.json.
  The doubled Audi Q3 folder name was renamed (its Claude memory copied to the new folder key).
- Tabs (2026-11-17, user: "what happened to the tabs here? Like the revision MLP?"): every main tab always shows
  (Ready to post, Final MLP revision, Mobile revision...). Empty ones are dimmed with 0 (class "zero"; ".empty" is the
  empty-table box - do not reuse it). Before this they hid when empty, which looked like they were gone.
- Blogs tab v3 (2026-11-17, user: "galaxy posting is not mine go ahead for your picks"):
  1) Pop-up when a blog reaches "For Web Posting" (blogs.watch_loop, every 10 min inside the shift window, same
     on/off as the monday watcher; blog_seen.json remembers what was already your turn). Click opens #blogs=<card>.
  2) "Build it" on your-turn blogs with no folder: Claude job action "blog" (blogs.build_prompt): .docx bold runs,
     images to images/original + images/webp, preview.html + cms.html, then `python -I webapp/blogs.py check "<folder>"`.
  3) "late" only on your-turn blogs; Coming up shows the next 2 weeks, later ones folded.
  4) Filter buttons Your turn / Built / All (remembered in the browser).
  Confirmed by the user: only "For Web Posting" is theirs ("galaxy posting is not mine").
- Tabs v2 (2026-11-17, user approved the idea): Ready to post / Final MLP revision / Mobile revision fold away when
  empty, replaced by one green note "nothing to post or fix ✓" (hover lists them, click shows/hides them). A tab that
  comes back gets a red NEW tag + pulse until you open it (counts remembered in the browser: localStorage.tseen).
  All / City Pages / Waiting for Review and the side icons never hide. Blogs: "Your turn" filter hides at 0 and shows
  "No blogs waiting on you ✓".

## Open in Claude Code (2026-11-19)
The faint >_ icon on every page row / dealer row, and the "Open in Claude Code" button in the page panel and dealer
card: server.py claude_open() opens the page's folder (dealer folder for a dealer) in VS Code, then the page opens
vscode://anthropic.claude-code/open?prompt=... so a Claude Code chat starts in that window with one short line
typed in: "<Dealer> – <Page>. Task: " (no Enter). The rest (tracker path, QA rules, where the page's status / notes /
QA comment are) is in CLAUDE.md in D:\WORK FOLDER\MLP and <City pages folder (Settings tab)>, which Claude reads by itself. Images paste / drop there as usual.
This replaced the in-page terminal panel built the same day (user chose "A"); terminal.py, webapp/vendor and pywinpty
are no longer used. The MLP / City / toolkit folders stay marked trusted in ~/.claude.json (backup
~/.claude.json.before-tracker-trust).

## Start now (2026-11-19)
User: "add a start now button for the projects that are pending". Pending = Claude "Not started" and monday Assigned /
Working on it. A green "Start now" button sits in the row's "Your next step" cell and in the page panel. It runs the
server action "build" (server.py build_prompt): Claude builds ONLY that page like a page from the Start queue (brief,
content doc, Figma, city pages cloned from the dealer's latest approved city, SEO fix, QA sweep, Final mobile check,
dealer lessons, upload pack, note, Claude is done), then stops. One Claude job at a time: while Start / Fix / another
build runs, the button only says so. Pop-up + header label "Start now run" like Fix it now.

## Claude usage chip + My build memory (2026-11-19)
- **Claude usage chip** (header, "Claude 52% · week 18%"): % of the 5-hour and weekly plan limits, same numbers as
  /usage. Sources: Claude Code's status line (claude_usage_statusline.py, set in ~/.claude/settings.json statusLine -
  the terminal Claude Code runs it, the VS Code extension does not) and every tracker Claude run's `rate_limit_event`
  (features.save_claude_usage). File: plat.app_dir()/claude_usage.json. Orange >= 70 %, red >= 90 %; Start / Fix it now /
  Start now ask first at >= 90 %. Team setup adds the status line only when the person has none.
- **My build memory** (Settings tab, webapp/buildmemory.py): teammates link their OWN Claude memory (personal memory,
  project memories, commands, skills; claude.ai memory by paste) -> `MLP Automation/my build rules/MY CLAUDE MEMORY.md`
  (links, not copies). Team CLAUDE.md + the MLP / CITY PAGES CLAUDE.md (setup writes them when missing) make every run and
  "Open in Claude Code" chat read it; new QA lessons are added back to the linked file that fits. "Check what Claude will
  follow" = small read-only Claude run that sums up the rules.

## UI round (2026-11-19, user: "Go ahead with 1 to 9") - folded, nothing removed
1 header badge = what is happening now (CLAUDE WORKING / REFRESHING / IDLE); a finished Start run sets the automation
Stopped (server job_state). 2 usage/update chips sit inside the button group so the monday chip never drops off.
3 ready-to-post card = one line + "Copy · Preview · Upload pack" fold (rows ~200 -> 100 px, page 3.8k -> 2.3k px).
4 toolbar icons with a count keep their label (Approved / Assigned / Blogs / SEO review); on 1001-1700 px screens the
search shows as its icon and opens over the toolbar (one row at 1366-1920). 5 Claude's notes = entries per date, newest
first, "Decided" / "Revision done" / "BLOCKER" / QA results marked, older folded (notesHtml). 6 page panel = one main
action (Fix it now / Start now / Open upload pack + Mark as posted) + a row of small links. 7 phone header one compact
row (82 px, icon Start/Stop), tabs fade at the edge. 8 phone: Now box one line ("tap for more"), Since-last-shift one
line. 9 calmer row padding, even button heights. Styles: the "UI round 2026-11-19" block at the end of index.html.

## Header Refresh button (2026-11-20, user: "there are parts that the MLP tracker is not updated")
- `Refresh` (header, before Start) -> POST /api/check-now {"full": true} -> watch.json force = "full" -> the watcher runs a
  FULL refresh (refresh_monday.py) even when the quick signature check sees no change, any time of day. Log reason:
  "you pressed Refresh" in webapp/jobs/auto-refresh.log. Costs ~10 monday calls per press.
- Settings > "Check monday now" is unchanged (quick check; full refresh only if something changed).
- The button is disabled and its arrow spins while the watcher is busy; on phones it shows only the icon.
- 2026-11-20: city pages are found by NAME too - a subitem named "Place, ST" (regex `,\s*[A-Z]{2}\b`) counts as a city page
  whatever its parent is called (refresh_monday.to_record). One Legacy Motors' 6 pages sat under "Month 3-4 - We Buy Page
  [NOV-DEC]" and were skipped because only parents named "City Pages" counted.

## Never silent / connector chip / batch city pages (2026-11-20, user: "go ahead with 1, 2 and 3")
1. **Couldn't place**: refresh_monday.save_unplaced() writes webapp/unplaced.json = every subitem assigned to the owner
   that is not a tracker page, not a side task (SIDE_TASKS: Final MLP, Final Mobile Check, Metatags & Metadata, SEO
   Review, Site Live) and not Approved. All tab shows one amber fold "N assigned tasks ... couldn't place"; "Got it"
   hides those ids (localStorage). If a new kind of page shows up there, teach to_record() about it.
2. **Connector chip**: a connector error counts for 24 h; older errors show green with "last error <date>, none since"
   on hover (the Nov 13 error kept the chip red for a week). Claude still records errors with monday_health.py.
3. **Batch city pages** (webapp/batch.py, batches.json): dealer row shows
   - "Build N as a batch" (>=2 not-started city pages under one monday parent, none built) -> action "batch" (sid =
     parent item id) = build_prompt(first page) + write batch_from_sample.py in the dealer's city-pages folder, then stop.
   - "Copy <built page> to the other N" (a page of the group is "Claude is done" and others are not started) ->
     action "batch-copy" = each remaining page from the sample with its own content doc (writes batch_from_sample.py
     first if missing), SEO fix, QA sweep, Final mobile check, pack, note "Copied from the sample ... (batch)".
   Turns: 80 + 110 per page (max 900). One Claude job at a time, like Start now.

## Dashboard + sidebar menu (2026-11-20, user: "lets put a dashboard for our automation tracker? And fix UI that is pleasing and easy to navigate")
- New first tab **Dashboard** (`tab="dash"`, now the landing view; deep links /#all etc. still work). Code: `dashView()` / `dashChart()` in index.html,
  CSS block "Dashboard + sidebar navigation". Read-only - uses /api/state (items, history, approved, claude_usage) plus /api/qa-report and
  /api/costs (fetched at most every 5 min). Nothing new on the server.
- Shows: 5 numbers (Ready to post, Revisions open, With QA, Overdue or Due in 7 days, Approved this week -> each opens its tab), a per-day chart
  (built/fixed by Claude, QA revision comments, approved; the first tracker day's approval import is left out), Where the pages are (stages),
  Due next (click = page panel), Dealers with open work (click = dealer card), QA this week + Claude this week. Now & Next shows on it too.
  The Overdue tile is hidden on the Dashboard only (it has its own).
- Navigation: >=1180 px the tabs are a labelled left sidebar - search, Dashboard, Work (list tabs + "nothing else to post or fix"), Views
  (Assigned, Approved, Blogs, SEO review), Reports (QA report, Calendar, Activity), Settings. Below 1180 px the old one-row top bar is unchanged
  (Dashboard is its first tab). Nothing was removed. Typing in search on the Dashboard jumps to All.
- How to use: new topic "Dashboard and the menu". Backup of the page before this change: backups/index.before-dashboard-20261120.html

## Spacing check (2026-11-20, user: "lets focus on the thing that will make the job easier and faster" -> fewer QA revisions)
- qa_sweep.js has one new CHECK (amber, not FIX): "not centred beside its photo" at 1920 - text stuck to the top of a taller photo
  (QA Auburn #8 "move this content downward to center it"). Tested: catches it on Auburn's before-fix copy, fixed Auburn clean,
  2 notes on 69 approved/current pages (Escalade, Toyota bZ). Other checks unchanged (old/new output identical on 8 pages).
- Tried and removed: "uneven section gap" - false alarms on ~50 of 70 approved pages. Spacing gaps need Figma numbers (plan step 3).
- Lesson added to _mlp-toolkit/qa_feedback.md (Recurring QA points). Old sweep: backups/qa_sweep.before-spacing-20261120.js.

## Spacing vs Figma (2026-11-20, user: "lets proceed with figma key")
- Settings > Figma connection: the user's own Figma key in %APPDATA%\MLP Tracker\figma_token.txt (settings.figma_token, /api/figma-token,
  /api/figma-token/test). Read-only, no Claude tokens. Figma keys expire - "Figma refused the key" = make a new one.
- _mlp-toolkit/tools/figma_layout.py saves <page>/figma/layout.json (desktop frame >=1000px, phone frame 320-500px if any): every text,
  its box and the space above it. Link from project.json, brief.json, or figma/link.txt (features.save_figma_links copies it from the
  monday update before every QA check and every Claude run - city pages and newer pages have it only there).
- qa_sweep.js fetches layout.json by itself when missing (key saved), then CHECK "spacing vs Figma @1920" (amber): texts found once on
  the page and once in the Figma, gap above off by >= max(16px, 35%). Skipped: dealer vehicle carousel (-car with arrows/dots), sliders,
  galleries, disclaimers, and gaps QA's 20px rhythm made tighter than the Figma.
- Test 2026-11-20: Helms before-fix flagged 10 spots (QA: "follow the design in Figma") / fixed version matches; 38 of 69 pages compared,
  11 approved pages get a note (1-5 spots, real Figma differences QA accepted). 31 pages have no Figma link. City pages use a generic
  sample Figma (Audi Annapolis) so only ~10 spots match there. No phone frames found in any Figma yet.
- Figma key expiry (2026-11-20, user: "if the token is nearly expired give notification to the tracker"): Figma's API does not give
  the expiry, so Settings has "Key expires on" (figma_key.json in %APPDATA%\MLP Tracker; blank = 90 days after saving, shown as a guess).
  features.figma_key_status -> /api/state "figma_key"; amber line (<=7 days) / red (expired, or figma_refused.txt written by
  figma_layout.py --check) on Dashboard + All. features.figma_key_alerts (daily_jobs): one --check per day, one pop-up per step
  (7 days, 1 day, expired, refused; keyed by expiry date in watch.json figma_alerts).
