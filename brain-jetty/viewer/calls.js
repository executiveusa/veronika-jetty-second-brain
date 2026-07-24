// Jetty V6 — HANDS-FREE CALLING client. Registers voice routes in window.__jettyRoutes:
// "call Luigi's and book a table for 4 at 7 tonight" → Jetty finds the number, asks permission
// ("Shall I ring them, sir?") → "do it" → dials via Retell → a live call card shows dialing →
// ringing → on the call → ended, and Jetty speaks the outcome ("Booked, sir — 7:15, patio").
// Every real call needs an explicit "do it". Fully optional: no bridge, no effect.

const $id = (i) => document.getElementById(i);
let J = null;
let pending = null;           // {confirm_id, callee, number, need_number}
let poll = 0;

const NEVER = /$^/;
const goRoute = { re: NEVER, handler: goCall };     // "do it" dials — armed only while a call is pending confirm
const rxEsc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

function armGo(on) { goRoute.re = on ? /^(?:do it|go ahead|call them|ring them|yes,? (?:call|do it|please))[.!]?$/i : NEVER; }

function panel() {
  let el = $id('j-call');
  if (el) return el;
  el = document.createElement('div');
  el.id = 'j-call';
  el.style.cssText = 'position:fixed;right:26px;bottom:96px;width:322px;z-index:88;display:none;'
    + 'background:rgba(12,14,18,.95);border:1px solid rgba(96,200,255,.4);border-radius:16px;'
    + 'padding:15px 16px;backdrop-filter:blur(12px);font-family:-apple-system,"Segoe UI",sans-serif;'
    + 'box-shadow:0 12px 40px rgba(0,0,0,.5);';
  el.innerHTML = `<div style="display:flex;align-items:center;gap:9px;margin-bottom:10px;">
      <span id="jc-dot" style="width:9px;height:9px;border-radius:50%;background:#60c8ff;box-shadow:0 0 8px #60c8ff;"></span>
      <span style="font-family:'SF Mono',ui-monospace,monospace;font-size:11px;letter-spacing:.14em;color:#60c8ff;" id="jc-head">CALL</span>
      <button id="jc-x" style="margin-left:auto;background:rgba(251,113,133,.16);border:1px solid rgba(251,113,133,.55);color:#fb7185;border-radius:99px;font-size:11.5px;font-weight:600;padding:5px 13px;cursor:pointer;">✕</button>
    </div>
    <div id="jc-callee" style="font-size:14px;color:#eaf0ec;font-weight:600;"></div>
    <div id="jc-num" style="font-size:12px;color:#8a97a0;margin-top:1px;"></div>
    <div id="jc-body" style="font-size:12.5px;color:#c7d0d6;line-height:1.5;margin-top:9px;"></div>`;
  document.body.appendChild(el);
  el.querySelector('#jc-x').onclick = dismiss;
  return el;
}
function show() { panel().style.display = 'block'; }
function dismiss() { const el = $id('j-call'); if (el) el.style.display = 'none'; clearInterval(poll); pending = null; armGo(false); }

function setHead(txt, color) {
  const h = $id('jc-head'), d = $id('jc-dot');
  if (h) { h.textContent = txt; h.style.color = color; }
  if (d) { d.style.background = color; d.style.boxShadow = '0 0 8px ' + color; }
}

async function prepare(task) {
  show();
  setHead('FINDING…', '#60c8ff');
  $id('jc-callee').textContent = ''; $id('jc-num').textContent = '';
  $id('jc-body').textContent = 'Looking up the number, sir…';
  const r = await J.post('/calls_prepare', { task, session: J.session }, 40000);
  if (!r || r.error) { $id('jc-body').textContent = (r && r.error) || 'I could not set that up, sir.'; setHead('—', '#8a97a0'); return J.say((r && r.error) || 'I could not set that up, sir.'); }
  pending = r;
  $id('jc-callee').textContent = r.callee;
  $id('jc-num').textContent = r.pretty || '';
  if (r.need_number) {
    setHead('NEED NUMBER', '#f0b446');
    $id('jc-body').textContent = r.ask;
    return J.say(r.ask);
  }
  setHead('CONFIRM', '#f0b446');
  $id('jc-body').innerHTML = r.ask + '<div style="margin-top:8px;color:#8a97a0;font-size:11.5px;">say “do it” to ring — or “cancel”</div>';
  armGo(true);
  await J.say(r.ask);
}

