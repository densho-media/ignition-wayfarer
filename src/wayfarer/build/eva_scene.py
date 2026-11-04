"""The Wayfarer EVA system scene: the suit (WAYFARER_EVA_Y155 on the instructor) and the companion drone (WAYFARER_EVA_DRONE) in one packed
review file with the dock, the operating states and the dock / undock sequences (docs/WAYFARER_EVA_SYSTEM.md).

  blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/build/eva_scene.py -- [--wearer instructor]

Appends assets/characters/WF_EVA_<WEARER>.blend and WF_EVA_DRONE.blend unchanged (their rigs, actions, drivers and IK controls come with
them; nothing is re-posed by hand) and adds only what belongs to the pair:

- the dock: the drone rig follows the suit's SOCKET_DRONE_DOCK through one Copy Transforms (`docked`), the suit's capture tongue and N2
  poppet follow the drone's `capture` and `n2`;
- STATES: one state per SEG frames, the suit pose from EVA_SYSTEM_POSES, the drone placement, dock properties and arm pose from
  DRONE_ARM_POSES (keyed as EVA_SYSTEM_STATES / DRONE_STATES); markers name them and carry their camera;
- DRONE_DOCK_SEQUENCE / DRONE_UNDOCK_SEQUENCE (muted NLA strips): approach, alignment, capture, lock, power, N2, propulsion hand-over;
- presentation props per state (deck rail, ladder, hull panel with a service socket and a replaceable unit with its grapple bar, Brow
  Games gate placeholder), studio lights, the review cameras, a 0.1 m scale reference, optional plume cones (excluded).

Writes assets/characters/WF_EVA_SYSTEM.blend (packed: opens on the hero camera, nothing to run). validation/eva_system.py checks it.
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
from common import OWNER
import eva_geometry as eg
from eva_geometry import SYSTEM, bx, cyl, lathe, link, mat, materials, mesh, torus, tube_path

ASSET = 'WF_EVA_SYSTEM'
SEG = 10
R_DOCK = Matrix(((-1, 0, 0), (0, 0, 1), (0, 1, 0)))     # drone local (x, y, z) -> suit world (-x, z, y)
FULL = dict(docked=1, capture=1, latch=1, elec=1, n2=1, prop_mode=1)
FREE = dict(docked=0, capture=0, latch=0, elec=0, n2=0, prop_mode=0)
HULL = dict(docked=0, capture=1, latch=1, elec=0, n2=0, prop_mode=0)
NEAR = dict(FREE, prop_mode=1)          # free but within proximity_m of a suit: ventral nozzles valved off
# (key, label, dock props, placement, suit pose, drone arm pose, tool_A_driver)
STATES = [('ready', '1 EVA READY (DOCKED)', FULL, None, 'ready', 'stowed', 0),
          ('walk', '2 WALK ON A DECK (DOCKED)', FULL, None, 'walk', 'stowed', 0),
          ('reach', '3 REACH OVERHEAD', FULL, None, 'reach', 'stowed', 0),
          ('crouch', '4 CROUCH', FULL, None, 'crouch', 'stowed', 0),
          ('climb', '5 CLIMB A LADDER', FULL, None, 'climb', 'stowed', 0),
          ('flight', '6 FREE FLIGHT (DOCKED PROPULSION)', FULL, None, 'flight', 'stowed', 0),
          ('detached', '7 DRONE DETACHED, ARMS FOLDED', FREE, 'free', 'deployed', 'stowed', 0),
          ('arms', '8 DRONE DETACHED, ARMS DEPLOYED', FREE, 'free', 'deployed', 'ready', 0),
          ('maintenance', '9 ANCHORED MAINTENANCE (HULL SOCKET)', HULL, 'hull', 'deployed', 'maintenance', 1),
          ('burn', '10 BRACED UNDER THRUST (BURNBROW)', FULL, None, 'burn', 'stowed', 0),
          ('chase', '11 FREE-FLIGHT CHASE (BROW GAMES PLACEHOLDER)', FULL, None, 'chase', 'stowed', 0),
          ('approach', '12 DOCKING APPROACH (ALIGNED, 0.26 M OUT)', NEAR, 'approach', 'ready', 'stowed', 0),
          ('assist', '13 DOCKED-ARM ASSISTANCE (STUDY)', FULL, None, 'ready', 'assist', 0)]
# propulsion armed (flight, docking, free-flying drone); safed on deck, ladder and hull, under ship thrust and in the docked-arm
# assistance study (both thruster sets inhibited while the arms work beside the helmet). Plume checks apply to armed states.
ARMED = {'ready', 'flight', 'detached', 'arms', 'chase', 'approach'}
# one propulsion system at a time: docked the drone flies the pair and the suit reserve is isolated; during a docking approach the suit is
# the passive target (free drift). The reserve is armed only with the drone away ([suit_propulsion] reserve_armed_states).
RESERVE_ARMED = set(ev.SUIT_PROP['reserve_armed_states'])
FREE_M = Matrix.Translation((-.62, -2.15, 1.62)) @ Matrix.Rotation(math.radians(155), 4, 'Z')    # nose away from the astronaut, 2.2 m out:
# a free-flying drone keeps its plumes off the crew by standoff (1 Pa on axis at 1.6 m) unless it is on the docking corridor in near-suit mode
HULL_M = Matrix.Translation((-.30, -.80, 1.22)) @ R_DOCK.to_4x4()                                  # keel in a hull service socket
# the replaceable unit (drone frame, anchored): ahead of the nose on the hull; A backs out its captive fastener, B holds its grapple bar
ORU = dict(centre_local=(0.0, .515, .112), half=(.135, .072, .072), fasteners=((.120, .140), (-.120, .140), (.120, .060), (-.120, .060)))
LIGHTS = (('KEY', (-3.2, -3.6, 4.2), 1400, 2.5, (1.0, .97, .92)), ('FILL', (3.8, -2.4, 2.2), 450, 3.5, (.86, .92, 1.0)),
          ('RIM', (1.5, 4.2, 3.6), 1100, 2.0, (1.0, 1.0, 1.0)), ('REAR_FILL', (-2.6, 4.4, 2.4), 650, 3.0, (.95, .97, 1.0)))
# review cameras: name -> (state, location, target, lens, ortho scale, frame); frame 'free' / 'hull' = the drone's frame in that placement
CAMS = {
    'R01_ASTRONAUT_FRONT': ('ready', (0.0, -8.0, .97), (0.0, 0.0, .97), 50, 2.75, None),
    'R02_ASTRONAUT_SIDE': ('ready', (8.0, .12, .97), (0.0, .12, .97), 50, 2.75, None),
    'R03_REAR_DRONE_DOCKED': ('ready', (0.0, 8.0, .97), (0.0, 0.0, .97), 50, 2.75, None),
    'R04_THREE_QUARTER_HERO': ('ready', (-2.75, -1.95, 1.62), (0, .08, 1.0), 50, None, None),
    'R05_DRONE_DETACHED_ARMS_FOLDED': ('detached', (.62, .70, .46), (0, .0, .05), 50, None, 'free'),
    'R06_DRONE_ARMS_DEPLOYED': ('arms', (.78, .92, .55), (0, .17, .08), 50, None, 'free'),
    'R07_SENSOR_FACE': ('detached', (.15, .78, .20), (0, .26, .07), 50, None, 'free'),
    'R08_PROPULSION_LAYOUT': ('detached', (.42, -.30, -1.05), (0, .0, -.01), 50, None, 'free'),
    'R09_INTERNAL_CUTAWAY': ('detached', (.55, .45, .55), (0, -.01, .05), 50, None, 'free'),
    'R10_MANIPULATOR_CLOSEUP': ('maintenance', (.36, .30, .36), (.0, .45, .11), 50, None, 'hull'),
    'R11_DOCK_ENGAGED': ('ready', (.95, .85, 1.05), (0.0, .30, 1.27), 50, None, None),
    'R12_DOCK_DISENGAGED': ('approach', (1.05, .95, 1.12), (0.0, .38, 1.27), 45, None, None),
    'R13_MAINTENANCE_TASK': ('maintenance', (.55, .25, .95), (0, .30, .06), 40, None, 'hull'),
    'R14_FREE_FLIGHT': ('flight', (-3.6, -2.4, 2.3), (0, .05, 1.08), 50, None, None),
    'R15_DOCKED_ARM_ASSISTANCE': ('assist', (-1.35, -1.25, 2.05), (0, .15, 1.62), 50, None, None),
    'R16_HELMET_SHOULDER_PRESSURE': ('ready', (1.05, -.95, 1.78), (.16, .0, 1.42), 70, None, None),
}
# utility gripper opening that seats its pads on the grapple post (pads close to inner_m; stroke opens each jaw)
GRIP_POST = (ev.UTILITY_JAW['grapple_bar_d_m']/2-ev.UTILITY_JAW['inner_m'])/next(t['jaw_stroke_m'] for t in ev.TOOLS if t['key'] == 'utility_gripper')
MARK_CAM = dict(ready='R04_THREE_QUARTER_HERO', walk='R04_THREE_QUARTER_HERO', reach='R04_THREE_QUARTER_HERO', crouch='R04_THREE_QUARTER_HERO',
                climb='R03_REAR_DRONE_DOCKED', flight='R14_FREE_FLIGHT', detached='R05_DRONE_DETACHED_ARMS_FOLDED', arms='R06_DRONE_ARMS_DEPLOYED',
                maintenance='R13_MAINTENANCE_TASK', burn='R04_THREE_QUARTER_HERO', chase='R14_FREE_FLIGHT', approach='R12_DOCK_DISENGAGED',
                assist='R15_DOCKED_ARM_ASSISTANCE')


def tag(o, job, system='present'):
    o['wf_owner'] = OWNER; o['job'] = job; o['system'] = system; o['geometry_status'] = 'PROTOTYPE'; o.color = SYSTEM.get(system, SYSTEM['present'])
    return o


def into(o, col):
    for c in list(o.users_collection):
        c.objects.unlink(o)
    col.objects.link(o); return o


def append(path, root_name):
    """Append one asset's root collection tree (objects, rigs, actions, drivers) unchanged."""
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c == root_name]
        dst.actions = list(src.actions)
    c = dst.collections[0]; bpy.context.scene.collection.children.link(c); return c


