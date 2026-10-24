"""Contact-aware glove grasp on a cylindrical handle (ASSET-07, docs/ACCESSORIES.md): a display pose for review scenes, never a grip-force,
reach or glove-mobility claim (glove torque and grip strength OPEN).

grasp(rig, 'r', a, b, radius) takes the rig's current evaluated pose, freezes it (the action is unassigned so the pose stays), turns the
hand about the wrist so the knuckle line lies along the handle axis and the palm faces it, returns the shift that puts the palm on the
handle, and closes each finger joint by joint (proximal first) until the segment reaches the handle surface or its joint limit; the thumb
closes the same way from the opposite side. The rig's bones and actions are unchanged: only the pose bones of one hand move.
"""
import math

import bpy
from mathutils import Matrix, Vector

FINGERS = ('index', 'middle', 'ring', 'pinky')
LIMIT = (90.0, 100.0, 80.0)          # display joint limits (deg) of a pressurised glove, PROTOTYPE
FINGER_R = .019                      # finger bone line to glove surface (skin and the 0.011 m glove offset)
PALM_R = .030                        # palm bone plane to glove surface


def freeze(rig):
    ad = rig.animation_data
    if ad:
        ad.action = None
        for tr in ad.nla_tracks:
            tr.mute = True


def world(rig, name, end='tail'):
    pb = rig.pose.bones[name]; return rig.matrix_world @ (pb.tail if end == 'tail' else pb.head)


def to_axis(p, a, b):
    """Distance of p from the segment a-b."""
    d = b-a; t = max(0.0, min(1.0, (p-a).dot(d)/d.dot(d))); return (p-(a+d*t)).length


def flex(rig, name, deg, axis='X'):
    pb = rig.pose.bones[name]; pb.rotation_mode = 'QUATERNION'
    pb.rotation_quaternion = Matrix.Rotation(math.radians(deg), 4, axis).to_quaternion(); bpy.context.view_layer.update()


def rotate_world(rig, name, R, pivot):
    """Rotate a pose bone (and its children) by the world rotation R about the world point pivot."""
    pb = rig.pose.bones[name]; M = rig.matrix_world
    W = Matrix.Translation(pivot) @ R.to_4x4() @ Matrix.Translation(-pivot) @ M @ pb.matrix
    pb.matrix = M.inverted() @ W; bpy.context.view_layer.update()


def frame(rig, s):
    """Hand frame: wrist, palm centre, knuckle line (index to pinky) and palm normal (the side the fingers close to)."""
    wrist = world(rig, f'hand_{s}', 'head')
    k = [world(rig, f'{f}_01_{s}', 'head') for f in FINGERS]; knuckles = sum(k, Vector())/4
    across = (k[3]-k[0]).normalized(); palm = wrist.lerp(knuckles, .65)
    t0 = world(rig, f'middle_01_{s}'); pb = rig.pose.bones[f'middle_01_{s}']; q = pb.rotation_quaternion.copy()
    flex(rig, f'middle_01_{s}', 30); n = world(rig, f'middle_01_{s}')-t0; pb.rotation_quaternion = q; bpy.context.view_layer.update()
    n = (n-across*n.dot(across)).normalized()
    return wrist, palm, across, n


def close(rig, chain, a, b, r, sign=1.0):
    """Close a three-bone chain joint by joint until a later segment end touches the handle surface (or the joint limit)."""
    for k, name in enumerate(chain):
        ang = 0.0
        while ang < LIMIT[k]:
            if min(to_axis(world(rig, c), a, b) for c in chain[k:]) <= r+FINGER_R:
                break
            ang += 3.0; flex(rig, name, sign*ang)
    return [round(to_axis(world(rig, c), a, b)-r, 4) for c in chain]


def ik(rig, s, target):
    """Two-bone IK of the arm to put the wrist at target (world), baked into the pose (the constraint is removed again)."""
    e = bpy.data.objects.new('WF_IK_TARGET', None); bpy.context.scene.collection.objects.link(e); e.location = target
    up, lo = f'upperarm_{s}', f'lowerarm_{s}'; c = rig.pose.bones[lo].constraints.new('IK'); c.target = e; c.chain_count = 2
    bpy.context.view_layer.update(); mats = {n: rig.pose.bones[n].matrix.copy() for n in (up, lo)}
    rig.pose.bones[lo].constraints.remove(c); bpy.data.objects.remove(e)
    for n in (up, lo):
        rig.pose.bones[n].matrix = mats[n]; bpy.context.view_layer.update()


def orient(rig, s, a, b, r):
    """Turn the hand about the wrist so the knuckle line runs along the handle and the palm faces it; returns the palm-contact shift."""
    ax = (b-a).normalized(); wrist, palm, across, n = frame(rig, s)
    if across.dot(ax) < 0:
        ax = -ax
    rotate_world(rig, f'hand_{s}', across.rotation_difference(ax).to_matrix(), wrist)
    wrist, palm, across, n = frame(rig, s)
    c = a+(b-a)*.5; want = c-palm; want = (want-ax*want.dot(ax)).normalized()      # the palm should face the handle
    rotate_world(rig, f'hand_{s}', n.rotation_difference(want).to_matrix(), wrist)
    wrist, palm, across, n = frame(rig, s)
    foot = a+ax*(c-a).dot(ax); return (foot-n*(r+PALM_R))-palm                    # palm centre over the handle middle


def grasp(rig, s, a, b, r, reach=False):
    """Pose one hand closed on the handle a-b of radius r (world). reach: move the wrist there by arm IK (the body stays); otherwise
    shift the whole rig. Returns (residual shift, report)."""
    freeze(rig); a, b = Vector(a), Vector(b); bpy.context.view_layer.update()
    for f in FINGERS:
        for j in (1, 2, 3):
            flex(rig, f'{f}_{j:02d}_{s}', 0.0)
    for j in (1, 2, 3):
        flex(rig, f'thumb_{j:02d}_{s}', 0.0)
    if reach:
        for _ in range(6):
            shift = orient(rig, s, a, b, r)
            if shift.length < .003:
                break
            ik(rig, s, world(rig, f'hand_{s}', 'head')+shift)
    shift = orient(rig, s, a, b, r)
    if not reach:
        rig.location += shift; bpy.context.view_layer.update()
    gaps = {f: close(rig, [f'{f}_{j:02d}_{s}' for j in (1, 2, 3)], a, b, r) for f in FINGERS}
    th = [f'thumb_{j:02d}_{s}' for j in (1, 2, 3)]; d0 = to_axis(world(rig, th[-1]), a, b)
    flex(rig, th[1], 15); sign = 1.0 if to_axis(world(rig, th[-1]), a, b) < d0 else -1.0; flex(rig, th[1], 0)
    gaps['thumb'] = close(rig, th, a, b, r, sign)
    return shift, dict(handle_radius_m=r, residual_m=round(shift.length, 4) if reach else 0.0, finger_gap_m=gaps,
                       status='DISPLAY POSE (grip force, glove torque OPEN)')
