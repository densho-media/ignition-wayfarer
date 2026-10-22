"""Browser explorer (WEB-001): the saved COAST vehicle as a Draco GLB inside a static Three.js site.

`run()` (workflow.py web) exports the saved assets with the Godot exporter (`export/godot.py --out`, COAST, no Godot,
no characters), checks the GLB against that export's manifest, vendors a pinned Three.js and assembles a static site
from `web/`. Every path in the site is relative, so it serves from any subpath (GitHub Pages /ignition-wayfarer/).
It never builds or edits geometry: build first (pipeline), and pass that run with `--pipeline-run` to record its
geometry diff in build.json.
"""
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tarfile
import time
import urllib.request

import pipeline
from workflow import write_lock

THREE = {'version': '0.170.0', 'url': 'https://registry.npmjs.org/three/-/three-0.170.0.tgz',
         'integrity': 'sha512-FQK+LEpYc0fBD+J8g6oSEyyNzjp+Q7Ks1C568WWaoMRLW+TkNNWmenWeGgJjV105Gd+p/2ql1ZcjYvNiPZBhuQ=='}
# The module files the viewer imports, from the npm package: (package path, site path under vendor/three/).
THREE_FILES = [('build/three.module.min.js', 'three.module.min.js'), ('LICENSE', 'LICENSE'),
               *[(f'examples/jsm/{p}', f'addons/{p}') for p in (
                   'controls/OrbitControls.js', 'loaders/GLTFLoader.js', 'loaders/DRACOLoader.js',
                   'utils/BufferGeometryUtils.js', 'environments/RoomEnvironment.js')],
               *[(f'examples/jsm/libs/draco/gltf/{p}', f'draco/{p}') for p in ('draco_decoder.wasm', 'draco_wasm_wrapper.js')]]
CACHE = Path.home() / '.cache/wayfarer/web'
GLB_LIMIT = 95_000_000          # GitHub Pages refuses files over 100 MB
ALLOWED_EXTENSIONS = {'KHR_draco_mesh_compression', 'KHR_materials_emissive_strength'}


def three_package():
    """The pinned npm tarball, downloaded once into the cache and checked against its registry integrity."""
    path = CACHE / Path(THREE['url']).name
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(THREE['url'], timeout=120) as response:
            path.with_suffix('.part').write_bytes(response.read())
        path.with_suffix('.part').rename(path)
    algorithm, expected = THREE['integrity'].split('-', 1)
    if base64.b64encode(hashlib.new(algorithm, path.read_bytes()).digest()).decode() != expected:
        path.unlink()
        raise ValueError(f'three {THREE["version"]}: tarball integrity mismatch (deleted the cached copy)')
    return path


def vendor_three(site):
    with tarfile.open(three_package()) as tar:
        for src, dst in THREE_FILES:
            target = site / 'vendor/three' / dst
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tar.extractfile(f'package/{src}').read())


def check_glb(path, manifest):
    """Header, JSON chunk, extensions, node identities and assembly groups against the export manifest."""
    data = path.read_bytes()
    magic, version, length = struct.unpack('<4sII', data[:12])
    chunk_length, chunk_type = struct.unpack('<II', data[12:20])
    problems = []
    if magic != b'glTF' or version != 2 or length != len(data) or chunk_type != 0x4E4F534A:
        problems.append(f'not a glTF 2.0 binary: magic {magic!r}, version {version}, length {length}/{len(data)}')
        return {'ok': False, 'problems': problems}
    gltf = json.loads(data[20:20 + chunk_length])
    names = [n.get('name', '') for n in gltf.get('nodes', [])]
    meshes = {n for n in names if n.startswith('WF_')}
    expected = {r['node'] for r in manifest['nodes']}
    groups = sorted({n.split('.')[0] for n in names if n.startswith('Assembly_')})
    unknown = set(gltf.get('extensionsRequired', [])) - ALLOWED_EXTENSIONS
    if meshes != expected:
        problems.append(f'mesh nodes differ from the manifest: {len(meshes - expected)} extra, {len(expected - meshes)} missing')
    if groups != sorted(g for g in manifest['groups'] if g.startswith('Assembly_')):
        problems.append(f'assembly groups differ from the manifest: {groups}')
    if unknown:
        problems.append(f'required extensions the viewer does not load: {sorted(unknown)}')
    if not 0 < len(data) < GLB_LIMIT:
        problems.append(f'GLB size {len(data)} bytes outside (0, {GLB_LIMIT})')
    if min(manifest['bounds_runtime_m']['size']) <= 0:
        problems.append('empty export bounds')
    return {'ok': not problems, 'problems': problems, 'bytes': len(data), 'nodes': len(names), 'mesh_nodes': len(meshes),
            'meshes': len(gltf.get('meshes', [])), 'materials': len(gltf.get('materials', [])), 'assemblies': groups,
            'extensions_required': gltf.get('extensionsRequired', [])}


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def pipeline_record(root, run_dir):
    """The geometry check this site rests on: a PASS pipeline run on the current inputs with an empty geometry diff."""
    summary = json.loads((Path(run_dir) / 'summary.json').read_text())
    diff = summary.get('geometry_diff') or {}
    record = {'run': Path(run_dir).name, 'result': summary.get('result'), 'verification': summary.get('verification'),
              'steps': summary.get('steps'), 'seconds': summary.get('seconds'), 'geometry_diff': {
                  'baseline': Path(diff.get('baseline', '')).name, 'result': diff.get('result'),
                  **{k: diff.get(k) for k in ('changed', 'added', 'removed', 'links_changed')}}}
    if summary.get('result') != 'PASS' or diff.get('result') != 'PASS':
        raise ValueError(f'pipeline run {record["run"]} is not a PASS with a passing geometry diff')
    if summary.get('input_sha256') != pipeline.input_hashes(root):
        raise ValueError(f'pipeline run {record["run"]} was built from other inputs than the current data')
    return record


