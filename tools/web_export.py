"""Wayfarer website (WEB-001 explorer, WEB-002 site): a start page and independently loaded experiences, from the saved assets.

`run()` (workflow.py web) assembles a static site from `web/`:
  index.html, site.css   start page: two choices, the release line; loads no engine, model or library
  viewer/                Explore Ship: the saved COAST vehicle as a Draco GLB (export/godot.py --out --draco, checked against its
                         manifest) in a pinned three.js viewer; build.json names the content-addressed model files
  play/                  Enter Wayfarer: a launcher, and Integrated Demonstrator 01 as a Godot Web export (tools/web_play.py)
  review/                technical review page over release.json
  release.json           release manifest: identity, toolchain, inputs, every file's size and SHA-256, the experiences, checks
Every path in the site is relative, so it serves from any subpath (GitHub Pages /ignition-wayfarer/) or another static host.
It never builds or edits geometry: build first (pipeline), and pass that run with `--pipeline-run` to record its geometry diff.
Before returning PASS it checks that every local reference in the site resolves and that files and the start page stay in budget.
"""
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import tarfile
import time
import urllib.request

import pipeline
import web_play
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
SITE_LIMIT = 900_000_000        # GitHub Pages: a published site may be at most 1 GB
# Download budgets per experience (bytes before compression), set from the 2026-10-22 measurement with headroom: start page 6.6 kB,
# viewer 7.35 MB, play 62.9 MB (engine 39.5 MB, pack 23.1 MB). A larger build fails here instead of silently slowing the site.
START_BUDGET = 60_000
VIEWER_BUDGET = 12_000_000
PLAY_BUDGET = 90_000_000
LIMITATIONS = [
    'REP_PROXY geometry throughout: a display model generated from the parameters, not a measurement source (Draco quantizes '
    'viewer positions to about 1.5 cm).',
    'Enter Wayfarer is Integrated Demonstrator 01 only; the review sessions, EVA, flight timeline and hologram stay in the native '
    'development runtime (python3 tools/workflow.py runtime-export).',
    'The MPFB induction pair and EVA suits are not in the browser package: proxy figures stand in (presentation only).',
    'The browser build is single-threaded WebGL 2 (Godot Compatibility); the native Godot build stays the gameplay and physics reference.',
    'Key labels in the browser show US key positions (the Web display server cannot map physical keys to the layout).',
    'A few navigator markers (geometric symbols such as ▶ ◆ ○) show as empty boxes in the browser: Godot\'s default font lacks them and '
    'the browser build has no system fonts to fall back on (presentation only).',
    'Tested automatically in headless Chromium with software WebGL; Firefox, Safari, phones and real-GPU frame rates are not verified '
    'by CI (see docs/WEB.md).',
    'GitHub Pages caches each file for 10 minutes; engine, pack and model files are content-named so a new release never mixes files.',
]
SKIP = {'README.md', 'play/shell.html'}      # in the repository, not the site (the shell is a Godot export input)
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


