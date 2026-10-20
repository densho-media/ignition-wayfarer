"""Export the suited induction pair for Godot (TODO EVA-001, docs/EVA.md; S&E 44 EXP-01, EXP-03).

  blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/export/eva_gltf.py -- [--out godot/generated/characters]

Each assets/characters/WF_EVA_<ID>.blend becomes <out>/eva_<id>.glb: the wearer's unchanged game_engine skeleton, the skinned soft layers
(with the corrective morph targets), the bone-attached rigid parts and sockets (Godot BoneAttachment3D nodes), and one animation per NLA
track (the five shared actions, the stage poses and the eight EVA actions). The full validation body is not exported; the cutaway parts
are, and <out>/eva_characters.json lists them so the runtime hides them until the "Show me" cutaway. The JSON also carries, per node, its
assembly, part id and job, and per EVA action its length, loop flag, travel speed and protocol events. Nothing here edits the assets.
"""
import argparse
import json
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer')]
import eva_suit as es


def export(key, out):
    path = ROOT/'assets/characters'/f'WF_EVA_{key.upper()}.blend'
    bpy.ops.wm.open_mainfile(filepath=str(path)); sc = bpy.context.scene
    root = bpy.data.collections['WAYFARER_EVA_Y155']; objs = list(root.all_objects); rig = next(o for o in objs if o.type == 'ARMATURE')
    rig.animation_data.action = None
    for tr in rig.animation_data.nla_tracks:
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


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, default=ROOT/'godot/generated/characters'); ap.add_argument('--only', nargs='*')
    a = ap.parse_args(argv); a.out.mkdir(parents=True, exist_ok=True); data = es.load(ROOT)
    manifest = dict(contract='eva_characters v1', suit=data['suit']['id'], status=data['suit']['status'], certification=data['suit']['certification'],
                    variants={k: export(k, a.out) for k in (a.only or list(data['variant']))})
    (a.out/'eva_characters.json').write_text(json.dumps(manifest, indent=1)+'\n')
    print('WF_EVA_EXPORTED', ' '.join(f"{k}:{v['glb_bytes']}" for k, v in manifest['variants'].items()), flush=True)


if __name__ == '__main__':
    main()
