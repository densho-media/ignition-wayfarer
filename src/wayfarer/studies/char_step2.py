"""CHAR-STEP2 (S&E 15_MODEL_INTERFACES!A130, owner answer 2026-10-11): the thrust hatch step as a REDESIGN STUDY (NONCANON).

The owner rejects the as-passed 2.9-3.6 cm thigh-in-frame contact, padded or not, and asks to compare a top-rung-to-sill transfer with a
frame-mounted handhold against a relocated / re-spaced step, keeping hand reach, fall arrest and the 1.5 g aft-down body envelope. Nothing
canonical moves: every option is disposable geometry built in memory on top of the saved vehicle, and every option is a route-hardware
change that needs owner approval.

On the actual MPFB rigs (instructor, newcomer; the fixtures test_a / test_b with --who) the transfer from the step ladder onto the sector
hatch sill with aft down (rings locked, +X up in the sector frame, the overhead a side wall) is posed as a short sequence:

  K0 lower rung   both balls of the feet on the rung below the top one (the as-built mannequin station)
  K1 top rung     both feet on the top rung, hands on the sector-side grips
  K2 hands        feet on the top rung, leaning in, hands moved to the forward grips (tube ladder stiles / study handholds)
  K3 hip over     trailing foot on the top rung, the lead boot over the frame face, hips rising toward the opening
  K4 sill         lead foot on the sill (the frame's clear bore), trailing foot still on the top rung, torso into the tube

Each keyframe searches a small grid of hip stand-off, hip drop and trunk lean and keeps the posture with the largest least clearance
(grips and footings must be reached). The posed body mesh is intersected with every vehicle mesh nearby: least clearance per body part
(hip, thigh, shank, boot, hand, arm, torso, head) to the hatch frame, the step, ladders, the fall-arrest rail, the leaf rails, the
overhead and the tube. Below STUDY_MARGIN = MARGINAL, below zero = FAIL (the owner rejects any collision; padding is not allowed). A hand
may sit CONTACT_TOL in the grip it holds and a boot in the rung or sill it stands on, and both may touch the surface the grip or footing is
mounted on. Hand reach: wrist-to-grip distance and the solver's shortfall; at least one hand must hold in every keyframe. Fall arrest: the
link an arrester on the tube's arrest rail would need to reach the chest ring, against the PROTOTYPE link of the elbow climber. Body
envelope: the centre of mass (segment-mass model) over the support base and the horizontal hand force that holds it, as a fraction of the
1.5 g body weight.

  /snap/bin/blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/studies/char_step2.py -- \
      [--who instructor newcomer] [--options A B1 B2 B3 C] [--size 640]
"""
import argparse
import json
import math
import os
from pathlib import Path
import sys
import time

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/components'), str(ROOT/'src/wayfarer/validation')]
import characters as ch
import human_entry as he
import human_system as hs
import human_fit as hf
from human import Solver
from spec import load

STUDY_MARGIN = 0.05      # study margin (owner: no collision, no padding); below it MARGINAL, below zero FAIL
CONTACT_TOL = 0.03       # a hand in the grip it holds, a boot in the rung or sill it stands on (as human_fit)
MOUNT_GAP = 0.08         # a surface this close to a grip or footing point is the surface it is mounted on (contact allowed there too)
NEAR = 2.2
G_LOAD = 1.5
SEGMENTS = dict(head=.081, trunk=.497, upperarm=.028, lowerarm=.016, hand=.006, thigh=.100, calf=.0465, foot=.0145)   # Dempster fractions
HANDHOLD_LEN = 0.30      # PROTOTYPE study handhold bar
HANDHOLD_STANDOFF = 0.045

GROUPS = (('arrest_rail', ('_Arrest_Rail',)), ('transfer_rail', ('STUDY_Transfer_Rail',)), ('stowage', ('Crew_Stowage_Upper', 'STUDY_Stowage')),
          ('frame', ('Sector_Hatch_Frame', 'Landing_Fit_Hatch_Mark')),
          ('step', ('Sector_Thrust_Step_', 'STUDY_Step_')), ('handhold', ('STUDY_Handhold', 'STUDY_Grab')),
          ('ladders', ('Sector_Ladder_', 'Crew_Tube_1_1_Ladder_')), ('leaf_rails', ('Sector_Hatch_Rail', 'Sector_Hatch_Leaf', 'STUDY_Hatch_Rail')),
          ('overhead', ('Interior_Overhead',)), ('tube', ('Crew_Tube_',)))
PARTS = ('hip', 'thigh', 'shank', 'boot', 'hand', 'arm', 'torso', 'head')

OPTIONS = {
    'A': dict(title='top-rung-to-sill transfer with frame-mounted handholds, step as built', standoff=None, heights=None, lateral=0.0, handholds=True),
    'B1': dict(title='step moved off the overhead: stand-off 0.16 -> 0.30 m, rungs as built', standoff=0.30, heights=None, lateral=0.0, handholds=False),
    'B2': dict(title='step re-spaced: three rungs 0.22/0.45/0.68 m above the floor, stand-off as built', standoff=None, heights=(0.22, 0.45, 0.68), lateral=0.0, handholds=False),
    'B3': dict(title='step moved and re-spaced: stand-off 0.30 m, three rungs 0.22/0.45/0.68 m', standoff=0.30, heights=(0.22, 0.45, 0.68), lateral=0.0, handholds=False),
    'C': dict(title='B3 step with the frame-mounted handholds', standoff=0.30, heights=(0.22, 0.45, 0.68), lateral=0.0, handholds=True),
    'B3R': dict(title='B3 redesign (STEP-004): leaf guide recessed, right-hand grab post, sector-side transfer rail, upper stowage recessed',
                standoff=0.30, heights=(0.22, 0.45, 0.68), lateral=0.0, handholds=False, redesign=True),
    'B3S': dict(title='SIM-027 (owner 2026-10-11 16:45): B3R + re-profiled tube deck band and ladder features near the sill, anchor layout from RAIL_SETS, single-hand sequence',
                standoff=0.30, heights=(0.22, 0.45, 0.68), lateral=0.0, handholds=False, redesign=True, sim027=True),
    'B3H': dict(title='owner 2026-10-13 (15!A171): B3S with the grab post, its foot and bracket removed; one relocated low-profile handgrip under the recessed upper stowage',
                standoff=0.30, heights=(0.22, 0.45, 0.68), lateral=0.0, handholds=False, redesign=True, sim027=True, handgrip=True),
    'B3HR': dict(title='B3H with the transfer rail lowered 0.02 m (z -1.62 -> -1.64, anchor layout T4): K4 thigh-to-rail exploration, owner limit link <= 0.206 m',
                 standoff=0.30, heights=(0.22, 0.45, 0.68), lateral=0.0, handholds=False, redesign=True, sim027=True, handgrip=True, rails='T4'),
    # owner 2026-10-13b (15!A180): alternate / recessed transfer-rail mounts on B3H, arrest link <= 0.206 m kept as the CURRENT STUDY LIMIT (hard filter).
    # B3H2 is the pick (layout T5 + far handgrip brackets); B3H2X the screen option (anchor layout from --rails, e.g. 'poly:x,y,z;...' for one continuous dog-legged rail).
    'B3H2': dict(title='owner 2026-10-13b (15!A180): B3H with the transfer rail dog-legged (lower part recessed to z -1.66 up to x -0.10, upper anchor end at z -1.62 from x 0.0; '
                       'layout T5) and the handgrip brackets moved to the deck-side end of the bar (no bracket in the arm path)',
                 standoff=0.30, heights=(0.22, 0.45, 0.68), lateral=0.0, handholds=False, redesign=True, sim027=True, handgrip=True, rails='T5', grip_brackets='far'),
    'B3H2X': dict(title='B3H2 screen: B3H with an alternate transfer-rail mount from --rails (handgrip mount from B3H_GRIP_BRACKETS / B3H_GRIP_INSET)',
                  standoff=0.30, heights=(0.22, 0.45, 0.68), lateral=0.0, handholds=False, redesign=True, sim027=True, handgrip=True),
}

# B3H replacement handgrip (owner 2026-10-13, S&E 15!A171; PROTOTYPE, disposable, a route-hardware change needing owner approval). A straight bar
# (handrail radius) with two short standoff brackets to the lower face of the recessed Crew_Stowage_Upper copy (x = STOW_X[0] + STOW_TRIM): it sits
# inside the volume the stowage recess freed (lowest point above the as-built stowage face x 0.60), outside the leaf slab and its guides, and
# 0.65 m or more from the hatch axis. Candidates: (name, axis 'y' | 'z', fixed (x, y|z), range along the axis); chosen by --grip-grid.
GRIP_GAP = 0.045                               # knuckle gap between the bar and the stowage face (as HANDHOLD_STANDOFF)
GRIP_LEN = 0.25
GRIP_BRACKET_MODE = os.environ.get('B3H_GRIP_BRACKETS', 'ends')    # B3H2: 'ends' (B3H) or 'far' (both brackets at the deck-side end of the bar)
GRIP_BRACKET_INSET = float(os.environ.get('B3H_GRIP_INSET', '0.0'))   # B3H2 (15!A180): handgrip brackets moved in from the bar ends by this much (0 = B3H)


def handgrip_candidates():
    """The documented B3H grid: bars along z (lateral) at y in {-2.58, -2.48, -2.38} and bars along y (fore-aft, y -2.60..-2.35), centre z in
    {-1.25, -1.10, -0.95, -0.80}; bar axis GRIP_GAP + radius below the recessed stowage face."""
    face = STOW_X[0]+STOW_TRIM; out = {}
    for zc in (-1.25, -1.10, -0.95, -0.80):
        for y in (-2.58, -2.48, -2.38):
            out[f'Uz_y{-y:.2f}_z{-zc:.2f}'] = dict(axis='z', face_x=face, y=y, z=(zc-GRIP_LEN/2, zc+GRIP_LEN/2))
        out[f'Uy_z{-zc:.2f}'] = dict(axis='y', face_x=face, y=(-2.60, -2.35), z=zc)
    for zc in (-1.10, -1.00):                                 # refinement (full body runs): the fore-aft bar moved off the overhead, away from the arm path
        for y0 in (-2.55, -2.50, -2.45):
            out[f'Uy_z{-zc:.2f}_y{-y0:.2f}'] = dict(axis='y', face_x=face, y=(y0, y0+GRIP_LEN), z=zc)
    return out


GRIP_PICK = os.environ.get('B3H_GRIP', 'Uy_z1.10_y2.55')     # the pick: coarse grid (reach, head) then full body runs (instructor, test_a K0-K3 arm to the brackets)

# B3R study proposals (all PROTOTYPE, sector frame, disposable; each is a route-hardware / structure change needing owner approval)
STOW_TRIM = float(os.environ.get('B3R_STOW', '0.15'))   # Crew_Stowage_Upper recessed: its lower face (x 0.60, toward the hatch) cut back to x 0.60 + STOW_TRIM; upper face x 1.60 kept (a box)
STOW_X = (0.60, 1.60)
LEAF_RAIL_SHIFT = (0.0, -0.033, 0.0)      # Sector_Hatch_Rail_1 (sill-side leaf guide) recessed 0.033 m toward the overhead (top flush with the frame seat)
LEAF_RAIL_MOVED = 'Sector_Hatch_Rail_1'
STOW_MOVED = 'Crew_Stowage_Upper'
XFER_RAIL_Y, XFER_RAIL_Z = (float(x) for x in os.environ.get('B3R_RAIL', '-2.66,-1.54').split(','))   # transfer rail axis: 0.24 m off the overhead, left of the boots, on the tube-rail side
XFER_RAIL_X = (-1.07, float(os.environ.get('B3R_XEND', '0.30')))               # from just below the top rung up to the leaf plane's edge region
GRAB_Y, GRAB_DZ, GRAB_TOP_X = -2.62, 0.12, -0.20   # right grab post: 0.28 m off the overhead, 0.12 m right of the step's right stile, top at x = -0.20
GRIP = 'post'

