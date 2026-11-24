"""AMPN prototypes in Blender (work, noncanonical). Reads geometry/<design>.json (optimize.py) and results/coilpack.json; reuses the RON
blockout builders (lab/studies/vertex-compact-engine/vertex-ron/blender_ron.py) for coils, plug, blades, boom, field lines and particle paths.

  /snap/bin/blender -b --factory-startup --python lab/studies/vertex-compact-engine/vertex-ampn/blender_ampn.py -- [--no-render] [--no-anim]

Collections (pink WORK_ tags; the canonical ship is not touched, the ship is a proxy cylinder):
  WORK_AMPN_PROPULSION   B (today's tape optimum) in propulsion: four engines, armour bands, stern screen stowed edge-on, boom fences,
                         cryoplant and warm radiator at each plug node, helium loop round each ring, bellows at the carriage.
  WORK_AMPN_BRAKING      the same ship flipped (engines first), stern screen deployed in the plug shadow, ILLUSTRATIVE dust tracks
                         and debris clouds, the narrow (SIMULATED-class) plume and the rejected broad Mode B plume.
  WORK_AMPN_STOWED       one engine with the ring run up its carriage to the plug node, armour petals closed.
  WORK_AMPN_SECTION      the ring cross-section, layer by layer at exaggerated thickness, labelled.
  WORK_AMPN_E            the E competitor (forward mirror coil in the plug shadow) in propulsion, for comparison.
Animation (frames 1-240): ring stows and returns, ship flips 180 degrees, stern screen unfolds. Renders to lab/studies/vertex-compact-engine/vertex-ampn/renders/.
"""
import json
import math
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector, Matrix

HERE = Path(__file__).resolve().parent
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS
ANIM = '--no-anim' not in ARGS
src = (HERE.parent / 'vertex-ron' / 'blender_ron.py').read_text().replace('\nmain()\n', '\n')
src = src.replace("RES = json.loads((HERE/'results'/'ron.json').read_text())['variants']", "RES = {}")
NS = dict(__name__='ron_blocks', __file__=str(HERE.parent / 'vertex-ron' / 'blender_ron.py'))
sys.argv = [sys.argv[0], '--', '--no-render']
exec(compile(src, 'blender_ron.py', 'exec'), NS)
coll, revolve, ribbon_profile, poly, bar, text, cone, engine, camera, setup_render, link, mat = (
    NS[k] for k in ('coll', 'revolve', 'ribbon_profile', 'poly', 'bar', 'text', 'cone', 'engine', 'camera', 'setup_render', 'link', 'mat'))
M = NS['M']; SHIP_R = NS['SHIP_R']; SHIP_L = NS['SHIP_L']
M.update(armour=mat('AMPN_ARMOUR_CC', (0.12, 0.12, 0.13), rough=0.9),
         screen=mat('AMPN_STERN_SCREEN_CC', (0.20, 0.20, 0.22), rough=0.9),
         fence=mat('AMPN_BOOM_FENCE', (0.25, 0.25, 0.27), rough=0.9),
         cryo=mat('AMPN_CRYO_LOOP', (0.20, 0.75, 0.95), emit=1.0),
         warm=mat('AMPN_WARM_RADIATOR', (0.95, 0.55, 0.20), emit=0.5),
         plant=mat('AMPN_CRYOPLANT', (0.85, 0.85, 0.90), metal=0.6, rough=0.3),
         bellows=mat('AMPN_BELLOWS', (0.75, 0.75, 0.80), metal=0.8, rough=0.3),
         dust=mat('AMPN_DUST_TRACK_ILLUSTRATIVE', (1.0, 0.95, 0.6), emit=4.0),
         cloud=mat('AMPN_DEBRIS_CLOUD_ILLUSTRATIVE', (1.0, 0.4, 0.2), emit=1.5, alpha=0.25),
         plume=mat('AMPN_PLUME_NARROW', (0.55, 0.75, 1.0), emit=0.8, alpha=0.08),
         broad=mat('AMPN_PLUME_BROAD_REJECTED', (1.0, 0.3, 0.3), emit=0.5, alpha=0.04))
