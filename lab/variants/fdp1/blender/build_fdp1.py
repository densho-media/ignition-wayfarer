"""Build the FDP-1 review file: the full Wayfarer with the FDP-1 pulsed drive attached, in its own scenes and collections.
Study helper; nothing in src/ reads it. The engineering record is computed here by the same package run.py uses (one pipeline).

  /snap/bin/blender -b --factory-startup --python-exit-code 1 --python lab/variants/fdp1/blender/build_fdp1.py -- \
      [--variant baseline] [--out lab/variants/fdp1/REVIEW_FDP1.blend] [--render DIR] [--cams ...] [--size W H] [--no-save]

Scenes
  FDP1_WAYFARER        built ship (assets/wayfarer, unchanged on disk) + WORK_FDP1 (00..12 collections). Superseded four-nozzle drive
                       objects are hidden, never deleted; with tank layout T-B the bow assembly is moved forward in this file only.
  FDP1_CUTAWAY         the FDP-1 aft assembly alone, a wedge removed toward the camera
  BASELINE_WAYFARER    the untouched built ship (four-nozzle drive)
  COMPARE_PROPULSION   baseline ship above, FDP-1 ship below, same scale
  COMPARE_TANKS        existing 13-vessel farm against the FDP-1 farm (existing + proposed added vessels)
  FDP1_ENERGY_FLOW     the energy-flow diagram (packed image) if diagrams/energy_flow.png exists
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
FDP = HERE.parent
ROOT = FDP.parents[2]
sys.path[:0] = [str(FDP), str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation')]
from engineering import config, model, geometry as G   # noqa: E402
import functional_colors as fc                          # noqa: E402

a = argparse.ArgumentParser()
a.add_argument('--variant', default='baseline'); a.add_argument('--out', type=Path, default=FDP/'REVIEW_FDP1.blend')
a.add_argument('--render', type=Path); a.add_argument('--cams', nargs='+'); a.add_argument('--size', type=int, nargs=2, default=(1920, 1080))
a.add_argument('--no-save', action='store_true'); a.add_argument('--no-ship', action='store_true')
a = a.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])

cfg = config.load(a.variant)
R = model.solve(cfg)
if not R.get('converged'):
    raise SystemExit(f"FDP-1 variant {a.variant} does not close: {R.get('reason')} (see results); nothing to draw")
SHIP = ROOT/'assets/wayfarer/WF_WAYFARER_001.blend'
s = config.spec()
PALETTE = dict(fc.PALETTE)
for k, rgba in G.VIS.items():
    PALETTE['VIS_'+k] = (k.title(), rgba, 'COLOR_07')

# ----------------------------------------------------------------------------------------------------------------------------------
# meshes
# ----------------------------------------------------------------------------------------------------------------------------------


def seg_count(span_rad, radius, step=1.2, lo=8, hi=192):
    return max(lo, min(hi, int(abs(span_rad)*max(radius, 0.5)/step)))


def arc_range(p, cut):
    a0, a1 = p.get('arc') or (0.0, 360.0)
    full = p.get('arc') is None
    if cut:
        c0, c1 = cut
        if full:
            return [(c1, c0+360.0)], False
        out = []
        lo, hi = a0, a1
        # remove [c0, c1] from [lo, hi] (degrees, same branch)
        for s0, s1 in ((lo, min(hi, c0)), (max(lo, c1), hi)):
            if s1-s0 > 0.5:
                out.append((s0, s1))
        return out, False
    return [(a0, a1)], full


def rev_mesh(profile, arcs, closed):
    """Solid of revolution about X from a closed (x, r) polygon, over each arc (degrees)."""
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
        idx = lambda i, j: base+(i % cnt)*m+(j % m)
        for i in range(n):
            for j in range(m):
                fs.append((idx(i, j), idx(i+1, j), idx(i+1, j+1), idx(i, j+1)))
        if not closed:
            for i, rev in ((0, True), (n, False)):
                f = [idx(i, j) for j in range(m)]
                fs.append(tuple(reversed(f)) if rev else tuple(f))
    return vs, fs


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


def sphere_mesh(c, r, nu=24, nv=12):
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


MATS = {}


def mat(func, alpha=1.0, emit=0.0):
    key = (func, round(alpha, 3), emit)
    if key in MATS:
        return MATS[key]
    rgba = PALETTE.get(func, ('', (.8, .8, .8, 1), ''))[1]
    m = bpy.data.materials.new(f'FDP1_{func}'+(f'_A{alpha:g}' if alpha < 1 else '')+(f'_E{emit:g}' if emit else ''))
    m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    base = tuple(0.35+0.4*x for x in rgba[:3]) if func in ('STRUCTURE',) else rgba[:3]
    b.inputs['Base Color'].default_value = (*base, 1); b.inputs['Metallic'].default_value = 0.5; b.inputs['Roughness'].default_value = 0.45
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


def new_obj(name, vs, fs, coll):
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.validate(); me.update()
    ob = bpy.data.objects.new(name, me); coll.objects.link(ob)
    return ob


def text_obj(name, p, coll):
    cu = bpy.data.curves.new(name, 'FONT'); cu.body = p['body']; cu.size = p['size']; cu.align_x = 'CENTER'
    ob = bpy.data.objects.new(name, cu); coll.objects.link(ob); ob.location = p['location']
    ob.rotation_euler = (math.radians(90), 0, 0) if p.get('facing', 'side') == 'side' else (0, 0, 0)
    return ob


def build_part(p, coll, cut=None, suffix=''):
    sh = p['shape']; name = p['name']+suffix
    if cut and sh in ('box', 'tube', 'panel', 'capsule', 'sphere', 'text'):
        c = p.get('centre') or p.get('location') or (p['points'][len(p['points'])//2] if 'points' in p else p['corners'][0] if 'corners' in p else (0, 0, 0))
        if sh == 'capsule':
            c = (0.0, *p['centre'])
        az = math.degrees(math.atan2(c[2], c[1])) % 360 if math.hypot(c[1], c[2]) > 0.5 else None
        if az is not None and cut[0] <= az <= cut[1]:
            return None
    if sh == 'ring':
        cy, cz = p.get('centre', (0.0, 0.0))
        prof = [(p['x0'], p['r0']), (p['x1'], p['r0']), (p['x1'], p['r1']), (p['x0'], p['r1'])] if p['r0'] > 0 else [(p['x0'], 0.0), (p['x1'], 0.0), (p['x1'], p['r1']), (p['x0'], p['r1'])]
        arcs, closed = arc_range(p, cut if (cy, cz) == (0.0, 0.0) else None)
        vs, fs = rev_mesh(prof, arcs, closed)
        vs = [(x, y+cy, z+cz) for x, y, z in vs]
    elif sh == 'frustum':
        ri0, ri1 = p.get('ri0'), p.get('ri1')
        if ri0 is None:
            prof = [(p['x0'], 0.0), (p['x1'], 0.0), (p['x1'], p['r1']), (p['x0'], p['r0'])]
        else:
            prof = [(p['x0'], ri0), (p['x1'], ri1), (p['x1'], p['r1']), (p['x0'], p['r0'])]
        arcs, closed = arc_range(p, cut)
        vs, fs = rev_mesh(prof, arcs, closed)
    elif sh == 'torus':
        nvv = 10; prof = [(p['x']+p['a']*math.cos(2*math.pi*j/nvv), p['R']+p['a']*math.sin(2*math.pi*j/nvv)) for j in range(nvv)]
        arcs, closed = arc_range(p, cut)
        vs, fs = rev_mesh(prof, arcs, closed)
    elif sh == 'sphere':
        vs, fs = sphere_mesh(p['centre'], p['radius'])
    elif sh == 'box':
        vs, fs = box_mesh(p['centre'], p['size'], p.get('roll', 0.0))
    elif sh == 'tube':
        vs, fs = tube_mesh(p['points'], p['radius'])
    elif sh == 'panel':
        vs, fs = panel_mesh(p['corners'], p['thickness'])
    elif sh == 'capsule':
        cy, cz = p['centre']; r = p['radius']; L = p['x1']-p['x0']
        prof = [(p['x0']+r*(1-math.cos(math.pi/2*k/6)), r*math.sin(math.pi/2*k/6)) for k in range(7)]
        prof += [(p['x1']-r*(1-math.cos(math.pi/2*k/6)), r*math.sin(math.pi/2*k/6)) for k in reversed(range(7))]
        prof = [(x, max(rr, 1e-3)) for x, rr in prof]+[(p['x1'], 0.0), (p['x0'], 0.0)]
        prof = [(p['x0'], 0.0)]+prof[1:-2]+[(p['x1'], 0.0)]
        vs, fs = rev_mesh(prof, [(0.0, 360.0)], True)
        vs = [(x, y+cy, z+cz) for x, y, z in vs]
    elif sh == 'text':
        ob = text_obj(name, p, coll)
        ob.data.materials.append(mat('SERVICE', emit=2.0)); ob.color = (0.98, 0.95, 0.85, 1)
        return ob
    else:
        raise ValueError(sh)
    if not fs:
        return None
    ob = new_obj(name, vs, fs, coll)
    func = p['func']; rgba = PALETTE.get(func, ('', (.8, .8, .8, 1), ''))[1]
    emit = 3.0 if func in ('VIS_PLASMA', 'VIS_BEAM') and p['alpha'] >= 0.5 else 0.0
    ob.data.materials.append(mat(func, p['alpha'], emit))
    ob.color = (*rgba[:3], p['alpha'])
    ob['fdp1_function'] = PALETTE.get(func, (func,))[0]; ob['fdp1_status'] = p['status']; ob['wf_owner'] = 'work.fdp1'
    ob['wf_status'] = 'PROTOTYPE (lab/variants/fdp1, research prototype, not canon)'
    if p.get('note'):
        ob['fdp1_note'] = p['note']
    if p['alpha'] < 1:
        ob.show_transparent = True
    return ob


def make_collections(top, prefix=''):
    out = {}
    for key, (name, func) in G.COLLECTIONS.items():
        c = bpy.data.collections.new(prefix+name); top.children.link(c)
        c.color_tag = PALETTE.get(func, ('', '', 'NONE'))[2] if func in PALETTE else 'NONE'
        out[key] = c
    for opt in R['tanks']['options']:
        c = bpy.data.collections.new(prefix+f'FDP1_10_TANKS_{opt.replace("-", "")}_'+{'T-A': 'AFT_STACK', 'T-B': 'FORWARD_STRETCH', 'T-C': 'OUTER_RING'}[opt])
        out['10'].children.link(c); c.color_tag = 'COLOR_06'; out['10:'+opt] = c
    return out


def build(parts, colls, cut=None, suffix=''):
    made = []
    for p in parts:
        ob = build_part(p, colls[p['coll']], cut, suffix)
        if ob is not None:
            made.append(ob)
    return made


def set_excluded(sc, names, excluded=True):
    def walk(lc):
        if lc is None:
            return
        if lc.collection.name in names:
            lc.exclude = excluded
        for ch in lc.children:
            walk(ch)
    for vl in sc.view_layers:
        walk(vl.layer_collection)

# ----------------------------------------------------------------------------------------------------------------------------------
# ship
# ----------------------------------------------------------------------------------------------------------------------------------


def append_ship():
    with bpy.data.libraries.load(str(SHIP), link=False) as (src, dst):
        dst.collections = ['WF_WAYFARER_001']
    c = dst.collections[0]
    for _ in range(6):
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
    for ch in c.children_recursive:
        if ch.name.split('.')[0] in ('40_SIM_RIG', '30_CAMERAS', '20_HUMAN_SCALE'):
            ch.hide_viewport = True; ch.hide_render = True
    return c


def instance_targets(ship):
    """Collections instanced by the ship's assembly empties (name -> instancing empty)."""
    out = {}
    for o in ship.all_objects:
        if o is not None and o.instance_type == 'COLLECTION' and o.instance_collection:
            out.setdefault(o.instance_collection.name, []).append(o)
    return out