# SIM-027 (all PROTOTYPE, disposable copies in memory, route-hardware changes needing owner approval)
RAIL_SETS = {                                  # anchor layouts: (name, y, z, x0, x1) in the sector frame; the arrester uses the nearest rail point
    'T0': [('1', XFER_RAIL_Y, XFER_RAIL_Z, XFER_RAIL_X[0], XFER_RAIL_X[1])],       # the B3R rail
    'T4': [('1', -2.66, -1.64, -1.07, 0.15)],     # B3HR (2026-10-13): K4-only screen of z -1.64/-1.66/-1.68 and y -2.6725 (instructor, test_a, one_np): z -1.64 is the only one with thigh >= 0.05 and link <= 0.206
    'T5': [('1', 'poly', ((-1.07, -2.66, -1.66), (-0.10, -2.66, -1.66), (0.0, -2.66, -1.62), (0.15, -2.66, -1.62)))],   # B3H2 (15!A180): one continuous rail, dog-legged:
                                                  # the lower part (where the trailing thigh passes at K4) recessed 0.04 m to z -1.66, the upper end (where the chest link anchors) at z -1.62;
                                                  # screened against T6 (lower part z -1.68: test_b link 0.213 > 0.206, rejected) and z -1.64 straight to x 0.25 (links 0.207-0.211, rejected)
    'T6': [('1', 'poly', ((-1.07, -2.66, -1.68), (-0.10, -2.66, -1.68), (0.0, -2.66, -1.62), (0.15, -2.66, -1.62)))],
    'T3': [('1', -2.66, -1.62, -1.07, 0.15)],     # SIM-027 pick: z -1.62 keeps the worst case over all rigs/variants/keyframes highest (rail grid + refinement runs); the rail MUST start at x <= -0.92: its bracket
                                                  # crosses the leaf plane (y -2.82..-2.74) and the leaf radius is 0.85 m (a bracket at x = -0.20 sits inside the swept leaf: leaf sweep FAIL)
    'T2': [('1', -2.66, -1.62, -0.20, 0.15)],     # SIM-027 pick (rail grid, then x0/z refinement over all keyframes with the re-profiled band): link <= 0.206 m, thigh/boot best; a short anchor, not a climbing rail
    'T1': [('1', -2.66, -1.58, -1.07, 0.15)],     # SIM-027 pick from a rail grid (y -2.72..-2.60, z -1.70..-1.46, x end -0.30..0.30; instructor, test_a, K3/K4): link <= 0.206 m and thigh >= 0.05 m;
                                                  # y stays >= -2.6725 so the rail clears the swept leaf (y -2.82..-2.74) by 0.05 m
}
BAND_OBJ = 'Crew_Tube_1_1_Fit_Deck_Band'       # tube deck band: its sill-end cut back by BAND_CUT (the lead boot passes over it at K4)
BAND_CUT = float(os.environ.get('SIM_BAND_CUT', '0.40'))
BAND_SEAT_Y = -3.09                            # the band's sill-side end in the sector frame (as built)
TUBE_LADDER_OBJS = ('Crew_Tube_1_1_Ladder_Rungs', 'Crew_Tube_1_1_Ladder_Brackets')   # rungs and brackets nearest the sill removed (stiles stay)
TUBE_LADDER_CUT = float(os.environ.get('SIM_TUBE_CUT', '0.40'))                       # metres of tube ladder from the sill end (y = -2.89)
ARREST_RAIL_OBJS = ('Crew_Tube_1_1_Arrest_Rail', 'Crew_Tube_1_1_Arrest_Rail_Brackets')   # tube arrest rail: sill end trimmed (owner: reroute the arrest rail), the transfer rail covers the sill
ARREST_RAIL_CUT = float(os.environ.get('SIM_ARREST_CUT', '0.15'))
LAND_LADDER_OBJS = ('Sector_Ladder_Rungs', 'Sector_Ladder_Brackets')                   # landing ladder: the top part (nearest the overhead) removed
LAND_LADDER_CUT_Y = float(os.environ.get('SIM_LAND_CUT_Y', '-2.40'))                  # faces wholly above (toward the overhead) this y are dropped


def group_of(name):
    return next((g for g, keys in GROUPS if any(k in name for k in keys)), 'other')


def part_of(bone):
    if bone.startswith('thigh'): return 'thigh'
    if bone.startswith('calf'): return 'shank'
    if bone.startswith(('foot', 'ball')): return 'boot'
    if bone.startswith(('upperarm', 'lowerarm')): return 'arm'
    if bone.startswith(('hand', 'thumb', 'index', 'middle', 'ring', 'pinky')): return 'hand'
    if bone.startswith(('head', 'neck')): return 'head'
    if bone == 'pelvis': return 'hip'
    return 'torso'


class Sector:
    """Sector frame (he.landing) <-> vehicle frame at the index pose."""
    def __init__(self, s):
        _, _, point, vector = he.sector_frame(s)
        M = Matrix([list(vector((1, 0, 0))), list(vector((0, 1, 0))), list(vector((0, 0, 1)))]).transposed().to_4x4()
        M.translation = Vector(point((0, 0, 0))); self.M, self.Mi = M, M.inverted()
    def p(self, q): return self.M @ Vector(q)
    def d(self, q): return (self.M.to_3x3() @ Vector(q)).normalized()
    def back(self, q): return self.Mi @ Vector(q)


def step_geometry(s, opt):
    """The step ladder of an option in the sector frame (as he.thrust_step, with a changed stand-off and rung heights)."""
    h = s['human_entry']; S = he.thrust_step(s); L = he.landing(s); r = h['handrail_radius_m']
    y = L['ceiling']+opt['standoff'] if opt['standoff'] else S['y']
    rungs = [S['floor']+x for x in opt['heights']] if opt['heights'] else list(S['rungs'])
    zc = S['z']+opt['lateral']; w = h['spoke_ladder_width_m']/2
    return dict(floor=S['floor'], y=y, z=zc, stile_z=(zc-w, zc+w), rungs=rungs, x=(S['x'][0], max(S['x'][1], rungs[-1]+r+.0075)), r=r,
                ceiling=L['ceiling'], built=not (opt['standoff'] or opt['heights'] or opt['lateral']))


def rod(name, a, b, radius, coll, kind='study'):
    me = bpy.data.meshes.new(name); bm = bmesh.new(); a, b = Vector(a), Vector(b); d = b-a
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=radius, radius2=radius, depth=d.length)
    bm.to_mesh(me); bm.free(); o = bpy.data.objects.new(name, me); o['kind'] = kind
    o.matrix_world = Matrix.Translation((a+b)/2) @ Vector((0, 0, 1)).rotation_difference(d.normalized()).to_matrix().to_4x4()
    coll.objects.link(o); return o


def study_copy(sf, src, name, shift_sector, coll, fx=None):
    """A disposable copy of an evaluated vehicle object, moved by shift_sector (sector frame); the original is hidden and excluded by the caller."""
    dg = bpy.context.evaluated_depsgraph_get(); sh = sf.M.to_3x3() @ Vector(shift_sector)
    for inst in dg.object_instances:
        o = inst.object
        if o.name == src and o.type == 'MESH':
            mw = inst.matrix_world.copy(); me = bpy.data.meshes.new(name)
            me.from_pydata([(lambda q: sf.p(fx(sf.back(q))) if fx else q)((mw @ v.co)+sh) for v in o.data.vertices], [], [tuple(p.vertices) for p in o.data.polygons]); me.update()
            n = bpy.data.objects.new(name, me); n['kind'] = 'study'; coll.objects.link(n)
            for m in o.data.materials:
                me.materials.append(m)
            return n
    raise KeyError(src)


def study_clip(sf, src, name, keep_y_above, y_cut, coll):
    """A disposable copy of an evaluated vehicle object clipped by the sector-frame plane y = y_cut (Sutherland-Hodgman per face; long strips are cut,
    not dropped): keeps y > y_cut when keep_y_above, else y < y_cut. Returns (object, faces before, faces after)."""
    dg = bpy.context.evaluated_depsgraph_get()
    for inst in dg.object_instances:
        o = inst.object
        if o.name == src and o.type == 'MESH':
            mw = inst.matrix_world.copy(); vs = [sf.back(mw @ v.co) for v in o.data.vertices]; sg = 1.0 if keep_y_above else -1.0
            pts, faces = [], []
            for p in o.data.polygons:
                poly = [vs[i] for i in p.vertices]; out = []
                for a, b in zip(poly, poly[1:]+poly[:1]):
                    da, db = sg*(a[1]-y_cut), sg*(b[1]-y_cut)
                    if da >= 0: out.append(a)
                    if (da >= 0) != (db >= 0):
                        k = da/(da-db); out.append(a+(b-a)*k)
                if len(out) >= 3:
                    faces.append(tuple(range(len(pts), len(pts)+len(out)))); pts += [tuple(sf.p(q)) for q in out]
            me = bpy.data.meshes.new(name); me.from_pydata(pts, [], faces); me.update()
            n = bpy.data.objects.new(name, me); n['kind'] = 'study'; coll.objects.link(n)
            for m in o.data.materials:
                me.materials.append(m)
            return n, len(o.data.polygons), len(faces)
    raise KeyError(src)


def build_sim027_profile(sf, coll):
    """Re-profiled disposable copies: tube deck band cut back at the sill, nearest tube-ladder rungs/brackets removed, top of the landing-ladder rungs/brackets removed."""
    out, moved, meta = [], set(), {}
    o, n0, n1 = study_clip(sf, BAND_OBJ, 'STUDY_Fit_Deck_Band_cut', False, BAND_SEAT_Y-BAND_CUT, coll)
    out.append(o); moved.add(BAND_OBJ); meta['deck_band'] = dict(object=BAND_OBJ, sill_end_cut_back_m=BAND_CUT, faces_before_after=[n0, n1])
    for src in TUBE_LADDER_OBJS:
        o, n0, n1 = study_clip(sf, src, 'STUDY_'+src+'_cut', False, -2.8875-TUBE_LADDER_CUT, coll)
        out.append(o); moved.add(src); meta[src] = dict(removed_from_sill_end_m=TUBE_LADDER_CUT, faces_before_after=[n0, n1])
    for src in ARREST_RAIL_OBJS:
        o, n0, n1 = study_clip(sf, src, 'STUDY_'+src+'_cut', False, -2.8875-ARREST_RAIL_CUT, coll)
        out.append(o); moved.add(src); meta[src] = dict(sill_end_trimmed_m=ARREST_RAIL_CUT, faces_before_after=[n0, n1])
    for src in LAND_LADDER_OBJS:
        o, n0, n1 = study_clip(sf, src, 'STUDY_'+src+'_cut', True, LAND_LADDER_CUT_Y, coll)
        out.append(o); moved.add(src); meta[src] = dict(removed_above_y_m=LAND_LADDER_CUT_Y, faces_before_after=[n0, n1])
    return out, moved, meta


def seg_dist(p, a, b):
    """Distance of point p from the segment a-b (tuples of equal length)."""
    u = [y-x for x, y in zip(a, b)]; w = [y-x for x, y in zip(a, p)]; uu = sum(x*x for x in u) or 1e-12
    t = max(0.0, min(1.0, sum(x*y for x, y in zip(u, w))/uu)); return math.dist(p, [x+t*y for x, y in zip(a, u)])