def dedupe_materials():
    """Both assets carry the shared WF_EVA_* materials: keep one of each."""
    for m in list(bpy.data.materials):
        base = m.name.rsplit('.', 1)[0]
        if base != m.name and base in bpy.data.materials:
            m.user_remap(bpy.data.materials[base]); bpy.data.materials.remove(m)


def drive(owner, path, idx, expr, src, prop):
    fc = owner.driver_add(path, idx) if idx is not None else owner.driver_add(path); d = fc.driver; d.type = 'SCRIPTED'
    v = d.variables.new(); v.name = 'v'; v.type = 'SINGLE_PROP'; v.targets[0].id = src; v.targets[0].data_path = f'["{prop}"]'; d.expression = expr
    return fc


def dock(suit, drone, module):
    """The drone follows the suit dock socket while docked; the suit's tongue and poppet follow the drone's capture / N2 state."""
    sock = bpy.data.objects['SOCKET_DRONE_DOCK']
    con = drone.constraints.new('COPY_TRANSFORMS'); con.name = 'DOCKED_TO_SUIT'; con.target = sock
    drive(con, 'influence', None, 'v', drone, 'docked')
    for name, vec, prop, expr in ((module['poppet'], Vector((0, -0.010, 0)), 'n2', 'v*{d}'), (module['capture'], Vector((.010, 0, 0)), 'capture', '(1-v)*{d}')):
        o = bpy.data.objects[name]; b = suit.data.bones[o.parent_bone]; d = b.matrix_local.to_3x3().inverted() @ vec
        for i in range(3):
            drive(o, 'delta_location', i, expr.format(d=f'{d[i]:.5f}'), drone, prop)
    suit['drone_release'] = 0.0; suit.id_properties_ui('drone_release').update(min=0.0, max=1.0, description='manual release handle pulled')
    suit['companion_drone'] = drone.name; drone['astronaut_rig'] = suit.name
    return sock


