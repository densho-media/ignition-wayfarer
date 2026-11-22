// Engineering · Fusion engine: where the energy goes (tools/story.py writes engineering/fusion/ and its fusion.json from the
// selective-fusion study, lab/studies/selective-fusion/model.py). A concept explainer, not a reactor solver. The page computes no new
// physics: the power channels per setting (charged, neutron, X-ray, ion-heating power, reaction shares) are looked up in fusion.json,
// and evaluate() repeats model.py ledger() line by line (the site check compares the two at the study's check points). Three views
// share one 2D canvas: Reactions (which nuclei fuse and what comes out), Engine (where each product goes) and Energy budget (a
// two-stage flow from fusion power to thrust, heat in the ship and radiation that escapes). Dots are a picture of the shares.

const $ = id => document.getElementById(id);
const root = document.querySelector('section.fus');
const canvas = $('fusion-view'), ctx = canvas.getContext('2d');
const stage = $('stage'), evcap = $('evcap');
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

let D = null;
const S = { d: 8, t: 3, mode: 'thermal', pol: 'none', x: 0.62, view: 'reaction' };
let playing = !reduced, visible = true, last = 0, raf = 0;
const stats = { frames: 0 };

// ---- colours: the site's tokens (web/site.css) ---------------------------------------------------------------------------------
const css = getComputedStyle(document.documentElement);
const tok = (n, f) => (css.getPropertyValue(n) || '').trim() || f;
const COL = {
  D: tok('--info', '#8FC1F0'), He3: tok('--wf-violet', '#8C83C5'), alpha: tok('--wf-plasma', '#D99AC9'), p: tok('--wf-ignition', '#D8EAFF'),
  T: tok('--good', '#7FD39B'), n: '#A9B4BF', photon: tok('--warn', '#E9B85A'), heat: tok('--bad', '#FF7F73'), thrust: tok('--good', '#7FD39B'),
  ink: tok('--ink', '#C9D3DD'), muted: tok('--muted', '#8794A1'), line: tok('--line-strong', '#2C3A48'), bg: '#05070B', hw: '#3A4652',
};

// ---- formatting ----------------------------------------------------------------------------------------------------------------
const pc = v => v >= 0.001 ? `${(100 * v).toFixed(1)} %` : v > 0 ? `${(100 * v).toFixed(2)} %` : '0 %';
const big = v => v >= 100 ? Math.round(v).toLocaleString('en') : v >= 10 ? v.toFixed(0) : v.toFixed(1);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// ---- the model (lookup + model.py ledger) ----------------------------------------------------------------------------------------
const keyOf = (pol, mode, Ti, d) => `${pol}|${mode}|${Ti}|${d.toFixed(2)}`;
const keyNow = () => keyOf(S.pol, S.mode, D.axes.Ti[S.t], D.axes.d_share[S.d]);
function point(key) {
  const v = D.grid[key];
  if (!v) return null;
  const o = {};
  D.fields.forEach((f, i) => { o[f] = v[i]; });
  return o;
}
function evaluate(key, exposure) {
  const pt = point(key), K = D.canon, C = D.constants;
  const loss = pt.ei * (1 / C.injector_eff - 1);
  let plasma = pt.charged - pt.photon - loss;
  const sustains = plasma > 0;
  plasma = Math.max(plasma, 0);
  const thrust = plasma * K.directed_efficiency;
  const spread = plasma - thrust;
  const heat = pt.photon * exposure + pt.neutron * C.neutron_absorbed + loss;
  const escape = pt.photon * (1 - exposure) + pt.neutron * (1 - C.neutron_absorbed);
  const P = thrust > 0 ? K.jet_W / thrust : null;
  const heatW = P ? heat * P : null;
  const budget = K.hot_radiator_W * K.hot_share;
  // reactions by count (the grid holds energy shares)
  const E = C.energies_MeV, cD = pt.share_dhe3 / E.dhe3, cDD = pt.share_dd / ((E.ddn_n + E.ddn_he3 + E.ddp_t + E.ddp_p) / 2),
    cT = pt.share_dt / (E.dt_n + E.dt_alpha), cs = cD + cDD + cT;
  return { pt, thrust, spread, photon: pt.photon, neutron: pt.neutron, injector_loss: loss, heat, escape, sustains,
    fusion_needed_W: P, heat_W: heatW, radiator_multiple: heatW ? heatW / budget : null,
    closure: sustains ? thrust + spread + pt.photon + pt.neutron + loss : null,
    counts: { dhe3: cD / cs, dd: cDD / cs, dt: cT / cs }, rel: pt.rel_power };
}
let R = null;      // the current evaluation

