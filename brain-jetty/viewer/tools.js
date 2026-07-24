// Jetty V6 — TOOL ARMORY client (directory redesign). Registers voice routes in
// window.__jettyRoutes, adds the 🔌 dock button, and renders a full-screen tool directory:
// real brand logos on white chips (served same-origin via /tool_logo/<slug>), card grid with
// + connect buttons, registry search, confirm-gated installs, and an inline status toast so
// nothing ever fails silently. OAuth tabs are pre-opened synchronously inside the click
// gesture (popup blockers kill window.open after an await — learned the hard way).
// Fully optional: if the bridge never appears, this module does nothing.

const $id = (i) => document.getElementById(i);
const NAMECHARS = /[^a-z0-9 .+-]/g;

let J = null;                 // the __jetty bridge
let TILES = { direct: [], agent: [], connected: 0 };
let pendingInstall = null;    // {pending_id, name} awaiting "do it"
let lastSearch = [];          // registry candidates from the last search
let pollTimer = 0;
let waitingId = null;         // tile mid-OAuth — server doesn't know "waiting", so we overlay it

// ---- palette: graphite + gold. deliberately NOT the neon-emerald HUD. ----
const INK = '#ececf1', SUB = '#9a9aa5', DIM = '#61616c';
const GOLD = '#e8b64c', AMBER = '#f0a05a', CARD = '#16171c', LINE = 'rgba(255,255,255,.08)';

const MONO_BG = ['#2a2536', '#1e2a38', '#332430', '#223126', '#33301f', '#25232e'];
const monoBg = (s) => MONO_BG[[...s].reduce((a, c) => a + c.charCodeAt(0), 0) % MONO_BG.length];

function chipHTML(t) {
  const mono = `<span style="display:none;width:100%;height:100%;border-radius:10px;background:${monoBg(t.name)};color:#e8e2d4;font-size:17px;font-weight:700;align-items:center;justify-content:center;">${(t.name || '?')[0].toUpperCase()}</span>`;
  const img = t.slug
    ? `<img src="/tool_logo/${t.slug}" width="22" height="22" style="display:block;" onerror="this.style.display='none';this.nextElementSibling.style.display='flex';">`
    : '';
  return `<span style="flex-shrink:0;width:40px;height:40px;border-radius:10px;background:${t.slug ? '#ffffff' : 'transparent'};display:flex;align-items:center;justify-content:center;overflow:hidden;">${img}${mono.replace('display:none', t.slug ? 'display:none' : 'display:flex')}</span>`;
}

const PILL = {
  connected: `border:1px solid rgba(232,182,76,.55);color:${GOLD};`,
  waiting:   `border:1px solid rgba(240,160,90,.55);color:${AMBER};`,
  attention: `border:1px solid rgba(240,160,90,.55);color:${AMBER};`,
  setup:     `border:1px solid rgba(255,255,255,.14);color:${DIM};`,
};
const PILL_TEXT = { connected: '✓ connected', waiting: 'approve in the tab…', attention: 're-connect', setup: 'google setup' };

// tile action bar — BUTTONS, never typed commands (the old prompt() asked you to type "disconnect")
let menuId = null, removeArm = null;
// standard solid buttons — content-sized so they WRAP instead of overlapping (flex:1+min-width:0
// let nowrap labels paint over the neighbor), solid backgrounds, no gold/pink ghosts.
const BTN_KIND = {
  primary:     'background:#e8eaef;border:1px solid #e8eaef;color:#17181d;',
  neutral:     'background:#2f323a;border:1px solid #464a53;color:#e6e8ee;',
  danger:      'background:#2f323a;border:1px solid #464a53;color:#e5484d;',
  dangersolid: 'background:#dc2626;border:1px solid #dc2626;color:#ffffff;',
};
function menuBtn(act, label, kind) {
  return `<button data-act="${act}" style="flex:0 0 auto;padding:8px 14px;border-radius:8px;${BTN_KIND[kind] || BTN_KIND.neutral}font-size:12px;font-weight:600;font-family:-apple-system,'Segoe UI',sans-serif;cursor:pointer;white-space:nowrap;">${label}</button>`;
}
const AUTH_LABEL = { oauth: 'one-click sign-in', token: 'paste a token', url: 'paste your MCP URL',
                     google: 'Google sign-in', none: 'open — no login' };
function menuHTML(t) {
  const b = [];
  if (t.status === 'connected') {
    b.push(menuBtn('toggle', t.enabled ? '⏸ Pause' : '▶ Resume', 'neutral'));
    b.push(menuBtn('disconnect', 'Disconnect', 'danger'));
  } else if (t.status === 'waiting') {
    b.push(menuBtn('check', "I've approved — check", 'primary'));
    b.push(menuBtn('cancel', 'Cancel', 'neutral'));
  } else if (t.status === 'setup') {
    b.push(menuBtn('connect', 'Set up Google', 'primary'));
  } else {  // available — the ＋ now lives HERE, so a tile-click never fires OAuth on its own
    b.push(menuBtn('connect', t.auth === 'token' ? '＋ Connect (paste key)'
      : t.auth === 'url' ? '＋ Connect (paste URL)' : '＋ Connect', 'primary'));
  }
  // remove is on EVERY tile: custom → deleted, curated → hidden from the shelf (restorable)
  b.push(menuBtn('remove', removeArm === t.id ? 'Really remove?' : (t.custom ? 'Remove…' : 'Hide…'),
    removeArm === t.id ? 'dangersolid' : 'danger'));
  const detail = `<div style="width:100%;font-size:11px;color:${DIM};font-family:'SF Mono',ui-monospace,monospace;margin-top:11px;">`
    + `${AUTH_LABEL[t.auth] || t.auth} · ${t.host || ''}${t.custom ? ' · custom' : ''}</div>`;
  return detail + `<div class="jt-menu" style="display:flex;gap:8px;margin-top:9px;width:100%;flex-wrap:wrap;">${b.join('')}</div>`;
}

