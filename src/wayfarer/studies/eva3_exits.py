"""EVA-003 follow-up (owner direction 2026-10-11: S&E 15!A135 RESCUE-004, 15!A136 DIST-004, 43 EVA-063): disposable PROTOTYPE studies on the
L1-A forward district. NONCANON; nothing here changes data/, a generator, GEN_* geometry or a saved asset (the vehicle .blend is opened, never saved).

  1. SP-12 near-axial casualty exit. The 0.90 m radial branch turn (-0.093 m) and the 1.10 m widening (+0.009 m) are the control. Variants with
     no 90 deg turn in the trunk: N1 an axial slot hatch (carrier lowered without turning), N2/N3 a 15 deg oblique duct (1.10 / 1.20 m) sunk in
     the SP-12 floor and landing in the L1-A trunk extension. Carriers S (suited casualty on the full-length frame) and K (litter + kit) with an
     inline rescuer at each end (hum003_routes' sampled-pose sweep: a found pose, not a motion proof) through the SP-11 inner hatch, the
     turn-in under its bulkhead, the SP-12 run, the closure and the trunk. The SP-11 sliding plug's parked leaf and rails and the SP-12
     fit-out are obstacles. Margin: PASS >= 0.05, MARGINAL 0..0.05, FAIL < 0.
  2. SP-13 second exit: a radial port from SP-13's floor into the trunk extension (no SP-12 volume or closure), unsuited crew and carrier K.
  3. L1-A guarded ladder bypass at Dock_Primary: pure geometry on human_entry's ladder, climber and arrest rail.
  4. L1-A versus corridor B: numbers from references/p1_eva_district.json plus measured clearances to the reserves, the refuge and SP-52.

    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/eva3_exits.py -- --out runs/<stamp>-eva3-exits [--skip sweeps]
"""
from pathlib import Path
import argparse
import json
import math
import sys
import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/studies'), str(ROOT/'src/wayfarer/validation'), str(ROOT/'tools')]
from spec import load
import crew_transfer as ct
import eva_access as ea
import eva_suit as es
import human_entry as he
import storeroom_survey as sv
import eva3_district as ed
import hum003_routes as h3

AZ = math.radians(50.0)                     # the airlock azimuth (Airlock_EVA fitting, x 101.849)
STUDY_MARGIN = 0.05
FIT = True                                  # SP-12/13 PROTOTYPE fit-out as obstacles (--fit bare removes it)
CABIN_KPA = 80.0                            # BASELINE cabin pressure (eva_suit telemetry)
CAR = {'S': h3.CARRIERS['S'], 'K': h3.CARRIERS['K']}
SHELL_KG_M2 = 20.0                          # PROTOTYPE, data/eva_suit.toml sp11_eva3.shell_kg_m2 (SERV-002 survey value)
TRUNK_EXT_X = 107.4                         # the trunk extension for this study: L1-A to 104.9 plus the SP-13 port station (eva3_district.sp13_egress)


def status(m):
    return 'FAIL' if m is None or m < 0 else ('MARGINAL' if m < STUDY_MARGIN else 'PASS')


def P(x, r, tang=0.0, az=AZ):
    """Vehicle point at X x, radial coordinate r along azimuth az and tangential offset tang (+ = increasing azimuth)."""
    return (x, r*math.cos(az)-tang*math.sin(az), r*math.sin(az)+tang*math.cos(az))


def axes_at(az=AZ):
    return ((1.0, 0.0, 0.0), (0.0, -math.sin(az), math.cos(az)), (0.0, math.cos(az), math.sin(az)))      # X, tangential, radial


# ---------------------------------------------------------------------------------------------------------------------------------
# free-space construction (Blender booleans; the objects are temporary)

def link(me, name):
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob); return ob


def sector_obj(x0, x1, a0, a1, r0, r1, n=24, name='sector'):
    rings = [(x0, r0), (x0, r1), (x1, r1), (x1, r0)]; angs = [math.radians(a0+(a1-a0)*k/n) for k in range(n+1)]
    vs = [(x, r*math.cos(a), r*math.sin(a)) for x, r in rings for a in angs]; idx = lambda i, k: i*(n+1)+k; fs = []
    for i in range(4):
        j = (i+1) % 4
        for k in range(n):
            fs.append((idx(i, k), idx(i, k+1), idx(j, k+1), idx(j, k)))
    fs.append((idx(0, 0), idx(1, 0), idx(2, 0), idx(3, 0))); fs.append((idx(3, n), idx(2, n), idx(1, n), idx(0, n)))
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    return link(me, name)


def build_free(s, data, unions, diffs, x_fwd, sp12=True, sp13=False, ref=True, fit=True, hole_r=0.60):
    """Free space: trunk to x_fwd U refuge annulus U SP-12 (and SP-13) rooms U SP-11 chamber interior U `unions`, minus the chamber wall and
    bulkhead, the SP-11 plug's parked leaf and rails, the SP-12/13 fit-out and `diffs`. Returns (object, BVH)."""
    from mathutils.bvhtree import BVHTree
    tr = s['crew_transfer']['trunk_clear_radius_m']; rf = he.refuge_station(s)
    trunk = h3.prim_cyl((87.0, 0, 0), (x_fwd, 0, 0), tr)
    if ref:
        ann = h3.prim_cyl((rf['cavity_x0'], 0, 0), (rf['cavity_x1'], 0, 0), rf['pressure']); core = h3.prim_cyl((rf['cavity_x0']-.1, 0, 0), (rf['cavity_x1']+.1, 0, 0), rf['inner'])
        h3.boolean(ann, core, 'DIFFERENCE'); h3.boolean(trunk, ann, 'UNION')
    rooms = []
    if sp12:
        rooms.append(('sp12', data['sp12']))
    if sp13:
        rooms.append(('sp13', data['sp13']))
    for nm, q in rooms:
        h3.boolean(trunk, sector_obj(*q['x_m'], *q['az_deg'], *q['r_m'], name=nm), 'UNION')
    for mk in unions:
        h3.boolean(trunk, mk(), 'UNION')
    xc = 101.8494
    if sp12:
        # chamber wall and inner bulkhead (a 2.45-2.50 disc with the 1.20 m aperture) are solid; the interior (radius 1.05, a >= 2.5) is free
        wall = h3.prim_cyl(P(xc, 2.45), P(xc, 4.70), 1.10); inner = h3.prim_cyl(P(xc, 2.50), P(xc, 4.80), 1.05); hole = h3.prim_cyl(P(xc, 2.40), P(xc, 2.55), hole_r)
        h3.boolean(wall, inner, 'DIFFERENCE'); h3.boolean(wall, hole, 'DIFFERENCE'); h3.boolean(trunk, wall, 'DIFFERENCE')
        h3.boolean(trunk, h3.prim_cyl(P(xc, 2.50), P(xc, 6.15), 1.05), 'UNION')
        # SP-11 sliding plug (45 I-01): the leaf dropped 0.08 m below the seat (a 2.34-2.42) parks 1.30 m toward -az, on two rails 0.70 m each side
        h3.boolean(trunk, h3.prim_cyl(P(xc, 2.34, -1.30), P(xc, 2.42, -1.30), 0.65), 'DIFFERENCE')
        for sgn in (-1, 1):
            h3.boolean(trunk, h3.prim_box(P(xc+sgn*0.70, 2.37, -0.65), axes_at(), (0.08, 2.70, 0.10)), 'DIFFERENCE')
    for nm, q in (rooms if fit else []):
        for b in fixture_boxes(q):
            h3.boolean(trunk, h3.prim_box(*b), 'DIFFERENCE')
    for mk in diffs:
        h3.boolean(trunk, mk(), 'DIFFERENCE')
    bpy.context.view_layer.update()
    me = trunk.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    vs = [trunk.matrix_world@v.co for v in me.vertices]; fs = [tuple(p.vertices) for p in me.polygons]
    trunk.name = 'EVA3EXITS_FREE_SPACE'
    return trunk, BVHTree.FromPolygons(vs, fs)


