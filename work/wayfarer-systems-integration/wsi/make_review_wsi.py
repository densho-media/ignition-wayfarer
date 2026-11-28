"""WSI integrated review file: the approved ship + the joint WSI configuration (PSA structure, ISSA machinery, propellant, thermal,
electrical, logistics, interfaces, envelopes, alternatives, Track F references, sections) in WORK_WSI_* collections, one view layer per
review mode, framed cameras, packed. Regenerated entirely from results/wsi_config.json, wsi_members.json and wsi_cp2.json.

    /snap/bin/blender -b assets/wayfarer/WF_WAYFARER_001.blend --python work/wayfarer-systems-integration/wsi/make_review_wsi.py [-- --render]

Production GEN content is untouched: parts the joint configuration replaces (Brow and EYE at the historical station, the 150 t
structure line, the historical farm) are hidden in the WSI views, never deleted; the translated Brow is a second instance.
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(bpy.data.filepath).resolve().parents[2]
W = ROOT/'work'/'wayfarer-systems-integration'; RES = W/'results'
CFG = json.loads((RES/'wsi_config.json').read_text()); MEM = json.loads((RES/'wsi_members.json').read_text())
CP2 = json.loads((RES/'wsi_cp2.json').read_text())
OUT = W/'REVIEW_WSI_CP3.blend'
PINK = 'COLOR_06'
SPC = {'helium-3': (0.56, 0.30, 0.88), 'hydrogen': (0.14, 0.32, 0.92), 'deuterium': (0.02, 0.56, 0.52)}
FAM = {'rail': (0.85, 0.35, 0.2), 'trans': (0.75, 0.15, 0.1), 'ring': (0.6, 0.1, 0.1), 'pickup': (0.6, 0.1, 0.1), 'frame': (0.55, 0.55, 0.6),
       'modframe': (0.95, 0.75, 0.2), 'diag': (0.4, 0.6, 0.85), 'tie': (0.5, 0.5, 0.5), 'hubcone': (0.9, 0.2, 0.6), 'spine': (0.2, 0.8, 0.5),
       'hub': (0.2, 0.8, 0.5), 'collar': (0.6, 0.4, 0.9), 'keel': (0.85, 0.5, 0.2), 'deck': (0.95, 0.55, 0.1), 'guide': (0.7, 0.7, 0.3),
       'vesselwall': (0.3, 0.3, 0.35), 'iface': (0.3, 0.3, 0.3)}
LOOP = {'TI-HOT': (1.0, 0.25, 0.05), 'TI-L2': (1.0, 0.55, 0.1), 'TI-WARM': (0.95, 0.85, 0.2), 'TI-LOW': (0.3, 0.75, 0.95)}
MATS = {}


def mat(name, rgb, alpha=1.0, emit=0.0):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new('WSI_'+name); m.use_nodes = True; b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*rgb, 1.0); b.inputs['Alpha'].default_value = alpha
    if emit:
        b.inputs['Emission Color'].default_value = (*rgb, 1.0); b.inputs['Emission Strength'].default_value = emit
    m.diffuse_color = (*rgb, alpha)
    if alpha < 1:
        try:
            m.blend_method = 'BLEND'
        except Exception:  # noqa: BLE001
            pass
    MATS[name] = m
    return m


def coll(name, parent, color=PINK):
    c = bpy.data.collections.new(name); parent.children.link(c); c.color_tag = color
    return c


def obj(name, bm, c, m, props=None):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); o = bpy.data.objects.new(name, me); c.objects.link(o)
    if m:
        me.materials.append(m)
    for k, v in (props or {}).items():
        o[k] = v if isinstance(v, (int, float, str)) else json.dumps(v, default=float)
    return o


def add_tube(bm, p0, p1, r, sides=8):
    p0, p1 = Vector(p0), Vector(p1); d = p1-p0; L = d.length
    if L < 1e-6:
        return
    q = d.to_track_quat('Z', 'Y'); M = Matrix.Translation(p0+d/2) @ q.to_matrix().to_4x4()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=sides, radius1=r, radius2=r, depth=L, matrix=M)


def tubes(name, segs, c, m, sides=8, props=None):
    bm = bmesh.new()
    for p0, p1, r in segs:
        add_tube(bm, p0, p1, r, sides)
    return obj(name, bm, c, m, props)


def cyl_x(name, x0, x1, r, y, z, c, m, props=None, sides=32):
    bm = bmesh.new(); add_tube(bm, (x0, y, z), (x1, y, z), r, sides); return obj(name, bm, c, m, props)


def shell_x(name, x0, x1, r_in, r_out, c, m, props=None, n=48, a0=0.0, a1=360.0):
    bm = bmesh.new(); vs = []
    for x in (x0, x1):
        for rr in (r_in, r_out):
            row = []
            for i in range(n+1):
                a = math.radians(a0+(a1-a0)*i/n); row.append(bm.verts.new((x, rr*math.cos(a), rr*math.sin(a))))
            vs.append(row)
    for i in range(n):
        for A, B in ((0, 1), (2, 3), (0, 2), (1, 3)):
            bm.faces.new((vs[A][i], vs[A][i+1], vs[B][i+1], vs[B][i]))
    return obj(name, bm, c, m, props)


def plate(name, x0, x1, r0, r1, azd, c, m, props=None, t=0.15):
    a = math.radians(azd); u = Vector((0, math.cos(a), math.sin(a))); w = Vector((0, -math.sin(a), math.cos(a)))
    bm = bmesh.new(); vs = []
    for x in (x0, x1):
        for r in (r0, r1):
            for s in (-t/2, t/2):
                vs.append(bm.verts.new(Vector((x, 0, 0))+u*r+w*s))
    bmesh.ops.convex_hull(bm, input=vs)
    return obj(name, bm, c, m, props)


def box(name, cen, half, c, m, props=None):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(cen) @ Matrix.Diagonal((*[2*h for h in half], 1)))
    return obj(name, bm, c, m, props)


def sphere(bm, p, r):
    bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=r, matrix=Matrix.Translation(p))


def label(text, loc, c, size=2.5):
    cu = bpy.data.curves.new(text[:20], 'FONT'); cu.body = text; cu.size = size; cu.align_x = 'CENTER'
    o = bpy.data.objects.new('LBL_'+text[:30], cu); o.location = loc; o.rotation_euler = (math.radians(90), 0, 0); c.objects.link(o)
    o.data.materials.append(mat('label', (1, 1, 1), 1, 2.0)); return o


def pz(azd, r):
    a = math.radians(azd); return r*math.cos(a), r*math.sin(a)


def cam(c, name, loc, target, lens=30, ortho=None):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_end = 3000
    if ortho:
        cd.type = 'ORTHO'; cd.ortho_scale = ortho
    o = bpy.data.objects.new(name, cd); c.objects.link(o); o.location = loc
    d = Vector(target)-Vector(loc); o.rotation_euler = d.to_track_quat('-Z', 'Z').to_euler(); return o


# ---------------------------------------------------------------------------------------------------------------- builders
def structure(c):
    X = MEM['nodes']; by = {}
    for m in MEM['members']:
        by.setdefault(m['fam'], []).append((X[m['a']], X[m['b']], max(0.06, min(m['r'], 1.2))))
    for fam, segs in by.items():
        tubes(f'WSI_STR_{fam}', segs, c, mat('fam_'+fam, FAM.get(fam, (0.6, 0.6, 0.6))), props=dict(wf_owner='wsi.cp3', family=fam, members=len(segs),
              source=MEM['source'], structure_t=MEM['structure_t']))


def loadpath(c):
    """Members coloured by steady axial force at departure: compression red, tension blue, scaled by |N|."""
    X = MEM['nodes']; Nmax = max(abs(m['N_MN']) for m in MEM['members'] if m['primary']) or 1.0; bins = {}
    for m in MEM['members']:
        if abs(m['N_MN']) < 0.02*Nmax:
            continue
        k = ('C' if m['N_MN'] < 0 else 'T')+str(min(4, int(4*abs(m['N_MN'])/Nmax)))
        bins.setdefault(k, []).append((X[m['a']], X[m['b']], 0.08+0.5*abs(m['N_MN'])/Nmax))
    for k, segs in bins.items():
        lvl = int(k[1])/4; rgb = (0.4+0.6*lvl, 0.1, 0.1) if k[0] == 'C' else (0.1, 0.2, 0.4+0.6*lvl)
        tubes(f'WSI_LOAD_{k}', segs, c, mat('load_'+k, rgb, 1.0, 0.6), props=dict(meaning='steady thrust axial force at departure', bin=k, Nmax_MN=Nmax))


def propellant(c):
    for v in CFG['tanks']['vessels']:
        y, z = pz(v['az'], v['R'])
        cyl_x(f'WSI_VESSEL_{v["id"]}', v['x'][0], v['x'][1], v['a'], y, z, c, mat('sp_'+v['species'], SPC[v['species']], 0.85),
              props=dict(species=v['species'], loaded_t=v['loaded_t'], fill=v['fill'], volume_m3=v['volume_m3']))


def machinery(c):
    for e in CFG['equipment']:
        env = e['envelope'] if isinstance(e['envelope'], dict) else {}; cg = e['cg']
        if not cg:
            continue
        p = dict(owner=e['owner'], mass_t=e['mass_t'] or 0.0, register=e['register'], maturity=e['maturity'])
        if e['id'].startswith('PWR-L2U'):
            cyl_x(f'WSI_{e["id"]}', env['x'][0], env['x'][1], 1.9, cg[1], cg[2], c, mat('unit', (0.85, 0.3, 0.3)), p)
        elif e['id'].startswith(('CRYO-', 'HUB-ECLSS')):
            box(f'WSI_{e["id"]}', cg, [h/2 for h in env.get('box', (1.6, 1.8, 1.8))], c, mat('cryo', (0.6, 0.9, 1.0)), p)
        elif e['id'] == 'EXT-TA':
            box('WSI_EXT-TA', cg, (4.2, 1.0, 3.2), c, mat('mro', (0.95, 0.85, 0.2)), p)
        elif e['id'] == 'BODY-M10':
            shell_x('WSI_BODY-M10', env['x'][0], env['x'][1], env['r'][0], env['r'][1], c, mat('m10', (0.8, 0.7, 0.5), 0.6), p)


def thermal(c):
    env = CFG['dimensions']['radiator_envelope']
    for key, tid, (x0, x1), (r0, r1) in (('HOT', 'TI-HOT', env['hot_x'], (6.5, 37.0)), ('L2', 'TI-L2', env['l2_x'], (6.5, 36.1)),
                                          ('WARM', 'TI-WARM', env['warm_x'], (6.5, 37.0)), ('LOW', 'TI-LOW', env['low_x'], (6.5, 31.5)),
                                          ('LOWTAB', 'TI-LOW', env['low_tabs_x'], (31.5, 37.0))):
        for a in env['blades']:
            plate(f'WSI_RAD_{key}_{a:.0f}', x0, x1, r0, r1, a, c, mat('loop_'+tid, LOOP[tid], 0.7, 0.4), dict(loop=tid, x=(x0, x1)))
    segs = []
    for a in (90.0, 210.0, 330.0):
        y, z = pz(a, 6.52); segs.append(((-111.6, y, z), (41.02, y, z), 0.45))
    tubes('WSI_H6A_TRUNKS', segs, c, mat('h6a', (1.0, 0.35, 0.1), 1, 0.8), props=dict(meaning='H6a Li hot trunks (outside the hull)'))


def electrical(c):
    for u in CFG['utility_routes']:
        azs = u['az'] if isinstance(u['az'], (list, tuple)) else [u['az']]
        segs = [((u['x'][0], *pz(a, u['r_m'])), (u['x'][1], *pz(a, u['r_m'])), 0.12) for a in azs]
        col = (0.95, 0.85, 0.1) if 'BUS' in u['id'] or 'L1' in u['id'] else (0.2, 0.9, 0.9) if 'DATA' in u['id'] else (1.0, 0.45, 0.1)
        tubes(f'WSI_{u["id"]}', segs, c, mat('route_'+u['id'], col, 1, 0.5), props=dict(what=u['what']))


def logistics(c):
    MR = next(u for u in CFG['utility_routes'] if u['id'] == 'UR-MRU')
    tubes('WSI_MRU_RAILS', [((MR['x'][0], *pz(a, MR['r_m'])), (MR['x'][1], *pz(a, MR['r_m'])), 0.15) for a in MR['az']], c, mat('mru', (0.95, 0.85, 0.2)))
    box('WSI_LOG-G1_STORE', (100.5, 0, -2.2), (5.0, 1.6, 1.0), c, mat('log', (0.4, 0.85, 0.4)), dict(what='LOG-G1 3 t containers hub store'))


def envelopes(c):
    ko = {k['id']: k for k in CFG['keepouts']}
    kr = ko['K-RING']; shell_x('WSI_K-RING', kr['x'][0], kr['x'][1], 2.0, kr['r_max_m'], c, mat('ko_ring', (0.9, 0.2, 0.2), 0.12), dict(meaning=kr['what']))
    for kid, a in (('K-MRU-F', 255.0), ('K-MRU-F', 285.0), ('K-MRU-Y', 255.0), ('K-MRU-Y', 285.0)):
        k = ko[kid]; y, z = pz(a, k['r_lane_m'])
        cyl_x(f'WSI_{kid}_{a:.0f}', k['x'][0], k['x'][1], k['radius_m'], y, z, c, mat('ko_'+kid, (0.95, 0.6, 0.1) if kid.endswith('F') else (0.9, 0.3, 0.6), 0.2),
              dict(meaning=k['what']), sides=12)
    # plume cone 15 deg from the nozzle plane aft
    bm = bmesh.new(); L = 120.0
    bmesh.ops.create_cone(bm, cap_ends=False, segments=32, radius1=L*math.tan(math.radians(15.0)), radius2=0.5, depth=L,
                          matrix=Matrix.Translation((-140.0-L/2, 0, 0)) @ Matrix.Rotation(math.radians(90), 4, 'Y'))
    obj('WSI_K-PLUME', bm, c, mat('plume', (1.0, 0.5, 0.1), 0.08), dict(meaning='drive plume cone 15 deg'))
    # interferences from the member check
    bm = bmesh.new(); X = MEM['nodes']; n = 0
    for chk in MEM['checks']:
        if chk.get('verdict') == 'INTERFERENCE':
            m = next(mm for mm in MEM['members'] if mm['i'] == chk['member']); p = (Vector(X[m['a']])+Vector(X[m['b']]))/2; sphere(bm, p, 0.6); n += 1
    if n:
        obj('WSI_INTERFERENCES', bm, c, mat('clash', (1.0, 0.0, 0.0), 1, 3.0), dict(count=n, meaning='member check: hub cone aft legs vs MRU flight lane'))


def interfaces(c):
    bmA, bmS = bmesh.new(), bmesh.new()
    for m in CFG['mounts']:
        x = m.get('x'); r = m.get('r'); a = m.get('az')
        if x is None or r is None or a is None:
            continue
        y, z = pz(a, r); sphere(bmA if m.get('type') == 'anchor' else bmS, (x, y, z), 0.35)
    obj('WSI_MOUNTS_ANCHOR', bmA, c, mat('anchor', (1, 0.2, 0.2), 1, 1.0), dict(meaning='SSI anchors (6-DOF)'))
    obj('WSI_MOUNTS_SLIDE', bmS, c, mat('slide', (0.2, 0.5, 1), 1, 1.0), dict(meaning='SSI slides (axial free)'))
    tubes('WSI_L2_INTERFACE_X41', [((41.0, *pz(a, 0.0)), (41.0, *pz(a, 6.5)), 0.2) for a in range(0, 360, 30)], c, mat('if41', (1, 1, 1)), props=dict(station=41.0))


def alternatives(c):
    tb = next((x for x in CP2['propellant']['candidates'] if x['id'].startswith('T-B')), None)
    if tb:
        x1 = CFG['tanks']['vessels'][0]['x'][1]; mid = 0.5*(CFG['dimensions']['farm_x'][0]+x1)
        shell_x('WSI_ALT_TB_INTERMEDIATE_DECK', mid, mid+1.0, 2.0, 34.0, c, mat('alt_tb', (0.9, 0.9, 0.9), 0.35),
                dict(candidate='T-B tandem', departure_t=tb['departure_t'], ship_length_m=tb['ship_length_m']))
    g = CP2['propellant']['g_screens'][0]
    cyl_x('WSI_ALT_G_HULL', -119.0, -94.0, 4.0, 0, 0, c, mat('alt_g', SPC['hydrogen'], 0.35), dict(candidate='G-HULL', H2_t=g['H2_t'], verdict=g['verdict']))
    ga = CP2['propellant']['g_screens'][1]
    for a in (30.0, 150.0, 270.0):
        shell_x(f'WSI_ALT_G_ANNULAR_{a:.0f}', -125.0, -95.0, 8.2, 20.0, c, mat('alt_ga', (0.9, 0.1, 0.1), 0.18), dict(candidate='G-ANNULAR', verdict=ga['verdict']),
                n=16, a0=a-55.0, a1=a+55.0)


def fiction(c):
    for t, loc in (('FT-03 Brayton 1500 K (L2 units)', (-86.0, 0, 12.0)), ('FT-06 HOT forward fins', (-46.0, 0, 40.0)), ('FT-07 MRU / EXT-TA', (-10.0, 0, -10.0)),
                   ('FT-09 451 K WARM machinery', (61.0, 0, 40.0)), ('FT-01 refractory boundary (H6a)', (-80.0, 0, 9.5)),
                   ('WSI-0.1 Track F working configuration (noncanon)', (40.0, 0, 55.0))):
        label(t, loc, c, 2.2)


def sections(c_long, c_tr):
    """Longitudinal half (y >= 0 members, vessels, envelopes cut at y 0) and transverse slabs at stations, members by load."""
    X = MEM['nodes']; half = []
    for m in MEM['members']:
        a, b = X[m['a']], X[m['b']]
        if a[1] >= -0.05 and b[1] >= -0.05:
            half.append((a, b, max(0.06, min(m['r'], 1.2)), m['N_MN']))
    for sign, nm, rgb in ((-1, 'C', (0.9, 0.15, 0.1)), (1, 'T', (0.15, 0.35, 0.95)), (0, 'U', (0.6, 0.6, 0.6))):
        segs = [(a, b, r) for a, b, r, N in half if (N < -0.05 if sign < 0 else N > 0.05 if sign > 0 else abs(N) <= 0.05)]
        if segs:
            tubes(f'WSI_SEC_LONG_{nm}', segs, c_long, mat('sec_'+nm, rgb, 1, 0.5), props=dict(meaning='longitudinal half-section y >= 0, colour = steady axial force sign'))
    for xs in (-130.0, -86.0, 0.0, 41.0, 100.0, 120.0, 160.0):
        segs = [(X[m['a']], X[m['b']], max(0.08, min(m['r'], 1.2))) for m in MEM['members'] if min(X[m['a']][0], X[m['b']][0]) <= xs+1.0 and max(X[m['a']][0], X[m['b']][0]) >= xs-1.0
                and abs(X[m['a']][0]-X[m['b']][0]) < 2.5]
        if segs:
            tubes(f'WSI_SEC_X{xs:+.0f}', segs, c_tr, mat('sec_x', (0.95, 0.95, 0.95)), props=dict(station=xs))
        for v in CFG['tanks']['vessels']:
            if v['x'][0] <= xs <= v['x'][1]:
                y, z = pz(v['az'], v['R']); cyl_x(f'WSI_SEC_X{xs:+.0f}_{v["id"]}', xs-0.25, xs+0.25, v['a'], y, z, c_tr, mat('sp_'+v['species'], SPC[v['species']], 0.85))


def production_replacements():
    """Translated Brow/EYE instances; the historical Brow, EYE, structure line and farm assemblies are returned for hiding."""
    d = CFG['equipment'][[e['id'] for e in CFG['equipment']].index('BROW-TRANSLATION')]['envelope']['translation_m']
    inst = []
    for nm in ('Assembly_FORWARD_SHIELD', 'Assembly_EYE'):
        o = bpy.data.objects.get(nm)
        if o and o.instance_collection:
            n = bpy.data.objects.new(nm.replace('Assembly_', 'WSI_TRANSLATED_'), None); n.instance_type = 'COLLECTION'; n.instance_collection = o.instance_collection
            n.matrix_world = Matrix.Translation((d, 0, 0)) @ o.matrix_world; inst.append(n)
    hide = [bpy.data.objects.get(n) for n in ('Assembly_FORWARD_SHIELD', 'Assembly_EYE', 'Assembly_STRUCTURE', 'Assembly_STORAGE')]
    return inst, [h for h in hide if h], d


# ---------------------------------------------------------------------------------------------------------------- main
def main():
    sc = bpy.context.scene; top = bpy.data.collections.new('WORK_WSI_WAYFARER_SYSTEMS_INTEGRATION'); sc.collection.children.link(top); top.color_tag = PINK
    C = {k: coll(f'WORK_WSI_{k}', top) for k in ('PRIMARY_STRUCTURE', 'LOAD_PATHS', 'ISSA_MACHINERY', 'PROPELLANT', 'THERMAL', 'ELECTRICAL', 'LOGISTICS_MAINTENANCE',
                                                 'STRUCTURAL_INTERFACES', 'CLEARANCE_REMOVAL_ENVELOPES', 'RESEARCH_ALTERNATIVES', 'FICTIONAL_REFERENCE',
                                                 'SECTION_LONGITUDINAL', 'SECTION_TRANSVERSE', 'TRANSLATED_BROW', 'CAMERAS')}
    structure(C['PRIMARY_STRUCTURE']); loadpath(C['LOAD_PATHS']); machinery(C['ISSA_MACHINERY']); propellant(C['PROPELLANT']); thermal(C['THERMAL'])
    electrical(C['ELECTRICAL']); logistics(C['LOGISTICS_MAINTENANCE']); interfaces(C['STRUCTURAL_INTERFACES']); envelopes(C['CLEARANCE_REMOVAL_ENVELOPES'])
    alternatives(C['RESEARCH_ALTERNATIVES']); fiction(C['FICTIONAL_REFERENCE']); sections(C['SECTION_LONGITUDINAL'], C['SECTION_TRANSVERSE'])
    inst, hide, d = production_replacements()
    for n in inst:
        C['TRANSLATED_BROW'].objects.link(n)
    for h in hide:
        h.hide_viewport = True; h.hide_render = True; h['wsi_hidden'] = 'replaced in the WSI views (translated Brow, PSA structure, WSI farm); not deleted'
    cams = dict(
        COMPLETE=cam(C['CAMERAS'], 'CAM_WSI_COMPLETE', (150.0, -300.0, 120.0), (20.0, 0, 0), 30),
        AFT=cam(C['CAMERAS'], 'CAM_WSI_AFT_THRUST', (-95.0, -40.0, 22.0), (-128.0, 0, 0), 28),
        HUB=cam(C['CAMERAS'], 'CAM_WSI_HUB_DECK', (125.0, -48.0, 22.0), (100.0, 0, 0), 26),
        FARM=cam(C['CAMERAS'], 'CAM_WSI_FARM', (230.0, -110.0, 70.0), (150.0, 0, 0), 30),
        LONG=cam(C['CAMERAS'], 'CAM_WSI_SECTION_LONG', (30.0, -500.0, 0.0), (30.0, 0, 0), 30, ortho=360.0),
        TRANS=cam(C['CAMERAS'], 'CAM_WSI_SECTION_X0', (60.0, 0.0, 0.0), (-200.0, 0, 0), 30, ortho=90.0))
    sc.camera = cams['COMPLETE']
    # view layers: one per review mode (collections excluded per mode)
    modes = {
        'WSI_01_COMPLETE': ['PRIMARY_STRUCTURE', 'ISSA_MACHINERY', 'PROPELLANT', 'THERMAL', 'ELECTRICAL', 'LOGISTICS_MAINTENANCE', 'TRANSLATED_BROW', 'CAMERAS'],
        'WSI_02_EXTERIOR': ['PROPELLANT', 'THERMAL', 'TRANSLATED_BROW', 'CAMERAS'],
        'WSI_03_PRIMARY_STRUCTURE': ['PRIMARY_STRUCTURE', 'STRUCTURAL_INTERFACES', 'CAMERAS'],
        'WSI_04_LOAD_PATHS': ['LOAD_PATHS', 'CAMERAS'],
        'WSI_05_ISSA_MACHINERY': ['ISSA_MACHINERY', 'STRUCTURAL_INTERFACES', 'CAMERAS'],
        'WSI_06_PROPELLANT': ['PROPELLANT', 'PRIMARY_STRUCTURE', 'CAMERAS'],
        'WSI_07_THERMAL': ['THERMAL', 'CAMERAS'],
        'WSI_08_ELECTRICAL': ['ELECTRICAL', 'ISSA_MACHINERY', 'CAMERAS'],
        'WSI_09_HABITATS': ['CAMERAS'],
        'WSI_10_LOGISTICS_MAINTENANCE': ['LOGISTICS_MAINTENANCE', 'CLEARANCE_REMOVAL_ENVELOPES', 'CAMERAS'],
        'WSI_11_STRUCTURAL_INTERFACES': ['STRUCTURAL_INTERFACES', 'PRIMARY_STRUCTURE', 'CAMERAS'],
        'WSI_12_CLEARANCE_ENVELOPES': ['CLEARANCE_REMOVAL_ENVELOPES', 'PRIMARY_STRUCTURE', 'CAMERAS'],
        'WSI_13_RESEARCH_ALTERNATIVES': ['RESEARCH_ALTERNATIVES', 'PROPELLANT', 'THERMAL', 'CAMERAS'],
        'WSI_14_FICTIONAL_REFERENCE': ['FICTIONAL_REFERENCE', 'ISSA_MACHINERY', 'THERMAL', 'CAMERAS'],
        'WSI_15_SECTION_LONGITUDINAL': ['SECTION_LONGITUDINAL', 'CAMERAS'],
        'WSI_16_SECTION_TRANSVERSE': ['SECTION_TRANSVERSE', 'CAMERAS']}
    base = sc.view_layers[0]
    for name, keep in modes.items():
        vl = sc.view_layers.new(name)
        for lc in vl.layer_collection.children:
            if lc.collection == top:
                for ch in lc.children:
                    ch.exclude = ch.collection.name.replace('WORK_WSI_', '') not in keep
            elif lc.collection.name == 'WF_WAYFARER_001':
                lc.exclude = name not in ('WSI_01_COMPLETE', 'WSI_02_EXTERIOR', 'WSI_09_HABITATS')   # production context only where it explains
    # the default layer shows the complete joint ship
    for lc in base.layer_collection.children:
        if lc.collection == top:
            for ch in lc.children:
                ch.exclude = ch.collection.name.replace('WORK_WSI_', '') not in modes['WSI_01_COMPLETE']
    try:
        sc.view_layers.active = base
    except Exception:  # noqa: BLE001
        pass
    if '--render' in sys.argv:
        sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.color_type = 'MATERIAL'; sc.render.resolution_x, sc.render.resolution_y = 1600, 900
        sc.render.image_settings.file_format = 'JPEG'; sc.world = sc.world or bpy.data.worlds.new('W'); sc.world.color = (0.02, 0.02, 0.03)
        sc.render.use_single_layer = True
        for vl_name, cname in (('WSI_01_COMPLETE', 'COMPLETE'), ('WSI_03_PRIMARY_STRUCTURE', 'AFT'), ('WSI_03_PRIMARY_STRUCTURE', 'HUB'), ('WSI_06_PROPELLANT', 'FARM'),
                               ('WSI_15_SECTION_LONGITUDINAL', 'LONG'), ('WSI_16_SECTION_TRANSVERSE', 'TRANS'), ('WSI_12_CLEARANCE_ENVELOPES', 'HUB'),
                               ('WSI_13_RESEARCH_ALTERNATIVES', 'AFT')):
            for v in sc.view_layers:
                v.use = v.name == vl_name
            sc.camera = cams[cname]; sc.render.filepath = str(RES/f'cam_wsi_{vl_name.lower()}_{cname.lower()}.jpg'); bpy.ops.render.render(write_still=True)
        for v in sc.view_layers:
            v.use = True
        sc.camera = cams['COMPLETE']
    try:
        bpy.ops.file.pack_libraries()
    except Exception as e:  # noqa: BLE001
        print('pack_libraries failed:', e)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT), compress=True, relative_remap=False, copy=True)
    print('SAVED', OUT, OUT.stat().st_size, 'translation', d)


main()
