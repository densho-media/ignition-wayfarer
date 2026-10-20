"""SIM-027 / DIST-006 redline study (owner 2026-10-11 16:45: S&E 15!A157 DIST-005, 15!A158 DIST-006; references/EVA3_REPORT.md 12.6):
DISPOSABLE PROTOTYPE geometry, NONCANON. Nothing here changes data/, a generator, GEN_* geometry, a saved asset or the pressure shell; the
vehicle .blend is opened, never saved. It reuses eva3_exits (SP-13 free space, sweeps, solids) and eva3_district (L1-A elements, openings).

  A. SP-13: the rack / bench / lockers / panel rearranged (PROTOTYPE fit-out, same boxes) around a second exit that is independent of SP-12
     (its own closure, its own route from SP-13 to the trunk extension, no SP-12 volume). Carriers A, S (references/p1_hum003.json "carriers"),
     K (litter + kit) and a suited crew member (EVA_SUITED, references/p1_eva_access.json) with the rescuers, three seeds each; service access
     of the rack and bench; the independence matrix against the SP-12 exits.
  B. L1-A trunk ladder at Dock_Primary: (a) relocate the trunk ladder to 305-330 deg vs (b) move the district port (workshop port) off the
     285 deg ladder, both keeping one protected continuous 1.5 g ladder route to X 104.9 m; the rigid bridge over the dock mouth is the
     accepted prototype. Pure geometry on human_entry's ladder and openings.
  C. SP-52 warm module (~450 K, owner value) at 0.30 m from the workshop wall: standoffs, facing areas, a pure view-factor geometry
     (GEOMETRY ONLY, no heat-transfer number) and containment envelopes that fit; heat transfer stays OPEN/null (no owner emissivity,
     conductivity or insulation data).

    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/eva3_sp13_l1a.py -- --out runs/<stamp>-sim027 [--parts sp13,ladder,sp52]
"""
from pathlib import Path
import argparse
import bisect
import copy
import json
import math
import sys
import time
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer/studies')]
import eva3_exits as ex                        # also puts src/wayfarer, build, validation on sys.path
import casualty_sweep as cs
ed, h3, sv, he, ct, es = ex.ed, ex.h3, ex.sv, ex.he, ex.ct, ex.es
sd = ed.sd
P, axes_at = ex.P, ex.axes_at

# ---------------------------------------------------------------------------------------------------------------------------------
# PROTOTYPE constants of this study (none is a canon value; none is written to data/)

SEEDS = (17, 23, 41)                        # pose-search seeds; least_m is the minimum over seeds, seed_spread_m = [min, max]
MARGIN = 0.05                               # study pass margin (HUM-003, eva_suit access.suit_margin_m)
BAND = 'PASS >= 0.05, MARGINAL 0..0.05, FAIL < 0'
SERVICE_REACH_M = 0.70                      # free depth in front of the rack and the bench (hum003_routes.STAFF_REACH_M: arm reach of an operator)
LANE_R_M = 0.65                             # keep-clear radius round the exit axis above the floor (S capsule 0.43 + 0.22 for the bearers' hands)
LANE_TOP_R_M = 3.40                         # the lane runs from the floor (r 1.25) up to here, or to the room's forward wall
EXIT_D_M = 1.10                             # SP-13 exit aperture: the SP-12 N-series comparator size (not widened)
EXIT_BETAS = (30.0, 45.0)                   # oblique exits: the axis leans aft by beta from the radial (0 = radial control)
SHELL_KG_M2 = 20.0                          # SERV-002 shell value (info only; no mass is credited, no 5.41 t)
ROD_R_M = 0.0175                            # ladder stile rod radius (human_entry handrail_radius_m)
BRIDGE_ACCEPTED_M = 1.764                   # largest member gap of the accepted dock bridge at the 0.20 m margin (arrest rail, 285 deg)
LADDER_TOP_X = 104.9                        # SERV-003 ladder top (district hatch)
SIGMA = 5.670374419e-8                      # Stefan-Boltzmann constant (physical constant)
T_WARM_K = 450.0                            # owner "~450 K" (15!C123, G123); the only owner thermal value
STANDOFFS_M = (0.20, 0.30, 0.40, 0.60)      # warm module aft face to the workshop's forward outer face (0.20 = the L1-A scan, 0.30 = owner)
CONTAIN_T_M = (0.05, 0.10, 0.15, 0.20, 0.25)    # containment layer thickness tried (insulation + fire separation, unspecified, GEOMETRY)

SP13_MOVABLE = ('SP13_DRY_RACK', 'SP13_BENCH', 'SP13_SPARES', 'SP13_CHARGE_PANEL')
ROOM13 = None                               # filled by main from data/eva_suit.toml [sp13] (x_m, az_deg, r_m)


def status(m):
    return 'FAIL' if m is None or m < 0 else ('MARGINAL' if m < MARGIN else 'PASS')


# ---------------------------------------------------------------------------------------------------------------------------------
# SP-13: boxes, containment, service bands, exits

def obb_dist(pts, box):
    """Distance from points (N,3) to an oriented box (centre, axes, size); negative inside (the penetration depth)."""
    c, ax, sz = box; q = np.asarray(pts, float)-np.array(c); loc = np.stack([q@np.array(a) for a in ax], 1); d = np.abs(loc)-np.array(sz)/2
    return np.where(d.max(1) < 0, d.max(1), np.linalg.norm(np.maximum(d, 0.0), axis=1))


def box_pts(box, n=5):
    c, ax, sz = box; g = [np.linspace(-s_/2, s_/2, n) for s_ in sz]; out = []
    for a in g[0]:
        for b in g[1]:
            for d in g[2]:
                out.append(np.array(c)+a*np.array(ax[0])+b*np.array(ax[1])+d*np.array(ax[2]))
    return np.array(out)


def in_room(pts, room=None):
    room = room or ROOM13; p = np.asarray(pts, float); r = np.hypot(p[:, 1], p[:, 2]); az = np.degrees(np.arctan2(p[:, 2], p[:, 1]))
    return (p[:, 0] >= room['x'][0]) & (p[:, 0] <= room['x'][1]) & (az >= room['az'][0]) & (az <= room['az'][1]) & (r >= room['r'][0]) & (r <= room['r'][1])


def overflow_m(box):
    """Greatest distance (m) any corner of the fixture box lies outside the SP-13 room (x walls, azimuth walls, outer radius)."""
    room = ROOM13; worst = 0.0
    for p in box_pts(box, 2):
        x, y, z = p; r = math.hypot(y, z); az = math.atan2(z, y)
        worst = max(worst, room['x'][0]-x, x-room['x'][1], r*(math.radians(room['az'][0])-az), r*(az-math.radians(room['az'][1])), r-room['r'][1])
    return round(max(worst, 0.0), 3)


def fixture_boxes_rb(room):
    """eva3_exits.fixture_boxes with an optional per-fixture base radius `rb` (outer-wall or raised mounting); installed over ex.fixture_boxes in memory."""
    r0 = room['r_m'][0]; out = []
    for fi in room['fixtures']:
        if fi['kind'] == 'zone':
            continue
        rb = fi.get('rb', r0 if fi['kind'] in ('stand', 'rack', 'bench', 'locker') else r0+.90); dx, dw, dh = fi['size']; az = math.radians(fi['az'])
        out.append((P(fi['x'], rb+dh/2, az=az), axes_at(az), (dx, dw, dh)))
    return out


ex.fixture_boxes = fixture_boxes_rb


def fixture_list(base_fixtures):
    return [fi for fi in base_fixtures if fi['kind'] != 'zone']


def boxes_of(fixtures):
    return ex.fixture_boxes(dict(r_m=ROOM13['r'], fixtures=fixtures))      # same list order as the non-zone fixtures


def service_depth(box, others, sides=('+x', '-x', '+t', '-t', '-r')):
    """Greatest free depth (m, capped at 1.0) in front of a fixture on its best side: points over the side face (5 along, heights 0.3-1.5 m
    above its base on the horizontal sides) at depth d must lie in the room and outside every other fixture. '-r' is the face toward the
    ship axis (the front of a wall-mounted unit). Returns (depth, side)."""
    c, ax, sz = box; best = (0.0, None); ax = [np.array(a_) for a_ in ax]
    for side in sides:
        sg = 1 if side[0] == '+' else -1; k = 'xtr'.index(side[1]); depth = 0.0
        for d in np.arange(0.05, 1.0001, 0.05):
            pts = []
            if k < 2:
                other = 1 if k == 0 else 0
                for a_ in np.linspace(-sz[other]/2, sz[other]/2, 5):
                    for hh in np.linspace(-sz[2]/2+0.3, min(sz[2]/2, -sz[2]/2+1.5), 3):
                        loc = [0.0, 0.0, hh]; loc[k] = sg*(sz[k]/2+d); loc[other] = a_; pts.append(np.array(c)+loc[0]*ax[0]+loc[1]*ax[1]+loc[2]*ax[2])
            else:
                for ax_ in np.linspace(-sz[0]/2, sz[0]/2, 5):
                    for at_ in np.linspace(-sz[1]/2, sz[1]/2, 5):
                        pts.append(np.array(c)+ax_*ax[0]+at_*ax[1]+sg*(sz[2]/2+d)*ax[2])
            pts = np.array(pts)
            if not in_room(pts).all() or any((obb_dist(pts, o) < 0).any() for o in others):
                break
            depth = round(float(d), 2)
        if depth > best[0]:
            best = (depth, side)
    return best


def axis_pt(e, r):
    t = math.tan(math.radians(e['beta']))
    return P(e['xp']+(r-1.25)*t, r, az=math.radians(e['az']))


def lane_pts(e, n=15):
    """Axis points of the exit lane above the floor, from r 1.25 to LANE_TOP_R_M or the room's forward wall."""
    t = math.tan(math.radians(e['beta'])); r_end = LANE_TOP_R_M
    if t > 1e-6:
        r_end = min(r_end, 1.25+(ROOM13['x'][1]-0.05-e['xp'])/t)
    return np.array([axis_pt(e, r) for r in np.linspace(1.25, max(r_end, 1.6), n)])


def layout_metrics(fixtures, e, asbuilt_ov):
    """Hard constraints (overflow no worse than as built, no overlap, aperture not stood on) and merit (lane clearance, service depth); None if a hard one fails."""
    bx = boxes_of(fixtures); ids = [fi['id'] for fi in fixtures if fi['kind'] != 'zone']; ov = {i: overflow_m(b) for i, b in zip(ids, bx)}
    if any(ov[i] > asbuilt_ov[i]+1e-9 for i in ids):
        return None
    a = math.radians(e['az']); foot = np.array([P(e['xp'], 1.25, tang=tt, az=a) for tt in np.linspace(-e['D']/2, e['D']/2, 5)]+[P(e['xp']+q, 1.25, az=a) for q in np.linspace(-e['D']/2, e['D']/2, 5)])
    for b in bx:
        if (obb_dist(foot, b) < 0.02).any():
            return None
    for i_, b in enumerate(bx):
        for j_, b2 in enumerate(bx):
            if i_ < j_ and (obb_dist(box_pts(b, 4), b2) < -0.005).any():
                return None
    lane = lane_pts(e); clear = min(float(obb_dist(lane, b).min()) for b in bx); svc = {}
    for nm in ('SP13_DRY_RACK', 'SP13_BENCH'):
        k = ids.index(nm); dep, side = service_depth(bx[k], [b for j, b in enumerate(bx) if j != k]); svc[nm] = dict(depth_m=dep, side=side)
    score = 2*min(clear, 0.8)+sum(min(v['depth_m'], SERVICE_REACH_M) for v in svc.values())
    return dict(overflow_m=ov, lane_clear_m=round(clear, 3), service=svc, score=round(score, 3))


def make_fixture(base, x, az, rot):
    dx, dw, dh = base['size']
    return dict(base, x=round(float(x), 3), az=round(float(az), 1), size=[dw, dx, dh] if rot else [dx, dw, dh], rotated=bool(rot))


def placements(fi, e, asbuilt_ov, lane_min):
    """Every individually feasible placement of one movable fixture (grid: x 0.1 m, az 2.5 deg, quarter turn, floor / outer-wall mounting for the
    lockers): overflow no worse than as built, aperture not stood on, clear of the exit lane by lane_min."""
    out = []; x0, x1 = ROOM13['x']; lane = lane_pts(e); a = math.radians(e['az'])
    foot = np.array([P(e['xp'], 1.25, tang=tt, az=a) for tt in np.linspace(-e['D']/2, e['D']/2, 5)]+[P(e['xp']+q, 1.25, az=a) for q in np.linspace(-e['D']/2, e['D']/2, 5)])
    for rot in ((False,) if fi['id'] == 'SP13_CHARGE_PANEL' else (False, True)):
        dx = fi['size'][1] if rot else fi['size'][0]
        for x in ([fi['x']] if fi['id'] == 'SP13_CHARGE_PANEL' else list(np.arange(x0+dx/2, x1-dx/2+1e-9, 0.1))):
            for az in np.arange(5.0, 75.1, 2.5):
                for rb in ((None, round(ROOM13['r'][1]-fi['size'][2], 2)) if fi['kind'] in ('rack', 'bench', 'locker') else (None,)):
                    f_ = make_fixture(fi, x, az, rot)
                    if rb:
                        f_['rb'] = rb
                    b = boxes_of([f_])[0]
                    if overflow_m(b) > asbuilt_ov[fi['id']]+1e-9 or (obb_dist(foot, b) < 0.02).any() or float(obb_dist(lane, b).min()) < lane_min:
                        continue
                    out.append(f_)
    return out


def search_layouts(base, e, asbuilt_ov, n, rng, lane_min=0.55):
    """Random combinations of the individually feasible placements; hard: no overlaps; merit: lane clearance and service depth (layout_metrics)."""
    pl = {fi['id']: placements(fi, e, asbuilt_ov, lane_min) for fi in base}
    if any(not v for v in pl.values()):
        return []
    found = []
    for _ in range(n):
        fx = [pl[fi['id']][int(rng.integers(len(pl[fi['id']])))] for fi in base]
        m = layout_metrics(fx, e, asbuilt_ov)
        if m:
            found.append((m['score'], -sum(m['overflow_m'].values()), fx, m))
    found.sort(key=lambda q: (q[0], q[1]), reverse=True)
    return found


def exit_valid(e):
    """The aperture ellipse in the floor plane (half length D/2/cos beta along X) must lie inside SP-13's x walls with 0.05 m margin: no exit may open into SP-12."""
    half = e['D']/2/math.cos(math.radians(e['beta'])); return ROOM13['x'][0]+0.05 <= e['xp']-half and e['xp']+half <= ROOM13['x'][1]-0.05


def exit_solid(e):
    t = math.tan(math.radians(e['beta'])); a = math.radians(e['az']); xp = e['xp']
    lo = P(xp-(1.25-0.40)*t, 0.40, az=a); hi = P(xp+0.35*t, 1.60, az=a)
    return lambda: h3.prim_cyl(lo, hi, e['D']/2)


def route_for(e, rc=3.3):
    a = math.radians(e['az']); t = math.tan(math.radians(e['beta'])); xp = e['xp']; xe = xp-(1.25-0.37)*t
    xs = min(xp+(rc-1.25)*t, ROOM13['x'][1]-0.45) if e['beta'] > 0 else xp
    wps = [('R', P(xs, rc, az=a)), ('H', P(xp+(2.0-1.25)*t, 2.0, az=a)), ('D', P(xe, 0.37, az=a)), ('T', (xe-1.4, 0.0, 0.0)), ('T', (xe-3.0, 0.0, 0.0))]
    return ex.smooth(wps, cut=0.5), xe


class Ctx:
    pass


def carriers(ctx):
    c = dict(A=h3.CARRIERS['A'], S=h3.CARRIERS['S'], K=h3.CARRIERS['K'])
    sw = ctx.access['envelopes']['instructor']['EVA_SUITED']
    c['U'] = dict(name='suited crew member, self-propelled (EVA_SUITED instructor, p1_eva_access.json)', shape='capsule', length=sw['length_m'], radius=sw['measured_m']/2)
    return c


def eval_exit(ctx, fixtures, e, label, seeds=SEEDS, which=('A', 'S', 'K', 'U'), keep=False, diffs=()):
    """Free space with the SP-13 room (fit-out = `fixtures`), the exit solid and the trunk to X 107.4, minus `diffs` (extra solids, e.g. a parked
    closure leaf); sweep each carrier over seeds."""
    data2 = copy.deepcopy(ctx.data); data2['sp13']['fixtures'] = fixtures
    obj, tree = ex.build_free(ctx.s, data2, [exit_solid(e)], list(diffs), ex.TRUNK_EXT_X, sp12=False, sp13=True, ref=False, fit=True)
    walls = h3.Walls(ctx.fx, ctx.pts, free=tree); route, xe = route_for(e); cars = carriers(ctx); res = {}
    for cid in which:
        car = cars[cid]; per = []
        for sdv in seeds:
            rng = np.random.default_rng(sdv); per.append(h3.sweep_route(walls, car, route, rng, staff=(cid != 'U')))
        body = [r['least_m'] for r in per]; stf = [r['staff_least_m'] for r in per if r['staff_least_m'] is not None]
        k = int(np.argmin(body)); allv = body+stf; least = min(allv)
        near = per[k]['nearest'] if min(body) <= (min(stf) if stf else 9) else next(r['staff_nearest'] for r in per if r['staff_least_m'] == min(stf))
        res[cid] = dict(least_m=round(least, 3), body_least_m=round(min(body), 3), rescuer_least_m=round(min(stf), 3) if stf else None, status=status(least),
                        nearest=near, seed_spread_m=[round(min(allv), 3), round(max(allv), 3)],
                        by_seed=[dict(seed=sdv, body=r['least_m'], rescuers=r['staff_least_m']) for sdv, r in zip(seeds, per)],
                        zone=per[k]['zone'], by_zone=per[k]['by_zone'], head=per[k]['head'], axis=per[k]['axis'], roll=per[k]['roll'])
        print('WF_SP13', label, cid, res[cid]['least_m'], res[cid]['status'], res[cid]['nearest'], res[cid]['seed_spread_m'], flush=True)
    if keep:
        return res, obj
    bpy.data.objects.remove(obj)
    return res, None


# ---------------------------------------------------------------------------------------------------------------------------------
# exit solid screens: vehicle, spine cut, closure pocket, independence

def exit_vehicle_screen(ctx, e):
    clr = ctx.s['prototype']['mechanical_clearance_m']; a = math.radians(e['az']); t = math.tan(math.radians(e['beta'])); D = e['D']; hits = set(); inside = True
    xs = [(e['xp']-(1.25-0.40)*t, 0.40), (e['xp']+0.35*t, 1.60)]; n = 12; ig = ('Structural_Spine', 'Crew_Trunk', 'Trunk_Fit_', 'Crew_Trunk_')
    for k in range(n):
        (xa, ra), (xb, rb) = [(xs[0][0]+(xs[1][0]-xs[0][0])*q/n, xs[0][1]+(xs[1][1]-xs[0][1])*q/n) for q in (k, k+1)]
        b = sv.box(min(xa, xb)-D/2-0.02, max(xa, xb)+D/2+0.02, a, max(0.0, min(ra, rb)-D/2), max(ra, rb)+D/2, D/2, clr)
        hits |= ctx.obs.hits(b, ignore=ig); inside &= sv.inside_hull(ctx.s, b)
    return dict(hits=sorted(hits), inside_hull=bool(inside), status='CLEAR' if not hits and inside else 'BLOCKED', refuge_objects_hit=sorted(h for h in hits if 'Refuge' in h))


def exit_spine_cut_x(ctx, e):
    """X length over which the exit solid lies inside the spine-core annulus (trunk wall to spine_core_radius_m): a structural cut, OPEN."""
    core = ctx.s['prototype']['spine_core_radius_m']; w = ctx.s['crew_transfer']['passage_wall_m']; tr = ctx.s['crew_transfer']['trunk_clear_radius_m']
    t = math.tan(math.radians(e['beta'])); n = 0; half = e['D']/2/math.cos(math.radians(e['beta']))
    for x in np.arange(100.0, 110.0, 0.02):
        for r in np.arange(tr+w, core, 0.02):
            ax = e['xp']+(r-1.25)*t
            if abs(x-ax) <= half:
                n += 1; break
    return round(n*0.02, 2)


def seg_dist(p0, p1, q0, q1, n=60):
    a = np.linspace(0, 1, n)[:, None]; A = np.array(p0)+(np.array(p1)-np.array(p0))*a; B = np.array(q0)+(np.array(q1)-np.array(q0))*a
    d = np.linalg.norm(A[:, None, :]-B[None, :, :], axis=2); return float(d.min())


def sp12_solids():
    """The SP-12 exit solids of eva3_exits (airlock axis 50 deg): axis segments + radius, and the N1 slot box."""
    xb = 101.8494; AZ = ex.AZ; out = {}
    for D in (0.90, 1.10):
        out[f'N0_branch_{D:.2f}'] = dict(kind='cyl', a=P(xb, 0.40), b=P(xb, 1.45), r=D/2)
    for D, nm in ((1.10, 'N2_oblique15_1.10'), (1.20, 'N3_oblique15_1.20')):
        (xa, ra), (xe, re), t = ex.duct_axis(ex.PSI); out[nm] = dict(kind='cyl', a=P(xe, re), b=P(xa, ra), r=D/2)
    out['N1_axial_slot'] = dict(kind='box', box=(P(ex.XS, 0.85), axes_at(), (ex.SLOT_L, ex.SLOT_W, 1.20)))
    return out


def independence(ctx, e, layout_label):
    s = ctx.s; a = math.radians(e['az']); t = math.tan(math.radians(e['beta']))
    p0 = P(e['xp']-(1.25-0.40)*t, 0.40, az=a); p1 = P(e['xp']+0.35*t, 1.60, az=a); sep = {}
    for nm, v in sp12_solids().items():
        if v['kind'] == 'cyl':
            sep[nm] = round(seg_dist(p0, p1, v['a'], v['b'])-e['D']/2-v['r'], 3)
        else:
            pts = np.array([np.array(p0)+(np.array(p1)-np.array(p0))*q for q in np.linspace(0, 1, 60)])
            sep[nm] = round(float(obb_dist(pts, v['box']).min())-e['D']/2, 3)
    eva = {q['name']: q for q in ed.eva_elements(s, ctx.data, ctx.lead)[0]}
    # duct solid points (grid in the cylinder) against the SP-12 room, the SP-11 chamber and the SP-12 branch neck
    pts = []; ax = np.array(p1)-np.array(p0); L = np.linalg.norm(ax); ax /= L
    for q in np.linspace(0, L, int(L/0.05)+1):
        for ang in range(0, 360, 30):
            for rr in (0.0, e['D']/4, e['D']/2):
                tv = np.cross(ax, (0, 1, 0)); tv = tv/np.linalg.norm(tv); uv = np.cross(ax, tv)
                pts.append(np.array(p0)+ax*q+rr*(math.cos(math.radians(ang))*tv+math.sin(math.radians(ang))*uv))
    dist = {}
    for n in ('SP12', 'SP11_chamber', 'SP12_branch'):
        samp = ed.samples(eva[n]); kd = KDTree(len(samp)); [kd.insert(Vector(p_), i) for i, p_ in enumerate(samp)]; kd.balance()
        inside_n = sum(1 for p_ in pts if ed.inside(eva[n], tuple(p_) ) and np.hypot(p_[1], p_[2]) >= 1.25)
        dist[n] = dict(solid_points_inside_above_r1_25=inside_n, min_distance_solid_to_room_m=round(min(kd.find(Vector(p_))[2] for p_ in pts[::7]), 2))
    return dict(
        exits=dict(SP12=['SP-11 inner plug 1.20 m (chamber side only)', 'SP-12 exit closure (N0 branch / N1 slot / N2-N3 duct) between SP-12 and the trunk extension'],
                   SP13=[f"SP-13 exit closure (aperture {e['D']:.2f} m, axis {e['beta']:.0f} deg aft of radial at az {e['az']:.0f} deg, X {e['xp']:.2f}) between SP-13 and the trunk extension"]),
        shared_closures=[], shared_volumes=['trunk extension X 102.45-107.4 and the built trunk (destination of both exits; shirt-sleeve volume, neither SP-12 nor SP-13)'],
        not_shared=['SP-12/SP-13 door (neither exit uses it)', 'SP-11 inner plug and chamber (SP-12 only)', 'SP-12 donning stands / buddy zone / exit closure pocket (SP-12 only)',
                    'SP-12 and SP-13 ventilation loops (separate per topology; isolation valves OPEN)'],
        route_uses_sp12_volume=False, route_basis='sweeps run in a free space built with sp12=False: SP-12 room, SP-11 chamber and branch neck are not in the route volume',
        solid_separation_to_sp12_exit_solids_m=sep, exit_solid_vs_sp12_volumes=dict(dist, note='solid sample points (axis, half radius, surface; 0.05 m steps along the axis, every 7th) to the 0.1 m sample grid of each SP-12 element, so +-0.1 m'),
        pressure_isolation_points=['SP-13 exit closure (seats from SP-13 / trunk side OPEN)', 'SP-12 exit closure', 'SP-12/SP-13 door', 'district hatch at the trunk end'],
        fire_heat_notes=['SP-13 hosts battery charging and drying (thermal/fire load of the pair) and is the room the SP-13 exit evacuates',
                         'SP-12 hosts O2 preparation; its closure and the SP-11 plug isolate it. A fire or leak in one room leaves the other exit available as long as the trunk extension stays habitable (shared volume, OPEN)'],
        aperture_aft_edge_to_sp13_aft_wall_m=round(e['xp']-e['D']/2/math.cos(math.radians(e['beta']))-ROOM13['x'][0], 3),
        layout=layout_label,
        status='PROTOTYPE: no shared closure, no shared room volume; the destination volume (trunk extension / trunk) is shared')


def room_margin(pts):
    """Smallest distance (m) of points to the SP-13 room's x walls and azimuth walls (negative = outside); the floor and ceiling are not counted."""
    room = ROOM13; p = np.asarray(pts, float); r = np.hypot(p[:, 1], p[:, 2]); az = np.arctan2(p[:, 2], p[:, 1])
    return float(np.min(np.stack([p[:, 0]-room['x'][0], room['x'][1]-p[:, 0], r*(az-math.radians(room['az'][0])), r*(math.radians(room['az'][1])-az)])))


def closure_pocket(fixtures, e):
    """Sliding closure leaf parked beside the aperture on the SP-13 floor: radius D/2/cos(beta)+0.05 (the aperture ellipse's long half-axis), parked 2r+0.05 away along +-x or
    +-tangent at r 1.30; clearance = the smaller of the distance to every fixture and the margin to the room's walls (best of four directions)."""
    bx = boxes_of(fixtures); a = math.radians(e['az']); rl = e['D']/2/math.cos(math.radians(e['beta']))+0.05; best = (-9, None); allr = {}
    for nm, (dxs, dts) in dict(plus_x=(1, 0), minus_x=(-1, 0), plus_t=(0, 1), minus_t=(0, -1)).items():
        pts = []
        for ang in range(0, 360, 20):
            for rr in (rl, rl/2):
                pts.append(P(e['xp']+dxs*(2*rl+0.05)+rr*math.cos(math.radians(ang)), 1.30, tang=dts*(2*rl+0.05)+rr*math.sin(math.radians(ang)), az=a))
        pts = np.array(pts); d_fx = min(float(obb_dist(pts, b).min()) for b in bx); d_room = room_margin(pts); d = min(d_fx, d_room)
        allr[nm] = dict(least_m=round(d, 3), to_fixtures_m=round(d_fx, 3), to_room_walls_m=round(d_room, 3))
        if d > best[0]:
            best = (d, nm)
    return dict(least_m=round(best[0], 3), direction=best[1], by_direction=allr, status=status(best[0]),
                note=f'parked leaf radius {rl:.2f} m (the aperture ellipse long half-axis + 0.05), {2*rl+0.05:.2f} m from the aperture centre on the SP-13 floor; a sliding leaf needs a free floor strip that SP-13 (2.15 m x 1.5 m floor) does not have; the closure type is OPEN')


def exit_info(ctx, e):
    t = math.tan(math.radians(e['beta'])); D = e['D']; L = (1.25-0.37)/math.cos(math.radians(e['beta']))
    sill_aft = e['xp']-(D/2)/math.cos(math.radians(e['beta']))-ROOM13['x'][0]
    return dict(aperture_m=D, xp=e['xp'], az_deg=e['az'], beta_deg=e['beta'], duct_length_m=round(L, 2), exit_shell_m2=round(math.pi*D*L, 2),
                exit_shell_mass_kg_not_credited=round(math.pi*D*L*SHELL_KG_M2, 0), landing_x=round(e['xp']-(1.25-0.37)*t, 2),
                thrust_floor_sill_height_m=round(max(sill_aft, 0.0), 2),
                thrust_note='under 1.5 g aft-down the SP-13 floor is its aft wall (X 104.95): sill_height is the rise of the aperture lower edge above that wall (0 = floor level)')


# ---------------------------------------------------------------------------------------------------------------------------------
# renders

def render_sp13(ctx, obj, fixtures, e, res, name, out, extra=()):
    sc = bpy.context.scene; keep = [o for o in bpy.data.objects if not o.hide_render and o is not obj]
    for o in keep:
        o.hide_render = True
    made = []; obj.hide_render = False; a = math.radians(e['az']); ax = axes_at(a)
    mat = bpy.data.materials.new('free'); mat.diffuse_color = (.3, .6, .9, 1); obj.data.materials.append(mat)
    cutter = lambda: h3.prim_box(P(106.0, 3.0, 10.5, az=a), ax, (30.0, 21.0, 14.0))
    h3.boolean(obj, cutter(), 'DIFFERENCE')
    gm = bpy.data.materials.new('fixture'); gm.diffuse_color = (.55, .55, .55, 1)
    for b in boxes_of(fixtures):
        o = h3.prim_box(*b); o.data.materials.append(gm); h3.boolean(o, cutter(), 'DIFFERENCE'); made.append(o)
    lm = bpy.data.materials.new('leaf'); lm.diffuse_color = (.85, .2, .2, 1)
    for mk in extra:                                    # closure leaves (red), not cut: they stand inside the room
        o = mk(); o.data.materials.append(lm); made.append(o)
    for cid, col in (('S', (1.0, .5, .1, 1)),):          # the worst-seed pose of carrier S
        r = res.get(cid)
        if not r:
            continue
        car = carriers(ctx)[cid]; head, d, roll = r['head'], r['axis'], r['roll']
        if car['shape'] == 'box':
            vs, fs = h3.box_mesh(h3.boxes(car, head, d, roll), 0.0); me = bpy.data.meshes.new(cid); me.from_pydata(vs, [], fs); ob = ex.link(me, cid)
        else:
            p0 = np.asarray(head)+np.asarray(d)*car['radius']; p1 = np.asarray(head)+np.asarray(d)*(car['length']-car['radius']); ob = h3.prim_cyl(tuple(p0), tuple(p1), car['radius'])
        m = bpy.data.materials.new(cid); m.diffuse_color = col; ob.data.materials.append(m); made.append(ob)
    cam = bpy.data.objects.new('CAM_SP13', bpy.data.cameras.new('CAM_SP13')); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'; sc.render.resolution_x, sc.render.resolution_y = 1400, 800
    look = Vector((-ax[1][0], -ax[1][1], -ax[1][2])); up = Vector(ax[2]); z = -look.normalized(); x = up.cross(z).normalized(); y = z.cross(x)
    cam.rotation_euler = Matrix((x, y, z)).transposed().to_euler(); cam.data.type = 'ORTHO'; cam.data.ortho_scale = 9.6; cam.data.clip_start = .1; cam.data.clip_end = 60
    cam.location = Vector(P(105.9, 2.75, 25.0, az=a)); sc.render.filepath = str(out/f'{name}.png'); bpy.ops.render.render(write_still=True)
    for o in made:
        bpy.data.objects.remove(o)
    bpy.data.objects.remove(cam)
    for o in keep:
        o.hide_render = False
    return f'{name}.png'


# ---------------------------------------------------------------------------------------------------------------------------------
# part A driver

def load_ctx():
    c = Ctx(); c.s = ex.load(ROOT)[0]; c.data = es.load(ROOT); global ROOM13
    q = c.data['sp13']; ROOM13 = dict(x=tuple(q['x_m']), az=tuple(q['az_deg']), r=tuple(q['r_m']))
    c.access = json.loads((ROOT/'references/p1_eva_access.json').read_text())
    sp = json.loads((ROOT/'references/p1_eva_sp11.json').read_text()); c.lead = next(r for r in sp['rows'] if abs(r['aperture_m']-c.data['sp11_eva3']['lead_m']) < 1e-9)
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(c.s['vehicle']['asset']+'.blend'))); bpy.context.scene.frame_set(1)
    c.obs = sv.Obstacles(); ins = cs.load_inspect(); recs = cs.scene(c.s, ins, 1.0); c.fx = h3.fixtures(recs)
    c.pts = [(x_, y, z) for x_ in np.linspace(95, 107.5, 26) for y in (-3, 0, 3) for z in (-3, 0, 3)]
    return c


def worst_of(res):
    k = min(res, key=lambda q: res[q]['least_m']); return k, res[k]['least_m']


def run_sp13(ctx, out, exits, n_search=250):
    rng = np.random.default_rng(2710); base = [dict(f) for f in ctx.data['sp13']['fixtures']]; nz = fixture_list(base); ids = [f['id'] for f in nz]
    asb_ov = {i: overflow_m(b) for i, b in zip(ids, boxes_of(nz))}; results = dict(asbuilt_overflow_m=asb_ov); evals = {}
    # 1. control: as-built fit-out, the EVA-003 follow-up radial port (D 1.10, az 45, X 106.025)
    e0 = dict(D=EXIT_D_M, xp=106.025, az=45.0, beta=0.0)
    r0, obj0 = eval_exit(ctx, nz, e0, 'CONTROL', keep=True); evals['CONTROL'] = dict(exit=e0, fixtures=nz, res=r0)
    results['renders'] = [render_sp13(ctx, obj0, nz, e0, r0, 'sp13_control_asbuilt_radial', out)]; bpy.data.objects.remove(obj0)
    # 2. layout search per exit (exits chosen from the bare-room scan, scan_exits)
    cands = []; t0 = time.time()
    for e in exits:
        assert exit_valid(e), e
        fnd = search_layouts(nz, e, asb_ov, n_search, rng)
        print('WF_SP13 search', e, len(fnd), round(time.time()-t0), 's', flush=True)
        if fnd:
            cands.append((e['beta'], fnd[0][3]['lane_clear_m'], e, fnd[0][2], fnd[0][3], len(fnd), fnd[0][0]))
    results['search'] = [dict(exit=c[2], lane_clear_m=c[1], feasible_layouts=c[5], score=c[6], service=c[4]['service'], overflow_m=c[4]['overflow_m']) for c in cands]
    # 3. evaluate the best arrangement of every exit
    for i, c in enumerate(cands):
        lab = f"REARR_D{c[2]['D']*100:.0f}_b{c[0]:.0f}_x{c[2]['xp']:.2f}_az{c[2]['az']:.0f}"; r, obj = eval_exit(ctx, c[3], c[2], lab, keep=True)
        evals[lab] = dict(exit=c[2], fixtures=c[3], res=r, metrics=c[4]); bpy.data.objects.remove(obj)
    results['evals'] = evals
    return results



# ---------------------------------------------------------------------------------------------------------------------------------
# part B: trunk ladder vs the dock mouth and the district port (pure geometry on human_entry's ladder and openings)

def ladder_geom(s, th_deg):
    h = s['human_entry']; L0 = he.trunk_ladder(s); th = math.radians(th_deg); rl, phi = L0['rl'], L0['phi']
    return dict(th=th, rl=rl, phi=phi, floor=L0['floor'], rungs=L0['rungs'], top_built=L0['top'], rail_r=L0['rail_r'],
                lines={'stile_a': (rl, th-phi, ROD_R_M), 'stile_b': (rl, th+phi, ROD_R_M), 'rail': (L0['rail_r'], th, h['spoke_arrest_rail_radius_m'])})


