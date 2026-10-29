"""Enter Wayfarer (WEB-002): the walk (EXC-001, godot/scenes/excursion.tscn) as a single-threaded Godot Web export, built in a
disposable workspace.

`build()` (called by web_export.run, `workflow.py web`) copies godot/ into the run directory, fills its generated/ with the
package the walk reads, all from the saved assets and tracked inputs:
  wayfarer_docked.glb, manifest_docked.json, wf_sim_rig.json   export/godot.py --preset DOCKED (the same exporter as runtime-export)
  wf_route_v1.json                                             data/simulations/ (NAV-001 import, unchanged)
The MPFB characters are not built here: the walk keeps its proxy body (a presentation-only difference). In the workspace copy
export_presets.cfg is written; the project's godot/ and godot/generated/ are never touched. It then runs the walk's own check
natively in the same workspace (the native reference for this package), exports Web (no threads: no COOP/COEP headers needed)
and, optionally, a native Linux build of the same package.

Reuse: the staged project is reproducible but Godot's .pck is not (two exports of identical inputs differ), so an unchanged Enter
Wayfarer is recognised by its input key (`input_key`: the staged files with the manifests' commit fields left out, the shell, this
module and the pinned Godot). Given a previous verified site whose play record carries the same key, passing play and equivalence
tests and play files matching its release.json, build() copies those files (and its native zip) instead of importing, checking
and exporting again; the browser check then carries that release's browser-vs-native result.

Godot is the official 4.7.2 standard (not Mono) build and templates, SHA-512 checked against the release's SHA512-SUMS and kept
in a cache; only the templates used are extracted from the 1.3 GB archive.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.request
import zipfile

import pipeline

GODOT = {'version': '4.7.2', 'tag': '4.7.2-stable', 'version_line': '4.7.2.stable.official.ed1daf0bf',
         'release': 'https://github.com/godotengine/godot/releases/download/4.7.2-stable/',
         'editor': ('Godot_v4.7.2-stable_linux.x86_64.zip', '9aa00f7a605200940bce3027a567b782f49bd8e940dd06ae9e987bd65aee1b1467edd56ed84fcdcbdd44354bf613bdbb4e5d2913e925850368e150c59ed54c65'),
         'templates': ('Godot_v4.7.2-stable_export_templates.tpz', 'ca4d71c4d7b81dfc15d1a98baa07534aa95b03fdda78a0075b06672e1648d2e5f40980c9adc28d23e1b92e732ee7bf3461997aa804af74ec2fcd7a93ccb84079')}
# The templates taken out of the archive; their SHA-256 at extraction (from the SHA-512-checked archive) is kept in templates.json.
TEMPLATES = ('web_nothreads_release.zip', 'linux_release.x86_64')
# Godot's own licence texts, shipped with the export (59 POL-010/011: attribution before publication).
LICENSES = {'LICENSE.txt': ('https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/LICENSE.txt',
                           'b0435e3b3e4e55238f05f4b306f30524a1b2e20147810d436eaa554fa6855c80'),
            'COPYRIGHT.txt': ('https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/COPYRIGHT.txt',
                              'cb1980c88089573bcacd7221d777c689bb8bbd778799f24c27fca0fe5f774d6d')}
CACHE = Path(os.environ.get('WAYFARER_GODOT_CACHE') or Path.home() / '.cache/wayfarer/godot-4.7.2')
PCK_LIMIT = 95_000_000            # GitHub Pages refuses files over 100 MB
SCENE = 'res://scenes/excursion.tscn'
WALK_CHECK = ['--fixed-fps', '60', SCENE, '--quit-after', '300000', '--', '--check-excursion']
PRESETS = '''[preset.0]

name="Web"
platform="Web"
runnable=true
dedicated_server=false
custom_features=""
export_filter="all_resources"
include_filter="generated/*.json"
exclude_filter=""
export_path=""
encryption_include_filters=""
encryption_exclude_filters=""
encrypt_pck=false
encrypt_directory=false

[preset.0.options]

custom_template/debug=""
custom_template/release="{web}"
variant/extensions_support=false
variant/thread_support=false
vram_texture_compression/for_desktop=true
vram_texture_compression/for_mobile=false
html/export_icon=false
html/custom_html_shell="{shell}"
html/head_include=""
html/canvas_resize_policy=2
html/focus_canvas_on_start=true
html/experimental_virtual_keyboard=false
progressive_web_app/enabled=false

[preset.1]

name="Linux"
platform="Linux"
runnable=false
dedicated_server=false
custom_features=""
export_filter="all_resources"
include_filter="generated/*.json"
exclude_filter=""
export_path=""
encryption_include_filters=""
encryption_exclude_filters=""
encrypt_pck=false
encrypt_directory=false

[preset.1.options]

custom_template/debug=""
custom_template/release="{linux}"
debug/export_console_wrapper=0
binary_format/embed_pck=false
binary_format/architecture="x86_64"
texture_format/s3tc_bptc=true
texture_format/etc2_astc=false
'''


def sha(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def fetch(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + '.part')
    with urllib.request.urlopen(url, timeout=600) as response, open(part, 'wb') as f:
        shutil.copyfileobj(response, f, 1 << 20)
    part.rename(path)


def toolchain(native=False):
    """The pinned editor and the needed templates in the cache, downloaded and verified once; returns their paths."""
    editor = CACHE / 'Godot_v4.7.2-stable_linux.x86_64'
    if not editor.exists():
        name, digest = GODOT['editor']
        archive = CACHE / name
        fetch(GODOT['release'] + name, archive)
        if sha(archive, 'sha512') != digest:
            archive.unlink()
            raise ValueError(f'{name}: SHA-512 mismatch (deleted)')
        with zipfile.ZipFile(archive) as z:
            z.extract(editor.name, CACHE)
        editor.chmod(0o755)
        archive.unlink()
    wanted = ['web_nothreads_release.zip', *(['linux_release.x86_64'] if native else [])]
    stamp = CACHE / 'templates.json'
    known = json.loads(stamp.read_text()) if stamp.exists() else {}
    if any(not (CACHE / t).exists() or known.get(t) != sha(CACHE / t) for t in wanted):
        name, digest = GODOT['templates']
        archive = CACHE / name
        fetch(GODOT['release'] + name, archive)
        if sha(archive, 'sha512') != digest:
            archive.unlink()
            raise ValueError(f'{name}: SHA-512 mismatch (deleted)')
        with zipfile.ZipFile(archive) as z:
            for t in TEMPLATES:
                (CACHE / t).write_bytes(z.read(f'templates/{t}'))
                known[t] = sha(CACHE / t)
        archive.unlink()                 # 1.3 GB; the extracted templates are what the cache keeps
        stamp.write_text(json.dumps(known, indent=1) + '\n')
    for name, (url, digest) in LICENSES.items():
        if not (CACHE / name).exists():
            fetch(url, CACHE / name)
        if sha(CACHE / name) != digest:
            (CACHE / name).unlink()
            raise ValueError(f'Godot {name}: SHA-256 mismatch (deleted)')
    version = subprocess.run([str(editor), '--headless', '--version'], capture_output=True, text=True, timeout=60).stdout.strip().splitlines()[-1]
    if version != GODOT['version_line']:
        raise ValueError(f'Godot reports {version!r}, expected {GODOT["version_line"]}')
    return {'editor': editor, 'web': CACHE / 'web_nothreads_release.zip', 'linux': CACHE / 'linux_release.x86_64',
            'version': version, 'templates': {t: known[t] for t in wanted}}


def walk_result(log):
    """The walk's check (excursion check.gd) from its log: its result, failures and the route milestones it noted."""
    line = next((l for l in Path(log).read_text(errors='replace').splitlines() if l.startswith('WF_GODOT_EXCURSION ')), None)
    if line is None:
        return {'result': 'FAIL', 'reason': 'no WF_GODOT_EXCURSION line'}
    data = json.loads(line.split(' ', 1)[1])
    return {'result': data.get('result'), 'fails': data.get('fails', []), 'notes': sorted(data.get('notes', {})),
            'physics_frames': data.get('physics_frames'), 'errors': Path(log).read_text(errors='replace').count('ERROR:')}


