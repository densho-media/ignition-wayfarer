"""Engineering checks of WAYFARER_EVA_Y155 (TODO EVA-001, docs/EVA.md; S&E 44 ASSET-03, RUN-007, RUN-010, SIM-01, QA-02).

  blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/validation/eva_fit.py -- \
      [--report references/p1_eva_fit.json] [--renders renders/p1/eva/fit] [--no-route] [--step 6]

1. Pressure continuity: in sampled frames of every action (the EVA actions and the five shared unsuited ones), each covered body vertex
   must lie behind the outer layer (the nearest outer-layer surface faces away from it) or inside the torso-fixed helmet; the head must
   stay inside the helmet. Reports exposed vertices and how far outside (ASSET-03 "no gaps exposing skin in ANY animated pose").
2. Suited envelope at rest and its largest extent over the EVA actions: width, depth with the PLSS, height and the diameter of the
   circle that holds the cross-section across the body axis; compared with the route bottlenecks (no shrink, RUN-010): the largest PLSS
   depth each admits is reported instead.
3. SP-11 pair fit in the PROTOTYPE airlock fitting (the solid tube of hull_geometry.service_fittings; interior, doors and wall OPEN).
4. Exterior holds (eva_route): the suited bodies posed at the training route's holds in the vehicle (the saved COAST file: the EVA
   configuration differs only in states, 11!5), checked against the vehicle meshes near them, with a render per hold.
Passing checks are not certification (EVA-033, QA-03).
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/components'), str(ROOT/'src/wayfarer/validation')]
import eva_route
import eva_suit as es
import human_system as hs
import hull_geometry
from spec import load

REACH = .12                      # the outer layer must lie above the skin within this distance along the skin normal
SHARED = tuple(es.SHARED_ACTIONS)               # the wearer's unsuited actions: checked and reported, never suited EVA operations
NEAR = 3.0


ASSETS = ROOT/'assets/characters'


def append(key, scene=None):
    path = ASSETS/f'WF_EVA_{key.upper()}.blend'
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c == 'WAYFARER_EVA_Y155']
    c = dst.collections[0]; c.name = f'EVA_{key}'; (scene or bpy.context.scene).collection.children.link(c)
    objs = list(c.all_objects); rig = next(o for o in objs if o.type == 'ARMATURE')
    for o in objs:
        if o.get('eva_role') == 'validation_body':
            o.hide_viewport = False                            # evaluated for the coverage check; never rendered
    return rig, objs


def set_action(rig, name, frame):
    ad = rig.animation_data
    for tr in ad.nla_tracks:
        tr.mute = True
    act = bpy.data.actions[name]; ad.action = act
    if act.slots:
        ad.action_slot = act.slots[0]
    bpy.context.scene.frame_set(frame); bpy.context.view_layer.update()


def world_mesh(o, dg, normals=False):
    e = o.evaluated_get(dg); m = e.to_mesh(); mw = o.matrix_world; R = mw.to_3x3()
    vs = [mw @ v.co for v in m.vertices]; fs = [tuple(p.vertices) for p in m.polygons]
    ns = [(R @ v.normal).normalized() for v in m.vertices] if normals else None
    e.to_mesh_clear(); return (vs, fs, ns) if normals else (vs, fs)


AXES = (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)), Vector((-1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, -1)))


def inside(tree, p, sign):
    """Fallbacks where the skin-normal ray misses in a fold (armpit, crotch): the nearest shell surface faces away from p (by the
    shell's winding `sign`), or a ray along any axis crosses the shell an odd number of times within 0.6 m."""
    loc, nor, _, _ = tree.find_nearest(p)
    if loc is not None and (p-loc).dot(nor)*sign > 0:
        return True
    for d in AXES:
        n = 0; q = p
        while True:
            h = tree.ray_cast(q+d*.0005, d, .6-(q-p).length)
            if h[0] is None:
                break
            n += 1; q = h[0]
        if n % 2 == 1:
            return True
    return False


def coverage(rig, objs, data, step):
    """Exposed covered-body and head vertices per action (see module docstring)."""
    body = next(o for o in objs if o.get('eva_role') == 'validation_body'); outer = next(o for o in objs if o.get('part_id', '').endswith('MMOD_OUTER_SHELL'))
    helmet = next(o for o in objs if o.name.endswith('_Helmet_Shell'))
    hrep = json.loads(rig['eva_helmet']) if rig.get('eva_helmet') else None
    names = {g.index: g.name for g in body.vertex_groups}; unc = {body.vertex_groups[g].index for g in data['layers']['uncovered_groups'] if g in body.vertex_groups}
    head = [any(g.group in unc and g.weight > .5 for g in v.groups) for v in body.data.vertices]
    bones = set(hs.BONES); dom = []
    for v in body.data.vertices:
        g = [x for x in v.groups if names.get(x.group) in bones]; dom.append(names[max(g, key=lambda x: x.weight).group] if g else '')
    c0, R0 = Vector(hrep['centre']), hrep['radius'] - .008
    out = {}; sign = None
    for name in (*es.EVA_ACTIONS, *SHARED):
        act = bpy.data.actions[name]; lo, hi = (int(x) for x in act.frame_range); worst = dict(frames=0, exposed=0, max_out_mm=0.0, head_out=0, bones={})
        for f in range(lo, hi+1, step):
            set_action(rig, name, f); dg = bpy.context.evaluated_depsgraph_get()
            bv, _, bn = world_mesh(body, dg, True); ov, of = world_mesh(outer, dg); tree = BVHTree.FromPolygons(ov, of)
            if sign is None:                                   # the shell's winding, from the rest-like first frame: most skin is inside it
                ds = sorted((bv[i]-tree.find_nearest(bv[i])[0]).dot(tree.find_nearest(bv[i])[1]) for i in range(0, len(bv), 40) if not head[i])
                sign = -1.0 if ds[len(ds)//2] < 0 else 1.0
            c = helmet.matrix_world @ c0; worst['frames'] += 1
            for i in range(0, len(bv), 2):
                p = bv[i]; inside_helmet = (p-c).length < R0
                if head[i]:
                    if not inside_helmet:
                        worst['head_out'] += 1
                    continue
                if inside_helmet:
                    continue
                # covered when the outer layer lies above the skin along the posed skin normal (a ray from the skin hits it within REACH);
                # a ray that misses means the layer collapsed into, or was crossed by, the body there
                hit = tree.ray_cast(p+bn[i]*.0005, bn[i], REACH)
                if hit[0] is None and not inside(tree, p, sign):
                    back = tree.ray_cast(p, -bn[i], REACH)
                    depth = back[3] if back[0] is not None else REACH
                    worst['exposed'] += 1; worst['max_out_mm'] = max(worst['max_out_mm'], round(depth*1000, 1))
                    worst['bones'][dom[i]] = worst['bones'].get(dom[i], 0)+1
        worst['status'] = 'PASS' if worst['exposed'] == 0 and worst['head_out'] == 0 else 'FAIL'
        worst['use'] = 'EVA' if name in es.EVA_ACTIONS else 'NOT_SUITED_EVA'
        worst['bones'] = dict(sorted(worst['bones'].items(), key=lambda x: -x[1])[:4]); out[name] = worst
    return out


TORSO = {'pelvis', 'spine_01', 'spine_02', 'spine_03', 'clavicle_l', 'clavicle_r', 'neck_01', 'head', 'thigh_l', 'thigh_r'}


def dominant_index(o):
    names = {g.index: g.name for g in o.vertex_groups}; bones = set(hs.BONES); out = []
    for v in o.data.vertices:
        g = [x for x in v.groups if names.get(x.group) in bones]; out.append(names[max(g, key=lambda x: x.weight).group] if g else '')
    return out


def suit_points(objs, dg, torso=False):
    """World points of the visible suit; torso=True keeps only what rides the trunk (no arms or lower legs): the passage cross-section."""
    pts = []
    for o in objs:
        if o.type == 'MESH' and o.get('assembly') and o.get('eva_show') != 'cutaway' and o.get('eva_role') != 'validation_body' and not o.name.endswith('_Head'):
            vs, _ = world_mesh(o, dg)
            if torso:
                if o.parent_type == 'BONE':
                    vs = vs if o.parent_bone in TORSO else []
                else:
                    dom = dominant_index(o); vs = [p for p, d in zip(vs, dom) if d in TORSO]
            pts += vs[::3]
    return pts


def envelope(rig, objs):
    """Rest envelope in the body frame (MPFB: x right, -y front, z up) and the largest cross-section circle over the EVA actions."""
    ad = rig.animation_data; ad.action = None
    for pb in rig.pose.bones:
        pb.matrix_basis.identity()
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get(); P = suit_points(objs, dg)
    xs, ys, zs = ([p[i] for p in P] for i in range(3))
    torso = suit_points(objs, dg, torso=True)
    cx = (max(p.x for p in torso)+min(p.x for p in torso))/2; cy = (max(p.y for p in torso)+min(p.y for p in torso))/2
    circ = 2*max(math.hypot(p.x-cx, p.y-cy) for p in torso)
    rest = dict(width_m=round(max(xs)-min(xs), 3), depth_m=round(max(ys)-min(ys), 3), height_m=round(max(zs)-min(zs), 3),
                torso_width_m=round(max(p.x for p in torso)-min(p.x for p in torso), 3), torso_depth_with_plss_m=round(max(p.y for p in torso)-min(p.y for p in torso), 3),
                torso_circle_diameter_m=round(circ, 3))
    plss = next(o for o in objs if o.name.endswith('_PLSS')); pv, _ = world_mesh(plss, dg)
    rest['plss_depth_m'] = round(max(p.y for p in pv)-min(p.y for p in pv), 3)
    rest['torso_depth_without_plss_m'] = round(min(p.y for p in pv)-min(p.y for p in torso), 3)
    # the largest distance of any suit point from the hip centre over the EVA actions: the swept radius of a held body about its hold
    sweep = 0.0
    for name in es.EVA_ACTIONS:
        act = bpy.data.actions[name]; lo, hi = (int(x) for x in act.frame_range)
        for f in range(lo, hi+1, 15):
            set_action(rig, name, f); dg = bpy.context.evaluated_depsgraph_get(); hip = rig.matrix_world @ rig.pose.bones['pelvis'].head
            sweep = max(sweep, max((p-hip).length for p in suit_points(objs, dg)))
    rest['action_sweep_radius_m'] = round(sweep, 3)
    return rest


# EVA-002 access study poses (43 EVA-041/043/044, 44 EVA2-002/003): (action, frame offsets). The suited bodies' convex hulls in these
# poses are what eva_access.py sweeps through the SP-11 door and chamber candidates. Convex hulls are exact for containment in a convex
# chamber or aperture and conservative (never smaller) for separations.
# EVA-003 (44 EVA3-002/003): the extension-latch work (lever shut, mid-throw, open), the opening strap (high, low), the backup body pitch and
# the supported casualty. `joints_frames` keeps the rig's own hand positions at every sampled frame: the study mounts the lever and the
# strap where the rig's hand goes.
POSES = dict(chamber=('eva_buddy_check', (0,)), hatch_pass=('eva_hatch_pass', (0, 30, 60, 90)), casualty=('eva_casualty', (0, 60)),
             rescue=('eva_rescue_hold', (105,)), operate=('eva_airlock', (45, 150)),
             latch=('eva_latch_extension', (45, 75, 105)), strap=('eva_latch_extension', (165, 210)), pitch=('eva_latch_pitch', (30,)), supported=('eva_casualty_supported', (0,)))
JOINTS = dict(pelvis='pelvis', head='head', shoulder_l='upperarm_l', shoulder_r='upperarm_r', hand_l='hand_l', hand_r='hand_r',
              foot_l='foot_l', foot_r='foot_r')


def hull(points):
    """Convex hull of points: vertices (mm-rounded) and outward face planes (unit normal, offset), via bmesh."""
    import bmesh
    bm = bmesh.new()
    for p in points:
        bm.verts.new(p)
    res = bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=False)
    drop = {v for g in (res['geom_interior'], res['geom_unused']) for v in g if isinstance(v, bmesh.types.BMVert) and v.is_valid}
    bmesh.ops.delete(bm, geom=list(drop), context='VERTS')
    bm.normal_update(); bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    c = sum((v.co for v in bm.verts), Vector())/len(bm.verts); planes = []
    for f in bm.faces:
        n = f.normal.normalized(); d = n.dot(f.verts[0].co)
        if n.dot(c) > d:                                       # keep the normals outward
            n, d = -n, -d
        planes.append([round(n.x, 4), round(n.y, 4), round(n.z, 4), round(d, 4)])
    out = dict(verts=[[round(x, 3) for x in v.co] for v in bm.verts], planes=planes); bm.free(); return out


def support_points(pts, q):
    """EVA3-003 rescue support around the secured casualty's suit points (rig frame, body axis z): `frame` a litter of two side rails
    and head/foot cross bars at the suit's mid depth; `mattress` the suit wrapped by a vacuum mattress (each point pushed out from the
    body axis by its thickness, and past the head and feet); `kit` the frame plus a medical/O2 kit in front of the shins. Study geometry
    (data/eva_suit.toml [rescue_support]), never a medical device."""
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]; zs = [p[2] for p in pts]; cx, cy = (max(xs)+min(xs))/2, (max(ys)+min(ys))/2
    r = q['frame_rail_r_m']; hw = (max(xs)-min(xs))/2+q['frame_rail_gap_m']+r; z0 = min(zs)-q['frame_foot_m']; z1 = max(zs)+q['frame_head_m']
    rail = []
    for sx in (-1, 1):
        for z in (z0, z1):
            for k in range(8):
                a = 2*math.pi*k/8; rail.append((cx+sx*hw+r*math.cos(a), cy+r*math.sin(a), z))
    frame = list(pts)+rail
    m = q['mattress_m']; mat = []
    for p in pts:
        dx, dy = p[0]-cx, p[1]-cy; d = math.hypot(dx, dy) or 1.0
        mat.append((p[0]+dx/d*m, p[1]+dy/d*m, p[2]+(m if p[2] > (max(zs)+min(zs))/2 else -m)))
    kx, ky, kz = q["kit"]; zk = min(zs)+.35; yk = min(ys)-ky/2              # strapped on in front of the shins (-y is the front)
    kit = frame+[(cx+sx*kx/2, yk+sy*ky/2, zk+sz*kz/2) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    return dict(frame=frame, mattress=mat, kit=kit)


def pose_hulls(rig, objs):
    """The suit's convex hull in each access pose, the body-only hull (unsuited, same pose as `chamber`) and the joints, in the rig
    frame (MPFB: x right, -y front, z up; rig at the origin)."""
    rig.matrix_world = Matrix.Identity(4); body = next(o for o in objs if o.get('eva_role') == 'validation_body'); out = {}
    for pose, (name, offs) in POSES.items():
        lo = int(bpy.data.actions[name].frame_range[0]); pts = []; joints = {}; jf = []
        for k in offs:
            set_action(rig, name, lo+k); dg = bpy.context.evaluated_depsgraph_get(); pts += [tuple(p) for p in suit_points(objs, dg)]
            jf.append({j: [round(x, 3) for x in rig.matrix_world @ rig.pose.bones[b].head] for j, b in JOINTS.items()})
            joints = joints or jf[0]
        out[pose] = dict(action=name, frames=[lo+k for k in offs], joints=joints, joints_frames=jf, **hull(pts))
        if pose == 'supported':
            for kind, extra in support_points(pts, es.load(ROOT)['rescue_support']).items():
                out[f'supported_{kind}'] = dict(action=name, frames=[lo+k for k in offs], joints=joints, equipment=kind, **hull(extra))
        if pose == 'chamber':
            set_action(rig, name, lo); dg = bpy.context.evaluated_depsgraph_get(); bv, _ = world_mesh(body, dg)
            out['unsuited'] = dict(action=name, frames=[lo], joints=joints, **hull([tuple(p) for p in bv[::2]]))
    return out


def bottlenecks(s, env):
    """Each route bottleneck against the suited torso cross-section (head-first passage, arms along the body). D is a clear diameter."""
    h = s['human_entry']; m = h['mannequin']; ct = s['crew_transfer']
    rows = [('Q33 docking passage / trunk / ring-A tubes (1.6 m)', 2*ct['trunk_clear_radius_m'], 'interior route (shirt-sleeve, EVA-040)'),
            ('ring B spine port, necks and refuge port (0.90 m)', s['human_entry']['refuge_port_clear_m'], 'interior route (shirt-sleeve, EVA-040)'),
            ('ring B drum chamber length (1.10 m crawl, 15!A113)', 1.10, 'crawl with aft down'),
            ('route sweep assumption: suited_envelope_diameter_m', m['suited_envelope_diameter_m'], 'legacy UNSUITED route-control envelope (EVA-041), not a passage'),
            ('sector maintenance strip (0.60 m, SERV-STRIPS 15!A119)', .60, 'shirt-sleeve only')]
    W, Dp, Dn, C = env['torso_width_m'], env['torso_depth_with_plss_m'], env['torso_depth_without_plss_m'], env['torso_circle_diameter_m']
    out = []
    for name, D, kind in rows:
        fits = C <= D-1e-9
        out.append(dict(bottleneck=name, clear_diameter_m=round(D, 3), kind=kind, suit_circle_m=C, margin_m=round(D-C, 3),
                        status='CLEAR' if fits else 'BLOCKED', largest_plss_depth_m=round(max(0.0, min(D, math.sqrt(max(0.0, D*D-W*W)))-Dn), 3) if W < D else 0.0))
    return out


def pair_fit(s, env):
    """Two suits in the PROTOTYPE SP-11 fitting tube (radius from hull_geometry; an assumed 0.05 m wall, labelled)."""
    f = next(x for x in hull_geometry.service_fittings(s) if x['name'] == 'Airlock_EVA'); wall = .05; r = f['radius']-wall; L = f['r1']-f['r0']-2*wall
    C, Hs = env['torso_circle_diameter_m'], env['height_m']
    side = 2*C <= 2*r; tandem = 2*Hs <= L and C <= 2*r
    return dict(fitting='Airlock_EVA (solid PROTOTYPE tube, 14!6 lock size OPEN)', assumed_wall_m=wall, clear_diameter_m=round(2*r, 3), tube_length_m=round(L, 3),
                side_by_side=dict(status='FITS' if side else 'BLOCKED', margin_m=round(2*r-2*C, 3)),
                head_to_feet=dict(status='FITS' if tandem else 'BLOCKED', margin_m=round(L-2*Hs, 3)),
                hatch_clear_diameter_needed_m=round(C+.10, 3), hatch_basis='suit circle + 0.10 m PROTOTYPE margin; hatch size OPEN (EVA-007, EVA-037)',
                status='SIMULATION: interior, doors and door sweep OPEN; a doorway is not two-person capacity (EVA-037)')


def place(rig, origin, along, up):
    """Armature matrix: MPFB -Y faces -along? No: local +Y maps to `along` (so the face, -Y, looks against it), +Z to `up`."""
    y = Vector(along).normalized(); z = Vector(up).normalized(); x = y.cross(z).normalized(); y = z.cross(x)
    M = Matrix((x, y, z)).transposed().to_4x4(); M.translation = Vector(origin); rig.matrix_world = M


def route_holds(s, data, keys, args, sweep_r):
    rt = eva_route.route(s, data, sweep_r); th = math.radians(rt['rail_azimuth_deg']); up = (0.0, math.cos(th), math.sin(th))
    skin = lambda x: eva_route.body_radius(s, x); rail = rt['rail_radius_m']
    P = lambda x, r: (x, r*math.cos(th), r*math.sin(th))
    aft, fwd = rt['holds']['aft_hold']['x'], rt['holds']['forward_hold']['x']; mid = rt['holds']['rail_mid']['x']
    # (label, variant, action, frame, origin, facing along, hold key)
    cases = [('translate_mid', keys[1], 'eva_translate', 40, P(mid, rail), (1, 0, 0), 'rail_mid'),
             ('aft_guide', keys[0], 'eva_guide_point', 90, P(aft, skin(aft)), (1, 0, 0), 'aft_hold'),
             ('aft_tether', keys[1], 'eva_tether_transfer', 115, P(aft+1.3, skin(aft+1.3)), (1, 0, 0), 'aft_hold'),
             ('forward_tool', keys[0], 'eva_tool_inspect', 60, P(fwd, skin(fwd)), (-1, 0, 0), 'forward_hold'),
             ('forward_rotate', keys[1], 'eva_body_rotate', 140, P(fwd-1.3, skin(fwd-1.3)), (-1, 0, 0), 'forward_hold')]
    rigs = {}
    for k in keys:
        rigs[k] = append(k)
    out = []
    for label, k, act, fr, origin, along, hold in cases:
        rig, objs = rigs[k]
        for other, (r2, o2) in rigs.items():
            for o in o2:
                o.hide_render = other != k
        place(rig, origin, along, up); set_action(rig, act, fr); dg = bpy.context.evaluated_depsgraph_get()
        trees = vehicle_bvh(Vector(origin)); hits = {}; least = 9.0
        for o in objs:
            if o.type != 'MESH' or o.get('eva_show') == 'cutaway' or o.get('eva_role') == 'validation_body' or not o.get('assembly'):
                continue
            vs, fs = world_mesh(o, dg); t = BVHTree.FromPolygons(vs, fs)
            for name, vt in trees:
                if t.overlap(vt):
                    hits.setdefault(o['assembly'], set()).add(name)
            for p in vs[::4]:
                for name, vt in trees:
                    hit = vt.find_nearest(p, 1.0)
                    if hit[0] is not None:
                        least = min(least, hit[3])
        status = 'CLEAR' if not hits else 'CONTACT'
        out.append(dict(case=label, variant=k, action=act, frame=fr, hold=hold, x=round(origin[0], 3), status=status, least_clearance_m=round(least, 3),
                        intersections={a: sorted(v) for a, v in hits.items()}, route_status=rt['status'][hold]))
        if args.renders:
            render_hold(rig, origin, up, along, args.renders/f'eva_hold_{label}.png', args.size)
    return out, rt['status']


def vehicle_bvh(centre):
    """BVH trees of the evaluated vehicle meshes within NEAR of `centre` (instances resolved); scale guides, cameras, characters and
    the suits themselves excluded."""
    dg = bpy.context.evaluated_depsgraph_get(); trees = []
    for inst in dg.object_instances:
        o = inst.object
        if o.type != 'MESH' or o.get('kind') in ('scale_reference', 'camera') or o.get('assembly') or o.name.startswith(('Human_', 'CHAR_', 'EVA_')):
            continue
        mw = inst.matrix_world.copy(); corners = [mw @ Vector(c) for c in o.bound_box]
        lo = Vector([min(c[i] for c in corners) for i in range(3)]); hi = Vector([max(c[i] for c in corners) for i in range(3)])
        if Vector([max(lo[i]-centre[i], 0, centre[i]-hi[i]) for i in range(3)]).length > NEAR or not o.data or not len(o.data.polygons):
            continue
        trees.append((o.name, BVHTree.FromPolygons([mw @ v.co for v in o.data.vertices], [tuple(p.vertices) for p in o.data.polygons])))
    return trees


def render_hold(rig, origin, up, along, path, size):
    sc = bpy.context.scene; sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items} else 'CYCLES'
    sc.render.resolution_x, sc.render.resolution_y = size, int(size*.75)
    cam = bpy.data.objects.get('EVA_FIT_CAM') or bpy.data.objects.new('EVA_FIT_CAM', bpy.data.cameras.new('EVA_FIT_CAM'))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    cam.data.lens = 24; o = Vector(origin); u = Vector(up); a = Vector(along); side = a.cross(u)
    eye = o+u*2.6+side*2.4-a*2.2; cam.location = eye; cam.rotation_euler = (o+u*.6-eye).to_track_quat('-Z', 'Y').to_euler(); sc.camera = cam
    sun = bpy.data.objects.get('EVA_FIT_SUN')
    if sun is None:
        sun = bpy.data.objects.new('EVA_FIT_SUN', bpy.data.lights.new('EVA_FIT_SUN', 'SUN')); sc.collection.objects.link(sun); sun.data.energy = 4.0
    sun.rotation_euler = (u+side*.6).to_track_quat('Z', 'Y').to_euler()
    path.parent.mkdir(parents=True, exist_ok=True); sc.render.filepath = str(path); bpy.ops.render.render(write_still=True); print('WF_RENDER', path, flush=True)


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--report', type=Path, default=ROOT/'references/p1_eva_fit.json')
    ap.add_argument('--renders', type=Path, default=ROOT/'renders/p1/eva/fit'); ap.add_argument('--size', type=int, default=800)
    ap.add_argument('--vehicle', type=Path, default=ROOT/'assets/wayfarer/WF_WAYFARER_001.blend'); ap.add_argument('--no-route', action='store_true')
    ap.add_argument('--step', type=int, default=6); ap.add_argument('--route-only', action='store_true')
    ap.add_argument('--assets', type=Path, help='suit asset folder (a study build such as the compact PLSS, ASSET-10); default assets/characters')
    args = ap.parse_args(argv)
    if args.assets:
        global ASSETS
        ASSETS = args.assets.resolve()
    s = load(ROOT)[0]; data = es.load(ROOT); keys = list(data['variant'])
    report = dict(suit=data['suit']['id'], certification=data['suit']['certification'], reach_m=REACH, variants={}); hulls = {}
    if args.route_only and args.report.exists():
        report = json.loads(args.report.read_text()); keys = list(report['variants'])
    for k in ([] if args.route_only else keys):
        bpy.ops.wm.read_factory_settings(use_empty=True); rig, objs = append(k)
        cov = coverage(rig, objs, data, args.step); env = envelope(rig, objs)
        report['variants'][k] = dict(coverage=cov, envelope=env, bottlenecks=bottlenecks(s, env), sp11_pair=pair_fit(s, env))
        hulls[k] = pose_hulls(rig, objs)
        print(f'WF_EVA_FIT {k} coverage', {n: (c['status'], c['exposed'], c['max_out_mm'], c['head_out']) for n, c in cov.items()}, flush=True)
        print(f'WF_EVA_FIT {k} envelope', env, flush=True)
    report['sweep_radius_m'] = max(v['envelope']['action_sweep_radius_m'] for v in report['variants'].values())
    if not args.no_route:
        bpy.ops.wm.open_mainfile(filepath=str(args.vehicle))
        for o in bpy.data.objects:
            if o.name.startswith('Human_') or o.get('kind') == 'scale_reference':
                o.hide_render = True
        report['route'], report['route_status'] = route_holds(s, data, keys, args, report['sweep_radius_m'])
        print('WF_EVA_FIT route', [(r['case'], r['status'], r['least_clearance_m'], r['intersections']) for r in report['route']], flush=True)
    report['coverage_pass'] = all(c['status'] == 'PASS' for v in report['variants'].values() for c in v['coverage'].values())
    report['eva_coverage_pass'] = all(c['status'] == 'PASS' for v in report['variants'].values() for c in v['coverage'].values() if c['use'] == 'EVA')
    report['not_suited_eva_failures'] = sorted({f'{k}:{n}' for k, v in report['variants'].items() for n, c in v['coverage'].items()
                                                if c['use'] != 'EVA' and c['status'] != 'PASS'})
    args.report.write_text(json.dumps(report, indent=1)+'\n')
    if hulls:                                                  # the EVA-002 access study input (eva_access.py)
        (args.report.parent/'p1_eva_envelopes.json').write_text(json.dumps(dict(
            suit=data['suit']['id'], frame='rig frame: x right, -y front, z up, metres', poses={p: list(POSES[p]) for p in POSES},
            status='AS-BUILT PROTOTYPE suit measured in Blender (not certification)', variants=hulls))+'\n')


if __name__ == '__main__':
    main()