SUPERSEDED_INSTANCES = ('Nozzle_0', 'DRIVE_DEBUG_', 'Assembly_PROPULSION', 'Assembly_SHIELDING')


def supersede(ship):
    hidden = []
    for o in ship.all_objects:
        if o is None:
            continue
        if o.name.split('.')[0].startswith(SUPERSEDED_INSTANCES):
            o.hide_viewport = o.hide_render = True; hidden.append(o.name)
    return hidden


def bow_stretch(ship, dx, x_from):
    """T-B: move every bow object (bounding box entirely ahead of x_from) forward by dx, in this file only."""
    moved = []
    seen = set()
    inst = instance_targets(ship)
    colls = [ship]+[c for name, es in inst.items() for c in [bpy.data.collections[name]]]
    for c in colls:
        for o in c.all_objects:
            if o is None or o.name in seen or o.type not in ('MESH', 'CURVE', 'EMPTY', 'FONT') or o.instance_type == 'COLLECTION':
                continue
            seen.add(o.name)
            if o.parent is not None:
                continue
            if o.type == 'EMPTY':
                continue
            bb = [o.matrix_world @ Vector(v) for v in o.bound_box]
            if min(v.x for v in bb) >= x_from:
                o.location.x += dx; moved.append(o.name)
    return moved


