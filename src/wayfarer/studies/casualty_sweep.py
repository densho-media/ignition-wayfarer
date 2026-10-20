"""Casualty acceptance study (HUM-2026-10-10, 15!A113, 98!A82; 38!A36 S31, 39!A17 F12, 12A SP-50): three candidate carriers swept along
every built crew route, in memory (nothing is saved). NONCANON candidates; no route, hatch or pressure boundary changes (15!H113).

Carriers (every dimension PROTOTYPE; stretcher geometry OPEN, 12!G21; the patient's safe bend limits are OPEN and not verified here):
- A, rigid full-length immobilized transport: a 2.0 m litter with the patient strapped on, 0.55 x 0.30 m section.
- B, articulated supported carrier: the same section in three hinged boards (head and torso 1.00 m, thighs 0.45 m, lower legs 0.55 m, the
  leg boards 0.45 x 0.25 m). It reports the hip and knee bend each placement needs; it passes a limit only where a pose within that bend
  clears. Which bend a patient tolerates is a medical question this study does not answer.
- C, staged assisted rescue: the patient immobilized in a vacuum mattress (1.85 m, 0.50 x 0.25 m) and passed hand to hand between anchor
  points, rigid (a vacuum mattress is immobilization, not proof the patient may bend, 15!C113).
- K (HUM-002, 15!G121): A with its medical kit strapped over the legs (the last 0.60 m 0.45 m deep).
Rigid carriers are searched as straight two-segment chains (rigid=True). --root sweeps a disposable study workspace (casualty_whatif.py).
Each chain's joints lie on the route polyline at the chord lengths behind the head, every STEP_M of the head; where that touches a surface,
SEARCH carried poses (every joint up to OFFSET_MAX_M off the axis, segment lengths kept) and REFINE local refinements are tried, and the best
kept. Bearers: one rescuer inline at each end (a shirt-sleeve capsule, BEARER_R_M, reaching BEARER_M along the route beyond the end), the way
a party moves through 0.80-0.90 m passages; a margin is given with and without them.

Routes (human_entry.route()): dock to every sector of both rings through the despun drums, the induction and Seraph legs between ring-A
sectors, the refuge legs R (from the dock) and E (from the spine ports), and the medical legs (M): ring A sector 1 to the treatment couch of
the WORK_MEDICAL_OPS sector (SP-33/SP-50), and dock to that couch on both rings. Reversed they are the evacuation to the refuge or the
medical bay. Scene: docked, both entry leaves open, the despun transfer indexed with every Q46 closure open (inspect.route_sweep's scene);
at 1.5 g aft-down (rings stopped and locked) and in 0 g the corridors are the same. With the rings spinning the party rides the drum: gate
and doors closed while it syncs (MODEL "Despun transfer"), so the carrier and its bearers must fit wholly inside the closed drum; the dwell
check searches the closed annulus for that. Sampled clearance, not a continuous-motion proof; a search-based pass is a found pose, a block
means no tried pose fits.

    /snap/bin/blender -b --python src/wayfarer/studies/casualty_sweep.py -- --out runs/<stamp>-casualty
"""
from pathlib import Path
import argparse
import importlib.util
import json
import math
import sys
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build')]
from spec import load
import crew_transfer
import human_entry as he