def ops_for(s, alpha=None, sp13=None):
    ops = [tuple(o) for o in he.openings(s)]
    if alpha is not None:
        ops.append(('District_Port', 104.1, math.radians(alpha), 0.45))
    ops.append(('SP12_Exit_N1_slot', ex.XS, ex.AZ, 0.55))
    if sp13:
        ops.append(('SP13_Exit', sp13['xp'], math.radians(sp13['az']), sp13['D']/2))
    return ops


def line_blocks(rho, ang, ops, margin):
    """(a, b, name) intervals of X blocked at radius rho and angle by each opening at `margin` (the rule of human_entry.clear_spans)."""
    out = []
    for n, x, th, r in ops:
        d = ct.angle_diff(ang, th); lat = rho*math.sin(d)
        if math.cos(d) <= 0 or lat >= r+margin:
            continue
        half = math.sqrt((r+margin)**2-lat**2); out.append((x-half, x+half, n))
    return out


def merge_gaps(blocks, x0, x1):
    gaps = []
    for a, b, n in sorted(blocks):
        a, b = max(a, x0), min(b, x1)
        if b <= a:
            continue
        if gaps and a <= gaps[-1][1]+1e-9:
            gaps[-1][1] = max(gaps[-1][1], b); gaps[-1][2].add(n)
        else:
            gaps.append([a, b, {n}])
    return [(round(a, 3), round(b, 3), sorted(ns)) for a, b, ns in gaps]


def signed_gap(rho, ang, rr, ops, xs, skip):
    """Signed gap (m) from the rod surface to the nearest opening edge in the unrolled wall projection (positive = clear of the opening)."""
    best = (math.inf, None, None)
    for n, x, th, r in ops:
        d = ct.angle_diff(ang, th)
        if math.cos(d) <= 0:
            continue
        lat = rho*math.sin(d); g = np.hypot(xs-x, lat)-r-rr
        for a, b in skip:
            g = np.where((xs >= a) & (xs <= b), np.inf, g)
        i = int(np.argmin(g))
        if g[i] < best[0]:
            best = (float(g[i]), n, float(xs[i]))
    return best


def ladder_case(s, th_deg, alpha, sp13, x_top=LADDER_TOP_X):
    G = ladder_geom(s, th_deg); ops = ops_for(s, alpha, sp13); xs = np.arange(G['floor'], x_top+1e-9, 0.01); out = dict(theta_deg=th_deg, port_deg=alpha, lines={})
    dock_x = 99.4; worst0 = (math.inf, None, None, None)
    span = {0.0: 0.0, 0.2: 0.0}; extra = {0.0: [], 0.2: []}
    for ln, (rho, ang, rr) in G['lines'].items():
        row = {}
        for m in (0.0, 0.2):
            gaps = merge_gaps(line_blocks(rho, ang, ops, m), G['floor'], x_top)
            dock = [g for g in gaps if g[0] <= dock_x <= g[1]]; oth = [g for g in gaps if g not in dock]
            row[f'margin_{m:.2f}'] = dict(gaps=gaps, dock_gap_m=round(dock[0][1]-dock[0][0], 3) if dock else 0.0, other_gaps=oth)
            if dock:
                span[m] = max(span[m], dock[0][1]-dock[0][0])
            extra[m] += [dict(line=ln, a=g[0], b=g[1], by=g[2]) for g in oth]
        skip = [(g[0], g[1]) for g in merge_gaps(line_blocks(rho, ang, ops, 0.2), G['floor'], x_top) if g[0] <= dock_x <= g[1]]
        g0 = signed_gap(rho, ang, rr, ops, xs, skip)
        row['least_gap_to_opening_edge_m'] = dict(value=round(g0[0], 3), opening=g0[1], at_x=None if g0[2] is None else round(g0[2], 2))
        if g0[0] < worst0[0]:
            worst0 = (g0[0], ln, g0[1], g0[2])
        dp = next(o for o in ops if o[0] == 'Crew_Connector_Dock_Primary'); d = ct.angle_diff(ang, dp[2])
        row['arc_beyond_dock_primary_cutoff_m'] = round(rho*(d-math.pi/2), 3)
        out['lines'][ln] = row
    out['dock_window_m'] = {f'{k:.1f}': round(v, 3) for k, v in span.items()}
    out['dock_window_vs_accepted_bridge'] = dict(accepted_member_gap_m=BRIDGE_ACCEPTED_M, margin_0_20_gap_m=round(span[0.2], 3), shorter_by_m=round(BRIDGE_ACCEPTED_M-span[0.2], 3))
    out['unbridged_extra_gaps'] = {f'margin_{m:.2f}': v for m, v in extra.items()}
    out['continuous_with_one_dock_bridge'] = {f'margin_{m:.2f}': bool((not extra[m]) and span[m] <= BRIDGE_ACCEPTED_M+1e-9) for m in (0.0, 0.2)}
    out['least_m_margin0'] = round(worst0[0], 3); out['least_at'] = dict(line=worst0[1], opening=worst0[2], x=None if worst0[3] is None else round(worst0[3], 2))
    out['least_m_vs_0_20_margin'] = round(worst0[0]-0.2, 3)
    ds = next(o for o in ops if o[0] == 'Crew_Connector_Dock_Service')
    # share of the Dock_Service mouth (r 0.45 circle, lateral axis) covered by the ladder's 0.40 m wide strip
    c_lat = G['rl']*math.sin(G['th']-ds[2]); half_w = 0.20; R = ds[3]; tt = np.linspace(-R, R, 801); ww = np.sqrt(np.maximum(R*R-tt*tt, 0))
    cov = float(np.sum(ww[(tt >= c_lat-half_w) & (tt <= c_lat+half_w)])/np.sum(ww))
    out['dock_service_mouth_covered_by_ladder_strip'] = round(cov, 3)
    return out


def hoist_margin(s, th_deg):
    """Carrier A (box circumradius) and S (capsule) on the hoist line 0.25 m off the axis toward 105 deg (HUM-003) against the ladder rods,
    cross-section distance (the carrier is parallel to the axis): margin to the nearest stile / rail."""
    G = ladder_geom(s, th_deg); c = np.array([0.25*math.cos(math.radians(105)), 0.25*math.sin(math.radians(105))]); out = {}
    for cid, rad in (('A', math.hypot(0.275, 0.15)), ('S', h3.CARRIERS['S']['radius'])):
        best = math.inf
        for ln, (rho, ang, rr) in G['lines'].items():
            p = np.array([rho*math.cos(ang), rho*math.sin(ang)]); best = min(best, float(np.linalg.norm(p-c))-rr-rad)
        out[cid] = round(best, 3)
    return out


def fixture_tree(records):
    """One BVH of the built trunk fixtures (handrails, brackets, lights, frames, port rails) minus the ladder and its arrest rail."""
    from mathutils.bvhtree import BVHTree
    vs, fs, names, foffs = [], [], [], []
    for q in records:
        n = q['name']
        if n in h3.WALL_NAMES or not n.startswith(h3.FIXTURE_PREFIX) or 'Ladder' in n or 'Arrest_Rail' in n or n.startswith('Refuge_') or n.startswith('Survival_'):
            continue
        o = len(vs); foffs.append(len(fs)); names.append(n); vs += [tuple(v) for v in q['vs']]; fs += [tuple(i+o for i in f) for f in q['fs']]
    return BVHTree.FromPolygons(vs, fs), names, foffs


def ladder_fixture_clearance(ctx, th_deg, tree_pack):
    tree, names, foffs = tree_pack; G = ladder_geom(ctx.s, th_deg); best = (math.inf, None, None, None)
    nm = lambda idx: names[bisect.bisect_right(foffs, idx)-1]
    for ln, (rho, ang, rr) in G['lines'].items():
        for x in np.arange(G['floor'], 100.0, 0.05):
            p = Vector((x, rho*math.cos(ang), rho*math.sin(ang))); loc, n, idx, dist = tree.find_nearest(p)
            if loc is not None and dist-rr < best[0]:
                best = (dist-rr, ln, round(float(x), 2), nm(idx))
    for x in G['rungs']:
        for k in range(1, 5):
            q = k/5; a_ = G['th']-G['phi']+2*G['phi']*q; p = Vector((x, G['rl']*math.cos(a_), G['rl']*math.sin(a_))); loc, n, idx, dist = tree.find_nearest(p)
            if loc is not None and dist-ROD_R_M < best[0]:
                best = (dist-ROD_R_M, 'rung', round(float(x), 2), nm(idx))
    return best


def port_options(ctx, workshop_deg=240):
    """(b): the workshop port moved to alpha on the workshop's inner face (workshop stays at 240) and the workshop rotated to alpha: screens."""
    s, obs = ctx.s, ctx.obs; tr = s['crew_transfer']['trunk_clear_radius_m']; w = s['crew_transfer']['passage_wall_m']; ro = sd.PORT_CLEAR/2+w
    eva, br = ed.eva_elements(s, ctx.data, ctx.lead); o, R, els, ext = ed.serv_elements(s, obs, math.radians(workshop_deg), 'A', math.radians(210), 106.3)
    W = R['workshop']; d = W['u'][0]; half_t = W['t'][1]; xport = 104.1; res = {}
    for alpha in range(180, 245, 5):
        dphi = math.radians(alpha-workshop_deg); lat = d*math.tan(dphi); r1 = d/math.cos(dphi)+w
        fits_face = abs(lat)+ro <= half_t+1e-9 and abs(dphi) < math.radians(80)
        pe = ed.cylinder('district_port', xport, alpha, tr, r1, ro); sc = ed.screen(s, obs, pe, ('Structural_Spine', 'Crew_Trunk'))
        ov = [e['name'] for e in eva+[e for e in els if e['name'] in ('cell',)] if any(ed.inside(e, p_) for p_ in ed.samples(pe)[::2])]
        res[alpha] = dict(tangential_offset_on_face_m=round(lat, 3), port_tube_outer_r_m=round(r1, 3), fits_workshop_face=bool(fits_face), vehicle_hits=sc['hits'], inside_hull=sc['inside_hull'], overlaps_eva_or_cell=ov,
                          status='CLEAR' if fits_face and not sc['hits'] and sc['inside_hull'] and not ov else 'BLOCKED')
    rot = {}
    for alpha in range(150, 360, 5):
        o2, R2, els2, ext2 = ed.serv_elements(s, obs, math.radians(alpha), 'A', math.radians(210), 106.3)
        core = [e for e in els2 if e['name'] in ('workshop', 'cell') or e['name'].startswith('passage')]; ok, rs = ed.clean(s, obs, core, eva)
        runs = [o2.get('port', {}).get('run')]; ok = ok and all(not r_['hits'] for r_ in runs if r_)
        rot[alpha] = ok
    return res, [a for a, v in rot.items() if v]


def run_ladder(ctx, out, sp13):
    s = ctx.s; res = dict(sp13_exit_used=sp13); recs = cs.scene(s, cs.load_inspect(), 1.0); tp = fixture_tree(recs)
    res['reference'] = dict(built_ladder_deg=285.0, case_ref=ladder_case(s, 285.0, 240.0, sp13), fixture_clearance_m=None)
    f0 = ladder_fixture_clearance(ctx, 285.0, tp); res['reference']['fixture_clearance_m'] = dict(least_m=round(f0[0], 3), line=f0[1], x=f0[2], nearest=f0[3])
    res['reference']['hoist_offset_margin_m'] = hoist_margin(s, 285.0)
    res['option_a_ladder_relocated'] = {}
    for th in (285.0, 295.0, 300.0, 305.0, 310.0, 315.0, 320.0, 325.0, 330.0, 335.0):
        c = ladder_case(s, th, 240.0, sp13); f = ladder_fixture_clearance(ctx, th, tp)
        c['fixture_clearance_m'] = dict(least_m=round(f[0], 3), line=f[1], x=f[2], nearest=f[3]); c['hoist_offset_margin_m'] = hoist_margin(s, th); res['option_a_ladder_relocated'][str(int(th))] = c
        print('WF_LADDER a', th, c['least_m_margin0'], c['dock_window_m'], c['continuous_with_one_dock_bridge'], round(f[0], 3), flush=True)
    res['option_b_port_moved'] = {}
    ports, rot_ok = port_options(ctx)
    for al in range(180, 245, 5):
        c = ladder_case(s, 285.0, float(al), sp13); c['port_screen'] = ports[al]; res['option_b_port_moved'][str(al)] = c
        print('WF_LADDER b', al, c['least_m_margin0'], c['continuous_with_one_dock_bridge'], ports[al]['status'], flush=True)
    res['workshop_rotation_clear_angles_deg_5deg_scan'] = rot_ok
    G = ladder_geom(s, 285.0)
    res['ladder_built'] = dict(floor_x=round(G['floor'], 3), top_built_x=round(G['top_built'], 3), to_x=LADDER_TOP_X, built_length_m=round(G['top_built']-G['floor'], 2), rungs=len(G['rungs']))
    return res


# ---------------------------------------------------------------------------------------------------------------------------------
# part C: SP-52 warm module at a standoff from the workshop wall (GEOMETRY ONLY; heat transfer OPEN)

def face_poly(b, x):
    """Corners (y, z) of the (u, t) rectangle of a box dict, in the plane X = x (the box is rotated by its phi about the ship axis)."""
    c, s_ = math.cos(b['phi']), math.sin(b['phi'])
    return [(u*c-t*s_, u*s_+t*c) for u, t in ((b['u'][0], b['t'][0]), (b['u'][1], b['t'][0]), (b['u'][1], b['t'][1]), (b['u'][0], b['t'][1]))]


def poly_area(p):
    return 0.5*abs(sum(p[i][0]*p[(i+1) % len(p)][1]-p[(i+1) % len(p)][0]*p[i][1] for i in range(len(p))))


def clip(subject, clipper):
    """Sutherland-Hodgman: convex `clipper` against `subject`."""
    def ccw(p):
        a = sum(p[i][0]*p[(i+1) % len(p)][1]-p[(i+1) % len(p)][0]*p[i][1] for i in range(len(p)))
        return list(p) if a > 0 else list(p)[::-1]
    out = ccw(subject); cl = ccw(clipper)
    for i in range(len(cl)):
        a, b = cl[i], cl[(i+1) % len(cl)]; inp = out; out = []
        if not inp:
            break
        side = lambda p: (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
        for j in range(len(inp)):
            p, q = inp[j], inp[(j+1) % len(inp)]; sp, sq = side(p), side(q)
            if sp >= 0:
                out.append(p)
            if (sp >= 0) != (sq >= 0):
                t = sp/(sp-sq); out.append((p[0]+t*(q[0]-p[0]), p[1]+t*(q[1]-p[1])))
    return out


def grid_in_poly(poly, h=0.05):
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]; pts = []
    P_ = poly if sum(poly[i][0]*poly[(i+1) % 4][1]-poly[(i+1) % 4][0]*poly[i][1] for i in range(4)) > 0 else poly[::-1]
    for x in np.arange(min(xs)+h/2, max(xs), h):
        for y in np.arange(min(ys)+h/2, max(ys), h):
            if all((P_[(i+1) % 4][0]-P_[i][0])*(y-P_[i][1])-(P_[(i+1) % 4][1]-P_[i][1])*(x-P_[i][0]) >= 0 for i in range(4)):
                pts.append((x, y))
    return np.array(pts)


def view_factor_parallel(poly1, poly2, gap, h=0.05):
    """GEOMETRY ONLY: diffuse view factor from polygon 1 to polygon 2, parallel planes `gap` apart: (1/A1) double integral of d^2/(pi r^4)."""
    p1 = grid_in_poly(poly1, h); p2 = grid_in_poly(poly2, h); a1 = len(p1)*h*h; a2 = len(p2)*h*h; tot = 0.0
    for i in range(0, len(p1), 200):
        d2 = ((p1[i:i+200, None, :]-p2[None, :, :])**2).sum(2)+gap*gap; tot += float((gap*gap/(math.pi*d2*d2)).sum())
    return tot*h*h*h*h/a1, a1, a2


def run_sp52(ctx, out):
    s, obs = ctx.s, ctx.obs; c = s['prototype']['mechanical_clearance_m']; w = s['human_entry']['chamber_wall_m']; eva, br = ed.eva_elements(s, ctx.data, ctx.lead)
    dist = json.loads((ROOT/'references/p1_eva_district.json').read_text())['layouts']['L1-A']; wd, md, mx = dist['workshop_deg'], dist['warm_deg'], dist['warm_x0']
    o, R, els, ext = ed.serv_elements(s, obs, math.radians(wd), 'A', math.radians(md), mx); W = R['workshop']; x1w = W['x'][1]
    res = dict(layout=dict(workshop_deg=wd, warm_deg=md, scan_warm_x0=mx, workshop_x=[round(v, 3) for v in W['x']], workshop_forward_outer_face_x=round(x1w, 3),
                           scan_standoff_m=round(mx-x1w, 3), chamber_wall_m=w, module_clear_m=dict(tangential=sd.WARM[0], radial=sd.WARM[1], axial=sd.WARM[2]), robot_cube_m=sd.ROBOT),
               rows={})
    uvec = lambda ph: Vector((0, math.cos(ph), math.sin(ph))); tvec = lambda ph: Vector((0, -math.sin(ph), math.cos(ph)))
    for so in STANDOFFS_M:
        x0 = x1w+so; o2, R2, els2, _ = ed.serv_elements(s, obs, math.radians(wd), 'A', math.radians(md), x0); M = R2['warm']; Wb = R2['workshop']
        wm = next(e for e in els2 if e['name'] == 'warm_SP52'); others = eva+[e for e in els2 if e['name'] in ('workshop', 'cell')]; ok, wres = ed.clean(s, obs, [wm], others)
        wres = wres['warm_SP52']; gap = M['x'][0]-Wb['x'][1]
        pm = face_poly(M, M['x'][0]); pw = face_poly(Wb, Wb['x'][1]); ov_poly = clip(pm, pw); ov_a = poly_area(ov_poly) if len(ov_poly) >= 3 else 0.0
        F, a1, a2 = view_factor_parallel(pm, pw, gap)
        row = dict(standoff_m=round(gap, 3), warm_x=[round(v, 3) for v in M['x']], warm_u_m=[round(v, 3) for v in M['u']], warm_tangential_m=round(M['t'][1]-M['t'][0], 3),
                   vehicle_hits=wres['hits'], inside_hull=wres['inside_hull'], eva_overlap=wres['eva_overlap'], shield_column_gap_m=round(108.5-M['x'][1], 3),
                   facing=dict(warm_aft_face_m2=round(poly_area(pm), 3), workshop_forward_face_m2=round(poly_area(pw), 3), overlap_m2=round(ov_a, 3),
                               overlap_fraction_of_warm_face=round(ov_a/poly_area(pm), 3),
                               view_factor_warm_face_to_workshop_wall=round(F, 3), view_factor_note='GEOMETRY ONLY: diffuse view factor between the two parallel planes at the standoff, grid 0.05 m; no emissivity, temperature or heat flow is implied'))
        pts = []
        for u in np.linspace(M['u'][0], M['u'][1], 5):
            for x in np.linspace(M['x'][0], M['x'][1], 5):
                for t in (M['t'][0], M['t'][1]):
                    pts.append(Vector((x, 0, 0))+uvec(M['phi'])*u+tvec(M['phi'])*t)
        for x in np.linspace(M['x'][0], M['x'][1], 5):
            for t in np.linspace(M['t'][0], M['t'][1], 5):
                for u in (M['u'][0], M['u'][1]):
                    pts.append(Vector((x, 0, 0))+uvec(M['phi'])*u+tvec(M['phi'])*t)
        near = {}
        for ob in obs.objs:
            if np.any(ob['lo']-1.0 > np.array([M['x'][1], 9, 9])) or np.any(ob['hi']+1.0 < np.array([M['x'][0], -9, -9])):
                continue
            dd = min(ob['tree'].find_nearest(p_)[3] for p_ in pts[::2])
            if dd < 0.8:
                near[ob['name']] = round(dd, 3)
        row['vehicle_objects_within_0_8_m'] = dict(sorted(near.items(), key=lambda kv: kv[1])[:8])
        # containment envelope: the module box grown by t on every face (insulation + fire separation, thickness unspecified); the module moves out by t
        cont = {}
        for t_ in CONTAIN_T_M:
            g = sv.box(M['x'][0]-t_, M['x'][1]+t_, M['phi'], M['u'][0], M['u'][1]+2*t_, M['t'][1]+t_, c)      # inner face stays 0.15 m off the spine
            hits = sorted(obs.hits(g)); hull_ok = bool(sv.inside_hull(s, g)); left = gap-t_
            faces = {}; uc, xc = sum(M['u'])/2+t_, sum(M['x'])/2; rc = sd.ROBOT/2; ph = M['phi']
            pock = dict(outer=(xc-rc, xc+rc, M['u'][1]+2*t_, M['u'][1]+2*t_+sd.ROBOT, rc), forward=(M['x'][1]+t_, M['x'][1]+t_+sd.ROBOT, uc-rc, uc+rc, rc),
                        aft=(M['x'][0]-t_-sd.ROBOT, M['x'][0]-t_, uc-rc, uc+rc, rc), side_plus=(xc-rc, xc+rc, uc-rc, uc+rc, 1), side_minus=(xc-rc, xc+rc, uc-rc, uc+rc, -1))
            for fn, (xa, xb, ua, ub, ht) in pock.items():
                if fn.startswith('side'):
                    ta, tb = (M['t'][1]+t_, M['t'][1]+t_+sd.ROBOT) if ht > 0 else (M['t'][0]-t_-sd.ROBOT, M['t'][0]-t_)
                    corners = [Vector((xx, 0, 0))+uvec(ph)*uu+tvec(ph)*tt for xx in (xa-c, xb+c) for uu in (ua-c, ub+c) for tt in (ta-c, tb+c)]
                    bx = dict(corners=corners, x=(xa-c, xb+c), u=(ua-c, ub+c), t=(ta-c, tb+c), phi=ph)
                else:
                    bx = sv.box(xa, xb, ph, ua, ub, ht, c)
                el = ed.box_el('robot_pocket', bx); hh = sorted(obs.hits(bx)); ovl = [e['name'] for e in others if any(ed.inside(e, p_) for p_ in ed.samples(el)[::3])]
                faces[fn] = dict(free=bool(not hh and sv.inside_hull(s, bx) and not ovl), hits=hh, inside_hull=bool(sv.inside_hull(s, bx)), overlaps=ovl)
            cont[f'{t_:.2f}'] = dict(vehicle_hits=hits, inside_hull=hull_ok, air_gap_left_to_workshop_wall_m=round(left, 3), fits=bool(not hits and hull_ok and left >= MARGIN-1e-9),
                                     robot_pockets=faces, robot_faces_free=[k for k, v in faces.items() if v['free']])
        row['containment'] = cont; res['rows'][f'{so:.2f}'] = row
        print('WF_SP52', so, row['facing']['view_factor_warm_face_to_workshop_wall'], row['facing']['overlap_m2'], wres['hits'], wres['inside_hull'], {k: (v['fits'], v['robot_faces_free']) for k, v in cont.items()}, flush=True)
    res['open'] = dict(heat_transfer_w=None, wall_temperature_k=None, emissivity=None, insulation_conductivity=None, insulation_thickness_m=None, fire_barrier_rating=None,
                       allowable_wall_flux_w_m2=None, robot_service_access_route=None, owner_value_used=dict(warm_module_temperature_k=T_WARM_K, source='15!C123, G123 (~450 K)'),
                       emissive_power_unit_blackbody_w_m2_at_450k=round(SIGMA*T_WARM_K**4, 0),
                       emissive_power_note='sigma T^4 at the owner 450 K with emissivity 1: the ceiling of any surface flux, NOT an estimate; the real flux needs owner emissivities, wall temperature and insulation data (null)',
                       needed_from_owner=['surface emissivities of the module skin, the insulation and the workshop wall', 'insulation material, thickness, conductivity', 'allowed workshop wall temperature or flux',
                                          'fire-separation rating and the detection/suppression concept', 'whether robot-first servicing may use a face or needs a dedicated route', 'module heat dissipation (W) at 450 K'])
    return res


# ---------------------------------------------------------------------------------------------------------------------------------
# finalize: selection, extras, SVGs, JSON

def worst_cars(res):
    return min(r['least_m'] for r in res.values())


def render_exit(ctx, fixtures, e, res, name, out):
    data2 = copy.deepcopy(ctx.data); data2['sp13']['fixtures'] = fixtures
    obj, tree = ex.build_free(ctx.s, data2, [exit_solid(e)], [], ex.TRUNK_EXT_X, sp12=False, sp13=True, ref=False, fit=True)
    n = render_sp13(ctx, obj, fixtures, e, res, name, out); bpy.data.objects.remove(obj); return n


def fixture_table(ctx, fixtures, asb_ov, e):
    nz = fixture_list(fixtures); bx = boxes_of(nz); rows = {}
    for k, (f, b) in enumerate(zip(nz, bx)):
        dep, side = service_depth(b, [o for j, o in enumerate(bx) if j != k])
        rows[f['id']] = dict(job=f.get('job'), kind=f['kind'], x=f['x'], az_deg=f['az'], size_xyz_m=f['size'], quarter_turn=bool(f.get('rotated')),
                             mounted='outer wall' if 'rb' in f else ('floor' if f['kind'] in ('stand', 'rack', 'bench', 'locker') else 'wall 0.90 m above the floor'),
                             overflow_m=overflow_m(b), overflow_as_built_m=asb_ov[f['id']], service_depth_m=dep, service_side=side)
    lane = lane_pts(e); rows['_lane_clear_m'] = round(min(float(obb_dist(lane, b).min()) for b in bx), 3)
    return rows


def finalize_sp13(ctx, raw, out):
    evals = raw['evals']; cand = {k: worst_cars(v['res']) for k, v in evals.items() if k != 'CONTROL' and abs(v['exit']['D']-EXIT_D_M) < 1e-9}
    wide = {k: worst_cars(v['res']) for k, v in evals.items() if k != 'CONTROL' and abs(v['exit']['D']-EXIT_D_M) > 1e-9}
    best_k = max(cand, key=cand.get); sel = evals[best_k]; e, fx = sel['exit'], sel['fixtures']
    rad = [k for k in cand if evals[k]['exit']['beta'] == 0.0]; best_rad = max(rad, key=cand.get) if rad else None
    nz0 = fixture_list([dict(f) for f in ctx.data['sp13']['fixtures']]); asb = raw['asbuilt_overflow_m']
    SEEDS6 = tuple(SEEDS)+(59, 73, 97)
    recheck, _ = eval_exit(ctx, fx, e, 'SELECTED_6_SEEDS', seeds=SEEDS6); sel = dict(sel, res=recheck, res_3_seeds=sel['res'])
    bare, _ = eval_exit(ctx, [], e, 'BARE_SELECTED', seeds=SEEDS6)
    bare_rad, _ = eval_exit(ctx, [], evals['CONTROL']['exit'], 'BARE_CONTROL_EXIT')
    out_ = dict(sensitivity_wider_aperture={k: dict(exit=evals[k]['exit'], least_m=round(v, 3), by_carrier={c: r['least_m'] for c, r in evals[k]['res'].items()}) for k, v in wide.items()}, selected=best_k, selected_exit=e, selected_exit_info=exit_info(ctx, e), ranking={k: round(v, 3) for k, v in sorted(cand.items(), key=lambda kv: -kv[1])},
                carriers={k: dict(zip(('shape', 'size_or_length_radius'), (c['shape'], c.get('size') or [c.get('length'), c.get('radius')]))) for k, c in carriers(ctx).items()})
    out_['control'] = dict(exit=evals['CONTROL']['exit'], fit_out='as built (data/eva_suit.toml [sp13])', results=evals['CONTROL']['res'], fixtures=fixture_table(ctx, nz0, asb, evals['CONTROL']['exit']))
    out_['best_radial_rearranged'] = None if not best_rad else dict(label=best_rad, exit=evals[best_rad]['exit'], results=evals[best_rad]['res'], fixtures=fixture_table(ctx, evals[best_rad]['fixtures'], asb, evals[best_rad]['exit']))
    out_['selected_layout'] = dict(label=best_k, seeds=list(SEEDS6), results=sel['res'], results_first_3_seeds={c: r['least_m'] for c, r in sel['res_3_seeds'].items()}, fixtures=fixture_table(ctx, fx, asb, e), fixture_list=fx, merit=sel.get('metrics'))
    out_['bare_room_same_exit'] = bare; out_['bare_room_control_exit'] = bare_rad
    if wide:
        wk = max(wide, key=wide.get); we, wfx = evals[wk]['exit'], evals[wk]['fixtures']; wres, _ = eval_exit(ctx, wfx, we, 'WIDER_6_SEEDS', seeds=SEEDS6)
        wi = independence(ctx, we, wk)
        out_['wider_aperture_sensitivity_best'] = dict(label=wk, exit=we, exit_info=exit_info(ctx, we), seeds=list(SEEDS6), results=wres, results_first_3_seeds={c: r['least_m'] for c, r in evals[wk]['res'].items()},
                                                       fixtures=fixture_table(ctx, wfx, asb, we), vehicle_screen=exit_vehicle_screen(ctx, we), spine_core_cut_x_m=exit_spine_cut_x(ctx, we),
                                                       solid_separation_to_sp12_exit_solids_m=wi['solid_separation_to_sp12_exit_solids_m'], aperture_aft_edge_to_sp13_aft_wall_m=wi['aperture_aft_edge_to_sp13_aft_wall_m'],
                                                       note='SENSITIVITY ONLY: aperture 1.20 m instead of 1.10 m; a larger aperture is an owner decision (the SP-11 lead is 1.20 m), not applied here')
    out_['vehicle_screen'] = exit_vehicle_screen(ctx, e); out_['spine_core_cut_x_m'] = exit_spine_cut_x(ctx, e); out_['closure_pocket'] = closure_pocket(fx, e)
    out_['independence'] = independence(ctx, e, best_k)
    out_['renders'] = raw.get('renders', [])+[render_exit(ctx, fx, e, sel['res'], 'sp13_selected_rearranged_exit', out), render_exit(ctx, [], e, bare, 'sp13_selected_exit_bare_room', out)]
    out_['exit_scan_bare_room'] = raw.get('exit_scan'); out_['search'] = raw['search']; out_['all_evaluations'] = {k: dict(exit=v['exit'], least_by_carrier={c: r['least_m'] for c, r in v['res'].items()}) for k, v in evals.items()}
    return out_


def svg_ladder(res, path):
    """Unrolled trunk wall (X horizontal, angle vertical): the openings, the ladder lines and the bridged/unbridged gaps for the reference, option (a) at 315 deg and option (b) at port 210 deg."""
    s = res['_s']; panels = [('reference: ladder 285, port 240', 285.0, 240.0, res['reference']['case_ref']), ('(a) ladder moved to 315, port 240', 315.0, 240.0, res['option_a_ladder_relocated']['315']),
                             ('(b) ladder 285, port moved to 210', 285.0, 210.0, res['option_b_port_moved']['210'])]
    X0, X1 = 80.0, 106.0; sx, sy = 36.0, 1.0; W = int((X1-X0)*sx)+100; H = 3*(360*sy+60)+70; o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="monospace" font-size="11">', '<rect width="100%" height="100%" fill="#101418"/>']
    for pi, (title, th, al, case) in enumerate(panels):
        oy = 70+pi*(360*sy+60); o.append(f'<text x="50" y="{oy-14}" fill="#e8eaed" font-size="13">{title}   least gap {case["least_m_margin0"]:+.3f} m   dock window {case["dock_window_m"]["0.2"]:.3f} m (0.20 margin)</text>')
        o.append(f'<clipPath id="cp{pi}"><rect x="50" y="{oy}" width="{(X1-X0)*sx}" height="{360*sy}"/></clipPath><rect x="50" y="{oy}" width="{(X1-X0)*sx}" height="{360*sy}" fill="none" stroke="#5f6368"/><g clip-path="url(#cp{pi})">')
        ops = ops_for(s, al, res.get('sp13_exit_used'))
        for n, x, t_, r in ops:
            pts_r = []; pts_l = []
            for dd in np.linspace(-90, 90, 61):
                lat = 0.8*math.sin(math.radians(dd)); h_ = math.sqrt(max(r*r-lat*lat, 0.0)); a_ = (math.degrees(t_)+dd) % 360
                pts_r.append((x+h_, a_)); pts_l.append((x-h_, a_))
            ring = pts_r+pts_l[::-1]
            for wrap in (-360, 0, 360):
                poly = ' '.join(f'{50+(px-X0)*sx:.1f},{oy+(py+wrap)*sy:.1f}' for px, py in ring)
                o.append(f'<polygon points="{poly}" fill="#3b4a5a" fill-opacity="0.7" stroke="#8ab4f8" stroke-width="0.6"/>')
            o.append(f'<text x="{50+(x-X0)*sx:.0f}" y="{oy+((math.degrees(t_)%360))*sy:.0f}" fill="#bdc1c6" text-anchor="middle">{n.replace("Crew_Connector_","").replace("Crew_","")}</text>')
        G = ladder_geom(s, th)
        for ln, (rho, ang, rr) in G['lines'].items():
            a_ = math.degrees(ang) % 360; col = '#fdd663' if ln != 'rail' else '#f28b82'
            o.append(f'<line x1="{50+(G["floor"]-X0)*sx:.1f}" y1="{oy+a_*sy:.1f}" x2="{50+(LADDER_TOP_X-X0)*sx:.1f}" y2="{oy+a_*sy:.1f}" stroke="{col}" stroke-width="1.6"/>')
            gaps = merge_gaps(line_blocks(rho, ang, ops, 0.0), G['floor'], LADDER_TOP_X)
            for a, b, ns in gaps:
                dock = a <= 99.4 <= b
                o.append(f'<line x1="{50+(a-X0)*sx:.1f}" y1="{oy+a_*sy:.1f}" x2="{50+(b-X0)*sx:.1f}" y2="{oy+a_*sy:.1f}" stroke="{"#81c995" if dock else "#ff5252"}" stroke-width="4"/>')
        o.append('</g>')
        for xx in range(80, 107, 2):
            o.append(f'<text x="{50+(xx-X0)*sx:.0f}" y="{oy+360*sy+14}" fill="#9aa0a6" text-anchor="middle">{xx}</text>')
    o.append('<text x="50" y="18" fill="#e8eaed" font-size="13">SIM-027 trunk wall, unrolled: X (m) horizontal, angle 0-360 deg vertical. Yellow: stiles, red: arrest rail.</text><text x="50" y="34" fill="#e8eaed" font-size="12">Thick green: gap at the dock mouth (one rigid bridge). Thick red: unbridged gap (margin 0).</text></svg>')
    Path(path).write_text('\n'.join(o)+'\n')


