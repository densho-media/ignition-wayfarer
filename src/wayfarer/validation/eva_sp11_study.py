"""EVA-003 SP-11 comparison in the saved vehicle (S&E 43 EVA-056..058, 44 EVA3-001..004; docs/EVA.md "EVA-003").

  blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/validation/eva_sp11_study.py -- \
      [--sp11 references/p1_eva_sp11.json] [--out runs/<stamp>-eva3] [--renders runs/renders/p1/eva/eva3] [--no-renders]

For the 1.10 / 1.20 / 1.35 m two-person chambers of eva_sp11.py: builds the chamber, both leaves and the inner-hatch mechanism envelopes
(the parallel plug's parking pocket in each slide direction, the floor recess well) as disposable STUDY_* objects in the vehicle opened in
memory (never saved), measures them against the vehicle meshes and the SP-12 fixtures, then poses the real suit rigs: the operator in the
extension-latch work and the opening-strap pull, the partner beside it, the rescuer with the casualty on the litter frame, and measures
the rigs' own suit meshes (not hulls) against the chamber wall, the outer leaf's swing and each other. Renders the comparison.
Writes references/p1_eva_sp11_vehicle.json. Nothing becomes ship geometry (EVA-061).
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/validation')]
import spec
import eva_suit as es
import eva_airlock_study as st
import eva_fit
import eva_sp11_plug as pl

COLORS = dict(pocket=(.20, .70, .35, 1), recess=(.80, .25, .20, 1), frame=(.92, .92, .30, 1), lever=(.95, .20, .20, 1), valve=(.15, .45, .95, 1),
              gauge=(.92, .92, .92, 1), release=(.95, .20, .20, 1), path=(.20, .85, .95, 1), seat=(.30, .90, .40, 1), strap=(.95, .45, .05, 1))


def mat(key):
    if key in st.COLORS:
        return st.material(key)
    m = bpy.data.materials.get(f'STUDY_{key}') or bpy.data.materials.new(f'STUDY_{key}'); m.use_nodes = True
    m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = COLORS[key]; return m


def obj(name, bm, coll, key, props=None):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(mat(key))
    o = bpy.data.objects.new(name, me); coll.objects.link(o)
    for k, v in (props or {}).items():
        o[k] = v
    o['wf_owner'] = 'eva.study'; o['geometry_status'] = 'STUDY ONLY: not ship geometry (EVA-061)'; return o


def hull_bm(points):
    bm = bmesh.new()
    for p in points:
        bm.verts.new(p)
    res = bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=False)
    drop = {v for g in (res['geom_interior'], res['geom_unused']) for v in g if isinstance(v, bmesh.types.BMVert) and v.is_valid}
    bmesh.ops.delete(bm, geom=list(drop), context='VERTS'); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); return bm


def mechanism_objs(row, coll):
    """The parallel plug's leaf parked in each slide direction (leaf + carriage box) and the floor recess well."""
    fit = row['fitting']; out = []
    for d, p in row['mechanisms']['parallel_plug_slide']['parking'].items():
        out.append(obj(f"{row['id']}_Pocket_{d}", hull_bm([st.world(fit, *c) for c in p['corners_chamber']]), coll, 'pocket',
                       dict(study_part=f'pocket{d}', direction=d)))
    m = row['mechanisms']['hinged_floor_recess']; ch = row['chamber']; dr = row['door']
    if m['recess_depth_m'] > 0:
        a0 = m['floor_r_m']; a1 = row['mechanisms']['hinged_into_sp12']['floor_r_m']; w, l = m['recess_plan_m']
        pts = [st.world(fit, a, p, q) for a in (a0, a1) for p in (-w/2, w/2) for q in (-l/2, l/2)]
        out.append(obj(f"{row['id']}_Recess", hull_bm(pts), coll, 'recess', dict(study_part='recess')))
    return out


def rod_points(p0, p1, r):
    """16 points of a square-section rod (half-width r) from p0 to p1 (world)."""
    p0, p1 = Vector(p0), Vector(p1); d = (p1-p0).normalized(); a = d.orthogonal().normalized(); b = d.cross(a)
    return [e+a*sa*r+b*sb*r for e in (p0, p1) for sa in (-1, 1) for sb in (-1, 1)]*2


def rods_bm(pairs, r):
    bm = bmesh.new()
    for p0, p1 in pairs:
        piece = hull_bm(rod_points(p0, p1, r)[:8]); me = bpy.data.meshes.new('tmp'); piece.to_mesh(me); piece.free(); bm.from_mesh(me); bpy.data.meshes.remove(me)
    return bm


def lever_objs(row, coll):
    """The extension latch hardware as eva_sp11 placed it from the rigs: lever pivot, wall bracket, torque tube up the wall to the
    outer frame's latch drive (one per operator position)."""
    fit = row['fitting']; ch = row['chamber']; R = ch['clear_radius_m']; out = []
    for k, l in row['latch'].items():
        a, p, q = l['lever_pivot_chamber']; rho = math.hypot(p, q) or 1.0; wp = (a, p*R/rho, q*R/rho); top = (ch['leaf_face_a_m']+row['door']['t'], p*R/rho, q*R/rho)
        grip = (a+l['lever_grip_radius_m'], p, q)
        out.append(obj(f"{row['id']}_Latch_{k}", rods_bm([(st.world(fit, *x), st.world(fit, *y)) for x, y in ((grip, (a, p, q)), ((a, p, q), wp), (wp, top))], .02),
                       coll, 'lever', dict(study_part='latch_station')))
    return out


def chamber_coords(fit, v):
    u, X, w = st.chamber_frame(fit); d = Vector(v)-Vector((fit['x'], 0, 0)); return d.dot(u), d.dot(X), d.dot(w)


def rig_points(objs):
    dg = bpy.context.evaluated_depsgraph_get(); return eva_fit.suit_points(objs, dg)


def wall_gap(fit, R, pts):
    """Least radial clearance of rig points to the chamber's clear radius (negative: through the wall)."""
    return min(R-math.hypot(*chamber_coords(fit, p)[1:]) for p in pts)


def set_gap(A, B):
    kd = KDTree(len(B))
    for i, p in enumerate(B):
        kd.insert(p, i)
    kd.balance(); return min(kd.find(p)[2] for p in A)


def sweep_tree(row):
    fit = row['fitting']; ch = row['chamber']; dr = row['door']; hinge = ch['leaf_face_a_m']+dr['t']; vs = []; fs = []
    for ang in (15.0, 30.0, 45.0, 60.0, 75.0, 90.0):
        bm = st.leaf_bm(fit, dr, hinge, ch['outer_leaf']['hinge_deg'], ang); off = len(vs)
        vs += [v.co.copy() for v in bm.verts]; fs += [tuple(off+v.index for v in f.verts) for f in bm.faces]; bm.free()
    return BVHTree.FromPolygons(vs, fs), vs


