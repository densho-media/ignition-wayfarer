"""Wayfarer human characters from the shared MPFB system (C1-C3, docs/CHARACTERS.md).

Run through `python3 tools/workflow.py characters` (it sets BLENDER_USER_RESOURCES to the isolated MPFB install), or directly:
  BLENDER_USER_RESOURCES=<cache>/blender/user blender --background --factory-startup --python-exit-code 1 \
      --python src/wayfarer/build/human.py -- [--only test_a test_b ...] [--report references/p1_human_system.json]

For each [human.<id>] recipe of data/characters.toml: the MPFB height macro is bisected to the recipe's stature, the human is generated
with the game_engine rig, baked (helpers removed, targets applied, at most four weights per vertex), given the review materials, checked
against the rig contract (human_system.BONES), animated with the shared action library and saved as
assets/characters/WF_CHAR_HUMAN_<ID>.blend (GEN_ content regenerated, ART_ kept). test_b's actions are retargeted from test_a's rig, the
path an external animation library takes; every other character's come straight from the procedural source at its own stature.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import addon_utils
import bpy
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/components')]
import characters as ch
import human_system as hs
from common import OWNER, begin, save, tag
from spec import load

MPFB = 'bl_ext.user_default.mpfb'


def mpfb():
    mod = addon_utils.enable(MPFB, default_set=True)
    if mod is None:
        raise RuntimeError('MPFB is not installed in BLENDER_USER_RESOURCES; run `python3 tools/workflow.py deps install`')
    from bl_ext.user_default.mpfb import VERSION
    return mod, '.'.join(map(str, VERSION))


# ---------------------------------------------------------------------------------------------------------------------- generation

def clear_scene():
    for o in list(bpy.data.objects):
        if o.get('wf_owner') != OWNER and not any(c.name.startswith('ART_') for c in o.users_collection):
            bpy.data.objects.remove(o, do_unlink=True)


def body_stature(obj):
    dg = bpy.context.evaluated_depsgraph_get(); e = obj.evaluated_get(dg); m = e.to_mesh()
    zs = [(obj.matrix_world @ v.co).z for v in m.vertices]; e.to_mesh_clear()
    return max(zs)-min(zs)


def stature_macro(sys_, q):
    """Bisect MPFB's `height` macro (monotonic in stature) to the recipe's stature. Returns (macro, stature reached)."""
    from bl_ext.user_default.mpfb.services.humanservice import HumanService
    lo, hi = 0.0, 1.0; best = None
    for _ in range(sys_['bisection']['steps']):
        mid = (lo+hi)/2; info = hs.human_info(sys_, q, mid)
        bm = HumanService.create_human(macro_detail_dict=info['phenotype'])
        h = body_stature(bm); bpy.data.objects.remove(bm, do_unlink=True)
        if best is None or abs(h-q['stature_m']) < abs(best[1]-q['stature_m']):
            best = (mid, h)
        lo, hi = (mid, hi) if h < q['stature_m'] else (lo, mid)
    return best


def review_material(name, rgb, roughness=.6, metallic=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1); m['wf_owner'] = OWNER; m['geometry_status'] = 'PROTOTYPE'
    n = next(x for x in m.node_tree.nodes if x.type == 'BSDF_PRINCIPLED')
    n.inputs['Base Color'].default_value = (*rgb, 1); n.inputs['Roughness'].default_value = roughness; n.inputs['Metallic'].default_value = metallic
    return m


def bake(body, rig, sys_):
    """Helpers removed, masks and targets applied, shape keys flattened; weights limited to max_influences and normalized."""
    from bl_ext.user_default.mpfb.services.exportservice import ExportService
    name = body.name
    ExportService.bake_modifiers_remove_helpers(body, bake_masks=True, bake_subdiv=False, remove_helpers=True)
    body = bpy.data.objects[name]
    for o in rig.children:
        if o.type == 'MESH' and o.data.shape_keys:
            bpy.context.view_layer.objects.active = o; o.select_set(True)
            bpy.ops.object.shape_key_remove(all=True, apply_mix=True); o.select_set(False)
        for mod in list(o.modifiers):
            if mod.type != 'ARMATURE':
                bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier=mod.name)
        if o.type == 'MESH':
            limit_weights(o, rig, sys_['max_influences'])
    return body


def limit_weights(o, rig, n):
    """Keep each vertex's n largest deform weights and renormalize them to 1."""
    groups = {g.index: g for g in o.vertex_groups if g.name in rig.data.bones}
    for v in o.data.vertices:
        w = sorted(((e.weight, e.group) for e in v.groups if e.group in groups and e.weight > 0), reverse=True)
        for _, g in w[n:]:
            groups[g].remove([v.index])
        total = sum(x for x, _ in w[:n])
        for x, g in w[:n]:
            groups[g].add([v.index], x/total, 'REPLACE')


