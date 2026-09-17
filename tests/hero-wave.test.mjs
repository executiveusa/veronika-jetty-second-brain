import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../frontend/assets/landing.js', import.meta.url), 'utf8');
assert.match(source, /if \(img\.complete\) startHero\(\)/, 'cached images must start the hero');
assert.match(source, /document\.addEventListener\('visibilitychange'/, 'render loop must pause in hidden tabs');
assert.match(source, /if \(document\.hidden\) stopHero\(\); else startHero\(\);/);
assert.match(source, /if \(!state\.running && !document\.hidden\)/, 'only one animation loop may run');
assert.match(source, /if \(state\.reduced\) return;/, 'reduced motion must disable water movement');
console.log('hero wave startup checks passed');
