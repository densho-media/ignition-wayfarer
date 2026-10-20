"""HUM-003 (S&E 15_MODEL_INTERFACES!A126, owner answer 2026-10-11; follow-up of HUM-002): disposable candidate studies for full-length supported
casualty transport WITH staff and kit. NONCANON, PROTOTYPE, CANDIDATE STUDIES / NO HULL RELEASE: nothing here changes data/, a generator or a
saved asset. Release needs a rigid full-length supported carrier + staff/kit tested spinning, stopped and at 1.5 g with pressure/hub/station
effects (15!A126); near-zero clearances are not sufficient, so every margin below STUDY_MARGIN_M is MARGINAL, never PASS.

What is measured (all in memory; the scene is never saved):
- rings: the built model (ROOT) and disposable workspaces (casualty_whatif's approach: a copy of data/ with one [human_entry.study] change,
  built by build.py --root under runs/hum003/<variant>/work): ring A annulus +0.40 m; ring B port and necks 1.10 m. Routes start on the trunk
  axis at the dock station (the dock entry is not part of a sector-to-treatment/refuge route) and run to every sector deck, the medical couch
  (SP-33/SP-50, WORK_MEDICAL_OPS) and between sectors of one ring through its drum annulus. The closed-drum dwell (transfer while a ring spins)
  is searched with the carrier AND staff wholly inside the closed drum.
- local: the refuge entry candidates and the EVA-003 branch, as a local free-space model (Blender booleans of the trunk, the refuge annulus and
  the candidate opening, so the opening is a real hole) plus every built fixture in that region (ladder, rails, frames, hoop and anchor rails,
  panel, survival racks); calibrated against the built 0.90 m radial refuge port. And the trunk hoist: the carrier standing in the trunk on a
  guide line (aft down) next to an attendant on the trunk ladder, against the built model.

Carriers (PROTOTYPE envelopes, HUM-002 numbers; stretcher geometry OPEN, 12!G21; no medical judgement):
- A rigid litter: box 2.00 x 0.55 x 0.30 m.  C vacuum mattress: box 1.85 x 0.50 x 0.25 m.
- K A with its kit (monitor, oxygen, suction) strapped over the legs: + a 0.60 x 0.55 x 0.15 m box on the last 0.60 m (0.45 m deep there).
- S (EVA-003 link) a suited casualty on a full-length litter frame: capsule of the suited-supported passage circle (0.857 m, instructor
  envelope, references/p1_eva_envelopes.json) over its 2.093 m length.
HUM-002 swept A/C/K as capsules of the section's circumscribed circle between joints 2.0 m apart: that overran each end by 0.31 m, so its
turn results were pessimistic. Here a box is the stated envelope; its clearance is the largest inflation of the box (sharp, so conservative
at edges) that does not overlap the built meshes (BVH overlap, bisection to ~0.004 m), capped at CAP_M ("at least").
Staff: one shirt-sleeve rescuer inline at each end (capsule r 0.25 m reaching 0.70 m beyond the end along the route, HUM-001/002); beside the
couch they stand in the aisle and are not checked on the last sideways leg. A search pass is a found pose (sampled, not a motion proof).

    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/hum003_routes.py -- rings --root <work> --tag <name> --routes A1,A2
    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/hum003_routes.py -- local
    python3 src/wayfarer/studies/hum003_routes.py collect          (writes references/p1_hum003.json)
"""
from pathlib import Path
import argparse
import bisect
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/studies'), str(ROOT/'tools')]
RUNS = ROOT/'runs/hum003'
OUT_JSON = ROOT/'references/p1_hum003.json'
RENDERS = ROOT/'renders/p1/studies/hum003'

STUDY_MARGIN_M = 0.05            # HUM-003: near-zero clearances are not sufficient
CAP_M = 0.10                     # margins are searched up to this value and reported as "at least"
STEP_M = 0.10
SEARCH = 120
REFINE = 40
SPREAD_M = 0.60
CARRIERS = {    # PROTOTYPE envelopes
    'A': dict(name='rigid full-length litter', shape='box', size=(2.00, 0.55, 0.30)),
    'C': dict(name='vacuum mattress (rigid when evacuated)', shape='box', size=(1.85, 0.50, 0.25)),
    'K': dict(name='rigid litter with kit over the legs', shape='box', size=(2.00, 0.55, 0.30), kit=(0.60, 0.55, 0.15)),
    'S': dict(name='suited casualty on a full-length litter frame (EVA-003)', shape='capsule', length=2.093, radius=0.857/2),
}
STAFF_R_M = 0.25
STAFF_REACH_M = 0.70
STAFF_BODY_M = 1.25              # a crew member tucked and holding a rail (capsule overall length) in the closed-drum dwell
HOIST_HEAD_M = 0.15              # PROTOTYPE: hoist head (sheave, brake) depth under the trunk's forward end


def status(m):
    return 'FAIL' if m is None or m < 0 else ('MARGINAL' if m < STUDY_MARGIN_M else 'PASS')


# ------------------------------------------------------------------------------------------------------------------------------------
# geometry of a carrier pose (head point, unit axis from head to tail, roll)

def frame(d, roll):
    import numpy as np
    d = np.asarray(d, float); d = d/np.linalg.norm(d)
    ref = np.array((0.0, 0.0, 1.0)) if abs(d[2]) < .9 else np.array((0.0, 1.0, 0.0))
    w0 = np.cross(d, ref); w0 /= np.linalg.norm(w0); t0 = np.cross(d, w0)
    w = w0*math.cos(roll)+t0*math.sin(roll); t = np.cross(d, w)
    return d, w, t


def boxes(car, head, d, roll):
    """[(centre, (axis_len, axis_w, axis_t), half sizes)] of a box carrier; head first along d (head -> tail)."""
    import numpy as np
    u, w, t = frame(d, roll); L, W, T = car['size']; h = np.asarray(head, float)
    out = [(h+u*L/2, (u, w, t), (L/2, W/2, T/2))]
    if car.get('kit'):
        kl, kw, kt = car['kit']
        out.append((h+u*(L-kl/2)+t*(T/2+kt/2), (u, w, t), (kl/2, kw/2, kt/2)))
    return out


def box_mesh(bx, m):
    vs, fs = [], []
    for c, (u, w, t), (a, b, e) in bx:
        a, b, e = a+m, b+m, e+m; n = len(vs)
        for i in (-1, 1):
            for j in (-1, 1):
                for k in (-1, 1):
                    vs.append(tuple(c+u*a*i+w*b*j+t*e*k))
        fs += [tuple(n+q for q in f) for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3))]
    return vs, fs


def axis_points(car, head, d, n=9):
    import numpy as np
    L = car['size'][0] if car['shape'] == 'box' else car['length']
    return [tuple(np.asarray(head)+np.asarray(d)*L*i/(n-1)) for i in range(n)]