def suit_and_skin(body, sys_, q, outfits=None):
    """Clay or MPFB texture skin; with `suit`, every face outside the skin groups wears the review under-suit, or, with `outfit`, the
    zones of [outfit.<name>] (FUT-003: materials painted on the faces, no geometry)."""
    if q['skin'] == 'clay':
        body.data.materials.clear(); body.data.materials.append(review_material('WF_MAT_Human_Clay', sys_['clay_rgb']))
    if q.get('outfit'):
        return dress(body, sys_, outfits[q['outfit']])
    if not q.get('suit'):
        return
    body.data.materials.append(review_material('WF_MAT_Human_UnderSuit', sys_['suit_rgb'])); suit = len(body.data.materials)-1
    idx = {g.index for g in body.vertex_groups if g.name in sys_['skin_groups']}
    skin = [any(e.group in idx and e.weight > .5 for e in v.groups) for v in body.data.vertices]
    for p in body.data.polygons:
        p.material_index = 0 if all(skin[i] for i in p.vertices) else suit


def dress(body, sys_, outfit):
    """FUT-003 S004 outfit: each face outside the skin groups takes the last zone of the outfit it matches (data/characters.toml [outfit.*]);
    a face's bone is its vertices' most common dominant deform bone, positions are the rest pose. Returns {zone: faces}."""
    from collections import Counter
    rig = body.parent; bones = rig.data.bones; names = {g.index: g.name for g in body.vertex_groups}
    idx = {g.index for g in body.vertex_groups if g.name in sys_['skin_groups']}
    skin = [any(e.group in idx and e.weight > .5 for e in v.groups) for v in body.data.vertices]
    dom = [max(((e.weight, names[e.group]) for e in v.groups if names[e.group] in bones), default=(0.0, None))[1] for v in body.data.vertices]
    slots = []
    for z in outfit['zones']:
        if z.get('skin'):
            slots.append(0); continue
        m = review_material(f"WF_MAT_Outfit_{z['name']}", z['color'], z.get('roughness', .6), z.get('metallic', 0.0))
        if m.name not in [x.name for x in body.data.materials]:
            body.data.materials.append(m)
        slots.append([x.name for x in body.data.materials].index(m.name))
    height = lambda ref: bones[ref[0]].head_local.z+ref[1]

    def match(z, b, c, n):
        if 'bones' in z and b not in z['bones']:
            return False
        if 'bone_prefixes' in z and not b.startswith(tuple(z['bone_prefixes'])):
            return False
        if 'z' in z and not height(z['z'][0]) <= c.z <= height(z['z'][1]):
            return False
        if 'abs_x' in z and not z['abs_x'][0] <= abs(c.x) <= z['abs_x'][1]:
            return False
        if 'normal_z_min' in z and n.z < z['normal_z_min']:
            return False
        if 'along' in z or z.get('outer'):
            h, tl = bones[b].head_local, bones[b].tail_local; d = tl-h; f = (c-h).dot(d)/d.length_squared
            if 'along' in z and not z['along'][0] <= f <= z['along'][1]:
                return False
            if z.get('outer') and (c.x-(h.x+f*d.x))*(1 if h.x >= 0 else -1) <= 0:
                return False
        return True
    out = Counter()
    for p in body.data.polygons:
        bare = all(skin[i] for i in p.vertices)
        b = Counter(dom[i] for i in p.vertices).most_common(1)[0][0]; k = None if bare else 0
        for j, z in enumerate(outfit['zones']):
            # A zone paints skin faces only with over_skin (gloves); skin = true paints the clay skin back (bare hands to a clean cuff).
            if j and b is not None and (not bare or z.get('over_skin') or z.get('skin')) and match(z, b, p.center, p.normal):
                k = j
        if k is None or outfit['zones'][k].get('skin'):
            p.material_index = 0; out['skin'] += 1
        else:
            p.material_index = slots[k]; out[outfit['zones'][k]['name']] += 1
    return dict(out)


