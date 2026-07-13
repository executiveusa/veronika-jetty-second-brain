/**
 * JETTY™ — First-launch onboarding overlay.
 * 5 chapters, non-technical, JETTY voice (per SOUL.md).
 * Premium voice narrates each step. Dismissed permanently via localStorage.
 * Adapts the codebase-to-course skill: turns the app into a guided lesson.
 */
(function () {
  "use strict";

  const ONBOARDED_KEY = "jetty_onboarded";

  const CHAPTERS = [
    {
      title: "Meet Jetty",
      body: "I'm Jetty. Your thinking, coiled. I'm named for the Spiral Jetty out on the Great Salt Lake — a coil of black basalt spiraling into pink water. That's what your notes look like to me. A galaxy of stars, each one an idea, all connected. I'm here to remember what you forget, find what you buried, and help you take the next right step."
    },
    {
      title: "Your galaxy",
      body: "Every star is something you tell me. Right now there's one — the welcome note. Drag to orbit the galaxy. Scroll to zoom. Click a star to see what's inside it. When you tell me something new, a fresh star appears and the camera flies to it. Try saying or typing: \"remember that I'm job-hunting in operations\" — and watch a star be born."
    },
    {
      title: "The voice dock",
      body: "Down at the bottom you'll find the dock. The microphone is push-to-talk — click and speak. The ear button is hands-free: toggle it on, then just say \"Jetty\" and ask your question. The satellite-dish opens a live conversation. The screen-share lets me see what you're looking at and help. The bell gives you a morning briefing. Start with the microphone — it's the easiest."
    },
    {
      title: "Switch brains",
      body: "I run on whichever brain you pick — top-right. Groq is the fastest and it's free. Claude is the sharpest writer. ChatGPT, DeepSeek, Hermes are all there. Switch anytime. The default is Groq because it answers fast and costs nothing — good for everyday. Use Claude when you need your best cover letter or a careful answer."
    },
    {
      title: "Your data is yours",
      body: "Everything lives on this server. Not OpenAI's. Not mine. Yours. You can export your ChatGPT and Claude history as files and drop them into Jetty — ask me how anytime. When you're done here, click Enter Jetty and say: \"remember that I want a Series A operations role in Silicon Slopes with partial remote.\" That's the moment. Welcome aboard."
    }
  ];

  let step = 0;

  function $(id) { return document.getElementById(id); }

  function speakNarration(text) {
    // Use the same ElevenLabs-preferred path as app.js speak()
    try {
      if (typeof window.speak === "function") {
        window.speak(text, true);  // force = true, bypasses autoplay gate
        return;
      }
    } catch (_) { /* fall through to browser voice */ }
    if ("speechSynthesis" in window) {
      try {
        speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(text);
        u.rate = 0.94;
        u.pitch = 1.0;
        speechSynthesis.speak(u);
      } catch (_) { /* silent */ }
    }
  }

  function render() {
    const c = CHAPTERS[step];
    $("onboard-step-indicator").textContent = `${step + 1} / ${CHAPTERS.length}`;
    $("onboard-title").textContent = c.title;
    $("onboard-body").textContent = c.body;
    $("onboard-next").textContent = step === CHAPTERS.length - 1 ? "Enter Jetty →" : "Next →";
    speakNarration(c.body);
  }

  function show() {
    const el = $("onboarding");
    if (!el) return;
    el.hidden = false;
    render();
  }

  function dismiss() {
    const el = $("onboarding");
    if (el) el.hidden = true;
    try { localStorage.setItem(ONBOARDED_KEY, "1"); } catch (_) { }
    if ("speechSynthesis" in window) speechSynthesis.cancel();
  }

  function next() {
    if (step < CHAPTERS.length - 1) {
      step++;
      render();
    } else {
      dismiss();
    }
  }

  function skip() {
    dismiss();
  }

  function init() {
    // Don't re-show once dismissed
    let already = false;
    try { already = localStorage.getItem(ONBOARDED_KEY) === "1"; } catch (_) { }
    if (already) return;

    const nextBtn = $("onboard-next");
    const skipBtn = $("onboard-skip");
    if (nextBtn) nextBtn.onclick = next;
    if (skipBtn) skipBtn.onclick = skip;

    // Keyboard: Enter/→ next, Esc skip
    document.addEventListener("keydown", (e) => {
      if ($("onboarding")?.hidden) return;
      if (e.key === "Enter" || e.key === "ArrowRight") { e.preventDefault(); next(); }
      else if (e.key === "Escape") { e.preventDefault(); skip(); }
    });

    // Delay show until galaxy has rendered (2s) so the backdrop frames the galaxy
    setTimeout(show, 2200);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
