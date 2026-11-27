"""ISSA Phase IV review file: the Phase I-III review layers (hidden) plus the Phase IV research geometry (NONCANON, PROTOTYPE): the bulkhead
baffle (G3), the 700 K L2 section on the hot-blade forward end (N2-R4a) and as a forward extension (N2-R4b, hidden), sight lines from WARM
to the other blades' hot faces, the tank-facing shield bands of the three-unit district and the H5 hot-transport zones. Production geometry
is appended unchanged; everything new is in WORK_ISSA4_* collections (pink).

    /snap/bin/blender -b assets/wayfarer/WF_WAYFARER_001.blend --python work/ship-systems-architecture/make_review4.py [-- --render]
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(bpy.data.filepath).resolve().parents[2] / 'work' / 'ship-systems-architecture'
src = (HERE / 'make_review3.py').read_text().rsplit('\nmain()', 1)[0]
ns = {'__file__': str(HERE / 'make_review3.py'), '__name__': 'make_review3'}
exec(compile(src, 'make_review3.py', 'exec'), ns)
mn = ns['ns']                                   # Phase I/II helper namespace inside make_review3
mat, coll, put, tube, rod, label, cam = (mn['mat'], mn['coll'], mn['put'], mn['tube'], mn['rod'], mn['label'], ns['cam'])
P4 = json.loads((HERE / 'results' / 'phase4.json').read_text())
G = ns['G']
AZ = (90.0, 210.0, 330.0); BULK = 50.4; R_IN, R_OUT = 6.1, 36.1


def sector(name, x0, x1, az, r0, r1, t, c, m, props):
    return mn['sector_box'](name, x0, x1, az, r0, r1, t, c, m, props)


def band(name, c0, r, th0, th1, c, m, props, n=48):
    vs = []
    for th in (th0, th1):
        a = math.radians(th)
        for k in range(n):
            p = 2*math.pi*k/n
            vs.append(tuple(Vector(c0) + r*Vector((math.cos(a), math.sin(a)*math.cos(p), math.sin(a)*math.sin(p)))))
    fs = [(k, (k+1) % n, n+(k+1) % n, n+k) for k in range(n)]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    return put(name, me, c, m, props)


def phase4(root):
    cv = {c['name'][:6]: c for c in P4['convergence']['candidates']}
    Ta = cv['N2-R4a']; L = Ta['length_m'][1]
    bf = P4['thermal']['baffle']
    mb = mat('ISSA4_baffle', (0.35, 0.85, 0.9), 0.55); m7 = mat('ISSA4_700K', (0.95, 0.25, 0.55), 0.75)
    # R4a: 700 K section on the hot-blade forward end, baffle aft of it
    ca = coll('WORK_ISSA4_N2_R4A_700K_ON_HOT_END', root)
    for az in AZ:
        sector(f'ISSA4_R4a_700K_{az:.0f}', BULK-L, BULK, az, R_IN+0.4, R_OUT, 0.45, ca, m7,
               dict(meaning='research variant: forward end of the hot blade run at 700 K for L2 in burns (N2-R4a)', length_m=round(L, 1),
                    hot_capacity_GW=round(Ta['length_m'][1]*0.0889, 2), status='PROTOTYPE'))
    tube('ISSA4_R4a_Bulkhead_Relocated', BULK-L-0.3, BULK-L, 6.1, 37.0, ca, mb, dict(meaning='the production graded bulkhead (3 V-groove layers) '
         'moved aft of the 700 K section so the section stays shadowed from the hot blades; the production bulkhead itself is unchanged in this file',
         R_m=37.0, relocation_t_nominal=round(bf['mass_t'][1], 1)))
    label(f'N2-R4a: 700 K section {L:.0f} m, bulkhead moved aft (silhouette kept)', (BULK-L/2, 0, 44), ca, 1.8)
    # sight lines: the Phase III 550 K position (aft of the production bulkhead) to hot faces of the other two blades (red)
    cs = coll('WORK_ISSA4_SIGHTLINES_550K_TO_HOT', root)
    mr = mat('ISSA4_sight_hot', (1.0, 0.2, 0.15))
    a0 = math.radians(90.0)
    for k, (xw, rw, xh, rh, az) in enumerate([(45, 20, 0, 25, 210), (40, 30, -20, 15, 330), (35, 12, 10, 30, 210), (30, 25, -60, 20, 330), (42, 34, 15, 34, 330)]):
        p = (xw, rw*math.cos(a0), rw*math.sin(a0)); a = math.radians(az); q = (xh, rh*math.cos(a), rh*math.sin(a))
        rod(f'ISSA4_Sight_{k}', p, q, 0.35, cs, mr, dict(meaning='a line of sight from the Phase III 550 K position to an 1800 K face of another blade'))
    vfw = next(r for r in P4['thermal']['view_factors'] if '29 m' in r['surface'])
    label(f'Phase III 550 K section sees the hot blades: F = {vfw["F_hot"]:.3f}', (40, 0, -40), cs, 1.6)
    cs.hide_viewport = True
    for o in cs.all_objects: o.hide_render = True
    # He-3 tank sight lines from the three units: inside the 12.5 deg shadow cone (green), ~195 m (Phase III had them at 54 m, outside)
    ct = coll('WORK_ISSA4_TANK_SIGHTLINES', root)
    mg = mat('ISSA4_tank_ok', (0.3, 0.95, 0.45))
    for g in P4['district']['geometry']:
        u = next(r for r in G['districts']['2+1 x 2.66 MWe (one unit per blade)']['units'] if r['unit'] == g['unit'])
        a = math.radians(u['azimuth_deg']); p = (u['x_aft']+5.5, 2.9*math.cos(a), 2.9*math.sin(a))
        import sys as _s; _s.path.insert(0, str(HERE.parents[1] / 'src' / 'wayfarer'))
        import spec as _sp, fuel_storage as _fs
        tk = next(x for x in _fs.tanks(_sp.load()[0]) if x['name'] == g['tank'])
        rod(f'ISSA4_TankSight_U{g["unit"]}_{g["tank"]}', p, (tk['x0'], tk['y'], tk['z']), 0.15, ct, mg,
            dict(unit=g['unit'], tank=g['tank'], d_m=round(g['d_m'], 1), off_axis_deg=round(g['off_axis_deg'], 1), in_shadow_cone=g['in_cone']))
    label('He-3 tanks: ~195 m, inside the shadow cone', (10, 0, -20), ct, 1.6)
    # H5 hot-transport zones: six feeders per blade along the root (schematic)
    ch = coll('WORK_ISSA4_H5_HOT_TRANSPORT', root)
    mh = mat('ISSA4_h5', (1.0, 0.45, 0.1), 0.9)
    for az in AZ:
        a = math.radians(az)
        for z in range(6):
            x1 = -111.6+(z+1)*(BULK-L+111.6)/6; off = 0.35*(z-2.5)
            p = (-118.0, 6.5*math.cos(a)-off*math.sin(a), 6.5*math.sin(a)+off*math.cos(a)); q = (x1, p[1], p[2])
            rod(f'ISSA4_H5_{az:.0f}_zone{z+1}', p, q, 0.18, ch, mh, dict(meaning='H5 independent pumped zone feeder (schematic)', zone=z+1))
    ch.hide_viewport = True
    for o in ch.all_objects: o.hide_render = True


def main():
    mn['build']()
    th = bpy.data.objects.get('Assembly_THERMAL')
    if th:                          # Phase IV is a radiator review: the blades stay visible (the casing stays hidden as in Phases I-III)
        th.hide_viewport = False; th.hide_render = False; th['issa_review'] = 'visible in the Phase IV review (radiator study)'
    root = bpy.data.collections['WORK_SHIP_SYSTEMS_ARCHITECTURE']; cL = bpy.data.collections['WORK_ISSA_90_LABELS']
    for c in root.children:
        if c.name.startswith('WORK_ISSA_6') or c.name in ('WORK_ISSA_20_POWER_CANDIDATES', 'WORK_ISSA_30_MACHINERY_AND_STORES'):
            c.hide_viewport = True
            for o in c.all_objects: o.hide_render = True
    r3 = bpy.data.collections.new('WORK_ISSA3_PHASE3'); root.children.link(r3); r3.color_tag = mn['PINK']
    ns['phase3'](r3, cL)
    for c in r3.children:          # Phase III kept for the record; only its preferred district stays visible
        if not c.name.startswith('WORK_ISSA3_V2'):
            c.hide_viewport = True
            for o in c.all_objects: o.hide_render = True
    r4 = bpy.data.collections.new('WORK_ISSA4_PHASE4'); root.children.link(r4); r4.color_tag = mn['PINK']
    phase4(r4)
    c1 = cam(r4, 'CAM_ISSA4_BAFFLE', (175.0, -120.0, -95.0), (5.0, 0.0, 0.0), 30)
    cam(r4, 'CAM_ISSA4_SIGHTLINES', (20.0, -330.0, 40.0), (20.0, 0.0, 0.0), 30)
    bpy.context.scene.camera = c1
    if '--render' in sys.argv:
        sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.color_type = 'MATERIAL'
        sc.render.resolution_x, sc.render.resolution_y = 1600, 900; sc.render.film_transparent = False
        sc.world = sc.world or bpy.data.worlds.new('W'); sc.world.color = (0.02, 0.02, 0.03)
        for cname in ('CAM_ISSA4_BAFFLE', 'CAM_ISSA4_SIGHTLINES'):
            sc.camera = bpy.data.objects[cname]
            saved = {o.name: o.hide_render for o in bpy.data.objects}
            study = set(root.all_objects) - set(r4.all_objects)
            for o in bpy.data.objects:     # render isolation only: earlier ISSA layers and labels off; the saved file keeps them
                if o.type == 'FONT' or o in study:
                    o.hide_render = True
            sc.render.filepath = str(HERE / 'results' / f'{cname.lower()}.png'); bpy.ops.render.render(write_still=True)
            for o in bpy.data.objects: o.hide_render = saved[o.name]
        sc.camera = c1
    try:
        bpy.ops.file.pack_libraries()
    except Exception as e:  # noqa: BLE001
        print('pack_libraries failed:', e)
    bpy.ops.file.pack_all()
    out = HERE / 'REVIEW_ISSA_PHASE4.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True, relative_remap=False, copy=True)
    print('SAVED', out, out.stat().st_size)


main()
