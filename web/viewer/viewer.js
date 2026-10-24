// WEB-001 browser explorer: the exported COAST snapshot (model/wayfarer.glb), its pick labels (model/nodes.json)
// and its build identity (build.json). Runtime axes: metres, bow +X, dorsal +Y (Blender (x,y,z) -> (x,z,-y)).
// All paths are relative so the site works under any subpath. The viewer computes no spacecraft facts.
// WEB-002: build.json is fetched past the browser cache and names the content-addressed GLB; #view=<preset> or #cam=<x,y,z,tx,ty,tz>
// reopens a camera; ?diag shows frame time, draw calls and transfer sizes; leaving the page releases the WebGL context.
// WEB-003: hologram styles over the same meshes, as presentation only: SUBSYSTEMS (the M5 subsystem hologram: unshaded, additive, rim
// and scan bands in each functional subsystem's overlay colour) and ENGINE (the Blender engine exposition hologram: one colour, rim glow,
// wire edges). Colours and classification come from build.json's holo_file (shots/m5_subsystems.toml, SH_ENGINE_HOLOGRAM).
// WEB-004: style, per-target visibility states and focus are separate (appearance.js resolves every node from them); HYBRID focuses
// what is clicked; ghosts are non-additive and drawn once per pixel, holograms add at most HOLO_LAYERS layers (stencil), so dense
// radiator stacks cannot saturate. Imported materials stay on each mesh as userData.material and are put back by the resolver.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import * as A from './appearance.js';

const canvas = document.getElementById('view');
const status = document.getElementById('status');
const pickBox = document.getElementById('pick');
const list = document.getElementById('assemblies');
const panel = document.getElementById('panel');
const panelToggle = document.getElementById('panel-toggle');
const appearancePanel = document.getElementById('appearance');
const appearanceToggle = document.getElementById('appearance-toggle');
const legend = document.getElementById('legend');
const focusBar = document.getElementById('focusbar');

let renderer;
try {
  // stencil: the ghost and hologram layer limits (WEB-004)
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, logarithmicDepthBuffer: true, stencil: true });
} catch (err) {
  status.textContent = 'This browser could not start WebGL, which the 3D view needs. Enable hardware acceleration or try another browser.';
  status.classList.add('error');
  throw err;
}
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
// Transparent order: by renderOrder (holograms, then ghosts, then outlines); ghosts and holograms nearest first, so the one ghost layer
// and the capped hologram layers a pixel keeps are the front ones; every other transparent surface back to front as three.js does.
renderer.setTransparentSort((a, b) => a.groupOrder - b.groupOrder || a.renderOrder - b.renderOrder
  || (a.material.userData.nearFirst && b.material.userData.nearFirst ? a.z - b.z : b.z - a.z) || a.id - b.id);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x07090c);
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.35;
scene.add(new THREE.HemisphereLight(0xb8c4d0, 0x1a1d22, 0.9));
const sun = new THREE.DirectionalLight(0xfff4e6, 2.2);
sun.position.set(0.6, 0.8, 0.5);
scene.add(sun);
const fill = new THREE.DirectionalLight(0x8aa4c0, 0.5);
fill.position.set(-0.7, -0.3, -0.6);
scene.add(fill);

const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 10000);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.12;
controls.screenSpacePanning = true;
controls.zoomToCursor = true;

let model = null, box = null, radius = 1;
const groups = new Map();            // assembly name -> THREE.Object3D
let labels = {};                     // node -> [component_id, kind, canon_status, geometry_status]
const records = [];                  // one per WF_ node: { node, id, assembly, group, sid, meshes, res }
const byId = new Map();              // node id -> record
const state = A.initialState();
let selected = null;                 // the selected record (picked part)
let scope = 'node';                  // what the pick box's actions apply to: node | group | assembly | subsystem
let cameraHash = 'view=threequarter';
const highlight = new THREE.MeshStandardMaterial({ color: 0x4fb3ff, emissive: 0x0d4a80, roughness: 0.5, metalness: 0.1 });
const BACKGROUND = { standard: 0x07090c, subsystem: 0x020407, engine: 0x01060a, hybrid: 0x04070b };