# ----------------------------------------------------------------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene; scene.name = 'FDP1_WAYFARER'
top = bpy.data.collections.new('WORK_FDP1'); scene.collection.children.link(top); top.color_tag = 'COLOR_07'
hidden, moved = [], []
ship = None
if not a.no_ship:
    ship = append_ship(); ship.name = 'WORK_FDP1_SHIP_main'
    top.children.link(ship)
    hidden = supersede(ship)
    if R['tanks']['selected'] == 'T-B':
        moved = bow_stretch(ship, R['tanks']['options']['T-B']['added_length_m'], max(t['x1'] for t in R['tanks']['existing'])+0.05)
colls = make_collections(top)
PARTS = G.parts(R); TANKS = G.tank_parts(R); LABELS = G.labels(R)
build(PARTS+TANKS+LABELS, colls)
for opt in R['tanks']['options']:
    if opt != R['tanks']['selected']:
        set_excluded(scene, [colls['10:'+opt].name])

# cutaway scene: the aft assembly, a wedge removed toward the camera (-Y side)
cut_scene = bpy.data.scenes.new('FDP1_CUTAWAY')
cut_top = bpy.data.collections.new('WORK_FDP1_CUTAWAY'); cut_top.color_tag = 'COLOR_07'; cut_scene.collection.children.link(cut_top)
ccolls = make_collections(cut_top, 'CUT_')
aft = [p for p in PARTS if not p['name'].startswith(('FDP1_Wing_', 'FDP1_Shadow_Cone', 'FDP1_Low_Loop', 'FDP1_Feed_Line', 'FDP1_KeepOut_Plume'))]
build(aft, ccolls, cut=(120.0, 240.0), suffix='_CUT')

