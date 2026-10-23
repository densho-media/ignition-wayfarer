"""M8.1 exterior production identity: controlled OFF/ON stills of the [production.m8] layer (Brow aft face, Aegis Crown rim).

The saved vehicle is posed OFF-BURN COAST and dressed in memory with the hero exterior look (proxy grey, M4 functional marks kept,
hero_preview.dress); the production materials keep their own [production.m8.materials] values. Every view renders twice from one build
with the same camera, sun and exposure: the M8 layer hidden (`off`, the engineering geometry as built) and shown (`on`). The M7 interior
layer is left as it is (not visible from outside). Physical light only: one 1 AU-class sun at the hero strength, its direction a
labelled presentation choice from the aft hemisphere (the departure pointing is OPEN), no fill; the exposure is the COAST editorial
+2 EV of 15!A222, said in every caption. Presentation only: renders in memory, saves nothing, changes no geometry or canon.

Views:
- `brow_aft`        the Brow's aft face between the truss spokes round Crown bay 1: panel modules, service lane, caps, protected band.
- `crown_sector`    Crown sector 1 from aft and outboard: the doubler round the carriage-service hatch, access panels, closeouts,
                    the rim girder's boundary stripes and sector number.
- `forward_oblique` the whole forward assembly (Brow, truss, Crown, Lance) from the aft quarter.
- `full_ship`       the whole ship in perspective, silhouette and balance.
- `cutaway`         `xray` mode only: engineering in clay, the M8 layer in amber, the forward assembly from the aft quarter.

    /snap/bin/blender -b --python src/wayfarer/presentation/m8_exterior.py -- [--views ...] [--size 1600] [--samples 64] [--out-dir DIR]
                                                                           [--mode beforeafter|xray] [--sun-from-aft 40] [--sun-azimuth 20]
"""
from pathlib import Path
import argparse
import itertools
import json
import math
import sys
import bpy
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation')]
from common import pose_configuration
from spec import load
import forward_shield as fsh
import drive_manifold
import hero_preview as hp
from m7_section import xray

VIEWS = ('brow_aft', 'crown_sector', 'forward_oblique', 'full_ship', 'cutaway')
MODES = ('beforeafter', 'xray')
EDITORIAL_EV = 2.0


def status(s):
    m = s['production']['m8']
    return (f"M8.1 exterior layer: {m['maturity']} (owner art review pending), not engineering GO; shield thickness, protection and mass "
            f"unqualified; Crown mechanisms unchanged")


def m8_objects():
    return [o for o in bpy.data.objects if o.get('kind') == 'production_detail' and str(o.get('m7_assembly', '')).startswith('M8.')]


def show(on):
    for o in m8_objects():
        o.hide_render = not on


def frame(s, view):
    """(target, eye, lens) or (focus, direction, corners, lens) for hero_preview.place, from the shield stations and the Crown bay frame."""
    st = fsh.stations(s); cr = fsh.crown(s); R = st['shield_r']; b = cr['bays'][0]['azimuth']
    u = Vector((0, math.cos(b), math.sin(b))); t = Vector((0, -math.sin(b), math.cos(b)))
    box = lambda x0, x1, r: [Vector(p) for p in itertools.product((x0, x1), (-r, r), (-r, r))]
    if view == 'brow_aft':
        target = Vector((fsh.skin_aft_at(s, 22.0), 0, 0))+u*22.0+t*1.5
        return target, target+Vector((-17.0, 0, 0))+u*9.0-t*9.0, None, 24.0
    if view == 'crown_sector':
        target = Vector((cr['x0']-.3, 0, 0))+u*43.6
        return target, target+Vector((-13.0, 0, 0))+u*9.0-t*7.0, None, 30.0
    if view in ('forward_oblique', 'cutaway'):
        return Vector((st['face']-4, 0, 0)), Vector((-.75, 0, 0))+u*.55-t*.45, box(st['truss_aft']-1, st['lance_tip'], R), 45.0
    dm = drive_manifold.stations(s)
    return Vector(((dm['exit']+st['lance_tip'])/2, 0, 0)), Vector((-.55, 0, 0))+u*.75-t*.55, box(dm['exit']-6, st['lance_tip'], R), 40.0


def sun_vector(from_aft_deg, azimuth_deg):
    """Unit vector from the ship toward the sun: from_aft_deg off the -X axis, azimuth about +X from +Y."""
    a, z = math.radians(from_aft_deg), math.radians(azimuth_deg)
    return Vector((-math.cos(a), math.sin(a)*math.cos(z), math.sin(a)*math.sin(z)))