function cardHTML(t) {
  const lit = t.status === 'connected';
  const pill = PILL[t.status]
    ? `<span style="font-size:10px;letter-spacing:.06em;border-radius:99px;padding:4px 10px;${PILL[t.status]}">${t.enabled === false && lit ? 'paused' : PILL_TEXT[t.status]}</span>`
    : `<span class="jt-plus" style="display:inline-flex;width:30px;height:30px;border-radius:50%;border:1px solid rgba(255,255,255,.2);color:${INK};font-size:17px;align-items:center;justify-content:center;">+</span>`;
  return `<div class="jt-card jt-tile" data-id="${t.id}" style="background:${CARD};border:1px solid ${lit ? 'rgba(232,182,76,.4)' : LINE};border-radius:14px;padding:14px 16px;box-sizing:border-box;min-height:86px;display:flex;flex-wrap:wrap;gap:13px;align-items:flex-start;cursor:pointer;">
    ${chipHTML(t)}
    <span style="flex:1;min-width:0;">
      <span style="display:flex;align-items:center;gap:7px;">
        <span style="font-size:14px;color:${INK};font-weight:600;font-family:-apple-system,'Segoe UI',sans-serif;">${t.name}</span>
        ${t.custom ? '' : `<span style="color:${DIM};font-size:11px;">✓</span>`}
      </span>
      <span style="display:block;font-size:11.5px;color:${SUB};line-height:1.5;margin-top:3px;font-family:-apple-system,'Segoe UI',sans-serif;max-height:36px;overflow:hidden;">${t.blurb || ''}</span>
    </span>
    <span style="flex-shrink:0;padding-top:5px;">${pill}</span>
    ${menuId === t.id ? menuHTML(t) : ''}
  </div>`;
}

function ghostHTML(c, i) {
  return `<div class="jt-card jt-ghost" data-i="${i}" style="background:${CARD};border:1px dashed rgba(232,182,76,.35);border-radius:14px;padding:14px 16px;display:flex;gap:13px;align-items:flex-start;cursor:pointer;">
    <span style="flex-shrink:0;width:40px;height:40px;border-radius:10px;background:${monoBg(c.name)};color:#e8e2d4;font-size:17px;font-weight:700;display:flex;align-items:center;justify-content:center;">${(c.name || '?')[0].toUpperCase()}</span>
    <span style="flex:1;min-width:0;">
      <span style="font-size:14px;color:${INK};font-weight:600;font-family:-apple-system,'Segoe UI',sans-serif;">${c.name}</span>
      <span style="display:block;font-size:11.5px;color:${SUB};line-height:1.5;margin-top:3px;font-family:-apple-system,'Segoe UI',sans-serif;max-height:36px;overflow:hidden;">${(c.description || '').slice(0, 110)}</span>
      <span style="display:block;font-size:10px;color:${DIM};margin-top:5px;">${c.url ? 'remote server — installs instantly' : 'local package — waits for your “do it”'}</span>
    </span>
    <span style="flex-shrink:0;padding-top:5px;"><span style="display:inline-flex;width:30px;height:30px;border-radius:50%;border:1px solid rgba(232,182,76,.5);color:${GOLD};font-size:15px;align-items:center;justify-content:center;">⤓</span></span>
  </div>`;
}

function agentHTML(m) {
  return `<div style="background:${CARD};border:1px solid ${LINE};border-radius:12px;padding:10px 14px;display:flex;align-items:center;gap:10px;" title="Attached to Claude Code — Jetty uses it through missions and the agent.">
    <span style="flex-shrink:0;width:28px;height:28px;border-radius:8px;background:${monoBg(m.name)};color:#e8e2d4;font-size:13px;font-weight:700;display:flex;align-items:center;justify-content:center;">${m.name[0].toUpperCase()}</span>
    <span style="font-size:12.5px;color:${INK};flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-family:-apple-system,'Segoe UI',sans-serif;">${m.name}</span>
    <span style="font-size:9.5px;color:${DIM};border:1px solid ${LINE};border-radius:99px;padding:3px 9px;">via missions</span>
  </div>`;
}

function toast(msg, kind, linkText, linkUrl) {
  const el = $id('jt-toast');
  if (!el) return;
  const color = kind === 'err' ? '#e77' : kind === 'ok' ? GOLD : SUB;
  el.innerHTML = msg
    ? `<span style="color:${color};">${msg}</span>` +
      (linkUrl ? ` <a href="${linkUrl}" target="_blank" style="color:${GOLD};text-decoration:underline;">${linkText || 'continue →'}</a>` : '')
    : '';
  el.style.display = msg ? 'block' : 'none';
}

