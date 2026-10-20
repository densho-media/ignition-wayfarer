"""TODO D03 / S&E 15!A177 (OWN-RES-B2) + A178: an SP-13 exit that does not use the single 1.6 m trunk (NONCANON PROTOTYPE study).

The 2026-10-13 b2 study (references/EVA3_SP13_L1A_REDLINES.md, "A177") found mutual exclusion a single point of failure in every layout: a
carrier jammed in the shared trunk extension blocks the SP-13 exit by -0.37..-0.46 m, and an SP-12 leak with its closure open depressurizes
SP-13's destination. Its conclusion: "an independent SP-13 exit in all scenarios needs a destination or bypass that does not use the single
1.6 m trunk (OPEN, not studied)". This study screens that bypass.

Function: a second, separately pressurized gallery from SP-13 to the storm refuge (S&E refuge, X 94.15-96.95 m), so SP-13 has two
independent exits (its trunk exit and the gallery) and the refuge has a second door. Fixed: every built stationary mesh of the saved vehicle
(storeroom_survey.Obstacles), the rotating ring/hub annuli, the hull inner wall, the district rooms of the L1-A layout (SP-11 chamber, SP-12,
SP-13, workshop, cell, SP-52 module, EVA3 map) and the refuge envelope. Unknown: closure ratings (80 kPa both ways is an analysis input), gallery
structure, mass, ECLSS of the gallery. Design freedom (PROTOTYPE, this file): gallery azimuth, radius, diameter, the transverse leg out of SP-13
and the inward step to the refuge door.

Stage 1 (this file, --screen): geometric corridor search (no carrier sweep): which (azimuth, radius, D) give a clear duct at the mechanical
clearance along the whole path, inside the hull, outside every district room.

    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/d03_sp13_gallery.py -- --out runs/<stamp>-d03 --screen
"""
from pathlib import Path
import argparse
import json
import math
import sys
import bpy
import numpy as np
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer/studies')]
import eva3_exits as ex                        # puts src/wayfarer, build, validation on sys.path
import storeroom_survey as sv
from spec import load

# District rooms of the L1-A layout (EVA3_DISTRICT_MAP.svg, PROTOTYPE study volumes): x, az (deg), r. The gallery may not enter any but SP-13
# (where its transverse leg starts) and the refuge (where it ends).
ROOMS = {
    'SP11_chamber': ((100.70, 104.85), (0.0, 80.0), (2.50, 6.15)),
    'SP12': ((100.75, 104.85), (5.0, 75.0), (1.25, 4.60)),
    'SP12_branch': ((101.35, 102.35), (15.0, 95.0), (0.80, 1.25)),
    'SP13': ((104.95, 107.10), (5.0, 75.0), (1.25, 4.60)),
    'district_L1A': ((103.60, 106.10), (180.0, 330.0), (1.10, 5.07)),
    'warm_SP52': ((106.30, 107.90), (185.0, 290.0), (1.10, 2.90)),
}
REFUGE_FWD_X = 96.95                          # refuge forward bulkhead (power_storage.obstacles Refuge_Storm_Shelter 94.15-96.95, r 3.09)
REFUGE_R = 3.09
X_TRANSVERSE = 106.05                         # the transverse leg leaves SP-13 mid-room (X 104.95-107.10)
SP13_SIDE_AZ = 75.0                           # SP-13's upper side wall
CHORD_A0 = 65.0                               # PROTOTYPE: azimuth inside SP-13 where the straight transverse leg starts
CHORD_EXTRA = 0.0                             # PROTOTYPE: extra diameter of the transverse leg only (the S entry is its limit)
STEP_X = 99.30                                # the gallery starts its inclined descent to the door radius here (aft of survival pack 1 at X 99.40)
STEP_X1 = 97.30                               # the incline reaches the door radius here
DOOR_R = 2.00                                 # refuge door centre radius (PROTOTYPE): the refuge annulus is r 1.10-2.89 m (he.refuge_station)
D_SET = (1.10, 1.20)                          # the SP-12/13 comparator and the SP-11 lead size; carrier S needed 1.10 at best MARGINAL


def P(x, r, az):
    a = math.radians(az); return (x, r*math.cos(a), r*math.sin(a))


