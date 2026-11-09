"""T05 Stage B: build the non-destructive Vertex review file (NON-CANON research geometry). Study code in work/; nothing reads it.

  /snap/bin/blender -b --factory-startup --python-exit-code 1 --python work/vertex-blender/build_vertex.py -- \
      [--out work/vertex-blender/REVIEW_VERTEX_BLENDER.blend] [--render DIR] [--cams CAM_VTX_01 ...] [--size W H] [--no-save]

Every Vertex dimension comes from a live FDP-1 solve with each generation's registry overrides (lab/variants/vertex-drive/convergence.py),
the FDP-1 part list (lab/variants/fdp1/engineering/geometry.parts) and T03's closure-coil design; T05 PROTOTYPE sizes are the PR_*
constants below. The canonical ship is appended from assets/wayfarer/WF_WAYFARER_001.blend three times: one untouched copy (CANON)
and one working copy per Vertex generation (superseded drive and idle H2 vessels hidden, never deleted; bow moved for the T-B stretch).
Plan: work/vertex-blender/WORKFLOW.md, COLLECTIONS.md, CAMERAS.md. Measurements go to work/vertex-blender/checks.json.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FDP = ROOT/'lab/variants/fdp1'
sys.path[:0] = [str(HERE), str(ROOT/'lab/variants/vertex-drive'), str(FDP), str(ROOT/'src/wayfarer'), str(ROOT/'src')]
import screen                                            # noqa: E402  (canon datums, solve, envelope, irradiance)
from engineering import geometry as G                    # noqa: E402
import functional_colors as fc                           # noqa: E402

a = argparse.ArgumentParser()
a.add_argument('--out', type=Path, default=HERE/'REVIEW_VERTEX_BLENDER.blend')
a.add_argument('--render', type=Path); a.add_argument('--cams', nargs='+'); a.add_argument('--size', type=int, nargs=2, default=(2560, 1440))
a.add_argument('--ship-cache', default='/tmp/wayfarer_vertex_ship_local.blend')
a.add_argument('--no-save', action='store_true'); a.add_argument('--no-ship', action='store_true')
a.add_argument('--rays', type=int, default=2000000); a.add_argument('--kernel-rays', type=int, default=600000)
a = a.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
REV2 = json.loads((Path(__file__).resolve().parent/'rev2.json').read_text())     # python3 work/vertex-blender/rev2.py writes it
CANON2 = REV2['canon']
LAUNCHER_KG_PER_M_NOTE = 'mass about 0.5 t/m PROTOTYPE (UNKNOWN)'

SHIP = ROOT/'assets/wayfarer/WF_WAYFARER_001.blend'
REVISION = 4
GENS = ('V4', 'V0', 'V5')
C = screen.canon()
RS = {g: screen.solve(g) for g in GENS}
screen_data = json.loads((HERE/'screen.json').read_text())
ENV = {g: screen_data['generations'][g] for g in GENS}
LEDGER = json.loads((ROOT/'lab/variants/vertex-drive/studies/thermal/ledger.json').read_text())['cases']['S1_advanced_eta0.30']['circuits']

# T05 PROTOTYPE sizes (no thread gives a number): each is listed in VERTEX_PART_STATUS
PR_LAUNCHER_LEN = 20.0          # m, T01 says 10-20 m at 1e5 g; length UNKNOWN
PR_LAUNCHER_R = 0.6
PR_IGNITOR_R = 0.5
PR_IGNITOR_OFFSET = 1.6         # m off the bore axis
PR_TRITIUM_R = 1.0              # 2 m sphere
PR_SPLITS = 12                  # mechanical split lines per loop (30 deg), aligned to the trim joints (ISS-007)
PR_COIL_STRUTS = 6
PR_SKIRT_SHORT_X = C['ring_a_aft_face_x_m']-10.0
PR_RIB_PITCH = 1000.0           # wing rib pitch along the span
STATUS = {'ENGINEERED': 'ENGINEERING_SUPPORTED', 'PLACEHOLDER': 'PARAMETRIC_PLACEHOLDER', 'ILLUSTRATIVE': 'CONCEPTUAL_ILLUSTRATION'}
CODE = {'ENGINEERING_SUPPORTED': 'ES', 'PARAMETRIC_PLACEHOLDER': 'PP', 'PROTOTYPE': 'PR', 'CONCEPTUAL_ILLUSTRATION': 'CI'}
ALPHA = {'ENGINEERING_SUPPORTED': 1.0, 'PARAMETRIC_PLACEHOLDER': 0.75, 'PROTOTYPE': 0.6, 'CONCEPTUAL_ILLUSTRATION': 0.18}

PALETTE = dict(fc.PALETTE)
for k, rgba in G.VIS.items():
    PALETTE['VIS_'+k] = (k.title(), rgba, 'COLOR_07')
PALETTE['VIS_DUST'] = ('Dust stream (overlay)', (0.75, 0.75, 0.70, 1.0), 'COLOR_07')
PALETTE['VIS_LABEL'] = ('Label', (0.98, 0.95, 0.85, 1.0), 'COLOR_07')
PALETTE['VIS_ALT'] = ('Alternative outline', (0.30, 0.85, 0.95, 1.0), 'COLOR_07')
PALETTE['VIS_CONFLICT'] = ('Measured conflict', (1.0, 0.1, 0.1, 1.0), 'COLOR_07')

# collection keys: FDP-1 part collections -> Vertex functional groups (COLLECTIONS.md; 12 added for diagnostics)
GROUPS = {'01': 'REACTION_ZONE', '02': 'NOZZLE', '03': 'SHIELD', '04': 'DRIVERS', '05': 'THERMAL', '06': 'POWER', '07': 'FUEL',
          '08': 'STRUCTURE', '09': 'MAINTENANCE', '10': 'DUST_PROTECTION', '11': 'KEEP_OUT', '12': 'DIAGNOSTICS'}
GROUP_FUNC = {'01': 'MAIN_PROPULSION', '02': 'MAIN_PROPULSION', '03': 'SHIELD', '04': 'MAIN_PROPULSION', '05': 'WARM_RADIATOR', '06': 'POWER',
              '07': 'HELIUM3', '08': 'STRUCTURE', '09': 'SERVICE', '10': 'SHIELD', '11': 'SHIELD', '12': 'SENSORS_COMMS'}
FDP_TO = {'00': '08', '01': '07', '02': '04', '03': '01', '04': '02', '05': '03', '06': '05', '07': '06', '08': '12', '09': '09', '10': '07', '11': '11', '12': None}
# FDP-1 parts Vertex replaces (wings redrawn with circuit bands; loops redrawn with the sector clock; pellet train and gas guns -> launcher)
REPLACED = ('FDP1_Wing_', 'FDP1_Loop_', 'FDP1_Pellet_In_Flight_', 'FDP1_Pellet_Injector_', 'FDP1_Label_')
VTX_OF = {'FDP1_Ignition_Point': 'VTX-01', 'FDP1_KeepOut_Xray': 'VTX-01', 'FDP1_Shield_': 'VTX-06A', 'FDP1_Shadow_Cone': 'VTX-06',
          'FDP1_Driver_': 'VTX-01B', 'FDP1_Gallery_': 'VTX-01B', 'FDP1_Beam_': 'VTX-01B', 'FDP1_Final_Focus': 'VTX-01B',
          'FDP1_Pulse_Storage': 'VTX-02C', 'FDP1_Power_Conditioning': 'VTX-02C', 'FDP1_Target_': 'VTX-01C', 'FDP1_Pellet_': 'VTX-01C',
          'FDP1_Fuel_': 'VTX-01C', 'FDP1_Feed_': 'VTX-01C', 'FDP1_Nozzle_Strut': 'VTX-02D', 'FDP1_Module_': 'VTX-01C', 'FDP1_Thrust': 'VTX-02D',
          'FDP1_Burn_Diagnostic': 'VTX-05B', 'FDP1_Target_Tracker': 'VTX-05A', 'FDP1_Injector_Alignment': 'VTX-05A', 'FDP1_Cryoplant': 'VTX-07A',
          'FDP1_Hot_Line': 'VTX-07F', 'FDP1_Cryo_Line': 'VTX-02B', 'FDP1_Low_Loop': 'VTX-07', 'FDP1_Exhaust': 'VTX-03', 'FDP1_Plasma': 'VTX-03',
          'FDP1_Axial_Plug': 'VTX-06A', 'FDP1_TB_': 'VTX-04', 'FDP1_Strut_Crawler': 'VTX-06B', 'FDP1_KeepOut_Plume': 'VTX-03'}


def vtx_of(name):
    for k, v in VTX_OF.items():
        if name.startswith(k):
            return v
    return 'VTX-NONE'


# ----------------------------------------------------------------------------------------------------------------------------------
# meshes (same primitives as lab/variants/fdp1/blender/build_fdp1.py)
# ----------------------------------------------------------------------------------------------------------------------------------
def seg_count(span_rad, radius, step=1.2, lo=8, hi=256):
    return max(lo, min(hi, int(abs(span_rad)*max(radius, 0.5)/step)))


def rev_mesh(profile, arcs, closed):
    vs, fs = [], []
    m = len(profile)
    for a0, a1 in arcs:
        span = math.radians(a1-a0); rmax = max(r for x, r in profile)
        n = seg_count(span, rmax)
        base = len(vs); cnt = n if closed else n+1
        for i in range(cnt):
            t = math.radians(a0)+span*i/n; c, sn = math.cos(t), math.sin(t)
            for x, r in profile:
                vs.append((x, r*c, r*sn))
        idx = lambda i, j, base=base, cnt=cnt: base+(i % cnt)*m+(j % m)
        for i in range(n):
            for j in range(m):
                fs.append((idx(i, j), idx(i+1, j), idx(i+1, j+1), idx(i, j+1)))
        if not closed:
            for i, rev in ((0, True), (n, False)):
                f = [idx(i, j) for j in range(m)]
                fs.append(tuple(reversed(f)) if rev else tuple(f))
    return vs, fs


def arcs_of(p, cut):
    a0, a1 = p.get('arc') or (0.0, 360.0)
    full = p.get('arc') is None
    if cut:
        c0, c1 = cut
        if full:
            return [(c1, c0+360.0)], False
        out = [(s0, s1) for s0, s1 in ((a0, min(a1, c0)), (max(a0, c1), a1)) if s1-s0 > 0.5]
        return out, False
    return [(a0, a1)], full


def tube_mesh(points, radius, nv=10):
    vs, fs = [], []
    pts = [Vector(p) for p in points]
    for k in range(len(pts)-1):
        p0, p1 = pts[k], pts[k+1]; d = p1-p0
        if d.length < 1e-6:
            continue
        w = d.normalized(); u = w.orthogonal().normalized(); v = w.cross(u)
        base = len(vs)
        for p in (p0, p1):
            for j in range(nv):
                t = 2*math.pi*j/nv
                vs.append(tuple(p+(u*math.cos(t)+v*math.sin(t))*radius))
        for j in range(nv):
            fs.append((base+j, base+(j+1) % nv, base+nv+(j+1) % nv, base+nv+j))
        fs.append(tuple(base+j for j in reversed(range(nv)))); fs.append(tuple(base+nv+j for j in range(nv)))
    return vs, fs


def sphere_mesh(c, r, nu=32, nv=16):
    vs, fs = [], []
    for i in range(nv+1):
        th = math.pi*i/nv
        for j in range(nu):
            ph = 2*math.pi*j/nu
            vs.append((c[0]+r*math.cos(th), c[1]+r*math.sin(th)*math.cos(ph), c[2]+r*math.sin(th)*math.sin(ph)))
    for i in range(nv):
        for j in range(nu):
            fs.append((i*nu+j, i*nu+(j+1) % nu, (i+1)*nu+(j+1) % nu, (i+1)*nu+j))
    return vs, fs


def box_mesh(c, size, roll=0.0):
    hx, hy, hz = (x/2 for x in size); ca, sa = math.cos(math.radians(roll)), math.sin(math.radians(roll))
    vs = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                y, z = sy*hy, sz*hz
                vs.append((c[0]+sx*hx, c[1]+ca*y-sa*z, c[2]+sa*y+ca*z))
    fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return vs, fs


def panel_mesh(corners, t):
    c = [Vector(p) for p in corners]; n = (c[1]-c[0]).cross(c[3]-c[0]).normalized()*t/2
    vs = [tuple(p-n) for p in c]+[tuple(p+n) for p in c]
    fs = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    return vs, fs


def capsule_mesh(p):
    cy, cz = p['centre']; r = p['radius']
    prof = [(p['x0']+r*(1-math.cos(math.pi/2*k/6)), r*math.sin(math.pi/2*k/6)) for k in range(7)]
    prof += [(p['x1']-r*(1-math.cos(math.pi/2*k/6)), r*math.sin(math.pi/2*k/6)) for k in reversed(range(7))]
    prof = [(p['x0'], 0.0)]+[(x, max(rr, 1e-3)) for x, rr in prof][1:-1]+[(p['x1'], 0.0)]
    vs, fs = rev_mesh(prof, [(0.0, 360.0)], True)
    return [(x, y+cy, z+cz) for x, y, z in vs], fs


MATS = {}


def mat(func, alpha=1.0, emit=0.0):
    key = (func, round(alpha, 3), emit)
    if key in MATS:
        return MATS[key]
    rgba = PALETTE.get(func, ('', (.8, .8, .8, 1), ''))[1]
    m = bpy.data.materials.new(f'VTX_{func}'+(f'_A{alpha:g}' if alpha < 1 else '')+(f'_E{emit:g}' if emit else ''))
    m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    base = tuple(0.35+0.4*x for x in rgba[:3]) if func == 'STRUCTURE' else rgba[:3]
    b.inputs['Base Color'].default_value = (*base, 1); b.inputs['Metallic'].default_value = 0.4; b.inputs['Roughness'].default_value = 0.5
    if emit:
        b.inputs['Emission Color'].default_value = (*rgba[:3], 1); b.inputs['Emission Strength'].default_value = emit
    if alpha < 1:
        b.inputs['Alpha'].default_value = alpha
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            pass
    m.diffuse_color = (*rgba[:3], alpha)
    MATS[key] = m
    return m


PART_LOG = []


def tag(ob, gen, status, vtx, source, rep='HARDWARE', note=None, **extra):
    ob['vtx_id'] = vtx; ob['generation'] = gen; ob['evidence_status'] = status; ob['representation'] = rep
    ob['source'] = source; ob['revision'] = REVISION; ob['wf_owner'] = 'wayfarer.t05'
    ob['wf_status'] = 'NON-CANON research geometry (work/vertex-blender, T05 Stage B)'
    if note:
        ob['vtx_note'] = note
    for k, v in extra.items():
        ob[k] = v
    PART_LOG.append((gen, status, ob.name, vtx, source, note or ''))


def make(name, shape, coll, func, gen, status, vtx, source, rep='HARDWARE', note=None, alpha=None, wire=False, cut=None, trace=None, **kw):
    """One object: name gets '<gen>_<ES|PP|PR|CI>_' so the status reads in the outliner."""
    full = f"{gen}_{CODE[status]}_{name}"
    if cut and shape in ('box', 'tube', 'panel', 'capsule', 'sphere'):
        c = kw.get('centre') or (kw['points'][len(kw['points'])//2] if 'points' in kw else kw['corners'][0] if 'corners' in kw else (0, 0, 0))
        if shape == 'capsule':
            c = (0.0, *kw['centre'])
        az = math.degrees(math.atan2(c[2], c[1])) % 360 if math.hypot(c[1], c[2]) > 0.5 else None
        if az is not None and cut[0] <= az <= cut[1]:
            return None
    if shape == 'ring':
        cy, cz = kw.get('centre', (0.0, 0.0)); r0 = kw['r0']
        prof = [(kw['x0'], r0), (kw['x1'], r0), (kw['x1'], kw['r1']), (kw['x0'], kw['r1'])] if r0 > 0 else \
            [(kw['x0'], 0.0), (kw['x1'], 0.0), (kw['x1'], kw['r1']), (kw['x0'], kw['r1'])]
        arcs, closed = arcs_of(kw, cut if (cy, cz) == (0.0, 0.0) else None)
        vs, fs = rev_mesh(prof, arcs, closed); vs = [(x, y+cy, z+cz) for x, y, z in vs]
    elif shape == 'frustum':
        ri0, ri1 = kw.get('ri0'), kw.get('ri1')
        prof = [(kw['x0'], 0.0), (kw['x1'], 0.0), (kw['x1'], kw['r1']), (kw['x0'], kw['r0'])] if ri0 is None else \
            [(kw['x0'], ri0), (kw['x1'], ri1), (kw['x1'], kw['r1']), (kw['x0'], kw['r0'])]
        arcs, closed = arcs_of(kw, cut)
        vs, fs = rev_mesh(prof, arcs, closed)
    elif shape == 'torus':
        nvv = 10; prof = [(kw['x']+kw['a']*math.cos(2*math.pi*j/nvv), kw['R']+kw['a']*math.sin(2*math.pi*j/nvv)) for j in range(nvv)]
        arcs, closed = arcs_of(kw, cut)
        vs, fs = rev_mesh(prof, arcs, closed)
    elif shape == 'profile':                                       # any closed (x, r) polygon revolved about the axis (Rev 4 layered sections)
        arcs, closed = arcs_of(kw, cut)
        vs, fs = rev_mesh(kw['prof'], arcs, closed)
    elif shape == 'sphere':
        vs, fs = sphere_mesh(kw['centre'], kw['radius'])
    elif shape == 'box':
        vs, fs = box_mesh(kw['centre'], kw['size'], kw.get('roll', 0.0))
    elif shape == 'tube':
        vs, fs = tube_mesh(kw['points'], kw['radius'])
    elif shape == 'panel':
        vs, fs = panel_mesh(kw['corners'], kw['thickness'])
    elif shape == 'capsule':
        vs, fs = capsule_mesh(kw)
    else:
        raise ValueError(shape)
    if not fs:
        return None
    me = bpy.data.meshes.new(full); me.from_pydata(vs, [], fs); me.validate(); me.update()
    ob = bpy.data.objects.new(full, me); coll.objects.link(ob)
    al = ALPHA[status] if alpha is None else alpha
    rgba = PALETTE.get(func, ('', (.8, .8, .8, 1), ''))[1]
    emit = 2.5 if func in ('VIS_PLASMA', 'VIS_BEAM', 'VIS_CONFLICT') else 0.0
    ob.data.materials.append(mat(func, al, emit)); ob.color = (*rgba[:3], al)
    if al < 1:
        ob.show_transparent = True
    if wire:
        ob.display_type = 'WIRE'
    tag(ob, gen, status, vtx, source, rep, note, function=PALETTE.get(func, (func,))[0], **(trace or {}))
    return ob


def text(name, body, loc, coll, gen='ALL', size=6.0, facing='side', align='LEFT', rot=None):
    cu = bpy.data.curves.new(name, 'FONT'); cu.body = body; cu.size = size; cu.align_x = align
    ob = bpy.data.objects.new(f'{gen}_CI_LBL_{name}', cu); coll.objects.link(ob); ob.location = loc
    ob.rotation_euler = rot or ((math.radians(90), 0, 0) if facing == 'side' else (0, 0, 0) if facing == 'top' else (math.radians(90), 0, math.radians(-90)))
    ob.data.materials.append(mat('VIS_LABEL', emit=2.0)); ob.color = (0.98, 0.95, 0.85, 1)
    tag(ob, gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-NONE', 'label', rep='VISUALIZATION')
    return ob


def pol(x, r, az):
    t = math.radians(az)
    return (x, r*math.cos(t), r*math.sin(t))


def new_coll(name, parent, tag_color='NONE'):
    c = bpy.data.collections.new(name); parent.children.link(c); c.color_tag = tag_color
    return c


# ----------------------------------------------------------------------------------------------------------------------------------
# the canonical ship
# ----------------------------------------------------------------------------------------------------------------------------------
def local_ship():
    """The canonical vehicle with its linked subsystems made local (localise_ship.py), cached beside the source asset's mtime."""
    import subprocess
    cache = Path(a.ship_cache)
    if not cache.exists() or cache.stat().st_mtime < SHIP.stat().st_mtime:
        subprocess.run([bpy.app.binary_path, '-b', '--factory-startup', '--python-exit-code', '1', '--python', str(HERE/'localise_ship.py'), '--',
                        str(cache)], check=True)
    return cache


def append_ship(label):
    import time; t0 = time.time()
    with bpy.data.libraries.load(str(local_ship()), link=False) as (src, dst):
        dst.collections = ['WF_WAYFARER_001']
    c = dst.collections[0]
    for ch in c.children_recursive:
        if ch.name.split('.')[0] in ('40_SIM_RIG', '30_CAMERAS'):
            ch.hide_viewport = True; ch.hide_render = True
    c.name = label
    print('WF_VTX appended', label, round(time.time()-t0, 1), 's', flush=True)
    return c


def ship_objects(ship):
    """Every object the ship shows, including the contents of collections its assembly empties instance."""
    seen, out = set(), []
    stack = [ship]
    while stack:
        c = stack.pop()
        for o in c.all_objects:
            if o is None or o.name in seen:
                continue
            seen.add(o.name); out.append(o)
            if o.instance_type == 'COLLECTION' and o.instance_collection:
                stack.append(o.instance_collection)
    return out


def fingerprint(ship):
    """Local state of every canonical object: transform, parent, visibility, mesh size (evaluation-independent)."""
    out = []
    for o in ship_objects(ship):
        me = o.data if o.type == 'MESH' else None
        out.append((o.name, o.type, tuple(round(v, 5) for row in o.matrix_basis for v in row), o.parent.name if o.parent else '',
                    o.hide_render, o.hide_viewport,
                    (len(me.vertices), len(me.polygons)) if me else None))
    return sorted(out, key=str)


SUPERSEDED = ('Nozzle_0', 'DRIVE_DEBUG_', 'Assembly_PROPULSION', 'Assembly_SHIELDING')


def _roots(coll):
    hidden = {c.name for c in coll.children_recursive if c.hide_render}
    objs = [o for o in coll.all_objects if not any(u.name in hidden for u in o.users_collection) and not o.hide_render]
    keep = set(objs)
    return [o for o in objs if o.parent not in keep]


def _tree(o):
    return [o]+list(o.children_recursive)


def prepare_working_copy(canon, gen):
    """A working copy that shares the canonical objects (links only, nothing copied or edited): one new instance empty per subsystem,
    the superseded drive and shielding assemblies left out, idle H2 vessels left out (V4/V5), and every subsystem split at the tank-farm
    front so its bow part is instanced again shifted by the T-B stretch. The canonical collection itself is never touched."""
    work = bpy.data.collections.new(f'WORK_VERTEX_{gen}_SHIP'); work.color_tag = 'COLOR_07'
    blades = bpy.data.collections.new(f'WORK_VERTEX_{gen}_CANON_HOT_BLADES'); blades.color_tag = 'COLOR_01'
    dx = ENV[gen]['tanks_TB']['bow_shift_m']; x_from = C['tank_farm_x_m'][1]+0.05
    log = {'left_out_assemblies': [], 'left_out_objects': 0, 'bow_objects': 0, 'aft_objects': 0, 'bow_shift_m': dx, 'split_x_m': x_from}
    for asm in [o for o in canon.all_objects if o.instance_type == 'COLLECTION' and o.instance_collection]:
        base = asm.name.split('.')[0]
        if base.startswith(SUPERSEDED):
            log['left_out_assemblies'].append(base); continue
        sub = asm.instance_collection
        parts = {'AFT': bpy.data.collections.new(f'{sub.name}_{gen}_AFT'), 'BOW': bpy.data.collections.new(f'{sub.name}_{gen}_BOW'),
                 'HOT': bpy.data.collections.new(f'{sub.name}_{gen}_HOT_BLADES')}
        for p in parts.values():
            p.instance_offset = sub.instance_offset
        for r in _roots(sub):
            rb = r.name.split('.')[0]
            if rb.startswith(SUPERSEDED) or (gen in ('V4', 'V5') and rb.startswith('Fuel_Tank_') and rb.endswith('_H2')):
                log['left_out_objects'] += len(_tree(r)); log.setdefault('left_out_names', []).append(rb); continue
            pts = [o.matrix_world @ Vector(v) for o in _tree(r) for v in (o.bound_box if o.type in ('MESH', 'CURVE', 'FONT') else [(0, 0, 0)])]
            key = 'BOW' if min(v.x for v in pts) >= x_from else 'AFT'
            if sub.name.startswith('WF_THERMAL') and max(v.x for v in pts) <= C['hot_blades']['x_m'][1]+0.3:
                key = 'HOT'                          # the 1,800 K blade sections (X -133.25 to 48.9 m); bulkhead, WARM and LOW zones stay
            for o in _tree(r):
                if o.name not in parts[key].objects:
                    parts[key].objects.link(o)
            log[key.lower()+'_objects'] = log.get(key.lower()+'_objects', 0)+len(_tree(r))
        for key, p in parts.items():
            if not p.objects:
                bpy.data.collections.remove(p); continue
            e = bpy.data.objects.new(f'WORK_{gen}_{base}_{key}', None); e.instance_type = 'COLLECTION'; e.instance_collection = p
            e.matrix_world = asm.matrix_world.copy()
            if key == 'BOW':
                e.location.x += dx
            (blades if key == 'HOT' else work).objects.link(e)
    print('WF_VTX working copy', gen, log, flush=True)
    return work, blades, log


# ----------------------------------------------------------------------------------------------------------------------------------
# one generation
# ----------------------------------------------------------------------------------------------------------------------------------
CHECKS = {'canon': C, 'generations': {}}


def gen_collections(gen, top):
    root = new_coll(f'VAR_VERTEX_{gen}', top, 'COLOR_07')
    out = {}
    for k, nm in GROUPS.items():
        out[k] = new_coll(f'VAR_VERTEX_{gen}_{k}_{nm}', root, PALETTE[GROUP_FUNC[k]][2])
    return root, out


BREECH_PARTS = ('FDP1_Pellet_Magazine', 'FDP1_Axial_Plug', 'FDP1_Target_Injection_Axis')


def build_fdp_parts(gen, R, colls, cut=None, ghost=False, breech=None):
    for p in G.parts(R)+[t for t in G.tank_parts(R) if t['coll'] == '10:T-B']:
        if p['name'].startswith(REPLACED) or p.get('shape') == 'text':
            continue
        key = FDP_TO['10' if p['coll'].startswith('10') else p['coll']]
        if key is None:
            continue
        st = STATUS[p['status']]
        if p['name'].startswith('FDP1_TB_'):
            st = 'PARAMETRIC_PLACEHOLDER'
        kw = {k: v for k, v in p.items() if k not in ('name', 'coll', 'func', 'shape', 'status', 'alpha', 'note')}
        al = p['alpha'] if p['alpha'] < 1 else None
        if ghost:
            al = 0.12
        target = breech if (breech is not None and p['name'].startswith(BREECH_PARTS)) else colls[key]
        make(p['name'].replace('FDP1_', ''), p['shape'], target, p['func'], gen, st, vtx_of(p['name']),
             f'solve:{gen} fdp1 geometry.parts', note=p.get('note'), alpha=al, wire=ghost, cut=cut, **kw)