function armoryEl() {
  let el = $id('j-armory');
  if (el) return el;
  el = document.createElement('div');
  el.id = 'j-armory';
  el.style.cssText = 'position:fixed;inset:0;z-index:90;display:none;overflow-y:auto;background:'
    + 'radial-gradient(700px 340px at 50% -120px, rgba(232,182,76,.09), transparent),'
    + 'radial-gradient(rgba(255,255,255,.05) 1px, transparent 1px) 0 0/22px 22px,'
    + '#0d0e12;';
  el.innerHTML = `<div style="max-width:1020px;margin:0 auto;padding:44px 26px 60px;">
    <div style="display:flex;align-items:center;gap:16px;margin-bottom:6px;">
      <div style="font-family:Georgia,'Times New Roman',serif;font-size:30px;color:${INK};">Tool armory</div>
      <div id="jt-count" style="font-size:11.5px;color:${DIM};font-family:'SF Mono',ui-monospace,monospace;padding-top:8px;"></div>
      <button id="jt-close" style="margin-left:auto;background:#2f323a;border:1px solid #464a53;border-radius:99px;color:#e6e8ee;font-size:12px;padding:7px 16px;cursor:pointer;">✕ close</button>
    </div>
    <div style="font-size:12.5px;color:${SUB};margin-bottom:22px;font-family:-apple-system,'Segoe UI',sans-serif;">Everything Jetty can reach — connect an app and he uses it mid-conversation.</div>
    <div style="display:flex;gap:10px;margin-bottom:8px;">
      <input id="jt-q" placeholder="Search for new tools…  ( airtable, email marketing, weather )"
        style="flex:1;background:rgba(255,255,255,.05);border:1px solid ${LINE};border-radius:12px;padding:12px 16px;color:${INK};font-size:13.5px;outline:none;font-family:-apple-system,'Segoe UI',sans-serif;">
      <button id="jt-go" style="background:#e8eaef;border:1px solid #e8eaef;border-radius:12px;color:#17181d;font-size:12.5px;font-weight:600;padding:0 20px;cursor:pointer;">search</button>
    </div>
    <div id="jt-toast" style="display:none;font-size:12px;margin:6px 2px 0;font-family:-apple-system,'Segoe UI',sans-serif;"></div>
    <div id="jt-found-wrap" style="display:none;margin-top:22px;">
      <div style="font-size:11px;letter-spacing:.16em;color:${DIM};margin-bottom:10px;font-family:'SF Mono',ui-monospace,monospace;">DISCOVERED — CLICK TO INSTALL</div>
      <div id="jt-found" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;align-items:start;"></div>
    </div>
    <div style="font-size:11px;letter-spacing:.16em;color:${DIM};margin:26px 0 10px;font-family:'SF Mono',ui-monospace,monospace;">CONNECT DIRECTLY</div>
    <div id="jt-direct" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;align-items:start;"></div>
    <div style="font-size:11px;color:${DIM};line-height:1.7;margin-top:30px;font-family:'SF Mono',ui-monospace,monospace;">say: “connect notion” · “install airtable” · “find me a tool for email marketing” · “use canva to make a thumbnail” · “what tools do you have”</div>
  </div>`;
  document.body.appendChild(el);
  const style = document.createElement('style');
  style.textContent = '.jt-card:hover{border-color:rgba(232,182,76,.55)!important;} #jt-q::placeholder{color:#61616c;}'
    + '.jt-menu button:hover,#jt-go:hover,#jt-close:hover{filter:brightness(1.12);}';
  document.head.appendChild(style);
  el.addEventListener('click', (e) => { if (e.target === el) hide(); });
  el.querySelector('#jt-close').onclick = hide;
  el.querySelector('#jt-go').onclick = () => doSearch(el.querySelector('#jt-q').value);
  el.querySelector('#jt-q').addEventListener('keydown', (e) => { if (e.key === 'Enter') doSearch(e.target.value); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && el.style.display !== 'none') hide(); });
  return el;
}

const NEVER = /$^/;
const doitRoute = { re: NEVER, handler: confirmVoice };      // armed only while an install is pending
const toolRoute = { re: NEVER, handler: (q) => toolChat(q) };// armed only with connected tools, name+verb
const appRoute  = { re: NEVER, handler: (q) => toolChat(q) };// app noun + verb, NO tool named — the brain picks (Zapier = wildcard)
// "check again" / "that's wrong" after a tool run → RE-RUN the tools with a double-check note
// (2026-07-13: disputed results must trigger a fresh query, never a conceding chat reply).
// Audit hardening: 10-min recency gate (a stale morning query must not hijack an afternoon
// dispute) + verbs narrowed to check/look ("try/run again" belongs to research & agent retries).
let lastToolQ = null;                                     // {q, ts} of the last tool question
const RETRY_MS = 10 * 60 * 1000;
const RETRY_RE = /\b(?:check|look)(?: it| that)? again\b|^(?:no[,.\s]+)?that'?s (?:wrong|not right|incorrect)\b/i;
const retryRoute = { re: { test: (q) => !!lastToolQ && (Date.now() - lastToolQ.ts) < RETRY_MS && RETRY_RE.test(q) },
  handler: (q) => toolChat(lastToolQ.q + ' — the user says the previous answer was WRONG ("' + q
    + '"). Re-run the tools FRESH, double-check every parameter (dates, timezone, which account/'
    + 'calendar/mailbox), and name exactly which account you searched.') };
