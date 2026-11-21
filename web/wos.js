// Wayfarer Operating System shell behaviour (docs/WOS.md): shortcuts, focus mode, the ship-state sheet, panel toggles with
// remembered state, and the scenario chip. Presentation only: it never writes ship, simulation or scenario values anywhere but
// the chip, and every page works without it.
(() => {
  const root = document.documentElement, KEY = 'wos.v1';
  root.classList.add('js');
  const prefs = (() => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; } })();
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch { /* storage blocked: defaults stay */ } };
  const bar = document.getElementById('wos-bar');
  const sheet = bar?.querySelector('.wos-state');
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

  // The ship-state sheet closes on Escape or a click elsewhere.
  document.addEventListener('click', e => { if (sheet?.open && !sheet.contains(e.target)) sheet.open = false; });

  // Shortcuts: g then a module letter; \ focus mode; Esc closes the sheet or leaves focus mode. Never while typing.
  const keys = new Map([...(bar?.querySelectorAll('[data-wos-key]') || [])].map(a => [a.dataset.wosKey, a.href]));
  let lead = 0;
  document.addEventListener('keydown', e => {
    if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || e.target.closest?.('input, textarea, select, [contenteditable]')) return;
    if (e.key === 'Escape') {
      if (sheet?.open) { sheet.open = false; sheet.querySelector('summary').focus(); return; }
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
  const now = document.getElementById('profile-now');
  if (now) now.textContent = `This screen: ${window.wos.profile()} layout, ${innerWidth} × ${innerHeight} px, `
    + `${matchMedia('(pointer: coarse)').matches ? 'touch' : 'pointer'} input.`;
})();
