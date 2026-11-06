"""Render the cameras of REVIEW_FIJI_DRIVE.blend (study helper). Each camera carries 'render_scenes'.

  /snap/bin/blender -b lab/variants/fiji-drive/REVIEW_FIJI_DRIVE.blend --python lab/variants/fiji-drive/render_review.py -- --out DIR [--cams ...] [--samples N] [--size W H]
"""
import argparse
import sys
from pathlib import Path

import bpy

a = argparse.ArgumentParser(); a.add_argument('--out', type=Path, required=True); a.add_argument('--cams', nargs='+'); a.add_argument('--samples', type=int, default=32)
a.add_argument('--size', type=int, nargs=2, default=(1920, 1080)); a.add_argument('--scenes', nargs='+')
a = a.parse_args(sys.argv[sys.argv.index('--')+1:])
a.out.mkdir(parents=True, exist_ok=True)
TAG = {'FIJI_DRIVE': '', 'FIJI_DRIVE_ACTIVE': '__active', 'BEFORE_MAIN_5A913F9': '__before_main'}
for ob in [o for o in bpy.data.objects if o.type == 'CAMERA' and o.name.startswith('CAM_FIJI')]:
    if a.cams and ob.name not in a.cams:
        continue
    for name in ob.get('render_scenes', []):
        if a.scenes and name not in a.scenes:
            continue
        sc = bpy.data.scenes[name]; sc.camera = ob
        sc.render.resolution_x, sc.render.resolution_y = a.size; sc.cycles.samples = a.samples
        workbench = ob.name in ('CAM_FIJI_OVERVIEW', 'CAM_FIJI_SYSTEMS')
        if workbench:
            sc.render.engine = 'BLENDER_WORKBENCH'; sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'MATERIAL' if ob.name == 'CAM_FIJI_SYSTEMS' else 'OBJECT'
            sh.show_cavity = True; sh.show_object_outline = True; sh.background_type = 'WORLD'
            sc.view_settings.view_transform = 'Standard'
        else:
            sc.render.engine = 'CYCLES'; sc.view_settings.view_transform = 'AgX'
        sc.render.filepath = str(a.out/f'{ob.name}{TAG.get(name, "")}.png')
        bpy.ops.render.render(write_still=True, scene=sc.name)
        print('WF_RENDER', sc.render.filepath, flush=True)