// ---- materials ---------------------------------------------------------------------------------------------------------------------
// HOLOGRAM, subsystem tint: the Godot M5 shader (m5_holo.gd): tint * energy * (0.3 + 1.7 rim^2) * scan, additive, depth never written.
// HOLOGRAM, engine tint: the Blender REP_HOLOGRAM material (shot_tools.material): emission 1.6 x tint, alpha 0.12 + 0.55 facing.
// GHOST: low-opacity normal blending in one tint, with an optional rim (silhouette) term; one ghost layer per pixel.
// All three carry the logarithmic depth chunks the renderer uses, so they test depth against the solid meshes correctly.
const VERTEX = `
#include <common>
#include <logdepthbuf_pars_vertex>
varying vec3 vWorld; varying vec3 vNormal; varying vec3 vView;
void main() {
  vec4 w = modelMatrix * vec4(position, 1.0);
  vWorld = w.xyz;
  vNormal = normalize(mat3(modelMatrix) * normal);
  vView = cameraPosition - w.xyz;
  gl_Position = projectionMatrix * viewMatrix * w;
  #include <logdepthbuf_vertex>
}`;
const HOLO_FRAGMENT = `
#include <logdepthbuf_pars_fragment>
uniform vec3 tint; uniform float energy; uniform float engine;
varying vec3 vWorld; varying vec3 vNormal; varying vec3 vView;
void main() {
  #include <logdepthbuf_fragment>
  float facing = 1.0 - abs(dot(normalize(vNormal), normalize(vView)));
  if (engine > 0.5) {
    gl_FragColor = vec4(tint * 1.6 * energy, clamp(0.12 + 0.55 * pow(facing, 1.5), 0.0, 1.0));
  } else {
    float scan = 0.88 + 0.12 * step(0.5, fract(vWorld.y * 1.5));
    gl_FragColor = vec4(tint * energy * (0.3 + 1.7 * facing * facing) * scan, 1.0);
  }
  #include <colorspace_fragment>
}`;
const GHOST_FRAGMENT = `
#include <logdepthbuf_pars_fragment>
uniform vec3 tint; uniform float strength; uniform float outlines;
varying vec3 vWorld; varying vec3 vNormal; varying vec3 vView;
void main() {
  #include <logdepthbuf_fragment>
  float facing = 1.0 - abs(dot(normalize(vNormal), normalize(vView)));
  float shape = outlines > 0.5 ? 0.35 + 2.6 * facing * facing * facing : 1.0;
  gl_FragColor = vec4(tint, clamp(strength * shape, 0.0, 0.6));
  #include <colorspace_fragment>
}`;
const GHOST_TINT = [0.55, 0.62, 0.70];   // m5_holo.gd's ghost tint
const HOLO_LAYERS = 2;                   // hologram layers a pixel may add (stencil count, low 7 bits; measured: 3 still flattens the radiator stack)
const GHOST_BIT = 0x80;                  // stencil bit: this pixel already has its ghost layer
const ENERGY = { overview: 0.16, subject: 0.55, picked: 0.9 };   // m5_holo.gd's overview and subject energies
let holo = null;                         // the holo_file: subsystems, node -> subsystem id or [id, colour], engine colour
let holoLoading = null;
const holoMaterials = new Map();         // "blend|r,g,b|role" -> ShaderMaterial
const ghostMaterials = new Map();        // "r,g,b" -> ShaderMaterial (strength and outlines uniforms shared through updateGhosts)
const edgeGeometry = new Map();          // mesh geometry -> its EdgesGeometry (engine wire edges and the selection outline; made once)
let edgeMaterial = null;
const outlineMaterial = new THREE.LineBasicMaterial({ color: 0xffc060, transparent: true, opacity: 0.9, depthWrite: false, toneMapped: false });
let outlineLines = [];

const srgb = rgb => new THREE.Color().setRGB(...rgb, THREE.SRGBColorSpace);

function holoMaterial(rgb, engine, role) {
  const key = `${engine ? 'e' : 's'}|${rgb.join(',')}|${role}`;
  if (!holoMaterials.has(key)) {
    const m = new THREE.ShaderMaterial({
      uniforms: { tint: { value: srgb(rgb) }, energy: { value: engine ? 1.0 : ENERGY[role] }, engine: { value: engine ? 1 : 0 } },
      vertexShader: VERTEX, fragmentShader: HOLO_FRAGMENT, side: THREE.DoubleSide, transparent: true, depthWrite: false,
      blending: engine ? THREE.NormalBlending : THREE.AdditiveBlending, toneMapped: false,
      stencilWrite: true, stencilRef: HOLO_LAYERS, stencilFunc: THREE.GreaterStencilFunc, stencilFuncMask: 0x7f,
      stencilWriteMask: 0x7f, stencilZPass: THREE.IncrementStencilOp,
    });
    m.userData = { nearFirst: true };
    holoMaterials.set(key, m);
  }
  return holoMaterials.get(key);
}

function ghostMaterial(rgb) {
  const key = rgb.join(',');
  if (!ghostMaterials.has(key)) {
    const m = new THREE.ShaderMaterial({
      uniforms: { tint: { value: srgb(rgb) }, strength: { value: state.ghost }, outlines: { value: state.outlines ? 1 : 0 } },
      vertexShader: VERTEX, fragmentShader: GHOST_FRAGMENT, side: THREE.DoubleSide, transparent: true, depthWrite: false,
      toneMapped: false, stencilWrite: true, stencilRef: GHOST_BIT, stencilFunc: THREE.NotEqualStencilFunc, stencilFuncMask: GHOST_BIT,
      stencilWriteMask: GHOST_BIT, stencilZPass: THREE.ReplaceStencilOp,
    });
    m.userData = { nearFirst: true };
    ghostMaterials.set(key, m);
  }
  return ghostMaterials.get(key);
}

function updateGhosts() {
  for (const m of ghostMaterials.values()) { m.uniforms.strength.value = state.ghost; m.uniforms.outlines.value = state.outlines ? 1 : 0; }
}

