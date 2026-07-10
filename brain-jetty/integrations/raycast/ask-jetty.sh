#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Ask Jetty
# @raycast.mode fullOutput
#
# Optional parameters:
# @raycast.icon 🧠
# @raycast.argument1 { "type": "text", "placeholder": "ask anything…" }
# @raycast.packageName Jetty
#
# Documentation:
# @raycast.description Ask your second brain from anywhere (⌥Space → "ask jetty")
# @raycast.author Zubair Trabzada

Q="$1"
[ -z "$Q" ] && echo "Ask me something, sir." && exit 0

BODY=$(printf '%s' "$Q" | /usr/bin/python3 -c 'import json,sys; print(json.dumps({"question": sys.stdin.read(), "session": "raycast"}))')

curl -s -m 60 -X POST http://localhost:4719/chat \
  -H 'Content-Type: application/json' \
  -d "$BODY" \
  | /usr/bin/python3 -c 'import json,sys
try:
    d = json.load(sys.stdin)
    print(d.get("answer") or d.get("error") or "(no answer)")
except Exception:
    print("Jetty is offline, sir — start server.py first.")'
