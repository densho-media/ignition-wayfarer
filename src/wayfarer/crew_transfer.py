"""P1-001 crew transfer: a PROTOTYPE route from the stationary structure to every ring sector with the rings rotating and stopped.

Canon: a dedicated rotary vestibule/hub per rotor plane (12_HABITAT_LAYOUT A11, 15_MODEL_INTERFACES I5, WORKING); one refuge
near the transfer hub, reachable with the rings rotating or stopped (A8, I4, WORKING); primary EVA access and both docking
ports on the stationary central structure (14_HULL_SERVICE). The rings stay at full size and no room turns (08 A47/A55,
MEC-011). The route itself, the vestibule, hatches, rotary pressure seals, tube telescoping and pressurization are OPEN
(OD-002; habitat.transfer.crew_path).

Everything here comes from the PROTOTYPE [crew_transfer] table and keeps the P1-008 hub unchanged: a crew trunk inside the
spine bore, a hatch-isolated rotary vestibule aft of each rotor's ring-stop locks (tied to the drum by struts between the
lock pins), spine ports at the index angles and one crew tube per ring sector, turning in two mitered elbows near the hub and
running out beside its crew spoke, bracketed to both rails, to the sector's overhead hatch at the sector centre. One route serves
both habitat states.

Clearances are sampled distances between the parts and every obstacle. With the rings ROTATING, parts of different frames are
compared by their swept (x, r) extents; STOPPED_LOCKED the rotors sit at the index angle and are compared exactly.
Coordinates: x along +X; u = x - rotor centre; angles about +X from +Y; sector frame as in [interior] (+X along the ring axis,
aft bulkhead -X, +Y toward the floor). Standard library only.
"""
from pathlib import Path
import copy
import hashlib
import json
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import habitat_ring
import layout
import hull_geometry
import power_storage
import rotor_interface as ri

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'references/p1_crew_transfer.json'
SUBSYSTEM = 'WF_CREW_TRANSFER.blend'
STATES = ri.STATES
FITTINGS = ('AIRLOCK_EVA', 'DOCK_PRIMARY', 'DOCK_SERVICE')
STEP = 0.05     # sampling step along members and over surfaces
AROUND = 72     # angular samples on rings and cylinders
AROUND_TUBE = 24  # angular samples on flat-ended tubes


def radial(x, r, a):
    return (x, r*math.cos(a), r*math.sin(a))


def add(a, b, k=1.0):
    return tuple(p+k*q for p, q in zip(a, b))


def sub(a, b):
    return tuple(p-q for p, q in zip(a, b))


def dot(a, b):
    return sum(p*q for p, q in zip(a, b))


def to_world(v, x0, angle):
    """Rotor-local point -> vehicle frame for a rotor at x0 turned by `angle` about +X."""
    c, s_ = math.cos(angle), math.sin(angle)
    return (x0+v[0], v[1]*c-v[2]*s_, v[1]*s_+v[2]*c)


# ---------- primitives: distance (solid, 0 inside), surface samples and swept (x, r) bounds ---------------------------

def rod(name, points, radius, **kw):
    return dict(shape='rod', name=name, points=[tuple(p) for p in points], radius=radius, **kw)


def ring(name, x0, x1, r0, r1, sector=None, **kw):
    return dict(shape='ring', name=name, x0=x0, x1=x1, r0=r0, r1=r1, sector=sector, **kw)


def cyl(name, a, b, radius, **kw):
    return dict(shape='cyl', name=name, a=tuple(a), b=tuple(b), radius=radius, **kw)


def box(name, pack, **kw):
    return dict(shape='box', name=name, pack=pack, **kw)


def torus(name, centre, normal, major, minor, **kw):
    """Circular band: centre, unit normal, band radius and tube radius."""
    return dict(shape='torus', name=name, centre=tuple(centre), normal=tuple(normal), major=major, radius=minor, **kw)


def seg_dist(p, a, b):
    ab = sub(b, a); L2 = dot(ab, ab)
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, dot(sub(p, a), ab)/L2))
    return math.dist(p, add(a, ab, t))


def seg_solid(p, a, b, radius, flat_a, flat_b):
    """Distance from p to a tube around segment a-b; flat (open-tube) or rounded at each end."""
    ab = sub(b, a); L = math.sqrt(dot(ab, ab)); u = tuple(c/L for c in ab); t = dot(sub(p, a), u)
    q = math.dist(p, add(a, u, t))
    if t < 0 and not flat_a:
        return math.dist(p, a)-radius
    if t > L and not flat_b:
        return math.dist(p, b)-radius
    return math.hypot(max(0.0, -t, t-L), max(0.0, q-radius)) if (t < 0 or t > L or q > radius) else q-radius


def angle_diff(a, b):
    return abs((a-b+math.pi) % math.tau-math.pi)


def distance(o, p):
    """Distance from point p to the solid of primitive o (vehicle or rotor-local frame, whichever both use)."""
    if o['shape'] == 'rod':
        pts = o['points']; n = len(pts)-1; flat = o.get('flat', False)
        return min(seg_solid(p, pts[i], pts[i+1], o['radius'], flat and i == 0, flat and i == n-1) for i in range(n))
    if o['shape'] == 'cyl':
        ax = sub(o['b'], o['a']); L = math.sqrt(dot(ax, ax)); u = tuple(c/L for c in ax); t = dot(sub(p, o['a']), u)
        q = math.dist(p, add(o['a'], u, t))
        return math.hypot(max(0.0, -t, t-L), max(0.0, q-o['radius']))
    if o['shape'] == 'box':
        return power_storage.point_box(p, o['pack'])
    if o['shape'] == 'torus':
        d = sub(p, o['centre']); h = dot(d, o['normal']); rho = math.sqrt(max(0.0, dot(d, d)-h*h))
        return math.hypot(rho-o['major'], h)-o['radius']
    x, r, th = p[0], math.hypot(p[1], p[2]), math.atan2(p[2], p[1])
    dx = max(o['x0']-x, 0.0, x-o['x1'])
    lo, hi = o['sector'] or (0.0, math.tau)
    if o['sector'] is None or angle_diff(th, (lo+hi)/2) <= (hi-lo)/2:
        return math.hypot(dx, max(o['r0']-r, 0.0, r-o['r1']))
    # Outside the sector: nearest of its two flat edges (rectangles in the half-planes at lo and hi).
    best = math.inf
    for t in (lo, hi):
        d = angle_diff(th, t); rho, h = r*math.cos(d), r*math.sin(d)
        best = min(best, math.sqrt(dx*dx+max(o['r0']-rho, 0.0, rho-o['r1'])**2+h*h))
    return best


def samples(o):
    """(point, radius) pairs covering the primitive: axis points for rods, surface points for solids (cached on the dict)."""
    if '_samples' not in o:
        o['_samples'] = _samples(o)
    return o['_samples']


def frame(u):
    """Two unit vectors perpendicular to unit vector u."""
    e1 = (1.0, 0.0, 0.0) if abs(u[0]) < .9 else (0.0, 1.0, 0.0)
    v = sub(e1, tuple(dot(e1, u)*c for c in u)); nv = math.sqrt(dot(v, v)); v = tuple(c/nv for c in v)
    return v, (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])


def _samples(o):
    if o['shape'] == 'torus':
        v, w = frame(o['normal']); n = max(8, math.ceil(math.tau*o['major']/STEP))
        return [(add(o['centre'], add(tuple(math.cos(math.tau*k/n)*c for c in v), w, math.sin(math.tau*k/n)), o['major']), o['radius']) for k in range(n)]
    if o['shape'] == 'rod' and o.get('flat'):
        # Open-ended tube: points on its wall and on both end discs.
        out = []; pts = o['points']; R = o['radius']
        for i, (a, b) in enumerate(zip(pts, pts[1:])):
            ab = sub(b, a); L = math.sqrt(dot(ab, ab)); u = tuple(c/L for c in ab); v, w = frame(u)
            n = max(1, math.ceil(L/STEP))
            rims = [add(tuple(math.cos(math.tau*k/AROUND_TUBE)*c for c in v), w, math.sin(math.tau*k/AROUND_TUBE)) for k in range(AROUND_TUBE)]
            out += [(add(add(a, u, L*m/n), rim, R), 0.0) for m in range(n+1) for rim in rims]
            ends = ([a] if i == 0 else [])+([b] if i == len(pts)-2 else [])
            out += [(add(e, rim, R*m/4), 0.0) for e in ends for rim in rims for m in range(4)]
        return out
    if o['shape'] == 'rod':
        out = []
        for a, b in zip(o['points'], o['points'][1:]):
            n = max(1, math.ceil(math.dist(a, b)/STEP))
            out += [(add(a, sub(b, a), k/n), o['radius']) for k in range(n+1)]
        return out
    if o['shape'] == 'box':
        c = o['pack']['corners']; out = []
        for i in range(len(c)):
            for j in range(i+1, len(c)):
                n = max(1, math.ceil(math.dist(c[i], c[j])/STEP))
                out += [(add(c[i], sub(c[j], c[i]), k/n), 0.0) for k in range(n+1)]
        return out
    if o['shape'] == 'cyl':
        ax = sub(o['b'], o['a']); L = math.sqrt(dot(ax, ax)); u = tuple(c/L for c in ax)
        e1 = (1.0, 0.0, 0.0) if abs(u[0]) < .9 else (0.0, 1.0, 0.0)
        v = sub(e1, tuple(dot(e1, u)*c for c in u)); nv = math.sqrt(dot(v, v)); v = tuple(c/nv for c in v)
        w = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        out = []
        nl, nr = max(1, math.ceil(L/STEP)), max(1, math.ceil(o['radius']/STEP))
        for k in range(AROUND):
            t = math.tau*k/AROUND; rim = add(tuple(math.cos(t)*c for c in v), w, math.sin(t))
            out += [(add(add(o['a'], u, L*i/nl), rim, o['radius']), 0.0) for i in range(nl+1)]
            out += [(add(end, rim, o['radius']*i/nr), 0.0) for end in (o['a'], o['b']) for i in range(nr+1)]
        return out
    lo, hi = o['sector'] or (0.0, math.tau)
    nx, nr = max(1, math.ceil((o['x1']-o['x0'])/STEP)), max(1, math.ceil((o['r1']-o['r0'])/STEP))
    prof = [(o['x0']+(o['x1']-o['x0'])*i/nx, r) for i in range(nx+1) for r in (o['r0'], o['r1'])]
    prof += [(x, o['r0']+(o['r1']-o['r0'])*i/nr) for i in range(nr+1) for x in (o['x0'], o['x1'])]
    n = max(2, math.ceil(AROUND*(hi-lo)/math.tau))
    return [(radial(x, r, lo+(hi-lo)*k/n), 0.0) for x, r in prof for k in range(n+1)]