function classOf(node) {
  const c = holo?.nodes[node] ?? 'CTX';
  const sid = Array.isArray(c) ? c[0] : c;
  const sub = holo?.subsystems.find(s => s.id === sid);
  return { sid, sub, rgb: Array.isArray(c) ? c[1] : sub ? sub.color : [0.3, 0.31, 0.33] };
}

// The material of one mesh for its node's resolved state.
function materialFor(r, res, mesh) {
  const picked = selected === r && !state.focus;      // a plain selection (no focus): the WEB-001/003 highlight
  if (res.state === 'SOLID') return picked && state.style !== 'hybrid' ? highlight : mesh.userData.material;
  if (res.state === 'GHOST') return ghostMaterial(state.style === 'engine' ? holo.engine_color : GHOST_TINT);
  const role = picked ? 'picked' : state.focus || res.why.endsWith('override') ? 'subject' : 'overview';
  if (res.tint === 'engine') return holoMaterial(picked ? [0.85, 0.95, 1.0] : holo.engine_color, true, role);
  return holoMaterial(picked ? [1, 1, 1] : classOf(r.id).rgb, false, role);
}

// Engine wire edges: only on meshes drawn as an engine-tint hologram, made the first time a mesh needs them.
function setEdges(mesh, on) {
  if (!on && !mesh.userData.edges) return;
  if (!mesh.userData.edges) {
    edgeMaterial ??= new THREE.LineBasicMaterial({ color: srgb(holo.engine_color), transparent: true, opacity: 0.35, depthWrite: false,
                                                    blending: THREE.AdditiveBlending, toneMapped: false });
    if (!edgeGeometry.has(mesh.geometry)) edgeGeometry.set(mesh.geometry, new THREE.EdgesGeometry(mesh.geometry, 30));
    const line = new THREE.LineSegments(edgeGeometry.get(mesh.geometry), edgeMaterial);
    line.name = 'holo_edges';
    line.raycast = () => {};       // picking stays on the meshes
    mesh.add(line);
    mesh.userData.edges = line;
  }
  mesh.userData.edges.visible = on;
}

// The selection outline: the selected part's feature edges, drawn over whatever state it has.
function setOutline() {
  for (const l of outlineLines) l.removeFromParent();
  outlineLines = [];
  if (!selected) return;
  for (const mesh of selected.meshes) {
    if (!edgeGeometry.has(mesh.geometry)) edgeGeometry.set(mesh.geometry, new THREE.EdgesGeometry(mesh.geometry, 30));
    const line = new THREE.LineSegments(edgeGeometry.get(mesh.geometry), outlineMaterial);
    line.name = 'selection_outline';
    line.renderOrder = 3;
    line.raycast = () => {};
    mesh.add(line);
    outlineLines.push(line);
  }
}

// ---- the resolver applied to the scene ---------------------------------------------------------------------------------------------
let appliedStyle = 'standard';         // the style the scene shows now (state.style changes before the colours arrive)
function applyAppearance() {
  if (!model) return;
  appliedStyle = state.style;
  for (const r of records) {
    const res = r.res = A.resolve(state, r, A.inFocus(state, r));
    const hidden = res.state === 'HIDDEN';
    for (const mesh of r.meshes) {
      mesh.visible = mesh.userData.visible && !hidden;
      if (hidden) continue;
      mesh.material = materialFor(r, res, mesh);
      mesh.renderOrder = res.state === 'GHOST' ? 2 : res.state === 'HOLOGRAM' ? 1 : 0;
      setEdges(mesh, res.state === 'HOLOGRAM' && res.tint === 'engine');
    }
  }
  updateGhosts();
  setOutline();
  scene.background.set(BACKGROUND[state.style]);
  syncControls();
  writeHash();
}

function needsHolo() {
  return state.style !== 'standard' || state.focus || state.overrides.size > 0;
}

async function ensureHolo() {
  if (holo) return true;
  holoLoading ??= (async () => {
    status.hidden = false; status.textContent = 'Loading hologram colours…';
    const data = await fetch(buildInfo?.holo_file || 'model/holo.json').then(r => r.ok ? r.json() : null).catch(() => null);
    status.hidden = true;
    if (!data) { status.hidden = false; status.textContent = 'The hologram colours could not be loaded.'; status.classList.add('error'); return false; }
    holo = data;
    for (const r of records) { r.sid = classOf(r.id).sid; r.group = holo.groups?.[r.id] || ''; }
    return true;
  })();
  return holoLoading;
}

// Every change goes through here: mutate the state, fetch the colours if the new state draws a hologram or ghost, resolve, render.
async function update(mutate) {
  mutate(state);
  if (needsHolo() && !(await ensureHolo())) {
    Object.assign(state, A.initialState());
  }
  if (holo) pruneMissing();
  applyAppearance();
}

// A bookmarked group or subsystem that this build no longer has (a later model) is dropped instead of focusing nothing.
function pruneMissing() {
  const has = (kind, id) => records.some(r => (kind === 'group' ? r.group : r.sid) === id);
  if (state.focus && ['group', 'subsystem'].includes(state.focus.kind) && !has(state.focus.kind, state.focus.id)) state.focus = null;
  for (const k of [...state.overrides.keys()]) {
    if ((k.startsWith('g:') && !has('group', k.slice(2))) || (k.startsWith('s:') && !has('subsystem', k.slice(2)))) state.overrides.delete(k);
  }
}

