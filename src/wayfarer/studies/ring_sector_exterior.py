"""M4 slice 1 (TODO "Constructed exterior"): NONCANON exterior construction study of one ring A sector, built in memory as ART_RS_*
objects on the saved vehicle (nothing is saved, no generator reads this).

Function: the ring frame must read as construction, with the pressure sector, the frame, the water/storage fill and the service
equipment told apart. Fixed: every ring dimension in `habitat_ring` (outer r 30 m, frame r 24.5-30 m x 4 m, sectors r 25-28.7 m x
3.5 m recessed 0.25 m per side, six spokes at 60 deg), so the sweep (half-depth 2.15 m), the 1.5 m spar clearance and the docking
corridors cannot change; the inner hoop, crew tubes and hatches are left as built (the rescue routes are unresolved). Unknown and not
modelled: the water/storage split, any shielding credit, the ring mass distribution, frame section, stiffness and load path (OD-016).
Design freedom (PROTOTYPE judgment): 15 deg assembly segments with web frames at the joints, cassette fill with inspection covers,
heavy flank frames and a recess lip round the pressure sector, a service node housing at each structural spoke, a rim ID stripe.

The unit spans -67.5..+67.5 deg about sector 1_1 so both flanking service nodes are whole; the rest of ring A is rebuilt plain.
The screen keeps every vertex inside the frame envelope and outside the sector envelope.

    /snap/bin/blender -b --python src/wayfarer/studies/ring_sector_exterior.py -- --out runs/<stamp>-ring-sector
"""
from pathlib import Path
import argparse
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation')]
from spec import load
import habitat_ring as hr

RING = 1
SEG_DEG = 15.0          # assembly segment pitch (24 per ring), PROTOTYPE
UNIT_DEG = 67.5         # half-span of the studied unit: joint to joint round both structural spokes
GROOVE = 0.08           # rim joint groove, tangential (m)
WEB = 0.30              # web frame at each joint, tangential (m)
FLANK = 0.35            # heavy frame either side of the pressure sector, tangential (m)
INSET = 0.04            # cassette and groove inset from the frame faces (m)
COVER = 0.025           # inspection cover proud of the cassette face (still inside the frame face)
LIP = 0.20              # recess lip round the sector, radial (m)
NODE_DEG = 4.0          # service node half-span about each structural spoke
NODE_R = 27.2           # service node outer radius (spoke side of the fill)
STRIPE_U = 0.30         # rim ID stripe half-width, axial (m)
STRIPE_DEPTH = 0.02     # stripe is the outer 2 cm of the hoop, never proud of r 30

PALETTE = dict(frame=(.52, .58, .62), joint=(.16, .19, .22), cassette=(.30, .40, .44), cover=(.42, .52, .56),
               pressure=(.80, .76, .67), stripe=(.80, .42, .16), service=(.30, .26, .16), service_cover=(.78, .60, .24),
               plain_frame=(.46, .57, .63), plain_fill=(.34, .50, .55), scale=(1.0, .45, .1))


