"""WAYFARER_EVA_DRONE, the companion drone of the Wayfarer EVA system (docs/WAYFARER_EVA_SYSTEM.md): a suit-docking robotic service
spacecraft with two folding manipulators, a tool cartridge, 20 cold-gas thrusters and a sensor nose. PROTOTYPE equipment, not an S&E 51
fleet class (data/eva_drone.toml).

  blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/build/eva_drone.py

Builds assets/characters/WF_EVA_DRONE.blend in the drone's LOCAL frame (+Y nose, +Z dorsal, -Z dock face, origin on the dock face at the
keel's mid length), so the file stands alone and the system scene (build/eva_scene.py) docks it by one Copy Transforms onto the suit's
SOCKET_DRONE_DOCK. Everything is derived from data/eva_drone.toml, data/eva_suit.toml [form] (dock face, channel) and the pure maths of
src/wayfarer/eva_system.py; nothing is measured off another file.

- body: a graphite core beam and two composite vessel covers in a rounded (superellipse) section that tapers to the tail; lateral arm
  bays closed by two-leaf gull-wing covers (hinged at the core; `bay_A` / `bay_B` the shoulder leaves, `bay_A_aft` / `bay_B_aft` the
  aft leaves that close again behind an unfolded arm), so a stowed drone is one closed shell;
- RIG_EVA_DRONE: chassis, latch bolts, N2 probe, power plug, camera pan / tilt, bay covers, and per arm the joint chain (yaw, pitch,
  elbow, wrist pitch, [wrist yaw], roll, flange) with joint limits from the data; IK controls `ik_A` / `ik_B` (flange target; elbow
  side fixed by the elbow range, so no pole is needed) blended in by the `ik_A` / `ik_B` properties; FK poses in DRONE_ARM_POSES;
- custom properties drive capture / latch / plug / probe, grippers, lights, bay covers and the tool exchange; the dock and propulsion
  state itself (docked, prop_mode) is set by the system scene;
- every object carries assembly, part_id (WAYFARER_EVA_DRONE/<ASSEMBLY>/<PART>), job, system and geometry_status = PROTOTYPE.
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
from common import OWNER, begin, save
from eva_geometry import SYSTEM, bx, capsule, cyl, lathe, lin, link, materials, merged, mesh, nozzle_mesh, text, torus, tube_path
from spec import load

ASSET = 'WF_EVA_DRONE'
ID = 'WAYFARER_EVA_DRONE'
ASSEMBLIES = ('STRUCTURE', 'PROPULSION', 'DOCK', 'MANIPULATORS', 'TOOLS', 'SENSORS', 'MARKINGS', 'RIG')
SYS_ASM = dict(drone='STRUCTURE', drone_frame='STRUCTURE', n2='PROPULSION', drone_thr='PROPULSION', emergency='PROPULSION', dock='DOCK',
               arm='MANIPULATORS', efx='TOOLS', sensor='SENSORS', mark='MARKINGS', tether='STRUCTURE', rig='RIG')
COLS = {}
INDEX = []
BAY_OPEN_DEG = 150.0          # gull-wing cover opening: from its drooping closed slope to upright, clear of the arm's swing
UTILITY_CLOCK_DEG = 90.0      # utility gripper clocking on arm B's flange (see drivers())
POSE_SEG = 10                 # DRONE_ARM_POSES: one pose every POSE_SEG frames


def put(o, system, job, bone=None, rig=None, tag=None, cutaway=False):
    """File a drone object: assembly collection, part id, functional colour; bone-parent it when `bone` is given."""
    asm = SYS_ASM.get(system, 'STRUCTURE')
    for c in list(o.users_collection):
        c.objects.unlink(o)
    COLS[asm + ('/CUTAWAY' if cutaway else '')].objects.link(o)
    o['wf_owner'] = OWNER; o['assembly'] = asm; o['part_id'] = f'{ID}/{asm}/{o.name}'; o['component_id'] = o.name; o['job'] = job
    o['system'] = system; o['geometry_status'] = 'PROTOTYPE'; o['canon_status'] = 'PROTOTYPE'; o['representation'] = 'REP_PROXY'
    o['source_ref'] = 'data/eva_drone.toml (PROTOTYPE, no owner row)'; o['eva_show'] = 'cutaway' if cutaway else 'always'
    o.color = SYSTEM.get(system, SYSTEM['drone'])
    if o.data is not None:
        o.data['wf_owner'] = OWNER
    if tag:
        o['pod'] = tag
    if bone:
        bpy.context.view_layer.update(); w = o.matrix_world.copy(); o.parent = rig; o.parent_type = 'BONE'; o.parent_bone = bone
        bpy.context.view_layer.update(); o.matrix_world = w
        o.scale = (1.0, 1.0, 1.0)                                   # drop the float noise of the bone matrix (about 5e-6)
    INDEX.append(dict(name=o.name, assembly=asm, system=system, job=job, bone=bone or '', cutaway=cutaway))
    return o


def slab(name, rows, cols_of, zbot, ztop, mat_of, mats):
    """A closed body over rows of y; each row has its own x columns (same count). Bottom z = zbot(x), top z = ztop(x, y); mat_of(centre,
    normal) picks a material index."""
    import bmesh
    nx = len(cols_of(rows[0])); V = []; F = []; ny = len(rows)
    for y in rows:
        xs = cols_of(y)
        V += [Vector((x, y, zbot(x))) for x in xs]
        V += [Vector((x, y, ztop(x, y))) for x in xs]
    idx = lambda j, i, top: j*2*nx+(nx if top else 0)+i
    for j in range(ny-1):
        for i in range(nx-1):
            F.append((idx(j, i, 1), idx(j, i+1, 1), idx(j+1, i+1, 1), idx(j+1, i, 1)))
            F.append((idx(j, i, 0), idx(j+1, i, 0), idx(j+1, i+1, 0), idx(j, i+1, 0)))
        for i, s_ in ((0, -1), (nx-1, 1)):
            q = (idx(j, i, 0), idx(j, i, 1), idx(j+1, i, 1), idx(j+1, i, 0))
            F.append(q if s_ < 0 else q[::-1])
    for j, s_ in ((0, -1), (ny-1, 1)):
        for i in range(nx-1):
            q = (idx(j, i, 0), idx(j, i+1, 0), idx(j, i+1, 1), idx(j, i, 1))
            F.append(q if s_ < 0 else q[::-1])
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in V], [], F); me.update()
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-7); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    for m in mats:
        me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = True; p.material_index = mat_of(p.center, p.normal)
    return link(bpy.data.objects.new(name, me))


def form():
    """The body's analytic form (local frame): plan half-width, dock face, outer surface, bays. Shared by the generator and the checks."""
    D = ev.DRONE; L2 = D['length_m']/2; hw = ev.drone_halfwidth; bay = D['bay']; xc = D['core_half_width_m']; xi = bay['x_in_m']
    wm = ev.SUIT['plss_size_m'][0]/2*.97; bulge = ev.SUIT['plss_rear_bulge_m']; F = D['form']
    zv = lambda x: -bulge*min(1.0, (x/wm)**2)                       # dock face: the mirror of the module's convex rear face
    y_b0, y_b1 = F['bay_y_m']
    def ztop(x, y):
        """Outer surface: the core spine, the vessel crown, a shallow valley, the arm pod crown and a superellipse rim to the dock face
        (no vertical side wall), soft nose and tail chamfers. Where the plan narrows (tail) the rim starts further in."""
        ax_ = abs(x); w = max(hw(y), 1e-4); pr = F['profile_m']
        def prof(a):
            a = min(max(a, pr[0][0]), pr[-1][0])
            k = max(i for i in range(len(pr)-1) if pr[i][0] <= a); (x0, z0), (x1, z1) = pr[k], pr[min(k+1, len(pr)-1)]
            u = min(1.0, (a-x0)/max(1e-6, x1-x0)); return z0+(z1-z0)*(1-math.cos(math.pi*u))/2
        xp = max(xc, min(pr[-1][0], w-.035)); hp = prof(xp)
        if ax_ <= xc:
            z = D['depth_core_m']
        elif ax_ <= xp:
            z = prof(ax_)
        else:
            u = min(1.0, (ax_-xp)/max(1e-3, w-xp)); e = F['rim_exponent']; z = zv(x)+(hp-zv(x))*(1-u**e)**(1/e)
        if y > L2-F['chamfer_nose_m']:
            z -= (y-(L2-F['chamfer_nose_m']))**2/F['chamfer_nose_m']*1.4
        if y < -L2+F['chamfer_tail_m']:
            z -= ((-L2+F['chamfer_tail_m'])-y)**2/F['chamfer_tail_m']*1.6
        return max(z, zv(x)+.003)
    in_bay = lambda x, y: abs(x) > xi and y_b0 < y < y_b1
    return dict(L2=L2, hw=hw, xc=xc, xi=xi, zv=zv, ztop=ztop, in_bay=in_bay, bay=(y_b0, y_b1), floor=lambda x: zv(x)+bay['floor_m'],
                bay_split=F['bay_split_y_m'])


