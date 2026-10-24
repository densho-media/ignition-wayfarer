"""Renders of WAYFARER_EVA_Y155 (EVA-001; S&E 44 EXP-04, RUN-008): assembled, cutaway, exploded and pose sheets of the suit variants.

  blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/presentation/eva_preview.py -- \
      [--views lineup turnaround cutaway exploded poses back] [--out renders/p1/eva] [--size 1280 960] [--samples 32]

Every view opens the saved assets/characters/WF_EVA_<ID>.blend files (build/eva_suit.py) in memory and never saves them. The cutaway
removes the front-left quadrant of the outer layers and the PLSS covers by a boolean at render time only and shows the parts marked
`eva_show = cutaway`; the exploded view moves each assembly out along a fixed direction. Labels are drawn as text objects; they name
functions, never values (RUN-008: no fictitious output numbers). Display only: not a pressure or thermal simulation.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]

EXPLODE = dict(HELMET=(0, -.05, .35), PLSS=(0, .45, .05), PROTECTION=(0, -.0, 0), PRESSURE=(0, 0, 0), JOINTS=(0, 0, 0), TETHERS=(.35, 0, -.1),
               TOOLS=(-.35, -.25, 0), MARKINGS=(0, 0, 0), COOLING=(0, 0, 0), RIG=(0, 0, 0))


def append(key, offset=(0, 0, 0)):
    """Append the variant's WAYFARER_EVA_Y155 tree into the current scene, shifted by offset; returns (rig, objects)."""
    path = ROOT/'assets/characters'/f'WF_EVA_{key.upper()}.blend'
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c == 'WAYFARER_EVA_Y155']
    c = dst.collections[0]; c.name = f'EVA_{key}'; bpy.context.scene.collection.children.link(c)
    objs = list(c.all_objects); rig = next(o for o in objs if o.type == 'ARMATURE'); rig.location = offset
    return rig, objs


def pose(rig, action, frame):
    ad = rig.animation_data
    for tr in ad.nla_tracks:
        tr.mute = True
    if action:
        act = bpy.data.actions[action]; ad.action = act
        if act.slots:
            ad.action_slot = act.slots[0]
        bpy.context.scene.frame_set(frame)
    else:
        ad.action = None
        for pb in rig.pose.bones:
            pb.matrix_basis.identity()
    bpy.context.view_layer.update()


def scene_setup(size, samples, engine='CYCLES'):
    sc = bpy.context.scene; sc.render.engine = engine; sc.render.resolution_x, sc.render.resolution_y = size
    if engine == 'CYCLES':
        sc.cycles.samples = samples; sc.cycles.use_denoising = True; sc.cycles.device = 'CPU'
    sc.render.film_transparent = False
    w = bpy.data.worlds.new('EVA_World'); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (.018, .02, .026, 1); bg.inputs['Strength'].default_value = 1.0
    sc.view_settings.view_transform = 'AgX'
    for name, rot, energy, ang in (('Sun_Key', (math.radians(52), 0, math.radians(-38)), 4.2, 2.0), ('Sun_Fill', (math.radians(70), 0, math.radians(140)), 1.0, 10.0),
                                   ('Sun_Rim', (math.radians(100), 0, math.radians(200)), 2.2, 4.0)):
        L = bpy.data.lights.new(name, 'SUN'); L.energy = energy; L.angle = math.radians(ang); o = bpy.data.objects.new(name, L)
        sc.collection.objects.link(o); o.rotation_euler = rot
    floor = bpy.data.meshes.new('floor'); floor.from_pydata([(-20, -20, -.002), (20, -20, -.002), (20, 20, -.002), (-20, 20, -.002)], [], [(0, 1, 2, 3)])
    m = bpy.data.materials.new('floor'); m.use_nodes = True; m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.035, .037, .042, 1)
    m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .9; floor.materials.append(m)
    f = bpy.data.objects.new('floor', floor); sc.collection.objects.link(f)
    return sc


def camera(sc, eye, look, lens=50):
    cam = bpy.data.cameras.new('cam'); cam.lens = lens; o = bpy.data.objects.new('cam', cam); sc.collection.objects.link(o)
    o.location = eye; o.rotation_euler = (Vector(look)-Vector(eye)).to_track_quat('-Z', 'Y').to_euler(); sc.camera = o; return o


