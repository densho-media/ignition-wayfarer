// Vertex Engine 1.1 part inspection (owner brief 2026-11-14). The four engines are drawn from 22 merged render objects each, so the play
// package stays inside its budget; this module makes every one of the engine's logical parts inspectable without exporting more nodes.
// It loads, only when someone opens the Engine drawer, build.engine_file (the part records, categories, materials and the four engine
// placements, written by src/wayfarer/vertex_inspect.py) and its part geometry (one raw buffer: int16 positions in 1 mm steps in the
// engine frame, uint16 indices). Each part's mesh is placed by the engine matrices as an invisible pick proxy and drawn as the highlight.
// Honest limits: the proxies are the source part meshes, not the Draco-compressed render mesh, so a pick can sit about 1.5 cm off what is
// drawn; a part whose render object is hidden takes no pick; the highlight shows the part's own surface, never more than one part.
import * as THREE from 'three';

const PUSH = 0.03;              // the highlight surface sits 3 cm toward the camera (above the Draco render mesh, no z-fighting)
const SELECTED = 0xd99ac9;      // First Ignition plasma pink (--selected)

export function createInspector(ctx) {
  const { scene, byId, records, labels, panel, toggle, fitBox, camera, controls, changed, focusNode, isHidden, isGhost, clearPick } = ctx;
  let data = null, loading = null;
  const geos = new Map();       // part name -> BufferGeometry, shared by the four engines
  const roots = new Map();      // engine name -> Group at the engine placement (pick proxies, never drawn)
  const matrices = new Map();   // engine name -> Matrix4 (engine frame -> ship, runtime axes)
  const renderOf = new Map();   // `${engine}|${render object}` -> viewer record
  const parts = new Map();      // part name -> record
  const cats = new Map();       // category id -> category
  const sel = { engine: 'N1', part: null, cat: '', query: '' };
  const alignment = [];         // per render object: metres between the GLB node and the manifest placement (checked by web_check)
  let overlay = null, back = null;
  const overlayMaterial = new THREE.MeshBasicMaterial({ color: SELECTED, transparent: true, opacity: 0.5, depthWrite: false,
                                                        side: THREE.DoubleSide, toneMapped: false });
  overlayMaterial.onBeforeCompile = sh => {
    sh.vertexShader = sh.vertexShader.replace('#include <project_vertex>', `vec4 mvPosition = modelViewMatrix * vec4( transformed, 1.0 );
      mvPosition.xyz += normalize( -mvPosition.xyz ) * ${PUSH.toFixed(3)};
      gl_Position = projectionMatrix * mvPosition;`);
  };
  const edgeMaterial = new THREE.LineBasicMaterial({ color: SELECTED, transparent: true, opacity: 0.85, depthTest: false, toneMapped: false });

  const rgb = c => `rgb(${c.map(v => Math.round(255 * v)).join(',')})`;
  const el = (tag, props = {}, ...kids) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (k === 'data') for (const [dk, dv] of Object.entries(v)) e.dataset[dk] = dv;
      else if (k === 'on') e.addEventListener('click', v);
      else if (k in e && k !== 'style') e[k] = v; else e.setAttribute(k, v);
    }
    e.append(...kids.filter(x => x !== null && x !== undefined && x !== false));
    return e;
  };

  // ---- loading ---------------------------------------------------------------------------------------------------------------------
  async function load(build) {
    if (data) return true;
    loading ??= (async () => {
      if (!build?.engine_file) return false;
      const manifest = await fetch(build.engine_file).then(r => r.ok ? r.json() : null).catch(() => null);
      const bin = manifest && await fetch(manifest.geometry.file).then(r => r.ok ? r.arrayBuffer() : null).catch(() => null);
      if (!manifest || !bin) return false;
      const nv = manifest.geometry.vertices;
      const pos = new Int16Array(bin, 0, nv * 3), idx = new Uint16Array(bin, nv * 6);
      for (const p of manifest.parts) {
        const [v0, n, i0, ni] = p.geo;
        const g = new THREE.BufferGeometry();
        const f = new Float32Array(n * 3);
        for (let i = 0; i < n * 3; i++) f[i] = pos[v0 * 3 + i] * manifest.geometry.quantum_m;
        g.setAttribute('position', new THREE.BufferAttribute(f, 3));
        g.setIndex(new THREE.BufferAttribute(idx.slice(i0, i0 + ni), 1));
        g.computeVertexNormals(); g.computeBoundingSphere(); g.computeBoundingBox();
        geos.set(p.name, g); parts.set(p.name, p);
      }
      for (const c of manifest.categories) cats.set(c.id, c);
      for (const e of manifest.engines) {
        const m = new THREE.Matrix4().fromArray(e.matrix);
        matrices.set(e.name, m);
        const root = new THREE.Group();
        root.name = `inspect_${e.name}`; root.matrixAutoUpdate = false; root.matrix.copy(m);
        for (const p of manifest.parts) {
          const proxy = new THREE.Mesh(geos.get(p.name), overlayMaterial);
          proxy.visible = false;                                  // never drawn: the ray meets it explicitly
          proxy.userData = { engine: e.name, part: p.name };
          root.add(proxy);
        }
        scene.add(root); root.updateMatrixWorld(true);
        roots.set(e.name, root);
      }
      // Which GLB node is which engine's render object: the node whose drawn centre lies nearest the manifest's placement of it.
      const local = new Map();
      for (const p of manifest.parts) {
        const b = local.get(p.render_object) || new THREE.Box3();
        b.union(geos.get(p.name).boundingBox); local.set(p.render_object, b);
      }
      for (const r of records) {
        const id = labels[r.id]?.[0] || '';
        if (!id.startsWith('WF.VTX.CE.')) continue;
        const obj = id.slice('WF.VTX.CE.'.length);
        if (!local.has(obj)) continue;
        const drawn = new THREE.Box3();
        for (const mesh of r.meshes) drawn.expandByObject(mesh);
        const at = drawn.getCenter(new THREE.Vector3());
        let best = null;
        for (const [name, m] of matrices) {
          const d = local.get(obj).getCenter(new THREE.Vector3()).applyMatrix4(m).distanceTo(at);
          if (!best || d < best.d) best = { name, d };
        }
        renderOf.set(`${best.name}|${obj}`, r);
        alignment.push({ engine: best.name, object: obj, metres: best.d });
      }
      data = manifest;
      buildPanel();
      return true;
    })();
    return loading;
  }

  // ---- picking ---------------------------------------------------------------------------------------------------------------------
  // The nearest proxy whose render object is drawn; a ghosted render object yields to a solid one behind it, as the main picking does.
  function pick(raycaster) {
    if (!data) return null;
    const hits = [];
    for (const [name, root] of roots) {
      for (const h of raycaster.intersectObject(root, true)) {
        const r = renderOf.get(`${name}|${parts.get(h.object.userData.part).render_object}`);
        if (!r || isHidden(r)) continue;
        hits.push({ engine: name, name: h.object.userData.part, distance: h.distance, ghost: isGhost(r) });
      }
    }
    hits.sort((a, b) => a.distance - b.distance);
    return hits.find(h => !h.ghost) || hits[0] || null;
  }

  // ---- selection, highlight, camera -------------------------------------------------------------------------------------------------
  function setOverlay() {
    if (overlay) { overlay.removeFromParent(); overlay = null; }
    if (!sel.part) return;
    const g = geos.get(sel.part);
    overlay = new THREE.Group();
    overlay.name = 'inspect_highlight';
    const surface = new THREE.Mesh(g, overlayMaterial);
    const edges = new THREE.LineSegments(g.userData.edges ??= new THREE.EdgesGeometry(g, 25), edgeMaterial);
    surface.renderOrder = 4; edges.renderOrder = 5;
    surface.raycast = edges.raycast = () => {};                   // the highlight never takes a pick
    overlay.add(surface, edges);
    roots.get(sel.engine).add(overlay);
    overlay.updateMatrixWorld(true);
  }

  function selectPart(engine, name, { frame = false } = {}) {
    if (!data || (name && !parts.has(name)) || !matrices.has(engine)) return false;
    sel.engine = engine; sel.part = name || null;
    if (name && sel.cat && parts.get(name).category !== sel.cat) sel.cat = '';
    clearPick();
    setOverlay();
    render();
    if (frame && name) framePart();
    changed();
    return true;
  }

  function remember() {
    back ??= { p: camera.position.clone(), t: controls.target.clone(), up: camera.up.clone() };
  }
  function partBox(name, engine = sel.engine) {
    const b = geos.get(name).boundingBox.clone().applyMatrix4(matrices.get(engine));
    const c = b.getCenter(new THREE.Vector3());
    return b.union(new THREE.Box3().setFromCenterAndSize(c, new THREE.Vector3(2.5, 2.5, 2.5)));   // a part never fills more than the view
  }
  function framePart() {
    if (!sel.part) return;
    remember();
    fitBox(partBox(sel.part), camera.position.clone().sub(controls.target).normalize(), camera.up.clone());
    ctx.bookmark();
  }
  function frameEngine(engine = sel.engine) {
    if (!data) return;
    remember();
    const b = new THREE.Box3();
    for (const p of data.parts) b.union(partBox(p.name, engine));
    fitBox(b, camera.position.clone().sub(controls.target).normalize(), camera.up.clone());
    ctx.bookmark();
  }
  function goBack() {
    if (focused()) focusNode(null);
    if (back) {
      camera.position.copy(back.p); controls.target.copy(back.t); camera.up.copy(back.up);
      controls.update(); back = null; ctx.bookmark();
    }
  }
  const renderRecord = () => sel.part && renderOf.get(`${sel.engine}|${parts.get(sel.part).render_object}`);
  const focused = () => { const r = renderRecord(); return !!r && ctx.focusedNode() === r.id; };
  function isolate() {
    const r = renderRecord();
    if (r) focusNode(focused() ? null : r.id);
    setTimeout(render, 0);
  }

  // ---- the drawer ------------------------------------------------------------------------------------------------------------------
  let engineRow, catRow, search, list, details, countLine;
  function buildPanel() {
    panel.querySelector('.inspect-body').innerHTML = '';
    engineRow = el('span', { className: 'chips', role: 'group', 'aria-label': 'Engine' });
    for (const e of data.engines) {
      engineRow.append(el('button', { textContent: e.name, title: `Engine ${e.name} (${e.ident})`, data: { inspectEngine: e.name },
                                      on: () => { selectPart(e.name, sel.part); } }));
    }
    catRow = el('div', { className: 'chips cats', role: 'group', 'aria-label': 'Functional group' });
    catRow.append(el('button', { textContent: 'All', data: { cat: '' }, on: () => { sel.cat = ''; render(); changed(); } }));
    for (const c of data.categories) {
      catRow.append(el('button', { title: c.purpose, data: { cat: c.id }, on: () => { sel.cat = sel.cat === c.id ? '' : c.id; render(); changed(); } },
                       el('i', { className: 'sw', 'aria-hidden': 'true', style: `background:${rgb(c.color)}` }), c.title));
    }
    search = el('input', { type: 'search', placeholder: 'Search parts, materials…', 'aria-label': 'Search engine parts', className: 'search' });
    search.addEventListener('input', () => { sel.query = search.value.trim().toLowerCase(); renderList(); });
    details = el('div', { className: 'part-details', 'aria-live': 'polite' });
    countLine = el('p', { className: 'note count-line' });
    list = el('ul', { className: 'part-list', 'aria-label': 'Engine parts' });
    list.addEventListener('keydown', e => {                       // arrow keys walk the list
      if (!['ArrowDown', 'ArrowUp'].includes(e.key)) return;
      const items = [...list.querySelectorAll('button')];
      const i = items.indexOf(document.activeElement);
      if (i < 0) return;
      e.preventDefault();
      items[Math.max(0, Math.min(items.length - 1, i + (e.key === 'ArrowDown' ? 1 : -1)))].focus();
    });
    const actions = el('div', { className: 'chips actions' },
      el('button', { textContent: 'Frame engine', data: { act: 'frame-engine' }, on: () => frameEngine() }),
      el('button', { textContent: 'Back', title: 'The camera before framing, no isolation', data: { act: 'back' }, on: goBack }));
    panel.querySelector('.inspect-body').append(
      el('div', { className: 'row' }, el('span', { textContent: 'Engine' }), engineRow), actions, details,
      el('div', { className: 'row' }, el('span', { textContent: 'Group' })), catRow, search, countLine, list,
      el('p', { className: 'note', textContent: `${data.picking} Swatches are functional review colours, never material colours; `
        + 'every group is named in text. Masses are ENGINEERING_PROTOTYPE estimates.' }));
    render();
  }

  function renderList() {
    const q = sel.query;
    const shown = data.parts.filter(p => (!sel.cat || p.category === sel.cat)
      && (!q || `${p.label} ${p.name} ${data.materials[p.material]?.name || p.material} ${cats.get(p.category).title}`.toLowerCase().includes(q)));
    list.innerHTML = '';
    for (const p of shown) {
      const c = cats.get(p.category);
      const b = el('button', { data: { part: p.name }, 'aria-pressed': String(p.name === sel.part), on: () => selectPart(sel.engine, p.name, { frame: true }) },
                   el('i', { className: 'sw', 'aria-hidden': 'true', style: `background:${rgb(c.color)}` }), el('span', { textContent: p.label }),
                   el('span', { className: 'count', textContent: c.title.split(' ')[0] }));
      list.append(el('li', {}, b));
    }
    countLine.textContent = `${shown.length} of ${data.parts.length} parts`;
  }

  function renderDetails() {
    details.innerHTML = '';
    if (!sel.part) {
      details.append(el('p', { className: 'note', textContent: 'Pick a part on any engine, or choose one from the list.' }));
      return;
    }
    const p = parts.get(sel.part), c = cats.get(p.category), mat = data.materials[p.material];
    const iface = c.interfaces.map(n => data.interfaces[n] ? `${n} (${data.interfaces[n].kind})` : n);
    const research = [...c.weakest_links.map(w => el('a', { href: `../engineering/weakest-links/#${w}`, textContent: w })),
                      ...c.breakthroughs.map(b => el('a', { href: `../engineering/breakthrough-lab/#${b}`, textContent: b }))];
    const related = el('span', { className: 'chips' });
    for (const n of p.related) {
      const target = parts.has(n) ? n : data.parts.find(x => x.stem === n)?.name;
      if (target) related.append(el('button', { textContent: parts.get(target).label + (parts.has(n) ? '' : ' …'), data: { related: target },
                                                on: () => selectPart(sel.engine, target, { frame: true }) }));
    }
    const row = (k, ...v) => el('div', { className: 'kv' }, el('span', { className: 'k', textContent: k }), el('span', {}, ...v));
    const join = items => items.flatMap((x, i) => i ? [', ', x] : [x]);
    details.append(
      el('h3', { textContent: p.label }),
      el('p', { className: 'meta' }, el('code', { textContent: p.id }), ` · engine ${sel.engine}`,
         p.units > 1 ? ` · one of ${p.units} identical units` : ''),
      row('Group', el('i', { className: 'sw', 'aria-hidden': 'true', style: `background:${rgb(c.color)}` }),
          el('a', { href: `../engineering/vertex/#anatomy-${c.id.toLowerCase().replaceAll('_', '-')}`, textContent: c.title })),
      row('Function', `${c.purpose} ${p.note}`),
      row('Material', el('i', { className: 'sw', 'aria-hidden': 'true', style: `background:${rgb(mat?.color || [0.5, 0.5, 0.5])}` }),
          mat?.name || p.material),
      row('Evidence', el('b', { textContent: p.evidence })),
      row('Mass', `≈ ${p.mass_kg >= 1000 ? (p.mass_kg / 1000).toFixed(1) + ' t' : Math.round(p.mass_kg) + ' kg'} (estimate: drawn volume × assumed density)`),
      row('Interfaces', iface.join(', ') || 'none'),
      row('Research', ...(research.length ? join(research) : ['none declared'])),
      related.childElementCount ? row('Related', related) : null,
      el('div', { className: 'chips actions' },
        el('button', { textContent: 'Frame part', data: { act: 'frame-part' }, on: framePart }),
        el('button', { textContent: focused() ? 'Show all' : 'Isolate', 'aria-pressed': String(focused()),
                       title: 'Focus this part’s render object, the rest as a ghost', data: { act: 'isolate' }, on: isolate }),
        el('button', { textContent: 'Clear', data: { act: 'clear-part' }, on: () => selectPart(sel.engine, null) })));
  }

  function render() {
    if (!data) return;
    for (const b of engineRow.querySelectorAll('button')) b.setAttribute('aria-pressed', String(b.dataset.inspectEngine === sel.engine));
    for (const b of catRow.querySelectorAll('button')) b.setAttribute('aria-pressed', String(b.dataset.cat === sel.cat));
    renderDetails();
    renderList();
  }

  // ---- bookmarks: eng=N2, cat=MAGNETIC_COILS, part=N2.VTX_C1_Winding -----------------------------------------------------------------
  function hash() {
    if (!data || panel.hidden && !sel.part) return '';
    const out = [`eng=${sel.engine}`];
    if (sel.cat) out.push(`cat=${sel.cat}`);
    if (sel.part) out.push(`part=${sel.engine}.${sel.part}`);
    return out.join('&');
  }
  function asked(h) {
    const p = new URLSearchParams(h.replace(/^#/, ''));
    const part = /^(N\d)\.(\w+)$/.exec(p.get('part') || '');
    return { engine: part?.[1] || p.get('eng'), part: part?.[2] || null, cat: p.get('cat') || '' };
  }
  async function openFrom(h, build) {
    const a = asked(h);
    if (!a.engine && !a.part) return false;
    if (!(await load(build))) return false;
    if (a.cat && cats.has(a.cat)) sel.cat = a.cat;
    ctx.openDrawer();
    selectPart(matrices.has(a.engine) ? a.engine : 'N1', parts.has(a.part) ? a.part : null);
    return true;
  }

  return {
    load, pick, selectPart, frameEngine, framePart, goBack, isolate, hash, openFrom, render,
    active: () => !!data && !panel.hidden,
    hasPart: () => !!sel.part,
    state: () => ({ ...sel }),
    data: () => data,
    alignment: () => alignment,
    renderOf: (engine, obj) => renderOf.get(`${engine}|${obj}`)?.id,
    overlay: () => overlay,
  };
}
