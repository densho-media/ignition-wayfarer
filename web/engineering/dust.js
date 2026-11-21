// Engineering · Dust: what hits at speed (tools/story.py writes engineering/dust/ and its dust.json from the dust-impacts study).
// Three views of one open problem. One grain: a grain strikes the Brow stack (sacrificial disruptor layer, the 2.0 m stand-off, the
// shield skin) twice with one camera, on the left at 7 km/s where shields are tested, on the right at the visitor's speed. The trip:
// a schematic Wayfarer flies the Vertex research mission through the T02 dust environment, bow first while accelerating and engine
// first while braking. Your shield: the same trip with the visitor's stand-offs and attitude accuracy. The page computes no new
// spacecraft facts: impact() mirrors lab/studies/dust-impacts/model.py impact() line by line (the site check compares the two at the
// study's check points), and every trip and lever number is read from the study's result. Everything is procedural: a few meshes, one
// streak cloud, one particle cloud per effect, rendered on demand.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const INLINE = window.DUST_INLINE || null;          // the self-contained preview passes its data here instead of fetching it
const DATA = 'dust.json';                           // written by tools/story.py next to the page (engineering/dust/)
const $ = id => document.getElementById(id);
const stage = $('stage'), canvas = $('dust-view'), gate = $('gate'), cstatus = $('cstatus'), hud = $('hud'), evcap = $('evcap');
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const touch = matchMedia('(pointer: coarse)').matches;

let D = null, K = null;
let mode = 'grain', dcase = 'NOMINAL';
let gv = 0, gm = 1e-9;                               // grain speed (m/s) and mass (kg)
let lv = { brow: 2, eng: 0, att: 0.2 };              // the visitor's levers
const REF_V = 7e3;                                   // the left side: where Whipple shields are tested

// ---- formatting -----------------------------------------------------------------------------------------------------------------------
const sig = (v, p = 3) => +v.toPrecision(p);
const N = v => v === 0 ? '0' : Math.abs(v) >= 1e5 || Math.abs(v) < 1e-2 ? v.toExponential(1).replace('e+', 'e') : sig(v).toLocaleString('en');
const CNT = v => v < 0.01 ? (v === 0 ? '0' : v.toExponential(0).replace('e+', 'e')) : v < 10 ? v.toPrecision(2) : Math.round(v).toLocaleString('en');
const J = e => e >= 1e9 ? `${sig(e / 1e9)} GJ` : e >= 1e6 ? `${sig(e / 1e6)} MJ` : e >= 1e3 ? `${sig(e / 1e3)} kJ` : e >= 1 ? `${sig(e)} J`
  : e >= 1e-3 ? `${sig(e * 1e3)} mJ` : e >= 1e-6 ? `${sig(e * 1e6)} µJ` : `${sig(e * 1e9)} nJ`;
const KG = m => m >= 1 ? `${sig(m)} kg` : m >= 1e-3 ? `${sig(m * 1e3)} g` : m >= 1e-6 ? `${sig(m * 1e6)} mg` : m >= 1e-9 ? `${sig(m * 1e9)} µg`
  : m >= 1e-12 ? `${sig(m * 1e12)} ng` : `${N(m)} kg`;
const M_ = x => x >= 1 ? `${sig(x)} m` : x >= 1e-3 ? `${sig(x * 1e3)} mm` : x >= 1e-6 ? `${sig(x * 1e6)} µm` : `${sig(x * 1e9)} nm`;
const KMS = v => v >= 1e6 ? `${Math.round(v / 1e3).toLocaleString('en')} km/s` : v >= 1e4 ? `${sig(v / 1e3)} km/s` : `${sig(v / 1e3, 2)} km/s`;
const TNTF = kg => kg >= 1 ? `${sig(kg)} kg of TNT` : kg >= 1e-3 ? `${sig(kg * 1e3)} g of TNT` : kg >= 1e-6 ? `${sig(kg * 1e6)} mg of TNT` : `${N(kg)} kg of TNT`;
const EV = k => k >= 1 ? `${sig(k)} keV` : k >= 1e-3 ? `${sig(k * 1e3)} eV` : `${N(k * 1e3)} eV`;
const T = t => t >= 1e6 ? `${sig(t / 1e6)} kt` : `${Math.round(t).toLocaleString('en')} t`;
const OUT = { stopped: 'stopped by the layer', scorched: 'stopped; the skin is scorched', cratered: 'the skin is cratered', breach: 'the skin is breached' };

// ---- the impact model (model.py impact) ------------------------------------------------------------------------------------------------
const perf = (t, k) => { const p = t / K.perf_ratio; return 2 * Math.PI * p ** 3 / (3 * k); };
const defeat = (S, c) => { const b = K.bumper[c]; return b.F_allow * Math.PI * (S * Math.tan(b.alpha_deg * Math.PI / 180)) ** 2 / b.g; };
function regimeOf(v) { let out = D.regimes[0]; for (const r of D.regimes) if (v / 1e3 >= r[0]) out = r; return out; }
function impact(m, v, c = 'NOMINAL', st = D.stack) {
  const k = K.k_crater[c], b = K.bumper[c];
  const bumper = st.bumper_m, S = st.standoff_m, wall = st.wall_m;
  const E = 0.5 * m * v * v;
  const d = Math.cbrt(6 * m / (Math.PI * K.rho_grain));
  const crater = Math.cbrt(3 * k * E / (2 * Math.PI));
  const kms = v / 1e3;
  const disrupt = bumper > 0 && kms >= 3.0 && bumper >= K.t_over_d[c] * d;
  const R = S * Math.tan(b.alpha_deg * Math.PI / 180);
  let F = null, breach, outcome, hole, wallCrater = null;
  if (disrupt) {
    F = R > 0 ? b.g * E / (Math.PI * R * R) : Infinity;
    breach = F > b.F_allow;
    outcome = breach ? 'breach' : (F > 0.1 * b.F_allow ? 'scorched' : 'stopped');
    hole = bumper ? Math.min(2 * Math.max(d, crater), 2 * bumper + d) : 0.0;
  } else {
    const through = bumper === 0 || E > perf(bumper, k);
    if (!through) { outcome = 'stopped'; breach = false; hole = 0.0; wallCrater = 0.0; }
    else { hole = bumper ? 2 * Math.max(d, crater) : 0.0; breach = E > perf(wall, k); wallCrater = crater; outcome = breach ? 'breach' : 'cratered'; }
  }
  return { E_J: E, tnt_kg: E / K.tnt, d_m: d, keV_per_u: 0.5 * K.amu * v * v / K.ev / 1e3, regime: regimeOf(v)[1], disrupted: disrupt,
    cloud_r_m: disrupt ? R : null, cloud_J_m2: F, allow_J_m2: b.F_allow, crater_m: crater, wall_crater_m: wallCrater, bumper_hole_m: hole,
    outcome, breach, defeat_E_J: S > 0 ? defeat(S, c) : 0.0 };
}
function largestStopped(v, c) {
  let lo = 1e-21, hi = 10;
  if (impact(lo, v, c).breach) return 0;
  for (let i = 0; i < 200; i++) { const mid = Math.sqrt(lo * hi); if (impact(mid, v, c).breach) hi = mid; else lo = mid; }
  return lo;
}

// ---- shared rendering ---------------------------------------------------------------------------------------------------------------
let renderer, camera, controls, scene, grainScene, tripScene;
let u = 0, playing = !reduced, split = 'split', dirty = true, last = 0, frames = [], dpr = 1;
const rng = a => () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };

function glowTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d'), gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.18, 'rgba(255,255,255,0.75)'); gr.addColorStop(0.45, 'rgba(255,255,255,0.18)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
function stars(n, R) {
  const p = new Float32Array(n * 3), c = new Float32Array(n * 3), r = rng(7);
  for (let i = 0; i < n; i++) {
    const z = r() * 2 - 1, a = r() * Math.PI * 2, s = Math.sqrt(1 - z * z);
    p.set([R * s * Math.cos(a), R * z, R * s * Math.sin(a)], i * 3);
    const b = 0.25 + r() ** 3 * 0.9; c.set([b * 0.9, b * 0.95, b], i * 3);
  }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(p, 3)); g.setAttribute('color', new THREE.BufferAttribute(c, 3));
  const pts = new THREE.Points(g, new THREE.PointsMaterial({ size: 1.6, sizeAttenuation: false, vertexColors: true, transparent: true, depthWrite: false }));
  pts.frustumCulled = false; return pts;
}
function lights(s, scale, kx = -1) {
  s.add(new THREE.HemisphereLight(0x9fb4d8, 0x0a0c12, 0.55));
  const key = new THREE.DirectionalLight(0xfff1de, 2.4); key.position.set(kx, 1.4, 1.8).multiplyScalar(scale); s.add(key);
  const rim = new THREE.DirectionalLight(0x8aa6ff, 0.7); rim.position.set(1.5, -0.4, -1.2).multiplyScalar(scale); s.add(rim);
}

// A plate whose impact spot heats, scorches and opens: uniforms in plate-local y, z (metres).
function plateMaterial(color, rough) {
  const m = new THREE.MeshStandardMaterial({ color, metalness: 0.35, roughness: rough });
  const U = { uHit: { value: new THREE.Vector2() }, uSpot: { value: 0 }, uHeat: { value: 0 }, uScorch: { value: 0 }, uHole: { value: 0 }, uCrack: { value: 0 } };
  m.userData.U = U;
  m.onBeforeCompile = sh => {
    Object.assign(sh.uniforms, U);
    sh.vertexShader = 'varying vec3 vLoc;\n' + sh.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\n vLoc = position;');
    sh.fragmentShader = `varying vec3 vLoc; uniform vec2 uHit; uniform float uSpot, uHeat, uScorch, uHole, uCrack;
      float dh(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }\n` + sh.fragmentShader
      .replace('#include <clipping_planes_fragment>', `#include <clipping_planes_fragment>
        float dr = length(vLoc.yz - uHit);
        float ang = atan(vLoc.z - uHit.y, vLoc.y - uHit.x);
        float jag = 1.0 + 0.18 * sin(ang * 7.0) + 0.1 * sin(ang * 13.0 + 1.3);
        if (uHole > 0.0 && dr < uHole * jag) discard;`)
      .replace('#include <color_fragment>', `#include <color_fragment>
        float sp = exp(-pow(dr / max(uSpot, 1e-4), 2.0));
        diffuseColor.rgb *= 1.0 - 0.8 * uScorch * sp;
        float ray = uCrack * smoothstep(0.92, 1.0, sin(ang * 9.0 + dh(floor(vec2(ang * 3.0, 0.0))) * 6.0)) * exp(-dr / max(uSpot * 1.6, 1e-3));
        diffuseColor.rgb *= 1.0 - 0.6 * ray;`)
      .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
        float rim = uHole > 0.0 ? exp(-pow((dr - uHole * jag) / max(uHole * 0.35, 0.01), 2.0)) : 0.0;
        totalEmissiveRadiance += vec3(1.0, 0.42, 0.12) * uHeat * (sp + 1.6 * rim) + vec3(1.0, 0.25, 0.08) * ray * uHeat * 0.6;`);
  };
  return m;
}

// Additive particle cloud: everything is a function of uT (seconds since the impact), so scrubbing works both ways.
function cloudMaterial() {
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { uT: { value: -1 }, uA: { value: new THREE.Vector3() }, uS: { value: 2 }, uR: { value: 1 }, uN: { value: 1 }, uC1: { value: new THREE.Color() },
      uC2: { value: new THREE.Color() }, uIntact: { value: 0 }, uBreach: { value: 0 }, uHoleR: { value: 0 }, uScale: { value: 600 }, uSpeed: { value: 1 } },
    vertexShader: `attribute vec4 aSeed; uniform float uT, uS, uR, uN, uIntact, uBreach, uHoleR, uScale, uSpeed; uniform vec3 uA, uC1, uC2;
      varying vec3 vC; varying float vA;
      void main() {
        float age = uT - aSeed.w * 0.12;
        bool on = aSeed.x < uN && age > 0.0;
        float ph = aSeed.y * 6.2831853, rr = sqrt(aSeed.z);
        vec3 p = uA; float life = 2.4;
        bool back = aSeed.x < uN * 0.18;                       // ejecta thrown back toward the dust
        if (back) {
          vec3 dir = normalize(vec3(0.6 + aSeed.z, cos(ph) * (0.4 + aSeed.x), sin(ph) * (0.4 + aSeed.x)));
          p += dir * age * uSpeed * (0.6 + aSeed.y) * 1.2; life = 1.4;
        } else {
          float spread = mix(uR, 0.06 + 0.05 * uR, uIntact) * rr;     // radius reached at the wall
          vec3 tgt = vec3(0.0, uA.y + cos(ph) * spread, uA.z + sin(ph) * spread);
          float tr = age * uSpeed * (0.7 + 0.6 * aSeed.y);              // fraction of the way to the wall
          if (tr < 1.0) p = mix(uA, tgt, tr);
          else {
            float over = (tr - 1.0) / max(uSpeed, 1e-3);
            bool through = uBreach > 0.5 && length(tgt.yz - uA.yz) < max(uHoleR * 2.2, 0.3);
            vec3 sd = through ? vec3(-1.0, cos(ph) * 0.5, sin(ph) * 0.5) : vec3(0.08 + 0.2 * aSeed.z, cos(ph) * 0.9, sin(ph) * 0.9);
            p = tgt + sd * over * (through ? 2.4 : 0.35);
          }
        }
        float k = age / life;
        vA = (!on || k > 1.0) ? 0.0 : (1.0 - k) * (1.0 - k);
        vC = mix(uC1, uC2, clamp(age * 1.2 + aSeed.y * 0.3, 0.0, 1.0));
        vec4 mv = modelViewMatrix * vec4(p, 1.0); gl_Position = projectionMatrix * mv;
        gl_PointSize = vA > 0.0 ? clamp((0.012 + 0.02 * aSeed.z) * uScale / -mv.z, 1.0, 24.0) : 0.0;
      }`,
    fragmentShader: `varying vec3 vC; varying float vA;
      void main() { vec2 d = gl_PointCoord - 0.5; float r = dot(d, d) * 4.0; if (r > 1.0) discard; gl_FragColor = vec4(vC * vA * (1.0 - r), 1.0); }`,
  });
}
function shellMaterial() {
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { uA: { value: 0 }, uC: { value: new THREE.Color(0.8, 0.75, 1) } },
    vertexShader: `varying vec3 vN; varying vec3 vV; void main() { vec4 mv = modelViewMatrix * vec4(position, 1.0); vV = normalize(-mv.xyz);
      vN = normalize(normalMatrix * normal); gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `uniform float uA; uniform vec3 uC; varying vec3 vN; varying vec3 vV;
      void main() { float rim = pow(1.0 - abs(dot(vN, vV)), 2.5); gl_FragColor = vec4(uC * uA * (0.1 + rim), 1.0); }`,
  });
}

// ---- one grain ------------------------------------------------------------------------------------------------------------------------
const G = {};                       // grain-scene objects
const REG_COL = { 'bounces and dents': [1, 0.62, 0.3], shatters: [0.85, 0.85, 0.9], melts: [1, 0.55, 0.2], vaporises: [1, 0.88, 0.62],
  'turns to plasma': [0.72, 0.62, 1], 'beyond any test': [0.9, 0.85, 1] };
const GT = { approach: 1.2, cross: 0.9, V: 5.5 };   // visual seconds: impact on the layer at 1.2 s, the cloud reaches the skin 0.9 s later