def build_rig(f, layout):
    """The drone rig in its local frame. Rest pose = stowed (arms folded in the bays, covers closed)."""
    D = ev.DRONE; bay = D['bay']; keel = D['keel']; kw = keel['width_m']/2
    arm = bpy.data.armatures.new('RIG_EVA_DRONE'); rig = link(bpy.data.objects.new('RIG_EVA_DRONE', arm)); arm.display_type = 'STICK'
    bpy.context.view_layer.update(); bpy.context.view_layer.objects.active = rig; bpy.ops.object.mode_set(mode='EDIT'); eb = arm.edit_bones
    def bone(name, head, tail, parent=None, roll_to=(0, 0, 1), deform=False):
        b = eb.new(name); b.head = Vector(head); b.tail = Vector(tail); b.align_roll(Vector(roll_to)); b.use_deform = deform
        if parent:
            b.parent = eb[parent]
        return b
    bone('chassis', (0, 0, .05), (0, 0, .10), roll_to=(0, -1, 0))
    for y, tag in zip(layout['latch_y'], 'UL'):
        for sx, side in ((-1, 'P'), (1, 'S')):                     # P = suit world +X = drone local -X
            p = Vector((sx*(kw-.008), y, layout['bolt_z'])); bone(f'latch_{side}{tag}', p, p+Vector((0, 0, -.02)), 'chassis', roll_to=(0, 1, 0))
    for nm, y in (('n2_probe', layout['probe_y']), ('elec_plug', layout['plug_y'])):
        p = Vector((0, y, -keel['depth_m']+.004)); bone(nm, p, p+Vector((0, 0, -.02)), 'chassis', roll_to=(0, 1, 0))
    # bay covers: hinge line along the core's edge (local Y), the bone's Y axis is the hinge
    y0, y1 = f['bay']; ys_ = f['bay_split']
    for sx, side in ((1, 'L'), (-1, 'R')):
        for part, a_, b_ in (('aft', y0, ys_), ('fore', ys_, y1)):
            h = Vector((sx*f['xi'], a_, f['ztop'](sx*f['xi'], (y0+y1)/2)))
            bone(f'bay_{side}_{part}', h, h+Vector((0, b_-a_, 0)), 'chassis', roll_to=(0, 0, 1))
    gap = bay['layer_gap_m']; arms = {}
    for K, A in ev.ARMS.items():
        sx = A['side']; x = sx*A['shoulder_x_m']; zl = f['floor'](A['shoulder_x_m'])+bay['layer_low_m']
        S = Vector((x, A['shoulder_y_m'], zl)); E = S+Vector((0, -A['l_upper_m'], gap/2)); Wp = E+Vector((0, A['l_fore_m'], gap/2))
        bone(f'arm_{K}_yaw', S, S+Vector((0, 0, .03)), 'chassis', roll_to=(0, -1, 0))
        bone(f'arm_{K}_upper', S, E, f'arm_{K}_yaw', roll_to=(0, 0, -1))
        bone(f'arm_{K}_fore', E, Wp, f'arm_{K}_upper')
        bone(f'arm_{K}_wrist', Wp, Wp+Vector((0, .016, 0)), f'arm_{K}_fore')
        par = f'arm_{K}_wrist'
        if 'wrist_yaw' in A['joints']:
            bone(f'arm_{K}_wyaw', Wp+Vector((0, .016, 0)), Wp+Vector((0, .028, 0)), par); par = f'arm_{K}_wyaw'
        bone(f'arm_{K}_roll', Wp+Vector((0, .028, 0)), Wp+Vector((0, A['l_wrist_m'], 0)), par)
        F_ = Wp+Vector((0, A['l_wrist_m'], 0)); bone(f'arm_{K}_tool', F_, F_+Vector((0, .02, 0)), f'arm_{K}_roll')
        # IK controls: the flange target (move and turn it) and its wrist-centre child the IK chain reaches for
        bone(f'ik_{K}', F_, F_+Vector((0, .04, 0)), 'chassis')
        bone(f'ik_{K}_wrist', Wp, Wp+Vector((0, .02, 0)), f'ik_{K}')
        arms[K] = dict(S=S, E=E, W=Wp, F=F_, sx=sx)
    cam0 = Vector((-.045, f['L2']-.016, .062)); bone('cam_pan', cam0, cam0+Vector((0, 0, .02)), 'chassis', roll_to=(0, -1, 0))
    bone('cam_tilt', cam0, cam0+Vector((0, .02, 0)), 'cam_pan')
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in rig.pose.bones:
        pb.rotation_mode = 'XYZ'
    return rig, arms


def limits(rig):
    """Joint limits on every arm bone (Limit Rotation, local space: FK poses respect them) and the matching IK locks and limits. Ranges are
    data/eva_drone.toml [arm.*].joints; yaw ranges are inboard-positive, mirrored for the right-hand arm. Blender's IK limits stop at
    +-180 deg, so the pitch and elbow IK ranges are clipped there (the FK limits keep the full range)."""
    rad = math.radians; out = {}
    for K, A in ev.ARMS.items():
        J = A['joints']; s = A['side']; pb = rig.pose.bones
        def lim(bn, axis, lo, hi):
            p = pb[bn]; c = p.constraints.new('LIMIT_ROTATION'); c.name = 'JOINT_LIMIT'; c.owner_space = 'LOCAL'
            for a in 'xyz':
                setattr(c, f'use_limit_{a}', True); setattr(c, f'min_{a}', 0.0); setattr(c, f'max_{a}', 0.0)
            setattr(c, f'min_{axis}', rad(lo)); setattr(c, f'max_{axis}', rad(hi))
            for a in 'xyz':
                setattr(p, f'lock_ik_{a}', a != axis)
            setattr(p, f'use_ik_limit_{axis}', True)
            setattr(p, f'ik_min_{axis}', rad(max(-180.0, lo))); setattr(p, f'ik_max_{axis}', rad(min(180.0, hi)))
            out[f'{bn}.{axis}'] = (lo, hi)
        yl = sorted((J['shoulder_yaw'][0]*s, J['shoulder_yaw'][1]*s))
        lim(f'arm_{K}_yaw', 'y', *yl)
        lim(f'arm_{K}_upper', 'x', *J['shoulder_pitch']); lim(f'arm_{K}_fore', 'x', *J['elbow']); lim(f'arm_{K}_wrist', 'x', *J['wrist_pitch'])
        if f'arm_{K}_wyaw' in pb:
            lim(f'arm_{K}_wyaw', 'z', *J['wrist_yaw'])
        lim(f'arm_{K}_roll', 'y', *J['wrist_roll'])
    return out


