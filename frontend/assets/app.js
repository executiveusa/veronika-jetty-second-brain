/**
 * JETTY™ — Spiral Jetty AI Second Brain
 * Frontend Application Logic v1.4 — true 3D, streaming, voice dock, onboarding.
 * The Pauli Effect | Emerald Tablets™
 *
 * Stocks:  graph data, session history, voice selection, model selection
 * Flows:   user input → HERMES API → Claude/Groq/Mistral/OpenAI → response
 * Feedback: quality gate (UDEC 8.5), cost guard ($25/day), learning (graph grows)
 */
import * as THREE from 'three';
import ForceGraph3D from '3d-force-graph';
import SpriteText from 'three-spritetext';

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
  const host = window.location.hostname || '';
  if (host === 'localhost' || host === '127.0.0.1' || window.location.protocol === 'file:') {
    return 'http://localhost:4700';
  }
  return '';
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

function syncViewportMode() {
  const w = window.innerWidth || document.documentElement.clientWidth || 0;
  const isCoarse = window.matchMedia('(pointer: coarse)').matches;
  const isTouch = navigator.maxTouchPoints > 0 || isCoarse;
  const mode = w < 720 ? 'compact' : w < 1100 ? 'tablet' : 'desktop';
  const root = document.documentElement;
  root.dataset.viewport = mode;
  root.dataset.pointer = isTouch ? 'touch' : 'fine';
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

function formatMessageContent(text) {
  if (!text) return '';
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  html = html.replace(/\*\*([\s\S]*?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*([\s\S]*?)\*/g, '<em>$1</em>');
  html = html.replace(/\n/g, '<br>');
  return html;
}

function renderHistory() {
  const list = $('history-list');
  if (!list) return;
  const items = STATE.sessions;
  if (!items.length) {
    list.innerHTML = '<div class="history-item" style="cursor:default">No previous chats yet.<span class="history-meta">Your saved threads will appear here.</span></div>';
    return;
  }
  list.innerHTML = items.map(item => {
    const isActive = item.session_id === STATE.threadSessionId;
    return `
      <button type="button" class="history-item ${isActive ? 'active' : ''}" data-history-id="${item.session_id}">
        ${item.preview || item.title || 'Previous chat'}
        <span class="history-meta">${item.message_count || 0} messages · ${item.last_seen || ''}</span>
      </button>
    `;
  }).join('');
  list.querySelectorAll('[data-history-id]').forEach(btn => {
    btn.addEventListener('click', () => {
      const sid = btn.dataset.historyId;
      STATE.session = sid;
      STATE.threadSessionId = sid;
      sessionStorage.setItem('jetty_session', sid);
      localStorage.setItem('jetty_selected_session', sid);
      loadThread(sid);
      renderHistory();
    });
  });
}

function renderConversation() {
  const conv = $('chat-conversation');
  if (!conv) return;
  if (!STATE.thread.length) {
    conv.innerHTML = `
      <div class="chat-welcome">
        <div class="welcome-orb"></div>
        <h2>I am JETTY.</h2>
        <p>Your thinking, coiled in a 3D knowledge galaxy. Ask me about your notes, or say "remember that..." to build your second brain.</p>
      </div>
    `;
    return;
  }
  conv.innerHTML = STATE.thread.map(item => {
    const isAssistant = item.role === 'assistant';
    const contentHtml = formatMessageContent(item.content);
    return `
      <div class="message-bubble-wrapper ${isAssistant ? 'assistant-msg' : 'user-msg'}">
        <div class="message-sender">${isAssistant ? 'JETTY' : 'YOU'}</div>
        <div class="message-bubble">
          ${item.thinking ? '<div class="thinking-spinner"><span></span><span></span><span></span></div>' : contentHtml}
        </div>
      </div>
    `;
  }).join('');
  conv.scrollTop = conv.scrollHeight;
}

async function loadSessions() {
  try {
    const r = await fetch(apiUrl('/api/sessions'));
    if (!r.ok) return renderHistory();
    const j = await r.json();
    const sessions = Array.isArray(j.sessions) ? j.sessions : [];
    STATE.sessions = sessions;
    renderHistory();
    const selected = STATE.sessions.find(x => x.session_id === STATE.threadSessionId) || STATE.sessions[0];
    if (selected) await loadThread(selected.session_id);
    else renderConversation();
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
    renderConversation();
  } catch {
    STATE.thread = [];
    renderConversation();
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

// ── VOICE SETUP ───────────────────────────────────────────────────
function loadVoices() {
  const sel = $('voice-select');
  const all = speechSynthesis.getVoices();

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
  
  const ELEVENLABS_VOICES = [
    { id: "JBFqnCBsd6RMkjVDRZzb", name: "ElevenLabs: George" },
    { id: "cgSgspJ2msm6clMCkdW9", name: "ElevenLabs: Jessica" },
    { id: "EXAVITQu4vr4xnSDxMaL", name: "ElevenLabs: Bella" },
    { id: "21m00Tcm4TlvDq8ikWAM", name: "ElevenLabs: Rachel" }
  ];
  
  ELEVENLABS_VOICES.forEach(v => {
    const o = document.createElement('option');
    o.value = 'elevenlabs:' + v.id;
    o.textContent = v.name;
    if (o.value === STATE.voice) o.selected = true;
    sel.appendChild(o);
  });

  ranked.forEach(v => {
    const o = document.createElement('option');
    o.value = v.name;
    o.textContent = v.name.replace(/Google |Microsoft /, '');
    if (v.name === STATE.voice) o.selected = true;
    sel.appendChild(o);
  });
  if (!STATE.voice) STATE.voice = 'elevenlabs:' + ELEVENLABS_VOICES[0].id;
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

let currentAudio = null;

async function speak(text, force = false) {
  if (!STATE.unlocked && !force) return;
  
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  if ('speechSynthesis' in window) speechSynthesis.cancel();
  
  if (STATE.voice && STATE.voice.startsWith('elevenlabs:')) {
    const voiceId = STATE.voice.split(':')[1];
    try {
      const r = await fetch(apiUrl('/api/tts'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice_id: voiceId })
      });
      if (!r.ok) throw new Error('TTS failed');
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      currentAudio = new Audio(url);
      currentAudio.play();
    } catch (e) {
      console.error('ElevenLabs TTS error:', e);
      fallbackSpeak(text);
    }
  } else {
    fallbackSpeak(text);
  }
}

function fallbackSpeak(text) {
  if (!('speechSynthesis' in window)) return;
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
  $('knowledge-panel').classList.remove('panel-hidden');
  // 3D camera flyto — orbit in close to the node from a fixed offset
  const x = Number.isFinite(n.x) ? n.x : 0;
  const y = Number.isFinite(n.y) ? n.y : 0;
  const z = Number.isFinite(n.z) ? n.z : 0;
  const dist = 90;
  STATE.graph.cameraPosition(
    { x: x + dist * 0.6, y: y + dist * 0.45, z: z + dist },
    { x, y, z },
    1400
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
  if (ids.length < 4 && ids[0] != null) focusNode(ids[0]);
}

function labelObject(n) {
  // 3D sprite label that appears next to the node, fades at distance
  const sprite = new SpriteText(n.label);
  sprite.color = '#fff4e8';
  sprite.backgroundColor = 'rgba(15,10,18,.72)';
  sprite.padding = 3;
  sprite.borderRadius = 4;
  sprite.fontSize = 11;
  sprite.fontFace = 'JetBrains Mono, ui-monospace, monospace';
  sprite.position.y = 10;
  return sprite;
}

function addStarfield(scene) {
  if (!scene) return;
  const N = 1800;
  const geo = new THREE.BufferGeometry();
  const positions = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) {
    const r = 600 + Math.random() * 500;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    positions[i*3]   = r * Math.sin(phi) * Math.cos(theta);
    positions[i*3+1] = r * Math.sin(phi) * Math.sin(theta);
    positions[i*3+2] = r * Math.cos(phi);
  }
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const mat = new THREE.PointsMaterial({ color: 0xe04d8e, size: 1.2, transparent: true, opacity: 0.55, sizeAttenuation: false });
  scene.add(new THREE.Points(geo, mat));
}

function initGalaxy(data) {
  const elem = $('galaxy-canvas');
  STATE.graph = ForceGraph3D({ controlType: 'orbit', rendererConfig: { preserveDrawingBuffer: true, antialias: true } })(elem)
    .backgroundColor('#0f0a12')
    .graphData(data)
    .nodeId('id')
    .nodeLabel(n => `<div class="scene-tooltip">${n.label}</div>`)
    .nodeColor(n => nodeColor(n.group))
    .nodeRelSize(4)
    .nodeOpacity(0.95)
    .nodeResolution(12)
    .nodeThreeObjectExtend(true)
    .nodeThreeObject(labelObject)
    .linkColor(() => 'rgba(200,51,111,.18)')
    .linkWidth(0.7)
    .linkOpacity(0.4)
    .linkDirectionalParticles(2)
    .linkDirectionalParticleSpeed(0.0035)
    .linkDirectionalParticleWidth(1.2)
    .linkDirectionalParticleColor(() => '#c8336f')
    .onNodeClick(n => {
      STATE.unlocked = true;
      focusNode(n.id);
    })
    .enableNodeDrag(false)
    .showNavInfo(false);
  STATE.graph.d3Force('charge').strength(-130);
  STATE.graph.d3Force('link').distance(36);
  // Add the spiral-jetty starfield behind the graph
  try { addStarfield(STATE.graph.scene()); } catch (e) { /* older API */ }
  setTimeout(() => STATE.graph.zoomToFit(1400, 80), 650);
}

// ── GRAPH LOAD ────────────────────────────────────────────────────
async function loadGraph() {
  try {
    const r = await fetch(apiUrl('/api/graph'));
    if (!r.ok) throw new Error(`Server ${r.status}`);
    STATE.data = await r.json();
    const count = STATE.data.count || STATE.data.nodes.length;

    const hour = new Date().getHours();
    const salutation = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
    const bootMsg = `${salutation}. ${count} note${count !== 1 ? 's' : ''} indexed — all present and accounted for.`;

    $('panel-headline').textContent = `${count} note${count !== 1 ? 's' : ''} indexed.`;
    $('panel-subtext').textContent = 'Each star is a note. Each connection is a relationship JETTY™ found between your ideas.';

    initGalaxy(STATE.data);
    setStatus('ready');
    loadSessions();

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

  const inp = $('query-input');
  inp.value = '';
  inp.style.height = 'auto';
  $('answer-display').textContent = '';

  const identity = identityReply(text);
  if (identity) {
    STATE.thread.push({ role: 'user', content: text });
    STATE.thread.push({ role: 'assistant', content: identity });
    renderConversation();
    speak(identity);
    await loadSessions();
    setStatus('ready');
    return;
  }

  STATE.thread.push({ role: 'user', content: text });
  STATE.thread.push({ role: 'assistant', content: '', thinking: true });
  renderConversation();

  setStatus('thinking…', 'thinking');
  $('send-btn').disabled = true;
  const orbRing = $('orb')?.querySelector('.orb-ring');
  orbRing?.classList.add('listening');

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
      speak(j.answer);
      await loadSessions();
      setTimeout(() => focusNode(j.node.id), 400);
      toast('⭐ New star in your galaxy');
      setStatus('saved');
      return;
    }

    // ── STREAMING PATH (fast, tokens appear as they arrive) ──
    const assistantIdx = STATE.thread.length - 1;
    let fullAnswer = '';
    let nodes = [];
    let streamOk = false;
    try {
      const r = await fetch(apiUrl('/api/chat/stream'), {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          message: text,
          session_id: STATE.session,
          model_provider: STATE.model,
        }),
      });
      if (!r.ok || !r.body) throw new Error(`stream ${r.status}`);
      streamOk = true;
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      let firstByte = true;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const events = buf.split('\n\n');
        buf = events.pop() || '';
        for (const ev of events) {
          const m = ev.match(/^event: (\w+)\ndata: (.*)$/s);
          if (!m) continue;
          const [, type, dataStr] = m;
          let data = {};
          try { data = JSON.parse(dataStr); } catch (_) {}
          if (type === 'meta') { nodes = data.nodes || []; }
          else if (type === 'delta') {
            if (firstByte) { firstByte = false; setStatus('speaking…', 'ready'); }
            fullAnswer += data.text || '';
            STATE.thread[assistantIdx].content = fullAnswer;
            STATE.thread[assistantIdx].thinking = false;
            renderConversation();
          }
          else if (type === 'done') { fullAnswer = data.answer || fullAnswer; nodes = data.nodes || nodes; }
          else if (type === 'error') { throw new Error(data.message || 'stream error'); }
        }
      }
    } catch (streamErr) {
      // ── FALLBACK: non-streaming /api/chat ──
      if (!streamOk) {
        const r = await fetch(apiUrl('/api/chat'), {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ message: text, session_id: STATE.session, model_provider: STATE.model }),
        });
        const j = await r.json();
        if (!r.ok) throw new Error(j.detail || 'Query failed');
        fullAnswer = j.answer;
        nodes = j.nodes || [];
      } else {
        throw streamErr;
      }
    }

    STATE.thread[assistantIdx].content = fullAnswer;
    STATE.thread[assistantIdx].thinking = false;
    renderConversation();
    if (fullAnswer) speak(fullAnswer);
    await loadSessions();
    if (nodes.length) lightCluster(nodes);
    setStatus('ready');

  } catch(e) {
    if (STATE.thread.length && STATE.thread[STATE.thread.length - 1].thinking) {
      STATE.thread.pop();
    }
    STATE.thread.push({ role: 'assistant', content: `Error: ${e.message}` });
    renderConversation();
    setStatus('error', 'error');
  } finally {
    $('send-btn').disabled = false;
    $('orb')?.querySelector('.orb-ring')?.classList.remove('listening');
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
  rec.onerror  = e => {
    $('mic-btn').classList.remove('listening');
    let msg = 'Microphone error.';
    if (e.error === 'not-allowed') {
      msg = 'Microphone permission denied. Please check your browser settings.';
    } else if (e.error === 'no-speech') {
      msg = 'No speech detected. Please try speaking again.';
    } else if (e.error === 'audio-capture') {
      msg = 'Microphone hardware not found. Please connect a mic.';
    } else if (e.error === 'network') {
      msg = 'Network error occurred during speech recognition.';
    }
    setStatus('mic error', 'error');
    $('answer-display').textContent = msg;
    toast(msg);
  };
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
  renderConversation();
  $('query-input').value = '';
  $('query-input').style.height = 'auto';
  $('answer-display').textContent = '';
  toast('New chat ready');
  renderHistory();
};
$('clear-history-btn').onclick = () => {
  localStorage.removeItem('jetty_selected_session');
  STATE.sessions = [];
  STATE.thread = [];
  renderHistory();
  renderConversation();
  toast('History cleared from view');
};
$('query-input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(); }
});
$('query-input').addEventListener('input', function() {
  this.style.height = 'auto';
  this.style.height = (this.scrollHeight) + 'px';
});