def frame_bm(fit, occ, hull_verts, q, theta):
    """The litter frame (rails and cross bars) around a placed supported casualty, from its rig-frame hull (study geometry)."""
    xs = [v[0] for v in hull_verts]; ys = [v[1] for v in hull_verts]; zs = [v[2] for v in hull_verts]
    cx, cy = (max(xs)+min(xs))/2, (max(ys)+min(ys))/2; hw = (max(xs)-min(xs))/2+q['frame_rail_gap_m']+q['frame_rail_r_m']
    z0 = min(zs)-q['frame_foot_m']; z1 = max(zs)+q['frame_head_m']; r = q['frame_rail_r_m']; zmax = occ['zmax_m']
    def W(x, y, z):
        c, s = math.cos(math.radians(theta)), math.sin(math.radians(theta)); p, qq = x*c-y*s+occ['shift_m'][0], x*s+y*c+occ['shift_m'][1]
        return st.world(fit, occ['a_top_m']-(zmax-z), p, qq)
    pts = []
    for sx in (-1, 1):
        pts += rod_points(W(cx+sx*hw, cy, z0), W(cx+sx*hw, cy, z1), r)
    for z in (z0, z1):
        pts += rod_points(W(cx-hw, cy, z), W(cx+hw, cy, z), r)
    bm = bmesh.new()
    for i in range(0, len(pts), 16):                                   # each rod is its own convex piece
        piece = hull_bm(pts[i:i+16]); me = bpy.data.meshes.new('tmp'); piece.to_mesh(me); piece.free(); bm.from_mesh(me); bpy.data.meshes.remove(me)
    return bm


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--sp11', type=Path, default=ROOT/'references/p1_eva_sp11.json')
    ap.add_argument('--access', type=Path, default=ROOT/'references/p1_eva_access.json')
    ap.add_argument('--vehicle', type=Path, default=ROOT/'assets/wayfarer/WF_WAYFARER_001.blend'); ap.add_argument('--out', type=Path)
    ap.add_argument('--renders', type=Path, default=ROOT/'runs/renders/p1/eva/eva3'); ap.add_argument('--size', type=int, nargs=2, default=[1280, 960])
    ap.add_argument('--report', type=Path, default=ROOT/'references/p1_eva_sp11_vehicle.json'); ap.add_argument('--no-renders', action='store_true')
    ap.add_argument('--plug-renders', type=Path, default=ROOT/'runs/renders/p1/eva/airlock'); ap.add_argument('--plug-only', action='store_true', help='skip the three-aperture comparison'); ap.add_argument('--rl-renders', action='store_true', help='render only the SIM-027 stills'); ap.add_argument('--rl', default='all', choices=('all', 'keeper', 'controls'), help='SIM-027 redline parts to measure')
    a = ap.parse_args(argv)
    sp = json.loads(a.sp11.read_text()); acc = json.loads(a.access.read_text()); env = json.loads((ROOT/'references/p1_eva_envelopes.json').read_text())
    s = spec.load(ROOT)[0]; clr = s['prototype']['mechanical_clearance_m']; data = es.load(ROOT); q = data['rescue_support']
    bpy.ops.wm.open_mainfile(filepath=str(a.vehicle))
    fit = sp['rows'][0]['fitting']; trees = st.vehicle_trees(st.world(fit, 4.0, 0.0, 0.0))
    rc = bpy.data.collections.new('STUDY_ROOMS'); bpy.context.scene.collection.children.link(rc); robjs = st.rooms(acc, rc)
    fixtures = {o.name.replace('STUDY_', ''): BVHTree.FromPolygons(*st.evaluated(o)) for o in robjs if o.get('study_part') == 'fixture'}
    report = dict(contract='eva_sp11_vehicle v1', status=sp['status'], mechanical_clearance_m=clr, rows={})
    rigs = {k: st.append_suit(k, 'A') for k in env['variants']}; rigs2 = {k: st.append_suit(k, 'B') for k in env['variants']}
    if a.plug_only and a.report.exists():
        report = json.loads(a.report.read_text())
    for row in ([] if a.plug_only else sp['rows']):
        coll = bpy.data.collections.new(f"STUDY_{row['id']}"); bpy.context.scene.collection.children.link(coll)
        objs = st.build(row, coll); mobjs = mechanism_objs(row, coll)
        # the hinged inner leaf is only one of the mechanisms: its swing is reported by eva_sp11 (radial budget), not as a conflict here
        rep = dict(structure=st.clearance(objs, trees, clr), mechanisms=st.clearance(mobjs, trees, clr), fixtures={})
        for o in mobjs:
            t = BVHTree.FromPolygons(*st.evaluated(o)); rep['fixtures'][o['study_part']] = [n for n, ft in fixtures.items() if t.overlap(ft)] or 'CLEAR'
        # the real rigs: operator (latch, then strap) and partner; rescuer with the supported casualty
        ch = row['chamber']; R = ch['clear_radius_m']; sweep, sweep_vs = sweep_tree(row); rigs_rep = {}
        for k in rigs:
            for _, ob in (rigs[k], rigs2[k]):
                for x in ob:
                    x.hide_render = True
        occ = {o['variant']: o for o in row['occupants']}
        for op in env['variants']:
            partner = next(k for k in env['variants'] if k != op); res = {}
            for pose in ('latch', 'strap'):
                h = env['variants'][op][pose]; o = dict(occ[op]); top = ch['body_top_a_m']
                o['a_top_m'] = top-occ[op]['zmax_m']+max(v[2] for v in h['verts']); o['zmax_m'] = max(v[2] for v in h['verts'])
                st.pose_and_place(rigs2[partner][0], env['variants'][partner]['chamber'], occ[partner], fit); B = rig_points(rigs2[partner][1])
                worst = None
                for fr in h['frames']:                                     # every sampled frame of the pose (lever shut / mid / open; strap high / low)
                    st.pose_and_place(rigs[op][0], dict(h, frames=[fr]), o, fit); A = rig_points(rigs[op][1])
                    kd = [sweep.find_nearest(Vector(p)) for p in A]
                    r_ = dict(wall_m=round(wall_gap(fit, R, A), 3), partner_m=round(set_gap(A, B), 3), leaf_sweep_m=round(min(h_[3] for h_ in kd if h_[0] is not None), 3))
                    worst = r_ if worst is None else {k_: min(worst[k_], v_) for k_, v_ in r_.items()}
                res[pose] = dict(frames=h['frames'], partner_wall_m=round(wall_gap(fit, R, B), 3), **worst)
            rigs_rep[op] = res
        # rescuer + casualty on the frame (the first rescue pairing of that pose)
        resc = {}
        for pr in row['rescue_occupants']:
            if pr[1]['pose'] != 'supported_frame':
                continue
            rr, cc = pr; rig_r = rigs[rr['variant']]; rig_c = rigs2[cc['variant']]
            cpose = dict(env['variants'][cc['variant']]['supported']); oc = dict(cc)
            oc['a_top_m'] = cc['a_top_m']-q['frame_head_m']; oc['zmax_m'] = max(v[2] for v in cpose['verts'])
            st.pose_and_place(rig_r[0], env['variants'][rr['variant']]['rescue'], rr, fit); st.pose_and_place(rig_c[0], cpose, oc, fit)
            fb = frame_bm(fit, oc, cpose['verts'], q, cc['theta_deg']); fo = obj(f"{row['id']}_Litter_{cc['variant']}", fb, coll, 'frame', dict(study_part='litter'))
            A = rig_points(rig_r[1]); C = rig_points(rig_c[1]); F = [fo.matrix_world @ v.co for v in fo.data.vertices]
            resc[f"{rr['variant']}+{cc['variant']}"] = dict(rescuer_wall_m=round(wall_gap(fit, R, A), 3), casualty_wall_m=round(wall_gap(fit, R, C), 3),
                                                             litter_wall_m=round(wall_gap(fit, R, F), 3), rescuer_to_casualty_m=round(set_gap(A, C+F), 3),
                                                             to_leaf_sweep_m=round(min(sweep.find_nearest(Vector(p))[3] for p in A+C+F), 3))
            bpy.data.objects.remove(fo)
        rep['rigs_latch'] = rigs_rep; rep['rigs_rescue'] = resc
        report['rows'][row['id']] = rep
        print('WF_EVA3', row['id'], json.dumps({k: (v.get('status') if isinstance(v, dict) else v) for k, v in rep['structure'].items()}),
              json.dumps({k: (v['status'], v['intersects'], v['below_clearance']) for k, v in rep['mechanisms'].items()}), rep['fixtures'],
              json.dumps(rigs_rep), json.dumps(resc), flush=True)
        bpy.data.collections.remove(coll)
    report['sliding_plug'] = plug_measure(a, sp, env, data, rigs, rigs2, trees, fixtures, clr)
    if sp['sliding_plug'].get('redlines'):
        report['redlines'] = redline_measure(a, sp, env, data, rigs, rigs2, trees, fixtures, clr, s, acc, a.rl)
    a.report.write_text(json.dumps(report, indent=1)+'\n')
    if a.no_renders:
        return
    if a.plug_only:
        bpy.data.collections.remove(rc); rc = bpy.data.collections.new('STUDY_ROOMS_RENDER'); bpy.context.scene.collection.children.link(rc)
        st.rooms(acc, rc, render=True); rc.hide_render = True
        st.render_setup(tuple(a.size)); hc = bpy.data.collections.new('STUDY_HULL'); bpy.context.scene.collection.children.link(hc)
        st.section_strips(s, sp['rows'][0]['fitting'], hc, acc); st.hide_vehicle()
    else:
        render_all(a, sp, acc, env, s, rigs, rigs2, q, rc)
    if a.rl_renders:
        redline_renders(a, sp, env, data, rigs, rigs2, s, report['redlines'])
    else:
        plug_renders(a, sp, env, data, rigs, rigs2)
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True); bpy.ops.wm.save_as_mainfile(filepath=str(a.out/'WF_EVA3_SP11_STUDY.blend'), copy=True)


