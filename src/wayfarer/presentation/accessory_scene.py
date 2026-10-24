"""Accessory interaction scenes (docs/ACCESSORIES.md, A4): the suited instructor beside a spine utility crawler on its review rail, and the
interior drones at work. Needs build/eva_suit.py and build/drone_bodies.py first; opens the saved assets in memory and never saves them.

  blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/presentation/accessory_scene.py -- \
      --out <dir> [--scenes eva iva] [--quality draft|material|review] [--size 1600 1000] [--action eva_tool_inspect] [--frame 0.5]

EVA scene: DR-EVA-03 holds its `handoff` pose; the instructor (WAYFARER_EVA_Y155) is posed in an EVA action and placed so the right glove
meets the presented tool cartridge, feet in a PROTOTYPE foot restraint on the review hull patch. TRAINING_SIMULATION: no flight EVA, no
anchor rating, no released thermal or debris state (FLIGHT_EVA HOLD, 54 gates HOLD). IVA scene: DR-IVA-02 on a deck patch reaching for
its cargo cartridge, DR-IVA-01 perched on a handrail, DR-IVA-03 at a raceway port. Labels name functions and states, never values.
"""
import argparse
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation')]
import drone_bodies as db
from drone_bodies_render import apply_pose, camera, note, render_setup, shoot
from drone_preview import append as append_drone, key_values
from eva_grasp import grasp
from eva_preview import append as append_suit, pose as pose_suit


def mat(name, rgb, rough=.6, metal=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name); m.use_nodes = True; m.diffuse_color = (*rgb, 1)
    bs = m.node_tree.nodes['Principled BSDF']; bs.inputs['Base Color'].default_value = (*rgb, 1); bs.inputs['Roughness'].default_value = rough
    bs.inputs['Metallic'].default_value = metal; return m


def block(name, c, s, m):
    bpy.ops.mesh.primitive_cube_add(size=1, location=c); o = bpy.context.object; o.name = name; o.scale = s; o.data.materials.append(m); return o


def rod(name, a, b, r, m):
    a, b = Vector(a), Vector(b); bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=(b-a).length, location=(a+b)/2, vertices=20)
    o = bpy.context.object; o.name = name; o.rotation_euler = (b-a).to_track_quat('Z', 'Y').to_euler(); o.data.materials.append(m); return o


def place(objs, M):
    """Apply a world transform to every top-level object of an appended group."""
    for o in objs:
        if o.parent is None:
            o.matrix_world = M @ o.matrix_world


def eva(args, out, B):
    bpy.ops.wm.read_factory_settings(use_empty=True); render_setup(args.size, args.quality)
    b = B['DR-EVA-03']; E = append_drone('DR-EVA-03'); vals = key_values(b, 'handoff', 4.5); apply_pose(b, E, vals)
    ha, hb, hr = db.CREW_HANDLE; ha = Vector(db.at(b, 'cartridge', ha, vals)); hb = Vector(db.at(b, 'cartridge', hb, vals))
    tool = (ha+hb)/2                                                          # the cartridge crew handle the glove closes on
    rig, objs = append_suit('instructor'); pose_suit(rig, args.action, int(args.frame*bpy.data.actions[args.action].frame_range[1]))
    rig.rotation_euler[2] = math.radians(180); bpy.context.view_layer.update()   # face +Y, toward the track
    sh = rig.matrix_world @ rig.pose.bones['upperarm_r'].head
    rig.location += tool+Vector((0, -.36, .30))-sh; bpy.context.view_layer.update()   # shoulder above and behind the handle
    res, rep = grasp(rig, 'r', ha, hb, hr, reach=True); print('WF_GRASP', rep, flush=True)
    feet = min((rig.matrix_world @ rig.pose.bones[f'foot_{s}'].head).z for s in 'lr')-.09
    grey = mat('Fixture_Grey', (.36, .37, .38), .55, .3); orange = mat('Fixture_Orange', (.92, .36, .06), .5); hull_m = mat('Hull_Patch', (.78, .78, .75), .7)
    fx, fy = (rig.matrix_world @ rig.pose.bones['pelvis'].head).xy
    # a curved casing patch under the review rails (display radius, not the ship's casing): the crew stands lower on its flank, so the
    # presented handle comes at elbow height; the portable foot restraint stands on a short vertical post
    Rc = 1.0; zc = -.17-Rc; bpy.ops.mesh.primitive_cylinder_add(radius=Rc, depth=2.4, location=(tool.x-.1, 0, zc), rotation=(0, math.pi/2, 0), vertices=96)
    cas = bpy.context.object; cas.name = 'Casing_Patch_Display'; cas.data.materials.append(hull_m)
    surf = zc+math.sqrt(max(0.0, Rc*Rc-fy*fy))
    block('FootRestraint_Plate', (fx, fy, feet-.02), (.42, .32, .03), grey)
    rod('FootRestraint_Post', (fx, fy, surf-.02), (fx, fy, feet-.035), .03, grey)
    for s in 'lr':
        p = rig.matrix_world @ rig.pose.bones[f'ball_{s}'].head
        block(f'FootRestraint_Toe_{s}', (p.x, p.y, feet+.03), (.11, .05, .04), grey)
    sock = [o for o in objs if o.name == 'SOCKET_TETHER_A']
    if sock:                                                                  # tether A clipped to an anchor post on the casing (training fixture)
        a = sock[0].matrix_world.translation; ay = fy+.25; anchor = Vector((fx-.55, ay, zc+math.sqrt(max(0.0, Rc*Rc-ay*ay))+.12))
        rod('Tether_A', a, anchor, .006, orange); rod('Tether_Anchor', (anchor.x, anchor.y, anchor.z-.13), anchor, .015, grey)
    note('TRAINING SIMULATION · FLIGHT_EVA HOLD · PROTOTYPE, NOT CERTIFIED — DR-EVA-03 presents a tool cartridge to a suited crew member '
         '(DOP-04 supervised handoff); foot restraint and tether anchor are training fixtures; no anchor, thermal or debris release')
    c = Vector(((tool.x+fx)/2, (tool.y+fy)/2, .62))
    camera(c, 5.0, 8, 8, lens=40); shoot(out/'accessory_eva_handoff.png')                     # profile: crew, handle and crawler in one line
    camera(c, 5.2, -38, 20, lens=40); shoot(out/'accessory_eva_handoff_3q.png')
    camera(tool, .9, 0, 15, lens=50); shoot(out/'accessory_eva_grasp_closeup.png')
    if args.glb:                                                              # the composed scene for the standalone review viewer
        export_static(out/'accessory_eva_handoff.glb')


