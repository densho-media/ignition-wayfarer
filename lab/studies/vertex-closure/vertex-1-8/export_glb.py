"""Export the browser review and measurement GLBs of Vertex 1.8 Phase F (work, not canon).

  /snap/bin/blender -b --factory-startup --python lab/studies/vertex-closure/vertex-1-8/export_glb.py

Writes into runs/vtx18_web/ (disposable):
  baseline.glb   today's four engines (vertex_engine.parts, same placements), static: the reference for the measurements
  aplus.glb      the A+ engines: the same parts reshaped, the A+ machinery, moving groups under named empties (rest pose)
  effects.glb    the 56 per-engine effect objects of the cluster (vertex_cluster.effect_objects), shared by both pages
  counts.json    objects, mesh nodes, triangles, vertices and bytes of each, counted in Blender before export
Draco mesh compression on, as the site's viewer export does (export/godot.py).
"""
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
import blend_aplus as ba  # noqa: E402
import aplus  # noqa: E402
import vertex_engine as ve  # noqa: E402
import vertex_cluster as vc  # noqa: E402

OUT = ROOT/'runs'/'vtx18_web'; OUT.mkdir(parents=True, exist_ok=True)
s, R = aplus.load()


def counts(objs):
    me = [o for o in objs if o.type == 'MESH']
    tris = sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in me)
    return dict(objects=len(objs), mesh_nodes=len(me), unique_meshes=len({o.data.name for o in me}), triangles=tris,
                vertices=sum(len(o.data.vertices) for o in me), materials=len({m.name for o in me for m in o.data.materials if m}))


def export(name, objs):
    """Draco GLB (the measurement, as the site's viewer ships) and an uncompressed copy (the published review page: the artifact frame
    cannot fetch the Draco decoder)."""
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    for suffix, draco in (('', True), ('_raw', False)):
        fp = OUT/f'{name}{suffix}.glb'
        bpy.ops.export_scene.gltf(filepath=str(fp), export_format='GLB', use_selection=True, export_yup=True, export_apply=False,
                                  export_animations=False, export_extras=False, export_cameras=False, export_lights=False,
                                  export_draco_mesh_compression_enable=draco)
    return (OUT/f'{name}.glb').stat().st_size


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
res = {}
for variant in ('baseline', 'aplus'):
    c = bpy.data.collections.new(variant); scene.collection.children.link(c)
    rigs, objs = ba.build(s, R, c, variant, prefix='B' if variant == 'baseline' else 'A')
    allobjs = list(c.objects)
    res[variant] = dict(counts(allobjs), bytes=export(variant, allobjs))
    for o in allobjs:
        o.hide_set(True)
# effects: one mesh per effect, one object per engine (as components/vertex.cluster builds them)
c = bpy.data.collections.new('effects'); scene.collection.children.link(c); meshes = {}
for o in vc.effect_objects(s):
    key = o['name']; origin = o.get('origin') or (0.0, 0.0, 0.0)
    if key not in meshes:
        vs, fs = ve.mesh_of(o)
        d = bpy.data.meshes.new(f'FX_{key}'); d.from_pydata([tuple(v[i]-origin[i] for i in range(3)) for v in vs], [], fs); d.update()
        m = bpy.data.materials.new(f'FX_{key}'); m.diffuse_color = (*o['color'], 1.0); d.materials.append(m); meshes[key] = d
    ob = bpy.data.objects.new(o['object'], meshes[key]); c.objects.link(ob)
    ob.matrix_world = Matrix(vc.matrix(o['placement']))@Matrix.Translation(origin)
res['effects'] = dict(counts(list(c.objects)), bytes=export('effects', list(c.objects)))
res['engine_tris_reference'] = R['browser']['engine_tris']
(OUT/'counts.json').write_text(json.dumps(res, indent=1))
print('WF_GLB', json.dumps(res), flush=True)
