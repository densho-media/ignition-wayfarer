"""HIMS + Vertex integration prototype in Blender (work, noncanonical). Reuses the AMPN builders (lab/studies/vertex-compact-engine/vertex-ampn/blender_ampn.py, which
reuses the RON blockout) for the four-engine B-today ship, and adds the propulsion services, the HIMS stern concepts and the problem overlay.

  /snap/bin/blender -b --factory-startup --python lab/studies/vertex-compact-engine/vertex-hims/blender_hims.py -- [--no-render] [--no-anim]

Frame: the AMPN engine frame (burns at x = 0, ship stern at x = D). In braking the whole ship is turned engines-first, so the dust arrives
from -x toward the stern; the geometry is drawn unflipped and the dust is drawn arriving from -x.
Collections (pink WORK_ tags):
  WORK_HIMS_INTEGRATION   B today with propellant and fuel feeds, pellet injector tracks, maintenance platforms, spare cassette racks,
                          unshadowed-hemisphere keep-out cones, and HIMS-C (0.3 T) on the stern in place of the passive screen.
  WORK_HIMS_DUST_ILLUSTRATIVE  dust sheaf to the stern stack and the armoured engine faces (ILLUSTRATIVE).
  WORK_HIMS_CONCEPT_<k>   stern close-ups of PASSIVE, A, B2, B3 and C at their computed NOMINAL stand-offs (results/hims.json), with the
                          calculated test-ion paths (results/trajectories.json, SIMULATED) and illustrative debris cones.
  WORK_HIMS_PROBLEMS      red markers and labels: Engineering Problems Register IDs at their components (results/problems.json).
  WORK_HIMS_SEQUENCE      the interaction sequence (frames 1-200): grain, screen flash, cloud, SIMULATED ion paths, residual neutrals.
"""
import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector, Matrix

HERE = Path(__file__).resolve().parent
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS
ANIM = '--no-anim' not in ARGS
AMPN = HERE.parent / 'vertex-ampn' / 'blender_ampn.py'
src = AMPN.read_text().rstrip()
assert src.endswith('main()')
src = src[:-len('main()')]
NS = dict(__name__='ampn_blocks', __file__=str(AMPN))
exec(compile(src, 'blender_ampn.py', 'exec'), NS)
(coll, poly, bar, text, cone, camera, setup_render, link, mat, sphere, box, torus, revolve, ship_stack) = (NS[k] for k in (
    'coll', 'poly', 'bar', 'text', 'cone', 'camera', 'setup_render', 'link', 'mat', 'sphere', 'box', 'torus', 'revolve', 'ship_stack'))
M = NS['M']; SHIP_R = NS['SHIP_R']; SHIP_L = NS['SHIP_L']; MAIN = NS['MAIN']

H = json.loads((HERE / 'results' / 'hims.json').read_text())
TR = json.loads((HERE / 'results' / 'trajectories.json').read_text())
PR = json.loads((HERE / 'results' / 'problems.json').read_text())
OPT = {o['name']: o for o in H['cases']['NOMINAL']['options']}
OPTJ = {o['name']: o for o in H['cases']['JUSTIFIED']['options']}

M.update(ion=mat('HIMS_ION_PATH_SIMULATED', (0.15, 0.95, 1.0), emit=4.0),
         neutral=mat('HIMS_NEUTRAL_PATH_SIMULATED', (1.0, 0.55, 0.15), emit=4.0),
         grain=mat('HIMS_GRAIN_ILLUSTRATIVE', (1.0, 0.95, 0.6), emit=8.0),
         flash=mat('HIMS_FLASH_ILLUSTRATIVE', (1.0, 0.9, 0.7), emit=12.0, alpha=0.6),
         fieldvol=mat('HIMS_FIELD_REGION_SIM', (0.35, 0.55, 1.0), emit=0.4, alpha=0.08),
         go=mat('HIMS_CONDUCTOR_GO', (0.86, 0.16, 0.76), metal=0.6, rough=0.35),
         ret=mat('HIMS_CONDUCTOR_RETURN', (0.55, 0.10, 0.85), metal=0.6, rough=0.35),
         wall=mat('HIMS_STERN_WALL', (0.45, 0.48, 0.52), rough=0.8),
         mark=mat('HIMS_RESIDUAL_MARK', (1.0, 0.25, 0.1), emit=6.0),
         prob=mat('HIMS_PROBLEM_MARKER', (1.0, 0.08, 0.08), emit=5.0),
         probtxt=mat('HIMS_PROBLEM_LABEL', (1.0, 0.75, 0.75), emit=5.0),
         label=mat('HIMS_LABEL', (0.95, 0.95, 1.0), emit=4.0),
         fuel=mat('HIMS_FUEL_FEED', (0.95, 0.80, 0.20), emit=1.5),
         prop=mat('HIMS_PROPELLANT_FEED', (0.30, 0.95, 0.45), emit=1.5),
         keep=mat('HIMS_KEEP_OUT_SIM', (1.0, 0.2, 0.2), emit=0.2, alpha=0.025),
         rack=mat('HIMS_SPARE_CASSETTE', (0.70, 0.62, 0.50), rough=0.6),
         platform=mat('HIMS_PLATFORM', (0.95, 0.85, 0.15), rough=0.6))


