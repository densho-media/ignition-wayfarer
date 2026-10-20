"""SP-11 / SP-12 / SP-13 study in the saved vehicle (EVA-002; S&E 43 EVA-043/044, 44 EVA2-003/007; docs/EVA.md).

  blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/validation/eva_airlock_study.py -- \
      [--access references/p1_eva_access.json] [--out runs/<stamp>-eva-airlock] [--renders renders/p1/eva/airlock] [--size 1280 960]

Builds each SP-11 candidate of eva_access.py (chamber shell and bulkheads, outer neck through the hull, both plug leaves shut and their
90 deg swing, the handle) and the SP-12 / SP-13 rooms with their fixtures as disposable STUDY_* collections inside the saved vehicle opened
in memory, measures them against the vehicle's meshes (intersections and least clearance to every neighbour within reach, against the
shared mechanical clearance), places the suited pair and the rescue pair as eva_access placed them, renders the sections and saves the
study scene to the run folder only. The vehicle asset is never saved; nothing becomes ship geometry (EVA-043: no pressure-shell cutout).
Writes references/p1_eva_airlock.json.
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
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/validation')]
import spec
import eva_access

EXCLUDE = ('Airlock_EVA', 'Crew_Connector_Airlock_EVA', 'Trunk_Fit_Placard_Airlock_EVA', 'Body_Envelope_Reference')
HULL = 'Hull_Forward_Collar'
NEAR = 7.0
COLORS = dict(shell=(.62, .66, .70, 1), leaf=(.85, .55, .12, 1), sweep=(.95, .62, .10, 1), room=(.40, .46, .52, 1), fixture=(.30, .52, .62, 1),
              zone=(.90, .82, .25, 1), neck=(.55, .58, .62, 1))


# ---------------------------------------------------------------------------------------------------------------------------------
# frames

def chamber_frame(fit):
    """Vehicle-frame axes of the airlock: u outward radial, X along the ship, w = X x u (human_entry's a, p, q)."""
    th = math.radians(fit['theta_deg']); u = Vector((0, math.cos(th), math.sin(th))); X = Vector((1, 0, 0)); w = Vector((0, -math.sin(th), math.cos(th)))
    return u, X, w


def world(fit, a, p, q):
    u, X, w = chamber_frame(fit); return Vector((fit['x'], 0, 0))+u*a+X*p+w*q


def material(key):
    m = bpy.data.materials.get(f'STUDY_{key}') or bpy.data.materials.new(f'STUDY_{key}'); m.use_nodes = True
    bs = m.node_tree.nodes['Principled BSDF']; bs.inputs['Base Color'].default_value = COLORS[key]; bs.inputs['Roughness'].default_value = .6
    if key in ('zone', 'sweep'):
        bs.inputs['Alpha'].default_value = .35; m.surface_render_method = 'BLENDED' if hasattr(m, 'surface_render_method') else None
    return m


def mesh_obj(name, bm, coll, key, props=None):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(material(key))
    o = bpy.data.objects.new(name, me); coll.objects.link(o)
    for k, v in (props or {}).items():
        o[k] = v
    o['wf_owner'] = 'eva.study'; o['geometry_status'] = 'STUDY ONLY: not ship geometry (EVA-043)'; return o


def tube(fit, a0, a1, r_in, r_out, phi=(0.0, 2*math.pi), n=48, closed_ends=True):
    """An annular tube (or a sector of it) along the chamber axis, as a closed bmesh."""
    bm = bmesh.new(); full = abs(phi[1]-phi[0]-2*math.pi) < 1e-9; m = n if full else n+1
    rings = []
    for a in (a0, a1):
        for r in (r_in, r_out):
            rings.append([bm.verts.new(world(fit, a, r*math.cos(phi[0]+(phi[1]-phi[0])*k/n), r*math.sin(phi[0]+(phi[1]-phi[0])*k/n))) for k in range(m)])
    (i0, o0, i1, o1) = rings
    def strip(A, B):
        for k in range(len(A)-(0 if full else 1)):
            k2 = (k+1) % len(A); bm.faces.new((A[k], A[k2], B[k2], B[k]))
    strip(o0, o1); strip(i1, i0)
    if closed_ends:
        strip(i0, o0); strip(o1, i1)
    if not full:
        bm.faces.new((i0[0], o0[0], o1[0], i1[0])); bm.faces.new((i1[-1], o1[-1], o0[-1], i0[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); return bm


def disc_points(fit, centre_a, r, n=32):
    return [world(fit, centre_a, r*math.cos(2*math.pi*k/n), r*math.sin(2*math.pi*k/n)) for k in range(n)]


def leaf_bm(fit, dr, hinge_a, hinge_deg, angle_deg, n=32):
    """The plug leaf hinged at r_hinge (azimuth hinge_deg) on the hinge face hinge_a, opened by angle_deg inboard (toward -a): a closed
    disc of the leaf thickness."""
    phi = math.radians(hinge_deg); e2 = (math.cos(phi), math.sin(phi)); c, s = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    bm = bmesh.new(); layers = []
    for z in (0.0, -dr['t']):
        ring = []
        for k in range(n):
            t = 2*math.pi*k/n; x = dr['r_leaf']*math.sin(t); y = -dr['r_hinge']+dr['r_leaf']*math.cos(t)
            y2, z2 = y*c-z*s, y*s+z*c; rho = dr['r_hinge']+y2
            ring.append(bm.verts.new(world(fit, hinge_a+z2, rho*e2[0]-x*e2[1], rho*e2[1]+x*e2[0])))
        layers.append(ring)
    bm.faces.new(layers[0]); bm.faces.new(list(reversed(layers[1])))
    for k in range(n):
        k2 = (k+1) % n; bm.faces.new((layers[0][k], layers[1][k], layers[1][k2], layers[0][k2]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); return bm


def sector(q, x0, x1, a0, a1, r0, r1, n=24, cut=None):
    """An annular-sector room shell of wall thickness 0.05 around the ship axis (closed), or, for a render (`cut`), only its floor,
    ceiling and the walls away from the camera."""
    t = .05; bm = bmesh.new()
    def P(x, az, r):
        return Vector((x, r*math.cos(math.radians(az)), r*math.sin(math.radians(az))))
    def slab(xa, xb, aa, ab, ra, rb):
        vs = [bm.verts.new(P(x, a, r)) for x in (xa, xb) for a in (aa, ab) for r in (ra, rb)]
        idx = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        for f in idx:
            bm.faces.new([vs[i] for i in f])
    steps = [a0+(a1-a0)*k/n for k in range(n+1)]
    for k in range(n):
        slab(x0, x1, steps[k], steps[k+1], r0-t, r0)                     # floor (toward the spine)
        if not cut:
            slab(x0, x1, steps[k], steps[k+1], r1, r1+t)                 # ceiling
            slab(x1, x1+t, steps[k], steps[k+1], r0, r1)                 # forward end wall
        slab(x0-t, x0, steps[k], steps[k+1], r0, r1)                     # aft end wall
    slab(x0, x1, a0-1.0, a0, r0, r1)                                     # side walls (about 1 deg thick)
    if not cut:
        slab(x0, x1, a1, a1+1.0, r0, r1)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); return bm


def box_bm(centre, ex, ey, ez, size):
    bm = bmesh.new(); h = [s/2 for s in size]
    vs = [bm.verts.new(centre+ex*sx*h[0]+ey*sy*h[1]+ez*sz*h[2]) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
        bm.faces.new([vs[i] for i in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); return bm


def fixture_bm(fx):
    """A fixture box in its room: centred on (x, az), standing radially from r0 to r1, its size (along X, tangential, radial)."""
    az = math.radians(fx['az']); ez = Vector((0, math.cos(az), math.sin(az))); ey = Vector((0, -math.sin(az), math.cos(az))); ex = Vector((1, 0, 0))
    rc = (fx['r0']+fx['r1'])/2; return box_bm(Vector((fx['x'], 0, 0))+ez*rc, ex, ey, ez, fx['size'])


# ---------------------------------------------------------------------------------------------------------------------------------
# candidate geometry

def build(row, coll, render=False):
    """Study objects of one SP-11 candidate. render=True keeps only the half of the shell away from a camera on +X."""
    fit = row['fitting']; ch = row['chamber']; dr = row['door']; wall = fit['wall_m']; R = ch['clear_radius_m']
    top, bottom = ch['outer_bulkhead_a_m'], ch['inner_bulkhead_a_m']; a_out, a_in = top-wall, bottom+wall
    phi = (math.pi, 2*math.pi) if render else (0.0, 2*math.pi)                   # the half at q < 0, away from a camera on +w
    objs = []
    objs.append(mesh_obj(f"{row['id']}_Chamber_Shell", tube(fit, a_in, a_out, R, R+wall, phi), coll, 'shell', dict(study_part='chamber_shell')))
    objs.append(mesh_obj(f"{row['id']}_Outer_Bulkhead", tube(fit, a_out, top, dr['r_clear'], R+wall, phi), coll, 'shell', dict(study_part='chamber_shell')))
    objs.append(mesh_obj(f"{row['id']}_Inner_Bulkhead", tube(fit, bottom, a_in, dr['r_clear'], R+wall, phi), coll, 'shell', dict(study_part='chamber_shell')))
    neck_r = dr['hull_penetration_outside_m']/2
    objs.append(mesh_obj(f"{row['id']}_Outer_Neck", tube(fit, top, fit['port_face_a_m'], dr['r_clear'], neck_r, phi), coll, 'neck', dict(study_part='outer_neck')))
    hinge_out = a_out-dr['frame_depth']; hinge_in = bottom-dr['frame_depth']-dr['t']     # as eva_access.chamber and human_entry.stations
    hd = ch['outer_leaf']['hinge_deg']
    objs.append(mesh_obj(f"{row['id']}_Outer_Leaf", leaf_bm(fit, dr, hinge_out, hd, 0.0), coll, 'leaf', dict(study_part='leaf')))
    objs.append(mesh_obj(f"{row['id']}_Inner_Leaf", leaf_bm(fit, dr, hinge_in, hd, 0.0), coll, 'leaf', dict(study_part='leaf')))
    if render:
        for ang in (45.0, 90.0):
            objs.append(mesh_obj(f"{row['id']}_Outer_Leaf_Swing_{int(ang)}", leaf_bm(fit, dr, hinge_out, hd, ang), coll, 'sweep', dict(study_part='sweep')))
            objs.append(mesh_obj(f"{row['id']}_Inner_Leaf_Swing_{int(ang)}", leaf_bm(fit, dr, hinge_in, hd, ang), coll, 'sweep', dict(study_part='sweep')))
    return objs


def rooms(acc, coll, render=False):
    objs = []
    for key in ('sp12', 'sp13'):
        q = acc[key]
        objs.append(mesh_obj(f"STUDY_{q['id']}_Shell", sector(q, *q['x_m'], *q['az_deg'], *q['r_m'], cut=render), coll, 'room',
                             dict(study_part='room', room=q['id'])))
        for fx in q['fixtures']:
            objs.append(mesh_obj(f"STUDY_{fx['id']}", fixture_bm(fx), coll, 'zone' if fx['kind'] == 'zone' else 'fixture',
                                 dict(study_part='fixture', room=q['id'], job=fx['job'])))
    return objs


# ---------------------------------------------------------------------------------------------------------------------------------
# checks

def evaluated(o):
    dg = bpy.context.evaluated_depsgraph_get(); e = o.evaluated_get(dg); m = e.to_mesh(); mw = o.matrix_world
    vs = [mw @ v.co for v in m.vertices]; fs = [tuple(p.vertices) for p in m.polygons]; e.to_mesh_clear(); return vs, fs


def vehicle_trees(centre):
    dg = bpy.context.evaluated_depsgraph_get(); out = []
    for inst in dg.object_instances:
        o = inst.object
        if o.type != 'MESH' or o.get('wf_owner') == 'eva.study' or o.get('kind') in ('scale_reference', 'camera') or o.name.startswith(EXCLUDE) \
                or o.name.startswith(('Human_', 'CHAR_', 'EVA_')) or o.get('assembly'):
            continue
        mw = inst.matrix_world.copy(); cs = [mw @ Vector(c) for c in o.bound_box]
        lo = Vector([min(c[i] for c in cs) for i in range(3)]); hi = Vector([max(c[i] for c in cs) for i in range(3)])
        if Vector([max(lo[i]-centre[i], 0, centre[i]-hi[i]) for i in range(3)]).length > NEAR or not o.data or not len(o.data.polygons):
            continue
        out.append((o.name, BVHTree.FromPolygons([mw @ v.co for v in o.data.vertices], [tuple(p.vertices) for p in o.data.polygons])))
    return out


def sample(vs, fs, step=.12):
    """Vertices plus points spread over each face (so a big flat face is not judged by its corners only)."""
    pts = list(vs)
    for f in fs:
        P = [vs[i] for i in f]; c = sum(P, Vector())/len(P)
        span = max((p-c).length for p in P); n = max(1, int(span/step))
        for p in P:
            pts += [c+(p-c)*k/n for k in range(1, n)]
    return pts


def clearance(objs, trees, clr):
    """Per study part: vehicle objects it intersects, the least gap to each vehicle object nearby, and the parts closer than clr."""
    out = {}
    for o in objs:
        part = o.get('study_part'); vs, fs = evaluated(o); t = BVHTree.FromPolygons(vs, fs); pts = sample(vs, fs)
        rec = out.setdefault(part, dict(intersects=set(), gaps={}))
        for name, vt in trees:
            if t.overlap(vt):
                rec['intersects'].add(name)
            least = min((h[3] for h in (vt.find_nearest(p, 1.5) for p in pts) if h[0] is not None), default=None)
            if least is not None:
                rec['gaps'][name] = round(min(least, rec['gaps'].get(name, 9.0)), 3)
    for part, rec in out.items():
        rec['intersects'] = sorted(rec['intersects'] - ({HULL} if part == 'outer_neck' else set()))
        close = {n: g for n, g in rec['gaps'].items() if g < clr and n not in rec['intersects'] and not (part == 'outer_neck' and n == HULL)}
        rec['below_clearance'] = dict(sorted(close.items(), key=lambda x: x[1])); rec['nearest'] = dict(sorted(rec['gaps'].items(), key=lambda x: x[1])[:6])
        del rec['gaps']; rec['status'] = 'CLEAR' if not rec['intersects'] and not rec['below_clearance'] else 'CONFLICT'
    return out


def internal(acc, row, room_objs, cand_objs):
    """Study-internal conflicts: fixtures against the chamber shell and the inner leaf's swing (the chamber rises through SP-12)."""
    swing = []
    fit = row['fitting']; dr = row['door']; ch = row['chamber']; hinge_in = ch['inner_bulkhead_a_m']-dr['frame_depth']-dr['t']
    for ang in (30.0, 60.0, 90.0):
        bm = leaf_bm(fit, dr, hinge_in, ch['outer_leaf']['hinge_deg'], ang); vs = [v.co.copy() for v in bm.verts]; fs = [tuple(v.index for v in f.verts) for f in bm.faces]
        bm.free(); swing.append(BVHTree.FromPolygons(vs, fs))
    shell = [BVHTree.FromPolygons(*evaluated(o)) for o in cand_objs if o.get('study_part') == 'chamber_shell']
    out = {}
    for o in room_objs:
        if o.get('study_part') != 'fixture':
            continue
        t = BVHTree.FromPolygons(*evaluated(o)); hit = [n for n, ts in (('chamber_shell', shell), ('inner_leaf_swing', swing)) if any(t.overlap(x) for x in ts)]
        out[o.name.replace('STUDY_', '')] = hit or 'CLEAR'
    return out


# ---------------------------------------------------------------------------------------------------------------------------------
# suits and renders

def append_suit(key, tag):
    path = ROOT/'assets/characters'/f'WF_EVA_{key.upper()}.blend'
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c == 'WAYFARER_EVA_Y155']
    c = dst.collections[0]; c.name = f'EVA_{key}_{tag}'; bpy.context.scene.collection.children.link(c)
    objs = list(c.all_objects); rig = next(o for o in objs if o.type == 'ARMATURE')
    for o in objs:
        if o.get('eva_role') == 'validation_body' or o.get('eva_show') == 'cutaway':
            o.hide_render = True; o.hide_viewport = True
    return rig, objs


def pose_and_place(rig, env_pose, occ, fit):
    """Pose the rig as the hull was measured and place it as eva_access placed the hull: body z along u, body (x, y) rotated by theta into
    (X, w), origin at a = a_top - zmax, shifted across the axis."""
    name, frames = env_pose['action'], env_pose['frames']; ad = rig.animation_data
    for tr in ad.nla_tracks:
        tr.mute = True
    act = bpy.data.actions[name]; ad.action = act
    if act.slots:
        ad.action_slot = act.slots[0]
    bpy.context.scene.frame_set(frames[0])
    u, X, w = chamber_frame(fit); th = math.radians(occ['theta_deg'])
    bx = X*math.cos(th)+w*math.sin(th); by = -X*math.sin(th)+w*math.cos(th)
    M = Matrix((bx, by, u)).transposed().to_4x4(); M.translation = world(fit, occ['a_top_m']-occ['zmax_m'], *occ['shift_m']); rig.matrix_world = M
    bpy.context.view_layer.update(); freeze(rig)


def freeze(rig):
    """Keep the rig in its evaluated pose whatever the scene frame does next (each rig of a scene holds its own pose and frame): the
    pose is copied into the bones and the action is unassigned."""
    basis = {b.name: b.matrix_basis.copy() for b in rig.pose.bones}; rig.animation_data.action = None
    for b in rig.pose.bones:
        b.matrix_basis = basis[b.name]
    bpy.context.view_layer.update()


def label(text, at, eye, up, size=.12):
    cu = bpy.data.curves.new('lbl', 'FONT'); cu.body = text; cu.size = size; o = bpy.data.objects.new('STUDY_label', cu)
    bpy.context.scene.collection.objects.link(o); M = view_matrix(eye, at, up); M.translation = Vector(at); o.matrix_world = M
    o['wf_owner'] = 'eva.study'; m = bpy.data.materials.new('lbl'); m.use_nodes = True; bs = m.node_tree.nodes['Principled BSDF']
    bs.inputs['Emission Color'].default_value = (.95, .93, .85, 1); bs.inputs['Emission Strength'].default_value = 2.0; cu.materials.append(m); return o


def view_matrix(eye, look, up):
    z = (Vector(eye)-Vector(look)).normalized(); x = Vector(up).cross(z).normalized(); y = z.cross(x)
    M = Matrix((x, y, z)).transposed().to_4x4(); M.translation = Vector(eye); return M


def camera(eye, look, lens=24, up=(0, 0, 1), ortho=None):
    sc = bpy.context.scene; cam = bpy.data.objects.get('STUDY_CAM') or bpy.data.objects.new('STUDY_CAM', bpy.data.cameras.new('STUDY_CAM'))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    cam.data.type = 'ORTHO' if ortho else 'PERSP'; cam.data.ortho_scale = ortho or 1.0
    cam.data.lens = lens; cam.data.clip_start = .05; cam.matrix_world = view_matrix(eye, look, up); sc.camera = cam


def render_setup(size):
    sc = bpy.context.scene; engines = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items}
    sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in engines else 'BLENDER_EEVEE_NEXT'; sc.render.resolution_x, sc.render.resolution_y = size
    sc.view_settings.view_transform = 'AgX'
    if not bpy.data.objects.get('STUDY_SUN'):
        for name, rot, e in (('STUDY_SUN', (math.radians(40), math.radians(10), math.radians(70)), 3.5), ('STUDY_FILL', (math.radians(110), 0, math.radians(-120)), 1.2)):
            L = bpy.data.lights.new(name, 'SUN'); L.energy = e; o = bpy.data.objects.new(name, L); sc.collection.objects.link(o); o.rotation_euler = rot
    if sc.world is None:
        sc.world = bpy.data.worlds.new('STUDY_WORLD')
    sc.world.use_nodes = True; bg = sc.world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs['Color'].default_value = (.02, .022, .028, 1); bg.inputs['Strength'].default_value = .6


CONTEXT = ('Structural_Spine', 'Crew_Trunk', 'Shield_Sector_Keel_1', 'Survival_Reserve_1', 'Survival_Reserve_2', 'Storeroom_Shell')


def hide_vehicle(keep=CONTEXT):
    """Show only the study, the suits and a few context parts of the vehicle (the hull is drawn as a section ring instead)."""
    for o in bpy.data.objects:
        if o.get('wf_owner') == 'eva.study' or o.name.startswith(('EVA_', 'STUDY_')) or o.type not in ('MESH', 'CURVE', 'FONT', 'EMPTY'):
            continue
        if o.users_collection and any(c.name.startswith('EVA_') for c in o.users_collection):
            continue
        o.hide_render = o.name not in keep


def section_strips(s, fit, coll, acc=None):
    """The hull skin and the spine cut by the section plane through the airlock axis (the plane of X and u): thin strips for the
    section views, which hide the vehicle's own hull."""
    import hull_geometry
    import layout
    out = []; rows = [('Hull', hull_geometry.inner_radius_at(s, fit['x']), hull_geometry.radius_at(s, fit['x']), -6.0, 6.0),
                      ('Spine', 0.0, layout.spine_radius_at(s, fit['x']), -6.0, 6.0)]
    for key in ('sp12', 'sp13'):
        q_ = (acc or {}).get(key)
        if q_:
            x0, x1 = (x-fit['x'] for x in q_['x_m']); r0, r1 = q_['r_m']
            rows += [(f"{q_['id']}_Floor", r0-.05, r0, x0, x1), (f"{q_['id']}_Ceiling", r1, r1+.05, x0, x1), (f"{q_['id']}_Aft", r0, r1, x0-.05, x0),
                     (f"{q_['id']}_Fwd", r0, r1, x1, x1+.05)]
    for name, r0, r1, p0, p1 in rows:
        bm = bmesh.new(); vs = [bm.verts.new(world(fit, a, p, q)) for p in (p0, p1) for a in (r0, r1) for q in (-1.2, -1.18)]
        for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            bm.faces.new([vs[i] for i in f])
        out.append(mesh_obj(f'STUDY_{name}_Section', bm, coll, 'neck'))
    return out


def render(path):
    path.parent.mkdir(parents=True, exist_ok=True); bpy.context.scene.render.filepath = str(path); bpy.ops.render.render(write_still=True)
    print('WF_RENDER', path, flush=True)


# ---------------------------------------------------------------------------------------------------------------------------------

def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--access', type=Path, default=ROOT/'references/p1_eva_access.json')
    ap.add_argument('--vehicle', type=Path, default=ROOT/'assets/wayfarer/WF_WAYFARER_001.blend'); ap.add_argument('--out', type=Path)
    ap.add_argument('--renders', type=Path, default=ROOT/'renders/p1/eva/airlock'); ap.add_argument('--size', type=int, nargs=2, default=[1280, 960])
    ap.add_argument('--report', type=Path, default=ROOT/'references/p1_eva_airlock.json'); ap.add_argument('--no-renders', action='store_true')
    a = ap.parse_args(argv)
    acc = json.loads(a.access.read_text()); env = json.loads((ROOT/'references/p1_eva_envelopes.json').read_text())
    s = spec.load(ROOT)[0]; clr = s['prototype']['mechanical_clearance_m']
    bpy.ops.wm.open_mainfile(filepath=str(a.vehicle))
    fit = acc['sp11'][0]['fitting']; centre = world(fit, 4.0, 0.0, 0.0)
    trees = vehicle_trees(centre); report = dict(contract='eva_airlock v1', status=acc['status'], mechanical_clearance_m=clr, candidates={}, rooms={})
    for row in acc['sp11']:
        coll = bpy.data.collections.new(f"STUDY_{row['id']}"); bpy.context.scene.collection.children.link(coll)
        objs = build(row, coll); rep = clearance(objs, trees, clr)
        rep['hull_penetration_outside_m'] = row['door']['hull_penetration_outside_m']
        report['candidates'][row['id']] = rep
        print('WF_EVA_AIRLOCK', row['id'], {k: (v['status'], v['intersects'], v['below_clearance']) for k, v in rep.items() if isinstance(v, dict)}, flush=True)
        bpy.data.collections.remove(coll)
    rc = bpy.data.collections.new('STUDY_ROOMS'); bpy.context.scene.collection.children.link(rc); robjs = rooms(acc, rc)
    report['rooms'] = clearance(robjs, trees, clr)
    rec = next(r for r in acc['sp11'] if r['id'] == acc['recommendation']['id'])
    cc = bpy.data.collections.new(f"STUDY_{rec['id']}"); bpy.context.scene.collection.children.link(cc); cobjs = build(rec, cc)
    report['fixtures_vs_chamber'] = internal(acc, rec, robjs, cobjs)
    report['recommendation'] = acc['recommendation']['id']
    print('WF_EVA_ROOMS', {k: (v['status'], v['intersects'], v['below_clearance']) for k, v in report['rooms'].items()}, report['fixtures_vs_chamber'], flush=True)
    a.report.write_text(json.dumps(report, indent=1)+'\n')
    if a.no_renders:
        return
    # renders: the section of every candidate with its occupants, the rescue pair in the recommended one, the rooms
    bpy.data.collections.remove(cc); bpy.data.collections.remove(rc)
    rc = bpy.data.collections.new('STUDY_ROOMS_RENDER'); bpy.context.scene.collection.children.link(rc); rooms(acc, rc, render=True)
    render_setup(tuple(a.size)); rigs = {}
    for k in env['variants']:
        rigs[k] = append_suit(k, 'A')
    rigs2 = {k: append_suit(k, 'B') for k in env['variants']}
    hc = bpy.data.collections.new('STUDY_HULL'); bpy.context.scene.collection.children.link(hc); section_strips(s, fit, hc, acc); hide_vehicle()
    u, X, w = chamber_frame(fit); mid = world(fit, 4.0, 0.0, 0.0); eye = mid+w*14.0; look = mid       # looking across the axis: X runs left-right
    rc.hide_render = True
    for row in acc['sp11']:
        coll = bpy.data.collections.new(f"STUDY_R_{row['id']}"); bpy.context.scene.collection.children.link(coll); build(row, coll, render=True)
        for k, (rig, objs) in rigs.items():
            o = next((x for x in row['occupants'] if x['variant'] == k), None)
            for x in objs:
                x.hide_render = o is None or x.get('eva_role') == 'validation_body' or x.get('eva_show') == 'cutaway'
            if o:
                pose_and_place(rig, env['variants'][k][o['pose']], o, fit)
        for rig, objs in rigs2.values():
            for x in objs:
                x.hide_render = True
        ch = row['chamber']
        lb = label(f"{row['id']}  STUDY ONLY (no ship geometry)\ndoor {row['aperture_m']:.2f} m  chamber {ch['clear_diameter_m']:.2f} x {ch['clear_length_m']:.2f} m  "
                   f"{ch['volume_m3']} m3\n{row['status']}: " + '; '.join(row['geometry_fail'])[:110], world(fit, 7.45, -4.65, 2.0), eye, u, .14)
        camera(eye, look, up=u, ortho=9.6); render(a.renders/f"{row['id'].lower()}.png")
        if row['id'] == rec['id'] and row.get('rescue', {}).get('occupants'):
            for rig, objs in (*rigs.values(), *rigs2.values()):
                for x in objs:
                    x.hide_render = True
            for o in row['rescue']['occupants'][0]:            # rescuer from the A set, casualty from the B set
                rig, objs = (rigs if o['pose'] == 'rescue' else rigs2)[o['variant']]
                for x in objs:
                    x.hide_render = x.get('eva_role') == 'validation_body' or x.get('eva_show') == 'cutaway'
                pose_and_place(rig, env['variants'][o['variant']][o['pose']], o, fit)
            lb.data.body = f"{row['id']}  STUDY ONLY\nrescue: rescuer holds the casualty (neutral body posture)\nchamber sized for this pairing"
            render(a.renders/f"{row['id'].lower()}_rescue.png")
            for rig, objs in rigs2.values():
                for x in objs:
                    x.hide_render = True
        bpy.data.objects.remove(lb); bpy.data.collections.remove(coll)
    # the rooms from inside the forward collar, looking aft along the airlock side
    coll = bpy.data.collections.new('STUDY_R_REC'); bpy.context.scene.collection.children.link(coll); build(rec, coll, render=True)
    for k, (rig, objs) in rigs.items():
        o = next(x for x in rec['occupants'] if x['variant'] == k)
        for x in objs:
            x.hide_render = x.get('eva_role') == 'validation_body' or x.get('eva_show') == 'cutaway'
        pose_and_place(rig, env['variants'][k][o['pose']], o, fit)
    rc.hide_render = False; th = math.radians(95.0); eye = Vector((110.5, 8.0*math.cos(th), 8.0*math.sin(th))); th2 = math.radians(38.0)
    look = Vector((103.2, 2.7*math.cos(th2), 2.7*math.sin(th2))); camera(eye, look, 24, up=(0, math.cos(th2), math.sin(th2)))
    render(a.renders/'sp12_sp13_rooms.png')
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True); bpy.ops.wm.save_as_mainfile(filepath=str(a.out/'WF_EVA_AIRLOCK_STUDY.blend'), copy=True)


if __name__ == '__main__':
    main()
