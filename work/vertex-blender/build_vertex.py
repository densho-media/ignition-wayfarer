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
a = a.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])

SHIP = ROOT/'assets/wayfarer/WF_WAYFARER_001.blend'
REVISION = 1
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


def make(name, shape, coll, func, gen, status, vtx, source, rep='HARDWARE', note=None, alpha=None, wire=False, cut=None, **kw):
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
    tag(ob, gen, status, vtx, source, rep, note, function=PALETTE.get(func, (func,))[0])
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
    dx = ENV[gen]['tanks_TB']['bow_shift_m']; x_from = C['tank_farm_x_m'][1]+0.05
    log = {'left_out_assemblies': [], 'left_out_objects': 0, 'bow_objects': 0, 'aft_objects': 0, 'bow_shift_m': dx, 'split_x_m': x_from}
    for asm in [o for o in canon.all_objects if o.instance_type == 'COLLECTION' and o.instance_collection]:
        base = asm.name.split('.')[0]
        if base.startswith(SUPERSEDED):
            log['left_out_assemblies'].append(base); continue
        sub = asm.instance_collection
        parts = {'AFT': bpy.data.collections.new(f'{sub.name}_{gen}_AFT'), 'BOW': bpy.data.collections.new(f'{sub.name}_{gen}_BOW')}
        for p in parts.values():
            p.instance_offset = sub.instance_offset
        for r in _roots(sub):
            rb = r.name.split('.')[0]
            if rb.startswith(SUPERSEDED) or (gen in ('V4', 'V5') and rb.startswith('Fuel_Tank_') and rb.endswith('_H2')):
                log['left_out_objects'] += len(_tree(r)); log.setdefault('left_out_names', []).append(rb); continue
            pts = [o.matrix_world @ Vector(v) for o in _tree(r) for v in (o.bound_box if o.type in ('MESH', 'CURVE', 'FONT') else [(0, 0, 0)])]
            key = 'BOW' if min(v.x for v in pts) >= x_from else 'AFT'
            for o in _tree(r):
                if o.name not in parts[key].objects:
                    parts[key].objects.link(o)
            log[key.lower()+'_objects'] += len(_tree(r))
        for key, p in parts.items():
            if not p.objects:
                bpy.data.collections.remove(p); continue
            e = bpy.data.objects.new(f'WORK_{gen}_{base}_{key}', None); e.instance_type = 'COLLECTION'; e.instance_collection = p
            e.matrix_world = asm.matrix_world.copy()
            if key == 'BOW':
                e.location.x += dx
            work.objects.link(e)
    print('WF_VTX working copy', gen, log, flush=True)
    return work, log


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


def build_fdp_parts(gen, R, colls, cut=None, ghost=False):
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
        make(p['name'].replace('FDP1_', ''), p['shape'], colls[key], p['func'], gen, st, vtx_of(p['name']),
             f'solve:{gen} fdp1 geometry.parts', note=p.get('note'), alpha=al, wire=ghost, cut=cut, **kw)