def show(rig, visible):
    for x in rig[1]:
        x.hide_render = not visible or x.get('eva_role') == 'validation_body' or x.get('eva_show') == 'cutaway'


def render_all(a, sp, acc, env, s, rigs, rigs2, q, rc):
    """Per aperture: the section along the ship with the routine pair at the latch (operator) and the parallel plug parked +X; the
    rescue pairing with the litter; and one view of the latch station from inside."""
    bpy.data.collections.remove(rc); rc = bpy.data.collections.new('STUDY_ROOMS_RENDER'); bpy.context.scene.collection.children.link(rc)
    st.rooms(acc, rc, render=True); st.render_setup(tuple(a.size)); fit = sp['rows'][0]['fitting']
    hc = bpy.data.collections.new('STUDY_HULL'); bpy.context.scene.collection.children.link(hc); st.section_strips(s, fit, hc, acc); st.hide_vehicle()
    u, X, w = st.chamber_frame(fit); mid = st.world(fit, 4.0, 0.0, 0.0); eye = mid+w*14.0; rc.hide_render = True
    for row in sp['rows']:
        coll = bpy.data.collections.new(f"STUDY_R_{row['id']}"); bpy.context.scene.collection.children.link(coll); st.build(row, coll, render=True)
        for o in list(coll.objects):
            if o.name.startswith(f"{row['id']}_Inner_Leaf_Swing"):
                bpy.data.objects.remove(o)                            # the lead mechanism is the parallel plug: show its parked leaf instead
        for o in mechanism_objs(row, coll):
            if o.get('direction') not in (None, '+X') or o.get('study_part') == 'recess':
                bpy.data.objects.remove(o)
        lever_objs(row, coll)
        occ = {o['variant']: o for o in row['occupants']}; ch = row['chamber']; op, partner = list(env['variants'])
        for k in env['variants']:
            show(rigs[k], False); show(rigs2[k], False)
        h = env['variants'][op]['latch']; o = dict(occ[op]); o['a_top_m'] = ch['body_top_a_m']-occ[op]['zmax_m']+max(v[2] for v in h['verts'])
        o['zmax_m'] = max(v[2] for v in h['verts']); st.pose_and_place(rigs[op][0], h, o, fit); show(rigs[op], True)
        st.pose_and_place(rigs2[partner][0], env['variants'][partner]['chamber'], occ[partner], fit); show(rigs2[partner], True)
        m = row['mechanisms']; lead = row['aperture_m']
        lines = [f"{row['id']}  {row['role']}  STUDY ONLY (no ship geometry)",
                 f"door {lead:.2f} m   chamber {ch['clear_diameter_m']:.2f} x {ch['clear_length_m']:.2f} m  {ch['volume_m3']} m3 (EVA-002: "
                 f"{row['eva002_chamber']['clear_diameter_m']:.2f} x {row['eva002_chamber']['clear_length_m']:.2f})",
                 f"inner hatch: hinged {m['hinged_into_sp12']['radial_budget_m']:+.2f} m to the SP-12 floor ({m['hinged_into_sp12']['status']}); "
                 f"parallel plug {m['parallel_plug_slide']['radial_budget_m']:+.2f} m, parked +X ({m['parallel_plug_slide']['status']})",
                 'operator: extension latch lever (left hand), partner beside']
        lb = st.label('\n'.join(lines), st.world(fit, 7.45, -4.65, 2.0), eye, u, .13)
        st.camera(eye, mid, up=u, ortho=9.6); st.render(a.renders/f"{row['id'].lower()}_section.png")
        # the latch station seen along the ship (X): the lever ahead of the operator, its bracket and the torque tube up the wall
        mid2 = st.world(fit, (ch['inner_bulkhead_a_m']+ch['outer_bulkhead_a_m'])/2+.3, 0.0, 0.0); eye2 = mid2+X*9.0
        lb2 = st.label(f"{row['id']}  extension latch (EVA3-002), seen along the ship\nlever, wall bracket and torque tube to the outer frame's "
                       "latch drive (red)", st.world(fit, ch['outer_bulkhead_a_m']+.6, 0.0, -1.9), eye2, u, .09)
        hid = [o for o in coll.objects if o.name.startswith((f"{row['id']}_Chamber_Shell", f"{row['id']}_Outer_Neck"))]
        for o in hid:
            o.hide_render = True
        show(rigs2[partner], False)
        st.camera(eye2, mid2, up=u, ortho=5.6); st.render(a.renders/f"{row['id'].lower()}_latch.png"); bpy.data.objects.remove(lb2)
        for o in hid:
            o.hide_render = False
        show(rigs2[partner], True)
        # rescue: rescuer with the casualty on the litter frame
        for k in env['variants']:
            show(rigs[k], False); show(rigs2[k], False)
        pr = next(p for p in row['rescue_occupants'] if p[1]['pose'] == 'supported_frame'); rr, cc = pr
        cpose = env['variants'][cc['variant']]['supported']; oc = dict(cc); oc['a_top_m'] = cc['a_top_m']-q['frame_head_m']; oc['zmax_m'] = max(v[2] for v in cpose['verts'])
        st.pose_and_place(rigs[rr['variant']][0], env['variants'][rr['variant']]['rescue'], rr, fit); show(rigs[rr['variant']], True)
        st.pose_and_place(rigs2[cc['variant']][0], cpose, oc, fit); show(rigs2[cc['variant']], True)
        fo = obj(f"{row['id']}_Litter", frame_bm(fit, oc, cpose['verts'], q, cc['theta_deg']), coll, 'frame')
        lb.data.body = f"{row['id']}  STUDY ONLY\nrescue: {rr['variant']} holds the {cc['variant']} secured on a full-length litter frame\n" \
                       f"supported casualty through the door: margin {min(v['margin_m'] for k_, v in row['door_passage'].items() if k_.endswith('supported_frame')):+.2f} m; " \
                       f"free limp: {min(v['margin_m'] for k_, v in row['door_passage'].items() if k_.endswith('.casualty')):+.2f} m"
        st.render(a.renders/f"{row['id'].lower()}_rescue.png")
        bpy.data.objects.remove(fo); bpy.data.objects.remove(lb); bpy.data.collections.remove(coll)


# ---------------------------------------------------------------------------------------------------------------------------------
# SP-11 1.20 m sliding plug (owner direction 2026-10-11): geometry from eva_sp11_plug, measured against the vehicle and the posed rigs

def cyl_pts(c, nrm, r, th, n=24):
    """Points of a thin disc in chamber coordinates: centre c, normal nrm, radius r, thickness th."""
    nrm = Vector(nrm).normalized(); e1 = nrm.orthogonal().normalized(); e2 = nrm.cross(e1); c = Vector(c)
    return [tuple(c+e1*math.cos(2*math.pi*i/n)*r+e2*math.sin(2*math.pi*i/n)*r+nrm*sg*th/2) for i in range(n) for sg in (-1, 1)]


def combine(bms):
    out = bmesh.new()
    for b in bms:
        me = bpy.data.meshes.new('tmp'); b.to_mesh(me); b.free(); out.from_mesh(me); bpy.data.meshes.remove(me)
    return out


def hb(fit, pts):
    return hull_bm([st.world(fit, *p) for p in pts])


def box_pts(a, r, t):
    """Corners of a box in chamber coordinates: a range, radial range, tangential half width, at angle psi given by the caller via (r0, r1, tt)."""
    return a, r, t


def dog_piece(fit, psi, a0, a1, r0, r1, tt):
    c, s_ = math.cos(psi), math.sin(psi)
    return hb(fit, [(a, r*c-t*s_, r*s_+t*c) for a in (a0, a1) for r in (r0, r1) for t in (-tt, tt)])