// Sidebar toggle listeners
$('toggle-sessions-btn').onclick = () => {
  $('sessions-sidebar').classList.toggle('sidebar-hidden');
};
$('toggle-knowledge-btn').onclick = () => {
  $('knowledge-panel').classList.toggle('panel-hidden');
};

document.body.addEventListener('click', () => { STATE.unlocked = true; }, { once: true });

window.addEventListener('resize', syncViewportMode, { passive: true });
window.addEventListener('orientationchange', syncViewportMode, { passive: true });

// ── VOICE DOCK: reactor orb + wake word + live + screen + briefing ───────────
const WAKE_RE = /\b(?:hey |okay |ok )?(?:jetty|jeti|jetti)(?:\s+a\.?\s?i\.?)?\b[\s,.]*(.*)$/i;
const STRIP_WAKE = /^\s*(?:hey |okay |ok )?(?:jetty|jeti|jetti)(?:\s+a\.?\s?i\.?)?[\s,.]*/i;
const SHORT_CMD = /^(stop|wait|hold on|never mind|thanks|thank you|nothing|cancel)\b/i;
let wakeOn = false, wakeRec = null, micActive = false, awaitingCmd = false, orbThink = false, orbSpeak = false;
let wakeTimer = null, followupTimer = null;

function renderOrb() {
  const orb = $('j-orb');
  if (!orb) return;
  const s = orbSpeak ? 'speak' : orbThink ? 'think' : (wakeOn || micActive || awaitingCmd) ? 'listen' : 'idle';
  orb.className = 'is-' + s;
  const lbl = $('j-state-txt');
  if (lbl) {
    const labels = { speak: 'SPEAKING', think: 'THINKING', listen: 'LISTENING', idle: 'ONLINE' };
    lbl.textContent = labels[s];
  }
}