def path(az, rg, D):
    """Gallery centreline: transverse arc out of SP-13 at X_TRANSVERSE from the room's side wall to az at rg; axial run aft at az, rg to STEP_X;
    inward step to DOOR_R; axial to the refuge bulkhead. Returned as (kind, x0, x1, az0, az1, r0, r1) legs."""
    return [('chord', X_TRANSVERSE, X_TRANSVERSE, CHORD_A0, az, rg, rg),
            ('axial', X_TRANSVERSE, STEP_X, az, az, rg, rg),
            ('incline', STEP_X, STEP_X1, az, az, rg, DOOR_R),
            ('axial', STEP_X1, REFUGE_FWD_X, az, az, DOOR_R, DOOR_R)]


def boxes(az, rg, D, clr, n_arc=12, n_ax=1.0):
    """Boxes (storeroom_survey.box) covering the duct of diameter D along the path, each grown by the mechanical clearance. Tagged with their leg."""
    out = []
    for kind, x0, x1, a0, a1, r0, r1 in path(az, rg, D):
        if kind == 'chord':          # straight leg between the two azimuths at rg: boxes along the chord, oriented to its local radial
            p0, p1 = np.array(P(x0, rg, a0)), np.array(P(x0, rg, a1))
            for k in range(n_arc):
                c = p0+(p1-p0)*(k+0.5)/n_arc; rc = math.hypot(c[1], c[2]); ac = math.atan2(c[2], c[1])
                ht = np.linalg.norm(p1-p0)/n_arc/2+0.02
                Dc = D+CHORD_EXTRA; out.append(('chord', sv.box(x0-Dc/2, x0+Dc/2, ac, rc-Dc/2, rc+Dc/2, ht, clr)))
        elif kind == 'axial':
            n = max(1, int(abs(x1-x0)/n_ax))
            for k in range(n):
                xa, xb = x0+(x1-x0)*k/n, x0+(x1-x0)*(k+1)/n
                out.append(('axial', sv.box(min(xa, xb), max(xa, xb), math.radians(a0), r0-D/2, r0+D/2, D/2, clr)))
        else:                        # inclined leg: boxes along it, each spanning its own slice of X and r
            n = 8
            for k in range(n):
                xa, xb = x0+(x1-x0)*k/n, x0+(x1-x0)*(k+1)/n; ra, rb = r0+(r1-r0)*k/n, r0+(r1-r0)*(k+1)/n
                out.append(('incline', sv.box(min(xa, xb)-0.15, max(xa, xb)+0.15, math.radians(a0), min(ra, rb)-D/2, max(ra, rb)+D/2, D/2, clr)))
    return out


def in_room(b, room):
    """Does box b overlap the cylindrical-sector room (x, az, r)? Tested on the box corners and centre plus the room's own sample points."""
    (x0, x1), (a0, a1), (r0, r1) = room; pts = [tuple(v) for v in b['corners']]
    c = tuple(sum(p[i] for p in pts)/8 for i in range(3)); pts.append(c)
    def inside(p):
        az = math.degrees(math.atan2(p[2], p[1])) % 360; r = math.hypot(p[1], p[2])
        return x0 < p[0] < x1 and a0 < az < a1 and r0 < r < r1
    if any(inside(p) for p in pts):
        return True
    # room sample points inside the box (box is convex in its own frame)
    cu, su = math.cos(b['phi']), math.sin(b['phi'])
    for x in np.linspace(x0, x1, 5):
        for az in np.linspace(a0, a1, 7):
            for r in np.linspace(r0, r1, 4):
                y, z = r*math.cos(math.radians(az)), r*math.sin(math.radians(az)); u, t = y*cu+z*su, -y*su+z*cu
                if b['x'][0] < x < b['x'][1] and b['u'][0] < u < b['u'][1] and b['t'][0] < t < b['t'][1]:
                    return True
    return False


