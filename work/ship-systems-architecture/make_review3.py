"""ISSA Phase III review file: the Phase I/II review layers plus EPS-G1 unit envelopes, four district variants, the He-3 tank sight lines, the
thermal-machinery envelopes and the 550 K section research variant (NONCANON, PROTOTYPE). Production geometry is unchanged: the built ship is
appended as it is, the casing and blades are hidden (never deleted), and everything new sits in WORK_ISSA3_* collections (pink), one per
district variant and equipment family so each can be isolated in the outliner.

    /snap/bin/blender -b assets/wayfarer/WF_WAYFARER_001.blend --python work/ship-systems-architecture/make_review3.py [-- --render]
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(bpy.data.filepath).resolve().parents[2] / 'work' / 'ship-systems-architecture'
src = (HERE / 'make_review.py').read_text().rsplit('\nmain()', 1)[0]
ns = {'__file__': str(HERE / 'make_review.py'), '__name__': 'make_review'}
exec(compile(src, 'make_review.py', 'exec'), ns)          # Phase I/II helpers and layers (build(), mat, coll, put, sector_box, tube, rod, cone, label)
mat, coll, put, tube, rod, cone, label = (ns[k] for k in ('mat', 'coll', 'put', 'tube', 'rod', 'cone', 'label'))

G = json.loads((HERE / 'results' / 'phase3_eps_g1.json').read_text())
P3 = json.loads((HERE / 'results' / 'phase3.json').read_text())
BAY = G['bay']
FAM_COL = {'REACTOR': (0.9, 0.25, 0.2), 'SHIELD': (0.55, 0.55, 0.6), 'HEAT_TRANSPORT': (0.95, 0.55, 0.15), 'CONVERSION': (0.85, 0.75, 0.2),
           'ELECTRICAL': (0.25, 0.6, 0.95), 'STRUCTURE': (0.6, 0.45, 0.3), 'ACCESS': (0.3, 0.85, 0.5)}
CLS_ALPHA = {'PHYSICAL': 0.85, 'THERMAL_EXCLUSION': 0.12, 'MAINTENANCE': 0.15, 'ROBOTIC': 0.15, 'REMOVAL': 0.12, 'ATTACHMENT': 0.9, 'INTERFACE': 0.9}


def frame(x_aft, az):
    a = math.radians(az); ur = Vector((0, math.cos(a), math.sin(a))); ut = Vector((0, -math.sin(a), math.cos(a)))
    return lambda u, v, w: Vector((x_aft+u, 0, 0)) + ur*(BAY['r0']+v) + ut*w


def env_mesh(name, e, P, c, m, props):
    if e['shape'] == 'box':
        vs = [P(u, v, w) for u in e['u'] for v in sorted(e['v']) for w in sorted(e['w'])]
        fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    else:
        n = 24; vs = []; fs = []
        for u, r in zip(e['u'], e['r']):
            for k in range(n):
                t = 2*math.pi*k/n; vs.append(P(u, e['vc']+r*math.cos(t), r*math.sin(t)))
        for k in range(n):
            fs.append((k, (k+1) % n, n+(k+1) % n, n+k))
        fs.append(tuple(range(n))[::-1]); fs.append(tuple(range(n, 2*n)))
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    return put(name, me, c, m, props)


def phase3(root, cL):
    mats = {}
    def M(fam, cls):
        k = (fam, cls)
        if k not in mats:
            col = FAM_COL.get(fam, (0.8, 0.8, 0.8))
            if cls == 'THERMAL_EXCLUSION': col = (1.0, 0.3, 0.1)
            if cls in ('MAINTENANCE', 'ROBOTIC', 'REMOVAL'): col = {'MAINTENANCE': (0.3, 0.9, 0.4), 'ROBOTIC': (0.2, 0.7, 1.0), 'REMOVAL': (0.95, 0.9, 0.2)}[cls]
            mats[k] = mat(f'ISSA3_{fam}_{cls}', col, CLS_ALPHA.get(cls, 0.5))
        return mats[k]
    keys = {'C-lean 3+1 x 1.75 MWe (Phase II reference)': 'V1_CLEAN_3P1', '2+1 x 2.66 MWe (one unit per blade)': 'V2_2P1_266',
            '2 x 100 % x 5.3 MWe': 'V3_2X100', '4+1 x 1.33 MWe (modular, two per blade except one)': 'V4_4P1_133'}
    preferred = 'V2_2P1_266'
    for name, D in G['districts'].items():
        key = keys[name]; U = G['units'][name]
        dc = coll(f'WORK_ISSA3_{key}', root)
        fams = {}
        for row in D['units']:
            P = frame(row['x_aft'], row['azimuth_deg'])
            for e in U['envelopes']:
                fam = e['family'] if e['cls'] == 'PHYSICAL' or e['cls'] in ('ATTACHMENT', 'INTERFACE') else e['cls']
                if fam not in fams:
                    fams[fam] = coll(f'WORK_ISSA3_{key}_{fam}', dc)
                env_mesh(f'ISSA3_{key}_U{row["unit"]}_{e["name"][:40]}', e, P, fams[fam], M(e['family'], e['cls']),
                         dict(variant=name, unit=row['unit'], module=row['module'], azimuth_deg=row['azimuth_deg'], bus=row['bus'],
                              blade_header=row['blade_header'], envelope_class=e['cls'], family=e['family'], volume_m3=round(e['volume_m3'], 2),
                              mass_kg=round(e['mass_kg']) if e['mass_kg'] else 'n/a', status=e['status'], note=e['note'] or ''))
        label(f'{key}: {name}', (-78.0, 0, -12.0), dc, 1.2)
        if key != preferred:
            dc.hide_viewport = True
            for o in dc.all_objects:
                o.hide_render = True
    # shadow cones: reference 12.5 deg and the ~28 deg needed to cover the outer-ring He-3 tanks; tank sight lines
    cs = coll('WORK_ISSA3_SHADOW_AND_TANK_SIGHTLINES', root)
    w = P3['shielding']['wide_cone']
    cone('ISSA3_Shadow_Cone_12_5deg', (-84.0, 0, 2.9), 60.0, 12.5, cs, mat('ISSA3_cone', (0.95, 0.9, 0.3), 0.06), dict(half_angle_deg=12.5))
    cone('ISSA3_Shadow_Cone_needed', (-84.0, 0, 2.9), 60.0, w['half_angle_deg'], cs, mat('ISSA3_cone2', (1.0, 0.35, 0.2), 0.05),
         dict(half_angle_deg=round(w['half_angle_deg'], 1), shadow_t=round(w['shadow_t'], 1), fits_bay=w['fits_bay']))
    mt = mat('ISSA3_sight', (1.0, 0.2, 0.2)); mt2 = mat('ISSA3_sight_ok', (0.3, 0.9, 0.4))
    for t in P3['shielding']['tanks']:
        a = math.radians(0)
        rod(f'ISSA3_Sight_{t["tank"]}', (-84.0, 0, 2.9), (-35.5, 0, t['R_m']), 0.08, cs, mt2 if t['in_shadow'] else mt,
            dict(tank=t['tank'], species=t['species'], off_axis_deg=round(t['off_axis_deg'], 1), in_shadow=t['in_shadow'],
                 bare_deposit_W=round(t['bare_deposit_W'], 1)))
    label('He-3 tanks outside the 12.5 deg shadow (red lines)', (-60, 0, 30), cs, 1.6)
    # thermal machinery envelopes in D2 (aft engineering bay) and the 550 K section research variant on the hot blades
    ctm = coll('WORK_ISSA3_THERMAL_MACHINERY', root)
    x = -130.0
    for it in G['thermal_machinery']:
        L = max(1.0, it['volume_m3']/(2.8*3.2))
        if L > 60: L = 60.0
        ns['sector_box'](f'ISSA3_TM_{it["name"][:40]}', x, x+L, 150.0 if 'L1' in it['name'] else 270.0, 1.5, 4.3, 3.0, ctm,
                         mat(f'ISSA3_TM_{it["family"]}', {'HEAT_PUMP': (0.9, 0.3, 0.6), 'L1_CONVERSION': (0.9, 0.2, 0.2), 'THERMAL_BUFFER': (1.0, 0.6, 0.1),
                                                          'PUMPS': (0.4, 0.6, 0.95)}[it['family']], 0.5),
                         dict(capacity_MW=round(it['capacity_W']/1e6, 2), volume_m3=round(it['volume_m3'], 1), mass_kg=round(it['mass_kg']), status=it['status'],
                              district=it['district']))
        x += L+1.0
        if x > -92: x = -130.0
    c550 = coll('WORK_ISSA3_RADIATOR_VARIANT_550K', root)
    S = P3['convergence']['section550']['N2']; L = S['length_m'][1]
    for deg in (90, 210, 330):
        ns['sector_box'](f'ISSA3_550K_Section_{deg}', 48.9-L, 48.9, deg, 6.5, 37.0, 0.4, c550, mat('ISSA3_550', (0.95, 0.75, 0.2), 0.45),
                         dict(meaning='research variant (DR-03): forward end of the hot blade run at 550 K for L2 in burns', length_m=round(L, 1),
                              area_m2=round(S['area_m2'][1]), hot_allowance_GW=round(S['hot_allowance_W'][1]/1e9, 2)))
    label(f'550 K section variant ({L:.0f} m, thermal option F)', (48.9-L/2, 0, 42), c550, 1.8)
    c550.hide_viewport = True
    for o in c550.all_objects:
        o.hide_render = True


def cam(root, name, loc, target, lens=24):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_end = 3000
    o = bpy.data.objects.new(name, cd); root.objects.link(o); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def main():
    ns['build']()
    root = bpy.data.collections['WORK_SHIP_SYSTEMS_ARCHITECTURE']; cL = bpy.data.collections['WORK_ISSA_90_LABELS']
    for c in root.children:      # Phase II layouts and Phase I candidate layers stay, hidden, so Phase III reads first
        if c.name.startswith('WORK_ISSA_6') or c.name in ('WORK_ISSA_20_POWER_CANDIDATES', 'WORK_ISSA_30_MACHINERY_AND_STORES'):
            c.hide_viewport = True
            for o in c.all_objects:
                o.hide_render = True
    r3 = bpy.data.collections.new('WORK_ISSA3_PHASE3'); root.children.link(r3); r3.color_tag = ns['PINK']
    ns['LBLM'] = ns.get('LBLM')
    phase3(r3, cL)
    c1 = cam(r3, 'CAM_ISSA3_DISTRICT', (-58.0, -14.0, -12.0), (-80.0, 0.0, 0.5), 24)
    cam(r3, 'CAM_ISSA3_UNIT', (-73.0, -9.0, 11.0), (-84.5, 0.0, 3.4), 26)
    cam(r3, 'CAM_ISSA3_TANK_SIGHTLINES', (-55.0, -150.0, 12.0), (-55.0, 0.0, 12.0), 30)
    bpy.context.scene.camera = c1
    if '--render' in sys.argv:
        sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.color_type = 'MATERIAL'
        sc.render.resolution_x, sc.render.resolution_y = 1600, 900; sc.render.film_transparent = False
        sc.world = sc.world or bpy.data.worlds.new('W'); sc.world.color = (0.02, 0.02, 0.03)
        keep = {'CAM_ISSA3_DISTRICT': ('ISSA3_',), 'CAM_ISSA3_UNIT': ('ISSA3_V2',), 'CAM_ISSA3_TANK_SIGHTLINES': ('ISSA3_', 'Fuel_Tank_', 'ISSA_District')}
        for cname in ('CAM_ISSA3_DISTRICT', 'CAM_ISSA3_UNIT', 'CAM_ISSA3_TANK_SIGHTLINES'):
            sc.camera = bpy.data.objects[cname]
            saved = {o.name: o.hide_render for o in bpy.data.objects}
            for o in bpy.data.objects:            # isolate the Phase III layer for the render only; the saved file keeps every layer
                if o.type in ('MESH', 'CURVE', 'FONT') and not o.name.startswith(keep[cname]):
                    o.hide_render = True
                if o.type == 'FONT':
                    o.hide_render = True
            sc.render.filepath = str(HERE / 'results' / f'{cname.lower()}.png'); bpy.ops.render.render(write_still=True)
            for o in bpy.data.objects:
                o.hide_render = saved[o.name]
        sc.camera = c1
    try:
        bpy.ops.file.pack_libraries()
    except Exception as e:  # noqa: BLE001
        print('pack_libraries failed:', e)
    bpy.ops.file.pack_all()
    out = HERE / 'REVIEW_ISSA_PHASE3.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True, relative_remap=False, copy=True)
    print('SAVED', out, out.stat().st_size)


main()