def build_nozzle(gen, R, e, colls, cut=None, ghost=False, support=None, env_coll=None, bumper_coll=None):
    """Loops redrawn as 12 replaceable segments per loop, trim joints clocked 45 deg loop to loop (VTX-03A, 03E), plus closure coils,
    guard rings, local bumpers and coil load-path candidates."""
    loops = R['nozzle']['loops']; src = f'solve:{gen} nozzle.loops'
    sh = R['shield']; xSA = R['layout']['x_shield_aft']
    g = 0.6 if not ghost else 0.0
    for i, L in enumerate(loops):
        clock = 45.0*i
        env = e['loops'][i]['envelope_r_m']
        if ghost:
            make(f"{L['name']}_Envelope", 'torus', colls['02'], 'MAIN_PROPULSION', gen, 'ENGINEERING_SUPPORTED', 'VTX-02', src,
                 x=L['x'], R=L['r'], a=max(env, 0.6), alpha=0.25, wire=True)
            continue
        for s in range(PR_SPLITS):
            a0 = clock+360.0*s/PR_SPLITS+g/2; a1 = a0+360.0/PR_SPLITS-g
            trim = 1+int(((360.0*s/PR_SPLITS) % 360)//90)
            make(f"{L['name']}_Seg_{s+1:02d}", 'torus', colls['02'], 'MAIN_PROPULSION', gen, 'ENGINEERING_SUPPORTED', 'VTX-03E', src,
                 note=f'replaceable segment {s+1}/12 (30 deg) of trim sector {trim}; joints clocked {clock:.0f} deg (VTX-03A)',
                 x=L['x'], R=L['r'], a=L['minor_radius_m']*1.6, arc=(a0, a1), cut=cut, trim_sector=trim)
            make(f"{L['name']}_Cryostat_{s+1:02d}", 'torus', colls['02'], 'LOW_RADIATOR', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-02B', src,
                 note='cryostat envelope (T03 0.4-0.7 m)', x=L['x'], R=L['r'], a=env, arc=(a0, a1), alpha=0.3, cut=cut)
        for t in range(4):                                         # trim joints: bright markers
            az = clock+90.0*t
            make(f"{L['name']}_Trim_Joint_{t+1}", 'sphere', colls['02'], 'VIS_BEAM', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-03A', src,
                 rep='VISUALIZATION', note='trim-sector joint (sector clock, not a helix)', centre=pol(L['x'], L['r'], az), radius=env*2.2, alpha=0.9, cut=cut)
        ph = math.radians(L['phi_deg']); off = env*1.05
        make(f"{L['name']}_Armour_Shoe", 'torus', colls['03'], 'SHIELD', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-06B', src,
             note=f"burn-face armour {L['armour_kg']/1e3:.1f} t", x=L['x']-off*math.cos(ph), R=L['r']-off*math.sin(ph), a=env*0.55, cut=cut)
        make(f"{L['name']}_Lattice_Band", 'torus', colls['02'], 'HELIUM3', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-02A', src,
             note='Fiji lattice carrier band, outer face (canon properties only)', x=L['x']+env*0.4*math.cos(ph), R=L['r']+env*0.9*math.sin(ph),
             a=env*0.45, alpha=0.7, cut=cut)
        if L['r'] > 45.0:                                          # local bumpers outside the forward shield's r 45 m shadow (VTX-08A/F)
            make(f"{L['name']}_Local_Bumper", 'torus', bumper_coll if bumper_coll is not None else colls['10'], 'SHIELD', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-08F', 'T02 HANDOFF E',
                 note='local bumper, 2 m stand-off on both faces (outside r 45 m)', x=L['x'], R=L['r'], a=env+2.0, alpha=0.15, cut=cut)
        if i >= 1:                                                 # guard rings 22.5 m forward of L2 and L3 (VTX-08F, scaled to the loop radii)
            make(f"{L['name']}_Guard_Ring", 'torus', bumper_coll if bumper_coll is not None else colls['10'], 'SHIELD', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-08F', 'T02 HANDOFF E (20-25 m fwd)',
                 note='guard ring 0.8 m wide, 22.5 m forward of the loop', x=L['x']+22.5, R=L['r'], a=0.4, cut=cut)
    for c in e['closure_coils']:
        nm = f"Closure_{c['name']}"; s3 = 'T03 nozzle_results.json C_W15, scaled by R_s'
        if ghost:
            make(nm+'_Envelope', 'torus', colls['02'], 'MAIN_PROPULSION', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-03D', s3, x=c['x_m'], R=c['r_m'],
                 a=c['envelope_r_m'][1], alpha=0.2, wire=True)
            continue
        make(nm+'_Winding', 'torus', colls['02'], 'MAIN_PROPULSION', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-03D', s3,
             note=f"winding minor {c['winding_minor_m']:.2f} m; hoop 3-7 GN (T03); UNBOOKED structure 855-1,281 t", x=c['x_m'], R=c['r_m'],
             a=c['winding_minor_m'], cut=cut, unbooked='closure-coil structure 855-1,281 t')
        make(nm+'_Envelope', 'torus', env_coll if env_coll is not None else colls['02'], 'LOW_RADIATOR', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-03D', s3,
             note=f"Rev 1-3 envelope (C2 copied C1's; superseded in V4 by rev4.json coil_assembly): cryostat + warm eddy screen envelope r {c['envelope_r_m'][0]:.1f}-{c['envelope_r_m'][1]:.1f} m", x=c['x_m'], R=c['r_m'],
             a=c['envelope_r_m'][1], alpha=0.22, cut=cut)
    if ghost:
        return
    # load-path candidates: C1 -> shield frame ring (compression), C2 -> C1 and C2 -> L1 (tension ties); unsized (ISS-003)
    c1, c2 = e['closure_coils']; L1 = loops[0]
    ring_r = sh['radius_hw_aft_m']+1.0
    sup = support if support is not None else colls['08']
    make('Coil_Reaction_Ring', 'torus', sup, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-03D', 'T05 PR (ISS-003)',
         note='candidate reaction ring on the shield aft face carrying C1/C2 axial force into the shield frame; unsized',
         x=xSA-0.8, R=ring_r, a=0.8, cut=cut)
    for j in range(PR_COIL_STRUTS):
        az = 360.0*j/PR_COIL_STRUTS+30.0
        make(f'C1_Strut_{j+1}', 'tube', sup, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-02D', 'T05 PR (ISS-003)',
             note='C1 -> shield reaction ring, compression member for 0.2-1.9 GN inter-coil attraction; unsized',
             points=[pol(c1['x_m'], c1['r_m'], az), pol(xSA-0.8, ring_r, az)], radius=0.6, cut=cut)
        make(f'C2_Tie_C1_{j+1}', 'tube', sup, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-02D', 'T05 PR (ISS-003)',
             note='C2 -> C1 tie (one candidate path); unsized', points=[pol(c2['x_m'], c2['r_m'], az), pol(c1['x_m'], c1['r_m'], az)], radius=0.4, cut=cut)
        make(f'C2_Tie_L1_{j+1}', 'tube', sup, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-02D', 'T05 PR (ISS-003)',
             note='C2 -> L1 tie (alternative candidate path); unsized', points=[pol(c2['x_m'], c2['r_m'], az+15), pol(L1['x'], L1['r'], az+15)],
             radius=0.4, alpha=0.35, cut=cut)


def build_module(gen, R, e, colls, cut=None, launch=None):
    """Launcher, catcher, ignitor line, tritium store in the equipment module (VTX-01H, 01G); returns the corridor fit."""
    lay = R['layout']; xSF = lay['x_shield_fwd']; xMF = lay['x_module_fwd']
    plug = R['shield']['streaming']['pellet_bore']
    x_mag = xSF+14.5; x_plug = xSF+16.0
    v = e['launcher_one_in_flight_m_s']; free = x_mag-xSF
    lc = launch if launch is not None else colls['07']
    make('Target_Launcher_Barrel', 'tube', lc, 'MAIN_PROPULSION', gen, 'PROTOTYPE', 'VTX-01H', 'T05 PR_LAUNCHER_LEN (UNKNOWN 10-20 m)',
         note=f'barrel {PR_LAUNCHER_LEN:.0f} m, >= {v/1e3:.1f} km/s for one target in flight; length UNKNOWN', unbooked='launcher',
         points=[(xSF+PR_LAUNCHER_LEN, 0, 0), (xSF+0.2, 0, 0)], radius=PR_LAUNCHER_R, cut=cut)
    make('Sabot_Catcher', 'ring', lc, 'MAIN_PROPULSION', gen, 'PROTOTYPE', 'VTX-01H', 'T05 PR', note='annular sabot trap at the muzzle',
         x0=xSF+0.2, x1=xSF+2.2, r0=0.7, r1=1.8, cut=cut, unbooked='launcher')
    make('Fast_Ignitor_Line', 'tube', colls['04'], 'VIS_BEAM', gen, 'PROTOTYPE', 'VTX-01G', 'T04 (volume UNKNOWN)', alpha=0.8,
         note='fast-ignitor beam line beside the bore; it needs its own shield port (another streaming path)',
         points=[pol(xMF-2.0, PR_IGNITOR_OFFSET, 120), pol(xSF+0.2, PR_IGNITOR_OFFSET, 120)], radius=PR_IGNITOR_R, cut=cut)
    make('Fast_Ignitor_Port', 'tube', colls['03'], 'VIS_XRAY', gen, 'PROTOTYPE', 'VTX-01G', 'T05 PR', alpha=0.8,
         note='ignitor port through the shadow shield', points=[pol(xSF+0.2, PR_IGNITOR_OFFSET, 120), pol(lay['x_shield_aft']-0.2, PR_IGNITOR_OFFSET*0.95, 120)],
         radius=0.25, cut=cut)
    make('Tritium_Store', 'sphere', colls['07'], 'HYDROGEN', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-01G', 'T04 43-144 kg per mission', alpha=0.5,
         note='tritium store, containment UNKNOWN', centre=pol(xSF+26.0, 4.2, 300), radius=PR_TRITIUM_R, cut=cut, unbooked='tritium store')
    clash = PR_LAUNCHER_LEN > free
    return {'shield_face_to_magazine_m': free, 'plug_from_shield_face_m': x_plug-xSF, 'plug_length_m': plug['plug_length_m'],
            'barrel_m': PR_LAUNCHER_LEN, 'barrel_clashes_magazine_and_plug': clash, 'one_in_flight_m_s': v,
            'accel_g_if_barrel_fits_free_length': v*v/(2*free)/9.80665, 'accel_g_at_20m': v*v/(2*PR_LAUNCHER_LEN)/9.80665}


def band_shares():
    from collections import defaultdict
    b = defaultdict(float)
    for v in LEDGER.values():
        b[v['T_K']] += v['area_m2']
    b = {k: v for k, v in b.items() if k >= 550}
    t = sum(b.values())
    return [(T, b[T]/t) for T in sorted(b, reverse=True)]


def build_wings(gen, R, e, colls, ghost=False, graded=None, coll=None, label='', alpha_hot=None, tip_override=None):
    """W2 wings at az 0/180 in the z = 0 plane: 1,800 K root band, warm circuit bands (T01 proportions) outward, thermal break, two spars,
    ribs every 1 km, a droplet generator bar on the forward edge and a collector on the aft edge, root boom and struts. Every part goes
    into one collection so a layout swaps as a unit. graded = (hot x0, hot x1, hot r1): the hot band stops at hot x1 (the canon
    RADIATOR_FRONT) and the forward root corner becomes a 550 K capacitor band; tip_override keeps the warm area for that layout."""
    w = e['wing']; x0, x1 = w['x_m']; h0, h1 = w['hot_band_r_m']; tip = tip_override or w['tip_r_m']; src = f'solve:{gen} thermal.layouts.W2'
    out = coll or colls['05']
    hx0, hx1, hr1 = (x0, x1, h1) if graded is None else graded
    if graded is not None:
        src = 'rev2.json thermal.preferred_rev2 (same hot and warm areas as solve:V4)'
    for side, az in (('P', 0.0), ('S', 180.0)):
        if ghost:
            make(f'Wing_{side}_Outline', 'panel', out, 'WARM_RADIATOR', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-07', src, alpha=0.15, wire=True,
                 corners=[pol(x0, h0, az), pol(x1, h0, az), pol(x1, tip, az), pol(x0, tip, az)], thickness=0.5)
            continue
        make(f'Wing_{side}_Hot_Band{label}', 'panel', out, 'HOT_RADIATOR', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-07F', src,
             note=f"1,800 K band r {h0:.0f}-{hr1:.0f} m, X {hx0:.1f} to {hx1:.1f} m", alpha=alpha_hot,
             corners=[pol(hx0, h0, az), pol(hx1, h0, az), pol(hx1, hr1, az), pol(hx0, hr1, az)], thickness=0.4)
        if graded is not None:
            make(f'Wing_{side}_Root_Capacitor_Band{label}', 'panel', out, 'WARM_RADIATOR', gen, 'PROTOTYPE', 'VTX-07E', 'T05 graded layout',
                 note='550 K capacitor circuit in the forward root corner by the rings (counted in the warm area)', alpha=0.45,
                 corners=[pol(hx1+2, h0, az), pol(x1, h0, az), pol(x1, hr1, az), pol(hx1+2, hr1, az)], thickness=0.3)
            make(f'Wing_{side}_Chordwise_Thermal_Break{label}', 'tube', out, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-07D', 'T05 graded layout',
                 note='chordwise 1,800 K / 550 K thermal break with expansion joint (L-shaped break)', points=[pol(hx1+1, h0, az), pol(hx1+1, hr1, az)], radius=0.9)
        r = hr1+2.0
        for T, sh in band_shares():
            dr = sh*(tip-hr1-2.0)
            make(f'Wing_{side}_Warm_{T}K{label}', 'panel', out, 'WARM_RADIATOR', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-07B',
                 f'{src}; band shares T01 ledger S1_advanced_eta0.30', rep='MIXED',
                 note=f'tin droplet sheet, {T} K circuit band (exists only while the drive runs)', alpha=0.22+0.2*(T-550)/450,
                 corners=[pol(x0+4, r, az), pol(x1-4, r, az), pol(x1-4, r+dr, az), pol(x0+4, r+dr, az)], thickness=0.2)
            make(f'Wing_{side}_Manifold_{T}K{label}', 'tube', out, 'WARM_RADIATOR', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-07E', src,
                 note=f'thermal break and manifold at the {T} K band root', points=[pol(x0, r, az), pol(x1, r, az)], radius=0.8)
            r += dr
        make(f'Wing_{side}_Thermal_Break{label}', 'tube', out, 'STRUCTURE', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-07D', src,
             points=[pol(x0, hr1+1.0, az), pol(x1, hr1+1.0, az)], radius=1.0)
        for nm, xe, rad in (('Spar_Aft', x0, 1.2), ('Spar_Fwd', x1, 1.2)):
            make(f'Wing_{side}_{nm}{label}', 'tube', out, 'STRUCTURE', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-07D', src,
                 note='12.5 kg/m CFRP spar (V4 package); buckling of the 10 km compression spar not modelled (ISS-005)',
                 points=[pol(xe, h0, az), pol(xe, tip, az)], radius=rad)
        k = 1; rr = h0+PR_RIB_PITCH
        while rr < tip:
            make(f'Wing_{side}_Rib_{k:02d}{label}', 'tube', out, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-07D', 'T05 PR_RIB_PITCH',
                 note='chordwise rib / deployment hinge station (1 km pitch)', points=[pol(x0, rr, az), pol(x1, rr, az)], radius=0.7)
            k += 1; rr += PR_RIB_PITCH
        make(f'Wing_{side}_Droplet_Generator{label}', 'tube', out, 'WARM_RADIATOR', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-07B', 'T01 REPORT 5',
             rep='HARDWARE', note='droplet generator bar on the forward edge: drops fly along -X', points=[pol(x1-2, hr1+2, az), pol(x1-2, tip, az)], radius=1.6, alpha=0.8)
        make(f'Wing_{side}_Droplet_Collector{label}', 'tube', out, 'WARM_RADIATOR', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-07B', 'T01 REPORT 5',
             rep='HARDWARE', note='collector trough on the aft edge', points=[pol(x0+2, hr1+2, az), pol(x0+2, tip, az)], radius=2.4, alpha=0.8)
        make(f'Wing_{side}_Root_Boom{label}', 'tube', out, 'STRUCTURE', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-07D', src,
             points=[pol(x0, h0, az), pol(x1, h0, az)], radius=1.0)
        for j, xr in enumerate((x0+20, (x0+x1)/2, x1-20)):
            make(f'Wing_{side}_Root_Strut_{j}{label}', 'tube', out, 'STRUCTURE', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-07D', src,
                 points=[pol(xr, 6.4, az), pol(xr, h0, az)], radius=0.6)


def build_alternatives(gen, e, coll):
    """Outlines only: graded hot band (D-T05-1), W3, tandem R2, panel skin, tip bracket circles."""
    w = e['wing']; x0, x1 = w['x_m']; h0, h1 = w['hot_band_r_m']; tip = w['tip_r_m']
    alts = {r['id']: r for r in screen_data['V4_radiator_alternatives']}
    # W3: three wings between the canon blades (az 90/210/330)
    w3 = alts['R1-W3']['tip_r_m']
    for az in (90.0, 210.0, 330.0):
        make(f'ALT_W3_Wing_{int(az)}', 'panel', coll, 'VIS_ALT', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-07D', 'screen.json R1-W3 (layout only)',
             rep='VISUALIZATION', note=f'W3 alternative, tip {w3:,.0f} m, view-factor penalty x1.15; mass not re-closed', alpha=0.35,
             corners=[pol(x0, h0, az), pol(x1, h0, az), pol(x1, w3, az), pol(x0, w3, az)], thickness=1.0)
    # tandem R2: aft wing and forward wing on the T-B stretch, tip 5,456 m
    r2 = alts['R2']['tip_r_m']; xf0 = C['tank_farm_x_m'][1]+5.0; xf1 = C['tank_farm_x_m'][1]+e['tanks_TB']['added_length_m']
    for az in (0.0, 180.0):
        for nm, (a_, b_) in (('Aft', (x0, x1)), ('Fwd', (xf0, xf1))):
            make(f'ALT_R2_{nm}_Wing_{int(az)}', 'panel', coll, 'VIS_ALT', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-07D', 'screen.json R2 (geometry only)',
                 rep='VISUALIZATION', note=f'tandem W2: both pairs to tip {r2:,.0f} m at equal area; second manifold set not closed', alpha=0.35,
                 corners=[pol(a_, h0, az), pol(b_, h0, az), pol(b_, r2, az), pol(a_, r2, az)], thickness=1.0)
    # end-view spokes (CI, 30 m radius so they read at 30 km scale): W2 baseline, W3, tandem R2
    for nm, azs, r, func in (('W2_baseline', (0.0, 180.0), tip, 'HOT_RADIATOR'), ('W3', (90.0, 210.0, 330.0), w3, 'VIS_ALT'), ('R2_tandem', (0.0, 180.0), r2, 'VIS_LABEL')):
        for az in azs:
            make(f'ALT_Spoke_{nm}_{int(az)}', 'tube', coll, func, gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-07', 'screen.json', rep='VISUALIZATION',
                 note=f'{nm} wing, root to tip {r:,.0f} m (end-view marker)', points=[pol(x0-60 if nm == 'R2_tandem' else x0-30, 10.0, az+(4 if nm == 'R2_tandem' else 0)),
                 pol(x0-60 if nm == 'R2_tandem' else x0-30, r, az+(4 if nm == 'R2_tandem' else 0))], radius=30.0 if nm != 'R2_tandem' else 22.0, alpha=1.0)
        az = azs[0]
        text(f'alt_{nm}', f'{nm}: tip {r:,.0f} m', pol(x0-80, r+300, az+(8 if nm == 'R2_tandem' else 0)), coll, gen=gen, size=500, facing='end')
    # tip brackets as circles about the axis at mid-chord
    xm = (x0+x1)/2
    for r, nm in ((3400.0, 'driver_0p45'), (6700.0, '670K'), (14500.0, 'launcher_12kms'), (ENV['V5']['wing']['tip_r_m'], 'V5_bound')):
        make(f'TIP_{nm}', 'torus', coll, 'VIS_ALT' if nm != 'V5_bound' else 'MAIN_PROPULSION', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-07',
             'convergence.json V4 bands', rep='VISUALIZATION', note=f'tip radius {r:,.0f} m ({nm})', x=xm, R=r, a=25.0, alpha=0.6)


def build_skirts(gen, R, e, coll_root):
    """Three dust-protection alternatives (VTX-08E/F): A full skirt to r 45 m with dock apertures, B short skirt ending aft of ring A,
    C no skirt (guard rings and local bumpers only, drawn with the nozzle). The skirt lies on the hardware cone; slotted at the wing planes."""
    xB = e['x_burn_m']; t = math.tan(math.radians(e['hardware_cone_deg'])); xs = e['x_shield_aft_m']
    x45 = xB+45.0/t
    out = {}
    for key, xe, note in (('A_FULL', x45, 'skirt on the hardware cone to r 45 m; both docking corridors pierce it'),
                          ('B_SHORT', PR_SKIRT_SHORT_X, 'skirt ending 10 m aft of ring A; farm and docks rely on bumpers'),
                          ('B2_DOCK_CLEAR', REV2['dust']['options']['B2_DOCK_CLEAR']['edge_x_m'],
                           'Rev 2: skirt ending 3.6 m aft of the docking corridors (shadow r 36.0 m covers the farm and T-B tanks); mounts on the Q45 bypass collar'),
                          ('C_BUMPERS_ONLY', None, 'no skirt: guard rings and local bumpers (in 02_NOZZLE / 10) and sector replacement')):
        c = new_coll(f'VAR_VERTEX_{gen}_10_DUST_{key}', coll_root, 'COLOR_03'); out[key] = c
        if xe is None:
            continue
        r0 = (xs-xB)*t; r1 = (xe-xB)*t
        for a0, a1 in ((2.0, 178.0), (182.0, 358.0)):
            make(f'Skirt_{key}_{int(a0)}', 'frustum', c, 'SHIELD', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-08E', f'T02 HANDOFF E, re-apexed to solve:{gen}',
                 note=note+'; slots along the wing planes (burn rays)', x0=xs, r0=r0, x1=xe, r1=r1, ri0=r0-0.15, ri1=r1-0.15, arc=(a0, a1),
                 alpha=0.28, unbooked='skirt 22-90 t')
        if key == 'A_FULL':
            for nm, az, xd in (('Primary', C['dock_primary']['az_deg'], C['dock_primary']['x_m']), ('Service', C['dock_service']['az_deg'], C['dock_primary']['x_m']),
                               ('Airlock', C['airlock']['az_deg'], C['airlock']['x_m'])):
                rd = (xd-xB)*t
                make(f'Skirt_A_Dock_Aperture_{nm}', 'torus', c, 'VIS_CONFLICT', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-08E', 'T05 ISS-004',
                     rep='VISUALIZATION', note=f'{nm} route pierces the skirt here (skirt r {rd:.1f} m at X {xd:.2f} m)',
                     x=xd, R=rd, a=0.6, arc=(az-6, az+6), alpha=1.0)
    return out, x45


def build_overlays(gen, R, e, coll):
    xB = e['x_burn_m']; Rs = e['stand_off_m']
    # density band ghosts of the stand-off (V4_density_scan: 43-65 m)
    for r, nm in ((43.0, 'dense_3000'), (Rs, 'nominal')):
        make(f'StandOff_{nm}', 'sphere', coll, 'VIS_XRAY', gen, 'ENGINEERING_SUPPORTED' if nm == 'nominal' else 'CONCEPTUAL_ILLUSTRATION', 'VTX-01E',
             'convergence.json V4_density_scan', rep='VISUALIZATION', note=f'X-ray stand-off {r:.1f} m', centre=(xB, 0, 0), radius=r, alpha=0.05, wire=nm != 'nominal')
    make('Injection_Path', 'tube', coll, 'DEUTERIUM', gen, 'ENGINEERING_SUPPORTED', 'VTX-01H', f'solve:{gen} injection.path',
         note=f"one target in flight on {e['injection_path_m']:.1f} m (82.7 m at a 12 km/s launcher)", points=[(R['layout']['x_shield_aft'], 0, 0), (xB, 0, 0)],
         radius=0.12, alpha=0.9)
    make('Target_In_Flight', 'sphere', coll, 'DEUTERIUM', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-01H', 'T01', rep='VISUALIZATION',
         note='the one target in the open (marker; true size about 2 cm)', centre=((R['layout']['x_shield_aft']+xB)/2, 0, 0), radius=0.4, alpha=0.9)


def build_dust_stream(gen, e, coll):
    """Braking (engine-first): the dust arrives from -X; parallel streak lines aft of the ship (overlay)."""
    xa = e['loops'][-1]['x_m']-60
    k = 0
    for r in (20.0, 60.0, 110.0, 170.0, 240.0):
        for j in range(12):
            az = 360.0*j/12+(15.0 if k % 2 else 0.0)
            make(f'Dust_Streak_{k:03d}', 'tube', coll, 'VIS_DUST', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-08D', 'T02 (braking, engine-first)',
                 rep='VISUALIZATION', points=[pol(xa-500, r, az), pol(xa-120, r, az)], radius=0.5, alpha=0.5)
            k += 1


# ----------------------------------------------------------------------------------------------------------------------------------
# Revision 2: launcher architectures, spine across the T-B stretch, closure-coil protection, docking/EVA routes, lane cores
# ----------------------------------------------------------------------------------------------------------------------------------
LOPT = {o['key']: o for o in REV2['launcher']['options']}
BREECH_X = LOPT['A']['breech_x_m']
SRC_L = 'rev2.json launcher (work/vertex-blender/rev2.py)'


def build_spine_extension(gen, e, coll):
    """PROTOTYPE structure across the T-B stretch (ISS-013): the canonical Momentum Spine (r 0.95 m) ends at X 140.75 m and the bow is
    instanced 275.4 m (V4) forward, so the forward shield would hang on nothing. Spine continuation, three sector longerons at the
    canonical sector radius (5 m, 30/150/270 deg) inside the tanks' 7.75 m inner edge, bay frames every tank length, and a crawlway."""
    dx = e['tanks_TB']['bow_shift_m']; x0 = CANON2['spine_x_m'][1]; x1 = x0+dx
    note = f'PROTOTYPE continuation across the {dx:.1f} m T-B stretch (ISS-013); sizing OPEN'
    make('Spine_Extension_TB', 'ring', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', 'T05 Rev 2', note=note, x0=x0, x1=x1, r0=0.55, r1=CANON2['spine_r_m'])
    make('Spine_Extension_Crawlway', 'tube', coll, 'SERVICE', gen, 'PROTOTYPE', 'VTX-04', 'T05 Rev 2', alpha=0.5,
         note='0.8 m clear robot/crew crawlway to the bow (bow access gap 281 m beyond the crew trunk)', points=[(x0-6.0, 0, 0), (x1, 0, 0)], radius=0.4)
    for az in (30.0, 150.0, 270.0):
        make(f'SpineExt_Longeron_{int(az)}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', 'T05 Rev 2', note=note,
             points=[pol(x0-20.0, 5.0, az), pol(x1+2.0, 5.0, az)], radius=0.3)
    x = x0+1.0; k = 0
    while x < x1:
        make(f'SpineExt_Bay_Frame_{k:02d}', 'torus', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', 'T05 Rev 2', note='bay frame at a tank joint', x=x, R=5.0, a=0.25)
        for az in (30.0, 150.0, 270.0):
            make(f'SpineExt_Bay_Spoke_{k:02d}_{int(az)}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', 'T05 Rev 2',
                 points=[pol(x, CANON2['spine_r_m'], az), pol(x, 5.0, az)], radius=0.15)
        k += 1; x += 28.6


def build_launcher(key, gen, R, e, coll, labels=True):
    """One target-injection architecture (rev2.json launcher.options[key]). Every target must be behind a shutter or out of line of sight
    at each pulse, so a chopper sits at the end of the protected run; only the line-of-sight segment (red-violet) is open."""
    o = LOPT[key]; lay = R['layout']; xB = e['x_burn_m']; xSA = e['x_shield_aft_m']; xSF = lay['x_shield_fwd']
    st = 'PROTOTYPE'
    common = dict(unbooked='launcher, chopper, sabot return')
    if key in ('A', 'B'):
        mz = o['muzzle_x_m']
        make(f'L{key}_Accelerator_Barrel', 'tube', coll, 'MAIN_PROPULSION', gen, st, 'VTX-01H', SRC_L,
             note=f"{o['accelerator_m']:.0f} m accelerator in the spine bore, {o['exit_speed_m_s']/1e3:.2f} km/s at {o['accel_g']:,.0f} g; "
                  f"{o['targets_in_barrel']:.0f} targets in the barrel at once; {LAUNCHER_KG_PER_M_NOTE}", points=[(BREECH_X, 0, 0), (mz+0.5, 0, 0)], radius=0.35, **common)
        k = 0; x = BREECH_X-12.0
        while x > mz+2:
            make(f'L{key}_Drive_Coil_{k:02d}', 'torus', coll, 'POWER', gen, st, 'VTX-01H', SRC_L, note='accelerator drive stage (pitch 12 m shown)',
                 x=x, R=0.5, a=0.12); x -= 12.0; k += 1
        make(f'L{key}_Breech_Plug', 'ring', coll, 'SHIELD', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-06A', 'solve:V4 shield.streaming.pellet_bore (moved)',
             note=f"LiH bore plug moved behind the breech: {R['shield']['streaming']['pellet_bore']['plug_length_m']:.2f} m; "
                  f"{CANON2['crew_trunk_x_m'][0]-BREECH_X-R['shield']['streaming']['pellet_bore']['plug_length_m']:.1f} m from the crew trunk",
             x0=BREECH_X+0.3, x1=BREECH_X+0.3+R['shield']['streaming']['pellet_bore']['plug_length_m'], r0=0.0, r1=0.8)
        make(f'L{key}_Breech_Loader', 'box', coll, 'MAIN_PROPULSION', gen, st, 'VTX-01H', SRC_L, note='side-loading breech (targets enter off axis)',
             centre=(BREECH_X-1.0, 1.4, 0.0), size=(2.0, 1.4, 1.2))
        make(f'L{key}_Target_Conditioning', 'box', coll, 'LOW_RADIATOR', gen, st, 'VTX-01C', SRC_L,
             note='target conditioning at the breech, outside the spine (1.5 K He-3 core)', centre=(BREECH_X-5.0, 3.2, 0.0), size=(6.0, 2.4, 2.4))
        make(f'L{key}_Target_Transfer_Line', 'tube', coll, 'DEUTERIUM', gen, st, 'VTX-01C', SRC_L,
             note=f'cryogenic target transfer from the module factory, about {BREECH_X-(xSF+15):.0f} m', points=[pol(xSF+15.0, 2.6, 90.0), pol(BREECH_X-5.0, 2.6, 90.0)],
             radius=0.12)
        make(f'L{key}_Sabot_Stripper', 'ring', coll, 'MAIN_PROPULSION', gen, st, 'VTX-01H', SRC_L,
             note=f"sabot strip and catch: {o['sabot_flow_kg_day']/1e3:.1f} t/day returned, {o['sabot_catch_W']/1e6:.0f} MW into the catcher",
             x0=xSF+6.0, x1=xSF+10.0, r0=0.4, r1=1.1)
        make(f'L{key}_Sabot_Return', 'tube', coll, 'MAIN_PROPULSION', gen, st, 'VTX-01H', SRC_L, note='sabot return to the conditioning station',
             points=[pol(xSF+8.0, 1.6, 270.0), pol(BREECH_X-5.0, 1.6, 270.0)], radius=0.08)
    if key == 'B':
        tip = o['muzzle_x_m']
        make('LB_Snout', 'frustum', coll, 'SHIELD', gen, st, 'VTX-06A', SRC_L,
             note=f"shielded snout {o['snout_m']:.1f} m aft of the shield, on the axis (side walls grazing to the burn)", x0=tip+1.5, r0=0.6, x1=xSA, r1=0.9, ri0=0.4, ri1=0.4)
        make('LB_Snout_Tip_Cartridge', 'ring', coll, 'SHIELD', gen, st, 'VTX-06A', SRC_L,
             note=f"replaceable W tip cartridge, {o['shutter_flux_W_m2']/1e6:.1f} MW/m2 X-ray ({o['tip_flux_vs_shield_face']:.2f} x the shield face)",
             x0=tip, x1=tip+1.5, r0=0.3, r1=0.75)
        make('LB_Tip_Chopper', 'ring', coll, 'VIS_CONFLICT', gen, st, 'VTX-06A', SRC_L, alpha=0.9,
             note='rotating chopper: closed at every pulse, open for the target between pulses (neutron-chopper precedent)', x0=tip+1.6, x1=tip+1.75, r0=0.0, r1=0.55)
    if key == 'A':
        make('LA_Face_Chopper', 'ring', coll, 'VIS_CONFLICT', gen, st, 'VTX-06A', SRC_L, alpha=0.9,
             note=f"rotating chopper at the shield aft face ({o['shutter_flux_W_m2']/1e6:.1f} MW/m2)", x0=xSA-0.25, x1=xSA-0.1, r0=0.0, r1=0.9)
    if key == 'C':
        az = 30.0; slope = o['exit_r_m']/(xSA-xB); xe = o['breech_x_m']
        rA = lambda x: (x-xB)*slope
        make('LC_Offset_Barrel', 'tube', coll, 'MAIN_PROPULSION', gen, st, 'VTX-01H', SRC_L,
             note=f"{o['accelerator_m']:.0f} m inclined {o['inclination_deg']:.2f} deg on a line through the burn point; {o['accel_g']:,.0f} g",
             points=[pol(xe, rA(xe), az), pol(xSA+0.2, rA(xSA+0.2), az)], radius=0.35, **common)
        make('LC_Own_Shield_Penetration', 'tube', coll, 'VIS_XRAY', gen, st, 'VTX-06A', SRC_L, alpha=0.8,
             note='second straight shield penetration (a bore-sized streaming path)', points=[pol(xSF+0.3, rA(xSF+0.3), az), pol(xSA-0.3, rA(xSA-0.3), az)], radius=0.3)
        make('LC_Chopper', 'ring', coll, 'VIS_CONFLICT', gen, st, 'VTX-06A', SRC_L, alpha=0.9, note='own chopper', x0=xSA-0.25, x1=xSA-0.1, r0=0.0, r1=0.6,
             centre=tuple(pol(0, rA(xSA), az)[1:]))
        make('LC_Breech_Plug', 'ring', coll, 'SHIELD', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-06A', SRC_L, note='second bore plug behind its breech',
             x0=xe+0.3, x1=xe+4.2, r0=0.0, r1=0.8, centre=tuple(pol(0, rA(xe), az)[1:]))
        make('LC_CONFLICT_Thrust_Ring', 'sphere', coll, 'VIS_CONFLICT', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-01H', SRC_L, rep='VISUALIZATION', alpha=1.0,
             note=f"barrel line at r {o['r_at_thrust_ring_m']:.2f} m where the canon 12 m thrust ring (r 5-6 m) sits", centre=pol(e['x_module_fwd_m'], rA(e['x_module_fwd_m']), az), radius=0.9)
    # line of sight: the only exposed segment; must be crossed between two pulses
    if key == 'C':
        p0 = pol(xSA-0.3, rA(xSA-0.3), 30.0)
    else:
        p0 = (o['muzzle_x_m'], 0, 0)
    make(f'L{key}_Line_Of_Sight', 'tube', coll, 'VIS_XRAY', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-01H', SRC_L, rep='VISUALIZATION', alpha=0.9,
         note=f"open line of sight {o['line_of_sight_m']:.1f} m, crossed in one pulse interval ({1e3/REV2['launcher']['pulse_Hz']:.2f} ms)",
         points=[p0, (xB, 0, 0)], radius=0.25)
    if key in ('A', 'B'):
        make(f'L{key}_Protected_Run', 'tube', coll, 'VIS_SAFE', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-01H', SRC_L, rep='VISUALIZATION', alpha=0.35,
             note='protected run behind the chopper', points=[(BREECH_X, 0, 0), (o['muzzle_x_m']+1.8, 0, 0)], radius=0.55)
    if key == 'REV1':
        make('LREV1_CONFLICT_Magazine', 'sphere', coll, 'VIS_CONFLICT', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-01H', 'checks.json (Rev 1 ISS-009)',
             rep='VISUALIZATION', alpha=1.0, note='20 m barrel runs through the FDP-1 magazine (xSF+14.5-16 m) and LiH plug', centre=(xSF+15.0, 0, 0), radius=2.0)


def build_lane_core_launch(gen, R, e, coll):
    """Axis-only ghost context for the launcher comparison lanes (the opaque canon spine would hide the barrel)."""
    lay = R['layout']; xB = e['x_burn_m']
    make('LaneCore_Spine', 'ring', coll, 'STRUCTURE', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-NONE', 'canon Structural_Spine (built asset)', rep='VISUALIZATION',
         x0=CANON2['spine_x_m'][0], x1=CANON2['spine_x_m'][1], r0=0.6, r1=CANON2['spine_r_m'], alpha=0.25)
    make('LaneCore_Crew_Trunk', 'ring', coll, 'SERVICE', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-NONE', 'canon Crew_Trunk (built asset)', rep='VISUALIZATION',
         x0=CANON2['crew_trunk_x_m'][0], x1=CANON2['crew_trunk_x_m'][1], r0=0.0, r1=1.0, alpha=0.8)
    for nm, x in (('Ring_A', 97.3), ('Ring_B', 103.3)):
        make(f'LaneCore_{nm}_Hub_Tick', 'box', coll, 'SERVICE', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-NONE', 'canon datum', rep='VISUALIZATION',
             centre=(x, 0, 7.0), size=(4.3, 0.6, 14.0), alpha=0.6)
    make('LaneCore_Shield', 'frustum', coll, 'SHIELD', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-06A', f'solve:{gen}', rep='VISUALIZATION',
         x0=e['x_shield_aft_m'], r0=e['shield_r_hw_m'], x1=lay['x_shield_fwd'], r1=e['shield_r_hw_m'], alpha=0.7)
    make('LaneCore_Module', 'frustum', coll, 'STRUCTURE', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-NONE', f'solve:{gen}', rep='VISUALIZATION',
         x0=lay['x_shield_fwd'], r0=6.5, x1=e['x_module_fwd_m'], r1=6.5, ri0=6.3, ri1=6.3, alpha=0.12)
    make('LaneCore_Thrust_Ring', 'torus', coll, 'STRUCTURE', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-NONE', 'canon 12 m thrust ring', rep='VISUALIZATION',
         x=e['x_module_fwd_m'], R=5.5, a=0.5, alpha=0.5)
    make('LaneCore_Burn_Point', 'sphere', coll, 'VIS_PLASMA', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-01', f'solve:{gen}', rep='VISUALIZATION',
         centre=(xB, 0, 0), radius=1.5, alpha=1.0)
    make('LaneCore_Galleries', 'ring', coll, 'MAIN_PROPULSION', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-01B', f'solve:{gen}', rep='VISUALIZATION',
         x0=R['drivers']['x_aft'], x1=R['drivers']['x_fwd'], r0=4.3, r1=4.7, alpha=0.08)


def build_coil_protection(gen, R, e, colls_opt, cut=None):
    """C1/C2 protection concepts (rev2.json coils). P0 = Rev 1 (warm screen only), P1 = monolithic sacrificial armour shoe on the burn face,
    P2 = 12 replaceable armour segments per coil on low-conductance stand-offs in front of the warm screen. The X-ray they intercept is set by
    their solid angle, so every option absorbs the same 30 GW; armour only decides where it lands and how it is replaced."""
    xB = e['x_burn_m']; CR = {c['name']: c for c in REV2['coils']['coils']}
    for c in e['closure_coils']:
        q = CR[c['name']]; env = c['envelope_r_m'][1]
        u = (xB-c['x_m'], -c['r_m']); d = math.hypot(*u); u = (u[0]/d, u[1]/d)
        sx, sr = c['x_m']+u[0]*(env+0.5), c['r_m']+u[1]*(env+0.5)
        msg = f"{q['xray_W']/1e9:.1f} GW X-ray on {q['burn_face_m2']:,.0f} m2 (share {q['solid_angle_share']:.3f}); armour {q['armour_kg_at_loop_areal']/1e3:.0f} t at the loops' 45 kg/m2"
        make(f"{c['name']}_P1_Armour_Shoe", 'torus', colls_opt['P1'], 'SHIELD', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-06B', 'rev2.json coils', note='sacrificial shoe; '+msg,
             x=sx, R=sr, a=env*0.45, cut=cut)
        for k in range(12):
            a0 = 30.0*k+0.75; a1 = a0+28.5
            make(f"{c['name']}_P2_Armour_Seg_{k+1:02d}", 'torus', colls_opt['P2'], 'SHIELD', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-06B', 'rev2.json coils',
                 note='replaceable segment 1/12; '+msg, x=sx, R=sr, a=env*0.45, arc=(a0, a1), cut=cut)
            mid = (a0+a1)/2
            make(f"{c['name']}_P2_Handling_Post_{k+1:02d}", 'box', colls_opt['P2'], 'SERVICE', gen, 'PROTOTYPE', 'VTX-06B', 'T05 Rev 2',
                 note='robotic handling post', centre=pol(sx+1.6, sr, mid), size=(1.2, 0.6, 0.6), roll=mid, cut=cut)
            for j in (-1, 1):
                make(f"{c['name']}_P2_Standoff_{k+1:02d}_{j:+d}", 'tube', colls_opt['P2'], 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-03D', 'T05 Rev 2',
                     note='low-conductance stand-off: armour to coil structure, bypassing the warm screen', points=[pol(sx-u[0]*0.4, sr-u[1]*0.4, mid+8*j),
                     pol(c['x_m']+u[0]*env*0.2, c['r_m']+u[1]*env*0.2, mid+8*j)], radius=0.12, cut=cut)
        make(f"{c['name']}_P2_Warm_Screen", 'torus', colls_opt['P2'], 'LOW_RADIATOR', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-03D', 'T03 (warm eddy screen)',
             note='warm screen behind the armour: sees the armour back face (re-radiation) instead of the burn', x=c['x_m'], R=c['r_m'], a=env*0.9, alpha=0.3, cut=cut)
        if 'CORE' in colls_opt:
            make(f"{c['name']}_Core_Winding", 'torus', colls_opt['CORE'], 'MAIN_PROPULSION', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-03D', 'T03 (lane copy)',
                 x=c['x_m'], R=c['r_m'], a=c['winding_minor_m'], cut=cut)
            make(f"{c['name']}_Core_Envelope", 'torus', colls_opt['CORE'], 'LOW_RADIATOR', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-03D', 'T03 (lane copy)',
                 x=c['x_m'], R=c['r_m'], a=env, alpha=0.22, cut=cut)
        make(f"{c['name']}_XRAY_Fan", 'frustum', colls_opt['FAN'], 'VIS_XRAY', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-03D', 'rev2.json coils', rep='VISUALIZATION',
             note=msg, x0=xB+0.01, r0=0.01, x1=c['x_m'], r1=c['r_m'], ri0=0.0, ri1=c['r_m']-0.3, alpha=0.05)
    # sized C1 struts (1.9 GN case) and the reaction ring: indicative, not a structural proof
    sz = REV2['coils']['struts']['cases'][1]; c1 = e['closure_coils'][0]
    ring_r = e['shield_r_hw_m']+1.0; xr = e['x_shield_aft_m']-0.8
    make('C1_Sized_Reaction_Ring', 'torus', colls_opt['SUP'], 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-03D', 'rev2.json coils.struts',
         note='reaction ring on the shield aft face; the shield frame must take 0.2-1.9 GN (unsized)', x=xr, R=ring_r, a=1.0, cut=cut)
    for j in range(6):
        az = 60.0*j+30.0
        make(f'C1_Sized_Strut_{j+1}', 'tube', colls_opt['SUP'], 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-02D', 'rev2.json coils.struts',
             note=f"CFRP tube r {sz['tube_r_m']:.1f} m, wall {sz['wall_m']*1e3:.0f} mm for {sz['load_per_strut_N']/1e6:.0f} MN (1.9 GN / 6); buckling {sz['buckling_per_strut_N']/1e9:.2f} GN; "
                  f"{sz['mass_kg']/1e3:.0f} t for six; hoop 3-7 GN carried by the 855-1,281 t coil structure (T03, unbooked)",
             points=[pol(c1['x_m'], c1['r_m']-c1['envelope_r_m'][1]*0.6, az), pol(xr, ring_r, az)], radius=sz['tube_r_m'], cut=cut)


def build_dock_routes(gen, coll):
    for nm, az, x, rad in (('Primary_Dock_Corridor', C['dock_primary']['az_deg'], C['dock_primary']['x_m'], 3.0),
                           ('Service_Dock_Corridor', C['dock_service']['az_deg'], C['dock_primary']['x_m'], 3.0),
                           ('EVA_Airlock_Route', C['airlock']['az_deg'], C['airlock']['x_m'], 1.5)):
        make(nm, 'tube', coll, 'SERVICE', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-NONE', 'canon spec (dock_x, airlock_x) and MODEL.md 3 m corridor', rep='VISUALIZATION',
             note=f'{nm.replace("_", " ").lower()}: keep clear (radial, r 7 to 45 m)', points=[pol(x, 7.2, az), pol(x, 45.0, az)], radius=rad, alpha=0.35)


# ----------------------------------------------------------------------------------------------------------------------------------
# Revision 3: structure and access across the T-B stretch (rev3.json), longer launcher outline, coil cooling lines
# ----------------------------------------------------------------------------------------------------------------------------------
REV3 = json.loads((HERE/'rev3.json').read_text())     # python3 work/vertex-blender/rev3.py writes it
SRC3 = 'rev3.json (work/vertex-blender/rev3.py)'
ST3 = REV3['stretch']; SO3 = REV3['options_operational']


def stretch_frames(x0, x1):
    xs = []; pitch = ST3['bay_pitch_m']; x = x0
    while x <= x1+0.1:
        xs.append(x); x += pitch
    return xs


def build_stretch(key, gen, coll):
    """One ISS-013 layout from rev3.json options_operational[key]. Member radii are the screened sizes (stiffness-upgraded where the
    0.2 Hz target added area); every member is PROTOTYPE."""
    o = SO3[key]; x0, x1 = ST3['x_m']; rs = CANON2['spine_r_m']
    note = f"{key}: {o['members']}; {o['structure_kg']/1e3:,.0f} t strength, {o['structure_stiff_kg']/1e3:,.0f} t for f1 >= {REV3['f_target_Hz']} Hz; f1 full {o['f_bending_Hz']['full']:.3f} Hz"
    if key == 'S1_SPINE_ONLY':
        make('S1_Spine_Thick_Tube', 'ring', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC3, note=note+'; violates the hub-alone rule', x0=x0, x1=x1, r0=0.24, r1=rs)
        make('S1_CONFLICT_Hub_Alone', 'sphere', coll, 'VIS_CONFLICT', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-04', 'data/wayfarer_3d.toml forward_defense.shield_load_path',
             rep='VISUALIZATION', alpha=1.0, note='hub alone forbidden: the Brow needs the three primary sectors', centre=(x1-2.0, 0, 0), radius=3.0)
        return
    make(f'{key[:2]}_Spine', 'ring', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC3, note=note, x0=x0, x1=x1, r0=rs-0.006, r1=rs)
    if key in ('S2_CANON_SECTORS', 'S4_SECTORS_PLUS_BELT'):
        k = SO3['S2_CANON_SECTORS']['keel']
        for az in (30.0, 150.0, 270.0):
            make(f'{key[:2]}_Sector_Keel_{int(az)}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC3, note=f"sector keel r {k['r_m']:.2f} m x {k['t_m']*1e3:.0f} mm; " + note,
                 points=[pol(x0-3.0, 5.0, az), pol(x1, 5.0, az)], radius=k['r_m'])
    if key == 'S4_SECTORS_PLUS_BELT':
        b = o['belt_keel']
        for az in (90.0, 210.0, 330.0):
            make(f'S4_Belt_Keel_{int(az)}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC3, note='belt keel in the 1.75 m gap between the tank rings; the 0.2 Hz stiffness upgrade would need r about 1.0 m, which does not fit',
                 points=[pol(x0, 20.1, az), pol(x1, 20.1, az)], radius=b['r_m'])
    if key == 'S3_OUTER_CAGE':
        L_ = o['longeron']; rr = o.get('stiffness_member_r_m_each_at_t_over_r_0p05') or L_['r_m']
        for j in range(6):
            az = 60.0*j
            make(f'S3_Outer_Longeron_{int(az)}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC3, note=f"outer longeron r {max(rr, L_['r_m']):.2f} m at r 34.8 m; " + note,
                 points=[pol(x0, 34.8, az), pol(x1, 34.8, az)], radius=max(rr, L_['r_m']))
    # frames: S2/S4 keel ring + radial girders to each outer and inner tank saddle; S3 outer rings + 12 spokes
    xs = stretch_frames(x0-1.0, x1)
    for i, x in enumerate(xs):
        if key in ('S2_CANON_SECTORS', 'S4_SECTORS_PLUS_BELT'):
            make(f'{key[:2]}_Frame_{i:02d}', 'torus', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC3, note='bay frame at a tank joint (2 m gap between bays)', x=x, R=5.0, a=0.3)
            for j in range(12):
                az = 6.2+30.0*j
                make(f'{key[:2]}_Girder_{i:02d}_O{j:02d}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC3, note='radial two-chord girder (1.8 m deep) to an outer tank saddle',
                     points=[pol(x, 5.0, az), pol(x, 27.75, az)], radius=0.25)
            for j in range(3):
                make(f'{key[:2]}_Spoke_{i:02d}_{j}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC3, points=[pol(x, rs, 30+120*j), pol(x, 5.0, 30+120*j)], radius=0.2)
        if key == 'S3_OUTER_CAGE':
            make(f'S3_Ring_{i:02d}', 'torus', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC3, note='outer ring frame r 34.8 m', x=x, R=34.8, a=0.35)
            for j in range(12):
                make(f'S3_Spoke_{i:02d}_{j:02d}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC3, points=[pol(x, rs, 30*j+15), pol(x, 34.8, 30*j+15)], radius=0.18)
    # joints
    for nm, x, why in (('J1_Root_Transfer_Frame', x0-1.5, 'J1: splice to the canon spine end and sector rails (farm front frame X 137.9 m)'),
                       ('J3_Bow_Interface_Frame', x1-1.5, 'J3: spine to the shield spine column, keels to the Brow-side sector keels')):
        make(f'{key[:2]}_{nm}', 'torus', coll, 'VIS_BEAM', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-04', SRC3, rep='VISUALIZATION', note=why, x=x, R=5.0 if key != 'S3_OUTER_CAGE' else 34.8, a=0.9, alpha=0.9)


def build_corridor(key, gen, coll):
    c = REV3['corridor'][key]; x0 = CANON2['crew_trunk_x_m'][1]; x1 = ST3['x_m'][1]
    if key == 'K1_TRUNK_IN_SPINE':
        make('K1_Trunk_In_Spine', 'ring', coll, 'HABITAT', gen, 'PROTOTYPE', 'VTX-04', SRC3, alpha=0.8,
             note=f"pressurised trunk inside the spine bore, 1.65 m clear, {c['mass_kg']/1e3:.0f} t; spine becomes the pressure hull; single route",
             x0=x0, x1=x1, r0=0.7, r1=0.83)
        pts = [x0+ST3['bay_pitch_m']*k for k in range(10)]
        for k, x in enumerate(pts):
            make(f'K1_Hatch_{k:02d}', 'ring', coll, 'SERVICE', gen, 'PROTOTYPE', 'VTX-04', SRC3, note='0.75 m bulkhead hatch', x0=x, x1=x+0.3, r0=0.38, r1=0.9)
    elif key == 'K2_TUBE_BESIDE_SPINE':
        cy, cz = pol(0, 3.0, 90.0)[1:]
        make('K2_Pressure_Tube', 'ring', coll, 'HABITAT', gen, 'PROTOTYPE', 'VTX-04', SRC3, alpha=0.8,
             note=f"2.2 m pressure tube at r 3 m az 90, {c['wall_mm']:.1f} mm Al-Li (min gauge 2.5), {c['kg_per_m']:.0f} kg/m, {c['mass_kg']/1e3:.0f} t; 10 hatches",
             x0=x0-3.0, x1=x1, r0=0.98, r1=1.1, centre=(cy, cz))
        make('K2_Link_To_Crew_Trunk', 'tube', coll, 'HABITAT', gen, 'PROTOTYPE', 'VTX-04', SRC3, alpha=0.8, note='transfer node from the canon crew trunk end (X 134.7 m) into the tube',
             points=[(x0-1.5, 0, 0), pol(x0-1.5, 3.0, 90.0)], radius=0.8)
        for k in range(10):
            x = x0+ST3['bay_pitch_m']*k
            make(f'K2_Hatch_Ring_{k:02d}', 'ring', coll, 'SERVICE', gen, 'PROTOTYPE', 'VTX-04', SRC3, note='bulkhead with 0.75 m hatch at each bay frame; bay service hatch to the tanks',
                 x0=x, x1=x+0.4, r0=0.0, r1=1.25, centre=(cy, cz))
    make(f'{key[:2]}_Robot_Rail', 'tube', coll, 'SERVICE', gen, 'PROTOTYPE', 'VTX-04', SRC3, note='robot rail along keel 270 (inspection, tank saddles, cable runs)',
         points=[pol(x0, 5.6, 270.0), pol(x1, 5.6, 270.0)], radius=0.12)


def build_tb_section_core(gen, R, coll):
    """Ghost T-B tank cylinders for the structure comparison lanes (the built tanks would hide the members)."""
    for v in R['tanks']['options']['T-B']['vessels']:
        make('Core_' + v['name'].replace('FDP1_', ''), 'ring', coll, 'HELIUM3' if v['species'] == 'helium_3' else 'DEUTERIUM', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-NONE',
             f'solve:{gen} tanks T-B', rep='VISUALIZATION', alpha=0.12, x0=v['x0'], x1=v['x1'], r0=0.0, r1=v['a'], centre=(v['y'], v['z']))
    make('Core_Canon_Spine_End', 'ring', coll, 'STRUCTURE', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-NONE', 'canon Structural_Spine', rep='VISUALIZATION', alpha=0.5,
         x0=100.0, x1=CANON2['spine_x_m'][1], r0=0.0, r1=CANON2['spine_r_m'])
    make('Core_Crew_Trunk', 'ring', coll, 'HABITAT', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-NONE', 'canon Crew_Trunk', rep='VISUALIZATION', alpha=0.7,
         x0=CANON2['crew_trunk_x_m'][0], x1=CANON2['crew_trunk_x_m'][1], r0=0.0, r1=0.9)
    make('Core_Bow_Shield', 'frustum', coll, 'SHIELD', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-NONE', 'canon forward shield (shifted)', rep='VISUALIZATION', alpha=0.25,
         x0=ST3['x_m'][1], r0=45.0, x1=ST3['x_m'][1]+4.0, r1=45.0, ri0=0.0, ri1=0.0)
    make('Core_Skirt_B2_Shadow', 'frustum', coll, 'VIS_SAFE', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-08E', 'rev2.json dust B2', rep='VISUALIZATION', alpha=0.06,
         x0=ST3['x_m'][0], r0=36.0, x1=ST3['x_m'][1], r1=36.0, ri0=35.9, ri1=35.9)


def build_launcher_long(gen, R, e, coll):
    lt = REV3['launcher_target']['B_long_to_bow']; o = LOPT['B']; x1 = ST3['x_m'][1]
    make('LBL_Accelerator_To_Bow', 'tube', coll, 'MAIN_PROPULSION', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-01H', SRC3, rep='VISUALIZATION', alpha=0.7,
         note=f"B-long: {lt['accelerator_m']:.0f} m accelerator from the bow to the snout tip, {lt['accel_g']:,.0f} g at {o['exit_speed_m_s']/1e3:.2f} km/s; {lt['needs']}",
         points=[(x1-2.0, 0, 0), (o['muzzle_x_m']+0.5, 0, 0)], radius=0.35)
    make('LBL_CONFLICT_Crew_Trunk', 'sphere', coll, 'VIS_CONFLICT', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-01H', SRC3, rep='VISUALIZATION', alpha=1.0,
         note='shares the spine bore with the canon crew trunk X 93.85-134.7 m', centre=(114.0, 0, 0), radius=2.0)
    make('LBL_Line_Of_Sight', 'tube', coll, 'VIS_XRAY', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-01H', SRC3, rep='VISUALIZATION', alpha=0.9,
         points=[(o['muzzle_x_m'], 0, 0), (e['x_burn_m'], 0, 0)], radius=0.25)
    make('LBL_Stretch_Spine_Ghost', 'ring', coll, 'STRUCTURE', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-04', SRC3, rep='VISUALIZATION', alpha=0.25,
         x0=CANON2['spine_x_m'][1], x1=x1, r0=0.6, r1=CANON2['spine_r_m'])


def build_coil_cooling(gen, R, e, coll):
    """P2 armour cooling: tin (the T01 hot-radiator fluid) at 1,800 K into the wing hot-band root; pipe radius for 5 m/s per side."""
    cc = REV3['coil_cooling']; w0 = PREF['hot_x_m'][0]
    for c in e['closure_coils']:
        q = cc[c['name']]; per_side = q['tin_m3_s']/2; r_p = math.sqrt(per_side/5.0/math.pi)
        env = c['envelope_r_m'][1]
        make(f"{c['name']}_Cooling_Manifold", 'torus', coll, 'HOT_RADIATOR', gen, 'PROTOTYPE', 'VTX-03D', SRC3,
             note=f"armour coolant manifold: {q['xray_W']/1e9:.1f} GW, tin {q['tin_m3_s']:.0f} m3/s (lithium {q['lithium_m3_s']:.0f} m3/s), 300 K rise",
             x=c['x_m']+env+0.8, R=c['r_m'], a=r_p*0.7)
        for az in (0.0, 180.0):
            for k, dz in (('Supply', 1.0), ('Return', -1.0)):
                make(f"{c['name']}_Coolant_{k}_{int(az)}", 'tube', coll, 'HOT_RADIATOR', gen, 'PROTOTYPE', 'VTX-03D', SRC3,
                     note=f"{k.lower()} line r {r_p:.2f} m (5 m/s) to the wing hot-band root; pump about {q['tin_m3_s']*1e6/1e6:.0f} MW at 1 MPa",
                     points=[pol(c['x_m']+env+0.8, c['r_m'], az+dz*4), pol(w0+2.0, 12.0+(3 if k == 'Return' else 0), az+dz*1.5)], radius=r_p)


# ----------------------------------------------------------------------------------------------------------------------------------
# Revision 4: closure-coil assemblies as layered sections (rev4.json coil_assembly), lithium armour loop routed in the strut shadows
# ----------------------------------------------------------------------------------------------------------------------------------
REV4 = json.loads((HERE/'rev4.json').read_text())     # python3 work/vertex-blender/rev4.py writes it
SRC4 = 'rev4.json (work/vertex-blender/rev4.py)'
CA4 = REV4['coil_assembly']; CP4 = REV4['coil_plant']
T00H = json.loads((HERE/'t00_handoff_rev4.json').read_text())     # T00 handoff v1 (copy of 9rsgog results/t05_handoff_rev4.json)


def h_t00(nm):
    return T00H['coils'][nm]


def tr4(issue, param, tech='VTX-03D'):
    """Rev 4 traceability block on top of the six base properties (brief sec. 8)."""
    return {'issue_id': issue, 'parameter': param, 'tech_id': tech, 'geom_rev': 4}


def annulus(xc, rc, r_in, r_out, phi0=0.0, phi1=360.0, n=28):
    """(x, r) polygon of an annular band of a coil cross-section, phi measured in the (x, r) plane."""
    full = abs(phi1-phi0) >= 359.9
    k = n if not full else n
    ph = [math.radians(phi0+(phi1-phi0)*i/k) for i in range(k+1)]
    outer = [(xc+r_out*math.cos(t), rc+r_out*math.sin(t)) for t in ph]
    if r_in <= 1e-6:
        return outer[:-1] if full else [(xc, rc)]+outer
    inner = [(xc+r_in*math.cos(t), rc+r_in*math.sin(t)) for t in reversed(ph)]
    return outer+inner


def build_coil_assembly(key, gen, e, coll, cut=None, detail=True, plant_key=None, opaque=False):
    """C1/C2 as the full assembly the burn sees: 25 T winding envelope, structural case, cryostat (vacuum + 80 K shield + wall), warm screen,
    stand-off gap, then the burn-facing armour (coolant back plate + sacrificial face) in 12 replaceable segments. The outermost layer
    sets the X-ray share (rev4.json coil_assembly builds[key]); detail adds manifolds, stand-offs, handling posts and the service rail."""
    xB = e['x_burn_m']
    _mk = globals()['make']
    def make(*a_, **k_):                                                 # noqa: E306  (section lanes draw every layer opaque)
        if opaque:
            k_['alpha'] = 1.0
        return _mk(*a_, **k_)
    for c in e['closure_coils']:
        nm = c['name']; q = CA4['coils'][nm]; b = q['builds'][key]; xc, rc = c['x_m'], c['r_m']
        phi_u = math.degrees(math.atan2(-rc, xB-xc))                     # direction of the burn point in the (x, r) section plane
        a_w = q['winding_25T_minor_m']; r_case = b['case_outer_m']
        gw = f"{b['xray_W']/1e9:.2f} GW, share {b['share']:.4f}, half-width {b['projected_half_width_m']:.2f} m"
        T = lambda p: tr4('T05-ISS-014', f'rev4.json coil_assembly.coils.{nm}.builds.{key}.{p}')
        if 'profile' in b:                                                # T00 shadowed build: everything kept inside the projected half-width
            pf = b['profile']; a_ = pf['winding_minor_m']; hw = b['projected_half_width_m']; S = pf['case_back_s_m']; f_ = pf['front_layers_m']
            lih = pf['lih_nose_m']; gap = pf['shadow_margin_m']; li = pf['li_channel_m']; cf = pf['cfc_m']
            ux, ur = math.cos(math.radians(phi_u)), math.sin(math.radians(phi_u)); nx, nr = -ur, ux
            P = lambda sw: [(xc+s_*ux+w_*nx, rc+s_*ur+w_*nr) for s_, w_ in sw]
            arc = lambda cs, r, t0, t1, n=24: [(cs+r*math.cos(math.radians(t0+(t1-t0)*i/n)), r*math.sin(math.radians(t0+(t1-t0)*i/n))) for i in range(n+1)]
            def stad(cs, r, back, hw_):                                   # front half-disc at cs (radius r), straight sides of half-width hw_ back to s = back
                return arc(cs, r, -90, 90)+[(back, hw_), (back, -hw_)]
            Tt = lambda p_: tr4('T05-ISS-014', f'rev4.json coil_assembly.coils.{nm}.builds.{key}.profile.{p_}')
            make(f'{nm}_{key}_Winding', 'profile', coll, 'MAIN_PROPULSION', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-03D', SRC4, cut=cut,
                 note=f"winding pack r {a_:.2f} m at 150 A/mm2 ({h_t00(nm)['current_MA']:.0f} MA, T00)", trace=Tt('winding_minor_m'),
                 prof=P(arc(0.0, a_, 0, 360, 28)[:-1]))
            make(f'{nm}_{key}_Case_Tail', 'profile', coll, 'STRUCTURE', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-03D', SRC4, cut=cut,
                 note=f"hoop case {pf['case_area_m2']:.2f} m2 as a tail behind the winding, in its own shadow ({b['masses_t']['case']:,.0f} t, T00)",
                 trace=Tt('case_area_m2'), prof=P(arc(0.0, a_, 90, 270, 16)+[(-S, -a_), (-S, a_)]))
            for half, sg in (('Upper', 1.0), ('Lower', -1.0)):             # band = outer stadium minus inner stadium, drawn in two simple halves
                band = [(s_, sg*w_) for s_, w_ in arc(0.0, a_+f_, 0, 90, 12)+[(-S-f_, a_+f_), (-S-f_, 0.0), (-S, 0.0), (-S, a_)]+arc(0.0, a_, 90, 0, 12)]
                make(f'{nm}_{key}_Cryostat_{half}', 'profile', coll, 'LOW_RADIATOR', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-03D', SRC4, cut=cut, alpha=0.55,
                     note=f'insulation + cryostat wall + vacuum/MLI/80 K screen, {f_:.2f} m around winding and case ({b["masses_t"]["cryostat"]:,.0f} t)',
                     trace=Tt('front_layers_m'), prof=P(band))
            make(f'{nm}_{key}_LiH_Nose', 'profile', coll, 'SHIELD', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-03D', SRC4, cut=cut,
                 note=f"LiH neutron screen {lih:.2f} m on the burn face (100x fast-neutron attenuation; REBCO at 35x its limit unshielded, T00); {b['masses_t']['neutron_screen']:,.0f} t",
                 trace=Tt('lih_nose_m'), prof=P(arc(lih, a_+f_, -90, 90)+arc(0.0, a_+f_, 90, -90)))
            out_r = a_+f_+gap
            make(f'{nm}_{key}_Li_Channel', 'profile', coll, 'HOT_RADIATOR', gen, 'PROTOTYPE', 'VTX-06B', SRC4, cut=cut,
                 note=f'Mo-TZM lithium channel {li*1e3:.0f} mm under the armour (1,500 -> 1,800 K loop)', trace=Tt('li_channel_m'),
                 prof=P(arc(lih, out_r+li, -90, 90)+[(-0.3, out_r+li), (-0.3, out_r)]+arc(lih, out_r, 90, -90)+[(-0.3, -out_r), (-0.3, -out_r-li)]))
            for k in range(12):
                make(f'{nm}_{key}_CFC_Armour_{k+1:02d}', 'profile', coll, 'SHIELD', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-06B', SRC4, cut=cut,
                     note=f'CFC monoblock armour {cf*1e3:.0f} mm, segment {k+1}/12 with shiplap edges (T00 surfaces: survives every spectrum band); {gw}',
                     trace=Tt('cfc_m'), arc=(30.0*k-0.2, 30.0*k+30.2),
                     prof=P(arc(lih, out_r+li+max(cf, 0.02), -90, 90)+[(-0.3, out_r+li+max(cf, 0.02)), (-0.3, out_r+li)]+arc(lih, out_r+li, 90, -90)
                            + [(-0.3, -out_r-li), (-0.3, -out_r-li-max(cf, 0.02))]))
            if detail:
                for k in range(12):
                    mid = 30.0*k+15.0
                    hp = P([(-S-f_-0.4, 0.0)])[0]
                    make(f'{nm}_{key}_Handling_Post_{k+1:02d}', 'box', coll, 'SERVICE', gen, 'PROTOTYPE', 'VTX-06B', SRC4, cut=cut,
                         note='robot handling post + Li quick-disconnects at the case tail (shadowed side)', trace=Tt('case_back_s_m'),
                         centre=pol(hp[0], hp[1], mid), size=tuple(v_*min(1.0, (a_+f_)/1.5) for v_ in (0.6, 0.45, 0.45)), roll=mid)
                sp = P([(-S-f_-1.0, 0.0)])[0]
                make(f'{nm}_{key}_Service_Rail', 'torus', coll, 'SERVICE', gen, 'PROTOTYPE', 'VTX-06B', SRC4, cut=cut,
                     note='robot rail behind the case tail: armour exchange by sector, Li disconnects, stand-off inspection', trace=Tt('case_back_s_m'),
                     x=sp[0], R=sp[1], a=0.1)
                for side, dw in (('Supply', 0.45*(a_+f_)), ('Return', -0.45*(a_+f_))):         # inside the half-width: in the shadow
                    mp = P([(-S-f_-0.25, dw)])[0]
                    make(f'{nm}_{key}_Manifold_{side}', 'torus', coll, 'HOT_RADIATOR', gen, 'PROTOTYPE', 'VTX-03D', SRC4, cut=cut,
                         note=f'Li {side.lower()} ring manifold on the case tail (shadowed)', trace=Tt('li_channel_m'), x=mp[0], R=mp[1], a=min(0.16, 0.25*(a_+f_)))
            continue
        if r_case is None:                                                # T03 3x winding or the Rev 2/3 copied envelope: one ghost shell
            make(f'{nm}_{key}_Envelope', 'torus', coll, 'LOW_RADIATOR', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-03D', SRC4, alpha=0.25, cut=cut,
                 note=f'{key}: envelope only ({gw})', trace=T('assembly_outer_m'), x=xc, R=rc, a=b['assembly_outer_m'])
            make(f'{nm}_{key}_Winding', 'torus', coll, 'MAIN_PROPULSION', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-03D', SRC4, cut=cut,
                 trace=T('winding'), x=xc, R=rc, a=a_w)
            continue
        Ls = {l: t for l, t, _ in [(r['id'], r['t_m'], r['what']) for r in CA4['layers_PROTOTYPE']]}
        r = r_case; R_ = {}
        for lid in ('cryostat_vacuum_mli', 'thermal_shield_80K', 'cryostat_wall', 'warm_eddy_screen', 'standoff_gap', 'armour_coolant', 'armour_face'):
            R_[lid] = (r, r+Ls[lid]); r += Ls[lid]
        make(f'{nm}_{key}_Winding_25T', 'torus', coll, 'MAIN_PROPULSION', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-03D', SRC4, cut=cut,
             note=f"field-limited winding envelope r {a_w:.2f} m (25 T surface, T03 C_W15 scaled); {q['current_A']/1e6:.0f} MA", trace=T('winding'),
             x=xc, R=rc, a=a_w)
        make(f'{nm}_{key}_Case', 'profile', coll, 'STRUCTURE', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-03D', SRC4, cut=cut, alpha=0.85,
             note=f"structural case to r {r_case:.2f} m for {q['hoop_tension_N']/1e9:.2f} GN hoop (T03 virial basis); "
                  f"{q['case_mass_kg_T03_virial']/1e3:,.0f} t (steel {q['case_mass_kg_steel']/1e3:,.0f} t)", trace=T('case_outer_m'),
             prof=annulus(xc, rc, a_w, r_case))
        for lid, func, al in (('thermal_shield_80K', 'LOW_RADIATOR', 0.5), ('cryostat_wall', 'STRUCTURE', 0.45), ('warm_eddy_screen', 'LOW_RADIATOR', 0.4)):
            r0, r1 = R_[lid]
            if lid == 'thermal_shield_80K':
                r0 = r1-0.02
            make(f'{nm}_{key}_{lid}', 'profile', coll, func, gen, 'PROTOTYPE', 'VTX-03D', SRC4, cut=cut, alpha=al,
                 note=f'{lid} r {r0:.2f}-{r1:.2f} m (PROTOTYPE layer)', trace=T('layers'), prof=annulus(xc, rc, r0, r1))
        # armour: burn-facing half (+-95 deg about the burn direction) in 12 segments, coolant back plate + face tiles
        p0, p1 = phi_u-95.0, phi_u+95.0
        for k in range(12):
            a0 = 30.0*k+0.75; a1 = a0+28.5
            make(f'{nm}_{key}_Armour_Backplate_{k+1:02d}', 'profile', coll, 'HOT_RADIATOR', gen, 'PROTOTYPE', 'VTX-06B', SRC4, cut=cut,
                 note=f'segment {k+1}/12 coolant back plate (lithium channels), {gw}', trace=T('armour'), arc=(a0, a1),
                 prof=annulus(xc, rc, *R_['armour_coolant'], p0, p1))
            make(f'{nm}_{key}_Armour_Face_{k+1:02d}', 'profile', coll, 'SHIELD', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-06B', SRC4, cut=cut,
                 note=f'segment {k+1}/12 sacrificial face, shiplap edges overlap the neighbours (no line-of-sight gap); material waits for T00 sec. 5; {gw}',
                 trace=T('armour'), arc=(30.0*k-0.2, 30.0*k+30.2),
                 prof=annulus(xc, rc, *R_['armour_face'], p0, p1))
            if not detail:
                continue
            mid = (a0+a1)/2
            for j, dphi in ((-1, -55.0), (0, 0.0), (1, 55.0)):
                ph = math.radians(phi_u+dphi)
                pa = (xc+R_['standoff_gap'][1]*math.cos(ph), rc+R_['standoff_gap'][1]*math.sin(ph))
                pb = (xc+R_['warm_eddy_screen'][0]*math.cos(ph), rc+R_['warm_eddy_screen'][0]*math.sin(ph))
                make(f'{nm}_{key}_Standoff_{k+1:02d}_{j:+d}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-03D', SRC4, cut=cut,
                     note='low-conductance stand-off through the warm screen to the case (bypasses the cryostat)', trace=T('standoff_gap'),
                     points=[pol(pa[0], pa[1], mid), pol(pb[0], pb[1], mid)], radius=0.05 if nm == 'C2' else 0.08)
            ph = math.radians(phi_u+180.0)                                   # handling post on the shadowed (forward) side
            hp = (xc+(r+0.35)*math.cos(ph), rc+(r+0.35)*math.sin(ph))
            make(f'{nm}_{key}_Handling_Post_{k+1:02d}', 'box', coll, 'SERVICE', gen, 'PROTOTYPE', 'VTX-06B', SRC4, cut=cut,
                 note='robot handling post and coolant quick-disconnect for the segment (shadowed side)', trace=T('armour'),
                 centre=pol(hp[0], hp[1], mid), size=(0.7, 0.5, 0.5), roll=mid)
        if not detail:
            continue
        pk = plant_key or f"LI_LOOP_HX:{key}"
        pl = CP4['cases'].get(pk)
        if pl:
            rm = pl['manifold_r_m'][nm]; ph = math.radians(phi_u+180.0)
            for side, dphi in (('Supply', -28.0), ('Return', 28.0)):
                t = math.radians(phi_u+180.0+dphi)
                mx, mr = xc+(r+rm+0.15)*math.cos(t), rc+(r+rm+0.15)*math.sin(t)
                make(f'{nm}_{key}_Manifold_{side}', 'torus', coll, 'HOT_RADIATOR', gen, 'PROTOTYPE', 'VTX-03D', SRC4, cut=cut,
                     note=f"{side.lower()} ring manifold r {rm:.2f} m, fed at six points ({pl['fluid']}, {pl['flow_C1_m3_s' if nm == 'C1' else 'flow_C2_m3_s']:.1f} m3/s)",
                     trace=tr4('T05-ISS-014', f'rev4.json coil_plant.cases.{pk}.manifold_r_m.{nm}'), x=mx, R=mr, a=rm)
            # service rail and one robot carriage on the shadowed side; one segment drawn withdrawn on its exchange path
            sx, sr = xc+(r+1.2)*math.cos(ph), rc+(r+1.2)*math.sin(ph)
            make(f'{nm}_{key}_Service_Rail', 'torus', coll, 'SERVICE', gen, 'PROTOTYPE', 'VTX-06B', SRC4, cut=cut,
                 note='robot rail in the coil shadow: segment exchange, stand-off inspection, quick-disconnects', trace=T('armour'), x=sx, R=sr, a=0.12)
            make(f'{nm}_{key}_Robot_Carriage', 'box', coll, 'SERVICE', gen, 'PROTOTYPE', 'VTX-06B', SRC4,
                 note='exchange robot (segment gripper); parks in the shadow between pulses-off campaigns', trace=T('armour'),
                 centre=pol(sx, sr+0.6, 112.0), size=(2.0, 1.2, 1.2), roll=112.0)
            make(f'{nm}_{key}_Segment_Withdrawn', 'profile', coll, 'VIS_SAFE', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-06B', SRC4, rep='VISUALIZATION', alpha=0.35,
                 note='one armour segment on its exchange path: lifted 3 m off the stand-offs toward the shadowed side, then along the rail',
                 trace=T('armour'), arc=(90.75, 119.25),
                 prof=[(x+3.0*math.cos(ph), rr+3.0*math.sin(ph)) for x, rr in annulus(xc, rc, R_['armour_coolant'][0], R_['armour_face'][1], p0, p1, n=16)])


R4_SHADOW_MARGIN = 0.25         # m inside the shield's geometric shadow for the reaction ring's outer edge (PROTOTYPE)
R4_BUMPER_STANDOFF = 2.0        # m along the dust direction (T02 HANDOFF E: local bumpers <= 2 m stand-off)


def shadow_r(e, x):
    """radius of the shield's geometric X-ray shadow at station x (cone from the burn point over the shield's aft rim)."""
    xB = e['x_burn_m']
    return e['shield_r_hw_m']*(x-xB)/(e['x_shield_aft_m']-xB)


def r4_supports(e, key):
    c1, c2 = e['closure_coils']; b1 = CA4['coils']['C1']['builds'][key]
    a_ring = 0.8; xr = e['x_shield_aft_m']+a_ring+0.1          # inside the shield's aft frame, wholly forward of its X-ray face
    ring_r = shadow_r(e, xr)-a_ring-R4_SHADOW_MARGIN
    inset = (b1['case_outer_m'] or b1['assembly_outer_m']*0.6)*0.7
    struts = [(pol(c1['x_m']+0.3, c1['r_m']-inset, 60.0*j+30.0), pol(xr, ring_r, 60.0*j+30.0)) for j in range(6)]
    ties = [(pol(c2['x_m'], c2['r_m'], 60.0*j+30.0), pol(c1['x_m'], c1['r_m'], 60.0*j+30.0)) for j in range(6)]
    return xr, ring_r, a_ring, struts, ties


def build_coil_supports_r4(key, gen, e, coll):
    """Rev 4 coil load path: the reaction ring moves inside the shield's X-ray shadow (Rev 3's ring at r 8.2 m sat in the beam), the six sized
    C1 struts end on it, and six C2 -> C1 ties (missing from the Rev 3 V4 set) close C2's load path. The armour coolant lines run behind them."""
    sz = dict(REV2['coils']['struts']['cases'][1])
    b1 = CA4['coils']['C1']['builds'][key]
    if 'struts' in b1:                                                   # T00 sizing: width = diameter
        sz['tube_r_m'] = b1['struts']['width_m']/2
    r_tie = CA4['coils']['C2']['builds'][key]['struts']['width_m']/2 if 'struts' in CA4['coils']['C2']['builds'][key] else 0.4
    xr, ring_r, a_ring, struts, ties = r4_supports(e, key)
    T = lambda p: tr4('T05-ISS-003', p)
    make('C1_R4_Reaction_Ring', 'torus', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-03D', SRC4,
         note=f'reaction ring r {ring_r:.2f} m on the shield aft frame, outer edge {R4_SHADOW_MARGIN} m inside the shield shadow; frame must take 0.2-1.9 GN (unsized)',
         trace=T('build_vertex.py r4_supports ring_r'), x=xr, R=ring_r, a=a_ring)
    for j, (p, q) in enumerate(struts):
        make(f'C1_R4_Strut_{j+1}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-02D', SRC4,
             note=f"strut r {sz['tube_r_m']:.2f} m (T00 width where given) for {sz['load_per_strut_N']/1e6:.0f} MN (1.9 GN / 6); "
                  'carries the coolant pair in its shadow', trace=T('rev2.json coils.struts.cases[1]'), points=[p, q], radius=sz['tube_r_m'])
    for j, (p, q) in enumerate(ties):
        make(f'C2_R4_Tie_C1_{j+1}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-02D', SRC4,
             note=f'C2 -> C1 tie r {r_tie:.2f} m (T00 width); carries the C2 coolant pair in its shadow',
             trace=T('T00 handoff coils.C2.struts'), points=[p, q], radius=r_tie)


def cone_band(xB, theta, r_a, r_b, t):
    """thin conical sheet on the cone of polar angle theta (apex at the burn point): every line through the burn lies in it (edge-on to the X-ray),
    while every line parallel to X at radius r_a..r_b crosses it (it stops dust arriving along the axis). (x, r) polygon, thickness t normal to it."""
    c, s_ = math.cos(theta), math.sin(theta); cot = c/s_
    p0 = (xB+r_a*cot, r_a); p1 = (xB+r_b*cot, r_b)
    n = (-s_*t, c*t)                                   # normal to the ray direction (cos, sin) in the (x, r) plane
    return [p0, p1, (p1[0]+n[0], p1[1]+n[1]), (p0[0]+n[0], p0[1]+n[1])]


def build_dust_guards_r4(gen, R, e, coll):
    """Local bumpers and guard rings redrawn as burn-ray cone bands. Rev 2 drew them as tori 2.7 m thick around the loops; seen from the burn
    they intercepted 7.6 % of 4 pi (about 31 GW, ray cast) against T02's +0.1-0.4 % estimate. A cone band through the burn point is edge-on to
    the X-ray and still crosses every dust line that would reach the loop, fore and aft (T02 HANDOFF E: <= 2 m stand-off, both faces)."""
    xB = e['x_burn_m']; loops = R['nozzle']['loops']
    for i, L in enumerate(loops):
        if L['r'] <= 45.0:
            continue
        env = e['loops'][i]['envelope_r_m']; w = env+0.5
        cot_L = (L['x']-xB)/L['r']
        for face, sgn in (('Fwd', 1.0), ('Aft', -1.0)):
            th = math.atan2(1.0, cot_L+sgn*R4_BUMPER_STANDOFF/L['r'])
            for k in range(12):
                a0 = 30.0*k+45.0*i+0.5; a1 = a0+29.0
                make(f"{L['name']}_R4_Bumper_{face}_{k+1:02d}", 'profile', coll, 'SHIELD', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-08F', SRC4, alpha=0.55,
                     note=f"{face.lower()} local bumper sector {k+1}/12: cone band at polar {math.degrees(th):.2f} deg through the burn point (edge-on to the X-ray), "
                          f"r {L['r']-w:.1f}-{L['r']+w:.1f} m, {R4_BUMPER_STANDOFF:.0f} m stand-off along X; two-layer 0.5-2 kg/m2 (T02)",
                     trace=tr4('T05-ISS-019', 'T02 HANDOFF E local bumpers; build_vertex.py R4_BUMPER_STANDOFF', 'VTX-08F'), arc=(a0, a1),
                     prof=cone_band(xB, th, L['r']-w, L['r']+w, 0.02))
        if i >= 1:
            xg = L['x']+22.5; thg = math.atan2(L['r'], xg-xB)
            make(f"{L['name']}_R4_Guard_Band", 'profile', coll, 'SHIELD', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-08F', SRC4, alpha=0.55,
                 note=f'guard band 0.8 m wide, 22.5 m forward of the loop, on the burn-ray cone at {math.degrees(thg):.2f} deg (edge-on)',
                 trace=tr4('T05-ISS-019', 'T02 HANDOFF E guard rings', 'VTX-08F'), prof=cone_band(xB, thg, L['r']-0.4, L['r']+0.4, 0.02))


ST4 = REV4['structure']


def build_stretch_r4(gen, R, coll, key='S5_N9_NESTED'):
    """Rev 4 stretch structure (rev4.json structure.cases[key]): spine + three canon sector keels at r 5 m (S2) + nested longerons in the
    inter-tank gaps, bay frames in the 2 m inter-bay gaps (keel ring, outer ring at the longeron radius, spokes at the longeron azimuths,
    one girder to each tank's polar boss), J4 polar-boss saddles (aft fixed, forward sliding), J1 root diaphragm and J3 bow frame."""
    c = ST4['cases'][key]; x0, x1 = ST3['x_m']; rs = CANON2['spine_r_m']; rl = c['longeron_r_m']; rt = c['tube_r_m']
    k = SO3['S2_CANON_SECTORS']['keel']; T = lambda p: tr4('T05-ISS-013', f'rev4.json structure.cases.{key}.{p}', 'VTX-04')
    head = (f"{key}: {c['members']} longerons r {rt:.2f} m (t/r {c['t_over_r']}) at r {rl:.0f} m in the inter-tank gaps; {c['structure_kg']/1e3:,.2f} kt; "
            f"f1 {c['f1_full_Hz']:.2f} Hz full (beam model, PROTOTYPE target); tank clearance {c['min_tank_clearance_m']:.2f} m, B2 margin {c['B2_shadow_margin_m']:.1f} m")
    make('S5N_Spine', 'ring', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC4, note='spine continuation r 0.95 m; bore left free for services or a B-long barrel',
         trace=T('base'), x0=x0, x1=x1, r0=rs-0.006, r1=rs)
    for az in (30.0, 150.0, 270.0):
        make(f'S5N_Sector_Keel_{int(az)}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC4, note=f"canon sector keel r {k['r_m']:.2f} m at r 5 m (hub + three sectors rule)",
             trace=T('base'), points=[pol(x0-3.0, 5.0, az), pol(x1, 5.0, az)], radius=k['r_m'])
    for az in c['longeron_az_deg']:
        make(f'S5N_Longeron_{az:05.1f}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC4, note=head, trace=T('area_m2_each'),
             points=[pol(x0-2.0, rl, az), pol(x1+1.0, rl, az)], radius=rt)
    tanks = R['tanks']['options']['T-B']['vessels']
    frames = stretch_frames(x0-1.0, x1)
    if 'lacing' in c:                                                # T00: lacing in every bay panel is part of the stiffness; in the gap planes (chords would cut tanks)
        r_lc = math.sqrt(0.25*c['area_m2_each']/(2*math.pi*c['t_over_r']))
        for i in range(len(frames)-1):
            for az in c['longeron_az_deg']:
                xa, xb = (frames[i], frames[i+1]) if i % 2 == 0 else (frames[i+1], frames[i])
                make(f'S5N_Lacing_{i:02d}_{az:05.1f}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC4,
                     note=f"bay lacing diagonal in the inter-tank gap plane, r {r_lc:.2f} m (0.25 x longeron area, T00): {c['lacing']}", trace=T('lacing'),
                     points=[pol(xa, rl, az), pol(xb, 5.3, az)], radius=r_lc)
    for i, x in enumerate(frames):
        make(f'S5N_Frame_Keel_Ring_{i:02d}', 'torus', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC4, note='bay frame keel ring (2 m inter-bay gap)', trace=T('frames'), x=x, R=5.0, a=0.3)
        make(f'S5N_Frame_Outer_Ring_{i:02d}', 'torus', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC4, note=f'bay frame outer ring at the longeron radius r {rl:.0f} m' + (f"; {c['frames']}" if isinstance(c.get('frames'), str) else ''), trace=T('frames'),
             x=x, R=rl, a=0.32)
        for az in c['longeron_az_deg']:
            make(f'S5N_Frame_Spoke_{i:02d}_{az:05.1f}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC4, note='spoke: keel ring to longeron', trace=T('frames'),
                 points=[pol(x, 5.0, az), pol(x, rl, az)], radius=0.2)
        for j in range(3):
            make(f'S5N_Frame_Hub_Spoke_{i:02d}_{j}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC4, trace=T('frames'),
                 points=[pol(x, rs, 30+120*j), pol(x, 5.0, 30+120*j)], radius=0.2)
    for v in tanks:                                                  # girder to each polar boss + saddle (J4)
        az = v['azimuth_deg']; nm = v['name'].replace('FDP1_', '')
        for end, xe, xf, kind in (('Aft', v['x0'], v['x0']-1.0, 'FIXED'), ('Fwd', v['x1'], v['x1']+1.0, 'SLIDING')):
            make(f'S5N_Girder_{nm}_{end}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC4,
                 note='two-chord girder (1.8 m deep) from the keel ring to the polar boss', trace=T('frames'),
                 points=[pol(xf, 5.0, az), (xf, v['y'], v['z'])], radius=0.22)
            make(f'S5N_Saddle_{nm}_{end}', 'ring', coll, 'SERVICE', gen, 'PROTOTYPE', 'VTX-04', SRC4,
                 note=f'J4 polar-boss saddle, {kind}: G10/CFRP isolating struts (1.5-20 K tank on a warm frame); '
                      + ('sliding boss takes the 0.1 m axial contraction' if kind == 'SLIDING' else 'fixed boss carries the axial burn load')
                      + (f"; isolated at {c['tank_saddles']['recommend_Hz'][0]:.0f}-{c['tank_saddles']['recommend_Hz'][1]:.0f} Hz (T00: passes 0.3-2.3 % of the pulse ripple)" if 'tank_saddles' in c else ''),
                 trace=T('J4'), x0=min(xe, xf), x1=max(xe, xf), r0=0.0, r1=0.9 if kind == 'FIXED' else 0.7, centre=(v['y'], v['z']))
    # J1 root diaphragm (X 137.9-140.75) and J3 bow frame (X 413.25-416.15): radial deep girders at the longeron azimuths
    for jn, xa, xb, why in (('J1', 137.9, 140.75, 'J1 root diaphragm: longeron feet land on the canon farm front frame (farm r 7.75-34.5 m, canon, unmodified); '
                                                      'deep radial girders shear the longeron forces into the keels and spine sleeve'),
                            ('J3', x1-2.9, x1, 'J3 bow frame: spine to the shield spine column, keels to the Brow sector keels, longerons to the Brow outer truss ring')):
        xm = (xa+xb)/2
        if 'joints' in c:
            jj = c['joints'][jn]
            why += ('; T00 loads: ' + ', '.join(f"{k_.replace('_', ' ')} {v_:,.2f}" for k_, v_ in jj.items()) + ' (beam model; FE not done)')
        make(f'S5N_{jn}_Outer_Ring', 'torus', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC4, note=why, trace=T(jn), x=xm, R=rl, a=0.6)
        make(f'S5N_{jn}_Keel_Ring', 'torus', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC4, note=why, trace=T(jn), x=xm, R=5.0, a=0.5)
        make(f'S5N_{jn}_Spine_Sleeve', 'ring', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC4, note='splice sleeve on the spine', trace=T(jn), x0=xa, x1=xb, r0=rs, r1=rs+0.25)
        for az in c['longeron_az_deg']:
            for xx in (xa, xb):
                make(f'S5N_{jn}_Girder_Chord_{az:05.1f}_{int(xx)}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC4, trace=T(jn),
                     points=[pol(xx, rs+0.25, az), pol(xx, rl, az)], radius=0.25)
            make(f'S5N_{jn}_Girder_Diag_{az:05.1f}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC4, trace=T(jn),
                 points=[pol(xa, rl, az), pol(xb, 5.0, az)], radius=0.18)
            make(f'S5N_{jn}_Longeron_Foot_{az:05.1f}', 'box', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC4, note='longeron end fitting', trace=T(jn),
                 centre=pol(xa if jn == 'J1' else xb, rl, az), size=(1.6, 1.6, 1.6), roll=az)


def build_access_r4(gen, coll):
    """K2 corridor kept independent of the primary structure: it rides on sliding mounts at each frame (no axial load, no strain from the
    stretch); robot rails on keel 270 (inner) and along the longeron nearest az 276 (outer inspection); bay crawlways along the frame girder to
    the inner tank at az 93.7; service trays (power, data, cryo vent) on keel 150, away from K2 and the robot rails."""
    x0, x1 = ST3['x_m']; frames = stretch_frames(x0-1.0, x1); rl = ST4['cases']['S5_N9_NESTED']['longeron_r_m']
    T = lambda p: tr4('T05-ISS-015', p, 'VTX-04')
    cy, cz = pol(0, 3.0, 90.0)[1:]
    for i, x in enumerate(frames):
        for side in (-1, 1):
            make(f'K2R4_Sliding_Mount_{i:02d}_{side:+d}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-04', SRC4,
                 note='K2 sliding mount on the frame: carries the tube laterally, lets the stretch strain past it axially (corridor is not primary structure)',
                 trace=T('build_vertex.py build_access_r4'), points=[(x, cy+side*1.0, cz), (x, *pol(0, 5.0, 90.0+side*25)[1:])], radius=0.09)
        make(f'K2R4_Robot_Station_{i:02d}', 'box', coll, 'SERVICE', gen, 'PROTOTYPE', 'VTX-04', SRC4, note='robot dock / charger at the frame on the keel-270 rail',
             trace=T('robot rail'), centre=pol(x+1.5, 5.9, 270.0), size=(1.6, 0.9, 0.9), roll=270.0)
        make(f'K2R4_Bay_Crawlway_{i:02d}', 'tube', coll, 'HABITAT', gen, 'PROTOTYPE', 'VTX-04', SRC4, alpha=0.6,
             note='unpressurised crawlway along the frame girder from K2 to the inner tank saddles (EVA or robot)', trace=T('crawlway'),
             points=[(x, cy, cz+1.2), pol(x, 12.0, 93.7)], radius=0.45)
    make('K2R4_Robot_Rail_Outer', 'tube', coll, 'SERVICE', gen, 'PROTOTYPE', 'VTX-04', SRC4, note='outer inspection rail along the longeron at az 276',
         trace=T('robot rail'), points=[pol(x0, rl-0.9, 276.0), pol(x1, rl-0.9, 276.0)], radius=0.1)
    make('K2R4_Service_Tray_Keel150', 'box', coll, 'POWER', gen, 'PROTOTYPE', 'VTX-04', SRC4,
         note='service tray on keel 150: power and data trunks, cryo vent; separate from K2 (az 90) and the robot rails (270)',
         trace=T('services'), centre=pol((x0+x1)/2, 5.9, 150.0), size=(x1-x0, 0.8, 0.5), roll=150.0)


def build_coil_plant(key, gen, e, coll, fluid='LI_LOOP_HX'):
    """Armour coolant lines from rev4.json coil_plant: C2 -> C1 along the C2-C1 ties, C1 -> reaction ring along the six sized struts (lines on
    the strut's shadowed side), ring -> hot-band root inside the shield shadow, where the Li/Sn heat exchanger and pumps sit."""
    pk = f'{fluid}:{key}'; pl = CP4['cases'][pk]; xB = e['x_burn_m']
    c1, c2 = e['closure_coils']; b1 = CA4['coils']['C1']['builds'][key]; b2 = CA4['coils']['C2']['builds'][key]
    xr, ring_r, _, S, TI = r4_supports(e, key); w0 = PREF['hot_x_m'][0]
    strut_r = b1['struts']['width_m']/2 if 'struts' in b1 else 0.8
    tie_r = b2['struts']['width_m']/2 if 'struts' in b2 else 0.4
    side_sgn = {'Supply': -1.0, 'Return': 1.0}
    L = {l['leg']: l for l in pl['lines']}
    T = lambda leg: tr4('T05-ISS-014', f'rev4.json coil_plant.cases.{pk}.lines.{leg}')

    def shadow_offset(p, q, dist):
        """shift a line p->q by dist away from the burn point (into the strut's own shadow)."""
        mx, my, mz = [(a+b)/2 for a, b in zip(p, q)]
        v = (mx-xB, my, mz); n = math.sqrt(sum(t*t for t in v)); v = [t/n for t in v]
        d = [b-a for a, b in zip(p, q)]; dn = math.sqrt(sum(t*t for t in d)); d = [t/dn for t in d]
        dot = sum(a*b for a, b in zip(v, d)); w = [a-dot*b for a, b in zip(v, d)]; wn = math.sqrt(sum(t*t for t in w)); w = [t/wn for t in w]
        return [tuple(a+dist*b for a, b in zip(pt, w)) for pt in (p, q)]
    for j in range(6):
        az = 60.0*j+30.0
        for side, daz in (('Supply', -1.6), ('Return', 1.6)):
            # C1 -> reaction ring, behind the 0.8 m strut
            lr1 = L['C1_to_ring']['line_r_m']; lr2 = L['C2_to_C1']['line_r_m']; tandem = side == 'Return'   # pair in tandem behind the strut: never wider than it
            p, q = shadow_offset(*S[j], strut_r+lr1+0.05+(2*lr1+0.05 if tandem else 0.0))
            if lr1 > strut_r:
                CHECKS.setdefault('rev4_plant_warnings', []).append(f'C1 line r {lr1:.2f} wider than strut r {strut_r:.2f}: line not fully shadowed')
            make(f'Plant_{key}_C1_{side}_{j+1}', 'tube', coll, 'HOT_RADIATOR', gen, 'PROTOTYPE', 'VTX-03D', SRC4,
                 note=f"{fluid} {side.lower()} line r {L['C1_to_ring']['line_r_m']:.2f} m, wall {L['C1_to_ring']['wall_m']*1e3:.0f} mm, in tandem in the shadow of C1 strut {j+1}",
                 trace=T('C1_to_ring'), points=[p, q], radius=L['C1_to_ring']['line_r_m'])
            # C2 -> C1 along the tie
            p, q = shadow_offset(*TI[j], tie_r+lr2+0.05+(2*lr2+0.05 if tandem else 0.0))
            make(f'Plant_{key}_C2_{side}_{j+1}', 'tube', coll, 'HOT_RADIATOR', gen, 'PROTOTYPE', 'VTX-03D', SRC4,
                 note=f"{fluid} {side.lower()} line r {L['C2_to_C1']['line_r_m']:.2f} m behind C2-C1 tie {j+1}", trace=T('C2_to_C1'),
                 points=[p, q], radius=L['C2_to_C1']['line_r_m'])
            # reaction ring -> hot-band root, inside the shield shadow (r below the 5.5 deg hardware cone)
            rr = 5.6+(0.9 if side == 'Return' else 0.0)
            make(f'Plant_{key}_Trunk_{side}_{j+1}', 'tube', coll, 'HOT_RADIATOR', gen, 'PROTOTYPE', 'VTX-03D', SRC4,
                 note=f"{fluid} trunk r {L['ring_to_hot_root']['line_r_m']:.2f} m along the module, shield shadow", trace=T('ring_to_hot_root'),
                 points=[pol(xr+0.9, ring_r-0.3, az+daz), pol(e['x_shield_fwd_m']+0.5, rr, az+daz), pol(w0-4.0, rr, az+daz)], radius=L['ring_to_hot_root']['line_r_m'])
    # Li/Sn heat exchangers and pumps at the hot-band root (inside the shadow)
    hx_kg = pl['hx_kg']; vol = max(hx_kg/3000.0, 1.0)                      # about 3 t/m3 compact HX, PROTOTYPE
    for j in range(3):
        az = 120.0*j+60.0
        make(f'Plant_{key}_HX_{j+1}', 'box', coll, 'HOT_RADIATOR', gen, 'PROTOTYPE', 'VTX-03D', SRC4,
             note=f"{'Li/Sn heat exchanger' if fluid == 'LI_LOOP_HX' else 'tin header'} 1/3: {pl['heat_W']/3e9:.2f} GW, {hx_kg/3e3:.0f} t (20 t/GW PROTOTYPE)",
             trace=tr4('T05-ISS-014', f'rev4.json coil_plant.cases.{pk}.hx_kg'), centre=pol(w0-6.0, 6.0, az), size=(4.0, (vol/3/4.0)**0.5, (vol/3/4.0)**0.5), roll=az)
        make(f'Plant_{key}_Pump_{j+1}', 'capsule', coll, 'POWER', gen, 'PROTOTYPE', 'VTX-03D', SRC4,
             note=f"EM pump 1/3: {pl['pump_electric_W']/3e6:.1f} MWe ({pl['pump_hydraulic_W']/3e6:.1f} MW hydraulic, eta 0.5)",
             trace=tr4('T05-ISS-014', f'rev4.json coil_plant.cases.{pk}.pump_electric_W'), centre=pol(0, 6.0, az+20)[1:], radius=0.6, x0=w0-13.5, x1=w0-10.5)


# ----------------------------------------------------------------------------------------------------------------------------------
# measurements on the built geometry inputs (written to checks.json)
# ----------------------------------------------------------------------------------------------------------------------------------
def measure(gen, R, e, mod, x45):
    w = e['wing']; c1 = e['closure_coils'][0]; xa = C['ring_a_aft_face_x_m']
    xB = e['x_burn_m']; t = math.tan(math.radians(e['hardware_cone_deg']))
    dock_x = C['dock_primary']['x_m']
    m = {
        'hot_band_fwd_edge_to_ring_A_m': xa-w['x_m'][1],
        'C1_envelope_to_hot_band_aft_edge_m': w['x_m'][0]-(c1['x_m']+c1['envelope_r_m'][1]),
        'C1_to_shield_aft_face_m': e['x_shield_aft_m']-c1['x_m'],
        'wing_fwd_edge_to_dock_x_m': dock_x-w['x_m'][1],
        'dock_az_off_wing_plane_deg': {'primary': abs(C['dock_primary']['az_deg']-180.0), 'service': abs(360.0-C['dock_service']['az_deg'])},
        'skirt_r_at_dock_m': (dock_x-xB)*t, 'skirt_x_at_r45_m': x45, 'skirt_r_at_ring_A_m': (xa-xB)*t,
        'ring_A_inside_hardware_cone': (xa-xB)*t > C['ring_outer_r_m'],
        'hardware_cone_margin_at_ring_A_m': (xa-xB)*t-C['ring_outer_r_m'],
        'tank_farm_r_m': 34.5, 'hardware_cone_r_at_farm_front_m': (C['tank_farm_x_m'][1]+e['tanks_TB']['added_length_m']-xB)*t,
        'module_corridor': mod,
        'ring_A_irradiance_W_m2': e['ring_A_irradiance']['hot_band']['aft_face']['W_m2'],
        'C1_irradiance_W_m2': e['closure_coil_C1_irradiance'],
        'loop_struts_at_wing_plane_azimuths': any(abs(math.sin(math.radians(360.0*j/6))) < 1e-6 for j in range(6)),
        'loop_struts_overlap_wing_chord_in_x': e['x_shield_aft_m'] > w['x_m'][0],
        'C1_envelope_radial_gap_to_shield_rim_m': c1['r_m']-c1['envelope_r_m'][1]-e['shield_r_hw_m'],
        'C1_r_vs_hardware_cone_r_at_C1_m': [c1['r_m'], (c1['x_m']-xB)*t],
        'L1_strut_x_range_m': [e['loops'][0]['x_m'], e['x_shield_aft_m']], 'wing_aft_x_m': w['x_m'][0],
        'C2_struts_vs_wing': 'C2 ties run X {:.1f} to {:.1f} m, aft of the wing edge X {:.1f} m'.format(e['closure_coils'][1]['x_m'], c1['x_m'], w['x_m'][0]),
    }
    # does the bow-shifted forward shield still cover the farm? (forward shield r 45 m; farm r 34.5 m)
    m['farm_inside_forward_shield_shadow'] = 34.5 < 45.0
    CHECKS['generations'][gen] = m
    return m


# ----------------------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------------------
# Revision 4 (T00 inputs): axis plasma keep-out, rejected axis plug, launcher B-modified overlay, B-ray concept, coupled-ship ghost
# ----------------------------------------------------------------------------------------------------------------------------------
LR4 = REV4['launcher']; SRC_T00 = 'T00 9rsgog f180b63 results/t05_handoff_rev4.json + 853b867 studies/rev4/results/proposals.json'


def ray_pt(e, d, polar, az):
    th = math.radians(polar)
    return pol(e['x_burn_m']+d*math.cos(th), d*math.sin(th), az)


def build_axis_keepout(gen, e, coll):
    """Near-axis plasma has no stopping radius (T03 thin shell, polar 0): it reaches the shield face and anything on the axis. Drawn as a
    keep-out cone to polar 6 deg (VIS_CONFLICT, never hardware) and the shield-face centre marked as an open blocker."""
    ap = LR4['axis_plasma']; xB = e['x_burn_m']; xSA = e['x_shield_aft_m']; r_f = (xSA-xB)*math.tan(math.radians(6.0))
    T = lambda p: tr4('T05-ISS-022', f'rev4.json launcher.axis_plasma.{p}', 'VTX-06A')
    make('AX4_KEEP_OUT_Axis_Plasma_Channel', 'frustum', coll, 'VIS_CONFLICT', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-06A', SRC_T00, rep='VISUALIZATION', alpha=0.3,
         note=f"KEEP-OUT: unstopped near-axis plasma (no stopping radius at polar 0; 10 deg stops at 44.5 m on V4): {ap['shield_plasma_W']/1e9:.0f} GW onto the shield face, "
              f"{ap['shield_mean_J_cm2_per_pulse']:.0f} J/cm2 per pulse, {ap['shield_mean_MW_m2']:.0f} MW/m2 mean. No hardware may sit in it (T00)",
         trace=T('shield_plasma_W'), x0=xB+0.5, r0=0.05, x1=xSA-0.02, r1=r_f)
    make('AX4_OPEN_BLOCKER_Shield_Face_Centre', 'ring', coll, 'VIS_CONFLICT', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-06A', SRC_T00, rep='VISUALIZATION', alpha=0.9,
         note=f"OPEN BLOCKER: the shield-face centre stays in the axial channel ({ap['shield_mean_J_cm2_per_pulse']:.0f} J/cm2 per pulse, about 100x the CFC "
              "single-pulse range); needs a field-topology or target-design answer in the next phase (T00 853b867). Not solved in Rev 4",
         trace=T('shield_mean_J_cm2_per_pulse'), x0=xSA-0.06, x1=xSA-0.01, r0=0.0, r1=r_f)


def build_axis_plug_rejected(gen, e, coll):
    p = REV4['axis_plug_T05_proposal']; xB = e['x_burn_m']; xp = xB+p['x_from_burn_m']
    T = lambda q: tr4('T05-ISS-022', f'rev4.json axis_plug_T05_proposal.{q}', 'VTX-06A')
    make('AXP_REJECTED_Li_Droplet_Sheet', 'ring', coll, 'VIS_CONFLICT', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-06A', SRC_T00, rep='VISUALIZATION', alpha=0.8,
         note=f"REJECTED (T00: NOT PLAUSIBLE): renewable Li droplet sheet {p['x_from_burn_m']:.0f} m from the burn, r {p['r_m']:.2f} m; takes "
              f"{p['intercepted_W'][0]/1e9:.0f}-{p['intercepted_W'][1]/1e9:.0f} GW ({p['raw_J_cm2_per_pulse']:,.0f} J/cm2 per pulse); ions stop in < 1 mm of Li so droplets vaporise; "
              f"{p['li_mission_t_range'][0]/1e6:.0f}-{p['li_mission_t_range'][1]/1e6:.0f} Mt of Li over the mission",
         trace=T('status'), x0=xp-0.3, x1=xp+0.3, r0=0.0, r1=p['r_m'])
    make('AXP_REJECTED_Axial_Feed', 'tube', coll, 'VIS_CONFLICT', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-06A', SRC_T00, rep='VISUALIZATION', alpha=0.6,
         note='REJECTED: axial Li feed from the shield face to the sheet', trace=T('medium'), points=[(xp+0.3, 0, 0), (e['x_shield_aft_m'], 0, 0)], radius=0.3)


def build_launcher_bmod(gen, R, e, coll):
    """B-modified overlay on the Rev 3 B layout (T00 handoff launcher.B_modified): same kinematics, contactless coilgun, 30 K gas-filled HDC
    capsule, split EM sabot stripped before the snout into a catcher in the shadow cone, chopper at the snout tip, the barrel on a kinematic
    rail (flexure mounts) that is not a spine member, CFC 2.5 mm on the snout face. TARGET PHYSICS UNPROVEN."""
    b = LR4['B_modified']; tg = LR4['target']; o = LOPT['B']; tip = o['muzzle_x_m']; xSF = R['layout']['x_shield_fwd']; ap = LR4['axis_plasma']
    T = lambda p: tr4('T05-ISS-023', f'rev4.json launcher.{p}', 'VTX-01H')
    head = (f"B-MODIFIED (T00: CANDIDATE, TARGET PHYSICS UNPROVEN): {b['accelerator_m']:.0f} m contactless coilgun, {b['muzzle_m_s']/1e3:.2f} km/s at {b['accel_g']:,.0f} g, "
            f"{b['rate_Hz']:.0f} Hz, {b['electric_W']/1e6:.0f} MWe, {b['launcher_kg']/1e3:.0f} t; target: {tg['class']}, wall {tg['wall_um']:.0f} um, limit {tg['limit_g']:,.0f} g")
    k = 0; x = BREECH_X-6.0
    while x > tip+8.0:
        for j in range(3):
            make(f'LBM_Kinematic_Mount_{k:02d}_{j}', 'tube', coll, 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-01H', SRC_T00,
                 note='kinematic rail flexure: carries the barrel laterally, not a spine member (no stretch strain into the barrel); ' + head, trace=T('B_modified.launcher_kg'),
                 points=[pol(x, 0.62, 120.0*j+60.0), pol(x, 0.9, 120.0*j+60.0)], radius=0.045)
        x -= 24.0; k += 1
    make('LBM_Sabot_Catcher', 'ring', coll, 'HOT_RADIATOR', gen, 'PROTOTYPE', 'VTX-01H', SRC_T00,
         note=f"split EM sabot stripped before the snout; catcher {b['sabot_catcher_W']/1e6:.0f} MW in the shadow cone, sabot {b['sabot_kg']*1e3:.1f} g per shot",
         trace=T('B_modified.sabot_catcher_W'), x0=xSF+10.3, x1=xSF+13.0, r0=0.42, r1=1.05)
    make('LBM_Snout_Face_CFC', 'ring', coll, 'SHIELD', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-06A', SRC_T00,
         note=f"CFC monoblocks 2.5 mm on Mo-TZM Li tubes on the snout tip face (T00 surfaces); tip X-ray {b['tip_xray_J_cm2']:.1f} J/cm2 per pulse; renewable Li is the fallback",
         trace=T('B_modified.tip_xray_J_cm2'), x0=tip-0.03, x1=tip, r0=0.3, r1=0.75)
    make('LBM_CONFLICT_Chopper_Rim_In_Axis_Plasma', 'torus', coll, 'VIS_CONFLICT', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-06A', SRC_T00, rep='VISUALIZATION', alpha=1.0,
         note=f"chopper rim (500 m/s) and the snout tip sit inside the unstopped axis plasma channel ({ap['shield_mean_J_cm2_per_pulse']:.0f} J/cm2 per pulse at the shield face); "
              "UNSOLVED in Rev 4", trace=T('shutter.note'), x=tip+1.68, R=0.55, a=0.12)
    make('LBM_Target_Capsule_Marker', 'sphere', coll, 'VIS_SAFE', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-01C', SRC_T00, rep='VISUALIZATION', alpha=1.0,
         note=f"PLACEHOLDER (survivability UNPROVEN): 30 K gas-filled HDC capsule, fill {tg['fill_MPa']:.1f} MPa, wall {tg['wall_um']:.0f} um, "
              f"limit {tg['limit_g']:,.0f} g (x{tg['limit_g']/b['accel_g']:.1f} on 13,700 g), convergence {tg['convergence_to_2000']:.0f}; marker 5x scale",
         trace=T('target.limit_g'), centre=(BREECH_X-2.0, 0.0, 0.0), radius=0.25)


def build_launcher_bray(gen, R, e, coll):
    """B-ray (T05 concept, T00 853b867: KINEMATICS PLAUSIBLE): barrel on a burn ray (polar 12, az 120), so the burn sees only its tip;
    tip moved out to 56.5 m (1.3x the V4 stopping radius), 208 m barrel at 30,000 g. Off the axis it does not need the plug. Mounted on the
    shield frame and the C1 strut ring, not on the spine; the breech lands 55 m off axis and its support is UNSIZED."""
    br = LR4['B_ray']; pr, az = br['polar_deg'], br['az_deg']; d0 = br['tip_from_burn_m']; L = br['accelerator_m']; d1 = d0+L
    xB = e['x_burn_m']; xSF = R['layout']['x_shield_fwd']; xSA = e['x_shield_aft_m']
    T = lambda p: tr4('T05-ISS-023', f'rev4.json launcher.B_ray.{p}', 'VTX-01H')
    head = (f"B-RAY (CONCEPTUAL; T00: kinematics plausible): {L:.0f} m barrel on a burn ray, polar {pr:.0f} deg az {az:.0f}; {br['muzzle_m_s']/1e3:.1f} km/s at {br['accel_g']:,.0f} g; "
            f"capsule SF {br['gas_capsule_SF']:.1f}; EM armature and sabot at 30,000 g NOT DEMONSTRATED")
    make('LBR_Accelerator_Barrel', 'tube', coll, 'MAIN_PROPULSION', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-01H', SRC_T00, note=head, trace=T('accelerator_m'),
         points=[ray_pt(e, d1, pr, az), ray_pt(e, d0+1.5, pr, az)], radius=0.35)
    d = d1-12.0; k = 0
    while d > d0+4.0:
        fld = max((f['B_T_upper'] for f in br['field_along_ray'] if abs(f['distance_m']-d) <= 12.0), default=0.0)
        make(f'LBR_Drive_Stage_{k:02d}', 'tube', coll, 'POWER', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-01H', SRC_T00,
             note=f'coilgun stage at {d:.0f} m from the burn; vacuum field up to {fld:.1f} T here (upper bound; stages and stripper sit in the coil field)',
             trace=T('field_along_ray'), points=[ray_pt(e, d+0.6, pr, az), ray_pt(e, d-0.6, pr, az)], radius=0.6)
        d -= 12.0; k += 1
    make('LBR_Tip_Cartridge_Chopper', 'tube', coll, 'SHIELD', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-06A', SRC_T00,
         note=f"tip cartridge + chopper, CFC 2.5 mm face; {br['tip_xray_J_cm2']:.1f} J/cm2 per pulse, {br['tip_MW_m2']:.1f} MW/m2; "
              f"{br['margin_to_stopping_surface_m']:.0f} m outside the V4 stopping surface", trace=T('tip_MW_m2'),
         points=[ray_pt(e, d0+1.5, pr, az), ray_pt(e, d0, pr, az)], radius=0.75)
    make('LBR_Line_Of_Sight', 'tube', coll, 'VIS_XRAY', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-01H', SRC_T00, rep='VISUALIZATION', alpha=0.9,
         note=f"open flight {d0:.1f} m along the ray, crossed in one pulse interval", trace=T('tip_from_burn_m'), points=[ray_pt(e, d0, pr, az), (xB, 0, 0)], radius=0.25)
    make('LBR_Stopping_Surface_Marker', 'sphere', coll, 'VIS_CONFLICT', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-06A', SRC_T00, rep='VISUALIZATION', alpha=0.6,
         note=f"V4 stopping surface on this ray ({br['stopping_radius_V4_m']['12_interp']:.1f} m); the Rev 4 first-draft 45 m tip sat on it", trace=T('stopping_radius_V4_m'),
         centre=ray_pt(e, br['stopping_radius_V4_m']['12_interp'], pr, az), radius=0.8)
    # mounts: C1 strut ring and shield frame (T00 alignment note); breech support UNSIZED
    xr, ring_r, _, _, _ = r4_supports(e, 'R4_T00_SHADOWED')
    for nm, xm, rr in (('C1_Strut_Ring', xr, ring_r), ('Shield_Frame', xSF, e['shield_r_hw_m'])):
        dm = (xm-xB)/math.cos(math.radians(pr))
        make(f'LBR_Mount_{nm}', 'tube', coll, 'STRUCTURE', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-01H', SRC_T00,
             note=f"barrel mount to the {nm.replace('_', ' ')} (T00: not on the spine); drift 0.5 um transverse, 2.3 um axial (negligible); UNSIZED",
             trace=T('alignment'), points=[ray_pt(e, dm, pr, az), pol(xm, rr, az)], radius=0.25)
    bx, brr = br['breech_xr_m']
    make('LBR_UNSIZED_Breech_Support', 'tube', coll, 'VIS_CONFLICT', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-01H', SRC_T00, rep='VISUALIZATION', alpha=0.5,
         note=f'breech {brr:.0f} m off axis at X {bx:.0f}: needs its own support back to the hull (UNSIZED, a cantilever of about {brr:.0f} m)', trace=T('breech_xr_m'),
         points=[pol(bx, brr, az), pol(bx, 6.0, az)], radius=0.3)
    make('LBR_Capsule_Station', 'box', coll, 'LOW_RADIATOR', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-01C', SRC_T00,
         note='capsule fill and 30 K conditioning at the breech (the module factory cannot reach an off-axis breech without crossing the module equipment)',
         trace=T('breech_xr_m'), centre=pol(bx+4.0, brr+0.4, az), size=(6.0, 2.4, 2.4), roll=az)
    make('LBR_Fuel_Feed_Line', 'tube', coll, 'DEUTERIUM', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-01C', SRC_T00,
         note='D / 3He feed from the tank-farm front frame, outside the hull and the rings, to the capsule station', trace=T('breech_xr_m'),
         points=[pol(137.9, 34.6, az), pol(bx+7.0, brr+0.4, az)], radius=0.1)


def build_ghost_coupled(gen, coll):
    gc = REV4['ghost_coupled']; x0 = ST3['x_m'][0]; L = gc['tank_stretch_length_m_if_same_section']; cp = gc['coupled_preferred']
    make('GH4_COUPLED_APPROXIMATION_Tank_Stretch', 'ring', coll, 'VIS_CONFLICT', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-04', SRC_T00, rep='VISUALIZATION', alpha=0.12,
         note=f"COUPLED APPROXIMATION (T00, not a converged design): {cp['departure_t']/1e3:.1f} kt departure, {cp['propellant_t']/1e3:.1f} kt propellant, "
              f"{cp['pellet_rate_Hz']:.0f} Hz, wing tip {cp['wing_tip_radius_m']:,.0f} m; stretch {L:.0f} m at the same section. V4 stays the drawn baseline",
         trace=tr4('T05-ISS-024', 'rev4.json ghost_coupled', 'VTX-04'), x0=x0, x1=x0+L, r0=33.9, r1=34.2)


bpy.ops.wm.read_factory_settings(use_empty=True)
for nm in list(bpy.data.scenes):
    pass
main = bpy.context.scene; main.name = 'VERTEX_V4'
SC = {'VERTEX_V4': main}
for nm in ('CANON_WAYFARER', 'VERTEX_V0', 'COMPARE_SIDE_BY_SIDE', 'COMPARE_TOP', 'COMPARE_SPAN', 'VERTEX_CUTAWAY', 'BRAKING_EXPOSURE',
           'RADIATOR_ALTERNATIVES', 'LAUNCHER_COMPARE', 'THERMAL_COMPARE', 'COIL_COMPARE', 'SKIRT_COMPARE', 'OPTIONS_LIBRARY',
           'STRUCTURE_COMPARE', 'STRUCTURE_SECTION', 'COIL_ASSEMBLY_SECTION', 'LAUNCHER_R4_COMPARE', 'REV3_VS_REV4'):
    SC[nm] = bpy.data.scenes.new(nm)

LIB = new_coll('VERTEX_LIBRARY', main.collection)          # every built collection hangs here once; scenes link what they show
ships, fps, HOT_BLADES = {}, {}, {}
if not a.no_ship:
    ships['CANON'] = append_ship('CANON_WAYFARER_SHIP_main'); fps['before'] = fingerprint(ships['CANON'])
    for g in ('V4', 'V0'):
        ships[g], HOT_BLADES[g], CHECKS.setdefault('ship_edits', {})[g] = prepare_working_copy(ships['CANON'], g)

ASM, VAR, COLL, OPT, OPTROOT = {}, {}, {}, {}, {}
CORR = {}
PREF = REV2['thermal']['preferred_rev2']


def opt_coll(g, k, color='COLOR_07'):
    c = new_coll(f'OPT_VERTEX_{g}_{k}', OPTROOT[g], color); OPT[g][k] = c
    return c


for g in GENS:
    R = RS[g]; e = ENV[g]
    top = bpy.data.collections.new(f'ASM_{g}'); ASM[g] = top
    root, colls = gen_collections(g, top); VAR[g] = root; COLL[g] = colls
    ghost = g == 'V5'
    if ghost:
        build_nozzle(g, R, e, colls, ghost=True)
        build_wings(g, R, e, colls, ghost=True)
        make('Shield_Ghost', 'frustum', colls['03'], 'SHIELD', g, 'ENGINEERING_SUPPORTED', 'VTX-06A', f'solve:{g}', alpha=0.15, wire=True,
             x0=e['x_shield_aft_m'], r0=e['shield_r_hw_m'], x1=e['x_shield_fwd_m'], r1=e['shield_r_hw_m'])
        make('StandOff_Ghost', 'sphere', colls['11'], 'VIS_XRAY', g, 'ENGINEERING_SUPPORTED', 'VTX-01', f'solve:{g}', rep='VISUALIZATION', alpha=0.08,
             wire=True, centre=(e['x_burn_m'], 0, 0), radius=e['stand_off_m'])
        continue
    if g in ships:
        top.children.link(ships[g])
    # Rev 2: everything that has alternatives is an option collection (OPT_VERTEX_<g>_*); the assembly links the chosen ones
    OPT[g] = {}; OPTROOT[g] = bpy.data.collections.new(f'OPT_VERTEX_{g}'); OPTROOT[g].color_tag = 'COLOR_07'
    opt_coll(g, 'LAUNCH_REV1'); opt_coll(g, 'SUP_REV1', 'COLOR_02'); opt_coll(g, 'WINGS_CALC', 'COLOR_01')
    opt_coll(g, 'SPINE_EXT', 'COLOR_02'); opt_coll(g, 'DOCK_ROUTES', 'COLOR_03'); opt_coll(g, 'COIL_ENV_REV3', 'COLOR_04')
    opt_coll(g, 'DUST_GUARDS_REV2', 'COLOR_04')
    build_fdp_parts(g, R, colls, breech=OPT[g]['LAUNCH_REV1'])
    build_nozzle(g, R, e, colls, support=OPT[g]['SUP_REV1'], env_coll=OPT[g]['COIL_ENV_REV3'], bumper_coll=OPT[g]['DUST_GUARDS_REV2'])
    CORR[g] = build_module(g, R, e, colls, launch=OPT[g]['LAUNCH_REV1'])
    build_wings(g, R, e, colls, coll=OPT[g]['WINGS_CALC'])
    build_overlays(g, R, e, colls['01'])
    skirts, x45 = build_skirts(g, R, e, OPTROOT[g])
    COLL[g]['skirts'] = skirts
    build_spine_extension(g, e, OPT[g]['SPINE_EXT'])
    build_dock_routes(g, OPT[g]['DOCK_ROUTES'])
    measure(g, R, e, CORR[g], x45)
    if g == 'V4':
        build_launcher('REV1', g, R, e, OPT[g]['LAUNCH_REV1'])
        for k in ('A', 'B', 'C'):
            build_launcher(k, g, R, e, opt_coll(g, f'LAUNCH_{k}'))
        build_lane_core_launch(g, R, e, opt_coll(g, 'LANE_CORE_LAUNCH'))
        build_wings(g, R, e, colls, graded=(PREF['hot_x_m'][0], PREF['hot_x_m'][1], PREF['hot_r_m'][1]), coll=opt_coll(g, 'WINGS_PREF', 'COLOR_01'),
                    label='_GRADED', tip_override=PREF['tip_r_m'])
        build_coil_protection(g, R, e, {'P1': opt_coll(g, 'COIL_P1', 'COLOR_04'), 'P2': opt_coll(g, 'COIL_P2', 'COLOR_04'),
                                        'FAN': opt_coll(g, 'COIL_XRAY_FAN'), 'SUP': opt_coll(g, 'COIL_SUP_SIZED', 'COLOR_02'),
                                        'CORE': opt_coll(g, 'LANE_CORE_COIL')})
        # Rev 3: stretch structure options, corridors, B-long outline, coil cooling, tank ghosts for the lanes
        for k in ('S1_SPINE_ONLY', 'S2_CANON_SECTORS', 'S3_OUTER_CAGE', 'S4_SECTORS_PLUS_BELT'):
            build_stretch(k, g, opt_coll(g, 'STRUCT_'+k[:2], 'COLOR_02'))
        for k in ('K1_TRUNK_IN_SPINE', 'K2_TUBE_BESIDE_SPINE'):
            build_corridor(k, g, opt_coll(g, 'CORR_'+k[:2], 'COLOR_04'))
        build_tb_section_core(g, R, opt_coll(g, 'LANE_CORE_TB'))
        build_launcher_long(g, R, e, opt_coll(g, 'LAUNCH_B_LONG'))
        build_coil_cooling(g, R, e, opt_coll(g, 'COIL_COOLING', 'COLOR_01'))
        # Rev 4: coil assemblies as layered sections (preferred R4_NOMINAL + thickness alternatives) and the armour coolant plant
        for k, oc in (('R4_NOMINAL', 'COIL_ASM_R4'), ('R4_COMPACT', 'COIL_ASM_COMPACT'), ('R4_STEEL_CASE', 'COIL_ASM_STEEL'), ('T03_3X_WINDING', 'COIL_ASM_T03')):
            build_coil_assembly(k, g, e, opt_coll(g, oc, 'COLOR_04'), detail=(k == 'R4_NOMINAL'))
        build_coil_assembly('R4_T00_SHADOWED', g, e, opt_coll(g, 'COIL_ASM_T00', 'COLOR_04'), detail=True)
        build_coil_supports_r4('R4_T00_SHADOWED', g, e, opt_coll(g, 'COIL_SUP_R4', 'COLOR_02'))
        build_coil_plant('R4_T00_SHADOWED', g, e, opt_coll(g, 'COIL_PLANT_LI', 'COLOR_01'), fluid='LI_LOOP_HX')
        build_coil_plant('R4_NOMINAL', g, e, opt_coll(g, 'COIL_PLANT_SN', 'COLOR_01'), fluid='SN_DIRECT')
        build_dust_guards_r4(g, R, e, opt_coll(g, 'DUST_GUARDS_R4', 'COLOR_04'))
        build_stretch_r4(g, R, opt_coll(g, 'STRUCT_S5N', 'COLOR_02'), key='S5_N9_T00')
        build_axis_keepout(g, e, opt_coll(g, 'AXIS_KEEPOUT'))
        build_axis_plug_rejected(g, e, opt_coll(g, 'AXIS_PLUG_REJECTED'))
        build_launcher_bmod(g, R, e, opt_coll(g, 'LAUNCH_BMOD'))
        build_launcher_bray(g, R, e, opt_coll(g, 'LAUNCH_BRAY'))
        build_ghost_coupled(g, opt_coll(g, 'GHOST_COUPLED'))
        build_access_r4(g, opt_coll(g, 'ACCESS_R4', 'COLOR_04'))
        chosen = ['LAUNCH_B', 'LAUNCH_BMOD', 'AXIS_KEEPOUT', 'WINGS_PREF', 'COIL_ASM_T00', 'COIL_PLANT_LI', 'COIL_SUP_R4', 'DUST_GUARDS_R4', 'STRUCT_S5N', 'CORR_K2', 'ACCESS_R4', 'DOCK_ROUTES']
        chosen_sk = 'B2_DOCK_CLEAR'
    else:
        chosen = ['LAUNCH_REV1', 'SUP_REV1', 'WINGS_CALC', 'SPINE_EXT', 'DOCK_ROUTES', 'COIL_ENV_REV3', 'DUST_GUARDS_REV2']
        chosen_sk = 'A_FULL'
    for k in chosen:
        top.children.link(OPT[g][k])
    top.children.link(skirts[chosen_sk])
    if g == 'V0' and g in HOT_BLADES:
        top.children.link(HOT_BLADES[g])               # V0 stays the Rev 1 historical layout (canon blades kept beside its wing)
    CHECKS.setdefault('assemblies', {})[g] = {'options': chosen+[chosen_sk], 'canon_hot_blades_shown': g == 'V0',
                                              'note': 'V4 Rev 4: COIL_ASM_T00 (T00 shadowed build) + COIL_PLANT_LI + COIL_SUP_R4 replace Rev 3 COIL_P2 + COIL_COOLING + COIL_SUP_SIZED; STRUCT_S5N (S5_N9_T00) replaces S2 + S3; LAUNCH_BMOD overlays LAUNCH_B; AXIS_KEEPOUT is a keep-out, not hardware' if g == 'V4' else ''}

# V4 as chosen in Revision 3 (for the Rev 3 -> Rev 4 comparison and the ray-cast baseline)
ASM['V4_REV3'] = bpy.data.collections.new('ASM_V4_REV3_CHOSEN')
for c in ([ships['V4']] if 'V4' in ships else [])+[VAR['V4']]+[OPT['V4'][k] for k in ('LAUNCH_B', 'WINGS_PREF', 'COIL_P2', 'COIL_SUP_SIZED', 'COIL_COOLING', 'STRUCT_S2',
                                                                                   'STRUCT_S3', 'CORR_K2', 'DOCK_ROUTES', 'COIL_ENV_REV3', 'DUST_GUARDS_REV2')]+\
         [COLL['V4']['skirts']['B2_DOCK_CLEAR']]:
    ASM['V4_REV3'].children.link(c)

# V4 calculated layout as an assembly of its own (Rev 1 options, canon blades kept): thermal and launcher comparisons
ASM['V4_CALC'] = bpy.data.collections.new('ASM_V4_REV1_LAYOUT')
for c in ([ships['V4']] if 'V4' in ships else [])+[VAR['V4']]+[OPT['V4'][k] for k in ('LAUNCH_REV1', 'SUP_REV1', 'WINGS_CALC', 'SPINE_EXT', 'DOCK_ROUTES', 'COIL_ENV_REV3', 'DUST_GUARDS_REV2')]+\
         [COLL['V4']['skirts']['A_FULL']]+([HOT_BLADES['V4']] if 'V4' in HOT_BLADES else []):
    ASM['V4_CALC'].children.link(c)

# V4 extras: alternatives, graded band, dust stream, labels
e4 = ENV['V4']; R4 = RS['V4']
ALT = bpy.data.collections.new('VAR_VERTEX_V4_ALTERNATIVES'); ALT.color_tag = 'COLOR_07'
GRADED = OPT['V4']['WINGS_PREF']
OUTL = new_coll('VAR_VERTEX_V4_ALT_OUTLINES', ALT, 'COLOR_07')
build_alternatives('V4', e4, OUTL)
PANEL = new_coll('VAR_VERTEX_V4_ALT_PANEL_SKIN', ALT, 'COLOR_07')
w = e4['wing']
for side, az in (('P', 0.0), ('S', 180.0)):
    make(f'ALT_Panel_Skin_{side}', 'panel', PANEL, 'WARM_RADIATOR', 'V4', 'PARAMETRIC_PLACEHOLDER', 'VTX-07', '1.5 kg/m2 panels (T01, TARGET)',
         note='panel alternate: same area, about +3 % mass', alpha=0.9,
         corners=[pol(w['x_m'][0], w['hot_band_r_m'][1]+2, az), pol(w['x_m'][1], w['hot_band_r_m'][1]+2, az), pol(w['x_m'][1], w['tip_r_m'], az),
                  pol(w['x_m'][0], w['tip_r_m'], az)], thickness=0.3)
DUST = bpy.data.collections.new('VAR_VERTEX_OVERLAYS_DUST_STREAM'); DUST.color_tag = 'COLOR_07'
build_dust_stream('V4', e4, DUST)
OVL = bpy.data.collections.new('VAR_VERTEX_OVERLAYS'); OVL.color_tag = 'COLOR_07'
OVL.children.link(ALT); OVL.children.link(DUST)
LBL = new_coll('VAR_VERTEX_OVERLAYS_LABELS', OVL, 'COLOR_07')

# conflict markers (measured), in V4's keep-out group
m4 = CHECKS['generations']['V4']; xa = C['ring_a_aft_face_x_m']
make('CONFLICT_HotBand_RingA', 'tube', OPT['V4']['WINGS_CALC'], 'VIS_CONFLICT', 'V4', 'CONCEPTUAL_ILLUSTRATION', 'VTX-07F', 'checks.json', rep='VISUALIZATION',
     note=f"{m4['hot_band_fwd_edge_to_ring_A_m']:.1f} m; {m4['ring_A_irradiance_W_m2']/1e3:.0f} kW/m2 on ring A", points=[(w['x_m'][1], 30.0, 0.5), (xa, 30.0, 0.5)], radius=0.8, alpha=1.0)
c1 = e4['closure_coils'][0]
make('CONFLICT_C1_HotBand', 'tube', OPT['V4']['WINGS_CALC'], 'VIS_CONFLICT', 'V4', 'CONCEPTUAL_ILLUSTRATION', 'VTX-03D', 'checks.json', rep='VISUALIZATION',
     note=f"{m4['C1_envelope_to_hot_band_aft_edge_m']:.1f} m envelope gap", points=[(c1['x_m']+c1['envelope_r_m'][1], c1['r_m'], 0.5), (w['x_m'][0], c1['r_m'], 0.5)],
     radius=0.6, alpha=1.0)

# scale bars (alternating 100 m blocks; 1 km blocks for span views)
SB = new_coll('VAR_VERTEX_OVERLAYS_SCALE', OVL, 'COLOR_07')
for i in range(8):
    make(f'Scale_100m_{i}', 'box', SB, 'VIS_LABEL' if i % 2 else 'STRUCTURE', 'ALL', 'CONCEPTUAL_ILLUSTRATION', 'VTX-NONE', 'scale', rep='VISUALIZATION',
         centre=(-350+100*i+50, 0, -230), size=(100, 4, 8), alpha=1.0)
for i in range(20):
    make(f'Scale_1km_{i}', 'box', SB, 'VIS_LABEL' if i % 2 else 'STRUCTURE', 'ALL', 'CONCEPTUAL_ILLUSTRATION', 'VTX-NONE', 'scale', rep='VISUALIZATION',
         centre=(-2600, -10000+1000*i+500, 0), size=(60, 1000, 4), alpha=1.0)
text('scale_100m', 'scale: 100 m blocks', (-350, 0, -250), SB, size=12)
text('scale_1km', '1 km blocks', (-2600, -10000, 30), SB, size=220, facing='top', rot=(0, 0, math.radians(90)))

# labels and dimension callouts (side view facing -Y, top view facing +Z)
L = e4['loops']
labels_side = [
    ('v4_title', f"VERTEX V4 (research target, NON-CANON): {R4 and ENV['V4']['departure_t']:,.0f} t at departure, every mass a lower bound", (-340, 0, 215), 9),
    ('v4_len', f"length {e4['extent_x_m'][1]-e4['extent_x_m'][0]:,.0f} m: X {e4['extent_x_m'][0]:+.0f} (L3) to {e4['extent_x_m'][1]:+.0f} m (bow after the {e4['tanks_TB']['added_length_m']:.0f} m T-B stretch)", (-340, 0, 200), 7),
    ('burn', f"burn point X {e4['x_burn_m']:.1f} m, stand-off {e4['stand_off_m']:.1f} m, {R4['fusion']['pellet_rate_Hz']:.0f} Hz x {R4['fusion']['yield_per_pulse_J']/4.184e12:.1f} t TNT", (e4['x_burn_m']-60, 0, -80), 5),
    ('loops', f"loops r {L[0]['r_m']:.0f} / {L[1]['r_m']:.0f} / {L[2]['r_m']:.0f} m, 12 replaceable segments each, trim joints clocked 45 deg", (L[2]['x_m']-20, 0, L[2]['r_m']+12), 5),
    ('coils', f"closure coils C1 r {e4['closure_coils'][0]['r_m']:.1f} m, C2 r {e4['closure_coils'][1]['r_m']:.1f} m (PARAMETRIC, structure UNBOOKED)", (-215, 0, 52), 4),
    ('module', f"module: launcher B snout (8.8 km/s, 45 m open flight), ignitor, tritium store (PROTOTYPE)", (-185, 0, 14), 3),
    ('wing_edgeon', 'warm wings edge-on in this view (plane z = 0)', (-60, 0, -14), 4),
]
for nm, body, loc, sz in labels_side:
    text(nm, body, loc, LBL, gen='V4', size=sz)
labels_top = [
    ('span', f"V4 warm wings: tip r {w['tip_r_m']:,.0f} m, span {2*w['tip_r_m']:,.0f} m, {w['warm_planform_m2']/1e6:.2f} km2 at {w['warm_T_K']:.0f} K", (-2000, w['tip_r_m']+300, 5), 260),
    ('hotband', f"1,800 K band r {w['hot_band_r_m'][0]:.0f}-{w['hot_band_r_m'][1]:.0f} m", (-180, 900, 5), 30),
    ('ringgap', f"hot band to ring A {m4['hot_band_fwd_edge_to_ring_A_m']:.1f} m: {m4['ring_A_irradiance_W_m2']/1e3:.0f} kW/m2", (60, 40, 5), 3.5),
    ('c1gap', f"C1 envelope to hot band {m4['C1_envelope_to_hot_band_aft_edge_m']:.1f} m", (-215, 30, 5), 3.0),
    ('dock', f"docks X {C['dock_primary']['x_m']:.2f} m (az 195 / 315 deg): skirt A at r {m4['skirt_r_at_dock_m']:.1f} m here", (120, -50, 5), 3.5),
]
for nm, body, loc, sz in labels_top:
    text(nm, body, loc, LBL, gen='V4', size=sz, facing='top')

# ----------------------------------------------------------------------------------------------------------------------------------
# scenes
# ----------------------------------------------------------------------------------------------------------------------------------
def link(sc, coll):
    if coll.name not in sc.collection.children:
        sc.collection.children.link(coll)


def inst(sc, coll, loc, name):
    o = bpy.data.objects.new(name, None); o.instance_type = 'COLLECTION'; o.instance_collection = coll; o.location = loc
    sc.collection.objects.link(o)
    return o


def exclude(sc, names, flag=True):
    def walk(lc):
        if lc.collection.name in names:
            lc.exclude = flag
        for ch in lc.children:
            walk(ch)
    for vl in sc.view_layers:
        vl.update(); walk(vl.layer_collection)


main.collection.children.unlink(LIB)
LIB_ALL = [ASM['V4'], ASM['V0'], ASM['V5'], OVL]
link(SC['VERTEX_V4'], ASM['V4']); link(SC['VERTEX_V4'], ASM['V5']); link(SC['VERTEX_V4'], OVL)
exclude(SC['VERTEX_V4'], [PANEL.name, OUTL.name, DUST.name, VAR['V5'].name])
link(SC['VERTEX_V0'], ASM['V0'])
# every option collection is kept in one library scene (all excluded) so nothing is orphaned and each option can be switched on there
for g_ in OPTROOT:
    link(SC['OPTIONS_LIBRARY'], OPTROOT[g_])
link(SC['OPTIONS_LIBRARY'], ASM['V4_CALC'])
exclude(SC['OPTIONS_LIBRARY'], [c.name for g_ in OPTROOT for c in OPTROOT[g_].children]+[ASM['V4_CALC'].name])
if 'CANON' in ships:
    link(SC['CANON_WAYFARER'], ships['CANON'])

# compare: side-by-side in Z (side view), lanes in Y for the top view (wings hidden there), lanes in X for the span view
CMP_WINGLESS = {}
for nm, z in (('CANON', 0.0), ('V0', -260.0), ('V4', -640.0)):
    src = ships.get('CANON') if nm == 'CANON' else ASM[nm]
    if src is not None:
        inst(SC['COMPARE_SIDE_BY_SIDE'], src, (0, 0, z), f'CMP_SIDE_{nm}')
for nm, y in (('CANON', 0.0), ('V0', -260.0), ('V4', -640.0)):
    src = ships.get('CANON') if nm == 'CANON' else ASM[nm]
    if src is not None:
        inst(SC['COMPARE_TOP'], src, (0, y, 0), f'CMP_TOP_{nm}')
for nm, x in (('V4', 0.0), ('V0', 2200.0), ('CANON', 4000.0)):
    src = ships.get('CANON') if nm == 'CANON' else ASM[nm]
    if src is not None:
        inst(SC['COMPARE_SPAN'], src, (x, 0, 0), f'CMP_SPAN_{nm}')
inst(SC['COMPARE_SPAN'], OUTL, (0, 0, 0), 'CMP_SPAN_TIPS')
inst(SC['COMPARE_SIDE_BY_SIDE'], ASM['V5'], (0, 0, -640.0), 'CMP_SIDE_V5_GHOST')
for nm, body, loc in (('cmp_canon', 'CANONICAL WAYFARER (main, unchanged): 289.5 m body, four-nozzle Fiji drive', (-350, 0, 60)),
                      ('cmp_v0', f"V0 FDP-1 (HISTORICAL, needs coupling 2.1): {ENV['V0']['departure_t']:,.0f} t, {ENV['V0']['extent_x_m'][1]-ENV['V0']['extent_x_m'][0]:,.0f} m", (-350, 0, -260+125)),
                      ('cmp_v4', f"V4 RESEARCH TARGET: {ENV['V4']['departure_t']:,.0f} t, {e4['extent_x_m'][1]-e4['extent_x_m'][0]:,.0f} m (V5 bound as wire ghost)", (-350, 0, -640+185))):
    t_ = text(nm, body, loc, SC['COMPARE_SIDE_BY_SIDE'].collection, size=26)
for nm, body, loc in (('top_canon', 'CANONICAL', (-160, 60, 5)), ('top_v0', 'V0 FDP-1 (wings omitted in this view)', (-160, -260+125, 5)),
                      ('top_v4', 'V4 (wings omitted in this view; see COMPARE_SPAN)', (-160, -640+185, 5))):
    text(nm, body, loc, SC['COMPARE_TOP'].collection, size=26, facing='top')
for nm, body, loc in (('span_v4', f"V4  span {2*w['tip_r_m']:,.0f} m", (0-600, w['tip_r_m']+500, 5)),
                      ('span_v0', f"V0  span {2*ENV['V0']['wing']['tip_r_m']:,.0f} m", (2200-600, ENV['V0']['wing']['tip_r_m']+500, 5)),
                      ('span_canon', 'canonical ship 289.5 m (dot)', (4000-200, 400, 5))):
    text(nm, body, loc, SC['COMPARE_SPAN'].collection, size=450, facing='top')

# cutaway: V4 aft assembly with a 120 deg wedge removed toward -Y
CUT = bpy.data.collections.new('VAR_VERTEX_V4_CUTAWAY'); CUT.color_tag = 'COLOR_07'
_, ccolls = gen_collections('V4', CUT)
for k, c in list(ccolls.items()):
    c.name = c.name.replace('VAR_VERTEX_V4_', 'CUT_V4_')
TRASH = bpy.data.collections.new('TRASH_CUT')
build_fdp_parts('V4', R4, ccolls, cut=(200.0, 340.0), breech=TRASH)
for o in [o for c in ccolls.values() for o in c.objects if o.name.split('_', 2)[2].startswith(('Wing_', 'Shadow_Cone', 'Low_Loop', 'Feed_Line', 'KeepOut_Plume', 'TB_'))]:
    bpy.data.objects.remove(o)
build_nozzle('V4', R4, e4, ccolls, cut=(200.0, 340.0), support=TRASH)
build_module('V4', R4, e4, ccolls, cut=(200.0, 340.0), launch=TRASH)
for o in list(TRASH.objects):
    PART_LOG[:] = [r for r in PART_LOG if r[2] != o.name]; bpy.data.objects.remove(o)
bpy.data.collections.remove(TRASH)
build_launcher('B', 'V4', R4, e4, ccolls['07'])
build_coil_protection('V4', R4, e4, {'P1': new_coll('CUT_V4_COIL_P1_UNUSED', CUT), 'P2': new_coll('CUT_V4_COIL_P2_UNUSED', CUT), 'FAN': ccolls['11'],
                                      'SUP': ccolls['08']}, cut=(200.0, 340.0))
for nm_ in ('CUT_V4_COIL_P1_UNUSED', 'CUT_V4_COIL_P2_UNUSED'):
    for o in list(bpy.data.collections[nm_].objects):
        PART_LOG[:] = [r for r in PART_LOG if r[2] != o.name]; bpy.data.objects.remove(o)
    bpy.data.collections.remove(bpy.data.collections[nm_])
build_coil_assembly('R4_NOMINAL', 'V4', e4, ccolls['03'], cut=(200.0, 340.0), detail=False)
build_overlays('V4', R4, e4, ccolls['01'])
link(SC['VERTEX_CUTAWAY'], CUT)

# braking exposure: V4 with skirt A and the dust stream; radiator alternatives: V4 hull + outlines + graded band
link(SC['BRAKING_EXPOSURE'], ASM['V4']); link(SC['BRAKING_EXPOSURE'], DUST)
link(SC['RADIATOR_ALTERNATIVES'], ASM['V4']); link(SC['RADIATOR_ALTERNATIVES'], ALT)
exclude(SC['RADIATOR_ALTERNATIVES'], [DUST.name, PANEL.name])

# ---- Rev 2 comparison scenes (lanes instance the option collections; nothing is copied) ----
O4 = OPT['V4']; P4 = {o['key']: o for o in REV2['launcher']['options']}
LZ = {'REV1': 75.0, 'A': 25.0, 'B': -25.0, 'C': -75.0}
inst(SC['LAUNCHER_COMPARE'], O4['LANE_CORE_LAUNCH'], (0, 0, -125.0), 'LCMP_CORE_B_LONG')
inst(SC['LAUNCHER_COMPARE'], O4['LAUNCH_B'], (0, 0, -125.0), 'LCMP_B_LONG_B')
inst(SC['LAUNCHER_COMPARE'], O4['LAUNCH_B_LONG'], (0, 0, -125.0), 'LCMP_B_LONG')
_bl = REV3['launcher_target']['B_long_to_bow']
text('lcmp_B_LONG', f"B-long (Rev 3 outline): accelerator {_bl['accelerator_m']:.0f} m from the bow, {_bl['accel_g']:,.0f} g; needs the crew trunk out of the spine bore. "
     f"Evidence: IFE targets about 1,000 g (DT ice extrapolation), mockup < 500 g", (-250, 0, -114), SC['LAUNCHER_COMPARE'].collection, size=6.0)
for k, z in LZ.items():
    inst(SC['LAUNCHER_COMPARE'], O4['LANE_CORE_LAUNCH'], (0, 0, z), f'LCMP_CORE_{k}')
    inst(SC['LAUNCHER_COMPARE'], O4[f'LAUNCH_{k}'], (0, 0, z), f'LCMP_{k}')
    o = P4[k]
    body = (f"{o['name']}  |  {o['status']}  |  accelerator {o['accelerator_m']:.0f} m, {o['exit_speed_m_s']/1e3:.2f} km/s, {o['accel_g']:,.0f} g, "
            f"shell {o['shell_stress_MPa']:.1f} MPa (margin {o['stress_margin'][0]:.2f}-{o['stress_margin'][1]:.2f}), {o['targets_in_barrel']:.1f} in barrel, "
            f"{o['electric_W']/1e6:.0f} MWe")
    text(f'lcmp_{k}', body, (-250, 0, z+10), SC['LAUNCHER_COMPARE'].collection, size=6.0)
text('lcmp_title', 'TARGET INJECTION (ISS-009): REV1 vs A axial vs B shielded snout (preferred) vs C offset. Red-violet = open line of sight to the burn, '
     'yellow = protected run behind the chopper', (-250, 0, 130), SC['LAUNCHER_COMPARE'].collection, size=7.0)
text('lcmp_rule', f"rule: any target in line of sight at a pulse instant is destroyed ({REV2['launcher']['xray_per_pulse_J']/1e9:.1f} GJ X-ray per pulse, "
     f"every {1e3*REV2['launcher']['pulse_interval_s']:.2f} ms), so v >= open length x {REV2['launcher']['pulse_Hz']:.0f} Hz", (-250, 0, 120), SC['LAUNCHER_COMPARE'].collection, size=6.0)

# thermal: calculated (Rev 1, canon blades kept) at X 0, preferred graded (canon blades retired) at X +1,000 m
inst(SC['THERMAL_COMPARE'], ASM['V4_CALC'], (0, 0, 0), 'TCMP_CALC')
inst(SC['THERMAL_COMPARE'], ASM['V4'], (1000.0, 0, 0), 'TCMP_PREF')
TH = REV2['thermal']
for nm, x, body in (('tcmp_calc', -180, f"CALCULATED (Rev 1): hot band X -178.8 to 88.0, r 10-{w['hot_band_r_m'][1]:,.0f} m;\ncanon 1,800 K blades kept beside it; "
                                          f"ring A {TH['ring_A_W_m2']['calc']/1e3:.0f} kW/m2"),
                    ('tcmp_pref', 820, f"PREFERRED (graded): hot X {PREF['hot_x_m'][0]:.1f} to {PREF['hot_x_m'][1]:.1f}, r 10-{PREF['hot_r_m'][1]:,.0f} m, "
                                       f"{PREF['hot_area_m2']:,.0f} m2;\ncanon blades retired, area moved into the wing; ring A {PREF['ring_A_W_m2']/1e3:.0f} kW/m2")):
    text(nm, body, (x, -90, 5), SC['THERMAL_COMPARE'].collection, size=20, facing='top')

# coils: P0 Rev 1 (warm screen only, unsized struts), P1 monolithic shoe + sized struts, P2 segmented armour + sized struts (preferred)
for k, x, parts in (('P0', 0.0, ['LANE_CORE_COIL', 'SUP_REV1', 'COIL_XRAY_FAN']), ('P1', 120.0, ['LANE_CORE_COIL', 'COIL_P1', 'COIL_SUP_SIZED', 'COIL_XRAY_FAN']),
                    ('P2', 240.0, ['LANE_CORE_COIL', 'COIL_P2', 'COIL_SUP_SIZED', 'COIL_XRAY_FAN'])):
    inst(SC['COIL_COMPARE'], O4['LANE_CORE_LAUNCH'], (x, 0, 0), f'CCMP_CORE_{k}')
    for pp in parts:
        inst(SC['COIL_COMPARE'], O4[pp], (x, 0, 0), f'CCMP_{k}_{pp}')
CO = REV2['coils']; S1 = CO['struts']['cases']
for k, x, body in (('P0', 0.0, 'P0 Rev 1: warm screen only, struts unsized'),
                   ('P1', 120.0, f"P1 sacrificial shoe {CO['coil_armour_total_kg']/1e3:.0f} t; struts sized for 1.9 GN ({S1[1]['mass_kg']/1e3:.0f} t)"),
                   ('P2', 240.0, f"P2 PREFERRED: 12 replaceable segments/coil on stand-offs + warm screen; same {CO['coil_xray_total_W']/1e9:.1f} GW intercepted")):
    text(f'ccmp_{k}', body, (x-225, 0, 58), SC['COIL_COMPARE'].collection, size=2.6)
text('ccmp_rule', f"X-ray onto C1+C2 is fixed by their solid angle, the same in every option and unbooked: 11.9 GW on T03 geometry (T00), "
     f"{CO['coil_xray_total_W']/1e9:.1f} GW upper case as drawn (C2 envelope); hoop 3-7 GN and 855-1,281 t coil structure unbooked (T03)", (-225, 0, 66), SC['COIL_COMPARE'].collection, size=3.4)

# Rev 4 coil assembly sections: each build cut open (near half removed) so the layers read in section; lanes 40 m apart in X
CASEC = bpy.data.collections.new('VAR_VERTEX_V4_COIL_SECTIONS'); CASEC.color_tag = 'COLOR_04'
CAS_LANES = [('REV3_COPIED', 0.0), ('T03_3X_WINDING', 40.0), ('R4_COMPACT', 80.0), ('R4_NOMINAL', 120.0), ('R4_STEEL_CASE', 160.0), ('R4_T00_SHADOWED', 200.0)]
for k, dx in CAS_LANES:
    lc = new_coll(f'CASEC_{k}', CASEC, 'COLOR_04')
    kk = 'REV2_COPIED_C1' if k == 'REV3_COPIED' else k
    build_coil_assembly(kk, 'V4', e4, lc, cut=(96.0, 444.0), detail=False, opaque=True)          # keeps a 12 deg wedge at az 84-96
    for o in lc.objects:
        o.location.x += dx
    b1 = CA4['coils']['C1']['builds'][kk]; b2 = CA4['coils']['C2']['builds'][kk]
    tot = CA4['cases'][kk]['total_W']
    body = (f"{k}{'  PREFERRED (T00)' if k == 'R4_T00_SHADOWED' else ''}\nC1 h {b1['projected_half_width_m']:.2f} m {b1['xray_W']/1e9:.1f} GW\n"
            f"C2 h {b2['projected_half_width_m']:.2f} m {b2['xray_W']/1e9:.1f} GW\ntotal {tot/1e9:.1f} GW")
    text(f'casec_{k}', body, (e4['closure_coils'][0]['x_m']+dx-14, 0, 52), SC['COIL_ASSEMBLY_SECTION'].collection, size=2.2)
link(SC['COIL_ASSEMBLY_SECTION'], CASEC)
_c1 = CA4['coils']['C1']; _c2 = CA4['coils']['C2']
text('casec_title', "CLOSURE-COIL ASSEMBLIES IN SECTION (ISS-014, rev4.json): winding, case, 80 K shield, cryostat, warm screen,\n"
     "stand-off gap, Li back plate + armour face. The outermost layer sets the X-ray share.", (-205, 0, 64), SC['COIL_ASSEMBLY_SECTION'].collection, size=2.4)
text('casec_note', f"C1 hoop {_c1['hoop_tension_N']/1e9:.1f} GN: case {_c1['case_mass_kg_T03_virial']/1e3:,.0f} t on T03's virial basis, "
     f"{_c1['case_mass_kg_steel']/1e3:,.0f} t if steel; C2 hoop {_c2['hoop_tension_N']/1e9:.2f} GN. Upper section: C2 at r 41.6 m; lower: C1 at r 22.1 m (burn to the left, X -249)",
     (-205, 0, 58), SC['COIL_ASSEMBLY_SECTION'].collection, size=2.0)

# ---- Rev 4 launcher lanes: B (Rev 3) and B-long NOT DEFENSIBLE, B-modified CANDIDATE, B-ray CONCEPTUAL, axis plug REJECTED ----
_LV = LR4['verdicts']; _vk = lambda pre: next((v for k_, v in _LV.items() if k_.startswith(pre)), '?')
_BR = LR4['B_ray']; _BM = LR4['B_modified']
for k, z, parts, body in (
        ('B', 280.0, ['LAUNCH_B'], f"B (Rev 3): {P4['B']['accelerator_m']:.0f} m in the spine bore, {P4['B']['accel_g']:,.0f} g, layered D/3He target  |  T00: {_vk('B (T05')}"),
        ('B_LONG', 190.0, ['LAUNCH_B', 'LAUNCH_B_LONG'], f"B-long: accelerator from the bow  |  T00: {_vk('B-long')}"),
        ('B_MOD', 100.0, ['LAUNCH_B', 'LAUNCH_BMOD'], f"B-MODIFIED (Rev 4 preferred layout candidate): B kinematics, contactless coilgun, 30 K gas-filled HDC capsule ({LR4['target']['limit_g']:,.0f} g limit), "
                                                      f"sabot catcher {_BM['sabot_catcher_W']/1e6:.0f} MW, {_BM['electric_W']/1e6:.0f} MWe  |  T00: {_vk('B-modified')}\n"
                                                      "snout tip and chopper rim sit in the unstopped axis plasma channel: OPEN BLOCKER"),
        ('B_RAY', 10.0, ['LAUNCH_BRAY'], f"B-RAY (T05 concept): {_BR['accelerator_m']:.0f} m on a burn ray (polar {_BR['polar_deg']:.0f}, az {_BR['az_deg']:.0f}), tip {_BR['tip_from_burn_m']:.1f} m, {_BR['accel_g']:,.0f} g, "
                                          f"{_BR['tip_MW_m2']:.1f} MW/m2 at the tip  |  T00: KINEMATICS PLAUSIBLE; armature/sabot at 30,000 g NOT DEMONSTRATED; breech support UNSIZED"),
        ('AXIS_PLUG', -80.0, ['LAUNCH_B', 'AXIS_PLUG_REJECTED'], "AXIS_PLUG_LI (T05 concept): Li droplet sheet on the axis at 35 m  |  T00: NOT PLAUSIBLE (REJECTED): droplets vaporise, 6-880 Mt Li per mission")):
    inst(SC['LAUNCHER_R4_COMPARE'], O4['LANE_CORE_LAUNCH'], (0, 0, z), f'LR4_CORE_{k}')
    inst(SC['LAUNCHER_R4_COMPARE'], O4['AXIS_KEEPOUT'], (0, 0, z), f'LR4_KEEPOUT_{k}')
    for pp in parts:
        inst(SC['LAUNCHER_R4_COMPARE'], O4[pp], (0, 0, z), f'LR4_{k}_{pp}')
    text(f'lr4_{k}', body, (-260, 0, z+14), SC['LAUNCHER_R4_COMPARE'].collection, size=5.0)
text('lr4_title', "TARGET INJECTION, REVISION 4 (T00 verdicts). Red cone = unstopped axis plasma KEEP-OUT (113 GW, 473 J/cm2 per pulse on the shield face). "
     "Red-violet = open flight; yellow marker = capsule PLACEHOLDER", (-260, 0, 330), SC['LAUNCHER_R4_COMPARE'].collection, size=6.5)

# ---- Rev 3 vs Rev 4: the two chosen V4 assemblies one above the other (true scale, same X) ----
inst(SC['REV3_VS_REV4'], ASM['V4_REV3'], (0, 0, 60.0), 'R34_REV3')
inst(SC['REV3_VS_REV4'], ASM['V4'], (0, 0, -180.0), 'R34_REV4')
inst(SC['REV3_VS_REV4'], O4['GHOST_COUPLED'], (0, 0, -180.0), 'R34_REV4_GHOST')
text('r34_rev3', "REV 3 CHOSEN: C1/C2 P2 armour envelopes + Rev 2 torus dust bumpers (ray cast: 70.5 GW intercepted), reaction ring in the beam, S5 as drawn (f1 0.077 Hz, not 0.2), launcher B",
     (-300, 0, 112), SC['REV3_VS_REV4'].collection, size=6.0)
text('r34_rev4', "REV 4 CHOSEN: T00 shadowed C1/C2 (6.1 GW incl. struts) + Li loop in the strut shadows, edge-on cone dust guards, reaction ring in the shield shadow, "
     "S5N 9 nested longerons (2.06 kt, f1 0.2 Hz beam model), B + B-modified overlay, axis KEEP-OUT; ghost = COUPLED APPROXIMATION 68.5 kt / 43.3 kt propellant",
     (-300, 0, -128), SC['REV3_VS_REV4'].collection, size=6.0)

# skirts: A full (3 penetrations), B2 dock-clear (preferred), B short, C none; same ship core in each lane
SKCORE = bpy.data.collections.new('LANE_CORE_SKIRT')
for c in ([ships['V4']] if 'V4' in ships else [])+[VAR['V4'], O4['SPINE_EXT'], O4['DOCK_ROUTES']]:
    SKCORE.children.link(c)
DU = REV2['dust']['options']
for k, z in (('A_FULL', 150.0), ('B2_DOCK_CLEAR', 50.0), ('B_SHORT', -50.0), ('C_BUMPERS_ONLY', -150.0)):
    inst(SC['SKIRT_COMPARE'], SKCORE, (0, 0, z), f'SCMP_CORE_{k}')
    inst(SC['SKIRT_COMPARE'], COLL['V4']['skirts'][k], (0, 0, z), f'SCMP_{k}')
    d = DU[k]
    body = (f"{k}: shadow r {d['shadow_r_m']:.1f} m, {d['mass_t'][0]:.0f}-{d['mass_t'][1]:.0f} t, dock/EVA penetrations {d['penetrations']}, "
            f"exposed while braking {sum(d['exposed_annuli_m2'].values()):,.0f} m2" + (' (ring A, farm, fwd-shield back)' if k == 'C_BUMPERS_ONLY' else ''))
    text(f'scmp_{k}', body, (-170, 0, z+38), SC['SKIRT_COMPARE'].collection, size=6)
text('scmp_title', 'DUST PROTECTION WHILE BRAKING (dust arrives along -X; shadow = cylinder of the skirt edge radius). Docking corridors and EVA route drawn',
     (-170, 0, 205), SC['SKIRT_COMPARE'].collection, size=7)

# ---- Rev 3 structure lanes: side view (lanes in Z) and end view (lanes in Y); tanks as ghosts ----
SLANES = [('S1', ['STRUCT_S1']), ('S2', ['STRUCT_S2', 'CORR_K2']), ('S3', ['STRUCT_S3']), ('S4', ['STRUCT_S4']), ('S5', ['STRUCT_S2', 'STRUCT_S3', 'CORR_K2']),
          ('S5N', ['STRUCT_S5N', 'CORR_K2', 'ACCESS_R4'])]
for i, (k, parts) in enumerate(SLANES):
    z = 200.0-100.0*i; y = -240.0+120.0*i
    for sc_, loc in (('STRUCTURE_COMPARE', (0, 0, z)), ('STRUCTURE_SECTION', (0, y, 0))):
        inst(SC[sc_], O4['LANE_CORE_TB'], loc, f'{sc_[:5]}_CORE_{k}')
        for pp in parts:
            inst(SC[sc_], O4[pp], loc, f'{sc_[:5]}_{k}_{pp}')
    if k == 'S5N':
        c_ = ST4['cases']['S5_N9_T00']
        body = (f"S5N REV 4 PREFERRED (T00 sizing): S2 + {c_['members']} longerons r {c_['tube_r_m']:.2f} m nested in the inter-tank gaps at r {c_['longeron_r_m']:.0f} m; "
                f"{c_['structure_kg']/1e3:,.2f} kt for f1 {c_['f1_full_Hz']:.2f} Hz (beam model, no FE); gap-plane lacing; saddles 10-30 Hz; {c_['B2_shadow_margin_m']:.1f} m inside B2; tanks exit radially")
    else:
        key = {'S1': 'S1_SPINE_ONLY', 'S2': 'S2_CANON_SECTORS', 'S3': 'S3_OUTER_CAGE', 'S4': 'S4_SECTORS_PLUS_BELT', 'S5': 'S5_SECTORS_PLUS_OUTER_STIFFENERS'}[k]
        o = SO3[key]
        body = (f"{key}: {o['structure_kg']/1e3:,.0f} t (strength), {o['structure_stiff_kg']/1e3:,.0f} t for f1 >= {REV3['f_target_Hz']} Hz; "
                f"f1 {o['f_bending_Hz']['full']:.3f} Hz full / {o['f_bending_Hz']['dry']:.3f} dry; axial {o['f_axial_Hz']['full']:.2f} Hz; {o['canon_rule'].split(' (')[0]}")
        if k == 'S5':
            c3 = ST4['cases']['S5_REV3_AS_DRAWN']; cc = ST4['cases']['S5_REV3_CORRECTED']
            body = (f"S5 REV 3 (stiffness area undercounted 6x): as drawn f1 {c3['f1_full_Hz']:.3f} Hz, not 0.2; corrected {cc['structure_kg']/1e3:,.2f} kt, "
                    f"longerons r {cc['tube_r_m']:.2f} m, {cc['min_tank_clearance_m']:.2f} m to the tanks, {cc['B2_shadow_margin_m']:.2f} m inside B2")
    text(f'scmp3_{k}', body, (100, 0, z+40), SC['STRUCTURE_COMPARE'].collection, size=7)
    text(f'ssec3_{k}', k, (60, y, 48), SC['STRUCTURE_SECTION'].collection, size=12, facing='end')
text('scmp3_title', f"T-B STRETCH STRUCTURE (ISS-013): X {ST3['x_m'][0]:.2f}-{ST3['x_m'][1]:.2f} m, {ST3['propellant_kg']/1e6:,.1f} kt propellant + "
     f"{ST3['tank_kg']/1e6:.1f} kt tanks + bow {ST3['bow_kg_PROTOTYPE']/1e3:.0f} t; root axial {REV3['loads']['root_axial_design_N']/1e6:.2f} MN design, slosh "
     f"{REV3['dynamics']['slosh_Hz']['outer'][0]:.3f}-{REV3['dynamics']['slosh_Hz']['inner'][1]:.3f} Hz, ring spin 0.067 Hz", (100, 0, 262), SC['STRUCTURE_COMPARE'].collection, size=8)

# human scale: a 1.75 m figure at the shield-face rail and one at a wing-root crossing (instances of canon figures if present)
HUM = bpy.data.collections.new('VAR_VERTEX_V4_HUMAN_SCALE')
fig = None
if False:  # canon HUMAN_ collections sit at ship positions; a T05 1.75 m capsule is placed instead
    for c in ships['CANON'].children_recursive:
        if c.name.split('.')[0].startswith('HUMAN_'):
            fig = c; break
spots = [((R4['layout']['x_shield_fwd']+1.5, 0, R4['shield']['radius_hw_fwd_m']+0.6+0.9), 'shield-face exchange rail'),
         ((w['x_m'][0]+(w['x_m'][1]-w['x_m'][0])/2, 8.0, 0.9), 'wing-root crossing')]
for i, (loc, why) in enumerate(spots):
    if fig is not None:
        o = bpy.data.objects.new(f'V4_PR_Human_{i}', None); o.instance_type = 'COLLECTION'; o.instance_collection = fig; o.location = loc
        HUM.objects.link(o); tag(o, 'V4', 'PROTOTYPE', 'VTX-NONE', f'canon {fig.name}', note=why)
    else:
        make(f'Human_{i}', 'capsule', HUM, 'SERVICE', 'V4', 'PROTOTYPE', 'VTX-NONE', 'T05 scale figure 1.75 m', note=why,
             x0=loc[0]-0.15, x1=loc[0]+0.15, centre=(loc[1], loc[2]), radius=0.25)
link(SC['VERTEX_V4'], HUM)

# ----------------------------------------------------------------------------------------------------------------------------------
# look, cameras
# ----------------------------------------------------------------------------------------------------------------------------------
sun = bpy.data.lights.new('Review_Sun', 'SUN'); sun.energy = 3.0
so = bpy.data.objects.new('Review_Sun', sun); so.rotation_euler = (-Vector((-.55, .62, .55)).normalized()).to_track_quat('-Z', 'Y').to_euler()
world = bpy.data.worlds.new('VTX_Space'); world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND'); bg.inputs['Color'].default_value = (.012, .014, .02, 1)
for sc in SC.values():
    sc.world = world; sc.collection.objects.link(so)
    sc.render.engine = 'BLENDER_WORKBENCH'; shd = sc.display.shading
    shd.light = 'STUDIO'; shd.color_type = 'MATERIAL'; shd.show_cavity = True; shd.show_object_outline = True; shd.background_type = 'WORLD'
    sc.view_settings.view_transform = 'Standard'; sc.render.resolution_x, sc.render.resolution_y = a.size
    sc.unit_settings.system = 'METRIC'


def camera(name, loc, look, lens=35.0, ortho=None, up='Z', clip=80000.0, top=False):
    cam = bpy.data.cameras.new(name); ob = bpy.data.objects.new(name, cam)
    ob.location = loc; d = Vector(look)-Vector(loc)
    if top:
        ob.rotation_euler = (0, 0, 0)
    else:
        ob.rotation_euler = d.to_track_quat('-Z', up).to_euler()
    cam.lens = lens; cam.clip_start = 0.5; cam.clip_end = clip
    if ortho:
        cam.type = 'ORTHO'; cam.ortho_scale = ortho
    return ob


x4a, x4b = e4['extent_x_m']; xm = (x4a+x4b)/2
xB = e4['x_burn_m']; xSA = e4['x_shield_aft_m']; tip = w['tip_r_m']
CAMS = {
    'CAM_VTX_01_SIDE_COMPARE': (camera('CAM_VTX_01_SIDE_COMPARE', (37, -6000, -330), (37, 0, -330), ortho=1700), ['COMPARE_SIDE_BY_SIDE']),
    'CAM_VTX_02_TOP_COMPARE': (camera('CAM_VTX_02_TOP_COMPARE', (37, -330, 6000), (37, -330, 0), ortho=1700, top=True), ['COMPARE_TOP']),
    'CAM_VTX_03_THREEQ_COMPARE': (camera('CAM_VTX_03_THREEQ_COMPARE', (-1000, -1500, 300), (40, 0, -330), lens=35), ['COMPARE_SIDE_BY_SIDE']),
    'CAM_VTX_04_SPAN_FULL': (camera('CAM_VTX_04_SPAN_FULL', (1500, 0, 30000), (1500, 0, 0), ortho=24000, top=True), ['COMPARE_SPAN']),
    'CAM_VTX_05_SPAN_ROOT': (camera('CAM_VTX_05_SPAN_ROOT', (-40, 700, 9000), (-40, 700, 0), ortho=2500, top=True), ['VERTEX_V4']),
    'CAM_VTX_06_AFT_ASSEMBLY': (camera('CAM_VTX_06_AFT_ASSEMBLY', (xB-230, -250, 140), (xB+30, 0, 10), lens=30), ['VERTEX_V4']),
    'CAM_VTX_07_CUTAWAY': (camera('CAM_VTX_07_CUTAWAY', (xB+10, -260, 60), (xB+40, 0, 0), lens=30), ['VERTEX_CUTAWAY']),
    'CAM_VTX_07b_MODULE_CUTAWAY': (camera('CAM_VTX_07b_MODULE_CUTAWAY', (xSA+14, -26, 9), (xSA+16, 0, 0), lens=24), ['VERTEX_CUTAWAY']),
    'CAM_VTX_08_BRAKING_EXPOSURE': (camera('CAM_VTX_08_BRAKING_EXPOSURE', (x4a-900, -520, 300), (-150, 0, 0), lens=30), ['BRAKING_EXPOSURE']),
    'CAM_VTX_09_RADIATOR_ALTS_END': (camera('CAM_VTX_09_RADIATOR_ALTS_END', (-40000, 0, 0), (0, 0, 0), ortho=31000, up='Z', clip=120000), ['RADIATOR_ALTERNATIVES']),
    'CAM_VTX_09b_RADIATOR_ALTS_TOP': (camera('CAM_VTX_09b_RADIATOR_ALTS_TOP', (0, 0, 30000), (0, 0, 0), ortho=31000, top=True), ['RADIATOR_ALTERNATIVES']),
    'CAM_VTX_10_RADIATOR_STATES': (camera('CAM_VTX_10_RADIATOR_STATES', (-260, 420, 260), (-40, 950, 0), lens=30), ['VERTEX_V4']),
    'CAM_VTX_11_MAINTENANCE': (camera('CAM_VTX_11_MAINTENANCE', (R4['layout']['x_shield_fwd']+14, -12, 12), (R4['layout']['x_shield_fwd']+1, 0, 7.5), lens=28), ['VERTEX_V4']),
    'CAM_VTX_12_DOCK_HAB_CLEARANCE': (camera('CAM_VTX_12_DOCK_HAB_CLEARANCE', (60, -170, 95), (112, 0, 0), lens=30), ['VERTEX_V4']),
    'CAM_VTX_13_RING_HOTBAND': (camera('CAM_VTX_13_RING_HOTBAND', (40, 30, 600), (40, 30, 0), ortho=200, top=True), ['VERTEX_V4']),
    'CAM_VTX_14_C1_WING': (camera('CAM_VTX_14_C1_WING', (-150, 60, 40), (-188, 22, 0), lens=30), ['VERTEX_V4']),
    'CAM_VTX_15_V0_WHOLE': (camera('CAM_VTX_15_V0_WHOLE', (-900, -2600, 1600), (-20, 0, 0), lens=35), ['VERTEX_V0']),
    'CAM_VTX_16_CANON': (camera('CAM_VTX_16_CANON', (-260, -420, 200), (0, 0, 0), lens=35), ['CANON_WAYFARER']),
    'CAM_VTX_17_V4_WHOLE': (camera('CAM_VTX_17_V4_WHOLE', (-9000, -16000, 8000), (0, 0, 0), lens=35, clip=120000), ['VERTEX_V4']),
    # Rev 2
    'CAM_VTX_20_LAUNCHER_COMPARE': (camera('CAM_VTX_20_LAUNCHER_COMPARE', (80, -3000, -10), (80, 0, -10), ortho=680), ['LAUNCHER_COMPARE']),
    'CAM_VTX_21_SNOUT_CUTAWAY': (camera('CAM_VTX_21_SNOUT_CUTAWAY', (xSA-55, -75, 28), (xSA-15, 0, 0), lens=28), ['VERTEX_CUTAWAY']),
    'CAM_VTX_22_BREECH_DETAIL': (camera('CAM_VTX_22_BREECH_DETAIL', (80, -3000, -25), (80, 0, -25), ortho=44), ['LAUNCHER_COMPARE']),
    'CAM_VTX_23_THERMAL_TOP': (camera('CAM_VTX_23_THERMAL_TOP', (480, 560, 9000), (480, 560, 0), ortho=2500, top=True), ['THERMAL_COMPARE']),
    'CAM_VTX_24_RING_CALC': (camera('CAM_VTX_24_RING_CALC', (40, 30, 3000), (40, 30, 0), ortho=200, top=True), ['THERMAL_COMPARE']),
    'CAM_VTX_25_RING_GRADED': (camera('CAM_VTX_25_RING_GRADED', (1040, 30, 3000), (1040, 30, 0), ortho=200, top=True), ['THERMAL_COMPARE']),
    'CAM_VTX_26_COIL_COMPARE': (camera('CAM_VTX_26_COIL_COMPARE', (-40, -3000, 8), (-40, 0, 8), ortho=380), ['COIL_COMPARE']),
    'CAM_VTX_27_COIL_THREEQ': (camera('CAM_VTX_27_COIL_THREEQ', (-140, -95, 55), (-190, 0, 0), lens=30), ['VERTEX_V4']),
    'CAM_VTX_28_SKIRT_COMPARE': (camera('CAM_VTX_28_SKIRT_COMPARE', (175, -4000, 25), (175, 0, 25), ortho=760), ['SKIRT_COMPARE']),
    'CAM_VTX_29_DOCK_SKIRT': (camera('CAM_VTX_29_DOCK_SKIRT', (118, -170, -25), (122, 0, 0), lens=30), ['VERTEX_V4']),
    'CAM_VTX_30_V4_SIDE_TRUE_SCALE': (camera('CAM_VTX_30_V4_SIDE_TRUE_SCALE', (37, -6000, 0), (37, 0, 0), ortho=830), ['VERTEX_V4']),
    'CAM_VTX_31_SPINE_STRETCH': (camera('CAM_VTX_31_SPINE_STRETCH', (270, -3000, 0), (270, 0, 0), ortho=360), ['VERTEX_V4']),
    # Rev 3
    'CAM_VTX_32_STRUCTURE_COMPARE': (camera('CAM_VTX_32_STRUCTURE_COMPARE', (330, -4000, -30), (330, 0, -30), ortho=1080), ['STRUCTURE_COMPARE']),
    'CAM_VTX_33_STRUCTURE_SECTION': (camera('CAM_VTX_33_STRUCTURE_SECTION', (-900, 60, 0), (0, 60, 0), ortho=780, up='Z'), ['STRUCTURE_SECTION']),
    'CAM_VTX_34_ROOT_JOINT_CORRIDOR': (camera('CAM_VTX_34_ROOT_JOINT_CORRIDOR', (152, -13, 7), (136, 2, 1), lens=22), ['VERTEX_V4']),
    'CAM_VTX_35_BOW_JOINT': (camera('CAM_VTX_35_BOW_JOINT', (385, -70, 40), (414, 0, 0), lens=28), ['VERTEX_V4']),
    'CAM_VTX_36_COIL_COOLING': (camera('CAM_VTX_36_COIL_COOLING', (-150, -110, 75), (-185, 0, 0), lens=30), ['VERTEX_V4']),
    'CAM_VTX_37_COIL_SECTIONS': (camera('CAM_VTX_37_COIL_SECTIONS', (-78, -3000, 38), (-78, 0, 38), ortho=262), ['COIL_ASSEMBLY_SECTION']),
    'CAM_VTX_38c_C1_T00_CLOSE': (camera('CAM_VTX_38c_C1_T00_CLOSE', (11.7, -3000, 22.1), (11.7, 0, 22.1), ortho=7), ['COIL_ASSEMBLY_SECTION']),
    'CAM_VTX_42_LAUNCHER_R4': (camera('CAM_VTX_42_LAUNCHER_R4', (80, -3000, 115), (80, 0, 115), ortho=800), ['LAUNCHER_R4_COMPARE']),
    'CAM_VTX_43_SNOUT_KEEPOUT': (camera('CAM_VTX_43_SNOUT_KEEPOUT', (-215, -3000, 10), (-215, 0, 10), ortho=110), ['LAUNCHER_R4_COMPARE']),
    'CAM_VTX_44_REV3_VS_REV4': (camera('CAM_VTX_44_REV3_VS_REV4', (80, -4000, -60), (80, 0, -60), ortho=900), ['REV3_VS_REV4']),
    'CAM_VTX_45_REV3_VS_REV4_AFT': (camera('CAM_VTX_45_REV3_VS_REV4_AFT', (-180, -4000, -60), (-180, 0, -60), ortho=260), ['REV3_VS_REV4']),
    'CAM_VTX_46_BRAY_THREEQ': (camera('CAM_VTX_46_BRAY_THREEQ', (-330, 260, 230), (-110, 25, 25), lens=30), ['VERTEX_V4']),
    'CAM_VTX_38_C1_SECTION_CLOSE': (camera('CAM_VTX_38_C1_SECTION_CLOSE', (-68.3, -3000, 22.1), (-68.3, 0, 22.1), ortho=10), ['COIL_ASSEMBLY_SECTION']),
    'CAM_VTX_38b_C2_SECTION_CLOSE': (camera('CAM_VTX_38b_C2_SECTION_CLOSE', (-79.6, -3000, 41.6), (-79.6, 0, 41.6), ortho=3.2), ['COIL_ASSEMBLY_SECTION']),
    'CAM_VTX_39_COIL_PLANT': (camera('CAM_VTX_39_COIL_PLANT', (-150, -62, 38), (-187, 0, 12), lens=28), ['VERTEX_V4']),
    'CAM_VTX_40_S5N_END': (camera('CAM_VTX_40_S5N_END', (-900, 360, 0), (0, 360, 0), ortho=84, up='Z'), ['STRUCTURE_SECTION']),
    'CAM_VTX_41_S5N_THREEQ': (camera('CAM_VTX_41_S5N_THREEQ', (95, -120, 75), (230, 0, 0), lens=30), ['VERTEX_V4']),
}
CAMS['CAM_VTX_09_RADIATOR_ALTS_END'][0].rotation_euler = (math.radians(90), 0, math.radians(-90))
CAMS['CAM_VTX_33_STRUCTURE_SECTION'][0].rotation_euler = (math.radians(90), 0, math.radians(-90))
CAMS['CAM_VTX_40_S5N_END'][0].rotation_euler = (math.radians(90), 0, math.radians(-90))
for name, (ob, names) in CAMS.items():
    ob['render_scenes'] = [n for n in names if n in bpy.data.scenes]
    for n in ob['render_scenes']:
        bpy.data.scenes[n].collection.objects.link(ob)
DEFAULT = {'COMPARE_SIDE_BY_SIDE': 'CAM_VTX_01_SIDE_COMPARE', 'COMPARE_TOP': 'CAM_VTX_02_TOP_COMPARE', 'COMPARE_SPAN': 'CAM_VTX_04_SPAN_FULL',
           'VERTEX_V4': 'CAM_VTX_06_AFT_ASSEMBLY', 'VERTEX_CUTAWAY': 'CAM_VTX_07_CUTAWAY', 'BRAKING_EXPOSURE': 'CAM_VTX_08_BRAKING_EXPOSURE',
           'RADIATOR_ALTERNATIVES': 'CAM_VTX_09_RADIATOR_ALTS_END', 'VERTEX_V0': 'CAM_VTX_15_V0_WHOLE', 'CANON_WAYFARER': 'CAM_VTX_16_CANON',
           'LAUNCHER_COMPARE': 'CAM_VTX_20_LAUNCHER_COMPARE', 'THERMAL_COMPARE': 'CAM_VTX_23_THERMAL_TOP', 'COIL_COMPARE': 'CAM_VTX_26_COIL_COMPARE', 'COIL_ASSEMBLY_SECTION': 'CAM_VTX_37_COIL_SECTIONS',
           'SKIRT_COMPARE': 'CAM_VTX_28_SKIRT_COMPARE', 'STRUCTURE_COMPARE': 'CAM_VTX_32_STRUCTURE_COMPARE', 'STRUCTURE_SECTION': 'CAM_VTX_33_STRUCTURE_SECTION',
           'LAUNCHER_R4_COMPARE': 'CAM_VTX_42_LAUNCHER_R4', 'REV3_VS_REV4': 'CAM_VTX_44_REV3_VS_REV4'}
for sc, cam in DEFAULT.items():
    SC[sc].camera = CAMS[cam][0]

# hide the wings for the top compare camera (they cover the other lanes); render-time per camera hiding
WING = ('_Wing_', 'TIP_', 'ALT_')
PLUME = ('_Shadow_Cone', '_KeepOut', '_Exhaust_', 'Dust_Streak', 'StandOff_dense')
RENDER_HIDE = {'CAM_VTX_02_TOP_COMPARE': WING+PLUME, 'CAM_VTX_01_SIDE_COMPARE': PLUME, 'CAM_VTX_03_THREEQ_COMPARE': PLUME,
               'CAM_VTX_06_AFT_ASSEMBLY': PLUME, 'CAM_VTX_10_RADIATOR_STATES': PLUME, 'CAM_VTX_12_DOCK_HAB_CLEARANCE': PLUME,
               'CAM_VTX_13_RING_HOTBAND': PLUME, 'CAM_VTX_14_C1_WING': PLUME, 'CAM_VTX_15_V0_WHOLE': PLUME, 'CAM_VTX_17_V4_WHOLE': PLUME,
               'CAM_VTX_11_MAINTENANCE': PLUME+('_LBL_',),
               'CAM_VTX_27_COIL_THREEQ': PLUME, 'CAM_VTX_28_SKIRT_COMPARE': PLUME, 'CAM_VTX_29_DOCK_SKIRT': PLUME, 'CAM_VTX_30_V4_SIDE_TRUE_SCALE': PLUME,
               'CAM_VTX_31_SPINE_STRETCH': PLUME+('_PP_TB_', '_LBL_'), 'CAM_VTX_21_SNOUT_CUTAWAY': PLUME+('_LBL_', '_XRAY_Fan', 'StandOff'), 'CAM_VTX_23_THERMAL_TOP': PLUME, 'CAM_VTX_24_RING_CALC': PLUME,
               'CAM_VTX_25_RING_GRADED': PLUME,
               'CAM_VTX_34_ROOT_JOINT_CORRIDOR': PLUME+('_PP_TB_', '_LBL_'), 'CAM_VTX_35_BOW_JOINT': PLUME+('_PP_TB_', '_LBL_'), 'CAM_VTX_36_COIL_COOLING': PLUME+('_LBL_',), 'CAM_VTX_39_COIL_PLANT': PLUME+('_LBL_', '_XRAY_Fan', 'StandOff', 'Wing_'), 'CAM_VTX_41_S5N_THREEQ': PLUME+('_PP_TB_', '_LBL_'), 'CAM_VTX_44_REV3_VS_REV4': PLUME, 'CAM_VTX_45_REV3_VS_REV4_AFT': PLUME, 'CAM_VTX_46_BRAY_THREEQ': PLUME, 'CAM_VTX_07b_MODULE_CUTAWAY': ('_LBL_',), 'CAM_VTX_08_BRAKING_EXPOSURE': ('_Exhaust_', '_KeepOut_Plume')}

# ----------------------------------------------------------------------------------------------------------------------------------
# checks, texts
# ----------------------------------------------------------------------------------------------------------------------------------
if 'CANON' in ships:
    after = fingerprint(ships['CANON'])
    CHECKS['canon_unchanged'] = {'objects': len(after), 'identical_to_append': after == fps['before']}
    src_ship = bpy.data.collections.get('CANON_WAYFARER_SHIP_main')
# ----------------------------------------------------------------------------------------------------------------------------------
# Rev 4 geometry check for T00: X-ray interception shares from the burn point, ray-cast on the drawn V4 hardware (first hit per ray)
# ----------------------------------------------------------------------------------------------------------------------------------
def raycast_shares(n_rays, asm, kernel=None):
    from mathutils.bvhtree import BVHTree
    from mathutils import Vector
    xB = e4['x_burn_m']; origin = Vector((xB, 0.0, 0.0))
    obs = [o for o in asm.all_objects if o.type == 'MESH' and o.get('wf_owner') == 'wayfarer.t05' and o.get('representation') == 'HARDWARE'
           and o.get('generation') == 'V4' and not o.hide_render and not str(o.get('function', '')).upper().startswith('VIS')
           and o.get('evidence_status') != 'CONCEPTUAL_ILLUSTRATION'
           and not any(k in o.name for k in PLUME+('Ignition', 'Pellet_In_Flight', 'Target_Flight', '_Path', 'Line_Of_Sight', 'Axis'))]
    def contains_burn(o):
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        return all(min(v[i] for v in bb) <= (xB, 0.0, 0.0)[i] <= max(v[i] for v in bb) for i in range(3)) and \
            max(v[0] for v in bb)-min(v[0] for v in bb) < 400.0 and o.name.split('_', 2)[2].startswith(('Exhaust', 'Burn', 'Plasma'))
    obs = [o for o in obs if not contains_burn(o)]
    verts, polys, owner = [], [], []
    for o in obs:
        mw = o.matrix_world; base = len(verts)
        verts.extend(mw @ v.co for v in o.data.vertices)
        for p in o.data.polygons:
            polys.append([base+i for i in p.vertices]); owner.append(o.name)
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False)

    def cat(nm):
        n = nm.split('_', 2)[2]
        for key, pats in (('C1_armour_face', ('C1_R4_NOMINAL_Armour_Face', 'C1_R4_T00_SHADOWED_CFC_Armour')), ('C1_armour_backplate', ('C1_R4_NOMINAL_Armour_Backplate', 'C1_R4_T00_SHADOWED_Li_Channel')),
                          ('C1_behind_armour', ('C1_R4_NOMINAL_', 'C1_R4_T00_SHADOWED_')), ('C2_armour_face', ('C2_R4_NOMINAL_Armour_Face', 'C2_R4_T00_SHADOWED_CFC_Armour')),
                          ('C2_armour_backplate', ('C2_R4_NOMINAL_Armour_Backplate', 'C2_R4_T00_SHADOWED_Li_Channel')), ('C2_behind_armour', ('C2_R4_NOMINAL_', 'C2_R4_T00_SHADOWED_')),
                          ('closure_winding_drawn_by_nozzle', ('Closure_C',)), ('coil_struts_and_ties', ('C1_Sized_Strut', 'C1_Sized_Reaction', 'C1_Strut', 'C2_Tie', 'C1_R4_Strut', 'C1_R4_Reaction', 'C2_R4_Tie')),
                          ('coil_coolant_lines', ('Plant_',)), ('loop_bumpers_rev2', ('Loop_1_Local', 'Loop_2_Local', 'Loop_3_Local')),
                          ('loop_guard_rings_rev2', ('Loop_2_Guard', 'Loop_3_Guard')), ('loop_dust_guards_r4', ('Loop_1_R4', 'Loop_2_R4', 'Loop_3_R4')),
                          ('nozzle_loops', ('Loop_',)), ('nozzle_struts', ('Strut', 'Truss')),
                          ('shield', ('Shield',)), ('launcher', ('LB_', 'LA_', 'LC_', 'Launcher', 'Snout', 'Pellet', 'Injector')),
                          ('wing', ('Wing', 'Hot_', 'Rad')), ):
            if n.startswith(pats) or any(p in n for p in pats if key in ('nozzle_struts', 'launcher', 'wing')):
                return key
        return 'other:'+n.split('_')[0]
    hits = {}; per_obj = {}
    ga = math.pi*(3.0-math.sqrt(5.0)); kept = 0
    for i in range(n_rays):
        zc = 1.0-2.0*(i+0.5)/n_rays                       # cos(polar) about +X, Fibonacci sphere
        if zc < -0.6:                                      # nothing beyond polar 127 deg (L3 at 120 deg is inside)
            continue
        kept += 1
        rr = math.sqrt(1.0-zc*zc); t = ga*i
        d = Vector((zc, rr*math.cos(t), rr*math.sin(t)))
        loc, nrm, idx, dist = bvh.ray_cast(origin, d, 5000.0)
        if idx is None:
            continue
        o = owner[idx]; k = cat(o); hits[k] = hits.get(k, 0)+1; per_obj[o] = per_obj.get(o, 0)+1
    shares = {k: v/n_rays for k, v in sorted(hits.items(), key=lambda kv: -kv[1])}
    sig = {k: math.sqrt(v)/n_rays for k, v in hits.items()}
    top = sorted(per_obj.items(), key=lambda kv: -kv[1])[:40]
    if kernel:                                             # near-axis exposure kernel: rays uniform in solid angle to polar kmax, binned by polar angle
        kmax, nk = kernel; cmin = math.cos(math.radians(kmax)); bins = {}
        for i in range(nk):
            zc = 1.0-(1.0-cmin)*(i+0.5)/nk; rr = math.sqrt(max(0.0, 1.0-zc*zc)); t = ga*i
            d = Vector((zc, rr*math.cos(t), rr*math.sin(t)))
            th = math.degrees(math.acos(zc)); b = min(int(th/0.5), int(kmax/0.5)-1)
            loc, nrm, idx, dist = bvh.ray_cast(origin, d, 5000.0)
            B = bins.setdefault(b, {'rays': 0, 'hit': {}, 'obj': {}, 'dist': {}})
            B['rays'] += 1
            k = 'NO_HIT' if idx is None else cat(owner[idx])
            B['hit'][k] = B['hit'].get(k, 0)+1
            if idx is not None:
                B['obj'][owner[idx]] = B['obj'].get(owner[idx], 0)+1; B['dist'][k] = B['dist'].get(k, 0.0)+dist
        dom = 2*math.pi*(1.0-cmin)/(4*math.pi)               # this ray set's share of 4 pi
        kern = []
        for b in sorted(bins):
            B = bins[b]; th0, th1 = 0.5*b, 0.5*b+0.5
            sh_bin = (math.cos(math.radians(th0))-math.cos(math.radians(th1)))/2.0      # bin share of 4 pi
            kern.append({'polar_deg': [th0, th1], 'bin_share_of_4pi': sh_bin,
                         'first_hit_fraction': {k: v/B['rays'] for k, v in sorted(B['hit'].items(), key=lambda kv: -kv[1])},
                         'mean_hit_distance_m': {k: B['dist'][k]/B['hit'][k] for k in B['dist']},
                         'top_objects': [o for o, _ in sorted(B['obj'].items(), key=lambda kv: -kv[1])[:6]]})
        kernel_out = {'max_polar_deg': kmax, 'rays': nk, 'ray_set_share_of_4pi': dom, 'bins': kern,
                      'use': 'multiply first_hit_fraction x bin_share_of_4pi x (escaping energy per unit solid angle in that bin x 4 pi) to get the energy on each part'}
    else:
        kernel_out = None
    return {'axis_kernel': kernel_out, 'n_rays_full_sphere': n_rays, 'rays_cast': kept, 'objects_in_bvh': len(obs), 'shares_of_4pi': shares, 'one_sigma': sig,
            'top_objects': [{'object': o, 'share': v/n_rays} for o, v in top],
            'scope': 'V4 chosen assembly (ASM_V4), T05 hardware objects only; canon ship parts not included; first hit per ray from the burn point'}


import time as _time
_t0 = _time.time()
RC = raycast_shares(a.rays, ASM['V4'], kernel=(30.0, a.kernel_rays) if a.kernel_rays else None) if a.rays else None
RC3 = raycast_shares(a.rays, ASM['V4_REV3']) if a.rays else None
if RC:
    print('WF_RAYCAST', f'{_time.time()-_t0:.1f}s', json.dumps(RC['shares_of_4pi'])[:600], flush=True)
    try:
        _head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except Exception:
        _head = 'unknown'
    esc = CA4['escape_xray_W']
    geo = {'version': 'rev4_geometry v1', 'from': 'T05 claude/project-thread-ctwplp', 'built_on_commit': _head,
           'note': 'built from the working tree on top of built_on_commit; the commit that carries this file follows it',
           'coil_assembly': CA4, 'coil_plant': CP4, 'raycast': RC, 'raycast_rev3_chosen': RC3,
           'raycast_W_at_escape': {k: v*esc for k, v in RC['shares_of_4pi'].items()},
           'raycast_rev3_W_at_escape': {k: v*esc for k, v in RC3['shares_of_4pi'].items()}}
    (HERE/'rev4_geometry.json').write_text(json.dumps(geo, indent=1, default=float))

    CHECKS['rev4_raycast'] = {'shares_of_4pi': RC['shares_of_4pi'], 'rev3_chosen_shares_of_4pi': RC3['shares_of_4pi'], 'n': RC['n_rays_full_sphere']}

VAR_OBJS = [o for o in bpy.data.objects if o.get('wf_owner') == 'wayfarer.t05']
missing = [o.name for o in VAR_OBJS if not all(k in o.keys() for k in ('vtx_id', 'generation', 'evidence_status', 'representation', 'source', 'revision'))]
from collections import Counter
CHECKS['objects'] = {'var_objects': len(VAR_OBJS), 'missing_properties': missing[:20],
                     'by_status': dict(Counter(o['evidence_status'] for o in VAR_OBJS)), 'by_generation': dict(Counter(o['generation'] for o in VAR_OBJS))}
CHECKS['revision'] = REVISION
# Rev 4 dimension and integrity checks (each is a measurement; a FAIL is reported, never hidden)
import hashlib
def _geo_hash(objs):
    h = hashlib.sha256()
    for o in sorted(objs, key=lambda o: o.name):
        h.update(o.name.encode())
        if o.type == 'MESH':
            for v in o.data.vertices:
                h.update(('%.4f,%.4f,%.4f;' % tuple(o.matrix_world @ v.co)).encode())
    return h.hexdigest()[:16]
_xr, _ring_r, _a_ring, _S, _TI = r4_supports(e4, 'R4_T00_SHADOWED')
_c1 = CA4['coils']['C1']; _c2 = CA4['coils']['C2']; _s5 = ST4['cases']['S5_N9_T00']
_w0 = PREF['hot_x_m'][0]
R4C = {
    'preferred_coil_build': 'R4_T00_SHADOWED', 'preferred_structure': 'S5_N9_T00',
    'coil_C1_assembly_outer_m': _c1['builds']['R4_T00_SHADOWED']['assembly_outer_m'], 'coil_C2_assembly_outer_m': _c2['builds']['R4_T00_SHADOWED']['assembly_outer_m'],
    'C1_assembly_to_hot_band_aft_edge_m': _w0-(e4['closure_coils'][0]['x_m']+_c1['builds']['R4_T00_SHADOWED']['assembly_outer_m']),
    'reaction_ring_outer_r_m': _ring_r+_a_ring, 'shield_shadow_r_at_ring_m': shadow_r(e4, _xr),
    'reaction_ring_inside_shadow': _ring_r+_a_ring < shadow_r(e4, _xr),
    'S5N_longeron_to_tank_min_m': _s5['min_tank_clearance_m'], 'S5N_longeron_to_tank_ok_ge_1m': _s5['min_tank_clearance_m'] >= 1.0,
    'S5N_B2_shadow_margin_m': _s5['B2_shadow_margin_m'],
    'K2_to_keel30_m': REV3['corridor']['K2_TUBE_BESIDE_SPINE']['clearances_m']['to_keel_30'],
    'geometry_hash_t05_objects': _geo_hash([o for o in bpy.data.objects if o.get('wf_owner') == 'wayfarer.t05']),
    'object_count_t05': len([o for o in bpy.data.objects if o.get('wf_owner') == 'wayfarer.t05']),
    'rev4_parts_with_trace': len([o for o in bpy.data.objects if o.get('geom_rev') == 4]),
    'rev4_parts_missing_trace': [o.name for o in bpy.data.objects if o.get('geom_rev') == 4 and not all(k in o.keys() for k in ('issue_id', 'parameter', 'tech_id'))][:10],
}
CHECKS['rev4'] = R4C


def _hw(coll):
    return [o for o in coll.all_objects if o.type == 'MESH' and o.get('representation') == 'HARDWARE' and o.get('wf_owner') == 'wayfarer.t05'
            and not str(o.get('function', '')).upper().startswith('VIS')]


def _bvh(o):
    from mathutils.bvhtree import BVHTree
    mw = o.matrix_world
    return BVHTree.FromPolygons([mw @ v.co for v in o.data.vertices], [list(p.vertices) for p in o.data.polygons], all_triangles=False)


def interference(a_objs, b_objs):
    from mathutils import Vector
    hits = []
    for a_ in a_objs:
        ba = _bvh(a_); bb_a = [a_.matrix_world @ Vector(c) for c in a_.bound_box]
        lo = [min(v[i] for v in bb_a) for i in range(3)]; hi = [max(v[i] for v in bb_a) for i in range(3)]
        for b_ in b_objs:
            if b_ is a_:
                continue
            bb_b = [b_.matrix_world @ Vector(c) for c in b_.bound_box]
            if any(max(v[i] for v in bb_b) < lo[i] or min(v[i] for v in bb_b) > hi[i] for i in range(3)):
                continue
            if ba.overlap(_bvh(b_)):
                hits.append([a_.name, b_.name])
    return hits


def in_axis_channel(objs, deg=6.0):
    xB_ = e4['x_burn_m']; xS_ = e4['x_shield_aft_m']; t_ = math.tan(math.radians(deg)); out = []
    for o in objs:
        mw = o.matrix_world
        for v in o.data.vertices:
            p_ = mw @ v.co
            if xB_ < p_.x < xS_ and math.hypot(p_.y, p_.z) < (p_.x-xB_)*t_:
                out.append(o.name); break
    return out


_v4hw = _hw(ASM['V4'])
_bray = _hw(O4['LAUNCH_BRAY'])
_NOTHW = ('Shadow_Cone', 'KeepOut', '_Path', 'Ignition_Point', 'Plasma_Expansion')
_v4hw = [o for o in _v4hw if o.get('evidence_status') != 'CONCEPTUAL_ILLUSTRATION' and not any(k in o.name for k in _NOTHW)]
_bray_others = [o for o in _v4hw+_hw(O4['STRUCT_S5N'])+_hw(O4['COIL_SUP_R4']) if not o.name.split('_', 2)[2].startswith(('LB_', 'LBM_'))]
def near_axis_parts(objs, deg=15.0):
    xB_ = e4['x_burn_m']; out = []
    for o in objs:
        mw = o.matrix_world; best = None
        for v in o.data.vertices:
            p_ = mw @ v.co; dx = p_.x-xB_
            if dx <= 0.5:
                continue
            th = math.degrees(math.atan2(math.hypot(p_.y, p_.z), dx))
            if best is None or th < best[0]:
                best = (th, math.sqrt(dx*dx+p_.y*p_.y+p_.z*p_.z), p_.x)
        if best and best[0] < deg:
            out.append({'object': o.name, 'function': o.get('function'), 'status': o.get('evidence_status'), 'min_polar_deg': round(best[0], 3),
                        'distance_at_min_m': round(best[1], 2), 'x_at_min_m': round(best[2], 2)})
    return sorted(out, key=lambda r: r['min_polar_deg'])


CHECKS['rev4_launcher'] = {
    'axis_channel_deg': 6.0,
    'V4_chosen_hardware_in_axis_channel': in_axis_channel(_v4hw),
    'B_ray_hardware_in_axis_channel': in_axis_channel(_bray),
    'B_ray_overlaps_V4_chosen_hardware': interference(_bray, list({o.name: o for o in _bray_others}.values())),
    'B_modified_overlaps_canon_or_V4': interference(_hw(O4['LAUNCH_BMOD']), [o for o in _v4hw if not o.name.split('_', 2)[2].startswith(('LB_', 'LBM_'))]),
    'B_ray_mount_overlaps_are_intended_attachments': ['LBR_Mount_C1_Strut_Ring', 'LBR_Mount_Shield_Frame'],
    'note': 'BVH triangle overlap on drawn hardware (VIS keep-outs, concept illustrations and paths excluded from the partner set); canon objects are not tagged wayfarer.t05 and are not in this set',
}
if RC and RC.get('axis_kernel'):
    (HERE/'axis_kernel.json').write_text(json.dumps({'version': 'axis_kernel v1 (feasibility gate, T05 geometry support for ISS-022)', 'built_on_commit': _head,
        'origin': 'burn point X %.2f m on the axis' % e4['x_burn_m'], 'scope': RC['scope'], 'kernel': RC['axis_kernel'],
        'parts_within_15deg': near_axis_parts(_v4hw), 'x_shield_aft_m': e4['x_shield_aft_m'], 'shield_r_hw_m': e4['shield_r_hw_m']}, indent=1, default=float))
pb = R4['shield']['streaming']['pellet_bore']['plug_length_m']; c1 = e4['closure_coils'][0]; LB = P4['B']; LC = P4['C']
CHECKS['rev2'] = {
    'source': 'rev2.json (work/vertex-blender/rev2.py) plus the placements built here',
    'assemblies': CHECKS.get('assemblies'),
    'launcher_B_breech_plug_fwd_end_to_crew_trunk_m': CANON2['crew_trunk_x_m'][0]-(BREECH_X+0.3+pb),
    'launcher_B_snout_tip_x_m': LB['muzzle_x_m'], 'launcher_B_tip_to_burn_m': LB['muzzle_x_m']-e4['x_burn_m'],
    'launcher_B_snout_to_C1_envelope_radial_m': c1['r_m']-c1['envelope_r_m'][1]-0.6,
    'launcher_C_line_to_thrust_ring_inner_m': CANON2['thrust_ring_r_m'][0]-LC['r_at_thrust_ring_m'],
    'skirt_B2_edge_to_dock_corridor_m': (C['dock_primary']['x_m']-CANON2['dock_corridor_halfwidth_m'])-REV2['dust']['options']['B2_DOCK_CLEAR']['edge_x_m'],
    'skirt_B2_crosses_bypass_collar': REV2['dust']['options']['B2_DOCK_CLEAR']['meets_bypass_collar'],
    'graded_hot_band_to_ring_A_m': C['ring_a_aft_face_x_m']-PREF['hot_x_m'][1],
    'canon_hot_blade_objects_left_out_of_V4': CHECKS['ship_edits'].get('V4', {}).get('hot_objects') if 'ship_edits' in CHECKS else None,
    'spine_extension_m': e4['tanks_TB']['bow_shift_m'],
    'launcher_options': {k: {kk: P4[k][kk] for kk in ('status', 'accelerator_m', 'exit_speed_m_s', 'accel_g', 'shell_stress_MPa', 'stress_margin', 'targets_in_barrel', 'electric_W', 'line_of_sight_m')} for k in P4},
}
(HERE/'checks.json').write_text(json.dumps(CHECKS, indent=1, default=float))
readme = bpy.data.texts.new('README_VERTEX')
readme.write((HERE/'REPORT.md').read_text() if (HERE/'REPORT.md').exists() else 'Vertex Stage B review file. See work/vertex-blender/REPORT.md.\n')
for nm, body in (('VERTEX_PART_STATUS', '\n'.join(f'{g:4s} {s:26s} {n:60s} {v:8s} {src}  {nt}' for g, s, n, v, src, nt in PART_LOG)),
                 ('VERTEX_CHECKS.json', json.dumps(CHECKS, indent=1, default=float)),
                 ('VERTEX_COLOR_LEGEND', '\n'.join(f'{k}: {v[0]}  RGBA {tuple(round(c, 2) for c in v[1])}' for k, v in PALETTE.items())),
                 ('VERTEX_STATUS_LEGEND', 'Object names start <generation>_<ES|PP|PR|CI>_.\nES ENGINEERING_SUPPORTED (opaque), PP PARAMETRIC_PLACEHOLDER (0.75),\n'
                                          'PR PROTOTYPE (0.6, T05 judgment), CI CONCEPTUAL_ILLUSTRATION (0.18, overlays). V5 is wire only (ghost).\n')):
    bpy.data.texts.new(nm).write(body)
for g in GENS:
    bpy.data.texts.new(f'VERTEX_PARAMS_{g}.json').write(json.dumps(ENV[g], indent=1, default=float))
print('WF_VTX objects', len(VAR_OBJS), 'missing props', len(missing), flush=True)

# ----------------------------------------------------------------------------------------------------------------------------------
if a.render:
    a.render.mkdir(parents=True, exist_ok=True)
    for name, (ob, names) in CAMS.items():
        if a.cams and name not in a.cams:
            continue
        for n in ob['render_scenes']:
            sc = bpy.data.scenes[n]; sc.camera = ob
            hide = [o for o in bpy.data.objects if any(k in o.name for k in RENDER_HIDE.get(name, ()))]
            for o in hide:
                o.hide_render = True
            sc.render.filepath = str(a.render/f'{name}.png')
            bpy.ops.render.render(write_still=True, scene=sc.name)
            print('WF_RENDER', sc.render.filepath, flush=True)
            for o in hide:
                o.hide_render = False
    for sc, cam in DEFAULT.items():
        SC[sc].camera = CAMS[cam][0]
if not a.no_save:
    win = bpy.context.window_manager.windows
    if win:
        win[0].scene = SC['COMPARE_SIDE_BY_SIDE']
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(a.out), compress=True)
    print('WF_REVIEW saved', a.out, flush=True)