LAYER_M = [mat(f'AMPN_LAYER_{i}', c, rough=0.6) for i, c in enumerate([
    (0.12, 0.12, 0.13), (0.55, 0.55, 0.60), (0.35, 0.30, 0.28), (0.70, 0.60, 0.45), (0.80, 0.78, 0.70), (0.95, 0.85, 0.30),
    (0.60, 0.65, 0.70), (0.86, 0.16, 0.76), (0.30, 0.30, 0.35)])]

CP = json.loads((HERE / 'results' / 'coilpack.json').read_text())
MAIN, COMP = 'B_today', 'E_today'


def load(key):
    g = json.loads((HERE / 'geometry' / f'{key}.json').read_text())
    o = json.loads((HERE / 'results' / 'optimize.json').read_text())[key]
    r = dict(cant_deg=g.get('cant_deg', 0.0), particles=dict(forward_cone_p95_deg=0.0, forward_energy_share=0.0))
    return g, r, o


def sphere(name, loc, rad, c, m, seg=16):
    ob = bpy.data.objects.new(name, bpy.data.meshes.new(name)); bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=max(4, seg // 2), radius=rad); bm.to_mesh(ob.data); bm.free()
    link(ob, c, m); ob.location = loc
    return ob


def torus(name, R, r, c, m, x=0.0):
    prof = [(x + r * math.cos(2 * math.pi * i / 12), R + r * math.sin(2 * math.pi * i / 12)) for i in range(12)]
    return revolve(name, prof, c, m, seg=96)


def box(name, ctr, size, c, m):
    ob = bpy.data.objects.new(name, bpy.data.meshes.new(name)); bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0); bm.to_mesh(ob.data); bm.free()
    link(ob, c, m); ob.location = ctr; ob.scale = size
    return ob


def extras(name, g, key, c, origin, cant_m):
    """Armour bands, helium loop, bellows, cryoplant and warm radiator for one engine (engine frame matrix cant_m)."""
    ce = coll(f'{name}_PROTECTION_COOLING', c, 'NONE')
    cp = CP[key]
    rows = {r['face']: r for r in cp['dust_rows']}
    arm = next(v for k, v in rows.items() if k.startswith('ring aft'))['armour_t_m'] or 0.1
    q = g['coils'][0]
    t = max(q['thick'], 0.5)
    # armour tiles: a dark band over the burn-facing tip and one on the forward edge (thickness exaggerated to 0.5 m minimum)
    ux, uy = q['p1'][0] - q['p0'][0], q['p1'][1] - q['p0'][1]; L = math.hypot(ux, uy)
    a0 = (q['p0'][0] - ux / L * max(arm, 0.4), q['p0'][1] - uy / L * max(arm, 0.4))
    for nm, (pa, pb) in (('AFT', (a0, q['p0'])), ('FWD', (q['p1'], (q['p1'][0] + ux / L * max(arm, 0.4), q['p1'][1] + uy / L * max(arm, 0.4))))):
        ob = revolve(f'{name}_ARMOUR_{nm}', ribbon_profile(pa, pb, t * 1.4), ce, M['armour']); ob.matrix_world = cant_m
    R = q['p1'][1]
    lp = torus(f'{name}_HE_LOOP', R + t, max(0.25, 0.01 * R), ce, M['cryo'], x=q['p1'][0]); lp.matrix_world = cant_m
    xp, rp = g['plug']['x'], g['plug']['r']
    sdir = (Vector((g['D'], 0, 0)) - origin).normalized()
    node = origin + sdir * (xp + 3.0)
    plant = box(f'{name}_CRYOPLANT', node + sdir * 4.0, (6.0, 4.0, 4.0), ce, M['plant'])
    plant.rotation_euler = Vector((1, 0, 0)).rotation_difference(sdir).to_euler()
    # warm radiator: edge-on to the burn (its plane contains the burn-node line), in the plug shadow
    side = sdir.cross(Vector((0, 0, 1))).normalized()
    rad = bar(f'{name}_WARM_RADIATOR', node + sdir * 8.0, node + sdir * (8.0 + 0.6 * xp), 2 * rp * 0.8, 0.1, ce, M['warm'], up=side)
    # bellows: short corrugated segment where the cryo line leaves the carriage (illustrative ribs)
    for i in range(6):
        b = torus(f'{name}_BELLOWS_{i}', 0.6, 0.12, ce, M['bellows'], x=0.0)
        b.matrix_world = Matrix.Translation(node + sdir * (14.0 + 0.5 * i)) @ Vector((1, 0, 0)).rotation_difference(sdir).to_matrix().to_4x4()
    # cryo line along the blade to the ring
    rim = cant_m @ Vector((q['p1'][0], q['p1'][1] + t, 0.0))
    poly(f'{name}_CRYO_LINE', [tuple(node), tuple(rim)], ce, M['cryo'], 0.25)
    return ce