def fixture_boxes(room):
    """Solid fit-out (every kind but the buddy-check ZONE, which is people, not solid): (centre, axes, size)."""
    r0 = room['r_m'][0]; out = []
    for fi in room['fixtures']:
        if fi['kind'] == 'zone':
            continue
        rb = r0 if fi['kind'] in ('stand', 'rack', 'bench', 'locker') else r0+.90; dx, dw, dh = fi['size']; az = math.radians(fi['az'])
        out.append((P(fi['x'], rb+dh/2, az=az), axes_at(az), (dx, dw, dh)))
    return out


def free_stats(obj):
    return dict(objects=obj.name)


# ---------------------------------------------------------------------------------------------------------------------------------
# paths

def smooth(wps, cut=0.45, k=6):
    """Round the corners of a waypoint list [(label, point)] with quadratic Beziers (cut = the length taken off each leg at a corner)."""
    pts = [np.array(p, float) for _, p in wps]; labs = [l for l, _ in wps]; out = [(labs[0], tuple(pts[0]))]
    for i in range(1, len(pts)-1):
        a, w, b = pts[i-1], pts[i], pts[i+1]; da, db = np.linalg.norm(a-w), np.linalg.norm(b-w)
        p0 = w+(a-w)/da*min(cut, da/2); p2 = w+(b-w)/db*min(cut, db/2)
        for j in range(k+1):
            t = j/k; q = (1-t)**2*p0+2*t*(1-t)*w+t*t*p2; out.append((labs[i] if t < .5 else labs[i+1], tuple(q)))
    out.append((labs[-1], tuple(pts[-1]))); return out


def zone_sweep(walls, name, route, rng):
    res = {}
    for cid, car in CAR.items():
        r = h3.sweep_route(walls, car, route, rng); res[cid] = r
        print('WF_EXITS', name, cid, r['least_m'], r['status'], r['zone'], r['nearest'], 'staff', r['staff_least_m'], flush=True)
    return res


# ---------------------------------------------------------------------------------------------------------------------------------
# exit variants

XC = 101.8494
RA = 1.80                                   # axis radius of a carrier lying on the SP-12 floor (floor r 1.25 + the S capsule radius 0.43 + 0.12)
PSI = math.radians(15.0)
SLOT_W, SLOT_L, XS = 1.10, 2.50, 103.65     # N1: the axial slot hatch (width, length, centre X)


def duct_axis(psi, xa=XC+0.60, ra=RA):
    """Oblique duct axis in the radial plane at the airlock azimuth: r(x) = ra - (xa - x) tan psi (aft = down). Ends where r = 0.37 (an S
    capsule centred inside the trunk clear radius 0.80 less its 0.43)."""
    t = math.tan(psi); x_e = xa-(ra-0.37)/t
    return (xa, ra), (x_e, 0.37), t


def variants(s, data):
    tr = s['crew_transfer']['trunk_clear_radius_m']; xb = ct.stationary(s)[1]['points'][0][0]; out = {}
    ext = TRUNK_EXT_X
    def lying(r):
        return [P(XC, r)]
    # control: the built 0.90 m branch and the 1.10 m widening, on the same SP-12 rig (radial branch, carrier turns in the trunk)
    for nm, D in (('N0_branch_0.90', 0.90), ('N0_branch_1.10', 1.10)):
        out[nm] = dict(kind='control', D=D, ext=ext, unions=[lambda D=D: h3.prim_cyl(P(xb, 0.40), P(xb, 1.45), D/2)],
                       path=[('C', P(xb, 5.8)), ('B', P(xb, 1.2)), ('B', P(xb, 0.0)), ('T', (xb-1.0, 0.0, 0.0)), ('T', (97.0, 0.0, 0.0))],
                       smooth=False, area=math.pi*(D/2)**2, desc=f'radial branch {D:.2f} m on the airlock axis (X {xb:.3f}, 50 deg); the carrier turns aft in the trunk (control)')
    # N1: axial slot hatch, the carrier lowered without turning
    x0, x1 = XS-SLOT_L/2, XS+SLOT_L/2
    out['N1_axial_slot'] = dict(kind='axial', D=SLOT_W, ext=ext, unions=[lambda: h3.prim_box(P(XS, 0.85), axes_at(), (SLOT_L, SLOT_W, 1.20))],
                                path=[('C', P(XC, 5.8)), ('H', P(XC, RA)), ('F', P(x1-1.05+1.05, RA))], smooth=True, area=SLOT_W*SLOT_L,
                                desc=f'axial slot hatch {SLOT_W:.2f} x {SLOT_L:.2f} m in the SP-12 floor over the trunk extension (X {x0:.2f}-{x1:.2f}); the carrier lies along X and is lowered radially, no turn')
    # N2 / N3: 15 deg oblique duct sunk in the floor, landing in the trunk extension
    for nm, D in (('N2_oblique15_1.10', 1.10), ('N3_oblique15_1.20', 1.20)):
        (xa, ra), (xe, re), t = duct_axis(PSI)
        L = math.hypot(xa-xe, ra-re)
        out[nm] = dict(kind='oblique', D=D, ext=ext, psi_deg=15.0, unions=[lambda D=D, xa=xa, ra=ra, xe=xe, re=re: h3.prim_cyl(P(xa+0.35, ra+0.35*t), P(xe-0.4, re-0.4*t), D/2)],
                       path=[('C', P(XC, 5.8)), ('H', P(XC, ra-(xa-XC)*t)), ('D', P(xe, re)), ('T', (xe-1.4, 0.0, 0.0)), ('T', (xe-2.9, 0.0, 0.0))],
                       smooth=True, area=math.pi*(D/2)**2, duct=dict(xa=xa, ra=ra, xe=xe, re=re, length_m=round(L, 3)),
                       desc=f'{D:.2f} m round duct at 15 deg to the trunk axis, axis from (X {xa:.2f}, r {ra:.2f}) to (X {xe:.2f}, r {re:.2f}); sunk below the SP-12 floor, landing in the trunk')
    return out


def pose_lower(walls, car, name, rng):
    """N1: the carrier (head forward on +X) lowered radially from the floor run into the trunk extension, then moved aft along the extension and
    the built trunk: explicit poses, no turn. Returns the three legs and all poses."""
    L = h3.length(car); xh = XS+L/2; d = (-1.0, 0.0, 0.0)
    n = np.array((0.0, math.cos(AZ), math.sin(AZ))); tang = np.array((0.0, -math.sin(AZ), math.cos(AZ)))
    u, w0, t0 = h3.frame(d, 0.0); roll = math.atan2(float(np.dot(tang, t0)), float(np.dot(tang, w0)))
    lower = [((xh,)+tuple(n[1:]*r), d, roll, f'lower r {r:.2f}') for r in np.linspace(RA, 0.37, 15)]
    ext = [((xx,)+tuple(n[1:]*0.37), d, roll, f'extension x {xx:.2f}') for xx in np.arange(xh, 102.45+L, -0.25)]
    trunk = [((xx,)+tuple(n[1:]*0.20), d, roll, f'built trunk x {xx:.2f}') for xx in np.arange(102.45+L, 98.9, -0.25)]
    legs = {k: h3.sweep_poses(walls, car, p_, rng) for k, p_ in (('lowering through the slot (no turn)', lower), ('run aft in the L1-A extension', ext), ('run aft in the built trunk (HUM-003 fixtures)', trunk))}
    return legs, lower+ext+trunk


