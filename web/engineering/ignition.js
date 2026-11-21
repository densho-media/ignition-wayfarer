// Engineering · Ignition: what breaks (tools/story.py writes engineering/ignition/ and its ignition.json from the ignition-failures study).
// Today's four Vertex engines at the mission point, twice, with one camera: left as the ship's budget assumes, right with the measured
// physics (Overload, Meltdown, or the visitor's levers). The page plays the recorded ledger; it computes no new spacecraft facts. The lever
// model below mirrors lab/studies/ignition-failures/model.py evaluate() line by line, and the site check compares the two (window.__ign).
// Geometry: Explore Ship's engine inspection parts (build.engine_file: 264 parts, int16 positions), never the ship GLB. The four engines
// are one InstancedMesh; every part's temperature, melt, vapour and fragment motion live in two small float textures (parts x engines x
// sides), read by the vertex and fragment shaders. Effects are additive and few: plume cones, burn glows, one particle cloud, shock shells.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { mergeGeometries, toCreasedNormals } from 'three/addons/utils/BufferGeometryUtils.js';

const INLINE = window.IGN_INLINE || null;          // the self-contained preview passes its data here instead of fetching it
const VIEWER = '../../viewer/';
const DATA = 'ignition.json';       // written by tools/story.py next to the page (engineering/ignition/), not beside this script
const $ = id => document.getElementById(id);
const stage = $('stage'), canvas = $('ign-view'), gate = $('gate'), cstatus = $('cstatus'), hud = $('hud'), evcap = $('evcap');
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const touch = matchMedia('(pointer: coarse)').matches;

let D = null, K = null;                             // ignition.json and its constants
let mode = 'overload', run = null, levers = {};
const ENG = 4;

// ---- formatting -----------------------------------------------------------------------------------------------------------------------
const W = w => w >= 1e11 ? `${(w / 1e12).toLocaleString('en', { maximumFractionDigits: 2 })} TW` : w >= 1e8 ? `${(w / 1e9).toFixed(2)} GW`
  : w >= 1e5 ? `${(w / 1e6).toFixed(1)} MW` : `${(w / 1e3).toFixed(0)} kW`;
const S = t => t == null ? '—' : t < 1e-3 ? `${t < 1e-5 ? (t * 1e6).toFixed(1) : Math.round(t * 1e6)} µs` : t < 1 ? `${(t * 1e3).toPrecision(3)} ms`
  : t < 3600 ? `${t.toPrecision(3)} s` : t < 86400 * 2 ? `${(t / 3600).toPrecision(3)} h` : t < 3.156e7 * 2 ? `${(t / 86400).toPrecision(3)} d` : `${(t / 3.156e7).toPrecision(3)} yr`;
const X = r => r >= 100 ? `${Math.round(r).toLocaleString('en')}×` : `${r.toPrecision(3)}×`;
const N = v => v >= 1e4 || v < 1e-2 ? v.toExponential(1).replace('e+', 'e') : v.toPrecision(3).replace(/\.?0+$/, '');
const T = kg => kg >= 1e6 ? `${(kg / 1e6).toPrecision(3)} kt` : `${Math.round(kg / 1e3).toLocaleString('en')} t`;

// ---- the lever model (model.py evaluate) ----------------------------------------------------------------------------------------------
function evaluate(v) {
  const { tau, rho, att, leak, src, G } = v;
  const P = tau * K.Pf;
  const Hpn = tau * K.PN * src;
  const Hl = tau * K.L * leak / K.leak0;
  const Hd = tau * K.D100 * 100.0 / G;
  const H = Hpn + Hl + tau * K.loss + Hd;
  const Q = rho * K.cap;
  const burn_s = K.burn_d * 86400.0 / tau;
  const run_s = K.burns * burn_s;
  const lives = D.coils.map(c => ({ coil: c.coil, life_s: c.life_unshielded_s * (K.Pf_n / P) * att / src,
    shield_kg: c.shield_kg * (att > 1 ? Math.log(att) / Math.log(c.attenuation_needed) : 0.0) }));
  const first = lives.reduce((a, b) => b.life_s < a.life_s ? b : a);
  const shield_kg = 4 * lives.reduce((s, c) => s + c.shield_kg, 0);
  const rad_kg = 4 * (rho - 1) * K.area_m2 * K.areal_kg;
  const Pd = P / (G * K.eta);
  const out = { P_W: P, heat_W: H, burn_heat_W: Hpn + Hl + tau * K.loss, driver_heat_W: Hd, capacity_W: Q, ratio: H / Q,
    burn_ratio: (Hpn + Hl + tau * K.loss) / Q, driver_W: Pd, bank_ratio: Pd / K.bank_W, burn_s, run_s, coil: first.coil, coil_life_s: first.life_s,
    added_kg: shield_kg + rad_kg, shield_kg, radiator_kg: rad_kg, melt_s: H > Q ? K.E1000 / (H - Q) : null,
    extra_trip_s: K.burns * (burn_s - K.burn_d * 86400.0), Hpn, Hl, Hd, Q, H };
  const fails = [];
  if (Pd > K.bank_W) fails.push({ id: 'POWER', t: K.bank_J / Pd, what: `The driver needs ${W(Pd)}; the 50 MW pulse bank, the only budgeted source, is empty` });
  if (H > Q) fails.push({ id: 'MELT', t: out.melt_s, what: `${X(H / Q)} more heat than the radiators carry: the engine is +1000 K` });
  if (first.life_s < run_s) fails.push({ id: 'QUENCH', t: first.life_s, what: `Neutrons end the ${first.coil} superconductor; it quenches and releases its stored energy` });
  if (out.added_kg > K.margin_kg) fails.push({ id: 'MASS', t: null, what: `${T(out.added_kg)} added against the ${T(K.margin_kg)} departure margin` });
  if (out.extra_trip_s > K.allowance_s) fails.push({ id: 'SLOW', t: null, what: `Four burns of ${S(burn_s)}: the trip grows beyond its ${D.proto.trip_allowance_yr} yr allowance` });
  fails.sort((a, b) => (a.t == null) - (b.t == null) || (a.t ?? 0) - (b.t ?? 0));
  out.fails = fails;
  return out;
}

