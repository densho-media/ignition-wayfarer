// WEB-001 browser explorer: the exported COAST snapshot (model/wayfarer.glb), its pick labels (model/nodes.json)
// and its build identity (build.json). Runtime axes: metres, bow +X, dorsal +Y (Blender (x,y,z) -> (x,z,-y)).
// All paths are relative so the site works under any subpath. The viewer computes no spacecraft facts.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const canvas = document.getElementById('view');
const status = document.getElementById('status');
const pickBox = document.getElementById('pick');
const list = document.getElementById('assemblies');
const panel = document.getElementById('panel');
const panelToggle = document.getElementById('panel-toggle');

let renderer;
try {
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, logarithmicDepthBuffer: true });
} catch (err) {
  status.textContent = 'This browser could not start WebGL, which the 3D view needs. Enable hardware acceleration or try another browser.';
  status.classList.add('error');
  throw err;
}
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;

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
let selected = null;                 // { node, materials: Map<mesh, material> }
const highlight = new THREE.MeshStandardMaterial({ color: 0x4fb3ff, emissive: 0x0d4a80, roughness: 0.5, metalness: 0.1 });

// Blender suffixes the export groups (.001); the loader drops the dot.
const pretty = name => name.replace(/^Assembly_/, '').replace(/[._]?\d{3}$/, '').split('_')
  .map((w, i) => i ? w.toLowerCase() : w[0] + w.slice(1).toLowerCase()).join(' ');

// Camera views: direction from the target to the camera and the screen-up vector, in runtime axes.
const VIEWS = {
  threequarter: { dir: [0.75, 0.45, 0.85], up: [0, 1, 0] },
  side:         { dir: [0, 0, 1],          up: [0, 1, 0] },
  top:          { dir: [0, 1, 0.0001],     up: [0, 1, 0] },
  front:        { dir: [1, 0, 0],          up: [0, 1, 0] },
  aft:          { dir: [-1, 0, 0],         up: [0, 1, 0] },
};

function frame(viewName = 'threequarter') {
  if (!box) return;
  // Drop the damping's leftover motion so the view lands exactly.
  controls.enableDamping = false;
  controls.update();
  const view = VIEWS[viewName] || VIEWS.threequarter;
  const dir = new THREE.Vector3(...view.dir).normalize();
  const centre = box.getCenter(new THREE.Vector3());
  // Fit the box's projection: the camera's right and up axes for this direction.
  const up = new THREE.Vector3(...view.up);
  const right = new THREE.Vector3().crossVectors(up, dir).normalize();
  const trueUp = new THREE.Vector3().crossVectors(dir, right).normalize();
  let w = 0, h = 0, d = 0;
  for (let i = 0; i < 8; i++) {
    const c = new THREE.Vector3(i & 1 ? box.max.x : box.min.x, i & 2 ? box.max.y : box.min.y, i & 4 ? box.max.z : box.min.z).sub(centre);
    w = Math.max(w, Math.abs(c.dot(right))); h = Math.max(h, Math.abs(c.dot(trueUp))); d = Math.max(d, c.dot(dir));
  }
  const vfov = THREE.MathUtils.degToRad(camera.fov) / 2;
  const hfov = Math.atan(Math.tan(vfov) * camera.aspect);
  const dist = 1.08 * Math.max(h / Math.tan(vfov), w / Math.tan(hfov)) + d;
  camera.up.copy(up);
  camera.position.copy(centre).addScaledVector(dir, dist);
  controls.target.copy(centre);
  camera.near = Math.max(0.05, radius / 2000);
  camera.far = dist + radius * 4;
  camera.updateProjectionMatrix();
  controls.update();
  controls.enableDamping = true;
  for (const b of document.querySelectorAll('[data-view]')) b.setAttribute('aria-pressed', String(b.dataset.view === viewName));
}

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

function clearSelection() {
  if (selected) for (const [mesh, material] of selected.materials) mesh.material = material;
  selected = null;
  pickBox.hidden = true;
}

function select(node) {
  clearSelection();
  if (!node) return;
  const materials = new Map();
  node.traverse(o => { if (o.isMesh) { materials.set(o, o.material); o.material = highlight; } });
  selected = { node, materials };
  const [component, kind, canon, geometry] = labels[node.name] || [node.name, '', '', ''];
  pickBox.innerHTML = '';
  const title = document.createElement('b');
  title.textContent = component;
  const info = document.createElement('span');
  info.textContent = [pretty(assemblyOf(node)), kind, canon && `canon ${canon}`, geometry && `geometry ${geometry}`].filter(Boolean).join(' · ');
  pickBox.append(title, info);
  pickBox.hidden = false;
}