scenes = [scene, cut_scene]
base_scene = None
if not a.no_ship:
    base = append_ship(); base.name = 'BASELINE_WAYFARER_SHIP_main'
    base_scene = bpy.data.scenes.new('BASELINE_WAYFARER'); bt = bpy.data.collections.new('BASELINE_WAYFARER'); bt.color_tag = 'NONE'
    base_scene.collection.children.link(bt); bt.children.link(base); scenes.append(base_scene)
    # side-by-side propulsion comparison by collection instances
    cmp = bpy.data.scenes.new('COMPARE_PROPULSION'); scenes.append(cmp)
    fdp_all = bpy.data.collections.new('COMPARE_FDP1_ASSEMBLY')
    fdp_all.children.link(ship)
    for k in ('00', '01', '02', '03', '04', '05', '06', '07', '08', '09', '10:'+R['tanks']['selected']):
        fdp_all.children.link(colls[k])
    for nm, coll, z in (('CMP_BASELINE', base, 150.0), ('CMP_FDP1', fdp_all, -40.0)):
        e = bpy.data.objects.new(nm, None); e.instance_type = 'COLLECTION'; e.instance_collection = coll; e.location = (0, 0, z)
        cmp.collection.objects.link(e)
    for body, x, z in (('BASELINE: four-nozzle drive (main, unchanged)', -300.0, 150.0+45.0), ('FDP-1: pulsed D-He3, one Fiji magnetic nozzle', -90.0, -40.0+45.0)):
        cu = bpy.data.curves.new('CMP_LABEL', 'FONT'); cu.body = body; cu.size = 12; cu.align_x = 'LEFT'
        t = bpy.data.objects.new('CMP_LABEL_'+body[:8], cu); t.location = (x, 0.0, z); t.rotation_euler = (math.radians(90), 0, 0)
        t.data.materials.append(mat('SERVICE', emit=2.0)); t.color = (1, 1, 1, 1); cmp.collection.objects.link(t)

