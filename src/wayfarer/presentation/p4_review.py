"""Phase 4 review set (docs/PHASE4_PLAN.md section 3.2): the matched cameras of the S1 grammar study, rendered from the saved assets in
the selected exterior grammar look ([production.exterior], owner S1 selection 2026-10-24) or in the pre-Phase-4 hero look, so every slice
compares against the same images. Presentation only: the vehicle is posed and dressed in memory and never saved.

Views (shared stations, never fixed numbers): ship_34, ship_side, rings_34 (whole ship); brow_sector, crown_bay, human_crown (forward);
ring_segment, human_ring (ring A, the pressure segment farthest from the blades in the posed frame); blade_clamp, blade_edge, blade_35m,
blade_root (radiator 1); spine (the casing between two blades). Light: one sun 40 deg from aft, azimuth -20 deg (presentation choice,
departure pointing OPEN), no fill; COAST at +2 EV editorial, the matched COAST/IGNITION pair (15!A222) with --pair. The orange figures are
1.8 m scale references, not EVA positions.

    /snap/bin/blender -b --python src/wayfarer/presentation/p4_review.py -- --out runs/<stamp>-p4-review [--look grammar|hero]
        [--views ...] [--size 1600] [--samples 48] [--pair] [--label "S2"]
    python3 src/wayfarer/presentation/p4_review.py --pairs <before_dir> <after_dir> <out_dir>    (side-by-side sheets, system Python + PIL)
"""
from pathlib import Path
import argparse
import itertools
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation')]

VIEWS = ('ship_34', 'ship_side', 'rings_34', 'brow_sector', 'crown_bay', 'human_crown', 'ring_segment', 'human_ring', 'blade_clamp',
         'blade_edge', 'blade_35m', 'blade_root', 'spine')
PAIR_VIEWS = ('ship_34', 'rings_34')
SUN = (40.0, -20.0)          # degrees from aft, azimuth about +X from +Y (the m8_exterior / S1 convention)


def ring_frame(s):
    import habitat_ring as hr
    r = s['habitat_ring']
    return dict(R0=r['frame_inner_radius_m'], RS0=r['sector_inner_radius_m'], RS1=r['sector_outer_radius_m'], RO=hr.outer(s),
                H=r['frame_axial_m']/2, HS=r['sector_axial_m']/2, half=hr.sector_arc(s)/2, sweep=hr.sweep_half(s))


def rotor_world(ring):
    """World matrix of a ring's rotor at the posed frame (ring-local frame of habitat_ring: u along the axis, r cos t, r sin t)."""
    import bpy
    return bpy.data.objects[f'Rotor_{ring}'].matrix_world.copy()


def ring_aft_sign():
    """+1 if ring-local +u points aft (-X world) for ring A, else -1 (the ring cameras look at the aft flank)."""
    from mathutils import Vector
    return 1 if (rotor_world(1).to_3x3() @ Vector((1, 0, 0))).x < 0 else -1


def clear_sector(s, w):
    """Local angle (deg) of the ring A pressure segment whose posed world azimuth lies farthest from the three blades."""
    import habitat_ring as hr
    from mathutils import Vector
    blades = [math.radians(s['prototype']['radiator_phase_deg']+120*k) for k in range(3)]
    best = None
    for q in (x for x in hr.sectors(s) if x['ring'] == 1):
        p = w.to_3x3() @ Vector((0, math.cos(q['angle']), math.sin(q['angle']))); az = math.atan2(p.z, p.y)
        d = min(abs(math.remainder(az-b, math.tau)) for b in blades)
        if best is None or d > best[0]:
            best = (d, math.degrees(q['angle']))
    return best[1]