def parts(s):
    """Ring-local parts (vertices (u, r cos t, r sin t), sector 1_1 at t = 0): name, class, vertices, faces."""
    r = s['habitat_ring']; R0, R1, RS0, RS1, RO = r['frame_inner_radius_m'], r['sector_outer_radius_m'], r['sector_inner_radius_m'], r['sector_outer_radius_m'], hr.outer(s)
    H = r['frame_axial_m']/2; HS = r['sector_axial_m']/2; half = hr.sector_arc(s)/2; n = r['display']['hoop_facets']; rad = math.radians
    out = []

    def add(name, cls, u0, u1, r0, r1, t0, t1, facets=None):
        k = facets or max(2, math.ceil(n*(t1-t0)/math.tau))
        vs, fs = hr.ring_solid(u0, u1, r0, r1, t0, t1, k)
        out.append(dict(name=f'ART_RS_{name}', cls=cls, vertices=vs, faces=fs, t0=t0, t1=t1))

    joints = [rad(-UNIT_DEG+SEG_DEG*i) for i in range(int(2*UNIT_DEG/SEG_DEG)+1)]
    mid = lambda dr: dr/((RS0+RS1)/2)                   # tangential metres to radians at mid-fill
    # Outer hoop: one segment per joint pair with a dark groove between; the pressure segment carries the ID stripe in its outer 2 cm.
    for i, (a, b) in enumerate(zip(joints, joints[1:])):
        g = GROOVE/2/RO
        pressure = a < 0 < b
        add(f'Hoop_Seg_{i:02d}', 'frame', -H, H, R1, RO-(STRIPE_DEPTH if pressure else 0), a+g, b-g)
        if pressure:
            add('Hoop_Seg_Stripe', 'stripe', -STRIPE_U, STRIPE_U, RO-STRIPE_DEPTH, RO, a+g, b-g)
            add('Hoop_Seg_Rim_Fore', 'frame', STRIPE_U, H, RO-STRIPE_DEPTH, RO, a+g, b-g)
            add('Hoop_Seg_Rim_Aft', 'frame', -H, -STRIPE_U, RO-STRIPE_DEPTH, RO, a+g, b-g)
    for i, a in enumerate(joints):
        g = GROOVE/2/RO
        add(f'Hoop_Joint_{i:02d}', 'joint', -H+INSET, H-INSET, R1, RO-INSET, a-g, a+g, 1)
    # Fill: web frames at the joints, flank frames at the sector, cassettes between with two inspection covers per face.
    for i, a in enumerate(joints):
        w = mid(WEB)/2
        add(f'Web_{i:02d}', 'frame', -H, H, RS0, RS1, a-w, a+w, 1)
    f = mid(FLANK)
    for side in (-1, 1):
        t0, t1 = sorted((side*half, side*(half+f)))
        add(f'Flank_{"P" if side > 0 else "N"}', 'frame', -H, H, RS0, RS1, t0, t1, 1)
        j = rad(SEG_DEG/2)*side
        t0, t1 = sorted((side*(half+f), j-side*mid(WEB)/2))
        add(f'Flank_Fill_{"P" if side > 0 else "N"}', 'frame', -H, H, RS0, RS1, t0, t1, 1)
    # Sector recess: lips at the inner and outer edge (the flank frames close the sides) and the pressure-hull face finish.
    for side in (-1, 1):
        u0, u1 = sorted((side*HS, side*H))
        add(f'Lip_In_{side:+d}', 'frame', u0, u1, RS0, RS0+LIP, -half, half)
        add(f'Lip_Out_{side:+d}', 'frame', u0, u1, RS1-LIP, RS1, -half, half)
        u0, u1 = sorted((side*HS, side*(HS+0.015)))
        add(f'Pressure_Face_{side:+d}', 'pressure', u0, u1, RS0+LIP, RS1-LIP, -half+0.2/RS0, half-0.2/RS0)
    nodes = [rad(60.0), rad(-60.0)]
    for i, (a, b) in enumerate(zip(joints, joints[1:])):
        if a < 0 < b:
            continue
        lo, hi = a+mid(WEB)/2, b-mid(WEB)/2
        node = next((c for c in nodes if lo < c < hi), None)
        spans = [(lo, hi, RS0)] if node is None else [(lo, node-rad(NODE_DEG), RS0), (node-rad(NODE_DEG), node+rad(NODE_DEG), NODE_R), (node+rad(NODE_DEG), hi, RS0)]
        for k, (c0, c1, rin) in enumerate(spans):
            if c1-c0 < 1e-6:
                continue
            add(f'Cassette_{i:02d}_{k}', 'cassette', -H+INSET, H-INSET, rin, RS1, c0, c1)
            m = 0.4/RS1
            tiers = [(rin+0.4, (rin+RS1)/2-0.1), ((rin+RS1)/2+0.1, RS1-0.4)] if RS1-rin > 2.5 else [(rin+0.3, RS1-0.3)]
            for side in (-1, 1):
                u0, u1 = sorted((side*(H-INSET), side*(H-INSET+COVER)))
                for q, (p0, p1) in enumerate(tiers):
                    add(f'Cover_{i:02d}_{k}_{q}_{side:+d}', 'cover', u0, u1, p0, p1, c0+m, c1-m)
        if node is not None:
            c0, c1 = node-rad(NODE_DEG), node+rad(NODE_DEG)
            add(f'Service_Node_{i:02d}', 'service', -H+INSET, H-INSET, RS0, NODE_R, c0, c1)
            for side in (-1, 1):
                u0, u1 = sorted((side*(H-INSET), side*(H-INSET+COVER)))
                add(f'Service_Cover_{i:02d}_{side:+d}', 'service_cover', u0, u1, RS0+0.3, NODE_R-0.3, c0+0.3/RS0, c1-0.3/RS0)
    # Plain remainder of the outer hoop and of fills 1 and 3 (fill 2 and the inner hoop stay the built objects).
    lo, hi = rad(UNIT_DEG), math.tau-rad(UNIT_DEG)
    add('Plain_Hoop_Outer', 'plain_frame', -H, H, R1, RO, lo, hi)
    s1 = [q for q in hr.sectors(s) if q['ring'] == RING]
    add('Plain_Fill_1', 'plain_fill', -H, H, RS0, RS1, lo, s1[1]['angle']-half)
    add('Plain_Fill_3', 'plain_fill', -H, H, RS0, RS1, s1[2]['angle']+half, hi)
    return out


