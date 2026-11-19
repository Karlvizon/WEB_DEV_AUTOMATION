"""Keep the MLP Tracker web app running (user, 2026-11-13: "1,2,5,6" - 6 = restart it by itself).

Windows Task Scheduler runs this every minute (task "MLP Tracker keep-alive"). It only asks whether the tracker answers
on 127.0.0.1:8765; if it doesn't (crash, after sleep, after an update), it starts webapp/server.py hidden. Takes a few
milliseconds when the tracker is up, so it is light on the PC.
"""
import socket
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def up():
    try:
        with socket.create_connection(("127.0.0.1", 8765), timeout=3):
            return True
    except OSError:
        return False


if not up():
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe") if exe.with_name("pythonw.exe").exists() else exe
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([str(pyw), "-I", str(HERE / "webapp" / "server.py")], cwd=str(HERE), creationflags=flags,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