// ---- controls ------------------------------------------------------------------------------------------------------------------
const cd = $('c-d'), ct = $('c-t'), cx = $('c-x');
function readHash() {
  const h = location.hash.slice(1);
  if (['reaction', 'engine', 'budget'].includes(h)) { S.view = h; return; }
  const q = new URLSearchParams(h);
  const near = (arr, v) => arr.reduce((b, a, i) => Math.abs(a - v) < Math.abs(arr[b] - v) ? i : b, 0);
  if (q.has('d')) S.d = near(D.axes.d_share, +q.get('d') / 100);
  if (q.has('t')) S.t = near(D.axes.Ti, +q.get('t'));
  if (D.axes.modes[q.get('m')] !== undefined) S.mode = q.get('m');
  if (D.axes.pol[q.get('p')]) S.pol = q.get('p');
  if (q.has('x')) S.x = Math.min(1, Math.max(0, +q.get('x') / 100));
  if (['reaction', 'engine', 'budget'].includes(q.get('v'))) S.view = q.get('v');
}
const linkOf = () => `#d=${Math.round(100 * D.axes.d_share[S.d])}&t=${D.axes.Ti[S.t]}&m=${S.mode}&p=${S.pol}&x=${Math.round(100 * S.x)}&v=${S.view}`;
function sync() {
  cd.value = S.d; ct.value = S.t; cx.value = Math.round(100 * S.x);
  $('o-d').textContent = `${Math.round(100 * D.axes.d_share[S.d])} %`;
  $('o-t').textContent = `${D.axes.Ti[S.t]} keV`;
  $('o-x').textContent = `${Math.round(100 * S.x)} %`;
  document.querySelectorAll('[data-modeop]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.modeop === S.mode)));
  document.querySelectorAll('[data-pol]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.pol === S.pol)));
  document.querySelectorAll('.ign-modes [role="tab"]').forEach(b => b.setAttribute('aria-selected', String(b.dataset.mode === S.view)));
  root.dataset.mode = S.view;
  R = evaluate(keyNow(), S.x);
  readouts();
  if (!playing) draw(0);
}
function readouts() {
  const r = R, K = D.canon;
  const vals = { thrust: r.thrust, spread: r.spread, photon: r.photon, neutron: r.neutron, loss: r.injector_loss };
  for (const tr of $('ledger').rows) {
    const v = vals[tr.dataset.k];
    tr.cells[1].textContent = pc(v);
    tr.querySelector('.fbar i').style.width = `${Math.min(100, 100 * v).toFixed(1)}%`;
    tr.classList.toggle('zero', v < 1e-6);
  }
  $('r-heat').textContent = pc(r.heat);
  $('r-escape').textContent = pc(r.escape);
  $('r-mix').textContent = `${pc(r.counts.dhe3)} / ${pc(r.counts.dd)} / ${pc(r.counts.dt)}`;
  $('r-rel').textContent = `${Math.round(100 * r.rel)} % of the best setting`;
  const mode = S.mode === 'thermal' ? 'thermal' : 'hot-ion';
  const pol = D.axes.pol[S.pol];
  const spec = pol.cls === 'SPECULATIVE' ? ' <span class="st st-SPECULATIVE">speculative</span>' : pol.cls === 'MODEL-BASED' ? ' <span class="st st-CALCULATED">model-based</span>' : '';
  const setting = `${Math.round(100 * D.axes.d_share[S.d])} % D, ${D.axes.Ti[S.t]} keV, ${mode}, ${pol.label.toLowerCase()}${spec}`;
  const isRef = S.d === D.axes.d_share.indexOf(D.reference.d_share) && S.t === D.axes.Ti.indexOf(D.reference.Ti) && S.mode === D.reference.mode
    && S.pol === D.reference.pol && Math.abs(S.x - D.constants.photon_exposure_ref) < 0.005;
  $('verdict').className = 'first ' + (r.sustains ? '' : 'bad');
  $('verdict').innerHTML = r.sustains
    ? `<b>${pc(r.thrust)} becomes thrust</b> and ${pc(r.heat)} heats the ship.${isRef ? ' <i>Reference point.</i>' : ''}<br><span class="meta">${setting}</span>`
    : `<b>The burn cannot keep itself hot</b>: the X-rays${r.injector_loss > 0 ? ' and injector losses' : ''} take more than the charged products give.<br><span class="meta">${setting}</span>`;
  const budget = K.hot_radiator_W * K.hot_share;
  $('r-scale').innerHTML = r.sustains
    ? `At the Wayfarer's operating point (${Math.round(K.jet_W / 1e12)} TW of jet) the burn needs ${Math.round(r.fusion_needed_W / 1e12)} TW of fusion,
       and about ${big(r.heat_W / 1e9)} GW lands in the ship, against ${(budget / 1e9).toFixed(1)} GW of radiator for the drive:
       <b class="bad">${big(r.radiator_multiple)}× too much</b>.`
    : 'No thrust at this setting, so there is no Wayfarer operating point.';
}
function wire() {
  cd.addEventListener('input', () => { S.d = +cd.value; sync(); });
  ct.addEventListener('input', () => { S.t = +ct.value; sync(); });
  cx.addEventListener('input', () => { S.x = +cx.value / 100; sync(); });
  document.querySelectorAll('[data-modeop]').forEach(b => b.addEventListener('click', () => { S.mode = b.dataset.modeop; sync(); }));
  document.querySelectorAll('[data-pol]').forEach(b => b.addEventListener('click', () => { S.pol = b.dataset.pol; sync(); }));
  const tabs = [...document.querySelectorAll('.ign-modes [role="tab"]')];
  tabs.forEach((b, i) => {
    b.addEventListener('click', () => { S.view = b.dataset.mode; parts.length = 0; sync(); });
    b.addEventListener('keydown', ev => {
      const j = ev.key === 'ArrowRight' ? (i + 1) % tabs.length : ev.key === 'ArrowLeft' ? (i + tabs.length - 1) % tabs.length : -1;
      if (j >= 0) { ev.preventDefault(); tabs[j].focus(); tabs[j].click(); }
    });
  });
  $('ref').addEventListener('click', () => {
    S.d = D.axes.d_share.indexOf(D.reference.d_share); S.t = D.axes.Ti.indexOf(D.reference.Ti);
    S.mode = D.reference.mode; S.pol = D.reference.pol; S.x = D.constants.photon_exposure_ref; sync();
  });
  $('share').addEventListener('click', async () => {
    history.replaceState(null, '', linkOf());
    try { await navigator.clipboard.writeText(location.href); $('share').textContent = 'Link copied'; } catch { $('share').textContent = 'Link in the address bar'; }
    setTimeout(() => { $('share').textContent = 'Copy a link to this setting'; }, 2000);
  });
  $('play').addEventListener('click', () => {
    playing = !playing;
    $('play').textContent = playing ? '❚❚' : '▶'; $('play').setAttribute('aria-label', playing ? 'Pause' : 'Play');
    if (playing) loop(); else draw(0);
  });
  new ResizeObserver(() => { size(); if (!playing) draw(0); }).observe(stage);
  new IntersectionObserver(es => { visible = es[0].isIntersecting; if (visible && playing) loop(); }).observe(stage);
  document.addEventListener('visibilitychange', () => { if (!document.hidden && playing) loop(); });
}

// ---- canvas ------------------------------------------------------------------------------------------------------------------
let W = 0, H = 0, dpr = 1;
function size() {
  dpr = Math.min(2, devicePixelRatio || 1);
  const r = stage.getBoundingClientRect();
  W = Math.max(200, r.width); H = Math.max(200, r.height);
  canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}
const parts = [];
let spawnClock = 0, flashes = [];
const rnd = (a, b) => a + Math.random() * (b - a);
function pickReaction() {
  const c = R.counts, u = Math.random();
  // D-D is shown 3x as often as its share so that it stays visible at small shares; the counts in the readout are the real ones
  const dd = Math.min(0.6, 3 * c.dd), dt = Math.min(0.3, 3 * c.dt);
  if (u < dd) return Math.random() < 0.5 ? 'ddn' : 'ddp';
  if (u < dd + dt) return 'dt';
  return 'dhe3';
}
const PRODUCTS = {
  dhe3: [['alpha', 4.5, 1.0], ['p', 3, 2.0]], ddn: [['He3', 4, 0.6], ['n', 3.5, 1.7]], ddp: [['T', 3.5, 0.9], ['p', 3, 1.5]], dt: [['alpha', 4.5, 0.9], ['n', 3.5, 2.4]],
};
const REACT = {
  dhe3: ['D', 'He3', 'D + ³He → α + p · 18.35 MeV, all charged: useful'], ddn: ['D', 'D', 'D + D → ³He + n · the neutron cannot be steered'],
  ddp: ['D', 'D', 'D + D → T + p · charged, but the tritium can fuse again'], dt: ['T', 'D', 'T + D → α + n · a 14.1 MeV neutron'],
};
const LABEL = { D: 'D', He3: '³He', alpha: 'α', p: 'p', T: 'T', n: 'n' };

function spawnReaction(t) {
  const kind = pickReaction(), [a, b, txt] = REACT[kind];
  const cx = W * rnd(0.3, 0.7), cy = H * rnd(0.28, 0.72), ang = rnd(0, Math.PI), dist = Math.min(W, H) * 0.16, tm = 0.7;
  const ux = Math.cos(ang), uy = Math.sin(ang);
  parts.push({ k: 'in', sp: a, x: cx - ux * dist, y: cy - uy * dist, vx: ux * dist / tm, vy: uy * dist / tm, life: tm, r: a === 'He3' ? 4.5 : 3.5, kind, cx, cy, txt });
  parts.push({ k: 'in', sp: b, x: cx + ux * dist, y: cy + uy * dist, vx: -ux * dist / tm, vy: -uy * dist / tm, life: tm, r: b === 'He3' ? 4.5 : 3.5, kind, cx, cy, lead: true, txt });
}
function burst(p) {
  flashes.push({ x: p.cx, y: p.cy, life: 0.35, c: p.kind === 'dhe3' ? COL.p : COL.heat });
  const out = rnd(0, 2 * Math.PI), v0 = Math.min(W, H) * 0.35;
  PRODUCTS[p.kind].forEach(([sp, r, s], i) => {
    const a = out + i * Math.PI + rnd(-0.2, 0.2);
    parts.push({ k: 'out', sp, x: p.cx, y: p.cy, vx: Math.cos(a) * v0 * s, vy: Math.sin(a) * v0 * s, life: 2.2, r, trail: [] });
  });
  if (p.lead) evcap.innerHTML = `<b>${esc(p.txt.split(' · ')[0])}</b><span>${esc(p.txt.split(' · ')[1])}</span>`;
}
function spawnPhoton(x0, y0, ang, v, life) { parts.push({ k: 'ph', x: x0, y: y0, vx: Math.cos(ang) * v, vy: Math.sin(ang) * v, life, ph: rnd(0, 6) }); }

// Engine geometry (aft to the right): ship, shield, injectors, burn, coils, nozzle field lines, exhaust.
function geo() {
  const cx = W * 0.42, cy = H * 0.5, rh = Math.min(H * 0.32, W * 0.2);
  return { cx, cy, rh, shieldX: W * 0.2, coils: [[W * 0.33, cy - rh, W * 0.33, cy + rh], [W * 0.51, cy - rh * 0.95, W * 0.51, cy + rh * 0.95], [W * 0.6, cy - rh * 0.7, W * 0.6, cy + rh * 0.7]] };
}
const hardwarePoint = g => {
  const u = Math.random();
  if (u < 0.35) return [g.shieldX + 4, g.cy + rnd(-g.rh * 1.2, g.rh * 1.2)];
  const c = g.coils[Math.floor(rnd(0, g.coils.length))];
  return [c[0] + rnd(-6, 6), Math.random() < 0.5 ? c[1] : c[3]];
};
function fieldLine(g, s, t) {      // s in [-1, 1] picks the line, t in [0, 1] goes from the burn to the exit
  const x = g.cx + t * (W - g.cx + 40), spread = s * (0.25 + 1.6 * t * t) * g.rh;
  return [x, g.cy + spread];
}
function spawnEngine(dt) {
  const g = geo(), r = R;
  spawnClock += dt;
  const rate = 70;                                   // dots per second in all, split by the energy shares
  while (spawnClock > 1 / rate) {
    spawnClock -= 1 / rate;
    const u = Math.random(), plasma = r.thrust + r.spread;
    if (u < plasma) {
      const aimed = Math.random() < r.thrust / Math.max(plasma, 1e-9);
      parts.push({ k: 'ex', s: aimed ? rnd(-0.35, 0.35) : (Math.random() < 0.5 ? -1 : 1) * rnd(0.6, 1), t: 0, sp: Math.random() < 0.5 ? 'alpha' : 'p', aimed, life: 3 });
    } else if (u < plasma + r.photon) {
      const hit = Math.random() < S.x;
      if (hit) { const [hx, hy] = hardwarePoint(g); const a = Math.atan2(hy - g.cy, hx - g.cx), d = Math.hypot(hx - g.cx, hy - g.cy); spawnPhoton(g.cx, g.cy, a, 520, d / 520); parts[parts.length - 1].hit = [hx, hy]; }
      else { const a = rnd(-0.9, 0.9) + (Math.random() < 0.5 ? -Math.PI / 2 : Math.PI / 2); spawnPhoton(g.cx, g.cy, a, 520, 2); }
    } else if (u < plasma + r.photon + r.neutron) {
      const hit = Math.random() < D.constants.neutron_absorbed;
      let a, life, hx, hy;
      if (hit) { [hx, hy] = hardwarePoint(g); a = Math.atan2(hy - g.cy, hx - g.cx); life = Math.hypot(hx - g.cx, hy - g.cy) / 300; }
      else { a = rnd(0, 2 * Math.PI); life = 3; }
      parts.push({ k: 'n', x: g.cx, y: g.cy, vx: Math.cos(a) * 300, vy: Math.sin(a) * 300, life, hit: hit ? [hx, hy] : null });
    } else if (r.injector_loss > 0) {
      flashes.push({ x: g.shieldX - 14, y: g.cy + rnd(-g.rh, g.rh), life: 0.4, c: COL.heat });
    }
  }
  // fuel stream into the burn, in the mix's proportions
  if (Math.random() < dt * 30) {
    const d = D.axes.d_share[S.d];
    parts.push({ k: 'fuel', sp: Math.random() < d ? 'D' : 'He3', x: g.shieldX + 8, y: g.cy + rnd(-g.rh * 0.25, g.rh * 0.25), life: 0.9 });
  }
}
function update(dt) {
  if (S.view === 'reaction') {
    spawnClock += dt;
    const rate = 2.2;
    while (spawnClock > 1 / rate) { spawnClock -= 1 / rate; spawnReaction(); }
    if (Math.random() < dt * 30 * R.photon) spawnPhoton(W * rnd(0.3, 0.7), H * rnd(0.3, 0.7), rnd(0, 2 * Math.PI), 260, 1.2);
  } else if (S.view === 'engine') spawnEngine(dt);
  for (const p of parts) {
    p.life -= dt;
    if (p.k === 'ex') { p.t += dt * (p.aimed ? 0.45 : 0.3); if (p.t > 1) p.life = 0; continue; }
    if (p.k === 'fuel') { const g = geo(); p.x += (g.cx - p.x) * Math.min(1, dt * 3.5); p.y += (g.cy - p.y) * Math.min(1, dt * 3.5); continue; }
    if (p.trail) { p.trail.push([p.x, p.y]); if (p.trail.length > 14) p.trail.shift(); }
    p.x += p.vx * dt; p.y += p.vy * dt;
    if (p.k === 'in' && p.life <= 0 && p.lead) burst(p);
    if ((p.k === 'ph' || p.k === 'n') && p.hit && p.life <= 0) flashes.push({ x: p.hit[0], y: p.hit[1], life: 0.5, c: COL.heat });
  }
  for (let i = parts.length - 1; i >= 0; i--) if (parts[i].life <= 0) parts.splice(i, 1);
  for (const f of flashes) f.life -= dt;
  flashes = flashes.filter(f => f.life > 0);
  if (parts.length > 900) parts.splice(0, parts.length - 900);
}

function dot(x, y, r, c, ring) {
  ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI);
  if (ring) { ctx.strokeStyle = c; ctx.lineWidth = 1.5; ctx.stroke(); } else { ctx.fillStyle = c; ctx.fill(); }
}
function label(x, y, txt, c = COL.muted, align = 'left', size = 12) {
  ctx.fillStyle = c; ctx.font = `${size}px ${tok('--mono', 'monospace')}`; ctx.textAlign = align; ctx.textBaseline = 'middle'; ctx.fillText(txt, x, y);
}
function wiggle(p) {
  const n = Math.hypot(p.vx, p.vy) || 1, ux = p.vx / n, uy = p.vy / n;
  ctx.beginPath();
  for (let i = 0; i <= 10; i++) {
    const s = i * 1.6, w = Math.sin(p.ph + i * 1.3) * 2.2;
    const x = p.x - ux * s - uy * w, y = p.y - uy * s + ux * w;
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  }
  ctx.strokeStyle = COL.photon; ctx.lineWidth = 1.4; ctx.stroke();
}
function legend(items) {
  // wraps onto a second line on narrow stages instead of dropping entries
  ctx.font = `12px ${tok('--mono', 'monospace')}`;
  const rows = [[]]; let x = 12;
  for (const it of items) {
    const w = 22 + ctx.measureText(it[0]).width;
    if (x + w > W - 8 && rows[rows.length - 1].length) { rows.push([]); x = 12; }
    rows[rows.length - 1].push([it, x]); x += w;
  }
  rows.forEach((row, i) => {
    const y = H - 16 - (rows.length - 1 - i) * 18;
    for (const [[txt, c, ring], xx] of row) { dot(xx + 4, y, 4, c, ring); label(xx + 12, y, txt, COL.ink); }
  });
}
function drawReaction() {
  for (const p of parts) {
    if (p.k === 'ph') { wiggle(p); continue; }
    if (p.trail && p.trail.length > 1) {
      ctx.beginPath(); p.trail.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
      ctx.strokeStyle = COL[p.sp]; ctx.globalAlpha = 0.35; ctx.lineWidth = p.sp === 'n' ? 1 : 2;
      if (p.sp === 'n') ctx.setLineDash([3, 4]);
      ctx.stroke(); ctx.setLineDash([]); ctx.globalAlpha = 1;
    }
    dot(p.x, p.y, p.r, COL[p.sp], p.sp === 'n');
    if (p.k === 'out' && p.life > 1.2) label(p.x + p.r + 4, p.y, LABEL[p.sp], COL[p.sp]);
  }
  for (const f of flashes) { ctx.globalAlpha = f.life / 0.35; dot(f.x, f.y, 14 * (1 - f.life / 0.35) + 4, f.c, true); ctx.globalAlpha = 1; }
  label(12, 18, 'Reactions in the burn', COL.ink, 'left', 13);
  label(12, 36, `D-D shown 3× as often as it happens (${pc(R.counts.dd)} of reactions)`, COL.muted, 'left', 11);
  legend([['D', COL.D], ['³He', COL.He3], ['α', COL.alpha], ['p', COL.p], ['T', COL.T], ['neutron', COL.n, true], ['X-ray', COL.photon]]);
}
function drawEngine() {
  const g = geo();
  const heatLvl = Math.min(1, R.heat / 0.25);
  // field lines
  ctx.strokeStyle = COL.line; ctx.lineWidth = 1;
  for (const s of [-1, -0.6, -0.3, 0, 0.3, 0.6, 1]) {
    ctx.beginPath();
    for (let i = 0; i <= 24; i++) { const [x, y] = fieldLine(g, s, i / 24); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }
    ctx.stroke();
  }
  // ship side and shield
  ctx.fillStyle = '#1A222B'; ctx.fillRect(0, g.cy - g.rh * 1.5, g.shieldX - 26, g.rh * 3);
  const shipY = g.cy - g.rh * 1.5 - 12;                           // inside the hull block when the title lines need the room
  label(10, shipY < 64 ? shipY + 26 : shipY, 'ship (forward)', COL.muted);
  ctx.fillStyle = mix(COL.hw, COL.heat, heatLvl * 0.8); ctx.fillRect(g.shieldX - 6, g.cy - g.rh * 1.3, 12, g.rh * 2.6);
  label(g.shieldX, g.cy + g.rh * 1.3 + 12, 'shield', COL.muted, 'center');
  // coils
  for (const c of g.coils) {
    ctx.fillStyle = mix(COL.hw, COL.heat, heatLvl);
    ctx.fillRect(c[0] - 7, c[1] - 9, 14, 18); ctx.fillRect(c[2] - 7, c[3] - 9, 14, 18);
  }
  label(g.coils[1][0], g.coils[1][1] - 20, 'field coils', COL.muted, 'center');
  // burn
  const grd = ctx.createRadialGradient(g.cx, g.cy, 2, g.cx, g.cy, g.rh * 0.45);
  grd.addColorStop(0, '#FFFFFF'); grd.addColorStop(0.3, COL.alpha); grd.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = grd; ctx.beginPath(); ctx.arc(g.cx, g.cy, g.rh * 0.45, 0, 2 * Math.PI); ctx.fill();
  label(g.cx, g.cy + g.rh * 0.55, 'burn', COL.ink, 'center');
  label(W - 10, g.cy - g.rh * 1.25, 'exhaust → thrust', COL.thrust, 'right');
  // particles
  for (const p of parts) {
    if (p.k === 'ex') { const [x, y] = fieldLine(g, p.s, p.t); dot(x, y, p.sp === 'alpha' ? 3.2 : 2.4, p.aimed ? COL[p.sp] : COL.muted); }
    else if (p.k === 'fuel') dot(p.x, p.y, 2.8, COL[p.sp]);
    else if (p.k === 'ph') wiggle(p);
    else if (p.k === 'n') dot(p.x, p.y, 3, COL.n, true);
  }
  for (const f of flashes) { ctx.globalAlpha = Math.min(1, f.life / 0.4); dot(f.x, f.y, 5, f.c); ctx.globalAlpha = 1; }
  label(12, 18, 'Engine (aft is to the right)', COL.ink, 'left', 13);
  if (W < 520) {
    label(12, 36, `X-rays hitting hardware: ${Math.round(100 * S.x)} %`, COL.muted, 'left', 11);
    label(12, 52, `heat in the ship: ${pc(R.heat)}`, COL.muted, 'left', 11);
  } else label(12, 36, `X-rays hitting hardware: ${Math.round(100 * S.x)} % · heat in the ship ${pc(R.heat)}`, COL.muted, 'left', 11);
  legend([['fuel D', COL.D], ['fuel ³He', COL.He3], ['α', COL.alpha], ['p', COL.p], ['neutron', COL.n, true], ['X-ray', COL.photon], ['heat', COL.heat]]);
}
function mix(a, b, t) {
  const h = s => s.length === 4 ? [1, 2, 3].map(i => parseInt(s[i] + s[i], 16)) : [1, 3, 5].map(i => parseInt(s.slice(i, i + 2), 16));
  const A = h(a), B = h(b);
  return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * t)).join(',')})`;
}
function band(x0, y0, h0, x1, y1, h1, c, alpha = 0.55) {
  if (h0 <= 0) return;
  const m = (x0 + x1) / 2;
  ctx.beginPath(); ctx.moveTo(x0, y0); ctx.bezierCurveTo(m, y0, m, y1, x1, y1); ctx.lineTo(x1, y1 + h1);
  ctx.bezierCurveTo(m, y1 + h1, m, y0 + h0, x0, y0 + h0); ctx.closePath();
  ctx.fillStyle = c; ctx.globalAlpha = alpha; ctx.fill(); ctx.globalAlpha = 1;
}
function drawBudget(t) {
  const narrow = W < 520;                                         // phones: shorter columns, two-line labels
  const r = R, top = narrow ? 94 : 78, hT = H - top - 46, gap = 10, colW = 14;
  const x0 = narrow ? 14 : 30, x1 = W * (narrow ? 0.3 : 0.36), x2 = W * (narrow ? 0.55 : 0.7);
  const fusion = r.pt.charged + r.pt.neutron;                    // = 1
  const minH = v => v > 0 ? Math.max(2, v * (hT - 3 * gap)) : 0;
  // stage 1
  ctx.fillStyle = COL.p; ctx.fillRect(x0, top, colW, hT);
  label(x0, top - 12, 'fusion power 100 %', COL.ink);
  const ch = minH(r.pt.charged / fusion), nh = minH(r.pt.neutron / fusion);
  const yC = top, yN = top + ch + gap;
  band(x0 + colW, top, ch, x1, yC, ch, COL.alpha);
  band(x0 + colW, top + ch, nh, x1, yN, nh, COL.n);
  ctx.fillStyle = COL.alpha; ctx.fillRect(x1, yC, colW, ch); ctx.fillStyle = COL.n; ctx.fillRect(x1, yN, colW, nh);
  if (narrow) {                                                   // the middle column is too thin for labels on phones
    label(x0 + colW + 6, yC + 12, 'charged', COL.ink); label(x0 + colW + 6, yC + 28, pc(r.pt.charged), COL.ink);
    label(x0, top + hT + 16, `neutrons ${pc(r.pt.neutron)} (grey band)`, COL.n);
  } else {
    label(x1 + colW + 6, yC + 10, `charged products ${pc(r.pt.charged)}`, COL.alpha);
    label(x1 + colW + 6, yN + nh / 2 + (nh < 14 ? 8 : 0), `neutrons ${pc(r.pt.neutron)}`, COL.n);
  }
  // stage 2: outcomes
  const outs = [
    ['Useful for thrust', COL.thrust, [['c', r.thrust]]],
    ['Leaves sideways', COL.muted, [['c', r.spread]]],
    ['Heat in the ship', COL.heat, [['c', r.photon * S.x], ['c', r.injector_loss], ['n', r.neutron * D.constants.neutron_absorbed]]],
    ['Escapes to space', COL.photon, [['c', r.photon * (1 - S.x)], ['n', r.neutron * (1 - D.constants.neutron_absorbed)]]],
  ];
  let y = top, sc = yC, sn = yN, ly = -1e9;
  const scale = (hT - 3 * gap) / Math.max(1e-9, fusion);
  for (const [name, c, flows] of outs) {
    const tot = flows.reduce((a, f) => a + f[1], 0);
    const hh = tot > 0 ? Math.max(2, tot * scale) : 0;
    let yy = y;
    for (const [src, v] of flows) {
      const h = v > 0 ? Math.max(1, v * scale) : 0;
      if (!h) continue;
      if (src === 'c') { band(x1 + colW, sc, h, x2, yy, h, c); sc += h; } else { band(x1 + colW, sn, h, x2, yy, h, c); sn += h; }
      yy += h;
    }
    if (hh) { ctx.fillStyle = c; ctx.fillRect(x2, y, colW, hh); }
    const lc = c === COL.muted ? COL.ink : c;
    if (narrow) {                                                 // name over value; labels never overlap when bands are thin
      const cy = Math.max(y + hh / 2 - 8, ly + 34); ly = cy;
      label(x2 + colW + 6, cy, name, lc); label(x2 + colW + 6, cy + 16, pc(tot), lc);
    } else {
      const cy = Math.max(y + Math.max(hh, 12) / 2, ly + 16); ly = cy;
      label(x2 + colW + 8, cy, `${name} ${pc(tot)}`, lc);
    }
    y += hh + gap;
  }
  if (!r.sustains) label(W / 2, top + hT / 2, 'X-rays exceed the charged heating: no burn', COL.heat, 'center', 14);
  label(12, 18, narrow ? 'Energy budget' : 'Energy budget: where each watt of fusion goes', COL.ink, 'left', 13);
  if (r.sustains && W < 520) {
    label(12, 36, `Wayfarer: ${big(r.radiator_multiple)}× more heat than`, COL.heat, 'left', 11);
    label(12, 52, `the drive's radiators reject`, COL.heat, 'left', 11);
  } else label(12, 36, r.sustains ? `Wayfarer: ${big(r.radiator_multiple)}× more heat than the drive's radiators reject` : '', COL.heat, 'left', 11);
  // a few dots flowing along the thrust band, so the budget reads as a flow
  if (playing && r.thrust > 0) for (let i = 0; i < 6; i++) {
    const f = ((t / 2600 + i / 6) % 1), xx = x1 + colW + f * (x2 - x1 - colW);
    dot(xx, top + 4 + (r.thrust * scale - 8) * ((i * 0.37) % 1), 1.8, COL.thrust);
  }
}
function draw(t) {
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = COL.bg; ctx.fillRect(0, 0, W, H);
  if (S.view === 'reaction') drawReaction(); else if (S.view === 'engine') drawEngine(); else drawBudget(t);
  stats.frames++;
}
function loop() {
  cancelAnimationFrame(raf);
  raf = requestAnimationFrame(function step(t) {
    if (!playing || !visible || document.hidden) { last = 0; return; }
    const dt = last ? Math.min(0.05, (t - last) / 1000) : 0.016;
    last = t;
    update(dt); draw(t);
    raf = requestAnimationFrame(step);
  });
}

// ---- start ---------------------------------------------------------------------------------------------------------------------
async function start() {
  D = window.FUSION_INLINE || await (await fetch('fusion.json')).json();
  S.d = D.axes.d_share.indexOf(D.reference.d_share); S.t = D.axes.Ti.indexOf(D.reference.Ti);
  S.x = D.constants.photon_exposure_ref;
  readHash();
  size(); wire(); sync();
  if (reduced) { for (let i = 0; i < 120; i++) update(1 / 30); draw(0); $('play').textContent = '▶'; $('play').setAttribute('aria-label', 'Play'); }
  else loop();
  window.__fusion = { ready: true, data: D, evaluate, keyOf, state: S, stats, get result() { return R; },
    set: o => { Object.assign(S, o); sync(); } };
}
start().catch(err => {
  evcap.innerHTML = `<b>The explainer could not start</b><span>${esc(err.message || err)}. The numbers beside it still read from the page.</span>`;
  window.__fusion = { ready: false, error: String(err) };
});
