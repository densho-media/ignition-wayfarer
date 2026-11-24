// Simulations · Fusion Ignition: from nucleus to nozzle (tools/story_ignite.py writes engineering/fusion-ignition/ and its data from
// lab/studies/fusion-ignition). Eleven stages (the Heat stage in six steps, from the burn to space), from the ship's need for an engine down to one D-3He reaction and back out to thrust and the
// modeled failures. The page computes no new spacecraft facts: it draws the study's numbers and interpolates its precomputed grids.
// Geometry: the schematic ship is drawn from a handful of measured numbers; the engines are Explore Ship's engine inspection parts
// (build.engine_file, int16 positions), one InstancedMesh per functional category (12 draw calls for four engines); the field lines are
// the viewer's lazily fetched vacuum-field file. The nuclear and plasma scales are 2-D drawings on a second canvas (ILLUSTRATIVE).
// three.js loads only with the 3D view (load()); the 2-D stages, the text and the numbers work without it.
let THREE, OrbitControls, mergeGeometries, toCreasedNormals;

const VIEWER = '../../viewer/';
const DATA = 'fusion_ignition.json';
const $ = id => document.getElementById(id);
const root = $('fi'), stage = $('stage'), canvas = $('fi-view'), c2 = $('fi-2d'), gate = $('gate'), cstatus = $('cstatus'), hud = $('hud');
const evcap = $('evcap'), scaleEl = $('scale'), tip = $('tip'), readEl = $('read'), partsEl = $('parts'), labEl = $('lab');
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const touch = matchMedia('(pointer: coarse)').matches;
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim() || '#ccc';
const COL = {};
['--good', '--bad', '--warn', '--info', '--accent', '--accent-2', '--muted', '--ink', '--ink-strong', '--fn-DEUTERIUM', '--fn-HELIUM3', '--fn-HYDROGEN',
  '--wf-ignition', '--wf-plasma', '--wf-violet', '--line-strong'].forEach(k => { COL[k.slice(2)] = css(k); });
COL.neutron = '#A9B4BF';

// ---- formatting -----------------------------------------------------------------------------------------------------------------------
const W = w => w >= 1e11 ? `${(w / 1e12).toLocaleString('en', { maximumFractionDigits: 1 })} TW` : w >= 1e8 ? `${(w / 1e9).toFixed(1)} GW` : w >= 1e6 ? `${(w / 1e6).toFixed(0)} MW` : `${(w / 1e3).toFixed(0)} kW`;
const X = r => r >= 100 ? `${Math.round(r).toLocaleString('en')}×` : `${r.toPrecision(3)}×`;
const E = v => v >= 1e4 || (v < 1e-2 && v > 0) ? v.toExponential(2).replace('e+', 'e') : String(+v.toPrecision(3));
const TS = s => s < 1e-6 ? `${(s * 1e9).toPrecision(2)} ns` : s < 1 ? `${(s * 1e3).toPrecision(3)} ms` : `${s.toPrecision(3)} s`;
const pct = v => `${(100 * v).toFixed(v < 0.1 ? 1 : 0)} %`;
const CHIP = { SPEC: ['SPEC', 'spec'], CALCULATED: ['CALCULATED', 'calculated'], SAMPLED: ['CALCULATED', 'sampled'], IMPORTED: ['WORKING', 'imported'],
  'MODEL-BASED': ['ASSUMED', 'model-based'], ILLUSTRATIVE: ['ASSUMED', 'illustrative'], OPEN: ['OPEN', 'open'], SPECULATIVE: ['SPECULATIVE', 'speculative'] };
const chip = c => `<span class="st st-${CHIP[c][0]}">${CHIP[c][1]}</span>`;

// ---- stages -----------------------------------------------------------------------------------------------------------------------------
const LADDER = { need: 0, hardware: 1, magnets: 1, fuel: 2, nucleus: 7, many: 5, ignition: 4, nozzle: 1, losses: 0, thermal: 1, lab: 1 };   // the scale ruler's tick per stage
const ladderEl = $('ladder'), ctlEl = $('fictl');
const STAGES = ['need', 'hardware', 'magnets', 'fuel', 'nucleus', 'many', 'ignition', 'nozzle', 'losses', 'thermal', 'lab'];
const DUR = { need: 11, hardware: 14, magnets: 14, fuel: 12, nucleus: 22, many: 16, ignition: 18, nozzle: 22, losses: 20, thermal: 36, lab: 1e9 };
const TWO_D = new Set(['nucleus', 'many', 'ignition']);
const SCALE = { need: ['Spacecraft scale', '100 m'], hardware: ['Engine scale', '10 m'], magnets: ['Engine scale', '10 m'], fuel: ['Burn point', '1 m · target mm'],
  nucleus: ['Nuclear scale', '~10 fm · illustrative'], many: ['Plasma scale', 'statistical · not to scale'], ignition: ['Plasma scale', 'energy balance'],
  nozzle: ['Engine scale', '10 m'], losses: ['Engine and ship', '10–100 m'], thermal: ['Engine scale', '1–10 m'], lab: ['Engine scale', '10 m'] };

let D = null, M = null;
let si = 0, u = 0, playing = false, view = 'concept', last = 0, dirty = true, ready = false;
const layers = { field: true, fuel: true, paths: true, rad: true, heat: true, problems: true, cut: false, ship: true, mirrors: true, cooling: true, flow: true };
const lab = { variant: 'C1', field: '1', d: 0.5, Ti: 100, mode: 'thermal', pol: 'none', armour: 0.22, mirror: 0, rhoR: null, Ti0: null, mix: 1, rate: 1, h2: 0 };
let focusCat = null, catMode = 'highlight';
window.__fi = { ready: false };

// ---- three.js state -----------------------------------------------------------------------------------------------------------------------
let renderer, scene, camera, controls, shipGroup, engineGroup, fieldGroup, pathGroup, fxGroup, radGroup, markerEls = [];
let catMeshes = {}, catMats = {}, engineMats = [], burnW = [], N1 = null, cutPlane = null, plume, plasmaPts, targetMesh, beams, h2pts, thrustArrow;
let fieldLines = [], pathLines = [], camFrom = null, camTo = null, camT = 1, userCam = false;
const BURN = -18.8;

function v3(a) { return new THREE.Vector3(a[0], a[1], a[2]); }
function shipPt(x, yb, zb) { return new THREE.Vector3(x, zb, -yb); }       // Blender ship (x, y, z) -> runtime

// ---- load ------------------------------------------------------------------------------------------------------------------------------
async function boot() {
  D = await fetch(DATA).then(r => r.json());
  lab.rhoR = D.plasma.burn.rhoR_design; lab.Ti0 = D.plasma.burn.Ti_design;
  buildLab(); setStage(0, true);
  $('load').addEventListener('click', load);
  window.__fi.data = { variants: D.channels.variants, heat_over: D.ledger.pulse.heat_over, thrust_N: D.ledger.pulse.thrust_N };
  if (new URLSearchParams(location.search).has('autostart')) load(); else requestAnimationFrame(frame2d);
}
// Before the 3D view is loaded the 2-D stages still play; a 3D stage waits at its load button.
function frame2d(now) {
  if (ready) return;
  const t = now / 1000, dt = last ? Math.min(0.1, t - last) : 0; last = t;
  const id = STAGES[si]; sdt = playing && !reduced ? dt : 0;
  if (playing && TWO_D.has(id)) {
    u += dt / DUR[id];
    if (u >= 1) { if (TWO_D.has(STAGES[si + 1])) setStage(si + 1); else { u = 1; playing = false; syncPlay(); } }
    $('scrub').value = Math.round(u * 1000);
  }
  sizeC2(); draw2d(t);
  requestAnimationFrame(frame2d);
}

async function load() {
  $('load').disabled = true; cstatus.hidden = false; cstatus.textContent = 'Loading the engine parts…';
  try {
    [THREE, { OrbitControls }, { mergeGeometries, toCreasedNormals }] = await Promise.all([import('three'),
      import('three/addons/controls/OrbitControls.js'), import('three/addons/utils/BufferGeometryUtils.js')]);
    ray = new THREE.Raycaster(); mouse = new THREE.Vector2();
    const build = await fetch(VIEWER + 'build.json', { cache: 'no-store' }).then(r => r.ok ? r.json() : null);
    if (!build?.engine_file) throw new Error('this build has no engine inspection file');
    M = await fetch(VIEWER + build.engine_file).then(r => r.json());
    const bin = await fetch(VIEWER + M.geometry.file).then(r => r.arrayBuffer());
    let field = null;
    if (M.magnet?.field_file) field = await fetch(VIEWER + M.magnet.field_file).then(r => r.ok ? r.json() : null).catch(() => null);
    init(bin, field);
    gate.hidden = true; cstatus.hidden = true; stage.classList.add('live'); stage.classList.remove('flat'); hud.hidden = false; ready = true;
    window.wos?.scenario?.({ label: 'FUSION', class: 'SIM' });   // short: a longer label overflows the ship line at 1280 px
    buildParts(); setStage(si, true); playing = !reduced; syncPlay();
    window.__fi.ready = true;
  } catch (err) {
    cstatus.textContent = `The 3D view could not start: ${err.message}. The text and numbers still hold.`; cstatus.classList.add('error');
    $('load').disabled = false; console.error(err);
  }
}

function init(bin, field) {
  renderer = new THREE.WebGLRenderer({ canvas, antialias: !touch, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, touch ? 1.5 : 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.localClippingEnabled = true;
  scene = new THREE.Scene(); scene.background = new THREE.Color(0x05070b);
  scene.add(new THREE.HemisphereLight(0x9fb4d8, 0x0a0c12, 0.9));
  const key = new THREE.DirectionalLight(0xfff1de, 2.4); key.position.set(-120, 160, 220); scene.add(key);
  const rim = new THREE.DirectionalLight(0x8aa6ff, 0.8); rim.position.set(200, -60, -160); scene.add(rim);
  camera = new THREE.PerspectiveCamera(38, 1, 0.3, 9000);
  controls = new OrbitControls(camera, canvas); controls.enableDamping = true; controls.dampingFactor = 0.08;
  controls.addEventListener('start', () => { userCam = true; });
  controls.addEventListener('change', () => { dirty = true; });

  engineMats = M.engines.map(e => new THREE.Matrix4().fromArray(e.matrix));
  burnW = engineMats.map(m => new THREE.Vector3(BURN, 0, 0).applyMatrix4(m));
  N1 = engineMats[0];
  const ax = new THREE.Vector3(1, 0, 0).transformDirection(N1), side = new THREE.Vector3(0, 0, 1).transformDirection(N1);
  cutPlane = new THREE.Plane().setFromNormalAndCoplanarPoint(side.clone().negate(), burnW[0]);
  window.__fi.axis = ax.toArray();

  buildShip();
  buildEngines(bin);
  buildField(field);
  buildPaths();
  buildFx();
  buildMarkers();
  buildThermal();
  stars();
  new ResizeObserver(() => { dirty = true; }).observe(stage);
  canvas.addEventListener('pointermove', hover);
  canvas.addEventListener('click', pick);
  renderer.setAnimationLoop(frame);
}

// ---- the ship (SCHEMATIC, from the measured numbers in the data) ----------------------------------------------------------------------------
function buildShip() {
  const S = D.ship; shipGroup = new THREE.Group(); scene.add(shipGroup);
  const mat = new THREE.MeshStandardMaterial({ color: 0x8a96a8, roughness: 0.8, metalness: 0.2, transparent: true, opacity: 0.55, depthWrite: false });
  const edge = new THREE.LineBasicMaterial({ color: 0x9fb4d8, transparent: true, opacity: 0.35 });
  const cyl = (x0, x1, r, m = mat, seg = 40) => {
    const g = new THREE.CylinderGeometry(r, r, x1 - x0, seg, 1, false); g.rotateZ(Math.PI / 2); g.translate((x0 + x1) / 2, 0, 0);
    const me = new THREE.Mesh(g, m); shipGroup.add(me); shipGroup.add(new THREE.LineSegments(new THREE.EdgesGeometry(g, 30), edge)); return me;
  };
  cyl(S.tank[0], S.tank[1], S.tank[2]);
  cyl(S.spine[0], S.spine[1], S.spine[2]);
  cyl(S.shield[0], S.shield[1], S.shield[2], new THREE.MeshStandardMaterial({ color: css('--fn-SHIELD'), roughness: 0.7, transparent: true, opacity: 0.35, depthWrite: false }), 64);
  const ring = new THREE.TorusGeometry(S.habitat[2], 2.2, 10, 72); ring.rotateY(Math.PI / 2); ring.translate((S.habitat[0] + S.habitat[1]) / 2, 0, 0);
  shipGroup.add(new THREE.Mesh(ring, new THREE.MeshStandardMaterial({ color: css('--fn-HABITAT'), transparent: true, opacity: 0.6 })));
  const tr = new THREE.TorusGeometry(S.thrust_ring[1], 0.6, 8, 48); tr.rotateY(Math.PI / 2); tr.translate(S.thrust_ring[0], 0, 0);
  shipGroup.add(new THREE.Mesh(tr, mat));
  const b = S.blades, bm = new THREE.MeshStandardMaterial({ color: css('--fn-HOT_RADIATOR'), roughness: 0.6, transparent: true, opacity: 0.22, side: THREE.DoubleSide, depthWrite: false });
  b.az.forEach(az => {
    const g = new THREE.PlaneGeometry(b.x1 - b.x0, b.r1 - b.r0); g.translate((b.x0 + b.x1) / 2, (b.r0 + b.r1) / 2, 0);
    const me = new THREE.Mesh(g, bm), a = az * Math.PI / 180;
    // the blade plane holds the ship axis; its radial direction is (cos az, sin az) in Blender (y, z), (sin az, -cos az) in runtime (y, z)
    me.rotation.x = a - Math.PI / 2;
    const ed = new THREE.LineSegments(new THREE.EdgesGeometry(g), edge); ed.rotation.x = me.rotation.x;
    shipGroup.add(me, ed);
  });
}

// ---- engines: one InstancedMesh per category ---------------------------------------------------------------------------------------------
function buildEngines(bin) {
  engineGroup = new THREE.Group(); scene.add(engineGroup);
  const q = M.geometry.quantum_m, nv = M.geometry.vertices;
  const pos = new Int16Array(bin, 0, nv * 3), idx = new Uint16Array(bin, nv * 6);
  const byCat = {};
  M.parts.forEach(p => {
    const [v0, n, i0, ni] = p.geo;
    const P = new Float32Array(n * 3); let cx = 0, cy = 0, cz = 0;
    for (let i = 0; i < n * 3; i += 3) { P[i] = pos[v0 * 3 + i] * q; P[i + 1] = pos[v0 * 3 + i + 1] * q; P[i + 2] = pos[v0 * 3 + i + 2] * q; cx += P[i]; cy += P[i + 1]; cz += P[i + 2]; }
    let g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(P, 3)); g.setIndex(Array.from(idx.subarray(i0, i0 + ni)));
    g = toCreasedNormals(g, Math.PI / 5);
    p.centroid = new THREE.Vector3(cx / n, cy / n, cz / n);
    (byCat[p.category] ||= []).push(g);
  });
  M.categories.forEach(c => {
    if (!byCat[c.id]) return;
    const geo = mergeGeometries(byCat[c.id], false); byCat[c.id].forEach(g => g.dispose());
    const col = new THREE.Color().setRGB(...c.color, THREE.SRGBColorSpace);
    const mat = new THREE.MeshStandardMaterial({ color: col, roughness: 0.55, metalness: 0.35, emissive: new THREE.Color(0, 0, 0), transparent: true, opacity: 1,
      clippingPlanes: [], side: THREE.DoubleSide });
    const im = new THREE.InstancedMesh(geo, mat, engineMats.length); engineMats.forEach((m, i) => im.setMatrixAt(i, m)); im.frustumCulled = false;
    im.userData.cat = c.id; engineGroup.add(im); catMeshes[c.id] = im; catMats[c.id] = { mat, base: col.clone() };
  });
}

// ---- field lines (the viewer's vacuum-field file, revolved about each engine axis) --------------------------------------------------------------
function buildField(field) {
  fieldGroup = new THREE.Group(); scene.add(fieldGroup);
  if (!field) return;
  const cand = field[M.magnet.active] || Object.values(field)[0];
  const mat = new THREE.LineBasicMaterial({ color: COL.info, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending });
  const segs = [];                                  // [fraction along its line, x0, y0, z0, x1, y1, z1]
  engineMats.forEach((m, e) => {
    const az = e === 0 ? 10 : 5;
    cand.lines.forEach(L => {
      for (let k = 0; k < az; k++) {
        const a = k / az * Math.PI * 2, pts = [];
        for (let i = 0; i < L.length; i += 2) pts.push(new THREE.Vector3(L[i], L[i + 1] * Math.cos(a), L[i + 1] * Math.sin(a)).applyMatrix4(m));
        for (let i = 1; i < pts.length; i++) segs.push([i / (pts.length - 1), ...pts[i - 1].toArray(), ...pts[i].toArray()]);
      }
    });
  });
  segs.sort((a, b) => a[0] - b[0]);
  const P = new Float32Array(segs.length * 6); segs.forEach((g, i) => P.set(g.slice(1), i * 6));
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(P, 3));
  const ln = new THREE.LineSegments(g, mat); ln.frustumCulled = false; fieldGroup.add(ln);
  fieldLines = [ln]; ln.userData.frac = Float32Array.from(segs, x => x[0]);           // one draw call for every field line of the cluster
  fieldGroup.userData.mat = mat;
}

// ---- particle paths (SAMPLED: Boris push in the vacuum field, engine N1) -------------------------------------------------------------------
const SPC = { 'p_14.7MeV': 'wf-plasma', 'alpha_3.6MeV': 'wf-violet', D_debris: 'fn-DEUTERIUM', He3_debris: 'fn-HELIUM3' };
function upTo(frac, k) { let lo = 0, hi = frac.length; while (lo < hi) { const m = (lo + hi) >> 1; if (frac[m] <= k) lo = m + 1; else hi = m; } return lo; }
function buildPaths() {
  if (!pathGroup) { pathGroup = new THREE.Group(); scene.add(pathGroup); }
  pathGroup.clear(); pathLines = [];
  const set = D.nozzle.mult[lab.field === '4' ? '4' : '1'], segs = { AFT: [], HIT: [] }, heads = [];
  Object.entries(set).forEach(([sp, s]) => {
    s.paths.forEach(p => {
      const pts = []; for (let i = 0; i < p.pts.length; i += 3) pts.push(new THREE.Vector3(p.pts[i], p.pts[i + 1], p.pts[i + 2]).applyMatrix4(N1));
      const key = p.outcome === 'AFT' ? 'AFT' : 'HIT';
      for (let i = 1; i < pts.length; i++) segs[key].push([i / (pts.length - 1), ...pts[i - 1].toArray(), ...pts[i].toArray()]);
      heads.push({ pts, sp, aft: key === 'AFT' });
    });
  });
  Object.entries(segs).forEach(([key, L]) => {
    L.sort((a, b) => a[0] - b[0]);
    const P = new Float32Array(L.length * 6); L.forEach((g, i) => P.set(g.slice(1), i * 6));
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(P, 3));
    const ln = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: key === 'AFT' ? COL.good : COL.bad, transparent: true, opacity: 0.85 }));
    ln.frustumCulled = false; ln.userData = { key, frac: Float32Array.from(L, x => x[0]) }; pathGroup.add(ln); pathLines.push(ln);
  });
  const hm = new THREE.InstancedMesh(new THREE.SphereGeometry(0.32, 10, 8), new THREE.MeshBasicMaterial(), heads.length);
  heads.forEach((h, i) => hm.setColorAt(i, new THREE.Color(COL[SPC[h.sp]])));
  hm.frustumCulled = false; hm.userData.heads = heads; pathGroup.add(hm); pathGroup.userData.heads = hm;      // three draw calls for all paths
  // one representative 14.7 MeV proton that leaves aft, drawn alone first (stage 7, step 2)
  if (pathGroup.userData.rep) { scene.remove(pathGroup.userData.rep.line, pathGroup.userData.rep.head); }
  const one = heads.find(h => h.aft && h.sp === 'p_14.7MeV') || heads.find(h => h.aft);
  if (one) {
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(one.pts), new THREE.LineBasicMaterial({ color: COL['wf-plasma'], transparent: true, depthTest: false }));
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.5, 12, 10), new THREE.MeshBasicMaterial({ color: '#FFFFFF', depthTest: false }));
    line.renderOrder = head.renderOrder = 5; line.frustumCulled = false; scene.add(line, head); pathGroup.userData.rep = { line, head, pts: one.pts };
  }
}

// ---- effects ------------------------------------------------------------------------------------------------------------------------------
function pointsMat(size, color, additive = true) {
  return new THREE.PointsMaterial({ size, color, transparent: true, opacity: 0.9, depthWrite: false, sizeAttenuation: true, blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending, vertexColors: false });
}
function buildFx() {
  fxGroup = new THREE.Group(); scene.add(fxGroup);
  radGroup = new THREE.Group(); scene.add(radGroup);
  // target and the six driver beams (engine N1)
  targetMesh = new THREE.Mesh(new THREE.SphereGeometry(0.35, 16, 12), new THREE.MeshBasicMaterial({ color: COL['fn-HELIUM3'] })); fxGroup.add(targetMesh);
  const ports = M.parts.filter(p => /Driver_Port/.test(p.name)).map(p => p.centroid.clone().applyMatrix4(N1));
  const bp = []; ports.forEach(p => bp.push(p, burnW[0]));
  beams = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(bp), new THREE.LineBasicMaterial({ color: 0xbfe0ff, transparent: true, opacity: 0, blending: THREE.AdditiveBlending }));
  fxGroup.add(beams);
  // plasma: ions and electrons round the burn point (ILLUSTRATIVE motion)
  const n = 900, P = new Float32Array(n * 3); plasmaPts = new THREE.Points(new THREE.BufferGeometry(), pointsMat(0.25, COL['wf-plasma']));
  plasmaPts.geometry.setAttribute('position', new THREE.BufferAttribute(P, 3)); plasmaPts.userData.seed = Float32Array.from({ length: n * 3 }, () => Math.random() * 2 - 1);
  fxGroup.add(plasmaPts);
  // exhaust plume (all four engines)
  const m = 4 * 700, Q = new Float32Array(m * 3); plume = new THREE.Points(new THREE.BufferGeometry(), pointsMat(0.6, COL['wf-ignition']));
  plume.geometry.setAttribute('position', new THREE.BufferAttribute(Q, 3)); plume.userData.seed = Float32Array.from({ length: m * 3 }, () => Math.random());
  fxGroup.add(plume);
  // hydrogen reaction mass (SPECULATIVE coupling; drawn entering the nozzle round the burn)
  const h = 400, H = new Float32Array(h * 3); h2pts = new THREE.Points(new THREE.BufferGeometry(), pointsMat(0.3, COL['fn-HYDROGEN']));
  h2pts.geometry.setAttribute('position', new THREE.BufferAttribute(H, 3)); h2pts.userData.seed = Float32Array.from({ length: h * 3 }, () => Math.random());
  fxGroup.add(h2pts);
  // radiation: photons and neutrons from the burn of N1, ending on the parts they meet (ILLUSTRATIVE rays, shares from the data)
  const targets = M.parts.filter(p => ['MAGNETIC_NOZZLE', 'SHIELDING', 'MAGNETIC_COILS', 'STRUCTURE'].includes(p.category));
  const mk = (count, col, len) => {
    const seg = [];
    for (let i = 0; i < count; i++) {
      const hit = Math.random() < 0.62 && targets.length;
      let end;
      if (hit) end = targets[Math.floor(Math.random() * targets.length)].centroid.clone().applyMatrix4(N1);
      else { const d = new THREE.Vector3().randomDirection(); end = burnW[0].clone().addScaledVector(d, len); }
      seg.push(burnW[0].clone(), end);
    }
    const g = new THREE.BufferGeometry().setFromPoints(seg);
    return new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.0, blending: THREE.AdditiveBlending, depthWrite: false }));
  };
  radGroup.userData.ph = mk(260, COL.warn, 140); radGroup.userData.n = mk(70, COL.neutron, 160);
  radGroup.add(radGroup.userData.ph, radGroup.userData.n);
  const packets = (src, per, size, col) => {
    const seg = src.geometry.attributes.position.array, ns = seg.length / 6, n = ns * per, o = new THREE.Points(new THREE.BufferGeometry(), pointsMat(size, col));
    o.geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3), 3)); o.frustumCulled = false;
    o.userData = { seg, idx: Int32Array.from({ length: n }, (_, i) => i % ns), phase: Float32Array.from({ length: n }, () => Math.random()) }; radGroup.add(o); return o;
  };
  radGroup.userData.packets = { ph: packets(radGroup.userData.ph, 2, 0.9, COL.warn), n: packets(radGroup.userData.n, 3, 1.3, COL.neutron) };
  // ship-bound rays (ENG-032): from the four burns to the blade aft ends
  const B = D.ship.blades, sh = [];
  burnW.forEach(bw => B.az.forEach(az => { const a = az * Math.PI / 180; for (let k = 0; k < 3; k++) sh.push(bw.clone(), shipPt(B.x0 + 4 + k * 10, (B.r0 + 6 + k * 9) * Math.cos(a), (B.r0 + 6 + k * 9) * Math.sin(a))); }));
  radGroup.userData.ship = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(sh), new THREE.LineBasicMaterial({ color: COL.bad, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
  radGroup.add(radGroup.userData.ship);
  thrustArrow = new THREE.ArrowHelper(new THREE.Vector3(1, 0, 0), new THREE.Vector3(-60, 60, 0), 60, new THREE.Color(COL.good).getHex(), 14, 8);
  scene.add(thrustArrow);
}

function stars() {
  const n = 1500, P = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) { const d = new THREE.Vector3().randomDirection().multiplyScalar(4000); P.set([d.x, d.y, d.z], i * 3); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(P, 3));
  scene.add(new THREE.Points(g, new THREE.PointsMaterial({ size: 1.6, color: 0x9fb0c8, sizeAttenuation: false, transparent: true, opacity: 0.7 })));
}