def screen(s, ps):
    """Every vertex inside the frame envelope (r 24.5-30, |u| <= frame half-depth) and no part inside the sector envelope."""
    r = s['habitat_ring']; H = r['frame_axial_m']/2; half = hr.sector_arc(s)/2; eps = 1e-6; fails = []
    for p in ps:
        for u, y, z in p['vertices']:
            rr = math.hypot(y, z)
            if abs(u) > H+eps or rr < r['frame_inner_radius_m']-eps or rr > hr.outer(s)+eps:
                fails.append(f"{p['name']} outside the frame envelope at u {u:.3f}, r {rr:.3f}"); break
        # Sector envelope: |u| < sector half-depth, r 25-28.7, |t| < half arc. A part enters it only if its own span overlaps all three.
        us = [v[0] for v in p['vertices']]; rs = [math.hypot(v[1], v[2]) for v in p['vertices']]
        t_overlap = p['t0'] < half-eps and p['t1'] > -half+eps
        if t_overlap and min(us) < r['sector_axial_m']/2-eps and max(us) > -r['sector_axial_m']/2+eps and min(rs) < r['sector_outer_radius_m']-eps and max(rs) > r['sector_inner_radius_m']+eps:
            fails.append(f"{p['name']} enters the sector pressure envelope")
    return fails


def summary(s, ps):
    counts = {}
    for p in ps:
        counts[p['cls']] = counts.get(p['cls'], 0)+1
    return dict(study='M4 slice 1: ring A sector exterior construction (NONCANON, PROTOTYPE, nothing saved)', ring=RING,
                unit_deg=[-UNIT_DEG, UNIT_DEG], segment_pitch_deg=SEG_DEG, parts=counts, screen=screen(s, ps) or 'PASS',
                envelope=dict(frame_r=[s['habitat_ring']['frame_inner_radius_m'], hr.outer(s)], frame_half_u=s['habitat_ring']['frame_axial_m']/2,
                              sweep_half_u=hr.sweep_half(s), spar_clearance_m=round(hr.spar_clearance_m(s), 3)),
                not_modelled='water/storage split, shielding credit, ring mass distribution, frame section, stiffness, load path (OD-016); cassette withdrawal path; utility routing at the service nodes',
                untouched='inner hoop, crew tubes and hatches, spokes, sector envelopes, ring B')


# ---------- Blender (preview.py study hook and close-ups) ------------------------------------------------------------------

note = 'STUDY ring A sector exterior (ART_RS, NONCANON, PROTOTYPE construction inside the unchanged frame envelope)'


def spec(s):
    return s