// Wake word toggle
function toggleWake() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const btn = $('j-wake');
  if (!SR) { toast('Hands-free needs Chrome or Edge'); return; }
  wakeOn = !wakeOn;
  renderOrb();
  if (!btn) return;
  if (wakeOn) {
    btn.classList.add('dock-active');
    wakeRec = new SR();
    wakeRec.lang = 'en-US';
    wakeRec.continuous = true;
    wakeRec.interimResults = true;
    wakeRec.maxAlternatives = 1;
    wakeRec.onstart = () => { };
    wakeRec.onresult = e => {
      const res = e.results[e.results.length - 1];
      const txt = (res[0].transcript || '').trim();
      const fin = !!res.isFinal;
      if (!fin) return;
      const words = txt.split(/\s+/).filter(w => w.length > 1).length;
      if (awaitingCmd) {
        if (words < 2 && !SHORT_CMD.test(txt) && !WAKE_RE.test(txt)) return;
        awaitingCmd = false;
        clearTimeout(wakeTimer);
        const cmd = txt.replace(STRIP_WAKE, '').trim();
        if (cmd) ask(cmd);
        return;
      }
      const m = txt.match(WAKE_RE);
      if (!m) return;
      const cmd = (m[1] || '').trim();
      if (cmd) ask(cmd);
      else { armCmd(); speak('Yes?'); }
    };
    wakeRec.onerror = e => {
      if (e.error === 'not-allowed') { toast('Mic blocked — allow it in Chrome'); wakeOn = false; renderOrb(); }
    };
    wakeRec.onend = () => { if (wakeOn && !micActive) { try { wakeRec.start(); } catch (_) { } } };
    try { wakeRec.start(); speak("Hands-free engaged. Say \"Jetty\" and I'll answer."); } catch (_) { }
  } else {
    btn.classList.remove('dock-active');
    if (wakeRec) { try { wakeRec.stop(); } catch (_) { } }
  }
}

