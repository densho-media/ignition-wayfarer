"""Geometry review of REVIEW_FIJI_DRIVE.blend (study helper): intersections, floating parts, plume cone, engine gaps, envelopes, normals,
colours and collection tags. Writes lab/variants/fiji-drive/results/geometry_check.json.

  /snap/bin/blender -b lab/variants/fiji-drive/REVIEW_FIJI_DRIVE.blend --python lab/variants/fiji-drive/check_review.py
"""
import json
import math
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(ROOT/'src/wayfarer')]
import spec  # noqa: E402
import fiji_geometry as fg  # noqa: E402

s = spec.load()[0]; prm = fg.params(); g, ST = fg.stations(s); p = s['prototype']
dg = bpy.context.evaluated_depsgraph_get()
scene = bpy.data.scenes['FIJI_DRIVE']
drive = bpy.data.collections['PROPULSION_FIJI_DRIVE']
vis = {o.name for c in ('FIJI_12_VIS_ACTIVE_STATE', 'FIJI_12_VIS_FIELD_LINES', 'FIJI_12_VISUALIZATION') for o in bpy.data.collections[c].all_objects}
rev = [o for o in drive.all_objects if o.type in ('MESH', 'CURVE') and o.name not in vis]


def world_mesh(o):
    ev = o.evaluated_get(dg); me = ev.to_mesh()
    bm = bmesh.new(); bm.from_mesh(me); bm.transform(o.matrix_world); ev.to_mesh_clear()
    return bm


def bvh(o):
    bm = world_mesh(o); t = BVHTree.FromBMesh(bm); verts = [v.co.copy() for v in bm.verts]
    nonman = sum(1 for e in bm.edges if not e.is_manifold); bm.free()
    return t, verts, nonman


# ship objects near the drive that stay visible (instanced collections: evaluate their objects in place, transforms are identity)
ship = []
for o in bpy.data.objects:
    if o.type not in ('MESH', 'CURVE') or o.hide_render or o.name in vis or o in rev or o.users_collection and any(c.name.startswith(('FIJI_CUT', 'WORK_FIJI_DRIVE_SYSTEMS')) for c in o.users_collection):
        continue
    if o.name.startswith(('DBG_', 'SEP_', 'DRIVE_DEBUG')):
        continue
    if o.name.endswith('_CUT') or o.name.startswith(('SHEET_', 'FIJI_')) or '.0' in o.name:
        continue
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    if max(v.x for v in bb) < -146 or min(v.x for v in bb) > -110 or min(math.hypot(v.y, v.z) for v in bb) > 9:
        continue
    ship.append(o)

T = {o.name: bvh(o) for o in rev+ship}
# intentional contacts: part families meant to touch (links on collars/nodes, struts on coils, lines on rings, inserts in coils ...)
def family(n):
    return n.split('_')[0]+'_'+n.split('_')[1] if n.startswith('ENG_') else n.split('_')[0]


inter = []
names = [o.name for o in rev]
for i, a in enumerate(names):
    for b in names[i+1:]:
        if T[a][0].overlap(T[b][0]):
            inter.append((a, b))
ship_inter = []
for a in names:
    for o in ship:
        if T[a][0].overlap(T[o.name][0]):
            ship_inter.append((a, o.name))

# floating: a part is attached when it overlaps another part or a vertex lies within 0.08 m of another surface
alln = names+[o.name for o in ship]
touch = {a: set() for a in names}
for a, b in inter:
    touch[a].add(b); touch[b].add(a)
for a, b in ship_inter:
    touch[a].add(b)
