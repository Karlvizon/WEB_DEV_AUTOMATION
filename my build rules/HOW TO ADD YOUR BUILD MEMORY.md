# How to add your build memory

This automation handles the workflow: it reads monday, keeps your web tracker, runs your queue, and responds to
the web tracker. **How you build a page is up to you.** Claude follows your own build rules (your
"memory"), not someone else's.

When Claude builds or revises an MLP, it reads your rules from **any one** of these places. Pick the one that suits you.

## Option A: your memory is already in Claude (nothing to do)

If you already keep your build rules in your personal Claude memory, i.e. the file
`C:\Users\<you>\.claude\CLAUDE.md` or files it points to, Claude Code loads it automatically in every
folder, this one included. You're done. To check, ask Claude: *"What are my build rules for an MLP?"*

## Option B: put your rule files in this folder

Copy your rule files (`.md` or `.txt`: build standards, CMS format, mobile layout rules, prompt templates)
into this folder, **`my build rules\`**. Claude reads every file here before each build and revision.

Tips:
- Plain text or Markdown, one subject per file (e.g. `desktop.md`, `mobile.md`, `cms-dealer-inspire.md`).
- Write each rule as a clear instruction: *"Every button opens in a new tab."*
- When you get a newer version of the MLP Automation folder, keep this folder .

## Option C: point to where your rules already live

If your rules are somewhere else on your PC (another folder, a prompt file you already use), add one line to a file
in `my build rules\`, e.g. *"My build rules are in D:\WORK FOLDER\My Rules - read every .md file there."*

## Option D: a slash command you already use

If you build with your own command (e.g. `/dealer-page`), put its file in `.claude\commands\` inside this folder,
or keep it in `C:\Users\<you>\.claude\commands\`. Then also add one line to a file in `my build rules\`, e.g.
*"Build every MLP with the /dealer-page command."*

## No rules at all yet?

Claude will still build from the Figma, but it will ask you about your standards first (CMS format, mobile
layout, spacing, image handling). Ask it to save your answers as a file in `my build rules\` so it never asks again.

## Adding a rule later

Just tell Claude in the chat, e.g. *"From now on, mobile buttons are 48px tall. Save that to my build rules."*
It will add the rule to a file in `my build rules\`.
