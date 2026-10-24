"""Review renders of the maintenance-drone body family (docs/ACCESSORIES.md; build/drone_bodies.py first).

  blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/presentation/drone_preview.py -- \
      --out <dir> [--views lineup classes closeups review cradles] [--only DR-EVA-03 ...] [--quality draft|material|review] [--size 1280 800]

Opens the saved assets/drones/WF_DRONE_<ID>.blend files in memory (never saves): `lineup` puts every class at one scale beside a 1.80 m
scale post (the suited instructor if assets/characters/WF_EVA_INSTRUCTOR.blend exists); `classes` renders each class stowed on its
review stand and at a working keyframe of its main action; `closeups` the GU-SIF dock, tool changer and recovery fittings. Labels name
classes and functions, never performance values (all OPEN).
"""
import argparse
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build')]
import drone_bodies as db
from drone_bodies_render import apply_pose, camera, label, note, render_setup, shoot   # noqa: E402  (shared render helpers)

MAIN = db.MAIN


def ident(cid):
    return f'WF_DRONE_{cid.replace("-", "_")}'


def append(cid, offset=(0, 0, 0), fixture=True, rot=0.0):
    path = ROOT/'assets/drones'/f'{ident(cid)}.blend'
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c in (f'GEN_{ident(cid)}', f'REVIEW_FIXTURE_{ident(cid)}')]
    E = {}
    for c in dst.collections:
        if c is None or (not fixture and c.name.startswith('REVIEW')):
            continue
        bpy.context.scene.collection.children.link(c)
        for o in c.objects:
            if o.get('drone_joint'):
                E[o['drone_joint']] = o
    top = [o for c in dst.collections if c for o in c.objects if o.parent is None]
    for o in top:
        o.location = Vector(o.location)+Vector(offset); o.rotation_euler[2] += math.radians(rot)
    if not fixture:
        for c in dst.collections:
            if c and c.name.startswith('REVIEW'):
                for o in c.objects:
                    o.hide_render = True
    return E


def key_values(b, action, t):
    best = None
    for fr, vals in db.frames(b, action):
        if fr <= round(t*db.FPS):
            best = vals
    return best or {}


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def suit_reference(offset):
    """The suited instructor as the human scale reference, if built; else a 1.80 m post with 0.1 m marks."""
    path = ROOT/'assets/characters/WF_EVA_INSTRUCTOR.blend'
    if path.exists():
        with bpy.data.libraries.load(str(path), link=False) as (src, dst):
            dst.collections = [c for c in src.collections if c == 'WAYFARER_EVA_Y155']
        c = dst.collections[0]; bpy.context.scene.collection.children.link(c)
        rig = next(o for o in c.all_objects if o.type == 'ARMATURE'); rig.location = offset
        if rig.animation_data:
            rig.animation_data.action = None
            for tr in rig.animation_data.nla_tracks:
                tr.mute = True
        return 'WAYFARER_EVA_Y155 instructor (1.78 m)'
    bpy.ops.mesh.primitive_cylinder_add(radius=.02, depth=1.8, location=(offset[0], offset[1], .9))
    return '1.80 m scale post'