def plug_objs(row, sl, pq, rq, coll):
    """The plug in its three states, the swept envelope, the carriage and rails, dogs, keeper ledges, blocking pins, the lever linkage down to
    the dog cam ring, the load-path markers and the control panels. STUDY objects only."""
    fit = row['fitting']; dr = row['door']; ch = row['chamber']; kin = sl['kinematics']; meta = kin['meta']; ret = sl['retention']; g = ret['geometry']
    top = meta['seat_top_a_m']; drop = rq['plug_stroke_m']; t = dr['t']; rl = dr['r_leaf']; travel = meta['travel_m']; rail = rq['slide_rail_depth_m']; i = row['id']
    out = []

    def add(name, bm, key, part):
        out.append(obj(f'{i}_{name}', bm, coll, key, dict(study_part=part)))
    leaf = lambda dz, qq: cyl_pts((top-dz-t/2, 0.0, -qq), (1, 0, 0), rl, t, 48)
    add('Plug_Seated', hb(fit, leaf(0.0, 0.0)), 'sweep', 'plug_seated'); add('Plug_Dropped', hb(fit, leaf(drop, 0.0)), 'sweep', 'plug_dropped')
    add('Plug_Parked', hb(fit, leaf(drop, travel)), 'leaf', 'plug_parked')
    cb = top-drop-t; car = [(a, p, -travel+w) for a in (cb-rail, cb) for p in (-rl-.05, rl+.05) for w in (-rl-.05, rl+.05)]
    add('Plug_Carriage', hb(fit, car), 'pocket', 'plug_carriage')
    add('Plug_Swept', hb(fit, leaf(drop, 0.0)+leaf(drop, travel)+car+[(a, p, q) for a in (cb-rail, cb) for p in (-rl-.05, rl+.05) for q in (-rl-.05, rl+.05)]),
        'sweep', 'plug_swept')
    add('Plug_Rails', combine([hb(fit, [(cb-rail, p+dp, q) for dp in (-.02, .02) for q in (-travel-rl, .2)]+[(cb, p+dp, q) for dp in (-.02, .02) for q in (-travel-rl, .2)])
                               for p in (-.45, .45)]), 'lever', 'plug_rails')
    add('Frame_Ring', st.tube(fit, top, top+dr['frame_depth'], dr['r_clear'], rl+.10), 'neck', 'frame_ring')
    n = g['dog_count']; dh = g['dog_h_m']; dog_a = top-dh/2
    add('Dogs', combine([dog_piece(fit, 2*math.pi*k/n, top-dh, top, rl, rl+g['dog_stroke_m'], g['dog_w_m']/2) for k in range(n)]), 'lever', 'dogs')
    add('Keeper_Ledges', combine([dog_piece(fit, 2*math.pi*k/n, top-max(g['lug_depth_m'], dh+.004), top-dh, rl, rl+g['dog_stroke_m']+.04, .06) for k in range(n)]), 'frame', 'keeper_ledges')
    add('Blocking_Pins', combine([dog_piece(fit, math.pi/2+k*math.pi, top-t/2-.006, top-t/2+.006, rl-.14, rl+.01, .006) for k in range(2)]), 'release', 'blocking_pins')
    R = ch['clear_radius_m']
    for k, l in row['latch'].items():
        a_, p_, q_ = l['lever_pivot_chamber']; rho = math.hypot(p_, q_) or 1.0; wp = (a_, p_*R/rho, q_*R/rho); lo = (top+dr['frame_depth'], p_*(rl+.07)/rho, q_*(rl+.07)/rho)
        add(f'Plug_Lever_Linkage_{k}', rods_bm([(st.world(fit, *x), st.world(fit, *y)) for x, y in ((wp, (top+.30, wp[1], wp[2])), ((top+.30, wp[1], wp[2]), (lo[0]+.02, lo[1]*R/(rl+.07), lo[2]*R/(rl+.07))),
                                                                                         ((lo[0]+.02, lo[1]*R/(rl+.07), lo[2]*R/(rl+.07)), lo))], .015), 'lever', 'plug_lever')
    chain = ['P_chamber', 'LEAF_PLATE', 'DOG', 'KEEPER_LEDGE', 'FRAME_RING', 'BULKHEAD_RING']; mk = {m['id']: m['chamber'] for m in ret['markers']}
    add('Load_Path_Reverse', rods_bm([(st.world(fit, *mk[x]), st.world(fit, *mk[y])) for x, y in zip(chain, chain[1:])], .012), 'path', 'load_path')
    for m in ret['markers']:
        add(f"Marker_{m['id']}", hb(fit, cyl_pts(m['chamber'], (1, 0, 0), .035, .07, 12)), 'seat' if m['id'] == 'SEAT_LIP' else 'path', 'marker')
    out += panel_objs(row, sl, pq, coll)
    return out


def panel_objs(row, sl, pq, coll):
    """Backplate, equalization valve handwheel, gauge dial and release ring of every control cluster (chamber side: two, SP-12 side: one)."""
    fit = row['fitting']; R = row['chamber']['clear_radius_m']; wall = fit['wall_m']; out = []; ctl = sl['controls']
    for side, cls in (('chamber', ctl['chamber']['clusters']), ('sp12', [ctl['sp12']])):
        for cl in cls:
            phi = math.radians(cl['angle_deg']); nrm = (0.0, math.cos(phi), math.sin(phi)); tag = f"{row['id']}_Panel_{side}_{cl.get('for_crew', 'sp12')}"
            lay = dict(layout='row', pitch_m=cl['pitch_m']) if cl.get('layout') == 'row' else None
            out.append(obj(tag+'_Plate', hb(fit, pl.panel_box_pts(R, cl['station_a_m'], phi, pq, side, wall, lay)), coll, 'neck', dict(study_part=f'panel_{side}')))
            for nm, key, r_, th in (('valve', 'valve', .05, .02), ('gauge', 'gauge', .045, .03), ('release', 'release', .03, .015)):
                out.append(obj(f'{tag}_{nm}', hb(fit, cyl_pts(cl['points'][nm], nrm, r_, th, 24)), coll, key, dict(study_part=f'ctl_{nm}_{side}')))
    return out


def tree_of(o):
    return BVHTree.FromPolygons(*st.evaluated(o))


def pts_to(A, T):
    """Least surface distance from points A (world) to the BVH T."""
    best = 9.0
    for p in A:
        h = T.find_nearest(Vector(p), 3.0)
        if h[0] is not None:
            best = min(best, h[3])
    return round(best, 3)