// ---- controls ----------------------------------------------------------------------------------------------------------------------
// Blender suffixes the export groups (.001); the loader drops the dot.
const pretty = name => name.replace(/^Assembly_/, '').replace(/[._]?\d{3}$/, '').split('_')
  .map((w, i) => i ? w.toLowerCase() : w[0] + w.slice(1).toLowerCase()).join(' ');

function targetName(kind, id) {
  if (kind === 'assembly') return pretty(id);
  if (kind === 'group') {             // WF.RADIATOR.01 -> Radiator 01, WF.DRIVE.NODE.DRIVE_NOZZLE_1 -> Drive nozzle 1
    const parts = id.replace(/^WF\./, '').split('.');
    const tail = parts.pop();
    return /^\d+$/.test(tail) && parts.length ? `${pretty(parts.pop())} ${tail}` : pretty(tail);
  }
  if (kind === 'subsystem') { const s = holo?.subsystems.find(x => x.id === id); return s ? `${s.id} ${s.name}` : id; }
  return labels[id]?.[0] || id;
}

// The target the pick box's actions apply to: the selected part, its assembly or its subsystem.
function scopeTarget() {
  if (!selected) return null;
  if (scope === 'group' && selected.group) return { kind: 'group', id: selected.group, key: 'g:' + selected.group };
  if (scope === 'assembly' && selected.assembly) return { kind: 'assembly', id: selected.assembly, key: 'a:' + selected.assembly };
  if (scope === 'subsystem' && holo) return { kind: 'subsystem', id: selected.sid, key: 's:' + selected.sid };
  return { kind: 'node', id: selected.id, key: 'n:' + selected.id };
}

function syncControls() {
  for (const b of document.querySelectorAll('[data-style]')) b.setAttribute('aria-pressed', String(b.dataset.style === state.style));
  const look = A.effectiveLook(state);
  for (const b of document.querySelectorAll('[data-look]')) b.setAttribute('aria-pressed', String(b.dataset.look === look));
  for (const b of document.querySelectorAll('[data-ctx]')) b.setAttribute('aria-pressed', String(b.dataset.ctx === state.contextLook));
  const slider = document.getElementById('ghost');
  slider.value = Math.round(state.ghost * 100);
  document.getElementById('ghost-value').textContent = `${slider.value} %`;
  document.getElementById('outlines').checked = state.outlines;
  for (const sel of list.querySelectorAll('select')) sel.value = state.overrides.get('a:' + sel.dataset.assembly) || '';
  focusBar.hidden = !state.focus;
  if (state.focus) document.getElementById('focus-name').textContent = targetName(state.focus.kind, state.focus.id);
  buildLegend();
  showPick();
}

function showPick() {
  if (!selected) { pickBox.hidden = true; return; }
  const r = selected;
  const [component, kind, canon, geometry] = labels[r.id] || [r.id, '', '', ''];
  pickBox.innerHTML = '';
  const title = document.createElement('b');
  title.textContent = component;
  const info = document.createElement('span');
  const sub = holo ? classOf(r.id).sub : null;
  info.textContent = [pretty(r.assembly), r.group && targetName('group', r.group), kind, canon && `canon ${canon}`, geometry && `geometry ${geometry}`,
                      sub && `${sub.id} ${sub.name} (overlay colour)`, r.res && `shown ${r.res.state.toLowerCase()} (${r.res.why})`]
    .filter(Boolean).join(' · ');
  const scopes = document.createElement('div');
  scopes.className = 'chips';
  scopes.setAttribute('role', 'group');
  scopes.setAttribute('aria-label', 'Apply to');
  for (const [k, label] of [['node', 'Part'], ['group', 'Group'], ['assembly', 'Assembly'], ['subsystem', 'Subsystem']]) {
    if ((k === 'subsystem' && !holo) || (k === 'group' && !r.group)) continue;
    scopes.append(button(label, () => { scope = k; showPick(); }, { pressed: scope === k, data: { scope: k } }));
  }
  const t = scopeTarget();
  const current = state.overrides.get(t.key);
  const actions = document.createElement('div');
  actions.className = 'chips actions';
  const focused = state.focus && state.focus.kind === t.kind && state.focus.id === t.id;
  actions.append(
    button(focused ? 'Unfocus' : 'Focus', () => update(s => { s.focus = focused ? null : { kind: t.kind, id: t.id }; }), { data: { act: 'focus' } }),
    button('Frame', frameSelection, { data: { act: 'frame' }, title: 'Frame the selection (F)' }),
    ...['SOLID', 'HOLOGRAM', 'GHOST', 'HIDDEN'].map(st => button({ SOLID: 'Solid', HOLOGRAM: 'Holo', GHOST: 'Ghost', HIDDEN: 'Hide' }[st],
      () => update(s => { s.overrides.set(t.key, st); if (st === 'HIDDEN' && t.kind === 'node') selected = null; }),
      { pressed: current === st, data: { act: st.toLowerCase() } })),
    button('Restore', () => update(s => { s.overrides.delete(t.key); }), { data: { act: 'restore' }, disabled: !current }));
  pickBox.append(title, info, scopes, actions);
  pickBox.hidden = false;
}

