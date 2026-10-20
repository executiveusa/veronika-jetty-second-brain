(() => {
  const hero = document.querySelector('.hero');
  const canvas = document.getElementById('wave-canvas');
  const ctx = canvas.getContext('2d');

  const state = {
    dpr: Math.min(window.devicePixelRatio || 1, 2),
    w: 0, h: 0,
    reduced: matchMedia('(prefers-reduced-motion: reduce)').matches,
    pointer: { x: -9999, y: -9999 }, ripples: [], rafId: 0
  };

  function syncViewportMode() {
    const w = window.innerWidth || document.documentElement.clientWidth || 0;
    const isTouch = window.matchMedia('(pointer: coarse)').matches || navigator.maxTouchPoints > 0;
    document.documentElement.dataset.viewport = w < 700 ? 'compact' : w < 1100 ? 'tablet' : 'desktop';
    document.documentElement.dataset.pointer = isTouch ? 'touch' : 'fine';
  }

  function resize() {
    const heroRect = hero.getBoundingClientRect();
    state.w = innerWidth;
    state.h = Math.max(innerHeight, Math.ceil(heroRect.height || innerHeight));
    state.dpr = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.floor(state.w * state.dpr);
    canvas.height = Math.floor(state.h * state.dpr);
    canvas.style.width = state.w + 'px'; canvas.style.height = state.h + 'px';
    if (ctx) ctx.setTransform(state.dpr, 0, 0, state.dpr, 0, 0);
    syncViewportMode();
  }
  addEventListener('resize', resize, { passive: true });

  // Animated water (WebGL), inspired by the earendil-works/waves ocean shader
  // (https://github.com/earendil-works/waves, Apache-2.0). The hero photo is
  // refracted by travelling wave trains below the waterline, so the waves
  // visibly move without depending on video autoplay. Canvas 2D handles GPU
  // failures. Reduced motion uses gentle waves; the visitor can pause at any time.
  let glCanvas = document.getElementById('wave-gl');
  const motionPreference = matchMedia('(prefers-reduced-motion: reduce)');
  const params = new URLSearchParams(location.search);
  let choice = null;
  try { choice = localStorage.getItem('jetty-waves'); } catch {}
  let paused = choice === 'paused';
  let water = null;
  const diagnostics = { build: 'waves-v3', path: 'still', reason: 'loading', frames: 0 };
  const waveToggle = document.getElementById('wave-toggle');
  const debug = document.getElementById('wave-debug');
  function reportWater(path, reason) {
    Object.assign(diagnostics, { path, reason });
    hero.dataset.waves = path;
    if (debug && params.get('waves') === 'debug') {
      debug.hidden = false;
      debug.textContent = `${diagnostics.build} | ${path} | reduced:${state.reduced} | ${reason} | frames:${diagnostics.frames}`;
    }
  }
  function syncControl() {
    waveToggle.textContent = paused ? 'Play waves' : 'Pause waves';
    waveToggle.setAttribute('aria-pressed', String(!paused));
    hero.classList.toggle('waves-paused', paused);
    reportWater(paused ? 'still' : diagnostics.path, paused ? 'paused by preference' : diagnostics.reason);
  }
  waveToggle.addEventListener('click', () => {
    paused = !paused;
    try { localStorage.setItem('jetty-waves', paused ? 'paused' : 'playing'); } catch {}
    syncControl();
    if (!paused && !water) startWater();
    else if (!paused) water.kick();
    else if (water) { cancelAnimationFrame(water.rafId); water.rafId = 0; }
  });
  motionPreference.addEventListener('change', event => {
    state.reduced = event.matches;
    let saved; try { saved = localStorage.getItem('jetty-waves'); } catch {}
    // A visitor's explicit Pause choice persists; preference changes only
    // adjust wave speed/amplitude, never restart a paused animation.
    syncControl();
  });


  const WATER_VERT = `
attribute vec2 aPos;
varying vec2 vUv;
void main(){ vUv = vec2(aPos.x*0.5+0.5, 0.5-aPos.y*0.5); gl_Position = vec4(aPos,0.0,1.0); }
`;

  const WATER_FRAG = `
precision mediump float;
varying vec2 vUv;
uniform sampler2D uTex;
uniform float uTime;
uniform vec2 uRes;
uniform vec2 uImg;
uniform float uFocusY;
uniform float uWaterLine;
uniform float uGentle;

float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453123); }
float noise(vec2 p){
  vec2 i=floor(p), f=fract(p);
  vec2 u=f*f*(3.0-2.0*f);
  return mix(mix(hash(i),hash(i+vec2(1.,0.)),u.x), mix(hash(i+vec2(0.,1.)),hash(i+vec2(1.,1.)),u.x), u.y);
}
float fbm(vec2 p){
  float v=0.0,a=0.5;
  for(int i=0;i<3;i++){ v+=a*noise(p); p=p*2.03+vec2(17.3,9.1); a*=0.5; }
  return v;
}
void main(){
  float ca = uRes.x/uRes.y;
  float ia = uImg.x/uImg.y;
  vec2 s = vec2(1.0);
  if (ca > ia) { s.y = ia/ca; } else { s.x = ca/ia; }
  vec2 uv = (vUv - vec2(0.5, uFocusY)) * s + vec2(0.5, uFocusY);

  float t = uTime * mix(1.0, 0.22, uGentle);
  float water = smoothstep(uWaterLine - 0.015, uWaterLine + 0.05, vUv.y);
  float depth = smoothstep(uWaterLine, 1.0, vUv.y);

  // travelling wave trains + slow fbm swell (screen space)
  float w1 = sin(vUv.x*34.0 + vUv.y*22.0 + t*1.7);
  float w2 = sin(vUv.x*61.0 - vUv.y*31.0 + t*2.4);
  float w3 = sin(vUv.y*95.0 + t*3.2 + sin(vUv.x*18.0 + t*0.9));
  float swell = fbm(vUv*vec2(6.0,10.0) + vec2(t*0.12, -t*0.09));

  vec2 duv = vec2(w1*0.55 + w2*0.45 + (swell-0.5)*1.4,
                  w3*0.45 + (swell-0.5)*1.2)
             * water * (0.0028 + 0.0062*depth) * mix(1.0, 0.25, uGentle);
  vec3 col = texture2D(uTex, uv + duv).rgb;

  // sun glitter: fine moving warm streaks on the swell
  float streak = pow(0.5 + 0.5*sin(vUv.x*260.0 + swell*36.0 + t*2.2), 6.0);
  float sparkleMask = water * smoothstep(0.0, 0.25, depth) * (1.0 - smoothstep(0.75, 1.0, depth));
  float pulse = 0.6 + 0.4*sin(t*0.8 + vUv.x*9.0);
  col += vec3(1.0, 0.72, 0.42) * streak * sparkleMask * pulse * 0.22 * (1.0 - uGentle);

  // gentle breathing light on the swell
  col *= 1.0 + water * mix(0.06, 0.01, uGentle) * sin(t*1.1 + vUv.y*38.0 + vUv.x*14.0);

  gl_FragColor = vec4(col, 1.0);
}
`;

  function initWater() {
    if (!glCanvas) return null;
    const gl = glCanvas.getContext('webgl', { alpha:false, antialias:false, depth:false, stencil:false, powerPreference:'low-power' });
    if (!gl) return null;

    function compile(type, src) {
      const sh = gl.createShader(type);
      gl.shaderSource(sh, src); gl.compileShader(sh);
      if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
        console.warn('water shader:', gl.getShaderInfoLog(sh));
        return null;
      }
      return sh;
    }
    const vs = compile(gl.VERTEX_SHADER, WATER_VERT);
    const fs = compile(gl.FRAGMENT_SHADER, WATER_FRAG);
    if (!vs || !fs) return null;
    const prog = gl.createProgram();
    gl.attachShader(prog, vs); gl.attachShader(prog, fs); gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return null;
    gl.useProgram(prog);

    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 3,-1, -1,3]), gl.STATIC_DRAW);
    const aPos = gl.getAttribLocation(prog, 'aPos');
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);

    const U = {};
    for (const n of ['uTex','uTime','uRes','uImg','uFocusY','uWaterLine','uGentle']) U[n] = gl.getUniformLocation(prog, n);
    gl.uniform1i(U.uTex, 0);

    const tex = gl.createTexture();
    const water = { gl, ready:false, visible:true, rafId:0, img:null };

    function sizeGL() {
      const dpr = Math.min(devicePixelRatio || 1, 1.25, 1600 / Math.max(state.w, state.h));
      glCanvas.width = Math.max(2, Math.floor(state.w * dpr));
      glCanvas.height = Math.max(2, Math.floor(state.h * dpr));
      gl.viewport(0, 0, glCanvas.width, glCanvas.height);
    }

    function setSceneUniforms(t) {
      const compact = state.w <= 900;
      gl.uniform1f(U.uTime, t);
      gl.uniform1f(U.uGentle, state.reduced ? 1 : 0);
      gl.uniform2f(U.uRes, glCanvas.width, glCanvas.height);
      gl.uniform2f(U.uImg, water.img.naturalWidth, water.img.naturalHeight);
      gl.uniform1f(U.uFocusY, compact ? 0.6 : 0.5);
      gl.uniform1f(U.uWaterLine, compact ? 0.455 : 0.405);
    }

    function frame(now) {
      water.rafId = 0;
      if (paused || !water.visible || document.hidden || !water.ready) return;
      setSceneUniforms(now / 1000);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      hero.classList.add('ready');
      diagnostics.frames++; reportWater('webgl', 'running');
      water.rafId = requestAnimationFrame(frame);
    }
    function kick() { if (!paused && !water.rafId && water.ready) water.rafId = requestAnimationFrame(frame); }

    water.kick = kick;
    const img = new Image();
    img.onload = () => {
      gl.bindTexture(gl.TEXTURE_2D, tex);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false); // quad v=0 is already screen-top
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, img);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      water.img = img; water.ready = true;
      sizeGL();
      kick();
    };
    img.onerror = () => reportWater('still', 'hero image failed');
    img.src = '/assets/jetty-hero-clean.png';

    addEventListener('resize', sizeGL, { passive:true });
    document.addEventListener('visibilitychange', kick);
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(entries => {
        water.visible = entries[0].isIntersecting;
        if (water.visible) kick();
      }).observe(hero);
    }
    glCanvas.addEventListener('webglcontextlost', e => {
      e.preventDefault();
      if (water.rafId) cancelAnimationFrame(water.rafId);
      water.ready = false;
      start2D('WebGL context lost');
    });

    return water;
  }

  function start2D(reason) {
    if (water) { cancelAnimationFrame(water.rafId); water.rafId = 0; }
    // A canvas cannot change context types. Replace it after a GPU failure.
    const replacement = document.createElement('canvas');
    replacement.id = 'wave-gl'; replacement.className = 'hero-water';
    replacement.setAttribute('aria-hidden', 'true');
    glCanvas.replaceWith(replacement); glCanvas = replacement;
    const c = glCanvas.getContext('2d', { alpha: false });
    if (!c) { reportWater('still', 'Canvas unavailable'); waveToggle.textContent = 'Waves unavailable'; waveToggle.disabled = true; return; }
    const buffer = document.createElement('canvas');
    const b = buffer.getContext('2d', { alpha: false });
    const fallback = { ready: false, visible: true, rafId: 0, kick, last: 0 };
    water = fallback;
    const img = new Image();
    function size() {
      const scale = Math.min(1, 1280 / Math.max(state.w, state.h));
      glCanvas.width = buffer.width = Math.max(2, Math.round(state.w * scale));
      glCanvas.height = buffer.height = Math.max(2, Math.round(state.h * scale));
      if (!fallback.ready) return;
      const w = buffer.width, h = buffer.height;
      const cover = Math.max(w / img.naturalWidth, h / img.naturalHeight);
      const iw = img.naturalWidth * cover, ih = img.naturalHeight * cover;
      b.drawImage(img, (w-iw)*.5, (h-ih)*(state.w<=900?.6:.5), iw, ih);
    }
    function frame(now) {
      fallback.rafId = 0;
      if (paused || document.hidden || !fallback.visible || !fallback.ready) return;
      if (now-fallback.last >= 1000/24) {
        fallback.last = now;
        const w = buffer.width, h = buffer.height;
        const line = h*(state.w<=900?.455:.405);
        const t = now/1000*(state.reduced?.22:1);
        c.drawImage(buffer,0,0);
        // Refract narrow water-only strips. Sky and page geometry never move.
        for (let y=Math.floor(line); y<h; y+=3) {
          const depth=(y-line)/(h-line);
          const amp=(1+depth*5)*(state.reduced?.25:1);
          const dx=Math.sin(y*.07+t*1.7)*amp + Math.sin(y*.033-t*1.1)*amp*.5;
          const dy=Math.sin(y*.11+t*2)*amp*.35;
          const sy=Math.max(0,Math.min(h-3,y+dy));
          c.drawImage(buffer,0,sy,w,Math.min(3,h-y),dx,y,w,Math.min(3,h-y));
        }
        hero.classList.add('ready');
        diagnostics.frames++; reportWater('2d', reason);
      }
      fallback.rafId=requestAnimationFrame(frame);
    }
    function kick() { if (!paused && !fallback.rafId && fallback.ready) fallback.rafId=requestAnimationFrame(frame); }
    img.onload=()=>{ fallback.ready=true; size(); kick(); };
    img.onerror=()=>reportWater('still','hero image failed');
    img.src='/assets/jetty-hero-clean.png';
    addEventListener('resize',size,{passive:true});
    document.addEventListener('visibilitychange',kick);
    if ('IntersectionObserver' in window) new IntersectionObserver(entries=>{
      fallback.visible=entries[0].isIntersecting; if(fallback.visible) kick();
    }).observe(hero);
    reportWater('2d',reason);
  }
  function startWater() {
    if (params.get('renderer') === '2d') { start2D('requested 2D'); return; }
    try { water=initWater(); } catch (e) { console.warn('Water GPU unavailable', e); }
    if (!water) start2D('WebGL unavailable');
  }
  syncControl();
  if (!paused) startWater();


  // Pointer ripples on the water (transparent overlay canvas; the only rAF work left).
  function drawRipples() {
    if (!ctx) return;
    const now = performance.now();
    state.ripples = state.ripples.filter(r => now - r.birth < 1600);
    ctx.clearRect(0, 0, state.w, state.h);
    if (!state.ripples.length) { state.rafId = 0; return; }
    ctx.save(); ctx.globalCompositeOperation = 'screen';
    for (const r of state.ripples) {
      const age = (now - r.birth) / 1600;
      const radius = 18 + age * 180;
      ctx.strokeStyle = `rgba(255,247,239,${0.32 * (1 - age)})`;
      ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.arc(r.x, r.y, radius, 0, Math.PI * 2); ctx.stroke();
      ctx.strokeStyle = `rgba(200,51,111,${0.22 * (1 - age)})`;
      ctx.beginPath(); ctx.arc(r.x, r.y, radius * .55, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.restore();
    state.rafId = requestAnimationFrame(drawRipples);
  }

  function kickRipples() {
    if (!state.rafId) state.rafId = requestAnimationFrame(drawRipples);
  }

  // Star cursor, hover spin, and sparse spark trail.
  const star = document.getElementById('cursor-star');
  let sx = -80, sy = -80, lastSpark = 0;
  function setCursorVars(x, y){
    document.documentElement.style.setProperty('--cursor-x', `${x}px`);
    document.documentElement.style.setProperty('--cursor-y', `${y}px`);
  }
  addEventListener('pointermove', e => {
    state.pointer.x = e.clientX; state.pointer.y = e.clientY;
    sx += (e.clientX - sx) * 0.34; sy += (e.clientY - sy) * 0.34;
    setCursorVars(sx, sy);
    if (star) star.style.transform = `translate3d(${sx}px,${sy}px,0)`;
    const now = performance.now();
    if (!state.reduced && now - lastSpark > 85 && document.body.classList.contains('cursor-hover')) {
      lastSpark = now; createSpark(e.clientX, e.clientY);
    }
  }, { passive: true });

  function createSpark(x, y){
    const el = document.createElement('span'); el.className = 'star-spark';
    el.style.left = `${x - 7}px`; el.style.top = `${y - 7}px`;
    const angle = Math.random() * Math.PI * 2; const dist = 18 + Math.random() * 22;
    el.style.setProperty('--dx', `${Math.cos(angle) * dist}px`);
    el.style.setProperty('--dy', `${Math.sin(angle) * dist}px`);
    document.body.appendChild(el); setTimeout(() => el.remove(), 820);
  }

  const hoverTargets = 'a,button,.top-nav,.agent-card,.bento-grid article,.process-card,.landmark-card';
  document.querySelectorAll(hoverTargets).forEach(el => {
    el.addEventListener('mouseenter', () => document.body.classList.add('cursor-hover'));
    el.addEventListener('mouseleave', () => document.body.classList.remove('cursor-hover'));
  });

  addEventListener('pointerdown', e => {
    const waterTop = state.h * (state.w > 900 ? 0.405 : 0.455);
    if (!state.reduced && e.clientY >= waterTop) {
      state.ripples.push({ x:e.clientX, y:e.clientY, birth:performance.now() });
      kickRipples();
    }
    const el = document.createElement('span'); el.className = 'ripple'; el.style.left = e.clientX + 'px'; el.style.top = e.clientY + 'px';
    document.body.appendChild(el); setTimeout(() => el.remove(), 750);
  });

  // Right hamburger/chevron menu. Desktop: compact upper-right stack. Mobile: glass panel.
  const menu = document.querySelector('[data-jetty-menu]');
  const trigger = menu?.querySelector('.menu-trigger-toggle');
  const links = menu?.querySelector('.menu-links');
  function setMenu(open){
    if (!menu || !trigger || !links) return;
    links.hidden = !open;
    menu.classList.toggle('is-open', open);
    trigger.setAttribute('aria-expanded', String(open));
    trigger.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
  }
  trigger?.addEventListener('click', () => setMenu(!menu.classList.contains('is-open')));
  links?.querySelectorAll('a').forEach(a => a.addEventListener('click', () => setMenu(false)));
  addEventListener('pointerdown', e => { if (menu && !menu.contains(e.target)) setMenu(false); }, true);
  addEventListener('keydown', e => { if (e.key === 'Escape') setMenu(false); });

  // Smooth button scroll
  document.querySelectorAll('[data-scroll]').forEach(btn => btn.addEventListener('click', () => {
    document.querySelector(btn.dataset.scroll)?.scrollIntoView({ behavior:'smooth', block:'start' });
  }));

  // Appearance toggle: auto/sunset/night
  const modes = ['AUTO','SUNSET','DARK']; let modeIndex = 0;
  const toggle = document.getElementById('theme-toggle');
  toggle?.addEventListener('click', () => {
    modeIndex = (modeIndex + 1) % modes.length;
    toggle.querySelector('strong').textContent = modes[modeIndex];
    document.body.classList.toggle('theme-night', modes[modeIndex] === 'DARK');
  });

  resize();
})();