def generate(sys_, key, q, outfits=None):
    from bl_ext.user_default.mpfb.services.humanservice import HumanService
    t0 = time.time(); macro, reached = stature_macro(sys_, q)
    info = hs.human_info(sys_, dict(q, id=f'CHAR_{key.upper()}'), macro)
    st = HumanService.get_default_deserialization_settings(); st['subdiv_levels'] = sys_['subdiv_levels']
    body = HumanService.deserialize_from_dict(info, st)
    rig = body.parent; body = bake(body, rig, sys_); dressed = suit_and_skin(body, sys_, q, outfits)
    ident = f'CHAR_{key.upper()}'; rig.name = rig.data.name = ident
    for o in rig.children:
        part = o.name.split('.', 1)[-1]; o.name = f'{ident}_{"Body" if part == "body" else part.title().replace("-", "_")}'
    return rig, dict(height_macro=round(macro, 6), bisection_stature_m=round(reached, 4), generate_s=round(time.time()-t0, 2),
                     **({'outfit': dict(name=q['outfit'], faces=dressed)} if q.get('outfit') else {}))


def contract(rig, sys_):
    """The generated skeleton against the runtime contract; raises on any difference."""
    names = [b.name for b in rig.data.bones]
    assert set(names) == set(hs.BONES) and len(names) == len(hs.BONES), f'rig differs from the contract: {sorted(set(names) ^ set(hs.BONES))}'
    roots = [b.name for b in rig.data.bones if b.parent is None]
    assert roots == [sys_['root_bone']], roots
    meshes = [o for o in rig.children if o.type == 'MESH']; worst = 0; unweighted = 0
    for o in meshes:
        deform = {g.index for g in o.vertex_groups if g.name in rig.data.bones}
        for v in o.data.vertices:
            w = [e for e in v.groups if e.group in deform and e.weight > 0]
            worst = max(worst, len(w)); unweighted += not w
    assert worst <= sys_['max_influences'] and unweighted == 0, (worst, unweighted)
    return dict(bones=len(names), root=roots[0], max_influences=worst, unweighted_vertices=unweighted)


# --------------------------------------------------------------------------------------------------------------- retarget solver

def V(t): return Vector(t)


def frame_matrix(x, z):
    x = V(x).normalized(); z = (V(z)-x*x.dot(V(z))).normalized(); return Matrix((x, z.cross(x), z)).transposed()


def source_frames(f):
    """Pelvis, chest and head frames of a source frame (columns: right, forward-ish, up)."""
    pel = frame_matrix(hs.sub(f['hip_right'], f['hip_left']), hs.sub(f['waist'], f['hip_c']))
    chest = frame_matrix(hs.sub(f['shoulder_right'], f['shoulder_left']), hs.sub(f['neck'], f['chest']))
    up = V(f['head_up']).normalized(); fw = (V(f['face'])-up*up.dot(V(f['face']))).normalized()
    head = Matrix((fw.cross(up), fw, up)).transposed()
    return pel, chest, head


def hinge_angle(a, b, c, axis):
    """Signed angle at b from (b-a) to (c-b) about axis."""
    u, w = (V(b)-V(a)).normalized(), (V(c)-V(b)).normalized()
    return math.atan2(u.cross(w).dot(axis), u.dot(w))


def swing(m, d):
    """m with its rotation swung so its Y axis points along d (translation kept)."""
    y = m.col[1].xyz.normalized(); q = y.rotation_difference(V(d).normalized())
    r = (q.to_matrix() @ m.to_3x3()).to_4x4(); r.translation = m.translation; return r