def ik_controls(rig):
    """IK per arm: chain yaw-upper-fore reaches the wrist centre under ik_<K>; the wrist tracks the flange target. Influence = property ik_<K>
    (0 = FK poses / actions, 1 = IK). The elbow's one-sided range fixes the elbow side, so the chain needs no pole target."""
    for K in ev.ARMS:
        pb = rig.pose.bones
        c = pb[f'arm_{K}_fore'].constraints.new('IK'); c.name = 'ARM_IK'; c.target = rig; c.subtarget = f'ik_{K}_wrist'; c.chain_count = 3
        c.use_tail = True; c.use_stretch = False; c.iterations = 2000
        t = pb[f'arm_{K}_wrist'].constraints.new('DAMPED_TRACK'); t.name = 'WRIST_TO_TARGET'; t.target = rig; t.subtarget = f'ik_{K}'; t.track_axis = 'TRACK_Y'
        r = pb[f'arm_{K}_roll'].constraints.new('COPY_ROTATION'); r.name = 'ROLL_FROM_TARGET'; r.target = rig; r.subtarget = f'ik_{K}'
        r.use_x = False; r.use_z = False; r.mix_mode = 'ADD'; r.target_space = 'LOCAL'; r.owner_space = 'LOCAL'
        rig[f'ik_{K}'] = 0.0; rig.id_properties_ui(f'ik_{K}').update(min=0.0, max=1.0, description=f'arm {K}: 0 = FK (poses, actions), 1 = IK to ik_{K}')
        for con in (c, t, r):
            fc = con.driver_add('influence'); d = fc.driver; d.type = 'AVERAGE'; v = d.variables.new(); v.type = 'SINGLE_PROP'
            v.targets[0].id = rig; v.targets[0].data_path = f'["ik_{K}"]'


def body(M, f, rig, layout):
    """Shell, core, bay covers, vessels and internals, keel and dock hardware. Returns the objects later steps need."""
    D = ev.DRONE; L2 = f['L2']; hw = f['hw']; xc = f['xc']; xi = f['xi']; zv = f['zv']; ztop = f['ztop']; y_b0, y_b1 = f['bay']
    TR = D['tool_trough']; R = lambda o, s, job, bn='chassis', **kw: put(o, s, job, bn, rig, **kw); out = {}
    ys = merged(lin(-L2, L2, 61), [y_b0-.003, y_b0+.003, y_b1-.003, y_b1+.003, TR['y_from_m']-.003, TR['y_from_m']+.003, TR['y_to_m']-.003,
                                   TR['y_to_m']+.003])
    def core_top(x, y):
        return TR['floor_z_m'] if TR['y_from_m'] < y < TR['y_to_m'] else ztop(x, y)+.004*(1 if abs(y) < L2-.03 else 0)
    core = slab('DRN_Core', ys, lambda y: lin(-xc+.002, xc-.002, 7), zv, core_top, lambda c, n: 0, [M['drone_dark']])
    R(core, 'drone_frame', 'structural core: machined beam nose to tail; carries the keel, the vessel bosses, regulator, battery, avionics and '
      'the tool cartridge (trough); raised 4 mm over the covers')
    # vessel covers: the outer surface everywhere except over the bays, where the shell drops to the bay floor (the covers close it)
    shells = []
    for sx, side in ((1, 'L'), (-1, 'R')):
        def cols(y, sx=sx):
            w = hw(y)-(.008 if y_b0 < y < y_b1 else 0.0)            # under a cover the shell's rim stays 8 mm inside it
            xs = lin(xc+.003, xi-.002, 9)+[xi+.002+(max(xi+.006, w)-xi-.002)*math.sin(math.pi/2*s_) for s_ in lin(0, 1, 16)]
            return [sx*v for v in xs][::(1 if sx > 0 else -1)]
        def top(x, y):
            return f['floor'](x) if f['in_bay'](x, y) else ztop(x, y)
        def mof(c, n):
            return 1 if f['in_bay'](c.x*1.0, c.y) or (y_b0-.004 < c.y < y_b1+.004 and abs(c.x) > xi-.004 and abs(n.y) > .5) or \
                (abs(abs(c.x)-xi) < .004 and y_b0 < c.y < y_b1 and abs(n.x) > .5) else 0
        sh = slab(f'DRN_Shell_{side}', ys, cols, zv, top, mof, [M['drone'], M['drone_dark']])
        shells.append(R(sh, 'drone', f'{side} vessel cover: composite thermal / MMOD skin over the COPV, the nose and tail pods with the '
                        'thruster clusters, and the arm bay (graphite floor)'))
        # bay covers: the outer surface over the bay in two leaves, 3 mm composite, gull-wing hinges on the core edge. The fore leaf
        # (shoulder) stays open while the arm works; the aft leaf closes again behind the unfolded arm, so only the shoulder well is open
        for part, a_, b_, why in (('Aft', y_b0, f['bay_split'], 'opens only while the arm unfolds or folds, then closes behind it'),
                                  ('Fore', f['bay_split'], y_b1, 'stays open over the shoulder while the arm works')):
            yy = lin(a_+.002, b_-.002, 14); V = []; Fc = []; nx = 16
            for y in yy:
                for s_ in lin(0, 1, nx):                             # sine spacing: the rim's curvature gets the columns
                    x = xi+.001+(hw(y)-xi-.001)*math.sin(math.pi/2*s_)
                    V.append(Vector((sx*x, y, ztop(sx*x, y))))
            for j in range(len(yy)-1):
                for i in range(nx-1):
                    q = (j*nx+i, j*nx+i+1, (j+1)*nx+i+1, (j+1)*nx+i); Fc.append(q if sx > 0 else q[::-1])
            cv = mesh(f'DRN_Bay_Cover_{side}_{part}', V, Fc, M['drone'])
            so = cv.modifiers.new('Skin', 'SOLIDIFY'); so.thickness = .003; so.offset = -1.0; so.use_even_offset = True; so.use_rim = True
            R(cv, 'drone', f'arm bay cover {side}, {part.lower()} leaf: closed over the stowed arm (one closed shell in flight and docked); '
              f'opens {BAY_OPEN_DEG:.0f} deg about its core-side hinge; {why}', f'bay_{side}_{part.lower()}')
        hl = [Vector((sx*xi, y, ztop(sx*xi, y)+.001)) for y in lin(y_b0+.004, y_b1-.004, 12)]
        R(tube_path(f'DRN_Bay_Hinge_{side}', hl, .0028, M['graphite'], 8), 'drone_frame', f'bay cover hinge {side} (piano hinge, actuated)')
    out['shells'] = shells; out['core'] = core
    vv = D['vessels']; r_v = vv['outer_d_m']/2; zvs = zv(vv['x_m'])+.003+r_v; out['vessels'] = []
    b = ev.budget()
    for sx, side in ((1, 'L'), (-1, 'R')):
        a_ = Vector((sx*vv['x_m'], vv['y_centre_m']-vv['length_m']/2, zvs)); b_ = a_+Vector((0, vv['length_m'], 0))
        out['vessels'].append(R(capsule(f'N2_Drone_COPV_{side}', a_, b_, r_v, M['copv'], 32, 8), 'n2',
                                f'drone N2 COPV {side}, 30 MPa, {b["drone_vessels"]["volume_l"]/2:.2f} L (type IV, carbon overwrap)'))
    for nm, c, h, m_ in (('Regulator', (0, -.205, .045), (.022, .018, .022), M['n2line']), ('Battery_400Wh', (0, .068, .060), (.026, .056, .026), M['ls']),
                         ('Avionics_IMU', (0, .175, .075), (.03, .035, .03), M['ls'])):
        R(bx(f'DRN_INT_{nm}', c, h, m_, bevel=.004), 'drone_frame', f'internal: {nm.replace("_", " ").lower()}', cutaway=True)
    # keel (ventral): bolts, N2 probe, power plug; load pads
    keel = D['keel']; kw = keel['width_m']/2; ky0 = zv(0); ky1 = ky0-keel['depth_m']; ka, kb = -keel['length_m']/2, keel['length_m']/2
    kv = []; kf = []; sec = [(-kw, ky0+.003), (-kw+.004, ky1), (kw-.004, ky1), (kw, ky0+.003)]
    for yy in (ka, ka+.018, kb-.018, kb):
        nose = yy in (ka, kb)
        kv += [Vector((x*(.88 if nose else 1), yy, z+(.006 if nose and z < ky0 else 0))) for x, z in sec]
    for j in range(3):
        for i in range(3):
            kf.append((j*4+i, (j+1)*4+i, (j+1)*4+i+1, j*4+i+1))
    kf += [(0, 1, 2, 3), (15, 14, 13, 12)]
    keelo = mesh('DOCK_Drone_Keel', kv, kf, M['dockmetal'], smooth=False); bv = keelo.modifiers.new('Bevel', 'BEVEL'); bv.width = .002; bv.segments = 2
    R(keelo, 'dock', 'docking keel: tapered ends self-align in the drafted suit channel (capture), carries the bolts, probe and plug')
    for y, tag in zip(layout['latch_y'], 'UL'):
        for sx, side in ((-1, 'P'), (1, 'S')):
            c = Vector((sx*(kw+.0005), y, layout['bolt_z']))
            R(bx(f'DOCK_Drone_Bolt_{side}{tag}', c, (.006, .0065, .0045), M['steel'], bevel=.001), 'dock',
              'latch bolt: motor-driven, 8.5 mm stroke into the channel wall socket; spring-retracts on the manual release cable', f'latch_{side}{tag}')
    zp = ky1+.012; pn = Vector((0, layout['probe_y'], zp)); pe = Vector((0, layout['plug_y'], 0))
    R(lathe('DOCK_Drone_N2_Probe', pn, Vector((0, 0, -1)), [(0, .0075), (.012, .0075), (.016, .0065), (.026, .0060), (.030, .0040), (.031, 0.0)],
            M['metal'], 20, True, False), 'dock', 'N2 probe: extends 20 mm into the suit\'s dry-break receptacle after the bolts lock; retracts and '
      'seals before they open', 'n2_probe')
    R(torus('DOCK_Drone_N2_Probe_Mark', Vector((0, layout['probe_y'], ky1+.001)), Vector((0, 0, 1)), .0105, .0012, M['blue'], 20, 6), 'n2', 'N2 identification ring')
    R(bx('DOCK_Drone_Power_Plug', Vector((0, pe.y, ky1-.002)), (.010, .006, .007), M['text'], bevel=.001), 'sensor', 'floating blind-mate power / data plug',
      'elec_plug')
    for sx in (1, -1):
        for yy, nm in ((.165, 'U'), (-.16, 'L')):
            c = Vector((sx*.115, yy, zv(sx*.115)))
            R(cyl(f'DOCK_Drone_Load_Pad_{nm}{"L" if sx > 0 else "R"}', c+Vector((0, 0, .001)), c+Vector((0, 0, -.006)), .016, M['rubber'], 20), 'dock',
              'load pad: elastomer on titanium; with the keel it spreads the docked load over the hatch frame')
    out['keel'] = (ky0, ky1, ka, kb)
    return out