def screen_one(s, obs, az, rg, D):
    clr = s['prototype']['mechanical_clearance_m']; hits = {}; rooms = set(); inside = True
    for leg, b in boxes(az, rg, D, clr):
        ign = ('Refuge',) if leg == 'axial' and b['x'][0] < REFUGE_FWD_X+0.3 else ()
        for h in obs.hits(b, ignore=ign):
            hits.setdefault(h, leg)
        for x0, x1, rr0, rr1, name in obs.annuli:          # rotating rings / hubs swept at the saved pose
            if b['x'][1] > x0 and b['x'][0] < x1:
                rr = [math.hypot(v.y, v.z) for v in b['corners']]
                if max(rr) > rr0 and min(rr) < rr1:
                    hits.setdefault(name, leg)
        inside &= sv.inside_hull(s, b)
        for nm, room in ROOMS.items():
            if nm == 'SP13' and leg == 'chord':
                continue
            if in_room(b, room):
                rooms.add(nm)
    length = 2*rg*math.sin(math.radians(abs(CHORD_A0-az))/2)+abs(X_TRANSVERSE-STEP_X)+math.hypot(STEP_X-STEP_X1, rg-DOOR_R)+abs(STEP_X1-REFUGE_FWD_X)
    ok = not hits and not rooms and inside
    return dict(az_deg=az, rg_m=rg, D_m=D, status='CLEAR' if ok else 'BLOCKED', hits=hits, rooms=sorted(rooms), inside_hull=bool(inside),
                length_m=round(length, 2))


def run_screen(out):
    s = load(ROOT)[0]
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend'))); bpy.context.scene.frame_set(1)
    obs = sv.Obstacles(); rows = []
    for D in D_SET:
        for az in range(95, 181, 5):
            for rg in np.arange(2.8, 4.81, 0.2):
                r = screen_one(s, obs, float(az), round(float(rg), 2), D); rows.append(r)
                print('WF_D03', D, az, round(float(rg), 2), r['status'], list(r['hits'])[:3], r['rooms'], flush=True)
    clear = [r for r in rows if r['status'] == 'CLEAR']
    # blocker frequency, to read the space
    freq = {}
    for r in rows:
        for h in r['hits']:
            freq[h] = freq.get(h, 0)+1
        for h in r['rooms']:
            freq['room:'+h] = freq.get('room:'+h, 0)+1
    res = dict(study='D03 stage 1: SP-13 gallery to the refuge, geometric screen (NONCANON PROTOTYPE)', rooms=ROOMS,
               fixed=dict(refuge_fwd_x=REFUGE_FWD_X, transverse_x=X_TRANSVERSE, step_x=STEP_X, door_r=DOOR_R, D_set=D_SET,
                          clearance_m=s['prototype']['mechanical_clearance_m']),
               candidates=len(rows), clear=clear, blockers=dict(sorted(freq.items(), key=lambda kv: -kv[1])[:30]), rows=rows)
    out.mkdir(parents=True, exist_ok=True); (out/'d03_screen.json').write_text(json.dumps(res, indent=1, default=str)+'\n')
    print('WF_D03 done', len(clear), 'clear of', len(rows), flush=True)
    return res


# ---------------------------------------------------------------------------------------------------------------------------------
# Stage 2: turning nodes, free space and carrier sweeps (hum003_routes.sweep_route through the gallery, SP-13 to the refuge annulus)

NODE_V1 = dict(x=(104.95, 107.05), r=1.05)    # vestibule at the gallery's forward end: the transverse leg turns aft here (PROTOTYPE, D 2.10)
ARC_SEG = 8


def node_boxes(az, rg, D, clr):
    a = math.radians(az)
    return [('node_v1', sv.box(NODE_V1['x'][0], NODE_V1['x'][1], a, rg-NODE_V1['r'], rg+NODE_V1['r'], NODE_V1['r'], clr)),
            ]


def screen_nodes(s, obs, az, rg, D):
    clr = s['prototype']['mechanical_clearance_m']; hits = {}; rooms = set(); inside = True
    for leg, b in node_boxes(az, rg, D, clr):
        for h in obs.hits(b):
            hits.setdefault(h, leg)
        inside &= sv.inside_hull(s, b)
        for nm, room in ROOMS.items():
            if nm != 'SP13' and in_room(b, room):
                rooms.add(nm)
    return dict(status='CLEAR' if not hits and not rooms and inside else 'BLOCKED', hits=hits, rooms=sorted(rooms), inside_hull=bool(inside))


