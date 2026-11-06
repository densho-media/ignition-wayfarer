"""Build lab/variants/fiji-drive/REVIEW_FIJI_DRIVE.blend (owner review file: opens on the Fiji Drive, nothing to run) and optionally render it.
Study helper; nothing in src/ reads it.

  /snap/bin/blender -b --factory-startup --python lab/variants/fiji-drive/make_review.py -- [--render DIR] [--cams ...] [--samples N]

Scenes
- FIJI_DRIVE: the built ship of this branch (= main 5a913f9) appended and made local, with the Fiji Drive revision in WORK_FIJI_DRIVE
  (00..12 collections, functional viewport colours) replacing the hidden drive hardware it supersedes; powered down (COAST).
- FIJI_DRIVE_ACTIVE: the same, with 12_VISUALIZATION/VIS_ACTIVE_STATE (plasma, exhaust, energised lattice and coil glow) shown.
- FIJI_DRIVE_CUTAWAY: the drive alone, a 120-degree wedge cut away toward the camera, plasma shown.
- FIJI_DRIVE_SYSTEMS: an exploded systems sheet: each functional collection instanced on its own row (orthographic).
- BEFORE_MAIN_5A913F9: the untouched main ship for comparison.
Nothing is deleted from the original model: superseded objects are hidden (listed in the README text), the casing aft of the shadow shield
is cut in this file only (the open reactor bay).
"""
import argparse
import math
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation')]
import spec  # noqa: E402
import hero_preview as hp  # noqa: E402
import fiji_geometry as fg  # noqa: E402

a = argparse.ArgumentParser(); a.add_argument('--out', type=Path, default=HERE/'REVIEW_FIJI_DRIVE.blend')
a.add_argument('--render', type=Path); a.add_argument('--samples', type=int, default=32); a.add_argument('--cams', nargs='+')
a.add_argument('--size', type=int, nargs=2, default=(1920, 1080)); a.add_argument('--no-before', action='store_true')
a = a.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
s = spec.load()[0]; prm = fg.params(); g, ST = fg.stations(s)
SHIP = ROOT/'assets/wayfarer/WF_WAYFARER_001.blend'

# ------------------------------------------------------------------------------------------------------------------------------------
# ship
# ------------------------------------------------------------------------------------------------------------------------------------

def append(blend, coll):
    with bpy.data.libraries.load(str(blend), link=False) as (src, dst):
        dst.collections = [coll]
    return dst.collections[0]


def make_all_local():
    for _ in range(5):
        n = 0
        for attr in ('collections', 'objects', 'meshes', 'curves', 'materials', 'node_groups', 'actions', 'images', 'texts', 'lights', 'cameras', 'fonts'):
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


def hide_helpers(coll):
    for c in coll.children_recursive:
        if c.name.split('.')[0] in ('40_SIM_RIG', '30_CAMERAS', '20_HUMAN_SCALE'):
            c.hide_viewport = True; c.hide_render = True


KEEP_PROPULSION = ('LASER_', 'OPTICAL_', 'GATE_', 'IF_LASER', 'IF_OPTICAL', 'SPINE_TERMINATION', 'IF_SPINE', 'DRIVE_', 'WF_DRIVE_ROOT')
CUT_PREFIXES = ('Hull_Aft_Body', 'Prod_SP_CASING', 'Casing_Seams', 'Casing_Access', 'Survival_Crawler_Rail', 'Drone_Rail_DS-13')