class Walls:
    """Built meshes near the routes (casualty_sweep.Clearance's selection) as one BVH, plus optional signed free-space walls (local model)."""

    def __init__(self, records, pts, free=None):
        import casualty_sweep as cs
        self.cl = cs.Clearance(records, pts) if records else None
        self.free = free                                    # (BVHTree, ) of a closed free-space mesh, normals pointing out of the free space

    def name(self, i):
        return self.cl.names[bisect.bisect_right(self.cl.offsets, i)-1]

    def overlaps(self, vs, fs):
        from mathutils.bvhtree import BVHTree
        t = BVHTree.FromPolygons(vs, fs)
        hit = t.overlap(self.cl.tree) if self.cl else []
        if hit:
            return self.name(hit[0][1])
        if self.free is not None and t.overlap(self.free):
            return 'FREE_SPACE_WALL'
        return None

    def outside(self, pts):
        """Any point outside the local free space (by the nearest wall's normal), or None."""
        from mathutils import Vector
        if self.free is None:
            return False
        for p in pts:
            loc, n, _, dist = self.free.find_nearest(Vector(p))
            if loc is not None and dist > .02 and (Vector(p)-loc).dot(n) > 0:
                return True
        return False

    def point(self, p):
        from mathutils import Vector
        best = (math.inf, None)
        if self.cl:
            d = self.cl.point(p, 0.0)
            best = d
        if self.free is not None:
            loc, n, _, dist = self.free.find_nearest(Vector(p))
            if loc is not None:
                dd = -dist if (Vector(p)-loc).dot(n) > 0 else dist
                if dd < best[0]:
                    best = (dd, 'FREE_SPACE_WALL')
        return best

    def capsule(self, a, b, r):
        n = max(1, math.ceil(math.dist(a, b)/.08)); best = (math.inf, None)
        for k in range(n+1):
            p = tuple(a[i]+(b[i]-a[i])*k/n for i in range(3)); m = self.point(p)
            if m[0]-r < best[0]:
                best = (m[0]-r, m[1])
        return best


def margin(walls, car, head, d, roll, cap=CAP_M, check_outside=True):
    """Clearance of one carrier pose: (margin, nearest), at most cap."""
    if car['shape'] == 'capsule':
        import numpy as np
        R = car['radius']; L = car['length']; a = tuple(np.asarray(head)+np.asarray(d)*R); b = tuple(np.asarray(head)+np.asarray(d)*(L-R))
        m = walls.capsule(a, b, R)
        return (min(m[0], cap), m[1])
    if check_outside and walls.outside(axis_points(car, head, d)):
        return (-0.5, 'OUTSIDE_FREE_SPACE')
    bx = boxes(car, head, d, roll)
    if walls.overlaps(*box_mesh(bx, cap)) is None:
        return (cap, None)
    lo, hi = -0.14, cap; name = walls.overlaps(*box_mesh(bx, lo))
    if name is not None:
        return (lo, name)
    name = walls.overlaps(*box_mesh(bx, hi))
    for _ in range(7):
        mid = (lo+hi)/2; n2 = walls.overlaps(*box_mesh(bx, mid))
        if n2 is None:
            lo = mid
        else:
            hi, name = mid, n2
    return (lo, name)


def length(car):
    return car['size'][0] if car['shape'] == 'box' else car['length']


def best_pose(walls, car, head, tail, roll0, rng, n=SEARCH, spread=SPREAD_M):
    """Best pose about a seed (head, tail on the route): random carried poses (length kept, any roll) and a local refinement."""
    import numpy as np
    L = length(car); h0 = np.asarray(head, float); d0 = np.subtract(tail, head); d0 = d0/np.linalg.norm(d0)
    best = (*margin(walls, car, h0, d0, roll0), h0, d0, roll0)
    if best[0] >= CAP_M:
        return best
    for sp, k, droll in ((spread, n, math.pi), (.15, REFINE, .4)):
        c_h, c_d, c_r = (h0, d0, roll0) if sp == spread else best[2:]
        for _ in range(k):
            h = c_h+rng.uniform(-1, 1, 3)*sp/math.sqrt(3); tl = c_h+c_d*L+rng.uniform(-1, 1, 3)*sp/math.sqrt(3)
            d = tl-h; d = d/np.linalg.norm(d); r = c_r+rng.uniform(-droll, droll)
            m = margin(walls, car, h, d, r)
            if m[0] > best[0]:
                best = (*m, h, d, r)
                if best[0] >= CAP_M:
                    return best
    return best


# ------------------------------------------------------------------------------------------------------------------------------------
# sweeps along a route polyline

def turn_roll(path, cum, t, d):
    """Roll that puts the carrier's width across the local turn plane (its thin side in the plane of the turn)."""
    import numpy as np
    import casualty_sweep as cs
    a = np.subtract(cs.at(path, cum, min(t+.6, cum[-1]))[1], cs.at(path, cum, t)[1]); b = np.subtract(cs.at(path, cum, t)[1], cs.at(path, cum, max(t-.6, 0))[1])
    n = np.cross(a, b)
    if np.linalg.norm(n) < 1e-6:
        return 0.0
    u, w0, t0 = frame(d, 0.0); n = n/np.linalg.norm(n)
    return math.atan2(float(np.dot(n, t0)), float(np.dot(n, w0)))


def best_staff(walls, end, ahead, rng, n=60):
    """A rescuer holding the carrier's end: a capsule from near the end-face centre (within 0.15 m) toward the route point beyond it (within
    0.35 m) or 0.5-0.95 m off the end in any direction; the best of n tries (a rescuer adjusts their body), (margin, nearest)."""
    import numpy as np
    best = walls.capsule(end, ahead, STAFF_R_M)
    for _ in range(n):
        if best[0] >= CAP_M:
            break
        a = tuple(np.asarray(end)+rng.uniform(-.15, .15, 3))
        if rng.uniform() < .5:
            b = tuple(np.asarray(ahead)+rng.uniform(-.35, .35, 3))
        else:
            e = rng.normal(size=3); b = tuple(np.asarray(a)+e/np.linalg.norm(e)*rng.uniform(.5, .95))
        if not .3 <= math.dist(a, b) <= 1.1:
            continue
        m = walls.capsule(a, b, STAFF_R_M)
        if m[0] > best[0]:
            best = m
    return best


def sweep_route(walls, car, route, rng, staff=True, couch=False):
    """Least clearance of a carrier (and its two inline staff) along a route: per zone, the tightest point and the staff margin."""
    import numpy as np
    import casualty_sweep as cs
    L = length(car); path = tuple(zip(*route)); cum = cs.cumulative(path[1]); res = dict(least=(math.inf,), zones={}, staff=(math.inf, None, None, None))
    staff_end = cum[-2] if couch else cum[-1]
    for t in np.arange(L, cum[-1]+1e-9, STEP_M):
        zone, head = cs.at(path, cum, t); ts = cs.behind(path, cum, t, head, L); tail = cs.at(path, cum, ts)[1]
        tm = cs.behind(path, cum, t, head, min(1.4, L*.7)); mid = cs.at(path, cum, tm)[1]
        seeds = [tail]
        dm = np.subtract(mid, head)
        if np.linalg.norm(dm) > 1e-6:
            seeds.append(tuple(np.asarray(head)+dm/np.linalg.norm(dm)*L))
        best = None
        for sd in seeds:
            d = np.subtract(sd, head)
            if np.linalg.norm(d) < 1e-6:
                continue
            b = best_pose(walls, car, head, sd, turn_roll(path, cum, t, d), rng)
            if best is None or b[0] > best[0]:
                best = b
            if best[0] >= CAP_M:
                break
        m, name, h, d, r = best
        z = str(zone)
        if m < res['zones'].get(z, (math.inf,))[0]:
            res['zones'][z] = (round(m, 3), name, round(float(t), 2), [round(float(x), 3) for x in h], [round(float(x), 3) for x in d], round(r, 3))
        if m < res['least'][0]:
            res['least'] = (round(m, 3), name, z, round(float(t), 2), [round(float(x), 3) for x in h], [round(float(x), 3) for x in d], round(r, 3))
        if staff:
            tail_pt = tuple(h+d*L)
            for a, tt in ((tuple(h), t+STAFF_REACH_M), (tail_pt, ts-STAFF_REACH_M)):
                if 0.0 <= tt <= staff_end:
                    sm = best_staff(walls, a, cs.at(path, cum, tt)[1], rng)
                    if sm[0] < res['staff'][0]:
                        res['staff'] = (round(sm[0], 3), sm[1], z, round(float(t), 2))
    least = res['least']
    return dict(least_m=least[0], status=status(least[0]), nearest=least[1], zone=least[2], at_m=least[3], head=least[4], axis=least[5], roll=least[6],
                by_zone={z: dict(least_m=v[0], status=status(v[0]), nearest=v[1], at_m=v[2]) for z, v in res['zones'].items()},
                staff_least_m=None if res['staff'][0] == math.inf else res['staff'][0], staff_nearest=res['staff'][1], staff_zone=res['staff'][2], staff_at_m=res['staff'][3],
                staff_status=status(res['staff'][0]) if res['staff'][0] != math.inf else 'n/a')