// ---- problem markers (HTML, projected) ------------------------------------------------------------------------------------------------------
function markerPoint(id) {
  const part = re => M.parts.find(p => re.test(p.name))?.centroid.clone().applyMatrix4(N1);
  const B = D.ship.blades;
  return ({ 'ENG-030': part(/Loop.*L2|L2/), 'ENG-031': new THREE.Vector3(-34, 0, 0).applyMatrix4(N1), 'ENG-032': shipPt(B.x0 + 8, B.r0 + 14, 0),
    'ENG-033': part(/C2/), 'ENG-034': part(/Hub|Cradle/) || new THREE.Vector3(D.ship.cluster_front - 4, 0, 0), 'ENG-036': part(/Shadow_Shield/),
    'ENG-038': part(/L3/), 'ENG-040': new THREE.Vector3(-12.95, 0, -3.2).applyMatrix4(N1), 'ENG-043': new THREE.Vector3(-15.8, 0, 4.9).applyMatrix4(N1),
    'ENG-046': new THREE.Vector3(-23.4, 8.46, 4.6).applyMatrix4(N1), 'ENG-048': new THREE.Vector3(-24.4, 0, -9.6).applyMatrix4(N1),
    'ENG-053': new THREE.Vector3(-12.84, -2.6, 0).applyMatrix4(N1), 'ENG-057': thPt('EDGE'), 'ENG-060': thPt('WARM_RING'), 'ENG-058': thPt('ROOT'), 'ENG-035': shipPt(D.ship.tank[0] - 8, 0, 14), 'ENG-037': new THREE.Vector3(D.ship.cluster_front + 2, 8, 0) })[id];
}
function thPt(comp) {                                          // a point on the first thermal-study primitive of this component, engine N1
  const g = D.thermal && D.thermal.geometry.find(x => x.comp === comp); if (!g) return null;
  const p = g.kind === 'tube' ? g.points[g.points.length >> 1] : g.kind === 'box' ? g.center : g.kind === 'torus' ? [g.x, 0, g.R] : null;
  return p ? v3(p).applyMatrix4(N1) : null;
}
function buildMarkers() {
  D.problems.items.forEach(p => {
    const at = markerPoint(p.id); if (!at) return;
    const b = document.createElement('button'); b.className = `fi-mark ${p.status === 'OPEN' ? 'open' : 'mit'}`; b.type = 'button';
    b.textContent = p.id; b.title = p.title; b.hidden = true;
    b.addEventListener('click', () => showProblem(p)); stage.appendChild(b); markerEls.push({ el: b, at, p });
  });
}
function showProblem(p) {
  readEl.innerHTML = `<p class="first bad"><b>${esc(p.id)}</b> ${esc(p.title)} <span class="st st-${p.status === 'OPEN' ? 'OPEN' : 'WORKING'}">${esc(p.status.toLowerCase())}</span></p>
    <table><tbody><tr><th>Physical origin</th><td>${esc(p.mechanism)}</td></tr><tr><th>Required</th><td>${esc(p.required)}</td></tr>
    <tr><th>Achieved</th><td>${esc(p.achieved)}</td></tr><tr><th>Severity</th><td>${esc(p.severity)}</td></tr><tr><th>Variants</th><td>${esc(p.variants.join(', '))}</td></tr>
    <tr><th>Possible directions</th><td>${esc(p.solutions)}</td></tr><tr><th>Needs</th><td>${esc(p.advances)}</td></tr><tr><th>Evidence</th><td><code>${esc(p.evidence)}</code></td></tr></tbody></table>
    <p class="meta">${chip('IMPORTED')} ${/^ENG-06[1-3]/.test(p.id) ? 'source study' : /^ENG-0[456]/.test(p.id) ? 'thermal study' : 'compact-engine'} register · <a href="#p-${esc(p.id)}">in the table below</a></p>`;
  if (p.categories.length) { focusCat = p.categories[0]; catMode = 'highlight'; applyCats(); }
}

