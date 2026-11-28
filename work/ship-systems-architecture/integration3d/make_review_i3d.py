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


def hook_all(r6):
    hook(r6); hook2(r6)


def render_all():
    render(); render2()


ns['I3D_HOOK'] = hook_all; ns['I3D_RENDER'] = render_all
exec(compile(src, 'make_review6.py', 'exec'), ns)
ns['main']()