def plug_measure(a, sp, env, data, rigs, rigs2, trees, fixtures, clr):
    """The sliding-plug objects against the vehicle and the SP-12 fixtures, then the real rig meshes against the plug envelope, the panels and the bore."""
    sl = sp['sliding_plug']; pq = data['sp11_plug']; rq = data['sp11_eva3']; k_ = data['rescue_support']; margin = data['access']['suit_margin_m']
    row = next(r for r in sp['rows'] if abs(r['aperture_m']-pq['aperture_m']) < 1e-9); fit = row['fitting']; ch = row['chamber']; R = ch['clear_radius_m']
    coll = bpy.data.collections.new('STUDY_PLUG'); bpy.context.scene.collection.children.link(coll); pl.configure(pq)
    base = st.build(row, coll); po = plug_objs(row, sl, pq, rq, coll); rep = dict(status='STUDY: real suit meshes and vehicle meshes against the sliding-plug study geometry')
    by = lambda part: next(o for o in po if o.get('study_part') == part)
    # 1. vehicle and fixtures
    cl = st.clearance([o for o in po if o.get('study_part') in ('plug_swept', 'plug_carriage', 'plug_rails', 'plug_parked', 'frame_ring', 'dogs', 'keeper_ledges', 'plug_lever')]
                      + [o for o in po if str(o.get('study_part')).startswith(('panel_sp12', 'ctl_')) and 'sp12' in o.name], trees, clr)
    fx = {}
    for part in ('plug_swept', 'plug_carriage', 'plug_parked'):
        pts = st.sample(*st.evaluated(by(part)))
        fx[part] = {n: round(min((h[3] for h in (ft.find_nearest(Vector(p), 3.0) for p in pts) if h[0] is not None), default=9.0), 3) for n, ft in fixtures.items()}
    sp12_p = [o for o in po if o.get('study_part') == 'panel_sp12']
    fx['panel_sp12'] = {n: round(min((h[3] for h in (ft.find_nearest(Vector(p), 3.0) for p in st.sample(*st.evaluated(sp12_p[0]))) if h[0] is not None), default=9.0), 3) for n, ft in fixtures.items()}
    rep['vehicle'] = {k: dict(status=v['status'], intersects=v['intersects'], below_clearance=v['below_clearance'], nearest=v['nearest']) for k, v in cl.items()}
    rep['fixtures_nearest_m'] = fx
    rep['fixtures_min_m'] = {k: min(v.values()) for k, v in fx.items()}
    # 2. targets for the rigs
    T = {nm: tree_of(by(part)) for nm, part in (('plug_envelope', 'plug_swept'), ('carriage', 'plug_carriage'), ('parked_leaf', 'plug_parked'), ('frame_ring', 'frame_ring'))}
    for o in po:
        if str(o.get('study_part', '')).startswith('panel_chamber'):
            T.setdefault('panel_chamber', []).append(tree_of(o))
        if o.get('study_part') == 'panel_sp12':
            T['panel_sp12'] = tree_of(o)
    T['bulkhead'] = tree_of(base[2]); T['shell'] = tree_of(base[0])                 # st.build: shell, outer bulkhead, inner bulkhead, neck, leaves
    pc = lambda A: min(pts_to(A, t) for t in T['panel_chamber'])
    for k in rigs:
        for _, ob in (rigs[k], rigs2[k]):
            for x in ob:
                x.hide_render = True
    occ = {o['variant']: o for o in row['occupants']}; res = {}
    # routine standing positions and the lever / strap poses
    for op in env['variants']:
        partner = next(k for k in env['variants'] if k != op); r_ = {}
        for pose in ('chamber', 'latch', 'strap'):
            h = env['variants'][op][pose]; o = dict(occ[op]); top = ch['body_top_a_m']
            o['a_top_m'] = top-occ[op]['zmax_m']+max(v[2] for v in h['verts']); o['zmax_m'] = max(v[2] for v in h['verts'])
            st.pose_and_place(rigs2[partner][0], env['variants'][partner]['chamber'], occ[partner], fit); B = rig_points(rigs2[partner][1])
            worst = {}
            for fr in h['frames'][:6]:
                st.pose_and_place(rigs[op][0], dict(h, frames=[fr]), o, fit); A = rig_points(rigs[op][1])
                m = dict(to_plug_envelope_m=pts_to(A, T['plug_envelope']), to_chamber_panels_m=pc(A), to_panel_gap_partner_m=min(pts_to(B, t) for t in T['panel_chamber']))
                worst = m if not worst else {kk: min(worst[kk], v) for kk, v in m.items()}
            r_[pose] = worst
        res[op] = r_
    rep['rigs_routine'] = res
    # rescuer + casualty on the strapped litter frame, both pairings
    resc = {}
    for pr in row['rescue_occupants']:
        if pr[1]['pose'] != 'supported_frame':
            continue
        rr, cc = pr; rig_r = rigs[rr['variant']]; rig_c = rigs2[cc['variant']]; cpose = env['variants'][cc['variant']]['supported']; oc = dict(cc)
        oc['a_top_m'] = cc['a_top_m']-k_['frame_head_m']; oc['zmax_m'] = max(v[2] for v in cpose['verts'])
        st.pose_and_place(rig_r[0], env['variants'][rr['variant']]['rescue'], rr, fit); st.pose_and_place(rig_c[0], cpose, oc, fit)
        fo = obj('Litter', frame_bm(fit, oc, cpose['verts'], k_, cc['theta_deg']), coll, 'frame', dict(study_part='litter'))
        sbm = combine([hull_bm([st.world(fit, *c) for c in b.corners()]) for b in pl.straps(env['variants'][cc['variant']]['supported_frame'], cc['theta_deg'], tuple(cc['shift_m']),
                                                                                            cc['a_top_m'], cc['zmax_m'], k_, pq['strap_tail_stowed_m'])])
        so = obj('Straps', sbm, coll, 'strap', dict(study_part='straps'))
        A = rig_points(rig_r[1]); C = rig_points(rig_c[1]); F = [fo.matrix_world @ v.co for v in fo.data.vertices]; S = [so.matrix_world @ v.co for v in so.data.vertices]
        resc[f"{rr['variant']}+{cc['variant']}"] = dict(
            casualty_litter_straps_to_plug_envelope_m=pts_to(C+F+S, T['plug_envelope']), rescuer_to_plug_envelope_m=pts_to(A, T['plug_envelope']),
            casualty_litter_straps_to_chamber_panels_m=pc(C+F+S), rescuer_to_chamber_panels_m=pc(A), straps_to_wall_m=round(min(R-math.hypot(*chamber_coords(fit, p)[1:]) for p in S), 3))
        bpy.data.objects.remove(fo); bpy.data.objects.remove(so)
    rep['rigs_rescue_litter'] = resc
    # the casualty centred on the aperture, moved along -a: bore (frame ring), the parked leaf and carriage, with the straps
    transit = {}; cc = next(p[1] for p in row['rescue_occupants'] if p[1]['pose'] == 'supported_frame')
    cv = cc['variant']; cpose = env['variants'][cv]['supported']; rig_c = rigs2[cv]
    for depth in (0.0, 0.4, 0.8, 1.2):
        oc = dict(cc); oc['shift_m'] = [0.0, 0.0]; oc['a_top_m'] = cc['a_top_m']-k_['frame_head_m']-depth; oc['zmax_m'] = max(v[2] for v in cpose['verts'])
        st.pose_and_place(rig_c[0], cpose, oc, fit)
        fo = obj('Litter', frame_bm(fit, oc, cpose['verts'], k_, cc['theta_deg']), coll, 'frame', dict(study_part='litter'))
        ocs = dict(cc, shift_m=[0.0, 0.0], a_top_m=cc['a_top_m']-depth)
        so = obj('Straps', combine([hull_bm([st.world(fit, *c) for c in b.corners()]) for b in pl.straps(env['variants'][cv]['supported_frame'], cc['theta_deg'], (0.0, 0.0),
                                                                                                         ocs['a_top_m'], cc['zmax_m'], k_, pq['strap_tail_stowed_m'])]), coll, 'strap', dict(study_part='straps'))
        C = rig_points(rig_c[1]); F = [fo.matrix_world @ v.co for v in fo.data.vertices]; S = [so.matrix_world @ v.co for v in so.data.vertices]
        transit[f'depth_{depth:.1f}'] = dict(suit_to_frame_ring_m=pts_to(C, T['frame_ring']), litter_to_frame_ring_m=pts_to(F, T['frame_ring']), straps_to_frame_ring_m=pts_to(S, T['frame_ring']),
                                             all_to_parked_leaf_m=pts_to(C+F+S, T['parked_leaf']), all_to_carriage_m=pts_to(C+F+S, T['carriage']))
        bpy.data.objects.remove(fo); bpy.data.objects.remove(so)
    rep['transit_casualty_centred'] = dict(variant=cv, depths_m=transit, note='suit mesh, litter rails and the box straps (an envelope wider than the contour-following bands of eva_sp11_plug); '
                                                                              'the frame ring is the bore edge, the parked leaf and carriage the plug')
    # SP-12 operators at their stations (suited rigs): chamber wall, fixtures, the plug envelope, the panel
    ops = {}; so_ = sl['controls']['sp12']['operator']
    for k in env['variants']:
        c = so_[f'suited_{k}']; h = env['variants'][k]['chamber']; zmax = max(v[2] for v in h['verts']); zmin = min(v[2] for v in h['verts'])
        o = dict(theta_deg=c['facing_deg'], shift_m=c['station_chamber'][1:], a_top_m=c['station_chamber'][0]+zmax-zmin, zmax_m=zmax)
        st.pose_and_place(rigs[k][0], h, o, fit); A = rig_points(rigs[k][1])
        ops[k] = dict(to_chamber_outer_wall_m=pts_to(A, T['shell']), to_plug_envelope_m=pts_to(A, T['plug_envelope']), to_panel_m=pts_to(A, T['panel_sp12']),
                      to_fixtures_m={n: round(min((hh[3] for hh in (ft.find_nearest(Vector(p), 3.0) for p in A) if hh[0] is not None), default=9.0), 3) for n, ft in fixtures.items()})
    rep['sp12_operators_suited'] = ops
    for o in list(coll.objects):
        bpy.data.objects.remove(o)
    bpy.data.collections.remove(coll)
    return rep


