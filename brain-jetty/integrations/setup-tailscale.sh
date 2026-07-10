#!/bin/bash
# One-shot Tailscale config for Jetty (run AFTER installing + signing into the Tailscale app).
# - serves the 3D brain (4719) privately on your tailnet
# - funnels ONLY the token-authed duplex brain port (4722) publicly for ElevenLabs
TS="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
command -v tailscale >/dev/null 2>&1 && TS="tailscale"
if ! "$TS" status >/dev/null 2>&1; then
  echo "Tailscale isn't installed or signed in yet — see integrations/TAILSCALE.md step 1."
  exit 1
fi
set -x
"$TS" serve  --bg 4719
"$TS" funnel --bg 4722
set +x
echo
echo "Private brain URL (your devices only):"
"$TS" serve status 2>/dev/null | head -5
echo "Use the public funnel URL for:  python3 setup_duplex.py --url <it>"