// ---- runs: what the right-hand side does over its physical clock -----------------------------------------------------------------------
const BASE = () => Object.fromEntries(D.levers.map(l => [l.id, l.value]));
const ISOLATE = { overload: { rho: 1e12 }, meltdown: { G: 1e12, att: 1e12 } };
function makeRun() {
  const v = mode === 'design' ? { ...levers } : { ...BASE(), ...ISOLATE[mode] };
  const o = evaluate(v);
  const sc = D.scenarios.find(s => s.id === mode);
  const quench = mode !== 'meltdown' && o.fails.some(f => f.id === 'QUENCH');
  const power = mode !== 'meltdown' && o.fails.some(f => f.id === 'POWER');
  let tEnd;
  if (sc) tEnd = sc.clock[1];
  else {
    const ts = o.fails.filter(f => f.t != null).map(f => f.t);
    tEnd = ts.length ? Math.min(Math.max(Math.max(...ts) * 1.3, 0.05), 30) : 2;
  }
  const events = sc ? sc.events.map(e => ({ ...e }))
    : [{ t: 0, id: 'IGNITE', title: 'Ignition with your levers', text: `${W(o.P_W)} of fusion per engine; ${W(o.heat_W)} of heat for ${W(o.capacity_W)} of radiator.` },
       ...o.fails.filter(f => f.t != null && f.t <= tEnd).map(f => ({ t: f.t, id: f.id, title: ({ POWER: 'The pulse bank is empty', MELT: 'The engine is 1000 K hotter', QUENCH: `${o.coil} quenches` })[f.id], text: f.what })),
       ...o.fails.filter(f => f.t == null || f.t > tEnd).map(f => ({ t: f.t ?? Infinity, late: true, id: f.id, title: f.t == null ? 'Design check' : `Later, after ${S(f.t)}`, text: f.what })),
       ...(o.fails.some(f => f.t != null && f.t <= tEnd) ? [] : [{ t: tEnd * 0.6, id: 'HOLDS', title: 'It holds this long', text: o.fails.length ? o.fails.map(f => f.what).join('. ') : 'Nothing fails on this clock. Check the readouts for mass and trip time.' }])];
  // per part, per engine: the heating rate and the times it melts and vapourises (linear warming, PROTOTYPE cp)
  const excess = o.H > o.Q ? 1 - o.Q / o.H : 0;
  const elec = D.parts.filter(p => p.group === 'ELECTRICAL').reduce((s, p) => s + p.mass_kg, 0);
  const parts = PARTS.map(p => {
    const heat = (o.Hpn * p.pn + o.Hl * p.ch + (p.group === 'ELECTRICAL' ? o.Hd * p.mass_kg / elec : 0)) * excess;
    const rate = heat / Math.max(p.mass_kg, 1) / D.proto.cp_J_kgK;
    return { rate, start: p.start_K, melt: p.melt_K };
  });
  // warming on a log time grid: a part that has turned to vapour keeps receiving its share, and that heat now reaches every part still
  // standing in proportion to its mass (re-radiation from the hot vapour: a display rule, PROTOTYPE), so the energy ledger stays whole
  const n = parts.length, steps = 320, cp = D.proto.cp_J_kgK, times = new Float64Array(steps), grid = new Float32Array(steps * n);
  const Tn = Float64Array.from(parts, p => p.start), mass = PARTS.map(p => Math.max(p.mass_kg, 1));
  for (let k = 1; k < steps; k++) times[k] = 1e-6 * Math.pow(tEnd / 1e-6, (k - 1) / (steps - 2));
  grid.set(Float32Array.from(Tn), 0);
  for (let k = 1; k < steps; k++) {
    const dt = times[k] - times[k - 1];
    let pool = 0, alive = 0;
    for (let i = 0; i < n; i++) { const pr = parts[i]; if (Tn[i] >= pr.melt + 4000) pool += pr.rate * mass[i] * cp; else alive += mass[i]; }
    const share = alive > 0 ? pool * dt / (alive * cp) : 0;
    for (let i = 0; i < n; i++) { const pr = parts[i]; if (Tn[i] < pr.melt + 4000) Tn[i] = Math.min(Tn[i] + pr.rate * dt + share, 12000); }
    grid.set(Float32Array.from(Tn), k * n);
  }
  const tq = quench ? o.coil_life_s : null;
  const V = mode === 'design' ? 24 : (sc.id === 'overload' ? 20 : 22);
  const a = 1e-4, dec = Math.log10(tEnd / a + 1);
  return { v, o, events, tEnd, parts, times, grid, tq, power, V, a, dec, tail: quench ? 10 : 6, coldLoss: mode === 'meltdown' || (o.fails.some(f => f.id === 'MELT')) };
}
const phys = (r, u) => u >= r.V ? r.tEnd : r.a * (Math.pow(10, r.dec * Math.max(u, 0) / r.V) - 1);
const vis = (r, t) => r.V * Math.log10(t / r.a + 1) / r.dec;

// ---- three.js -------------------------------------------------------------------------------------------------------------------------
let renderer, scene, camera, controls, engines, stateA, stateB, plumes, glows, cloud, shocks = [], light, stars;
let PARTS = [], partIndex = new Map(), engineMats = [], burnLocal = -18.8;
let u = 0, playing = !reduced, split = 'split', dirty = true, last = 0, frames = [], dpr = 1;
const PART_W = 272;   // texture width (>= parts)

const GLSL_COMMON = `
uniform sampler2D uState; uniform sampler2D uMove; uniform int uSide;
varying float vT; varying float vMelt; varying float vVap; varying float vFlash;
vec3 ign_hash3(float n) { return fract(sin(vec3(n, n + 1.7, n + 3.1)) * vec3(43758.5453, 22578.1459, 19642.3490)); }
float ign_noise(vec3 p) { vec3 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  float n = dot(i, vec3(1.0, 57.0, 113.0));
  return mix(mix(mix(fract(sin(n) * 43758.5), fract(sin(n + 1.0) * 43758.5), f.x), mix(fract(sin(n + 57.0) * 43758.5), fract(sin(n + 58.0) * 43758.5), f.x), f.y),
             mix(mix(fract(sin(n + 113.0) * 43758.5), fract(sin(n + 114.0) * 43758.5), f.x), mix(fract(sin(n + 170.0) * 43758.5), fract(sin(n + 171.0) * 43758.5), f.x), f.y), f.z); }
vec3 ign_rot(vec3 p, vec3 ax, float a) { float c = cos(a), s = sin(a); return p * c + cross(ax, p) * s + ax * dot(ax, p) * (1.0 - c); }
`;
const GLSL_BB = `
vec3 ign_blackbody(float t) {           // Planckian locus, approximate (Helland), linear RGB
  t = clamp(t, 1000.0, 15000.0) / 100.0;
  float r = t <= 66.0 ? 1.0 : clamp(1.292936 * pow(t - 60.0, -0.1332047592), 0.0, 1.0);
  float g = t <= 66.0 ? clamp(0.3900815788 * log(t) - 0.6318414438, 0.0, 1.0) : clamp(1.129890861 * pow(t - 60.0, -0.0755148492), 0.0, 1.0);
  float b = t >= 66.0 ? 1.0 : (t <= 19.0 ? 0.0 : clamp(0.5432067891 * log(t - 10.0) - 1.19625408914, 0.0, 1.0));
  return pow(vec3(r, g, b), vec3(2.2));
}
float ign_glow(float t) { float x = max(t - 650.0, 0.0) / 800.0; return min(x * x * 4.0, 18.0); }
`;

