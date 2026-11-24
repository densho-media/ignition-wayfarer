"""Compact integrated Wayfarer review file (work, noncanonical). Owner direction 2026-11-23: keep the compact ship and its aft cluster.

  /snap/bin/blender -b --factory-startup --python lab/studies/vertex-compact-engine/vertex-compact/blender_compact.py [-- --no-render]

The approved ship (assets/wayfarer/WF_WAYFARER_001.blend, built from this branch, geometry identical to the baseline) is appended and
made local; it is variant C1 and stays untouched. C2-C4 are lightweight copies: new instance empties of the same subsystem collections
(nothing duplicated), side by side at -Y, with the cluster instance moved aft and the variant hardware in pink WORK_COMPACT_<k> collections:
  C2  cluster 30 m aft, thrust-truss extension from the ship thrust ring to the hub, extended feed and service trunks.
  C3  cluster 36 m aft (30 m truss + 6 m nozzle extension): enlarged shadow shields 12 m ahead of each burn (the drawn shield stays as
      their core), ribbon-loop note (the instanced loops are the drawn round cryostats).
  C4  C3 + braking protection: three stern screens ahead of the tank dome, armour on the loop aft faces and hub cap, blade aft-edge
      bumpers, service trunks inside the hub shadow.
Every variant carries SIMULATED overlays from results/compact.json: burn points, each engine's shadow cone, direct-burn hotspots on the
ship (colour by W/m2) and red problem markers with Engineering Problems Register IDs. Nothing is drawn as solved that is not.
"""
import json
import math
import os
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RENDER = '--no-render' not in sys.argv
RES = json.loads((HERE / 'results' / 'compact.json').read_text())['variants']
PR = json.loads((HERE / 'results' / 'problems_compact.json').read_text()) if (HERE / 'results' / 'problems_compact.json').exists() else []
PINK = 'COLOR_07'
DY = -140.0                                    # side-by-side spacing of the variant ships
SHIFT = dict(C1=0.0, C2=-30.0, C3=-36.0, C4=-36.0)   # C3/C4: 30 m truss + 6 m nozzle extension (shield moved 12 m ahead of the burn)
SPOOL = dict(C1=0.0, C2=0.0, C3=0.0, C4=0.0)
BURN_LOCAL = -18.8                              # burn point on the engine axis, engine frame (measured: ship x -153.4 at the drawn cluster)


def mat(name, rgba, emit=0.0, alpha=1.0, metal=0.0, rough=0.5):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (rgba[0], rgba[1], rgba[2], alpha); m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*rgba[:3], 1.0); b.inputs['Metallic'].default_value = metal; b.inputs['Roughness'].default_value = rough
    if emit:
        b.inputs['Emission Color'].default_value = (*rgba[:3], 1.0); b.inputs['Emission Strength'].default_value = emit
    if alpha < 1.0:
        b.inputs['Alpha'].default_value = alpha
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            m.blend_method = 'BLEND'
    return m


bpy.ops.wm.read_factory_settings(use_empty=True)
M = dict(truss=mat('WORK_COMPACT_TRUSS_TI_CFRP', (0.62, 0.62, 0.64), metal=0.5),
         spool=mat('WORK_COMPACT_SPOOL', (0.70, 0.66, 0.55), metal=0.5),
         shield=mat('WORK_COMPACT_SHADOW_SHIELD_LIH_W', (0.45, 0.46, 0.50), rough=0.8),
         armour=mat('WORK_COMPACT_ARMOUR_W_B4C', (0.20, 0.19, 0.18), metal=0.8, rough=0.4),
         screen=mat('WORK_COMPACT_STERN_SCREEN', (0.30, 0.32, 0.34), rough=0.9, alpha=0.85),
         bumper=mat('WORK_COMPACT_BLADE_BUMPER', (0.25, 0.25, 0.27), rough=0.8),
         feed=mat('WORK_COMPACT_FEED_EXTENSION', (0.30, 0.95, 0.45), emit=1.5),
         trunk=mat('WORK_COMPACT_SERVICE_TRUNK', (0.95, 0.80, 0.20), emit=1.5),
         burn=mat('WORK_COMPACT_BURN_POINT', (0.75, 0.88, 1.0), emit=40.0),
         cone=mat('WORK_COMPACT_SHADOW_CONE_SIM', (0.15, 0.35, 1.0), emit=0.2, alpha=0.025),
         hot=[mat(f'WORK_COMPACT_HOTSPOT_SIM_{i}', c, emit=3.0) for i, c in enumerate(
             [(1.0, 0.85, 0.2), (1.0, 0.5, 0.1), (1.0, 0.15, 0.05), (0.85, 0.0, 0.35)])],
         prob=mat('WORK_COMPACT_PROBLEM_MARKER', (1.0, 0.08, 0.08), emit=5.0),
         label=mat('WORK_COMPACT_LABEL', (0.95, 0.95, 1.0), emit=4.0),
         plabel=mat('WORK_COMPACT_PROBLEM_LABEL', (1.0, 0.75, 0.75), emit=5.0))