function button(text, onClick, { pressed, data = {}, title, disabled } = {}) {
  const b = document.createElement('button');
  b.textContent = text;
  if (pressed !== undefined) b.setAttribute('aria-pressed', String(pressed));
  for (const [k, v] of Object.entries(data)) b.dataset[k] = v;
  if (title) b.title = title;
  if (disabled) b.disabled = true;
  b.addEventListener('click', onClick);
  return b;
}

// The subsystem legend (Subsystems and Hybrid): each subsystem's overlay colour, node count and maturity; a click focuses it.
function buildLegend() {
  const drawerOpen = window.matchMedia('(max-width: 640px)').matches && (!panel.hidden || !appearancePanel.hidden);
  legend.hidden = !holo || !['subsystem', 'hybrid'].includes(state.style) || drawerOpen;   // a phone shows one panel at a time
  if (legend.hidden) return;
  legend.querySelector('#legend-toggle').setAttribute('aria-expanded', String(!legend.classList.contains('collapsed')));
  const counts = {};
  for (const r of records) counts[r.sid] = (counts[r.sid] || 0) + 1;
  const ul = legend.querySelector('ul');
  ul.innerHTML = '';
  for (const s of holo.subsystems) {
    if (!counts[s.id]) continue;
    const li = document.createElement('li');
    const on = state.focus?.kind === 'subsystem' && state.focus.id === s.id;
    const b = button('', () => update(st => { st.focus = on ? null : { kind: 'subsystem', id: s.id }; }), { pressed: on, data: { sid: s.id } });
    b.title = s.maturity || s.name;
    const sw = document.createElement('i');
    sw.style.background = `rgb(${s.color.map(v => Math.round(255 * v)).join(',')})`;
    const name = document.createElement('span');
    name.textContent = `${s.id === 'CTX' ? '' : s.id + ' '}${s.name}`;
    const n = document.createElement('span');
    n.className = 'count'; n.textContent = counts[s.id];
    b.append(sw, name, n);
    li.append(b); ul.append(li);
  }
}

// Assembly visibility: each assembly's state (Auto follows style and focus), stable across selection and camera changes.
function buildPanel() {
  list.innerHTML = '';
  for (const [name] of [...groups].sort((a, b) => pretty(a[0]).localeCompare(pretty(b[0])))) {
    const count = records.filter(r => r.assembly === name).length;
    const li = document.createElement('li');
    const label = document.createElement('label');
    const text = document.createElement('span');
    text.textContent = pretty(name);
    const n = document.createElement('span');
    n.className = 'count'; n.textContent = count;
    const sel = document.createElement('select');
    sel.dataset.assembly = name;
    sel.setAttribute('aria-label', `${pretty(name)} appearance`);
    for (const [v, t] of [['', 'Auto'], ['SOLID', 'Solid'], ['HOLOGRAM', 'Hologram'], ['GHOST', 'Ghost'], ['HIDDEN', 'Hidden']]) {
      const o = document.createElement('option'); o.value = v; o.textContent = t; sel.append(o);
    }
    sel.addEventListener('change', () => update(s => {
      if (sel.value) s.overrides.set('a:' + name, sel.value); else s.overrides.delete('a:' + name);
      if (sel.value === 'HIDDEN' && selected?.assembly === name) selected = null;
    }));
    label.append(text, n, sel); li.append(label); list.append(li);
  }
}

// Show all: every HIDDEN override is lifted; other states stay. Reset appearance: the initial state (Standard, no focus, no override,
// default ghost settings), no selection, every mesh back on its imported material and visibility; the camera stays where it is.
function showAll() {
  update(s => { for (const [k, v] of [...s.overrides]) if (v === 'HIDDEN') s.overrides.delete(k); });
}
function resetAppearance() {
  selected = null;
  scope = 'node';
  Object.assign(state, A.initialState());
  applyAppearance();
  for (const r of records) for (const mesh of r.meshes) {
    if (mesh.userData.edges) { mesh.userData.edges.removeFromParent(); delete mesh.userData.edges; }
  }
  for (const g of edgeGeometry.values()) g.dispose();
  edgeGeometry.clear();
}

// ---- camera ------------------------------------------------------------------------------------------------------------------------
// Camera views: direction from the target to the camera and the screen-up vector, in runtime axes.
const VIEWS = {
  threequarter: { dir: [0.75, 0.45, 0.85], up: [0, 1, 0] },
  side:         { dir: [0, 0, 1],          up: [0, 1, 0] },
  top:          { dir: [0, 1, 0.0001],     up: [0, 1, 0] },
  front:        { dir: [1, 0, 0],          up: [0, 1, 0] },
  aft:          { dir: [-1, 0, 0],         up: [0, 1, 0] },
};

