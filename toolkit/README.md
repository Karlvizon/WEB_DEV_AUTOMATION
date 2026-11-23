# MLP toolkit

Shared tools and component library for dealer model landing pages (MLPs).
Rules live in your own build rules (see `my build rules\HOW TO ADD YOUR BUILD MEMORY.md`) and the
`/dealer-page-WP` command; this folder is the code that applies them.

## Start a project

1. Make `D:\WORK FOLDER\<year make model>, <Dealer>\project.json` (copy `project.example.json`):
   - `id` page-unique wrapper id (`hc-2026-blazer`), `prefix` class prefix (`blz`), `name` deliverable file name
   - `platform`: `dealer-inspire` (three CMS fields, needs `cdn` media URL) or `one-file` (any other site: one HTML file)
   - `figma.file` / `figma.frame` (the 1920 page frame) / `figma.groups` (sub-section frames for text-position grouping)
2. `python "<toolkit>/new_project.py" "<project folder>"`
   - copies `tools/` with the tokens filled in, the QA `node_modules`, creates the folders
   - writes a starter `preview.html` = component library CSS/JS inside the wrapper, empty markup
3. Figma: save `figma/meta-<frame>.xml`, `figma/assets.json`, `figma/jobs.json`, `tools/_work/figma/full.png`
4. `python tools/prep_images.py` (cuts each fill to its frame, upscales blurry ones one at a time)
5. Write the markup with the components below; add project-only CSS (crop vars, widths) after the library CSS
6. `python tools/sync_dims.py` then `python tools/split_fields.py` then the QA (see below)

## Before and after the build

- **Pre-flight** (before setting "Claude working on it"): write `brief.json` (Figma, content doc, button links, fonts;
  `figma_ok` / `doc_ok` after opening them with the Figma MCP / Google Drive), then `python tools/preflight.py`.
  Every `QUESTION` line goes to the tracker with `build_mlp_tracker.py --ask`. Writes `qa/preflight.txt`.
- **Review page** (after the QA): `python tools/review.py` writes `review.html` in the project folder: Figma vs
  page (desktop, synced scroll) + mobile 390, deliverables, every link with an on-site check, the tracker's
  Questions / Answers / Revisions, and every QA result.

- **QA feedback list**: read `qa_feedback.md` before every build and revision (past QA comments by topic, brand and
  dealer). Figma still wins: when it breaks a point, log a Question quoting it. Add new points after each revision.
- **Ready-for-review note**: `review.py` also writes `ready-for-review.txt` (for a revision, list the changes in
  `qa/revision_done.txt` first). The user posts it on monday.
- **Live page check** (after publishing): `node tools/qa/livepage.js "<project>" <live url>` -> `qa/live.txt`
  (the tracker runs it for every row with a Live URL via `live_check_all.py`).

## Deliverable by platform

| platform | `split_fields.py` writes |
|---|---|
| dealer-inspire | `cms-fields/<name>.html` (wrapper + font link + `<style>` + markup), `.css`, `.js` |
| one-file | `cms-fields/<name>.html` = the whole wrapper: font link + `<style>` + markup + `<script>`; three-field copies go to `tools/_work/fields/` only for the lint/placement tests |
| one-file, Apollo (`"cms": "Apollo"`) | one file in the Apollo reference structure: `<script>` const css (fonts as @import) + `.main-div` markup + `<script>` page JS and Apollo CMS fixes (`tools/apollo_style.py`, user rule 2026-11-20); images are JPEG (`assets/jpg/`, the pack uploads .jpg) - transparent icons go inline SVG |

## Components (`components/components.css`, `.js`; `reference-page.html` shows every one in use)

Classes use the project prefix `P-`. Desktop sizes are `calc(var(--px) * <figma px>)`; heights via `P-h<N>` / `--h`.