def propulsion(M, f, rig):
    """Four thruster clusters (nose pods, tail corners) of six or seven 4 N nozzles; the lateral nozzles lean towards the dock face so the drone
    can back away from a suit with its ventral nozzles valved off (fix 4.1: data [propulsion] lateral_ventral_cant_deg)."""
    hw = f['hw']; zv = f['zv']; ztop = f['ztop']; R = lambda o, s, job, bn='chassis', **kw: put(o, s, job, bn, rig, **kw); cl = {}; noz = []
    for sy, tag, y in ((1, 'N', .232), (-1, 'T', -.228)):
        for sx, side in ((1, 'L'), (-1, 'R')):
            x = sx*(hw(y)-.022); z = (zv(x)+ztop(x, y))/2+.004
            cl[f'{tag}{side}'] = ((x, y, z), sx, sy); c = Vector((x, y, z))
            R(capsule(f'THR_Drone_Cluster_{tag}{side}', c-Vector((0, 0, .024)), c+Vector((0, 0, .024)), .020, M['drone_dark'], 20, 6), 'drone_thr',
              f'thruster cluster {tag}{side}: {7 if tag == "N" else 6} 4 N valves on a manifold block, scarfed into the pod corner', tag=f'D{tag}{side}')
    for name, pos, e, tag, inh in ev.nozzles_from_clusters(cl):
        parts = nozzle_mesh(f'NZ_DRN_{name}', pos, e, .70, M)
        for o in parts[:2]:
            R(o, 'drone_thr', f'drone nozzle {name}: {ev.THRUST_N:.0f} N' + (' (valved off docked and near a suit: it faces the suit)' if inh else ''), tag=f'D{tag}')
        em = R(parts[2], 'drone_thr', f'drone thruster socket {name}', tag=f'D{tag}'); em['exhaust'] = True; em['inhibit_docked'] = inh
        em['thrust_n'] = ev.THRUST_N; em['local_pos'] = list(pos); em['local_dir'] = list(e); noz.append(em.name)
    put(tube_path('N2_INT_Drone_Manifold', [Vector((sx*hw(y)*.8, y, .03)) for sx, y in ((1, .232), (1, -.20), (-1, -.20), (-1, .232))], .003,
                  M['n2line']), 'n2', 'regulated N2 ring main to the four clusters (isolation valve at each)', 'chassis', rig, cutaway=True)
    return cl, noz


