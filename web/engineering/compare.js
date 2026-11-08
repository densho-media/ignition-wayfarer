// Engineering · What we have, what we need (tools/story.py writes engineering/compare/ and its compare.json).
// Per open problem, two 3D views side by side under one camera and one scale:
//   left   today's ship: the Explore Ship model (../../viewer/build.json names the GLB); the problem's M5 subsystems (holo_file) solid,
//          the rest a ghost
//   right  what the problem needs: the problem map's 1 m blockout (compare.json parts, ship frame), the problem's groups solid
// Presentation only: it computes no spacecraft facts. Blender frame (x, y, z) -> three (x, z, -y), as the viewer.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

const VIEWER = '../../viewer/';
const DATA = 'compare.json';
const $ = id => document.getElementById(id);
const stage = $('stage'), canvas = $('compare-view'), gate = $('gate'), cstatus = $('cstatus');

// Functional colours of the blockout (overlay colours that explain function; never ship materials).
const FUNC = {
  MAIN_PROPULSION: 0xd2553c, STRUCTURE: 0x9a8f80, HELIUM3: 0x9fd0ff, DEUTERIUM: 0x6fa8ff, HYDROGEN: 0x4f7fd0, POWER: 0xe8c547,
  HOT_RADIATOR: 0xff6a3a, WARM_RADIATOR: 0xf0a040, LOW_RADIATOR: 0x7fd1c8, SHIELD: 0x7fd18b, VIS_XRAY: 0xc58aff, SENSORS_COMMS: 0x4fb3ff,
  SERVICE: 0xd9d06a, HABITAT: 0x6fcf7f,
};
const GROUP_NAMES = {
  hull: 'hull', engineering: 'engineering bay', habitat: 'habitat', storage: 'tanks', bow: 'bow', radiators: 'radiators (earlier baseline)',
  fdp1_structure: 'FDP-1 structure', fdp1_nozzle: 'FDP-1 magnetic nozzle', fdp1_power: 'FDP-1 power', fdp1_shield: 'FDP-1 shielding',
  fdp1_reaction: 'FDP-1 reaction chamber', fdp1_drivers: 'FDP-1 drivers', fdp1_fuel_prep: 'FDP-1 fuel preparation',
  fdp1_service: 'FDP-1 service', fdp1_thermal: 'FDP-1 radiator wings and loops', fdp1_sensors: 'FDP-1 sensors', fdp1_tanks: 'FDP-1 tank bays',
};

let data = null;
let current = null;                  // the shown pair
let loaded = false;

// ---- captions (work before the 3D loads) ---------------------------------------------------------------------------------------------
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
function caption(pair) {
  const p = data.problems[pair.id] || {};
  const now = (p.current || []).map(c => `<li>${esc(c)}</li>`).join('');
  $('caption').innerHTML = `<h3><code>${pair.id}</code> ${esc(p.title || '')} <span class="st st-${esc((p.status || '').split(' ')[0])}">${esc(p.status || '')}</span></h3>
    <p>${esc(pair.note)}</p>
    <dl><dt>Today</dt><dd><ul class="plain">${now}</ul></dd><dt>Needed</dt><dd>${esc(p.target || '')}</dd><dt>Gap</dt><dd>${esc(p.gap || '')}</dd></dl>
    <p class="note"><a href="${esc(data.source.link)}#${pair.id}">${pair.id} in the problem map</a></p>`;
}
function select(id, push) {
  const pair = data.pairs.find(p => p.id === id) || data.pairs[0];
  current = pair;
  for (const b of document.querySelectorAll('.pairs button')) b.setAttribute('aria-selected', String(b.dataset.pair === pair.id));
  caption(pair);
  if (push) history.replaceState(null, '', '#' + pair.id);
  if (loaded) show(pair);
}

