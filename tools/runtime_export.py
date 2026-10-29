"""Explicit runtime publishing and local Godot checks; production Blender assets are never opened for writing.

`run()` (workflow.py runtime-export) builds in a disposable workspace, exports the COAST and DOCKED packages, runs every Godot check
there and publishes `godot/generated/` with a `build_identity.json` naming the package inputs. `check()` (workflow.py runtime-check)
runs selected Godot checks in the real project against that published package after confirming every package input (code, data,
route, character assets, project settings and tool versions) still matches; a stale package is refused, never reported as current.
Pruning is a proposal only (`prune_candidates`); nothing is deleted here.
"""
import json
import re
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone

import pipeline
from workflow import write_lock

GODOT = os.environ.get('WAYFARER_GODOT', '/snap/bin/godot-4')
IDENTITY = 'build_identity.json'
# Godot checks: name, arguments after `--path <project>`, the scene or script it runs (for change selection), what it needs from the
# package and the PASS marker its log must contain. Godot may return zero for a scene whose attached script failed, so every check
# also fails on 'ERROR:'.
CHECKS = [
    dict(name='check', args=['--script', 'res://scripts/check_export.gd'], script='scripts/check_export.gd'),
    dict(name='check-docked', args=['--script', 'res://scripts/check_export.gd', '--', '--docked'], script='scripts/check_export.gd'),
    # PHYS-001 phase 9: the packaged route sampled at every released row reproduces it (C-001/C-010); WF_GODOT_ROUTE.
    dict(name='route', args=['--script', 'res://scripts/check_route.gd'], script='scripts/check_route.gd', marker='"result":"PASS"'),
    # EXC-001: station -> ring A circuit -> station, then ring B, by the player's own actions (excursion check.gd); WF_GODOT_EXCURSION.
    dict(name='excursion', args=['--fixed-fps', '60', 'res://scenes/excursion.tscn', '--quit-after', '300000', '--', '--check-excursion'],
         scene='scenes/excursion.tscn', marker='"result":"PASS"'),
    # The MPFB humans (docs/CHARACTERS.md), once `workflow.py characters` has built them.
    dict(name='characters', args=['--script', 'res://scripts/check_characters.gd'], script='scripts/check_characters.gd', needs='humans'),
]


def godot_command(project, check):
    args = list(check['args']); pre = []
    if args[:2] == ['--fixed-fps', '60']:
        pre, args = args[:2], args[2:]
    return [GODOT, '--headless', *pre, '--path', str(project), *args]


def failed(check, log):
    text = Path(log).read_text(errors='replace')
    return 'ERROR:' in text or (check.get('marker') and check['marker'] not in text)


def versions():
    """Tool versions that shape the package: the Blender that exported it and the Godot that imports and runs it."""
    out = {}
    for key, argv in (('blender', [pipeline.BLENDER, '--version']), ('godot', [GODOT, '--version'])):
        try:
            out[key] = subprocess.run(argv, capture_output=True, text=True, timeout=60).stdout.strip().splitlines()[0]
        except (OSError, IndexError, subprocess.TimeoutExpired):
            out[key] = None
    return out


def package_inputs(root):
    """{path: sha256} of everything the published package is built from: the Python (build, export and the shared formulas),
    this exporter, every data TOML, the imported route, the character assets and the Godot project settings. Godot
    scripts and scenes are not package inputs: runtime-check runs the current ones against the package."""
    src = root/'src/wayfarer'
    paths = [*sorted(p for p in src.rglob('*.py') if '__pycache__' not in p.parts),
             root/'tools/runtime_export.py', *sorted((root/'data').glob('*.toml')), *sorted(p for p in (root/'data/detail').rglob('*') if p.is_file()),
             root/'godot/project.godot',
             *(p for p in (root/'data/simulations/wf_route_v1.json',) if p.exists()),
             *sorted((root/'assets/characters').glob('WF_CHAR_HUMAN_*.blend'))]
    return {str(p.relative_to(root)): pipeline.sha256(p) for p in paths}