def pose_arms(drone, ang):
    pb = drone.pose.bones
    for K in ev.ARMS:
        a = ang.get(K, {})
        pb[f'arm_{K}_yaw'].rotation_euler = (0, a.get('yaw', 0.0), 0); pb[f'arm_{K}_upper'].rotation_euler = (a.get('pitch', 0.0), 0, 0)
        pb[f'arm_{K}_fore'].rotation_euler = (a.get('elbow', 0.0), 0, 0); pb[f'arm_{K}_wrist'].rotation_euler = (a.get('wrist', 0.0), 0, 0)
        if f'arm_{K}_wyaw' in pb:
            pb[f'arm_{K}_wyaw'].rotation_euler = (0, 0, a.get('wrist_yaw', 0.0))
        pb[f'arm_{K}_roll'].rotation_euler = (0, a.get('roll', 0.0), 0)


def key_props(o, f, props):
    for k, v in props.items():
        o[k] = float(v); o.keyframe_insert(f'["{k}"]', frame=f)


def key_arms(drone, f):
    for pb in drone.pose.bones:
        if pb.name.startswith('arm_'):
            pb.keyframe_insert('rotation_euler', frame=f)


def suit_states(suit):
    """EVA_SYSTEM_STATES: the suit pose of each state, copied from EVA_SYSTEM_POSES (one pose per SEG frames, constant)."""
    src = bpy.data.actions['EVA_SYSTEM_POSES']; order = json.loads(src['poses']); seg = src['segment_frames']; sc = bpy.context.scene
    act = bpy.data.actions.new('EVA_SYSTEM_STATES'); act.use_fake_user = True; act['wf_owner'] = OWNER
    for i, st in enumerate(STATES):
        suit.animation_data.action = src; sc.frame_set(order.index(st[4])*seg+2)
        vals = {pb.name: (pb.location.copy(), pb.rotation_quaternion.copy(), pb.rotation_euler.copy(), pb.scale.copy()) for pb in suit.pose.bones}
        suit.animation_data.action = act
        for f in (i*SEG, i*SEG+SEG-1):
            for pb in suit.pose.bones:
                lo, q, e, s = vals[pb.name]; pb.location = lo; pb.rotation_quaternion = q; pb.rotation_euler = e; pb.scale = s
                pb.keyframe_insert('location', frame=f); pb.keyframe_insert('rotation_quaternion' if pb.rotation_mode == 'QUATERNION' else 'rotation_euler', frame=f)
    act['states'] = json.dumps([s[0] for s in STATES]); act['segment_frames'] = SEG
    return act


