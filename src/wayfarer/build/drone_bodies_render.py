"""Shared render helpers for the drone renders and the accessory scenes (presentation/drone_preview.py, accessory_scene.py)."""
import math

import bpy
from mathutils import Vector


def apply_pose(b, E, values):
    idx = {'x': 0, 'y': 1, 'z': 2}
    for nid in b.joints():
        n = b.nodes[nid]; v = values.get(nid, 0.0); j = E[nid]
        j.rotation_euler = (0, 0, 0); j.location = (0, 0, 0)
        if n['joint'] == 'revolute':
            j.rotation_euler[idx[n['axis']]] = math.radians(v)
        else:
            j.location[idx[n['axis']]] = v
    bpy.context.view_layer.update()


def render_setup(size, quality):
    sc = bpy.context.scene; sc.render.resolution_x, sc.render.resolution_y = size; sc.render.film_transparent = False
    if quality == 'draft':
        sc.render.engine = 'BLENDER_WORKBENCH'; sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'
        sh.show_cavity = True; sh.cavity_type = 'BOTH'; sh.show_shadows = True; sh.show_specular_highlight = True
        sc.display.shadow_focus = .2
    elif quality == 'material':
        sc.render.engine = 'BLENDER_EEVEE'; sc.eevee.taa_render_samples = 16
    else:
        sc.render.engine = 'CYCLES'; sc.cycles.samples = 24 if quality == 'review' else 64; sc.cycles.use_denoising = True; sc.cycles.device = 'CPU'
    sc.view_settings.view_transform = 'AgX'
    w = bpy.data.worlds.get('DRONE_World') or bpy.data.worlds.new('DRONE_World'); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (.020, .022, .028, 1); bg.inputs['Strength'].default_value = 1.0
    for nm, rot, en in (('Key', (52, 0, -38), 4.0), ('Fill', (70, 0, 140), 1.0), ('Rim', (110, 0, 20), 1.6)):
        if nm in bpy.data.objects:
            continue
        L = bpy.data.lights.new(nm, 'SUN'); L.energy = en; L.angle = math.radians(3)
        o = bpy.data.objects.new(nm, L); sc.collection.objects.link(o); o.rotation_euler = [math.radians(a) for a in rot]


def camera(target, dist, az, el, lens=55, ortho=None):
    sc = bpy.context.scene; cam = sc.camera
    if cam is None:
        cd = bpy.data.cameras.new('Cam'); cam = bpy.data.objects.new('Cam', cd); sc.collection.objects.link(cam); sc.camera = cam
    t = Vector(target); d = Vector((math.cos(math.radians(el))*math.cos(math.radians(az)), math.cos(math.radians(el))*math.sin(math.radians(az)), math.sin(math.radians(el))))
    cam.location = t+d*dist; cam.rotation_euler = (t-cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens; cam.data.clip_start = .01; cam.data.clip_end = 200
    if ortho:
        cam.data.type = 'ORTHO'; cam.data.ortho_scale = ortho
    else:
        cam.data.type = 'PERSP'


def label(text, loc, size=.03, rot=(90, 0, 0), col=(.9, .9, .85)):
    cu = bpy.data.curves.new('Label', 'FONT'); cu.body = text; cu.size = size; cu.align_x = 'CENTER'
    o = bpy.data.objects.new('Label', cu); bpy.context.scene.collection.objects.link(o); o.location = loc; o.rotation_euler = [math.radians(a) for a in rot]
    m = bpy.data.materials.get('Label_Mat') or bpy.data.materials.new('Label_Mat'); m.use_nodes = True
    bs = m.node_tree.nodes['Principled BSDF']; bs.inputs['Base Color'].default_value = (*col, 1); bs.inputs['Emission Color'].default_value = (*col, 1)
    bs.inputs['Emission Strength'].default_value = 1.0; m.diffuse_color = (*col, 1); cu.materials.append(m); return o


def shoot(path):
    bpy.context.scene.render.filepath = str(path); bpy.ops.render.render(write_still=True); print(f'WF_RENDER {path.name}', flush=True)




def note(text):
    """Burn a status line into the render (stamp note): status words stay readable whatever the camera does."""
    r = bpy.context.scene.render; r.use_stamp = True; r.use_stamp_note = True; r.stamp_note_text = text
    for k in ('date', 'time', 'render_time', 'frame', 'frame_range', 'memory', 'hostname', 'camera', 'lens', 'scene', 'marker', 'filename',
              'sequencer_strip'):
        if hasattr(r, f'use_stamp_{k}'):
            setattr(r, f'use_stamp_{k}', False)
    r.stamp_font_size = 22; r.stamp_background = (0, 0, 0, .55)