const rxEsc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// a NAMED tool Jetty doesn't have connected → offer to add it or check Zapier (user-requested).
// Extracts the name from "use X to…", "with X", "run X"; fires ONLY when X isn't a connected tile,
// isn't a known Zapier app (those auto-route), and isn't a native surface — so it never shadows
// real intents. pendingOffer holds the original request until sir says "check zapier" or "no".
let pendingOffer = null, offerName = '', offerTimer = 0;
const NAMEDTOOL = /\b(?:use|using|via|run|open|launch|fire up|through)\s+(?:the\s+)?([a-z][a-z0-9.\-]{2,20})\b(?=.*\b(?:to|and|for|make|create|generate|design|draft|build|edit|post|export|find|search|send)\b)/i;
const OFFER_STOP = /\b(my|the|it|that|this|computer|screen|mouse|keyboard|internet|web|notes?|brain|vault|graph|voice|zapier|toolbox|armou?ry)\b/i;
function namedUnknownTool(q) {
  if (!connectedNames.length) return null;                 // nothing to check against → let chat answer
  const m = q.match(NAMEDTOOL); if (!m) return null;
  const name = m[1].trim();
  if (OFFER_STOP.test(name) || LOCALISH.test(name) || ZAPPY.test(name)) return null;
  if (fuzzyToolIn(name)) return null;                      // already connected → toolRoute owns it
  return name;
}
const offerRoute = { re: { test: (q) => { const n = namedUnknownTool(q); if (n) offerName = n; return !!n; } },
                     handler: (q) => offerZapier(q) };