def sensors(M, f, rig):
    """Sensor nose (one recessed window), dock-face cameras, proximity, star tracker, dosimeter, magnetometer, antenna. No decorative part."""
    L2 = f['L2']; zv = f['zv']; ztop = f['ztop']; R = lambda o, s, job, bn='chassis': put(o, s, job, bn, rig)
    yf = L2+.0005; zf = .060
    R(bx('SENS_Drone_Face_Bezel', Vector((0, yf-.002, zf)), (.124, .003, .036), M['graphite'], bevel=.006), 'sensor', 'sensor face bezel (graphite)')
    R(bx('SENS_Drone_Face_Glass', Vector((0, yf+.0012, zf)), (.116, .0010, .029), M['display'], bevel=.004), 'sensor',
      'sensor window: dark coated optical window over the nose bay (protects every forward sensor; replaceable)')
    yw = yf+.0022
    for sx, side in ((1, 'L'), (-1, 'R')):
        c = Vector((sx*ev.SENSORS['stereo_baseline_m']/2, yw, zf+.012))
        R(lathe(f'SENS_Drone_Stereo_{side}', c, Vector((0, 1, 0)), [(0, .0125), (.003, .0125), (.005, .0095), (.006, 0)], M['lens'], 24, True, False),
          'sensor', f'stereo navigation camera {side}: {ev.SENSORS["stereo_baseline_m"]:.3f} m baseline (depth to about 3 m at the working range)')
        R(torus(f'SENS_Drone_Stereo_{side}_Ring', c+Vector((0, .0005, 0)), Vector((0, 1, 0)), .0142, .0013, M['metal'], 24, 6), 'sensor', 'lens ring')
        R(bx(f'SENS_Drone_Task_Light_{side}', Vector((sx*.066, yw, zf-.018)), (.022, .0012, .0055), M['lens_light'], bevel=.002), 'sensor',
          f'task light {side}: dimmable LED bar behind a diffuser')
    R(bx('SENS_Drone_Lidar', Vector((0, yw, zf+.018)), (.028, .0014, .0095), M['lens'], bevel=.002), 'sensor', 'flash lidar / time-of-flight depth window (0.1-30 m)')
    R(lathe('SENS_Drone_Inspection_Cam', Vector((-.045, yw-.001, zf)), Vector((0, 1, 0)), [(0, .0110), (.004, .0110), (.007, .0075), (.008, 0)], M['lens'], 24,
            True, False), 'sensor', 'high-resolution inspection camera with macro focus, on a pan / tilt gimbal behind the window', 'cam_tilt')
    R(lathe('SENS_Drone_Thermal_IR', Vector((.045, yw, zf)), Vector((0, 1, 0)), [(0, .0110), (.004, .0110), (.006, .0085), (.0065, 0)], M['lens'], 24, True,
            False), 'sensor', 'thermal infrared inspection camera (8-14 um microbolometer)')
    R(torus('SENS_Drone_Thermal_IR_Ring', Vector((.045, yw+.0005, zf)), Vector((0, 1, 0)), .0122, .0013, M['visor_tint'], 24, 6), 'sensor', 'germanium window ring')
    R(cyl('SENS_Drone_Status', Vector((0, yw, zf-.020)), Vector((0, yw+.0012, zf-.020)), .0026, M['cyan'], 12), 'sensor', 'status light (mode / link)')
    for sx in (1, -1):
        p = Vector((sx*.045, .215, zv(.045)))
        R(cyl(f'SENS_Drone_Dock_Cam_{"L" if sx > 0 else "R"}', p+Vector((0, 0, .001)), p+Vector((0, 0, -.003)), .0075, M['lens'], 20), 'sensor',
          'docking camera (reads the hatch\'s retroreflector targets during approach and alignment)')
    for nm, p, d in (('Tail_L', Vector((.05, -L2+.02, ztop(.05, -L2+.02)+.0004)), Vector((0, -.7, .7))),
                     ('Tail_R', Vector((-.05, -L2+.02, ztop(-.05, -L2+.02)+.0004)), Vector((0, -.7, .7))),
                     ('Nose_L', Vector((.11, .222, ztop(.11, .222)+.0005)), Vector((0, 0, 1))), ('Nose_R', Vector((-.11, .222, ztop(-.11, .222)+.0005)), Vector((0, 0, 1)))):
        d = d.normalized(); R(cyl(f'SENS_Drone_Prox_{nm}', p-d*.002, p+d*.0015, .0055, M['lens'], 16), 'sensor', 'proximity sensor (ToF)')
    yt = -.215; xt = .085; zt_ = ztop(xt, yt)
    R(cyl('SENS_Drone_Star_Tracker_Baffle', Vector((xt, yt, zt_-.002)), Vector((xt, yt, zt_+.013)), .015, M['graphite'], 24, r_b=.017), 'sensor',
      'star tracker baffle (attitude reference)')
    R(cyl('SENS_Drone_Star_Tracker', Vector((xt, yt, zt_+.007)), Vector((xt, yt, zt_+.0095)), .011, M['lens'], 20), 'sensor', 'star tracker lens')
    zt = ztop(0, .0)+.0045
    R(bx('SENS_Drone_Antenna_Patch', Vector((0, .135, zt)), (.030, .030, .0008), M['graphite'], bevel=.002), 'sensor', 'UWB / S-band patch antenna (suit, ship, buddy)')
    for nm, y in (('RAD', .185), ('MAG', .215)):
        R(bx(f'SENS_Drone_{nm}_Window', Vector((0, y, ztop(0, y)+.0045)), (.014, .008, .0008), M['lens'], bevel=.001), 'sensor',
          'embedded radiation dosimeter window' if nm == 'RAD' else 'embedded three-axis magnetometer window')
        R(text(f'MARK_Drone_{nm}', nm, Vector((0, y, ztop(0, y)+.0054)), Vector((-1, 0, 0)), Vector((0, 0, 1)), .0065, M['text_light']), 'mark', 'sensor label')


def tools(M):
    """The three modelled end effectors, each on the common GU-SIF-S coupling plate, built in their own frame (origin on the coupling face,
    +Y along the tool, +Z up). Returns {key: root}; jaws carry `jaw_side` and are driven by grip_A / grip_B."""
    out = {}
    def plate(nm):
        root = cyl(f'TOOL_{nm}', Vector((0, 0, 0)), Vector((0, .006, 0)), ev.COUPLING['outer_d_m']/2, M['metal'], 28); parts = [root]
        for k in range(ev.COUPLING['pins']):
            a = math.radians(90+120*k)
            parts.append(bx(f'TOOL_{nm}_Lug_{k}', Vector((math.cos(a)*.0205, .003, math.sin(a)*.0205)), (.003, .0025, .003), M['steel']))
        parts.append(torus(f'TOOL_{nm}_Contacts', Vector((0, -.0003, 0)), Vector((0, 1, 0)), .010, .0016, M['graphite'], 20, 6))
        return root, parts
    def finish(root, parts, job, jaws=()):
        put(root, 'efx', job)
        for o in parts[1:]:
            put(o, 'efx', f'{root.name} part'); o.parent = root
        for o in jaws:
            put(o, 'efx', f'{root.name} jaw (driven)'); o.parent = root
        return root
    T = {t['key']: t for t in ev.TOOLS}
    r, ps = plate('Precision_Gripper')
    ps.append(bx('TOOL_Precision_Gripper_Body', Vector((0, .024, 0)), (.016, .018, .013), M['graphite'], bevel=.004))
    ps.append(bx('TOOL_Precision_Gripper_Guide', Vector((0, .044, 0)), (.019, .0035, .006), M['metal'], bevel=.001))
    jaws = []
    for sx, nm in ((1, 'L'), (-1, 'R')):
        j = bx(f'TOOL_Precision_Gripper_Jaw_{nm}', Vector((sx*.006, .056, 0)), (.0028, .013, .0075), M['metal'], bevel=.001)
        pd = bx(f'TOOL_Precision_Gripper_Pad_{nm}', Vector((sx*.0029, .062, 0)), (.0008, .006, .006), M['rubber'])
        jaws += [j, pd]; j['jaw_side'] = sx; pd['jaw_side'] = sx
    out['precision_gripper'] = finish(r, ps, T['precision_gripper']['function'], jaws)
    # utility gripper: two jaws, each with two elastomer pads; a bar or handrail is held on four line contacts
    r, ps = plate('Utility_Gripper')
    ps.append(bx('TOOL_Utility_Gripper_Body', Vector((0, .028, 0)), (.022, .022, .018), M['drone'], bevel=.006))
    ps.append(bx('TOOL_Utility_Gripper_Rail', Vector((0, .053, 0)), (.030, .004, .010), M['graphite'], bevel=.002))
    jaws = []
    U = ev.UTILITY_JAW
    for sx, nm in ((1, 'L'), (-1, 'R')):
        j = bx(f'TOOL_Utility_Gripper_Jaw_{nm}', Vector((sx*(U['inner_m']+.0055+.0018), U['centre_y_m'], 0)), (.0055, .016, .013), M['graphite'], bevel=.002)
        j['jaw_side'] = sx; jaws.append(j)
        for k, zz in enumerate((-.0075, .0075)):
            pad = bx(f'TOOL_Utility_Gripper_Pad_{nm}_{k}', Vector((sx*(U['inner_m']+.0009), U['centre_y_m'], zz)), (.0009, .009, .0045), M['rubber'])
            pad['jaw_side'] = sx; jaws.append(pad)
    out['utility_gripper'] = finish(r, ps, T['utility_gripper']['function'], jaws)
    r, ps = plate('Powered_Driver')
    ps.append(cyl('TOOL_Powered_Driver_Motor', Vector((0, .006, 0)), Vector((0, .058, 0)), .0175, M['graphite'], 24))
    ps.append(cyl('TOOL_Powered_Driver_Gearbox', Vector((0, .058, 0)), Vector((0, .074, 0)), .0175, M['metal'], 24, r_b=.010))
    ps.append(cyl('TOOL_Powered_Driver_Chuck', Vector((0, .074, 0)), Vector((0, .082, 0)), .0085, M['steel'], 20))
    ps.append(cyl('TOOL_Powered_Driver_Bit', Vector((0, .082, 0)), Vector((0, T['powered_driver']['length_m'], 0)), .0037, M['steel'], 6))
    ps.append(bx('TOOL_Powered_Driver_Reaction_Tab', Vector((0, .070, -.024)), (.006, .022, .0025), M['metal'], bevel=.001))
    ps.append(torus('TOOL_Powered_Driver_ID', Vector((0, .050, 0)), Vector((0, 1, 0)), .0178, .0012, M['amber'], 24, 6))
    out['powered_driver'] = finish(r, ps, T['powered_driver']['function'])
    return out