def svg_sp52(sp52, path):
    """The two facing planes in the yz section at the 0.30 m standoff: warm module aft face, workshop forward face, their overlap."""
    row = sp52['rows']['0.30']; L = sp52['layout']; s_ = 80.0; ox, oy = 330, 300; o = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="560" font-family="monospace" font-size="12">', '<rect width="100%" height="100%" fill="#101418"/>']
    wd, md = math.radians(L['workshop_deg']), math.radians(L['warm_deg'])
    sd_ = sd; w = L['chamber_wall_m']; d = row['warm_u_m'][0]
    Wf = [(u*math.cos(wd)-t_*math.sin(wd), u*math.sin(wd)+t_*math.cos(wd)) for u, t_ in ((d, -2.05), (d+2.6, -2.05), (d+2.6, 2.05), (d, 2.05))]
    Mf = [(u*math.cos(md)-t_*math.sin(md), u*math.sin(md)+t_*math.cos(md)) for u, t_ in ((row['warm_u_m'][0], -row['warm_tangential_m']/2), (row['warm_u_m'][1], -row['warm_tangential_m']/2), (row['warm_u_m'][1], row['warm_tangential_m']/2), (row['warm_u_m'][0], row['warm_tangential_m']/2))]
    ov = clip(Mf, Wf); P_ = lambda pl: ' '.join(f'{ox+y*s_:.1f},{oy-z*s_:.1f}' for y, z in pl)
    o.append(f'<circle cx="{ox}" cy="{oy}" r="{0.95*s_:.1f}" fill="#2d3238" stroke="#9aa0a6"/><circle cx="{ox}" cy="{oy}" r="{0.8*s_:.1f}" fill="#101418" stroke="#9aa0a6"/>')
    o.append(f'<polygon points="{P_(Wf)}" fill="#34a853" fill-opacity="0.25" stroke="#81c995"/><polygon points="{P_(Mf)}" fill="#fa7b17" fill-opacity="0.35" stroke="#fdd663"/>')
    if len(ov) >= 3:
        o.append(f'<polygon points="{P_(ov)}" fill="#ea4335" fill-opacity="0.45" stroke="#f28b82"/>')
    f_ = row['facing']
    for i, tx in enumerate([f'SIM-027 SP-52 geometry only: view along X, standoff {row["standoff_m"]:.2f} m (workshop wall X {L["workshop_forward_outer_face_x"]:.2f} to module X {row["warm_x"][0]:.2f})',
                            f'warm aft face {f_["warm_aft_face_m2"]:.2f} m2, workshop forward face {f_["workshop_forward_face_m2"]:.2f} m2, overlap {f_["overlap_m2"]:.2f} m2 ({f_["overlap_fraction_of_warm_face"]*100:.0f}% of the module face)',
                            f'view factor warm face -> workshop wall {f_["view_factor_warm_face_to_workshop_wall"]:.3f} (geometry only; heat transfer OPEN)']):
        o.append(f'<text x="14" y="{22+i*16}" fill="#e8eaed">{tx}</text>')
    o.append('</svg>'); Path(path).write_text('\n'.join(o)+'\n')


# ---------------------------------------------------------------------------------------------------------------------------------
# segments (access matrix input) and main

ALL_STATES = ["0g", "spin", "stopped", "locked_1.5g"]
CAR_NAMES = {'A': 'carrier A', 'S': 'carrier S', 'K': 'carrier K', 'U': 'suited crew'}


def seg(id_, route, states, variant, case, least, worst, spread, nearest, note, status_=None):
    return dict(id=id_, route=route, states=states, variant=variant, case=case, least_m=None if least is None else round(float(least), 3),
                status=status_ or (status(least) if least is not None else 'OPEN'), worst_case_over=worst, seed_spread_m=spread, nearest=nearest, note=note)


def sp13_segments(S):
    out = []; ST = ["0g", "stopped", "locked_1.5g", "spin"]
    def pack(prefix, variant, res, note, seeds=None):
        seeds = list(seeds or SEEDS)
        allv = [r['least_m'] for r in res.values()]; k = min(res, key=lambda c: res[c]['least_m']); sp = [min(r['seed_spread_m'][0] for r in res.values()), max(r['seed_spread_m'][1] for r in res.values())]
        out.append(seg(f'{prefix}-ALL', 'SP-13', ST, variant, 'carriers A, S, K and suited crew with rescuers at both ends; minimum over all', min(allv), [CAR_NAMES[c] for c in res]+['rescuers (A, S, K)', f'seeds {seeds}'],
                       sp, res[k]['nearest'], note+f' Worst: {CAR_NAMES[k]}.'))
        for c, r in res.items():
            out.append(seg(f'{prefix}-{c}', 'SP-13', ST, variant, f'{CAR_NAMES[c]} through the exit{" with rescuers" if c != "U" else " (self-propelled, no rescuers)"}', r['least_m'],
                           [CAR_NAMES[c], 'body', 'rescuers' if c != 'U' else 'body only', f'seeds {seeds}'], r['seed_spread_m'], r['nearest'], f'body {r["body_least_m"]:+.3f} m, rescuers {r["rescuer_least_m"]}; sampled-pose sweep capped at 0.10 m.'))
    c = S['control']; pack('SP13-CTRL', f'control: as-built fit-out, radial exit D {c["exit"]["D"]:.2f} m at az {c["exit"]["az"]:.0f}, X {c["exit"]["xp"]:.3f}', c['results'], 'EVA-003 follow-up port re-run with this study seeds; the carrier turns 90 deg in the 1.6 m trunk extension.')
    if S.get('best_radial_rearranged'):
        b = S['best_radial_rearranged']; pack('SP13-RADREARR', f'rearranged fit-out, radial exit az {b["exit"]["az"]:.0f}, X {b["exit"]["xp"]:.2f}', b['results'], 'best radial arrangement found by the layout search.')
    e = S['selected_exit']; pack('SP13-SEL', f'rearranged fit-out ({S["selected"]}), exit D {e["D"]:.2f} m leaning {e["beta"]:.0f} deg aft of radial at az {e["az"]:.0f}, X {e["xp"]:.2f}', S['selected_layout']['results'],
                                 'selected arrangement of the layout search (highest minimum over carriers), re-run with six seeds.', S['selected_layout']['seeds'])
    if S.get('wider_aperture_sensitivity_best'):
        w = S['wider_aperture_sensitivity_best']; we = w['exit']
        pack('SP13-WIDE', f'SENSITIVITY aperture 1.20 m (not the 1.10 m comparator), exit leaning {we["beta"]:.0f} deg aft at az {we["az"]:.0f}, X {we["xp"]:.2f}', w['results'], 'sensitivity only; a wider aperture is an owner decision.', w['seeds'])
    pack('SP13-BARE', f'bare room (no fit-out), same exit as the selected one', S['bare_room_same_exit'], 'upper bound of the room geometry for this exit; fixtures removed.', S['selected_layout']['seeds'])
    ft = S['selected_layout']['fixtures']
    for fid in ('SP13_DRY_RACK', 'SP13_BENCH'):
        r = ft[fid]; ab = S['control']['fixtures'][fid]
        out.append(seg(f'SP13-SERVICE-{fid.split("_")[1]}', 'SP-13', ["0g", "stopped", "locked_1.5g", "spin"], f'rearranged ({S["selected"]})', f'service access: free depth in front of the {fid.split("_")[-1].lower()} on its best side minus the {SERVICE_REACH_M:.2f} m arm reach (free depth capped at 1.0 m)',
                       r['service_depth_m']-SERVICE_REACH_M, ['best of sides +x, -x, +tangential, -tangential, toward the axis'], None, f'{fid} on side {r["service_side"]}',
                       f'rearranged: depth {r["service_depth_m"]:.2f} m on {r["service_side"]}, mounted {r["mounted"]}, overflow past the room walls {r["overflow_m"]:.3f} m (as built {r["overflow_as_built_m"]:.3f} m; as built service depth {ab["service_depth_m"]:.2f} m on {ab["service_side"]}). Points checked at 5 positions along the side and three heights.'))
    cp = S['closure_pocket']
    out.append(seg('SP13-POCKET', 'SP-13', ["0g", "stopped", "locked_1.5g", "spin"], f'rearranged ({S["selected"]})', 'exit closure leaf parked beside the aperture vs the fit-out', cp['least_m'], ['four parking directions (best)'], None, cp['direction'], cp['note']))
    ind = S['independence']; sep = ind['solid_separation_to_sp12_exit_solids_m']; n1 = {k: v for k, v in sep.items() if 'N1' in k}; oth = {k: v for k, v in sep.items() if 'N1' not in k}
    for tag, grp, what in (('N0N2N3', oth, 'N0 branch, N2/N3 oblique duct'), ('N1', n1, 'N1 axial slot')):
        k = min(grp, key=grp.get)
        out.append(seg(f'SP13-INDEP-{tag}', 'SP-13', ["0g", "stopped", "locked_1.5g", "spin"], f'exit solid vs SP-12 {what} ({S["selected"]})', f'solid separation between the SP-13 exit solid and the SP-12 {what} solid(s)', grp[k], list(grp), None, k,
                       'no shared closure, no SP-12 room volume on the SP-13 route; the trunk extension is the shared destination volume. Separation of solids only; the wall thickness between them is OPEN.'))
    out.append(seg('SP13-INDEP-PARTITION', 'SP-13', ["0g", "stopped", "locked_1.5g", "spin"], f'aperture vs the SP-12/SP-13 partition ({S["selected"]})', 'aft edge of the aperture ellipse in the SP-13 floor plane vs SP-13 aft wall X 104.95', ind['aperture_aft_edge_to_sp13_aft_wall_m'], ['aperture ellipse, floor plane'], None, 'SP-13 aft wall',
                   'the aperture must not open into SP-12; the study constraint is 0.05 m. The SP-12/SP-13 partition itself (X 104.85-104.95) is unchanged.'))
    vs = S['vehicle_screen']
    out.append(seg('SP13-VEHICLE', 'SP-13', ["0g", "stopped", "locked_1.5g", "spin"], f'exit solid vs the saved vehicle ({S["selected"]})', 'exit solid boxes at the 0.15 m mechanical clearance against every stationary mesh and inside the hull',
                   None, ['stationary meshes', 'hull inner radius'], None, ', '.join(vs['hits']) or None, f'{vs["status"]}; refuge objects hit: {vs["refuge_objects_hit"] or "none"}; spine-core cut {S["spine_core_cut_x_m"]} m of X (structural, OPEN).', 'PASS' if vs['status'] == 'CLEAR' else 'FAIL'))
    return out


def ladder_segments(L):
    out = []; ST = ["locked_1.5g"]
    def one(id_, route, variant, case, c, extra='', status_=None):
        nb = c['unbridged_extra_gaps']['margin_0.00']
        out.append(seg(id_, route, ST, variant, case, c['least_m_margin0'], ['stile_a', 'stile_b', 'arrest rail', 'every opening 81.6-104.9 m', 'dock window excluded (bridged)'], None,
                       f'{c["least_at"]["line"]} / {c["least_at"]["opening"]} at X {c["least_at"]["x"]}',
                       f'dock bridge span {c["dock_window_m"]["0.0"]:.2f} m (margin 0) / {c["dock_window_m"]["0.2"]:.3f} m (0.20 margin; accepted prototype 1.764); unbridged extra gaps at margin 0: {[(g["line"], g["a"], g["b"], g["by"]) for g in nb] or "none"}. {extra}', status_))
    r = L['reference']; one('LAD-REF', 'dock_bridge', 'built ladder 285 deg, district port 240 deg (L1-A as scanned)', 'ladder lines vs openings to X 104.9, margin 0 (the built ladder rule)', r['case_ref'], 'the 240 deg port crosses the stile-a line at X 103.76-104.45.')
    for th in ('305', '310', '315', '320', '325', '330'):
        c = L['option_a_ladder_relocated'][th]
        one(f'LAD-A-{th}', 'dock_bridge', f'(a) trunk ladder relocated to {th} deg, port stays 240 deg', 'ladder lines vs openings to X 104.9, margin 0', c,
            f'Dock_Service mouth {c["dock_service_mouth_covered_by_ladder_strip"]*100:.0f}% covered by the ladder strip (built 285: {r["case_ref"]["dock_service_mouth_covered_by_ladder_strip"]*100:.0f}%); nearest trunk fixture {c["fixture_clearance_m"]["least_m"]:.3f} m ({c["fixture_clearance_m"]["nearest"]}).')
    for al in ('200', '205', '210', '215', '220', '225'):
        c = L['option_b_port_moved'][al]; ps = c['port_screen']
        one(f'LAD-B-{al}', 'dock_bridge', f'(b) ladder stays 285 deg, workshop port moved to {al} deg on the workshop face', 'ladder lines vs openings to X 104.9, margin 0', c,
            f'port screen: {ps["status"]} (tangential offset on the workshop face {ps["tangential_offset_on_face_m"]:+.2f} m; vehicle hits {ps["vehicle_hits"] or "none"}). The least value is the BUILT ladder passing Crew_Port_2_2 (existing 0.018 m) while the port edge itself is clear by {c["port_edge_gap_m"]:+.3f} m.', 'FAIL' if ps['status'] == 'BLOCKED' else None)
    out.append(seg('DOCK-BRIDGE', 'dock_bridge', ST, 'accepted rigid ladder bridge over the Dock_Primary mouth, 285 deg (imported)', 'climber figure vs the connector rim and dock passage envelope', 0.106,
                   ['climber body rods', 'connector rim curve'], None, 'Human_Trunk_Climber_Arm_1', 'imported from references/p1_eva_exits.json bypass.climber_vs_connector_rim (not re-run); dock passage envelope 0.35 m vs stiles 0.273 m. Structure, arrester lock and swing OPEN.'))
    return out


def sp52_segments(C):
    out = []; ST = ["0g", "spin", "stopped", "locked_1.5g"]; r = C['rows']['0.30']
    near = r['vehicle_objects_within_0_8_m']; k = min(near, key=near.get)
    out.append(seg('SP52-STANDOFF-0.30', 'L1-A', ST, 'warm module 0.30 m from the workshop wall, scan angles (workshop 240, module 210)', 'geometric clearances of the module envelope: workshop wall, spine, struts, shield column',
                   min(r['standoff_m'], near[k], r['shield_column_gap_m']), ['workshop wall', 'vehicle meshes within 0.8 m', 'shield column'], None, k,
                   'GEOMETRY ONLY. Heat transfer, wall temperature, insulation and fire-barrier performance are OPEN (null): no owner emissivity, conductivity, rating or dissipation exists.', 'OPEN'))
    for t_ in ('0.10', '0.20'):
        c = r['containment'][t_]
        out.append(seg(f'SP52-CONT-{t_}', 'L1-A', ST, f'containment envelope {t_} m thick on every face, module moved out by {t_} m', 'envelope against the vehicle (0.15 m clearance), the hull, and the air gap left to the workshop wall',
                       c['air_gap_left_to_workshop_wall_m'], ['vehicle meshes', 'hull', 'workshop wall'], None, ', '.join(c['vehicle_hits']) or None,
                       f'fits geometrically: {c["fits"]}; robot 0.60 m cube pockets free on faces {c["robot_faces_free"]} (aft face toward the workshop never). Thickness is a geometry parameter, not a design.', 'OPEN'))
    return out


def scan_exits(ctx, out, shard, n):
    """Bare-room scan of every valid exit (D 1.10 / 1.20 m, 0-45 deg aft, X in 0.1 m steps, az 30-60), carriers S and A, three seeds; shard i of n writes scan_i.jsonl."""
    grid = []
    for D in (EXIT_D_M, 1.20):
        for beta in (0.0, 15.0, 25.0, 35.0, 45.0):
            half = D/2/math.cos(math.radians(beta)); lo = ROOM13['x'][0]+0.05+half; hi = ROOM13['x'][1]-0.05-half
            for xp in np.arange(math.ceil(lo*10)/10, hi+1e-9, 0.1):
                for az in (30.0, 40.0, 50.0, 60.0):
                    grid.append(dict(D=D, xp=round(float(xp), 2), az=az, beta=beta))
    with open(out/f'scan_{shard}.jsonl', 'w') as f:
        for e in grid[shard::n]:
            r, _ = eval_exit(ctx, [], e, 'SCAN', seeds=SEEDS, which=('S', 'A'))
            f.write(json.dumps(dict(exit=e, S=r['S']['least_m'], A=r['A']['least_m'], S_body=r['S']['body_least_m'], S_spread=r['S']['seed_spread_m']))+'\n'); f.flush()


def pick_exits(scan_glob):
    import glob
    rows = [json.loads(l) for f in sorted(glob.glob(scan_glob)) for l in open(f) if l.strip()]
    for r in rows:
        r['worst'] = min(r['S'], r['A'])
    out = []
    for D in (EXIT_D_M, 1.20):
        for grp in ('radial', 'oblique'):
            rr = sorted([r for r in rows if abs(r['exit']['D']-D) < 1e-9 and ((r['exit']['beta'] == 0.0) == (grp == 'radial'))], key=lambda r: -r['worst'])
            out += [r['exit'] for r in rr[:(2 if grp == 'radial' else 4)] if D == EXIT_D_M] + [r['exit'] for r in rr[:2] if D != EXIT_D_M]
    return out, rows


def main(out, parts, sp13_raw, scan_glob=None, shard=None):
    ctx = load_ctx(); out.mkdir(parents=True, exist_ok=True)
    if 'scan' in parts:
        scan_exits(ctx, out, *shard); return
    S = L = C = None; rdir = ROOT/'renders/p1/eva/district'; rdir.mkdir(parents=True, exist_ok=True)
    if 'sp13' in parts:
        if sp13_raw:
            raw = json.loads(Path(sp13_raw).read_text())
        else:
            exits, rows = pick_exits(scan_glob); (out/'exit_scan.json').write_text(json.dumps(rows, indent=1)+'\n'); raw = run_sp13(ctx, out, exits); raw['exit_scan'] = rows; (out/'sp13_raw.json').write_text(json.dumps(raw, indent=1, default=str)+'\n')
        S = finalize_sp13(ctx, raw, out); (out/'sp13.json').write_text(json.dumps(S, indent=1, default=str)+'\n')
        for nm in S['renders']:
            if (out/nm).exists():
                (rdir/f'sim027_{nm}').write_bytes((out/nm).read_bytes())
    else:
        S = json.loads((out/'sp13.json').read_text())
    e = S['selected_exit']
    if 'ladder' in parts:
        L = run_ladder(ctx, out, e); L['_s'] = ctx.s
        for a_ in L['option_b_port_moved']:
            c = L['option_b_port_moved'][a_]; ops = ops_for(ctx.s, float(a_), e); xs = np.arange(81.6, 104.9, 0.01); ang = ladder_geom(ctx.s, 285.0)['lines']['stile_a']
            c['port_edge_gap_m'] = round(signed_gap(ang[0], ang[1], ang[2], [o for o in ops if o[0] == 'District_Port'], xs, [])[0], 3)
        svg_ladder(L, rdir/'sim027_ladder_dock_options.svg'); L.pop('_s'); (out/'ladder.json').write_text(json.dumps(L, indent=1, default=str)+'\n')
    elif (out/'ladder.json').exists():
        L = json.loads((out/'ladder.json').read_text())
    if 'sp52' in parts:
        C = run_sp52(ctx, out); svg_sp52(C, rdir/'sim027_sp52_facing_faces.svg'); (out/'sp52.json').write_text(json.dumps(C, indent=1, default=str)+'\n')
    elif (out/'sp52.json').exists():
        C = json.loads((out/'sp52.json').read_text())
    segs = (sp13_segments(S) if S else [])+(ladder_segments(L) if L else [])+(sp52_segments(C) if C else [])
    src = ['src/wayfarer/studies/eva3_sp13_l1a.py', 'references/p1_eva_sp13_l1a.json', 'references/p1_hum003.json', 'references/p1_eva_exits.json', 'references/p1_eva_district.json', 'references/p1_eva_access.json', 'data/eva_suit.toml']
    (ROOT/'references/p1_access_seg_sp13_l1a.json').write_text(json.dumps(dict(study='SIM-027 / DIST-006: SP-13 independent second exit, L1-A trunk ladder vs district port at Dock_Primary, SP-52 containment geometry (owner 2026-10-11 16:45)',
                                                                         source=src, segments=segs), indent=1)+'\n')
    (ROOT/'references/p1_eva_sp13_l1a.json').write_text(json.dumps(dict(study='SIM-027 / DIST-006 redline study (NONCANON PROTOTYPE, disposable geometry)', band=BAND, seeds=list(SEEDS), owner_refs=['15!A157 DIST-005', '15!A158 DIST-006', 'references/EVA3_REPORT.md 12.6'],
                                                                     constants=dict(service_reach_m=SERVICE_REACH_M, lane_r_m=LANE_R_M, exit_d_m=EXIT_D_M, bridge_accepted_m=BRIDGE_ACCEPTED_M, standoffs_m=list(STANDOFFS_M), containment_t_m=list(CONTAIN_T_M)),
                                                                     sp13=S, ladder=L, sp52=C), indent=1, default=str)+'\n')
    print('WF_SIM027 done', len(segs), 'segments', flush=True)


# =================================================================================================================================
# Owner 2026-10-13 (S&E 15!A170 RESCUE-PORTS, 15!A171 DIST-L1-STEP, L1-A part): disposable study extensions, zero canonical geometry change.
#   A170: N1 rejected as the SP-12 emergency slot (it takes SP-13's only route). SP-12: N2 first, then N0 / N3, each against the independent SP-13
#         exit. SP-13 closure: (a) an outward-offset hinged, positively dogged leaf; (b) a dual-isolation fallback (two closures in series). The
#         80 kPa nominal differential both ways is an OPEN load case (only the ideal dp x area DIAGNOSTIC of CALC-R01 is printed; no rating, no
#         capacity, no hinge assumed to resist reversed pressure).
#   A171: L1-A district port moved to 205-215 deg as a reversible WHITEBOX: whole-route clearance (>= 0.05 m total, the local +0.018 m is not a
#         route PASS), suited litter / carriers with rescuers past the extended ladder, one-handed traverse geometry, no new ladder break,
#         pressure-boundary interference. Tether fall load OPEN.

O13_TAG = 'owner_2026_10_13'
LEAF_SEAT_M = 0.05              # leaf overlap beyond the clear aperture on every side (the SP-11 1.20 m bore / 1.30 m leaf ratio), PROTOTYPE
LEAF_T_M = 0.08                 # leaf proxy thickness (= the SP-11 plug leaf proxy of eva3_exits.build_free), PROTOTYPE, not a structural size
HINGE_OFFSETS_M = (0.10, 0.02)  # outward hinge offset beyond the leaf edge (the hinge line lies outside the seat), PROTOTYPE
HINGE_EDGES = ('aft', 'fwd', 'plus_t', 'minus_t')
PARK_DEG = 90.0                 # parked open angle (standing against the wall the hinge edge faces)
WHEEL_R_M, WHEEL_PROUD_M = 0.15, 0.08   # dog-operating handwheel on both faces at the leaf centre (through spindle), PROTOTYPE
DOGS_N = 12                     # positive dogs on the leaf rim (the SP-11 plug PROTOTYPE count); geometry only, no capacity
DUAL_GAP_M = 0.02               # gap between the two stacked leaves of the dual-isolation variant, PROTOTYPE
OP_REACH_M = h3.STAFF_REACH_M   # 0.70 m arm reach of an operator (shoulder to the handwheel)
OP_R_M = h3.STAFF_R_M           # operator torso capsule radius 0.25 m
SP12_O13 = (('N2_oblique30_1.10', 'oblique', 1.10, 30.0), ('N2_oblique35_1.10', 'oblique', 1.10, 35.0), ('N0_branch_0.90', 'control', 0.90, 90.0),
            ('N0_branch_1.10', 'control', 1.10, 90.0), ('N3_oblique30_1.20', 'oblique', 1.20, 30.0), ('N2_fwd45_1.10', 'fwd', 1.10, 45.0))
FWD_RH = 1.45                   # N2 forward-leaning variant: the duct axis passes under the chamber axis at this radius (as the N2 30 deg 'H' point), PROTOTYPE
PORT_ALPHAS = (205.0, 210.0, 215.0)
STATES_NOTE = ('the trunk, the district and SP-12/13 are on the non-rotating spine, so a clearance of fixed geometry is the same number in 0 g, spin, stopped '
               'and locked 1.5 g; the sampled-pose carriers are free poses (any state); the climber figure is the 1.5 g aft-down pose only; a 0 g free-float '
               'traverse pose, Coriolis and the loads of each state are not represented')


def frame13(e):
    """Local frame at the SP-13 aperture centre on the floor (r 1.25): origin, X, tangential, radial."""
    a = math.radians(e['az']); X, T, R = (np.array(v, float) for v in axes_at(a))
    return np.array(P(e['xp'], 1.25, az=a), float), X, T, R


def leaf_dims(e):
    return e['D']/2/math.cos(math.radians(e['beta']))+LEAF_SEAT_M, e['D']/2+LEAF_SEAT_M      # semi-axes along X and tangential (floor-plane ellipse)


EDGE_DIR = dict(aft=(-1, 0), fwd=(1, 0), plus_t=(0, 1), minus_t=(0, -1))


def leaf_transform(e, edge, o_h, theta_deg, layer=0):
    """Rigid motion of a leaf hinged on `edge`: the hinge line runs along the edge, o_h outside the leaf rim, in the leaf's top-face plane.
    layer 0 = the leaf on the seat (r_local 0..T), layer 1 = a second leaf stacked above it (dual isolation). Returns f(points local (x, t, r)) -> global."""
    O, X, T, R = frame13(e); A, B = leaf_dims(e); sx, st = EDGE_DIR[edge]; out = X*sx+T*st; ext = A if sx else B
    base = layer*(LEAF_T_M+DUAL_GAP_M); off = o_h+layer*(LEAF_T_M+DUAL_GAP_M)
    H = O+out*(ext+off)+R*(base+LEAF_T_M); th = math.radians(theta_deg); c, s_ = math.cos(th), math.sin(th)
    def f(loc):
        loc = np.atleast_2d(np.asarray(loc, float)); g = O+np.outer(loc[:, 0], X)+np.outer(loc[:, 1], T)+np.outer(loc[:, 2]+base, R)
        rel = g-H; a_ = rel@(-out); r_ = rel@R; along = rel-np.outer(a_, -out)-np.outer(r_, R)
        a2 = a_*c-r_*s_; r2 = a_*s_+r_*c
        return H+np.outer(a2, -out)+np.outer(r2, R)+along
    return f


def leaf_local_points(e, n_ring=24, n_rad=4, wheels=True):
    A, B = leaf_dims(e); pts = []
    for k in range(n_rad+1):
        q = k/n_rad
        for i in range(n_ring if k else 1):
            ph = 2*math.pi*i/n_ring
            for z in (0.0, LEAF_T_M):
                pts.append((A*q*math.cos(ph), B*q*math.sin(ph), z))
    if wheels:
        for i in range(12):
            ph = 2*math.pi*i/12
            for z in (LEAF_T_M+WHEEL_PROUD_M, -WHEEL_PROUD_M):
                pts.append((WHEEL_R_M*math.cos(ph), WHEEL_R_M*math.sin(ph), z))
    return np.array(pts)


def prism_obj(bottom, top, name):
    """Closed prism mesh from two matching rings of global points (a leaf or a handwheel), for the booleans and the renders."""
    n = len(bottom); vs = [tuple(p) for p in bottom]+[tuple(p) for p in top]
    fs = [(i, (i+1) % n, n+(i+1) % n, n+i) for i in range(n)]+[tuple(range(n-1, -1, -1)), tuple(range(n, 2*n))]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    import bmesh
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    return ex.link(me, name)


def leaf_solids(e, edge, o_h, theta_deg, layers=(0,), name='LEAF'):
    """Callables making the leaf (an elliptic plate) and its two handwheels at an angle: obstacles for the free space / render objects."""
    A, B = leaf_dims(e); n = 40; out = []
    for layer in layers:
        f = leaf_transform(e, edge, o_h, theta_deg, layer)
        ring = lambda z, a_=A, b_=B: [(a_*math.cos(2*math.pi*i/n), b_*math.sin(2*math.pi*i/n), z) for i in range(n)]
        out.append(lambda f=f, ring=ring, layer=layer: prism_obj(f(ring(0.0)), f(ring(LEAF_T_M)), f'{name}_{layer}'))
        wr = lambda z: [(WHEEL_R_M*math.cos(2*math.pi*i/16), WHEEL_R_M*math.sin(2*math.pi*i/16), z) for i in range(16)]
        out.append(lambda f=f, wr=wr, layer=layer: prism_obj(f(wr(LEAF_T_M)), f(wr(LEAF_T_M+WHEEL_PROUD_M)), f'{name}_{layer}_wheel_top'))
        out.append(lambda f=f, wr=wr, layer=layer: prism_obj(f(wr(-WHEEL_PROUD_M)), f(wr(0.0)), f'{name}_{layer}_wheel_bottom'))
    return out


def room_clear(pts):
    """Margin of points to the SP-13 room: x walls, azimuth walls, the ceiling (r 4.60) and the floor (r 1.25 less the aperture: points over the
    aperture may go below the floor only inside the duct, which is not checked here). Negative = outside."""
    p = np.asarray(pts, float); r = np.hypot(p[:, 1], p[:, 2])
    return min(room_margin(p), float(np.min(ROOM13['r'][1]-r)))


def leaf_geometry(ctx, fixtures, e, edge, o_h, layers=(0,)):
    """Pure geometry of one hinged closure variant: parked envelope and swing envelope against the room walls and the fit-out boxes."""
    bx = boxes_of(fixture_list(fixtures)); ids = [f['id'] for f in fixture_list(fixtures)]; loc = leaf_local_points(e)
    def clear(pts):
        d_fx = [(float(obb_dist(pts, b).min()), i) for b, i in zip(bx, ids)]; k = min(d_fx) if d_fx else (9.0, None)
        return dict(to_room_m=round(room_clear(pts), 3), to_fitout_m=round(k[0], 3), nearest_fixture=k[1])
    park = np.vstack([leaf_transform(e, edge, o_h, PARK_DEG, l)(loc) for l in layers])
    swing = np.vstack([leaf_transform(e, edge, o_h, th, l)(loc) for l in layers for th in np.arange(5.0, PARK_DEG+1e-9, 5.0)])
    pk, sw = clear(park), clear(swing)
    r = np.hypot(park[:, 1], park[:, 2])
    return dict(park=pk, swing=sw, park_least_m=round(min(pk['to_room_m'], pk['to_fitout_m']), 3), swing_least_m=round(min(sw['to_room_m'], sw['to_fitout_m']), 3),
                park_extent=dict(x=[round(float(park[:, 0].min()), 3), round(float(park[:, 0].max()), 3)], r=[round(float(r.min()), 3), round(float(r.max()), 3)]),
                status=status(min(pk['to_room_m'], pk['to_fitout_m'], sw['to_room_m'], sw['to_fitout_m'])))


def operator_fit(walls, release, side, rng, n=800):
    """Opposite-side operation: an operator torso (capsule r 0.25 m, 0.5-0.95 m) whose shoulder end lies within the 0.70 m arm reach of the release
    point (the handwheel), wholly on one side of the closure plane (`side` = predicate on capsule axis end points). Best of n samples: (clearance
    capped 0.10, nearest, reach used)."""
    best = (-9.0, None, None); release = np.asarray(release, float)
    for _ in range(n):
        u = rng.normal(size=3); u /= np.linalg.norm(u); a = release+u*rng.uniform(OP_R_M, OP_REACH_M)
        v = rng.normal(size=3); v /= np.linalg.norm(v); b = a+v*rng.uniform(0.5, 0.95)
        if not side(a, b):
            continue
        m = walls.capsule(tuple(a), tuple(b), OP_R_M)
        if m[0] > best[0]:
            best = (min(m[0], h3.CAP_M), m[1], round(float(np.linalg.norm(a-release)), 3))
            if best[0] >= h3.CAP_M:
                break
    if best[2] is None:
        return dict(least_m=None, status='FAIL', nearest=None, reach_used_m=None, reach_margin_m=None, note='no operator placement found on that side')
    return dict(least_m=round(best[0], 3), status=status(best[0]), nearest=best[1], reach_used_m=best[2], reach_margin_m=round(OP_REACH_M-best[2], 3))


def plane_side(O, R, lo=None, hi=None, pad=OP_R_M):
    """Capsule wholly above (lo) or below (hi) a plane through O normal R, counting its radius."""
    def f(a, b):
        da, db = float(np.dot(a-O, R)), float(np.dot(b-O, R))
        return (lo is None or min(da, db)-pad >= lo) and (hi is None or max(da, db)+pad <= hi)
    return f


def dp_cases(name, clear_area_m2, leaf_area_m2, seated_by, reverse_on):
    """The 80 kPa nominal both ways: OPEN load case. Only the ideal dp x area DIAGNOSTIC (CALC-R01 method: clear area, and the leaf outer area as
    the bounding value) is printed; no seat load, rating, dog capacity, hinge capacity or factor is assumed."""
    return dict(closure=name, dp_nominal_kpa=CABIN_KPA_O13, directions={
        seated_by: dict(held_by='the seat (pressure pushes the leaf onto it)', status='OPEN'),
        reverse_on: dict(held_by='the positive dogs only (the hinge is NOT assumed to resist reversed pressure)', status='OPEN')},
        ideal_dp_x_clear_area_kn=round(CABIN_KPA_O13*clear_area_m2, 1), ideal_dp_x_leaf_outer_area_kn=round(CABIN_KPA_O13*leaf_area_m2, 1),
        basis='DIAGNOSTIC: 80 kPa x area; not a seat load, not a rating, no structural release', status='OPEN')


CABIN_KPA_O13 = 80.0     # owner 15!A170: "dual dp 80 kPa nominal loads" (= eva3_exits.CABIN_KPA BASELINE cabin pressure)


# ---------------------------------------------------------------------------------------------------------------------------------
# A170 SP-12: N2 first, then N0 / N3, against the independent SP-13 exit

def sp12_variant(name, kind, D, psi_deg):
    xb = 101.8494; XC = ex.XC; RA = ex.RA; P_ = P
    if kind == 'control':
        return dict(kind='control', D=D, unions=[lambda D=D: h3.prim_cyl(P_(xb, 0.40), P_(xb, 1.45), D/2)],
                    path=[('C', P_(xb, 5.8)), ('B', P_(xb, 1.2)), ('B', P_(xb, 0.0)), ('T', (xb-1.0, 0.0, 0.0)), ('T', (97.0, 0.0, 0.0))], area=math.pi*(D/2)**2,
                    solid=dict(a=P_(xb, 0.40), b=P_(xb, 1.45), r=D/2), floor_x=xb, below_pt=P_(xb, 1.05), desc=f'radial branch {D:.2f} m on the airlock axis (control; turn in the trunk)')
    if kind == 'fwd':
        # N2 family, leaning FORWARD: from under the SP-11 chamber down-forward into the L1-A trunk extension; the carrier enters head first,
        # aligns with the trunk axis in the extension and is then moved aft feet first (a shunt, no reversal turn)
        psi = math.radians(psi_deg); t = math.tan(psi); xa, ra = XC, FWD_RH; xe, re = XC+(FWD_RH-0.37)/t, 0.37; L = math.hypot(xe-xa, ra-re)
        p0, p1 = P_(xa-0.35, ra+0.35*t), P_(xe+0.4, re-0.4*t); xf = xa+(ra-1.25)/t
        return dict(kind='fwd', D=D, psi_deg=psi_deg, unions=[lambda D=D, p0=p0, p1=p1: h3.prim_cyl(p0, p1, D/2)],
                    path=[('C', P_(XC, 5.8)), ('H', P_(xa, ra)), ('D', P_(xe, re)), ('E', (xe+2.6, 0.0, 0.0))], area=math.pi*(D/2)**2,
                    duct=dict(xa=xa, ra=ra, xe=xe, re=re, length_m=round(L, 3)), solid=dict(a=p0, b=p1, r=D/2), floor_x=xf,
                    below_pt=P_(xa+(ra-1.05)/t, 1.05), shunt_from_x=xe+2.6,
                    desc=f'{D:.2f} m round duct leaning {psi_deg:.0f} deg FORWARD from under the chamber (X {xa:.2f}, r {ra:.2f}) to the L1-A extension at X {xe:.2f}; the carrier enters head first, aligns in the extension and is moved aft feet first')
    psi = math.radians(psi_deg); (xa, ra), (xe, re), t = ex.duct_axis(psi); L = math.hypot(xa-xe, ra-re)
    p0, p1 = P_(xa+0.35, ra+0.35*t), P_(xe-0.4, re-0.4*t); xf = xa-(ra-1.25)/t
    return dict(kind='oblique', D=D, psi_deg=psi_deg, unions=[lambda D=D, p0=p0, p1=p1: h3.prim_cyl(p0, p1, D/2)],
                path=[('C', P_(XC, 5.8)), ('H', P_(XC, ra-(xa-XC)*t)), ('D', P_(xe, re)), ('T', (xe-1.4, 0.0, 0.0)), ('T', (xe-2.9, 0.0, 0.0))],
                area=math.pi*(D/2)**2, duct=dict(xa=xa, ra=ra, xe=xe, re=re, length_m=round(L, 3)), solid=dict(a=p0, b=p1, r=D/2), floor_x=xf,
                below_pt=P_(xa-(ra-1.05)/t, 1.05), desc=f'{D:.2f} m round duct at {psi_deg:.0f} deg to the trunk axis from (X {xa:.2f}, r {ra:.2f}) to the trunk at X {xe:.2f}')


