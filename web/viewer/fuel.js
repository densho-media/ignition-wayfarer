// Fuel & Propellant System drawer (owner brief 2026-11-18, FPS V0): the installed feed train isolated in its species colours (M1), flow
// dots along every pipe (M2) and the operating states (M3). Everything comes from build.fuel_file (fuel_system.web: the pipes as runtime
// polylines, each state's flow fractions and the flows, thrust and exhaust velocity the shared numbers give for it). CONCEPTUAL display:
// dot speed and spacing are display values, not line velocities, and nothing here is a fluid simulation. Loaded on first use only.
// Cost: one instanced draw call for every dot (a few hundred instances), one fetch of about 20 kB; no change to the imported meshes.
const fmt = (v, d = 2) => v === null || v === undefined ? '–' : Number(v).toLocaleString('en', { maximumFractionDigits: d, minimumFractionDigits: d });
const SPECIES_LABEL = { deuterium: 'Deuterium (fusion fuel)', 'helium-3': 'Helium-3 (second fuel, canon)', hydrogen: 'Hydrogen (reaction mass)',
                        helium: 'Helium (purge)' };

export function createFuel({ THREE, scene, byId, records, panel, update, changed, frameIds }) {
  let data = null, dots = null, state = 'STANDBY', h2 = null, isolated = false;
  const lines = [];                     // { path, species, seg: [[a, b, len]], length, n, offset }
  const tmp = new THREE.Object3D(), col = new THREE.Color();

  async function load(build) {
    if (data) return true;
    data = build?.fuel_file ? await fetch(build.fuel_file).then(r => r.ok ? r.json() : null).catch(() => null) : null;
    if (!data) return false;
    const spacing = data.display.dot_spacing_m;
    let total = 0;
    for (const l of data.lines) {
      const seg = [];
      let length = 0;
      for (let i = 1; i < l.points.length; i++) {
        const a = new THREE.Vector3(...l.points[i - 1]), b = new THREE.Vector3(...l.points[i]), d = a.distanceTo(b);
        seg.push([a, b, d, length]); length += d;
      }
      const n = Math.max(2, Math.floor(length / spacing));
      lines.push({ name: l.name, path: l.path, species: l.species, seg, length, n, offset: total });
      total += n;
    }
    const r = data.display.dot_radius_m;
    dots = new THREE.InstancedMesh(new THREE.SphereGeometry(r, 10, 6), new THREE.MeshBasicMaterial({ toneMapped: false }), total);
    dots.name = 'FPS_FlowDots'; dots.frustumCulled = false; dots.renderOrder = 5;
    for (let i = 0; i < total; i++) dots.setColorAt(i, col.setRGB(1, 1, 1));
    scene.add(dots);
    render();
    return true;
  }

  const ids = () => new Set(Object.values(data.nodes).flat());
  // the aft feed train (everything but the refuelling receptacle on the farm deck), for framing
  const aft = () => new Set(Object.entries(data.nodes).filter(([n]) => !n.startsWith('FPS_Refuel')).flatMap(([, v]) => v));
  // M1: while isolated, every FPS object takes its species colour (a presentation material; the exported one is put back after)
  const tints = {};
  function tint(on) {
    for (const [name, nodes] of Object.entries(data.nodes)) {
      const rgb = data.colors[data.objects[name]?.species] || data.colors.service;
      const key = rgb.join(',');
      tints[key] ??= new THREE.MeshStandardMaterial({ color: new THREE.Color(...rgb), emissive: new THREE.Color(...rgb).multiplyScalar(0.35),
                                                      roughness: 0.55, metalness: 0.1, side: THREE.DoubleSide });
      for (const id of nodes) for (const m of byId.get(id)?.meshes || []) {
        if (on && !m.userData.fpsMaterial) { m.userData.fpsMaterial = m.userData.material; m.userData.material = tints[key]; }
        if (!on && m.userData.fpsMaterial) { m.userData.material = m.userData.fpsMaterial; delete m.userData.fpsMaterial; }
      }
    }
  }
  const current = () => {
    const s = data.states.find(x => x.id === state);
    if (state !== 'THROTTLE' || h2 === null) return s;
    return data.throttle.find(x => x.flow.h2 === h2) || s;
  };

  // One line's dot speed (display m/s) and colour for the current state: the hydrogen lines carry helium while they are purged.
  function flowOf(l, st) {
    const f = st.flow, v = data.display.dot_speed_m_s;
    if (l.path === 'h2' && f.h2 > 0) return [v * Math.min(f.h2, 3), data.colors.hydrogen];
    if (l.path === 'h2' && f.purge > 0) return [v * f.purge, data.colors.helium];
    if (l.path === 'purge') return [v * f.purge, data.colors.helium];
    const k = { fuel: f.fuel, refuel: f.refuel, vent: f.vent }[l.path] || 0;
    return [v * Math.min(k, 3), data.colors[l.species] || data.colors.service];
  }

  let clock = 0;
  function tick(dt) {
    if (!dots || !dots.visible) return;
    clock += dt;
    const st = current();
    for (const l of lines) {
      const [speed, rgb] = flowOf(l, st);
      for (let k = 0; k < l.n; k++) {
        const i = l.offset + k;
        if (speed <= 0) { tmp.scale.setScalar(0); tmp.updateMatrix(); dots.setMatrixAt(i, tmp.matrix); continue; }
        // wrap the dot's distance along the line (the header ring is a loop, every other line restarts at its source)
        const s = ((k / l.n) * l.length + clock * speed) % l.length;
        const seg = l.seg.find(q => s <= q[3] + q[2]) || l.seg[l.seg.length - 1];
        tmp.position.lerpVectors(seg[0], seg[1], seg[2] ? (s - seg[3]) / seg[2] : 0);
        tmp.scale.setScalar(1); tmp.updateMatrix();
        dots.setMatrixAt(i, tmp.matrix);
        dots.setColorAt(i, col.setRGB(...rgb));
      }
    }
    dots.instanceMatrix.needsUpdate = true;
    if (dots.instanceColor) dots.instanceColor.needsUpdate = true;
  }

  function setState(name, factor = null) {
    if (!data?.states.some(s => s.id === name)) return;
    state = name; h2 = name === 'THROTTLE' ? (factor ?? h2 ?? data.states.find(s => s.id === name).flow.h2) : null;
    render(); changed();
  }
  function isolate(on) {
    isolated = on;
    tint(on);
    update(s => { s.focus = on ? { kind: 'set', id: 'Fuel & Propellant System', ids: ids() } : (s.focus?.kind === 'set' ? null : s.focus); })
      .then(() => { if (on) frameIds(aft()); render(); changed(); });
  }
  function show(on) { if (dots) dots.visible = on; }

  function render() {
    if (!data) return;
    const st = current();
    const body = panel.querySelector('.fuel-body');
    body.innerHTML = '';
    const row = (label, el) => { const d = document.createElement('div'); d.className = 'row'; const s = document.createElement('span'); s.textContent = label; d.append(s, el); body.append(d); return d; };
    const chips = document.createElement('span'); chips.className = 'chips';
    const iso = document.createElement('button'); iso.textContent = isolated ? 'Whole ship' : 'Isolate feed train';
    iso.title = 'Show only the fuel and propellant feed train, the rest as a ghost, and frame it';
    iso.setAttribute('aria-pressed', String(isolated)); iso.addEventListener('click', () => isolate(!isolated));
    chips.append(iso); row('View', chips);
    const states = document.createElement('div'); states.className = 'row buttons fuel-states'; states.setAttribute('role', 'group');
    states.setAttribute('aria-label', 'Operating state');
    for (const s of data.states) {
      const b = document.createElement('button'); b.textContent = s.label; b.dataset.fuel = s.id; b.title = s.text;
      b.setAttribute('aria-pressed', String(s.id === state)); b.addEventListener('click', () => setState(s.id));
      states.append(b);
    }
    body.append(states);
    if (state === 'THROTTLE') {
      const t = document.createElement('span'); t.className = 'chips';
      for (const r of data.throttle) {
        const b = document.createElement('button'); b.textContent = `×${r.flow.h2}`; b.dataset.h2 = r.flow.h2;
        b.title = `Hydrogen at ${r.flow.h2} × the operating-point flow: ${fmt(r.thrust_MN)} MN at ${fmt(r.ve_km_s, 0)} km/s`;
        b.setAttribute('aria-pressed', String(r.flow.h2 === st.flow.h2)); b.addEventListener('click', () => setState('THROTTLE', r.flow.h2));
        t.append(b);
      }
      row('Hydrogen', t);
    }
    const p = document.createElement('p'); p.className = 'note fuel-text'; p.textContent = st.text; body.append(p);
    const dl = document.createElement('dl'); dl.className = 'fuel-readout';
    const item = (k, v) => { const a = document.createElement('dt'); a.textContent = k; const b = document.createElement('dd'); b.textContent = v; dl.append(a, b); };
    item('Deuterium', `${fmt(st.deuterium_kg_s, 3)} kg/s`); item('Helium-3', `${fmt(st.he3_kg_s, 3)} kg/s`); item('Hydrogen', `${fmt(st.h2_kg_s, 3)} kg/s`);
    item('Thrust', `${fmt(st.thrust_MN)} MN`); item('Exhaust velocity', st.ve_km_s ? `${fmt(st.ve_km_s, 0)} km/s` : '–');
    item('Jet power', `${fmt(st.jet_TW, 0)} TW`);
    body.append(dl);
    const ul = document.createElement('ul'); ul.className = 'fuel-legend';
    for (const sp of ['deuterium', 'helium-3', 'hydrogen', 'helium']) {
      const li = document.createElement('li'); const sw = document.createElement('span'); sw.className = 'swatch';
      const c = data.colors[sp].map(v => Math.round(255 * Math.pow(v, 1 / 2.2)));
      sw.style.background = `rgb(${c.join(',')})`;
      const t = data.numbers.mission_t[sp];
      li.append(sw, SPECIES_LABEL[sp] + (t ? ` · ${fmt(t, 0)} t carried` : ''));
      ul.append(li);
    }
    body.append(ul);
    const n = document.createElement('p'); n.className = 'note';
    n.textContent = `${data.status} display of FPS ${data.version} (${data.engineering_status}): flows are fractions of the B01 operating point `
      + `(${fmt(data.numbers.thrust_MN)} MN, ${fmt(data.numbers.ve_km_s, 0)} km/s); dot speed is a display value, not a line velocity. `
      + `Deuterium and helium-3 are metered separately to the cluster bay; hydrogen runs its own path to each engine. `
      + `Engine-side injection and target fabrication stay OPEN interfaces.`;
    body.append(n);
  }

  const hash = () => data && state !== 'STANDBY' ? `fuel=${state}${state === 'THROTTLE' && h2 !== null ? '.' + h2 : ''}${isolated ? '.iso' : ''}` : '';
  async function openFrom(h, build) {
    const m = /(?:^|[#&])fuel=([A-Z]+)(?:\.([\d.]+))?(\.iso)?/.exec(h);
    if (!m || !(await load(build))) return false;
    state = data.states.some(s => s.id === m[1]) ? m[1] : 'STANDBY';
    h2 = state === 'THROTTLE' && m[2] ? Number(m[2]) : null;
    if (m[3]) isolate(true); else render();
    return true;
  }
  return { load, tick, setState, isolate, show, hash, openFrom, state: () => ({ state, h2, isolated, dots: dots?.count ?? 0, data }) };
}