// Fit a box along a view direction: its projection on the camera's right and up axes fills the view.
function fitBox(target, dir, up) {
  // Drop the damping's leftover motion so the view lands exactly.
  const damping = controls.enableDamping;
  controls.enableDamping = false;
  controls.update();
  const centre = target.getCenter(new THREE.Vector3());
  const right = new THREE.Vector3().crossVectors(up, dir).normalize();
  const trueUp = new THREE.Vector3().crossVectors(dir, right).normalize();
  let w = 0, h = 0, d = 0;
  for (let i = 0; i < 8; i++) {
    const c = new THREE.Vector3(i & 1 ? target.max.x : target.min.x, i & 2 ? target.max.y : target.min.y, i & 4 ? target.max.z : target.min.z).sub(centre);
    w = Math.max(w, Math.abs(c.dot(right))); h = Math.max(h, Math.abs(c.dot(trueUp))); d = Math.max(d, c.dot(dir));
  }
  const vfov = THREE.MathUtils.degToRad(camera.fov) / 2;
  const hfov = Math.atan(Math.tan(vfov) * camera.aspect);
  const dist = 1.08 * Math.max(h / Math.tan(vfov), w / Math.tan(hfov)) + d;
  camera.up.copy(up);
  camera.position.copy(centre).addScaledVector(dir, dist);
  controls.target.copy(centre);
  camera.near = Math.max(0.05, Math.min(radius / 2000, dist / 200));
  camera.far = dist + radius * 4;
  camera.updateProjectionMatrix();
  controls.update();
  controls.enableDamping = damping;
}

function frame(viewName = 'threequarter') {
  if (!box) return;
  const view = VIEWS[viewName] || VIEWS.threequarter;
  fitBox(box, new THREE.Vector3(...view.dir).normalize(), new THREE.Vector3(...view.up));
  for (const b of document.querySelectorAll('[data-view]')) b.setAttribute('aria-pressed', String(b.dataset.view === viewName));
  cameraHash = `view=${viewName}`;
  writeHash();
}

// Frame selection: the focus subject, else the selected part (or its scope), from the current viewing direction. Never automatic.
function frameSelection() {
  const t = state.focus || scopeTarget();
  if (!t) return;
  const target = new THREE.Box3();
  for (const r of records) {
    if (!A.inFocus({ focus: t }, r) || r.res?.state === 'HIDDEN') continue;
    for (const mesh of r.meshes) target.expandByObject(mesh);
  }
  if (target.isEmpty()) return;
  fitBox(target, camera.position.clone().sub(controls.target).normalize(), camera.up.clone());
  bookmark();
}

// The bookmark: the camera part first (view= or cam=, as WEB-002/003 links have it), then the appearance state without defaults.
function writeHash() {
  const rest = A.encode(state);
  history.replaceState(null, '', `#${cameraHash}${rest ? '&' + rest : ''}`);
}

// Camera bookmarks: the preset name, or the exact camera position and target (metres, runtime axes) written after each drag.
function bookmark() {
  const r = v => v.toArray().map(x => +x.toFixed(2)).join(',');
  cameraHash = `cam=${r(camera.position)},${r(controls.target)}`;
  writeHash();
  for (const b of document.querySelectorAll('[data-view]')) b.setAttribute('aria-pressed', 'false');
}
function openBookmark() {
  const view = /view=(\w+)/.exec(location.hash);
  const cam = /cam=([-\d.,e]+)/.exec(location.hash);
  const v = cam && cam[1].split(',').map(Number);
  // A focus or state whose target is not in this build is dropped (groups and subsystems are checked once the colours are in).
  const asked = A.decode(location.hash, (kind, id) => kind === 'node' ? byId.has(id) : kind === 'assembly' ? groups.has(id) : true);
  if (v && v.length === 6 && v.every(Number.isFinite)) {
    frame('threequarter');
    camera.position.set(v[0], v[1], v[2]);
    controls.target.set(v[3], v[4], v[5]);
    const damping = controls.enableDamping;
    controls.enableDamping = false; controls.update(); controls.enableDamping = damping;
    cameraHash = `cam=${cam[1]}`;
  } else {
    frame(view && VIEWS[view[1]] ? view[1] : 'threequarter');
  }
  return asked;
}
controls.addEventListener('end', bookmark);

function resize() {
  const w = window.innerWidth, h = window.innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}

function nodeOf(object) {
  for (let o = object; o; o = o.parent) if (o.name.startsWith('WF_')) return o;
  return null;
}
function assemblyOf(object) {
  for (let o = object; o; o = o.parent) if (o.name.startsWith('Assembly_')) return o.name;
  return '';
}

