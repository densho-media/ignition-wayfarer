"""Build work/fuel-propellant/REVIEW_FUEL-PROPELLANT.blend: the owner review file for FPS V0 (opens on the aft feed train, nothing to run).

  /snap/bin/blender -b --factory-startup --python work/fuel-propellant/make_review.py -- [--render DIR]

The built ship of this branch is appended and made local. Every FPS object and the four feed run tanks are also linked into the pink
WORK_FUEL_PROPELLANT collection (the generator still owns them). Solid shading with object colour shows the functional species colours.
The aft hull skin, spine casing and radiator blades are hidden in this file only, and every other part is dark grey, so the train is visible. Scenes: FUEL_PROPELLANT (opens: the feed train alone) and SHIP_CONTEXT (the whole ship). Cameras: CAM_FPS_AFT_TRAIN (opens on it),
CAM_FPS_BRANCHES (header and engine branches from aft), CAM_FPS_REFUEL (the receptacle on the farm deck). Study helper; nothing reads it.
"""
import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SHIP = ROOT/'assets/wayfarer/WF_WAYFARER_001.blend'
a = argparse.ArgumentParser(); a.add_argument('--out', type=Path, default=HERE/'REVIEW_FUEL-PROPELLANT.blend'); a.add_argument('--render', type=Path)
a = a.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
CUT = ('Hull_Aft_Body', 'Prod_SP_CASING', 'Casing_Seams', 'Casing_Access', 'Survival_Crawler_Rail', 'Drone_Rail_DS-13')


def make_all_local():
    for _ in range(5):
        n = 0
        for attr in ('collections', 'objects', 'meshes', 'curves', 'materials', 'node_groups', 'actions', 'images', 'texts', 'lights', 'cameras', 'fonts'):
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


def camera(name, loc, target, lens=35):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name)); cam.data.lens = lens; cam.data.clip_end = 6000; cam.data.clip_start = 0.1
    cam.location = loc; cam.rotation_euler = (Vector(target)-Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return cam


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene; scene.name = 'FUEL_PROPELLANT'
with bpy.data.libraries.load(str(SHIP), link=False) as (src, dst):
    dst.collections = ['WF_WAYFARER_001']
ship = dst.collections[0]; scene.collection.children.link(ship)
make_all_local()
for c in ship.children_recursive:
    if c.name.split('.')[0] in ('40_SIM_RIG', '30_CAMERAS', '20_HUMAN_SCALE'):
        c.hide_viewport = True; c.hide_render = True
work = bpy.data.collections.new('WORK_FUEL_PROPELLANT'); work.color_tag = 'COLOR_07'; scene.collection.children.link(work)
fps = [o for o in bpy.data.objects if o.name.startswith(('FPS_', 'IF_FPS_', 'Feed_Run_Tank'))]
for o in fps:
    if o.name not in work.objects:
        work.objects.link(o)
sys.path.insert(0, str(ROOT/'src/wayfarer'))
import functional_colors as fc  # noqa: E402
SPC = {'deuterium': 'DEUTERIUM', 'helium-3': 'HELIUM3', 'hydrogen': 'HYDROGEN'}
hidden = []
for c in ship.children_recursive:                 # the radiator blades would hide the aft train from every side
    if c.name.split('.')[0] == '13_THERMAL':
        c.hide_viewport = True; c.hide_render = True; hidden.append(c.name)
for o in bpy.data.objects:
    if o.name.startswith(CUT):
        o.hide_viewport = True; o.hide_render = True; hidden.append(o.name)
    elif o in fps:                                # species colour (functional_colors); helium purge and service parts cream
        key = SPC.get(o.get('species', '')) or SPC.get(o.get('fuel_family', '')) or 'SERVICE'
        o.color = fc.PALETTE[key][1]
    elif o.instance_type != 'COLLECTION':         # an instancer's colour would paint everything it instances
        o.color = (0.30, 0.31, 0.33, 1.0)
cams = bpy.data.collections.new('WORK_FUEL_PROPELLANT_CAMERAS'); work.children.link(cams)
CAMS = [camera('CAM_FPS_AFT_TRAIN', (-54.0, -72.0, 38.0), (-118.0, 0.0, 0.0)),
        camera('CAM_FPS_BRANCHES', (-126.0, 0.0, 42.0), (-138.0, 0.0, 0.0), lens=30),
        camera('CAM_FPS_REFUEL', (101.0, -30.0, -42.0), (109.5, -13.0, -25.0), lens=35)]
for c in CAMS:
    cams.objects.link(c)
scene.camera = CAMS[0]
# The opening scene shows the feed train alone (the ship's cage, envelopes and cluster frame hide it from every side); SHIP_CONTEXT has
# the whole ship with the same cameras.
ctx = bpy.data.scenes.new('SHIP_CONTEXT'); ctx.collection.children.link(ship); ctx.collection.children.link(work); ctx.camera = CAMS[0]
scene.view_layers[0].layer_collection.children[ship.name].exclude = True
txt = bpy.data.texts.new('README_FUEL_PROPELLANT')
txt.write(__doc__ + f'\nObjects in WORK_FUEL_PROPELLANT: {len(fps)}. Hidden in this file only: {", ".join(sorted(set(n.split(".")[0] for n in hidden)))}.\n'
          'Record: docs/FUEL_SYSTEM.md. All dimensions PROTOTYPE; engine interfaces IF_FPS_* OPEN.\n')
for sc in (scene, ctx):
    sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'OBJECT'; sh.show_cavity = True
    sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
for scr in bpy.data.screens:
    for area in scr.areas:
        if area.type == 'VIEW_3D':
            for sp in area.spaces:
                if sp.type == 'VIEW_3D':
                    sp.shading.type = 'SOLID'; sp.shading.color_type = 'OBJECT'; sp.clip_end = 6000; sp.clip_start = .1
                    sp.region_3d.view_perspective = 'CAMERA'
if a.render:
    a.render.mkdir(parents=True, exist_ok=True)
    for sc in (scene, ctx):
        for c in CAMS:
            sc.camera = c; sc.render.filepath = str(a.render/f'{sc.name}__{c.name}.png'); bpy.ops.render.render(write_still=True, scene=sc.name)
            print('WF_RENDER', sc.render.filepath, flush=True)
        sc.camera = CAMS[0]
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(a.out), compress=True)
print('WF_REVIEW saved', a.out, len(fps), flush=True)
