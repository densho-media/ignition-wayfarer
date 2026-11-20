"""Blender side of the Vertex 1.8 Phase F review (work, not canon). Turns aplus.parts_aplus into objects: one mesh per (group, category,
material) shared by the four engines, one object per engine (the effect-object pattern), moving groups under their own empties so a
rigid transform moves them. Used by make_review.py (the review .blend) and export_glb.py (the browser review and the measurements)."""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
for p in (ROOT/'src'/'wayfarer', ROOT/'src'/'wayfarer'/'build', ROOT/'src'/'wayfarer'/'components', HERE):
    sys.path.insert(0, str(p))
import vertex_engine as ve  # noqa: E402
import vertex_cluster as vc  # noqa: E402
import aplus  # noqa: E402

SMOOTH = {'torus', 'tube', 'sphere', 'revolve', 'torus_section', 'plume', 'disc'}
MAT_RGB = None


def physical(key):
    """The engine's physical material (same name and values as components/vertex.physical), reused when the file already has it."""
    name = f'WF_MAT_VTX_{key.upper()}'
    m = bpy.data.materials.get(name)
    if m:
        return m
    if key == 'field':
        rgb, rough, metal, emit = (0.25, 0.55, 0.95), 0.6, 0.0, 0.12
    else:
        rgb, rough, metal, emit = ve.MATERIALS[key]
    m = bpy.data.materials.new(name); m.use_nodes = True; m.diffuse_color = (*rgb, 1.0)
    node = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    node.inputs['Base Color'].default_value = (*rgb, 1.0); node.inputs['Roughness'].default_value = rough; node.inputs['Metallic'].default_value = metal
    if emit:
        node.inputs['Emission Color'].default_value = (*rgb, 1.0); node.inputs['Emission Strength'].default_value = emit
    m['vtx_material'] = key
    return m


def mesh(name, ps, origin=(0.0, 0.0, 0.0)):
    vs, fs, smooth = [], [], []
    for p in ps:
        v, f = ve.mesh_of(p)[:2]
        fs += [tuple(i+len(vs) for i in face) for face in f]; vs += [tuple(x[i]-origin[i] for i in range(3)) for x in v]
        smooth += [p['shape'] in SMOOTH]*len(f)
    d = bpy.data.meshes.new(name); d.from_pydata(vs, [], fs); d.update(); d.polygons.foreach_set('use_smooth', smooth)
    d.materials.append(physical(ps[0]['material']))
    return d


def keyed(P):
    """{object key: (group, parent group, origin, parts)}: one object per group, category and material."""
    out = {}
    for p in P:
        k = (p['group'], p['category'], p['material'])
        out.setdefault(k, dict(group=p['group'], parent=p.get('parent'), origin=p.get('origin', (0.0, 0.0, 0.0)), parts=[]))['parts'].append(p)
    return out


