"""Export the suited induction pair for Godot (TODO EVA-001, docs/EVA.md; S&E 44 EXP-01, EXP-03).

  blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/export/eva_gltf.py -- [--out godot/generated/characters]

Each assets/characters/WF_EVA_<ID>.blend becomes <out>/eva_<id>.glb: the wearer's unchanged game_engine skeleton, the skinned soft layers
(with the corrective morph targets), the bone-attached rigid parts and sockets (Godot BoneAttachment3D nodes), and one animation per NLA
track (the five shared actions, the stage poses and the eight EVA actions; the fold-out hand controller's links join the stage-pose
animation). Then the EVA system (export_system): eva_system.glb, eva_drone.glb and eva_system.json. The full validation body is not exported; the cutaway parts
are, and <out>/eva_characters.json lists them so the runtime hides them until the "Show me" cutaway. The JSON also carries, per node, its
assembly, part id and job, and per EVA action its length, loop flag, travel speed and protocol events. Nothing here edits the assets.
"""
import argparse
import json
import re
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer')]
import eva_suit as es
import eva_system as es_ev


def export(key, out):
    path = ROOT/'assets/characters'/f'WF_EVA_{key.upper()}.blend'
    bpy.ops.wm.open_mainfile(filepath=str(path)); sc = bpy.context.scene
    root = bpy.data.collections['WAYFARER_EVA_Y155']; objs = list(root.all_objects); rig = next(o for o in objs if o.type == 'ARMATURE')
    for o in objs:                                        # the rig's tracks, and the hand controller links' EVA_SYSTEM_POSES tracks
        if o.animation_data:
            o.animation_data.action = None
            for tr in o.animation_data.nla_tracks:
                tr.mute = False
    nodes = {}; keep = []
    for o in objs:
        if o.get('eva_role') == 'validation_body':
            continue
        o.hide_viewport = False; o.hide_set(False); keep.append(o)
        nodes[o.name] = dict(assembly=o.get('assembly', ''), part_id=o.get('part_id', ''), job=o.get('job', ''), show=o.get('eva_show', 'always'),
                             bone=o.parent_bone if o.parent_type == 'BONE' else '')
    sc.frame_set(0); bpy.ops.object.select_all(action='DESELECT')
    for o in keep:
        o.select_set(True)
    bpy.context.view_layer.objects.active = rig
    glb = out/f'eva_{key}.glb'
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True, export_yup=True, export_apply=False,
                              export_skins=True, export_morph=True, export_morph_animation=True, export_animations=True, export_animation_mode='NLA_TRACKS',
                              export_force_sampling=True, export_frame_step=1, export_def_bones=False, export_extras=True,
                              export_influence_nb=4, export_all_influences=False, export_materials='EXPORT',
                              export_optimize_animation_size=False, export_optimize_animation_keep_anim_armature=True)
    acts = {}
    for tr in rig.animation_data.nla_tracks:
        a = tr.strips[0].action; lo, hi = (int(x) for x in a.frame_range)
        rec = dict(frames=hi-lo+1, loop=bool(a.get('loop', False)), eva=bool(a.get('eva', False)))
        for k in ('travel_speed_m_s', 'events', 'point_dir_body', 'anchors_body'):
            if a.get(k):
                rec[k] = json.loads(a[k])
        acts[a.name] = rec
    return dict(key=key, wearer=rig.name, glb=glb.name, glb_bytes=glb.stat().st_size, stature_m=rig.get('eva_stature', None), nodes=nodes,
                cutaway=sorted(n for n, v in nodes.items() if v['show'] == 'cutaway'), actions=acts, helmet=json.loads(rig['eva_helmet']),
                eva_actions=list(es.EVA_ACTIONS), geometry_status='PROTOTYPE', certification=root.get('certification', ''))