def frames(s):
    """Whole-ship and forward cameras: (focus, direction-or-eye, corners or None, lens)."""
    from mathutils import Vector
    import drive_manifold
    import forward_shield as fsh
    import habitat_ring as hr
    st = fsh.stations(s); cr = fsh.crown(s); R = st['shield_r']; b = cr['bays'][0]['azimuth']
    u = Vector((0, math.cos(b), math.sin(b))); t = Vector((0, -math.sin(b), math.cos(b)))
    box = lambda x0, x1, r: [Vector(p) for p in itertools.product((x0, x1), (-r, r), (-r, r))]
    dm = drive_manifold.stations(s); xa, xb = hr.centers(s)
    out = {}
    out['ship_34'] = (Vector(((dm['exit']+st['lance_tip'])/2, 0, 0)), Vector((-.55, 0, 0))+u*.75-t*.55, box(dm['exit']-6, st['lance_tip'], R), 40.0)
    out['ship_side'] = (Vector(((dm['exit']+st['lance_tip'])/2, 0, 0)), Vector((-.08, 0, 0))+u*1.0-t*.10, box(dm['exit']-6, st['lance_tip'], R), 50.0)
    # Between two blades on the sun side (the bisector nearest the sun azimuth), from aft and outboard: both rings against the Brow.
    ph = s['prototype']['radiator_phase_deg']
    beta = min((math.radians(ph+60+120*k) for k in range(3)), key=lambda a_: abs(math.remainder(a_-math.radians(SUN[1]), math.tau)))
    out['rings_34'] = (Vector((xa+3, 18*math.cos(beta), 18*math.sin(beta))), Vector((xa-30, 72*math.cos(beta), 72*math.sin(beta))), None, 24.0)
    tgt = Vector((fsh.skin_aft_at(s, 22.0), 0, 0))+u*22.0+t*1.5
    out['brow_sector'] = (tgt, tgt+Vector((-17.0, 0, 0))+u*9.0-t*9.0, None, 24.0)
    tgt = Vector((cr['x0']-.3, 0, 0))+u*43.6
    out['crown_bay'] = (tgt, tgt+Vector((-13.0, 0, 0))+u*9.0-t*7.0, None, 30.0)
    tgt = Vector((cr['x0']-.4, 0, 0))+u*42.7+t*2.2
    out['human_crown'] = (tgt, tgt+Vector((-6.5, 0, 0))+u*2.6-t*4.2, None, 28.0)
    # Spine: the casing between two blades on the sun side, from outboard and aft of the rings.
    out['spine'] = (Vector((xa-40, 6.5*math.cos(beta), 6.5*math.sin(beta))), Vector((xa-70, 34*math.cos(beta), 34*math.sin(beta))), None, 28.0)
    return out


def ring_cameras(s, tc):
    """Ring A cameras on its pressure segment at local angle tc (deg), ring-local (eye, target, lens); +u is flipped to the aft flank."""
    from mathutils import Vector
    g = ring_frame(s); H = g['H']
    loc = lambda u, r, deg: Vector((u, r*math.cos(math.radians(tc+deg)), r*math.sin(math.radians(tc+deg))))
    return {'ring_segment': (loc(21, 44, 9), loc(H, 27.4, 0), 40.0),
            'human_ring': (loc(6.5, 31.5, 10), loc(H, 26.6, 3.5), 30.0)}


def blade_cameras(s, sun):
    """Radiator 1 cameras in its blade frame (components/revision.py radiator(): u along the blade from mid-length, v from the root edge,
    z normal to the sheet): (eye, target, lens) in world, looking at the truss face toward the sun."""
    import bpy
    import pack_rad_frame as prf
    b = prf.blade(s); M = bpy.data.objects['Radiator_01'].matrix_world; R = M.to_3x3()
    uh, vh, nh = (R.col[i].normalized() for i in range(3))
    lit = 1.0 if nh.dot(sun) > 0 else -1.0
    P = lambda u, v, z: M @ __import__('mathutils').Vector((u, v, z))
    L, w, h = b['L'], b['w'], b['half']; u7 = b['stations'][7]
    clamp = P(-L/2-.05, w*5/6, lit*h); edge = P(-L/2, w*.7, 0); mid = P(u7, w*.6, 0); root = P(-L/2+20, 1.5, lit*h)
    return {'blade_clamp': (clamp-uh*3.0+nh*lit*2.5+vh*2.0, clamp, 35.0),
            'blade_edge': (edge-uh*8.0+nh*lit*5.0+vh*6.0, edge, 35.0),
            'blade_35m': (P(u7, w+18.0, lit*14.0)-uh*22.0, mid, 35.0),
            'blade_root': (root+nh*lit*9.0+vh*7.0-uh*10.0, root, 30.0)}


def figure(s, mat, at, axis, facing, col):
    """Non-diegetic 1.8 m scale reference (capsule + head) standing along `axis`; not an EVA position (flight EVA HOLD)."""
    import bpy
    import bmesh
    from mathutils import Matrix, Vector
    h = s['prototype']['human_height_m']
    me = bpy.data.meshes.new('P4_Figure'); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=.19, radius2=.17, depth=h*.80, matrix=Matrix.Translation((0, 0, h*.40)))
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=.13, matrix=Matrix.Translation((0, 0, h-.13)))
    bm.to_mesh(me); bm.free(); me.materials.append(mat)
    ob = bpy.data.objects.new('P4_Figure', me); col.objects.link(ob); ob['kind'] = 'scale_reference_review'
    z = Vector(axis).normalized(); x = Vector(facing).cross(z).normalized(); y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4(); m.translation = Vector(at); ob.matrix_world = m
    return ob


