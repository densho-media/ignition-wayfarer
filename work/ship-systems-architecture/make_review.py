"""ISSA review file: the built ship with the study's districts, candidate envelopes, utility routes and exclusion zones (NONCANON).

Opens assets/wayfarer/WF_WAYFARER_001.blend, hides the service casing and the radiator blades (Assembly_HULL, Assembly_THERMAL: hidden, not deleted) so the interior shows, adds
WORK_SHIP_SYSTEMS_ARCHITECTURE (pink) with one sub-collection per layer, frames two cameras, packs the linked libraries and saves
work/ship-systems-architecture/REVIEW_SHIP_SYSTEMS_ARCHITECTURE.blend. Every envelope is a PROTOTYPE candidate from this study, not a
selection; positions come from the built model (survey_blender.py) and the dry-store module stations.

    /snap/bin/blender -b assets/wayfarer/WF_WAYFARER_001.blend --python work/ship-systems-architecture/make_review.py [-- --render]
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(bpy.data.filepath).resolve().parents[2] / 'work' / 'ship-systems-architecture'
PINK = 'COLOR_06'


def mat(name, rgba, alpha=1.0):
    m = bpy.data.materials.new(name); m.diffuse_color = (*rgba, alpha)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    if b:
        b.inputs['Base Color'].default_value = (*rgba, 1.0); b.inputs['Alpha'].default_value = alpha
        b.inputs['Emission Color'].default_value = (*rgba, 1.0); b.inputs['Emission Strength'].default_value = 0.6
    m.blend_method = 'BLEND' if alpha < 1 else 'OPAQUE'
    return m


def coll(name, parent):
    c = bpy.data.collections.new(name); parent.children.link(c); c.color_tag = PINK
    return c


def put(name, me, c, m, props):
    o = bpy.data.objects.new(name, me); c.objects.link(o)
    me.materials.append(m)
    for k, v in props.items():
        o[k] = v
    o['canon_status'] = 'PROTOTYPE (ISSA study candidate, not a selection)'
    return o


def sector_box(name, x0, x1, deg, r0, r1, width, c, m, props):
    """A box between radii r0..r1 centred on azimuth deg (+Y = 0 deg, +Z = 90 deg), width tangential."""
    a = math.radians(deg); ur = Vector((0, math.cos(a), math.sin(a))); ut = Vector((0, -math.sin(a), math.cos(a)))
    vs = []
    for x in (x0, x1):
        for r in (r0, r1):
            for t in (-width/2, width/2):
                vs.append(Vector((x, 0, 0)) + ur*r + ut*t)
    fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    return put(name, me, c, m, props)


def tube(name, x0, x1, r_in, r_out, c, m, props, n=64):
    vs, fs = [], []
    for x in (x0, x1):
        for r in (r_out, r_in):
            for i in range(n):
                t = 2*math.pi*i/n; vs.append((x, r*math.cos(t), r*math.sin(t)))
    def q(a, b):
        for i in range(n):
            fs.append((a+i, a+(i+1) % n, b+(i+1) % n, b+i))
    q(0, 2*n); q(n, 3*n); q(0, n); q(2*n, 3*n)
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    return put(name, me, c, m, props)


def rod(name, p, q, rad, c, m, props, n=10):
    p, q = Vector(p), Vector(q); d = (q-p).normalized()
    t = d.orthogonal().normalized(); u = d.cross(t)
    vs = [tuple(e + rad*(math.cos(2*math.pi*i/n)*t + math.sin(2*math.pi*i/n)*u)) for e in (p, q) for i in range(n)]
    fs = [(i, (i+1) % n, n+(i+1) % n, n+i) for i in range(n)]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    return put(name, me, c, m, props)


def cone(name, apex, length, half_deg, c, m, props, n=64):
    R = length*math.tan(math.radians(half_deg)); ax = Vector(apex)
    vs = [tuple(ax)] + [(ax.x+length, R*math.cos(2*math.pi*i/n), R*math.sin(2*math.pi*i/n)) for i in range(n)]
    fs = [(0, 1+i, 1+(i+1) % n) for i in range(n)]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    return put(name, me, c, m, props)


def sphere(name, ctr, r, c, m, props):
    me = bpy.data.meshes.new(name)
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=r); bm.to_mesh(me); bm.free()
    o = put(name, me, c, m, props); o.location = ctr
    return o


def label(text, loc, c, size=2.2):
    cu = bpy.data.curves.new('L_'+text[:40], 'FONT'); cu.body = text; cu.size = size; cu.align_x = 'CENTER'
    o = bpy.data.objects.new('LBL '+text[:50], cu); c.objects.link(o); o.location = loc; o.rotation_euler = (math.radians(180), 0, 0)  # faces -Z: read from below, between blades 210 and 330
    o.data.materials.append(LBLM)
    return o


def build():
    global LBLM
    sc = bpy.context.scene
    for o in bpy.data.objects:
        if o.name in ('Assembly_HULL', 'Assembly_THERMAL'):
            o.hide_viewport = True; o.hide_render = True
            o['issa_review'] = 'hidden for the review so the casing interior shows (unhide in the outliner); never deleted'
    root = bpy.data.collections.new('WORK_SHIP_SYSTEMS_ARCHITECTURE'); sc.collection.children.link(root); root.color_tag = PINK
    LBLM = mat('ISSA_Label', (0.95, 0.95, 0.95))
    cD = coll('WORK_ISSA_10_DISTRICTS', root); cE = coll('WORK_ISSA_20_POWER_CANDIDATES', root); cM = coll('WORK_ISSA_30_MACHINERY_AND_STORES', root)
    cU = coll('WORK_ISSA_40_UTILITY_ROUTES', root); cX = coll('WORK_ISSA_50_EXCLUSION_ZONES', root); cL = coll('WORK_ISSA_90_LABELS', root)
    dist = [('D1 drive', -136.75, -133.25, (0.75, 0.2, 0.2)), ('D2 aft engineering', -133.25, -89.5, (0.85, 0.45, 0.2)),
            ('D3 mid-body dry store', -89.5, 21.0, (0.6, 0.45, 0.3)), ('D4 fwd body', 21.0, 48.9, (0.55, 0.55, 0.4)),
            ('D5 RAD-ZONE casing', 48.9, 93.4, (0.9, 0.6, 0.2)), ('D6 rotor bay', 93.4, 108.8, (0.3, 0.6, 0.35)),
            ('D7 forward service', 108.8, 141.75, (0.3, 0.5, 0.85))]
    for i, (n, a, b, col) in enumerate(dist):
        tube(f'ISSA_District_{n.split()[0]}', a+0.05, b-0.05, 6.15, 6.35, cD, mat(f'ISSA_D{i}', col, 0.18), dict(district=n, x_range=f'{a}..{b}'))
        label(n, ((a+b)/2, 9.0 + (i % 2)*3.0, -8.0), cL, 2.0)
    # Burn machinery in the aft dry-store modules M1-M2, all three sectors (EPS-01 drive generators, TMS-04 heat pumps, TMS-01 pumps)
    mB = mat('ISSA_BurnMachinery', (0.85, 0.25, 0.15), 0.55)
    for deg in (90, 210, 330):
        sector_box(f'ISSA_Burn_Machinery_{deg}', -89.35, -67.15, deg, 1.5, 4.3, 3.2, cM, mB,
                   dict(systems='EPS-01, TMS-04, TMS-01', envelope='equipment + maintenance + removal, 4 dry-store modules per sector',
                        basis='300-900 m3 + 200-600 m3 needed (systems.toml); 3 x 22 m x 2.8 m x 3.2 m ~ 590 m3 here'))
    label('Burn machinery (EPS-01, TMS-04)', (-78, -9, -8), cL, 1.6)
    # Ship-service plants A and B: separate modules, separate sectors, a CMG frame between them
    mA = mat('ISSA_PlantA', (0.2, 0.55, 0.95), 0.7); mBp = mat('ISSA_PlantB', (0.55, 0.3, 0.9), 0.7)
    sector_box('ISSA_EPS02_Plant_A', -65.35, -55.15, 90, 1.5, 4.3, 3.2, cE, mA, dict(system='EPS-02A', candidate='L2 mid-body aft modules (M3, 90 deg)'))
    sector_box('ISSA_EPS02_Plant_B', -51.35, -41.15, 210, 1.5, 4.3, 3.2, cE, mBp, dict(system='EPS-02B', candidate='L2 (M4, 210 deg)'))
    for nm, x, m_ in (('A', -60.25, mA), ('B', -46.25, mBp)):
        cone(f'ISSA_Shadow_Cone_{nm}', (x, 0, 0), 145.0 - x, 12.5, cX, mat(f'ISSA_Shadow_{nm}', (0.9, 0.9, 0.3), 0.07),
             dict(meaning='shadow-shield cone that must cover rings (r 30) and Brow (r 45) as seen from the plant', half_angle_deg=12.5))
    label('Plant A', (-60, 7, -8), cL, 1.5); label('Plant B', (-46, -7, -8), cL, 1.5)
    # Alternative candidate positions (rejected / secondary), shown as wireframe-like thin boxes
    mR = mat('ISSA_Rejected', (0.9, 0.15, 0.15), 0.35)
    sector_box('ISSA_EPS02_Candidate_L3_RADZONE_REJECTED', 60, 72, 90, 1.5, 4.3, 3.2, cE, mR,
               dict(candidate='L3 RAD-ZONE casing', verdict='REJECTED for a reactor: 25-45 m from ring A; good for distribution and cold-side machinery'))
    sector_box('ISSA_EPS02_Candidate_L1_AFT_BAY', -103.8, -100.8, 270, 1.3, 3.6, 2.6, cE, mat('ISSA_L1', (0.2, 0.75, 0.75), 0.6),
               dict(candidate='L1 aft engineering bay beside Brayton A/B', verdict='full (FPS feed, fabrication); 16-75 m3 usable'))
    # Survival power E near the refuge
    sector_box('ISSA_EPS05_Survival_Source_Candidate', 112.6, 114.4, 240, 1.4, 2.6, 1.4, cE, mat('ISSA_Surv', (0.3, 0.8, 0.35), 0.8),
               dict(system='EPS-05', candidate='RPS / small Stirling core beside the survival packs (kWe class)'))
    # Stores that want to be near the crew: food, spares, heavy workshop in the forward modules / RAD-ZONE casing
    mS = mat('ISSA_Stores', (0.8, 0.7, 0.3), 0.45)
    for deg in (90, 210, 330):
        sector_box(f'ISSA_Stores_M8_M9_{deg}', -1.35, 20.85, deg, 1.5, 4.3, 3.2, cM, mS,
                   dict(systems='LOG-01 food, MRO-02 spares', basis='110-160 m3 food + 60-200 m3 spares'))
    sector_box('ISSA_Heavy_Workshop_Candidate', 52.0, 64.0, 330, 1.5, 4.3, 3.2, cM, mat('ISSA_Shop', (0.75, 0.75, 0.2), 0.5),
               dict(system='MRO-01', candidate='stationary heavy workshop in the RAD-ZONE casing (usable 309 m3)'))
    sector_box('ISSA_Heat_Buffer_Candidate', 74.0, 86.0, 210, 1.5, 4.3, 3.2, cM, mat('ISSA_Buffer', (0.95, 0.5, 0.1), 0.5),
               dict(system='TMS-06', candidate='Heat Debt buffer at the WARM section roots'))
    label('Food / spares (M8-M9)', (10, -9, -8), cL, 1.5); label('Workshop, heat buffer (D5)', (70, -9, -8), cL, 1.5)
    # Utility routes: A, B and E on three different keel-lane walls; hot/warm trunks at the blade roots are existing geometry
    for nm, deg, col in (('A', 12.0, (0.95, 0.85, 0.1)), ('B', 132.0, (0.1, 0.85, 0.95)), ('E', 252.0, (0.3, 0.95, 0.3))):
        a = math.radians(deg); y, z = 5.0*math.cos(a), 5.0*math.sin(a)
        rod(f'ISSA_Bus_{nm}_Trunk', (-125, y, z), (108, y, z), 0.18, cU, mat(f'ISSA_Bus_{nm}', col),
            dict(route=f'EPS-06/07 bus {nm} + CDH data {nm}', rule='never in the same chase or keel lane as another bus'))
    label('Bus A / B / E trunks on three keel lanes', (-10, 13, -8), cL, 1.5)
    # Exclusion zones
    sphere('ISSA_Drive_Magnetic_Exclusion', (-138.0, 0, 0), 14.0, cX, mat('ISSA_Mag', (0.9, 0.2, 0.6), 0.08),
           dict(meaning='illustrative magnetic/neutron exclusion radius round the drive; real radius OPEN (EPS-09)'))
    tube('ISSA_EVA_Keepout_Plants_Running', -70.0, -36.0, 6.4, 7.6, cX, mat('ISSA_EVA', (1.0, 0.1, 0.1), 0.15),
         dict(meaning='EVA keep-out on the hull outside the shadow cones while plants A/B run (EVA there only with the plant at decay power)'))
    phase2(root, cL)
    # Cameras
    def cam(name, loc, target, lens=24):
        cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_end = 3000
        o = bpy.data.objects.new(name, cd); root.objects.link(o); o.location = loc
        o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        return o
    c1 = cam('CAM_ISSA_WHOLE_SHIP', (-10, -150, -140), (-5, 0, 0), 26)
    cam('CAM_ISSA_POWER_DISTRICT', (-30, -30, -32), (-62, 0, 0), 24)
    sc.camera = c1
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == 'VIEW_3D':
                sp = area.spaces[0]; sp.region_3d.view_perspective = 'CAMERA'; sp.shading.type = 'SOLID'
                sp.shading.color_type = 'MATERIAL'; sp.clip_end = 3000; sp.overlay.show_extras = False


def phase2(root, cL):
    """ISSA Phase II candidate layouts (results/phase2_placement.json): one hidden collection per layout, the preferred one visible."""
    import json
    P = json.loads((HERE / 'results' / 'phase2_placement.json').read_text())
    cols = {'L-A': (0.2, 0.55, 0.95), 'L-B': (0.95, 0.35, 0.2), 'L-C': (0.6, 0.4, 0.95), 'L-E': (0.2, 0.85, 0.6), 'L-D': (0.9, 0.15, 0.15)}
    preferred = 'L-E'
    for name, L in P['layouts'].items():
        key = name.split()[0]
        c = coll(f'WORK_ISSA_6{list(cols).index(key)}_LAYOUT_{key.replace("-", "")}', root)
        m = mat(f'ISSA2_{key}', cols[key], 0.7); mc = mat(f'ISSA2_{key}_cone', (0.95, 0.9, 0.3), 0.06)
        mb = mat(f'ISSA2_{key}_band', (0.95, 0.6, 0.1), 0.35)
        for k, (x, deg) in enumerate(zip(L['x'], L['sectors'])):
            sector_box(f'ISSA2_{key}_Unit_{k+1}', x-2.6, x+2.6, deg, 1.5, 4.3, 3.0, c, m,
                       dict(layout=name, unit=k+1, envelope_m3=round(P['envelopes']['C-lean']['unit_total_m3'][1]),
                            shield_kg=round(L['per_unit_shield_kg'][1]), note=L['note']))
            tube(f'ISSA2_{key}_ScatterBand_{k+1}', x-1.0, x+1.0, 1.0, 1.0+L['side_efolds'][1]*P['dose_model']['lam_m'][1]*0.5, c, mb,
                 dict(meaning='blade-facing side shield against single scatter (schematic thickness, not a design)'))
        x0 = min(L['x']); cone(f'ISSA2_{key}_ShadowCone', (x0, 0, 0), 145.0-x0, L['cone_half_angle_needed_deg'], c, mc,
                               dict(half_angle_deg=round(L['cone_half_angle_needed_deg'], 1)))
        tube(f'ISSA2_{key}_CrewExclusion', min(L['x'])-6.0, max(L['x'])+6.0, 4.4, 6.3, c, mat(f'ISSA2_{key}_excl', (1.0, 0.1, 0.1), 0.12),
             dict(meaning='no crew or EVA in line of sight of a running unit (21-24 e-folds needed at 2-4 m); drones only'))
        label(f'{key}: {name[4:40]}', ((min(L['x'])+max(L['x']))/2, 0, -14.0), c, 1.4)
        if key != preferred:
            c.hide_viewport = True
            for o in c.objects:
                o.hide_render = True


def main():
    build()
    if '--render' in sys.argv:
        sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.color_type = 'MATERIAL'
        sc.render.resolution_x, sc.render.resolution_y = 1800, 900; sc.render.film_transparent = False
        sc.world = sc.world or bpy.data.worlds.new('W'); sc.world.color = (0.02, 0.02, 0.03)
        for cname in ('CAM_ISSA_WHOLE_SHIP', 'CAM_ISSA_POWER_DISTRICT'):
            sc.camera = bpy.data.objects[cname]
            sc.render.filepath = str(HERE / 'results' / f'{cname.lower()}.png'); bpy.ops.render.render(write_still=True)
        sc.camera = bpy.data.objects['CAM_ISSA_WHOLE_SHIP']
    try:
        bpy.ops.file.pack_libraries()
    except Exception as e:  # noqa: BLE001
        print('pack_libraries failed:', e)
    bpy.ops.file.pack_all()
    out = HERE / 'REVIEW_SHIP_SYSTEMS_ARCHITECTURE.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True, relative_remap=False, copy=True)
    print('SAVED', out, out.stat().st_size)


main()