const offerConfirm = { re: NEVER, handler: (q) => resolveOffer(q) };
function armOffer(on) {
  clearTimeout(offerTimer);
  offerConfirm.re = on
    ? /^(?:yes|yeah|yep|sure|okay|ok|please|check zapier|check it|look it up|do that|go for it|no|nope|don'?t|cancel|never ?mind|forget it)\b/i
    : NEVER;
  if (on) offerTimer = setTimeout(() => { pendingOffer = null; armOffer(false); }, 25000);
}
async function offerZapier(q) {
  pendingOffer = q; armOffer(true);
  await J.say(`${offerName} isn't in your arsenal, sir — you can add it yourself in the toolbox, or I can check whether Zapier has it. Shall I check Zapier?`);
}
async function resolveOffer(q) {
  const req = pendingOffer; pendingOffer = null; armOffer(false);
  if (/\b(no|nope|don'?t|cancel|never ?mind|forget it)\b/i.test(q)) return J.say('As you wish, sir — say "add a tool" whenever you like.');
  if (!req) return;
  await toolChat(req);   // now runs through the tool brain, which reaches Zapier's whole catalogue
}

let confirmTimer = 0;
function armConfirm(on) {
  doitRoute.re = on ? /^(?:do it|go ahead|yes,? do it|install it)[.!]?$/i : NEVER;
  clearTimeout(confirmTimer);   // audit fix: never stays armed forever — a stale "do it" hours later
  if (on) confirmTimer = setTimeout(() => { doitRoute.re = NEVER; pendingInstall = null; lastSearch = []; }, 90000);
}

const ACTIONY = /\b(use|make|create|design|draft|add|update|search|find|list|check|export|generate|put|log|open|pull|fetch|post|schedule|send)\b/i;

// apps the user may name WITHOUT them being directly connected — Zapier almost certainly fronts
// them, so the ask routes to the tool brain which checks direct connections first, then Zapier,
// then reports the miss. Deliberately EXCLUDES surfaces Jetty already owns natively: calendar/
// schedule (briefing), youtube (war room), instagram/tiktok/social posting (Blotato missions),
// notes/brain/vault/screen (local).
const ZAPPY = /\b(g?mail|e-?mails?|inbox(?:es)?|slack|canva|notion|sheets?|spreadsheets?|airtable|google docs?|drive|dropbox|trello|asana|linear|jira|hubspot|salesforce|mailchimp|convert ?kit|kit|klaviyo|stripe|github|figma|discord|calendly|typeform|shopify|quickbooks|zapier|zaps?|calendar|schedule|meetings?|agenda|events?)\b/i;
const LOCALISH = /\b(?:my (?:brain|notes?|graph|vault)|calendar|schedule|screen|youtube|instagram|tiktok|blotato)\b/i;      // native surfaces
const LOCALISH_ZAP = /\b(?:my (?:brain|notes?|graph|vault)|screen|youtube|instagram|tiktok|blotato)\b/i;                    // Zapier wildcard connected → calendar/schedule ride the tools

// speech-tolerant tool-name matching: "higgs field" / "higsfield" / "can va" all find their
// tile. Normalize away spaces/punctuation, then allow ~1 typo per 6 chars (voice never spells).
let connectedNames = [];
function normName(s) { return String(s || '').toLowerCase().replace(/[^a-z0-9]/g, ''); }
function fuzzyHas(hay, needle) {
  if (!needle || needle.length < 4) return hay.includes(needle);
  if (hay.includes(needle)) return true;
  const tol = Math.max(1, Math.floor(needle.length / 6));
  for (let i = 0; i + needle.length <= hay.length; i++) {          // misheard LETTERS (substitutions)
    let miss = 0;
    for (let j = 0; j < needle.length && miss <= tol; j++) if (hay[i + j] !== needle[j]) miss++;
    if (miss <= tol) return true;
  }
  if (needle.length >= 5) {                                        // a DROPPED letter ("higsfield")
    for (let k = 0; k < needle.length; k++) {
      if (hay.includes(needle.slice(0, k) + needle.slice(k + 1))) return true;
    }
  }
  return false;
}
function fuzzyToolIn(q) {
  const qq = normName(q);
  return connectedNames.find((n) => fuzzyHas(qq, normName(n))) || null;
}

function zapWildcard() {
  return TILES.direct.some((t) => t.status === 'connected' && t.enabled !== false && /zapier/i.test(t.id + ' ' + t.name));
}
function rebuildToolRoute() {
  const on = TILES.direct.filter((t) => t.status === 'connected' && t.enabled);
  connectedNames = on.map((t) => t.name);
  // named-tool actions — duck-typed .test so mishearings still route ("generate an image
  // using higgs field" reaches the tool brain, which matches names generously itself)
  toolRoute.re = on.length
    ? { test: (q) => ACTIONY.test(q) && !!fuzzyToolIn(q) }
    : NEVER;
  // the no-tool-named route: "check my email", "add this to my sheet" — armed whenever ANYTHING
  // is connected (the tool brain does the picking; Zapier is the wildcard behind it)
  const loc = zapWildcard() ? LOCALISH_ZAP : LOCALISH;   // with Zapier connected, calendar asks go to the tools too
  appRoute.re = on.length
    ? new RegExp(`^(?!.*${loc.source})(?=.*(?:${ACTIONY.source}|what'?s on|what is on))(?=.*${ZAPPY.source})`, 'i')
    : NEVER;
}

function paint() {
  const el = armoryEl();
  el.querySelector('#jt-count').textContent = `${TILES.connected} connected`;
  const hiddenLink = TILES.hidden
    ? `<div id="jt-showhidden" style="grid-column:1/-1;text-align:center;font-size:11.5px;color:${DIM};cursor:pointer;`
      + `font-family:'SF Mono',ui-monospace,monospace;padding:4px;">↩ show ${TILES.hidden} hidden tool${TILES.hidden > 1 ? 's' : ''}</div>`
    : '';
  el.querySelector('#jt-direct').innerHTML = applyOrder(TILES.direct).map(cardHTML).join('')
    + `<div class="jt-card" id="jt-addcustom" style="display:flex;align-items:center;justify-content:center;gap:10px;`
    + `box-sizing:border-box;min-height:86px;border:1.5px dashed rgba(232,182,76,.45);border-radius:14px;cursor:pointer;`
    + `color:${GOLD};font-size:13.5px;font-family:-apple-system,sans-serif;background:rgba(232,182,76,.04);">`
    + `<span style="font-size:19px;">＋</span> Add your own tool <span style="color:${DIM};font-size:11.5px;">(any MCP URL)</span></div>`
    + hiddenLink;
  el.querySelectorAll('.jt-tile').forEach((n) => {
    n.onclick = () => tileClick(n.dataset.id);
    n.draggable = (menuId !== n.dataset.id);   // collapsed tiles reorder; the open one keeps its buttons clickable
    n.style.cursor = n.draggable ? 'grab' : 'pointer';
    n.ondragstart = (e) => { dragId = n.dataset.id; try { e.dataTransfer.effectAllowed = 'move'; } catch (_) {} };
    n.ondragover = (e) => { e.preventDefault(); };
    n.ondrop = (e) => { e.preventDefault(); reorderTo(n.dataset.id); };
  });
  el.querySelectorAll('.jt-menu [data-act]').forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); menuAct(b.closest('.jt-tile').dataset.id, b.dataset.act); };
  });
  const add = el.querySelector('#jt-addcustom');
  if (add) add.onclick = addCustomTool;
  const sh = el.querySelector('#jt-showhidden');
  if (sh) sh.onclick = async () => { await J.post('/tools_unhide', {}); toast('hidden tools restored'); await refresh(); };
  const btn = $id('j-toolsbtn');   // gold ring when ≥1 tool is connected (emoji ignores style.color)
  if (btn) { btn.style.borderColor = TILES.connected ? 'rgba(232,182,76,.7)' : 'rgba(52,211,153,.45)';
             btn.style.boxShadow = TILES.connected ? '0 0 10px rgba(232,182,76,.28)' : 'none'; }
}

async function refresh() {
  try { TILES = await (await fetch('/api/tools')).json(); } catch (_) { return; }
  const w = waitingId && TILES.direct.find((t) => t.id === waitingId);
  if (w && w.status !== 'connected') w.status = 'waiting';
  rebuildToolRoute();
  paint();
}

async function addCustomTool() {
  const name = (window.prompt('Name for your tool (e.g. "My CRM"):') || '').trim();
  if (!name) return;
  const url = (window.prompt('Its MCP server URL (https://…):') || '').trim();
  if (!url) return;
  toast(`probing ${name}…`);
  const r = await J.post('/tools_custom', { name, url }, 20000);
  if (!r || r.error) { toast((r && r.error) || 'that URL did not answer'); return; }
  toast(`${name} is on the shelf — click its tile to connect`);
  await refresh();
}