def material(name, rgba):
    import bpy
    m = bpy.data.materials.new(name); m.use_nodes = True; n = next(q for q in m.node_tree.nodes if q.type == 'BSDF_PRINCIPLED')
    n.inputs['Base Color'].default_value = (*rgba[:3], 1); n.inputs['Roughness'].default_value = rgba[3]; n.inputs['Metallic'].default_value = rgba[4]
    return m


def render(out, views=VIEWS, look='grammar', size=1600, samples=48, pair=False, label=''):
    import bpy
    from mathutils import Vector
    from common import pose_configuration
    from spec import load
    import forward_shield as fsh
    import hero_preview as hp
    import production_detail as pd
    from m8_exterior import sun_vector
    s = load(ROOT)[0]; out.mkdir(parents=True, exist_ok=True); report = dict(look=look, label=label, views={})
    pd.load_packs()
    states = ['COAST', 'IGNITION'] if pair else ['COAST']
    for state in states:
        bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend'))); scene = bpy.context.scene
        pose_configuration(s, 'COAST' if state == 'COAST' else 'HIGH_POWER'); scene.frame_set(scene.frame_current)
        hp.dress(s, functional=True, emit=(state == 'IGNITION'), grammar=(look == 'grammar')); x = s['look']['exterior']
        if state == 'COAST':
            inventory = {m.name[7:].split('.')[0]: pd.ship_family(s, m.name[7:].split('.')[0]) for m in bpy.data.materials if m.name.startswith('WF_MAT_')}
            (out/'materials.json').write_text(json.dumps(dict(sorted(inventory.items())), indent=1))
        scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = samples; scene.cycles.use_denoising = True
        scene.cycles.seed = 0; scene.render.resolution_x = size; scene.render.resolution_y = round(size*9/16)
        scene.render.image_settings.file_format = 'PNG'; aspect = 16/9
        scene.world.use_nodes = True; bg = next(n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND')
        bg.inputs['Color'].default_value = (0, 0, 0, 1); bg.inputs['Strength'].default_value = 0.0
        sv = sun_vector(*SUN)
        sun = bpy.data.lights.new('P4_Sun', 'SUN'); sun.energy = x['sun_strength']; sun.angle = math.radians(x['sun_angular_deg'])
        so = bpy.data.objects.new(sun.name, sun); scene.collection.objects.link(so); so.rotation_euler = (-sv).to_track_quat('-Z', 'Y').to_euler()
        scene.view_settings.view_transform = 'AgX'; scene.view_settings.look = 'None'
        cd = bpy.data.cameras.new('P4_Camera'); cam = bpy.data.objects.new(cd.name, cd); scene.collection.objects.link(cam); scene.camera = cam
        col = bpy.data.collections.new('P4_REVIEW'); scene.collection.children.link(col)
        red = material('P4_Figure', [1.0, .45, .10, .6, 0])
        cr = fsh.crown(s); b = cr['bays'][0]['azimuth']; uu = Vector((0, math.cos(b), math.sin(b))); tt = Vector((0, -math.sin(b), math.cos(b)))
        figure(s, red, Vector((cr['x0']-.35, 0, 0))+uu*41.9+tt*1.9, uu, Vector((-1, 0, 0)), col)
        w = rotor_world(1); sg = ring_aft_sign(); g = ring_frame(s); tc = clear_sector(s, w); ft = math.radians(tc+4)
        figure(s, red, w @ Vector((sg*(g['H']+.55), 26.4*math.cos(ft), 26.4*math.sin(ft))), w.to_3x3() @ Vector((0, math.cos(ft), math.sin(ft))),
               w.to_3x3() @ Vector((sg, 0, 0)), col)
        fr = frames(s); rc = ring_cameras(s, tc); bc = blade_cameras(s, sv)
        todo = [v for v in views if v in PAIR_VIEWS] if state == 'IGNITION' else list(views)
        for vw in todo:
            for ex_name, ev in ([('editorial', 2.0)] if state == 'COAST' else [])+([('matched', 0.0)] if pair and vw in PAIR_VIEWS else []):
                scene.view_settings.exposure = x['exposure_ev']+ev
                if vw in fr:
                    a, b2, corners, lens = fr[vw]; quat, dist = hp.place(cam, a, b2, corners, lens, aspect); cd.clip_start = .1 if corners is None else .5
                elif vw in rc:
                    eye, tgt, lens = rc[vw]; eye = Vector((eye.x*sg, eye.y, eye.z)); tgt = Vector((tgt.x*sg, tgt.y, tgt.z))
                    quat, dist = hp.place(cam, w @ tgt, w @ eye, None, lens, aspect); cd.clip_start = .1
                else:
                    eye, tgt, lens = bc[vw]; quat, dist = hp.place(cam, tgt, eye, None, lens, aspect); cd.clip_start = .1
                lines = [f"WAYFARER 001 / Phase 4 review {label} / {vw.upper()} / "
                         + ('COAST' if state == 'COAST' else 'FIRST IGNITION (HIGH_POWER, 1800 K emission unchanged)') + ' / '
                         + (f'+{ev:g} EV editorial exposure, not comparable brightness' if ev else 'matched exposure (comparison truth, 15!A222)'),
                         ('look: selected exterior grammar VC+ moderated ([production.exterior], Art Style Spacecraft row 19); depiction only, '
                          'S&E 15 OWN-P4-LOCKED' if look == 'grammar' else 'look: pre-Phase-4 hero look (proxy grey + M4 functional marks)'),
                         'production layers at their maturity (M7 L4_VISUAL_ACCEPTED; Phase 4 work L4_VISUAL_CANDIDATE until owner review); '
                         'orange figure = 1.8 m scale reference, not an EVA position',
                         'physical light: one sun 40 deg from aft, azimuth -20 deg (presentation choice; pointing OPEN); no fill']
                labels = hp.caption(scene, cam, quat, dist, lines, aspect)
                tag = vw + ('' if state == 'COAST' and ex_name == 'editorial' else f'_{state.lower()}_{ex_name}')
                scene.render.filepath = str(out/f'{tag}.png'); bpy.ops.render.render(write_still=True)
                for o in labels:
                    bpy.data.objects.remove(o, do_unlink=True)
                report['views'][tag] = dict(view=vw, state=state, ev=scene.view_settings.exposure, lens=cd.lens,
                                            camera=[round(c, 3) for c in cam.location], size=size, samples=samples)
                (out/'p4_review.json').write_text(json.dumps(report, indent=1))
                print('WF_P4_REVIEW', tag, flush=True)
    return report


def pairs(before, after, out):
    """Side-by-side before/after sheets of every view present in both runs (system Python with PIL)."""
    from PIL import Image, ImageDraw, ImageFont
    out.mkdir(parents=True, exist_ok=True)
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 30)
    except OSError:
        font = ImageFont.load_default()
    made = []
    for p in sorted(after.glob('*.png')):
        q = before/p.name
        if not q.exists():
            continue
        a, b = Image.open(q).convert('RGB'), Image.open(p).convert('RGB').resize(Image.open(q).size)
        sheet = Image.new('RGB', (a.width*2+8, a.height), (14, 16, 20)); sheet.paste(a, (0, 0)); sheet.paste(b, (a.width+8, 0))
        d = ImageDraw.Draw(sheet)
        for x, t in ((0, f'BEFORE  {before.name}'), (a.width+8, f'AFTER  {after.name}')):
            d.rectangle([x, 0, x+min(a.width, 900), 46], fill=(0, 0, 0)); d.text((x+12, 6), t, fill=(255, 200, 80), font=font)
        sheet.save(out/f'pair_{p.stem}.png', optimize=True); made.append(out/f'pair_{p.stem}.png')
    return made


if __name__ == '__main__':
    if '--pairs' in sys.argv:
        i = sys.argv.index('--pairs'); b, a, o = (Path(x) for x in sys.argv[i+1:i+4])
        print('\n'.join(str(p) for p in pairs(b, a, o)))
    else:
        argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
        ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); ap.add_argument('--look', choices=['grammar', 'hero'], default='grammar')
        ap.add_argument('--views', nargs='+', default=list(VIEWS), choices=VIEWS); ap.add_argument('--size', type=int, default=1600)
        ap.add_argument('--samples', type=int, default=48); ap.add_argument('--pair', action='store_true'); ap.add_argument('--label', default='')
        a = ap.parse_args(argv)
        render(a.out if a.out.is_absolute() else ROOT/a.out, a.views, a.look, a.size, a.samples, a.pair, a.label)