async function supplyNumber(numText) {
  if (!pending || !pending.need_number) return false;
  const r = await J.post('/calls_number', { confirm_id: pending.confirm_id, number: numText }, 15000);
  if (!r || r.error) return J.say((r && r.error) || "That number won't dial, sir.");
  pending.need_number = false; pending.number = r.number;
  $id('jc-num').textContent = r.pretty || r.number;
  setHead('CONFIRM', '#f0b446');
  $id('jc-body').innerHTML = r.ask + '<div style="margin-top:8px;color:#8a97a0;font-size:11.5px;">say “do it” to ring</div>';
  armGo(true);
  await J.say(r.ask);
}

async function goCall() {
  if (!pending) return false;
  const cid = pending.confirm_id; armGo(false);
  const r = await J.post('/calls_go', { confirm_id: cid }, 20000);
  pending = null;
  if (!r || r.error) { $id('jc-body').textContent = (r && r.error) || 'The line would not connect, sir.'; setHead('FAILED', '#fb7185'); return J.say((r && r.error) || 'The line would not connect, sir.'); }
  setHead('DIALING', '#60c8ff');
  $id('jc-body').textContent = 'Ringing now, sir…';
  await J.say(r.say);
  watch(r.call_id, r.callee);
}

const STATUS_UI = {
  registered: ['DIALING', '#60c8ff', 'Connecting the call, sir…'],
  ongoing:    ['ON THE CALL', '#34d399', 'Talking to them now, sir — I\'ll report back.'],
  ended:      ['ENDED', '#8a97a0', ''],
  error:      ['ERROR', '#fb7185', ''],
  not_connected: ['NO ANSWER', '#f0b446', ''],
};

function watch(cid, callee) {
  clearInterval(poll);
  poll = setInterval(async () => {
    let d;
    try { d = await (await fetch('/api/calls?id=' + encodeURIComponent(cid))).json(); } catch (_) { return; }
    const ui = STATUS_UI[d.status] || ['…', '#60c8ff', ''];
    setHead(ui[0], ui[1]);
    if (!d.done && ui[2]) $id('jc-body').textContent = ui[2];
    if (d.done) {
      clearInterval(poll);
      const line = d.summary || (callee + ' call finished, sir.');
      $id('jc-body').innerHTML = `<span style="color:#eaf0ec;">${line}</span>`
        + (d.outcome ? `<div style="margin-top:6px;color:${ui[1]};font-size:11.5px;">${d.outcome}</div>` : '')
        + (d.recording ? `<div style="margin-top:6px;"><a href="${d.recording}" target="_blank" style="color:#60c8ff;font-size:11.5px;">▶ recording</a></div>` : '');
      J.setLastNote && J.setLastNote(line);
      await J.say(line);
      setTimeout(() => { const el = $id('j-call'); if (el && el.style.display === 'block' && !pending) { /* leave it up */ } }, 100);
    }
  }, 1500);
}

// intents
const CALL = /\b(call|ring|phone|dial|give (?:a |them a )?(?:call|ring)|get (?:me )?on the phone with)\b/i;
const STRIP = /^(?:jetty[,:\s]+)?(?:can you |could you |please |go ahead and |i (?:want|need) you to )*/i;
const OUTCOME_Q = /\b(did they (?:answer|pick up|say)|what did they say|how did (?:the|that) call go|any luck with the call)\b/i;

function routes() {
  const R = (window.__jettyRoutes = window.__jettyRoutes || []);
  R.push(
    { re: OUTCOME_Q, handler: async () => {
        let live; try { live = await (await fetch('/api/calls')).json(); } catch (_) {}
        const el = $id('j-call'), body = $id('jc-body');
        if (body && el && el.style.display === 'block') { show(); return J.say('Here on the card, sir — ' + (body.textContent || '').slice(0, 120)); }
        return J.say('No calls on the books just now, sir.');
      } },
    { re: CALL, handler: async (q) => {
        // if we're waiting for a number and they just said one, take it
        if (pending && pending.need_number) return supplyNumber(q);
        const task = q.replace(STRIP, '').trim();
        await prepare(task);
      } },
  );
  // if a number is pending, a bare number utterance supplies it
  R.unshift({ re: /^[\d\s+().-]{7,}$/, handler: async (q) => (pending && pending.need_number) ? supplyNumber(q) : false });
  R.unshift(goRoute);   // "do it" dials — outranks other bays ONLY while a call is pending (regex NEVER otherwise)
}

(function boot() {
  let n = 0;
  const w = setInterval(() => {
    if (window.__jetty) { clearInterval(w); J = window.__jetty; routes(); }
    else if (++n > 100) clearInterval(w);
  }, 150);
})();
