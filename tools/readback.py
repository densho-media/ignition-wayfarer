"""`workflow.py readback`: measure the saved vehicle for the owner (READBACK-001) and summarize it against the owner's study figures.

Runs src/wayfarer/validation/readback.py in Blender under the write lock into runs/<stamp>-readback/ and writes readback.md there. With
--install the CSVs and the summary are copied to references/p1_readback.* (the reviewed copy). Measurements are correspondence
evidence for the owner, never canon."""
from datetime import datetime, timezone
from pathlib import Path
import csv
import json
import shutil
import sys

import pipeline
import workflow

SCRIPT = Path('src/wayfarer/validation/readback.py')
# Owner study figures the summary compares against (S&E capture 2026-10-09); quoted, never adopted.
RING_NET_M3, RING_GROSS_M3 = 240.0, (400.0, 460.0)          # 33!A6, 33!A9:A10
CORRIDOR_ASSUMED_M, PROPELLANT_ZONE_M = 120.0, 60.0          # 27!A12, 34!A9
STATIONARY_STUDY = [                                          # 33!A27:A32 (roomy, compact) net m3, plus SP-45 (33!A71)
    ('Storm refuge', ('Refuge_Storm_Shelter',), (55, 55)),
    ('Workshop / fabrication', (), (55, 40)),
    ('Science / lattice lab', (), (40, 25)),
    ('Boarding, service and EVA airlocks', ('Dock_Primary', 'Dock_Primary_Entry_Chamber', 'Dock_Primary_Trunk_Node',
                                            'Dock_Primary_Inboard_Neck', 'Crew_Connector_Dock_Primary'), (40, 28)),
    ('Stationary trunk + two ring transfer hubs', ('Crew_Trunk', 'Crew_Port_1_1', 'Crew_Port_2_2', 'Crew_Refuge_Port',
                                                   'Crew_Vestibule_1', 'Crew_Vestibule_2'), (45, 35)),
    ('Stationary ECLSS for refuge', (), (15, 12)),
    ('Walk-in storeroom SP-45', ('Storeroom_Shell', 'Crew_Store_Port'), (42, 30)),
]