def duct_spine_cut(s, v):
    """X length over which a duct (axis segment, diameter D) passes through the spine-core annulus (trunk wall to the core radius): structural cut, OPEN."""
    core = s['prototype']['spine_core_radius_m']; w = s['crew_transfer']['passage_wall_m']; tr = s['crew_transfer']['trunk_clear_radius_m']; d = v['duct']
    a = np.array((d['xa'], d['ra'])); b = np.array((d['xe'], d['re'])); u = (b-a)/np.linalg.norm(b-a); n = 0
    for x in np.arange(95.0, 108.0, 0.02):
        for r in np.arange(tr+w, core+1e-9, 0.02):
            q = np.array((x, r))-a; along = float(np.dot(q, u))
            if 0 <= along <= np.linalg.norm(b-a) and abs(q[0]*u[1]-q[1]*u[0]) <= v['D']/2:
                n += 1; break
    return round(n*0.02, 2)


def route_envelope_gap(route_a, route_b, ra_, rb_, r_min=0.85):
    """Least gap between two carriers' route envelopes outside the shared trunk (route points with r >= r_min), as capsules along the polylines."""
    A = np.array([p for _, p in route_a if math.hypot(p[1], p[2]) >= r_min]); B = np.array([p for _, p in route_b if math.hypot(p[1], p[2]) >= r_min])
    if not len(A) or not len(B):
        return None
    def dense(Q):
        out = [Q[0]]
        for a, b in zip(Q, Q[1:]):
            n = max(1, int(np.linalg.norm(b-a)/0.05)); out += [a+(b-a)*k/n for k in range(1, n+1)]
        return np.array(out)
    A, B = dense(A), dense(B); d = np.min(np.linalg.norm(A[:, None, :]-B[None, :, :], axis=2))
    return round(float(d)-ra_-rb_, 3)


def sweep_sp12_carriers(walls, v, kind, route, cars, seeds, name):
    out = {}
    for cid, car in cars.items():
        per = []
        for sdv in seeds:
            rng = np.random.default_rng(sdv); per.append(h3.sweep_route(walls, car, route, rng, staff=True))
        if kind == 'fwd':           # the shunt: carrier on the axis, head forward, moved aft feet first from the extension to X 97 (explicit poses, two rescuers)
            Lc = h3.length(car); poses = [((xx, 0.0, 0.0), (-1.0, 0.0, 0.0), 0.0, f'shunt aft x {xx:.2f}') for xx in np.arange(v['shunt_from_x'], 97.0+Lc, -0.25)]
            for j, sdv in enumerate(seeds):
                rng = np.random.default_rng(sdv+1000); q = h3.sweep_poses(walls, car, poses, rng); st = ex.staff_at(walls, rng, poses, car)
                per[j] = dict(per[j]); per[j]['by_zone'] = dict(per[j]['by_zone'], S_shunt=dict(least_m=q['least_m'], status=q['status'], nearest=q['nearest'], at_m=q['at']))
                if q['least_m'] < per[j]['least_m']:
                    per[j].update(least_m=q['least_m'], nearest=q['nearest'], zone='S_shunt', head=q['head'], axis=q['axis'], roll=q['roll'])
                if st[0] < (per[j]['staff_least_m'] if per[j]['staff_least_m'] is not None else 9):
                    per[j].update(staff_least_m=st[0], staff_nearest=st[1])
        body = [r['least_m'] for r in per]; stf = [r['staff_least_m'] for r in per if r['staff_least_m'] is not None]; k = int(np.argmin(body))
        zones = {}
        for r in per:
            for z, q in r['by_zone'].items():
                if z not in zones or q['least_m'] < zones[z]['least_m']:
                    zones[z] = q
        least = min(body+stf)
        out[cid] = dict(least_m=round(least, 3), body_least_m=min(body), rescuers_least_m=min(stf) if stf else None, status=status(least),
                                    seed_spread_m=[round(min(body+stf), 3), round(max(body+stf), 3)], body_by_seed=body, rescuers_by_seed=[r['staff_least_m'] for r in per],
                                    nearest=per[k]['nearest'], zone=per[k]['zone'], by_zone=zones, rescuer_nearest=min(per, key=lambda r: r['staff_least_m'] if r['staff_least_m'] is not None else 9)['staff_nearest'],
                                    head=per[k]['head'], axis=per[k]['axis'], roll=per[k]['roll'])
        print('WF_O13_SP12', name, cid, out[cid]['least_m'], body, stf, per[k]['zone'], flush=True)
    return out


def run_o13_sp12(ctx, out, sp13, seeds=SEEDS):
    s = ctx.s; ex.load_room(s); res = {}; rdir = ROOT/'renders/p1/eva/district'
    e13 = sp13['selected_exit']; route13, xe13 = route_for(e13); t13 = math.tan(math.radians(e13['beta'])); a13 = math.radians(e13['az'])
    s13 = (np.array(P(e13['xp']-(1.25-0.40)*t13, 0.40, az=a13)), np.array(P(e13['xp']+0.35*t13, 1.60, az=a13)))
    cars = dict(S=h3.CARRIERS['S'], A=h3.CARRIERS['A'], K=h3.CARRIERS['K'])
    jf = out/'o13_sp12.json'
    if jf.exists():
        res = json.loads(jf.read_text())
    for name, kind, D, psi in SP12_O13:
        if name in res:
            continue
        t0 = time.time(); v = sp12_variant(name, kind, D, psi)
        obj, tree = ex.build_free(s, ctx.data, v['unions'], [], ex.TRUNK_EXT_X, fit=True)
        walls = h3.Walls(ctx.fx, ctx.pts, free=tree)
        route = ex.smooth(v['path'], cut=0.55) if kind != 'control' else v['path']
        row = dict(desc=v['desc'], kind=kind, clear_m=D, psi_deg=psi, carriers=sweep_sp12_carriers(walls, v, kind, route, cars, seeds, name))
        # opposite-side operation at the exit closure: release at the closure centre, operator in SP-12 (above the floor) and below it (duct / trunk side)
        rng = np.random.default_rng(seeds[0]); O = np.array(P(v['floor_x'], 1.25)); Rn = np.array(axes_at()[2])
        row['opposite_side_operation'] = dict(
            sp12_side=operator_fit(walls, P(v['floor_x'], 1.35), plane_side(O, Rn, lo=0.0), rng),
            trunk_side=operator_fit(walls, v['below_pt'], plane_side(O, Rn, hi=0.0), rng),
            note='operator torso capsule r 0.25 m, shoulder within 0.70 m of the release at the closure centre, wholly on one side of the SP-12 floor plane; the closure type and its release are the existing study model (sliding plug leaf, eva3_exits.closure_data)')
        ex.PSI = math.radians(psi if kind == 'oblique' else 15.0)
        vv = dict(kind=kind, D=D, area=v['area'], duct=v.get('duct'))
        row['closures'] = ex.closure_data(s, dict(vv, kind='oblique' if kind == 'fwd' else kind, duct=dict(v['duct'], xa=v['floor_x']+0.3) if kind == 'fwd' else v.get('duct'))); row['vehicle'] = ex.vehicle_screen(s, ctx.obs, dict(vv, kind='oblique' if kind == 'fwd' else kind))
        row['spine_core_cut_x_m'] = duct_spine_cut(s, v) if kind != 'control' else D
        ex.PSI = math.radians(15.0)
        sv_ = v['solid']; sep = seg_dist(sv_['a'], sv_['b'], s13[0], s13[1], n=120)-sv_['r']-e13['D']/2
        lands = v['duct']['xe'] if kind != 'control' else 101.8494
        row['vs_sp13'] = dict(solid_separation_m=round(sep, 3), status=status(sep),
                              route_envelope_gap_m=route_envelope_gap(route, route13, h3.CARRIERS['S']['radius'], h3.CARRIERS['S']['radius']),
                              sp12_route_enters_trunk_at_x=round(lands, 2), sp13_route_enters_trunk_at_x=round(xe13, 2),
                              shared='trunk extension / built trunk aft of the landings (the destination of both exits); no shared closure, no shared room volume',
                              note='solid separation = SP-12 exit solid (axis cylinder) to the SP-13 exit duct solid; route envelope gap = the S carrier capsules (r 0.43 m) along both routes outside the trunk (r >= 0.85 m)')
        row['seconds'] = round(time.time()-t0)
        rv = dict(legs={c: dict(least_m=q['least_m'], head=q['head'], axis=q['axis'], roll=q['roll']) for c, q in row['carriers'].items() if c in ('S', 'K')})
        try:
            ex.render_variant('o13_'+name, obj, rv, out)
            src = out/f'exit_o13_{name}_fit.png'
            if src.exists():
                (rdir/f'a170_sp12_{name}.png').write_bytes(src.read_bytes()); row['render'] = f'renders/p1/eva/district/a170_sp12_{name}.png'
        except Exception as exc:
            row['render_error'] = str(exc)
        if obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj)
        res[name] = row; jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
        print('WF_O13_SP12 done', name, row['seconds'], 's', flush=True)
    # the best variant re-run with six seeds
    best = max(res, key=lambda k: min(q['least_m'] for q in res[k]['carriers'].values()))
    if 'recheck_6_seeds' not in res[best]:
        name, kind, D, psi = next(q for q in SP12_O13 if q[0] == best); v = sp12_variant(name, kind, D, psi)
        obj, tree = ex.build_free(s, ctx.data, v['unions'], [], ex.TRUNK_EXT_X, fit=True); walls = h3.Walls(ctx.fx, ctx.pts, free=tree)
        route = ex.smooth(v['path'], cut=0.55) if kind != 'control' else v['path']; seeds6 = tuple(seeds)+(59, 73, 97)
        c6 = sweep_sp12_carriers(walls, v, kind, route, cars, seeds6, name+'_6SEEDS'); bpy.data.objects.remove(obj)
        res[best]['recheck_6_seeds'] = dict(seeds=list(seeds6), carriers=c6, least_m=min(q['least_m'] for q in c6.values()), status=status(min(q['least_m'] for q in c6.values())))
        jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
    return res


# ---------------------------------------------------------------------------------------------------------------------------------
# A170 SP-13 closure: (a) outward-offset hinged, positively dogged leaf; (b) dual isolation (two closures in series)

def keepout_placements_filter(pts, min_m):
    """Install a keep-out (sample points) into the layout search: a fixture placement within min_m of the points is rejected."""
    base = placements
    def wrapped(fi, e, asbuilt_ov, lane_min):
        return [f_ for f_ in base(fi, e, asbuilt_ov, lane_min) if float(obb_dist(pts, boxes_of([f_])[0]).min()) >= min_m]
    return base, wrapped


def run_o13_sp13(ctx, out, sp13, seeds=SEEDS, n_search=250):
    e = sp13['selected_exit']; fx = sp13['selected_layout']['fixture_list']; res = dict(exit=e, fixtures_used='SIM-027 selected rearranged fit-out (p1_eva_sp13_l1a.json sp13.selected_layout)')
    jf = out/'o13_sp13.json'
    if jf.exists():
        res = json.loads(jf.read_text())
    A, B = leaf_dims(e)
    res['leaf'] = dict(semi_axes_m=[round(A, 3), round(B, 3)], thickness_m=LEAF_T_M, seat_band_m=LEAF_SEAT_M, handwheel=dict(radius_m=WHEEL_R_M, proud_m=WHEEL_PROUD_M), dogs=DOGS_N,
                       plane='SP-13 floor plane (tangent at r 1.25 m, az 50) over the 45 deg exit aperture ellipse; leaf on the SP-13 side',
                       clear_area_m2=round(math.pi*(A-LEAF_SEAT_M)*(B-LEAF_SEAT_M), 3), leaf_outer_area_m2=round(math.pi*A*B, 3))
    # 1. pure geometry, every hinge edge and offset, single leaf and the stacked dual
    geo = res.setdefault('geometry', {})
    for layers, tag in (((0,), 'single'), ((0, 1), 'dual')):
        for edge in HINGE_EDGES:
            for o_h in HINGE_OFFSETS_M:
                geo[f'{tag}_{edge}_o{o_h:.2f}'] = leaf_geometry(ctx, fx, e, edge, o_h, layers)
    print('WF_O13_SP13 geometry', {k: (v['park_least_m'], v['swing_least_m']) for k, v in geo.items()}, flush=True)
    # 2. per hinge edge the offset that keeps the leaf (park and swing) inside the room best; the fit-out can be re-sited, the room walls cannot
    def room_of(k):
        return min(geo[k]['park']['to_room_m'], geo[k]['swing']['to_room_m'])
    choice = {}
    for tag in ('single', 'dual'):
        for edge in HINGE_EDGES:
            k = max((f'{tag}_{edge}_o{o:.2f}' for o in HINGE_OFFSETS_M), key=room_of); choice[(tag, edge)] = (k, float(k.rsplit('_o', 1)[1]))
    res['offset_choice'] = {f'{t_}_{e_}': dict(key=k, hinge_offset_m=o, room_m=room_of(k)) for (t_, e_), (k, o) in choice.items()}
    sweeps = res.setdefault('sweeps', {}); todo = []
    for edge in HINGE_EDGES:                       # every single-leaf edge on the selected fit-out (the parked leaf is the obstacle)
        k, o = choice[('single', edge)]; todo.append((f'single_{edge}_selected_fitout', 'single', edge, o, (0,), fx))
    # 3. re-sited fit-out per edge whose leaf stays inside the room: park + swing envelope as a keep-out for the layout search (what the hinged leaf
    #    needs from the room); the dual stacked leaves on the same re-sited fit-out when they stay inside the room too
    rs = res.setdefault('resited_layouts', {}); loc = leaf_local_points(e); res.setdefault('geometry_resited', {})
    for edge in HINGE_EDGES:
        k, o = choice[('single', edge)]
        if room_of(k) < 0:
            rs.setdefault(edge, dict(found=0, skipped=f'leaf outside the room walls ({room_of(k)} m): no fit-out arrangement can help'))
            continue
        if edge not in rs:
            keep = np.vstack([leaf_transform(e, edge, o, th)(loc) for th in np.arange(0.0, PARK_DEG+1e-9, 5.0)])
            base, wrapped = keepout_placements_filter(keep, MARGIN+0.02); globals()['placements'] = wrapped
            try:
                nz = fixture_list([dict(f) for f in ctx.data['sp13']['fixtures']]); ids = [f['id'] for f in nz]
                asb = {i: overflow_m(b) for i, b in zip(ids, boxes_of(nz))}
                fnd = search_layouts(nz, e, asb, n_search, np.random.default_rng(2710))
            finally:
                globals()['placements'] = base
            rs[edge] = dict(found=len(fnd), hinge=k, keepout_m=MARGIN+0.02, fixture_list=fnd[0][2] if fnd else None, metrics=fnd[0][3] if fnd else None,
                            fixtures=fixture_table(ctx, fnd[0][2], asb, e) if fnd else None)
            jf.write_text(json.dumps(res, indent=1, default=str)+'\n'); print('WF_O13_SP13 resited', edge, len(fnd), flush=True)
        if rs[edge].get('fixture_list'):
            fl = rs[edge]['fixture_list']; res['geometry_resited'][f'single_{edge}_o{o:.2f}'] = leaf_geometry(ctx, fl, e, edge, o, (0,))
            todo.append((f'single_{edge}_resited_fitout', 'single', edge, o, (0,), fl))
            kd, od = choice[('dual', edge)]; gd = leaf_geometry(ctx, fl, e, edge, od, (0, 1)); res['geometry_resited'][f'dual_{edge}_o{od:.2f}'] = gd
            if min(gd['park']['to_room_m'], gd['swing']['to_room_m']) >= 0:
                todo.append((f'dual_{edge}_resited_fitout', 'dual', edge, od, (0, 1), fl))
    for lab, tag, edge, o_h, layers, fxl in todo:
        if lab in sweeps:
            continue
        t0 = time.time()
        r, obj = eval_exit(ctx, fxl, e, f'O13_{lab}', seeds=seeds, keep=True, diffs=leaf_solids(e, edge, o_h, PARK_DEG, layers))
        walls = h3.Walls(ctx.fx, ctx.pts, free=h3_tree(obj))
        # opposite-side operation with the leaf CLOSED: handwheel on the SP-13 face and on the duct face; operator wholly on its side of the leaf
        O, X, T, R = frame13(e); rng = np.random.default_rng(seeds[0]); top = LEAF_T_M*len(layers)+DUAL_GAP_M*(len(layers)-1)
        ops = dict(sp13_side=operator_fit(walls, O+R*(top+WHEEL_PROUD_M), plane_side(O, R, lo=top+WHEEL_PROUD_M), rng),
                   trunk_side=operator_fit(walls, O-R*WHEEL_PROUD_M, plane_side(O, R, hi=-WHEEL_PROUD_M), rng))
        try:
            nm = render_sp13(ctx, obj, fxl, e, r, f'a170_sp13_{lab}', out, extra=leaf_solids(e, edge, o_h, PARK_DEG, layers, name='LEAFR'))
            (ROOT/'renders/p1/eva/district'/nm).write_bytes((out/nm).read_bytes()); rnd = f'renders/p1/eva/district/{nm}'
        except Exception as exc:
            rnd = f'render failed: {exc}'
        if obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj)
        g_ = leaf_geometry(ctx, fxl, e, edge, o_h, layers); allm = [worst_cars(r), g_['park_least_m'], g_['swing_least_m']]+[q['least_m'] if q['least_m'] is not None else -9 for q in ops.values()]
        sweeps[lab] = dict(variant=tag, hinge_edge=edge, hinge_offset_m=o_h, layers=len(layers), results=r, carriers_least_m=worst_cars(r), leaf_geometry=g_, least_m=round(min(allm), 3),
                           status=status(min(allm)), opposite_side_operation=ops, seconds=round(time.time()-t0), render=rnd, fitout='selected' if fxl is fx else 'resited')
        print('WF_O13_SP13 sweep', lab, sweeps[lab]['least_m'], {c: q['least_m'] for c, q in r.items()}, ops['sp13_side']['least_m'], ops['trunk_side']['least_m'], sweeps[lab]['seconds'], 's', flush=True)
        jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
    # 3b. the three best variants re-run with six seeds (the pose search is stochastic; differences below ~0.05 m are not significant)
    seeds6 = tuple(seeds)+(59, 73, 97); fxs = {'selected': fx}; fxs.update({f'resited_{k}': v['fixture_list'] for k, v in rs.items() if v.get('fixture_list')})
    for lab in sorted(sweeps, key=lambda k: -sweeps[k]['least_m'])[:3]:
        q = sweeps[lab]
        if 'recheck_6_seeds' in q:
            continue
        fl = fx if q['fitout'] == 'selected' else rs[q['hinge_edge']]['fixture_list']; layers = tuple(range(q['layers']))
        r6, _ = eval_exit(ctx, fl, e, f'O13_{lab}_6SEEDS', seeds=seeds6, diffs=leaf_solids(e, q['hinge_edge'], q['hinge_offset_m'], PARK_DEG, layers))
        g_ = q['leaf_geometry']; allm = [worst_cars(r6), g_['park_least_m'], g_['swing_least_m']]+[o['least_m'] for o in q['opposite_side_operation'].values()]
        q['recheck_6_seeds'] = dict(seeds=list(seeds6), results=r6, carriers_least_m=worst_cars(r6), least_m=round(min(allm), 3), status=status(min(allm)))
        print('WF_O13_SP13 recheck6', lab, q['recheck_6_seeds']['least_m'], {c: x['least_m'] for c, x in r6.items()}, flush=True)
        jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
    # 4. the opposite-seated second closure (a true pressure pair) and the 80 kPa cases
    res['opposite_seated_second_closure'] = second_closure_feasibility(ctx, e)
    res['pressure'] = dict(
        a_single=dp_cases('SP-13 hinged leaf (a)', res['leaf']['clear_area_m2'], res['leaf']['leaf_outer_area_m2'], 'SP-13 high (trunk or SP-13 side loss)', 'trunk high (SP-13 depressurized)'),
        b_dual_stacked=dict(dp_cases('SP-13 dual stacked leaves (b), each', res['leaf']['clear_area_m2'], res['leaf']['leaf_outer_area_m2'], 'SP-13 high', 'trunk high'),
                            note='both leaves lie on the SP-13 side, so trunk-high is the reverse case for both: two independent dog sets in series carry it, neither hinge'),
        both_directions_status='OPEN: no structural rating, seat, dog or hinge capacity, factor or relief setpoint; owner hold "do not assume ordinary hinge resists reversed pressure" applied')
    res['single_fault'] = single_fault_table()
    jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
    return res


def h3_tree(obj):
    from mathutils.bvhtree import BVHTree
    me = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh(); vs = [obj.matrix_world@v.co for v in me.vertices]; fs = [tuple(p.vertices) for p in me.polygons]
    return BVHTree.FromPolygons(vs, fs)


def second_closure_feasibility(ctx, e):
    """Where an opposite-seated second closure (leaf on the trunk side, seated by trunk-high pressure) could sit on the SP-13 exit: pure geometry."""
    s = ctx.s; tr = s['crew_transfer']['trunk_clear_radius_m']; w = s['crew_transfer']['passage_wall_m']; b = math.radians(e['beta']); D = e['D']; R1 = D/2+LEAF_SEAT_M
    # (i) a second seat normal to the duct axis inside the duct: the whole seat ring must stay outside the trunk wall (r >= tr + w) and below the floor
    need_c = tr+w+R1*math.sin(b)                         # seat centre radius so the lowest rim point clears the trunk wall (rim offsets +-R1 sin(beta) in r)
    floor_c = 1.25-R1*math.sin(b)                        # seat centre radius so the highest rim point stays under the floor
    # (ii) a transverse hatch across the trunk extension between the SP-13 duct's aft edge on the trunk wall and the district port's forward edge
    duct_aft_x = e['xp']-(1.25-(tr+w))*math.tan(b)-(D/2)/math.cos(b)
    return dict(
        in_duct_normal_seat=dict(seat_ring_radius_m=round(R1, 3), centre_r_needed_to_clear_trunk_wall_m=round(need_c, 3), centre_r_allowed_below_floor_m=round(floor_c, 3),
                                 fits=bool(need_c <= floor_c), shortfall_m=round(need_c-floor_c, 3),
                                 note='the 45 deg duct is 1.24 m long; a second seat normal to its axis needs its centre at r >= the first value and <= the second: the duct is too short'),
        trunk_transverse_hatch=dict(sp13_duct_aft_edge_on_trunk_wall_x=round(duct_aft_x, 3), district_port_forward_edge_x=round(104.1+0.45, 3),
                                    window_m=round(duct_aft_x-(104.1+0.45), 3), ladder_top_x=LADDER_TOP_X,
                                    crosses_extended_ladder=True,
                                    note='a transverse hatch frame (bore 1.10 m, ring to r 0.80 m) between X 104.55 and the duct edge would cut both stiles and the arrest rail of the L1-A ladder (r 0.64 m), i.e. a new ladder break, and its 1.20 m leaf can only park as a chord at <= 0.53 m off the axis (the trunk is 1.60 m): not evaluated further'),
        stacked_same_side='evaluated as (b): two leaves in series on the SP-13 side, both seated by SP-13-high, both dogged for trunk-high')


def single_fault_table():
    return {
        '(a) single hinged dogged leaf': dict(
            seal_or_leaf_fault='isolation between SP-13 and the trunk lost (one barrier); the SP-12/SP-13 door does not bound this path',
            one_dog_fails=f'{DOGS_N-1} dogs remain for trunk-high; their capacity OPEN', hinge_fault='not a pressure path by rule; leaf held by the dogs when closed; a jammed hinge blocks the exit (manual recovery: OPEN, see handwheel reach)',
            manual_recovery='handwheel on both faces (through spindle) reaches the dogs from either side; equalization valve and dp interlock threshold OPEN',
            single_fault_tolerant='NO (one barrier)'),
        '(b) dual stacked leaves': dict(
            seal_or_leaf_fault='the other leaf keeps the isolation in both directions (SP-13-high by its seat, trunk-high by its dogs)',
            one_dog_set_fails='the other leaf\'s dogs carry trunk-high; capacity OPEN', hinge_fault='one leaf jammed open: the other still isolates; one jammed shut: the exit is blocked until manual recovery',
            manual_recovery='each leaf has its own handwheel on both faces; between-leaf vent and equalization OPEN',
            single_fault_tolerant='YES for isolation (geometry and logic only); NO for exit availability (two leaves in series, either jammed shut blocks the exit)'),
        'opposite-seated pair (a true pressure pair)': dict(single_fault_tolerant='not placeable in the present SP-13 exit (see opposite_seated_second_closure)')}


# ---------------------------------------------------------------------------------------------------------------------------------
# A171: L1-A district port 205-215 deg as a reversible WHITEBOX, whole route

class WallsPlus(h3.Walls):
    """h3.Walls plus an extra BVH of study rods (the L1-A ladder extension: stiles, rungs and arrest rail from the built top to X 104.9)."""

    def __init__(self, records, pts, free=None, extra=None):
        super().__init__(records, pts, free)
        self.extra = extra                      # (BVHTree, label)

    def overlaps(self, vs, fs):
        n = super().overlaps(vs, fs)
        if n is None and self.extra is not None:
            from mathutils.bvhtree import BVHTree
            if BVHTree.FromPolygons(vs, fs).overlap(self.extra[0]):
                return self.extra[1]
        return n

    def point(self, p):
        best = super().point(p)
        if self.extra is not None:
            loc, n, _, dist = self.extra[0].find_nearest(Vector(p))
            if loc is not None and dist < best[0]:
                best = (dist, self.extra[1])
        return best


def ladder_extension_rods(s):
    """The L1-A ladder from the built top over the bridged dock mouth to X 104.9 at 285 deg: two stiles, the arrest rail and rungs on the built pitch
    (the accepted rigid bridge carries the same members). Returns ((BVHTree, label), rung count)."""
    from mathutils.bvhtree import BVHTree
    G = ladder_geom(s, 285.0); p_ = s['human_entry']['spoke_rung_pitch_m']; x0 = G['top_built']; vs, fs = [], []; objs = []
    for ln, (rho, ang, rr) in G['lines'].items():
        objs.append(h3.prim_cyl((x0, rho*math.cos(ang), rho*math.sin(ang)), (LADDER_TOP_X, rho*math.cos(ang), rho*math.sin(ang)), rr, seg=12))
    last = max(G['rungs']); xs = np.arange(last+p_, LADDER_TOP_X-0.05, p_)
    for x in xs:
        a0, a1 = G['th']-G['phi'], G['th']+G['phi']
        objs.append(h3.prim_cyl((x, G['rl']*math.cos(a0), G['rl']*math.sin(a0)), (x, G['rl']*math.cos(a1), G['rl']*math.sin(a1)), ROD_R_M, seg=12))
    bpy.context.view_layer.update()
    for o in objs:
        me = o.data; off = len(vs); vs += [tuple(o.matrix_world@v.co) for v in me.vertices]; fs += [tuple(i+off for i in p.vertices) for p in me.polygons]
        bpy.data.objects.remove(o)
    return (BVHTree.FromPolygons(vs, fs), 'L1A_LADDER_EXTENSION'), len(xs)


def port_rim(alpha_deg, x=104.1, r=0.45, rt=0.80, n=180):
    th = math.radians(alpha_deg); nrm = ct.radial(0, 1.0, th); e_ = (0.0, -math.sin(th), math.cos(th)); out = []
    for k in range(n):
        psi = 2*math.pi*k/n; lat = r*math.sin(psi); a_ = math.sqrt(max(0.0, rt*rt-lat*lat)); out.append((x+r*math.cos(psi), a_*nrm[1]+lat*e_[1], a_*nrm[2]+lat*e_[2]))
    return out


def climber_vs_rims(s, rims, x_from, x_to):
    """The 1.5 g climber figure (he.trunk_climber, both hands on the stiles) moved rung by rung along the ladder: least distance of its rods to the
    rim curves of the given openings (a rim is an edge a hand or boot can catch)."""
    clim = he.trunk_climber(s); out = {}
    for nm, rim in rims.items():
        kd = KDTree(len(rim)); [kd.insert(Vector(q), i) for i, q in enumerate(rim)]; kd.balance(); worst = (math.inf, None, None)
        for x_f in np.arange(x_from, x_to, 0.1):
            dx = x_f-clim['feet_x']
            for rn, pts, rad in clim['rods']:
                for k in range(7):
                    a_ = np.add(pts[0], np.subtract(pts[1], pts[0])*k/6)+np.array((dx, 0, 0)); dd = kd.find(Vector(a_))[2]-rad
                    if dd < worst[0]:
                        worst = (dd, rn, round(float(x_f), 2))
        out[nm] = dict(least_m=round(min(worst[0], 1.0), 3), body_part=worst[1], feet_x=worst[2], status=status(worst[0]))
    return out, clim


def cyl_points(a, b, rad, r_min, step=0.04):
    """Surface and axis sample points of a cylinder solid, kept where they lie outside the trunk wall (r >= r_min): the part that is structure, not trunk bore."""
    a = np.asarray(a, float); b = np.asarray(b, float); ax = b-a; L = float(np.linalg.norm(ax)); ax /= L
    tv = np.cross(ax, (1.0, 0.0, 0.0)); tv = tv/np.linalg.norm(tv) if np.linalg.norm(tv) > 1e-6 else np.array((0.0, 1.0, 0.0)); uv = np.cross(ax, tv); out = []
    for q in np.arange(0.0, L+1e-9, step):
        c = a+ax*q; out.append(c)
        for k in range(36):
            ph = 2*math.pi*k/36; out.append(c+rad*(math.cos(ph)*tv+math.sin(ph)*uv))
    P_ = np.array(out); return P_[np.hypot(P_[:, 1], P_[:, 2]) >= r_min]


def pts_gap(A, B):
    if not len(A) or not len(B):
        return None
    kd = KDTree(len(B)); [kd.insert(Vector(p), i) for i, p in enumerate(B)]; kd.balance()
    return min(kd.find(Vector(p))[2] for p in A)


def run_o13_l1a(ctx, out, sp13, sp12_choice, seeds=SEEDS):
    s = ctx.s; e13 = sp13['selected_exit']; res = dict(port_alphas_deg=list(PORT_ALPHAS), states_note=STATES_NOTE, sp13_exit=e13, sp12_exit=sp12_choice)
    jf = out/'o13_l1a.json'
    if jf.exists():
        res.update({k: v for k, v in json.loads(jf.read_text()).items() if k in ('carriers',)})
    # openings for the ladder rule: the built ones + the moved district port + the SP-13 exit + the chosen SP-12 exit's trunk landing (N1 dropped, A170)
    sp12_op = None
    if sp12_choice and sp12_choice.get('kind') in ('oblique', 'fwd'):
        sp12_op = ('SP12_Exit_'+sp12_choice['name'], sp12_choice['wall_x'], ex.AZ, sp12_choice['D']/2/math.sin(math.radians(sp12_choice['psi_deg'])))
    def ops_o13(alpha):
        o = [tuple(q) for q in he.openings(s)]+[('District_Port', 104.1, math.radians(alpha), 0.45), ('SP13_Exit', e13['xp'], math.radians(e13['az']), e13['D']/2)]
        return o+([sp12_op] if sp12_op else [])
    G = ladder_geom(s, 285.0); recs = cs.scene(s, cs.load_inspect(), 1.0); tp = fixture_tree(recs); f0 = ladder_fixture_clearance(ctx, 285.0, tp)
    xs = np.arange(G['floor'], LADDER_TOP_X+1e-9, 0.01); rows = {}
    for al in PORT_ALPHAS+(240.0,):
        ops = ops_o13(al); lines = {}; worst = (math.inf, None, None, None); extra = {0.0: [], 0.2: []}; dock = {0.0: 0.0, 0.2: 0.0}
        for ln, (rho, ang, rr) in G['lines'].items():
            for m in (0.0, 0.2):
                gaps = merge_gaps(line_blocks(rho, ang, ops, m), G['floor'], LADDER_TOP_X)
                for g in gaps:
                    if g[0] <= 99.4 <= g[1]:
                        dock[m] = max(dock[m], g[1]-g[0])
                    else:
                        extra[m].append(dict(line=ln, a=g[0], b=g[1], by=g[2]))
            skip = [(g[0], g[1]) for g in merge_gaps(line_blocks(rho, ang, ops, 0.2), G['floor'], LADDER_TOP_X) if g[0] <= 99.4 <= g[1]]
            g0 = signed_gap(rho, ang, rr, ops, xs, skip); lines[ln] = dict(least_m=round(g0[0], 3), opening=g0[1], x=None if g0[2] is None else round(g0[2], 2))
            if g0[0] < worst[0]:
                worst = (g0[0], ln, g0[1], g0[2])
        pe = [o for o in ops if o[0] == 'District_Port']; ang = G['lines']['stile_a']
        port_edge = min(signed_gap(rho, a_, rr, pe, xs, [])[0] for rho, a_, rr in G['lines'].values())
        rows[str(int(al))] = dict(ladder_least_m=round(worst[0], 3), ladder_least_at=dict(line=worst[1], opening=worst[2], x=None if worst[3] is None else round(worst[3], 2)), by_line=lines,
                                  port_edge_to_ladder_m=round(port_edge, 3), port_edge_status=status(port_edge), dock_window_m={'0.0': round(dock[0.0], 3), '0.2': round(dock[0.2], 3)},
                                  new_ladder_breaks={f'margin_{m:.2f}': extra[m] for m in (0.0, 0.2)},
                                  no_new_ladder_break=bool(not extra[0.0]) and dock[0.2] <= BRIDGE_ACCEPTED_M+1e-9)
    ports, rot_ok = port_options(ctx)
    for al in PORT_ALPHAS+(240.0,):
        rows[str(int(al))]['port_screen'] = ports.get(int(al))
    res['ladder_rows'] = rows; res['trunk_fixture_clearance'] = dict(least_m=round(f0[0], 3), line=f0[1], x=f0[2], nearest=f0[3]); res['hoist_offset_margin_m'] = hoist_margin(s, 285.0)
    # pressure boundary: the moved port tube against the exit solids and the closure of SP-13
    eva, br = ed.eva_elements(s, ctx.data, ctx.lead); pb = {}
    t13 = math.tan(math.radians(e13['beta'])); a13 = math.radians(e13['az']); s13 = (P(e13['xp']-(1.25-0.40)*t13, 0.40, az=a13), P(e13['xp']+0.35*t13, 1.60, az=a13))
    for al in PORT_ALPHAS:
        pt = (ct.radial(104.1, 0.80, math.radians(al)), ct.radial(104.1, ports[int(al)]['port_tube_outer_r_m'], math.radians(al))); ro = sd.PORT_CLEAR/2+s['crew_transfer']['passage_wall_m']
        r_wall = s['crew_transfer']['trunk_clear_radius_m']+s['crew_transfer']['passage_wall_m']
        tube = cyl_points(pt[0], pt[1], ro, r_wall); d13 = pts_gap(tube, cyl_points(s13[0], s13[1], e13['D']/2, r_wall))
        d12 = None
        if sp12_choice and sp12_choice.get('solid'):
            q = sp12_choice['solid']; d12 = round(pts_gap(tube, cyl_points(q['a'], q['b'], q['r'], r_wall)), 3)
        pb[str(int(al))] = dict(port_tube_to_sp13_exit_solid_m=round(d13, 3), port_tube_to_sp12_exit_solid_m=d12, basis='sampled solids outside the trunk wall (r >= 0.85 m), surface to surface, +-0.04 m', vehicle_hits=ports[int(al)]['vehicle_hits'], inside_hull=ports[int(al)]['inside_hull'],
                                overlaps_eva_or_cell=ports[int(al)]['overlaps_eva_or_cell'], status=ports[int(al)]['status'])
    res['pressure_boundary'] = pb
    # climber (1.5 g pose) against the rims, from the bridge top to the ladder top; one-handed traverse geometry
    rims = {f'District_Port_{int(al)}': port_rim(al) for al in PORT_ALPHAS+(240.0,)}
    cr, clim = climber_vs_rims(s, rims, 99.0, LADDER_TOP_X-1.6)
    res['climber_vs_port_rim'] = cr
    pitch = s['human_entry']['spoke_rung_pitch_m']
    res['one_handed_traverse'] = dict(rung_pitch_m=pitch, arm_reach_m={k: round(v, 3) for k, v in clim['reach'].items()},
                                      grip_lines_continuous={a_: rows[a_]['no_new_ladder_break'] for a_ in rows},
                                      note='geometry only: both stiles and the arrest rail are continuous over [built top, 104.9] apart from the one bridged dock mouth, so one hand always has a stile or rung within one pitch; the regrip dynamics, the free hand carrying a litter end and the arrester behaviour are OPEN',
                                      status='OPEN (dynamics); geometry: no grip lost to the moved port')
    res['tether_fall_load'] = dict(status='OPEN', value=None, note='no arrest-rail, anchor, lanyard or body-load number is assumed (owner A171 evidence item)')
    # multi-rig carrier sweep in the trunk extension past the moved port, the ladder extension and the dock bridge (free poses; any state)
    if 'carriers' not in res:
        res['carriers'] = {}
    rods, nr = ladder_extension_rods(s); res['ladder_extension_rungs'] = nr
    for al in PORT_ALPHAS:
        key = str(int(al))
        if key in res['carriers']:
            continue
        t0 = time.time(); w = s['crew_transfer']['passage_wall_m']
        port = lambda al=al: h3.prim_cyl(ct.radial(104.1, 0.60, math.radians(al)), ct.radial(104.1, ports[int(al)]['port_tube_outer_r_m'], math.radians(al)), 0.45)
        obj, tree = ex.build_free(s, ctx.data, [port, exit_solid(e13)], [], ex.TRUNK_EXT_X, sp12=False, sp13=False, ref=True, fit=False)
        walls = WallsPlus(ctx.fx, ctx.pts, free=tree, extra=rods)
        route = [('E', (105.3, 0.0, 0.0)), ('E', (104.1, 0.0, 0.0)), ('T', (101.0, 0.0, 0.0)), ('T', (97.0, 0.0, 0.0))]
        cars = carriers(ctx); row = {}
        for cid in ('S', 'A', 'K', 'U'):
            per = [h3.sweep_route(walls, cars[cid], route, np.random.default_rng(sdv), staff=(cid != 'U')) for sdv in seeds]
            body = [r['least_m'] for r in per]; stf = [r['staff_least_m'] for r in per if r['staff_least_m'] is not None]; k = int(np.argmin(body)); least = min(body+stf)
            row[cid] = dict(least_m=round(least, 3), body_least_m=min(body), rescuers_least_m=min(stf) if stf else None, status=status(least), nearest=per[k]['nearest'], zone=per[k]['zone'],
                            rescuer_nearest=[r['staff_nearest'] for r in per], seed_spread_m=[round(min(body+stf), 3), round(max(body+stf), 3)])
            print('WF_O13_L1A carriers', al, cid, row[cid]['least_m'], body, stf, row[cid]['nearest'], flush=True)
        row['seconds'] = round(time.time()-t0); res['carriers'][key] = row
        bpy.data.objects.remove(obj); jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
    # whole-route total clearance per port angle: the minimum of every measured element (the local +0.018 m counts as what it is)
    whole = {}
    for al in PORT_ALPHAS:
        k = str(int(al)); r_ = rows[k]; c_ = res['carriers'][k]
        items = {'ladder lines vs every opening (built ladder incl.)': r_['ladder_least_m'], 'moved port edge vs ladder': r_['port_edge_to_ladder_m'],
                 'ladder vs trunk fixtures': res['trunk_fixture_clearance']['least_m'], 'climber (1.5 g pose) vs moved port rim': cr[f'District_Port_{k}']['least_m'],
                 'hoist line 0.25 m @105 deg, A vs ladder rods': res['hoist_offset_margin_m']['A'], 'hoist line, S vs ladder rods': res['hoist_offset_margin_m']['S'],
                 'port tube vs SP-13 exit solid': pb[k]['port_tube_to_sp13_exit_solid_m']}
        if pb[k]['port_tube_to_sp12_exit_solid_m'] is not None:
            items['port tube vs SP-12 exit solid'] = pb[k]['port_tube_to_sp12_exit_solid_m']
        for cid in ('S', 'A', 'K', 'U'):
            items[f'carrier {cid} past the extended ladder' + (' with rescuers' if cid != 'U' else ' (suited crew, self-propelled)')] = c_[cid]['least_m']
        kk = min(items, key=items.get)
        whole[k] = dict(items=items, least_m=items[kk], limiting=kk, status=status(items[kk]) if r_['no_new_ladder_break'] and pb[k]['status'] == 'CLEAR' else 'FAIL',
                        no_new_ladder_break=r_['no_new_ladder_break'], port_screen=pb[k]['status'])
    res['whole_route'] = whole
    jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
    return res