def axis_distance(a, b):
    """Smallest distance of segment a-b from the +X axis."""
    return seg_dist((0.0, 0.0), a[1:], b[1:]) if a[1:] != b[1:] else math.hypot(*a[1:])


def swept(o):
    """(x0, x1, r0, r1) bounds of the solid swept one full turn about +X (conservative, cached)."""
    if '_swept' not in o:
        o['_swept'] = _swept(o)
    return o['_swept']


def _swept(o):
    if o['shape'] == 'ring':
        return (o['x0'], o['x1'], o['r0'], o['r1'])
    if o['shape'] == 'rod':
        pts, pad = o['points'], o['radius']
        near = min(axis_distance(a, b) for a, b in zip(pts, pts[1:]))
        if o.get('flat'):
            pp = [q for q, _ in samples(o)]; rs = [math.hypot(*q[1:]) for q in pp]
            return (min(q[0] for q in pp), max(q[0] for q in pp), min(rs), max(rs))
        return (min(p[0] for p in pts)-pad, max(p[0] for p in pts)+pad, max(0.0, near-pad), max(math.hypot(*p[1:]) for p in pts)+pad)
    pad = o['radius'] if o['shape'] == 'torus' else 0.0
    pts = [p for p, _ in samples(o)]; rs = [math.hypot(p[1], p[2]) for p in pts]
    return (min(p[0] for p in pts)-pad, max(p[0] for p in pts)+pad, max(0.0, min(rs)-pad), max(rs)+pad)


def xr_gap(p, radius, b):
    x, r = p[0], math.hypot(p[1], p[2])
    return math.hypot(max(b[0]-x, 0.0, x-b[1]), max(b[2]-r, 0.0, r-b[3]))-radius


def profile(o):
    """(x, r, radius) points of the solid swept about +X, de-duplicated on a 1 cm grid (cached)."""
    if '_profile' not in o:
        seen = {}
        for pt, rad in samples(o):
            key = (round(pt[0], 2), round(math.hypot(pt[1], pt[2]), 2), rad)
            seen[key] = key
        o['_profile'] = list(seen)
    return o['_profile']


def swept_gap(a, b):
    """Clearance between the bodies of revolution swept by a and b about +X."""
    ba, bb = swept(a), swept(b)
    coarse = math.hypot(max(0.0, bb[0]-ba[1], ba[0]-bb[1]), max(0.0, bb[2]-ba[3], ba[2]-bb[3]))
    if coarse > 1.0:
        return coarse
    if b['shape'] == 'ring':
        return min(math.hypot(max(bb[0]-x, 0.0, x-bb[1]), max(bb[2]-r, 0.0, r-bb[3]))-rad for x, r, rad in profile(a))
    if a['shape'] == 'ring':
        return swept_gap(b, a)
    # Only points near the other body matter: filter both profiles to the overlap window first.
    win = lambda pts, bx: [q for q in pts if bx[0]-1 <= q[0] <= bx[1]+1 and bx[2]-1 <= q[1] <= bx[3]+1]
    pa, pb = win(profile(a), bb), win(profile(b), ba)
    return min((math.hypot(x-y, r-q)-ra-rb for x, r, ra in pa for y, q, rb in pb), default=coarse)


def bounds(o):
    """Axis-aligned bounds, analytic where possible."""
    if o['shape'] == 'ring':
        return [o['x0'], -o['r1'], -o['r1']], [o['x1'], o['r1'], o['r1']]
    if o['shape'] == 'box':
        c = o['pack']['corners']
        return [min(p[i] for p in c) for i in range(3)], [max(p[i] for p in c) for i in range(3)]
    if o['shape'] == 'torus':
        pts = [q for q, _ in samples(o)]
        return [min(q[i] for q in pts)-o['radius'] for i in range(3)], [max(q[i] for q in pts)+o['radius'] for i in range(3)]
    pts, pad = (o['points'], o['radius']) if o['shape'] == 'rod' else ((o['a'], o['b']), o['radius'])
    return [min(p[i] for p in pts)-pad for i in range(3)], [max(p[i] for p in pts)+pad for i in range(3)]


def posed(o, x0, angle):
    """A rotor-local primitive moved into the vehicle frame (rings stay axisymmetric, sectors turn)."""
    o = {k: v for k, v in o.items() if k not in ('_samples', '_profile', '_swept')}
    if o['shape'] == 'torus':
        n = to_world(o['normal'], 0.0, angle)
        return {**o, 'centre': to_world(o['centre'], x0, angle), 'normal': n}
    if o['shape'] == 'ring':
        return {**o, 'x0': o['x0']+x0, 'x1': o['x1']+x0, 'sector': None if o['sector'] is None else (o['sector'][0]+angle, o['sector'][1]+angle)}
    if o['shape'] == 'rod':
        return {**o, 'points': [to_world(p, x0, angle) for p in o['points']]}
    return {**o, 'a': to_world(o['a'], x0, angle), 'b': to_world(o['b'], x0, angle)}


# ---------- PROTOTYPE layout ----------------------------------------------------------------------------------------

def outer(s):
    """Outer radius of a crew passage: clear radius plus wall."""
    c = s['crew_transfer']
    return c['passage_clear_radius_m']+c['passage_wall_m']


def vestibule(s, j):
    """Stations of rotor j's rotary vestibule (rotor-local u): span u0..u1, transit chamber cu0..cu1 between the guard rings, radii, spine port
    and outer hatch stations, the spine port's outer and clear radius and the sectors that get a spine port. HUM-001 zone 3: the human-entry rotors
    (human_entry.vestibule_rotors) are hollow, each with one spine port whose annular chamber joins it to every sector hatch. The chamber holds the
    port's outer diameter plus a seal allowance at each end and grows aft from the lock-pin bound (vestibule_u_m[1]); its clear depth holds the
    suited envelope between handrails on both walls. The port carries the 1.6 m docking passage unless the other rotor's cartridge withdrawal
    paths end aft of this rotor: then it is the largest (on a 0.05 m grid) whose vestibule, guard rings included, stays one mechanical clearance
    clear of them (ring B: hub 1's forward cartridges). The outer hatches take the port's size (window). The other rotors keep the P1-001 proxy."""
    c, p, h = s['crew_transfer'], s['prototype'], s['human_entry']; g = c['vestibule_guard_m']; u1 = c['vestibule_u_m'][1]
    if j not in h['vestibule_rotors']:
        u0 = c['vestibule_u_m'][0]
        return dict(human=False, u0=u0, u1=u1, cu0=u0+g, cu1=u1-g, r0=c['vestibule_inner_radius_m'], clear=None, r1=c['vestibule_outer_radius_m'],
                    port_u=c['spine_port_u_m'], hatch_u=c['vestibule_hatch_u_m'], port_r=outer(s), port_clear=None, window=None, ports=[k for k, _ in sectors(s)])
    x = next(r['x'] for r in ri.rotors(s) if r['index'] == j); ends = [e for e in (ri.withdrawal_extent(s, r['index'])[1] for r in ri.rotors(s) if r['index'] != j) if e <= x]
    m = h['mannequin']; cu1 = u1-g; wall = c['passage_wall_m']; seal = c['seal_allowance_m']; pc = p['dock_clear_radius_m']; window = None
    if ends:
        window = (max(ends)+p['mechanical_clearance_m']-x, u1)       # rotor-local u the vestibule may span
        pc = min(pc, math.floor(((cu1-g-window[0])/2-seal-wall)/0.05+1e-9)*0.05)
    # HUM-002 what-ifs only: [human_entry.study] is set in disposable study workspaces (studies/casualty_whatif.py), never in the spec.
    w = h.get('study', {}); pc = w.get('port_clear_radius_m', {}).get(str(j), pc)
    cu0 = cu1-2*(pc+wall+seal); r0 = c['vestibule_inner_radius_m']
    depth = math.ceil((m['suited_envelope_diameter_m']+2*(h['handrail_standoff_m']+2*h['handrail_radius_m']))/0.05-1e-9)*0.05
    depth += w.get('chamber_depth_extra_m', {}).get(str(j), 0.0)
    return dict(human=True, u0=cu0-g, u1=u1, cu0=cu0, cu1=cu1, r0=r0, clear=r0+depth, r1=r0+depth+h['chamber_wall_m'], port_u=(cu0+cu1)/2,
                hatch_u=(cu0+cu1)/2, port_r=pc+wall, port_clear=pc, window=window, ports=[h['vestibule_port_sectors'][h['vestibule_rotors'].index(j)]])


def sector_axes(s, a):
    """Rotor-local centre and axes of the ring sector at local angle a, as revision.habitat places it (sectors never turn in the ring)."""
    rad = (0.0, math.cos(a), math.sin(a)); tan = (0.0, -math.sin(a), math.cos(a))
    return radial(0.0, habitat_ring.floor(s), a), (1.0, 0.0, 0.0), rad, tan


def sector_point(s, a, local):
    c, X, Y, Z = sector_axes(s, a)
    return add(add(add(c, X, local[0]), Y, local[1]), Z, local[2])