// ---- parts panel (stage 1) -------------------------------------------------------------------------------------------------------------------
function buildParts() {
  partsEl.innerHTML = `<p class="presets" role="group" aria-label="How a picked group is shown"><button data-cm="highlight" aria-pressed="true">Highlight</button>
    <button data-cm="isolate" aria-pressed="false">Isolate</button><button data-cm="xray" aria-pressed="false">Others transparent</button><button data-cm="none">Show all</button></p>
    <ul class="fi-cats">${M.categories.map(c => `<li><button data-cat="${c.id}" aria-pressed="false"><i style="background:rgb(${c.color.map(v => Math.round(255 * v ** (1 / 2.2))).join(',')})"></i>${esc(c.title)} <small>${c.parts}</small></button></li>`).join('')}</ul>
    <div id="catinfo" class="meta"></div>`;
  partsEl.addEventListener('click', ev => {
    const b = ev.target.closest('button'); if (!b) return;
    if (b.dataset.cm) { if (b.dataset.cm === 'none') { focusCat = null; } else catMode = b.dataset.cm; }
    if (b.dataset.cat) focusCat = focusCat === b.dataset.cat ? null : b.dataset.cat;
    applyCats();
  });
}
function applyCats() {
  partsEl.querySelectorAll('[data-cm]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.cm === catMode && focusCat != null)));
  partsEl.querySelectorAll('[data-cat]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.cat === focusCat)));
  const c = M?.categories.find(x => x.id === focusCat);
  const info = $('catinfo');
  if (info) info.innerHTML = c ? `<b>${esc(c.title)}.</b> ${esc(c.purpose || '')} ${esc(c.how || '')}${c.speculative ? ` <br><b>Speculative:</b> ${esc(c.speculative)}` : ''}` : 'Pick a group to see what it does.';
  dirty = true;
}

// ---- experiment (stage 9) --------------------------------------------------------------------------------------------------------------------
// ---- the pulse energy ledger (lab/studies/fusion-ignition/ledger.py pulse(): the same arithmetic) --------------------------------------
const C2 = 299792458 ** 2;
function pulseLedger(cell, m, Hz, noz, budget, mirror = 0, h2 = 0) {
  const F = cell.fusion_J, Q = cell.heat_J, Xr = cell.xray_J, Nn = cell.neutron_J, P = cell.plasma_J;
  const jet = noz.eta * P, hit = noz.hit * P, side = Math.max(P - jet - hit, 0);
  const x_abs = noz.pickup * Xr * (1 - mirror), n_abs = noz.pickup * Nn, mx = m - F / C2, coupled = h2 === 0;
  const I = coupled ? Math.sqrt(2 * mx * jet) : null, v = coupled ? Math.sqrt(2 * jet / mx) : null, heat = x_abs + n_abs + hit;
  return { fusion_J: F, heat_in_J: Q, xray_J: Xr, neutron_J: Nn, plasma_J: P, jet_J: jet, side_J: side, hit_J: hit, x_abs_J: x_abs, n_abs_J: n_abs,
    residual_J: cell.residual_J || 0, number_change_J: cell.number_change_J || 0, engine_heat_J: heat, impulse_Ns: I, exhaust_m_s: v, mass_kg: m, exhaust_mass_kg: mx, reacted_kg: cell.reacted_kg,
    burn_fraction: cell.burn_fraction, Hz, fusion_W: F * Hz, jet_W: jet * Hz, thrust_N: coupled ? I * Hz : null, engine_heat_W: heat * Hz,
    heat_over: heat * Hz / budget, driver_abs_W: Q * Hz, driver_elec_W: Q * Hz / D.ledger.wallplug, fuel_kg_s: m * Hz, reacted_kg_s: cell.reacted_kg * Hz,
    jet_share: jet / F, coupled, budget_W: budget };
}
const nozOf = (v, f = '1') => D.ledger.nozzle[`${v}|${f}`];
const stateOf = id => D.ledger.states.find(s => s.id === id);
function LED() {                              // the ledger every stage reads, by view: Intended = design point, Modeled = coupled C1, Experiment = levers
  const Lg = D.ledger;
  if (view === 'exp') return expLedger();
  if (view === 'concept') { const n = nozOf('C1'); return Object.assign(pulseLedger(Lg.design_cell, Lg.target_mass_kg, Lg.design_Hz, Object.assign({}, n, { eta: 1, hit: 0 }), n.budget_W),
    { state: 'DESIGN', cls: 'SPECULATIVE', label: 'Intended: the engine design point (78 % jet assumed)' }); }
  const n = nozOf('C1');
  return Object.assign(pulseLedger(Lg.grid.cells[Lg.grid.design], Lg.target_mass_kg, Lg.design_Hz, n, n.budget_W),
    { state: 'COUPLED', cls: 'CALCULATED', label: 'Modeled: the design target burned (R2-B), nozzle C1' });
}
function expLedger() {
  const Lg = D.ledger, cell = Lg.grid.cells[`${lab.rhoR}|${lab.Ti0}|${lab.mix}`], noz = nozOf(lab.variant, lab.field);
  const mi = lab.mirror ? D.lab.mirrors.rows[lab.mirror - 1] : null;
  const r = pulseLedger(cell, Lg.target_mass_kg, Lg.design_Hz * lab.rate, noz, noz.budget_W, mi ? mi.reflected : 0, lab.h2 * Lg.target_mass_kg);
  const A = D.lab.armour, Pn0 = D.channels.powers.P_n_W;
  r.flu = A.over_at_t0 * (Math.exp(-lab.armour / A.lam_m) + A.floor) / (Math.exp(-A.t0_m / A.lam_m) + A.floor) * (r.neutron_J * r.Hz / Pn0);
  r.armour_t = (lab.armour - A.t0_m) * A.area_m2_per_engine * A.density_kg_m3 / 1e3;
  return Object.assign(r, { mi, noz, state: 'EXPERIMENT', cls: 'CALCULATED', label: `Experiment: ${lab.rhoR} g/cm², ${lab.Ti0} keV, D:³He ${lab.mix}, ×${lab.rate} rate, ${lab.variant} field ×${lab.field}` });
}
const SEG = [['x', 'X-rays', 'xray_J'], ['n', 'neutrons', 'neutron_J'], ['hit', 'plasma on hardware', 'hit_J'], ['side', 'plasma not directed', 'side_J'], ['jet', 'directed jet', 'jet_J']];
const HL = { need: 'jet', fuel: '', nucleus: '', many: '', ignition: 'x', nozzle: 'jet', losses: 'hit', thermal: 'x', lab: '' };
function ledgerBar(r) {                       // one pulse: where its energy goes, in the active model state (shares of the outputs)
  const tot = r.fusion_J + r.heat_in_J, hl = HL[STAGES[si]] || '';
  const seg = SEG.map(([k, l, f]) => `<i class="s-${k}${hl === k ? ' on' : ''}" style="flex:${(r[f] / tot).toFixed(4)}" title="${esc(l)}: ${pct(r[f] / tot)}"></i>`).join('');
  const leg = SEG.filter(s => r[s[2]] / tot >= 0.0005).map(([k, l, f]) => `<span class="${hl === k ? 'on' : ''}"><i class="s-${k}"></i>${esc(l)} ${pct(r[f] / tot)}</span>`).join('');
  const res = r.state === 'DESIGN' ? 'driver heat not booked by the design point (gain 100 assumed)' : `ions lost in D-D and D-T reactions carry ${pct(Math.abs(r.number_change_J || 0) / (r.fusion_J + r.heat_in_J))}; integration residual ${pct(Math.abs(r.residual_J) / (r.fusion_J + r.heat_in_J))} (R2-B)`;
  return `<div class="fi-ledger" aria-label="Energy of one pulse by destination"><p class="fl-h">One pulse: where the energy goes (share of fusion + driver heat) ${chip(r.cls)}</p>
    <p class="fl-s">${esc(r.label)}</p><div class="fl-bar">${seg}</div><p class="fl-leg">${leg}</p>
    <p class="meta">In: ${(r.fusion_J / 1e9).toFixed(2)} GJ fusion + ${(r.heat_in_J / 1e6).toFixed(0)} MJ driver heat; out: jet ${(r.jet_J / 1e6).toFixed(0)} MJ${r.coupled ? `, ${r.impulse_Ns.toFixed(1)} N·s per pulse` : ''}; ${res}. <a href="#ledger">Ledger</a></p></div>`;
}

function buildLab() {
  const ax = D.lab.fuel.axes, b = D.plasma.burn;
  labEl.innerHTML = `
    <p class="meta">Each lever feeds one process of the pulse ledger: the target sets the burn, the rate the power, the variant and field the nozzle,
      mirrors and armour the engine's heat and its windings. Where no model couples a lever, the result says so.</p>
    <p class="presets" role="group" aria-label="Compact variant">${D.lab.variants.order.map(k => `<button data-v="${k}" aria-pressed="${k === lab.variant}">${k}</button>`).join('')} ${chip('IMPORTED')}</p>
    <p class="meta">${esc(D.lab.variants.note)}</p>
    <p class="presets" role="group" aria-label="Closure field">Field ${['1', '2', '4'].map(k => `<button data-f="${k}" aria-pressed="${k === lab.field}">×${k}</button>`).join('')} ${chip('SAMPLED')}</p>
    <div class="lever"><label for="l-r">Target areal density <output id="o-r"></output></label><input type="range" id="l-r" min="0" max="${b.rhoR.length - 1}" value="${b.rhoR.indexOf(b.rhoR_design)}"></div>
    <div class="lever"><label for="l-i">Target start temperature <output id="o-i"></output></label><input type="range" id="l-i" min="0" max="${b.Ti.length - 1}" value="${b.Ti.indexOf(b.Ti_design)}"></div>
    <p class="presets" role="group" aria-label="Target fuel mix">Target D : ³He ${D.ledger.grid.mix.map(k => `<button data-x="${k}" aria-pressed="${k === lab.mix}">${k === 0.5 ? '1 : 2' : k === 1 ? '1 : 1' : '2 : 1'}</button>`).join('')} ${chip('CALCULATED')}</p>
    <div class="lever"><label for="l-f">Pulse rate <output id="o-f"></output></label><input type="range" id="l-f" min="0" max="${RATES.length - 1}" value="${RATES.indexOf(1)}"><span class="meta">${chip('SPECULATIVE')} target delivery at this rate is VTX-S2.</span></div>
    <div class="lever"><label for="l-m">Grazing-incidence mirrors <output id="o-m"></output></label><input type="range" id="l-m" min="0" max="${D.lab.mirrors.rows.length}" value="0">
      <span class="meta">${esc(D.lab.mirrors.note)} ${chip('MODEL-BASED')}</span></div>
    <div class="lever"><label for="l-a">Coil armour <output id="o-a"></output></label><input type="range" id="l-a" min="22" max="200" value="22"><span class="meta">${esc(D.lab.armour.note)}</span></div>
    <div class="lever"><label for="l-h">Hydrogen added per pulse <output id="o-h"></output></label><input type="range" id="l-h" min="0" max="${H2S.length - 1}" value="0"><span class="meta">${chip('OPEN')} no model says how the plasma would heat it.</span></div>
    <details class="fi-steady"><summary>Steady-plasma levers (a different regime)</summary>
      <p class="meta">These change the selective-fusion split of a steady, magnetically confined plasma and the crowd of stage 5. A pulsed target
        cannot be run hot-ion or channelled, so they are not coupled to the pulse ledger.</p>
      <div class="lever"><label for="l-d">Fuel: deuterium share <output id="o-d"></output></label><input type="range" id="l-d" min="0" max="${ax.d_share.length - 1}" value="${ax.d_share.indexOf(0.5)}"></div>
      <div class="lever"><label for="l-t">Ion temperature <output id="o-t"></output></label><input type="range" id="l-t" min="0" max="${ax.Ti.length - 1}" value="${ax.Ti.indexOf(100)}"></div>
      <p class="presets" role="group" aria-label="Electrons">${Object.keys(ax.modes).map(k => `<button data-m="${k}" aria-pressed="${k === lab.mode}">${k === 'thermal' ? 'Thermal' : 'Hot-ion'}</button>`).join('')} ${chip('CALCULATED')}</p>
      <p class="presets" role="group" aria-label="Spin polarisation">${Object.entries(ax.pol).map(([k, v]) => `<button data-p="${k}" aria-pressed="${k === lab.pol}" title="${esc(v.label)}">${k === 'none' ? 'Unpolarised' : k === 'polarised' ? 'Polarised' : 'Polarised, D-D suppressed'}</button>`).join('')}</p>
      <p class="meta" id="o-steady"></p></details>
    <p class="presets"><button id="l-reset">Reset</button></p>`;
  const sync = () => {
    labEl.querySelectorAll('[data-v]').forEach(x => x.setAttribute('aria-pressed', String(x.dataset.v === lab.variant)));
    labEl.querySelectorAll('[data-f]').forEach(x => x.setAttribute('aria-pressed', String(x.dataset.f === lab.field)));
    labEl.querySelectorAll('[data-x]').forEach(x => x.setAttribute('aria-pressed', String(+x.dataset.x === lab.mix)));
    labEl.querySelectorAll('[data-m]').forEach(x => x.setAttribute('aria-pressed', String(x.dataset.m === lab.mode)));
    labEl.querySelectorAll('[data-p]').forEach(x => x.setAttribute('aria-pressed', String(x.dataset.p === lab.pol)));
  };
  labEl.addEventListener('click', ev => {
    const b_ = ev.target.closest('button'); if (!b_) return;
    if (b_.dataset.v) lab.variant = b_.dataset.v;
    if (b_.dataset.f) { lab.field = b_.dataset.f; if (ready) buildPaths(); }
    if (b_.dataset.x) lab.mix = +b_.dataset.x;
    if (b_.dataset.m) lab.mode = b_.dataset.m;
    if (b_.dataset.p) lab.pol = b_.dataset.p;
    if (b_.id === 'l-reset') { Object.assign(lab, { variant: 'C1', field: '1', d: 0.5, Ti: 100, mode: 'thermal', pol: 'none', armour: 0.22, mirror: 0, rhoR: b.rhoR_design, Ti0: b.Ti_design, mix: 1, rate: 1, h2: 0 });
      $('l-d').value = ax.d_share.indexOf(0.5); $('l-t').value = ax.Ti.indexOf(100); $('l-a').value = 22; $('l-m').value = 0; $('l-r').value = b.rhoR.indexOf(b.rhoR_design); $('l-i').value = b.Ti.indexOf(b.Ti_design);
      $('l-f').value = RATES.indexOf(1); $('l-h').value = 0; if (ready) buildPaths(); }
    sync(); labUpdate();
  });
  labEl.addEventListener('input', () => {
    lab.d = ax.d_share[+$('l-d').value]; lab.Ti = ax.Ti[+$('l-t').value]; lab.armour = +$('l-a').value / 100; lab.mirror = +$('l-m').value;
    lab.rhoR = b.rhoR[+$('l-r').value]; lab.Ti0 = b.Ti[+$('l-i').value]; lab.rate = RATES[+$('l-f').value]; lab.h2 = H2S[+$('l-h').value]; labUpdate();
  });
  labUpdate();
}
const RATES = [0.25, 0.5, 1, 2, 4, 8], H2S = [0, 1, 3, 10];
const fmtD = v => v.toFixed(2);
function fuelPoint(pol, mode, Ti, d) {
  const g = D.lab.fuel.grid[`${pol}|${mode}|${Ti.toFixed(0)}|${fmtD(d)}`];
  return g ? Object.fromEntries(D.lab.fuel.fields.map((k, i) => [k, g[i]])) : null;
}
const MN = n => `${(n / 1e6).toFixed(n < 1e6 ? 2 : 1)} MN`;
function labUpdate() {
  $('o-d').textContent = pct(lab.d); $('o-t').textContent = `${lab.Ti} keV`; $('o-a').textContent = `${lab.armour.toFixed(2)} m`;
  const mi = lab.mirror ? D.lab.mirrors.rows[lab.mirror - 1] : null;
  $('o-m').textContent = mi ? `${mi.theta_deg}° grazing` : 'none'; $('o-r').textContent = `${lab.rhoR} g/cm²`; $('o-i').textContent = `${lab.Ti0} keV`;
  $('o-f').textContent = `×${lab.rate} (${Math.round(D.ledger.design_Hz * lab.rate).toLocaleString('en')} Hz)`; $('o-h').textContent = lab.h2 ? `${lab.h2}× the target mass` : 'none';
  const sp = fuelPoint(lab.pol, lab.mode, lab.Ti, lab.d);
  if (sp) $('o-steady').innerHTML = `Steady split at these settings: charged ${pct(sp.charged)}, neutrons ${pct(sp.neutron)}, X-rays ${pct(sp.photon)} of fusion ${chip('CALCULATED')}`;
  if (si !== STAGES.indexOf('lab')) return;
  const r = expLedger(), nd = D.ledger.need, row = (a, b, c = '') => `<div><dt>${a}</dt><dd class="num ${c}">${b}</dd></div>`;
  const F4 = r.coupled ? 4 * r.thrust_N : null, need4 = 4 * nd.thrust_per_engine_N;
  readEl.innerHTML = `<p class="first bad">${r.coupled ? `<b>${MN(F4)}</b> of the ${MN(need4)} the ship needs (four engines, ${X(need4 / F4)} short)` : '<b>Thrust not computed</b>: hydrogen coupling is not modelled'};
      engine heat <b>${X(r.heat_over)}</b> the radiators.</p>${ledgerBar(r)}
    <dl class="fi-dl">
      ${row(`Fusion per engine ${chip('CALCULATED')}`, `${W(r.fusion_W)} (${(r.fusion_J / 1e9).toFixed(2)} GJ × ${Math.round(r.Hz).toLocaleString('en')} Hz)`)}
      ${row(`Burn: gain, fuel used (by mass) ${chip('CALCULATED')}`, `${(r.fusion_J / r.heat_in_J).toFixed(1)}, ${pct(r.burn_fraction)}`)}
      ${row(`X-rays · neutrons (share of fusion) ${chip('CALCULATED')}`, `${pct(r.xray_J / r.fusion_J)} · ${pct(r.neutron_J / r.fusion_J)}`, 'bad')}
      ${row(`Plasma energy left · directed jet ${chip('IMPORTED')}`, `${pct(r.plasma_J / r.fusion_J)} · ${pct(r.jet_share)} (nozzle ${r.noz.eta.toFixed(2)})`)}
      ${row(`Exhaust speed (needs ${Math.round(nd.exhaust_m_s / 1e3).toLocaleString('en')} km/s) ${chip(r.coupled ? 'CALCULATED' : 'OPEN')}`, r.coupled ? `${Math.round(r.exhaust_m_s / 1e3).toLocaleString('en')} km/s` : 'not modelled', 'bad')}
      ${row(`Thrust, four engines ${chip(r.coupled ? 'CALCULATED' : 'OPEN')}`, r.coupled ? MN(F4) : 'not modelled', 'bad')}
      ${row(`Driver heat into the fuel (lower bound) ${chip('OPEN')}`, `${W(r.driver_abs_W)}; ${W(r.driver_elec_W)} electric at ${pct(D.ledger.wallplug)}`, 'bad')}
      ${row(`Heat into the engine${r.mi ? `, mirrors ${r.mi.theta_deg}°` : ''} ${chip(r.mi ? 'MODEL-BASED' : 'CALCULATED')}`, `${W(r.engine_heat_W)} (X-rays ${W(r.x_abs_J * r.Hz)}, neutrons ${W(r.n_abs_J * r.Hz)}, plasma ${W(r.hit_J * r.Hz)})`, 'bad')}
      ${row(`Winding neutron fluence ${chip('CALCULATED')}`, `${X(r.flu)} limit`, r.flu > 1 ? 'bad' : '')}
      ${row(`Added armour per engine ${chip('CALCULATED')}`, `${Math.round(r.armour_t).toLocaleString('en')} t`)}
      ${row(`Fuel injected · reacted ${chip('CALCULATED')}`, `${(r.fuel_kg_s * 1e3).toFixed(1)} · ${(r.reacted_kg_s * 1e3).toFixed(1)} g/s per engine`)}
      ${r.mi ? row(`Mirror length for the same coverage ${chip('MODEL-BASED')}`, `${Math.round(r.mi.length_factor)}×`) : ''}
      ${row(`Direct burn on the ship (limit 0.1 GW) ${chip('IMPORTED')}`, `${W(D.channels.variants[lab.variant].ship_lit_W)} (steady-source study)`)}
    </dl>
    ${r.coupled ? '' : `<p class="meta bad">${chip('OPEN')} ${esc('Hydrogen added to the exhaust: how fusion energy reaches cold hydrogen is not modelled, so no exhaust speed or thrust is computed. The rest of the ledger is unchanged.')}</p>`}
    ${lab.mix !== 1 ? `<p class="meta">The ignition animation plays the 1 : 1 burn history; these numbers use the ${lab.mix === 0.5 ? '1 : 2' : '2 : 1'} burn.</p>` : ''}
    <p class="meta">How this is combined: one pulse of the chosen target burns in the R2-B model (precomputed for every lever setting), the nozzle
      shares of the chosen variant split the plasma energy, and the rate turns joules into watts and impulse into thrust. The nozzle and pickup
      shares are ${chip('IMPORTED')} from the compact study's test particles. Nothing here changes the ship.</p>`;
  window.__fi.lab = { thrust_N: r.thrust_N, heat_over: r.heat_over, jet_share: r.jet_share, flu: r.flu, exhaust_m_s: r.exhaust_m_s };
  dirty = true; draw2d();
}

// ---- stage control -------------------------------------------------------------------------------------------------------------------------
function setStage(i, quiet) {
  si = Math.max(0, Math.min(STAGES.length - 1, i)); u = 0;
  enterT = performance.now() / 1000; PLX.prods = []; PLX.phot = []; IGN.fl = []; IGN.ph = []; IGN.nn = [];
  const id = STAGES[si];
  root.dataset.stage = id; tip.hidden = true;
  document.querySelectorAll('.fi-stages [role="tab"]').forEach((t, k) => { t.setAttribute('aria-selected', String(k === si)); t.tabIndex = k === si ? 0 : -1; });
  document.querySelectorAll('.fi-text').forEach(a => { a.hidden = a.dataset.stage !== id; });
  partsEl.hidden = !(id === 'hardware' && ready); labEl.hidden = id !== 'lab';
  $('replay').hidden = id !== 'nucleus';
  $('graphs').hidden = !TWO_D.has(id);
  ladderEl.style.setProperty('--k', LADDER[id]);
  ctlUpdate();
  if (!ready && TWO_D.has(id) && !reduced && !quiet) { playing = true; syncPlay(); }
  const [a, b] = SCALE[id]; scaleEl.innerHTML = `<b>${a}</b> ${b}`;
  c2.classList.toggle('on', TWO_D.has(id));
  stage.classList.toggle('twod', TWO_D.has(id));
  stage.classList.toggle('flat', !ready && TWO_D.has(id)); gate.hidden = ready || TWO_D.has(id);
  if (!quiet) { const t = document.getElementById(`t-${id}`), row = t?.parentElement; if (t && row) row.scrollLeft = Math.max(0, t.offsetLeft - row.clientWidth / 2 + t.offsetWidth / 2); }
  if (id !== 'hardware') focusCat = null;
  if (id === 'lab') labUpdate(); else stageReadout();
  userCam = false; camGo(id);
  if (ready) applyCats();
  window.__fi.stage = id; dirty = true; draw2d();
}
function stageReadout() {
  if (STAGES[si] === 'lab') { labUpdate(); return; }
  const id = STAGES[si], n = D.need, e = D.engine, ch = D.channels.variants[view === 'exp' ? lab.variant : 'C1'], md = D.modeled;
  const row = (a, b, c = '') => `<div><dt>${a}</dt><dd class="num ${c}">${b}</dd></div>`;
  let h = '';
  if (id === 'need') h = row('Departure mass', `${Math.round(n.departure_t).toLocaleString('en')} t`) + row('Cruise speed', `${n.cruise_c.toFixed(3)} c`) + row('Exhaust speed', `${n.exhaust_c.toFixed(3)} c`) +
    row('Thrust', `${(n.thrust_N / 1e6).toFixed(1)} MN`) + row('Fusion power (four engines)', W(n.fusion_W)) + row('Fusion power per engine', W(n.fusion_W / 4)) + row('Burns', `${n.burns} × ${n.burn_d.toFixed(1)} d`) + row('Heat allowed in the drive', W(n.hot_budget_W));
  else if (id === 'hardware') h = row('Parts per engine', M ? M.parts.length : 264) + row('Engines', 4) + row('Burn point aft of the shield', '6 m') + row('Coils', e.coils.map(c => c.name).join(' '));
  else if (id === 'magnets') { const k = Math.min(1, u * 1.4); h = row('Coil current', `${(k * 100).toFixed(0)} %`) + row('Stored field energy', `${(k * k * e.stored_J / 1e9).toFixed(2)} GJ`) +
    row('Field at the burn point', `${(k * e.B_burn_T).toFixed(2)} T`) + row('Windings', `${e.cold_K} K`) + row('Ramp at 100 MW', `${(D.startup.steps[2].value.charge_s).toFixed(0)} s (illustrative)`) +
    row('Pulse bank', `${D.startup.steps[0].value.bank_J / 1e6} MJ at ${D.startup.steps[0].value.bank_W / 1e6} MW`, 'bad'); }
  else if (id === 'fuel') { const r = LED(), pd = D.ledger.design.particles, i = pd.injected, A = 1.66053906660e-27, ms = stateOf('MISSION');
    h = row('Target injected per pulse', `${(r.mass_kg * 1e6).toFixed(2)} mg (D ${(i.D * 2.0141 * A * 1e6).toFixed(2)}, ³He ${(i.He3 * 3.01603 * A * 1e6).toFixed(2)})`) +
    row(r.state === 'DESIGN' ? 'Reacted per pulse (from the yield)' : 'Reacted per pulse (burn)', `${(r.reacted_kg * 1e6).toFixed(2)} mg, ${pct(r.burn_fraction)} of the target`) +
    row('Energy per pulse · rate', `${(r.fusion_J / 1e9).toFixed(2)} GJ · ${Math.round(r.Hz).toLocaleString('en')} Hz`) + row('Fusion per engine', W(r.fusion_W)) +
    row('Mission needs per engine', `${W(D.ledger.need.fusion_per_engine_W)} (${(D.ledger.need.fusion_per_engine_W / r.fusion_W).toFixed(1)}×)`, 'bad') +
    row('Mission fuel per engine: reacted, fed (burn-up 0.8)', `${(ms.reacted_kg_s * 1e3).toFixed(0)}, ${(ms.injected_kg_s * 1e3).toFixed(0)} g/s (mission state)`) +
    row('H₂ reaction mass', 'mission state only; heating it is not modelled'); }
  else if (id === 'nucleus') { const nu = D.nuclear; h = row('Coulomb barrier', `${nu.barrier_MeV.toFixed(2)} MeV`) + row('Gamow energy', `${(nu.gamow_keV / 1e3).toFixed(2)} MeV`) +
    row('Most reactions at (100 keV plasma)', `${nu.gamow_peak_keV.toFixed(0)} keV`) + row('Cross section there', `${nu.points[0].sigma_fus_b.toFixed(2)} b`) + row('Proton', `${nu.products.p.MeV.toFixed(2)} MeV, ${nu.products.p.v_c.toFixed(3)} c`) + row('⁴He', `${nu.products.alpha.MeV.toFixed(2)} MeV, ${nu.products.alpha.v_c.toFixed(3)} c`) +
    row('Hard (90°) encounters per fusion, 100 keV', Math.round(1 / D.accounting.encounter.per_close_90)); }
  else if (id === 'many') { const ec = D.accounting.encounter; h = row('Fusion per hard (90°) encounter, 100 keV', `1 in ${Math.round(1 / ec.per_close_90)}`) +
    row(`Same at ${ec.peak_keV.toFixed(0)} keV`, `1 in ${(1 / ec.peak_per_close_90).toFixed(1)}`) +
    row('Deflections per fusion, 100 keV (all passes)', `about ${(Math.round(1 / ec.per_deflection / 1000) * 1000).toLocaleString('en')}`) + row('Nuclei pairs in one target', E(D.fuel.nuclei_pairs)); }
  else if (id === 'ignition') { const b = D.plasma.burn, r = view === 'concept' ? null : LED(), c = r ? null : D.ledger.grid.cells[D.ledger.grid.design], q = r || pulseLedger(c, D.ledger.target_mass_kg, D.ledger.design_Hz, nozOf('C1'), 1);
    h = row('Target areal density', `${view === 'exp' ? lab.rhoR : b.rhoR_design} g/cm²`) + row('Gain (fusion / heat in)', (q.fusion_J / q.heat_in_J).toFixed(1)) + row('Fuel used, by mass', pct(q.burn_fraction)) +
      row('X-rays (share of fusion energy)', pct(q.xray_J / q.fusion_J), 'bad') + row('Neutrons', pct(q.neutron_J / q.fusion_J)) + row('Left in the plasma (steerable)', pct(q.plasma_J / q.fusion_J)) +
      row('Design point assumes as jet', pct(stateOf('DESIGN').jet_share), view === 'concept' ? '' : 'bad') +
      (view !== 'concept' ? row('Driver heat into the fuel (lower bound)', W(q.driver_abs_W), 'bad') + row(`Driver electric at ${pct(D.ledger.wallplug)}`, W(q.driver_elec_W), 'bad') + row('Compression to this density', 'not modelled', 'bad') : row('Compression to this density', 'not modelled', 'bad')); }
  else if (id === 'nozzle') { const s = D.nozzle.mult[view === 'exp' ? (lab.field === '4' ? '4' : '1') : '1']['p_14.7MeV'], r = LED(), nd = D.ledger.need;
    h = row(`Exhaust speed (${r.state === 'DESIGN' ? 'design' : 'ledger'})`, r.coupled ? `${Math.round(r.exhaust_m_s / 1e3).toLocaleString('en')} km/s` : 'not modelled', r.state === 'DESIGN' ? '' : 'bad') +
      row('Mission exhaust speed', `${Math.round(nd.exhaust_m_s / 1e3).toLocaleString('en')} km/s`) +
      row('Thrust, four engines', r.coupled ? MN(4 * r.thrust_N) : 'not modelled', 'bad') + row('Mission thrust', MN(4 * nd.thrust_per_engine_N)) +
      row(r.state === 'DESIGN' ? 'Jet share (design assumption)' : 'Jet share of fusion', pct(r.jet_share), r.state === 'DESIGN' ? '' : 'bad') +
      (view !== 'concept' ? row('Nozzle axial efficiency (compact study)', (r.noz || nozOf('C1')).eta.toFixed(2), 'bad') + row('Sampled protons leaving aft', pct(s.share.aft)) + row('Sampled protons hitting hardware', pct(s.share.hit), 'bad') : ''); }
  else if (id === 'losses') { const r = LED(), st = stateOf('STEADY'), ch = D.channels.variants[view === 'exp' ? lab.variant : 'C1'];
    h = row('Fusion per engine', W(r.fusion_W)) + row('Directed jet', W(r.jet_W)) + row('X-rays', W(r.xray_J * r.Hz), 'bad') + row('Neutrons', W(r.neutron_J * r.Hz)) +
      row('Plasma on hardware', W(r.hit_J * r.Hz), 'bad') + row('Plasma not directed', W(r.side_J * r.Hz)) + row('Heat into the engine (per engine)', W(r.engine_heat_W), 'bad') +
      row('Radiator share', W(r.budget_W)) + row('Heat over radiator', X(r.heat_over), 'bad') + row('Winding fluence (steady-source study)', `${X(ch.winding_over)} limit`, 'bad') +
      row('Steady-plasma study (different regime)', `X-rays ${pct(st.xray_share + st.sync_share)}, heat ${X(ch.over)}`); }
  if (id === 'thermal') { readEl.innerHTML = `<p class="fi-view-tag model">Thermal study at the coupled pulse (one engine). ${chip('IMPORTED')}</p>${thReadout(Math.max(0, stepOf(id)))}`;
    hud.innerHTML = `<div class="hrow"><span>Engine scale</span><b>thermal study</b></div><div class="hrow warn"><span>Hardware</span><b>WORK, not canon</b></div>`; return; }
  const tag = view === 'concept' ? (['need', 'hardware'].includes(id) ? '' : '<p class="fi-view-tag concept">Intended operation: what the engine is meant to do.</p>')
    : view === 'model' ? '<p class="fi-view-tag model">Current engineering model: what the calculations predict.</p>' : `<p class="fi-view-tag exp">Experiment: variant ${lab.variant}, field ×${lab.field}.</p>`;
  const bar = ['need', 'hardware', 'magnets'].includes(id) ? '' : ledgerBar(LED());
  readEl.innerHTML = `${tag}${bar}<dl class="fi-dl">${h}</dl>`;
  const cfg = view === 'exp' ? (lab.variant === 'C1' ? 'C1 approved cluster' : `${lab.variant} experimental, not canon`) : 'C1 approved cluster';
  hud.innerHTML = h ? `<div class="hrow"><span>${esc(SCALE[id][0])}</span><b>${esc(view === 'concept' ? 'intended' : view === 'model' ? 'modeled' : 'experiment')}</b></div>`
    + `<div class="hrow ${view === 'exp' && lab.variant !== 'C1' ? 'warn' : ''}"><span>Engine</span><b>${esc(cfg)}</b></div>` : '';
}

// ---- cameras ---------------------------------------------------------------------------------------------------------------------------------
function camKey(id) {
  const c = new THREE.Vector3(D.ship.cluster_front - 18, 0, 0), b = burnW[0], ax = new THREE.Vector3(1, 0, 0).transformDirection(N1);
  const side = new THREE.Vector3(0, 0, 1).transformDirection(N1);
  const near = (d, up = 0.35, back = 0.5) => ({ t: b.clone().addScaledVector(ax, 4), p: b.clone().addScaledVector(side, -d).addScaledVector(ax, -d * back).add(new THREE.Vector3(0, d * up, 0)) });
  switch (id) {
    case 'need': return { t: new THREE.Vector3(-20, 0, 0), p: new THREE.Vector3(-330, 170, 330) };
    case 'hardware': return { t: c, p: c.clone().add(new THREE.Vector3(-95, 55, 85)) };
    case 'magnets': return near(34, 0.45, 0.35);
    case 'lab': return { t: c, p: c.clone().add(new THREE.Vector3(-75, 45, 70)) };
    case 'fuel': return near(20, 0.3, 0.2);
    case 'nucleus': return near(1.4, 0.15, 0.05);           // into the burn point; the 2-D scene fades in over it
    case 'many': case 'ignition': return near(3, 0.2, 0.1);
    case 'nozzle': { const k = stepOf(id);                 // close on one engine for the field and one proton, then back out for the exhaust
      if (k === 0) return near(34, 0.3, 0.15); if (k <= 2) return near(24, 0.22, 0.05);
      if (k === 3) return { t: c.clone().add(new THREE.Vector3(-45, 0, 0)), p: c.clone().add(new THREE.Vector3(-120, 55, 100)) };
      return { t: c.clone().add(new THREE.Vector3(-30, 0, 0)), p: c.clone().add(new THREE.Vector3(-150, 70, 120)) }; }
    case 'thermal': { const k = stepOf(id);
      if (k === 0) return near(30, 0.3, 0.25); if (k === 1) return near(26, 0.3, 0.25); if (k === 2) return near(24, 0.45, 0.1); if (k === 3) return near(20, 0.35, 0.15);
      if (k === 4) return near(30, 0.45, -0.1); return near(34, -0.3, 0.15); }
    case 'losses': { const k = stepOf(id);
      if (k <= 1) return near(48, 0.35, 0.1); if (k === 2) return near(30, 0.25, 0.1);
      return { t: new THREE.Vector3(-150, 0, 0), p: new THREE.Vector3(-300, 120, 200) }; }
  }
  return { t: c, p: c.clone().add(new THREE.Vector3(-80, 40, 80)) };
}
function camGo(id) {
  if (!camera) return;
  const k = camKey(id), asp = camera.aspect || 1.6;
  if (asp < 1.3) k.p = k.t.clone().add(k.p.clone().sub(k.t).multiplyScalar(Math.min(2.6, 1.4 / asp)));   // portrait screens: step back so the frame holds the same subject
  camFrom = { t: controls.target.clone(), p: camera.position.clone() }; camTo = k; camT = reduced || camFrom.p.lengthSq() === 0 ? 1 : 0;
  if (camT === 1) { camera.position.copy(k.p); controls.target.copy(k.t); controls.update(); }
}

function stepOf(id) { return id === 'nozzle' ? (u < 0.16 ? 0 : u < 0.36 ? 1 : u < 0.58 ? 2 : u < 0.8 ? 3 : 4) : id === 'losses' ? (u < 0.22 ? 0 : u < 0.44 ? 1 : u < 0.66 ? 2 : 3) : id === 'thermal' ? Math.min(5, Math.floor(u * 6)) : -1; }
let lastStep = '';
// ---- per-frame state ------------------------------------------------------------------------------------------------------------------------
const ease = x => x < 0.5 ? 2 * x * x : 1 - (-2 * x + 2) ** 2 / 2;
let LEDc = null, LEDk = '';
function update(t) {
  const id = STAGES[si];
  const lk = view + JSON.stringify(lab); if (lk !== LEDk || !LEDc) { LEDk = lk; LEDc = LED(); }
  // progressive disclosure: one mechanism at a time in Thrust (field, one product, many, exhaust, thrust) and Losses (photons, neutrons, charged, all)
  const NZ = id === 'nozzle' ? stepOf(id) : -1, LS = id === 'losses' ? stepOf(id) : -1, TS = id === 'thermal' ? stepOf(id) : -1;
  const sk = `${id}:${stepOf(id)}`; if (sk !== lastStep) { const first = !lastStep.startsWith(id + ':'); lastStep = sk; if (!first && !userCam && stepOf(id) >= 0) camGo(id); if (!first && id === 'thermal') stageReadout(); }
  caption(id, NZ, LS, TS);
  thUpdate(t, id, TS);
  // categories
  const charge = id === 'magnets' ? Math.min(1, u * 1.4) : ['need', 'hardware'].includes(id) ? 0 : 1;
  const heatOn = layers.heat && ((id === 'losses' && LS >= 2) || (id === 'lab') || (view !== 'concept' && NZ >= 2) || TS === 4);
  const over = Math.log10(Math.max(1, LEDc.heat_over));
  Object.entries(catMats).forEach(([cat, { mat, base }]) => {
    let op = 1, em = 0;
    if (focusCat) {
      if (cat === focusCat) em = 0.35;
      else if (catMode === 'isolate') op = 0; else if (catMode === 'xray') op = 0.12; else op = 0.55;
    }
    if ((NZ >= 0 && NZ <= 2) || (LS >= 0 && LS <= 1)) op = Math.min(op, 0.16);
    if (TS >= 1 && !['HOT_THERMAL', 'CRYOGENIC'].includes(cat)) op = Math.min(op, TS <= 3 ? 0.35 : 0.22);
    if (TS === 4 && cat === 'CRYOGENIC') op = Math.min(op, 0.22);      // the physics leads: hardware turns to glass while one mechanism is shown
    if (heatOn && ['MAGNETIC_NOZZLE', 'SHIELDING', 'MAGNETIC_COILS', 'HOT_THERMAL'].includes(cat)) em = Math.max(em, Math.min(1, over / 4) * (0.6 + 0.4 * Math.sin(t * 3)));
    if (id === 'magnets' && cat === 'MAGNETIC_COILS' || id === 'magnets' && cat === 'MAGNETIC_NOZZLE') em = Math.max(em, 0.25 * charge);
    mat.opacity = op; mat.visible = op > 0.01; mat.depthWrite = op > 0.9;
    mat.emissive.copy(heatOn && em > 0.36 ? new THREE.Color(COL.bad) : base).multiplyScalar(em);
    mat.clippingPlanes = layers.cut && ['hardware', 'magnets', 'fuel', 'nozzle', 'losses', 'lab'].includes(id) ? [cutPlane] : [];
  });
  shipGroup.visible = layers.ship;
  // field lines grow with the coil current
  if (fieldGroup.userData.mat) {
    const show = layers.field && !['need', 'hardware'].includes(id);
    fieldGroup.visible = show;
    fieldGroup.userData.mat.opacity = show ? (NZ === 0 ? 0.85 : NZ > 0 ? 0.2 : LS >= 0 && LS < 3 ? 0 : LS === 3 ? 0.15 : 0.55) * charge : 0;
    const fk = id === 'magnets' ? Math.min(1, u * 1.6) : 1;
    fieldLines.forEach(l => l.geometry.setDrawRange(0, 2 * upTo(l.userData.frac, fk)));
  }
  // target and plasma
  const fuelOn = layers.fuel && ['fuel', 'nucleus', 'many', 'ignition'].includes(id);
  const mag = M.parts.find(p => p.name === 'VTX_Target_Magazine')?.centroid || new THREE.Vector3(-6, 0, 0);
  const tu = id === 'fuel' ? Math.min(1, u * 2) : 1;
  targetMesh.visible = fuelOn && tu < 1;
  targetMesh.position.copy(new THREE.Vector3(THREE.MathUtils.lerp(mag.x, BURN, ease(tu)), 0, 0).applyMatrix4(N1));
  beams.material.opacity = fuelOn && id === 'fuel' && u > 0.45 && u < 0.62 ? 0.9 : 0;
  const pl = plasmaPts.geometry.attributes.position, sd = plasmaPts.userData.seed, R = id === 'fuel' ? (u > 0.55 ? Math.min(3, (u - 0.55) * 12) : 0) : 1.2;
  plasmaPts.visible = fuelOn && R > 0;
  for (let i = 0; i < pl.count; i++) {
    const w = t * (1.5 + (i % 7) * 0.3);
    const p = new THREE.Vector3(sd[i * 3] * R + 0.25 * Math.sin(w + i), sd[i * 3 + 1] * R + 0.25 * Math.cos(w * 1.3 + i), sd[i * 3 + 2] * R).add(burnW[0]);
    pl.setXYZ(i, p.x, p.y, p.z);
  }
  pl.needsUpdate = true;
  // hydrogen (after ignition)
  const h2On = layers.fuel && (NZ >= 3 || id === 'lab');
  h2pts.visible = h2On;
  if (h2On) {
    const a = h2pts.geometry.attributes.position, s = h2pts.userData.seed, ax = new THREE.Vector3(1, 0, 0).transformDirection(N1);
    for (let i = 0; i < a.count; i++) {
      const f = (s[i * 3] + t * 0.25) % 1, ang = s[i * 3 + 1] * Math.PI * 2, rr = 6.8 * (1 - f) + 1.5;
      const loc = new THREE.Vector3(BURN + 2 - f * 6, rr * Math.cos(ang), rr * Math.sin(ang)).applyMatrix4(N1); a.setXYZ(i, loc.x, loc.y, loc.z);
    }
    a.needsUpdate = true;
  }
  // plume
  const plumeOn = NZ >= 3 || LS === 3 || id === 'lab';
  plume.visible = plumeOn;
  if (plumeOn) {
    const a = plume.geometry.attributes.position, s = plume.userData.seed, n4 = a.count / 4;
    const eff = view === 'concept' ? 0.9 : D.channels.variants[view === 'exp' || id === 'lab' ? lab.variant : 'C1'].eta;
    for (let i = 0; i < a.count; i++) {
      const e = Math.floor(i / n4), f = (s[i * 3] + t * 0.6) % 1, ang = s[i * 3 + 1] * Math.PI * 2;
      const spread = (1 - eff) * 2.4 + 0.15, rr = (2 + f * 60 * spread) * Math.sqrt(s[i * 3 + 2]);
      const loc = new THREE.Vector3(BURN - 8 - f * 90, rr * Math.cos(ang), rr * Math.sin(ang)).applyMatrix4(engineMats[e]); a.setXYZ(i, loc.x, loc.y, loc.z);
    }
    a.needsUpdate = true; plume.material.opacity = 0.35 + 0.4 * eff;
  }
  // paths
  const pathsOn = layers.paths && (NZ >= 2 || id === 'lab' || LS >= 2);
  const rep = pathGroup.userData.rep;
  if (rep) { const on = layers.paths && NZ >= 1; rep.line.visible = on; rep.head.visible = on && NZ === 1;
    if (on) { const k = NZ === 1 ? sm(0.16, 0.34, u) : 1, n = Math.max(2, Math.floor(rep.pts.length * k)); rep.line.geometry.setDrawRange(0, n); rep.head.position.copy(rep.pts[n - 1]); rep.line.material.opacity = NZ === 1 ? 1 : 0.5; } }
  pathGroup.visible = pathsOn;
  if (pathsOn) {
    const conceptOnly = view === 'concept' && id === 'nozzle';
    const k = id === 'nozzle' ? sm(0.36, 0.56, u) : (t * 0.25) % 1;
    pathLines.forEach(l => {
      l.visible = (!conceptOnly || l.userData.key === 'AFT') && !(LS === 2 && l.userData.key === 'AFT');
      l.geometry.setDrawRange(0, 2 * upTo(l.userData.frac, k));
      l.material.opacity = NZ >= 3 ? 0.35 : 0.85;
    });
    const hm = pathGroup.userData.heads, mx = new THREE.Matrix4(), zero = new THREE.Matrix4().makeScale(0, 0, 0);
    hm.userData.heads.forEach((h, i) => {
      if (conceptOnly && !h.aft) { hm.setMatrixAt(i, zero); return; }
      const n = Math.max(1, Math.floor((h.pts.length - 1) * k)); hm.setMatrixAt(i, mx.makeTranslation(h.pts[n].x, h.pts[n].y, h.pts[n].z));
    });
    hm.instanceMatrix.needsUpdate = true;
  }
  // radiation
  const radOn = layers.rad && (id === 'losses' || id === 'lab' || TS === 0 || TS === 1);
  radGroup.visible = radOn;
  if (radOn) {
    const fl = 0.35 + 0.25 * Math.sin(t * 9);
    const phOn = LS < 0 || LS === 0 || LS === 3, nOn = LS < 0 || LS === 1 || LS === 3;
    radGroup.userData.ph.material.opacity = phOn ? (LS === 0 ? 0.22 : 0.12) : 0; radGroup.userData.n.material.opacity = nOn ? (LS === 1 ? 0.2 : 0.1) : 0;
    const pk = radGroup.userData.packets;                 // photons as fast packets along straight rays; neutrons as slower dots that ignore the field
    pk.ph.visible = phOn; pk.n.visible = nOn;
    [[pk.ph, 0.9], [pk.n, 0.35]].forEach(([o, sp]) => { if (!o.visible) return; const a = o.geometry.attributes.position, S0 = o.userData.seg, ph = o.userData.phase;
      for (let i = 0; i < a.count; i++) { const j = o.userData.idx[i], f = (t * sp + ph[i]) % 1; a.setXYZ(i, S0[j * 6] + (S0[j * 6 + 3] - S0[j * 6]) * f, S0[j * 6 + 1] + (S0[j * 6 + 4] - S0[j * 6 + 1]) * f, S0[j * 6 + 2] + (S0[j * 6 + 5] - S0[j * 6 + 2]) * f); }
      a.needsUpdate = true; });
    radGroup.userData.ship.material.opacity = LS >= 0 && LS < 3 ? 0 : (view === 'exp' || id === 'lab') && lab.variant === 'C4' ? 0.15 : 0.55;
  }
  thrustArrow.visible = (id === 'need' && u > 0.5) || NZ === 4;
  // markers
  markerEls.forEach(m => {
    const thp = /^ENG-0[456]/.test(m.p.id);
    const on = layers.problems && (thp ? id === 'thermal' && (TH_MARK[TS] || []).includes(m.p.id) : (LS === 3 || id === 'lab' || (view === 'model' && (NZ === 4 || id === 'magnets'))));
    const appl = m.p.variants.includes(id === 'lab' || view === 'exp' ? lab.variant : 'C1');
    m.el.hidden = !(on && appl && !TWO_D.has(id));
  });
}

const CAP = {
  nozzle: ['1 · The magnetic nozzle: the field of the six coils (calculated vacuum field, field lines drawn)',
    '2 · One 14.7 MeV proton: it spirals round a field line (0.37 m circle at the burn) and is turned aft (sampled test particle)',
    '3 · Many products: each follows the field; green leave aft, red strike hardware (sampled)',
    '4 · Together the products and the plasma push the field open and leave as exhaust; hydrogen reaction mass joins (coupling SPECULATIVE)',
    '5 · The momentum carried aft is the thrust'],
  losses: ['1 · Photons (X-rays): straight lines from the burn, unaffected by the field; they end on whatever they meet',
    '2 · Neutrons: uncharged and slower, they ignore the field and pass into the coils and structure',
    '3 · Charged products that miss the exit: they loop onto coils and shield and heat them',
    '4 · All together: heat piped out of the hardware against what the radiators can reject'],
  thermal: ['1 · At the source: the burn\'s charged products heat its electrons, which glow as X-rays; pick a lever to follow it to thrust and heat',
    '2 · Supermirrors: where a grazing X-ray mirror could act, and why the engine\'s faces are the wrong angle',
    '3 · Edge-on blades and cones (adopted): every member shows the burn only its edge',
    '4 · Protection layers: the thin blanket (option) moves heat into lithium; it does not remove it',
    '5 · Hot and warm circuits: lithium at 1500 → 1800 K and NaK at 650 → 850 K, manifolds to the ship\'s radiators',
    '6 · Cryogenic circuit, service interfaces, and the whole path from the reaction to space'],
};
let capKey = '';
function caption(id, NZ, LS, TS = -1) {
  let s = '';
  const r = LEDc || LED(), noz = r.noz || nozOf('C1');
  if (NZ >= 0) { s = CAP.nozzle[NZ]; if (NZ === 2) s += view === 'concept' ? ': intended, all leave aft' : `: modeled, ${pct(noz.eta)} axial efficiency for ${view === 'exp' ? lab.variant : 'C1'}`;
    if (NZ === 4) s += r.coupled ? `: ${MN(4 * r.thrust_N)} for four engines (${r.state === 'DESIGN' ? 'design point' : 'ledger'}; the mission needs ${MN(4 * D.ledger.need.thrust_per_engine_N)})` : ': not computed (hydrogen coupling not modelled)'; }
  else if (LS >= 0) { s = CAP.losses[LS]; const v = [W(r.xray_J * r.Hz) + ' per engine, ' + W(r.x_abs_J * r.Hz) + ' absorbed', W(r.neutron_J * r.Hz) + ' per engine (ENG-033)', W(r.hit_J * r.Hz) + ' per engine', `${W(r.engine_heat_W)} per engine against ${W(r.budget_W)}: ${X(r.heat_over)} (ENG-030)`][LS]; s += ': ' + v; }
  if (TS >= 0) { const T = D.thermal, b = D.source.levers[0]; s = CAP.thermal[TS] + ': ' + [`${pct(b.xray_share)} of the fusion energy leaves as X-rays (ENG-061)`,
    `coatings return ${T.strategies.A.coupled_reflected_share.toExponential(1)} of the X-rays that strike (ENG-040)`,
    `members keep ${pct(T.strategies.B.keep_share)} of their heat; the edge takes ${X(T.strategies.B.detail.edge.over_limit)} its limit (ENG-057)`,
    `${W(T.strategies.C.thin.moved_to_hot_W)} moved for ${Math.round(T.strategies.C.thin.mass_t)} t; the 20 K load stays ${W(T.strategies.C.thin.cryo_after_W)} (ENG-059)`,
    `the drawn lines carry ${W(T.hot.drawn_line_cap_W)} of ${W(T.hot.heat_W + T.hot.warm_uncooled_W)} (ENG-046)`,
    `${W(T.cryo.refrig_W)} of refrigeration; still ${X(T.comparison.find(r => r.id === 'B+Ct').over_budget_after)} the radiator share (ENG-030)`][TS]; }
  const key = s + id;
  if (key === capKey) return; capKey = key;
  evcap.innerHTML = s ? `<span class="step">${id === 'nozzle' ? 'THRUST' : id === 'thermal' ? 'HEAT' : 'LOSSES'} · step ${(NZ >= 0 ? NZ : LS >= 0 ? LS : TS) + 1} of ${NZ >= 0 ? 5 : TS >= 0 ? CAP.thermal.length : 4}</span><span>${esc(s)}</span>` : '';
}
function placeMarkers(w, h) {
  markerEls.forEach(m => {
    if (m.el.hidden) return;
    const p = m.at.clone().project(camera);
    const off = p.z > 1 || p.x < -1.1 || p.x > 1.1 || p.y < -1.1 || p.y > 1.1;
    m.el.style.visibility = off ? 'hidden' : 'visible';
    m.el.style.transform = `translate(${((p.x + 1) / 2 * w).toFixed(0)}px, ${((1 - p.y) / 2 * h).toFixed(0)}px) translate(-50%, -50%)`;
  });
}

// ---- 2-D views (nuclear, plasma, ignition): ILLUSTRATIVE drawings over the data ----------------------------------------------------------------
let c2w = 0, c2h = 0, ctx = null;
function sizeC2() {
  const r = stage.getBoundingClientRect(), dpr = Math.min(devicePixelRatio || 1, 2);
  if (Math.round(r.width * dpr) !== c2.width || Math.round(r.height * dpr) !== c2.height) { c2.width = Math.round(r.width * dpr); c2.height = Math.round(r.height * dpr); }
  ctx = c2.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); c2w = r.width; c2h = r.height;
}
function txt(s, x, y, col = COL.ink, size = 13, align = 'left', weight = 400) { ctx.fillStyle = col; ctx.font = `${weight} ${size}px system-ui, sans-serif`; ctx.textAlign = align; ctx.fillText(s, x, y); }
function nucleus(x, y, pr, nn, r, label, col) {
  const k = pr + nn, pts = [];
  for (let i = 0; i < k; i++) { const a = i / k * Math.PI * 2 + 0.6; pts.push([x + (k > 1 ? r * 0.55 : 0) * Math.cos(a), y + (k > 1 ? r * 0.55 : 0) * Math.sin(a), i < pr]); }
  pts.forEach(([px, py, p]) => { ctx.beginPath(); ctx.arc(px, py, r * 0.62, 0, Math.PI * 2); ctx.fillStyle = p ? COL.bad : COL.neutron; ctx.globalAlpha = 0.92; ctx.fill(); ctx.globalAlpha = 1;
    if (p) txt('+', px, py + 4, '#1B2633', r * 0.7, 'center', 700); });
  ctx.beginPath(); ctx.arc(x, y, r * 1.35, 0, Math.PI * 2); ctx.strokeStyle = col; ctx.lineWidth = 1.5; ctx.stroke();
  txt(label, x, y + r * 2.1, COL['ink-strong'], 13, 'center', 600);
}
function axes(x, y, w, h, title, xl, yl) {
  ctx.strokeStyle = COL['line-strong']; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x, y + h); ctx.lineTo(x + w, y + h); ctx.stroke();
  txt(title, x, y - 8, COL['ink-strong'], 12, 'left', 600); txt(xl, x + w, y + h + 16, COL.muted, 11, 'right'); txt(yl, x + 4, y + 12, COL.muted, 11);
}
function logx(v, a, b, x, w) { return x + (Math.log10(v) - Math.log10(a)) / (Math.log10(b) - Math.log10(a)) * w; }