# ---------------------------------------------------------------------------------------------------------------------------------
# segments and the merge into the reference files (old entries kept)

def o13_segments(S12, S13, L):
    out = []; ALL = ["0g", "spin", "stopped", "locked_1.5g"]
    for nm, r in S12.items():
        six = r.get('recheck_6_seeds')                 # worst case (RINGB-006): a six-seed recheck replaces the three-seed result
        for cid, q in r['carriers'].items():
            sd = list(SEEDS)
            if six and cid in six['carriers']:
                q, sd = six['carriers'][cid], six['seeds']
            out.append(seg(f'A170-SP12-{nm}-{cid}', 'SP-12 exit (A170)', ALL, nm, f'carrier {cid} with two rescuers, chamber -> SP-12 -> exit -> trunk', q['least_m'],
                           [f'carrier {cid}', 'body', 'rescuers at both ends', f'seeds {sd}'], q['seed_spread_m'], q['nearest'] if q['body_least_m'] <= (q['rescuers_least_m'] if q['rescuers_least_m'] is not None else 9) else q['rescuer_nearest'],
                           f'body {q["body_least_m"]:+.3f} m (zone {q["zone"]}), rescuers {q["rescuers_least_m"]}; sampled-pose sweep capped 0.10 m; {r["desc"]}.'))
        for side, q in r['opposite_side_operation'].items():
            if side == 'note':
                continue
            out.append(seg(f'A170-SP12-{nm}-OP-{side}', 'SP-12 exit (A170)', ALL, nm, f'opposite-side operation of the exit closure from the {side.replace("_", " ")}', q['least_m'],
                           ['operator torso r 0.25 m', 'shoulder within 0.70 m of the release'], None, q['nearest'], f'reach used {q["reach_used_m"]} m.'))
        v = r['vs_sp13']
        out.append(seg(f'A170-SP12-{nm}-VS-SP13', 'SP-12 exit (A170)', ALL, nm, 'SP-12 exit solid vs the SP-13 exit duct solid (independence)', v['solid_separation_m'],
                       ['axis-cylinder solids'], None, 'SP-13 exit duct', f'route envelope gap (S capsules outside the trunk) {v["route_envelope_gap_m"]} m; shared trunk only. Wall thickness between OPEN.'))
        vs_ = r['vehicle']
        out.append(seg(f'A170-SP12-{nm}-VEHICLE', 'SP-12 exit (A170)', ALL, nm, 'exit solid vs the saved vehicle (0.15 m)', None, ['stationary meshes', 'hull'], None, ', '.join(vs_['hits']) or None,
                       f'{vs_["status"]}; spine-core cut {r["spine_core_cut_x_m"]} m of X (OPEN).', 'PASS' if vs_['status'] == 'CLEAR' else 'FAIL'))
    for lab, q in S13['sweeps'].items():
        six = q.get('recheck_6_seeds'); least = min(q['least_m'], six['least_m']) if six else q['least_m']
        out.append(seg(f'A170-SP13-CLOSURE-{lab}', 'SP-13 closure (A170)', ALL, f'{q["variant"]} hinged dogged leaf, hinge {q["hinge_edge"]}, offset {q["hinge_offset_m"]} m, {q["fitout"]} fit-out',
                       'carriers A, S, K (two rescuers) and suited crew through the exit with the leaf parked open, the leaf park and swing envelopes, operation from both sides; minimum over all', least,
                       ['carrier A', 'carrier S', 'carrier K', 'suited crew', 'rescuers', 'leaf park', 'leaf swing 5-90 deg', 'operator SP-13 side', 'operator trunk side', f'seeds {six["seeds"] if six else list(SEEDS)}'],
                       None, min(q['results'].items(), key=lambda kv: kv[1]['least_m'])[1]['nearest'],
                       f'carriers {({c: x["least_m"] for c, x in q["results"].items()})}; leaf park {q["leaf_geometry"]["park_least_m"]}, swing {q["leaf_geometry"]["swing_least_m"]}; operators {({k: o["least_m"] for k, o in q["opposite_side_operation"].items()})}.'))
        for side, o in q['opposite_side_operation'].items():
            out.append(seg(f'A170-SP13-CLOSURE-{lab}-OP-{side}', 'SP-13 closure (A170)', ALL, lab, f'operation of the closed leaf from the {side.replace("_", " ")}', o['least_m'], ['operator torso r 0.25 m', 'shoulder within 0.70 m of the handwheel'], None, o['nearest'], f'reach used {o["reach_used_m"]} m.'))
    for k, g in [(k, g) for k, g in S13['geometry'].items()]+[('resited_'+k, g) for k, g in S13.get('geometry_resited', {}).items()]:
        out.append(seg(f'A170-SP13-LEAF-{k}', 'SP-13 closure (A170)', ALL, k, 'leaf parked (90 deg) and swing envelope vs room walls and fit-out', min(g['park_least_m'], g['swing_least_m']),
                       ['park envelope', 'swing 5-90 deg', 'room walls', 'fit-out boxes'], None, g['park']['nearest_fixture'], f'park {g["park"]}, swing {g["swing"]}.'))
    for key, p in S13['pressure'].items():
        if isinstance(p, dict):
            out.append(seg(f'A170-SP13-DP80-{key}', 'SP-13 closure (A170)', ALL, key, '80 kPa nominal both directions', None, list(p.get('directions', {}).keys()), None, None,
                           f'ideal dp x clear area {p.get("ideal_dp_x_clear_area_kn")} kN, x leaf outer {p.get("ideal_dp_x_leaf_outer_area_kn")} kN (DIAGNOSTIC); no rating; hinge not assumed to resist reversed pressure.', 'OPEN'))
    for al, w in L['whole_route'].items():
        out.append(seg(f'A171-L1A-PORT{al}-ROUTE', 'L1-A district (A171)', ALL, f'district port moved to {al} deg (reversible WHITEBOX), ladder 285 deg', 'whole route: minimum over every measured element', w['least_m'],
                       list(w['items']), None, w['limiting'], f'no new ladder break: {w["no_new_ladder_break"]}; port screen {w["port_screen"]}. {STATES_NOTE}.', w['status']))
        for i_, (it, val) in enumerate(w['items'].items()):
            out.append(seg(f'A171-L1A-PORT{al}-E{i_:02d}', 'L1-A district (A171)', ALL, f'port {al} deg', it, val, [it], None, None, 'element of the whole-route minimum.'))
    out.append(seg('A171-L1A-TETHER-FALL', 'L1-A district (A171)', ["locked_1.5g", "0g", "spin", "stopped"], 'ladder 285 deg, port 205-215 deg', 'tether fall load on the arrest rail', None, [], None, None, 'OPEN: no load assumed.', 'OPEN'))
    return out


def merge_refs(S12, S13, L, segs):
    jf = ROOT/'references/p1_eva_sp13_l1a.json'; d = json.loads(jf.read_text())
    d[O13_TAG] = dict(owner_refs=['15!A170 RESCUE-PORTS', '15!A171 DIST-L1-STEP (L1-A)'], status='NONCANON PROTOTYPE, disposable geometry; zero canonical geometry change; cutout and pressure rating HOLD',
                      band=BAND, seeds=list(SEEDS),
                      constants=dict(leaf_seat_m=LEAF_SEAT_M, leaf_t_m=LEAF_T_M, hinge_offsets_m=list(HINGE_OFFSETS_M), park_deg=PARK_DEG, wheel_r_m=WHEEL_R_M, wheel_proud_m=WHEEL_PROUD_M,
                                     dogs_n=DOGS_N, dual_gap_m=DUAL_GAP_M, op_reach_m=OP_REACH_M, op_r_m=OP_R_M, dp_nominal_kpa=CABIN_KPA_O13),
                      sp12=S12, sp13_closure=S13, l1a=L)
    jf.write_text(json.dumps(d, indent=1, default=str)+'\n')
    sf = ROOT/'references/p1_access_seg_sp13_l1a.json'; d = json.loads(sf.read_text())
    keep = [g for g in d['segments'] if not g['id'].startswith(('A170-', 'A171-'))]
    d['segments'] = keep+segs; d['study'] = d['study'].split(' + owner 2026-10-13')[0]+' + owner 2026-10-13 15!A170/A171 extensions (A170-*/A171-* segments)'
    sf.write_text(json.dumps(d, indent=1)+'\n')


def main_o13(out, parts):
    ctx = load_ctx(); out.mkdir(parents=True, exist_ok=True)
    sp13 = json.loads((ROOT/'references/p1_eva_sp13_l1a.json').read_text())['sp13']
    S12 = run_o13_sp12(ctx, out, sp13) if 'sp12' in parts else None
    S13 = run_o13_sp13(ctx, out, sp13) if 'sp13' in parts else None
    if not ('l1a' in parts or 'merge' in parts):
        print('WF_O13 done (partial)', parts, flush=True); return
    S12 = S12 or json.loads((out/'o13_sp12.json').read_text()); S13 = S13 or json.loads((out/'o13_sp13.json').read_text())
    # the SP-12 choice for the ladder rule and the port-tube check: the best N2/N3 (oblique) by the worst carrier, else the best overall
    best = max(S12, key=lambda k: (S12[k]['vehicle']['status'] == 'CLEAR', min(q['least_m'] for q in S12[k]['carriers'].values())))
    v = sp12_variant(*next(t for t in SP12_O13 if t[0] == best))
    d_ = v.get('duct') or {}; wall_x = None
    if d_:
        tt = math.tan(math.radians(v['psi_deg'])); wall_x = d_['xa']+(d_['ra']-0.80)/tt if v['kind'] == 'fwd' else d_['xa']-(d_['ra']-0.80)/tt
    choice = dict(name=best, kind=v['kind'], D=v['D'], psi_deg=v.get('psi_deg'), lands_x=d_.get('xe'), wall_x=wall_x, solid=v['solid'])
    L = run_o13_l1a(ctx, out, sp13, choice) if 'l1a' in parts else json.loads((out/'o13_l1a.json').read_text())
    L['sp12_exit'] = dict(choice, solid={k: (list(map(float, x)) if isinstance(x, tuple) else x) for k, x in choice['solid'].items()})
    segs = o13_segments(S12, S13, L)
    if 'merge' in parts:
        merge_refs(S12, S13, L, segs)
    print('WF_O13 done', len(segs), 'segments', flush=True)


# =================================================================================================================================
# Owner 2026-10-13b (S&E 15!A176 OWN-RES-B1, 15!A177 OWN-RES-B2, 15!A178 OWN-RES-C1; verbatim in references/drive_capture_2026-10-13c/engineering.txt
# lines 733-735). Disposable study, zero canonical geometry change: the 45 deg duct is never represented as installed, no pressure-shell edit, no
# load, rating or mass. Results under the key `owner_2026_10_13b` of references/p1_eva_sp13_l1a.json, segments A176-* / A177-* / A178-*.
#   b1 (A176): N2 fwd45 as the NEXT REVERSIBLE comparison only: opposite-side operation retest (six seeds, search to 0.30 m instead of the 0.10 m
#       cap), single faults (jammed closures as logic; an incapacitated rescuer as an obstacle in the duct / the extension), the complete litter route
#       chamber -> SP-12 -> duct -> extension -> shunt aft past the dock mouth to the refuge port station with the L1-A ladder extension as obstacle,
#       and the hoist interfaces (lift under locked 1.5 g, anchor station, line sweep against the SP-13 exit and the ladder); anchor loads OPEN.
#   b2 (A177): failure tree of SP-12 single faults against the SP-13 exit (sweeps of the SP-13 route with the fault as an obstacle), the
#       simultaneous-use case, pressure isolation, and alternate SP-12 layouts that move the SP-12 corridor (six seeds each).
#   c1 (A178): the SP-13 aft-hinged dogged leaf with modest partition / mount moves (0.02-0.10 m PROTOTYPE steps): leaf swing and park, carriers
#       (six seeds), operation from both sides, outer (trunk-side) leaf access against the SP-12 corridor; the pressure items stay OPEN.

O13B_TAG = 'owner_2026_10_13b'
SEEDS6 = tuple(SEEDS)+(59, 73, 97)
SHIFT_STEPS_M = (0.0, 0.02, 0.04, 0.06, 0.08, 0.10)     # partition / leaf-mount moves tried (PROTOTYPE, owner "modest"): partition aft (dP), mount
                                                         # forward along X (dM), mount sideways toward the room's centre azimuth (dT, tangential at r 1.25)
HINGE_OFFSETS_B = (0.02, 0.04, 0.06)                     # aft hinge outward offsets tried with the moves (PROTOTYPE)
OP_CAP_B = 0.30                                           # operator retest: the placement search runs to 0.30 m instead of the 0.10 m cap
PUSH_AZ_DEG = 140.0             # a stuck carrier / incapacitated body pushed against the bore wall here: away from the SP-13 and SP-12 exits (50 deg),
                                # the ladder (285 deg) and the moved district port (205-215 deg); PROTOTYPE
N2F = ('N2_fwd45_1.10', 'fwd', 1.10, 45.0)
ALT_SP12 = (('N2_fwd60_1.10', 'fwd', 1.10, 60.0), ('N2_oblique30_1.10', 'oblique', 1.10, 30.0))
BODY = dict(name='incapacitated rescuer (tucked body, hum003 STAFF_BODY_M)', shape='capsule', length=h3.STAFF_BODY_M, radius=h3.STAFF_R_M)
EXT_AFT_X = 102.45              # aft end of the L1-A trunk extension (the built trunk's forward end)


def refuge_x(s):
    return next(q[1] for q in he.openings(s) if q[0] == 'Crew_Refuge_Port')


def duct_x_at(v, r):
    d = v['duct']; t = math.tan(math.radians(v['psi_deg']))
    return d['xa']+(d['ra']-r)/t if v['kind'] == 'fwd' else d['xa']-(d['ra']-r)/t


def body_solid(car, head, d, roll=0.0):
    """A parked carrier or body as an obstacle (closed mesh maker for build_free diffs); a capsule is drawn as its full-length cylinder (conservative)."""
    if car['shape'] == 'box':
        c, ax, hs = h3.boxes(dict(car, kit=None), head, d, roll)[0]
        return lambda c=c, ax=ax, hs=hs: h3.prim_box(tuple(c), [tuple(a) for a in ax], tuple(2*x for x in hs))
    a = np.asarray(head, float); b = a+np.asarray(d, float)*car['length']
    return lambda a=a, b=b, r=car['radius']: h3.prim_cyl(tuple(a), tuple(b), r, seg=32)


def pushed_pose(car, xc, az_deg=PUSH_AZ_DEG, gap=0.02):
    """A carrier / body lying along the bore, pushed against the 1.6 m bore wall at az, centred at X xc: (head, axis, roll)."""
    a = math.radians(az_deg); n = np.array((0.0, math.cos(a), math.sin(a))); tang = np.array((0.0, -math.sin(a), math.cos(a))); d = np.array((-1.0, 0.0, 0.0))
    tr = 0.80-gap
    if car['shape'] == 'box':
        L, W, T = car['size']; rc = math.sqrt(tr*tr-(W/2)**2)-T/2; u, w0, t0 = h3.frame(d, 0.0); roll = math.atan2(float(np.dot(tang, t0)), float(np.dot(tang, w0)))
    else:
        L = car['length']; rc = tr-car['radius']; roll = 0.0
    return (np.array((xc+L/2, 0.0, 0.0))+n*rc, d, roll)


def obstacle_poses(v):
    """Stuck-carrier poses of an SP-12 exit variant (head, axis, roll, carrier key): in the duct mouth, at the extension / trunk landing on the axis,
    and pushed against the bore wall (what rescuers could do with a jammed litter)."""
    S = h3.CARRIERS['S']; out = {}; up = None
    if v['kind'] in ('fwd', 'oblique'):
        hm = np.array(P(duct_x_at(v, 0.80), 0.80)); up = np.array(P(v['duct']['xa'], v['duct']['ra']))-hm; up /= np.linalg.norm(up)
        out['stuck_in_duct_mouth'] = dict(car='S', head=hm, axis=up, roll=0.0, desc='carrier S jammed in the SP-12 duct, head at the duct mouth on the trunk wall (r 0.80), tail up the duct')
    if v['kind'] == 'fwd':
        out['stuck_on_axis_shunt_start'] = dict(car='S', head=np.array((v['shunt_from_x'], 0.0, 0.0)), axis=np.array((-1.0, 0.0, 0.0)), roll=0.0,
                                                desc=f"carrier S jammed on the bore axis at the shunt start (head X {v['shunt_from_x']:.2f}, the forward-most point of the SP-12 corridor)")
        xc = 0.5*(v['shunt_from_x']+v['duct']['xe'])
    else:
        xe = v['duct']['xe']
        out['stuck_on_axis_trunk_landing'] = dict(car='S', head=np.array((xe-1.0, 0.0, 0.0)), axis=np.array((1.0, 0.0, 0.0)), roll=0.0,
                                                  desc=f'carrier S jammed on the bore axis at the trunk landing (head X {xe-1.0:.2f}, tail forward)')
        xc = xe-0.4
    h, d, r = pushed_pose(h3.CARRIERS['A'], xc)
    out['litter_pushed_to_wall'] = dict(car='A', head=h, axis=d, roll=r, desc=f'rigid litter A jammed but pushed flat against the bore wall at az {PUSH_AZ_DEG:.0f}, centre X {xc:.2f}')
    return out


def walls_for(ctx, unions, diffs, sp12, sp13, fixtures13=None, rods=None):
    data2 = copy.deepcopy(ctx.data)
    if fixtures13 is not None:
        data2['sp13']['fixtures'] = fixtures13
    obj, tree = ex.build_free(ctx.s, data2, unions, diffs, ex.TRUNK_EXT_X, sp12=sp12, sp13=sp13, ref=True, fit=True)
    w = WallsPlus(ctx.fx, ctx.pts, free=tree, extra=rods) if rods else h3.Walls(ctx.fx, ctx.pts, free=tree)
    chk = [(p, h3.Walls.point(w, p)[0], inside_free(tree, p)) for p in ((106.0, 0.01, 0.01), (103.0, 0.3, 0.1), (101.0, -0.9, 0.5))]
    print('WF_O13B free-space sign check (normal sign, parity inside):', [(p, round(d, 3), ins) for p, d, ins in chk], flush=True)
    return obj, w


def one_sweep(walls, car, route, sdv, v=None, x_tail_end=None, staff=True):
    """One seed of one carrier: the route sweep, plus for a forward-leaning SP-12 duct the shunt aft (explicit poses, feet first, two rescuers) in
    three zones (extension, dock mouth, refuge port station) down to the tail at x_tail_end."""
    r = dict(h3.sweep_route(walls, car, route, np.random.default_rng(sdv), staff=staff))
    if v is not None and v['kind'] == 'fwd':
        Lc = h3.length(car); groups = {}
        for xx in np.arange(v['shunt_from_x'], x_tail_end+Lc-1e-9, -0.25):
            tail = xx-Lc; z = 'S_extension' if tail >= EXT_AFT_X else ('S_dock' if tail >= 98.0 else 'S_refuge_station')
            groups.setdefault(z, []).append(((xx, 0.0, 0.0), (-1.0, 0.0, 0.0), 0.0, f'shunt aft head x {xx:.2f}'))
        rng = np.random.default_rng(sdv+1000)
        for z, poses in groups.items():
            q = h3.sweep_poses(walls, car, poses, rng); r['by_zone'] = dict(r['by_zone'], **{z: dict(least_m=q['least_m'], status=q['status'], nearest=q['nearest'], at_m=q['at'])})
            if q['least_m'] < r['least_m']:
                r.update(least_m=q['least_m'], nearest=q['nearest'], zone=z, head=q['head'], axis=q['axis'], roll=q['roll'])
            if staff:
                st = ex.staff_at(walls, rng, poses, car)
                if st[0] < (r['staff_least_m'] if r['staff_least_m'] is not None else 9):
                    r.update(staff_least_m=st[0], staff_nearest=st[1])
    return r


def agg_sweeps(per, seeds):
    body = [r['least_m'] for r in per]; stf = [r['staff_least_m'] for r in per if r['staff_least_m'] is not None]; k = int(np.argmin(body)); least = min(body+stf)
    zones = {}
    for r in per:
        for z, q in r['by_zone'].items():
            if z not in zones or q['least_m'] < zones[z]['least_m']:
                zones[z] = q
    rk = min(per, key=lambda r: r['staff_least_m'] if r['staff_least_m'] is not None else 9)
    return dict(least_m=round(least, 3), body_least_m=round(min(body), 3), rescuers_least_m=round(min(stf), 3) if stf else None, status=status(least),
                seed_spread_m=[round(min(body+stf), 3), round(max(body+stf), 3)], seeds=list(seeds), body_by_seed=body, rescuers_by_seed=[r['staff_least_m'] for r in per],
                nearest=per[k]['nearest'] if (not stf or min(body) <= min(stf)) else rk['staff_nearest'], zone=per[k]['zone'], by_zone=zones,
                head=per[k]['head'], axis=per[k]['axis'], roll=per[k]['roll'])


def sweep_wc(walls, cars, route, label, v=None, x_tail_end=None, always6=False):
    """Worst case over seeds (RINGB-006): three seeds; if nothing FAILs (or always6) the three extra seeds are added (six in all). More seeds can only
    lower a minimum, so a three-seed FAIL is final."""
    raw = {}
    def run(seeds):
        for cid, car in cars.items():
            for sdv in seeds:
                raw.setdefault(cid, []).append(one_sweep(walls, car, route, sdv, v, x_tail_end, staff=(cid != 'U')))
            print('WF_O13B', label, cid, [r['least_m'] for r in raw[cid]], [r['staff_least_m'] for r in raw[cid]], flush=True)
    run(SEEDS); first = {c: round(min([r['least_m'] for r in p]+[r['staff_least_m'] for r in p if r['staff_least_m'] is not None]), 3) for c, p in raw.items()}
    seeds = SEEDS
    if always6 or min(first.values()) >= 0:
        run(SEEDS6[len(SEEDS):]); seeds = SEEDS6
    res = {c: agg_sweeps(p, seeds) for c, p in raw.items()}; lm = min(q['least_m'] for q in res.values())
    return dict(carriers=res, seeds=list(seeds), first_3_seeds=first, least_m=round(lm, 3), status=status(lm), limiting=min(res, key=lambda c: res[c]['least_m']))


def operator_fit_cap(walls, release, side, rng, n=800, cap=OP_CAP_B):
    """operator_fit with the search continued to `cap` (the A170 numbers were capped at 0.10 m)."""
    best = (-9.0, None, None); release = np.asarray(release, float)
    for _ in range(n):
        u = rng.normal(size=3); u /= np.linalg.norm(u); a = release+u*rng.uniform(OP_R_M, OP_REACH_M)
        w = rng.normal(size=3); w /= np.linalg.norm(w); b = a+w*rng.uniform(0.5, 0.95)
        if not side(a, b):
            continue
        m = walls.capsule(tuple(a), tuple(b), OP_R_M)
        if m[0] > best[0]:
            best = (min(m[0], cap), m[1], round(float(np.linalg.norm(a-release)), 3))
            if best[0] >= cap:
                break
    return best


def op_retest(walls, release, side, seeds=SEEDS6):
    rows = [operator_fit_cap(walls, release, side, np.random.default_rng(sdv)) for sdv in seeds]; vals = [r[0] if r[2] is not None else None for r in rows]
    ok = [x for x in vals if x is not None]; worst = min(ok) if len(ok) == len(vals) else None; k = int(np.argmin([x if x is not None else -9 for x in vals]))
    return dict(least_m=None if worst is None else round(worst, 3), status=status(worst), by_seed=[None if x is None else round(x, 3) for x in vals], seeds=list(seeds),
                reach_used_m=[r[2] for r in rows], nearest=rows[k][1], search_cap_m=OP_CAP_B,
                note='worst over seeds of the best-found operator placement (torso capsule r 0.25 m, shoulder within 0.70 m of the release, wholly on its side of the closure plane); None = no placement found')


def sp12_e2e_route(v):
    return ex.smooth(v['path'], cut=0.55) if v['kind'] != 'control' else v['path']


def path_profile(route, car):
    """Head and centre positions of a carrier along a route (0.05 m steps): under locked 1.5 g aft-down, X is height."""
    path = tuple(zip(*route)); cum = cs.cumulative(path[1]); L = h3.length(car); out = []
    for t in np.arange(L, cum[-1]+1e-9, 0.05):
        z, h = cs.at(path, cum, t); ts = cs.behind(path, cum, t, h, L); tl = cs.at(path, cum, ts)[1]
        out.append((str(z), np.array(h, float), 0.5*(np.array(h, float)+np.array(tl, float))))
    return out


def pt_seg(p, a, b):
    p, a, b = (np.asarray(q, float) for q in (p, a, b)); ab = b-a; t = min(max(float(np.dot(p-a, ab)/max(np.dot(ab, ab), 1e-12)), 0.0), 1.0)
    return float(np.linalg.norm(p-(a+ab*t)))


def inside_free(tree, p, dirn=(0.137, 0.981, 0.137)):
    """Point inside the closed free-space mesh by ray parity (diagnostic only: internal faces left by the booleans can spoil it)."""
    o = Vector(tuple(float(x) for x in p)); d = Vector(dirn).normalized(); n = 0
    for _ in range(400):
        loc, nrm, i, dist = tree.ray_cast(o, d)
        if loc is None:
            break
        n += 1; o = loc+d*1e-5
    return n % 2 == 1


def in_cyl(p, a, b, r):
    p, a, b = (np.asarray(q, float) for q in (p, a, b)); ab = b-a; t = float(np.dot(p-a, ab)/np.dot(ab, ab))
    return 0.0 <= t <= 1.0 and float(np.linalg.norm(p-(a+ab*t))) <= r


def union_inside_fn(ctx, v12, e13, fl13):
    """Analytic inside test of the b1 hoist free space (the union of its primitives less the SP-12 / SP-13 fit-out boxes): independent of the
    boolean mesh's face orientation. The parked SP-13 leaf and the SP-11 plug are not subtracted (the hoist lines do not reach them)."""
    tr = ctx.s['crew_transfer']['trunk_clear_radius_m']; q12 = ctx.data['sp12']; R12 = dict(x=tuple(q12['x_m']), az=tuple(q12['az_deg']), r=tuple(q12['r_m'])); s13 = s13_solid(e13)
    b12 = ex.fixture_boxes(q12); b13 = boxes_of(fixture_list(fl13)); d12 = v12['solid']
    def f(p):
        p = np.asarray(p, float); r = math.hypot(p[1], p[2])
        ins = (87.0 <= p[0] <= ex.TRUNK_EXT_X and r <= tr) or in_cyl(p, d12['a'], d12['b'], d12['r']) or in_cyl(p, s13[0], s13[1], s13[2]) \
            or bool(in_room(p[None, :], R12)[0]) or bool(in_room(p[None, :], ROOM13)[0]) or in_cyl(p, P(ex.XC, 2.50), P(ex.XC, 6.15), 1.05)
        return ins and not any(float(obb_dist(p[None, :], b)[0]) < 0 for b in b12+b13)
    return f


def signed_pt(walls, p, inside_fn):
    """walls.point with the free-space sign from an analytic inside test (a thin hoist line, not a carrier pose)."""
    p = tuple(float(x) for x in p); best = walls.cl.point(p, 0.0) if walls.cl else (math.inf, None)
    if getattr(walls, 'extra', None) is not None:
        loc, n, _, dist = walls.extra[0].find_nearest(Vector(p))
        if loc is not None and dist < best[0]:
            best = (dist, walls.extra[1])
    loc, n, _, dist = walls.free.find_nearest(Vector(p))
    if loc is not None:
        dd = dist if inside_fn(p) else -dist
        if dd < best[0]:
            best = (dd, 'FREE_SPACE_WALL')
    return best


def line_metrics(walls, a, b, s13, r13_pts, rods, inside_fn, step=0.05):
    """A hoist line (thin rope) from a to b: least distance to the free-space walls / built fixtures / ladder extension (negative = the straight line
    leaves the free space: it needs a deflector there), to the SP-13 exit solid surface and to the SP-13 carrier S envelope."""
    a = np.asarray(a, float); b = np.asarray(b, float); n = max(2, int(np.linalg.norm(b-a)/step)); pts = [a+(b-a)*k/n for k in range(n+1)]
    w = min((signed_pt(walls, p, inside_fn)+(tuple(float(x) for x in np.round(p, 2)),) for p in pts), key=lambda q: q[0])
    d13 = min(pt_seg(p, s13[0], s13[1]) for p in pts)-s13[2]
    dr = min(min(pt_seg(q, a, b) for q in r13_pts)-h3.CARRIERS['S']['radius'], 9.0) if len(r13_pts) else None
    dl = min([math.hypot(p[1]-rho*math.cos(ang), p[2]-rho*math.sin(ang))-rr for p in pts if p[0] <= LADDER_TOP_X for rho, ang, rr in rods.values()] or [9.0])
    return dict(to_walls_m=round(w[0], 3), walls_nearest=w[1], at=list(w[2]), to_sp13_exit_solid_m=round(d13, 3), to_sp13_S_envelope_m=None if dr is None else round(dr, 3), to_ladder_lines_m=round(dl, 3))


def sp13_parts(S13):
    e = S13['exit']; fl = S13['resited_layouts']['aft']['fixture_list']; return e, fl, ('aft', 0.02)


def s13_solid(e):
    t = math.tan(math.radians(e['beta'])); a = math.radians(e['az'])
    return (np.array(P(e['xp']-(1.25-0.40)*t, 0.40, az=a)), np.array(P(e['xp']+0.35*t, 1.60, az=a)), e['D']/2)


def sp13_duct_wall_edges(ctx, e):
    s = ctx.s; tr = s['crew_transfer']['trunk_clear_radius_m']; w = s['crew_transfer']['passage_wall_m']; b = math.radians(e['beta']); D = e['D']
    c = e['xp']-(1.25-(tr+w))*math.tan(b); return round(c-(D/2)/math.cos(b), 3), round(c+(D/2)/math.cos(b), 3)


def route13_long(e, x_end=97.0):
    r, xe = route_for(e); return r+[('T', (x_end, 0.0, 0.0))], xe


# ---------------------------------------------------------------------------------------------------------------------------------
# b1 (A176)

