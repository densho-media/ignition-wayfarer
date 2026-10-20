"""EVA-002 suited access: the four movement envelopes, the shirt-sleeve versus suited route classification, and the SP-11 door and
chamber study with the SP-12 / SP-13 rooms (S&E 43 EVA-040..044, 44 EVA2-002/003, 45 G-01..G-07; docs/EVA.md). Standard library only.

Inputs: the as-built suit hulls of `references/p1_eva_envelopes.json` (validation/eva_fit.py measures them in Blender: the convex hull of
the visible suit, PLSS, tether reels, hooks and tool, per access pose) and data/eva_suit.toml [access], [airlock_study], [sp12], [sp13].
Nothing here edits the ship: the candidates are disposable study geometry on the existing PROTOTYPE airlock axis, and every result is a
geometric readback, never a certification (EVA-055). The Blender side (validation/eva_airlock_study.py) measures the candidates and rooms
against the saved vehicle and renders them.

Envelope classes (EVA-041):
  UNSUITED            the shirt-sleeve body; the legacy 0.70 m route-sweep key is this class's route-control envelope (PROTOTYPE)
  EVA_SUITED          the pressurized suit with PLSS, arms along the body (passage and chamber standing)
  EVA_OPERATIONAL     the suit moving: hatch passage with the hands ahead, panel and handle reach, tools and tether reels
  RESCUE              an unresponsive suited casualty (neutral body posture) and a rescuer holding it

Chamber frame (human_entry.world / local): a = distance from the ship axis along the airlock's outward radial; across the axis a point
sits at rho, phi. Bodies stand along the axis, head outboard toward the outer hatch.

  python3 src/wayfarer/eva_access.py [--out references/p1_eva_access.json]
"""
import argparse
import json
import math
import random
from pathlib import Path

import eva_suit
import hull_geometry
import human_entry
import spec

ROOT = Path(__file__).resolve().parents[2]
ENVELOPES = ROOT/'references/p1_eva_envelopes.json'
OUTPUT = ROOT/'references/p1_eva_access.json'


# ---------------------------------------------------------------------------------------------------------------------------------
# Plane geometry

def enclosing_circle(pts):
    """Smallest circle (centre, radius) holding 2-D points (Welzl, iterative; deterministic order)."""
    P = sorted(set((round(x, 4), round(y, 4)) for x, y in pts)); random.Random(0).shuffle(P)    # expected linear time, reproducible
    def circ2(a, b):
        c = ((a[0]+b[0])/2, (a[1]+b[1])/2); return c, math.dist(a, c)
    def circ3(a, b, c):
        d = 2*(a[0]*(b[1]-c[1])+b[0]*(c[1]-a[1])+c[0]*(a[1]-b[1]))
        if abs(d) < 1e-12:
            return max((circ2(p, q) for p, q in ((a, b), (a, c), (b, c))), key=lambda t: t[1])
        ux = ((a[0]**2+a[1]**2)*(b[1]-c[1])+(b[0]**2+b[1]**2)*(c[1]-a[1])+(c[0]**2+c[1]**2)*(a[1]-b[1]))/d
        uy = ((a[0]**2+a[1]**2)*(c[0]-b[0])+(b[0]**2+b[1]**2)*(a[0]-c[0])+(c[0]**2+c[1]**2)*(b[0]-a[0]))/d
        return (ux, uy), math.dist((ux, uy), a)
    inside = lambda c, p: math.dist(c[0], p) <= c[1]+1e-9
    c = (P[0], 0.0)
    for i, p in enumerate(P):
        if inside(c, p):
            continue
        c = (p, 0.0)
        for j, q in enumerate(P[:i]):
            if inside(c, q):
                continue
            c = circ2(p, q)
            for r in P[:j]:
                if not inside(c, r):
                    c = circ3(p, q, r)
    return c


def rot2(p, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg)); return (p[0]*c-p[1]*s, p[0]*s+p[1]*c)