def build(s, R, coll, variant='aplus', base=Matrix.Identity(4), prefix='WORK_VTX18', effects=False):
    """Four engines in `coll`. variant 'aplus' (moving groups and new parts) or 'baseline' (today's parts, static). Returns
    {engine n: {group: empty}} and the list of created objects."""
    P = aplus.parts_aplus(s, R) if variant == 'aplus' else [dict(p, group='STATIC') for p in ve.parts(s)]
    K = keyed(P); meshes = {}
    for k, o in K.items():
        meshes[k] = mesh(f'{prefix}_{o["group"]}_{k[1]}_{k[2]}_Mesh', o['parts'], o['origin'])
    rigs = {}; objs = []
    for pl in vc.placements(s):
        n = pl['n']; root = bpy.data.objects.new(f'{prefix}_N{n}', None); coll.objects.link(root)
        root.matrix_world = base@Matrix(vc.matrix(pl)); root.empty_display_size = 1.0; root['engine'] = f'N{n}'
        root['wf_status'] = 'PROTOTYPE review (Vertex 1.8 Phase F A+), not canon'
        groups = {'STATIC': root}
        def holder(gname, parent_name, origin):
            if gname in groups:
                return groups[gname]
            par = groups[parent_name] if parent_name else root
            e = bpy.data.objects.new(f'{prefix}_N{n}_{gname}', None); coll.objects.link(e); e.parent = par
            e.location = origin if parent_name in (None, 'STATIC', 'L4') else origin
            e.empty_display_size = 0.4; e['moving_group'] = gname; groups[gname] = e
            return e
        for k, o in K.items():
            gname = o['group']
            if gname != 'STATIC':
                holder(gname, o['parent'], o['origin'])
            ob = bpy.data.objects.new(f'{prefix}_N{n}_{gname}_{k[1]}_{k[2]}', meshes[k]); coll.objects.link(ob)
            ob.parent = groups[gname]; ob['moving_group'] = gname; ob['wf_category'] = k[1]; ob['wf_material'] = k[2]
            ob['wf_parts'] = ', '.join(p['name'] for p in o['parts'])[:4000]; ob['wf_units'] = len(o['parts'])
            ob['wf_status'] = 'PROTOTYPE' if any(p['name'].startswith(('VTX_C', 'VTX_L')) and ('Dynamo' in p['name'] or 'Trim' in p['name'] or 'Carriage' in p['name']
                                                                      or 'Switch' in p['name'] or 'Metrology' in p['name'] or 'Petal' in p['name'] or 'Lock' in p['name']) for p in o['parts']) else 'ENGINEERING_PROTOTYPE'
            if any(p.get('lamp') == 'lock' for p in o['parts']):
                ob['lock_lamp'] = True
            objs.append(ob)
        if variant == 'aplus':
            for gname, e in groups.items():
                if gname.startswith('PETAL_'):
                    sh, ar = aplus.petal_motion(s, gname); e['shell_dir'] = sh; e['armour_dir'] = ar
            beams = aplus.metrology_beams(s, R)
            if 'FX_METROLOGY' not in meshes:
                meshes['FX_METROLOGY'] = mesh(f'{prefix}_FX_METROLOGY_Mesh', [beams])
                meshes['FX_METROLOGY'].materials[0] = beam_material()
            ob = bpy.data.objects.new(f'{prefix}_N{n}_FX_METROLOGY', meshes['FX_METROLOGY']); coll.objects.link(ob); ob.parent = groups['STATIC']
            ob['effect'] = 'metrology'; objs.append(ob)
        rigs[n] = groups
    return rigs, objs


def beam_material():
    m = bpy.data.materials.get('WORK_VTX18_METROLOGY') or bpy.data.materials.new('WORK_VTX18_METROLOGY')
    m.use_nodes = True; m.diffuse_color = (0.3, 1.0, 0.4, 1.0)
    nt = m.node_tree; nt.nodes.clear()
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (0.3, 1.0, 0.4, 1.0); em.inputs['Strength'].default_value = 8.0
    out = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(em.outputs[0], out.inputs[0])
    return m


def build_flywheel(s, coll, base=Matrix.Identity(4), prefix='WORK_VTX18'):
    """Optional ignition flywheel (ship frame) in its own collection."""
    out = {}
    for p in aplus.flywheel(s):
        o = p.get('origin', (0.0, 0.0, 0.0)); d = mesh(f'{prefix}_{p["name"]}_Mesh', [p], o)
        ob = bpy.data.objects.new(f'{prefix}_{p["name"]}', d); coll.objects.link(ob); ob.matrix_world = base@Matrix.Translation(o)
        ob['wf_status'] = 'OPTIONAL (owner 2026-11-16): mass and energy requirements OPEN'; out[p['name']] = ob
    return out


def apply_pose(s, T, rigs, v, gain=1.0):
    """Set the empties for control values v (used to bake keyframes and for the GLB rest pose)."""
    ps = aplus.pose(T, v, gain)
    for n, groups in rigs.items():
        for gname, e in groups.items():
            if gname == 'L4':
                e.location = ps['L4']['t']
            elif gname.startswith('PETAL_'):
                f = v['service_petals']; sh = Vector(e['shell_dir']); ar = Vector(e['armour_dir'])
                for ch in e.children:
                    ch.location = (ar if ch.get('wf_material') == 'armour' else sh)*f
    return ps