def staff_at(walls, rng, poses, car):
    """Rescuer capsules (r 0.25) at both ends of the carrier over an explicit pose list (the best of 60 placements each end)."""
    L = h3.length(car); least = (math.inf, None, None)
    for h, d, r, lab in poses[::2]:
        d = np.asarray(d, float); h = np.asarray(h, float)
        for end, ahead in ((tuple(h), tuple(h+d*(-.7))), (tuple(h+d*L), tuple(h+d*(L+.7)))):
            m = h3.best_staff(walls, end, ahead, rng, n=30)
            if m[0] < least[0]:
                least = (round(m[0], 3), m[1], lab)
    return least


def closure_data(s, v):
    """Closure on the route (SP-12 -> trunk): count with the SP-11 inner plug, size, ideal pressure load at 80 kPa (DIAGNOSTIC, clear area x cabin
    pressure) and the parked-leaf pocket against the SP-12 fit-out and the SP-11 plug envelope (sampled, PROTOTYPE sliding plug on the SP-12 face)."""
    D = v['D']; A = v['area']; ideal = round(CABIN_KPA*A, 1)
    if v['kind'] == 'axial':
        leaf = (SLOT_L+0.30, SLOT_W+0.30); pocket = f'rectangular sliding cover {leaf[0]:.2f} x {leaf[1]:.2f} m parked 1.50 m toward +az on the SP-12 floor'
        tang_shift = 1.50; px, ptw = SLOT_L+0.30, SLOT_W+0.30; cx = XS; cr = 1.30
    else:
        rl = D/2+0.05; pocket = f'sliding plug leaf radius {rl:.2f} m parked {2*rl+0.05:.2f} m toward +az beside the aperture'
        tang_shift = 2*rl+0.05; px = ptw = 2*rl; cx = v.get('duct', {}).get('xa', 0)-0.3 if v['kind'] == 'oblique' else 101.849; cr = 1.30
    dm = math.inf; near = None; fb = fixture_boxes(load_room(s))
    # pocket samples (floor level, centre cx, tangent tang_shift, size px x ptw); distance to each fixture box (oriented), exact point-to-box
    for ix in np.linspace(-px/2, px/2, 9):
        for it in np.linspace(-ptw/2, ptw/2, 9):
            p = np.array(P(cx+ix, cr, tang_shift+it))
            for (c, ax, sz), nm in zip(fb, FIX_NAMES):
                q = p-np.array(c); loc = [float(np.dot(q, np.array(a))) for a in ax]
                dd = math.sqrt(sum(max(abs(l)-z/2, 0.0)**2 for l, z in zip(loc, sz)))
                if dd < dm:
                    dm, near = dd, nm
    return dict(closures_on_route=['SP-11 inner plug 1.20 m (existing study)', 'SP-12 exit closure'], closure_count=2, exit_aperture=f'{D:.2f} m' + (' x %.2f m' % SLOT_L if v['kind'] == 'axial' else ' round'),
                clear_area_m2=round(A, 3), ideal_load_kn_80kpa=ideal, ideal_basis='80 kPa BASELINE x clear aperture area, DIAGNOSTIC (not a seat load, not a rating)',
                pocket=pocket, pocket_to_fixtures_m=round(dm, 3), pocket_nearest=near, pocket_status=status(dm))


FIX_NAMES = []


def load_room(s):
    global FIX_NAMES
    data = es.load(ROOT); room = data['sp12']
    FIX_NAMES = [fi['id'] for fi in room['fixtures'] if fi['kind'] != 'zone']
    return room


def vehicle_screen(s, obs, v):
    """The exit solid against the saved vehicle (every built mesh except the trunk, spine and airlock fittings), as boxes along the axis at the
    mechanical clearance: names hit and whether it stays inside the hull."""
    hits = set(); inside = True; clr = s['prototype']['mechanical_clearance_m']
    if v['kind'] == 'axial':
        boxes = [sv.box(XS-SLOT_L/2, XS+SLOT_L/2, AZ, 0.25, 1.45, SLOT_W/2, clr)]
    else:
        D = v['D']
        if v['kind'] == 'control':
            xb = ct.stationary(s)[1]['points'][0][0]; boxes = [sv.box(xb-D/2, xb+D/2, AZ, 0.40, 1.45, D/2, clr)]
        else:
            d = v['duct']; n = 14; boxes = []
            for k in range(n):
                xa = d['xe']+(d['xa']-d['xe'])*k/n; xb_ = d['xe']+(d['xa']-d['xe'])*(k+1)/n
                r1 = d['re']+(d['ra']-d['re'])*k/n; r2 = d['re']+(d['ra']-d['re'])*(k+1)/n
                boxes.append(sv.box(min(xa, xb_)-0.05, max(xa, xb_)+0.05, AZ, max(0.0, min(r1, r2)-D/2), max(r1, r2)+D/2, D/2, clr))
    for b in boxes:
        hits |= obs.hits(b, ignore=('Structural_Spine', 'Crew_Trunk', 'Airlock_EVA', 'Crew_Connector_Airlock_EVA', 'Trunk_Fit_', 'Crew_Trunk_')); inside &= sv.inside_hull(s, b)
    return dict(hits=sorted(hits), inside_hull=inside, status='CLEAR' if not hits and inside else 'BLOCKED')


def spine_cut(s, v):
    """Length (X, m) over which the exit's solid lies inside the spine core annulus r 0.85-0.95 (the trunk wall to the core's radius): a structural
    cut that is OPEN. Sampled along X."""
    core = s['prototype']['spine_core_radius_m']; w = s['crew_transfer']['passage_wall_m']; tr = s['crew_transfer']['trunk_clear_radius_m']
    xs = np.arange(95.0, 108.0, 0.02); n = 0
    for x in xs:
        if v['kind'] == 'axial':
            inside = abs(x-XS) <= SLOT_L/2
        elif v['kind'] == 'control':
            xb = ct.stationary(s)[1]['points'][0][0]; inside = abs(x-xb) <= v['D']/2
        else:
            d = v['duct']; rax = d['re']+(d['ra']-d['re'])*(x-d['xe'])/(d['xa']-d['xe'])
            half = v['D']/2/math.cos(PSI); inside = d['xe'] <= x <= d['xa'] and rax+half >= tr+w and rax-half <= core
        n += 1 if inside else 0
    return round(n*0.02, 2)


# ---------------------------------------------------------------------------------------------------------------------------------