function armCmd() {
  awaitingCmd = true;
  renderOrb();
  clearTimeout(wakeTimer);
  wakeTimer = setTimeout(() => { awaitingCmd = false; renderOrb(); }, 8000);
}

// Live duplex (silent fallback to push-to-talk)
async function toggleLive() {
  const btn = $('j-live');
  if (!btn) return;
  try {
    const st = await fetch(apiUrl('/api/duplex')).then(r => r.json()).catch(() => ({}));
    if (!st.configured) {
      // Silent fallback: behave like wake word
      toast('Live voice needs a key — using push-to-talk instead');
      if (!wakeOn) toggleWake();
      return;
    }
    const s = await fetch(apiUrl('/api/duplex_signed')).then(r => r.json()).catch(() => ({}));
    if (s.signed_url) {
      window.open(s.signed_url, '_blank');
    } else {
      if (!wakeOn) toggleWake();
    }
  } catch (_) {
    if (!wakeOn) toggleWake();
  }
}

// Screen vision
let screenStream = null;
async function toggleScreen() {
  const btn = $('j-screen');
  if (!btn) return;
  if (screenStream) {
    screenStream.getTracks().forEach(t => t.stop());
    screenStream = null;
    btn.classList.remove('dock-active');
    toast('Screen share stopped');
    return;
  }
  try {
    screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
    btn.classList.add('dock-active');
    toast('Sharing screen — ask "what am I looking at?"');
    screenStream.getVideoTracks()[0].onended = () => {
      screenStream = null;
      btn.classList.remove('dock-active');
    };
  } catch (_) {
    // silent
  }
}

