/**
 * JETTY™ — Spiral Jetty AI Second Brain
 * Frontend Application Logic
 * Kupuri Media™ × Akash Engine | Emerald Tablets™
 *
 * Stocks:  graph data, session history, voice selection, model selection
 * Flows:   user input → HERMES API → Claude/Groq/Mistral/OpenAI → response
 * Feedback: quality gate (UDEC 8.5), cost guard ($25/day), learning (graph grows)
 */

const STATE = {
  graph:    null,
  data:     null,
  session:  sessionStorage.getItem('jetty_session') || crypto.randomUUID(),
  model:    localStorage.getItem('jetty_model')  || 'anthropic',
  voice:    localStorage.getItem('jetty_voice')  || null,
  unlocked: false,
};
sessionStorage.setItem('jetty_session', STATE.session);

const $ = id => document.getElementById(id);

// ── STATUS ────────────────────────────────────────────────────────
function setStatus(text, mode = 'ready') {
  $('status-text').textContent = text;
  const dot = $('status-dot');
  dot.className = 'status-indicator';
  if (mode !== 'ready') dot.classList.add(mode);
}

function toast(msg, ms = 2600) {
  const t = $('toast-msg');
  t.textContent = msg;
  t.classList.add('visible');
  setTimeout(() => t.classList.remove('visible'), ms);
}

// ── VOICE SETUP ───────────────────────────────────────────────────
function loadVoices() {
  const sel = $('voice-select');
  const all = speechSynthesis.getVoices();
  if (!all.length) return;

  const preferred = ['Samantha', 'Victoria', 'Karen', 'Zoe',
                     'Google US English', 'Microsoft Zira'];
  const ranked = [...all].sort((a, b) => {
    const ai = preferred.findIndex(p => a.name.includes(p));
    const bi = preferred.findIndex(p => b.name.includes(p));
    if (ai !== -1 && bi === -1) return -1;
    if (bi !== -1 && ai === -1) return 1;
    if (a.lang.startsWith('en') && !b.lang.startsWith('en')) return -1;
    if (b.lang.startsWith('en') && !a.lang.startsWith('en')) return 1;
    return 0;
  });

  sel.innerHTML = '';
  ranked.forEach(v => {
    const o = document.createElement('option');
    o.value = v.name;
    o.textContent = v.name.replace(/Google |Microsoft /, '');
    if (v.name === STATE.voice) o.selected = true;
    sel.appendChild(o);
  });
  if (!STATE.voice) STATE.voice = ranked[0]?.name;
}

$('voice-select').addEventListener('change', function () {
  STATE.voice = this.value;
  localStorage.setItem('jetty_voice', STATE.voice);
  speak('Voice updated.', true);
});

$('model-select').value = STATE.model;
$('model-select').addEventListener('change', function () {
  STATE.model = this.value;
  localStorage.setItem('jetty_model', STATE.model);
  const names = {
    anthropic: 'Claude',
    openai:    'GPT-4o',
    groq:      'Groq (free)',
    mistral:   'Mistral (free)',
  };
  toast(`Brain: ${names[STATE.model]}`);
});

function speak(text, force = false) {
  if (!('speechSynthesis' in window)) return;
  if (!STATE.unlocked && !force) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  const voices = speechSynthesis.getVoices();
  u.voice = voices.find(v => v.name === STATE.voice)
         || voices.find(v => /Samantha|Victoria|Google US/i.test(v.name))
         || voices.find(v => v.lang.startsWith('en'))
         || voices[0];
  u.rate  = 0.96;
  u.pitch = 1.0;
  speechSynthesis.speak(u);
}

if ('speechSynthesis' in window) {
  speechSynthesis.getVoices();
  speechSynthesis.onvoiceschanged = loadVoices;
  setTimeout(loadVoices, 300);
}

// ── GALAXY HELPERS ────────────────────────────────────────────────
const NODE_COLORS = {
  'job-search':   '#d4a030',   // alpenglow gold
  'silicon-slopes':'#3092cc',  // lake blue
  'contacts':     '#3092cc',
  'ai-tools':     '#e04d8e',
  'captures':     '#c8336f',
  'ideas':        '#4d9050',   // sage green
  'Root':         '#f07aab',   // soft pink
};

function nodeColor(group) {
  const key = Object.keys(NODE_COLORS).find(k =>
    group.toLowerCase().includes(k.toLowerCase()));
  if (key) return NODE_COLORS[key];
  let h = 0;
  for (const c of group) h = (h * 31 + c.charCodeAt(0)) % 360;
  return `hsl(${h},70%,62%)`;
}

function neighbors(id) {
  const set = new Set([id]);
  (STATE.data.links || []).forEach(l => {
    const s = typeof l.source === 'object' ? l.source.id : l.source;
    const t = typeof l.target === 'object' ? l.target.id : l.target;
    if (s === id) set.add(t);
    if (t === id) set.add(s);
  });
  return set;
}

function showSource(n) {
  $('source-view').innerHTML = `
    <h2>${n.label}</h2>
    <code>${n.path}</code>
    <p style="font-size:13px;color:rgba(254,254,254,.55);line-height:1.6">
      ${n.excerpt || ''}
    </p>`;
}

