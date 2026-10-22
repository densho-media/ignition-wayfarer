"""Enter Wayfarer (WEB-002): Integrated Demonstrator 01 as a single-threaded Godot Web export, built in a disposable workspace.

`build()` (called by web_export.run, `workflow.py web`) copies godot/ into the run directory, fills its generated/ with the
package Demonstrator 01 reads, all from the saved assets and tracked inputs:
  wayfarer_docked.glb, manifest_docked.json, wf_sim_rig.json   export/godot.py --preset DOCKED (the same exporter as runtime-export)
  manifest.json                                                the COAST manifest of the viewer export (forward explorer)
  wf_route_v1.json                                             simulations/ (NAV-001 import, unchanged)
  wf_eva.json                                                  eva_route.py with the tracked EVA references (remote view only)
The MPFB characters and EVA suits are not built here: boarding.gd keeps the exported proxies (a presentation-only difference).
In the workspace copy only, the main scene becomes demo01.tscn (60 UX-002/UX-017: one visitor journey, the review menu stays a
developer tool) and export_presets.cfg is written; the project's godot/ and godot/generated/ are never touched.
It then runs Demonstrator 01's own check natively in the same workspace (the native reference for this package), exports Web
(no threads: no COOP/COEP headers needed) and, optionally, a native Linux build of the same package.

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
DEMO_CHECK = ['--fixed-fps', '60', 'res://scenes/demo01.tscn', '--quit-after', '60000', '--', '--check-demo']
RECORDING = ['--fixed-fps', '30', 'res://scenes/demo01.tscn', '--quit-after', '20000', '--', '--autoplay', '--record-exit']
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


def demo_result(log):
    line = next((l for l in Path(log).read_text(errors='replace').splitlines() if l.startswith('WF_GODOT_DEMO ')), None)
    if line is None:
        return {'result': 'FAIL', 'reason': 'no WF_GODOT_DEMO line'}
    data = json.loads(line.split(' ', 1)[1])
    failed = [c['id'] for c in data['checks'] if not c['ok']]
    return {'result': data.get('result'), 'checks': len(data['checks']), 'failed': failed,
            'errors': Path(log).read_text(errors='replace').count('ERROR:'), 'ok_by_check': {c['id']: c['ok'] for c in data['checks']}}


def run_logged(command, log, root, timeout=pipeline.STEP_TIMEOUT):
    return pipeline.subprocess_runner(command, log, root, timeout)


def build(root, run_dir, out, coast_manifest, identity, native=False, native_check=True):
    """Workspace -> package -> import -> native Demonstrator 01 check -> Web export into `out` (the site's play/ directory).
    Returns the play record for release.json; raises on any failure (the site is then not assembled)."""
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
    shutil.copy2(coast_manifest, generated / 'manifest.json')
    shutil.copy2(root / 'simulations/wf_route_v1.json', generated / 'wf_route_v1.json')
    step('eva-route', ['python3', str(root / 'src/wayfarer/eva_route.py'), '--root', str(root), '--out', str(generated),
                       '--access', str(root / 'references/p1_eva_access.json'), '--sp11', str(root / 'references/p1_eva_sp11.json')])
    settings = project / 'project.godot'
    text, n = re.subn(r'^run/main_scene=.*$', 'run/main_scene="res://scenes/demo01.tscn"', settings.read_text(), flags=re.M)
    if n != 1:
        raise ValueError('project.godot: run/main_scene not found')
    settings.write_text(text)
    (project / 'export_presets.cfg').write_text(PRESETS.format(web=tools['web'], linux=tools['linux'],
                                                               shell=root / 'web/play/shell.html'))
    godot = str(tools['editor'])
    log = step('import', [godot, '--headless', '--path', str(project), '--editor', '--import'])
    if 'ERROR:' in log.read_text(errors='replace'):
        raise RuntimeError(f'play import reported errors: {pipeline.failure_tail(log)}')
    native_ref = None
    if native_check:
        s = time.monotonic()
        log = run_dir / 'play-native-demo-check.log'
        run_logged([godot, '--headless', '--fixed-fps', '60', '--path', str(project), *DEMO_CHECK[2:]], log, root)
        native_ref = {**demo_result(log), 'seconds': round(time.monotonic() - s, 1), 'godot': tools['version'],
                      'note': 'Godot 4.7.2 headless on Linux, --fixed-fps 60, same workspace and package as the Web export'}
        if native_ref['result'] != 'PASS':
            raise RuntimeError(f'native Demonstrator 01 check failed on the web package: {native_ref}')
        # The run the browser check repeats in the Web build: the whole journey in autoplay at a fixed 30 fps (web_check.py compares).
        log = run_dir / 'play-native-recording.log'
        run_logged([godot, '--headless', '--path', str(project), *RECORDING], log, root)
        line = next((l for l in log.read_text(errors='replace').splitlines() if l.startswith('WF_DEMO_RECORDING ')), None)
        native_ref['recording'] = json.loads(line.split(' ', 1)[1]) if line else None
        native_ref['recording_args'] = RECORDING
        if not line or native_ref['recording']['result'] != 'PASS':
            raise RuntimeError(f'native Demonstrator 01 recording failed on the web package: {native_ref["recording"]}')
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
        step('export-linux', [godot, '--headless', '--path', str(project), '--export-release', 'Linux', str(linux / 'wayfarer_demo01.x86_64')])
        for name in LICENSES:
            shutil.copy2(CACHE / name, linux / f'GODOT_{name}')
        (linux / 'README.txt').write_text(NATIVE_README)
        native_zip = run_dir / 'wayfarer-demo01-linux-x86_64.zip'
        with zipfile.ZipFile(native_zip, 'w', zipfile.ZIP_DEFLATED) as z:
            for p in sorted(linux.iterdir()):
                z.write(p, f'wayfarer-demo01/{p.name}')
    sizes = {k: (out / v).stat().st_size for k, v in files.items()}
    if sizes['pck'] > PCK_LIMIT or sizes['wasm'] > PCK_LIMIT:
        raise ValueError(f'play files over the Pages limit: {sizes}')
    return {'entry': files['html'], 'files': files, 'bytes': sizes, 'godot': tools['version'], 'templates': tools['templates'],
            'variant': 'web_nothreads_release (single-threaded, no GDExtension, WebGL 2 / Compatibility)',
            'scene': 'res://scenes/demo01.tscn', 'package': sorted(p.name for p in generated.iterdir() if not p.name.endswith('.import')),
            'reduced_fidelity': ['MPFB induction pair and EVA suits not packaged: the exported proxies stand in (presentation only)'],
            'native_reference': native_ref, 'native_zip': str(native_zip) if native_zip else None,
            'step_seconds': seconds, 'seconds': round(time.monotonic() - t0, 1)}


def content_named(export, out):
    """Give the export content-unique names (Pages caches every file for 10 minutes, and the shell, engine and pack must come from
    one export): engine-<hash>.{js,wasm,audio*.js} and demo01-<hash>.{pck,html}. Returns {kind: site file name}."""
    out.mkdir(parents=True, exist_ok=True)
    html = (export / 'wayfarer.html').read_text()
    engine = 'engine-' + hashlib.sha256((export / 'wayfarer.wasm').read_bytes() + (export / 'wayfarer.js').read_bytes()).hexdigest()[:12]
    pack = 'demo01-' + sha(export / 'wayfarer.pck')[:12]
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


NATIVE_README = """G.U. WAYFARER 001 - Integrated Demonstrator 01, native Linux x86_64 build (Godot 4.7.2, Compatibility renderer).

The same package as the browser build at https://densho-media.github.io/ignition-wayfarer/play/ (DOCKED REP_PROXY export, proxy
characters). Run ./wayfarer_demo01.x86_64 from this directory. SIMULATION_ONLY: no transfer timing, procedure or interlock is
released; see the in-game labels. The full development runtime (review menu, characters, EVA) is built from the repository with
python3 tools/workflow.py runtime-export. Godot Engine: MIT licence, see GODOT_LICENSE.txt and GODOT_COPYRIGHT.txt.
"""
