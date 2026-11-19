"""Windows / Mac differences in one place (user, 2026-11-19: share the tracker with teammates on Mac and Windows, one
zip per system). On Windows every helper does exactly what the tracker did before; the Mac branch is the equivalent.

  app_dir()        where the monday token + tracker pointer live (%APPDATA%\\MLP Tracker / ~/Library/Application Support)
  open_path(p)     open a file or folder like a double-click (os.startfile / `open`)
  group_kwargs()   Popen kwargs so a whole process tree can be stopped later (Mac: own session)
  kill_tree(pid)   stop a process and its children (taskkill /T / killpg)
  exit_code(pid)   None while running, else an exit code - for a process started by an earlier server
  notify(...)      desktop pop-up (toast.ps1 / osascript)
  copy_file_to_clipboard(path)
  vscode(), claude_exe(), background_python()
"""
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
HERE = Path(__file__).resolve().parent
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)          # 0 on Mac: nothing to hide


def app_dir():
    if IS_WIN:
        return Path(os.environ.get("APPDATA", str(Path.home()))) / "MLP Tracker"
    if IS_MAC:
        return Path.home() / "Library" / "Application Support" / "MLP Tracker"
    return Path.home() / ".config" / "mlp-tracker"


def open_path(p):
    p = str(p)
    if IS_WIN:
        os.startfile(p)
    else:
        subprocess.Popen(["open" if IS_MAC else "xdg-open", p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def group_kwargs():
    """Extra Popen arguments for a job we may have to stop with its children (claude -> node -> Edge ...)."""
    return {} if IS_WIN else {"start_new_session": True}


def kill_tree(pid):
    pid = int(pid)
    if IS_WIN:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def exit_code(pid):
    """None while the process runs, else its exit code (0 when unknown)."""
    pid = int(pid)
    if IS_WIN:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return 0
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        if ok and code.value == 259:                 # STILL_ACTIVE
            return None
        return code.value if ok else 0
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return 0
    except PermissionError:
        return None
    try:   # a finished child of this process shows as a zombie until reaped
        done, status = os.waitpid(pid, os.WNOHANG)
        if done:
            return os.waitstatus_to_exitcode(status) if hasattr(os, "waitstatus_to_exitcode") else 0
    except ChildProcessError:
        pass
    return None


def process_name(pid):
    """Program name / tasklist line of a running process ("" when gone) - lower-case."""
    if IS_WIN:
        return subprocess.run(["tasklist", "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"], capture_output=True,
                              text=True, creationflags=NOWIN).stdout.lower()
    r = subprocess.run(["ps", "-p", str(int(pid)), "-o", "command="], capture_output=True, text=True)
    return r.stdout.lower()


def _osa(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def notify(title, body, url, extra=None, toast_ps1=None):
    """Desktop pop-up. Windows: toast.ps1 (click opens the tracker; extra = ["-Action2", ..., "-Url2", ...]).
    Mac: a Notification Center banner (macOS gives script banners no click target - the tracker page is already live)."""
    try:
        if IS_WIN:
            subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(toast_ps1),
                              "-Title", title[:120], "-Body", body[:300], "-Url", url] + (extra or []),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NOWIN)
        elif IS_MAC:
            subprocess.Popen(["osascript", "-e", f"display notification {_osa(body[:300])} with title {_osa('Web Dev Tracker')} "
                              f"subtitle {_osa(title[:120])} sound name {_osa('Glass')}"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def copy_file_to_clipboard(path):
    if IS_WIN:
        subprocess.run(["powershell", "-NoProfile", "-Sta", "-Command",
                        f"Set-Clipboard -Value (Get-Content -LiteralPath '{path}' -Raw -Encoding UTF8)"],
                       capture_output=True, timeout=30, creationflags=NOWIN)
    elif IS_MAC:
        with open(path, "rb") as f:
            subprocess.run(["pbcopy"], stdin=f, capture_output=True, timeout=30)


def vscode():
    found = shutil.which("code")
    if found:
        return found
    if IS_MAC:
        return "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
    return str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Microsoft VS Code" / "bin" / "code.cmd")


def claude_exe():
    return shutil.which("claude") or str(Path.home() / ".local" / "bin" / ("claude.exe" if IS_WIN else "claude"))


def background_python():
    """pythonw on Windows (no console window); the normal python elsewhere."""
    exe = Path(sys.executable)
    if IS_WIN and exe.with_name("pythonw.exe").exists():
        return str(exe.with_name("pythonw.exe"))
    return str(exe)