def sector_hatches(s):
    """The sector hatches in the sector frame: the overhead hatch at the pressure wall (the crew tube lands there) and on the overhead
    panel (the interior interface). HUM-001 zone 4: on the ring plane, off the spoke's rail plane by overhead_hatch_z_m."""
    import habitat_interior
    c, r = s['crew_transfer'], s['habitat_ring']
    return {'overhead_wall': (c['overhead_hatch_x_m'], r['sector_inner_radius_m']-habitat_ring.floor(s), c['overhead_hatch_z_m']),
            'overhead_panel': habitat_interior.hatch(s)}


def tube_radii(s, j):
    """Outer and clear radius of rotor j's crew tubes: HUM-001 zone 4 carries the 1.6 m passage through the spokes of the rotors in
    human_entry.tube_rotors (clear radius dock_clear_radius_m, wall passage_wall_m; on ring B above a neck, tube_neck); the others keep the
    solid 0.80 m proxy (clear None)."""
    p = s['prototype']
    if j in s['human_entry']['tube_rotors']:
        return p['dock_clear_radius_m']+s['crew_transfer']['passage_wall_m'], p['dock_clear_radius_m']
    return outer(s), None


def transfer_stack(s, j):
    """Q46 / MEC-019 (PROTOTYPE stack): radii outward from the drum wall of human-entry rotor j. The vestibule is a despun transfer drum: its
    doors slide round the outside of its wall (`door`), a running gap separates it from the ring side, whose crew-tube collars start at
    `ring_face` and carry the tube hatches (`hatch`); each closure rides a track gap off the surface it seals on."""
    c = s['crew_transfer']; v = vestibule(s, j); t, g = c['transfer_closure_thickness_m'], c['transfer_track_gap_m']
    door = (v['r1']+g, v['r1']+g+t); face = door[1]+c['transfer_running_gap_m']
    return dict(wall=v['r1'], door=door, ring_face=face, hatch=(face+g, face+g+t))


def tube_neck(s, j):
    """HUM-001 zone 4 at ring B: where a hollow tube is wider than its vestibule's outer hatch (the window-limited 0.90 m hatch; the tube's 1.7 m
    outer diameter would overhang the 1.60 m vestibule), the tube's root is a bulkhead of the passage wall, opened by a neck of the hatch's clear
    radius and the passage wall. Since Q46 the neck starts at the ring side's face (`root`, transfer_stack), across the running gap from the
    despun drum, and holds the tube hatch; the bulkhead's chamber-side face (`base`, from the ship axis) sits a track gap above the hatch, on the
    0.05 m grid. None where the tube is a proxy or the hatch takes the tube's size (ring A)."""
    ro, rc = tube_radii(s, j); v = vestibule(s, j)
    if rc is None or v['port_clear'] >= rc-1e-9:
        return None
    w = s['crew_transfer']['passage_wall_m']; pc = v['port_clear']; st = transfer_stack(s, j)
    top = st['hatch'][1]+s['crew_transfer']['transfer_track_gap_m']
    return dict(clear=pc, outer=pc+w, wall=w, base=math.ceil(top/0.05-1e-9)*0.05, root=st['ring_face'])


def tube_floor(s, j):
    """Radius (from the ship axis, along the tube's root segment) where rotor j's crew-tube bore begins: on a hollow tube the ring side's face
    across the running gap from the drum (transfer_stack), on a necked tube the bulkhead's tube-side face, on a proxy the vestibule wall."""
    n = tube_neck(s, j)
    if n:
        return n['base']+n['wall']
    return transfer_stack(s, j)['ring_face'] if vestibule(s, j)['human'] and tube_radii(s, j)[1] else vestibule(s, j)['r1']


def tube_path(s, j, la):
    """Axis of rotor j's crew tube to the sector at rotor-local angle la: root on the ring side's face across the running gap from the despun
    drum (tube_floor; on a necked tube the bulkhead, tube_neck; on a proxy the vestibule wall), a radial collar one tube radius beyond the drum wall (or the bulkhead's tube side), a 45 deg side leg that advances spoke_side_advance_m while moving out
    to the hatch's tangential offset, a forward leg to the hatch station at the bend radius, and the radial run beside the crew spoke to the
    sector's overhead wall."""
    c = s['crew_transfer']; v = vestibule(s, j); ro, _ = tube_radii(s, j); hat = sector_hatches(s)['overhead_wall']; x_h, _, z_h = hat
    at = lambda u, rho, z: sector_point(s, la, (u, rho-habitat_ring.floor(s), z))
    u0, a = v['hatch_u'], c['spoke_side_advance_m']; neck = tube_neck(s, j)
    # The collar ends one tube radius beyond the drum wall (or the bulkhead's tube side), where the elbows have always been: Q46 shortened it
    # at the root, not at the elbow, so the elbows keep their fit inside the body.
    collar = (neck['base']+neck['wall'] if neck else v['r1'])+ro
    root = neck['base'] if neck else tube_floor(s, j)
    return [at(u0, root, 0.0), at(u0, collar, 0.0), at(u0+a, collar+math.hypot(a, z_h), z_h), at(x_h, c['coast_tube_bend_radius_m'], z_h), sector_point(s, la, hat)]


def closures(s, j):
    """Q46 / MEC-019 closures of human-entry rotor j (PROTOTYPE shapes; seals, drives and latches OPEN), each a curved plate (ri.solid ring
    segment x0..x1, r0..r1, t0..t1) given closed, with how it opens:
    - PORT_GATE (stationary side, vehicle frame): in the spine shell between the trunk and the spine core, across the spine port's bore; it
      slides forward (`slide`, +X) by twice its half-length plus port_gate_park_margin_m. Saved closed.
    - DRUM_DOOR_k (the despun drum, rotor-local at the index): on the drum wall's outer face over each crew-tube opening; it slides round the
      drum by `turn` (its own angular width plus transfer_park_margin_deg).
    - TUBE_HATCH_k (ring side, rotor-local): across the collar (or neck) bore just above the ring side's face; it slides round the ring the
      same way.
    Every plate laps its clear opening by transfer_closure_lap_m."""
    c = s['crew_transfer']; v = vestibule(s, j); st = transfer_stack(s, j); rot = next(r for r in ri.rotors(s) if r['index'] == j)
    lap, t, g = c['transfer_closure_lap_m'], c['transfer_closure_thickness_m'], c['transfer_track_gap_m']; m = math.radians(c['transfer_park_margin_deg'])
    neck = tube_neck(s, j); tc = neck['clear'] if neck else tube_radii(s, j)[1]; la = dict(sectors(s)); out = []
    to = c['trunk_clear_radius_m']+c['passage_wall_m']; core = layout.spine_core(s)[2]; mid = (to+core)/2
    pc = v['port_clear']; half = pc+lap; r0, r1 = mid-t/2, mid+t/2; th = rot['phase']+la[v['ports'][0]]; b = math.asin(min(1.0, half/r0)); xp = rot['x']+v['port_u']
    out.append(dict(name=f'Crew_Port_{j}_{v["ports"][0]}_Gate', kind='PORT_GATE', side='STATIONARY', rotor=j, x0=xp-half, x1=xp+half, r0=r0, r1=r1,
                    t0=th-b, t1=th+b, slide=2*half+c['port_gate_park_margin_m'], turn=0.0, angle=th, clear=pc))
    half = tc+lap
    for kind, side, (q0, q1) in (('DRUM_DOOR', 'DRUM', st['door']), ('TUBE_HATCH', 'ROTATING', st['hatch'])):
        b = math.asin(min(1.0, half/q0))
        for k, a in la.items():
            name = f'Crew_Vestibule_{j}_Door_{k}' if kind == 'DRUM_DOOR' else f'Crew_Tube_{j}_{k}_Hatch'
            out.append(dict(name=name, kind=kind, side=side, rotor=j, sector=k, x0=v['hatch_u']-half, x1=v['hatch_u']+half, r0=q0, r1=q1,
                            t0=a-b, t1=a+b, slide=0.0, turn=2*b+m, angle=a, clear=tc))
    return out


def unit(v):
    n = math.sqrt(dot(v, v))
    return tuple(x/n for x in v)


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def turn(v, a, b):
    """v rotated by the minimal rotation that takes unit a to unit b (Rodrigues)."""
    k = cross(a, b); sn = math.sqrt(dot(k, k)); cs = dot(a, b)
    if sn < 1e-12:
        return v
    k = tuple(x/sn for x in k); kv = cross(k, v); kd = dot(k, v)
    return tuple(v[i]*cs+kv[i]*sn+k[i]*kd*(1-cs) for i in range(3))


def tube_frames(points, normal):
    """Mitered sweep frames of a tube axis: per segment its direction and transported normals (n1, n2), with n1 on the last segment along
    `normal` made square to it; per joint the miter plane bisecting the two segments. A ring point at angle phi from n1 is projected onto the
    miter plane, so neighbouring segments share their joint rings and every wall line stays straight along its segment."""
    d = [unit(sub(b, a)) for a, b in zip(points, points[1:])]
    n1 = [None]*len(d); n1[-1] = unit(sub(normal, tuple(x*dot(normal, d[-1]) for x in d[-1])))
    for i in range(len(d)-2, -1, -1):
        n1[i] = turn(n1[i+1], d[i+1], d[i])
    return dict(points=[tuple(q) for q in points], d=d, n1=n1, n2=[cross(a, b) for a, b in zip(d, n1)],
                miter=[d[0]]+[unit(add(a, b)) for a, b in zip(d, d[1:])]+[d[-1]])


def tube_point(fr, i, rho, phi, t=0.0):
    """Point at distance rho from the axis and angle phi: on segment i at distance t from its start point i, or (t None) on the ring of joint
    i, projected onto its miter plane along the incoming segment."""
    seg = i if t is not None else max(i-1, 0); p = fr['points'][i]
    q = add(p, fr['d'][seg], t or 0.0)
    v = add(q, add(tuple(x*math.cos(phi) for x in fr['n1'][seg]), tuple(x*math.sin(phi) for x in fr['n2'][seg])), rho)
    if t is not None:
        return v
    m, d = fr['miter'][i], fr['d'][seg]
    return add(v, d, -dot(sub(v, p), m)/dot(d, m))