class Solver:
    """Poses a game_engine rig from source frames (human_system docstring). All matrices are armature space, rig at the origin."""

    def __init__(self, rig, src_rest):
        self.rig = rig; self.R = {b.name: b.matrix_local.copy() for b in rig.data.bones}
        self.parent = {b.name: b.parent.name if b.parent else None for b in rig.data.bones}
        self.order = [b.name for b in rig.data.bones]          # parents precede children
        self.length = {b.name: b.length for b in rig.data.bones}
        R = self.R
        self.hip_rest = (R['thigh_l'].translation+R['thigh_r'].translation)/2
        self.pelvis_offset = R['pelvis'].translation-self.hip_rest
        self.rest_frames = source_frames(src_rest)
        self.src_rest = src_rest

    def solve(self, f, k=1.0, za=0.0, zb=0.0):
        """Pose for one source frame. A source body of another size maps by m(p) = (k x, k y, zb + k (z - za)): k is the leg-length
        ratio (thigh + shank), za and zb the source's and the target's ankle heights, so a straight source leg is a straight target leg
        and planted feet stay planted. The Root keeps the floor (z scaled only)."""
        R, P, basis = self.R, {}, {}
        pel, chest, head = source_frames(f)
        D = [a @ b.transposed() for a, b in zip((pel, chest, head), self.rest_frames)]
        qp, qc, qh = (d.to_quaternion() for d in D)
        rot = dict(pelvis=qp, spine_01=qp.slerp(qc, .33), spine_02=qp.slerp(qc, .67), spine_03=qc, neck_01=qc.slerp(qh, .5), head=qh)
        P_ = lambda key: Vector((f[key][0]*k, f[key][1]*k, f[key][2]*k if key == 'root' else zb+k*(f[key][2]-za)))
        ik = {}; fwd = pel.col[1].xyz                              # elbows bend back, knees forward when a limb is straight
        for side, s in (('right', 'r'), ('left', 'l')):
            ik[f'arm_{s}'] = (P_(f'wrist_{side}'), V(f[f'elbow_{side}'])-(V(f[f'shoulder_{side}'])+V(f[f'wrist_{side}']))/2, -fwd)
            ik[f'leg_{s}'] = (P_(f'ankle_{side}'), V(f[f'knee_{side}'])-(V(f[f'hip_{side}'])+V(f[f'ankle_{side}']))/2, fwd)
        reach = {}; mids = {}
        for b in self.order:
            p = self.parent[b]
            unposed = R[b].copy() if p is None else P[p] @ (R[p].inverted() @ R[b])
            if b == 'Root':
                want = Matrix.Translation(P_('root')) @ R[b].to_3x3().to_4x4()
            elif b in rot:
                r = (rot[b].to_matrix() @ R[b].to_3x3()).to_4x4()
                r.translation = (P_('hip_c')+rot['pelvis'].to_matrix() @ self.pelvis_offset) if b == 'pelvis' else unposed.translation
                want = r
            elif b.split('_')[0] in ('upperarm', 'thigh'):
                s = b[-1]; chain = 'arm' if b.startswith('upperarm') else 'leg'; lower = ('lowerarm_' if chain == 'arm' else 'calf_')+s
                target, pole, fallback = ik[f'{chain}_{s}']; a = unposed.translation
                l1, l2 = self.length[b], self.length[lower]
                mid, end = ch.ik(tuple(a), tuple(target), l1, l2, tuple(pole if pole.length > 1e-3 else fallback))
                reach[f'{chain}_{s}'] = max(0.0, (target-a).length-(l1+l2)*.999)
                mids[lower] = V(end); want = swing(unposed, V(mid)-a)
            elif b.split('_')[0] in ('lowerarm', 'calf'):
                want = swing(unposed, mids[b]-unposed.translation)
            elif b.startswith('foot_'):
                side = 'right' if b.endswith('_r') else 'left'; calf = P['calf_'+b[-1]]
                # Ankle flexion: the source's change from its rest angle, about the body's right axis, added to MPFB's rest angle.
                right = lambda g: V(hs.sub(g['hip_right'], g['hip_left'])).normalized()
                axis_t = (rot['pelvis'].to_matrix() @ Vector((-1, 0, 0))).normalized()          # MPFB faces -Y: its right is -X
                ks = lambda g: (g[f'knee_{side}'], g[f'ankle_{side}'], g[f'toe_{side}'])
                delta = hinge_angle(*ks(f), right(f))-hinge_angle(*ks(self.src_rest), right(self.src_rest))
                y = unposed.col[1].xyz; cdir = calf.col[1].xyz.normalized()
                rest_ang = hinge_angle(tuple(calf.translation), tuple(unposed.translation), tuple(unposed.translation+y), axis_t)
                want = swing(unposed, Quaternion(axis_t, rest_ang+delta) @ cdir)
            else:
                want = unposed
            basis[b] = unposed.inverted() @ want; P[b] = want
        return basis, P, reach


def local_frame(frame, up, fwd):
    """A vehicle-frame source frame in a body frame: R places the armature (MPFB faces -Y, +Z up) at the frame's root with the body's
    up and facing; the returned frame is expressed in R, Root at the origin."""
    z = Vector(up).normalized(); y = -Vector(fwd).normalized(); x = y.cross(z)
    R = Matrix((x, y, z)).transposed().to_4x4(); R.translation = Vector(frame['root']); inv = R.inverted()
    loc = {k: (tuple(inv @ Vector(v)) if k not in ('head_up', 'face', 'contacts') and isinstance(v, tuple) and len(v) == 3 else v) for k, v in frame.items()}
    for k in ('head_up', 'face'):
        loc[k] = tuple(inv.to_3x3() @ Vector(frame[k]))
    loc['root'] = (0.0, 0.0, 0.0)
    return R, loc


