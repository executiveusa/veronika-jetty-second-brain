(() => {
  const hero = document.querySelector('.hero');
  const video = document.getElementById('wave-video');
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
    ctx.setTransform(state.dpr, 0, 0, state.dpr, 0, 0);
    syncViewportMode();
  }
  addEventListener('resize', resize, { passive: true });

  // Water loop video (HyperFrames render, seamless ping-pong loop). The still
  // image underneath is the poster: it paints instantly, the video fades over
  // it when ready, and it is what reduced-motion users keep.
  function markReady() { hero.classList.add('ready'); }

  if (video) {
    if (state.reduced) {
      video.removeAttribute('autoplay');
      video.pause();
    } else {
      const play = () => { const p = video.play(); if (p && p.catch) p.catch(() => {}); };
      if (video.readyState >= 3) markReady();
      else {
        video.addEventListener('canplay', markReady, { once: true });
        setTimeout(markReady, 2500); // never leave the hero blank on a slow connection
      }
      document.addEventListener('visibilitychange', () => {
        if (document.hidden) video.pause(); else if (!state.reduced) play();
      });
      play();
    }
  } else {
    markReady();
  }

  // Pointer ripples on the water (transparent overlay canvas; the only rAF work left).
  function drawRipples() {
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