def tube_radius_at(fr, p, eps=1e-9):
    """Distance of point p from the axis of the mitered tube segment whose two end planes (miter or flat end, within eps) enclose it; inf outside
    the tube's length. Unlike the distance to the axis polyline it is exact on the outer side of an elbow."""
    best = math.inf
    for i, d in enumerate(fr['d']):
        a, b = fr['points'][i], fr['points'][i+1]
        if dot(sub(p, a), fr['miter'][i]) >= -eps and dot(sub(p, b), fr['miter'][i+1]) <= eps:
            q = sub(p, a); best = min(best, math.sqrt(max(dot(q, q)-dot(q, d)**2, 0.0)))
    return best


def tube_frames_of(s, j, la):
    """Sweep frames of rotor j's crew tube to the sector at la: n1 points from the tube's run toward its crew spoke's rail plane."""
    _, _, z_h = sector_hatches(s)['overhead_wall']
    return tube_frames(tube_path(s, j, la), tuple(-math.copysign(1.0, z_h)*x for x in sector_axes(s, la)[3]))


def hoop_cuts(s, j):
    """HUM-001 zone 5: openings (a, b, radius) through ring j's inner hoop for its hollow crew tubes, rotor-local: the tube's outer radius along
    its run, from inside the hoop's inner face to the sector's overhead wall. Proxy tubes (no clear bore) open nothing."""
    ro, rc = tube_radii(s, j)
    if rc is None:
        return []
    x_h, y_w, z_h = sector_hatches(s)['overhead_wall']; y_in = s['habitat_ring']['frame_inner_radius_m']-habitat_ring.floor(s)
    return [(sector_point(s, la, (x_h, y_in-.3, z_h)), sector_point(s, la, (x_h, y_w+.05, z_h)), ro) for _, la in sectors(s)]


def bracket_stations(s, points):
    """Radial stations of the spoke brackets along a tube's run: every spoke_bracket_pitch_m from half a pitch past the last elbow, inside the
    ring frame's inner hoop by half a metre."""
    c = s['crew_transfer']; pitch = c['spoke_bracket_pitch_m']; r0 = math.hypot(*points[-2][1:]); r1 = s['habitat_ring']['frame_inner_radius_m']-.5
    return [r0+pitch*(k+.5) for k in range(int((r1-r0)/pitch+.5)) if r0+pitch*(k+.5) <= r1]


def sectors(s):
    """(1-based sector index, ring-local angle) of the sectors of one ring; the crew spokes sit on these angles."""
    return [(k+1, a) for k, a in enumerate(habitat_ring.sector_angles(s))]


def stationary(s):
    """Vehicle-frame parts in WF_CREW_TRANSFER: trunk, spine ports, fitting connectors and the refuge port (all rods). HUM-001: the trunk, the
    connectors of the human-entry ports, the spine port of each human-entry vestibule and the refuge port (human_entry.refuge_port_clear_m) are
    hollow (`hollow` = clear radius; the rod radius is the outer one)."""
    c, p = s['crew_transfer'], s['prototype']; ro = outer(s); ref = hull_geometry.refuge(s); out = []
    tr = c['trunk_clear_radius_m']; human = set(s['human_entry']['ports'])
    for f in hull_geometry.service_fittings(s):
        n = f['name'].upper(); big = f['name'] in human
        out.append(rod(f'Crew_Connector_{f["name"]}', [radial(f['x'], tr, f['theta']), radial(f['x'], f['r0'], f['theta'])], p['dock_radius_m'] if big else ro, flat=True,
                       role='FITTING_CONNECTOR', edge=('TRUNK', n), mates={'Crew_Trunk', 'Structural_Spine', f['name']}, fitting=f['name'], interface=f'IF_CREW_{n}',
                       pairs_with=f['interface'], **({'hollow': p['dock_clear_radius_m']} if big else {})))
    a = math.radians(c['refuge_port_angle_deg']); xm = (ref['x0']+ref['x1'])/2; rc = s['human_entry']['refuge_port_clear_m']/2
    out.append(rod('Crew_Refuge_Port', [radial(xm, tr, a), radial(xm, ref['inner'], a)], rc+c['passage_wall_m'], flat=True, role='REFUGE_PORT', edge=('TRUNK', 'REFUGE'),
                   mates={'Crew_Trunk', 'Structural_Spine', 'Refuge_Storm_Shelter'}, interface='IF_CREW_REFUGE_PORT', pairs_with='IF_CREW_REFUGE', hollow=rc))
    import storeroom                   # HUM-002: the SP-45 storeroom's port, its sill on the room's floor (storeroom.port)
    sp = storeroom.port(s)
    out.append(rod('Crew_Store_Port', [sp['a'], sp['b']], sp['outer'], flat=True, role='STORE_PORT', edge=('TRUNK', 'STOREROOM'),
                   mates={'Crew_Trunk', 'Structural_Spine', 'Storeroom_Shell'}, interface='IF_CREW_STORE_PORT', pairs_with='IF_STOREROOM', hollow=sp['clear']))
    for rot in ri.rotors(s):
        j = rot['index']; v = vestibule(s, j); xx = rot['x']+v['port_u']
        for k, la in sectors(s):
            if k not in v['ports']:
                continue
            out.append(rod(f'Crew_Port_{j}_{k}', [radial(xx, tr, rot['phase']+la), radial(xx, v['r0'], rot['phase']+la)], v['port_r'], flat=True,
                           role='SPINE_PORT', edge=('TRUNK', f'VESTIBULE_{j}'), rotor=j, sector=k,
                           mates={'Crew_Trunk', 'Structural_Spine', f'Crew_Vestibule_{j}', f'Crew_Vestibule_{j}_Guard_Aft', f'Crew_Vestibule_{j}_Guard_Fwd'}, interface=f'IF_CREW_PORT_{j}_{k}', pairs_with=f'IF_VESTIBULE_{j}',
                           **({'hollow': v['port_clear']} if v['human'] else {})))
    x0 = min(q['points'][0][0]-q['radius'] for q in out)-c['trunk_end_allowance_m']; x1 = max(q['points'][0][0]+q['radius'] for q in out)+c['trunk_end_allowance_m']
    out.insert(0, rod('Crew_Trunk', [(x0, 0.0, 0.0), (x1, 0.0, 0.0)], tr+c['passage_wall_m'], flat=True, role='TRUNK', edge=None, interface=None, hollow=tr))
    # Every stationary branch opens off the same trunk: where branches meet at one station is a framed spine opening (OPEN).
    names = {q['name'] for q in out}
    for q in out:
        q['mates'] = set(q.get('mates', ())) | {'Structural_Spine'} | (names-{q['name']})
    return out


def bores(s):
    """HUM-001 zone 2-3 openings, as closed cylinders (a, b, radius) for the generators' boolean cuts: through the trunk wall, the clear bore of each
    hollow connector; through the spine, the trunk envelope and the outer cylinder of each hollow connector; through each hollow connector's inner
    end, the trunk's outer cylinder, so the connector starts on the trunk skin and its walls never share the trunk wall's volume (coincident walls
    rendered as z-fighting patches through the port, M7.1). Connector cutters run from the ship axis to beyond the spine skin."""
    parts = stationary(s); trunk = parts[0]; w = s['crew_transfer']['passage_wall_m']; out = {'Crew_Trunk': [], 'Structural_Spine': []}
    (x0, _, _), (x1, _, _) = trunk['points']; reach = layout.spine_core(s)[2]+w
    out['Structural_Spine'].append(((x0, 0.0, 0.0), (x1, 0.0, 0.0), trunk['radius']))
    for q in parts[1:]:
        if 'hollow' in q:
            x, th = q['points'][0][0], math.atan2(q['points'][0][2], q['points'][0][1])
            out['Crew_Trunk'].append(((x, 0.0, 0.0), radial(x, reach, th), q['hollow']))
            out['Structural_Spine'].append(((x, 0.0, 0.0), radial(x, reach, th), q['radius']))
            out[q['name']] = [((x0+w, 0.0, 0.0), (x1-w, 0.0, 0.0), trunk['radius'])]
    return out


def trims(s):
    """HUM-001 zone 3 review: each hollow spine port ends on its vestibule chamber's inner radius (a saddle), so none of it stands in the rotating
    annulus (a flat end reaches (r0^2 + port radius^2)^0.5 there at its sides); the refuge port likewise on the refuge cavity's inner face. Closed
    cylinders (a, b, radius) the generator keeps (boolean intersection)."""
    face = {'SPINE_PORT': lambda q: vestibule(s, q['rotor'])['r0'], 'REFUGE_PORT': lambda q: hull_geometry.refuge(s)['inner']}
    return {q['name']: [((q['points'][0][0]-q['radius']-.1, 0.0, 0.0), (q['points'][0][0]+q['radius']+.1, 0.0, 0.0), face[q['role']](q))]
            for q in stationary(s) if q['role'] in face and 'hollow' in q}


def chamber_u(s, j):
    """Axial span of the transit chamber of rotor j's vestibule: its span less a guard ring at each end (its end faces are the primary seal planes)."""
    v = vestibule(s, j)
    return v['cu0'], v['cu1']


def seal_planes(s):
    """Seal planes a leak path along the spine crosses on its weakest side, counted from the ring end faces the geometry builds: for each rotor and
    each side of the spine-port span, the distinct axial positions of built vestibule ring end faces that reach the spine seal radius; the minimum
    over rotors and sides (Q30 asks two)."""
    worst = None
    for j in {q['rotor'] for q in rotating(s) if q['shape'] == 'ring'}:
        v = vestibule(s, j); lo, hi = v['port_u']-v['port_r'], v['port_u']+v['port_r']
        faces = {round(u, 9) for q in rotating(s) if q['shape'] == 'ring' and q['rotor'] == j and q['r0'] <= v['r0']+1e-9 for u in (q['x0'], q['x1'])}
        for n in (len({u for u in faces if u <= lo+1e-9}), len({u for u in faces if u >= hi-1e-9})):
            worst = n if worst is None else min(worst, n)
    return worst or 0


