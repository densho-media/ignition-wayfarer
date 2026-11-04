"""WAYFARER_EVA_Y155, the suit of the Wayfarer EVA system, dressed onto each wearer (docs/WAYFARER_EVA_SYSTEM.md; TODO EVA-001 / K03; S&E 44
ASSET-01..15, RIG-02..04, ANIM-01..08, RUN-005..009).

  blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/build/eva_suit.py -- [--only instructor newcomer]
          [--report references/p1_eva_suit.json]

Per variant of data/eva_suit.toml the wearer's built character (assets/characters/WF_CHAR_HUMAN_<ID>.blend, `workflow.py characters`) is
appended unchanged (rig, body, correctives, shared actions) and dressed into assets/characters/WF_EVA_<ID>.blend:

- soft layers (cooling garment, bladder, patterned restraint + thermal/MMOD outer) are offset shells of the wearer's own body, smoothed and
  skinned with its weights and corrective shape keys, so every existing action still drives them and the bladder stays continuous;
- the rigid rear-entry cuirass and the integral helmet are one loft from the waist to the crown (data/eva_suit.toml [form]): the cuirass
  opens in an arch over the flexible abdomen, the helmet is an asymmetric superellipsoid sized to the swept head plus clearance, with a
  wrap visor, brow and service crest; the head turns inside it;
- the rear-entry life-support module is the hatch: it carries the dock channel the companion drone (build/eva_drone.py) keys into, four
  suit thruster clusters (16 x 8 N) on the N2 reserve, and the packaging layout of [module] as cut-away internals;
- low-profile bearings, gauntlets, integrated boots, restraint lines, forearm drone and suit controls, chest display, tether reels;
- sockets (RIG-03/04) are bone-parented empties with stable ids, including SOCKET_DRONE_DOCK (the drone's docked frame); the 53-bone
  game_engine rig is not changed;
- the EVA actions of eva_suit.py and the system poses (EVA_SYSTEM_POSES: ready, walk, reach, crouch, climb, free flight, drone deployed,
  braced under thrust, chase) are solved onto the rig with the shared Solver and added as muted NLA tracks beside the shared ones.

Every object carries `assembly`, `part_id` (WAYFARER_EVA_Y155/<ASSEMBLY>/<PART>), `job`, `system` (its functional colour) and
`geometry_status = PROTOTYPE`. Collections follow RUN-005 plus PROPULSION and DOCK. The full body stays in the file (hidden,
`eva_role = validation_body`) for the coverage check; the runtime head is a copy with the covered faces removed. Nothing here is CERTIFIED.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/components')]
import characters as ch
import eva_suit as es
import eva_system as ev
import human_system as hs
from common import OWNER, begin, save
from eva_geometry import (SYSTEM, materials, bx, capsule, cyl, frame3, grid_shell, lathe, lin, link, merged, mesh, nozzle_mesh, ring,
                          boundary_loops, smooth3, smooth_loop, smoothstep, text, torus, tube_path)
from human import Solver, bake_action
from spec import load

HAND_BONES = {f'{f}_{k:02d}_{s}' for s in 'lr' for f in ('thumb', 'index', 'middle', 'ring', 'pinky') for k in (1, 2, 3)} | {'hand_l', 'hand_r'}
FOOT_BONES = {'foot_l', 'foot_r', 'ball_l', 'ball_r'}
FINGERS = [f'{f}_{k:02d}' for f in ('index', 'middle', 'ring', 'pinky') for k in (1, 2, 3)]
THUMB = [f'thumb_{k:02d}' for k in (1, 2, 3)]
B3 = 'spine_03'
KEY = 'SUIT'           # the wearer key of the suit being built (main sets it per variant)
_S = None              # the Part collector of the suit being built
POSE_SEG = 10          # EVA_SYSTEM_POSES: one pose every POSE_SEG frames

def assembly_of(name, system):
    """RUN-005 assembly and part id of a suit object from its name and system."""
    for keys, ap in ((('LCVG',), ('COOLING', 'LCVG_INNER')), (('BLADDER',), ('PRESSURE', 'SUIT_PRESSURE_BLADDER')),
                     (('Torso_Shell', 'Neck_Ring', 'Cuirass_Edge', 'Cuirass_Seal', 'Scye_Sleeve', 'Scye_Housing'), ('PRESSURE', 'SUIT_PRESSURE_HARD_TORSO')),
                     (('Wrist_Disconnect', 'Gauntlet'), ('JOINTS', 'SUIT_GLOVES')), (('Boot', 'Toe_Hook', 'Heel_Fitting'), ('JOINTS', 'SUIT_BOOTS')),
                     (('Bearing', 'Sleeve'), ('JOINTS', 'SUIT_JOINTS')), (('MARK_', 'Arm_Band', 'Label'), ('MARKINGS', 'SAFETY_MARKINGS')),
                     (('OUTER_LAYER', 'Restraint_Line'), ('PROTECTION', 'MMOD_OUTER_SHELL'))):
        if any(k in name for k in keys):
            return ap
    if system == 'sensor' and ('Helmet' in name or name.startswith('SENS_Helmet')):
        return 'HELMET', 'SUIT_HELMET_VISOR'
    return dict(helmet=('HELMET', 'SUIT_HELMET_VISOR'), life=('PLSS', 'PLSS_PRIMARY'), emergency=('PLSS', 'PLSS_PRIMARY'),
                sensor=('PLSS', 'PLSS_PRIMARY'), suit_thr=('PROPULSION', 'SUIT_THRUSTERS'), n2=('PROPULSION', 'N2_RESERVE'),
                dock=('DOCK', 'DRONE_DOCK'), tether=('TETHERS', 'TETHERS'), tool=('TOOLS', 'TOOLS'), rig=('RIG', 'SOCKETS'),
                body=('RIG', 'SOCKETS'), mark=('MARKINGS', 'SAFETY_MARKINGS')).get(system, ('PROTECTION', 'MMOD_OUTER_SHELL'))


def put(o, system, job, bone=None, rig=None, parent=None, tag=None, cutaway=False):
    """File a suit object: its RUN-005 assembly (Part.put), its functional colour and system tag; bone-parent it when `bone` is given."""
    asm, part = assembly_of(o.name, system)
    _S.put(o, asm, part, job, 'cutaway' if cutaway else 'always', bone)
    o.color = SYSTEM.get(system, SYSTEM['suit']); o['system'] = system
    if tag:
        o['pod'] = tag
    if parent is not None and not bone:
        bpy.context.view_layer.update(); w = o.matrix_world.copy(); o.parent = parent; bpy.context.view_layer.update(); o.matrix_world = w
    return o


# ---------------------------------------------------------------------------------------------------------------------- helpers
class Part:
    """Collects one assembly's tagged objects in its collection under WAYFARER_EVA_Y155."""

    def __init__(self, root, data, rig):
        self.root = root; self.data = data; self.rig = rig; self.cols = {}; self.index = []
        for a in data['assemblies']:
            c = bpy.data.collections.new(a); root.children.link(c); c['wf_owner'] = OWNER; self.cols[a] = c

    def put(self, obj, assembly, part, job, show='always', bone=None):
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        self.cols[assembly].objects.link(obj)
        obj['wf_owner'] = OWNER; obj['assembly'] = assembly; obj['part_id'] = f"{self.data['suit']['id']}/{assembly}/{part}"
        obj['component_id'] = obj.name; obj['job'] = job; obj['eva_show'] = show; obj['geometry_status'] = 'PROTOTYPE'
        obj['canon_status'] = 'PROTOTYPE'; obj['representation'] = 'REP_PROXY'; obj['source_ref'] = 'S&E 43/44 EVA suit rows; data/eva_suit.toml'
        if obj.data is not None:
            obj.data['wf_owner'] = OWNER
        if bone:
            world = obj.matrix_world.copy(); obj.parent = self.rig; obj.parent_type = 'BONE'; obj.parent_bone = bone
            bpy.context.view_layer.update(); obj.matrix_world = world
        if show == 'cutaway':
            obj.hide_render = True; obj.hide_viewport = True
        self.index.append(dict(name=obj.name, assembly=assembly, part_id=obj['part_id'], job=job, show=show, bone=bone or ''))
        return obj


def new_mesh(name, verts, faces, material):
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in verts], [], faces); me.update(); me.materials.append(material)
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o)
    for p in me.polygons:
        p.use_smooth = True
    return o


def frame_from(z, hint=Vector((0, 0, 1))):
    z = z.normalized(); x = hint.cross(z)
    if x.length < 1e-4:
        x = Vector((1, 0, 0)).cross(z)
    x.normalize(); y = z.cross(x); return x, y, z


def ring_torus(name, centre, axis, R, r, material, n=40, m=10, scale=(1.0, 1.0), section=(1.0, 1.0)):
    """A ring of major radius R (scaled per axis in its plane: an elliptic bearing or seal ring) and section radius r; `section` scales the
    section radially and axially (a flat bearing band is radially thin and axially long)."""
    x, y, z = frame_from(axis); verts = []; faces = []
    for i in range(n):
        a = 2*math.pi*i/n; c = (x*math.cos(a)*scale[0]+y*math.sin(a)*scale[1])
        d = c.normalized()
        for k in range(m):
            b = 2*math.pi*k/m; verts.append(centre+c*R+(d*math.cos(b)*section[0]+z*math.sin(b)*section[1])*r)
    for i in range(n):
        for k in range(m):
            faces.append((i*m+k, i*m+(k+1) % m, ((i+1) % n)*m+(k+1) % m, ((i+1) % n)*m+k))
    return new_mesh(name, verts, faces, material)


def tube(name, a, b, r, material, n=24, cap=True, r_b=None):
    x, y, z = frame_from(b-a); verts = []; faces = []; rb = r if r_b is None else r_b
    for end, rr in ((a, r), (b, rb)):
        for i in range(n):
            t = 2*math.pi*i/n; verts.append(end+(x*math.cos(t)+y*math.sin(t))*rr)
    faces = [(i, (i+1) % n, n+(i+1) % n, n+i) for i in range(n)]
    if cap:
        faces += [tuple(reversed(range(n))), tuple(range(n, 2*n))]
    return new_mesh(name, verts, faces, material)


def dominant(body):
    """Per vertex: the deform bone with the largest weight."""
    names = {g.index: g.name for g in body.vertex_groups}; bones = set(hs.BONES); out = []
    for v in body.data.vertices:
        best = max(((g.weight, names[g.group]) for g in v.groups if names[g.group] in bones), default=(0.0, ''))
        out.append(best[1])
    return out


def in_groups(body, groups):
    idx = {body.vertex_groups[g].index for g in groups if g in body.vertex_groups}
    return [any(g.group in idx and g.weight > .5 for g in v.groups) for v in body.data.vertices]


# ---------------------------------------------------------------------------------------------------------------------- soft layers
def offset_layer(body, name, offset, smooth_n, region_offset, region_smooth, uncovered, dom, material, hand_mat=None, foot_mat=None):
    """A copy of the body, every covered vertex moved out along its normal (region offsets for hands and feet), smoothed, kept at least
    80 % of its offset outside the body; the corrective shape keys keep their deltas; the uncovered (head) faces are removed."""
    o = body.copy(); o.data = body.data.copy(); o.name = name; o.data.name = name
    o.animation_data_clear() if o.animation_data else None
    bpy.context.scene.collection.objects.link(o)
    region = ['hand' if d in HAND_BONES else ('foot' if d in FOOT_BONES else 'body') for d in dom]
    off = [region_offset.get(r, offset) if r != 'body' else offset for r in region]
    nsm = [region_smooth.get(r, smooth_n) if r != 'body' else smooth_n for r in region]
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table(); bm.normal_update()
    base = [v.co.copy() for v in bm.verts]; nor = [v.normal.copy() for v in bm.verts]
    pos = [base[i]+nor[i]*off[i] for i in range(len(base))]
    nbr = [[e.other_vert(v).index for e in v.link_edges] for v in bm.verts]
    for it in range(max(nsm)):
        new = []
        for i, p in enumerate(pos):
            if it >= nsm[i] or not nbr[i]:
                new.append(p); continue
            c = sum((pos[j] for j in nbr[i]), Vector())/len(nbr[i]); q = p.lerp(c, .5)
            along = (q-base[i]).dot(nor[i])
            if along < off[i]*.8:
                q = q+nor[i]*(off[i]*.8-along)
            new.append(q)
        pos = new
    shapes = bm.verts.layers.shape
    for v in bm.verts:
        d = pos[v.index]-base[v.index]
        v.co = pos[v.index]
        for lay in shapes.values():
            v[lay] = v[lay]+d
    unc = in_groups(body, uncovered)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if unc[v.index]], context='VERTS')
    bm.to_mesh(o.data); bm.free()
    o.data.materials.clear(); o.data.materials.append(material)
    if hand_mat or foot_mat:
        dom_after = dominant(o); mats = [material]
        for extra in (hand_mat, foot_mat):
            if extra:
                o.data.materials.append(extra); mats.append(extra)
        for p in o.data.polygons:
            ds = [dom_after[v] for v in p.vertices]; d = max(set(ds), key=ds.count)
            if hand_mat and d in HAND_BONES:
                p.material_index = mats.index(hand_mat)
            elif foot_mat and d in FOOT_BONES:
                p.material_index = mats.index(foot_mat)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


# ---------------------------------------------------------------------------------------------------------------------- measures
def bone(rig, name):
    b = rig.data.bones[name]; return b.head_local.copy(), b.tail_local.copy()


def section(points, a, b, t0, t1, q=.80):
    """The limb section between fractions t0..t1 of the bone a-b: its centroid on the bone's line (the bone runs off-centre in a limb)
    and the q-quantile distance of its points from that centre, perpendicular to the bone (a quantile, not the maximum, so the buttock or
    the armpit next to a joint does not size a ring)."""
    d = b-a; L2 = d.dot(d); sel = []
    for p in points:
        t = (p-a).dot(d)/L2
        if t0 <= t <= t1:
            sel.append(p)
    if not sel:
        return a.lerp(b, (t0+t1)/2), 0.0
    c = sum(sel, Vector())/len(sel); u = d.normalized(); c = c-u*(c-a.lerp(b, (t0+t1)/2)).dot(u)
    rs = sorted(((p-c)-u*(p-c).dot(u)).length for p in sel)
    return c, rs[min(len(rs)-1, int(q*len(rs)))]


def radius_about(points, a, b, t0, t1, q=.80):
    return section(points, a, b, t0, t1, q)[1]


def outer_points(outer, dom, bones):
    return [v.co.copy() for v, d in zip(outer.data.vertices, dom) if d in bones]


# ---------------------------------------------------------------------------------------------------------------------- finish
def outer_zones(outer, rig, M, odom, pal, flex=None):
    """Zones on the outer layer (no geometry moves, so every measured envelope stays): restrained touch-point wear where the suit meets
    rails, restraints and the hull (knee and shin fronts, elbow backs, seat) as a soft per-vertex colour (`wf_zone`, exported as COLOR_0
    and used by the outer textile only); rubber grip faces on the palm side of the glove and the fingertips."""
    me = outer.data; me.materials.append(M['grip']); grip = len(me.materials)-1
    gi = list(me.materials).index(M['glove'])
    B = rig.data.bones; fwd = Vector((0, -1, 0))
    palm = {s: (B[f'index_01_{s}'].matrix_local.col[2].xyz+B[f'middle_01_{s}'].matrix_local.col[2].xyz).normalized() for s in 'lr'}  # +X flexion closes toward +Z
    for poly in me.polygons:
        if poly.material_index != gi:
            continue
        ds = [odom[v] for v in poly.vertices]; d = max(set(ds), key=ds.count); side = d[-1] if d[-2:-1] == '_' else ''
        if d.endswith(('_03_l', '_03_r')) or (side in palm and poly.normal.dot(palm[side]) > .45):
            poly.material_index = grip
    patches = []
    for s in 'lr':
        ka, kb = bone(rig, f'calf_{s}'); ea, _ = bone(rig, f'lowerarm_{s}')
        patches += [(ka, .12, fwd), (ka.lerp(kb, .42), .11, fwd), (ea, .075, Vector((0, 1, 0)))]
    pa, _ = bone(rig, 'pelvis'); patches.append((pa+Vector((0, .08, -.07)), .12, Vector((0, 1, 0))))
    step = lambda a, b, x: (lambda t: t*t*(3-2*t))(max(0.0, min(1.0, (x-a)/(b-a))))
    shell, ab = Vector(pal['shell']), Vector((.50, .49, .46))     # restrained touch-point wear, soft-edged
    jb = next(n for n in M['joint'].node_tree.nodes if n.type == 'BSDF_PRINCIPLED').inputs['Base Color'].default_value
    joint = Vector(jb[:3])                                         # flex zones: the joint restraint colour, soft-edged
    col = me.color_attributes.new('wf_zone', 'FLOAT_COLOR', 'POINT')
    for i, (v, c) in enumerate(zip(me.vertices, col.data)):
        w = max((step(r, r*.86, (v.co-p).length)*step(.10, .35, v.normal.dot(n)) for p, r, n in patches), default=0.0)
        c.color = (*shell.lerp(ab, w).lerp(joint, flex[i] if flex else 0.0), 1.0)
    nt = M['shell'].node_tree; bs = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    if not bs.inputs['Base Color'].is_linked:
        vc = nt.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'wf_zone'; nt.links.new(vc.outputs['Color'], bs.inputs['Base Color'])