def input_key(project, tools, shell):
    """SHA-256 over what decides the play package: the staged project (no .godot, imports or export_presets.cfg, whose template
    paths are machine-specific), with `identity.git_revision`/`git_dirty` left out of the manifests (the only commit-dependent
    bytes), plus the Web shell, this module (presets, check arguments, naming) and the pinned Godot build and templates."""
    h = hashlib.sha256()
    for path in sorted(p for p in project.rglob('*') if p.is_file()):
        rel = path.relative_to(project).as_posix()
        if rel.startswith('.godot/') or rel.endswith('.import') or rel == 'export_presets.cfg':
            continue
        data = path.read_bytes()
        if path.suffix == '.json':
            try:
                record = json.loads(data)
            except ValueError:
                record = None
            if isinstance(record, dict) and isinstance(record.get('identity'), dict):
                record['identity'] = {k: v for k, v in record['identity'].items() if k not in ('git_revision', 'git_dirty')}
                data = json.dumps(record, sort_keys=True).encode()
        h.update(f'{rel}\0{hashlib.sha256(data).hexdigest()}\n'.encode())
    for extra in (Path(shell), Path(__file__)):
        h.update(f'{extra.name}\0{sha(extra)}\n'.encode())
    h.update(json.dumps({'godot': tools['version'], 'templates': tools['templates']}, sort_keys=True).encode())
    return h.hexdigest()


