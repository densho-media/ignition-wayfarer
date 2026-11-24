"""Thermal review file for the Vertex engine (work, noncanonical; owner brief 2026-11-23 14:18Z).

  /snap/bin/blender -b --factory-startup --python lab/studies/vertex-compact-engine/vertex-thermal/blender_thermal.py [-- --no-render]

Opens showing the approved engine (assets/wayfarer/components/WF_VERTEX_ENGINE.blend, appended and made local, untouched) with the
thermal study's hardware in pink WORK_THERMAL_* collections, all parametric from results/thermal.json (thermal.py geometry):
  WORK_THERMAL_MIRRORS_A   Pt-coated burn faces on the armour shoes and LiH noses (strategy A; reflects 1.5e-5 of what strikes)
  WORK_THERMAL_MIRRORS_B   source-aligned blade fairings on the cage longerons (strategy B; the one strategy that cuts heat)
  WORK_THERMAL_MIRRORS_D   source-pointing grazing liners in front of L3/L4 (strategy D; drawn to show where it would sit: no benefit)
  WORK_THERMAL_BLANKET_C   layered full-silhouette blankets on every coil (strategy C), cut away 40 deg to show the layers
  WORK_THERMAL_HOT         lithium circuit additions: armour channel jackets, shield ring header, EM pumps, heat exchanger, link to the HOT radiator
  WORK_THERMAL_CRYO        80 K screens, refrigerator, its feed and its LOW-radiator rejection line, quench dump lines
  WORK_THERMAL_SECTION     a longitudinal half-section in the dorsal plane (+Z): every coil with its blanket layers, winding, screen,
                           vessel and drawn shoe, the shield face, and rays from the burn point (scene SECTION)
  WORK_THERMAL_LABELS      labels
Every number is the study's (SIMULATED/CALCULATED), never a claim that the hardware solves the problem: see PROBLEMS.md.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
import vertex_engine as ve  # noqa: E402

RENDER = '--no-render' not in sys.argv
D = json.loads((HERE / 'results' / 'thermal.json').read_text())
GEO = D['geometry']
PINK = 'COLOR_07'
BURN = -18.8


def mat(name, rgba, emit=0.0, alpha=1.0, metal=0.0, rough=0.5):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (rgba[0], rgba[1], rgba[2], alpha); m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*rgba[:3], 1.0); b.inputs['Metallic'].default_value = metal; b.inputs['Roughness'].default_value = rough
    if emit:
        b.inputs['Emission Color'].default_value = (*rgba[:3], 1.0); b.inputs['Emission Strength'].default_value = emit
    if alpha < 1.0:
        b.inputs['Alpha'].default_value = alpha
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            m.blend_method = 'BLEND'
    return m


bpy.ops.wm.read_factory_settings(use_empty=True)
M = dict(A=mat('WORK_THERMAL_MIRROR_A_PT', (0.80, 0.78, 0.92), metal=1.0, rough=0.08),
         B=mat('WORK_THERMAL_MIRROR_B_BLADE', (0.45, 0.70, 0.98), emit=0.5, metal=0.6, rough=0.2),
         D=mat('WORK_THERMAL_MIRROR_D_LINER', (0.95, 0.85, 0.45), metal=1.0, rough=0.1, alpha=0.45),
         hot=mat('WORK_THERMAL_HOT_LITHIUM', (1.0, 0.45, 0.12), emit=2.5, metal=0.4),
         hx=mat('WORK_THERMAL_HOT_HX', (0.75, 0.42, 0.20), metal=0.7, rough=0.35),
         cryo=mat('WORK_THERMAL_CRYO', (0.25, 0.65, 1.0), emit=1.5, metal=0.3),
         screen=mat('WORK_THERMAL_CRYO_80K_SCREEN', (0.85, 0.50, 0.30), metal=1.0, rough=0.25),
         quench=mat('WORK_THERMAL_QUENCH', (0.95, 0.85, 0.2), emit=1.5),
         label=mat('WORK_THERMAL_LABEL', (0.95, 0.95, 1.0), emit=4.0),
         ray=mat('WORK_THERMAL_RAY_SIM', (1.0, 0.9, 0.5), emit=6.0),
         burn=mat('WORK_THERMAL_BURN_POINT', (0.75, 0.88, 1.0), emit=40.0),
         winding=mat('WORK_THERMAL_SECTION_WINDING', (0.75, 0.45, 0.20), metal=0.6),
         vessel=mat('WORK_THERMAL_SECTION_VESSEL', (0.55, 0.57, 0.60), metal=0.7),
         shoe=mat('WORK_THERMAL_SECTION_DRAWN_SHOE', (0.20, 0.19, 0.18), metal=0.8),
         sub=mat('WORK_THERMAL_MIRROR_SUBSTRATE', (0.30, 0.28, 0.30), metal=0.6, rough=0.4),
         blade=mat('WORK_THERMAL_BLADE_CFC', (0.45, 0.70, 0.98), emit=0.5, metal=0.6, rough=0.2),
         edge=mat('WORK_THERMAL_BLADE_EDGE', (0.95, 0.55, 0.25), emit=1.2, metal=0.5),
         root=mat('WORK_THERMAL_BLADE_ROOT', (0.35, 0.37, 0.40), metal=0.7, rough=0.4),
         ret=mat('WORK_THERMAL_HOT_RETURN', (0.85, 0.20, 0.06), emit=2.0, metal=0.4),
         warm=mat('WORK_THERMAL_WARM_NAK', (0.95, 0.80, 0.20), emit=1.2, metal=0.4),
         service=mat('WORK_THERMAL_SERVICE', (0.15, 0.85, 0.55), emit=0.8, metal=0.3))
LAYER_COL = {'CFC sacrificial face': (0.08, 0.08, 0.09), 'W/CFC heat sink with lithium channels': (0.45, 0.30, 0.22),
             'W/B4C shield': (0.33, 0.30, 0.26), 'LiH moderator': (0.92, 0.92, 0.88), 'Vacuum gap and polished screen': (0.75, 0.78, 0.82),
             '80 K screen (Cu, cooled)': (0.85, 0.50, 0.30), 'MLI': (0.90, 0.75, 0.30)}
LM = {k: mat('WORK_THERMAL_C_' + k.split(' ')[0].replace('/', '_').upper() + f'_{i}', v, rough=0.6, metal=0.3 if 'Cu' in k or 'MLI' in k else 0.0,
             alpha=0.35 if 'gap' in k.lower() else 1.0) for i, (k, v) in enumerate(LAYER_COL.items())}


def coll(name, parent, tag=PINK):
    c = bpy.data.collections.new(name); parent.children.link(c); c.color_tag = tag
    return c


def obj(name, vs, fs, c, m):
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in vs], [], [tuple(f) for f in fs]); me.update()
    o = bpy.data.objects.new(name, me); c.objects.link(o); me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = True
    return o


def ribbon(a, b):
    vs = [tuple(p) for p in a] + [tuple(p) for p in b]; n = len(a)
    return vs, [(i, i + 1, n + i + 1, n + i) for i in range(n - 1)]


def mesh_of(g):
    k = g['kind']
    if k == 'torus':
        return ve.torus_mesh(g['x'], g['R'], g['a'], tuple(g['arc']) if g.get('arc') else None, 64, 12)
    if k == 'tube':
        return ve.tube_mesh(g['points'], g['radius'], 8)
    if k == 'box':
        return ve.box_mesh(g['center'], g['size'], g['az'])
    if k == 'revolve':
        return ve._revolve([tuple(p) for p in g['profile']], 72, g.get('closed', False), tuple(g['arc']) if g.get('arc') and g['arc'] != [0.0, 360.0] else None)
    if k == 'ribbon':
        return ribbon(g['a'], g['b'])
    raise ValueError(k)


def text(name, body, loc, size, c, rot=(math.pi / 2, 0, 0), m=None):
    cu = bpy.data.curves.new(name, 'FONT'); cu.body = body; cu.size = size; cu.align_x = 'LEFT'
    o = bpy.data.objects.new(name, cu); c.objects.link(o); cu.materials.append(m or M['label']); o.location = loc; o.rotation_euler = rot
    return o


def camera(name, loc, target, c, ortho=None, lens=35):
    cd = bpy.data.cameras.new(name); cd.clip_end = 5e3; cd.clip_start = 0.1
    if ortho:
        cd.type = 'ORTHO'; cd.ortho_scale = ortho
    else:
        cd.lens = lens
    o = bpy.data.objects.new(name, cd); c.objects.link(o); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def make_all_local():
    for _ in range(5):
        n = 0
        for attr in ('collections', 'objects', 'meshes', 'curves', 'materials', 'node_groups', 'images', 'texts', 'lights', 'cameras', 'fonts', 'worlds'):
            for idb in list(getattr(bpy.data, attr)):
                if idb.library is not None:
                    try:
                        idb.make_local(); n += 1
                    except Exception:
                        pass
        if n == 0:
            break
    for lib in list(bpy.data.libraries):
        try:
            bpy.data.libraries.remove(lib)
        except Exception:
            pass


scene = bpy.context.scene; scene.name = 'THERMAL'
with bpy.data.libraries.load(str(ROOT / 'assets/wayfarer/components/WF_VERTEX_ENGINE.blend'), link=False) as (src, dst):
    dst.collections = ['WF_VERTEX_ENGINE']
eng = dst.collections[0]; scene.collection.children.link(eng); make_all_local()
for c in bpy.data.collections:
    if c.name in ('VTX_VISUAL_EFFECTS', 'REVIEW_VERTEX_ENGINE'):
        c.hide_render = True; c.hide_viewport = True
top = coll('WORK_THERMAL', scene.collection)
C = {k: coll(f'WORK_THERMAL_{k}', top) for k in ('MIRRORS_A', 'BLADES', 'MIRRORS_D', 'BLANKET_THIN', 'BLANKET_C_ARCHIVED', 'HOT', 'WARM', 'CRYO',
                                                  'SERVICE', 'LABELS')}
LAYER = dict(mirror_A='MIRRORS_A', mirror_B='BLADES', blades='BLADES', mirror_D='MIRRORS_D', blanket_C='BLANKET_C_ARCHIVED', blanket_thin='BLANKET_THIN',
             hot='HOT', warm='WARM', cryo='CRYO', cryo_quench='CRYO', service='SERVICE')
C['BLANKET_C_ARCHIVED'].hide_viewport = True; C['BLANKET_C_ARCHIVED'].hide_render = True
for i, g in enumerate(GEO):
    vs, fs = mesh_of(g)
    if g['layer'] in ('blanket_C', 'blanket_thin'):
        m = LM[g['layer_name']]
    elif g['layer'] == 'blades':
        m = dict(EDGE=M['edge'], ROOT=M['root']).get(g['comp'], M['blade'])
    elif g['layer'] == 'hot':
        m = M['hx'] if g['kind'] == 'box' else M['ret'] if g['comp'].endswith('_R') else M['hot']
    else:
        m = dict(mirror_A=M['sub'] if g['comp'].endswith('_SUB') else M['A'], mirror_B=M['B'], mirror_D=M['root'] if g['comp'] == 'SUPPORT' else M['D'],
                 cryo_quench=M['quench'], warm=M['warm'], service=M['service'],
                 cryo=M['screen'] if 'screen' in g.get('note', '') else M['cryo'])[g['layer']]
    o = obj(f'WORK_THERMAL_{g["layer"]}_{g["comp"]}_{i:03}', vs, fs, C[LAYER[g['layer']]], m)
    o['wf_note'] = g.get('note', g.get('layer_name', '')); o['wf_status'] = 'WORK / PROTOTYPE (thermal study, not canon)'
# burn point
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.18, location=(BURN, 0, 0)); bp = bpy.context.object; bp.name = 'WORK_THERMAL_BURN_POINT'
for c_ in bp.users_collection:
    c_.objects.unlink(bp)
C['LABELS'].objects.link(bp); bp.data.materials.append(M['burn'])

# ---------- longitudinal half-section (dorsal plane) ----------
SCN = bpy.data.scenes.new('SECTION')
SEC = coll('WORK_THERMAL_SECTION', SCN.collection)
import spec as S  # noqa: E402
s = S.load()[0]; st = ve.stations(s); g = ve.config(s)['geometry']
SL = [89.6, 90.4]                                     # a 0.8 deg slice about +Z


def slab(name, prof, m):
    """A flat face in the dorsal (XZ) plane, seen square-on by the section cameras. A ring is passed as ('ring', outer, inner)
    point lists and is built as a quad strip; anything else is one filled polygon."""
    if prof[0] == 'ring':
        _, o, i = prof; n = len(o)
        vs = [(x, -0.01, r) for x, r in o] + [(x, -0.01, r) for x, r in i]
        fs = [(k, k + 1, n + k + 1, n + k) for k in range(n - 1)]
    else:
        vs = [(x, -0.01, r) for x, r in prof]; fs = [tuple(range(len(prof)))]
    return obj(name, vs, fs, SEC, m)


def ring_prof(xc, rc, a_in, a_out, a0=0.0, a1=2 * math.pi, n=40):
    angs = [a0 + (a1 - a0) * k / n for k in range(n + 1)]
    return ('ring', [(xc + a_out * math.cos(t), rc + a_out * math.sin(t)) for t in angs],
            [(xc + a_in * math.cos(t), rc + a_in * math.sin(t)) for t in angs])


def disc_prof(xc, rc, a, n=40):
    return [(xc + a * math.cos(2 * math.pi * k / n), rc + a * math.sin(2 * math.pi * k / n)) for k in range(n)]


for c in st['coils'] + st['loops']:
    cm = c['cryostat_minor_m']; phi = math.atan2(c['r'], c['x'] - BURN)
    slab(f'SEC_{c["name"]}_winding', disc_prof(c['x'], c['r'], c['winding_minor_m']), M['winding'])
    slab(f'SEC_{c["name"]}_screen80', ring_prof(c['x'], c['r'], cm * 0.80, cm * 0.84), M['screen'])
    slab(f'SEC_{c["name"]}_vessel', ring_prof(c['x'], c['r'], cm - 0.02, cm), M['vessel'])
    if c['name'].startswith('L'):
        off = cm + g['armour_offset_m'] + g['armour_minor_m']
        slab(f'SEC_{c["name"]}_drawn_shoe', disc_prof(c['x'] - off * math.cos(phi), c['r'] - off * math.sin(phi), g['armour_minor_m']), M['shoe'])
    acc = cm
    layers = [x for x in D['strategies']['C']['stack'] if x['layer'] != 'Cryostat vessel wall']
    for L in reversed(layers):
        t = L['t_m']; a0 = phi + math.pi / 2; a1 = phi + 3 * math.pi / 2
        # blanket drawn offset outward of the drawn shoe region: it wraps the vessel's burn-facing half
        slab(f'SEC_{c["name"]}_C_{L["layer"][:12]}', ring_prof(c['x'], c['r'], acc + 0.30, acc + 0.30 + max(t, 0.012), a0, a1), LM[L['layer']])
        acc += max(t, 0.012)
    # lithium channels in the heat sink (dots)
    for k in range(7):
        tt = phi + math.pi / 2 + math.pi * (k + 0.5) / 7; rr_ = cm + 0.30 + 0.05 + 0.01 + 0.005 + 0.22 + 0.10 + 0.002 + 0.02 + 0.006
        slab(f'SEC_{c["name"]}_Li_{k}', disc_prof(c['x'] + rr_ * math.cos(tt), c['r'] + rr_ * math.sin(tt), 0.012, 10), M['hot'])
# shield and its face
slab('SEC_shield_LiH', [(-10.6, 0.0), (-10.6, 4.4), (-12.78, 5.35), (-12.78, 0.0)], LM['LiH moderator'])
slab('SEC_shield_face', [(-12.78, 0.0), (-12.78, 5.35), (-12.92, 5.25), (-12.92, 0.0)], M['shoe'])
slab('SEC_shield_coating_A', [(-12.92, 0.0), (-12.92, 5.25), (-12.935, 5.25), (-12.935, 0.0)], M['A'])
# rays from the burn point to each coil (sky trace directions)
for c in st['coils'] + st['loops']:
    for dth in (-0.06, 0.0, 0.06):
        th = math.atan2(c['r'], c['x'] - BURN) + dth; d = math.hypot(c['x'] - BURN, c['r']) - c['cryostat_minor_m'] - 0.4
        p0 = (BURN, 0.0, 0.0); p1 = (BURN + d * math.cos(th), 0.0, d * math.sin(th))
        vs, fs = ve.tube_mesh([p0, p1], 0.015, 6); obj(f'SEC_ray_{c["name"]}_{dth}', vs, fs, SEC, M['ray'])
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15, location=(BURN, 0, 0)); bp2 = bpy.context.object; bp2.name = 'SEC_burn'
for c_ in bp2.users_collection:
    c_.objects.unlink(bp2)
SEC.objects.link(bp2); bp2.data.materials.append(M['burn'])
rotS = (math.pi / 2, 0, 0)
y0 = -0.5
sec_lbl = [('Burn point', (BURN - 0.4, y0, -0.9)), ('Shield: LiH body, W/B4C face,\nPt coating (A)', (-12.6, y0, 6.4))]
for c in st['coils'] + st['loops']:
    ph = math.atan2(c['r'], c['x'] - BURN); dd = c['cryostat_minor_m'] + 0.75
    if c['name'] == 'C1':
        ph = math.radians(150)
    sec_lbl.append((c['name'], (c['x'] + dd * math.cos(ph) - 0.2, y0, c['r'] + dd * math.sin(ph) - 0.1)))
for i, (t, p) in enumerate(sec_lbl):
    text(f'SEC_LBL_{i}', t, p, 0.32, SEC, rot=rotS)
leg = ['Section legend (outside to inside, strategy C):'] + [f'{L["layer"]}: {L["t_m"] * 1000:.0f} mm' for L in D['strategies']['C']['stack']] + \
      ['Dark circle: drawn armour shoe (0.22 m)', 'Copper ring: 80 K screen   Brown disc: 20 K winding', 'Orange dots: lithium channels   Yellow: rays from the burn']
for i, t in enumerate(leg):
    text(f'SEC_LEG_{i}', t, (-33.3, y0, -0.4 - 0.36 * i), 0.24, SEC, rot=rotS)

# ---------- labels in the 3D view ----------
LB = C['LABELS']
lbl3 = [('A  Pt-coated burn faces: reflect 1.5e-5 of the X-rays that strike', (-17.0, 0.0, -8.4)),
        ('B  edge-on blades and cones (adopted): the members\' heat falls to 9 %', (-24.0, 0.0, 12.6)),
        ('C  thin coil blanket (option, 248 t): bare cryostats cooled, neutrons pass', (-31.0, 0.0, -12.0)),
        ('D  grazing liners: no benefit for a 1-1000 keV spectrum', (-27.0, 0.0, -10.6)),
        ('Hot circuit: lithium 1500 -> 1800 K, drawn lines carry 0.22 GW of 5.8 TW', (-8.0, 0.0, 9.6)),
        ('Cryo circuit: 20 K windings take 25 GW; independent helium headers', (-4.0, 0.0, -6.6)),
        ('Warm circuit: NaK 650 -> 850 K for blade roots and housings', (-6.0, 0.0, 11.2))]
for i, (t, p) in enumerate(lbl3):
    text(f'LBL_{i}', t, p, 0.55, LB, rot=(math.pi / 2, 0, math.radians(-25)))

# ---------- lights, world, cameras ----------
LIGHTS = coll('WORK_THERMAL_LIGHTS', scene.collection, 'NONE')
for ob in list(LIGHTS.objects):
    pass
w = bpy.data.worlds.new('WORK_THERMAL_WORLD'); scene.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.012, 0.014, 0.02, 1); w.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
for nm, loc, en in (('KEY', (10, -30, 25), 6.0), ('FILL', (-40, 25, -10), 2.0), ('RIM', (-45, -5, 30), 3.0)):
    ld = bpy.data.lights.new(nm, 'SUN'); ld.energy = en; lo = bpy.data.objects.new(f'WORK_THERMAL_LIGHT_{nm}', ld); LIGHTS.objects.link(lo)
    lo.rotation_euler = (Vector((-16, 0, 0)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
CAM = coll('WORK_THERMAL_CAMERAS', scene.collection, 'NONE')
ALL = ('MIRRORS_A', 'BLADES', 'MIRRORS_D', 'BLANKET_THIN', 'HOT', 'WARM', 'CRYO', 'SERVICE')
cams = dict(
    overview=(camera('CAM_overview', (14, -34, 18), (-16, 0, 0), CAM, lens=32), ALL, False),
    mirrors=(camera('CAM_mirrors', (-2, -26, -12), (-19, 0, 1), CAM, lens=30), ('MIRRORS_A', 'MIRRORS_D'), False),
    blades=(camera('CAM_blades', (-56, -30, 20), (-20, 0, 1), CAM, lens=30), ('BLADES',), False),
    blanket=(camera('CAM_blanket', (-6, 22, 12), (-20, 0, 0), CAM, lens=30), ('BLANKET_THIN',), False),
    network=(camera('CAM_network', (6, -26, 20), (-17, 0, 0), CAM, lens=30), ('HOT', 'WARM', 'CRYO'), False),
    hot=(camera('CAM_hot', (2, -22, 14), (-14, 0, 0), CAM, lens=30), ('HOT',), False),
    warm=(camera('CAM_warm', (-2, 24, 16), (-18, 0, 0), CAM, lens=30), ('WARM', 'BLADES'), False),
    cryo=(camera('CAM_cryo', (2, 22, -12), (-16, 0, 0), CAM, lens=30), ('CRYO',), False),
    service=(camera('CAM_service', (-36, -18, -14), (-20, 0, 0), CAM, lens=32), ('SERVICE', 'BLADES'), False),
    aft=(camera('CAM_aft', (-58, -10, 6), (-18, 0, 0), CAM, lens=40), ALL, False),
)
SCN.world = w
secam = camera('CAM_section', (-20.8, -60.0, 3.5), (-20.8, 0.0, 3.5), SCN.collection, ortho=26.0)
secC2 = camera('CAM_section_C2_L1', (-16.0, -40.0, 4.9), (-16.0, 0.0, 4.9), SCN.collection, ortho=8.0)
secL4 = camera('CAM_section_L3_L4', (-27.8, -40.0, 9.4), (-27.8, 0.0, 9.4), SCN.collection, ortho=10.0)
for nm, loc, en in (('SKEY', (-18, -40, 20), 1.6), ('SFILL', (-18, -40, -10), 0.5)):
    ld = bpy.data.lights.new(nm, 'SUN'); ld.energy = en; lo = bpy.data.objects.new(f'WORK_THERMAL_{nm}', ld); SCN.collection.objects.link(lo)
    lo.rotation_euler = (Vector((-18, 0, 4)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
SCN.camera = secam
SCN.view_settings.view_transform = 'Standard'
scene.camera = cams['overview'][0]
for sc in (scene, SCN):
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1000; sc.render.film_transparent = False
out = HERE / 'REVIEW_THERMAL.blend'
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
print('saved', out, flush=True)
if RENDER:
    rd = Path('/mnt/project-files/vertex-thermal'); rd.mkdir(parents=True, exist_ok=True)
    import os
    only = [v for v in os.environ.get('ONLY', '').split(',') if v]
    for vn, (cam, show, tech) in cams.items():
        if only and vn not in only:
            continue
        for k, cc in C.items():
            cc.hide_render = k not in show
        scene.render.engine = 'BLENDER_EEVEE'; scene.eevee.taa_render_samples = 16
        scene.camera = cam; scene.render.filepath = str(rd / f'thermal_{vn}.png')
        bpy.ops.render.render(write_still=True, scene=scene.name); print('rendered', vn, flush=True)
    for k, cc in C.items():
        cc.hide_render = k == 'BLANKET_C_ARCHIVED'
    for nm, cam in (('section', secam), ('section_C2_L1', secC2), ('section_L3_L4', secL4)):
        if only and nm not in only:
            continue
        SCN.render.engine = 'BLENDER_EEVEE'; SCN.eevee.taa_render_samples = 16; SCN.camera = cam
        SCN.render.filepath = str(rd / f'thermal_{nm}.png')
        bpy.ops.render.render(write_still=True, scene=SCN.name); print('rendered', nm, flush=True)
    SCN.camera = secam; scene.camera = cams['overview'][0]
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