function buildGrain() {
  const s = new THREE.Scene(); s.background = new THREE.Color(0x05070b);
  lights(s, 10, 2.2);
  // a section cut through the stack: 2.6 m tall, cut 0.45 m beside the impact so that the gap between layer and skin can be seen
  const P = 2.6, Z0 = -1.55, Z1 = 0.45, S = D.stack.standoff_m;
  const plate = (t, c, r) => new THREE.Mesh(new THREE.BoxGeometry(t, P, Z1 - Z0).translate(0, 0, (Z0 + Z1) / 2), plateMaterial(c, r));
  G.wall = plate(0.06, 0x6b7480, 0.55); s.add(G.wall);
  G.bump = plate(0.035, 0xa08a55, 0.7); G.bump.position.x = S; s.add(G.bump);
  // the plates' edges and the stand-off rails, so the stack reads as a section of the Brow
  const rail = new THREE.MeshStandardMaterial({ color: 0x39404a, metalness: 0.6, roughness: 0.5 });
  for (const [y, z] of [[-P / 2, Z0], [-P / 2, Z1], [P / 2, Z0], [P / 2, Z1]]) {
    const r = new THREE.Mesh(new THREE.BoxGeometry(S, 0.05, 0.05), rail); r.position.set(S / 2, y, z); s.add(r);
  }
  G.grain = new THREE.Mesh(new THREE.SphereGeometry(1, 16, 12), new THREE.MeshBasicMaterial({ color: 0xffe8c8 })); s.add(G.grain);
  G.streak = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 1, 1, 10, 1, true).rotateZ(-Math.PI / 2).translate(0.5, 0, 0),
    new THREE.MeshBasicMaterial({ color: 0xbfb4ff, transparent: true, opacity: 0.6, blending: THREE.AdditiveBlending, depthWrite: false }));
  s.add(G.streak);
  const tex = glowTexture();
  G.flash = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, color: 0xffffff, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false }));
  G.flash2 = G.flash.clone(); G.flash2.material = G.flash.material.clone(); s.add(G.flash, G.flash2);
  G.shell = new THREE.Mesh(new THREE.SphereGeometry(1, 32, 16), shellMaterial()); s.add(G.shell);
  const n = 1400, seed = new Float32Array(n * 4), r = rng(11);
  for (let i = 0; i < n; i++) seed.set([i / n, r(), r(), r()], i * 4);
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3), 3)); g.setAttribute('aSeed', new THREE.BufferAttribute(seed, 4));
  G.cloud = new THREE.Points(g, cloudMaterial()); G.cloud.frustumCulled = false; s.add(G.cloud);
  G.light = new THREE.PointLight(0xffd6a8, 0, 12, 1.6); s.add(G.light);
  s.add(stars(1200, 400));
  G.hit = new THREE.Vector2(0.1, 0.0);
  return s;
}
// What one side shows at visual time t for the grain result r.
function grainSide(r, v, t) {
  const S = D.stack.standoff_m, hit = G.hit, eL = Math.log10(Math.max(r.E_J, 1e-12));
  const col = REG_COL[r.regime] || [1, 1, 1];
  const ti = GT.approach, ta = t - ti;
  // grain and streak: drawn 40 times its size (at least 4 mm) so it can be seen
  const vis = Math.min(Math.max(r.d_m * 40, 0.004), 0.06);
  const x0 = 9, xg = t < ti ? S + (x0 - S) * (1 - t / ti) : S;
  G.grain.visible = t < ti || (!r.disrupted && r.outcome !== 'stopped' && ta < GT.cross);
  if (!r.disrupted && ta >= 0) G.grain.position.set(S * (1 - Math.min(ta / GT.cross, 1)), hit.x, hit.y);
  else G.grain.position.set(xg, hit.x, hit.y);
  G.grain.scale.setScalar(vis);
  const sl = Math.min(0.4 + 1.1 * Math.log10(v / 1e3 + 1), 6) * (t < ti ? 1 : 0);
  G.streak.visible = sl > 0; G.streak.position.copy(G.grain.position); G.streak.scale.set(sl, vis * 0.9, vis * 0.9);
  G.streak.material.color.setRGB(...(v > 1e5 ? [0.75, 0.7, 1] : [1, 0.85, 0.65]));
  // flash on the layer
  const fs = Math.min(Math.max(0.12 + 0.14 * (eL + 7), 0.08), 3.4);
  const fa = ta < 0 ? 0 : Math.exp(-ta * 3.2) * (1 + Math.max(eL, 0) * 0.15);
  G.flash.visible = fa > 0.003; G.flash.position.set(S + 0.02, hit.x, hit.y); G.flash.scale.setScalar(fs * (0.7 + 0.6 * Math.min(ta * 6, 1)));
  G.flash.material.color.setRGB(col[0] * fa, col[1] * fa, col[2] * fa);
  // the cloud reaching the skin
  const tw = ta - GT.cross, q = r.cloud_J_m2 != null ? r.cloud_J_m2 / r.allow_J_m2 : (r.wall_crater_m ? 1 : 0);
  const wa = tw < 0 ? 0 : Math.exp(-tw * 2.2) * Math.min(Math.max(Math.log10(q) + 2, 0), 3) / 2;
  G.flash2.visible = wa > 0.003; G.flash2.position.set(0.05, hit.x, hit.y); G.flash2.scale.setScalar((r.cloud_r_m || 0.3) * 1.6);
  G.flash2.material.color.setRGB(1 * wa, 0.5 * wa, 0.25 * wa);
  // shock shell for impacts beyond any test
  const sh = r.regime === 'beyond any test' || r.regime === 'turns to plasma';
  G.shell.visible = sh && ta > 0 && ta < 1.2;
  if (G.shell.visible) { G.shell.position.set(S, hit.x, hit.y); G.shell.scale.setScalar(0.05 + ta * (0.6 + 0.12 * Math.max(eL, 0))); G.shell.material.uniforms.uA.value = (1 - ta / 1.2) * Math.min(0.2 + 0.1 * Math.max(eL, 0), 1.2); }
  // particles
  const U = G.cloud.material.uniforms;
  U.uT.value = ta; U.uA.value.set(S, hit.x, hit.y); U.uR.value = r.disrupted ? r.cloud_r_m : 0.08; U.uIntact.value = r.disrupted ? 0 : 1;
  U.uN.value = r.outcome === 'stopped' && !r.disrupted ? 0.08 : Math.min(Math.max((eL + 7) / 12, 0.12), 1);
  U.uSpeed.value = 1 / GT.cross; U.uBreach.value = r.breach ? 1 : 0;
  U.uC1.value.setRGB(...col); U.uC2.value.setRGB(...(r.regime === 'shatters' || r.regime === 'bounces and dents' ? [0.5, 0.48, 0.45] : [1, 0.35, 0.12]));
  // plates: the layer's hole and glow, the skin's scorch, crater or breach
  const B = G.bump.material.userData.U, W = G.wall.material.userData.U;
  B.uHit.value.copy(hit); W.uHit.value.copy(hit);
  const hb = r.bumper_hole_m ? Math.min(Math.max(r.bumper_hole_m * 0.5 * 3, 0.012), 0.5) : 0;
  B.uHole.value = ta > 0 ? hb : 0; B.uSpot.value = Math.max(hb * 3, 0.05); B.uHeat.value = ta > 0 ? Math.min(Math.max(eL + 4, 0) / 6, 2.2) * Math.exp(-ta * 0.9) + (hb ? 0.4 : 0) : 0;
  B.uScorch.value = ta > 0 && hb ? 0.8 : 0; B.uCrack.value = 0;
  const on = tw > 0;
  if (r.disrupted) {
    const sc = Math.min(Math.max(Math.log10(Math.max(q, 1e-9)) + 2.3, 0) / 2.3, 1.4);
    W.uSpot.value = r.cloud_r_m * 0.7; W.uScorch.value = on ? Math.min(sc, 1) : 0;
    W.uHeat.value = on ? sc * sc * (r.breach ? 1.2 : 0.35) * (0.4 + 1.6 * Math.exp(-tw * 1.1)) : 0;
    W.uHole.value = on && r.breach ? Math.min(0.06 + 0.22 * Math.log10(q), 0.75) : 0; W.uCrack.value = on && r.breach ? 1 : 0;
  } else {
    const cr = r.wall_crater_m ? Math.max(r.wall_crater_m * 6, 0.02) : 0;
    W.uSpot.value = Math.max(cr * 2, 0.04); W.uScorch.value = on && cr ? 0.9 : 0; W.uHeat.value = on && cr ? 1.2 * Math.exp(-tw) : 0;
    W.uHole.value = on && r.breach ? Math.max(cr, 0.04) : 0; W.uCrack.value = on && r.breach ? 0.6 : 0;
  }
  G.light.position.set(S - 0.3, hit.x, hit.y);
  G.light.intensity = 2.5 * fa * Math.min(Math.max(eL + 4, 0.2), 10) + 3 * wa;
}