def coll(name, parent, tag=PINK):
    c = bpy.data.collections.new(name); parent.children.link(c); c.color_tag = tag
    return c


def link(ob, c, m=None):
    c.objects.link(ob)
    if m is not None and hasattr(ob.data, 'materials'):
        ob.data.materials.append(m)
    return ob


def revolve(name, prof, c, m, seg=64):
    """Profile [(x, r)] revolved about the local x axis."""
    bm = bmesh.new(); rings = []
    for i in range(seg):
        a = 2 * math.pi * i / seg; ca, sa = math.cos(a), math.sin(a)
        rings.append([bm.verts.new((x, r * ca, r * sa)) for x, r in prof])
    for i in range(seg):
        A, B = rings[i], rings[(i + 1) % seg]
        for j in range(len(prof) - 1):
            try:
                bm.faces.new((A[j], A[j + 1], B[j + 1], B[j]))
            except ValueError:
                pass
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    return link(bpy.data.objects.new(name, me), c, m)


def bar(name, a, b, r, c, m):
    a, b = Vector(a), Vector(b); d = b - a
    o = revolve(name, [(0.0, r), (d.length, r)], c, m, seg=10)
    o.matrix_world = Matrix.Translation(a) @ Vector((1, 0, 0)).rotation_difference(d.normalized()).to_matrix().to_4x4()
    return o


