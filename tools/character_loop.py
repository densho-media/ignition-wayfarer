"""`python3 tools/workflow.py characters`: the character loop (docs/CHARACTERS.md).

deps check -> build (build/human.py, MPFB in the isolated tree) -> rig review (validation/human_rig.py) -> glTF export
(export/human_gltf.py, into the run folder) -> Godot check (godot/scripts/check_characters.gd) -> in-ship fit (validation/human_fit.py,
under the write lock because it reads the vehicle asset). Prints one compact JSON summary; logs and exports stay in runs/<stamp>-characters.

`stages` runs a subset of build, rig, export (with its Godot check, which reads this run's export) and fit. A skipped stage is reused only
when its inputs are unchanged since it last ran through this loop (checks.stage_inputs); otherwise the run is refused.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time

import checks
import external
import pipeline

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = {'build': ['src/wayfarer/build/human.py'], 'rig': ['src/wayfarer/validation/human_rig.py'], 'export': ['src/wayfarer/export/human_gltf.py'],
           'fit': ['src/wayfarer/validation/human_fit.py']}
STAGES = list(SCRIPTS)


def run(root, only=None, fit=True, stages=None):
    status = external.status(include_optional=False)
    if not status['ready']:
        return dict(result='FAIL', step='deps', reason='run `python3 tools/workflow.py deps install`', deps=status['dependencies'])
    unknown = sorted(set(stages or ()) - set(STAGES))
    if unknown:
        return dict(result='FAIL', reason=f'unknown stages {unknown}; choose from {STAGES}')
    # A subset of the characters is a partial build: never recorded as the stage state, never reused.
    record = not only
    if stages and only:
        return dict(result='FAIL', reason='--stages reuses whole-set stage results; it cannot be combined with --only <characters>')
    g = checks.graph(root)
    skipped = [n for n in STAGES if stages and n not in stages]
    stale = checks.stale_stages(root, 'characters', SCRIPTS, [n for n in skipped if n != 'fit' or fit], g)
    if stale:
        return dict(result='FAIL', reason=f'skipped stages {stale} are stale (inputs changed since they last ran, or never ran through this '
                                          'loop); include them in --stages or run the whole loop')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'); rd = root/'runs'/f'{stamp}-characters'; (rd/'glb').mkdir(parents=True)
    sel = ['--only', *only] if only else []; godot = os.environ.get('WAYFARER_GODOT', '/snap/bin/godot-4'); env = external.blender_env()
    steps = [('build', pipeline.blender(root/'src/wayfarer/build/human.py', *sel, '--report', root/'references/p1_human_system.json')),
             ('rig', pipeline.blender(root/'src/wayfarer/validation/human_rig.py', *sel)),
             ('export', pipeline.blender(root/'src/wayfarer/export/human_gltf.py', *sel, '--out', rd/'glb')),
             ('godot', [godot, '--headless', '--path', str(root/'godot'), '--script', 'res://scripts/check_characters.gd', '--', f'--dir={rd/"glb"}'])]
    out = dict(run_dir=str(rd.relative_to(root)), seconds={})
    for name, argv in steps:
        if (name if name != 'godot' else 'export') in skipped:
            continue
        log = rd/f'{name}.log'; t0 = time.monotonic()
        with open(log, 'w') as f:
            code = subprocess.run(argv, cwd=root, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=pipeline.STEP_TIMEOUT).returncode
        out['seconds'][name] = round(time.monotonic() - t0, 1)
        if code:
            return dict(out, result='FAIL', step=name, log=str(log.relative_to(root)), tail=pipeline.failure_tail(log))
    built = json.loads((root/'references/p1_human_system.json').read_text())['characters']
    rig = json.loads((root/'references/p1_human_rig.json').read_text())['characters']
    g_out = next((json.loads(l.split(' ', 1)[1]) for l in (rd/'godot.log').read_text().splitlines() if l.startswith('WF_GODOT_CHARACTERS')), None) \
        if (rd/'godot.log').exists() else None
    out['characters'] = {k: dict(stature_m=v['stature_m'], bones=v['contract']['bones'], max_influences=v['contract']['max_influences'],
                                 slip_mm=max([x for a in v['actions'].values() for x in a['slip_mm'].values()] or [0]),
                                 reopened_identical=rig.get(k, {}).get('fingerprint_matches_build'),
                                 flagged_postures=[p for p, m in rig.get(k, {}).get('postures', {}).items() if m['flag']],
                                 godot=None if g_out is None else ('PASS' if not g_out['characters'].get(k, {}).get('fail') else g_out['characters'][k]['fail']))
                         for k, v in built.items() if not only or k in only}
    if fit and 'fit' not in skipped:
        from workflow import write_lock
        with write_lock(root) as lock:
            if lock is None:
                out['fit'] = 'BUSY (another session holds the write lock); rerun later'
            else:
                log = rd/'fit.log'; t0 = time.monotonic()
                with open(log, 'w') as f:
                    code = subprocess.run(pipeline.blender(root/'src/wayfarer/validation/human_fit.py'), cwd=root, env=env, stdout=f,
                                          stderr=subprocess.STDOUT, timeout=pipeline.STEP_TIMEOUT).returncode
                out['seconds']['fit'] = round(time.monotonic() - t0, 1)
                if code:
                    return dict(out, result='FAIL', step='fit', log=str(log.relative_to(root)), tail=pipeline.failure_tail(log))
                fitr = json.loads((root/'references/p1_human_fit.json').read_text())['characters']
                out['fit'] = {w: {k: r['verdict']+(f" (standoff {r['standoff_to_clear_m']} m)" if r.get('standoff_to_clear_m') is not None else '')
                                  for k, r in st.items()} for w, st in fitr.items()}
    ran = [n for n in STAGES if n not in skipped and (n != 'fit' or (fit and isinstance(out.get('fit'), dict)))]
    if record:
        recorded = checks.stage_state(root, 'characters')
        recorded.update({n: checks.stage_inputs(root, SCRIPTS[n], g) for n in ran})
        checks.save_stage_state(root, 'characters', recorded)
    stale_after = checks.stale_stages(root, 'characters', SCRIPTS, [n for n in skipped if n != 'fit' or fit], g)
    if skipped:
        out['skipped'] = skipped
    if stale_after:
        out.update(result='STALE', stale=stale_after, reason='a rerun stage changed the inputs of these skipped stages; rerun them')
    else:
        out['result'] = 'PASS' if g_out is None or g_out['result'] == 'PASS' else 'FAIL'
    return out
