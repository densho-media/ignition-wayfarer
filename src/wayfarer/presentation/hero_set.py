"""The three permanent hero cameras rendered in their two presentation modes (exterior production refinement 2026-11-01;
hero_cameras.py, [look.hero_cameras]; presentation only, posed and dressed in memory, the saved assets are never changed).

- engineering: Workbench, studio light, the functional review colours (functional_colors, the viewport colour every generated object
  carries), cavity and outlines; the review label overlay is composited onto it as <cam>_engineering_annotated.png;
- cinematic: Cycles, the Phase 4 grammar with the exterior production families ([production.exterior], hero_preview.dress), one hard sun
  per camera ([look.hero_cameras] sun, attitude OPEN), black space, AgX; in FIRST_IGNITION the hot faces emit as grey bodies
  (look.exterior) and bulkhead layer 1 at its study temperature and emissivity (radiator_zones, about 1200 K at eps 0.12). No labels;
- overlay: the review labels and leader lines alone on a transparent frame (<cam>_overlay.png), so they stay a separate layer.

Every camera is the saved CAM_HERO_* of the vehicle file; the sun, exposure and states ride on it as properties.

    /snap/bin/blender -b --python src/wayfarer/presentation/hero_set.py -- --out runs/renders/hero_set [--cameras ...]
        [--modes engineering cinematic overlay] [--states COAST FIRST_IGNITION] [--size 1920] [--samples 64] [--asset path]
"""
from pathlib import Path
import argparse
import json
import math
import sys
import bpy
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation')]
from spec import load
from common import pose_configuration
import hero_cameras as hc
import hero_preview as hp
import look
import radiator_zones
from m8_exterior import sun_vector

MODES = ('engineering', 'cinematic', 'overlay')


def bulkhead_glow(s):
    """Grey-body emission of bulkhead layer 1 under maximum drive (Cycles strength under the [look.exterior] calibration)."""
    x = s['look']['exterior']; L1 = radiator_zones.layers(s)[0]; T = radiator_zones.bulkhead_cfg(s)['foil'][0]['T_K']
    col = look.kelvin_rgb(T); Lum = look.grey_body_luminance(T, L1['emissivity']); Y = .2126*col[0]+.7152*col[1]+.0722*col[2]
    return col, x['sun_strength']*Lum/(x['sun_illuminance_lx']*Y), T


def pose_camera(scene, q):
    """The saved CAM_HERO_* (created when an older vehicle file lacks it), posed from the source so a render always matches
    [look.hero_cameras] even before the next build."""
    from mathutils import Matrix
    cam = bpy.data.objects.get(q['name'])
    if cam is None:
        cam = bpy.data.objects.new(q['name'], bpy.data.cameras.new(q['name'])); scene.collection.objects.link(cam)
    cam.data.lens = q['lens_mm']; cam.data.sensor_width = q['sensor_mm']; cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.clip_start, cam.data.clip_end = q['clip']
    cam.matrix_world = Matrix([(q['right'][i], q['up'][i], q['back'][i], q['location'][i]) for i in range(3)]+[(0, 0, 0, 1)])
    return cam


def functional_materials():
    """Workbench shows a collection instance's members in the instancer's colour, not their own, so the engineering mode puts the
    functional review colour on the materials instead: each material takes the function most of its objects carry (wf_function)."""
    import collections
    import functional_colors as fc
    votes = collections.defaultdict(collections.Counter)
    for o in bpy.data.objects:
        f = o.get('wf_function')
        if f in fc.PALETTE:
            for sl in o.material_slots:
                if sl.material:
                    votes[sl.material.name][f] += 1
    for m in bpy.data.materials:
        if m.name in votes:
            m.diffuse_color = fc.PALETTE[votes[m.name].most_common(1)[0][0]][1]


def hide_display(s):
    x = s['look']['exterior']
    for o in bpy.data.objects:
        if o.get('kind') in x['hidden_kinds'] or o.name.startswith(('Preview_', *x['hidden_prefixes'])):
            o.hide_render = o.hide_viewport = True


