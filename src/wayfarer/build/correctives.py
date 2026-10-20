"""CHAR-001: corrective shape keys for the linear-blend artefacts the rig review flags (docs/CHARACTERS.md "Validation"): the groin, knees,
elbows, armpits and lower back collapse at extreme joint angles. Each corrective is generated, not sculpted: the body is posed at the
joint's flagged angle with the shared solver, a delta mush (Blender's Corrective Smooth against the bind shape) restores the local shape,
and the difference is carried back through the vertex's skinning matrix into a rest-space shape key, limited to the joint's region and
side. A driver ramps the key from an onset angle to the flagged angle, read from the rig, so every pose and action gets it; the glTF
exporter samples the driven weights into each animation (morph-target weights), so Godot plays them with the clips. PROTOTYPE values.
"""
import math

import bpy
import numpy as np
from mathutils import Vector

import characters as ch
import human_system as hs

# name: (pose of characters.STAND, side-specific region bones (format with s = l/r; None = one key across both sides), shared bones
# (split by side), driver (kind, bones)). Kinds: 'swing' = the bone's swing off its rest direction in its parent (TRANSFORMS, local
# space, swing-twist Y, W); 'diff' = the rotational difference of two bones. The poses are the rig review's flagged postures, one
# joint at a time.
ARMS = lambda flex, abduct, elbow: dict(right=dict(flex=flex, abduct=abduct, elbow=elbow), left=dict(flex=flex, abduct=abduct, elbow=elbow))
SPEC = dict(
    knee=(dict(knee=(120.0, 120.0)), ('thigh_{s}', 'calf_{s}'), (), ('swing', ('calf_{s}',))),
    hip=(dict(hip=(100.0, 100.0)), ('thigh_{s}',), ('pelvis', 'spine_01'), ('swing', ('thigh_{s}',))),
    elbow=(dict(arms=ARMS(0.0, 12.0, 140.0)), ('upperarm_{s}', 'lowerarm_{s}'), (), ('swing', ('lowerarm_{s}',))),
    shoulder=(dict(arms=ARMS(170.0, 10.0, 5.0)), ('clavicle_{s}', 'upperarm_{s}'), ('spine_03',), ('swing', ('upperarm_{s}',))),
)
# No trunk key: the solver turns the pelvis with the trunk, so the review's trunk-forward posture bends the hips (the hip key), not the spine.
ONSET = 0.35            # the key starts at this fraction of the way from rest to the flagged angle and is full at the flagged angle
SMOOTH = dict(factor=0.5, iterations=10)    # the review postures, newcomer: lighter smoothing loses less volume, heavier crushes more edges
SIDE_BLEND_M = 0.03     # shared bones split by side over this half-width across the midline


def swing(pb):
    """The bone's swing off its rest direction in its parent (radians): the driver's TRANSFORMS ROT_W in swing-twist Y, local space."""
    y = pb.matrix_basis.to_quaternion() @ Vector((0.0, 1.0, 0.0))
    return math.acos(max(-1.0, min(1.0, y.y)))


def diff(rig, a, b):
    """Rotational difference of two pose bones (radians), as the ROTATION_DIFF driver variable computes it."""
    q = rig.pose.bones[a].matrix.to_quaternion().inverted() @ rig.pose.bones[b].matrix.to_quaternion()
    return 2.0*math.acos(min(1.0, abs(q.w)))


def reading(rig, kind, bones):
    return swing(rig.pose.bones[bones[0]]) if kind == 'swing' else diff(rig, *bones)


def weights(body, rig):
    """(n, bones) deform weights and the bone order."""
    names = [b.name for b in rig.data.bones]; idx = {g.index: names.index(g.name) for g in body.vertex_groups if g.name in names}
    W = np.zeros((len(body.data.vertices), len(names)))
    for v in body.data.vertices:
        for e in v.groups:
            if e.group in idx:
                W[v.index, idx[e.group]] = e.weight
    return W, names


def skin_matrices(rig, body, names):
    """(bones, 3, 3) linear parts of each bone's skinning matrix in the body's object space."""
    M = body.matrix_world.inverted() @ rig.matrix_world
    return np.array([np.array((M @ rig.pose.bones[n].matrix @ rig.data.bones[n].matrix_local.inverted() @ M.inverted()).to_3x3()) for n in names])


def masks(body, W, names, region, shared):
    """{side: (n,) mask in 0..1}: the side's region bones' weights plus the shared bones' weights split across the midline."""
    x = np.array([v.co.x for v in body.data.vertices]); col = lambda bs: sum((W[:, names.index(b)] for b in bs), np.zeros(len(x)))
    left = np.clip(.5+x/(2*SIDE_BLEND_M), 0.0, 1.0)              # MPFB: the _l side is +x
    if region is None:
        return {'': np.clip(col(shared), 0.0, 1.0)}
    return {s: np.clip(col([b.format(s=s) for b in region])+col(shared)*(left if s == 'l' else 1-left), 0.0, 1.0) for s in 'lr'}