def keeper_summary(rep):
    """The named distances of a plug_measure report that depend on the plug's stroke and carriage, and their least (name, value)."""
    d = {}
    for op, poses in rep['rigs_routine'].items():
        for pose, m in poses.items():
            d[f'{op}.{pose}.rig_to_plug_envelope'] = m['to_plug_envelope_m']
    for pair, m in rep['rigs_rescue_litter'].items():
        d[f'{pair}.casualty_litter_straps_to_plug_envelope'] = m['casualty_litter_straps_to_plug_envelope_m']; d[f'{pair}.rescuer_to_plug_envelope'] = m['rescuer_to_plug_envelope_m']
    for k, m in rep['sp12_operators_suited'].items():
        d[f'sp12_operator_{k}.to_plug_envelope'] = m['to_plug_envelope_m']
    for dep, m in rep['transit_casualty_centred']['depths_m'].items():
        d[f'transit.{dep}.to_parked_leaf'] = m['all_to_parked_leaf_m']; d[f'transit.{dep}.to_carriage'] = m['all_to_carriage_m']
    env = {k: v for k, v in d.items() if 'plug_envelope' in k}; tr = {k: v for k, v in d.items() if k.startswith('transit')}
    le = min(env, key=env.get); lt = min(tr, key=tr.get)
    return dict(envelope_least_m=env[le], envelope_least_at=le, parked_leaf_carriage_least_m=tr[lt], parked_leaf_carriage_least_at=lt, vehicle={k: v['status'] for k, v in rep['vehicle'].items()},
                vehicle_intersects={k: v['intersects'] for k, v in rep['vehicle'].items() if v['intersects']}, fixtures_min_m=rep['fixtures_min_m'], distances_m=d)


def redline_measure(a, sp, env, data, rigs, rigs2, trees, fixtures, clr, s, acc, parts='all'):
    """SIM-027 on the real meshes: every keeper variant's plug envelope (stroke, carriage depth) against the rig meshes, and every SP-12 control variant
    (cluster layout, stand A, zone, stand-off) against the operators posed at its station."""
    import copy
    sl = sp['sliding_plug']; red = sl['redlines']; pq0 = data['sp11_plug']; rq0 = data['sp11_eva3']
    row = next(r for r in sp['rows'] if abs(r['aperture_m']-pq0['aperture_m']) < 1e-9); fit = row['fitting']; ch = row['chamber']
    out = dict(keeper={}, controls={}, status='STUDY: real suit meshes against SIM-027 variants (disposable objects, nothing saved)')
    for kv in (red['keeper'] if parts in ('all', 'keeper') else []):
        d2 = copy.deepcopy(data); d2['sp11_eva3'].update(plug_stroke_m=kv['stroke_m'], slide_rail_depth_m=kv['rail_m'])
        d2['sp11_plug'].update(dog_h_m=kv['dog_h_m'], ledge_h_m=kv['ledge_h_m'], ledge_recess_m=kv['ledge_recess_m'])
        ret = pl.retention(s, row, d2['sp11_plug'], d2['sp11_eva3']); sp2 = dict(sp, sliding_plug=dict(sl, retention=ret))
        rep = plug_measure(a, sp2, env, d2, rigs, rigs2, trees, fixtures, clr); out['keeper'][kv['id']] = keeper_summary(rep)
        print('WF_REDLINE keeper', kv['id'], out['keeper'][kv['id']]['envelope_least_m'], out['keeper'][kv['id']]['envelope_least_at'], out['keeper'][kv['id']]['parked_leaf_carriage_least_m'], flush=True)
    # control variants: operators at their stations
    pl.configure(pq0); coll = bpy.data.collections.new('STUDY_RL'); bpy.context.scene.collection.children.link(coll)
    base = st.build(row, coll); po = plug_objs(row, sl, pq0, rq0, coll)
    by = lambda part: next(o for o in po if o.get('study_part') == part)
    T_plug = tree_of(by('plug_swept')); T_shell = tree_of(base[0])
    for cv in (red['controls_sp12'] if parts in ('all', 'controls') else []):
        acc2 = copy.deepcopy(acc)
        for f in acc2['sp12']['fixtures']:
            if f['id'] == 'SP12_DON_STAND_A':
                f['x'] = cv['stand_a']['x_m']; f['az'] = cv['stand_a']['az_deg']
            if f['id'] == 'SP12_BUDDY_ZONE':
                f['x'] = cv['buddy_zone']['x_m']; f['az'] = cv['buddy_zone']['az_deg']
        rcoll = bpy.data.collections.new('STUDY_RL_ROOMS'); bpy.context.scene.collection.children.link(rcoll); robjs = [o for o in st.rooms(acc2, rcoll) if o.get('study_part') == 'fixture']
        fx = {o.name.replace('STUDY_', '').split('.')[0]: tree_of(o) for o in robjs}
        ps = dict(cv, points=cv['points'], pitch_m=pq0['panel_pitch_m'] if cv['layout'] == 'row' else None)
        ps['station_a_m'] = cv['station_a_m']; ps['angle_deg'] = cv['angle_deg']
        sl2 = dict(sl, controls=dict(sl['controls'], sp12=ps))
        pobjs = panel_objs(row, sl2, pq0, coll); plate = next(o for o in pobjs if o.get('study_part') == 'panel_sp12'); T_plate = tree_of(plate)
        res = {}
        for k in env['variants']:
            c = cv['operator'][f'suited_{k}']; h = env['variants'][k]['chamber']; zmax = max(v[2] for v in h['verts']); zmin = min(v[2] for v in h['verts'])
            o = dict(theta_deg=c['facing_deg'], shift_m=c['station_chamber'][1:], a_top_m=c['station_chamber'][0]+zmax-zmin, zmax_m=zmax)
            st.pose_and_place(rigs[k][0], h, o, fit); A = rig_points(rigs[k][1])
            solid = {n: round(min((hh[3] for hh in (ft.find_nearest(Vector(p), 3.0) for p in A) if hh[0] is not None), default=9.0), 3) for n, ft in fx.items()}
            zone = solid.pop('SP12_BUDDY_ZONE')
            r_ = dict(to_chamber_outer_wall_m=pts_to(A, T_shell), to_plug_envelope_m=pts_to(A, T_plug), to_panel_plate_m=pts_to(A, T_plate), to_fixtures_m=solid, to_buddy_zone_surface_m=zone)
            r_['least_m'] = min([r_['to_chamber_outer_wall_m'], r_['to_plug_envelope_m'], r_['to_panel_plate_m']]+list(solid.values()))
            res[k] = r_
        least = min(res.values(), key=lambda r: r['least_m'])
        parts = {n: min(res[k][n] for k in res) for n in ('to_chamber_outer_wall_m', 'to_plug_envelope_m', 'to_panel_plate_m')}
        parts['to_fixtures_m'] = min(min(res[k]['to_fixtures_m'].values()) for k in res)
        nm = min(parts, key=parts.get)
        out['controls'][cv['id']] = dict(operators_suited=res, least_m=least['least_m'], least_component=nm, components_least_m=parts)
        print('WF_REDLINE controls', cv['id'], least['least_m'], nm, parts, flush=True)
        for o in pobjs + robjs:
            bpy.data.objects.remove(o)
        bpy.data.collections.remove(rcoll)
    for o in list(coll.objects):
        bpy.data.objects.remove(o)
    bpy.data.collections.remove(coll)
    return out