def build_handgrip(sf, r, spec, coll, axis_xz, mode=None, inset=None):
    """B3H: the replacement handgrip bar and its two standoff brackets to the recessed stowage face (sector frame). Returns (objects, metadata)."""
    xa = spec['face_x']-GRIP_GAP-r
    if spec['axis'] == 'z':
        a, b = (xa, spec['y'], spec['z'][0]), (xa, spec['y'], spec['z'][1])
    else:
        a, b = (xa, spec['y'][0], spec['z']), (xa, spec['y'][1], spec['z'])
    out = [rod('STUDY_Grab_Handgrip', sf.p(a), sf.p(b), r, coll)]
    mode = mode or GRIP_BRACKET_MODE; inset = GRIP_BRACKET_INSET if inset is None else inset
    k = inset/GRIP_LEN                        # B3H2 alternate mount: the standoff brackets moved in from the bar ends (the ends cantilever)
    ins = (tuple(p+(q-p)*k for p, q in zip(a, b)), tuple(q+(p-q)*k for p, q in zip(a, b)))
    if mode == 'far':                         # both brackets at the deck-side end (b): the overhead-side end cantilevers, no bracket in the arm path
        ins = (tuple(q+(p-q)*0.06/GRIP_LEN for p, q in zip(a, b)), tuple(b))
    for i, e in enumerate(ins, 1):
        out.append(rod(f'STUDY_Grab_Handgrip_bracket_{i}', sf.p(e), sf.p((spec['face_x'], e[1], e[2])), r*.7, coll))
    return out, dict(a_sector=[round(x, 3) for x in a], b_sector=[round(x, 3) for x in b], radius_m=r, axis=spec['axis'], length_m=GRIP_LEN,
                     knuckle_gap_m=GRIP_GAP, mount_face_x_m=round(spec['face_x'], 3), bracket_inset_from_bar_ends_m=inset, bracket_mode=mode,
                     lowest_point_x_m=round(xa-r, 3), as_built_stowage_face_x_m=STOW_X[0],
                     hatch_axis_distance_to_surface_m=round(seg_dist(axis_xz, (a[0], a[2]), (b[0], b[2]))-r, 3),
                     note='low-profile bar under the recessed Crew_Stowage_Upper copy, inside the volume the recess freed (protrudes nothing past the as-built stowage face); '
                          'mount load path into the stowage structure, pressure boundary and injury robustness need an engineering check')


def rail_points(rl):
    """(name, points) of a RAIL_SETS entry: (name, y, z, x0, x1) is a straight rail along x; (name, 'poly', points) a continuous polyline (B3H2)."""
    if rl[1] == 'poly':
        return rl[0], [tuple(q) for q in rl[2]]
    nm, ry, rz, rx0, rx1 = rl; return nm, [(rx0, ry, rz), (rx1, ry, rz)]


def parse_rails(rk):
    """--rails: a RAIL_SETS key, 'y,z,x0,x1', or 'poly:x,y,z;x,y,z;...' (one continuous polyline rail)."""
    if rk in RAIL_SETS:
        return RAIL_SETS[rk]
    if rk.startswith('poly:'):
        return [('1', 'poly', tuple(tuple(float(v) for v in q.split(',')) for q in rk[5:].split(';')))]
    return [('1',)+tuple(float(x) for x in rk.split(','))]


def build_redesign(s, sf, g, coll, rails=None, post=True, grip=None, grip_mount=None):
    """The B3R hardware: moved leaf guide and stowage (copies), right grab post (or the B3H handgrip), sector-side transfer rail. Returns (objects, excluded originals, metadata)."""
    r = s['human_entry']['handrail_radius_m']; L = he.landing(s); out = []
    out.append(study_copy(sf, LEAF_RAIL_MOVED, 'STUDY_Hatch_Rail_1_recessed', LEAF_RAIL_SHIFT, coll))
    k = (STOW_X[1]-STOW_X[0]-STOW_TRIM)/(STOW_X[1]-STOW_X[0])      # scale x about the upper face: the lower face moves from STOW_X[0] to STOW_X[0]+STOW_TRIM
    out.append(study_copy(sf, STOW_MOVED, 'STUDY_Stowage_Upper_recessed', (0, 0, 0), coll, fx=lambda q: (STOW_X[1]-(STOW_X[1]-q[0])*k, q[1], q[2])))
    top = g['rungs'][-1]; zr = g['stile_z'][1]+GRAB_DZ
    if post:
        out.append(rod('STUDY_Grab_Post_right', sf.p((top, GRAB_Y, zr)), sf.p((GRAB_TOP_X, GRAB_Y, zr)), r, coll))
        out.append(rod('STUDY_Grab_Post_foot', sf.p((top, GRAB_Y, g['stile_z'][1])), sf.p((top, GRAB_Y, zr)), r, coll))
        out.append(rod('STUDY_Grab_Post_bracket', sf.p((top, GRAB_Y, g['stile_z'][1])), sf.p((top, g['ceiling'], g['stile_z'][1])), r*.7, coll))
    grip_meta = None
    if grip:
        objs, grip_meta = build_handgrip(sf, r, grip, coll, (L['x'], L['z']), *(grip_mount or (None, None))); out += objs
    rails = rails or [('1', XFER_RAIL_Y, XFER_RAIL_Z, XFER_RAIL_X[0], XFER_RAIL_X[1])]; rail_meta = []
    for rl in rails:
        nm, pts = rail_points(rl)
        for i, (a, b) in enumerate(zip(pts, pts[1:])):          # one continuous rail: straight pieces of a polyline (B3H2), one bracket at its lower end
            out.append(rod(f'STUDY_Transfer_Rail_{nm}' + (f'_s{i}' if i else ''), sf.p(a), sf.p(b), r, coll))
        a = pts[0]; out.append(rod(f'STUDY_Transfer_Rail_Bracket_{nm}', sf.p(a), sf.p((a[0], L['ceiling'], a[2])), r*.7, coll))
        rail_meta.append(dict(name=f'STUDY_Transfer_Rail_{nm}', a_sector=[round(x, 3) for x in pts[0]], b_sector=[round(x, 3) for x in pts[-1]],
                              points_sector=[[round(x, 3) for x in q] for q in pts]))
    a, b = rail_points(rails[0])[1][0], rail_points(rails[0])[1][-1]
    meta = dict(
        leaf_guide=dict(object=LEAF_RAIL_MOVED, shift_sector_m=list(LEAF_RAIL_SHIFT), note='recessed toward the overhead; leaf engagement and the guide load path need an engineering check'),
        stowage=dict(object=STOW_MOVED, lower_face_x_from_to_m=[STOW_X[0], round(STOW_X[0]+STOW_TRIM, 3)], upper_face_x_m=STOW_X[1], volume_fraction_kept=round(1-STOW_TRIM/(STOW_X[1]-STOW_X[0]), 3), note='recessed (lower face cut back, y/z extent unchanged); structural and pressure-boundary load re-evaluation required before any move'),
        grab_post=dict(a_sector=[round(x, 3) for x in (top, GRAB_Y, zr)], b_sector=[round(x, 3) for x in (GRAB_TOP_X, GRAB_Y, zr)], radius_m=r,
                       note='cantilevered from the step top rung / right stile bracket; load path needs an engineering check') if post else
                  dict(removed=True, note='owner 2026-10-13 (15!A171): grab post, foot and bracket removed from the candidate'),
        handgrip=grip_meta,
        transfer_rail=dict(a_sector=[round(x, 3) for x in a], b_sector=[round(x, 3) for x in b], radius_m=r, bracket='one end bracket to the overhead at x = %.2f' % a[0],
                           note='cantilevered; sector-side rail overlapping the tube arrest rail (end at sector x 0.007, y -2.888, z -1.702); cannot pierce the leaf plane'),
        transfer_rails=rail_meta)
    return out, {LEAF_RAIL_MOVED, STOW_MOVED}, meta


def opening_check(s, sf, objs):
    """Hatch clear opening: the frame bore (clear radius) is untouched; for every added or moved study object, the distance of its vertices from the
    hatch axis, split by depth: inside the frame/leaf slab, and on the sector side (approach path). Also the leaf's travel envelope."""
    L = he.landing(s); rows = {}
    for o in objs:
        pts = [o.matrix_world @ v.co for v in o.data.vertices]; vs = [sf.back(p) for p in pts]
        for e in o.data.edges:                                # dense: long boxes have vertices only at their ends
            a, b = pts[e.vertices[0]], pts[e.vertices[1]]; n = max(1, int((b-a).length/.01))
            vs += [sf.back(a+(b-a)*(i/n)) for i in range(1, n)]
        def r_ax(v): return math.hypot(v[0]-L['x'], v[2]-L['z'])
        slab = [r_ax(v) for v in vs if L['frame_top'] <= v[1] <= L['seat']]
        front = [r_ax(v) for v in vs if v[1] > L['seat']]
        leaf = [v for v in vs if L['leaf_closed'][0] <= v[1] <= L['leaf_closed'][1]+.0 and r_ax(v) < L['leaf_r'] + .0]
        rows[o.name] = dict(min_axis_distance_in_frame_slab_m=round(min(slab), 3) if slab else None,
                            intrudes_clear_bore=bool(slab and min(slab) < L['clear_r']-1e-6),
                            min_axis_distance_sector_side_m=round(min(front), 3) if front else None,
                            in_leaf_slab_over_leaf_radius=bool(leaf))
    return dict(clear_radius_m=L['clear_r'], frame_outer_radius_m=L['frame_r'], leaf_radius_m=L['leaf_r'], leaf_slab_y=[round(x, 3) for x in L['leaf_closed']],
                frame_object='Sector_Hatch_Frame (unmodified)', objects=rows)


def build_step(sf, g, coll):
    """Disposable study step (stiles, rungs, brackets to the overhead), as the generator draws it, in memory."""
    out = []
    for j, zs in enumerate(g['stile_z'], 1):
        out.append(rod(f'STUDY_Step_Stile_{j}', sf.p((g['x'][0], g['y'], zs)), sf.p((g['x'][1], g['y'], zs)), g['r'], coll))
    for i, x in enumerate(g['rungs'], 1):
        out.append(rod(f'STUDY_Step_Rung_{i}', sf.p((x, g['y'], g['stile_z'][0])), sf.p((x, g['y'], g['stile_z'][1])), g['r'], coll))
    for x in (g['x'][0]+.05, g['x'][1]-.05):
        for zs in g['stile_z']:
            out.append(rod(f'STUDY_Step_Bracket_{len(out)}', sf.p((x, g['y']-g['r'], zs)), sf.p((x, g['ceiling'], zs)), g['r']*.7, coll))
    return out


def handhold_sites(s):
    """Candidate frame-mounted handholds in the sector frame: bars tangent to the frame ring on its sector face (radius mid-frame,
    HANDHOLD_STANDOFF proud of the face) and bars on the clear bore along the hatch axis (HANDHOLD_STANDOFF inside the bore), every 10 deg;
    the lower 120 deg (the sill and the leg path) stay free."""
    L = he.landing(s); r = s['human_entry']['handrail_radius_m']; out = []
    face_y = L['seat']+HANDHOLD_STANDOFF+r; rm = (L['clear_r']+L['frame_r'])/2; rb = L['clear_r']-HANDHOLD_STANDOFF-r
    for deg in range(-120, 121, 10):                      # from the top (+X), positive toward +Z (the body's right)
        a = math.radians(deg); c, sn = math.cos(a), math.sin(a)
        p = (L['x']+rm*c, face_y, L['z']+rm*sn); t = (-sn, 0.0, c)
        out.append(dict(kind='face', deg=deg, centre=p, a=tuple(p[i]-t[i]*HANDHOLD_LEN/2 for i in range(3)), b=tuple(p[i]+t[i]*HANDHOLD_LEN/2 for i in range(3))))
        q = (L['x']+rb*c, L['seat']-.11, L['z']+rb*sn)
        out.append(dict(kind='bore', deg=deg, centre=q, a=(q[0], L['seat']-.02, q[2]), b=(q[0], L['frame_top']+.02, q[2])))
    return out


def trees_near(centre, exclude):
    dg = bpy.context.evaluated_depsgraph_get(); out = []
    for inst in dg.object_instances:
        o = inst.object
        if o.type != 'MESH' or o.name in exclude or o.get('kind') in ('scale_reference', 'camera') or o.name.startswith(('Human_', 'CHAR_')):
            continue
        mw = inst.matrix_world.copy(); cs = [mw @ Vector(c) for c in o.bound_box]
        lo = Vector([min(c[i] for c in cs) for i in range(3)]); hi = Vector([max(c[i] for c in cs) for i in range(3)])
        if Vector([max(lo[i]-centre[i], 0, centre[i]-hi[i]) for i in range(3)]).length > NEAR or not len(o.data.polygons):
            continue
        out.append((o.name, group_of(o.name), BVHTree.FromPolygons([mw @ v.co for v in o.data.vertices], [tuple(p.vertices) for p in o.data.polygons])))
    return out