CARRIERS = {     # PROTOTYPE: segment lengths (head first) and capsule radii (circumscribed section)
    # Rigid bodies are searched as straight two-segment chains (rigid=True): seeded on the chord through the route point 1.4 m behind the
    # head, which finds poses a single 2.0 m chord between two route points misses (HUM-002 re-run: ring A -0.09 m instead of -0.29 m).
    'A': dict(name='rigid full-length litter', lengths=[1.40, .60], radii=[math.hypot(.55, .30)/2]*2, bend_limits=[0], rigid=True),
    'B': dict(name='articulated supported carrier', lengths=[1.00, .45, .55], radii=[math.hypot(.55, .30)/2]+[math.hypot(.45, .25)/2]*2,
              bend_limits=[30, 60, 90]),
    'C': dict(name='staged transfer in a vacuum mattress', lengths=[1.30, .55], radii=[math.hypot(.50, .25)/2]*2, bend_limits=[0], rigid=True),
    # HUM-002 (15!G121): the rigid litter with its medical kit (monitor, oxygen, suction) strapped over the patient's legs: the last 0.60 m
    # is 0.45 m deep instead of 0.30.
    'K': dict(name='rigid full-length litter with medical kit', lengths=[1.40, .60], radii=[math.hypot(.55, .30)/2, math.hypot(.55, .45)/2],
              bend_limits=[0], rigid=True),
}
BEARER_R_M = 0.25                # PROTOTYPE: a shirt-sleeve rescuer inline at each end
BEARER_M = 0.70
CARRY_Y_M = -0.90                # sector frame: litter carried 0.9 m above the deck (-Y is up)
STEP_M = 0.10
SAMPLE_M = 0.10                  # capsule sample spacing along a segment
SEARCH = 160
REFINE = 60
OFFSET_MAX_M = 0.60
ZONE_NAMES = {1: 'entry chamber', 2: 'trunk and spine port', 3: 'transfer drum annulus', 4: 'crew tube', 5: 'sector hatch and landing',
              'R': 'refuge leg', 'M': 'sector aisle to the treatment couch'}


def load_inspect():
    spec = importlib.util.spec_from_file_location('wf_inspect', ROOT/'src/wayfarer/validation/inspect.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def scene(s, ins, open_=1.0):
    """The route sweep's scene: docked, entry leaves open, the transfer indexed with every Q46 closure at open_; evaluated records."""
    f = he.ports(s)[0]; ctrl = bpy.data.objects['DOCK_ENTRY_CTRL']
    for w in ('outer', 'inner'):
        ctrl[f"{f['name']}_{w}_open"] = 1.0
    ctrl.update_tag()
    for o in bpy.data.objects:
        if o.name.endswith('_Hatch_Hinge'):
            o.update_tag()
    ins.pose_configuration(s, 'DOCKED'); ins.pose_transfer(s, open_)
    return [r for r in ins.evaluated(1) if r['kind'] not in ('scale_reference', 'sector_interior_deck', 'entry_camera')]


def medical_routes(s, routes):
    """M legs: from a sector route's hatch axis at carry height, across the landing to the aisle, along it to the treatment couch and
    sideways over the couch (SP-33 / SP-50), in the work/medical sector of each ring."""
    import habitat_interior
    k = s['habitat']['layout']['functions'].index('WORK_MEDICAL_OPS')+1
    b = next(q for q in habitat_interior.zones(s, 'WORK_MEDICAL_OPS') if q['name'] == 'Medical_Couch'); L = he.landing(s)
    xc = (b['min'][0]+b['max'][0])/2; zc = (b['min'][2]+b['max'][2])/2
    top = -(s['sector_whitebox']['medical_table_m']+.08+.20)
    out = {}
    for j in s['human_entry']['tube_rotors']:
        tag = 'AB'[j-1]; rot, v, la = he.vestibule_station(s, j)
        point = lambda p: he.at_index(rot, crew_transfer.sector_point(s, la[k], p))
        leg = [('M', point((L['x'], CARRY_Y_M, L['z']))), ('M', point((L['x'], CARRY_Y_M, 0.0))), ('M', point((xc, CARRY_Y_M, 0.0))),
               ('M', point((xc, top, zc)))]
        for key in (f'{tag}{k}', f'{tag}1-{tag}{k}'):
            if key in routes:
                cut = next((i for i, p in enumerate(routes[key]['path']) if p[0] == 5), len(routes[key]['path']))
                out[f'{key}-M'] = dict(path=routes[key]['path'][:cut]+leg, walk=[])
    return out


def cumulative(pts):
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1]+math.dist(a, b))
    return cum


def at(path, cum, t):
    zones, pts = path
    i = next((j for j in range(1, len(cum)) if t <= cum[j]), len(cum)-1)
    u = min(max((t-cum[i-1])/max(cum[i]-cum[i-1], 1e-12), 0.0), 1.0)
    return zones[i], tuple(pts[i-1][k]+u*(pts[i][k]-pts[i-1][k]) for k in range(3))


def behind(path, cum, t, p, length):
    """The route parameter behind t whose point lies `length` (chord) from p."""
    lo, hi = max(0.0, t-3*length), t
    for _ in range(50):
        mid = (lo+hi)/2
        lo, hi = (mid, hi) if math.dist(at(path, cum, mid)[1], p) > length else (lo, mid)
    return lo


