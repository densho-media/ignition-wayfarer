"""RON blockouts in Blender (work, noncanonical). Reads geometry/<variant>.json and results/ron.json written by ron.py; nothing typed by hand.

  /snap/bin/blender -b --factory-startup --python lab/studies/vertex-compact-engine/vertex-ron/blender_ron.py -- [--no-render] [--views a,b] [--engine eevee|workbench]

Builds one WORK_RON_<variant> collection per prototype (pink tag), side by side at one scale, and saves
lab/studies/vertex-compact-engine/vertex-ron/REVIEW_RON.blend (packed; opens on the line-up camera) and one RON_<variant>.blend per prototype (only that prototype
visible). Renders six views per prototype to lab/studies/vertex-compact-engine/vertex-ron/renders/.

Per engine (engine axes: +X forward toward the ship, burn point at the origin; Blender +X bow, +Z dorsal):
  coils (MAIN_PROPULSION magenta): conical REBCO ribbons laid along the burn rays, thickness exaggerated for visibility (label);
  shadow plug (SHIELD amber), its blades to the ring rims and the boom to the ship (STRUCTURE grey): the load path;
  field lines (SIMULATED, from ron.py's Biot-Savart filaments, light blue), particle paths (SIMULATED, ron.py Boris pusher: exhaust white,
  forward escape orange, strike red), forward-stream cone (SIMULATED p95 cone), plug shadow (SIMULATED geometry, dark blue),
  photon and neutron escape shell (ILLUSTRATIVE: isotropic, shown as a translucent sphere at half the ship distance).
The ship is a proxy cylinder (canon 289.5 m long, 45 m shadow radius), not the built ship: the approved ship assets are not built in this
cloud container. Four engines sit on a square of side S, axes parallel to flight, the ship off each axis (ron.py cluster rule).
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector, Matrix

HERE = Path(__file__).resolve().parent
ARGS = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS
ENGINE = ARGS[ARGS.index('--engine')+1] if '--engine' in ARGS else 'eevee'
PROTOS = ['A_compact', 'B_D800', 'C_remote_F', 'D_distributed', 'E_hybrid_4_S250']
SHIP_L, SHIP_R = 289.5, 45.0
RES = json.loads((HERE/'results'/'ron.json').read_text())['variants']
PINK = 'COLOR_07'


def mat(name, rgba, emit=0.0, alpha=1.0, metal=0.0, rough=0.5):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (rgba[0], rgba[1], rgba[2], alpha); m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*rgba[:3], 1.0); b.inputs['Metallic'].default_value = metal
    b.inputs['Roughness'].default_value = rough
    if emit:
        b.inputs['Emission Color'].default_value = (*rgba[:3], 1.0); b.inputs['Emission Strength'].default_value = emit
    if alpha < 1.0:
        b.inputs['Alpha'].default_value = alpha
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            m.blend_method = 'BLEND'
    return m


M = dict(coil=mat('RON_COIL_REBCO', (0.86, 0.16, 0.76), metal=0.6, rough=0.35),
         plug=mat('RON_SHADOW_PLUG', (0.80, 0.58, 0.18), metal=0.7, rough=0.4),
         struct=mat('RON_STRUCTURE', (0.56, 0.56, 0.58), metal=0.5, rough=0.5),
         ship=mat('RON_SHIP_PROXY', (0.30, 0.34, 0.38), rough=0.7),
         field=mat('RON_FIELD_SIM', (0.55, 0.80, 1.0), emit=2.0),
         aft=mat('RON_PATH_EXHAUST_SIM', (0.95, 0.97, 1.0), emit=3.0),
         fwd=mat('RON_PATH_FORWARD_SIM', (1.0, 0.50, 0.10), emit=3.0),
         hit=mat('RON_PATH_STRIKE_SIM', (1.0, 0.10, 0.10), emit=3.0),
         cone=mat('RON_FORWARD_CONE_SIM', (1.0, 0.45, 0.15), emit=0.3, alpha=0.03),
         shadow=mat('RON_PLUG_SHADOW_SIM', (0.10, 0.25, 0.85), emit=0.3, alpha=0.06),
         rad=mat('RON_PHOTON_NEUTRON_ILLUSTRATIVE', (0.95, 0.85, 0.30), emit=0.15, alpha=0.015),
         burn=mat('RON_BURN', (0.75, 0.88, 1.0), emit=60.0),
         text=mat('RON_LABEL', (1.0, 0.88, 0.96), emit=4.0))


def coll(name, parent, tag=PINK):
    c = bpy.data.collections.new(name); parent.children.link(c); c.color_tag = tag
    return c


def link(obj, c, m=None):
    c.objects.link(obj)
    if m is not None:
        obj.data.materials.append(m)
    return obj


def revolve(name, prof, c, m, seg=96):
    """Mesh of revolution about +X from a closed (x, r) profile."""
    vs, fs = [], []; n = len(prof)
    for j in range(seg):
        a = 2*math.pi*j/seg
        for x, r in prof:
            vs.append((x, r*math.cos(a), r*math.sin(a)))
    for j in range(seg):
        jn = (j+1) % seg
        for i in range(n):
            i2 = (i+1) % n
            fs.append((j*n+i, j*n+i2, jn*n+i2, jn*n+i))
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    return link(bpy.data.objects.new(name, me), c, m)


def ribbon_profile(p0, p1, t):
    ux, uy = p1[0]-p0[0], p1[1]-p0[1]; L = math.hypot(ux, uy); nx, ny = -uy/L*t/2, ux/L*t/2
    return [(p0[0]+nx, p0[1]+ny), (p1[0]+nx, p1[1]+ny), (p1[0]-nx, p1[1]-ny), (p0[0]-nx, p0[1]-ny)]


def poly(name, pts, c, m, bevel):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = bevel; cu.bevel_resolution = 1
    s = cu.splines.new('POLY'); s.points.add(len(pts)-1)
    for p, q in zip(s.points, pts):
        p.co = (*q, 1.0)
    return link(bpy.data.objects.new(name, cu), c, m)


def bar(name, a, b, w, t, c, m, up=None):
    """A flat plate from a to b: width w in the plane of (a, b, up), thickness t across it."""
    a, b = Vector(a), Vector(b); d = b-a; L = d.length; z = d.normalized()
    u = (Vector(up) if up is not None else Vector((0, 0, 1)))
    x = (u-u.dot(z)*z); x = x.normalized() if x.length > 1e-6 else z.orthogonal().normalized(); y = z.cross(x)
    vs = [a+x*sx*w/2+y*sy*t/2+z*sz*L for sz in (0, 1) for sx in (-1, 1) for sy in (-1, 1)]
    fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in vs], [], fs); me.update()
    return link(bpy.data.objects.new(name, me), c, m)


def text(name, body, loc, size, c, rot=(math.pi/2, 0, math.pi/2)):
    cu = bpy.data.curves.new(name, 'FONT'); cu.body = body; cu.size = size
    o = link(bpy.data.objects.new(name, cu), c, M['text']); o.location = loc; o.rotation_euler = rot; o.hide_render = True
    return o


def cone(name, apex, axis, half_deg, length, c, m):
    r = length*math.tan(math.radians(half_deg))
    o = revolve(name, [(0.0, 0.0), (length, r), (length, 0.0)], c, m, seg=48)
    o.matrix_world = Matrix.Translation(apex) @ Vector((1, 0, 0)).rotation_difference(Vector(axis)).to_matrix().to_4x4()
    return o


def engine(name, g, r, c, origin, axis_to_ship, sims=True):
    """One engine at origin (burn point). Engine +X is the flight direction (rotated by the cant away from the ship)."""
    ce = coll(f'{name}', c)
    scale = max(max(math.hypot(*q['p1']) for q in g['coils']), g['plug']['x'])
    exag = max(1.0, 0.006*scale)                                      # visual minimum thickness
    objs = []
    for q in g['coils']:
        t = max(q['thick'], exag)
        objs.append(revolve(f'{name}_COIL_{q["name"]}', ribbon_profile(q['p0'], q['p1'], t), ce, M['coil']))
    # plug on the burn -> ship line (off axis by the ship offset): a grazing disc of radius r_p
    o = Vector(origin); sdir = Vector(axis_to_ship).normalized(); xp, rp = g['plug']['x'], g['plug']['r']
    pc = o+sdir*xp
    plug = revolve(f'{name}_PLUG', [(0, 0), (0, rp), (0.6, rp*0.98), (0.6, 0)], ce, M['plug'], seg=48)
    plug.matrix_world = Matrix.Translation(pc) @ Vector((1, 0, 0)).rotation_difference(sdir).to_matrix().to_4x4()
    # engine frame (rotation applied to the coil, field and path objects)
    cant = math.radians(r.get('cant_deg', 0.0)); off = Vector((0, -o.y, -o.z)); off = off.normalized() if off.length else Vector((0, 0, 1))
    Rm = Matrix.Rotation(cant, 4, Vector((1, 0, 0)).cross(off).normalized()) if cant and off.length else Matrix.Identity(4)
    Tm = Matrix.Translation(o) @ Rm
    for ob in objs:
        ob.matrix_world = Tm
    if g['boom']:
        cs = coll(f'{name}_LOAD_PATH', ce, 'NONE')
        for q in g['coils']:
            if q['name'].startswith('PLUG_COIL'):
                continue
            x1, r1 = q['p1']
            for j in range(g['blades']):
                a = 2*math.pi*(j+0.5)/g['blades']
                rim = Tm @ Vector((x1, r1*math.cos(a), r1*math.sin(a)))
                bar(f'{name}_BLADE_{q["name"]}_{j}', rim, pc, max(1.5, 0.02*scale), max(0.3, 0.004*scale), cs, M['struct'], up=rim-o)
        ship_aft = Vector((g['D'], 0, 0))
        bar(f'{name}_BOOM', pc, ship_aft+(pc-ship_aft).normalized()*SHIP_R*0.2, 2.5, 2.5, cs, M['struct'])
    if not sims:
        return ce
    sim = coll(f'{name}_SIMULATED', ce, 'NONE')
    for i, line in enumerate(g['field_lines']):
        if i % 5 == 4:                    # the seed just outside the conductor only circles the ribbon: left out of the picture
            continue
        for j in range(3):
            a = 2*math.pi*j/3+0.3
            pts = [tuple(Tm @ Vector((x, rr*math.cos(a), rr*math.sin(a)))) for x, rr in line[::3]]
            if len(pts) > 2:
                poly(f'{name}_FIELD_{i}_{j}', pts, sim, M['field'], 0.0008*scale)
    for i, p in enumerate(g.get('paths', [])):
        m = dict(AFT=M['aft'], FORWARD=M['fwd'], HIT=M['hit']).get(p['outcome'], M['aft'])
        pts = [tuple(Tm @ Vector(q)) for q in p['points']]
        if len(pts) > 2:
            poly(f'{name}_PATH_{p["outcome"]}_{i}', pts, sim, m, 0.0012*scale)
    fc = r['particles'].get('forward_cone_p95_deg') or 0.0
    if r['particles']['forward_energy_share'] > 0 and fc:
        cone(f'{name}_FORWARD_STREAM_CONE', Tm @ Vector((0, 0, 0)), (Tm.to_3x3() @ Vector((1, 0, 0))), fc, 1.3*scale, sim, M['cone'])
    th = math.degrees(math.atan(rp/xp))
    cone(f'{name}_PLUG_SHADOW', o, sdir, th, (Vector((g['D'], 0, 0))-o).length+SHIP_L, sim, M['shadow'])
    burn = bpy.data.objects.new(f'{name}_BURN', bpy.data.meshes.new(f'{name}_BURN'))
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=max(1.0, 0.01*scale)); bm.to_mesh(burn.data); bm.free()
    link(burn, sim, M['burn']); burn.location = o
    ill = coll(f'{name}_ILLUSTRATIVE', ce, 'NONE')
    sh = bpy.data.objects.new(f'{name}_PHOTON_NEUTRON_ESCAPE', bpy.data.meshes.new(f'{name}_PNE'))
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.6*scale); bm.to_mesh(sh.data); bm.free()
    link(sh, ill, M['rad']); sh.location = o
    return ce


def prototype(name, root, offset_y):
    g = json.loads((HERE/'geometry'/f'{name}.json').read_text()); r = RES[name]
    c = coll(f'WORK_RON_{name}', root)
    S, D = g['S'], g['D']
    if g['family'] == 'compact':
        origins = [Vector((0, sy*18.0, sz*18.0)) for sy in (-1, 1) for sz in (-1, 1)]
    else:
        origins = [Vector((0, sy*S/2, sz*S/2)) for sy in (-1, 1) for sz in (-1, 1)]
    ship = revolve(f'{name}_SHIP_PROXY', [(D, 0), (D, SHIP_R), (D+SHIP_L, SHIP_R*0.6), (D+SHIP_L, 0)], c, M['ship'], seg=48)
    for i, o in enumerate(origins):
        engine(f'{name}_E{i+1}', g, r, c, o, Vector((D, 0, 0))-o, sims=(i == 0))
    sh = r['ship']; L = r['ledger']; m = r['mass_t']
    lab = (f"{r['label']}\nengine {r['engine_t']:.0f} t | departure {sh['departure_t']:.0f} t (canon 4426) | eta {r['particles']['axial_efficiency']:.2f}"
           f" | cant {r['cant_deg']:.1f} deg\nhardware heat x4: piped {4*L['B01_W']/1e9:.1f} GW, self-radiated {4*L['self_W']/1e9:.0f} GW"
           f"\nSIMULATED: field lines, particle paths, forward cone, plug shadow. ILLUSTRATIVE: photon/neutron shell. Coil thickness exaggerated."
           f"\nShip = proxy cylinder (canon 289.5 m). WORK, not canon.")
    text(f'{name}_LABEL', lab, (D*0.0, -max(S, 200)*0.9, max(S, 200)*0.9+40), max(8.0, 0.02*(D+SHIP_L)), c, rot=(math.pi/2, 0, 0))
    for ob in c.all_objects:
        ob.location.y += offset_y
    return c, g, r


def camera(name, loc, target, c, ortho=None, lens=35):
    cd = bpy.data.cameras.new(name); cd.clip_end = 2e5; cd.clip_start = 0.5
    if ortho:
        cd.type = 'ORTHO'; cd.ortho_scale = ortho
    else:
        cd.lens = lens
    o = bpy.data.objects.new(name, cd); c.objects.link(o); o.location = loc
    o.rotation_euler = (Vector(target)-Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def views(name, g, oy, c):
    s = max(max(math.hypot(*q['p1']) for q in g['coils']), g['plug']['x'])
    e = Vector((0, -g['S']/2 if g['family'] != 'compact' else -18, -g['S']/2 if g['family'] != 'compact' else -18))+Vector((0, oy, 0))
    ctr = e+Vector((s*0.5, 0, 0)); W = g['D']+SHIP_L+max(g['S'], 60)
    mid = Vector(((g['D']+SHIP_L)/2-60, oy, 0))
    return {
        'three_quarter': camera(f'CAM_{name}_three_quarter', ctr+Vector((-2.2*s, -2.4*s, 1.6*s)), ctr, c, lens=35),
        'side': camera(f'CAM_{name}_side', ctr+Vector((0, -6*s, 0)), ctr, c, ortho=3.2*s),
        'top': camera(f'CAM_{name}_top', ctr+Vector((0, 0, 6*s)), ctr, c, ortho=3.2*s),
        'rear': camera(f'CAM_{name}_rear', e+Vector((-6*s, 0, 0)), e, c, ortho=2.6*s),
        'integration': camera(f'CAM_{name}_integration', mid+Vector((-0.55*W, -0.9*W, 0.45*W)), mid, c, lens=40),
        'closeup': camera(f'CAM_{name}_closeup', e+Vector((g['coils'][0]['p1'][0]*0.4, -1.1*g['coils'][0]['p1'][1], 0.5*g['coils'][0]['p1'][1])),
                          e+Vector((g['coils'][0]['p1'][0], 0, -0.2*g['coils'][0]['p1'][1])), c, lens=24),
    }


def setup_render():
    sc = bpy.context.scene
    try:
        sc.render.engine = 'BLENDER_EEVEE' if ENGINE == 'eevee' else 'BLENDER_WORKBENCH'
    except TypeError:
        sc.render.engine = 'BLENDER_EEVEE_NEXT'
    if sc.render.engine.startswith('BLENDER_EEVEE'):
        sc.eevee.taa_render_samples = 8
    else:
        sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720; sc.render.film_transparent = False
    w = bpy.data.worlds.new('RON_WORLD'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.01, 0.012, 0.02, 1.0)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
    sun = bpy.data.objects.new('RON_SUN', bpy.data.lights.new('RON_SUN', 'SUN')); sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(40), math.radians(-30), math.radians(-35)); sc.collection.objects.link(sun)
    sc.view_settings.view_transform = 'AgX' if 'AgX' in [i.identifier for i in sc.view_settings.bl_rna.properties['view_transform'].enum_items] else 'Filmic'


def main():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    setup_render()
    sc = bpy.context.scene
    root = sc.collection
    cams = coll('30_CAMERAS', root, 'NONE')
    built, oy = [], 0.0
    for name in PROTOS:
        c, g, r = prototype(name, root, -oy)                      # A on the left in the line-up (top view, bow up)
        built.append((name, c, g, -oy, views(name, g, -oy, cams)))
        oy += max(g['S'], 200)+900.0
    span = oy
    cy = -(span-1100.0)/2
    lineup = camera('CAM_LINEUP', (1100, cy, 2.3*span), (1100, cy, 0), cams, ortho=0.98*span)
    lineup.rotation_euler = (0.0, 0.0, -math.pi/2)                      # top view, prototypes left to right, bow up
    sc.camera = lineup
    legend = ('RON blockouts (WORK, not canon). Colours: magenta coils (main propulsion), amber shadow plug (shield), grey blades and boom '
              '(structure, load path), light blue field lines (SIMULATED), white/orange/red particle paths (SIMULATED exhaust/forward/strike), '
              'blue cone plug shadow (SIMULATED geometry), amber shell photon/neutron escape (ILLUSTRATIVE). Same scale for every prototype.')
    text('RON_LEGEND', legend, (0, -400, 600), 30.0, root, rot=(math.pi/2, 0, 0))
    rd = HERE/'renders'; rd.mkdir(exist_ok=True)
    out = HERE/'REVIEW_RON.blend'
    bpy.ops.file.pack_all(); bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
    if RENDER:
        only = ARGS[ARGS.index('--views')+1].split(',') if '--views' in ARGS else None
        sc.render.filepath = str(rd/'lineup.png'); bpy.ops.render.render(write_still=True)
        for name, c, g, y0, cv in built:
            for other in built:
                other[1].hide_render = other[0] != name
            for vn, cam in cv.items():
                if only and vn not in only:
                    continue
                tech = vn in ('side', 'top', 'rear', 'closeup')          # orthographic views and the close-up: Workbench (fast); three-quarter, integration, line-up: Eevee
                sc.render.engine = 'BLENDER_WORKBENCH' if (tech or ENGINE != 'eevee') else 'BLENDER_EEVEE'
                sc.display.shading.light = 'FLAT'; sc.display.shading.color_type = 'MATERIAL'
                for ob in bpy.data.objects:                   # Workbench draws no blended alpha: translucent volumes stay out of those views
                    if ob.type == 'MESH' and ob.data.materials and ob.data.materials[0].name in ('RON_FORWARD_CONE_SIM', 'RON_PLUG_SHADOW_SIM',
                                                                                                    'RON_PHOTON_NEUTRON_ILLUSTRATIVE'):
                        ob.hide_render = tech
                sc.camera = cam; sc.render.filepath = str(rd/f'{name}_{vn}.png'); bpy.ops.render.render(write_still=True)
                print('rendered', name, vn, flush=True)
        for other in built:
            other[1].hide_render = False
        sc.camera = lineup
    for name, c, g, y0, cv in built:                    # per-prototype files: only that prototype visible, its three-quarter camera active
        for other in built:
            other[1].hide_viewport = other[1].hide_render = other[0] != name
        sc.camera = cv['three_quarter']
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'RON_{name}.blend'), compress=True, copy=True)
    for other in built:
        other[1].hide_viewport = other[1].hide_render = False
    sc.camera = lineup
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)


main()