def sweep_poses(walls, car, poses, rng):
    """Least clearance over an explicit pose sequence (head, axis, roll, label): a carrier moved without turning (the axial refuge entry)."""
    least = (math.inf,)
    for h, d, r, label in poses:
        import numpy as np
        tail = tuple(np.asarray(h)+np.asarray(d)*length(car))
        m, name, hh, dd, rr = best_pose(walls, car, h, tail, r, rng, n=60, spread=.25)
        if m < least[0]:
            least = (round(m, 3), name, label, [round(float(x), 3) for x in hh], [round(float(x), 3) for x in dd], round(rr, 3))
    return dict(least_m=least[0], status=status(least[0]), nearest=least[1], at=least[2], head=least[3], axis=least[4], roll=least[5])


# ------------------------------------------------------------------------------------------------------------------------------------
# SIM-027 (owner 2026-10-11 16:45, RINGB-006): worst case over body sizes, pose families and perturbations (not a chosen / best-found pose)

BODY_SCALE_LARGE = 1.08          # PROTOTYPE: large casualty class, the whole carrier envelope (litter + body + kit) scaled
FAM_ROLLS = (0.0, math.radians(30), -math.radians(30))        # PROTOTYPE roll families about the turn-natural roll
FAM_TRIES = 25
JITTER = ((.02, 0, 0, 0, .02, 0, .05), (-.02, 0, 0, 0, -.02, 0, -.05), (0, .02, 0, 0, 0, -.02, .05), (0, -.02, 0, 0, 0, .02, -.05),
          (0, 0, .02, .02, 0, 0, -.05), (0, 0, -.02, -.02, 0, 0, .05))        # head xyz, tail xyz offsets (m), roll (rad): hand-hold wobble
STAFF_LAT_M = 0.10


def scaled(car, k):
    """The carrier with its whole envelope scaled by k (a larger casualty)."""
    c = dict(car)
    if car['shape'] == 'box':
        c['size'] = tuple(v*k for v in car['size'])
        if car.get('kit'):
            c['kit'] = tuple(v*k for v in car['kit'])
    else:
        c['length'] = car['length']*k; c['radius'] = car['radius']*k
    return c


def family_sweep(walls, car, route, couch=False):
    """Deterministic pose families along a route. A family = (axis seed: tail on the route | chord toward the route point behind) x (roll family
    -30 / 0 / +30 deg about the turn-natural roll), each locally adapted (25 + 40 tries within 0.15 m, a fixed seed per step: a rescuer adjusts a
    handled pose, not a global search) and then perturbed (six +-0.02 m / +-0.05 rad hand-hold wobbles; the minimum counts). Per family the least
    over the route; the worst case is the least family; `best_family` is the best family at each step, least over the route. Staff: both ends,
    inline and +-0.10 m lateral, with the same wobbles, around the carrier of the first family."""
    import numpy as np
    import casualty_sweep as cs
    L = length(car); path = tuple(zip(*route)); cum = cs.cumulative(path[1]); staff_end = cum[-2] if couch else cum[-1]
    fam = {}; best_fam = (math.inf, None, None); staff = (math.inf, None, None)
    for t in np.arange(L, cum[-1]+1e-9, STEP_M):
        zone, head = cs.at(path, cum, t); ts = cs.behind(path, cum, t, head, L); tail = cs.at(path, cum, ts)[1]
        tm = cs.behind(path, cum, t, head, min(1.4, L*.7)); mid = cs.at(path, cum, tm)[1]
        seeds = [('tail', tail)]; dm = np.subtract(mid, head)
        if np.linalg.norm(dm) > 1e-6:
            seeds.append(('chord', tuple(np.asarray(head)+dm/np.linalg.norm(dm)*L)))
        at_t = []; first = None
        for si, (sn, sd) in enumerate(seeds):
            d = np.subtract(sd, head)
            if np.linalg.norm(d) < 1e-6:
                continue
            r0 = turn_roll(path, cum, t, d)
            for ri, off in enumerate(FAM_ROLLS):
                key = f'{sn}/{round(math.degrees(off)):+d}'
                m, name, h, dd, r = best_pose(walls, car, head, sd, r0+off, np.random.default_rng(int(round(t*100))*37+si*5+ri), n=FAM_TRIES, spread=.15)
                if m < CAP_M:
                    tl = np.asarray(h)+np.asarray(dd)*L
                    for j in JITTER:
                        h2 = np.asarray(h)+np.array(j[:3]); d2 = tl+np.array(j[3:6])-h2; d2 = d2/np.linalg.norm(d2)
                        mj = margin(walls, car, h2, d2, r+j[6])
                        if mj[0] < m:
                            m, name = mj
                if m < fam.get(key, (math.inf,))[0]:
                    fam[key] = (round(m, 3), name, round(float(t), 2), str(zone))
                at_t.append((m, name))
                if first is None:
                    first = (np.asarray(h), np.asarray(dd), r)
        if at_t:
            b = max(at_t, key=lambda q: q[0])
            if b[0] < best_fam[0]:
                best_fam = (round(b[0], 3), b[1], round(float(t), 2))
        if first is not None:
            h, dd, r = first; tail_pt = h+dd*L; u, w, _ = frame(dd, r)
            for a, tt in ((h, t+STAFF_REACH_M), (tail_pt, ts-STAFF_REACH_M)):
                if not 0.0 <= tt <= staff_end:
                    continue
                ahead = np.asarray(cs.at(path, cum, tt)[1])
                for lat in (0.0, STAFF_LAT_M, -STAFF_LAT_M):
                    for j in ((0,)*6,)+tuple(tuple(x*1.5 for x in q[:6]) for q in JITTER[:4]):
                        a2 = a+w*lat+np.array(j[:3]); b2 = ahead+w*lat+np.array(j[3:6])
                        sm = walls.capsule(tuple(a2), tuple(b2), STAFF_R_M)
                        if sm[0] < staff[0]:
                            staff = (round(sm[0], 3), sm[1], round(float(t), 2))
    worst = min(fam.items(), key=lambda kv: kv[1][0]) if fam else None
    return dict(worst_family_m=worst[1][0] if worst else None, worst_family=worst[0] if worst else None, worst_nearest=worst[1][1] if worst else None,
                worst_at_m=worst[1][2] if worst else None, worst_zone=worst[1][3] if worst else None,
                families={k: dict(least_m=v[0], nearest=v[1], at_m=v[2]) for k, v in fam.items()},
                best_family_m=None if best_fam[0] == math.inf else best_fam[0], best_family_nearest=best_fam[1],
                staff_least_m=None if staff[0] == math.inf else staff[0], staff_nearest=staff[1], staff_at_m=staff[2])