// ---- the trip -------------------------------------------------------------------------------------------------------------------------
const TR = {};
const SHIP = { brow_x: 122.5, aft_x: -167, eng_r: 11.4358, eng_a: 24, eng_len: 32, eng_x: -164.5 };
function buildTrip() {
  const s = new THREE.Scene(); s.background = new THREE.Color(0x05070b);
  lights(s, 400, 1.2);
  const ship = new THREE.Group(); s.add(ship); TR.ship = ship;
  const metal = (c, r = 0.5, m = 0.5) => new THREE.MeshStandardMaterial({ color: c, roughness: r, metalness: m });
  // the Brow: flat hub to r 7.4 m at x 122.5, cone to r 45 m at x 119.5, a conical truss behind it (MODEL.md, Forward defense)
  const lathe = new THREE.LatheGeometry([new THREE.Vector2(0.01, 122.5), new THREE.Vector2(7.4, 122.5), new THREE.Vector2(45, 119.5), new THREE.Vector2(45, 116.4),
    new THREE.Vector2(7, 112), new THREE.Vector2(0.01, 112)].map(p => new THREE.Vector2(p.x, p.y)), 72);
  lathe.rotateZ(-Math.PI / 2);
  TR.brow = new THREE.Mesh(lathe, metal(0x8a7448, 0.75, 0.25)); ship.add(TR.brow);
  TR.layer = new THREE.Mesh(new THREE.CircleGeometry(45, 72).rotateY(Math.PI / 2), new THREE.MeshStandardMaterial({ color: 0xc8a861, roughness: 0.8,
    metalness: 0.1, transparent: true, opacity: 0.55, side: THREE.DoubleSide, depthWrite: false }));
  ship.add(TR.layer);
  const body = new THREE.Mesh(new THREE.CylinderGeometry(6.5, 6.5, SHIP.brow_x - 3 - SHIP.aft_x, 32).rotateZ(Math.PI / 2), metal(0x7c8590, 0.55, 0.55));
  body.position.x = (SHIP.brow_x - 3 + SHIP.aft_x) / 2; ship.add(body);
  TR.rings = [];
  for (const x of [72, 46]) { const t = new THREE.Mesh(new THREE.TorusGeometry(30, 4.6, 14, 64).rotateY(Math.PI / 2), metal(0x6f8a74, 0.6, 0.35)); t.position.x = x; ship.add(t); TR.rings.push(t);
    for (let k = 0; k < 4; k++) { const sp = new THREE.Mesh(new THREE.CylinderGeometry(0.9, 0.9, 60), metal(0x5d6670)); sp.position.set(x, 0, 0); sp.rotation.x = k * Math.PI / 4; ship.add(sp); } }
  TR.blades = [];
  for (let k = 0; k < 4; k++) {
    const a = Math.PI / 4 + k * Math.PI / 2;
    const b = new THREE.Mesh(new THREE.BoxGeometry(182, 30.5, 0.3), metal(0x93552c, 0.55, 0.4));
    b.position.set(-110 + 91, Math.cos(a) * (6.5 + 15.25), Math.sin(a) * (6.5 + 15.25)); b.rotation.x = a - Math.PI / 2 + Math.PI / 2; ship.add(b); TR.blades.push(b);
  }
  TR.engines = [];
  for (let k = 0; k < 4; k++) {
    const a = Math.PI / 4 + k * Math.PI / 2;
    const e = new THREE.Mesh(new THREE.CylinderGeometry(SHIP.eng_r, SHIP.eng_r * 0.85, SHIP.eng_len, 32, 1, true).rotateZ(Math.PI / 2), metal(0x5b5f6a, 0.4, 0.75));
    e.material.side = THREE.DoubleSide;
    e.position.set(SHIP.eng_x - SHIP.eng_len / 2, Math.cos(a) * SHIP.eng_a, Math.sin(a) * SHIP.eng_a); ship.add(e); TR.engines.push(e);
    const ring = new THREE.Mesh(new THREE.RingGeometry(8, SHIP.eng_r, 40).rotateY(-Math.PI / 2), metal(0x9a7b4f, 0.6, 0.5));
    ring.material.side = THREE.DoubleSide; ring.position.set(SHIP.eng_x - SHIP.eng_len, e.position.y, e.position.z); ship.add(ring);
  }
  const yoke = new THREE.Mesh(new THREE.CylinderGeometry(26, 26, 3, 32, 1, true).rotateZ(Math.PI / 2), metal(0x4c525c)); yoke.material.side = THREE.DoubleSide;
  yoke.position.x = SHIP.aft_x + 1; ship.add(yoke);
  TR.engBumpers = new THREE.Group(); ship.add(TR.engBumpers);
  for (const e of TR.engines) { const d = new THREE.Mesh(new THREE.CircleGeometry(SHIP.eng_r, 40).rotateY(-Math.PI / 2), TR.layer.material.clone()); d.userData.y = e.position.y; d.userData.z = e.position.z; TR.engBumpers.add(d); }
  // dust: streaks in world space, flowing past the ship opposite to its motion (+x)
  const n = 900, seg = new Float32Array(n * 2 * 4), r = rng(5);
  for (let i = 0; i < n; i++) { const a = r() * 6.283, rr = 8 + Math.sqrt(r()) * 150, ph = r(); for (let e = 0; e < 2; e++) seg.set([Math.cos(a) * rr, Math.sin(a) * rr, ph, e], (i * 2 + e) * 4); }
  const sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 6), 3)); sg.setAttribute('aSeed', new THREE.BufferAttribute(seg, 4));
  TR.dust = new THREE.LineSegments(sg, new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { uT: { value: 0 }, uLen: { value: 30 }, uDir: { value: new THREE.Vector3(-1, 0, 0) }, uA: { value: 0.5 }, uN: { value: 1 } },
    vertexShader: `attribute vec4 aSeed; uniform float uT, uLen, uA, uN; uniform vec3 uDir; varying float vA;
      void main() { float L = 900.0; float s = fract(aSeed.z + uT * 0.35) * L - L * 0.5;
        vec3 side = normalize(cross(uDir, vec3(0.0, 0.0, 1.0)) + 1e-4); vec3 up = cross(side, uDir);
        vec3 p = uDir * s + side * aSeed.x + up * aSeed.y - uDir * uLen * aSeed.w;
        vA = (fract(aSeed.z * 13.7) < uN ? uA : 0.0) * (aSeed.w < 0.5 ? 1.0 : 0.0) * (1.0 - abs(s) / (L * 0.5));
        gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0); }`,
    fragmentShader: `varying float vA; void main() { gl_FragColor = vec4(vec3(0.72, 0.7, 0.95) * vA, 1.0); }`,
  }));
  TR.dust.frustumCulled = false; s.add(TR.dust);
  // impact sparks: a pool of points with birth times, written on the CPU as the clock passes
  const m = 600, sp = new Float32Array(m * 3), life = new Float32Array(m * 4), col = new Float32Array(m * 3);
  life.fill(-1e9);
  const pg = new THREE.BufferGeometry(); pg.setAttribute('position', new THREE.BufferAttribute(sp, 3)); pg.setAttribute('aLife', new THREE.BufferAttribute(life, 4)); pg.setAttribute('color', new THREE.BufferAttribute(col, 3));
  TR.sparks = new THREE.Points(pg, new THREE.ShaderMaterial({ transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending,
    uniforms: { uT: { value: 0 }, uScale: { value: 600 } },
    vertexShader: `attribute vec4 aLife; attribute vec3 color; uniform float uT, uScale; varying vec3 vC; varying float vA;
      void main() { float age = uT - aLife.x, k = age / aLife.y; vA = (age < 0.0 || k > 1.0) ? 0.0 : (1.0 - k) * aLife.w; vC = color;
        vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_Position = projectionMatrix * mv;
        gl_PointSize = vA > 0.0 ? clamp(aLife.z * uScale / -mv.z * (0.6 + 0.6 * (1.0 - k)), 1.5, 48.0) : 0.0; }`,
    fragmentShader: `varying vec3 vC; varying float vA; void main() { vec2 d = gl_PointCoord - 0.5; float r = dot(d, d) * 4.0; if (r > 1.0) discard;
      gl_FragColor = vec4(vC * vA * (1.0 - r) * (1.0 - r), 1.0); }`,
  }));
  TR.sparks.frustumCulled = false; TR.sparkHead = 0; s.add(TR.sparks);
  s.add(stars(1600, 4000));
  return s;
}