def staged_frame(q, M, H):
    """A characters.skeleton() staging entry `q` (pose, root, up, forward, hands, feet) in frame M as a source frame in the vehicle frame,
    with the body axes and the hand targets. Call with characters.P set to the body's proportions."""
    j = ch.skeleton(hs.figure(H), q['pose'], q['root'], q['up'], q['forward'], q['hands'], q['feet'])
    w = {k: (tuple(M @ Vector(v)) if k not in ('head_up', 'face') else tuple(M.to_3x3() @ Vector(v))) for k, v in j.items() if k != 'axes'}
    up = (M.to_3x3() @ Vector(q['up'])).normalized(); fwd = (M.to_3x3() @ Vector(q['forward'])).normalized()
    sole = tuple(Vector(w['hip_c'])-up*1.0) if q['feet'] is None else tuple(M @ Vector(q['feet']))
    hands = {k: tuple(M @ Vector(v[0])) for k, v in (q['hands'] or {}).items()}
    eye = Vector(w['head'])+fwd*.09
    pose = 'SIT' if q['pose'] is ch.SIT else 'STAND' if q['pose'] is ch.STAND else 'FLOAT'
    return hs.frame_of(w, sole, ()), dict(up=tuple(up), forward=tuple(fwd), hands=hands, feet={}, eye=tuple(eye), look=tuple(fwd), pose=pose)


def greeting_frame(s, who, H, offset=(0.0, 0.0, 0.0)):
    """The S004A greeting in the entry chamber (characters.greeting, vehicle frame, rings stopped): `who` is instructor or newcomer; `offset`
    re-stages the newcomer for its own body (recipe greeting_offset_m)."""
    import human_entry as he
    fr, info = staged_frame(ch.greeting(s, he.ports(s)[0], tuple(offset))[who], Matrix.Identity(4), H)
    return fr, dict(info, scene='S004A', function='ENTRY_CHAMBER')


def posed_back_depth(rig, solver, s, H):
    """CHAR-001: the back depth of the body as posed on the couch, not at rest: stage it with the joint plane on the mattress (back 0),
    pose it and return how deep the evaluated body mesh reaches below the mattress plane (sector +Y). The staging shifts root and soles
    together, so lifting by this depth puts the lowest point of the posed back on the mattress."""
    import figures
    q = ch.couch(s, 0.0); M = figures.sector_matrix(s, q['function']); fr, info = staged_frame(q, M, H)
    R, loc = local_frame(fr, info['up'], info['forward'])
    saved = rig.matrix_world.copy(), {pb.name: (pb.rotation_mode, pb.rotation_quaternion.copy(), pb.location.copy()) for pb in rig.pose.bones}
    rig.matrix_world = R; basis, _, _ = solver.solve(loc)
    for b, m in basis.items():
        pb = rig.pose.bones[b]; pb.rotation_mode = 'QUATERNION'; pb.rotation_quaternion = m.to_quaternion()
        if b in ('Root', 'pelvis'):
            pb.location = m.translation
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get(); depth = -math.inf     # every mesh: the body and what it wears
    for o in rig.children:
        if o.type == 'MESH' and not o.hide_render:
            ev = o.evaluated_get(dg); inv = M.inverted() @ ev.matrix_world
            depth = max(depth, max((inv @ v.co).y for v in ev.data.vertices)-q['root'][1])
    rig.matrix_world = saved[0]                                 # leave the rig as found (the bake and the export expect it at rest)
    for name, (mode, rot, loc_) in saved[1].items():
        pb = rig.pose.bones[name]; pb.rotation_mode = mode; pb.rotation_quaternion = rot; pb.location = loc_
    bpy.context.view_layer.update()
    return depth


def couch_frame(s, H, back=0.11):
    """The newcomer on the treatment couch at the S004B burn-readiness stop (characters.couch, sector frame at the docked pose); `back`
    is the body's back depth (posed_back_depth)."""
    import figures
    q = ch.couch(s, back)
    fr, info = staged_frame(q, figures.sector_matrix(s, q['function']), H)
    return fr, dict(info, scene=q['scene'], function=q['function'])


