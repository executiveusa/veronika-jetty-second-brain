import assert from 'node:assert/strict';import{readFileSync}from'node:fs';
const gate=readFileSync(new URL('../frontend/assets/auth-gate.js',import.meta.url),'utf8');
const build=readFileSync(new URL('../scripts/build-frontend.mjs',import.meta.url),'utf8');
const app=readFileSync(new URL('../frontend/app.html',import.meta.url),'utf8');
const wellness=readFileSync(new URL('../frontend/wellness.html',import.meta.url),'utf8');
const appJs=readFileSync(new URL('../frontend/assets/app.js',import.meta.url),'utf8');
const wellnessJs=readFileSync(new URL('../frontend/assets/wellness.js',import.meta.url),'utf8');
assert.match(gate,/Authorization.*Bearer/);assert.match(gate,/Sign-in is not configured/);assert.match(gate,/getSession/);assert.match(build,/supabaseAnonKey/);assert.match(app,/auth-gate\.js/);assert.match(wellness,/type="module" src="\/assets\/wellness\.js"/);assert.match(appJs,/^if \(window\.JETTY_AUTH_READY\) await/);assert.match(wellnessJs,/^if \(window\.JETTY_AUTH_READY\) await/);console.log('client auth checks passed');