// ---- picking -----------------------------------------------------------------------------------------------------------------------
// Picking policy: hidden meshes are never hit. With a focus, the nearest SOLID or HOLOGRAM hit wins over ghosts in front of it, so the
// faint context never steals the click from the visible subject; a ghost is picked only where the ray meets nothing but ghosts.
// In Hybrid a pick also focuses the target in the current scope; elsewhere it only selects. A click on empty space clears the selection.
const raycaster = new THREE.Raycaster();
const visibleChain = o => { for (; o; o = o.parent) if (!o.visible) return false; return true; };
function pickAt(x, y) {
  const ndc = new THREE.Vector2((x / window.innerWidth) * 2 - 1, -(y / window.innerHeight) * 2 + 1);
  raycaster.setFromCamera(ndc, camera);
  const hits = raycaster.intersectObject(model, true).filter(h => h.object.isMesh && visibleChain(h.object));
  const recordOf = h => byId.get(nodeOf(h.object)?.name);
  const hit = hits.find(h => recordOf(h)?.res?.state !== 'GHOST') || hits[0];
  return hit ? recordOf(hit) : null;
}
function select(r) {
  selected = r || null;
  if (!selected) { applyAppearance(); return; }     // the highlight and outline go with the selection
  if (state.style === 'hybrid') {
    const t = scopeTarget();
    update(s => { s.focus = { kind: t.kind, id: t.id }; });
  } else {
    applyAppearance();
  }
}
let down = null;
canvas.addEventListener('pointerdown', e => { down = { x: e.clientX, y: e.clientY, t: performance.now() }; });
canvas.addEventListener('pointerup', e => {
  if (!down || !model) return;
  const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y);
  const quick = performance.now() - down.t < 500;
  down = null;
  if (moved > 6 || !quick) return;
  select(pickAt(e.clientX, e.clientY));
});

// The legend opens with the Subsystems style and starts collapsed in Hybrid, where the part on screen matters more.
function setStyleLegend(name) {
  if (name === 'subsystem' && !window.matchMedia('(max-width: 640px)').matches) legend.classList.remove('collapsed');
  if (name === 'hybrid') legend.classList.add('collapsed');
  return update(s => { s.style = name; });
}

// ---- page controls -----------------------------------------------------------------------------------------------------------------
// One drawer at a time, so a phone keeps the ship in view.
function openDrawer(which) {
  for (const [p, t] of [[panel, panelToggle], [appearancePanel, appearanceToggle]]) {
    const open = p === which && p.hidden;
    p.hidden = !open;
    t.setAttribute('aria-expanded', String(open));
  }
  if (which && !which.hidden && window.matchMedia('(max-width: 640px)').matches) legend.classList.add('collapsed');
  buildLegend();
}
panelToggle.addEventListener('click', () => openDrawer(panel));
appearanceToggle.addEventListener('click', () => openDrawer(appearancePanel));
document.getElementById('show-all').addEventListener('click', showAll);
document.getElementById('show-all-2').addEventListener('click', showAll);
document.getElementById('reset-appearance').addEventListener('click', resetAppearance);
document.getElementById('whole-ship').addEventListener('click', () => update(s => { s.focus = null; }));
document.getElementById('focus-frame').addEventListener('click', frameSelection);
for (const b of document.querySelectorAll('[data-style]')) b.addEventListener('click', () => setStyleLegend(b.dataset.style));
for (const b of document.querySelectorAll('[data-look]')) b.addEventListener('click', () => update(s => { s.focusLook = b.dataset.look; }));
for (const b of document.querySelectorAll('[data-ctx]')) b.addEventListener('click', () => update(s => { s.contextLook = b.dataset.ctx; }));
document.getElementById('ghost').addEventListener('input', e => {
  state.ghost = Math.min(A.GHOST_MAX, Number(e.target.value) / 100);
  updateGhosts();
  document.getElementById('ghost-value').textContent = `${e.target.value} %`;
  writeHash();
});
document.getElementById('outlines').addEventListener('change', e => { state.outlines = e.target.checked; updateGhosts(); writeHash(); });
document.getElementById('legend-all').addEventListener('click', () => update(s => { s.focus = null; }));
document.getElementById('legend-toggle').addEventListener('click', () => { legend.classList.toggle('collapsed'); buildLegend(); });
if (window.matchMedia('(max-width: 640px)').matches) legend.classList.add('collapsed');
for (const b of document.querySelectorAll('[data-view]')) {
  b.addEventListener('click', () => frame(b.dataset.view === 'reset' ? 'threequarter' : b.dataset.view));
}
window.addEventListener('keydown', e => {
  if (e.target.closest('input, select') || e.ctrlKey || e.metaKey || e.altKey) return;
  const keys = { '1': 'side', '2': 'top', '3': 'threequarter', '4': 'front', '5': 'aft', Home: 'threequarter' };
  if (keys[e.key]) frame(keys[e.key]);
  if (e.key === 'Escape') {
    if (selected) select(null); else if (state.focus) update(s => { s.focus = null; });
  }
  const styles = { s: 'standard', h: 'subsystem', e: 'engine', x: 'hybrid' };
  const k = e.key.toLowerCase();
  if (styles[k]) setStyleLegend(styles[k]);
  if (k === 'f') frameSelection();
});
window.addEventListener('resize', () => { resize(); });

function showBuild(build) {
  const el = document.getElementById('build');
  if (!build) return;
  const rev = (build.git_revision || '').slice(0, 7);
  const link = document.createElement('a');
  link.href = `https://github.com/densho-media/ignition-wayfarer/commit/${build.git_revision}`;
  link.target = '_blank'; link.rel = 'noopener';
  link.textContent = rev + (build.git_dirty ? '+dirty' : '');
  el.append('Build ', link, ` · ${(build.built_utc || '').slice(0, 10)} · ${build.preset} · ${(build.triangles || 0).toLocaleString('en')} tris`);
}