def bake_action(rig, solver, frames, name, meta, k=(1.0, 0.0, 0.0)):
    """Solve every frame, key location (Root, pelvis) and rotation (all bones), store the source contacts on the action."""
    act = bpy.data.actions.get(name)
    if act is not None:
        bpy.data.actions.remove(act)
    act = bpy.data.actions.new(name); act['wf_owner'] = OWNER; act.use_fake_user = True
    rig.animation_data_create(); rig.animation_data.action = act
    prev = {}; points = []; reach = {}
    for i, f in enumerate(frames):
        basis, P, short = solver.solve(f, *k)
        for c, v in short.items():                              # only a held limb has to reach: arm_r <- hand_right, leg_l <- foot_left
            limb = ('hand_' if c.startswith('arm') else 'foot_')+('right' if c.endswith('_r') else 'left')
            if limb in f['contacts']:
                reach[c] = max(reach.get(c, 0.0), v)
        for b, m in basis.items():
            pb = rig.pose.bones[b]; pb.rotation_mode = 'QUATERNION'
            q = m.to_quaternion()
            if b in prev and prev[b].dot(q) < 0:
                q.negate()
            prev[b] = q; pb.rotation_quaternion = q; pb.keyframe_insert('rotation_quaternion', frame=i, group=b)
            if b in ('Root', 'pelvis'):
                pb.location = m.translation; pb.keyframe_insert('location', frame=i, group=b)
        points.append({f'foot_{s}': tuple(P[f'foot_{x}'].translation) for s, x in (('right', 'r'), ('left', 'l'))}
                      | {f'hand_{s}': tuple(P[f'hand_{x}'].translation) for s, x in (('right', 'r'), ('left', 'l'))}
                      | {f'knee_{s}': tuple(P[f'calf_{x}'].translation) for s, x in (('right', 'r'), ('left', 'l'))})
    act['contacts'] = json.dumps([list(f['contacts']) for f in frames]); act['loop'] = meta['loop']; act['root_motion'] = meta['root_motion']
    act['geometry_status'] = 'PROTOTYPE'
    slip = hs.contact_slip(points, [f['contacts'] for f in frames])
    return act, dict(frames=len(frames), loop=meta['loop'], root_motion=meta['root_motion'],
                     slip_mm={k2: round(v*1000, 1) for k2, v in slip.items()}, reach_short_mm={k2: round(v*1000, 1) for k2, v in reach.items() if v > 1e-4})


def body_measures(rig):
    b = rig.data.bones
    return dict(leg=b['thigh_l'].length+b['calf_l'].length, ankle=b['foot_l'].head_local.z, hip=b['thigh_l'].head_local.z)


def rig_source(rig, act):
    """Read a posed game_engine rig as source frames (human_system.RIG_JOINTS), one per key frame of `act`."""
    rig.animation_data.action = act; lo, hi = (int(x) for x in act.frame_range); contacts = json.loads(act['contacts'])
    rest_head = rig.data.bones['head'].matrix_local.to_3x3(); out = []
    def joints():
        g = {}
        for key, spec in hs.RIG_JOINTS.items():
            b, end = spec.split('.'); pb = rig.pose.bones[b]
            g[key] = tuple(rig.matrix_world @ (pb.head if end == 'head' else pb.tail))
        hb = rig.pose.bones['head']; g['head_up'] = tuple(hb.matrix.col[1].xyz.normalized())
        g['face'] = tuple((hb.matrix.to_3x3() @ rest_head.inverted()) @ Vector(hs.FORWARD))
        g['root'] = tuple(rig.pose.bones['Root'].head)
        return g
    for i in range(lo, hi+1):
        bpy.context.scene.frame_set(i); g = joints(); g['contacts'] = tuple(contacts[i-lo]); out.append(g)
    rig.animation_data.action = None; bpy.context.scene.frame_set(0)
    saved = rig.data.pose_position; rig.data.pose_position = 'REST'; bpy.context.view_layer.update()
    rest = joints(); rest['contacts'] = (); rig.data.pose_position = saved; bpy.context.view_layer.update()
    return out, rest


def solver_check(rig, act, P_last):
    """The solver's own matrices against Blender's evaluated pose at the action's last frame (catches a wrong basis convention)."""
    rig.animation_data.action = act; bpy.context.scene.frame_set(int(act.frame_range[1]))
    dev = max((rig.pose.bones[b].matrix.translation-m.translation).length for b, m in P_last.items())
    rig.animation_data.action = None; bpy.context.scene.frame_set(0); return dev


