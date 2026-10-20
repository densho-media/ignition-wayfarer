"""Export the generated humans for Godot (docs/CHARACTERS.md "Blender to Godot").

  blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/export/human_gltf.py -- [--only test_a ...] [--out <dir>]

Each assets/characters/WF_CHAR_HUMAN_<ID>.blend becomes <out>/<id>.glb (default godot/generated/characters): the game_engine skeleton,
the skinned meshes (at most four weights) with the corrective shape keys as morph targets, and one glTF animation per NLA track (idle,
walk, sit, crawl, climb), the exporter sampling the correctives' driven weights into each. <out>/characters.json
records, per character, the contract (bones, stature, axes), each action's frame count, loop and root-motion flags and held contacts,
and Blender's evaluated world positions of the check bones and the corrective weights at sampled frames, in Godot axes (x, z, -y): check_characters.gd compares
the imported animation against them. Nothing here edits the source assets.
"""
import argparse
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer')]
import human_system as hs

CHECK_BONES = ('pelvis', 'head', 'hand_l', 'hand_r', 'foot_l', 'foot_r', 'calf_l', 'calf_r')
LIMB_BONE = dict(foot_right='foot_r', foot_left='foot_l', hand_right='hand_r', hand_left='hand_l', knee_right='calf_r', knee_left='calf_l')


def godot(v):
    return [round(v[0], 5), round(v[2], 5), round(-v[1], 5)]


def export(key, out):
    path = ROOT/'assets/characters'/f'WF_CHAR_HUMAN_{key.upper()}.blend'
    bpy.ops.wm.open_mainfile(filepath=str(path)); rig = bpy.data.objects[f'CHAR_{key.upper()}']
    sc = bpy.context.scene; rig.animation_data.action = None
    for tr in rig.animation_data.nla_tracks:
        tr.mute = False
    record = dict(key=key, rig=rig.name, bones=[b.name for b in rig.data.bones], root_bone='Root', fps=sc.render.fps,
                  stature_m=max(v.co.z for o in rig.children if o.type == 'MESH' for v in o.data.vertices), front='+Z (glTF), Blender -Y',
                  geometry_status='PROTOTYPE', identity_ref=rig.get('identity_ref', ''), actions={})
    body = next(o for o in rig.children if o.name.endswith('_Body')); keys = body.data.shape_keys.key_blocks[1:] if body.data.shape_keys else []
    record['correctives'] = [k.name for k in keys]               # CHAR-001: driven shape keys, exported as morph targets with their sampled weights
    for tr in rig.animation_data.nla_tracks:                    # sample each action alone, assigned directly (NLA evaluation differs)
        act = tr.strips[0].action
        for t2 in rig.animation_data.nla_tracks:
            t2.mute = True
        rig.animation_data.action = act; rig.animation_data.action_slot = act.slots[0]
        lo, hi = (int(x) for x in act.frame_range); contacts = json.loads(act['contacts']); samples = {}; weights = {}
        for f in sorted({lo, (lo+hi)//2, hi, *range(lo, hi+1, 6)}):
            sc.frame_set(f); samples[str(f-lo)] = {b: godot(rig.matrix_world @ rig.pose.bones[b].head) for b in CHECK_BONES}
            weights[str(f-lo)] = {k.name: round(k.value, 4) for k in keys}
        record['actions'][act.name] = dict(frames=hi-lo+1, loop=bool(act['loop']), root_motion=bool(act['root_motion']),
                                           contacts=[[LIMB_BONE[c] for c in cs] for cs in contacts], samples=samples, weights=weights)
    rig.animation_data.action = None
    for tr in rig.animation_data.nla_tracks:
        tr.mute = False
    sc.frame_set(0)
    bpy.ops.object.select_all(action='DESELECT')
    for o in [rig, *rig.children]:
        o.select_set(True)
    bpy.context.view_layer.objects.active = rig
    glb = out/f'{key}.glb'
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True, export_yup=True, export_apply=False,
                              export_skins=True, export_morph=True, export_morph_animation=True, export_animations=True, export_animation_mode='NLA_TRACKS',
                              export_force_sampling=True, export_frame_step=1, export_def_bones=False, export_extras=True,
                              export_influence_nb=4, export_all_influences=False, export_materials='EXPORT',
                              export_optimize_animation_size=False, export_optimize_animation_keep_anim_armature=True)   # every bone keyed in every clip
    record['glb'] = glb.name; record['glb_bytes'] = glb.stat().st_size
    if rig.get('stage'):                                        # the induction staging: placement and posed check bones, in Godot axes
        stages = json.loads(rig['stages']) if rig.get('stages') else {json.loads(rig['stage'])['scene']: json.loads(rig['stage'])}
        C = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))
        for st in stages.values():                              # S004A for both; S004B (the couch) for the newcomer (CHAR-001)
            M = Matrix(st['matrix']); G = C @ M @ C.inverted(); act = bpy.data.actions[st['action']]
            rig.animation_data.action = act; rig.animation_data.action_slot = act.slots[0]; sc.frame_set(0); rig.matrix_world = M
            bpy.context.view_layer.update()
            st['placement_godot'] = dict(basis_columns=[[round(G[r][c], 6) for r in range(3)] for c in range(3)], origin=[round(G[r][3], 5) for r in range(3)])
            st['bones_godot'] = {b: godot(M @ rig.pose.bones[b].head) for b in CHECK_BONES}
        rig.animation_data.action = None; rig.matrix_world = Matrix.Identity(4); record['stage'] = stages['S004A']; record['stages'] = stages
    return record


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--only', nargs='*'); ap.add_argument('--out', type=Path, default=ROOT/'godot/generated/characters')
    args = ap.parse_args(argv); args.out.mkdir(parents=True, exist_ok=True)
    keys = args.only or list(hs.load(ROOT)['human'])
    manifest = dict(contract=dict(rig='game_engine', bones=len(hs.BONES), axes='Godot: x right of the model, y up, +z model front'),
                    characters={k: export(k, args.out) for k in keys})
    (args.out/'characters.json').write_text(json.dumps(manifest, indent=1)+'\n')
    print('WF_EXPORTED', ' '.join(f"{k}:{v['glb_bytes']}" for k, v in manifest['characters'].items()), flush=True)


if __name__ == '__main__':
    main()
