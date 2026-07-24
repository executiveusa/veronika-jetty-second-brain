// lang.js — Jetty V5 MULTILINGUAL bay (ES module, loaded after the core IIFE).
// Client side of multilingual mode: keeps the browser in step with the server's
// language state (jetty-lang.json). window.__jettyLang (BCP-47) steers both
// speech recognizers + the browser-voice picker; a 🌐 chip under the reactor
// shows the active tongue; voice routes handle "speak Spanish" / "switch to
// French" / "back to English" / "what languages do you speak". The model can
// also flip the language server-side via the [LANG:] tag from ANY phrasing —
// a light poll notices and catches the client up.
// Fully optional: if the bridge never appears, this module does nothing.

const BCP = { en: 'en-US', es: 'es-ES', fr: 'fr-FR', de: 'de-DE', it: 'it-IT', pt: 'pt-BR',
              nl: 'nl-NL', hi: 'hi-IN', ur: 'ur-PK', ar: 'ar-SA', ja: 'ja-JP', ko: 'ko-KR',
              zh: 'zh-CN', ru: 'ru-RU', tr: 'tr-TR', pl: 'pl-PL' };
const NATIVE = { en: 'English', es: 'Español', fr: 'Français', de: 'Deutsch', it: 'Italiano',
                 pt: 'Português', nl: 'Nederlands', hi: 'हिन्दी', ur: 'اردو', ar: 'العربية',
                 ja: '日本語', ko: '한국어', zh: '中文', ru: 'Русский', tr: 'Türkçe', pl: 'Polski' };
// every name the SWITCH routes accept (the server's LANG_ALIAS covers all of these)
const NAMES = 'spanish|espa[ñn]ol|french|fran[çc]ais|german|deutsch|italian|italiano|portuguese|' +
              'portugu[êe]s|dutch|hindi|urdu|arabic|japanese|korean|chinese|mandarin|russian|' +
              'turkish|polish|english';

let J, CUR = 'en';

// INSTANT boot: apply the cached language BEFORE the /api/lang round-trip returns,
// so the recognizers get the right locale on the very first mic use after a reload.
try {
  const c = localStorage.getItem('jetty-lang');
  if (c && c !== 'en' && BCP[c]) { CUR = c; window.__jettyLang = BCP[c]; }
} catch (_) {}

(function boot(n) {
  if (window.__jetty) { try { init(); } catch (e) { console.warn('[lang]', e); } return; }
  if ((n || 0) < 3600) requestAnimationFrame(() => boot((n || 0) + 1));   // ~1 min of patience
})();

function init() {
  J = window.__jetty;
  chip(CUR);
  routes();
  sync();          // the server is the source of truth — reconcile the cache right away
  watchers();
}

// ---------- state ----------
function apply(code) {
  if (!BCP[code]) return;
  CUR = code;
  try { window.__jettyLang = (code === 'en') ? '' : BCP[code]; } catch (_) {}
  try {
    if (code === 'en') localStorage.removeItem('jetty-lang');
    else localStorage.setItem('jetty-lang', code);
  } catch (_) {}
  chip(code);
}

async function sync() {
  try {
    const d = await fetch('/api/lang').then(r => r.json());
    if (d && d.code && d.code !== CUR) apply(d.code);   // [LANG:] tag / another surface flipped it
  } catch (_) {}
}

// ---------- 🌐 chip (sits under the brain chip, same pill family as #j-brain-chip) ----------
function chip(code) {
  try {
    let holder = document.getElementById('j-lang-holder');
    if (!code || code === 'en') { if (holder) holder.remove(); return; }
    if (!holder) {
      const brain = document.getElementById('j-brain');
      if (!brain) return;
      holder = document.createElement('div');                       // block row → renders UNDER the chips above
      holder.id = 'j-lang-holder'; holder.style.cssText = 'margin-top:6px;';
      const el = document.createElement('span');
      el.id = 'j-lang-chip';
      el.style.cssText = 'display:inline-block;font-family:"SF Mono",ui-monospace,monospace;' +
        'font-size:11px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:#34d399;' +
        'border:1px solid rgba(52,211,153,.45);border-radius:999px;padding:5px 14px;' +
        'background:rgba(10,22,18,.72);backdrop-filter:blur(6px);';
      holder.appendChild(el); brain.appendChild(holder);
    }
    document.getElementById('j-lang-chip').textContent = '🌐 ' + (NATIVE[code] || code);
  } catch (_) {}
}