# ------------------------------------------------------------------------------------------------------------------------------------
# routes

def trunk_routes(s):
    """human_entry.route() without the dock entry (from the trunk axis at the dock station), the medical legs, and sector-to-sector legs of
    ring B (the induction ring's exist already)."""
    import casualty_sweep as cs
    import crew_transfer
    import human_entry as he
    routes = he.route(s); out = {}
    for k, r in routes.items():
        p = r['path']
        if k[0] in 'AB' and len(k) == 2:
            out[k] = dict(path=p[2:])
        elif '-' in k:
            out[k] = dict(path=p)
    for j in s['human_entry']['tube_rotors']:              # ring B sector legs (the induction ring has its own)
        tag = 'AB'[j-1]
        if f'{tag}1-{tag}2' in out:
            continue
        rot, v, la = he.vestibule_station(s, j); mid = (v['r0']+v['clear'])/2
        def descent(key):
            p = out[key]['path']; i3 = max(i for i, q in enumerate(p) if q[0] == 3); return p[i3:]
        for k1 in (1, 3):
            up = descent(f'{tag}{k1}'); back = [(up[i+1][0], up[i][1]) for i in reversed(range(len(up)-1))]
            turn = math.remainder(la[2]-la[k1], 2*math.pi); n = max(1, math.ceil(abs(turn)/math.radians(5)))
            around = [(3, he.at_index(rot, crew_transfer.radial(v['port_u'], mid, la[k1]+turn*i/n))) for i in range(n+1)]
            out[f'{tag}{k1}-{tag}2'] = dict(path=[up[-1]]+back+around+descent(f'{tag}2'))
    med = cs.medical_routes(s, {k: dict(path=v['path']) for k, v in out.items() if len(k) == 2})
    for k, v in med.items():
        out[k] = dict(path=v['path'], couch=True)
    # sector -> sector 2 -> couch: the inter-sector leg cut at its final landing, then the couch leg
    for key in [k for k in out if '-' in k and k.endswith('2') and not k.endswith('-M')]:
        tag = key[0]; m = out.get(f'{tag}2-M')
        if not m:
            continue
        p = out[key]['path']; cut = max(i for i, q in enumerate(p) if q[0] == 4)+1
        leg = [q for q in m['path'] if q[0] == 'M']
        out[f'{key}-M'] = dict(path=p[:cut+1]+leg, couch=True)
    return out


def lifts(route):
    """Under 1.5 g aft-down (+X up): the vertical extent of each crew-tube and trunk leg, the longest single vertical run."""
    p = route['path']; runs = []; cur = 0.0
    for (z0, a), (z1, b) in zip(p, p[1:]):
        dx = b[0]-a[0]; horiz = math.hypot(b[1]-a[1], b[2]-a[2])
        if abs(dx) > 2*horiz and abs(dx) > .05:
            cur += abs(dx)
        else:
            if cur:
                runs.append(round(cur, 2))
            cur = 0.0
    if cur:
        runs.append(round(cur, 2))
    xs = [q[1][0] for q in p]
    return dict(x_span_m=[round(min(xs), 2), round(max(xs), 2)], vertical_runs_m=runs)


# ------------------------------------------------------------------------------------------------------------------------------------
# closed-drum dwell with staff (transfer while the ring spins)

def dwell(s, records, carriers, rng, n=2500):
    """The party wholly inside the closed drum: the carrier's best pose first, then each crew member (a tucked capsule) placed in turn, clear
    of the walls, the closures and the carrier (greedy, so a lower bound of what fits)."""
    import numpy as np
    import crew_transfer
    import human_entry as he
    out = {}
    for j in s['human_entry']['vestibule_rotors']:
        rot, v, _ = he.vestibule_station(s, j); r0, r1, u0, u1 = v['r0'], v['clear'], v['cu0'], v['cu1']
        pts = [he.at_index(rot, crew_transfer.radial(u, r1, a*math.tau/24)) for u in (u0, u1) for a in range(24)]
        walls = Walls(records, pts)
        def inside(p):          # vehicle-frame point -> margin to the closed annulus bounds (rotor-local u, r)
            q = crew_transfer.sub(p, (rot['x'], 0.0, 0.0)); r = math.hypot(q[1], q[2]); u = q[0]
            return min(r-r0, r1-r, u-u0, u1-u)
        def rand_pt():
            return np.asarray(he.at_index(rot, crew_transfer.radial(rng.uniform(u0, u1), rng.uniform(r0, r1), rng.uniform(0, math.tau))))
        res = {}
        for cid, car in carriers.items():
            def car_score(h, d, r):
                if car['shape'] == 'box':
                    ins = min(inside(c) for c in box_mesh(boxes(car, h, d, r), 0.0)[0])
                else:
                    ins = min(inside(c) for c in axis_points(car, h, d))-car['radius']
                if ins < 0:
                    return ins
                return min(margin(walls, car, h, d, r, cap=.30)[0], ins)
            best = (-math.inf,)
            for _ in range(n):
                h = rand_pt(); d = rng.normal(size=3); d /= np.linalg.norm(d); r = rng.uniform(0, math.pi); sc = car_score(h, d, r)
                if sc > best[0]:
                    best = (sc, h, d, r)
            for _ in range(400):
                h = best[1]+rng.uniform(-.1, .1, 3); d = best[2]+rng.uniform(-.1, .1, 3); d /= np.linalg.norm(d); r = best[3]+rng.uniform(-.2, .2)
                sc = car_score(h, d, r)
                if sc > best[0]:
                    best = (sc, h, d, r)
            m_car, h, d, r = best; bx = boxes(car, h, d, r) if car['shape'] == 'box' else None
            def gap_to_carrier(p):
                if bx:
                    return box_point_dist(bx, p)
                q = np.subtract(p, h); tt = min(max(float(np.dot(q, d)), car['radius']), length(car)-car['radius'])
                return float(np.linalg.norm(q-d*tt))-car['radius']
            res[f'{cid}+0staff'] = dict(least_m=round(m_car, 3), status=status(m_car)); crew = []; party = m_car
            for k in (1, 2):
                bs = (-math.inf,)
                for _ in range(1500):
                    a = rand_pt(); e = rng.normal(size=3); e /= np.linalg.norm(e); b2 = a+e*(STAFF_BODY_M-2*STAFF_R_M)
                    seg = [a+(b2-a)*i/6 for i in range(7)]
                    ins = min(inside(q) for q in seg)-STAFF_R_M
                    if ins < bs[0]:
                        continue
                    gp = min(gap_to_carrier(q) for q in seg)-STAFF_R_M
                    for c0, c1 in crew:
                        gp = min(gp, min(math.dist(q, c0+(c1-c0)*i/6) for q in seg for i in range(7))-2*STAFF_R_M)
                    sc = min(ins, gp)
                    if sc > bs[0]:
                        sc = min(sc, walls.capsule(tuple(a), tuple(b2), STAFF_R_M)[0])
                        if sc > bs[0]:
                            bs = (sc, a, b2)
                crew.append((bs[1], bs[2])); party = min(party, bs[0])
                res[f'{cid}+{k}staff'] = dict(least_m=round(party, 3), status=status(party), staff_least_m=round(bs[0], 3))
                print('WF_HUM003_DWELL', 'AB'[j-1], cid, k, round(m_car, 3), round(bs[0], 3), flush=True)
        out['AB'[j-1]] = dict(annulus_depth_m=round(r1-r0, 3), clear_length_m=round(u1-u0, 3), party=res)
    return out