def rotating(s):
    """Rotor-local parts of rotor j: vestibule, struts, the crew tubes and their spoke brackets. The human-entry vestibule (HUM-001 zone 3)
    carries `hollow` (its clear outer radius) and `wall`: a pressure shell open toward the spine, its ring envelope is what the clearance screens use.
    Since Q46 it and its guard rings are the despun transfer drum (`drum`): parented to Drum_j, on its own bearings on the spine, and not strutted
    to the rotor; at the index it lines up with the rotor, so the screens keep it in rotor j's frame (it is axisymmetric but for its openings).
    Its crew tubes (zone 4) carry `hollow` (their clear radius): mitered pressure tubes whose solid rod is what the screens use. A ring-B tube's
    rod starts at its bulkhead; its neck (tube_neck) lies between the screened vestibule envelope and that rod."""
    c, ri_ = s['crew_transfer'], s['rotor_interface']; out = []
    rs = (ri_['drum_inner_radius_m']+ri_['drum_outer_radius_m'])/2
    for rot in ri.rotors(s):
        j = rot['index']; v = vestibule(s, j); u0, u1, cu0, cu1 = v['u0'], v['u1'], v['cu0'], v['cu1']; g = c['vestibule_guard_m']
        guards = [f'Crew_Vestibule_{j}_Guard_{e}' for e in ('Aft', 'Fwd')] if g > 0 else []
        drum = {'drum': True} if v['human'] else {}
        out.append(ring(f'Crew_Vestibule_{j}', cu0, cu1, v['r0'], v['r1'], role='VESTIBULE', rotor=j, **drum,
                        mates={'Structural_Spine'} | {f'Crew_Port_{j}_{k}' for k, _ in sectors(s)} | {f'Vestibule_Strut_{j}_{k}' for k, _ in sectors(s)} |
                        {f'Crew_Tube_{j}_{k}' for k, _ in sectors(s)} | set(guards), **({'hollow': v['clear'], 'wall': s['human_entry']['chamber_wall_m']} if v['human'] else {})))
        # Guard rings (HAB-001, Q30): the monitored inter-seal cavity outside each primary end plane; their outer faces are the secondary planes.
        if g > 0:
            for name, a, b, end in ((guards[0], u0, cu0, 'AFT'), (guards[1], cu1, u1, 'FWD')):
                out.append(ring(name, a, b, v['r0'], v['r1'], role='VESTIBULE_GUARD', rotor=j, end=end, ident=f'WF.CREW.{j}.VESTIBULE_GUARD_{end}', **drum,
                                mates={'Structural_Spine', f'Crew_Vestibule_{j}'} | {f'Vestibule_Strut_{j}_{k}' for k, _ in sectors(s)} | {f'Crew_Tube_{j}_{k}' for k, _ in sectors(s)} |
                                {f'Crew_Port_{j}_{k}' for k, _ in sectors(s)} | (set(guards)-{name})))
        # Struts extend the drum: they mate with the drum and its rings, and keep the drum's own display gap to the stationary hub.
        spinning = {q['name'] for q in ri.rotating(s) if q['rotor'] == j}
        for k, la in sectors(s):
            a = la+math.radians(c['strut_offset_deg'])
            # Q46: a human-entry vestibule is the despun transfer drum on its own bearings on the spine, so only a proxy vestibule is strutted
            # to the rotor drum.
            if not v['human']:
                out.append(rod(f'Vestibule_Strut_{j}_{k}', [radial(u1, rs, a), radial(ri_['drum_u_m'][0], rs, a)], c['strut_radius_m'], role='STRUT', rotor=j,
                               mates={f'Crew_Vestibule_{j}', f'Crew_Vestibule_{j}_Guard_Aft', f'Crew_Vestibule_{j}_Guard_Fwd'} | spinning, display_gap_prefixes={f'Hub{j}_', f'Path:Hub{j}_'}))
            # The tube leaves the vestibule square through a radial collar, turns beside the crew spoke in two elbows and opens through the inner
            # hoop onto the sector's overhead wall (tube_path).
            ro, rc = tube_radii(s, j); pts = tube_path(s, j, la); name = f'Crew_Tube_{j}_{k}'
            rails = [q for q in habitat_ring.spokes(s) if q['ring'] == j and q['crew'] and math.isclose(q['angle'], la, abs_tol=1e-9)]
            brackets = []
            for i, rho in enumerate(bracket_stations(s, pts), 1):
                axis = sector_point(s, la, (pts[-1][0], rho-habitat_ring.floor(s), sector_hatches(s)['overhead_wall'][2]))
                for q in rails:
                    a = radial(q['u'], rho, la); e = unit(sub(a, axis))
                    brackets.append(rod(f"{name}_Bracket_{i}_{'Aft' if q['side'] < 0 else 'Fwd'}", [a, add(axis, e, ro)], c['spoke_bracket_radius_m'], role='TUBE_BRACKET',
                                        rotor=j, mates={name, q['name']}))
            out.append(rod(name, pts, ro, flat=True, role='COAST_TUBE', rotor=j, sector=k, edge=(f'VESTIBULE_{j}', f'SECTOR_{j}_{k}'),
                           mates={f'Crew_Vestibule_{j}', *guards}, mate_prefixes={f'Sector_{j}_{k}', f'Ring_{j}_Hoop_Inner'}, interface=f'IF_CREW_TUBE_{j}_{k}_SECTOR',
                           pairs_with='IF_SECTOR_OVERHEAD_HATCH', **({'hollow': rc} if rc else {})))
            out += brackets
    return out


def interfaces(s):
    """Interface empties: stationary ones (vehicle frame, WF_CREW_TRANSFER) and rotating ones (rotor-local, habitat files)."""
    c = s['crew_transfer']; out = []
    for q in stationary(s):
        if q['interface']:
            out.append(dict(name=q['interface'], side='STATIONARY', rotor=q.get('rotor'), at=q['points'][-1], pairs_with=q['pairs_with'],
                            status={'FITTING_CONNECTOR': 'OPEN D1/E4: pressurized connector from the crew trunk to the fitting; hatch and isolation not designed',
                                    'REFUGE_PORT': 'OPEN OD-011: refuge entry from the crew trunk; hatch, second egress and shielding penetration not designed',
                                    'STORE_PORT': 'OPEN HUM-002: SP-45 storeroom entry from the crew trunk; hatch seal, latch and framed spine opening not designed',
                                    'SPINE_PORT': 'OPEN OD-002: stationary hatch through the spine wall into the rotary vestibule; framed spine opening not designed'}[q['role']]))
    trunk = stationary(s)[0]
    for end, at in (('AFT', trunk['points'][0]), ('FWD', trunk['points'][1])):
        out.append(dict(name=f'IF_CREW_TRUNK_{end}', side='STATIONARY', rotor=None, at=at, pairs_with=None,
                        status='OPEN OD-002: pressurized crew trunk in the spine bore; pressure shell, spine structure and routing of hub power/data around it not designed'))
    for rot in ri.rotors(s):
        j = rot['index']; v = vestibule(s, j); u0, u1, cu0, cu1 = v['u0'], v['u1'], v['cu0'], v['cu1']
        # Q46: a human-entry vestibule is the despun transfer drum (side DRUM, parented to Drum_j); a proxy one rides on the rotor.
        side = 'DRUM' if v['human'] else 'ROTATING'
        out.append(dict(name=f'IF_VESTIBULE_{j}', side=side, rotor=j, at=((u0+u1)/2, 0.0, 0.0), pairs_with=None,
                        status='OPEN OD-002/MEC-019: despun transfer drum (BASELINE architecture, Q46): isolated intermediate volume that synchronizes between the spine and the ring; drum size, bearings, despin drive, sync cycle, pressure and procedure not designed'
                        if v['human'] else 'OPEN OD-002/MEC-006: hatch-isolated rotary vestibule, pressurized only for transit; volume, pressure and procedure not designed'))
        for end, u in (('AFT', u0), ('FWD', u1)):
            out.append(dict(name=f'IF_VESTIBULE_{j}_SEAL_{end}', side=side, rotor=j, at=radial(u, v['r0'], 0.0), pairs_with=None,
                            status='OPEN MEC-006/007/019: secondary rotary pressure seal and drum bearing race on the spine as a life-limited replaceable cartridge; type, leak rate, load and life not designed'))
        for end, u in (('AFT', cu0), ('FWD', cu1)):
            out.append(dict(name=f'IF_VESTIBULE_{j}_SEAL_{end}_PRIMARY', side=side, rotor=j, at=radial(u, v['r0'], 0.0), pairs_with=None,
                            status='OPEN MEC-006/007: primary rotary pressure seal at the transit chamber end; type, leak rate and life not designed'))
        for end, u in (('AFT', (u0+cu0)/2), ('FWD', (cu1+u1)/2)):
            out.append(dict(name=f'IF_VESTIBULE_{j}_GUARD_{end}', side=side, rotor=j, at=radial(u, v['r0'], 0.0), pairs_with=None,
                            status='OPEN MEC-015/019: inter-seal guard cavity pressure sensing and the drum\'s despin drive; sensor, threshold, drive rating and response timing not designed'))
        for k, la in sectors(s):
            out.append(dict(name=f'IF_VESTIBULE_{j}_HATCH_{k}', side=side, rotor=j, at=radial(v['hatch_u'], v['r1'], la), pairs_with=f'IF_CREW_TUBE_{j}_{k}_COLLAR' if v['human'] else None,
                            status='OPEN OD-002/MEC-019: drum opening onto the crew tube with its sliding door; mates the tube collar across the running gap only when the drum is synchronized and latched; seal, latch and door drive not designed'
                            if v['human'] else 'OPEN OD-002: vestibule outer hatch of the crew tube; size and mechanism not designed'))
        if v['human']:
            st = transfer_stack(s, j)
            for k, la in sectors(s):
                out.append(dict(name=f'IF_CREW_TUBE_{j}_{k}_COLLAR', side='ROTATING', rotor=j, at=radial(v['hatch_u'], st['ring_face'], la), pairs_with=f'IF_VESTIBULE_{j}_HATCH_{k}',
                                status='OPEN OD-002/MEC-019: crew-tube collar face with its sliding hatch (rotating-side closure, Q46); latch collar, seal and hatch drive not designed'))
            q = next(q for q in closures(s, j) if q['kind'] == 'PORT_GATE')
            out.append(dict(name=f'IF_CREW_PORT_{j}_GATE', side='STATIONARY', rotor=j, at=radial((q['x0']+q['x1'])/2, (q['r0']+q['r1'])/2, q['angle']), pairs_with=None,
                            status='OPEN OD-002/MEC-019: stationary-side closure (Q46): gate sliding forward in a pocket of the spine shell; seal, drive, pocket framing and the slotted spine shell not designed'))
    for q in rotating(s):
        if q.get('interface'):
            out.append(dict(name=q['interface'], side='ROTATING', rotor=q['rotor'], sector=q['sector'], at=q['points'][-1], pairs_with=q['pairs_with'],
                            status='OPEN OD-002: telescoping pressurized crew tube; retraction, stowage and loads not designed'))
    return out