def controller_states(suit):
    """HCM_*_STATES: the fold-out hand controller per state, deployed where the state's suit pose grips it (data [form] hand_controller)."""
    hc = json.loads(suit['eva_hand_controller']); out = {}
    l1, l2 = (bpy.data.objects[n] for n in hc['links'])
    for o, path, vals in ((l1, 'rotation_euler', [math.radians(v) for v in hc['stops']['yaw_deg']]), (l2, 'location', hc['stops']['slide_m'])):
        idx = 2 if path == 'rotation_euler' else 0; o.animation_data_create()
        a = bpy.data.actions.new(f'{o.name}_STATES'); a.use_fake_user = True; a['wf_owner'] = OWNER; o.animation_data.action = a
        for i, st in enumerate(STATES):
            v = vals[1] if st[4] in hc['deploy_poses'] else vals[0]
            for f in (i*SEG, i*SEG+SEG-1):
                getattr(o, path)[idx] = v; o.keyframe_insert(path, index=idx, frame=f)
        out[o.name] = a
    return out


def drone_states(drone, sock, angles):
    """DRONE_STATES: placement, dock properties, bay covers, grips and arm pose per state."""
    sc = bpy.context.scene; act = bpy.data.actions.new('DRONE_STATES'); act.use_fake_user = True; act['wf_owner'] = OWNER
    drone.animation_data.action = act
    for i, (key, label, props, place, _, apose, tool) in enumerate(STATES):
        for f in (i*SEG, i*SEG+SEG-1):
            sc.frame_set(f); bpy.context.view_layer.update(); sw = sock.matrix_world.copy()
            out = apose != 'stowed'
            key_props(drone, f, dict(props, tool_A_driver=tool, bay_A=out, bay_B=out, bay_A_aft=0, bay_B_aft=0, lights=key in ('arms', 'maintenance', 'assist'),
                                     grip_A=.35 if apose == 'ready' else 0.0, grip_B=dict(ready=.25, maintenance=GRIP_POST).get(apose, 0.0)))
            if place == 'approach':
                drone.matrix_world = Matrix.Translation((0, .26, 0)) @ sw
            elif place == 'free':
                drone.matrix_world = FREE_M
            elif place == 'hull':
                drone.matrix_world = HULL_M
            else:
                drone.matrix_world = sw
            drone.keyframe_insert('location', frame=f); drone.keyframe_insert('rotation_euler', frame=f)
            pose_arms(drone, angles.get(apose, {})); key_arms(drone, f)
    act['states'] = json.dumps([s[0] for s in STATES]); act['segment_frames'] = SEG
    return act