def box_point_dist(bx, p):
    import numpy as np
    best = math.inf
    for c, ax, hs in bx:
        q = np.subtract(p, c); d = [max(abs(float(np.dot(q, a)))-h, 0.0) for a, h in zip(ax, hs)]
        best = min(best, math.sqrt(sum(x*x for x in d)))
    return best


# ------------------------------------------------------------------------------------------------------------------------------------
# rings mode

def run_rings(args):
    import bpy
    import numpy as np
    import casualty_sweep as cs
    from spec import load
    s = load(args.root)[0]; bpy.ops.wm.open_mainfile(filepath=str(args.root/'assets/wayfarer/WF_WAYFARER_001.blend')); ins = cs.load_inspect()
    rng = np.random.default_rng(11); routes = trunk_routes(s)
    keys = [k for k in args.routes.split(',') if k] or list(routes)
    records = cs.scene(s, ins, 1.0); out = dict(tag=args.tag, root=str(args.root), routes={}, lifts={k: lifts(routes[k]) for k in keys})
    for k in keys:
        walls = Walls(records, [p for _, p in routes[k]['path']])
        out['routes'][k] = {}
        for cid in args.carriers:
            r = sweep_route(walls, CARRIERS[cid], routes[k]['path'], rng, couch=routes[k].get('couch', False))
            out['routes'][k][cid] = r
            print('WF_HUM003', args.tag, k, cid, r['least_m'], r['status'], r['zone'], r['nearest'], 'staff', r['staff_least_m'], flush=True)
    if args.dwell:
        out['dwell'] = dwell(s, cs.scene(s, ins, 0.0), {c: CARRIERS[c] for c in args.carriers}, rng)
    d = RUNS/args.tag; d.mkdir(parents=True, exist_ok=True); (d/'hum003_rings.json').write_text(json.dumps(out, indent=1, default=str)+'\n')


# ------------------------------------------------------------------------------------------------------------------------------------
# local mode: refuge entry candidates, the EVA branch, the trunk hoist

WALL_NAMES = ('Structural_Spine', 'Crew_Trunk', 'Refuge_Storm_Shelter', 'Refuge_Inner_Wall', 'Crew_Refuge_Port', 'Crew_Connector_Airlock_EVA',
              'Airlock_EVA')
FIXTURE_PREFIX = ('Crew_Trunk_', 'Trunk_Fit_', 'Refuge_', 'Survival_Refuge_')


def prim_cyl(p0, p1, r, seg=96):
    import bpy
    from mathutils import Vector
    a, b = Vector(p0), Vector(p1)
    bpy.ops.mesh.primitive_cylinder_add(vertices=seg, radius=r, depth=(b-a).length, location=(a+b)/2)
    o = bpy.context.active_object; o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(b-a)
    return o


def prim_box(centre, axes, size):
    import bpy
    from mathutils import Matrix, Vector
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    o = bpy.context.active_object
    M = Matrix([list(Vector(a)*sz) for a, sz in zip(axes, size)]).transposed().to_4x4(); M.translation = Vector(centre); o.matrix_world = M
    return o


def boolean(target, operand, op):
    import bpy
    mod = target.modifiers.new('B', 'BOOLEAN'); mod.operation = op; mod.solver = 'EXACT'; mod.object = operand
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(operand)


def free_space(s, opening, x_fwd=None):
    """The local free space: trunk (to its forward end) U refuge annulus U the candidate opening(s); returns (object, BVHTree)."""
    import bpy
    from mathutils.bvhtree import BVHTree
    import human_entry as he
    ref = he.refuge_station(s); tr = s['crew_transfer']['trunk_clear_radius_m']; xf = x_fwd or 102.449-s['crew_transfer']['passage_wall_m']
    trunk = prim_cyl((87.0, 0, 0), (xf, 0, 0), tr)
    ann = prim_cyl((ref['cavity_x0'], 0, 0), (ref['cavity_x1'], 0, 0), ref['pressure']); core = prim_cyl((ref['cavity_x0']-.1, 0, 0), (ref['cavity_x1']+.1, 0, 0), ref['inner'])
    boolean(ann, core, 'DIFFERENCE'); boolean(trunk, ann, 'UNION')
    for o in opening():
        boolean(trunk, o, 'UNION')
    bpy.context.view_layer.update()
    me = trunk.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    vs = [trunk.matrix_world@v.co for v in me.vertices]; fs = [tuple(p.vertices) for p in me.polygons]
    tree = BVHTree.FromPolygons(vs, fs)
    trunk.name = 'HUM003_FREE_SPACE'
    return trunk, tree


def fixtures(records, drop=lambda q: False, cut=None):
    """Built fixtures in the local region (walls excluded); cut(face centre) True removes a face (an opening through a rail or frame)."""
    out = []
    for q in records:
        if q['name'] in WALL_NAMES or not q['name'].startswith(FIXTURE_PREFIX) or drop(q):
            continue
        if q['hi'][0] < 86.5 or q['lo'][0] > 103.0:
            continue
        if cut:
            fs = [f for f in q['fs'] if not cut(tuple(sum(q['vs'][i][k] for i in f)/len(f) for k in range(3)))]
            if not fs:
                continue
            q = dict(q, fs=fs)
        out.append(q)
    return out