def reusable(previous, key, native_zip=None):
    """(release.json, None) when the site at `previous` holds a verified play build with this input key, else (None, reason)."""
    try:
        release = json.loads((Path(previous) / 'release.json').read_text())
    except (OSError, ValueError) as error:
        return None, f'no previous release.json ({error})'
    play, tests = release.get('experiences', {}).get('play'), release.get('tests') or {}
    if not play or not play.get('input_key'):
        return None, f"release {release.get('release')} has no play input key"
    if play['input_key'] != key:
        return None, f"play inputs changed since release {release.get('release')}"
    for name in ('play', 'equivalence'):
        if (tests.get(name) or {}).get('result') != 'PASS':
            return None, f"release {release.get('release')}: {name} tests did not pass"
    for f in [*play['files'].values(), *(f'GODOT_{n}' for n in LICENSES)]:
        entry, path = release['files'].get(f'play/{f}'), Path(previous) / 'play' / f
        if not entry or not path.is_file() or sha(path) != entry['sha256']:
            return None, f"release {release.get('release')}: play/{f} missing or not as recorded"
    if native_zip is not None and (not play.get('native_zip_sha256') or not Path(native_zip).is_file()
                                   or sha(native_zip) != play['native_zip_sha256']):
        return None, f"release {release.get('release')}: no matching native Linux zip"
    return release, None


def run_logged(command, log, root, timeout=pipeline.STEP_TIMEOUT):
    return pipeline.subprocess_runner(command, log, root, timeout)