float_ = []
for a in names:
    if touch[a]:
        continue
    _, verts, _ = T[a]; best = math.inf
    step = max(1, len(verts)//400)
    for b in alln:
        if b == a:
            continue
        tb = T[b][0]
        for v in verts[::step]:
            hit = tb.find_nearest(v, .5)
            if hit[0] is not None and hit[3] < best:
                best = hit[3]
        if best < .08:
            break
    if best >= .08:
        float_.append((a, round(best, 3)))

# ship contacts: intended mounts and penetrations versus clashes
INTENDED = [
    (('CORE_CRADLE_LINK',), ('Primary_Rail',), 'cradle link pinned to the primary rail'),
    (('CORE_NEUTRON_SPECTROMETER',), ('Primary_Rail',), 'spectrometer mounted on the primary rail'),
    (('SEPTUM_',), ('Central_Thrust_Hub', 'Hub_Web'), 'septum root bolted into the thrust hub'),
    (('ENG_',), ('Thrust_Ring_Splice', 'Ring_Web', 'Thrust_Node_Plate'), 'engine mount collar/link pinned to a thrust-ring node'),
    (('H2_MAIN_INJECTION_RING',), ('CRYO_FEED_LINE_03', 'CRYO_FEED_LINE_04'), 'main-model H2 feed lines land on the injection ring'),
    (('CORE_CHOKE_FWD',), ('CRYO_FEED_LINE_01', 'CRYO_FEED_LINE_02'), 'main-model D/He-3 line terminus touches the choke face (moves 0.5 m forward on integration)'),
    (('FUEL_LINE_',), ('CRYO_FEED_LINE_01', 'CRYO_FEED_LINE_02'), 'fuel take-off joins the main-model D/He-3 line'),
    (('SHIELD_',), ('CRYO_FEED_LINE', 'OPTICAL_BORE', 'Primary_Rail', 'Primary_XBrace', 'SPINE_TERMINATION_HUB'),
     'shield penetration (stepped sleeve) or shield mount on the spine termination hub'),
    (('CHANNEL_',), ('GATE_L',), 'guide-coil strongback forward end on the lattice gate frame'),
    (('DRIVE_HX_',), ('Primary_Rail', 'Blade_', 'Radiator_'), 'HX on the rail / hot-loop tube into the blade root'),
]
def classify(a, b):
    for pa, pb, why in INTENDED:
        if a.startswith(pa) and b.startswith(pb):
            return why
    return None
ship_intended = {}; ship_clash = []
for a, b in ship_inter:
    w = classify(a, b)
    if w:
        ship_intended[w] = ship_intended.get(w, 0)+1
    else:
        ship_clash.append((a, b))

# plume: 15 deg half-angle cone from each exit circle; nothing visible aft of the exit plane inside it
plume = []
half = math.radians(15); rx = p['nozzle_exit_radius_m']
for (cy, cz) in fg.engine_axes(s):
    for o in rev+ship:
        for v in T[o.name][1]:
            if v.x < ST['exit']-1e-3:
                d = ST['exit']-v.x; r = math.hypot(v.y-cy, v.z-cz)
                if r < rx+d*math.tan(half):
                    plume.append(o.name); break
coils = fg.engine_coils(s, prm); axes = fg.engine_axes(s)
outer = max(c['outer'] for c in coils)+prm['engine']['trim_module_m']*0+.10+.05
gaps = sorted({round(math.dist(a_, b_)-2*outer, 3) for i, a_ in enumerate(axes) for b_ in axes[i+1:]})
env = [o.name for o in drive.all_objects if o.name.startswith(('CORE_COIL', 'CORE_CHOKE', 'CORE_MIRROR')) and o.type == 'MESH'
       and max(math.hypot(v.y, v.z) for v in T[o.name][1]) > p['reactor_radius_m']+.01]
nonman = {a: T[a][2] for a in names if T[a][2]}
uncoloured = [o.name for o in rev if tuple(o.color) == (1.0, 1.0, 1.0, 1.0)]
untagged = [c.name for c in drive.children_recursive if c.color_tag == 'NONE' and not c.name.startswith('FIJI_12')]
pairs_by_family = {}
for a, b in inter:
    k = f'{family(a)} x {family(b)}'; pairs_by_family[k] = pairs_by_family.get(k, 0)+1
out = dict(revision_objects=len(rev), ship_objects_checked=len(ship), intersections_within_revision=len(inter),
           intersections_by_family=dict(sorted(pairs_by_family.items(), key=lambda kv: -kv[1])), ship_contacts_intended=ship_intended,
           ship_clashes=ship_clash, intersections_with_ship=ship_inter,
           floating_parts=float_, plume_violations=sorted(set(plume)), engine_gap_min_m=gaps[0] if gaps else None, engine_gaps_m=gaps,
           core_coils_outside_locked_r46=env, non_manifold_edges=nonman, uncoloured=uncoloured, untagged_collections=untagged,
           intersections_within_revision_list=inter)
(HERE/'results').mkdir(exist_ok=True)
(HERE/'results/geometry_check.json').write_text(json.dumps(out, indent=1)+'\n')
print('WF_CHECK', json.dumps({k: (v if not isinstance(v, list) or len(v) < 25 else f'{len(v)} items') for k, v in out.items() if k != 'intersections_within_revision_list'}, indent=1))