def vlabel(name, body, loc, size, c, m=None, rot=(math.pi / 2, 0, 0)):
    o = text(name, body, loc, size, c, rot=rot); o.hide_render = False; o.data.materials.clear(); o.data.materials.append(m or M['label'])
    return o


def cyl(name, x0, x1, r, c, m, y=0.0, z=0.0, seg=64):
    o = revolve(name, [(x0, 0), (x0, r), (x1, r), (x1, 0)], c, m, seg=seg); o.location = (0, y, z)
    return o


# ---------- integration extras ----------------------------------------------------------------------------------------------------------
def services(c, g):
    """Propellant and fuel feeds along the booms, pellet injector track, maintenance platform, spare cassettes, keep-out cones."""
    cs = coll('WORK_HIMS_SERVICES', c)
    D, S = g['D'], g['S']; xp, rp = g['plug']['x'], g['plug']['r']
    for i, (sy, sz) in enumerate(((-1, -1), (-1, 1), (1, -1), (1, 1))):
        og = Vector((0, sy * S / 2, sz * S / 2)); d = (Vector((D, 0, 0)) - og).normalized()
        node = og + d * xp
        stern = Vector((D, sy * SHIP_R * 0.55, sz * SHIP_R * 0.55))
        up = Vector((0, 0, 1)) if sz > 0 else Vector((0, 0, -1))
        side = d.cross(up).normalized()
        poly(f'HIMS_E{i + 1}_PROPELLANT_FEED', [tuple(stern + side * 3), tuple(node + side * 3)], cs, M['prop'], 0.6)
        poly(f'HIMS_E{i + 1}_FUEL_PELLET_FEED', [tuple(stern - side * 3), tuple(node - side * 3)], cs, M['fuel'], 0.4)
        poly(f'HIMS_E{i + 1}_PELLET_INJECTOR_TRACK', [tuple(og + d * max(1.0, xp - rp)), tuple(og)], cs, M['fuel'], 0.25)
        pf = box(f'HIMS_E{i + 1}_MAINT_PLATFORM', node + d * 22 + up * 8, (14.0, 14.0, 0.6), cs, M['platform'])
        pf.rotation_euler = Vector((1, 0, 0)).rotation_difference(d).to_euler()
        mid = node + (stern - node) * 0.55
        for k in range(3):
            rk = box(f'HIMS_E{i + 1}_SPARE_CASSETTE_{k + 1}', mid + (stern - node).normalized() * (k * 9.0) + up * 6, (6.0, 4.0, 3.0), cs, M['rack'])
            rk.rotation_euler = Vector((1, 0, 0)).rotation_difference((stern - node).normalized()).to_euler()
        # the burn's unshadowed directions (away from the ship): nothing may be placed there; drawn as a 70 deg keep-out cone
        cone(f'HIMS_E{i + 1}_KEEP_OUT_UNSHADOWED', og, tuple(-d), 70.0, 45.0, cs, M['keep'])
    vlabel('HIMS_SERVICES_LABEL', 'Propellant feed (green) and fuel pellet feed (gold) along each boom; pellet injector track plug-to-burn; '
           'maintenance platform and 3 spare nose cassettes per boom; red cones: unshadowed burn view (keep out). Routing PROTOTYPE.',
           (0, -S / 2 - 80, S / 2 + 140), 16.0, cs).hide_render = True
    return cs