def run(root, out=None, pipeline_run=None, draco=True):
    started = time.monotonic()
    with write_lock(root) as lock:
        if lock is None:
            return {'result': 'BUSY'}
        run_dir = root / 'runs' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-web')
        work, site = run_dir / 'work', Path(out).resolve() if out else run_dir / 'site'
        if site.exists():
            shutil.rmtree(site)
        work.mkdir(parents=True)
        site.mkdir(parents=True)
        vehicle = root / 'assets/wayfarer/WF_WAYFARER_001.blend'
        if not vehicle.exists():
            return {'result': 'FAIL', 'step': 'assets', 'reason': 'no saved vehicle; run the pipeline (full build) first'}
        built = pipeline_record(root, pipeline_run) if pipeline_run else None
        revision, dirty = git(root, 'rev-parse', 'HEAD'), bool(git(root, 'status', '--porcelain', '--untracked-files=no'))
        identity = {'git_revision': revision, 'git_dirty': dirty, 'build': 'saved assets, browser copy (WEB-001)',
                    'inputs': pipeline.input_hashes(root)}
        (work / 'build_identity.json').write_text(json.dumps(identity, indent=2) + '\n')
        log = run_dir / 'export.log'
        t0 = time.monotonic()
        code = pipeline.subprocess_runner(pipeline.blender(root / 'src/wayfarer/export/godot.py', '--root', root, '--out', work,
                                                           '--identity', work / 'build_identity.json', *(['--draco'] if draco else [])),
                                          log, root, pipeline.STEP_TIMEOUT)
        export_s = round(time.monotonic() - t0, 1)
        if code:
            return {'result': 'FAIL', 'step': 'export', 'log': str(log), 'tail': pipeline.failure_tail(log)}
        manifest = json.loads((work / 'manifest.json').read_text())
        glb = check_glb(work / 'wayfarer.glb', manifest)
        if not glb['ok']:
            return {'result': 'FAIL', 'step': 'check-glb', 'problems': glb['problems'], 'run_dir': str(run_dir)}
        for item in (root / 'web').iterdir():
            if item.suffix in ('.html', '.css', '.js'):        # web/README.md stays in the repository
                shutil.copy2(item, site / item.name)
        vendor_three(site)
        (site / 'model').mkdir()
        shutil.copy2(work / 'wayfarer.glb', site / 'model/wayfarer.glb')
        # The pick labels: node -> component, kind and statuses (the manifest's records without placements and lights).
        nodes = {r['node']: [r['component_id'], r['kind'], r['canon_status'], r['geometry_status']] for r in manifest['nodes']}
        (site / 'model/nodes.json').write_text(json.dumps(nodes, separators=(',', ':')))
        build = {'contract': 'WF_WEB_EXPLORER', 'version': 1, 'vessel': 'G.U. WAYFARER 001', 'project': 'IGNITION',
                 'git_revision': revision, 'git_dirty': dirty, 'built_utc': pipeline.utc_now(),
                 'representation': manifest['representation'], 'preset': manifest['preset'], 'blender': manifest['blender'],
                 'three': THREE['version'], 'draco': draco, 'spec_hash': manifest['spec_hash'], 'source_map_hash': manifest['source_map_hash'],
                 'coordinates': manifest['coordinates'], 'bounds_runtime_m': manifest['bounds_runtime_m'], 'triangles': manifest['triangles'],
                 'glb': {k: glb[k] for k in ('bytes', 'nodes', 'mesh_nodes', 'meshes', 'materials', 'extensions_required')},
                 'glb_sha256': pipeline.sha256(site / 'model/wayfarer.glb'), 'pipeline': built}
        (site / 'build.json').write_text(json.dumps(build, indent=2) + '\n')
        files = {str(p.relative_to(site)): p.stat().st_size for p in sorted(site.rglob('*')) if p.is_file()}
        result = {'result': 'PASS', 'run_dir': str(run_dir), 'site': str(site), 'git_revision': revision, 'git_dirty': dirty,
                  'export_seconds': export_s, 'seconds': round(time.monotonic() - started, 1),
                  'glb_mb': round(glb['bytes'] / 1e6, 2), 'site_mb': round(sum(files.values()) / 1e6, 2),
                  'mesh_nodes': glb['mesh_nodes'], 'assemblies': len(glb['assemblies']), 'triangles': manifest['triangles'],
                  'pipeline': built and {'run': built['run'], 'geometry_diff': built['geometry_diff']}}
        (run_dir / 'web.json').write_text(json.dumps({**result, 'files': files}, indent=2) + '\n')
        return result
