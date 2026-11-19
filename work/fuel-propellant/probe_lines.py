"""Sample each FPS line (pure fuel_system polylines) against the saved vehicle's evaluated meshes: points closer than the line radius +
margin to any object, with that object's name (study code). blender -b <vehicle> --python probe_lines.py -- <name-substring>..."""
import bpy, math, sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0, 'src/wayfarer')
import spec, fuel_system as fs
s = spec.load()[0]
dg = bpy.context.evaluated_depsgraph_get(); items = []
for inst in dg.object_instances:
    ob = inst.object
    if ob.type not in ('MESH', 'CURVE') or ob.name.startswith('FPS_'):
        continue
    me = ob.to_mesh()
    if me is None or not len(me.polygons):
        ob.to_mesh_clear(); continue
    mw = inst.matrix_world.copy(); vs = [mw @ v.co for v in me.vertices]
    items.append(((inst.parent.name+'/' if inst.is_instance and inst.parent else '')+ob.name, BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in me.polygons]),
                  Vector([min(v[k] for v in vs) for k in range(3)]), Vector([max(v[k] for v in vs) for k in range(3)])))
    ob.to_mesh_clear()
want = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
for name, sp, pts, rad in fs.polylines(s):
    if want and not any(w in name for w in want):
        continue
    hits = {}
    for a, b in zip(pts, pts[1:]):
        a, b = Vector(a), Vector(b); n = max(2, int((b-a).length/0.1))
        for k in range(n+1):
            p = a+(b-a)*k/n
            for nm, t, lo, hi in items:
                if any(p[i] < lo[i]-1 or p[i] > hi[i]+1 for i in range(3)):
                    continue
                r = t.find_nearest(p)
                if r[0] is not None and r[3] < rad+0.05:
                    hits.setdefault(nm, []).append((round(p.x, 2), round(math.hypot(p.y, p.z), 2), round(math.degrees(math.atan2(p.z, p.y)), 1), round(r[3], 3)))
    print('LINE', name, {k: (len(v), v[0], v[-1]) for k, v in hits.items()})