def stern_stack(c, kind, D, yoff=0.0, segment=False, case='NOMINAL'):
    """One HIMS concept at the stern (wall at x = D, dust from -x). Returns (screen positions, field range)."""
    opts = OPT if case == 'NOMINAL' else OPTJ
    nm = dict(P='PASSIVE stern screen (AMPN)', A='A screen + Vertex ring field', B2='B two screens', B3='B three screens',
              C='C screen + deflector 0.3 T')[kind]
    o = opts[nm]; Sx = o['standoff_m']
    if segment:
        cyl(f'HIMS_{kind}_STERN_SEGMENT', D, D + 70, SHIP_R, c, M['ship'], y=yoff)
    cyl(f'HIMS_{kind}_STERN_WALL', D - 0.6, D, SHIP_R * 1.01, c, M['wall'], y=yoff)
    n = o['screens']
    xs = [D - Sx * (1 - j / n) for j in range(n)]
    for j, x in enumerate(xs):
        cyl(f'HIMS_{kind}_SCREEN_{j + 1}', x, x + 0.5, SHIP_R * 1.02, c, M['screen'], y=yoff)
    bar(f'HIMS_{kind}_MAST', (D - Sx, yoff, 0), (D, yoff, 0), 1.2, 1.2, c, M['struct'])
    field = None
    if kind == 'C':
        L = 20.0; r = 50.0
        x1 = D - 0.5; x0 = x1 - L; field = (x0, x1)
        cyl('HIMS_C_FIELD_REGION_0p3T', x0, x1, r, c, M['fieldvol'], y=yoff)
        for k in range(16):
            th = 2 * math.pi * (k + 0.5) / 16
            w = abs(math.cos(th)); yy, zz = r * math.cos(th), r * math.sin(th)
            m = M['go'] if math.cos(th) > 0 else M['ret']
            bar(f'HIMS_C_CONDUCTOR_{k + 1:02d}', (x0, yoff + yy, zz), (x1, yoff + yy, zz), 0.6 + 2.6 * w, 0.6 + 2.6 * w, c, m)
        for x in (x0, x1):
            t_ = torus(f'HIMS_C_END_RETURN_{int(x)}', r, 0.9, c, M['ret'], x=x); t_.location = (0, yoff, 0)
        mg = o['magnet']
        vlabel('HIMS_C_MAGNET_LABEL', f"cos-theta deflector 0.3 T, bore r 50 m, depth 20 m: {mg['I_tot_A'] / 1e6:.0f} MA-turns, "
               f"stored {mg['W_J'] / 1e9:.0f} GJ, magnet {o['magnet_t']:.0f} t", (x0 - 20, yoff - 60, r + 22), 4.0, c)
    if kind == 'A':
        for k in range(6):   # ring far-field label lines (3.3e-6 T): drawn as faint circles round the stack
            t_ = torus(f'HIMS_A_RING_FAR_FIELD_{k}', SHIP_R + 8 + 6 * k, 0.15, c, M['field'], x=D - Sx + 10 * k); t_.location = (0, yoff, 0)
    j = OPTJ[nm] if nm in OPTJ else None
    jt = f"JUSTIFIED: {j['standoff_m']:.0f} m, {j['mass_t']:.0f} t" if j and j.get('closes') else 'JUSTIFIED: does not close'
    title = dict(P='PASSIVE (AMPN reference)', A='HIMS-A: screen + Vertex ring field', B2='HIMS-B: two screens (distributed)',
                 B3='HIMS-B: three screens (distributed)', C='HIMS-C: screen + ionisation + 0.3 T deflector')[kind]
    vlabel(f'HIMS_{kind}_LABEL', f"{title}\nNOMINAL: stand-off {Sx:.1f} m, stack {o['mass_t']:.1f} t | {jt}\n"
           f"screen {o['screen_kg_m2']:.2f} kg/m2 x{n}, holed {o['screen_holed_fraction'] * 100:.2f} %, transit {o['t_transit_ms'] * 1e3:.1f} us",
           (D - 75, yoff - 60, SHIP_R + 40), 4.2, c)
    return xs, field