| Block | Markup root | Notes |
|---|---|---|
| Hero | `section.P-hero` > `.P-hero__media` (picture: mobile full file, desktop frame crop) + `.P-hero__tx` (h1 name/loc, price box) | mobile: photo, then panel, then CTA bar |
| CTA bar | `div.P-cta` (+ `P-cta--top` under hero, `P-full` elsewhere) > `.P-cta__row` (+ `--solo`) > `a.P-btn` | all buttons rest navy, hover slate |
| Discover carousel | `section.P-disc` > `.P-disc__bg` (halves `P-ha`/`P-hb`) + head + `.P-car` track with 2 lead + 3 tail static clones + nav | JS `carousel`: drag, swipe, keys, dots |
| Section column | `.P-col` + `P-cg<N>` gap; `.P-b` = 1760 centred block | `--cg` resets to 30 on every `.P-col` |
| Kicker | `.P-kicker > p.P-kicker__t` | navy label + rule |
| Heading | `.P-head` (+ `P-hw<N>` width) > `h2.P-h2` + `p.P-sub` | `.P-wt` makes it white |
| Stats | `.P-stats > .P-st > p.P-st__v + p.P-st__l` | mobile: plain figures with dark rules |
| Picture | `.P-m.P-pic.P-h<N> > img.P-cover` | radius 20; `P-r100` = 100 radius |
| Card grids | `.P-g2` / `.P-g3` / `.P-g4` (+ `P-gg<N>` gap) > `.P-fc` (+ `P-fg<N>`) > `.P-m` + `.P-tx > h3.P-t + p.P-p` | `.P-tx--c` centres text |
| Band (text over photo) | `.P-band` (+ `P-bh500`, `P-ga27` gradient stops, `P-band--ds`) > `.P-band__media > .P-m` + `.P-band__tx > h3.P-bh + p.P-bp`; `P-e-<x>` sets `--edge` | mobile: photo then panel from `--edge` |
| Legend band (right text, angled gradient) | `.P-lg > .P-lg__media + .P-lg__tx` | |
| Grey band | `.P-gb` (full-bleed f3f3f3) > `.P-gb__img` + `.P-gb__in` | 20 gap to neighbours on desktop |
| Engine card | `.P-eng > .P-m + .P-eng__tx` (`.P-es` stat rows) | |
| Storm (photo fading to white, cards over it) | `.P-storm > .P-storm__bg + .P-storm__in` | |
| Photo with side cards | `.P-cold > .P-m + .P-cold__cards > .P-hc` | |
| Split row | `.P-sr > .P-m + .P-sr__tx` | |
| Gallery | `section.P-gal` > `.P-gal__in > .P-gal__row > .P-gal__cell(.P-gw1080)(.P-gal__full every 3rd)` | JS `gallery-zoom`; mobile 2-then-1 |
| Trims | `.P-trims__grid > .P-trims__row > .P-trim > .P-m + .P-trim__tx` | mobile crop loosened so no vehicle is cut |
| MLP content | `section.P-b.P-seo > .P-seo__item > h3.P-seo__q + p.P-seo__a + p.P-seo__p` | same font size for question and body |
| Disclaimers | `section.P-b.P-legal > p` | |

## QA (run one at a time: PC rule)

`node tools/qa/fullshot.js 1920 qa/shots/d1920.png`, `textpos.js`, `python -I tools/qa/pixeldiff.py`,
`sweep.js`, `mobile.js`, `mimg.js` (needs `tools/qa/vehicle-bbox.json`), `zoom.js`, `gaps-desk.js`,
`interact.js`, `cdrag.js`, `cmsplace.js`, `python tools/qa/cmslint.py`, `python tools/upload_check.py`,
`sh tools/qa/matrix.sh`, `python -I tools/qa/report.py` -> `qa/index.html`.

## Keeping it current

After a project adds or fixes a component or a QA script, rebuild the toolkit from it:
`python make_toolkit.py "<project folder>" <id> <prefix> <name>`
