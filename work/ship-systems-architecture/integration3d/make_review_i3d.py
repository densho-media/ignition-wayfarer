"""3D integration Checkpoint 1 review file: the Phase VI review (production ship unchanged + WORK_ISSA6_TRACK_F1) plus the Stage B propellant
alternatives as separate, isolatable collections built from results/i3d_tanks.json:
  WORK_I3D_TANKS_TA_STRETCH   (visible)  every vessel lengthened forward + the translated Brow envelope
  WORK_I3D_TANKS_TB_TANDEM    (hidden)   the mission-modular forward segment, its intermediate deck and translated Brow
  WORK_I3D_TANKS_TC_DENSIFY   (hidden)   the shorter stretch with re-allocated species colours + translated Brow
The Phase VI extension envelope (linear estimate) is hidden as superseded.

    /snap/bin/blender -b assets/wayfarer/WF_WAYFARER_001.blend --python work/ship-systems-architecture/integration3d/make_review_i3d.py [-- --render]
"""
import json
import math
import sys
from pathlib import Path

import bpy

HERE = Path(bpy.data.filepath).resolve().parents[2] / 'work' / 'ship-systems-architecture'
src = (HERE / 'make_review6.py').read_text().rsplit('\nmain()', 1)[0]
src = src.replace("    cols = build6(r6)\n    checks6()\n", "    cols = build6(r6)\n    checks6()\n    I3D_HOOK(r6)\n")
src = src.replace("if '--render' in sys.argv:", "if False:")
src = src.replace("out = HERE / 'REVIEW_ISSA_PHASE6.blend'", "out = HERE / 'REVIEW_I3D_CP1.blend'")
src = src.replace("    bpy.context.scene.camera = c1\n", "    bpy.context.scene.camera = c1\n    I3D_RENDER()\n")
ns = {'__file__': str(HERE / 'make_review6.py'), '__name__': 'make_review6'}
T = json.loads((HERE / 'results' / 'i3d_tanks.json').read_text())
SPC = {'helium-3': (0.56, 0.30, 0.88), 'hydrogen': (0.14, 0.32, 0.92), 'deuterium': (0.02, 0.56, 0.52)}
ALTS = {}


def hook(r6):
    coll, mat, cyl_x, ring_x, label, S, fs = ns['coll'], ns['mat'], ns['cyl_x'], ns['ring_x'], ns['label'], ns['S'], ns['_fs']
    old = bpy.data.collections.get('WORK_ISSA6_F1_FUEL_EXTENSION_ENVELOPE')
    if old:
        old.hide_viewport = True
        for o in old.all_objects: o.hide_render = True
    ts = fs.tanks(S); x1 = T['farm']['x1']; mats = {k: mat(f'I3D_{k}', v, 1.0) for k, v in SPC.items()}
    brow = mat('I3D_brow_ghost', (0.95, 0.70, 0.20), 1.0); deck = mat('I3D_deck', (0.56, 0.56, 0.58), 1.0)
    root = coll('WORK_I3D_CP1_PROPELLANT', r6)
    for a in T['alternatives']:
        if a['id'] == 'T-X': continue
        c = coll(f'WORK_I3D_TANKS_{a["id"].replace("-", "")}_{a["name"].split()[0].upper()}', root); ALTS[a['id']] = c
        base = dict(track='F1 (fiction)', status='PROTOTYPE / NONCANON', maturity='M1 functional envelope', config='WF-F1-P6.0', alternative=a['id'])
        assign = [t['species'] for t in ts]
        if a['id'] == 'T-C':
            pool = {k: dict(v) for k, v in a['reallocated']['after'].items()}; assign = []
            for t in ts:
                sp = next(k for k in ('helium-3', 'hydrogen', 'deuterium') if pool[k][t['tank_class']] > 0); pool[sp][t['tank_class']] -= 1; assign.append(sp)
        dL = a['added_length_m']
        for t, sp in zip(ts, assign):
            if a['id'] == 'T-B':
                L = a['segment_vessel_length_m']; xc = x1+dL-L/2
                cyl_x(f'I3D_{a["id"]}_{t["id"]}_Segment', (xc, t['y'], t['z']), L, t['a_env'], t['a_env'], c, mats[sp],
                      dict(base, meaning=f'forward segment vessel {t["id"]} ({sp}), {L:.1f} m apex to apex, mission-modular'))
            else:
                cyl_x(f'I3D_{a["id"]}_{t["id"]}_Stretch', (x1+dL/2, t['y'], t['z']), dL, t['a_env'], t['a_env'], c, mats[sp],
                      dict(base, meaning=f'added barrel of vessel {t["id"]} ({sp}), +{dL:.1f} m'))
        if a['id'] == 'T-B':
            ring_x(f'I3D_{a["id"]}_IntermediateDeck', (x1+0.8+0.9, 0.0, 0.0), 1.8, 34.8, c, deck,
                   dict(base, meaning='intermediate thrust deck carrying the forward segment (M0: depth from the aft deck, mass OPEN)'))
        ring_x(f'I3D_{a["id"]}_BrowTranslated', (144.75+dL-1.5, 0.0, 0.0), 3.0, 45.0, c, brow,
              dict(base, maturity='M0 reservation', meaning=f'Brow shield, EYE and forward assembly translated forward by {dL:.1f} m (envelope only)'))
        label(f'{a["id"]} {a["name"]}: +{dL:.1f} m, ship {a["ship_length_m"]:.1f} m', (x1+dL/2, 0, -48), c, 2.0)
        if a['id'] != 'T-A':
            c.hide_viewport = True
            for o in c.all_objects: o.hide_render = True
    ns['cam'](root, 'CAM_I3D_FARM_SIDE', (128.0, -230.0, 0.0), (128.0, 0.0, 0.0), 50).data.type = 'ORTHO'
    bpy.data.objects['CAM_I3D_FARM_SIDE'].data.ortho_scale = 175.0
    ns['cam'](root, 'CAM_I3D_FARM_34', (230.0, -120.0, -70.0), (120.0, 0.0, 0.0), 35)


def render():
    if '--render' not in sys.argv: return
    sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.color_type = 'MATERIAL'
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900; sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 88
    sc.world = sc.world or bpy.data.worlds.new('W'); sc.world.color = (0.02, 0.02, 0.03)
    saved = {o.name: o.hide_render for o in bpy.data.objects}
    for o in bpy.data.objects:
        if o.type == 'FONT': o.hide_render = True
    for aid, c in ALTS.items():
        for k, cc in ALTS.items():
            for o in cc.all_objects:
                if o.type != 'FONT': o.hide_render = (k != aid)
        for cname in ('CAM_I3D_FARM_SIDE', 'CAM_I3D_FARM_34'):
            sc.camera = bpy.data.objects[cname]
            sc.render.filepath = str(HERE / 'results' / f'{cname.lower()}_{aid.replace("-", "").lower()}.jpg'); bpy.ops.render.render(write_still=True)
    for o in bpy.data.objects: o.hide_render = saved.get(o.name, o.hide_render)


ns['I3D_HOOK'] = hook; ns['I3D_RENDER'] = render
exec(compile(src, 'make_review6.py', 'exec'), ns)
ns['main']()