class Body:
    def __init__(self, who, coll):
        src = ROOT/'assets/characters'/f'WF_CHAR_HUMAN_{who.upper()}.blend'          # read only, appended in memory
        with bpy.data.libraries.load(str(src), link=False) as (data_from, dst):
            dst.objects = [n for n in data_from.objects if n.startswith(f'CHAR_{who.upper()}')]
        for o in dst.objects:
            coll.objects.link(o)
        rig = bpy.data.objects[f'CHAR_{who.upper()}']; rig.animation_data_create(); rig.animation_data.action = None
        for tr in rig.animation_data.nla_tracks:
            tr.mute = True
        b = rig.data.bones; self.H = max(v.co.z for o in rig.children if o.type == 'MESH' for v in o.data.vertices)
        self.bones = dict(hip=b['thigh_l'].head_local.z, ankle=b['foot_l'].head_local.z, ball=abs(b['ball_l'].head_local.y-b['foot_l'].head_local.y))
        self.P = hs.proportions({x.name: (tuple(x.head_local), tuple(x.tail_local)) for x in b}, self.H)
        self.rig, self.who = rig, who
        self.body = next(o for o in rig.children if o.name.endswith('_Body'))
        names = {g.index: g.name for g in self.body.vertex_groups}; bones = set(b.keys()); self.lab = []
        for v in self.body.data.vertices:
            gs = [x for x in v.groups if names.get(x.group) in bones]
            self.lab.append(part_of(names[max(gs, key=lambda x: x.weight).group]) if gs else 'torso')
        saved = dict(ch.P); ch.P.update(self.P)
        try:
            self.solver = Solver(rig, hs.rest(self.H))
        finally:
            ch.P.clear(); ch.P.update(saved)
        self.arm = (self.P['upper_arm']+self.P['forearm'])*self.H

    def mesh(self):
        dg = bpy.context.evaluated_depsgraph_get(); e = self.body.evaluated_get(dg); m = e.to_mesh(); mw = self.body.matrix_world
        vs = [mw @ v.co for v in m.vertices]; fs = [tuple(p.vertices) for p in m.polygons]; e.to_mesh_clear(); return vs, fs


def measure(body, trees):
    """(part, object) -> least clearance (negative: penetration depth, as human_fit), over the posed body surface."""
    vs, fs = body.mesh(); lab = body.lab; bt = BVHTree.FromPolygons(vs, fs); out = {}
    for name, grp, t in trees:
        pen, dist = {}, {}
        for bf, _ in bt.overlap(t):
            for i in fs[bf]:
                hit = t.find_nearest(vs[i], .3); d = hit[3] if hit[0] is not None else 0.0
                pen[lab[i]] = max(pen.get(lab[i], 0.0), d)
        for i in range(0, len(vs), 2):
            hit = t.find_nearest(vs[i], .6)
            if hit[0] is not None and hit[3] < dist.get(lab[i], 9.0):
                dist[lab[i]] = hit[3]
        for part in set(pen) | set(dist):
            out[(part, name)] = -pen[part] if part in pen else dist[part]
    return out


def com(joints):
    J = {k: Vector(v) for k, v in joints.items()}; m, tot = Vector(), 0.0
    def add(p, w):
        nonlocal m, tot; m += p*w; tot += w
    add(J['head']+(J['head']-J['neck_01'])*.6, SEGMENTS['head']); add((J['pelvis']+J['neck_01'])/2, SEGMENTS['trunk'])
    for s in 'lr':
        add((J[f'upperarm_{s}']+J[f'lowerarm_{s}'])/2, SEGMENTS['upperarm']); add((J[f'lowerarm_{s}']+J[f'hand_{s}'])/2, SEGMENTS['lowerarm'])
        add(J[f'hand_{s}'], SEGMENTS['hand']); add((J[f'thigh_{s}']+J[f'calf_{s}'])/2, SEGMENTS['thigh'])
        add((J[f'calf_{s}']+J[f'foot_{s}'])/2, SEGMENTS['calf']); add((J[f'foot_{s}']+J[f'ball_{s}'])/2, SEGMENTS['foot'])
    return m/tot


class Study:
    def __init__(self, s, sf, body, trees, grips, step):
        self.s, self.sf, self.b, self.trees, self.grips, self.g = s, sf, body, trees, grips, step
        self.L = he.landing(s); self.r = s['human_entry']['handrail_radius_m']
        self.tree = {n: t for n, _, t in trees}
        self.rail = [t for n, g, t in trees if g == 'arrest_rail' and 'Bracket' not in n]
        self.rail_xfer = [t for n, g, t in trees if g == 'transfer_rail' and 'Bracket' not in n]
        self.link_weight = 0.0                                # B3R: the arrester link above the PROTOTYPE link costs score (a design gate, like reach)
        self.link = he.elbow_climber(s)['link_m']; self.sleeve = s['human_entry']['spoke_arrest_rail_radius_m']+.015

    # Sector-frame helpers. Up +X (aft down), the body faces the overhead (-Y), its right is +Z.
    def sill_point(self, z, y):
        L = self.L; return (L['x']-math.sqrt(L['clear_r']**2-(z-L['z'])**2), y, z)

    def ankle_for(self, contact):
        """Ankle target for the ball of the foot on a contact point (rung top or sill), toes toward the overhead."""
        b = self.b.bones; return (contact[0]+b['ankle'], contact[1]+b['ball'], contact[2])

    def grip_point(self, name, shoulder_v):
        hit = self.tree[name].find_nearest(shoulder_v)
        return hit[0]

    def pose(self, hip, lean, feet, hand_sets):
        """hip (sector), lean (deg, + toward the overhead), feet {side: contact (sector)}, hand_sets {side: [grip object names]}.
        Each hand takes the reachable grip in its set nearest its shoulder; none reachable: the hand hangs free."""
        sf, b = self.sf, self.b; up, fwd = sf.d((1, 0, 0)), sf.d((0, -1, 0)); H = b.H; self.free = {}
        pose = dict(ch.STAND, trunk=lean, head=-.5*lean)
        saved = dict(ch.P); ch.P.update(b.P)
        try:
            j0 = ch.skeleton(hs.figure(H), pose, tuple(sf.p(hip)), tuple(up), tuple(fwd))
            hands, held = {}, {}
            for side, names in hand_sets.items():
                sh = Vector(j0[f'shoulder_{side}']); best = None
                for n in names:
                    if n not in self.tree:
                        continue
                    gp = self.grip_point(n, sh); d = (gp-sh).length
                    if best is None or d < best[0]:
                        best = (d, n, gp)
                if best and best[0] <= b.arm*1.02:
                    pole = tuple(-fwd*.4-up); hands[side] = (tuple(best[2]), pole); held[side] = (best[1], best[2], best[0])
                elif best:
                    self.free[side] = (best[1], best[2], best[0]-b.arm)
            j = ch.skeleton(hs.figure(H), pose, tuple(sf.p(hip)), tuple(up), tuple(fwd), hands=hands or None)
            ank = {side: tuple(sf.p(self.ankle_for(c))) for side, c in feet.items()}
            j = hs.legs_to(j, H, ank, tuple(fwd), tuple(up))
            sole = sum((sf.p(c) for c in feet.values()), Vector())/len(feet)
            fr = hs.frame_of(j, tuple(sole), ())
        finally:
            ch.P.clear(); ch.P.update(saved)
        return fr, dict(up=tuple(up), forward=tuple(fwd)), held

    def evaluate(self, hip, lean, feet, hand_sets, footing):
        """Pose, measure and classify. footing {side: object names a boot may stand on}."""
        fr, info, held = self.pose(hip, lean, feet, hand_sets)
        joints, short = hf.place(self.b.rig, self.b.solver, fr, info['up'], info['forward'])
        cl = measure(self.b, self.trees)
        allowed = {}                                          # part -> set of objects it may touch (<= CONTACT_TOL)
        for side, (n, gp, _) in held.items():
            allowed.setdefault('hand', set()).add(n); allowed.setdefault('arm', set()).add(n)     # the forearm at its own grip, as human_fit
            allowed['hand'] |= {m for m, _, t in self.trees if (lambda h: h[0] is not None and h[3] < MOUNT_GAP)(t.find_nearest(gp, MOUNT_GAP))}
        for side, c in feet.items():
            cp = self.sf.p(c); allowed.setdefault('boot', set()).update(footing[side])
            if footing[side]:                                 # an airborne boot touches nothing
                allowed['boot'] |= {m for m, _, t in self.trees if (lambda h: h[0] is not None and h[3] < MOUNT_GAP)(t.find_nearest(cp, MOUNT_GAP))}
        parts, by_group = {}, {}
        for (part, name), c in cl.items():
            if not (name in allowed.get(part, ()) and c >= -CONTACT_TOL):
                k = (part, group_of(name)); by_group[k] = min(by_group.get(k, 9.0), c)
            ok = name in allowed.get(part, ()) and c >= -CONTACT_TOL
            key = 'contact' if ok else 'free'
            cur = parts.setdefault(part, {}).get(key)
            if cur is None or c < cur[0]:
                parts[part][key] = (c, name)
        least = min([v['free'][0] for v in parts.values() if 'free' in v] or [9.0])
        reach = {}
        for side in ('left', 'right'):
            w = Vector(joints[f'hand_{side[0]}'])
            if side in held:
                n, gp, d0 = held[side]; reach[side] = dict(grip=n, grip_point_sector=[round(x, 3) for x in self.sf.back(gp)],
                                                           shoulder_to_grip_m=round(d0, 3), wrist_to_grip_m=round((w-gp).length, 3),
                                                           solver_short_m=round(short.get(f'arm_{side[0]}', 0.0), 3))
            elif side in self.free:
                n, gp, sh = self.free[side]
                reach[side] = dict(grip=None, nearest_grip=n, nearest_grip_point_sector=[round(x, 3) for x in self.sf.back(gp)], beyond_arm_reach_m=round(sh, 3))
            else:
                reach[side] = dict(grip=None)
        legs_short = max(short.get('leg_l', 0.0), short.get('leg_r', 0.0))
        holding = [k for k, v in reach.items() if v.get('grip') and v['wrist_to_grip_m'] <= CONTACT_TOL]
        # Fall arrest: an arrester on the tube's arrest rail, the link to the chest ring (0.72 H, 0.13 m forward of the body axis).
        chest = Vector(joints['spine_03'])+Vector(info['forward'])*.13
        hit_tube = min((t.find_nearest(chest) for t in self.rail), key=lambda h: h[3]) if self.rail else None
        hit_xfer = min((t.find_nearest(chest) for t in self.rail_xfer), key=lambda h: h[3]) if self.rail_xfer else None
        rail = min([h for h in (hit_tube, hit_xfer) if h is not None], key=lambda h: h[3], default=None)
        link_need = rail[3]-self.sleeve if rail else None
        link_tube = hit_tube[3]-self.sleeve if hit_tube else None; link_xfer = hit_xfer[3]-self.sleeve if hit_xfer else None
        # Body envelope: the centre of mass over the feet, the horizontal hand force for moment balance about the footing.
        c = com(joints); U = Vector(info['up']); Fw = Vector(info['forward'])
        balls = [Vector(joints[f'ball_{x[0]}']) for x in feet]; base = sum(balls, Vector())/len(balls)
        off = (c-base); off_h = off-U*off.dot(U); toward = off_h.dot(Fw)
        hands_h = [Vector(joints[f'hand_{x[0]}']) for x in holding]
        lever = (sum(hands_h, Vector())/len(hands_h)-base).dot(U) if hands_h else 0.0
        frac = abs(toward)/lever if lever > .2 else None
        score = least-3*sum(max(0.0, short.get(f'arm_{x[0]}', 0.0)-.01) for x in held)-3*max(0.0, legs_short-.01)-(0.5 if not holding else 0.0)-self.link_weight*max(0.0, (link_need if rail else 0.0)-self.link)
        return dict(score=score, least=least, parts=parts, by_group={f'{p}->{g}': round(c, 3) for (p, g), c in sorted(by_group.items())}, reach=reach, holding=holding, legs_short_m=round(legs_short, 3),
                    arrest=dict(rail_point_sector=[round(x, 3) for x in self.sf.back(rail[0])] if rail else None,
                                link_needed_m=round(link_need, 3) if rail else None, prototype_link_m=round(self.link, 3),
                                link_tube_rail_m=round(link_tube, 3) if hit_tube else None, link_transfer_rail_m=round(link_xfer, 3) if hit_xfer else None,
                                rail_used='transfer' if (hit_xfer is not None and rail is hit_xfer) else 'tube',
                                continuous=bool(rail and link_need <= self.link)),
                    envelope=dict(com_sector=[round(x, 3) for x in self.sf.back(c)], com_toward_overhead_of_feet_m=round(toward, 3),
                                  com_lateral_of_feet_m=round(off_h.dot(Vector(info['forward']).cross(U)), 3),
                                  hand_horizontal_force_fraction_of_weight=round(frac, 2) if frac is not None else None,
                                  hands_pull=('toward the overhead (COM behind the feet)' if toward < 0 else 'off the overhead (COM ahead of the feet)')),
                    joints={k: tuple(v) for k, v in joints.items()}, fr=fr, info=info)


