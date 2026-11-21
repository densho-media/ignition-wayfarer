// Wayfarer Operating System shell behaviour (docs/WOS.md): shortcuts, focus mode, the ship-state sheet, panel toggles with
// remembered state, and the scenario chip. Presentation only: it never writes ship, simulation or scenario values anywhere but
// the chip, and every page works without it.
(() => {
  const root = document.documentElement, KEY = 'wos.v1';
  root.classList.add('js');
  const prefs = (() => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; } })();
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch { /* storage blocked: defaults stay */ } };
  const bar = document.getElementById('wos-bar');
  const page = location.pathname.replace(/index\.html$/, '');

  // Panel toggles: <button data-wos-toggle="id"> opens and closes #id (hidden), remembered per page.
  const panels = (prefs.panels ||= {})[page] ||= {};
  for (const b of document.querySelectorAll('[data-wos-toggle]')) {
    const target = document.getElementById(b.dataset.wosToggle);
    if (!target) continue;
    b.setAttribute('aria-controls', target.id);
    const set = open => { target.hidden = !open; b.setAttribute('aria-expanded', String(open)); };
    if (b.dataset.wosToggle in panels) set(panels[b.dataset.wosToggle]);
    else b.setAttribute('aria-expanded', String(!target.hidden));
    b.addEventListener('click', () => { const open = target.hidden; set(open); panels[b.dataset.wosToggle] = open; save(); });
  }

  // Focus mode: the workspace takes the whole screen (and the screen, where the browser allows); \ or Esc returns.
  const focus = on => {
    root.classList.toggle('wos-focus', on);
    window.dispatchEvent(new Event('resize'));
    if (on && root.requestFullscreen && matchMedia('(pointer: fine)').matches) root.requestFullscreen().catch(() => {});
    if (!on && document.fullscreenElement) document.exitFullscreen().catch(() => {});
  };
  document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement && root.classList.contains('wos-focus')) focus(false); });
  for (const b of document.querySelectorAll('[data-wos-focus]')) b.addEventListener('click', () => focus(!root.classList.contains('wos-focus')));

  // The sheets close on Escape or a click elsewhere.
  document.addEventListener('click', e => { for (const d of document.querySelectorAll('.wos-bar details[open]')) if (!d.contains(e.target)) d.open = false; });

  // Guidance strips (docs/WOS.md section 7): dismissed ones stay closed in this browser; the help sheet shows them again.
  const guides = prefs.guides ||= {};
  for (const g of document.querySelectorAll('[data-guide]')) {
    if (guides[g.dataset.guide]) g.hidden = true;
    g.querySelector('[data-wos-dismiss]')?.addEventListener('click', () => { g.hidden = true; guides[g.dataset.guide] = 1; save(); });
  }
  document.querySelector('[data-wos-reset-guides]')?.addEventListener('click', () => {
    prefs.guides = {}; save();
    for (const g of document.querySelectorAll('[data-guide]')) g.hidden = false;
  });
  // The current section tab stays in view on a narrow screen; a link to a section inside a closed disclosure opens it.
  const sub = document.querySelector('.wos-sub');
  if (sub) {
    const cur = sub.querySelector('[aria-current]');
    if (cur) sub.scrollLeft = cur.offsetLeft - (sub.clientWidth - cur.offsetWidth) / 2;
    // More sections off to a side: an edge fade and an arrow say so; the arrow scrolls the row (mouse users have no sideways wheel).
    const btn = side => sub.parentNode.querySelector(`.wos-sub-more[data-side="${side}"]`);
    const edge = () => {
      const l = sub.scrollLeft > 4, r = sub.scrollLeft + sub.clientWidth < sub.scrollWidth - 4;
      sub.dataset.more = [l && 'l', r && 'r'].filter(Boolean).join(' ');
      btn('l').hidden = !l; btn('r').hidden = !r;
    };
    for (const side of ['l', 'r']) btn(side)?.addEventListener('click', () => sub.scrollBy({ left: (side === 'r' ? 1 : -1) * sub.clientWidth * 0.7, behavior: 'smooth' }));
    sub.addEventListener('scroll', edge, { passive: true }); addEventListener('resize', edge); edge();
  }
  const reveal = () => { const t = location.hash && document.getElementById(location.hash.slice(1)); const d = t?.closest?.('details'); if (d) d.open = true; };
  addEventListener('hashchange', reveal); reveal();
  for (const d of document.querySelectorAll('.wos-bar details')) d.addEventListener('toggle', () => {
    if (d.open) for (const o of document.querySelectorAll('.wos-bar details')) if (o !== d) o.open = false;
  });

  // Shortcuts: g then a module letter (or an earlier module's letter); \ focus mode; Esc closes a sheet or leaves focus mode.
  const keys = new Map();
  for (const a of bar?.querySelectorAll('[data-wos-key]') || []) for (const k of a.dataset.wosKey + (a.dataset.wosAlias || '')) keys.set(k, a.href);
  let lead = 0;
  document.addEventListener('keydown', e => {
    if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || e.target.closest?.('input, textarea, select, [contenteditable]')) return;
    if (e.key === 'Escape') {
      const open = document.querySelector('.wos-bar details[open]');
      if (open) { open.open = false; open.querySelector('summary').focus(); return; }
      if (root.classList.contains('wos-focus')) focus(false);
      return;
    }
    if (e.key === '\\') { focus(!root.classList.contains('wos-focus')); e.preventDefault(); return; }
    if (e.key === 'g' && !lead) { lead = e.timeStamp; return; }
    if (lead && e.timeStamp - lead < 1500 && keys.has(e.key)) { e.preventDefault(); location.href = keys.get(e.key); }
    lead = 0;
  }, true);

  // A module announces a running simulation or scenario; it is a property of this page only (never stored, never shared).
  const chip = bar?.querySelector('.wos-scn');
  window.wos = {
    profile: () => matchMedia('(max-width: 699px), (max-height: 499px)').matches ? 'terminal'
      : matchMedia('(max-width: 1099px)').matches ? 'compact' : 'workstation',
    scenario(s) {
      if (!chip) return;
      chip.hidden = !s;
      chip.textContent = s ? `${s.class === 'SCENARIO' ? 'SCENARIO' : 'SIM'} · ${s.label}` : '';
      chip.classList.toggle('scn', s?.class === 'SCENARIO');
      chip.title = s ? `${s.class === 'SCENARIO' ? 'Scenario' : 'Simulation'} running on this page only: the ship state above is unchanged` : '';
    },
    prefs, save,
  };
  const line = `This screen: ${window.wos.profile()} layout, ${innerWidth} × ${innerHeight} px, `
    + `${matchMedia('(pointer: coarse)').matches ? 'touch' : 'pointer'} input.`;
  for (const e of document.querySelectorAll('#profile-now, [data-wos-profile]')) e.textContent = line;
})();