function engineMaterial() {
  const m = new THREE.MeshStandardMaterial({ vertexColors: true, metalness: 0.55, roughness: 0.48, envMapIntensity: 0.6 });
  m.onBeforeCompile = sh => {
    sh.uniforms.uState = { value: stateA.tex }; sh.uniforms.uMove = { value: stateB.tex }; sh.uniforms.uSide = engineSide;
    sh.vertexShader = 'attribute vec4 aPart;\n' + GLSL_COMMON + sh.vertexShader
      .replace('#include <beginnormal_vertex>', `#include <beginnormal_vertex>
        ivec2 ign_px = ivec2(int(aPart.w + 0.5), gl_InstanceID + uSide * ${ENG});
        vec4 ign_st = texelFetch(uState, ign_px, 0), ign_mv = texelFetch(uMove, ign_px, 0);
        vT = ign_st.r; vMelt = ign_st.g; vVap = ign_st.b; vFlash = ign_st.a;
        vec3 ign_ax = normalize(ign_hash3(aPart.w) - 0.5 + 1e-3);
        objectNormal = ign_rot(objectNormal, ign_ax, ign_mv.w);`)
      .replace('#include <begin_vertex>', `#include <begin_vertex>
        vec3 ign_p = transformed - aPart.xyz;
        if (vMelt > 0.0) {
          float h = ign_noise(transformed * 0.55 + aPart.w);
          ign_p.yz *= 1.0 - 0.22 * vMelt * h;
          ign_p.x -= vMelt * (0.4 + 2.2 * h) * (1.0 + 0.04 * length(ign_p.yz));
        }
        transformed = aPart.xyz + ign_rot(ign_p, ign_ax, ign_mv.w) + ign_mv.xyz;`);
    sh.fragmentShader = GLSL_COMMON.replace('uniform sampler2D uState; uniform sampler2D uMove; uniform int uSide;', '') + GLSL_BB + sh.fragmentShader
      .replace('#include <clipping_planes_fragment>', `#include <clipping_planes_fragment>
        if (vVap > 0.0 && fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453) < vVap) discard;`)
      .replace('#include <color_fragment>', `#include <color_fragment>
        diffuseColor.rgb = mix(diffuseColor.rgb, diffuseColor.rgb * 0.35, smoothstep(900.0, 2500.0, vT));`)
      .replace('#include <roughnessmap_fragment>', `#include <roughnessmap_fragment>
        roughnessFactor = mix(roughnessFactor, 0.12, vMelt);`)
      .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
        totalEmissiveRadiance += ign_blackbody(vT) * ign_glow(vT) + vec3(0.55, 0.75, 1.0) * vFlash * 3.0;`);
  };
  return m;
}
const engineSide = { value: 0 };                          // 0 = as budgeted (left), 1 = as measured (right)

class State {     // RGBA float texture: PART_W x (engines x 2 sides)
  constructor() {
    this.data = new Float32Array(PART_W * ENG * 2 * 4);
    this.tex = new THREE.DataTexture(this.data, PART_W, ENG * 2, THREE.RGBAFormat, THREE.FloatType);
    this.tex.minFilter = this.tex.magFilter = THREE.NearestFilter; this.tex.needsUpdate = true;
  }
  set(side, eng, part, a, b, c, d) { const i = ((side * ENG + eng) * PART_W + part) * 4; const x = this.data; x[i] = a; x[i + 1] = b; x[i + 2] = c; x[i + 3] = d; }
}

function plumeMaterial() {
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    uniforms: { uTime: { value: 0 }, uP: { value: Array.from({ length: ENG * 2 }, () => new THREE.Vector4(1, 1, 0, 0)) }, uSide: { value: 0 } },
    vertexShader: `uniform vec4 uP[${ENG * 2}]; uniform int uSide; varying vec2 vUv; varying vec3 vN; varying vec3 vV; varying vec4 vP;
      void main() { vP = uP[gl_InstanceID + uSide * ${ENG}]; vUv = uv; vec3 p = position;
        float w = mix(1.0, vP.y, smoothstep(0.0, 0.6, uv.y)); p.yz *= w;
        vec4 mv = modelViewMatrix * instanceMatrix * vec4(p, 1.0); vV = normalize(-mv.xyz);
        vN = normalize(normalMatrix * mat3(instanceMatrix) * normal); gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `uniform float uTime; varying vec2 vUv; varying vec3 vN; varying vec3 vV; varying vec4 vP;
      float h(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float n2(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
        return mix(mix(h(i), h(i + vec2(1, 0)), f.x), mix(h(i + vec2(0, 1)), h(i + vec2(1, 1)), f.x), f.y); }
      void main() { float rim = pow(1.0 - abs(dot(normalize(vN), vV)), 1.6);
        float core = 1.0 - rim; float along = vUv.y;
        float flow = n2(vec2(vUv.x * 24.0, along * 9.0 - uTime * 3.0)) * 0.6 + n2(vec2(vUv.x * 7.0, along * 3.0 - uTime * 1.3)) * 0.6;
        float rag = mix(1.0, flow * 1.6, vP.z);
        float a = vP.x * (0.35 + 0.65 * core) * smoothstep(0.0, 0.08, along) * pow(1.0 - along, 1.4) * (0.55 + 0.45 * flow) * rag;
        vec3 c = mix(vec3(0.62, 0.42, 0.95), vec3(0.95, 0.7, 0.9), core) * 0.55;
        gl_FragColor = vec4(c * a, 1.0); }`,
  });
}

function pointsMaterial() {
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { uTime: { value: 0 }, uScale: { value: 600 } },
    vertexShader: `attribute vec3 aVel; attribute vec4 aLife; attribute vec3 color; uniform float uTime; uniform float uScale;
      varying vec3 vC; varying float vA;
      void main() { float age = uTime - aLife.x; float k = age / aLife.y;
        vA = (age < 0.0 || k > 1.0) ? 0.0 : (1.0 - k) * min(age * 8.0, 1.0) * aLife.w;
        vec3 p = position + aVel * max(age, 0.0); vC = color;
        vec4 mv = modelViewMatrix * vec4(p, 1.0); gl_Position = projectionMatrix * mv;
        gl_PointSize = vA > 0.0 ? clamp(aLife.z * uScale / -mv.z, 1.0, 64.0) : 0.0; }`,
    fragmentShader: `varying vec3 vC; varying float vA;
      void main() { vec2 d = gl_PointCoord - 0.5; float r = dot(d, d) * 4.0; if (r > 1.0) discard;
        gl_FragColor = vec4(vC * vA * (1.0 - r) * (1.0 - r), 1.0); }`,
  });
}