def pad(S, key, nm, a, b, centre, r, face, arc, half, bone_, material, job, t=.004, assembly=('PROTECTION', 'MMOD_OUTER_SHELL')):
    """A curved cover plate on a limb: a cylinder-shell segment about the bone a-b, centred on `centre`, outer radius r, `arc` degrees wide
    about the direction `face` (projected off the axis), `half` long either side of centre, t thick, with rolled edges."""
    ax = (b-a).normalized(); f = (face-ax*face.dot(ax)).normalized(); g = ax.cross(f); n, m = 18, 6; verts = []; faces = []
    for rr in (r, r-t):
        for j in range(m+1):
            z = -half+2*half*j/m; shrink = 1.0-.25*abs(2*j/m-1)**4                 # the arc narrows toward the ends: a rounded plate
            for i in range(n+1):
                ang = math.radians(arc*shrink)*(i/n-.5); verts.append(centre+ax*z+(f*math.cos(ang)+g*math.sin(ang))*rr)
    k = (n+1)*(m+1); q = lambda o, j, i: o+j*(n+1)+i
    for j in range(m):
        for i in range(n):
            faces += [(q(0, j, i), q(0, j, i+1), q(0, j+1, i+1), q(0, j+1, i)), (q(k, j, i), q(k, j+1, i), q(k, j+1, i+1), q(k, j, i+1))]
    for j in range(m):
        faces += [(q(0, j, 0), q(0, j+1, 0), q(k, j+1, 0), q(k, j, 0)), (q(0, j, n), q(k, j, n), q(k, j+1, n), q(0, j+1, n))]
    for i in range(n):
        faces += [(q(0, 0, i), q(k, 0, i), q(k, 0, i+1), q(0, 0, i+1)), (q(0, m, i), q(0, m, i+1), q(k, m, i+1), q(k, m, i))]
    o = S.put(new_mesh(f'EVA_{key}_{nm}', verts, faces, material), *assembly, job, bone=bone_)
    o.color = SYSTEM['frame']; o['system'] = 'frame'
    return o



def label(S, key, text, centre, right, normal, size, material, assembly='MARKINGS', part='SAFETY_MARKINGS', job='', bone_=None):
    """Flat lettering (Blender's built-in font) laid on a surface: `right` reads left to right, `normal` points out of the surface."""
    cu = bpy.data.curves.new(f'EVA_{key}_Text', 'FONT'); cu.body = text; cu.size = size; cu.align_x = 'CENTER'; cu.align_y = 'CENTER'
    cu.extrude = .0004
    tmp = bpy.data.objects.new('tmp_text', cu); bpy.context.scene.collection.objects.link(tmp); bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get())); bpy.data.objects.remove(tmp); bpy.data.curves.remove(cu)
    r = right.normalized(); n = normal.normalized(); u = n.cross(r)
    me.transform(Matrix(((r.x, u.x, n.x, centre.x), (r.y, u.y, n.y, centre.y), (r.z, u.z, n.z, centre.z), (0, 0, 0, 1))))
    me.materials.clear(); me.materials.append(material); o = bpy.data.objects.new(f'EVA_{key}_Label_{text[:12].replace(" ", "_")}', me)
    bpy.context.scene.collection.objects.link(o)
    return S.put(o, assembly, part, job or f'lettering "{text}" (ASSET-15; status PROTOTYPE until owner approval)', bone=bone_)


def runtime_head(body, unc, key, S):
    """The visible head inside the helmet: a copy of the body with every covered face removed (the full body stays for validation)."""
    o = body.copy(); o.data = body.data.copy(); o.name = f'CHAR_{key}_Head'; o.data.name = o.name; bpy.context.scene.collection.objects.link(o)
    keep = in_groups(body, unc + ['neck'])
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not keep[v.index]], context='VERTS'); bm.to_mesh(o.data); bm.free()
    S.put(o, 'RIG', 'SOCKETS', 'wearer head visible inside the helmet (the covered body is not exported)')
    return o


def grip_fingers(rig, act, held_frames, curl=(40.0, 50.0, 30.0)):
    """Close the glove on a rail while a hand holds (ASSET-07): key the finger bones' flexion on the frames the hand is held."""
    for side, frames in held_frames.items():
        s = 'r' if side == 'right' else 'l'
        for fr, on in frames:
            for f in FINGERS+THUMB:
                pb = rig.pose.bones[f'{f}_{s}']; k = int(f[-1])-1; ang = (curl[k]*(.5 if f.startswith('thumb') else 1.0)) if on else 0.0
                pb.rotation_mode = 'QUATERNION'; pb.rotation_quaternion = Matrix.Rotation(math.radians(ang), 4, 'X').to_quaternion()
                pb.keyframe_insert('rotation_quaternion', frame=fr, group=pb.name)