def build(root, run_dir, out, identity, native=False, native_check=True, reuse=None, reuse_native=None):
    """Workspace -> package -> import -> native walk check -> Web export into `out` (the site's play/ directory).
    With `reuse` (a previous site directory; `reuse_native` its native Linux zip when native=True), an unchanged package is copied
    from there instead (see the module docstring). Returns the play record for release.json; raises on any failure."""
    t0 = time.monotonic()
    tools = toolchain(native)
    work = run_dir / 'play'
    project = work / 'godot'
    shutil.copytree(root / 'godot', project, ignore=shutil.ignore_patterns('.godot', 'generated', 'export_presets.cfg'))
    generated = project / 'generated'
    generated.mkdir()
    seconds = {}

    def step(name, command, timeout=pipeline.STEP_TIMEOUT):
        s = time.monotonic()
        log = run_dir / f'play-{name}.log'
        if run_logged(command, log, root, timeout):
            raise RuntimeError(f'play step {name} failed: {pipeline.failure_tail(log)}')
        seconds[name] = round(time.monotonic() - s, 1)
        return log

    step('export-docked', pipeline.blender(root / 'src/wayfarer/export/godot.py', '--root', root, '--preset', 'DOCKED',
                                           '--out', generated, '--identity', identity))
    shutil.copy2(root / 'data/simulations/wf_route_v1.json', generated / 'wf_route_v1.json')
    if f'run/main_scene="{SCENE}"' not in (project / 'project.godot').read_text():
        raise ValueError(f'project.godot: run/main_scene is not {SCENE}')
    (project / 'export_presets.cfg').write_text(PRESETS.format(web=tools['web'], linux=tools['linux'],
                                                               shell=root / 'web/play/shell.html'))
    key = input_key(project, tools, root / 'web/play/shell.html')
    if not reuse or not native_check or (native and not reuse_native):
        previous, why = None, 'no previous site (and native zip) given'
    else:
        previous, why = reusable(reuse, key, reuse_native if native else None)
    if previous:
        return reused(previous, Path(reuse), out, run_dir, key, tools, generated, native and reuse_native, seconds, t0)
    godot = str(tools['editor'])
    log = step('import', [godot, '--headless', '--path', str(project), '--editor', '--import'])
    if 'ERROR:' in log.read_text(errors='replace'):
        raise RuntimeError(f'play import reported errors: {pipeline.failure_tail(log)}')
    native_ref = None
    if native_check:
        s = time.monotonic()
        log = run_dir / 'play-native-walk-check.log'
        run_logged([godot, '--headless', '--fixed-fps', '60', '--path', str(project), *WALK_CHECK[2:]], log, root)
        native_ref = {**walk_result(log), 'seconds': round(time.monotonic() - s, 1), 'godot': tools['version'],
                      'note': 'Godot 4.7.2 headless on Linux, --fixed-fps 60, same workspace and package as the Web export'}
        if native_ref['result'] != 'PASS':
            raise RuntimeError(f'native walk check failed on the web package: {native_ref}')
    export = work / 'web'
    export.mkdir()
    step('export-web', [godot, '--headless', '--path', str(project), '--export-release', 'Web', str(export / 'wayfarer.html')])
    files = content_named(export, out)
    for name in LICENSES:
        shutil.copy2(CACHE / name, out / f'GODOT_{name}')
    native_zip = None
    if native:
        linux = work / 'linux'
        linux.mkdir()
        step('export-linux', [godot, '--headless', '--path', str(project), '--export-release', 'Linux', str(linux / 'wayfarer_walk.x86_64')])
        for name in LICENSES:
            shutil.copy2(CACHE / name, linux / f'GODOT_{name}')
        (linux / 'README.txt').write_text(NATIVE_README)
        native_zip = run_dir / 'wayfarer-walk-linux-x86_64.zip'
        with zipfile.ZipFile(native_zip, 'w', zipfile.ZIP_DEFLATED) as z:
            for p in sorted(linux.iterdir()):
                z.write(p, f'wayfarer-walk/{p.name}')
    sizes = {k: (out / v).stat().st_size for k, v in files.items()}
    if sizes['pck'] > PCK_LIMIT or sizes['wasm'] > PCK_LIMIT:
        raise ValueError(f'play files over the Pages limit: {sizes}')
    return {'entry': files['html'], 'files': files, 'bytes': sizes, 'godot': tools['version'], 'templates': tools['templates'],
            'variant': VARIANT, 'scene': SCENE,
            'package': sorted(p.name for p in generated.iterdir() if not p.name.endswith('.import')),
            'reduced_fidelity': REDUCED_FIDELITY, 'native_reference': native_ref, 'native_zip': str(native_zip) if native_zip else None,
            'native_zip_sha256': sha(native_zip) if native_zip else None, 'input_key': key, 'reused_from': None, 'reuse_note': why,
            'step_seconds': seconds, 'seconds': round(time.monotonic() - t0, 1)}


VARIANT = 'web_nothreads_release (single-threaded, no GDExtension, WebGL 2 / Compatibility)'
REDUCED_FIDELITY = ['MPFB characters not packaged: the proxy body stands in (presentation only)']


