"""Human-scale fit of the MPFB humans in the real vehicle (docs/CHARACTERS.md "Human scale"; HUM-001 doctrine, 15!A86, Q47).

  blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/validation/human_fit.py -- \
      [--who test_a test_b] [--report references/p1_human_fit.json] [--renders runs/renders/p1/human_system/fit] [--size 640]

Every generic-mannequin station of the crew route (the rod figures human_entry builds into the vehicle as non-canon scale guides) and
the induction pair's staging (the S004A greeting of both, the newcomer on the S004B treatment couch) become source frames: the same feet stations, the same rail and rung grips, the same body axis (so the same
gravity case: floating with the rings stopped, radial-down in a ring, aft-down under thrust). The generated human is posed into each by
the shared solver at its own size and checked against the vehicle's evaluated meshes near it (scale guides, cameras and lights
excluded): body vertices inside a vehicle surface (penetration depth), the least clearance of the head and torso, and how far a hand or
foot falls short of its grip or footing. A cutaway render per station shows the body in place. The rod mannequins and the suited
sweep in `inspect` stay the clearance authority; this check says whether a real body fits the postures they stand for.
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
import characters as ch
import human_entry as he
import human_system as hs
from human import Solver, couch_frame, greeting_frame, local_frame, posed_back_depth
from spec import load

CONTACT_TOL = 0.03          # a hand or foot touching its rail, rung or deck may sit this deep in it (grip and sole compression)
NEAR = 3.0                  # vehicle meshes within this distance of the station are checked

# Station -> (mannequin function, gravity case). The rods carry the contact points.
STATIONS = dict(
    entry_chamber=(lambda s: he.mannequin(s, he.ports(s)[0]), 'float (docked, rings stopped)'),
    trunk=(lambda s: he.trunk_mannequin(s, he.ports(s)[0]), 'float (docked, rings stopped)'),
    vestibule_ring_a=(lambda s: he.vestibule_mannequin(s), 'float (despun drum)'),
    tube_ladder_ring_a=(lambda s: he.spoke_mannequin(s), 'radial-down (ring spinning)'),
    sector_landing=(lambda s: he.landing_mannequin(s), 'radial-down (ring spinning)'),
    refuge=(lambda s: he.refuge_mannequin(s), 'float (docked, rings stopped)'),
    trunk_ladder_thrust=(lambda s: he.trunk_climber(s), 'aft-down (thrust, rings locked)'),
    tube_elbow_thrust=(lambda s: he.elbow_climber(s), 'aft-down (thrust, rings locked)'),
    hatch_step_thrust=(lambda s: he.thrust_stepper(s), 'aft-down (thrust, rings locked)'),
)
RUNGS = {'tube_ladder_ring_a', 'trunk_ladder_thrust', 'tube_elbow_thrust'}
FEET_HELD = {'tube_ladder_ring_a', 'sector_landing', 'trunk_ladder_thrust', 'tube_elbow_thrust', 'hatch_step_thrust'}


def unit(v): return Vector(v).normalized()


def rod_frame(m, H, bones, back=0.0, rungs=False, drop=0.0, lateral=0.0):
    """Source frame from a rod mannequin: body axis from the torso rod, feet at the leg rods' lower ends (ankle height above the sole),
    hands on the rail/grip arm ends (contacts) or the reach arm's end; facing the grips (or the look direction when floating). `back`
    moves the hips away from what the figure faces; with `rungs` the ball of each foot sits on the rung axis (the mannequin's foot point
    is one foot radius, 0.07 m, short of it) instead of the ankle on the foot point, as a climber stands; `drop` lowers the hips toward
    the feet, so the knees bend (CHAR-001's bent-knee stance on the hatch step); `lateral` slides hips and feet along the rungs to the
    body's right (negative: left), hands staying on their grips."""
    rods = {n.rsplit('_', 1)[-1] if 'Leg' not in n else n.rsplit('_', 2)[-2]+n.rsplit('_', 1)[-1]: (n, [Vector(p) for p in pts]) for n, pts, _ in m['rods']}
    torso = next(p for n, p in rods.values() if n.endswith('Torso')); up = (torso[1]-torso[0]).normalized()
    legs = [p for n, p in rods.values() if '_Leg_' in n]; feet = [p[0] for p in legs]
    arms = [(n, p) for n, p in rods.values() if '_Arm_' in n]
    grips = [p[1] for n, p in arms if not n.endswith('Reach')]
    aim = (sum(grips, Vector())/len(grips)-(torso[0]+torso[1])/2) if grips else Vector(m['look'])
    fwd = (aim-up*aim.dot(up)).normalized()
    right = fwd.cross(up); feet = [f+right*lateral for f in feet]
    sole = sum(feet, Vector())/len(feet)-up*.07; hip = sole+up*(bones['hip']-drop)-fwd*back
    side_of = lambda p: 'right' if (p-hip).dot(right) > 0 else 'left'
    hands = {}
    for n, p in arms:
        hands[side_of(p[1]) if len(arms) == 2 and not hands.get(side_of(p[1])) else ('left' if 'right' in hands else 'right')] = (tuple(p[1]), tuple(-fwd))
    j = ch.skeleton(hs.figure(H), ch.STAND, tuple(hip), tuple(up), tuple(fwd), hands=hands)
    if rungs:
        ank = {side_of(f): tuple(f+fwd*(.07-bones['ball'])+up*(bones['ankle']-.07)) for f in feet}
    else:
        ank = {side_of(f): tuple(f-up*.07+up*bones['ankle']) for f in feet}
    j = hs.legs_to(j, H, ank, tuple(fwd), tuple(up))
    reach = sorted(k for k in hands if any(n.endswith('Reach') and tuple(p[1]) == hands[k][0] for n, p in arms))
    return hs.frame_of(j, tuple(sole), ()), dict(up=tuple(up), forward=tuple(fwd), hands={k: v[0] for k, v in hands.items()}, reach_only=reach,
                                                 feet=ank, eye=tuple(m['eye']), look=tuple(m['look']))


def place(rig, solver, frame, up, fwd):
    """Pose the rig in the vehicle frame: the armature object takes the body axes (MPFB faces -Y), the solver works in its local frame."""
    R, loc = local_frame(frame, up, fwd); rig.matrix_world = R
    basis, P, short = solver.solve(loc)
    for b, m in basis.items():
        pb = rig.pose.bones[b]; pb.rotation_mode = 'QUATERNION'; pb.rotation_quaternion = m.to_quaternion()
        if b in ('Root', 'pelvis'):
            pb.location = m.translation
    bpy.context.view_layer.update()
    return {b: R @ m.translation for b, m in P.items()}, short


def vehicle_bvh(centre):
    """BVH trees of the evaluated vehicle meshes near `centre` (instances resolved), without scale guides, cameras or lights."""
    dg = bpy.context.evaluated_depsgraph_get(); trees = []
    for inst in dg.object_instances:
        o = inst.object
        if o.type != 'MESH' or o.get('kind') in ('scale_reference', 'camera') or o.name.startswith(('Human_', 'CHAR_')):
            continue
        mw = inst.matrix_world.copy()
        corners = [mw @ Vector(c) for c in o.bound_box]; lo = Vector([min(c[i] for c in corners) for i in range(3)]); hi = Vector([max(c[i] for c in corners) for i in range(3)])
        d = Vector([max(lo[i]-centre[i], 0, centre[i]-hi[i]) for i in range(3)]).length
        if d > NEAR:
            continue
        me = o.data if o.data else None
        if me is None or not len(me.polygons):
            continue
        vs = [mw @ v.co for v in me.vertices]; fs = [tuple(p.vertices) for p in me.polygons]
        trees.append((o.name, BVHTree.FromPolygons(vs, fs)))
    return trees


def clearance(rig, trees):
    """Intersections of the posed body surface with each nearby vehicle mesh (BVH overlap), by body region, with a depth bound (the
    deepest body vertex of an intersecting face, measured to that surface); and each region's least distance to any vehicle surface."""
    body = next(o for o in rig.children if o.name.endswith('_Body')); dg = bpy.context.evaluated_depsgraph_get()
    e = body.evaluated_get(dg); m = e.to_mesh(); mw = body.matrix_world
    vs = [mw @ v.co for v in m.vertices]; fs = [tuple(p.vertices) for p in m.polygons]; e.to_mesh_clear()
    names = {g.index: g.name for g in body.vertex_groups}; bones = set(rig.data.bones.keys()); lab = []
    for v in body.data.vertices:
        g = [x for x in v.groups if names.get(x.group) in bones]
        bone = names[max(g, key=lambda x: x.weight).group] if g else ''
        lab.append(REGION.get(bone, 'hands' if bone.startswith(('hand', 'thumb', 'index', 'middle', 'ring', 'pinky')) else 'feet' if bone.startswith(('foot', 'ball')) else 'torso'))
    bt = BVHTree.FromPolygons(vs, fs); per, clr = {}, {}
    for name, t in trees:
        for bf, _ in bt.overlap(t):
            for i in fs[bf]:
                hit = t.find_nearest(vs[i], .3); d = hit[3] if hit[0] is not None else 0.0
                per.setdefault(lab[i], {})[name] = max(per.get(lab[i], {}).get(name, 0.0), d)
    for i in range(0, len(vs), 3):
        for name, t in trees:
            hit = t.find_nearest(vs[i], .5)
            if hit[0] is not None:
                clr[lab[i]] = min(clr.get(lab[i], 9.0), hit[3])
    return per, clr


REGION = dict(head='head', neck_01='head', spine_03='torso', spine_02='torso', spine_01='torso', pelvis='torso', clavicle_l='torso',
              clavicle_r='torso', upperarm_l='arms', upperarm_r='arms', lowerarm_l='arms', lowerarm_r='arms', thigh_l='legs', thigh_r='legs',
              calf_l='legs', calf_r='legs')


def render(rig, info, path, size):
    """Cutaway third-person view: a camera 2.6 m out along the body's left side, clipping everything nearer than the body."""
    sc = bpy.context.scene; cam = bpy.data.objects.get('WF_FIT_CAM') or bpy.data.objects.new('WF_FIT_CAM', bpy.data.cameras.new('WF_FIT_CAM'))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    up, fwd = Vector(info['up']), Vector(info['forward']); side = fwd.cross(up).normalized()
    centre = Vector(info['centre']); d = (side*-1.0+fwd*.35+up*.15).normalized()
    y = (up-d*up.dot(d)).normalized(); x = y.cross(d)                       # camera looks along -d, the body's head up in the image
    cam.matrix_world = Matrix.Translation(centre+d*2.6) @ Matrix((x, y, d)).transposed().to_4x4()
    cam.data.lens = 24; cam.data.clip_start = 2.6-.30; cam.data.clip_end = 30
    sc.camera = cam; sc.render.engine = 'BLENDER_WORKBENCH'; sh = sc.display.shading
    sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True; sh.show_backface_culling = False
    sc.render.resolution_x = sc.render.resolution_y = size; sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def proxy_render(s, who, info, rig, args):
    """Render the IND-001 proxy of `who` (assets/characters/<[characters].asset>.blend) at the greeting with the same camera, the MPFB body
    hidden."""
    src = ROOT/'assets/characters'/f"{s['characters']['asset']}.blend"; prefix = f"{who.title()}_"
    with bpy.data.libraries.load(str(src), link=False) as (data_from, dst):
        dst.objects = [n for n in data_from.objects if n.startswith(prefix)]
    coll = bpy.data.collections.new('FIT_PROXY'); bpy.context.scene.collection.children.link(coll)
    for o in dst.objects:
        coll.objects.link(o)
    hidden = [rig, *rig.children]
    for o in hidden:
        o.hide_render = True
    path = args.renders/f'{who}_greeting_{who}_proxy.png'; render(rig, info, path, args.size)
    for o in hidden:
        o.hide_render = False
    for o in list(coll.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(coll)
    return path


def assess(rig, solver, fr, info, grav):
    """Pose, intersect and classify. Hands and feet may sit up to CONTACT_TOL in what they hold or stand on; a forearm or shank in the same
    rail, rung or deck within that depth is part of the same grip or footing. Anything else intersecting is a clash."""
    joints, short = place(rig, solver, fr, info['up'], info['forward'])
    trees = vehicle_bvh(joints['spine_02']); per, clr = clearance(rig, trees)
    held = {n for k in ('hands', 'feet') for n, d in per.get(k, {}).items() if d <= CONTACT_TOL}
    def worst(k):                                               # the region's deepest intersection that is not part of a grip or footing
        return max([d for n, d in per[k].items() if not ((k in ('hands', 'feet') or (k in ('arms', 'legs') and n in held)) and d <= CONTACT_TOL)] or [0.0])
    clashes = {k: round(worst(k), 3) for k in per if worst(k) > 0.005}
    depth = {k: max(v.values()) for k, v in per.items()}; surf = {k: max(v, key=v.get) for k, v in per.items()}
    grip = {f'hand_{x}': round((joints[f'hand_{x[0]}']-Vector(info['hands'][x])).length, 3) for x in info['hands'] if x not in info.get('reach_only', [])}
    foot = {f'foot_{x}': round((joints[f'foot_{x[0]}']-Vector(info['feet'][x])).length, 3) for x in info['feet']}
    return dict(gravity=grav, intersection_depth_m={k: round(v, 3) for k, v in depth.items()}, surfaces=surf, contacts=sorted(held),
                least_clearance_m={k: round(v, 3) for k, v in clr.items()}, hand_to_grip_m=grip, foot_to_footing_m=foot,
                reach_short_m={k: round(v, 3) for k, v in short.items() if v > 1e-3}, verdict='CLASH' if clashes else 'FIT', clashes=clashes), joints


def hatches(s, k):
    """Open (1) or close (0) both entry hatches of the primary port through DOCK_ENTRY_CTRL (in memory; the asset is saved closed). S004A
    happens with both open, as in the induction stills; every other station keeps the saved state."""
    f = he.ports(s)[0]; ctrl = bpy.data.objects['DOCK_ENTRY_CTRL']
    for which in ('outer', 'inner'):
        ctrl[f"{f['name']}_{which}_open"] = float(k)
    ctrl.update_tag(); bpy.context.view_layer.update()


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--who', nargs='*', default=['test_a', 'test_b', 'instructor', 'newcomer'])
    ap.add_argument('--report', type=Path, default=ROOT/'references/p1_human_fit.json'); ap.add_argument('--renders', type=Path, default=ROOT/'runs/renders/p1/human_system/fit')
    ap.add_argument('--size', type=int, default=640); ap.add_argument('--vehicle', type=Path, default=ROOT/'assets/wayfarer/WF_WAYFARER_001.blend')
    ap.add_argument('--restage', action='store_true', help='search the newcomer greeting offset that clears and reaches (CHAR-001)')
    ap.add_argument('--only-frames', nargs='*', help='assess only these frames (fast iteration)')
    args = ap.parse_args(argv); s = load(ROOT)[0]; args.renders.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(args.vehicle))
    for o in bpy.data.objects:                                  # the scale guides stay in the file for comparison, hidden in renders
        if o.name.startswith('Human_') or o.get('kind') == 'scale_reference':
            o.hide_render = True
    report = dict(vehicle=args.vehicle.name, contact_tolerance_m=CONTACT_TOL, characters={})
    for who in args.who:
        src = ROOT/'assets/characters'/f'WF_CHAR_HUMAN_{who.upper()}.blend'
        with bpy.data.libraries.load(str(src), link=False) as (_, dst):
            dst.objects = [n for n in _.objects if n.startswith(f'CHAR_{who.upper()}')]
        coll = bpy.data.collections.new(f'FIT_{who}'); bpy.context.scene.collection.children.link(coll)
        for o in dst.objects:
            coll.objects.link(o)
        rig = bpy.data.objects[f'CHAR_{who.upper()}']; rig.animation_data_create(); rig.animation_data.action = None
        for tr in rig.animation_data.nla_tracks:
            tr.mute = True
        b = rig.data.bones; H = max(v.co.z for o in rig.children if o.type == 'MESH' for v in o.data.vertices)
        bones = dict(hip=b['thigh_l'].head_local.z, ankle=b['foot_l'].head_local.z, ball=abs(b['ball_l'].head_local.y-b['foot_l'].head_local.y))
        P = hs.proportions({x.name: (tuple(x.head_local), tuple(x.tail_local)) for x in b}, H)
        saved = dict(ch.P); ch.P.update(P)
        try:
            solver = Solver(rig, hs.rest(H)); frames = {k: (*rod_frame(fn(s), H, bones), g) for k, (fn, g) in STATIONS.items()}
            backed = {k: [(rod_frame(fn(s), H, bones, .01*i, k in RUNGS), dict(back=.01*i)) for i in range(0, 25)] for k, (fn, g) in STATIONS.items() if k in FEET_HELD}
            # CHAR-001: the hatch step also tries the bent-knee stance, hips lowered and back, hands still on the stiles.
            backed['hatch_step_thrust'] = [(rod_frame(STATIONS['hatch_step_thrust'][0](s), H, bones, b, False, dr, lt), dict(back=b, drop=dr, lateral=lt))
                                           for lt in (0.0, -.04, .04, -.08, .08, -.12, .12) for dr in (0.0, .05, .10, .15, .20)
                                           for b in (0.0, .03, .06, .09, .12)]
            recipe = hs.load(ROOT)['human'].get(who, {}); offset = tuple(recipe.get('greeting_offset_m', (0.0, 0.0, 0.0)))
            for k in ('instructor', 'newcomer'):                # this body in each role; the newcomer's role at this body's re-staging offset
                fr, info = greeting_frame(s, k, H, offset if k == 'newcomer' else (0.0, 0.0, 0.0)); frames[f'greeting_{k}'] = (fr, info, 'float (docked, rings stopped)')
            fr, info = couch_frame(s, H, posed_back_depth(rig, solver, s, H)); frames['couch_newcomer'] = (fr, info, 'radial-down (docked induction pose)')
            if args.restage:                                    # CHAR-001: the smallest newcomer offset that clears the leaf and reaches the rim
                restage = [(da, dp, dq, dh) for da in (-.10, 0.0, .10) for dp in (0.0, .08, .16) for dq in (0.0, .08, .16, .24, .32, .40)
                           for dh in (0.0, .08, .16, .24, .32, .40)]
                restage.sort(key=lambda o: math.dist(o, (0, 0, 0, 0)))
                cands = []
                for o in restage:
                    s2 = dict(s, characters=dict(s['characters'], greeting=dict(s['characters'].get('greeting', {}), hand_offset_m=o[3])))
                    cands.append((o, greeting_frame(s2, 'newcomer', H, o[:3])))
        finally:
            ch.P.clear(); ch.P.update(saved)
        out = {}
        if args.restage:
            hatches(s, 1); best = None; closest = None
            for o, (fr, info) in cands:
                r, _ = assess(rig, solver, fr, info, 'float (docked, rings stopped)')
                score = max(r['clashes'].values() or [0.0])+max(max(r['hand_to_grip_m'].values())-.03, 0.0)
                if closest is None or score < closest[0]:
                    closest = (score, dict(offset_m=list(o), clashes=r['clashes'], surfaces={k: r['surfaces'][k] for k in r['clashes']}, hand_to_grip_m=r['hand_to_grip_m']))
                if score == 0.0:
                    best = dict(offset_m=list(o), least_clearance_m=r['least_clearance_m'], hand_to_grip_m=r['hand_to_grip_m']); break
            print(f'WF_RESTAGE {who} {json.dumps(best or dict(none=True, closest=closest[1]))}', flush=True)
        for name, (fr, info, grav) in frames.items():
            if args.only_frames and name not in args.only_frames:
                continue
            hatches(s, 1 if name.startswith('greeting_') else 0)
            r, joints = assess(rig, solver, fr, info, grav)
            if r['clashes'] and name in backed:                 # how far the body must stand off its grips and footing to clear
                for (fb, ib), how in backed[name]:
                    rb, jb = assess(rig, solver, fb, ib, grav)
                    if not rb['clashes'] and max(rb['hand_to_grip_m'].values() or [0.0]) <= .05:
                        # CHAR-001: the clearing posture is this body's stance here (climber on a ladder, bent knee on the hatch step);
                        # the mannequin's stance stays recorded as stance_of_the_mannequin.
                        r['stance_of_the_mannequin'] = dict(verdict=r['verdict'], clashes=r['clashes'])
                        r['standoff_to_clear_m'] = round(how['back'], 2); r['knee_drop_m'] = round(how.get('drop', 0.0), 2)
                        r['stance'] = ('climber: ball of the foot on the rung, hips %.2f m off the ladder' % how['back'] if name in RUNGS else
                                       'bent knee: hips %.2f m lower, %.2f m back and %+.2f m along the rungs, hands on the stiles'
                                       % (how.get('drop', 0.0), how['back'], how.get('lateral', 0.0)))
                        r['at_standoff'] = {k2: rb[k2] for k2 in ('least_clearance_m', 'hand_to_grip_m', 'reach_short_m', 'contacts')}
                        r['at_standoff']['ball_of_foot_to_mannequin_footing_m'] = {
                            x: round(min((jb[f'ball_{x[0]}']-Vector(f)).length for f in info['feet'].values()), 3) for x in ('right', 'left')}
                        r['verdict'] = 'FIT'; r['clashes'] = {}; fr, info = fb, ib
                        break
                else:
                    r['standoff_to_clear_m'] = None
                    if name == 'hatch_step_thrust':             # what blocks the best of the tried stances (CHAR-001)
                        tried = [(assess(rig, solver, fb, ib, grav)[0], how) for (fb, ib), how in backed[name]]
                        rb, how = min(tried, key=lambda x: max(x[0]['clashes'].values() or [0.0])+max(max(x[0]['hand_to_grip_m'].values() or [0.0])-.05, 0.0))
                        r['closest_stance'] = dict(how, clashes=rb['clashes'], surfaces={k: rb['surfaces'][k] for k in rb['clashes']}, hand_to_grip_m=rb['hand_to_grip_m'])
                place(rig, solver, fr, info['up'], info['forward'])
            info['centre'] = tuple(joints['spine_02']); render(rig, info, args.renders/f'{who}_{name}.png', args.size)
            if name == f'greeting_{who}':                       # the proxy this body replaces, same pose and camera
                r['proxy_render'] = str(proxy_render(s, who, info, rig, args).relative_to(ROOT))
            out[name] = r; print(f'WF_FIT {who} {name} {json.dumps(r)}', flush=True)
        report['characters'][who] = out
        for o in list(coll.objects):
            bpy.data.objects.remove(o, do_unlink=True)
    args.report.write_text(json.dumps(report, indent=1)+'\n')


if __name__ == '__main__':
    main()