def paths(c, key, x_wall, yoff, m_by=None, n=None, bevel=0.08):
    out = []
    for k, p in enumerate(TR[key][:n]):
        pts = [(x_wall - TR_WALL[key] + q[0], yoff + q[1], q[2]) for q in p['points']]
        m = M['neutral'] if key == 'neutral_or_unfielded' else (M['ion'] if p['outcome'] == 'turned' else M['hit'])
        poly(f'HIMS_{key}_{k:02d}_{p["species"]}{p["q"]}_{p["outcome"]}', pts, c, m, bevel)
        out.append(pts)
    return out


TR_WALL = dict(C_slab_0p3T=TR['geometry']['C']['wall'], A_ring_far_field=TR['geometry']['A']['wall'], neutral_or_unfielded=TR['geometry']['C']['wall'])


def concept(root, kind, D, yoff):
    c = coll(f'WORK_HIMS_CONCEPT_{kind}', root)
    xs, field = stern_stack(c, kind, D, yoff, segment=True)
    rnd = random.Random(3)
    for k in range(10):   # illustrative incoming grains and debris cones at the first screen
        y, z = rnd.uniform(-35, 35), rnd.uniform(-35, 35)
        poly(f'HIMS_{kind}_DUST_IN_{k}', [(D - 260, yoff + y, z), (xs[0], yoff + y, z)], c, M['dust'], 0.12)
        if k == 0:
            cone(f'HIMS_{kind}_DEBRIS_CONE_{k}', (xs[0] + 0.5, yoff + y, z), (1, 0, 0), 30.0, (xs[1] if len(xs) > 1 else D) - xs[0] - 0.5, c, M['cloud'])
    if kind == 'C':
        paths(c, 'C_slab_0p3T', D, yoff, n=24)
        paths(c, 'neutral_or_unfielded', D, yoff, n=8)
    elif kind == 'A':
        paths(c, 'A_ring_far_field', D, yoff, n=16)
    vlabel(f'HIMS_{kind}_KEY', 'yellow: incoming grains (ILLUSTRATIVE) | orange cones: debris clouds (ILLUSTRATIVE) | cyan: ion test paths '
           '(SIMULATED, vacuum field) | orange lines: neutrals (SIMULATED)', (D - 75, yoff - 60, -SHIP_R - 30), 3.2, c)
    return c


# ---------- problem overlay -------------------------------------------------------------------------------------------------------------
def overlay(root, g):
    c = coll('WORK_HIMS_PROBLEMS', root)
    D, S = g['D'], g['S']; q = g['coils'][0]; xp = g['plug']['x']
    og = Vector((0, -S / 2, S / 2)); d = (Vector((D, 0, 0)) - og).normalized(); node = og + d * xp
    loc = dict(ENGINE=og + Vector((0, 0, 60)), RING=og + Vector((q['p0'][0], 0, q['p0'][1])), EDDY_SHIELD=og + Vector((q['p1'][0], 0, -q['p1'][1])),
               PLUME=og + Vector((-160, 0, 0)), PLUG=og + d * (xp - g['plug']['r']), NOSE=og + Vector((q['p0'][0], 0, -q['p0'][1])),
               SLUG=og + d * (xp + 2), SHIP=Vector((D + SHIP_L / 2, 0, SHIP_R + 20)), BOOM=node + (Vector((D, -SHIP_R, SHIP_R)) - node) * 0.5,
               STERN_SCREEN=Vector((D - 38, 0, -SHIP_R)), HIMS_MAGNET=Vector((D - 10, 0, 50)), HIMS_A=Vector((D - 64, 0, SHIP_R + 10)),
               QUENCH=node + Vector((0, 0, -25)), CARRIAGE=og + d * (xp * 0.5))
    used = {}
    for p in PR:
        comp = p['components'][0]
        base = loc[comp]
        k = used.get(comp, 0); used[comp] = k + 1
        sphere(f'PROB_{p["id"]}_MARKER', base, 9.0, c, M['prob'], seg=12)
        if k == 0:
            for comp2 in p['components'][1:]:
                if comp2 in loc:
                    poly(f'PROB_{p["id"]}_LINK_{comp2}', [tuple(base), tuple(loc[comp2])], c, M['prob'], 1.0)
        t = p['title'] if len(p['title']) < 46 else p['title'][:44] + '..'
        vlabel(f'PROB_{p["id"]}_LABEL', f'{p["id"]} [{p["status"]}] {t}', base + Vector((14, -12, 40 + 30 * k)), 18.0, c, M['probtxt'])
    vlabel('PROB_KEY', 'Engineering Problems Register (lab/studies/vertex-compact-engine/vertex-hims/PROBLEMS.md): red markers at the components each problem lives in',
           (0, -S / 2, S / 2 + 380), 30.0, c, M['probtxt'])
    return c