def study_layout(work, eye_layout):
    """H03 labelled study: select an Eye layout in the workspace copy of the data only (the project's TOML, r4 canon, is never touched)."""
    path = work / 'data/wayfarer_3d.toml'
    text = path.read_text()
    head = text.index('[forward_defense.eye_layout]')
    m = re.compile(r'^selected = "[^"]*"$', re.M).search(text, head)
    if m is None or text.find('\n[', head + 1) < m.start():
        raise ValueError('forward_defense.eye_layout.selected not found')
    path.write_text(text[:m.start()] + f'selected = "{eye_layout}"' + text[m.end():])


def run(root, eye_layout=None):
    """eye_layout (H03): publish a labelled STUDY package with that Eye layout, built only in the workspace; runtime-check refuses it
    until a plain runtime-export restores the canonical package."""
    with write_lock(root) as lock:
        if lock is None:
            return {'result': 'BUSY'}
        run_dir = root / 'runs' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-runtime')
        work = run_dir / 'work'
        work.mkdir(parents=True)
        shutil.copytree(root / 'data', work / 'data')
        if eye_layout:
            study_layout(work, eye_layout)
        shutil.copytree(root / 'godot', work / 'godot',
                        ignore=shutil.ignore_patterns('.godot', 'generated'))
        # PHYS-001 phase 9: the imported route (NAV-001) travels with the COAST package for the rebased flight playback.
        if (root / 'data/simulations/wf_route_v1.json').exists():
            (work / 'data/simulations').mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / 'data/simulations/wf_route_v1.json', work / 'data/simulations/wf_route_v1.json')
        sources = [*sorted(p for p in (root / 'src/wayfarer').rglob('*.py') if '__pycache__' not in p.parts),
                   root / 'tools/runtime_export.py', root / 'tools/workflow.py',
                   *sorted((root / 'godot').rglob('*.gd')),
                   root / 'godot/project.godot', *sorted((root / 'godot/scenes').glob('*.tscn'))]
        identity = {str(p.relative_to(root)): pipeline.sha256(p) for p in sources}
        identity.update({str(p.relative_to(root)): pipeline.sha256(p) for p in [*(root / 'data').glob('*.toml'), *(p for p in (root / 'data/detail').rglob('*') if p.is_file())]})
        def git(*args):
            return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
        package = {'package_inputs': package_inputs(root), 'versions': versions(), 'git_revision': git('rev-parse', 'HEAD'),
                   'git_dirty': bool(git('status', '--porcelain')), 'built_utc': pipeline.utc_now(), 'run_dir': run_dir.name}
        if eye_layout:
            package['study'] = {'eye_layout': eye_layout, 'label': f'STUDY package: Eye layout {eye_layout}. Not canon: the owner keeps r4 '
                                f'and B_array 8 m WORKING (Eye 45 FD-B07); no mass, FEA, stiffness or optics value comes with it.'}
        (work / 'build_identity.json').write_text(json.dumps({
            'source_hashes': identity, 'git_revision': package['git_revision'],
            'git_dirty': package['git_dirty'], 'build': 'fresh disposable full build',
        }, indent=2) + '\n')
        project = work / 'godot'
        commands = [
            ('build', pipeline.blender(root / 'src/wayfarer/build/build.py', '--root', work)),
            *([('inspect', pipeline.blender(root / 'src/wayfarer/validation/inspect.py', '--root', work, '--output', run_dir / 'validation.json'))] if eye_layout else []),
            ('export', pipeline.blender(root / 'src/wayfarer/export/godot.py', '--root', work)),
            ('export-docked', pipeline.blender(root / 'src/wayfarer/export/godot.py', '--root', work, '--preset', 'DOCKED')),
            ('import', [GODOT, '--headless', '--path', str(project), '--editor', '--import']),
        ]
        humans = sorted((root / 'assets/characters').glob('WF_CHAR_HUMAN_*.blend'))
        if humans:
            identity.update({str(h.relative_to(root)): pipeline.sha256(h) for h in humans})
            commands[3:3] = [('export-characters', pipeline.blender(root / 'src/wayfarer/export/human_gltf.py', '--out', work / 'godot/generated/characters'))]
        # The MPFB humans are required package content: a missing asset fails the export instead of skipping its checks.
        if not humans:
            return {'result': 'FAIL', 'step': 'assets', 'reason': 'required runtime assets missing: characters (python3 tools/workflow.py characters)',
                    'run_dir': str(run_dir)}
        checks = list(CHECKS)
        for name, command in commands:
            log = run_dir / f'{name}.log'
            code = pipeline.subprocess_runner(command, log, root, pipeline.STEP_TIMEOUT)
            if code or (name == 'import' and 'ERROR:' in log.read_text()):
                return {'result': 'FAIL', 'step': name, 'log': str(log), 'tail': pipeline.failure_tail(log)}
        for check in checks:
            log = run_dir / f'{check["name"]}.log'
            code = pipeline.subprocess_runner(godot_command(project, check), log, root, pipeline.STEP_TIMEOUT)
            if code or failed(check, log):
                return {'result': 'FAIL', 'step': check['name'], 'log': str(log), 'tail': pipeline.failure_tail(log)}
        # Source changes during a build must not publish a mixed snapshot.
        if any(pipeline.sha256(root / p) != digest for p, digest in identity.items()) or package_inputs(root) != package['package_inputs']:
            return {'result': 'FAIL', 'reason': 'Sources changed during export; rerun.', 'run_dir': str(run_dir)}
        package['checks'] = [c['name'] for c in checks]
        (work / 'godot/generated' / IDENTITY).write_text(json.dumps(package, indent=1) + '\n')
        target = root / 'godot/generated'
        backup = run_dir / 'previous-generated'
        if target.exists():
            target.rename(backup)
        try:
            (work / 'godot/generated').rename(target)
        except OSError:
            if backup.exists():
                backup.rename(target)
            raise
        # Running a Godot project does not perform the editor's initial GLB import.
        # Initialize the real project's cache so the documented launch works now.
        import_log = run_dir / 'import-published.log'
        command = [GODOT, '--headless', '--path', str(root / 'godot'), '--editor', '--import']
        code = pipeline.subprocess_runner(command, import_log, root, pipeline.STEP_TIMEOUT)
        if code or 'ERROR:' in import_log.read_text():
            target.rename(run_dir / 'failed-generated')
            if backup.exists():
                backup.rename(target)
                pipeline.subprocess_runner(command, run_dir / 'restore-import.log', root, pipeline.STEP_TIMEOUT)
            return {'result': 'FAIL', 'step': 'import-published', 'log': str(import_log),
                    'tail': pipeline.failure_tail(import_log)}
        manifest = json.loads((target / 'manifest.json').read_text())
        result = {'result': 'PASS', 'run_dir': str(run_dir), 'generated': str(target),
                  'objects': len(manifest['nodes']), 'triangles': manifest['triangles'],
                  'bounds_runtime_m': manifest['bounds_runtime_m'], 'checks': len(checks),
                  'note': 'COAST and DOCKED frame 1, static REP_PROXY, with the First Ignition timeline; production Blender assets unchanged'}
        (run_dir / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
        candidates = prune_candidates(root)
        result['prune_proposal'] = (f"{len(candidates)} run directories, {sum(c['bytes'] for c in candidates)/1e6:.0f} MB could go; "
                                    "list them with `workflow.py prune` and delete only after the user approves") if candidates else 'none'
        return result


def package_state(root):
    """Compare the published package's recorded inputs with the current ones: CURRENT, STALE (with the differing paths) or UNIDENTIFIED."""
    path = root / 'godot/generated' / IDENTITY
    if not path.exists():
        return {'state': 'UNIDENTIFIED', 'reason': 'the published package carries no build_identity.json; run runtime-export once'}
    recorded = json.loads(path.read_text()); now = package_inputs(root)
    old = recorded['package_inputs']
    changed = sorted(p for p in set(old) | set(now) if old.get(p) != now.get(p))
    current_versions = versions()
    tools = sorted(k for k, v in recorded['versions'].items() if v != current_versions.get(k))
    state = 'CURRENT' if not changed and not tools else 'STALE'
    if recorded.get('study'):
        state = 'STUDY'
    return {'state': state, 'study': recorded.get('study'), 'git_revision': recorded['git_revision'], 'built_utc': recorded['built_utc'], 'run_dir': recorded['run_dir'],
            'changed_inputs': changed[:20], 'changed_input_count': len(changed), 'changed_tools': tools}


def check(root, names=None):
    """Run Godot checks (default all the package supports) in the real project against the published package; refuse a stale package."""
    with write_lock(root) as lock:
        if lock is None:
            return {'result': 'BUSY'}
        state = package_state(root)
        if state['state'] == 'STUDY':
            return {'result': 'STUDY', 'package': state,
                    'reason': 'the published package is a labelled study; a plain `workflow.py runtime-export` restores the canonical one'}
        if state['state'] != 'CURRENT':
            return {'result': 'STALE' if state['state'] == 'STALE' else 'FAIL', 'package': state,
                    'reason': 'the published package does not match the current inputs; run `workflow.py runtime-export` (it rebuilds, '
                              'checks everything and republishes)'}
        recorded = json.loads((root / 'godot/generated' / IDENTITY).read_text())
        known = {c['name']: c for c in CHECKS if c['name'] in recorded['checks']}
        names = list(known) if not names else names
        unknown = [n for n in names if n not in known]
        if unknown:
            return {'result': 'FAIL', 'reason': f'unknown or unpackaged checks {unknown}; choose from {list(known)}'}
        run_dir = root / 'runs' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-runtime-check')
        run_dir.mkdir(parents=True)
        out = {'run_dir': str(run_dir.relative_to(root)), 'package': state, 'checks': {}}
        for name in names:
            log = run_dir / f'{name}.log'
            code = pipeline.subprocess_runner(godot_command(root / 'godot', known[name]), log, root, pipeline.STEP_TIMEOUT)
            out['checks'][name] = 'FAIL' if code or failed(known[name], log) else 'PASS'
            if out['checks'][name] == 'FAIL':
                out.update(result='FAIL', step=name, tail=pipeline.failure_tail(log))
                break
        else:
            out['result'] = 'PASS'
        # The inputs must not change while the checks run.
        if out['result'] == 'PASS' and package_state(root)['state'] != 'CURRENT':
            out.update(result='FAIL', reason='package inputs changed during the checks; rerun')
        out['verification'] = (f"LOCAL: {len(out['checks'])} of {len(known)} Godot checks against the published package of "
                               f"{state['git_revision'][:7]} (inputs current); not a republish")
        (run_dir / 'summary.json').write_text(json.dumps(out, indent=2) + '\n')
        return out


def prune_candidates(root):
    """Run directories AGENTS.md step 6 would allow deleting, as a proposal: never the newest passing pipeline and runtime-export
    runs, any run named in TODO, the docs, references/ or the memory index, the Drive inbox or a deliberate backup (*-pre-*)."""
    runs = root / 'runs'
    def passed(d):
        try:
            return json.loads((d / 'summary.json').read_text()).get('result') == 'PASS'
        except (OSError, ValueError):
            return False
    keep = {}
    for suffix in ('-pipeline', '-runtime'):
        newest = next((d for d in sorted(runs.glob('*' + suffix), reverse=True) if passed(d)), None)
        if newest:
            keep[newest.name] = f'newest passing {suffix[1:]} run'
    texts = [root / 'TODO.md', root / 'AGENTS.md', root / 'CLAUDE.md', root / 'README.md', *(root / 'docs').rglob('*.md'),
             *(p for p in (root / 'references').rglob('*') if p.suffix in {'.md', '.json', '.txt', '.toml', '.csv'}),
             *(Path.home() / '.claude/projects' / ('-' + str(root).strip('/').replace('/', '-')) / 'memory').glob('*.md')]
    named = '\n'.join(p.read_text(errors='ignore') for p in texts if p.is_file())
    out = []
    for d in sorted(runs.iterdir()):
        if d.name in keep or d.name in ('drive_inbox', 'renders') or '-pre-' in d.name or d.name in named:
            continue
        size = sum(f.stat().st_size for f in d.rglob('*') if f.is_file()) if d.is_dir() else d.stat().st_size
        out.append({'path': str(d.relative_to(root)), 'bytes': size, 'kind': 'directory' if d.is_dir() else 'file'})
    return out
