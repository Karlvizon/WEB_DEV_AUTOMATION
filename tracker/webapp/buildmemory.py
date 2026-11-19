"""My build memory (user, 2026-11-19 #6: "they have their own claude memory on how to build the pages so ... think of
something that they can put the memory of their claude into the automation").

The automation runs Claude in the tracker folder, where Claude Code loads only the person's personal CLAUDE.md, commands
and skills - not the project memories it saved in other folders, and never their claude.ai chat memory. This module:
  scan()          lists the Claude memory on this computer (~/.claude: CLAUDE.md, memory/, every projects/*/memory/,
                  commands/, skills/, agents/) with each file's own one-line description; build-related ones pre-ticked
  save(paths)     writes <MLP Automation>/my build rules/MY CLAUDE MEMORY.md = LINKS to the chosen files (not copies, so
                  what their Claude learns later is picked up) - every Start / Fix it now / Start now run and every
                  "Open in Claude Code" chat reads it first (team CLAUDE.md + the MLP / CITY PAGES CLAUDE.md)
  paste(text)     their claude.ai memory -> my build rules/from-claude-ai.md
  check()         asks Claude (read-only, small) to sum up the rules it will follow in about 10 lines
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

APP = Path(__file__).resolve().parent
HERE = APP.parent
sys.path.insert(0, str(HERE))
import plat  # noqa: E402

CLAUDE_HOME = Path.home() / ".claude"
RULES = HERE.parent / "my build rules"
LINKS = RULES / "MY CLAUDE MEMORY.md"
PASTE = RULES / "from-claude-ai.md"
BUILD_WORDS = re.compile(r"\b(mlp|landing page|dealer|figma|cms|wordpress|dealer ?inspire|dealeron|mobile|hero|css|"
                         r"page build|build standard|city page|qa|responsive|webp|trim|disclaimer)\b", re.I)


def _meta(f):
    """(title, description, memory type) from frontmatter name/description/type, else the first heading / line."""
    try:
        s = f.read_text(encoding="utf-8", errors="ignore")[:4000]
    except OSError:
        return f.stem, "", ""
    name = desc = mtype = ""
    m = re.match(r"^---\s*\n(.*?)\n---", s, re.S)
    if m:
        for ln in m.group(1).splitlines():
            if ln.lower().startswith("name:"):
                name = ln.split(":", 1)[1].strip().strip('"')
            elif ln.lower().startswith("description:"):
                desc = ln.split(":", 1)[1].strip().strip('"')
            elif ln.strip().lower().startswith("type:"):
                mtype = ln.split(":", 1)[1].strip().lower()
        body = s[m.end():]
    else:
        body = s
    if not desc:
        first = next((l.strip("# ").strip() for l in body.splitlines() if l.strip() and not l.startswith("---")), "")
        desc = first[:160]
    return name or f.stem, desc, mtype


def _project_label(folder_name):
    """'d--WORK-FOLDER-MLP-Huston-CDJR' -> 'WORK FOLDER MLP Huston CDJR' (Claude's folder key is lossy - for display)."""
    s = re.sub(r"^[a-zA-Z]--", "", folder_name)
    return s.replace("-", " ").strip()


def chosen():
    if not LINKS.exists():
        return set()
    return {m.group(1) for m in re.finditer(r"^- `([^`]+)`", LINKS.read_text(encoding="utf-8"), re.M)}


def scan():
    have = chosen()
    rows = []

    def add(f, kind, where=""):
        title, desc, mtype = _meta(f)
        text = f"{title} {desc}"
        # pre-tick: personal memory / commands / skills about page building, and project memories saved as general
        # feedback or rules - not notes about one project (a Figma link, one page's fonts)
        general = kind != "Project memory" or mtype == "feedback" or title.lower().startswith(("feedback", "rule"))
        try:
            st = f.stat()
        except OSError:
            return
        rows.append({"path": str(f), "kind": kind, "where": where, "title": title, "desc": desc[:200],
                     "kb": round(st.st_size / 1024, 1), "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d"),
                     "suggested": general and bool(BUILD_WORDS.search(text)), "chosen": str(f) in have})

    if (CLAUDE_HOME / "CLAUDE.md").exists():
        add(CLAUDE_HOME / "CLAUDE.md", "Personal CLAUDE.md (already loaded everywhere)")
    for f in sorted((CLAUDE_HOME / "memory").rglob("*.md")) if (CLAUDE_HOME / "memory").is_dir() else []:
        if f.name.upper() not in ("INDEX.MD", "MEMORY.MD"):
            add(f, "Personal memory", str(f.parent.relative_to(CLAUDE_HOME / "memory")).replace(".", "") or "")
    for d in sorted((CLAUDE_HOME / "projects").glob("*/memory")) if (CLAUDE_HOME / "projects").is_dir() else []:
        for f in sorted(d.glob("*.md")):
            if f.name.upper() != "MEMORY.MD":
                add(f, "Project memory", _project_label(d.parent.name))
    for sub, kind in (("commands", "Slash command"), ("agents", "Agent")):
        for f in sorted((CLAUDE_HOME / sub).glob("*.md")) if (CLAUDE_HOME / sub).is_dir() else []:
            add(f, kind)
    for f in sorted((CLAUDE_HOME / "skills").glob("*/SKILL.md")) if (CLAUDE_HOME / "skills").is_dir() else []:
        add(f, "Skill", f.parent.name)
    return {"rows": rows, "linked": len(have), "rules_folder": str(RULES),
            "pasted": PASTE.exists(), "saved_at": datetime.fromtimestamp(LINKS.stat().st_mtime).strftime("%Y-%m-%d %H:%M") if LINKS.exists() else None}


