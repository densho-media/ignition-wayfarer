"""ISSA Phase V review file: Phases I-IV layers (hidden where superseded) plus the Phase V research geometry (NONCANON, PROTOTYPE), all
parametric from results/phase5.json: R5-A 750 K cross-strapped L2 sections with the relocated bulkhead, the R5-C bulkhead emitter (hidden),
H6a trunk pairs, section headers and isolation valves, the restart packs at the district, seven ECLSS-G1 units, LOG-G1 containers, service
and removal routes, and the OpenMC 3-D source cone. Checks: bounding-box collisions of every new object with production meshes, and the
OpenMC CSG frame against the generated tank objects (results/phase5_review_checks.json).

    /snap/bin/blender -b assets/wayfarer/WF_WAYFARER_001.blend --python work/ship-systems-architecture/make_review5.py [-- --render]
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(bpy.data.filepath).resolve().parents[2] / 'work' / 'ship-systems-architecture'
src = (HERE / 'make_review4.py').read_text().rsplit('\nmain()', 1)[0]
ns4 = {'__file__': str(HERE / 'make_review4.py'), '__name__': 'make_review4'}
exec(compile(src, 'make_review4.py', 'exec'), ns4)
mn = ns4['mn']; ns3 = ns4['ns']
mat, coll, put, tube, rod, label, cam = (mn['mat'], mn['coll'], mn['put'], mn['tube'], mn['rod'], mn['label'], ns3['cam'])
P5 = json.loads((HERE / 'results' / 'phase5.json').read_text())
AZ = (90.0, 210.0, 330.0); BULK = 50.4; R_IN, R_OUT = 6.1, 36.1
sys.path.insert(0, str(HERE.parents[1] / 'src' / 'wayfarer'))
import spec as _sp  # noqa: E402
import fuel_storage as _fs  # noqa: E402
import habitat_ring as _hr  # noqa: E402
S = _sp.load()[0]
NEW = []


def box(name, c, d, col, m, props):
    x, y, z = c; a, b, h = (v/2 for v in d)
    vs = [(x+i*a, y+j*b, z+k*h) for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)]
    fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    o = put(name, me, col, m, props); NEW.append(o); return o


def track(o):
    NEW.append(o); return o


def phase5(root):
    Rd = P5['radiators']; H = P5['transport']['topologies']['H6a']
    L = Rd['l2_750']['cross']['length_m']
    m75 = mat('ISSA5_750K', (0.95, 0.35, 0.55), 0.8); mb = mat('ISSA5_bulkhead', (0.35, 0.85, 0.9), 0.55)
    ca = coll('WORK_ISSA5_R5A_750K_CROSS_STRAPPED', root)
    for az in AZ:
        track(ns4['sector'](f'ISSA5_R5A_750K_{az:.0f}', BULK-L, BULK, az, R_IN+0.4, R_OUT, 0.45, ca, m75,
                            dict(meaning='R5-A: 750 K L2 section, dual headers from two neighbouring units (cross-strapped)', length_m=round(L, 1),
                                 config=P5['config_id'], status='PROTOTYPE')))
    track(tube('ISSA5_R5A_Bulkhead_Relocated', BULK-L-0.3, BULK-L, 6.1, 37.0, ca, mb, dict(meaning='production graded bulkhead moved aft of the '
               'R5-A section (production bulkhead unchanged in this file)', station_x=round(BULK-L, 2))))
    label(f'R5-A: 750 K cross-strapped L2 sections {L:.1f} m; 20 % HOT rule kept', (BULK-L/2, 0, 44), ca, 1.8)
    # R5-C emitter (rejected: tank IR) hidden
    cc = coll('WORK_ISSA5_R5C_BULKHEAD_EMITTER_REJECTED', root)
    track(tube('ISSA5_R5C_Emitter', 50.6, 51.0, 6.1, 37.0, cc, mat('ISSA5_r5c', (1.0, 0.5, 0.2), 0.5),
               dict(meaning='R5-C forward-face L2 emitter: rejected, irradiates the He-3 tank zone', status='REJECTED')))
    cc.hide_viewport = True
    for o in cc.all_objects: o.hide_render = True
    # H6a: two trunk pairs per blade from the drive heat exchanger to the root, six isolatable sections with valves
    ch = coll('WORK_ISSA5_H6A_HOT_NETWORK', root)
    mt = mat('ISSA5_trunk', (1.0, 0.45, 0.1), 0.95); mv = mat('ISSA5_valve', (1.0, 0.9, 0.2)); ms = mat('ISSA5_section', (1.0, 0.6, 0.3), 0.35)
    D = H['net'][1]['D_trunk']; x_hot0 = -111.6; x_hot1 = BULK-L; n = H['sections']
    for az in AZ:
        a = math.radians(az); er = Vector((0, math.cos(a), math.sin(a))); et = Vector((0, -math.sin(a), math.cos(a)))
        for k, off in enumerate((-0.9, 0.9)):
            p0 = Vector((-140.0, 0, 0))+er*5.9+et*off; p1 = Vector((x_hot1, 0, 0))+er*5.9+et*off
            track(rod(f'ISSA5_H6a_Trunk_{az:.0f}_{k}', tuple(p0), tuple(p1), D/2, ch, mt,
                      dict(meaning='H6a primary trunk pair (60 % rated each), tapered toward the bow', D_m=round(D, 2), wall_mm=round(H['net'][1]['t_trunk']*1e3))))
        for sct in range(n):
            xa = x_hot0+sct*(x_hot1-x_hot0)/n; xb = x_hot0+(sct+1)*(x_hot1-x_hot0)/n
            c = Vector(((xa+xb)/2, 0, 0))+er*21.1
            o = box(f'ISSA5_H6a_Section_{az:.0f}_{sct+1}', tuple(c), (xb-xa-0.6, 0.3, 0.3), ch, ms, dict(meaning='isolatable section boundary (schematic)'))
            o.rotation_euler = (a-math.pi/2, 0, 0); o.scale = (1, 1, 100)
            for k, off in enumerate((-0.9, 0.9)):
                box(f'ISSA5_H6a_Valve_{az:.0f}_{sct+1}_{k}', tuple(Vector((xa+0.5, 0, 0))+er*6.6+et*off), (0.8, 0.8, 0.8), ch, mv,
                    dict(meaning='section isolation valve pair'))
    label('H6a: 2 trunk pairs per blade, 6 isolatable sections, heat-pipe fins', (-40, 0, -44), ch, 1.8)
    # district: restart packs and removal routes
    cd = coll('WORK_ISSA5_DISTRICT_STORAGE_ROUTES', root)
    mp = mat('ISSA5_restart', (0.4, 0.9, 0.4)); mr = mat('ISSA5_route', (0.9, 0.9, 0.9), 0.6)
    for az in AZ:
        a = math.radians(az)
        box(f'ISSA5_RestartPack_{az:.0f}', (-78.5, 4.4*math.cos(a+0.5), 4.4*math.sin(a+0.5)), (1.6, 0.9, 1.2), cd, mp,
            dict(meaning='independent L2 restart pack (R1b): own cells, bus and converter', energy_kWh=500))
    track(rod('ISSA5_Route_KeelLane', (-92.0, 0, -3.6), (93.0, 0, -3.6), 0.6, cd, mr, dict(meaning='service and removal route (keel lane, 1.2 m clear)')))
    # ECLSS-G1 units: 3 ring A, 3 ring B, 1 hub
    ce = coll('WORK_ISSA5_ECLSS_G1', root); me = mat('ISSA5_eclss', (0.3, 0.8, 1.0))
    xa, xb = _hr.centers(S); u = P5['eclss']['unit']['envelope_m']
    for tag, xc in (('A', xa), ('B', xb)):
        for k, th in enumerate((30.0, 150.0, 270.0)):
            t = math.radians(th)
            box(f'ISSA5_ECLSS_{tag}{k+1}', (xc, 27.6*math.cos(t), 27.6*math.sin(t)), (u[0], u[1], u[2]), ce, me, dict(meaning='ECLSS-G1 four-person unit', ring=tag))
    box('ISSA5_ECLSS_HUB', ((xa+xb)/2, 0, 3.2), (u[0], u[2], u[1]), ce, me, dict(meaning='ECLSS-G1 cross-ring hub unit (spoke ducts)'))
    # LOG-G1 3 t containers in the hub store (12 months)
    cl = coll('WORK_ISSA5_LOG_G1', root); ml = mat('ISSA5_log', (0.95, 0.8, 0.4))
    c3 = next(c for c in P5['logistics']['containers'] if c['gross_t'] == 3.0); e = c3['edge_m']
    nreq = next(m for m in P5['logistics']['missions'] if m['months'] == 12)['options']['3.0 t']['n']
    for k in range(nreq):
        box(f'ISSA5_LOG_{k+1}', (106.5+(k % 4)*(e+0.2), -2.2+(k // 4)*(e+0.2), -3.0), (e, e, e), cl, ml, dict(meaning='LOG-G1 3 t container', gross_t=3.0))
    # OpenMC source cone
    cr = coll('WORK_ISSA5_OPENMC_3D', root); mc = mat('ISSA5_cone', (0.6, 0.4, 1.0), 0.4)
    for az in AZ:
        a = math.radians(az); p = (-84.0, 2.9*math.cos(a), 2.9*math.sin(a))
        for ph in range(0, 360, 45):
            q = (140.0, p[1]+224*math.tan(math.radians(12.5))*math.cos(math.radians(ph)), p[2]+224*math.tan(math.radians(12.5))*math.sin(math.radians(ph)))
            track(rod(f'ISSA5_Cone_{az:.0f}_{ph}', p, q, 0.08, cr, mc, dict(meaning='12.5 deg shadow cone edge of the OpenMC source')))
    cr.hide_viewport = True
    for o in cr.all_objects: o.hide_render = True


def checks():
    prod = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('ISSA') and not o.hide_render]
    def bb(o):
        w = [o.matrix_world @ Vector(c) for c in o.bound_box]
        return [min(v[i] for v in w) for i in range(3)], [max(v[i] for v in w) for i in range(3)]
    pb = [(o.name, *bb(o)) for o in prod]
    rows = []
    for o in NEW:
        if o.hide_render or o.type != 'MESH': continue
        lo, hi = bb(o); hits = []
        for n, a, b in pb:
            if all(lo[i] < b[i] and hi[i] > a[i] for i in range(3)): hits.append(n)
        rows.append(dict(obj=o.name, bbox_overlaps=len(hits), first=hits[:4]))
    frame = []
    for t in _fs.tanks(S):
        o = bpy.data.objects.get(t['name'])
        if not o: frame.append(dict(tank=t['id'], found=False)); continue
        lo, hi = bb(o); c = [(lo[i]+hi[i])/2 for i in range(3)]
        frame.append(dict(tank=t['id'], found=True, model_center=c, csg_center=[(t['x0']+t['x1'])/2, t['y'], t['z']],
                          d_m=math.dist(c, [(t['x0']+t['x1'])/2, t['y'], t['z']])))
    out = dict(note='bounding-box overlaps are a screen, not a collision proof: a box around a ring or a blade overlaps much empty space',
               new_objects=rows, frame=frame)
    (HERE / 'results' / 'phase5_review_checks.json').write_text(json.dumps(out, indent=1))
    print('CHECKS', sum(1 for r in rows if r['bbox_overlaps']), 'of', len(rows), 'overlap; frame max d', max((f.get('d_m', 0) for f in frame), default=None))


def main():
    mn['build']()
    th = bpy.data.objects.get('Assembly_THERMAL')
    if th:
        th.hide_viewport = False; th.hide_render = False
    root = bpy.data.collections['WORK_SHIP_SYSTEMS_ARCHITECTURE']; cL = bpy.data.collections['WORK_ISSA_90_LABELS']
    for c in root.children:
        if c.name.startswith('WORK_ISSA_6') or c.name in ('WORK_ISSA_20_POWER_CANDIDATES', 'WORK_ISSA_30_MACHINERY_AND_STORES'):
            c.hide_viewport = True
            for o in c.all_objects: o.hide_render = True
    r3 = bpy.data.collections.new('WORK_ISSA3_PHASE3'); root.children.link(r3); r3.color_tag = mn['PINK']
    ns3['phase3'](r3, cL)
    for c in r3.children:
        if not c.name.startswith('WORK_ISSA3_V2'):
            c.hide_viewport = True
            for o in c.all_objects: o.hide_render = True
    r4 = bpy.data.collections.new('WORK_ISSA4_PHASE4'); root.children.link(r4); r4.color_tag = mn['PINK']
    ns4['phase4'](r4)
    r4.hide_viewport = True                     # Phase IV superseded by Phase V (kept for the record)
    for o in r4.all_objects: o.hide_render = True
    r5 = bpy.data.collections.new('WORK_ISSA5_PHASE5'); root.children.link(r5); r5.color_tag = mn['PINK']
    phase5(r5)
    checks()
    c1 = cam(r5, 'CAM_ISSA5_OVERVIEW', (190.0, -150.0, -110.0), (0.0, 0.0, 0.0), 30)
    cam(r5, 'CAM_ISSA5_DISTRICT', (-55.0, -32.0, 18.0), (-85.0, 0.0, 0.0), 40)
    cam(r5, 'CAM_ISSA5_ECLSS', (100.0, -95.0, 55.0), (100.0, 0.0, 0.0), 45)
    cam(r5, 'CAM_ISSA5_RAD3D', (20.0, -360.0, 60.0), (20.0, 0.0, 0.0), 30)
    bpy.context.scene.camera = c1
    if '--render' in sys.argv:
        sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.color_type = 'MATERIAL'
        sc.render.resolution_x, sc.render.resolution_y = 1600, 900; sc.render.film_transparent = False
        sc.world = sc.world or bpy.data.worlds.new('W'); sc.world.color = (0.02, 0.02, 0.03)
        cr = bpy.data.collections['WORK_ISSA5_OPENMC_3D']
        for cname in ('CAM_ISSA5_OVERVIEW', 'CAM_ISSA5_DISTRICT', 'CAM_ISSA5_ECLSS', 'CAM_ISSA5_RAD3D'):
            sc.camera = bpy.data.objects[cname]
            saved = {o.name: o.hide_render for o in bpy.data.objects}
            study = set(root.all_objects) - set(r5.all_objects)
            for o in bpy.data.objects:
                if o.type == 'FONT' or o in study:
                    o.hide_render = True
            if cname == 'CAM_ISSA5_RAD3D':
                for o in cr.all_objects: o.hide_render = False
            sc.render.filepath = str(HERE / 'results' / f'{cname.lower()}.png'); bpy.ops.render.render(write_still=True)
            for o in bpy.data.objects: o.hide_render = saved[o.name]
        sc.camera = c1
    try:
        bpy.ops.file.pack_libraries()
    except Exception as e:  # noqa: BLE001
        print('pack_libraries failed:', e)
    bpy.ops.file.pack_all()
    out = HERE / 'REVIEW_ISSA_PHASE5.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True, relative_remap=False, copy=True)
    print('SAVED', out, out.stat().st_size)


main()