def labels(scene, cam, s, name, aspect):
    """Text and leader lines on a plane 4 m in front of the camera (an overlay layer; nothing else renders with it)."""
    from bpy_extras.object_utils import world_to_camera_view
    q = hc.resolve(s, name); data = cam.data; depth = 4.0
    w = 2*depth*math.tan(data.angle_x/2); h = w/aspect
    rot = cam.matrix_world.to_quaternion(); objs = []
    mat = bpy.data.materials.new('Hero_Label'); mat.use_nodes = True
    n = next(k for k in mat.node_tree.nodes if k.type == 'BSDF_PRINCIPLED'); n.inputs['Emission Color'].default_value = (.95, .95, .92, 1)
    n.inputs['Emission Strength'].default_value = 1.0; n.inputs['Base Color'].default_value = (0, 0, 0, 1)
    def plane(u, v):
        return cam.matrix_world @ Vector(((u-.5)*w, (v-.5)*h, -depth))
    pts = []
    for i, lab in enumerate(q['labels']):
        if lab['at'] is None:
            continue
        p = world_to_camera_view(scene, cam, Vector(lab['at']))
        if 0.02 < p.x < 0.98 and 0.02 < p.y < 0.98 and p.z > 0:
            pts.append((i, lab['text'], p))
    # two margin columns: anchors in the left half label on the left edge, right half on the right, spread evenly by height
    for side in (0, 1):
        col = sorted([x for x in pts if (x[2].x >= .5) == bool(side)], key=lambda x: -x[2].y)
        ys = [.88-k*(.76/max(1, len(col)-1)) for k in range(len(col))] if len(col) > 1 else [min(.88, max(.12, col[0][2].y))] if col else []
        for (i, text, p), tv in zip(col, ys):
            tu = .97 if side else .03
            curve = bpy.data.curves.new(f'Hero_Label_{i}', 'FONT'); curve.body = text; curve.size = w*.016
            curve.align_x = 'RIGHT' if side else 'LEFT'; curve.materials.append(mat)
            tt = bpy.data.objects.new(curve.name, curve); scene.collection.objects.link(tt); tt.rotation_euler = rot.to_euler()
            tt.location = plane(tu, tv+.012); objs.append(tt)
            kink = (tu+(-.02 if side else .02)+(-.18 if side else .18)*0, tv)
            a_, k_, e_ = plane(p.x, p.y), plane(*kink), plane(.80 if side else .20, tv)
            lc = bpy.data.curves.new(f'Hero_Leader_{i}', 'CURVE'); lc.dimensions = '3D'; lc.bevel_depth = w*.0007
            sp = lc.splines.new('POLY'); sp.points.add(2)
            for pt, co in zip(sp.points, (a_, e_, k_)):
                pt.co = (*co, 1)
            lc.materials.append(mat); lo = bpy.data.objects.new(lc.name, lc); scene.collection.objects.link(lo); objs.append(lo)
            dot = bpy.data.meshes.new(f'Hero_Dot_{i}'); r = w*.003
            dot.from_pydata([tuple(a_+rot@Vector((r*math.cos(k*math.pi/6), r*math.sin(k*math.pi/6), 0))) for k in range(12)], [], [tuple(range(12))])
            dot.materials.append(mat); do = bpy.data.objects.new(dot.name, dot); scene.collection.objects.link(do); objs.append(do)
    return objs


def composite(base, over, out):
    """Alpha-over of the overlay PNG onto a base PNG (numpy on Blender images)."""
    import numpy as np
    A = bpy.data.images.load(str(base)); B = bpy.data.images.load(str(over))
    a = np.array(A.pixels[:]).reshape(-1, 4); b = np.array(B.pixels[:]).reshape(-1, 4)
    al = b[:, 3:4]; c = a.copy(); c[:, :3] = b[:, :3]*al+a[:, :3]*(1-al); c[:, 3] = 1.0
    img = bpy.data.images.new('Hero_Composite', A.size[0], A.size[1]); img.pixels[:] = c.ravel().tolist()
    img.filepath_raw = str(out); img.file_format = 'PNG'; img.save()