def gallery_solids(az, rg, D):
    """Free-space makers (hum003_routes primitives) for the gallery: the transverse arc as chord cylinders, the vestibule, the axial run, the step
    node and the door leg through the refuge's forward wall into its annulus."""
    import hum003_routes as h3
    a0 = CHORD_A0; out = []
    # transverse leg: one straight chord from SP-13 (az a0) to the vestibule axis (az), no curvature for the carrier to follow
    out.append(lambda: h3.prim_cyl(P(X_TRANSVERSE, rg, a0), P(X_TRANSVERSE, rg, az), (D+CHORD_EXTRA)/2))
    out.append(lambda: h3.prim_cyl(P(NODE_V1['x'][0], rg, az), P(NODE_V1['x'][1], rg, az), NODE_V1['r']))
    out.append(lambda: h3.prim_cyl(P(NODE_V1['x'][0]+0.2, rg, az), P(STEP_X-0.3, rg, az), D/2))
    out.append(lambda: h3.prim_cyl(P(STEP_X+0.3, rg, az), P(STEP_X1-0.3, DOOR_R, az), D/2))      # inclined leg, overlapping both runs
    out.append(lambda: h3.prim_cyl(P(STEP_X1+0.3, DOOR_R, az), P(95.6, DOOR_R, az), D/2))
    return out


def gallery_route(az, rg):
    """Waypoints: SP-13 floor area -> arc -> vestibule -> aft along the gallery -> step node -> through the refuge door -> refuge annulus."""
    a0 = CHORD_A0; w = [('R', P(X_TRANSVERSE, 2.6, 35.0)), ('R', P(X_TRANSVERSE, rg, a0))]
    w += [('A', P(X_TRANSVERSE, rg, az))]
    w += [('V', P(105.4, rg, az)), ('G', P(STEP_X, rg, az)), ('I', P(STEP_X1, DOOR_R, az)), ('D', P(96.2, DOOR_R, az)), ('F', P(95.2, DOOR_R, az))]
    return ex.smooth(w, cut=0.6)


def run_sweep(out, cands, seeds, a0=None, extra=None):
    global CHORD_A0, CHORD_EXTRA
    if a0 is not None:
        CHORD_A0 = a0
    if extra is not None:
        CHORD_EXTRA = extra
    import eva3_sp13_l1a as sp13
    import hum003_routes as h3
    ctx = sp13.load_ctx(); cars = sp13.carriers(ctx); res = []
    for az, rg, D in cands:
        nodes = screen_nodes(ctx.s, ctx.obs, az, rg, D); tube = screen_one(ctx.s, ctx.obs, az, rg, D)
        obj, tree = ex.build_free(ctx.s, ctx.data, gallery_solids(az, rg, D), [], 107.4, sp12=False, sp13=True, ref=True, fit=True)
        walls = h3.Walls(ctx.fx, ctx.pts, free=tree); route = gallery_route(az, rg); row = dict(az_deg=az, rg_m=rg, D_m=D, tube=tube['status'], nodes=nodes, carriers={})
        for cid in ('U', 'A', 'S', 'K'):
            per = [h3.sweep_route(walls, cars[cid], route, np.random.default_rng(sd), staff=(cid != 'U')) for sd in seeds]
            body = [r['least_m'] for r in per]; stf = [r['staff_least_m'] for r in per if r['staff_least_m'] is not None]
            k = int(np.argmin(body)); allv = body+stf; least = min(allv)
            row['carriers'][cid] = dict(least_m=round(least, 3), body_least_m=round(min(body), 3), rescuer_least_m=round(min(stf), 3) if stf else None,
                                        status=sp13.status(least), zone=per[k]['zone'], nearest=per[k]['nearest'], by_zone=per[k]['by_zone'],
                                        seed_spread_m=[round(min(allv), 3), round(max(allv), 3)])
            print('WF_D03_SWEEP', az, rg, D, cid, row['carriers'][cid]['least_m'], row['carriers'][cid]['status'], row['carriers'][cid]['zone'],
                  row['carriers'][cid]['nearest'], flush=True)
        bpy.data.objects.remove(obj); res.append(row)
    out.mkdir(parents=True, exist_ok=True); (out/'d03_sweep.json').write_text(json.dumps(dict(seeds=seeds, rows=res), indent=1, default=str)+'\n')
    print('WF_D03_SWEEP done', flush=True)
    return res


# ---------------------------------------------------------------------------------------------------------------------------------
# Review renders: cutaway of the forward district (hull hidden) with the gallery, SP-12/SP-13 and the refuge

