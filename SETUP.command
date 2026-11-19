#!/bin/bash
# MLP Automation setup (Mac) - one click. New Mac: installs what is missing and sets up the Web Dev Tracker.
# Older version on this Mac: updates it and keeps your settings, pages, notes and QA lessons. Safe to run again.
cd "$(dirname "$0")"
find_py() {
  for c in /opt/homebrew/bin/python3 /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
      command -v "$c"; return
    fi
  done
}
PY="$(find_py)"
if [ -z "$PY" ]; then
  BREW="$(command -v brew || ls /opt/homebrew/bin/brew /usr/local/bin/brew 2>/dev/null | head -1)"
  if [ -n "$BREW" ]; then
    echo "Python 3.10+ is not installed - installing it with Homebrew, this takes a few minutes..."
    "$BREW" install python
    PY="$(find_py)"
  fi
fi
if [ -z "$PY" ]; then
  echo
  echo "Python 3.10 or newer is needed. Install Homebrew from https://brew.sh (one command in Terminal),"
  echo "or Python 3.12 from https://www.python.org/downloads/macos/ - then double-click SETUP.command again."
  read -n 1 -s -r -p "Press any key to close"
  exit 1
fi
"$PY" "tracker/setup_tracker.py"
echo
read -n 1 -s -r -p "Press any key to close"