let buildInfo = null;
async function load() {
  const build = buildInfo = await fetch('build.json', { cache: 'no-store' }).then(r => r.ok ? r.json() : null).catch(() => null);
  const nodes = await fetch(build?.nodes_file || 'model/nodes.json').then(r => r.ok ? r.json() : {}).catch(() => ({}));
  labels = nodes;
  showBuild(build);
  const draco = new DRACOLoader().setDecoderPath('vendor/three/draco/');
  const loader = new GLTFLoader().setDRACOLoader(draco);
  // Pages serves the GLB gzip-compressed: e.total is the compressed size, e.loaded counts unpacked bytes.
  const total = build?.glb?.bytes;
  const gltf = await loader.loadAsync(build?.glb_file || 'model/wayfarer.glb', e => {
    if (total) status.textContent = `Loading model… ${Math.min(100, Math.round(100 * e.loaded / total))} %`;
    else status.textContent = `Loading model… ${(e.loaded / 1e6).toFixed(1)} MB`;
  });
  draco.dispose();
  model = gltf.scene;
  model.traverse(o => {
    if (o.name.startsWith('Assembly_') && !groups.has(o.name)) groups.set(o.name, o);
    if (o.isMesh) {
      for (const m of [].concat(o.material)) m.side = THREE.DoubleSide;   // the export turns back-face culling off
      o.userData.material = o.material;
      o.userData.visible = o.visible;
      const node = nodeOf(o);
      const id = node ? node.name : o.name;
      if (!byId.has(id)) {
        const r = { node, id, assembly: assemblyOf(o), group: '', sid: 'CTX', meshes: [], res: null };
        byId.set(id, r);
        records.push(r);
      }
      byId.get(id).meshes.push(o);
    }
  });
  scene.add(model);
  box = new THREE.Box3().setFromObject(model);
  radius = box.getSize(new THREE.Vector3()).length() / 2;
  buildPanel();
  const asked = openBookmark();
  status.hidden = true;
  await update(s => Object.assign(s, asked));
  stats.ready_ms = Math.round(performance.now());
  window.wayfarer = { model, groups, camera, controls, frame, build, box, renderer, stats, records, byId, state,   // for inspection and the checks
                      style: () => appliedStyle, select: node => select(node ? byId.get(node.name || node) : null), update, pickAt,
                      setStyle: setStyleLegend, resetAppearance, showAll, frameSelection,
                      setScope: k => { scope = k; showPick(); }, holo: () => holo, selected: () => selected,
                      recordOf: o => byId.get(nodeOf(o)?.name), srgb, THREE };
}

// Diagnostics (always measured, shown with ?diag): frame time over the last 120 frames, draw calls, GPU objects and transfer sizes.
const stats = { ready_ms: null, frame_ms: [], calls: 0, triangles: 0 };
const diag = document.getElementById('diag');
if (new URLSearchParams(location.search).has('diag')) diag.hidden = false;
let last = performance.now(), shown = 0;
function measure() {
  const now = performance.now();
  stats.frame_ms.push(now - last); last = now;
  if (stats.frame_ms.length > 120) stats.frame_ms.shift();
  stats.calls = renderer.info.render.calls; stats.triangles = renderer.info.render.triangles;
  if (diag.hidden || now - shown < 500) return;
  shown = now;
  const f = [...stats.frame_ms].sort((a, b) => a - b);
  const mean = f.reduce((a, b) => a + b, 0) / f.length;
  const transfer = performance.getEntriesByType('resource').reduce((a, e) => a + (e.transferSize || 0), 0)
    + (performance.getEntriesByType('navigation')[0]?.transferSize || 0);
  const heap = performance.memory ? `${(performance.memory.usedJSHeapSize / 1e6).toFixed(0)} MB JS heap\n` : '';
  diag.textContent = `${(1000 / mean).toFixed(0)} fps · ${mean.toFixed(1)} ms mean · ${f[Math.floor(f.length * 0.95)].toFixed(1)} ms p95\n`
    + `${stats.calls} draw calls · ${(stats.triangles / 1e6).toFixed(2)} M tris\n`
    + `${renderer.info.memory.geometries} geometries · ${renderer.info.memory.textures} textures · ${renderer.info.programs.length} programs\n`
    + heap + `${(transfer / 1e6).toFixed(1)} MB transferred · ready ${stats.ready_ms ?? '–'} ms`;
}

// Leaving releases the GPU context at once instead of waiting for garbage collection; a page restored from the back-forward cache reloads.
window.addEventListener('pagehide', () => { renderer.setAnimationLoop(null); renderer.dispose(); renderer.forceContextLoss(); });
window.addEventListener('pageshow', e => { if (e.persisted) location.reload(); });

resize();
renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); measure(); });
load().catch(err => {
  console.error(err);
  status.textContent = `The model could not be loaded: ${err.message || err}`;
  status.classList.add('error');
});
