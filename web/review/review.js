// WEB-002 technical review: renders release.json (written by tools/web_export.py) and probes this browser. No engine is loaded.
const out = document.getElementById('out');
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) k === 'class' ? (e.className = v) : e.setAttribute(k, v);
  for (const k of kids.flat()) e.append(k instanceof Node ? k : String(k ?? '—'));
  return e;
};
const tag = v => el('span', { class: `tag ${v}` }, v);
const mb = b => b == null ? '—' : `${(b / 1e6).toFixed(2)} MB`;
const link = (href, text) => el('a', { href }, text);
const table = rows => el('table', {}, rows.filter(Boolean).map(([k, ...v]) => el('tr', {}, el('th', {}, k), ...v.map(x => el('td', {}, x)))));
const section = (title, ...body) => el('section', { class: 'panel' }, el('h2', {}, title), ...body);

const LEGEND = [
  ['CANON', 'Owner-released value in its owner workbook.'],
  ['DERIVED', 'Computed by a shared formula from canon inputs; no independent authority.'],
  ['WORKING', 'Owner working value: in use, not yet released.'],
  ['PROTOTYPE', 'Unsourced physical or display choice made to keep building; replaceable.'],
  ['DIAGNOSTIC', 'A check or what-if value; never an engine or flight input.'],
  ['HOLD', 'Blocked until an owner decision; shown, never presented as GO.'],
];

function probe() {
  const canvas = document.createElement('canvas');
  const gl = canvas.getContext('webgl2');
  let renderer = 'no WebGL 2';
  if (gl) {
    const info = gl.getExtension('WEBGL_debug_renderer_info');
    renderer = info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
    gl.getExtension('WEBGL_lose_context')?.loseContext();
  }
  // A one-instruction SIMD module: v128.const, drop (Godot 4.7 web templates are built with wasm SIMD).
  const simd = WebAssembly.validate(new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0, 1, 4, 1, 96, 0, 0, 3, 2, 1, 0, 10, 22, 1, 20, 0,
    253, 12, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 26, 11]));
  return table([
    ['Browser', navigator.userAgent],
    ['WebGL 2', gl ? tag('yes') : tag('no'), renderer],
    ['WebAssembly SIMD', simd ? tag('yes') : tag('no')],
    ['Cross-origin isolated', String(self.crossOriginIsolated), 'not needed: the Godot build is single-threaded'],
    ['Device memory / cores', `${navigator.deviceMemory ?? '?'} GB / ${navigator.hardwareConcurrency ?? '?'}`],
    ['Screen', `${screen.width} × ${screen.height} @ ${devicePixelRatio}x`],
    ['Pointer', matchMedia('(pointer: fine)').matches ? 'fine (mouse)' : 'coarse (touch)'],
  ]);
}