def run_o13b_b1(ctx, out, S13):
    s = ctx.s; jf = out/'o13b_b1.json'; res = json.loads(jf.read_text()) if jf.exists() else {}
    v = sp12_variant(*N2F); route = sp12_e2e_route(v); xr = refuge_x(s); rods, nr = ladder_extension_rods(s); G = ladder_geom(s, 285.0)
    e13, fl13, leaf = sp13_parts(S13); s13 = s13_solid(e13); r13, xe13 = route_for(e13); r13_pts = [np.array(p) for _, p in r13]
    cars = dict(S=h3.CARRIERS['S'], A=h3.CARRIERS['A'], K=h3.CARRIERS['K'])
    res['variant'] = dict(name=N2F[0], desc=v['desc'], status='NEXT REVERSIBLE comparison only (15!A176); not installed, no canonical pressure-shell edit; 1.66 m spine-core cutout HOLD',
                          refuge_port_x=round(xr, 3), ladder_extension_rungs=nr)
    obj, walls = walls_for(ctx, v['unions'], [], sp12=True, sp13=False, rods=rods)
    # 1. complete litter route, end to end, six seeds
    if 'e2e' not in res:
        res['e2e'] = sweep_wc(walls, cars, route, 'B1_E2E', v=v, x_tail_end=xr, always6=True)
        res['e2e']['route'] = (f"SP-11 chamber (X {ex.XC:.2f}, r 5.8) -> SP-12 floor (H) -> 45 deg forward duct (D) -> L1-A extension to head X {v['shunt_from_x']:.2f} (E) -> shunt aft feet first through "
                               f"the extension, past the Dock_Primary mouth (X 99.4) and the bridged ladder, to the tail at the Crew_Refuge_Port station (X {xr:.2f}); the turn into the refuge is HUM-003's (not re-run)")
        res['e2e']['obstacles'] = 'SP-12 fit-out, parked SP-11 plug, built trunk fixtures (HUM-003 records), L1-A ladder extension (stiles, rungs, arrest rail to X 104.9)'
        jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
    # 2. opposite-side operation retest (six seeds, search to 0.30 m)
    O = np.array(P(v['floor_x'], 1.25)); Rn = np.array(axes_at()[2])
    if 'opposite_side' not in res:
        res['opposite_side'] = dict(sp12_side=op_retest(walls, P(v['floor_x'], 1.35), plane_side(O, Rn, lo=0.0)), trunk_side=op_retest(walls, v['below_pt'], plane_side(O, Rn, hi=0.0)),
                                    a170_reported_m=0.100, closure_model='existing study model (sliding plug leaf, eva3_exits.closure_data); release at the closure centre')
        print('WF_O13B opposite', {k: q['least_m'] for k, q in res['opposite_side'].items() if isinstance(q, dict)}, flush=True)
        jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
    bpy.data.objects.remove(obj)
    # 3. single faults with geometry: an incapacitated rescuer (tucked body) in the duct / in the extension; the carrier jammed in the duct mouth vs
    #    the trunk-side release (can the closure still be worked from below?)
    sf = res.setdefault('single_fault', {})
    up = np.array(P(v['duct']['xa'], v['duct']['ra']))-np.array(P(duct_x_at(v, 0.80), 0.80)); up /= np.linalg.norm(up)
    body_cases = {'rescuer_down_in_duct': (np.array(P(duct_x_at(v, 1.10), 1.10))-up*BODY['length']/2, up, 0.0, 'incapacitated rescuer (capsule r 0.25 m, 1.25 m) lying along the SP-12 duct axis at r 1.10'),
                  'rescuer_down_in_extension': (*pushed_pose(BODY, 104.0), f'incapacitated rescuer pushed against the extension wall at az {PUSH_AZ_DEG:.0f}, centre X 104.0')}
    for k, (h, d, r, desc) in body_cases.items():
        if k in sf:
            continue
        obj, w2 = walls_for(ctx, v['unions'], [body_solid(BODY, h, d, r)], sp12=True, sp13=False, rods=rods)
        sf[k] = dict(desc=desc, sweep=sweep_wc(w2, dict(S=h3.CARRIERS['S'], A=h3.CARRIERS['A']), route, 'B1_SF_'+k, v=v, x_tail_end=xr))
        bpy.data.objects.remove(obj); jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
    if 'carrier_jammed_in_duct_vs_release' not in sf:
        q = obstacle_poses(v)['stuck_in_duct_mouth']
        obj, w2 = walls_for(ctx, v['unions'], [body_solid(h3.CARRIERS[q['car']], q['head'], q['axis'], q['roll'])], sp12=True, sp13=False, rods=rods)
        sf['carrier_jammed_in_duct_vs_release'] = dict(desc=q['desc'], sp12_side=op_retest(w2, P(v['floor_x'], 1.35), plane_side(O, Rn, lo=0.0)),
                                                       trunk_side=op_retest(w2, v['below_pt'], plane_side(O, Rn, hi=0.0)))
        bpy.data.objects.remove(obj); jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
    sf['logic'] = {
        'SP-11 inner plug jammed shut': 'the casualty cannot leave the SP-11 chamber into SP-12; the only other way is the outer hatch (EVA side); no geometry measured',
        'SP-12 exit closure jammed shut': 'the SP-12 route is blocked; the fallback through the SP-12/SP-13 door to the SP-13 exit is not modelled (no door geometry in the study data): OPEN',
        'SP-12 exit closure jammed open': 'SP-12 can no longer be isolated from the L1-A extension (shared with SP-13): see b2 pressure isolation',
        'one dog / latch lost': 'capacity of the remaining dogs OPEN (no rating)',
        'one rescuer incapacitated': 'the carrier geometry with one rescuer is a subset of the two-rescuer sweep (clearance >= the e2e value); whether one rescuer can move the casualty (effort, 1.5 g lift) is OPEN; the body left in the corridor is measured as an obstacle above'}
    # 4. hoist interfaces under locked 1.5 g (aft is down, +X is up): the lift, the anchor station and the line sweep
    if 'hoist' not in res:
        obj, wc = walls_for(ctx, v['unions']+[exit_solid(e13)], list(leaf_solids(e13, *leaf, PARK_DEG)), sp12=True, sp13=True, fixtures13=fl13, rods=rods)
        prof = path_profile(route, h3.CARRIERS['S']); hx = max(p[1][0] for p in prof); cxs = [p[2][0] for p in prof]; ins = union_inside_fn(ctx, v, e13, fl13)
        i_h = next(i for i, p in enumerate(prof) if p[0] in ('H', 'D')); lift_c = round(max(cxs)-min(cxs[i_h:]), 3)
        anchors = {'axis': (hx+h3.HOIST_HEAD_M, 0.0), 'offset_0.25_at_105deg (HUM-003 hoist line)': (hx+h3.HOIST_HEAD_M, 0.25), 'extension_forward_end': (ex.TRUNK_EXT_X-h3.HOIST_HEAD_M, 0.0)}
        rows = {}
        for an, (ax_, off) in anchors.items():
            A_ = np.array(ct.radial(ax_, off, math.radians(105.0))) if off else np.array((ax_, 0.0, 0.0))
            lift = {}
            for zn in ('H', 'D', 'E'):
                hs = [p[1] for p in prof if p[0] == zn]
                if not hs:
                    continue
                ms = [line_metrics(wc, A_, h_, s13, r13_pts, G['lines'], ins) for h_ in hs[::4]]; worst = min(ms, key=lambda m: m['to_walls_m'])
                lift[zn] = {k: min(m[k] for m in ms) for k in ('to_walls_m', 'to_sp13_exit_solid_m', 'to_sp13_S_envelope_m', 'to_ladder_lines_m')}
                lift[zn].update(walls_nearest=worst['walls_nearest'], at=worst['at'])
            lower = line_metrics(wc, A_, np.array((xr+h3.CARRIERS['S']['length'], 0.0, 0.0)) if not off else np.array(ct.radial(xr+h3.CARRIERS['S']['length'], off, math.radians(105.0))), s13, r13_pts, G['lines'], ins)
            rows[an] = dict(anchor=[round(float(q), 3) for q in A_], anchor_to_sp13_exit_solid_m=round(pt_seg(A_, s13[0], s13[1])-s13[2], 3),
                            anchor_to_extension_forward_end_m=round(ex.TRUNK_EXT_X-float(A_[0]), 3), line_while_lifting=lift, line_while_lowering_aft=lower)
        e0, e1 = sp13_duct_wall_edges(ctx, e13)
        res['hoist'] = dict(head_max_x=round(hx, 3), centre_lift_m=lift_c, duct_rise_m=round(v['duct']['xe']-v['duct']['xa'], 3),
                            lift_note=f'locked 1.5 g aft-down: the casualty centre rises {lift_c:.2f} m from the SP-12 floor turn (zone H) to the shunt start; the duct alone rises {v["duct"]["xe"]-v["duct"]["xa"]:.2f} m (the A170 "about 1.1 m")',
                            sp13_duct_on_trunk_wall_x=[e0, e1], anchors=rows, swept_volume=dict(x=[round(min(p[1][0] for p in prof), 2), round(hx, 2)], note='carrier S head positions from the SP-12 floor to the shunt start; the carrier capsule r 0.43 m and the rescuers add to this'),
                            loads='OPEN: anchor, line, sheave and deflector loads, winch rating and the 1.5 g handling effort are not assumed', status='GEOMETRY ONLY; loads OPEN')
        bpy.data.objects.remove(obj); jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
    return res


# ---------------------------------------------------------------------------------------------------------------------------------
# b2 (A177)

def corridor_points(v, car, x_tail_end=None):
    """Axis points of the SP-12 corridor occupied by the carrier S (route + shunt to the extension's aft end): the swept volume is these points
    grown by the capsule radius, plus a rescuer (0.25 m) within 0.70 m beyond each end."""
    route = sp12_e2e_route(v); pts = [np.array(p) for _, p in route]
    if v['kind'] == 'fwd':
        pts += [np.array((x, 0.0, 0.0)) for x in np.arange(v['shunt_from_x'], (x_tail_end or EXT_AFT_X), -0.1)]
    dense = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(np.linalg.norm(b-a)/0.05)); dense += [a+(b-a)*k/n for k in range(1, n+1)]
    return np.array(dense)


def run_o13b_b2(ctx, out, S13):
    s = ctx.s; jf = out/'o13b_b2.json'; res = json.loads(jf.read_text()) if jf.exists() else {}
    e13, fl13, leaf = sp13_parts(S13); s13 = s13_solid(e13); r13l, xe13 = route13_long(e13); e0, e1 = sp13_duct_wall_edges(ctx, e13)
    R13 = np.array([p for _, p in route_for(e13)[0]]); rS = h3.CARRIERS['S']['radius']; rods, _ = ladder_extension_rods(s)
    leaf_d = list(leaf_solids(e13, *leaf, PARK_DEG)); cars13 = dict(U=carriers(ctx)['U'], S=h3.CARRIERS['S'])
    res['sp13_exit'] = dict(exit=e13, closure='(a) aft hinge, 0.02 m offset, re-sited fit-out (the A170 preferred candidate, parked open)', duct_on_trunk_wall_x=[e0, e1], landing_x=round(xe13, 2),
                            route='SP-13 -> 45 deg duct -> landing on the axis -> aft along the extension and the built trunk to X 97.0')
    # baseline: the SP-13 route to X 97 with the SP-12 N2 fwd45 duct present and no fault (the reference for every fault row)
    v45 = sp12_variant(*N2F)
    def sweep13(key, v12, diffs, label, always6=False):
        if key in res.get('sweeps13', {}):
            return
        unions = [exit_solid(e13)]+(list(v12['unions']) if v12 else [])
        obj, w = walls_for(ctx, unions, leaf_d+list(diffs), sp12=v12 is not None, sp13=True, fixtures13=fl13, rods=rods)
        res.setdefault('sweeps13', {})[key] = sweep_wc(w, cars13, r13l, label, always6=always6); bpy.data.objects.remove(obj)
        jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
    sweep13('no_fault_N2_fwd45', v45, [], 'B2_NOFAULT', always6=True)
    # SP-12 swept corridors and their gaps to the SP-13 exit (static)
    def envelope(v):
        pts = corridor_points(v, h3.CARRIERS['S']); inb = pts[np.hypot(pts[:, 1], pts[:, 2]) < 0.80]
        fwd = float(inb[:, 0].max()) if len(inb) else None
        g_solid = min(pt_seg(p, s13[0], s13[1]) for p in pts[::2])-rS-s13[2]
        g_route = min(float(np.min(np.linalg.norm(R13-p, axis=1))) for p in pts[::2])-2*rS
        lands = v['duct']['xe'] if v['kind'] != 'control' else 101.85
        xf = (fwd+rS+h3.STAFF_REACH_M+h3.STAFF_R_M) if fwd else None
        return dict(corridor_x_in_bore=[round(float(inb[:, 0].min()), 2), round(fwd, 2)] if fwd else None, carrier_forward_end_x=None if fwd is None else round(fwd+rS, 2),
                    with_rescuer_forward_end_x=None if xf is None else round(xf, 2), lands_x=round(lands, 2),
                    gap_to_sp13_exit_solid_m=round(g_solid, 3), gap_to_sp13_route_R_to_landing_m=round(g_route, 3),
                    transverse_isolation_window_m=None if xf is None else round(e0-xf, 3),
                    note='S capsule envelope (r 0.43 m) along the SP-12 route and shunt; the transverse isolation window is the free X between the SP-12 corridor (with a rescuer ahead) and the aft edge of the SP-13 duct on the trunk wall; any transverse closure in the extension also crosses both stiles and the arrest rail of the L1-A ladder (r 0.64 m)')
    res['envelopes'] = {N2F[0]: envelope(v45)}
    # the simultaneous-use case and the failure tree: SP-13 swept with each SP-12 fault left in the bore as an obstacle
    for k, q in obstacle_poses(v45).items():
        sweep13(f'N2_fwd45_{k}', v45, [body_solid(h3.CARRIERS[q['car']], q['head'], q['axis'], q['roll'])], f'B2_{k}')
        res['sweeps13'][f'N2_fwd45_{k}']['desc'] = q['desc']
    # the trunk-side (outer) access to the SP-13 leaf with the SP-12 carrier at its forward-most point (simultaneous use)
    if 'outer_leaf_access' not in res:
        q = obstacle_poses(v45)['stuck_on_axis_shunt_start']; O, X, T, R = frame13(e13)
        obj, w = walls_for(ctx, [exit_solid(e13)]+list(v45['unions']), leaf_d+[body_solid(h3.CARRIERS['S'], q['head'], q['axis'], q['roll'])], sp12=True, sp13=True, fixtures13=fl13)
        rel = O-R*WHEEL_PROUD_M; cp = corridor_points(v45, h3.CARRIERS['S']); dmin = float(np.min(np.linalg.norm(cp-rel, axis=1)))-rS
        res['outer_leaf_access'] = dict(with_sp12_S_at_shunt_start=op_retest(w, rel, plane_side(O, R, hi=-WHEEL_PROUD_M)), release_to_sp12_corridor_surface_m=round(dmin, 3),
                                        reach_zone_m=OP_REACH_M+OP_R_M, corridor_inside_reach_zone=bool(dmin < OP_REACH_M+OP_R_M))
        bpy.data.objects.remove(obj); jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
    # alternates: SP-12 corridors that move away from the SP-13 landing (six seeds for the SP-12 carriers and for the SP-13 bypass)
    alts = res.setdefault('alternates', {})
    for name, kind, D, psi in ALT_SP12:
        a = alts.setdefault(name, {})
        v = sp12_variant(name, kind, D, psi); route = sp12_e2e_route(v)
        if 'sp12_sweep' not in a:
            obj, w = walls_for(ctx, v['unions'], [], sp12=True, sp13=False)
            a['sp12_sweep'] = sweep_wc(w, dict(S=h3.CARRIERS['S'], A=h3.CARRIERS['A'], K=h3.CARRIERS['K']), route, 'B2_ALT_'+name, v=v, x_tail_end=97.0-0.0, always6=True)
            bpy.data.objects.remove(obj)
            ex.PSI = math.radians(psi if kind == 'oblique' else 15.0)
            a['vehicle'] = ex.vehicle_screen(s, ctx.obs, dict(kind='oblique', D=D, area=v['area'], duct=v['duct'])); a['spine_core_cut_x_m'] = duct_spine_cut(s, v); ex.PSI = math.radians(15.0)
            a['desc'] = v['desc']; jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
        a['envelope'] = envelope(v)
        for k, q in obstacle_poses(v).items():
            if k == 'stuck_in_duct_mouth':
                continue
            sweep13(f'{name}_{k}', v, [body_solid(h3.CARRIERS[q['car']], q['head'], q['axis'], q['roll'])], f'B2_ALT_{name}_{k}', always6=True)
            res['sweeps13'][f'{name}_{k}']['desc'] = q['desc']
    res['isolation'] = dict(
        barriers_between_sp12_and_sp13=['SP-12/SP-13 partition and door (seats from SP-12; reverse load OPEN)', 'SP-12 exit closure (sliding plug model; seats OPEN)', 'SP-13 exit closure (a) single hinged dogged leaf (one barrier, not single-fault tolerant)',
                                        'SP-11 inner plug (SP-12 side only)'],
        shared_volume='the L1-A extension X 102.45-107.4 and the built trunk: no transverse closure between the SP-12 landing and the SP-13 landing in any layout studied',
        transverse_closure_note=f'a transverse closure needs a free X window between the two corridors; it would also cut both stiles and the arrest rail of the L1-A ladder (a new ladder break, excluded by 15!A171) and the trunk is the only way aft to the refuge for both',
        status='OPEN: no isolation valve, equalization, relief or rating assumed')
    jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
    return res


# ---------------------------------------------------------------------------------------------------------------------------------
# c1 (A178)

def room_limits(pts):
    """Margin (m) of points to each SP-13 room bound separately (negative = outside): which wall limits a leaf envelope."""
    room = ROOM13; p = np.asarray(pts, float); r = np.hypot(p[:, 1], p[:, 2]); az = np.arctan2(p[:, 2], p[:, 1])
    return dict(aft_wall_partition=round(float(np.min(p[:, 0]-room['x'][0])), 3), forward_wall=round(float(np.min(room['x'][1]-p[:, 0])), 3),
                side_wall_az_lo=round(float(np.min(r*(az-math.radians(room['az'][0])))), 3), side_wall_az_hi=round(float(np.min(r*(math.radians(room['az'][1])-az))), 3),
                ceiling=round(float(np.min(room['r'][1]-r)), 3))


def mount_exit(e, dM, dT):
    """The exit (aperture, duct and leaf mount together) moved dM forward along X and dT sideways toward the room's centre azimuth (tangential, at r 1.25)."""
    c = 0.5*sum(ROOM13['az']); sg = -1.0 if e['az'] > c else 1.0
    return dict(e, xp=round(e['xp']+dM, 3), az=round(e['az']+sg*math.degrees(dT/1.25), 2))


def side_wall_screen(ctx, dW, x0, x1):
    """The SP-13 side wall at the room's upper azimuth moved outward by dW (tangential at the floor radius r 1.25): the added wedge slab against
    the saved vehicle at the mechanical clearance, minus what the same slab just inside the present wall already meets (pre-existing)."""
    if dW <= 0:
        return dict(new_hits=[], status='CLEAR')
    clr = ctx.s['prototype']['mechanical_clearance_m']; a1 = math.radians(ctx.data['sp13']['az_deg'][1]); da = dW/1.25; ig = ('Structural_Spine', 'Crew_Trunk', 'Trunk_Fit_', 'Crew_Trunk_')
    def slab(phi):
        hits = set(); inside = True
        for rr in np.arange(1.25, 4.60, 0.25):
            b = sv.box(x0, x1, phi, rr, min(rr+0.25, 4.60), (rr+0.25)*da/2+0.005, clr); hits |= ctx.obs.hits(b, ignore=ig); inside &= sv.inside_hull(ctx.s, b)
        return hits, inside
    new, ins = slab(a1+da/2); ref, _ = slab(a1-da/2)
    return dict(new_hits=sorted(new-ref), preexisting_hits=sorted(ref), inside_hull=bool(ins), status='CLEAR' if not (new-ref) and ins else 'BLOCKED',
                az_hi_deg=round(math.degrees(a1+da), 2), note='slab X of the room, r 1.25-4.60, grown by the 0.15 m mechanical clearance; the room wall itself is a PROTOTYPE boundary')


def sp12_fwd_margin(ctx, dP):
    fw = ctx.data['sp12']['x_m'][1]-dP; ends = [(fi['x']+fi['size'][0]/2, fi['id']) for fi in ctx.data['sp12']['fixtures']]; x, n = max(ends)
    return round(fw-x, 3), n


def nudge_fitout(fl, e, o_h, asb0):
    """The smallest move of the one fixture the leaf envelope (closed to parked, 5 deg steps) comes within 0.07 m of: azimuth +-2.5..7.5 deg and/or
    X +-0.1..0.2 m, the other fixtures kept; the layout hard constraints (no overlap, aperture not stood on, overflow no worse than as built) hold."""
    loc = leaf_local_points(e); keep = np.vstack([leaf_transform(e, 'aft', o_h, th)(loc) for th in np.arange(0.0, PARK_DEG+1e-9, 5.0)])
    nz = fixture_list(fl); best = None
    for i, f in enumerate(nz):
        if float(obb_dist(keep, boxes_of([f])[0]).min()) >= MARGIN+0.02:
            continue
        for daz in (-2.5, 2.5, -5.0, 5.0, -7.5, 7.5, 0.0):
            for dx in (0.0, -0.1, 0.1, -0.2, 0.2):
                f2 = dict(f, az=round(f['az']+daz, 1), x=round(f['x']+dx, 3)); fl2 = [f2 if j == i else g for j, g in enumerate(nz)]
                if any(float(obb_dist(keep, bb).min()) < MARGIN+0.02 for bb in boxes_of(fl2)):
                    continue
                lm = layout_metrics(fl2, e, asb0)
                if lm is None:
                    continue
                cost = math.radians(abs(daz))*3.0+abs(dx)
                if best is None or cost < best[0]:
                    best = (cost, fl2, dict(fixture=f['id'], d_az_deg=daz, d_x_m=dx, lane_clear_m=lm['lane_clear_m'], service=lm['service']))
    return (best[1], best[2]) if best else (None, None)


def resite_for(ctx, e, edge, o_h, n_search=250):
    loc = leaf_local_points(e); keep = np.vstack([leaf_transform(e, edge, o_h, th)(loc) for th in np.arange(0.0, PARK_DEG+1e-9, 5.0)])
    base, wrapped = keepout_placements_filter(keep, MARGIN+0.02); globals()['placements'] = wrapped
    try:
        nz = fixture_list([dict(f) for f in ctx.data['sp13']['fixtures']]); ids = [f['id'] for f in nz]
        asb = {i: overflow_m(b) for i, b in zip(ids, boxes_of(nz))}; fnd = search_layouts(nz, e, asb, n_search, np.random.default_rng(2710))
    finally:
        globals()['placements'] = base
    return (fnd[0][2], fixture_table(ctx, fnd[0][2], asb, e)) if fnd else (None, None)


def run_o13b_c1(ctx, out, S13):
    global ROOM13
    s = ctx.s; jf = out/'o13b_c1.json'; res = json.loads(jf.read_text()) if jf.exists() else {}
    e13, fl13, _ = sp13_parts(S13); x0, x1 = ctx.data['sp13']['x_m']; room0 = dict(ROOM13); v45 = sp12_variant(*N2F)
    asb = {f['id']: overflow_m(b) for f, b in zip(fixture_list(fl13), boxes_of(fixture_list(fl13)))}
    az0 = list(ctx.data['sp13']['az_deg'])
    def set_room(dP, dW=0.0):
        global ROOM13
        ah = round(az0[1]+math.degrees(dW/1.25), 2)
        ctx.data['sp13']['x_m'] = [round(x0-dP, 3), x1]; ctx.data['sp13']['az_deg'] = [az0[0], ah]; ROOM13 = dict(room0, x=(round(x0-dP, 3), x1), az=(az0[0], ah))
    try:
        if 'grid' not in res:
            grid = []
            loc = leaf_local_points(e13); ovl = {k: max(v, overflow_m(b)) for (k, v), b in zip(asb.items(), boxes_of(fixture_list(fl13)))}
            for dP in SHIFT_STEPS_M:
                set_room(dP); m12, n12 = sp12_fwd_margin(ctx, dP)
                for dM in SHIFT_STEPS_M:
                    for dT in SHIFT_STEPS_M:
                        e2 = mount_exit(e13, dM, dT); lm = layout_metrics(fl13, e2, ovl)
                        for o_h in HINGE_OFFSETS_B:
                            g = leaf_geometry(ctx, fl13, e2, 'aft', o_h)
                            swp = np.vstack([leaf_transform(e2, 'aft', o_h, th)(loc) for th in np.arange(5.0, PARK_DEG+1e-9, 5.0)]); lim = room_limits(swp)
                            grid.append(dict(dP=dP, dM=dM, dT=dT, hinge_offset_m=o_h, exit_xp=e2['xp'], exit_az=e2['az'], exit_valid=exit_valid(e2), lane_ok=lm is not None, lane_clear_m=lm['lane_clear_m'] if lm else None,
                                             park_room_m=g['park']['to_room_m'], park_fitout_m=g['park']['to_fitout_m'], swing_room_m=g['swing']['to_room_m'], swing_fitout_m=g['swing']['to_fitout_m'],
                                             swing_by_bound=lim, swing_limiting_bound=min(lim, key=lim.get), leaf_room_least_m=min(g['park']['to_room_m'], g['swing']['to_room_m']),
                                             leaf_least_m=min(g['park_least_m'], g['swing_least_m']), leaf_status=g['status'], sp12_fixture_margin_m=m12, sp12_limiting_fixture=n12,
                                             sp13_aft_wall_x=round(x0-dP, 3), sp12_forward_wall_x=round(ctx.data['sp12']['x_m'][1]-dP, 3)))
            res['grid'] = grid; jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
        if 'grid_side_wall' not in res:
            # the room's upper-azimuth side wall (the swing limit of the A170 leaf) moved outward by dW, with the partition / X mount moves; dT = 0
            loc = leaf_local_points(e13); ovl = {k: max(v, overflow_m(b)) for (k, v), b in zip(asb.items(), boxes_of(fixture_list(fl13)))}; grid = []; scr = {}
            for dW in SHIFT_STEPS_M:
                scr[dW] = side_wall_screen(ctx, dW, x0-max(SHIFT_STEPS_M), x1)
                for dP in SHIFT_STEPS_M:
                    set_room(dP, dW); m12, n12 = sp12_fwd_margin(ctx, dP)
                    for dM in SHIFT_STEPS_M:
                        e2 = mount_exit(e13, dM, 0.0); lm = layout_metrics(fl13, e2, ovl)
                        for o_h in HINGE_OFFSETS_B:
                            g = leaf_geometry(ctx, fl13, e2, 'aft', o_h)
                            swp = np.vstack([leaf_transform(e2, 'aft', o_h, th)(loc) for th in np.arange(5.0, PARK_DEG+1e-9, 5.0)]); lim = room_limits(swp)
                            grid.append(dict(dP=dP, dM=dM, dT=0.0, dW=dW, side_wall_az_hi_deg=ROOM13['az'][1], side_wall_screen=scr[dW]['status'], hinge_offset_m=o_h, exit_xp=e2['xp'], exit_az=e2['az'],
                                             exit_valid=exit_valid(e2), lane_ok=lm is not None, lane_clear_m=lm['lane_clear_m'] if lm else None,
                                             park_room_m=g['park']['to_room_m'], park_fitout_m=g['park']['to_fitout_m'], swing_room_m=g['swing']['to_room_m'], swing_fitout_m=g['swing']['to_fitout_m'],
                                             swing_by_bound=lim, swing_limiting_bound=min(lim, key=lim.get), leaf_room_least_m=min(g['park']['to_room_m'], g['swing']['to_room_m']),
                                             leaf_least_m=min(g['park_least_m'], g['swing_least_m']), leaf_status=g['status'], sp12_fixture_margin_m=m12, sp12_limiting_fixture=n12,
                                             sp13_aft_wall_x=round(x0-dP, 3), sp12_forward_wall_x=round(ctx.data['sp12']['x_m'][1]-dP, 3)))
            set_room(0.0, 0.0); res['grid_side_wall'] = grid; res['side_wall_screen'] = {str(k): v for k, v in scr.items()}; jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
        for g in res['grid']:
            g.setdefault('dW', 0.0)
        rows = res['grid']+res['grid_side_wall']
        # the room walls cannot be helped by re-siting the fit-out; the fit-out can (searched again below when the leaf comes within 0.05 m of it)
        ok = [g for g in rows if g['leaf_room_least_m'] >= MARGIN and g['exit_valid'] and g['lane_ok'] and g['sp12_fixture_margin_m'] >= 0 and g.get('side_wall_screen', 'CLEAR') == 'CLEAR']
        pick = {}; fam = {}
        for lab, f in (('partition_only', lambda g: g['dM'] == 0 and g['dT'] == 0 and g['dW'] == 0), ('mount_x_only', lambda g: g['dP'] == 0 and g['dT'] == 0 and g['dW'] == 0),
                       ('mount_sideways_only', lambda g: g['dP'] == 0 and g['dM'] == 0 and g['dW'] == 0), ('side_wall_only', lambda g: g['dP'] == 0 and g['dM'] == 0 and g['dT'] == 0),
                       ('partition_and_sideways', lambda g: g['dM'] == 0 and g['dW'] == 0 and g['dP'] > 0 and g['dT'] > 0), ('mount_x_and_sideways', lambda g: g['dP'] == 0 and g['dW'] == 0 and g['dM'] > 0 and g['dT'] > 0),
                       ('partition_and_side_wall', lambda g: g['dM'] == 0 and g['dT'] == 0 and g['dP'] > 0 and g['dW'] > 0), ('mount_x_and_side_wall', lambda g: g['dP'] == 0 and g['dT'] == 0 and g['dM'] > 0 and g['dW'] > 0)):
            allf = [g for g in rows if f(g) and g['exit_valid'] and g['lane_ok'] and g['sp12_fixture_margin_m'] >= 0]
            b = max(allf, key=lambda g: g['leaf_room_least_m']); fam[lab] = {k: b[k] for k in ('dP', 'dM', 'dT', 'dW', 'hinge_offset_m', 'exit_az', 'park_room_m', 'swing_room_m', 'swing_limiting_bound', 'leaf_room_least_m')}
            c = sorted([g for g in ok if f(g)], key=lambda g: (round(g['dP']+g['dM']+g['dT']+g['dW'], 3), g['hinge_offset_m'], -g['leaf_least_m']))
            if c:
                pick[lab] = c[0]
        res['candidates'] = pick; res['family_best_leaf_room'] = fam
        asb0 = {f['id']: overflow_m(b) for f, b in zip(fixture_list(ctx.data['sp13']['fixtures']), boxes_of(fixture_list(ctx.data['sp13']['fixtures'])))}
        sw = res.setdefault('sweeps', {})
        for lab, g in pick.items():
            if lab in sw:
                continue
            t0 = time.time(); set_room(g['dP'], g['dW']); e2 = dict(e13, xp=g['exit_xp'], az=g['exit_az']); fl = fl13; resited = None
            nudge = None
            if g['park_fitout_m'] < MARGIN or g['swing_fitout_m'] < MARGIN:
                fl, nudge = nudge_fitout(fl13, e2, g['hinge_offset_m'], asb0)
                if fl is None:
                    fl, resited = resite_for(ctx, e2, 'aft', g['hinge_offset_m'])
                if fl is None:
                    sw[lab] = dict(candidate=g, error='no fit-out arrangement keeps 0.07 m off the leaf envelope'); continue
            diffs = leaf_solids(e2, 'aft', g['hinge_offset_m'], PARK_DEG)
            r6, obj = eval_exit(ctx, fl, e2, f'O13B_C1_{lab}', seeds=SEEDS6, keep=True, diffs=diffs)
            walls = h3.Walls(ctx.fx, ctx.pts, free=h3_tree(obj)); O, X, T, R = frame13(e2)
            ops = dict(sp13_side=op_retest(walls, O+R*(LEAF_T_M+WHEEL_PROUD_M), plane_side(O, R, lo=LEAF_T_M+WHEEL_PROUD_M)),
                       trunk_side=op_retest(walls, O-R*WHEEL_PROUD_M, plane_side(O, R, hi=-WHEEL_PROUD_M)))
            try:
                nm = render_sp13(ctx, obj, fl, e2, r6, f'a178_sp13_{lab}', out, extra=leaf_solids(e2, 'aft', g['hinge_offset_m'], PARK_DEG, name='LEAFR')); rnd = str((out/nm).relative_to(ROOT))
            except Exception as exc:
                rnd = f'render failed: {exc}'
            bpy.data.objects.remove(obj)
            # outer (trunk-side) leaf access with the SP-12 N2 fwd45 carrier S at its forward-most point (the SP-12 corridor in the extension)
            q = obstacle_poses(v45)['stuck_on_axis_shunt_start']
            obj, w2 = walls_for(ctx, [exit_solid(e2)]+list(v45['unions']), list(diffs)+[body_solid(h3.CARRIERS['S'], q['head'], q['axis'], q['roll'])], sp12=True, sp13=True, fixtures13=fl)
            rel = O-R*WHEEL_PROUD_M; cp = corridor_points(v45, h3.CARRIERS['S']); dmin = float(np.min(np.linalg.norm(cp-rel, axis=1)))-h3.CARRIERS['S']['radius']
            outer = dict(trunk_side_with_sp12_S_at_shunt_start=op_retest(w2, rel, plane_side(O, R, hi=-WHEEL_PROUD_M)), release_to_sp12_corridor_surface_m=round(dmin, 3),
                         reach_zone_m=OP_REACH_M+OP_R_M, corridor_inside_reach_zone=bool(dmin < OP_REACH_M+OP_R_M))
            bpy.data.objects.remove(obj)
            gg = leaf_geometry(ctx, fl, e2, 'aft', g['hinge_offset_m']); vs13 = exit_vehicle_screen(ctx, e2)
            allm = [worst_cars(r6), gg['park_least_m'], gg['swing_least_m']]+[o['least_m'] if o['least_m'] is not None else -9 for o in ops.values()]
            sw[lab] = dict(candidate=g, exit=e2, fitout='aft re-sited (A170)' if (resited is None and nudge is None) else ('A170 aft re-sited, one fixture nudged' if nudge else 'searched again with the leaf keep-out'),
                           nudge=nudge, fixtures=resited, fixture_list=fl, results=r6,
                           carriers_least_m=worst_cars(r6), leaf_geometry=gg, opposite_side_operation=ops, outer_leaf_access=outer, vehicle=vs13, sp13_duct_on_trunk_wall_x=list(sp13_duct_wall_edges(ctx, e2)),
                           least_m=round(min(allm), 3), status=status(min(allm)) if vs13['status'] == 'CLEAR' else 'FAIL', seeds=list(SEEDS6), render=rnd, seconds=round(time.time()-t0))
            print('WF_O13B c1', lab, sw[lab]['least_m'], {c: x['least_m'] for c, x in r6.items()}, gg['swing_least_m'], {k: o['least_m'] for k, o in ops.items()}, flush=True)
            jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
    finally:
        ctx.data['sp13']['x_m'] = [x0, x1]; ctx.data['sp13']['az_deg'] = az0; ROOM13 = room0
    leaf = S13['leaf']
    res['pressure'] = dict(ideal_dp_x_clear_area_kn=round(CABIN_KPA_O13*leaf['clear_area_m2'], 1), clear_area_m2=leaf['clear_area_m2'], basis='DIAGNOSTIC as reported in A170: 80 kPa x the clear aperture ellipse; the aperture is unchanged by these moves; not a seat load, not a rating',
                           open_items=['inward and outward 80 kPa and the design extremes (two polarities; SP-13-high seats the leaf, trunk-high is carried by the dogs only)',
                                       'dog count, dog / keeper capacity and preload; seat and seal', 'jammed-leaf egress (a leaf jammed shut blocks the SP-13 exit; no second exit from SP-13 except the SP-12/SP-13 door, not modelled)',
                                       'manual release (handwheel through spindle reaches the dogs from both faces in geometry; forces, equalization valve, dp interlock threshold OPEN)',
                                       'hinge: not assumed to resist reversed pressure (owner hold); final door style, hull aperture and certification not chosen'],
                           status='OPEN / TWO-POLARITY LOAD HOLD (15!A178)')
    res['rejected'] = 'dual stacked leaves (b), six-seed -0.027 m: rejected by the owner, not re-studied'
    jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
    return res


# ---------------------------------------------------------------------------------------------------------------------------------
# segments and merge