def tilt(v, ax, ay):
    """Rotate a body point about the body x then y axes (deg): a casualty turned for a door."""
    x, y, z = v; c, s = math.cos(math.radians(ax)), math.sin(math.radians(ax)); y, z = y*c-z*s, y*s+z*c
    c, s = math.cos(math.radians(ay)), math.sin(math.radians(ay)); x, z = x*c+z*s, -x*s+z*c
    return (x, y, z)


# ---------------------------------------------------------------------------------------------------------------------------------
# Envelopes (EVA-041)

def load_envelopes(path=ENVELOPES):
    return json.loads(Path(path).read_text()) if Path(path).exists() else None


def passage_circle(h, tilts=(0.0,)):
    """Clear diameter a pose needs to pass an aperture along its body axis (z): the smallest circle of its hull's projection, over the
    given tilts (the best one; a conscious crew member can turn, a rescuer can turn a casualty)."""
    best = None
    for ax in tilts:
        for ay in tilts:
            pts = [tilt(v, ax, ay)[:2] for v in h['verts']]; c, r = enclosing_circle(pts)
            if best is None or 2*r < best[0]:
                best = (2*r, ax, ay)
    return dict(diameter_m=round(best[0], 3), tilt_deg=[best[1], best[2]])


def hull_area(pts):
    """Area of the 2-D convex hull of points (monotone chain)."""
    P = sorted(set(pts))
    if len(P) < 3:
        return 0.0
    cross = lambda o, a, b: (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]); lo = []; hi = []
    for p in P:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    H = lo[:-1]+hi[:-1]; return abs(sum(H[i][0]*H[i-1][1]-H[i-1][0]*H[i][1] for i in range(len(H))))/2


def projected_area(h, n=12):
    """GEOMETRY READBACK for 45 H-06 (the owner releases it): the suit's silhouette area (its convex hull projected, an upper bound of the
    true silhouette) over view directions on a sphere: min, max and the directions. Not an absorbed-power input by itself (H-07 OPEN)."""
    out = []
    for i in range(n+1):
        el = -math.pi/2+math.pi*i/n
        for j in range(max(1, int(2*n*math.cos(el)))):
            az = 2*math.pi*j/max(1, int(2*n*math.cos(el))); d = (math.cos(el)*math.cos(az), math.cos(el)*math.sin(az), math.sin(el))
            e1 = (-math.sin(az), math.cos(az), 0.0); e2 = (-math.sin(el)*math.cos(az), -math.sin(el)*math.sin(az), math.cos(el))
            pts = [(round(sum(a*b for a, b in zip(v, e1)), 3), round(sum(a*b for a, b in zip(v, e2)), 3)) for v in h['verts']]
            out.append((hull_area(pts), [round(x, 3) for x in d]))
    lo = min(out); hi = max(out)
    return dict(status='GEOMETRY READBACK for 45 H-06 (convex silhouette, upper bound); not released', min_m2=round(lo[0], 3), min_dir_body=lo[1],
                max_m2=round(hi[0], 3), max_dir_body=hi[1])


def length(h):
    zs = [v[2] for v in h['verts']]; return max(zs)-min(zs)


def classes(s, env):
    """The four envelope classes per variant, with their measured passage diameters (m) and how each is used."""
    m = s['human_entry']['mannequin']; data = eva_suit.load(); tilts = data['airlock_study']['casualty_tilt_deg']; out = {}
    for k, v in env['variants'].items():
        out[k] = dict(
            UNSUITED=dict(route_control_m=m['suited_envelope_diameter_m'], measured_m=passage_circle(v['unsuited'])['diameter_m'],
                          use='interior induction (shirt-sleeve); the 0.70 m key keeps its legacy name (EVA-041)'),
            EVA_SUITED=dict(measured_m=passage_circle(v['chamber'])['diameter_m'], length_m=round(length(v['chamber']), 3),
                            projected_area=projected_area(v['chamber']),
                            use='SP-12 -> SP-11 -> exterior only (EVA-040)'),
            EVA_OPERATIONAL=dict(measured_m=passage_circle(v['hatch_pass'])['diameter_m'], length_m=round(length(v['hatch_pass']), 3),
                                 operate_m=passage_circle(v['operate'])['diameter_m'], use='hatch passage with the hands ahead; panel and handle work'),
            RESCUE=dict(casualty=passage_circle(v['casualty'], tilts), rescuer_m=passage_circle(v['rescue'])['diameter_m'],
                        use='an unresponsive suited crew member moved by a rescuer (EVA-054)'))
    return out