def redline_renders(a, sp, env, data, rigs, rigs2, s, red_meas):
    """SIM-027 stills into runs/renders/p1/eva/airlock/: the keeper section of the 0.10 m stroke variant against the published 0.08 m one, and the SP-12 side
    with the row-layout control cluster (operator posed at its station, donning stand A and the other fixtures in place)."""
    import copy
    sl = sp['sliding_plug']; red = sl['redlines']; pq = data['sp11_plug']; rq = data['sp11_eva3']; out = a.plug_renders
    row = next(r for r in sp['rows'] if abs(r['aperture_m']-pq['aperture_m']) < 1e-9); fit = row['fitting']; u, X, w = st.chamber_frame(fit); i = row['id']
    coll = bpy.data.collections.new('STUDY_RL_R'); bpy.context.scene.collection.children.link(coll); base = st.build(row, coll, render=True)
    for o in list(coll.objects):
        if 'Inner_Leaf' in o.name:
            o.hide_render = True

    def hide_all():
        for k in env['variants']:
            show(rigs[k], False); show(rigs2[k], False)

    def corner(text, eye, mid, up, ortho):
        M = st.view_matrix(eye, mid, up); x = Vector(M.col[0][:3]); y = Vector(M.col[1][:3]); z = Vector(M.col[2][:3])
        return st.label(text, Vector(mid)-x*ortho*.48+y*ortho*.375*.93+z*(Vector(eye)-Vector(mid)).length*.5, eye, up, ortho*.0195)
    shell = lambda o: 'Chamber_Shell' in o.name or 'Outer_Neck' in o.name or 'Outer_Bulkhead' in o.name
    hide_all()
    # 1. keeper section: published 0.08 m stroke (ghost seated, dropped) with the lugs, then the 0.10 m variant
    kv = {k['id']: k for k in red['keeper']}
    for vid, tag in (('KP0_baseline', 'base'), ('KP1_stroke_0.10', 'stroke010')):
        k = kv[vid]; d2 = copy.deepcopy(data); d2['sp11_eva3'].update(plug_stroke_m=k['stroke_m'], slide_rail_depth_m=k['rail_m'])
        d2['sp11_plug'].update(dog_h_m=k['dog_h_m'], ledge_h_m=k['ledge_h_m'], ledge_recess_m=k['ledge_recess_m']); pl.configure(d2['sp11_plug'])
        ret = pl.retention(s, row, d2['sp11_plug'], d2['sp11_eva3']); sl2 = dict(sl, retention=ret)
        po = plug_objs(row, sl2, d2['sp11_plug'], d2['sp11_eva3'], coll)
        for o in coll.objects:
            if shell(o) or str(o.get('study_part')) in ('plug_parked', 'plug_swept', 'plug_carriage', 'plug_rails', 'marker', 'load_path', 'plug_lever', 'blocking_pins') or str(o.get('study_part')).startswith(('panel_', 'ctl_')):
                o.hide_render = True
        top = sl['kinematics']['meta']['seat_top_a_m']; mid = st.world(fit, top-0.07, row['door']['r_leaf']+0.03, 0.0); eye = mid+w*8.0
        lb = corner('\n'.join((f"{i}  KEEPER CLEARANCE, {vid}   STUDY / PROTOTYPE", f"stroke {k['stroke_m']:.2f} m; lug hang {k['lug_hang_m']:.3f} m; clearance {k['keeper_clearance_m']:+.3f} m {k['keeper_status']} (owner target >= 0.05)",
                                f"swept envelope to bodies {k['plug_to_bodies_min_m']:+.3f} m (hull planes); SP-12 room margin {k['sp12_room_margin_m']:+.3f} m",
                                "dogs (red) and keeper ledges (yellow) on the frame ring; ghost: seated leaf, dropped leaf")), eye, mid, u, 0.8)
        st.camera(eye, mid, up=u, ortho=0.8); st.render(out/f'sp11_120_redline_keeper_{tag}.png'); bpy.data.objects.remove(lb)
        for o in po:
            bpy.data.objects.remove(o)
    # 2. SP-12 side with the row cluster
    cv = {c['id']: c for c in red['controls_sp12']}['CT3_row_fine_angle_standoff_0.13']; meas = red_meas['controls']['CT3_row_fine_angle_standoff_0.13']; pl.configure(pq)
    ps = dict(cv, pitch_m=pq['panel_pitch_m']); sl2 = dict(sl, controls=dict(sl['controls'], sp12=ps))
    po = plug_objs(row, sl2, pq, rq, coll)
    for o in coll.objects:
        if str(o.get('study_part')) in ('plug_parked', 'plug_swept', 'plug_carriage', 'plug_rails', 'plug_dropped', 'marker', 'load_path', 'plug_lever', 'blocking_pins', 'dogs', 'keeper_ledges', 'plug_seated') \
                or str(o.get('study_part')).startswith('panel_chamber') or str(o.get('study_part')).startswith('ctl_') and 'chamber' in str(o.get('study_part')):
            o.hide_render = True
        elif shell(o):
            o.hide_render = False
    rc = bpy.data.collections.get('STUDY_ROOMS_RENDER'); rc.hide_render = False
    for o in rc.objects:
        o.hide_render = o.get('study_part') != 'fixture' or 'ZONE' in o.name
    k = list(env['variants'])[1]; h = env['variants'][k]['chamber']; zmax = max(v[2] for v in h['verts']); zmin = min(v[2] for v in h['verts']); c = cv['operator'][f'suited_{k}']
    o = dict(theta_deg=c['facing_deg'], shift_m=c['station_chamber'][1:], a_top_m=c['station_chamber'][0]+zmax-zmin, zmax_m=zmax)
    st.pose_and_place(rigs[k][0], h, o, fit); show(rigs[k], True)
    mid = st.world(fit, 2.9, 1.55, 0.0); eye = mid+w*12.0
    lb = corner('\n'.join((f"{i}  SP-12 SIDE CONTROLS, row layout, 0.13 m stand-off (CT3)   STUDY / PROTOTYPE",
                           f"suited reach margin >= {cv['reach_suited_min_m']:+.3f} m (published layout +0.007), unsuited >= {cv['reach_unsuited_min_m']:+.3f} m",
                           f"operator mesh to panel plate {meas['components_least_m']['to_panel_plate_m']:+.3f}, wall {meas['components_least_m']['to_chamber_outer_wall_m']:+.3f}, fixtures {meas['components_least_m']['to_fixtures_m']:+.3f} m",
                           "release, valve, gauge side by side at one height; donning stand A not moved; buddy zone not drawn")), eye, mid, u, 5.2)
    st.camera(eye, mid, up=u, ortho=5.2); st.render(out/'sp11_120_redline_valves_sp12_row.png'); bpy.data.objects.remove(lb)
    hide_all(); rc.hide_render = True; bpy.data.collections.remove(coll)


