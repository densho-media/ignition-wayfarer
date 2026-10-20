"""Q38 candidate warm panels (15!A98, 40!A67:F68): PROTOTYPE geometry for the dedicated, cold-space-facing 450 K panels, capacity unknown.

The owner's direction: no warm or cold rejection is credited to the hot-facing casing or ring surfaces; warm heat goes to dedicated panels
with a clear cold-space view, shielded from the 1800 K blades; "Claude: leave capacity unknown, show candidate panels PROTOTYPE only" (15!I98).
The AFT-010 heat-loop screen finds the least-irradiated candidates in the blade planes, forward of the blade front
and inside the shield shadow, where each blade is seen edge-on. The Q45 bypass collar already runs a planar truss in each blade plane there
(r 33-35 m, from its aft station to the shield truss), so the candidate is a pair of single-sided plates flanking each collar truss, carried by
it on brackets: radiating faces outward, the truss between them. The collar's three r 35 m hoops cross every blade plane, so each plate is split
axially into segments that leave each hoop its radius plus clearance. Every choice here is PROTOTYPE; warm.area stays OPEN and nothing here feeds
an area, view factor or margin (AGENTS.md: never credit capacity to a mesh). Pure standard library.
"""
import math

import forward_shield
import habitat_ring
import hull_geometry


def table(s):
    return s['thermal']['loops']['candidate_panels']


def _plane(s, j):
    th = math.radians(s['prototype']['radiator_phase_deg']+j*s['radiators']['separation_deg'])
    return th, (0.0, math.cos(th), math.sin(th)), (0.0, -math.sin(th), math.cos(th))


def envelope(s):
    """Axial and radial bounds shared by every panel: from the collar's aft station to the shield truss (less clearance), from the ring rim plus
    the ring service clearance to the shield shadow radius."""
    q = table(s); collar = forward_shield.bypass_collar(s); clr = s['prototype']['mechanical_clearance_m']
    r_lo = habitat_ring.outer(s)+s['habitat']['ring_service_clearance']['min_m']
    r_hi = forward_shield.shield_radius(s)-s['forward_shield']['radiator_shadow_margin']['value']
    x_lo = collar['stations']['aft']; x_hi = min(forward_shield.truss_aft_at(s, r) for r in (r_lo, r_hi))-clr
    offset = collar['member_radius']+clr+q['thickness_m']/2          # plate mid-plane off the collar truss plane
    cuts = sorted(h['x'] for h in collar['hoops']); gap = max(h['radius'] for h in collar['hoops'])+clr
    edges = [x_lo]+[v for x in cuts for v in (x-gap, x+gap)]+[x_hi]
    segments = [(a, b) for a, b in zip(edges[::2], edges[1::2]) if b-a > 2*gap]       # drop the slivers behind a hoop at the panel edge
    return dict(r_lo=r_lo, r_hi=r_hi, x_lo=x_lo, x_hi=x_hi, offset=offset, segments=segments)


def panels(s):
    """Per blade plane j, side P/M and axial segment k: the plate box (8 corners, faces), its outward normal, the brackets to the collar chords
    (0.5 m inside each segment end) and the radiating area of its outer face."""
    q = table(s); e = envelope(s); collar = forward_shield.bypass_collar(s); t = q['thickness_m']; out = []
    chords = (collar['inner_r'], collar['outer_r'])
    for j in range(s['radiators']['count']):
        th, u, n = _plane(s, j)
        for sign, side in ((1, 'P'), (-1, 'M')):
            def at(x, r, d):
                return (x, r*u[1]+d*n[1], r*u[2]+d*n[2])
            near, far = sign*(e['offset']-t/2), sign*(e['offset']+t/2)
            for k, (x0, x1) in enumerate(e['segments'], 1):
                name = f'Warm_Panel_{j+1}{side}_{k}'
                corners = [at(x, r, d) for d in (near, far) for x in (x0, x1) for r in (e['r_lo'], e['r_hi'])]
                faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
                brackets = [(f'{name}_Bracket_{"AF"[a]}{"IO"[c]}', [at(x, r, 0.0), at(x, r, near)])
                            for a, x in enumerate((x0+.5, x1-.5)) for c, r in enumerate(chords)]
                out.append(dict(name=name, plane=j+1, side=side, segment=k, theta=th, normal=tuple(sign*v for v in n), corners=corners,
                                faces=faces, brackets=brackets, radiating_area_m2=(x1-x0)*(e['r_hi']-e['r_lo'])))
    return out