def run_exits(s, data, records, obs, rng, out):
    res = {}; V = variants(s, data)
    for nm, v in V.items():
        obj, tree = build_free(s, data, v['unions'], [], v['ext'], fit=FIT)
        route = smooth(v['path'], cut=0.55 if v['kind'] != 'control' else 0.25) if v['smooth'] else v['path']
        pts = [p for _, p in v['path']]
        walls = h3.Walls(h3.fixtures(records), [(x, y, z) for x in np.linspace(95, 105.5, 22) for y in (-3, 0, 3) for z in (-3, 0, 3)], free=tree)
        row = dict(desc=v['desc'], kind=v['kind'], psi_deg=v.get('psi_deg', 0.0 if v['kind'] == 'axial' else 90.0), clear_m=v['D'])
        if v['kind'] == 'axial':
            first = zone_sweep_part(walls, nm, route, rng)
            row['legs'] = {}
            for cid, car in CAR.items():
                lowlegs, poses = pose_lower(walls, car, nm, rng); stf = staff_at(walls, rng, [q for q in poses if 'lower' in q[3]], car)
                stf2 = staff_at(walls, rng, [q for q in poses if 'lower' not in q[3]], car); r1 = first[cid]
                row['legs'][cid] = {'turn-in under the SP-11 bulkhead and the SP-12 floor run': dict(least_m=r1['least_m'], status=r1['status'], nearest=r1['nearest'], by_zone=r1['by_zone'],
                                                                                                      head=r1['head'], axis=r1['axis'], roll=r1['roll'])}
                for k, q in lowlegs.items():
                    row['legs'][cid][k] = dict(least_m=q['least_m'], status=q['status'], nearest=q['nearest'], at=q['at'], head=q['head'], axis=q['axis'], roll=q['roll'])
                row['legs'][cid]['rescuers: SP-12 floor run'] = dict(least_m=r1['staff_least_m'], status=r1['staff_status'], nearest=r1['staff_nearest'])
                row['legs'][cid]['rescuers: lowering'] = dict(least_m=stf[0], status=status(stf[0]), nearest=stf[1], at=stf[2])
                row['legs'][cid]['rescuers: aft runs'] = dict(least_m=stf2[0], status=status(stf2[0]), nearest=stf2[1], at=stf2[2])
        else:
            sw = zone_sweep(walls, nm, route, rng); row['legs'] = {}
            for cid, r in sw.items():
                row['legs'][cid] = dict(least_m=r['least_m'], status=r['status'], nearest=r['nearest'], zone=r['zone'], head=r['head'], axis=r['axis'], roll=r['roll'],
                                        by_zone=r['by_zone'], rescuers=dict(least_m=r['staff_least_m'], status=r['staff_status'], nearest=r['staff_nearest'], zone=r['staff_zone']))
        row['closures'] = closure_data(s, v); row['vehicle'] = vehicle_screen(s, obs, v); row['spine_core_cut_x_m'] = spine_cut(s, v)
        L = v.get('duct', {}).get('length_m')
        if v['kind'] == 'oblique':
            row['exit_shell_m2'] = round(math.pi*v['D']*L, 1)
        elif v['kind'] == 'axial':
            row['exit_shell_m2'] = round(2*SLOT_L*1.2+2*SLOT_W*1.2, 1)
        else:
            row['exit_shell_m2'] = 0.0
        row['exit_shell_mass_kg'] = round(row['exit_shell_m2']*SHELL_KG_M2, 0)
        res[nm] = row
        res[nm]['_viz'] = dict(path=route)
        render_variant(nm, obj, row, out)
        bpy.data.objects.remove(obj)
    # the oblique angle scan against the vehicle: the shallowest duct the saved vehicle allows
    scan = {}
    for deg in (10, 12, 15, 20, 25, 30, 35, 40):
        psi = math.radians(deg); (xa, ra), (xe, re), t = duct_axis(psi); vv = dict(kind='oblique', D=1.10, duct=dict(xa=xa, ra=ra, xe=xe, re=re))
        scan[deg] = dict(length_m=round(math.hypot(xa-xe, ra-re), 2), lands_at_x=round(xe, 2), vehicle=vehicle_screen(s, obs, vv), spine_core_cut_x_m=spine_cut(s, dict(vv, D=1.10)))
    res['_oblique_angle_scan_D1.10'] = scan
    return res


def zone_sweep_part(walls, nm, route, rng):
    return zone_sweep(walls, nm, route, rng)


# ---------------------------------------------------------------------------------------------------------------------------------
# SP-13 second exit

def run_sp13(s, data, records, obs, rng, out):
    clr = s['prototype']['mechanical_clearance_m']; x = 106.025; res = {}
    for D in (0.90, 1.10):
        for az in (35, 45, 55):
            a = math.radians(az)
            port = lambda D=D, a=a: h3.prim_cyl(P(x, 0.40, az=a), P(x, 1.45, az=a), D/2)
            obj, tree = build_free(s, data, [port], [], TRUNK_EXT_X, sp12=False, sp13=True, ref=False, fit=FIT)
            walls = h3.Walls([], [(x_, y, z) for x_ in np.linspace(103, 107.5, 10) for y in (-3, 0, 3) for z in (-3, 0, 3)], free=tree)
            row = dict(clear_m=D, az_deg=az, x=x)
            route = smooth([('R', P(x, 3.6, az=a)), ('B', P(x, 1.2, az=a)), ('B', P(x, 0.0, az=a)), ('T', (x-1.4, 0.0, 0.0)), ('T', (x-3.0, 0.0, 0.0))], cut=0.5)
            for cid, car in CAR.items():
                r = h3.sweep_route(walls, car, route, rng)
                row[cid] = dict(least_m=r['least_m'], status=r['status'], nearest=r['nearest'], zone=r['zone'], by_zone=r['by_zone'],
                                rescuers=dict(least_m=r['staff_least_m'], status=r['staff_status']))
            crew = dict(shape='capsule', length=1.25, radius=0.35)       # an unsuited crew member tucked/crouching, the 0.70 m route-control envelope
            r = h3.sweep_route(walls, crew, route, rng, staff=False)
            row['unsuited'] = dict(least_m=r['least_m'], status=r['status'], nearest=r['nearest'], by_zone=r['by_zone'], envelope='capsule r 0.35 m (the 0.70 m route-control key), 1.25 m long')
            row['port_margin_to_0.70_m'] = round(D-0.70, 3)
            print('WF_EXITS_SP13', D, az, {k: row[k]['least_m'] for k in ('S', 'K', 'unsuited')}, flush=True)
            res[f'D{D:.2f}_az{az}'] = row
            bpy.data.objects.remove(obj)
    ld = ea.door(s, 1.10)
    res['_closure'] = dict(count_on_route=1, closure='SP-13 port hatch from the trunk extension, seats from the trunk side (a SP-13 fire/leak holds it shut)',
                           ideal_load_kn_80kpa={'0.90': round(CABIN_KPA*math.pi*.45**2, 1), '1.10': round(CABIN_KPA*math.pi*.55**2, 1)}, seat_load_kn_leaf_1_10=ld['seat_load_kn'])
    res['_independence'] = independence()
    return res