def ship_stack(key, cname, root, flipped=False, sims=True, screen_deployed=False):
    g, r, o = load(key)
    c = coll(cname, root)
    S, D = g['S'], g['D']
    origins = [Vector((0, sy * S / 2, sz * S / 2)) for sy in (-1, 1) for sz in (-1, 1)]
    revolve(f'{cname}_SHIP_PROXY', [(D, 0), (D, SHIP_R), (D + SHIP_L, SHIP_R * 0.6), (D + SHIP_L, 0)], c, M['ship'], seg=48)
    for i, og in enumerate(origins):
        ce = engine(f'{cname}_E{i + 1}', g, r, c, og, Vector((D, 0, 0)) - og, sims=(sims and i == 0))
        cant = math.radians(r.get('cant_deg', 0.0)); off = Vector((0, -og.y, -og.z)).normalized()
        Rm = Matrix.Rotation(cant, 4, Vector((1, 0, 0)).cross(off).normalized()) if cant else Matrix.Identity(4)
        extras(f'{cname}_E{i + 1}', g, key, ce, og, Matrix.Translation(og) @ Rm)
        # boom fence: strip bumper on struts ahead of the services duct (both sides), 50 m stand-off
        node = og + (Vector((D, 0, 0)) - og).normalized() * g['plug']['x']
        aft = Vector((D, 0, 0)) + (node - Vector((D, 0, 0))).normalized() * SHIP_R * 0.2
        for sgn in (-1, 1):
            bar(f'{cname}_E{i + 1}_FENCE_{"AFT" if sgn < 0 else "FWD"}', node + Vector((sgn * 50.0, 0, 0)), aft + Vector((sgn * 50.0, 0, 0)), 3.0, 0.2, c, M['fence'])
    cp = CP[key]
    st = next(rw for rw in cp['dust_rows'] if rw['face'].startswith('ship stern'))
    Sst = st['standoff_needed_m'] or 60.0
    scr = revolve(f'{cname}_STERN_SCREEN', [(0, 0), (0, SHIP_R * 1.02), (0.6, SHIP_R * 1.02), (0.6, 0)], c, M['screen'], seg=64)
    scr.location = (D - Sst, 0, 0)
    if not screen_deployed:
        scr.scale = (1, 0.08, 1)                      # stowed: furled along the mast, edge-on
    bar(f'{cname}_STERN_MAST', (D - Sst, 0, 0), (D, 0, 0), 1.5, 1.5, c, M['struct'])
    lab = (f"{key}: R {o['x'][0]:.0f} m, kappa {o['x'][1]:.2f}, ship {o['x'][2]:.0f} m aft of the burn, spacing {o['x'][3]:.0f} m | engine "
           f"{cp['engine_full_t']:.0f} t | departure {cp['ship']['departure_t']:,.0f} t (canon 4,426) | eta {o['eta']:.2f} | cant {o['cant_deg']:.1f}\n"
           f"Armour, stern screen ({Sst:.0f} m), fences, cryoplant, warm radiator, He loop: PROTOTYPE sizing (dust.py, coilpack.py). WORK, not canon.")
    text(f'{cname}_LABEL', lab, (0, -S * 0.9, S * 0.9 + 40), max(10.0, 0.012 * (D + SHIP_L)), c, rot=(math.pi / 2, 0, 0))
    if flipped:
        pivot = Vector((D + SHIP_L / 2, 0, 0))
        for ob in c.all_objects:
            if ob.parent is None:
                ob.matrix_world = Matrix.Translation(pivot) @ Matrix.Rotation(math.pi, 4, 'Z') @ Matrix.Translation(-pivot) @ ob.matrix_world
    return c, g, o