def route_access(s, fit, env_classes):
    """Each induction bottleneck by envelope class. The interior route is shirt-sleeve by owner direction (EVA-040): a suited class is
    NOT PERMITTED there whatever the geometry says; the geometry is still reported, a failed clearance is never hidden."""
    rows = []
    for b in next(iter(fit['variants'].values()))['bottlenecks']:
        D = b['clear_diameter_m']; row = dict(bottleneck=b['bottleneck'], clear_diameter_m=D, kind=b['kind'])
        legacy = s['human_entry']['mannequin']['suited_envelope_diameter_m']
        row['UNSUITED'] = 'CLEAR' if legacy <= D+1e-9 else 'BLOCKED'
        for k, c in env_classes.items():
            for cls, d in (('EVA_SUITED', fit['variants'][k]['envelope']['torso_circle_diameter_m']), ('EVA_OPERATIONAL', c['EVA_OPERATIONAL']['measured_m']),
                           ('RESCUE', c['RESCUE']['casualty']['diameter_m'])):
                geo = 'CLEAR' if d <= D-1e-9 else 'BLOCKED'
                row[f'{cls}.{k}'] = dict(geometry=geo, margin_m=round(D-d, 3), permitted='NOT A SUITED ROUTE (EVA-040)')
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------------------------------------------------------------
# SP-11 candidates (EVA-043/044)

def door(s, D):
    """The plug-leaf hardware of a clear aperture D, the docking port's family (human_entry): leaf, hinge and parking radii, the seat
    load at cabin pressure (80 kPa BASELINE x the leaf area: DERIVED, 45 P-01), and the hull penetration it implies."""
    h = s['human_entry']; rc = D/2; r_leaf = rc+h['hatch_leaf_overlap_m']; r_hinge = rc+h['hatch_frame_width_m']
    park = math.hypot(r_hinge+h['hatch_leaf_thickness_m'], r_leaf)+h['leaf_swing_clearance_m']
    cabin = eva_suit.load()['telemetry']['cabin_pressure_kpa']['value']
    return dict(clear_m=D, r_clear=rc, r_leaf=r_leaf, r_hinge=r_hinge, t=h['hatch_leaf_thickness_m'], frame_depth=h['hatch_frame_depth_m'],
                swing_depth_m=round(r_hinge+r_leaf, 3), park_radius_m=round(park, 3),
                seat_load_kn=round(cabin*math.pi*r_leaf**2, 1), seat_load_basis='cabin 80 kPa (BASELINE) x leaf area; DERIVED, not a structural release',
                hull_penetration_outside_m=round(D+2*(h['hatch_frame_width_m']+h['chamber_wall_m']), 3))


def placed(h, theta, shift, a_top):
    """A body hull standing on the chamber axis, head outboard: its (x, y) rotated by theta about the body axis and shifted across the
    chamber axis (the layouts' convention), its top at a_top. Returns chamber-local vertices (a, p, q) and outward planes (a rigid
    motion: the rotated normal keeps the offset plus its component along the translation)."""
    zmax = max(v[2] for v in h['verts']); da = a_top-zmax
    verts = [(da+v[2], *(c+s for c, s in zip(rot2((v[0], v[1]), theta), shift))) for v in h['verts']]; planes = []
    for n0, n1, n2, d in h['planes']:
        pn = rot2((n0, n1), theta); planes.append(((n2, pn[0], pn[1]), d+n2*da+pn[0]*shift[0]+pn[1]*shift[1]))
    return verts, planes