async function seeScreen(question = 'What am I looking at? Briefly.') {
  if (!screenStream) return '';
  const track = screenStream.getVideoTracks()[0];
  const capture = new ImageCapture(track);
  try {
    const bitmap = await capture.grabFrame();
    const canvas = document.createElement('canvas');
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    canvas.getContext('2d').drawImage(bitmap, 0, 0);
    const dataUrl = canvas.toDataURL('image/jpeg', 0.7);
    const r = await fetch(apiUrl('/api/see'), {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ image: dataUrl, question })
    });
    const j = await r.json();
    return j.answer || '';
  } catch (_) {
    return '';
  }
}

// Morning briefing
async function runBriefing() {
  const btn = $('j-bell');
  if (btn) btn.classList.add('dock-active');
  orbThink = true; renderOrb();
  setStatus('gathering your day…', 'thinking');
  try {
    const r = await fetch(apiUrl('/api/briefing'), { method: 'POST' });
    const j = await r.json();
    if (j.answer) {
      STATE.thread.push({ role: 'assistant', content: j.answer });
      renderConversation();
      speak(j.answer);
    }
  } catch (_) { /* silent */ }
  finally {
    orbThink = false; renderOrb();
    if (btn) btn.classList.remove('dock-active');
    setStatus('ready');
  }
}

