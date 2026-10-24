"""Maintenance-drone body family in Blender (data/drone_bodies.toml, src/wayfarer/drone_bodies.py, docs/ACCESSORIES.md).

  blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/build/drone_bodies.py -- \
      [--only DR-EVA-03 ...] [--out runs/<stamp>-drones] [--no-glb]

Per class: assets/drones/WF_DRONE_<ID>.blend with WF_DRONE_<ID> / GEN_WF_DRONE_<ID> (the body: one empty per node, joint empties keyed by
the actions, primitive meshes per shape) and REVIEW_FIXTURE (rail stand and dock cradle; never ship geometry). Every action is an NLA
track (glTF animation), every object carries part, job, drone_class, geometry_status = PROTOTYPE and maturity = L4_VISUAL_CANDIDATE.
`--out` also writes <out>/glb/WF_DRONE_<ID>.glb (body only, with its actions) and <out>/drone_bodies.json (the fit screen and the asset
index). Review renders: presentation/drone_preview.py.
The ship's WF_DRONES proxies are not touched (54 DGT-017 HOLD).
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build')]
import drone_bodies as db
from common import OWNER, begin, save

MAT = {}


def material(d, name):
    if name in MAT:
        return MAT[name]
    rgb = d['palette'][name]; m = bpy.data.materials.get(f'WF_DRONE_{name}') or bpy.data.materials.new(f'WF_DRONE_{name}')
    m['wf_owner'] = OWNER; m.use_nodes = True; m.diffuse_color = (*rgb, 1)
    bs = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    rough, metal = dict(metal=(.32, .9), radiator=(.18, .0), lens=(.05, .0), mli_gold=(.28, .85), rubber=(.85, .0), graphite=(.55, .2),
                        target_white=(.5, .0), target_black=(.6, .0), beta_white=(.82, .0), shell_white=(.45, .0), grey=(.5, .3)).get(name, (.5, .0))
    bs.inputs['Base Color'].default_value = (*rgb, 1); bs.inputs['Roughness'].default_value = rough; bs.inputs['Metallic'].default_value = metal
    if name.startswith('lamp'):
        bs.inputs['Emission Color'].default_value = (*rgb, 1); bs.inputs['Emission Strength'].default_value = 4.0
    MAT[name] = m; return m


def _frame(axis):
    z = Vector(axis).normalized(); h = Vector((1, 0, 0)) if abs(z.x) < .9 else Vector((0, 1, 0))
    x = h.cross(z).normalized(); y = z.cross(x); return x, y, z


def mesh_box(c, s, bevel):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x*s[0]+c[0], v.co.y*s[1]+c[1], v.co.z*s[2]+c[2]))
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, min(s)*.45), segments=2, affect='EDGES', profile=.5)
    return bm


def mesh_cyl(a, b, r, r2, n):
    a, b = Vector(a), Vector(b); x, y, z = _frame(b-a); bm = bmesh.new(); rings = []
    for end, rr in ((a, r), (b, r2)):
        rings.append([bm.verts.new(end+(x*math.cos(2*math.pi*i/n)+y*math.sin(2*math.pi*i/n))*rr) for i in range(n)])
    for i in range(n):
        bm.faces.new((rings[0][i], rings[0][(i+1) % n], rings[1][(i+1) % n], rings[1][i]))
    bm.faces.new(list(reversed(rings[0]))); bm.faces.new(rings[1])
    return bm


def mesh_torus(c, axis, R, r, arc, n=40, m=10):
    c = Vector(c); bm = bmesh.new(); a0, a1 = arc; full = abs(a1-a0) >= 359.9; steps = n if full else max(4, int(n*abs(a1-a0)/360))
    rows = []
    for i in range(steps+(0 if full else 1)):
        t = math.radians(a0+(a1-a0)*i/steps); d = Vector(db._torus_dir(axis, t)); ax = Vector({'x': (1, 0, 0), 'y': (0, 1, 0), 'z': (0, 0, 1)}[axis])
        rows.append([bm.verts.new(c+d*R+(d*math.cos(2*math.pi*k/m)+ax*math.sin(2*math.pi*k/m))*r) for k in range(m)])
    for i in range(len(rows)-(0 if full else 1)):
        A, B = rows[i], rows[(i+1) % len(rows)]
        for k in range(m):
            bm.faces.new((A[k], A[(k+1) % m], B[(k+1) % m], B[k]))
    if not full:
        bm.faces.new(list(reversed(rows[0]))); bm.faces.new(rows[-1])
    return bm


def text_obj(q, mat):
    cu = bpy.data.curves.new(f'T_{q["body"]}', 'FONT'); cu.body = q['body']; cu.size = q['size']; cu.align_x = 'CENTER'; cu.align_y = 'CENTER'
    cu.extrude = .0004; o = bpy.data.objects.new('tmp_text', cu); bpy.context.scene.collection.objects.link(o)
    o.location = q['c']; bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get(); me = bpy.data.meshes.new_from_object(o.evaluated_get(dg)); me.transform(Matrix.Translation(q['c']))
    bpy.data.objects.remove(o); bpy.data.curves.remove(cu); me.materials.append(mat); return me


def build(b, d, gen, fix):
    """Objects for one body: an empty per node (joint empties keyed), shape meshes merged per (node, material)."""
    E = {}
    for nid in b.order:
        n = b.nodes[nid]; e = bpy.data.objects.new(f'{b.id}_{nid}', None); e.empty_display_size = .03
        (fix if n['role'] == 'fixture' else gen).objects.link(e)
        e.location = n['at']; e.rotation_mode = 'XYZ'; e.rotation_euler = Euler([math.radians(a) for a in n['rest']])
        if n['parent']:
            e.parent = E[n['parent']]
        e['wf_owner'] = OWNER; e['drone_node'] = nid; e['drone_class'] = b.id; e['job'] = n['job'] or n['role']
        if n['joint']:
            # A child empty carries the joint so the rest rotation and the keyed joint value stay separate channels.
            j = bpy.data.objects.new(f'{b.id}_{nid}_J', None); j.empty_display_size = .02; (fix if n['role'] == 'fixture' else gen).objects.link(j)
            j.parent = e; j.rotation_mode = 'XYZ'; j['wf_owner'] = OWNER; j['drone_joint'] = nid; j['joint_type'] = n['joint']; j['joint_axis'] = n['axis']
            j['limits_deg'] = json.dumps(n['limits']); E[nid] = j
            if nid == 'root':
                E['__root_frame'] = e
        else:
            E[nid] = e
    groups = {}
    for q in b.shapes:
        groups.setdefault((q['node'], q['mat'], q['part']), []).append(q)
    made = []
    for (nid, mname, part), qs in groups.items():
        mat = material(d, mname); bm = bmesh.new(); texts = []
        for q in qs:
            if q['kind'] == 'text':
                texts.append(text_obj(q, mat)); continue
            sub = mesh_box(q['c'], q['s'], q['bevel']) if q['kind'] == 'box' else mesh_cyl(q['a'], q['b'], q['r'], q['r2'], q['n']) if q['kind'] == 'cyl' \
                else mesh_torus(q['c'], q['axis'], q['R'], q['r'], q['arc'])
            tmp = bpy.data.meshes.new('tmp'); sub.to_mesh(tmp); sub.free(); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp)
        name = f'{b.id}_{part}_{nid}_{mname}'; me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
        for t in texts:
            bm2 = bmesh.new(); bm2.from_mesh(me); bm2.from_mesh(t); bm2.to_mesh(me); bm2.free(); bpy.data.meshes.remove(t)
        me.materials.append(mat)
        for p in me.polygons:
            p.use_smooth = True
        me['wf_owner'] = OWNER
        o = bpy.data.objects.new(name, me); fixture = part.startswith('FIXTURE') or b.nodes[nid]['role'] == 'fixture' or nid.startswith('fixture')
        (fix if fixture else gen).objects.link(o); o.parent = E[nid]
        o['wf_owner'] = OWNER; o['drone_class'] = b.id; o['part'] = part; o['job'] = qs[0]['job'] or part.lower().replace('_', ' ')
        o['geometry_status'] = 'PROTOTYPE'; o['maturity'] = 'L4_VISUAL_CANDIDATE'; o['representation'] = 'REP_PROXY' if fixture else 'ACCESSORY_BODY'
        o['source_ref'] = 'data/drone_bodies.toml; S&E 51/53/56'; o['review_fixture'] = fixture
        made.append(o)
    # auto-smooth by angle so bevels read sharp and cylinders read round
    for o in made:
        o.data.set_sharp_from_angle(angle=math.radians(35)) if hasattr(o.data, 'set_sharp_from_angle') else None
    return E, made


def actions(b, E):
    """One action per body action: joint empties keyed per keyframe (rotation about / location along the joint axis); NLA tracks."""
    idx = {'x': 0, 'y': 1, 'z': 2}; made = {}
    for name in b.actions:
        act = bpy.data.actions.get(f'{b.id}__{name}')
        if act:
            bpy.data.actions.remove(act)
        keys = db.frames(b, name)
        # one action per joint object (glTF exports per-object animation); group them by NLA track name
        for nid in b.joints():
            j = E[nid]; n = b.nodes[nid]; i = idx[n['axis']]
            if not j.animation_data:
                j.animation_data_create()
            a = bpy.data.actions.new(f'{b.id}__{name}__{nid}'); a['wf_owner'] = OWNER; a.use_fake_user = True; a['drone_action'] = name
            j.animation_data.action = a
            for fr, vals in keys:
                v = vals.get(nid, 0.0)
                if n['joint'] == 'revolute':
                    j.rotation_euler[i] = math.radians(v); j.keyframe_insert('rotation_euler', index=i, frame=fr)
                else:
                    j.location[i] = v; j.keyframe_insert('location', index=i, frame=fr)
            j.animation_data.action = None
            tr = j.animation_data.nla_tracks.new(); tr.name = name; tr.strips.new(name, int(keys[0][0]), a); tr.mute = True
            made.setdefault(name, []).append(a.name)
        for nid in b.joints():
            E[nid].rotation_euler = (0, 0, 0); E[nid].location = (0, 0, 0)
    return made


def export_glb(path, gen):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in gen.all_objects:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', use_selection=True, export_animations=True,
                              export_animation_mode='NLA_TRACKS', export_optimize_animation_size=False, export_extras=True, export_apply=False, export_yup=True)


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--only', nargs='*'); ap.add_argument('--out', type=Path); ap.add_argument('--no-glb', action='store_true')
    ap.add_argument('--no-save', action='store_true')
    args = ap.parse_args(argv)
    s, d = db.load(ROOT); B = db.bodies(s, d); rows, fails = db.check(s, d)
    spec_text = (ROOT/'data/wayfarer_3d.toml').read_text(); source_text = (ROOT/'data/source_map.toml').read_text()
    out = args.out.resolve() if args.out else None; index = {}
    if out:
        (out/'glb').mkdir(parents=True, exist_ok=True)
    for cid in args.only or list(B):
        b = B[cid]; ident = f'WF_DRONE_{cid.replace("-", "_")}'; path = ROOT/'assets/drones'/f'{ident}.blend'
        MAT.clear(); root, gen = begin(path, ident)
        fix = bpy.data.collections.get(f'REVIEW_FIXTURE_{ident}') or bpy.data.collections.new(f'REVIEW_FIXTURE_{ident}')
        if fix.name not in root.children:
            root.children.link(fix)
        for o in list(fix.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        fix['wf_owner'] = OWNER; fix['review_fixture'] = 'REVIEW FIXTURE: rail stand / dock cradle, never ship geometry'
        for a in list(bpy.data.actions):
            if a.get('wf_owner') == OWNER and a.name.startswith(f'{cid}__'):
                bpy.data.actions.remove(a)
        E, made = build(b, d, gen, fix); acts = actions(b, E)
        gen['drone_class'] = cid; gen['title'] = b.title; gen['mount'] = b.mount; gen['family'] = d['family']['id']; gen['maturity'] = d['family']['maturity']
        gen['integration'] = d['family']['integration']; gen['form'] = d['class'][cid]['form']; gen['precedent'] = d['class'][cid]['precedent']
        gen['open'] = json.dumps({k: v['status'] for k, v in d['open'].items()}); gen['actions'] = json.dumps({k: v['job'] for k, v in b.actions.items()})
        gen['kit'] = json.dumps(b.kit)
        if not args.no_save:
            save(path, root, spec_text, source_text)
        glb = None
        if out and not args.no_glb:
            glb = out/'glb'/f'{ident}.glb'; export_glb(glb, gen)
        index[cid] = dict(asset=str(path.relative_to(ROOT)), glb=str(glb.relative_to(ROOT)) if glb else None, objects=len(made), nla_actions=sorted(acts),
                          faces=sum(len(o.data.polygons) for o in made if not o['review_fixture']), **rows[cid])
        print(f'WF_DRONE {cid} objects={len(made)} actions={len(acts)}', flush=True)
    if out:
        (out/'drone_bodies.json').write_text(json.dumps(dict(family=d['family'], fails=fails, inventory=rows['inventory'], classes=index), indent=1)+'\n')
    if fails:
        print('WF_DRONE_CHECK FAIL', fails, flush=True); sys.exit(1)


if __name__ == '__main__':
    main()