# ---------------------------------------------------------------------------------------------------------------------- suit form
def form(rig, body, M, data):
    """The suit on the wearer's MPFB body: soft layers, the rigid cuirass and integral helmet lofted as one surface, slim bearings,
    protective plates, integrated boots and gloves. Returns the measurements later parts are placed from."""
    P = ev.SUIT; unc = data['layers']['uncovered_groups']
    rig.data.pose_position = 'REST'; bpy.context.view_layer.update(); dom = dominant(body)
    layers = {}
    for name, off, sm, mt, extra, job in (
            ('LCVG_INNER', P['lcvg_m'], P['smooth']['lcvg'], M['blue'], {}, 'liquid cooling and ventilation garment (cutaway layer)'),
            ('PRESSURE_BLADDER', P['bladder_m'], P['smooth']['bladder'], M['joint'], {}, 'continuous gas bladder: the pressure boundary (cutaway layer)'),
            ('OUTER_LAYER', P['outer_m'], P['smooth']['outer'], M['shell'], dict(hand_mat=M['glove'], foot_mat=M['fabric_grey']),
             'patterned restraint (lines of non-extension) under a thin thermal / MMOD textile: the visible "second skin"')):
        k = off/P['outer_m']
        o = offset_layer(body, f'EVA_{KEY}_{name}', off, sm, {'hand': P['hand_m']*k, 'foot': P['foot_m']*k},
                            {'hand': min(P['smooth']['hand'], sm), 'foot': min(P['smooth']['foot'], sm)}, unc, dom, mt, **extra)
        cut = name != 'OUTER_LAYER'
        layers[name] = put(o, 'suit', job, cutaway=cut)
    outer = layers['OUTER_LAYER']; odom = dominant(outer)
    # flex joints stand proud of the limb: the restraint folds into a convolute at the elbows, knees and the hip-crotch, so the outer
    # layer there carries 6 mm (22 mm at the elbow) more than the plain offset (the soft layer otherwise thins under skinning in deep flexion)
    pa_, _ = bone(rig, 'pelvis'); crotch_ = pa_+Vector((0, -.01, -.12)); prouds = [(crotch_, .09, .006)]
    for s_ in 'lr':
        prouds += [(bone(rig, f'lowerarm_{s_}')[0], .11, .022), (bone(rig, f'calf_{s_}')[0], .08, .006)]
    bm_ = bmesh.new(); bm_.from_mesh(outer.data); bm_.normal_update(); shp = list(bm_.verts.layers.shape.values())
    for v in bm_.verts:
        w = max(((1.0-smoothstep(min(1.0, (v.co-c_).length/r_)))*h_ for c_, r_, h_ in prouds), default=0.0)
        if w > 0:
            d_ = v.normal*w; v.co += d_
            for L in shp:
                v[L] = v[L]+d_
    bm_.to_mesh(outer.data); bm_.free(); outer.data.update()
    # flexible joint zones: the dark restraint panels at elbow, knee, hip-crotch and armpit where the patterned restraint folds
    W = lambda b: bone(rig, b)
    # every flex zone is a band across its joint axis (elbow, knee, armpit, hip), not a patch: the restraint folds there. The zones are
    # a smooth per-vertex weight (8 mm soft edge, written into the outer layer's colour) instead of whole faces, so no edge steps
    bands = []
    for s in 'lr':
        for parent_, child, lo, hi in (('upperarm', 'lowerarm', -.040, .045), ('thigh', 'calf', -.050, .050)):
            a_, b_ = W(f'{child}_{s}'); bands.append(({f'{parent_}_{s}', f'{child}_{s}'}, a_, (b_-a_).normalized(), lo, hi))
        a_, b_ = W(f'upperarm_{s}'); bands.append(({f'upperarm_{s}'}, a_, (b_-a_).normalized(), .055, .125))
        a_, b_ = W(f'thigh_{s}'); bands.append(({f'thigh_{s}'}, a_, (b_-a_).normalized(), .030, .095))
    pa, _ = W('pelvis'); crotch = pa+Vector((0, -.01, -.12))
    pts = lambda bones: outer_points(outer, odom, bones)
    # ---- the rigid torso + integral helmet: one lofted surface from the waist seal to the helmet crown
    s2, _ = W('spine_02'); ua, _ = W('upperarm_l'); torso = pts({'spine_01', 'spine_02', 'spine_03', 'clavicle_l', 'clavicle_r', 'neck_01'})
    z0 = s2.z+.03; zs = ua.z+.025; m = P['hut_margin_m']
    # the arm roots (armpit and scye) are left out of the section widths: the shell follows the ribcage under the arms instead of
    # bridging out to the sleeves, so a hanging arm clears its sides (fix 4.2; the scye boolean opens the shell at the bearing)
    a0_, b0_ = W('upperarm_l'), W('upperarm_r')
    def arm_root(p):
        for a_, b_ in (a0_, b0_):
            u = (b_-a_).normalized(); t = (p-a_).dot(u)
            if -.10 < t < .12 and ((p-a_)-u*t).length < .085:
                return True
        return False
    torso_w = [p for p in torso if not arm_root(p)] or torso
    # scye bearings (computed before the loft: the shoulder tops inboard of each bearing plane must lie inside the shell)
    scye = {}
    for s in 'lr':
        # the scye axis is a design axis, not the rest pose's upper arm (49 deg down in the MPFB A pose): outboard, tilted down and forward
        # by P['scye_axis_deg'] (as in a hard upper torso), so the bearing plane stands nearly upright in the cuirass's side wall
        a_, b_ = W(f'upperarm_{s}'); L_ = (b_-a_).length; dn, fw = (math.radians(x_) for x_ in P['scye_axis_deg'])
        n_ = Vector(((1 if s == 'l' else -1)*math.cos(dn)*math.cos(fw), -math.cos(dn)*math.sin(fw), -math.sin(dn)))
        b_ = a_+n_*L_; cc, rr = section(pts({f'upperarm_{s}'}), a_, b_, .10, .18, .6); scye[s] = (a_, b_, cc, rr)
    tz = lin(z0, zs, 13); A = []; BF = []; BB = []; YC = []
    for kz, z in enumerate(tz):
        band = [p for p in torso_w if abs(p.z-z) < .016] or torso
        mk = m*(.25+.75*smoothstep(kz/3))                            # the shell closes onto the soft lower torso: no skirt at the waist
        xs = max(abs(p.x) for p in band); ys = [p.y for p in band]; yc = (max(ys)+min(ys))/2
        A.append(xs+mk); BF.append(yc-min(ys)+mk); BB.append(max(ys)-yc+mk); YC.append(yc)
    A, BF, BB, YC = (smooth3(smooth3(l)) for l in (A, BF, BB, YC))
    # helmet: a superellipsoid sized to the head's motion envelope plus clearance (head pivots about the head bone's root)
    head_pts = [v.co.copy() for v, u in zip(body.data.vertices, in_groups(body, unc)) if u]
    hp, _ = W('head'); sweep = []
    mo = P['head_motion_deg']
    for yaw in (-mo['yaw'], 0.0, mo['yaw']):
        for pitch in (-mo['pitch_down'], 0.0, mo['pitch_up']):
            for roll in (-mo['roll'], 0.0, mo['roll']):
                R = (Matrix.Rotation(math.radians(yaw), 3, 'Z') @ Matrix.Rotation(math.radians(-pitch), 3, 'X') @
                     Matrix.Rotation(math.radians(roll), 3, 'Y'))
                sweep += [hp+R @ (p-hp) for p in head_pts[::3]]
    mn = Vector([min(p[i] for p in sweep) for i in range(3)]); mx = Vector([max(p[i] for p in sweep) for i in range(3)])
    # an asymmetric superellipsoid. Its centre sits just ahead of the head's pivot, so the face side (visor) gets the volume the
    # swept face needs and the back of the helmet stays close to the skull: ax = [x, y_front, z, y_back]
    hc = (mn+mx)/2; hc.x = 0.0; hc.y = hp.y+.004; c = P['helmet_clearance_m']; n = P['helmet_exponent']
    inner = [(mx.x-mn.x)/2, hc.y-mn.y, (mx.z-mn.z)/2, mx.y-hc.y]
    def f(q, a_):
        ay_ = a_[1] if q[1] < hc.y else a_[3]
        return (abs(q[0]-hc[0])/a_[0])**n+(abs(q[1]-hc[1])/ay_)**n+(abs(q[2]-hc[2])/a_[2])**n
    k = max(f(q, inner) for q in sweep)**(1/n)
    inner = [a*k for a in inner]; ax = [a+c for a in inner]           # outer = inner envelope + clearance (inner surface of the shell)
    t_hb = P['helmet_base_t']; z_hb = hc.z+t_hb*ax[2]; s_hb = (1-abs(t_hb)**n)**(1/n)
    hb = (ax[0]*s_hb, ax[1]*s_hb, ax[3]*s_hb, hc.y)
    rings = [(z, a, bf, bb, yc, P['hut_exponent']) for z, a, bf, bb, yc in zip(tz, A, BF, BB, YC)]
    for q in range(1, 7):                                            # shoulder yoke: torso section to the helmet base
        t = q/7; s = smoothstep(t); z = zs+(z_hb-zs)*t
        rings.append((z, A[-1]+(hb[0]-A[-1])*s, BF[-1]+(hb[1]-BF[-1])*s, BB[-1]+(hb[2]-BB[-1])*s, YC[-1]+(hb[3]-YC[-1])*s,
                      P['hut_exponent']+(n-P['hut_exponent'])*s))
    # containment: every torso / yoke section is grown until the soft layer's trunk points in its band (arm roots excepted) lie inside it
    # with 6 mm to spare, so the shell never cuts the shoulders or the trapezius
    trunk = [p for p in pts({'spine_01', 'spine_02', 'spine_03', 'clavicle_l', 'clavicle_r'}) if not arm_root(p)]
    for s in 'lr':                                                   # the shoulder top inboard of the bearing plane (above its centre)
        a_, b_, cc, rr = scye[s]; n_ = (b_-a_).normalized()
        trunk += [p for p in pts({f'upperarm_{s}', f'clavicle_{s}'}) if (p-cc).dot(n_) < -.012 and p.z > cc.z]
    for k_, (z, a, bf, bb, yc, ex) in enumerate(rings):
        band = [p for p in trunk if abs(p.z-z) < .012]
        grow = 1.0
        for p in band:
            b_ = bb if p.y > yc else bf
            f_ = ((abs(p.x)+.006)/a)**ex+((abs(p.y-yc)+.006)/b_)**ex
            grow = max(grow, f_**(1/ex))
        if grow > 1.0:
            rings[k_] = (z, a*grow, bf*grow, bb*grow, yc, ex)
    k_hb = len(rings)
    phis = lin(math.asin(t_hb), math.radians(88.0), 20)
    for ph in phis:
        tt = math.sin(ph); sc_ = (1-abs(tt)**n)**(1/n); rings.append((hc.z+tt*ax[2], ax[0]*sc_, ax[1]*sc_, ax[3]*sc_, hc.y, n))
    # visor: one wrap-around window, widest at eye level and dropping at the sides for downward peripheral view; a superellipse in
    # (azimuth, elevation) rather than a rectangle. The brow is the band above it, carrying the lights, cameras and sunshade.
    VZ = P['visor']
    el_ctr = lambda az: VZ['el_centre_deg']-VZ['side_drop_deg']*(az/VZ['az_max_deg'])**2
    def in_visor(az, el):
        h_ = VZ['el_half_deg']*(1-.22*(az/VZ['az_max_deg'])**2)
        return (abs(az)/VZ['az_max_deg'])**VZ['power']+(abs(el-el_ctr(az))/h_)**VZ['power']
    brow_w = lambda az: .55-.35*(abs(az)/78)
    # cuirass: the rigid torso opens over the abdomen in an arch (sternum to the lower ribs); sides and back stay rigid for the hatch
    s3, _ = W('spine_03'); z_arch_top = s3.z+P['cuirass_arch']['z_top_rel_spine03']; arch_half = P['cuirass_arch']['half_angle_deg']
    def below_arch(p):
        z_, a_, bf_, bb_, yc_, ex_ = ring_at(rings[:k_hb], p.z)
        th = abs(math.degrees(math.atan2(p.x/a_, -(p.y-yc_)/bf_)))
        if th >= arch_half:
            return False
        zc_ = z_arch_top-(z_arch_top-z0)*smoothstep(th/arch_half)**1.4
        return p.z < zc_
    info_arch = dict(z_top=z_arch_top, half=arch_half)
    N = 64; verts = []
    for z, a, bf, bb, yc, ex in rings:
        verts += ring(z, a, bf, bb, yc, ex, N)
    top = Vector((0, hc.y, hc.z+ax[2])); verts.append(top)
    faces = []; kind = []
    def cls(cent):
        xn = cent.x/ax[0]; yn = (cent.y-hc.y)/(ax[1] if cent.y < hc.y else ax[3]); zn = (cent.z-hc.z)/ax[2]
        az = math.degrees(math.atan2(xn, -yn)); el = math.degrees(math.atan2(zn, math.hypot(xn, yn))); return az, el
    for r_ in range(len(rings)-1):
        for i in range(N):
            fa = (r_*N+i, r_*N+(i+1) % N, (r_+1)*N+(i+1) % N, (r_+1)*N+i); faces.append(fa)
            cent = sum((verts[q] for q in fa), Vector())/4
            if r_ < k_hb:
                kind.append('cut' if below_arch(cent) else 'hut')
            else:
                az, el = cls(cent)
                vz = in_visor(az, el)
                kind.append('visor' if vz < 1.0 else ('brow' if abs(az) < 78 and el > el_ctr(az) and vz < 1.0+brow_w(az) else 'helmet'))
    last = len(rings)-1
    for i in range(N):
        faces.append((last*N+i, last*N+(i+1) % N, len(verts)-1)); kind.append('helmet')
    # the visor and brow outlines are analytic curves in (azimuth, elevation): move every grid vertex on a visor or brow boundary onto its
    # curve (Newton steps in the parameter plane, then back onto the superellipsoid), so the window edge is smooth instead of stepped
    def surf(az, el):
        d = Vector((math.sin(math.radians(az))*math.cos(math.radians(el)), -math.cos(math.radians(az))*math.cos(math.radians(el)), math.sin(math.radians(el))))
        A3 = (ax[0], ax[1] if d.y < 0 else ax[3], ax[2]); r_ = sum(abs(d[i])**n for i in range(3))**(-1/n)
        return hc+Vector((d.x*A3[0]*r_, d.y*A3[1]*r_, d.z*A3[2]*r_))
    vk = {}
    for i, fa in enumerate(faces):
        for q in fa:
            vk.setdefault(q, set()).add(kind[i])
    snapped = set()
    for inside, fn in (({'visor'}, lambda az, el: in_visor(az, el)), ({'brow'}, lambda az, el: in_visor(az, el)-brow_w(az))):
        for q, ks in vk.items():
            if q in snapped or q >= len(verts)-1 or q < (k_hb+2)*N or not (ks & inside) or not (ks-inside-{'visor'}):
                continue
            az, el = cls(verts[q])
            for _ in range(8):
                f0 = fn(az, el)-1.0; ga = (fn(az+.05, el)-fn(az-.05, el))/.1; ge = (fn(az, el+.05)-fn(az, el-.05))/.1; g2 = ga*ga+ge*ge
                if g2 < 1e-12 or abs(f0) < 1e-5:
                    break
                az -= f0*ga/g2; el -= f0*ge/g2
            verts[q] = surf(az, el); snapped.add(q)
    # scye openings: the torso faces inside each upper arm's root cylinder are cut away; the scye bearing closes the opening
    def in_scye(p):
        for a_, b_, cc, rr in scye.values():
            u = (b_-a_).normalized(); t = (p-cc).dot(u); d = ((p-cc)-u*t).length
            if -.12 < t < .05 and d < rr+.012:
                return True
        return False
    def build(nm, sel, mt, solid, system, job, bevel_=False):
        idx = [i for i, kd in enumerate(kind) if kd in sel]
        used = sorted({q for i in idx for q in faces[i]}); remap = {q: j for j, q in enumerate(used)}
        o = mesh(nm, [verts[q] for q in used], [tuple(remap[q] for q in faces[i]) for i in idx], mt)
        if 'hut' in sel:                                             # scye openings: an exact round cut (boolean); the scye housing seals its edge
            for a_, b_, cc, rr in scye.values():
                u = (b_-a_).normalized()
                R = rr+SCYE_GAP                                      # the cutter is the housing's own bore: the shell edge lies on the housing
                cut = lathe('_scye_cut', cc, u, [(.05, R+.004), (0.0, R+.004)]+[(t, r_-.0015) for t, r_ in housing_profile(R)[1:]], mt, 96)
                bo = o.modifiers.new('Scye', 'BOOLEAN'); bo.operation = 'DIFFERENCE'; bo.solver = 'EXACT'; bo.object = cut
                bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier=bo.name)
                bpy.data.objects.remove(cut, do_unlink=True)
            # the exact cut on an open surface can leave sliver faces reaching across the opening: the loft's own faces are about
            # 3 cm across, so any face with an edge over 8 cm is such a sliver and goes
            bm = bmesh.new(); bm.from_mesh(o.data)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=.0008)
            bmesh.ops.dissolve_degenerate(bm, dist=.0008, edges=bm.edges)
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if max(e.calc_length() for e in f.edges) > .08 or f.calc_area() < 2e-7], context='FACES')
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS'); bm.to_mesh(o.data); bm.free()
        if solid:
            so = o.modifiers.new('Shell', 'SOLIDIFY'); so.thickness = solid; so.offset = 1.0; so.use_even_offset = True; so.use_rim = True
            so.solidify_mode = 'NON_MANIFOLD'; so.nonmanifold_thickness_mode = 'CONSTRAINTS'   # no spikes at the corners of a cut edge
        return put(o, system, job, B3, rig)
    hut = build(f'EVA_{KEY}_Torso_Shell', {'hut'}, M['hut'], P['hut_shell_m'], 'suit',
                'rigid rear-entry composite torso: pressure shell, load path for the life-support hatch and the drone dock; shoulder yoke '
                'flows into the integral helmet')
    helm = build(f'EVA_{KEY}_Helmet_Shell', {'helmet'}, M['hut'], .006, 'helmet',
                 'integral helmet (bonded to the torso, rear entry): superellipsoid sized to the swept head plus 22 mm')
    visor = build(f'EVA_{KEY}_Visor', {'visor'}, M['visor'], .003, 'helmet',
                  'panoramic pressure visor (polycarbonate, inner anti-fog / thermal coat), set inside the structural frame')
    visor.modifiers['Shell'].offset = -1.0
    brow = build(f'EVA_{KEY}_Helmet_Brow', {'brow'}, M['graphite'], .012, 'helmet',
                 'brow structure: carries the visor frame load, the work lights and cameras in protected recesses, and the retracted sunshade')
    # visor frame: the boundary of the window, a graphite structural rim (the visor's integrated frame)
    win = [faces[i] for i, kd in enumerate(kind) if kd == 'visor']
    ec = {}
    for fa in win:
        for e in zip(fa, fa[1:]+fa[:1]):
            kk = tuple(sorted(e)); ec[kk] = ec.get(kk, 0)+1
    bnd = [e for e, cnt in ec.items() if cnt == 1]; nbr = {}
    for a_, b_ in bnd:
        nbr.setdefault(a_, []).append(b_); nbr.setdefault(b_, []).append(a_)
    loop = [bnd[0][0]]; prev = None
    while True:
        nx = [q for q in nbr[loop[-1]] if q != prev]
        if not nx or nx[0] == loop[0]:
            break
        prev = loop[-1]; loop.append(nx[0])
    hcv = Vector((0, hc.y, hc.z))
    fr = [verts[q]+(verts[q]-hcv).normalized()*.004 for q in loop]; fr.append(fr[0])
    put(tube_path(f'EVA_{KEY}_Visor_Frame', fr, .0055, M['graphite'], 10), 'helmet', 'visor structural frame: titanium-composite rim bonded to the shell', B3, rig)
    # helmet-to-torso bond seam and the waist seal (slim metal bands)
    def band(nm, k_, rr, mt, job, bone=B3, push=.007):
        z, a, bf, bb, yc, ex = rings[k_]; pts_ = ring(z, a+push, bf+push, bb+push, yc, ex, 64); pts_.append(pts_[0])
        return put(tube_path(nm, pts_, rr, mt, 8), 'suit', job, bone, rig)
    # neck ring: the helmet is not bonded but seated on a machined ring at the top of the yoke (dual O-ring face seal, a locking collar
    # above it). It is a service joint, not a donning disconnect (entry is through the rear hatch); the head moves inside the torso-fixed
    # helmet, so the neck needs no flexible joint: the yoke rises to the ring as one rigid loft
    NR = P['neck_ring']; z, a, bf, bb, yc, ex = rings[k_hb]
    for nm_, dz, push, rr_, job_ in (('Neck_Ring', 0.0, .004, NR['section_m'][1], 'neck ring: helmet-to-yoke flange, dual O-ring face seal (pressure joint)'),
                                     ('Neck_Ring_Collar', NR['section_m'][0]*.7, .007, NR['collar_m'], 'neck-ring locking collar (service, not donning)')):
        z_ = ring_at(rings, z+dz); pts_ = ring(z+dz, z_[1]+push, z_[2]+push, z_[3]+push, z_[4], z_[5], 72); pts_.append(pts_[0])
        put(tube_path(f'EVA_{KEY}_{nm_}', pts_, rr_, M['metal'] if nm_ == 'Neck_Ring' else M['joint_hw'], 10), 'helmet', job_, B3, rig)
    # cuirass edge: the rolled graphite rim along the torso shell's lower boundary (back hem and the abdominal arch); the same edge
    # treatment as the visor frame and the drone's panel edges
    def at_scye(lp):                                                 # the scye boss's own edges (its seat carries the bearing)
        return any(all(((q-cc)-(b_-a_).normalized()*(q-cc).dot((b_-a_).normalized())).length < rr+.09 for q in lp) for a_, b_, cc, rr in scye.values())
    for li in boundary_loops(hut, indices=True):
        if min(hut.data.vertices[q].co.z for q in li) < z_arch_top-.03 and not at_scye([hut.data.vertices[q].co for q in li]):
            smooth_loop(hut, li)
    for k_, lp in enumerate(boundary_loops(hut)):
        if min(q.z for q in lp) < z_arch_top-.03 and not at_scye(lp):
            lp = lp+[lp[0]]
            put(tube_path(f'EVA_{KEY}_Cuirass_Edge_{k_}', [q+(q-Vector((0, ring_at(rings, q.z)[4], q.z))).normalized()*.003 for q in lp], .0048,
                          M['graphite'], 8), 'frame', 'cuirass edge: rolled rim of the rigid torso around the flexible abdomen and the back hem', B3, rig)
    # work lights and cameras in the brow recesses; peripheral status lights inside the helmet
    def on_helmet(az, el, lift=0.0):
        d = Vector((math.sin(math.radians(az))*math.cos(math.radians(el)), -math.cos(math.radians(az))*math.cos(math.radians(el)), math.sin(math.radians(el))))
        A3 = (ax[0], ax[1] if d.y < 0 else ax[3], ax[2])
        r_ = sum(abs(d[i])**n for i in range(3))**(-1/n); q = Vector((d.x*A3[0]*r_, d.y*A3[1]*r_, d.z*A3[2]*r_))
        g = Vector([n*abs(q[i]/A3[i])**(n-1)*math.copysign(1, q[i])/A3[i] for i in range(3)]).normalized()
        return hc+q+g*lift, g
    el_b = el_ctr(0)+P['visor']['el_half_deg']+9
    for sx, side in ((1, 'P'), (-1, 'S')):
        p, g = on_helmet(sx*44, el_b, .012)
        put(cyl(f'SENS_Helmet_Light_{side}', p-g*.004, p+g*.0015, .011, M['lens_light'], 24), 'helmet', 'work light (flush lens in the brow recess)', B3, rig)
        p, g = on_helmet(sx*16, el_b, .012)
        put(cyl(f'SENS_Helmet_Cam_{side}', p-g*.004, p+g*.001, .0065, M['lens'], 20), 'sensor', 'helmet camera (stereo pair, flush)', B3, rig)
        p, g = on_helmet(sx*58, -12, -.012)
        put(bx(f'SENS_Helmet_Status_{side}', p, (.004, .003, .003), M['cyan'], axes=frame3(g)), 'helmet',
            'in-helmet peripheral status light (drone link, gas, latch)', B3, rig)
    # service crest: a low graphite rib from the brow over the crown to the back; it carries the visor-frame load into the torso and
    # the harness of the brow lights and cameras to the hatch; its front end holds the forward work camera and a spot light
    cr = [on_helmet(0, el, .0045)[0] for el in lin(el_b+3, 88, 12)]+[on_helmet(180, el, .0045)[0] for el in lin(88, -38, 22)]
    put(tube_path(f'EVA_{KEY}_Helmet_Crest', cr, P['crest']['width_m']/4, M['graphite'], 10), 'helmet',
        'service crest: structural rib and harness run (brow lights and cameras to the hatch)', B3, rig)
    p, g = on_helmet(0, el_b+4, .012)
    put(cyl('SENS_Helmet_Crest_Cam', p-g*.004, p+g*.0012, .0058, M['lens'], 20), 'sensor', 'forward work camera at the crest root', B3, rig)
    p, g = on_helmet(180, 38, .0)
    put(bx('SENS_Helmet_Comms_Patch', p+g*.0045, (.035, .025, .0015), M['graphite'], axes=(Vector((1, 0, 0)), g.cross(Vector((1, 0, 0))), g), bevel=.001), 'sensor',
        'conformal comms antenna patch (suit-drone-ship link) under the shell skin', B3, rig)
    # sunshade: retracted into the brow (a thin gold edge shows); deployable over the visor
    sun = [faces[i] for i, kd in enumerate(kind) if kd == 'brow']
    used = sorted({q for fa in sun for q in fa}); remap = {q: j for j, q in enumerate(used)}
    so = mesh(f'EVA_{KEY}_Sunshade_Retracted', [verts[q]+(verts[q]-hcv).normalized()*.0035 for q in used], [tuple(remap[q] for q in fa) for fa in sun], M['visor_tint'])
    put(so, 'helmet', 'gold sunshade, retracted inside the brow structure (shown stowed; deployment not rigged)', B3, rig)
    # ---- bearings (low profile), gauntlets, joints
    def bearing(nm, bone_axis, t, parent, minor, mt=None, q=.80, job='low-profile rotary bearing'):
        a_, b_ = W(bone_axis); cc, rr = section(pts({bone_axis}), a_, b_, max(0, t-.05), min(1, t+.05), q); rr = rr or .06
        put(ring_torus(f'EVA_{KEY}_{nm}', cc, b_-a_, rr+minor*.15, minor, mt or M['joint_hw'], m=12, section=(.50, 1.0)), 'suit', job, parent, rig)
        put(tube(f'EVA_{KEY}_{nm}_Sleeve', cc-(b_-a_).normalized()*minor*.9, cc+(b_-a_).normalized()*minor*.9, rr-.001, M['joint'], n=32), 'suit',
            'restraint attachment sleeve', parent, rig)
        return cc, rr
    info = dict(rings=rings, k_hb=k_hb, hc=hc, ax=ax, n=n, inner=inner, head_sweep=sweep, z0=z0, zs=zs, outer=outer, hut=hut, helmet=helm,
                visor=visor, brow=brow, odom=odom, layers=layers)
    # the soft outer layer ends at the rigid torso: its faces enclosed by the torso shell and helmet are removed (no hidden double skin)
    def inside_loft(p):
        if p.z < z0+.015 or in_scye(p) or below_arch(p):
            return False
        z, a, bf, bb, yc, ex = ring_at(rings, p.z); b = bb if p.y > yc else bf
        return (abs(p.x)/a)**ex+(abs(p.y-yc)/b)**ex < 1.0
    bm = bmesh.new(); bm.from_mesh(outer.data); bm.faces.ensure_lookup_table()
    dom0 = dominant(outer)
    gone = [f for f in bm.faces if all(inside_loft(v.co) for v in f.verts) or
            max(set(ds := [dom0[v.index] for v in f.verts]), key=ds.count) in ('neck_01', 'head')]
    bmesh.ops.delete(bm, geom=gone, context='FACES')
    bm.to_mesh(outer.data); bm.free(); outer.data.update()
    # the soft layer ends where the rigid shell begins: every face the built torso shell (solid wall, exact scye openings) passes through
    # is removed, and with it any fabric islands left enclosed, so no fabric runs inside the wall (fix 4.2: no hidden intersection)
    dg = bpy.context.evaluated_depsgraph_get(); he = hut.evaluated_get(dg); hm = he.to_mesh()
    Hb = BVHTree.FromPolygons([he.matrix_world @ v.co for v in hm.vertices], [list(q.vertices) for q in hm.polygons]); he.to_mesh_clear()
    me = outer.data; mw = outer.matrix_world
    Ob = BVHTree.FromPolygons([mw @ v.co for v in me.vertices], [list(q.vertices) for q in me.polygons])
    cut = {j_ for _, j_ in Hb.overlap(Ob)}
    # and the fabric within 4 mm of the shell: the seam allowance under the rolled edge, so a bending waist does not push into the rim
    cut = sorted(cut | {q.index for q in me.polygons if Hb.find_nearest(mw @ q.center)[3] < .004})
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[j_] for j_ in cut], context='FACES')
    bm.faces.index_update(); seen = set(); islands = []
    for f0 in bm.faces:
        if f0.index in seen:
            continue
        isl = []; stack = [f0]; seen.add(f0.index)
        while stack:
            f1 = stack.pop(); isl.append(f1)
            for e1 in f1.edges:
                for f2 in e1.link_faces:
                    if f2.index not in seen:
                        seen.add(f2.index); stack.append(f2)
        islands.append(isl)
    crumbs = [f1 for isl in islands if len(isl) < 80 for f1 in isl]
    bmesh.ops.delete(bm, geom=crumbs, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    # rigid-to-soft at the shoulder: the arm fabric from the scye bearing to the upper-arm bearing is replaced by the shoulder convolute
    # (scye_sleeves); the side and yoke fabric inboard of the bearing plane (up to 9 cm outside the ring) and round the armpit is stitched
    # to the cuirass rim and follows only the torso
    dl = bm.verts.layers.deform.verify(); g3 = outer.vertex_groups[B3].index; ramp = .02; RACE = 0.0; RIM = .08   # the sleeve replaces the arm fabric over the race
    held = 0; shapes = [bm.verts.layers.shape[k_] for k_ in bm.verts.layers.shape.keys() if k_.startswith('corrective_')]
    for v in bm.verts:
        p = mw @ v.co
        rim0 = v[dl].get(g3, 0.0) >= .5; rim = rim0 and Hb.find_nearest(p)[3] < .03      # torso fabric at the cuirass rim
        for s in 'lr':
            a_, b_, cc, rr = scye[s]; u = (b_-a_).normalized(); t = (p-cc).dot(u); d = ((p-cc)-u*t).length
            rim = rim or (rim0 and t < RIM and d < rr+.12)                                # torso fabric round the armpit
            if (t < ramp+RACE and d < rr+.05) or (t < 0.0 and d < rr+.09) or rim:
                # inboard of the bearing plane (t < 0), or torso fabric beside the cuirass rim: fully on the torso, and the body
                # correctives (which bulge the unsuited deltoid, waist, hips) do not move fabric that is stitched to the rigid shell
                w = 0.0 if rim else smoothstep(max(0.0, min(1.0, (t-RACE)/ramp)))
                for L in shapes:
                    v[L] = v.co+(v[L]-v.co)*w
                old = {k_: v[dl][k_] for k_ in v[dl].keys()}
                v[dl].clear()
                for k_, x_ in old.items():
                    if k_ != g3 and x_*w > 1e-4:
                        v[dl][k_] = x_*w
                v[dl][g3] = old.get(g3, 0.0)*w+(1.0-w); held += 1
                break
    bm.to_mesh(outer.data); bm.free(); outer.data.update()
    info['scye_sleeves'] = scye_sleeves(rig, outer, scye, M)
    info['cuirass_seal'] = cuirass_seal(rig, outer, hut, scye, M)
    info['outer_cut_faces'] = len(cut); info['outer_crumb_faces'] = len(crumbs); info['outer_scye_held_verts'] = held
    odom = dominant(outer); info['odom'] = odom; info['outer_trimmed_faces'] = len(gone)
    e_ = .008; st = lambda a, b, x: smoothstep(max(0.0, min(1.0, (x-a)/(b-a))))
    flex = []
    for v, d0 in zip(outer.data.vertices, odom):
        p = v.co; w = 1.0-st(.075-e_, .075+e_, (p-crotch).length)
        for bs, a_, d_, lo, hi in bands:
            if d0 in bs:
                t = (p-a_).dot(d_); w = max(w, st(lo-e_, lo+e_, t)*(1.0-st(hi-e_, hi+e_, t)))
        if p.y < 0 and z0-.07 < p.z < z_arch_top and below_arch(Vector((p.x, p.y-.02, max(p.z, z0+.002)))):
            w = max(w, st(z0-.07, z0-.04, p.z))                        # the flexible abdomen under the arch: dark restraint fabric
        flex.append(w)
    outer_zones(outer, rig, M, odom, data['palette'], flex)
    info['arch'] = info_arch
    restraint_lines(rig, outer, odom, M)
    info['scye_housing'] = scye_housing(rig, scye, M, P['hut_shell_m'])
    for s in 'lr':
        a_, b_, cc, rr = scye[s]
        put(ring_torus(f'EVA_{KEY}_Scye_Bearing_{s}', cc, b_-a_, rr+SCYE_GAP, P['scye_minor_m'], M['joint_hw'], m=12, section=(.40, 1.0)), 'suit',
            'scye bearing in the torso shell (shoulder rotation)', B3, rig)
        bearing(f'Upperarm_Bearing_{s}', f'upperarm_{s}', P['scye_sleeve']['end_t'], f'upperarm_{s}', P['bearing_minor_m'], job='upper-arm bearing (humeral rotation)')
        cw, rw = bearing(f'Wrist_Disconnect_{s}', f'lowerarm_{s}', .95, f'lowerarm_{s}', P['wrist_minor_m'], M['metal'],
                         job='glove wrist disconnect and bearing')
        a_, b_ = W(f'lowerarm_{s}'); d = (b_-a_).normalized()
        put(tube(f'EVA_{KEY}_Gauntlet_{s}', b_-d*.05, b_-d*.012, rw+.004, M['graphite'], r_b=rw+.010), 'frame',
            'gauntlet cuff: thermal / MMOD cover over the wrist disconnect', f'lowerarm_{s}', rig)
        bearing(f'Ankle_Bearing_{s}', f'calf_{s}', .88, f'calf_{s}', P['bearing_minor_m'], job='ankle bearing and boot seal')
        # protective structures (graphite composite plates on the restraint)
        def plate(nm, bone_, t, face, arc, half, lift=.003, job='protective plate'):
            a_, b_ = W(bone_); cc, rr = section(pts({bone_}), a_, b_, max(0, t-.08), min(1, t+.08), .9)
            pad(_S, KEY, f'{nm}_{s}', a_, b_, cc, rr+lift, face, arc, half, bone_, M['graphite'], job, t=.0045)
        plate('Knee_Cap', f'calf_{s}', .06, Vector((0, -1, 0)), 105, .050, .004, 'knee cap: kneeling and restraint contact')
        plate('Shin_Guard', f'calf_{s}', .45, Vector((0, -1, 0)), 85, .110, .003, 'shin guard: MMOD and abrasion')
        plate('Elbow_Cap', f'lowerarm_{s}', .05, Vector((0, 1, 0)), 100, .040, .004, 'elbow cap')
        # arm identification band (role colour)
        a_, b_ = W(f'upperarm_{s}'); cc, rr = section(pts({f'upperarm_{s}'}), a_, b_, .70, .78)
        put(ring_torus(f'EVA_{KEY}_Arm_Band_{s}', cc, b_-a_, rr+.002, .0035, M['band'], m=6, n=40), 'suit', 'identification band (role colour)', f'upperarm_{s}', rig)
        # integrated boots: rigid heel/arch shell and toe cap, both hulls of the outer layer's foot plus a sole band
        boot(rig, outer, odom, s, M)
    return info


SCYE_GAP = .018                  # the scye bearing seat: the arm root's outer-layer radius plus this
BOSS_L = .06                     # scye housing length inboard of the bearing seat


def housing_profile(R):
    """The scye housing's inner surface [(t along the arm axis from the bearing seat, radius)]: a flare from the seat inboard."""
    return [(0.0, R), (-.012, R+.002), (-.035, R+.010), (-BOSS_L, R+.024)]


def scye_housing(rig, scye, M, wall):
    """The scye housing (fix 2.2): a rigid flared collar bolted to the torso shell round each scye opening. Its narrow end is the round
    planar seat of the scye bearing (the arm root's section plus SCYE_GAP); it flares inboard to overlap the shell round the cut, so
    shell, bearing and shoulder convolute form one sealed chain without a gap at the opening's edge."""
    out = {}
    for s, (a_, b_, cc, rr) in scye.items():
        u = (b_-a_).normalized(); R = rr+SCYE_GAP
        prof = [(t, r_+wall) for t, r_ in housing_profile(R)]
        o = lathe(f'EVA_{KEY}_Scye_Housing_{s}', cc, u, prof, M['hut'], 96, close_start=False, close_end=False)
        sh = o.modifiers.new('Shell', 'SOLIDIFY'); sh.thickness = wall; sh.offset = 1.0; sh.use_even_offset = True; sh.use_rim = True
        for p in o.data.polygons:
            p.use_smooth = True
        put(o, 'suit', 'scye housing: rigid collar bolted to the torso shell, the scye bearing seat (pressure joint)', B3, rig)
        out[s] = dict(seat_radius_m=round(R, 4), flare_radius_m=round(R+.024, 4), length_m=BOSS_L)
    return out


def scye_sleeves(rig, outer, scye, M):
    """The shoulder convolute (fix 2.2): a pressure-bearing sleeve from the scye bearing in the cuirass to the upper-arm bearing. Its root
    ring is sealed to the bearing and rides the torso; its rings hand over to the upper arm along its length (a bellows that bends with
    the shoulder), with restraint ribs every convolute. It replaces the soft outer layer over that span (those faces are removed: no
    double skin), so the arm's root always moves inside a modelled pressure wall. Returns the sleeve dimensions per side."""
    P = ev.SUIT['scye_sleeve']; out = {}; W = lambda b: bone(rig, b)
    me = outer.data; mw = outer.matrix_world; odom = dominant(outer); kill = set()
    for s in 'lr':
        a_, b_, cc, rr = scye[s]; n_ = (b_-a_).normalized()                # the scye (design) axis
        ua, ub = W(f'upperarm_{s}'); u = (ub-ua).normalized()                # the upper arm at rest
        arm = [mw @ v.co for v, d in zip(me.vertices, odom) if d in (f'upperarm_{s}', f'clavicle_{s}')]
        c1, r1 = section([q for q in arm if True], ua, ub, P['end_t']-.05, P['end_t']+.05, .80)
        # the convolute's centre line: a cubic from the scye seat (leaving along the scye axis) to the upper-arm bearing (along the arm)
        h = (c1-cc).length*.45; B = (cc, cc+n_*h, c1-u*h, c1)
        bez = lambda f: B[0]*(1-f)**3+B[1]*3*f*(1-f)**2+B[2]*3*f*f*(1-f)+B[3]*f**3
        tan = lambda f: ((B[1]-B[0])*3*(1-f)**2+(B[2]-B[1])*6*f*(1-f)+(B[3]-B[2])*3*f*f).normalized()
        K = 2*P['convolutes']+1; N = 48; verts = []; faces = []; wts = []; radii = []; cents = []
        x, y, _ = frame_from(n_)
        for k in range(K):
            f = k/(K-1); c = bez(f); tg = tan(f)
            q_ = n_.rotation_difference(tg); xk = q_ @ x; yk = q_ @ y        # the seat frame carried along the curve
            near = [((p-c)-tg*(p-c).dot(tg)).length for p in arm if abs((p-c).dot(tg)) < .01 and (p-c).length < .2]
            # tapering from the bearing seat to the upper-arm bearing, never closer than the clearance to the outer layer
            r_ = max(max(near, default=0.0)+P['clearance_m'], (rr+SCYE_GAP)*(1-f)+(r1+.006)*f) if f > 0 else rr+SCYE_GAP
            rib = P['rib_m'] if k % 2 == 1 else 0.0                     # a restraint rib every other ring
            radii.append(r_); cents.append(c)
            for i in range(N):
                th = 2*math.pi*i/N; verts.append(c+(xk*math.cos(th)+yk*math.sin(th))*(r_+rib))
            wts.append(smoothstep(min(1.0, f/.18)))              # torso-fixed at the bearing seat, then turning with the upper arm (the bearing rotates)
        for k in range(K-1):
            for i in range(N):
                faces.append((k*N+i, k*N+(i+1) % N, (k+1)*N+(i+1) % N, (k+1)*N+i))
        o = new_mesh(f'EVA_{KEY}_Scye_Sleeve_{s}', verts, faces, M['joint'])
        g0 = o.vertex_groups.new(name=B3); g1 = o.vertex_groups.new(name=f'upperarm_{s}')
        for k, w in enumerate(wts):
            ids = list(range(k*N, (k+1)*N))
            if w < 1.0:
                g0.add(ids, 1.0-w, 'REPLACE')
            if w > 0.0:
                g1.add(ids, w, 'REPLACE')
        so = o.modifiers.new('Shell', 'SOLIDIFY'); so.thickness = .004; so.offset = 1.0
        am = o.modifiers.new('Armature', 'ARMATURE'); am.object = rig
        put(o, 'suit', 'shoulder convolute: pressure-bearing sleeve from the scye bearing to the upper-arm bearing (restraint ribs)', parent=rig)
        # the outer-layer faces enclosed by the sleeve (rest pose) are removed; the sleeve overlaps the remaining fabric under the bearing
        def enclosed_(p):
            if (p-cc).dot(n_) < -.004 or (p-c1).dot(u) > -.012:
                return False
            k = min(range(K), key=lambda j: (p-cents[j]).length)
            return (p-cents[k]).length < radii[k]+.03
        for q in me.polygons:
            if all(enclosed_(mw @ me.vertices[vi].co) for vi in q.vertices):
                kill.add(q.index)
        out[s] = dict(length_m=round(sum((cents[j+1]-cents[j]).length for j in range(K-1)), 3), root_radius_m=round(rr+SCYE_GAP, 3), end_radius_m=round(r1+P['clearance_m'], 3), rings=K)
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[j] for j in sorted(kill)], context='FACES')
    bm.faces.ensure_lookup_table(); seen = set(); crumbs = []
    for f0 in bm.faces:                                          # fabric islands left between the sleeve and the cuirass rim
        if f0 in seen:
            continue
        isl = []; stack = [f0]; seen.add(f0)
        while stack:
            f1 = stack.pop(); isl.append(f1)
            for e1 in f1.edges:
                for f2 in e1.link_faces:
                    if f2 not in seen:
                        seen.add(f2); stack.append(f2)
        if len(isl) < 80:
            crumbs += isl
    bmesh.ops.delete(bm, geom=crumbs, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(me); bm.free(); me.update()
    out['outer_faces_replaced'] = len(kill); out['outer_crumb_faces'] = len(crumbs)
    return out


def cuirass_seal(rig, outer, hut, scye, M):
    """The bladder-to-cuirass clamp skirt: where the soft layer ends at the rigid torso (the abdominal arch, the back hem, the yoke under
    the helmet) its cut edge is carried to the shell's inner face by a pressure-bearing skirt, the bladder flange that a clamp ring holds
    against the cuirass. The fabric edge rides the body (it copies the fabric's skin weights); the clamp edge sits 2.5 mm into the shell wall
    and follows the torso. The scye openings have their own sleeves and are skipped. Returns the skirt's loop and vertex counts."""
    sh = [m for m in hut.modifiers if m.type == 'SOLIDIFY']                # the shell's base sheet (its wall grows outward from it)
    for m in sh:
        m.show_viewport = False
    dg = bpy.context.evaluated_depsgraph_get(); he = hut.evaluated_get(dg); hm = he.to_mesh()
    Hb = BVHTree.FromPolygons([he.matrix_world @ v.co for v in hm.vertices], [list(q.vertices) for q in hm.polygons]); he.to_mesh_clear()
    for m in sh:
        m.show_viewport = True
    me = outer.data; mw = outer.matrix_world; gn = {g.index: g.name for g in outer.vertex_groups}
    def near_scye(p):
        return any(((p-cc)-(b_-a_).normalized()*(p-cc).dot((b_-a_).normalized())).length < rr+.05 and (p-cc).dot((b_-a_).normalized()) > -.04
                   for a_, b_, cc, rr in scye.values())
    verts = []; faces = []; wts = []; loops = 0
    for lp in boundary_loops(outer, indices=True):
        idx = []
        for q in lp:
            p = mw @ me.vertices[q].co; h = Hb.find_nearest(p)
            if h[0] is None or h[3] > .035 or near_scye(p):
                idx.append(None); continue
            d = (h[0]-p); tip = h[0]+d.normalized()*.0025 if d.length > 1e-6 else p
            verts += [p, tip]; wts.append({gn[g.group]: g.weight for g in me.vertices[q].groups if gn.get(g.group) in rig.data.bones})
            idx.append(len(verts)-2)
        n_ = len(idx); pairs = [(idx[i], idx[(i+1) % n_]) for i in range(n_) if idx[i] is not None and idx[(i+1) % n_] is not None]
        if pairs:
            faces += [(a, a+1, b+1, b) for a, b in pairs]; loops += 1
    if not faces:
        return dict(loops=0, verts=0)
    o = new_mesh(f'EVA_{KEY}_Cuirass_Seal', verts, faces, M['joint'])
    groups = {}
    def grp(nm):
        if nm not in groups:
            groups[nm] = o.vertex_groups.new(name=nm)
        return groups[nm]
    for k, w in enumerate(wts):
        for nm, x in w.items():
            grp(nm).add([2*k], x, 'REPLACE')
        grp(B3).add([2*k+1], 1.0, 'REPLACE')
    am = o.modifiers.new('Armature', 'ARMATURE'); am.object = rig
    put(o, 'suit', 'bladder-to-cuirass clamp skirt: the soft layer\'s pressure flange carried into the rigid torso\'s clamp ring', parent=rig)
    return dict(loops=loops, verts=len(verts), faces=len(faces))


def restraint_lines(rig, outer, odom, M):
    """Lines of non-extension: two helical cords per limb segment on the outer layer (the visible logic of the patterned restraint that
    lets the limbs bend at nearly constant volume). They run between the joint bands and twist in opposite senses left and right."""
    me = outer.data; bvh = BVHTree.FromPolygons([v.co for v in me.vertices], [list(p.vertices) for p in me.polygons])
    for s, sg in (('l', 1), ('r', -1)):
        for bone_, t0, t1, tw in (('upperarm', .16, .80, 70), ('lowerarm', .22, .78, -70), ('thigh', .16, .80, 60), ('calf', .20, .78, -60)):
            a_, b_ = bone(rig, f'{bone_}_{s}'); d = (b_-a_); L_ = d.length; d.normalize()
            ref = d.orthogonal().normalized()
            for k, ph0 in enumerate((0.0, 180.0)):
                pts = []
                for i in range(18):
                    t = t0+(t1-t0)*i/17; ph = math.radians(ph0+sg*tw*(t-t0)/(t1-t0)+(35 if bone_ in ('thigh', 'calf') else 90))
                    r_ = Matrix.Rotation(ph, 3, d) @ ref; o_ = a_+d*(t*L_)
                    hit = bvh.ray_cast(o_, r_, .25)
                    if hit[0] is not None:
                        pts.append(hit[0]+hit[1]*.0016)
                if len(pts) > 6:
                    put(tube_path(f'EVA_{KEY}_Restraint_Line_{bone_}_{s}_{k}', pts, .0013, M['joint_hw'], 6), 'suit',
                        'line of non-extension (restraint cord): keeps the limb length and volume constant in flexion', f'{bone_}_{s}', rig)


def boot(rig, outer, odom, s, M):
    for b, nm, job in ((f'foot_{s}', 'Boot_Shell', 'integrated boot: rigid heel counter and arch, sole band, heel fitting'),
                       (f'ball_{s}', 'Boot_Toe', 'boot toe section: flexes at the ball joint; toe hook for foot restraints')):
        pts = [v.co+v.normal*.004 for v, d in zip(outer.data.vertices, odom) if d == b]
        lo = min(p.z for p in pts); pts += [Vector((p.x, p.y, max(0.0, lo-.006))) for p in pts if p.z < lo+.03]
        bm = bmesh.new()
        for q in pts:
            bm.verts.new(q)
        bmesh.ops.convex_hull(bm, input=bm.verts); bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        me = bpy.data.meshes.new(f'EVA_{KEY}_{nm}_{s}'); bm.to_mesh(me); bm.free(); me.materials.append(M['graphite']); me.materials.append(M['sole'])
        for p in me.polygons:
            p.use_smooth = True; p.material_index = 1 if p.center.z < lo+.016 else 0
        o = link(bpy.data.objects.new(me.name, me)); sub = o.modifiers.new('Smooth', 'SUBSURF'); sub.levels = 1; sub.render_levels = 2
        put(o, 'frame', job, b, rig)
    fa, fb = bone(rig, f'foot_{s}'); ba, bb = bone(rig, f'ball_{s}')
    fd = Vector((bb.x-fa.x, bb.y-fa.y, 0)).normalized(); side = fd.cross(Vector((0, 0, 1)))
    hk = Vector((bb.x, bb.y, .045))+fd*.035
    put(cyl(f'EVA_{KEY}_Toe_Hook_{s}', hk-side*.035, hk+side*.035, .0045, M['metal'], 12), 'frame', 'toe hook bar (foot restraint)', f'ball_{s}', rig)
    heel = Vector((fa.x, fa.y, .05))-fd*.075
    put(bx(f'EVA_{KEY}_Heel_Fitting_{s}', heel, (.022, .006, .012), M['metal'], axes=(side, fd, Vector((0, 0, 1))), bevel=.002), 'frame',
        'heel fitting: foot-restraint clip', f'foot_{s}', rig)


# ---------------------------------------------------------------------------------------------------------------------- torso helpers
def ring_at(rings, z):
    """Interpolated section parameters at height z (clamped to the loft's range)."""
    if z <= rings[0][0]:
        return rings[0]
    for r0, r1 in zip(rings, rings[1:]):
        if r0[0] <= z <= r1[0]:
            t = (z-r0[0])/max(1e-9, r1[0]-r0[0]); return tuple(a+(b-a)*t for a, b in zip(r0, r1))
    return rings[-1]


def torso_y(rings, x, z, back=True, push=0.0):
    zz, a, bf, bb, yc, ex = ring_at(rings, z); a += push; b = (bb if back else bf)+push
    if abs(x) >= a:
        return yc
    return yc+(1 if back else -1)*b*(1-abs(x/a)**ex)**(1/ex)


# ---------------------------------------------------------------------------------------------------------------------- life support
def life_support(rig, info, M):
    """The rear-entry hatch / life-support module: its front follows the torso back, its rear is a gentle convex cylinder that the drone's
    dock face mirrors; a recessed dock channel runs down its centre. Four thruster clusters sit in its corners."""
    P = ev.SUIT; w, dpt, h = P['plss_size_m']; rings = info['rings']; push = P['hut_shell_m']+.002
    top = info['zs']+.095; bot = top-h; zc = (top+bot)/2
    yb = max(torso_y(rings, x, z, True, push) for x in lin(-w/2, w/2, 9) for z in lin(info['z0'], top, 12))
    y_r0 = yb+dpt                                     # rear face at the centre line
    bulge = P['plss_rear_bulge_m']
    y_rear = lambda x: y_r0-bulge*(x/(w/2))**2
    hw = lambda v: ev.plss_halfwidth(v)
    ch_ = P['channel']; cwh = ch_['width_m']/2; cu = cwh/(w/2*.97)
    keel = ev.DRONE['keel']; zk0 = zc-.025-keel['length_m']/2-.012; zk1 = zc-.025+keel['length_m']/2+.012
    vk0, vk1 = (zk0-bot)/h, (zk1-bot)/h
    us = merged(lin(-1, 1, 25), [-cu, cu]); vs = merged(lin(0, 1, 31), [vk0, vk1])
    def xz(u, v):
        return u*hw(v)*(1.0 if .10 <= v <= .86 else 1.0), bot+v*h
    backpts = [v.co.copy() for v, d in zip(info['outer'].data.vertices, info['odom']) if d in ('spine_01', 'spine_02', 'spine_03', 'pelvis', 'thigh_l', 'thigh_r',
                                                                                              'clavicle_l', 'clavicle_r', 'neck_01') and v.co.y > 0]
    memo = {}
    def y_front(x, z):
        key = (round(x, 4), round(z, 4))
        if key not in memo:
            zz, a, bf, bb, yc, ex = ring_at(rings, z)
            low = z < bot+.06                                         # over the seat the buttocks bulge below: a wider window, more margin
            near = [p.y for p in backpts if abs(p.x-x) < (.05 if low else .035) and abs(p.z-z) < (.06 if low else .03)]
            y = torso_y(rings, x, z, True, push) if z >= info['z0'] else -1.0
            if near:
                y = max(y, max(near)+(.020 if low else .012))
            memo[key] = max(y, yc+.45*(bb+push)) if z >= info['z0'] else max(y, yc)
        return memo[key]
    def y_back(x, z, u, v):
        e = (1-abs(u)**6)**(1/6)*(1-abs(2*v-1)**10)**(1/10); yf = y_front(x, z)
        return yf+(y_rear(x)-yf)*(.40+.60*e)
    mod = grid_shell(f'LS_{KEY}_Module', us, vs, xz, y_front, y_back, M['hut'])
    # cut the channel opening (the faces between the channel edges and ends on the rear face) and line it
    bm = bmesh.new(); bm.from_mesh(mod.data)
    cut = [f for f in bm.faces if abs(f.calc_center_median().x) < cwh-1e-4 and zk0+1e-4 < f.calc_center_median().z < zk1-1e-4 and f.normal.y > .3]
    bmesh.ops.delete(bm, geom=cut, context='FACES'); bm.to_mesh(mod.data); bm.free()
    put(mod, 'life', 'life-support module = the rear-entry hatch: O2, CO2 / humidity swing bed, membrane evaporator, fan / pump, battery, '
        'radio, the N2 reserve and the suit manifold (packaging: data/eva_suit.toml [module]); its frame carries the drone dock into the torso shell', B3, rig)
    dep = ch_['depth_m']; dr = math.tan(math.radians(ch_['draft_deg']))*dep; yr_c = y_rear(cwh)
    sec = [Vector((-cwh, yr_c+.0005, 0)), Vector((-cwh+dr, yr_c-dep, 0)), Vector((cwh-dr, yr_c-dep, 0)), Vector((cwh, yr_c+.0005, 0))]
    zn_ = zc-.025-keel['length_m']/2+.045; ze_ = zc-.025+keel['length_m']/2-.03
    cuts = [zk0, zn_-.0135, zn_+.0135, ze_-.0085, ze_+.0085, zk1]
    lv = []; lf = []
    for z in cuts:
        lv += [Vector((p.x, p.y, z)) for p in sec]
    for k_ in range(len(cuts)-1):
        o_ = 4*k_
        lf += [(o_, o_+4, o_+5, o_+1), (o_+2, o_+6, o_+7, o_+3)]
        if k_ % 2 == 0:
            lf.append((o_+1, o_+5, o_+6, o_+2))                       # floor (open at the two receptacles)
    lf += [(0, 1, 2, 3), (4*(len(cuts)-1), 4*(len(cuts)-1)+3, 4*(len(cuts)-1)+2, 4*(len(cuts)-1)+1)]
    liner = mesh(f'DOCK_{KEY}_Suit_Channel', lv, lf, M['dockmetal'], smooth=False)
    so = liner.modifiers.new('Wall', 'SOLIDIFY'); so.thickness = .002; so.offset = 1.0
    put(liner, 'dock', f'dock channel: drafted {ch_["draft_deg"]:.0f} deg walls guide the drone keel in (capture +-'
        f'{(cwh-keel["width_m"]/2)*1000:.0f} mm at the mouth); hard-anodised wear liner', B3, rig)
    out = dict(top=top, bot=bot, zc=zc, w=w, dpt=dpt, h=h, y_rear=y_rear, y_r0=y_r0, cwh=cwh, dep=dep, zk0=zk0, zk1=zk1, dr=dr, module=mod,
               pc=Vector((0, (yb+y_r0)/2, zc)), y_front=y_front, hw=hw)
    # ---- dock hardware in the channel: latch bolt sockets in both walls, N2 dry-break receptacle, power/data receptacle
    zl_u = zc-.025+keel['length_m']/2-.07; zl_l = zc-.025-keel['length_m']/2+.10
    z_n2 = zc-.025-keel['length_m']/2+.045; z_el = zc-.025+keel['length_m']/2-.03
    yb_mid = yr_c-dep*.55
    for zz, tag in ((zl_u, 'U'), (zl_l, 'L')):
        for sx, side in ((1, 'P'), (-1, 'S')):
            xw = sx*(cwh-dr*.55)
            put(bx(f'DOCK_{KEY}_Suit_Bolt_Socket_{side}{tag}', Vector((xw, yb_mid, zz)), (.0035, .0065, .0085), M['steel'], bevel=.001), 'dock',
                'latch bolt socket: hardened insert in the channel wall; the drone keel\'s bolt shoots into it (carries pull-off and shear loads)', B3, rig)
    rc = Vector((0, yr_c-dep-.0005, z_n2))
    put(lathe(f'DOCK_{KEY}_Suit_N2_Receptacle', rc+Vector((0, .0015, 0)), Vector((0, -1, 0)), [(0, .0135), (.004, .0135), (.004, .0085), (.030, .0085), (.030, .0)],
              M['dockmetal'], 24, False, True), 'dock', 'N2 dry-break receptacle, flush in the channel floor (no gas path without the probe)', B3, rig)
    put(torus(f'DOCK_{KEY}_Suit_N2_Mark', rc+Vector((0, .0012, 0)), Vector((0, 1, 0)), .0155, .0012, M['blue'], 24, 6), 'n2', 'N2 identification ring', B3, rig)
    pop = put(cyl(f'DOCK_{KEY}_Suit_N2_Poppet', rc+Vector((0, -.002, 0)), rc+Vector((0, .0005, 0)), .0080, M['steel'], 20), 'dock',
              'spring-loaded poppet: pushed in 10 mm by the probe while coupled', B3, rig)
    put(bx(f'DOCK_{KEY}_Suit_Power_Receptacle', Vector((0, yr_c-dep-.0005, z_el)), (.012, .0015, .008), M['text'], bevel=.001), 'sensor',
        'blind-mate power / data receptacle (flush, sealed shutter)', B3, rig)
    for zz in (zk0+.004, zk1-.004):
        put(bx(f'DOCK_{KEY}_Suit_Mouth_Mark_{int(zz*1000)}', Vector((0, yr_c+.0008, zz)), (cwh*.9, .0008, .0016), M['yellow']), 'dock',
            'channel mouth alignment mark (the only hazard colour on the dock)', B3, rig)
    out.update(z_n2=z_n2, z_el=z_el, zl_u=zl_u, zl_l=zl_l, poppet=pop, yb_mid=yb_mid)
    # staged dock: the capture tongue at the channel mouth holds the keel nose (soft capture) before the bolts lock; two upper load
    # pads over the shoulder yoke and the keel spread the drone's load; three retroreflectors (asymmetric, so roll is unambiguous) guide
    # the drone's docking cameras during approach and alignment
    cap = put(bx(f'DOCK_{KEY}_Suit_Capture_Tongue', Vector((cwh-dr*.5-.006, yr_c-dep*.45, zk1-.016)), (.006, .006, .010), M['steel'], bevel=.0015), 'dock',
              'capture tongue: spring-loaded, slides across the channel mouth over the keel nose (soft capture), then the bolts lock', B3, rig)
    out['capture'] = cap
    for sx in (1, -1):
        x_ = sx*.115; z_ = zc-.025+.165
        put(cyl(f'DOCK_{KEY}_Suit_Load_Pad_{"P" if sx > 0 else "S"}', Vector((x_, y_rear(x_)-.0015, z_)), Vector((x_, y_rear(x_)+.0010, z_)), .018, M['metal'], 24),
            'dock', 'load pad (titanium): takes the drone\'s upper pads; the load path runs into the shoulder yoke', B3, rig)
    for k_, (x_, z_) in enumerate(((.125, top-.085), (-.125, top-.085), (.125, bot+.10))):
        put(cyl(f'DOCK_{KEY}_Suit_Retro_Target_{k_}', Vector((x_, y_rear(x_)-.001, z_)), Vector((x_, y_rear(x_)+.0012, z_)), .0085, M['lens_light'], 20), 'dock',
            'retroreflector alignment target (read by the drone\'s docking cameras)', B3, rig)
        put(torus(f'DOCK_{KEY}_Suit_Retro_Ring_{k_}', Vector((x_, y_rear(x_)+.0012, z_)), Vector((0, 1, 0)), .0095, .0012, M['graphite'], 20, 6), 'dock',
            'target ring', B3, rig)
    # ---- suit thruster clusters in the module corners
    cl = {}
    for sz, tag, v in ((1, 'U', 1.0-.040/h), (-1, 'L', .040/h)):
        z = bot+v*h
        for sx, side in ((1, 'P'), (-1, 'S')):
            x = sx*(w/2-(.032 if sz > 0 else .042)); y = y_back(x, z, x/(w/2), v)-.020
            cl[f'{tag}{side}'] = ((x, y, z), sx, sz)
    out['clusters'] = cl; nzs = []
    for tag, (c, sx, sz) in cl.items():
        c = Vector(c)
        put(capsule(f'THR_{KEY}_Suit_Cluster_{tag}', c-Vector((0, .014, 0)), c+Vector((0, .014, 0)), .021, M['graphite'], 20, 6), 'suit_thr',
            f'suit thruster cluster {tag}: four 8 N cold-N2 valves in a scarfed composite housing, flush with the module corner', B3, rig, tag=tag)
        put(torus(f'THR_{KEY}_Suit_Cluster_{tag}_ID', c+Vector((0, .0, 0)), Vector((0, 1, 0)), .0215, .0018, M['amber'], 24, 6), 'suit_thr',
            'propulsion identification ring (amber)', B3, rig, tag=tag)
    for name, pos, e, tag in ev.suit_nozzles(cl):
        parts = nozzle_mesh(f'NZ_{KEY}_SUIT_{name}', pos, e, .85, M)
        for o in parts[:2]:
            put(o, 'suit_thr', f'suit nozzle {name}: {ev.THRUST["suit_n"]:.0f} N cold N2', B3, rig, tag=tag)
        em = put(parts[2], 'suit_thr', f'suit thruster socket {name} (+Z = exhaust)', B3, rig, tag=tag); em['exhaust'] = True; em['thrust_n'] = ev.THRUST['suit_n']
        nzs.append(em.name)
    out['nozzles'] = nzs
    # ---- emergency reserve: red isolation knob and gauge window in the module's lower right side; the bottle is internal (cutaway)
    sxr = -1; zr = bot+.065; xr = sxr*hw(.065/h)
    yv = (y_front(xr, zr)+y_back(xr, zr, sxr*.98, .065/h))/2
    put(cyl(f'N2_{KEY}_Reserve_Valve_Knob', Vector((xr+sxr*.000, yv, zr)), Vector((xr+sxr*.012, yv, zr)), .0105, M['red'], 20), 'emergency',
        'reserve isolation valve knob (red): open in flight; closed for stowage or a leak', B3, rig)
    put(cyl(f'N2_{KEY}_Reserve_Gauge', Vector((xr-sxr*.002, yv, zr+.032)), Vector((xr+sxr*.004, yv, zr+.032)), .0085, M['text_light'], 20), 'emergency',
        'direct-reading reserve gauge window', B3, rig)
    put(text(f'N2_{KEY}_Reserve_Label', 'N2 RES', Vector((xr+sxr*.0045, yv, zr+.052)), Vector((0, -1, 0)), Vector((sxr, 0, 0)), .0085, M['text']), 'emergency',
        'reserve label', B3, rig)
    # ---- hatch hardware: hinge knuckles on the right edge, the hatch lever on the left (rear entry), D-rings, antenna patch
    for k, zz in enumerate((zc+.17, zc-.17)):
        xh = -hw(.5)-.004; yh = (y_front(xh, zz)+y_rear(xh))/2-.01
        put(cyl(f'LS_{KEY}_Hatch_Hinge_{k}', Vector((xh, yh, zz-.022)), Vector((xh, yh, zz+.022)), .0085, M['metal'], 16), 'life',
            'rear-entry hatch hinge knuckle: the whole life-support module swings open to the right for donning', B3, rig)
    xl = hw(.5)+.002; yl = (y_front(xl, zc)+y_rear(xl))/2-.008
    put(bx(f'LS_{KEY}_Hatch_Lever', Vector((xl+.004, yl, zc+.05)), (.004, .010, .045), M['graphite'], bevel=.002), 'life',
        'hatch closure lever (operated by the wearer from the front via a cable, as on rear-entry suits)', B3, rig)
    for sx in (1, -1):
        p = Vector((sx*.095, y_back(sx*.095, top-.01, sx*.095/(w/2), .985)-.03, top-.004))
        put(torus(f'TETHER_{KEY}_Hardpoint_{"P" if sx > 0 else "S"}', p+Vector((0, 0, .012)), Vector((1, 0, 0)), .013, .0035, M['steel'], 20, 6), 'tether',
            'rescue / tether hardpoint (folding D-ring) on the module top', B3, rig)
    put(bx(f'SENS_{KEY}_Suit_Antenna', Vector((0, y_r0-.035, top+.0005)), (.040, .022, .0015), M['graphite'], bevel=.001), 'sensor',
        'conformal S-band / UWB antenna window on the module top', B3, rig)
    put(text(f'LS_{KEY}_Label', 'LSS  O2 · CO2 · H2O', Vector((.11, y_rear(.11)+.0008, top-.05)), Vector((-1, 0, 0)), Vector((0, 1, 0)), .0085, M['text']), 'life',
        'service label', B3, rig)
    # ---- internals (cutaway collection, excluded by default): display layout of the packaging budget
    pc = out['pc']
    ints = [('O2_Primary_1', 'cap', Vector((-.12, pc.y, zc+.10)), (.034, .26), M['ls']), ('O2_Primary_2', 'cap', Vector((.12, pc.y, zc+.10)), (.034, .26), M['ls']),
            ('O2_Secondary', 'cap', Vector((-.155, pc.y, zc-.12)), (.024, .16), M['red']),
            ('CO2_Swing_Bed', 'box', Vector((0, pc.y-.005, zc+.12)), (.065, .040, .085), M['ls']),
            ('Membrane_Evaporator', 'box', Vector((0, pc.y+.03, zc-.02)), (.10, .012, .05), M['ls']),
            ('Fan_Pump_Separator', 'box', Vector((.12, pc.y, zc-.07)), (.04, .035, .045), M['ls']),
            ('Battery_1kWh', 'box', Vector((-.06, pc.y, zc-.08)), (.06, .035, .05), M['ls']),
            ('Avionics_Radio', 'box', Vector((.05, pc.y, zc-.09)), (.04, .03, .035), M['ls'])]
    for nm, kind, c, size, mt in ints:
        o = (capsule(f'LS_{KEY}_INT_{nm}', c-Vector((0, 0, size[1]/2)), c+Vector((0, 0, size[1]/2)), size[0], mt, 20, 6) if kind == 'cap'
             else bx(f'LS_{KEY}_INT_{nm}', c, size, mt, bevel=.004))
        put(o, 'life', f'internal: {nm.replace("_", " ").lower()} (packaging layout, cutaway)', B3, rig, cutaway=True)
    rt = ev.SUIT_RESERVE; ra = Vector((-rt['length_m']/2, pc.y+.004, bot+.065))
    put(capsule(f'N2_{KEY}_INT_Reserve_COPV', ra, ra+Vector((rt['length_m'], 0, 0)), rt['outer_d_m']/2, M['copv'], 24, 6), 'emergency',
        f'suit N2 reserve COPV {ev.budget()["suit_reserve"]["volume_l"]} L at 30 MPa (about {ev.budget()["dv_suit_reserve_alone_m_s"]} m/s alone)', B3, rig, cutaway=True)
    man = Vector((0, pc.y+.02, zk0+.02))
    put(bx(f'N2_{KEY}_INT_Suit_Manifold', man, (.03, .012, .015), M['n2line'], bevel=.003), 'n2',
        'suit N2 manifold: drone feed (1.4 MPa) or reserve (1.2 MPa) through two check valves', B3, rig, cutaway=True)
    for tag, (c, sx, sz) in cl.items():
        put(tube_path(f'N2_{KEY}_INT_Line_{tag}', [man, Vector((sx*.06, man.y, man.z)), Vector((sx*.06, man.y, c[2])), Vector(c)], .0028, M['n2line']), 'n2',
            f'manifold to cluster {tag}', B3, rig, cutaway=True)
    put(tube_path(f'N2_{KEY}_INT_Receptacle_Line', [man, Vector((0, man.y, z_n2)), rc+Vector((0, .028, 0))], .0035, M['n2line']), 'n2',
        'dock receptacle to manifold', B3, rig, cutaway=True)
    return out


# ---------------------------------------------------------------------------------------------------------------------- controls
def controls(rig, info, ls, M):
    """Chest display (flush) and the forearm drone control. The fold-out hand controller and the manual release are built after the
    poses (hand_controller), because the controller's deployed grip is the left hand's free-flight grip."""
    rings = info['rings']; z = 1.31; yf = torso_y(rings, 0, z, False, ev.SUIT['hut_shell_m'])
    put(bx(f'CTRL_{KEY}_Chest_Display', Vector((0, yf-.0012, z)), (.055, .0015, .030), M['display'], bevel=.002), 'sensor',
        'chest display: suit and drone status, flush in the torso shell (read in the helmet mirror or by the buddy)', B3, rig)
    put(bx(f'CTRL_{KEY}_Chest_Bezel', Vector((0, yf-.0004, z)), (.063, .0012, .037), M['graphite'], bevel=.003), 'frame', 'display bezel', B3, rig)
    put(text(f'MARK_{KEY}_Suit_GUC', 'G.U.C. WAYFARER 001', Vector((0, yf-.0016, z+.058)), Vector((1, 0, 0)), Vector((0, -1, 0)), .0095, M['text']), 'suit',
        'official marking (small, functional lettering)', B3, rig)
    put(bx(f'MARK_{KEY}_Suit_ID_Plate', Vector((0, yf-.0008, z+.082)), (.035, .001, .006), M['band']), 'suit', 'identification plate (role colour)', B3, rig)
    # forearm drone control: a curved plate on the right forearm with display and guarded release
    la, lb = bone(rig, 'lowerarm_r'); outer = info['outer']; odom = info['odom']
    cc, rr = section(outer_points(outer, odom, {'lowerarm_r'}), la, lb, .45, .65, .9)
    pad(_S, KEY, 'Forearm_Drone_Control', la, lb, cc, rr+.010, Vector((0, -.6, .5)), 70, .045, 'lowerarm_r', M['graphite'],
        'forearm drone control: mode, gas status (drone and reserve), guarded DRONE RELEASE', t=.008, assembly=('PLSS', 'PLSS_PRIMARY'))
    d = (lb-la).normalized(); f = Vector((0, -.6, .5)); f = (f-d*f.dot(d)).normalized(); p = cc+f*(rr+.0185)
    put(bx(f'CTRL_{KEY}_Forearm_Display', p, (.018, .0012, .028), M['display'], axes=(d.cross(f), f, d)), 'sensor', 'forearm display', 'lowerarm_r', rig)
    put(bx(f'CTRL_{KEY}_Forearm_Release_Guard', p+d*.038-f*.001, (.007, .003, .006), M['yellow'], axes=(d.cross(f), f, d), bevel=.0015), 'dock',
        'guarded release switch (lift the guard, hold 1 s)', 'lowerarm_r', rig)
    for k_, off in enumerate((-.022, -.008, .006)):                 # three glove-size command bars beside the display (mode, arms, return)
        put(bx(f'CTRL_{KEY}_Forearm_Drone_Key_{k_}', p+d*off+d.cross(f)*.024+f*.002, (.005, .002, .0055), M['graphite'], axes=(d.cross(f), f, d), bevel=.0015),
            'sensor', 'drone command key (raised bar, operable in EVA gloves): mode / arms / return-and-dock', 'lowerarm_r', rig)
    # left forearm: suit status (pressure, O2, reserve gas), tether management and the guarded emergency switch
    la, lb = bone(rig, 'lowerarm_l')
    cc, rr = section(outer_points(outer, odom, {'lowerarm_l'}), la, lb, .45, .65, .9)
    pad(_S, KEY, 'Forearm_Suit_Status', la, lb, cc, rr+.010, Vector((0, -.6, .5)), 70, .045, 'lowerarm_l', M['graphite'],
        'forearm suit status: pressure, O2, CO2, reserve N2, tether state', t=.008, assembly=('PLSS', 'PLSS_PRIMARY'))
    d = (lb-la).normalized(); f = Vector((0, -.6, .5)); f = (f-d*f.dot(d)).normalized(); p = cc+f*(rr+.0185)
    put(bx(f'CTRL_{KEY}_Forearm_Status_Display', p, (.018, .0012, .028), M['display'], axes=(d.cross(f), f, d)), 'sensor', 'suit status display', 'lowerarm_l', rig)
    put(bx(f'CTRL_{KEY}_Forearm_Emergency_Guard', p+d*.038-f*.001, (.007, .003, .006), M['red'], axes=(d.cross(f), f, d), bevel=.0015), 'emergency',
        'guarded emergency switch: suit reserve open, beacon, comms override (works without the drone)', 'lowerarm_l', rig)
    put(bx(f'CTRL_{KEY}_Forearm_Tether_Key', p-d*.040-f*.001, (.006, .002, .006), M['orange'], axes=(d.cross(f), f, d), bevel=.0015), 'tether',
        'tether reel brake / retract key', 'lowerarm_l', rig)
    # tether reels at the hips (slim)
    pa, _ = bone(rig, 'pelvis'); hips = outer_points(outer, odom, {'pelvis', 'spine_01'}); hw_ = max(abs(p.x) for p in hips)
    for side, sg in (('A', 1), ('B', -1)):
        c = Vector((sg*(hw_+.004), pa.y+.01, pa.z+.10))
        put(cyl(f'TETHER_{KEY}_Reel_{side}', c, c+Vector((sg*.020, 0, 0)), .030, M['graphite'], 24), 'tether', f'waist tether reel {side} (one of two independent restraints)',
            'pelvis', rig)
        put(torus(f'TETHER_{KEY}_Reel_{side}_Mark', c+Vector((sg*.0205, 0, 0)), Vector((1, 0, 0)), .021, .0022, M['orange'], 24, 6), 'tether', 'tether reel safety mark',
            'pelvis', rig)
        put(torus(f'TETHER_{KEY}_Hook_{side}', c+Vector((sg*.028, -.03, -.022)), Vector((1, 0, 0)), .015, .0042, M['orange'], 20, 6), 'tether',
            f'tether {side} hook (captive gate, stowed)', 'pelvis', rig)


# ---------------------------------------------------------------------------------------------------------------------- poses
def extra_frames(H):
    """Walk, reach, crouch, climb as human_system source frames (MPFB faces -Y). PROTOTYPE motion, inside the Y155 mobility limits."""
    fig = es._fig(H); F = (0.0, -1.0, 0.0); U = (0.0, 0.0, 1.0); legs = sum(hs.leg_lengths(H)[:3]); out = {}
    def shift(fr, d):
        o = {}
        for k_, v in fr.items():
            o[k_] = tuple(a-b for a, b in zip(v, d)) if isinstance(v, tuple) and len(v) == 3 and all(isinstance(q, float) for q in v) and k_ not in ('axes',) else v
        return o
    wk = hs.walk(H, dict(walk_speed_m_s=.60, walk_cadence_steps_min=88, step_height_m=.05), 30)['frames']
    fr = wk[int(len(wk)*.12)]; out['walk'] = shift(fr, (0.0, fr['root'][1], 0.0)); out['walk']['root'] = (0.0, 0.0, 0.0)
    stand = dict(ch.STAND, head=-4.0, arms=dict(right=dict(flex=6.0, abduct=20.0, elbow=22.0), left=dict(flex=10.0, abduct=18.0, elbow=30.0)))
    tgt = {'right': ((-.22, -.34, 1.86), (-.4, .4, -.6))}
    j = ch.skeleton(fig, stand, (0, 0, legs*.99), U, F, hands=es.suit_reach(H, stand, (0, 0, legs*.99), U, F, tgt))
    ank = {s: (sg*ch.P['hip_x']*H*1.25, 0.0, ch.P['ankle']*H) for s, sg in zip(es.SIDES, (-1, 1))}
    out['reach'] = es._frame(hs.legs_to(j, H, ank, F, U), (0, 0, 0), ('foot_right', 'foot_left'))
    hip = (0.0, .08, .56); pose = dict(ch.STAND, trunk=30.0, head=18.0)
    arms = {'right': ((-.17, -.30, .50), (-.3, .5, -.8)), 'left': ((.17, -.30, .50), (.3, .5, -.8))}
    j = ch.skeleton(fig, pose, hip, U, F, hands=es.suit_reach(H, pose, hip, U, F, arms))
    ank = {s: (sg*ch.P['hip_x']*H*1.6, -.16, ch.P['ankle']*H) for s, sg in zip(es.SIDES, (-1, 1))}
    out['crouch'] = es._frame(hs.legs_to(j, H, ank, F, U), (0, 0, 0), ('foot_right', 'foot_left'))
    # climb: facing the ladder (rungs every 0.30 m at y = -0.31, rails at x = +-0.26), right foot on the 0.30 m rung, left on the 0.60 m
    # rung, hands on the rails (wide grip clears the helmet), right hand high
    hip = (0.0, -.04, 1.17); pose = dict(ch.STAND, trunk=6.0, head=-12.0)
    arms = {'right': ((-.25, -.27, 1.70), (-.5, .6, -.3)), 'left': ((.25, -.27, 1.42), (.5, .6, -.4))}
    j = ch.skeleton(fig, pose, hip, U, F, hands=es.suit_reach(H, pose, hip, U, F, arms))
    ank = {'right': (-.10, -.22, .30+.07), 'left': (.10, -.22, .60+.07)}
    toes = {'right': (-.10, -.36, .32), 'left': (.10, -.36, .62)}
    out['climb'] = es._frame(hs.legs_to(j, H, ank, F, U, toes), (0, 0, 0), ('foot_right', 'foot_left', 'hand_right', 'hand_left'))
    return out


def body_pt(j, base, d):
    ax = j['axes']; b = j[base] if isinstance(base, str) else base
    return tuple(b[i]+ax[0][i]*d[0]+ax[1][i]*d[1]+ax[2][i]*d[2] for i in range(3))


def pose_frames(H):
    """The five presentation poses as human_system source frames (MPFB faces -Y). PROTOTYPE motion, inside the Y155 mobility limits."""
    fig = es._fig(H); F = (0.0, -1.0, 0.0); U = (0.0, 0.0, 1.0); legs = sum(hs.leg_lengths(H)[:3]); out = {}
    def feet(j, spread=1.25, fwd=0.0):
        ank = {s: (sg*ch.P['hip_x']*H*spread, fwd, ch.P['ankle']*H) for s, sg in zip(es.SIDES, (-1, 1))}
        return hs.legs_to(j, H, ank, F, U)
    # 1 EVA ready: standing, arms slightly out from the hard torso, feet planted
    stand = dict(ch.STAND, head=-4.0, arms=dict(right=dict(flex=8.0, abduct=40.0, elbow=22.0), left=dict(flex=8.0, abduct=40.0, elbow=22.0)))
    out['ready'] = es._frame(feet(ch.skeleton(fig, stand, (0, 0, legs*.99), U, F)), (0, 0, 0), ('foot_right', 'foot_left'))
    # 2 free flight: neutral-body posture pitched 12 deg into the direction of travel; hands aimed at the hand controller and forward
    # (clear_arms then turns both arms out of the cuirass, so the left hand ends about 0.4 m from the controller: a known limitation)
    a = math.radians(12); up = (0.0, -math.sin(a), math.cos(a)); face = (0.0, -math.cos(a), -math.sin(a)); hip = (0.0, 0.0, 1.02)
    pose = dict(ch.STAND, trunk=0.0, head=-10.0, **es._legs(38.0, 32.0)); j0 = ch.skeleton(fig, pose, hip, up, face)
    arms = {'left': (body_pt(j0, 'chest', (-.26, .46, -.12)), (.4, .3, -.8)), 'right': (body_pt(j0, 'chest', (.38, .32, -.18)), (-.4, .3, -.8))}
    out['flight'] = es._frame(es.floating(H, hip, up, face, arms, head=-10.0, legs=es._legs(38.0, 32.0)), (0, 0, 0))
    # 3 drone deployed: upright float while the drone works, the same arm targets as free flight.
    # A cross-body reach (left hand on the right forearm keys) cannot clear the rigid cuirass at any shoulder turn: the forearm keys
    # are for short presses with the forearm low, not for a held control pose.
    up = (0.0, 0.0, 1.0); face = (-.20, -.98, 0.0); face = tuple(c/math.hypot(*face) for c in face); hip = (0.0, 0.0, 1.02)
    pose = dict(ch.STAND, head=-6.0, **es._legs(28.0, 24.0)); j0 = ch.skeleton(fig, pose, hip, up, face)
    arms = {'left': (body_pt(j0, 'chest', (-.26, .46, -.12)), (.4, .3, -.8)), 'right': (body_pt(j0, 'chest', (.38, .32, -.18)), (-.4, .3, -.8))}
    out['deployed'] = es._frame(es.floating(H, hip, up, face, arms, head=-6.0, legs=es._legs(28.0, 24.0)), (0, 0, 0))
    # 4 burn operation (Burnbrow, 1.1-1.5 g toward the engines = -Z here): crouched and braced, both hands on a grab bar, toe hooks in the
    # foot-restraint rail; the drone stays docked (its weight is carried by the dock frame and the legs)
    bar = (0.0, -.50, .98); hip = (0.0, .10, .74); pose = dict(ch.STAND, trunk=32.0, head=18.0)
    j0 = ch.skeleton(fig, pose, hip, (0, 0, 1), F)
    arms = {'right': ((-.30, bar[1]+.07, bar[2]), (-.3, .5, -.8)), 'left': ((.30, bar[1]+.07, bar[2]), (.3, .5, -.8))}
    j = ch.skeleton(fig, pose, hip, (0, 0, 1), F, hands=es.suit_reach(H, pose, hip, (0, 0, 1), F, arms))
    ank = {s: (sg*ch.P['hip_x']*H*1.45, -.10, ch.P['ankle']*H) for s, sg in zip(es.SIDES, (-1, 1))}
    out['burn'] = es._frame(hs.legs_to(j, H, ank, F, U), (0, 0, 0), ('foot_right', 'foot_left', 'hand_right', 'hand_left'))
    # 5 chase: a push-off glide, body horizontal and head first toward -Y, arms held before the chest as in free flight (an arm
    # reaching overhead sits in the shoulder FWD cones, an arm along the side in the lumbar ones), legs trailing
    up = (0.0, -1.0, 0.0); face = (0.0, 0.0, -1.0); hip = (0.0, .35, 1.05)
    pose = dict(ch.STAND, head=18.0, **es._legs(12.0, 8.0)); j0 = ch.skeleton(fig, pose, hip, up, face)
    arms = {'right': (body_pt(j0, 'chest', (.38, .32, -.18)), (-.4, .8, .3)), 'left': (body_pt(j0, 'chest', (-.26, .46, -.12)), (.4, .8, .3))}
    out["chase"] = es._frame(es.floating(H, hip, up, face, arms, head=18.0, legs=es._legs(12.0, 8.0)), (0, 0, 0))
    return out



# ---------------------------------------------------------------------------------------------------------------------- kit and sockets
def kit(rig, info, ls, M, variant):
    """Role marking, the stowed inspection tool (ASSET-14), umbilical and cooling ports on the module, and the RIG-03/04 sockets."""
    rings = info['rings']; z = 1.31; yf = torso_y(rings, 0, z, False, ev.SUIT['hut_shell_m'])
    role = 'GUIDED EVA · INSTRUCTOR' if variant['role_band'] == 'gu_blue' else 'GUIDED EVA · VISITOR'
    put(text(f'MARK_{KEY}_Role', role, Vector((0, yf-.0016, z-.048)), Vector((1, 0, 0)), Vector((0, -1, 0)), .0078, M['text']), 'mark',
        'role designation (ASSET-15 "GUIDED EVA designation"): ' + variant['markings'], B3, rig)
    # inspection scanner / dosimeter on a chest bracket on the right, clear of the hand controller on the left (EVA-020)
    zt = info['z0']+.05; xt = -.105; yt = torso_y(rings, xt, zt, False, ev.SUIT['hut_shell_m'])
    tc = Vector((xt, yt-.026, zt))
    put(bx(f'EVA_{KEY}_Tool_Scanner', tc, (.026, .018, .050), M['graphite'], bevel=.005), 'tool',
        'inspection scanner / dosimeter with retained lanyard; stowed on the chest bracket (ASSET-14, EVA-020)', B3, rig)
    put(cyl(f'EVA_{KEY}_Tool_Scanner_Lens', tc+Vector((0, -.018, .03)), tc+Vector((0, -.020, .03)), .008, M['lens'], 16), 'tool', 'scanner window', B3, rig)
    put(torus(f'EVA_{KEY}_Tool_Lanyard_Ring', tc+Vector((0, 0, -.058)), Vector((0, 1, 0)), .010, .0028, M['orange'], 16, 6), 'tool',
        'tool retention lanyard ring (EVA-020)', B3, rig)
    # umbilical (SCU) and cooling quick disconnects on the module's lower sides (ASSET-09; recharge from ship supplies, 53!6, 53!8)
    ports = {}
    for nm, sx, job in (('SCU_Port', 1, 'umbilical port: O2, power and data from certified ship supplies (53!6)'),
                        ('Cooling_Port', -1, 'cooling-loop quick disconnect (53!8)')):
        zp = ls['bot']+.16; v = (zp-ls['bot'])/ls['h']; xp = sx*ls['hw'](v); yp = ls['y_front'](xp, zp)+ls['dpt']*.45
        a = Vector((xp-sx*.004, yp, zp)); b = a+Vector((sx*.022, 0, 0))
        put(cyl(f'EVA_{KEY}_PLSS_{nm}', a, b, .012, M['metal'], 20), 'life', job, B3, rig); ports[nm] = b
    sock = []
    for nm, bn, loc, job in [('SOCKET_HAND_L_GRIP', 'hand_l', None, 'left palm grip contact (RIG-04)'),
                             ('SOCKET_HAND_R_GRIP', 'hand_r', None, 'right palm grip contact (RIG-04)'),
                             ('SOCKET_HAND_R_TOOL', 'hand_r', None, 'tool equipped pose (ASSET-14)'), ('SOCKET_TOOL_STOW', B3, tc, 'tool stow pose (ASSET-14)'),
                             ('SOCKET_TOE_HOOK_L', 'ball_l', None, 'left toe hook'), ('SOCKET_TOE_HOOK_R', 'ball_r', None, 'right toe hook'),
                             ('SOCKET_PLSS_SCU', B3, ports['SCU_Port'], 'umbilical port'),
                             ('SOCKET_HELMET_EYE', B3, info['hc']+Vector((0, -.04, 0)), 'eye point for a first-person camera inside the helmet'),
                             ('SOCKET_HUD', B3, info['hc']+Vector((0, -info['ax'][1]*.85, -.04)), 'in-view display plane (EVA-018)')]:
        if loc is None:
            h0, h1 = bone(rig, bn); loc = h1 if bn.startswith('hand') else (h0+h1)/2
        e = link(bpy.data.objects.new(nm, None)); e.location = loc; e.empty_display_size = .04; put(e, 'rig', job, bn, rig); sock.append(nm)
    for side in 'AB':                                           # tether hook sockets (RIG-04): the runtime line starts here
        hk = bpy.data.objects[f'TETHER_{KEY}_Hook_{side}']; c = sum((hk.matrix_world @ Vector(q) for q in hk.bound_box), Vector())/8
        e = link(bpy.data.objects.new(f'SOCKET_TETHER_{side}', None)); e.location = c; e.empty_display_size = .05
        put(e, 'rig', f'tether {side} hook socket (RIG-04): runtime line start', 'pelvis', rig); sock.append(e.name)
    d = link(bpy.data.objects.new('SOCKET_DRONE_DOCK', None)); d.empty_display_type = 'ARROWS'; d.empty_display_size = .15
    d.matrix_world = dock_frame(ls)
    put(d, 'rig', 'companion drone docked frame: the drone rig copies this transform while "docked" = 1 (build/eva_drone.py)', B3, rig)
    sock.append(d.name)
    return sock


def dock_frame(ls):
    """World matrix of the drone's local frame when docked: origin on the dock face, on the keel line at the keel's mid length; local
    (x, y, z) -> suit world (-x, z, y)."""
    R = Matrix(((-1, 0, 0), (0, 0, 1), (0, 1, 0)))
    return Matrix.Translation((0.0, ls['y_r0']+ev.SUIT['dock_gap_m'], ls['zc']-.025)) @ R.to_4x4()


# ---------------------------------------------------------------------------------------------------------------------- build
def dress(rig, body, data, variant, key, root_c):
    global KEY, _S
    global _M
    KEY = key; _S = Part(root_c, data, rig); M = materials(data['palette'], data['palette'][variant['role_band']], variant['role_band'], OWNER)
    _M = M
    info = form(rig, body, M, data)
    ls = life_support(rig, info, M)
    controls(rig, info, ls, M)
    sockets = kit(rig, info, ls, M, variant)
    rig.data.pose_position = 'POSE'
    module = dict(top=ls['top'], bot=ls['bot'], zc=ls['zc'], w=ls['w'], dpt=ls['dpt'], h=ls['h'], y_r0=ls['y_r0'], cwh=ls['cwh'], dep=ls['dep'],
                  zk0=ls['zk0'], zk1=ls['zk1'], pc=list(ls['pc']), nozzles=ls['nozzles'], clusters={k: [list(c), sx, sz] for k, (c, sx, sz) in ls['clusters'].items()},
                  poppet=ls['poppet'].name, capture=ls['capture'].name, module_object=ls['module'].name)
    rig['eva_module'] = json.dumps({k: (round(v, 5) if isinstance(v, float) else v) for k, v in module.items()})
    rig['eva_helmet'] = json.dumps(dict(centre=[round(x, 4) for x in info['hc']], semi_axes=[round(a, 4) for a in info['ax']], exponent=info['n'],
                                        bone=B3, shells=[info['helmet'].name, info['visor'].name, info['brow'].name, info['hut'].name]))
    rig['eva_outer'] = info['outer'].name
    return _S, dict(helmet_centre=[round(x, 4) for x in info['hc']], helmet_semi_axes_m=[round(a, 4) for a in info['ax']],
                    plss_centre=[round(x, 4) for x in ls['pc']], plss_size_m=list(ev.SUIT['plss_size_m']), module=module, sockets=sockets,
                    outer_trimmed_faces=info['outer_trimmed_faces'], cuirass_arch=info['arch'], scye_sleeves=info['scye_sleeves'])


def system_poses(rig, body, H, fps):
    """The EVA system poses as one action (EVA_SYSTEM_POSES, a pose every POSE_SEG frames, muted NLA track): the build/eva_scene.py states
    and the renders reuse it instead of posing a rig per scene."""
    data = es.load(ROOT)
    P = hs.proportions({b.name: (tuple(b.head_local), tuple(b.tail_local)) for b in rig.data.bones}, H)
    saved = dict(ch.P); es.ELBOW_LIMIT[0] = data['mobility']['elbow_max_deg']
    try:
        ch.P.update(P); frames = pose_frames(H); frames.update(extra_frames(H)); rest = hs.rest(H)
    finally:
        ch.P.clear(); ch.P.update(saved)
    order = list(SYSTEM_POSES)
    seq = []
    for k in order:
        seq += [frames[k]]*POSE_SEG
    act, rep = bake_action(rig, Solver(rig, rest, hinge_elbows=True), seq, 'EVA_SYSTEM_POSES', dict(loop=False, root_motion=False))
    act['poses'] = json.dumps(order); act['segment_frames'] = POSE_SEG; act['eva'] = True
    act['pose_notes'] = json.dumps(SYSTEM_POSES)
    rep['shoulder_clearance'] = clear_arms(rig, act, order)
    rep['hand_controller'] = hand_controller(rig, act, order)
    return act, rep


def join(target, others):
    """Merge `others` into `target` (materials kept per face) and delete them."""
    me = target.data; bm = bmesh.new(); bm.from_mesh(me); inv = target.matrix_world.inverted()
    for o in others:
        slot = {}
        for i, m_ in enumerate(o.data.materials):
            if m_.name not in [x.name for x in me.materials if x]:
                me.materials.append(m_)
            slot[i] = [x.name for x in me.materials].index(m_.name)
        tmp = o.data.copy(); tmp.transform(inv @ o.matrix_world)
        for pg in tmp.polygons:
            pg.material_index = slot.get(pg.material_index, 0)
        bm.from_mesh(tmp); bpy.data.meshes.remove(tmp); bpy.data.objects.remove(o, do_unlink=True)
    bm.to_mesh(me); bm.free(); me.update()


def hand_controller(rig, act, order):
    """The fold-out hand controller (fix 3): a hinge housing on the module's left front corner carries a swing link and a telescoping link
    whose end carries the vertical grip (translation / rotation controller, MMU armrest class). Stowed, the arm lies back along the
    module's side, above the lumbar thrusters' plumes and behind the hanging arm; deployed, it swings forward and down about one skewed
    hinge axis (perpendicular to both directions) and telescopes out, so the grip stands vertical beside the left palm of the
    free-flight pose and the glove closes on it in flight, drone-deployed and chase without moving the arm. The grip is seated against the
    glove: its axis is the nearest vertical line to the palm centre that clears the evaluated glove by seat_gap_m over the grip's height.
    Objects: HCM_Pivot (empty on spine_03, X = stowed direction, Z = hinge axis), HCM_Link_1 (rotation about Z: the swing), HCM_Link_2
    (location along X: the telescope); the EVA_SYSTEM_POSES NLA track of each link keys stowed or deployed per pose. Returns the
    geometry, the stops and the deployed reach."""
    P = ev.SUIT['hand_controller']; M = _M; pb = rig.pose.bones; db = rig.data.bones; mw = rig.matrix_world; sc = bpy.context.scene
    r1, r2 = P['link_r_m']; rg = .018; rise = P['grip_rise_m']
    rig.animation_data.action = act; sc.frame_set(order.index('flight')*POSE_SEG+2); bpy.context.view_layer.update()
    palm = mw @ ((pb['hand_l'].head+pb['middle_01_l'].head)/2); B3w = mw @ pb[B3].matrix; up = (B3w.to_3x3() @ Vector((0, 1, 0))).normalized()
    outer = next(o for o in rig.children if o.name.endswith('_OUTER_LAYER'))
    dg = bpy.context.evaluated_depsgraph_get(); e = outer.evaluated_get(dg); me = e.to_mesh()
    glove = [e.matrix_world @ v.co for v in me.vertices if (e.matrix_world @ v.co-palm).length < .16]; e.to_mesh_clear()
    u1 = (up.cross(Vector((1, 0, 0)))).normalized(); u2 = up.cross(u1).normalized(); best = None
    for i in range(-14, 15):                                          # seat the grip: nearest clear vertical axis to the palm centre
        for j in range(-14, 15):
            c = palm+u1*(i*.004)+u2*(j*.004); dist = (c-palm).length
            if best is not None and dist >= best[0]:
                continue
            clear = all(((q-c)-up*(q-c).dot(up)).length >= rg+P['seat_gap_m'] for q in glove if -rise-.01 <= (q-c).dot(up) <= .072)
            if clear:
                best = (dist, c)
    assert best, 'hand controller: no clear grip axis within 56 mm of the palm'
    seat = best[1]; g_loc = pb[B3].matrix.inverted() @ (mw.inverted() @ seat)
    rig.animation_data.action = None; sc.frame_set(0)
    R3 = mw @ db[B3].matrix_local; G = R3 @ g_loc                     # the grip centre on the rest-pose torso
    a1 = (R3.to_3x3() @ Vector((0, 1, 0))).normalized()               # the torso's long axis: the grip stands along it when deployed
    mod = next(o for o in rig.children if o.name.startswith('LS_') and o.name.endswith('_Module'))
    rig.data.pose_position = 'REST'; bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get(); e = mod.evaluated_get(dg); me = e.to_mesh(); pts = [e.matrix_world @ v.co for v in me.vertices]; e.to_mesh_clear()
    T = G-a1*rise                                                     # the telescope's end, under the grip
    band = [p for p in pts if abs((p-T).dot(a1)-P['hinge_rise_m']) < .04 and p.x > 0]
    side = max(band, key=lambda p: p.x); front = min((p for p in band if p.x > side.x-.02), key=lambda p: p.y)
    H = Vector((side.x+P['standoff_m'], front.y+.012, T.z)); H = H+a1*((T-H).dot(a1)+P['hinge_rise_m'])   # hinge on the front corner, above the grip
    stow = Vector((0, 1, 0)); stow = (stow-a1*stow.dot(a1)).normalized()   # stowed: back along the module side, above the lumbar cluster
    d = T-H; reach = d.length; dep = d.normalized()
    kax = stow.cross(dep).normalized(); th = math.acos(max(-1.0, min(1.0, stow.dot(dep))))   # skewed hinge axis, swing angle about it
    L1 = max(P['link_m'], (reach+.04)/2)                                             # the outer tube grows for a longer reach
    s_dep = reach-L1; s_min = P['slide_min_m']
    assert s_min < s_dep < L1-.03, f'hand controller: reach {reach:.3f} m does not fit the telescope (hinge {H}, side {side}, front {front})'
    # pivot frame: X = stowed direction, Z = hinge axis
    piv = bpy.data.objects.new(f'CTRL_{KEY}_HCM_Pivot', None); piv.empty_display_type = 'ARROWS'; piv.empty_display_size = .04
    bpy.context.scene.collection.objects.link(piv)
    Rp = Matrix((stow, kax.cross(stow), kax)).transposed(); piv.matrix_world = Matrix.Translation(H) @ Rp.to_4x4()
    put(piv, 'sensor', 'hand-controller hinge frame (X: stowed direction, Z: hinge axis; the links swing about it)', B3, rig)
    def child(o, parent):
        o.parent = parent; o.parent_type = 'OBJECT'; o.parent_bone = ''; o.matrix_parent_inverse = Matrix(); o.location = (0, 0, 0); o.rotation_euler = (0, 0, 0)
    hs_ = cyl(f'CTRL_{KEY}_HCM_Hinge_Housing', Vector((-.012, 0, -.03)), Vector((-.012, 0, .03)), .021, M['graphite'], 24)
    put(hs_, 'sensor', 'hinge housing on the module corner: detented hinge, hard stops at stowed and deployed', B3, rig); child(hs_, piv)
    l1 = cyl(f'CTRL_{KEY}_HCM_Link_1', Vector((0, 0, 0)), Vector((L1, 0, 0)), r1, M['graphite'], 20)
    k1 = cyl('_k', Vector((0, 0, -.016)), Vector((0, 0, .016)), .016, M['graphite'], 20)
    join(l1, [k1]); put(l1, 'sensor', 'controller arm, outer tube: swings on the hinge (stops at 0 and the deployed angle)', B3, rig); child(l1, piv)
    gax = (Matrix.Rotation(th, 3, 'Z').inverted() @ (Rp.inverted() @ a1)).normalized()   # the grip axis in the link frame: vertical when deployed
    l2 = cyl(f'CTRL_{KEY}_HCM_Link_2', Vector((-(L1-.03), 0, 0)), Vector((0, 0, 0)), r2, M['metal'], 20)
    grip = lathe('_g', Vector((0, 0, 0)), gax, [(0, .014), (.015, .013), (.03, .015), (.075, .015), (.085, rg), (.095, rg), (.10, 0)], M['rubber'], 20)
    puck = cyl('_p', gax*.10, gax*.112, .016, M['graphite'], 20)
    join(l2, [grip, puck]); put(l2, 'sensor', 'telescoping inner tube with the vertical grip: translation (squeeze / push) and rotation (twist / tilt) '
                              'controller, thumb puck on top', B3, rig); child(l2, l1); l2.location = (L1+s_min, 0, 0)
    rel = bx(f'CTRL_{KEY}_Manual_Release', H-a1*.075-Vector((0, 1, 0))*.004, (.005, .012, .005), M['yellow'],
             axes=(a1.cross(Vector((1, 0, 0))).normalized(), Vector((1, 0, 0)), a1), bevel=.002)
    put(rel, 'dock', 'mechanical release T-handle below the controller hinge: Bowden cable to the drone keel bolts (works unpowered)', B3, rig)
    # stowed and deployed keys on the links' EVA_SYSTEM_POSES tracks
    stops = dict(yaw_deg=[0.0, round(math.degrees(th), 2)], slide_m=[round(L1+s_min, 4), round(L1+s_dep, 4)])
    for o, path, idx, vals in ((l1, 'rotation_euler', 2, (0.0, th)), (l2, 'location', 0, (L1+s_min, L1+s_dep))):
        o.animation_data_create(); a = bpy.data.actions.new(f'{o.name}_SYSTEM_POSES'); a['wf_owner'] = OWNER; o.animation_data.action = a
        for k, nm in enumerate(order):
            v = vals[1] if nm in P['deploy_poses'] else vals[0]
            for f in (k*POSE_SEG, k*POSE_SEG+POSE_SEG-1):
                getattr(o, path)[idx] = v; o.keyframe_insert(path, index=idx, frame=f)
        for fc in a.fcurves if hasattr(a, 'fcurves') else []:
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'
        o.animation_data.action = None; tr = o.animation_data.nla_tracks.new(); tr.name = 'EVA_SYSTEM_POSES'; tr.strips.new('EVA_SYSTEM_POSES', 0, a); tr.mute = True
        getattr(o, path)[idx] = vals[0]
    out = dict(pivot=piv.name, links=[l1.name, l2.name], housing=hs_.name, release=rel.name, deploy_poses=P['deploy_poses'], stops=stops,
               reach_m=round(reach, 3), grip_local=[round(c, 4) for c in g_loc], hinge_world=[round(c, 4) for c in H], hinge_axis=[round(c, 4) for c in kax],
               seat_from_palm_mm=round(best[0]*1000, 1), grip_r_m=rg, grip_axis_link=[round(c, 5) for c in gax],
               swing_deg=round(math.degrees(th), 1), telescope_m=round(s_dep-s_min, 3),
               controls=dict(yaw='HCM_Link_1 rotation_euler.z (rad, about the skewed hinge axis), stowed 0', slide='HCM_Link_2 location.x (m)'))
    rig['eva_hand_controller'] = json.dumps(out); rig.data.pose_position = 'POSE'
    return out


ARM_PARTS = ('upperarm', 'lowerarm', 'hand', 'thumb', 'index', 'middle', 'ring', 'pinky')


def clear_arms(rig, act, order, abduct=(0, 6, 12, 18, 24, 30, 36, 42, 48), flex=(0, -10, 10, -20, 20, -30, 30, -40, 40)):
    """The suit's arm-to-torso limit (fix 4.2): a pressurised arm cannot fold against the rigid torso or the module. For each system pose,
    an arm whose soft layer meets the torso shell or the module is turned at the shoulder, outward (abduction 0-48 deg, about the axis normal to
    the upper arm and the shoulder's outward direction) and forward or back (+-40 deg, about that outward direction), choosing among the turns
    that clear it the one that moves the hand least. The keys of that pose are rewritten.
    Returns {pose: {side: dict(abduct_deg, flex_deg, hand_moved_mm, contacts_left)}}; contacts_left > 0: no turn in range clears it."""
    kids = list(rig.children)
    outer = next(o for o in kids if o.name.endswith('OUTER_LAYER')); hut = next(o for o in kids if o.name.endswith('_Torso_Shell'))
    mod = next(o for o in kids if o.name.startswith('LS_') and o.name.endswith('_Module'))
    bones = {b.name for b in rig.data.bones}; names = {g.index: g.name for g in outer.vertex_groups if g.name in bones}
    side_of = []
    for v in outer.data.vertices:                                   # the dominant deform bone (other vertex groups are body-part masks)
        best = max(((g.weight, names[g.group]) for g in v.groups if g.group in names), default=(0.0, ''))[1]
        side_of.append(best[-1] if best.startswith(ARM_PARTS) and best[-2:] in ('_l', '_r') else '')
    faces = {s: [list(q.vertices) for q in outer.data.polygons if any(side_of[k] == s for k in q.vertices)] for s in 'lr'}   # boundary faces too
    pb = rig.pose.bones; rig.animation_data.action = act; sc = bpy.context.scene; out = {}
    def rigid():
        dg = bpy.context.evaluated_depsgraph_get(); trees = []
        for o in (hut, mod):
            e = o.evaluated_get(dg); me = e.to_mesh()
            trees.append(BVHTree.FromPolygons([e.matrix_world @ v.co for v in me.vertices], [list(q.vertices) for q in me.polygons])); e.to_mesh_clear()
        return trees
    def contacts(trees, s):
        dg = bpy.context.evaluated_depsgraph_get(); e = outer.evaluated_get(dg); me = e.to_mesh()
        T = BVHTree.FromPolygons([e.matrix_world @ v.co for v in me.vertices], faces[s]); e.to_mesh_clear()
        return sum(len(t.overlap(T)) for t in trees)
    for k, nm in enumerate(order):
        f = k*POSE_SEG; sc.frame_set(f+2); trees = rigid(); res = {}
        for s in 'lr':
            n0 = contacts(trees, s)
            if not n0:
                continue
            b = pb[f'upperarm_{s}']; M0 = b.matrix.copy(); h = M0.translation.copy(); u = (pb[f'lowerarm_{s}'].head-h).normalized()
            hand0 = pb[f'hand_{s}'].head.copy()
            chest = pb['spine_03'].matrix.translation; o_ = h-chest; o_ = (o_-u*o_.dot(u)).normalized(); ax_a = u.cross(o_).normalized()
            best = (n0, 0.0, 0.0, 0.0)
            for a in abduct:
                for fl in flex:
                    if not a and not fl:
                        continue
                    R = Matrix.Rotation(math.radians(fl), 4, o_) @ Matrix.Rotation(math.radians(a), 4, ax_a)
                    b.matrix = Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ M0; bpy.context.view_layer.update()
                    n = contacts(trees, s); mv = (pb[f'hand_{s}'].head-hand0).length
                    if (n, mv) < (best[0], best[3]):
                        best = (n, a, fl, mv)
            R = Matrix.Rotation(math.radians(best[2]), 4, o_) @ Matrix.Rotation(math.radians(best[1]), 4, ax_a)
            b.matrix = Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ M0; bpy.context.view_layer.update()
            q = b.rotation_quaternion.copy()
            for fr in range(f, f+POSE_SEG):
                b.rotation_quaternion = q; b.keyframe_insert('rotation_quaternion', frame=fr, group=b.name)
            sc.frame_set(f+2)
            res[s] = dict(abduct_deg=best[1], flex_deg=best[2], hand_moved_mm=round(best[3]*1000, 1), contacts_left=best[0])
        if res:
            out[nm] = res
    rig.animation_data.action = None
    return out


SYSTEM_POSES = dict(ready='standing, EVA ready', walk='mid-stride on a deck (gravity)', reach='right hand overhead', crouch='crouched, hands low',
                    climb='on a ladder', flight='free flight, pitched into travel, arms forward clear of the cuirass',
                    deployed='upright float while the drone works, arms forward clear of the cuirass', burn='braced in a foot rail under thrust (Burnbrow)',
                    chase='head-first push-off glide (Brow Games chase)')


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--only', nargs='*'); ap.add_argument('--root', type=Path, default=ROOT)
    ap.add_argument('--report', type=Path); ap.add_argument('--no-save', action='store_true')
    args = ap.parse_args(argv); root = args.root
    data = es.load(root); hsd = hs.load(root); _, _, spec_text, source_text = load(root); fps = hsd['human_system']['fps']
    report = dict(suit=data['suit']['id'], status=data['suit']['status'], certification=data['suit']['certification'], variants={})
    for key in args.only or list(data['variant']):
        v = data['variant'][key]; who = v['wearer']; ident = f'WF_EVA_{who.upper()}'; path = root/'assets/characters'/f'{ident}.blend'
        src = root/'assets/characters'/f'WF_CHAR_HUMAN_{who.upper()}.blend'
        assert src.exists(), f'{src.name} missing: run `python3 tools/workflow.py characters` first'
        begin(path, ident); bpy.context.scene.render.fps = fps
        for o in list(bpy.data.objects):                      # the whole file outside ART is regenerated
            if not any(c.name.startswith('ART_') for c in o.users_collection):
                bpy.data.objects.remove(o, do_unlink=True)
        for c in list(bpy.data.collections):
            if c.get('wf_owner') == OWNER and not c.name.startswith(('GEN_', 'ART_')):
                bpy.data.collections.remove(c)
        for table in (bpy.data.meshes, bpy.data.materials, bpy.data.actions, bpy.data.armatures):
            for blk in list(table):
                if blk.users == 0 or blk.get('wf_owner') == OWNER and table is bpy.data.actions:
                    table.remove(blk)
        root_c = bpy.data.collections.new('WAYFARER_EVA_Y155'); bpy.context.scene.collection.children.link(root_c); root_c['wf_owner'] = OWNER
        root_c['suit_status'] = data['suit']['status']; root_c['certification'] = data['suit']['certification']; root_c['variant'] = key
        with bpy.data.libraries.load(str(src), link=False) as (dsrc, dst):
            dst.objects = [n for n in dsrc.objects if n.startswith(f'CHAR_{who.upper()}')]
        rig = next(o for o in dst.objects if o.type == 'ARMATURE')
        for o in dst.objects:
            bpy.context.scene.collection.objects.link(o)
        body = next(o for o in rig.children if o.name.endswith('_Body'))
        S, info = dress(rig, body, data, v, who.upper(), root_c); rig['eva_plss'] = 'LIFE_SUPPORT_MODULE (rear-entry hatch)'
        S.put(rig, 'RIG', 'SOCKETS', 'the wearer\'s unchanged MPFB game_engine rig (RIG-02): 53 bones'); rig.color = SYSTEM['rig']
        for o in rig.children:
            if o.name.startswith(f'CHAR_{who.upper()}_') and not o.name.endswith(('_Body', '_Head')) and o.get('assembly') is None:
                S.put(o, 'RIG', 'SOCKETS', 'wearer eyes, brows and lashes inside the helmet')
        S.put(body, 'RIG', 'SOCKETS', 'full wearer body for the coverage check; not exported'); body['eva_role'] = 'validation_body'
        body.hide_render = True; body.hide_viewport = True
        runtime_head(body, data['layers']['uncovered_groups'], who.upper(), S)
        # ---- EVA actions on the unchanged rig
        H = round(max(vv.co.z for vv in body.data.vertices), 4); bones = {b.name: (tuple(b.head_local), tuple(b.tail_local)) for b in rig.data.bones}
        P = hs.proportions(bones, H); lib = es.actions(H, data, fps, P); solver = Solver(rig, lib['rest'], hinge_elbows=True); acts = {}; info['actions'] = {}
        for name in es.EVA_ACTIONS:
            a = lib[name]; act, r = bake_action(rig, solver, a['frames'], name, a)
            held = {s: [(i, f'hand_{s}' in (a.get('grips') or [f['contacts'] for f in a['frames']])[i]) for i in range(len(a['frames']))] for s in hs.SIDES}
            grip_fingers(rig, act, held)
            for k in ('travel_speed_m_s', 'events', 'point_dir_body', 'anchors_body'):
                if k in a:
                    act[k] = json.dumps(a[k])
            if 'grips' in a:
                act['grips'] = json.dumps(a['grips'])
            act['eva'] = True; acts[name] = act; info['actions'][name] = r
        info['mobility'] = es.mobility_report(lib, data['mobility'])
        pact, prep = system_poses(rig, body, H, fps); acts['EVA_SYSTEM_POSES'] = pact; info['actions']['EVA_SYSTEM_POSES'] = prep
        rig.animation_data.action = None
        for name, act in acts.items():
            tr = rig.animation_data.nla_tracks.new(); tr.name = name; tr.strips.new(name, 0, act); tr.mute = True
        for name, why in es.SHARED_ACTIONS.items():           # inherited unsuited actions stay playable for the wearer, never as EVA
            if name in bpy.data.actions:
                a = bpy.data.actions[name]; a['eva'] = False; a['suited_use'] = 'NOT_SUITED_EVA'; a['suited_note'] = why
        rig['eva_suit'] = data['suit']['id']; rig['eva_variant'] = key; rig['eva_actions'] = json.dumps(list(es.EVA_ACTIONS))
        rig['eva_system_poses'] = json.dumps(list(SYSTEM_POSES)); rig['eva_not_suited_actions'] = json.dumps(list(es.SHARED_ACTIONS))
        info['parts'] = S.index; info['stature_m'] = H; info['objects'] = len(S.index)
        info['vertices'] = {o.name: len(o.data.vertices) for c in root_c.children for o in c.objects if o.type == 'MESH'}
        for name, text_ in (('WF_EVA_SUIT_SNAPSHOT', (root/'data/eva_suit.toml').read_text()),):
            t = bpy.data.texts.get(name) or bpy.data.texts.new(name); t.clear(); t.write(text_)
        if not args.no_save:
            save(path, root_c, spec_text, source_text)
        report['variants'][key] = info
        print(f"WF_EVA {key} parts={len(S.index)} verts={sum(info['vertices'].values())} actions={len(acts)}", flush=True)
    if args.report:
        args.report.write_text(json.dumps(report, indent=1)+'\n')


if __name__ == '__main__':
    main()