def sphere(name, loc, r, c, m, seg=10):
    ob = bpy.data.objects.new(name, bpy.data.meshes.new(name)); bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=max(4, seg // 2), radius=r); bm.to_mesh(ob.data); bm.free()
    link(ob, c, m); ob.location = loc
    return ob


def text(name, body, loc, size, c, m=None, rot=(math.pi / 2, 0, 0)):
    cu = bpy.data.curves.new(name, 'FONT'); cu.body = body; cu.size = size
    o = link(bpy.data.objects.new(name, cu), c, m or M['label']); o.location = loc; o.rotation_euler = rot
    return o


def camera(name, loc, target, c, ortho=None, lens=35):
    cd = bpy.data.cameras.new(name); cd.clip_end = 5e4; cd.clip_start = 0.5
    if ortho:
        cd.type = 'ORTHO'; cd.ortho_scale = ortho
    else:
        cd.lens = lens
    o = bpy.data.objects.new(name, cd); c.objects.link(o); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def append_vehicle(blend):
    with bpy.data.libraries.load(str(blend), link=False) as (src, dst):
        dst.collections = ['WF_WAYFARER_001']
    return dst.collections[0]


def make_all_local():
    for _ in range(5):
        n = 0
        for attr in ('collections', 'objects', 'meshes', 'curves', 'materials', 'node_groups', 'actions', 'images', 'texts', 'lights', 'cameras', 'fonts', 'worlds'):
            for idb in list(getattr(bpy.data, attr)):
                if idb.library is not None:
                    try:
                        idb.make_local(); n += 1
                    except Exception:
                        pass
        if n == 0:
            break
    for lib in list(bpy.data.libraries):
        try:
            bpy.data.libraries.remove(lib)
        except Exception:
            pass


# ---------- engine frames -----------------------------------------------------------------------------------------------------------
ENG = {}
LABELS = {}


def engine_frames():
    for n in range(1, 5):
        ENG[n] = bpy.data.objects[f'ENGINE_N{n}'].matrix_world.copy()


def eng_mat(n, key):
    """Engine frame of engine n in variant key (cluster shift and spool along ship X; the variant's Y offset added by the caller)."""
    return Matrix.Translation((SHIFT[key] + SPOOL[key], 0, 0)) @ ENG[n]


def place(ob, mw, yoff):
    ob.matrix_world = Matrix.Translation((0, yoff, 0)) @ mw @ ob.matrix_world
    return ob


# ---------- variant ship copies -----------------------------------------------------------------------------------------------------
def ship_copy(key, yoff, root):
    c = coll(f'WORK_COMPACT_{key}_SHIP_INSTANCES', root, 'NONE')
    for o in [o for o in bpy.data.objects if o.name.startswith('Assembly_') and o.instance_type == 'COLLECTION']:
        e = bpy.data.objects.new(f'{key}_{o.name}', None); e.instance_type = 'COLLECTION'; e.instance_collection = o.instance_collection
        dx = SHIFT[key] if o.name == 'Assembly_PROPULSION_CLUSTER' else 0.0
        e.matrix_world = Matrix.Translation((dx, yoff, 0)) @ o.matrix_world; c.objects.link(e)
    return c


def engines_spool(key, yoff, c):
    """C3/C4: the cluster's own engine instances sit 6 m aft of their cradles on a spool (the instances in the copied cluster are the
    cluster's engines, so the spool is shown as eight longerons and two hoops; the engine copies move with WORK empties)."""
    if not SPOOL[key]:
        return
    for n in range(1, 5):
        mw = Matrix.Translation((0, yoff, 0)) @ eng_mat(n, key)
        e = bpy.data.objects.new(f'{key}_ENGINE_N{n}_ON_SPOOL', None); e.instance_type = 'COLLECTION'
        e.instance_collection = bpy.data.objects[f'ENGINE_N{n}'].instance_collection; e.matrix_world = mw; c.objects.link(e)
        for k in range(8):
            a = 2 * math.pi * (k + 0.5) / 8; p = Vector((0, 6.3 * math.cos(a), 6.3 * math.sin(a)))
            bar(f'{key}_N{n}_SPOOL_LONGERON_{k}', mw @ (p + Vector((0, 0, 0))), mw @ (p + Vector((-SPOOL[key], 0, 0))), 0.35, c, M['spool'])
        for x in (0.0, -SPOOL[key]):
            h = revolve(f'{key}_N{n}_SPOOL_HOOP_{int(abs(x))}', [(x - 0.3, 6.6), (x + 0.3, 6.6), (x + 0.3, 6.0), (x - 0.3, 6.0)], c, M['spool'], seg=48)
            h.matrix_world = mw @ h.matrix_world


def hide_cluster_engines_in_copy(key):
    """In C3/C4 the copied cluster would also draw its engines at the cradle; they are hidden by giving the copy a cluster without engines
    is not possible with an instance, so the spool engines are drawn 6 m aft and labelled; the cradle engines stay visible as a ghost."""
    return


def truss_extension(key, yoff, c):
    if not SHIFT[key]:
        return
    for k in range(12):
        a = 2 * math.pi * k / 12
        p0 = Vector((-136.3, yoff + 6.0 * math.cos(a), 6.0 * math.sin(a)))
        p1 = Vector((-136.3 + SHIFT[key], yoff + 5.6 * math.cos(a), 5.6 * math.sin(a)))
        bar(f'{key}_THRUST_TRUSS_{k:02d}', p0, p1, 0.6, c, M['truss'])
        if k % 2 == 0:
            q = Vector((-136.3 + SHIFT[key], yoff + 5.6 * math.cos(a + 2 * math.pi / 12), 5.6 * math.sin(a + 2 * math.pi / 12)))
            bar(f'{key}_THRUST_TRUSS_DIAG_{k:02d}', p0, q, 0.35, c, M['truss'])
    for n in range(1, 5):                 # feed and service trunk extensions: from the ship-side FPS flange to the moved engine panel
        e0 = Matrix.Translation((0, yoff, 0)) @ ENG[n] @ Vector((0.0, 0, 0)); e1 = Matrix.Translation((0, yoff, 0)) @ eng_mat(n, key) @ Vector((0.0, 0, 0))
        inward = Vector((0, -e0.y + yoff, -e0.z)).normalized()
        bar(f'{key}_N{n}_FEED_EXTENSION', e0 + inward * 4.0, e1 + inward * 4.0, 0.18, c, M['feed'])
        bar(f'{key}_N{n}_SERVICE_TRUNK_EXTENSION', e0 + inward * 4.6, e1 + inward * 4.6, 0.25, c, M['trunk'])


def big_shields(key, yoff, c):
    r = RES[key]['shield']
    if r['r_fwd'] < 5.0:
        return
    for n in range(1, 5):
        mw = Matrix.Translation((0, yoff, 0)) @ eng_mat(n, key)
        xb = BURN_LOCAL; x0 = xb + r['x0']; x1 = x0 + r['t']
        o = revolve(f'{key}_N{n}_SHADOW_SHIELD_r{r["r_fwd"]:.0f}', [(x0, 0.3), (x0, r['r_aft']), (x1, r['r_fwd']), (x1, 0.3)], c, M['shield'], seg=64)
        o.matrix_world = mw @ o.matrix_world
        f = revolve(f'{key}_N{n}_SHIELD_BURN_FACE_W', [(x0 - 0.06, 0.3), (x0 - 0.06, r['r_aft']), (x0, r['r_aft']), (x0, 0.3)], c, M['armour'], seg=64)
        f.matrix_world = mw @ f.matrix_world


def protection(key, yoff, c):
    if key != 'C4':
        return
    x_tank = -100.0
    for j, s in enumerate((5.0, 10.0, 15.0)):
        o = revolve(f'C4_STERN_SCREEN_{j + 1}', [(x_tank - s - 0.15, 0.0), (x_tank - s - 0.15, 19.9), (x_tank - s + 0.15, 19.9), (x_tank - s + 0.15, 0.0)], c, M['screen'], seg=64)
        o.location.y = yoff
    for k in range(6):
        a = 2 * math.pi * k / 6
        bar(f'C4_SCREEN_MAST_{k}', (x_tank, yoff + 17 * math.cos(a), 17 * math.sin(a)), (x_tank - 15.2, yoff + 17 * math.cos(a), 17 * math.sin(a)), 0.25, c, M['truss'])
    hub_x = -146.0 + SHIFT[key]
    cap = revolve('C4_HUB_ARMOUR_CAP', [(hub_x - 0.6, 0.0), (hub_x - 0.6, 5.9), (hub_x, 5.9), (hub_x, 0.0)], c, M['armour'], seg=48); cap.location.y = yoff
    for n in range(1, 5):
        mw = Matrix.Translation((0, yoff, 0)) @ eng_mat(n, key)
        for i, (dx, r) in enumerate(((2.3, 6.4), (0.0, 7.6), (-5.6, 8.9), (-12.4, 9.9))):
            x = BURN_LOCAL + dx
            o = revolve(f'C4_N{n}_LOOP_AFT_ARMOUR_L{i + 1}', [(x - 0.9, r - 0.7), (x - 0.9, r + 0.7), (x - 0.7, r + 0.7), (x - 0.7, r - 0.7)], c, M['armour'], seg=64)
            o.matrix_world = mw @ o.matrix_world
    for az in (30.0, 150.0, 270.0):
        a = math.radians(az)
        bar(f'C4_BLADE_AFT_BUMPER_{int(az)}', (-133.25 - 6.0, yoff + 6.5 * math.cos(a), 6.5 * math.sin(a)), (-133.25 - 6.0, yoff + 37 * math.cos(a), 37 * math.sin(a)), 0.25, c, M['bumper'])
        for r in (10.0, 20.0, 30.0):
            bar(f'C4_BLADE_BUMPER_STRUT_{int(az)}_{int(r)}', (-133.25 - 6.0, yoff + r * math.cos(a), r * math.sin(a)), (-133.25, yoff + r * math.cos(a), r * math.sin(a)), 0.12, c, M['truss'])


def overlays(key, yoff, c):
    r = RES[key]; sh = r['shield']
    tan_c = min(sh['r_aft'] / sh['x0'], sh['r_fwd'] / (sh['x0'] + sh['t']))
    for n in range(1, 5):
        mw = Matrix.Translation((0, yoff, 0)) @ eng_mat(n, key)
        b = mw @ Vector((BURN_LOCAL, 0, 0))
        sphere(f'{key}_N{n}_BURN_POINT', b, 1.2, c, M['burn'])
        L = r['D_m'] + 40.0; rr = L * tan_c
        o = revolve(f'{key}_N{n}_SHADOW_CONE_SIM', [(0.0, 0.0), (L, rr), (L, 0.0)], c, M['cone'], seg=48)
        o.matrix_world = Matrix.Translation(b) @ (mw.to_3x3().normalized().to_4x4())
    qs = [p[3] for p in r['lit_points']]
    for i, p in enumerate(r['lit_points'][:700]):
        q = p[3]; lvl = 0 if q < 1e6 else 1 if q < 1e7 else 2 if q < 1e8 else 3
        sphere(f'{key}_HOTSPOT_{i:04d}', (p[0], p[1] + yoff, p[2]), 0.55, c, M['hot'][lvl], seg=6)
    hdr = (f"{key}  {r['label']}\n"
           f"piped engine heat {r['piped_four_W'] / 1e12:,.0f} TW = {r['piped_over_budget']:,.0f} x the 10.8 GW drive radiators | "
           f"direct burn on the ship {r['ship_lit_W'] / 1e12:,.2f} TW ({r['ship_lit_over_limit']:,.0f} x 0.1 GW)\n"
           f"eta {r['eta']:.2f} | winding fluence {r['winding_over_limit']:,.0f} x limit | dust {r['dust_nominal_t']:,.0f} t NOMINAL / "
           f"{r['dust_justified_t']:,.0f} t JUSTIFIED | departure {r['departure_if_heat_closed_t']:,.0f} t if the heat closed\nWORK, not canon: OPEN problems shown in red")
    text(f'{key}_HEADER', hdr, (-215.0, yoff - 60.0, 75.0), 4.0, LABELS[key])


def problem_markers(key, yoff, c):
    loc = dict(ENGINE=Vector((-160.0 + SHIFT[key], yoff + 17, 30)), RING=Vector((-165.0 + SHIFT[key] + SPOOL[key], yoff - 17, 30)),
               SHIELD=Vector((-148.0 + SHIFT[key] + SPOOL[key], yoff + 17, -22)), BLADES=Vector((-125.0, yoff + 30, 17)),
               TANK=Vector((-100.0, yoff, -20)), HUB=Vector((-146.0 + SHIFT[key], yoff, 0)), SCREEN=Vector((-110.0, yoff, 20)),
               TRUSS=Vector((-140.0 + SHIFT[key] / 2, yoff, 8)), SHIP=Vector((0.0, yoff, 45)))
    used = {}
    for p in PR:
        if key not in p.get('variants', []):
            continue
        comp = p['components'][0]; base = loc.get(comp, loc['SHIP']); k = used.get(comp, 0); used[comp] = k + 1
        sphere(f'{key}_PROB_{p["id"]}', base, 2.2, c, M['prob'])
        t = p['title'] if len(p['title']) < 50 else p['title'][:48] + '..'
        text(f'{key}_PROB_{p["id"]}_LABEL', f'{p["id"]} [{p["status"]}] {t}', base + Vector((3, -4, 4 + 5 * k)), 3.0, c, M['plabel'])


# ---------- scene -------------------------------------------------------------------------------------------------------------------------
scene = bpy.context.scene; scene.name = 'COMPACT_REVIEW'
ship = append_vehicle(ROOT / 'assets/wayfarer/WF_WAYFARER_001.blend')
make_all_local()
top = bpy.data.collections.new('WF_APPROVED_SHIP_C1'); scene.collection.children.link(top); top.children.link(ship)
for cc in ship.children_recursive:
    if cc.name.split('.')[0] in ('40_SIM_RIG', '30_CAMERAS', '20_HUMAN_SCALE'):
        cc.hide_viewport = True; cc.hide_render = True
engine_frames()
work = coll('WORK_COMPACT', scene.collection)
cams = coll('30_CAMERAS_COMPACT', scene.collection, 'NONE')
for j, key in enumerate(('C1', 'C2', 'C3', 'C4')):
    yoff = DY * j
    c = coll(f'WORK_COMPACT_{key}', work)
    if j:
        ship_copy(key, yoff, c)
    truss_extension(key, yoff, c); engines_spool(key, yoff, c); big_shields(key, yoff, c); protection(key, yoff, c)
    LABELS[key] = coll(f'WORK_COMPACT_{key}_LABELS', c)
    ov = coll(f'WORK_COMPACT_{key}_OVERLAYS_SIM', c); overlays(key, yoff, ov)
    pm = coll(f'WORK_COMPACT_{key}_PROBLEMS', c); problem_markers(key, yoff, pm)

# lights and world
w = bpy.data.worlds.new('COMPACT_WORLD'); scene.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.01, 0.012, 0.02, 1.0)
sun = bpy.data.objects.new('COMPACT_SUN', bpy.data.lights.new('COMPACT_SUN', 'SUN')); sun.data.energy = 3.5
sun.rotation_euler = (math.radians(50), math.radians(-25), math.radians(-40)); scene.collection.objects.link(sun)
scene.render.resolution_x, scene.render.resolution_y = 1600, 900
try:
    scene.view_settings.view_transform = 'AgX'