function render(rel) {
  const v = rel.experiences.viewer, p = rel.experiences.play, t = rel.tests || {};
  const commit = link(`https://github.com/densho-media/ignition-wayfarer/commit/${rel.git_revision}`, rel.git_revision.slice(0, 12));
  const diff = rel.model.geometry_diff || {};
  const checks = (name, c) => c ? [name, tag(c.result), `${c.passed ?? '?'} / ${c.total ?? '?'} checks${c.browser ? ' · ' + c.browser : ''}`,
    c.failed?.length ? c.failed.join(', ') : ''] : [name, '—', 'not run for this release'];
  out.replaceChildren(
    section('Identity', table([
      ['Release', rel.release], ['Commit', commit, rel.git_dirty ? 'working tree dirty' : 'clean'], ['Built', rel.built_utc],
      ['Toolchain', Object.entries(rel.toolchain).map(([k, val]) => `${k} ${val}`).join(' · ')],
      ['Hosting', rel.hosting], ['Manifest', link('../release.json', 'release.json'), `${Object.keys(rel.files).length} files, ${mb(rel.site_bytes)}`],
    ])),
    section('Model', table([
      ['Representation', `${rel.model.representation} · ${rel.model.preset} (viewer) · DOCKED (play)`],
      ['Spec / source map', el('code', {}, rel.model.spec_hash.slice(0, 16)), el('code', {}, rel.model.source_map_hash.slice(0, 16))],
      ['Geometry diff', diff.result ? tag(diff.result) : '—', `vs ${diff.baseline ?? '—'}: changed ${diff.changed ?? '—'}, added ${diff.added ?? '—'}, removed ${diff.removed ?? '—'}`],
      ['Viewer GLB', `${v.mesh_nodes} mesh nodes · ${v.assemblies} assemblies · ${(v.triangles / 1e6).toFixed(2)} M triangles`, el('code', {}, v.glb_sha256.slice(0, 16))],
    ])),
    section('Experiences', table([
      ['Explore Ship', link('../viewer/', 'viewer/'), `three.js ${v.three} · ${mb(v.download_bytes)} to load`],
      p ? ['Enter Wayfarer', link('../play/', 'play/'), `Godot ${p.godot} · ${mb(p.download_bytes)} to load · ${p.variant}`]
        : ['Enter Wayfarer', '—', 'not in this release'],
      p && ['Play package', p.package.join(', ')],
      p && ['Play build', p.reused_from ? `reused from release ${p.reused_from.release} (same inputs, key ${(p.input_key || '').slice(0, 12)})`
        : `built for this release (inputs key ${(p.input_key || '—').slice(0, 12)})`],
      p && ['Reduced fidelity', p.reduced_fidelity.join('; ')],
    ])),
    section('Checks', table([
      ['Pipeline', rel.pipeline ? tag(rel.pipeline.result) : '—',
        rel.pipeline ? `${(rel.pipeline.steps || []).map(x => `${x.name} ${x.status} ${x.seconds} s`).join(' · ')} — ${rel.pipeline.verification}` : 'not recorded'],
      checks('Viewer in browser', t.viewer),
      checks('Loading isolation', t.isolation),
      checks('Play in browser', t.play),
      p?.native_reference ? ['Play native reference', tag(p.native_reference.result),
        `Demonstrator 01 check: ${p.native_reference.checks} checks, ${p.native_reference.errors} engine errors (${p.native_reference.godot})`] : null,
      t.equivalence ? ['Browser vs native', tag(t.equivalence.result), t.equivalence.note] : null,
    ])),
    section('Camera bookmarks', el('p', {}, ...['threequarter', 'side', 'top', 'front', 'aft'].flatMap(n => [link(`../viewer/#view=${n}`, n), ' · ']),
      link('../viewer/?diag', 'viewer with frame-time diagnostics'))),
    section('Status labels', table(LEGEND.map(([k, d]) => [el('span', { class: 'tag' }, k), d]))),
    section('Known limitations', el('ul', { class: 'plain' }, (rel.limitations || []).map(x => el('li', {}, x)))),
    section('Licences', el('p', {}, 'three.js (MIT): ', link('../viewer/vendor/three/LICENSE', 'licence'),
      p ? ' · Godot Engine (MIT): ' : '', p ? link('../play/GODOT_LICENSE.txt', 'licence') : '', p ? ', ' : '',
      p ? link('../play/GODOT_COPYRIGHT.txt', 'third-party notices') : '',
      ' · Wayfarer: ', link('https://github.com/densho-media/ignition-wayfarer/blob/main/LICENSE', 'repository licence')),
      el('p', { class: 'note' }, 'The model is generated from the project parameters; no third-party art is in either experience.')),
    section('This browser', probe()),
  );
}

fetch('../release.json', { cache: 'no-store' }).then(r => r.ok ? r.json() : Promise.reject(new Error(`release.json ${r.status}`)))
  .then(render).catch(err => { out.replaceChildren(el('p', { class: 'note' }, `No release record: ${err.message}`), section('This browser', probe())); });
