"""Character rig review (docs/CHARACTERS.md "Validation"): reopen each saved human, check that it is what the build reported (fingerprint
after save and reopen), pose it through extreme test postures with the shared solver and measure deformation, sample every action,
and render a review sheet.

  blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/validation/human_rig.py -- \
      [--only test_a ...] [--report references/p1_human_rig.json] [--renders runs/renders/p1/human_system] [--size 512]

Deformation metrics, per posture against the rest pose (body mesh only): volume change (closed-mesh signed volume; the MPFB body is
open at the eyes, so this is a comparison number, not a physical volume), the share of edges stretched beyond 1.6x or shrunk below 0.5x,
and the worst edge ratios. Thresholds are review flags, not engineering limits.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build')]
import characters as ch
import human_system as hs
from human import Solver, fingerprint, body_measures

FLAGS = dict(stretch=1.6, shrink=0.5, share=0.002, volume=0.06)


def postures(H, P):
    """Extreme test postures as source frames (procedural, at the body's own proportions)."""
    saved = dict(ch.P); ch.P.update(P)
    try:
        fig = hs.figure(H); l1, l2, la, _ = hs.leg_lengths(H); stand = (0.0, 0.0, l1+l2+la-.005)
        arms = lambda flex, abduct, elbow: dict(right=dict(flex=flex, abduct=abduct, elbow=elbow), left=dict(flex=flex, abduct=abduct, elbow=elbow))
        def pose(name, p, hip=stand, feet=True, up=hs.UP, fwd=hs.FORWARD):
            j = ch.skeleton(fig, dict(ch.STAND, **p), hip, up, fwd)
            if feet:
                right = ch.frame(hs.UP, hs.FORWARD)[0]
                ank = {s: (sg*ch.P['hip_x']*H*1.2*right[0], 0.0, la) for s, sg in zip(hs.SIDES, (1, -1))}
                j = hs.legs_to(j, H, ank, hs.FORWARD, hs.UP)
            return name, hs.frame_of(j, (0.0, 0.0, 0.0), ())
        return dict([
            pose('rest_stand', {}),
            pose('arms_overhead', dict(arms=arms(170.0, 10.0, 5.0))),
            pose('arms_forward_elbows_140', dict(arms=arms(80.0, 5.0, 140.0))),
            pose('arms_side_90', dict(arms=arms(0.0, 90.0, 10.0))),
            pose('trunk_forward_45_head_down', dict(trunk=45.0, head=40.0, arms=arms(30.0, 10.0, 20.0))),
            pose('deep_squat', dict(trunk=35.0, arms=arms(70.0, 10.0, 30.0)), hip=(0.0, .18, la+.42)),
            pose('high_step_knee_120', dict(hip=(110.0, 0.0), knee=(120.0, 0.0), arms=arms(20.0, 10.0, 30.0)), hip=stand, feet=False),
        ])
    finally:
        ch.P.clear(); ch.P.update(saved)


def body_mesh(rig):
    return next(o for o in rig.children if o.name.endswith('_Body'))


def evaluated(obj):
    dg = bpy.context.evaluated_depsgraph_get(); e = obj.evaluated_get(dg); m = e.to_mesh()
    co = np.array([tuple(v.co) for v in m.vertices]); bm = bmesh.new(); bm.from_mesh(m); vol = abs(bm.calc_volume(signed=True)); bm.free()
    e.to_mesh_clear(); return co, vol


def edge_ratios(rest, posed, edges):
    a = np.linalg.norm(rest[edges[:, 0]]-rest[edges[:, 1]], axis=1); b = np.linalg.norm(posed[edges[:, 0]]-posed[edges[:, 1]], axis=1)
    return b/np.maximum(a, 1e-9)


def apply(rig, solver, frame):
    basis, _, _ = solver.solve(frame)
    for b, m in basis.items():
        pb = rig.pose.bones[b]; pb.rotation_mode = 'QUATERNION'; pb.rotation_quaternion = m.to_quaternion()
        if b in ('Root', 'pelvis'):
            pb.location = m.translation
    bpy.context.view_layer.update()


def clear_pose(rig):
    rig.animation_data_create(); rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
    bpy.context.view_layer.update()


def setup_render(size):
    sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sh = sc.display.shading
    sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True; sh.show_object_outline = True
    sc.render.resolution_x = sc.render.resolution_y = size; sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new('W'); sc.world.color = (.9, .9, .92)
    cam = bpy.data.objects.get('WF_REVIEW_CAM') or bpy.data.objects.new('WF_REVIEW_CAM', bpy.data.cameras.new('WF_REVIEW_CAM'))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    sc.camera = cam; return cam


def shoot(cam, rig, path, view):
    """Frame the evaluated body from the front-left three-quarter (or the side) and render."""
    co, _ = evaluated(body_mesh(rig)); co = co @ np.array(rig.matrix_world.to_3x3()).T+np.array(rig.matrix_world.translation)
    lo, hi = co.min(0), co.max(0); c = Vector(((lo+hi)/2).tolist()); r = float(np.linalg.norm(hi-lo))/2
    d = Vector({'q': (-.75, -1.0, .35), 's': (-1.0, 0.0, .1), 'f': (0.0, -1.0, .1)}[view]).normalized()
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 2.15*r; cam.location = c+d*6
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler(); cam.data.clip_end = 50
    bpy.context.scene.render.filepath = str(path); bpy.ops.render.render(write_still=True)


def sheet(paths, out, cols):
    imgs = []
    for p in paths:
        im = bpy.data.images.load(str(p)); a = np.array(im.pixels[:]).reshape(im.size[1], im.size[0], 4); imgs.append(a); bpy.data.images.remove(im)
    h, w = imgs[0].shape[:2]; rows = math.ceil(len(imgs)/cols); grid = np.ones((rows*h, cols*w, 4))
    for i, a in enumerate(imgs):
        r, c = divmod(i, cols); grid[(rows-1-r)*h:(rows-r)*h, c*w:(c+1)*w] = a
    im = bpy.data.images.new('sheet', cols*w, rows*h); im.pixels = grid.ravel(); im.filepath_raw = str(out); im.file_format = 'PNG'; im.save()


def review(key, args, report):
    path = ROOT/'assets/characters'/f'WF_CHAR_HUMAN_{key.upper()}.blend'
    bpy.ops.wm.open_mainfile(filepath=str(path)); built = json.loads((ROOT/'references/p1_human_system.json').read_text())['characters'][key]
    rig = bpy.data.objects[f'CHAR_{key.upper()}']; out = dict(fingerprint_matches_build=fingerprint(rig) == built['fingerprint'])
    clear_pose(rig); body = body_mesh(rig); rest, vol0 = evaluated(body)
    edges = np.array([tuple(e.vertices) for e in body.data.edges])
    H = built['stature_m']; P = hs.proportions({b.name: (tuple(b.head_local), tuple(b.tail_local)) for b in rig.data.bones}, H)
    solver = Solver(rig, hs.actions(H, json.loads(json.dumps({'walk_speed_m_s': 1, 'walk_cadence_steps_min': 100, 'step_height_m': .1,
                                                             'crawl_speed_m_s': .3, 'climb_rungs_per_s': 1})), 30, .45, .3, P)['rest'])
    cam = setup_render(args.size); shots = []; rdir = args.renders; rdir.mkdir(parents=True, exist_ok=True)
    clear_pose(rig)
    for view in ('f', 's'):
        p = rdir/f'{key}_rest_{view}.png'; shoot(cam, rig, p, view); shots.append(p)
    out['postures'] = {}
    for name, frame in postures(H, P).items():
        clear_pose(rig); apply(rig, solver, frame); co, vol = evaluated(body); r = edge_ratios(rest, co, edges)
        m = dict(volume_change=round(vol/vol0-1, 4), stretched_share=round(float((r > FLAGS['stretch']).mean()), 5),
                 shrunk_share=round(float((r < FLAGS['shrink']).mean()), 5), max_ratio=round(float(r.max()), 3), min_ratio=round(float(r.min()), 3))
        m['flag'] = (abs(m['volume_change']) > FLAGS['volume'] or m['stretched_share'] > FLAGS['share'] or m['shrunk_share'] > FLAGS['share'])
        out['postures'][name] = m
        if name != 'rest_stand':
            p = rdir/f'{key}_{name}.png'; shoot(cam, rig, p, 'q'); shots.append(p)
    out['actions'] = {}
    for act in sorted((a for a in bpy.data.actions if a.get('contacts')), key=lambda a: (a.name not in hs.ACTIONS, hs.ACTIONS.index(a.name) if a.name in hs.ACTIONS else 0, a.name)):
        clear_pose(rig); rig.animation_data.action = act; lo, hi = (int(x) for x in act.frame_range); worst = 0.0
        for f in range(lo, hi+1, 3):
            bpy.context.scene.frame_set(f); co, _ = evaluated(body); worst = max(worst, float(edge_ratios(rest, co, edges).max()))
        out['actions'][act.name] = dict(frames=hi-lo+1, max_edge_ratio=round(worst, 3))
        bpy.context.scene.frame_set((lo+hi)//2); p = rdir/f'{key}_action_{act.name}.png'; shoot(cam, rig, p, 'q' if act.name != 'climb' else 's'); shots.append(p)
        rig.animation_data.action = None
    clear_pose(rig); bpy.context.scene.frame_set(0)
    co, _ = evaluated(body)
    out['rest_extent_m'] = dict(width_x=round(float(np.ptp(co[:, 0])), 3), depth_y=round(float(np.ptp(co[:, 1])), 3), height_z=round(float(np.ptp(co[:, 2])), 3))
    sh = co[np.abs(co[:, 2]-rig.data.bones['upperarm_l'].head_local.z) < .03]
    out['shoulder_breadth_m'] = round(float(np.ptp(sh[:, 0])), 3)
    sheet(shots, rdir/f'{key}_sheet.png', 4); out['sheet'] = str((rdir/f'{key}_sheet.png').relative_to(ROOT))
    report[key] = out
    print(f'WF_RIG {key} {json.dumps(out)}', flush=True)


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--only', nargs='*'); ap.add_argument('--size', type=int, default=512)
    ap.add_argument('--report', type=Path, default=ROOT/'references/p1_human_rig.json'); ap.add_argument('--renders', type=Path, default=ROOT/'runs/renders/p1/human_system')
    args = ap.parse_args(argv); data = hs.load(ROOT); report = {}
    for key in args.only or list(data['human']):
        review(key, args, report)
    args.report.write_text(json.dumps(dict(flags=FLAGS, characters=report), indent=1)+'\n')


if __name__ == '__main__':
    main()