// The trip's clock: every model row gets equal visual time, each flip three seconds.
let TRIP = null;
function tripData() {
  const t = D.trip[dcase], cols = t.cols, ix = Object.fromEntries(cols.map((c, i) => [c, i]));
  const rows = t.rows, vis = [0];
  for (let i = 1; i < rows.length; i++) vis.push(vis[i - 1] + (rows[i][ix.orient] === 'BROADSIDE' || rows[i - 1][ix.orient] === 'BROADSIDE' ? 1.6 : 0.16));
  // shield mode: scale each counter to the lever's end-of-trip total (the shape over time is the drawn trip's)
  const L = D.levers[dcase], end = rows[rows.length - 1];
  const scale = { brow: 1, engines: 1, blades: 1, rings: 1, body: 1, optics: 1 };
  if (mode === 'shield') {
    const o = shieldNumbers();
    for (const k of ['brow', 'engines', 'blades', 'rings', 'body']) scale[k] = end[ix[`cum_${k}`]] > 0 ? o[k] / end[ix[`cum_${k}`]] : 0;
  }
  TRIP = { t, ix, rows, vis, V: vis[vis.length - 1], scale, L, flash: {} };
  for (const k of ['brow', 'engines', 'blades', 'rings', 'body']) TRIP.flash[k] = Math.max(1, end[ix[`cum_${k}`]] * scale[k] / 120);
}
function rowAt(uu) {
  const { vis, rows } = TRIP;
  let i = 0; while (i < vis.length - 2 && vis[i + 1] <= uu) i++;
  const f = Math.min(Math.max((uu - vis[i]) / (vis[i + 1] - vis[i]), 0), 1);
  return { i, f, a: rows[i], b: rows[i + 1] };
}
const lerp = (a, b, f) => a + (b - a) * f;
function tripValue(k, uu) { const { a, b, f } = rowAt(uu); const j = TRIP.ix[k]; return lerp(a[j], b[j], f); }
function spark(pos, size, c, life, now) {
  const g = TR.sparks.geometry, i = TR.sparkHead; TR.sparkHead = (i + 1) % g.attributes.position.count;
  g.attributes.position.setXYZ(i, pos.x, pos.y, pos.z); g.attributes.aLife.setXYZW(i, now, life, size, 1); g.attributes.color.setXYZ(i, ...c);
  g.attributes.position.needsUpdate = g.attributes.aLife.needsUpdate = g.attributes.color.needsUpdate = true;
}
const ITEM_COL = { brow: [1, 0.3, 0.2], engines: [1, 0.25, 0.15], blades: [1, 0.5, 0.15], rings: [1, 0.2, 0.3], body: [1, 0.2, 0.3] };
function itemPoint(k, r) {
  const v = new THREE.Vector3();
  if (k === 'brow' || k === 'layer') { const a = r() * 6.283, rr = 45 * Math.sqrt(r()); v.set(k === 'layer' ? TR.layer.position.x + 0.3 : SHIP.brow_x + 0.5, Math.cos(a) * rr, Math.sin(a) * rr); }
  else if (k === 'engines') { const e = TR.engines[Math.floor(r() * 4)], a = r() * 6.283, rr = SHIP.eng_r * Math.sqrt(r()); v.set(SHIP.eng_x - SHIP.eng_len - 0.5, e.position.y + Math.cos(a) * rr, e.position.z + Math.sin(a) * rr); }
  else if (k === 'blades') { const b = TR.blades[Math.floor(r() * 4)]; const k2 = 1.2 + 0.5 * r(); v.set(b.position.x + (r() - 0.5) * 182, b.position.y * k2, b.position.z * k2); }
  else if (k === 'rings') { const t = TR.rings[Math.floor(r() * 2)], a = r() * 6.283; v.set(t.position.x, Math.cos(a) * 30, Math.sin(a) * 30); }
  else { v.set(SHIP.aft_x + r() * 280, (r() - 0.5) * 12, (r() - 0.5) * 12); }
  return v.applyMatrix4(TR.ship.matrixWorld);
}
let lastTripU = 0;
const sparkRng = rng(99);
function tripUpdate() {
  const { a, b, f } = rowAt(u), ix = TRIP.ix;
  // orientation: bow first is the ship's +x into the dust; engine first turns it round; the flips turn it in their own rows
  let yaw = a[ix.orient] === 'ENGINE_FIRST' ? Math.PI : 0;
  if (a[ix.orient] === 'BROADSIDE') yaw = Math.PI * f;
  else if (b[ix.orient] === 'BROADSIDE') yaw = 0;
  TR.ship.rotation.y = yaw; TR.ship.updateMatrixWorld(true);
  const v = lerp(a[ix.v], b[ix.v], f), r = lerp(a[ix.r], b[ix.r], f);
  const vg = r > 30 ? 26e3 : 20e3, ab = Math.atan(vg / v);
  const dir = new THREE.Vector3(-Math.cos(ab), -Math.sin(ab), 0);
  const U = TR.dust.material.uniforms;
  U.uDir.value.copy(dir); U.uT.value = u * (0.4 + 0.6 * Math.min(v / K.v_cruise, 1)); U.uLen.value = 4 + 90 * Math.min(v / K.v_cruise, 1);
  const rate = lerp(a[ix.lead_1J_per_s], b[ix.lead_1J_per_s], f);
  U.uN.value = Math.min(Math.max(Math.log10(Math.max(lerp(a[ix.lead_per_s], b[ix.lead_per_s], f), 1e-6)) / 7, 0.05), 1);
  U.uA.value = 0.35 + 0.4 * Math.min(v / K.v_cruise, 1);
  TR.layer.position.x = SHIP.brow_x + (mode === 'shield' ? lv.brow : D.stack.standoff_m);
  TR.layer.visible = true;
  TR.engBumpers.visible = mode === 'shield' && lv.eng > 0;
  for (const d of TR.engBumpers.children) d.position.set(SHIP.eng_x - SHIP.eng_len - lv.eng, d.userData.y, d.userData.z);
  // sparks: the leading face's grains above 1 J, one spark for many; red sparks for breaches (one per TRIP.flash[k] events)
  const now = u;
  if (u > lastTripU && u - lastTripU < 1) {
    const steps = Math.min(40, Math.round(Math.log10(1 + lerp(a[ix.lead_per_s], b[ix.lead_per_s], f)) * 4 * (u - lastTripU) / 0.16 + sparkRng() * 0.6));
    const lead = a[ix.orient] === 'BOW_FIRST' ? 'brow' : a[ix.orient] === 'ENGINE_FIRST' ? 'engines' : null;
    for (let s = 0; s < steps && lead; s++) {
      const p = itemPoint(lead === 'brow' ? 'layer' : lead, sparkRng);
      spark(p, 4 + 4 * sparkRng(), [0.9, 0.86, 1], 0.45, now);
    }
    for (const k of ['brow', 'engines', 'blades', 'rings', 'body']) {
      const c0 = tripValue(`cum_${k}`, lastTripU) * TRIP.scale[k], c1 = tripValue(`cum_${k}`, u) * TRIP.scale[k];
      const nf = Math.min(Math.floor(c1 / TRIP.flash[k]) - Math.floor(c0 / TRIP.flash[k]), 12);
      for (let s = 0; s < nf; s++) spark(itemPoint(k, sparkRng), (k === 'brow' || k === 'engines' ? 14 : 9) + 6 * sparkRng(), ITEM_COL[k], 1.1, now);
    }
  }
  lastTripU = u;
  TR.sparks.material.uniforms.uT.value = now;
  return { v, r, rate, row: a, f, W: lerp(a[ix.lead_W], b[ix.lead_W], f), day: lerp(a[ix.t_d], b[ix.t_d], f) };
}

