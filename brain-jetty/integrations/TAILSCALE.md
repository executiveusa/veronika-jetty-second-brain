# Jetty everywhere — Tailscale setup (5 minutes, one time)

Tailscale gives every one of your devices a private, encrypted HTTPS path to
Jetty — no open ports, no public exposure. This unlocks the phone PWA,
lock-screen widgets, Shortcuts/Watch access, and remote use from anywhere.
Related: [[jetty-second-brain]], `JETTY-V5-ROADMAP.md`.

## 1. Install + sign in (the only manual part)

1. Download the Mac app: https://tailscale.com/download (or App Store → "Tailscale").
2. Open it, sign in (Google/GitHub/Apple — free personal plan).
3. Install the iPhone app too and sign in with the same account.

## 2. Serve Jetty on your tailnet (private — all your devices, nothing public)

```bash
./integrations/setup-tailscale.sh
```

or by hand:

```bash
tailscale serve --bg 4719        # → https://<your-mac>.<tailnet>.ts.net  = the 3D brain
```

Open that URL on your phone → Add to Home Screen → Jetty is an app in your pocket.

## 3. Funnel ONLY the duplex brain port (public — needed by ElevenLabs Agents)

The live-voice feature needs ElevenLabs' cloud to reach the brain endpoint.
Only port 4722 is safe to expose — it serves a single OpenAI-compatible route
protected by a bearer token (in `jetty-duplex.json`). **Never funnel 4719** —
that's the full assistant with your tools behind it.

```bash
tailscale funnel --bg 4722       # → public https URL for setup_duplex.py --url …
```

(Until Tailscale is installed, the stopgap is a Cloudflare quick tunnel:
`./bin/cloudflared tunnel --url http://localhost:4722` — free, no account,
prints a temporary public URL. Fine for testing; Funnel is the stable home.)