def outside(planes, pt):
    """A lower bound of the distance from pt to a convex hull (negative inside)."""
    return max(sum(a*b for a, b in zip(n, pt))-d for n, d in planes)


def clear_of(planes, pts, margin):
    """Whether every point keeps at least `margin` (lower bound) from the hull: a point is cleared as soon as one face plane shows it
    that far outside, so the outboard-facing planes are tried first."""
    order = sorted(planes, key=lambda q: -q[0][0])
    for x in pts:
        for (n0, n1, n2), d in order:
            if n0*x[0]+n1*x[1]+n2*x[2]-d >= margin:
                break
        else:
            return False
    return True


def pair_layout(hA, hB, margin, steps=12):
    """Two bodies side by side across the axis (B turned half a turn): the arrangement with the smallest enclosing radius whose
    projections along the side-by-side direction keep `margin` apart (a lower bound of their true gap)."""
    best = None
    for k in range(steps):
        th = 360.0*k/steps
        PA = [rot2((v[0], v[1]), th) for v in hA['verts']]; PB = [rot2((v[0], v[1]), th+180.0) for v in hB['verts']]
        ca = ((max(p[0] for p in PA)+min(p[0] for p in PA))/2, (max(p[1] for p in PA)+min(p[1] for p in PA))/2)
        cb = ((max(p[0] for p in PB)+min(p[0] for p in PB))/2, (max(p[1] for p in PB)+min(p[1] for p in PB))/2)
        sa = margin/2-min(p[0]-ca[0] for p in PA); sb = -margin/2-max(p[0]-cb[0] for p in PB)
        A = [(p[0]-ca[0]+sa, p[1]-ca[1]) for p in PA]; B = [(p[0]-cb[0]+sb, p[1]-cb[1]) for p in PB]
        c, r = enclosing_circle(A+B)
        if best is None or r < best['radius']:
            best = dict(theta=th, radius=r, centre=c, shift_a=(sa-ca[0]-c[0], -ca[1]-c[1]), shift_b=(sb-cb[0]-c[0], -cb[1]-c[1]))
    return best


def single_layout(h):
    c, r = enclosing_circle([(v[0], v[1]) for v in h['verts']]); return dict(theta=0.0, radius=r, centre=c, shift_a=(-c[0], -c[1]))


def leaf_sweep(dr, hinge_phi, a_hinge, n_ang=7, n_r=4, n_t=16):
    """Chamber-local samples (a, p, q) of the outer leaf swept from shut to 90 deg open into the chamber, hinged on the inboard face of
    the frame at rho = r_hinge, azimuth hinge_phi (the docking port's construction, human_entry.hinge)."""
    out = []; e2 = (math.cos(hinge_phi), math.sin(hinge_phi))
    for i in range(n_ang):
        ang = math.radians(90.0*i/(n_ang-1)); c, sn = math.cos(ang), math.sin(ang)
        for k in range(1, n_r+1):
            for j in range(n_t):
                t = 2*math.pi*j/n_t; x = dr['r_leaf']*k/n_r*math.sin(t); y = -dr['r_hinge']+dr['r_leaf']*k/n_r*math.cos(t)
                for z in (0.0, -dr['t']):
                    y2, z2 = y*c-z*sn, y*sn+z*c                           # rotate about the hinge axis: the free edge swings inboard (-a)
                    rho_e2 = dr['r_hinge']+y2; tang = x
                    out.append((a_hinge+z2, rho_e2*e2[0]-tang*e2[1], rho_e2*e2[1]+tang*e2[0]))
    return out