except Exception:
    pass

mid = Vector((0, 0, 0)); aft = Vector((-150.0, 0, 0))
cv = {
    'whole_ship': (camera('CAM_COMPACT_WHOLE', Vector((-260, -330, 170)), Vector((0, 0, 0)), cams, lens=35), {'C1'}, False),
    'problems_overlay': (camera('CAM_COMPACT_PROBLEMS', Vector((-115, -300, 35)), Vector((-115, 0, 35)), cams, ortho=230), {'C1', 'LABELS'}, True),
    'problems_C4': (camera('CAM_COMPACT_PROBLEMS_C4', Vector((-120, DY * 3 - 300, 35)), Vector((-120, DY * 3, 35)), cams, ortho=240), {'C4', 'LABELS'}, True),
    'aft_cluster': (camera('CAM_COMPACT_AFT_CLUSTER', Vector((-215, -75, 55)), Vector((-140, 0, 0)), cams, lens=32), {'C1'}, False),
    'braking_facing': (camera('CAM_COMPACT_BRAKING', Vector((-330, -60, 40)), Vector((-130, 0, 0)), cams, lens=40), {'C1'}, False),
    'side': (camera('CAM_COMPACT_SIDE', Vector((0, -900, 0)), Vector((0, 0, 0)), cams, ortho=360), {'C1'}, True),
    'top': (camera('CAM_COMPACT_TOP', Vector((0, 0, 900)), Vector((0, 0, 0)), cams, ortho=360), {'C1'}, True),
    'rear': (camera('CAM_COMPACT_REAR', Vector((-900, 0, 0)), Vector((0, 0, 0)), cams, ortho=110), {'C1'}, True),
    'component_breakdown': (camera('CAM_COMPACT_COMPONENTS', Vector((-175, -48, 30)), Vector((-150, 12, 12)), cams, lens=30), {'C1'}, False),
    'variants_sheet': (camera('CAM_COMPACT_VARIANTS', Vector((-480, DY * 1.5 - 330, 210)), Vector((-120, DY * 1.5, 0)), cams, lens=35), {'C1', 'C2', 'C3', 'C4'}, False),
    'variants_side': (camera('CAM_COMPACT_VARIANTS_SIDE', Vector((-140, DY * 1.5, 900)), Vector((-140, DY * 1.5, 0)), cams, ortho=640), {'C1', 'C2', 'C3', 'C4'}, True),
}
for k in ('C2', 'C3', 'C4'):
    yo = DY * ('C1', 'C2', 'C3', 'C4').index(k)
    cv[f'aft_{k}'] = (camera(f'CAM_COMPACT_AFT_{k}', Vector((-245, yo - 85, 60)), Vector((-150, yo, 0)), cams, lens=32), {k}, False)