def manipulators(M, rig, arms):
    """Two arms in the bays (A precision, 6-axis; B utility, 5-axis): strain-wave joint housings, titanium spars with composite link covers,
    the GU-SIF-S flange; arm A carries the wrist camera and ring light."""
    parts = {'A': [], 'B': []}
    for K, A in ev.ARMS.items():
        a = arms[K]; sx = a['sx']; S, E, Wp, F_ = a['S'], a['E'], a['W'], a['F']; lk = A['link_m']/2; big = K == 'B'
        P_ = lambda o, job, bn: (put(o, 'arm', job, bn, rig), parts[K].append(o))[0]
        rS = .024 if big else .021
        P_(cyl(f'ARM_{K}_Shoulder_Yaw', S+Vector((0, 0, -.018)), S+Vector((0, 0, .016)), rS, M['joint_hw'], 24), 'shoulder yaw actuator (strain-wave drive, '
           'hollow shaft: power and data run through every joint)', f'arm_{K}_yaw')
        P_(cyl(f'ARM_{K}_Shoulder_Pitch', S+Vector((-.022, 0, 0)), S+Vector((.022, 0, 0)), rS-.003, M['joint_hw'], 24), 'shoulder pitch actuator', f'arm_{K}_yaw')
        def link_(nm, a_, b_, bn, r0):
            d = (b_-a_); L_ = d.length; u = d.normalized(); zx = Vector((1, 0, 0)); zz = zx.cross(u).normalized()
            if zz.z < 0:
                zz = -zz
            c = (a_+b_)/2
            P_(bx(f'ARM_{K}_{nm}_Spar', c, (lk*.70, L_/2-r0*.6, lk*.70), M['joint_hw'], axes=(zx, u, zz), bevel=.004), f'{nm.lower()} link spar (titanium '
               'tube, cables inside)', bn)
            P_(bx(f'ARM_{K}_{nm}_Cover', c, (lk*.95, L_/2-r0-.004, lk*.92), M['drone'], axes=(zx, u, zz), bevel=.007),
               f'{nm.lower()} link cover: off-white composite fairing (thermal / MMOD)', bn)
        link_('Upper', S, E, f'arm_{K}_upper', rS)
        P_(cyl(f'ARM_{K}_Elbow', E+Vector((-.021, 0, 0)), E+Vector((.021, 0, 0)), .022 if big else .019, M['joint_hw'], 24), 'elbow actuator (folds 180 deg '
           'between the two layers)', f'arm_{K}_upper')
        link_('Fore', E, Wp, f'arm_{K}_fore', .020)
        rw = .019 if big else .016
        P_(cyl(f'ARM_{K}_Wrist_Pitch', Wp+Vector((-.019, 0, 0)), Wp+Vector((.019, 0, 0)), rw, M['joint_hw'], 24), 'wrist pitch actuator', f'arm_{K}_fore')
        if 'wrist_yaw' in A['joints']:
            q = Wp+Vector((0, .022, 0))
            P_(cyl(f'ARM_{K}_Wrist_Yaw', q+Vector((0, 0, -.015)), q+Vector((0, 0, .015)), .014, M['joint_hw'], 20), 'wrist yaw actuator (precision arm only)',
               f'arm_{K}_wrist')
        P_(cyl(f'ARM_{K}_Wrist_Roll', Wp+Vector((0, .028, 0)), F_-Vector((0, .004, 0)), rw-.002, M['graphite'], 24), 'wrist roll actuator and force / torque '
           'sensor', f'arm_{K}_wyaw' if 'wrist_yaw' in A['joints'] else f'arm_{K}_wrist')
        P_(cyl(f'ARM_{K}_Flange', F_-Vector((0, .005, 0)), F_, ev.COUPLING['outer_d_m']/2, M['metal'], 28), 'tool flange: GU-SIF-S (bayonet, conical seat, '
           'six spring contacts)', f'arm_{K}_roll')
        if K == 'A':
            c = F_+Vector((0, -.014, rw+.004))
            P_(cyl('ARM_A_Wrist_Cam', c-Vector((0, .008, 0)), c+Vector((0, .006, 0)), .0062, M['graphite'], 16), 'wrist camera housing (close-range + macro)', 'arm_A_roll')
            P_(cyl('ARM_A_Wrist_Cam_Lens', c+Vector((0, .006, 0)), c+Vector((0, .0075, 0)), .0042, M['lens'], 16), 'wrist camera lens', 'arm_A_roll')
            P_(torus('ARM_A_Wrist_Ring_Light', c+Vector((0, .0068, 0)), Vector((0, 1, 0)), .0056, .0009, M['lens_light'], 16, 6), 'ring light', 'arm_A_roll')
        P_(text(f'MARK_Arm_{K}', K, (S+E)/2+Vector((sx*lk*.96, 0, 0)), Vector((0, -sx, 0)), Vector((sx, 0, 0)), .011, M['text']), f'arm identification {K}',
           f'arm_{K}_upper')
    return parts


def service(M, f, rig):
    """Tool cartridge, cover seams and fasteners, handholds, fill port, emergency isolation, tether point, markings."""
    L2 = f['L2']; hw = f['hw']; xc = f['xc']; xi = f['xi']; ztop = f['ztop']; TR = ev.DRONE['tool_trough']; R = lambda o, s, job, bn='chassis': put(o, s, job, bn, rig)
    zs_ = TR['floor_z_m']-.002; slots = {}
    for k, y0 in ((1, -.220), (2, -.108)):
        R(bx(f'DRN_Tool_Slot_{k}_Cradle', Vector((0, y0+.048, zs_+.004)), (.030, .050, .004), M['drone_dark'], bevel=.002), 'drone_frame',
          f'tool cartridge slot {k}: cradle with two spring clips; the arm inserts and twists the tool off its bayonet here')
        for yy in (y0+.022, y0+.070):
            R(torus(f'DRN_Tool_Slot_{k}_Clip_{int(yy*1000)}', Vector((0, yy, zs_+.026)), Vector((0, 1, 0)), .0225, .0022, M['graphite'], 24, 6), 'drone_frame',
              'spring clip')
        R(cyl(f'DRN_Tool_Slot_{k}_Receptacle', Vector((0, y0-.004, zs_+.026)), Vector((0, y0+.001, zs_+.026)), .021, M['metal'], 24), 'drone_frame',
          'slot coupling receptacle (the same GU-SIF-S as the arm flange: tools are always held by their coupling)')
        e = link(bpy.data.objects.new(f'SOCKET_TOOL_SLOT_{k}', None)); e.empty_display_type = 'ARROWS'; e.empty_display_size = .04
        e.location = (0, y0+.001, zs_+.026); e.rotation_euler = (0, math.pi if k == 1 else 0.0, 0)
        R(e, 'rig', f'tool slot {k} frame (Child Of target)'); slots[k] = e
    for sx in (1, -1):
        pts = [Vector((sx*(xc+.006), y, ztop(sx*(xc+.006), y)+.0012)) for y in lin(-.20, .20, 11)]
        R(tube_path(f'DRN_Vessel_Cover_Seam_{"L" if sx > 0 else "R"}', pts, .0009, M['text'], 6), 'drone_frame',
          'vessel cover seam along the core: the cover lifts off for COPV inspection (quarter-turn fasteners)')
        for y in (-.21, -.07, .05, .19):
            p = Vector((sx*(xc+.013), y, ztop(sx*(xc+.013), y)+.001))
            R(cyl(f'DRN_Fastener_{"L" if sx > 0 else "R"}_{int(y*1000)}', p-Vector((0, 0, .001)), p+Vector((0, 0, .0012)), .0032, M['steel'], 10),
              'drone_frame', 'quarter-turn fastener (glove-operable with the driver tool)')
        yh = -.215; xh = sx*(hw(yh)-.030); zh = ztop(xh, yh)
        R(tube_path(f'DRN_Handhold_{"L" if sx > 0 else "R"}', [Vector((xh, yh-.030, zh-.004)), Vector((xh, yh-.022, zh+.013)), Vector((xh, yh+.022, zh+.013)),
                                                               Vector((xh, yh+.030, zh-.004))], .0052, M['graphite'], 12), 'drone_frame',
          'glove-size handhold on the tail pod (crew handling, stowage, manual docking assist)')
    pf = Vector((.045, -L2+.012, .030))
    R(cyl('N2_Drone_Fill_Port', pf, pf+Vector((0, -.012, 0)), .0072, M['blue'], 16), 'n2', 'N2 fill port (blue cap): ship recharge to 30 MPa')
    R(cyl('N2_Drone_Isolation', Vector((-.045, -L2+.012, .030)), Vector((-.045, -L2, .030)), .0082, M['red'], 16), 'emergency',
      'emergency N2 isolation valve (red): closes the vessels from outside; a crew member can safe a drone by hand')
    R(torus('TETHER_Drone_Point', Vector((0, -L2-.004, .012)), Vector((1, 0, 0)), .011, .0032, M['steel'], 20, 6), 'tether', 'tether / retrieval point (rated)')
    zt = ztop(0, .08)+.0047
    R(text('MARK_Drone_ID', 'EVA-CD 07', Vector((0, .080, zt)), Vector((-1, 0, 0)), Vector((0, 0, 1)), .0105, M['text_light']), 'mark', 'drone identification')
    for sx in (1, -1):
        x = sx*(xi-.035)
        R(text(f'MARK_Drone_GUC_{"L" if sx > 0 else "R"}', 'G.U.C. WAYFARER 001', Vector((x, -.20, ztop(x, -.20)+.0008)), Vector((0, -sx, 0)),
               Vector((0, 0, 1)), .0062, M['text']), 'mark', 'official marking (small)')
    return slots


