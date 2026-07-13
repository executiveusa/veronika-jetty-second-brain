(() => {
  const hero = document.querySelector('.hero');
  const canvas = document.getElementById('wave-canvas');
  const ctx = canvas.getContext('2d', { alpha: false, desynchronized: true });
  const img = new Image();
  img.src = '/assets/jetty-hero-clean.png';

  const state = {
    dpr: Math.min(window.devicePixelRatio || 1, 2),
    w: 0, h: 0, t: 0, reduced: matchMedia('(prefers-reduced-motion: reduce)').matches,
    pointer: { x: -9999, y: -9999 }, ripples: []
  };

  function syncViewportMode() {
    const w = window.innerWidth || document.documentElement.clientWidth || 0;
    const isTouch = window.matchMedia('(pointer: coarse)').matches || navigator.maxTouchPoints > 0;
    document.documentElement.dataset.viewport = w < 700 ? 'compact' : w < 1100 ? 'tablet' : 'desktop';
    document.documentElement.dataset.pointer = isTouch ? 'touch' : 'fine';
  }

  function coverRect(iw, ih, w, h) {
    // Portrait phones: don't crop 70%+ of a landscape image.
    // Use "contain" (full image visible) on tall screens so the Spiral Jetty
    // and water stay in frame. Bars are filled by the basalt bg + vignette.
    const screenAspect = w / h;
    const imgAspect = iw / ih;
    const portrait = screenAspect < 0.85;
    if (portrait) {
      // Contain: scale to fit, center vertically biased slightly toward water
      const s = Math.min(w / iw, h / ih);
      const sw = iw * s, sh = ih * s;
      const sx = 0;
      const sy = Math.max(0, (h - sh) / 2); // centered, bars top+bottom
      // For the source-image crop rect (used by drawWaterOnly), map back:
      return { sx: 0, sy: 0, sw: iw, sh: ih };
    }
    // Landscape/tablet/desktop: classic cover, centered
    const s = Math.max(w / iw, h / ih);
    const sw = w / s, sh = h / s;
    return { sx: (iw - sw) / 2, sy: (ih - sh) / 2, sw, sh };
  }

  function resize() {
    // Track the HERO element size (which may exceed viewport when content wraps on mobile)
    // rather than innerHeight, so the canvas paints the whole hero, not just one screen.
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

  function drawImageBase() {
    const r = coverRect(img.width, img.height, state.w, state.h);
    ctx.drawImage(img, r.sx, r.sy, r.sw, r.sh, 0, 0, state.w, state.h);
    return r;
  }

  function smoothstep(edge0, edge1, x) {
    const t = Math.max(0, Math.min(1, (x - edge0) / (edge1 - edge0)));
    return t * t * (3 - 2 * t);
  }

  function drawWaterOnly(r) {
    if (state.reduced) return;
    // This mask keeps the sky, mountains, real DOM nav, and hero copy visually stable.
    // Only the lower reflective salt/water plane gets displaced.
    const waterTop = Math.floor(state.h * (state.w > 900 ? 0.405 : 0.455));
    const fade = Math.max(90, state.h * 0.12);
    const rowHeight = state.w > 900 ? 3 : 4;
    const amp = state.w > 900 ? 7.5 : 4.2;

    ctx.save();
    ctx.beginPath();
    ctx.rect(0, waterTop, state.w, state.h - waterTop);
    ctx.clip();

    for (let y = waterTop; y < state.h; y += rowHeight) {
      const p = (y - waterTop) / Math.max(1, state.h - waterTop);
      const mask = smoothstep(waterTop, waterTop + fade, y) * (0.35 + p * 0.65);
      const waveA = Math.sin(state.t * 0.00135 + y * 0.039);
      const waveB = Math.sin(state.t * 0.00082 + y * 0.017 + p * 2.7);
      const xoff = (waveA + waveB * 0.7) * amp * mask;
      const sy = r.sy + (y / state.h) * r.sh;
      const sh = (rowHeight / state.h) * r.sh;
      ctx.globalAlpha = 0.42 * mask;
      ctx.drawImage(img, r.sx, sy, r.sw, sh, xoff, y, state.w, rowHeight + 1);
    }

    const grad = ctx.createLinearGradient(0, waterTop, 0, state.h);
    grad.addColorStop(0, 'rgba(255,180,84,0)');
    grad.addColorStop(0.45, 'rgba(255,199,127,0.075)');
    grad.addColorStop(1, 'rgba(200,51,111,0.13)');
    ctx.globalAlpha = 1;
    ctx.fillStyle = grad; ctx.fillRect(0, waterTop, state.w, state.h - waterTop);

    ctx.globalCompositeOperation = 'screen';
    for (let i = 0; i < 16; i++) {
      const y = waterTop + ((state.t * (0.012 + i * 0.0007) + i * 59) % (state.h - waterTop));
      const mask = smoothstep(waterTop, waterTop + fade, y);
      const alpha = 0.055 * mask * (1 - (y - waterTop) / (state.h - waterTop));
      ctx.strokeStyle = `rgba(255,236,197,${alpha})`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let x = -30; x <= state.w + 30; x += 26) {
        const yy = y + Math.sin(x * 0.012 + state.t * 0.0018 + i) * (3.5 + i * 0.10);
        if (x === -30) ctx.moveTo(x, yy); else ctx.lineTo(x, yy);
      }
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawRipples() {
    if (!state.ripples.length || state.reduced) return;
    ctx.save(); ctx.globalCompositeOperation = 'screen';
    const now = performance.now();
    state.ripples = state.ripples.filter(r => now - r.birth < 1600);
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
  }

  function frame(t) {
    state.t = t;
    if (img.complete && img.naturalWidth) {
      const r = drawImageBase();
      drawWaterOnly(r);
      drawRipples();
    }
    requestAnimationFrame(frame);
  }

  img.onload = () => { resize(); hero.classList.add('ready'); requestAnimationFrame(frame); };
  resize();

  // Star cursor, hover spin, and sparse spark trail. Mirrors the original star-cursor feel without copying its runtime.
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
    if (e.clientY >= waterTop) state.ripples.push({ x:e.clientX, y:e.clientY, birth:performance.now() });
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
})();
