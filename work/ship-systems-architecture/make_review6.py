"""ISSA Phase VI review file: the production ship (unchanged) plus the Track F1 development configuration as functional assemblies, all
parametric from results/phase6.json ('layout'): the three-unit L2 power district (reactor and shield ENVELOPES, Brayton TAC, recuperator,
gas cooler / dual-header manifold, PMAD, mount rings, clearances, removal route), the H6a network in refractory composite (trunk pairs, EM
pumps, accumulators, drain/recovery, section headers, isolation valves, saddles, inspection ports), the F1 L2 sections (950 K, FT-03) with
the F0 / Track R 750 K sections as a hidden comparison, electrical buses / switchgear / ride-through / restart / defense buffer / L1 DC
pickup and conditioning / survival bridge / data networks, seven ECLSS-G1 units with both rotary couplings and the hub duct, LOG-G1
containers, rail, workshop and spares, and the Track F1 tank-farm extension envelope. Each family is its own WORK_ISSA6_F1_* collection;
Phase III-V research layers stay in the file, hidden (Phase V = Track R reference geometry).

    /snap/bin/blender -b assets/wayfarer/WF_WAYFARER_001.blend --python work/ship-systems-architecture/make_review6.py [-- --render]
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(bpy.data.filepath).resolve().parents[2] / 'work' / 'ship-systems-architecture'
src = (HERE / 'make_review5.py').read_text().rsplit('\nmain()', 1)[0]
ns5 = {'__file__': str(HERE / 'make_review5.py'), '__name__': 'make_review5'}
exec(compile(src, 'make_review5.py', 'exec'), ns5)
mn, ns4, ns3 = ns5['mn'], ns5['ns4'], ns5['ns3']
mat, coll, put, tube, rod, label, cam = (mn['mat'], mn['coll'], mn['put'], mn['tube'], mn['rod'], mn['label'], ns3['cam'])
P6 = json.loads((HERE / 'results' / 'phase6.json').read_text())
S = ns5['S']; _fs = ns5['_fs']
NEW = []
# engineering visualisation colours by function (kept separate from final fictional materials, owner 3D brief section 16)
COL = dict(POWER_DISTRICT=(0.95, 0.75, 0.2), THERMAL_H6A=(1.0, 0.42, 0.1), RADIATOR_F1=(0.95, 0.35, 0.55), RADIATOR_F0=(0.6, 0.6, 0.65),
           ELECTRICAL=(0.3, 0.6, 1.0), ECLSS=(0.3, 0.85, 0.5), LOGISTICS=(0.85, 0.8, 0.55), FUEL=(0.7, 0.9, 1.0))
ROD_R = dict(Trunk=None, Header=0.16, MainBus=0.22, DataNet=0.07, L1_Bus=0.22, HubDuct=0.14, HubStoreRail=0.08, District_RemovalRoute=0.6)


def props_of(a):
    p = dict(meaning=a['meaning'], track='F1 (fiction)', family=a['family'], status='PROTOTYPE / NONCANON', config=P6['configs']['F1']['id'])
    for k in ('failure_domain', 'register', 'route', 'clearance_m'):
        if a.get(k) is not None: p[k] = a[k]
    if a['interfaces']: p['interfaces'] = '; '.join(a['interfaces'])
    p['maturity'] = 'M0 reservation' if ('ENVELOPE' in a['meaning'].upper() or 'Clearance' in a['name']) else 'M1 functional envelope'
    return p


def mesh(name, vs, fs, c, m, props):
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    o = put(name, me, c, m, props); NEW.append(o); return o


def cyl_x(name, c, L, ry, rz, col, m, props, n=24):
    x, y, z = c; vs = []
    for xx in (x-L/2, x+L/2):
        for k in range(n):
            t = 2*math.pi*k/n; vs.append((xx, y+ry*math.cos(t), z+rz*math.sin(t)))
    fs = [(k, (k+1) % n, n+(k+1) % n, n+k) for k in range(n)] + [tuple(range(n))[::-1], tuple(range(n, 2*n))]
    return mesh(name, vs, fs, col, m, props)


def ring_x(name, c, t, R, col, m, props, n=32):
    x, y, z = c; r0 = R*0.82; vs = []
    for xx in (x-t/2, x+t/2):
        for r in (R, r0):
            for k in range(n):
                a = 2*math.pi*k/n; vs.append((xx, y+r*math.cos(a), z+r*math.sin(a)))
    def i(s, j, k): return s*2*n+j*n+k % n
    fs = []
    for k in range(n):
        fs += [(i(0, 0, k), i(0, 0, k+1), i(1, 0, k+1), i(1, 0, k)), (i(0, 1, k), i(1, 1, k), i(1, 1, k+1), i(0, 1, k+1)),
               (i(0, 0, k), i(0, 1, k), i(0, 1, k+1), i(0, 0, k+1)), (i(1, 0, k), i(1, 0, k+1), i(1, 1, k+1), i(1, 1, k))]
    return mesh(name, vs, fs, col, m, props)


def build6(root):
    mats = {f: mat(f'ISSA6_{f}', c, 1.0) for f, c in COL.items()}
    mclear = mat('ISSA6_clearance', (0.9, 0.9, 0.9), 0.12); menv = mat('ISSA6_envelope', (0.95, 0.85, 0.4), 0.35)
    cols = {}
    D = P6['hot']['F1'].get('D_trunk') or P6['hot']['F0']['D_trunk']
    for a in P6['layout']:
        fam = a['family']
        if fam not in cols:
            cols[fam] = coll(f'WORK_ISSA6_F1_{fam}', root)
        c = cols[fam]; m = mats.get(fam, mats['POWER_DISTRICT']); pr = props_of(a)
        if 'Clearance' in a['name']: m = mclear
        elif 'Envelope' in a['name']: m = menv
        nm = f'ISSA6_{a["name"]}'; sh = a['shape']
        if sh == 'box':
            o = ns5['box'](nm, tuple(a['c']), tuple(a['d']), c, m, pr); NEW.append(o)
        elif sh == 'cyl':
            cyl_x(nm, a['c'], a['d'][0], a['d'][1], a['d'][2], c, m, pr)
        elif sh == 'ring':
            ring_x(nm, a['c'], a['d'][0], a['d'][1], c, m, pr)
        elif sh == 'rod':
            key = next((k for k in ROD_R if a['name'].startswith(k)), None)
            r = (D/2 if key == 'Trunk' else ROD_R.get(key, 0.12))
            NEW.append(rod(nm, tuple(a['c']), tuple(a['d']), r, c, m, pr))
        elif sh == 'sector':
            NEW.append(ns4['sector'](nm, a['c'][0], a['d'][0], a['c'][1], a['c'][2], a['d'][1], a['d'][2], c, m, pr))
        elif sh == 'tube':
            NEW.append(tube(nm, a['c'][0], a['d'][0], a['c'][1], a['c'][2], c, m, pr))
    if 'RADIATOR_F0' in cols:                                  # comparison: the 750 K sections (F0 / Track R), hidden
        cols['RADIATOR_F0'].hide_viewport = True
        for o in cols['RADIATOR_F0'].all_objects: o.hide_render = True
    for n in ('POWER_DISTRICT',):                              # clearances hidden by default; visible on demand
        for o in cols[n].all_objects:
            if 'Clearance' in o.name: o.hide_render = True; o.hide_viewport = True
    # Track F1 tank-farm extension envelope (lengthen all 13 vessels forward; Stage B of the 3D brief compares alternatives)
    cf = coll('WORK_ISSA6_F1_FUEL_EXTENSION_ENVELOPE', root); mf = mat('ISSA6_fuel_ext', COL['FUEL'], 0.3)
    ext = next(r for r in P6['tanks']['F1']['rows'] if r['case'] == 'nom')['extension_m']
    for t in _fs.tanks(S):
        cyl_x(f'ISSA6_TankExt_{t["id"]}', ((t['x1']+t['x1']+ext)/2, t['y'], t['z']), ext, t['a'], t['a'], cf, mf,
              dict(meaning=f'Track F1 propellant volume beyond the historical farm (nominal +{ext:.1f} m per vessel; M0 reservation)', track='F1',
                   status='PROTOTYPE / NONCANON', maturity='M0 reservation', problem='P6-05'))
    label(f'Track F1 tank volume: +{ext:.1f} m on every vessel (M0, alternatives in the next stage)', (128.0, 0, -44), cf, 1.8)
    label('F1 power district: 3 x 3.5 MWe, 1500 K Brayton (FT-03), reactor + shield ENVELOPES only', (-86.0, 0, -12), cols['POWER_DISTRICT'], 1.0)
    return cols


def checks6():
    prod = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('ISSA') and not o.hide_render]
    def bb(o):
        w = [o.matrix_world @ Vector(c) for c in o.bound_box]
        return [min(v[i] for v in w) for i in range(3)], [max(v[i] for v in w) for i in range(3)]
    pb = [(o.name, *bb(o)) for o in prod]
    mine = [o for o in NEW if o.type == 'MESH' and not o.hide_render and 'Clearance' not in o.name]
    rows = []
    for o in mine:
        lo, hi = bb(o); hits = [n for n, a, b in pb if all(lo[i] < b[i] and hi[i] > a[i] for i in range(3))]
        rows.append(dict(obj=o.name, family=o.get('family'), bbox_overlaps_production=len(hits), first=hits[:3]))
    # new-vs-new overlaps across different families (unintended interference screen)
    inter = []
    bbs = [(o.name, o.get('family'), *bb(o)) for o in mine]
    for i, (n1, f1, a1, b1) in enumerate(bbs):
        for n2, f2, a2, b2 in bbs[i+1:]:
            if f1 != f2 and all(a1[k] < b2[k] and b1[k] > a2[k] for k in range(3)):
                inter.append((n1, n2))
    ids = [o.name for o in NEW]
    out = dict(note='bounding-box screens only (a box around a blade or ring is mostly empty space); not a collision proof',
               objects=len(NEW), unique_ids=len(set(ids)) == len(ids), production_overlaps=sum(1 for r in rows if r['bbox_overlaps_production']),
               cross_family_overlaps=len(inter), cross_family_first=inter[:20], rows=rows,
               register_refs=sorted({str(o.get('register')) for o in NEW if o.get('register')}))
    (HERE / 'results' / 'phase6_review_checks.json').write_text(json.dumps(out, indent=1))
    print('CHECKS6 objects', len(NEW), 'prod overlaps', out['production_overlaps'], 'cross-family', len(inter), 'unique', out['unique_ids'])


def section_cam(root, name, loc, target, ortho, clip):
    o = cam(root, name, loc, target, 50); o.data.type = 'ORTHO'; o.data.ortho_scale = ortho; o.data.clip_start = clip; return o


def main():
    mn['build']()
    th = bpy.data.objects.get('Assembly_THERMAL')
    if th: th.hide_viewport = False; th.hide_render = False
    root = bpy.data.collections['WORK_SHIP_SYSTEMS_ARCHITECTURE']
    for c in list(root.children):                              # Phase I-II layers hidden
        c.hide_viewport = True
        for o in c.all_objects: o.hide_render = True
    for nm, fn in (('WORK_ISSA3_PHASE3', lambda r: ns3['phase3'](r, bpy.data.collections['WORK_ISSA_90_LABELS'])), ('WORK_ISSA4_PHASE4', ns4['phase4']),
                   ('WORK_ISSA5_PHASE5_TRACK_R_REFERENCE', ns5['phase5'])):
        r = bpy.data.collections.new(nm); root.children.link(r); r.color_tag = mn['PINK']; fn(r)
        r.hide_viewport = True
        for o in r.all_objects: o.hide_render = True
    r6 = bpy.data.collections.new('WORK_ISSA6_TRACK_F1'); root.children.link(r6); r6.color_tag = mn['PINK']
    cols = build6(r6)
    checks6()
    c1 = cam(r6, 'CAM_ISSA6_OVERVIEW', (170.0, -160.0, -95.0), (-10.0, 0.0, 0.0), 30)
    cam(r6, 'CAM_ISSA6_DISTRICT', (-66.0, -14.0, 9.0), (-86.0, 0.0, 0.0), 30)
    cam(r6, 'CAM_ISSA6_HOT_NETWORK', (-150.0, -30.0, 22.0), (-110.0, 0.0, 0.0), 30)
    cam(r6, 'CAM_ISSA6_HUB', (112.0, -22.0, 12.0), (100.0, 0.0, 0.0), 30)
    section_cam(r6, 'CAM_ISSA6_SECTION_X86', (-40.0, 0.0, 0.0), (-200.0, 0.0, 0.0), 14.0, 45.5)     # transverse cut at x -85.5, looking aft
    section_cam(r6, 'CAM_ISSA6_SECTION_X40', (90.0, 0.0, 0.0), (-200.0, 0.0, 0.0), 80.0, 50.0)      # cut through the F1 L2 section, looking aft
    section_cam(r6, 'CAM_ISSA6_SECTION_LONG', (0.0, -300.0, 0.0), (0.0, 0.0, 0.0), 310.0, 300.0)   # longitudinal cut at y 0, from -y
    bpy.context.scene.camera = c1
    if '--render' in sys.argv:
        sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.color_type = 'MATERIAL'
        sc.render.resolution_x, sc.render.resolution_y = 1600, 900; sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 88
        sc.world = sc.world or bpy.data.worlds.new('W'); sc.world.color = (0.02, 0.02, 0.03)
        for cname in ('CAM_ISSA6_OVERVIEW', 'CAM_ISSA6_DISTRICT', 'CAM_ISSA6_HOT_NETWORK', 'CAM_ISSA6_HUB', 'CAM_ISSA6_SECTION_X86', 'CAM_ISSA6_SECTION_X40',
                      'CAM_ISSA6_SECTION_LONG'):
            sc.camera = bpy.data.objects[cname]
            saved = {o.name: o.hide_render for o in bpy.data.objects}
            for o in bpy.data.objects:
                if o.type == 'FONT': o.hide_render = True
            sc.render.filepath = str(HERE / 'results' / f'{cname.lower()}.jpg'); bpy.ops.render.render(write_still=True)
            for o in bpy.data.objects: o.hide_render = saved[o.name]
        sc.camera = c1
    try:
        bpy.ops.file.pack_libraries()
    except Exception as e:  # noqa: BLE001
        print('pack_libraries failed:', e)
    bpy.ops.file.pack_all()
    out = HERE / 'REVIEW_ISSA_PHASE6.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True, relative_remap=False, copy=True)
    print('SAVED', out, out.stat().st_size)


main()