def run(root, out=None, pipeline_run=None, draco=True, with_play=True, native=False, native_check=True):
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
        for src in sorted((root / 'web').rglob('*')):
            rel = src.relative_to(root / 'web').as_posix()
            if src.is_file() and rel not in SKIP:
                (site / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, site / rel)
        viewer = site / 'viewer'
        vendor_three(viewer)
        (viewer / 'model').mkdir()
        glb_sha = pipeline.sha256(work / 'wayfarer.glb')
        glb_file = f'model/wayfarer-{glb_sha[:12]}.glb'
        shutil.copy2(work / 'wayfarer.glb', viewer / glb_file)
        # The pick labels: node -> component, kind and statuses (the manifest's records without placements and lights).
        nodes = {r['node']: [r['component_id'], r['kind'], r['canon_status'], r['geometry_status']] for r in manifest['nodes']}
        nodes_text = json.dumps(nodes, separators=(',', ':'))
        nodes_file = f'model/nodes-{hashlib.sha256(nodes_text.encode()).hexdigest()[:12]}.json'
        (viewer / nodes_file).write_text(nodes_text)
        build = {'contract': 'WF_WEB_EXPLORER', 'version': 2, 'vessel': 'G.U. WAYFARER 001', 'project': 'IGNITION',
                 'git_revision': revision, 'git_dirty': dirty, 'built_utc': pipeline.utc_now(),
                 'representation': manifest['representation'], 'preset': manifest['preset'], 'blender': manifest['blender'],
                 'three': THREE['version'], 'draco': draco, 'spec_hash': manifest['spec_hash'], 'source_map_hash': manifest['source_map_hash'],
                 'coordinates': manifest['coordinates'], 'bounds_runtime_m': manifest['bounds_runtime_m'], 'triangles': manifest['triangles'],
                 'glb': {k: glb[k] for k in ('bytes', 'nodes', 'mesh_nodes', 'meshes', 'materials', 'extensions_required')},
                 'glb_sha256': glb_sha, 'glb_file': glb_file, 'nodes_file': nodes_file, 'pipeline': built}
        (viewer / 'build.json').write_text(json.dumps(build, indent=2) + '\n')
        play = None
        if with_play:
            try:
                play = web_play.build(root, run_dir, site / 'play', work / 'manifest.json', work / 'build_identity.json',
                                      native=native, native_check=native_check)
            except (RuntimeError, ValueError, OSError) as error:
                return {'result': 'FAIL', 'step': 'play', 'reason': str(error)[-2000:], 'run_dir': str(run_dir)}
            (site / 'play/play.json').write_text(json.dumps({
                'entry': play['entry'], 'bytes': play['bytes'], 'godot': play['godot'], 'godot_short': web_play.GODOT['version'],
                'scene': play['scene'], 'git_revision': revision}, indent=1) + '\n')
        else:
            shutil.rmtree(site / 'play')
        release = release_record(root, site, build, play, revision, dirty, built)
        problems = verify_site(site, release)
        if problems:
            return {'result': 'FAIL', 'step': 'verify-site', 'problems': problems[:20], 'run_dir': str(run_dir)}
        files = release['files']
        result = {'result': 'PASS', 'run_dir': str(run_dir), 'site': str(site), 'release': release['release'],
                  'git_revision': revision, 'git_dirty': dirty, 'export_seconds': export_s, 'seconds': round(time.monotonic() - started, 1),
                  'glb_mb': round(glb['bytes'] / 1e6, 2), 'site_mb': round(release['site_bytes'] / 1e6, 2),
                  'start_page_bytes': release['experiences']['start']['download_bytes'],
                  'viewer_mb': round(release['experiences']['viewer']['download_bytes'] / 1e6, 2),
                  'play': play and {'mb': round(release['experiences']['play']['download_bytes'] / 1e6, 2), 'entry': play['entry'],
                                    'native_reference': play['native_reference'], 'native_zip': play['native_zip'],
                                    'seconds': play['seconds'], 'step_seconds': play['step_seconds']},
                  'mesh_nodes': glb['mesh_nodes'], 'assemblies': len(glb['assemblies']), 'triangles': manifest['triangles'],
                  'pipeline': built and {'run': built['run'], 'geometry_diff': built['geometry_diff']}}
        (run_dir / 'web.json').write_text(json.dumps({**result, 'files': {k: v['bytes'] for k, v in files.items()}}, indent=2) + '\n')
        return result


def tool_versions():
    out = {'python': platform.python_version()}
    try:
        out['blender'] = subprocess.run([pipeline.BLENDER, '--version'], capture_output=True, text=True, timeout=60).stdout.strip().splitlines()[0]
    except (OSError, IndexError, subprocess.TimeoutExpired):
        out['blender'] = None
    return out