def dock_sequence(drone, sock_w, name, undock=False):
    """Docking or its reverse as a muted NLA strip: 0.45 m hold, align, close at the approach speed limit, contact, capture, latch,
    power, N2, propulsion hand-over."""
    a = bpy.data.actions.new(name); a.use_fake_user = True; a['wf_owner'] = OWNER; drone.animation_data.action = a
    off = lambda d: Matrix.Translation((0, d, 0)) @ sock_w
    Z = dict(docked=0, capture=0, latch=0, elec=0, n2=0, prop_mode=1)       # the whole sequence lies inside proximity_m: near-suit mode
    fps = bpy.context.scene.render.fps; v = ev.PROP['approach_speed_max_m_s']; f_close = 45+round((.26-.02)/v*fps/40)   # time-compressed x40 in the file
    steps = [(0, dict(Z), off(.45)), (20, dict(Z), off(.45)), (45, dict(Z), off(.26)), (f_close, dict(Z), off(.02)),
             (f_close+15, dict(Z, docked=1), sock_w), (f_close+25, dict(Z, docked=1, capture=1), sock_w),
             (f_close+40, dict(Z, docked=1, capture=1, latch=1), sock_w), (f_close+53, dict(Z, docked=1, capture=1, latch=1, elec=1), sock_w),
             (f_close+68, dict(Z, docked=1, capture=1, latch=1, elec=1, n2=1), sock_w), (f_close+80, dict(FULL), sock_w)]
    if undock:
        last = steps[-1][0]; steps = [(last-f, pr, mw) for f, pr, mw in reversed(steps)]
    for f, pr, mw in steps:
        key_props(drone, f, pr); drone.matrix_world = mw; drone.keyframe_insert('location', frame=f); drone.keyframe_insert('rotation_euler', frame=f)
        pose_arms(drone, {}); key_arms(drone, f)
    a['sequence'] = json.dumps([(f, pr) for f, pr, _ in steps]); a['time_compression'] = 40
    tr = drone.animation_data.nla_tracks.new(); tr.name = name; tr.strips.new(name, 0, a); tr.mute = True
    return a


