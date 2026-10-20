import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const js = readFileSync(new URL('../frontend/assets/landing.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../frontend/index.html', import.meta.url), 'utf8');
const css = readFileSync(new URL('../frontend/assets/landing.css', import.meta.url), 'utf8');

// Hero media stack: still image + WebGL water-shader canvas + transparent ripple canvas.
assert.match(html, /class="hero-still"[^>]*jetty-hero-clean\.png/, 'still image underlay must use the hero photo');
assert.match(html, /<canvas id="wave-gl" class="hero-water"/, 'water motion must come from the shader canvas, not autoplay video');
assert.doesNotMatch(html, /<video/, 'no video element: autoplay-dependent motion hid the waves on some devices');
assert.match(js, /getContext\('webgl'/, 'landing.js must drive a WebGL water shader');
assert.match(js, /requestAnimationFrame\(frame\)/, 'shader must animate on rAF');
assert.match(js, /webglcontextlost/, 'context loss must degrade to the still image');

// Motion safety and battery behavior.
assert.match(js, /prefers-reduced-motion: reduce/, 'reduced-motion preference must be detected');
assert.match(js, /if \(state\.reduced \|\| !glCanvas\) \{ if \(glCanvas\) glCanvas\.remove\(\); return null; \}/, 'reduced motion must not start the shader');
assert.match(js, /document\.addEventListener\('visibilitychange'/, 'shader must pause in hidden tabs');
assert.match(js, /document\.hidden/, 'hidden tab stops the shader loop');
assert.match(js, /IntersectionObserver/, 'shader must pause when the hero is off-screen');
assert.match(css, /@media\(prefers-reduced-motion:reduce\)[\s\S]*?\.hero-water\{display:none\}/, 'reduced motion hides the shader canvas, still remains');
assert.match(css, /object-position:50% 60%/, 'portrait crop must keep the spiral and water in frame');

// Ripple overlay must not run a permanent rAF loop: it only animates while ripples live.
assert.match(js, /if \(!state\.ripples\.length\) \{ state\.rafId = 0; return; \}/, 'ripple loop must stop when idle');
assert.match(js, /state\.reduced && e\.clientY >= waterTop/, 'ripples respect reduced motion');

console.log('hero wave startup checks passed');