def _segment_distance(a, b, c, d, steps=64):
    pa = [tuple(a[i]+(b[i]-a[i])*k/steps for i in range(3)) for k in range(steps+1)]
    pc = [tuple(c[i]+(d[i]-c[i])*k/steps for i in range(3)) for k in range(steps+1)]
    return min(math.dist(p, r) for p in pa for r in pc)


def check(s):
    """Fit screen: clearances to the ring rim, the shield truss, the collar members and the dock corridors. Returns (rows, failures)."""
    q = table(s); e = envelope(s); clr = s['prototype']['mechanical_clearance_m']; collar = forward_shield.bypass_collar(s)
    rows = {'ring_rim_gap_m': e['r_lo']-habitat_ring.outer(s), 'truss_gap_m': min(forward_shield.truss_aft_at(s, r) for r in (e['r_lo'], e['r_hi']))-e['x_hi'],
            'collar_member_gap_m': e['offset']-q['thickness_m']/2-collar['member_radius']}
    dock = math.inf
    for c in hull_geometry.dock_corridors(s):
        for j in range(s['radiators']['count']):
            th, u, n = _plane(s, j)
            for sign in (1, -1):
                d0 = sign*e['offset']
                axis = [(c['x'], r*math.cos(c['theta']), r*math.sin(c['theta'])) for r in (c['r0'], c['r1'])]
                edge = [(min(max(c['x'], e['x_lo']), e['x_hi']), r*u[1]+d0*n[1], r*u[2]+d0*n[2]) for r in (e['r_lo'], e['r_hi'])]
                dock = min(dock, _segment_distance(*axis, *edge)-c['radius'])
    rows['dock_corridor_gap_m'] = dock if dock < math.inf else None
    crossed = any(a < h['x'] < b for h in collar['hoops'] for a, b in e['segments'])
    rows['hoop_gap_m'] = -1.0 if crossed else min(abs(h['x']-x)-h['radius'] for h in collar['hoops'] for a, b in e['segments'] for x in (a, b))
    area = sum(p['radiating_area_m2'] for p in panels(s))
    rows['radiating_area_m2'] = area
    fails = [f'{k} {v:.3f} m below {need:.3f} m' for k, v, need in (('ring_rim_gap_m', rows['ring_rim_gap_m'], s['habitat']['ring_service_clearance']['min_m']),
                                                                    ('truss_gap_m', rows['truss_gap_m'], clr), ('collar_member_gap_m', rows['collar_member_gap_m'], clr),
                                                                    ('hoop_gap_m', rows['hoop_gap_m'], clr))
             if v < need-1e-9]
    if rows['dock_corridor_gap_m'] is not None and rows['dock_corridor_gap_m'] < clr:
        fails.append(f"a panel enters a dock corridor ({rows['dock_corridor_gap_m']:.3f} m)")
    if s['thermal']['loops']['warm']['area'].get('known') is not False:
        fails.append('thermal.loops.warm.area must stay unknown: the candidate panels carry no capacity (15!I98)')
    return rows, fails


if __name__ == '__main__':
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import spec
    s, *_ = spec.load()
    rows, fails = check(s)
    print(json.dumps({'envelope': envelope(s), **rows, 'panels': len(panels(s)), 'failures': fails}, indent=1))
    sys.exit(1 if fails else 0)
