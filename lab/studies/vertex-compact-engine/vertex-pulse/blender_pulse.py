"""Integrated engine hardware of the research geometry, and a labelled coil cross-section (WORK / PROTOTYPE, not canon; owner brief
2026-11-25 08:55Z, item 5).

  /snap/bin/blender -b --factory-startup --python lab/studies/vertex-compact-engine/vertex-pulse/blender_pulse.py [-- --no-render]

Opens vertex-optimize/REVIEW_OPTIMIZE.blend (ORIGINAL: the approved engine; OPTIMIZED: burn 4 m aft, closure rewound) and saves
REVIEW_PULSE.blend with two more scenes:
  INTEGRATED  everything OPTIMIZED shows, minus the approved armour, armour headers and lithium jumpers (they faced the drawn burn; hidden
              here, never deleted), plus results/frames.json:
     WORK_INT_CRYOSTATS  the six research cryostats, cut away 70 deg so the windings show
     WORK_INT_LIPS       re-aimed sacrificial tungsten armour, eight exchange modules per coil, split at the longerons
     WORK_INT_HOT        twin-bore lithium headers, feeders into every module, branches to the cage supply and return lines
     WORK_INT_CRYO       20 K rings and their branches from both cage cryogen lines
     WORK_INT_WARM       warm rings, the warm manifold on the thrust collar and the two warm headers along the cage
     WORK_INT_MIRRORS    grazing-incidence supermirror strips on the lip edges (conical, apex at the burn)
     WORK_INT_TRAYS      busbar / instrumentation trays to the coil current lead line
     WORK_INT_SUPPORTS   pipe brackets to the structure where a run exceeds 3 m
  SECTION     a 1:1 cut through C1 in its meridian plane: winding, insulation, hoop band with 20 K channels, vacuum, 80 K shield, vessel,
              lip with its lithium channel, headers, supermirror strips, the ray to the burn, labels.
Colours: hot red-orange, warm amber, cryo blue, electrical yellow, structure grey, mirrors bright metal.
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
FR = json.loads((HERE / 'results' / 'frames.json').read_text())
CO = json.loads((HERE.parent / 'vertex-optimize' / 'results' / 'coils.json').read_text())
PINK = 'COLOR_07'
BX = FR['burn_x']

bpy.ops.wm.open_mainfile(filepath=str(HERE.parent / 'vertex-optimize' / 'REVIEW_OPTIMIZE.blend'))
opt = bpy.data.scenes['OPTIMIZED']


def mat(name, rgba, emit=0.0, metal=0.0, rough=0.5, alpha=1.0):
    m = bpy.data.materials.new(name); m.diffuse_color = (rgba[0], rgba[1], rgba[2], alpha); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgba[:3], 1); b.inputs['Metallic'].default_value = metal; b.inputs['Roughness'].default_value = rough
    if emit:
        b.inputs['Emission Color'].default_value = (*rgba[:3], 1); b.inputs['Emission Strength'].default_value = emit
    if alpha < 1:
        b.inputs['Alpha'].default_value = alpha
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            pass
    return m


M = dict(hot=mat('WORK_INT_hot_lithium', (0.85, 0.28, 0.12), metal=0.7, rough=0.35),
         lip=mat('WORK_INT_tungsten_lip', (0.42, 0.40, 0.38), metal=0.95, rough=0.45),
         cryo=mat('WORK_INT_cryo_20K', (0.25, 0.6, 1.0), metal=0.6, rough=0.3, emit=0.6),
         warm=mat('WORK_INT_warm', (0.95, 0.68, 0.18), metal=0.6, rough=0.35),
         elec=mat('WORK_INT_busbar_tray', (0.95, 0.85, 0.2), metal=0.5, rough=0.4),
         struct=mat('WORK_INT_bracket', (0.55, 0.55, 0.58), metal=0.8, rough=0.4),
         mirror=mat('WORK_INT_supermirror', (0.86, 0.9, 1.0), metal=1.0, rough=0.04),
         cryostat=mat('WORK_INT_cryostat', (0.62, 0.66, 0.72), metal=0.8, rough=0.3),
         wind=mat('WORK_INT_winding', (0.72, 0.36, 0.12), metal=0.9, rough=0.35),
         band=mat('WORK_INT_hoop_band', (0.1, 0.1, 0.11), rough=0.6),
         ins=mat('WORK_INT_insulation', (0.85, 0.82, 0.6), rough=0.8),
         shield80=mat('WORK_INT_80K_shield', (0.75, 0.75, 0.78), metal=0.9, rough=0.25),
         vac=mat('WORK_INT_vacuum', (0.03, 0.03, 0.05), rough=1.0),
         ray=mat('WORK_INT_ray', (1.0, 0.85, 0.4), emit=4.0),
         ink=mat('WORK_INT_ink', (0.04, 0.04, 0.06), rough=1.0),
         text=bpy.data.materials.get('WORK_OPT_text') or mat('WORK_INT_text', (0.95, 0.95, 0.95), emit=2.0))
NETMAT = dict(hot=M['hot'], cryo=M['cryo'], warm=M['warm'], electrical=M['elec'], structure=M['struct'])


def coll(name, parent):
    c = bpy.data.collections.new(name); parent.children.link(c); c.color_tag = PINK
    return c


def obj(name, vf, c, m, note, smooth=True):
    vs, fs = vf
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in vs], [], [tuple(f) for f in fs]); me.update()
    o = bpy.data.objects.new(name, me); c.objects.link(o); me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = smooth
    o['wf_note'] = note; o['wf_status'] = 'WORK / PROTOTYPE integrated research hardware (vertex-pulse, not canon)'
    return o


def join(parts):
    vs, fs = [], []
    for v_, f_ in parts:
        o = len(vs); vs += list(v_); fs += [tuple(i + o for i in f) for f in f_]
    return vs, fs


# ---------- INTEGRATED ----------
sc = bpy.data.scenes.new('INTEGRATED')
for a in ('engine', 'resolution_x', 'resolution_y', 'film_transparent'):
    setattr(sc.render, a, getattr(opt.render, a))
try:
    sc.eevee.taa_render_samples = opt.eevee.taa_render_samples
except Exception:
    pass
sc.world = opt.world
replaced = set(FR['replaced_approved'])
base = bpy.data.collections.new('INT_BASE'); sc.collection.children.link(base)
import tomllib  # noqa: E402
SPEC = tomllib.loads((ROOT / 'data/wayfarer_3d.toml').read_text())
PARTS = {p['name']: p for p in ve.parts(SPEC) + ve.refinements(SPEC)}
seen = set(); rebuilt = []
top = coll('WORK_INT', sc.collection)
keep = coll('WORK_INT_APPROVED_KEPT', top); keep.color_tag = 'NONE'
for o in opt.collection.all_objects:
    parts_ = {q.strip() for q in str(o.get('wf_parts', '')).split(',') if q.strip()}
    if o.name in seen or o.name.startswith('WORK_OPT_') and ('cryostat' in o.name or '20K_channel' in o.name):
        continue
    seen.add(o.name)
    if parts_ & replaced:
        # a joined family object holding replaced parts: rebuild it from the approved part list without them (the approved file is
        # untouched; this copy lives only in the INTEGRATED scene)
        kept = [PARTS[q] for q in sorted(parts_ - replaced) if q in PARTS]
        if kept:
            vf = join([ve.mesh_of(q) for q in kept])
            me = bpy.data.meshes.new(o.name + '_INT'); me.from_pydata(vf[0], [], vf[1]); me.update()
            for m_ in o.data.materials:
                me.materials.append(m_)
            for pg in me.polygons:
                pg.use_smooth = True
            no = bpy.data.objects.new(o.name + '_INT', me); keep.objects.link(no); no.matrix_world = o.matrix_world.copy()
            no['wf_parts'] = ', '.join(q['name'] for q in kept); no['wf_note'] = f'{o.name} without the parts the integrated hardware replaces'
            rebuilt.append((o.name, len(kept), len(parts_ & replaced)))
        continue
    if o.name not in replaced:
        base.objects.link(o)
C = {k: coll(f'WORK_INT_{k}', top) for k in ('CRYOSTATS', 'LIPS', 'HOT', 'CRYO', 'WARM', 'MIRRORS', 'TRAYS', 'SUPPORTS', 'LABELS')}
mixed = rebuilt

for e in CO['research_geometry']:
    obj(f'WORK_INT_{e["name"]}_cryostat', ve.torus_mesh(e['x'], e['r'], e['cryostat_minor_m'], (35.0, 325.0), 72, 20), C['CRYOSTATS'],
        M['cryostat'], f'{e["name"]} research cryostat (minor {e["cryostat_minor_m"]:.2f} m), cut away 70 deg')
    obj(f'WORK_INT_{e["name"]}_winding', ve.torus_mesh(e['x'], e['r'], e['winding_minor_m'], None, 72, 14), C['CRYOSTATS'], M['wind'],
        f'{e["name"]} winding at the research current scale')

for c in FR['components']:
    k, n = c['kind'], c['name'].replace('INT_', 'WORK_INT_')
    if k == 'lip':
        cx, cr = c['center']; lo, hi = c['arc']; a, t = c['a'], c['t']
        prof = [(cx + a * math.cos(math.radians(lo + (hi - lo) * i / 24)), cr + a * math.sin(math.radians(lo + (hi - lo) * i / 24))) for i in range(25)]
        prof += [(cx + (a + t) * math.cos(math.radians(hi - (hi - lo) * i / 24)), cr + (a + t) * math.sin(math.radians(hi - (hi - lo) * i / 24))) for i in range(25)]
        mods = [ve._revolve(prof, 72, True, (az + 0.8, az + 45 - 0.8)) for az in c['split_az']]
        obj(n, join(mods), C['LIPS'], M['lip'], f'{c["station"]} sacrificial tungsten lip, poloidal {lo % 360:.0f}-{hi % 360:.0f} deg facing the moved burn, '
            f'{c["modules"]} exchange modules split at the longerons, lithium-cooled from behind')
    elif k == 'ring' or k == 'plant':
        m = NETMAT[c['net']]
        note = {'hot': 'twin-bore lithium header (supply and return bores), in the coil shadow from the burn',
                'cryo': '20 K distribution ring on the cryostat skin', 'warm': 'warm ring: cryostat thermal shield and frame cooling'}[c['net']]
        obj(n, ve.torus_mesh(c['x'], c['R'], c['a'], None, 96, 10), C[{'hot': 'HOT', 'cryo': 'CRYO', 'warm': 'WARM'}[c['net']]], m,
            note if k == 'ring' else 'warm manifold on the thrust collar rim (warm plant interface)')
    elif k in ('header', 'branch', 'tray', 'support'):
        pts = c.get('path')
        if pts is None:
            seg = [s for s in (c.get('segs') or [])]
        r = c.get('radius', 0.07 if k != 'support' else 0.04)
        cl = {'support': {'structure': 'SUPPORTS'}, 'header': {'warm': 'WARM'}, 'branch': {'hot': 'HOT', 'cryo': 'CRYO', 'warm': 'WARM'}, 'tray': {'electrical': 'TRAYS'}}[k][c['net']]
        obj(n, ve.tube_mesh(pts, r if k != 'tray' else 0.12, 4 if k == 'tray' else 10), C[cl], NETMAT[c['net']],
            {'header': 'warm header along the cage', 'branch': f'{c["net"]} branch: cage line -> elbow -> ring (routed clear of every part)',
             'tray': 'busbar and instrumentation tray to the coil current lead line',
             'support': 'pipe bracket to the nearest structural member (run over 3 m)'}[k], smooth=k != 'tray')
    elif k == 'feeder':
        pass
    elif k == 'mirror':
        parts = []
        for s_ in c['strips']:
            al = math.radians(s_['half_angle_deg'])
            prof = [(BX + s_['d0'] * math.cos(al), s_['d0'] * math.sin(al)), (BX + s_['d1'] * math.cos(al), s_['d1'] * math.sin(al))]
            parts.append(ve._revolve(prof, c['facets'], False))
        obj(n, join(parts), C['MIRRORS'], M['mirror'], 'grazing-incidence supermirror strips: conical, apex at the burn, 0.2 deg off the ray; '
            'reflect only X-rays within a few mrad (multilayer at 100 keV), most energy still reaches the lip', smooth=False)
# feeders and supports from their segments (stored in frames.json components without segs; rebuild from stations)
st_by = {s['name']: s for s in FR['stations']}
for c in FR['components']:
    if c['kind'] == 'feeder':
        st = st_by[c['station']]; cx, cr = st['x'], st['r']; lo, hi = st['lip']
        hx, hr = st['ring']['Hot_Supply'][0], st['ring']['Hot_Supply'][1]
        th_e = lo if abs(((st['th_sup'] - lo + 180) % 360) - 180) < abs(((st['th_sup'] - hi + 180) % 360) - 180) else hi
        ex = cx + (st['a_lip'] + FR['P']['lip_t']) * math.cos(math.radians(th_e)); er = cr + (st['a_lip'] + FR['P']['lip_t']) * math.sin(math.radians(th_e))
        parts = [ve.tube_mesh([ve.pol(hx, hr, az), ve.pol(ex, er, az)], FR['P']['feeder_r'], 8) for az in [22.5 + 45 * j + 22.5 for j in range(8)]]
        obj(c['name'].replace('INT_', 'WORK_INT_'), join(parts), C['HOT'], M['hot'], 'lithium feeders, header to every lip module')
    if c['kind'] == 'support':
        pass

# labels
def text(name, body, loc, size, coll_=None, rot=(math.pi / 2, 0, 0)):
    cu = bpy.data.curves.new(name, 'FONT'); cu.body = body; cu.size = size; cu.align_x = 'CENTER'
    o = bpy.data.objects.new(name, cu); (coll_ or C['LABELS']).objects.link(o); o.location = loc; o.rotation_euler = rot
    cu.materials.append(M['text'])
    return o


text('LBL_int_title', 'integrated research hardware: hot / warm / 20 K networks, re-aimed armour, supermirror strips', (-20.0, 0, 13.2), 0.6)
for o in [o for o in opt.collection.all_objects if o.type in ('CAMERA', 'LIGHT')]:
    if o.name not in base.objects:
        try:
            base.objects.link(o)
        except RuntimeError:
            pass
cd = bpy.data.cameras.new('CAM_int_detail'); cd.lens = 32
cam = bpy.data.objects.new('CAM_int_detail', cd); C['LABELS'].objects.link(cam)
cam.location = (-9.0, -15.5, 11.5); cam.rotation_euler = (Vector((-17.5, 0.0, 4.5)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cd2 = bpy.data.cameras.new('CAM_int_aft'); cd2.lens = 28
cam2 = bpy.data.objects.new('CAM_int_aft', cd2); C['LABELS'].objects.link(cam2)
cam2.location = (-44.0, -16.0, 14.0); cam2.rotation_euler = (Vector((-20.0, 0.0, 0.0)) - cam2.location).to_track_quat('-Z', 'Y').to_euler()
sc.camera = bpy.data.objects.get('CAM_overview') or cam

# ---------- SECTION ----------
ss = bpy.data.scenes.new('SECTION')
for a in ('engine', 'resolution_x', 'resolution_y'):
    setattr(ss.render, a, getattr(opt.render, a))
ss.world = opt.world
S = coll('WORK_INT_SECTION', ss.collection)
st = st_by['C1']; e = next(q for q in CO['research_geometry'] if q['name'] == 'C1')
cx, cr = e['x'], e['r']; wm, cm = e['winding_minor_m'], e['cryostat_minor_m']; bt, bw = e['band_t_m'], e['band_width_m']


def disc2(cx_, cz_, r0, r1, n=64, a0=0.0, a1=360.0):
    """Annulus (or sector) in the x-z plane at y = 0 (z plays the role of r)."""
    vs, fs = [], []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        vs += [(cx_ + r0 * math.cos(a), 0.0, cz_ + r0 * math.sin(a)), (cx_ + r1 * math.cos(a), 0.0, cz_ + r1 * math.sin(a))]
    for i in range(n):
        fs.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
    return vs, fs


def rect2(x0, z0, x1, z1, y=0.0):
    return [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], [(0, 1, 2, 3)]


layers = [('winding', disc2(cx, cr, 0.0001, wm), M['wind'], f'winding (REBCO stack, {wm:.2f} m radius at the research current density)'),
          ('insulation', disc2(cx, cr, wm, wm + 0.02), M['ins'], 'ground insulation'),
          ('hoop_band', rect2(cx - bw / 2, cr + wm + 0.02, cx + bw / 2, cr + wm + 0.02 + bt, -0.01), M['band'],
           f'hoop band {bt * 1000:.0f} mm (1.5 GPa allowable): hoop structure, cold-mass support and 20 K channels'),
          ('vacuum', disc2(cx, cr, wm + 0.02, cm - 0.09), M['vac'], 'insulating vacuum'),
          ('shield_80K', disc2(cx, cr, cm - 0.09, cm - 0.07), M['shield80'], '80 K thermal shield (warm-network cooled)'),
          ('vessel', disc2(cx, cr, cm - 0.03, cm), M['cryostat'], 'vacuum vessel'),
          ('lip', disc2(cx, cr, st['a_lip'], st['a_lip'] + FR['P']['lip_t'], 48, st['lip'][0], st['lip'][1]), M['lip'],
           'sacrificial tungsten lip facing the burn (5 mm face, lithium channel behind)'),
          ('lip_channel', disc2(cx, cr, st['a_lip'] + 0.012, st['a_lip'] + 0.03, 48, st['lip'][0], st['lip'][1]), M['hot'], 'lithium channel')]
for nm, vf, m, note in layers:
    obj(f'SEC_{nm}', vf, S, m, note, smooth=False)
for j in (-1, 1):
    obj(f'SEC_20K_channel_{j:+d}', disc2(cx + j * bw / 4, cr + wm + 0.02 + bt / 2, 0.0001, min(0.03, bt / 3), 24), S, M['cryo'], '20 K channel in the band', smooth=False)
for tag, m in (('Hot_Supply', M['hot']), ('Cryo_Ring', M['cryo']), ('Warm_Ring', M['warm'])):
    px, pr, rr = st['ring'][tag][0], st['ring'][tag][1], st['ring'][tag][2]
    obj(f'SEC_{tag}', disc2(px, pr, 0.0001, rr, 32), S, m, f'{tag} cross-section', smooth=False)
    if tag == 'Hot_Supply':
        for j in (-1, 1):
            obj(f'SEC_hot_bore_{j:+d}', disc2(px + j * rr * 0.4, pr, 0.0001, rr * 0.32, 16, 0, 360), S, M['vac'], 'twin bores (supply / return)', smooth=False)
for s_ in next(c for c in FR['components'] if c['name'] == 'INT_C1_Supermirror')['strips']:
    al = math.radians(s_['half_angle_deg'])
    p0 = (BX + s_['d0'] * math.cos(al), s_['d0'] * math.sin(al)); p1 = (BX + s_['d1'] * math.cos(al), s_['d1'] * math.sin(al))
    nx, nz = -math.sin(al) * 0.012, math.cos(al) * 0.012
    obj(f'SEC_mirror_{s_["edge_deg"]:.0f}', ([(p0[0] - nx, 0, p0[1] - nz), (p1[0] - nx, 0, p1[1] - nz), (p1[0] + nx, 0, p1[1] + nz), (p0[0] + nx, 0, p0[1] + nz)],
        [(0, 1, 2, 3)]), S, M['mirror'], 'supermirror strip, grazing to the burn ray', smooth=False)
u = math.radians(st['u_deg'])
ray_end = (cx + (st['a_lip'] + 0.05) * math.cos(u), cr + (st['a_lip'] + 0.05) * math.sin(u))
ray_start = (cx + 2.2 * math.cos(u), cr + 2.2 * math.sin(u))
obj('SEC_ray_to_burn', ve.tube_mesh([(ray_start[0], 0.02, ray_start[1]), (ray_end[0], 0.02, ray_end[1])], 0.01, 6), S, M['ray'],
    'direction to the moved burn (x = %.1f m)' % BX)
lbl = [('winding', (cx, -0.05, cr), 0.06), ('hoop band + 20 K channels (top of the winding)', (cx, -0.05, cr + wm - 0.24), 0.03),
       ('80 K shield / vacuum vessel', (cx - 0.15, -0.05, cr + cm + 0.32), 0.05), ('tungsten lip, Li-cooled', (ray_end[0] - 0.3, -0.05, ray_end[1] - 0.22), 0.05),
       ('twin-bore Li header', (st['ring']['Hot_Supply'][0], -0.05, st['ring']['Hot_Supply'][1] - 0.18), 0.05),
       ('20 K ring', (st['ring']['Cryo_Ring'][0] + 0.25, -0.05, st['ring']['Cryo_Ring'][1]), 0.05),
       ('warm ring', (st['ring']['Warm_Ring'][0] + 0.25, -0.05, st['ring']['Warm_Ring'][1] + 0.08), 0.05),
       ('to the burn', (ray_start[0], -0.05, ray_start[1] + 0.08), 0.05),
       ('C1 meridian section, research geometry (PROTOTYPE)', (cx, -0.05, cr + 1.45), 0.07)]
for i, (body, loc, size) in enumerate(lbl):
    t_ = text(f'SEC_LBL_{i}', body, loc, size, S)
    if i < 2:   # labels drawn over the pale winding read in dark ink
        t_.data.materials[0] = M['ink']
lt = bpy.data.lights.new('SEC_sun', 'SUN'); lt.energy = 3.0
lo_ = bpy.data.objects.new('SEC_sun', lt); S.objects.link(lo_); lo_.rotation_euler = (math.radians(90), 0, 0)
csd = bpy.data.cameras.new('CAM_section'); csd.type = 'ORTHO'; csd.ortho_scale = 3.6
cso = bpy.data.objects.new('CAM_section', csd); S.objects.link(cso)
cso.location = (cx - 0.3, -6.0, cr + 0.35); cso.rotation_euler = (math.pi / 2, 0, 0)


def frame_section(cam, scene, pad=1.3):
    # fit the ortho camera to every SEC_ object (labels included), looking along +y at the meridian plane
    from mathutils import Vector
    pts = [o.matrix_world @ Vector(c) for o in scene.objects if o.name.startswith('SEC_') and o.type == 'MESH' for c in o.bound_box]
    for o in scene.objects:   # labels: their matrices are not evaluated in background, so take the location and an estimated text extent
        if o.name.startswith('SEC_LBL') and o.type == 'FONT':
            w = 0.3 * o.data.size * len(o.data.body)
            pts += [Vector((o.location.x - w, 0, o.location.z - 0.2 * o.data.size)), Vector((o.location.x + w, 0, o.location.z + o.data.size))]
    x0, x1 = min(p.x for p in pts), max(p.x for p in pts); z0, z1 = min(p.z for p in pts), max(p.z for p in pts)
    r = scene.render; asp = r.resolution_x / r.resolution_y
    cam.location = ((x0 + x1) / 2, -6.0, (z0 + z1) / 2); cam.rotation_euler = (math.pi / 2, 0, 0)
    cam.data.ortho_scale = pad * max(x1 - x0, (z1 - z0) * asp)


frame_section(cso, ss)
ss.camera = cso

out = HERE / 'REVIEW_PULSE.blend'
if bpy.context.window_manager.windows:
    bpy.context.window_manager.windows[0].scene = sc
bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True); print('saved', out, 'mixed objects kept visible:', mixed, flush=True)
if RENDER:
    rd = Path('/mnt/project-files/fusion-pulse'); rd.mkdir(parents=True, exist_ok=True)
    shots = [('integrated_overview', sc, 'CAM_overview'), ('integrated_detail', sc, 'CAM_int_detail'), ('integrated_aft', sc, 'CAM_int_aft'),
             ('section_C1', ss, 'CAM_section'), ('optimized_detail', opt, 'CAM_int_detail')]
    for nm, scene, cn in shots:
        cobj = bpy.data.objects.get(cn)
        if cobj is None:
            continue
        if cobj.name not in scene.collection.all_objects:
            scene.collection.objects.link(cobj)
        scene.camera = cobj; scene.render.filepath = str(rd / f'{nm}.png')
        bpy.ops.render.render(write_still=True, scene=scene.name); print('rendered', nm, flush=True)
    sc.camera = bpy.data.objects.get('CAM_overview') or cam
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