def o13b_segments(B1, B2, C1):
    out = []; ALL = ALL_STATES
    def carseg(prefix, route, variant, case, sw, note=''):
        for cid, q in sw['carriers'].items():
            out.append(seg(f'{prefix}-{cid}', route, ALL, variant, f'{CAR_NAMES.get(cid, cid)}: {case}', q['least_m'], [CAR_NAMES.get(cid, cid), 'body', 'rescuers' if cid != 'U' else 'self-propelled', f'seeds {sw["seeds"]}'],
                           q['seed_spread_m'], q['nearest'], f'body {q["body_least_m"]}, rescuers {q["rescuers_least_m"]}, limiting zone {q["zone"]}. {note}'.strip()))
    if B1:
        carseg('A176-SP12-N2FWD45-E2E', 'SP-12 exit N2 fwd45 (A176)', 'N2 fwd45 1.10 m, NEXT REVERSIBLE comparison only', 'complete litter route chamber -> SP-12 -> duct -> extension -> shunt aft -> refuge port station', B1['e2e'])
        for side in ('sp12_side', 'trunk_side'):
            q = B1['opposite_side'][side]
            out.append(seg(f'A176-SP12-N2FWD45-OP-{side}', 'SP-12 exit N2 fwd45 (A176)', ALL, 'N2 fwd45 1.10 m', f'opposite-side operation retest, {side.replace("_", " ")} (search to 0.30 m)', q['least_m'], ['operator torso r 0.25 m', f'seeds {q["seeds"]}'], None, q['nearest'], f'by seed {q["by_seed"]}; reach used {q["reach_used_m"]}.'))
        for k, q in B1['single_fault'].items():
            if k == 'logic':
                continue
            if 'sweep' in q:
                carseg(f'A176-SP12-N2FWD45-SF-{k}', 'SP-12 exit N2 fwd45 (A176)', 'N2 fwd45 1.10 m, single fault', q['desc'], q['sweep'])
            else:
                for side in ('sp12_side', 'trunk_side'):
                    o = q[side]; out.append(seg(f'A176-SP12-N2FWD45-SF-{k}-{side}', 'SP-12 exit N2 fwd45 (A176)', ALL, 'N2 fwd45 1.10 m, single fault', f'{q["desc"]}: release reachable from the {side.replace("_", " ")}', o['least_m'], ['operator torso r 0.25 m'], None, o['nearest'], f'by seed {o["by_seed"]}.'))
        for an, r in B1['hoist']['anchors'].items():
            lw = r['line_while_lowering_aft']
            out.append(seg(f'A176-SP12-N2FWD45-HOIST-{an.split()[0]}', 'SP-12 exit N2 fwd45 (A176)', ['locked_1.5g'], f'hoist anchor {an} at {r["anchor"]}', 'hoist line (lift and lowering) vs the SP-13 exit solid and the SP-13 carrier S envelope',
                           min(lw['to_sp13_S_envelope_m'], min(z['to_sp13_S_envelope_m'] for z in r['line_while_lifting'].values())), ['line while lifting (H, D, E)', 'line while lowering aft'], None, 'SP-13 S envelope',
                           f'anchor to SP-13 exit solid {r["anchor_to_sp13_exit_solid_m"]} m; line vs walls while lifting {({z: q["to_walls_m"] for z, q in r["line_while_lifting"].items()})} (negative = needs a deflector); loads OPEN.'))
        out.append(seg('A176-SP12-N2FWD45-HOIST-LOADS', 'SP-12 exit N2 fwd45 (A176)', ['locked_1.5g'], 'N2 fwd45 1.10 m', f'hoist / lowering anchor loads for the {B1["hoist"]["centre_lift_m"]} m lift', None, [], None, None, 'OPEN: no load, rating or effort assumed.', 'OPEN'))
    if B2:
        for k, sw in B2['sweeps13'].items():
            carseg(f'A177-SP13-{k}', 'SP-13 exit vs SP-12 faults (A177)', k, sw.get('desc', 'no SP-12 fault (reference)'), sw)
        for nm, a in B2['alternates'].items():
            carseg(f'A177-ALT-{nm}-SP12', 'SP-12 alternate corridor (A177)', nm, 'SP-12 carriers, chamber to the refuge port station / trunk', a['sp12_sweep'], f'vehicle {a["vehicle"]["status"]}; spine-core cut {a["spine_core_cut_x_m"]} m.')
        for nm, en in [(N2F[0], B2['envelopes'][N2F[0]])]+[(k, a['envelope']) for k, a in B2['alternates'].items()]:
            out.append(seg(f'A177-ENV-{nm}', 'SP-12 / SP-13 shared extension (A177)', ALL, nm, 'SP-12 corridor (S envelope) vs the SP-13 exit route from SP-13 to its landing', en['gap_to_sp13_route_R_to_landing_m'], ['S capsule envelopes'], None, None,
                           f'vs SP-13 exit solid {en["gap_to_sp13_exit_solid_m"]} m; transverse isolation window {en["transverse_isolation_window_m"]} m; corridor in the bore X {en["corridor_x_in_bore"]}.'))
        o = B2['outer_leaf_access']['with_sp12_S_at_shunt_start']
        out.append(seg('A177-SP13-OUTER-LEAF-ACCESS', 'SP-13 exit vs SP-12 faults (A177)', ALL, 'N2 fwd45 carrier S at its shunt start', 'trunk-side operation of the SP-13 leaf', o['least_m'], ['operator torso r 0.25 m'], None, o['nearest'], f'release to SP-12 corridor surface {B2["outer_leaf_access"]["release_to_sp12_corridor_surface_m"]} m.'))
        out.append(seg('A177-ISOLATION', 'SP-12 / SP-13 shared extension (A177)', ALL, 'all layouts studied', 'pressure isolation between the SP-12 and SP-13 routes', None, [], None, None, B2['isolation']['shared_volume'], 'OPEN'))
    if C1:
        for lab, q in C1['sweeps'].items():
            if 'results' not in q:
                continue
            g = q['candidate']
            out.append(seg(f'A178-SP13-LEAF-{lab}', 'SP-13 closure (A178)', ALL, f'aft hinge, offset {g["hinge_offset_m"]} m, partition aft {g["dP"]} m, mount fwd {g["dM"]} m, sideways {g["dT"]} m (az {g["exit_az"]}), side wall out {g.get("dW", 0.0)} m', 'carriers, leaf park / swing, operation from both sides; minimum over all', q['least_m'],
                           ['carrier A', 'carrier S', 'carrier K', 'suited crew', 'rescuers', 'leaf park', 'leaf swing 5-90 deg', 'operator SP-13 side', 'operator trunk side', f'seeds {q["seeds"]}'], None, min(q['results'].items(), key=lambda kv: kv[1]['least_m'])[1]['nearest'],
                           f'carriers {({c: x["least_m"] for c, x in q["results"].items()})}; park {q["leaf_geometry"]["park_least_m"]}, swing {q["leaf_geometry"]["swing_least_m"]}; operators {({k: o["least_m"] for k, o in q["opposite_side_operation"].items()})}; SP-12 fixture margin {g["sp12_fixture_margin_m"]} m.',
                           q['status']))
            o = q['outer_leaf_access']['trunk_side_with_sp12_S_at_shunt_start']
            out.append(seg(f'A178-SP13-LEAF-{lab}-OUTER-ACCESS', 'SP-13 closure (A178)', ALL, lab, 'outer (trunk-side) leaf access with the SP-12 N2 fwd45 carrier at its forward-most point', o['least_m'], ['operator torso r 0.25 m'], None, o['nearest'], f'by seed {o["by_seed"]}.'))
        out.append(seg('A178-SP13-DP80', 'SP-13 closure (A178)', ALL, 'aft hinged dogged leaf', '80 kPa both directions, dogs / preload, jammed-leaf egress, manual release', None, C1['pressure']['open_items'], None, None,
                       f'ideal dp x clear area {C1["pressure"]["ideal_dp_x_clear_area_kn"]} kN (DIAGNOSTIC only).', 'OPEN'))
    return out


def compact_c1(C1):
    """The c1 grids as one line per row (the full rows stay in the run folder's o13b_c1.json)."""
    c = {k: v for k, v in C1.items() if k not in ('grid', 'grid_side_wall')}
    rows = [g for g in C1.get('grid', [])+C1.get('grid_side_wall', []) if g['hinge_offset_m'] == HINGE_OFFSETS_B[0]]
    c['grid_compact'] = dict(columns='dP dM dT dW (m) | exit X az | park room / fit-out | swing room / fit-out | swing limit | lane ok | SP-12 fixture margin',
                             hinge_offset_m=HINGE_OFFSETS_B[0], rows=[f"{g['dP']:.2f} {g['dM']:.2f} {g['dT']:.2f} {g.get('dW', 0.0):.2f} | {g['exit_xp']:.2f} {g['exit_az']:.2f} | {g['park_room_m']:+.3f} / {g['park_fitout_m']:+.3f} | "
                                                                   f"{g['swing_room_m']:+.3f} / {g['swing_fitout_m']:+.3f} | {g['swing_limiting_bound']} | {g['lane_ok']} | {g['sp12_fixture_margin_m']:+.3f}" for g in rows])
    for q in c.get('sweeps', {}).values():
        for r in q.get('results', {}).values():
            r.pop('by_seed', None)
    return c


def merge_o13b(B1, B2, C1, segs):
    jf = ROOT/'references/p1_eva_sp13_l1a.json'; d = json.loads(jf.read_text()); C1 = compact_c1(C1)
    d[O13B_TAG] = dict(owner_refs=['15!A176 OWN-RES-B1-2026-10-13', '15!A177 OWN-RES-B2-2026-10-13', '15!A178 OWN-RES-C1-2026-10-13'],
                       status='NONCANON PROTOTYPE, disposable geometry; the 45 deg duct is not installed; zero canonical geometry change; cutout, pressure rating and loads HOLD / OPEN',
                       band=BAND, seeds_worst_case=list(SEEDS6), constants=dict(shift_steps_m=list(SHIFT_STEPS_M), hinge_offsets_m=list(HINGE_OFFSETS_B), op_cap_m=OP_CAP_B, push_az_deg=PUSH_AZ_DEG),
                       b1=B1, b2=B2, c1=C1)
    jf.write_text(json.dumps(d, indent=1, default=str)+'\n')
    sf = ROOT/'references/p1_access_seg_sp13_l1a.json'; d = json.loads(sf.read_text())
    d['segments'] = [g for g in d['segments'] if not g['id'].startswith(('A176-', 'A177-', 'A178-'))]+segs
    if '15!A176-A178' not in d['study']:
        d['study'] += ' + owner 2026-10-13b 15!A176-A178 (A176-*/A177-*/A178-* segments)'
    sf.write_text(json.dumps(d, indent=1)+'\n')


def main_o13b(out, parts):
    ctx = load_ctx(); out.mkdir(parents=True, exist_ok=True); ex.load_room(ctx.s)
    S13 = json.loads((ROOT/'references/p1_eva_sp13_l1a.json').read_text())['owner_2026_10_13']['sp13_closure']
    B1 = run_o13b_b1(ctx, out, S13) if 'b1' in parts else None
    B2 = run_o13b_b2(ctx, out, S13) if 'b2' in parts else None
    C1 = run_o13b_c1(ctx, out, S13) if 'c1' in parts else None
    if 'merge' in parts:
        B1 = B1 or json.loads((out/'o13b_b1.json').read_text()); B2 = B2 or json.loads((out/'o13b_b2.json').read_text()); C1 = C1 or json.loads((out/'o13b_c1.json').read_text())
        segs = o13b_segments(B1, B2, C1); merge_o13b(B1, B2, C1, segs); print('WF_O13B merged', len(segs), 'segments', flush=True)
    print('WF_O13B done', parts, flush=True)


# =================================================================================================================================
# Owner 2026-10-13c (S&E 15!A177 OWN-RES-B2 "protect SP-13 independent exit in all scenarios"; 15!A136 / 15!A158 independent SP-13 exit; 15!A171 /
# 15!A179 L1-A ladder; verbatim in references/drive_capture_2026-10-13c/engineering.txt lines 693, 715, 734). Disposable study, zero canonical
# geometry change: no pressure-shell edit, no generator, no saved asset; every new form is PROTOTYPE. Design direction under study (main agent):
# SP-13's independent exit goes SIDEWAYS from the L1-A extension into the L1-A district through the district port (205-215 deg, X 104.1, ladder
# with the A179 stile candidate CB2J6 / CB2J6DP), not aft down the single trunk; SP-12 is rerouted to ALT-2 (N2 aft30) so that the SP-12 corridor
# stays in the built trunk (X 97-101) and never enters the extension. Results under the key `owner_2026_10_13c` of references/p1_eva_sp13_l1a.json,
# segments A177C-*.
#   alt2:     what limits ALT-2 (Trunk_Fit_Frame_13_1: identity and source), the ring frame broken round the duct opening (PROTOTYPE, as the
#             generator breaks frames round every built opening), duct variants aft 25 / 30 / 35 deg x landing X -0.2 / 0 / +0.2 m, carriers S, A,
#             K with two rescuers (three seeds, six where nothing FAILs), the 1.5 g lowering and the hoist interfaces of the best variant.
#   district: SP-13 -> exit -> extension -> district port (205 / 210 / 215 deg) -> L1-A workshop, carriers S, A, K with two rescuers and the suited
#             crew member U; failure tree with each ALT-2 SP-12 fault in its corridor; outer SP-13 leaf access with the ALT-2 carrier at its
#             forward-most point; pressure isolation geometry and the district's onward ways (no new pressure path is invented).
#   ladder:   the A179 candidate ladder vs the ALT-2 opening (its true duct bore and rim), the dock bridge window, the hoist guide and the dock mouth.

O13C_TAG = 'owner_2026_10_13c'
ALT2_PSIS = (30.0, 25.0, 35.0)                 # duct lean aft of the radial, deg (30 = A177 ALT-2, run first)
ALT2_DXA = (0.0, -0.2, 0.2)                    # duct top station moved along X (m): the landing X moves with it (PROTOTYPE)
FRAME_PAD_M = 0.05                             # the ring frame ends this far outside the duct bore (the generator leaves 2 deg ~ 0.03 m round fixtures)
WS_DEG = 240.0                                 # workshop azimuth (SERV-003 / A171 whitebox)
DP_X = 104.1                                   # district port station (A171)
STILE_FOR = {205.0: 'CB2J6', 210.0: 'CB2J6', 215.0: 'CB2J6DP'}     # A179 recommendation per port angle (references/L1A_STILE_2026-10-13.md)
HOIST_GUIDE = dict(rho=0.72, deg=105.0, x1=102.4)                    # HUM-003 trunk hoist guide rail line (trunk r - 0.08, across from the ladder)
DP110_X = 104.25                               # a 1.10 m district port must rise 0.15 m to keep its aft edge above the workshop floor (PROTOTYPE)


def alt2_variant(psi_deg, dxa=0.0, D=1.10):
    """ALT-2 family (A177 'N2_oblique30_1.10' at psi 30, dxa 0): a D round duct leaning psi AFT from under the SP-11 chamber into the built trunk."""
    psi = math.radians(psi_deg); (xa, ra), (xe, re), t = ex.duct_axis(psi, xa=ex.XC+0.60+dxa); L = math.hypot(xa-xe, ra-re)
    p0, p1 = P(xa+0.35, ra+0.35*t), P(xe-0.4, re-0.4*t); xf = xa-(ra-1.25)/t
    A = np.array(P(xa, ra), float); E = np.array(P(xe, re), float); u = (E-A)/np.linalg.norm(E-A); wx = xa-(ra-0.80)/t
    return dict(name=f'ALT2_aft{psi_deg:.0f}_dx{dxa:+.1f}', kind='oblique', D=D, psi_deg=psi_deg, dxa=dxa,
                unions=[lambda D=D, p0=p0, p1=p1: h3.prim_cyl(p0, p1, D/2)],
                path=[('C', P(ex.XC, 5.8)), ('H', P(ex.XC, ra-(xa-ex.XC)*t)), ('D', P(xe, re)), ('T', (xe-1.4, 0.0, 0.0)), ('T', (xe-2.9, 0.0, 0.0))],
                area=math.pi*(D/2)**2, duct=dict(xa=xa, ra=ra, xe=xe, re=re, length_m=round(L, 3)), solid=dict(a=p0, b=p1, r=D/2), floor_x=xf,
                below_pt=P(xa-(ra-1.05)/t, 1.05), A=A, u=u, wall_x=wx, floor_aperture_x=(xf-D/2/math.sin(psi), xf+D/2/math.sin(psi)),
                desc=f'{D:.2f} m round duct leaning {psi_deg:.0f} deg AFT from under the chamber (X {xa:.2f}, r {ra:.2f}) to the built trunk (axis on the trunk wall '
                     f'X {wx:.2f}, landing X {xe:.2f}); the carrier turns aft on the axis and goes down the trunk')


def bore_gap(v, pts, rr=0.0, side=True):
    """Distance (m) from points (surface = point - rr) to the duct's bore cylinder carried into the trunk; side: only on the duct's side of the axis."""
    p = np.atleast_2d(np.asarray(pts, float)); w = p-v['A']; al = w@v['u']; g = np.linalg.norm(w-np.outer(al, v['u']), axis=1)-v['D']/2-rr
    if side:
        g = np.where(p[:, 1]*math.cos(ex.AZ)+p[:, 2]*math.sin(ex.AZ) > 0, g, np.inf)
    return g


def duct_rim(v, rw=0.80, n=144):
    """The duct opening's rim on the trunk wall (intersection of the duct bore with the r rw cylinder)."""
    u = v['u']; e1 = np.cross(u, (1.0, 0.0, 0.0)); e1 /= np.linalg.norm(e1); e2 = np.cross(u, e1); out = []
    r_ = lambda q: math.hypot(q[1], q[2]); L = v['duct']['length_m']
    for k in range(n):
        ps = 2*math.pi*k/n; o = v['A']+v['D']/2*(math.cos(ps)*e1+math.sin(ps)*e2); lo, hi = 0.0, L+0.6
        if not (r_(o+lo*u) > rw > r_(o+hi*u)):
            continue
        for _ in range(40):
            m = 0.5*(lo+hi)
            lo, hi = (m, hi) if r_(o+m*u) > rw else (lo, m)
        out.append(o+0.5*(lo+hi)*u)
    return np.array(out)


def wall_rim(xc, th, r, rw=0.80, n=360):
    """Rim on the trunk wall (radius rw) of a radial opening of radius r at (xc, th): fore and aft edges (works for r > rw, e.g. Dock_Primary)."""
    out = []
    for k in range(n):
        a = 2*math.pi*k/n; d = ct.angle_diff(a, th)
        if math.cos(d) <= 0:
            continue
        lat = rw*math.sin(d)
        if abs(lat) < r:
            h = math.sqrt(r*r-lat*lat)
            out += [(xc-h, rw*math.cos(a), rw*math.sin(a)), (xc+h, rw*math.cos(a), rw*math.sin(a))]
    return np.array(out)


def frame_cut(records, v, pad=FRAME_PAD_M):
    """PROTOTYPE, non-destructive: the trunk ring frames (route_fitout Trunk_Fit_Frame_*, ARCHITECTURE fit-out) broken round the duct opening (faces
    whose centre lies within pad of the duct bore, wall band r >= 0.70 m, removed), as trunk_elements() breaks them round every built opening.
    Returns (records, {frame: faces removed}, [other fixtures with faces inside the bore at the wall])."""
    out, cut, other = [], {}, set()
    for q in records:
        V = np.asarray(q['vs'], float); cen = np.array([V[list(f)].mean(0) for f in q['fs']])
        wall = np.hypot(cen[:, 1], cen[:, 2]) >= 0.70; g = bore_gap(v, cen)
        ins = wall & (g < pad)
        if q['name'].startswith('Trunk_Fit_Frame_') and ins.any():
            cut[q['name']] = int(ins.sum()); fs = [f for f, k in zip(q['fs'], ins) if not k]
            if fs:
                out.append(dict(q, fs=fs))
            continue
        if (wall & (g < 0)).any():
            other.add(q['name'])
        out.append(q)
    return out, cut, sorted(other)


def walls_c(ctx, fx, unions, diffs, sp12, sp13=True, fl13=None, extra=None):
    data2 = copy.deepcopy(ctx.data)
    if fl13 is not None:
        data2['sp13']['fixtures'] = fl13
    obj, tree = ex.build_free(ctx.s, data2, unions, diffs, ex.TRUNK_EXT_X, sp12=sp12, sp13=sp13, ref=True, fit=True)
    return obj, WallsPlus(fx, ctx.pts, free=tree, extra=extra)


def corridor_env(v, rS):
    pts = corridor_points(v, h3.CARRIERS['S']); inb = pts[np.hypot(pts[:, 1], pts[:, 2]) < 0.80]; fwd = float(inb[:, 0].max())
    return dict(corridor_x_in_bore=[round(float(inb[:, 0].min()), 2), round(fwd, 2)], carrier_forward_end_x=round(fwd+rS, 2),
                with_rescuer_forward_end_x=round(fwd+rS+h3.STAFF_REACH_M+h3.STAFF_R_M, 2), lands_x=round(v['duct']['xe'], 2),
                enters_extension=bool(fwd+rS+h3.STAFF_REACH_M+h3.STAFF_R_M > EXT_AFT_X))


def o13c_ctx():
    import l1a_stile as LS                      # read-only reuse of the A179 candidate ladder (lazy: l1a_stile imports this module)
    ctx = load_ctx(); ex.load_room(ctx.s); recs = cs.scene(ctx.s, cs.load_inspect(), 1.0)
    ctx.fx_nl = h3.fixtures(recs, drop=lambda q: 'Ladder' in q['name'] or 'Arrest_Rail' in q['name']); ctx.LS = LS
    ctx.Lo = json.loads((ROOT/'references/p1_eva_sp13_l1a.json').read_text())[O13_TAG]['l1a']
    ctx.ladder = {al: LS.ladder_bvh(ctx.s, LS.CANDS[c], al) for al, c in STILE_FOR.items()}
    return ctx


# ---------------------------------------------------------------------------------------------------------------------------------
# alt2

def frame_identity(s):
    import route_fitout as rf
    el = {e['name']: e for e in rf.trunk_elements(s)}; e = el['Trunk_Fit_Frame_13_1']; p = s['route_fitout']
    return dict(name=e['name'], function=e['function'], layer=e['layer'], grammar=e['grammar'], design_class=e['design_class'], geometry_status=e['geometry_status'],
                x=[round(v, 3) for v in e['x']], rho_m=list(e['rho']), phi_deg=[round(v, 1) for v in e['phi']],
                source='src/wayfarer/route_fitout.py trunk_elements() (IND-001 cultural fit-out, scheme D, built into WF_CREW_TRANSFER); [route_fitout] status PROTOTYPE in data/wayfarer_3d.toml '
                       f'(frame_depth_m {p["frame_depth_m"]}, frame_width_m {p["frame_width_m"]}, trunk_frame_pitch_m {p["trunk_frame_pitch_m"]}); no data/source_map.toml entry (no owner source)',
                verdict='FIT-OUT, not structure or pressure: an ARCHITECTURE-layer ring frame 0.035 m deep inside the 0.80 m trunk clear radius that carries the replaceable wall '
                        'panels; the trunk pressure wall (passage_wall_m 0.05 m, r 0.80-0.85) is separate. The generator already breaks these frames round every rail, light, '
                        'ladder and opening (docs/MODEL.md Architecture); AGENTS.md: fit-out never changes a pressure boundary. Its frames 1..13 sit every '
                        f'{(rf.trunk_extent(s)[2]-rf.trunk_extent(s)[1])/14:.3f} m, so an opening 2.2 m long always meets one: relocating the frame along X cannot clear it.',
                neighbours={k: dict(x=[round(v, 3) for v in q['x']], phi_deg=[round(v, 1) for v in q['phi']]) for k, q in el.items() if k.startswith(('Trunk_Fit_Frame_12_', 'Trunk_Fit_Frame_13_'))})


def run_o13c_alt2(ctx, out, S13):
    s = ctx.s; jf = out/'o13c_alt2.json'; res = json.loads(jf.read_text()) if jf.exists() else {}
    save = lambda: jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
    res['limiter'] = frame_identity(s); res['a177_reference'] = dict(S=-0.134, A=-0.092, K=-0.092, nearest='Trunk_Fit_Frame_13_1', note='A177 ALT-2 own carriers, six seeds, frame as built, no ladder extension')
    lad = ctx.ladder[210.0]; cars = dict(S=h3.CARRIERS['S'], A=h3.CARRIERS['A'], K=h3.CARRIERS['K']); rS = h3.CARRIERS['S']['radius']
    q12 = ctx.data['sp12']; V = res.setdefault('variants', {})
    for psi in ALT2_PSIS:
        for dxa in ALT2_DXA:
            v = alt2_variant(psi, dxa); r = V.setdefault(v['name'], {})
            if 'sweep' in r:
                continue
            fx, cut, other = frame_cut(ctx.fx_nl, v); rim = duct_rim(v)
            ex.PSI = math.radians(psi); veh = ex.vehicle_screen(s, ctx.obs, dict(kind='oblique', D=v['D'], area=v['area'], duct=v['duct'])); ex.PSI = math.radians(15.0)
            fa = v['floor_aperture_x']
            r.update(desc=v['desc'], psi_deg=psi, dxa_m=dxa, duct=v['duct'], wall_x=round(v['wall_x'], 3), opening_on_trunk_wall_x=[round(float(rim[:, 0].min()), 3), round(float(rim[:, 0].max()), 3)],
                     frames_broken=cut, other_fixtures_in_opening=other, vehicle=veh, spine_core_cut_x_m=duct_spine_cut(s, v), envelope=corridor_env(v, rS),
                     sp12_floor_aperture_x=[round(fa[0], 3), round(fa[1], 3)], sp12_room_x=list(q12['x_m']), aperture_past_sp12_aft_wall_m=round(max(0.0, q12['x_m'][0]-fa[0]), 3))
            t0 = time.time(); obj, w = walls_c(ctx, fx, v['unions'], [], sp12=True, sp13=False, extra=lad)
            r['sweep'] = sweep_wc(w, cars, sp12_e2e_route(v), 'C_ALT2_'+v['name'], v=v); r['seconds'] = round(time.time()-t0)
            bpy.data.objects.remove(obj); save()
            print('WF_O13C alt2', v['name'], r['sweep']['least_m'], {c: q['least_m'] for c, q in r['sweep']['carriers'].items()}, cut, r['seconds'], flush=True)
    # the as-built frame for the reference variant with the same rig (ladder extension), so the frame's share is measured, not assumed
    if 'reference_frame_as_built' not in res:
        v = alt2_variant(30.0, 0.0); obj, w = walls_c(ctx, ctx.fx_nl, v['unions'], [], sp12=True, sp13=False, extra=lad)
        res['reference_frame_as_built'] = sweep_wc(w, cars, sp12_e2e_route(v), 'C_ALT2_asbuilt', v=v); bpy.data.objects.remove(obj); save()
    ok = {k: q for k, q in V.items() if q['vehicle']['status'] == 'CLEAR' and not q['envelope']['enters_extension']}
    best = max(ok, key=lambda k: (ok[k]['sweep']['least_m'], -abs(ok[k]['psi_deg']-30.0)-abs(ok[k]['dxa_m'])))
    res['best'] = best; res['best_least_m'] = V[best]['sweep']['least_m']; res['best_status'] = V[best]['sweep']['status']
    if 'hoist' not in res:
        res['hoist'] = alt2_hoist(ctx, alt2_variant(V[best]['psi_deg'], V[best]['dxa_m']), S13, lad); save()
    save()
    return res


def alt2_hoist(ctx, v, S13, lad):
    """1.5 g (aft down, +X up): the vertical travel of carrier S along the ALT-2 route and the anchor / line geometry (lowering), as the A176 check."""
    s = ctx.s; e13, fl13, leaf = sp13_parts(S13); s13 = s13_solid(e13); r13, xe13 = route_for(e13); r13_pts = [np.array(p) for _, p in r13]
    route = sp12_e2e_route(v); prof = path_profile(route, h3.CARRIERS['S']); cx = [p[2][0] for p in prof]; hx = [p[1][0] for p in prof]
    rise = max(c-min(cx[:i+1]) for i, c in enumerate(cx)); drop = max(cx)-min(cx)
    fx, _, _ = frame_cut(ctx.fx_nl, v); G = ladder_geom(s, 285.0)
    obj, wc = walls_c(ctx, fx, v['unions']+[exit_solid(e13)], list(leaf_solids(e13, *leaf, PARK_DEG)), sp12=True, sp13=True, fl13=fl13, extra=lad)
    ins = union_inside_fn(ctx, v, e13, fl13); up = -v['u']; top = np.array(P(v['duct']['xa']+0.35, v['duct']['ra']+0.35*math.tan(math.radians(v['psi_deg']))))
    anchors = {'SP-12, on the duct axis 0.60 m above the duct top': top+0.60*up, 'HUM-003 trunk hoist head (0.25 m @105 deg, X 102.25)': np.array(ct.radial(102.4-h3.HOIST_HEAD_M, 0.25, math.radians(105.0))),
               'trunk axis, X 102.25': np.array((102.4-h3.HOIST_HEAD_M, 0.0, 0.0))}
    rows = {}
    for an, A_ in anchors.items():
        z = {}
        for zn in ('H', 'D', 'T'):
            hs = [p[1] for p in prof if p[0] == zn]
            if hs:
                ms = [line_metrics(wc, A_, h_, s13, r13_pts, G['lines'], ins) for h_ in hs[::4]]; worst = min(ms, key=lambda m: m['to_walls_m'])
                z[zn] = {k: min(m[k] for m in ms) for k in ('to_walls_m', 'to_sp13_exit_solid_m', 'to_sp13_S_envelope_m', 'to_ladder_lines_m')}
                z[zn].update(walls_nearest=worst['walls_nearest'], at=worst['at'])
        rows[an] = dict(anchor=[round(float(q), 3) for q in A_], anchor_inside_free_space=bool(ins(A_)), anchor_to_sp13_exit_solid_m=round(pt_seg(A_, s13[0], s13[1])-s13[2], 3), line_by_zone=z)
    bpy.data.objects.remove(obj)
    return dict(variant=v['name'], centre_x_start=round(cx[0], 3), centre_x_end=round(cx[-1], 3), centre_rise_m=round(rise, 3), centre_drop_m=round(drop, 3),
                head_x_range=[round(min(hx), 2), round(max(hx), 2)],
                note=f'locked 1.5 g aft-down: along ALT-2 the casualty never rises (largest rise {rise:.2f} m); it is LOWERED {drop:.2f} m (centre X {max(cx):.2f} -> {min(cx):.2f}) from the SP-12 '
                     'floor turn down the aft-leaning duct and the trunk: a controlled-lowering (belay / hoist-down) interface, not a lift',
                anchors=rows, loads='OPEN: anchor, line, sheave and brake loads, lowering speed and handling effort are not assumed', status='GEOMETRY ONLY; loads OPEN')


# ---------------------------------------------------------------------------------------------------------------------------------
# district

def workshop_geom(ctx):
    o, R, els, ext = ed.serv_elements(ctx.s, ctx.obs, math.radians(WS_DEG), 'A', math.radians(210), 106.3)
    W = R['workshop']; w = ctx.s['human_entry']['chamber_wall_m']
    return dict(W=W, R=R, option=o, x=(W['x'][0]+w, W['x'][1]-w), u=(W['u'][0]+w, W['u'][1]-w), t=W['t'][1]-w, phi=W['phi'], d=W['u'][0], wall=w)


def ws_pt(G, x, u, t):
    ph = G['phi']; return (x, u*math.cos(ph)-t*math.sin(ph), u*math.sin(ph)+t*math.cos(ph))


def ws_solid(G):
    c = ws_pt(G, 0.5*sum(G['x']), 0.5*sum(G['u']), 0.0); size = (G['x'][1]-G['x'][0], 2*G['t'], G['u'][1]-G['u'][0])
    return lambda c=c, ax=axes_at(G['phi']), size=size: h3.prim_box(c, ax, size)


def dport(G, alpha, D=0.90, x=DP_X):
    a = math.radians(alpha); dphi = math.radians(alpha-WS_DEG); rf = G['u'][0]/math.cos(dphi); lat = G['d']*math.tan(dphi); w = 0.05
    return dict(alpha=alpha, D=D, x=x, r_face=round(rf, 3), lateral_on_face_m=round(lat, 3), fits_face=bool(abs(lat)+D/2+w <= G['t']+w),
                aft_edge_above_floor_m=round(x-D/2-w-G['x'][0], 3), solid=lambda a=a, re=(G['u'][0]+D/2*abs(math.sin(dphi)))/math.cos(dphi)+0.10, D=D, x=x:
                h3.prim_cyl(ct.radial(x, 0.60, a), ct.radial(x, re, a), D/2))     # the tube runs on until its whole end cap is inside the workshop (oblique wall)


def port_ladder_gap(ctx, port):
    """Least gap (m) from the A179 candidate ladder members (stiles, rail; the candidate used at this angle, and CB2J6DP) to the district port's bore."""
    LS = ctx.LS; al = float(port['alpha']); out = {}
    for cn in sorted({STILE_FOR[al], 'CB2J6DP'}):
        lad = LS.Lad(ctx.s, LS.CANDS[cn], al); xs = np.arange(lad.floor, LADDER_TOP_X+1e-9, 0.01)
        out[cn] = round(min(LS.pt_gap(Pp, rr, [('District_Port', port['x'], math.radians(al), port['D']/2)])[0] for Pp, rr in lad.lines(xs).values()), 3)
    return out


def route_district(e, G, port, rc=3.3):
    """SP-13 -> 45 deg exit -> landing -> across the bore -> district port (head first) -> straight on along the port axis into the workshop until the
    head is 0.55 m off its far or side wall (PROTOTYPE route). A carrier that barely fits the port cannot bend while its tail is in the port tube, so
    the route ends there: when the straight run is shorter than the carrier, the tail is still in the port at the end (straight_run reports it)."""
    a = math.radians(e['az']); t = math.tan(math.radians(e['beta'])); xp = e['xp']; xe = xp-(1.25-0.37)*t; xs = min(xp+(rc-1.25)*t, ROOM13['x'][1]-0.45)
    al = math.radians(port['alpha']); x = port['x']; r_max = straight_run(G, port)[1]
    wps = [('R', P(xs, rc, az=a)), ('H', P(xp+(2.0-1.25)*t, 2.0, az=a)), ('D', P(xe, 0.37, az=a)), ('P', ct.radial(x, 0.45, al)), ('P', ct.radial(x, port['r_face'], al)),
           ('W', ct.radial(x, r_max, al))]
    return ex.smooth(wps, cut=0.5)


def straight_run(G, port, rc=0.55):
    """Straight run (m) available inside the workshop along the port axis from the inner face, keeping rc (S radius 0.43 + 0.12) off the far and side
    walls: a rigid carrier that barely fits the port must go straight until its tail has left the port tube. Returns (run, r at its end)."""
    dphi = math.radians(port['alpha']-WS_DEG); lim = [(G['u'][1]-rc)/math.cos(dphi)]
    if abs(math.sin(dphi)) > 1e-9:
        lim.append((G['t']-rc)/abs(math.sin(dphi)))
    r_max = min(lim); return round(r_max-port['r_face'], 3), r_max


def seg_gap(a0, a1, b0, b1, n=40):
    A = np.linspace(a0, a1, n); B = np.linspace(b0, b1, n); return float(np.min(np.linalg.norm(A[:, None, :]-B[None, :, :], axis=2)))


def obstacle_axis(q):
    car = q['car'] if isinstance(q['car'], dict) else h3.CARRIERS[q['car']]
    L = h3.length(car); r = car['radius'] if car['shape'] == 'capsule' else math.hypot(car['size'][1]/2, car['size'][2]/2)
    h = np.asarray(q['head'], float); return h, h+np.asarray(q['axis'], float)*L, r


