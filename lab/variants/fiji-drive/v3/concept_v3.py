"""Fiji Drive v3 concept package (study helper, not the production model): builds CONCEPT_FIJI_V3.blend with the integrated drive IFD-1
on a truncated Wayfarer aft body, its overlays, and schematic layouts of the topology study, then renders the review views.

  /snap/bin/blender -b --factory-startup --python lab/variants/fiji-drive/v3/concept_v3.py -- [--no-render]

Colours: the 2026-11-01 functional standard (src/wayfarer/functional_colors.py); overlays (plasma, escape, protected zone) are helpers.
Numbers come from lab/variants/fiji-drive/v3/results/integrated.json (run integrated.py first).
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT/'src/wayfarer'))
import functional_colors as fc  # noqa: E402

ARGS = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
RES = json.loads((HERE/'results/integrated.json').read_text())
DP = RES['design_point']['central']
PAL = {k: v[1] for k, v in fc.PALETTE.items()}
OVER = {'PLASMA': (0.75, 0.95, 1.0, 0.35), 'ESCAPE': (1.0, 1.0, 0.85, 0.12), 'PROTECTED': (0.55, 1.0, 0.55, 0.18), 'FIELD': (0.85, 0.85, 1.0, 1.0),
        'TEXT': (0.05, 0.05, 0.05, 1.0), 'TEXT_W': (0.95, 0.95, 0.95, 1.0)}

bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene; SC.name = 'IFD1_INTEGRATED'
MATS = {}


def mat(key, rgba):
    if key in MATS:
        return MATS[key]
    m = bpy.data.materials.new(key); m.diffuse_color = rgba; m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = rgba; b.inputs['Alpha'].default_value = rgba[3]
    if rgba[3] < 1:
        m.blend_method = 'BLEND' if hasattr(m, 'blend_method') else None
    MATS[key] = m; return m


def coll(name, parent=None, tag='NONE'):
    c = bpy.data.collections.new(name); (parent or SC.collection).children.link(c); c.color_tag = tag; return c


def obj_from_bm(name, bm, col, func=None, rgba=None):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); col.objects.link(o)
    rgba = rgba or (PAL[func] if func in PAL else OVER[func])
    o.color = rgba; me.materials.append(mat(func or name, rgba)); o['wf_function'] = func or 'overlay'
    return o


def ring(name, x0, x1, r0, r1, col, func, a0=0.0, a1=2*math.pi, cy=0.0, cz=0.0, seg=64):
    """Annular sector between radii r0..r1 along X x0..x1 (a0..a1 about +X from +Y)."""
    bm = bmesh.new(); full = abs(a1-a0-2*math.pi) < 1e-6; n = seg if full else max(4, int(seg*(a1-a0)/(2*math.pi)))
    rows = []
    for i in range(n+(0 if full else 1)):
        a = a0+(a1-a0)*i/n
        c, s_ = math.cos(a), math.sin(a)
        rows.append([bm.verts.new((x, cy+r*c, cz+r*s_)) for x, r in ((x0, r0), (x1, r0), (x1, r1), (x0, r1))])
    m = len(rows)
    for i in range(m if full else m-1):
        A, B = rows[i], rows[(i+1) % m]
        for k in range(4):
            bm.faces.new((A[k], B[k], B[(k+1) % 4], A[(k+1) % 4]))
    if not full:
        bm.faces.new(rows[0][::-1]); bm.faces.new(rows[-1])
    return obj_from_bm(name, bm, col, func)


def tube(name, pts, r, col, func, seg=12):
    bm = bmesh.new(); prev = None
    for i, p in enumerate(pts):
        p = Vector(p); d = (Vector(pts[min(i+1, len(pts)-1)])-Vector(pts[max(i-1, 0)])).normalized()
        u = d.orthogonal().normalized(); v = d.cross(u)
        cur = [bm.verts.new(p+r*(math.cos(2*math.pi*k/seg)*u+math.sin(2*math.pi*k/seg)*v)) for k in range(seg)]
        if prev:
            for k in range(seg):
                bm.faces.new((prev[k], prev[(k+1) % seg], cur[(k+1) % seg], cur[k]))
        prev = cur
    return obj_from_bm(name, bm, col, func)


def box(name, c, size, col, func):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts); bmesh.ops.translate(bm, vec=c, verts=bm.verts)
    return obj_from_bm(name, bm, col, func)


def plane_blade(name, phi, r0, r1, x0, x1, col, func, t=0.3):
    bm = bmesh.new(); u = Vector((0, math.cos(phi), math.sin(phi))); n = Vector((0, -math.sin(phi), math.cos(phi)))
    vs = [bm.verts.new(Vector((x, 0, 0))+r*u+s*t/2*n) for s in (-1, 1) for x, r in ((x0, r0), (x1, r0), (x1, r1), (x0, r1))]
    for f in ((0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
        bm.faces.new([vs[i] for i in f])
    return obj_from_bm(name, bm, col, func)


def cone(name, x0, r0, x1, r1, col, func, seg=64):
    bm = bmesh.new(); A = [bm.verts.new((x0, r0*math.cos(2*math.pi*k/seg), r0*math.sin(2*math.pi*k/seg))) for k in range(seg)]
    B = [bm.verts.new((x1, r1*math.cos(2*math.pi*k/seg), r1*math.sin(2*math.pi*k/seg))) for k in range(seg)]
    for k in range(seg):
        bm.faces.new((A[k], A[(k+1) % seg], B[(k+1) % seg], B[k]))
    return obj_from_bm(name, bm, col, func)


def text(name, body, loc, rot, size, col, rgba=OVER['TEXT']):
    cu = bpy.data.curves.new(name, 'FONT'); cu.body = body; cu.size = size; cu.align_x = 'CENTER'
    o = bpy.data.objects.new(name, cu); o.location = loc; o.rotation_euler = rot; col.objects.link(o); o.color = rgba
    cu.materials.append(mat('TEXT_'+name, rgba)); return o

# ---------------------------------------------------------------- IFD-1 integrated drive -------------------------------------------------
R_F, R_O, L = DP['R_face_m'], DP['R_out_m'], DP['L_m']
XF, XA = DP['x_plasma'][1], DP['x_plasma'][0]          # forward / aft plasma ends
XS, RS = DP['shield_x'], DP['shield_radius_m']
NCOIL = 16; PITCH = L/NCOIL; W = PITCH*0.25
TOP = coll('WORK_FIJI_V3', tag='COLOR_07')
C = {k: coll(f'WORK_FIJI_V3_{k}', TOP, fc.PALETTE[f][2] if f in fc.PALETTE else 'NONE') for k, f in (
    ('SHIP_CONTEXT', 'STRUCTURE'), ('DRIVE_HARDWARE', 'MAIN_PROPULSION'), ('HOT_LOOP', 'HOT_RADIATOR'), ('PROPELLANT_FUEL', 'HYDROGEN'),
    ('POWER_CONTROL', 'POWER'), ('OVERLAYS', 'NONE'), ('LABELS', 'NONE'))}


def build_drive(cut=None, suffix=''):
    a0, a1 = (cut if cut else (0.0, 2*math.pi))
    # ship context (truncated at X -60): hull aft body and the three blades
    ring('HULL_AFT_BODY'+suffix, -134.0, -60.0, 6.9, 7.2, C['SHIP_CONTEXT'], 'STRUCTURE', a0, a1)
    if not cut:
        for j, ph in enumerate((30, 150, 270)):
            plane_blade(f'BLADE_{j+1}_TRUNCATED', math.radians(ph), 6.5, 37.0, -133.25, -60.0, C['SHIP_CONTEXT'], 'HOT_RADIATOR', 0.3)
    # shadow shield (layered: W hot face, B4C, LiH, steel back) on a ring frame tied to the hull primary frame
    lay = [('W', 0.10), ('B4C', 0.30), ('LiH', 0.50), ('STEEL', 0.10)]; x = XS
    for nm, tk in lay:
        ring(f'SHADOW_SHIELD_{nm}'+suffix, x-tk if nm == 'W' else x, x if nm == 'W' else x+tk, 0.6, RS, C['DRIVE_HARDWARE'], 'MAIN_PROPULSION', a0, a1)
        if nm == 'W':
            x0w = x-tk
        else:
            x += tk
    ring('SHIELD_COOLING_HEADER'+suffix, XS-0.15, XS+0.2, RS, RS+0.25, C['HOT_LOOP'], 'HOT_RADIATOR', a0, a1)
    # forward choke and aft mirror (stronger end coils), open-cage central coils with armour (red, heat-pipe cooled) and shield + winding
    xs = [XF-PITCH*(k+0.5) for k in range(NCOIL)]
    ring('CHOKE_FWD'+suffix, XF-0.6, XF+0.6, R_F-2.2, R_O-1.0, C['DRIVE_HARDWARE'], 'MAIN_PROPULSION', a0, a1)
    ring('CHOKE_FWD_ARMOUR'+suffix, XF-0.6, XF+0.6, R_F-2.3, R_F-2.2, C['HOT_LOOP'], 'HOT_RADIATOR', a0, a1)
    for k, xc in enumerate(xs):
        ring(f'COIL_{k+1:02}_ARMOUR'+suffix, xc-W/2, xc+W/2, R_F, R_F+0.1, C['HOT_LOOP'], 'HOT_RADIATOR', a0, a1)
        ring(f'COIL_{k+1:02}_SHIELD_WINDING'+suffix, xc-W/2, xc+W/2, R_F+0.1, R_O, C['DRIVE_HARDWARE'], 'MAIN_PROPULSION', a0, a1)
        ring(f'COIL_{k+1:02}_HEAT_PIPE_RING'+suffix, xc-0.15, xc+0.15, R_O, R_O+0.2, C['HOT_LOOP'], 'HOT_RADIATOR', a0, a1)
    ring('MIRROR_AFT'+suffix, XA-0.6, XA+0.6, R_F-1.6, R_O-0.6, C['DRIVE_HARDWARE'], 'MAIN_PROPULSION', a0, a1)
    ring('MIRROR_AFT_ARMOUR'+suffix, XA-0.6, XA+0.6, R_F-1.7, R_F-1.6, C['HOT_LOOP'], 'HOT_RADIATOR', a0, a1)
    # one axial magnetic nozzle: six flaring coils, four Fiji trim sectors each (gaps show the sectors)
    for i in range(6):
        xn = XA-2.0-i*2.6; rb = 3.2+0.9*i**1.25
        for q in range(4):
            qa0 = math.radians(90*q+4); qa1 = math.radians(90*q+86)
            if cut and not (qa1 <= a0 or qa0 >= a1):
                qa0, qa1 = max(qa0, a0), min(qa1, a1)
                if qa1-qa0 < 0.05:
                    continue
            ring(f'NOZZLE_COIL_{i+1}_SECTOR_{q+1}'+suffix, xn-0.35, xn+0.35, rb, rb+0.55, C['DRIVE_HARDWARE'], 'MAIN_PROPULSION', qa0, qa1, seg=48)
    # strongback (six bars) carrying coil thrust forward into the shield frame and the hull primary frames
    for j in range(6):
        ph = math.radians(60*j+15)
        if cut and a0 < ph < a1:
            continue
        rr = R_O+0.45
        tube(f'STRONGBACK_{j+1}'+suffix, [(XA-14.0, rr*math.cos(ph), rr*math.sin(ph)), (XA, rr*math.cos(ph), rr*math.sin(ph)),
                                          (XF, rr*math.cos(ph), rr*math.sin(ph)), (XS+0.6, (RS+0.3)*math.cos(ph), (RS+0.3)*math.sin(ph)),
                                          (-128.0, 7.0*math.cos(ph), 7.0*math.sin(ph))], 0.35, C['SHIP_CONTEXT'], 'STRUCTURE')
    # hot loop: three Li heat-pipe trunks from the coil rings forward to the blade roots (blade planes 30/150/270)
    for j, ph in enumerate((30, 150, 270)):
        p = math.radians(ph)
        if cut and a0 < p < a1:
            continue
        rr = R_O+0.1
        tube(f'HOT_TRUNK_{j+1}'+suffix, [(XA, rr*math.cos(p), rr*math.sin(p)), (XF, rr*math.cos(p), rr*math.sin(p)),
                                        (XS+1.5, (RS+0.9)*math.cos(p), (RS+0.9)*math.sin(p)), (-130.0, 7.6*math.cos(p), 7.6*math.sin(p)),
                                        (-120.0, 7.6*math.cos(p), 7.6*math.sin(p))], 0.45, C['HOT_LOOP'], 'HOT_RADIATOR')
    # propellant and fuel: H2 to the forward gas box and to the nozzle mass-loading ring; D and He-3 to the axial fueller
    tube('H2_FEED_AXIAL'+suffix, [(-128.0, 0.0, 0.0), (XS-1.2, 0.0, 0.0)], 0.22, C['PROPELLANT_FUEL'], 'HYDROGEN')
    tube('H2_GAS_BOX_RING'+suffix, [(XF+0.9, 2.2*math.cos(t), 2.2*math.sin(t)) for t in [2*math.pi*k/40 for k in range(41)]], 0.12, C['PROPELLANT_FUEL'], 'HYDROGEN')
    if not cut:
        tube('H2_NOZZLE_LINE', [(XS+1.0, 0.0, RS+1.6), (XA-1.0, 0.0, R_O+1.6), (XA-3.0, 0.0, 4.5)], 0.15, C['PROPELLANT_FUEL'], 'HYDROGEN')
        tube('H2_NOZZLE_MASS_LOADING_RING', [(XA-3.0, 4.3*math.cos(t), 4.3*math.sin(t)) for t in [2*math.pi*k/40 for k in range(41)]], 0.12, C['PROPELLANT_FUEL'], 'HYDROGEN')
    tube('D_FEED'+suffix, [(-128.0, 0.5, 0.3), (XS-1.2, 0.5, 0.3), (XF+0.4, 0.35, 0.2)], 0.08, C['PROPELLANT_FUEL'], 'DEUTERIUM')
    tube('HE3_FEED'+suffix, [(-128.0, -0.5, 0.3), (XS-1.2, -0.5, 0.3), (XF+0.4, -0.35, 0.2)], 0.08, C['PROPELLANT_FUEL'], 'HELIUM3')
    ring('AXIAL_FUELLER'+suffix, XF+0.2, XF+1.2, 0.15, 0.7, C['PROPELLANT_FUEL'], 'DEUTERIUM', a0, a1)
    # power and control: startup bank feed and coil power bus, diagnostics boxes
    tube('COIL_POWER_BUS'+suffix, [(-126.0, 0.0, -7.6), (XS+0.6, 0.0, -(RS+0.6)), (XF, 0.0, -(R_O+1.0)), (XA, 0.0, -(R_O+1.0))], 0.25, C['POWER_CONTROL'], 'POWER')
    for k in range(0, NCOIL, 4):
        box(f'COIL_POWER_UNIT_{k+1:02}'+suffix, (xs[k], 0.0, -(R_O+1.0)), (1.2, 0.9, 0.7), C['POWER_CONTROL'], 'POWER')
    # overlays: plasma column, protected (shadowed) zone, radial escape band
    ring('OVERLAY_PLASMA_COLUMN'+suffix, XA, XF, 0.0, DP['r_plasma_m'], C['OVERLAYS'], 'PLASMA', a0, a1)
    if not cut:
        cone('OVERLAY_PROTECTED_ZONE', XS+1.0, RS, -60.0, RS+(RS+0.0)*((-60.0-XS)/(XS-XA))*1.0, C['OVERLAYS'], 'PROTECTED')
        for k in range(0, NCOIL-1, 2):
            xg = XF-PITCH*(k+1)
            ring(f'OVERLAY_ESCAPE_GAP_{k}', xg-(PITCH-W)/2*0.9, xg+(PITCH-W)/2*0.9, R_O+0.6, R_O+9.0, C['OVERLAYS'], 'ESCAPE')
        cone('OVERLAY_AFT_ESCAPE', XA-16.0, 6.0, XA-40.0, 30.0, C['OVERLAYS'], 'ESCAPE')


build_drive()
# labels for the side and cutaway views
rot_side = (math.radians(90), 0, 0)
lab = [('SHADOW SHIELD  W | B4C | LiH | steel  (r %.1f m)' % RS, (XS, 0, RS+3.0)),
       ('OPEN-CAGE COILS: %d rings, 25%% cover\nW armour on Li heat pipes, 1.4 m neutron shield' % NCOIL, ((XF+XA)/2, 0, R_O+6.5)),
       ('PLASMA  r %.0f m x %.0f m  (%.2f TW fusion)' % (DP['r_plasma_m'], L, DP['P_fus_TW']), ((XF+XA)/2, 0, 0.0)),
       ('ONE AXIAL NOZZLE\n4 Fiji trim sectors per coil', (XA-9.0, 0, 13.0)), ('HOT LOOP TRUNKS\nto blade roots (1800 K)', (-125.0, 0, 13.0)),
       ('RADIAL ESCAPE THROUGH COIL GAPS (72 %)', ((XF+XA)/2, 0, R_O+11.0)), ('PROTECTED ZONE (shield shadow)', (-95.0, 0, 9.5))]
for i, (b, p) in enumerate(lab):
    text(f'LABEL_SIDE_{i}', b, p, rot_side, 1.4, C['LABELS'])

# ---------------------------------------------------------------- cutaway scene ---------------------------------------------------------
cut_sc = bpy.data.scenes.new('IFD1_CUTAWAY')
for k in list(C):
    C[k+'_SAVE'] = C[k]
cut_top = bpy.data.collections.new('WORK_FIJI_V3_CUTAWAY'); cut_sc.collection.children.link(cut_top); cut_top.color_tag = 'COLOR_07'
C = {k: (lambda n: (lambda c: (cut_top.children.link(c), c)[1])(bpy.data.collections.new('WORK_FIJI_V3_CUT_'+n)))(k) for k in
     ('SHIP_CONTEXT', 'DRIVE_HARDWARE', 'HOT_LOOP', 'PROPELLANT_FUEL', 'POWER_CONTROL', 'OVERLAYS', 'LABELS')}
build_drive(cut=(math.radians(-60), math.radians(120)), suffix='_CUT')

# ---------------------------------------------------------------- topology layouts --------------------------------------------------------
topo_sc = bpy.data.scenes.new('TOPOLOGY_LAYOUTS')
TT = bpy.data.collections.new('WORK_FIJI_V3_TOPOLOGIES'); topo_sc.collection.children.link(TT); TT.color_tag = 'COLOR_07'
EV = RES['evaluation']['central']['W_armour_Li_heat_pipe_1900K']
TOPO_COLLS = []
order = ['F0_1x4_aft', 'F1_2x4', 'F2_4x4', 'F3_6x6', 'F4_8x8', 'F5_1x1']
for i, key in enumerate(order):
    t = RES['topologies'][key]; mc = RES['monte_carlo'][key]; ev = EV[key]
    c = bpy.data.collections.new(f'TOPO_{key}'); TT.children.link(c)
    TOPO_COLLS.append((c, i))
    zo = -(i % 3)*62.0; xo = (i//3)*190.0; Lt = 30.0; xf, xa = -139.0, -169.0
    # side layout (XZ at Y=0) and aft layout (YZ), the aft layout shifted forward to X +20
    ring(f'{key}_HULL_END', -134.0, -110.0, 6.9, 7.2, c, 'STRUCTURE').location = (0, 0, zo)
    shield = ring(f'{key}_SHADOW_SHIELD', -137.0, -136.0, 0.3, mc['shield_radius_m'], c, 'MAIN_PROPULSION'); shield.location = (0, 0, zo)
    for m, (py, pz) in enumerate(t['pos']):
        for k in range(8):
            xc = xf-(k+0.5)*Lt/8
            o = ring(f'{key}_M{m+1}_COIL_{k+1}', xc-0.45, xc+0.45, max(0.2, t['R_face']), t['R_out'], c, 'MAIN_PROPULSION', cy=py, cz=pz, seg=40); o.location = (0, 0, zo)
            o2 = ring(f'{key}_M{m+1}_ARMOUR_{k+1}', xc-0.45, xc+0.45, max(0.1, t['R_face']-0.1), max(0.2, t['R_face']), c, 'HOT_RADIATOR', cy=py, cz=pz, seg=40); o2.location = (0, 0, zo)
        if t['r_plasma'] > 0:
            ring(f'{key}_M{m+1}_PLASMA', xa, xf, 0.0, t['r_plasma'], c, 'PLASMA', cy=py, cz=pz, seg=32).location = (0, 0, zo)
    noz = t['nozzles']; npos = t['pos'] if noz == t['reactors'] else ([(0.0, 0.0)] if noz == 1 else [(2.6*math.cos(math.radians(45+90*q)), 2.6*math.sin(math.radians(45+90*q))) for q in range(4)])
    if key == 'F1_2x4':
        npos = [(py+sy*1.2, pz) for (py, pz) in t['pos'] for sy in (-1, 1)]
    for q, (py, pz) in enumerate(npos):
        rn = 1.4 if noz > 1 else 3.0
        ring(f'{key}_NOZZLE_{q+1}', xa-8.0, xa-1.0, rn, rn+0.4, c, 'MAIN_PROPULSION', cy=py, cz=pz, seg=32).location = (0, 0, zo)
    # aft-view copy: rotate the module ring layout into the YZ plane at X = +20 (seen from the side camera as an end view)
    for m, (py, pz) in enumerate(t['pos']):
        o = ring(f'{key}_AFTVIEW_M{m+1}', -0.3, 0.3, max(0.2, t['R_face']), t['R_out'], c, 'MAIN_PROPULSION', seg=48)
        o.rotation_euler = (0, 0, math.radians(90)); o.location = (-90.0+py, 0, zo+pz)
        if t['r_plasma'] > 0:
            p_ = ring(f'{key}_AFTVIEW_P{m+1}', -0.2, 0.2, 0.0, t['r_plasma'], c, 'PLASMA', seg=32); p_.rotation_euler = (0, 0, math.radians(90)); p_.location = (-90.0+py, 0, zo+pz)
    hv = ring(f'{key}_AFTVIEW_HULL', -0.25, 0.25, 6.9, 7.2, c, 'STRUCTURE'); hv.rotation_euler = (0, 0, math.radians(90)); hv.location = (-90.0, 0, zo)
    for j, ph in enumerate((30, 150, 270)):
        p = math.radians(ph); b = tube(f'{key}_AFTVIEW_BLADE_{j+1}', [(-90.0+6.5*math.cos(p), 0, zo+6.5*math.sin(p)), (-90.0+16.0*math.cos(p), 0, zo+16.0*math.sin(p))], 0.25, c, 'HOT_RADIATOR')
    if ev.get('feasible'):
        info = ('%s  %d reactor(s) x %d nozzle(s)\nP max %.3f TW (%s)\nhardware heat %.1f GW, neighbour share %.2f\ndrive mass ~%.0f t, one module out: %.0f %% thrust left' % (
            key, t['reactors'], t['nozzles'], ev['P_fus_max_TW'], ev['binding'], ev['permanent_heat_GW'], mc['fractions'].get('neighbour', 0.0),
            ev['mass_t']['total_nanocomposite'], 100*ev['one_module_out']['thrust_left']))
    else:
        info = '%s  %d x %d\nINFEASIBLE: %s' % (key, t['reactors'], t['nozzles'], ev['reason'])
    text(f'{key}_LABEL', info, (-120.0, 0, zo+22.0), rot_side, 2.6, c)
    text(f'{key}_SIDE_TAG', 'side', (-150.0, 0, zo-17.0), rot_side, 2.0, c)
    text(f'{key}_AFT_TAG', 'aft view', (-90.0, 0, zo-17.0), rot_side, 2.0, c)
    for o in c.objects:
        o.location.x += xo

# ---------------------------------------------------------------- cameras, render settings, legend -------------------------------------
def camera(name, loc, target, lens=35, ortho=None, scenes=()):
    cd = bpy.data.cameras.new(name)
    if ortho:
        cd.type = 'ORTHO'; cd.ortho_scale = ortho
    else:
        cd.lens = lens
    cd.clip_end = 5000
    o = bpy.data.objects.new(name, cd); o.location = loc
    d = Vector(target)-Vector(loc); o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    for sc in scenes:
        sc.collection.objects.link(o)
    o['render_scenes'] = [s.name for s in scenes]; return o


cams = [camera('CAM_V3_SIDE_OVERLAY', (-163, -160, 2), (-163, 0, 2), ortho=118, scenes=[SC]),
        camera('CAM_V3_WHOLE', (-60, -150, 90), (-150, 0, 0), 32, scenes=[SC]),
        camera('CAM_V3_AFT', (XA-120, 0, 0), (XA, 0, 0), ortho=44, scenes=[SC]),
        camera('CAM_V3_CUTAWAY', (-150, -55, 32), (-168, 0, 0), 28, scenes=[cut_sc]),
        camera('CAM_V3_TOPOLOGIES', (-30, -400, -58), (-30, 0, -58), ortho=385, scenes=[topo_sc])]
for sc in (SC, cut_sc, topo_sc):
    sc.render.engine = 'BLENDER_WORKBENCH'; sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'OBJECT'
    sh.show_cavity = True; sh.show_object_outline = True; sh.background_type = 'VIEWPORT'; sh.background_color = (0.13, 0.14, 0.16)
    sc.view_settings.view_transform = 'Standard'; sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    sc.render.film_transparent = False; sh.show_xray = False
cams[2].data.clip_start = 120.0+DP['L_m']/2; SC.camera = cams[0]; cut_sc.camera = cams[3]; topo_sc.camera = cams[4]
txt = bpy.data.texts.new('README_FIJI_V3')
txt.write('Fiji Drive v3 concept (study file, not the production model). Scenes: IFD1_INTEGRATED (side overlay, whole-aft and aft cameras), '
          'IFD1_CUTAWAY, TOPOLOGY_LAYOUTS. Colours follow the 2026-11-01 functional standard: drive hardware MAIN_PROPULSION, armour, heat '
          'pipes and trunks HOT_RADIATOR, H2 HYDROGEN, D DEUTERIUM, He-3 HELIUM3, power POWER, structure STRUCTURE. Light translucent '
          'objects are overlays (plasma, escape bands, protected zone). Numbers: lab/variants/fiji-drive/v3/results/integrated.json, REPORT.md.\n')
for area in []:
    pass
out = HERE/'CONCEPT_FIJI_V3.blend'
bpy.ops.file.pack_all() if bpy.data.images else None
bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
print('WF_SAVED', out)

if '--no-render' not in ARGS:
    rd = Path(ARGS[ARGS.index('--out')+1]) if '--out' in ARGS else HERE/'renders'
    rd.mkdir(parents=True, exist_ok=True)
    for cam in cams:
        for sn in cam['render_scenes']:
            sc = bpy.data.scenes[sn]; sc.camera = cam
            sc.render.filepath = str(rd/f'{cam.name}.png')
            bpy.ops.render.render(write_still=True, scene=sc.name)
            print('WF_RENDER', sc.render.filepath)