def fingerprint(rig):
    """SHA-256 of the generated content: vertex positions (0.1 mm), deform weights (1e-4), corrective offsets and drivers, bone rest heads
    and every action key."""
    h = hashlib.sha256()
    for o in sorted(rig.children, key=lambda o: o.name):
        if o.type != 'MESH':
            continue
        h.update(o.name.encode())
        names = {g.index: g.name for g in o.vertex_groups}
        for v in o.data.vertices:
            h.update(('%.4f %.4f %.4f' % tuple(v.co)).encode())
            for e in sorted(v.groups, key=lambda e: names[e.group]):
                if names[e.group] in rig.data.bones and e.weight > 0:
                    h.update(f'{names[e.group]}{e.weight:.4f}'.encode())
        for k in (o.data.shape_keys.key_blocks[1:] if o.data.shape_keys else []):    # correctives: offsets (0.1 mm) and driver
            fc = o.data.shape_keys.animation_data.drivers.find(f'key_blocks["{k.name}"].value')
            h.update((k.name+(fc.driver.expression if fc else '')).encode())
            for a, b in zip(k.data, o.data.vertices):
                h.update(('%.4f %.4f %.4f' % tuple(a.co-b.co)).encode())
    for b in rig.data.bones:
        h.update(('%s %.4f %.4f %.4f' % (b.name, *b.head_local)).encode())
    for act in sorted((a for a in bpy.data.actions if a.get('wf_owner') == OWNER), key=lambda a: a.name):
        for fc in sorted(act_curves(act), key=lambda fc: (fc.data_path, fc.array_index)):
            h.update(fc.data_path.encode())
            for kp in fc.keyframe_points:
                h.update(('%.5f' % kp.co[1]).encode())
    return h.hexdigest()


def act_curves(act):
    """F-curves of a (slotted) action."""
    if hasattr(act, 'fcurves'):
        return list(act.fcurves)
    return [fc for layer in act.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]


# ------------------------------------------------------------------------------------------------------------------------- main