def independence():
    return dict(
        exits=dict(
            SP12=['SP-11 inner plug 1.20 m (chamber side only)', 'SP-12 exit closure (N1 slot / N2-N3 duct / N0 branch) between SP-12 and the trunk extension'],
            SP13=['SP-13 port hatch between SP-13 and the trunk extension']),
        shared_closures=[], shared_volumes=['trunk extension X 102.45-107.4 (destination of both exits; a shirt-sleeve volume, not a SP-12 or SP-13 volume)'],
        not_shared=['SP-12/SP-13 door (stays closed on the SP-13 exit; neither exit needs it)', 'SP-12 ventilation loop and SP-13 ventilation loop (own, isolatable per topology)'],
        pressure_isolation_points=['SP-13 port hatch (seats from the trunk side)', 'SP-12 exit closure (seats from the trunk side in the study; N1 slot cover is a large sliding cover, side OPEN)',
                                   'SP-12/SP-13 door (seats from SP-12)', 'district hatch at the trunk end (seats from the trunk side)'],
        fire_heat_points=['SP-13 hosts battery charging and drying (the thermal/fire load of the pair); its port hatch and the SP-12/13 door isolate it from both the trunk and SP-12',
                          'SP-12 hosts O2 preparation (oxidizer-rich); its closure and the SP-11 inner plug isolate it',
                          'no common closure: a fire or leak in one room leaves the other exit available, provided the trunk extension itself stays habitable (shared volume, OPEN)'],
        status='PROTOTYPE: independence holds for closures; the destination volume is shared, so a trunk-extension event takes both')


# ---------------------------------------------------------------------------------------------------------------------------------
# L1-A ladder bypass at Dock_Primary (pure geometry)

def bypass(s):
    h = s['human_entry']; c = s['crew_transfer']; L = he.trunk_ladder(s); th = L['th']; rl = L['rl']; phi = L['phi']
    ops = he.openings(s); dock = next(o for o in ops if o[0] == 'Crew_Connector_Dock_Primary'); xd = dock[1]; rd = dock[3]
    out = dict(ladder=dict(angle_deg=round(math.degrees(th), 1), stile_radius_m=round(rl, 3), stile_half_angle_deg=round(math.degrees(phi), 2), width_m=h['spoke_ladder_width_m'],
                           present_floor_x=round(L['floor'], 3), present_top_x=round(L['top'], 3), rung_pitch_m=h['spoke_rung_pitch_m'], first_rung_m=h['landing_first_rung_m']),
               dock=dict(x=xd, angle_deg=round(math.degrees(dock[2]) % 360, 1), radius_m=rd, trunk_clear_radius_m=c['trunk_clear_radius_m'], opening_margin_m=h['opening_margin_m']))
    # gap of each stile line and of the arrest rail at the ladder angle, for margin 0 (the opening itself) and the 0.20 m opening margin (hands/brackets)
    gaps = {}
    for mname, m in (('opening_only', 0.0), ('with_0.20_margin', h['opening_margin_m'])):
        row = {}
        for nm, rho, ang in (('stile_a', rl, L['stiles'][0]), ('stile_b', rl, L['stiles'][1]), ('arrest_rail', L['rail_r'], th), ('hoist_guide_105', c['trunk_clear_radius_m']-.08, th+math.pi)):
            sp = he.clear_spans(s, rho, ang, 96.0, 104.9, margin=m)
            blocked = [(round(a1, 3), round(b0, 3)) for (a0, a1), (b0, b1) in zip(sp, sp[1:])]
            row[nm] = dict(clear_spans=[(round(a, 3), round(b, 3)) for a, b in sp], gaps=blocked, dock_gap_length_m=round(max([b-a for a, b in blocked if a < xd < b] or [0.0]), 3))
        gaps[mname] = row
    out['gaps_at_ladder_angle'] = gaps
    # ladder-angle scan of the dock gap (stile pair) with margin 0: the cusp
    scan = {}
    for deg in range(255, 316, 5):
        a = math.radians(deg); worst = 0.0
        for sg in (-1, 1):
            sp = he.clear_spans(s, rl, a+sg*phi, 96.0, 104.9, margin=0.0)
            for (a0, a1), (b0, b1) in zip(sp, sp[1:]):
                if a1 < xd < b0:
                    worst = max(worst, b0-a1)
        scan[deg] = round(worst, 3)
    out['stile_pair_dock_gap_by_angle_deg_m'] = scan
    # bridge design (PROTOTYPE): the stile pair carried across the dock gap as a rigid bridge anchored at the clear spans' ends, rungs on the pitch,
    # the arrest rail resting on the rungs, a cheek guard plate between the stiles and the wall; structural sizing OPEN
    g = gaps['with_0.20_margin']; span = max(g['stile_a']['dock_gap_length_m'], g['stile_b']['dock_gap_length_m'])
    rungs = [r_ for r_ in L['rungs']]; p = h['spoke_rung_pitch_m']
    out['bridge'] = dict(span_m=round(span, 3), anchored_from_to_x=[round(xd-span/2, 3), round(xd+span/2, 3)], rungs_continue_at_pitch_m=p, rungs_in_span=int(span/p),
                         arrest_rail='continuous: the rail rests on the climber side of the rungs, which the bridge carries; no break over the mouth',
                         guard='cheek plate between the stiles and the trunk wall over the span (curved, 0.04 m off the wall), so a foot or hand cannot go into the connector gap',
                         structure='OPEN (unsized): a 1.0-1.7 m two-stile beam carrying a climber at 1.5 g (14.7 N/kg of climber, suit and tool, masses OPEN)')
    # climber figure rung by rung across the mouth: the rim curve of the connector against every body rod
    clim = he.trunk_climber(s); n = ct.radial(0, 1.0, dock[2]); e = (0.0, -math.sin(dock[2]), math.cos(dock[2]))
    rim = []
    for k in range(180):
        psi = 2*math.pi*k/180; a_ = math.sqrt(max(0.0, c['trunk_clear_radius_m']**2-(rd*math.sin(psi))**2)); lat = rd*math.sin(psi)
        rim.append((xd+rd*math.cos(psi), a_*n[1]+lat*e[1], a_*n[2]+lat*e[2]))
    kd = KDTree(len(rim)); [kd.insert(Vector(q), i) for i, q in enumerate(rim)]; kd.balance()
    xf0 = clim['feet_x']; worst = (math.inf, None, None); table = []
    for x_f in np.arange(97.0, 101.5, 0.1):
        dx = x_f-xf0; least = (math.inf, None)
        for nm, pts, rad in clim['rods']:
            for k in range(7):
                a_ = np.add(pts[0], np.subtract(pts[1], pts[0])*k/6) + np.array((dx, 0, 0)); dd = kd.find(Vector(a_))[2]-rad
                if dd < least[0]:
                    least = (dd, nm)
        table.append((round(float(x_f), 2), round(least[0], 3), least[1]))
        if least[0] < worst[0]:
            worst = (least[0], least[1], round(float(x_f), 2))
    out['climber_vs_connector_rim'] = dict(least_m=round(worst[0], 3), status=status(worst[0]), body_part=worst[1], feet_x=worst[2], sampled=table[::5],
                                           note='the rim is the intersection curve of the r 0.85 connector with the trunk; the climber is 0.65 m off the axis at the 285 deg station, so the rim is where the wall is, not a trap')
    # dock passage envelope kept: a person crossing the trunk centre line from the connector (0.70 m envelope) against the bridge/ladder line
    out['dock_passage_vs_bridge'] = dict(envelope_radius_m=0.35, bridge_stile_radius_m=round(rl, 3), gap_m=round(rl-0.35-0.0175, 3), status=status(rl-0.35-0.0175),
                                         note='the bridge sits 90 deg round from the connector axis; a 0.70 m envelope on the trunk axis clears the stiles (the ladder is already there above and below)')
    # hands/feet geometry of the figure (as built): grips at 0.87 H, reach and feet on the rung
    out['climber_figure'] = dict(arm_reach_m={k: round(v_, 3) for k, v_ in clim['reach'].items()}, feet_x=round(clim['feet_x'], 3), head_x=round(clim['head_x'], 3),
                                 grips_x=[round(g_[0], 3) for g_ in clim['grips']], note='the figure of he.trunk_climber (hands on the stiles above the shoulder, soles on the rung, arrester on the rail); on the bridge the same pose repeats rung for rung since the bridge carries the same stiles, rungs and rail')
    # hoist line 0.20-0.25 m off axis toward 105 deg: carrier and attendant clearances inherited from HUM-003 (built trunk; the connector mouth is in that model)
    try:
        hz = json.loads((ROOT/'references/p1_hum003.json').read_text())['local']['hoist']
        sel = {cid: {k: dict(carrier_least_m=v_['carrier_least_m'], attendant_gap_m=v_['attendant_gap_m']) for k, v_ in rows.items() if k.startswith(('e_0.20', 'e_0.25'))} for cid, rows in hz['offsets'].items() if cid in 'SK'}
        out['hoist_line_105deg'] = dict(offsets_m=[0.20, 0.25], source='references/p1_hum003.json local.hoist (HUM-003; not re-run)', rows=sel,
                                        guide_rail_clear_spans_x=hz['guide_rail_clear_spans_x'])
    except Exception as ex:
        out['hoist_line_105deg'] = dict(error=str(ex))
    # upper run: the extended stile line to 104.9 against the openings of L1-A (the built ones minus the bridged dock mouth, plus the district port, the exits and the SP-13 port)
    built = he.openings(s); add = [('District_Port_240', 104.1, math.radians(240), 0.45), ('SP12_Exit_N1_slot', XS, AZ, SLOT_W/2), ('SP13_Port', 106.025, math.radians(45), 0.45)]
    keep = he.openings
    ang = {}
    for mname, m in (('margin_0.20', h['opening_margin_m']), ('margin_0', 0.0)):
        ang[mname] = []
        for deg in range(0, 360, 5):
            a = math.radians(deg); ok = True
            for sg in (-1, 1):
                he.openings = lambda _s, ops=[o for o in built if o[0] != 'Crew_Connector_Dock_Primary']+add: ops
                sp = he.clear_spans(s, rl, a+sg*phi, xd+span/2, 104.9, margin=m)
                he.openings = keep
                ok &= any(a0 <= xd+span/2+1e-6 and b0 >= 104.9-1e-6 for a0, b0 in sp)
            if ok:
                ang[mname].append(deg)
    he.openings = keep
    ang_ok = ang
    out['upper_run_to_104.9'] = dict(angles_clear_deg=ang_ok, built_285_clear={k: 285 in v_ for k, v_ in ang_ok.items()},
                                     openings_added=[(n, x_, round(math.degrees(a_) % 360, 1), r_) for n, x_, a_, r_ in add],
                                     note='stile pair clear over [dock bridge end, 104.9] against the built openings (minus the bridged dock mouth) plus the three added ones; the run below the bridge is the built ladder')
    # ladder top at 1.5 g: present top 98.6 -> 104.9 is 6.3 m; the extension past the dock gap is the new section
    out['extension_m'] = dict(present_top=round(L['top'], 3), to=104.9, total_m=round(104.9-L['top'], 2), bridge_m=round(span, 2), above_bridge_m=round(104.9-(xd+span/2), 2))
    out['status'] = 'CANDIDATE (PROTOTYPE): continuous by a bridge over the dock mouth; structure, arrester lock and bridge-versus-docking-passage swing are OPEN'
    return out