def supersede(ship_colls):
    """Hide what the revision replaces, cut the casing aft of the shield. Returns the README list."""
    hidden, cut = [], []
    prop = bpy.data.collections.get('WF_PROPULSION')
    for o in [o for o in (prop.all_objects if prop else []) if o is not None]:
        if not o.name.startswith(KEEP_PROPULSION) or o.name.startswith('DRIVE_DEBUG'):
            if not o.hide_render:
                hidden.append(o.name)
            o.hide_viewport = o.hide_render = True
    for name in ['Reactor_Shadow_Shield_Envelope']+[f'Nozzle_Pickup_{k}' for k in range(4)]+[o.name for o in bpy.data.objects if o.name.startswith(('Drone_Dock_DS-13', 'Drone_Dock_DS-14', 'Drone_Unit_DR-EVA-03', 'Drone_Unit_DR-EVA-04', 'Drone_ArmBase_DS-16'))]:
        o = bpy.data.objects.get(name)
        if o:
            o.hide_viewport = o.hide_render = True; hidden.append(name)
    xcut = ST['shield_fwd']
    for o in list(bpy.data.objects):
        if o.type != 'MESH' or not o.name.startswith(CUT_PREFIXES):
            continue
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        if min(v.x for v in bb) >= xcut:
            continue
        if max(v.x for v in bb) <= xcut:
            o.hide_viewport = o.hide_render = True; hidden.append(o.name); continue
        o.data = o.data.copy()
        bm = bmesh.new(); bm.from_mesh(o.data)
        inv = o.matrix_world.inverted(); co = inv @ Vector((xcut, 0, 0)); no = (inv.to_3x3().transposed() @ Vector((1, 0, 0))).normalized()
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:]+bm.edges[:]+bm.faces[:], plane_co=co, plane_no=no, clear_inner=True)
        bm.to_mesh(o.data); bm.free(); cut.append(o.name)
    return hidden, cut


# ------------------------------------------------------------------------------------------------------------------------------------
# revision builder
# ------------------------------------------------------------------------------------------------------------------------------------
MATS = {}
LOOK = {   # production depiction per function: base colour, metallic, roughness
    'STRUCTURE': ((.62, .63, .65), .6, .42), 'CORE': ((.70, .40, .16), .5, .45), 'COIL': ((.20, .26, .36), .55, .38),
    'LATTICE': ((.26, .15, .38), .85, .22), 'PLASMA': ((.35, .52, .56), .6, .35), 'PROPELLANT': ((.78, .80, .74), .1, .6),
    'THERMAL': ((.55, .22, .16), .5, .45), 'SHIELDING': ((.24, .24, .26), .7, .5), 'DIAGNOSTIC': ((.80, .66, .20), .3, .45),
}


def mat(func, emit=None, strength=0.0, alpha=1.0):
    key = (func, emit, strength, alpha)
    if key in MATS:
        return MATS[key]
    name = f'FIJI_{func}' + (f'_GLOW_{strength:g}' if emit else '') + (f'_A{alpha:g}' if alpha < 1 else '')
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    base, met, rough = LOOK.get(func, ((.8, .8, .85), 0, .5))
    b.inputs['Base Color'].default_value = (*base, 1); b.inputs['Metallic'].default_value = met; b.inputs['Roughness'].default_value = rough
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1); b.inputs['Emission Strength'].default_value = strength
        b.inputs['Base Color'].default_value = (*emit, 1)
    if alpha < 1:
        b.inputs['Alpha'].default_value = alpha
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            pass
    m.diffuse_color = (*fg.PALETTE[func][1][:3], 1) if func in fg.PALETTE else (*base, 1)
    MATS[key] = m
    return m


