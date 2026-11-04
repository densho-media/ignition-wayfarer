"""The one validation workflow of the Wayfarer EVA system (docs/WAYFARER_EVA_SYSTEM.md "Validation"): checks the built system scene
assets/characters/WF_EVA_SYSTEM.blend (build/eva_scene.py) and writes references/p1_eva_system.json.

  blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/validation/eva_system.py -- [--report <json>]

Every result is either AUTOMATED (measured here on the built meshes, rigs and nozzle sockets, with a pass rule) or REVIEW (an
engineering assumption or estimate that no mesh check can prove: life-support capability, strength, certification). A passing
automated check is a geometric or kinematic fact about the PROTOTYPE model, not proof that the hardware works.

Automated: mesh integrity, scale, transforms, articulation and collisions per state (suit limbs and trunk against the rigid shells, drone
arms against the drone, the pair against each other), drone joint limits, manipulator kinematics (analytic FK and the in-file IK
controls), tool contact (utility gripper on the grapple post, driver bit on the fastener), dock offset and release path, propulsion
authority and single-valve failure (free, proximity, docked, suit reserve), plume impingement per state and on the approach corridor,
centre of mass, helmet clearance over the head-motion envelope, sensor field of view, the docked-arm assistance study, external
dependencies and packing.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build')]
import eva_system as ev
import human_system as hs
from eva_geometry import OWNERS, overlap, overlap_names, plume_envelope, plume_hits, simons_norm, world_mesh_bvh

LIMB = ('upperarm', 'lowerarm', 'hand', 'thumb', 'index', 'middle', 'ring', 'pinky', 'thigh', 'calf', 'foot', 'ball')
RESULTS = []


def check(name, ok, measured, rule):
    RESULTS.append(dict(check=name, kind='AUTOMATED', result='PASS' if ok else 'FAIL', measured=measured, rule=rule)); return ok


def analysis(name, ok, measured, rule):
    """A preliminary engineering estimate that meets its design target: PROVISIONAL, never counted as a PASS."""
    RESULTS.append(dict(check=name, kind='ANALYTICAL', result='PROVISIONAL' if ok else 'FAIL', measured=measured, rule=rule)); return ok


def review(name, statement, basis):
    RESULTS.append(dict(check=name, kind='REVIEW', result='UNVERIFIED', statement=statement, basis=basis))


def meshes(pred):
    return [o for o in bpy.data.objects if o.type == 'MESH' and not o.hide_render and pred(o)]


def in_cutaway(o):
    return any(c.name.endswith('CUTAWAY') for c in o.users_collection)


def dominant(obj):
    names = {g.index: g.name for g in obj.vertex_groups}; bones = set(hs.BONES); out = []
    for v in obj.data.vertices:
        best = max(((g.weight, names[g.group]) for g in v.groups if names.get(g.group) in bones), default=(0.0, ''))
        out.append(best[1])
    return out


def soft_split(outer, odom, dg):
    ev_ = outer.evaluated_get(dg); me = ev_.to_mesh(); mw = ev_.matrix_world
    vs = [mw @ v.co for v in me.vertices]; ps = [list(p.vertices) for p in me.polygons]; cl = []
    for p in ps:
        ds = [odom[i] for i in p]; d = max(set(ds), key=ds.count); cl.append('limb' if d.startswith(LIMB) else 'trunk')
    ev_.to_mesh_clear()
    from mathutils.bvhtree import BVHTree
    return BVHTree.FromPolygons(vs, ps), cl, vs, ps


def split_count(a, soft):
    t, cl = soft[0], soft[1]; out = {'trunk': 0, 'limb': 0}
    if a is None:
        return out
    for i, j in a.overlap(t):
        out[cl[j]] += 1
    return out


def min_distance(objs_a, bvh_b, dg, step=1):
    best = 9.0
    for o in objs_a:
        if o.type != 'MESH':
            continue
        e = o.evaluated_get(dg); me = e.to_mesh(); mw = e.matrix_world
        for v in me.vertices[::step]:
            r = bvh_b.find_nearest(mw @ v.co)
            if r[3] is not None:
                best = min(best, r[3])
        e.to_mesh_clear()
    return round(best, 4)


def bbox(objs, dg, frame=None):
    pts = []; inv = frame.inverted() if frame is not None else None
    for o in objs:
        e = o.evaluated_get(dg); me = e.to_mesh(); pts += [(inv @ (e.matrix_world @ v.co)) if inv else e.matrix_world @ v.co for v in me.vertices]; e.to_mesh_clear()
    mn = [min(p[i] for p in pts) for i in range(3)]; mx = [max(p[i] for p in pts) for i in range(3)]
    return dict(min=[round(v, 3) for v in mn], max=[round(v, 3) for v in mx], size=[round(mx[i]-mn[i], 3) for i in range(3)])


def cone_dirs(z, half_deg, n=8):
    x = z.orthogonal().normalized(); y = z.cross(x)
    return [z]+[(z*math.cos(math.radians(half_deg))+(x*math.cos(a)+y*math.sin(a))*math.sin(math.radians(half_deg))).normalized()
                for a in [2*math.pi*k/n for k in range(n)]]


def integrity(dg):
    """Mesh integrity, transforms, dependencies and packing."""
    bad = {}; neg = []; unscaled = []; tiny = 0; nan = 0; objs = meshes(lambda o: True)+[o for o in bpy.data.objects if o.type == 'MESH' and in_cutaway(o)]
    for o in objs:
        me = o.data
        for v in me.vertices:
            if any(c != c for c in v.co):
                nan += 1
        z = sum(1 for p in me.polygons if p.area < 1e-10)
        if z:
            bad[o.name] = z; tiny += z
        if any(s < 0 for s in o.scale):
            neg.append(o.name)
        if any(abs(s-1.0) > 1e-6 for s in o.scale) and not o.name.startswith(('STUDIO_', 'REF_')):
            unscaled.append(o.name)
    check('mesh_integrity', nan == 0 and tiny == 0, dict(meshes=len(objs), nan_vertices=nan, zero_area_faces=tiny, worst=dict(list(bad.items())[:6])),
          'no NaN vertex, no zero-area face')
    check('transforms', not neg and not unscaled, dict(negative_scale=neg[:6], unapplied_scale=unscaled[:6]), 'every mesh at unit scale (geometry carries the size)')
    libs = [l.filepath for l in bpy.data.libraries]; unpacked = [i.name for i in bpy.data.images if i.source == 'FILE' and not i.packed_file]
    fonts = [f.name for f in bpy.data.fonts if f.filepath and f.filepath != '<builtin>' and not f.packed_file]
    check('dependencies_packed', not libs and not unpacked and not fonts, dict(libraries=libs, unpacked_images=unpacked, unpacked_fonts=fonts),
          'no linked library, every image and font packed: the review file opens anywhere')


def helmet(suit, dg):
    """Swept head (yaw, pitch, roll envelope of data [form]) against the helmet, visor, brow and torso shells, in the rest pose."""
    H = json.loads(suit['eva_helmet']); body = next(o for o in bpy.data.objects if o.get('eva_role') == 'validation_body' and o.parent == suit)
    import eva_suit as es
    unc = set(es.load(ROOT)['layers']['uncovered_groups']); gi = {g.index for g in body.vertex_groups if g.name in unc}
    pts = [body.matrix_world @ v.co for v in body.data.vertices if any(g.group in gi and g.weight > .5 for g in v.groups)]
    hp = suit.matrix_world @ suit.data.bones['head'].head_local; mo = ev.SUIT['head_motion_deg']; sweep = []
    for yaw in (-mo['yaw'], 0.0, mo['yaw']):
        for pitch in (-mo['pitch_down'], 0.0, mo['pitch_up']):
            for roll in (-mo['roll'], 0.0, mo['roll']):
                R = (Matrix.Rotation(math.radians(yaw), 3, 'Z') @ Matrix.Rotation(math.radians(-pitch), 3, 'X') @ Matrix.Rotation(math.radians(roll), 3, 'Y'))
                sweep += [hp+R @ (p-hp) for p in pts[::3]]
    t = world_mesh_bvh([bpy.data.objects[n] for n in H['shells']], dg); worst = 9.0; wrong = 0
    c = Vector(H['centre']); a = H['semi_axes']; n = H['exponent']; zb = c.z+es.load(ROOT)['form']['helmet_base_t']*a[2]
    for p in sweep:
        d = t.find_nearest(p)[3]
        if d is not None:
            worst = min(worst, d)
        # inside the helmet's inner superellipsoid (asymmetric front / back), or below its base ring (inside the yoke)
        f = (abs(p.x-c.x)/a[0])**n+(abs(p.y-c.y)/(a[1] if p.y < c.y else a[3]))**n+(abs(p.z-c.z)/a[2])**n
        wrong += f >= 1.0 and p.z > zb
    return dict(points=len(sweep), min_distance_m=round(worst, 4), points_outside_shell=wrong, semi_axes_m=H['semi_axes'], exponent=H['exponent'])


def ik_test(drone, angles):
    """The in-file IK controls: place ik_<K> at each named pose's flange target (tool axis along its approach), switch IK on, read the
    flange back. The FK pose from the analytic solution is checked the same way."""
    out = {}; pb = drone.pose.bones; ad = drone.animation_data; act = ad.action; ad.action = None
    for tr in ad.nla_tracks:
        tr.mute = True
    for nm, pose in angles.items():
        if not pose:
            continue
        out[nm] = {}
        for K, a in pose.items():
            for p in pb:
                if p.name.startswith(('arm_', 'ik_')):
                    p.rotation_euler = (0, 0, 0); p.location = (0, 0, 0); p.rotation_quaternion = (1, 0, 0, 0)
            drone['ik_A'] = drone['ik_B'] = 0.0
            # analytic FK
            from eva_scene import pose_arms
            pose_arms(drone, {K: a}); bpy.context.view_layer.update()
            fl = pb[f'arm_{K}_tool'].head.copy(); ax = (pb[f'arm_{K}_tool'].matrix.to_3x3() @ Vector((0, 1, 0))).normalized()
            fk_res = (fl-Vector(a['_target'])).length; fk_ang = math.degrees(ax.angle(Vector(a['_approach'])))
            lim = ev.joint_limits_ok(ev.ARMS[K], a)
            # IK controls, from the deployed (ready) pose: folded (stowed) the elbow sits at its 180 deg fold, a singular start the solver
            # cannot leave, so the arm deploys first (as the rig's poses and the docs say)
            pose_arms(drone, {K: dict(angles['ready'][K], wrist_yaw=0.0, roll=0.0)}); y = Vector(a['_approach']).normalized(); x = y.cross(Vector((0, 0, 1)))
            x = x.normalized() if x.length > 1e-4 else Vector((1, 0, 0)); z = x.cross(y)
            M = Matrix((x, y, z)).transposed().to_4x4(); M.translation = Vector(a['_target'])
            pb[f'ik_{K}'].matrix = M; drone[f'ik_{K}'] = 1.0; bpy.context.view_layer.update()
            fl2 = pb[f'arm_{K}_tool'].head.copy(); ax2 = (pb[f'arm_{K}_tool'].matrix.to_3x3() @ Vector((0, 1, 0))).normalized()
            out[nm][K] = dict(target=[round(v, 3) for v in a['_target']], reach_ok=a['reach_ok'], fk_residual_mm=round(fk_res*1000, 2),
                              fk_approach_error_deg=round(fk_ang, 2), joint_deg={k: v['deg'] for k, v in lim.items()},
                              joints_in_range=all(v['ok'] for v in lim.values()), ik_control_residual_mm=round((fl2-Vector(a['_target'])).length*1000, 1),
                              ik_control_approach_error_deg=round(math.degrees(ax2.angle(y)), 1))
            drone[f'ik_{K}'] = 0.0; pb[f'ik_{K}'].matrix_basis = Matrix.Identity(4)
    ad.action = act
    return out


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--blend', type=Path, default=ROOT/'assets/characters/WF_EVA_SYSTEM.blend')
    ap.add_argument('--report', type=Path, default=ROOT/'references/p1_eva_system.json'); args = ap.parse_args(argv)
    bpy.ops.wm.open_mainfile(filepath=str(args.blend))
    sc = bpy.context.scene; states = json.loads(sc['eva_states']); RESULTS.clear()
    suit = bpy.data.objects[bpy.data.objects['RIG_EVA_DRONE']['astronaut_rig']]; drone = bpy.data.objects['RIG_EVA_DRONE']
    hcd = json.loads(suit['eva_hand_controller']); module = json.loads(suit['eva_module']); dinfo = json.loads(drone['eva_drone']); angles = json.loads(drone['arm_pose_angles'])
    outer = bpy.data.objects[suit['eva_outer']]; odom = dominant(outer); sock = bpy.data.objects['SOCKET_DRONE_DOCK']
    report = dict(asset='WF_EVA_SYSTEM', status='PROTOTYPE', wearer=sc['eva_wearer'])
    dg = bpy.context.evaluated_depsgraph_get()
    integrity(dg)
    # ---- objects by role
    is_drone = lambda o: o.name.startswith(('DRN_', 'ARM_', 'TOOL_', 'SENS_Drone', 'THR_Drone', 'NZ_DRN', 'DOCK_Drone', 'N2_Drone', 'N2_INT_Drone',
                                            'MARK_Drone', 'MARK_Arm', 'TETHER_Drone'))
    drone_objs = meshes(lambda o: is_drone(o) and not in_cutaway(o))
    present = lambda o: o.name.startswith(('BURN_', 'LADDER_', 'HULL_', 'RACE_', 'STUDIO_', 'REF_', 'PLUME_'))
    suit_objs = meshes(lambda o: not is_drone(o) and not present(o) and not in_cutaway(o) and o.get('eva_role') != 'validation_body')
    mod_obj = bpy.data.objects[module['module_object']]
    suit_thr = [o for o in suit_objs if o.get('system') == 'suit_thr']; clusters = sorted({o['pod'] for o in suit_thr if 'pod' in o.keys()})
    astro = [o for o in suit_objs if o not in suit_thr and o is not mod_obj]
    arms = {K: [bpy.data.objects[n] for n in v] for K, v in dinfo['arm_parts'].items()}
    tools = [o for o in drone_objs if o.name.startswith('TOOL_')]; arms_tools = arms['A']+arms['B']+tools
    sensors = [o for o in drone_objs if o.name.startswith('SENS_Drone')]
    shell_d = [o for o in drone_objs if o.name.startswith(('DRN_Core', 'DRN_Shell', 'N2_Drone_COPV', 'DRN_Bay_Cover', 'THR_Drone'))]
    hull = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('HULL_')]          # visible only in the maintenance state
    suit_n = [bpy.data.objects[n] for n in module['nozzles']]; drone_n = [bpy.data.objects[n] for n in dinfo['nozzles']]
    # ---- scale
    sc.frame_set(states[0]['frame']); dg = bpy.context.evaluated_depsgraph_get()
    body = next(o for o in bpy.data.objects if o.get('eva_role') == 'validation_body' and o.parent == suit)
    stature = max((body.matrix_world @ v.co).z for v in body.data.vertices)
    dims = dict(astronaut_docked=bbox(suit_objs+drone_objs, dg), astronaut=bbox(suit_objs, dg), module=bbox([mod_obj], dg),
                drone_local=bbox(drone_objs, dg, drone.matrix_world), stature_m=round(stature, 3))
    dims['drone_depth_beyond_module_m'] = round(bbox(drone_objs, dg)['max'][1]-dims['module']['max'][1], 3)
    report['dimensions'] = dims
    ds = dims['drone_local']['size']
    check('scale', 1.55 < stature < 2.0 and .40 < ds[0] < .60 and .45 < ds[1] < .70 and .15 < ds[2] < .30,
          dict(stature_m=dims['stature_m'], drone_size_m=ds, docked_depth_beyond_module_m=dims['drone_depth_beyond_module_m']),
          'metres, real scale: a 1.55-2.0 m wearer; drone 0.40-0.60 x 0.45-0.70 x 0.15-0.30 m (stowed)')
    # ---- dock offset and release path
    off = (drone.matrix_world.translation-sock.matrix_world.translation).length
    rot = math.degrees((drone.matrix_world.to_quaternion().rotation_difference(sock.matrix_world.to_quaternion())).angle)
    check('dock_offset', off < 1e-4 and rot < .01, dict(offset_mm=round(off*1000, 3), angle_deg=round(rot, 4)), 'docked: the drone frame is the suit dock socket')
    # the envelope runs out to where a nozzle's on-axis Simons pressure falls to the sensitive limit (not a fixed 1.2 m): 4 N about 1.6 m,
    # 8 N about 2.3 m
    env_len = lambda F: max(ev.P['plume_check_m'], math.sqrt(F/(simons_norm(ev.P['plume_theta_lim_deg'])*ev.P['plume_limits_pa']['sensitive'])))
    report['plume_envelope_length_m'] = dict(drone=round(env_len(ev.THRUST_N), 2), suit=round(env_len(ev.THRUST['suit_n']), 2))
    # ---- per-state articulation, collisions, plumes, sensors
    st_out = {}
    for s in states:
        key = s['key']; f = s['frame']+3; sc.frame_set(f); dg = bpy.context.evaluated_depsgraph_get(); r = dict(label=s['label'])
        soft = soft_split(outer, odom, dg)
        r['torso_shell_vs_outer'] = split_count(world_mesh_bvh([o for o in suit_objs if o.name.endswith(('Torso_Shell',))], dg), soft)
        r['helmet_vs_outer'] = split_count(world_mesh_bvh([o for o in suit_objs if o.name.endswith(('Helmet_Shell', 'Helmet_Brow', 'Visor'))], dg), soft)
        r['module_vs_outer'] = split_count(world_mesh_bvh([mod_obj], dg), soft)
        A_ = world_mesh_bvh(arms['A'], dg); B_ = world_mesh_bvh(arms['B'], dg); Sd = world_mesh_bvh(shell_d, dg); Tl = world_mesh_bvh(tools, dg)
        r['arm_A_vs_drone'] = overlap_names(A_, Sd); r['arm_B_vs_drone'] = overlap_names(B_, Sd); r['arm_A_vs_arm_B'] = overlap(A_, B_)
        r['tools_vs_drone'] = overlap_names(Tl, Sd)
        As = world_mesh_bvh(astro, dg); Mb = world_mesh_bvh([mod_obj]+suit_thr, dg); Dw = world_mesh_bvh(drone_objs, dg)
        r['drone_vs_astronaut'] = overlap_names(Dw, As); r['drone_vs_module'] = overlap_names(Dw, Mb)
        r['arms_tools_vs_astronaut'] = overlap_names(world_mesh_bvh(arms_tools, dg), world_mesh_bvh(astro+[mod_obj]+suit_thr, dg))
        blockers = {'ASTRONAUT': As, 'MODULE': world_mesh_bvh([mod_obj], dg)}
        for p in clusters:
            blockers[p] = world_mesh_bvh([o for o in suit_thr if o.get('pod') == p], dg)
        blockers['DRONE'] = Dw
        armed = s.get('thrusters', True); r['thrusters'] = 'armed' if armed else 'safed'
        reserve = armed and s.get('suit_reserve', True); r['suit_reserve'] = 'armed' if reserve else 'isolated'
        r['suit_plume_hits'] = plume_hits(suit_n, blockers, dg, ev.P['plume_half_angle_deg'], ev.P['plume_check_m']) if reserve else {}
        if s['place'] != 'hull' and armed:
            live = [n for n in drone_n if not (s['props']['prop_mode'] == 1 and n.get('inhibit_docked'))]      # prop_mode 1: docked or near a suit
            bl = {k: v for k, v in blockers.items() if k != 'DRONE'}; bl['DRONE_ARMS_TOOLS'] = world_mesh_bvh(arms_tools, dg)
            bl['DRONE_SENSORS'] = world_mesh_bvh(sensors, dg); bl['DRONE_BAY_COVERS'] = world_mesh_bvh(meshes(lambda o: o.name.startswith('DRN_Bay_Cover')), dg)
            r['drone_plume_hits'] = plume_hits(live, bl, dg, ev.P['plume_half_angle_deg'], ev.P['plume_check_m']); r['drone_live_nozzles'] = len(live)
            r['drone_envelope'] = plume_envelope(live, bl, dg, ev.THRUST_N, ev.P['plume_half_angle_deg'], ev.P['plume_fringe_half_angle_deg'],
                                                 env_len(ev.THRUST_N), ev.P['plume_theta_lim_deg'])
        if reserve:
            r['suit_envelope'] = plume_envelope(suit_n, blockers, dg, ev.THRUST['suit_n'], ev.P['plume_half_angle_deg'], ev.P['plume_fringe_half_angle_deg'],
                                                env_len(ev.THRUST['suit_n']), ev.P['plume_theta_lim_deg'])
        if s['place'] == 'hull':
            r['drone_vs_hull'] = overlap_names(Dw, world_mesh_bvh(hull, dg))
        pbz = drone.pose.bones; viol = []
        for K, A in ev.ARMS.items():
            a = dict(yaw=pbz[f'arm_{K}_yaw'].rotation_euler.y, pitch=pbz[f'arm_{K}_upper'].rotation_euler.x, elbow=pbz[f'arm_{K}_fore'].rotation_euler.x,
                     wrist=pbz[f'arm_{K}_wrist'].rotation_euler.x, wrist_yaw=pbz[f'arm_{K}_wyaw'].rotation_euler.z if f'arm_{K}_wyaw' in pbz else 0.0)
            viol += [f'{K}.{j} {v["deg"]}' for j, v in ev.joint_limits_ok(A, a).items() if not v['ok']]
        r['drone_joint_limit_violations'] = viol
        if s['place'] in ('free', 'hull'):
            fwd = drone.matrix_world.to_3x3() @ Vector((0, 1, 0)); bl = {'DRONE_BODY': world_mesh_bvh([o for o in drone_objs if o not in arms_tools and o not in sensors], dg),
                                                                         'ARMS_TOOLS': world_mesh_bvh(arms_tools, dg)}
            fov = {}
            for nm in ('SENS_Drone_Stereo_L', 'SENS_Drone_Stereo_R', 'SENS_Drone_Lidar', 'SENS_Drone_Inspection_Cam', 'SENS_Drone_Thermal_IR'):
                o = bpy.data.objects[nm]; p = o.matrix_world @ (sum((Vector(c) for c in o.bound_box), Vector())/8); n = 0; first = []
                for d in cone_dirs(fwd.normalized(), 30.0):
                    for bn, t in bl.items():
                        h = t.ray_cast(p+d*.012, d, 1.0)
                        if h[0] is not None:
                            n += 1; first.append(f'{bn}:{OWNERS[id(t)][h[2]]}'); break
                fov[nm] = dict(rays=9, blocked=n, first=first[:2])
            r['sensor_fov'] = fov
        # fold-out hand controller: grip under the palm where the pose holds it, no contact with the suit, the drone or the release handle
        hcm = [o for o in astro if '_HCM_Link' in o.name]; rest_ = [o for o in astro if '_HCM_' not in o.name and not o.name.endswith('_Manual_Release')]
        l1, l2 = (bpy.data.objects[n] for n in hcd['links'])
        grip = l2.matrix_world @ (Vector(hcd['grip_axis_link'])*ev.SUIT['hand_controller']['grip_rise_m']); pbs = suit.pose.bones
        palm = suit.matrix_world @ ((pbs['hand_l'].head+pbs['middle_01_l'].head)/2); Hc = world_mesh_bvh(hcm, dg)
        r['hand_controller'] = dict(deployed=s['suit_pose'] in hcd['deploy_poses'], palm_to_grip_mm=round((palm-grip).length*1000, 1),
                                    yaw_deg=round(math.degrees(l1.rotation_euler.z), 2), slide_m=round(l2.location.x, 4),
                                    vs_suit=overlap_names(Hc, world_mesh_bvh(rest_, dg)), vs_drone=overlap_names(Hc, Dw),
                                    to_release_mm=round(min_distance(hcm, world_mesh_bvh([bpy.data.objects[hcd['release']]], dg), dg)*1000, 1),
                                    grip_gap_mm=round(min_distance([l2], world_mesh_bvh([outer], dg), dg)*1000, 1))
        st_out[key] = r; print('checked', key, flush=True)
    report['states'] = st_out
    plume_free = all(not v['suit_plume_hits'] and not v.get('drone_plume_hits') for v in st_out.values())
    check('plumes_all_states', plume_free, {k: dict(thrusters=v['thrusters'], suit_reserve=v['suit_reserve'], suit=len(v['suit_plume_hits']), drone=len(v.get('drone_plume_hits', {}))) for k, v in st_out.items()},
          f'in every state with propulsion armed, no live plume (axis + {ev.P["plume_half_angle_deg"]:.0f} deg cone to {ev.P["plume_check_m"]} m) hits the '
          'astronaut, module, other clusters, arms, sensors or covers')
    check('drone_arms_vs_drone', all(not v['arm_A_vs_drone'] and not v['arm_B_vs_drone'] and not v['arm_A_vs_arm_B'] for v in st_out.values()),
          {k: dict(A=sum(v['arm_A_vs_drone'].values()), B=sum(v['arm_B_vs_drone'].values()), AB=v['arm_A_vs_arm_B']) for k, v in st_out.items()},
          'no arm touches the drone body, covers, vessels or clusters, or the other arm, in any state')
    check('tools_vs_drone', all(not v['tools_vs_drone'] for v in st_out.values()), {k: v['tools_vs_drone'] for k, v in st_out.items() if v['tools_vs_drone']},
          'stowed and carried tools clear of the drone body')
    check('drone_joint_limits_states', all(not v['drone_joint_limit_violations'] for v in st_out.values()),
          {k: v['drone_joint_limit_violations'] for k, v in st_out.items() if v['drone_joint_limit_violations']}, 'every keyed arm pose inside data/eva_drone.toml joint ranges')
    pair = {k: dict(astronaut=v['drone_vs_astronaut'], module=v['drone_vs_module']) for k, v in st_out.items()}
    report['pair_contacts'] = pair
    # docked, the drone may touch the suit only through its mating hardware: bolts in the wall sockets (the bore is not modelled at
    # REP_PROXY: a bolt reads as overlapping its socket and the channel wall), the keel under the capture tongue, the load pads
    mating = lambda nm: nm.startswith(('DOCK_Drone_Bolt_', 'DOCK_Drone_Keel x DOCK_', 'DOCK_Drone_Load_Pad_'))
    stray = {k: {n: c for n, c in {**v['astronaut'], **v['module']}.items() if not mating(n)} for k, v in pair.items()}
    check('dock_contacts_mating_only', all(not v for v in stray.values()), {k: v for k, v in stray.items() if v} or 'none',
          'the drone touches the astronaut and module only through the dock hardware (bolts, keel, load pads), in every state')
    limb = {k: dict(torso=v['torso_shell_vs_outer']['limb'], module=v['module_vs_outer']['limb'], trunk_torso=v['torso_shell_vs_outer']['trunk'],
                    helmet=v['helmet_vs_outer']['trunk']+v['helmet_vs_outer']['limb']) for k, v in st_out.items()}
    hc_ = {k: v['hand_controller'] for k, v in st_out.items()}; lim_ = hcd['stops']
    ylo, yhi = sorted(lim_['yaw_deg'])
    seat_mm = ev.SUIT['hand_controller']['seat_max_m']*1000
    gap_mm = ev.SUIT['hand_controller']['grip_gap_max_m']*1000
    hc_ok = all((not v['deployed'] or (v['palm_to_grip_mm'] <= seat_mm and v['grip_gap_mm'] <= gap_mm)) and not v['vs_suit'] and not v['vs_drone'] and v['to_release_mm'] >= 20.0
                and ylo-.01 <= v['yaw_deg'] <= yhi+.01 and lim_['slide_m'][0]-1e-4 <= v['slide_m'] <= lim_['slide_m'][1]+1e-4 for v in hc_.values())
    report['hand_controller'] = dict(hcd, states=hc_)
    check('hand_controller', hc_ok, {k: (v['deployed'], v['palm_to_grip_mm'], v['grip_gap_mm'], sum(v['vs_suit'].values()), sum(v['vs_drone'].values()), v['to_release_mm'])
                                     for k, v in hc_.items()},
          f'fold-out controller: deployed in flight / drone-deployed / chase with the grip axis <= {seat_mm:.0f} mm from the left palm centre and the glove <= {gap_mm:.0f} mm from the grip (hand at the grip, no contact); stowed otherwise; '
          'never touching the suit or the drone, >= 20 mm from the manual release; yaw and telescope inside their stops in every state')
    check('suit_articulation', all(v['torso'] == 0 and v['module'] == 0 and v['trunk_torso'] == 0 and v['helmet'] == 0 for v in limb.values()), limb,
          'the soft outer layer (limbs and trunk) never passes through the rigid torso shell, module or helmet in any state')
    # ---- sensors (detached, arms folded must be clear)
    fov = st_out['detached']['sensor_fov']
    check('sensor_view_arms_folded', all(v['blocked'] == 0 for v in fov.values()), {k: v['blocked'] for k, v in fov.items()},
          'arms folded: no forward sensor ray (30 deg cone, 1 m) meets the drone itself')
    # ---- release path (docked -> 0.6 m along the dock axis, everything retracted)
    s0 = states[0]; sc.frame_set(s0['frame']+3); bpy.context.view_layer.update(); dock_w = sock.matrix_world.copy()
    ad = drone.animation_data; act = ad.action; ad.action = None
    for tr in ad.nla_tracks:
        tr.mute = True
    for k in ('docked', 'capture', 'latch', 'elec', 'n2', 'prop_mode'):
        drone[k] = 0.0
    from eva_scene import pose_arms
    drone.update_tag(); suit.update_tag(); sc.frame_set(sc.frame_current)   # re-run the bolt / tongue / probe drivers on the new values
    pose_arms(drone, json.loads(drone['arm_pose_angles']).get('stowed', {})); path = []
    for d in (.005, .01, .02, .05, .1, .2, .3, .45, .6):
        drone.matrix_world = Matrix.Translation((0, d, 0)) @ dock_w; bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
        A_ = world_mesh_bvh(astro+[mod_obj]+suit_thr, dg); hit = overlap_names(world_mesh_bvh(drone_objs, dg), A_); path.append(dict(offset_m=d, overlaps=sum(hit.values()), pairs=dict(list(hit.items())[:6])))
    check('release_path', all(p['overlaps'] == 0 for p in path), path, 'the drone backs straight off the channel from 5 mm to 0.6 m without touching the suit')
    # ---- plume corridor on approach: the drone held on the dock axis at 0.5 .. 0.03 m in its near-suit mode (ventral nozzles valved off)
    corridor = {}; near = [n for n in drone_n if not n.get('inhibit_docked')]
    for d in (.5, .26, .12, .05, .03):
        drone.matrix_world = Matrix.Translation((0, d, 0)) @ dock_w; bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
        bl = {'ASTRONAUT': world_mesh_bvh(astro, dg), 'MODULE': world_mesh_bvh([mod_obj]+suit_thr, dg)}
        corridor[f'{d:.2f}'] = plume_hits(near, bl, dg, ev.P['plume_fringe_half_angle_deg'], ev.P['plume_check_m'])
    check('approach_corridor_plumes', all(not v for v in corridor.values()), {k: v for k, v in corridor.items() if v} or 'none',
          f'near-suit mode ({len(near)} live nozzles): no {ev.P["plume_fringe_half_angle_deg"]:.0f} deg plume fringe reaches the astronaut or module '
          'with the drone on the dock axis 0.5-0.03 m out')
    report['approach_corridor_plumes'] = corridor
    # ---- 3D plume envelope (all states, the approach corridor and the drone's own arm motion): Simons-model pressure on every first hit
    #      inside the 30 deg fringe; core hits fail, fringe hits are held to the [gas] plume_limits_pa (sensitive: visor, optics, sensors)
    sens_ = lambda h: h['blocker'] in ('DRONE_SENSORS',) or any(t in h['object'] for t in ('Visor', 'SENS_', 'Helmet', 'Lens', 'Camera'))
    env_corr = {}                      # the whole approach from 2 m: the free set beyond proximity_m, the near-suit set inside it
    for d in (2.0, 1.6, 1.2, .9, .7, .5, .26, .12, .05, .03):
        drone.matrix_world = Matrix.Translation((0, d, 0)) @ dock_w; bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
        bl = {'ASTRONAUT': world_mesh_bvh(astro, dg), 'MODULE': world_mesh_bvh([mod_obj]+suit_thr, dg)}
        env_corr[f'{d:.2f}'] = plume_envelope(near if d <= ev.PROP['proximity_m'] else drone_n, bl, dg, ev.THRUST_N, ev.P['plume_half_angle_deg'],
                                              ev.P['plume_fringe_half_angle_deg'], env_len(ev.THRUST_N), ev.P['plume_theta_lim_deg'])
    drone.matrix_world = dock_w; sweep_env = {}; fr_ = next(s for s in states if s['key'] == 'arms')
    ad.action = act; sc.frame_set(fr_['frame']+3); free_w = drone.matrix_world.copy(); ad.action = None; drone.matrix_world = free_w
    A0 = angles.get('stowed', {}); bpy.context.view_layer.update(); sweep_state = {}
    for nm_ in [k for k in angles if k != 'stowed']:
        st_ = next((s_ for s_ in states if s_['arm_pose'] == nm_), None); sweep_state[nm_] = dict(state=st_ and st_['key'], thrusters='armed' if st_ and st_.get('thrusters', True) else 'safed')
        if sweep_state[nm_]['thrusters'] != 'armed':
            continue                   # this pose is only used anchored or docked with the drone thrusters safed: no plume during the motion
        for fr in (.25, .5, .75):
            mix = {K: {j: A0.get(K, {}).get(j, 0.0)*(1-fr)+v*fr for j, v in angles[nm_].get(K, {}).items() if isinstance(v, (int, float))} for K in ev.ARMS}
            pose_arms(drone, mix); bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
            bl = {'DRONE_ARMS_TOOLS': world_mesh_bvh(arms_tools, dg), 'DRONE_SENSORS': world_mesh_bvh(sensors, dg),
                  'DRONE_BAY_COVERS': world_mesh_bvh(meshes(lambda o: o.name.startswith('DRN_Bay_Cover')), dg)}
            sweep_env[f'stowed>{nm_}@{fr}'] = plume_envelope(drone_n, bl, dg, ev.THRUST_N, ev.P['plume_half_angle_deg'], ev.P['plume_fringe_half_angle_deg'],
                                                              env_len(ev.THRUST_N), ev.P['plume_theta_lim_deg'])
    pose_arms(drone, A0); ad.action = act
    lim = ev.P['plume_limits_pa']; worst = dict(core=0, sensitive_pa=0.0, hardware_pa=0.0); bad = []
    def judge(where, env):
        for nz, hs_ in env.items():
            for h in hs_:
                worst['core'] += h['core']; k_ = 'sensitive_pa' if sens_(h) else 'hardware_pa'; worst[k_] = max(worst[k_], h['pressure_pa'])
                if h['core'] or h['pressure_pa'] > (lim['sensitive'] if sens_(h) else lim['hardware']):
                    bad.append(dict(where=where, nozzle=nz, **h))
    for k, v in st_out.items():
        judge(f'state:{k}:suit', v.get('suit_envelope', {})); judge(f'state:{k}:drone', v.get('drone_envelope', {}))
    for k, v in env_corr.items():
        judge(f'approach:{k}', v)
    for k, v in sweep_env.items():
        judge(f'arm_sweep:{k}', v)
    report['plume_envelope'] = dict(model='Simons far field, cold N2 n = 5, theta_lim %.0f deg; axis + 5 rings to %.0f deg x 16 azimuths, %.1f m'
                                    % (ev.P['plume_theta_lim_deg'], ev.P['plume_fringe_half_angle_deg'], env_len(ev.THRUST['suit_n'])),
                                    limits_pa=lim, worst=worst, violations=bad, approach=env_corr,
                                    arm_sweeps={k: {n_: len(h_) for n_, h_ in v.items()} for k, v in sweep_env.items()}, arm_sweep_states=sweep_state,
                                    limits='no reflection, plume-plume interaction, rarefied transition or contamination transport; pressures are '
                                           'order-of-magnitude, not qualification')
    check('plume_envelope', not bad, dict(worst=worst, violations=len(bad), first=bad[:6]),
          f'3D envelope (axis + rings to {ev.P["plume_fringe_half_angle_deg"]:.0f} deg, out to the 1 Pa on-axis range) in every armed state, on the '
          f'approach from 2 m and through the arm motions made with the thrusters armed: no core hit, sensitive surfaces <= {lim["sensitive"]} Pa, everything else <= {lim["hardware"]} Pa (Simons estimate)')
    # ---- propulsion authority and CoM (pure maths on the built nozzle sockets)
    com = dinfo['com_local']
    dn_local = [(n.name, tuple(n['local_pos']), tuple(n['local_dir']), n.name, bool(n['inhibit_docked'])) for n in drone_n]
    suit_noz = [(n.name, tuple(n.matrix_world.translation), tuple(n.matrix_world.col[2].xyz.normalized())) for n in suit_n]
    dn_docked = [(n.name, tuple(dock_w @ Vector(n['local_pos'])), tuple((dock_w.to_3x3() @ Vector(n['local_dir'])).normalized()), bool(n['inhibit_docked']))
                 for n in drone_n]
    body_com = tuple(sum((body.matrix_world @ v.co for v in body.data.vertices), Vector())/len(body.data.vertices))
    live_prox = [(tuple(n['local_pos']), tuple(n['local_dir'])) for n in near]
    study = ev.study(drone_local=dict(nozzles=dn_local, com=com), docked=dict(suit_nozzles=suit_noz, drone_nozzles=dn_docked,
                     drone_centre=tuple(dock_w.translation), drone_com_world=tuple(dock_w @ Vector(com))), pc=tuple(module['pc']), body_com=body_com,
                     proximity=live_prox)
    report['propulsion'] = study
    ok6 = lambda a: ev.axes_ok(a) == 12
    check('authority_free', ok6(study['authority_drone_free']), {k: v['max'] for k, v in study['authority_drone_free'].items()}, 'drone alone: all 12 pure axes')
    check('authority_docked', ok6(study['authority_docked']), {k: v['max'] for k, v in study['authority_docked'].items()}, 'docked (the drone\'s near-suit set flies the pair, suit reserve isolated): all 12')
    check('authority_suit_reserve', ok6(study['authority_suit_reserve']), {k: v['max'] for k, v in study['authority_suit_reserve'].items()}, 'suit reserve alone: all 12')
    check('authority_proximity', ok6(study['authority_drone_proximity']),
          dict(live=len(live_prox), axes={k: v['max'] for k, v in study['authority_drone_proximity'].items()}),
          f'within {ev.PROP["proximity_m"]} m of a suit (near-suit mode, the plume-clear set above): all 12 pure axes, including +Z (back away) '
          'for retreat and abort')
    nf = study['near_suit_faults']
    check('near_suit_fault_stages', all(nf['stage_ok_all_single_failures'].values()) and nf['energy_j']['ok'],
          dict(stages=nf['stage_ok_all_single_failures'], failing=nf['failures_breaking_a_stage'], requirements=nf['requirements'], energy_j=nf['energy_j'],
               double_fault=nf['double_fault_bound']),
          'built near-suit nozzle set, real mass and inertia: approach, braking, alignment, capture and abort / retreat each keep the force and '
          'torque they need (x control margin) with any one nozzle failed closed; capture and lost-braking contact energy inside the capture '
          'mechanism\'s capacity')
    report['single_failure'] = {k: study[k] for k in ('single_failure_drone_free', 'single_failure_docked', 'single_failure_suit_reserve', 'single_failure_drone_proximity')}
    # ---- manipulator kinematics and IK controls
    ik = ik_test(drone, angles); report['manipulators'] = ik
    fk_ok = all(v['fk_residual_mm'] < .5 and v['fk_approach_error_deg'] < .5 and v['joints_in_range'] and v['reach_ok'] for p in ik.values() for v in p.values())
    check('manipulator_fk', fk_ok, {f'{n}.{K}': (v['fk_residual_mm'], v['joints_in_range'], v['reach_ok']) for n, p in ik.items() for K, v in p.items()},
          'every named pose reached (residual < 0.5 mm, approach < 0.5 deg) with every joint in range')
    ik_ok = all(v['ik_control_residual_mm'] < 2.0 for p in ik.values() for v in p.values())
    check('manipulator_ik_controls', ik_ok, {f'{n}.{K}': (v['ik_control_residual_mm'], v['ik_control_approach_error_deg']) for n, p in ik.items() for K, v in p.items()},
          'from the deployed (ready) pose, the in-file IK control (ik_A / ik_B bone + property) brings the flange to each named target within 2 mm')
    # ---- tool contact (maintenance state)
    ms = next(s for s in states if s['key'] == 'maintenance'); ad.action = act; sc.frame_set(ms['frame']+3); dg = bpy.context.evaluated_depsgraph_get()
    post = next(o for o in hull if o.get('grapple_post')); pads = [o for o in bpy.data.objects if o.name.startswith('TOOL_Utility_Gripper_Pad_')]
    jaws = [o for o in bpy.data.objects if o.name.startswith(('TOOL_Utility_Gripper_Jaw_', 'TOOL_Utility_Gripper_Rail', 'TOOL_Utility_Gripper_Body'))]
    Pb = world_mesh_bvh([post], dg)
    # surface gap: a flat pad touches the round post along a line (away from both meshes' vertices), so measure from the post axis:
    # the nearest pad point to points along the axis, less the post radius
    pc_ = Vector(post['jaw_centre']); pa_ = Vector(post['axis']).normalized(); r_ = post['radius_m']
    pad_d = {o.name: max(0.0, min(world_mesh_bvh([o], dg).find_nearest(pc_+pa_*(t/100))[3] for t in range(-2, 3))-r_) for o in pads}
    grasp = dict(pad_to_post_mm={k: round(v*1000, 2) for k, v in pad_d.items()}, pads_overlap=overlap(world_mesh_bvh(pads, dg), Pb),
                 jaws_body_overlap=overlap(world_mesh_bvh(jaws, dg), Pb), grip_B=round(drone['grip_B'], 4))
    check('grasp_utility_gripper', grasp['pads_overlap'] == 0 and grasp['jaws_body_overlap'] == 0 and all(v <= .0015 for v in pad_d.values()), grasp,
          'all four pads within 1.5 mm of the grapple post (line contacts), no pad, jaw or body inside it')
    bit = bpy.data.objects['TOOL_Powered_Driver_Bit']; fas = [o for o in hull if o.name.startswith('HULL_ORU_Fastener_')]
    tip = bit.matrix_world @ Vector((0, ev.TOOLS[[t['key'] for t in ev.TOOLS].index('powered_driver')]['length_m'], 0))
    F_ = world_mesh_bvh(fas, dg); near = F_.find_nearest(tip); flange = world_mesh_bvh([o for o in hull if o.name == 'HULL_ORU_Front_Flange'], dg)
    drv = dict(tip_to_fastener_mm=round(near[3]*1000, 2), fastener=OWNERS[id(F_)][near[2]], bit_into_flange=overlap(world_mesh_bvh([bit], dg), flange))
    check('driver_contact', drv['tip_to_fastener_mm'] <= 3.0 and drv['bit_into_flange'] == 0, drv, 'driver bit engages a fastener (<= 3 mm) without entering the flange')
    report['tool_contact'] = dict(utility_gripper=grasp, driver=drv)
    # ---- helmet clearance (rest pose)
    suit.data.pose_position = 'REST'; bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
    hc = helmet(suit, dg); suit.data.pose_position = 'POSE'; report['helmet'] = hc
    check('helmet_clearance', hc['points_outside_shell'] == 0 and hc['min_distance_m'] >= .015, hc,
          'every swept head point inside the helmet with >= 15 mm to the shell (data [form] head_motion_deg)')
    # ---- docked-arm assistance study
    asi = next(s for s in states if s['key'] == 'assist'); sc.frame_set(asi['frame']+3); dg = bpy.context.evaluated_depsgraph_get()
    helm = world_mesh_bvh([o for o in suit_objs if o.name.endswith(('Helmet_Shell', 'Helmet_Brow', 'Visor', 'Helmet_Crest'))], dg)
    emerg = [o for o in suit_objs if o.get('system') == 'emergency' or 'Manual_Release' in o.name or o.name.startswith('TETHER_')]
    Em = world_mesh_bvh(emerg, dg); At = arms_tools
    d_helm = min_distance(At, helm, dg); d_em = min_distance(At, Em, dg) if Em else 9.0
    flanges = {K: drone.matrix_world @ drone.pose.bones[f'arm_{K}_tool'].head for K in ev.ARMS}
    comd = Vector(study['com_docked']); loads = {K: ev.docked_arm_loads(round((flanges[K]-comd).length, 3), ev.ARMS[K]['tip_force_n']) for K in ev.ARMS}
    hcen = Vector(json.loads(suit['eva_helmet'])['centre'])
    # where the work happens: the tool's working point (flange + tool length along the tool axis), A with its gripper, B with the utility jaws
    tlen = {t['key']: t['length_m'] for t in ev.TOOLS}
    tips = {K: flanges[K]+(drone.matrix_world.to_3x3() @ (drone.pose.bones[f'arm_{K}_tool'].matrix.to_3x3() @ Vector((0, 1, 0)))).normalized()*tlen[k]
            for K, k in (('A', 'precision_gripper'), ('B', 'utility_gripper'))}
    seen = {K: round(math.degrees(math.atan2(abs(tips[K].x-hcen.x), -(tips[K].y-hcen.y))), 1) for K in ev.ARMS}
    assist = dict(arms_to_helmet_mm=round(d_helm*1000, 1), arms_to_emergency_items_mm=round(d_em*1000, 1), emergency_items=[o.name for o in emerg],
                  arms_vs_astronaut=st_out['assist']['arms_tools_vs_astronaut'], flange_world=[[round(v, 3) for v in flanges[K]] for K in ev.ARMS],
                  tool_point_world=[[round(v, 3) for v in tips[K]] for K in ev.ARMS], tool_point_azimuth_from_face_deg=seen, visor_half_width_deg=ev.SUIT['visor']['az_max_deg'], reaction=loads,
                  plumes=dict(suit=st_out['assist']['suit_plume_hits'], drone=st_out['assist'].get('drone_plume_hits')))
    report['docked_arm_assistance'] = assist
    check('docked_assist_clearance', d_helm >= .03 and d_em >= .05 and not st_out['assist']['arms_tools_vs_astronaut'],
          dict(helmet_mm=assist['arms_to_helmet_mm'], emergency_mm=assist['arms_to_emergency_items_mm'], contacts=st_out['assist']['arms_tools_vs_astronaut']),
          'docked assistance pose: arms and tools >= 30 mm from the helmet, >= 50 mm from the release handle, reserve valve, gauge and tether hooks, '
          'no contact with the astronaut')
    check('docked_assist_in_view', all(v <= ev.SUIT['visor']['az_max_deg'] for v in seen.values()), seen,
          'both tool working points inside the visor\'s horizontal field (azimuth from straight ahead <= the visor half-width)')
    # ---- analytical budgets (PROVISIONAL: they meet their design targets on paper)
    lsb = study['life_support_budget']; st_ = study['structure']; ls = study['life_support']
    analysis('life_support_budget', lsb['cases']['nominal']['meets_target'] and lsb['emergency']['meets'] and ls['margin_l'] >= 0,
             dict(nominal_limit_h=lsb['cases']['nominal']['duration_limit_h'], limiting=lsb['cases']['nominal']['limiting'],
                  high_case_h=lsb['cases']['high']['duration_limit_h'], purge_min=lsb['emergency']['purge_minutes'], packed_margin_l=ls['margin_l'],
                  heat_rejection_w=lsb['heat_rejection_nominal_w']),
             f'nominal case covers {lsb["target_h"]["nominal"]} h + {lsb["target_h"]["reserve"]} h on O2, feedwater and battery; secondary O2 gives '
             f'>= {lsb["target_h"]["emergency_return_min"]:.0f} min purge; packed items fit the module (high case is reported, not required)')
    analysis('structure', st_['dock']['ok'] and st_['dock']['pull_ok'] and st_['release']['ok'] and all(v['margin'] > 0 for v in st_['arm_roots'].values())
             and all(v['margin'] > 0 for v in st_['couplings'].values()),
             dict(dock_limit_nm=st_['dock']['limit_moment_nm'], dock_rating_nm=st_['dock']['rating_nm'], pull_limit_n=st_['dock']['limit_pull_n'],
                  release_n=st_['release']['loaded_n'], arm_root_margin={k: v['margin'] for k, v in st_['arm_roots'].items()},
                  coupling_margin={k: v['margin'] for k, v in st_['couplings'].items()}, anchor_gripper_off_axis_deg=st_['anchor_gripper']['max_off_axis_deg']),
             f'limit loads x FoS {st_["fos_ultimate"]} inside the dock / anchor ratings, arm-root links and tool couplings; emergency release '
             'within a gloved pull')

    # ---- engineering review items (not provable on the mesh)
    review('life_support_capability', f'The budget (O2 {lsb["cases"]["nominal"]["o2_kg_h"]} kg/h, feedwater {lsb["cases"]["nominal"]["feedwater_kg_h"]} kg/h, '
           f'{lsb["electronics_w"]} W electronics) is a steady-state estimate; no transient thermal, CO2-bed sizing or humidity model, no test. '
           'EVA-004 suit pressure stays OPEN.', 'data/eva_suit.toml [life_support], eva_system.life_support_budget()')
    review('structural_loads', 'Closed-form limit-load estimate only: channel-wall bearing, the module-to-cuirass mount and the composite '
           'laminates need FE and test.', 'eva_system.structure(), data/eva_drone.toml [anchor] structure')
    review('docked_arm_assistance', 'Reach is limited to beside and above the helmet; arm forces react into the suit through the dock, so the astronaut '
           'must be anchored (foot restraint or handrail) and the drone thrusters stay inhibited. Moving parts beside the helmet need a '
           'crew-commanded hold-to-run mode and a force limit; no human-in-the-loop evaluation exists.', 'arm loads, docked_arm_loads()')
    review('plume_model', 'The 3D envelope is a sampled Simons far-field estimate (no flow solution, reflection or contamination transport): it bounds '
           'where plumes reach, not their effect on coatings or optics; not a qualification.', 'data/eva_drone.toml [gas], report plume_envelope')
    report['results'] = RESULTS
    report['summary'] = dict(PASS=sum(r['result'] == 'PASS' for r in RESULTS), PROVISIONAL=sum(r['result'] == 'PROVISIONAL' for r in RESULTS),
                             UNVERIFIED=sum(r['result'] == 'UNVERIFIED' for r in RESULTS), FAIL=sum(r['result'] == 'FAIL' for r in RESULTS),
                             failed=[r['check'] for r in RESULTS if r['result'] == 'FAIL'])
    args.report.parent.mkdir(parents=True, exist_ok=True); args.report.write_text(json.dumps(report, indent=1, default=str)+'\n')
    print('EVA_SYSTEM checks', json.dumps(report['summary']), flush=True)


if __name__ == '__main__':
    main()