def chamber(s, f, dr, sets, margin, step, hinge_steps, floor_r):
    """Size one chamber for every occupancy in `sets` (each a list of (hull, theta, shift) standing head outboard, e.g. the routine pair
    and the rescue pairs): the clear radius they and the parked leaf need, then the shortest clear length that keeps every body of each
    set `margin` clear of the outer leaf's swing (one hinge azimuth for all sets, the best of those tried) and of both bulkheads.
    Returns the measured dimensions and the radial budget to the SP-12 floor (the inner leaf opens into SP-12)."""
    h = s['human_entry']; wall = h['chamber_wall_m']; clr = s['prototype']['mechanical_clearance_m']
    pts = []
    for hull, th, shift in (b for bodies in sets for b in bodies):
        pts += [(rot2((v[0], v[1]), th)[0]+shift[0], rot2((v[0], v[1]), th)[1]+shift[1]) for v in hull['verts']]
    R_body = max(math.hypot(*p) for p in pts)+margin
    R = human_entry.ceil_step(max(R_body, dr['park_radius_m']))
    span = R+wall; skin = min(hull_geometry.inner_radius_at(s, f['x']+k*span/4) for k in range(-4, 5))
    top = human_entry.floor_step(math.sqrt((skin-clr)**2-span**2)); a_out = top-wall; hinge_a = a_out-dr['frame_depth']
    best = None
    for k in range(hinge_steps):
        phi = 2*math.pi*k/hinge_steps; sweep = leaf_sweep(dr, phi, hinge_a)
        ok = lambda g: all(clear_of(placed(hull, th, shift, hinge_a-dr['t']-g)[1], sweep, margin) for bodies in sets for hull, th, shift in bodies)
        lo, hi = 0.0, 3.0
        if ok(0.0):
            hi = 0.0
        while hi-lo > step/2:                                  # bisect the shortest clear gap (the sweep only shrinks as the bodies move inboard)
            mid = (lo+hi)/2; lo, hi = (lo, mid) if ok(mid) else (mid, hi)
        gap = math.ceil(hi/step-1e-9)*step
        if best is None or gap < best['gap']:
            best = dict(gap=round(gap, 3), hinge_deg=round(math.degrees(phi), 1))
    L_body = max(length(hl) for bodies in sets for hl, _, _ in bodies)
    # clear length: outer frame and leaf, the measured gap to the body tops, the body, and margin to the inner frame
    L = human_entry.ceil_step(dr['frame_depth']+dr['t']+best['gap']+L_body+margin+dr['frame_depth'])
    a_in = a_out-L; bottom = a_in-wall
    node_floor = bottom-dr['frame_depth']-dr['t']-dr['swing_depth_m']-h['leaf_swing_clearance_m']   # the inner leaf opens into SP-12
    return dict(clear_radius_m=R, clear_diameter_m=round(2*R, 3), body_radius_m=round(R_body-margin, 3), clear_length_m=round(L, 3),
                outer_bulkhead_a_m=round(top, 3), inner_bulkhead_a_m=round(bottom, 3), inner_leaf_floor_a_m=round(node_floor, 3),
                leaf_face_a_m=round(hinge_a-dr['t'], 3), body_top_a_m=round(hinge_a-dr['t']-best['gap'], 3),
                sp12_floor_r_m=floor_r, radial_budget_m=round(node_floor-floor_r, 3), fits_radially=node_floor >= floor_r-1e-9,
                outer_leaf=best, volume_m3=round(math.pi*R*R*L, 2), hull_skin_m=skin,
                fitting_outside_m=round(2*(R+wall), 3), existing_fitting_outside_m=2*f['radius'])