def release_record(root, site, build, play, revision, dirty, built):
    """release.json: what this site is, what it was built from and what each experience downloads (the checks add `tests`)."""
    files = {p.relative_to(site).as_posix(): {'bytes': p.stat().st_size, 'sha256': pipeline.sha256(p)}
             for p in sorted(site.rglob('*')) if p.is_file()}
    size = lambda names: sum(files[n]['bytes'] for n in names)
    viewer_files = ['viewer/index.html', 'viewer/viewer.css', 'viewer/viewer.js', 'viewer/build.json', f"viewer/{build['nodes_file']}",
                    f"viewer/{build['glb_file']}", *[n for n in files if n.startswith('viewer/vendor/') and n.endswith(('.js', '.wasm'))]]
    release = {
        'contract': 'WF_WEB_RELEASE', 'version': 1, 'vessel': 'G.U. WAYFARER 001', 'project': 'IGNITION',
        'release': f"{build['built_utc'][:10].replace('-', '')}-{revision[:7]}{'-dirty' if dirty else ''}",
        'git_revision': revision, 'git_dirty': dirty, 'built_utc': build['built_utc'],
        'hosting': 'static files with relative paths (GitHub Pages project site; any static host)',
        'toolchain': {**tool_versions(), 'blender_export': build['blender'], 'three': THREE['version'],
                      **({'godot': play['godot']} if play else {})},
        'inputs': pipeline.input_hashes(root),
        'model': {**{k: build[k] for k in ('representation', 'preset', 'spec_hash', 'source_map_hash', 'bounds_runtime_m', 'triangles')},
                  'geometry_diff': (built or {}).get('geometry_diff')},
        'pipeline': built and {k: built[k] for k in ('run', 'result', 'verification', 'steps')},
        'experiences': {
            # The start page fetches release.json too; counted at a 4 kB allowance (it lists every file, but only once per visit).
            'start': {'entry': 'index.html', 'download_bytes': size(['index.html', 'site.css']),
                      'loads': ['index.html', 'site.css', 'release.json']},
            'viewer': {'entry': 'viewer/', 'download_bytes': size(viewer_files), 'three': THREE['version'],
                       'glb_file': f"viewer/{build['glb_file']}", 'glb_sha256': build['glb_sha256'],
                       'mesh_nodes': build['glb']['mesh_nodes'], 'assemblies': 14, 'triangles': build['triangles']},
            **({'play': {'entry': 'play/', 'page': f"play/{play['entry']}", 'godot': play['godot'], 'godot_short': web_play.GODOT['version'],
                         'download_bytes': size([f'play/{f}' for f in play['files'].values()]), 'files': play['files'],
                         'variant': play['variant'], 'scene': play['scene'], 'package': play['package'],
                         'reduced_fidelity': play['reduced_fidelity'], 'native_reference': play['native_reference']}} if play else {}),
            'review': {'entry': 'review/'},
        },
        'status_labels': ['CANON', 'DERIVED', 'WORKING', 'PROTOTYPE', 'DIAGNOSTIC', 'HOLD'],
        'limitations': LIMITATIONS,
        'tests': {},
        'files': files,
        'site_bytes': sum(f['bytes'] for f in files.values()),
    }
    (site / 'release.json').write_text(json.dumps(release, indent=1) + '\n')
    return release


# Local references in the site's pages, scripts and styles: attributes, module imports, import-map targets, fetches and url().
REFERENCE = re.compile(r"""\b(?:src|href)="([^"]+)"|\bfrom\s+'([^']+)'|"(\./vendor/[^"]+)"|\bfetch\('([^']+)'|url\(([^)]+)\)""")


def verify_site(site, release):
    """Every local reference resolves inside the site; file, site and start-page sizes stay within the budgets."""
    problems = []
    play_pages = set(release['experiences'].get('play', {}).get('files', {}).values())
    for page in sorted(p for p in site.rglob('*') if p.suffix in ('.html', '.js', '.css') and 'vendor' not in p.parts):
        if page.parent.name == 'play' and page.name in play_pages - {release['experiences']['play']['files']['html']}:
            continue                     # the Godot engine's own scripts
        for match in REFERENCE.finditer(page.read_text(errors='replace')):
            ref = next(g for g in match.groups() if g)
            if re.match(r'^(?:[a-z]+:|#|//)', ref) or '${' in ref or ref.startswith('three'):
                continue
            target = (page.parent / ref.split('#')[0].split('?')[0]).resolve()
            if target.is_dir() and not match.group(3):       # an import-map prefix names a directory; a link opens its index.html
                target = target / 'index.html'
            if not target.is_relative_to(site.resolve()) or not target.exists():
                problems.append(f'{page.relative_to(site)}: {ref} does not resolve inside the site')
    ex = release['experiences']
    named = [ex['viewer']['glb_file'], *(f'play/{f}' for f in ex.get('play', {}).get('files', {}).values())]
    problems += [f'missing {n}' for n in named if n not in release['files']]
    problems += [f'{n}: {f["bytes"]} bytes over the {GLB_LIMIT} file limit' for n, f in release['files'].items() if f['bytes'] > GLB_LIMIT]
    if release['site_bytes'] > SITE_LIMIT:
        problems.append(f'site {release["site_bytes"]} bytes over {SITE_LIMIT}')
    for name, budget in (('start', START_BUDGET), ('viewer', VIEWER_BUDGET), ('play', PLAY_BUDGET)):
        if name in ex and ex[name]['download_bytes'] > budget:
            problems.append(f'{name} downloads {ex[name]["download_bytes"]} bytes, over its {budget} budget')
    start = (site / 'index.html').read_text().replace('three.js', '')
    for heavy in ('.glb', '.wasm', '.pck', 'vendor/', 'engine-', '<script src', 'type="module"'):
        if heavy in start:
            problems.append(f'start page names {heavy!r}: it must load no engine, model or library')
    return problems