# tank comparison
tk_scene = bpy.data.scenes.new('COMPARE_TANKS'); scenes.append(tk_scene)
tkc = bpy.data.collections.new('COMPARE_TANKS_FARMS'); tk_scene.collection.children.link(tkc); tkc.color_tag = 'COLOR_06'
ex = R['tanks']['existing']; x0e = min(t['x0'] for t in ex)
sel = R['tanks']['options'][R['tanks']['selected']]
for label, y0, vessels in (('CURRENT FARM: 13 vessels', -60.0, [(t, 1.0) for t in ex]),
                           (f"FDP-1 FARM: 13 existing + {sel['count']} proposed ({R['tanks']['selected']})", 60.0,
                            [(t, 0.45 if t['key'] == 'hydrogen' else 1.0) for t in ex]+[(t, 0.4) for t in sel['vessels']])):
    for t, alpha in vessels:
        p = {'name': 'CMP_'+t['name'], 'func': G.SPECIES_FUNC[t['key']], 'shape': 'capsule', 'x0': t['x0']-x0e, 'x1': t['x1']-x0e,
             'centre': (t['y']+y0, t['z']), 'radius': t['a_env'], 'alpha': alpha, 'status': 'ENGINEERED'}
        build_part(p, tkc)
    cu = bpy.data.curves.new('TK_LABEL', 'FONT'); cu.body = label; cu.size = 6; cu.align_x = 'LEFT'
    to = bpy.data.objects.new('TK_LABEL_'+label[:12], cu); to.location = (-10.0, y0-40.0, 0.0); tkc.objects.link(to)
    to.data.materials.append(mat('SERVICE', emit=2.0)); to.color = (1, 1, 1, 1)
tk = R['tanks']['summary']
note = (f"He-3 need {tk['required_m3']['helium_3']:,.0f} m3 vs {tk['existing_m3']['helium_3']:,.0f};  D2 {tk['required_m3']['deuterium']:,.0f} vs {tk['existing_m3']['deuterium']:,.0f};"
        f"  H2 idle {tk['idle_hydrogen_m3']:,.0f} m3")
cu = bpy.data.curves.new('TK_NOTE', 'FONT'); cu.body = note; cu.size = 4.5; cu.align_x = 'LEFT'
to = bpy.data.objects.new('TK_NOTE', cu); to.location = (-10.0, -120.0, 0.0); tkc.objects.link(to); to.data.materials.append(mat('SERVICE', emit=2.0)); to.color = (1, 1, 1, 1)

