"""MLP Automation setup - one click, Windows (SETUP.cmd) and Mac (SETUP.command).
User, 2026-11-19: "Yes. And also what if they have the older version?" and "create a zip for mac user and a zip for
windows user".

New computer: installs what is missing, then sets the tracker up to start by itself and opens it.
    Windows: Python packages (pip), Node.js / VS Code (winget), Claude Code (official installer) + its VS Code
             extension; "Web Dev Tracker" desktop shortcut, Startup shortcut, "MLP Tracker keep-alive" task.
    Mac:     Python packages (pip), Node.js / VS Code / Microsoft Edge (Homebrew), Claude Code (official installer) +
             its VS Code extension; "Web Dev Tracker.command" on the Desktop, a login item (launchd) that starts the
             tracker at login and restarts it if it stops.
Update: if this computer already has the tracker (pointer file tracker_path.txt in %APPDATA%\\MLP Tracker or
    ~/Library/Application Support/MLP Tracker) somewhere else, that copy is UPDATED in place: the old files are backed up
    to <MLP Automation>/backups/before-update-<time>, the new program files are copied over, and the person's own data
    is never replaced:
      - settings / data files ship only in tracker/defaults/ and are created only when missing
      - QA rules ship as toolkit/qa_feedback.team.md; new team lessons are ADDED to their qa_feedback.md
    Unzipping the new version over the old folder is safe for the same reason.
Safe to run again at any time.   --no-system = only the file steps (used to test the package).
This file is written into the team packages by make_team_package.py (edit team_setup_template.py, not the copies).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
HERE = Path(__file__).resolve().parent          # <new package>/tracker
SRC = HERE.parent                               # the folder that was just unzipped
NO_SYSTEM = "--no-system" in sys.argv
if IS_WIN:
    APPDIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "MLP Tracker"
else:
    APPDIR = Path.home() / "Library" / "Application Support" / "MLP Tracker"
POINTER = APPDIR / "tracker_path.txt"
LOCAL = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
BREW = shutil.which("brew") or next((p for p in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew") if Path(p).exists()), None)
LABEL = "com.webdevtracker.server"               # Mac login item
ok = True


def line(good, text, fix=""):
    global ok
    ok &= bool(good)
    print(("  OK    " if good else "  FIX   ") + text + ("" if good else f"\n          -> {fix}"))


def version(root):
    try:
        return (root / "tracker" / "VERSION.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def run(cmd, **kw):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, **kw).returncode == 0
    except OSError:
        return False


# ------------------------------------------------------------------ 1. install what is missing
def winget(pkg_id, name, scope_user=True):
    if not shutil.which("winget"):
        return False
    print(f"  ...   installing {name} (a few minutes - Windows may ask you to allow it)")
    cmd = ["winget", "install", "-e", "--id", pkg_id, "--silent", "--accept-package-agreements", "--accept-source-agreements"]
    return run(cmd + (["--scope", "user"] if scope_user else []))


def brew(args, name):
    if not BREW:
        return False
    print(f"  ...   installing {name} with Homebrew (a few minutes - the Mac may ask for your password)")
    return run([BREW, "install", *args])


def find_node():
    cands = [Path(r"C:\Program Files\nodejs\node.exe")] if IS_WIN else [Path("/opt/homebrew/bin/node"), Path("/usr/local/bin/node")]
    return shutil.which("node") or next((str(p) for p in cands if p.exists()), None)


def find_code():
    if IS_WIN:
        cands = [LOCAL / "Programs" / "Microsoft VS Code" / "bin" / "code.cmd", Path(r"C:\Program Files\Microsoft VS Code\bin\code.cmd")]
    else:
        cands = [Path("/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"),
                 Path.home() / "Applications" / "Visual Studio Code.app" / "Contents" / "Resources" / "app" / "bin" / "code"]
    return shutil.which("code") or next((str(p) for p in cands if p.exists()), None)


def find_claude():
    p = shutil.which("claude") or str(Path.home() / ".local" / "bin" / ("claude.exe" if IS_WIN else "claude"))
    return p if Path(p).exists() else None


def find_edge():
    if IS_WIN:
        cands = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
    else:
        cands = ["/Applications/Microsoft Edge.app", str(Path.home() / "Applications" / "Microsoft Edge.app")]
    return next((p for p in cands if Path(p).exists()), None)


PY_PKGS = (("PIL", "pillow"), ("numpy", "numpy"), ("cv2", "opencv-python"), ("openpyxl", "openpyxl"))


def missing_pkgs():
    out = []
    for mod, pkg in PY_PKGS:
        try:
            __import__(mod)
        except ImportError:
            out.append(pkg)
    return out


def install_programs():
    print("Programs")
    line(sys.version_info >= (3, 10), f"Python {sys.version.split()[0]}",
         "install Python 3.10+ from python.org" + (" (tick 'Add to PATH')" if IS_WIN else ""))
    miss = missing_pkgs()
    if miss:
        print(f"  ...   installing Python packages: {' '.join(miss)}")
        base = [sys.executable, "-m", "pip", "install", "--quiet"]
        if not run(base + miss) and not IS_WIN:   # Homebrew Python refuses plain pip installs (PEP 668)
            run(base + ["--user", "--break-system-packages"] + miss)
    still = missing_pkgs()
    line(not still, "Python packages", f"{'pip' if IS_WIN else 'python3 -m pip'} install {' '.join(still)}")

    if IS_MAC and not BREW:
        print("  FIX   Homebrew is not installed - it installs Node.js, VS Code and Edge for you.\n"
              "          -> install it from https://brew.sh (one command in Terminal), then run SETUP.command again.")

    if not find_node():
        winget("OpenJS.NodeJS.LTS", "Node.js", scope_user=False) if IS_WIN else brew(["node"], "Node.js")
    line(find_node(), "Node.js", "install Node.js LTS from nodejs.org")

    if not find_edge():
        if IS_MAC:
            brew(["--cask", "microsoft-edge"], "Microsoft Edge (the QA checks use it)")
    line(find_edge(), "Microsoft Edge (the QA checks use it)", "install Microsoft Edge from microsoft.com/edge")

    if not find_code():
        winget("Microsoft.VisualStudioCode", "VS Code") if IS_WIN else brew(["--cask", "visual-studio-code"], "VS Code")
    code = find_code()
    line(code, "VS Code", "install VS Code from code.visualstudio.com")

    if not find_claude():
        print("  ...   installing Claude Code")
        if IS_WIN:
            run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "irm https://claude.ai/install.ps1 | iex"])
        else:
            run(["bash", "-c", "curl -fsSL https://claude.ai/install.sh | bash"])
    line(find_claude(), "Claude Code", "install Claude Code: https://code.claude.com (then sign in)")
    if code:
        sh = code.endswith(".cmd")
        has_ext = "anthropic.claude-code" in (subprocess.run([code, "--list-extensions"], capture_output=True, text=True,
                                                             shell=sh).stdout or "").lower()
        if not has_ext:
            print("  ...   adding the Claude Code extension to VS Code")
            run([code, "--install-extension", "anthropic.claude-code"], shell=sh)
            has_ext = True
        line(has_ext, "Claude Code in VS Code", "VS Code > Extensions > search 'Claude Code' > Install")


# ------------------------------------------------------------------ 2. new install or update an older one
def tracker_busy():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/api/job", timeout=2) as r:
            return bool(json.load(r).get("running"))
    except Exception:
        return False


def stop_server():
    """Windows: the keep-alive task starts it again within a minute; Mac: the login item restarts it at once."""
    if IS_WIN:
        run(["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*webapp*server.py*' } | "
             "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"])
    else:
        run(["pkill", "-f", "webapp/server.py"])


def find_old_install():
    try:
        t = Path(POINTER.read_text(encoding="utf-8").strip())
    except OSError:
        return None
    root = t.parent
    if (t / "webapp" / "server.py").exists() and root.resolve() != SRC.resolve():
        return root
    return None


def copy_update(target):
    """Copy the new program files over the old install; back up what gets replaced first."""
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    backup = target / "backups" / f"before-update-{stamp}"
    n = 0
    for f in SRC.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(SRC)
        dst = target / rel
        if dst.exists() and "node_modules" not in rel.parts:
            (backup / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, backup / rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
        n += 1
    return n, backup


def sections(text):
    out, head, cur = [], "", []
    for ln in text.splitlines():
        if ln.startswith("## "):
            out.append((head, cur))
            head, cur = ln.strip(), []
        else:
            cur.append(ln)
    out.append((head, cur))
    return out


def rule_key(ln):
    m = re.match(r"\s*- \*\*(.+?)\*\*", ln)
    return (m.group(1) if m else re.sub(r"\s+", " ", ln.strip("- ").strip())[:60]).lower()


def merge_rules(root):
    """Team QA lessons -> the person's own qa_feedback.md: only ADDS lessons they don't have (never deletes/rewrites)."""
    team, mine = root / "toolkit" / "qa_feedback.team.md", root / "toolkit" / "qa_feedback.md"
    if not team.exists():
        return 0
    if not mine.exists():
        shutil.copy2(team, mine)
        return -1
    text = mine.read_text(encoding="utf-8")
    have = {rule_key(l) for l in text.splitlines() if l.lstrip().startswith("- ")}
    secs, added = sections(text), 0
    for head, lines in sections(team.read_text(encoding="utf-8")):
        new = [l for l in lines if head and l.lstrip().startswith("- ") and not l.startswith("  ") and rule_key(l) not in have]
        if not new:
            continue
        added += len(new)
        hit = next((i for i, (h, _l) in enumerate(secs) if h.lower() == head.lower()), None)
        if hit is None:
            secs.append((head, [""] + new + [""]))
        else:
            body = secs[hit][1]
            last = max([i for i, l in enumerate(body) if l.lstrip().startswith("- ")] or [len(body) - 1])
            body[last + 1:last + 1] = new
    if added:
        shutil.copy2(mine, mine.with_name(f"qa_feedback.before-update-{datetime.now():%Y%m%d-%H%M}.md"))
        out = []
        for head, lines in secs:
            out += ([head] if head else []) + lines
        mine.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    return added


def fill_defaults(root):
    made = []
    for f in (root / "tracker" / "defaults").glob("*"):
        dst = root / "tracker" / f.name
        if not dst.exists():
            shutil.copy2(f, dst)
            made.append(f.name)
    return made


def install_files():
    """Returns the MLP Automation folder the tracker runs from."""
    print("\nTracker files")
    old = find_old_install()
    new_v = version(SRC)
    if old:
        old_v = version(old) or "an older version"
        if version(old) and version(old) > new_v:
            print(f"  OK    Your tracker in {old} is newer ({old_v}) than this folder ({new_v}) - nothing replaced.")
            return old
        if not NO_SYSTEM and tracker_busy():
            print("  FIX   Claude is working in the tracker right now (Start / Fix it now).\n"
                  "          -> press Stop in the tracker or wait until it is done, then run the setup again.")
            sys.exit(1)
        print(f"  ...   updating your tracker in {old} from {old_v} to {new_v}")
        stop_server() if not NO_SYSTEM else None
        n, backup = copy_update(old)
        line(True, f"Updated {n} program files (old ones saved in {backup.relative_to(old)})")
        target = old
    else:
        if not NO_SYSTEM and tracker_busy():
            print("  FIX   Claude is working in the tracker right now - stop it or wait, then run the setup again.")
            sys.exit(1)
        stop_server() if not NO_SYSTEM else None   # an older copy unzipped over this folder may still be running
        target = SRC
        line(True, f"Tracker version {new_v} in {target}")
    made = fill_defaults(target)
    line(True, "Your settings and data kept" + (f" (created: {', '.join(made)})" if made else ""))
    added = merge_rules(target)
    line(True, "QA rules: " + ("team rules copied" if added == -1 else f"{added} new team lesson(s) added to yours"
                               if added else "you already have every team lesson"))
    return target


# ------------------------------------------------------------------ 3. shortcuts, start with the computer, keep running
def win_shortcut(lnk, target, args="", workdir=""):
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');$s.TargetPath='{target}';"
          f"$s.Arguments='{args}';$s.WorkingDirectory='{workdir}';$s.WindowStyle=7;$s.Save()")
    return run(["powershell", "-NoProfile", "-Command", ps])


def system_windows(tr):
    pyw = Path(sys.executable).with_name("pythonw.exe")
    pyw = pyw if pyw.exists() else Path(sys.executable)
    desk = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    start_cmd = tr / "start_tracker.cmd"
    line(win_shortcut(desk / "Web Dev Tracker.lnk", str(start_cmd), "", str(tr)), "Desktop shortcut 'Web Dev Tracker'",
         "make a shortcut to tracker\\start_tracker.cmd yourself")
    startup = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    line(win_shortcut(startup / "MLP Tracker server.lnk", str(pyw), f'-I "{tr / "webapp" / "server.py"}"', str(tr)),
         "Starts with Windows", "optional - skip")
    r = subprocess.run(["schtasks", "/Create", "/F", "/SC", "MINUTE", "/MO", "1", "/TN", "MLP Tracker keep-alive",
                        "/TR", f'"{pyw}" -I "{tr / "keepalive.py"}"'], capture_output=True, text=True)
    line(r.returncode == 0, "Keep-alive task (restarts the tracker if it stops)", "optional - run SETUP.cmd again later")
    subprocess.Popen(["cmd", "/c", str(start_cmd)], cwd=str(tr))


def system_mac(tr):
    # login item: starts the tracker at login and restarts it if it stops (replaces Startup + keep-alive on Windows)
    agents = Path.home() / "Library" / "LaunchAgents"
    agents.mkdir(parents=True, exist_ok=True)
    plist = agents / f"{LABEL}.plist"
    (tr / "webapp" / "jobs").mkdir(parents=True, exist_ok=True)
    path_env = ":".join(dict.fromkeys([str(Path.home() / ".local" / "bin"), "/opt/homebrew/bin", "/usr/local/bin",
                                       "/usr/bin", "/bin", "/usr/sbin", "/sbin"]))
    esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    plist.write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key><array><string>{esc(sys.executable)}</string><string>-I</string><string>{esc(tr / "webapp" / "server.py")}</string></array>
  <key>WorkingDirectory</key><string>{esc(tr)}</string>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>{esc(path_env)}</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>{esc(tr / "webapp" / "jobs" / "server.log")}</string>
  <key>StandardErrorPath</key><string>{esc(tr / "webapp" / "jobs" / "server.log")}</string>
</dict></plist>
''', encoding="utf-8")
    uid = str(os.getuid())
    run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"])
    good = run(["launchctl", "bootstrap", f"gui/{uid}", str(plist)]) or run(["launchctl", "load", "-w", str(plist)])
    line(good, "Starts at login and restarts by itself if it stops", "log out and in again, or run the setup again")
    start = tr / "start_tracker.command"
    desk = Path.home() / "Desktop" / "Web Dev Tracker.command"
    try:
        desk.write_text(f'#!/bin/bash\n# Web Dev Tracker: opens the tracker (starts it first if needed)\nexec "{start}"\n', encoding="utf-8")
        desk.chmod(0o755)
        start.chmod(0o755)
        line(True, "Desktop shortcut 'Web Dev Tracker.command' (double-click it)")
    except OSError:
        line(False, "Desktop shortcut", "double-click tracker/start_tracker.command instead")
    subprocess.Popen(["bash", str(start)], cwd=str(tr))


def usage_status_line(tr):
    """Claude usage chip in the tracker header (2026-11-19): Claude Code's status line saves the plan-usage % for the
    tracker. Added to ~/.claude/settings.json ONLY when the person has no status line of their own."""
    f = Path.home() / ".claude" / "settings.json"
    try:
        cfg = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except ValueError:
        line(False, "Claude usage in the tracker header", "your ~/.claude/settings.json could not be read - skipped")
        return
    if cfg.get("statusLine"):
        line(True, "Claude usage in the tracker header (from your Start / Fix runs; you already have your own status line)")
        return
    script = (tr / "claude_usage_statusline.py").as_posix()
    cfg["statusLine"] = {"type": "command", "command": f'"{Path(sys.executable).as_posix()}" -I "{script}"', "refreshInterval": 60}
    f.parent.mkdir(parents=True, exist_ok=True)
    if f.exists():
        shutil.copy2(f, f.with_name("settings.before-tracker.json"))
    f.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    line(True, "Claude usage in the tracker header (Claude Code status line added)")


PAGES_CLAUDE_MD = """# Pages in this folder are tracked by the Web Dev Tracker