def dust_tracks(c, g, flipped_pivot):
    """ILLUSTRATIVE: grains arrive along the flight direction; in braking that is from the engine side. Tracks end on the stern screen
    (debris cloud) or the ring armour; none is stopped by the plume."""
    cd = coll('WORK_AMPN_DUST_ILLUSTRATIVE', c)
    D = g['D']; S = g['S']
    def fl(v):
        return Matrix.Translation(flipped_pivot) @ Matrix.Rotation(math.pi, 4, 'Z') @ Matrix.Translation(-flipped_pivot) @ Vector(v)
    st = next(rw for rw in CP[MAIN]['dust_rows'] if rw['face'].startswith('ship stern'))
    Sst = st['standoff_needed_m'] or 60.0
    import random
    rnd = random.Random(7)
    for i in range(24):
        y, z = rnd.uniform(-40, 40), rnd.uniform(-40, 40)
        a = fl((-3 * D, y, z)); b = fl((D - Sst, y, z))
        poly(f'DUST_STERN_{i}', [tuple(a), tuple(b)], cd, M['dust'], 0.25)
        if i % 4 == 0:
            cone(f'DEBRIS_CLOUD_{i}', b, tuple((fl((D, y, z)) - b).normalized()), 30.0, Sst, cd, M['cloud'])
    q = g['coils'][0]
    for i in range(8):
        a_ = 2 * math.pi * i / 8; og = Vector((0, S / 2, S / 2))
        y, z = og.y + q['p0'][1] * math.cos(a_), og.z + q['p0'][1] * math.sin(a_)
        poly(f'DUST_RING_{i}', [tuple(fl((-3 * D, y, z))), tuple(fl((q['p0'][0], y, z)))], cd, M['dust'], 0.2)
    return cd


def plumes(c, g, pivot):
    cp_ = coll('WORK_AMPN_PLUMES', c)
    og = Vector((0, g['S'] / 2, g['S'] / 2))
    def fl(v):
        return Matrix.Translation(pivot) @ Matrix.Rotation(math.pi, 4, 'Z') @ Matrix.Translation(-pivot) @ Vector(v)
    ax = (fl(og + Vector((-1, 0, 0))) - fl(og)).normalized()
    cone('PLUME_NARROW_10deg', fl(og), tuple(ax), 10.0, 2.0 * g['D'], cp_, M['plume'])
    og2 = Vector((0, -g['S'] / 2, g['S'] / 2))
    cone('PLUME_BROAD_MODE_B_45deg_REJECTED', fl(og2), tuple(ax), 45.0, 1.2 * g['D'], cp_, M['broad'])
    text('PLUME_LABEL', 'narrow plume (propulsion) vs broad Mode B plume (REJECTED: column 1e8 x short, thrust x0.60)',
         tuple(fl(og2 + Vector((-1.2 * g['D'], 0, g['S'] / 2)))), 40.0, cp_, rot=(math.pi / 2, 0, 0))
    return cp_


