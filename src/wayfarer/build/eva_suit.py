"""WAYFARER_EVA_Y155 on the induction pair (TODO EVA-001, docs/EVA.md; S&E 44 ASSET-01..15, RIG-02..04, ANIM-01..08, RUN-005..009).

  blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/build/eva_suit.py -- [--only instructor newcomer]
          [--report references/p1_eva_suit.json]

Per variant of data/eva_suit.toml the wearer's built character (assets/characters/WF_CHAR_HUMAN_<ID>.blend, `workflow.py characters`) is
appended unchanged (rig, body, correctives, shared actions) and dressed into assets/characters/WF_EVA_<ID>.blend:

- soft layers (LCVG, pressure bladder, restraint + thermal/MMOD outer) are offset shells of the wearer's own body, smoothed and skinned
  with its weights and corrective shape keys, so every existing action still drives them and the bladder stays continuous;
- rigid parts (hard upper torso, waist and neck rings, helmet and visors, PLSS and its internals, chest display, bearings, convolutes,
  gauntlets, soles and toe hooks, tether reels and hooks, the inspection tool, markings) are sized from the measured body and parented
  to bones; the helmet is fixed to the torso and the head turns inside it;
- sockets (RIG-03/04) are bone-parented empties with stable ids; the 53-bone game_engine rig is not changed;
- the EVA actions of eva_suit.py are solved onto the rig with the shared Solver and added as NLA tracks beside the shared ones.

Every object carries `assembly`, `part_id` (WAYFARER_EVA_Y155/<ASSEMBLY>/<PART>), `job` and `geometry_status = PROTOTYPE`. Collections
follow RUN-005: WAYFARER_EVA_Y155 / PRESSURE / PROTECTION / JOINTS / HELMET / PLSS / COOLING / TETHERS / TOOLS / MARKINGS / RIG. The full
body stays in the file (hidden, `eva_role = validation_body`) for the coverage check; the runtime head is a copy with the covered faces
removed. Nothing here is CERTIFIED.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/components')]
import eva_suit as es
import human_system as hs
from common import OWNER, begin, save
from human import Solver, bake_action
from spec import load

HAND_BONES = {f'{f}_{k:02d}_{s}' for s in 'lr' for f in ('thumb', 'index', 'middle', 'ring', 'pinky') for k in (1, 2, 3)} | {'hand_l', 'hand_r'}
FOOT_BONES = {'foot_l', 'foot_r', 'ball_l', 'ball_r'}
FINGERS = [f'{f}_{k:02d}' for f in ('index', 'middle', 'ring', 'pinky') for k in (1, 2, 3)]
THUMB = [f'thumb_{k:02d}' for k in (1, 2, 3)]


# ---------------------------------------------------------------------------------------------------------------------- materials
def mat(name, rgb, rough=.7, metal=0.0, alpha=1.0, emit=0.0):
    m = bpy.data.materials.get(f'WF_EVA_{name}') or bpy.data.materials.new(f'WF_EVA_{name}')
    m['wf_owner'] = OWNER; m.use_nodes = True; m.diffuse_color = (*rgb, alpha)
    bs = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bs.inputs['Base Color'].default_value = (*rgb, 1); bs.inputs['Roughness'].default_value = rough; bs.inputs['Metallic'].default_value = metal
    if alpha < 1:
        bs.inputs['Alpha'].default_value = alpha; m.surface_render_method = 'BLENDED'
    if emit:
        bs.inputs['Emission Color'].default_value = (*rgb, 1); bs.inputs['Emission Strength'].default_value = emit
    return m


def materials(pal, variant):
    band = pal[variant['role_band']]
    return dict(shell=mat('Shell', pal['shell'], .78), grey=mat('Shell_Grey', pal['shell_grey'], .7), joint=mat('Joint', pal['joint'], .6),
                bladder=mat('Bladder', pal['bladder'], .5), lcvg=mat('LCVG', pal['lcvg'], .55), band=mat(f"Band_{variant['role_band']}", band, .65),
                gu=mat('GU_Blue', pal['gu_blue'], .6), orange=mat('Safety_Orange', pal['safety_orange'], .55),
                visor=mat('Glare_Visor', pal['visor'], .12, .9), glass=mat('Pressure_Visor', pal['glass'], .05, 0.0, .28),
                metal=mat('Metal', pal['metal'], .35, .9), glove=mat('Glove', pal['joint'], .75), display=mat('Display', (.10, .22, .26), .3, 0.0, 1.0, .6),
                hw=mat('PLSS_Hardware', (.40, .42, .44), .5, .5), tank=mat('O2_Tank', (.30, .55, .30), .45, .3),
                reserve=mat('O2_Reserve', (.78, .70, .18), .45, .2), co2=mat('CO2_Cartridge', (.50, .45, .60), .5),
                hx=mat('Heat_Exchanger', (.70, .72, .74), .3, .8), battery=mat('Battery', (.18, .18, .20), .6))


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


def torus(name, centre, axis, R, r, material, n=40, m=10, scale=(1.0, 1.0), section=(1.0, 1.0)):
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


def box(name, centre, axes, half, material, bevel=0.0):
    ax = [Vector(a).normalized() for a in axes]; verts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                verts.append(Vector(centre)+ax[0]*sx*half[0]+ax[1]*sy*half[1]+ax[2]*sz*half[2])
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    o = new_mesh(name, verts, faces, material)
    for p in o.data.polygons:
        p.use_smooth = False
    if bevel:
        mod = o.modifiers.new('bevel', 'BEVEL'); mod.width = bevel; mod.segments = 3
        bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier=mod.name)
    return o


def sphere_cap(name, centre, R, fwd, up, lat0, lat1, material, n=48, m=24, hole=None):
    """Part of a sphere between latitudes lat0..lat1 (deg, about `up`); hole(dir) -> True skips faces whose centre direction is in it."""
    z = up.normalized(); y = (fwd-z*fwd.dot(z)).normalized(); x = y.cross(z); verts = []; faces = []
    for k in range(m+1):
        la = math.radians(lat0+(lat1-lat0)*k/m)
        for i in range(n):
            a = 2*math.pi*i/n; verts.append(centre+(x*math.cos(a)*math.cos(la)+y*math.sin(a)*math.cos(la)+z*math.sin(la))*R)
    for k in range(m):
        for i in range(n):
            q = (k*n+i, k*n+(i+1) % n, (k+1)*n+(i+1) % n, (k+1)*n+i)
            c = sum((verts[j] for j in q), Vector())/4-centre
            if hole is None or not hole(c.normalized(), x, y, z):
                faces.append(q)
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


# ---------------------------------------------------------------------------------------------------------------------- build
def dress(rig, body, data, variant, key):
    S = Part(bpy.data.collections['WAYFARER_EVA_Y155'], data, rig); M = materials(data['palette'], variant); L = data['layers']; R = data['rigid']
    rig.data.pose_position = 'REST'; bpy.context.view_layer.update(); dom = dominant(body)
    reg_o, reg_s, unc = L['region_offset_m'], L['region_smooth'], L['uncovered_groups']
    layers = {}
    for name, mat_, extra in (('LCVG_INNER', M['lcvg'], {}), ('SUIT_PRESSURE_BLADDER', M['bladder'], {}),
                              ('MMOD_OUTER_SHELL', M['shell'], dict(hand_mat=M['glove'], foot_mat=M['grey']))):
        q = L[name]; scale = q['offset_m']/L['MMOD_OUTER_SHELL']['offset_m']
        o = offset_layer(body, f'EVA_{key}_{name}', q['offset_m'], q['smooth'], {k: v*scale for k, v in reg_o.items()},
                         {k: min(v, q['smooth']) for k, v in reg_s.items()}, unc, dom, mat_, **extra)
        asm = {'LCVG_INNER': 'COOLING', 'SUIT_PRESSURE_BLADDER': 'PRESSURE', 'MMOD_OUTER_SHELL': 'PROTECTION'}[name]
        layers[name] = S.put(o, asm, name, q['job'], q['show'])
    outer = layers['MMOD_OUTER_SHELL']; odom = dominant(outer)
    outer.data.materials.append(M['joint']); ji = len(outer.data.materials)-1
    zones = [(bone(rig, f'{b_}_{s_}')[0], r_) for b_, r_ in (('lowerarm', .085), ('calf', .105)) for s_ in 'lr']
    for poly in outer.data.polygons:                     # restraint convolute zones in charcoal (RUN-017), the rest stays off-white
        if poly.material_index == 0 and any((poly.center-c_).length < r_ for c_, r_ in zones):
            poly.material_index = ji
    pts = lambda bones: outer_points(outer, odom, bones)
    W = lambda b: bone(rig, b)
    # ---- hard upper torso (rigid, spine_03) from the outer layer's chest sections
    s2, _ = W('spine_02'); s3, _ = W('spine_03'); nk, _ = W('neck_01'); torso = pts({'spine_02', 'spine_03', 'clavicle_l', 'clavicle_r', 'neck_01'})
    z0 = s2.z+.04; z1 = nk.z-.035; rings = []; levels = 9
    for k in range(levels+1):
        z = z0+(z1-z0)*k/levels; band = [p for p in torso if abs(p.z-z) < .02] or torso
        hw = max(abs(p.x) for p in band); ys = [p.y for p in band]; yc = (max(ys)+min(ys))/2; hd = (max(ys)-min(ys))/2
        taper = 1.0 if k < levels-2 else (.86 if k == levels-1 else .62)
        rings.append((z, (hw+R['hut_margin_m'])*taper, hd+R['hut_margin_m'], yc))
    verts = []; faces = []; n = 40
    for z, a, b, yc in rings:
        for i in range(n):
            t = 2*math.pi*i/n; verts.append(Vector((a*math.cos(t), yc+b*math.sin(t), z)))
    for k in range(len(rings)-1):
        faces += [(k*n+i, k*n+(i+1) % n, (k+1)*n+(i+1) % n, (k+1)*n+i) for i in range(n)]
    hut = new_mesh(f'EVA_{key}_HUT', verts, faces, M['shell'])
    sol = hut.modifiers.new('shell', 'SOLIDIFY'); sol.thickness = R['hut_shell_m']; sol.offset = 1.0
    bpy.context.view_layer.objects.active = hut; bpy.ops.object.modifier_apply(modifier=sol.name)
    S.put(hut, 'PRESSURE', 'SUIT_PRESSURE_HARD_TORSO', 'rigid/hybrid hard upper torso: load-bearing pressure shell with bearing and seal rings (EVA-021, ASSET-02); ingress concept OPEN', bone='spine_03')
    zb, ab, bb, yb = rings[0]; zt, at, bt, yt = rings[-1]
    S.put(torus(f'EVA_{key}_Waist_Ring', Vector((0, yb, zb)), Vector((0, 0, 1)), 1.0, .018, M['joint'], scale=(ab+.006, bb+.006)),
          'PRESSURE', 'SUIT_WAIST_RING', 'body seal closure: hard torso to lower torso pressure seal (EVA-005)', bone='spine_02')
    neck_c = Vector((0, yt, zt+.012)); neck_R = max(at, bt)*.92
    S.put(torus(f'EVA_{key}_Neck_Ring', neck_c, Vector((0, 0, 1)), neck_R, .020, M['metal']), 'PRESSURE', 'SUIT_NECK_RING',
          'helmet neck ring: sealed mechanical interface, helmet locks here (EVA-005, ASSET-06)', bone='spine_03')
    # ---- helmet: fixed to the torso; head room for head motion; visor window, glare visor raised
    head_pts = [v.co.copy() for v, u in zip(body.data.vertices, in_groups(body, unc)) if u]
    hc = sum(head_pts, Vector())/len(head_pts); hc.y -= R['helmet_forward_m']
    hR = max((p-hc).length for p in head_pts)+R['helmet_clearance_m']; hR = max(hR, (neck_c-hc).length+.01)
    fwd = Vector((0, -1, 0)); up = Vector((0, 0, 1)); hx, vy = (math.radians(a) for a in R['visor_half_angle_deg'])
    lat_neck = math.degrees(math.asin(max(-1, min(1, (neck_c.z-hc.z)/hR))))
    def window(d, x, y, z):
        az = math.atan2(d.dot(x), d.dot(y)); el = math.asin(max(-1, min(1, d.dot(z)))); return abs(az) < hx and -vy*1.1 < el < vy*.8
    helmet = sphere_cap(f'EVA_{key}_Helmet_Shell', hc, hR, fwd, up, lat_neck, 90.0, M['shell'], hole=window)
    sol = helmet.modifiers.new('shell', 'SOLIDIFY'); sol.thickness = .008; sol.offset = 1.0
    bpy.context.view_layer.objects.active = helmet; bpy.ops.object.modifier_apply(modifier=sol.name)
    S.put(helmet, 'HELMET', 'SUIT_HELMET_VISOR', 'sealed helmet pressure shell, independent of the visor assemblies (EVA-023, ASSET-06)', bone='spine_03')
    S.put(sphere_cap(f'EVA_{key}_Pressure_Visor', hc, hR-.002, fwd, up, lat_neck, 90.0, M['glass'], hole=lambda d, x, y, z: not window(d, x, y, z)),
          'HELMET', 'SUIT_HELMET_VISOR', 'clear pressure visor with anti-fog/thermal treatment; never opened in vacuum (EVA-023)', bone='spine_03')
    S.put(sphere_cap(f'EVA_{key}_Glare_Visor', hc, hR+.012, fwd, up, 18.0, 62.0, M['visor'],
                     hole=lambda d, x, y, z: abs(math.atan2(d.dot(x), d.dot(y))) > hx*1.05),
          'HELMET', 'SUIT_HELMET_VISOR', 'retractable glare visor, shown raised: shutter for sunlit work (EVA-023)', bone='spine_03')
    side = Vector((1, 0, 0))
    for sg in (1, -1):
        S.put(tube(f'EVA_{key}_Visor_Pivot_{"lr"[sg < 0]}', hc+side*sg*(hR-.004), hc+side*sg*(hR+.014), .024, M['metal'], n=20), 'HELMET', 'SUIT_HELMET_VISOR',
              'visor assembly pivot: the glare visor and the protective shell rotate about it (EVA-023)', bone='spine_03')
        pod = hc+side*sg*(hR+.026)+up*(hR*.32)+fwd*(hR*.18)
        S.put(box(f'EVA_{key}_Helmet_Light_{"lr"[sg < 0]}', pod, (side, fwd, up), (.016, .045, .020), M['grey'], bevel=.006), 'HELMET', 'SUIT_HELMET_VISOR',
              'helmet light and camera pod: work lights and the helmet camera for the remote supervisor (ASSET-06, Tale 26 remote views)', bone='spine_03')
        S.put(box(f'EVA_{key}_Helmet_Light_{"lr"[sg < 0]}_Lens', pod+fwd*.046, (side, fwd, up), (.012, .002, .010), M['display']), 'HELMET', 'SUIT_HELMET_VISOR',
              'work light lens', bone='spine_03')
        S.put(tube(f'EVA_{key}_Helmet_Cam_{"lr"[sg < 0]}', pod+up*.026+fwd*.02, pod+up*.026+fwd*.05, .007, M['visor'], n=12), 'HELMET', 'SUIT_HELMET_VISOR',
              'helmet camera', bone='spine_03')
    S.put(torus(f'EVA_{key}_Helmet_Band', hc+up*(hR*.25), up, hR*math.cos(math.asin(.25))+.004, .010, M['band'], n=48, m=6),
          'MARKINGS', 'SAFETY_MARKINGS', 'helmet identification band: ' + variant['markings'], bone='spine_03')
    # ---- PLSS on the back (+Y) of the hard torso
    w, dpt, h = R['plss_size_m']; back = max(p.y for p in torso)+R['hut_margin_m']+R['hut_shell_m']
    pc = Vector((0, back+dpt/2+.01, (z0+z1)/2+.02))
    # Two stacked replaceable modules (upper: oxygen storage and regulation; lower: CO2 removal, fan / pump / separator, battery, radio) with
    # the old pack's outer form (same width, depth and bevel), so the convex hulls the access study measures are unchanged (RUN-010); a
    # recessed interface band between them, keyed latches, side rescue handles (the pack handle a rescuer holds, eva_rescue_hold) placed
    # inside the shoulder-to-pack hull, a heat-rejection vent and the access covers within the old covers' 8 mm.
    A3 = ((1, 0, 0), (0, 1, 0), (0, 0, 1)); split = .012
    hu = (h-split)*.52; hl = h-split-hu; zb = pc.z-h/2; zl = zb+hl/2; zu = zb+hl+split+hu/2
    S.put(box(f'EVA_{key}_PLSS', Vector((0, pc.y, zu)), A3, (w/2, dpt/2, hu/2), M['shell'], bevel=.025), 'PLSS', 'PLSS_PRIMARY',
          'upper PLSS module: primary oxygen storage and regulation; packaging and mass OPEN (ASSET-09, EVA-024, EVA-028)', bone='spine_03')
    S.put(box(f'EVA_{key}_PLSS_Lower', Vector((0, pc.y, zl)), A3, (w/2, dpt/2, hl/2), M['shell'], bevel=.025), 'PLSS', 'PLSS_PRIMARY',
          'lower PLSS module: CO2 removal, fan / pump / separator, battery and radio; a separately replaceable unit (ASSET-09)', bone='spine_03')
    S.put(box(f'EVA_{key}_PLSS_Split', Vector((0, pc.y, zb+hl+split/2)), A3, (w/2-.012, dpt/2-.012, split/2+.002), M['joint']), 'PLSS', 'PLSS_PRIMARY',
          'module interface: seal and connector plane between the two PLSS modules', bone='spine_03')
    for sg in (1, -1):
        for zz in (zb+hl-.016, zb+hl+split+.016):
            S.put(box(f'EVA_{key}_PLSS_Latch_{"lr"[sg < 0]}_{int(zz*1000)}', Vector((sg*(w/2-.05), pc.y+dpt/2+.003, zz)), A3, (.014, .003, .008), M['metal']),
                  'PLSS', 'PLSS_PRIMARY', 'module latch (tool-operated, keyed)', bone='spine_03')
        hx = sg*(w/2+.022); hy = pc.y-dpt*.30
        for zz in (zu-hu*.30, zu+hu*.22):
            S.put(tube(f'EVA_{key}_PLSS_Handle_Post_{"lr"[sg < 0]}_{int(zz*1000)}', Vector((sg*w/2, hy, zz)), Vector((hx, hy, zz)), .007, M['grey'], n=12),
                  'PLSS', 'PLSS_PRIMARY', 'rescue handle standoff', bone='spine_03')
        S.put(tube(f'EVA_{key}_PLSS_Handle_{"lr"[sg < 0]}', Vector((hx, hy, zu-hu*.30)), Vector((hx, hy, zu+hu*.22)), .010, M['grey'], n=16),
              'PLSS', 'PLSS_PRIMARY', 'side rescue / handling handle (eva_rescue_hold); inside the shoulder-to-pack hull', bone='spine_03')
    face = pc.y+dpt/2
    for nm, cx, cz, hx_, hz in (('Cover_Upper', -w*.10, zu, w*.26, hu*.34), ('Cover_Lower', 0.0, zl, w*.38, hl*.32)):
        S.put(box(f'EVA_{key}_PLSS_{nm}', Vector((cx, face+.003, cz)), A3, (hx_, .003, hz), M['grey']),
              'PLSS', 'PLSS_PRIMARY', 'PLSS access panel: replaceable module boundary (ASSET-09 "distinct access hatches")', bone='spine_03')
        for sx in (-1, 1):
            for sz in (-1, 1):
                q = Vector((cx+sx*(hx_-.012), face+.005, cz+sz*(hz-.012)))     # heads end at the old cover face (face + 0.008)
                S.put(tube(f'EVA_{key}_PLSS_{nm}_Fastener_{sx}{sz}', q, q+Vector((0, .003, 0)), .005, M['metal'], n=8), 'PLSS', 'PLSS_PRIMARY',
                      'captive panel fastener', bone='spine_03')
    for k in range(6):
        S.put(box(f'EVA_{key}_PLSS_Vent_{k}', Vector((w*.29, face+.003, zu-hu*.30+k*hu*.12)), A3, (w*.09, .003, .004), M['joint']), 'PLSS', 'PLSS_PRIMARY',
              'heat-rejection vent louvre (evaporator / radiator exhaust; heat rejection OPEN, EVA-009)', bone='spine_03')
    S.put(box(f'EVA_{key}_PLSS_ID', Vector((w*.29, face+.002, zl+hl*.25)), A3, (w*.08, .002, .018), M['gu'] if variant['role_band'] == 'gu_blue' else M['band']),
          'MARKINGS', 'SAFETY_MARKINGS', 'PLSS identification plate: ' + variant['markings'], bone='spine_03')
    inner = [  # internals, shown in the cutaway (RUN-008, EXP-04); placement is a display layout, not packaging
        ('O2_Primary_1', 'tube', Vector((-w*.30, pc.y, pc.z+h*.05)), (.045, h*.70), M['tank'], 'primary oxygen storage (EVA-008)'),
        ('O2_Primary_2', 'tube', Vector((-w*.12, pc.y, pc.z+h*.05)), (.045, h*.70), M['tank'], 'primary oxygen storage (EVA-008)'),
        ('O2_Emergency_Reserve', 'tube', Vector((w*.30, pc.y+dpt*.12, pc.z-h*.28)), (.035, h*.32), M['reserve'], 'separate emergency oxygen reserve, independent regulator (EVA-008, EVA-026)'),
        ('O2_Regulator', 'box', Vector((w*.06, pc.y, pc.z+h*.36)), (.05, .04, .035), M['hw'], 'oxygen pressure regulator; suit setpoint OPEN (EVA-004)'),
        ('CO2_Cartridge', 'box', Vector((w*.16, pc.y, pc.z+h*.10)), (.06, dpt*.36, .09), M['co2'], 'replaceable/regenerable CO2 removal cartridge (53!7)'),
        ('Fan_Pump_Separator', 'tube', Vector((w*.30, pc.y, pc.z+h*.12)), (.045, .10), M['hw'], 'ventilation fan, cooling-water pump and water separator (53!6, 53!8)'),
        ('Heat_Exchanger', 'box', Vector((0.0, pc.y+dpt*.30, pc.z+h*.42)), (w*.42, dpt*.10, .05), M['hx'], 'primary heat exchanger / evaporator, emergency cooling branch (EVA-009, 53!9)'),
        ('Battery', 'box', Vector((-w*.20, pc.y, pc.z-h*.36)), (w*.18, dpt*.34, .06), M['battery'], 'PLSS battery'),
        ('Radio_Telemetry', 'box', Vector((w*.08, pc.y, pc.z-h*.38)), (.07, dpt*.30, .045), M['hw'], 'radio, telemetry and emergency beacon; antenna protected in the shell (EVA-019)')]
    for nm, kind, c, size, mt, job in inner:
        o = tube(f'EVA_{key}_PLSS_{nm}', c-Vector((0, 0, size[1]/2)), c+Vector((0, 0, size[1]/2)), size[0], mt) if kind == 'tube' else \
            box(f'EVA_{key}_PLSS_{nm}', c, ((1, 0, 0), (0, 1, 0), (0, 0, 1)), size, mt)
        S.put(o, 'PLSS', 'PLSS_PRIMARY', job, 'cutaway', bone='spine_03')
    for nm, x, mt, job in (('SCU_Port', -w/2-.012, M['metal'], 'umbilical port: recharge from certified ship supplies (53!6)'),
                           ('Cooling_Port', w/2+.012, M['metal'], 'cooling-loop quick disconnect (53!8)')):
        S.put(tube(f'EVA_{key}_PLSS_{nm}', Vector((x-math.copysign(.02, x)*0, pc.y-dpt*.2, pc.z-h*.30)), Vector((x+math.copysign(.03, x), pc.y-dpt*.2, pc.z-h*.30)), .018, mt),
              'PLSS', 'PLSS_PRIMARY', job, bone='spine_03')
    S.put(tube(f'EVA_{key}_PLSS_Purge_Valve', Vector((w*.36, pc.y, pc.z-h/2)), Vector((w*.36, pc.y, pc.z-h/2-.035)), .016, M['orange']),
          'MARKINGS', 'SAFETY_MARKINGS', 'emergency reserve actuator, safety orange (EVA-026)', bone='spine_03')
    # ---- chest display/control module and the left wrist display (EVA-018)
    front = min(p.y for p in torso)-R['hut_margin_m']-R['hut_shell_m']; dw, dd, dh = R['dcm_size_m']
    dcm_c = Vector((0, front-dd/2, (z0+z1)/2-.02))
    S.put(box(f'EVA_{key}_DCM', dcm_c, ((1, 0, 0), (0, 1, 0), (0, 0, 1)), (dw/2, dd/2, dh/2), M['grey'], bevel=.01), 'PLSS', 'PLSS_PRIMARY',
          'chest display and control module: suit status, warnings, tether count (EVA-018); no unreleased value is displayed', bone='spine_03')
    S.put(box(f'EVA_{key}_DCM_Display', dcm_c+Vector((0, -dd/2-.002, .01)), ((1, 0, 0), (0, 1, 0), (0, 0, 1)), (dw*.34, .002, dh*.28), M['display']),
          'PLSS', 'PLSS_PRIMARY', 'DCM status display', bone='spine_03')
    la, lb = W('lowerarm_l'); armr = radius_about(pts({'lowerarm_l'}), la, lb, .55, .85)
    wd = la.lerp(lb, .72); out_ = (wd-la).cross(Vector((0, 0, 1))).normalized()
    S.put(box(f'EVA_{key}_Wrist_Display', wd+Vector((0, -1, 0))*(armr+.012), (lb-la, Vector((0, -1, 0)), (lb-la).cross(Vector((0, -1, 0)))), (.045, .012, .030), M['display']),
          'PLSS', 'PLSS_PRIMARY', 'forearm status display and checklist (EVA-018)', bone='lowerarm_l')
    # ---- bearings and convolutes (ASSET-05): ring radius = the outer layer's local radius plus clearance
    def bearing(nm, bone_axis, t, parent, minor=None, mat_=None, part='SUIT_JOINTS', job='rotary bearing: low-torque pressure-compatible rotation (53!14)'):
        a, b = W(bone_axis); src = pts({bone_axis}); c, rr = section(src, a, b, max(0, t-.05), min(1, t+.05)); rr = rr or .06
        mn = minor or R['bearing_minor_m']; ax = (b-a).normalized()
        if 'Convolute' in nm:                       # bellows: three restraint ribs a rib-pitch apart
            for k, off in enumerate((-1.6, 0.0, 1.6)):
                S.put(torus(f'EVA_{key}_{nm}_{k}', c+ax*off*mn, b-a, rr+R['bearing_clearance_m']-mn*.1, mn*.8, mat_ or M['joint'], m=8),
                      'JOINTS', part, job, bone=parent)
            return rr
        if nm.startswith('Scye'):                    # the scye ring sets the torso width the owner quotes (45 G-01/G-02): unchanged
            S.put(torus(f'EVA_{key}_{nm}', c, b-a, rr+R['bearing_clearance_m']-mn*.2, mn, mat_ or M['joint']), 'JOINTS', part, job, bone=parent)
            return rr
        # a rotary bearing: a flat machined band with a race at each edge, inside the old ring's envelope (axial +-mn, radial rr + .8 mn);
        # the access-study hull classes were re-measured unchanged (docs/ACCESSORIES.md)
        S.put(torus(f'EVA_{key}_{nm}', c, b-a, rr+R['bearing_clearance_m'], mn, mat_ or M['joint'], m=12, section=(.55, 1.0)), 'JOINTS', part, job, bone=parent)
        for k, sg in enumerate((-1, 1)):
            S.put(torus(f'EVA_{key}_{nm}_Race{k}', c+ax*sg*mn*.72, b-a, rr+R['bearing_clearance_m']+mn*.2, mn*.28, M['metal'], m=6),
                  'JOINTS', part, 'bearing race / disconnect ring', bone=parent)
        return rr
    for s in 'lr':
        bearing(f'Scye_Bearing_{s}', f'upperarm_{s}', .10, 'spine_03', .020, job='scye (shoulder) bearing on the hard torso (EVA-022, 53!14)')
        bearing(f'Upperarm_Bearing_{s}', f'upperarm_{s}', .55, f'upperarm_{s}')
        bearing(f'Elbow_Convolute_{s}_dn', f'lowerarm_{s}', .12, f'lowerarm_{s}', .009, job='elbow convolute: restraint-held flexible pressure section (ASSET-05)')
        bearing(f'Elbow_Convolute_{s}_up', f'upperarm_{s}', .88, f'upperarm_{s}', .009, job='elbow convolute (ASSET-05)')
        bearing(f'Wrist_Bearing_{s}', f'lowerarm_{s}', .96, f'lowerarm_{s}', .016, M['metal'], 'SUIT_GLOVES', 'glove wrist disconnect and bearing: sealed cuff (ASSET-07)')
        bearing(f'Hip_Bearing_{s}', f'thigh_{s}', .10, 'pelvis', .020, job='hip bearing (53!14)')
        bearing(f'Thigh_Bearing_{s}', f'thigh_{s}', .55, f'thigh_{s}')
        bearing(f'Knee_Convolute_{s}_dn', f'calf_{s}', .10, f'calf_{s}', .010, job='knee convolute (ASSET-05)')
        bearing(f'Knee_Convolute_{s}_up', f'thigh_{s}', .90, f'thigh_{s}', .010, job='knee convolute (ASSET-05)')
        bearing(f'Ankle_Bearing_{s}', f'calf_{s}', .90, f'calf_{s}', .016, job='ankle bearing and boot seal (ASSET-08)')
        # gauntlet cuff
        a, b = W(f'lowerarm_{s}'); hr_ = radius_about(pts({f'lowerarm_{s}'}), a, b, .85, 1.0) or .05; d = (b-a).normalized()
        S.put(tube(f'EVA_{key}_Gauntlet_{s}', b-d*.02, b+d*.05, hr_+.020, M['grey'], r_b=hr_+.028), 'JOINTS', 'SUIT_GLOVES',
              'glove gauntlet: thermal/MMOD cuff over the wrist disconnect (ASSET-07)', bone=f'hand_{s}')
        # boots: heel/arch sole on the foot, toe sole and toe hook on the ball (foot-restraint compatible)
        fa, fb = W(f'foot_{s}'); ba, bb = W(f'ball_{s}'); sw, sl, st = R['boot_sole_m']
        fd = Vector((fb.x-fa.x, fb.y-fa.y, 0)).normalized(); side = fd.cross(Vector((0, 0, 1)))
        heel = Vector((fa.x, fa.y, 0))-fd*.06; toe = Vector((bb.x, bb.y, 0))+fd*.03; ballp = Vector((ba.x, ba.y, 0))
        S.put(box(f'EVA_{key}_Sole_{s}', (heel+ballp)/2+Vector((0, 0, st/2-.004)), (side, fd, Vector((0, 0, 1))), (sw/2, (ballp-heel).length/2, st/2), M['joint'], bevel=.006),
              'JOINTS', 'SUIT_BOOTS', 'rigid service sole (ASSET-08): no tread, foot-restraint interface', bone=f'foot_{s}')
        S.put(box(f'EVA_{key}_Toe_Sole_{s}', (ballp+toe)/2+Vector((0, 0, st/2-.004)), (side, fd, Vector((0, 0, 1))), (sw/2*.92, (toe-ballp).length/2, st/2), M['joint'], bevel=.006),
              'JOINTS', 'SUIT_BOOTS', 'flexible toe sole', bone=f'ball_{s}')
        S.put(box(f'EVA_{key}_Toe_Hook_{s}', toe+Vector((0, 0, .055)), (side, fd, Vector((0, 0, 1))), (sw*.35, .012, .02), M['metal']),
              'JOINTS', 'SUIT_BOOTS', 'toe hook for a foot restraint (ASSET-08)', bone=f'ball_{s}')
        # arm identification bands (EXP-03)
        a, b = W(f'upperarm_{s}'); cb, rr = section(pts({f'upperarm_{s}'}), a, b, .28, .42); rr = rr or .07
        S.put(torus(f'EVA_{key}_Arm_Band_{s}', cb, b-a, rr+.004, .006, M['band'], m=6, n=40), 'MARKINGS', 'SAFETY_MARKINGS',
              'upper-arm identification band: ' + variant['markings'], bone=f'upperarm_{s}')
    if variant['role_band'] == 'gu_blue':
        S.put(box(f'EVA_{key}_GU_Chest_Plate', Vector((0, front+.002, z1-.06)), ((1, 0, 0), (0, 1, 0), (0, 0, 1)), (.10, .003, .025), M['gu']),
              'MARKINGS', 'SAFETY_MARKINGS', 'Great Union deep-blue certified identification plate (Y155 era, EVA-025)', bone='spine_03')
    # ---- tethers (ASSET-13): two independent waist reels with hooks, safety orange; lines are drawn by the runtime
    pa, _ = W('pelvis'); hips = pts({'pelvis', 'spine_01'}); hw_ = max(abs(p.x) for p in hips)+.03
    for side, sg, tag in (('A', 1, 'l'), ('B', -1, 'r')):
        c = Vector((sg*hw_, pa.y-.02, s2.z-.02))
        S.put(tube(f'EVA_{key}_Tether_Reel_{side}', c, c+Vector((sg*.035, 0, 0)), .040, M['orange']), 'TETHERS', 'TETHERS',
              f'waist tether reel {side}: one of two independent restraints (EVA-014, ANIM-06); length OPEN (SIM-03)', bone='pelvis')
        hk = c+Vector((sg*.05, -.05, -.02))
        S.put(torus(f'EVA_{key}_Tether_Hook_{side}', hk, Vector((1, 0, 0)), .018, .005, M['metal'], n=20, m=6), 'TETHERS', 'TETHERS',
              f'tether {side} hook, captive gate', bone='pelvis')
        sock = bpy.data.objects.new(f'SOCKET_TETHER_{side}', None); bpy.context.scene.collection.objects.link(sock); sock.location = hk
        sock.empty_display_size = .05; S.put(sock, 'RIG', 'SOCKETS', f'tether {side} hook socket (RIG-04): runtime line start', bone='pelvis')
    # ---- tool (ASSET-14): inspection scanner/dosimeter stowed on the chest bracket, wrist lanyard ring
    tc = Vector((-.10, front-.03, z0+.03))
    S.put(box(f'EVA_{key}_Tool_Scanner', tc, ((1, 0, 0), (0, 1, 0), (0, 0, 1)), (.03, .02, .06), M['grey'], bevel=.006), 'TOOLS', 'TOOLS',
          'inspection scanner / dosimeter with retained lanyard; stowed on the chest bracket (ASSET-14, EVA-020)', bone='spine_03')
    S.put(torus(f'EVA_{key}_Tool_Lanyard_Ring', tc+Vector((0, 0, -.07)), Vector((0, 1, 0)), .012, .003, M['orange'], n=16, m=6), 'TOOLS', 'TOOLS',
          'tool retention lanyard ring (EVA-020)', bone='spine_03')
    # ---- sockets (RIG-03/04)
    for nm, bn, loc, job in [('SOCKET_HAND_L_GRIP', 'hand_l', None, 'left palm grip contact (RIG-04)'), ('SOCKET_HAND_R_GRIP', 'hand_r', None, 'right palm grip contact (RIG-04)'),
                             ('SOCKET_HAND_R_TOOL', 'hand_r', None, 'tool equipped pose (ASSET-14)'), ('SOCKET_TOOL_STOW', 'spine_03', tc, 'tool stow pose (ASSET-14)'),
                             ('SOCKET_TOE_HOOK_L', 'ball_l', None, 'left toe hook'), ('SOCKET_TOE_HOOK_R', 'ball_r', None, 'right toe hook'),
                             ('SOCKET_PLSS_SCU', 'spine_03', pc+Vector((-w/2-.03, -dpt*.2, -h*.30)), 'umbilical port'),
                             ('SOCKET_HELMET_EYE', 'spine_03', hc+Vector((0, -.04, .0)), 'eye point for a first-person camera inside the helmet'),
                             ('SOCKET_HUD', 'spine_03', hc+fwd*(hR*.85)+Vector((0, 0, -.04)), 'in-view display plane (EVA-018)')]:
        if loc is None:
            h0, h1 = W(bn); loc = h1 if bn.startswith('hand') else (h0+h1)/2
        e = bpy.data.objects.new(nm, None); bpy.context.scene.collection.objects.link(e); e.location = loc; e.empty_display_size = .04
        S.put(e, 'RIG', 'SOCKETS', job, bone=bn)
    rig.data.pose_position = 'POSE'
    return S, dict(hut_rings=[[round(x, 4) for x in r_] for r_ in rings], helmet_centre=[round(x, 4) for x in hc], helmet_radius_m=round(hR, 4),
                   plss_centre=[round(x, 4) for x in pc], plss_size_m=R['plss_size_m'])


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
        S, info = dress(rig, body, data, v, who.upper())
        S.put(rig, 'RIG', 'SOCKETS', 'the wearer\'s unchanged MPFB game_engine rig (RIG-02): 53 bones')
        rig['eva_helmet'] = json.dumps(dict(centre=info['helmet_centre'], radius=info['helmet_radius_m'], bone='spine_03'))
        for o in rig.children:
            if o.name.startswith(f'CHAR_{who.upper()}_') and not o.name.endswith(('_Body', '_Head')) and o.get('assembly') is None:
                S.put(o, 'RIG', 'SOCKETS', 'wearer eyes, brows and lashes inside the helmet')
        S.put(body, 'RIG', 'SOCKETS', 'full wearer body for the coverage check; not exported'); body['eva_role'] = 'validation_body'
        body.hide_render = True; body.hide_viewport = True
        runtime_head(body, data['layers']['uncovered_groups'], who.upper(), S)
        # ---- EVA actions on the unchanged rig
        H = round(max(vv.co.z for vv in body.data.vertices), 4); bones = {b.name: (tuple(b.head_local), tuple(b.tail_local)) for b in rig.data.bones}
        P = hs.proportions(bones, H); lib = es.actions(H, data, fps, P); solver = Solver(rig, lib['rest']); acts = {}; info['actions'] = {}
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
        rig.animation_data.action = None
        for name, act in acts.items():
            tr = rig.animation_data.nla_tracks.new(); tr.name = name; tr.strips.new(name, 0, act); tr.mute = True
        rig['eva_suit'] = data['suit']['id']; rig['eva_variant'] = key; rig['eva_actions'] = json.dumps(list(es.EVA_ACTIONS))
        info['parts'] = S.index; info['stature_m'] = H; info['objects'] = len(S.index)
        info['vertices'] = {o.name: len(o.data.vertices) for c in root_c.children for o in c.objects if o.type == 'MESH'}
        for name, text in (('WF_EVA_SUIT_SNAPSHOT', (root/'data/eva_suit.toml').read_text()),):
            t = bpy.data.texts.get(name) or bpy.data.texts.new(name); t.clear(); t.write(text)
        if not args.no_save:
            save(path, root_c, spec_text, source_text)
        report['variants'][key] = info
        print(f"WF_EVA {key} parts={len(S.index)} verts={sum(info['vertices'].values())} actions={len(acts)}", flush=True)
    if args.report:
        args.report.write_text(json.dumps(report, indent=1)+'\n')


if __name__ == '__main__':
    main()