def evaluated(body):
    dg = bpy.context.evaluated_depsgraph_get(); e = body.evaluated_get(dg); m = e.to_mesh()
    co = np.array([tuple(v.co) for v in m.vertices]); e.to_mesh_clear(); return co


def pose(rig, solver, frame):
    basis, _, _ = solver.solve(frame)
    for b, m in basis.items():
        pb = rig.pose.bones[b]; pb.rotation_mode = 'QUATERNION'; pb.rotation_quaternion = m.to_quaternion()
        if b in ('Root', 'pelvis'):
            pb.location = m.translation
    bpy.context.view_layer.update()


def rest_pose(rig):
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'; pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
    bpy.context.view_layer.update()


def frames(H, P):
    """The corrective poses as solver source frames at this body's proportions (feet free, as the rig review's high step)."""
    saved = dict(ch.P); ch.P.update(P)
    try:
        fig = hs.figure(H); l1, l2, la, _ = hs.leg_lengths(H); hip = (0.0, 0.0, l1+l2+la-.005)
        return {k: hs.frame_of(ch.skeleton(fig, dict(ch.STAND, **p), hip, hs.UP, hs.FORWARD), (0.0, 0.0, 0.0), ()) for k, (p, *_) in SPEC.items()}
    finally:
        ch.P.clear(); ch.P.update(saved)


def build(rig, body, solver, H, P, only=None):
    """Add the corrective shape keys and their drivers to `body`. Returns {key: dict(rest/full readings in degrees, vertices moved,
    largest rest-space offset in mm)}."""
    assert not body.data.shape_keys, f'{body.name}: correctives expect a body without shape keys'
    W, names = weights(body, rig); made = []; info = {}
    rest_pose(rig); rest = evaluated(body); readings0 = {}
    for key, (p, region, shared, (kind, bones)) in SPEC.items():
        if only and key not in only:
            continue
        sides = masks(body, W, names, region, shared); union = np.clip(sum(sides.values()), 0.0, 1.0)
        for s in sides:
            readings0[(key, s)] = reading(rig, kind, [b.format(s=s) for b in bones])
        g = body.vertex_groups.new(name=f'WF_CORRECTIVE_{key}')
        for i in np.nonzero(union > 1e-4)[0]:
            g.add([int(i)], float(union[i]), 'REPLACE')
        mod = body.modifiers.new(f'WF_CORRECTIVE_{key}', 'CORRECTIVE_SMOOTH'); mod.rest_source = 'ORCO'; mod.smooth_type = 'LENGTH_WEIGHTED'
        mod.factor = SMOOTH['factor']; mod.iterations = SMOOTH['iterations']; mod.use_pin_boundary = True; mod.vertex_group = g.name
        mod.show_viewport = False
        pose(rig, solver, frames(H, P)[key]); posed = evaluated(body)
        mod.show_viewport = True; target = evaluated(body)
        S = skin_matrices(rig, body, names); A = np.einsum('nb,bij->nij', W, S)
        delta = np.einsum('nij,nj->ni', np.linalg.inv(A), target-posed)
        full = {s: reading(rig, kind, [b.format(s=s) for b in bones]) for s in sides}
        body.modifiers.remove(mod); body.vertex_groups.remove(g); rest_pose(rig)
        for s, m in sides.items():
            made.append((f'corrective_{key}' + (f'_{s}' if s else ''), delta*m[:, None], kind, [b.format(s=s) for b in bones], readings0[(key, s)], full[s]))
    body.shape_key_add(name='Basis', from_mix=False)
    for name, d, kind, bones, r0, r1 in made:
        k = body.shape_key_add(name=name, from_mix=False); co = (rest+d).ravel(); k.data.foreach_set('co', co); k.value = 0.0
        fc = k.driver_add('value'); dr = fc.driver; dr.type = 'SCRIPTED'
        v = dr.variables.new(); v.name = 'a'
        if kind == 'swing':
            v.type = 'TRANSFORMS'; t = v.targets[0]; t.id = rig; t.bone_target = bones[0]; t.transform_type = 'ROT_W'
            t.rotation_mode = 'SWING_TWIST_Y'; t.transform_space = 'LOCAL_SPACE'
        else:
            v.type = 'ROTATION_DIFF'
            for t, b in zip(v.targets, bones):
                t.id = rig; t.bone_target = b
        a0 = r0+ONSET*(r1-r0)
        if r1-a0 < math.radians(5.0):
            raise ValueError(f'{name}: the driver reading barely moves between rest and the corrective pose')
        dr.expression = f'min(max((a-{a0:.5f})/{r1-a0:.5f},0.0),1.0)'
        if not dr.is_simple_expression:
            raise ValueError(f'{name}: driver is not a simple expression')
        moved = np.linalg.norm(d, axis=1)
        info[name] = dict(rest_deg=round(math.degrees(r0), 2), onset_deg=round(math.degrees(a0), 2), full_deg=round(math.degrees(r1), 2),
                          vertices=int((moved > 1e-4).sum()), max_offset_mm=round(float(moved.max())*1000, 1))
    bpy.context.view_layer.update()
    return info