def placements(route, lengths):
    """Chains along the route: (zone of the head, joints head first, head t, tail t), every STEP_M of the head."""
    path = tuple(zip(*route)); cum = cumulative(path[1]); total = sum(lengths); out = []
    for t in np.arange(total, cum[-1]+1e-9, STEP_M):
        zone, head = at(path, cum, t); joints = [head]; tt = t
        for L in lengths:
            tt = behind(path, cum, tt, joints[-1], L); joints.append(at(path, cum, tt)[1])
        out.append((zone, joints, t, tt))
    return out, path, cum


def bends(joints):
    d = [np.subtract(b, a) for a, b in zip(joints, joints[1:])]
    return [math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(p, q)/(np.linalg.norm(p)*np.linalg.norm(q))))))) for p, q in zip(d, d[1:])]


class Clearance:
    """Nearest-surface distance from one BVH of every record whose box comes within REACH_M of the routes (polygon -> record by offset)."""
    REACH_M = 3.0

    def __init__(self, records, pts):
        import bisect
        lo = np.min(pts, 0)-self.REACH_M; hi = np.max(pts, 0)+self.REACH_M; vs, fs, self.offsets, self.names = [], [], [], []
        for q in records:
            if all(q['lo'][k] <= hi[k] and q['hi'][k] >= lo[k] for k in range(3)):
                self.offsets.append(len(fs)); self.names.append(q['name']); n = len(vs)
                vs += [tuple(v) for v in q['vs']]; fs += [tuple(i+n for i in f) for f in q['fs']]
        self.tree = BVHTree.FromPolygons(vs, fs); self.bisect = bisect.bisect_right

    def point(self, c, r):
        hit = self.tree.find_nearest(Vector(c))
        return (math.inf, None) if hit[0] is None else (hit[3]-r, self.names[self.bisect(self.offsets, hit[2])-1])

    def capsule(self, a, b, r, floor=-math.inf):
        n = max(1, math.ceil(math.dist(a, b)/SAMPLE_M)); best = (math.inf, None)
        for k in range(n+1):
            m = self.point(np.add(a, np.subtract(b, a)*k/n), r)
            if m[0] < best[0]:
                best = m
                if best[0] < floor:
                    break
        return best

    def chain(self, joints, radii, floor=-math.inf):
        """Least margin of the chain; stops early once it is below floor (the pose can't beat the best so far)."""
        best = (math.inf, None)
        for a, b, r in zip(joints, joints[1:], radii):
            m = self.capsule(a, b, r, floor)
            if m[0] < best[0]:
                best = m
                if best[0] < floor:
                    break
        return best


def bearers(path, cum, t_head, t_tail, joints):
    """Inline rescuers: from each end of the chain to the route point BEARER_M beyond it (ahead of the head, behind the tail). Within BEARER_M
    of either end of a route the rescuer stands beside the carrier, in the room the route starts or ends in, and is not checked."""
    out = []
    if t_head+BEARER_M <= cum[-1]:
        out.append((joints[0], at(path, cum, t_head+BEARER_M)[1]))
    if t_tail-BEARER_M >= 0.0:
        out.append((joints[-1], at(path, cum, t_tail-BEARER_M)[1]))
    return out


def search(cl, carrier, joints, rng, centre=None, spread=OFFSET_MAX_M, n=SEARCH):
    """Random carried poses about `joints` (segment lengths kept, head first); returns [(margin, nearest, joints, bends)]."""
    out = []; floor = -math.inf
    for _ in range(n):
        h = np.add(joints[0], rng.uniform(-1, 1, 3)*spread/math.sqrt(3)); js = [tuple(h)]
        if carrier.get('rigid'):           # one rigid body in several segments: every joint on the head-to-tail line
            d = np.subtract(np.add(joints[-1], rng.uniform(-1, 1, 3)*spread/math.sqrt(3)), h); d = d/np.linalg.norm(d)
            js += [tuple(np.add(h, d*c)) for c in np.cumsum(carrier['lengths'])]
        for q, L in ([] if carrier.get('rigid') else zip(joints[1:], carrier['lengths'])):
            d = np.subtract(np.add(q, rng.uniform(-1, 1, 3)*spread/math.sqrt(3)), js[-1]); js.append(tuple(np.add(js[-1], d/np.linalg.norm(d)*L)))
        m, name = cl.chain(js, carrier['radii'], floor); out.append((m, name, js, bends(js)))
        if len(carrier['lengths']) == 1:
            floor = max(floor, m)
    return out