def render(out, cameras=None, modes=MODES, states=None, size=1920, samples=64, asset=None, tag=''):
    s = load(ROOT)[0]; out.mkdir(parents=True, exist_ok=True)
    cameras = cameras or list(s['look']['hero_cameras']['cameras']); report = dict(set='hero cameras', cameras={})
    asset = asset or ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')
    x = s['look']['exterior']
    for name in cameras:
        q = hc.resolve(s, name)
        for state in states or q['states']:
            if state not in q['states'] and state != 'COAST':
                continue
            for mode in modes:
                bpy.ops.wm.open_mainfile(filepath=str(asset)); scene = bpy.context.scene
                pose_configuration(s, state); scene.frame_set(scene.frame_current)
                cam = pose_camera(scene, q); scene.camera = cam
                scene.render.resolution_x = size; scene.render.resolution_y = round(size*9/16); scene.render.resolution_percentage = 100
                scene.render.image_settings.file_format = 'PNG'; aspect = 16/9
                stem = f"{name}_{state}_{mode}{tag}"
                if mode == 'cinematic':
                    hp.dress(s, functional=True, emit=state == 'FIRST_IGNITION', grammar=True)
                    if state == 'FIRST_IGNITION':
                        col, strength, T = bulkhead_glow(s)
                        for m in bpy.data.materials:
                            if m.name.startswith('WF_MAT_BulkheadFoilMo') and m.use_nodes:
                                nd = next(k for k in m.node_tree.nodes if k.type == 'BSDF_PRINCIPLED')
                                nd.inputs['Emission Color'].default_value = (*col, 1); nd.inputs['Emission Strength'].default_value = strength
                    scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = samples
                    scene.cycles.use_denoising = True; scene.cycles.seed = 0; scene.render.film_transparent = False
                    scene.world.use_nodes = True; bg = next(n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND')
                    bg.inputs['Color'].default_value = (0, 0, 0, 1); bg.inputs['Strength'].default_value = 0.0
                    sv = sun_vector(*q['sun']); sun = bpy.data.lights.new('Hero_Sun', 'SUN'); sun.energy = x['sun_strength']
                    sun.angle = math.radians(x['sun_angular_deg']); so = bpy.data.objects.new(sun.name, sun); scene.collection.objects.link(so)
                    so.rotation_euler = (-sv).to_track_quat('-Z', 'Y').to_euler()
                    scene.view_settings.view_transform = 'AgX'; scene.view_settings.look = 'AgX - Medium High Contrast'
                    # editorial exposure only for the COAST set; FIRST_IGNITION stays at the matched exposure (15!A222)
                    scene.view_settings.exposure = x['exposure_ev']+(q['ev'] if state == 'COAST' else 0.0)
                elif mode == 'engineering':
                    hide_display(s)
                    scene.render.engine = 'BLENDER_WORKBENCH'; sh = scene.display.shading
                    functional_materials()
                    sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True; sh.cavity_type = 'BOTH'
                    sh.show_object_outline = True; sh.object_outline_color = (0.02, 0.02, 0.025); sh.show_specular_highlight = True
                    sh.background_type = 'VIEWPORT'; sh.background_color = (0.035, 0.038, 0.045)
                    scene.display.render_aa = '16'; scene.view_settings.view_transform = 'Standard'; scene.view_settings.exposure = 0.0
                else:
                    for o in bpy.data.objects:
                        o.hide_render = True
                    labels(scene, cam, s, name, aspect)
                    scene.render.engine = 'BLENDER_WORKBENCH'; sh = scene.display.shading; sh.light = 'FLAT'; sh.color_type = 'MATERIAL'
                    scene.render.film_transparent = True; scene.render.image_settings.color_mode = 'RGBA'
                    scene.view_settings.view_transform = 'Standard'; scene.display.render_aa = '16'
                    for m in bpy.data.materials:
                        if m.name.startswith('Hero_Label'):
                            m.diffuse_color = (.95, .95, .92, 1)
                scene.render.filepath = str(out/f'{stem}.png'); bpy.ops.render.render(write_still=True)
                report['cameras'].setdefault(name, dict(purpose=q['purpose'], location=[round(v, 2) for v in q['location']], lens_mm=q['lens_mm'],
                                                        distance_m=round(q['distance_m'], 1), sun=q['sun'], ev=q['ev'], renders=[]))['renders'].append(f'{stem}.png')
                print('WF_HERO_SET', stem, flush=True)
            eng = out/f"{name}_{state}_engineering{tag}.png"; ov = out/f"{name}_{state}_overlay{tag}.png"
            if eng.is_file() and ov.is_file():
                composite(eng, ov, out/f"{name}_{state}_engineering_annotated{tag}.png")
        (out/'hero_set.json').write_text(json.dumps(report, indent=1))
    return report


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); ap.add_argument('--cameras', nargs='+')
    ap.add_argument('--modes', nargs='+', default=list(MODES), choices=MODES); ap.add_argument('--states', nargs='+')
    ap.add_argument('--size', type=int, default=1920); ap.add_argument('--samples', type=int, default=64); ap.add_argument('--asset', type=Path)
    ap.add_argument('--tag', default='')
    a = ap.parse_args(argv)
    render(a.out if a.out.is_absolute() else ROOT/a.out, a.cameras, a.modes, a.states, a.size, a.samples, a.asset, a.tag)