# ---------------------------------------------------------------------------------------------------------------------------------
# L1-A versus corridor B

def compare(s, data, obs):
    d = json.loads((ROOT/'references/p1_eva_district.json').read_text())
    A, B = d['layouts']['L1-A'], d['layouts']['L1-B']
    lead = next(r for r in json.loads((ROOT/'references/p1_eva_sp11.json').read_text())['rows'] if abs(r['aperture_m']-data['sp11_eva3']['lead_m']) < 1e-9)
    eva, br = ed.eva_elements(s, data, lead)
    res = {}
    for key, opt, L in (('L1-A', 'A', A), ('L1-B', 'B', B)):
        o, R, els, ext = ed.serv_elements(s, obs, math.radians(L['workshop_deg']), opt, math.radians(L['warm_deg']), L['warm_x0'])
        allel = eva+[e for e in els if e['name'] != 'trunk_extension']; by = {e['name']: e for e in allel}
        pts = {e['name']: ed.samples(e) for e in allel}
        def sep(a, b):
            kd = KDTree(len(pts[b])); [kd.insert(Vector(p), i) for i, p in enumerate(pts[b])]; kd.balance()
            return round(min(kd.find(Vector(p))[2] for p in pts[a][::3]), 2)
        warm = 'warm_SP52'
        seps = {n: sep(warm, n) for n in by if n != warm and not n.startswith('passage') and n != 'SP12_branch'}
        # measured nearest distance to the survival reserves and the refuge (BVH nearest, sampled)
        near = {}
        for nm in ('Survival_Reserve_1', 'Survival_Reserve_2', 'Refuge_Storm_Shelter'):
            ob = next((q for q in obs.objs if q['name'].startswith(nm) and 'Brackets' not in q['name']), None)
            if ob is None:
                continue
            for en in ('workshop', 'cell', warm, 'SP12', 'SP13'):
                dd = min(ob['tree'].find_nearest(Vector(p))[3] for p in pts[en][::4])
                near[f'{nm} -> {en}'] = round(dd, 2)
        shell = L['new_shell_m2']
        res[key] = dict(title=L['title'], new_shell_m2=shell, new_shell_mass_t=round(shell*SHELL_KG_M2/1e3, 2), shell_by_element_m2=L['shell_m2'], coolant_run_m=L['warm_feed']['length_m'],
                        coolant_panel=L['warm_feed']['panel'], sp52_separation_m=seps, reserve_refuge_distance_m=near, interfaces=o.get('new_pressure_interfaces'),
                        trunk_connection=(o.get('port') or o.get('trunk_port')), volumes_m3=L['volumes_m3'])
    return res


# ---------------------------------------------------------------------------------------------------------------------------------
# renders (Workbench): the exit solid, the best-pose carriers, side view in the airlock plane

