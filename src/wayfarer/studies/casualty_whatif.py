"""HUM-002-2026-10-10 what-ifs (S&E 15!A121, 09 OD-032, 98!A87): how much the blocking passages would have to grow for a full-length
supported carrier, swept like the built model. NONCANON: each variant is a disposable workspace (runs/<stamp>-hum002/<variant>/work, a copy
of data/ with one change) built by build.py --root and swept by casualty_sweep.py --root; the production spec and assets are never touched
(15!H121: no geometry change, no new pressure penetration). The owner decides from the measured costs.

Variants (each one passage, every other dimension as built):
- ring B port: [human_entry.study] port_clear_radius_m for rotor 2 (its spine port, drum openings and tube necks share it); the vestibule
  then grows forward past its window, into hub 1's forward withdrawal paths (reported, P1-008);
- refuge port: human_entry.refuge_port_clear_m; reported with the share of the spine core it cuts;
- ring A annulus: [human_entry.study] chamber_depth_extra_m for rotor 1 (the drum annulus gets deeper, the outer wall moves out);
- ring B annulus: the same for rotor 2 (its sectors 1 and 3 turn round the annulus).

    python3 src/wayfarer/studies/casualty_whatif.py [--only <variant,...>]
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import math
import re
import shutil
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'tools')]
BLENDER = '/snap/bin/blender'

RING_A = 'A2,A3,A2-M'
RING_B = 'B1,B2,B3,B2-M'
REFUGE = 'R,E'
VARIANTS = {     # name: (toml edit, routes, dwell)
    'built': ({}, f'{RING_A},{RING_B},{REFUGE}', True),
    'ringB_port_1.10': ({'port_clear_radius_m': {'2': 0.55}}, RING_B, True),
    'ringB_port_1.30': ({'port_clear_radius_m': {'2': 0.65}}, RING_B, True),
    'ringB_port_1.60': ({'port_clear_radius_m': {'2': 0.80}}, RING_B, True),
    'refuge_port_1.10': ({'refuge_port_clear_m': 1.10}, REFUGE, False),
    'refuge_port_1.30': ({'refuge_port_clear_m': 1.30}, REFUGE, False),
    'refuge_port_1.60': ({'refuge_port_clear_m': 1.60}, REFUGE, False),
    'ringA_depth_+0.20': ({'chamber_depth_extra_m': {'1': 0.20}}, RING_A, True),
    'ringA_depth_+0.40': ({'chamber_depth_extra_m': {'1': 0.40}}, RING_A, True),
    # Ring B sectors 1 and 3 are decided by the turn round the drum annulus, not by the port (ringB_port_*): a deeper annulus.
    'ringB_depth_+0.40': ({'chamber_depth_extra_m': {'2': 0.40}}, 'B1,B3', True),
    'ringB_depth_+0.80': ({'chamber_depth_extra_m': {'2': 0.80}}, 'B1,B3', True),
}
CARRIERS = 'ACK'


def edit(text, change):
    """The spec text with one study change: refuge_port_clear_m replaced in place, the rest as a [human_entry.study] table."""
    study = {k: v for k, v in change.items() if k != 'refuge_port_clear_m'} or {'note': '"refuge port only"'}
    if 'refuge_port_clear_m' in change:
        text, n = re.subn(r'^refuge_port_clear_m = .*$', f"refuge_port_clear_m = {change['refuge_port_clear_m']:.2f}", text, flags=re.M)
        assert n == 1
    if study:
        text += '\n# HUM-002 study workspace only (studies/casualty_whatif.py)\n[human_entry.study]\n'
        for k, v in study.items():
            text += (f'{k} = {{ ' + ', '.join(f'"{a}" = {b}' for a, b in v.items()) + ' }\n') if isinstance(v, dict) else f'{k} = {v}\n'
    return text


def costs(work):
    """What each change costs in the built geometry, from the pure modules: ring B's vestibule against its window (hub 1's forward withdrawal
    paths plus the mechanical clearance), the refuge port's cut in the spine core, ring A's annulus outer radius."""
    import importlib
    import spec
    for m in ('crew_transfer', 'hull_geometry', 'human_entry'):
        if m in sys.modules:
            importlib.reload(sys.modules[m])
    import crew_transfer
    s = spec.load(work)[0]; out = {}
    for j in s['human_entry']['vestibule_rotors']:
        v = crew_transfer.vestibule(s, j); tag = 'AB'[j-1]
        out[f'ring_{tag}'] = dict(port_clear_m=round(2*v['port_clear'], 3), annulus_depth_m=round(v['clear']-v['r0'], 3), outer_wall_r_m=round(v['r1'], 3),
                                  clear_length_m=round(v['cu1']-v['cu0'], 3), vestibule_u_m=[round(v['u0'], 3), round(v['u1'], 3)])
        if v['window']:
            out[f'ring_{tag}']['window_u0_m'] = round(v['window'][0], 3)
            out[f'ring_{tag}']['intrusion_into_window_m'] = round(max(0.0, v['window'][0]-v['u0']), 3)
    rc = s['prototype']['spine_core_radius_m']; d = s['human_entry']['refuge_port_clear_m']; wall = s['crew_transfer']['passage_wall_m']
    import human_entry
    out['trunk_ladder_top_x_m'] = round(human_entry.trunk_ladder(s)['top'], 3)    # the ladder stops below the first branch across a stile line
    out['refuge_port'] = dict(clear_m=d, spine_core_arc_deg=round(math.degrees(2*math.asin(min(1.0, (d/2+wall)/rc))), 1), core_radius_m=rc)
    return out


def main():
    a = argparse.ArgumentParser(); a.add_argument('--only', default=''); a.add_argument('--out', type=Path); a.add_argument('--force', action='store_true')
    args = a.parse_args()
    out = args.out or ROOT/'runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-hum002')
    out.mkdir(parents=True, exist_ok=True)
    summary = json.loads((out/'summary.json').read_text()) if (out/'summary.json').exists() else {}
    for name, (change, routes, dwell) in VARIANTS.items():
        if args.only and name not in args.only.split(','):
            continue
        vd = out/name
        for f in vd.glob('* [[]conflicted[]].*'):
            f.rename(vd/f.name.replace(' [conflicted]', ''))
        if (vd/'casualty_sweep.json').exists() and not args.force:       # reuse a finished sweep (re-summarize only)
            work = ROOT if name == 'built' else vd/'work'
            r = json.loads((vd/'casualty_sweep.json').read_text())
            summary[name] = dict(change=change, costs=costs(work),
                                 routes={cid: {k: dict(passes=v['bend_0']['passes'], least_m=v['bend_0']['least_margin_m'], at=v['bend_0']['zone_name'],
                                                       nearest=v['bend_0']['nearest'], with_bearers_m=v['with_bearers_least_m'])
                                               for k, v in res.items()} for cid, res in r['routes'].items()},
                                 drum_dwell=r['drum_dwell'])
            (out/'summary.json').write_text(json.dumps(summary, indent=1)+'\n'); print(name, 'reused', flush=True); continue
        if name == 'built':
            work = ROOT
        else:
            work = vd/'work'
            if work.exists():
                shutil.rmtree(work)
            shutil.copytree(ROOT/'data', work/'data')
            p = work/'data/wayfarer_3d.toml'; p.write_text(edit(p.read_text(), change))
            vd.mkdir(parents=True, exist_ok=True)
            with open(vd/'build.log', 'w') as log:
                code = subprocess.call([BLENDER, '-b', '--factory-startup', '--python', str(ROOT/'src/wayfarer/build/build.py'), '--', '--root', str(work)],
                                       stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
            if code:
                summary[name] = dict(change=change, result='BUILD FAILED', log=str(vd/'build.log')); print(name, 'BUILD FAILED', flush=True); continue
        cmd = [BLENDER, '-b', '--factory-startup', '--python', str(ROOT/'src/wayfarer/studies/casualty_sweep.py'), '--', '--out', str(vd), '--root', str(work),
               '--carriers', CARRIERS, '--routes', routes] + ([] if dwell else ['--no-dwell'])
        vd.mkdir(parents=True, exist_ok=True)
        with open(vd/'sweep.log', 'w') as log:
            code = subprocess.call(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
        for f in vd.glob('* [[]conflicted[]].*'):          # a cloud-sync mirror renames files written into a recreated folder
            f.rename(vd/f.name.replace(' [conflicted]', ''))
        if code or not (vd/'casualty_sweep.json').exists():
            summary[name] = dict(change=change, result='SWEEP FAILED', log=str(vd/'sweep.log')); print(name, 'SWEEP FAILED', flush=True); continue
        r = json.loads((vd/'casualty_sweep.json').read_text())
        summary[name] = dict(change=change, costs=costs(work),
                             routes={cid: {k: dict(passes=v['bend_0']['passes'], least_m=v['bend_0']['least_margin_m'], at=v['bend_0']['zone_name'],
                                                   nearest=v['bend_0']['nearest'], with_bearers_m=v['with_bearers_least_m'])
                                           for k, v in res.items()} for cid, res in r['routes'].items()},
                             drum_dwell=r['drum_dwell'])
        print(name, json.dumps({c: {k: v['least_m'] for k, v in q.items()} for c, q in summary[name]['routes'].items()}), flush=True)
        (out/'summary.json').write_text(json.dumps(summary, indent=1)+'\n')
    print('WF_HUM002_WHATIF', out, flush=True)


if __name__ == '__main__':
    main()