def build_nozzle(gen, R, e, colls, cut=None, ghost=False):
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
            make(f"{L['name']}_Local_Bumper", 'torus', colls['10'], 'SHIELD', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-08F', 'T02 HANDOFF E',
                 note='local bumper, 2 m stand-off on both faces (outside r 45 m)', x=L['x'], R=L['r'], a=env+2.0, alpha=0.15, cut=cut)
        if i >= 1:                                                 # guard rings 22.5 m forward of L2 and L3 (VTX-08F, scaled to the loop radii)
            make(f"{L['name']}_Guard_Ring", 'torus', colls['10'], 'SHIELD', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-08F', 'T02 HANDOFF E (20-25 m fwd)',
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
        make(nm+'_Envelope', 'torus', colls['02'], 'LOW_RADIATOR', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-03D', s3,
             note=f"cryostat + warm eddy screen envelope r {c['envelope_r_m'][0]:.1f}-{c['envelope_r_m'][1]:.1f} m", x=c['x_m'], R=c['r_m'],
             a=c['envelope_r_m'][1], alpha=0.22, cut=cut)
    if ghost:
        return
    # load-path candidates: C1 -> shield frame ring (compression), C2 -> C1 and C2 -> L1 (tension ties); unsized (ISS-003)
    c1, c2 = e['closure_coils']; L1 = loops[0]
    ring_r = sh['radius_hw_aft_m']+1.0
    make('Coil_Reaction_Ring', 'torus', colls['08'], 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-03D', 'T05 PR (ISS-003)',
         note='candidate reaction ring on the shield aft face carrying C1/C2 axial force into the shield frame; unsized',
         x=xSA-0.8, R=ring_r, a=0.8, cut=cut)
    for j in range(PR_COIL_STRUTS):
        az = 360.0*j/PR_COIL_STRUTS+30.0
        make(f'C1_Strut_{j+1}', 'tube', colls['08'], 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-02D', 'T05 PR (ISS-003)',
             note='C1 -> shield reaction ring, compression member for 0.2-1.9 GN inter-coil attraction; unsized',
             points=[pol(c1['x_m'], c1['r_m'], az), pol(xSA-0.8, ring_r, az)], radius=0.6, cut=cut)
        make(f'C2_Tie_C1_{j+1}', 'tube', colls['08'], 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-02D', 'T05 PR (ISS-003)',
             note='C2 -> C1 tie (one candidate path); unsized', points=[pol(c2['x_m'], c2['r_m'], az), pol(c1['x_m'], c1['r_m'], az)], radius=0.4, cut=cut)
        make(f'C2_Tie_L1_{j+1}', 'tube', colls['08'], 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-02D', 'T05 PR (ISS-003)',
             note='C2 -> L1 tie (alternative candidate path); unsized', points=[pol(c2['x_m'], c2['r_m'], az+15), pol(L1['x'], L1['r'], az+15)],
             radius=0.4, alpha=0.35, cut=cut)


def build_module(gen, R, e, colls, cut=None):
    """Launcher, catcher, ignitor line, tritium store in the equipment module (VTX-01H, 01G); returns the corridor fit."""
    lay = R['layout']; xSF = lay['x_shield_fwd']; xMF = lay['x_module_fwd']
    plug = R['shield']['streaming']['pellet_bore']
    x_mag = xSF+14.5; x_plug = xSF+16.0
    v = e['launcher_one_in_flight_m_s']; free = x_mag-xSF
    make('Target_Launcher_Barrel', 'tube', colls['07'], 'MAIN_PROPULSION', gen, 'PROTOTYPE', 'VTX-01H', 'T05 PR_LAUNCHER_LEN (UNKNOWN 10-20 m)',
         note=f'barrel {PR_LAUNCHER_LEN:.0f} m, >= {v/1e3:.1f} km/s for one target in flight; length UNKNOWN', unbooked='launcher',
         points=[(xSF+PR_LAUNCHER_LEN, 0, 0), (xSF+0.2, 0, 0)], radius=PR_LAUNCHER_R, cut=cut)
    make('Sabot_Catcher', 'ring', colls['07'], 'MAIN_PROPULSION', gen, 'PROTOTYPE', 'VTX-01H', 'T05 PR', note='annular sabot trap at the muzzle',
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


def build_wings(gen, R, e, colls, ghost=False, graded=None, coll=None, label='', alpha_hot=None):
    """W2 wings at az 0/180 in the z = 0 plane: 1,800 K root band, warm circuit bands (T01 proportions) outward, two spars, ribs every
    1 km, a droplet generator bar on the forward edge and a collector on the aft edge, the droplet sheet as a translucent overlay."""
    w = e['wing']; x0, x1 = w['x_m']; h0, h1 = w['hot_band_r_m']; tip = w['tip_r_m']; src = f'solve:{gen} thermal.layouts.W2'
    out = coll or colls['05']
    hx0, hx1, hr1 = (x0, x1, h1) if graded is None else graded
    for side, az in (('P', 0.0), ('S', 180.0)):
        if ghost:
            make(f'Wing_{side}_Outline', 'panel', out, 'WARM_RADIATOR', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-07', src, alpha=0.15, wire=True,
                 corners=[pol(x0, h0, az), pol(x1, h0, az), pol(x1, tip, az), pol(x0, tip, az)], thickness=0.5)
            continue
        make(f'Wing_{side}_Hot_Band{label}', 'panel', out, 'HOT_RADIATOR', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-07F', src,
             note=f"1,800 K band r {h0:.0f}-{hr1:.0f} m, X {hx0:.1f} to {hx1:.1f} m", alpha=alpha_hot,
             corners=[pol(hx0, h0, az), pol(hx1, h0, az), pol(hx1, hr1, az), pol(hx0, hr1, az)], thickness=0.4)
        if graded is not None:
            # forward root corner left by the graded hot band: capacitor (550 K) circuit, same plane
            make(f'Wing_{side}_Root_Capacitor_Band{label}', 'panel', out, 'WARM_RADIATOR', gen, 'PROTOTYPE', 'VTX-07E', 'T05 graded layout',
                 note='550 K capacitor circuit in the forward root corner by the rings', alpha=0.45,
                 corners=[pol(hx1+2, h0, az), pol(x1, h0, az), pol(x1, hr1, az), pol(hx1+2, hr1, az)], thickness=0.3)
            continue
        r = h1+2.0
        for T, sh in band_shares():
            dr = sh*(tip-h1-2.0)
            make(f'Wing_{side}_Warm_{T}K', 'panel', out, 'WARM_RADIATOR', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-07B',
                 f'{src}; band shares T01 ledger S1_advanced_eta0.30', rep='MIXED',
                 note=f'tin droplet sheet, {T} K circuit band (exists only while the drive runs)', alpha=0.22+0.2*(T-550)/450,
                 corners=[pol(x0+4, r, az), pol(x1-4, r, az), pol(x1-4, r+dr, az), pol(x0+4, r+dr, az)], thickness=0.2)
            make(f'Wing_{side}_Manifold_{T}K', 'tube', out, 'WARM_RADIATOR', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-07E', src,
                 note=f'thermal break and manifold at the {T} K band root', points=[pol(x0, r, az), pol(x1, r, az)], radius=0.8)
            r += dr
        make(f'Wing_{side}_Thermal_Break', 'tube', colls['08'], 'STRUCTURE', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-07D', src,
             points=[pol(x0, h1+1.0, az), pol(x1, h1+1.0, az)], radius=1.0)
        for nm, xe, rad in (('Spar_Aft', x0, 1.2), ('Spar_Fwd', x1, 1.2)):
            make(f'Wing_{side}_{nm}', 'tube', colls['08'], 'STRUCTURE', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-07D', src,
                 note='12.5 kg/m CFRP spar (V4 package); buckling of the 10 km compression spar not modelled (ISS-005)',
                 points=[pol(xe, h0, az), pol(xe, tip, az)], radius=rad)
        k = 1; rr = h0+PR_RIB_PITCH
        while rr < tip:
            make(f'Wing_{side}_Rib_{k:02d}', 'tube', colls['08'], 'STRUCTURE', gen, 'PROTOTYPE', 'VTX-07D', 'T05 PR_RIB_PITCH',
                 note='chordwise rib / deployment hinge station (1 km pitch)', points=[pol(x0, rr, az), pol(x1, rr, az)], radius=0.7)
            k += 1; rr += PR_RIB_PITCH
        make(f'Wing_{side}_Droplet_Generator', 'tube', out, 'WARM_RADIATOR', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-07B', 'T01 REPORT 5',
             rep='HARDWARE', note='droplet generator bar on the forward edge: drops fly along -X', points=[pol(x1-2, h1+2, az), pol(x1-2, tip, az)], radius=1.6, alpha=0.8)
        make(f'Wing_{side}_Droplet_Collector', 'tube', out, 'WARM_RADIATOR', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-07B', 'T01 REPORT 5',
             rep='HARDWARE', note='collector trough on the aft edge', points=[pol(x0+2, h1+2, az), pol(x0+2, tip, az)], radius=2.4, alpha=0.8)
        make(f'Wing_{side}_Root_Boom', 'tube', colls['08'], 'STRUCTURE', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-07D', src,
             points=[pol(x0, h0, az), pol(x1, h0, az)], radius=1.0)
        for j, xr in enumerate((x0+20, (x0+x1)/2, x1-20)):
            make(f'Wing_{side}_Root_Strut_{j}', 'tube', colls['08'], 'STRUCTURE', gen, 'PARAMETRIC_PLACEHOLDER', 'VTX-07D', src,
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
            for nm, az in (('Primary', C['dock_primary']['az_deg']), ('Service', C['dock_service']['az_deg'])):
                xd = C['dock_primary']['x_m']; rd = (xd-xB)*t
                make(f'Skirt_A_Dock_Aperture_{nm}', 'torus', c, 'VIS_CONFLICT', gen, 'CONCEPTUAL_ILLUSTRATION', 'VTX-08E', 'T05 ISS-004',
                     rep='VISUALIZATION', note=f'docking corridor pierces the skirt here (skirt r {rd:.1f} m at X {xd:.2f} m)',
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
bpy.ops.wm.read_factory_settings(use_empty=True)
for nm in list(bpy.data.scenes):
    pass
main = bpy.context.scene; main.name = 'VERTEX_V4'
SC = {'VERTEX_V4': main}
for nm in ('CANON_WAYFARER', 'VERTEX_V0', 'COMPARE_SIDE_BY_SIDE', 'COMPARE_TOP', 'COMPARE_SPAN', 'VERTEX_CUTAWAY', 'BRAKING_EXPOSURE',
           'RADIATOR_ALTERNATIVES'):
    SC[nm] = bpy.data.scenes.new(nm)

LIB = new_coll('VERTEX_LIBRARY', main.collection)          # every built collection hangs here once; scenes link what they show
ships, fps = {}, {}
if not a.no_ship:
    ships['CANON'] = append_ship('CANON_WAYFARER_SHIP_main'); fps['before'] = fingerprint(ships['CANON'])
    for g in ('V4', 'V0'):
        ships[g], CHECKS.setdefault('ship_edits', {})[g] = prepare_working_copy(ships['CANON'], g)

ASM, VAR, COLL = {}, {}, {}
CORR = {}
for g in GENS:
    R = RS[g]; e = ENV[g]
    top = bpy.data.collections.new(f'ASM_{g}'); ASM[g] = top
    root, colls = gen_collections(g, top); VAR[g] = root; COLL[g] = colls
    ghost = g == 'V5'
    if ghost:
        for k in ('03', '04', '06', '07', '09', '10', '11', '12'):
            pass
        build_nozzle(g, R, e, colls, ghost=True)
        build_wings(g, R, e, colls, ghost=True)
        make('Shield_Ghost', 'frustum', colls['03'], 'SHIELD', g, 'ENGINEERING_SUPPORTED', 'VTX-06A', f'solve:{g}', alpha=0.15, wire=True,
             x0=e['x_shield_aft_m'], r0=e['shield_r_hw_m'], x1=e['x_shield_fwd_m'], r1=e['shield_r_hw_m'])
        make('StandOff_Ghost', 'sphere', colls['11'], 'VIS_XRAY', g, 'ENGINEERING_SUPPORTED', 'VTX-01', f'solve:{g}', rep='VISUALIZATION', alpha=0.08,
             wire=True, centre=(e['x_burn_m'], 0, 0), radius=e['stand_off_m'])
        continue
    if g in ships:
        top.children.link(ships[g])
    build_fdp_parts(g, R, colls)
    build_nozzle(g, R, e, colls)
    CORR[g] = build_module(g, R, e, colls)
    build_wings(g, R, e, colls)
    build_overlays(g, R, e, colls['01'])
    skirts, x45 = build_skirts(g, R, e, colls['10'])
    COLL[g]['skirts'] = skirts
    measure(g, R, e, CORR[g], x45)

# V4 extras: alternatives, graded band, dust stream, labels
e4 = ENV['V4']; R4 = RS['V4']
ALT = bpy.data.collections.new('VAR_VERTEX_V4_ALTERNATIVES'); ALT.color_tag = 'COLOR_07'
mit = screen_data['V4_hot_band_mitigations']['hot_aft_of_RADIATOR_FRONT_and_20m_clear_of_C1']
GRADED = new_coll('VAR_VERTEX_V4_ALT_R0G_GRADED_HOT_BAND', ALT, 'COLOR_07')
build_wings('V4', R4, e4, COLL['V4'], graded=(mit['hot_x_m'][0], mit['hot_x_m'][1], mit['hot_r_m'][1]), coll=GRADED, label='_GRADED')
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
make('CONFLICT_HotBand_RingA', 'tube', COLL['V4']['11'], 'VIS_CONFLICT', 'V4', 'CONCEPTUAL_ILLUSTRATION', 'VTX-07F', 'checks.json', rep='VISUALIZATION',
     note=f"{m4['hot_band_fwd_edge_to_ring_A_m']:.1f} m; {m4['ring_A_irradiance_W_m2']/1e3:.0f} kW/m2 on ring A", points=[(w['x_m'][1], 30.0, 0.5), (xa, 30.0, 0.5)], radius=0.8, alpha=1.0)
c1 = e4['closure_coils'][0]
make('CONFLICT_C1_HotBand', 'tube', COLL['V4']['11'], 'VIS_CONFLICT', 'V4', 'CONCEPTUAL_ILLUSTRATION', 'VTX-03D', 'checks.json', rep='VISUALIZATION',
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
    ('module', f"module: launcher >= {CORR['V4']['one_in_flight_m_s']/1e3:.1f} km/s, ignitor, tritium store (PROTOTYPE)", (-185, 0, 14), 3),
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
exclude(SC['VERTEX_V4'], [COLL['V4']['skirts']['B_SHORT'].name, PANEL.name, OUTL.name, DUST.name, GRADED.name, VAR['V5'].name])
link(SC['VERTEX_V0'], ASM['V0'])
exclude(SC['VERTEX_V0'], [COLL['V0']['skirts']['B_SHORT'].name])
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
build_fdp_parts('V4', R4, ccolls, cut=(200.0, 340.0))
for o in [o for c in ccolls.values() for o in c.objects if o.name.split('_', 2)[2].startswith(('Wing_', 'Shadow_Cone', 'Low_Loop', 'Feed_Line', 'KeepOut_Plume', 'TB_'))]:
    bpy.data.objects.remove(o)
build_nozzle('V4', R4, e4, ccolls, cut=(200.0, 340.0))
build_module('V4', R4, e4, ccolls, cut=(200.0, 340.0))
build_overlays('V4', R4, e4, ccolls['01'])
link(SC['VERTEX_CUTAWAY'], CUT)

# braking exposure: V4 with skirt A and the dust stream; radiator alternatives: V4 hull + outlines + graded band
link(SC['BRAKING_EXPOSURE'], ASM['V4']); link(SC['BRAKING_EXPOSURE'], DUST)
exclude(SC['BRAKING_EXPOSURE'], [COLL['V4']['skirts']['B_SHORT'].name])
link(SC['RADIATOR_ALTERNATIVES'], ASM['V4']); link(SC['RADIATOR_ALTERNATIVES'], ALT)
exclude(SC['RADIATOR_ALTERNATIVES'], [DUST.name, PANEL.name])

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
}
CAMS['CAM_VTX_09_RADIATOR_ALTS_END'][0].rotation_euler = (math.radians(90), 0, math.radians(-90))
for name, (ob, names) in CAMS.items():
    ob['render_scenes'] = [n for n in names if n in bpy.data.scenes]
    for n in ob['render_scenes']:
        bpy.data.scenes[n].collection.objects.link(ob)
DEFAULT = {'COMPARE_SIDE_BY_SIDE': 'CAM_VTX_01_SIDE_COMPARE', 'COMPARE_TOP': 'CAM_VTX_02_TOP_COMPARE', 'COMPARE_SPAN': 'CAM_VTX_04_SPAN_FULL',
           'VERTEX_V4': 'CAM_VTX_06_AFT_ASSEMBLY', 'VERTEX_CUTAWAY': 'CAM_VTX_07_CUTAWAY', 'BRAKING_EXPOSURE': 'CAM_VTX_08_BRAKING_EXPOSURE',
           'RADIATOR_ALTERNATIVES': 'CAM_VTX_09_RADIATOR_ALTS_END', 'VERTEX_V0': 'CAM_VTX_15_V0_WHOLE', 'CANON_WAYFARER': 'CAM_VTX_16_CANON'}
for sc, cam in DEFAULT.items():
    SC[sc].camera = CAMS[cam][0]

# hide the wings for the top compare camera (they cover the other lanes); render-time per camera hiding
WING = ('_Wing_', 'TIP_', 'ALT_')
PLUME = ('_Shadow_Cone', '_KeepOut', '_Exhaust_', 'Dust_Streak', 'StandOff_dense')
RENDER_HIDE = {'CAM_VTX_02_TOP_COMPARE': WING+PLUME, 'CAM_VTX_01_SIDE_COMPARE': PLUME, 'CAM_VTX_03_THREEQ_COMPARE': PLUME,
               'CAM_VTX_06_AFT_ASSEMBLY': PLUME, 'CAM_VTX_10_RADIATOR_STATES': PLUME, 'CAM_VTX_12_DOCK_HAB_CLEARANCE': PLUME,
               'CAM_VTX_13_RING_HOTBAND': PLUME, 'CAM_VTX_14_C1_WING': PLUME, 'CAM_VTX_15_V0_WHOLE': PLUME, 'CAM_VTX_17_V4_WHOLE': PLUME,
               'CAM_VTX_11_MAINTENANCE': PLUME+('_LBL_',), 'CAM_VTX_07b_MODULE_CUTAWAY': ('_LBL_',), 'CAM_VTX_08_BRAKING_EXPOSURE': ('_Exhaust_', '_KeepOut_Plume')}

# ----------------------------------------------------------------------------------------------------------------------------------
# checks, texts
# ----------------------------------------------------------------------------------------------------------------------------------
if 'CANON' in ships:
    after = fingerprint(ships['CANON'])
    CHECKS['canon_unchanged'] = {'objects': len(after), 'identical_to_append': after == fps['before']}
    src_ship = bpy.data.collections.get('CANON_WAYFARER_SHIP_main')
VAR_OBJS = [o for o in bpy.data.objects if o.get('wf_owner') == 'wayfarer.t05']
missing = [o.name for o in VAR_OBJS if not all(k in o.keys() for k in ('vtx_id', 'generation', 'evidence_status', 'representation', 'source', 'revision'))]
from collections import Counter
CHECKS['objects'] = {'var_objects': len(VAR_OBJS), 'missing_properties': missing[:20],
                     'by_status': dict(Counter(o['evidence_status'] for o in VAR_OBJS)), 'by_generation': dict(Counter(o['generation'] for o in VAR_OBJS))}
CHECKS['revision'] = REVISION
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
