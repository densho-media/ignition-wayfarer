"""Maintenance-drone body family (data/drone_bodies.toml, docs/ACCESSORIES.md): production-candidate bodies for the seven mobile classes and
the two fixed arms of the DRONE-001 study fleet. Pure standard library; the Blender side is src/wayfarer/build/drone_bodies.py.

Each body is a tree of nodes. A node has an offset and a rest rotation in its parent's frame and optionally one joint (revolute about, or
prismatic along, a local axis); shapes (box, cylinder/cone, torus arc, text) sit in the node's frame. Joint value 0 is the stowed pose.
Local frame: +X forward along travel, +Y left, +Z away from the mounting surface (rails at z = 0, deck or duct floor at z = 0; the
free-flyer is centred). Every dimension is a PROTOTYPE design choice inside the owner's envelope class; no mass, power, speed, reach,
payload or latch rating is held (data [open]). Shared GU grammar: the GU-SIF fitting (dock, tool cartridge and robot-to-robot recovery),
docking targets, captive rail trucks, hardware stop, manual release, status lamp, qualification plate.

- load(root): ship spec + body data.
- bodies(s, d): {class id: body} with nodes, shapes, joints and actions.
- pose(body, values) -> world matrices; envelope(body, values) -> bbox; swept(body) over every action keyframe.
- check(s, d): the fit screen (inventory, stowed body inside its L2 proxy box, OPEN values null, GU safety kit present).

    python3 src/wayfarer/drone_bodies.py
"""
import math
import tomllib
from pathlib import Path

import drone_fleet as df

FPS = 24
FACE = {'+z': (0, 0, 0), '-z': (180, 0, 0), '+x': (0, 90, 0), '-x': (0, -90, 0), '+y': (-90, 0, 0), '-y': (90, 0, 0)}
TEXT_FACE = {'+z': (0, 0, 0), '+x': (90, 0, 90), '-x': (90, 0, -90), '+y': (90, 0, 180), '-y': (90, 0, 0)}   # lettering upright, read from outside
SAFETY_KIT = ('dock', 'recovery', 'hardware_stop', 'status_lamp', 'id_plate')


def load(root):
    import spec
    s = spec.load(Path(root))[0]
    d = tomllib.loads((Path(root)/'data/drone_bodies.toml').read_text())
    return s, d