def render(views=VIEWS, size=1600, samples=64, out_dir=None, mode='beforeafter', sun_from_aft=40.0, sun_azimuth=-20.0):
    s, *_ = load(ROOT)
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
    scene = bpy.context.scene; pose_configuration(s, 'COAST')
    # hero exterior look, then the production materials back to their own values (dress greys every WF_MAT_ material)
    # Keyed by datablock: each detail asset carries its own copy of a shared production material (same name, another library).
    keep = {}
    for m in bpy.data.materials:
        if m.name.startswith('WF_MAT_Prod_') and m.use_nodes:
            n = next(q for q in m.node_tree.nodes if q.type == 'BSDF_PRINCIPLED')
            keep[m] = {k: (tuple(n.inputs[k].default_value) if k == 'Base Color' else n.inputs[k].default_value) for k in ('Base Color', 'Roughness', 'Metallic')}
    hp.dress(s, functional=True, emit=False); x = s['look']['exterior']
    for m, vals in keep.items():
        n = next(q for q in m.node_tree.nodes if q.type == 'BSDF_PRINCIPLED')
        for k, v in vals.items():
            n.inputs[k].default_value = v
    scene.render.engine = 'CYCLES'; scene.cycles.samples = samples; scene.cycles.use_denoising = True; scene.cycles.seed = 0
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences; prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type != 'CPU'
        scene.cycles.device = 'GPU'
    except Exception:
        scene.cycles.device = 'CPU'
    scene.render.resolution_x = size; scene.render.resolution_y = round(size*9/16); scene.render.image_settings.file_format = 'PNG'
    aspect = 16/9
    scene.world.use_nodes = True; bg = next(n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = (0, 0, 0, 1); bg.inputs['Strength'].default_value = 0.0
    sv = sun_vector(sun_from_aft, sun_azimuth)
    sun = bpy.data.lights.new('M8_Sun', 'SUN'); sun.energy = x['sun_strength']; sun.angle = math.radians(x['sun_angular_deg'])
    so = bpy.data.objects.new(sun.name, sun); scene.collection.objects.link(so); so.rotation_euler = (-sv).to_track_quat('-Z', 'Y').to_euler()
    scene.view_settings.view_transform = 'AgX'; scene.view_settings.look = 'None'; scene.view_settings.exposure = x['exposure_ev']+EDITORIAL_EV
    cd = bpy.data.cameras.new('M8_Camera'); cam = bpy.data.objects.new(cd.name, cd); scene.collection.objects.link(cam); scene.camera = cam
    out = Path(out_dir or ROOT/'renders/m8'); out.mkdir(parents=True, exist_ok=True)
    objs = m8_objects()
    counts = {o.name: dict(assembly=o.get('m7_assembly'), family=o.get('family'), maturity=o.get('maturity'), elements=o.get('elements'),
                           faces=len(o.data.polygons), detail_range_m=o.get('detail_range_m')) for o in objs}
    light = (f"physical light: one sun, 1 AU-class hero strength {x['sun_strength']:g}, direction {sun_from_aft:g} deg from aft, azimuth "
             f"{sun_azimuth:g} deg (presentation choice; departure pointing OPEN); no fill")
    report = {}
    for view in views:
        if (view == 'cutaway') != (mode == 'xray'):
            continue
        a, b, corners, lens = frame(s, view)
        quat, dist = hp.place(cam, a, b, corners, lens, aspect)
        cd.clip_start = .1 if corners is None else .5
        states = (('xray', True),) if mode == 'xray' else (('off', False), ('on', True))
        made = []
        for tag, on in states:
            show(on)
            what = {'off': 'M8 LAYER OFF (engineering geometry as built)', 'on': 'M8 LAYER ON (Brow aft face + Crown rim)',
                    'xray': 'clay: engineering (unchanged) / amber: M8.1 production layer'}[tag]
            lines = [f"COAST — +{EDITORIAL_EV:g} EV editorial exposure, not comparable brightness / {view.upper()} / {what}", status(s), light,
                     'proxy grey + M4 functional marks (hero look) | OFF and ON: same camera, sun, exposure | NOT A FINAL RENDER: owner review pending']
            labels = hp.caption(scene, cam, quat, dist, lines, aspect)
            if tag == 'xray':
                xray(labels)
            path = out/f'{view}_{tag}.png'; scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True); made.append(str(path))
            for o in labels:
                bpy.data.objects.remove(o, do_unlink=True)
        report[view] = dict(images=made, camera=dict(location=list(cam.location), lens=cd.lens, distance_m=round(dist, 2)))
        print('WF_M8_VIEW', view, flush=True)
    (out/f'm8_exterior_{mode}.json').write_text(json.dumps(dict(status=status(s), mode=mode, light=light, exposure_ev=scene.view_settings.exposure,
                                                               production_objects=counts, views=report), indent=1))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--views', nargs='+', choices=VIEWS, default=list(VIEWS)); p.add_argument('--size', type=int, default=1600)
    p.add_argument('--samples', type=int, default=64); p.add_argument('--out-dir', type=Path); p.add_argument('--mode', choices=MODES, default='beforeafter')
    p.add_argument('--sun-from-aft', type=float, default=40.0); p.add_argument('--sun-azimuth', type=float, default=-20.0)
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    render(a.views, a.size, a.samples, a.out_dir, a.mode, a.sun_from_aft, a.sun_azimuth)