SUBS = ('WF_CREW_TRANSFER', 'WF_SERVICE', 'WF_STORAGE', 'WF_POWER_STORAGE', 'WF_HABITAT')


def render(out, az, rg, D, size=1280):
    import hum003_routes as h3
    from mathutils import Vector, Matrix
    s = load(ROOT)[0]
    bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
    for name in SUBS:
        path = ROOT/'assets/wayfarer/subsystems'/f'{name}.blend'
        if not path.exists():
            continue
        with bpy.data.libraries.load(str(path), link=False) as (src, dst):
            dst.objects = list(src.objects)
        for ob in dst.objects:
            if ob is None or ob.type not in ('MESH', 'CURVE'):
                continue
            pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
            lo, hi = min(p.x for p in pts), max(p.x for p in pts); rad = max(max(abs(p.y), abs(p.z)) for p in pts)
            if hi > 93.0 and lo < 108.5 and rad < 6.3 and not any(k in ob.name for k in ('Hull', 'Skin', 'Shell', 'Casing')):
                sc.collection.objects.link(ob)
    def mat(n, c, a=1.0):
        m = bpy.data.materials.new(n); m.diffuse_color = (*c, a); return m
    gal = mat('D03_gallery', (.95, .55, .15)); rooms = mat('D03_rooms', (.35, .55, .95), 0.35)
    global CHORD_EXTRA
    for mk in gallery_solids(az, rg, D):
        o = mk(); o.name = 'D03_Gallery'; o.data.materials.append(gal)
    import eva3_exits as ex_
    for nm in ('SP12', 'SP13'):
        (x0, x1), (a0, a1), (r0, r1) = ROOMS[nm]; o = ex_.sector_obj(x0, x1, a0, a1, r0, r1, name=f'D03_{nm}'); o.data.materials.append(rooms)
    sc.render.engine = 'BLENDER_WORKBENCH'; sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True
    sh.show_xray = False; sc.world = sc.world or bpy.data.worlds.new('D03_World'); sc.world.color = (.055, .075, .10)
    sc.render.resolution_x, sc.render.resolution_y = size, round(size*.75); sc.render.image_settings.file_format = 'PNG'
    cam = bpy.data.objects.new('D03_Camera', bpy.data.cameras.new('D03_Camera')); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.clip_start = 0.05
    views = {'oblique': (P(110.0, 16.0, az+25), P(100.5, 1.5, az), 28), 'side': (P(101.0, 26.0, az+90), P(101.0, 1.0, az), 40)}
    paths = []
    for name, (loc, look, lens) in views.items():
        loc, look = Vector(loc), Vector(look); z = (loc-look).normalized(); up = Vector((1, 0, 0)) if abs(z.x) < .9 else Vector((0, 0, 1))
        x = up.cross(z).normalized(); y = z.cross(x); cam.location = loc; cam.rotation_euler = Matrix((x, y, z)).transposed().to_euler(); cam.data.lens = lens
        p = out/f'd03_gallery_{name}.png'; sc.render.filepath = str(p); bpy.ops.render.render(write_still=True); paths.append(p.name)
    print('WF_D03_RENDER', paths, flush=True)
    return paths


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); ap.add_argument('--screen', action='store_true'); ap.add_argument('--sweep', action='store_true')
    ap.add_argument('--cand', nargs='*', default=['125,3.6,1.2', '125,3.6,1.1']); ap.add_argument('--seeds', type=int, nargs='*', default=[17, 23, 41]); ap.add_argument('--a0', type=float, nargs='*', default=[65.0]); ap.add_argument('--extra', type=float, nargs='*', default=[0.0]); ap.add_argument('--render', type=str, default=None)
    a = ap.parse_args(argv); out = a.out if a.out.is_absolute() else ROOT/a.out
    if a.screen:
        run_screen(out)
    if a.render:
        az_, rg_, D_, ex_ = map(float, a.render.split(',')); CHORD_EXTRA = ex_
        render(out, az_, rg_, D_)
    if a.sweep:
        for a0 in a.a0:
            for ex_ in a.extra:
                run_sweep(out/f'a0_{a0:g}_x{ex_:g}', [tuple(map(float, c.split(','))) for c in a.cand], a.seeds, a0, ex_)