// ---- blockout shapes (ports of the problem map's fdp1diag/v2kit.py, in the Blender ship frame) -------------------------------------
function mesh(vs, fs) {
  const pos = [];
  for (const f of fs) for (let i = 1; i < f.length - 1; i++) for (const k of [f[0], f[i], f[i + 1]]) pos.push(...vs[k]);
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.computeVertexNormals();
  return g;
}
function rev(profile, a0 = 0, a1 = 360, step = 2, centre = [0, 0]) {
  const full = Math.abs(a1 - a0) >= 359.999;
  const rmax = Math.max(...profile.map(p => p[1])) || 1;
  const n = Math.max(12, Math.min(128, Math.floor(Math.abs((a1 - a0) * Math.PI / 180) * rmax / step)));
  const m = profile.length, cols = full ? n : n + 1, vs = [], fs = [];
  for (let i = 0; i < cols; i++) {
    const a = (a0 + (a1 - a0) * i / n) * Math.PI / 180, ca = Math.cos(a), sa = Math.sin(a);
    for (const [x, r] of profile) vs.push([x, centre[0] + r * ca, centre[1] + r * sa]);
  }
  for (let i = 0; i < n; i++) {
    const i2 = full ? (i + 1) % cols : i + 1;
    for (let j = 0; j < m; j++) { const j2 = (j + 1) % m; fs.push([i * m + j, i * m + j2, i2 * m + j2, i2 * m + j]); }
  }
  if (!full) { fs.push([...Array(m).keys()].reverse()); fs.push([...Array(m).keys()].map(j => n * m + j)); }
  return mesh(vs, fs);
}
const arcOf = p => p.arc || [0, 360];
function ring(p) {
  const prof = p.r0 > 0 ? [[p.x0, p.r0], [p.x1, p.r0], [p.x1, p.r1], [p.x0, p.r1]] : [[p.x0, 0], [p.x1, 0], [p.x1, p.r1], [p.x0, p.r1]];
  return rev(prof, ...arcOf(p), 2, p.centre || [0, 0]);
}
function frustum(p) {
  const prof = p.ri0 == null ? [[p.x0, 0], [p.x1, 0], [p.x1, p.r1], [p.x0, p.r0]] : [[p.x0, p.ri0], [p.x1, p.ri1], [p.x1, p.r1], [p.x0, p.r0]];
  return rev(prof, ...arcOf(p), 2, p.centre || [0, 0]);
}
function torus(p) {
  const nv = 8, prof = [];
  for (let j = 0; j < nv; j++) prof.push([p.x + p.a * Math.cos(2 * Math.PI * j / nv), p.R + p.a * Math.sin(2 * Math.PI * j / nv)]);
  return rev(prof, ...arcOf(p), Math.max(2, p.R / 60));
}
function box(p) {
  const [dx, dy, dz] = p.size.map(s => s / 2), c = p.centre, r = (p.roll || 0) * Math.PI / 180, ca = Math.cos(r), sa = Math.sin(r);
  const vs = [[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]].map(([sx, sy, sz]) => {
    const y = sy * dy, z = sz * dz;
    return [c[0] + sx * dx, c[1] + y * ca - z * sa, c[2] + y * sa + z * ca];
  });
  return mesh(vs, [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]);
}
function panel(p) {
  const q = p.corners, t = p.thickness || 0.3;
  const u = [0, 1, 2].map(i => q[1][i] - q[0][i]), v = [0, 1, 2].map(i => q[3][i] - q[0][i]);
  let n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
  const L = Math.hypot(...n) || 1;
  n = n.map(x => x / L * t);
  const vs = [...q, ...q.map(c => c.map((x, i) => x + n[i]))];
  return mesh(vs, [[3, 2, 1, 0], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]);
}
function tube(p) {
  const pts = p.points.map(q => new THREE.Vector3(...q));
  const geos = [];
  for (let i = 0; i < pts.length - 1; i++) {
    const len = pts[i].distanceTo(pts[i + 1]);
    if (len < 1e-6) continue;
    const g = new THREE.CylinderGeometry(p.radius, p.radius, len, 8, 1, false).toNonIndexed();
    g.deleteAttribute('uv');
    const mid = pts[i].clone().add(pts[i + 1]).multiplyScalar(0.5);
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), pts[i + 1].clone().sub(pts[i]).normalize());
    g.applyMatrix4(new THREE.Matrix4().compose(mid, q, new THREE.Vector3(1, 1, 1)));
    geos.push(g);
  }
  return geos.length ? mergeGeometries(geos) : null;
}
function capsule(p) {
  const r = p.radius, prof = [[p.x0, 0]];
  for (let k = 1; k < 7; k++) { const t = Math.PI / 2 * k / 6; prof.push([p.x0 + r * (1 - Math.cos(t)), r * Math.sin(t)]); }
  for (let k = 5; k >= 0; k--) { const t = Math.PI / 2 * k / 6; prof.push([p.x1 - r * (1 - Math.cos(t)), r * Math.sin(t)]); }
  prof.push([p.x1, 0]);
  return rev(prof.map(([x, rr]) => [x, Math.max(rr, 1e-3)]), 0, 360, 2, p.centre || [0, 0]);
}
const SHAPES = { ring, frustum, torus, box, panel, tube, capsule };