def run_local(args):
    import bpy
    import numpy as np
    import casualty_sweep as cs
    import crew_transfer as ct
    import human_entry as he
    from spec import load
    s = load(ROOT)[0]; bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer/WF_WAYFARER_001.blend')); ins = cs.load_inspect()
    rng = np.random.default_rng(13); records = cs.scene(s, ins, 1.0); ref = he.refuge_station(s); xr = ref['x']; th0 = ref['th']
    radial = lambda x, r, a: ct.radial(x, r, a)
    out = dict(refuge={}, eva_branch={}, hoist={})
    carriers = [c for c in args.carriers]
    n_hat = (0.0, math.cos(th0), math.sin(th0)); t_hat = (0.0, -math.sin(th0), math.cos(th0))
    dock_x = 99.4; aft_x = 88.949
    def trunk_leg(x0):
        return [(2, (x0, 0.0, 0.0)), (2, (xr, 0.0, 0.0))]
    def around(r, a0, a1, z='R', n=24):
        return [(z, radial(xr, r, a0+(a1-a0)*i/n)) for i in range(n+1)]
    sg = 1 if s['human_entry']['refuge_panel_deg'] >= 0 else -1      # route R goes round away from the panel side, as built
    berth_a = th0-sg*ref['pitch']*1.5                                  # the second anchor station from the port, away from the panel
    candidates = {}
    # calibration: the built 0.90 m radial port (a round duct along the port axis)
    candidates['radial_0.90'] = dict(
        opening=lambda: [prim_cyl(radial(xr, .5, th0), radial(xr, ref['inner']+.15, th0), ref['clear'])], drop=lambda q: False, cut=None,
        legs={f'from_{w}': trunk_leg(x0)+[('R', radial(xr, ref['circulation_r'], th0))]+around(ref['circulation_r'], th0, th0-sg*math.pi/2)[1:]
              for w, x0 in (('fwd', dock_x), ('aft', aft_x))},
        note='as built: 0.90 m round port on the refuge radial (calibration against the built-model sweep)')
    # axial entry: a slot along the trunk, the carrier moved out sideways without turning
    for W, Ls in ((0.75, 2.30), (0.90, 2.30), (1.00, 2.30)):
        def opening(W=W, Ls=Ls):
            return [prim_box(radial(xr, (tr0+1.25)/2, th0), ((1, 0, 0), t_hat, n_hat), (Ls, W, 1.25-tr0))]
        tr0 = .55
        half = math.atan2(W/2+.03, 1.0)
        def cut(c, W=W, Ls=Ls, half=half):
            a = math.atan2(c[2], c[1]); r = math.hypot(c[1], c[2])
            return abs(ct.angle_diff(a, th0)) < math.atan2(W/2+.03, max(r, .3)) and abs(c[0]-xr) < Ls/2+.03 and .5 < r < 1.35
        candidates[f'axial_slot_{W:.2f}x{Ls:.2f}'] = dict(opening=opening, drop=lambda q: q['name'].startswith('Crew_Trunk_Refuge_Rail'), cut=cut, slot=(W, Ls),
                                                          note=f'axial entry: a {W:.2f} m wide, {Ls:.2f} m long slot hatch through the trunk wall, spine core and refuge inner wall on the refuge radial')
    # tangential vestibule: a round duct on a chord (offset e from the ship axis), entered from the trunk and leaving into the annulus heading round it
    for D, e in ((0.90, 0.35), (0.90, 0.60), (1.10, 0.60)):
        z0 = -0.3; z1 = math.sqrt(ref['inner']**2-e*e)+.3
        P = lambda zz, e=e: (xr, n_hat[1]*e+t_hat[1]*zz, n_hat[2]*e+t_hat[2]*zz)
        rc = 2.05; a_in = math.atan2(*reversed((P(math.sqrt(rc*rc-e*e))[1], P(math.sqrt(rc*rc-e*e))[2])))
        legs = {}
        for w, x0 in (('fwd', dock_x), ('aft', aft_x)):
            chord = [('T', P(zz)) for zz in np.linspace(0.0, math.sqrt(rc*rc-e*e), 12)]
            legs[f'from_{w}'] = trunk_leg(x0)+[('T', P(0.0))]+chord[1:]+around(rc, a_in, a_in+math.pi/2, z='R')[1:]
        candidates[f'tangential_D{D:.2f}_e{e:.2f}'] = dict(
            opening=lambda D=D, P=P, z0=z0, z1=z1: [prim_cyl(P(z0), P(z1), D/2)], drop=lambda q: q['name'].startswith('Crew_Trunk_Refuge_Rail'),
            cut=lambda c, P=P, D=D, z1=z1: (abs(c[0]-xr) < D/2+.03 and math.hypot(c[1]-P(0)[1]-(t_hat[1]*((c[1]-P(0)[1])*t_hat[1]+(c[2]-P(0)[2])*t_hat[2])),
                                                                             c[2]-P(0)[2]-(t_hat[2]*((c[1]-P(0)[1])*t_hat[1]+(c[2]-P(0)[2])*t_hat[2]))) < D/2+.03
                                            and math.hypot(c[1], c[2]) < 1.35),
            legs=legs, chord=dict(D=D, e=e, entry_angle_deg=round(math.degrees(math.asin(e/ref['inner'])), 1)),
            note=f'tangential vestibule: a {D:.2f} m round duct on a chord {e:.2f} m off the ship axis, leaving the trunk into the annulus heading round it')
    for name, c in candidates.items():
        obj, tree = free_space(s, c['opening'])
        fx = fixtures(records, c['drop'], c['cut'])
        res = dict(note=c['note'])
        pts = [(x, y, z) for x in np.linspace(87.5, 102.4, 30) for y in (-3, 0, 3) for z in (-3, 0, 3)]
        walls = Walls(fx, pts, free=tree)
        if 'legs' in c:
            for leg, path in c['legs'].items():
                res[leg] = {}
                for cid in carriers:
                    r = sweep_route(walls, CARRIERS[cid], path, rng)
                    res[leg][cid] = r
                    print('WF_HUM003_REFUGE', name, leg, cid, r['least_m'], r['status'], r['zone'], r['nearest'], 'staff', r['staff_least_m'], flush=True)
        if 'slot' in c:
            W, Ls = c['slot']
            for cid in carriers:
                car = CARRIERS[cid]; L = length(car); x_head = xr+L/2          # head forward, centred on the slot
                poses = []
                for rr in np.linspace(0.0, ref['circulation_r'], 18):           # straight out of the trunk, lying axially
                    poses.append(((x_head,)+tuple(np.asarray(n_hat[1:])*rr), (-1.0, 0.0, 0.0), 0.0 if car['shape'] == 'box' else 0.0, f'out r {rr:.2f}'))
                for a in np.linspace(th0, berth_a, 10):                         # round the annulus to the berth station
                    poses.append(((x_head,)+radial(0, ref['circulation_r'], a)[1:], (-1.0, 0.0, 0.0), a-th0, f'round {math.degrees(a-th0):.0f} deg'))
                for rr in np.linspace(ref['circulation_r'], ref['body_r'], 6):  # out to the occupant station on its anchor rail
                    poses.append(((x_head,)+radial(0, rr, berth_a)[1:], (-1.0, 0.0, 0.0), berth_a-th0, f'berth r {rr:.2f}'))
                fixed = []
                for h, d, r, lab in poses:      # the carrier is handed through flat (width tangential): roll so w is tangential
                    u, w0, t0 = frame(d, 0.0); a = math.atan2(h[2], h[1]); tang = (0.0, -math.sin(a), math.cos(a))
                    fixed.append((h, d, math.atan2(float(np.dot(tang, t0)), float(np.dot(tang, w0))), lab))
                r = sweep_poses(walls, car, fixed, rng)
                res.setdefault('slot_entry', {})[cid] = r
                print('WF_HUM003_SLOT', name, cid, r['least_m'], r['status'], r['at'], r['nearest'], flush=True)
            res['slot_staff_margin_m'] = round(min(W, 0.9)/2-STAFF_R_M, 3)
        if 'chord' in c:
            res['chord'] = c['chord']
            for cid in carriers:              # turn to an axial berth: rotate about the local radial at the berth radius
                car = CARRIERS[cid]; L = length(car); a = math.atan2(*reversed(c['legs']['from_fwd'][-1][1][1:])) if False else None
                end = c['legs']['from_fwd'][-1][1]; a = math.atan2(end[2], end[1]); rb = 2.2; poses = []
                tang = np.array((0.0, -math.sin(a), math.cos(a))); ctr = np.array((xr,)+radial(0, rb, a)[1:])
                for k in range(10):
                    phi = math.pi/2*k/9; d = tang*math.cos(phi)+np.array((1.0, 0, 0))*math.sin(phi)
                    poses.append((tuple(ctr-d*L/2), tuple(d), 0.0, f'turn {math.degrees(phi):.0f} deg'))
                r = sweep_poses(walls, car, poses, rng)
                res.setdefault('turn_to_axial_berth', {})[cid] = r
                print('WF_HUM003_TURN', name, cid, r['least_m'], r['status'], r['at'], r['nearest'], flush=True)
        out['refuge'][name] = res
        bpy.data.objects.remove(obj)
    # EVA-003: SP-12 -> the 0.90 m branch (X 101.849, 50 deg) -> the trunk -> aft to the refuge station; under thrust the branch is a horizontal
    # crawl and the carrier must turn down (aft) in the trunk, whose forward end is 0.10 m above the branch mouth.
    br = next(q for q in ct.stationary(s) if q['name'] == 'Crew_Connector_Airlock_EVA'); xb = br['points'][0][0]
    ab = math.atan2(br['points'][0][2], br['points'][0][1])
    variants = {     # EVA-003 option A extends the trunk forward in the spine bore to SP-13's floor (X 104.9)
        'as_built': dict(xc=xb, r=br['radius'], x_fwd=None, aft=True, note='0.90 m branch, trunk end as built (0.10 m above the branch mouth)'),
        'branch_1.10': dict(xc=xb-.05, r=.55, x_fwd=None, aft=True, note='1.10 m branch, centred 0.05 m further aft so it stays under the trunk end'),
        'trunk_ext_104.9': dict(xc=xb, r=br['radius'], x_fwd=104.9, aft=False,
                                note='0.90 m branch, trunk extended forward to X 104.9 (EVA-003 district option A); the carrier turns head forward into '
                                     'the extension, then is lowered aft along the trunk axis (a straight translation)'),
    }
    for vname, v in variants.items():
        def eva_open(v=v):
            return [prim_cyl(radial(v['xc'], .5, ab), radial(v['xc'], 1.45, ab), v['r']),
                    prim_box(radial(v['xc']+.4, 3.0, ab), ((1, 0, 0), (0.0, -math.sin(ab), math.cos(ab)), (0.0, math.cos(ab), math.sin(ab))), (2.4, 3.4, 3.4))]
        obj, tree = free_space(s, eva_open, v['x_fwd'])
        walls = Walls(fixtures(records), [(x, y, z) for x in np.linspace(87.5, 104.9, 30) for y in (-3, 0, 3) for z in (-3, 0, 3)], free=tree)
        tail = [(2, (v['xc']-1.0, 0.0, 0.0)), (2, (xr+.6, 0.0, 0.0))] if v['aft'] else [(2, (v['xc']+2.6, 0.0, 0.0))]
        path = [('B', radial(v['xc'], 3.6, ab)), ('B', radial(v['xc'], 1.2, ab)), ('B', radial(v['xc'], 0.0, ab))]+tail
        out['eva_branch'][vname] = dict(note=v['note'])
        for cid in carriers:
            r = sweep_route(walls, CARRIERS[cid], path, rng)
            out['eva_branch'][vname][cid] = r
            print('WF_HUM003_EVA', vname, cid, r['least_m'], r['status'], r['zone'], r['nearest'], 'staff', r['staff_least_m'], flush=True)
        bpy.data.objects.remove(obj)
    out['eva_branch']['note'] = ('from 3.6 m out in SP-12 along the branch axis (no SP-12 fit-out modelled), through the branch, turning into the '
                                 'trunk; the branch is at X 101.849 m, 50 deg')
    out['hoist'] = hoist(s, records, rng, carriers)
    (RUNS/'local').mkdir(parents=True, exist_ok=True); (RUNS/'local/hum003_local.json').write_text(json.dumps(out, indent=1, default=str)+'\n')