def ring_mesh(x0, x1, r0, r1, cy=0.0, cz=0.0, segments=1, gap_deg=0.0, phase_deg=0.0, cut=None):
    """Annular solid (closed) in `segments` arcs separated by gap_deg; r0 = 0 gives a disc. cut: (a0, a1) wedge left out (radians)."""
    vs, fs = [], []
    seg_span = 2*math.pi/segments; gap = math.radians(gap_deg) if segments > 1 else 0.0
    arcs = []
    for k in range(segments):
        a0 = math.radians(phase_deg)+k*seg_span+gap/2; a1 = a0+seg_span-gap
        arcs.append((a0, a1, segments == 1 and not cut))
    if cut:
        c0, c1 = cut; arcs2 = []
        for a0, a1, closed in arcs:
            if closed:
                arcs2.append((c1, c0+2*math.pi, False)); continue
            lo, hi = a0, a1
            m0, m1 = math.remainder(lo-c0, 2*math.pi), math.remainder(hi-c0, 2*math.pi)
            w = c1-c0
            if 0 <= m0 <= w and 0 <= m1 <= w:
                continue
            arcs2.append((a0, a1, False))
        arcs = arcs2
    for a0, a1, closed in arcs:
        span = a1-a0; n = max(6, int(span*max(r1, .3)/0.12)); n = min(n, 160)
        base = len(vs); cnt = n if closed else n+1
        for i in range(cnt):
            t = a0+span*i/n; c, sn = math.cos(t), math.sin(t)
            for x in (x0, x1):
                for r in (r0, r1):
                    vs.append((x, cy+r*c, cz+sn*r))
        idx = lambda i, xi, ri: base+(i % cnt)*4+xi*2+ri
        for i in range(n):
            j = i+1
            fs += [(idx(i, 0, 1), idx(j, 0, 1), idx(j, 1, 1), idx(i, 1, 1)),
                   (idx(i, 0, 0), idx(i, 1, 0), idx(j, 1, 0), idx(j, 0, 0)),
                   (idx(i, 0, 0), idx(j, 0, 0), idx(j, 0, 1), idx(i, 0, 1)),
                   (idx(i, 1, 0), idx(i, 1, 1), idx(j, 1, 1), idx(j, 1, 0))]
        if not closed:
            for i in (0, n):
                f = (idx(i, 0, 0), idx(i, 0, 1), idx(i, 1, 1), idx(i, 1, 0))
                fs.append(f if i == n else f[::-1])
    return vs, fs


def torus_mesh(center, axis, R, tube, nu=48, nv=10):
    u, v, w = fg.frame_from(axis); vs, fs = [], []
    for i in range(nu):
        t = 2*math.pi*i/nu; d = fg.add(fg.mul(u, math.cos(t)), fg.mul(v, math.sin(t)))
        for j in range(nv):
            p = 2*math.pi*j/nv; rr = R+tube*math.cos(p)
            vs.append(fg.add(center, fg.add(fg.mul(d, rr), fg.mul(w, tube*math.sin(p)))))
    for i in range(nu):
        for j in range(nv):
            a_, b_ = i*nv+j, ((i+1) % nu)*nv+j; c_, d_ = ((i+1) % nu)*nv+(j+1) % nv, i*nv+(j+1) % nv
            fs.append((a_, b_, c_, d_))
    return vs, fs


def box_mesh(center, size, frame):
    vs = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                p = center
                for ax, h, sg in zip(frame, size, (sx, sy, sz)):
                    p = fg.add(p, fg.mul(ax, h/2*sg))
                vs.append(p)
    fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return vs, fs


def hex_mesh(center, normal, radius, height):
    u, v, w = fg.frame_from(normal); vs = []
    for hgt in (0.0, height):
        for k in range(6):
            t = math.pi/3*k
            vs.append(fg.add(center, fg.add(fg.add(fg.mul(u, radius*math.cos(t)), fg.mul(v, radius*math.sin(t))), fg.mul(w, hgt))))
    fs = [tuple(range(5, -1, -1)), tuple(range(6, 12))]+[(k, (k+1) % 6, 6+(k+1) % 6, 6+k) for k in range(6)]
    return vs, fs


def sector_mesh(p):
    vs, fs = [], []; n = 16
    for i in range(n+1):
        t = p['a0']+(p['a1']-p['a0'])*i/n
        for x in (p['x0'], p['x1']):
            for r in (p['r0'], p['r1']):
                vs.append((x, r*math.cos(t), r*math.sin(t)))
    idx = lambda i, xi, ri: i*4+xi*2+ri
    for i in range(n):
        j = i+1
        fs += [(idx(i, 0, 1), idx(j, 0, 1), idx(j, 1, 1), idx(i, 1, 1)), (idx(i, 0, 0), idx(i, 1, 0), idx(j, 1, 0), idx(j, 0, 0)),
               (idx(i, 0, 0), idx(j, 0, 0), idx(j, 0, 1), idx(i, 0, 1)), (idx(i, 1, 0), idx(i, 1, 1), idx(j, 1, 1), idx(j, 1, 0))]
    fs += [(idx(0, 0, 0), idx(0, 0, 1), idx(0, 1, 1), idx(0, 1, 0))[::-1], (idx(n, 0, 0), idx(n, 0, 1), idx(n, 1, 1), idx(n, 1, 0))]
    return vs, fs