// The three microscopic stages are scenes first (what happens) and graphs second (the Graphs button). Scene time is u × DUR[stage], so
// Play, Pause and the scrubber drive them like the 3-D stages. Every scene is ILLUSTRATIVE motion over CALCULATED numbers from the study.
let graphs = false, sdt = 0, enterT = 0, prevTwoD = false;
const sm = (a, b, x) => { const k = Math.min(1, Math.max(0, (x - a) / (b - a))); return k * k * (3 - 2 * k); };
const hexA = (h, a) => { const n = parseInt(h.slice(1), 16); return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${a})`; };
const sci = v => { const e = Math.floor(Math.log10(v)), m = v / 10 ** e; return `${m.toFixed(1)} × 10${String(e).replace('-', '⁻').replace(/\d/g, c => '⁰¹²³⁴⁵⁶⁷⁸⁹'[c])}`; };
function glow(x, y, r, col, a) { const g = ctx.createRadialGradient(x, y, 0, x, y, r); g.addColorStop(0, hexA(col, a)); g.addColorStop(1, hexA(col, 0)); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill(); }
function arrow(x0, y0, x1, y1, col, w = 2) {
  const a = Math.atan2(y1 - y0, x1 - x0), h = 7 + w * 2;
  ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = w; ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x1 - h * Math.cos(a - 0.4), y1 - h * Math.sin(a - 0.4)); ctx.lineTo(x1 - h * Math.cos(a + 0.4), y1 - h * Math.sin(a + 0.4)); ctx.fill();
}
function squiggle(x, y, a, len, col, alpha, ph = 0) {      // a photon: a short wave packet along direction a
  ctx.strokeStyle = hexA(col, alpha); ctx.lineWidth = 1.5; ctx.beginPath();
  for (let s = 0; s <= len; s += 2) { const w = Math.sin(s * 0.55 + ph) * 3.2 * Math.sin(Math.PI * s / len); const px = x + s * Math.cos(a) - w * Math.sin(a), py = y + s * Math.sin(a) + w * Math.cos(a); s ? ctx.lineTo(px, py) : ctx.moveTo(px, py); }
  ctx.stroke();
}
function banner(title, sub, col = COL['ink-strong']) {
  // below the scale chip; the subtitle wraps clear of the scale ladder (top-right)
  const narrow = c2w < 600, y = narrow ? 58 : 52, band = narrow ? c2w : c2w - 180;
  const T = wrap(title, Math.floor((narrow ? c2w : c2w - 60) / (narrow ? 8.6 : 9.4))), lh = narrow ? 17 : 20;
  T.forEach((s, i) => txt(s, c2w / 2, y + i * lh, col, narrow ? 14 : 17, 'center', 600));
  if (sub) wrap(sub, Math.floor(band / (narrow ? 6.4 : 6.6))).forEach((s, i) => txt(s, c2w / 2, y + 2 + T.length * lh + i * 15, COL.muted, narrow ? 11 : 12, 'center'));
}
function wrap(s, n) { const out = []; let line = ''; s.split(' ').forEach(w => { if ((line + ' ' + w).trim().length > n) { out.push(line.trim()); line = w; } else line += ' ' + w; }); if (line.trim()) out.push(line.trim()); return out; }
function chipC(x, y, label, col) { ctx.font = '600 10px ui-monospace, monospace'; const w = ctx.measureText(label).width + 10; ctx.strokeStyle = col; ctx.lineWidth = 1; ctx.strokeRect(x, y - 10, w, 14); ctx.fillStyle = col; ctx.textAlign = 'left'; ctx.fillText(label, x + 5, y + 1); return w; }
// zoom rings: the camera passing through scales on the way in (or out) of the microscopic view
function zoomRings(k, inward, labels, note = 'a jump in scale, not a continuous zoom') {
  if (k >= 1) return;
  const cx = c2w / 2, cy = c2h / 2, S = Math.max(c2w, c2h);
  ctx.save(); ctx.globalAlpha = 1 - sm(0.75, 1, k);
  for (let i = 0; i < 7; i++) {
    let f = ((inward ? k : 1 - k) * 2.2 + i / 7) % 1; const r = S * 0.04 * Math.pow(18, f);
    ctx.strokeStyle = hexA(COL.info, 0.35 * (1 - f)); ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(cx, cy, r, 0, 7); ctx.stroke();
  }
  const j = Math.min(labels.length - 1, Math.floor(k * labels.length));
  txt(labels[j], cx, cy + 5, COL['ink-strong'], 15, 'center', 600);
  if (note) txt(note, cx, cy + 24, COL.muted, 11, 'center');
  ctx.restore();
}

// ---- 4 · one reaction: selected encounters, then one fusion in detail --------------------------------------------------------------------------
const KC = 1.43996 * 2;                    // Z1 Z2 e² / 4πε0 in MeV·fm for D + ³He
const NUC = { enc: null };
function encounter(E_keV, b, L = 60) {     // relative motion in the repulsive Coulomb field (CALCULATED trajectory, units fm and v0 = 1)
  const rc = KC / (E_keV / 1e3), out = [], h = 0.01; let x = -Math.sqrt(L * L - b * b), y = b;
  const s2 = 1 - rc / L, c = b / x;               // start at L with the energy (speed) and angular momentum (b × v∞) the pair has at infinity
  let vx = (c * c + Math.sqrt(c ** 4 - (1 + c * c) * (c * c - s2))) / (1 + c * c), vy = c * (vx - 1), rmin = 1e9;
  for (let i = 0; i < 200000; i++) {
    const r = Math.hypot(x, y), a = rc / (2 * r * r * r);
    vx += a * x * h; vy += a * y * h; x += vx * h; y += vy * h; rmin = Math.min(rmin, r);
    if (i % 20 === 0) out.push([x, y]);
    if (r > L * 1.25 && x * vx + y * vy > 0) break;
  }
  rmin = rc / 2 * (1 + Math.sqrt(1 + (2 * b / rc) ** 2));      // closest approach, analytic (the drawn path matches it closely)
  return { pts: out, rmin, theta: b > 0 ? 2 * Math.atan(rc / (2 * b)) * 180 / Math.PI : 180, rc };   // Rutherford deflection
}
function drawNucleus() {
  const nu = D.nuclear, st = u * DUR.nucleus, narrow = c2w < 600;
  ctx.clearRect(0, 0, c2w, c2h); ctx.fillStyle = `rgba(5,7,11,${sm(0.2, 1.5, st)})`; ctx.fillRect(0, 0, c2w, c2h);   // the burn point shows through only while the view dives in
  if (!NUC.enc) NUC.enc = [encounter(100, 34), encounter(100, 6.5), encounter(nu.gamow_peak_keV, 0)];
  const cy = graphs ? c2h * 0.4 : c2h * 0.52, cx = c2w / 2, S = Math.min(c2w, c2h * 1.3);
  const fm = Math.min(c2w * 0.46, c2h * 0.36) / 36 * (1 + 1.2 * sm(8.9, 11.2, st) * (1 - sm(13.4, 14.2, st))), R = Math.max(9, fm * 1.7);   // the view closes in on the head-on pair   // nuclei roughly to scale against the distances (≈1.7 fm radius)
  const p100 = nu.points[1], pG = nu.points[0];
  // persistent label: these are chosen, not typical
  const enc = D.accounting.encounter;
  const sel = `Selected examples, not the odds: at 100 keV a single hard (90°) encounter fuses about 1 time in ${Math.round(1 / enc.per_close_90)}`;
  const T = [1.6, 5.0, 8.4, 11.4, 13.0, 13.6, 19.0];        // phase starts (s)
  if (st < T[0]) { zoomRings(st / T[0], true, ['burn point · 1 m', 'target · 1 mm', 'plasma · 1 µm', 'two nuclei · 10 fm']); return; }
  const drawPair = (pts, k, trail = true) => {
    const n = Math.min(pts.length - 1, Math.floor(k * (pts.length - 1))), [rx, ry] = pts[n];
    const D_ = [cx - 0.6 * rx * fm, cy - 0.6 * ry * fm], H_ = [cx + 0.4 * rx * fm, cy + 0.4 * ry * fm];
    if (trail) {
      [[-0.6, COL['fn-DEUTERIUM']], [0.4, COL['fn-HELIUM3']]].forEach(([s, col]) => {
        ctx.strokeStyle = hexA(col, 0.5); ctx.lineWidth = 1.5; ctx.beginPath();
        for (let i = Math.max(0, n - 260); i <= n; i++) { const p = pts[i], X1 = cx + s * p[0] * fm, Y1 = cy + s * p[1] * fm; i === Math.max(0, n - 260) ? ctx.moveTo(X1, Y1) : ctx.lineTo(X1, Y1); }
        ctx.stroke();
      });
    }
    const r = Math.hypot(rx, ry);
    ctx.setLineDash([3, 4]); ctx.strokeStyle = hexA(COL.info, 0.55); ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(D_[0], D_[1]); ctx.lineTo(H_[0], H_[1]); ctx.stroke(); ctx.setLineDash([]);
    if (r > 8) txt(`${r.toFixed(0)} fm`, (D_[0] + H_[0]) / 2, (D_[1] + H_[1]) / 2 - 8, COL.info, 11, 'center');
    ctx.strokeStyle = hexA(COL.muted, 0.6); ctx.beginPath(); ctx.moveTo(cx - 5, cy); ctx.lineTo(cx + 5, cy); ctx.moveTo(cx, cy - 5); ctx.lineTo(cx, cy + 5); ctx.stroke();
    if (r < 45) {                                           // electric repulsion grows as 1/r²
      const f = Math.min(1, (12 / r) ** 2), ux = rx / r, uy = ry / r, Lr = 10 + 46 * f;
      arrow(D_[0], D_[1], D_[0] - ux * Lr, D_[1] - uy * Lr, hexA(COL.warn, 0.9), 2);
      arrow(H_[0], H_[1], H_[0] + ux * Lr, H_[1] + uy * Lr, hexA(COL.warn, 0.9), 2);
    }
    nucleus(D_[0], D_[1], 1, 1, R, narrow ? 'D' : 'D (deuteron)', COL['fn-DEUTERIUM']);
    nucleus(H_[0], H_[1], 2, 1, R, '³He', COL['fn-HELIUM3']);
    return { D_, H_, r };
  };
  if (st < T[2]) {                                          // two misses: deflected, never close
    const i = st < T[1] ? 0 : 1, k = (st - T[i]) / (T[i + 1] - T[i]), e = NUC.enc[i];
    drawPair(e.pts, k);
    const done = k > 0.75;
    banner(`Encounter ${i + 1} of 3: ${done ? `deflected ${e.theta.toFixed(0)}°, no fusion` : 'a D and a ³He nucleus meet at 100 keV'}`, sel);
    (narrow ? [`closest approach ${e.rmin.toFixed(0)} fm (calculated)`, `contact needs ${nu.touch_fm.toFixed(1)} fm · + centre of mass`] : [`closest approach ${e.rmin.toFixed(0)} fm (calculated) · nuclear contact needs ${nu.touch_fm.toFixed(1)} fm · + marks the centre of mass`])
      .forEach((l, i, A) => txt(l, cx, c2h - (graphs ? c2h * 0.36 : 46) - (A.length - 1 - i) * 15, COL.info, narrow ? 11 : 12, 'center'));
    if (done) { ctx.setLineDash([2, 4]); ctx.strokeStyle = hexA(COL.info, 0.5); ctx.beginPath(); ctx.arc(cx, cy, e.rmin * fm * 0.5, 0, 7); ctx.stroke(); ctx.setLineDash([]); }
  } else if (st < T[5]) {                                   // the head-on pair at the Gamow peak: turning point, tunnelling, contact
    const e = NUC.enc[2], half = e.pts.findIndex(p => p[0] > -e.rc * 1.001 && Math.hypot(p[0], p[1]) <= e.rmin * 1.002);
    const turn = half > 0 ? half / (e.pts.length - 1) : 0.5;
    let k = st < T[3] ? turn * sm(0, 1, (st - T[2]) / (T[3] - T[2])) : turn;
    const pr = drawPair(e.pts, k, true);
    if (st >= T[3]) {                                       // the classically forbidden gap and the probability leaking through it
      const g = sm(T[3], T[4], st), mx = (pr.D_[0] + pr.H_[0]) / 2;
      ctx.fillStyle = hexA(COL.warn, 0.1); ctx.fillRect(pr.D_[0] + R, cy - R * 2.4, pr.H_[0] - pr.D_[0] - 2 * R, R * 4.8);
      ctx.strokeStyle = hexA(COL.info, 0.8 * g); ctx.lineWidth = 2; ctx.beginPath();          // the pair's wave leaking through the barrier, shrinking inside it
      const xa = Math.min(pr.D_[0], pr.H_[0]), xb = Math.max(pr.D_[0], pr.H_[0]), gap = Math.max(1, xb - xa - 2 * R);   // the wave comes in from the left nucleus
      for (let xx = xa - R * 3; xx <= xb + R * 3; xx += 2) { const inside = xx > xa + R && xx < xb - R, amp = inside ? R * 1.4 * Math.exp(-3 * (xx - xa - R) / gap) : xx <= xa + R ? R * 1.4 : R * 1.4 * Math.exp(-3);
        const yy = cy - R * 4.6 + amp * Math.sin(xx * 0.25 - st * 9); xx === xa - R * 3 ? ctx.moveTo(xx, yy) : ctx.lineTo(xx, yy); }
      ctx.stroke(); txt('wave amplitude: large outside, small but not zero through the barrier', mx, cy - R * 6.6, COL.info, 11, 'center');
      txt('Coulomb barrier: classically forbidden', mx, cy - R * 2.6, COL.warn, 12, 'center');
      const P = Math.exp(-Math.sqrt(nu.gamow_keV / nu.gamow_peak_keV));
      banner('Encounter 3: head-on at the Gamow peak, stopped at the barrier', `Quantum tunnelling lets it through with P ≈ ${(P * 100).toFixed(1)} % per attempt (calculated); shown succeeding here (illustrative)`);
    } else banner('Encounter 3 of 3: a faster pair, head-on', sel);
    if (st >= T[4]) {                                       // contact
      const m = sm(T[4], T[5], st);
      glow(cx, cy, R * (3 + 9 * m), '#D8EAFF', 0.9 * m);
      txt('⁵Li*: a brief compound nucleus (illustrative)', cx, cy + R * 3.2, COL['ink-strong'], 12, 'center', 600);
    }
    txt(`turning point ${e.rmin.toFixed(1)} fm at ${nu.gamow_peak_keV.toFixed(0)} keV · contact ${nu.touch_fm.toFixed(1)} fm`, cx, c2h - (graphs ? c2h * 0.36 : 46), COL.info, 12, 'center');
  } else {                                                  // products: ⁴He and p fly apart; the frame follows them outward
    const k = Math.min(1, (st - T[5]) / (T[6] - T[5])), P = nu.products, ap = P.alpha, pp = P.p;
    const flash = 1 - sm(0, 0.12, k); if (flash > 0) glow(cx, cy, S * 0.25, '#D8EAFF', flash);
    const move = sm(0, 0.35, k), zoom = sm(0.3, 1, k);       // first the products leave the frame centre, then the frame widens
    const tReal = 1e-23 * Math.pow(10, 3 * zoom) * Math.max(0.05, move);
    const reach = Math.min(c2w * 0.42, c2w * 0.42);            // proton held near the frame edge once the zoom starts
    const dp = reach * move, da = dp * ap.v_c / pp.v_c, ang = -0.35;
    const frame_m = 2 * (pp.v_c * 2.998e8 * tReal) / 0.84;
    // background nuclei shrink away as the frame widens
    const F = Math.pow(10, 3 * zoom);                         // the frame widens a thousandfold: other nuclei of the plasma come into view
    for (let i = 0; i < 160; i++) { const a = Math.abs(Math.sin(i * 12.9898) * 43758.5453) % 1 * 6.2832, rr = S * 0.5 * Math.pow(1000, ((i * 0.618034) % 1)) / F; if (rr > S * 0.75 || rr < 8) continue;
      ctx.fillStyle = hexA(i % 2 ? COL['fn-DEUTERIUM'] : COL['fn-HELIUM3'], 0.7); ctx.beginPath(); ctx.arc(cx + rr * Math.cos(a) * c2w / S, cy + rr * Math.sin(a) * 0.8, Math.max(1.2, 3.5 - zoom * 2), 0, 7); ctx.fill(); }
    const ax_ = cx - da * Math.cos(ang), ay_ = cy - da * Math.sin(ang), px_ = cx + dp * Math.cos(ang), py_ = cy + dp * Math.sin(ang);
    ctx.strokeStyle = hexA(PC.p, 0.7); ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(px_, py_); ctx.stroke();
    ctx.strokeStyle = hexA(PC.a, 0.7); ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(ax_, ay_); ctx.stroke();
    const shrink = 1 - 0.55 * zoom;
    nucleus(ax_, ay_, 2, 2, R * 1.1 * shrink, '', PC.a);
    nucleus(px_, py_, 1, 0, R * 0.9 * shrink, '', PC.p);
    if (move > 0.15) {
    const kms = v => `${(Math.round(v * 299792.458 / 100) * 100).toLocaleString('en')} km/s`;
    txt(`⁴He  ${ap.MeV.toFixed(2)} MeV · ${kms(ap.v_c)}`, Math.max(ax_, 110), ay_ + R * 3.1, PC.a, narrow ? 11 : 13, 'center', 600);
    txt(`p  ${pp.MeV.toFixed(2)} MeV · ${kms(pp.v_c)}`, Math.min(px_, c2w - 130), py_ - R * 2.4, PC.p, narrow ? 11 : 13, 'center', 600);
    }
    if (move > 0.3) { arrow(px_, py_, px_ + 46 * Math.cos(ang), py_ + 46 * Math.sin(ang), PC.p, 2); arrow(ax_, ay_, ax_ - 12 * Math.cos(ang), ay_ - 12 * Math.sin(ang), PC.a, 2); }
    // energy split bar
    const bw = Math.min(420, c2w - 60), bx = cx - bw / 2, by = c2h - (graphs ? c2h * 0.36 : 70), fp = pp.MeV / nu.Q_MeV;
    ctx.fillStyle = hexA(PC.p, 0.85); ctx.fillRect(bx, by, bw * fp * sm(0.1, 0.4, k), 10);
    ctx.fillStyle = hexA(PC.a, 0.85); ctx.fillRect(bx + bw * fp, by, bw * (1 - fp) * sm(0.1, 0.4, k), 10);
    (narrow ? [`${nu.Q_MeV.toFixed(2)} MeV: ${pct(fp)} proton, ${pct(1 - fp)} ⁴He`, 'equal and opposite momentum: the proton is 4× faster'] : [`${nu.Q_MeV.toFixed(2)} MeV released: ${pct(fp)} to the proton, ${pct(1 - fp)} to the ⁴He; equal and opposite momentum, so the proton is 4× faster`])
      .forEach((l, i) => txt(l, cx, by + 26 + i * 14, COL.ink, narrow ? 11 : 12, 'center'));
    txt(`${(tReal * 1e21).toPrecision(2)} × 10⁻²¹ s after fusion · frame ≈ ${frame_m < 1e-12 ? `${(frame_m * 1e15).toFixed(0)} fm` : `${(frame_m * 1e12).toFixed(1)} pm`}`, cx, by - 12, COL.muted, 11, 'center');
    banner(k < 0.3 ? 'Fusion: ⁴He and a proton, no neutron' : k < 0.85 ? 'Following the products outward' : 'Into the crowd: the products meet the plasma (stage 5)', 'Both are charged: a magnetic field can steer them. That is what the nozzle is for (stage 7).', COL.good);
  }
  if (!narrow) chipC(14, c2h - 14, 'ILLUSTRATIVE motion · CALCULATED numbers', COL.warn);
  if (graphs) nucleusGraphs();
}
function nucleusGraphs() {
  const nu = D.nuclear, x0 = 24, w = Math.min(320, c2w * 0.42), h = Math.min(130, c2h * 0.22), y0 = c2h - h - 34;
  ctx.fillStyle = 'rgba(5,7,11,0.85)'; ctx.fillRect(0, y0 - 28, c2w, c2h - y0 + 28);
  axes(x0, y0, w, h, 'Coulomb barrier and the energy of a typical pair', 'distance →', 'energy');
  const rT = nu.touch_fm, Vb = nu.barrier_MeV, Ep = nu.gamow_peak_keV / 1e3, rmax = 40;
  const X_ = r => x0 + r / rmax * w, Y_ = v => y0 + h - Math.min(v / (Vb * 1.15), 1) * h;
  ctx.strokeStyle = COL.warn; ctx.lineWidth = 2; ctx.beginPath();
  for (let r = 0.2; r <= rmax; r += 0.2) { const v = r < rT ? -0.3 : Vb * rT / r; const yy = r < rT ? y0 + h : Y_(v); r === 0.2 ? ctx.moveTo(X_(r), yy) : ctx.lineTo(X_(r), yy); }
  ctx.stroke();
  ctx.strokeStyle = COL.info; ctx.setLineDash([5, 4]); ctx.beginPath(); ctx.moveTo(X_(Vb * rT / Ep), Y_(Ep)); ctx.lineTo(x0 + w, Y_(Ep)); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = 'rgba(143,193,240,0.18)'; ctx.fillRect(X_(rT), Y_(Ep) - 3, X_(Vb * rT / Ep) - X_(rT), 6);
  txt(`barrier ${Vb.toFixed(2)} MeV`, X_(rT) + 6, Y_(Vb) + 12, COL.warn, 11);
  txt(`pair at ${nu.gamow_peak_keV.toFixed(0)} keV: tunnels with P ≈ ${E(Math.exp(-Math.sqrt(nu.gamow_keV / nu.gamow_peak_keV)))}`, x0 + w, Y_(Ep) - 6, COL.info, 11, 'right');
  const x1 = c2w - Math.min(300, c2w * 0.4) - 24, w1 = Math.min(300, c2w * 0.4);
  axes(x1, y0, w1, h, 'Where reactions happen in a 100 keV plasma', 'pair energy, keV →', '');
  ctx.strokeStyle = COL.good; ctx.lineWidth = 2; ctx.beginPath();
  nu.gamow_window.forEach(([e, p], i) => { const xx = x1 + e / 600 * w1, yy = y0 + h - p * h * 0.95; i ? ctx.lineTo(xx, yy) : ctx.moveTo(xx, yy); }); ctx.stroke();
  txt('few pairs are fast × fast pairs tunnel more', x1 + w1, y0 + 14, COL.good, 11, 'right');
  txt(`peak ${nu.gamow_peak_keV.toFixed(0)} keV`, x1 + nu.gamow_peak_keV / 600 * w1, y0 + h + 16, COL.good, 11, 'center');
}

// ---- 5 · many reactions: a moving, repelling crowd; fusions at a display rate that follows the calculated reactivity ----------------------
// Box units: x in [0, 1], y in [0, ar]. Ions repel with a softened 1/r² force so near misses are real (ILLUSTRATIVE strength); electrons
// drift and radiate. Each due fusion takes the closest D–³He pair at that moment, so the display over-represents fusion per encounter.
const PLX = { T: 100, ions: null, el: null, prods: [], phot: [], rings: [], acc: 0, accP: 0, nPass: 0, nFuse: 0, near: new Map(), ar: 0.6, Tset: 0 };
const PC = {};                              // particle colours: nuclei keep their fuel colours; products, electrons and X-rays are kept apart
function pcol() { Object.assign(PC, { D: COL['fn-DEUTERIUM'], H: COL['fn-HELIUM3'], e: '#6E7B8C', p: '#FF8A4C', a: '#F2F2F2', x: COL.warn, n: COL.neutron }); }
function sigv(T) {                          // Bosch–Hale ⟨σv⟩ for D–³He, log-interpolated from the study's table (m³/s)
  const R = D.plasma.reactivity; if (T <= R[0][0]) return R[0][1]; if (T >= R[R.length - 1][0]) return R[R.length - 1][1];
  const i = R.findIndex(r => r[0] >= T), a = R[i - 1], b = R[i], f = Math.log(T / a[0]) / Math.log(b[0] / a[0]);
  return Math.exp(Math.log(a[1]) + f * Math.log(b[1] / a[1]));
}
function plasmaState() {                     // the conditions the crowd shows: the stage's temperature, or the Experiment levers
  const ex = view === 'exp', T = ex ? lab.Ti : PLX.T, d = ex ? lab.d : 0.5, pol = ex ? lab.pol : 'none';
  const ax = D.lab.fuel.axes.Ti, Tn = ax.reduce((a, b) => Math.abs(b - T) < Math.abs(a - T) ? b : a);
  const fp = fuelPoint(pol, ex ? lab.mode : 'thermal', Tn, d) || fuelPoint('none', 'thermal', 100, 0.5);
  const polF = D.lab.fuel.axes.pol[pol]?.dhe3 || 1;
  const rel = sigv(T) / sigv(100) * (4 * d * (1 - d)) * polF;   // relative to 100 keV, 1:1, unpolarised
  return { T, d, pol, rel, photon: fp.photon, neutron: fp.neutron, rate: Math.min(14, 1.2 * rel) };
}
const rnd = (() => { let s = 7; return () => (s = (s * 16807) % 2147483647) / 2147483647; })();   // repeatable crowd
function thermalV(k, T) { const v = 0.07 * Math.sqrt(T / 100) * (k === 'D' ? 1.22 : 1) * (0.5 + rnd()), a = rnd() * 6.2832; return [v * Math.cos(a), v * Math.sin(a)]; }
function seedCrowd(ps) {
  const n = touch ? 70 : 130, ar = PLX.ar;
  PLX.ions = Array.from({ length: n }, (_, i) => { const k = rnd() < ps.d ? 'D' : 'H', [vx, vy] = thermalV(k, ps.T); return { x: rnd(), y: rnd() * ar, vx, vy, k, hot: 0, tr: [] }; });
  PLX.el = Array.from({ length: touch ? 60 : 110 }, () => { const a = rnd() * 6.2832, v = 0.22 * Math.sqrt(ps.T / 100); return { x: rnd(), y: rnd() * ar, vx: v * Math.cos(a), vy: v * Math.sin(a), hot: 0 }; });
  PLX.prods = []; PLX.phot = []; PLX.rings = []; PLX.nPass = 0; PLX.nFuse = 0; PLX.near.clear(); PLX.Tset = ps.T;
}
function stepCrowd(ps, dt) {
  const I = PLX.ions, ar = PLX.ar, K = 2.4e-5, rc = 0.09, soft = 3e-5, pass = 0.024;
  if (PLX.Tset !== ps.T) {                    // a new temperature rescales the thermal speeds, keeping each particle's direction
    const f = Math.sqrt(ps.T / PLX.Tset); I.forEach(p => { p.vx *= f; p.vy *= f; }); PLX.el.forEach(p => { p.vx *= f; p.vy *= f; }); PLX.Tset = ps.T;
  }
  const sub = Math.max(1, Math.ceil(dt / 0.02)), h = dt / sub;
  for (let s = 0; s < sub; s++) {
    for (let i = 0; i < I.length; i++) for (let j = i + 1; j < I.length; j++) {
      const a = I[i], b = I[j], dx = b.x - a.x, dy = b.y - a.y; if (Math.abs(dx) > rc || Math.abs(dy) > rc) continue;
      const r2 = dx * dx + dy * dy; if (r2 > rc * rc) continue;
      const q = (a.k === 'H' ? 2 : 1) * (b.k === 'H' ? 2 : 1), f = K * q / (r2 + soft) / Math.sqrt(r2 + 1e-9);
      const ma = a.k === 'H' ? 3 : 2, mb = b.k === 'H' ? 3 : 2;
      a.vx -= f * dx / ma * h; a.vy -= f * dy / ma * h; b.vx += f * dx / mb * h; b.vy += f * dy / mb * h;
      const key = i * 1000 + j;
      if (r2 < pass * pass) { if (!PLX.near.has(key)) { PLX.near.set(key, 1); PLX.nPass++; PLX.rings.push({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, age: 0 }); } }
      else if (r2 > 4 * pass * pass) PLX.near.delete(key);
    }
    const mv = (p, cool) => { p.x += p.vx * h; p.y += p.vy * h;
      if (p.x < 0 || p.x > 1) { p.vx = -p.vx * cool; p.x = Math.min(1, Math.max(0, p.x)); } if (p.y < 0 || p.y > ar) { p.vy = -p.vy * cool; p.y = Math.min(ar, Math.max(0, p.y)); } };
    I.forEach(p => mv(p, 1)); PLX.el.forEach(p => mv(p, 1));
  }
  // heated ions relax back toward the plasma temperature (the energy is shared on): illustrative relaxation
  const vt = 0.07 * Math.sqrt(ps.T / 100) * 1.1;
  I.forEach(p => { const v = Math.hypot(p.vx, p.vy); if (v > 1.6 * vt) { const f = Math.exp(-dt * 0.8); p.vx *= f; p.vy *= f; } p.hot = Math.max(0, p.hot - dt * 0.6);
    p.tr.push(p.x, p.y); if (p.tr.length > 16) p.tr.splice(0, 2); });
}
function fuse(ps) {                          // the closest D–³He pair fuses: products leave back to back, the pair is replaced by fresh fuel
  const I = PLX.ions; let best = null, bd = 1e9;
  for (let i = 0; i < I.length; i++) for (let j = i + 1; j < I.length; j++) {
    if (I[i].k === I[j].k) continue; const d = (I[i].x - I[j].x) ** 2 + (I[i].y - I[j].y) ** 2; if (d < bd) { bd = d; best = [I[i], I[j]]; }
  }
  if (!best) return;
  const [a, b] = best, x = (a.x + b.x) / 2, y = (a.y + b.y) / 2, ang = rnd() * 6.2832;
  PLX.prods.push({ x, y, a: ang, v: 0.62, E: 1, k: 'p', tr: [x, y], age: 0 }, { x, y, a: ang + Math.PI, v: 0.157, E: 1, k: 'a', tr: [x, y], age: 0 });   // speed ratio 3.95 (calculated)
  PLX.rings.push({ x, y, age: 0, fuse: true }); PLX.nFuse++;
  [a, b].forEach(p => { p.x = rnd() < 0.5 ? 0 : 1; p.y = rnd() * PLX.ar; [p.vx, p.vy] = thermalV(p.k, ps.T); if (p.x === 1) p.vx = -Math.abs(p.vx); else p.vx = Math.abs(p.vx); p.tr = []; });
}
function drawMany() {
  const st = u * DUR.many, narrow = c2w < 600, ps = plasmaState();
  ctx.fillStyle = '#05070B'; ctx.fillRect(0, 0, c2w, c2h);
  const bx = 16, by = narrow ? 116 : 96, bw = c2w - 32 - (c2w >= 700 ? 84 : 0), bh = Math.max(120, graphs ? c2h * 0.46 : c2h - by - (narrow ? 134 : 108));
  PLX.ar = bh / bw;
  if (!PLX.ions) seedCrowd(ps);
  const dt = sdt, S = bw;                    // box units to pixels
  if (dt > 0) stepCrowd(ps, dt);
  if (dt > 0) PLX.acc += ps.rate * dt * sm(0.04, 0.12, u);
  while (PLX.acc >= 1) { PLX.acc -= 1; fuse(ps); PLX.accP += ps.photon * 2; }
  if (dt > 0) PLX.accP += ps.photon * 1.2 * dt * Math.sqrt(ps.T / 100);       // bremsstrahlung goes on all the time, more where it is hot
  while (PLX.accP >= 1) { PLX.accP -= 1; const e = PLX.el[Math.floor(rnd() * PLX.el.length)]; PLX.phot.push({ x: e.x, y: e.y, a: rnd() * 6.2832, age: 0 }); }
  const X_ = x => bx + x * S, Y_ = y => by + y * S;
  ctx.save(); ctx.beginPath(); ctx.rect(bx, by, bw, bh); ctx.clip();
  // products: fast proton, slow ⁴He; they lose energy to the nuclei they pass and kick them (heating)
  PLX.prods = PLX.prods.filter(q => q.E > 0.12 && q.age < 6 && q.x > -0.05 && q.x < 1.05 && q.y > -0.05 && q.y < PLX.ar + 0.05);
  PLX.prods.forEach(q => {
    if (dt > 0) {
      const sp = q.v * Math.sqrt(q.E); q.x += Math.cos(q.a) * sp * dt; q.y += Math.sin(q.a) * sp * dt; q.age += dt; q.E *= Math.exp(-dt * 0.35);
      PLX.ions.forEach(p => { const dx = p.x - q.x, dy = p.y - q.y; if (dx * dx + dy * dy < 0.0004 && p.hot < 0.5) {
        const kick = 0.05 * q.E; p.vx += Math.cos(q.a) * kick; p.vy += Math.sin(q.a) * kick; p.hot = 1; q.E *= 0.78; } });
      PLX.el.forEach(p => { const dx = p.x - q.x, dy = p.y - q.y; if (dx * dx + dy * dy < 0.0003) p.hot = 1; });
      q.tr.push(q.x, q.y); if (q.tr.length > 60) q.tr.splice(0, 2);
    }
    const col = PC[q.k]; ctx.lineWidth = q.k === 'p' ? 2 : 3;
    for (let i = 2; i < q.tr.length; i += 2) { ctx.strokeStyle = hexA(col, 0.85 * i / q.tr.length * Math.min(1, q.E * 1.5)); ctx.beginPath(); ctx.moveTo(X_(q.tr[i - 2]), Y_(q.tr[i - 1])); ctx.lineTo(X_(q.tr[i]), Y_(q.tr[i + 1])); ctx.stroke(); }
    ctx.fillStyle = col; ctx.beginPath(); ctx.arc(X_(q.x), Y_(q.y), q.k === 'p' ? 3 : 4.2, 0, 7); ctx.fill();
  });
  // close passes (faint rings) and fusions (bright flash)
  PLX.rings = PLX.rings.filter(r => (r.age += dt) < (r.fuse ? 0.9 : 0.6));
  PLX.rings.forEach(r => { const k = r.age / (r.fuse ? 0.9 : 0.6);
    if (r.fuse) { glow(X_(r.x), Y_(r.y), 34 * (1 - k) + 8, '#FFFFFF', 0.95 * (1 - k)); }
    else { ctx.strokeStyle = hexA(COL.info, 0.45 * (1 - k)); ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(X_(r.x), Y_(r.y), 9 + 10 * k, 0, 7); ctx.stroke(); } });
  // electrons: small, fast, dim; brighter for a moment when a product passes
  PLX.el.forEach(p => { p.hot = Math.max(0, p.hot - dt); ctx.fillStyle = p.hot > 0 ? PC.a : PC.e; ctx.fillRect(X_(p.x) - 1, Y_(p.y) - 1, 2, 2); });
  // nuclei with short trails so the motion and the deflections read in a still frame
  PLX.ions.forEach(p => {
    const col = p.k === 'D' ? PC.D : PC.H; ctx.strokeStyle = hexA(col, 0.28); ctx.lineWidth = 1.2; ctx.beginPath();
    for (let i = 0; i < p.tr.length; i += 2) i ? ctx.lineTo(X_(p.tr[i]), Y_(p.tr[i + 1])) : ctx.moveTo(X_(p.tr[i]), Y_(p.tr[i + 1])); ctx.stroke();
    if (p.hot > 0.05) glow(X_(p.x), Y_(p.y), 12, PC.p, 0.55 * p.hot);
    ctx.fillStyle = col; ctx.beginPath(); ctx.arc(X_(p.x), Y_(p.y), p.k === 'H' ? 4 : 3.2, 0, 7); ctx.fill();
  });
  ctx.restore();
  PLX.phot = PLX.phot.filter(q => q.age < 1.2);
  PLX.phot.forEach(q => { q.age += dt; const r = q.age * bw * 0.6; squiggle(X_(q.x) + r * Math.cos(q.a), Y_(q.y) + r * Math.sin(q.a), q.a, 24, PC.x, 0.9 * (1 - q.age / 1.2), q.age * 30); });
  ctx.strokeStyle = COL['line-strong']; ctx.lineWidth = 1; ctx.strokeRect(bx, by, bw, bh);
  // counters: what the display shows against what a real plasma does
  const enc = D.accounting.encounter;
  const c1 = `shown: ${PLX.nPass} close passes, ${PLX.nFuse} fusions`, c2 = `real, at 100 keV: 1 hard encounter in ${Math.round(1 / enc.per_close_90)} fuses; about ${(Math.round(1 / enc.per_deflection / 1000) * 1000).toLocaleString('en')} deflections per fusion`;
  const C2 = narrow ? wrap(c2, Math.floor((bw - 24) / 5.6)) : [c2];
  ctx.fillStyle = 'rgba(5,7,11,0.8)'; ctx.fillRect(bx + 6, by + 6, narrow ? bw - 12 : 430, 22 + C2.length * 14);
  txt(c1, bx + 14, by + 20, COL['ink-strong'], 12, 'left', 600); C2.forEach((l, i) => txt(l, bx + 14, by + 35 + i * 13, COL.muted, narrow ? 10 : 11));
  // legend and the documented display scaling
  const ly = by + bh + 18; let lx = bx, row = 0;
  [['D', PC.D], ['³He', PC.H], ['electron', PC.e], ['proton (product)', PC.p], ['⁴He (product)', PC.a], ['X-ray ∿', PC.x], ['close pass ○', COL.info]].forEach(([l, c]) => {
    ctx.font = '11px system-ui'; const wl = ctx.measureText(l).width + 30; if (lx + wl > bx + bw) { lx = bx; row++; }
    ctx.fillStyle = c; ctx.beginPath(); ctx.arc(lx + 4, ly - 4 + row * 16, 3.5, 0, 7); ctx.fill(); txt(l, lx + 12, ly + row * 16, COL.ink, 11); lx += wl;
  });
  (narrow ? [`${ps.T.toFixed(0)} keV · fusions drawn at ${ps.rate.toFixed(1)}/s ∝ ⟨σv⟩ (display scaling)`] : wrap(`${ps.T.toFixed(0)} keV · ⟨σv⟩ ${sci(sigv(ps.T))} m³/s (calculated) · fusions drawn at ${ps.rate.toFixed(1)}/s = 1.2/s × ⟨σv⟩ ratio × fuel mix${ps.pol !== 'none' ? ' × polarisation' : ''} (display scaling)`, Math.floor(bw / 6.2)))
    .forEach((l, i) => txt(l, bx, ly + (row + 1) * 16 + 2 + i * 14, COL.muted, narrow ? 10 : 11));
  const k = sm(0, 0.08, u); if (k < 1) zoomRings(k, false, ['two nuclei · 10 fm', 'plasma · 1 µm'], 'a jump in scale, not a continuous zoom');
  banner('Many reactions: a burning plasma', 'Nuclei repel and swerve; only rarely does a pair fuse. Its products heat what they pass.');
  if (graphs) manyGraph(bx, by + bh + 34);
}
function manyGraph(bx, y0) {
  const x0 = bx + 10, w = Math.min(360, c2w * 0.5), h = c2h - y0 - 40;
  if (h < 50) return;
  ctx.fillStyle = 'rgba(5,7,11,0.85)'; ctx.fillRect(0, y0 - 22, c2w, c2h - y0 + 22);
  axes(x0, y0, w, h, 'Reactivity ⟨σv⟩ against temperature (Bosch–Hale)', 'T, keV (log) →', 'log');
  const R = D.plasma.reactivity, lo = 1e-27, hi = 2e-21;
  const Y_ = v => y0 + h - (Math.log10(Math.max(v, lo)) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo)) * h;
  [['DHe3', 1, COL.good, 'D–³He'], ['DDn', 2, COL.neutron, 'D–D (n branch)'], ['DT', 4, COL.bad, 'D–T (for scale)']].forEach(([k, i, col, lab_], j) => {
    ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.beginPath(); R.forEach((r, m) => { const xx = logx(r[0], R[0][0], R[R.length - 1][0], x0, w); m ? ctx.lineTo(xx, Y_(r[i])) : ctx.moveTo(xx, Y_(r[i])); }); ctx.stroke();
    txt(lab_, x0 + w + 8, y0 + 14 + j * 16, col, 11);
  });
  const T = plasmaState().T, xx = logx(T, R[0][0], R[R.length - 1][0], x0, w); ctx.strokeStyle = COL.ink; ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.moveTo(xx, y0); ctx.lineTo(xx, y0 + h); ctx.stroke(); ctx.setLineDash([]);
  txt(`${T.toFixed(0)} keV`, xx + 4, y0 + h - 4, COL.ink, 11);
}

// ---- 6 · ignition: one pulsed target, from arrival to burn to disassembly -------------------------------------------------------------------
// The plasma is drawn as its nuclei (not a disc): their spacing follows the model's radius (density ∝ 1/R³), their colour its ion
// temperature, and burned pairs turn into ash. Fusion flashes, product tracks, X-rays and neutrons follow the model's release rate,
// bremsstrahlung (∝ n²√Te) and shares (scaled). The burn clock runs non-linearly so the first picosecond can be seen; it is shown as is.
const IGN = { pts: null, fl: [], ph: [], nn: [], acc: 0, accP: 0, accN: 0 };
function tcol(T) {                         // ion temperature colour: red (cool) to orange, yellow and white (hottest)
  const k = Math.min(1, Math.max(0, Math.log10(Math.max(T, 1)) / Math.log10(650)));
  const stops = [[0, [120, 30, 30]], [0.55, [255, 120, 60]], [0.78, [255, 200, 110]], [1, [250, 248, 255]]];
  let i = 0; while (i < stops.length - 2 && k > stops[i + 1][0]) i++;
  const [a, ca] = stops[i], [b, cb] = stops[i + 1], f = (k - a) / (b - a);
  return '#' + ca.map((c, j) => Math.round(c + f * (cb[j] - c)).toString(16).padStart(2, '0')).join('');
}
function burnCase() {
  const b = D.plasma.burn, rr = view === 'exp' ? lab.rhoR : b.rhoR_design, ti = view === 'exp' ? lab.Ti0 : b.Ti_design;
  return { rr, ti, g: b.grid[`${rr}|${ti}`] };
}
function burnAt(H, tt) {                    // the model state at burn time tt (linear between history rows)
  let i = 0; while (i < H.length - 1 && H[i + 1][0] < tt) i++;
  const a = H[i], b = H[Math.min(H.length - 1, i + 1)], f = b[0] > a[0] ? Math.min(1, Math.max(0, (tt - a[0]) / (b[0] - a[0]))) : 0;
  const L = j => a[j] + f * (b[j] - a[j]);
  return { t: tt, Ti: L(1), Te: L(2), R: L(3), E: L(4), dE: (b[4] - a[4]) / Math.max(1e-30, b[0] - a[0]) };
}
function drawIgnition() {
  if (graphs) { ignitionGraphs(); return; }
  const st = u * DUR.ignition, narrow = c2w < 600, { rr, ti, g } = burnCase(), H = g.history, nu = D.nuclear, ac = D.accounting, b_rr = D.plasma.burn.rhoR_design, b_ti = D.plasma.burn.Ti_design;
  ctx.fillStyle = '#05070B'; ctx.fillRect(0, 0, c2w, c2h);
  const P = [0, 3, 4, 12, 14, DUR.ignition];               // arrive + compress (OPEN), assumed start, burn, disassembly, verdict
  const cx = narrow ? c2w / 2 : c2w * 0.34, cy = narrow ? c2h * 0.36 : c2h * 0.5, S = Math.min(narrow ? c2w * 0.78 : c2w * 0.62, c2h);
  const tmax = H[H.length - 1][0], R0 = g.R0_m, Rb = S * 0.17;             // R0 is drawn at Rb pixels; the scale bar says what that is
  const pxPerUm = Rb / (R0 * 1e6);
  const kb = st < P[2] ? 0 : Math.min(1, (st - P[2]) / (P[3] - P[2])), tt = tmax * kb * kb;   // burn clock: quadratic, slow at the start
  const m = st >= P[2] ? burnAt(H, tt) : { t: 0, Ti: ti, Te: ti, R: R0, E: 0, dE: 0 };
  const ex = sm(P[3], P[4] + 1.5, st);                      // disassembly after the burn: the target is no longer confined
  const Rpx = Rb * m.R / R0;
  const n = touch ? 170 : 300;
  if (!IGN.pts) IGN.pts = Array.from({ length: n }, (_, i) => { const a = rnd() * 6.2832, r = Math.sqrt(rnd()) * 0.96, ash = rnd(); return { a, r, k: i % 2 ? 'D' : 'H', ash, ph: rnd() * 6.28, out: 0.6 + rnd() * 1.2 }; });
  // ---- before the model: the target arrives and must be crushed (OPEN) ----
  if (st < P[2]) {
    const arr = sm(0, 1.1, st), c = sm(1.1, P[1], st), x0 = cx - (1 - arr) * c2w * 0.5;
    const rad = Rb * (2.8 - 1.8 * c);
    ctx.setLineDash([5, 5]); ctx.strokeStyle = hexA(COL.bad, 0.7); ctx.lineWidth = 1.2; ctx.beginPath(); ctx.arc(x0, cy, rad, 0, 7); ctx.stroke(); ctx.setLineDash([]);
    IGN.pts.forEach(p => { ctx.fillStyle = hexA(PC[p.k], 0.85); ctx.beginPath(); ctx.arc(x0 + rad * p.r * Math.cos(p.a), cy + rad * p.r * Math.sin(p.a), 2.1, 0, 7); ctx.fill(); });
    if (st > 1.1 && st < P[1]) for (let k = 0; k < 8; k++) { const a = k * Math.PI / 4, r1 = rad + 60, r2 = rad + 12; ctx.setLineDash([5, 5]); arrow(x0 + r1 * Math.cos(a), cy + r1 * Math.sin(a), x0 + r2 * Math.cos(a), cy + r2 * Math.sin(a), hexA(COL.bad, 0.8), 2); ctx.setLineDash([]); }
    if (st >= P[1]) { glow(cx, cy, Rb * 1.4, tcol(ti), 0.35 * sm(P[1], P[2], st)); }
    chipC(x0 - 22, cy + rad + 30, 'OPEN', COL.bad);
    if (st < P[1]) banner(st < 1.1 ? 'A frozen D–³He target arrives at the burn point' : `It must be crushed to ${rr} g/cm² and heated to ${ti} keV`,
      'How: the driver and the implosion are not modelled anywhere in the project (OPEN). The crushing is drawn only as a question.', st < 1.1 ? COL['ink-strong'] : COL.bad);
    else banner(`Assumed start: ${rr} g/cm², ${ti} keV, radius ${(R0 * 1e6).toFixed(0)} µm`, 'The burn model (R2-B) begins here, from a compressed hot sphere it does not explain.');
    ignTimeline(st, P, H, tmax, narrow, kb); return;
  }
  // ---- the burn: heat, glow, fusions, product tracks, radiation ----
  const hotK = Math.min(1, m.Ti / 600), col = tcol(m.Ti);
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  glow(cx, cy, Rpx * (1.25 + 1.5 * ex), col, (0.12 + 0.5 * hotK) * (1 - ex * 0.85));
  ctx.restore();
  const lc = D.ledger.grid.cells[`${rr}|${ti}|${view === 'exp' ? lab.mix : 1}`], burned = Math.min(1, m.E / g.fusion_J) * lc.burn_fraction;   // share of the fuel mass burned so far
  const jig = 0.012 * Math.sqrt(m.Ti / 70);
  IGN.pts.forEach(p => {
    const rr_ = (p.r + jig * Math.sin(st * 9 + p.ph)) * Rpx * (1 + ex * p.out * 2.4);
    const x = cx + rr_ * Math.cos(p.a + jig * Math.cos(st * 7 + p.ph)), y = cy + rr_ * Math.sin(p.a);
    const ash = p.ash < burned, c_ = ash ? (p.k === 'D' ? PC.p : PC.a) : PC[p.k];
    ctx.globalAlpha = 0.9 * (1 - ex * 0.8); ctx.fillStyle = c_; ctx.beginPath(); ctx.arc(x, y, ash ? 1.7 : 2.2, 0, 7); ctx.fill();
  });
  ctx.globalAlpha = 1;
  ctx.strokeStyle = hexA(col, 0.6 * (1 - ex)); ctx.lineWidth = 1.2; ctx.beginPath(); ctx.arc(cx, cy, Rpx, 0, 7); ctx.stroke();
  // event rates from the model (display scaling): fusion ∝ dE/dt, X-rays ∝ n²√Te, neutrons ∝ fusion × neutron share
  if (st < P[3] + 0.3 && sdt > 0) {
    const meanRate = g.fusion_J / tmax, fr = Math.min(6, m.dE / meanRate) * (1 - ex);
    const dens = (R0 / m.R) ** 3, brem = dens * dens * Math.sqrt(Math.max(m.Te, 0.1) / ti);
    IGN.acc += fr * 7 * sdt; IGN.accP += Math.min(5, brem) * 7 * sdt * (1 - ex); IGN.accN += fr * 7 * g.neutron_share * 8 * sdt;
    while (IGN.acc >= 1) { IGN.acc--; const a = rnd() * 6.28, d = Rpx * Math.sqrt(rnd()) * 0.9; IGN.fl.push({ x: cx + d * Math.cos(a), y: cy + d * Math.sin(a), a: rnd() * 6.28, age: 0, L: Rpx * (0.12 + 0.1 * (m.R / R0 - 1)) }); }
    while (IGN.accP >= 1) { IGN.accP--; IGN.ph.push({ a: rnd() * 6.28, age: 0 }); }
    while (IGN.accN >= 1) { IGN.accN--; IGN.nn.push({ a: rnd() * 6.28, age: 0 }); }
  }
  IGN.fl = IGN.fl.filter(q => (q.age += sdt) < 0.6);
  IGN.fl.forEach(q => { const k = q.age / 0.6, L = q.L * Math.min(1, q.age * 5);   // products stop inside the fuel (ρR far above their range) and heat it
    glow(q.x, q.y, 10 * (1 - k) + 3, '#FFFFFF', 0.9 * (1 - k));
    ctx.lineWidth = 1.5; ctx.strokeStyle = hexA(PC.p, 0.9 * (1 - k)); ctx.beginPath(); ctx.moveTo(q.x, q.y); ctx.lineTo(q.x + L * Math.cos(q.a), q.y + L * Math.sin(q.a)); ctx.stroke();
    ctx.strokeStyle = hexA(PC.a, 0.9 * (1 - k)); ctx.beginPath(); ctx.moveTo(q.x, q.y); ctx.lineTo(q.x - L * 0.3 * Math.cos(q.a), q.y - L * 0.3 * Math.sin(q.a)); ctx.stroke();
    if (q.age > 0.2) glow(q.x + L * Math.cos(q.a), q.y + L * Math.sin(q.a), 7, PC.p, 0.5 * (1 - k)); });
  IGN.ph = IGN.ph.filter(q => (q.age += sdt) < 1.0);
  IGN.ph.forEach(q => { const d = Rpx * 0.9 + q.age * S * 0.55; squiggle(cx + d * Math.cos(q.a), cy + d * Math.sin(q.a), q.a, 20, PC.x, 0.9 * (1 - q.age), q.age * 40); });
  IGN.nn = IGN.nn.filter(q => (q.age += sdt) < 1.2);
  IGN.nn.forEach(q => { const d = Rpx + q.age * S * 0.45; ctx.fillStyle = hexA(PC.n, 0.95 * (1 - q.age / 1.2)); ctx.beginPath(); ctx.arc(cx + d * Math.cos(q.a), cy + d * Math.sin(q.a), 2.6, 0, 7); ctx.fill(); });
  // scale bar: how big the drawn target really is
  const bar = 20 * pxPerUm, sbx = cx - bar / 2, sby = cy + Rb * (narrow ? 1.95 : 2.05);
  ctx.strokeStyle = COL.muted; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(sbx, sby); ctx.lineTo(sbx + bar, sby); ctx.moveTo(sbx, sby - 4); ctx.lineTo(sbx, sby + 4); ctx.moveTo(sbx + bar, sby - 4); ctx.lineTo(sbx + bar, sby + 4); ctx.stroke();
  txt('20 µm', cx, sby + 15, COL.muted, 11, 'center');
  // readout: the model state now, and where the released energy has gone (shares of the fusion energy, R2-B)
  const bu = ac.burn, Ef = Math.min(1, m.E / g.fusion_J);
  const px0 = narrow ? 18 : c2w * 0.6, pw = narrow ? c2w - 36 : Math.min(300, c2w - px0 - (c2w >= 700 ? 104 : 24)), py0 = narrow ? cy + Rb * 1.95 + 30 : c2h * 0.24;
  const lines = [[`ion temperature ${m.Ti.toFixed(0)} keV`, col, 13, 600], [`density ${((R0 / m.R) ** 3).toFixed(2)} × start · radius ${(m.R * 1e6).toFixed(0)} µm`, COL.ink, 11, 400],
    [`t = ${(m.t * 1e12).toFixed(2)} of ${(tmax * 1e12).toFixed(1)} ps · ${pct(burned)} of the fuel burned`, COL.muted, 11, 400]];
  (narrow ? lines.slice(0, 2) : lines).forEach(([l, c, f, w], i) => txt(l, px0, py0 + i * 17, c, narrow ? Math.min(f, 12) : f, 'left', w));
  // the time-resolved ledger of the design burn (ledger.py history): where the energy is at this moment, as shares of the final fusion energy
  const LH = D.ledger.design.history, isDesign = rr === b_rr && ti === b_ti && (view !== 'exp' || lab.mix === 1);
  let lx, ln, lp;
  if (isDesign) { let i = 0; while (i < LH.length - 1 && LH[i + 1][0] < m.t) i++; const a = LH[i], c = LH[Math.min(LH.length - 1, i + 1)], f = c[0] > a[0] ? Math.min(1, Math.max(0, (m.t - a[0]) / (c[0] - a[0]))) : 0, I = j => a[j] + f * (c[j] - a[j]);
    const Ff = D.ledger.design.energy.fusion_J; lx = I(13) / Ff; ln = I(14) / Ff; lp = (I(15) + I(16) + I(17)) / Ff; }
  else { lx = Ef * g.photon_share; ln = Ef * g.neutron_share; lp = Ef * Math.max(0, 1 + g.heat_J / g.fusion_J - g.photon_share - g.neutron_share); }
  const rows = [['Fusion energy released', Ef, COL.good, `${(m.E / 1e9).toFixed(2)} GJ`],
    ['Escaped as X-rays', lx, PC.x, pct(lx)],
    ['Carried off by neutrons', ln, PC.n, pct(ln)],
    ['In the plasma now', lp, PC.p, pct(lp)]];
  rows.forEach(([l, f, c, v], j) => {
    const y = py0 + (narrow ? 44 : 64) + j * (narrow ? 22 : 34); txt(l, px0, y, COL.ink, 11); txt(v, px0 + pw, y, c, 11, 'right', 600);
    ctx.fillStyle = 'rgba(255,255,255,0.07)'; ctx.fillRect(px0, y + 5, pw, 5); ctx.fillStyle = c; ctx.fillRect(px0, y + 5, pw * Math.min(1, f), 5);
  });
  if (!narrow) { const L = [...wrap('Charged products stop inside the dense fuel and heat it; the hot electrons radiate.', Math.floor(pw / 5.9)),
      ...wrap('A pulsed target, not a steady (tokamak-like) plasma: nothing confines it, so it must burn before it flies apart.', Math.floor(pw / 5.9))];
    L.forEach((l, i) => txt(l, px0, py0 + 64 + 4 * 34 + 2 + i * 15, COL.muted, 11));
    chipC(px0, py0 + 64 + 4 * 34 + 22 + L.length * 15, 'ILLUSTRATIVE motion', COL.warn); chipC(px0 + 128, py0 + 64 + 4 * 34 + 22 + L.length * 15, 'compression OPEN', COL.bad); }
  // captions by phase, and the verdict by view
  const pk = H.reduce((a, h) => h[1] > a[1] ? h : a, H[0])[0];
  if (st < P[3]) banner(m.t < pk * 0.6 ? 'Fusions begin: their products heat the fuel' : m.t < pk * 1.6 ? `The burn runs away: ${m.Ti.toFixed(0)} keV, hotter fuel fuses faster` : m.Ti > 40 ? 'X-rays carry the heat away as the target expands' : 'Cooling: the burn quenches',
    narrow ? '' : `D + ³He → ⁴He + p, ${nu.Q_MeV.toFixed(1)} MeV each. Flashes, X-rays and neutrons are drawn at rates that follow the model (scaled).`);
  else if (st < P[4]) banner(`The target flies apart after ${(tmax * 1e12).toFixed(0)} ps: no confinement holds it`, `${(g.fusion_J / 1e9).toFixed(2)} GJ released, gain ${g.gain.toFixed(1)} over the heat put in; the burn cannot continue.`, COL.good);
  else {
    const md = D.modeled, pz = ac.states.find(s => s.id === 'pulse'), nd = ac.states.find(s => s.id === 'need');
    if (view === 'model') { const r = LEDc || LED(); banner('Modeled: the engine cannot keep this up', `${pct(r.plasma_J / r.fusion_J)} of the fusion energy is left to steer; drivers need at least ${W(r.driver_elec_W)} per engine (pulse bank ${TS(D.startup.steps[0].value.bank_J / r.driver_elec_W)}); engine heat ${X(r.heat_over)} the radiators.`, COL.bad); }
    else if (view === 'exp') banner(`Your target: ${rr} g/cm², ${ti} keV`, `Gain ${g.gain.toFixed(1)}, ${pct(g.burn_fraction)} burned, X-rays ${pct(g.photon_share)}. Change it in the Experiment stage.`, COL.info);
    else banner(`Intended: a new target every ${(1e6 / pz.Hz).toFixed(0)} µs, ${Math.round(pz.Hz).toLocaleString('en')} a second`,
      `Design point ${W(pz.per_engine_W)} per engine; the mission needs ${W(nd.per_engine_W)}, ${ac.gap.power_ratio.toFixed(1)}× more (Fuel stage: accounting).`, COL.warn);
  }
  const zk = sm(DUR.ignition - 1.4, DUR.ignition, st); if (zk > 0) zoomRings(zk, false, ['target · 100 µm', 'burn point · 1 m', 'engine · 10 m'], 'to the magnetic nozzle (stage 7)');
  ignTimeline(st, P, H, tmax, narrow, kb);
}
function ignTimeline(st, P, H, tmax, narrow, kb) {          // where we are: assumed compression, the modelled burn (its Ti curve), disassembly
  const x0 = 16, w = c2w - 32 - (narrow ? 0 : 84), y0 = c2h - (narrow ? 40 : 46), h = 18, T = DUR.ignition, X_ = s => x0 + s / T * w;
  ctx.fillStyle = hexA(COL.bad, 0.14); ctx.fillRect(X_(0), y0, X_(P[2]) - X_(0), h);
  ctx.fillStyle = 'rgba(255,255,255,0.05)'; ctx.fillRect(X_(P[2]), y0, X_(T) - X_(P[2]), h);
  const Tm = Math.max(...H.map(r => r[1]));
  ctx.strokeStyle = COL.warn; ctx.lineWidth = 1.5; ctx.beginPath();
  for (let s = P[2]; s <= P[3]; s += 0.05) { const k = (s - P[2]) / (P[3] - P[2]), m = burnAt(H, tmax * k * k), yy = y0 + h - m.Ti / Tm * h; s === P[2] ? ctx.moveTo(X_(s), yy) : ctx.lineTo(X_(s), yy); }
  ctx.stroke();
  const lab_ = narrow ? ['crush: OPEN', 'burn (model)', 'apart'] : ['crush: OPEN', 'burn: R2-B model (Ti curve)', 'flies apart', 'verdict'];
  [[0, COL.bad], [P[2], COL.warn], [P[3], COL.muted], [P[4], COL.muted]].slice(0, lab_.length).forEach(([s, c], i) => txt(lab_[i], X_(s) + 4, y0 - 4, c, 10));
  ctx.fillStyle = COL['ink-strong']; ctx.fillRect(X_(st) - 1, y0 - 2, 2, h + 4);
}
function ignitionGraphs() {
  ctx.fillStyle = 'rgba(5,7,11,0.94)'; ctx.fillRect(0, 0, c2w, c2h);
  const { rr, ti, g } = burnCase();
  const narrow = c2w < 640, pw = narrow ? c2w - 60 : (c2w - 90) / 2, ph = narrow ? (c2h - 150) / 2 : c2h - 130;
  let x0 = 40, y0 = 50;
  axes(x0, y0, pw, ph, 'Steady plasma: n·τE needed to self-heat (1:1 D–³He)', 'T, keV (log) →', 'n·τE, m⁻³ s (log)');
  const L = D.plasma.lawson, hi = 1e22;
  const Y_ = v => y0 + ph - (Math.log10(v) - 20) / 2 * ph;
  [['thermal', COL.warn, 'thermal (Te = Ti)'], ['hot_ion', COL.info, 'hot-ion (Te = Ti / 2), model-based']].forEach(([k, col, lb], j) => {
    ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.beginPath(); let started = false;
    L[k].forEach(([T, nt]) => { if (!nt || nt > hi) { started = false; return; } const xx = logx(T, 20, 500, x0, pw); started ? ctx.lineTo(xx, Y_(nt)) : ctx.moveTo(xx, Y_(nt)); started = true; }); ctx.stroke();
    txt(lb, x0 + pw, y0 + 14 + j * 15, col, 11, 'right');
  });
  const dt = D.plasma.dt_ref; ctx.strokeStyle = COL.muted; ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.moveTo(x0, Y_(dt.n_tau_min)); ctx.lineTo(x0 + pw, Y_(dt.n_tau_min)); ctx.stroke(); ctx.setLineDash([]);
  txt('D–T ignition, for scale', x0 + 6, Y_(dt.n_tau_min) - 5, COL.muted, 11);
  const xx = logx(35, 20, 500, x0, pw); ctx.fillStyle = 'rgba(255,127,115,0.12)'; ctx.fillRect(x0, y0, xx - x0, ph);
  txt('X-rays win:', x0 + 4, y0 + ph - 22, COL.bad, 11); txt('no ignition', x0 + 4, y0 + ph - 8, COL.bad, 11);
  x0 = narrow ? 40 : 60 + pw; y0 = narrow ? 50 + ph + 60 : 50;
  const LG = D.ledger.design, LH = LG.history, E0 = LG.energy.heat_in_J + LG.energy.fusion_J, tL = LH[LH.length - 1][0];
  axes(x0, y0, pw, ph, `Where the energy is during the design burn (${LG.case.rhoR_g_cm2} g/cm², ${LG.case.Ti_keV} keV)`, 'time →', 'share of heat in + fusion');
  const bands = [[16, 'in the ions', PC.D], [17, 'in the electrons', PC.e], [15, 'expansion (kinetic)', PC.p], [13, 'escaped as X-rays', PC.x], [14, 'neutrons', PC.n]];
  const cum = LH.map(() => 0);
  bands.forEach(([j, lb, col], bi) => {
    const lo = cum.slice(); LH.forEach((h, i) => { cum[i] += h[j] / E0; });
    ctx.fillStyle = hexA(col, 0.75); ctx.beginPath();
    LH.forEach((h, i) => { const X1 = x0 + h[0] / tL * pw, Y1 = y0 + ph - cum[i] * ph; i ? ctx.lineTo(X1, Y1) : ctx.moveTo(X1, Y1); });
    for (let i = LH.length - 1; i >= 0; i--) ctx.lineTo(x0 + LH[i][0] / tL * pw, y0 + ph - lo[i] * ph);
    ctx.closePath(); ctx.fill();
    ctx.strokeStyle = 'rgba(5,7,11,0.9)'; ctx.lineWidth = 1; ctx.stroke();
    const yl = y0 + ph - (lo[lo.length - 1] + cum[cum.length - 1]) / 2 * ph;
    if (cum[cum.length - 1] - lo[lo.length - 1] > 0.025) txt(`${lb} ${pct(cum[cum.length - 1] - lo[lo.length - 1])}`, x0 + pw - 4, yl + 4, COL['ink-strong'], 11, 'right', 600);
  });
  const fz = LH.map(h => (LG.energy.heat_in_J + h[12]) / E0);
  ctx.strokeStyle = COL.good; ctx.lineWidth = 2; ctx.setLineDash([5, 4]); ctx.beginPath(); LH.forEach((h, i) => { const X1 = x0 + h[0] / tL * pw, Y1 = y0 + ph - fz[i] * ph; i ? ctx.lineTo(X1, Y1) : ctx.moveTo(X1, Y1); }); ctx.stroke(); ctx.setLineDash([]);
  txt('dashed: heat in + fusion released so far', x0 + 6, y0 + 14, COL.good, 11);
  txt(`0 to ${(tL * 1e12).toPrecision(2)} ps · residual ${pct(Math.abs(LG.energy.residual_share))} (bookkeeping)`, x0, y0 + ph + 16, COL.muted, 11, 'left');
  txt('Engineering view: the two ignition ideas side by side. The Vertex uses the pulsed target on the right; its compression is OPEN.', c2w / 2, c2h - 14, COL.ink, 12, 'center', 600);
}

function draw2d() {
  if (!PC.D) pcol();
  if (!ctx) sizeC2(); if (!TWO_D.has(STAGES[si]) || !D) { if (ctx) ctx.clearRect(0, 0, c2w, c2h); return; }
  const id = STAGES[si];
  if (id === 'nucleus') drawNucleus(); else if (id === 'many') drawMany(); else drawIgnition();
}

// ---- heat and cooling (lab/studies/vertex-compact-engine/vertex-thermal via the study, IMPORTED): supermirror strategies, blankets, cooling circuits, energy flow, inspector ----
// The WORK hardware of the thermal study is drawn from its parametric primitives in the engine frame, merged per layer and instanced on the four
// engines (six draw calls). It is research hardware, not canon, and drawing it does not solve anything: every card names its open problems.
const TH_MESH = { mirror_A: 'A', mirror_B: 'blades', mirror_D: 'D', blanket_C: 'C', blanket_thin: 'Ct', blades: 'blades', hot: 'hot', warm: 'warm', cryo: 'cryo', cryo_quench: 'cryo', service: 'service' };
const TH_COL = { mirror_A: '#D6D0F4', sub: '#7A7490', mirror_D: '#F2D27A', support: '#9A8A60', blades: '#73B3FA', edge: '#F4F6FA', root: '#55687E', hot: '#FF7A2E', hotbox: '#B8703A',
  warm: '#FFC04D', cryo: '#4FB0FF', screen: '#D9844D', cryo_quench: '#F2D84A', service: '#B8BEC6',
  'CFC sacrificial face': '#2A2A2E', 'W/CFC heat sink with lithium channels': '#8A5A3C', 'W/B4C shield': '#6A6154', 'LiH moderator': '#E9E7DF',
  'Vacuum gap and polished screen': '#B9C0C9', '80 K screen (Cu, cooled)': '#D9844D', 'MLI': '#E6C050' };
const TH_MARK = [[], ['ENG-040', 'ENG-053'], ['ENG-057', 'ENG-058'], ['ENG-043'], ['ENG-046', 'ENG-060'], ['ENG-048']];   // problem markers per Heat step, so each view shows only its own
const TH_FLOW = { hot: ['#FFB070', 0.22], warm: ['#FFE08A', 0.16], cryo: ['#9AD4FF', 0.12] };
let thGroup = null, thMeshes = {}, thFlow = [], inspId = null, inspPrim = null, srcSel = 'L0', thArch = false;
function thKey(g) {
  if (g.layer === 'blanket_C' || g.layer === 'blanket_thin') return g.layer_name;
  if (g.layer === 'mirror_A') return /_SUB$/.test(g.comp) ? 'sub' : 'mirror_A';
  if (g.layer === 'mirror_D') return g.comp === 'SUPPORT' ? 'support' : 'mirror_D';
  if (g.layer === 'mirror_B' || g.layer === 'blades') return g.comp === 'EDGE' ? 'edge' : g.comp === 'ROOT' ? 'root' : 'blades';
  if (g.layer === 'hot' && g.kind === 'box') return 'hotbox';
  if (g.layer === 'cryo' && /screen/.test(g.note || '')) return 'screen';
  return g.layer;
}
function thPrim(g) {
  let geo;
  if (g.kind === 'torus') {
    const span = g.arc ? (g.arc[1] - g.arc[0]) * Math.PI / 180 : Math.PI * 2;
    geo = new THREE.TorusGeometry(g.R, g.a, 10, 72, span).rotateY(Math.PI / 2).rotateX(((g.arc ? g.arc[0] : 0) + 90) * Math.PI / 180).translate(g.x, 0, 0);
  } else if (g.kind === 'tube') {
    const path = new THREE.CurvePath(); for (let i = 1; i < g.points.length; i++) path.add(new THREE.LineCurve3(v3(g.points[i - 1]), v3(g.points[i])));
    geo = new THREE.TubeGeometry(path, 10 * g.points.length, g.radius, 6, false);
  } else if (g.kind === 'box') {
    const a = g.az * Math.PI / 180, m = new THREE.Matrix4().makeBasis(new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, Math.cos(a), Math.sin(a)), new THREE.Vector3(0, -Math.sin(a), Math.cos(a)));
    m.setPosition(v3(g.center)); geo = new THREE.BoxGeometry(...g.size).applyMatrix4(m);
  } else if (g.kind === 'revolve') {
    const pts = g.profile.map(([x, r]) => new THREE.Vector2(r, x)); if (g.closed) pts.push(pts[0].clone());
    const a0 = (g.arc ? g.arc[0] : 0) - 90, span = g.arc ? g.arc[1] - g.arc[0] : 360;
    geo = new THREE.LatheGeometry(pts, 72, a0 * Math.PI / 180, span * Math.PI / 180).rotateZ(-Math.PI / 2);
  } else if (g.kind === 'ribbon') {
    const P = [], n = g.a.length; for (let i = 0; i < n - 1; i++) { const q = [g.a[i], g.a[i + 1], g.b[i + 1], g.b[i]]; P.push(...q[0], ...q[1], ...q[2], ...q[0], ...q[2], ...q[3]); }
    geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.Float32BufferAttribute(P, 3)); geo.computeVertexNormals();
  }
  geo = geo.index ? geo.toNonIndexed() : geo; ['uv', 'uv1', 'uv2'].forEach(k => geo.deleteAttribute(k)); geo.computeVertexNormals();
  const c = new THREE.Color(TH_COL[thKey(g)] || '#ccc'), n = geo.attributes.position.count, C = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) C.set([c.r, c.g, c.b], i * 3);
  geo.setAttribute('color', new THREE.BufferAttribute(C, 3));
  return geo;
}
function buildThermal() {
  thGroup = new THREE.Group(); scene.add(thGroup);
  const T = D.thermal, by = {};
  T.geometry.forEach(g => { const k = TH_MESH[g.layer]; if (k) (by[k] ||= []).push(g); });
  const EM = { hot: ['#FF6A1E', 0.5], warm: ['#C08A20', 0.45], cryo: ['#2F7FD0', 0.5], blades: ['#2F6FB0', 0.25] };
  Object.entries(by).forEach(([k, list]) => {
    const geos = list.map(thPrim), ranges = []; let f = 0;
    geos.forEach((g, i) => { const n = g.attributes.position.count / 3; ranges.push([f, f + n, list[i]]); f += n; });
    const geo = mergeGeometries(geos, false); geos.forEach(g => g.dispose());
    const ghost = k === 'D' || k === 'C', em = EM[k] || ['#000000', 0];
    const mat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: k === 'A' || k === 'D' ? 0.15 : k === 'blades' ? 0.3 : 0.5,
      metalness: k === 'A' || k === 'D' ? 0.9 : k === 'blades' ? 0.6 : k === 'service' ? 0.5 : 0.3, emissive: new THREE.Color(em[0]), emissiveIntensity: em[1],
      transparent: true, opacity: k === 'D' ? 0.5 : k === 'C' ? 0.4 : 1, side: THREE.DoubleSide, depthWrite: !ghost });
    const im = new THREE.InstancedMesh(geo, mat, engineMats.length); engineMats.forEach((m, i) => im.setMatrixAt(i, m)); im.frustumCulled = false;
    im.userData = { th: k, ranges }; im.visible = false; thGroup.add(im); thMeshes[k] = im;
  });
  // coolant flow: dots along the hot, warm and cryogenic lines of engine N1, in the flow direction (supply out, return back)
  const paths = { hot: [], warm: [], cryo: [] };
  T.paths.forEach(p => paths[p.circuit] && paths[p.circuit].push(p.points.map(v3)));
  T.geometry.filter(g => g.kind === 'tube' && paths[g.layer] && !/^(HOT|WARM|CRYO)_/.test(g.comp || '')).forEach(g => paths[g.layer].push(g.points.map(v3)));
  Object.entries(paths).forEach(([k, list]) => {
    const segs = list.map(pts => { const L = [0]; for (let i = 1; i < pts.length; i++) L.push(L[i - 1] + pts[i].distanceTo(pts[i - 1])); return { pts, L }; });
    const per = 8, n = segs.length * per, o = new THREE.Points(new THREE.BufferGeometry(), pointsMat(0.3, TH_FLOW[k][0]));
    o.geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3), 3)); o.frustumCulled = false; o.visible = false;
    o.userData = { k, segs, per, speed: TH_FLOW[k][1] }; thGroup.add(o); thFlow.push(o);
  });
}
function thAt(seg, f) {
  const d = f * seg.L[seg.L.length - 1]; let i = 1; while (i < seg.L.length - 1 && seg.L[i] < d) i++;
  const k = (d - seg.L[i - 1]) / Math.max(1e-9, seg.L[i] - seg.L[i - 1]); return seg.pts[i - 1].clone().lerp(seg.pts[i], k);
}
// Heat steps: 0 source, 1 supermirrors, 2 edge-on blades (adopted), 3 blankets, 4 hot and warm circuits, 5 cryogenic circuit, service and the path to space.
function thUpdate(t, id, TS) {
  if (!thGroup) return;
  const on = id === 'thermal' || (id === 'lab' && view === 'exp'), all = TS < 0 || TS === 5, M = layers.mirrors && on, Cl = layers.cooling && on;
  const show = { A: M && (TS === 1 || TS < 0), D: M && TS === 1, blades: M && (TS === 2 || all), Ct: M && (TS === 3 || all), C: M && TS === 3 && thArch,
    hot: Cl && (TS === 4 || all), warm: Cl && (TS === 4 || all), cryo: Cl && all, service: Cl && all };
  Object.entries(thMeshes).forEach(([k, m]) => { m.visible = !!show[k]; });
  thFlow.forEach(o => {
    o.visible = layers.flow && !!show[o.userData.k];
    if (!o.visible) return;
    const a = o.geometry.attributes.position, { segs, per, speed } = o.userData;
    segs.forEach((s, j) => { for (let q = 0; q < per; q++) { const p = thAt(s, (t * speed + q / per) % 1).applyMatrix4(N1); a.setXYZ(j * per + q, p.x, p.y, p.z); } });
    a.needsUpdate = true;
  });
}
const TH_CHIPS = [[['SOURCE', 'Burn'], ['TAMPER', 'Tamper'], ['AUDIT', 'Pickup audit']],
  [['A', 'Mirror A'], ['D', 'Liner D'], ['SHIELD', 'Shield face'], ['C1', 'C1'], ['L3', 'L3']],
  [['B', 'Blades B'], ['BLADE', 'Blade and edge strip'], ['ROOT', 'Blade root'], ['CAGE', 'Cage'], ['LINES', 'Lines']],
  [['Ct', 'Thin blanket'], ['C', 'Archived blanket'], ['C1', 'C1'], ['C2', 'C2'], ['L1', 'L1'], ['L2', 'L2'], ['L4', 'L4']],
  [['HOT', 'Hot circuit'], ['WARM', 'Warm circuit'], ['OPTICS', 'Driver optics']],
  [['CRYO', 'Cryo circuit'], ['SERVICE', 'Service'], ['SPACE', 'Path to space']]];
// net-level picks map to cards; any picked primitive also shows its own note first
const TH_PICK = { EDGE: 'BLADE', CONE: 'BLADE', SEAT: 'BLADE', STRUT: 'BLADE', ROOT: 'ROOT', PANEL: 'D', SUPPORT: 'D', RAIL: 'SERVICE', PORT: 'SERVICE', COUPLING: 'SERVICE', LUG: 'SERVICE' };
function thPickKey(g) {
  if (TH_PICK[g.comp]) return TH_PICK[g.comp];
  if (g.layer === 'mirror_A') return 'A'; if (g.layer === 'mirror_D') return 'D'; if (g.layer === 'mirror_B' || g.layer === 'blades') return 'BLADE';
  if (g.layer === 'blanket_C') return 'C'; if (g.layer === 'blanket_thin') return 'Ct';
  if (g.layer === 'hot') return 'HOT'; if (g.layer === 'warm') return 'WARM'; if (g.layer === 'service') return 'SERVICE'; return 'CRYO';
}
function srcCases() {
  const S = D.source, y0 = S.levers[0].fusion_J;
  return [...S.levers.map((l, i) => ({ id: 'L' + i, grp: 'Burn levers', label: l.label, cls: l.cls, x: l.xray_share, n: l.neutron_share, p: l.extract_share, y: l.fusion_J / y0, ions: l.to_ions_share, e: l.engine })),
    ...S.tamper.map((t, i) => ({ id: 'T' + i, grp: 'Tamper round the fuel', label: `${t.material === 'C_diamond' ? 'carbon' : t.material} tamper ${t.sigma_g_cm2} g/cm² (${pct(t.tamper_over_fuel)} of the fuel)`, cls: 'MODEL-BASED', x: t.xray_left_share, n: null, p: null, y: 1, e: t.engine })),
    { id: 'BEST', grp: 'Together', label: S.best.label, cls: S.best.cls, x: S.best.xray_left_share, n: null, p: null, y: null, e: S.best.engine }];
}
function srcReadout() {
  const S = D.source, cs = srcCases(), c = cs.find(x => x.id === srcSel) || cs[0], b = cs[0], row = (a, v, k = '') => `<div><dt>${a}</dt><dd class="num ${k}">${v}</dd></div>`;
  const sl = S.slowing.find(x => x.Te_keV === 70) || S.slowing[5], e = c.e, need = D.ledger.need.thrust_per_engine_N;
  const grp = [...new Set(cs.map(x => x.grp))].map(g => `<optgroup label="${esc(g)}">${cs.filter(x => x.grp === g).map(x => `<option value="${x.id}"${x.id === c.id ? ' selected' : ''}>${esc(x.label)}</option>`).join('')}</optgroup>`).join('');
  const bar = c.n == null ? '' : `<div class="fi-split" role="img" aria-label="Fusion energy split: X-rays ${pct(c.x)}, neutrons ${pct(c.n)}, plasma ${pct(c.p)}"><i class="x" style="width:${(100 * Math.min(1, c.x)).toFixed(1)}%"></i><i class="n" style="width:${(100 * c.n).toFixed(1)}%"></i><i class="p" style="width:${(100 * c.p).toFixed(1)}%"></i></div>
    <p class="meta fi-key"><span><i style="background:var(--warn)"></i>X-rays</span><span><i style="background:var(--muted)"></i>neutrons</span><span><i style="background:var(--good)"></i>plasma the nozzle can use</span></p>`;
  const cmp = (v, v0, good) => v == null ? '' : (good ? v > v0 * 1.02 : v < v0 * 0.98) ? 'good' : (good ? v < v0 * 0.98 : v > v0 * 1.02) ? 'bad' : '';
  return `<p class="meta">Where the burn puts its energy, and how each lever changes it all the way to thrust and heat. Pick a case; the numbers below follow it through the ledger. ${chip(c.cls)}</p>
    <label class="fi-sel"><span>Case</span><select id="src-sel">${grp}</select></label>${bar}
    <dl class="fi-dl">${row('At 70 keV, energy the products give to ions', `proton ${pct(sl.p.to_ions)}, alpha ${pct(sl.alpha.to_ions)}; the rest heats electrons`)}${row('Proton range against the 40 µm target', `${(sl.p.range_m * 1e6).toFixed(1)} µm: it all deposits`, 'bad')}
    ${c.y != null ? row('Fusion yield', `×${c.y.toFixed(2)}`, cmp(c.y, 1, true)) : ''}${row('Left as X-rays', pct(c.x), cmp(c.x, b.x, false))}${c.p != null ? row('Plasma the nozzle can use', pct(c.p), cmp(c.p, b.p, true)) : ''}
    ${row('Exhaust speed', `${Math.round(e.exhaust_m_s / 1e3).toLocaleString('en')} km/s (mission ${Math.round(D.ledger.need.exhaust_m_s / 1e3).toLocaleString('en')})`, cmp(e.exhaust_m_s, b.e.exhaust_m_s, true))}
    ${row('Thrust, four engines', `${MN(4 * e.thrust_N)} (need ${MN(4 * need)})`, 'bad')}${row('Engine heat over its radiator share', X(e.heat_over), 'bad')}
    ${row('Heat from X-rays · from strikes', `${pct(e.xray_heat_share)} · ${pct(e.hit_heat_share)}`)}</dl>`;
}
function thFlowBars() {
  const T = D.thermal, n = Object.fromEntries(T.flow.nodes.map(x => [x.id, x])), mx = Math.log10(n.fusion.W), mn = 7;
  const rows = [['fusion', 0], ['driver', 0], ['xray', 1], ['neutron', 1], ['plasma', 1], ['jet', 2], ['side', 2], ['hit', 2], ['space_direct', 1], ['absorbed', 1],
    ['hot', 2], ['warm', 2], ['cryo', 2], ['removed', 3], ['deficit', 3], ['radiator', 3], ['refrig', 3]];
  const cls = { jet: 'good', removed: 'good', radiator: 'good', deficit: 'bad', warm: 'bad', hit: 'bad', refrig: 'bad', cryo: 'bad' };
  return `<div class="fi-flow2" role="list" aria-label="Where one engine's power goes, watts on a logarithmic scale">${rows.map(([k, d]) => { const x = n[k]; if (!x) return '';
    const w = Math.max(0.5, (Math.log10(Math.max(1, x.W)) - mn) / (mx - mn) * 100);
    return `<div role="listitem" class="d${d} ${cls[k] || ''}"><span>${esc(x.label)}</span><i style="width:${w.toFixed(1)}%"></i><b class="num">${W(x.W)}</b></div>`; }).join('')}</div>
    <p class="meta">Watts per engine at the coupled pulse rate, logarithmic bars. ${chip('IMPORTED')} thermal study.</p>`;
}
function thPath() {                                              // the energy path from the reaction to space, and the separate thrust path
  const T = D.thermal, n = Object.fromEntries(T.flow.nodes.map(x => [x.id, x.W])), B = T.strategies.B, base = D.source.levers[0], mx = Math.log10(n.fusion), mn = 7;
  const prod = n.fusion - n.neutron, el = prod * (1 - base.to_ions_share);
  const steps = [['Fusion', n.fusion, ''], ['Charged products (protons, alphas)', prod, ''], ['Heat the electrons directly (the ions pass theirs on)', el, ''], ['X-rays leave the burn (driver heat included)', n.xray, 'bad'],
    ['Strike this engine (X-rays and neutrons)', n.absorbed, 'bad'], ['Turned aside by edge-on blades and mirrors', B.removed_W, 'good'], ['Heat in the hardware: hot, warm, 20 K', n.hot + n.warm + n.cryo, 'bad'],
    ['Carried by the drawn cooling network', n.removed, ''], ['Rejected to space by radiators', n.radiator, 'good'], ['Left with nowhere to go', n.deficit, 'bad']];
  const thr = [['Plasma the nozzle can use', n.plasma, ''], ['Directed jet', n.jet, 'good']];
  const li = ([l, v, c], i, a) => `<div role="listitem" class="d0 ${c}"><span>${i ? '↓ ' : ''}${esc(l)}</span><i style="width:${Math.max(0.5, (Math.log10(Math.max(1, v)) - mn) / (mx - mn) * 100).toFixed(1)}%"></i><b class="num">${W(v)}</b></div>`;
  return `<h4>Energy path, one engine</h4><div class="fi-flow2" role="list" aria-label="Energy path from the reaction to space">${steps.map(li).join('')}</div>
    <h4>Thrust path (separate)</h4><div class="fi-flow2" role="list" aria-label="Thrust path">${thr.map(li).join('')}<div role="listitem" class="d0 good"><span>↓ Thrust, four engines</span><i style="width:0"></i><b class="num">${MN(4 * D.ledger.pulse.thrust_N)}</b></div></div>
    <p class="meta">Logarithmic bars, watts at the coupled pulse. Heat after the blades still ${X(T.comparison.find(r => r.id === 'B+Ct').over_budget_after)} the radiator share. ${chip('IMPORTED')}</p>`;
}
function thReadout(TS) {
  const T = D.thermal, h = T.hot, cr = T.cryo, S = T.strategies, Bd = S.B.detail, Wm = T.warm, Ct = S.C.thin, row = (a, b, c = '') => `<div><dt>${a}</dt><dd class="num ${c}">${b}</dd></div>`;
  let r = '';
  if (TS === 0) return srcReadout() + thChips(TS);
  if (TS === 1) { const sf = T.surfaces.reduce((a, s) => { a.i += s.xray.incident_W; a.r += s.xray.reflected_W; a.t += s.xray.transmitted_W; a.a += s.xray.absorbed_W; return a; }, { i: 0, r: 0, t: 0, a: 0 });
    r = row('Faces meet the burn at (median)', `${S.A.median_psi_deg.toFixed(0)}°`) + row('X-rays on the drawn parts', W(sf.i)) +
    row('Reflected · transmitted · absorbed', `${W(sf.r)} · ${W(sf.t)} · ${W(sf.a)}`, 'bad') + row('A · coated faces return', `${W(S.A.coupled_reflected_W)} (${S.A.coupled_reflected_share.toExponential(1)})`, 'bad') +
    row('D · deflectors inside the engine', 'no measurable benefit', 'bad') + row('Neutrons, charged products', 'not reflected by mirrors'); }
  else if (TS === 2) r = row('B · members keep', `${pct(S.B.keep_share)} of their heat (−${W(S.B.removed_W)})`, 'good') + row('Grazing angle on the faces', `${Bd.alignment.psi_total_mrad.toFixed(3)} mrad`) +
    row('Alignment budget (target, mount, bow, vibration)', Bd.alignment.budget.map(x => x.mrad.toFixed(3)).join(' + ') + ' mrad') + row('Allowed face-to-face difference', `${Bd.alignment.face_dT_allowed_K.toFixed(1)} K`, 'bad') +
    row('First bending mode · pulse rate', `${Bd.vibration.f1_Hz.toFixed(0)} Hz · ${Math.round(Bd.blade.pulse_Hz).toLocaleString('en')} Hz`) +
    row('Edge strip: flux · jump per pulse', `${(Bd.edge.steady_W_m2 / 1e9).toFixed(1)} GW/m² (${X(Bd.edge.over_limit)}) · +${Math.round(Bd.edge.dT_per_pulse_K).toLocaleString('en')} K`, 'bad') +
    row('Added mass (blades, actuators)', `${Math.round(S.B.mass_t)} t + ${Bd.integration.actuator_t.toFixed(0)} t`);
  else if (TS === 3) r = row('Drawn shoes cover (coil silhouette)', pct(T.components.filter(c => /^[CL]\d$/.test(c.id)).reduce((a, c) => a + c.armoured_share * c.sky, 0) / T.components.filter(c => /^[CL]\d$/.test(c.id)).reduce((a, c) => a + c.sky, 0)), 'bad') +
    row('Thin blanket (option) moves to lithium', `${W(Ct.moved_to_hot_W)} for ${Math.round(Ct.mass_t)} t`) + row('Thin blanket: 20 K load', `${W(Ct.cryo_after_W)} (neutrons pass)`, 'bad') +
    row('Archived full blanket: 20 K load', `${W(S.C.cryo_after_W)} for ${Math.round(S.C.mass_t).toLocaleString('en')} t`) + row('Best face material under one pulse', (m => `carbon: +${Math.round(m.dT_surface_K).toLocaleString('en')} K, ${Math.round(-m.margin_K)} K past sublimation`)(T.pulsed.materials.find(x => x.material === 'C_diamond')), 'bad') +
    `<p class="presets"><button id="th-arch" aria-pressed="${thArch}">Show the archived ${Math.round(S.C.mass_t).toLocaleString('en')} t blanket</button></p>`;
  else if (TS === 4) r = row('Hot lithium in → out', `${h.inlet_K} → ${h.outlet_K} K`) + row('Heat to carry (hot + uncooled warm)', W(h.heat_W + h.warm_uncooled_W), 'bad') +
    row('Drawn lines carry', `${W(h.drawn_line_cap_W)} (${X(h.drawn_line_over)} short)`, 'bad') + row('Radiator at 1800 K', `${(h.radiator_m2 / 1e6).toFixed(1)} km² (${X(h.radiator_over_ship)} the ship)`, 'bad') +
    row(`Warm ${Wm.fluid.replace(' (PROTOTYPE)', '')} in → out`, `${Wm.inlet_K} → ${Wm.outlet_K} K`) + row('Warm load (blade roots, optics, vessel walls)', W(Wm.load_W), 'bad') +
    row('Warm radiator at 850 K', `${(Wm.radiator_m2 / 1e6).toFixed(2)} km², ${Math.round(Wm.radiator_t / 1e3).toLocaleString('en')} kt`, 'bad');
  else r = row('20 K windings', W(cr.stage20_W), 'bad') + row(`Refrigeration (${Math.round(cr.cop20_W_per_W)} W/W)`, W(cr.refrig_W), 'bad') + row('80 K screens', W(cr.stage80_W)) +
    row('Quench dump per engine', `${(cr.quench.stored_J / 1e9).toFixed(1)} GJ over ${cr.quench.dump_s} s`);
  return `<dl class="fi-dl">${r}</dl>${TS === 5 ? thPath() : TS === 4 ? thFlowBars() : ''}${thChips(TS)}`;
}
function thChips(TS) {
  return `<p class="fi-chips" role="group" aria-label="Inspect a component">${TH_CHIPS[TS].map(([k, l]) => `<button data-insp="${k}" aria-pressed="${inspId === k}">${esc(l)}</button>`).join('')}</p><div id="insp" class="fi-insp">${inspId ? inspCard(inspId) : '<p class="meta">Pick a component above or click one in the 3D view.</p>'}</div>`;
}
function probLinks(ids) { return ids.map(i => `<a href="#p-${i}">${i}</a>`).join(' '); }
function mirrorChart(psiMark) {
  const O = D.thermal.optics, w = 300, hh = 120, lx = v => 30 + (Math.log10(v) + 2) / 5 * (w - 40), ly = v => 10 + (1 - v) * (hh - 30);
  const line = (arr, c, dash = '') => `<polyline fill="none" stroke="${c}" stroke-width="2" ${dash} points="${O.psi_mrad.map((p, i) => `${lx(p).toFixed(1)},${ly(arr[i]).toFixed(1)}`).join(' ')}"/>`;
  const cols = ['#7CC4FF', '#9F8CFF', '#E58BD0', '#FFB060', '#FF6B5B'];
  return `<svg viewBox="0 0 ${w} ${hh}" class="fi-chart" role="img" aria-label="Mirror reflectivity against grazing angle for 3 to 300 keV and for the whole burn spectrum; the faces sit at ${psiMark.toFixed(0)} degrees, where it is zero">
    <rect x="${lx(psiMark * Math.PI / 180 * 1e3) - 3}" y="8" width="6" height="${hh - 26}" fill="var(--bad)" opacity="0.5"/>
    ${O.R.map((arr, i) => line(arr, cols[i])).join('')}${line(O.R_spectrum, 'var(--ink-strong)', 'stroke-dasharray="4 3"')}
    <line x1="30" y1="${hh - 20}" x2="${w - 10}" y2="${hh - 20}" stroke="var(--line-strong)"/>
    ${[0.01, 0.1, 1, 10, 100, 1000].map(v => `<text x="${lx(v)}" y="${hh - 6}" font-size="9" fill="var(--muted)" text-anchor="middle">${v >= 1 ? v : v}</text>`).join('')}
    <text x="${w - 10}" y="${hh - 24}" font-size="9" fill="var(--muted)" text-anchor="end">grazing angle, mrad</text><text x="32" y="16" font-size="9" fill="var(--muted)">R = 1</text></svg>
    <p class="meta fi-key">${O.E_keV.map((E, i) => `<span><i style="background:${cols[i]}"></i>${E} keV</span>`).join('')}<span><i style="background:var(--ink-strong)"></i>burn spectrum</span><span><i style="background:var(--bad)"></i>these faces</span></p>`;
}
const TH_COMPS = { BLADE: ['EDGE', 'SEAT', 'STRUT', 'CONE', 'CAGE'], ROOT: ['ROOT'], WARM: ['WARM_RING', 'WARM_HOOP', 'WARM_RISER', 'WARM_LINK'], SOURCE: ['TARGET'], TAMPER: ['TARGET'],
  AUDIT: ['LINES'], SERVICE: ['RAIL', 'PORT', 'COUPLING', 'LUG'], Ct: ['C1', 'C2', 'L1', 'L2', 'L3', 'L4'], SPACE: ['TARGET', 'HOT', 'CRYO'] };
function probsFor(k, extra = []) {                                // problems whose register entry names one of this card's components
  const keys = TH_COMPS[k] || [k], ids = new Set(extra);
  D.problems.items.forEach(p => { if (/^ENG-0[456]/.test(p.id) && (p.components || []).some(c => keys.includes(c))) ids.add(p.id); });
  return [...ids].sort();
}
function primNote() { return inspPrim ? `<p class="meta fi-pick">Picked: <b>${esc(inspPrim.comp || inspPrim.layer)}</b>, ${esc(inspPrim.note || inspPrim.layer_name || '')}</p>` : ''; }
function inspCard(k) {
  const T = D.thermal, row = (a, b, c = '') => `<div><dt>${a}</dt><dd class="num ${c}">${b}</dd></div>`, S = T.strategies, Bd = S.B.detail, SR = D.source;
  const comp = T.components.find(c => c.id === k), hr = T.hot.rows.find(x => x.id === k), cr = T.cryo.rows.find(x => x.id === k), tail = (ids, note = '') => `<p class="meta">${note}Problems: ${probLinks(ids)} · ${chip('IMPORTED')} thermal study</p>`;
  if (comp) {
    const pk = T.pulsed.points.filter(p => p.comp === k), Cr = S.C.rows.find(x => x.id === k), coil = /^[CL]\d$/.test(k);
    let h = row('Share of the burn\'s sky', pct(comp.sky)) + row('X-rays · neutrons · charged strikes', `${W(comp.xray_W)} · ${W(comp.neutron_W)} · ${W(comp.charged_W)}`) +
      row('Faces meet the rays at (median)', `${comp.psi_median_deg.toFixed(0)}°`) + row('Into lithium (hot)', W(comp.hot_W)) + row('Into parts with no coolant drawn', W(comp.warm_W), comp.warm_W > 0 ? 'bad' : '');
    if (coil) h += row('Silhouette behind armour', pct(comp.armoured_share), 'bad') + row('Neutron heat in the 20 K winding', W(comp.cryo_W), 'bad');
    if (hr) h += row('Mean flux on the hot faces', `${(hr.flux_W_m2 / 1e6).toFixed(0)} MW/m² (${X(hr.flux_W_m2 / hr.q_limit_W_m2)} the 20 MW/m² limit)`, 'bad') +
      row('Lithium speed needed in the channels', `${(hr.v_needed_m_s / 1e3).toFixed(1)} km/s (limit 10 m/s)`, 'bad') + row(`MHD loss per run at 10 m/s (${hr.B_T.toFixed(1)} T)`, `${(hr.dp_mhd_bare_Pa / 1e6).toFixed(1)} MPa bare, ${(hr.dp_mhd_fci_Pa / 1e6).toFixed(2)} MPa with SiC inserts`);
    pk.forEach(p => { h += row(`Pulse on the ${p.surface.toLowerCase()} (${p.material === 'Ni' ? 'steel' : p.material})`, `${(p.fluence_J_m2 / 1e6).toFixed(2)} MJ/m², surface +${Math.round(p.dT_surface_K).toLocaleString('en')} K`, p.dT_surface_K > 1500 ? 'bad' : ''); });
    if (cr) h += row('Refrigeration for this coil', W(cr.refrig_W), 'bad') + row('Field at the winding', `${cr.field_T.toFixed(1)} T`);
    if (Cr) h += row('Archived blanket C: mass, 20 K load after', `${Math.round(Cr.mass_t)} t, ${W(Cr.cryo_after_W)}`);
    const base = k === 'OPTICS' ? ['ENG-053'] : k === 'CAGE' || k === 'LINES' ? ['ENG-052', 'ENG-056'] : k === 'SHIELD' ? ['ENG-040', 'ENG-044', 'ENG-045'] : ['ENG-043', 'ENG-045', 'ENG-047', 'ENG-048'];
    return `<h4>${esc(k === 'SHIELD' ? 'Shield burn face' : k === 'CAGE' ? 'Nozzle cage, seats and struts' : k === 'LINES' ? 'Coolant, cryogen and lead lines' : k === 'OPTICS' ? 'Driver final optics' : `Coil ${k}`)}</h4>${primNote()}<dl class="fi-dl">${h}</dl>${tail(probsFor(k, base))}`;
  }
  if (k === 'SOURCE') { const sl = SR.slowing, b = SR.levers[0];
    return `<h4>The burn: where the products leave their energy</h4><dl class="fi-dl">${row('Target', `${(SR.design.mass_kg * 1e6).toFixed(2)} mg, R ${SR.design.R0_um.toFixed(0)} µm, ρR ${SR.design.rhoR_g_cm2} g/cm²`)}${row('Burn time · gain', `${b.duration_ps.toFixed(1)} ps · ${b.gain.toFixed(1)}`)}
      ${sl.filter(x => [10, 30, 70, 150, 300].includes(x.Te_keV)).map(x => row(`Te ${x.Te_keV} keV: to ions (p · α)`, `${pct(x.p.to_ions)} · ${pct(x.alpha.to_ions)}`)).join('')}
      ${row('Self-heating share', pct(b.self_heat_share))}${row('Energy booked to particle-number change', pct(b.number_change_share))}${row('Integration residual', b.residual_share.toExponential(1))}</dl>
      <p>${esc(SR.findings[0])}</p>${tail(probsFor(k, ['ENG-061']), `${chip('CALCULATED')} `)}`; }
  if (k === 'TAMPER') { const tw = SR.tamper.filter(t => t.material === 'W');
    return `<h4>X-ray trapping tamper round the fuel</h4><dl class="fi-dl">${tw.map(t => row(`W ${t.sigma_g_cm2} g/cm²: absorbs · exhaust`, `${pct(t.absorbed)} · ${Math.round(t.exhaust_m_s / 1e3).toLocaleString('en')} km/s`, t.absorbed > 0.5 ? 'good' : '')).join('')}
      ${row('Best source case and tamper: X-rays · thrust ×4', `${pct(SR.best.xray_left_share)} · ${MN(4 * SR.best.engine.thrust_N)}`)}${row('Heat over its radiator share', X(SR.best.engine.heat_over), 'bad')}</dl>
      <p>${esc(SR.findings.find(f => /tamper/.test(f)) || '')}</p>${tail(probsFor(k, ['ENG-061', 'ENG-062']), `${chip('MODEL-BASED')} cold opacity, an upper bound. `)}`; }
  if (k === 'AUDIT') { const A = SR.audit;
    return `<h4>Pickup audit: 63.1 % against 54.6 %</h4><dl class="fi-dl">${row('Geometric trace of every drawn part', pct(A.geometry_sky))}${Object.entries(A.geometry_terms).map(([a, v]) => row(`  ${a.replace(/_/g, ', ').replace(', and,', ' and')}`, pct(v))).join('')}
      ${row('Compact study\'s piped share', `(${W(A.pickup_terms.piped_W)} − ${W(A.pickup_terms.charged_hits_W)}) / ${W(A.pickup_terms.neutral_W)} = ${pct(T.reconcile.ledger_pickup)}`)}${row('Ledger now uses', `${pct(A.ledger_pickup)} (geometric trace)`, 'good')}</dl>
      <ul class="fi-ul">${A.findings.map(f => `<li>${esc(f)}</li>`).join('')}</ul>${tail(probsFor(k, ['ENG-056']))}`; }
  if (k === 'Ct') { const c = S.C.thin;
    return `<h4>Thin coil blanket <span class="st st-WORKING">optional configuration</span></h4>${primNote()}<dl class="fi-dl">${row('Areal mass · mass per engine', `${Math.round(c.areal_kg_m2)} kg/m² · ${Math.round(c.mass_t)} t`)}${row('Moved into lithium', W(c.moved_to_hot_W))}
      ${row('Neutrons through to the winding', pct(c.transmission), 'bad')}${row('20 K load after', W(c.cryo_after_W), 'bad')}</dl><p>${esc(c.note)}</p>${tail(probsFor(k, ['ENG-054', 'ENG-059']))}`; }
  if (k === 'BLADE') { const bl = Bd.blade, ed = Bd.edge;
    return `<h4>Edge-on blade and edge strip <span class="st st-WORKING">adopted direction</span></h4>${primNote()}<dl class="fi-dl">${row('Material', esc(bl.material))}${row('Thickness · span · width', `${bl.thickness_m * 1000} mm · ${bl.span_m} m · ${bl.width_m.toFixed(2)} m`)}
      ${row('Grazing angle at the alignment budget', `${Bd.alignment.psi_total_mrad.toFixed(3)} mrad`)}${row('Members keep', `${pct(Bd.alignment.keep_share_at_budget)} of their heat`, 'good')}
      ${row('Edge flux', `${(ed.steady_W_m2 / 1e9).toFixed(1)} GW/m², ${X(ed.over_limit)} the face limit`, 'bad')}${row('Edge jump per pulse', `+${Math.round(ed.dT_per_pulse_K).toLocaleString('en')} K, ${pct(ed.stress_over_strength)} of CFC strength`, 'bad')}</dl>
      <p>${esc(ed.note)}</p>${tail(probsFor(k, ['ENG-052']))}`; }
  if (k === 'ROOT') { const al = Bd.alignment;
    return `<h4>Blade root: actuator, damper, lithium tap</h4>${primNote()}<dl class="fi-dl">${al.budget.map(x => row(esc(x.term), `${x.mrad.toFixed(3)} mrad`)).join('')}${row('Sum', `${al.psi_total_mrad.toFixed(3)} mrad`)}
      ${row('Allowed face-to-face difference', `${al.face_dT_allowed_K.toFixed(1)} K`, 'bad')}${row('First mode · pulse rate', `${Bd.vibration.f1_Hz.toFixed(0)} Hz · ${Math.round(Bd.blade.pulse_Hz).toLocaleString('en')} Hz`)}${row('Actuators per engine', `${Bd.integration.actuator_t.toFixed(1)} t`)}</dl>
      <p>${esc(al.note)} ${esc(Bd.vibration.note)}</p>${tail(probsFor(k, ['ENG-058']))}`; }
  if (k === 'HOT') { const h = T.hot;
    return `<h4>Hot circuit (lithium)</h4>${primNote()}<dl class="fi-dl">${row('Inlet → outlet', `${h.inlet_K} → ${h.outlet_K} K`)}${row('Heat to carry', W(h.heat_W + h.warm_uncooled_W), 'bad')}${row('Mass flow needed', `${(h.mdot_kg_s / 1e6).toFixed(2)} kt/s`, 'bad')}
      ${row('Drawn feeder and panel lines carry', W(h.drawn_line_cap_W), 'bad')}${row('Flow area for the radiator share alone', `${h.budget_line_area_m2.toFixed(2)} m²`)}${row('Pumping at 1 MPa', W(h.pump_W))}
      ${row('Radiator, 1800 K', `${(h.radiator_m2 / 1e6).toFixed(1)} km², ${Math.round(h.radiator_t / 1e3).toLocaleString('en')} kt`, 'bad')}${row('Brayton: electric · driver need', `${W(h.brayton.electric_W)} · ${W(h.brayton.driver_elec_W)}`)}
      ${row('Brayton radiator (cold side ' + h.brayton.cold_K + ' K)', `×${h.brayton.radiator_over_direct.toFixed(0)}`, 'bad')}</dl><p class="meta">Supply ring 1500 K and return ring 1800 K at the shield, eight longeron feeders, branches to every jacket, exchanger to the ship's HOT radiator. ${esc(h.brayton.note)}</p>${tail(probsFor(k, ['ENG-045', 'ENG-046', 'ENG-047', 'ENG-049', 'ENG-055']))}`; }
  if (k === 'WARM') { const w = T.warm;
    return `<h4>Warm circuit (${esc(w.fluid.replace(' (PROTOTYPE)', ''))}, PROTOTYPE)</h4>${primNote()}<dl class="fi-dl">${row('Inlet → outlet', `${w.inlet_K} → ${w.outlet_K} K`)}${row('Load', W(w.load_W), 'bad')}${row('Mass flow', `${Math.round(w.mdot_kg_s).toLocaleString('en')} kg/s`)}
      ${row('Radiator at 850 K', `${(w.radiator_m2 / 1e6).toFixed(2)} km², ${Math.round(w.radiator_t / 1e3).toLocaleString('en')} kt`, 'bad')}</dl><p>${esc(w.note)}</p>${tail(probsFor(k, ['ENG-060']))}`; }
  if (k === 'CRYO') { const c = T.cryo;
    return `<h4>Cryogenic circuit (20 K windings, 80 K screens)</h4>${primNote()}<dl class="fi-dl">${c.rows.map(x => row(`${x.id}: 20 K · refrigeration`, `${W(x.stage20_W)} · ${W(x.refrig_W)}`, 'bad')).join('')}
      ${row('LOW radiator for the refrigerators', `${(c.low_radiator_m2 / 1e6).toFixed(0)} km²`, 'bad')}${row('Quench dump', `${W(c.quench.dump_W)} for ${c.quench.dump_s} s into warm resistors`)}</dl>
      <p class="meta">Its own supply and return headers behind the shield, one line pair per coil, never shared with the lithium. ${esc(c.separation)}</p>${tail(probsFor(k, ['ENG-048', 'ENG-051', 'ENG-059']))}`; }
  if (k === 'SERVICE') return `<h4>Service and replaceable interfaces</h4>${primNote()}<dl class="fi-dl">${row('Service rail', 'one exchange carriage reaches every blade root and coupling')}${row('Edge-strip ports', 'one per longeron; strips slide out along it')}
      ${row('Quick-disconnect couplings', 'between the rings and the feeders, remote handling')}${row('Blanket lift lugs', 'segments come off in place')}${row('Strip life', `${(3600 * Bd.blade.pulse_Hz / 1e6).toFixed(1)} million pulses per hour`, 'bad')}</dl>
      <p class="meta">Drawn as interfaces (PROTOTYPE); no maintenance rate is calculated yet (OPEN).</p>${tail(probsFor(k, ['ENG-057', 'ENG-058']))}`;
  if (k === 'SPACE') return thPath() + tail(probsFor(k, ['ENG-030', 'ENG-046', 'ENG-048', 'ENG-063']));
  const s = S[k]; if (!s) return '';
  let body = `<p>${esc(s.why)}</p>`;
  if (k === 'A') body = mirrorChart(s.median_psi_deg) + body + `<dl class="fi-dl">${row('Reflected, coupled pulse', W(s.coupled_reflected_W), 'bad')}${row('Far-IR, steady regime: tungsten face absorbs', W(s.steady_absorbed_W_face))}${row('Same with a B4C face', W(s.steady_absorbed_B4C_face))}${row('Coating mass', `${(s.mass_t * 1000).toFixed(0)} kg`)}</dl>`;
  if (k === 'B') body += `<dl class="fi-dl">${row('Grazing angle on the faces', `${s.psi_mrad.toFixed(2)} mrad`)}${row('Face absorptance there', pct(s.face_absorptance))}${row('Heat kept', `${pct(s.keep_share)} (−${W(s.removed_W)})`, 'good')}${row('Added mass', `${Math.round(s.mass_t)} t`)}</dl>`;
  if (k === 'C') body += `<table class="fi-stack"><tbody>${s.stack.map(L => `<tr><td><i style="background:${TH_COL[L.layer] || '#888'}"></i>${esc(L.layer)}</td><td class="num">${(L.t_m * 1000).toFixed(0)} mm</td><td>${esc(L.role)}</td></tr>`).join('')}</tbody></table>
    <dl class="fi-dl">${row('Areal mass', `${Math.round(s.areal_kg_m2).toLocaleString('en')} kg/m²`)}${row('Neutrons through to the winding', s.transmission.toExponential(1))}${row('Mass per engine', `${Math.round(s.mass_t).toLocaleString('en')} t`, 'bad')}</dl><p class="meta">${esc(s.status)}</p>`;
  if (k === 'D') body += `<dl class="fi-dl">${s.rows.map(x => row(`${x.id}: turn needed`, `${x.psi_needed_mrad.toFixed(0)} mrad (Pt θc ${x.theta_c_1keV_mrad.toFixed(0)} mrad at 1 keV)`, 'bad')).join('')}</dl>`;
  const tag = k === 'B' ? 'adopted direction' : k === 'C' ? 'archived' : s.verdict.toLowerCase();
  return `<h4>${esc(s.title)} <span class="st st-${s.verdict.startsWith('NO') || k === 'C' ? 'OPEN' : 'WORKING'}">${esc(tag)}</span></h4>${primNote()}${body}${tail(probsFor(k, k === 'A' ? ['ENG-040', 'ENG-042'] : k === 'B' ? ['ENG-052', 'ENG-057'] : k === 'C' ? ['ENG-043', 'ENG-054'] : ['ENG-041']))}`;
}
function inspect(k, prim = null) { inspId = k; inspPrim = prim; const el = $('insp'); if (el) el.innerHTML = inspCard(k); document.querySelectorAll('[data-insp]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.insp === k))); }
readEl.addEventListener('click', ev => { const b = ev.target.closest('[data-insp]'); if (b) inspect(b.dataset.insp);
  if (ev.target.id === 'th-arch') { thArch = !thArch; ev.target.setAttribute('aria-pressed', String(thArch)); dirty = true; } });
readEl.addEventListener('change', ev => { if (ev.target.id === 'src-sel') { srcSel = ev.target.value; stageReadout(); const s = $('src-sel'); if (s) s.focus(); } });
function compAt(pw) {                                           // nearest thermal component to a picked world point (engine frame by its instance)
  let best = null, bd = 1e9;
  engineMats.forEach(m => { const p = pw.clone().applyMatrix4(m.clone().invert()), rr = Math.hypot(p.y, p.z);
    D.engine.coils.forEach(c => { const d = Math.hypot(p.x - c.x, rr - c.r); if (d < bd) { bd = d; best = c.name; } });
    if (p.x > -13.2 && p.x < -10.4 && rr < 5.6 && 0.5 < bd) { bd = 0.5; best = 'SHIELD'; }
    if (rr > 4.9 && bd > 1.3) { best = 'CAGE'; bd = 1.3; } });
  return best;
}

// ---- hover and pick (engine parts by category, ship schematic) ---------------------------------------------------------------------------
let ray = null, mouse = null;
function hit(ev) {
  const r = canvas.getBoundingClientRect(); mouse.set((ev.clientX - r.left) / r.width * 2 - 1, -(ev.clientY - r.top) / r.height * 2 + 1);
  ray.setFromCamera(mouse, camera);
  const objs = Object.values(catMeshes).filter(m => m.material.visible);
  const h = ray.intersectObjects(objs, false)[0];
  return h ? { cat: h.object.userData.cat, x: ev.clientX - r.left, y: ev.clientY - r.top } : null;
}
function hover(ev) {
  if (!ready || TWO_D.has(STAGES[si])) { tip.hidden = true; return; }
  const h = hit(ev); if (!h) { tip.hidden = true; return; }
  const c = M.categories.find(x => x.id === h.cat); tip.hidden = false; tip.textContent = c.title; tip.style.transform = `translate(${h.x + 12}px, ${h.y + 12}px)`;
}
function pick(ev) {
  if (!ready || TWO_D.has(STAGES[si])) return;
  if (STAGES[si] === 'thermal') {
    const r = canvas.getBoundingClientRect(); mouse.set((ev.clientX - r.left) / r.width * 2 - 1, -(ev.clientY - r.top) / r.height * 2 + 1); ray.setFromCamera(mouse, camera);
    const hm = ray.intersectObjects(Object.values(thMeshes).filter(m => m.visible), false)[0];
    if (hm) { const rg = hm.object.userData.ranges.find(([a, b]) => hm.faceIndex >= a && hm.faceIndex < b), g = rg && rg[2];
      if (g) { inspect(thPickKey(g), g); return; } }
    const he = ray.intersectObjects(Object.values(catMeshes).filter(m => m.material.visible), false)[0];
    if (he) { const k = he.object.userData.cat === 'HOT_THERMAL' ? 'HOT' : he.object.userData.cat === 'CRYOGENIC' ? 'CRYO' : compAt(he.point); if (k) inspect(k); }
    return;
  }
  const h = hit(ev); if (!h) return;
  if (STAGES[si] !== 'hardware') setStage(1);
  focusCat = h.cat; applyCats();
}

// ---- loop --------------------------------------------------------------------------------------------------------------------------------
let fpsN = 0, fpsT = 0;
function frame(now) {
  const t = now / 1000, dt = last ? Math.min(0.1, t - last) : 0; last = t;
  const id = STAGES[si]; sdt = playing && !reduced ? dt : 0;
  if (playing && id !== 'lab') {
    u += dt / DUR[id];
    if (u >= 1) { if (si < STAGES.length - 2) { setStage(si + 1); } else { u = 1; playing = false; syncPlay(); } }
    $('scrub').value = Math.round(u * 1000);
    if (['magnets', 'ignition', 'nozzle'].includes(id)) stageReadout();
  }
  if (camT < 1 && camTo && !userCam) {
    camT = Math.min(1, camT + dt / 2.2); const k = ease(camT);
    camera.position.lerpVectors(camFrom.p, camTo.p, k); controls.target.lerpVectors(camFrom.t, camTo.t, k);
  }
  controls.update();
  const r = stage.getBoundingClientRect();
  const w = Math.max(1, Math.round(r.width)), h = Math.max(1, Math.round(r.height));
  if (canvas.width !== Math.round(w * renderer.getPixelRatio()) || canvas.height !== Math.round(h * renderer.getPixelRatio())) { renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); sizeC2(); }
  update(t);
  if (!TWO_D.has(id) || t - enterT < 3) renderer.render(scene, camera);          // the 3D view keeps moving under the fade into a 2-D scene
  placeMarkers(w, h);
  draw2d(t);
  fpsN++; if (t - fpsT > 1) { window.__fi.fps = fpsN / (t - fpsT); window.__fi.calls = renderer.info.render.calls; window.__fi.tris = renderer.info.render.triangles; fpsN = 0; fpsT = t; }
}

// ---- controls ----------------------------------------------------------------------------------------------------------------------------
function syncPlay() { const b = $('play'); b.textContent = playing ? '❚❚' : '▶'; b.setAttribute('aria-label', playing ? 'Pause' : 'Play'); }
const memU = {};                             // a stage you return to resumes where you left it (autoplay into the next stage starts at 0)
document.querySelector('.fi-stages').addEventListener('click', ev => { const b = ev.target.closest('[data-stage]'); if (!b) return;
  memU[STAGES[si]] = u; setStage(STAGES.indexOf(b.dataset.stage)); const m = memU[STAGES[si]];
  if (m > 0.02 && m < 0.98) { u = m; $('scrub').value = Math.round(u * 1000); stageReadout(); dirty = true; draw2d(); } });
document.querySelector('.fi-stages').addEventListener('keydown', ev => {
  if (ev.key === 'ArrowRight' || ev.key === 'ArrowLeft') { ev.preventDefault(); setStage(si + (ev.key === 'ArrowRight' ? 1 : -1)); document.querySelector('.fi-stages [aria-selected="true"]')?.focus(); }
});
$('prev').addEventListener('click', () => setStage(si - 1));
$('next').addEventListener('click', () => setStage(si + 1));
$('play').addEventListener('click', () => { playing = !playing; if (playing && u >= 1) u = 0; syncPlay(); });
$('scrub').addEventListener('input', ev => { u = +ev.target.value / 1000; playing = false; syncPlay(); stageReadout(); dirty = true; draw2d(); });
$('graphs').addEventListener('click', () => { graphs = !graphs; $('graphs').setAttribute('aria-pressed', String(graphs)); draw2d(); });
function ctlUpdate() {                       // in-scene controls: the plasma temperature in the Many stage
  const id = STAGES[si], on = id === 'many' && view !== 'exp';
  ctlEl.hidden = !on && !(id === 'many' && view === 'exp');
  if (id !== 'many') { ctlEl.hidden = true; return; }
  ctlEl.innerHTML = view === 'exp' ? `<span>Plasma from your Experiment levers: ${lab.Ti} keV, ${pct(lab.d)} D</span>`
    : `<span>Plasma temperature</span>${[40, 60, 100, 160, 200].map(T => `<button data-T="${T}" aria-pressed="${PLX.T === T}">${T} keV</button>`).join('')}`;
}
ctlEl.addEventListener('click', ev => { const b = ev.target.closest('[data-T]'); if (!b) return; PLX.T = +b.dataset.T; ctlUpdate(); draw2d(); });
$('replay').addEventListener('click', () => { u = 0.07; playing = true; syncPlay(); });
document.querySelectorAll('[data-view]').forEach(b => b.addEventListener('click', () => {
  view = b.dataset.view; root.dataset.view = view;
  document.querySelectorAll('[data-view]').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
  if (STAGES[si] === 'lab') labUpdate(); else stageReadout(); ctlUpdate(); draw2d();
}));
document.querySelectorAll('[data-layer]').forEach(b => b.addEventListener('change', () => { layers[b.dataset.layer] = b.checked; dirty = true; }));
addEventListener('keydown', ev => {
  if (ev.target.closest('input, textarea, select')) return;
  if (ev.key === ' ' && document.activeElement === document.body) { ev.preventDefault(); $('play').click(); }
});

boot().catch(err => { cstatus.hidden = false; cstatus.textContent = `The simulation data could not load: ${err.message}`; cstatus.classList.add('error'); });