// ---- scenes ----------------------------------------------------------------------------------------------------------------------------
let renderer, camera, controls;
const sides = { left: null, right: null };
const ghost = new THREE.MeshBasicMaterial({ color: 0x8a9aa8, transparent: true, opacity: 0.07, depthWrite: false, side: THREE.DoubleSide });
const shadowMat = new THREE.MeshBasicMaterial({ color: 0x7fd18b, transparent: true, opacity: 0.12, depthWrite: false, side: THREE.DoubleSide });
const funcMats = new Map();
const funcMat = f => {
  if (!funcMats.has(f)) funcMats.set(f, new THREE.MeshStandardMaterial({ color: FUNC[f] ?? 0xb0b8c0, roughness: 0.65, metalness: 0.1,
                                                                          side: THREE.DoubleSide }));
  return funcMats.get(f);
};

function makeScene(env) {
  const scene = new THREE.Scene();
  scene.environment = env;
  scene.environmentIntensity = 0.35;
  scene.add(new THREE.HemisphereLight(0xb8c4d0, 0x1a1d22, 0.9));
  const sun = new THREE.DirectionalLight(0xfff4e6, 2.2);
  sun.position.set(0.6, 0.8, 0.5);
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0x8aa4c0, 0.5);
  fill.position.set(-0.7, -0.3, -0.6);
  scene.add(fill);
  const root = new THREE.Group();       // centred on the focus, scaled in "fit each side"
  scene.add(root);
  return { scene, root, focusBox: new THREE.Box3(), meshes: 0, error: null };
}
// The shield shadow (P11): a translucent cylinder of the shadow radius from the shield plane aft, in the Blender frame.
function shadow(xAft) {
  const s = data.shadow;
  const g = rev([[xAft, s.radius_m], [s.x_m, s.radius_m], [s.x_m, s.radius_m - 0.01], [xAft, s.radius_m - 0.01]], 0, 360, 4);
  const m = new THREE.Mesh(g, shadowMat);
  m.renderOrder = 2;
  return m;
}

// Right: the blockout, its pieces made once; per pair merged into one mesh per function colour (focus) and one ghost.
let blockParts = null;
function buildBlockout() {
  blockParts = [];
  for (const p of data.parts) {
    const make = SHAPES[p.shape];
    const g = make ? make(p) : null;
    if (g) blockParts.push({ p, g });
  }
}
function showRight(pair) {
  const side = sides.right;
  side.root.clear();
  const frame = new THREE.Group();
  frame.rotation.x = -Math.PI / 2;       // Blender (x, y, z) -> three (x, z, -y)
  side.root.add(frame);
  const all = pair.needed.includes('ALL');
  const byFunc = new Map(), rest = [];
  for (const { p, g } of blockParts) {
    if (all || pair.needed.includes(p.group)) (byFunc.get(p.func) || byFunc.set(p.func, []).get(p.func)).push(g);
    else rest.push(g);
  }
  side.meshes = 0;
  for (const [f, gs] of byFunc) { frame.add(new THREE.Mesh(mergeGeometries(gs), funcMat(f))); side.meshes += gs.length; }
  if (rest.length) { const gm = new THREE.Mesh(mergeGeometries(rest), ghost); gm.renderOrder = 1; frame.add(gm); }
  side.root.position.set(0, 0, 0);
  side.root.updateMatrixWorld(true);
  side.focusBox = new THREE.Box3();
  for (const c of frame.children) if (c.material !== ghost) side.focusBox.expandByObject(c);
  if (pair.id === 'P11') {
    const whole = new THREE.Box3().setFromObject(frame);
    frame.add(shadow(whole.min.x));
  }
  const fn = [...byFunc.keys()];
  $('label-right').textContent = all ? ' whole FDP-1 blockout' : ' ' + pair.needed.map(g => GROUP_NAMES[g] || g).join(', ');
  return fn;
}