def label(sc, text, at, size=.045, rgb=(.85, .85, .82)):
    cu = bpy.data.curves.new('lbl', 'FONT'); cu.body = text; cu.size = size; cu.align_x = 'LEFT'
    o = bpy.data.objects.new('lbl', cu); sc.collection.objects.link(o); o.location = at; o.rotation_euler = (math.radians(90), 0, 0)
    m = bpy.data.materials.new('lbl'); m.use_nodes = True; bs = m.node_tree.nodes['Principled BSDF']
    bs.inputs['Emission Color'].default_value = (*rgb, 1); bs.inputs['Emission Strength'].default_value = 1.5; bs.inputs['Base Color'].default_value = (*rgb, 1)
    cu.materials.append(m); return o


def render(sc, path):
    path.parent.mkdir(parents=True, exist_ok=True); sc.render.filepath = str(path); bpy.ops.render.render(write_still=True); print('WF_RENDER', path, flush=True)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def lineup(out, size, samples):
    reset(); sc = scene_setup(size, samples)
    r1, _ = append('instructor', (-.55, 0, 0)); r2, _ = append('newcomer', (.55, 0, 0))
    pose(r1, None, 0); pose(r2, None, 0)
    camera(sc, (2.6, -5.2, 1.55), (0, 0, 1.0), 55)
    label(sc, 'WAYFARER_EVA_Y155  ·  PROTOTYPE, NOT CERTIFIED', (-1.6, -.6, 2.15), .07)
    label(sc, 'instructor variant (GU markings)', (-1.25, -.6, -.0), .05); label(sc, 'visitor variant (neutral markings)', (.15, -.6, -.0), .05)
    render(sc, out/'eva_lineup.png')


def back(out, size, samples):
    reset(); sc = scene_setup(size, samples); r, _ = append('newcomer'); pose(r, None, 0)
    camera(sc, (-2.4, 3.6, 1.7), (0, 0, 1.15), 55); render(sc, out/'eva_back.png')


def turnaround(out, size, samples):
    """The instructor suit from the front, side, back and three-quarter, side by side at one scale (accessory review, A5)."""
    reset(); sc = scene_setup(size, samples)
    for k, (yaw, name) in enumerate(((0, 'front'), (90, 'side'), (180, 'back'), (35, 'three-quarter'))):
        rig, _ = append('instructor', ((k-1.5)*1.05, 0, 0)); rig.rotation_euler[2] = math.radians(yaw); pose(rig, None, 0)
        label(sc, name, ((k-1.5)*1.05-.25, -.6, -.0), .05)
    label(sc, 'WAYFARER_EVA_Y155  ·  PROTOTYPE, NOT CERTIFIED', (-2.1, -.6, 2.15), .07)
    cam = camera(sc, (0, -9.0, 1.05), (0, 0, 1.0), 50); cam.data.type = 'ORTHO'; cam.data.ortho_scale = 4.6
    render(sc, out/'eva_turnaround.png')