def props(M, col, drone, angles):
    """Presentation props per state (PROTOTYPE): deck foot rail and grab bar, ladder, hull panel with the service socket and the replaceable
    unit (fastener for A, grapple bar for B), Brow Games gate placeholder, the maintenance work light."""
    P = {}
    burn = [bx('BURN_Deck_Plate', (0, -.15, -.006), (.9, .7, .006), M['rail'], bevel=.004)]
    for sx in (1, -1):
        burn.append(bx(f'BURN_Foot_Rail_{"P" if sx > 0 else "S"}', (sx*.16, -.22, .02), (.05, .12, .02), M['rail'], bevel=.004))
        burn.append(cyl(f'BURN_Grab_Post_{"P" if sx > 0 else "S"}', (sx*.42, -.50, 0), (sx*.42, -.50, .98), .02, M['rail'], 16))
    burn.append(cyl('BURN_Grab_Bar', (-.45, -.50, .98), (.45, -.50, .98), .018, M['rail'], 16)); P['burn'] = burn
    lad = [cyl(f'LADDER_Rail_{"P" if sx > 0 else "S"}', (sx*.26, -.33, 0), (sx*.26, -.33, 2.4), .016, M['rail'], 16) for sx in (1, -1)]
    lad += [cyl(f'LADDER_Rung_{k}', (-.26, -.31, k*.30), (.26, -.31, k*.30), .013, M['rail'], 16) for k in range(1, 8)]; P['climb'] = lad
    H = HULL_M; yw = H.translation.y-.040; ax3 = (H.col[0].xyz, H.col[1].xyz, H.col[2].xyz)
    hull = [bx('HULL_Panel', (-.10, yw-.012, 1.30), (1.10, .012, 1.05), M['hull'], bevel=.004)]
    for sx in (1, -1):
        hull.append(bx(f'HULL_Service_Socket_Rail_{"P" if sx > 0 else "S"}', H @ Vector((sx*.039, -.015, -.022)), (.007, .180, .018), M['dockmetal'], axes=ax3, bevel=.002))
    hull.append(bx('HULL_Service_Socket_Base', H @ Vector((0, 0, -.038)), (.050, .225, .002), M['dockmetal'], axes=ax3, bevel=.001))
    c = Vector(ORU['centre_local']); hx, hy, hz = ORU['half']; yf_ = c.y-hy
    hull.append(bx('HULL_ORU_Unit', H @ c, (hx, hy, hz), M['ls'], axes=ax3, bevel=.006))
    hull.append(bx('HULL_ORU_Front_Flange', H @ Vector((c.x, yf_-.002, c.z)), (hx+.012, .002, hz+.006), M['metal'], axes=ax3, bevel=.001))
    hull.append(bx('HULL_ORU_Mount_Rail', H @ Vector((c.x, c.y, -.020)), (hx+.03, hy+.02, .020), M['rail'], axes=ax3, bevel=.002))
    for k, (fx, fz) in enumerate(ORU['fasteners']):
        p = Vector((fx, yf_-.004, fz))
        hull.append(cyl(f'HULL_ORU_Fastener_{k}', H @ (p+Vector((0, .003, 0))), H @ (p-Vector((0, .0035, 0))), .0055, M['steel'], 6))
    # grapple post: a standard handling post on the unit's top face, placed on the utility gripper's jaw line in the solved maintenance
    # pose, so the jaws close onto it (fix 4.3: the grasp is a real contact, checked by validation/eva_system.py)
    drone.animation_data.action = None; drone.matrix_world = HULL_M; pose_arms(drone, angles['maintenance'])
    drone['grip_B'] = 0.0; bpy.context.view_layer.update()
    tool = bpy.data.objects['TOOL_Utility_Gripper']; tm = tool.matrix_world.copy()          # the jaw frame (clocking included)
    U = ev.UTILITY_JAW; bar_c = tm @ Vector((0, U['centre_y_m'], 0)); bar_ax = (tm.to_3x3() @ Vector((0, 0, 1))).normalized(); r_bar = U['grapple_bar_d_m']/2
    n = (H.to_3x3() @ Vector((0, 0, 1))).normalized(); top = H @ Vector((c.x, c.y, c.z+hz))
    if bar_ax.dot(n) < 0:
        bar_ax = -bar_ax
    foot = bar_c-bar_ax*((bar_c-top).dot(n)/bar_ax.dot(n))
    post = cyl('HULL_ORU_Grapple_Post', foot, bar_c+bar_ax*.024, r_bar, M['yellow'], 24); hull.append(post)
    hull.append(cyl('HULL_ORU_Grapple_Post_Base', foot-bar_ax*.001, foot+bar_ax*.006, r_bar*1.9, M['metal'], 24))
    post['grapple_post'] = True; post['radius_m'] = r_bar; post['axis'] = list(bar_ax); post['jaw_centre'] = list(bar_c); tool['grasp_target'] = post.name
    for z_ in (.95, 1.75):
        hull.append(cyl(f'HULL_Handrail_Standoff_{int(z_*100)}', (.55, yw, z_), (.55, yw+.06, z_), .010, M['rail'], 12))
    hull.append(cyl('HULL_Handrail', (.55, yw+.06, .90), (.55, yw+.06, 1.80), .0165, M['handrail'], 16))
    hull.append(tube_path('HULL_Tether_Line', [Vector((.16, .03, 1.13)), Vector((.36, -.30, 1.05)), Vector((.55, yw+.06, 1.10))], .0025, M['orange'], 8))
    P['maintenance'] = hull
    gate = [torus('RACE_Gate_Ring', (0, -3.1, 1.15), (0, 1, 0), 1.25, .045, M['hull'], 64, 10), torus('RACE_Gate_Ring_2', (.6, -6.2, 1.5), (0, 1, 0), 1.25, .045, M['hull'], 64, 10)]
    P['chase'] = gate
    ld = bpy.data.lights.new('LIGHT_MAINT_WORK', 'AREA'); ld.energy = 520; ld.size = 1.6; ld.color = (1.0, .97, .93)
    lo = link(bpy.data.objects.new('LIGHT_MAINT_WORK', ld)); lo.location = (-1.3, .9, 2.3)
    lo.rotation_euler = (Vector((-.3, -.8, 1.5))-Vector(lo.location)).to_track_quat('-Z', 'Y').to_euler(); P['maintenance'].append(lo)
    for key, objs in P.items():
        for o in objs:
            into(tag(o, f'{key} presentation prop (PROTOTYPE): not ship geometry'), col)
    return P