// Left: the Explore Ship GLB; each mesh keeps its material in userData and takes the ghost when it is not in the pair's subsystems.
let ship = null, holo = null;
const shipMeshes = [];
async function loadShip() {
  const build = await fetch(VIEWER + 'build.json', { cache: 'no-store' }).then(r => r.ok ? r.json() : null).catch(() => null);
  if (!build?.glb_file) throw new Error('the Explore Ship model is not part of this build');
  holo = await fetch(VIEWER + build.holo_file).then(r => r.ok ? r.json() : null).catch(() => null);
  const draco = new DRACOLoader().setDecoderPath(VIEWER + 'vendor/three/draco/');
  const loader = new GLTFLoader().setDRACOLoader(draco);
  const total = build.glb?.bytes;
  const gltf = await loader.loadAsync(VIEWER + build.glb_file, e => {
    cstatus.textContent = total ? `Loading today's ship… ${Math.min(100, Math.round(100 * e.loaded / total))} %`
                                : `Loading today's ship… ${(e.loaded / 1e6).toFixed(1)} MB`;
  });
  draco.dispose();
  ship = gltf.scene;
  ship.traverse(o => {
    if (!o.isMesh) return;
    for (const m of [].concat(o.material)) m.side = THREE.DoubleSide;
    o.userData.material = o.material;
    let n = o;
    while (n && !n.name.startsWith('WF_')) n = n.parent;
    const c = holo?.nodes?.[n?.name] ?? 'CTX';
    o.userData.sid = Array.isArray(c) ? c[0] : c;
    shipMeshes.push(o);
  });
}
function showLeft(pair) {
  const side = sides.left;
  side.root.clear();
  side.root.position.set(0, 0, 0);
  side.root.scale.setScalar(1);
  if (!ship) {
    $('label-left').textContent = ' not available in this build';
    side.focusBox = new THREE.Box3(new THREE.Vector3(-1, -1, -1), new THREE.Vector3(1, 1, 1));
    return;
  }
  side.root.add(ship);
  const all = pair.current.includes('ALL');
  side.meshes = 0;
  side.root.updateMatrixWorld(true);
  side.focusBox = new THREE.Box3();
  for (const o of shipMeshes) {
    const on = all || pair.current.includes(o.userData.sid);
    o.material = on ? o.userData.material : ghost;
    o.renderOrder = on ? 0 : 1;
    if (on) { side.meshes++; side.focusBox.expandByObject(o); }
  }
  if (side.focusBox.isEmpty()) side.focusBox.setFromObject(ship);
  if (pair.id === 'P11') {
    const frame = new THREE.Group();
    frame.rotation.x = -Math.PI / 2;
    frame.add(shadow(new THREE.Box3().setFromObject(ship).min.x));
    side.root.add(frame);
  }
  const names = all ? ['the whole ship'] : pair.current.map(id => holo?.subsystems?.find(s => s.id === id)?.name || id);
  $('label-left').textContent = ' ' + names.join(', ');
}

// Both sides centred on their focus; one camera. "Fit each side" scales the left so both foci fill their halves.
let radii = { left: 1, right: 1 };
function show(pair) {
  showLeft(pair);
  showRight(pair);
  for (const k of ['left', 'right']) {
    const s = sides[k], c = s.focusBox.getCenter(new THREE.Vector3());
    radii[k] = Math.max(1, s.focusBox.getSize(new THREE.Vector3()).length() / 2);
    s.root.position.copy(c).multiplyScalar(-1);
  }
  applyFit();
  frameAll();
}
function applyFit() {
  const fit = $('fit').checked, k = fit ? radii.right / radii.left : 1;
  const l = sides.left.root, c = sides.left.focusBox.getCenter(new THREE.Vector3());
  l.scale.setScalar(k);
  l.position.copy(c).multiplyScalar(-k);
  const r = fit ? radii.right : Math.max(radii.left, radii.right);
  $('scale').textContent = fit ? `Left enlarged ×${k.toFixed(k < 10 ? 2 : 0)} to fill its half.` : `Same scale. Today's focus spans about ${fmt(2 * radii.left)}, the need about ${fmt(2 * radii.right)}.`;
  return r;
}
const fmt = m => m >= 2000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;
// Camera directions in three axes (bow +X, dorsal +Y, starboard +Z): the default looks down on the ship from aft-starboard
// so that planforms (radiator wings) and lengths both read.
const VIEWS = { threequarter: [-0.5, 0.72, 0.48], side: [0, 0, 1], top: [0, 1, 0.0001], front: [1, 0.08, 0] };
let view = 'threequarter';
function frameAll() {
  const r = $('fit').checked ? radii.right : Math.max(radii.left, radii.right);
  const fov = camera.fov * Math.PI / 180, aspect = Math.min(camera.aspect, 1);
  const d = r / Math.sin(fov / 2) / Math.max(aspect, 0.5) * 0.9;
  const dir = new THREE.Vector3(...VIEWS[view]).normalize();
  controls.target.set(0, 0, 0);
  camera.position.copy(dir.multiplyScalar(d));
  camera.near = Math.max(0.1, d / 2000);
  camera.far = d * 20;
  camera.updateProjectionMatrix();
  controls.update();
  dirty = true;
}

