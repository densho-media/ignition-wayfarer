// Fuel & Propellant System drawer (owner briefs 2026-11-18 V0, 2026-11-19 V1). Everything comes from build.fuel_file (fuel_system.web):
// the modeled pipes as runtime polylines (the farm's outlets, ring mains and transfer trunks, the aft feed train, the cluster's target-feed
// lines and every engine's target feed, injection line and injector ports), each state's flow fractions and the flows, thrust and exhaust
// velocity the shared numbers give for it, the energy ledger and the interfaces where a flow ends unresolved.
// Views: the ship as built (V0), the whole propulsion chain, fuel flow, propellant flow and the combined operation (which also sets the
// drive state). Dots run only on the modeled topology; the one leg that is not modeled (target fabrication inside the cluster bay) is drawn
// dashed and named so. CONCEPTUAL display: dot speed and spacing are display values, not line velocities, nothing here is a fluid
// simulation. Loaded on first use only. Cost: one instanced draw call for every dot, one for the open-end markers, one dashed line per
// conceptual leg; one fetch of about 70 kB; no change to the imported meshes.
const fmt = (v, d = 2) => v === null || v === undefined ? '–' : Number(v).toLocaleString('en', { maximumFractionDigits: d, minimumFractionDigits: d });
const SPECIES_LABEL = { deuterium: 'Deuterium (fusion fuel)', 'helium-3': 'Helium-3 (fusion fuel, D–³He baseline)', target: 'Filled targets (D–³He)',
                        hydrogen: 'Hydrogen (reaction mass)', helium: 'Helium (purge)' };
const GROUP_LABEL = { farm: 'Farm', transfer: 'Transfer trunks', aft: 'Aft feed train', cluster: 'Cluster bay, frame and lines', engine: 'Engines' };

