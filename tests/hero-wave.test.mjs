import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const js = readFileSync(new URL('../frontend/assets/landing.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../frontend/index.html', import.meta.url), 'utf8');
const css = readFileSync(new URL('../frontend/assets/landing.css', import.meta.url), 'utf8');

// Hero media stack: still image + looping video + transparent ripple canvas.
assert.match(html, /class="hero-still"[^>]*jetty-hero-clean\.png/, 'still image underlay must use the hero photo');
assert.match(html, /<video id="wave-video"[^>]*autoplay muted loop playsinline/, 'water loop video must autoplay muted inline');
assert.match(html, /jetty-water-loop\.mp4/, 'hero must reference the rendered water loop');
assert.match(html, /poster="\/assets\/jetty-hero-clean\.png"/, 'video poster must be the hero still');

// Motion safety and battery behavior.
assert.match(js, /prefers-reduced-motion: reduce/, 'reduced-motion preference must be detected');
assert.match(js, /video\.removeAttribute\('autoplay'\)/, 'reduced motion must not autoplay');
assert.match(js, /document\.addEventListener\('visibilitychange'/, 'video must pause in hidden tabs');
assert.match(js, /if \(document\.hidden\) video\.pause\(\)/, 'hidden tab pauses the video');
assert.match(css, /@media\(prefers-reduced-motion:reduce\)[\s\S]*?\.hero-water\{display:none\}/, 'reduced motion hides the video, still remains');
assert.match(css, /object-position:50% 60%/, 'portrait crop must keep the spiral and water in frame');

// Ripple overlay must not run a permanent rAF loop: it only animates while ripples live.
assert.match(js, /if \(!state\.ripples\.length\) \{ state\.rafId = 0; return; \}/, 'ripple loop must stop when idle');
assert.match(js, /state\.reduced && e\.clientY >= waterTop/, 'ripples respect reduced motion');

console.log('hero wave startup checks passed');
