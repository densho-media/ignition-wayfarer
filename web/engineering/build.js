// Engineering · How Wayfarer is built (tools/story.py writes engineering/build/ and its sequence.json from the assembly-sequence study).
// The Explore Ship model (../../viewer/build.json names the GLB, its nodes file and its hologram file) shown step by step: parts of
// earlier steps in their own materials, the selected step's parts highlighted, later steps a ghost or hidden.
// Each part's step comes from the study's selectors, with the rules of lab/studies/assembly-sequence/sequence.py classify(): the first
// step (file order) whose `select` matches wins, else the first whose `fallback` does. Presentation only: it computes no spacecraft facts.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const VIEWER = '../../viewer/';
const $ = id => document.getElementById(id);
const stage = $('stage'), canvas = $('build-view'), gate = $('gate'), cstatus = $('cstatus');
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fmtT = t => t >= 10 ? `${Math.round(t).toLocaleString('en')} t` : `${t.toFixed(1)} t`;

let seq = null, cur = 0, loaded = false;
const counts = {};                                   // step id -> parts in the model (after loading)

// ---- the sequence without 3D: captions, the step list, the mass bar ----------------------------------------------------------------
const glob = p => new RegExp('^' + p.replace(/[.+^${}()|\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\?/g, '.').replace(/\[!/g, '[^') + '$');
function rules(field) {
  const out = [];
  seq.steps.forEach((st, i) => { for (const s of st[field] || []) { const k = s.indexOf(':'); out.push([i, s.slice(0, k), glob(s.slice(k + 1))]); } });
  return out;
}
let SELECT = [], FALLBACK = [];
function classify(item) {
  for (const list of [SELECT, FALLBACK]) for (const [i, f, re] of list) if (re.test(String(item[f] ?? ''))) return i;
  return -1;
}

function caption() {
  const st = seq.steps[cur], ph = seq.phases.find(p => p.id === st.phase), m = st.mass;
  const after = st.after.map(a => { const s = seq.steps.find(x => x.id === a); return `<a href="#${a}">${s.n} ${esc(s.title)}</a>`; }).join(', ');
  const list = (xs, cls = 'plain') => xs.length ? `<ul class="${cls}">${xs.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : '';
  const parts = m.parts.length ? `<ul class="plain mass">${m.parts.map(([n, t]) => `<li><code>${esc(n)}</code> ${fmtT(t)}</li>`).join('')}</ul>` : '';
  const n = counts[st.id];
  $('caption').innerHTML = `<p class="eyebrow">Step ${st.n} of ${seq.steps.length} · phase ${ph.id.slice(1)} ${esc(ph.name)}</p>
    <h3>${esc(st.title)}</h3>
    <p>${esc(st.why)}</p>
    <dl><dt>Rests on</dt><dd>${esc(st.rests_on)}</dd>
      ${after ? `<dt>After</dt><dd>${after}</dd>` : ''}
      ${st.detail.length ? `<dt>Sub-steps</dt><dd>${list(st.detail, 'detail')}</dd>` : ''}
      ${st.open.length ? `<dt>Open</dt><dd>${list(st.open)}</dd>` : ''}
      <dt>Mass</dt><dd>${m.added_t >= 0.05 ? `+${fmtT(m.added_t)} booked here, ` : 'none booked here, '}${fmtT(m.cumulative_t)} in place${parts}</dd>
      ${n != null ? `<dt>Parts</dt><dd>${n ? `${n.toLocaleString('en')} model parts` : 'no new hardware'}</dd>` : ''}</dl>`;
}
function massbar() {
  const total = seq.ledger.total_t;
  $('massbar').innerHTML = seq.steps.map((st, i) => st.mass.added_t > 0
    ? `<i data-i="${i}" style="flex:${st.mass.added_t / total}" title="${st.n} ${esc(st.title)}: +${fmtT(st.mass.added_t)}"></i>` : '').join('')
    + `<span id="masstext"></span>`;
}
function marks() {
  for (const li of document.querySelectorAll('#steps .step')) {
    const i = seq.steps.findIndex(s => s.id === li.dataset.step);
    li.classList.toggle('done', i < cur);
    li.classList.toggle('current', i === cur);
    li.querySelector('button').setAttribute('aria-current', i === cur ? 'step' : 'false');
  }
  for (const b of document.querySelectorAll('#massbar i')) b.classList.toggle('on', +b.dataset.i <= cur);
  const st = seq.steps[cur];
  $('masstext').textContent = `${fmtT(st.mass.cumulative_t)} of ${fmtT(seq.ledger.total_t)} when complete`;
  $('scrub').value = String(cur + 1);
  $('step-label').innerHTML = `<b>${st.n}</b> ${esc(st.title)}`;
}
function select(i, push) {
  cur = Math.max(0, Math.min(seq.steps.length - 1, i));
  caption();
  marks();
  if (push) history.replaceState(null, '', '#' + seq.steps[cur].id);
  if (loaded) show(true);
}

// ---- 3D -----------------------------------------------------------------------------------------------------------------------------
let renderer, scene, camera, controls, ship;
const meshes = [];                                       // {o, step}
const ghost = new THREE.MeshBasicMaterial({ color: 0x8a9aa8, transparent: true, opacity: 0.035, depthWrite: false, side: THREE.DoubleSide });
const hot = new THREE.MeshStandardMaterial({ color: 0xD99AC9, emissive: 0x6b2d5c, emissiveIntensity: 0.6, roughness: 0.5, metalness: 0.1,
                                             side: THREE.DoubleSide });   // the step's new parts: plasma pink, the site's selected colour
const VIEWS = { threequarter: [-0.5, 0.62, 0.6], side: [0, 0.05, 1], top: [0, 1, 0.0001], front: [0.85, 0.3, 0.45], aft: [-1, 0.25, 0.35] };
let view = 'auto';

async function loadShip() {
  const build = await fetch(VIEWER + 'build.json', { cache: 'no-store' }).then(r => r.ok ? r.json() : null).catch(() => null);
  if (!build?.glb_file) throw new Error('the Explore Ship model is not part of this build');
  const [nodes, holo] = await Promise.all([build.nodes_file, build.holo_file].map(f => f ? fetch(VIEWER + f).then(r => r.ok ? r.json() : null).catch(() => null) : null));
  if (!nodes) throw new Error('the part labels could not be loaded');
  const draco = new DRACOLoader().setDecoderPath(VIEWER + 'vendor/three/draco/');
  const total = build.glb?.bytes;
  const gltf = await new GLTFLoader().setDRACOLoader(draco).loadAsync(VIEWER + build.glb_file, e => {
    cstatus.textContent = total ? `Loading the ship… ${Math.min(100, Math.round(100 * e.loaded / total))} %` : `Loading the ship… ${(e.loaded / 1e6).toFixed(1)} MB`;
  });
  draco.dispose();
  ship = gltf.scene;
  const stepOf = new Map();
  ship.traverse(o => {
    if (!o.name.startsWith('WF_') || stepOf.has(o.name)) return;
    const n = nodes[o.name];
    if (!n) return;
    const sub = holo?.nodes?.[o.name] ?? 'CTX';
    const i = classify({ id: n[0], kind: n[1], sub: Array.isArray(sub) ? sub[0] : sub, group: holo?.groups?.[o.name] ?? '' });
    stepOf.set(o.name, i);
    if (i >= 0) counts[seq.steps[i].id] = (counts[seq.steps[i].id] || 0) + 1;
  });
  for (const st of seq.steps) counts[st.id] = counts[st.id] || 0;
  let unplaced = 0;
  ship.traverse(o => {
    if (!o.isMesh) return;
    let n = o;
    while (n && !stepOf.has(n.name)) n = n.parent;
    let i = n ? stepOf.get(n.name) : -1;
    if (i < 0) { unplaced++; i = seq.steps.length - 1; }      // never silently dropped: shown with the finished ship
    for (const m of [].concat(o.material)) m.side = THREE.DoubleSide;
    meshes.push({ o, step: i, material: o.material, visible: o.visible });
  });
  return unplaced;
}

function show(animate) {
  const ghosted = $('ghost').checked;
  const box = new THREE.Box3(), built = new THREE.Box3();
  for (const m of meshes) {
    const o = m.o;
    if (!m.visible) { o.visible = false; continue; }
    if (m.step < cur) { o.material = m.material; o.visible = true; o.renderOrder = 0; built.expandByObject(o); }
    else if (m.step === cur) { o.material = hot; o.visible = true; o.renderOrder = 0; box.expandByObject(o); }
    else { o.material = ghost; o.visible = ghosted; o.renderOrder = 1; }
  }
  // Frame the step's parts with enough of the ship around them to see where they sit; the last step (no new parts) frames everything.
  const whole = new THREE.Box3().setFromObject(ship);
  let focus = box.isEmpty() ? (built.isEmpty() ? whole : built) : box;
  const size = focus.getSize(new THREE.Vector3()).length();
  const minR = whole.getSize(new THREE.Vector3()).length() * 0.18;
  frame(focus.getCenter(new THREE.Vector3()), Math.max(size / 2, minR), animate);
  dirty = true;
}

let tween = null;
function frame(center, r, animate) {
  const name = view === 'auto' ? seq.steps[cur].view : view;
  const fov = camera.fov * Math.PI / 180, aspect = Math.min(camera.aspect, 1.6);
  const d = r / Math.sin(fov / 2) / Math.max(Math.min(aspect, 1), 0.55) * 1.05;
  const to = { target: center.clone(), pos: center.clone().add(new THREE.Vector3(...VIEWS[name]).normalize().multiplyScalar(d)) };
  camera.near = Math.max(0.1, d / 3000);
  camera.far = d * 30;
  camera.updateProjectionMatrix();
  if (!animate || matchMedia('(prefers-reduced-motion: reduce)').matches) {
    controls.target.copy(to.target); camera.position.copy(to.pos); controls.update(); tween = null; return;
  }
  tween = { t0: performance.now(), dur: 900, from: { target: controls.target.clone(), pos: camera.position.clone() }, to };
}

let dirty = true, raf = 0;
function render(now) {
  raf = requestAnimationFrame(render);
  if (tween) {
    const k = Math.min(1, (now - tween.t0) / tween.dur), e = k < 0.5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2;
    controls.target.lerpVectors(tween.from.target, tween.to.target, e);
    camera.position.lerpVectors(tween.from.pos, tween.to.pos, e);
    if (k >= 1) tween = null;
    dirty = true;
  }
  if (controls.update()) dirty = true;
  if (!dirty) return;
  dirty = false;
  renderer.render(scene, camera);
}
function layout() {
  renderer.setSize(stage.clientWidth, stage.clientHeight, false);
  camera.aspect = stage.clientWidth / stage.clientHeight;
  camera.updateProjectionMatrix();
  dirty = true;
}

async function start() {
  gate.hidden = true;
  cstatus.hidden = false;
  cstatus.textContent = 'Starting…';
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, logarithmicDepthBuffer: true });
  } catch (err) {
    cstatus.textContent = 'This browser could not start WebGL, which the 3D build sequence needs. The steps below read without it.';
    cstatus.classList.add('error');
    return;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.setClearColor(0x07090c);
  scene = new THREE.Scene();
  scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.35;
  scene.add(new THREE.HemisphereLight(0xb8c4d0, 0x1a1d22, 0.9));
  const sun = new THREE.DirectionalLight(0xfff4e6, 2.2);
  sun.position.set(0.6, 0.8, 0.5);
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0x8aa4c0, 0.5);
  fill.position.set(-0.7, -0.3, -0.6);
  scene.add(fill);
  camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100000);
  controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.12;
  controls.screenSpacePanning = true;
  controls.addEventListener('start', () => { tween = null; });
  controls.addEventListener('change', () => { dirty = true; });
  layout();
  stage.classList.add('live');
  let unplaced = 0;
  try {
    unplaced = await loadShip();
  } catch (err) {
    cstatus.textContent = `The ship could not load (${err.message || err}). The steps below read without it.`;
    cstatus.classList.add('error');
    return;
  }
  scene.add(ship);
  loaded = true;
  cstatus.hidden = !unplaced;
  if (unplaced) cstatus.textContent = `${unplaced} parts match no step yet; they appear with the finished ship.`;
  caption();
  show(false);
  render(performance.now());
  window.buildSeq = { ready: true, step: () => seq.steps[cur].id, select: id => select(seq.steps.findIndex(s => s.id === id), true), counts, unplaced,
                      stats: () => ({ meshes: meshes.length, calls: renderer.info.render.calls }) };
}

// ---- controls -----------------------------------------------------------------------------------------------------------------------
let timer = 0;
function play(on) {
  clearInterval(timer);
  timer = 0;
  $('play').textContent = on ? '❚❚ Pause' : '▶ Play';
  $('play').setAttribute('aria-pressed', String(!!on));
  if (!on) return;
  if (cur >= seq.steps.length - 1) select(0, true);
  timer = setInterval(() => { if (cur >= seq.steps.length - 1) play(false); else select(cur + 1, true); }, 3200);
}

async function init() {
  seq = await fetch('sequence.json').then(r => r.json());
  SELECT = rules('select');
  FALLBACK = rules('fallback');
  massbar();
  const fromHash = () => { const i = seq.steps.findIndex(s => s.id === location.hash.slice(1)); return i < 0 ? 0 : i; };
  select(fromHash(), false);
  for (const li of document.querySelectorAll('#steps .step')) li.querySelector('button').addEventListener('click', () => {
    play(false); select(seq.steps.findIndex(s => s.id === li.dataset.step), true);
    if (!loaded && matchMedia('(max-width: 760px)').matches) $('caption').scrollIntoView({ block: 'nearest' });
  });
  $('prev').addEventListener('click', () => { play(false); select(cur - 1, true); });
  $('next').addEventListener('click', () => { play(false); select(cur + 1, true); });
  $('play').addEventListener('click', () => { play(!timer); if (timer && !loaded && !renderer) start(); });
  $('scrub').addEventListener('input', e => { play(false); select(+e.target.value - 1, true); });
  $('ghost').addEventListener('change', () => { if (loaded) show(false); });
  for (const b of document.querySelectorAll('.views button')) b.addEventListener('click', () => {
    view = b.dataset.view;
    for (const x of document.querySelectorAll('.views button')) x.setAttribute('aria-pressed', String(x === b));
    if (loaded) show(true);
  });
  window.addEventListener('keydown', e => {
    if (e.target.closest('input, textarea')) return;
    if (e.key === 'ArrowRight') { play(false); select(cur + 1, true); }
    if (e.key === 'ArrowLeft') { play(false); select(cur - 1, true); }
  });
  $('load').addEventListener('click', start);
  window.addEventListener('resize', () => { if (renderer) { layout(); if (loaded) show(false); } });
  window.addEventListener('hashchange', () => select(fromHash(), false));
  window.addEventListener('pagehide', () => { cancelAnimationFrame(raf); renderer?.dispose(); renderer?.forceContextLoss(); });
  window.buildSeq = { ready: false, start };
}
init().catch(err => { $('caption').textContent = `The build sequence could not load: ${err.message || err}`; });
