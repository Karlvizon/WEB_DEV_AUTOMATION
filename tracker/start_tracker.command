#!/bin/bash
# Web Dev Tracker (Mac): starts the tracker if it is not running yet, then opens it in your browser.
cd "$(dirname "$0")"
if ! curl -s -o /dev/null --max-time 2 http://127.0.0.1:8765/api/version; then
  launchctl kickstart "gui/$(id -u)/com.webdevtracker.server" >/dev/null 2>&1 || (nohup python3 -I webapp/server.py >/dev/null 2>&1 &)
  sleep 3
fi
open http://127.0.0.1:8765