def save(paths):
    home = str(CLAUDE_HOME.resolve()).lower()
    ok = []
    for p in paths or []:
        f = Path(str(p))
        try:
            if str(f.resolve()).lower().startswith(home) and f.is_file() and f.suffix.lower() == ".md":
                ok.append(f)
        except OSError:
            continue
    meta = {r["path"]: r for r in scan()["rows"]}
    RULES.mkdir(parents=True, exist_ok=True)
    lines = ["# My Claude memory - the build rules the automation must follow", "",
             "Made by the tracker (Settings > My build memory). These are LINKS to this person's own Claude memory files.",
             "**Before every build or revision (Start, Fix it now, Start now, or a chat about a page): read every file",
             "listed here.** They are this person's own rules for building pages. QA's rules (toolkit/qa_feedback.md) still",
             "apply on top. When a QA revision teaches a new rule, add it to the file below that fits it best (keep its",
             "format), or to `my build rules/learned.md` if none fits - so their own Claude learns it too.", ""]
    for f in ok:
        r = meta.get(str(f), {})
        lines.append(f"- `{f}` - {r.get('kind', '')}{(' (' + r['where'] + ')') if r.get('where') else ''}: "
                     f"{r.get('title', f.stem)} - {r.get('desc', '')}")
    if PASTE.exists():
        lines.append(f"- `{PASTE}` - claude.ai memory (pasted on the Settings tab)")
    LINKS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ok": True, "msg": f"Saved: the automation now reads {len(ok)} of your memory file(s)" +
            (" + your claude.ai memory" if PASTE.exists() else ""), "file": str(LINKS)}


def paste(text):
    text = (text or "").strip()
    RULES.mkdir(parents=True, exist_ok=True)
    if not text:
        PASTE.unlink(missing_ok=True)
        save(list(chosen()))
        return {"ok": True, "msg": "claude.ai memory removed"}
    PASTE.write_text("# My claude.ai memory (pasted " + datetime.now().strftime("%Y-%m-%d") + ")\n\n" + text + "\n",
                     encoding="utf-8")
    save(list(chosen()))
    return {"ok": True, "msg": "claude.ai memory saved - the automation reads it too"}


def check():
    """Small read-only Claude run: what rules will the automation follow? (~1 minute, a little Claude usage)."""
    if not LINKS.exists() and not any(RULES.glob("*.md")):
        return {"error": "Nothing linked yet - press Find my Claude memory, tick your build files and Save"}
    prompt = ("Read the file 'my build rules/MY CLAUDE MEMORY.md' (one folder above the tracker folder) and EVERY file it "
              "links, plus every other .md / .txt in 'my build rules'. Then sum up, in at most 10 short plain bullet "
              "points, the rules you would follow when building or revising a dealer landing page (layout, mobile, CMS "
              "format, images, QA). Name the file each rule comes from. If the files hold no page-building rules, say so. "
              "Do not change any file.")
    env = {k: v for k, v in os.environ.items()
           if not re.match(r"^(CLAUDECODE|CLAUDE_PID|CLAUDE_EFFORT|CLAUDE_AGENT_SDK_VERSION|CLAUDE_CODE_\w+)$", k)}
    try:
        r = subprocess.run([plat.claude_exe(), "-p", prompt, "--allowedTools", "Read Glob Grep", "--max-turns", "25",
                            "--add-dir", str(CLAUDE_HOME), "--add-dir", str(RULES)],
                           cwd=str(HERE), capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=300, env=env, creationflags=plat.NOWIN)
    except subprocess.TimeoutExpired:
        return {"error": "Claude took too long - try again"}
    except OSError as e:
        return {"error": f"Could not start Claude Code: {e}"}
    out = (r.stdout or "").strip()
    return {"ok": True, "text": out or (r.stderr or "No answer").strip()[-600:]}
