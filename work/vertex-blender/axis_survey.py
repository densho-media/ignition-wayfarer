"""Survey what occupies the canonical ship's axis (T05 Rev 2, launcher option A). Reads the localised ship cache; writes axis_survey.json.

  /snap/bin/blender -b /tmp/wayfarer_vertex_ship_local.blend --python work/vertex-blender/axis_survey.py

At each X station (1 m) it casts rays outward from the axis in 12 directions and records the first hit within r 0.8, 1.5 and 3.0 m
(the barrel bore, barrel + coils, barrel + service crawlway). Nothing is written to the ship.
"""
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sc = bpy.context.scene
for c in bpy.data.collections:
    if c.name.split('.')[0] in ('40_SIM_RIG', '30_CAMERAS', '20_HUMAN_SCALE'):
        c.hide_render = True; c.hide_viewport = True
for o in bpy.data.objects:
    if o.name.startswith(('DRIVE_DEBUG_',)):
        o.hide_viewport = True
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
out = {'stations': [], 'radii_m': [0.8, 1.5, 3.0]}
for xi in range(-145, 146):
    x = float(xi)
    row = {'x': x}
    for R in out['radii_m']:
        hit = None
        for k in range(12):
            a = 2*math.pi*k/12
            d = Vector((0, math.cos(a), math.sin(a)))
            ok, loc, nrm, idx, ob, mw = sc.ray_cast(dg, Vector((x, 0, 0)), d, distance=R)
            if ok:
                hit = ob.name.split('.')[0]; break
        row[f'r{R}'] = hit
    out['stations'].append(row)
(HERE/'axis_survey.json').write_text(json.dumps(out, indent=0))
# summary: contiguous runs
for R in out['radii_m']:
    runs, cur = [], None
    for s in out['stations']:
        h = s[f'r{R}']
        if cur and cur[2] == h:
            cur[1] = s['x']
        else:
            cur = [s['x'], s['x'], h]; runs.append(cur)
    print('AXIS r', R, [(a, b, h) for a, b, h in runs])