# energy flow diagram as a packed image plane
ef_scene = None
png = FDP/'diagrams'/f"energy_flow_{R['variant']}.png"
if png.exists():
    ef_scene = bpy.data.scenes.new('FDP1_ENERGY_FLOW'); scenes.append(ef_scene)
    img = bpy.data.images.load(str(png)); w, h = img.size
    m = bpy.data.materials.new('FDP1_ENERGY_FLOW_IMG'); m.use_nodes = True; nt = m.node_tree
    tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img; em = nt.nodes.new('ShaderNodeEmission'); out = nt.nodes['Material Output']
    nt.links.new(tex.outputs['Color'], em.inputs['Color']); nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    hh = 100.0*h/w
    me = bpy.data.meshes.new('FDP1_ENERGY_FLOW'); me.from_pydata([(-50, -hh/2, 0), (50, -hh/2, 0), (50, hh/2, 0), (-50, hh/2, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(); [setattr(uv.data[i], 'uv', c) for i, c in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)])]
    ob = bpy.data.objects.new('FDP1_ENERGY_FLOW', me); ob.data.materials.append(m); ef_scene.collection.objects.link(ob)

# ----------------------------------------------------------------------------------------------------------------------------------
# lights, world, cameras
# ----------------------------------------------------------------------------------------------------------------------------------
sun = bpy.data.lights.new('Review_Sun', 'SUN'); sun.energy = 3.0
so = bpy.data.objects.new('Review_Sun', sun); so.rotation_euler = (-Vector((-.55, .62, .55)).normalized()).to_track_quat('-Z', 'Y').to_euler()
world = bpy.data.worlds.new('FDP1_Space'); world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND'); bg.inputs['Color'].default_value = (.01, .012, .016, 1)
for sc in scenes:
    sc.world = world; sc.collection.objects.link(so)
    sc.render.engine = 'BLENDER_WORKBENCH'; shd = sc.display.shading
    shd.light = 'STUDIO'; shd.color_type = 'OBJECT'; shd.show_cavity = True; shd.show_object_outline = True; shd.background_type = 'WORLD'
    sc.view_settings.view_transform = 'Standard'; sc.render.resolution_x, sc.render.resolution_y = a.size
    sc.render.film_transparent = False
if bpy.data.scenes.get('COMPARE_PROPULSION'):
    bpy.data.scenes['COMPARE_PROPULSION'].display.shading.color_type = 'MATERIAL'
if ef_scene:
    ef_scene.display.shading.color_type = 'TEXTURE'; ef_scene.display.shading.light = 'FLAT'


def camera(name, loc, look, lens=35.0, ortho=None, up='Z', clip=30000.0):
    cam = bpy.data.cameras.new(name); ob = bpy.data.objects.new(name, cam)
    ob.location = loc; d = Vector(look)-Vector(loc)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y' if abs(d.normalized().z) > 0.95 else up).to_euler()
    cam.lens = lens; cam.clip_start = 0.5; cam.clip_end = clip
    if ortho:
        cam.type = 'ORTHO'; cam.ortho_scale = ortho
    return ob