# ---------- obstacles ------------------------------------------------------------------------------------------------

def world_obstacles(s):
    """Vehicle-frame obstacles: spine, stationary hub parts and withdrawal paths, spokes, ring-stop locks (flat rods, present in both
    habitat states), refuge, fittings, storage packs, forward mount, cage, hull and radiator envelopes."""
    p = s['prototype']; L = s['ship']['length']['value']; R = s['ship']['body_diameter']['value']/2; st = s['structure']; out = []
    sp = next(o for o in power_storage.obstacles(s) if o[0] == 'Structural_Spine')
    out.append(ring('Structural_Spine', sp[1][0], sp[2][0], 0.0, sp[3]))
    parts = {q['name']: q for q in ri.stationary(s)}
    for q in parts.values():
        out.append(ring(q['name'], q['x0'], q['x1'], q['r0'], q['r1'], q['sector']))
    for name, row in ri.withdrawal(s).items():
        q = parts[name]
        out.append(ring(f'Path:{name}', row['path_x_m'][0], row['path_x_m'][1], q['r0'], q['r1'], q['sector'], rotor=q['rotor']))
    for q in ri.spokes(s):
        out.append(rod(q['name'], [q['a'], q['b']], q['radius']))
    for q in ri.ring_stop_locks(s):
        out.append(rod(q['name'], [q['a'], q['b']], q['radius'], flat=True))
    ref = hull_geometry.refuge(s)
    out.append(ring('Refuge_Storm_Shelter', ref['x0'], ref['x1'], ref['inner'], ref['outer']))
    for f in hull_geometry.service_fittings(s):
        out.append(rod(f['name'], [radial(f['x'], f['r0'], f['theta']), radial(f['x'], f['r1'], f['theta'])], f['radius'], flat=True))
    for pk in power_storage.packs(s):
        out.append(box(pk['name'], pk))
    phase = math.radians(p['ring_phase_deg'])
    for j, n in enumerate(st['sector_pickup_nodes']):
        a = phase+n*math.tau/st['ring_nodes']
        out.append(rod(f'Forward_Mount_Strut_{j}', [radial(layout.at(s, p['forward_mount_aft_x']), p['forward_mount_inner_radius_m'], a),
                                                     radial(layout.at(s, p['forward_mount_fwd_x']), p['forward_mount_outer_radius_m'], a)], p['structural_strut_radius_m']))
    rail = p['structural_rail_radius_m']
    out.append(ring('Primary_Cage', layout.at(s, p['thrust_ring_x']), layout.at(s, p['outer_cage_end_x'])+rail, st['sector_radius_m']-rail, st['sector_radius_m']+rail))
    (_, _, aft1), (_, fwd0, _) = hull_geometry.intervals(s)
    shell = s['hull']['shell_thickness_m']
    out.append(ring('Hull_Aft_Body', aft1-6.0, aft1, min(hull_geometry.inner_radius_at(s, aft1-6.0+k*.5) for k in range(13)), R+shell))
    out.append(ring('Hull_Forward_Collar', fwd0, L/2, min(hull_geometry.inner_radius_at(s, fwd0+k*.25) for k in range(int((L/2-fwd0)/.25)+1)), R+shell))
    out.append(ring('Radiator_Envelope', -L, layout.origin(s, 'RADIATOR_FRONT')+p['radiator_leading_spar_radius_m'], s['radiators']['root_radius']['value']-p['radiator_boom_radius_m'], 10*L))
    return out


def rotor_obstacles(s, j):
    """Rotor-local obstacles of rotor j: drum and hub rings, the ring frame (hoops and fills), the sectors and the spoke rails."""
    out = []
    for q in ri.rotating(s):
        if q['rotor'] == j:
            out.append(ring(q['name'], q['u0'], q['u1'], q['r0'], q['r1']))
    for q in habitat_ring.frame_parts(s):
        if q['ring'] == j:
            out.append(ring(q['name'], q['u0'], q['u1'], q['r0'], q['r1'], None if math.isclose(q['t1']-q['t0'], math.tau) else (q['t0'], q['t1'])))
    for q in habitat_ring.sectors(s):
        if q['ring'] == j:
            out.append(ring(q['name'], -q['axial']/2, q['axial']/2, q['r0'], q['r1'], (q['angle']-q['arc']/2, q['angle']+q['arc']/2)))
    for q in habitat_ring.spokes(s):
        if q['ring'] == j:
            out.append(rod(q['name'], [radial(q['u'], q['r0'], q['angle']), radial(q['u'], q['r1'], q['angle'])], q['radius']))
    return out


# ---------- screens ----------------------------------------------------------------------------------------------------

def mated(part, other):
    return other in part.get('mates', ()) or any(other.startswith(x) for x in part.get('mate_prefixes', ()))


def need(s, part, other):
    """Required gap: the mechanical clearance; only no overlap where a strut meets the hub like the drum it extends; the residual spine shell for the
    trunk, which fills the spine bore, so every part around it sits outside the spine wall (HUM-001 zone 2; fit row trunk_inside_spine)."""
    if part.get('role') == 'TRUNK':
        return s['crew_transfer']['passage_wall_m']
    if any(other.startswith(x) for x in part.get('display_gap_prefixes', ())):
        return 1e-9
    return s['prototype']['mechanical_clearance_m']


def gap(a, b, mode):
    """Clearance between primitives a and b ('exact' in one frame, 'swept' when one of them spins relative to the other)."""
    if mode == 'swept':
        return swept_gap(a, b)
    lo_a, hi_a = bounds(a); lo_b, hi_b = bounds(b)
    coarse = math.sqrt(sum(max(0.0, lo_b[i]-hi_a[i], lo_a[i]-hi_b[i])**2 for i in range(3)))
    if coarse > 1.0:
        return coarse
    def near(pts, lo, hi, pad=1.0):
        # Samples farther than `pad` from the other part's bounds cannot set a gap below 1 m.
        return [(q, r) for q, r in pts if all(lo[i]-pad-r <= q[i] <= hi[i]+pad+r for i in range(3))]
    one = min((distance(b, pt)-rad for pt, rad in near(samples(a), lo_b, hi_b)), default=1.0)
    # Thin rods and bands can sit wholly inside a solid part without touching its surface samples: check them the other way too.
    two = min((distance(a, pt)-rad for pt, rad in near(samples(b), lo_a, hi_a)), default=1.0) if b['shape'] in ('rod', 'torus') else one
    return min(one, two, max(coarse, 1.0))


_MEMO = {}


def clearances(s):
    """Every crew part against every non-mated obstacle and crew part, per habitat state. Rows keep the worst pair per part.
    Memoized on the full input, because spec.load validates on every call."""
    key = hashlib.sha256(json.dumps(s, sort_keys=True, default=str).encode()).hexdigest()
    if key not in _MEMO:
        _MEMO[key] = _clearances(s)
    return copy.deepcopy(_MEMO[key])


def _clearances(s):
    rows = {}; rot = {r['index']: r for r in ri.rotors(s)}
    world = world_obstacles(s); crew_st = stationary(s); crew_rot = rotating(s)
    local = {j: rotor_obstacles(s, j)+[q for q in crew_rot if q['rotor'] == j] for j in rot}
    for state in STATES:
        # Rotor j's obstacles and crew parts: rotor-local, and posed in the vehicle frame (at the index angle when stopped and locked).
        angle = lambda j: rot[j]['phase'] if state == 'STOPPED_LOCKED' else 0.0
        pose = {j: [posed(o, rot[j]['x'], angle(j)) for o in local[j]] for j in rot}
        mode = 'exact' if state == 'STOPPED_LOCKED' else 'swept'

        def check(part, other, how):
            if other['name'] == part['name'] or mated(part, other['name']) or mated(other, part['name']):
                return
            g = gap(part, other, how)
            row = rows.setdefault(f"{part['name']}@{state}", dict(part=part['name'], state=state, min_gap_m=math.inf, nearest=None, need_m=None, failures=[]))
            req = need(s, part, other['name'])
            if g-req < (row['min_gap_m']-row['need_m'] if row['need_m'] is not None else math.inf):
                row.update(min_gap_m=g, nearest=other['name'], need_m=req)
            if g < req-1e-9:            # a placement derived to sit on the clearance (ring B's vestibule) passes despite float noise
                row['failures'].append(f"{other['name']}: {g:.3f} < {req:.3f} m")
        for part in crew_st:
            for o in world+crew_st:
                check(part, o, 'exact')
            for j in rot:
                for o in pose[j]:
                    check(part, o, mode)
        for part in crew_rot:
            j = part['rotor']; mine = next(o for o in pose[j] if o['name'] == part['name'])
            for o in local[j]:
                check(part, o, 'exact')
            for o in world:
                check(mine, o, mode)
            for i in rot:
                if i != j:
                    for o in pose[i]:
                        check(mine, o, mode)
    for row in rows.values():
        row['passed'] = not row['failures']
    return rows