function show() { armoryEl().style.display = 'block'; refresh(); }
function hide() { const el = $id('j-armory'); if (el) el.style.display = 'none'; toast(''); }

function findTile(id) { return TILES.direct.find((t) => t.id === id); }
function byName(name) {
  const n = (name || '').toLowerCase().replace(NAMECHARS, '').trim();
  return TILES.direct.find((t) => t.name.toLowerCase() === n) ||
         TILES.direct.find((t) => t.name.toLowerCase().includes(n) || t.id.includes(n.replace(/ /g, '')));
}

function tileClick(id) {
  const t = findTile(id);
  if (!t) return;
  // EVERY tile opens its detail menu — clicking never fires OAuth. Connect happens on the ＋ button.
  removeArm = null;
  menuId = (menuId === id) ? null : id;
  paint();
}

async function menuAct(id, act) {
  const t = findTile(id);
  if (!t) return;
  if (act === 'connect') { menuId = null; paint(); return connectTool(t, true); }   // stay synchronous — the popup must own this click
  if (act === 'remove' && removeArm !== id) { removeArm = id; paint(); return; }    // two-step arm, no dialogs
  if (act === 'toggle') { await J.post('/tools_toggle', { id }); toast(t.enabled ? `${t.name} paused` : `${t.name} back on duty`); }
  else if (act === 'disconnect') { await J.post('/tools_disconnect', { id }); toast(`${t.name} disconnected`); }
  else if (act === 'cancel') { clearInterval(pollTimer); if (waitingId === id) waitingId = null; toast(`${t.name} connection cancelled`); }
  else if (act === 'check') { toast(`checking ${t.name}…`); }
  else if (act === 'remove') {   // custom → deleted; curated → hidden (restorable via "show hidden")
    await J.post(t.custom ? '/tools_custom_remove' : '/tools_hide', { id });
    clearInterval(pollTimer); if (waitingId === id) waitingId = null;
    toast(t.custom ? `${t.name} removed from the shelf` : `${t.name} hidden — restore any time`);
  }
  menuId = null; removeArm = null;
  await refresh();
}

// ---- drag-to-reorder (persisted per browser) ----
let dragId = null;
function savedOrder() { try { return JSON.parse(localStorage.getItem('jetty-tool-order') || '[]'); } catch (_) { return []; } }
function applyOrder(list) {
  const ord = savedOrder(); if (!ord.length) return list;
  const rank = (id) => { const i = ord.indexOf(id); return i < 0 ? 1e6 : i; };
  return list.slice().sort((a, b) => rank(a.id) - rank(b.id));
}
function reorderTo(targetId) {
  if (!dragId || dragId === targetId) return;
  const ids = applyOrder(TILES.direct).map((t) => t.id);
  const from = ids.indexOf(dragId); if (from < 0) { dragId = null; return; }
  ids.splice(from, 1);
  const to = ids.indexOf(targetId);
  ids.splice(to < 0 ? ids.length : to, 0, dragId);
  try { localStorage.setItem('jetty-tool-order', JSON.stringify(ids)); } catch (_) {}
  dragId = null; menuId = null; paint();
}

async function connectTool(t, inGesture) {
  if (t.auth === 'token' || t.auth === 'url') {
    const val = prompt(`${t.name} — paste your ${t.auth === 'url' ? 'personal MCP URL' : 'token'}\n${t.hint || ''}`);
    if (!val) return;
    const r = await J.post('/tools_connect', { id: t.id, [t.auth === 'url' ? 'url' : 'token']: val.trim() });
    if (r && r.connected) { toast(`${t.name} connected.`, 'ok'); J.say(`${t.name} is online, sir.`); refresh(); }
    else toast((r && r.error) || 'That did not take.', 'err');
    return;
  }
  if (t.auth === 'none') {
    const r = await J.post('/tools_connect', { id: t.id });
    if (r && r.connected) { toast(`${t.name} connected.`, 'ok'); J.say(`${t.name} is online, sir.`); refresh(); }
    else toast((r && r.error) || 'Could not reach it.', 'err');
    return;
  }
  // OAuth: pre-open the tab SYNCHRONOUSLY (inside the click) so popup blockers allow it.
  const win = inGesture ? window.open('about:blank', '_blank') : null;
  toast(`Contacting ${t.name}…`);
  const r = await J.post('/tools_connect', { id: t.id }, 45000);
  if (r && r.setup) {                       // Google tiles before the one-time client exists: guide, not error
    if (win) win.close();
    toast(r.msg);
    return J.say(`${t.name} needs your own free Google sign-in client first, sir — the step-by-step is on screen. Fifteen minutes, once, and both Google cards go live.`);
  }
  if (!r || r.error) {
    if (win) win.close();
    toast((r && r.error) || `Couldn't reach ${t.name}'s sign-in.`, 'err');
    return J.say(`${t.name} declined the handshake, sir — the details are on screen.`);
  }
  if (win && !win.closed) win.location = r.auth_url;
  else toast(`${t.name} is ready to approve —`, 'ok', `continue to ${t.name} →`, r.auth_url);
  waitingId = t.id;
  refresh();
  toast(`Approve Jetty in the ${t.name} tab — I'll light the card the moment it's done.`);
  J.say(`I've opened ${t.name}'s approval page, sir — say the word there and I'll take it from here.`);
  clearInterval(pollTimer);
  const t0 = Date.now();
  pollTimer = setInterval(async () => {
    if (Date.now() - t0 > 180000) return clearInterval(pollTimer);
    try {
      const d = await (await fetch('/api/tools')).json();
      const now = d.direct.find((x) => x.id === t.id);
      if (now && now.status === 'connected') {
        clearInterval(pollTimer); waitingId = null; TILES = d; refresh();
        toast(`${t.name} connected.`, 'ok');
        J.say(`${t.name} is online, sir. The armory grows.`);
      }
    } catch (_) {}
  }, 2500);
}