def keyframes(st, opt_hh, one_hand=False):
    """The transfer as (key, description, grid of (hip, lean, feet, hand_sets, footing))."""
    z = st.g['z']                                             # the body (hips and feet) also slides 0.06 m either way along the rungs
    return [(k, d, [it for lt in (-.06, 0.0, .06) for it in _keyframes(st, opt_hh, z+lt, only=k, one_hand=one_hand)]) for k, d, _ in _keyframes(st, opt_hh, z, one_hand=one_hand)]


def _keyframes(st, opt_hh, zc, only=None, one_hand=False):
    g, L, b, r = st.g, st.L, st.b, st.r; zl, zr = zc-.09, zc+.09
    top, low = g['rungs'][-1], (g['rungs'][-2] if len(g['rungs']) > 1 else None)
    rung = lambda x, z: (x+r, g['y'], z)                        # ball of the foot on the rung's top
    step_names = [n for n, grp, _ in st.trees if grp == 'step']
    land = ['Sector_Ladder_Stile_1', 'Sector_Ladder_Stile_2']; tube = ['Crew_Tube_1_1_Ladder_Stile_1', 'Crew_Tube_1_1_Ladder_Stile_2']
    hh = list(opt_hh) if isinstance(opt_hh, (list, tuple)) else ['STUDY_Handhold_left', 'STUDY_Handhold_right'] if opt_hh else []
    sector_grips = land+hh; fwd_grips = tube+hh; every = land+tube+hh
    sill = st.sill_point(zr, -2.98); edge = st.sill_point(zr, L['seat']-.03)
    lead_air = (edge[0]+.07, edge[1], edge[2])
    hip_h = b.bones['hip']
    stand = lambda x_rung, back, drop: (x_rung+r+hip_h-drop, g['y']+.07+back, zc)
    out = []
    if low is not None:
        grid = [(stand(low, bk, dr), ln) for bk in (.04, .10, .16, .22, .28) for dr in (0.0, .08, .16) for ln in (0.0, 12.0)]
        out.append(('K0_lower_rung', 'both feet on the rung below the top one, hands on the sector-side grips',
                    [(hp, ln, {'left': rung(low, zl), 'right': rung(low, zr)}, {'left': sector_grips, 'right': sector_grips},
                      {'left': step_names, 'right': step_names}) for hp, ln in grid]))
    grid = [(stand(top, bk, dr), ln) for bk in (.04, .10, .16, .22, .28) for dr in (0.0, .08, .16) for ln in (0.0, 12.0)]
    out.append(('K1_top_rung', 'both feet on the top rung, hands on the sector-side grips',
                [(hp, ln, {'left': rung(top, zl), 'right': rung(top, zr)}, {'left': sector_grips, 'right': sector_grips},
                  {'left': step_names, 'right': step_names}) for hp, ln in grid]))
    grid = [(stand(top, bk, dr), ln) for bk in (.04, .10, .16, .22) for dr in (0.0, .08) for ln in (15.0, 30.0, 45.0)]
    out.append(('K2_hands_transfer', 'feet on the top rung, leaning in, hands to the forward grips (the trailing hand may keep its grip)',
                [(hp, ln, {'left': rung(top, zl), 'right': rung(top, zr)}, {'left': every, 'right': fwd_grips},
                  {'left': step_names, 'right': step_names}) for hp, ln in grid]))
    grid = [((top+r+hip_h-dr, g['y']+.07+bk, zc), ln) for bk in (0.0, .06, .12, .18) for dr in (0.0, .08, .16) for ln in (15.0, 30.0, 45.0)]
    out.append(('K3_hip_over_step', 'trailing (left) foot on the top rung, the lead boot over the frame face, hips toward the opening',
                [(hp, ln, {'left': rung(top, zl), 'right': lead_air}, {'left': every, 'right': fwd_grips},
                  {'left': step_names, 'right': []}) for hp, ln in grid]))
    grid = [((sill[0]+k*hip_h, g['y']+dy, zc), ln) for dy in (-.12, -.04, .04, .12) for k in (.55, .70, .85) for ln in (30.0, 45.0, 60.0)]
    out.append(('K4_foot_on_sill', 'lead (right) foot on the sill, trailing foot still on the top rung, torso into the tube',
                [(hp, ln, {'left': rung(top, zl), 'right': sill}, {'left': every, 'right': fwd_grips},
                  {'left': step_names, 'right': ['Sector_Hatch_Frame', 'Landing_Fit_Hatch_Mark', 'Crew_Tube_1_1']}) for hp, ln in grid]))
    if one_hand:                                              # the right hand stays free: only the left hand ever holds
        out = [(k, d, [(hp, ln, ft, dict(hs_, right=[]), fo) for hp, ln, ft, hs_, fo in grid]) for k, d, grid in out]
    return [it for k, d, grid in out if k == only for it in grid] if only else out


def status(c):
    return 'FAIL' if c < 0 else 'MARGINAL' if c < STUDY_MARGIN else 'PASS'


def place_handholds(s, sf, bodies, coll, step):
    """Put one PROTOTYPE handhold per side where the hands reach: of the candidate sites, the one nearest that side's shoulder at a nominal
    K2 stance (top rung, hips 0.10 m off, leaning 30 deg) over both induction bodies (worst body counts), outside the lower 120 deg."""
    sites = handhold_sites(s); r = s['human_entry']['handrail_radius_m']; up, fwd = sf.d((1, 0, 0)), sf.d((0, -1, 0)); chosen = {}
    for side, sign in (('left', -1), ('right', 1)):
        best = None
        for site in sites:
            if site['deg']*sign < 0:
                continue
            worst = 0.0
            for b in bodies:                                  # the nearest of the nominal K1-K3 stances counts for each body
                near = 9.0
                for back, lean in ((.10, 0.0), (.10, 30.0), (.04, 45.0)):
                    hip = (step['rungs'][-1]+r+b.bones['hip'], step['y']+.07+back, step['z'])
                    saved = dict(ch.P); ch.P.update(b.P)
                    try:
                        j = ch.skeleton(hs.figure(b.H), dict(ch.STAND, trunk=lean), tuple(sf.p(hip)), tuple(up), tuple(fwd))
                    finally:
                        ch.P.clear(); ch.P.update(saved)
                    sh = Vector(j[f'shoulder_{side}']); a, c = sf.p(site['a']), sf.p(site['b']); u = c-a
                    t = max(0.0, min(1.0, (sh-a).dot(u)/u.dot(u))); near = min(near, (a+u*t-sh).length-r)
                worst = max(worst, near-b.arm)
            if best is None or worst < best[0]:
                best = (worst, site)
        site = best[1]; rod(f'STUDY_Handhold_{side}', sf.p(site['a']), sf.p(site['b']), r, coll)
        chosen[side] = dict(site, worst_beyond_arm_reach_m=round(best[0], 3), length_m=HANDHOLD_LEN, radius_m=r,
                            a=[round(x, 3) for x in site['a']], b=[round(x, 3) for x in site['b']], centre=[round(x, 3) for x in site['centre']],
                            centre_vehicle=[round(x, 3) for x in sf.p(site['centre'])])
    return chosen


CARRIERS = {'A': dict(name='rigid full-length litter', shape='box', size=(2.0, 0.55, 0.30)),          # references/p1_hum003.json "carriers"
            'S': dict(name='suited casualty on a full-length litter frame (EVA-003)', shape='disc', radius=0.4285, length=2.093)}
SWEEP_Y = (-3.04, -2.00)                                   # the aperture passage: from the tube side of the frame to 0.8 m in front of the leaf plane
SWEEP_SKIP = ('Interior_Overhead', 'Sector_Hatch_Frame', 'Crew_Tube_1_1', 'Landing_Fit_Hatch_Mark')   # the bore itself is the constraint (clear radius)
SWEEP_STEP = 0.02


def surface_samples(o, sf, step=0.01):
    """Sector-frame points along every face edge of a mesh object (edges densified; long rods have vertices only at their ends)."""
    mw = o.matrix_world; vs = [sf.back(mw @ v.co) for v in o.data.vertices]; out = []; seen = set()
    for p in o.data.polygons:
        ids = list(p.vertices)
        for a, b in zip(ids, ids[1:]+ids[:1]):
            if (min(a, b), max(a, b)) in seen:
                continue
            seen.add((min(a, b), max(a, b))); n = max(1, int((vs[a]-vs[b]).length/step))
            out += [tuple(vs[a]+(vs[b]-vs[a])*(i/n)) for i in range(n+1)]
    return out


def passage_samples(s, sf, hardware, exclude):
    """name -> numpy (N, 3) sector-frame surface samples of every vehicle object in the aperture passage (|x|, |z - hatch| < 1.1, y in SWEEP_Y)."""
    import numpy as np
    L = he.landing(s); dg = bpy.context.evaluated_depsgraph_get(); out = {}
    for inst in dg.object_instances:
        o = inst.object
        if o.type != 'MESH' or o.name in exclude or o.name.startswith(('Human_', 'CHAR_', 'STUDY_CHAR')) or o.get('kind') in ('scale_reference', 'camera', 'study_skip'):
            continue
        if any(o.name == k or o.name.startswith(k+'.') for k in SWEEP_SKIP) or not len(o.data.polygons):
            continue
        class W:                                              # evaluated world matrix of the instance
            pass
        w = W(); w.matrix_world = inst.matrix_world; w.data = o.data
        cs = [sf.back(inst.matrix_world @ Vector(c)) for c in o.bound_box]
        lo = [min(c[i] for c in cs) for i in range(3)]; hi = [max(c[i] for c in cs) for i in range(3)]
        if hi[1] < SWEEP_Y[0] or lo[1] > SWEEP_Y[1] or hi[0] < L['x']-1.1 or lo[0] > L['x']+1.1 or hi[2] < L['z']-1.1 or lo[2] > L['z']+1.1:
            continue
        pts = np.array(surface_samples(w, sf, 0.02))
        pts = pts[(pts[:, 1] >= SWEEP_Y[0]) & (pts[:, 1] <= SWEEP_Y[1])]
        pts = pts[np.hypot(pts[:, 0]-L['x'], pts[:, 2]-L['z']) < 1.4]
        if len(pts):
            out[o.name] = pts
    return out


def carrier_clearance(shape, centres, theta, P, bore_r, axis):
    """Least clearance (m) of a carrier cross-section (box half-sizes or disc radius) at each centre (K, 2) for roll theta, against the points P (N, 2)
    [(x, z) projections of obstacle surface samples] and the circular bore of radius bore_r about axis; negative: overlap."""
    import numpy as np
    c, s_ = math.cos(theta), math.sin(theta); out = np.empty(len(centres))
    for k0 in range(0, len(centres), 256):
        C = centres[k0:k0+256]; d = P[None, :, :]-C[:, None, :]
        if shape[0] == 'disc':
            dist = np.hypot(d[..., 0], d[..., 1])-shape[1]; far = np.hypot(C[:, 0]-axis[0], C[:, 1]-axis[1])+shape[1]
        else:
            hx, hz = shape[1], shape[2]
            u = c*d[..., 0]+s_*d[..., 1]; v = -s_*d[..., 0]+c*d[..., 1]; qx, qz = np.abs(u)-hx, np.abs(v)-hz
            dist = np.hypot(np.maximum(qx, 0), np.maximum(qz, 0))+np.minimum(np.maximum(qx, qz), 0)
            corners = np.array([[sx*hx, sz*hz] for sx in (-1, 1) for sz in (-1, 1)])
            wx = c*corners[:, 0]-s_*corners[:, 1]; wz = s_*corners[:, 0]+c*corners[:, 1]
            far = np.max(np.hypot(C[:, None, 0]+wx[None]-axis[0], C[:, None, 1]+wz[None]-axis[1]), axis=1)
        out[k0:k0+256] = np.minimum(dist.min(axis=1) if dist.size else 9.0, bore_r-far)
    return out


