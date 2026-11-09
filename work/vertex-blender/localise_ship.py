"""Write a self-contained copy of the canonical vehicle (every linked subsystem made local) for build_vertex.py to append.

  /snap/bin/blender -b --factory-startup --python work/vertex-blender/localise_ship.py -- <out.blend>

Reads assets/wayfarer/WF_WAYFARER_001.blend and never writes it; the copy is a disposable cache (not in Git). About 75 s.
Appending the linked vehicle and making its IDs local one by one takes tens of minutes; Blender's make_local(type='ALL') does it at once.
"""
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
out = sys.argv[sys.argv.index('--')+1]
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer/WF_WAYFARER_001.blend'))
bpy.ops.file.make_paths_absolute()
for o in bpy.context.view_layer.objects:
    o.select_set(True)
bpy.ops.object.make_local(type='ALL')
left = [i.name for a in ('collections', 'objects', 'meshes', 'materials', 'curves', 'images', 'node_groups') for i in getattr(bpy.data, a) if i.library]
if left:
    raise SystemExit(f'still linked: {left[:10]}')
bpy.ops.wm.save_as_mainfile(filepath=out, relative_remap=False)
print('WF_VTX localised ship', out, len(bpy.data.objects), 'objects', flush=True)