def hoist(s, records, rng, carriers, offsets=(0.0, 0.10, 0.20, 0.25, 0.30), guide_deg=None, scale=1.0):
    """Guided trunk hoist (aft down, +X up): the carrier hangs head up on a line from a head at the trunk's forward end, its centreline offset e
    toward GUIDE_DEG (across from the ladder at trunk_ladder_deg) and held by shoes on a guide rail there; an attendant climbs the trunk ladder
    beside it. For each offset: the carrier's least clearance against the built trunk over its travel, and the least gap between the carrier and
    the attendant (trunk_climber's figure moved rung by rung)."""
    import numpy as np
    import crew_transfer as ct
    import human_entry as he
    L = he.trunk_ladder(s); guide = L['th']+math.pi if guide_deg is None else math.radians(guide_deg); tr = s['crew_transfer']['trunk_clear_radius_m']
    climber = he.trunk_climber(s); x_feet = climber['feet_x']
    pts = [(x, 0.0, 0.0) for x in np.linspace(81.6, 102.45, 60)]
    walls = Walls(records, pts)
    rails = [q for q in records if q['name'].startswith('Crew_Trunk_Handrail')]; rail_walls = Walls(rails, pts) if rails else None
    out = dict(guide_deg=round(math.degrees(guide) % 360, 1), ladder_deg=round(math.degrees(L['th']) % 360, 1), scale=scale,
               handrail_deg=sorted({round(math.degrees(math.atan2(.5*(q['lo'][2]+q['hi'][2]), .5*(q['lo'][1]+q['hi'][1]))) % 360, 0) for q in rails}),
                                           ladder_x=[round(L['floor'], 3), round(L['top'], 3)], offsets={})
    spans = he.clear_spans(s, tr-.08, guide, L['floor'], 102.4)
    out['guide_rail_clear_spans_x'] = [[round(a, 2), round(b, 2)] for a, b in spans]
    x_lo, x_hi = 83.6, 102.4-HOIST_HEAD_M   # from just above ring A's spine port mouth to below the hoist head at the trunk's forward end
    for cid in carriers:
        car = scaled(CARRIERS[cid], scale); Lc = length(car); res = {}
        n_g = np.array(ct.radial(0.0, 1.0, guide))
        for e in offsets:
            off = n_g*e; d = np.array((-1.0, 0, 0)); u, w0, t0 = frame(d, 0.0)
            rolls = {'thin side to the ladder': math.atan2(float(np.dot(n_g, w0)), float(-np.dot(n_g, t0))),
                     'flat to the ladder': math.atan2(float(np.dot(n_g, t0)), float(np.dot(n_g, w0)))}
            for rname, roll in rolls.items():
                worst = (math.inf,); gap = math.inf; rail_gap = (math.inf, None, None)
                for x_top in np.arange(x_lo+Lc, x_hi+1e-9, .10):
                    m = margin(walls, car, np.array((x_top, 0, 0))+off, d, roll)
                    if m[0] < worst[0]:
                        worst = (round(m[0], 3), m[1], round(float(x_top), 2))
                    if rail_walls is not None:
                        mr = margin(rail_walls, car, np.array((x_top, 0, 0))+off, d, roll, cap=.30)
                        if mr[0] < rail_gap[0]:
                            rail_gap = (round(mr[0], 3), mr[1], round(float(x_top), 2))
                head = np.array((90.0+Lc/2, 0, 0))+off
                bx = boxes(car, head, d, roll) if car['shape'] == 'box' else None
                for dxr in np.arange(-2.5, 2.6, .1):      # the attendant on the ladder at every height beside the carrier
                    for name, (a, b), r in climber['rods']:
                        for k in range(9):
                            p = np.add(a, np.subtract(b, a)*k/8)+np.array((90.0-x_feet+dxr, 0, 0))
                            if bx:
                                dd = box_point_dist(bx, p)
                            else:
                                q = np.subtract(p, head); tt = min(max(float(np.dot(q, d)), car['radius']), Lc-car['radius'])
                                dd = float(np.linalg.norm(q-d*tt))-car['radius']
                            gap = min(gap, dd-r)
                res[f'e_{e:.2f}_{rname}'] = dict(offset_m=e, roll=rname, carrier_least_m=worst[0], status=status(worst[0]), nearest=worst[1],
                                                 at_head_x=worst[2], attendant_gap_m=round(gap, 3), attendant_status=status(gap),
                                                 handrail_gap_m=None if rail_gap[0] == math.inf else rail_gap[0], handrail_nearest=rail_gap[1], handrail_at_head_x=rail_gap[2])
                print('WF_HUM003_HOIST', cid, e, rname, worst, round(gap, 3), flush=True)
        out['offsets'][cid] = res
    return out


