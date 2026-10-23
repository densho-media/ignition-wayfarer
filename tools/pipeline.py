"""Wayfarer build → check → render chain.

`run()` runs spec validation, the unit tests, the Blender build, saved-asset
inspection, the geometry fingerprint diff against the current baseline, a
compact scene report and cheap previews. `quick=True` is the modeling loop:
spec, the change-selected tests (tools/checks.py), build, an optional scoped
inspection, geometry diff and draft COAST previews. Only the full run is a
whole-ship verification; a geometry change no --expect prefix explains fails
either run. Each step logs to `<run>/logs/`, the
summary is a short JSON document, and the whole run holds the project's write
lock so two sessions never build the same assets at once.
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
BLENDER = os.environ.get('WAYFARER_BLENDER', '/snap/bin/blender')
BASELINES = Path('references/baselines.json')
STEP_TIMEOUT = int(os.environ.get('WAYFARER_STEP_TIMEOUT', 1800))
INPUTS = ('data/wayfarer_3d.toml', 'data/source_map.toml')
WHOLE_SHIP_VIEWS = ('side', 'top', 'threequarter')
PREVIEW_STATES = ('COAST', 'HIGH_POWER')
FAILURE_WORDS = ('Error', 'error:', 'Traceback', 'assert', 'FAIL', 'Exception', 'refus')
QUALITIES = ('draft', 'material', 'review', 'look')     # presentation/preview.py --quality


def utc_now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def stamp():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def input_hashes(root):
    """The spec pair plus the module registry and every detail pack manifest (docs/MODULES.md): a run is accepted only on unchanged inputs."""
    out = {Path(name).name: sha256(root / name) for name in INPUTS}
    out.update({str(p.relative_to(root)): sha256(p) for p in [root / 'data/modules.toml', *sorted(p for p in (root / 'data/detail').rglob('*') if p.is_file())]
                if p.is_file()})
    return out


def current_baseline(root=PROJECT):
    return root / json.loads((root / BASELINES).read_text())['current']


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def blender(script, *args):
    return [BLENDER, '--background', '--factory-startup', '--python-exit-code', '1',
            '--python', str(script), '--', *map(str, args)]


def subprocess_runner(argv, log_path, cwd, timeout, pass_fds=()):
    """Run one step with its own process group so a timeout kills Blender too."""
    with open(log_path, 'w') as log:
        log.write('$ ' + ' '.join(map(str, argv)) + '\n')
        log.flush()
        process = subprocess.Popen(list(map(str, argv)), cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True, pass_fds=pass_fds)
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            log.write(f'\nWAYFARER PIPELINE: step exceeded {timeout} s and was killed\n')
            return 124


def failure_tail(log_path, lines=30):
    text = Path(log_path).read_text(errors='replace').splitlines()
    marked = [i for i, line in enumerate(text) if any(word in line for word in FAILURE_WORDS)]
    start = max(0, (marked[0] if marked else len(text)) - 5)
    tail = text[start:start + lines] if marked else text[-lines:]
    return [line[:240] for line in tail]


def scene_report(validation, derived=None, root=None):
    """Compact view of an inspect.py report (~40 lines instead of ~2,100)."""
    report = {'result': validation.get('result'), 'blender': validation.get('blender')}
    if root is not None:
        hashes = input_hashes(root)
        report['matches_current_inputs'] = (validation.get('spec_hash') == hashes['wayfarer_3d.toml'] and
                                            validation.get('source_map_hash') == hashes['source_map.toml'])
    keep = ('radiator_cell', 'eye_facet', 'sector_pressure', 'ring_frame', 'ring_spoke', 'ring_stop_lock', 'rotor_mechanism', 'crew_passage',
            'hull_shell', 'power_storage', 'thrust_node', 'geometry')
    for name, config in validation.get('configurations', {}).items():
        counts = config.get('evaluated_geometry_counts', {})
        report[name] = {
            'configurations': config.get('realizes'),
            'body_size_m': [round(v, 3) for v in config.get('body_bounds', {}).get('size_m', [])],
            'deployed_size_m': [round(v, 3) for v in config.get('deployed_bounds', {}).get('size_m', [])],
            'hull_contacts': (config.get('hull') or {}).get('bvh_contacts'),
            'hull_min_margin_m': (config.get('hull') or {}).get('min_enclosure_margin_m'),
            'clear_eye_rays': config.get('clear_eye_rays'),
            'counts': {k: counts[k] for k in keep if k in counts},
            'plume_margin_15deg_m': round(config.get('hypothetical_plume_vertex_margins_m', {}).get('15', float('nan')), 3)}
    radiators = validation.get('radiators', {})
    report['radiators'] = {k: round(radiators[k], 3) for k in
                           ('area_m2', 'total_planform_m2', 'blade_length_m', 'root_radius_m', 'cant_deg')
                           if isinstance(radiators.get(k), (int, float))}
    drive = validation.get('drive_manifold', {})
    report['drive'] = {'drivers': drive.get('drivers'), 'actions': len(drive.get('actions', [])),
                       'screen_pass': drive.get('screen_pass')}
    rig = validation.get('simulation_rig', {})
    report['rig'] = {k: rig.get(k) for k in ('contract_version', 'anchors', 'proxies', 'center_of_mass_placed')}
    report['assets'] = len(validation.get('assets', {}))
    if derived:
        report['spec'] = {k: derived[k] for k in ('length_m', 'body_diameter_m', 'ring_outer_radius_m', 'ring_com_radius_m',
                                                   'floor_gravity_g', 'flight_thrust_N') if k in derived}
        checks = []
        coast = validation.get('configurations', {}).get('COAST', {}).get('body_bounds', {}).get('size_m')
        if coast and 'length_m' in derived:
            checks.append({'check': 'COAST body length = spec length', 'expected': derived['length_m'],
                           'measured': round(coast[0], 4), 'ok': abs(coast[0] - derived['length_m']) < 1e-3})
        if coast and 'body_diameter_m' in derived:
            checks.append({'check': 'COAST body width <= spec diameter', 'expected': derived['body_diameter_m'],
                           'measured': round(max(coast[1:]), 4), 'ok': max(coast[1:]) <= derived['body_diameter_m'] + 1e-3})
        report['checks'] = checks
    return report


def geometry_diff(root, baseline_dir, fingerprint, expect=()):
    compare = load_module(root / 'tests/compare_fingerprint.py', 'compare_fingerprint').compare
    before = json.loads((Path(baseline_dir) / 'geometry_fingerprint.json').read_text())
    after = json.loads(Path(fingerprint).read_text())
    diff = compare(before, after)
    entries = [(kind, item) for kind in ('changed', 'added', 'removed') for item in diff[kind]]

    def expected(item):
        file_name, _, rest = item.partition(':')
        obj = rest.split(':')[0]
        return any(obj.startswith(p) or file_name.startswith(p) or Path(file_name).stem.startswith(p)
                   for p in expect)

    def expected_links(name):
        # A host whose link list changed is expected when it lost no link and every link it gained is to an expected file (a new detail
        # asset linked at its anchor), not because the host's own name is listed.
        gone = [x for x in before[name]['direct_links'] if x not in after[name]['direct_links']]
        new = [x for x in after[name]['direct_links'] if x not in before[name]['direct_links']]
        return not gone and new and all(any(Path(x).stem.startswith(p) for p in expect) for x in new)

    unexpected = [f'{kind}: {item}' for kind, item in entries if not expected(item)]
    unexpected += [f'{kind}: {name}' for kind in ('files_added', 'files_removed', 'links_changed') for name in diff[kind]
                   if not any(name.startswith(p) or Path(name).stem.startswith(p) for p in expect)
                   and not (kind == 'links_changed' and expected_links(name))]
    return {'baseline': str(baseline_dir), 'result': diff['result'],
            **{k: len(diff[k]) for k in ('changed', 'added', 'removed', 'files_added', 'files_removed', 'links_changed')},
            'expected_prefixes': list(expect), 'unexpected_count': len(unexpected),
            'unexpected': unexpected[:20], 'sample': [f'{k}: {i}' for k, i in entries[:10]]}


def run(root=PROJECT, run_dir=None, target='all', previews='auto', views=WHOLE_SHIP_VIEWS, size=512,
        expect=(), quick=False, runner=subprocess_runner, lock=True, tests=None, inspect=None, quality=None, base='HEAD'):
    """Run the chain; return the summary (also written to `<run_dir>/summary.json`).

    tests: 'auto' (tools/checks.py selection, the quick default), 'all' or 'none'; a full run always runs all.
    inspect: None/'none' (the quick default), 'auto', 'all' or a list of inspect.py groups; a full run always inspects everything.
    target 'auto' takes the build target from the change selection. quality: preview quality (quick: draft, full: review)."""
    root = Path(root).resolve()
    tests = 'all' if not quick else tests or 'auto'
    inspect = 'all' if not quick else inspect or 'none'
    quality = quality or ('draft' if quick else 'review')
    selection = None
    if quick and ('auto' in (tests, target) or inspect == 'auto'):
        sys.path.insert(0, str(PROJECT / 'tools'))
        import checks
        selection = checks.plan(root, base=base)
        if target == 'auto':
            target = selection['build_target'] or 'all'
        if inspect == 'auto':
            inspect = selection['inspect_groups'] or 'none'
    if isinstance(inspect, str) and inspect not in ('none', 'all'):
        inspect = [inspect]
    production = root == PROJECT.resolve()
    run_dir = Path(run_dir or root / 'runs' / f'{stamp()}-{"quick" if quick else "pipeline"}').resolve()
    (run_dir / 'logs').mkdir(parents=True, exist_ok=True)
    test_names = None if tests == 'all' else [] if tests == 'none' else selection['tests']
    summary = {'result': 'PASS', 'root': str(root), 'production': production, 'run_dir': str(run_dir),
               'quick': quick, 'target': target, 'started_utc': utc_now(), 'input_sha256': input_hashes(root),
               'verification': verification_scope(quick, test_names, inspect),
               'preview_quality': quality, 'steps': []}
    if selection:
        summary['selection'] = {k: selection[k] for k in ('widened_by', 'tests', 'build_target', 'inspect_groups', 'runtime_checks', 'note')}
    started = time.monotonic()
    derived = {}
    validation_path = run_dir / 'validation.json'
    fingerprint_path = run_dir / 'fingerprint.json'

    def step(name, argv, parse=None, cwd=None):
        log = run_dir / 'logs' / f'{len(summary["steps"]) + 1:02d}-{name}.log'
        t0 = time.monotonic()
        code = runner(argv, log, cwd or root, STEP_TIMEOUT, pass_fds)
        entry = {'name': name, 'status': 'PASS' if code == 0 else 'FAIL', 'seconds': round(time.monotonic() - t0, 1),
                 'log': str(log.relative_to(run_dir))}
        summary['steps'].append(entry)
        if code == 0 and input_hashes(root) != summary['input_sha256']:
            entry['status'] = 'FAIL'
            summary['failure'] = {'step': name, 'tail': ['inputs changed while the pipeline was running; rerun']}
        elif code != 0:
            summary['failure'] = {'step': name, 'exit_code': code, 'tail': failure_tail(log)}
        if entry['status'] == 'FAIL':
            summary['result'] = 'FAIL'
            return False
        if parse:
            parse(log)
        return True

    def parse_spec(log):
        text = Path(log).read_text()
        derived.update(json.loads(text[text.index('{'):]))

    def chain():
        py = sys.executable
        if not step('spec', [py, root / 'src/wayfarer/spec.py'], parse_spec):
            return
        if test_names is None:
            if not step('tests', [py, '-m', 'unittest', 'discover', '-s', root / 'tests', '-q']):
                return
        elif test_names and not step('tests', [py, '-m', 'unittest', '-q', *test_names], cwd=root / 'tests'):
            return
        build_args = ['--root', root] + (['--target', target] if target != 'all' else [])
        if not step('build', blender(root / 'src/wayfarer/build/build.py', *build_args)):
            return
        if inspect != 'none':
            scope = [] if inspect == 'all' else ['--scope', *(inspect or ['core'])]
            if not step('inspect', blender(root / 'src/wayfarer/validation/inspect.py', '--root', root,
                                           '--output', validation_path, *scope)):
                return
        if not step('fingerprint', blender(root / 'tests/geometry_fingerprint.py', '--root', root,
                                           '--output', fingerprint_path)):
            return
        summary['geometry_diff'] = geometry_diff(root, current_baseline(root), fingerprint_path, expect)
        if summary['geometry_diff']['unexpected_count']:
            # Previews still render so the change can be looked at; the run cannot pass until --expect explains it.
            summary['result'] = 'FAIL'
            summary['failure'] = {'step': 'geometry_diff', 'tail': ['geometry changed outside the --expect prefixes; explain it with '
                                                                    '--expect <prefixes> or revert it', *summary['geometry_diff']['unexpected'][:10]]}
        if quick and inspect != 'none':
            summary['scene'] = scene_report(json.loads(validation_path.read_text()), derived, root)
            summary['scene']['scope'] = json.loads(validation_path.read_text()).get('scope')
        if not quick:
            summary['scene'] = scene_report(json.loads(validation_path.read_text()), derived, root)
            if production:
                target_report = root / 'references/p1_validation.json'
                if target_report.exists():
                    shutil.copyfile(target_report, run_dir / 'p1_validation.before.json')
                shutil.copyfile(validation_path, target_report)
                summary['installed'] = 'references/p1_validation.json (previous copy in run dir)'
        states = previews
        if previews == 'auto':
            diff = summary.get('geometry_diff', {})
            states = ['COAST'] if quick else list(PREVIEW_STATES) if any(diff.get(k) for k in ('changed', 'added', 'removed')) else []
        summary['previews'] = []
        for state in states or []:
            out = run_dir / 'previews' / state.lower()
            if not step(f'preview-{state.lower()}', blender(
                    root / 'src/wayfarer/presentation/preview.py', '--root', root, '--state', state,
                    '--size', size, '--quality', quality, '--views', *views, '--out-dir', out)):
                return
            summary['previews'] += [str(p.relative_to(run_dir)) for p in sorted(out.glob('*.png'))]

    pass_fds = ()
    if lock:
        sys.path.insert(0, str(PROJECT / 'tools'))
        from workflow import write_lock
        with write_lock(root) as handle:
            if handle is None:
                summary.update(result='BUSY', failure={'step': 'lock', 'tail': ['another session is building; retry when it finishes']})
            else:
                pass_fds = (handle.fileno(),)
                chain()
    else:
        chain()
    summary['finished_utc'] = utc_now()
    summary['seconds'] = round(time.monotonic() - started, 1)
    (run_dir / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


def verification_scope(quick, test_names, inspect):
    """One line naming what this run verified, so a scoped PASS is never read as a whole-ship PASS."""
    if not quick:
        return 'FULL: all unit tests, whole-ship inspection, fingerprint diff'
    tests = 'all unit tests' if test_names is None else f'{len(test_names)} selected test modules' if test_names else 'no unit tests'
    checked = {'none': 'no inspection', 'all': 'whole-ship inspection'}.get(inspect) if isinstance(inspect, str) else \
        'scoped inspection (core + ' + ', '.join(inspect) + ')'
    return f'SCOPED: {tests}, {checked}, fingerprint diff; not a whole-ship PASS'


def compact(summary):
    """Short stdout form: failure tail, diff counts, scene report and preview paths."""
    view = {k: summary[k] for k in ('result', 'run_dir', 'seconds', 'verification') if k in summary}
    view['steps'] = ' '.join(f'{s["name"]}:{s["status"]}({s["seconds"]}s)' for s in summary['steps'])
    for key in ('failure', 'selection', 'geometry_diff', 'scene'):
        if key in summary:
            view[key] = summary[key]
    if summary.get('previews'):
        view['previews'] = f'{len(summary["previews"])} PNGs under {summary["run_dir"]}/previews'
    return view


def accept(run_dir, name, root=PROJECT):
    """Make a PASS full production run's fingerprint the new baseline (for an intended geometry change)."""
    summary = json.loads((Path(run_dir) / 'summary.json').read_text())
    if summary.get('result') != 'PASS' or not summary.get('production') or summary.get('quick'):
        raise ValueError('a baseline needs a PASS full pipeline run on production')
    if summary['input_sha256'] != input_hashes(root):
        raise ValueError('inputs changed after the pipeline run')
    target = root / 'references' / f'baseline_{name}'
    if target.exists():
        raise FileExistsError(f'{target} already exists; pick a new name')
    target.mkdir(parents=True)
    shutil.copyfile(Path(run_dir) / 'fingerprint.json', target / 'geometry_fingerprint.json')
    pointer = json.loads((root / BASELINES).read_text())
    pointer.setdefault('history', []).append({'baseline': pointer['current'], 'replaced_utc': utc_now()})
    pointer['current'] = str(target.relative_to(root))
    (root / BASELINES).write_text(json.dumps(pointer, indent=2) + '\n')
    return {'baseline': pointer['current']}