// Wire dock buttons (deferred so DOM is ready)
function wireDock() {
  const mic = $('j-mic'), wake = $('j-wake'), live = $('j-live'), screen = $('j-screen'), bell = $('j-bell');
  if (mic) mic.onclick = () => { STATE.unlocked = true; micActive = true; renderOrb(); $('mic-btn')?.click(); setTimeout(() => { micActive = false; renderOrb(); }, 2000); };
  if (wake) wake.onclick = toggleWake;
  if (live) live.onclick = toggleLive;
  if (screen) screen.onclick = toggleScreen;
  if (bell) bell.onclick = runBriefing;
  // Screen-vision intent: "what am I looking at" routes to /api/see
  const origAsk = ask;
  window.ask = async function(text) {
    if (screenStream && /\b(looking at|see|on my screen|what.*screen|describe.*screen|read.*screen)\b/i.test(text)) {
      const ans = await seeScreen(text);
      if (ans) {
        STATE.thread.push({ role: 'user', content: text });
        STATE.thread.push({ role: 'assistant', content: ans });
        renderConversation();
        speak(ans);
        return;
      }
    }
    return origAsk(text);
  };
  renderOrb();
}

// Load ElevenLabs voices into the dropdown alongside browser voices
async function loadElevenVoices() {
  try {
    const st = await fetch(apiUrl('/api/voice')).then(r => r.json());
    if (st.configured && st.voices?.length) {
      const sel = $('voice-select');
      if (!sel) return;
      const eg = document.createElement('optgroup');
      eg.label = '★ Premium voices (ElevenLabs)';
      st.voices.forEach(v => {
        const o = document.createElement('option');
        o.value = 'elevenlabs:' + v.id;
        o.textContent = v.name + (v.category ? ' · ' + v.category : '');
        eg.appendChild(o);
      });
      sel.appendChild(eg);
      if (st.active && !STATE.voice) {
        sel.value = 'elevenlabs:' + st.active;
        STATE.voice = 'elevenlabs:' + st.active;
        localStorage.setItem('jetty_voice', STATE.voice);
      }
    }
  } catch (_) { /* silent */ }
}

async function boot() {
  syncViewportMode();
  await syncPreferredModel();
  await loadGraph();
  wireDock();
  await loadElevenVoices();
}

boot();