// ---- the visitor's levers --------------------------------------------------------------------------------------------------------------
function interpLog(xs, ys, x) {             // log-log on the grid; zeros stay zero
  if (x <= xs[0]) return ys[0];
  if (x >= xs[xs.length - 1]) return ys[ys.length - 1];
  let i = 0; while (xs[i + 1] < x) i++;
  const f = Math.log(x / xs[i]) / Math.log(xs[i + 1] / xs[i]);
  const a = ys[i], b = ys[i + 1];
  if (a <= 0 || b <= 0) return a + (b - a) * f;
  return Math.exp(Math.log(a) + (Math.log(b) - Math.log(a)) * f);
}
function shieldNumbers(c = dcase, v = lv) {
  const L = D.levers[c], Sx = L.S.slice(1);
  const brow = interpLog(Sx, L.brow.slice(1), v.brow);
  const engines = v.eng > 0 ? interpLog(Sx, L.engines.slice(1), v.eng) : L.engines[0];
  const att = k => interpLog(L.att, L.att_items[k], v.att);
  const kg = S => S > 0 ? interpLog(Sx, L.bumper_kg_m2.slice(1), S) : 0;
  return { brow, engines, blades: att('blades'), rings: att('rings'), body: att('body'), optics: L.optics,
    brow_kg_m2: kg(v.brow), eng_kg_m2: kg(v.eng), brow_t: K.brow_area * kg(v.brow) / 1e3, eng_t: K.eng_area * kg(v.eng) / 1e3 };
}

// ---- frame --------------------------------------------------------------------------------------------------------------------------
function setSize() {
  const w = stage.clientWidth, h = stage.clientHeight;
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) renderer.setSize(w, h, false);
  return [w, h];
}
const VEND = () => mode === 'grain' ? GT.V : TRIP.V;
let gRes = null, gRef = null;
function frame(now) {
  const dt = Math.min((now - (last || now)) / 1000, 0.1); last = now;
  const moving = controls.update();
  if (playing) { u = Math.min(u + dt * (mode === 'grain' ? 1 : 1), VEND()); if (u >= VEND()) { playing = false; syncPlay(); } dirty = true; }
  if (!dirty && !moving) return;
  dirty = false;
  const [w, h] = setSize();
  const t0 = performance.now();
  let info = null;
  if (mode === 'grain') {
    const portrait = matchMedia('(max-width: 760px)').matches && h > w * 0.8, both = split === 'split';
    const views = both ? (portrait ? [[0, h / 2, w, h / 2, 0], [0, 0, w, h / 2, 1]] : [[0, 0, w / 2, h, 0], [w / 2, 0, w / 2, h, 1]]) : [[0, 0, w, h, 1]];
    for (const [x, y, vw, vh, side] of views) {
      renderer.setViewport(x, y, vw, vh); renderer.setScissor(x, y, vw, vh);
      camera.aspect = vw / vh; camera.updateProjectionMatrix();
      grainSide(side ? gRes : gRef, side ? gv : REF_V, u);
      G.cloud.material.uniforms.uScale.value = vh * renderer.getPixelRatio();
      renderer.render(grainScene, camera);
    }
  } else {
    renderer.setViewport(0, 0, w, h); renderer.setScissor(0, 0, w, h);
    camera.aspect = w / h; camera.updateProjectionMatrix();
    info = tripUpdate();
    TR.sparks.material.uniforms.uScale.value = h * renderer.getPixelRatio();
    renderer.render(tripScene, camera);
  }
  const ft = performance.now() - t0;
  frames.push(dt * 1000); if (frames.length > 60) frames.shift();
  adapt();
  window.__dust.stats = { calls: renderer.info.render.calls, triangles: renderer.info.render.triangles, cpu_ms: ft, dpr: renderer.getPixelRatio() };
  if (now - (frame.hud || 0) > 100 || !playing) { frame.hud = now; paintHud(info); }
}
function adapt() {
  if (frames.length < 60 || !playing) return;
  const mean = frames.reduce((a, b) => a + b, 0) / frames.length, now = performance.now();
  if (mean > 45 && dpr > 0.75 && now - (adapt.at || 0) > 3000) { dpr = Math.max(0.75, dpr - 0.25); renderer.setPixelRatio(dpr); adapt.at = now; frames.length = 0; }
}

