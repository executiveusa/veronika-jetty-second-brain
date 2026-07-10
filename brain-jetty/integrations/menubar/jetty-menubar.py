#!/usr/bin/env python3
"""Jetty in the Mac menu bar — always one click away.

◉ icon in the top bar: Ask Jetty (types), Morning Briefing, Pulse Check,
Focus Mode toggle, Open the 3D brain. The title shows •n when Agent-Inbox
cards are waiting. Answers arrive as notifications AND in Jetty's voice
(ElevenLabs via the server, falling back to the macOS 'Daniel' voice).

Run:      python3 integrations/menubar/jetty-menubar.py &
Login item: ./integrations/menubar/install-login-item.sh
Needs:    pip3 install --user rumps pyobjc-framework-Cocoa   (already done)
"""
import json
import os
import subprocess
import tempfile
import threading
import urllib.request

import rumps

BASE = os.environ.get("JETTY_URL", "http://localhost:4719")


def post(path, data, timeout=240):
    req = urllib.request.Request(BASE + path, data=json.dumps(data).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def get(path, timeout=10):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return json.load(r)


def notify(title, text):
    try:  # Notification Center via osascript (no Info.plist needed)
        subprocess.run(["osascript", "-e",
                        'display notification {} with title {}'.format(
                            json.dumps(text[:230]), json.dumps(title))],
                       capture_output=True, timeout=5)
    except Exception:
        pass


def speak(text):
    """Prefer the server's ElevenLabs voice; fall back to the macOS butler."""
    def go():
        try:
            req = urllib.request.Request(BASE + "/tts", data=json.dumps({"text": text}).encode(),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                audio = r.read()
            f = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            f.write(audio); f.close()
            subprocess.run(["afplay", f.name], timeout=90)
            os.unlink(f.name)
        except Exception:
            try:
                subprocess.run(["say", "-v", "Daniel", text[:500]], timeout=60)
            except Exception:
                pass
    threading.Thread(target=go, daemon=True).start()


class JettyBar(rumps.App):
    def __init__(self):
        super().__init__("◉", quit_button=rumps.MenuItem("Quit Jetty Bar"))
        self.menu = [
            rumps.MenuItem("Ask Jetty…", callback=self.ask),
            rumps.MenuItem("Morning Briefing", callback=self.briefing),
            rumps.MenuItem("Pulse Check", callback=self.pulse),
            None,
            rumps.MenuItem("Focus Mode", callback=self.focus),
            rumps.MenuItem("Open the Brain", callback=self.open_ui),
            None,
        ]
        self.focused = False
        rumps.Timer(self.poll, 30).start()

    def poll(self, _=None):
        try:
            cards = get("/api/inbox").get("cards", [])
            self.title = f"◉ {len(cards)}" if cards else "◉"
            d = get("/api/dnd")
            self.focused = bool(d.get("focus"))
            self.menu["Focus Mode"].state = self.focused
        except Exception:
            self.title = "◌"          # server down

    def ask(self, _):
        w = rumps.Window(message="What do you need, sir?", title="Ask Jetty",
                         default_text="", ok="Ask", cancel="Cancel", dimensions=(340, 60))
        r = w.run()
        if not r.clicked or not r.text.strip():
            return
        q = r.text.strip()

        def go():
            try:
                d = post("/chat", {"question": q, "session": "menubar"}, timeout=90)
                a = d.get("answer") or d.get("error") or "(no answer)"
            except Exception:
                a = "Jetty is offline, sir — start server.py."
            notify("Jetty", a)
            speak(a)
        threading.Thread(target=go, daemon=True).start()

    def briefing(self, _):
        notify("Jetty", "Assembling your briefing, sir…")

        def go():
            try:
                a = post("/briefing", {}).get("answer", "(no briefing)")
            except Exception:
                a = "Jetty is offline, sir."
            notify("Morning Briefing", a)
            speak(a)
        threading.Thread(target=go, daemon=True).start()

    def pulse(self, _):
        def go():
            try:
                d = post("/pulse", {})
                a = d.get("answer") or d.get("error") or "(nothing)"
            except Exception:
                a = "Jetty is offline, sir."
            notify("Pulse", a)
            speak(a)
        threading.Thread(target=go, daemon=True).start()

    def focus(self, sender):
        self.focused = not self.focused
        sender.state = self.focused
        try:
            post("/dnd", {"focus": self.focused}, timeout=10)
        except Exception:
            pass
        notify("Jetty", "Focus mode on — holding all but the urgent, sir."
               if self.focused else "Focus mode off — back to normal, sir.")

    def open_ui(self, _):
        subprocess.run(["open", BASE])


if __name__ == "__main__":
    JettyBar().run()
