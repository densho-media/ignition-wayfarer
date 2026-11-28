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
src = src.replace("out = HERE / 'REVIEW_ISSA_PHASE6.blend'", "out = HERE / 'REVIEW_I3D.blend'")
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


# ============================================================================================================ Checkpoint 2 (Stages C, D)
from mathutils import Matrix, Vector  # noqa: E402
PW = json.loads((HERE / 'results' / 'i3d_power.json').read_text()); H6 = json.loads((HERE / 'results' / 'i3d_h6a.json').read_text())
FCOL = {'reactor_ihx': (0.75, 0.22, 0.18), 'shield': (0.85, 0.64, 0.22), 'tac': (0.30, 0.25, 0.66), 'recuperator': (0.90, 0.50, 0.15), 'gas_cooler': (0.93, 0.64, 0.24),
        'pmad': (0.36, 0.42, 0.82), 'ic': (0.56, 0.63, 0.71), 'restart': (0.42, 0.36, 0.91), 'structure': (0.56, 0.56, 0.58), 'ducts': (0.75, 0.25, 0.20)}
CP2 = {}


def _obj(name, me, c, m, props):
    o = bpy.data.objects.new(name, me); c.objects.link(o)
    if m and not me.materials: me.materials.append(m)
    for k, v in props.items(): o[k] = v if isinstance(v, (int, float, str)) else str(v)
    o['canon_status'] = 'PROTOTYPE / NONCANON (3D integration, Track F1)'
    return o


def _cyl_mesh(name, r0, r1, L, n=24):
    """Along +Z from -L/2 to +L/2 (frustum when r0 != r1)."""
    vs = [(r*math.cos(2*math.pi*k/n), r*math.sin(2*math.pi*k/n), z) for z, r in ((-L/2, r0), (L/2, r1)) for k in range(n)]
    fs = [(k, (k+1) % n, n+(k+1) % n, n+k) for k in range(n)]+[tuple(range(n))[::-1], tuple(range(n, 2*n))]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update(); return me