async function doSearch(q) {
  q = (q || '').trim();
  if (!q) return;
  const el = armoryEl();
  el.querySelector('#jt-found-wrap').style.display = 'block';
  el.querySelector('#jt-found').innerHTML = `<div style="font-size:12px;color:${SUB};font-family:-apple-system,sans-serif;">searching the MCP registry…</div>`;
  const r = await J.post('/tools_search', { q }, 30000);
  lastSearch = (r && r.results) || [];
  el.querySelector('#jt-found').innerHTML = lastSearch.length ? lastSearch.map(ghostHTML).join('')
    : `<div style="font-size:12px;color:${SUB};font-family:-apple-system,sans-serif;">nothing in the registry for “${q}” — try different words</div>`;
  el.querySelectorAll('.jt-ghost').forEach((n) => { n.onclick = () => installCandidate(lastSearch[+n.dataset.i]); });
  return lastSearch;
}

async function installCandidate(c) {
  if (!c) return;
  const r = await J.post('/tools_install', { candidate: c }, 30000);
  if (!r) return;
  if (r.error) return toast(r.error, 'err');
  if (r.pending_id) { pendingInstall = r; armConfirm(true); toast(r.say); J.say(r.say); return; }
  pendingInstall = null;
  if (!lastSearch.length) armConfirm(false);
  await refresh();
  toast(`${r.name} is on the shelf — click it to connect.`, 'ok');
  J.say(r.say || `${r.name} is on the shelf, sir.`);
}

async function confirmVoice() {
  if (pendingInstall) {
    const p = pendingInstall; pendingInstall = null; armConfirm(false);
    const r = await J.post('/tools_install_confirm', { pending_id: p.pending_id }, 120000);
    if (r && r.say) { await refresh(); toast(r.say, 'ok'); return J.say(r.say); }
    return J.say((r && r.error) || 'The install did not take, sir.');
  }
  if (lastSearch.length) {
    const c = lastSearch.shift();
    if (!lastSearch.length && !pendingInstall) armConfirm(false);
    return installCandidate(c);
  }
  armConfirm(false);
}

async function toolChat(q) {
  if (!/previous answer was WRONG/.test(q)) lastToolQ = { q, ts: Date.now() };   // for "check again" (don't nest retries)
  J.status('● reaching for the tools…');
  // immediate ack, then SILENT routing — direct tool first, Zapier second, zero route narration
  // (user 2026-07-13: "it should immediately say let me see if I have access — then just do it")
  // fire-and-forget: awaiting the spoken ack delayed the actual fetch by ~3-4s (user: "incredibly slow")
  try { J.say('Let me see if I have the tools for that, sir.').catch(() => {}); } catch (_) {}
  // heartbeat: witty status lines so he's never silent more than ~5s mid-run
  const hb = J.progress ? J.progress(4500) : (J.ack && J.ack('agent', 1600));
  const r = await J.post('/tool_chat', { question: q, session: J.session }, 160000);
  if (hb && hb.settle) { try { await hb.settle(); } catch (_) {} }
  if (!r || r.error) return J.say((r && r.error) || 'The tools misfired, sir.');
  J.setLastNote && J.setLastNote(r.answer);
  // honesty receipts: WHICH tools actually ran (and failures) — a data answer with zero calls is
  // suspect. Painted into the ANSWER PANEL too: hands-free mode's armFollowup() overwrites the
  // status line with "listening, sir…" instantly, so status-only receipts were invisible by voice.
  const rec = (r.tool_calls || []).slice(0, 3).join(' · ');
  const receipt = r.tool_errors
    ? '⚠ ' + r.tool_errors + ' tool call(s) FAILED — via ' + (r.tools_used || []).join(', ') + (rec ? ' · ' + rec : '')
    : (r.tools_used && r.tools_used.length) ? 'via ' + r.tools_used.join(', ') + (rec ? ' · ' + rec : '')
    : 'no tool was called';
  if (localStorage.getItem('jetty-readback') !== '0') await J.say(r.answer);        // spoken read-back with commentary (default)
  else if (J.voice) await J.voice('On your screen, sir.');                           // "I'll read it myself" mode
  if (J.showLine) J.showLine(r.answer + '   —   ' + receipt);                        // receipt survives the status overwrite
  J.status('● ' + receipt);
}