def export_system(out):
    """The EVA system for the runtime: eva_system.glb (both the suited instructor and the drone, one SYSTEM_STATES animation over the 13
    states, every driven part, the dock constraint and the hand controller baked per frame), eva_drone.glb (the drone alone with its
    DRONE_DOCK_SEQUENCE / DRONE_UNDOCK_SEQUENCE / DRONE_STATES animations, baked) and eva_system.json (state frames, thruster state,
    live nozzles, articulation controls and limits, the hand controller's stops). Nothing here edits the assets."""
    path = ROOT/'assets/characters/WF_EVA_SYSTEM.blend'; bpy.ops.wm.open_mainfile(filepath=str(path)); sc = bpy.context.scene
    states = json.loads(sc['eva_states']); drone = bpy.data.objects['RIG_EVA_DRONE']; suit = bpy.data.objects[drone['astronaut_rig']]
    dinfo = json.loads(drone['eva_drone']); hcd = json.loads(suit['eva_hand_controller'])
    vis = [o for o in sc.objects if o.visible_get() and not o.hide_render and o.get('eva_role') != 'validation_body' and o.type in ('MESH', 'ARMATURE', 'EMPTY')
           and not o.name.startswith(('PLUME_', 'STUDIO_', 'REF_', 'LIGHT_', 'CAM_'))]
    is_drone = lambda o: o is drone or o.parent is drone or (o.parent and o.parent.parent is drone) or o.name.startswith(('DRN_', 'ARM_', 'TOOL_', 'SENS_Drone',
                                                                                                                       'THR_Drone', 'NZ_DRN', 'DOCK_Drone', 'N2_Drone'))
    def gltf(fp, objs, mode):
        bpy.ops.object.select_all(action='DESELECT')
        for o in objs:
            o.hide_set(False); o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.export_scene.gltf(filepath=str(fp), export_format='GLB', use_selection=True, export_yup=True, export_apply=False, export_skins=True,
                                  export_morph=True, export_animations=True, export_animation_mode=mode, export_bake_animation=True,
                                  export_force_sampling=True, export_frame_step=1, export_def_bones=False, export_extras=True, export_influence_nb=4,
                                  export_materials='EXPORT', export_optimize_animation_size=False, export_anim_scene_split_object=False)
        return fp.stat().st_size
    sc.frame_start = 0; sc.frame_end = len(states)*10-1
    sys_bytes = gltf(out/'eva_system.glb', [suit]+[o for o in vis if o is not suit], 'SCENE')
    dobjs = [drone]+[o for o in vis if o is not drone and is_drone(o)]
    ad = drone.animation_data; states_act = ad.action
    if states_act and not ad.nla_tracks.get('DRONE_STATES'):
        tr = ad.nla_tracks.new(); tr.name = 'DRONE_STATES'; tr.strips.new('DRONE_STATES', 0, states_act); tr.mute = True
    ad.action = None
    for tr in ad.nla_tracks:
        tr.mute = False; tr.name = re.sub(r'\.\d{3}$', '', tr.name)     # appended copies carry .NNN suffixes: the runtime sees the plain name
    drone_bytes = gltf(out/'eva_drone.glb', dobjs, 'NLA_TRACKS')
    arms = {K: dict(joints=a['joints'], tip_force_n=a['tip_force_n'], role=a['role']) for K, a in es_ev.ARMS.items()}
    return dict(contract='eva_system v1', status='PROTOTYPE', glb=dict(system='eva_system.glb', drone='eva_drone.glb'), bytes=dict(system=sys_bytes, drone=drone_bytes),
                fps=sc.render.fps, segment_frames=10, animation='SYSTEM_STATES (one clip, scene timeline)',
                states=[dict(s, frames=[s['frame'], s['frame']+9]) for s in states], drone_animations=[t.name for t in ad.nla_tracks],
                nozzles=dict(suit=json.loads(suit['eva_module'])['nozzles'], drone=dinfo['nozzles'],
                             drone_inhibited_near_suit=[n for n in dinfo['nozzles'] if bpy.data.objects[n].get('inhibit_docked')]),
                controls=dict(drone_props=['docked', 'capture', 'latch', 'elec', 'n2', 'prop_mode', 'bay_A', 'bay_B', 'grip_A', 'grip_B', 'lights', 'tool_A_driver'],
                              arm_bones={K: [b.name for b in drone.pose.bones if b.name.startswith(f'arm_{K}_')] for K in es_ev.ARMS}, arms=arms,
                              hand_controller=dict(nodes=hcd['links'], stops=hcd['stops'], deploy_poses=hcd['deploy_poses'])),
                objects=sorted(o.name for o in vis))


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, default=ROOT/'godot/generated/characters'); ap.add_argument('--only', nargs='*')
    a = ap.parse_args(argv); a.out.mkdir(parents=True, exist_ok=True); data = es.load(ROOT)
    manifest = dict(contract='eva_characters v1', suit=data['suit']['id'], status=data['suit']['status'], certification=data['suit']['certification'],
                    variants={k: export(k, a.out) for k in (a.only or list(data['variant']))})
    (a.out/'eva_characters.json').write_text(json.dumps(manifest, indent=1)+'\n')
    if not a.only:
        sysm = export_system(a.out); (a.out/'eva_system.json').write_text(json.dumps(sysm, indent=1)+'\n')
        print('WF_EVA_SYSTEM_EXPORTED', sysm['bytes'], flush=True)
    print('WF_EVA_EXPORTED', ' '.join(f"{k}:{v['glb_bytes']}" for k, v in manifest['variants'].items()), flush=True)


if __name__ == '__main__':
    main()