def floor(size=12, z=-0.17):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z)); p = bpy.context.object
    m = bpy.data.materials.new('Floor'); m.use_nodes = True; m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.05, .055, .06, 1)
    m.diffuse_color = (.05, .055, .06, 1); p.data.materials.append(m)


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); ap.add_argument('--views', nargs='*', default=['lineup', 'classes', 'closeups'])
    ap.add_argument('--only', nargs='*'); ap.add_argument('--quality', default='draft'); ap.add_argument('--size', nargs=2, type=int, default=[1280, 800])
    args = ap.parse_args(argv); out = args.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    s, d = db.load(ROOT); B = db.bodies(s, d); order = args.only or list(B)
    body = lambda b: {q['part'] for q in b.shapes if not q['part'].startswith('FIXTURE')}
    if 'lineup' in args.views:
        for name, group in (('drone_lineup_mobile', [c for c in order if not c.startswith('DR-FIX')]), ('drone_lineup_fixed', [c for c in order if c.startswith('DR-FIX')])):
            if not group:
                continue
            clear(); render_setup(args.size, args.quality); floor(size=40, z=-.001); x = 0.0; gap = .22 if 'mobile' in name else .6
            for cid in group:
                lo, hi = db.envelope(B[cid], {}, include=body(B[cid])); w = hi[0]-lo[0]; x += w/2+gap
                append(cid, (x-(lo[0]+hi[0])/2, 0, -lo[2]), fixture=False)
                label(cid, (x, -.42 if 'mobile' in name else -.8, .002), .045 if 'mobile' in name else .09, rot=(0, 0, 0)); x += w/2
            note('WF_DRONE_FAMILY_Y155 · PROTOTYPE design candidates (L4_VISUAL_CANDIDATE), not integrated (54 DGT-017 HOLD) · '
                 '24 mobile units in 7 classes + 2 fixed arms (S&E 51) · mass, power, speed, reach, payload OPEN')
            who = suit_reference((x+.55, 0, 0)); label('scale: ' + who.split(' (')[0], (x+.55, -.42 if 'mobile' in name else -.8, .002), .03, rot=(0, 0, 0))
            span = x+.9; mid = span/2
            camera((mid, 0, .9), 20, -90, 0, ortho=span+.3); shoot(out/f'{name}.png')
            camera((mid, 0, .45), span*1.15, -66, 22, lens=40); shoot(out/f'{name}_3q.png')
    if 'classes' in args.views:
        for cid in order:
            b = B[cid]; clear(); render_setup(args.size, args.quality); E = append(cid)
            lo, hi = db.envelope(b, {}, include=body(b)); c = [(lo[i]+hi[i])/2 for i in range(3)]; ext = max(hi[i]-lo[i] for i in range(3))
            slo, shi = db.swept(b); sc_ = [(slo[i]+shi[i])/2 for i in range(3)]; sext = max(shi[i]-slo[i] for i in range(3))
            fixed = cid.startswith('DR-FIX'); floor(z=-.17 if 'travel' in b.nodes else (lo[2]-.01 if not fixed else -.002))
            apply_pose(b, E, {})
            camera(c, ext*2.1, -58, 24, lens=55); shoot(out/f'{ident(cid)}_stowed.png')
            act, t = MAIN[cid]; apply_pose(b, E, key_values(b, act, t))
            camera(sc_, sext*2.5, 32, 22, lens=55); shoot(out/f'{ident(cid)}_{act}.png')
            camera(c, ext*2.2, -90, 2, lens=55); apply_pose(b, E, {}); shoot(out/f'{ident(cid)}_side.png')
    if 'review' in args.views:                                   # the persistent review package: one lineup, one labelled 3/4 view per class
        import drone_fleet as df
        C = df.classes(s); rows, _ = db.check(s, d)
        dims = lambda cid: ' x '.join(f'{v:.2f}' for v in rows[cid]['stowed_m'])
        clear(); render_setup((2400, 1000), args.quality); floor(size=40, z=-.001); x = 0.0; tags = []
        for cid in order:
            lo, hi = db.envelope(B[cid], {}, include=body(B[cid])); w = hi[0]-lo[0]; gap = .30 if not cid.startswith('DR-FIX') else .45
            x += w/2+gap; append(cid, (x-(lo[0]+hi[0])/2, 0, -lo[2]), fixture=False)
            tags.append((f'{cid}\n{dims(cid)} m', x)); x += w/2
        who = suit_reference((x+.6, 0, 0)); tags.append(('suited instructor\n1.78 m (scale)' if 'instructor' in who else who, x+.6))
        for i, (text, tx) in enumerate(tags):                     # standing labels under the floor line (front view), staggered
            label(text, (tx, -.6, -.14-.22*(i % 2)), .075)
        note('WF_DRONE_FAMILY_Y155 · 7 mobile classes (24 units incl. 4 reserves) + 2 fixed arms (S&E 51) · stowed sizes from the fit screen · '
             'PROTOTYPE L4 visual candidates, NOT INTEGRATED (DGT-017 HOLD) · GU-SIF proposed (DGT-012 HOLD) · mass, power, speed, reach, payload OPEN')
        span = x+1.0
        camera((span/2, 0, .62), 30, -90, 0, ortho=span+.2); shoot(out/'review_drone_lineup.png')
        render_setup(args.size, args.quality)
        for cid in order:
            b = B[cid]; c = C[cid]; clear(); render_setup(args.size, args.quality); E = append(cid)
            act, t = MAIN[cid]; apply_pose(b, E, key_values(b, act, t))
            slo, shi = db.swept(b); sc_ = [(slo[i]+shi[i])/2 for i in range(3)]; sext = max(shi[i]-slo[i] for i in range(3))
            fixed = cid.startswith('DR-FIX'); lo, hi = db.envelope(b, {}, include=body(b))
            floor(z=-.17 if 'travel' in b.nodes else (lo[2]-.01 if not fixed else -.002))
            size = (f"stowed {dims(cid)} m in envelope class {rows[cid]['envelope_class_m']} m" if not fixed
                    else f"base {' x '.join(f'{v:.2f}' for v in rows[cid]['base_m'])} m, boom display only")
            note(f"{cid} {b.title} · {c['active']} active + {c['reserve']} reserve · {act} (SIMULATION_ONLY) · {size} · "
                 'PROTOTYPE L4, NOT INTEGRATED (DGT-017 HOLD) · GU-SIF proposed (DGT-012 HOLD) · performance OPEN')
            camera(sc_, sext*2.4, -52, 24, lens=50); shoot(out/f'review_{ident(cid)}.png')
    if 'cradles' in args.views:                                  # the PROTOTYPE docking cradles on the review stands, seen low from the crew side
        for cid in [c for c in order if c in ('DR-EVA-01', 'DR-EVA-02', 'DR-EVA-03')]:
            b = B[cid]; clear(); render_setup(args.size, args.quality); E = append(cid); apply_pose(b, E, {})
            floor(z=-.17)
            note(f'{cid} docked on its review stand: PROTOTYPE dock cradle (pedestal to the underside GU-SIF-M, V-guides, umbilical, '
                 'docked lamp, orange manual release) · review fixture, NOT ship geometry · latch, charge and alignment ratings OPEN (DGT-012 HOLD)')
            camera((0, 0, .02), 1.25, -112, 8, lens=45); shoot(out/f'cradle_{ident(cid)}.png')
    if 'closeups' in args.views:
        for cid in [c for c in order if c in ('DR-EVA-03', 'DR-IVA-01', 'DR-FIX-01', 'DR-IVA-03')]:
            b = B[cid]; clear(); render_setup(args.size, args.quality); E = append(cid); apply_pose(b, E, {})
            P = db.pose(b)
            k = 1.6 if cid.startswith('DR-EVA') else 1.0
            for item, nid, az, el, dist in (('dock', 'dock' if 'dock' in b.nodes else 'base', -40, -20, .45*k), ('tool', None, 30, 35, .40*k),
                                            ('recovery', None, 150, 20, .40*k)):
                nodes = [k['node'] for k in b.kit.get(item, [])]
                nid = nid if nid in b.nodes else (nodes[0] if nodes else None)
                if nid is None:
                    continue
                if item == 'dock' and cid == 'DR-EVA-03':
                    el = 8; az = -70
                t = P[nid][1]; camera(t, dist if not cid.startswith('DR-FIX') else dist*3, az, el, lens=60)
                shoot(out/f'{ident(cid)}_closeup_{item}.png')


if __name__ == '__main__':
    main()