// ---------- voice routes ----------
function routes() {
  const R = (window.__jettyRoutes = window.__jettyRoutes || []);
  // "speak Spanish" / "respond in French" / "talk to me in German" / "answer in Urdu"
  // (NOTE: "speak IN spanish" is stolen upstream by the voice-wardrobe intent — by route order)
  const SWITCH = new RegExp('^(?:jetty[,!\\s]+)?(?:speak|talk|respond|reply|answer)(?: to me)?(?: in)? (' +
                            NAMES + ')[?.!]*$', 'i');
  // bare "switch to X" is constrained to real language names so "switch to grok" (model swap)
  // and "switch to dark mode" (OS) keep their existing server-side handling untouched
  const SWITCH2 = new RegExp('^(?:jetty[,!\\s]+)?switch to (' + NAMES + ')[?.!]*$', 'i');
  const SWITCH3 = /^(?:jetty[,!\s]+)?switch the language to (\w+)[?.!]*$/i;   // explicit → let the server 404 with wit
  const BACK = /^(?:jetty[,!\s]+)?(?:go |get |take (?:it|us) )?back to (?:normal |regular |plain )?english(?: please)?[?.!]*$/i;
  const LIST = /^(?:jetty[,!\s]+)?(?:what|which) languages (?:do you|can you) speak[?.!]*$/i;

  R.push({ re: BACK,    handler: async () => switchTo('english') });
  R.push({ re: SWITCH,  handler: async (q, m) => switchTo(m[1]) });
  R.push({ re: SWITCH2, handler: async (q, m) => switchTo(m[1]) });
  R.push({ re: SWITCH3, handler: async (q, m) => switchTo(m[1]) });
  R.push({ re: LIST,    handler: async () => listLangs() });
}

async function switchTo(word) {
  let d;
  try { d = await J.post('/lang', { lang: word }, 15000); }
  catch (_) { await J.say("The language centre didn't answer, sir."); return; }
  if (!d || d.error || !d.code) {           // unknown tongue → the server's witty 404 lists the repertoire
    await J.say((d && d.error) || 'The language centre refused, sir.'); return;
  }
  apply(d.code);                            // recognizers + voice pick FIRST, so the line below…
  await J.say(d.line || 'Done, sir.');      // …the canned confirmation, arrives IN the new language
}

async function listLangs() {
  let d = null;
  try { d = await fetch('/api/lang').then(r => r.json()); } catch (_) {}
  const names = (d && d.spoken) || [];
  if (!names.length) { await J.say("I couldn't consult my phrasebook just now, sir."); return; }
  await J.say('My repertoire runs to ' + names.join(', ') + ' — ' + names.length +
              ' tongues in all, sir. Say "speak Spanish", or simply address me in one and I shall reply in kind.');
}

// ---------- tag-path catch-up: the model may execute [LANG:] server-side from ANY phrasing ----------
function watchers() {
  try { setInterval(() => { if (document.visibilityState === 'visible') sync(); }, 20000); } catch (_) {}
  try { document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') sync(); }); } catch (_) {}
  try {                                      // any answer landing on screen → re-check shortly after
    const ansEl = document.getElementById('j-answer');
    if (ansEl && window.MutationObserver) {
      let t = null;
      new MutationObserver(() => { clearTimeout(t); t = setTimeout(sync, 2000); })
        .observe(ansEl, { childList: true, characterData: true, subtree: true });
    }
  } catch (_) {}
}