def _box_mesh(name, hx, hy, hz):
    vs = [(sx*hx, sy*hy, sz*hz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update(); return me


def _ring_mesh(name, R, r_in, L, n=32):
    vs = []
    for z in (-L/2, L/2):
        for rr in (r_in, R):
            vs += [(rr*math.cos(2*math.pi*k/n), rr*math.sin(2*math.pi*k/n), z) for k in range(n)]
    q = lambda a, b, c, d: (a, b, c, d)
    fs = []
    for k in range(n):
        k1 = (k+1) % n
        fs += [q(n+k, n+k1, 3*n+k1, 3*n+k), q(k, 2*n+k, 2*n+k1, k1), q(k, k1, n+k1, n+k), q(2*n+k, 3*n+k, 3*n+k1, 2*n+k1)]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update(); return me


XROT = Matrix.Rotation(math.radians(90), 4, 'Y')          # mesh +Z -> ship +X


def seg(name, p0, p1, r, c, m, props):
    p0, p1 = Vector(p0), Vector(p1); d = p1-p0; me = _cyl_mesh(name, r, r, d.length, 16)
    o = _obj(name, me, c, m, props); o.matrix_world = Matrix.Translation((p0+p1)/2) @ d.to_track_quat('Z', 'Y').to_matrix().to_4x4(); return o


def unit_meshes():
    """One mesh per unit part, in the unit frame (u -> +X); shared by the three placements (reusable assembly)."""
    U = PW['unit']; out = []
    for p in U['parts']:
        h = p['half']
        if p['shape'] == 'cyl': me = _cyl_mesh('PU_'+p['key'], h[1], h[1], 2*h[0]); M = Matrix.Translation((p['u'], p['v'], p['w'])) @ XROT
        elif p['shape'] == 'cone': me = _cyl_mesh('PU_'+p['key'], h[1], h[2], 2*h[0]); M = Matrix.Translation((p['u'], 0, 0)) @ XROT
        elif p['shape'] == 'ring': me = _ring_mesh('PU_'+p['key'], h[1], h[1]-0.22, 2*h[0]); M = Matrix.Translation((p['u'], 0, 0)) @ XROT
        elif p['shape'] == 'duct':                          # hot leg and return: two tubes outside the shield (dog-leg, no straight streaming path)
            for sgn in (-1, 1):
                me = _cyl_mesh(f'PU_{p["key"]}_{sgn}', 0.2, 0.2, 2*h[0]); out.append((p, me, Matrix.Translation((p['u'], sgn*h[1], 0.0)) @ XROT))
            continue
        else: me = _box_mesh('PU_'+p['key'], *h); M = Matrix.Translation((p['u'], p['v'], p['w']))
        out.append((p, me, M))
    return out


def hook2(r6):
    coll, mat = ns['coll'], ns['mat']
    for nm in ('WORK_ISSA6_F1_POWER_DISTRICT', 'WORK_ISSA6_F1_THERMAL_H6A'):
        c = bpy.data.collections.get(nm)
        if c:
            c.hide_viewport = True
            for o in c.all_objects: o.hide_render = True
    root = coll('WORK_I3D_CP2_POWER_AND_HOT_NETWORK', r6)
    mats = {k: mat(f'I3D_PU_{k}', v, 1.0) for k, v in FCOL.items()}
    meshes = unit_meshes()
    for u in PW['district']:
        c = coll(f'WORK_I3D_C_POWER_UNIT_{u["index"]}', root); CP2[f'U{u["index"]}'] = c
        rot = Matrix.Rotation(math.radians(u['azimuth_deg']-90.0), 4, 'X'); T = Matrix.Translation(u['centre'])
        for p, me, M in meshes:
            o = _obj(f'I3D_U{u["index"]}_{me.name}', me, c, mats[p['key']],
                     dict(meaning=p['name'], mass_t=round(p['mass_t'], 2), modules=p['modules'], replacement=p['replacement'], interfaces='; '.join(p['interfaces']),
                          note=p['note'], maturity='M3 engineering assembly', failure_domain=u['domain'], track='F1 (fiction)', register='FT-03',
                          reusable='one mesh set shared by the three units'))
            o.matrix_world = T @ rot @ M
    cd = coll('WORK_I3D_C_DISTRICT_SERVICES', root); CP2['DIST'] = cd
    d = CFG_D = json.loads((HERE / 'results' / 'i3d_power.json').read_text())['checks']
    xr = (PW['district'][0]['centre'][0]+PW['unit']['u_range'][0]-1.0, PW['district'][0]['centre'][0]+PW['unit']['u_range'][1]+1.0)
    def pz(az, r): a = math.radians(az); return r*math.cos(a), r*math.sin(a)
    y, z = pz(30.0, 3.6); seg('I3D_L1_Bus_Slot', (-140.0, y, z), (xr[1], y, z), 0.22, cd, mat('I3D_l1', (1.0, 0.48, 0.35), 1.0),
                              dict(meaning='L1 bus in its own slot (az 30, r 3.6); Phase VI ran it through unit 90', maturity='M2 arrangement'))
    y, z = pz(270.0, 3.6); seg('I3D_RemovalRoute', (xr[0], y, z), (xr[1]+2.0, y, z), 0.6, cd, mat('I3D_route', (0.95, 0.91, 0.76), 0.35),
                               dict(meaning='removal route (1.2 m clear) along the keel lane at az 270', maturity='M2 arrangement'))
    for i, pth in enumerate(PW['paths']):
        pts = pth['points']
        for j in range(len(pts)-1):
            seg(f'I3D_Path_{i}_{j}', pts[j], pts[j+1], 0.04, cd, mat('I3D_path', (1.0, 1.0, 0.6), 1.0) if i == 0 and j == 0 else bpy.data.materials['I3D_path'],
                dict(meaning=f'replacement path U{pth["unit"]} {pth["part"]} ({pth["cls"]})', maturity='M3'))
    # H6a
    hm = {'Supply': mat('I3D_h6a_supply', (1.0, 0.30, 0.16), 1.0), 'Return': mat('I3D_h6a_return', (1.0, 0.58, 0.32), 1.0), 'hdr': mat('I3D_h6a_hdr', (1.0, 0.70, 0.45), 1.0),
          'valve': mat('I3D_h6a_valve', (0.25, 0.25, 0.28), 1.0), 'bell': mat('I3D_h6a_bell', (0.70, 0.70, 0.72), 1.0), 'pump': mat('I3D_h6a_pump', (0.30, 0.25, 0.66), 1.0),
          'tank': mat('I3D_h6a_tank', (0.55, 0.20, 0.15), 1.0), 'sup': mat('I3D_h6a_sup', (0.56, 0.56, 0.58), 1.0)}
    for blade in sorted({p['blade'] for p in H6['parts']}):
        c = coll(f'WORK_I3D_D_H6A_BLADE_{blade:.0f}', root); CP2[f'H{blade:.0f}'] = c
        rot = Matrix.Rotation(math.radians(blade), 4, 'X')
        for p in (q for q in H6['parts'] if q['blade'] == blade):
            g = p['geo']; nm = p['name']; props = dict(meaning=p['meaning'], mass_t=round(p['mass_t'], 3), material=p['material'], maturity=p['maturity'], track='F1 (fiction)',
                                                    register='FT-01/FT-02', **({'failure_domain': p['domain']} if p.get('domain') else {}))
            m = (hm['Supply'] if 'Supply' in nm and p['kind'] == 'seg' else hm['Return'] if 'Return' in nm and p['kind'] == 'seg' else hm['hdr'] if 'Header' in nm or 'CrossFeed' in nm or 'Line' in nm or 'Bypass' in nm and p['kind'] == 'seg'
                 else hm['valve'] if 'Valve' in nm else hm['bell'] if 'Bellows' in nm else hm['pump'] if 'Pump' in nm else hm['tank'] if p['kind'] == 'cylx' else hm['sup'])
            if p['kind'] == 'seg': seg(nm, g['p0'], g['p1'], g['r'], c, m, props)
            elif p['kind'] == 'box':
                o = _obj(nm, _box_mesh(nm, *g['half']), c, m, props); o.matrix_world = Matrix.Translation(g['c']) @ rot
            elif p['kind'] == 'ring':
                o = _obj(nm, _ring_mesh(nm, g['r']+0.1, g['r']-0.02, g['t'], 20), c, m, props); o.matrix_world = Matrix.Translation(g['c']) @ XROT
            elif p['kind'] == 'cylx':
                o = _obj(nm, _cyl_mesh(nm, g['r'], g['r'], g['L']), c, m, props); o.matrix_world = Matrix.Translation(g['c']) @ XROT
            elif p['kind'] == 'torus':
                n = 10; pts = [(g['x'], g['R']*math.cos(math.radians(g['a0']+(g['a1']-g['a0'])*k/n)), g['R']*math.sin(math.radians(g['a0']+(g['a1']-g['a0'])*k/n))) for k in range(n+1)]
                for k in range(n): seg(f'{nm}_{k}', pts[k], pts[k+1], g['r'], c, m, props)
            elif p['kind'] == 'path':
                seg(nm, g['points'][0], g['points'][1], 0.04, c, bpy.data.materials.get('I3D_path') or mat('I3D_path', (1.0, 1.0, 0.6), 1.0), props)
    cam = ns['cam']
    cam(root, 'CAM_I3D_UNIT', (-80.0, 9.0, 12.0), (-86.0, 0.0, 2.9), 40)
    o = cam(root, 'CAM_I3D_DISTRICT_END', (-60.0, 0.0, 0.0), (-200.0, 0.0, 0.0), 50); o.data.type = 'ORTHO'; o.data.ortho_scale = 16.0
    cam(root, 'CAM_I3D_AFT_MANIFOLD', (-120.0, -9.0, 14.0), (-134.0, 0.0, 5.5), 35)
    o = cam(root, 'CAM_I3D_H6A_SECTION', (-110.0, 0.0, 0.0), (200.0, 0.0, 0.0), 50); o.data.type = 'ORTHO'; o.data.ortho_scale = 27.0; o.data.clip_start = 10.0
    cam(root, 'CAM_I3D_CP2_SHIP', (40.0, -150.0, -70.0), (-60.0, 0.0, 0.0), 30)


def render2():
    if '--render' not in sys.argv: return
    sc = bpy.context.scene
    keep = {o.name: o.hide_render for o in bpy.data.objects}
    def only(colls):
        names = {o.name for c in colls for o in c.all_objects}
        for o in bpy.data.objects:
            if o.type in ('MESH', 'CURVE'): o.hide_render = o.name not in names
            if o.type == 'FONT': o.hide_render = True
    units = [CP2[k] for k in ('U1', 'U2', 'U3')]; h6 = [CP2[k] for k in CP2 if k.startswith('H')]
    for cname, colls in (('CAM_I3D_UNIT', [CP2['U1']]), ('CAM_I3D_DISTRICT_END', units+[CP2['DIST']]+h6), ('CAM_I3D_AFT_MANIFOLD', h6),
                         ('CAM_I3D_H6A_SECTION', h6+units)):
        only(colls); sc.camera = bpy.data.objects[cname]
        sc.render.filepath = str(HERE / 'results' / f'{cname.lower()}.jpg'); bpy.ops.render.render(write_still=True)
    for o in bpy.data.objects: o.hide_render = keep.get(o.name, o.hide_render)
    for o in bpy.data.objects:
        if o.type == 'FONT': o.hide_render = True
    sc.camera = bpy.data.objects['CAM_I3D_CP2_SHIP']; sc.render.filepath = str(HERE / 'results' / 'cam_i3d_cp2_ship.jpg'); bpy.ops.render.render(write_still=True)
    for o in bpy.data.objects: o.hide_render = keep.get(o.name, o.hide_render)


# ============================================================================================================ Checkpoint 3 (Stages E, F)
RD = json.loads((HERE / 'results' / 'i3d_radiators.json').read_text()); EL = json.loads((HERE / 'results' / 'i3d_electrical.json').read_text())
ECOL = {'S1': (0.25, 0.44, 0.85), 'S2': (0.18, 0.64, 0.42), 'S3': (0.79, 0.52, 0.16), 'TIE': (0.15, 0.15, 0.17), 'L1': (0.88, 0.33, 0.23), 'BAR': (0.55, 0.55, 0.58),
        'DEF': (0.82, 0.23, 0.42), 'REF': (0.47, 0.47, 0.47), 'DA': (0.35, 0.63, 0.72), 'DB': (0.22, 0.45, 0.58)}
CP3 = {}


def _hp_row_mesh(name, L, r0, r1, pitch, d):
    """All heat pipes of one row of one bay as one mesh (square section d x d; pipes along +X, stacked along +Y = radius)."""
    vs, fs = [], []; n = int((r1-r0)/pitch); h = d/2
    for i in range(n):
        y = r0+(i+0.5)*pitch; b = len(vs)
        vs += [(x, y+sy*h, sz*h) for x in (0.0, L) for sy in (-1, 1) for sz in (-1, 1)]
        fs += [(b, b+1, b+3, b+2), (b+4, b+6, b+7, b+5), (b, b+4, b+5, b+1), (b+2, b+3, b+7, b+6), (b, b+2, b+6, b+4), (b+1, b+5, b+7, b+3)]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update(); return me


def hook3(r6):
    coll, mat = ns['coll'], ns['mat']
    for nm in ('WORK_ISSA6_F1_RADIATOR_F1', 'WORK_ISSA6_F1_ELECTRICAL'):
        c = bpy.data.collections.get(nm)
        if c:
            c.hide_viewport = True
            for o in c.all_objects: o.hide_render = True
    root = coll('WORK_I3D_CP3_RADIATORS_AND_ELECTRICAL', r6)
    S = RD['section']; G = RD['geometry']; hp = G['parts']; tf = G['blade_half_t']
    m = dict(face=mat('I3D_l2_face', (0.62, 0.60, 0.56), 1.0), hp=mat('I3D_l2_heatpipe', (0.80, 0.34, 0.18), 1.0), A=mat('I3D_l2_hdrA', (0.88, 0.46, 0.18), 1.0),
             B=mat('I3D_l2_hdrB', (0.94, 0.63, 0.31), 1.0), saddle=mat('I3D_l2_saddle', (0.54, 0.35, 0.27), 1.0), nak=mat('I3D_nak', (0.93, 0.50, 0.12), 1.0),
             valve=mat('I3D_nak_valve', (0.25, 0.25, 0.28), 1.0), pump=mat('I3D_nak_pump', (0.30, 0.25, 0.66), 1.0))
    shared = {}
    for q in hp:
        if q['kind'] == 'hp_row': shared[q['bay']] = _hp_row_mesh(f'I3D_HPRow_Bay{q["bay"]+1}', q['x1']-q['x0'], q['r0'], q['r1'], q['pitch'], q['d'])
    for az in (90.0, 210.0, 330.0):
        c = coll(f'WORK_I3D_E_L2_SECTION_{az:.0f}', root); CP3[f'L2_{az:.0f}'] = c
        rot = Matrix.Rotation(math.radians(az), 4, 'X')
        def place(o, x, r, t): o.matrix_world = rot @ Matrix.Translation((x, r, t))
        base = dict(maturity='M3 engineering assembly', track='F1 (fiction)', register='FT-03 / FT-06', failure_domain=f'L2 section {az:.0f}')
        for q in hp:
            if q['kind'] == 'hp_row':
                for sgn in (-1, 1):
                    o = _obj(f'I3D_L2_{az:.0f}_HPRow_B{q["bay"]+1}_{"P" if sgn > 0 else "M"}', shared[q['bay']], c, m['hp'],
                             dict(base, meaning=f'potassium heat pipes, bay {q["bay"]+1}, face {"+" if sgn > 0 else "-"} ({RD["heat_pipes"]["per_row"]} pipes, aft dual-saddle evaporators)'))
                    place(o, q['x0'], 0.0, sgn*q['t'])
            elif q['kind'] == 'header':
                L = q['r1']-q['r0']; me = _cyl_mesh(f'I3D_L2_{az:.0f}_Hdr{q["loop"]}{q["bay"]+1}', q['d']/2, q['d']/2, L, 12)
                o = _obj(me.name, me, c, m[q['loop']], dict(base, meaning=f'NaK header loop {q["loop"]}, bay {q["bay"]+1} (D {q["d"]*1e3:.0f} mm)'))
                o.matrix_world = rot @ Matrix.Translation((q['x'], (q['r0']+q['r1'])/2, 0.0)) @ Matrix.Rotation(math.radians(-90), 4, 'X')
            elif q['kind'] == 'saddle':
                for sgn in (-1, 1):                       # one saddle strip per face row: conduction blocks from the pipe evaporators down to both headers
                    me = _box_mesh(f'I3D_L2_{az:.0f}_Saddle{q["bay"]+1}{"P" if sgn > 0 else "M"}', (q['x1']-q['x0'])/2, (q['r1']-q['r0'])/2, 0.045)
                    o = _obj(me.name, me, c, m['saddle'], dict(base, meaning=f'dual-saddle evaporator strip, bay {q["bay"]+1} (pipes to headers A and B)'))
                    place(o, (q['x0']+q['x1'])/2, (q['r0']+q['r1'])/2, sgn*(q['t']-0.075))
            elif q['kind'] == 'face':
                bay = RD['heat_pipes']['bay_chord_m']
                for nm_, x0, x1, t in (('FaceM', q['x0'], q['x1'], -q['t']), ('FaceP_fwd', q['x0']+bay, q['x1'], q['t'])):     # +t face of bay 1 left open (cutaway)
                    me = _box_mesh(f'I3D_L2_{az:.0f}_{nm_}', (x1-x0)/2, (q['r1']-q['r0'])/2, 0.006)
                    o = _obj(me.name, me, c, m['face'], dict(base, meaning=f'C-C face sheet {nm_} ({C3_FACE} mm); bay 1 + face open as a cutaway'))
                    place(o, (x0+x1)/2, (q['r0']+q['r1'])/2, t)
            elif q['kind'] == 'crossover':
                seg(f'I3D_L2_{az:.0f}_Crossover', (q['x0'], 0, 0), (q['x1'], 0, 0), q['d']/2, c, m['A'], dict(base, meaning='header crossover at the tip (bay 1 -> bay 2)'))
                ob = bpy.data.objects[f'I3D_L2_{az:.0f}_Crossover']; ob.matrix_world = rot @ Matrix.Translation(((q['x0']+q['x1'])/2, q['r'], 0.0)) @ Matrix.Rotation(math.radians(90), 4, 'Y')
    cl = coll('WORK_I3D_E_L2_TRANSPORT_LOOPS', root); CP3['LOOPS'] = cl
    for q in RD['loops']:
        props = dict(meaning=q.get('meaning', f'unit {q["unit"]} NaK loop {q["leg"]}'), maturity='M3 routing', track='F1 (fiction)', failure_domain=f'L2 unit {q["unit"]}')
        if q['kind'] == 'seg': seg(f'I3D_NaK_U{q["unit"]}_{q["leg"]}', q['p0'], q['p1'], q['r'], cl, m['nak'], props)
        elif q['kind'] == 'poly':
            for j in range(len(q['points'])-1): seg(f'I3D_NaK_U{q["unit"]}_{q["leg"]}_{j}', q['points'][j], q['points'][j+1], q['r'], cl, m['nak'], props)
        elif q['kind'] == 'box':
            o = _obj(f'I3D_NaK_U{q["unit"]}_{q["leg"]}', _box_mesh(f'I3D_NaK_U{q["unit"]}_{q["leg"]}', *q['half']), cl, m['valve' if 'Flow' in q['leg'] else 'pump'], props)
            o.matrix_world = Matrix.Translation(q['c'])
    ce = coll('WORK_I3D_F_ELECTRICAL', root); CP3['EL'] = ce
    em = {k: mat(f'I3D_el_{k}', v, 1.0) for k, v in ECOL.items()}
    for q in EL['geometry']:
        props = dict(meaning=q['meaning'], maturity='M2 arrangement', track='F1 (fiction)', failure_domain=q['dom'])
        if q['kind'] == 'seg': seg(q['name'], q['p0'], q['p1'], q['r'], ce, em[q['dom']], props)
        elif q['kind'] == 'poly':
            for j in range(len(q['points'])-1): seg(f'{q["name"]}_{j}', q['points'][j], q['points'][j+1], q['r'], ce, em[q['dom']], props)
        elif q['kind'] in ('box', 'plate'):
            o = _obj(q['name'], _box_mesh(q['name'], *q['half']), ce, em[q['dom']], props)
            o.matrix_world = Matrix.Translation(q['c']) @ (Matrix.Rotation(math.radians(q.get('az', 0.0)-90.0), 4, 'X') if q['kind'] == 'plate' else Matrix.Identity(4))
    for nm in ('RideThrough', 'RestartPack', 'DefenseBuffer', 'Switchgear', 'SurvivalBridge', 'L1_Conditioning', 'L1_DC_Pickup'):
        for a in P6_LAY:
            if a['name'].startswith(nm) and a['shape'] == 'box':
                dom = 'DEF' if 'Defense' in nm else 'REF' if 'Survival' in nm else 'L1' if 'L1' in nm else 'S' + str(1+[30.0, 150.0, 270.0].index(min((30.0, 150.0, 270.0), key=lambda z: abs(((math.degrees(math.atan2(a['c'][2], a['c'][1])) % 360)-z+180) % 360-180))))
                o = _obj(f'I3D_{a["name"]}', _box_mesh(f'I3D_{a["name"]}', a['d'][0]/2, a['d'][1]/2, a['d'][2]/2), ce, em[dom],
                         dict(meaning=a['meaning'], maturity='M2 arrangement', track='F1 (fiction)', failure_domain=a['failure_domain'], register=a.get('register') or '-'))
                o.matrix_world = Matrix.Translation(a['c'])
    cam = ns['cam']; az = math.radians(90.0)
    xm = (S['x0']+S['x1'])/2
    cam(root, 'CAM_I3D_L2_CUTAWAY', (xm-9.0, -9.0, 14.0), (xm+0.5, 0.0, 10.0), 28)
    o = cam(root, 'CAM_I3D_L2_EVAP_DETAIL', (S['x0']+0.35, 0.0, 60.0), (S['x0']+0.35, 0.0, -100.0), 50); o.data.type = 'ORTHO'; o.data.ortho_scale = 1.3; o.data.clip_start = 60.0-21.0
    o = cam(root, 'CAM_I3D_L2_CHORD_CUT', (xm, 0.0, 60.0), (xm, 0.0, -100.0), 50); o.data.type = 'ORTHO'; o.data.ortho_scale = 11.5; o.data.clip_start = 60.0-21.0
    o = cam(root, 'CAM_I3D_ELEC_SECTION', (-76.0, 0.0, 0.0), (200.0, 0.0, 0.0), 16); o.data.clip_start = 0.5; o.data.clip_end = 60.0
    cam(root, 'CAM_I3D_ELEC_OVERVIEW', (60.0, -60.0, 40.0), (-10.0, 0.0, 0.0), 35)
    cam(root, 'CAM_I3D_LOOPS', (22.0, -26.0, 20.0), (41.0, 0.0, 4.0), 30)
    cam(root, 'CAM_I3D_CP3_SHIP', (40.0, -150.0, -70.0), (-60.0, 0.0, 0.0), 30)


def render3():
    if '--render' not in sys.argv: return
    sc = bpy.context.scene; keep = {o.name: o.hide_render for o in bpy.data.objects}
    def only(colls):
        names = {o.name for c in colls for o in c.all_objects}
        for o in bpy.data.objects:
            if o.type in ('MESH', 'CURVE'): o.hide_render = o.name not in names
            if o.type == 'FONT': o.hide_render = True
    l2 = [CP3[k] for k in CP3 if k.startswith('L2_')]
    for cname, colls in (('CAM_I3D_L2_CUTAWAY', [CP3['L2_90']]), ('CAM_I3D_L2_CHORD_CUT', [CP3['L2_90']]), ('CAM_I3D_L2_EVAP_DETAIL', [CP3['L2_90']]), ('CAM_I3D_ELEC_SECTION', [CP3['EL'], CP3['LOOPS']]+[CP2[k] for k in ('U1', 'U2', 'U3')]),
                         ('CAM_I3D_ELEC_OVERVIEW', [CP3['EL']]), ('CAM_I3D_LOOPS', [CP3['LOOPS']]+l2+[CP2[k] for k in ('U1', 'U2', 'U3')])):
        only(colls); sc.camera = bpy.data.objects[cname]
        sc.render.filepath = str(HERE / 'results' / f'{cname.lower()}.jpg'); bpy.ops.render.render(write_still=True)
    for o in bpy.data.objects: o.hide_render = keep.get(o.name, o.hide_render)
    for o in bpy.data.objects:
        if o.type == 'FONT': o.hide_render = True
    sc.camera = bpy.data.objects['CAM_I3D_CP3_SHIP']; sc.render.filepath = str(HERE / 'results' / 'cam_i3d_cp3_ship.jpg'); bpy.ops.render.render(write_still=True)
    for o in bpy.data.objects: o.hide_render = keep.get(o.name, o.hide_render)


EC4 = json.loads((HERE / 'results' / 'i3d_eclss.json').read_text()); LG4 = json.loads((HERE / 'results' / 'i3d_logistics.json').read_text())
RM4 = json.loads((HERE / 'results' / 'i3d_remaining.json').read_text())
CP4 = {}


def _box_at(name, half, c, coll_, m, props, rot=None):
    o = _obj(name, _box_mesh(name, *half), coll_, m, props)
    o.matrix_world = (rot or Matrix.Identity(4)) @ Matrix.Translation(c) if rot is not None else Matrix.Translation(c)
    return o


def _g1_meshes(e, mm_):
    """LOG-G1 frame (12 edge members), 6 panels, grapple fixtures and latches as separate meshes shared by every container."""
    h = e/2; b = mm_/2; parts = {}
    vs, fs = [], []
    for axis in range(3):
        for s1 in (-1, 1):
            for s2 in (-1, 1):
                c = [0.0, 0.0, 0.0]; o = [i for i in range(3) if i != axis]; c[o[0]] = s1*(h-b); c[o[1]] = s2*(h-b)
                hx = [b, b, b]; hx[axis] = h; k = len(vs)
                vs += [(c[0]+sx*hx[0], c[1]+sy*hx[1], c[2]+sz*hx[2]) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
                fs += [(k, k+1, k+3, k+2), (k+4, k+6, k+7, k+5), (k, k+4, k+5, k+1), (k+2, k+3, k+7, k+6), (k, k+2, k+6, k+4), (k+1, k+5, k+7, k+3)]
    me = bpy.data.meshes.new('I3D_G1_Frame'); me.from_pydata(vs, [], fs); me.update(); parts['frame'] = me
    vs, fs = [], []
    for axis in range(3):
        for s in (-1, 1):
            c = [0.0, 0.0, 0.0]; c[axis] = s*(h-b); hx = [h-2*b, h-2*b, h-2*b]; hx[axis] = 0.01; k = len(vs)
            vs += [(c[0]+sx*hx[0], c[1]+sy*hx[1], c[2]+sz*hx[2]) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
            fs += [(k, k+1, k+3, k+2), (k+4, k+6, k+7, k+5), (k, k+4, k+5, k+1), (k+2, k+3, k+7, k+6), (k, k+2, k+6, k+4), (k+1, k+5, k+7, k+3)]
    me = bpy.data.meshes.new('I3D_G1_Panels'); me.from_pydata(vs, [], fs); me.update(); parts['panels'] = me
    vs, fs = [], []
    for (x, y) in ((-h/2, 0.0), (h/2, 0.0), (0.0, -h/2), (0.0, h/2)):             # grapple fixtures on the top face
        k = len(vs); vs += [(x+sx*0.09, y+sy*0.09, h+0.02+sz*0.04) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        fs += [(k, k+1, k+3, k+2), (k+4, k+6, k+7, k+5), (k, k+4, k+5, k+1), (k+2, k+3, k+7, k+6), (k, k+2, k+6, k+4), (k+1, k+5, k+7, k+3)]
    me = bpy.data.meshes.new('I3D_G1_Grapples'); me.from_pydata(vs, [], fs); me.update(); parts['grapple'] = me
    vs, fs = [], []
    for sx_ in (-1, 1):
        for sy_ in (-1, 1):
            for sz_ in (-1, 1):                                                    # 8 corner latches
                k = len(vs); cc = (sx_*(h+0.03), sy_*(h-0.1), sz_*(h-0.1))
                vs += [(cc[0]+sx*0.03, cc[1]+sy*0.06, cc[2]+sz*0.06) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
                fs += [(k, k+1, k+3, k+2), (k+4, k+6, k+7, k+5), (k, k+4, k+5, k+1), (k+2, k+3, k+7, k+6), (k, k+2, k+6, k+4), (k+1, k+5, k+7, k+3)]
    me = bpy.data.meshes.new('I3D_G1_Latches'); me.from_pydata(vs, [], fs); me.update(); parts['latch'] = me
    return parts


def hook4(r6):
    coll, mat, cam = ns['coll'], ns['mat'], ns['cam']
    for nm in ('WORK_ISSA6_F1_ECLSS', 'WORK_ISSA6_F1_LOGISTICS'):
        c = bpy.data.collections.get(nm)
        if c:
            c.hide_viewport = True
            for o in c.all_objects: o.hide_render = True
    root = coll('WORK_I3D_CP4_SYSTEMS', r6)
    m = dict(oru=mat('I3D_eclss_oru', (0.30, 0.66, 0.42), 1.0), env=mat('I3D_eclss_frame', (0.55, 0.58, 0.60), 1.0), duct=mat('I3D_eclss_duct', (0.62, 0.80, 0.70), 1.0),
             ring=mat('I3D_eclss_ring', (0.24, 0.55, 0.36), 1.0), fr=mat('I3D_g1_frame', (0.36, 0.42, 0.48), 1.0), pan=mat('I3D_g1_panel', (0.80, 0.70, 0.30), 1.0),
             gr=mat('I3D_g1_grapple', (0.82, 0.23, 0.42), 1.0), la=mat('I3D_g1_latch', (0.79, 0.52, 0.16), 1.0), dry=mat('I3D_drystore', (0.23, 0.56, 0.82), 1.0),
             rail=mat('I3D_mru_rail', (0.79, 0.52, 0.16), 1.0), car=mat('I3D_mru_carriage', (0.92, 0.62, 0.10), 1.0), rob=mat('I3D_robot', (0.95, 0.85, 0.20), 1.0),
             ws=mat('I3D_workshop', (0.85, 0.78, 0.25), 1.0), cryo=mat('I3D_cryo', (0.40, 0.70, 0.95), 1.0), gnc=mat('I3D_gnc', (0.60, 0.40, 0.80), 1.0))
    # G: ECLSS hub unit (M3) as ORUs inside its envelope frame, ring units (M2), hub-to-ring ducts
    cg = coll('WORK_I3D_G_ECLSS', root); CP4['G'] = cg; h = EC4['hub']; hc = Vector(h['c']); env = h['env']
    base = dict(maturity='M3 engineering assembly', track='R/F', failure_domain='ECLSS hub unit')
    for i, q in enumerate(h['orus']):
        _box_at(f'I3D_ECLSS_HUB_ORU{i+1}', [v/2 for v in q['size']], tuple(hc+Vector(q['c'])), cg, m['oru'],
                dict(base, meaning=f'ORU {q["name"]}: {q["mass_kg"]} kg, {q["power_W"]} W (<= {EC4["unit"]["orus_max_width_m"]:.2f} m wide)'))
    for sx in (-1, 1):
        for sy in (-1, 1):
            seg(f'I3D_ECLSS_HUB_Post_{sx}{sy}', tuple(hc+Vector((sx*env[0]/2, sy*env[1]/2, -env[2]/2))), tuple(hc+Vector((sx*env[0]/2, sy*env[1]/2, env[2]/2))), 0.03, cg, m['env'],
                dict(base, meaning='unit frame post'))
        for z in (-1, 1):
            seg(f'I3D_ECLSS_HUB_RailX_{sx}{z}', tuple(hc+Vector((-env[0]/2, sx*env[1]/2, z*env[2]/2))), tuple(hc+Vector((env[0]/2, sx*env[1]/2, z*env[2]/2))), 0.025, cg, m['env'],
                dict(base, meaning='unit frame rail'))
            seg(f'I3D_ECLSS_HUB_Rail_{sx}{z}', tuple(hc+Vector((sx*env[0]/2, -env[1]/2, z*env[2]/2))), tuple(hc+Vector((sx*env[0]/2, env[1]/2, z*env[2]/2))), 0.025, cg, m['env'],
                dict(base, meaning='unit frame rail'))
    D = EC4['duct']['D_m']
    for tag, cx in (('A', 99.199), ('B', 101.399)):
        p0 = (hc.x+(-0.9 if tag == 'A' else 0.9), 0.0, hc.z-0.5); p1 = (cx, 0.0, 1.40); p2 = (cx, 0.0, -1.40)
        seg(f'I3D_ECLSS_Duct_{tag}_supply', p0, p1, D/2, cg, m['duct'], dict(base, meaning=f'hub-to-ring air duct D {D:.2f} m to rotary coupling {tag} (transfer drum r 1.3-1.5 m)'))
        seg(f'I3D_ECLSS_Duct_{tag}_drum', p1, p2, D/2, cg, m['duct'], dict(base, meaning=f'duct passage through the transfer drum {tag}'))
    for q in EC4['ring_units']:
        _box_at(f'I3D_{q["name"]}', [v/2 for v in q['env']], tuple(q['c']), cg, m['ring'],
                dict(maturity='M2 arrangement', track='R/F', failure_domain=f'ring {q["ring"]}', meaning=f'ECLSS-G1 ring unit {q["name"]} (same ORU set as the hub unit)'))
    # H: LOG-G1 containers (M3, shared meshes), hub store, module 10 dry store, workshop, robots, MRU carriage
    ch = coll('WORK_I3D_H_LOGISTICS', root); CP4['H'] = ch; G1 = LG4['container']; parts = _g1_meshes(G1['edge_m'], G1['member_m'])
    for q in LG4['hub_store']:
        for k, mk in (('frame', 'fr'), ('panels', 'pan'), ('grapple', 'gr'), ('latch', 'la')):
            o = _obj(f'I3D_{q["name"]}_{k}', parts[k], ch, m[mk], dict(maturity='M3 engineering assembly', track='R/F', register='FT-07', failure_domain='hub store',
                     meaning=f'LOG-G1 {k}: {G1["edge_m"]:.2f} m, {G1["tare_t"]:.2f} t tare, {G1["payload_t"]:.2f} t payload'))
            o.matrix_world = Matrix.Translation(q['c'])
    seg('I3D_HubStore_Rail', (105.2, 1.3, -4.2), (114.6, 1.3, -4.2), 0.06, ch, m['rail'], dict(maturity='M2', track='R/F', meaning='hub store transfer rail for the single-arm manipulator'))
    M10 = LG4['module10']
    for q in M10['containers']:
        L = q['x1']-q['x0']; rc = (q['r0']+q['r1'])/2; rot = Matrix.Rotation(math.radians(q['azimuth_deg']), 4, 'X')
        o = _obj(f'I3D_{q["name"]}', _box_mesh(f'I3D_{q["name"]}', L/2, (q['r1']-q['r0'])/2, q['width']/2), ch, m['dry'],
                 dict(maturity='M2 arrangement', track='R/F', failure_domain='body bay module 10', meaning=f'relocated dry-store container ({q["volume_m3"]:.1f} m3), displaced by the L2 district'))
        o.matrix_world = rot @ Matrix.Translation(((q['x0']+q['x1'])/2, rc, 0.0))
    for o in bpy.data.objects:                                                       # Phase VI defense buffers move forward to clear module 10
        if o.name.startswith('I3D_DefenseBuffer_'): o.matrix_world = Matrix.Translation((M10['defense_buffer_shift_m'], 0, 0)) @ o.matrix_world
    ws = LG4['workshop']; _box_at('I3D_Workshop', [v/2 for v in ws['d']], tuple(ws['c']), ch, m['ws'], dict(maturity='M2 arrangement', track='R/F', meaning='workshop: ' + ', '.join(ws['functions'])))
    c_ = LG4['carriage']; a = math.radians(c_['az']); ry, rz = c_['r']*math.cos(a), c_['r']*math.sin(a)
    seg('I3D_MRU_Rail', (c_['x'][0], ry, rz), (c_['x'][1], ry, rz), 0.09, ch, m['rail'],
        dict(maturity='M2 arrangement', track='F1', register='FT-07', meaning=f'MRU heavy-carriage rail, keel lane az {c_["az"]:.0f}, {c_["rail_m"]:.0f} m, {c_["rail_t"]:.1f} t'))
    _box_at('I3D_MRU_Carriage', (1.6, 0.6, 0.6), (-70.0, ry*0.85, rz*0.85), ch, m['car'],
            dict(maturity='M2 arrangement', track='F1', meaning=f'MRU heavy carriage, rated {c_["rating_t"]:.1f} t ({c_["carriage_t"]:.1f} t); {c_["rule"]}'))
    for i, (x, az) in enumerate(((-20.0, 30.0), (10.0, 150.0), (60.0, 270.0))):
        a = math.radians(az); _box_at(f'I3D_Manipulator_{i+1}', (0.5, 0.35, 0.35), (x, 3.0*math.cos(a), 3.0*math.sin(a)), ch, m['rob'],
                                      dict(maturity='M2 arrangement', track='R/F', register='FT-07', meaning='single-arm 3 t manipulator on its keel-lane rail'))
    # I: cryocooler stations (M2), GNC / CDH blocks (M1)
    ci = coll('WORK_I3D_I_CRYO_GNC', root); CP4['I'] = ci
    for q in RM4['cryo']['stations']:
        _box_at(f'I3D_Cryo_{q["tank"]}', (0.8, 0.9, 0.9), tuple(q['c']), ci, m['cryo'],
                dict(maturity='M2 arrangement', track='R/F', failure_domain=f'vessel {q["tank"]}', meaning=f'cryocooler station {q["stage"]} for {q["species"]} vessel {q["tank"]}'))
    for q in RM4['gnc']:
        _box_at('I3D_GNC_' + q['name'].split(' (')[0].replace(' ', '_').replace('/', ''), tuple(q['half']), tuple(q['c']), ci, m['gnc'],
                dict(maturity='M1 placeholder', track='R/F', meaning=q['name']))
    cam(root, 'CAM_I3D_ECLSS_HUB', (hc.x+3.2, hc.y-4.2, hc.z+3.0), tuple(hc), 30)
    cam(root, 'CAM_I3D_LOG_G1', (104.0, -7.5, 1.5), (110.0, -1.0, -3.0), 30)
    cam(root, 'CAM_I3D_MODULE10', (12.0, -14.0, 12.0), (28.0, 0.0, 1.0), 28)
    cam(root, 'CAM_I3D_MRO_ROUTE', (-58.0, -16.0, -14.0), (-80.0, 0.0, -3.0), 26)
    cam(root, 'CAM_I3D_CRYO', (175.0, -70.0, 40.0), (150.0, 0.0, 0.0), 35)


def render4():
    if '--render' not in sys.argv: return
    sc = bpy.context.scene; keep = {o.name: o.hide_render for o in bpy.data.objects}
    def only(colls):
        names = {o.name for c in colls for o in c.all_objects}
        for o in bpy.data.objects:
            if o.type in ('MESH', 'CURVE'): o.hide_render = o.name not in names
            if o.type == 'FONT': o.hide_render = True
    for cname, colls in (('CAM_I3D_ECLSS_HUB', [CP4['G']]), ('CAM_I3D_LOG_G1', [CP4['H']]), ('CAM_I3D_MODULE10', [CP4['H'], CP3['EL']]), ('CAM_I3D_MRO_ROUTE', [CP4['H']]+[CP2[k] for k in ('U1', 'U2', 'U3')]),
                         ('CAM_I3D_CRYO', [CP4['I']]+[c for c in (bpy.data.collections.get('WORK_I3D_TANKS_TA_STRETCH'),) if c])):
        only(colls); sc.camera = bpy.data.objects[cname]
        sc.render.filepath = str(HERE / 'results' / f'{cname.lower()}.jpg'); bpy.ops.render.render(write_still=True)
    for o in bpy.data.objects: o.hide_render = keep.get(o.name, o.hide_render)


P6_LAY = json.loads((HERE / 'results' / 'phase6.json').read_text())['layout']
C3_FACE = '1.2'


def hook_all(r6):
    hook(r6); hook2(r6); hook3(r6); hook4(r6)


def render_all():
    render(); render2(); render3(); render4()


ns['I3D_HOOK'] = hook_all; ns['I3D_RENDER'] = render_all
exec(compile(src, 'make_review6.py', 'exec'), ns)
ns['main']()