def carrier_sweep(s, sf, samples, study_names, grip='post', only=None):
    """Best clearance of each carrier translating along the hatch axis through the aperture (cross-section free to shift and roll), for the vehicle with
    all the study hardware, without the grab post, without the transfer rail(s), and with neither."""
    import numpy as np
    L = he.landing(s); axis = (L['x'], L['z']); R = L['clear_r']; res = {}
    gx = np.arange(-R, R+1e-9, SWEEP_STEP); centres = np.array([(L['x']+a, L['z']+b) for a in gx for b in gx if math.hypot(a, b) < R])
    def points(drop):
        arrs = [v[:, [0, 2]] for n, v in samples.items() if not any(k in n for k in drop)]
        return np.concatenate(arrs) if arrs else np.zeros((0, 2))
    gk, gn = ('STUDY_Grab_Post', 'grab_post') if grip == 'post' else ('STUDY_Grab_Handgrip', 'handgrip')
    sets = {'all_study_hardware': (), f'without_{gn}': (gk,), 'without_transfer_rail': ('STUDY_Transfer_Rail',),
            f"without_{'post' if grip == 'post' else gn}_and_rail": (gk, 'STUDY_Transfer_Rail')}
    sets = {k: v for k, v in sets.items() if not only or k in only}
    for cid, c in CARRIERS.items():
        shape = ('disc', c['radius']) if c['shape'] == 'disc' else ('box', c['size'][1]/2, c['size'][2]/2)
        thetas = [0.0] if shape[0] == 'disc' else [math.radians(a) for a in range(0, 180, 10)]
        row = {}
        for sname, drop in sets.items():
            P = points(drop); best = (-9.0, None, None)
            for th in thetas:
                cl = carrier_clearance(shape, centres, th, P, R, axis); i = int(np.argmax(cl))
                if cl[i] > best[0]:
                    best = (float(cl[i]), th, centres[i])
            cl0, th, cen = best
            # nearest object at the best placement
            near = None
            if cl0 > -9:
                dd = {}
                for n, v in samples.items():
                    if any(k in n for k in drop):
                        continue
                    one = carrier_clearance(shape, cen[None], th, v[:, [0, 2]], 9.0, axis)[0]; dd[n] = one
                near = min(dd, key=dd.get) if dd else None
            row[sname] = dict(least_m=round(cl0, 3), best_roll_deg=round(math.degrees(th)), best_centre_sector_xz=[round(float(cen[0]), 3), round(float(cen[1]), 3)],
                              nearest=near, bore_wall_clearance_m=round(R-(math.hypot(cen[0]-axis[0], cen[1]-axis[1])+(shape[1] if shape[0] == 'disc' else math.hypot(shape[1], shape[2]))), 3))
        res[cid] = dict(carrier=c['name'], cross_section=(f"disc r {c['radius']} m" if c['shape'] == 'disc' else f"box {c['size'][1]} x {c['size'][2]} m, long axis along the hatch axis ({c['size'][0]} m)"), placements=row)
    return res


def leaf_sweep(s, sf, hardware):
    """3-D distance of the study hardware to the swept volume of the sliding hatch leaf (closed over the bore to fully open), and the recessed-guide overlap with the leaf."""
    import numpy as np
    L = he.landing(s); y0, y1 = min(L['leaf_closed'][0], L['leaf_open'][0]), max(L['leaf_closed'][1], L['leaf_open'][1])
    lo = np.array([L['x']-L['leaf_r'], y0, L['z']-L['leaf_r']]); hi = np.array([L['x']+L['leaf_r'], y1, L['z']+L['leaf_r']+L['travel']])
    rows = {}
    for o in hardware:
        P = np.array(surface_samples(o, sf, 0.01)); q = np.maximum(np.maximum(lo-P, P-hi), 0); d = np.linalg.norm(q, axis=1)
        inside = np.all((P > lo) & (P < hi), axis=1)
        rows[o.name] = dict(least_m=round(float(-1.0 if inside.any() else d.min()), 3), inside_swept_volume=bool(inside.any()))
    return dict(swept_volume_sector=dict(lo=[round(float(x), 3) for x in lo], hi=[round(float(x), 3) for x in hi]), objects=rows)


def grip_grid(s, sf, g, coll, bodies, args):
    """B3H handgrip grid search (no body-clearance run): for every candidate of handgrip_candidates(), on the B3S hardware with the grab post removed,
    the best-placement carrier clearances (A, S), the leaf swept-volume clearance of the bar and brackets, the clear-bore check, and the right-hand reach
    from the B3S both-hands postures of each rig (shoulder to the nearest bar point minus 1.02 x arm, as Study.pose accepts a grip)."""
    import numpy as np
    L = he.landing(s); r = s['human_entry']['handrail_radius_m']; up, fwd = sf.d((1, 0, 0)), sf.d((0, -1, 0))
    objs, moved, _ = build_redesign(s, sf, g, coll, rails=RAIL_SETS[args.rails], post=False)
    prof, moved2, _ = build_sim027_profile(sf, coll); moved |= moved2
    exclude = moved | {'Sector_Thrust_Step_Stile_1', 'Sector_Thrust_Step_Stile_2', 'Sector_Thrust_Step_Rungs', 'Sector_Thrust_Step_Brackets'}
    bpy.context.view_layer.update(); base = passage_samples(s, sf, objs, exclude)
    b3s = json.loads(args.report.read_text())['options']['B3S']['bodies']; rail = RAIL_SETS[args.rails][0]
    rail_a, rail_b = (rail[3], rail[1], rail[2]), (rail[4], rail[1], rail[2])
    stance = {}
    for b in bodies:                                       # shoulders and head of the B3S both-hands posture per keyframe (independent of the hands)
        for kk, kf in b3s[b.who]['variants']['both']['keyframes'].items():
            saved = dict(ch.P); ch.P.update(b.P)
            try:
                lean = kf['posture']['lean_deg']
                j = ch.skeleton(hs.figure(b.H), dict(ch.STAND, trunk=lean, head=-.5*lean), tuple(sf.p(kf['posture']['hip_sector'])), tuple(up), tuple(fwd))
            finally:
                ch.P.clear(); ch.P.update(saved)
            stance[(b.who, kk)] = (tuple(sf.back(Vector(j['shoulder_right']))), tuple(sf.back(Vector(j['head']))), b.arm)
    rows = {}
    for name, spec in handgrip_candidates().items():
        gobjs, meta = build_handgrip(sf, r, spec, coll, (L['x'], L['z'])); bpy.context.view_layer.update()
        smp = dict(base); smp.update({o.name: np.array(surface_samples(o, sf, 0.02)) for o in gobjs})
        cs = carrier_sweep(s, sf, smp, [o.name for o in gobjs], grip='handgrip', only=('all_study_hardware',))
        lf = leaf_sweep(s, sf, gobjs)['objects']; op = opening_check(s, sf, gobjs)['objects']
        a, b_ = meta['a_sector'], meta['b_sector']; reach = {}
        for (who, kk), (sh, hd, arm) in stance.items():
            reach.setdefault(who, {})[kk[:2]] = dict(beyond_reach_m=round(seg_dist(sh, a, b_)-r-arm*1.02, 3), head_to_bar_m=round(seg_dist(hd, a, b_)-r, 3))
        n_reach = sum(v['beyond_reach_m'] <= 0 for w in reach.values() for v in w.values())
        rows[name] = dict(spec=meta, carriers={c: v['placements']['all_study_hardware']['least_m'] for c, v in cs.items()},
                          carrier_nearest={c: v['placements']['all_study_hardware']['nearest'] for c, v in cs.items()},
                          leaf_least_m=min(v['least_m'] for v in lf.values()), intrudes_clear_bore=any(v['intrudes_clear_bore'] for v in op.values()),
                          bar_to_transfer_rail_m=round(min(seg_dist(p, rail_a, rail_b) for p in (a, b_))-2*r, 3),
                          right_hand_reach=reach, keyframes_reached=n_reach, min_head_to_bar_m=min(v['head_to_bar_m'] for w in reach.values() for v in w.values()))
        print('WF_STEP2 GRIP', name, json.dumps({k: rows[name][k] for k in ('carriers', 'leaf_least_m', 'intrudes_clear_bore', 'keyframes_reached', 'min_head_to_bar_m')}), flush=True)
        for o in gobjs:
            bpy.data.objects.remove(o, do_unlink=True)
    args.grip_grid.write_text(json.dumps(dict(study='B3H handgrip grid (owner 2026-10-13, 15!A171), NONCANON', rails=args.rails,
                                              reach_basis='B3S both-hands postures (references/p1_char_step2.json options.B3S); the full run re-searches postures',
                                              candidates=rows), indent=1)+'\n')
    print('WF_STEP2 grip grid', len(rows), flush=True)


def band(c):
    return None if c is None else 'FAIL' if c < 0 else 'MARGINAL' if c < STUDY_MARGIN else 'PASS'


ACCESS = {'B3S': dict(prefix='tsb', grip='right grab post', study='SIM-027 thrust hatch step B3S (B3R + deck band / ladder re-profile, anchor layout, single-hand sequence, carrier and leaf sweeps)'),
          'B3H': dict(prefix='tsh', grip='right handgrip', study='owner 2026-10-13 (15!A171) thrust hatch step B3H (B3S with the grab post replaced by one relocated low-profile handgrip)'),
          'B3H2': dict(prefix='tsh2', grip='right handgrip',
                       study='owner 2026-10-13b (15!A180) thrust hatch step B3H2 (B3H with the dog-legged transfer rail T5 and the handgrip brackets at the deck-side end; arrest link <= 0.206 m hard limit)'),
          'B3HR': dict(prefix='tshr', grip='right handgrip', segments=False,      # rejected exploration (links up to 0.211 m > 0.206 m): kept in p1_char_step2.json only
                       study='B3HR exploration (B3H with the transfer rail at z -1.64, anchor layout T4)')}


def build_access(paths, report_path):
    """Merge per-rig SIM-027 / B3H reports (one Blender process per rig and variant) into their option (B3S or B3H) of p1_char_step2.json and write
    references/p1_access_seg_step.json with the segments of every such option present (B3S ids tsb.*, B3H ids tsh.*).
    least_m is the MINIMUM over all rigs, keyframes and postures evaluated (owner worst-case rule); no padding; a hand-sequence segment is OPEN
    while the restraint load analysis (arrest distance / injury load) is open."""
    reps = [json.loads(Path(x).read_text()) for x in paths]; opt = None
    key = next(k for k in ACCESS if k in reps[0]['options'])
    for r in reps:                                           # one process per (rig, variant): merge variants per rig, take the sweeps from the report that ran them
        o = r['options'][key]
        if opt is None:
            opt = o
        for who, b in o['bodies'].items():
            tgt = opt['bodies'].setdefault(who, dict(b, variants={}))
            for vn, v in b['variants'].items():              # a variant may also come in several per-keyframe reports (a native Blender crash loses the whole process)
                cur = tgt['variants'].setdefault(vn, dict(v, keyframes={})); cur['keyframes'].update(v['keyframes'])
        if 'carrier_sweep' in o['redesign']:
            opt['redesign'] = o['redesign']
    for b in opt['bodies'].values():
        for v in b['variants'].values():
            kf = dict(sorted(v['keyframes'].items())); v['keyframes'] = kf; kk, k2 = min(kf.items(), key=lambda kv: kv[1]['least_m'])
            v['tightest'] = dict(keyframe=kk, least_m=k2['least_m'], status=status(k2['least_m']))
            v['one_hand_always_holds'] = all(x['one_hand_holds'] for x in kf.values()); v['both_hands_hold_keyframes'] = [k for k, x in kf.items() if len(x['holding']) == 2]
            v['arrest_continuous'] = all(x['arrest']['continuous'] for x in kf.values()); v['arrest_max_link_needed_m'] = max(x['arrest']['link_needed_m'] for x in kf.values())
            v['summary'] = {}
            for pn in PARTS:
                vals = [(x['parts'][pn]['least_m'], k, x['parts'][pn]['at']) for k, x in kf.items() if pn in x['parts']]
                if vals:
                    m = min(vals); v['summary'][pn] = dict(least_m=m[0], keyframe=m[1], at=m[2], status=status(m[0]))
        base = b['variants'].get('both') or next(iter(b['variants'].values())); b.update({k: v for k, v in base.items() if k != 'variants'})
    rep = json.loads(report_path.read_text()) if report_path.exists() else dict(options={})
    rep.setdefault('options', {})[key] = opt; report_path.write_text(json.dumps(rep, indent=1)+'\n')
    keys = [k for k in ACCESS if k in rep['options'] and ACCESS[k].get('segments', True)]
    segs = [sg for k in keys for sg in access_segments(k, rep['options'][k])]
    out = dict(study='; '.join(ACCESS[k]['study'] + f" (ids {ACCESS[k]['prefix']}.*)" for k in keys) + ', NONCANON disposable studies',
               source=[f'references/p1_char_step2.json (options.{k})' for k in keys] + ['references/CHAR_STEP2_HATCH_STEP.md', 'references/p1_hum003.json (carriers)'], segments=segs)
    Path(ROOT/'references/p1_access_seg_step.json').write_text(json.dumps(out, indent=1)+'\n')
    print('WF_STEP2 access segments', len(segs), flush=True)