def reach(dr, hull, theta, shift, a_top, leaf_a, limit_deg, arm):
    """Can the occupant's hand meet the outer leaf's handle from the unlatch position (helmet top `a_top`, under the shut leaf)? The
    handle goes where the operator's nearer shoulder is (a PROTOTYPE choice: anywhere on the leaf's chamber face, 0.10 m inside its rim).
    PASS when that shoulder is within the measured suited reach `arm`. The elevation from body-down is reported against the shoulder
    limit: above it the operator must pitch toward the hatch (by `pitch_needed_deg`) or the handle needs an extension (OPEN)."""
    j = hull['joints']; zmax = max(v[2] for v in hull['verts'])
    def T(v):
        p, q = rot2((v[0], v[1]), theta); return (a_top-(zmax-v[2]), p+shift[0], q+shift[1])
    rr = dr['r_leaf']-.10; out = []
    for side in ('r', 'l'):
        sh = T(j[f'shoulder_{side}']); rho = math.hypot(sh[1], sh[2]); k = min(1.0, rr/max(rho, 1e-9))
        handle = (leaf_a-.05, sh[1]*k, sh[2]*k); d = math.dist(sh, handle)
        elev = math.degrees(math.acos(max(-1.0, min(1.0, -(handle[0]-sh[0])/max(d, 1e-9)))))   # angle from body-down (-a)
        out.append(dict(side=side, handle_rho_m=round(math.hypot(handle[1], handle[2]), 3), distance_m=round(d, 3), reach_m=round(arm, 3),
                        elevation_deg=round(elev, 1), ok=d <= arm, pitch_needed_deg=round(max(0.0, elev-limit_deg), 1)))
    return min(out, key=lambda r: (not r['ok'], r['distance_m']))


PALM = .085                        # wrist to the gripping palm, as eva_suit.grip places a hand on a rail


def occ(V, body, a_top):
    """An occupant for the Blender study: variant, pose, rotation about the body axis, shift across the chamber axis, helmet-top station."""
    hull, th, shift = body; k, pose = next((k, p) for k, v in V.items() for p, h in v.items() if h is hull)
    return dict(variant=k, pose=pose, theta_deg=round(th, 3), shift_m=[round(x, 4) for x in shift], a_top_m=a_top,
                zmax_m=max(v[2] for v in hull['verts']))


def arm_reach(h):
    """The largest shoulder-to-wrist distance the suited arm reaches in any access pose (measured, PROTOTYPE motion), plus the palm."""
    return max(math.dist(p['joints'][f'shoulder_{s}'], p['joints'][f'hand_{s}']) for p in h.values() for s in 'lr')+PALM