function dockButton() {
  const live = $id('j-live');
  if (!live || $id('j-toolsbtn')) return;
  const b = document.createElement('button');
  b.id = 'j-toolsbtn';
  b.className = 'j-dock';
  b.dataset.tip = 'Tool armory — connect and manage apps';
  // the plug emoji is near-black — invert it to white so it reads on the dark chip
  b.innerHTML = '<span style="display:inline-block;filter:invert(1) brightness(1.4);">🔌</span>';
  b.style.cssText = live.style.cssText;
  b.onclick = () => { const el = $id('j-armory'); (el && el.style.display === 'block') ? hide() : show(); };
  live.parentElement.insertBefore(b, live);
}

function routes() {
  const R = (window.__jettyRoutes = window.__jettyRoutes || []);
  R.push(
    { re: /^(?:open|show|pull up)\b.*\b(?:tool ?box|armou?ry|tools)\b/i, handler: async () => { show(); await J.say('The armory, sir.'); } },
    { re: /^(?:close|hide)\b.*\b(?:tool ?box|armou?ry|tools)\b/i, handler: async () => hide() },
    { re: /\bwhat tools\b.*\b(?:have|connected|available)\b|\bwhat(?:'s| is) in the (?:tool ?box|armou?ry)\b/i,
      handler: async () => {
        await refresh();
        const on = TILES.direct.filter((t) => t.status === 'connected' && t.enabled).map((t) => t.name);
        const line = on.length
          ? `Connected: ${on.join(', ')}. Say "open the toolbox" to see the wall, sir — one click adds more.`
          : `Nothing connected yet, sir. Say "open the toolbox" — Canva, Notion, Figma and friends are one click each, and Zapier covers the rest.`;
        await J.say(line);
      } },
    { re: /^connect (?:to |the )?([a-z0-9 .+-]{2,30})$/i,
      handler: async (q, m) => {
        await refresh();
        const t = byName(m[1]);
        if (!t) return J.say(`No ${m[1]} on the shelf, sir — say "install ${m[1]}" and I'll go find it.`);
        show(); connectTool(t, false);   // voice → no gesture → toast offers the continue link
      } },
    { re: /^disconnect (?:from |the )?([a-z0-9 .+-]{2,30})$/i,
      handler: async (q, m) => {
        const t = byName(m[1]);
        if (!t) return J.say(`Nothing called ${m[1]} is connected, sir.`);
        await J.post('/tools_disconnect', { id: t.id }); await refresh();
        await J.say(`${t.name} is unplugged, sir.`);
      } },
    { re: /^(?:install|get|add) (?:the )?([a-z0-9 .+-]{2,40}?)(?: tool| mcp| server)?$/i,
      handler: async (q, m) => {
        await refresh();
        const already = byName(m[1]);
        if (already) { show(); return connectTool(already, false); }
        show();
        const found = await doSearch(m[1]);
        if (!found || !found.length) return J.say(`The registry has nothing for ${m[1]}, sir.`);
        await installCandidate(found[0]);
      } },
    { re: /(?:find|search for|recommend)(?: me)? a tool (?:for|to|that) (.+)/i,
      handler: async (q, m) => {
        show();
        const found = await doSearch(m[1]);
        if (!found || !found.length) return J.say(`The registry came up empty for that, sir.`);
        const names = found.slice(0, 3).map((c) => c.name).join(', ');
        lastSearch = found; armConfirm(true);
        await J.say(`Top candidates: ${names}. Say "do it" for ${found[0].name}, or "install" any of the others, sir.`);
      } },
    retryRoute,          // "check again" / "that's wrong" after a tool run — fresh re-query, never concession
    toolRoute,           // connected-tool actions ("use canva to…") — regex armed by rebuildToolRoute()
    appRoute,            // "check my email / add this to my sheet" — no tool named; the brain routes, Zapier is the wildcard
    offerRoute,          // a NAMED tool that isn't connected → offer to add it or check Zapier
  );
  R.unshift(offerConfirm);  // "check zapier" / "no" — wins only while an offer is pending (regex NEVER otherwise)
  R.unshift(doitRoute);     // outranks the mission bay's "do it" ONLY while an install is pending
}

(function boot() {
  // SELF-HEAL read-aloud: screen-only mode ('jetty-readback'='0') used to persist across reloads,
  // so one "I'll read it myself" left Jetty permanently silent (user 2026-07-13: "it puts it on
  // screen but won't read it"). Reading aloud is now the guaranteed default on every fresh load;
  // "I'll read it myself" lasts only for the current session and resets on reload.
  try { localStorage.removeItem('jetty-readback'); } catch (_) {}
  let tries = 0;
  const wait = setInterval(() => {
    if (window.__jetty) {
      clearInterval(wait);
      J = window.__jetty;
      dockButton(); routes();
      fetch('/api/tools').then((r) => r.json()).then((d) => {
        TILES = d; rebuildToolRoute(); dockButton();
        const b = $id('j-toolsbtn');
        if (b) { b.style.borderColor = d.connected ? 'rgba(232,182,76,.7)' : 'rgba(52,211,153,.45)';
                 b.style.boxShadow = d.connected ? '0 0 10px rgba(232,182,76,.28)' : 'none'; }
      }).catch(() => {});
    } else if (++tries > 100) clearInterval(wait);
  }, 150);
})();
