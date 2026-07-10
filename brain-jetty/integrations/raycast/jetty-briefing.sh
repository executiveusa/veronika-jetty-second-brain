#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Jetty Briefing
# @raycast.mode fullOutput
#
# Optional parameters:
# @raycast.icon ☀️
# @raycast.packageName Jetty
#
# Documentation:
# @raycast.description Morning briefing — calendar, email, tasks, notes
# @raycast.author Zubair Trabzada

curl -s -m 240 -X POST http://localhost:4719/briefing \
  -H 'Content-Type: application/json' -d '{}' \
  | /usr/bin/python3 -c 'import json,sys
try:
    d = json.load(sys.stdin)
    print(d.get("answer") or d.get("error") or "(no briefing)")
except Exception:
    print("Jetty is offline, sir — start server.py first.")'