def camera(name, loc, target, lens, ortho, col):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_start = .02
    if ortho:
        cd.type = 'ORTHO'; cd.ortho_scale = ortho
    o = link(bpy.data.objects.new(name, cd)); o.location = loc; o.rotation_euler = (Vector(target)-Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return into(o, col)


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--wearer', default='instructor'); ap.add_argument('--out', type=Path)
    args = ap.parse_args(argv)
    out = args.out or ROOT/'assets/characters'/f'{ASSET}.blend'
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; sc['wf_asset'] = ASSET; sc.unit_settings.system = 'METRIC'; sc.render.fps = 30
    who = args.wearer.upper()
    suit_c = append(ROOT/'assets/characters'/f'WF_EVA_{who}.blend', 'WAYFARER_EVA_Y155')
    drone_c = append(ROOT/'assets/characters/WF_EVA_DRONE.blend', 'WAYFARER_EVA_DRONE')
    dedupe_materials()
    suit = next(o for o in suit_c.all_objects if o.type == 'ARMATURE'); drone = bpy.data.objects['RIG_EVA_DRONE']
    module = json.loads(suit['eva_module'])
    root = bpy.data.collections.new('WAYFARER_EVA_SYSTEM'); sc.collection.children.link(root); root['wf_owner'] = OWNER
    for c in (suit_c, drone_c):
        sc.collection.children.unlink(c); root.children.link(c)
    pres = bpy.data.collections.new('EVA_PRESENTATION'); root.children.link(pres); pres.color_tag = 'NONE'
    lc_ = bpy.data.collections.new('EVA_LIGHTS_CAMERAS'); root.children.link(lc_)
    eg.KEEP_EXISTING = True
    M = materials(dict(lcvg=(.3, .5, .6), bladder=(.6, .6, .55)), (.62, .50, .10), 'Drone_Band', OWNER)
    sock = dock(suit, drone, module)
    angles = json.loads(drone['arm_pose_angles'])
    drone.animation_data_create(); suit.animation_data_create()
    sact = suit_states(suit); hacts = controller_states(suit)
    P = props(M, pres, drone, angles)
    sc.frame_set(0); suit.animation_data.action = sact; bpy.context.view_layer.update(); dock_w = sock.matrix_world.copy()
    dock_sequence(drone, dock_w, 'DRONE_DOCK_SEQUENCE'); dock_sequence(drone, dock_w, 'DRONE_UNDOCK_SEQUENCE', undock=True)
    dact = drone_states(drone, sock, angles)
    for i, st in enumerate(STATES):
        for f in (i*SEG, i*SEG+SEG-1):
            for key, objs in P.items():
                for o in objs:
                    o.hide_render = o.hide_viewport = st[0] != key; o.keyframe_insert('hide_render', frame=f); o.keyframe_insert('hide_viewport', frame=f)
    fl = mesh('STUDIO_Floor', [(math.cos(2*math.pi*i/64)*6, math.sin(2*math.pi*i/64)*6, -0.002) for i in range(64)], [tuple(range(64))], M['floor'], smooth=False)
    into(tag(fl, 'neutral studio floor (render only)'), pres)
    for k in range(19):
        z = k*.1; Lt = .06 if k % 5 == 0 else .03
        into(tag(bx(f'REF_Tick_{k*10:03d}', (.62, .30, z), (Lt/2, .002, .0015), M['ref']), 'scale reference: 0.1 m ticks', 'ref'), pres)
    into(tag(bx('REF_Ruler', (.62, .30, .9), (.004, .002, .9), M['ref']), 'scale reference', 'ref'), pres)
    for nm in [o.name for o in pres.objects if o.name.startswith('REF_')]:
        bpy.data.objects[nm].hide_render = True
    w = bpy.data.worlds.new('WF_EVA_Studio'); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (.035, .037, .042, 1)
    for nm, loc, en, size, col in LIGHTS:
        ld = bpy.data.lights.new(f'LIGHT_{nm}', 'AREA'); ld.energy = en; ld.size = size; ld.color = col
        o = into(link(bpy.data.objects.new(f'LIGHT_{nm}', ld)), lc_); o.location = loc
        o.rotation_euler = (Vector((0, 0, 1.1))-Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    # optional plume cones (cold gas is invisible; excluded by default)
    pv = bpy.data.collections.new('EVA_PLUME_VIZ'); pres.children.link(pv)
    pm = mat('Plume_Viz', (.75, .82, .95), .5, 0.0, alpha=.08, owner=OWNER); pa = mat('Plume_Viz_Drone', (.95, .62, .25), .5, 0.0, alpha=.10, owner=OWNER)
    dnoz = json.loads(drone['eva_drone'])['nozzles']
    for nzn in module['nozzles']+dnoz:
        em = bpy.data.objects[nzn]; Lp = .35
        cone = lathe(f'PLUME_{nzn}', Vector((0, 0, 0)), Vector((0, 0, 1)), [(0, .004), (Lp, Lp*math.tan(math.radians(ev.P['plume_half_angle_deg'])))],
                     pa if nzn in dnoz else pm, 12, False, False)
        into(tag(cone, 'optional plume visualisation (cold gas is invisible in reality)'), pv); cone.parent = em
    cams = {}
    for k, (state, loc, tgt, lens, ortho, fr) in CAMS.items():
        if fr:
            F = FREE_M if fr == 'free' else HULL_M; loc = F @ Vector(loc); tgt = F @ Vector(tgt)
        cams[k] = camera(f'CAM_{k}', tuple(loc), tuple(tgt), lens, ortho, lc_)
    for i, st in enumerate(STATES):
        m = sc.timeline_markers.new(st[1], frame=i*SEG); m.camera = cams[MARK_CAM[st[0]]]
    sc.frame_start = 0; sc.frame_end = len(STATES)*SEG-1
    suit.animation_data.action = sact; drone.animation_data.action = dact
    sc['eva_states'] = json.dumps([dict(key=s[0], label=s[1], frame=i*SEG, props=s[2], place=s[3], suit_pose=s[4], arm_pose=s[5],
                                         thrusters=s[0] in ARMED, suit_reserve=s[0] in ARMED and s[0] in RESERVE_ARMED) for i, s in enumerate(STATES)])
    sc['eva_cameras'] = json.dumps({k: v[0] for k, v in CAMS.items()}); sc['eva_wearer'] = args.wearer
    sc['eva_placements'] = json.dumps(dict(free=[list(r) for r in FREE_M], hull=[list(r) for r in HULL_M], oru=ORU))
    for lc in bpy.context.view_layer.layer_collection.children['WAYFARER_EVA_SYSTEM'].children:
        for sub in lc.children:
            if sub.name.endswith('CUTAWAY') or sub.name == 'EVA_PLUME_VIZ':
                sub.exclude = True
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == 'VIEW_3D':
                for sp in area.spaces:
                    if sp.type == 'VIEW_3D':
                        sp.shading.type = 'SOLID'; sp.shading.color_type = 'OBJECT'; sp.region_3d.view_perspective = 'CAMERA'
    t = bpy.data.texts.new('README_EVA_SYSTEM')
    t.write('WAYFARER EVA system review file (PROTOTYPE). Scrub the timeline: each marker is a state and switches to its camera.\n'
            'Drone rig RIG_EVA_DRONE: properties docked / capture / latch / elec / n2 / prop_mode, bay_A / bay_B (+ _aft), grip_A / grip_B, '
            'tool_A_driver, ik_A / ik_B (move the ik_A / ik_B bones in Pose mode). NLA: DRONE_DOCK_SEQUENCE, DRONE_UNDOCK_SEQUENCE, '
            'DRONE_ARM_POSES. Suit actions: EVA_SYSTEM_POSES and the eva_* actions. See docs/WAYFARER_EVA_SYSTEM.md.\n')
    sc.frame_set(0); sc.camera = cams['R04_THREE_QUARTER_HERO']
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.file.pack_all(); bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
    print('WF_EVA_SYSTEM saved', out, 'states', len(STATES), flush=True)


if __name__ == '__main__':
    main()
