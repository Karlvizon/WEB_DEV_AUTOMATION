# MLP Automation: start here

This folder gives you the **Web Dev Tracker** (a page in your browser that follows your Final MLP pages on monday) and
lets Claude Code build and revise your assigned pages. Claude only **reads** monday and never changes anything there.

Everything here is yours alone: your own monday account, your own pages, your own tracker. Nothing is shared
with the person who sent you this folder.

## Quick start

1. **Unzip** this folder, e.g. to `D:\WORK FOLDER\MLP Automation`.
2. **Double-click `SETUP.cmd`.** It installs what's missing and opens the tracker.
3. **Sign in** to Claude Code in VS Code with your company Claude account.
4. **Tracker > Settings > monday token:** paste your own monday API token.
5. **Your build rules:** Tracker > Settings > **My build memory** > *Find my Claude memory* > *Save my choice*.

That's it. The tracker now follows your monday pages by itself. Everything below is the detail.

## 1. One-time setup (about 15 minutes)

1. **Unzip** this folder somewhere on your PC, e.g. `D:\WORK FOLDER\MLP Automation`. By default your projects go to
   the `MLP` and `CITY PAGES` folders next to it (you can change that in the tracker's Settings tab).
2. **Double-click `SETUP.cmd`.** It installs whatever is missing by itself (Python and its packages, Node.js, VS Code,
   Claude Code and its VS Code extension - Windows may ask you to allow an install), puts a **Web Dev Tracker** shortcut
   on your desktop, makes the tracker start with Windows, and opens it. If a line says FIX, do what it says and run
   SETUP.cmd again.
3. **Sign in** to Claude Code in VS Code with your company Claude account.
4. **Connect** in claude.ai > Settings > Connectors (same account as Claude Code): **monday.com**, **Figma**, **Google Drive**.
5. In the tracker, open **Settings**:
   - **monday token:** paste your own monday API token (monday: profile picture > Developers > My access tokens).
     It is stored only on your PC. Your name and monday ID fill in by themselves on the first refresh.
   - **Shift:** your working hours (the auto-update, pop-ups and the shift summary follow them).
   - **Folders:** where your MLP and city page projects live.
6. **Your build rules:** this folder doesn't tell Claude *how* to build a page. It uses YOUR build memory. Read
   `my build rules\HOW TO ADD YOUR BUILD MEMORY.md` (2 minutes).

## 2. Daily use

Open the **Web Dev Tracker** shortcut. During your shift it checks monday every few minutes by itself and pops up when
something needs you (QA revision, new page, approval, due date).

- **The list** is grouped by stage: Ready to post, Claude is working on it, Needs you, Not started yet, With QA.
- **Start** = Claude works your queue (revisions first). **Stop** = stops it. **Fix it now** (on a revision) = one page.
- **Ready to post** cards: copy the HTML / CSS / JS and the monday note with one click, tick each image batch as you
  upload it, then **Mark as posted** and set the page to Waiting for Review on monday yourself.
- **QA badge** on each ready page: the QA check runs by itself; "QA clean" means the known QA points pass.
- **Since your last shift** (top of the list): what changed on monday while you were away. **Got it** clears it.
- **QA report** tab: what QA sent back this week, by type and dealer, with a **Copy report** button. It is also made
  for you after your Friday shift (change the day in Settings).
- **Activity** tab: everything that happened, plus the **Shift summary** button.

You can also work in VS Code: open this folder, open Claude Code and type **start**, **stop** or **summary**, or just
ask (e.g. "fix the Canyon revision").

## 3. The QA rules

`toolkit\qa_feedback.md` holds what QA keeps sending back, and how to avoid it. Claude reads it before every build and
revision, and adds every new QA point to it. If you learn something worth sharing with the team, send it to the team lead.

## 4. Getting a newer version

Unzip the new version anywhere (or over your old folder) and **double-click its `SETUP.cmd`**. That's all.
It finds your tracker, updates the program files and keeps everything that is yours: settings, monday token, pages,
notes, history, `my build rules\` and your QA lessons (new team lessons are added to yours, nothing is removed).
The replaced files are saved first in `backups\before-update-<date>`. If you unzipped somewhere else, SETUP tells you
when you can delete that folder. If Claude is working (Start / Fix it now), SETUP asks you to stop it first.
The version you have is in `tracker\VERSION.txt` (older versions don't have this file).