def fit(s):
    """Hatch, port and vestibule placement rules that the sampled clearances do not express."""
    c, p, ri_, hr = s['crew_transfer'], s['prototype'], s['rotor_interface'], s['habitat_ring']
    ro = outer(s); clr = p['mechanical_clearance_m']; tol = 1e-9; x_core, _, core = layout.spine_core(s); h = s['human_entry']
    rs_in = (ri_['drum_inner_radius_m']+ri_['drum_outer_radius_m'])/2-c['strut_radius_m']
    # Port and hatch rules hold for every rotor's vestibule (the worst one is reported); each outer hatch takes its rotor's crew tube, or on ring B
    # the tube's neck.
    ves = [dict(vestibule(s, r['index']), tube=tube_radii(s, r['index']), hatch_r=(tube_neck(s, r['index']) or {}).get('outer', tube_radii(s, r['index'])[0]))
           for r in ri.rotors(s)]
    port = lambda v: (v['port_u']-v['port_r'], v['port_u']+v['port_r']); vh = lambda v: (v['hatch_u']-v['hatch_r'], v['hatch_u']+v['hatch_r'])
    human = [v for v in ves if v['human']]; ro_max = max(v['tube'][0] for v in ves)
    import habitat_interior
    x_h, _, z_h = sector_hatches(s)['overhead_wall']
    tubes = [(q, tube_radii(s, q['rotor'])[0]) for q in rotating(s) if q['role'] == 'COAST_TUBE']
    elbow = max(math.hypot(*pt[1:])+r for q, r in tubes for pt in q['points'][1:-1])
    seg_a = math.radians(ri_['segment_offset_deg']); strut_a = math.radians(c['strut_offset_deg'])
    sweep_half = habitat_ring.sweep_half(s); body = s['ship']['body_diameter']['value']/2
    # Angle (deg) between each crew tube and the nearest crew spoke: the tubes run out along the crew spokes.
    spoke_angles = [q['angle'] for q in habitat_ring.spokes(s) if q['crew']]
    tube_error = max(min(angle_diff(la, a) for a in spoke_angles) for _, la in sectors(s))
    rows = {
        'trunk_inside_spine': (core-(c['trunk_clear_radius_m']+c['passage_wall_m']), c['passage_wall_m']),
        'vestibule_seals_on_spine': (min(v['r0'] for v in ves)-core, tol),
        'spine_core_under_trunk_and_vestibules': (min([stationary(s)[0]['points'][0][0]]+[r['x']+vestibule(s, r['index'])['u0'] for r in ri.rotors(s)])-x_core, -tol),
        'spine_port_inside_vestibule_seals': (min(min(port(v)[0]-(v['cu0']+c['seal_allowance_m']), (v['cu1']-c['seal_allowance_m'])-port(v)[1]) for v in ves), -tol),
        'vestibule_hatch_inside_outer_wall': (min(min(vh(v)[0]-(v['cu0']+c['hatch_rim_m']), (v['cu1']-c['hatch_rim_m'])-vh(v)[1]) for v in ves), -tol),
        'straight_port_to_hatch_overlap_m': (min(min(port(v)[1], vh(v)[1])-max(port(v)[0], vh(v)[0])-c['passage_clear_radius_m'] for v in ves), -tol),
        # HUM-001 zone 3: each human-entry chamber holds the suited envelope between handrails on both walls; ring A's spine port is the 1.6 m
        # passage, and a window-limited one (ring B; the Path:* clearances keep the vestibule clear of the withdrawal paths) passes the suited envelope.
        'human_vestibule_depth_holds_suited_envelope': (min(v['clear']-v['r0'] for v in human)-2*(h['handrail_standoff_m']+2*h['handrail_radius_m']), h['mannequin']['suited_envelope_diameter_m']-tol),
        'primary_vestibule_port_clear_radius': (vestibule(s, h['vestibule_rotors'][0])['port_clear'], p['dock_clear_radius_m']-tol),
        'human_vestibule_port_holds_suited_envelope': (min(v['port_clear'] for v in human), h['mannequin']['suited_envelope_diameter_m']/2-tol),
        'human_tube_clear_radius': (min(tube_radii(s, j)[1] for j in h['tube_rotors']), p['dock_clear_radius_m']-tol),
        'overhead_hatch_inside_sector_ends': (hr['sector_axial_m']/2-s['interior']['end_allowance_m']-(abs(x_h)+ro_max), -tol),
        # HUM-001 zone 4: the tube runs beside its crew spoke, clear of the whole rail plane (rails and any web lacing between them), and its hatch
        # with its rim fits the overhead between the sector's side walls.
        'crew_tube_clear_of_spoke_plane': (abs(z_h)-ro_max-hr['spoke_rail_radius_m'], clr-tol),
        'overhead_hatch_inside_sector_arc': (habitat_interior.section(s)['half_width_ceiling_m']-(abs(z_h)+ro_max+c['hatch_rim_m']), -tol),
        'guard_cavity_m': (c['vestibule_guard_m'], 2*c['seal_allowance_m']-tol),
        'seal_planes': (seal_planes(s), s['habitat']['transfer']['seal_planes_min']),
        'strut_no_closer_to_stationary_band_than_drum': (rs_in-ri_['drum_inner_radius_m'], -tol),
        'strut_to_index_lock_angle_m': ((ri_['drum_inner_radius_m']+ri_['drum_outer_radius_m'])/2*math.sin(abs(seg_a-strut_a))-c['strut_radius_m'], clr),
        'coast_tube_bend_inside_body': (body-elbow, -tol),
        'coast_tube_inside_ring_sweep': (sweep_half-(abs(x_h)+ro_max), -tol),
        'crew_tube_on_crew_spoke': (-math.degrees(tube_error), -tol),
    }
    rows.update(transfer_fit(s))
    out = {k: dict(value_m=v, need_m=n, passed=v >= n) for k, (v, n) in rows.items()}
    return out


def transfer_fit(s):
    """Q46 placement rules for the despun drum and its closures, worst over the human-entry rotors (value, need) in metres: the gate inside the
    spine shell and, parked, clear of every other bore through it; each drum door and tube hatch parked clear of the next opening round the
    drum (or collar round the ring) and of the spoke rails; the tube hatch below the collar's first miter (ring A) or under the bulkhead (ring B)."""
    c, p = s['crew_transfer'], s['prototype']; tol = 1e-9; g = c['transfer_track_gap_m']; core = layout.spine_core(s)[2]
    to = c['trunk_clear_radius_m']+c['passage_wall_m']; rows = {}; worst = lambda k, v, n: rows.__setitem__(k, (min(v, rows[k][0]) if k in rows else v, n))
    bores = [q for q in stationary(s) if q['role'] != 'TRUNK']
    for j in s['human_entry']['vestibule_rotors']:
        v = vestibule(s, j); st = transfer_stack(s, j); qs = closures(s, j); ro, _ = tube_radii(s, j); neck = tube_neck(s, j)
        gate = next(q for q in qs if q['kind'] == 'PORT_GATE')
        worst('port_gate_inside_spine_shell', min(gate['r0']-(to+g), (core-g)-gate['r1']), -tol)
        x0, x1 = gate['x0']+gate['slide'], gate['x1']+gate['slide']; gap = math.inf
        for q in bores:
            a = q['points'][1]; th = math.atan2(a[2], a[1]); w = math.asin(min(1.0, q['radius']/gate['r0']))
            if angle_diff(th, gate['angle']) < w+(gate['t1']-gate['t0'])/2:
                gap = min(gap, max(q['points'][0][0]-q['radius']-x1, x0-(q['points'][0][0]+q['radius'])))
        worst('port_gate_parked_clear_of_spine_bores', gap, -tol)
        for kind, opening, rr in (('DRUM_DOOR', (neck or {}).get('clear', tube_radii(s, j)[1]), st['door'][0]), ('TUBE_HATCH', (neck or {}).get('outer', ro), st['hatch'][0])):
            q = next(q for q in qs if q['kind'] == kind); half = (q['t1']-q['t0'])/2; nxt = 2*math.pi/len(sectors(s))-math.asin(min(1.0, opening/rr))
            worst(f'{kind.lower()}_parked_clear_of_next_opening', (nxt-(q['turn']+half))*rr, -tol)
        q = next(q for q in qs if q['kind'] == 'TUBE_HATCH')
        rails = [r for r in habitat_ring.spokes(s) if r['ring'] == j]
        worst('tube_hatch_clear_of_spoke_rails', min(max(r['u']-r['radius']-q['x1'], q['x0']-(r['u']+r['radius'])) for r in rails), p['mechanical_clearance_m']-tol)
        top = neck['base']-g if neck else (v['r1']+ro)-ro*math.tan(math.pi/8)
        worst('tube_hatch_below_collar_miter_or_bulkhead', top-st['hatch'][1], -tol)
    return rows


def derived_constraints(s):
    """Requirements the PROTOTYPE route places on OPEN mechanisms."""
    c, ri_, p = s['crew_transfer'], s['rotor_interface'], s['prototype']
    rs_in = (ri_['drum_inner_radius_m']+ri_['drum_outer_radius_m'])/2-c['strut_radius_m']
    return {'retracted_lock_outer_radius_max_m': {'value': ri.retracted_lock_outer_radius_max(s), 'unit': 'm', 'canon_status': 'DERIVED', 'selection_status': 'PROTOTYPE',
                                                  'applies_to': 'ring-stop lock pins and the hub index-lock pin while the rotor spins',
                                                  'basis': 'The vestibule struts sweep the lock plane while the rings rotate; retracted locks and the index pin must stay inside this radius.'},
            'spine_port_circumference_share': {'value': max(len(v['ports'])*2*math.asin(min(1.0, v['port_r']/layout.spine_core(s)[2]))/math.tau
                                                            for v in (vestibule(s, r['index']) for r in ri.rotors(s))),
                                               'canon_status': 'DERIVED', 'selection_status': 'PROTOTYPE',
                                               'basis': 'Largest share of the spine core circumference that the spine ports at one vestibule station open (arc spanned by each port); the framed opening is OPEN.'}}