def render_variant(nm, obj, row, out):
    sc = bpy.context.scene; keep = [o for o in bpy.data.objects if not o.hide_render and o is not obj]
    for o in keep:
        o.hide_render = True
    made = []
    obj.hide_render = False
    mat = bpy.data.materials.new('free'); mat.diffuse_color = (.3, .6, .9, 1); obj.data.materials.append(mat)
    cut = h3.prim_box(P(102.0, 3.0, 10.5), axes_at(), (30.0, 21.0, 14.0)); h3.boolean(obj, cut, 'DIFFERENCE')      # open the near half: look into the cavity from +tangent
    for cid, col in (('S', (1.0, .5, .1, 1)), ('K', (.2, .9, .3, 1)), ('A', (.2, .9, .3, 1))):
        legs = row['legs'].get(cid, {}); cands = [legs] if 'head' in legs else [v for v in legs.values() if isinstance(v, dict) and 'head' in v]
        if not cands:
            continue
        leg = min(cands, key=lambda q: q['least_m']); car = CAR[cid] if cid in CAR else h3.CARRIERS[cid]; head, d, roll = leg['head'], leg['axis'], leg['roll']
        if car['shape'] == 'box':
            vs, fs = h3.box_mesh(h3.boxes(car, head, d, roll), 0.0); me = bpy.data.meshes.new(cid); me.from_pydata(vs, [], fs); ob = link(me, cid)
        else:
            a = np.asarray(head)+np.asarray(d)*car['radius']; b = np.asarray(head)+np.asarray(d)*(car['length']-car['radius'])
            ob = h3.prim_cyl(tuple(a), tuple(b), car['radius'])
        m = bpy.data.materials.new(cid); m.diffuse_color = col; ob.data.materials.append(m); made.append(ob)
    cam = bpy.data.objects.new('CAM_EXIT', bpy.data.cameras.new('CAM_EXIT')); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'; sc.render.resolution_x, sc.render.resolution_y = 1400, 800
    ax = axes_at(); look = Vector((-ax[1][0], -ax[1][1], -ax[1][2])); up = Vector(ax[2]); loc = Vector(P(102.0, 0.0, 25.0))
    z = -look.normalized(); x = up.cross(z).normalized(); y = z.cross(x)
    cam.location = loc; cam.rotation_euler = Matrix((x, y, z)).transposed().to_euler(); cam.data.type = 'ORTHO'; cam.data.ortho_scale = 12.0
    cam.data.shift_x = 0.0; cam.data.clip_start = .1; cam.data.clip_end = 60
    # centre on X ~ 102, r ~ 2.3 : the view axis is -tangential; translate the camera in the view plane
    cam.location = Vector(P(101.5, 2.3, 25.0)); sc.render.filepath = str(out/f'exit_{nm}_{"fit" if FIT else "bare"}.png'); bpy.ops.render.render(write_still=True)
    for o in made:
        bpy.data.objects.remove(o)
    bpy.data.objects.remove(cam)
    for o in keep:
        o.hide_render = False


# ---------------------------------------------------------------------------------------------------------------------------------
# SIM-027: the SP-11 -> SP-12 litter turn and the rearranged SP-12 path (DIST-005, owner 2026-10-11 16:45)

CAR_R = {'S': h3.CARRIERS['S'], 'A': h3.CARRIERS['A']}      # S suited casualty on the full-length frame; A rigid litter 2.00 x 0.55 x 0.30 m
SEEDS = (17, 23, 41)


def turn_route(v, car):
    """Waypoints of the carrier's head: down the chamber, through the aperture, to the lowering station over the slot (or the N1 slot end)."""
    xs = v['slot_x_m']; L = h3.length(car); xh = xs+L/2; x_end = xs+SLOT_L/2 if v['end'] == 'slot_end' else xh
    if v['route'] == 'corner':
        return smooth([('C', P(XC, 5.8)), ('H', P(XC, RA)), ('F', P(x_end, RA))], cut=0.55)
    return smooth([('C', P(XC, 5.8)), ('D', P(XC, 2.9)), ('H', P(XC+0.9, RA)), ('F', P(x_end, RA))], cut=0.7)


def sweep_route_ex(walls, car, route, rng, staff='two'):
    """h3.sweep_route's sampled-pose sweep with the staff choice of the variant: two = a rescuer at each end, foot = one at the foot (tail) end only."""
    import casualty_sweep as cs
    L = h3.length(car); path = tuple(zip(*route)); cum = cs.cumulative(path[1]); res = dict(least=(math.inf,), zones={}, staff=(math.inf, None, None))
    for tt in np.arange(L, cum[-1]+1e-9, h3.STEP_M):
        zone, head = cs.at(path, cum, tt); ts = cs.behind(path, cum, tt, head, L); tail = cs.at(path, cum, ts)[1]
        tm = cs.behind(path, cum, tt, head, min(1.4, L*.7)); mid = cs.at(path, cum, tm)[1]; seeds = [tail]; dm = np.subtract(mid, head)
        if np.linalg.norm(dm) > 1e-6:
            seeds.append(tuple(np.asarray(head)+dm/np.linalg.norm(dm)*L))
        best = None
        for sd in seeds:
            d = np.subtract(sd, head)
            if np.linalg.norm(d) < 1e-6:
                continue
            b = h3.best_pose(walls, car, head, sd, h3.turn_roll(path, cum, tt, d), rng)
            if best is None or b[0] > best[0]:
                best = b
            if best[0] >= h3.CAP_M:
                break
        m, name, h, d, r = best; z = str(zone)
        if m < res['zones'].get(z, (math.inf,))[0]:
            res['zones'][z] = (round(m, 3), name, round(float(tt), 2))
        if m < res['least'][0]:
            res['least'] = (round(m, 3), name, z, round(float(tt), 2), [round(float(x), 3) for x in h], [round(float(x), 3) for x in d], round(r, 3))
        ends = ((tuple(h), tt+h3.STAFF_REACH_M), (tuple(h+d*L), ts-h3.STAFF_REACH_M)) if staff == 'two' else ((tuple(h+d*L), ts-h3.STAFF_REACH_M),)
        for a, t2 in ends:
            if 0.0 <= t2 <= cum[-1]:
                sm = h3.best_staff(walls, a, cs.at(path, cum, t2)[1], rng)
                if sm[0] < res['staff'][0]:
                    res['staff'] = (round(sm[0], 3), sm[1], z)
    le = res['least']
    return dict(least_m=le[0], status=h3.status(le[0]), nearest=le[1], zone=le[2], at_m=le[3], head=le[4], axis=le[5], roll=le[6],
                by_zone={z: dict(least_m=v[0], status=h3.status(v[0]), nearest=v[1], at_m=v[2]) for z, v in res['zones'].items()},
                staff_least_m=None if res['staff'][0] == math.inf else res['staff'][0], staff_nearest=res['staff'][1], staff_status=h3.status(res['staff'][0]))


def pose_lower_at(walls, car, rng, xs, staff):
    """pose_lower for a slot centred at xs: lowering through the slot, then aft along the extension and the built trunk, with the rescuers of the staff mode."""
    L = h3.length(car); xh = xs+L/2; d = (-1.0, 0.0, 0.0)
    n = np.array((0.0, math.cos(AZ), math.sin(AZ))); tang = np.array((0.0, -math.sin(AZ), math.cos(AZ)))
    u, w0, t0 = h3.frame(d, 0.0); roll = math.atan2(float(np.dot(tang, t0)), float(np.dot(tang, w0)))
    lower = [((xh,)+tuple(n[1:]*r), d, roll, f'lower r {r:.2f}') for r in np.linspace(RA, 0.37, 15)]
    x_ext = min(xh, 102.45+L)             # a slot shifted aft lowers the carrier with its tail already past the extension's aft end: the extension leg is then the lowered pose
    ext = [((xx,)+tuple(n[1:]*0.37), d, roll, f'extension x {xx:.2f}') for xx in np.arange(xh, x_ext-1e-9, -0.25)]
    trunk = [((xx,)+tuple(n[1:]*0.20), d, roll, f'built trunk x {xx:.2f}') for xx in np.arange(x_ext, 98.9, -0.25)]
    legs = {k: h3.sweep_poses(walls, car, p_, rng) for k, p_ in (('lowering through the slot', lower), ('run aft in the extension', ext), ('run aft in the built trunk', trunk))}

    def stf(poses):
        least = (math.inf, None, None)
        for h, d_, r, lab in poses[::2]:
            d_ = np.asarray(d_, float); h = np.asarray(h, float)
            ends = ((tuple(h), tuple(h+d_*(-.7))), (tuple(h+d_*L), tuple(h+d_*(L+.7)))) if staff == 'two' else ((tuple(h+d_*L), tuple(h+d_*(L+.7))),)
            for end, ahead in ends:
                m = h3.best_staff(walls, end, ahead, rng, n=30)
                if m[0] < least[0]:
                    least = (round(m[0], 3), m[1], lab)
        return least
    return legs, stf(lower), stf(ext+trunk)


