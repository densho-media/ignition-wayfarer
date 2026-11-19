"""FPS mesh screen (study code, work/fuel-propellant): every FPS_ object of the saved vehicle against all other evaluated geometry.
blender -b assets/wayfarer/WF_WAYFARER_001.blend --python work/fuel-propellant/probe.py -- [out.json]
Overlaps (BVH triangle intersection) and the minimum clearance of each FPS object to its nearest non-FPS neighbour, with the expected
contacts named: the run tank a line leaves, the Engineering_Envelope it passes through, the shadow-shield slab its sleeve crosses, the
cluster bay face the fuel ends on, the engine panel lines a branch joins, the frames the clamps bear on and the farm mains/deck."""
import bpy, json, sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ALLOWED = ('Hull_Aft_Body', 'Feed_Run_Tank', 'Engineering_Envelope', 'Reactor_Shadow_Shield', 'CL_ELECTRICAL', 'Primary_Frame', 'Fuel_Ring_Main', 'Fuel_Deck',
           'Brayton')
# FPS V1 designed contacts, per object prefix: the feedthroughs, inlets and check valves sit on the transfer trunks they join; the target
# feed passes through the cartridge shell (VTX_STRUCTURE) into the magazine (VTX_FUEL); the flanges mate the panel and the magazine; the
# injector ports pass the thrust collar (VTX_STRUCTURE) and the shadow shield and burn-face armour (VTX_SHIELDING) through galleries.
ALLOWED_BY = {'FPS_Feedthrough': ('Fuel_Transfer',), 'FPS_Farm_Flanges': ('Fuel_Transfer',), 'FPS_Tank_Inlet': ('Fuel_Transfer',),
              'FPS_Check_Valve': ('Fuel_Transfer',), 'FPS_H2_Crossover': ('Fuel_Ring_Main',),
              '_Target_Feed': ('VTX_STRUCTURE', 'VTX_FUEL'), '_Flanges': ('VTX_FUEL', 'VTX_SERVICE'), '_H2_Injectors': ('VTX_STRUCTURE', 'VTX_SHIELDING')}
def allowed(fname, other):
    return any(a in other for a in ALLOWED) or any(k in fname and any(a in other for a in v) for k, v in ALLOWED_BY.items())
dg = bpy.context.evaluated_depsgraph_get()
items = []
def _poly_c(o, j):
    p = o['polys'][j]; return sum((o['vs'][k] for k in p), Vector())/len(p)

for inst in dg.object_instances:
    ob = inst.object
    if ob.type not in ('MESH', 'CURVE'):
        continue
    try:
        me = ob.to_mesh()
    except Exception:
        continue
    if me is None or not len(me.polygons):
        ob.to_mesh_clear(); continue
    mw = inst.matrix_world.copy()
    vs = [mw @ v.co for v in me.vertices]; fs = [tuple(p.vertices) for p in me.polygons]
    name = (inst.parent.name+'/' if inst.is_instance and inst.parent else '')+ob.name
    lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs))); hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    items.append(dict(name=name, base=ob.name, bvh=BVHTree.FromPolygons(vs, fs), lo=lo, hi=hi, vs=vs, polys=fs))
    ob.to_mesh_clear()
fps = [i for i in items if i['base'].startswith('FPS_')]; other = [i for i in items if not i['base'].startswith('FPS_')]
out = {}
for f in fps:
    hits = []; near = (1e9, '')
    for o in other:
        m = 1.0
        if any(f['hi'][k]+m < o['lo'][k] or o['hi'][k]+m < f['lo'][k] for k in range(3)):
            continue
        ov = f['bvh'].overlap(o['bvh'])
        if ov:
            hits.append(o['name']); f.setdefault('where', {})[o['name']] = sorted({tuple(round(c, 1) for c in o['vs'][0]*0+_poly_c(o, j)) for i, j in ov[:2000]})[:6]
        else:
            step = max(1, len(f['vs'])//400)
            for v in f['vs'][::step]:
                r = o['bvh'].find_nearest(v)
                if r[0] is not None and r[3] < near[0]:
                    near = (r[3], o['name'])
    bad = [h for h in hits if not allowed(f['base'], h)]
    out[f['base']] = dict(overlaps=hits, unexpected=bad, nearest=[round(near[0], 3), near[1]], where={k: v for k, v in f.get('where', {}).items() if k in bad}, designed={k: v for k, v in f.get('where', {}).items() if k not in bad})
summary = {k: v for k, v in out.items() if v['unexpected']}
res = dict(objects=len(fps), unexpected=len(summary), detail=out)
path = sys.argv[sys.argv.index('--')+1] if '--' in sys.argv and len(sys.argv) > sys.argv.index('--')+1 else None
if path:
    json.dump(res, open(path, 'w'), indent=1)
print('FPS_PROBE', json.dumps(dict(objects=len(fps), unexpected={k: v['where'] for k, v in summary.items()})))