// A click is a pointer press and release without much movement (orbit drags never select).
const raycaster = new THREE.Raycaster();
let down = null;
canvas.addEventListener('pointerdown', e => { down = { x: e.clientX, y: e.clientY, t: performance.now() }; });
canvas.addEventListener('pointerup', e => {
  if (!down || !model) return;
  const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y);
  const quick = performance.now() - down.t < 500;
  down = null;
  if (moved > 6 || !quick) return;
  const ndc = new THREE.Vector2((e.clientX / window.innerWidth) * 2 - 1, -(e.clientY / window.innerHeight) * 2 + 1);
  raycaster.setFromCamera(ndc, camera);
  const hit = raycaster.intersectObject(model, true).find(h => h.object.visible && visibleChain(h.object));
  select(hit ? nodeOf(hit.object) : null);
});
const visibleChain = o => { for (; o; o = o.parent) if (!o.visible) return false; return true; };

function buildPanel() {
  list.innerHTML = '';
  for (const [name, group] of [...groups].sort((a, b) => pretty(a[0]).localeCompare(pretty(b[0])))) {
    let count = 0;
    group.traverse(o => { if (o.name.startsWith('WF_')) count++; });
    const li = document.createElement('li');
    const label = document.createElement('label');
    const box = document.createElement('input');
    box.type = 'checkbox'; box.checked = true;
    box.addEventListener('change', () => {
      group.visible = box.checked;
      if (!box.checked && selected && assemblyOf(selected.node) === name) clearSelection();
    });
    const text = document.createElement('span');
    text.textContent = pretty(name);
    const n = document.createElement('span');
    n.className = 'count'; n.textContent = count;
    label.append(box, text, n); li.append(label); list.append(li);
  }
}

document.getElementById('show-all').addEventListener('click', () => {
  for (const g of groups.values()) g.visible = true;
  for (const b of list.querySelectorAll('input')) b.checked = true;
});
panelToggle.addEventListener('click', () => {
  panel.hidden = !panel.hidden;
  panelToggle.setAttribute('aria-expanded', String(!panel.hidden));
});
for (const b of document.querySelectorAll('[data-view]')) {
  b.addEventListener('click', () => frame(b.dataset.view === 'reset' ? 'threequarter' : b.dataset.view));
}
window.addEventListener('keydown', e => {
  if (e.target.closest('input')) return;
  const keys = { '1': 'side', '2': 'top', '3': 'threequarter', '4': 'front', '5': 'aft', Home: 'threequarter' };
  if (keys[e.key]) frame(keys[e.key]);
  if (e.key === 'Escape') clearSelection();
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

async function load() {
  const [build, nodes] = await Promise.all([
    fetch('build.json').then(r => r.ok ? r.json() : null).catch(() => null),
    fetch('model/nodes.json').then(r => r.ok ? r.json() : {}).catch(() => ({})),
  ]);
  labels = nodes;
  showBuild(build);
  const draco = new DRACOLoader().setDecoderPath('vendor/three/draco/');
  const loader = new GLTFLoader().setDRACOLoader(draco);
  const gltf = await loader.loadAsync('model/wayfarer.glb', e => {
    if (e.total) status.textContent = `Loading model… ${Math.round(100 * e.loaded / e.total)} %`;
    else status.textContent = `Loading model… ${(e.loaded / 1e6).toFixed(1)} MB`;
  });
  draco.dispose();
  model = gltf.scene;
  model.traverse(o => {
    if (o.name.startsWith('Assembly_') && !groups.has(o.name)) groups.set(o.name, o);
    if (o.isMesh) {
      for (const m of [].concat(o.material)) m.side = THREE.DoubleSide;   // the export turns back-face culling off
    }
  });
  scene.add(model);
  box = new THREE.Box3().setFromObject(model);
  radius = box.getSize(new THREE.Vector3()).length() / 2;
  buildPanel();
  frame('threequarter');
  status.hidden = true;
  window.wayfarer = { model, groups, camera, controls, frame, select, build, box };   // for inspection from the console
}

resize();
renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });
load().catch(err => {
  console.error(err);
  status.textContent = `The model could not be loaded: ${err.message || err}`;
  status.classList.add('error');
});