def drivers(rig, tl):
    """Properties and drivers that live in the drone itself (the dock state and Copy Transforms are the system scene's)."""
    for k, v, desc in (('capture', 0.0, '0 open .. 1 the suit channel holds the keel nose (soft capture; mirrored by the suit tongue)'),
                       ('latch', 0.0, '0 bolts retracted .. 1 four bolts locked (hard dock)'), ('elec', 0.0, '0 .. 1 power / data plug mated'),
                       ('n2', 0.0, '0 .. 1 N2 probe mated, suit poppet open'),
                       ('docked', 0.0, '1 = rigidly follows the suit dock socket (system scene); 0 = free flight'),
                       ('prop_mode', 0.0, '0 drone flies itself (26 nozzles) .. 1 docked or within proximity_m of a suit: the 4 ventral nozzles are '
                                          'valved off (docked, the suit hand controller commands both)'),
                       ('lights', 0.0, 'task lights'), ('grip_A', 0.0, 'precision gripper 0 closed .. 1 open'), ('grip_B', 0.0, 'utility gripper 0 .. 1'),
                       ('bay_A', 0.0, 'fore (shoulder) bay cover over arm A: 0 closed .. 1 open'), ('bay_B', 0.0, 'fore bay cover over arm B'),
                       ('bay_A_aft', 0.0, 'aft bay cover over arm A: open only while the arm unfolds or folds'), ('bay_B_aft', 0.0, 'aft bay cover over arm B'),
                       ('tool_A_driver', 0.0, '0 = precision gripper on arm A, driver in slot 1; 1 = driver on arm A, gripper in slot 2')):
        rig[k] = v; rig.id_properties_ui(k).update(min=0.0, max=1.0, description=desc)
    def drv(owner, path, idx, expr, prop):
        fc = owner.driver_add(path, idx) if idx is not None else owner.driver_add(path); d = fc.driver; d.type = 'SCRIPTED'
        var = d.variables.new(); var.name = 'v'; var.type = 'SINGLE_PROP'; var.targets[0].id = rig; var.targets[0].data_path = f'["{prop}"]'
        d.expression = expr; return fc
    for nm in ('latch_PU', 'latch_SU', 'latch_PL', 'latch_SL'):
        sx = -1 if nm[6] == 'P' else 1
        drv(rig.pose.bones[nm], 'location', 0, f'{-sx}*(1-v)*0.0085', 'latch')       # retracts inboard (bone x = drone +X)
    drv(rig.pose.bones['n2_probe'], 'location', 1, '(v-1)*0.020', 'n2')
    drv(rig.pose.bones['elec_plug'], 'location', 1, '(v-1)*0.010', 'elec')
    for side, K, sx in (('L', 'A', 1), ('R', 'B', -1)):            # gull-wing: the cover turns up about the hinge (bone Y)
        drv(rig.pose.bones[f'bay_{side}_fore'], 'rotation_euler', 1, f'{-sx}*v*{math.radians(BAY_OPEN_DEG):.5f}', f'bay_{K}')
        drv(rig.pose.bones[f'bay_{side}_aft'], 'rotation_euler', 1, f'{-sx}*v*{math.radians(BAY_OPEN_DEG):.5f}', f'bay_{K}_aft')
    for key, root in tl.items():
        for o in root.children:
            if 'jaw_side' in o.keys():
                stroke = next(t['jaw_stroke_m'] for t in ev.TOOLS if t['key'] == key)
                drv(o, 'delta_location', 0, f'{o["jaw_side"]}*v*{stroke}', 'grip_A' if key == 'precision_gripper' else 'grip_B')
    for key, on_arm, slot, expr_arm in (('powered_driver', 'arm_A_tool', 'SOCKET_TOOL_SLOT_1', 'v'), ('precision_gripper', 'arm_A_tool', 'SOCKET_TOOL_SLOT_2', '1-v'),
                                        ('utility_gripper', 'arm_B_tool', None, None)):
        o = tl[key]
        c1 = o.constraints.new('CHILD_OF'); c1.name = 'ON_ARM'; c1.target = rig; c1.subtarget = on_arm; c1.inverse_matrix = Matrix.Identity(4)
        if slot:
            drv(c1, 'influence', None, expr_arm, 'tool_A_driver')
            c2 = o.constraints.new('CHILD_OF'); c2.name = 'IN_SLOT'; c2.target = bpy.data.objects[slot]; c2.inverse_matrix = Matrix.Identity(4)
            drv(c2, 'influence', None, '1-v' if expr_arm == 'v' else 'v', 'tool_A_driver')
        else:                                                       # clocked 90 deg on the bayonet: stowed, the jaw rail stands on edge
            o.rotation_euler = (0.0, math.radians(UTILITY_CLOCK_DEG), 0.0)  # under the closed cover; working poses roll the wrist back


def arm_poses(rig, arms):
    """FK poses of both arms from the analytic IK (eva_system.arm_ik) for the named targets of data [arm_pose]; 'stowed' is the rest."""
    gap = ev.DRONE['bay']['layer_gap_m']; out = {'stowed': {}}
    for nm, tg in ev.ARM_POSES.items():
        out[nm] = {}
        for K, (p, a) in tg.items():
            A = ev.ARMS[K]; S = arms[K]['S']
            if a is None:                                           # in-plane approach for the 5-axis arm: along the shoulder-to-target line
                d = Vector((p[0]-S.x, p[1]-S.y, 0)).normalized(); a = (d.x, d.y, -.15)
            ang = ev.arm_ik(A, p, a, tuple(S), (gap/2, gap), A['yaw_offset_m'])
            ang['roll'] = -math.radians(UTILITY_CLOCK_DEG) if K == 'B' else 0.0; ang['_target'] = list(p); ang['_approach'] = list(Vector(a).normalized()); out[nm][K] = ang
    return out


def pose_arms(rig, pose):
    """pose: {K: dict(yaw, pitch, elbow, wrist, wrist_yaw, roll)}; {} or missing arm = stowed."""
    pb = rig.pose.bones
    for K in ev.ARMS:
        ang = pose.get(K, {})
        pb[f'arm_{K}_yaw'].rotation_euler = (0, ang.get('yaw', 0.0), 0)
        pb[f'arm_{K}_upper'].rotation_euler = (ang.get('pitch', 0.0), 0, 0)
        pb[f'arm_{K}_fore'].rotation_euler = (ang.get('elbow', 0.0), 0, 0)
        pb[f'arm_{K}_wrist'].rotation_euler = (ang.get('wrist', 0.0), 0, 0)
        if f'arm_{K}_wyaw' in pb:
            pb[f'arm_{K}_wyaw'].rotation_euler = (0, 0, ang.get('wrist_yaw', 0.0))
        pb[f'arm_{K}_roll'].rotation_euler = (0, ang.get('roll', 0.0), 0)