# component labels on C1 (propulsion / shielding / cooling)
lab = coll('WORK_COMPACT_C1_COMPONENT_LABELS', bpy.data.collections['WORK_COMPACT_C1'])
mw = ENG[1]
for name, xl, r, txt in (('BURN', BURN_LOCAL, 0.0, 'burn point (fusion pulses, 5.7 kHz)'), ('L4', BURN_LOCAL - 12.4, 9.9, 'nozzle loop L4 (REBCO, round cryostat)'),
                         ('L2', BURN_LOCAL, 7.6, 'nozzle loop L2'), ('SHIELD', BURN_LOCAL + 7.1, 5.4, 'shadow shield LiH + W/B4C face'),
                         ('C2', BURN_LOCAL + 3.0, 4.2, 'closure coil C2'), ('CART', -4.6, 3.4, 'drive cartridge (targets, driver)'),
                         ('COLLAR', -9.9, 5.6, 'thrust collar + trunnions'), ('PANEL', -9.6, 5.6, 'service panel: Li hot loop, cold loop, power, targets, H2')):
    p = mw @ Vector((xl, 0, r + 0.6)); q = p + Vector((0, -12, 8))
    sphere(f'LBL_{name}_DOT', p, 0.35, lab, M['label'], seg=8)
    bar(f'LBL_{name}_LEADER', p, q, 0.06, lab, M['label'])
    text(f'LBL_{name}', txt, q + Vector((0.3, 0, 0.3)), 1.1, lab)
