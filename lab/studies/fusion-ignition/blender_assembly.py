"""Progressive-assembly review of the Vertex engine for the Fusion Engineering page (research, not canon; owner brief 2026-11-24 09:49Z).

  /snap/bin/blender -b --factory-startup --python lab/studies/fusion-ignition/blender_assembly.py [-- --no-render]

Appends the approved engine (assets/wayfarer/components/WF_VERTEX_ENGINE.blend, made local, untouched) and saves REVIEW_ASSEMBLY.blend
with one scene per assembly step (ASM_01 ... ASM_06): each scene links the engine's functional collections (VTX_<category>) that are in
place by that step, in the page's dependency order (PROTOTYPE order, web/engineering/fusion-ignition.js ASM_ORDER). The file opens on the
last step; the earlier steps are the scene list. Renders go to /mnt/project-files/fusion-engineering/.
"""
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RENDER = '--no-render' not in sys.argv
STEPS = [('01_frame', 'Thrust frame', ['STRUCTURE']),
         ('02_shield', 'Shadow shield', ['SHIELDING']),
         ('03_cold', 'Cold lines, then the closure coils', ['CRYOGENIC', 'MAGNETIC_COILS']),
         ('04_nozzle', 'Magnetic nozzle', ['MAGNETIC_NOZZLE']),
         ('05_feeds', 'Hot circuit, power and fuel', ['HOT_THERMAL', 'ELECTRICAL', 'FUEL']),
         ('06_complete', 'Injection, diagnostics and service: complete', ['TARGET_INJECTION', 'INSTRUMENTATION', 'SERVICE', 'FUSION_REACTION'])]

bpy.ops.wm.read_factory_settings(use_empty=True)
base = bpy.context.scene; base.name = 'ASM_ALL'
with bpy.data.libraries.load(str(ROOT / 'assets/wayfarer/components/WF_VERTEX_ENGINE.blend'), link=False) as (src, dst):
    dst.collections = ['WF_VERTEX_ENGINE']
eng = dst.collections[0]
for _ in range(5):
    n = 0
    for attr in ('collections', 'objects', 'meshes', 'curves', 'materials', 'node_groups', 'images'):
        for idb in list(getattr(bpy.data, attr)):
            if idb.library is not None:
                try:
                    idb.make_local(); n += 1
                except Exception:
                    pass
    if n == 0:
        break
cats = {c.name[4:]: c for c in bpy.data.collections if c.name.startswith('VTX_')}
print('categories', sorted(cats), flush=True)
base.collection.children.link(eng)
for c in bpy.data.collections:
    if c.name in ('VTX_VISUAL_EFFECTS', 'REVIEW_VERTEX_ENGINE'):
        c.hide_render = True; c.hide_viewport = True

w = bpy.data.worlds.new('WORK_ASSEMBLY_WORLD'); w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.012, 0.014, 0.02, 1)
helpers = bpy.data.collections.new('WORK_ASSEMBLY_CAMERA_LIGHTS')
for nm, loc, en in (('KEY', (10, -30, 25), 6.0), ('FILL', (-40, 25, -10), 2.0), ('RIM', (-45, -5, 30), 3.0)):
    ld = bpy.data.lights.new(nm, 'SUN'); ld.energy = en; lo = bpy.data.objects.new(f'WORK_ASSEMBLY_LIGHT_{nm}', ld); helpers.objects.link(lo)
    lo.rotation_euler = (Vector((-16, 0, 0)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
cd = bpy.data.cameras.new('CAM_assembly'); cd.lens = 32; cd.clip_end = 5e3
cam = bpy.data.objects.new('CAM_assembly', cd); helpers.objects.link(cam)
cam.location = (14, -34, 18); cam.rotation_euler = (Vector((-16, 0, 0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
base.collection.children.link(helpers); base.camera = cam; base.world = w

scenes = []
for k, (sid, title, add) in enumerate(STEPS):
    sc = bpy.data.scenes.new(f'ASM_{sid}'); sc.world = w; sc.camera = cam
    sc.collection.children.link(helpers)
    top = bpy.data.collections.new(f'WORK_ASSEMBLY_{sid}'); top.color_tag = 'COLOR_07'; sc.collection.children.link(top)
    for _, _, cs in STEPS[:k + 1]:
        for c in cs:
            if c in cats:
                top.children.link(cats[c])
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
    sc.render.engine = 'BLENDER_EEVEE'; sc.eevee.taa_render_samples = 16
    scenes.append((sid, title, sc))
bpy.context.window_manager.windows[0].scene = scenes[-1][2] if bpy.context.window_manager.windows else None
out = HERE / 'REVIEW_ASSEMBLY.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True); print('saved', out, flush=True)
if RENDER:
    rd = Path('/mnt/project-files/fusion-engineering'); rd.mkdir(parents=True, exist_ok=True)
    for sid, title, sc in scenes:
        sc.render.filepath = str(rd / f'assembly_{sid}.png')
        bpy.ops.render.render(write_still=True, scene=sc.name); print('rendered', sid, title, flush=True)