def utc_stamp():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def rows(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def num(text):
    try:
        return float(text)
    except ValueError:
        return None


def summary(run_dir):
    data = json.loads((run_dir / 'readback.json').read_text())
    table = {r['ID']: r for r in rows(run_dir / 'readback.csv')}
    room = lambda name: table.get(f'ROOM.{name}')
    out = ['# Wayfarer measurement readback', '',
           f"Saved vehicle at {data['pose']}; spec {data['spec_hash'][:12]}, source map {data['source_map_hash'][:12]}. "
           f"{data['objects']} evaluated meshes in {data['groups']} groups; {data['rooms_measured']} pressurized rooms. "
           'Measurements of a PROTOTYPE proxy model for the owner (S&E 34!A94:A110, 31!A39/A53/A104, 33!A66:A68, 27!A12): '
           'bounds, closed-mesh solid volumes, envelopes of revolution and pressurized volumes from the generator dimensions. '
           'Mass, power and heat are not computed (dry_kg = unknown; Sheets owns them). Not canon.', '',
           '## Rings (33!A5:A24, A59:A68)', '',
           '| Ring | Sectors | Gross m³ | Net m³ (deck to overhead less fit-out) | Crew tubes m³ | Transfer drum m³ |', '|---|---|---|---|---|---|']
    tot_g = tot_n = 0.0
    for j in (1, 2):
        sectors = [room(f'Sector_{j}_{k}') for k in (1, 2, 3)]
        g = sum(num(r['pressure_gross_m3']) for r in sectors); n = sum(num(r['pressure_net_m3']) for r in sectors)
        tubes = sum(num(room(f'Crew_Tube_{j}_{k}')['pressure_gross_m3']) for k in (1, 2, 3))
        drum = num(room(f'Crew_Vestibule_{j}')['pressure_gross_m3'])
        tot_g += g; tot_n += n
        out.append(f'| {"AB"[j-1]} | 3 | {g:.1f} | {n:.1f} | {tubes:.1f} | {drum:.1f} |')
    out += ['', f'Both rings: sector gross {tot_g:.1f} m³ against the 400–460 m³ gross range, sector net {tot_n:.1f} m³ against the '
            f'{RING_NET_M3:g} m³ net. The six pressurized crew tubes ({sum(num(room(f"Crew_Tube_{j}_{k}")["pressure_gross_m3"]) for j in (1, 2) for k in (1, 2, 3)):.1f} m³) '
            'and the two despun drums are outside both figures; whether the 400–460 m³ includes them is the owner\'s scope question (33!A39).', '',
            '## Stationary pressurized rooms (33!A26:A35)', '',
            '| Study item | Roomy / compact net m³ | Built rooms | Built gross m³ | Built net m³ |', '|---|---|---|---|---|']
    for label, names, (roomy, compact) in STATIONARY_STUDY:
        built = [room(n) for n in names if room(n)]
        gross = sum(num(r['pressure_gross_m3']) for r in built)
        nets = [num(r['pressure_net_m3']) for r in built]; nets = [v for v in nets if v is not None]; net = sum(nets) if nets else None
        out.append(f"| {label} | {roomy} / {compact} | {', '.join(names) if built else 'not built'} | {f'{gross:.1f}' if built else '—'} | "
                   f"{f'{net:.1f}' if net is not None else '—'} |")
    out += ['', 'Gross is the clear cavity inside the pressure wall; junction overlaps are not deducted. Net is given for the rooms with modelled fit-out '
            '(the SP-45 room less its racks; its port has none); elsewhere it is not modelled (—). The EVA airlock and the service dock are solid '
            'proxies with no cavity yet.', '',
            '## Free axial corridor (27!A12, 31!A39/A53, 34!A9/A95)', '']
    coarse = data['free_corridor_between_equipment']
    out.append(f"Stationary hull x {coarse['hull_x'][0]:.2f} to {coarse['hull_x'][1]:.2f} m; spine radius {coarse['spine_radius_m']:.2f} m. "
               'Free means no stationary object other than the hull, spine, primary lattice, hub webs and cryogenic feed lines reaches '
               'inside the hull\'s inner radius; the annulus is between the spine and the inner hull radius. Unoccupied in the '
               'PROTOTYPE model, not proven available: water, stores, workshop and other unsized equipment are not packaged yet.')
    out += ['', '| x from | x to | Length m | Annulus m³ | Aft neighbour | Forward neighbour | Crossed by (x) |', '|---|---|---|---|---|---|---|']
    for iv in coarse['intervals']:
        if iv['length_m'] < 1.0:
            continue
        crossed = ', '.join(iv['crossed_by']) + (f" ({', '.join(f'{x:g}' for x in iv['crossing_stations_x'])})" if iv['crossed_by'] else '')
        out.append(f"| {iv['x_min']:.2f} | {iv['x_max']:.2f} | {iv['length_m']:.2f} | {iv['annulus_m3']:.0f} | {iv['aft_neighbour']} | "
                   f"{iv['fwd_neighbour']} | {crossed or '—'} |")
    longest = max(iv['length_m'] for iv in coarse['intervals'])
    out += ['', f'Longest free run {longest:.1f} m, against the {CORRIDOR_ASSUMED_M:g} m corridor assumption (27!A12) and the '
            f'{PROPELLANT_ZONE_M:g} m propellant zone (34!A9). The strict scan that also splits on the crossing members is in readback.json.', '',
            '## Radiator root against the body (34!A88:A91, A101)', '']
    rr = data['radiator_root']
    out.append(f"Hot blade inner edge r {rr['blade_inner_edge_r_m']:.3f} m; built hull outer r {rr['hull_outer_r_m']:.3f} m (gap "
               f"{rr['gap_to_built_hull_m']:.3f} m). Against nominal bodies: " +
               ', '.join(f'{k} {v:+.3f} m' for k, v in rr['gap_to_nominal_body_m'].items()) + '. Clearance numbers only.')
    out += ['', '## Files', '', '- `readback.csv`: one row per object group (library, name stem, kind) and per pressurized room, in the 34!A105 columns.',
            '- `station_map.csv`: x and radial extent of every group, sorted by x, plus the free corridor intervals.',
            '- `readback.json`: totals, both corridor scans and the radiator-root numbers.', '']
    return '\n'.join(out)


def run(root, install=False):
    with workflow.write_lock(root) as lock:
        if lock is None:
            return {'result': 'BUSY'}
        run_dir = root / 'runs' / f'{utc_stamp()}-readback'
        (run_dir / 'logs').mkdir(parents=True)
        log = run_dir / 'logs' / 'readback.log'
        code = pipeline.subprocess_runner(pipeline.blender(root / SCRIPT, '--root', root, '--out-dir', run_dir), log, root, 600)
        if code != 0:
            return {'result': 'FAIL', 'run_dir': str(run_dir), 'log_tail': pipeline.failure_tail(log)}
        (run_dir / 'readback.md').write_text(summary(run_dir))
        if install:
            for name in ('readback.csv', 'station_map.csv', 'readback.md'):
                shutil.copyfile(run_dir / name, root / 'references' / f'p1_{name}')
        data = json.loads((run_dir / 'readback.json').read_text())
        return {'result': 'PASS', 'run_dir': str(run_dir), 'objects': data['objects'], 'groups': data['groups'],
                'rooms': data['rooms_measured'], 'installed': install, 'summary': str(run_dir / 'readback.md')}


if __name__ == '__main__':
    print(json.dumps(run(workflow.ROOT, '--install' in sys.argv)))