def run_o13c_district(ctx, out, S13):
    s = ctx.s; jf = out/'o13c_district.json'; res = json.loads(jf.read_text()) if jf.exists() else {}
    save = lambda: jf.write_text(json.dumps(res, indent=1, default=str)+'\n')
    e13, fl13, leaf = sp13_parts(S13); leaf_d = list(leaf_solids(e13, *leaf, PARK_DEG)); G = workshop_geom(ctx); v12 = alt2_variant(30.0, 0.0)
    fx, _, _ = frame_cut(ctx.fx_nl, v12); cars = carriers(ctx); rS = h3.CARRIERS['S']['radius']; e0, e1 = sp13_duct_wall_edges(ctx, e13)
    res['setup'] = dict(sp13_exit=e13, sp13_closure='A170 aft hinge 0.02 m, re-sited fit-out, leaf parked open (as A177)', sp12='ALT-2 N2 aft30 (A177), frames broken round its opening',
                        workshop=dict(x=[round(v, 3) for v in G['x']], u=[round(v, 3) for v in G['u']], half_t=round(G['t'], 3), phi_deg=WS_DEG, inner_face_d=round(G['d'], 3),
                                      note='SERV-003 option A workshop (4.0 x 2.5 x 2.4 m clear), interior empty: its machines / fit-out are not modelled (OPEN)'),
                        ladder={str(int(k)): c for k, c in STILE_FOR.items()}, sp13_duct_on_trunk_wall_x=[e0, e1])
    D_ = res.setdefault('routes', {})
    def run_route(key, port, label, diffs=(), which=('S', 'A', 'K', 'U'), with12=True, always6=False):
        if key in D_:
            return D_[key]
        unions = [exit_solid(e13), port['solid'], ws_solid(G)]+(list(v12['unions']) if with12 else [])
        t0 = time.time(); obj, w = walls_c(ctx, fx, unions, leaf_d+list(diffs), sp12=with12, sp13=True, fl13=fl13, extra=ctx.ladder[float(port['alpha'])])
        sw = sweep_wc(w, {c: cars[c] for c in which}, route_district(e13, G, port), 'C_DIST_'+key, always6=always6)
        sw.update(port={k: v for k, v in port.items() if k != 'solid'}, seconds=round(time.time()-t0), ladder_to_port_edge_m=port_ladder_gap(ctx, port), straight_run_in_workshop_m=straight_run(G, port)[0]); D_[key] = sw; bpy.data.objects.remove(obj); save()
        print('WF_O13C district', key, sw['least_m'], {c: q['least_m'] for c, q in sw['carriers'].items()}, flush=True)
        return sw
    # 1. the route at each port angle (0.90 m district port, the A171 whitebox)
    for al in PORT_ALPHAS:
        run_route(f'P{int(al)}_D090', dport(G, al), f'port {al}')
    # 2. if a carrier FAILs at 0.90 m, the exit size 1.10 m (raised to X 104.25 so its aft edge stays above the workshop floor; PROTOTYPE whitebox)
    if any(q['least_m'] < 0 for k, sw in D_.items() if k.endswith('_D090') for q in sw['carriers'].values()):
        for al in PORT_ALPHAS:
            run_route(f'P{int(al)}_D110', dport(G, al, 1.10, DP110_X), f'port {al} 1.10')
    # 2b. a carrier FAIL at three seeds stops the extra seeds for every carrier of that sweep: the carriers that passed are re-run on six seeds
    for k in [k for k in list(D_) if k.startswith('P')]:
        ok = tuple(c for c, q in D_[k]['carriers'].items() if q['least_m'] >= 0)
        if ok and len(D_[k]['seeds']) < len(SEEDS6):
            q = D_[k]['port']; run_route('SIX_'+k, dport(G, q['alpha'], q['D'], q['x']), k, which=ok, always6=True)
    best = max([k for k in D_ if k.startswith('P')], key=lambda k: (D_[k]['least_m'], -abs(D_[k]['port']['alpha']-210.0)))
    res['best_route'] = best; bp = dict(D_[best]['port']); bport = dport(G, bp['alpha'], bp['D'], bp['x'])
    # 3. failure tree: each ALT-2 SP-12 fault left in its corridor as an obstacle; static gap to the SP-13 -> district route and a sweep (U, S)
    route = route_district(e13, G, bport); R = np.array([p for _, p in route]); dense = [R[0]]
    for a_, b_ in zip(R, R[1:]):
        n = max(1, int(np.linalg.norm(b_-a_)/0.05)); dense += [a_+(b_-a_)*k/n for k in range(1, n+1)]
    dense = np.array(dense); FT = res.setdefault('failure_tree', {})
    obs = obstacle_poses(v12); up = np.asarray(v12['u'])*-1.0
    obs['rescuer_down_in_duct'] = dict(car=BODY, head=np.array(P(duct_x_at(v12, 1.10), 1.10))+v12['u']*BODY['length']/2, axis=up, roll=0.0,
                                       desc='incapacitated rescuer (capsule r 0.25 m, 1.25 m) lying along the ALT-2 duct axis at r 1.10')
    obs['rescuer_down_on_axis_landing'] = dict(car=BODY, head=np.array((v12['duct']['xe']-0.6, 0.0, 0.0)), axis=np.array((1.0, 0.0, 0.0)), roll=0.0,
                                               desc=f"incapacitated rescuer on the bore axis at the ALT-2 landing (X {v12['duct']['xe']-0.6:.2f}-{v12['duct']['xe']+0.65:.2f})")
    for k, q in obs.items():
        if k in FT:
            continue
        car = q['car'] if isinstance(q['car'], dict) else h3.CARRIERS[q['car']]; a_, b_, ro = obstacle_axis(dict(q, car=car))
        A_ = np.linspace(a_, b_, 30); gap = float(np.min(np.linalg.norm(A_[:, None, :]-dense[None, :, :], axis=2)))-ro-rS
        reach = gap-(h3.STAFF_REACH_M+h3.STAFF_R_M)
        sw = run_route(f'FT_{k}', bport, k, diffs=[body_solid(car, q['head'], q['axis'], q['roll'])], which=('U', 'S'))
        FT[k] = dict(desc=q['desc'], obstacle_x=[round(float(min(a_[0], b_[0])), 2), round(float(max(a_[0], b_[0])), 2)], static_gap_to_route_envelope_m=round(gap, 3),
                     static_gap_beyond_rescuer_reach_m=round(reach, 3), sweep_key=f'FT_{k}', U=sw['carriers']['U']['least_m'], S=sw['carriers']['S']['least_m'], least_m=sw['least_m']); save()
    FT['logic'] = {
        'SP-12 exit closure jammed shut': 'no shared closure or volume with the SP-13 -> district route: no effect (the ALT-2 corridor and its closure are aft of X 102.1)',
        'SP-12 exit closure jammed open': 'SP-12 is no longer isolable from the trunk; a later SP-12 leak depressurizes the trunk AND the extension unless a closure separates them (see isolation): YES (pressure) without it',
        'SP-12 pressure loss, closure open (exit in use)': 'trunk + extension depressurize together, with the SP-13 -> district crossing in that volume, unless the extension is isolated: YES (pressure) without it',
        'SP-12 pressure loss, closure shut': 'isolated by the SP-12 exit closure, the SP-11 plug and the SP-12/SP-13 partition (reverse loads OPEN): no',
        'debris / smoke': 'no debris envelope; ventilation isolation not modelled: OPEN'}
    # 4. outer (trunk-side) SP-13 leaf access with the ALT-2 carrier S at its forward-most in-bore pose (head at the duct mouth, tail up the duct)
    if 'outer_leaf_access' not in res:
        q = obstacle_poses(v12)['stuck_in_duct_mouth']; O, X, T, Rn = frame13(e13)
        obj, w = walls_c(ctx, fx, [exit_solid(e13)]+list(v12['unions']), leaf_d+[body_solid(h3.CARRIERS['S'], q['head'], q['axis'], q['roll'])], sp12=True, sp13=True, fl13=fl13)
        rel = O-Rn*WHEEL_PROUD_M; cp = corridor_points(v12, h3.CARRIERS['S']); dmin = float(np.min(np.linalg.norm(cp-rel, axis=1)))-rS
        res['outer_leaf_access'] = dict(with_alt2_S_in_duct_mouth=op_retest(w, rel, plane_side(O, Rn, hi=-WHEEL_PROUD_M)), release_to_alt2_corridor_surface_m=round(dmin, 3),
                                        reach_zone_m=OP_REACH_M+OP_R_M, corridor_inside_reach_zone=bool(dmin < OP_REACH_M+OP_R_M), a177_n2fwd45_m=-0.021, empty_extension_m=0.135)
        bpy.data.objects.remove(obj); save()
    # 5. pressure isolation and onward ways (geometry only)
    res['isolation'] = isolation(ctx, G, bport, v12, e13, dense); save()
    return res


def isolation(ctx, G, port, v12, e13, dense):
    s = ctx.s; rS = h3.CARRIERS['S']['radius']; env = corridor_env(v12, rS); e0, e1 = sp13_duct_wall_edges(ctx, e13); tr = s['crew_transfer']['trunk_clear_radius_m']
    w = s['crew_transfer']['passage_wall_m']; inb = dense[np.hypot(dense[:, 1], dense[:, 2]) < tr]
    route_aft = float(inb[:, 0].min())-rS; port_aft = port['x']-port['D']/2-w
    lo = env['with_rescuer_forward_end_x']; hi = min(route_aft, port_aft, e0); L0 = he.trunk_ladder(s)
    win = dict(from_x=lo, to_x=round(hi, 3), length_m=round(hi-lo, 3), limited_by=min((('SP-13 -> district route envelope (aft-most, carrier S)', route_aft), ('district port aft edge', port_aft),
                                                                                        ('SP-13 duct on the trunk wall (aft edge)', e0)), key=lambda t: t[1])[0],
               trunk_forward_end_x=EXT_AFT_X, serv002_district_hatch='SERV-002 option A lists a "district hatch at the trunk end (seats from the trunk side)" at X 102.45, inside this window',
               ladder_conflict=f'the L1-A ladder (stiles r 0.64, arrest rail, rungs) runs continuously from X {L0["floor"]:.2f} to {LADDER_TOP_X} through the whole window (A171 extension, '
                               'A179 CB2J6): a transverse closure across the 1.6 m bore anywhere in it cuts both stiles and the rail = a NEW LADDER BREAK (excluded by 15!A171 / A179) unless '
                               'the ladder passes the closure by a means not studied here (OPEN)')
    # the district port: the only free-space connection between the workshop and the bore in option A
    face_gap = G['d']-(tr+w)
    dp = dict(port_tube_r=[tr+w, port['r_face']], port_tube_length_m=round(port['r_face']-(tr+w), 3), workshop_inner_face_to_extension_wall_m=round(face_gap, 3),
              separates='YES (geometry): in option A the workshop joins the bore only through the district port tube, so a closure seated in that tube separates the workshop '
                        '(and the cell behind it, which has only a sealed pass-through) from the extension, the trunk and SP-12. It does NOT isolate the extension (X 102.45-107.4), '
                        'which SP-13 crosses (duct mouth -> port, about 1.6 m across the bore) and which is one volume with the trunk where the ALT-2 corridor lands',
              closure='seat side, leaf, dogs, equalization, rating: OPEN (none assumed)')
    # onward: what the district touches (shell to shell), from the SERV-003 / SERV-002 elements
    R = G['R']; ws_el = ed.box_el('workshop', G['W']); wp = np.array(ed.samples(ws_el)[::3]); rf = he.refuge_station(s)
    dx = np.maximum.reduce([rf['cavity_x0']-wp[:, 0], np.zeros(len(wp)), wp[:, 0]-rf['cavity_x1']]); dr = np.maximum(np.hypot(wp[:, 1], wp[:, 2])-rf['pressure'], 0.0)
    near = {'refuge annulus (pressure shell)': round(float(np.min(np.hypot(dx, dr))), 2)}
    for q in ct.stationary(s):
        if q['name'] in ('Crew_Trunk',):
            continue
        a_, b_ = np.array(q['points'][0]), np.array(q['points'][1]); ax = b_-a_; Ln = float(np.linalg.norm(ax)); ax /= Ln; d_ = wp-a_; t_ = np.clip(d_@ax, 0, Ln)
        near[q['name']] = round(float(np.min(np.linalg.norm(d_-np.outer(t_, ax), axis=1)))-q['radius'], 2)
    eva, br = ed.eva_elements(s, ctx.data, ctx.lead)
    for e in eva:
        near[e['name']] = round(pts_gap(wp, np.array(ed.samples(e)[::4])), 2)
    return dict(transverse_window=win, district_port_closure=dp, workshop_shell_to=near,
                district_interfaces=['district port (workshop port) hatch: to the extension only', 'cell pass-through (sealed, no crew entry while running)', 'SP-52 service hatch (non-habitable, robot first)'],
                onward='NONE without the trunk: in option A (studied) the workshop/cell/SP-52 group connects to the rest of the ship only through the district port into the extension, and the '
                       'extension only through the trunk; option B (corridor B, EVA3_REPORT 12.4) also leaves from a trunk port (X ~101.85, 240 deg). The Dock_Primary "bypass" of EVA3_REPORT 12.3 '
                       'is the ladder bridge across the dock mouth INSIDE the trunk, not a pressure path; the docked vehicle (if any) and the storm refuge open off the trunk aft of the ALT-2 '
                       'landing. A trunk-independent way onward from the district (or the district as a refuge in its own right: life support, consumables, comms, duration) is OPEN; '
                       'no new pressure path is drawn here',
                status='GEOMETRY ONLY; isolation hardware, loads and ratings OPEN')


# ---------------------------------------------------------------------------------------------------------------------------------
# ladder (pure geometry with the A179 candidate)

def run_o13c_ladder(ctx, out, A2):
    s = ctx.s; LS = ctx.LS; Lo = ctx.Lo; vb = A2['variants'][A2['best']]; res = {}
    vs_ = {'ALT2_aft30_dx+0.0': alt2_variant(30.0, 0.0), A2['best']: alt2_variant(vb['psi_deg'], vb['dxa_m'])}
    ops_b = {n: (x, th, r) for n, x, th, r in he.openings(s)}
    for vn, v in vs_.items():
        rim = duct_rim(v); kd = KDTree(len(rim))
        for i, p in enumerate(rim):
            kd.insert(Vector(p), i)
        kd.balance(); R = {}
        Lo2 = dict(Lo, sp12_exit=dict(name=vn, kind='oblique', D=v['D'], psi_deg=v['psi_deg'], wall_x=v['wall_x']))
        for al in PORT_ALPHAS:
            for cn in ('CB2J6', 'CB2J6DP'):
                c = LS.CANDS[cn]; g = LS.geometry(s, c, al, Lo2); lad = LS.Lad(s, c, al); xs = np.arange(lad.floor, LADDER_TOP_X+1e-9, 0.01)
                memb = []
                for ln, (Pp, rr) in lad.lines(xs).items():
                    memb.append((ln, Pp, rr))
                for x, A_, B_, pts in lad.rung_pts():
                    memb.append(('rung', pts, np.full(len(pts), lad.r)))
                for st, x, Pp in lad.bracket_segs():
                    memb.append(('bracket', Pp, np.full(len(Pp), lad.r*.7)))
                bg = min((float(np.min(bore_gap(v, Pp, rr))), ln) for ln, Pp, rr in memb)
                rg = min((min(kd.find(Vector(p))[2] for p in Pp[::3])-float(np.max(rr)), ln) for ln, Pp, rr in memb)
                br_ = [(float(np.min([kd.find(Vector(p))[2] for p in Pp[(Pp[:, 0] >= 98.54) & (Pp[:, 0] <= 100.26)]] or [9.0]))-float(np.max(rr)), ln) for ln, Pp, rr in memb]
                R[f'{cn}@{int(al)}'] = dict(ladder_least_m=g['least_ladder_m'], no_new_ladder_break=g['no_new_ladder_break'], lines={k: q['least_m'] for k, q in g['lines'].items()},
                                            lines_limit={k: q['opening'] for k, q in g['lines'].items()}, rungs=g['rungs']['least_m'], brackets=g['brackets']['least_m'],
                                            alt2_bore_gap_m=None if bg[0] == math.inf else round(bg[0], 3), alt2_bore_note='inf = every ladder member is on the far side of the axis from the duct (az 50 vs 267-303 deg)',
                                            alt2_rim_min_m=round(rg[0], 3), alt2_rim_member=rg[1], bridge_members_to_alt2_rim_m=round(min(b[0] for b in br_), 3))
        # dock bridge window: the 0.20 m-margin gap at X 99.4 on each built ladder line, with and without the ALT-2 opening (bore rule, not the circle)
        Gl = ladder_geom(s, 285.0); dock = {}
        for ln, (rho, ang, rr) in Gl['lines'].items():
            gaps = merge_gaps(line_blocks(rho, ang, [tuple(o) for o in he.openings(s)], 0.2), Gl['floor'], LADDER_TOP_X); d0 = [g_ for g_ in gaps if g_[0] <= 99.4 <= g_[1]]
            xs = np.arange(98.0, 102.5, 0.005); Pp = np.stack([xs, rho*np.cos(ang)*np.ones_like(xs), rho*np.sin(ang)*np.ones_like(xs)], 1); hit = bore_gap(v, Pp, rr) < 0.2
            dock[ln] = dict(dock_gap_x=list(d0[0][:2]) if d0 else None, dock_gap_m=round(d0[0][1]-d0[0][0], 3) if d0 else 0.0, alt2_blocks_line_at_0_20=bool(hit.any()))
        # hoist guide line vs the ALT-2 opening, and the opening's ligaments to the built openings on the wall
        xs = np.arange(he.trunk_ladder(s)['floor'], HOIST_GUIDE['x1'], 0.005); a = math.radians(HOIST_GUIDE['deg'])
        Pg = np.stack([xs, HOIST_GUIDE['rho']*math.cos(a)*np.ones_like(xs), HOIST_GUIDE['rho']*math.sin(a)*np.ones_like(xs)], 1); gg = bore_gap(v, Pg, ROD_R_M)
        blocked = xs[gg < 0.2]; guide_spans = he.clear_spans(s, HOIST_GUIDE['rho'], a, he.trunk_ladder(s)['floor'], HOIST_GUIDE['x1'], margin=0.2)
        lig = {}
        for n, (x, th, r) in ops_b.items():
            wr = wall_rim(x, th, r)
            if len(wr):
                lig[n] = round(pts_gap(rim, wr), 3)
        res[vn] = dict(by_candidate=R, dock_window=dock, accepted_bridge_m=BRIDGE_ACCEPTED_M, opening_x=[round(float(rim[:, 0].min()), 3), round(float(rim[:, 0].max()), 3)],
                       hoist_guide=dict(line=HOIST_GUIDE, least_bore_gap_m=round(float(np.min(gg)), 3), blocked_x_at_0_20=[round(float(blocked.min()), 2), round(float(blocked.max()), 2)] if len(blocked) else None,
                                        built_clear_spans_0_20=[[round(p_, 2) for p_ in sp] for sp in guide_spans], rim_min_m=round(min(KDTree_find(kd, p) for p in Pg[::4])-ROD_R_M, 3)),
                       wall_ligament_to_openings_m=lig, note='ligament = least distance between the ALT-2 rim and each built opening rim on the trunk wall (r 0.80); Crew_Connector_Airlock_EVA '
                                                            '(the built 0.90 m SP-12 branch at X 101.85, az 50) merges with it by construction (ALT-2 is an N2 duct from under the same chamber)')
    return res


def KDTree_find(kd, p):
    return kd.find(Vector(tuple(float(x) for x in p)))[2]


# ---------------------------------------------------------------------------------------------------------------------------------
# stills (at most three) and segments / merge

def render_o13c(ctx, out, S13, A2, D):
    e13, fl13, leaf = sp13_parts(S13); G = workshop_geom(ctx); made = []
    vb = A2['variants'][A2['best']]; v = alt2_variant(vb['psi_deg'], vb['dxa_m']); bp = D['routes'][D['best_route']]['port']; port = dport(G, bp['alpha'], bp['D'], bp['x'])
    def pose_obj(cid, q, col, cars):
        car = cars[cid]
        if car['shape'] == 'box':
            vs, fs = h3.box_mesh(h3.boxes(car, q['head'], q['axis'], q['roll']), 0.0); me = bpy.data.meshes.new(cid); me.from_pydata(vs, [], fs); ob = ex.link(me, cid)
        else:
            p0 = np.asarray(q['head'])+np.asarray(q['axis'])*car['radius']; p1 = np.asarray(q['head'])+np.asarray(q['axis'])*(car['length']-car['radius']); ob = h3.prim_cyl(tuple(p0), tuple(p1), car['radius'])
        m = bpy.data.materials.new(cid); m.diffuse_color = col; ob.data.materials.append(m); return ob
    def shot(obj, extras, name, centre, scale):
        sc = bpy.context.scene; keep = [o for o in bpy.data.objects if not o.hide_render and o is not obj and o not in extras]
        for o in keep:
            o.hide_render = True
        mat = bpy.data.materials.new('free'); mat.diffuse_color = (.3, .6, .9, 1); obj.data.materials.append(mat)
        cam = bpy.data.objects.new('CAM_O13C', bpy.data.cameras.new('CAM_O13C')); sc.collection.objects.link(cam); sc.camera = cam
        sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'; sc.display.shading.show_xray = True; sc.display.shading.xray_alpha = 0.35
        sc.render.resolution_x, sc.render.resolution_y = 1400, 800
        ax = axes_at(math.radians(50.0)); look = Vector((-ax[1][0], -ax[1][1], -ax[1][2])); up = Vector(ax[2]); z = -look; x = up.cross(z).normalized(); y = z.cross(x)
        cam.rotation_euler = Matrix((x, y, z)).transposed().to_euler(); cam.data.type = 'ORTHO'; cam.data.ortho_scale = scale; cam.data.clip_start = .1; cam.data.clip_end = 80
        cam.location = Vector(centre)-look*30.0; sc.render.filepath = str(out/f'{name}.png'); bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(cam); sc.display.shading.show_xray = False
        for o in keep:
            o.hide_render = False
        return f'{name}.png'
    outs = []; cars = carriers(ctx)
    # 1. ALT-2 best: free space (frames broken round the opening) with the worst carrier S pose
    obj, w = walls_c(ctx, ctx.fx_nl, v['unions'], [], sp12=True, sp13=False)
    q = vb['sweep']['carriers']['S']; ex_ = [pose_obj('S', q, (1.0, .5, .1, 1), cars)]
    outs.append(shot(obj, ex_, 'o13c_alt2_best_S', (100.6, 0.0, 0.0), 9.0)); [bpy.data.objects.remove(o) for o in ex_]; bpy.data.objects.remove(obj)
    # 2. SP-13 -> district: worst S and U poses of the best route
    obj, w = walls_c(ctx, ctx.fx_nl, [exit_solid(e13), port['solid'], ws_solid(G)], list(leaf_solids(e13, *leaf, PARK_DEG)), sp12=False, sp13=True, fl13=fl13)
    sw = D['routes'][D['best_route']]['carriers']; ex_ = [pose_obj('S', sw['S'], (1.0, .5, .1, 1), cars), pose_obj('U', sw['U'], (.2, .8, .3, 1), cars)]
    outs.append(shot(obj, ex_, 'o13c_sp13_district_route', (105.0, 0.0, 0.0), 10.0)); [bpy.data.objects.remove(o) for o in ex_]; bpy.data.objects.remove(obj)
    # 3. the whole layout: ALT-2 stuck carrier (red) on the trunk landing and the SP-13 -> district route S pose (orange)
    obj, w = walls_c(ctx, ctx.fx_nl, [exit_solid(e13), port['solid'], ws_solid(G)]+list(v['unions']), list(leaf_solids(e13, *leaf, PARK_DEG)), sp12=True, sp13=True, fl13=fl13)
    qo = obstacle_poses(alt2_variant(30.0, 0.0))['stuck_on_axis_trunk_landing']
    ex_ = [pose_obj('S', dict(head=qo['head'], axis=qo['axis'], roll=0.0), (.9, .15, .15, 1), cars), pose_obj('S', sw['S'], (1.0, .5, .1, 1), cars)]
    outs.append(shot(obj, ex_, 'o13c_independence_overview', (102.3, 0.0, 1.0), 14.0)); [bpy.data.objects.remove(o) for o in ex_]; bpy.data.objects.remove(obj)
    return [str((out/o).relative_to(ROOT)) for o in outs]


def o13c_segments(A2, D, Lr):
    out = []; ALL = ALL_STATES
    def carseg(prefix, route, variant, case, sw, note=''):
        for cid, q in sw['carriers'].items():
            out.append(seg(f'{prefix}-{cid}', route, ALL, variant, f'{CAR_NAMES.get(cid, cid)}: {case}', q['least_m'], [CAR_NAMES.get(cid, cid), 'body', 'rescuers' if cid != 'U' else 'self-propelled', f'seeds {sw["seeds"]}'],
                           q['seed_spread_m'], q['nearest'], f'body {q["body_least_m"]}, rescuers {q["rescuers_least_m"]}, limiting zone {q["zone"]}. {note}'.strip()))
    if A2:
        for k, r in A2['variants'].items():
            carseg(f'A177C-ALT2-{k}', 'SP-12 ALT-2 corridor (A177C)', f'{k} (frames broken round the opening, PROTOTYPE)', 'chamber -> SP-12 -> aft duct -> built trunk to X ~97, CB2J6 ladder and bridge present', r['sweep'],
                   f'vehicle {r["vehicle"]["status"]}; spine-core cut {r["spine_core_cut_x_m"]} m (HOLD); corridor in bore {r["envelope"]["corridor_x_in_bore"]}, with rescuer to X {r["envelope"]["with_rescuer_forward_end_x"]}.')
        carseg('A177C-ALT2-ASBUILT-FRAME', 'SP-12 ALT-2 corridor (A177C)', 'ALT2_aft30_dx+0.0, frame as built', 'same rig, Trunk_Fit_Frame_13_1 left across the opening', A2['reference_frame_as_built'])
        h = A2['hoist']
        for an, r in h['anchors'].items():
            z = r['line_by_zone']
            out.append(seg(f'A177C-ALT2-HOIST-{an.split(",")[0].split()[0]}', 'SP-12 ALT-2 corridor (A177C)', ['locked_1.5g'], f'{h["variant"]}, anchor {an}', 'lowering line from the anchor to the head (zones H, D, T) vs walls',
                           min(q['to_walls_m'] for q in z.values()), [f'zone {k}' for k in z], None, min(z.values(), key=lambda q: q['to_walls_m'])['walls_nearest'],
                           f'by zone {({k: q["to_walls_m"] for k, q in z.items()})} (negative = the straight line leaves the free space: deflector needed); vs SP-13 S envelope {min(q["to_sp13_S_envelope_m"] for q in z.values())} m; drop {h["centre_drop_m"]} m, rise {h["centre_rise_m"]} m.'))
        out.append(seg('A177C-ALT2-HOIST-LOADS', 'SP-12 ALT-2 corridor (A177C)', ['locked_1.5g'], h['variant'], f'lowering {h["centre_drop_m"]} m: anchor / line / brake loads', None, [], None, None, h['loads'], 'OPEN'))
    if D:
        for k, sw in D['routes'].items():
            if k.startswith('P'):
                carseg(f'A177C-SP13DIST-{k}', 'SP-13 exit into the L1-A district (A177C)', f'district port {sw["port"]["alpha"]} deg, {sw["port"]["D"]:.2f} m at X {sw["port"]["x"]}, ladder {STILE_FOR[float(sw["port"]["alpha"])]}',
                       'SP-13 -> 45 deg exit -> landing -> across the bore -> district port -> workshop', sw)
        for k, f in D['failure_tree'].items():
            if k == 'logic':
                continue
            carseg(f'A177C-FT-{k}', 'SP-13 exit into the L1-A district (A177C)', f'ALT-2 SP-12 fault: {k}', f'SP-13 -> district route past the fault ({f["desc"]})', D['routes'][f['sweep_key']],
                   f'static gap fault -> route envelope {f["static_gap_to_route_envelope_m"]} m.')
            out.append(seg(f'A177C-FT-{k}-STATIC', 'SP-13 exit into the L1-A district (A177C)', ALL, k, 'static gap: fault obstacle (axis + envelope radius) to the S route envelope, less a rescuer reach zone 0.95 m',
                           f['static_gap_beyond_rescuer_reach_m'], ['obstacle envelope', 'S envelope r 0.43', 'rescuer reach 0.95'], None, None, f'obstacle X {f["obstacle_x"]}; raw gap {f["static_gap_to_route_envelope_m"]} m.'))
        o = D['outer_leaf_access']['with_alt2_S_in_duct_mouth']
        out.append(seg('A177C-SP13-OUTER-LEAF-ACCESS-ALT2', 'SP-13 exit into the L1-A district (A177C)', ALL, 'ALT-2 carrier S jammed in its duct mouth (forward-most in-bore pose)', 'trunk-side operation of the SP-13 leaf',
                       o['least_m'], ['operator torso r 0.25 m', f'seeds {o["seeds"]}'], None, o['nearest'], f'release to ALT-2 corridor surface {D["outer_leaf_access"]["release_to_alt2_corridor_surface_m"]} m (A177 N2 fwd45: -0.021).'))
        iso = D['isolation']; tw = iso['transverse_window']
        out.append(seg('A177C-ISO-DISTRICT-PORT', 'SP-13 exit into the L1-A district (A177C)', ALL, 'closure seated in the district port tube', 'separates the workshop from the extension / trunk / SP-12', None, [], None, None, iso['district_port_closure']['separates'], 'OPEN'))
        out.append(seg('A177C-ISO-TRANSVERSE', 'SP-13 exit into the L1-A district (A177C)', ALL, 'transverse closure between the ALT-2 corridor and the extension', f'free X window {tw["from_x"]}-{tw["to_x"]}', tw['length_m'],
                       ['ALT-2 corridor + rescuer', tw['limited_by']], None, None, tw['ladder_conflict'], 'OPEN'))
        out.append(seg('A177C-ONWARD', 'SP-13 exit into the L1-A district (A177C)', ALL, 'L1-A district (option A)', 'way onward from the district without the trunk', None, [], None, None, iso['onward'], 'OPEN'))
    if Lr:
        for vn, r in Lr.items():
            for k, q in r['by_candidate'].items():
                out.append(seg(f'A177C-LADDER-{vn}-{k.replace("@", "-P")}', 'L1-A ladder with ALT-2 (A177C)', ALL, f'{k.split("@")[0]}, port {k.split("@")[1]} deg, SP-12 {vn}', 'ladder members vs every opening (A179 rule) + ALT-2 rim',
                               min(q['ladder_least_m'], q['alt2_rim_min_m']), ['stiles', 'rail', 'rungs', 'brackets', 'ALT-2 rim'], None, None,
                               f'no new ladder break {q["no_new_ladder_break"]}; ALT-2 rim {q["alt2_rim_min_m"]} m ({q["alt2_rim_member"]}); bridge members to ALT-2 rim {q["bridge_members_to_alt2_rim_m"]} m.',
                               None if q['no_new_ladder_break'] else 'FAIL'))
            hg = r['hoist_guide']
            out.append(seg(f'A177C-HOIST-GUIDE-{vn}', 'L1-A ladder with ALT-2 (A177C)', ALL, vn, 'HUM-003 hoist guide line (r 0.72 @105 deg) vs the ALT-2 bore', hg['least_bore_gap_m'], ['guide line', 'ALT-2 bore'], None, None,
                           f'blocked at the 0.20 m margin over X {hg["blocked_x_at_0_20"]}; built guide spans (0.20) {hg["built_clear_spans_0_20"]}.'))
            out.append(seg(f'A177C-DOCK-{vn}', 'L1-A ladder with ALT-2 (A177C)', ALL, vn, 'ALT-2 opening rim vs Dock_Primary mouth on the trunk wall', r['wall_ligament_to_openings_m'].get('Crew_Connector_Dock_Primary'), ['rims on the wall'], None, None,
                           f'ligaments {r["wall_ligament_to_openings_m"]}; dock window per line {({k: q["dock_gap_m"] for k, q in r["dock_window"].items()})} (accepted {BRIDGE_ACCEPTED_M}).'))
    return out


def merge_o13c(A2, D, Lr, renders, segs):
    jf = ROOT/'references/p1_eva_sp13_l1a.json'; d = json.loads(jf.read_text())
    d[O13C_TAG] = dict(owner_refs=['15!A177 OWN-RES-B2-2026-10-13 (I177: protect SP-13 independent exit in all scenarios)', '15!A136 DIST-004', '15!A158 DIST-006', '15!A171 DIST-L1-STEP', '15!A179 OWN-RES-D1'],
                       status='NONCANON PROTOTYPE, disposable geometry; zero canonical geometry change; no pressure-shell edit; spine-core cut, closures, loads and ratings HOLD / OPEN',
                       direction='SP-13 exits sideways into the L1-A district through the district port; SP-12 rerouted to ALT-2 (N2 aft) so its corridor stays in the built trunk',
                       band=BAND, seeds_worst_case=list(SEEDS6), constants=dict(alt2_psis=list(ALT2_PSIS), alt2_dxa=list(ALT2_DXA), frame_pad_m=FRAME_PAD_M, workshop_deg=WS_DEG, district_port_x=DP_X,
                                                                                  dp110_x=DP110_X, stile_for={str(int(k)): v for k, v in STILE_FOR.items()}),
                       alt2=A2, district=D, ladder=Lr, renders=renders)
    jf.write_text(json.dumps(d, indent=1, default=str)+'\n')
    sf = ROOT/'references/p1_access_seg_sp13_l1a.json'; d = json.loads(sf.read_text())
    d['segments'] = [g for g in d['segments'] if not g['id'].startswith('A177C-')]+segs
    if 'A177C' not in d['study']:
        d['study'] += ' + owner 2026-10-13c SP-13 exit into the L1-A district, ALT-2 SP-12 (A177C-* segments)'
    sf.write_text(json.dumps(d, indent=1)+'\n')


def main_o13c(out, parts):
    out.mkdir(parents=True, exist_ok=True); ctx = o13c_ctx()
    S13 = json.loads((ROOT/'references/p1_eva_sp13_l1a.json').read_text())['owner_2026_10_13']['sp13_closure']
    rd = lambda n: json.loads((out/n).read_text()) if (out/n).exists() else None
    A2 = run_o13c_alt2(ctx, out, S13) if 'alt2' in parts else rd('o13c_alt2.json')
    D = run_o13c_district(ctx, out, S13) if 'district' in parts else rd('o13c_district.json')
    Lr = None
    if 'ladder' in parts:
        Lr = run_o13c_ladder(ctx, out, A2); (out/'o13c_ladder.json').write_text(json.dumps(Lr, indent=1, default=str)+'\n')
    Lr = Lr or rd('o13c_ladder.json')
    renders = rd('o13c_renders.json')
    if 'render' in parts:
        renders = render_o13c(ctx, out, S13, A2, D); (out/'o13c_renders.json').write_text(json.dumps(renders)+'\n')
    if 'merge' in parts:
        segs = o13c_segments(A2, D, Lr); merge_o13c(A2, D, Lr, renders, segs); print('WF_O13C merged', len(segs), 'segments', flush=True)
    print('WF_O13C done', parts, flush=True)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); ap.add_argument('--parts', default='sp13,ladder,sp52'); ap.add_argument('--sp13-raw', default=None); ap.add_argument('--scan', default=None); ap.add_argument('--shard', default='0/1')
    ap.add_argument('--o13', default=None, help='owner 2026-10-13 (15!A170/A171) extensions: comma list of sp12, sp13, l1a, merge')
    ap.add_argument('--o13b', default=None, help='owner 2026-10-13b (15!A176-A178) extensions: comma list of b1, b2, c1, merge')
    ap.add_argument('--o13c', default=None, help='owner 2026-10-13c (SP-13 exit into the L1-A district, ALT-2 SP-12): comma list of alt2, district, ladder, render, merge')
    a = ap.parse_args(argv); o = a.out if a.out.is_absolute() else ROOT/a.out
    if a.o13c:
        main_o13c(o, a.o13c.split(','))
    elif a.o13b:
        main_o13b(o, a.o13b.split(','))
    elif a.o13:
        main_o13(o, a.o13.split(','))
    else:
        main(o, a.parts.split(','), a.sp13_raw, a.scan, tuple(int(v) for v in a.shard.split('/')))