// ---- HUD and panels -------------------------------------------------------------------------------------------------------------------
const row = (label, value, note, cls = '') => `<div class="hrow ${cls}"><span>${esc(label)}</span><b>${value}</b>${note ? `<i>${esc(note)}</i>` : ''}</div>`;
function paintHud(info) {
  if (mode === 'grain') {
    const r = gRes;
    hud.innerHTML = row('Speed', KMS(gv), `${sig(100 * gv / K.c, 2)} % of light`) + row('Energy', J(r.E_J), TNTF(r.tnt_kg))
      + row('Per atom', EV(r.keV_per_u), 'kinetic energy per nucleon') + row('The grain', r.regime, `${M_(r.d_m)} across, ${KG(gm)}`)
      + row('Outcome', OUT[r.outcome], r.cloud_J_m2 != null ? `cloud ${N(r.cloud_J_m2)} J/m² on the skin, ${N(r.allow_J_m2)} allowed` : '', r.breach ? 'bad' : 'ok');
    $('clock').textContent = u < GT.approach ? `${sig(D.stack.standoff_m / gv * 1e6, 2)} µs from layer to skin` : u < GT.approach + GT.cross ? 'impact: slowed about 10⁶×' : 'after the impact';
    $('side-a').querySelector('small').textContent = `${OUT[gRef.outcome]}, ${J(gRef.E_J)}`;
    $('side-b').querySelector('small').textContent = `${OUT[gRes.outcome]}, ${J(gRes.E_J)}`;
    evcap.innerHTML = '';
  } else if (info) {
    const ix = TRIP.ix, a = info.row, sc = TRIP.scale;
    const cum = k => tripValue(`cum_${k}`, u) * sc[k];
    const lead = a[ix.orient] === 'BOW_FIRST' ? 'the Brow' : a[ix.orient] === 'ENGINE_FIRST' ? 'engine fronts' : 'the side';
    hud.innerHTML = row('Mission day', `${Math.round(info.day).toLocaleString('en')}`, a[ix.phase]) + row('Speed', KMS(info.v), `${sig(100 * info.v / K.c, 2)} % of light, ${sig(info.r, 3)} AU from the Sun`)
      + row('Leading face', esc(lead), `${N(lerp(a[ix.lead_per_s], info.row === a ? a[ix.lead_per_s] : a[ix.lead_per_s], 0))} grains/s, ${N(info.rate)} above 1 J, ${N(info.W)} W`)
      + row(mode === 'shield' ? `Grains through the ${sig(lv.brow, 2)} m layer` : 'Grains through the 2 m layer', CNT(cum('brow')), 'each one breaches the Brow skin', cum('brow') > 0.1 ? 'bad' : '')
      + row('Engine-front breaches', CNT(cum('engines')), mode === 'shield' && lv.eng > 0 ? `${sig(lv.eng, 2)} m bumper` : 'bare 5 mm face', cum('engines') > 0.1 ? 'bad' : '')
      + row('Radiator blade punctures', CNT(cum('blades')), `${mode === 'shield' ? lv.att : 0.2}° attitude error`, cum('blades') > 0.1 ? 'bad' : '');
    const ph = TRIP.t.phases.findIndex(p => info.row && TRIP.rows.indexOf(info.row) >= p.i0 && TRIP.rows.indexOf(info.row) <= p.i1);
    if (ph !== paintHud.ph) {
      paintHud.ph = ph; const p = TRIP.t.phases[ph];
      evcap.innerHTML = p ? `<b>${esc(p.name)}</b><span>${esc(p.text)}</span>` : '';
      for (const li of document.querySelectorAll('#phases li')) li.classList.toggle('current', +li.dataset.i === ph);
    }
    $('clock').textContent = `day ${Math.round(info.day)}`;
  }
  $('scrub').value = Math.round(1000 * u / VEND());
}
function paintGrainPanel() {
  gRes = impact(gm, gv, dcase); gRef = impact(gm, REF_V, dcase);
  $('g-speed-o').textContent = KMS(gv); $('g-mass-o').textContent = `${KG(gm)} (${M_(gRes.d_m)})`;
  $('g-speed').value = Math.round(1000 * Math.log(gv / 1e3) / Math.log(K.v_cruise / 1e3));
  $('g-mass').value = Math.round(1000 * (Math.log10(gm) + 18) / 15);
  const ls = largestStopped(gv, dcase), lr = largestStopped(REF_V, dcase);
  const tr = (l, a, b) => `<tr><td>${l}</td><td class="num">${a}</td><td class="num">${b}</td></tr>`;
  $('g-read').innerHTML = `<table><thead><tr><th></th><th>At 7 km/s</th><th>At ${esc(KMS(gv))}</th></tr></thead><tbody>
    ${tr('Energy', J(gRef.E_J), J(gRes.E_J))}${tr('As TNT', TNTF(gRef.tnt_kg), TNTF(gRes.tnt_kg))}
    ${tr('Per atom', EV(gRef.keV_per_u), EV(gRes.keV_per_u))}${tr('The grain', esc(gRef.regime), esc(gRes.regime))}
    ${tr('Crater it would dig in a thick plate', M_(gRef.crater_m), M_(gRes.crater_m))}
    ${tr('Outcome on the Brow stack', `<b class="${gRef.breach ? 'bad' : 'ok'}">${OUT[gRef.outcome]}</b>`, `<b class="${gRes.breach ? 'bad' : 'ok'}">${OUT[gRes.outcome]}</b>`)}
    ${tr('Largest grain the stack stops', KG(lr), KG(ls))}</tbody></table>`;
  window.__dust.grain = { m: gm, v: gv, r: gRes };
  for (const b of document.querySelectorAll('[data-speed]')) b.setAttribute('aria-pressed', String(Math.abs(D.speeds[+b.dataset.speed][1] / gv - 1) < 0.01));
  for (const b of document.querySelectorAll('[data-mass]')) b.setAttribute('aria-pressed', String(Math.abs(D.masses[+b.dataset.mass][1] / gm - 1) < 0.01));
}
function paintShield() {
  const o = shieldNumbers(), tgt = K.target_events;
  for (const k of ['brow', 'eng', 'att']) $(`lo-${k}`).textContent = k === 'att' ? `${lv.att}°` : lv[k] > 0 ? `${sig(lv[k], 2)} m` : 'none';
  $('lv-brow').value = Math.round(1000 * Math.log(lv.brow / 0.5) / Math.log(600));
  $('lv-eng').value = lv.eng > 0 ? Math.round(1000 * Math.log(lv.eng / 0.5) / Math.log(600)) : 0;
  $('lv-att').value = Math.round(1000 * Math.log(lv.att / 0.05) / Math.log(60));
  const tr = (l, v, note, ok) => `<tr class="${ok ? 'ok' : 'bad'}"><td>${l}</td><td class="num">${v}</td><td>${note}</td></tr>`;
  const fails = [['brow', 'the Brow'], ['engines', 'the engine fronts'], ['blades', 'the radiator blades'], ['rings', 'the habitat rings'], ['body', 'the body']].filter(([k]) => o[k] > tgt);
  $('s-read').innerHTML = `<p class="first ${fails.length ? 'bad' : 'ok'}">${fails.length ? `Still failing: <b>${fails.map(f => f[1]).join(', ')}</b>.`
    : '<b>Every critical part holds</b> at the 0.1-events target.'}</p>
    <table><thead><tr><th>Over one trip</th><th>Expected</th><th>Target ≤ ${tgt}</th></tr></thead><tbody>
    ${tr('Grains through the Brow layer', CNT(o.brow), `layer at ${sig(lv.brow, 2)} m`, o.brow <= tgt)}
    ${tr('Engine-front breaches', CNT(o.engines), lv.eng > 0 ? `bumper at ${sig(lv.eng, 2)} m: it would sit in the exhaust` : 'bare 5 mm face', o.engines <= tgt)}
    ${tr('Radiator blade punctures', CNT(o.blades), `${lv.att}° attitude`, o.blades <= tgt)}
    ${tr('Habitat ring breaches', CNT(o.rings), 'in the Brow\'s shadow', o.rings <= tgt)}
    ${tr('Body and tank breaches', CNT(o.body), 'in the Brow\'s shadow', o.body <= tgt)}
    ${tr('Driver optics hit', CNT(o.optics), 'sacrificial, replaced in service', true)}
    </tbody></table>
    <p class="meta">Brow layer ${sig(o.brow_kg_m2, 3)} kg/m² (${T(o.brow_t)}); engine bumpers ${sig(o.eng_kg_m2, 3)} kg/m² (${T(o.eng_t)}).
    A layer 10 m or more ahead lengthens the ship by that much and must survive the dust itself. Dust: ${esc(D.case_labels[dcase][0].toLowerCase())}.</p>`;
  window.__dust.shield = { levers: { ...lv }, case: dcase, ...o };
}

function paintCase() { $('case-note').innerHTML = `<b>${esc(D.case_labels[dcase][0])}:</b> ${esc(D.case_labels[dcase][1])}.`; $('case-note').classList.toggle('stress', dcase === 'HIGH'); }
function setMode(m) {
  mode = m;
  document.querySelector('.ign').dataset.mode = m;
  for (const b of document.querySelectorAll('.ign-modes [data-mode]')) b.setAttribute('aria-selected', String(b.dataset.mode === m));
  stage.dataset.view = m === 'grain' ? 'grain' : 'trip';
  stage.dataset.split = m === 'grain' ? split : 'b';
  if (m !== 'grain') tripData();
  if (m === 'shield') paintShield();
  if (camera) placeCamera();
  u = 0; lastTripU = 0; playing = !reduced; syncPlay(); paintHud.ph = -2; dirty = true;
  if (renderer && reduced) { u = VEND() * (m === 'grain' ? 0.62 : 1); }
  history.replaceState(null, '', `#mode=${m}${m === 'shield' ? `&lv=${lv.brow},${lv.eng},${lv.att}` : ''}${dcase !== 'NOMINAL' ? `&case=${dcase}` : ''}`);
}
function placeCamera() {
  if (mode === 'grain') {
    camera.near = 0.02; camera.far = 2000; camera.fov = 38;
    camera.position.set(4.6, 1.5, touch ? 6.4 : 5.2); controls.target.set(0.95, 0.05, -0.2); controls.minDistance = 2; controls.maxDistance = 30;
  } else {
    camera.near = 1; camera.far = 12000; camera.fov = 36;
    camera.position.set(190, 135, touch ? 520 : 375); controls.target.set(0, -8, 0); controls.minDistance = 120; controls.maxDistance = 2500;
  }
  camera.updateProjectionMatrix(); controls.update();
}
function syncPlay() { const b = $('play'); b.textContent = playing ? '❚❚' : '▶'; b.setAttribute('aria-label', playing ? 'Pause' : 'Play'); }