def candidates(s, env, data):
    """Every aperture x layout, with door passage, chamber packaging (routine and rescue occupancy), operator reach and the rescue
    case. The two-person chamber is sized for the routine pair and both rescue pairings (EVA-044)."""
    st = data['airlock_study']; ac = data['access']; margin = ac['suit_margin_m']
    f = next(x for x in hull_geometry.service_fittings(s) if x['name'] == 'Airlock_EVA'); V = env['variants']; keys = list(V)
    tilts = st['casualty_tilt_deg']; out = []; fr = data['sp12']['r_m'][0]
    passing = {k: dict(hatch_pass=passage_circle(V[k]['hatch_pass']), suited=passage_circle(V[k]['chamber']),
                       casualty_restrained=passage_circle(V[k]['chamber']), casualty_free=passage_circle(V[k]['casualty'], tilts)) for k in keys}
    for D in st['apertures_m']:
        dr = door(s, D); doors = {}
        for k in keys:
            for pose, c in passing[k].items():
                m = round(D-c['diameter_m'], 3)
                doors[f'{k}.{pose}'] = dict(need_m=c['diameter_m'], margin_m=m, tilt_deg=c.get('tilt_deg'), required=pose != 'casualty_free',
                                           status='PASS' if m >= margin else ('MARGINAL' if m >= 0 else 'FAIL'))
        door_ok = all(v['status'] == 'PASS' for v in doors.values() if v['required'])
        for lay in st['layouts']:
            if lay == 'two_person':
                pl = pair_layout(V[keys[0]]['chamber'], V[keys[1]]['chamber'], margin)
                routine = [(V[keys[0]]['chamber'], pl['theta'], pl['shift_a']), (V[keys[1]]['chamber'], pl['theta']+180.0, pl['shift_b'])]
                rescue_sets = []
                for a, b in ((keys[0], keys[1]), (keys[1], keys[0])):
                    pr = pair_layout(V[a]['rescue'], V[b]['casualty'], margin)
                    rescue_sets.append([(V[a]['rescue'], pr['theta'], pr['shift_a']), (V[b]['casualty'], pr['theta']+180.0, pr['shift_b'])])
                ch = chamber(s, f, dr, [routine], margin, st['step_m'], st['hinge_steps'], fr)
                full = chamber(s, f, dr, [routine]+rescue_sets, margin, st['step_m'], st['hinge_steps'], fr)
                rescue = dict(status='PASS', routine_only_clear_m=[ch['clear_diameter_m'], ch['clear_length_m']],
                              note='the chamber is sized for the routine pair and both rescuer/casualty pairings (casualty in the free neutral posture)')
                ch = full; occupants = routine; rescue['occupants'] = [[occ(V, b, ch['body_top_a_m']) for b in st_] for st_ in rescue_sets]
            else:
                big = max(keys, key=lambda k: single_layout(V[k]['chamber'])['radius']); sl = single_layout(V[big]['chamber'])
                occupants = [(V[big]['chamber'], 0.0, sl['shift_a'])]
                ch = chamber(s, f, dr, [occupants], margin, st['step_m'], st['hinge_steps'], fr)
                rescue = dict(status='FAIL', note='an unresponsive crew member cannot cycle a single-person lock alone; a rescuer must share the '
                              'chamber (or a ship-side remote cycle, OPEN): the sequential layout serves routine egress only (EVA-044, EVA-054)')
            unlatch = ch['leaf_face_a_m']-ac['unlatch_standoff_m']
            ops = {k: reach(dr, V[k]['operate'], th, sh, unlatch, ch['leaf_face_a_m'], ac['reach_elevation_max_deg'], arm_reach(V[k]))
                   for k, (_, th, sh) in zip(keys, occupants)}
            row = dict(id=f'SP11_{lay.upper()}_{int(round(D*100)):03d}', aperture_m=D, layout=lay, study_target=abs(D-st['target_m']) < 1e-9,
                       door=dr, door_passage=doors, door_ok=door_ok, chamber=ch, operator_reach=ops, rescue=rescue,
                       cycles_per_pair=1 if lay == 'two_person' else 2, occupants=[occ(V, b, ch['body_top_a_m']) for b in occupants],
                       fitting=dict(x=round(f['x'], 4), theta_deg=round(math.degrees(f['theta']), 3), port_face_a_m=f['r1'], wall_m=s['human_entry']['chamber_wall_m']))
            fails = [f'door: {n} {v["status"]} (margin {v["margin_m"]} m)' for n, v in doors.items() if v['required'] and v['status'] != 'PASS']
            if not ch['fits_radially']:
                fails.append(f"radial budget {ch['radial_budget_m']} m: the inner leaf's swing (with its 0.05 m clearance) reaches below the SP-12 floor")
            if not any(o['ok'] for o in ops.values()):
                fails.append('outer hatch handle out of suited reach')
            row['conditions'] = [f"{k}: unlatching needs the body pitched {o['pitch_needed_deg']} deg toward the hatch (or an extension handle, OPEN)"
                                 for k, o in ops.items() if o['ok'] and o['pitch_needed_deg'] > 0]
            if rescue['status'] != 'PASS':
                fails.append('rescue: an incapacitated crew member cannot be cycled')
            row['geometry_fail'] = fails; row['status'] = 'STUDY PASS' if not fails else 'STUDY FAIL'
            out.append(row)
    return out


