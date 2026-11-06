"""What the Engineering pages of the website (tools/story.py) show of this problem map. Standard library only.

story() returns the problem register P01-P11 with its values filled from the FDP-1 record (fdp1diag.model), the model's own
checks, and the P11 side-elevation data: the shield shadow and every part's radial extent along the ship, classified covered or
outside for the aligned stream (fdp1diag.protection). Nothing here changes the map; it is the same data the Blender boards print.

    python3 lab/problems/fdp1-requirements/site.py [--json]     # prints the summary (or the whole record)
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
    if '--json' in sys.argv:
        print(json.dumps(s, separators=(',', ':')))
        sys.exit(0)
    p = s['protection']
    print(f"{len(s['register'])} problems, checks {s['checks']['passed']}/{s['checks']['total']}; shield r {p['shield_radius_m']:.1f} m at "
          f"x {p['shield_x_m']:.1f}; engine r {p['engine']['max_radius_m']:.1f} m; {p['critical_outside']}/{p['critical_parts']} critical "
          f"parts outside; radiators {100 * p['radiator_outside_fraction']:.1f} % outside; {len(p['elevation']['cells'])} cells")