def apply(s, state=None):
    import bpy
    from mathutils import Matrix
    from common import material
    hide = {f'Ring_{RING}_Hoop_Outer', f'Ring_{RING}_Fill_1', f'Ring_{RING}_Fill_3'}
    for o in bpy.data.objects:
        if o.name in hide:
            o.hide_render = o.hide_viewport = True
    rotor = bpy.data.objects[f'Rotor_{RING}']; asm = bpy.data.objects['Assembly_HABITAT']
    world = asm.matrix_world @ rotor.matrix_world          # rotor pose at the current frame (preset already posed)
    mats = {k: material(f'ART_RS_{k}', v) for k, v in PALETTE.items()}
    for p in parts(s):
        me = bpy.data.meshes.new(p['name']); me.from_pydata(p['vertices'], [], p['faces']); me.update(); me.materials.append(mats[p['cls']])
        ob = bpy.data.objects.new(p['name'], me); bpy.context.scene.collection.objects.link(ob); ob.matrix_world = world
        ob['geometry_status'] = 'PROTOTYPE'; ob['study'] = 'ring_sector_exterior'
    # Non-diegetic 1.8 m scale reference beside ring A's aft face, off the sector at t = 10 deg.
    h = s['prototype']['human_height_m']; t = math.radians(10.0); rr = 27.0
    bpy.ops.mesh.primitive_cylinder_add(radius=0.22, depth=h, location=(0, 0, 0))
    fig = bpy.context.active_object; fig.name = 'ART_RS_Scale_Figure'; fig.data.materials.append(mats['scale']); fig['kind'] = 'scale_reference'
    fig.matrix_world = world @ Matrix.Translation((-s['habitat_ring']['frame_axial_m']/2-0.45, rr*math.cos(t), rr*math.sin(t))) @ Matrix.Rotation(t-math.pi/2, 4, 'X')
    return world


def close_ups(s, out, size, overlay=True):
    import bpy
    from mathutils import Vector, Matrix
    from common import pose_configuration
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
    pose_configuration(s, 'COAST'); bpy.context.scene.frame_set(1)
    if overlay:
        world = apply(s)
    else:      # the generated construction (habitat_ring.construction) as saved
        world = bpy.data.objects['Assembly_HABITAT'].matrix_world @ bpy.data.objects[f'Rotor_{RING}'].matrix_world
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'; sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True; sh.cavity_type = 'WORLD'
    sh.show_backface_culling = False; sc.world.color = (.055, .075, .10)
    sc.render.resolution_x, sc.render.resolution_y = size, round(size*.75); sc.render.image_settings.file_format = 'PNG'
    cam = bpy.data.objects.new('ART_RS_Camera', bpy.data.cameras.new('ART_RS_Camera')); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.clip_start = 0.1; cam.data.clip_end = 600
    local = lambda u, r, deg: world @ Vector((u, r*math.cos(math.radians(deg)), r*math.sin(math.radians(deg))))
    H = s['habitat_ring']['frame_axial_m']/2
    views = {
        # whole unit from aft and outboard: the aft face, the rim and both service nodes
        'unit_aft': (local(-58, 30, 0), local(-H, 22, 0), 24),
        # rim and aft face over the pressure segment, both rings in frame
        'rim_oblique': (local(-12, 44, 22), local(0, 28.5, 4), 35),
        # the sector recess and a 1.8 m figure at the aft face
        'human_scale': (local(-9.5, 24.0, 22), local(-H, 27.0, 6), 30),
    }
    paths = []
    for name, (loc, look, lens) in views.items():
        z = (loc-look).normalized()
        up = (world.to_3x3() @ Vector((0, math.cos(math.radians(8)), math.sin(math.radians(8))))).normalized()
        x = up.cross(z).normalized(); y = z.cross(x)
        cam.location = loc; cam.rotation_euler = Matrix((x, y, z)).transposed().to_euler(); cam.data.lens = lens
        p = out/f'ring_sector_{name}.png'; sc.render.filepath = str(p); bpy.ops.render.render(write_still=True); paths.append(p.name)
        print('WF_RING_SECTOR', name, flush=True)
    return paths


def main(out, size, whole, overlay=True):
    s = load(ROOT)[0]; out.mkdir(parents=True, exist_ok=True)
    ps = parts(s); result = summary(s, ps)
    print('WF_RING_SECTOR screen', result['screen'], flush=True)
    if whole:
        import preview
        preview.render(ROOT, ['side', 'top', 'threequarter', 'habitat_detail'], size, 'COAST', out, study=sys.modules[__name__], quality='draft')
    result['renders'] = close_ups(s, out, size, overlay)
    (out/'ring_sector.json').write_text(json.dumps(result, indent=1)+'\n')
    print('WF_RING_SECTOR done', out, flush=True)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); ap.add_argument('--size', type=int, default=1024)
    ap.add_argument('--no-whole', action='store_true'); ap.add_argument('--saved', action='store_true', help='render the saved generated rings, no overlay')
    a = ap.parse_args(argv)
    main(a.out if a.out.is_absolute() else ROOT/a.out, a.size, not a.no_whole, not a.saved)