export function createFuel({ THREE, scene, byId, records, panel, update, changed, frameIds, pick, drive }) {
  let data = null, dots = null, ends = null, state = 'STANDBY', h2 = null, view = 'ship';
  const lines = [];                     // { name, path, species, group, modeled, seg: [[a, b, len, at]], length, n, offset }
  const dashed = [];
  const tmp = new THREE.Object3D(), col = new THREE.Color();

  async function load(build) {
    if (data) return true;
    data = build?.fuel_file ? await fetch(build.fuel_file).then(r => r.ok ? r.json() : null).catch(() => null) : null;
    if (!data) return false;
    data.views ||= [];
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
      lines.push({ name: l.name, path: l.path, species: l.species, group: l.group || 'aft', modeled: l.modeled !== false, seg, length, n, offset: total });
      total += n;
      if (l.modeled === false) {      // a conceptual leg: a dashed line, no pipe exists there
        const g = new THREE.BufferGeometry().setFromPoints(l.points.map(p => new THREE.Vector3(...p)));
        const m = new THREE.Line(g, new THREE.LineDashedMaterial({ color: new THREE.Color(...(data.colors[l.species] || data.colors.service)), dashSize: 0.6, gapSize: 0.4, toneMapped: false }));
        m.computeLineDistances(); m.name = 'FPS_Conceptual_' + l.name; m.visible = false; m.renderOrder = 5; scene.add(m);
        dashed.push({ line: m, species: l.species, group: l.group });
      }
    }
    const r = data.display.dot_radius_m;
    dots = new THREE.InstancedMesh(new THREE.SphereGeometry(r, 10, 6), new THREE.MeshBasicMaterial({ toneMapped: false }), total);
    dots.name = 'FPS_FlowDots'; dots.frustumCulled = false; dots.renderOrder = 5;
    for (let i = 0; i < total; i++) dots.setColorAt(i, col.setRGB(1, 1, 1));
    scene.add(dots);
    const oe = data.open_ends || [];
    if (oe.length) {                    // where a modeled flow stops at an unresolved interface
      ends = new THREE.InstancedMesh(new THREE.OctahedronGeometry(0.45), new THREE.MeshBasicMaterial({ color: 0xffc04d, toneMapped: false, wireframe: true }), oe.length);
      ends.name = 'FPS_OpenEnds'; ends.frustumCulled = false; ends.renderOrder = 6;
      oe.forEach((e, i) => { tmp.position.set(...e.at); tmp.scale.setScalar(1); tmp.updateMatrix(); ends.setMatrixAt(i, tmp.matrix); });
      ends.visible = false; scene.add(ends);
    }
    render();
    return true;
  }

  const V = () => data.views.find(v => v.id === view) || null;
  // a view selects by species and (V1.1) optionally by chain group: the fabrication view is the cluster bay, the assembly view adds the frame and engines
  const inView = (species, group) => { const v = V(); return !v || (v.species.includes(species) && (!v.groups || !group || v.groups.includes(group))); };
  const names = () => Object.keys(data.nodes).filter(n => { const o = data.objects[n] || {}; const g = groupOf(n);
    return inView(o.species || 'service', g) || (o.species === 'service' && (!V()?.groups || V().groups.includes(g))); });
  const idsOf = list => new Set(list.flatMap(n => data.nodes[n] || []));
  // the aft feed train only (V0 isolation framing): everything but the farm and the refuelling receptacle
  const aft = () => idsOf(Object.keys(data.nodes).filter(n => !n.startsWith('FPS_Refuel') && !['farm', 'transfer'].includes(groupOf(n))));
  const groupOf = n => data.objects[n]?.group || legacyGroup(n);
  const legacyGroup = n => n.startsWith('Fuel_') || n.startsWith('FPS_Refuel') || n.startsWith('FPS_H2_Crossover') || n === 'FPS_Farm_Flanges'
    ? (n.startsWith('Fuel_Transfer') ? 'transfer' : 'farm')
    : n.startsWith('FPS_Feedthrough') || n.startsWith('FPS_Tank_Inlet') ? 'transfer' : n.startsWith('CL_') ? 'cluster' : n.startsWith('FPS_N') ? 'engine' : 'aft';
  // While a view is on, every object in it takes its species colour (a presentation material; the exported one is put back after).
  const tints = {};
  function tint(on) {
    for (const [name, nodes] of Object.entries(data.nodes)) {
      if (['structure', 'engine'].includes(data.objects[name]?.species)) continue;   // the frame and engines keep their materials and drive animation
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
    if (!inView(l.species, l.group) || (view === 'ship' && !['aft', 'engine'].includes(l.group) && l.path !== 'refuel')) return [0, null];
    if (l.path === 'h2' && f.h2 > 0) return [v * Math.min(f.h2, 3), data.colors.hydrogen];
    if (l.path === 'h2' && f.purge > 0 && l.group !== 'farm' && l.group !== 'transfer') return [v * f.purge, data.colors.helium];
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
        // wrap the dot's distance along the line (ring mains and the header are loops, every other line restarts at its source)
        const s = ((k / l.n) * l.length + clock * speed) % l.length;
        const seg = l.seg.find(q => s <= q[3] + q[2]) || l.seg[l.seg.length - 1];
        tmp.position.lerpVectors(seg[0], seg[1], seg[2] ? (s - seg[3]) / seg[2] : 0);
        tmp.scale.setScalar(l.modeled ? 1 : 0.6); tmp.updateMatrix();
        dots.setMatrixAt(i, tmp.matrix);
        dots.setColorAt(i, col.setRGB(...rgb));
      }
    }
    dots.instanceMatrix.needsUpdate = true;
    if (dots.instanceColor) dots.instanceColor.needsUpdate = true;
  }

  function linkDrive() {
    const v = V(), st = data.states.find(x => x.id === state);
    if (v?.drive && drive && st?.drive) drive(st.drive);
  }
  function setState(name, factor = null) {
    if (!data?.states.some(s => s.id === name)) return;
    state = name; h2 = name === 'THROTTLE' ? (factor ?? h2 ?? data.states.find(s => s.id === name).flow.h2) : null;
    linkDrive(); render(); changed();
  }
  function setView(id) {
    view = data.views.some(v => v.id === id) ? id : 'ship';
    const on = view !== 'ship';
    tint(on);
    for (const d of dashed) d.line.visible = on && inView(d.species, d.group);
    if (ends) ends.visible = on;
    update(s => { s.focus = on ? { kind: 'set', id: 'Fuel & Propellant System', ids: idsOf(names()) } : (s.focus?.kind === 'set' ? null : s.focus); })
      .then(() => { if (on) frameIds(idsOf(names())); linkDrive(); render(); changed(); });
  }
  // V0 compatibility: isolate(true) is the aft-train view framed as before
  function isolate(on) { setView(on ? 'whole' : 'ship'); if (on) setTimeout(() => frameIds(aft()), 0); }
  function show(on) {
    if (dots) dots.visible = on;
    if (ends) ends.visible = on && view !== 'ship';
    for (const d of dashed) d.line.visible = on && view !== 'ship' && inView(d.species, d.group);
  }

  function render() {
    if (!data) return;
    const st = current();
    const body = panel.querySelector('.fuel-body');
    body.innerHTML = '';
    const row = (label, el) => { const d = document.createElement('div'); d.className = 'row'; const s = document.createElement('span'); s.textContent = label; d.append(s, el); body.append(d); return d; };
    const views = document.createElement('div'); views.className = 'row buttons fuel-states'; views.setAttribute('role', 'group'); views.setAttribute('aria-label', 'View');
    for (const v of [{ id: 'ship', label: 'Ship', text: 'The ship as built, with the flows on the aft feed train and the engines' }, ...data.views]) {
      const b = document.createElement('button'); b.textContent = v.label; b.dataset.fuelView = v.id; b.title = v.text;
      b.setAttribute('aria-pressed', String(v.id === view)); b.addEventListener('click', () => setView(v.id)); views.append(b);
    }
    row('View', views);
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
    const p = document.createElement('p'); p.className = 'note fuel-text'; p.textContent = (V()?.text ? V().text + ' ' : '') + st.text; body.append(p);
    const dl = document.createElement('dl'); dl.className = 'fuel-readout';
    const item = (k, v) => { const a = document.createElement('dt'); a.textContent = k; const b = document.createElement('dd'); b.textContent = v; dl.append(a, b); };
    item('Deuterium', `${fmt(st.deuterium_kg_s, 3)} kg/s`); item('Helium-3', `${fmt(st.he3_kg_s, 3)} kg/s`); item('Hydrogen', `${fmt(st.h2_kg_s, 3)} kg/s`);
    item('Thrust', `${fmt(st.thrust_MN)} MN`); item('Exhaust velocity', st.ve_km_s ? `${fmt(st.ve_km_s, 0)} km/s` : '–');
    item('Jet power', `${fmt(st.jet_TW, 0)} TW`);
    const e = data.energy;
    if (e && V()?.drive) {             // the combined view: where the fusion power goes (shares of it at the operating point)
      item('Fusion power', `${fmt(e.fusion_TW * (st.flow.fuel || 0), 0)} TW`);
      item(`Photons (${e.regime.toLowerCase()})`, `${fmt(100 * e.shares.photon, 1)} %`); item('Neutrons', `${fmt(100 * e.shares.neutron, 1)} %`);
      item('Charged debris', `${fmt(100 * e.shares.charged, 1)} % (current result)`);
      if (!e.reconciliation) item('Canon jet share', `${fmt(100 * e.jet_canon, 0)} %`); else item('B01 jet share', `${fmt(100 * e.jet_canon, 0)} % (not claimed)`);
    }
    body.append(dl);
    if (e && V()?.drive) {
      const n = document.createElement('p'); n.className = 'note' + (e.closes ? '' : ' warn');
      const r = e.reconciliation;
      n.textContent = r
        ? `${r.note} Engine point versus ship: one gap, ×${fmt(r.power_gap, 2)} in fusion power (yield × rate; ${fmt(r.closing_rate_kHz, 1)} kHz at today's yield would close it). `
          + `The V1 ×${fmt(r.v1_quoted, 1)} fuel gap set reacted fuel against the pulse's exhaust mass (${fmt(r.pulse_exhaust_mg, 2)} mg, of which ${fmt(r.pulse_reacted_mg, 2)} mg reacts): like for like it is the same ×${fmt(r.power_gap, 2)}. `
          + `OPEN with the engine workstream; hydrogen heating by the debris is SPECULATIVE.`
        : `Energy ${e.closes ? 'closes' : 'does not close'} at the ${e.regime.toLowerCase()} burn: charged debris ${fmt(100 * e.shares.charged, 1)} % against the `
        + `${fmt(100 * e.jet_canon, 0)} % jet share. The engines' own pulse point (${fmt(e.engine_pulse_mg, 2)} mg at ${fmt(e.engine_pulse_Hz, 0)} Hz, ${fmt(e.engine_kg_s * 1e3, 0)} g/s each) `
        + `carries 1/${fmt(e.ratio, 1)} of the ship operating point (${fmt(e.ship_fuel_per_engine_kg_s * 1e3, 0)} g/s of fuel each): OPEN with the engine workstream. `
        + `Hydrogen heating by the debris is SPECULATIVE.`;
      body.append(n);
    }
    const ul = document.createElement('ul'); ul.className = 'fuel-legend';
    for (const sp of ['deuterium', 'helium-3', 'target', 'hydrogen', 'helium']) {
      if (!data.colors[sp] || (view !== 'ship' && !inView(sp))) continue;
      const li = document.createElement('li'); const sw = document.createElement('span'); sw.className = 'swatch';
      const c = data.colors[sp].map(v => Math.round(255 * Math.pow(v, 1 / 2.2)));
      sw.style.background = `rgb(${c.join(',')})`;
      const t = data.numbers.mission_t[sp];
      li.append(sw, SPECIES_LABEL[sp] + (t ? ` · ${fmt(t, 0)} t carried` : ''));
      ul.append(li);
    }
    body.append(ul);
    if (view !== 'ship') {
      // component inspection: every object in the view, grouped along the chain; choosing one frames and selects it
      const sel = document.createElement('select'); sel.className = 'fuel-components'; sel.setAttribute('aria-label', 'Component');
      const o0 = document.createElement('option'); o0.textContent = `Components (${names().length})`; o0.value = ''; sel.append(o0);
      const byGroup = {};
      for (const n of names()) (byGroup[groupOf(n)] ||= []).push(n);
      for (const g of ['farm', 'transfer', 'aft', 'cluster', 'engine']) {
        if (!byGroup[g]) continue;
        const og = document.createElement('optgroup'); og.label = GROUP_LABEL[g];
        for (const n of byGroup[g].sort()) {
          const o = document.createElement('option'); o.value = n; o.textContent = n + (data.objects[n]?.owner ? ` · ${data.objects[n].owner}` : ''); og.append(o);
        }
        sel.append(og);
      }
      sel.addEventListener('change', () => { const ids = data.nodes[sel.value]; if (ids?.length) { frameIds(new Set(ids)); pick?.(ids[0]); } });
      row('Inspect', sel);
      const oe = data.open_ends || [];
      if (oe.length) {
        const d = document.createElement('details'); const sm = document.createElement('summary');
        sm.textContent = `${oe.length} flows end at unresolved interfaces (amber markers)`; d.append(sm);
        const list = document.createElement('ul'); list.className = 'fuel-ends';
        for (const x of oe) { const li = document.createElement('li'); li.textContent = `${x.name}: ${x.note}`; list.append(li); }
        d.append(list); body.append(d);
      }
    }
    const n = document.createElement('p'); n.className = 'note';
    n.textContent = `${data.status} display of FPS ${data.version} (${data.engineering_status}): flows are fractions of the B01 operating point `
      + `(${fmt(data.numbers.thrust_MN)} MN, ${fmt(data.numbers.ve_km_s, 0)} km/s); dot speed is a display value, not a line velocity. `
      + (dashed.length ? `Dots run only on modeled pipes; the dashed leg through the cluster bay is target fabrication, not modeled. ` : `Dots run only on modeled pipes; target fabrication in the bay core is a V1.1 blockout (its process SPECULATIVE). `)
      + `The engine-side feeds and injection are candidates for the engine workstream.`;
    body.append(n);
  }

  const hash = () => data && (state !== 'STANDBY' || view !== 'ship')
    ? `fuel=${state}${state === 'THROTTLE' && h2 !== null ? '.' + h2 : ''}${view !== 'ship' ? '.' + view : ''}` : '';
  async function openFrom(h, build) {
    const m = /(?:^|[#&])fuel=([A-Z]+)(?:\.([\d.]+))?(?:\.([a-z0-9]+))?/.exec(h);
    if (!m || !(await load(build))) return false;
    state = data.states.some(s => s.id === m[1]) ? m[1] : 'STANDBY';
    h2 = state === 'THROTTLE' && m[2] ? Number(m[2]) : null;
    const v = m[3] === 'iso' ? 'whole' : m[3];
    if (v && v !== 'ship') setView(v); else render();
    return true;
  }
  return { load, tick, setState, setView, isolate, show, hash, openFrom,
           state: () => ({ state, h2, view, isolated: view !== 'ship', dots: dots?.count ?? 0, ends: ends?.count ?? 0, conceptual: dashed.length, data }) };
}
