"""Standalone accessory review viewer (docs/ACCESSORIES.md): stage, check, screenshot and open accessories/viewer/.

  python3 tools/accessory_viewer.py stage [--from <run dir>]   build (or reuse) the GLBs and fill accessories/viewer/generated/
  python3 tools/accessory_viewer.py check                     Godot headless: load every entry, play every action (PASS / ERROR)
  python3 tools/accessory_viewer.py shots --out <dir>         one screenshot per entry (needs a display; uses xvfb-run when present)
  python3 tools/accessory_viewer.py open                      the interactive viewer (stages first when generated/ is empty)

`stage` without --from runs the Blender drone builder (build/drone_bodies.py) and the accessory scenes (presentation/accessory_scene.py
--glb; the suits must be built) into runs/<stamp>-accessory-viewer and copies the GLBs. The manifest names each design's class facts,
its actions (SIMULATION_ONLY) and the gates it stays under; none of it is a ship input. The ship viewer in godot/, the runtime export
and the module registry are never touched.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src/wayfarer'))
import drone_bodies as db       # noqa: E402
import drone_fleet as df        # noqa: E402

PROJECT = ROOT/'accessories/viewer'
GEN = PROJECT/'generated'
GODOT = os.environ.get('WAYFARER_GODOT', '/snap/bin/godot-4')
BLENDER = os.environ.get('WAYFARER_BLENDER', '/snap/bin/blender')
DRONE_GATES = ('PROTOTYPE · L4_VISUAL_CANDIDATE · NOT INTEGRATED: the ship keeps its L2 proxies (54 DGT-017 HOLD) · GU-SIF is a proposed '
               'common interface, not an approved standard (DGT-012 HOLD) · mass, power, speed, reach, payload, latch and endurance OPEN')
SCENES = [dict(id='SCENE-EVA-HANDOFF', title='EVA tool handoff (training simulation)', glb='accessory_eva_handoff.glb',
               facts=['WAYFARER_EVA_Y155 instructor (MPFB rig) in a portable foot restraint, tether A clipped',
                      'DR-EVA-03 presents its tool cartridge; the glove is closed on the crew handle (contact-aware display grasp)',
                      'casing patch, rails, restraint and anchor are review fixtures, not ship geometry'],
               gates='TRAINING SIMULATION · FLIGHT_EVA HOLD · PROTOTYPE, NOT CERTIFIED · suit life support, glove torque, grip and latch '
                     'ratings OPEN · DOP-04 supervised handoff'),
          dict(id='SCENE-IVA-TASKS', title='Interior drones at work', glb='accessory_iva_tasks.glb',
               facts=['DR-IVA-02 picks a cargo cartridge on a deck guide (the guide channel is an interface request, not in the ship)',
                      'DR-IVA-01 perched on a handrail, fans off', 'DR-IVA-03 probing a sensor port in a raceway (conduits DS-09 HOLD)'],
               gates='PROTOTYPE · L4 visual candidates · NOT INTEGRATED (DGT-017 HOLD)')]


def run(cmd, **kw):
    print('$', ' '.join(str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], **kw)


def blender(script, *args, log):
    with open(log, 'w') as f:
        r = run([BLENDER, '--background', '--factory-startup', '--python-exit-code', '1', '--python', ROOT/script, '--', *args], stdout=f, stderr=subprocess.STDOUT)
    if r.returncode:
        raise SystemExit(f'{script} failed: see {log}')


def manifest(s, d):
    B = db.bodies(s, d); C = df.classes(s); rows, _ = db.check(s, d); out = []
    for cid, b in B.items():
        c = C[cid]; r = rows[cid]
        facts = [f"{c['name']} · {c['domain']} · {c['active']} active + {c['reserve']} reserve (S&E 51) · mobility: {c['mobility']}",
                 f"mount: {b.mount} · precedent: {c['precedent']}",
                 (f"stowed {' x '.join(f'{v:.2f}' for v in r['stowed_m'])} m, inside the owner envelope class {r['envelope_class_m']} m"
                  if c['domain'] != 'FIXED' else f"base {' x '.join(f'{v:.2f}' for v in r['base_m'])} m (owner base); boom shown for display only, reach OPEN"),
                 f"L2 proxy: {r['proxy_fit']}" if r.get('proxy_fit') else 'fixed arm: no L2 proxy comparison',
                 'kit: ' + ', '.join(f'{k} {v}' for k, v in sorted(r.get('kit', {}).items()))]
        facts += [n for n in b.notes]
        out.append(dict(id=cid, title=b.title, glb=f"WF_DRONE_{cid.replace('-', '_')}.glb", main=list(db.MAIN[cid]), facts=facts,
                        actions=[dict(name=n, job=a['job'], status=a['status']) for n, a in b.actions.items()], gates=DRONE_GATES))
    return out


def stage(args):
    s, d = db.load(ROOT)
    if args.source:
        src = args.source.resolve()
    else:
        src = ROOT/'runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-accessory-viewer'); src.mkdir(parents=True)
        blender('src/wayfarer/build/drone_bodies.py', '--out', src, log=src/'drones.log')
        if (ROOT/'assets/characters/WF_EVA_INSTRUCTOR.blend').exists():
            blender('src/wayfarer/presentation/accessory_scene.py', '--out', src/'scenes', '--glb', '--size', 640, 400, log=src/'scenes.log')
        else:
            print('note: no suit assets (tools/workflow.py characters, then eva): the scenes are left out')
    if GEN.exists():
        shutil.rmtree(GEN)
    GEN.mkdir(parents=True); (GEN/'.gdignore').write_text('')
    entries = manifest(s, d)
    for e in entries:
        shutil.copy2(src/'glb'/e['glb'], GEN/e['glb'])
    for sc in SCENES:
        p = next((q for q in (src/'scenes'/sc['glb'], src/sc['glb']) if q.exists()), None)
        if p:
            shutil.copy2(p, GEN/sc['glb']); entries.append(sc)
    fam = d['family']
    (GEN/'accessories.json').write_text(json.dumps(dict(family=fam, source=str(src.relative_to(ROOT)) if src.is_relative_to(ROOT) else str(src),
                                                        entries=entries), indent=1)+'\n')
    print(f'staged {len(entries)} entries from {src} into {GEN.relative_to(ROOT)}')


def godot(args_, headless=True, display=False):
    cmd = [GODOT, *(['--headless'] if headless else ['--audio-driver', 'Dummy']), '--path', PROJECT, *args_]
    if display and not os.environ.get('DISPLAY') and shutil.which('xvfb-run'):
        cmd = ['xvfb-run', '-a', '-s', '-screen 0 1440x900x24', *cmd]
    return run(cmd, capture_output=True, text=True, timeout=600)


def check(_):
    if not (GEN/'accessories.json').exists():
        raise SystemExit('generated/ is empty: run `python3 tools/accessory_viewer.py stage` first')
    godot(['--import'])                                    # first run: create the project cache (no assets are imported: generated/ is .gdignored)
    r = godot(['--', '--check']); text = r.stdout+r.stderr
    print('\n'.join(line for line in text.splitlines() if 'WF_ACC_VIEWER' in line or 'ERROR' in line))
    ok = r.returncode == 0 and 'WF_ACC_VIEWER CHECK PASS' in text and 'ERROR:' not in text
    print('PASS' if ok else 'FAIL'); return 0 if ok else 1


def shots(args):
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    r = godot(['--', '--shots', out], headless=False, display=True)
    print('\n'.join(line for line in (r.stdout+r.stderr).splitlines() if 'WF_ACC_VIEWER' in line or 'ERROR' in line))
    return r.returncode


def open_(args):
    if not (GEN/'accessories.json').exists():
        stage(args)
    return run([GODOT, '--path', PROJECT]).returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('stage', 'open'):
        p = sub.add_parser(name); p.add_argument('--from', dest='source', type=Path, help='reuse a run directory holding glb/ (and scenes/)')
    sub.add_parser('check')
    p = sub.add_parser('shots'); p.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    return dict(stage=stage, check=check, shots=shots, open=open_)[a.cmd](a) or 0


if __name__ == '__main__':
    sys.exit(main())