lay = R['layout']; noz = R['nozzle']; L3 = noz['loops'][-1]
x_aft = L3['x']-3*lay['R_s']-30; x_bow = 145.0+(R['tanks']['options']['T-B']['added_length_m'] if R['tanks']['selected'] == 'T-B' else 0.0)
xm = (x_aft+x_bow)/2; span = x_bow-x_aft
wsel = R['thermal']['layouts'][R['thermal']['selected_layout']]; tip = wsel['tip_radius_m']
CAMS = {
    'CAM_01_SIDE_ELEVATION': (camera('CAM_01_SIDE_ELEVATION', (xm, -4000, 0), (xm, 0, 0), ortho=span*1.08), ['FDP1_WAYFARER']),
    'CAM_01b_PLAN_RADIATORS': (camera('CAM_01b_PLAN_RADIATORS', (xm, 0, 9000), (xm, 0, 0), ortho=max(2.2*tip, span)*1.05), ['FDP1_WAYFARER']),
    'CAM_02_PERSPECTIVE_WHOLE': (camera('CAM_02_PERSPECTIVE_WHOLE', (xm-0.9*tip, -1.6*tip, 0.9*tip), (xm, 0, 0), lens=35), ['FDP1_WAYFARER']),
    'CAM_02b_PERSPECTIVE_SHIP': (camera('CAM_02b_PERSPECTIVE_SHIP', (xm-420, -560, 300), (xm, 0, 0), lens=35), ['FDP1_WAYFARER', 'BASELINE_WAYFARER']),
    'CAM_03_AFT_ASSEMBLY': (camera('CAM_03_AFT_ASSEMBLY', (lay['x_burn']-260, -300, 170), (lay['x_burn']+20, 0, 0), lens=30), ['FDP1_WAYFARER']),
    'CAM_04_NOZZLE_CUTAWAY': (camera('CAM_04_NOZZLE_CUTAWAY', (lay['x_burn']-30, -360, 70), (lay['x_burn']-5, 0, 0), lens=35), ['FDP1_CUTAWAY']),
    'CAM_05_FUEL_AND_DRIVERS': (camera('CAM_05_FUEL_AND_DRIVERS', (lay['x_shield_fwd']-6, -34, 14), (lay['x_shield_fwd']+14, 0, 0), lens=24), ['FDP1_CUTAWAY']),
    'CAM_05b_DRIVER_GALLERIES': (camera('CAM_05b_DRIVER_GALLERIES', (lay['x_attach']-40, -60, 70), (lay['x_attach']+60, 0, 8), lens=28), ['FDP1_WAYFARER']),
    'CAM_06_SHIELDING_AND_ESCAPE': (camera('CAM_06_SHIELDING_AND_ESCAPE', (xm, -4000, 0), (xm, 0, 0), ortho=span*1.08), ['FDP1_WAYFARER']),
    'CAM_06b_SHIELD_CLOSE': (camera('CAM_06b_SHIELD_CLOSE', (lay['x_shield_aft']-40, -45, 20), (lay['x_shield_aft']+4, 0, 0), lens=30), ['FDP1_CUTAWAY']),
    'CAM_07_THERMAL_RADIATORS': (camera('CAM_07_THERMAL_RADIATORS', (xm-1.2*tip, -1.0*tip, 1.3*tip), (xm, 0, 0), lens=30), ['FDP1_WAYFARER']),
    'CAM_07b_RADIATOR_ROOTS': (camera('CAM_07b_RADIATOR_ROOTS', (xm-260, -420, 520), (xm-60, 0, 0), lens=30), ['FDP1_WAYFARER']),
    'CAM_08_COMPARE_PROPULSION': (camera('CAM_08_COMPARE_PROPULSION', ((x_aft+x_bow)/2, -3000, 55), ((x_aft+x_bow)/2, 0, 55), ortho=(x_bow-x_aft)*1.05), ['COMPARE_PROPULSION']),
    'CAM_09_COMPARE_TANKS': (camera('CAM_09_COMPARE_TANKS', (70, -150, 230), (70, 0, 0), lens=30), ['COMPARE_TANKS']),
}
if ef_scene:
    CAMS['CAM_10_ENERGY_FLOW'] = (camera('CAM_10_ENERGY_FLOW', (0, 0, 200), (0, 0, 0), ortho=104), ['FDP1_ENERGY_FLOW'])
for nm in ('CAM_01b_PLAN_RADIATORS', 'CAM_10_ENERGY_FLOW'):
    if nm in CAMS:
        CAMS[nm][0].rotation_euler = (0, 0, 0)
for name, (ob, names) in CAMS.items():
    ob['render_scenes'] = [n for n in names if n in bpy.data.scenes]
    for n in ob['render_scenes']:
        bpy.data.scenes[n].collection.objects.link(ob)
for sc, cam in ((scene, 'CAM_03_AFT_ASSEMBLY'), (cut_scene, 'CAM_04_NOZZLE_CUTAWAY'), (base_scene, 'CAM_02b_PERSPECTIVE_SHIP'),
                (bpy.data.scenes.get('COMPARE_PROPULSION'), 'CAM_08_COMPARE_PROPULSION'), (tk_scene, 'CAM_09_COMPARE_TANKS'), (ef_scene, 'CAM_10_ENERGY_FLOW')):
    if sc is not None:
        sc.camera = CAMS[cam][0]