def access_segments(key, opt):
    """Route segments of one merged option (B3S or B3H)."""
    segs = []; rd = opt['redesign']; PL = 0.206; px = ACCESS[key]['prefix']; gl_ = ACCESS[key]['grip']
    def add(id_, variant, case, least, worst_over, nearest, note, status=None, states=('0g', 'locked_1.5g'), spread=None):
        segs.append(dict(id=id_, route='thrust_hatch_step', states=list(states), variant=variant, case=case,
                         least_m=None if least is None else round(least, 3), status=status or band(least) or 'OPEN',
                         worst_case_over=worst_over, seed_spread_m=spread, nearest=nearest, note=note))
    for who, b in opt['bodies'].items():
        for vname, label in (('both', f'both hands (left stiles, {gl_})'), ('one', f"single hand (left only), {gl_.replace('right ', '')} allowed"),
                             ('one_np', f"single hand (left only), no {gl_.replace('right ', '')}"),
                             ('both_opt', f'both hands, {gl_} OPTIONAL (the right hand may stay free where a grip costs clearance)')):
            v = b['variants'].get(vname)
            if not v:
                continue
            kf = v['keyframes']; worst = min(kf.items(), key=lambda kv: kv[1]['least_m']); kk, k2 = worst
            pt = min(((p, d) for p, d in k2['parts'].items()), key=lambda pd: pd[1]['least_m'], default=(None, None))
            nearest = f"{pt[0]} -> {pt[1]['at']} at {kk}" if pt[0] else None
            seq = '; '.join(f"{k[:2]} " + ('/'.join(f"{s_[0]}:{r_['grip']} (wrist {r_['wrist_to_grip_m']*100:.1f} cm)" for s_, r_ in k2_['reach'].items() if r_.get('grip')) or 'NO HAND HOLDS')
                            for k, k2_ in kf.items())
            links = [k2_['arrest']['link_needed_m'] for k2_ in kf.values()]
            gl = [(k, next((r_['grip'] for r_ in k2_['reach'].values() if r_.get('grip')), None)) for k, k2_ in kf.items()]
            regrip = ', '.join(f"{a[0][:2]}->{b[0][:2]}: {a[1]} -> {b[1]}" for a, b in zip(gl, gl[1:]) if a[1] != b[1]) or 'none: the same grip in every keyframe'
            holds = all(k2_['holding'] for k2_ in kf.values())
            if vname == 'both':
                add(f'{px}.{who}.body.both_hands', vname, f'{who}, K0..K4, {label}', k2['least_m'], ['keyframes K0..K4', 'posture grid per keyframe (hip stand-off, drop, trunk lean, +-0.06 m along the rungs)', 'all body parts vs all vehicle and study objects'],
                    nearest, f"tightest keyframe {kk}. Grips: {seq}. Geometry only; no suit, harness or load.")
            elif vname == 'both_opt':
                add(f'{px}.{who}.body.both_hands_optional', vname, f'{who}, K0..K4, {label}', k2['least_m'], ['keyframes K0..K4', 'posture grid per keyframe, each posture with and without the right-hand grip', 'all body parts vs all vehicle and study objects'],
                    nearest, f"tightest keyframe {kk}. Grips: {seq}. Geometry only; no suit, harness or load.")
            else:
                seq_status = 'FAIL' if (k2['least_m'] < 0 or not holds) else 'OPEN'
                add(f'{px}.{who}.sequence.{vname}', vname, f'{who}, single-hand transition K0..K4, restraint attached throughout ({label})', k2['least_m'],
                    ['keyframes K0..K4', 'posture grid per keyframe', 'every grip reach (hand holds within 3 cm of the grip, solver arm shortfall)'], nearest,
                    f"{'a hand holds in every keyframe' if holds else 'NO HAND HOLDS in at least one keyframe'}; geometric status {band(k2['least_m'])}. Hand schedule: {seq}. "
                    f"Regrips ({regrip}) pass through a moment with no hand holding, restrained by the arrester link ({min(links):.3f}..{max(links):.3f} m needed vs {PL} m PROTOTYPE) and both feet (that moment is not checked between static keyframes); "
                    "OPEN until the restraint load / arrest-distance / injury-load analysis exists (not invented here).", status=seq_status)
            if vname == 'both':
                for part, lab, keys in (('boot', 'lead boot / boots (deck band, sill, frame)', ('K0', 'K1', 'K2', 'K3', 'K4')), ('hand', 'hands', None), ('arm', 'arms', None), ('thigh', 'thighs', None)):
                    cand = [(k_[:2], k2_['parts'][part]) for k_, k2_ in kf.items() if part in k2_['parts']]
                    if not cand:
                        continue
                    kq, pv = min(cand, key=lambda c: c[1]['least_m'])
                    add(f'{px}.{who}.part.{part}', vname, f'{who}, {part}, {label}', pv['least_m'], ['keyframes K0..K4', 'posture grid per keyframe'], f"{part} -> {pv['at']} at {kq}",
                        f"{lab}; K4 boot values per owner item 2 (3.6-4.4 cm in B3R)." if part == 'boot' else lab)
        # arrest
        lk = {vn: [k2_['arrest']['link_needed_m'] for k2_ in vv['keyframes'].values()] for vn, vv in b['variants'].items()}
        over = {vn: [round(x, 3) for x in xs if x > PL] for vn, xs in lk.items()}
        add(f'{px}.{who}.arrest_link', 'all', f'{who}, chest ring to the nearest anchor (tube rail or transfer rail(s)), K0..K4', None,
            ['keyframes K0..K4', 'variants both/one/one_np'], None,
            "link needed (m) per variant: " + '; '.join(f"{vn} {min(xs):.3f}..{max(xs):.3f}" for vn, xs in lk.items()) + f" vs PROTOTYPE link {PL}. "
            + ('above the link at: ' + '; '.join(f"{vn} {xs}" for vn, xs in over.items() if xs) + ' (a longer lanyard needs the arrest-distance / injury-load analysis, OPEN).' if any(over.values()) else 'at or below the PROTOTYPE link in every keyframe (continuity by overlapping anchors).'),
            status='OPEN')
    cs = rd['carrier_sweep']['results']
    for cid, c in cs.items():
        for sname, pl in c['placements'].items():
            add(f'{px}.carrier.{cid}.{sname}', f'carrier_{cid}' + ('' if sname == 'all_study_hardware' else '_' + sname), f"{c['carrier']}, {c['cross_section']}, passing the aperture along the hatch axis ({sname.replace('_', ' ')})",
                pl['least_m'], [f"carrier translation along the hatch axis over y {rd['carrier_sweep']['slab_y']}", 'cross-section shift and roll chosen to MAXIMISE the least clearance (best placement, not a worst placement)', 'all vehicle and study objects in the passage; bore wall'],
                pl['nearest'], f"best roll {pl['best_roll_deg']} deg, centre sector (x, z) {pl['best_centre_sector_xz']}, bore wall clearance {pl['bore_wall_clearance_m']} m. Approach up the sector wall and the turn into the tube are not swept here (HUM-003 routes).")
    ls = rd['leaf_sweep']
    wk = min(ls['objects'].items(), key=lambda kv: kv[1]['least_m'])
    add(f'{px}.leaf.sweep.hardware', 'leaf', f"sliding leaf swept volume (closed over the bore to fully open) vs {gl_.replace('right ', '')}, transfer rail(s) and brackets", wk[1]['least_m'],
        ['leaf travel closed->open (swept volume)', 'all study hardware'], wk[0], 'analytic swept box: |x| < leaf radius, y over the leaf slab, z from the closed leaf to the open end')
    wsw = min(ls['stowage_to_leaf_swept'].items(), key=lambda kv: kv[1]['least_m'])
    add(f'{px}.leaf.sweep.stowage', 'leaf', 'sliding leaf swept volume vs recessed Crew_Stowage_Upper', wsw[1]['least_m'], ['leaf travel closed->open'], wsw[0], 'recessed stowage copy')
    add(f'{px}.leaf.guide_overlap', 'leaf', 'recessed leaf guide Sector_Hatch_Rail_1 vs leaf engagement', None, ['leaf slab y vs recessed guide y'], 'Sector_Hatch_Rail_1 (study copy)',
        f"leaf engagement in the recessed guide is {ls['guide_leaf_overlap_y_m']} m (unreleased); not a clearance; engagement and guide load path need an engineering check.", status='OPEN')
    add(f'{px}.all.0g_feet_free', '0g', 'hand-over-hand with the feet off the rungs (0 g)', None, ['not modelled'], None,
        'The 0 g rerun uses the same postures as 1.5 g (the posture search is geometric, gravity enters only the body envelope, so the 0 g clearances equal the 1.5 g ones); a feet-free hand-over-hand 0 g pose model does not exist and is not invented. OPEN.',
        status='OPEN', states=('0g',))
    return segs


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--who', nargs='*', default=['instructor', 'newcomer'])
    ap.add_argument('--options', nargs='*', default=list(OPTIONS)); ap.add_argument('--size', type=int, default=640)
    ap.add_argument('--variants', nargs='*', default=['both', 'one'])
    ap.add_argument('--rails', default='T3', help='SIM-027 anchor layout from RAIL_SETS')
    ap.add_argument('--no-sweep', action='store_true', help='skip the carrier and leaf sweeps (rail exploration)')
    ap.add_argument('--access', nargs='*', default=None, help='build references/p1_access_seg_step.json from these per-rig SIM-027 reports (no study run)')
    ap.add_argument('--merge', action='store_true', help='merge the run options into the existing report instead of replacing it')
    ap.add_argument('--keyframes', nargs='*', default=None, help='only keyframes whose key starts with one of these (debug)')
    ap.add_argument('--report', type=Path, default=ROOT/'references/p1_char_step2.json')
    ap.add_argument('--renders', type=Path, default=ROOT/'renders/p1/studies/char_step2')
    ap.add_argument('--grip', default=GRIP_PICK, help='B3H handgrip candidate from handgrip_candidates()')
    ap.add_argument('--grip-grid', type=Path, default=None, help='B3H: evaluate every handgrip candidate (carriers, leaf, bore, right-hand reach) into this JSON; no body run')
    args = ap.parse_args(argv)
    if args.access is not None:
        return build_access([Path(x) for x in args.access], args.report)
    args.renders.mkdir(parents=True, exist_ok=True); t0 = time.time()
    s = load(ROOT)[0]; bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer/WF_WAYFARER_001.blend'))
    for o in bpy.data.objects:
        if o.name.startswith('Human_') or o.get('kind') == 'scale_reference':
            o.hide_render = True
    sf = Sector(s); L = he.landing(s); S = he.thrust_step(s)
    rig_coll = bpy.data.collections.new('STUDY_CHAR_STEP2_RIGS'); bpy.context.scene.collection.children.link(rig_coll)
    bodies = [Body(w, rig_coll) for w in args.who]
    for b in bodies:
        b.rig.hide_render = True
        for c in b.rig.children:
            c.hide_render = True
    report = dict(study='CHAR-STEP2', status='NONCANON REDESIGN STUDY (S&E 15!A130 REDESIGN STUDY / CURRENT FAIL)', vehicle='WF_WAYFARER_001.blend',
                  frame='sector frame of the ring-A spine-port sector (he.landing): +X up with aft down, +Y radially out (the deck), the overhead at '
                        f"y = {L['ceiling']:.2f}, the hatch axis at x = {L['x']:.2f}, z = {L['z']:.2f}",
                  as_built=dict(step_rungs_above_floor_m=[round(x-S['floor'], 3) for x in S['rungs']], step_standoff_from_overhead_m=round(S['y']-L['ceiling'], 3),
                                step_offset_from_hatch_axis_m=round(S['z']-L['z'], 3), sill_above_floor_m=round(S['sill']-S['floor'], 3),
                                frame_face_proud_of_overhead_m=round(L['seat']-L['ceiling'], 3),
                                frame_radii_m=[L['clear_r'], L['frame_r']]),
                  rules=dict(study_margin_m=STUDY_MARGIN, contact_tolerance_m=CONTACT_TOL, mount_gap_m=MOUNT_GAP, gravity=f'{G_LOAD} g aft-down (rings locked)',
                             padding='not allowed (owner)'), options={})
    report['reference_as_passed'] = {}
    trees0 = trees_near(sf.p((-0.7, -2.6, S['z'])), set())
    for b in bodies:                                          # the stance human_fit tested (the rod mannequin's), reproduced as the test failure
        saved = dict(ch.P); ch.P.update(b.P)
        try:
            fr, info = hf.rod_frame(he.thrust_stepper(s), b.H, b.bones)
        finally:
            ch.P.clear(); ch.P.update(saved)
        hf.place(b.rig, b.solver, fr, info['up'], info['forward']); cl = measure(b, trees0); worst = {}
        for (part, name), c in cl.items():
            if (part in ('hand', 'arm') and name.startswith('Sector_Ladder_Stile') or part == 'boot' and name.startswith('Sector_Thrust_Step')) and c >= -CONTACT_TOL:
                continue
            k = f'{part}->{group_of(name)}'
            if c < worst.get(k, (9.0,))[0]:
                worst[k] = (c, name)
        fails = {k: dict(least_m=round(v[0], 3), at=v[1]) for k, v in worst.items() if v[0] < STUDY_MARGIN}
        report['reference_as_passed'][b.who] = dict(stance='human_fit hatch_step_thrust mannequin stance (ankle on the mannequin foot point, both hands on the landing stiles)',
                                                    below_margin=fails, status=status(min(v[0] for v in worst.values())))
        print(f"WF_STEP2 REF {b.who} {json.dumps(fails)}", flush=True)
    for key in args.options:
        opt = OPTIONS[key]; coll = bpy.data.collections.new(f'STUDY_{key}'); bpy.context.scene.collection.children.link(coll)
        g = step_geometry(s, opt); exclude = set()
        if not g['built']:
            build_step(sf, g, coll); exclude = {n for n in ('Sector_Thrust_Step_Stile_1', 'Sector_Thrust_Step_Stile_2', 'Sector_Thrust_Step_Rungs', 'Sector_Thrust_Step_Brackets')}
        for n in ('Sector_Thrust_Step_Stile_1', 'Sector_Thrust_Step_Stile_2', 'Sector_Thrust_Step_Rungs', 'Sector_Thrust_Step_Brackets'):
            bpy.data.objects[n].hide_render = n in exclude
        hh = place_handholds(s, sf, [b for b in bodies if b.who in ('instructor', 'newcomer')] or bodies, coll, g) if opt['handholds'] else None
        redesign = None
        if opt.get('redesign'):
            if args.grip_grid:
                return grip_grid(s, sf, g, coll, bodies, args)
            rk = opt.get('rails', args.rails)
            objs, moved, meta = build_redesign(s, sf, g, coll, rails=parse_rails(rk) if opt.get('sim027') else None,
                                               post=not opt.get('handgrip'), grip=handgrip_candidates()[args.grip] if opt.get('handgrip') else None,
                                               grip_mount=(opt.get('grip_brackets'), opt.get('grip_inset'))); exclude |= moved
            if opt.get('handgrip'):
                meta['handgrip']['candidate'] = args.grip
            prof = []
            if opt.get('sim027'):
                prof, moved2, meta2 = build_sim027_profile(sf, coll); moved |= moved2; exclude |= moved2; meta['reprofile'] = meta2; meta['rail_set'] = opt.get('rails', args.rails)
            bpy.context.view_layer.update()
            for n in moved:
                bpy.data.objects[n].hide_render = True
            redesign = dict(meta, opening=opening_check(s, sf, objs))
            hh = ['STUDY_Grab_Handgrip'] if opt.get('handgrip') else ['STUDY_Grab_Post_right']
            if opt.get('sim027') and not args.no_sweep:
                hw = [o for o in objs if not o.name.startswith('STUDY_Hatch_Rail') and not o.name.startswith('STUDY_Stowage')] + [o for o in objs if o.name.startswith('STUDY_Stowage')]
                smp = passage_samples(s, sf, hw, exclude)
                redesign['carrier_sweep'] = dict(slab_y=list(SWEEP_Y), objects_in_passage=sorted(smp), skipped=list(SWEEP_SKIP), step_m=SWEEP_STEP,
                                                 results=carrier_sweep(s, sf, smp, [o.name for o in objs], grip='handgrip' if opt.get('handgrip') else 'post'))
                guide = next(o for o in objs if o.name.startswith('STUDY_Hatch_Rail'))
                gy = max(sf.back(guide.matrix_world @ v.co)[1] for v in guide.data.vertices)
                redesign['leaf_sweep'] = dict(leaf_sweep(s, sf, [o for o in hw if not o.name.startswith('STUDY_Stowage')]),
                                              guide_leaf_overlap_y_m=round(gy-L['leaf_open'][0], 3),
                                              stowage_to_leaf_swept=leaf_sweep(s, sf, [o for o in hw if o.name.startswith('STUDY_Stowage')])['objects'])
                print('WF_STEP2 SWEEP', json.dumps({c: {k: v['least_m'] for k, v in r['placements'].items()} for c, r in redesign['carrier_sweep']['results'].items()}), flush=True)
        bpy.context.view_layer.update()
        trees = trees_near(sf.p((-0.7, -2.6, g['z'])), exclude)
        ores = dict(title=opt['title'], route_hardware_change=True, needs_owner_approval=True,
                    step=dict(rungs_above_floor_m=[round(x-g['floor'], 3) for x in g['rungs']], standoff_from_overhead_m=round(g['y']-g['ceiling'], 3),
                              offset_from_hatch_axis_m=round(g['z']-L['z'], 3), top_rung_to_sill_rise_m=round(S['sill']-g['rungs'][-1], 3),
                              as_built=g['built']),
                    handholds=hh if not redesign else None, redesign=redesign, bodies={})
        allv = (('both', False, True), ('one', True, True), ('one_np', True, False)) if opt.get('sim027') else (('both', False, True), ('one', True, True))
        if opt.get('handgrip'):                               # B3H: also both hands with the right hand OPTIONAL (it may stay free where a grip would cost clearance)
            allv += (('both_opt', 'right_optional', True),)
        variants = tuple(v for v in allv if v[0] in args.variants) if redesign else (('both', False, True),)
        for b in bodies:
            st = Study(s, sf, b, trees, None, g); st.link_weight = 3.0 if redesign else 0.0
            b.rig.hide_render = False
            for c in b.rig.children:
                c.hide_render = False
            vres = {}
            for vname, one_hand, use_post in variants:
                kres = {}; worst = None
                for kk, desc, grid in keyframes(st, ((hh if use_post else []) if redesign else bool(opt['handholds'])), one_hand is True):
                    if one_hand == 'right_optional':
                        grid = grid+[(hp, ln, ft, dict(hs_, right=[]), fo) for hp, ln, ft, hs_, fo in grid]
                    if args.keyframes and not any(kk.startswith(x) for x in args.keyframes):
                        continue
                    best = None
                    for hip, lean, feet, hands, footing in grid:
                        res = st.evaluate(hip, lean, feet, hands, footing)
                        if best is None or res['score'] > best[0]['score']:
                            best = (res, dict(hip_sector=[round(x, 3) for x in hip], lean_deg=lean))
                    res, how = best
                    parts = {p: dict(least_m=round(v['free'][0], 3), at=v['free'][1], group=group_of(v['free'][1]), status=status(v['free'][0]))
                             for p, v in res['parts'].items() if 'free' in v}
                    contacts = {p: dict(least_m=round(v['contact'][0], 3), at=v['contact'][1]) for p, v in res['parts'].items() if 'contact' in v}
                    kres[kk] = dict(description=desc, posture=how, least_m=round(res['least'], 3), status=status(res['least']), parts=parts,
                                    part_to_group_m=res['by_group'],
                                    allowed_contacts=contacts, reach=res['reach'], holding=res['holding'], one_hand_holds=bool(res['holding']),
                                    legs_short_m=res['legs_short_m'], arrest=res['arrest'], envelope=res['envelope'])
                    if redesign:
                        kres[kk]['stowage_headroom_m'] = {p: res['by_group'].get(f'{p}->stowage') for p in ('head', 'hand', 'arm', 'torso')}
                        kres[kk]['g0'] = dict(clearances='identical to the 1.5 g posture (the posture search is purely geometric)', envelope=None,
                                              arrest_link_needed_m=res['arrest']['link_needed_m'])
                    print(f"WF_STEP2 {key} {vname} {b.who} {kk} least {res['least']:.3f} {status(res['least'])} holding {res['holding']} "
                          f"arrest {res['arrest']['link_needed_m']} t={time.time()-t0:.0f}s", flush=True)
                    if worst is None or res['least'] < worst[0]['least']:
                        worst = (res, kk)
                res, kk = worst                                      # render the tightest frame of this option and body
                hf.place(b.rig, b.solver, res['fr'], res['info']['up'], res['info']['forward'])
                info = dict(res['info'], centre=res['joints']['spine_02']); path = args.renders/(f'{key}_{b.who}_{kk}.png' if not redesign else f'{key}_{vname}_{b.who}_{kk}.png')
                hf.render(b.rig, info, path, args.size)
                summary = {}
                for p in PARTS:
                    vals = [(k2['parts'][p]['least_m'], k, k2['parts'][p]['at']) for k, k2 in kres.items() if p in k2['parts']]
                    if vals:
                        v = min(vals); summary[p] = dict(least_m=v[0], keyframe=v[1], at=v[2], status=status(v[0]))
                vres[vname] = dict(keyframes=kres, summary=summary, tightest=dict(keyframe=kk, least_m=round(res['least'], 3), status=status(res['least'])),
                                   one_hand_always_holds=all(k2['one_hand_holds'] for k2 in kres.values()),
                                   both_hands_hold_keyframes=[k for k, k2 in kres.items() if len(k2['holding']) == 2],
                                   arrest_continuous=all(k2['arrest']['continuous'] for k2 in kres.values()),
                                   arrest_max_link_needed_m=max(k2['arrest']['link_needed_m'] for k2 in kres.values()),
                                   render=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path))
            ores['bodies'][b.who] = dict(vres.get('both') or next(iter(vres.values())), **({'variants': vres} if redesign else {}))
            b.rig.hide_render = True
            for c in b.rig.children:
                c.hide_render = True
        report['options'][key] = ores
        if opt.get('sim027'):
            for r_ in (report,):
                r_['rails'] = args.rails
        for o in list(coll.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(coll)
        out = report
        if args.merge and args.report.exists():
            out = json.loads(args.report.read_text()); out.setdefault('options', {}).update(report['options'])
        args.report.write_text(json.dumps(out, indent=1)+'\n')
    print(f'WF_STEP2 done {time.time()-t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