def reused(previous, site, out, run_dir, key, tools, generated, native_zip, seconds, t0):
    """The play record for files copied from a verified previous site with the same input key (checked by reusable())."""
    play = previous['experiences']['play']
    out.mkdir(parents=True, exist_ok=True)
    for f in [*play['files'].values(), *(f'GODOT_{n}' for n in LICENSES)]:
        shutil.copy2(site / 'play' / f, out / f)
    target = None
    if native_zip:
        target = run_dir / 'wayfarer-walk-linux-x86_64.zip'
        shutil.copy2(native_zip, target)
    package = sorted(p.name for p in generated.iterdir() if not p.name.endswith('.import'))
    if package != play['package']:
        raise ValueError(f'reused package lists differ: {package} vs {play["package"]}')
    tests = previous['tests']
    return {'entry': play['files']['html'], 'files': play['files'], 'bytes': {k: (out / v).stat().st_size for k, v in play['files'].items()},
            'godot': tools['version'], 'templates': tools['templates'], 'variant': VARIANT, 'scene': play['scene'], 'package': package,
            'reduced_fidelity': REDUCED_FIDELITY, 'native_reference': play['native_reference'],
            'native_zip': str(target) if target else None, 'native_zip_sha256': play.get('native_zip_sha256') if target else None,
            'input_key': key, 'reused_from': {'release': previous['release'], 'git_revision': previous['git_revision'],
                                              'play': tests['play'], 'equivalence': tests['equivalence']},
            'reuse_note': f"same inputs as release {previous['release']}: import, native check and exports skipped",
            'step_seconds': seconds, 'seconds': round(time.monotonic() - t0, 1)}


def content_named(export, out):
    """Give the export content-unique names (Pages caches every file for 10 minutes, and the shell, engine and pack must come from
    one export): engine-<hash>.{js,wasm,audio*.js} and walk-<hash>.{pck,html}. Returns {kind: site file name}."""
    out.mkdir(parents=True, exist_ok=True)
    html = (export / 'wayfarer.html').read_text()
    engine = 'engine-' + hashlib.sha256((export / 'wayfarer.wasm').read_bytes() + (export / 'wayfarer.js').read_bytes()).hexdigest()[:12]
    pack = 'walk-' + sha(export / 'wayfarer.pck')[:12]
    config = re.search(r'const GODOT_CONFIG = (\{.*?\});\n', html)
    if not config:
        raise ValueError('shell: GODOT_CONFIG not found')
    data = json.loads(config.group(1))
    if data.get('executable') != 'wayfarer' or data.get('mainPack') not in (None, 'wayfarer.pck'):
        raise ValueError(f'unexpected export config {data.get("executable")}, {data.get("mainPack")}')
    data['executable'], data['mainPack'] = engine, f'{pack}.pck'
    data['fileSizes'] = {f'{pack}.pck': (export / 'wayfarer.pck').stat().st_size, f'{engine}.wasm': (export / 'wayfarer.wasm').stat().st_size}
    html = html.replace(config.group(1), json.dumps(data, separators=(',', ':')))
    if html.count('<script src="wayfarer.js">') != 1:
        raise ValueError('shell: engine script tag not found')
    html = html.replace('<script src="wayfarer.js">', f'<script src="{engine}.js">')
    files = {'html': f'{pack}.html', 'js': f'{engine}.js', 'wasm': f'{engine}.wasm', 'pck': f'{pack}.pck'}
    (out / files['html']).write_text(html)
    for kind in ('js', 'wasm', 'pck'):
        shutil.copy2(export / f'wayfarer.{kind}', out / files[kind])
    for worklet in sorted(export.glob('wayfarer.audio*.js')):          # loaded by the engine as <executable>.audio*.js
        target = engine + worklet.name[len('wayfarer'):]
        shutil.copy2(worklet, out / target)
        files[worklet.name[len('wayfarer.'):-3]] = target
    unknown = sorted(p.name for p in export.iterdir() if p.suffix not in ('.html', '.js', '.wasm', '.pck', '.png'))   # the unused splash
    if unknown:
        raise ValueError(f'unexpected export files {unknown}')
    return files


NATIVE_README = """G.U. WAYFARER 001 - the walk (EXC-001), native Linux x86_64 build (Godot 4.7.2, Compatibility renderer).

The same package as the browser build at https://densho-media.github.io/ignition-wayfarer/play/ (DOCKED REP_PROXY export, proxy
body). Run ./wayfarer_walk.x86_64 from this directory. SIMULATION_ONLY: no transfer timing, procedure or interlock is released;
see the in-game labels. The development runtime (with the MPFB characters) is built from the repository with
python3 tools/workflow.py runtime-export. Godot Engine: MIT licence, see GODOT_LICENSE.txt and GODOT_COPYRIGHT.txt.
"""