async function load() {
  gate.querySelector('button').disabled = true;
  try {
    const q = new URLSearchParams(location.search);
    renderer = new THREE.WebGLRenderer({ canvas, antialias: !touch && !q.has('noaa'), powerPreference: 'high-performance' });
    dpr = Math.min(devicePixelRatio || 1, touch ? 1.5 : 2); renderer.setPixelRatio(dpr);
    renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.setScissorTest(true);
    camera = new THREE.PerspectiveCamera(38, 1, 0.02, 2000);
    controls = new OrbitControls(camera, canvas); controls.enableDamping = true; controls.dampingFactor = 0.08;
    controls.addEventListener('change', () => { dirty = true; });
    grainScene = buildGrain(); tripScene = buildTrip();
    placeCamera();
    new ResizeObserver(() => { dirty = true; }).observe(stage);
    gate.hidden = true; stage.classList.add('live'); hud.hidden = false;
    window.wos?.scenario({ label: 'DUST', class: 'SIM' });
    setMode(mode);
    renderer.setAnimationLoop(frame);
    window.__dust.ready = true;
  } catch (err) {
    cstatus.hidden = false; cstatus.textContent = `The 3D view could not start: ${err.message}. The numbers below still hold.`; cstatus.classList.add('error');
    gate.querySelector('button').disabled = false; console.error(err);
  }
}

async function start() {
  D = INLINE ? INLINE.data : await fetch(DATA).then(r => r.json());
  K = D.constants; gv = K.v_cruise;
  const h = location.hash, auto = /[#&]autostart/.test(h);
  const hm = /mode=(\w+)/.exec(h); if (hm && ['grain', 'trip', 'shield'].includes(hm[1])) mode = hm[1];
  const hc = /case=(\w+)/.exec(h); if (hc && D.levers[hc[1]]) dcase = hc[1];
  const hl = /lv=([\d.]+),([\d.]+),([\d.]+)/.exec(h); if (hl) lv = { brow: +hl[1] || 2, eng: +hl[2], att: +hl[3] || 0.2 };
  $('g-speed').addEventListener('input', ev => { gv = 1e3 * Math.pow(K.v_cruise / 1e3, +ev.target.value / 1000); paintGrainPanel(); replay(); });
  $('g-mass').addEventListener('input', ev => { gm = Math.pow(10, -18 + 15 * +ev.target.value / 1000); paintGrainPanel(); replay(); });
  for (const b of document.querySelectorAll('[data-speed]')) b.addEventListener('click', () => { gv = D.speeds[+b.dataset.speed][1]; paintGrainPanel(); if (mode !== 'grain') setMode('grain'); replay(); });
  for (const b of document.querySelectorAll('[data-mass]')) b.addEventListener('click', () => { gm = D.masses[+b.dataset.mass][1]; paintGrainPanel(); if (mode !== 'grain') setMode('grain'); replay(); });
  for (const b of document.querySelectorAll('[data-case]')) b.addEventListener('click', () => {
    dcase = b.dataset.case; for (const x of document.querySelectorAll('[data-case]')) x.setAttribute('aria-pressed', String(x === b));
    paintCase(); paintGrainPanel(); paintShield(); setMode(mode); });
  for (const b of document.querySelectorAll('[data-case]')) b.setAttribute('aria-pressed', String(b.dataset.case === dcase));
  const fromS = p => +(0.5 * Math.pow(600, p / 1000)).toPrecision(2);
  $('lv-brow').addEventListener('input', ev => { lv.brow = fromS(+ev.target.value); onLever(); });
  $('lv-eng').addEventListener('input', ev => { lv.eng = +ev.target.value < 5 ? 0 : fromS(+ev.target.value); onLever(); });
  $('lv-att').addEventListener('input', ev => { lv.att = +(0.05 * Math.pow(60, +ev.target.value / 1000)).toPrecision(2); onLever(); });
  const PRE = { drawn: { brow: 2, eng: 0, att: 0.2 }, wide: { brow: 30, eng: 0, att: 0.2 }, all: { brow: 300, eng: 300, att: 0.05 } };
  for (const b of document.querySelectorAll('[data-preset]')) b.addEventListener('click', () => { lv = { ...PRE[b.dataset.preset] }; onLever(); });
  $('share').addEventListener('click', async () => { try { await navigator.clipboard.writeText(location.href); $('share').textContent = 'Link copied'; } catch { $('share').textContent = 'Copy the address bar'; } });
  for (const b of document.querySelectorAll('.ign-modes [data-mode]')) b.addEventListener('click', () => setMode(b.dataset.mode));
  $('play').addEventListener('click', () => { if (!playing && u >= VEND()) { u = 0; lastTripU = 0; } playing = !playing; syncPlay(); dirty = true; });
  $('restart').addEventListener('click', replay);
  $('scrub').addEventListener('input', ev => { u = (+ev.target.value / 1000) * VEND(); lastTripU = u; playing = false; syncPlay(); dirty = true; });
  for (const b of document.querySelectorAll('[data-split]')) b.addEventListener('click', () => {
    split = b.dataset.split; for (const x of document.querySelectorAll('[data-split]')) x.setAttribute('aria-pressed', String(x === b));
    if (mode === 'grain') stage.dataset.split = split; dirty = true; });
  for (const li of document.querySelectorAll('#phases li')) li.addEventListener('click', () => {
    if (mode === 'grain') setMode('trip');
    u = TRIP.vis[TRIP.t.phases[+li.dataset.i].i0]; lastTripU = u; playing = true; syncPlay(); dirty = true; });
  paintCase(); paintGrainPanel(); paintShield();
  setMode(mode);
  $('load').addEventListener('click', load);
  if (INLINE || auto) load();
}
function replay() { u = 0; lastTripU = 0; playing = true; syncPlay(); dirty = true; }
let leverTimer = 0;
function onLever() {
  paintShield();
  if (mode !== 'shield') setMode('shield');
  else { history.replaceState(null, '', `#mode=shield&lv=${lv.brow},${lv.eng},${lv.att}${dcase !== 'NOMINAL' ? `&case=${dcase}` : ''}`); }
  clearTimeout(leverTimer); leverTimer = setTimeout(() => { tripData(); dirty = true; }, 120);
}
function bench(n = 30) {      // measurement only: n synchronous redraws of the current view, each finished with a 1-pixel read
  const gl = renderer.getContext(), px = new Uint8Array(4), t = [];
  for (let i = 0; i < n; i++) { dirty = true; const t0 = performance.now(); frame(t0); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px); t.push(performance.now() - t0); }
  t.sort((a, b) => a - b);
  return { p50: t[Math.floor(n / 2)], p95: t[Math.floor(n * 0.95)], calls: renderer.info.render.calls, dpr: renderer.getPixelRatio() };
}
window.__dust = { ready: false, bench, impact: (m, v, c) => impact(m, v, c), shield: null, grain: null,
  seek: x => { u = x * VEND(); playing = false; dirty = true; syncPlay(); }, mode: m => setMode(m), get data() { return D; } };
start();