def plug_renders(a, sp, env, data, rigs, rigs2):
    """Four stills of the 1.20 m sliding plug into runs/renders/p1/eva/airlock/: the plug parked, the casualty transit, the two-side valves and the retention section."""
    sl = sp['sliding_plug']; pq = data['sp11_plug']; rq = data['sp11_eva3']; k_ = data['rescue_support']; row = next(r for r in sp['rows'] if abs(r['aperture_m']-pq['aperture_m']) < 1e-9)
    fit = row['fitting']; ch = row['chamber']; u, X, w = st.chamber_frame(fit); pl.configure(pq); out = a.plug_renders; i = row['id']; names = 'sp11_120_slideplug_'
    coll = bpy.data.collections.new('STUDY_PLUG_R'); bpy.context.scene.collection.children.link(coll); base = st.build(row, coll, render=True)
    for o in list(coll.objects):
        if o.name.startswith((f'{i}_Inner_Leaf', f'{i}_Outer_Leaf_Swing', f'{i}_Inner_Leaf_Swing')) and 'Swing' in o.name:
            bpy.data.objects.remove(o)
    po = plug_objs(row, sl, pq, rq, coll)
    for o in coll.objects:                                                 # the old hinged inner leaf is not this concept: the plug objects replace it
        if 'Inner_Leaf' in o.name and 'Swing' not in o.name:
            o.hide_render = True
    occ = {o['variant']: o for o in row['occupants']}; op, partner = list(env['variants'])
    def hide_all():
        for k in env['variants']:
            show(rigs[k], False); show(rigs2[k], False)
    def routine():
        for k, rg in ((op, rigs[op]), (partner, rigs2[partner])):
            h = env['variants'][k]['chamber']; st.pose_and_place(rg[0], h, occ[k], fit); show(rg, True)
    def tog(flt, vis):
        for o in coll.objects:
            if flt(o):
                o.hide_render = not vis
    hide_all(); routine()
    lines = lambda *t: '\n'.join(t)

    def corner(text, eye, mid, up, ortho):
        M = st.view_matrix(eye, mid, up); x = Vector(M.col[0][:3]); y = Vector(M.col[1][:3])
        z = Vector(M.col[2][:3]); return st.label(text, Vector(mid)-x*ortho*.48+y*ortho*.375*.93+z*(Vector(eye)-Vector(mid)).length*.5, eye, up, ortho*.0195)
    shell = lambda o: 'Chamber_Shell' in o.name or 'Outer_Neck' in o.name or 'Outer_Bulkhead' in o.name
    kin = sl['kinematics']; cs_ = sl['cases']; ret = sl['retention']; ctl = sl['controls']
    # A. plug parked, seen from below on the -az side (the lateral park is in the picture plane); shell hidden
    mid = st.world(fit, 3.3, 0.0, -0.6); dirv = (X*0.45-w*0.8-u*0.25).normalized(); eye = mid+dirv*12.0; tog(shell, False); tog(lambda o: str(o.get('study_part')).startswith(('panel_', 'ctl_')), False)
    lb = corner(lines(f"{i}  1.20 m SLIDING PLUG   STUDY / PROTOTYPE", 'ghost: seated, dropped 0.08 m; orange: parked 1.30 m toward -az',
                      f"parked edge to bore {kin['parked_edge_to_bore_m']:+.2f} m; SP-12 room {kin['sp12_room_margin_m']:+.2f} m",
                      f"fixtures {kin['sp12_fixture_min_m']:+.2f} m; bodies {cs_['routine_pair']['plug_to_bodies_m']:+.2f} m (PASS >= 0.05)"), eye, mid, u, 6.4)
    st.camera(eye, mid, up=u, ortho=6.4); st.render(out/(names+'parked.png')); bpy.data.objects.remove(lb)
    # B. casualty transit: litter with straps centred on the aperture, partly through, rescuer above
    cc = next(p for p in row['rescue_occupants'] if p[1]['pose'] == 'supported_frame'); rr, cs = cc; hide_all()
    cpose = env['variants'][cs['variant']]['supported']; depth = 0.7; oc = dict(cs, shift_m=[0.0, 0.0]); oc['a_top_m'] = cs['a_top_m']-k_['frame_head_m']-depth; oc['zmax_m'] = max(v[2] for v in cpose['verts'])
    orr = dict(rr, shift_m=[0.0, 0.62])
    st.pose_and_place(rigs[rr['variant']][0], env['variants'][rr['variant']]['rescue'], orr, fit); show(rigs[rr['variant']], True)
    st.pose_and_place(rigs2[cs['variant']][0], cpose, oc, fit); show(rigs2[cs['variant']], True)
    fo = obj('Litter_R', frame_bm(fit, oc, cpose['verts'], k_, cs['theta_deg']), coll, 'frame', dict(study_part='litter'))
    so = obj('Straps_R', combine([hull_bm([st.world(fit, *c) for c in b.corners()]) for b in pl.straps(env['variants'][cs['variant']]['supported_frame'], cs['theta_deg'], (0.0, 0.0),
                                                                                                       cs['a_top_m']-depth, cs['zmax_m'], k_, pq['strap_tail_stowed_m'])]), coll, 'strap', dict(study_part='straps'))
    c = cs_['litter_frame']['transit']; cv = f"{cs['variant']}.stowed"
    lb = corner(lines(f"{i}  CASUALTY TRANSIT, plug parked   STUDY / PROTOTYPE", f"{cs['variant']} on the litter frame, strapped, centred in the aperture, {depth:.1f} m through",
                      f"bore {c[cv]['bore_clearance_m']:+.3f} m {c[cv]['bore_status']} (0.25 m loose tails {c[cv.replace('stowed', 'loose')]['bore_clearance_m']:+.3f} m)",
                      f"vertical insertion stops {c[cv]['insertion_limit_m']:.2f} m in (litter {c[cv]['body_length_m']:.2f} m): turn in SP-12 OPEN"), eye, mid, u, 6.4)
    st.camera(eye, mid, up=u, ortho=6.4); st.render(out/(names+'transit.png')); bpy.data.objects.remove(lb); bpy.data.objects.remove(fo); bpy.data.objects.remove(so)
    # C. the two-side valves and gauges from the section plane (clusters at +p / -p in profile), with the SP-12 operator
    hide_all(); routine(); k = op; h = env['variants'][k]['chamber']; so_ = ctl['sp12']['operator'][f'suited_{k}']; zmax = max(v[2] for v in h['verts']); zmin = min(v[2] for v in h['verts'])
    o = dict(theta_deg=so_['facing_deg'], shift_m=so_['station_chamber'][1:], a_top_m=so_['station_chamber'][0]+zmax-zmin, zmax_m=zmax)
    st.pose_and_place(rigs[k][0], h, o, fit); show(rigs[k], True); tog(shell, True); tog(lambda o: str(o.get('study_part')).startswith(('panel_', 'ctl_')), True)
    tog(lambda o: o.get('study_part') in ('plug_parked', 'plug_swept', 'plug_carriage', 'plug_rails'), False)
    mid3 = st.world(fit, 3.55, 0.3, 0.0); eye3 = mid3+w*12.0
    lb = corner(lines(f"{i}  EQUALIZATION VALVE (blue), GAUGE (white), RELEASE (red), both sides   STUDY / PROTOTYPE",
                      f"chamber: a cluster per crew position; reach margin >= {min(ctl['chamber']['reach_margin_m'].values()):+.2f} m (suited, unsuited, rescuers)",
                      f"SP-12: cluster on the chamber's outside wall, operator on the floor; reach >= {min(ctl['sp12']['reach_margin_m'].values()):+.3f} m",
                      f"SP-12 operator to the nearest fixture {ctl['sp12']['operator_clearance_m']:+.3f} m; chamber body gap {ctl['chamber']['body_gap_m']:+.2f} m"), eye3, mid3, u, 6.4)
    st.camera(eye3, mid3, up=u, ortho=6.4); st.render(out/(names+'valves.png')); bpy.data.objects.remove(lb)
    # C2. close-ups of the two clusters, the chamber side seen from the axis and the SP-12 side seen from outside
    hide_all(); tog(shell, False); a_v = ctl['chamber']['clusters'][0]['points']['valve'][0]; rho = ctl['chamber']['clusters'][0]['points']['valve'][1]
    mid5 = st.world(fit, a_v, rho, 0.0); eye5 = st.world(fit, a_v, 0.0, 0.0)+X*0.0
    lb = corner(lines(f"{i}  CHAMBER SIDE (crew {ctl['chamber']['clusters'][0]['for_crew']}): release (red), valve (blue), gauge (white)",
                      f"reach margins {min(v for kk, v in ctl['chamber']['reach_margin_m'].items() if 'suited_' + ctl['chamber']['clusters'][0]['for_crew'] in kk):+.2f} m or better; head to gauge {max(ctl['chamber']['head_to_gauge_m'].values()):.2f} m",
                      "a pull ring, a hand valve and a dial on a plate 0.06 m proud of the wall; no power"), eye5, mid5, u, 1.7)
    st.camera(eye5, mid5, up=u, ortho=1.7); st.render(out/(names+'valves_chamber.png')); bpy.data.objects.remove(lb)
    a_s = ctl['sp12']['points']['valve'][0]; rho_s = ctl['sp12']['points']['valve'][1]; mid6 = st.world(fit, a_s, rho_s, 0.0); eye6 = mid6+X*6.0
    lb = corner(lines(f"{i}  SP-12 SIDE: release (red), valve (blue), gauge (white), on the chamber's outside wall",
                      f"reach margin {min(ctl['sp12']['reach_margin_m'].values()):+.3f} m or better (suited and unsuited, both bodies)",
                      f"operator to the nearest fixture {ctl['sp12']['operator_clearance_m']:+.3f} m"), eye6, mid6, u, 1.7)
    st.camera(eye6, mid6, up=u, ortho=1.7); st.render(out/(names+'valves_sp12.png')); bpy.data.objects.remove(lb)
    # D. retention: from below, the seated leaf (ghost), dogs, keeper ledges, blocking pins, lever linkage and the reverse load path
    hide_all(); tog(lambda o: str(o.get('study_part')).startswith(('panel_', 'ctl_')) or o.get('study_part') in ('plug_parked', 'plug_swept', 'plug_carriage', 'plug_rails', 'plug_dropped'), False); tog(shell, False)
    mid4 = st.world(fit, 2.45, 0.0, 0.0); eye4 = mid4+(-u*5.0+w*3.2+X*1.2).normalized()*12.0
    lb = corner(lines(f"{i}  BIDIRECTIONAL RETENTION   STUDY / PROTOTYPE   DERIVED / DIAGNOSTIC",
                      f"reverse load: leaf outer d 1.30 m x 80 kPa = {ret['derived_reverse_kn']:.1f} kN bound (seal line {ret['seal_line_comparison_kn']:.1f} kN, comparison)",
                      f"{ret['geometry']['dog_count']} dogs (red) on keeper ledges (yellow), {ret['per_dog_kn']:.1f} kN each; cyan: load path",
                      "lever linkage (red rods) moves the dogs only; pins (red) block it"), eye4, mid4, X, 3.4)
    st.camera(eye4, mid4, up=X, ortho=3.4); st.render(out/(names+'retention.png')); bpy.data.objects.remove(lb)
    bpy.data.collections.remove(coll)


if __name__ == '__main__':
    main()