def key_arms(rig, f):
    for pb in rig.pose.bones:
        if pb.name.startswith('arm_'):
            pb.keyframe_insert('rotation_euler', frame=f)


def pose_library(rig, poses):
    """DRONE_ARM_POSES: one keyed pose per POSE_SEG frames (stowed, then each named pose) with the bay covers and grips that go with it;
    the rig's `arm_poses` property maps names to frames."""
    act = bpy.data.actions.new('DRONE_ARM_POSES'); act.use_fake_user = True; act['wf_owner'] = OWNER
    rig.animation_data_create(); rig.animation_data.action = act; frames = {}
    for i, (nm, pose) in enumerate(poses.items()):
        f = i*POSE_SEG; frames[nm] = f; pose_arms(rig, pose); key_arms(rig, f)
        for k_, v in (('bay_A', 0.0 if nm == 'stowed' else 1.0), ('bay_B', 0.0 if nm == 'stowed' else 1.0), ('bay_A_aft', 0.0), ('bay_B_aft', 0.0)):
            rig[k_] = v; rig.keyframe_insert(f'["{k_}"]', frame=f)
    rig['arm_poses'] = json.dumps(frames)
    for k_ in ('bay_A', 'bay_B', 'bay_A_aft', 'bay_B_aft'):
        rig[k_] = 0.0
    tr = rig.animation_data.nla_tracks.new(); tr.name = act.name; tr.strips.new(act.name, 0, act); tr.mute = True
    rig.animation_data.action = None; pose_arms(rig, {})
    return act


def mass_model(rig, objs):
    """Drone CoM in its local frame (stowed): each dry-mass line at the centre of the parts that carry it, the N2 in the vessels. PROTOTYPE
    lumping (good to a centimetre or two), enough to place the thrusters about the CoM."""
    m = ev.DRONE['dry_mass_kg']; b = ev.budget(); kids = [o for o in bpy.data.objects if o.get('wf_owner') == OWNER and o.type in ('MESH', 'EMPTY')]
    by = lambda *pre: [o for o in kids if o.name.startswith(pre)]
    def centre(os_):
        pts = []
        for o in os_:
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box] if o.type == 'MESH' else [o.matrix_world.translation.copy()]
        return sum(pts, Vector())/len(pts)
    groups = [('shell_and_core', by('DRN_Core', 'DRN_Shell')), ('bay_covers', by('DRN_Bay_Cover')), ('copv_pair', objs['vessels']),
              ('n2_load', objs['vessels']), ('regulator_manifold', by('DRN_INT_Regulator', 'N2_INT_Drone_Manifold')),
              ('battery_400wh', by('DRN_INT_Battery')), ('avionics_sensors', by('DRN_INT_Avionics', 'SENS_Drone')),
              ('thrusters_26', [bpy.data.objects[n] for n in objs['nozzles']]), ('dock_mechanism', [o for o in kids if o.get('system') == 'dock']),
              ('arm_precision', objs['arm_parts']['A']), ('arm_utility', objs['arm_parts']['B']), ('tools_carried', list(objs['slots'].values())),
              ('tool_cartridge', by('DRN_Tool_Slot'))]
    tot = 0.0; acc = Vector(); rows = {}
    for key, os_ in groups:
        mass = b['drone_vessels']['n2_kg'] if key == 'n2_load' else m[key]
        c = centre(os_); acc += c*mass; tot += mass; rows[key] = dict(kg=mass, at=[round(v, 3) for v in c])
    return [round(v, 4) for v in acc/tot], round(tot, 2), rows


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--root', type=Path, default=ROOT); ap.add_argument('--no-save', action='store_true')
    args = ap.parse_args(argv); root = args.root
    path = root/'assets/characters'/f'{ASSET}.blend'; _, _, spec_text, source_text = load(root)
    begin(path, ASSET)
    for o in list(bpy.data.objects):
        if not any(c.name.startswith('ART_') for c in o.users_collection):
            bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        if c.get('wf_owner') == OWNER and not c.name.startswith(('GEN_', 'ART_')):
            bpy.data.collections.remove(c)
    for table in (bpy.data.meshes, bpy.data.materials, bpy.data.actions, bpy.data.armatures, bpy.data.curves):
        for blk in list(table):
            if blk.users == 0 or (table is bpy.data.actions and blk.get('wf_owner') == OWNER):
                table.remove(blk)
    COLS.clear(); INDEX.clear()
    root_c = bpy.data.collections.new(ID); bpy.context.scene.collection.children.link(root_c); root_c['wf_owner'] = OWNER
    root_c['status'] = 'PROTOTYPE'; root_c['fleet'] = ev.DRONE_INFO['fleet']
    for a in ASSEMBLIES:
        c = bpy.data.collections.new(f'DRONE_{a}'); root_c.children.link(c); c['wf_owner'] = OWNER; COLS[a] = c
        cc = bpy.data.collections.new(f'DRONE_{a}_CUTAWAY'); c.children.link(cc); cc['wf_owner'] = OWNER; COLS[a+'/CUTAWAY'] = cc
    pal = dict(lcvg=(.3, .5, .6), bladder=(.6, .6, .55))
    M = materials(pal, (.62, .50, .10), 'Drone_Band', OWNER)
    f = form(); layout = ev.dock_layout()
    rig, arms = build_rig(f, layout)
    put(rig, 'rig', 'drone rig: chassis, two manipulators (FK + IK controls), latch bolts, N2 probe, power plug, bay covers, camera pan / tilt')
    joint_limits = limits(rig); ik_controls(rig)
    objs = body(M, f, rig, layout)
    objs['clusters'], objs['nozzles'] = propulsion(M, f, rig)
    sensors(M, f, rig)
    objs['arm_parts'] = manipulators(M, rig, arms)
    objs['slots'] = service(M, f, rig)
    tl = tools(M); objs['tools'] = tl
    drivers(rig, tl)
    poses = arm_poses(rig, arms); pose_library(rig, poses)
    bpy.context.view_layer.update()
    com, total, rows = mass_model(rig, objs)
    rig['eva_drone'] = json.dumps(dict(id=ID, nozzles=objs['nozzles'], clusters={k: [list(c), sx, sy] for k, (c, sx, sy) in objs['clusters'].items()},
                                       com_local=com, mass_model_kg=total, arm_parts={K: [o.name for o in v] for K, v in objs['arm_parts'].items()},
                                       tools={k: r.name for k, r in tl.items()}, slots={k: e.name for k, e in objs['slots'].items()},
                                       shoulders={K: list(a['S']) for K, a in arms.items()}, joint_limits_deg=joint_limits,
                                       vessels=[o.name for o in objs['vessels']], keel=objs['keel']))
    rig['arm_pose_angles'] = json.dumps({nm: {K: {k: (round(v, 6) if isinstance(v, float) else v) for k, v in a.items()} for K, a in p.items()}
                                         for nm, p in poses.items()})
    bpy.context.scene['wf_asset'] = ASSET
    for lc in bpy.context.view_layer.layer_collection.children[ID].children:
        for sub in lc.children:
            sub.exclude = True
    t = bpy.data.texts.get('WF_EVA_DRONE_SNAPSHOT') or bpy.data.texts.new('WF_EVA_DRONE_SNAPSHOT'); t.clear()
    t.write((root/'data/eva_drone.toml').read_text())
    if not args.no_save:
        save(path, root_c, spec_text, source_text)
    print(f'WF_EVA_DRONE parts={len(INDEX)} nozzles={len(objs["nozzles"])} com={com} mass_model={total} kg', flush=True)


if __name__ == '__main__':
    main()