def best_within(poses, limit):
    ok = [p for p in poses if max(p[3], default=0.0) <= limit+1e-3]
    return max(ok, key=lambda p: p[0]) if ok else None


def sweep(s, records, routes, rng, sp45_x=None):
    cl = Clearance(records, [p for r in routes.values() for _, p in r['path']]); out = {}
    for cid, carrier in CARRIERS.items():
        res = {}
        for key, route in routes.items():
            places, path, cum = placements(route['path'], carrier['lengths'])
            per_limit = {lim: dict(least=(math.inf,), blocked=[]) for lim in carrier['bend_limits']}; need = 0.0
            bearer_least = (math.inf, None, None); at_sp45 = math.inf; by_zone = {}
            for zone, joints, t, tt in places:
                if carrier.get('rigid') and len(joints) > 2:      # a rigid body lies on its head-to-tail chord
                    u = np.subtract(joints[-1], joints[0]); u = u/np.linalg.norm(u)
                    joints = [joints[0]]+[tuple(np.add(joints[0], u*c)) for c in np.cumsum(carrier['lengths'])]
                m, name = cl.chain(joints, carrier['radii']); poses = [(m, name, joints, bends(joints))]
                if m < 0 or any(max(poses[0][3], default=0) > lim+1e-3 for lim in carrier['bend_limits']):
                    seeds = [joints]
                    if len(joints) > 2:                          # the straight board along the head-to-tail chord, as the rigid litter lies
                        u = np.subtract(joints[-1], joints[0]); u = u/np.linalg.norm(u); c = np.cumsum([0.0]+carrier['lengths'])
                        straight = [tuple(np.add(joints[0], u*d)) for d in c]
                        poses.append((*cl.chain(straight, carrier['radii']), straight, bends(straight))); seeds.append(straight)
                    for sd in seeds:
                        poses += search(cl, carrier, sd, rng, n=SEARCH//len(seeds))
                    for lim in carrier['bend_limits']:            # refine the best pose within each bend limit
                        b = best_within(poses, lim)
                        if b:
                            poses += [p for p in search(cl, carrier, b[2], rng, spread=.15, n=REFINE//len(carrier['bend_limits'])+10)]
                for lim in carrier['bend_limits']:
                    b = best_within(poses, lim); q = per_limit[lim]
                    mm = b[0] if b else -math.inf
                    if mm < q['least'][0]:
                        q['least'] = (mm, b[1] if b else None, zone, round(float(t), 2), [round(x, 3) for x in (b[2][0] if b else joints[0])],
                                      [round(x, 1) for x in (b[3] if b else [])], b[2] if b else joints)
                    if mm < 0:
                        q['blocked'].append((round(float(t), 2), zone, round(mm, 3), b[1] if b else None))
                top = max(poses, key=lambda p: p[0])
                if top[0] < by_zone.get(zone, (math.inf,))[0]:
                    by_zone[zone] = (top[0], top[1], [round(b, 1) for b in top[3]])
                if sp45_x is not None and zone == 2 and any(abs(j[0]-sp45_x) < 1.0 for j in top[2]):
                    at_sp45 = min(at_sp45, top[0])
                if top[0] >= 0 and top[3]:
                    need = max(need, min(max(p[3]) for p in poses if p[0] >= 0))
                br = min((cl.capsule(a, b, BEARER_R_M) for a, b in bearers(path, cum, t, tt, top[2])), key=lambda x: x[0], default=(math.inf, None))
                if min(top[0], br[0]) < bearer_least[0]:
                    bearer_least = (min(top[0], br[0]), br[1] if br[0] < top[0] else top[1], zone)
            res[key] = {}
            for lim, q in per_limit.items():
                spans = []
                for t, zone, m, name in q['blocked']:
                    if spans and t-spans[-1]['to_m'] <= STEP_M+1e-6 and spans[-1]['zone'] == zone:
                        sp = spans[-1]; sp['to_m'] = t; sp['worst_m'] = min(sp['worst_m'], m); sp['objects'] = sorted(set(sp['objects']) | {str(name)})
                    else:
                        spans.append(dict(zone=zone, zone_name=ZONE_NAMES.get(zone, str(zone)), from_m=t, to_m=t, worst_m=m, objects=[str(name)]))
                m, name, zone, t, head, bend, js = q['least']
                res[key][f'bend_{lim}'] = dict(passes=not q['blocked'], least_margin_m=None if m == -math.inf else round(m, 3), nearest=name, zone=zone,
                                               zone_name=ZONE_NAMES.get(zone, str(zone)), at_m=t, head=head, bends_deg=bend, blocked_spans=spans,
                                               pose=[[round(x, 3) for x in p] for p in js])
            res[key]['with_bearers_least_m'] = round(bearer_least[0], 3); res[key]['with_bearers_nearest'] = bearer_least[1]
            res[key]['with_bearers_zone'] = ZONE_NAMES.get(bearer_least[2], str(bearer_least[2]))
            res[key]['least_by_zone_loosest_limit'] = {ZONE_NAMES.get(z, str(z)): dict(margin_m=round(m, 3), nearest=n, bends_deg=b) for z, (m, n, b) in by_zone.items()}
            if at_sp45 < math.inf:
                res[key]['trunk_margin_at_sp45_port_m'] = round(at_sp45, 3)
            if len(carrier['lengths']) > 1:
                res[key]['max_bend_needed_deg'] = round(need, 1)
            print('WF_CASUALTY', cid, key, {k: (v['passes'], v['least_margin_m']) for k, v in res[key].items() if k.startswith('bend')}, flush=True)
        out[cid] = res
    return out


def dwell(s, records, rng):
    """Closed-drum dwell (transfer while the ring spins): the best pose of each carrier wholly inside each human-entry drum's annulus with the
    gate, doors and hatches closed."""
    out = {}
    for j in s['human_entry']['vestibule_rotors']:
        rot, v, _ = he.vestibule_station(s, j); r0, r1 = v['r0'], v['clear']
        cl = Clearance(records, [he.at_index(rot, crew_transfer.radial(u, r1, a*math.tau/24)) for u in (v['cu0'], v['cu1']) for a in range(24)])
        def inside():
            return he.at_index(rot, crew_transfer.radial(rng.uniform(v['cu0'], v['cu1']), rng.uniform(r0, r1), rng.uniform(0, math.tau)))
        res = {}
        for cid, carrier in CARRIERS.items():
            best = (-math.inf,)
            for _ in range(3000):
                js = [inside()]; d0 = rng.normal(size=3)
                for L in carrier['lengths']:
                    d = d0 if carrier.get('rigid') else rng.normal(size=3); js.append(tuple(np.add(js[-1], d/np.linalg.norm(d)*L)))
                bd = bends(js)
                if any(b > max(carrier['bend_limits'])+1e-3 for b in bd):
                    continue
                m, name = cl.chain(js, carrier['radii'])
                if m > best[0]:
                    best = (m, name, js, bd)
            for _ in range(400):
                cand = search(cl, carrier, best[2], rng, spread=.2, n=1)[0]
                if cand[0] > best[0] and all(b <= max(carrier['bend_limits'])+1e-3 for b in cand[3]):
                    best = cand
            res[cid] = dict(least_margin_m=round(best[0], 3), nearest=best[1], fits=best[0] >= 0, bends_deg=[round(b, 1) for b in best[3]])
        out['AB'[j-1]] = dict(annulus_depth_m=round(r1-r0, 3), clear_length_m=round(v['cu1']-v['cu0'], 3), carriers=res)
        print('WF_CASUALTY_DWELL', 'AB'[j-1], {k: (q['fits'], q['least_margin_m']) for k, q in res.items()}, flush=True)
    return out


def render(chain, radii, name, out):
    """Workbench still of a carrier pose from beside it."""
    objs = []
    for k, (a, b, r) in enumerate(zip(chain, chain[1:], radii)):
        bpy.ops.mesh.primitive_cylinder_add(radius=r*.9, depth=math.dist(a, b), location=tuple(np.add(a, b)/2))
        o = bpy.context.active_object; o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(Vector(np.subtract(b, a)))
        mat = bpy.data.materials.new('Litter'); mat.diffuse_color = (.95, .35, .05, 1); o.data.materials.append(mat); objs.append(o)
    a, b = Vector(chain[0]), Vector(chain[-1]); ax = (a-b).normalized(); side = ax.cross(Vector((1, 0, 0)) if abs(ax.x) < .9 else Vector((0, 0, 1))).normalized(); up = ax.cross(side)
    sc = bpy.context.scene; cam = bpy.data.objects.new('CasualtyCam', bpy.data.cameras.new('CasualtyCam')); sc.collection.objects.link(cam)
    mid = (a+b)/2; eye = mid+side*2.2+up*1.2-ax*1.0
    f = (mid-eye).normalized(); rgt = f.cross(up).normalized(); u2 = rgt.cross(f)
    cam.matrix_world = Matrix((rgt, u2, -f)).transposed().to_4x4(); cam.location = eye; cam.data.lens = 18; cam.data.clip_start = .05; sc.camera = cam
    sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'
    sc.render.resolution_x, sc.render.resolution_y = 1280, 800; sc.render.filepath = str(out/f'{name}.png'); bpy.ops.render.render(write_still=True)
    for o in objs:
        bpy.data.objects.remove(o)
    bpy.data.objects.remove(cam)


def main():
    a = argparse.ArgumentParser(); a.add_argument('--out', type=Path, required=True); a.add_argument('--carriers', default='ABC'); a.add_argument('--routes', default='')
    a.add_argument('--root', type=Path, default=ROOT, help='a study workspace built with build.py --root (casualty_whatif.py)')
    a.add_argument('--no-dwell', action='store_true')
    args = a.parse_args(sys.argv[sys.argv.index('--')+1:]); out = (ROOT/args.out) if not args.out.is_absolute() else args.out; out.mkdir(parents=True, exist_ok=True)
    for k in [k for k in CARRIERS if k not in args.carriers]:
        del CARRIERS[k]
    s = load(args.root)[0]; bpy.ops.wm.open_mainfile(filepath=str(args.root/'assets/wayfarer/WF_WAYFARER_001.blend')); ins = load_inspect(); rng = np.random.default_rng(7)
    routes = he.route(s); routes.update(medical_routes(s, routes))
    if args.routes:
        routes = {k: v for k, v in routes.items() if k in args.routes.split(',')}
    import storeroom
    p = storeroom.port(s)
    result = sweep(s, scene(s, ins, 1.0), routes, rng, p['x'])
    held = {} if args.no_dwell else dwell(s, scene(s, ins, 0.0), rng)
    sp45 = dict(port_station_x_m=round(p['x'], 3), port_clear_m=p['clear'],
                note='SP-45 port off the trunk; its hatch opens into the room, so the trunk margin at this station is the trunk margin of each route')
    report = dict(study='Casualty acceptance study (HUM-2026-10-10, 15!A113; 38 S31, 39 F12, 12A SP-50)',
                  status='NONCANON candidate carriers; PROTOTYPE dimensions; patient bend limits OPEN; no certification',
                  carriers={k: dict(name=c['name'], segments_m=c['lengths'], capsule_radii_m=[round(r, 3) for r in c['radii']], bend_limits_deg=c['bend_limits'])
                            for k, c in CARRIERS.items()},
                  bearers=dict(radius_m=BEARER_R_M, reach_m=BEARER_M, placement='inline at each end along the route'),
                  scene='docked, entry leaves open, despun transfer indexed with every closure open; dwell: closures closed',
                  sampling=dict(step_m=STEP_M, sample_m=SAMPLE_M, search=SEARCH, refine=REFINE, offset_max_m=OFFSET_MAX_M),
                  routes=result, drum_dwell=held, sp45=sp45)
    (out/'casualty_sweep.json').write_text(json.dumps(report, indent=1, default=str)+'\n')
    for cid, res in result.items():                         # one still at each blocked route's tightest point, at the loosest bend limit
        lim = max(CARRIERS[cid]['bend_limits'])
        for key, r in res.items():
            q = r[f'bend_{lim}']
            if not q['passes']:
                render(q['pose'], CARRIERS[cid]['radii'], f'{cid}_{key}_tightest', out)
    print('WF_CASUALTY_SWEEP done', flush=True)


if __name__ == '__main__':
    main()
