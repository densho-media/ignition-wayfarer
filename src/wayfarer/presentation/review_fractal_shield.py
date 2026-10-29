"""Review file for the fractal shielding: the saved vehicle in the grammar look with the fractal ram face, saved as its own .blend that opens
in Material Preview on the Brow, so the owner reviews it in Blender without running anything. Presentation only: the vehicle asset is
never overwritten; linked data is made local so the review file is self-contained and can be downloaded alone (CI artifact
wayfarer-review-blend).

    /snap/bin/blender -b --python src/wayfarer/presentation/review_fractal_shield.py -- [--out review/WF_REVIEW_FRACTAL_SHIELD.blend]
"""
from pathlib import Path
import argparse
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation')]

import bpy
from mathutils import Vector

# Viewpoints on the Brow (Blender axes, +X bow): eye and target. The face is at X 112.5 m (flat hub) sweeping aft to X 109.5 m at r 45 m.
# The EYE views follow the r30 Eye layout (forward_defense.eye_layout, user 2026-10-29): F1 well centre at Y = Z = 21.2 m, face X ~110.7 m.
VIEWS = {'Whole_Brow': ((235.0, -95.0, 60.0), (110.0, 0.0, 0.0)),
         'EYE_Array': ((205.0, -30.0, 22.0), (110.5, 0.0, 0.0)),
         'EYE_Shell': ((124.0, 13.0, 27.0), (110.8, 21.2, 21.2)),
         'Plate_Field': ((132.0, -14.0, 30.0), (111.4, 0.0, 22.0)),
         'Close_1m': ((113.2, -1.2, 21.4), (111.45, 0.6, 21.0))}
START = 'EYE_Array'


def main(out):
    from common import pose_configuration
    from spec import load
    import hero_preview as hp
    import production_detail as pd
    s = load(ROOT)[0]
    pd.load_packs()
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
    if bpy.data.libraries:                                  # self-contained: the dressed materials are saved with the file
        bpy.ops.object.make_local(type='ALL')
    scene = bpy.context.scene
    pose_configuration(s, 'COAST'); scene.frame_set(scene.frame_current)
    hp.dress(s, functional=True, emit=False, grammar=True)
    col = bpy.data.collections.new('REVIEW_FRACTAL_SHIELD'); scene.collection.children.link(col)
    cams = {}
    for name, (eye, target) in VIEWS.items():
        cd = bpy.data.cameras.new('Review_'+name); cd.lens = 35.0; cd.clip_start = 0.05; cd.clip_end = 3000.0
        cam = bpy.data.objects.new(cd.name, cd); col.objects.link(cam)
        cam.location = eye; cam.rotation_euler = (Vector(target)-Vector(eye)).to_track_quat('-Z', 'Y').to_euler()
        cams[name] = cam
    scene.camera = cams[START]
    eye, target = (Vector(v) for v in VIEWS[START])
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != 'VIEW_3D':
                continue
            for space in area.spaces:
                if space.type != 'VIEW_3D':
                    continue
                space.shading.type = 'MATERIAL'
                space.clip_start = 0.05; space.clip_end = 3000.0; space.lens = 35.0
                r3d = space.region_3d
                r3d.view_perspective = 'PERSP'
                r3d.view_location = target
                r3d.view_distance = (target-eye).length
                r3d.view_rotation = (target-eye).to_track_quat('-Z', 'Y')
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True, copy=True)
    print('WF_REVIEW_FRACTAL_SHIELD', out, out.stat().st_size)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, default=ROOT/'review/WF_REVIEW_FRACTAL_SHIELD.blend')
    a = ap.parse_args(argv)
    main(a.out if a.out.is_absolute() else ROOT/a.out)