# shield view: only the shadow cones and the ship read; hide the wings for that camera at render time
SHIELD_VIEW_HIDE = ('FDP1_Wing_',)
CLOSE_CAMS = ('CAM_04_NOZZLE_CUTAWAY', 'CAM_05_FUEL_AND_DRIVERS', 'CAM_05b_DRIVER_GALLERIES', 'CAM_06b_SHIELD_CLOSE')


def hide_layer(sc, name):
    def walk(lc):
        if lc is None:
            return
        if lc.collection.name == name:
            lc.hide_viewport = True
        for ch in lc.children:
            walk(ch)
    for vl in sc.view_layers:
        walk(vl.layer_collection)


hide_layer(scene, colls['11'].name)   # keep-outs: one click on the eye in the outliner shows them

# ----------------------------------------------------------------------------------------------------------------------------------
# texts inside the file
# ----------------------------------------------------------------------------------------------------------------------------------
readme = bpy.data.texts.new('README_FDP1')
readme.write((FDP/'README.md').read_text() if (FDP/'README.md').exists() else 'FDP-1 review file\n')
readme.write('\n\n## Hidden in this file (superseded four-nozzle drive, not deleted)\n\n'+', '.join(sorted(set(hidden)))+'\n')
if moved:
    readme.write(f"\n## Bow moved forward by {R['tanks']['options']['T-B']['added_length_m']:.1f} m in this file (tank layout T-B)\n\n"+', '.join(moved[:400])+'\n')
legend = bpy.data.texts.new('FDP1_FUNCTIONAL_COLOR_LEGEND')
legend.write('\n'.join(f'{k}: {v[0]}  RGBA {tuple(round(c, 2) for c in v[1])}  collection tag {v[2]}' for k, v in PALETTE.items()))
rec = bpy.data.texts.new('FDP1_ENGINEERING_RECORD.json'); rec.write(json.dumps(R, indent=1, default=float))
status = bpy.data.texts.new('FDP1_PART_STATUS')
status.write('\n'.join(f"{p['status']:12s} {p['name']}  {p.get('note', '')}" for p in PARTS+TANKS))

# ----------------------------------------------------------------------------------------------------------------------------------
if a.render:
    a.render.mkdir(parents=True, exist_ok=True)
    for name, (ob, names) in CAMS.items():
        if a.cams and name not in a.cams:
            continue
        for n in ob['render_scenes']:
            sc = bpy.data.scenes[n]; sc.camera = ob
            if name == 'CAM_06_SHIELDING_AND_ESCAPE':
                hide = [o for o in bpy.data.objects if o.name.startswith(SHIELD_VIEW_HIDE+('FDP1_Exhaust_Plume', 'FDP1_Exhaust_Envelope'))]
            else:
                hide = [o for o in bpy.data.objects if o.name.startswith(('FDP1_Shadow_Cone', 'FDP1_KeepOut'))]
            if name in CLOSE_CAMS:
                hide += [o for c in (colls['12'], ccolls['12']) for o in c.objects]
            for o in hide:
                o.hide_render = True
            tag = '' if n in ('FDP1_WAYFARER', 'FDP1_CUTAWAY', 'COMPARE_PROPULSION', 'COMPARE_TANKS', 'FDP1_ENERGY_FLOW') else '__'+n.lower()
            sc.render.filepath = str(a.render/f'{name}{tag}.png')
            bpy.ops.render.render(write_still=True, scene=sc.name)
            print('WF_RENDER', sc.render.filepath, flush=True)
            for o in hide:
                o.hide_render = False
    for sc, cam in ((scene, 'CAM_03_AFT_ASSEMBLY'), (cut_scene, 'CAM_04_NOZZLE_CUTAWAY')):
        sc.camera = CAMS[cam][0]
if not a.no_save:
    bpy.context.window_manager.windows[0].scene = scene if bpy.context.window_manager.windows else None
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(a.out), compress=True)
    print('WF_REVIEW saved', a.out, flush=True)