function focusNode(id) {
  const n = STATE.data.nodes.find(x => x.id === id);
  if (!n) return;
  showSource(n);
  const dist = 90;
  const len = Math.hypot(n.x || 1, n.y || 1, n.z || 1) || 1;
  STATE.graph.cameraPosition(
    { x: (n.x||1)/len*dist, y: (n.y||1)/len*dist, z: (n.z||1)/len*dist },
    n, 1400
  );
  const hood = neighbors(id);
  STATE.graph
    .nodeColor(node => hood.has(node.id) ? '#c8336f' : nodeColor(node.group))
    .nodeRelSize(node => hood.has(node.id) ? 9 : 4);
}

function lightCluster(ids) {
  const set = new Set(ids);
  STATE.graph
    .nodeColor(n => set.has(n.id) ? '#d4a030' : nodeColor(n.group))
    .nodeRelSize(n => set.has(n.id) ? 9 : 4);
  // Prompt 4 spec: fly to top node when < 4 sources; light whole cluster when 4+
  if (ids.length < 4 && ids[0] != null) focusNode(ids[0]);
}

function initGalaxy(data) {
  const elem = $('galaxy-canvas');
  STATE.graph = ForceGraph3D()(elem)
    .backgroundColor('#0f0a12')
    .graphData(data)
    .nodeId('id')
    .nodeLabel(n => `<div class="scene-tooltip">${n.label}</div>`)
    .nodeColor(n => nodeColor(n.group))
    .nodeRelSize(4)
    .nodeOpacity(.92)
    .linkColor(() => 'rgba(200,51,111,.18)')
    .linkOpacity(.5)
    .linkWidth(0.7)
    .onNodeClick(n => {
      STATE.unlocked = true;
      focusNode(n.id);
    })
    .enableNodeDrag(false);
  STATE.graph.d3Force('charge').strength(-100);
  setTimeout(() => STATE.graph.zoomToFit(1400, 80), 650);
}

// ── GRAPH LOAD ────────────────────────────────────────────────────
async function loadGraph() {
  try {
    const r = await fetch('/api/graph');
    if (!r.ok) throw new Error(`Server ${r.status}`);
    STATE.data = await r.json();
    const count = STATE.data.count || STATE.data.nodes.length;

    // Boot greeting — spoken after first interaction unlocks audio
    const hour = new Date().getHours();
    const salutation = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
    const bootMsg = `${salutation}. ${count} note${count !== 1 ? 's' : ''} indexed — all present and accounted for.`;

    $('panel-headline').textContent = `${count} note${count !== 1 ? 's' : ''} indexed.`;
    $('panel-subtext').textContent = 'Each star is a note. Each connection is a relationship JETTY™ found between your ideas.';

    initGalaxy(STATE.data);
    setStatus('ready');

    // Speak boot greeting on first user interaction (browser audio gate)
    const greet = () => { speak(bootMsg, true); document.removeEventListener('click', greet); };
    document.addEventListener('click', greet);

  } catch(e) {
    $('panel-headline').textContent = 'Could not load your vault.';
    $('panel-subtext').textContent = e.message;
    setStatus('error', 'error');
  }
}

// ── CHAT ──────────────────────────────────────────────────────────
async function ask(text) {
  text = (text || $('query-input').value).trim();
  if (!text) return;
  STATE.unlocked = true;

  $('query-input').value = '';
  $('answer-display').textContent = '';
  setStatus('thinking…', 'thinking');
  $('send-btn').disabled = true;
  $('orb').querySelector('.orb-ring').classList.add('listening');

  try {
    const isRemember = /^remember that/i.test(text);

    if (isRemember) {
      const r = await fetch('/api/remember', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ text, session_id: STATE.session }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || 'Save failed');
      STATE.data = j.graph;
      STATE.graph.graphData(STATE.data);
      $('answer-display').textContent = j.answer;
      speak(j.answer);
      setTimeout(() => focusNode(j.node.id), 400);
      toast('⭐ New star in your galaxy');
      setStatus('saved');
      return;
    }

    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        message: text,
        session_id: STATE.session,
        model_provider: STATE.model,
      }),
    });
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || 'Query failed');
    $('answer-display').textContent = j.answer;
    speak(j.answer);
    if (j.nodes?.length) lightCluster(j.nodes);
    setStatus('ready');

  } catch(e) {
    $('answer-display').textContent = e.message;
    setStatus('error', 'error');
  } finally {
    $('send-btn').disabled = false;
    $('orb').querySelector('.orb-ring').classList.remove('listening');
  }
}

// ── VOICE INPUT ───────────────────────────────────────────────────
$('mic-btn').onclick = () => {
  STATE.unlocked = true;
  const Rec = window.webkitSpeechRecognition || window.SpeechRecognition;
  if (!Rec) {
    $('answer-display').textContent = 'Voice input needs Chrome or Edge.';
    return;
  }
  const rec = new Rec();
  rec.lang = 'en-US';
  rec.interimResults = false;
  rec.onstart  = () => { setStatus('listening…', 'thinking'); $('mic-btn').classList.add('listening'); };
  rec.onerror  = () => { setStatus('mic error', 'error');     $('mic-btn').classList.remove('listening'); };
  rec.onresult = e => { $('mic-btn').classList.remove('listening'); ask(e.results[0][0].transcript); };
  rec.onend    = () => { $('mic-btn').classList.remove('listening'); };
  rec.start();
};

// ── EVENT WIRING ──────────────────────────────────────────────────
$('send-btn').onclick = () => ask();
$('query-input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(); }
});
document.body.addEventListener('click', () => { STATE.unlocked = true; }, { once: true });

loadGraph();
