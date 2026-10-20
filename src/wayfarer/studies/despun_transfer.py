"""Q46 study (HUM-001): sections across each human-entry ring's despun transfer drum, looking aft from just forward of the crew-tube openings,
in memory on the saved vehicle (nothing is saved). States: closed (saved: drum despun at the index, gate, doors and tube hatches closed),
open (docked, indexed transfer: every closure open) and synced (COAST at frame 61: the ring has turned, the drum turns with it, its doors and
the selected tube's hatch open, the gate closed). Workbench, material colours.

    /snap/bin/blender -b --python src/wayfarer/studies/despun_transfer.py -- --out runs/<stamp>-q46
"""
from pathlib import Path
import argparse
import math
import sys
import bpy
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation')]
from spec import load
from common import pose_configuration, pose_transfer
import crew_transfer as ct
import rotor_interface as ri


def section(s, j, name, out, size, frame=1):
    rot = next(r for r in ri.rotors(s) if r['index'] == j); v = ct.vestibule(s, j); scene = bpy.context.scene
    x = rot['x']+v['hatch_u']+0.02; cam = bpy.data.objects.get('CAM_Q46') or bpy.data.objects.new('CAM_Q46', bpy.data.cameras.new('CAM_Q46'))
    if cam.name not in scene.collection.objects:
        scene.collection.objects.link(cam)
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 7.0; cam.data.clip_start = 2.0; cam.data.clip_end = 60.0
    cam.location = (x+2.0, 0.0, 0.0); cam.rotation_euler = (0.0, math.radians(90), 0.0)    # looks along -X (aft): +Z up, +Y left
    scene.camera = cam; scene.frame_set(frame)
    scene.render.engine = 'BLENDER_WORKBENCH'; scene.display.shading.light = 'STUDIO'; scene.display.shading.color_type = 'MATERIAL'
    scene.display.shading.show_cavity = True; scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.filepath = str(out/f'q46_ring_{"AB"[j-1]}_{name}.png'); bpy.ops.render.render(write_still=True)


def main(out, size):
    s = load(ROOT)[0]; out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
    for obj in bpy.data.objects:      # the sector interiors and figures do not matter here
        if obj.get('kind') in ('scale_reference',):
            obj.hide_render = True
    for state in ('closed', 'open', 'synced'):
        if state == 'synced':
            pose_configuration(s, 'COAST'); pose_transfer(s, 0.0, sync=1.0)
            gate = bpy.data.objects['CREW_PORT_GATE_CTRL']
            for j in s['human_entry']['vestibule_rotors']:
                c = bpy.data.objects[f'TRANSFER_{j}_CTRL']
                for k in (1, 2, 3):
                    c[f'door_open_{k}'] = 1.0
                c['hatch_open_1'] = 1.0; c.update_tag()
            frame = 61
        else:
            pose_configuration(s, 'DOCKED'); pose_transfer(s, 1.0 if state == 'open' else 0.0, sync=0.0); frame = 1
        for obj in bpy.data.objects:
            if obj.get('kind') in ('transfer_closure', 'transfer_drum'):
                obj.update_tag()
        for j in s['human_entry']['vestibule_rotors']:
            section(s, j, state, out, size, frame)
        print('WF_Q46', state, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--out', type=Path, required=True); p.add_argument('--size', type=int, default=900)
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    main(a.out.resolve(), a.size)