function shockMaterial() {
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.FrontSide,
    uniforms: { uA: { value: 0 }, uC: { value: new THREE.Color(1, 0.9, 0.8) } },
    vertexShader: `varying vec3 vN; varying vec3 vV; void main() { vec4 mv = modelViewMatrix * vec4(position, 1.0); vV = normalize(-mv.xyz);
      vN = normalize(normalMatrix * normal); gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `uniform float uA; uniform vec3 uC; varying vec3 vN; varying vec3 vV;
      void main() { float rim = pow(1.0 - abs(dot(vN, vV)), 2.5); gl_FragColor = vec4(uC * uA * (0.15 + rim), 1.0); }`,
  });
}

function buildEngineGeometry(M, bin) {
  const q = M.geometry.quantum_m, nv = M.geometry.vertices;
  const pos = new Int16Array(bin, 0, nv * 3), idx = new Uint16Array(bin, nv * 6);
  const mats = M.materials;
  const geos = [];
  M.parts.forEach(p => {
    const sp = D.partByName.get(p.name);
    if (!sp || p.category === 'FUSION_REACTION') return;
    const [v0, n, i0, ni] = p.geo;
    const P = new Float32Array(n * 3);
    let cx = 0, cy = 0, cz = 0;
    for (let i = 0; i < n * 3; i += 3) { P[i] = pos[v0 * 3 + i] * q; P[i + 1] = pos[v0 * 3 + i + 1] * q; P[i + 2] = pos[v0 * 3 + i + 2] * q; cx += P[i]; cy += P[i + 1]; cz += P[i + 2]; }
    let g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(P, 3));
    g.setIndex(Array.from(idx.subarray(i0, i0 + ni)));
    g = toCreasedNormals(g, Math.PI / 5);
    const k = g.attributes.position.count, A = new Float32Array(k * 4), C = new Float32Array(k * 3);
    const col = new THREE.Color().setRGB(...(mats[p.material]?.color || [0.6, 0.6, 0.6]), THREE.SRGBColorSpace);
    for (let i = 0; i < k; i++) { A.set([cx / n, cy / n, cz / n, sp.index], i * 4); C.set([col.r, col.g, col.b], i * 3); }
    g.setAttribute('aPart', new THREE.BufferAttribute(A, 4)); g.setAttribute('color', new THREE.BufferAttribute(C, 3));
    sp.centroid = new THREE.Vector3(cx / n, cy / n, cz / n); sp.label = p.label;
    geos.push(g);
  });
  const merged = mergeGeometries(geos, false);
  geos.forEach(g => g.dispose());
  return merged;
}

function plumeGeometry() {        // engine frame: burn point at x = burnLocal, exhaust toward -x
  const g = new THREE.CylinderGeometry(9.5, 1.2, 90, 40, 24, true);
  g.rotateZ(-Math.PI / 2);             // axis along x, top (radius 9.5) toward -x after the translate below
  g.translate(burnLocal - 45, 0, 0);
  const uv = g.attributes.uv; for (let i = 0; i < uv.count; i++) uv.setY(i, 1 - uv.getY(i));
  return g;
}

async function load() {
  gate.querySelector('button').disabled = true;
  cstatus.hidden = false; cstatus.textContent = 'Loading the engine parts…';
  try {
    let M, bin;
    if (INLINE) { M = INLINE.engine; bin = Uint8Array.from(atob(INLINE.parts), c => c.charCodeAt(0)).buffer; }
    else {
      const build = await fetch(VIEWER + 'build.json', { cache: 'no-store' }).then(r => r.ok ? r.json() : null);
      if (!build?.engine_file) throw new Error('this build has no engine inspection file');
      M = await fetch(VIEWER + build.engine_file).then(r => r.json());
      bin = await fetch(VIEWER + M.geometry.file).then(r => r.arrayBuffer());
    }
    init(M, bin);
    gate.hidden = true; cstatus.hidden = true; stage.classList.add('live'); hud.hidden = false;
    window.wos?.scenario({ label: 'IGNITION', class: 'SIM' });
    setMode(mode, true);
    window.__ign.ready = true;
  } catch (err) {
    cstatus.textContent = `The 3D view could not start: ${err.message}. The numbers below still hold.`; cstatus.classList.add('error');
    gate.querySelector('button').disabled = false;
    console.error(err);
  }
}

function init(M, bin) {
  const q = new URLSearchParams(location.search);
  renderer = new THREE.WebGLRenderer({ canvas, antialias: !touch && !q.has('noaa'), powerPreference: 'high-performance' });
  dpr = Math.min(devicePixelRatio || 1, touch ? 1.5 : 2);
  renderer.setPixelRatio(dpr);
  renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.0;
  renderer.setScissorTest(true);
  scene = new THREE.Scene(); scene.background = new THREE.Color(0x05070b);
  const pm = new THREE.PMREMGenerator(renderer); scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture; pm.dispose();
  scene.environmentIntensity = 0.35;
  scene.add(new THREE.HemisphereLight(0x9fb4d8, 0x0a0c12, 0.35));
  const key = new THREE.DirectionalLight(0xfff1de, 2.2); key.position.set(-120, 160, 220); scene.add(key);
  const rim = new THREE.DirectionalLight(0x8aa6ff, 0.6); rim.position.set(200, -60, -160); scene.add(rim);
  light = new THREE.PointLight(0xe8b4ff, 0, 0, 1.4); scene.add(light);

  stateA = new State(); stateB = new State();
  engineMats = M.engines.map(e => new THREE.Matrix4().fromArray(e.matrix));
  const geo = buildEngineGeometry(M, bin);
  const mat = engineMaterial();
  engines = new THREE.InstancedMesh(geo, mat, ENG); engines.frustumCulled = false;
  engineMats.forEach((m, i) => engines.setMatrixAt(i, m));
  scene.add(engines);

  plumes = new THREE.InstancedMesh(plumeGeometry(), plumeMaterial(), ENG); plumes.frustumCulled = false;
  engineMats.forEach((m, i) => plumes.setMatrixAt(i, m)); scene.add(plumes);

  // burn glows: one point sprite per engine and side, sized in metres
  const burnW = engineMats.map(m => new THREE.Vector3(burnLocal, 0, 0).applyMatrix4(m));
  const gg = new THREE.BufferGeometry().setFromPoints(burnW);
  gg.setAttribute('aVel', new THREE.BufferAttribute(new Float32Array(ENG * 3), 3));
  gg.setAttribute('aLife', new THREE.BufferAttribute(new Float32Array(ENG * 4), 4));
  gg.setAttribute('color', new THREE.BufferAttribute(new Float32Array(ENG * 3).fill(1), 3));
  glows = new THREE.Points(gg, pointsMaterial()); glows.frustumCulled = false; scene.add(glows);

  const center = burnW.reduce((a, b) => a.add(b), new THREE.Vector3()).multiplyScalar(1 / ENG);
  light.position.copy(center);
  const mid = engineMats.map(m => new THREE.Vector3(-12, 0, 0).applyMatrix4(m)).reduce((a, b) => a.add(b), new THREE.Vector3()).multiplyScalar(1 / ENG);
  const span = Math.max(...burnW.map(b => b.distanceTo(center))) + 16;
  camera = new THREE.PerspectiveCamera(36, 1, 0.5, 6000);
  camera.position.copy(mid).add(new THREE.Vector3(0.55, 0.75, 2.3).multiplyScalar(span * (touch ? 1.85 : 1.7)));
  controls = new OrbitControls(camera, canvas); controls.target.copy(mid).add(new THREE.Vector3(-6, 0, 0)); controls.enableDamping = true; controls.dampingFactor = 0.08;
  controls.minDistance = span * 0.6; controls.maxDistance = span * 8; controls.update();
  controls.addEventListener('change', () => { dirty = true; });
  window.__ign.center = center.toArray(); window.__ign.span = span;

  // stars: one static cloud on a far sphere
  const sp = new Float32Array(1800 * 3), sc = new Float32Array(1800 * 3), sv = new Float32Array(1800 * 3), sl = new Float32Array(1800 * 4);
  for (let i = 0; i < 1800; i++) {
    const z = Math.random() * 2 - 1, a = Math.random() * Math.PI * 2, r = Math.sqrt(1 - z * z);
    sp.set([center.x + 2500 * r * Math.cos(a), center.y + 2500 * z, center.z + 2500 * r * Math.sin(a)], i * 3);
    const b = 0.25 + Math.random() ** 3 * 0.9; sc.set([b * 0.9, b * 0.95, b], i * 3); sl.set([-1e9, 1e12, 5 + Math.random() * 9, 1], i * 4);
  }
  const sgeo = new THREE.BufferGeometry(); sgeo.setAttribute('position', new THREE.BufferAttribute(sp, 3));
  sgeo.setAttribute('aVel', new THREE.BufferAttribute(sv, 3)); sgeo.setAttribute('aLife', new THREE.BufferAttribute(sl, 4)); sgeo.setAttribute('color', new THREE.BufferAttribute(sc, 3));
  stars = new THREE.Points(sgeo, pointsMaterial()); stars.material.uniforms.uTime.value = 0; stars.frustumCulled = false; scene.add(stars);

  for (let i = 0; i < 6; i++) { const m = new THREE.Mesh(new THREE.SphereGeometry(1, 32, 16), shockMaterial()); m.visible = false; m.frustumCulled = false; scene.add(m); shocks.push(m); }

  new ResizeObserver(() => { dirty = true; }).observe(stage);
  renderer.setAnimationLoop(frame);
  window.__ign.parts3d = { engines, plumes, glows, stars, get cloud() { return cloud; }, scene };
}

// ---- the run's effects (deterministic in visual time, so scrubbing works both ways) -----------------------------------------------
function local(eng, p) { return p.clone().applyMatrix4(engineMats[eng]); }
function dirOf(eng, p) { return new THREE.Vector3(p.x - burnLocal, p.y, p.z).normalize().transformDirection(engineMats[eng]); }
function buildEffects(r) {
  const pos = [], vel = [], life = [], col = [];
  const add = (p, v, birth, len, size, c, a = 1) => { pos.push(p.x, p.y, p.z); vel.push(v.x, v.y, v.z); life.push(birth, len, size, a); col.push(...c); };
  const rnd = mulberry(7);
  const jitter = s => new THREE.Vector3(rnd() - 0.5, rnd() - 0.5, rnd() - 0.5).multiplyScalar(s);
  r.quenchVis = r.tq != null && r.tq <= r.tEnd ? [0, 1, 2, 3].map(e => vis(r, r.tq) + (reduced ? 0 : 0.55) * e) : null;
  r.powerVis = r.power ? vis(r, K.bank_J / r.o.driver_W) : null;
  r.coldVis = r.coldLoss ? vis(r, 1e-4) : null;
  const plumeEnd = r.quenchVis ? r.quenchVis : [r.V + r.tail, r.V + r.tail, r.V + r.tail, r.V + r.tail];
  // plasma leaking onto the hardware: sparks from the burn point to the parts that take charged heat
  const targets = D.parts.filter(p => p.ch > 0 && p.centroid);
  const nLeak = Math.round(900 * Math.min(r.v.leak / K.leak0, 1.6));
  for (let i = 0; i < nLeak && targets.length; i++) {
    const e = i % ENG, tgt = targets[Math.floor(rnd() * targets.length)];
    const from = local(e, new THREE.Vector3(burnLocal, 0, 0)), to = local(e, tgt.centroid.clone().add(jitter(3)));
    const birth = rnd() * plumeEnd[e], len = 0.35 + rnd() * 0.3;
    add(from, to.sub(from).multiplyScalar(1 / len), birth, len, 0.9, [1.0, 0.55, 0.85], 0.8);
  }
  // vapour from parts past their boiling display threshold
  r.parts.forEach((p, i) => {
    let kb = -1; for (let k = 0; k < r.times.length; k++) if (r.grid[k * PARTS.length + i] >= p.melt + 1500) { kb = k; break; }
    if (kb < 0) return;
    const tb = Math.max(r.times[kb], 1e-6);
    const sp = PARTS[i]; if (!sp.centroid) return;
    const vb = vis(r, tb), n = Math.min(8, 2 + Math.round(Math.sqrt(sp.mass_kg) / 25));
    for (let e = 0; e < ENG; e++) for (let k = 0; k < n; k++) {
      const p0 = local(e, sp.centroid.clone().add(jitter(2.5)));
      const v = dirOf(e, sp.centroid).multiplyScalar(2 + rnd() * 4).add(new THREE.Vector3(-3 - rnd() * 4, 0, 0).transformDirection(engineMats[e]));
      add(p0, v, vb + rnd() * 2.5, 2.2 + rnd() * 2, 3.5 + rnd() * 3, [1.0, 0.5, 0.18], 0.55);
    }
  });
  // the quench: cryogen vents (white) and fragments (sparks) from the coil cryostats, per engine at its quench time
  if (r.quenchVis) {
    const cold = D.parts.filter(p => (p.group === 'CLOSURE_COILS' || p.group === 'NOZZLE_LOOPS') && p.centroid);
    for (let e = 0; e < ENG; e++) {
      const vq = r.quenchVis[e];
      for (let k = 0; k < 420; k++) {
        const sp = cold[Math.floor(rnd() * cold.length)];
        const p0 = local(e, sp.centroid.clone().add(jitter(4)));
        add(p0, dirOf(e, sp.centroid).add(jitter(1.2)).normalize().multiplyScalar(3 + rnd() * 9), vq + rnd() * 1.2, 2 + rnd() * 2.5, 2.5 + rnd() * 2.5, [0.75, 0.85, 1.0], 0.45);
      }
      for (let k = 0; k < 260; k++) {
        const sp = cold[Math.floor(rnd() * cold.length)];
        const p0 = local(e, sp.centroid.clone());
        add(p0, dirOf(e, sp.centroid).add(jitter(1.6)).normalize().multiplyScalar(14 + rnd() * 26), vq + rnd() * 0.15, 0.8 + rnd() * 1.4, 0.7, [1.0, 0.78, 0.45], 1);
      }
    }
  }
  // the pulse bank overrun: sparks at the electrical parts
  if (r.powerVis != null) {
    const el = D.parts.filter(p => p.group === 'ELECTRICAL' && p.centroid);
    for (let e = 0; e < ENG; e++) for (let k = 0; k < 160; k++) {
      const sp = el[Math.floor(rnd() * el.length)];
      add(local(e, sp.centroid.clone().add(jitter(1))), jitter(14), r.powerVis + rnd() * 2.2, 0.25 + rnd() * 0.4, 0.8, [0.6, 0.8, 1.0], 1);
    }
  }
  if (cloud) { scene.remove(cloud); cloud.geometry.dispose(); }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('aVel', new THREE.Float32BufferAttribute(vel, 3));
  g.setAttribute('aLife', new THREE.Float32BufferAttribute(life, 4)); g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  cloud = new THREE.Points(g, cloud?.material || pointsMaterial()); cloud.frustumCulled = false; scene.add(cloud);
  r.particles = pos.length / 3;
  // fragment motion per part: slowed display speed from the 10 % kinetic share of the quench energy over the part's mass
  const moved = { CLOSURE_COILS: 1, NOZZLE_LOOPS: 1, COIL_SUPPORTS: 0.8, CAGE: 0.55, ELECTRICAL: 0.6, THERMAL_PLUMBING: 0.6 };
  r.frag = PARTS.map(p => ({ k: moved[p.group] ?? 0.3, sp: Math.min(3, Math.max(0.35, Math.sqrt(4e4 / Math.max(p.mass_kg, 50)))), spin: 0.25 + mulberry(p.index + 11)() * 1.2 }));
  const ke = D.proto.quench_kinetic_share * K.quench_J, coldMass = D.parts.filter(p => p.group === 'CLOSURE_COILS' || p.group === 'NOZZLE_LOOPS').reduce((s, p) => s + p.mass_kg, 0);
  r.fragSpeed = Math.sqrt(2 * ke / coldMass);
}
function mulberry(a) { return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

// ---- per frame: fill the state textures for both sides ---------------------------------------------------------------------------------
const DESIGN_K = { hot: 1800, armour: 1300, structure: 440, coil: 20, cryostat: 80, cryo: 30 };   // 1.6B allowable classes (left side)
function updateState() {
  const r = run, t = phys(r, u), ramp = Math.min(u / 1.5, 1), n = PARTS.length;
  let k = 1; while (k < r.times.length - 1 && r.times[k] < t) k++;
  const f = r.times[k] > r.times[k - 1] ? Math.min(Math.max((t - r.times[k - 1]) / (r.times[k] - r.times[k - 1]), 0), 1) : 1;
  const flick = 0.85 + 0.15 * Math.sin(u * 23.0) * Math.sin(u * 7.3);
  let hottest = { T: 0, name: '' }, quenched = 0;
  for (let e = 0; e < ENG; e++) {
    const qv = r.quenchVis?.[e], since = qv != null ? u - qv : -1;
    if (since >= 0) quenched++;
    PARTS.forEach((p, i) => {
      const tl = DESIGN_K[p.material] ?? 300;
      stateA.set(0, e, p.index, 300 + (tl - 300) * ramp, 0, 0, 0);
      const pr = r.parts[i];
      const Tk = r.grid[(k - 1) * n + i] * (1 - f) + r.grid[k * n + i] * f;
      const melt = Math.min(Math.max((Tk - pr.melt) / 500, 0), 1), vap = Math.min(Math.max((Tk - pr.melt - 1500) / 2500, 0), 0.92);
      let flash = 0;
      if (r.powerVis != null && p.group === 'ELECTRICAL') { const s = u - r.powerVis; if (s >= 0) flash = Math.max(0, 1 - s / 2.4) * (0.5 + 0.5 * Math.sin(s * 31 + i)); }
      if (since >= 0 && (p.group === 'CLOSURE_COILS' || p.group === 'NOZZLE_LOOPS')) flash = Math.max(flash, Math.exp(-since * 2.2) * 0.8);
      stateA.set(1, e, p.index, Tk, melt, vap, flash);
      if (Tk > hottest.T) hottest = { T: Tk, name: p.label || p.name };
      // fragments
      let dx = 0, dy = 0, dz = 0, ang = 0;
      if (since > 0) {
        const f = r.frag[i], d = f.k * f.sp * 4.0 * since * (reduced ? 0.4 : 1);
        const dir = p.centroid ? new THREE.Vector3(p.centroid.x - burnLocal, p.centroid.y, p.centroid.z).normalize() : new THREE.Vector3(1, 0, 0);
        dx = dir.x * d; dy = dir.y * d; dz = dir.z * d; ang = f.spin * f.k * since;
      }
      stateB.set(0, e, p.index, 0, 0, 0, 0);
      stateB.set(1, e, p.index, dx, dy, dz, ang);
    });
    // plume: intensity, width, raggedness; left nominal, right per event
    const pl = plumes.material.uniforms.uP.value;
    pl[e].set(ramp * flick, 1, 0, 0);
    let I = ramp * flick, w = 1, rag = Math.min(r.v.leak / K.leak0, 1) * 0.35;
    if (r.coldVis != null && u > r.coldVis) { const s = Math.min((u - r.coldVis) / 3, 1); w = 1 + 1.6 * s; rag = Math.max(rag, 0.4 + 0.5 * s); }
    if (since >= 0) { I *= Math.exp(-since * 3); w = 1 + since * 2; rag = 1; }
    pl[ENG + e].set(I, w, rag, 0);
  }
  stateA.tex.needsUpdate = true; stateB.tex.needsUpdate = true;
  // shocks: the unconfined plasma as the field goes (one shell per quenched engine)
  shocks.forEach((m, i) => {
    const qv = r.quenchVis?.[i]; m.userData.on = false;
    if (qv == null || i >= ENG) return;
    const s = u - qv; if (s < 0 || s > 3.2) return;
    m.userData.on = true; const b = new THREE.Vector3(burnLocal, 0, 0).applyMatrix4(engineMats[i]);
    m.position.copy(b); m.scale.setScalar(4 + s * 18); m.material.uniforms.uA.value = (reduced ? 0.3 : 0.8) * Math.exp(-s * 1.6);
  });
  return { t, hottest, quenched };
}

function setSize() {
  const w = stage.clientWidth, h = stage.clientHeight;
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) renderer.setSize(w, h, false);
  return [w, h];
}
function frame(now) {
  const dt = Math.min((now - (last || now)) / 1000, 0.1); last = now;
  const moving = controls.update();
  if (playing) { u = Math.min(u + dt, run.V + run.tail); if (u >= run.V + run.tail) { playing = false; syncPlay(); } dirty = true; }
  if (!dirty && !moving) return;
  dirty = false;
  const info = updateState();
  const [w, h] = setSize();
  const portrait = matchMedia('(max-width: 760px)').matches && h > w * 0.8, both = split === 'split';
  const time = u;
  plumes.material.uniforms.uTime.value = time; cloud.material.uniforms.uTime.value = time; glows.material.uniforms.uTime.value = 0;
  const views = both ? (portrait ? [[0, h / 2, w, h / 2, 0], [0, 0, w, h / 2, 1]] : [[0, 0, w / 2, h, 0], [w / 2, 0, w / 2, h, 1]]) : [[0, 0, w, h, 1]];
  const t0 = performance.now();
  for (const [x, y, vw, vh, side] of views) {
    renderer.setViewport(x, y, vw, vh); renderer.setScissor(x, y, vw, vh);
    camera.aspect = vw / vh; camera.updateProjectionMatrix();
    engineSide.value = side; plumes.material.uniforms.uSide.value = side;
    const pl = plumes.material.uniforms.uP.value, gl = glows.geometry.attributes.aLife;
    let li = 0;
    for (let e = 0; e < ENG; e++) { const P = pl[side * ENG + e]; gl.setXYZW(e, -1e9, 1e12, 10 * Math.min(P.x, 1.4) + 3, 0.8 * Math.min(P.x, 1.2)); li += P.x; }
    gl.needsUpdate = true;
    light.intensity = 1800 * li / ENG + (side ? shocks.reduce((s, m) => s + (m.userData.on ? m.material.uniforms.uA.value * 9000 : 0), 0) : 0);
    cloud.visible = side === 1; shocks.forEach(m => { m.visible = side === 1 && m.userData.on; });
    renderer.render(scene, camera);
    cloud.material.uniforms.uScale.value = vh * renderer.getPixelRatio() * 0.9;
  }
  const ft = performance.now() - t0;
  frames.push(dt * 1000); if (frames.length > 60) frames.shift();
  adapt();
  window.__ign.stats = { calls: renderer.info.render.calls, triangles: renderer.info.render.triangles, frame_ms: frames.reduce((a, b) => a + b, 0) / frames.length,
    cpu_ms: ft, dpr: renderer.getPixelRatio(), particles: run.particles };
  if (now - (frame.hud || 0) > 100) { frame.hud = now; paintHud(info); }
}
function adapt() {              // keep the frame near the budget: lower the pixel ratio after a slow second, at most every 3 s
  if (frames.length < 60 || !playing) return;
  const mean = frames.reduce((a, b) => a + b, 0) / frames.length, now = performance.now();
  if (mean > 45 && dpr > 0.75 && now - (adapt.at || 0) > 3000) { dpr = Math.max(0.75, dpr - 0.25); renderer.setPixelRatio(dpr); adapt.at = now; frames.length = 0; }
}

// ---- HUD, captions, timeline -------------------------------------------------------------------------------------------------------
function paintHud(info) {
  const r = run, o = r.o, t = info.t;
  const rate = u > 0.05 && u < r.V ? (phys(r, u + 0.01) - phys(r, u)) / 0.01 : 0;
  const slow = rate > 0 ? (rate < 1 ? `slowed ${N(1 / rate)}×` : `sped up ${N(rate)}×`) : u >= r.V ? 'after the clock: motion slowed' : '';
  const ex = o.H > o.Q;
  hud.innerHTML = `<div class="hrow"><span>Physical time</span><b>${S(t)}</b><i>${esc(slow)}</i></div>
    ${mode === 'overload' ? `<div class="hrow"><span>Heat / radiators</span><b>assumed away</b><i>the real ratio is ${X(evaluate(BASE()).ratio)}</i></div>`
    : `<div class="hrow ${ex ? 'bad' : 'ok'}"><span>Heat / radiators</span><b>${X(o.ratio)}</b><i>${W(o.H)} for ${W(o.Q)}</i></div>
    <div class="bar"><i style="width:${Math.min(100, 100 * Math.log10(Math.max(o.ratio, 1)) / 5)}%"></i></div>`}
    <div class="hrow ${info.hottest.T > 1700 ? 'bad' : ''}"><span>Hottest part</span><b>${Math.round(info.hottest.T).toLocaleString('en')} K</b><i>${esc(info.hottest.name)}</i></div>
    <div class="hrow ${info.quenched ? 'bad' : ''}"><span>Coils</span><b>${info.quenched ? `${info.quenched} of 4 quenched` : (r.coldVis != null && u > r.coldVis ? 'lost their cold' : 'superconducting')}</b><i>${r.tq ? `${r.o.coil} life ${S(r.tq)}` : ''}</i></div>
    ${mode === 'meltdown' ? `<div class="hrow"><span>Driver power</span><b>assumed supplied</b><i>it needs ${W(evaluate(BASE()).driver_W)}</i></div>`
    : `<div class="hrow ${o.bank_ratio > 1 ? 'bad' : 'ok'}"><span>Driver power</span><b>${W(o.driver_W)}</b><i>${N(o.bank_ratio)}× the 50 MW bank</i></div>`}`;
  const evs = r.events.filter(e => !e.late && e.t <= t + 1e-12);
  const cur = evs[evs.length - 1];
  const key = cur ? cur.id + cur.t : '';
  if (key !== paintHud.key) {
    paintHud.key = key;
    evcap.innerHTML = cur ? `<b>${esc(S(cur.t))} · ${esc(cur.title)}</b><span>${esc(cur.text)}</span>` : '';
    for (const li of document.querySelectorAll('#events .ev')) {
      if (li.dataset.scn !== mode) continue;
      const tt = +li.dataset.t; li.classList.toggle('past', tt <= t); li.classList.toggle('current', cur && li.dataset.ev === cur.id);
    }
  }
  $('clock').textContent = `t = ${S(t)}`;
  $('scrub').value = Math.round(1000 * u / (r.V + r.tail));
}

function designEvents() {
  const ol = $('events');
  ol.querySelectorAll('[data-scn="design"]').forEach(n => n.remove());
  if (mode !== 'design') return;
  ol.insertAdjacentHTML('beforeend', run.events.map(e => `<li class="ev${e.late ? ' late' : ''}" data-scn="design" data-ev="${e.id}" data-t="${e.t}"><b>${esc(e.late ? (e.t === Infinity ? 'check' : 'later') : e.t ? S(e.t) : '0 s')}</b> <span><strong>${esc(e.title)}.</strong> ${esc(e.text)}</span></li>`).join(''));
}

function setMode(m, keepTime) {
  mode = m;
  for (const b of document.querySelectorAll('.ign-modes [data-mode]')) b.setAttribute('aria-selected', String(b.dataset.mode === m));
  document.querySelector('.ign').dataset.mode = m;
  if (!engines) { paintReadouts(); return; }
  run = makeRun(); buildEffects(run);
  if (!keepTime) u = 0;
  paintHud.key = null; designEvents(); paintReadouts();
  playing = !reduced || keepTime === 'play'; syncPlay(); dirty = true;
  window.__ign.run = { mode, tEnd: run.tEnd, V: run.V, events: run.events.map(e => [e.id, e.t]), ratio: run.o.ratio, particles: run.particles, fragSpeed: run.fragSpeed };
}

function syncPlay() { const b = $('play'); b.textContent = playing ? '❚❚' : '▶'; b.setAttribute('aria-label', playing ? 'Pause' : 'Play'); }

// ---- levers -------------------------------------------------------------------------------------------------------------------------
const toPos = (l, v) => l.log ? Math.round(1000 * Math.log(v / l.min) / Math.log(l.max / l.min)) : Math.round(1000 * (v - l.min) / (l.max - l.min));
const fromPos = (l, p) => { const k = p / 1000; const v = l.log ? l.min * Math.pow(l.max / l.min, k) : l.min + (l.max - l.min) * k; return l.log ? +v.toPrecision(3) : +v.toFixed(4); };
const fmtLever = (l, v) => l.pct ? `${(100 * v).toFixed(1)} %` : l.id === 'tau' ? `${N(v)}` : `${N(v)}×`;
const PRESETS = { drawn: {}, best: { att: 1e5, src: 0.67 }, breakthrough: { src: 1e-7, leak: 0, G: 3e6 } };

function paintLevers() {
  for (const l of D.levers) {
    const inp = $(`lv-${l.id}`); if (!inp) continue;
    inp.value = toPos(l, levers[l.id]); $(`lo-${l.id}`).textContent = fmtLever(l, levers[l.id]);
  }
}
function paintReadouts() {
  const o = evaluate(levers), fails = o.fails;
  const row = (label, val, ok, note) => `<tr class="${ok ? 'ok' : 'bad'}"><td>${label}</td><td class="num">${val}</td><td>${ok ? 'holds' : '<b>fails</b>'}</td><td class="meta">${note}</td></tr>`;
  $('readouts').innerHTML = `<p class="first ${fails.length ? 'bad' : 'ok'}">${fails.length ? `<b>Fails first:</b> ${esc(fails[0].what)}${fails[0].t != null ? `, after ${S(fails[0].t)}` : ''}.` : '<b>Holds.</b> Every check passes with these levers. Look at what each lever had to be.'}</p>
  <table><tbody>
   ${row('Heat / radiators', X(o.ratio), o.H <= o.Q, `${W(o.H)} of heat, ${W(o.Q)} of radiator per engine`)}
   ${row('Time to +1000 K', o.melt_s == null ? 'never' : S(o.melt_s), o.melt_s == null, 'engine heat capacity 0.62 TJ')}
   ${row(`Coil life (${o.coil})`, S(o.coil_life_s), o.coil_life_s >= o.run_s, `four burns need ${S(o.run_s)}`)}
   ${row('Driver power', W(o.driver_W), o.driver_W <= K.bank_W, `the budgeted pulse bank gives 50 MW (${N(o.bank_ratio)}×)`)}
   ${row('Added mass', T(o.added_kg), o.added_kg <= K.margin_kg, `shields ${T(o.shield_kg)}, radiators ${T(o.radiator_kg)}; margin ${T(K.margin_kg)}`)}
   ${row('One burn', S(o.burn_s), o.extra_trip_s <= K.allowance_s, `trip allowance ${D.proto.trip_allowance_yr} yr over four burns`)}
  </tbody></table>`;
  window.__ign.design = { levers: { ...levers }, ratio: o.ratio, fails: fails.map(f => f.id) };
}
let leverTimer = 0;
function onLever() {
  paintLevers(); paintReadouts();
  history.replaceState(null, '', `#mode=design&lv=${D.levers.map(l => `${l.id}:${levers[l.id]}`).join(',')}`);
  if (mode !== 'design') setMode('design');
  clearTimeout(leverTimer); leverTimer = setTimeout(() => { if (engines) { setMode('design', 'play'); u = 0; } }, 180);
}