# ---------- sequence (frames 1-200) ----------------------------------------------------------------------------------------------------
def sequence(root, D, yoff, cam):
    """HIMS-C interaction sequence in the concept-C close-up. Time stretched (the real event lasts about 13 us)."""
    c = coll('WORK_HIMS_SEQUENCE', root)
    sc = bpy.context.scene; sc.frame_start, sc.frame_end = 1, 200; sc.render.fps = 24
    xs0 = D - OPT['C screen + deflector 0.3 T']['standoff_m']
    y0, z0 = TR['C_slab_0p3T'][0]['points'][0][1], TR['C_slab_0p3T'][0]['points'][0][2]
    gr = sphere('SEQ_GRAIN_ILLUSTRATIVE', (D - 260, yoff + y0, z0), 1.2, c, M['grain'])
    gr.keyframe_insert('location', frame=1); gr.location = (xs0, yoff + y0, z0); gr.keyframe_insert('location', frame=40)
    gr.scale = (1, 1, 1); gr.keyframe_insert('scale', frame=40); gr.scale = (0.01, 0.01, 0.01); gr.keyframe_insert('scale', frame=41)
    fl = sphere('SEQ_FLASH_ILLUSTRATIVE', (xs0, yoff + y0, z0), 1.0, c, M['flash'])
    for f, s in ((1, 0.01), (40, 0.01), (44, 9.0), (52, 0.01)):
        fl.scale = (s, s, s); fl.keyframe_insert('scale', frame=f)
    cl = cone('SEQ_CLOUD_ILLUSTRATIVE', (xs0 + 0.5, yoff + y0, z0), (1, 0, 0), 30.0, 17.0, c, M['cloud'])
    for f, s in ((1, 0.01), (44, 0.01), (90, 1.0), (110, 1.0), (125, 0.01)):
        cl.scale = (s, s, s); cl.keyframe_insert('scale', frame=f)
    rnd = random.Random(5)
    def ride(key, n, f0, f1, m, size):
        for k, p in enumerate(TR[key][:n]):
            pts = [Vector((D - TR_WALL[key] + q[0], yoff + q[1], q[2])) for q in p['points']]
            b = sphere(f'SEQ_{key}_{k:02d}', pts[0], size, c, m, seg=8)
            b.scale = (0.01, 0.01, 0.01); b.keyframe_insert('scale', frame=1); b.keyframe_insert('scale', frame=f0 - 1)
            b.scale = (1, 1, 1); b.keyframe_insert('scale', frame=f0)
            for j, q in enumerate(pts):
                b.location = q; b.keyframe_insert('location', frame=f0 + (f1 - f0) * j / max(1, len(pts) - 1))
            if key == 'neutral_or_unfielded':
                mk = sphere(f'SEQ_RESIDUAL_MARK_{k:02d}', pts[-1] + Vector((0.4, 0, 0)), 1.6, c, M['mark'], seg=8)
                mk.scale = (0.01, 0.01, 0.01); mk.keyframe_insert('scale', frame=1); mk.keyframe_insert('scale', frame=f1)
                mk.scale = (1, 0.3, 1); mk.keyframe_insert('scale', frame=f1 + 4)
    ride('C_slab_0p3T', 24, 90, 170, M['ion'], 0.7)
    ride('neutral_or_unfielded', 8, 90, 150, M['neutral'], 0.9)
    stages = [(1, 'A  incoming grain (ILLUSTRATIVE): ~1 mm, 4,800 km/s, 87 MJ'), (41, 'A  impact on the first screen: vaporisation and ionisation (EXTRAPOLATED rules)'),
              (52, 'B  debris cloud expands, 30 deg cone (ILLUSTRATIVE)'), (90, 'C  isolated ions turned by 0.3 T (SIMULATED test particles; plasma beta NOT modelled)'),
              (150, 'D  neutrals and unturned debris reach the wall: residual damage (SIMULATED share)'),
              (175, 'Collective cloud behaviour is unresolved (ENG-011): deflection is not demonstrated for the dense cloud')]
    for f, s in stages:
        t = vlabel(f'SEQ_CAPTION_{f:03d}', s, (-0.53, -0.27, -1.0), 0.026, c, rot=(0, 0, 0)); t.parent = cam
        nxt = next((g for g, _ in stages if g > f), 201)
        for fr, vis in ((1, f == 1), (f, True), (nxt, False)):
            t.hide_render = not vis; t.hide_viewport = not vis
            t.keyframe_insert('hide_render', frame=fr); t.keyframe_insert('hide_viewport', frame=fr)
    return c