# ------------------------------------------------------------------------------------------------------------------------------------
# collect (system python): results + pure geometry -> references/p1_hum003.json

def boundary_costs(s):
    """What each candidate opening does to a pressure boundary and the spine core, from the shared dimensions (text for the owner, never an
    approved change): clear area and the closure's pressure load at the spec cabin pressure, the share of the 1.9 m spine core it cuts at its
    station, and, for ring B's 1.10 m port, the trunk ladder top for each ladder angle with the refuge entry where it is or turned."""
    import copy
    import human_entry as he
    from spec import load
    p_kpa = s['habitat']['atmosphere']['cabin_pressure_kpa']
    rc = s['prototype']['spine_core_radius_m']; wall = s['crew_transfer']['passage_wall_m']
    def arc(half):
        return round(math.degrees(2*math.asin(min(1.0, (half+wall)/rc))), 1)
    out = dict(cabin_pressure_kpa=p_kpa, openings={})
    def add(name, area, core_arc_deg, core_cut_len_m, note):
        out['openings'][name] = dict(clear_area_m2=round(area, 3), closure_load_kn=round(area*p_kpa, 1), spine_core_arc_deg=core_arc_deg,
                                     core_cut_length_x_m=core_cut_len_m, note=note)
    add('refuge_port_0.90_round (built)', math.pi*.45**2, arc(.45), round(.9+2*wall, 2), 'no closure modelled (OD-011 OPEN)')
    for W in (0.75, 0.90, 1.00):
        add(f'refuge_axial_slot_{W:.2f}x2.30', W*2.30, arc(W/2), round(2.30+2*wall, 2),
            'rectangular hatch along the trunk; spine core cut over 2.40 m; refuge hoop rails and trunk frames 9/10 interrupted over the slot')
    for D, e in ((0.90, 0.35), (0.90, 0.60), (1.10, 0.60)):
        lo, hi = e-D/2, e+D/2            # duct band across the core circle at the station, on one side of the radial
        a0 = math.degrees(math.acos(min(1.0, max(-1.0, hi/rc)))); a1 = math.degrees(math.acos(min(1.0, max(-1.0, lo/rc))))
        add(f'refuge_tangential_D{D:.2f}_e{e:.2f}', math.pi*(D/2)**2, round(a1-a0, 1), round(D+2*wall, 2),
            'round hatch on a chord; the hole in the trunk wall and spine core is oblique (elongated)')
    out['openings']['ringB_port_1.10'] = dict(clear_area_m2=round(math.pi*.55**2, 3), closure_load_kn=round(math.pi*.55**2*p_kpa, 1),
                                               built_area_m2=round(math.pi*.45**2, 3), spine_core_arc_deg=arc(.55), built_core_arc_deg=arc(.45),
                                               note='spine-port gate, drum doors, tube hatches and necks of ring B all grow to 1.10 m (Q46 closures resized)')
    w = RUNS/'ringB_port_1.10/work'
    if w.exists():
        sb = load(w)[0]; orig = he.openings(sb); table = {}
        for ref_deg, half in ((0, .5), (10, .5), (20, .5), (20, .55), (30, .55)):
            ops = [(n, x, (math.radians(ref_deg) if n == 'Crew_Refuge_Port' else th), (half if n == 'Crew_Refuge_Port' else r)) for n, x, th, r in orig]
            keep = he.openings; he.openings = lambda _s, ops=ops: ops
            row = {}
            for deg in range(280, 335, 5):
                sc = copy.deepcopy(sb); sc['human_entry']['trunk_ladder_deg'] = deg; row[deg] = round(he.trunk_ladder(sc)['top'], 2)
            he.openings = keep; table[f'refuge entry at {ref_deg} deg, half-width {half:.2f} m'] = row
        out['ringB_1.10_trunk_ladder_top_x_by_ladder_deg'] = table
    orig = he.openings(s); keep = he.openings; row = {}
    for half in (.425, .50, .55):                 # the built ladder (285 deg) against a refuge entry of this half-width on the refuge radial
        ops = [(n, x, th, (half if n == 'Crew_Refuge_Port' else r)) for n, x, th, r in orig]; he.openings = lambda _s, ops=ops: ops
        row[f'half-width {half:.3f} m'] = round(he.trunk_ladder(s)['top'], 2)
    he.openings = keep; out['built_trunk_ladder_top_x_by_refuge_entry'] = row
    L = he.trunk_ladder(s)
    out['guide_rail'] = {f'{deg} deg': [[round(a, 2), round(b, 2)] for a, b in he.clear_spans(s, s['crew_transfer']['trunk_clear_radius_m']-.08, math.radians(deg), L['floor'], 102.4)]
                         for deg in (60, 105, 120, 150)}
    return out


def collect():
    import casualty_whatif as cw
    import human_entry as he
    import habitat_ring as hr
    from spec import load
    s = load(ROOT)[0]; res = dict(study='HUM-003 casualty routes (S&E 15!A126, owner answer 2026-10-11)',
                                   status='NONCANON CANDIDATE STUDIES / NO HULL RELEASE; PROTOTYPE envelopes; gas, mass and medical numbers OPEN',
                                   study_margin_m=STUDY_MARGIN_M, cap_m=CAP_M, carriers=CARRIERS,
                                   staff=dict(radius_m=STAFF_R_M, reach_m=STAFF_REACH_M, dwell_body_m=STAFF_BODY_M), variants={})
    for d in sorted(RUNS.glob('*/hum003_rings.json')):
        r = json.loads(d.read_text()); work = Path(r['root'])
        res['variants'][r['tag']] = dict(r, costs=cw.costs(work))
    loc = RUNS/'local/hum003_local.json'
    if loc.exists():
        res['local'] = json.loads(loc.read_text())
    w = hr.omega(s); g = hr.G0
    res['station_effects'] = dict(
        spin_rpm=round(w*60/math.tau, 2), coriolis_g_per_m_s=round(2*w/g, 3), ladder_push={j: he.ladder_push(s, j) for j in (1, 2)},
        floor_gravity_g=round(w*w*hr.floor(s)/g, 3), thrust_g=1.5, thrust_load_n_per_kg=round(1.5*g, 2),
        notes=['the trunk and the despun drums are stationary: 0 g with the rings spinning or stopped (drive off)',
               'in a crew tube spin gravity grows from ~0.10 g at the top of the run to ~0.45 g at the tube tip; moving along it at v adds 2 omega v '
               'across the tube (outbound: antispinward)', 'aft down at 1.5 g every vertical leg is a shaft; static line load is 14.7 N per kg '
               'carried (patient, carrier, kit and any rider; masses OPEN)'])
    res['pressure_and_structure'] = boundary_costs(s)
    OUT_JSON.write_text(json.dumps(res, indent=1, default=str)+'\n')
    print('wrote', OUT_JSON)


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    a = argparse.ArgumentParser(); a.add_argument('mode', choices=('rings', 'local', 'collect'))
    a.add_argument('--root', type=Path, default=ROOT); a.add_argument('--tag', default='built'); a.add_argument('--routes', default='')
    a.add_argument('--carriers', default='ACK'); a.add_argument('--dwell', action='store_true')
    args = a.parse_args(argv)
    if args.mode == 'rings':
        run_rings(args)
    elif args.mode == 'local':
        run_local(args)
    else:
        collect()


if __name__ == '__main__':
    main()