def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--only', nargs='*'); ap.add_argument('--root', type=Path, default=ROOT)
    ap.add_argument('--report', type=Path, default=None); ap.add_argument('--no-save', action='store_true')
    args = ap.parse_args(argv); root = args.root
    data = hs.load(root); sys_ = data['human_system']; s, _, spec_text, source_text = load(root)
    _, version = mpfb(); assert version == sys_['mpfb'], f'installed MPFB {version}, contract {sys_["mpfb"]}'
    seat, pitch = s['sector_whitebox']['seat_height_m'], s['human_entry']['spoke_rung_pitch_m']
    keys = args.only or list(data['human']); report = dict(mpfb=version, rig=sys_['rig'], fps=sys_['fps'], characters={})
    if 'test_b' in keys and 'test_a' not in keys:
        keys = ['test_a']+keys                                   # test_b's actions are retargeted from test_a's rig
    keys = sorted(keys, key=lambda k: k != 'test_a')
    built = {}
    for key in keys:
        q = data['human'][key]; ident = f'WF_CHAR_HUMAN_{key.upper()}'; path = root/'assets/characters'/f'{ident}.blend'
        coll, gen = begin(path, ident); bpy.context.scene.render.fps = sys_['fps']; clear_scene()
        for a in list(bpy.data.actions):
            if a.get('wf_owner') == OWNER:
                bpy.data.actions.remove(a)
        rig, info = generate(sys_, key, q, data.get('outfit', {}))
        for o in [rig, *rig.children]:
            for c in list(o.users_collection):
                c.objects.unlink(o)
            gen.objects.link(o); tag(o, o.name, 'character', source='prototype')
            o['layer'] = 'CHARACTER'; o['character'] = key; o['character_kind'] = q['kind']; o['mpfb_version'] = version
            if q['kind'] == 'induction':
                o['identity_ref'] = q['identity_ref']; o['identity_status'] = 'PROTOTYPE body; open: ' + ', '.join(q['unknown'])
        bpy.context.scene.frame_start = 0                       # actions start at frame 0: Blender frame f is glTF time f/fps
        info['stature_m'] = round(body_stature(next(o for o in rig.children if o.name.endswith('_Body'))), 4)
        assert abs(info['stature_m']-q['stature_m']) <= sys_['stature_tolerance_m'], f"{key}: stature {info['stature_m']} m, recipe {q['stature_m']} m"
        info['contract'] = contract(rig, sys_)
        info['hip_height_m'] = round(rig.data.bones['thigh_l'].head_local.z, 4)
        info['vertices'] = {o.name: len(o.data.vertices) for o in rig.children if o.type == 'MESH'}
        info['materials'] = sorted({m.name for o in rig.children if o.type == 'MESH' for m in o.data.materials if m})
        H = info['stature_m']; acts = {}
        # CHAR-001: corrective shape keys from this body's own procedural rest, before any staging measures the posed body.
        import correctives
        Pc = hs.proportions({b.name: (tuple(b.head_local), tuple(b.tail_local)) for b in rig.data.bones}, H)
        info['correctives'] = correctives.build(rig, next(o for o in rig.children if o.name.endswith('_Body')),
                                                Solver(rig, hs.actions(H, data['actions'], sys_['fps'], seat, pitch, Pc)['rest']), H, Pc)
        if key == 'test_b':
            src = built['test_a']; mine = body_measures(rig); solver = None
            k = (mine['leg']/src['body']['leg'], src['body']['ankle'], mine['ankle'])
            for name in hs.ACTIONS:
                frames, rest, meta = src['sources'][name]; solver = solver or Solver(rig, rest)
                act, r = bake_action(rig, solver, frames, name, meta, k); acts[name] = act; info.setdefault('actions', {})[name] = r
            info['retarget'] = dict(source='CHAR_TEST_A rig (game_engine), read as joints', leg_ratio=round(k[0], 4), ankle_from_to_m=[round(k[1], 4), round(k[2], 4)])
        else:
            P = hs.proportions({b.name: (tuple(b.head_local), tuple(b.tail_local)) for b in rig.data.bones}, H)
            lib = hs.actions(H, data['actions'], sys_['fps'], seat, pitch, P); solver = Solver(rig, lib['rest'])
            info['proportions'] = {k2: round(v, 4) for k2, v in P.items()}
            for name in hs.ACTIONS:
                act, r = bake_action(rig, solver, lib[name]['frames'], name, lib[name]); acts[name] = act
                info.setdefault('actions', {})[name] = r
            info['retarget'] = dict(source='human_system procedural library at this stature', scale=1.0)
            _, P, _ = solver.solve(lib['climb']['frames'][-1]); info['solver_vs_blender_m'] = round(solver_check(rig, acts['climb'], P), 6)
            if q['kind'] == 'induction':                         # the S004A greeting, as a held pose clip and a vehicle-frame placement
                saved = dict(ch.P); ch.P.update(P)
                try:
                    staging = [(greeting_frame(s, q['proxy'], H, q.get('greeting_offset_m', (0.0, 0.0, 0.0))),
                                'characters.greeting (IND-001 PROTOTYPE staging, re-staged for this body: recipe greeting_offset_m), vehicle frame at the docked pose')]
                    if q['proxy'] == 'newcomer':                 # CHAR-001: the S004B couch too, lying at this body's own back depth
                        bd = posed_back_depth(rig, solver, s, H); info['back_depth_m'] = round(bd, 4)
                        staging.append((couch_frame(s, H, bd), 'characters.couch at the posed body\'s back depth (CHAR-001), sector frame posed at the docked pose'))
                finally:
                    ch.P.clear(); ch.P.update(saved)
                stages = {}
                for (fr, st), source in staging:
                    R, loc = local_frame(fr, st['up'], st['forward']); name = f"stage_{st['scene']}"
                    act, r = bake_action(rig, solver, [loc]*10, name, dict(loop=True, root_motion=False)); acts[name] = act
                    info['actions'][name] = r
                    stages[st['scene']] = dict(scene=st['scene'], function=st['function'], action=name, proxy=q['proxy'] if st['scene'] == 'S004A' else f"S004B_{q['proxy']}",
                                               matrix=[list(row) for row in R], source=source)
                rig['stage'] = json.dumps(stages['S004A']); rig['stages'] = json.dumps(stages)
                info['stage'] = stages['S004A']; info['stages'] = sorted(stages)
        rig.animation_data.action = acts['idle']
        for name, act in acts.items():                         # one NLA track per action: the glTF exporter writes each as an animation
            tr = rig.animation_data.nla_tracks.new(); tr.name = name; tr.strips.new(name, 0, act); tr.mute = True
        rig.animation_data.action = None
        info['fingerprint'] = fingerprint(rig)
        if key == 'test_a':                                     # test_b retargets from this rig; its file is closed by the next begin()
            built[key] = dict(body=body_measures(rig), sources={n: (*rig_source(rig, a), dict(loop=bool(a['loop']), root_motion=bool(a['root_motion'])))
                                                                 for n, a in acts.items()})
        for name, text in (('WF_CHARACTERS_SNAPSHOT', (root/'data/characters.toml').read_text()),
                           ('WF_EXTERNAL_MANIFEST_SNAPSHOT', (root/'assets/external/manifest.toml').read_text())):
            t = bpy.data.texts.get(name) or bpy.data.texts.new(name); t.clear(); t.write(text)
        if not args.no_save:
            save(path, coll, spec_text, source_text)
        report['characters'][key] = info
        print(f'WF_HUMAN {key} {json.dumps(info)}', flush=True)
    if args.report:
        args.report.write_text(json.dumps(report, indent=1)+'\n')


if __name__ == '__main__':
    main()
