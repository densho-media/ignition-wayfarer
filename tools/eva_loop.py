"""`python3 tools/workflow.py eva`: the EVA suit loop (docs/EVA.md, TODO EVA-001).

build (build/eva_suit.py on the saved induction characters) -> checks (validation/eva_fit.py: pressure continuity in every action,
envelope against the route bottlenecks, SP-11 pair fit, the access-pose hulls, suited bodies at the training route's holds in the vehicle,
under the write lock because it reads the vehicle asset) -> EVA-002 access study (eva_access.py: envelope classes, SP-11 door and chamber
candidates, SP-12/13 rooms) -> its check in the vehicle (validation/eva_airlock_study.py, with section renders unless --no-renders) ->
EVA-003 comparison (eva_sp11.py: 1.10/1.20/1.35 m, inner-hatch mechanisms, the extension latch on the rigs, rescue cases) -> its check in
the vehicle with the posed rigs (validation/eva_sp11_study.py) ->
renders (presentation/eva_preview.py, unless --no-renders) -> glTF export into the run folder -> route summary (eva_route.py). Prints one compact JSON summary; logs stay in runs/<stamp>-eva. The Godot scene check runs in
`runtime-export`, which publishes the suits and the route with the ship.

`only` runs a subset of the stages. A skipped stage is reused only when its inputs (script import closure, data, saved assets and the
EVA/character reference JSON) are unchanged since it last ran (checks.stage_inputs); otherwise the run is refused. Stages skipped while a
rerun stage changed their inputs are reported as STALE afterwards.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

import checks
import pipeline

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = {'build': ['src/wayfarer/build/eva_suit.py'], 'fit': ['src/wayfarer/validation/eva_fit.py'], 'access': ['src/wayfarer/eva_access.py'],
           'airlock': ['src/wayfarer/validation/eva_airlock_study.py'], 'sp11': ['src/wayfarer/eva_sp11.py'],
           'sp11_vehicle': ['src/wayfarer/validation/eva_sp11_study.py'], 'renders': ['src/wayfarer/presentation/eva_preview.py'],
           'export': ['src/wayfarer/export/eva_gltf.py'], 'route': ['src/wayfarer/eva_route.py']}
STAGES = list(SCRIPTS)


def run(root, renders=True, route=True, only=None):
    if not all((root/'assets/characters'/f'WF_CHAR_HUMAN_{k}.blend').exists() for k in ('INSTRUCTOR', 'NEWCOMER')):
        return dict(result='FAIL', step='characters', reason='run `python3 tools/workflow.py characters` first')
    unknown = sorted(set(only or ()) - set(STAGES))
    if unknown:
        return dict(result='FAIL', reason=f'unknown stages {unknown}; choose from {STAGES}')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'); rd = root/'runs'/f'{stamp}-eva'; (rd/'glb').mkdir(parents=True)
    from workflow import write_lock
    steps = [('build', pipeline.blender(root/'src/wayfarer/build/eva_suit.py', '--report', root/'references/p1_eva_suit.json')),
             ('fit', pipeline.blender(root/'src/wayfarer/validation/eva_fit.py', *([] if route else ['--no-route']))),
             ('access', ['python3', str(root/'src/wayfarer/eva_access.py')]),
             ('airlock', pipeline.blender(root/'src/wayfarer/validation/eva_airlock_study.py', '--out', rd, *([] if renders else ['--no-renders']))),
             ('sp11', ['python3', str(root/'src/wayfarer/eva_sp11.py')]),
             ('sp11_vehicle', pipeline.blender(root/'src/wayfarer/validation/eva_sp11_study.py', '--out', rd, *([] if renders else ['--no-renders']))),
             *([('renders', pipeline.blender(root/'src/wayfarer/presentation/eva_preview.py'))] if renders else []),
             ('export', pipeline.blender(root/'src/wayfarer/export/eva_gltf.py', '--out', rd/'glb')),
             ('route', ['python3', str(root/'src/wayfarer/eva_route.py'), '--out', str(rd)])]
    out = dict(run_dir=str(rd.relative_to(root)), seconds={})
    with write_lock(root) as lock:
        if lock is None:
            return dict(out, result='BUSY')
        g = checks.graph(root)
        skipped = [n for n, _ in steps if only and n not in only]
        stale = checks.stale_stages(root, 'eva', SCRIPTS, skipped, g)
        if stale:
            return dict(out, result='FAIL', reason=f'skipped stages {stale} are stale (inputs changed since they last ran, or never ran '
                                                   'through this loop); include them in --only or run the whole loop')
        for name, argv in steps:
            if name in skipped:
                continue
            log = rd/f'{name}.log'; t0 = time.monotonic()
            with open(log, 'w') as f:
                code = subprocess.run([str(a) for a in argv], cwd=root, stdout=f, stderr=subprocess.STDOUT, timeout=pipeline.STEP_TIMEOUT).returncode
            out['seconds'][name] = round(time.monotonic() - t0, 1)
            if code:
                return dict(out, result='FAIL', step=name, log=str(log.relative_to(root)), tail=pipeline.failure_tail(log))
        recorded = checks.stage_state(root, 'eva')
        recorded.update({n: checks.stage_inputs(root, SCRIPTS[n], g) for n, _ in steps if n not in skipped})
        checks.save_stage_state(root, 'eva', recorded)
        stale_after = checks.stale_stages(root, 'eva', SCRIPTS, skipped, g)
    if skipped:
        out['skipped'] = skipped
    route_ = json.loads((rd/'wf_eva.json').read_text()) if (rd/'wf_eva.json').exists() else None
    fit = json.loads((root/'references/p1_eva_fit.json').read_text())
    out['coverage'] = {k: {a: c['status'] for a, c in v['coverage'].items() if c['status'] != 'PASS'} or 'PASS' for k, v in fit['variants'].items()}
    out['envelope'] = {k: dict(circle_m=v['envelope']['torso_circle_diameter_m'], height_m=v['envelope']['height_m'],
                               blocked=[b['bottleneck'] for b in v['bottlenecks'] if b['status'] == 'BLOCKED']) for k, v in fit['variants'].items()}
    out['holds'] = {r['case']: r['status'] for r in fit.get('route', [])}
    if route_:
        out['route_status'] = route_['status']; out['flight'] = route_['flight']['state']
    acc = json.loads((root/'references/p1_eva_access.json').read_text()); air = json.loads((root/'references/p1_eva_airlock.json').read_text())
    out['sp11'] = {r['id']: r['status'] for r in acc['sp11']}; out['sp11_recommendation'] = acc['recommendation']['id']
    out['sp11_structure'] = {k: sorted({p['status'] for p in v.values() if isinstance(p, dict)}) for k, v in air['candidates'].items()}
    out['rooms'] = {k: v['status'] for k, v in air['rooms'].items()}
    e3 = json.loads((root/'references/p1_eva_sp11.json').read_text()); v3 = json.loads((root/'references/p1_eva_sp11_vehicle.json').read_text())
    out['eva3'] = {r['id']: dict(routine_door=r['routine_door_ok'], mechanisms=[k for k, m in r['mechanisms'].items() if m['status'] == 'PASS'],
                                 structure=sorted({p['status'] for p in v3['rows'][r['id']]['structure'].values()}),
                                 rescue=[k for k, x in r['rescue'].items() if x['status'] == 'PASS']) for r in e3['rows']}
    if stale_after:
        out.update(result='STALE', stale=stale_after, reason='a rerun stage changed the inputs of these skipped stages; rerun them')
    else:
        out['result'] = 'PASS'
        out['verification'] = 'FULL EVA loop' if not skipped else f'PARTIAL: reran {[n for n, _ in steps if n not in skipped]}; reused current {skipped}'
    return out