def loft_mesh(profile, cy=0.0, cz=0.0, n=40):
    vs, fs = [], []
    for x, r in profile:
        for i in range(n):
            t = 2*math.pi*i/n; vs.append((x, cy+r*math.cos(t), cz+r*math.sin(t)))
    for k in range(len(profile)-1):
        for i in range(n):
            fs.append((k*n+i, k*n+(i+1) % n, (k+1)*n+(i+1) % n, (k+1)*n+i))
    vs += [(profile[0][0], cy, cz), (profile[-1][0], cy, cz)]; c0, c1 = len(vs)-2, len(vs)-1
    fs += [(c0, (i+1) % n, i) for i in range(n)]+[(c1, (len(profile)-1)*n+i, (len(profile)-1)*n+(i+1) % n) for i in range(n)]
    return vs, fs


def new_mesh(name, vs, fs, coll, material):
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.validate(); me.update()
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    for poly in me.polygons:
        poly.use_smooth = False
    me.materials.append(material)
    ob = bpy.data.objects.new(name, me); coll.objects.link(ob)
    return ob


def new_tube(name, points, radius, coll, material):
    cu = bpy.data.curves.new(name+'_Curve', 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = radius; cu.bevel_resolution = 3; cu.use_fill_caps = True
    sp = cu.splines.new('POLY'); sp.points.add(len(points)-1)
    for p_, co in zip(sp.points, points):
        p_.co = (*co, 1)
    cu.materials.append(material)
    ob = bpy.data.objects.new(name, cu); coll.objects.link(ob)
    return ob


def in_cut(point, cut):
    if not cut:
        return False
    a_ = math.atan2(point[2], point[1]); c0, c1 = cut
    return 0 <= math.remainder(a_-c0, 2*math.pi) <= c1-c0 and math.hypot(point[1], point[2]) > .4


def build_part(p, coll, cut=None, suffix=''):
    sh = p['shape']; func = p['func']
    if func == 'VIS':
        m = VIS_MATS.get(p.get('state', 'field'))
    else:
        m = mat(func)
    name = p['name']+suffix
    if sh == 'ring':
        cc = None if (p.get('cy', 0) or p.get('cz', 0)) else cut
        if cut and (p.get('cy', 0) or p.get('cz', 0)) and in_cut((0, p['cy'], p['cz']), cut):
            return None
        vs, fs = ring_mesh(p['x0'], p['x1'], p['r0'], p['r1'], p.get('cy', 0.0), p.get('cz', 0.0), p.get('segments', 1), p.get('gap_deg', 0.0), p.get('phase_deg', 0.0), cc)
        if not fs:
            return None
        ob = new_mesh(name, vs, fs, coll, m)
    elif sh == 'torus':
        if cut and in_cut(p['center'], cut) and abs(p['axis'][0]) < .99:
            return None
        if cut and abs(p['axis'][0]) > .99 and not (p['center'][1] or p['center'][2]):
            vs, fs = ring_mesh(p['center'][0]-p['tube'], p['center'][0]+p['tube'], p['radius']-p['tube'], p['radius']+p['tube'], cut=cut)
        else:
            if cut and in_cut(p['center'], cut):
                return None
            vs, fs = torus_mesh(p['center'], p['axis'], p['radius'], p['tube'])
        ob = new_mesh(name, vs, fs, coll, m)
    elif sh == 'box':
        if cut and in_cut(p['center'], cut):
            return None
        ob = new_mesh(name, *box_mesh(p['center'], p['size'], p['frame']), coll, m)
    elif sh == 'hexcell':
        if cut and in_cut(p['center'], cut):
            return None
        ob = new_mesh(name, *hex_mesh(p['center'], p['normal'], p['radius'], p['height']), coll, m)
    elif sh == 'sector':
        if cut and in_cut(fg.polar(p['x0'], p['r0'], (p['a0']+p['a1'])/2), cut):
            return None
        ob = new_mesh(name, *sector_mesh(p), coll, m)
    elif sh == 'loft':
        ob = new_mesh(name, *loft_mesh(p['profile'], p.get('cy', 0.0), p.get('cz', 0.0)), coll, m)
    elif sh == 'tube':
        mid = p['points'][len(p['points'])//2]
        if cut and in_cut(mid, cut):
            return None
        ob = new_tube(name, p['points'], p['radius'], coll, m)
    else:
        raise ValueError(sh)
    lab, rgba, _ = fg.PALETTE[func]
    ob.color = rgba; ob['fiji_function'] = lab; ob['role'] = p.get('role', ''); ob['wf_status'] = 'PROTOTYPE (lab/variants/fiji-drive revision, owner review pending)'
    ob['wf_owner'] = 'work.fiji_drive'
    return ob


def collections(top):
    out = {}
    root = bpy.data.collections.new('PROPULSION_FIJI_DRIVE'); top.children.link(root); root.color_tag = 'COLOR_07'
    for key, (name, func) in fg.COLLECTIONS.items():
        c = bpy.data.collections.new(f'FIJI_{name}'); root.children.link(c); c.color_tag = fg.PALETTE[func][2]
        out[key] = c
    va = bpy.data.collections.new('FIJI_12_VIS_ACTIVE_STATE'); va.color_tag = 'COLOR_05'   # linked into the ACTIVE scene only
    vf = bpy.data.collections.new('FIJI_12_VIS_FIELD_LINES'); out['12'].children.link(vf); vf.color_tag = 'COLOR_05'
    out['active'] = va; out['field'] = vf
    return root, out


def roots(colls):
    """One parent empty per collection (engines: at the engine inlet centre) so each assembly moves as a unit."""
    out = {}
    axes = fg.engine_axes(s)
    for key, (name, func) in fg.COLLECTIONS.items():
        e = bpy.data.objects.new(f'FIJI_ROOT_{name}', None); e.empty_display_type = 'PLAIN_AXES'; e.empty_display_size = 1.0
        if key in ('05', '06', '07', '08'):
            cy, cz = axes[int(key)-5]; e.location = (ST['inlet'], cy, cz); e.empty_display_type = 'ARROWS'
        colls[key].objects.link(e); out[key] = e
    return out


def build(parts, colls, parents, cut=None, suffix=''):
    made = []
    for p in parts:
        coll = colls[p['coll']]
        if p['func'] == 'VIS':
            coll = colls['active'] if p.get('state') == 'active' else colls['field']
        ob = build_part(p, coll, cut, suffix)
        if ob is None:
            continue
        par = parents.get(p['coll']) if parents else None
        if par is not None:
            ob.parent = par; ob.matrix_parent_inverse = Matrix.Translation(par.location).inverted()
        made.append(ob)
    return made


def glow_overlays(parts, colls):
    """Active state: thin emissive shells on the energised Fiji lattice cells and on the coil bores (display, in VIS_ACTIVE_STATE)."""
    lat = mat('LATTICE', emit=(.72, .45, 1.0), strength=6.0); coil = mat('COIL', emit=(.35, .6, 1.0), strength=2.0)
    for p in parts:
        if p['shape'] == 'hexcell' and p['func'] == 'LATTICE':
            q = dict(p, name=p['name']+'_ENERGISED', height=.012, radius=p['radius']*.72,
                     center=fg.add(p['center'], fg.mul(fg.norm(p['normal']), p['height']+.002)))
            ob = new_mesh(q['name'], *hex_mesh(q['center'], q['normal'], q['radius'], q['height']), colls['active'], lat)
            ob.color = fg.PALETTE['VIS'][1]
        elif p['shape'] == 'ring' and p['func'] == 'COIL':
            vs, fs = ring_mesh(p['x0']+.02, p['x1']-.02, p['r0']-.012, p['r0']-.002, p.get('cy', 0.0), p.get('cz', 0.0))
            ob = new_mesh(p['name']+'_ENERGISED', vs, fs, colls['active'], coil); ob.color = fg.PALETTE['VIS'][1]


# ------------------------------------------------------------------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene; scene.name = 'FIJI_DRIVE'
after = append(SHIP, 'WF_WAYFARER_001'); after.name = 'WORK_FIJI_SHIP_main_5a913f9_revised'
make_all_local()
hp.dress(s, functional=True, emit=False, grammar=True)
hidden, cut_objs = supersede([after])
top = bpy.data.collections.new('WORK_FIJI_DRIVE'); scene.collection.children.link(top); top.color_tag = 'COLOR_07'
top.children.link(after); hide_helpers(after)

VIS_MATS = {'active': mat('PLASMA', emit=(.55, .75, 1.0), strength=1.6, alpha=.35), 'field': mat('PLASMA', emit=(.2, .85, .95), strength=.6)}
P = fg.parts(s, prm)
drive_root, colls = collections(top)
parents = roots(colls)
build(P, colls, parents)
glow_overlays(P, colls)

# cutaway: the drive alone, wedge toward the camera removed
cut_scene = bpy.data.scenes.new('FIJI_DRIVE_CUTAWAY')
cut_top = bpy.data.collections.new('WORK_FIJI_DRIVE_CUTAWAY'); cut_top.color_tag = 'COLOR_07'; cut_scene.collection.children.link(cut_top)
ccolls = {k: bpy.data.collections.new(f'FIJI_CUT_{v[0]}') for k, v in fg.COLLECTIONS.items()}
for k, c in ccolls.items():
    cut_top.children.link(c); c.color_tag = fg.PALETTE[fg.COLLECTIONS[k][1]][2]
ccolls['active'] = ccolls['12']; ccolls['field'] = ccolls['12']
CUT = (math.radians(-35), math.radians(80))
build([p for p in P if not (p['func'] == 'VIS' and (p.get('state') == 'field' or p['name'].endswith('_VIS_EXHAUST')))], ccolls, None, cut=CUT, suffix='_CUT')

# systems sheet: each functional collection instanced on its own cell
sys_scene = bpy.data.scenes.new('FIJI_DRIVE_SYSTEMS')
sheet = bpy.data.collections.new('WORK_FIJI_DRIVE_SYSTEMS_SHEET'); sheet.color_tag = 'COLOR_07'; sys_scene.collection.children.link(sheet)
cells = [('ASSEMBLY', None), ('00', ['00']), ('01', ['01']), ('02', ['02']), ('03', ['03']), ('04', ['04']), ('ENGINES', ['05', '06', '07', '08']),
         ('09', ['09']), ('10', ['10']), ('11', ['11'])]
SHEET = []
for i, (label, keys) in enumerate(cells):
    col, row = i % 3, i//3; off = Vector((col*42.0, -row*15.5, 0))
    targets = [drive_root] if keys is None else [colls[k] for k in keys]
    for t in targets:
        e = bpy.data.objects.new(f'SHEET_{label}_{t.name}', None); e.instance_type = 'COLLECTION'; e.instance_collection = t
        e.location = off; sheet.objects.link(e)
    SHEET.append((label, off))

# BEFORE scene
scenes = [scene]
active_scene = scene.copy() if False else None
act = bpy.data.scenes.new('FIJI_DRIVE_ACTIVE'); act.collection.children.link(top); act.collection.children.link(colls['active'])
scenes.append(act)
if not a.no_before:
    before = append(SHIP, 'WF_WAYFARER_001'); before.name = 'WORK_FIJI_BEFORE_SHIP_main_5a913f9'
    make_all_local()
    bscene = bpy.data.scenes.new('BEFORE_MAIN_5A913F9'); btop = bpy.data.collections.new('WORK_FIJI_BEFORE'); btop.color_tag = 'COLOR_07'
    bscene.collection.children.link(btop); btop.children.link(before); hide_helpers(before); scenes.append(bscene)
scenes += [cut_scene, sys_scene]


def set_vis(sc, name, visible):
    def walk(lc):
        if lc.collection.name == name:
            lc.exclude = not visible; return True
        return any(walk(ch) for ch in lc.children)
    for vl in sc.view_layers:
        walk(vl.layer_collection)



# lights and render settings
sun = bpy.data.lights.new('Review_Sun', 'SUN'); sun.energy = 3.2; sun.angle = math.radians(.5)
so = bpy.data.objects.new('Review_Sun', sun); so.rotation_euler = (-Vector((-.55, .62, .55)).normalized()).to_track_quat('-Z', 'Y').to_euler()
fill = bpy.data.lights.new('Review_Fill', 'SUN'); fill.energy = .55; fill.angle = math.radians(8)
fo = bpy.data.objects.new('Review_Fill', fill); fo.rotation_euler = (-Vector((.4, -.7, -.3)).normalized()).to_track_quat('-Z', 'Y').to_euler()
for sc in scenes:
    sc.world = bpy.data.worlds.get('WF_Space') or bpy.data.worlds.new('WF_Space'); sc.world.use_nodes = True
    bg = next(n for n in sc.world.node_tree.nodes if n.type == 'BACKGROUND'); bg.inputs['Color'].default_value = (.004, .004, .006, 1); bg.inputs['Strength'].default_value = 1
    sc.collection.objects.link(so); sc.collection.objects.link(fo)
    sc.render.engine = 'CYCLES'; sc.cycles.samples = a.samples; sc.cycles.use_denoising = True; sc.cycles.device = 'CPU'
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.exposure = 0.3
    sc.render.resolution_x, sc.render.resolution_y = a.size


def camera(name, loc, look, lens, ortho=None):
    cam = bpy.data.cameras.new(name); ob = bpy.data.objects.new(name, cam)
    ob.location = loc; ob.rotation_euler = (Vector(look)-Vector(loc)).to_track_quat('-Z', 'Z' if abs((Vector(look)-Vector(loc)).normalized().z) < .95 else 'Y').to_euler()
    cam.lens = lens; cam.clip_start = 0.1; cam.clip_end = 6000
    if ortho:
        cam.type = 'ORTHO'; cam.ortho_scale = ortho
    return ob


xd = (ST['exit']+ST['shield_fwd'])/2; cy1, cz1 = fg.engine_axes(s)[0]
CAMS = {
    'CAM_FIJI_WHOLE': (camera('CAM_FIJI_WHOLE', (-330, 205, 120), (-20, 0, 0), 35), [scene, act, 'BEFORE_MAIN_5A913F9']),
    'CAM_FIJI_ASSEMBLY': (camera('CAM_FIJI_ASSEMBLY', (-172, 34, 22), (-128.5, 0, 0), 32), [scene, act, 'BEFORE_MAIN_5A913F9']),
    'CAM_FIJI_CORE': (camera('CAM_FIJI_CORE', (-125.5, -4.0, 14.0), (-118.6, 0, 0.5), 24), [scene, act, 'BEFORE_MAIN_5A913F9']),
    'CAM_FIJI_ENGINE': (camera('CAM_FIJI_ENGINE', (-150.5, cy1+8.5, cz1+5.0), (-140.5, cy1, cz1), 30), [scene, act]),
    'CAM_FIJI_REAR': (camera('CAM_FIJI_REAR', (-185, 0.01, 0), (-140, 0, 0), 50), [scene, act, 'BEFORE_MAIN_5A913F9']),
    'CAM_FIJI_OVERVIEW': (camera('CAM_FIJI_OVERVIEW', (xd, 0.01, 80), (xd, 0, 0), 50, ortho=40), [scene]),
    'CAM_FIJI_CUTAWAY': (camera('CAM_FIJI_CUTAWAY', (-141, 30, 12), (-127.5, 0, 0), 30), ['FIJI_DRIVE_CUTAWAY']),
    'CAM_FIJI_SYSTEMS': (camera('CAM_FIJI_SYSTEMS', (xd+42, -23.25, 120), (xd+42, -23.25, 0), 50, ortho=132), ['FIJI_DRIVE_SYSTEMS']),
}
CAMS['CAM_FIJI_OVERVIEW'][0].rotation_euler = (0, 0, 0)
CAMS['CAM_FIJI_SYSTEMS'][0].rotation_euler = (0, 0, 0)
for name, (ob, scs) in CAMS.items():
    scs[:] = [bpy.data.scenes.get(sc) if isinstance(sc, str) else sc for sc in scs]
    scs[:] = [sc for sc in scs if sc is not None]
    ob['render_scenes'] = [sc.name for sc in scs]
    for sc in scs:
        sc.collection.objects.link(ob)
for sc, cam in ((scene, 'CAM_FIJI_ASSEMBLY'), (act, 'CAM_FIJI_ASSEMBLY'), (cut_scene, 'CAM_FIJI_CUTAWAY'), (sys_scene, 'CAM_FIJI_SYSTEMS')):
    sc.camera = CAMS[cam][0]
if 'BEFORE_MAIN_5A913F9' in bpy.data.scenes:
    bpy.data.scenes['BEFORE_MAIN_5A913F9'].camera = CAMS['CAM_FIJI_ASSEMBLY'][0]

# sheet labels (text objects, systems sheet only)
for label, off in SHEET:
    name = 'FULL ASSEMBLY' if label == 'ASSEMBLY' else (fg.COLLECTIONS[label][0][3:].replace('_', ' ') if label in fg.COLLECTIONS else 'ENGINES (4, shared design)')
    tc = bpy.data.curves.new(f'SHEET_LABEL_{label}', 'FONT'); tc.body = name; tc.size = 1.6; tc.align_x = 'LEFT'
    to = bpy.data.objects.new(f'SHEET_LABEL_{label}', tc); to.location = off+Vector((ST['exit']-1, 6.6, 8)); sheet.objects.link(to)
    to.data.materials.append(mat('DIAGNOSTIC', emit=(1, 1, 1), strength=3.0))

readme = bpy.data.texts.new('README_FIJI_DRIVE')
readme.write((HERE/'NOTES.md').read_text() if (HERE/'NOTES.md').exists() else 'Fiji Drive revision\n')
readme.write('\n\n## Hidden in this file (superseded by the revision, not deleted)\n\n'+', '.join(sorted(set(hidden)))+'\n\n## Cut aft of the shadow shield (open reactor bay)\n\n'+', '.join(cut_objs)+'\n')
legend = bpy.data.texts.new('FIJI_DRIVE_COLOR_LEGEND')
legend.write('\n'.join(f'{k}: {v[0]}  RGBA {tuple(round(c, 2) for c in v[1])}  collection tag {v[2]}' for k, v in fg.PALETTE.items()))

if a.render:
    a.render.mkdir(parents=True, exist_ok=True)
    for name, (ob, scs) in CAMS.items():
        if a.cams and name not in a.cams:
            continue
        for sc in scs:
            sc.camera = ob
            if name in ('CAM_FIJI_OVERVIEW', 'CAM_FIJI_SYSTEMS'):
                sc.render.engine = 'BLENDER_WORKBENCH'; sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'OBJECT'
                sh.show_cavity = True; sh.show_object_outline = True; sh.background_type = 'VIEWPORT'
                sc.display_settings.display_device = 'sRGB'; sc.view_settings.view_transform = 'Standard'
            tag = {'FIJI_DRIVE': '', 'FIJI_DRIVE_ACTIVE': '__active', 'BEFORE_MAIN_5A913F9': '__before_main'}.get(sc.name, '')
            sc.render.filepath = str(a.render/f'{name}{tag}.png')
            bpy.ops.render.render(write_still=True, scene=sc.name)
            print('WF_RENDER', sc.render.filepath, flush=True)
            if name in ('CAM_FIJI_OVERVIEW', 'CAM_FIJI_SYSTEMS'):
                sc.render.engine = 'CYCLES'; sc.view_settings.view_transform = 'AgX'
    for sc, cam in ((scene, 'CAM_FIJI_ASSEMBLY'), (act, 'CAM_FIJI_ASSEMBLY')):
        sc.camera = CAMS[cam][0]
else:
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == 'VIEW_3D':
                for sp in area.spaces:
                    if sp.type == 'VIEW_3D':
                        sp.shading.type = 'SOLID'; sp.shading.color_type = 'OBJECT'; sp.clip_end = 6000; sp.clip_start = .1
                        sp.region_3d.view_perspective = 'CAMERA'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(a.out), compress=True)
    print('WF_REVIEW saved', a.out, flush=True)