def cutaway(out, size, samples):
    """Front-left quadrant removed from the outer layers, HUT, helmet and PLSS covers; internals shown; labels name functions."""
    reset(); sc = scene_setup(size, samples); rig, objs = append('newcomer'); pose(rig, None, 0)
    import bmesh
    # Remove, in memory, the faces of each layer inside a front-right quadrant box (x > x0, y < y0, z0 < z < z1); each inner layer's box
    # starts a little further in and lower, so the outer layer, the bladder and the cooling garment all show as steps.
    step = {'MMOD_OUTER_SHELL': 0.0, 'SUIT_PRESSURE_BLADDER': .06, 'LCVG_INNER': .12, 'SUIT_PRESSURE_HARD_TORSO': 0.0, 'SUIT_HELMET_VISOR': 0.0,
            'PLSS_PRIMARY': 0.0, 'SUIT_NECK_RING': 0.0, 'SUIT_WAIST_RING': 0.0}
    for o in objs:
        if o.type != 'MESH' or o.get('eva_role') == 'validation_body' or (o.get('eva_show') == 'cutaway' and o.get('assembly') == 'PLSS'):
            continue
        part = o.get('part_id', '').split('/')[-1]
        if part not in step or (part == 'PLSS_PRIMARY' and not o.name.endswith(('_PLSS', '_PLSS_Lower', 'Cover_Upper', 'Cover_Lower'))):
            continue
        d = step[part]; x0, y0, z0, z1 = .0+d, .05-d, .55+d*2, 2.2
        if part == 'PLSS_PRIMARY':
            x0, y0, z0 = -.05, 1.0, 0.0                      # open the pack's right half from the back
        mw = o.matrix_world; me = o.data.copy(); o.data = me
        bm = bmesh.new(); bm.from_mesh(me)
        kill = [f for f in bm.faces if (lambda c: c.x > x0 and (c.y < y0 if part != 'PLSS_PRIMARY' else True) and z0 < c.z < z1)(mw @ f.calc_center_median())]
        bmesh.ops.delete(bm, geom=kill, context='FACES'); bm.to_mesh(me); bm.free()
    for o in objs:
        if o.get('eva_show') == 'cutaway':
            o.hide_render = False; o.hide_viewport = False
    camera(sc, (1.9, -2.9, 1.65), (.05, 0, 1.12), 55)
    for text, at in (('helmet shell · clear pressure visor · glare visor', (.30, -.5, 1.86)), ('outer thermal/MMOD layer + restraint', (.48, -.5, 1.30)),
                     ('pressure bladder (continuous)', (.48, -.5, 1.18)), ('liquid cooling & ventilation garment', (.48, -.5, 1.06)),
                     ('hard upper torso · bearings · waist seal', (.48, -.5, .94)), ('PLSS: O2 primary · emergency reserve · CO2 · fan/pump · heat exchanger', (-.95, -.5, 1.62)),
                     ('chest display & controls', (-.95, -.5, 1.48))):
        label(sc, text, at, .028)
    label(sc, 'CUTAWAY (display only)  ·  values OPEN', (-.95, -.5, 2.02), .04)
    render(sc, out/'eva_cutaway.png')


def exploded(out, size, samples):
    reset(); sc = scene_setup(size, samples); rig, objs = append('instructor'); pose(rig, None, 0)
    for o in objs:
        if o.get('eva_show') == 'cutaway' and o.get('assembly') == 'PLSS':
            o.hide_render = False
        d = EXPLODE.get(o.get('assembly'), (0, 0, 0))
        if o.parent is rig and o.parent_type == 'BONE':
            o.matrix_world.translation += Vector(d)
        elif o.get('assembly') == 'PLSS':
            o.matrix_world.translation += Vector(d)
    for o in objs:                                             # the PLSS covers come off further, to open the pack
        if o.name.endswith(('_PLSS', '_PLSS_Lower', 'Cover_Upper', 'Cover_Lower')):
            o.matrix_world.translation += Vector((0, .35, 0))
    camera(sc, (3.2, -2.8, 1.9), (0, .35, 1.1), 50)
    label(sc, 'EXPLODED: helmet · torso & bearings · PLSS (covers off) · tethers · tool', (-1.2, -.5, 2.2), .04)
    render(sc, out/'eva_exploded.png')


def poses(out, size, samples):
    """Four EVA actions side by side at a representative frame (the newcomer)."""
    reset(); sc = scene_setup(size, samples)
    picks = [('eva_suit_check', 240), ('eva_translate', 40), ('eva_tether_transfer', 115), ('eva_guide_point', 90)]
    for k, (act, fr) in enumerate(picks):
        rig, _ = append('newcomer', ((k-1.5)*1.25, 0, 0)); pose(rig, act, fr)
        label(sc, act, ((k-1.5)*1.25-.45, -.7, -.0), .045)
    camera(sc, (3.0, -6.5, 2.2), (0, 0, .9), 45); render(sc, out/'eva_poses.png')


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--views', nargs='*', default=['lineup', 'back', 'cutaway', 'exploded', 'poses'])
    ap.add_argument('--out', type=Path, default=ROOT/'renders/p1/eva'); ap.add_argument('--size', nargs=2, type=int, default=[1280, 960])
    ap.add_argument('--samples', type=int, default=32)
    a = ap.parse_args(argv)
    for v in a.views:
        globals()[v](a.out, a.size, a.samples)


if __name__ == '__main__':
    main()