# ---------- main ------------------------------------------------------------------------------------------------------------------------
def shots(cv, groups, rd):
    sc = bpy.context.scene
    for vn, (cam, show, tech) in cv.items():
        for cname, cc in groups.items():
            cc.hide_render = cname not in show
        sc.render.engine = 'BLENDER_WORKBENCH' if tech else 'BLENDER_EEVEE'
        sc.display.shading.light = 'FLAT' if tech else 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'
        for ob in bpy.data.objects:
            if ob.type == 'MESH' and ob.data.materials and ob.data.materials[0].name == 'RON_PHOTON_NEUTRON_ILLUSTRATIVE':
                ob.hide_render = True
            if ob.type == 'CURVE' and '_FIELD_' in ob.name:
                ob.hide_render = vn in ('nozzle_closeup', 'services', 'braking_dust', 'stern_C_perspective', 'integration')
        sc.camera = cam; sc.render.filepath = str(rd / f'hims_{vn}.png'); bpy.ops.render.render(write_still=True)
        print('rendered', vn, flush=True)
    for cc in groups.values():
        cc.hide_render = False


def main():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    setup_render()
    sc = bpy.context.scene; root = sc.collection
    cams = coll('30_CAMERAS', root, 'NONE')
    integ, g, o = ship_stack(MAIN, 'WORK_HIMS_INTEGRATION', root, sims=True, screen_deployed=True)
    D, S = g['D'], g['S']
    for ob in list(integ.all_objects):          # the passive screen is replaced by the HIMS-C stack
        if ob.name.endswith(('STERN_SCREEN', 'STERN_MAST')):
            bpy.data.objects.remove(ob)
    services(integ, g)
    hc = coll('WORK_HIMS_STERN_C', integ)
    stern_stack(hc, 'C', D)
    dust = coll('WORK_HIMS_DUST_ILLUSTRATIVE', root)
    rnd = random.Random(11)
    for k in range(30):
        y, z = rnd.uniform(-40, 40), rnd.uniform(-40, 40)
        poly(f'HIMS_DUST_STERN_{k}', [(-0.6 * D, y, z), (D - 38.2, y, z)], dust, M['dust'], 0.3)
    q = g['coils'][0]
    for i, (sy, sz) in enumerate(((-1, -1), (-1, 1), (1, -1), (1, 1))):
        og = Vector((0, sy * S / 2, sz * S / 2))
        for k in range(6):
            a = 2 * math.pi * k / 6
            y, z = og.y + q['p0'][1] * math.cos(a), og.z + q['p0'][1] * math.sin(a)
            poly(f'HIMS_DUST_ENGINE{i + 1}_{k}', [(-0.6 * D, y, z), (q['p0'][0], y, z)], dust, M['dust'], 0.25)
    vlabel('HIMS_BRAKING_LABEL', 'BRAKING: ship turned engines-first; dust (yellow, ILLUSTRATIVE) arrives from the left. Engine faces: armour only '
           '(ENG-014). Stern: HIMS-C stack, 0.3 T field region (blue, SIMULATED region).', (-0.6 * D, -S / 2, S / 2 + 160), 26.0, dust)
    base = -S - 900.0
    kinds = ['P', 'A', 'B2', 'B3', 'C']
    cons = {k: concept(root, k, D, base - 260 * j) for j, k in enumerate(kinds)}
    probs = overlay(root, g)
    yC = base - 260 * 4
    groups = dict(integ=integ, dust=dust, probs=probs, **{f'c_{k}': v for k, v in cons.items()})
    mid = Vector(((D + SHIP_L) / 2, 0, 0)); W = D + SHIP_L + S
    e1 = Vector((0, -S / 2, -S / 2)); R = q['p1'][1]
    d1 = (Vector((D, 0, 0)) - e1).normalized(); node1 = e1 + d1 * g['plug']['x']
    cv = {
        'integration': (camera('CAM_integration', mid + Vector((-0.6 * W, -0.9 * W, 0.5 * W)), mid, cams, lens=40), {'integ'}, False),
        'integration_side': (camera('CAM_integration_side', mid + Vector((0, -3 * W, 0)), mid, cams, ortho=1.15 * W), {'integ'}, True),
        'nozzle_closeup': (camera('CAM_nozzle', e1 + Vector((q['p0'][0] - 1.2 * R, -1.6 * R, 0.6 * R)), e1 + Vector((q['p0'][0], 0, -0.4 * R)), cams, lens=28), {'integ'}, False),
        'services': (camera('CAM_services', node1 + Vector((-30, -110, 60)), node1 + d1 * 25, cams, lens=30), {'integ'}, False),
        'braking_dust': (camera('CAM_braking', mid + Vector((-0.75 * W, -0.95 * W, 0.45 * W)), mid + Vector((-0.2 * D, 0, 0)), cams, lens=35), {'integ', 'dust'}, False),
        'stern_C_perspective': (camera('CAM_stern_C', Vector((D - 140, -150, 85)), Vector((D - 20, 0, 0)), cams, lens=30), {'integ', 'dust'}, False),
        'concepts_lineup': (camera('CAM_concepts', Vector((D - 40, base - 520 - 900, 0)), Vector((D - 40, base - 520, 0)), cams, ortho=1250), {f'c_{k}' for k in kinds}, True),
        'concept_C_endview': (camera('CAM_C_end', Vector((D - 25, yC, 0)), Vector((D, yC, 0)), cams, ortho=200), {'c_C'}, True),
        'problems_overlay': (camera('CAM_problems', mid + Vector((0, -3 * W, 0.2 * W)), mid + Vector((0, 0, 0.12 * W)), cams, ortho=1.35 * W), {'integ', 'probs'}, True),
    }
    for j, k in enumerate(kinds):
        yk = base - 260 * j
        cv[f'concept_{k}'] = (camera(f'CAM_concept_{k}', Vector((D - 75, yk - 400, 22)), Vector((D - 75, yk, 22)), cams, ortho=270), {f'c_{k}'}, True)
    lc = cv['concepts_lineup'][0]; lc.location = (D - 60, base - 520, 1500); lc.rotation_euler = (0, 0, math.pi / 2)
    lc.data.ortho_scale = 1250
    cseq = camera('CAM_sequence', Vector((D - 90, yC - 150, 55)), Vector((D - 25, yC, 0)), cams, lens=32)
    seq = sequence(root, D, yC, cseq) if ANIM else None
    if seq:
        groups['seq'] = seq; cv['concept_C'][1].add('seq')
        seq.hide_render = True
    sc.camera = cv['integration'][0]
    out = HERE / 'REVIEW_HIMS.blend'
    sc.frame_set(1)
    bpy.ops.file.pack_all(); bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
    rd = HERE / 'renders'; rd.mkdir(exist_ok=True)
    if RENDER:
        if seq:
            sc.frame_set(110)
        shots(cv, groups, rd)
    if ANIM and RENDER:
        for cname, cc in groups.items():
            cc.hide_render = cname not in ('c_C', 'seq')
        clutter = [ob for ob in cons['C'].all_objects if any(t in ob.name for t in ('_C_slab_', 'neutral_or', 'DEBRIS_CONE', 'DUST_IN', '_LABEL', '_KEY'))]
        for ob in clutter:
            ob.hide_render = True
        sc.camera = cseq; sc.render.engine = 'BLENDER_EEVEE'
        sc.render.resolution_x, sc.render.resolution_y = 960, 540
        (rd / 'anim').mkdir(exist_ok=True); sc.frame_step = 3
        sc.render.filepath = str(rd / 'anim' / 'f_'); bpy.ops.render.render(animation=True)
        sc.frame_step = 1; sc.render.resolution_x, sc.render.resolution_y = 1280, 720
        for cc in groups.values():
            cc.hide_render = False
        for ob in clutter:
            ob.hide_render = False
    sc.camera = cv['integration'][0]; sc.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)


main()