def section(root, loc):
    """Ring cross-section at exaggerated thickness, layers from the burn-facing tip (left) to the winding support (right)."""
    c = coll('WORK_AMPN_SECTION', root)
    layers = CP[MAIN]['layers']
    x = 0.0
    widths = [1.0, 2.0, 0.4, 0.4, 0.8, 0.6, 0.3, 1.2, 0.8]
    for i, (L, w) in enumerate(zip(layers, widths)):
        box(f'SECTION_{i}', Vector(loc) + Vector((x + w / 2, 0, 0)), (w / 2, 0.5, 1.0 + 0.1 * i), c, LAYER_M[i])
        tt = f"{L['layer']}" + (f" | {L['mass_t']:.1f} t/engine" if L.get('mass_t') else '') + (f" | {L['T_K']} K" if L.get('T_K') else '')
        lab = text(f'SECTION_LABEL_{i}', tt, tuple(Vector(loc) + Vector((x + w / 2, -0.6, 2.4 + 0.55 * (i % 2))) ), 0.16, c, rot=(math.pi / 2, 0, math.pi / 2 * 0 + 0))
        lab.rotation_euler = (math.pi / 2, 0, 0); lab.hide_render = False
        lab.rotation_euler = (math.pi / 2, -math.pi / 2.6, 0)
        x += w + 0.08
    text('SECTION_TITLE', 'Ring cross-section (not to scale; thickness exaggerated). Burn side left. PROTOTYPE stack (coilpack.py).',
         tuple(Vector(loc) + Vector((0, -0.6, -1.8))), 0.3, c, rot=(math.pi / 2, 0, 0)).hide_render = False
    return c


def stowed(root, g, oy):
    """One engine with the ring run up the carriage to the plug node, armour petals closed (cones over the ring)."""
    c = coll('WORK_AMPN_STOWED', root)
    r = dict(cant_deg=0.0, particles=dict(forward_cone_p95_deg=0.0, forward_energy_share=0.0))
    gs = json.loads(json.dumps(g))
    xp = g['plug']['x']
    for q in gs['coils']:
        dx = (xp - 4.0) - q['p1'][0]
        q['p0'] = [q['p0'][0] + dx, q['p0'][1]]; q['p1'] = [q['p1'][0] + dx, q['p1'][1]]
    engine('STOWED_E1', gs, r, c, Vector((0, oy, 0)), Vector((g['D'], 0, 0)), sims=False)
    q = gs['coils'][0]
    pet = revolve('STOWED_PETALS', [(q['p0'][0] - 2, q['p0'][1] - 2), (q['p1'][0] + 1, q['p1'][1] + 2), (q['p1'][0] + 1.5, q['p1'][1] + 1.5),
                                    (q['p0'][0] - 1.5, q['p0'][1] - 2.5)], c, M['armour'], seg=64)
    pet.location.y = oy
    # the working position as a ghost outline for comparison
    gw = coll('WORK_AMPN_WORKING_POSITION_GHOST', c, 'NONE')
    q0 = g['coils'][0]
    gh = revolve('GHOST_RING_WORKING', ribbon_profile(q0['p0'], q0['p1'], max(q0['thick'], 0.5)), gw, M['cone'])
    gh.location.y = oy
    text('STOWED_LABEL', f'STOWED: ring on its carriage at the plug node ({q0["p1"][0]:.0f} m -> {xp - 4:.0f} m), petals closed, field down. '
         'Ghost: working position.', (0, oy - 3 * q0['p1'][1], 3 * q0['p1'][1]), 4.0, c, rot=(math.pi / 2, 0, 0)).hide_render = False
    return c


def animate(prop_c, g, pivot):
    """Frames 1-80 ring stows (engine 1), 81-160 ship flips, 161-240 stern screen unfolds."""
    sc = bpy.context.scene; sc.frame_start, sc.frame_end = 1, 240; sc.render.fps = 24
    q = g['coils'][0]; dx = (g['plug']['x'] - 4.0) - q['p1'][0]
    ring = [ob for ob in prop_c.all_objects if '_E1_COIL_' in ob.name or '_E1_ARMOUR' in ob.name or '_E1_HE_LOOP' in ob.name]
    emp = bpy.data.objects.new('AMPN_FLIP_PIVOT', None); prop_c.objects.link(emp); emp.location = pivot
    bpy.context.view_layer.update()
    for ob in prop_c.all_objects:
        if ob.parent is None and ob is not emp:
            mw = ob.matrix_world.copy(); ob.parent = emp; ob.matrix_parent_inverse = emp.matrix_world.inverted(); ob.matrix_world = mw
    bpy.context.view_layer.update()
    for ob in ring:
        loc0 = ob.location.copy()
        shift = ob.matrix_world.to_3x3() @ Vector((dx, 0, 0))
        ob.location = loc0; ob.keyframe_insert('location', frame=1)
        ob.location = loc0 + shift; ob.keyframe_insert('location', frame=40); ob.keyframe_insert('location', frame=50)
        ob.location = loc0; ob.keyframe_insert('location', frame=80)
    emp.rotation_euler = (0, 0, 0); emp.keyframe_insert('rotation_euler', frame=81)
    emp.rotation_euler = (0, 0, math.pi); emp.keyframe_insert('rotation_euler', frame=160)
    scr = next(ob for ob in prop_c.all_objects if ob.name.endswith('STERN_SCREEN'))
    scr.scale = (1, 0.08, 1); scr.keyframe_insert('scale', frame=161)
    scr.scale = (1, 1, 1); scr.keyframe_insert('scale', frame=240)


