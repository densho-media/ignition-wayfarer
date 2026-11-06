"""Build lab/studies/graded-thermal-blade/REVIEW_GRADED_THERMAL_BLADE.blend (owner review file: opens showing the change, nothing to run) and
its renders. Study code: nothing in src/ reads it.

  /snap/bin/blender -b --factory-startup --python lab/studies/graded-thermal-blade/make_review.py

The after ship (assets/wayfarer, this branch) and the before ship (lab/studies/graded-thermal-blade/before, main 90df1a9) are appended, made
local and coloured by function (hot red, warm orange, low pale blue, structure grey); the before ship sits 140 m to +Y. WORK_GTB_
collections hold labels and the scene notes. Cameras: CAM_GTB_SIDE, _TOP, _THREEQUARTER, _CLOSEUP(_BEFORE), _THERMAL(_BEFORE),
_SUPPORT, _BEFORE_AFTER.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT/'src/wayfarer'))
import spec  # noqa: E402
import functional_colors as fc  # noqa: E402
import layout, radiator_zones as rz  # noqa: E402,E401

BEFORE_Y = 140.0
s = spec.load()[0]


def append_vehicle(blend, tag):
    with bpy.data.libraries.load(str(blend), link=False) as (src, dst):
        dst.collections = ['WF_WAYFARER_001']
    c = dst.collections[0]; c.name = f'WORK_GTB_{tag}_SHIP'
    return c


def make_all_local():
    for _ in range(4):
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


def colour(objs):
    owners = {}
    for c in bpy.data.collections:
        n = c.name.split('.')[0]
        base = n[4:] if n.startswith('GEN_') else n
        if base.startswith('WF_'):
            for d in [c]+list(c.children_recursive):
                owners.setdefault(d.name, fc.asset_key(base))
    counts = {}
    for o in objs:
        if o.type not in ('MESH', 'CURVE', 'SURFACE', 'META', 'FONT'):
            continue
        a = next((owners[c.name] for c in o.users_collection if c.name in owners), None) or 'STRUCTURE'
        bank = o.get('storage_bank') or 'aft'
        f = o.get('wf_function') or fc.classify(a, o.name.split('.')[0], o.get('kind', ''), o.get('species', ''), bank=bank)
        if f is None:
            continue
        o.color = fc.PALETTE[f][1]; counts[f] = counts.get(f, 0)+1
    return counts


def mat(name, rgba):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = rgba; m.use_nodes = False
    return m


def text(name, body, loc, size, c, rgba, rot=(math.pi/2, 0, 0), align='CENTER'):
    cu = bpy.data.curves.new(name, 'FONT'); cu.body = body; cu.size = size; cu.align_x = align
    o = bpy.data.objects.new(name, cu); o.location = loc; o.rotation_euler = rot; c.objects.link(o); o.color = rgba
    o.data.materials.append(mat('WORK_'+name, rgba))
    return o


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene; scene.name = 'GTB_REVIEW'
after = append_vehicle(ROOT/'assets/wayfarer/WF_WAYFARER_001.blend', 'AFTER')
before = append_vehicle(HERE/'before/wayfarer/WF_WAYFARER_001.blend', 'BEFORE')
make_all_local()
top_a = bpy.data.collections.new('WORK_GTB_AFTER_graded_thermal_blade'); scene.collection.children.link(top_a); top_a.color_tag = 'COLOR_07'
top_b = bpy.data.collections.new('WORK_GTB_BEFORE_main_90df1a9_baffles'); scene.collection.children.link(top_b); top_b.color_tag = 'COLOR_07'
top_a.children.link(after); top_b.children.link(before)
for o in before.all_objects:
    if o.parent is None:
        o.location.y += BEFORE_Y
counts = colour(list(bpy.data.objects))
for _ in range(4):
    inst = [ob for ob in scene.objects if ob.instance_type == 'COLLECTION' and ob.instance_collection is not None]
    if not inst:
        break
    bpy.ops.object.select_all(action='DESELECT')
    for ob in inst:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = inst[0]
    bpy.ops.object.duplicates_make_real(use_base_parent=True, use_hierarchy=True)
    for ob in inst:
        ob.instance_type = 'NONE'
counts = colour([ob for ob in scene.objects if tuple(ob.color[:3]) == (1.0, 1.0, 1.0)]) or counts
print('WF_REVIEW colours', counts, flush=True)
for c in list(after.children_recursive)+list(before.children_recursive):
    if c.name.split('.')[0] in ('40_SIM_RIG', '30_CAMERAS', '20_HUMAN_SCALE'):
        c.hide_viewport = True; c.hide_render = True

labels = bpy.data.collections.new('WORK_GTB_LABELS'); scene.collection.children.link(labels); labels.color_tag = 'COLOR_07'
o = layout.origins(s); white = (0.95, 0.95, 0.95, 1.0); dim = (0.75, 0.75, 0.75, 1.0)
P = {x['id']: x for x in rz.placed(s)}; L = rz.layers(s)
res = {n: json.load(open(HERE/f'results/{n}.json')) for n in ('base_baffled', 'G_final', 'G_eol')}
for i, (t, x) in enumerate([('HOT 1800 K', (o['RADIATOR_FRONT']+o['RADIATOR_AFT'])/2), ('V-groove\nbulkhead', L[1]['x_inner']),
                            ('WARM 440 K', (P['WARM']['x0']+P['WARM']['x1'])/2), ('LOW 300 K', (P['LOW']['x0']+P['LOW']['x1'])/2),
                            ('RINGS', o['RING_A']+3)]):
    text(f'LBL_A_{i}', t, (x, 0, 46+(7 if i % 2 else 0)), 4.0, labels, white)
for i, (t, x) in enumerate([('HOT 1800 K', (o['RADIATOR_FRONT']+o['RADIATOR_AFT'])/2), ('2 baffle\ndiscs', 49.9), ('WARM', 61.4),
                            ('2 baffle\ndiscs', 72.9), ('LOW', 83.6)]):
    text(f'LBL_B_{i}', t, (x, BEFORE_Y, 46+(7 if i % 2 else 0)), 4.0, labels, dim)
w, lo = res['G_final']['WARM'], res['G_final']['LOW']; bw, bl = res['base_baffled']['WARM'], res['base_baffled']['LOW']
text('LBL_AFTER', f"AFTER: Graded Thermal Blade - 1 V-groove bulkhead (3 sheets)\nmax drive net WARM {w['net_MW']:.2f} MW ({w['margin']:+.0%}), "
     f"LOW {lo['net_MW']:.2f} MW ({lo['margin']:+.0%})", (0, 0, 72), 5.0, labels, white)
text('LBL_BEFORE', f"BEFORE: main 90df1a9 - 2 stations x 2 flat baffle discs\nmax drive net WARM {bw['net_MW']:.2f} MW ({bw['margin']:+.0%}), "
     f"LOW {bl['net_MW']:.2f} MW ({bl['margin']:+.0%})", (0, BEFORE_Y, 72), 5.0, labels, dim)


def camera(name, loc, look, lens=24, ortho=None):
    cam = bpy.data.cameras.new(name); ob = bpy.data.objects.new(name, cam); scene.collection.objects.link(ob)
    ob.location = loc; ob.rotation_euler = (Vector(look)-Vector(loc)).to_track_quat('-Z', 'Z').to_euler()
    cam.clip_end = 5000; cam.clip_start = 0.1
    if ortho:
        cam.type = 'ORTHO'; cam.ortho_scale = ortho
    else:
        cam.lens = lens
    return ob


xr = (o['RADIATOR_FRONT']+o['RADIATOR_ZONE_FRONT'])/2
cams = dict(
    side=(camera('CAM_GTB_SIDE', (0, -700, 20), (0, 0, 20), ortho=330), False),
    top=(camera('CAM_GTB_TOP', (0, 0, 700), (0, 0, 0), ortho=330), False),
    threequarter=(camera('CAM_GTB_THREEQUARTER', (300, -300, 190), (10, 0, 0), lens=30), False),
    closeup=(camera('CAM_GTB_CLOSEUP', (xr+70, -95, 70), (xr-5, 0, 5), lens=28), False),
    thermal=(camera('CAM_GTB_THERMAL', (xr-8, -60, -95), (xr-8, -12, 6), lens=24), False),
    support=(camera('CAM_GTB_SUPPORT', (L[0]['x_inner']+14, -12, 50), (L[0]['x_inner']+1.5, 0, 33), lens=24), False),
    before_after=(camera('CAM_GTB_BEFORE_AFTER', (xr+160, -260, 260), (xr-20, 70, 0), lens=26), True),
)
for k in ('closeup', 'thermal'):
    ob = cams[k][0]; cams[k+'_before'] = (camera(ob.name+'_BEFORE', tuple(ob.location+Vector((0, BEFORE_Y, 0))), tuple(Vector((0, 0, 0))), lens=ob.data.lens), True)
    cams[k+'_before'][0].rotation_euler = ob.rotation_euler.copy()
scene.render.engine = 'BLENDER_WORKBENCH'
sh = scene.display.shading; sh.light = 'STUDIO'; sh.color_type = 'OBJECT'; sh.show_shadows = False; sh.show_cavity = True
sh.cavity_type = 'WORLD'; sh.background_type = 'VIEWPORT'
scene.render.resolution_x, scene.render.resolution_y = 1600, 1000
scene.world = bpy.data.worlds.new('WF_World') if scene.world is None else scene.world
scene.world.color = (0.03, 0.035, 0.05)
notes = bpy.data.texts.new('README_GRADED_THERMAL_BLADE'); notes.write((HERE/'NOTES.md').read_text())
t = bpy.data.texts.new('FUNCTIONAL_COLOR_LEGEND'); t.write(fc.legend_text())

render_dir = ROOT/'runs/renders/graded_thermal_blade'; render_dir.mkdir(parents=True, exist_ok=True)
for name, (cam, show_before) in cams.items():
    scene.camera = cam
    top_b.hide_render = not show_before
    top_a.hide_render = name.endswith('_before')
    for ob in labels.objects:
        ob.hide_render = (ob.name.startswith(('LBL_B', 'LBL_BEFORE')) and not show_before) or name in ('closeup', 'thermal', 'support', 'closeup_before', 'thermal_before')
    scene.render.filepath = str(render_dir/f'gtb_{name}.png')
    bpy.ops.render.render(write_still=True)
top_a.hide_render = False; top_b.hide_render = False
for ob in labels.objects:
    ob.hide_render = False
scene.camera = cams['closeup'][0]
for scr in bpy.data.screens:
    for area in scr.areas:
        if area.type == 'VIEW_3D':
            for sp in area.spaces:
                if sp.type == 'VIEW_3D':
                    sp.shading.type = 'SOLID'; sp.shading.color_type = 'OBJECT'; sp.clip_end = 5000
                    sp.region_3d.view_perspective = 'CAMERA'
bpy.context.preferences.filepaths.save_version = 0
path = HERE/'REVIEW_GRADED_THERMAL_BLADE.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
print('WF_REVIEW saved', path, flush=True)