Every page folder under here is a page on the tracker. Chats opened from the tracker's "Open in Claude Code" button
start with one line: "<Dealer> - <Page>. Task: ..." - the details below are where to look it up.

- **Tracker:** `{tracker}` (web app at http://127.0.0.1:8765). How it works: `REFRESH.md` there.
- **My build rules:** read `{rules}/MY CLAUDE MEMORY.md` and every file it links before building or revising a page
  (the person's own Claude memory, chosen on the tracker's Settings tab). QA's rules still apply on top.
- **This page's tracker entry:** in `tracker_state.json` (tracker folder), the item in `items` whose `folder` is the
  folder you are in (dealer folder: all items whose `dealer` matches): `subitem_id`, `status` (monday), `claude`,
  `next_step`, `due`, `notes` (the person's own - never write there), `cnotes` (Claude's notes).
- **Latest QA comment:** the newest folder in `revisions/` in the page folder, or `{tracker}/revisions/<subitem_id>/`.
- **QA rules:** `{toolkit}/qa_feedback.md`; lessons QA keeps sending per dealer: `{tracker}/webapp/dealer_lessons.md`.
- **Write what you did:** `python "{tracker}/build_mlp_tracker.py" --note <subitem_id> "<text>"`.
- **Show progress:** `python "{tracker}/session_progress.py" "<task>" "<step>"`, and `--done "<what was done>"` at the end.
- monday is read-only. No questions about the build - decide by the QA rules, then the Figma. (Mac: `python3`.)
"""


def pages_claude_md(root):
    """CLAUDE.md in the MLP and CITY PAGES folders (only when missing): "Open in Claude Code" chats in a page folder then
    know where the tracker, the QA rules and the person's linked build memory are (2026-11-19)."""
    tr = root / "tracker"
    try:
        sys.path.insert(0, str(tr))
        import settings as st
        folders = [Path(st.get("mlp_root")), Path(st.get("city_root"))]
        toolkit = Path(st.get("toolkit_root"))
    except Exception:
        folders, toolkit = [root.parent / "MLP", root.parent / "CITY PAGES"], root / "toolkit"
    made = 0
    for d in folders:
        f = d / "CLAUDE.md"
        if f.exists():
            continue
        try:
            d.mkdir(parents=True, exist_ok=True)
            f.write_text(PAGES_CLAUDE_MD.format(tracker=tr.as_posix(), rules=(root / "my build rules").as_posix(),
                                                toolkit=toolkit.as_posix()), encoding="utf-8")
            made += 1
        except OSError:
            pass
    line(True, "Project folders know the tracker" + (f" (CLAUDE.md added in {made} folder(s))" if made else ""))


def system_setup(root):
    print("\nShortcuts")
    tr = root / "tracker"
    usage_status_line(tr)
    pages_claude_md(root)
    POINTER.parent.mkdir(parents=True, exist_ok=True)
    POINTER.write_text(str(tr), encoding="utf-8")   # tools copied into project folders find the tracker here
    line((root / "toolkit" / "node_modules" / "playwright-core").exists(), "QA browser driver (toolkit/node_modules)",
         "unzip the whole MLP Automation folder again (node_modules is missing)")
    system_windows(tr) if IS_WIN else system_mac(tr)


if __name__ == "__main__":
    print(f"\nMLP Automation - setup (version {version(SRC) or '?'}, {'Windows' if IS_WIN else 'Mac' if IS_MAC else sys.platform})\n")
    if not NO_SYSTEM:
        install_programs()
    root = install_files()
    if not NO_SYSTEM:
        system_setup(root)
    if root != SRC:
        print(f"\nDone - your tracker in {root} is updated. You can delete the folder you just unzipped:\n  {SRC}")
    print("\n" + ("All set. The tracker is opening in your browser." if ok else "Fix the lines marked FIX, then run the setup again.")
          + "\nFirst time only:"
          + "\n  1. Open Claude Code in VS Code and sign in with your company Claude account."
          + "\n  2. claude.ai > Settings > Connectors: connect monday.com, Figma and Google Drive."
          + "\n  3. Tracker > Settings tab > monday token: paste your own monday API token"
          + "\n     (monday: profile picture > Developers > My access tokens). Your name and ID fill in by themselves."
          + "\n  4. Tracker > Settings tab: check your folders and shift hours.\n")
