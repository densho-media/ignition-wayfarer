"""Phase 4 S10 hero set (docs/PHASE4_PLAN.md section 3.3): reproducible stills of the five moments the plan names, from the same saved
master assets and the same grammar look as the review set (hero_preview.dress(grammar=True)); the vehicle is posed and dressed in memory
and never saved. Presentation only, every choice below labelled on the image:

- induction (S004): DOCKED, the primary port seen from between ring B and the Brow, as a visiting craft's crew approach it;
- departure: COAST, Y155 launch baseline, whole ship from the bow quarter;
- first_ignition: FIRST_IGNITION, the WORKING 1800 K hot faces at matched exposure (no editorial gain, so no impossible dimming); the
  plume is not drawn (its boundary and luminosity are OPEN);
- survival: COAST with the post-voyage wear layer on the Brow's ram face (impact pitting, dense repairs) from ahead;
- return: COAST with the wear layer, whole ship from the aft quarter.

The sun direction is a presentation choice per shot (departure pointing, attitude and the thermal clock are OPEN, K05); there is no fill
light, so nothing is concept-lit. Cycles CPU, 1920x1080, 64 samples by default.

    /snap/bin/blender -b --python src/wayfarer/presentation/p4_hero.py -- --out runs/<stamp>-p4-hero [--shots ...] [--size 1920] [--samples 64]
"""
from pathlib import Path
import argparse
import itertools
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation')]

# name: (configuration, hot faces emit, wear layer, sun (deg from aft, azimuth), editorial EV, title)
SHOTS = {
    'induction': ('DOCKED', False, False, (60.0, 195.0), 2.0, 'S004 induction: the primary port, docked, between ring B and the Brow'),
    'departure': ('COAST', False, False, (40.0, -20.0), 2.0, 'Departure: Y155 launch baseline, clean and serviced'),
    'first_ignition': ('FIRST_IGNITION', True, False, (40.0, -20.0), 0.0, 'First Ignition: WORKING 1800 K hot faces at matched exposure'),
    'survival': ('COAST', False, True, (130.0, -20.0), 2.0, 'Survival: the ram face after the voyage (post-voyage wear layer)'),
    'return': ('COAST', False, True, (55.0, 10.0), 2.0, 'Return: post-voyage wear layer'),
}


def cameras(s):
    """(focus, direction or eye, corners or None, lens) per shot from the shared stations, never fixed X numbers."""
    from mathutils import Vector
    import drive_manifold
    import forward_shield as fsh
    import hero_preview as hp
    import hull_geometry as hg
    st = fsh.stations(s); R = st['shield_r']; dm = drive_manifold.stations(s)
    rad = lambda x, r, deg: Vector((x, r*math.cos(math.radians(deg)), r*math.sin(math.radians(deg))))
    box = lambda x0, x1, r: [Vector(p) for p in itertools.product((x0, x1), (-r, r), (-r, r))]
    port = next(f for f in hg.service_fittings(s) if f['name'] == 'Dock_Primary'); pd_ = math.degrees(port['theta'])
    whole = box(dm['exit']-6, st['lance_tip'], R); mid = Vector(((dm['exit']+st['lance_tip'])/2, 0, 0))
    u = rad(0, 1, 330.0); t = rad(0, 1, 60.0)
    return {'induction': (rad(port['x'], port['r1'], pd_)+Vector((-2.0, 0, 0)), rad(port['x']-1.5, 36.0, pd_+12.0), None, 22.0),
            'departure': (mid, Vector((.62, 0, 0))+u*.75+t*.22, whole, 35.0),
            'first_ignition': hp.frame('establishing', s),
            'survival': (Vector((st['face'], 0, 0))+u*8.0, Vector((st['face']+9.0, 0, 0))+u*53.0-t*14.0, None, 24.0),
            'return': (mid, Vector((-.58, 0, 0))+u*.80-t*.25, whole, 38.0)}


def render(out, shots=tuple(SHOTS), size=1920, samples=64):
    import bpy
    from common import pose_configuration
    from spec import load
    import hero_preview as hp
    from m8_exterior import sun_vector
    s = load(ROOT)[0]; out.mkdir(parents=True, exist_ok=True); report = dict(set='Phase 4 S10 hero set', shots={})
    for name in shots:
        cfg, emit, wear, sun_dir, ev, title = SHOTS[name]
        bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend'))); scene = bpy.context.scene
        pose_configuration(s, cfg); scene.frame_set(scene.frame_current)
        hp.dress(s, functional=True, emit=emit, grammar=True, wear=wear); x = s['look']['exterior']
        scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = samples; scene.cycles.use_denoising = True
        scene.cycles.seed = 0; scene.render.resolution_x = size; scene.render.resolution_y = round(size*9/16)
        scene.render.image_settings.file_format = 'PNG'; aspect = 16/9
        scene.world.use_nodes = True; bg = next(n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND')
        bg.inputs['Color'].default_value = (0, 0, 0, 1); bg.inputs['Strength'].default_value = 0.0
        sv = sun_vector(*sun_dir); sun = bpy.data.lights.new('Hero_Sun', 'SUN'); sun.energy = x['sun_strength']
        sun.angle = math.radians(x['sun_angular_deg']); so = bpy.data.objects.new(sun.name, sun); scene.collection.objects.link(so)
        so.rotation_euler = (-sv).to_track_quat('-Z', 'Y').to_euler()
        scene.view_settings.view_transform = 'AgX'; scene.view_settings.exposure = x['exposure_ev']+ev
        cd = bpy.data.cameras.new('Hero_Camera'); cam = bpy.data.objects.new(cd.name, cd); scene.collection.objects.link(cam); scene.camera = cam
        focus, direction, corners, lens = cameras(s)[name]
        quat, dist = hp.place(cam, focus, direction, corners, lens, aspect)
        lines = [f'WAYFARER 001 / Phase 4 hero / {title}',
                 f'{cfg}; look: exterior grammar VC+ moderated (Art Style Spacecraft row 19), depiction only (S&E 15 OWN-P4-LOCKED); '
                 + ('post-voyage wear layer ON' if wear else 'Y155 launch baseline (wear layer off)'),
                 f'physical light: one sun {sun_dir[0]:g} deg from aft, azimuth {sun_dir[1]:g} deg (presentation choice; attitude and pointing OPEN); no fill; '
                 + (f'+{ev:g} EV editorial exposure' if ev else 'matched exposure (comparison truth, 15!A222)')
                 + ('; plume not drawn (OPEN)' if emit else '') + ('; ram-face tiles ILLUSTRATIVE' if name == 'survival' else ''),
                 'production layers at their maturity (M7 L4_VISUAL_ACCEPTED; Phase 4 work L4_VISUAL_CANDIDATE until owner review)']
        labels = hp.caption(scene, cam, quat, dist, lines, aspect)
        scene.render.filepath = str(out/f'hero_{name}.png'); bpy.ops.render.render(write_still=True)
        report['shots'][name] = dict(configuration=cfg, emit=emit, wear=wear, sun=sun_dir, ev=scene.view_settings.exposure, lens=cd.lens,
                                     camera=[round(c, 3) for c in cam.location], size=size, samples=samples)
        (out/'p4_hero.json').write_text(json.dumps(report, indent=1))
        print('WF_P4_HERO', name, flush=True)
    return report


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--shots', nargs='+', default=list(SHOTS), choices=SHOTS); ap.add_argument('--size', type=int, default=1920)
    ap.add_argument('--samples', type=int, default=64)
    a = ap.parse_args(argv)
    render(a.out if a.out.is_absolute() else ROOT/a.out, a.shots, a.size, a.samples)