def run_litter_turn(s, data, records, obs, out, seeds=SEEDS, only=None):
    """Every redline_sp12_path variant x carrier (S, A) x seed. Per leg the least over the seeds is reported with the seed spread."""
    import copy
    global XS, CAR
    jf = out/'eva3_litter_turn.json'; res = json.loads(jf.read_text()) if only and jf.exists() else {}; keep = (XS, CAR); CAR = CAR_R
    try:
        for v in data['sp11_plug']['redline_sp12_path']:
            if only and v['id'] not in only:
                continue
            d2 = copy.deepcopy(data)
            for f in d2['sp12']['fixtures']:
                if f['id'] in ('SP12_DON_STAND_A', 'SP12_DON_STAND_B'):
                    f['az'] = v['stand_az_deg']
            XS = v['slot_x_m']
            obj, tree = build_free(s, d2, [lambda: h3.prim_box(P(XS, 0.85), axes_at(), (SLOT_L, SLOT_W, 1.20))], [], TRUNK_EXT_X, fit=v['fitout'] != 'bare', hole_r=v.get('aperture_m', 1.20)/2)
            walls = h3.Walls(h3.fixtures(records), [(x, y, z) for x in np.linspace(95, 105.5, 22) for y in (-3, 0, 3) for z in (-3, 0, 3)], free=tree)
            row = dict(what=v['what'], spec=v, legs={}); vv = dict(kind='axial', D=SLOT_W, area=SLOT_W*SLOT_L)
            for cid, car in CAR_R.items():
                per = {}
                for seed in seeds:
                    rng = np.random.default_rng(seed)
                    tr = sweep_route_ex(walls, car, turn_route(v, car), rng, v['staff'])
                    lows, sl_, sa_ = pose_lower_at(walls, car, rng, XS, v['staff'])
                    legs = {'turn: chamber, aperture, corner, floor run to the lowering station': dict(tr)}
                    legs.update({k: dict(q) for k, q in lows.items()})
                    legs['rescuers: turn and floor run'] = dict(least_m=tr['staff_least_m'], status=tr['staff_status'], nearest=tr['staff_nearest'])
                    legs['rescuers: lowering'] = dict(least_m=sl_[0], status=status(sl_[0]), nearest=sl_[1], at=sl_[2])
                    legs['rescuers: aft runs'] = dict(least_m=sa_[0], status=status(sa_[0]), nearest=sa_[1], at=sa_[2])
                    for k, q in legs.items():
                        per.setdefault(k, []).append(q)
                    print('WF_TURN', v['id'], cid, seed, {k: q['least_m'] for k, q in legs.items()}, flush=True)
                row['legs'][cid] = {}
                for k, lst in per.items():
                    vals = [q['least_m'] for q in lst]; worst = min(lst, key=lambda q: q['least_m'] if q['least_m'] is not None else -9)
                    row['legs'][cid][k] = dict(worst, least_m=min(vals), seeds=list(seeds), least_by_seed_m=vals, seed_spread_m=[min(vals), max(vals)], status=status(min(vals)))
            row['vehicle'] = vehicle_screen(s, obs, vv); row['spine_core_cut_x_m'] = spine_cut(s, vv)
            row['closure'] = dict(exit_aperture=f'{SLOT_W:.2f} x {SLOT_L:.2f} m slot, centre X {XS:.2f}', clear_area_m2=round(SLOT_W*SLOT_L, 3), ideal_load_kn_80kpa=round(CABIN_KPA*SLOT_W*SLOT_L, 1),
                                  basis='80 kPa x clear area, DIAGNOSTIC; no pressure-shell cutout is approved')
            res[v['id']] = row
            render_variant('turn_'+v['id'], obj, row, out)
            bpy.data.objects.remove(obj)
            (out/'eva3_litter_turn.json').write_text(json.dumps(res, indent=1, default=str)+'\n')
    finally:
        XS, CAR = keep
    return res


# ---------------------------------------------------------------------------------------------------------------------------------

def main(out, skip, fit, turn=None, seeds=SEEDS):
    global FIT
    FIT = fit == 'fit'
    s = load(ROOT)[0]; data = es.load(ROOT); out.mkdir(parents=True, exist_ok=True); load_room(s)
    import casualty_sweep as cs
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend'))); bpy.context.scene.frame_set(1)
    obs = sv.Obstacles(); ins = cs.load_inspect(); records = cs.scene(s, ins, 1.0); rng = np.random.default_rng(17)
    if turn is not None:
        r = run_litter_turn(s, data, records, obs, out, seeds=seeds, only=turn or None)
        (out/'eva3_litter_turn.json').write_text(json.dumps(r, indent=1, default=str)+'\n'); print('WF_TURN done', out, flush=True)
        return
    res = dict(study='EVA-003 follow-up: SP-12 near-axial exit, SP-13 second exit, L1-A guarded ladder bypass, L1-A vs corridor B (owner direction 2026-10-11)',
               status='NONCANON PROTOTYPE STUDY; no hull, port, closure, seal, load path, mass or budget is approved; sampled-pose sweeps, not motion proofs',
               source=dict(owner=['15!A135 RESCUE-004', '15!A136 DIST-004', '43 EVA-063'], margin_m=STUDY_MARGIN, patient_and_equipment='carrier S: suited casualty on the full-length frame (capsule d 0.857 m, 2.093 m, hum003_routes.CARRIERS); K: litter 2.00 x 0.55 x 0.30 m + kit 0.60 x 0.55 x 0.15 m; a rescuer capsule r 0.25 m at each end (HUM-001/002)'))
    res['bypass'] = bypass(s); res['compare'] = compare(s, data, obs)
    if 'sweeps' not in skip:
        res['sp12_exits'] = run_exits(s, data, records, obs, rng, out)
        res['sp13_exit'] = run_sp13(s, data, records, obs, rng, out)
    for v in res.get('sp12_exits', {}).values():
        if isinstance(v, dict):
            v.pop('_viz', None)
    (out/f'eva3_exits_{fit}.json').write_text(json.dumps(res, indent=1, default=str)+'\n')
    print('WF_EXITS done', out, flush=True)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); ap.add_argument('--skip', default=''); ap.add_argument('--fit', default='fit', choices=('fit', 'bare')); ap.add_argument('--seeds', default='17,23,41'); ap.add_argument('--turn', default=None, help='SIM-027 litter turn: comma list of variant ids, or all')
    a = ap.parse_args(argv); main(a.out if a.out.is_absolute() else ROOT/a.out, a.skip.split(','), a.fit, None if a.turn is None else ([] if a.turn == 'all' else a.turn.split(',')), tuple(int(x) for x in a.seeds.split(',')))