def export_static(path):
    """The posed scene as static meshes (deformation applied, no skins or actions) for the accessory viewer."""
    for o in bpy.context.scene.objects:
        o.select_set(o.type == 'MESH' and not o.hide_render and o.visible_get())
    bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', use_selection=True, export_apply=True, export_skins=False,
                              export_animations=False, export_extras=True)


def iva(args, out, B):
    bpy.ops.wm.read_factory_settings(use_empty=True); render_setup(args.size, args.quality)
    deck = mat('Deck', (.42, .43, .44), .7); wall = mat('Wall', (.72, .72, .69), .6); grey = mat('Fixture_Grey', (.36, .37, .38), .55, .3)
    yellow = mat('Guide', (.25, .26, .27), .4, .6)
    block('Deck', (0, 0, -.01), (4.0, 2.4, .02), deck); block('Wall', (0, 1.2, 1.0), (4.0, .04, 2.0), wall)
    block('Deck_Guide_Channel', (0, -.45, .002), (3.6, .04, .004), yellow)     # the retained surface guide: an interface request (not in the ship)
    b2 = B['DR-IVA-02']; E2 = append_drone('DR-IVA-02', (-.55, -.45, 0)); apply_pose(b2, E2, key_values(b2, 'arm_pick', 4.5))
    b1 = B['DR-IVA-01']; v1 = key_values(b1, 'perch', 4); g = Vector(db.at(b1, 'arm_grip', (-.012, 0, -.012), v1))
    rail = Vector((.35, .95, .95)); E1 = append_drone('DR-IVA-01', tuple(rail-g)); apply_pose(b1, E1, v1)
    rod('Handrail', (rail.x-.5, rail.y, rail.z), (rail.x+.5, rail.y, rail.z), .016, grey)
    for x in (rail.x-.45, rail.x+.45):
        rod('Handrail_Standoff', (x, rail.y, rail.z), (x, 1.18, rail.z), .012, grey)
    b3 = B['DR-IVA-03']; E3 = append_drone('DR-IVA-03', (.55, -.75, .0)); apply_pose(b3, E3, key_values(b3, 'probe_inspect', 2))
    block('Raceway_Floor', (.62, -.75, -.004), (.5, .14, .008), grey)
    for y in (-.83, -.67):
        block('Raceway_Wall', (.62, y, .045), (.5, .01, .09), grey)
    block('Raceway_Sensor_Port', (.79, -.75, .002), (.03, .05, .004), mat('Port', (.1, .1, .1)))
    note('PROTOTYPE · L4 visual candidates — DR-IVA-02 picks its cargo cartridge on a deck guide (guide channel: interface request) · '
         'DR-IVA-01 perched on a handrail, fans off · DR-IVA-03 probing a sensor port in a designed raceway (conduits: DS-09 HOLD)')
    camera((.0, .15, .5), 3.6, -112, 16, lens=36); shoot(out/'accessory_iva_tasks.png')
    if args.glb:
        export_static(out/'accessory_iva_tasks.glb')


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); ap.add_argument('--scenes', nargs='*', default=['eva', 'iva'])
    ap.add_argument('--quality', default='draft'); ap.add_argument('--size', nargs=2, type=int, default=[1600, 1000])
    ap.add_argument('--action', default='eva_suit_check'); ap.add_argument('--frame', type=float, default=0.0)
    ap.add_argument('--glb', action='store_true', help='also export the scenes as static GLBs (accessory viewer)')
    args = ap.parse_args(argv); out = args.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    s, d = db.load(ROOT); B = db.bodies(s, d)
    if 'eva' in args.scenes:
        eva(args, out, B)
    if 'iva' in args.scenes:
        iva(args, out, B)


if __name__ == '__main__':
    main()