def recommend(rows):
    """The candidate to put to the owner: a two-person chamber (EVA-044 prefers it) ranked by its failures (a FAIL above a MARGINAL door
    above none), then the smaller aperture. A recommendation for owner review only: no pressure-shell geometry is released (EVA-043/055)."""
    def rank(r):
        hard = sum(1 for f in r['geometry_fail'] if 'MARGINAL' not in f); soft = len(r['geometry_fail'])-hard
        return (hard, soft, r['aperture_m'])
    two = sorted((r for r in rows if r['layout'] == 'two_person'), key=rank); best = two[0]
    return dict(id=best['id'], aperture_m=best['aperture_m'], status='EVA-002 ranking, SUPERSEDED by the owner (43 EVA-056: 1.10 m is the MARGINAL benchmark, '
                '1.20 m the lead study; see eva_sp11.py / p1_eva_sp11.json)', clean=not best['geometry_fail'],
                open_conditions=best['geometry_fail']+best.get('conditions', []),
                ranking=[dict(id=r['id'], fails=r['geometry_fail']) for r in sorted(rows, key=rank)],
                basis='two-person chamber first (EVA-044), fewest hard failures, then the smallest aperture; the sequential layouts cannot cycle a casualty')


# ---------------------------------------------------------------------------------------------------------------------------------
# SP-12 / SP-13 rooms

def room(s, q, name):
    """An annular-sector room (vehicle frame): extents, clear volume, floor area at the floor radius, and its fixtures in (x, az, r)."""
    (x0, x1), (a0, a1), (r0, r1) = q['x_m'], q['az_deg'], q['r_m']
    vol = (x1-x0)*math.radians(a1-a0)*(r1*r1-r0*r0)/2
    fx = []
    for fi in q['fixtures']:
        r_base = r0 if fi['kind'] in ('stand', 'zone', 'rack', 'bench', 'locker') else r0+.90
        fx.append(dict(fi, r0=round(r_base, 3), r1=round(r_base+fi['size'][2], 3), fits=r_base+fi['size'][2] <= r1+1e-9
                       and x0 <= fi['x']-fi['size'][0]/2+1e-9 and fi['x']+fi['size'][0]/2 <= x1+1e-9))
    return dict(id=name, status='PROTOTYPE STUDY (12A PROPOSED / PROGRAM)', x_m=[x0, x1], az_deg=[a0, a1], r_m=[r0, r1],
                clear_height_m=round(r1-r0, 3), clear_volume_m3=round(vol, 1), floor_arc_m=round(math.radians(a1-a0)*r0, 2), fixtures=fx)


def study(root=ROOT, env=None):
    s = spec.load(root)[0]; data = eva_suit.load(root); env = env or load_envelopes(root/'references/p1_eva_envelopes.json')
    fit = json.loads((root/'references/p1_eva_fit.json').read_text())
    cl = classes(s, env); rows = candidates(s, env, data)
    return dict(contract='eva_access v1', status='STUDY: geometric readback only, no pressure-shell change, not certification (EVA-043/055)',
                envelopes=cl, route_access=route_access(s, fit, cl), suited_route=data['access']['suited_route'],
                legacy_envelope=dict(key=data['access']['legacy_envelope_key'], value_m=s['human_entry']['mannequin']['suited_envelope_diameter_m'],
                                     classification=data['access']['legacy_envelope_class']),
                sp11=rows, recommendation=recommend(rows), sp12=room(s, data['sp12'], 'SP12'), sp13=room(s, data['sp13'], 'SP13'))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, default=OUTPUT); a = ap.parse_args()
    r = study(); a.out.write_text(json.dumps(r, indent=1)+'\n')
    print(json.dumps(dict(envelopes={k: {c: (v.get('measured_m') or v.get('casualty')) for c, v in e.items()} for k, e in r['envelopes'].items()},
                          sp11=[(x['id'], x['status'], x['chamber']['clear_diameter_m'], x['chamber']['clear_length_m'], x['chamber']['radial_budget_m'],
                                 x['geometry_fail']) for x in r['sp11']], recommendation=r['recommendation']), indent=1))


if __name__ == '__main__':
    main()