# ------------------------------------------------------------------------------------------------------------------------------ maths
def _rot(axis, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    if axis == 'x':
        return ((1, 0, 0), (0, c, -s), (0, s, c))
    if axis == 'y':
        return ((c, 0, s), (0, 1, 0), (-s, 0, c))
    return ((c, -s, 0), (s, c, 0), (0, 0, 1))


def _mul(a, b):
    return tuple(tuple(sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def _app(m, v):
    return tuple(sum(m[i][k]*v[k] for k in range(3)) for i in range(3))


def euler(e):
    """Blender XYZ Euler (degrees): R = Rz Ry Rx."""
    return _mul(_rot('z', e[2]), _mul(_rot('y', e[1]), _rot('x', e[0])))


I3 = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


# ------------------------------------------------------------------------------------------------------------------------------ body
class Body:
    def __init__(self, cid, title, mount):
        self.id = cid; self.title = title; self.mount = mount; self.nodes = {}; self.order = []; self.shapes = []; self.kit = {}
        self.actions = {}; self.fixtures = []; self.notes = []
        self.node('root')

    def node(self, nid, parent=None, at=(0, 0, 0), rest=(0, 0, 0), joint=None, axis=None, limits=None, role='', job=''):
        if parent is None and nid != 'root':
            parent = 'root'
        self.nodes[nid] = dict(id=nid, parent=parent, at=tuple(at), rest=tuple(rest), joint=joint, axis=axis, limits=limits, role=role, job=job)
        self.order.append(nid); return nid

    def face(self, nid, parent, at, normal, **kw):
        return self.node(nid, parent, at, FACE[normal], **kw)

    def add(self, node, kind, part, mat, job='', **geo):
        self.shapes.append(dict(node=node, kind=kind, part=part, mat=mat, job=job, **geo)); return self.shapes[-1]

    def box(self, node, part, c, s, mat, bevel=0.0, job=''):
        return self.add(node, 'box', part, mat, job, c=tuple(c), s=tuple(s), bevel=bevel)

    def cyl(self, node, part, a, b, r, mat, r2=None, job='', n=24):
        return self.add(node, 'cyl', part, mat, job, a=tuple(a), b=tuple(b), r=r, r2=r if r2 is None else r2, n=n)

    def torus(self, node, part, c, axis, R, r, mat, arc=(0.0, 360.0), job=''):
        return self.add(node, 'torus', part, mat, job, c=tuple(c), axis=axis, R=R, r=r, arc=arc)

    def text(self, node, part, c, body, size, mat, job=''):
        """Lettering in the node's XY plane, reading along +X, facing +Z."""
        return self.add(node, 'text', part, mat, job, c=tuple(c), body=body, size=size)

    def mark(self, item, node, job):
        self.kit.setdefault(item, []).append(dict(node=node, job=job))

    def joints(self):
        return [n for n in self.order if self.nodes[n]['joint']]

    def act(self, name, keys, job, status='SIMULATION_ONLY'):
        """keys: [(time_s, {joint: value})]; every key is a whole pose: joints not named are at 0 (stowed)."""
        self.actions[name] = dict(keys=keys, job=job, status=status)


def pose(b, values=None):
    """World (rotation, translation) of every node for joint values {node: deg or m}."""
    values = values or {}; out = {}
    for nid in b.order:
        n = b.nodes[nid]; R, t = (I3, (0.0, 0.0, 0.0)) if n['parent'] is None else out[n['parent']]
        if '_R' not in n:
            n['_R'] = euler(n['rest'])
        a = _app(R, n['at']); t = (t[0]+a[0], t[1]+a[1], t[2]+a[2]); R = _mul(R, n['_R'])
        v = values.get(nid, 0.0)
        if n['joint'] == 'revolute' and v:
            R = _mul(R, _rot(n['axis'], v))
        elif n['joint'] == 'prismatic' and v:
            ax = {'x': (1, 0, 0), 'y': (0, 1, 0), 'z': (0, 0, 1)}[n['axis']]; t = tuple(t[i]+_app(R, ax)[i]*v for i in range(3))
        out[nid] = (R, t)
    return out


def _shape_points(q):
    if q['kind'] == 'box':
        c, s = q['c'], q['s']
        return [(c[0]+i*s[0]/2, c[1]+j*s[1]/2, c[2]+k*s[2]/2) for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)]
    if q['kind'] == 'cyl':
        a, b = q['a'], q['b']; e = [b[i]-a[i] for i in range(3)]; L = math.sqrt(sum(x*x for x in e)) or 1.0; e = [x/L for x in e]
        h = (1.0, 0.0, 0.0) if abs(e[0]) < .9 else (0.0, 1.0, 0.0)
        u = _unit(_cross(e, h)); w = _cross(e, u); pts = []
        for end, r in ((a, q['r']), (b, q['r2'])):
            for k in range(8):
                t = k*math.pi/4; pts.append(tuple(end[i]+r*(math.cos(t)*u[i]+math.sin(t)*w[i]) for i in range(3)))
        return pts
    if q['kind'] == 'torus':
        c = q['c']; R = q['R']+q['r']; pts = []
        a0, a1 = q['arc']
        for k in range(13):
            t = math.radians(a0+(a1-a0)*k/12); p = _torus_dir(q['axis'], t); pts.append(tuple(c[i]+R*p[i] for i in range(3)))
        return pts
    c = q['c']; w = q['size']*.6*len(q['body']); return [(c[0]-w/2, c[1]-q['size']/2, c[2]), (c[0]+w/2, c[1]+q['size']/2, c[2])]


def _torus_dir(axis, t):
    """Unit direction at angle t (rad) in the plane normal to axis; t = 0 is +Z for an x or y axis, +X for a z axis."""
    if axis == 'x':
        return (0.0, math.sin(t), math.cos(t))
    if axis == 'y':
        return (math.sin(t), 0.0, math.cos(t))
    return (math.cos(t), math.sin(t), 0.0)


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _unit(v):
    n = math.sqrt(sum(x*x for x in v)) or 1.0; return tuple(x/n for x in v)


def envelope(b, values=None, include=None):
    """Axis-aligned bbox (min, max) in the body frame of every shape (or those whose part is in include)."""
    P = pose(b, values); lo = [math.inf]*3; hi = [-math.inf]*3
    for q in b.shapes:
        if include and q['part'] not in include:
            continue
        R, t = P[q['node']]
        for p in _shape_points(q):
            w = _app(R, p)
            for i in range(3):
                v = w[i]+t[i]; lo[i] = min(lo[i], v); hi[i] = max(hi[i], v)
    return tuple(lo), tuple(hi)


def frames(b, name):
    """Joint values per keyframe of an action, every joint named (unnamed = 0, stowed): [(frame, {joint: value})]."""
    zero = {j: 0.0 for j in b.joints()}
    return [(round(t*FPS), dict(zero, **vals)) for t, vals in b.actions[name]['keys']]


def swept(b):
    """Body-frame swept bbox: the stowed pose and every keyframe of every action, travel joints held at zero and review fixtures excluded
    (keyframes only: interpolation between keys is not sampled). Mechanisms, tools and carried modules are included."""
    travel = {n for n in ('root', 'travel') if b.nodes.get(n, {}).get('joint') == 'prismatic'}
    parts = {q['part'] for q in b.shapes if not q['part'].startswith('FIXTURE')}
    lo = [math.inf]*3; hi = [-math.inf]*3
    for vals in [{}]+[v for a in b.actions for _, v in frames(b, a)]:
        l, h = envelope(b, {k: v for k, v in vals.items() if k not in travel}, include=parts)
        for i in range(3):
            lo[i] = min(lo[i], l[i]); hi[i] = max(hi[i], h[i])
    return tuple(lo), tuple(hi)


def reach(b, tool, target, joints, start=None, approach=None, w=.02, iters=60):
    """Joint values that bring node `tool` to `target` (body frame), its +Z toward `approach` if given: coordinate descent within the
    joint limits. A display-pose solver for keyframes, not a reach claim (arm reach OPEN)."""
    if start is None and joints and b.nodes[joints[0]]['axis'] == 'z':        # multi-start over the base yaw: avoids a folded local minimum
        runs = [reach(b, tool, target, joints, {joints[0]: a, **{j: 0.0 for j in joints[1:]}}, approach, w, iters) for a in range(-135, 181, 45)]
        return min(runs, key=lambda r: r[1])
    v = {j: 0.0 for j in joints}; v.update(start or {}); step = {j: 25.0 for j in joints}

    def cost(vals):
        R, t = pose(b, vals)[tool]; c = sum((t[i]-target[i])**2 for i in range(3))
        if approach:
            z = (R[0][2], R[1][2], R[2][2]); c += w*sum((z[i]-approach[i])**2 for i in range(3))
        return c
    best = cost(v)
    for _ in range(iters):
        for j in joints:
            lim = b.nodes[j]['limits']; moved = False
            for sgn in (1, -1):
                trial = dict(v); trial[j] = v[j]+sgn*step[j]
                if lim:
                    trial[j] = max(lim[0], min(lim[1], trial[j]))
                c = cost(trial)
                if c < best:
                    v, best, moved = trial, c, True; break
            if not moved:
                step[j] *= .6
    return {j: round(v[j], 2) for j in joints}, math.sqrt(best)


def at(b, node, offset=(0, 0, 0), values=None):
    """Body-frame position of a point given in a node's frame."""
    R, t = pose(b, values)[node]; o = _app(R, offset); return tuple(t[i]+o[i] for i in range(3))


# ------------------------------------------------------------------------------------------------------------------------------ GU kit
def sif(b, parent, name, at, normal, size, d, active=False, release=True, job=''):
    """GU-SIF fitting: flange, guide probe (passive) or receptacle (active, tool-changer side), three kinematic pins, power/data pad,
    orange manual release on M/L. Face normal along `normal` from `at`."""
    p = d['interface']['sif_plate_m'][size]; t = d['interface']['sif_plate_t_m']*(p/.09)**.5; q = d['interface']['sif_probe']
    n = b.face(name, parent, at, normal, role='sif', job=job or f'GU-SIF-{size} fitting')
    b.box(n, f'SIF_{size}', (0, 0, t/2), (p, p, t), 'graphite', bevel=t*.25, job=f'GU-SIF-{size} flange: kinematic seat, latch, power/data (DGT-012 HOLD)')
    if active:
        b.cyl(n, f'SIF_{size}', (0, 0, t), (0, 0, t+p*.10), p*q['r']*1.6, 'metal', job='active latch ring / receptacle')
        b.cyl(n, f'SIF_{size}', (0, 0, t+p*.10), (0, 0, t+p*.101), p*q['r']*.9, 'lens')
    else:
        b.cyl(n, f'SIF_{size}', (0, 0, t), (0, 0, t+p*q['h']), p*q['r'], 'metal', r2=p*q['r']*.45, job='guide probe')
    for k in range(d['interface']['sif_pins']):
        a = math.radians(90+120*k); r = p*.33
        b.cyl(n, f'SIF_{size}', (r*math.cos(a), r*math.sin(a), t), (r*math.cos(a), r*math.sin(a), t+p*.09), p*.05, 'metal', n=12)
    b.box(n, f'SIF_{size}', (0, -p*.33, t+.001), (p*.30, p*.10, .002), 'metal', job='power / data contact pad')
    if release and size != 'S':
        b.box(n, 'MANUAL_RELEASE', (p*.5+p*.06, 0, t*.5), (p*.12, p*.22, t*.8), 'safety_orange', job='manual latch release (crew glove / arm)')
        b.mark('manual_release', n, 'manual latch release on the GU-SIF flange')
    return n


def target(b, parent, name, at, normal, size, job='docking / grapple alignment target'):
    """ISS-style visual target: dark plate, white ring, standoff post with a white tip."""
    n = b.face(name, parent, at, normal, role='target')
    b.box(n, 'TARGET', (0, 0, .001), (size, size, .002), 'target_black', job=job)
    b.torus(n, 'TARGET', (0, 0, .0025), 'z', size*.32, size*.035, 'target_white')
    b.cyl(n, 'TARGET', (0, 0, .002), (0, 0, size*.55), size*.05, 'target_black', n=12)
    b.cyl(n, 'TARGET', (0, 0, size*.55), (0, 0, size*.60), size*.08, 'target_white', n=12)
    return n


def plate(b, parent, name, at, normal, w, h, label, job='GU qualification and identity plate'):
    n = b.node(name, parent, at, TEXT_FACE[normal], role='id_plate')
    b.box(n, 'ID_PLATE', (0, 0, .001), (w, h, .002), 'gu_blue', job=job)
    b.text(n, 'ID_PLATE', (0, 0, .0025), label, h*.55, 'target_white', job='class code')
    b.mark('id_plate', n, f'{label} plate'); return n


def lamp(b, parent, name, at, normal, r, colour='lamp_green'):
    n = b.face(name, parent, at, normal, role='status_lamp')
    b.cyl(n, 'STATUS_LAMP', (0, 0, 0), (0, 0, r*.6), r*1.25, 'graphite', n=16)
    b.cyl(n, 'STATUS_LAMP', (0, 0, r*.6), (0, 0, r*1.1), r, colour, n=16, job='status lamp: state visible to crew and cameras')
    b.mark('status_lamp', n, 'status lamp'); return n


def estop(b, parent, name, at, normal, r):
    n = b.face(name, parent, at, normal, role='hardware_stop')
    b.cyl(n, 'HARDWARE_STOP', (0, 0, 0), (0, 0, r*.5), r*1.4, 'graphite', n=16)
    b.cyl(n, 'HARDWARE_STOP', (0, 0, r*.5), (0, 0, r*1.2), r, 'safety_orange', r2=r*.85, n=16,
          job='independent hardware stop: cuts drive power, sets brakes, independent of Seraph and FDIR software (DOP-03/13)')
    b.mark('hardware_stop', n, 'hardware stop'); return n


def handle(b, parent, part, a, b_, h, r, mat='grey', job='handling handle'):
    """U handle from a to b_ standing h off along +Z of the node."""
    b.cyl(parent, part, a, (a[0], a[1], a[2]+h), r, mat, n=10)
    b.cyl(parent, part, b_, (b_[0], b_[1], b_[2]+h), r, mat, n=10)
    b.cyl(parent, part, (a[0], a[1], a[2]+h), (b_[0], b_[1], b_[2]+h), r, mat, n=10, job=job)


def camera(b, parent, part, at, normal, r, depth, job='camera / light pair'):
    n = b.face(f'{parent}_{part}_{len(b.order)}', parent, at, normal)
    b.cyl(n, part, (0, 0, 0), (0, 0, depth), r, 'grey', n=16, job=job)
    b.cyl(n, part, (0, 0, depth), (0, 0, depth+.002), r*.75, 'lens', n=16)
    return n


def fasteners(b, node, c, s, axis, inset=.012, r=.0035):
    """Four captive fasteners at the corners of a service cover of size s centred c, standing out along +axis (x/y/z)."""
    i = 'xyz'.index(axis); others = [k for k in range(3) if k != i]
    for u in (-1, 1):
        for v in (-1, 1):
            p = list(c); p[others[0]] += u*(s[others[0]]/2-inset); p[others[1]] += v*(s[others[1]]/2-inset)
            q = list(p); q[i] += .003*(1 if s[i] >= 0 else -1); p[i] -= .0005
            b.cyl(node, 'FASTENER', tuple(p), tuple(q), r, 'metal', n=8)


def cover(b, node, c, s, axis, mat='grey', job='service cover, captive fasteners'):
    b.box(node, 'SERVICE_COVER', c, s, mat, bevel=min(s)*.3, job=job); fasteners(b, node, c, s, axis)


def truck(b, parent, name, x, y, d, rail_r, spin_sign=1.0):
    """Captive rail truck: three wheels at 0 and +-120 deg round the rail (load wheel on top, two under-wheels either side of the rail's
    support web), held by a C-clamp arc open at the bottom. Positive retention in every direction (DOP-03, DGT-004 rating OPEN)."""
    wr, ww = d['interface']['truck_wheel_r_m'], d['interface']['truck_wheel_w_m']; R = rail_r+2*wr+.015
    n = b.node(name, parent, (x, y, 0.0), role='truck', job='captive rail truck')
    b.torus(n, 'RAIL_TRUCK', (0, 0, 0), 'x', R, .010, 'graphite', arc=(-126.0, 126.0), job='C-clamp truck frame, open below for the rail support web')
    b.box(n, 'RAIL_TRUCK', (0, 0, R+.012), (.09, .05, .03), 'graphite', bevel=.006)
    for k, phi in enumerate((0.0, 120.0, -120.0)):
        f = b.node(f'{name}_w{k}f', n, (0, 0, 0), (phi, 0, 0))
        b.box(f, 'RAIL_TRUCK', (0, 0, (rail_r+wr+R)/2+.005), (.022, .016, R-rail_r-wr), 'graphite')
        w = b.node(f'{name}_w{k}', f, (0, 0, rail_r+wr), joint='revolute', axis='y', role='spin', job=f'{"load" if k == 0 else "up-stop"} wheel')
        b.nodes[w]['spin'] = spin_sign*(1 if k == 0 else -1)/wr
        b.cyl(w, 'RAIL_WHEEL', (0, -ww/2, 0), (0, ww/2, 0), wr, 'metal', n=20, job='rail wheel (vacuum-rated bearing, rating OPEN)')
        b.cyl(w, 'RAIL_WHEEL', (0, -ww/2-.002, 0), (0, ww/2+.002, 0), wr*.35, 'graphite', n=12)
        b.box(w, 'RAIL_WHEEL', (wr*.6, 0, 0), (wr*.3, ww*1.1, wr*.18), 'graphite')    # spoke mark: makes spin visible
    return n


def rail_fixture(b, d, rails, length, standoff=.15, dock=None):
    """Review stand (never ship geometry): straight rails on posts above a hull patch, and the dock cradle's mating fitting."""
    rr = d['interface']['rail_radius_m']; n = b.node('fixture', 'root', role='fixture', job='REVIEW FIXTURE: not ship geometry')
    for y in rails:
        b.cyl(n, 'FIXTURE_RAIL', (-length/2, y, 0), (length/2, y, 0), rr, 'metal', n=20, job='GU crawler rail (rating OPEN)')
        k = 0
        while -length/2+.15+k*.6 < length/2:
            x = -length/2+.15+k*.6; k += 1
            b.box(n, 'FIXTURE_RAIL', (x, y, -(standoff+rr)/2), (.03, .012, standoff-rr), 'grey')
            b.box(n, 'FIXTURE_RAIL', (x, y, -standoff+.006), (.08, .06, .012), 'grey')
    w = max(abs(y) for y in rails)*2+.5
    b.box(n, 'FIXTURE_HULL', (0, 0, -standoff-.01), (length+.2, w, .02), 'shell_white', job='hull skin patch (review only)')
    if dock:
        x, size, top = (*dock, None)[:3] if len(dock) == 2 else dock
        if top is None:
            b.box(n, 'FIXTURE_DOCK', (x, 0, -standoff+.03), (.20, .16, .06), 'graphite', bevel=.008, job='dock latch cradle (review only)')
            sif(b, n, 'fixture_dock_sif', (x, 0, -standoff+.06), '+z', size, d, active=True, release=True, job='dock cradle active fitting: latch, charge, data')
        else:
            # PROTOTYPE docking cradle on the review stand (not on the ship; DS-10/11/13 dock design OPEN): a pedestal between the rails
            # rises to the crawler's underside GU-SIF-M; two V-guides take the chassis beam so the fitting meets square; charge / data
            # umbilical, docked lamp and a manual undock release. Latch, charge and alignment ratings OPEN (DGT-012 HOLD).
            seat = top-.03; base = -standoff
            b.box(n, 'FIXTURE_DOCK_CRADLE', (x, 0, base+.012), (.26, .20, .024), 'graphite', bevel=.006, job='PROTOTYPE dock cradle base plate (review stand only)')
            b.box(n, 'FIXTURE_DOCK_CRADLE', (x, 0, (base+.024+seat-.02)/2), (.09, .09, seat-.02-base-.024), 'grey', bevel=.008, job='cradle pedestal')
            b.box(n, 'FIXTURE_DOCK_CRADLE', (x, 0, seat-.01), (.16, .12, .02), 'graphite', bevel=.005, job='cradle head')
            sif(b, n, 'fixture_dock_sif', (x, 0, seat), '+z', size, d, active=True, release=True, job='cradle active fitting: latch, charge, data (ratings OPEN)')
            for sx in (1, -1):
                gx = x+sx*.17
                b.box(n, 'FIXTURE_DOCK_GUIDE', (gx, 0, (base+.024+top+.03)/2), (.02, .05, top+.03-base-.024), 'grey', bevel=.004, job='V-guide post: centres the chassis beam')
                for sy in (1, -1):
                    b.box(n, 'FIXTURE_DOCK_GUIDE', (gx, sy*.062, top+.02), (.02, .022, .05), 'graphite', bevel=.004, job='guide jaw (chassis beam lead-in)')
            b.cyl(n, 'FIXTURE_DOCK_UMBILICAL', (x-.05, .05, base+.024), (x-.05, .05, seat-.03), .010, 'graphite', n=10, job='charge / data umbilical')
            b.box(n, 'FIXTURE_DOCK_UMBILICAL', (x+.10, .085, base+.04), (.05, .03, .03), 'grey', bevel=.004, job='cradle power / data junction')
            b.box(n, 'FIXTURE_DOCK_RELEASE', (x+.10, .102, base+.045), (.018, .006, .018), 'safety_orange', job='manual undock release (recovery robot / crew)')
            b.cyl(n, 'FIXTURE_DOCK_LAMP', (x+.10, .085, base+.055), (x+.10, .085, base+.062), .006, 'lamp_green', n=12, job='docked / charging lamp')
    b.fixtures.append(n); return n


# ------------------------------------------------------------------------------------------------------------------------------ classes
def iva01(d):
    q = d['class']['DR-IVA-01']; L, W, H = q['body_m']; fm = q['fan_module_m']
    b = Body('DR-IVA-01', 'Interior survey free-flyer', 'centred (free flight in pressurised zero-g volumes only)')
    c = b.node('chassis')
    b.box(c, 'BODY_SHELL', (0, 0, 0), (L, W, H), 'shell_white', bevel=.03, job='polymer-composite shell over the avionics core')
    b.box(c, 'BODY_CORE', (0, 0, 0), (L*.9, W*1.02, H*.30), 'graphite', bevel=.008, job='structural belt / bumper ring')
    for sg, side in ((1, 'L'), (-1, 'R')):
        y = sg*(W/2+fm[1]/2+.002)
        b.box(c, 'FAN_MODULE', (0, y, 0), fm, 'shell_white', bevel=.02, job=f'ducted-fan propulsion module {side}: plenum with impeller; needs cabin air (S&E 51)')
        for k in range(7):                                                       # intake grille on the outer face
            z = -fm[2]*.30+k*fm[2]*.10
            b.box(c, 'FAN_GRILLE', (0, y+sg*fm[1]/2, z), (fm[0]*.62, .004, .010), 'graphite')
        b.cyl(c, 'FAN_GRILLE', (0, y+sg*(fm[1]/2-.003), 0), (0, y+sg*(fm[1]/2+.001), 0), fm[2]*.30, 'graphite', n=32)
        for ex, ez in ((1, 1), (1, -1), (-1, 1), (-1, -1)):                     # vectoring exhaust louvres on the fore / aft faces
            b.box(c, 'FAN_NOZZLE', (ex*(fm[0]/2+.001), y, ez*fm[2]*.28), (.004, fm[1]*.6, fm[2]*.16), 'graphite', job='exhaust louvre / nozzle')
        b.box(c, 'BUMPER', (0, y+sg*fm[1]/2, fm[2]/2-.012), (fm[0]*.9, .012, .012), 'rubber', job='soft bumper edge')
        b.box(c, 'BUMPER', (0, y+sg*fm[1]/2, -fm[2]/2+.012), (fm[0]*.9, .012, .012), 'rubber')
    s = b.face('sensor_face', c, (L/2, 0, 0), '+x')
    b.box(s, 'SENSOR_FACE', (0, 0, .004), (H*.62, W*.78, .008), 'graphite', bevel=.004, job='forward sensor face')
    for yy in (-.065, -.030):                                                   # sensor band across the top of the face (local -x is up)
        b.cyl(s, 'CAMERA', (-.06, yy, .008), (-.06, yy, .020), .014, 'grey', n=16, job='stereo navigation / survey cameras')
        b.cyl(s, 'CAMERA', (-.06, yy, .020), (-.06, yy, .022), .010, 'lens', n=16)
    b.box(s, 'DEPTH_SENSOR', (-.06, .040, .012), (.022, .07, .008), 'lens', job='time-of-flight depth sensor')
    b.box(s, 'SURVEY_LIGHT', (.0, 0, .010), (.012, .15, .004), 'target_white', job='survey light bar')
    b.box(s, 'SNIFFER', (.055, .055, .012), (.022, .022, .012), 'metal', job='gas / acoustic leak survey head (S&E 51 mission)')
    b.box(s, 'SNIFFER', (.055, -.04, .010), (.03, .05, .004), 'grey', job='microphone array grille')
    lamp(b, c, 'lamp', (0, 0, H/2), '+z', .010)
    plate(b, c, 'plate', (0, -W/2-fm[1]-.004, H*.32), '-y', .11, .025, 'DR-IVA-01')
    estop(b, c, 'estop', (-L*.22, 0, H/2), '+z', .010)
    sif(b, c, 'dock', (-L/2, 0, 0), '-x', q['dock'], d, job='rear dock fitting: latch, charge, data (DS-01/02 cassette)')
    b.mark('dock', 'dock', 'rear GU-SIF-S'); b.mark('recovery', 'dock', 'rear SIF doubles as the crew / robot recovery grip')
    target(b, c, 'target', (L*.22, 0, H/2), '+z', .04)
    # perching arm (Astrobee-style), folded flat under the body; grips a handrail to hold station without fan power.
    a1, a2 = q['arm_links_m']
    sh = b.node('arm_sh', c, (-L*.30, 0, -H/2-.012), joint='revolute', axis='y', limits=(0, 100), job='perching arm shoulder')
    b.cyl(sh, 'PERCH_ARM', (0, -.03, 0), (0, .03, 0), .012, 'graphite', n=16)
    b.box(sh, 'PERCH_ARM', (a1/2, 0, 0), (a1, .025, .014), 'grey', bevel=.004)
    el = b.node('arm_el', sh, (a1, 0, 0), joint='revolute', axis='y', limits=(0, 170))
    b.cyl(el, 'PERCH_ARM', (0, -.018, 0), (0, .018, 0), .010, 'graphite', n=16)
    b.box(el, 'PERCH_ARM', (-a2/2, 0, -.004), (a2, .022, .012), 'grey', bevel=.004)
    gr = b.node('arm_grip', el, (-a2, 0, -.004), joint='revolute', axis='y', limits=(-40, 40))
    for sg in (1, -1):
        b.box(gr, 'PERCH_GRIPPER', (-.012, sg*.010, -.012), (.024, .006, .024), 'graphite', job='two-finger handrail gripper')
    b.mark('tool', gr, 'perching gripper')
    b.act('undock_survey', [(0, {'root': 0}), (2, {'root': .25}), (4, {'root': .55}), (6, {'root': .55})], 'leave the cassette and translate to the survey point (fan thrust: display time only)')
    b.nodes['root'].update(joint='prismatic', axis='x')
    b.act('perch', [(0, {}), (1.5, {'arm_sh': 90}), (3, {'arm_sh': 90, 'arm_el': 150}), (4, {'arm_sh': 90, 'arm_el': 150, 'arm_grip': -25}), (6, {'arm_sh': 90, 'arm_el': 150, 'arm_grip': -25})],
          'unfold the perching arm and grip a handrail: hold station without fan power')
    b.act('fault_hold', [(0, {'arm_sh': 90, 'arm_el': 150}), (2, {'arm_sh': 0, 'arm_el': 0, 'arm_grip': 0}), (3, {})], 'lost link / low confidence: fold, stop fans, drift-safe and request recovery (DOP-13)')
    return b


def iva02(d):
    q = d['class']['DR-IVA-02']; L, W, H = q['body_m']; wr, ww = q['wheel_r_m'], q['wheel_w_m']
    b = Body('DR-IVA-02', 'Habitat service rover', 'deck (z = 0); ring-local, spin gravity')
    b.nodes['root'].update(joint='prismatic', axis='x')
    c = b.node('chassis'); zc = wr+.01
    b.box(c, 'CHASSIS', (0, 0, zc+H/2), (L, W*.78, H), 'graphite', bevel=.012, job='rover chassis: battery, drives, avionics')
    b.box(c, 'BODY_SHELL', (0, 0, zc+H+.012), (L*.98, W*.92, .024), 'shell_white', bevel=.008, job='cargo deck shell')
    for x in (L*.5-.02, -L*.5+.02):
        b.box(c, 'BUMPER', (x, 0, zc+H*.45), (.03, W*.86, H*.55), 'rubber', bevel=.01, job='bumper (crew-shared corridors)')
    for sx, sy, nm in ((1, 1, 'fl'), (1, -1, 'fr'), (-1, 1, 'rl'), (-1, -1, 'rr')):
        x = sx*(L/2-wr-.02); y = sy*(W/2-ww/2)
        b.box(c, 'SUSPENSION', (x, sy*(W*.39+.004), wr+.02), (.05, .02, .05), 'grey')
        w = b.node(f'wheel_{nm}', c, (x, y, wr), joint='revolute', axis='y', role='spin')
        b.nodes[w]['spin'] = 1/wr
        b.cyl(w, 'WHEEL', (0, -ww/2, 0), (0, ww/2, 0), wr, 'rubber', n=28, job='wheel (traction at ring spin gravity; Coriolis side load OPEN)')
        b.cyl(w, 'WHEEL', (0, -ww/2-.002, 0), (0, ww/2+.002, 0), wr*.55, 'metal', n=20)
        b.box(w, 'WHEEL', (wr*.4, sy*(ww/2+.003), 0), (wr*.5, .003, wr*.18), 'graphite')
    b.box(c, 'GUIDE_SHOE', (0, 0, .012), (.10, .03, .024), 'metal', job='captive guide shoe for a deck guide channel (owner: retained surface guide; channel NOT IN SHIP: interface request)')
    b.mark('dock', c, 'guide shoe and underside fitting seat in the DS-05/07 floor cassette')
    sif(b, c, 'dock', (L*.25, 0, zc), '-z', 'S', d, release=False, job='underside charge / data fitting (floor cassette)')
    deck = zc+H+.024
    cr = b.node('cradle', c, (-L*.12, 0, deck))
    b.box(cr, 'CARGO_CRADLE', (0, 0, .01), (.20, .20, .02), 'grey', bevel=.004, job='cartridge cradle: latching GU-SIF-M seat for Garden / ECLSS cartridges')
    for sx in (1, -1):
        b.box(cr, 'CARGO_CRADLE', (sx*.105, 0, .035), (.012, .16, .05), 'graphite')
    b.box(cr, 'CARGO_CARTRIDGE', (0, 0, .085), (.17, .15, .13), 'shell_white', bevel=.01, job='example service cartridge (filter / sensor module), PROTOTYPE')
    b.box(cr, 'CARGO_CARTRIDGE', (0, -.076, .10), (.10, .002, .03), 'gu_blue')
    handle(b, cr, 'CARGO_CARTRIDGE', (-.04, 0, .15), (.04, 0, .15), .02, .005, job='cartridge handle (crew or arm)')
    # 4-axis arm, folded along the right of the deck
    a1, a2 = q['arm_links_m']
    yaw = b.node('arm_yaw', c, (L*.30, -W*.25, deck), joint='revolute', axis='z', limits=(-170, 170), job='arm base yaw')
    b.cyl(yaw, 'ARM', (0, 0, 0), (0, 0, .035), .03, 'graphite', n=20)
    p1 = b.node('arm_p1', yaw, (0, 0, .05), joint='revolute', axis='y', limits=(-30, 150))
    b.cyl(p1, 'ARM', (0, -.025, 0), (0, .025, 0), .022, 'graphite', n=16)
    b.box(p1, 'ARM', (-a1/2, 0, 0), (a1, .03, .028), 'shell_white', bevel=.008)
    p2 = b.node('arm_p2', p1, (-a1, 0, 0), joint='revolute', axis='y', limits=(-170, 170))
    b.cyl(p2, 'ARM', (0, -.02, 0), (0, .02, 0), .018, 'graphite', n=16)
    b.box(p2, 'ARM', (a2/2, 0, .028), (a2, .026, .024), 'shell_white', bevel=.006)
    wr_ = b.node('arm_wr', p2, (a2, 0, .028), joint='revolute', axis='x')
    b.cyl(wr_, 'ARM', (0, 0, 0), (.025, 0, 0), .016, 'graphite', n=16)
    for sg in (1, -1):
        b.box(wr_, 'GRIPPER', (.045, sg*.012, 0), (.04, .006, .02), 'graphite', job='parallel gripper')
    b.mark('tool', wr_, 'arm gripper')
    m = b.node('mast', c, (L*.40, W*.22, deck), job='sensor mast')
    b.cyl(m, 'SENSOR_MAST', (0, 0, 0), (0, 0, .10), .012, 'grey', n=12)
    b.box(m, 'SENSOR_MAST', (0, 0, .12), (.04, .08, .035), 'grey', bevel=.006)
    camera(b, m, 'CAMERA', (.02, .02, .12), '+x', .010, .008); camera(b, m, 'CAMERA', (.02, -.02, .12), '+x', .010, .008)
    lamp(b, m, 'lamp', (0, 0, .1375), '+z', .008)
    estop(b, c, 'estop', (-L*.40, W*.25, deck), '+z', .012)
    plate(b, c, 'plate', (0, -W*.39-.002, zc+H*.55), '-y', .13, .028, 'DR-IVA-02')
    b.box(c, 'GU_STRIPE', (0, W*.39+.001, zc+H*.55), (L*.7, .002, .012), 'gu_blue')
    rec = b.face('recovery', c, (-L/2-.016, 0, zc+H*.5), '-x', role='recovery')
    b.torus(rec, 'RECOVERY_LOOP', (0, 0, .006), 'z', .02, .005, 'safety_orange', job='recovery / tow eye for crew retrieval')
    b.mark('recovery', rec, 'rear recovery loop')
    dist = .6
    b.act('drive', [(0, {'root': 0}), (4, {'root': dist})], 'drive along the deck guide (display time only; speed OPEN)')
    J = ['arm_yaw', 'arm_p1', 'arm_p2']; hnd = at(b, 'cradle', (0, 0, .19))
    hov, _ = reach(b, 'arm_wr', (hnd[0], hnd[1], hnd[2]+.10), J); grip, err = reach(b, 'arm_wr', (hnd[0], hnd[1], hnd[2]+.03), J, start=hov)
    b.notes.append(f'arm_pick grip residual {err:.3f} m (display pose)')
    b.act('arm_pick', [(0, {}), (1.5, {'arm_p1': 60}), (3, hov), (4.5, grip), (6, hov), (7.5, {})], 'reach over the deck to the cartridge handle and stow (payload OPEN)')
    b.act('fault_hold', [(0, {}), (1, {})], 'stop, brake, stay in the guide and report (DOP-06/13)')
    return b


def iva03(d):
    q = d['class']['DR-IVA-03']; L, W, H = q['body_m']; g = q['waist_gap_m']
    b = Body('DR-IVA-03', 'Micro inspection crawler', 'duct / raceway floor (z = 0); designed service passages only')
    b.nodes['root'].update(joint='prismatic', axis='x')
    def segment(nid, parent, at, sign, joint=None, axis=None):
        n = b.node(nid, parent, at, joint=joint, axis=axis)
        x0 = sign*(L/2)
        b.box(n, 'SEGMENT', (x0, 0, H/2+.006), (L, W*.62, H), 'shell_white', bevel=.008, job='sealed segment shell (contamination wipe-down)')
        for sy in (1, -1):
            b.box(n, 'TRACK', (x0, sy*W*.40, H*.42), (L*1.04, W*.20, H*.84), 'rubber', bevel=.012, job='track module (raceway traction; containment validation OPEN)')
            for k in range(5):
                b.box(n, 'TRACK', (x0-L*.4+k*L*.2, sy*W*.40, .002), (.006, W*.21, .004), 'graphite')
        return n
    r = segment('rear', 'root', (-g/2, 0, 0), -1)
    wj = b.node('waist', 'root', (0, 0, 0), joint='revolute', axis='z', limits=(-35, 35), job='articulated waist (bends in raceway turns)')
    b.cyl(wj, 'WAIST', (0, -W*.22, H*.5), (0, W*.22, H*.5), H*.25, 'graphite', n=16)
    f = segment('front', wj, (g/2, 0, 0), 1)
    head = b.face('head', f, (L, 0, H*.55), '+x')
    b.box(head, 'SENSOR_HEAD', (0, 0, .004), (H*.75, W*.55, .008), 'graphite', bevel=.003)
    b.cyl(head, 'CAMERA', (0, 0, .008), (0, 0, .014), .007, 'lens', n=16, job='inspection camera')
    for yy in (-.016, .016):
        b.cyl(head, 'SURVEY_LIGHT', (0, yy, .008), (0, yy, .011), .004, 'target_white', n=10)
    pr = b.node('probe', f, (L*.6, 0, H+.006), joint='revolute', axis='y', limits=(-60, 0), job='sniffer / contact probe')
    b.cyl(pr, 'PROBE', (0, 0, 0), (.06, 0, 0), .003, 'metal', n=8, job='leak sniffer / sensor probe (accessible probes only, S&E 51)')
    b.cyl(pr, 'PROBE', (0, -.006, 0), (0, .006, 0), .006, 'graphite', n=10)
    lamp(b, f, 'lamp', (L*.2, 0, H+.006), '+z', .004)
    plate(b, r, 'plate', (-L*.5, 0, H+.006), '+z', .05, .014, 'IVA-03')
    estop(b, r, 'estop', (-L*.15, 0, H+.006), '+z', .005)
    rec = b.face('recovery', r, (-L-.002, 0, H*.5), '-x', role='recovery')
    b.box(rec, 'SIF_S', (0, 0, .004), (.035, .035, .008), 'graphite', job='tapered pull fitting: a jammed unit can be drawn back out by its tether')
    b.torus(rec, 'RECOVERY_LOOP', (0, 0, .010), 'z', .008, .0025, 'safety_orange', job='recovery tether eye (retrieval after a jam, DOP-14)')
    b.mark('recovery', rec, 'rear tether eye and pull fitting'); b.mark('dock', rec, 'rear pull fitting doubles as the cassette charge seat')
    b.act('crawl', [(0, {'root': 0, 'waist': 0}), (2, {'root': .12, 'waist': 20}), (4, {'root': .24, 'waist': -15}), (5, {'root': .30, 'waist': 0})], 'crawl along a raceway, articulating at the waist')
    b.act('probe_inspect', [(0, {}), (1.5, {'probe': -45}), (3, {'probe': -45}), (4, {'probe': 0})], 'lower the sniffer probe at a sensor port')
    b.act('jam_recover', [(0, {'root': .2}), (1, {'root': .2, 'waist': 10}), (3, {'root': .0, 'waist': 0})], 'jam: stop, report, drawn back out on the recovery tether (DOP-14)')
    return b


def _crawler_common(b, d, cid, L, W, zc, H, label):
    """Shared EVA body: chassis beam, white vault, radiator lid, service covers, plate, stripe, lamp, stop, end fittings."""
    c = b.node('chassis', 'travel')
    b.box(c, 'CHASSIS', (0, 0, zc+.022), (L, .10, .044), 'graphite', bevel=.006, job='structural spine beam: truck and fitting load path')
    vz = zc+.044+H/2
    b.box(c, 'VAULT', (0, 0, vz), (L*.92, W, H), 'beta_white', bevel=.014, job='avionics / battery vault in beta-cloth MLI')
    for sy in (1, -1):
        for x in (-L*.2, L*.2):
            cover(b, c, (x, sy*(W/2+.002), vz), (L*.28, .004, H*.6), 'y')
    top = zc+.044+H
    b.box(c, 'RADIATOR', (-L*.04, 0, top+.004), (L*.70, W*.80, .008), 'radiator', job='silvered-Teflon radiator lid: rejects avionics heat to space (size from heat load OPEN)')
    plate(b, c, 'plate', (L*.08, W/2+.005, vz+H*.18), '+y', .13, .028, label)
    b.box(c, 'GU_STRIPE', (L*.46-.008, 0, vz), (.004, W*1.0, .016), 'gu_blue', job='GU institutional stripe')
    lamp(b, c, 'lamp', (L*.40, W*.30, top), '+z', .009, 'lamp_amber')
    estop(b, c, 'estop', (-L*.40, W*.28, top), '+z', .013)
    handle(b, c, 'CREW_HANDLE', (L*.22, -W*.42, top), (-L*.10, -W*.42, top), .03, .006, job='crew / arm handling handle')
    return c, vz, top


def _rail_crawler_ends(b, d, c, L, vz, size='M'):
    sif(b, c, 'tow_fwd', (L*.46, 0, vz), '+x', size, d, job='forward GU-SIF: tow / capture by another crawler or an arm (DOP-14)')
    sif(b, c, 'tow_aft', (-L*.46, 0, vz), '-x', size, d, job='aft GU-SIF: tow / capture (DOP-14)')
    b.mark('recovery', 'tow_fwd', 'forward GU-SIF tow fitting'); b.mark('recovery', 'tow_aft', 'aft GU-SIF tow fitting')


def _arm(b, parent, at, links, d, prefix='arm', stow_z=0.0, white='beta_white', tool='S', roll=True):
    """Folding arm: yaw, shoulder pitch, link 1 forward, elbow, link 2 folded back (offset in y), wrist pitch (+ roll), GU-SIF tool changer."""
    a1, a2 = links
    y = b.node(f'{prefix}_yaw', parent, at, joint='revolute', axis='z', limits=(-180, 180), job='arm yaw')
    b.cyl(y, 'ARM', (0, 0, 0), (0, 0, .02), .034, 'graphite', n=20)
    p = b.node(f'{prefix}_sh', y, (0, 0, .034), joint='revolute', axis='y', limits=(-150, 10), job='shoulder pitch')
    b.cyl(p, 'ARM', (0, -.03, 0), (0, .03, 0), .026, 'graphite', n=20)
    drive(b, p, (0, -.03, 0), -1, .024, job='shoulder drive: motor, harmonic gear and power-off brake (torque OPEN)')
    b.box(p, 'ARM', (a1/2, 0, 0), (a1, .042, .036), white, bevel=.01, job='arm boom 1')
    b.box(p, 'ARM_HARNESS', (a1/2, -.023, .006), (a1*.8, .006, .012), 'graphite', job='joint harness run (power / data / heater)')
    e = b.node(f'{prefix}_el', p, (a1, .045, 0), joint='revolute', axis='y', limits=(-175, 175), job='elbow (offset links: folds either way)')
    b.cyl(e, 'ARM', (0, -.026, 0), (0, .026, 0), .022, 'graphite', n=20)
    drive(b, e, (0, .026, 0), 1, .020, job='elbow drive with power-off brake')
    b.box(e, 'ARM', (-a2/2, 0, 0), (a2, .036, .032), white, bevel=.008, job='arm boom 2')
    b.box(e, 'ARM_HARNESS', (-a2/2, .020, .005), (a2*.75, .005, .010), 'graphite', job='joint harness run')
    camera(b, e, 'ARM_CAMERA', (-a2*.3, 0, .016), '+z', .009, .012, job='elbow camera')
    w = b.node(f'{prefix}_wp', e, (-a2, 0, 0), joint='revolute', axis='y', limits=(-150, 150), job='wrist pitch')
    b.cyl(w, 'ARM', (0, -.02, 0), (0, .02, 0), .019, 'graphite', n=16)
    drive(b, w, (0, -.02, 0), -1, .016, job='wrist drive with power-off brake')
    r = b.node(f'{prefix}_wr', w, (-.03, 0, 0), joint='revolute' if roll else None, axis='x', job='wrist roll')
    b.cyl(r, 'ARM', (0, 0, 0), (-.02, 0, 0), .02, 'graphite', n=16)
    sif(b, r, f'{prefix}_tool', (-.02, 0, 0), '-x', tool, d, active=True, release=False, job='tool changer: active GU-SIF accepts any GU cartridge of its size (DOP-11)')
    b.mark('tool', r, 'tool changer')
    # stow saddle under the folded booms at the elbow end: the arm rests and latches here for thrust (1.5 g) and power loss (DOP-03, DOP-13)
    sx, sy, sz = at[0]+a1*.82, at[1]+.0225, at[2]+stow_z
    b.box(parent, 'ARM_STOW', (sx, sy, sz+.008), (.05, .10, .016), 'graphite', bevel=.003, job='arm stow saddle with launch latch (latch rating OPEN)')
    b.box(parent, 'ARM_STOW', (sx, sy-.054, sz+.018), (.016, .008, .02), 'safety_orange', job='stow latch manual release (crew / recovery robot)')
    return y


def drive(b, node, at, side, r, job):
    """A joint drive housing on the outer face of a pitch joint: motor can, brake ring and a connector."""
    x, y, z = at; y2 = y+side*.022
    b.cyl(node, 'ARM_DRIVE', (x, y, z), (x, y2, z), r, 'grey', n=20, job=job)
    b.cyl(node, 'ARM_DRIVE', (x, y2, z), (x, y2+side*.003, z), r*.82, 'metal', n=20)
    b.box(node, 'ARM_DRIVE', (x+r*.7, y+side*.011, z+r*.5), (.010, .012, .010), 'graphite')


def eva01(d, s):
    q = d['class']['DR-EVA-01']; L, W, H = q['body_m']; g = d['interface']['rail_gauge_m']; rr = d['interface']['rail_radius_m']
    b = Body('DR-EVA-01', 'Forward Brow / EYE service crawler', 'twin rail on the shield truss aft face (z = 0 at the rails)')
    b.node('travel', 'root', joint='prismatic', axis='x', job='travel along the rail')
    zc = rr+2*d['interface']['truck_wheel_r_m']+.03
    for k, x in enumerate((L*.36, -L*.36)):
        for sy in (1, -1):
            truck(b, 'travel', f'truck{k}{"lr"[sy < 0]}', x, sy*g/2, d, rr)
    c, vz, top = _crawler_common(b, d, 'DR-EVA-01', L, W, zc, H, 'DR-EVA-01')
    _rail_crawler_ends(b, d, c, L, vz)
    sif(b, c, 'dock', (0, 0, zc), '-z', 'M', d, job='underside dock fitting (DS-10 cradle): latch, charge, data')
    b.mark('dock', 'dock', 'underside GU-SIF-M')
    # ORU bay: an exchangeable service module carried in clamshell latches on the deck
    o = q['oru_m']; ob = b.node('oru_bay', c, (L*.02, W/2-o[1]/2-.02, top+.008))
    for sx in (1, -1):
        cl = b.node(f'clam_{"fa"[sx < 0]}', ob, (sx*(o[0]/2+.012), 0, 0), joint='revolute', axis='y', limits=(-80, 80), job='clamshell latch arm')
        b.box(cl, 'ORU_LATCH', (0, 0, o[2]*.45), (.012, o[1]*.7, o[2]*.9), 'graphite', bevel=.004)
        b.box(cl, 'ORU_LATCH', (-sx*.012, 0, o[2]*.86), (.024, o[1]*.6, .012), 'metal')
    om = b.node('oru', ob, (0, 0, 0), job='carried service module')
    b.box(om, 'ORU_MODULE', (0, 0, o[2]/2), o, 'shell_white', bevel=.012, job='example Brow / EYE service module (ORU) with GU-SIF-M grapple (EYE 46 interface, PROTOTYPE)')
    target(b, om, 'oru_target', (o[0]*.25, 0, o[2]), '+z', .045)
    sif(b, om, 'oru_sif', (-o[0]*.2, 0, o[2]), '+z', 'S', d, release=False, job='ORU grapple fitting')
    b.box(om, 'ORU_MODULE', (0, o[1]/2+.001, o[2]*.6), (o[0]*.7, .002, .02), 'gu_blue')
    for sx in (1, -1):                                       # guide frame: four corner posts lead a module into the clamshell
        for sy in (1, -1):
            gx, gy = sx*(o[0]/2+.004), sy*(o[1]/2+.004)
            b.box(ob, 'ORU_GUIDE', (gx, gy, o[2]*.32), (.014, .014, o[2]*.64), 'graphite', bevel=.003, job='ORU guide post (module alignment)')
            b.cyl(ob, 'ORU_GUIDE', (gx, gy, o[2]*.64), (gx, gy, o[2]*.72), .009, 'metal', r2=.004, n=10, job='guide lead-in cone')
    b.box(ob, 'ORU_GUIDE', (0, 0, -.004), (o[0]+.03, o[1]+.03, .008), 'graphite', job='ORU bay seat with module data / power connector')
    # short 4-axis arm on the forward deck, periscope camera aft
    _arm(b, c, (-L*.32, -W*.28, top), q['arm_links_m'], d, roll=False)
    pm = b.node('peri_base', c, (L*.38, -W*.05, top))
    b.cyl(pm, 'PERISCOPE', (0, 0, 0), (0, 0, q['periscope_m'][0]), .022, 'grey', n=16, job='periscope mast housing')
    pe = b.node('peri', pm, (0, 0, 0), joint='prismatic', axis='z', limits=(0, q['periscope_m'][1]-q['periscope_m'][0]), job='telescoping periscope')
    b.cyl(pe, 'PERISCOPE', (0, 0, .02), (0, 0, q['periscope_m'][0]+.01), .015, 'metal', n=16)
    ph = b.node('peri_pan', pe, (0, 0, q['periscope_m'][0]+.01), joint='revolute', axis='z')
    b.box(ph, 'PERISCOPE', (0, 0, .02), (.07, .07, .04), 'grey', bevel=.008, job='Brow inspection head: stereo cameras, ranging and lights on the periscope')
    camera(b, ph, 'CAMERA', (.035, .018, .018), '+x', .011, .006, job='periscope stereo camera: looks round truss members and into EYE apertures from the safe side')
    camera(b, ph, 'CAMERA', (.035, -.018, .018), '+x', .011, .006)
    b.box(ph, 'SURVEY_LIGHT', (.036, 0, .034), (.004, .05, .007), 'target_white', job='inspection light bar')
    b.act('traverse', [(0, {'travel': 0}), (5, {'travel': .8})], 'traverse along the protected aft-face rail (display time; speed OPEN)')
    J = ['arm_yaw', 'arm_sh', 'arm_el', 'arm_wp']; op = {'clam_f': 50, 'clam_a': -50}
    g0 = at(b, 'oru_sif', (0, 0, .03)); g1 = (g0[0], g0[1], g0[2]+.10)
    hov, _ = reach(b, 'arm_tool', g1, J, approach=(0, 0, -1)); seat, err = reach(b, 'arm_tool', g0, J, start=hov, approach=(0, 0, -1))
    b.notes.append(f'oru_exchange grapple residual {err:.3f} m (display pose)')
    b.act('oru_exchange', [(0, {}), (1.5, op), (3.5, dict(op, **hov)), (5, dict(op, **seat)), (7, dict(op, **seat)), (8.5, dict(op, **hov)), (10, {})],
          'open the clamshell latches and seat the tool changer on the carried module\'s grapple fitting (module transfer to its worksite not animated; interface PROTOTYPE)')
    b.act('periscope', [(0, {}), (2, {'peri': .12}), (4, {'peri': .12, 'peri_pan': 120}), (6, {'peri': .12, 'peri_pan': -120}), (8, {})], 'raise the periscope and pan')
    b.act('fault_hold', [(0, {'arm_sh': -60, 'arm_el': 120}), (2, {'arm_sh': 0, 'arm_el': 0}), (3, {})], 'stow arm, brakes on the trucks, report (DOP-06/13)')
    rail_fixture(b, d, (g/2, -g/2), d['interface']['fixture_rail_len_m'], dock=(0.0, 'M', zc))
    return b


def eva02(d, s):
    q = d['class']['DR-EVA-02']; L, W, H = q['body_m']; g = d['interface']['rail_gauge_m']; rr = d['interface']['rail_radius_m']
    b = Body('DR-EVA-02', 'Radiator service crawler', 'twin rail at the radiator root, cold side (z = 0 at the rails)')
    b.node('travel', 'root', joint='prismatic', axis='x')
    zc = rr+2*d['interface']['truck_wheel_r_m']+.03
    for k, x in enumerate((L*.36, -L*.36)):
        for sy in (1, -1):
            truck(b, 'travel', f'truck{k}{"lr"[sy < 0]}', x, sy*g/2, d, rr)
    c, vz, top = _crawler_common(b, d, 'DR-EVA-02', L, W, zc, H, 'DR-EVA-02')
    _rail_crawler_ends(b, d, c, L, vz)
    sif(b, c, 'dock', (0, 0, zc), '-z', 'M', d, job='underside dock fitting (DS-11 HOME dock / unpowered stops)')
    b.mark('dock', 'dock', 'underside GU-SIF-M')
    # heat-shield wall on the blade side (+Y): stacked specular layers with gaps, on standoffs
    sl, sh = q['shield_m']; n = q['shield_layers']
    hs = b.node('shield', c, (0, W/2+.03, zc))
    for k in range(n):
        b.box(hs, 'HEAT_SHIELD', (0, k*.016, sh/2), (sl-k*.03, .004, sh-k*.02), 'radiator' if k == n-1 else 'metal',
              job='specular heat-shield layer: reflects blade radiation; no rating, view factor or cooldown released (DGT-007 HOLD)')
    for x in (-sl*.4, 0, sl*.4):
        b.box(hs, 'HEAT_SHIELD', (x, -.012, sh*.45), (.016, .03, sh*.85), 'graphite')
    for x in (-L*.2, L*.2):                                  # blade-side vault faces silvered (low absorptance toward the root)
        b.box(c, 'THERMAL_FACE', (x, W/2+.004, vz), (L*.30, .003, H*.70), 'radiator', job='silvered hot-side face (optical properties OPEN)')
    dfl = b.node('deflector', c, (0, W*.10, top+.022))
    b.box(dfl, 'DEFLECTOR', (0, 0, 0), (L*.80, W*.60, .006), 'metal', job='upper deflector: shades the deck from the blade root (view factor OPEN, DGT-007 HOLD)')
    for x in (-L*.32, L*.32):
        for y in (-W*.22, W*.22):
            b.cyl(dfl, 'DEFLECTOR', (x, y, -.003), (x, y, -.018), .006, 'graphite', n=8, job='deflector standoff (low-conductance)')
    irp = b.node('ir_pan', dfl, (L*.30, W*.12, .003), joint='revolute', axis='z', limits=(-170, 170), job='radiometer pan')
    b.box(irp, 'IR_TURRET', (0, 0, .02), (.06, .05, .04), 'grey', bevel=.006, job='IR radiometer / thermal imager: maps root and blade temperature before any approach (DOP-08)')
    b.cyl(irp, 'IR_TURRET', (0, .025, .02), (0, .055, .02), .016, 'graphite', r2=.022, n=16, job='radiometer sunshade cone')
    # leak-locator boom (RELL-type mass spectrometer) forward, valve-drive arm aft
    l1, l2 = q['boom_links_m']
    by = b.node('boom_yaw', c, (L*.30, -W*.20, top), joint='revolute', axis='z')
    b.cyl(by, 'LEAK_BOOM', (0, 0, 0), (0, 0, .03), .026, 'graphite', n=16)
    bp = b.node('boom_p', by, (0, 0, .04), joint='revolute', axis='y', limits=(-120, 0))
    b.cyl(bp, 'LEAK_BOOM', (0, 0, 0), (-l1, 0, 0), .012, 'metal', n=12, job='sensor boom')
    bp2 = b.node('boom_p2', bp, (-l1, 0, 0), joint='revolute', axis='y', limits=(-180, 0))
    b.cyl(bp2, 'LEAK_BOOM', (0, 0, 0), (l2, 0, .01), .010, 'metal', n=12)
    hd = b.node('leak_head', bp2, (l2, 0, .01))
    b.box(hd, 'LEAK_SENSOR', (.03, 0, 0), (.06, .045, .04), 'grey', bevel=.006, job='leak sensor head: mass spectrometer + ion gauge (ancestry NASA RELL)')
    b.cyl(hd, 'LEAK_SENSOR', (.06, 0, 0), (.08, 0, 0), .012, 'metal', r2=.006, n=12)
    b.mark('tool', hd, 'leak sensor head')
    _arm(b, c, (-L*.30, -W*.22, top), q['arm_links_m'], d)
    camera(b, c, 'THERMAL_CAMERA', (L*.46, -W*.28, vz+H*.3), '+x', .014, .02, job='thermal IR camera: remote cold-state check before any approach (DOP-08)')
    b.act('traverse', [(0, {'travel': 0}), (5, {'travel': .8})], 'traverse the root track, shield toward the blade (cold state only)')
    b.act('leak_scan', [(0, {}), (2, {'boom_yaw': 170, 'boom_p': -70, 'boom_p2': -140}), (4, {'boom_yaw': 130, 'boom_p': -60, 'boom_p2': -150}),
                        (6, {'boom_yaw': -150, 'boom_p': -60, 'boom_p2': -150}), (8, {})], 'sweep the leak-sensor head along a root joint')
    b.act('thermal_survey', [(0, {}), (2, {'ir_pan': 90}), (4, {'ir_pan': -90}), (6, {})], 'pan the IR radiometer across the root and blade before an approach (cold-state check, DOP-08)')
    b.act('valve_service', [(0, {}), (2, {'arm_yaw': -90, 'arm_sh': -70, 'arm_el': 130}), (3.5, {'arm_yaw': -90, 'arm_sh': -60, 'arm_el': 140, 'arm_wp': -60}),
                            (5, {'arm_yaw': -90, 'arm_sh': -60, 'arm_el': 140, 'arm_wp': -60, 'arm_wr': 270}), (7, {})], 'engage an accessible valve drive and turn it (torque OPEN)')
    b.act('fault_hold', [(0, {'boom_p': -70}), (2, {}), (3, {})], 'thermal or link fault: stow, retreat to the HOME dock or hold braked (DOP-08/13)')
    rail_fixture(b, d, (g/2, -g/2), d['interface']['fixture_rail_len_m'], dock=(0.0, 'M', zc))
    return b


# The review action and time (s) each class is shown at (previews, the accessory viewer)
MAIN = {'DR-IVA-01': ('perch', 4), 'DR-IVA-02': ('arm_pick', 3), 'DR-IVA-03': ('probe_inspect', 1.5), 'DR-EVA-01': ('oru_exchange', 5),
        'DR-EVA-02': ('leak_scan', 4), 'DR-EVA-03': ('tool_present', 4.5), 'DR-EVA-04': ('boom_survey', 5), 'DR-FIX-01': ('unstow', 6),
        'DR-FIX-02': ('unstow', 6)}
CREW_HANDLE = ((-.062, -.05, .035), (-.062, .05, .035), .011)      # DR-EVA-03 cartridge crew handle: end, end (node frame), radius


def eva03(d, s):
    q = d['class']['DR-EVA-03']; L, W, H = q['body_m']; g = d['interface']['rail_gauge_m']; rr = d['interface']['rail_radius_m']
    b = Body('DR-EVA-03', 'Spine utility crawler', 'twin rail on the stationary casing (z = 0 at the rails)')
    b.node('travel', 'root', joint='prismatic', axis='x')
    zc = rr+2*d['interface']['truck_wheel_r_m']+.03
    for k, x in enumerate((L*.34, -L*.34)):
        for sy in (1, -1):
            truck(b, 'travel', f'truck{k}{"lr"[sy < 0]}', x, sy*g/2, d, rr)
    c, vz, top = _crawler_common(b, d, 'DR-EVA-03', L, W, zc, H, 'DR-EVA-03')
    _rail_crawler_ends(b, d, c, L, vz)
    sif(b, c, 'dock', (0, 0, zc), '-z', 'M', d, job='underside dock fitting (DS-13 docks): latch, charge, data')
    b.mark('dock', 'dock', 'underside GU-SIF-M')
    target(b, c, 'target', (L*.30, -W*.05, top+.008), '+z', .05)
    # pan-tilt camera head forward
    pan = b.node('cam_pan', c, (L*.40, W*.05, top), joint='revolute', axis='z', limits=(-170, 170))
    b.cyl(pan, 'CAMERA_HEAD', (0, 0, 0), (0, 0, .04), .016, 'graphite', n=16)
    tilt = b.node('cam_tilt', pan, (0, 0, .055), joint='revolute', axis='y', limits=(-60, 90))
    b.box(tilt, 'CAMERA_HEAD', (0, 0, 0), (.05, .09, .045), 'grey', bevel=.008, job='pan-tilt inspection head')
    camera(b, tilt, 'CAMERA', (.025, .022, 0), '+x', .011, .006, job='inspection camera (stereo)'); camera(b, tilt, 'CAMERA', (.025, -.022, 0), '+x', .011, .006)
    b.box(tilt, 'SURVEY_LIGHT', (.026, 0, .015), (.004, .03, .008), 'target_white', job='work light')
    # the arm parks its current tool cartridge in a deck cradle (stowed = tool latched in its cradle); a spare cartridge rides in the caddy
    _arm(b, c, (-L*.36, -W*.22, top), q['arm_links_m'], d)
    tc = b.node('cartridge', 'arm_tool', (0, 0, .013), joint='prismatic', axis='z', limits=(0, .03), job='tool cartridge on the tool changer')
    b.box(tc, 'TOOL_CARTRIDGE', (0, 0, .035), (.05, .05, .07), 'graphite', bevel=.005, job='torque / fastener tool cartridge (GU-SIF-S base)')
    b.box(tc, 'TOOL_CARTRIDGE', (0, .026, .04), (.002, .002, .002), 'graphite')
    b.box(tc, 'TOOL_CARTRIDGE', (.026, 0, .035), (.002, .03, .012), 'gu_blue')
    b.cyl(tc, 'TOOL_BIT', (0, 0, .07), (0, 0, .095), .008, 'metal', r2=.005, n=12, job='hex drive bit')
    # crew D-handle on the -x face: a gloved hand closes on a 22 mm bar 0.10 m long (EVA glove clearance, ASSET-07); the arm keeps the
    # cartridge latched until the crew member's grip is confirmed (DOP-04 supervised handoff; latch and grip ratings OPEN)
    for y in (-.038, .038):
        b.cyl(tc, 'TOOL_CARTRIDGE', (-.025, y, .035), (-.062, y, .035), .006, 'grey', n=10)
    b.cyl(tc, 'CREW_HANDLE', CREW_HANDLE[0], CREW_HANDLE[1], CREW_HANDLE[2], 'metal', n=16, job='crew handle (handoff grip), knurled metal: reads against the glove grip pads')
    p0 = at(b, 'cartridge', (0, 0, .035)); cz = top+.008
    b.box(c, 'TOOL_CRADLE', (p0[0], p0[1], (cz+p0[2]-.026)/2), (.08, .05, p0[2]-.026-cz), 'grey', bevel=.004, job='tool cradle: holds the parked cartridge under 1.5 g (latch rating OPEN)')
    cd = b.node('caddy', c, (-L*.02, W*.26, top+.008))
    # tool magazine: three cartridge slots on keyed GU-SIF-S seats (torque spare, inspection probe, gripper); DGT-012 standard HOLD
    b.box(cd, 'TOOL_CADDY', (0, 0, .012), (.21, .075, .024), 'grey', bevel=.006, job='tool magazine: three keyed cartridge seats (DGT-012 standard HOLD)')
    b.box(cd, 'TOOL_CADDY', (0, -.04, .04), (.21, .006, .05), 'graphite', job='magazine retaining wall')
    for k, (x, tip, job) in enumerate(((-.07, 'bit', 'spare torque cartridge'), (0.0, 'probe', 'inspection-probe cartridge'), (.07, 'jaw', 'gripper cartridge'))):
        b.box(cd, 'TOOL_CARTRIDGE', (x, 0, .059), (.05, .05, .07), 'graphite', bevel=.005, job=job)
        b.box(cd, 'TOOL_CARTRIDGE', (x, -.026, .065), (.03, .002, .012), 'gu_blue')
        if tip == 'bit':
            b.cyl(cd, 'TOOL_BIT', (x, 0, .094), (x, 0, .104), .007, 'metal', r2=.004, n=10)
        elif tip == 'probe':
            b.cyl(cd, 'TOOL_BIT', (x, 0, .094), (x, 0, .106), .005, 'metal', n=10)
        else:
            for sy in (-1, 1):
                b.box(cd, 'TOOL_BIT', (x, sy*.012, .1), (.02, .006, .012), 'metal')
    sif(b, cd, 'spare_sif', (0, 0, .094), '+z', 'S', d, release=False)
    # crew assistance on the -Y (crew) side: a handrail a suited hand can close on, and a tether anchor ring (ratings OPEN)
    for x in (L*.30, -L*.30):
        b.cyl(c, 'CREW_RAIL', (x, -W/2-.01, vz+H*.25), (x, -W/2-.05, vz+H*.25), .008, 'grey', n=10, job='crew handrail standoff')
    b.cyl(c, 'CREW_RAIL', (L*.33, -W/2-.05, vz+H*.25), (-L*.33, -W/2-.05, vz+H*.25), .0125, 'metal', n=14, job='crew handrail: 25 mm bar, a suited crew member steadies on the crawler (handhold rating OPEN)')
    b.box(c, 'TETHER_ANCHOR', (-L*.44, -W/2+.01, vz+H*.35), (.03, .02, .03), 'graphite', bevel=.004, job='crew tether anchor (rating OPEN; never a primary anchor, DOP-04)')
    b.cyl(c, 'TETHER_ANCHOR', (-L*.44, -W/2-.012, vz+H*.35+.004), (-L*.44, -W/2-.016, vz+H*.35+.004), .014, 'safety_orange', n=14, job='tether anchor ring tag')
    J = ['arm_yaw', 'arm_sh', 'arm_el', 'arm_wp']
    up = {'arm_sh': -55, 'arm_el': 70}
    work = (L*.45, -W*.85, zc)                                                # a worksite beside the track, inside the arm's display reach
    wk, err = reach(b, 'arm_tool', work, J, approach=(1, 0, 0))
    b.notes.append(f'tool_present worksite residual {err:.3f} m (display pose)')
    b.act('traverse', [(0, {'travel': 0}), (6, {'travel': 1.0})], 'traverse along the casing track (display time; speed OPEN; no traversal while hot blades operate, DS-13 OPERATIONS HOLD)')
    b.act('inspect', [(0, {}), (1.5, {'cam_pan': 60, 'cam_tilt': 30}), (3, {'cam_pan': -60, 'cam_tilt': 30}), (4.5, {'cam_pan': 0, 'cam_tilt': -20}), (6, {})], 'pan-tilt survey of a structural node / harness')
    b.act('tool_present', [(0, {}), (1.0, {'arm_sh': -12, 'arm_el': 10}), (2.5, up), (4.5, wk), (5.5, dict(wk, arm_wr=180)), (6.5, dict(wk, arm_wr=360)),
                           (8.5, up), (10, {})],
          'lift the parked cartridge from its cradle, present it at a worksite beside the track, turn the drive, return and park (display poses)')
    hand = (L*.10, -W*1.15, .72)                                              # a suited crew member's glove beside the track (review scene)
    ho, _ = reach(b, 'arm_tool', hand, J, approach=(0, -1, 0))
    b.act('handoff', [(0, {}), (2, {'arm_sh': -60, 'arm_el': 60}), (4, ho), (7, ho), (9, {})],
          'present a tool to a suited crew member beside the track (supervised handoff, DOP-04; FLIGHT_EVA HOLD)')
    b.act('fault_hold', [(0, {'arm_sh': -50, 'arm_el': 80}), (1.5, {'arm_sh': 0, 'arm_el': 0}), (3, {})], 'power loss / jam / lost link: stow, brake, hold and report; wait for retrieval (DOP-13/14)')
    rail_fixture(b, d, (g/2, -g/2), d['interface']['fixture_rail_len_m'], dock=(0.0, 'M', zc))
    return b


def eva04(d, s):
    q = d['class']['DR-EVA-04']; L, W, H = q['body_m']; rr = d['interface']['rail_radius_m']
    b = Body('DR-EVA-04', 'Aft propulsion inspection crawler', 'mono rail on the aft casing (z = 0 at the rail)')
    b.node('travel', 'root', joint='prismatic', axis='x')
    zc = rr+2*d['interface']['truck_wheel_r_m']+.03
    for k, x in enumerate((L*.32, -L*.32)):
        truck(b, 'travel', f'truck{k}', x, 0.0, d, rr)
    c = b.node('chassis', 'travel')
    b.box(c, 'CHASSIS', (0, 0, zc+.016), (L, .08, .032), 'graphite', bevel=.005)
    vz = zc+.032+H/2
    b.box(c, 'VAULT', (0, 0, vz), (L*.92, W, H), 'graphite', bevel=.012, job='dense shielded electronics vault (radiation-tolerant core; shielding mass OPEN)')
    b.box(c, 'MLI', (0, 0, vz+.002), (L*.86, W*1.04, H*.86), 'mli_gold', bevel=.02, job='aluminised-polyimide MLI wrap (cryogenic-adjacent zone)')
    top = zc+.032+H
    b.box(c, 'RADIATOR', (0, 0, top+.004), (L*.60, W*.70, .008), 'radiator')
    plate(b, c, 'plate', (0, -W/2-.012, vz), '-y', .10, .022, 'DR-EVA-04')
    lamp(b, c, 'lamp', (-L*.30, -W*.25, top), '+z', .007, 'lamp_amber')
    estop(b, c, 'estop', (-L*.30, W*.25, top), '+z', .010)
    sif(b, c, 'dock', (-L/2, 0, vz), '-x', q['dock'], d, job='aft dock / recovery fitting (DS-14 cassette)')
    b.mark('dock', 'dock', 'aft GU-SIF-S'); b.mark('recovery', 'dock', 'aft GU-SIF-S is the retrieval grip for DR-FIX-02 (DGT-019 (a))')
    target(b, c, 'target', (L*.05, W*.2, top+.008), '+z', .035)
    bb = b.node('boom_base', c, (L*.30, 0, top))
    b.box(bb, 'SENSOR_BOOM', (0, 0, .012), (.08, .06, .024), 'grey', bevel=.006)
    bt = b.node('boom_tilt', bb, (0, 0, .03), joint='revolute', axis='y', limits=(-80, 10))
    r0, r1 = q['boom_m']
    b.cyl(bt, 'SENSOR_BOOM', (-r0*.85, 0, 0), (.02, 0, 0), .016, 'metal', n=16, job='telescoping boom (stowed aft along the body)')
    # two telescoping stages, each overlapping the one outside it at full extension (one stage could not span the stroke)
    ex = b.node('boom_ext', bt, (0, 0, 0), joint='prismatic', axis='x', limits=(0, (r1-r0)/2), job='boom stage 1')
    b.cyl(ex, 'SENSOR_BOOM', (-r0*.80, 0, 0), (.03, 0, 0), .012, 'metal', n=12)
    ex2 = b.node('boom_ext2', ex, (0, 0, 0), joint='prismatic', axis='x', limits=(0, (r1-r0)/2), job='boom stage 2')
    b.cyl(ex2, 'SENSOR_BOOM', (-r0*.75, 0, 0), (.06, 0, 0), .008, 'metal', n=12)
    hd = b.node('sensor_head', ex2, (.06, 0, 0), joint='revolute', axis='x')
    b.box(hd, 'SENSOR_HEAD', (.03, 0, 0), (.06, .05, .05), 'grey', bevel=.008, job='non-contact sensor head: thermal IR, gas, magnetometer, camera; never touches hazard hardware (DOP-09)')
    camera(b, hd, 'CAMERA', (.06, .012, 0), '+x', .010, .006); camera(b, hd, 'CAMERA', (.06, -.014, .012), '+x', .007, .006, job='thermal IR')
    b.mark('tool', hd, 'non-contact sensor head')
    b.act('traverse', [(0, {'travel': 0}), (5, {'travel': .6})], 'traverse the retained aft path with the drive isolated (DOP-09 HOLD)')
    out = {'boom_tilt': -35, 'boom_ext': .20, 'boom_ext2': .20}
    b.act('boom_survey', [(0, {}), (1.5, {'boom_tilt': -35}), (3.5, out), (5, dict(out, sensor_head=60)), (6.5, dict(out, sensor_head=-60)), (8, {})],
          'extend the boom and survey from standoff')
    b.act('fault_hold', [(0, out), (2, {}), (3, {})], 'retract the boom, brake, hold; DR-FIX-02 retrieves if stranded (DOP-14)')
    rail_fixture(b, d, (0.0,), d['interface']['fixture_rail_len_m'], dock=None)
    return b


def fixed(d, s, cid):
    q = d['class'][cid]; Dm, Hb = q['base_m']; a1, a2 = q['boom_m']; aft = cid == 'DR-FIX-02'
    b = Body(cid, 'Aft fixed service manipulator' if aft else 'Forward fixed precision service arm', 'mounting face (z = 0); stationary base')
    c = b.node('base')
    b.cyl(c, 'BASE', (0, 0, 0), (0, 0, .04), Dm/2, 'graphite', n=40, job='mounting flange (structural load path / clearance: OPEN)')
    b.cyl(c, 'BASE', (0, 0, .04), (0, 0, Hb), Dm/2*.82, 'beta_white', n=40, job='base drum: joint drives, electronics, MLI')
    b.torus(c, 'BASE', (0, 0, Hb), 'z', Dm/2*.80, .012, 'graphite')
    cover(b, c, (Dm/2*.82+.002, 0, Hb*.30), (.004, .16, .12), 'x', job='drive-electronics access cover')
    plate(b, c, 'plate', (Dm/2*.82+.002, 0, Hb*.62), '+x', .16, .034, cid)
    lamp(b, c, 'lamp', (-Dm/2*.5, Dm*.2, Hb), '+z', .012, 'lamp_amber')
    estop(b, c, 'estop', (-Dm/2*.5, -Dm*.2, Hb), '+z', .016)
    b.mark('dock', c, 'fixed base: no dock (power, data and recovery through the base)')
    b.mark('recovery', c, 'fixed: stranded-crawler recovery is this arm\'s job; the arm itself is recovered by crew EVA (HOLD)')
    # stow cradle that holds the folded booms under 1.5 g (DOP-03)
    sc = b.node('stow', c, (a1*.55, 0, 0))
    b.box(sc, 'STOW_CRADLE', (0, 0, (Hb+.10)/2), (.10, .08, Hb+.10), 'graphite', bevel=.01, job='launch / thrust stow cradle with latch (1.5 g retention, rating OPEN)')
    b.box(sc, 'STOW_CRADLE', (0, 0, Hb+.11), (.14, .16, .03), 'grey', bevel=.006)
    sh_r = b.node('sh_roll', c, (0, 0, Hb), joint='revolute', axis='z', job='shoulder roll')
    b.cyl(sh_r, 'ARM_JOINT', (0, 0, 0), (0, 0, .14), .11, 'graphite', n=32)
    sh_p = b.node('sh_pitch', sh_r, (0, 0, .22), joint='revolute', axis='y', limits=(-170, 10), job='shoulder pitch')
    b.cyl(sh_p, 'ARM_JOINT', (0, -.12, 0), (0, .12, 0), .09, 'graphite', n=32)
    b.cyl(sh_p, 'BOOM', (.06, 0, 0), (a1, 0, 0), .07, 'beta_white', n=28, job='boom 1 (display length only: reach OPEN)')
    b.torus(sh_p, 'BOOM', (a1*.5, 0, 0), 'x', .071, .006, 'gu_blue')
    camera(b, sh_p, 'ARM_CAMERA', (a1*.85, 0, .07), '+z', .02, .03, job='elbow camera and light')
    el = b.node('elbow', sh_p, (a1, .16, 0), joint='revolute', axis='y', limits=(0, 178), job='elbow')
    b.cyl(el, 'ARM_JOINT', (0, -.10, 0), (0, .10, 0), .08, 'graphite', n=32)
    b.cyl(el, 'BOOM', (-.06, 0, 0), (-a2, 0, 0), .06, 'beta_white', n=28, job='boom 2 (display length only)')
    wp = b.node('wr_pitch', el, (-a2, 0, 0), joint='revolute', axis='y', limits=(-120, 120))
    b.cyl(wp, 'ARM_JOINT', (0, -.07, 0), (0, .07, 0), .055, 'graphite', n=24)
    wy = b.node('wr_yaw', wp, (-.09, 0, 0), joint='revolute', axis='z', limits=(-120, 120))
    b.cyl(wy, 'ARM_JOINT', (0, 0, -.06), (0, 0, .06), .05, 'graphite', n=24)
    wr = b.node('wr_roll', wy, (-.07, 0, 0), joint='revolute', axis='x')
    b.cyl(wr, 'ARM_JOINT', (0, 0, 0), (-.08, 0, 0), .055, 'graphite', n=24)
    b.box(wr, 'FT_SENSOR', (-.10, 0, 0), (.03, .12, .12), 'metal', bevel=.006, job='force-torque sensor (compliant contact; limits OPEN)')
    camera(b, wr, 'WRIST_CAMERA', (-.07, 0, .06), '+z', .016, .02, job='wrist camera / light')
    sif(b, wr, 'lee', (-.115, 0, 0), '-x', 'L', d, active=True, release=True, job='latching end effector: active GU-SIF-L (captures modules and stranded robots by their SIF)')
    b.mark('tool', wr, 'GU-SIF-L latching end effector')
    if aft:
        hood = b.node('hood', sc, (0, 0, Hb+.13))
        b.box(hood, 'HEAT_HOOD', (0, 0, .08), (.36, .30, .006), 'radiator', job='heat hood over the stowed wrist: shades it from residual blade heat (no rating)')
        for sx in (1, -1):
            b.box(hood, 'HEAT_HOOD', (sx*.17, 0, .04), (.01, .28, .08), 'graphite')
        hol = b.node('holster', c, (-Dm*.30, Dm*.42, Hb*.5))
        for k in (0, 1):
            t = b.node(f'holster{k}', hol, (0, k*.10-.05, 0))
            b.box(t, 'TOOL_HOLSTER', (0, 0, 0), (.08, .08, .16), 'grey', bevel=.008, job='tool holster: GU-SIF-L tool (spare pump / valve driver), PROTOTYPE')
            sif(b, t, f'holster{k}_sif', (0, 0, .08), '+z', 'L' if k == 0 else 'M', d, release=False)
    b.act('unstow', [(0, {}), (2, {'sh_pitch': -40}), (4, {'sh_pitch': -70, 'elbow': 100}), (6, {'sh_pitch': -60, 'elbow': 120, 'wr_pitch': -40, 'sh_roll': 45}), (8, {'sh_pitch': -60, 'elbow': 120, 'wr_pitch': -40, 'sh_roll': 45})],
          'release from the stow cradle and unfold to a work pose (reach OPEN)')
    b.act('capture', [(0, {'sh_pitch': -60, 'elbow': 120, 'wr_pitch': -40, 'sh_roll': 45}), (3, {'sh_pitch': -35, 'elbow': 70, 'wr_pitch': -35, 'sh_roll': 90, 'wr_roll': 90}),
                      (5, {'sh_pitch': -35, 'elbow': 70, 'wr_pitch': -35, 'sh_roll': 90, 'wr_roll': 90}), (8, {})], 'approach and latch a module / stranded robot by its GU-SIF, then stow')
    b.act('fault_hold', [(0, {'sh_pitch': -60, 'elbow': 120}), (1, {'sh_pitch': -60, 'elbow': 120})], 'joint brakes on, hold pose; no motion on lost link (DOP-13)')
    return b


def bodies(s, d):
    out = {'DR-IVA-01': iva01(d), 'DR-IVA-02': iva02(d), 'DR-IVA-03': iva03(d), 'DR-EVA-01': eva01(d, s), 'DR-EVA-02': eva02(d, s),
           'DR-EVA-03': eva03(d, s), 'DR-EVA-04': eva04(d, s), 'DR-FIX-01': fixed(d, s, 'DR-FIX-01'), 'DR-FIX-02': fixed(d, s, 'DR-FIX-02')}
    for b in out.values():                               # wheels spin with travel in every action
        root = 'travel' if 'travel' in b.nodes else 'root'
        for a in b.actions.values():
            for _, vals in a['keys']:
                if root in vals:
                    for n in b.joints():
                        if b.nodes[n].get('spin'):
                            vals[n] = math.degrees(vals[root]*b.nodes[n]['spin'])
    return out


# ------------------------------------------------------------------------------------------------------------------------------ check
def check(s, d):
    """Fit screen. Owner numbers: classes and inventory as [drones]; each stowed body (fixtures excluded) inside its class's L2 proxy box
    (drone_fleet.unit_size); arm bases equal to the owner base; OPEN stays null; the GU safety kit on every class. Returns (rows, fails)."""
    cl = df.classes(s); B = bodies(s, d); fails = []; rows = {}
    if set(B) != set(cl):
        fails.append(f'class set {sorted(B)} != owner {sorted(cl)}')
    for k, v in d['open'].items():
        if v.get('known') is not False or 'value' in v:
            fails.append(f'open.{k} must stay unknown')
    man = df.manifest(s)
    for cid, b in B.items():
        c = cl[cid]; parts = {q['part'] for q in b.shapes if not q['part'].startswith('FIXTURE')}
        body_parts = parts - {'TARGET'}
        lo, hi = envelope(b, {}, include=body_parts); size = tuple(hi[i]-lo[i] for i in range(3))
        slo, shi = swept(b); env = tuple(shi[i]-slo[i] for i in range(3))
        row = dict(title=b.title, units=sum(u['cls'] == cid for u in man), stowed_m=[round(x, 3) for x in size], swept_m=[round(x, 3) for x in env],
                   joints=len(b.joints()), shapes=len(b.shapes), actions=sorted(b.actions), kit={k: len(v) for k, v in b.kit.items()})
        if c['domain'] != 'FIXED':
            hi_m = c['envelope_m'][1]; box = df.unit_size(c); row['envelope_class_m'] = c['envelope_m']; row['proxy_m'] = list(box)
            if max(size) > hi_m+1e-9:
                fails.append(f'{cid} stowed {row["stowed_m"]} exceeds the owner envelope class {c["envelope_m"]} m')
            # Dock compatibility with the ship's L2 proxy box (a Claude PROTOTYPE size, not owner canon): reported, never forced.
            row['proxy_fit'] = 'FITS' if all(size[i] <= box[i]+1e-9 for i in range(3)) else \
                f'EXCEEDS proxy on {"".join("xyz"[i] for i in range(3) if size[i] > box[i]+1e-9)} (ship session: placement and keep-out study; no automatic proxy change)'
        else:
            base = [q for q in b.shapes if q['part'] == 'BASE' and q['kind'] == 'cyl']
            dia = max(2*q['r'] for q in base); h = max(q['b'][2] for q in base)
            row['base_m'] = [dia, h]
            if abs(dia-c['base_m'][0]) > 1e-9 or abs(h-c['base_m'][1]) > 1e-9:
                fails.append(f'{cid} base {dia} x {h} != owner {c["base_m"]}')
        missing = [k for k in SAFETY_KIT if not b.kit.get(k)]
        if missing:
            fails.append(f'{cid} GU safety kit missing {missing}')
        rows[cid] = row
    rows['inventory'] = dict(mobile=sum(u['domain'] != 'FIXED' for u in man), fixed=sum(u['domain'] == 'FIXED' for u in man), designs=len(B))
    if rows['inventory']['mobile'] != s['drones']['fleet']['total'] or rows['inventory']['fixed'] != s['drones']['fleet']['fixed_arms']:
        fails.append(f"inventory {rows['inventory']} != owner {s['drones']['fleet']}")
    return rows, fails


if __name__ == '__main__':
    import json
    import sys
    root = Path(__file__).resolve().parents[2]; s, d = load(root); rows, fails = check(s, d)
    print(json.dumps(rows, indent=1)); print('FAIL' if fails else 'PASS', *fails, sep='\n  ')
    sys.exit(1 if fails else 0)