def graph(s):
    edges = [q['edge'] for q in stationary(s) if q['edge']]+[q['edge'] for q in rotating(s) if q.get('edge')]
    adj = {}
    for a, b in edges:
        adj.setdefault(a, set()).add(b); adj.setdefault(b, set()).add(a)
    return edges, adj


def reachable(adj, start):
    seen, todo = {start}, [start]
    while todo:
        for n in adj.get(todo.pop(), ()):
            if n not in seen:
                seen.add(n); todo.append(n)
    return seen


def length(points):
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def routes(s):
    """Per habitat state: every sector reaches the refuge, the EVA airlock and both docks; route length from each sector to the refuge.
    The crew tubes are the same in both states (no room turns); the state only changes how the clearances are screened."""
    c = s['crew_transfer']; st = {q['name']: q for q in stationary(s)}; out = {}
    ref_port = st.get('Crew_Refuge_Port')
    edges, adj = graph(s); rot = {q['name']: q for q in rotating(s)}
    for state in STATES:
        rows = {}
        for r in ri.rotors(s):
            j = r['index']
            for k, _ in sectors(s):
                seen = reachable(adj, f'SECTOR_{j}_{k}')
                leg = rot[f'Crew_Tube_{j}_{k}']['points']; v = vestibule(s, j)
                # A vestibule with one spine port (HUM-001) is crossed around the annulus at mid-depth from the port to the sector's hatch.
                kp = k if k in v['ports'] else v['ports'][0]; port = st[f'Crew_Port_{j}_{kp}']['points']
                arc = (v['r0']+v['r1'])/2*abs(angle_diff(sectors(s)[k-1][1], sectors(s)[kp-1][1]))
                crossing = math.hypot(v['hatch_u']-v['port_u'], v['r1']-v['r0'])+arc
                metres = None if ref_port is None else length(leg)+crossing+length(port)+abs(port[0][0]-ref_port['points'][0][0])+length(ref_port['points'])
                rows[f'SECTOR_{j}_{k}'] = {'reaches': sorted(n for n in seen if n in {'REFUGE', *FITTINGS}), 'route_to_refuge_m': metres,
                                        'passed': {'REFUGE', *FITTINGS} <= seen}
        out[state] = {'edges': [list(e) for e in edges], 'sectors': rows, 'passed': all(v['passed'] for v in rows.values())}
    return out


def alignment(s):
    """Crew tubes end exactly on the sector hatches where the habitat places the sectors."""
    hat = sector_hatches(s); out = {}
    for q in (q for q in rotating(s) if q.get('sector')):
        k = q['sector']; la = sectors(s)[k-1][1]
        out[q['name']] = math.dist(q['points'][-1], sector_point(s, la, hat['overhead_wall']))
    return out


def placement(s):
    """Protected-crew screen against Art Style Spacecraft rows A5/A7/A10 and the S&E ring shielding rule (12_HABITAT_LAYOUT A13)."""
    p = s['prototype']; body = s['ship']['body_diameter']['value']/2; ref = hull_geometry.refuge(s)
    shadow_fwd = layout.at(s, p['shadow_center_x'])+p['shadow_thickness_m']/2
    tube = next(q for q in rotating(s) if q['role'] == 'COAST_TUBE')
    axis = [add(a, sub(b, a), k/200) for a, b in zip(tube['points'], tube['points'][1:]) for k in range(201)]
    exposed = sum(math.dist(a, b) for a, b in zip(axis, axis[1:]) if min(math.hypot(*a[1:]), math.hypot(*b[1:])) >= body)
    return {'refuge_inside_body_m': body-ref['outer'],
            'refuge_forward_of_shadow_shield_m': ref['x0']-shadow_fwd, 'refuge_areal_density_g_cm2': s['shielding']['refuge']['areal_density_g_cm2'],
            'crew_tube_length_outside_body_m': exposed,
            'note': 'The rings stay at full size, so the pressurized sectors sit outside the 13 m body in every state; water, storage and structure fill the rest of the frame as distributed shielding (BASELINE ring_shielding, 12_HABITAT_LAYOUT A13). The crew tube is unshielded transit between the body and a sector. The refuge is inside the body.'}


def open_fields(s):
    return {'crew_path': s['habitat']['transfer']['crew_path'], 'bearing_seal': s['habitat']['transfer']['bearing_seal']}


def check(s):
    failures = []
    def require(condition, message):
        if not condition:
            failures.append(message)
    c = s['crew_transfer']
    require(c['status'] == 'PROTOTYPE' and c['unit'] == 'm', 'Crew transfer layout stays PROTOTYPE')
    for path, field in open_fields(s).items():
        require(field.get('known') is False and 'value' not in field, f'{path} stays OPEN')
    require(s['habitat']['transfer']['canon_status'] == 'BASELINE' and 'despun' in s['habitat']['transfer']['architecture'].lower(), 'Despun transfer vestibule per ring (I5, Q46)')
    require(s['service']['eva_access']['location'] == s['service']['docking']['location'] == 'STATIONARY_CENTRAL_STRUCTURE', 'EVA and docking on the stationary structure')
    require(s['shielding']['refuge']['capacity_persons'] >= s['crew']['rated_occupancy']['value'], 'Refuge holds the rated occupancy')
    require(c['vestibule_u_m'][0] < c['vestibule_u_m'][1] and 0 < c['passage_wall_m'] < c['passage_clear_radius_m'], 'Vestibule and passage dimensions')
    rows = fit(s)
    for k, v in rows.items():
        require(v['passed'], f"{k}: {v['value_m']:.3f} < {v['need_m']:.3f} m")
    gaps = clearances(s)
    for k, v in gaps.items():
        require(v['passed'], f"{k}: {v['failures']}")
    ways = routes(s)
    for state, v in ways.items():
        require(v['passed'], f'{state}: every sector must reach the refuge, the airlock and both docks')
    align = alignment(s)
    require(all(d < 1e-9 for d in align.values()), f'Crew tubes and collars must meet the sector hatches: {align}')
    # The P1-008 service paths stay clear of the crew route (checked above as Path:* obstacles) and remain removable.
    service = ri.withdrawal(s)
    require(all(r['passed'] for r in service.values()), 'P1-008 cartridge withdrawal paths')
    return dict(passed=not failures, failures=failures, fit=rows, clearances=gaps, routes=ways, alignment=align)


def contract(s):
    """Rig-contract section: PROTOTYPE route per state, sector hatches, OPEN fields and derived constraints."""
    c = s['crew_transfer']; hat = sector_hatches(s); ways = routes(s)
    return {'generation': 'P1-001', 'selection_status': 'PROTOTYPE', 'owner_question': 'P1-008 question 1 (crew vestibule vs hub)',
            'canon': {'architecture': s['habitat']['transfer']['architecture'], 'canon_status': s['habitat']['transfer']['canon_status'], 'source_ref': s['habitat']['transfer']['source_ref'],
                      'refuge_rule': s['shielding']['refuge']['location'], 'refuge_source_ref': s['shielding']['refuge']['source_ref']},
            'open': {k: {'known': False, 'canon_status': v['canon_status'], **({'reason': v['reason']} if 'reason' in v else {})} for k, v in open_fields(s).items()},
            'sector_hatches': {'OVERHEAD': {'sector_frame_m': list(hat['overhead_wall']), 'used_in': list(STATES), 'interface': 'IF_SECTOR_OVERHEAD_HATCH'}},
            'seal_planes': {'built_min_per_side': seal_planes(s), 'required': s['habitat']['transfer']['seal_planes_min'],
                            'chamber_u_m': {f"ROTOR_{r['index']}": list(chamber_u(s, r['index'])) for r in ri.rotors(s)}, 'guard_m': c['vestibule_guard_m']},
            'seal_fault': {'rule': s['habitat']['transfer']['seal_fault_action'], 'rig_action': 'WF_VESTIBULE_SEAL_FAULT', 'source_ref': 'rotary_transfer'},
            'vestibule': {'per_rotor': {f"ROTOR_{r['index']}": {'u_m': [v['u0'], v['u1']], 'radii_m': [v['r0'], v['r1']], 'spine_ports': v['ports'], 'hollow': v['human'],
                                                             'spine_port_clear_m': 2*v['port_clear'] if v['port_clear'] else None}
                                        for r in ri.rotors(s) for v in [vestibule(s, r['index'])]},
                          'pressurization': 'hatch-isolated; pressurized only for transit (PROTOTYPE rule)'},
            'routes': {state: {'edges': v['edges'], 'route_to_refuge_m': {k: r['route_to_refuge_m'] for k, r in v['sectors'].items()}} for state, v in ways.items()},
            'derived_constraints': derived_constraints(s), 'passage_clear_diameter_m': 2*c['passage_clear_radius_m'],
            'crew_tube_clear_diameter_m': {f"ROTOR_{r['index']}": 2*(tube_radii(s, r['index'])[1] or c['passage_clear_radius_m']) for r in ri.rotors(s)}}


def report(s):
    result = check(s)
    worst = sorted(result['clearances'].values(), key=lambda r: r['min_gap_m']-r['need_m'])[:12]
    return {'task': 'P1-001', 'scope': 'PROTOTYPE crew transfer route (stationary trunk, rotary vestibules, crew tubes) with clearances, hatch fit and refuge reachability with the rings ROTATING and STOPPED_LOCKED. No seal, hatch, pressure or structural sizing.',
            'passed': result['passed'], 'failures': result['failures'], 'fit': result['fit'], 'tightest_clearances': worst,
            'routes': result['routes'], 'alignment_m': result['alignment'], 'placement': placement(s), 'derived_constraints': derived_constraints(s),
            'contract': contract(s)}


if __name__ == '__main__':
    import spec
    data, _, _, _ = spec.load()
    out = report(data)
    OUTPUT.write_text(json.dumps(out, indent=1, default=float)+'\n')
    print('WF_CREW_TRANSFER', 'PASS' if out['passed'] else 'FAIL', OUTPUT)
    for f in out['failures']:
        print(' ', f)