def main():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    setup_render()
    sc = bpy.context.scene; root = sc.collection
    cams = coll('30_CAMERAS', root, 'NONE')
    prop, g, o = ship_stack(MAIN, 'WORK_AMPN_PROPULSION', root)
    D, S = g['D'], g['S']
    gap = D + SHIP_L + 2 * S
    brk, _, _ = ship_stack(MAIN, 'WORK_AMPN_BRAKING', root, flipped=True, sims=False, screen_deployed=True)
    pivot = Vector((D + SHIP_L / 2, 0, 0))
    for ob in brk.all_objects:
        ob.location.y -= gap
    cd = dust_tracks(brk, g, pivot); pl = plumes(brk, g, pivot)
    for cc in (cd, pl):
        for ob in cc.all_objects:
            ob.location.y -= gap
    st = stowed(root, g, -2 * gap)
    sec = section(root, (0, -2 * gap - 600, 0))
    ec, ge, oe = ship_stack(COMP, 'WORK_AMPN_E', root, sims=True)
    for ob in ec.all_objects:
        ob.location.y += gap
    q = g['coils'][0]; e1 = Vector((0, -S / 2, -S / 2)); R = q['p1'][1]
    mid = Vector(((D + SHIP_L) / 2, 0, 0)); W = D + SHIP_L + S
    bmid = mid + Vector((0, -gap, 0))
    cv = {
        'three_quarter': camera('CAM_three_quarter', mid + Vector((-0.6 * W, -0.9 * W, 0.5 * W)), mid, cams, lens=40),
        'side': camera('CAM_side', mid + Vector((0, -3 * W, 0)), mid, cams, ortho=1.15 * W),
        'top': camera('CAM_top', mid + Vector((0, 0, 3 * W)), mid, cams, ortho=1.15 * W),
        'rear': camera('CAM_rear', Vector((-3 * W, 0, 0)), Vector((0, 0, 0)), cams, ortho=1.3 * S + 4 * R),
        'ring_closeup': camera('CAM_ring_closeup', e1 + Vector((q['p0'][0] - 1.2 * R, -1.6 * R, 0.6 * R)), e1 + Vector((q['p0'][0], 0, -0.4 * R)), cams, lens=28),
        'cooling': camera('CAM_cooling', e1 + Vector((g['plug']['x'] * 0.6, -1.6 * g['plug']['x'], 0.9 * g['plug']['x'])),
                          e1 + Vector((g['plug']['x'], 0, 0)), cams, lens=30),
        'section': camera('CAM_section', Vector((4.5, -2 * gap - 600 - 14, 1.5)), Vector((4.5, -2 * gap - 600, 0.5)), cams, lens=35),
        'stowed_vs_working': camera('CAM_stowed', Vector((g['plug']['x'] / 2, -2 * gap - 4.5 * g['plug']['x'], 0.6 * g['plug']['x'])),
                                    Vector((g['plug']['x'] / 2, -2 * gap, 0)), cams, lens=35),
        'braking_dust': camera('CAM_braking_dust', Vector((D + SHIP_L + 400, -gap - 700, 300)), Vector((D + SHIP_L + 120, -gap, 0)), cams, lens=30),
        'engine_cluster': camera('CAM_engine_cluster', Vector((-0.9 * S, -1.1 * S, 0.8 * S)), Vector((0.1 * S, 0, 0)), cams, lens=35),
        'whole_ship_lineup': camera('CAM_lineup', Vector((mid.x, -gap / 2, 2.6 * (3 * gap))), Vector((mid.x, -gap / 2, 0)), cams, ortho=4.2 * gap),
        'competitor_E': camera('CAM_E', mid + Vector((-0.6 * W, gap - 0.9 * W, 0.5 * W)), mid + Vector((0, gap, 0)), cams, lens=40),
    }
    sc.camera = cv['three_quarter']
    out = HERE / 'REVIEW_AMPN.blend'
    bpy.ops.file.pack_all(); bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
    rd = HERE / 'renders'; rd.mkdir(exist_ok=True)
    if RENDER:
        for vn, cam in cv.items():
            tech = vn in ('side', 'top', 'rear', 'section', 'whole_ship_lineup')
            sc.render.engine = 'BLENDER_WORKBENCH' if tech else 'BLENDER_EEVEE'
            sc.display.shading.light = 'FLAT'; sc.display.shading.color_type = 'MATERIAL'
            for ob in bpy.data.objects:
                if ob.type == 'MESH' and ob.data.materials and ob.data.materials[0].name == 'RON_PHOTON_NEUTRON_ILLUSTRATIVE':
                    ob.hide_render = True
                    continue
                if ob.type == 'CURVE' and '_FIELD_' in ob.name:
                    ob.hide_render = vn in ('cooling', 'engine_cluster', 'braking_dust')
                if ob.type == 'MESH' and ob.data.materials and ob.data.materials[0].name in (
                        'RON_FORWARD_CONE_SIM', 'RON_PLUG_SHADOW_SIM', 'RON_PHOTON_NEUTRON_ILLUSTRATIVE', 'AMPN_PLUME_NARROW',
                        'AMPN_PLUME_BROAD_REJECTED', 'AMPN_DEBRIS_CLOUD_ILLUSTRATIVE'):
                    ob.hide_render = tech
            sc.camera = cam; sc.render.filepath = str(rd / f'ampn_{vn}.png'); bpy.ops.render.render(write_still=True)
            print('rendered', vn, flush=True)
    if ANIM:
        animate(prop, g, pivot)
        for cc in (brk, st, sec, ec, cd, pl):
            cc.hide_render = True
        rob = next(ob for ob in prop.all_objects if '_E1_COIL_' in ob.name)
        bb = [rob.matrix_world @ Vector(c_) for c_ in rob.bound_box]
        rc = sum(bb, Vector()) / 8
        print('ring centre', rc, flush=True)
        ca = camera('CAM_anim_ring', rc + Vector((0.6 * g['plug']['x'], -3.0 * g['plug']['x'], 1.2 * g['plug']['x'])),
                    rc + Vector((0.6 * g['plug']['x'], 0, 0)), cams, lens=30)
        cb = camera('CAM_anim_ship', pivot + Vector((0, -3 * W, 0.3 * W)), pivot, cams, ortho=2.3 * pivot.x)
        for fr, cam in ((1, ca), (81, cb)):
            mk = sc.timeline_markers.new(f'cam_{fr}', frame=fr); mk.camera = cam
        sc.camera = ca
        for ob in bpy.data.objects:
            if ob.type == 'MESH' and ob.data.materials and ob.data.materials[0].name == 'RON_PHOTON_NEUTRON_ILLUSTRATIVE':
                ob.hide_render = True
        sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'
        sc.render.resolution_x, sc.render.resolution_y = 960, 540
        if RENDER:
            (rd / 'anim').mkdir(exist_ok=True)
            sc.frame_step = 4
            sc.render.filepath = str(rd / 'anim' / 'f_'); bpy.ops.render.render(animation=True)
        sc.frame_step = 1
        for cc in (brk, st, sec, ec, cd, pl):
            cc.hide_render = False
        sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    sc.camera = cv['three_quarter']; sc.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)


main()
