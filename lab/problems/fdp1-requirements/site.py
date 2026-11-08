"""What the Engineering pages of the website (tools/story.py) show of this problem map. Standard library only.

story() returns the problem register P01-P11 with its values filled from the FDP-1 record (fdp1diag.model), the model's own
checks, and the P11 side-elevation data: the shield shadow and every part's radial extent along the ship, classified covered or
outside for the aligned stream (fdp1diag.protection). Nothing here changes the map; it is the same data the Blender boards print.

compare() gives the side-by-side 3D pages (tools/story.py, engineering/compare/): per problem, the subsystems of the current
model to show on the left (ids of shots/m5_subsystems.toml, as the Explore Ship viewer classifies its nodes) and the parts of the
FDP-1 blockout (data/ship_geometry.json) to show on the right, at the same scale.

    python3 lab/problems/fdp1-requirements/site.py [--json | --compare]     # the summary, the whole record, or the 3D pairs
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fdp1diag import model as fdp1_model            # noqa: E402
from fdp1diag import protection as fdp1_protection  # noqa: E402

CELL_X, CELL_R = 2.0, 2.0      # side-elevation bins (m): enough for a page figure, small enough to read the 45 m shadow line
R_CLIP = 140.0                 # the figure's radial reach; the wings continue to wings_max_r_m


def register(m):
    with open(os.path.join(HERE, 'data', 'requirements_p11.json')) as f:
        p11 = json.load(f)['requirements']
    out = []
    for r in m.requirements + p11:
        out.append({'id': r['id'], 'title': r['title'], 'description': m.render(r.get('description', '')),
                    'status': r['status'], 'classification': r.get('classification', []),
                    'current': [m.render(c) for c in r.get('current', [])], 'target': m.render(r.get('target', '')),
                    'gap': m.render(r.get('gap', '')), 'depends': r.get('depends', []),
                    'unresolved': r.get('unresolved', [])})
    return out


def elevation(pr):
    """Binned (x, r) cells per class for the aligned stream (cone 0, margin 0), the shield station and the wing extent."""
    cells = {}
    wings_r = 0.0
    for p in pr.geo['parts']:
        cl = fdp1_protection.classify(p)
        if cl == 'EXCLUDED':
            continue
        if p['shape'] == 'panel':
            pts = [(c[0], math.hypot(c[1], c[2])) for c in p['corners']]
            if cl == 'RADIATOR':
                wings_r = max(wings_r, max(r for _, r in pts))
            x0, x1 = min(x for x, _ in pts), max(x for x, _ in pts)
            r0, r1 = min(r for _, r in pts), min(max(r for _, r in pts), R_CLIP)
            if r0 > R_CLIP:
                continue
            n = max(2, int((r1 - r0) / CELL_R))
            smp = [(x0 + (x1 - x0) * i / n, r0 + (r1 - r0) * j / n) for i in range(n + 1) for j in range(n + 1)] if x1 - x0 > CELL_X \
                else [((x0 + x1) / 2, r0 + (r1 - r0) * j / n) for j in range(n + 1)]
            rows = [(x, r, 0.0) for x, r in smp]
        else:
            rows = [(x, math.hypot(y, z), z) for x, y, z, _ in fdp1_protection.samples(p, 1.0)]
        for x, r, _ in rows:
            if r > R_CLIP:
                continue
            if cl == 'SHIELD':
                kind = 'shield'
            else:
                inside = r <= pr.shield['radius_m'] and x <= pr.x_s
                kind = ('radiator_' if cl == 'RADIATOR' else 'part_') + ('covered' if inside else 'outside')
            key = (round(x / CELL_X), round(r / CELL_R))
            prev = cells.get(key)
            if prev is None or (prev.endswith('covered') and kind.endswith('outside')):
                cells[key] = kind
    return {'cell_m': [CELL_X, CELL_R], 'r_clip_m': R_CLIP,
            'cells': sorted([k[0] * CELL_X, k[1] * CELL_R, v] for k, v in cells.items()),
            'wings_max_r_m': wings_r}


# Per problem: what the current model shows (left, subsystem ids) and which FDP-1 blockout groups carry the requirement (right).
# ALL means the whole ship. The note says what the pair shows; the numbers come from the register.
PAIRS = [
    ('P01', ['S10'], ['fdp1_reaction', 'fdp1_fuel_prep', 'fdp1_nozzle'],
     'The burn point: today a reactor and four nozzles; FDP-1 needs a target chain (injector, tracker, reaction point) whose gain is unproven.'),
    ('P02', ['S10', 'S08'], ['fdp1_drivers', 'fdp1_sensors', 'fdp1_power'],
     'The drivers: FDP-1 needs beam galleries, final focus and their power feeds for billions of pulses.'),
    ('P03', ['ALL'], ['ALL'],
     'Power per mass: the whole ship today against the FDP-1 ship. 1 g would need power hardware many times heavier than either.'),
    ('P04', ['S10'], ['fdp1_nozzle'],
     'Magnetic nozzle: today\'s four-nozzle drive against the FDP-1 loops, r 112 m, that must catch and push the plasma.'),
    ('P05', ['S10', 'S01'], ['fdp1_shield'],
     'Radiation shielding: FDP-1 needs armour shoes and a shadow shield around every loop, near the burn point.'),
    ('P06', ['S09'], ['fdp1_thermal'],
     'Heat transport: the headers, lines and pumps that carry the waste heat out to the wings are not designed yet.'),
    ('P07', ['S09'], ['fdp1_thermal', 'radiators'],
     'Radiators: today\'s blades and zones against the wing area FDP-1 needs to reject its heat.'),
    ('P08', ['S05', 'S06', 'S07'], ['storage', 'fdp1_tanks', 'bow'],
     'Propellant: today\'s tank farm against the T-B farm, which moves the bow 122 m forward.'),
    ('P09', ['S02'], ['fdp1_structure', 'hull'],
     'Structure: the spine today against the FDP-1 module frames, which carry every pulse for years.'),
    ('P10', ['ALL'], ['ALL'],
     'The whole mission: today\'s ship against the FDP-1 ship that closes four burns.'),
    ('P11', ['S01'], ['ALL'],
     'Collision protection: everything outside the shield\'s shadow (the translucent cylinder) is hit at 0.016 c.'),
]


def compare():
    with open(os.path.join(HERE, 'data', 'ship_geometry.json')) as f:
        geo = json.load(f)
    keep = ('name', 'group', 'func', 'shape', 'status', 'x0', 'x1', 'r0', 'r1', 'ri0', 'ri1', 'arc', 'centre', 'x', 'R', 'a',
            'size', 'roll', 'corners', 'thickness', 'points', 'radius')
    parts = [{k: p[k] for k in keep if k in p} for p in geo['parts'] if p['status'] != 'SUPERSEDED']
    pr = fdp1_protection.Protection()
    return {'units': geo['meta']['units'], 'parts': parts,
            'shadow': {'radius_m': pr.shield['radius_m'], 'x_m': pr.x_s},
            'pairs': [{'id': i, 'current': cur, 'needed': need, 'note': note} for i, cur, need, note in PAIRS]}


def story():
    m = fdp1_model.Model()
    pr = fdp1_protection.Protection()
    rows = pr.assess()
    summary = fdp1_protection.summarize(rows)
    rad = pr.radiators()
    planform = sum(r['planform_m2'] for r in rad)
    return {
        'register': register(m),
        'checks': {'passed': sum(c['ok'] for c in m.checks), 'total': len(m.checks)},
        'protection': {
            'shield_radius_m': pr.shield['radius_m'], 'shield_x_m': pr.x_s,
            'engine': fdp1_protection.engine_envelope(pr.geo),
            'critical_parts': summary['critical_parts'], 'critical_outside': summary['critical_exposed'],
            'max_protrusion_m': summary['max_protrusion_m'],
            'radiator_outside_fraction': (sum(r['exposed_m2'] for r in rad) / planform) if planform else None,
            'unresolved': [list(u) for u in fdp1_protection.UNRESOLVED_CATEGORIES],
            'elevation': elevation(pr),
        },
    }


if __name__ == '__main__':
    s = story()
    if '--compare' in sys.argv:
        print(json.dumps(compare(), separators=(',', ':')))
        sys.exit(0)
    if '--json' in sys.argv:
        print(json.dumps(s, separators=(',', ':')))
        sys.exit(0)
    p = s['protection']
    print(f"{len(s['register'])} problems, checks {s['checks']['passed']}/{s['checks']['total']}; shield r {p['shield_radius_m']:.1f} m at "
          f"x {p['shield_x_m']:.1f}; engine r {p['engine']['max_radius_m']:.1f} m; {p['critical_outside']}/{p['critical_parts']} critical "
          f"parts outside; radiators {100 * p['radiator_outside_fraction']:.1f} % outside; {len(p['elevation']['cells'])} cells")