let dirty = true, raf = 0;
function layout() {
  const w = stage.clientWidth, h = stage.clientHeight, stacked = w < 700;
  renderer.setSize(w, h, false);
  stage.classList.toggle('stacked', stacked);
  camera.aspect = stacked ? w / (h / 2) : (w / 2) / h;
  camera.updateProjectionMatrix();
  dirty = true;
  return stacked;
}
function render() {
  raf = requestAnimationFrame(render);
  if (controls.update()) dirty = true;
  if (!dirty) return;
  dirty = false;
  const w = stage.clientWidth, h = stage.clientHeight, stacked = stage.classList.contains('stacked');
  const views = stacked ? [['left', 0, h / 2, w, h / 2], ['right', 0, 0, w, h / 2]] : [['left', 0, 0, w / 2, h], ['right', w / 2, 0, w / 2, h]];
  renderer.setScissorTest(true);
  for (const [k, x, y, vw, vh] of views) {
    renderer.setViewport(x, y, vw, vh);
    renderer.setScissor(x, y, vw, vh);
    renderer.setClearColor(k === 'left' ? 0x07090c : 0x0a0c10);
    renderer.render(sides[k].scene, camera);
  }
}

async function start() {
  gate.hidden = true;
  cstatus.hidden = false;
  cstatus.textContent = 'Starting…';
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, logarithmicDepthBuffer: true });
  } catch (err) {
    cstatus.textContent = 'This browser could not start WebGL, which the 3D comparison needs.';
    cstatus.classList.add('error');
    return;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.autoClear = true;
  const env = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
  sides.left = makeScene(env);
  sides.right = makeScene(env);
  camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100000);
  controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.12;
  controls.screenSpacePanning = true;
  controls.addEventListener('change', () => { dirty = true; });
  layout();
  stage.classList.add('live');
  buildBlockout();
  try {
    await loadShip();
  } catch (err) {
    sides.left.error = String(err.message || err);
  }
  loaded = true;
  cstatus.hidden = !sides.left.error;
  if (sides.left.error) cstatus.textContent = `Today's ship could not load (${sides.left.error}); the right side still shows the need.`;
  show(current);
  render();
  window.compare = { ready: true, pair: () => current.id, select: id => select(id, true), sides, camera, controls, renderer,
                     stats: () => ({ left_meshes: sides.left.meshes, right_parts: sides.right.meshes, left_error: sides.left.error,
                                     calls: renderer.info.render.calls }) };
}

async function init() {
  data = await fetch(DATA).then(r => r.json());
  for (const b of document.querySelectorAll('.pairs button')) b.addEventListener('click', () => select(b.dataset.pair, true));
  select(location.hash.slice(1), false);
  $('load').addEventListener('click', start);
  for (const b of document.querySelectorAll('.views button')) b.addEventListener('click', () => { view = b.dataset.view; if (loaded) frameAll(); });
  $('fit').addEventListener('change', () => { if (loaded) { applyFit(); frameAll(); } });
  window.addEventListener('resize', () => { if (renderer) { layout(); frameAll(); } });
  window.addEventListener('hashchange', () => select(location.hash.slice(1), false));
  window.addEventListener('pagehide', () => { cancelAnimationFrame(raf); renderer?.dispose(); renderer?.forceContextLoss(); });
  window.compare = { ready: false, start };
}
init().catch(err => { $('caption').textContent = `The comparison data could not load: ${err.message || err}`; });