// ---- start ----------------------------------------------------------------------------------------------------------------------------
async function start() {
  D = INLINE ? INLINE.data : await fetch(DATA).then(r => r.json());
  K = D.constants;
  D.partByName = new Map(D.parts.map((p, i) => [p.name, Object.assign(p, { index: i })]));
  PARTS = D.parts;
  levers = BASE();
  const h = /lv=([\w.:,+-]+)/.exec(location.hash);
  if (h) for (const kv of h[1].split(',')) { const [k, v] = kv.split(':'); if (k in levers && isFinite(+v)) levers[k] = +v; }
  const hm = /mode=(\w+)/.exec(location.hash); if (hm && ['overload', 'meltdown', 'design'].includes(hm[1])) mode = hm[1];
  for (const l of D.levers) $(`lv-${l.id}`)?.addEventListener('input', ev => { levers[l.id] = fromPos(l, +ev.target.value); onLever(); });
  for (const b of document.querySelectorAll('[data-preset]')) b.addEventListener('click', () => { levers = { ...BASE(), ...PRESETS[b.dataset.preset] }; onLever(); });
  $('share').addEventListener('click', async () => { try { await navigator.clipboard.writeText(location.href); $('share').textContent = 'Link copied'; } catch { $('share').textContent = 'Copy the address bar'; } });
  for (const b of document.querySelectorAll('.ign-modes [data-mode]')) b.addEventListener('click', () => setMode(b.dataset.mode));
  $('play').addEventListener('click', () => { if (!run) return; if (!playing && u >= run.V + run.tail) u = 0; playing = !playing; syncPlay(); dirty = true; });
  $('restart').addEventListener('click', () => { if (!run) return; u = 0; playing = true; syncPlay(); dirty = true; });
  $('scrub').addEventListener('input', ev => { if (!run) return; u = (+ev.target.value / 1000) * (run.V + run.tail); playing = false; syncPlay(); dirty = true; });
  for (const b of document.querySelectorAll('[data-split]')) b.addEventListener('click', () => {
    split = b.dataset.split; for (const x of document.querySelectorAll('[data-split]')) x.setAttribute('aria-pressed', String(x === b));
    stage.dataset.split = split; dirty = true; });
  stage.dataset.split = split;
  paintLevers(); setMode(mode);
  $('load').addEventListener('click', load);
  if (INLINE || /[#&]autostart/.test(location.hash)) load();
}
function bench(n = 30) {      // measurement only: n synchronous redraws of the current view, each finished with a 1-pixel read
  const gl = renderer.getContext(), px = new Uint8Array(4), t = [];
  for (let i = 0; i < n; i++) { dirty = true; const t0 = performance.now(); frame(t0); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px); t.push(performance.now() - t0); }
  t.sort((a, b) => a - b);
  return { p50: t[Math.floor(n / 2)], p95: t[Math.floor(n * 0.95)], calls_per_side: renderer.info.render.calls, dpr: renderer.getPixelRatio() };
}
window.__ign = { ready: false, bench, evaluate: v => evaluate(v), seek: x => { u = x; playing = false; dirty = true; syncPlay(); }, mode: m => setMode(m), get data() { return D; } };
start();
