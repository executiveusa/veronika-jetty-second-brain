/**
 * JETTY™ — Spiral Jetty AI Second Brain
 * Frontend Application Logic
 * The Pauli Effect | Emerald Tablets™
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
  sessions: [],
  thread:   [],
  threadSessionId: localStorage.getItem('jetty_selected_session') || sessionStorage.getItem('jetty_session') || crypto.randomUUID(),
};
sessionStorage.setItem('jetty_session', STATE.session);

const $ = id => document.getElementById(id);

function apiBase() {
  const cfg = window.JETTY_CONFIG?.apiBaseUrl || localStorage.getItem('jetty_api_base') || '';
  if (cfg) return cfg.replace(/\/+$/, '');
  return `${window.location.protocol}//${window.location.hostname}:4700`;
}

function apiUrl(path) {
  const base = apiBase();
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  if (!base) return cleanPath;
  if (/^https?:\/\//i.test(base)) return `${base}${cleanPath}`;
  if (base.startsWith('/')) {
    return cleanPath.startsWith(base) ? cleanPath : `${base}${cleanPath}`;
  }
  return `${base}${cleanPath}`;
}

async function syncPreferredModel() {
  try {
    const r = await fetch(apiUrl('/api/health'));
    if (!r.ok) return;
    const j = await r.json();
    const available = j.providers || {};
    const saved = STATE.model;
    if (saved && available[saved]) {
      $('model-select').value = saved;
      return;
    }
    const preferred = ['anthropic', 'groq', 'deepseek', 'openai', 'synthia', 'mistral', 'hermes']
      .find(name => available[name]);
    if (preferred) {
      STATE.model = preferred;
      localStorage.setItem('jetty_model', STATE.model);
      $('model-select').value = STATE.model;
    }
  } catch {
    // Keep the saved provider if the health check is unavailable.
  }
}

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

function saveHistory() {
  localStorage.setItem('jetty_selected_session', STATE.threadSessionId);
}

function renderHistory() {
  const list = $('history-list');
  if (!list) return;
  const items = STATE.sessions;
  if (!items.length) {
    list.innerHTML = '<div class="history-item" style="cursor:default">No previous chats yet.<span class="history-meta">Your saved threads will appear here.</span></div>';
    return;
  }
  list.innerHTML = items.map(item => `
    <button type="button" class="history-item" data-history-id="${item.id}">
      ${item.preview || item.title || 'Previous chat'}
      <span class="history-meta">${item.message_count || 0} messages · ${item.last_seen || ''}</span>
    </button>
  `).join('');
  list.querySelectorAll('[data-history-id]').forEach(btn => {
    btn.addEventListener('click', () => {
      const hit = STATE.sessions.find(entry => entry.id === btn.dataset.historyId);
      if (!hit) return;
      STATE.session = hit.session_id;
      STATE.threadSessionId = hit.session_id;
      sessionStorage.setItem('jetty_session', hit.session_id);
      localStorage.setItem('jetty_selected_session', hit.session_id);
      loadThread(hit.session_id);
    });
  });
}

function renderThread() {
  const thread = $('history-thread');
  if (!thread) return;
  if (!STATE.thread.length) {
    thread.innerHTML = '<div class="history-thread-item">Open a previous chat to see the messages here.</div>';
    return;
  }
  thread.innerHTML = STATE.thread.map(item => `
    <div class="history-thread-item">
      <strong>${item.role === 'assistant' ? 'Jetty' : 'You'}</strong>
      ${item.content}
    </div>
  `).join('');
}

async function loadSessions() {
  try {
    const r = await fetch(apiUrl('/api/sessions'));
    if (!r.ok) return renderHistory();
    const j = await r.json();
    const sessions = Array.isArray(j.sessions) ? j.sessions : [];
    STATE.sessions = sessions.map((item, idx) => ({ ...item, id: `${item.session_id}:${idx}` }));
    renderHistory();
    const selected = STATE.sessions.find(x => x.session_id === STATE.threadSessionId) || STATE.sessions[0];
    if (selected) await loadThread(selected.session_id);
    else renderThread();
  } catch {
    renderHistory();
  }
}

async function loadThread(sessionId) {
  try {
    const r = await fetch(apiUrl(`/api/history?session_id=${encodeURIComponent(sessionId)}`));
    if (!r.ok) throw new Error('History unavailable');
    const j = await r.json();
    STATE.thread = Array.isArray(j.turns) ? j.turns : [];
    STATE.threadSessionId = j.session_id || sessionId;
    sessionStorage.setItem('jetty_session', STATE.threadSessionId);
    localStorage.setItem('jetty_selected_session', STATE.threadSessionId);
    renderThread();
    const lastUser = [...STATE.thread].reverse().find(item => item.role === 'user');
    const lastAssistant = [...STATE.thread].reverse().find(item => item.role === 'assistant');
    if (lastUser) $('query-input').value = lastUser.content;
    if (lastAssistant) $('answer-display').textContent = lastAssistant.content;
  } catch {
    STATE.thread = [];
    renderThread();
  }
}

function identityReply(text) {
  const normalized = text.trim().toLowerCase();
  if (!normalized) return null;
  const asksWhoBuilt =
    /^(who built you|who made you|who created you|who is behind this|who made this|who built this|who built jetty|who made jetty|who created jetty)\??$/.test(normalized) ||
    /\b(who|what team)\b.*\b(built|made|created|behind)\b/.test(normalized);
  if (!asksWhoBuilt) return null;
  return 'The team at The Pauli Effect built me, a faceless group of volunteers building AI-powered solutions to promote human well being and inclusion.';
}

function rememberChat(user, assistant, kind = 'chat') {
  addHistoryEntry(user, assistant, kind);
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
    openai:    'ChatGPT / OpenAI',
    synthia:   'ChatGPT via Synthia',
    groq:      'Groq (free)',
    deepseek:  'DeepSeek',
    mistral:   'Mistral (free)',
    hermes:    'Hermes',
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
  const x = Number.isFinite(n.x) ? n.x : 0;
  const y = Number.isFinite(n.y) ? n.y : 0;
  STATE.graph.centerAt(x, y, 900);
  STATE.graph.zoom(4, 900);
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
  STATE.graph = ForceGraph()(elem)
    .backgroundColor('#0f0a12')
    .graphData(data)
    .nodeId('id')
    .nodeLabel(n => `<div class="scene-tooltip">${n.label}</div>`)
    .nodeColor(n => nodeColor(n.group))
    .nodeRelSize(4)
    .linkColor(() => 'rgba(200,51,111,.18)')
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
    const r = await fetch(apiUrl('/api/graph'));
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
    loadSessions();

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

  const identity = identityReply(text);
  if (identity) {
    $('query-input').value = '';
    $('answer-display').textContent = identity;
    speak(identity);
    await loadSessions();
    setStatus('ready');
    return;
  }

  $('query-input').value = '';
  $('answer-display').textContent = '';
  setStatus('thinking…', 'thinking');
  $('send-btn').disabled = true;
  $('orb').querySelector('.orb-ring').classList.add('listening');

  try {
    const isRemember = /^remember that/i.test(text);

    if (isRemember) {
      const r = await fetch(apiUrl('/api/remember'), {
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
      await loadSessions();
      setTimeout(() => focusNode(j.node.id), 400);
      toast('⭐ New star in your galaxy');
      setStatus('saved');
      return;
    }

    const r = await fetch(apiUrl('/api/chat'), {
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
    await loadSessions();
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
$('new-chat-btn').onclick = () => {
  STATE.session = crypto.randomUUID();
  STATE.threadSessionId = STATE.session;
  sessionStorage.setItem('jetty_session', STATE.session);
  localStorage.setItem('jetty_selected_session', STATE.session);
  STATE.thread = [];
  renderThread();
  $('query-input').value = '';
  $('answer-display').textContent = '';
  toast('New chat ready');
};
$('clear-history-btn').onclick = () => {
  localStorage.removeItem('jetty_selected_session');
  STATE.sessions = [];
  STATE.thread = [];
  renderHistory();
  renderThread();
  toast('History cleared from view');
};
$('query-input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(); }
});
document.body.addEventListener('click', () => { STATE.unlocked = true; }, { once: true });

async function boot() {
  await syncPreferredModel();
  await loadGraph();
}

boot();