scene.camera = cv['whole_ship'][0]
out = HERE / 'REVIEW_COMPACT.blend'
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
print('saved', out, flush=True)
if RENDER:
    rd = HERE / 'renders'; rd.mkdir(exist_ok=True)
    work_cols = {k: bpy.data.collections[f'WORK_COMPACT_{k}'] for k in ('C1', 'C2', 'C3', 'C4')}
    only = [v for v in os.environ.get('ONLY', '').split(',') if v]
    for vn, (cam, show, tech) in cv.items():
        if only and vn not in only:
            continue
        top.hide_render = 'C1' not in show
        for k, cc in work_cols.items():
            cc.hide_render = k not in show
            LABELS[k].hide_render = 'LABELS' not in show
            bpy.data.collections[f'WORK_COMPACT_{k}_PROBLEMS'].hide_render = 'LABELS' not in show
        scene.render.engine = 'BLENDER_WORKBENCH' if tech else 'BLENDER_EEVEE'
        scene.display.shading.light = 'STUDIO'; scene.display.shading.color_type = 'MATERIAL'
        if not tech:
            scene.eevee.taa_render_samples = 16
        scene.camera = cam; scene.render.filepath = str(rd / f'compact_{vn}.png')
        bpy.ops.render.render(write_still=True); print('rendered', vn, flush=True)
    top.hide_render = False
    for k, cc in work_cols.items():
        cc.hide_render = False; LABELS[k].hide_render = False; bpy.data.collections[f'WORK_COMPACT_{k}_PROBLEMS'].hide_render = False
    scene.camera = cv['whole_ship'][0]
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
