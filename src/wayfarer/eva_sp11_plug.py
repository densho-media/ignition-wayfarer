"""SP-11 1.20 m sliding plug study (owner direction 2026-10-11: S&E 15!A134 AIRLOCK-004, 43 EVA-062, 45 I-01..I-04). Standard library only.

Everything here is STUDY / PROTOTYPE geometry on the disposable EVA-003 chamber: nothing is cut into the ship, no seal, latch, dog or
valve is rated, no setpoint is released and every force is a DIAGNOSTIC readback. Called by eva_sp11.study() (key `sliding_plug`).

  1. kinematics: the plug drops 0.08 m along the seat normal, then parks laterally (-az); its swept envelope against the posed rigs,
     the litter with its straps, the chamber, the SP-12 room, its fixtures and the aperture transit;
  2. bidirectional retention: seat lip for the seat-side pressure, dogs + keeper lugs for the reverse load, the load-path markers, the
     derived reverse load from the seal-seat geometry, and why the lever linkage is not a load path;
  3. an equalization valve, a gauge and an emergency release on the chamber side and on the SP-12 side, checked against the reach envelopes;
  4. the interlock table (data, with a small evaluator; thresholds are inputs and stay OPEN);
  5. the two-person and casualty re-check with the pocket, the controls and the straps in place.

Statuses as eva_sp11: PASS (at least the 0.05 m study margin), MARGINAL (0 to 0.05 m), FAIL (negative). Chamber frame (a, p, q) as eva_sp11.
"""
import math

import eva_access as ea
import eva_sp11 as sp
import eva_suit

ACCESS = ('chamber', 'hatch_pass', 'casualty', 'rescue', 'operate', 'latch', 'strap', 'pitch', 'supported')
CASES = [('routine_pair', None, 'two suited crew in the routine standing positions'),
         ('limp_casualty', 'casualty', 'unrestrained limp casualty (no litter, no straps)'),
         ('limbs_secured', 'supported', 'limbs secured, no support'),
         ('litter_frame', 'supported_frame', 'casualty on the litter frame, strapped'),
         ('vacuum_mattress', 'supported_mattress', 'casualty in a vacuum mattress, strapped'),
         ('frame_with_kit', 'supported_kit', 'casualty on the frame with a med/O2 kit, strapped')]
STRAPPED = ('supported_frame', 'supported_mattress', 'supported_kit')


def worst(*statuses):
    return max(statuses, key=['PASS', 'MARGINAL', 'FAIL'].index)


class RigBox:
    """An axis-aligned box in a rig's frame (x right, y back, z up), placed as ea.placed places the hull: exact distance from a chamber point."""

    def __init__(self, lo, hi, theta, shift, a_top, zmax):
        self.lo, self.hi, self.th, self.sh, self.da = lo, hi, theta, shift, a_top-zmax

    def corners(self):
        out = []
        for x in (self.lo[0], self.hi[0]):
            for y in (self.lo[1], self.hi[1]):
                for z in (self.lo[2], self.hi[2]):
                    p, q = ea.rot2((x, y), self.th); out.append((self.da+z, p+self.sh[0], q+self.sh[1]))
        return out

    def dist(self, pt):
        a, p, q = pt; x, y = ea.rot2((p-self.sh[0], q-self.sh[1]), -self.th); z = a-self.da
        d = [max(lo-v, 0.0, v-hi) for v, lo, hi in zip((x, y, z), self.lo, self.hi)]
        return math.sqrt(sum(c*c for c in d))


def straps(hull, theta, shift, a_top, zmax, k, tail):
    """The restraint straps of a litter casualty as boxes: bands across the suit front between the rails, buckle tails beyond the rails."""
    vs = hull['verts']; z0 = min(v[2] for v in vs)+k['frame_foot_m']; z1 = max(v[2] for v in vs)-k['frame_head_m']; out = []
    for f in STRAP_FRACS:
        z = z0+f*(z1-z0); yf = min(v[1] for v in vs); xm = max(abs(v[0]) for v in vs)     # the hull's front and rails (convex: conservative)
        lo = (-xm, yf-STRAP_OFF, z-STRAP_BAND/2); hi = (xm+tail, yf, z+STRAP_BAND/2)
        out.append(RigBox(lo, hi, theta, shift, a_top, zmax))
    return out


STRAP_FRACS = (); STRAP_OFF = 0.04; STRAP_BAND = 0.05


def configure(pq):
    global STRAP_FRACS, STRAP_OFF, STRAP_BAND
    STRAP_FRACS, STRAP_OFF, STRAP_BAND = tuple(pq['strap_fracs']), pq['strap_stand_off_m'], pq['strap_band_m']


def strap_outline(hull, k, tail, n=12):
    """Rig-frame points of the straps for the aperture passage: each band follows the body contour between the rails (a half ellipse, front side)
    with the buckle tail beyond one rail. (The boxes of straps() are the conservative envelope for the other clearances.)"""
    vs = hull['verts']; z0 = min(v[2] for v in vs)+k['frame_foot_m']; z1 = max(v[2] for v in vs)-k['frame_head_m']
    xm = max(abs(v[0]) for v in vs); yf = min(v[1] for v in vs); yb = max(v[1] for v in vs); cy = (yf+yb)/2; b = cy-yf+STRAP_OFF; out = []
    for f in STRAP_FRACS:
        z = z0+f*(z1-z0)
        out += [(xm*math.cos(math.pi*i/n), cy-b*math.sin(math.pi*i/n), z) for i in range(n+1)]+[(xm+tail, cy, z)]
    return out


# ---------------------------------------------------------------------------------------------------------------------------------
# the plug's swept envelope

def disc(a, cp, cq, r, n=48):
    pts = []
    for k in range(1, 5):
        pts += [(a, cp+r*k/4*math.cos(2*math.pi*j/n), cq+r*k/4*math.sin(2*math.pi*j/n)) for j in range(n)]
    return pts+[(a, cp, cq)]


def plug_states(row, q, pq):
    """Seated, dropped and the lateral samples to the park (-az): leaf discs (both faces) and the carriage box under the dropped leaf."""
    dr = row['door']; ch = row['chamber']; t = dr['t']; fd = dr['frame_depth']; bottom = ch['inner_bulkhead_a_m']
    top = bottom-fd; drop = q['plug_stroke_m']; travel = row['mechanisms']['parallel_plug_slide']['travel_m']; rail = q['slide_rail_depth_m']
    states = [('seated', 0.0, 0.0)]+[('dropped', drop, 0.0)]+[('lateral', drop, travel*i/pq['step_lateral']) for i in range(1, pq['step_lateral']+1)]
    out = []
    for name, dz, s in states:
        pts = disc(top-dz, 0.0, -s, dr['r_leaf'])+disc(top-dz-t, 0.0, -s, dr['r_leaf'])
        pts += [(top-dz-t-rail*u, -dr['r_leaf']-.05+2*(dr['r_leaf']+.05)*i, -s+(dr['r_leaf']+.05)*w) for u in (0, 1) for i in (0, 1) for w in (-1, 0, 1)]
        out.append(dict(state=name, drop_m=dz, lateral_m=round(s, 3), pts=pts))
    box = dict(a=[round(top-drop-t-rail, 3), round(top, 3)], p=[-dr['r_leaf']-.05, dr['r_leaf']+.05], q=[round(-travel-dr['r_leaf']-.05, 3), dr['r_leaf']+.05])
    return out, box, dict(seat_top_a_m=round(top, 3), parked_centre_a_m=round(top-drop-t/2, 3), travel_m=travel)


def box_corners(b):
    return [(a, p, q) for a in b['a'] for p in b['p'] for q in b['q']]


def box_dist(b, pt):
    d = [max(lo-v, 0.0, v-hi) for v, (lo, hi) in zip(pt, (b['a'], b['p'], b['q']))]
    return math.sqrt(sum(c*c for c in d))


def body_items(V, keys, row, pose, margin, k, pq):
    """Bodies of one case as (name, planes, boxes) lists per occupancy set: hull planes plus strap boxes for the strapped casualty."""
    if pose is None:
        occ = row['occupants']; sets = [[(V[o['variant']][o['pose']], o['theta_deg'], tuple(o['shift_m'])) for o in occ]]
        top = row['chamber']['body_top_a_m']
        # the operators at the lever and at the strap, with the partner standing (EVA-003 latch poses)
        for pose2 in ('latch', 'strap'):
            for i, o in enumerate(occ):
                a = occ[i]; b = occ[1-i]; v = V[a['variant']]
                sets.append([(v[pose2], a['theta_deg'], tuple(a['shift_m']), sp.root_top(v['chamber'], top, v[pose2])),
                             (V[b['variant']]['chamber'], b['theta_deg'], tuple(b['shift_m']), top)])
        sets[0] = [(h, th, sh, top) for h, th, sh in sets[0]]
        return [([ea.placed(h, th, sh, at)[1] for h, th, sh, at in s], [], [ea.placed(h, th, sh, at)[0] for h, th, sh, at in s]) for s in sets]
    out = []; top = row['chamber']['body_top_a_m']
    for s in sp.rescue_sets(V, keys, margin, (pose,)):
        pl = []; bx = []; vs = []
        for j, (h, th, sh) in enumerate(s):
            pvs, pv = ea.placed(h, th, sh, top); pl.append(pv); vs.append(pvs)
            if pose in STRAPPED and j == 1:
                for tail in (pq['strap_tail_stowed_m'], pq['strap_tail_loose_m']):
                    bx.append((tail, straps(h, th, sh, top, max(v[2] for v in h['verts']), k, tail)))
        out.append((pl, bx, vs))
    return out


_ORDER = {}


def fast_gap(planes, pts):
    """eva_sp11.gap with early exit (same value): a point is dropped as soon as one plane already shows it no nearer than the best so far."""
    key = id(planes); pl_ = _ORDER.get(key)
    if pl_ is None or pl_[0] is not planes:
        pl_ = _ORDER[key] = (planes, sorted(planes, key=lambda q: q[0][0]))
    ordered = pl_[1]; best = 9.0
    for p in pts:
        v = -9.0
        for (n0, n1, n2), d in ordered:
            t = n0*p[0]+n1*p[1]+n2*p[2]-d
            if t > v:
                v = t
                if v >= best:
                    break
        else:
            best = v
    return best


def gap_items(pts, items):
    """Least distance from points to every body hull (lower bound) and strap box of the case's sets. tail: which strap variant is judged."""
    res = {'stowed': 9.0, 'loose': 9.0}
    for planes_l, bx, _ in items:
        g = min(fast_gap(pl, pts) for pl in planes_l); res['stowed'] = min(res['stowed'], g); res['loose'] = min(res['loose'], g)
        for tail, boxes in bx:
            key = 'stowed' if tail == min(t for t, _ in bx) else 'loose'
            res[key] = min(res[key], min(b.dist(p) for b in boxes for p in pts))
    return res


# ---------------------------------------------------------------------------------------------------------------------------------
# retention

def retention(s, row, pq, q):
    dr = row['door']; ch = row['chamber']; h = s['human_entry']; cabin = eva_suit.load()['telemetry']['cabin_pressure_kpa']['value']
    overlap = h['hatch_leaf_overlap_m']; rc = dr['r_clear']; rl = dr['r_leaf']; t = dr['t']; top = ch['inner_bulkhead_a_m']-dr['frame_depth']
    d_eff = 2*(rc+pq['seal_band_frac']*overlap); area = lambda d: math.pi*d*d/4*cabin   # kPa x m2 = kN
    loads = {'bore_circle': dict(d_m=2*rc, kn=round(area(2*rc), 1)), 'seal_line_effective': dict(d_m=round(d_eff, 3), kn=round(area(d_eff), 1)),
             'leaf_outer': dict(d_m=2*rl, kn=round(area(2*rl), 1))}
    read = pq['reverse_load_readback_n']/1e3; derived = loads['leaf_outer']['kn']     # SP11-005 / CALC-R01: the 1.30 m outer leaf bounds
    n = pq['dog_count']; per = derived/n; bearing = pq['dog_w_m']*pq['dog_stroke_m']
    dog_a = top-pq['dog_h_m']/2; ledge_a = top-pq['dog_h_m']-pq['ledge_h_m']/2; lug_depth = pq['dog_h_m']+pq['ledge_h_m']-pq.get('ledge_recess_m', 0.0); r_dog = rl+pq['dog_stroke_m']
    dogs = [dict(i=i, angle_deg=round(360.0*i/n, 1), chamber=[round(dog_a, 3), round(rl*math.cos(2*math.pi*i/n), 3), round(rl*math.sin(2*math.pi*i/n), 3)])
            for i in range(n)]
    markers = [dict(id='P_chamber', role='reverse pressure (chamber high / SP-12 loss) acts on the leaf (outer-diameter bound), toward SP-12', chamber=[round(top+.05, 3), 0.0, 0.0]),
               dict(id='LEAF_PLATE', role='leaf plate carries it to the rim', chamber=[round(top-t/2, 3), 0.0, 0.0]),
               dict(id='DOG', role=f'{n} radial dogs, bearing on the keeper ledges (axial load, no radial component)', chamber=[round(dog_a, 3), round(r_dog, 3), 0.0]),
               dict(id='KEEPER_LEDGE', role='ledge under each dog, in a lug hanging from the frame', chamber=[round(ledge_a, 3), round(r_dog, 3), 0.0]),
               dict(id='FRAME_RING', role='frame ring (bore 0.60 m) to the bulkhead', chamber=[round(top+dr['frame_depth']/2, 3), round(rc+overlap+.04, 3), 0.0]),
               dict(id='BULKHEAD_RING', role='inner bulkhead to the chamber shell (the existing PROTOTYPE shell)', chamber=[round(ch['inner_bulkhead_a_m']+.05, 3), round(ch['clear_radius_m'], 3), 0.0]),
               dict(id='SEAT_LIP', role='seat-side pressure (SP-12 high) loads the face seal on the frame lip: the seating path', chamber=[round(top, 3), round(rc+pq['seal_band_frac']*overlap, 3), 0.0])]
    fr = pq['friction']; draft = math.radians(pq['face_draft_deg'])
    lever = dict(
        load_face_normal='the chamber axis (a); the dogs retract radially, so the pressure load has no component on the retraction (90 deg)',
        back_drive_nominal_n=0.0, draft_deg=pq['face_draft_deg'], back_drive_with_draft_kn_per_dog=round(per*math.sin(draft), 3),
        self_locking=math.tan(draft) < fr, friction_assumed=fr, self_lock_basis='tan(draft) < friction, so a drafted face does not push the dog out',
        friction_to_retract_under_load_kn=round(fr*derived, 1), friction_note='a lever pulled under the reverse load would see this at the dogs (DIAGNOSTIC): '
                                                                              'it opposes unlatching; the blocking pins, not the lever, hold the cam ring',
        toggle=dict(crank_m=pq['toggle_throw_m'], overcentre_deg=pq['toggle_overcentre_deg'], offset_m=round(pq['toggle_throw_m']*math.sin(math.radians(pq['toggle_overcentre_deg'])), 4),
                    note='the dog-cam toggle locks over centre against a fixed stop: a back-driving force on the link holds it on the stop'),
        blocking_pins=dict(count=2, d_m=pq['block_pin_d_m'], where='opposite sides of the dog cam ring, engaged unless |dp| is inside the test point',
                           note='the pins, the dogs and the stop carry anything a person or the pressure puts on the linkage'),
        lever_force_path='lever -> torque tube -> toggle -> cam ring -> dogs: moves the dogs only, never carries the pressure load')
    return dict(
        geometry=dict(leaf_r_m=rl, bore_r_m=rc, seat_band_m=overlap, seal_line_d_m=round(d_eff, 3), seat_lip_a_m=round(top, 3), lug_depth_m=lug_depth,
                      dog_h_m=pq['dog_h_m'], ledge_h_m=pq['ledge_h_m'], dog_w_m=pq['dog_w_m'], dog_stroke_m=pq['dog_stroke_m'], dog_count=n),
        directions=dict(seat_side='SP-12 pressure high (the chamber evacuated): the leaf, under the frame on the SP-12 side, is pushed onto the face seal on the frame lip; '
                                  'the seating path carries it, the dogs only hold the leaf there',
                        reverse='chamber pressure high (or SP-12 loss): the leaf is pushed off the lip toward SP-12; the dogs bear on the keeper ledges (positive, bidirectional)',
                        note='the brief names the reverse case SP-12-high; with the leaf on the SP-12 face of the frame it is the chamber-high case (as ECLSS_REC2). The loads are equal.'),
        cabin_kpa=cabin, loads_kn=loads, derived_reverse_kn=derived, derived_basis='leaf outer diameter x 80 kPa (BASELINE cabin): the owner bounding diagnostic (15!A145, 45 I-08) until the true wetted '
                                                                 'seat area is known; the seal-line disc is a comparison only, seat and leaf are not claimed equal',
        seal_line_comparison_kn=loads['seal_line_effective']['kn'],
        readback_kn=round(read, 1), derived_vs_readback_pct=round(100.0*(derived-read)/read, 2), area_check_leaf_outer_kn=loads['leaf_outer']['kn'],
        readback_matches_leaf_outer=abs(loads['leaf_outer']['kn']-read) < 0.5,
        per_dog_kn=round(per, 2), per_dog_one_failed_kn=round(derived/(n-1), 2), dog_bearing_area_cm2=round(bearing*1e4, 1),
        keeper_drop_clearance_m=round(q['plug_stroke_m']-lug_depth, 3), keeper_drop_status=sp.status(q['plug_stroke_m']-lug_depth, 0.05),
        keeper_note='the dropped leaf must clear the lug underside; the 0.08 m stroke leaves stroke - (dog + ledge) under the lugs',
        dogs=dogs, markers=markers, lever=lever)


# ---------------------------------------------------------------------------------------------------------------------------------
# controls: equalization valve, gauge, emergency release, on both sides

def users_chamber(V, keys, row, margin):
    """Suited crew in the routine positions, the two rescuers and the same standing positions unsuited: (name, joints in the chamber frame, reach)."""
    out = []; top = row['chamber']['body_top_a_m']
    reach = {k: ea.arm_reach({n: V[k][n] for n in ACCESS}) for k in keys}; ureach = {k: ea.arm_reach({'unsuited': V[k]['unsuited']}) for k in keys}
    for o in row['occupants']:
        h = V[o['variant']]['chamber']
        out.append((f"suited_{o['variant']}", joints(h, o['theta_deg'], o['shift_m'], top), reach[o['variant']]))
        u = V[o['variant']]['unsuited']
        out.append((f"unsuited_{o['variant']}_same_place", joints(u, o['theta_deg'], o['shift_m'], top-max(v[2] for v in h['verts'])+max(v[2] for v in u['verts'])), ureach[o['variant']]))
    for pr in sp.rescue_sets(V, keys, margin, ('supported_frame',)):
        (h, th, sh), _ = pr
        k = next(k for k in keys if V[k]['rescue'] is h)
        out.append((f"rescuer_{k}", joints(h, th, sh, top), reach[k]))
    return out


def joints(h, theta, shift, a_top):
    return {n: sp.place_joint(h, theta, shift, a_top, p) for n, p in h['joints'].items()}


def panel_gap(verts, R, wall, a_c, phi, pq, lay=None):
    """Least distance from body hull vertices (chamber frame) to the SP-12-side panel plate (a box on the outer wall, flat, protruding panel_prot_m)."""
    Ro = R+wall; prot = pq['panel_prot_m']; hl = pq['panel_len_m']/2; hw = pq['panel_half_w_m']; c, s_ = math.cos(phi), math.sin(phi)
    if lay is not None and lay['layout'] == 'row':
        hl, hw = hw, lay['pitch_m']+0.10
    best = 9.0
    for a, p, q in verts:
        n = p*c+q*s_; tg = -p*s_+q*c
        best = min(best, math.sqrt(max(abs(a-a_c)-hl, 0.0)**2+max(abs(tg)-hw, 0.0)**2+max(Ro-0.05-n, 0.0, n-(Ro+prot))**2))
    return best


def cluster_pts(R, a_c, phi, pq, side, wall, lay=None):
    """Release ring, valve, gauge on the wall at angle phi: actuation points at the panel stand-off (chamber side inside R, SP-12 side outside R+wall).
    lay (SIM-027 redline_controls row, SP-12 side): layout 'vertical' stacks them along the axis in `order` (lowest first), 'row' puts them side by side at one height."""
    rho = (R-pq['panel_prot_m']) if side == 'chamber' else (R+wall+pq['panel_prot_m'])
    if lay is None:
        return {name: (a_c+off, rho*math.cos(phi), rho*math.sin(phi)) for name, off in (('release', -pq['panel_pitch_m']), ('valve', 0.0), ('gauge', pq['panel_pitch_m']))}
    pit = lay['pitch_m']; out = {}
    for i, name in enumerate(lay['order']):
        off = (i-1)*pit
        if lay['layout'] == 'vertical':
            out[name] = (a_c+off, rho*math.cos(phi), rho*math.sin(phi))
        else:
            ph = phi+off/rho; out[name] = (a_c, rho*math.cos(ph), rho*math.sin(ph))
    return out


def panel_box_pts(R, a_c, phi, pq, side, wall, lay=None):
    """Corner and mid points of the panel's backplate and stand-off envelope (study sampling). A row layout swaps the plate's long side to the tangent."""
    ws = R if side == 'chamber' else R+wall; out = []
    hl = pq['panel_len_m']/2; hw = pq['panel_half_w_m']; prot = pq['panel_prot_m']; ph = (math.cos(phi), math.sin(phi)); tg = (-math.sin(phi), math.cos(phi))
    if lay is not None and lay['layout'] == 'row':
        hl, hw = hw, lay['pitch_m']+0.10            # the plate spans the three controls along the wall
    for da in (-hl, 0.0, hl):
        for dt in (-hw, 0.0, hw):
            for rr in (0.0, prot):
                rho = ws-rr if side == 'chamber' else ws+rr
                out.append((a_c+da, rho*ph[0]+dt*tg[0], rho*ph[1]+dt*tg[1]))
    return out


def reach_margins(users, pts):
    """Per user and control: reach - nearest-shoulder distance (suited reach includes the palm); the gauge also against the head."""
    out = {}
    for name, jn, reach in users:
        for cn, c in pts.items():
            d = min(math.dist(jn[s], c) for s in ('shoulder_l', 'shoulder_r'))
            out[f'{name}.{cn}'] = round(reach-d, 3)
    return out


def chamber_side(s, V, keys, row, sets_for_gap, users, pq, q):
    """One cluster per crew position (the two stand 2.1 m apart: no single wall point is in both reaches); every user is judged against the nearest."""
    R = row['chamber']['clear_radius_m']; wall = row['fitting']['wall_m']; taken = []; clusters = []
    lev = [(math.atan2(l['lever_pivot_chamber'][2], l['lever_pivot_chamber'][1])) for l in row['latch'].values()]
    for v in keys:
        own = [u for u in users if u[0] in (f'suited_{v}', f'unsuited_{v}_same_place')]; best = None
        for i in range(16):
            a_c = 3.0+0.1*i
            for j in range(24):
                phi = math.radians(15.0*j)
                if any(abs(math.remainder(phi-l, 2*math.pi))*R < pq['lever_arc_min_m'] for l in lev+taken):
                    continue
                pts = cluster_pts(R, a_c, phi, pq, 'chamber', wall); mn = min(reach_margins(own, pts).values())
                if mn < 0.0 and best is not None and best[0] >= 0.0:
                    continue
                g = min(gap_items(panel_box_pts(R, a_c, phi, pq, 'chamber', wall), [it])['stowed'] for it in sets_for_gap) if mn >= -0.05 else -9.0
                sc = min(mn, g)
                if best is None or sc > best[0]:
                    best = (sc, a_c, phi, g)
        sc, a_c, phi, g = best; taken.append(phi)
        clusters.append(dict(for_crew=v, station_a_m=round(a_c, 2), angle_deg=round(math.degrees(phi), 1), wall_radius_m=R, stand_off_m=pq['panel_prot_m'],
                             points={k: [round(x, 3) for x in p] for k, p in cluster_pts(R, a_c, phi, pq, 'chamber', wall).items()},
                             body_gap_m=round(g, 3), body_status=sp.status(g, 0.05)))
    m = {}
    for u in users:
        for cl in clusters:
            for kk, vv in reach_margins([u], {k: tuple(p) for k, p in cl['points'].items()}).items():
                m[kk] = max(m.get(kk, -9.0), vv)
    head = {}
    for name, jn, _r in users:
        head[name] = round(min(math.dist(jn['head'], tuple(cl['points']['gauge'])) for cl in clusters), 3)
    return dict(clusters=clusters, reach_margin_m=m, reach_status={k: sp.status(v, 0.05) for k, v in m.items()}, head_to_gauge_m=head,
                gauge_view_status={k: ('PASS' if v <= pq['gauge_view_max_m'] else 'FAIL') for k, v in head.items()}, lever_arc_min_m=pq['lever_arc_min_m'],
                body_gap_m=min(c['body_gap_m'] for c in clusters), body_status=sp.status(min(c['body_gap_m'] for c in clusters), 0.05))


def sp12_side(s, data, V, keys, row, fit, pq, q, box, lay=None):
    """SP-12 side: the operator stands on the SP-12 floor (r 1.25 m; the chamber-axis plane is the approximation) facing a cluster on the chamber's
    outside wall; suited and unsuited, both bodies. Room bounds, the chamber wall, the fixtures and the plug's envelope are checked on hull vertices.
    lay (a SIM-027 redline_controls row) changes the cluster layout and the body stand-off and adds the body-to-panel gap to the operator clearance;
    data may carry moved study fixtures."""
    ch = row['chamber']; R = ch['clear_radius_m']; wall = row['fitting']['wall_m']; Ro = R+wall; room = data['sp12']
    standoff = lay['standoff_m'] if lay else pq['standoff_sp12_m']; a_min = lay['a_min_m'] if lay else 2.8; rm = ea.room(s, room, 'SP12')
    floor = room['r_m'][0]; hulls = []
    reach = {k: ea.arm_reach({n: V[k][n] for n in ACCESS}) for k in keys}; ureach = {k: ea.arm_reach({'unsuited': V[k]['unsuited']}) for k in keys}
    for k in keys:
        hulls += [(f'suited_{k}', V[k]['chamber'], reach[k]), (f'unsuited_{k}', V[k]['unsuited'], ureach[k])]

    def station(h, phi):
        th = math.degrees(math.atan2(-math.cos(phi), math.sin(phi))); yf = min(v[1] for v in h['verts']); d = Ro+standoff-yf
        sh = (d*math.cos(phi), d*math.sin(phi)); at = floor+max(v[2] for v in h['verts'])-min(v[2] for v in h['verts']); return th, sh, at

    def constraints(h, th, sh, at, a_c=None, phi=None):
        verts = ea.placed(h, th, sh, at)[0]; V3 = [sp.to_vehicle(fit, *v) for v in verts]; P = [sp.polar(v) for v in V3]
        inroom = min(min(p[0]-room['x_m'][0], room['x_m'][1]-p[0]) for p in P)
        inroom = min(inroom, min(room['r_m'][1]-p[2] for p in P), min(math.radians(1)*p[2]*min(p[1]-room['az_deg'][0], room['az_deg'][1]-p[1]) for p in P))
        wallg = min([math.hypot(v[1], v[2])-Ro for v in verts if v[0] >= ch['inner_bulkhead_a_m']] or [9.0])
        pg = panel_gap(verts, R, wall, a_c, phi, pq, lay) if lay else None
        fx = 9.0; zone = []; near = None
        for f in rm['fixtures']:
            az = math.radians(f['az']); ez = (0, math.cos(az), math.sin(az)); ey = (0, -math.sin(az), math.cos(az)); rc = (f['r0']+f['r1'])/2
            cen = (f['x'], rc*ez[1], rc*ez[2]); dmin = 9.0
            for v in V3:
                dd = [v[0]-cen[0], sum((v[i]-cen[i])*ey[i] for i in range(3)), sum((v[i]-cen[i])*ez[i] for i in range(3))]
                dmin = min(dmin, math.sqrt(sum(max(abs(x)-sz/2, 0.0)**2 for x, sz in zip(dd, f['size']))))
            if f['kind'] == 'zone':
                if dmin <= 0:
                    zone.append(f['id'])
            elif dmin < fx:
                fx = dmin; near = f['id']
        return dict(room_m=round(inroom, 3), chamber_wall_m=round(wallg, 3), plug_envelope_m=round(min(box_dist(box, v) for v in verts), 3), fixtures_m=round(fx, 3), panel_m=None if pg is None else round(pg, 3),
                    nearest_fixture=near, zones=zone, station_chamber=[round(floor, 3), round(sh[0], 3), round(sh[1], 3)], facing_deg=round(th, 1))

    step = lay.get('phi_step_deg', 15.0) if lay else 15.0; phis = lay['phi_deg'] if lay and lay.get('phi_deg') is not None else [step*j for j in range(-int(90/step), int(90/step)+1)]
    best = None
    for i in range(13):
        a_c = a_min+0.1*i
        for pdeg in phis:
            phi = math.radians(pdeg); pts = cluster_pts(R, a_c, phi, pq, 'sp12', wall, lay); res = {}
            for name, h, rch in hulls:
                th, sh, at = station(h, phi); jn = joints(h, th, sh, at)
                for cn, c in pts.items():
                    res[f'{name}.{cn}'] = round(rch-min(math.dist(jn[sd], c) for sd in ('shoulder_l', 'shoulder_r')), 3)
            mr = min(res.values())
            if mr < -0.05 or (best is not None and mr <= best[0]):
                continue
            cons = {name: constraints(h, *station(h, phi), a_c, phi) for name, h, _r in hulls}
            cg = min(min(c['room_m'], c['chamber_wall_m'], c['plug_envelope_m'], c['fixtures_m'], c['panel_m'] if c['panel_m'] is not None else 9.0) for c in cons.values())
            sc = min(mr, cg)
            if best is None or sc > best[0]:
                best = (sc, a_c, phi, res, cons, cg)
    sc, a_c, phi, res, cons, cg = best; pts = cluster_pts(R, a_c, phi, pq, 'sp12', wall, lay)
    head = {}
    for name, h, _r in hulls:
        th, sh, at = station(h, phi); head[name] = round(math.dist(joints(h, th, sh, at)['head'], pts['gauge']), 3)
    return dict(station_a_m=round(a_c, 2), angle_deg=round(math.degrees(phi), 1), wall_radius_m=round(Ro, 3), stand_off_m=pq['panel_prot_m'], layout=lay['layout'] if lay else 'vertical', pitch_m=lay['pitch_m'] if lay else pq['panel_pitch_m'],
                body_standoff_m=standoff,
                points={k: [round(x, 3) for x in v] for k, v in pts.items()}, reach_margin_m=res, reach_status={k: sp.status(v, 0.05) for k, v in res.items()},
                head_to_gauge_m=head, gauge_view_status={k: ('PASS' if v <= pq['gauge_view_max_m'] else 'FAIL') for k, v in head.items()},
                operator=cons, operator_clearance_m=round(cg, 3), operator_status=sp.status(cg, 0.05),
                floor_approximation='the floor is the cylinder r = 1.25 m; the chamber-axis plane stands in for it (0.04 m for stations within 0.3 m of the axis)',
                zone_overlap=sorted({z for c in cons.values() for z in c['zones']}))


# ---------------------------------------------------------------------------------------------------------------------------------
# interlock table

def interlock(pq):
    thr = None                                  # OPEN: the setpoint is not released; 45 I-01 is a test point
    conds = {'dp': 'abs(dp_kpa) <= threshold_kpa (threshold is an input; None = OPEN = fail closed)', 'other_closed': 'the other closure of the chamber confirmed latched',
             'plug_parked_clear': 'the plug parked and its carriage clear of the aperture', 'equalized_both': 'equalization valve closed after the gauge reads inside the test point'}
    rows = [dict(action='unlatch the inner plug (chamber lever)', requires=['dp', 'other_closed'], blocks_with='two blocking pins on the dog cam ring'),
            dict(action='unlatch the inner plug (SP-12 lever)', requires=['dp', 'other_closed'], blocks_with='the same pins'),
            dict(action='unlatch the outer hatch (chamber lever)', requires=['dp', 'other_closed'], blocks_with='the outer hatch dog pins (EVA3-002)'),
            dict(action='drop and park the plug', requires=['dp', 'other_closed'], blocks_with='dogs must be clear of the keeper lugs'),
            dict(action='close and dog the plug', requires=['plug_parked_clear'], blocks_with='lateral stop, then the drop-and-seat stroke'),
            dict(action='open the equalization valve', requires=[], blocks_with='none: it reduces |dp|; the gauge on both sides shows the result'),
            dict(action='emergency manual release (either side)', requires=['dp'], blocks_with='the pins: the release cannot override a structural differential; '
                                                                                                'it retracts the dogs only inside the test point'),
            dict(action='cycle the chamber gas', requires=['plug_parked_clear'], blocks_with='gas cycling is not assumed (OPEN, Sheets)')]
    return dict(inputs=dict(dp_threshold_kpa=thr, dp_threshold_status='OPEN (input); the study test point is 45 I-01 0.05 kPa, STUDY ONLY, not a setpoint',
                            dp_test_point_kpa=pq['dp_test_point_kpa']),
                conditions=conds, rows=rows,
                forces=dict(lever_force_target_n=pq['lever_force_target_n'], lever_force_basis='45 I-03 HUMAN FACTORS STUDY target to evaluate; the actual lever force is OPEN',
                            lever_force_actual_n=None, ideal_aperture_force_n=pq['ideal_aperture_force_n'],
                            ideal_aperture_force_derived_n=round(pq['dp_test_point_kpa']*1e3*math.pi*0.6**2, 8),
                            ideal_aperture_note='45 I-02 DIAGNOSTIC: dp x the 1.20 m circle area; it is not a handle force'),
                notes=['The unlatch is permitted only with |dp| inside the threshold AND the other closure confirmed; no threshold means no permission (fail closed).',
                       'Mechanical backing: blocking pins and the toggle stop hold the dogs; no logic, power or lever force substitutes for them.'])


def permits(table, action, dp_kpa, threshold_kpa=None, other_closed=False, plug_parked_clear=False):
    """The table's rule for one action and one state. Data, not a controller."""
    row = next(r for r in table['rows'] if r['action'].startswith(action)); state = dict(dp=threshold_kpa is not None and abs(dp_kpa) <= threshold_kpa,
                                                                                        other_closed=other_closed, plug_parked_clear=plug_parked_clear)
    miss = [c for c in row['requires'] if not state[c]]; return not miss, miss


# ---------------------------------------------------------------------------------------------------------------------------------
# kinematics, transit and the re-check

def casualty_transit(V, keys, row, pose, margin, k, pq, tilts, floor):
    """The casualty (no rescuer) centred on the aperture and moved along -a: bore and parked-carriage clearances of its enclosing circle (hull plus
    straps, turned by the best casualty tilt as the door passage turns it), and how far it goes before the SP-12 floor."""
    if pose is None:
        return None
    dr = row['door']; top = row['chamber']['body_top_a_m']; out = {}; travel = row['mechanisms']['parallel_plug_slide']['travel_m']
    edge = travel-(dr['r_leaf']+.05)                       # the carriage box under the parked leaf reaches this close to the axis (as the Blender pocket)
    for cas in keys:
        h = V[cas][pose]; strapped = pose in STRAPPED; zmax = max(v[2] for v in h['verts']); zmin = min(v[2] for v in h['verts'])
        for tail_name, tail in (('stowed', pq['strap_tail_stowed_m']), ('loose', pq['strap_tail_loose_m'])) if strapped else (('none', 0.0),):
            pts3 = [tuple(v) for v in h['verts']]
            if strapped:
                pts3 += strap_outline(h, k, tail)
            best = None
            for ax in tilts:
                for ay in tilts:
                    cen, rad = ea.enclosing_circle([ea.tilt(v, ax, ay)[:2] for v in pts3])
                    if best is None or rad < best[0]:
                        best = (rad, ax, ay)
            rad = best[0]; bore = round(dr['r_clear']-rad, 3); lat = round(edge-rad, 3)
            out[f'{cas}.{tail_name}'] = dict(enclosing_radius_m=round(rad, 3), tilt_deg=[best[1], best[2]], bore_clearance_m=bore, bore_status=sp.status(bore, margin),
                                             parked_plug_clearance_m=lat, parked_plug_status=sp.status(lat, margin), insertion_limit_m=round(top-(zmax-zmin)-floor-margin, 3),
                                             body_length_m=round(zmax-zmin, 3))
    return out


def case_report(s, V, keys, row, fit, q, pq, margin, plug, panel_ch, panel_sp, pose):
    ch = row['chamber']; R = ch['clear_radius_m']; wall = row['fitting']['wall_m']; k = eva_suit.load()['rescue_support']
    items = body_items(V, keys, row, pose, margin, k, pq)
    states, box, meta = plug
    # plug swept envelope against the bodies and the litter hardware, over all states
    g_plug = 9.0; g_plug_loose = 9.0
    for st in states:
        g = gap_items(st['pts'], items); g_plug = min(g_plug, g['stowed']); g_plug_loose = min(g_plug_loose, g['loose'])
    gps = [gap_items(panel_box_pts(R, c['station_a_m'], math.radians(c['angle_deg']), pq, 'chamber', wall), items) for c in panel_ch['clusters']]
    gp = {kk: min(g[kk] for g in gps) for kk in ('stowed', 'loose')}
    return dict(plug_to_bodies_m=round(g_plug, 3), plug_status=sp.status(g_plug, margin), plug_to_bodies_loose_straps_m=round(g_plug_loose, 3),
                chamber_panel_to_bodies_m=round(gp['stowed'], 3), chamber_panel_status=sp.status(gp['stowed'], margin),
                chamber_panel_to_bodies_loose_straps_m=round(gp['loose'], 3), sets=len(items))


def envelope_room(s, sp12, fit, states):
    """The plug's swept samples in the SP-12 room (polar bounds, room margin) and the distance to every SP-12 fixture."""
    rm = ea.room(s, sp12, 'SP12'); allp = [sp.polar(sp.to_vehicle(fit, *p)) for st in states for p in st['pts']]
    xs = [p[0] for p in allp]; az = [p[1] for p in allp]; rr = [p[2] for p in allp]
    bounds = dict(x_m=[round(min(xs), 3), round(max(xs), 3)], az_deg=[round(min(az), 1), round(max(az), 1)], r_m=[round(min(rr), 3), round(max(rr), 3)])
    room_m = round(min(min(xs)-sp12['x_m'][0], sp12['x_m'][1]-max(xs), (min(az)-sp12['az_deg'][0])*math.pi/180*min(rr), (sp12['az_deg'][1]-max(az))*math.pi/180*min(rr),
                       min(rr)-sp12['r_m'][0], sp12['r_m'][1]-max(rr)), 3)
    fx = {}
    for f in rm['fixtures']:
        az_ = math.radians(f['az']); ez = (0, math.cos(az_), math.sin(az_)); ey = (0, -math.sin(az_), math.cos(az_)); rc = (f['r0']+f['r1'])/2
        cen = (f['x'], rc*ez[1], rc*ez[2]); dmin = 9.0
        for st in states:
            for p in st['pts']:
                v = sp.to_vehicle(fit, *p); dd = [v[0]-cen[0], sum((v[i]-cen[i])*ey[i] for i in range(3)), sum((v[i]-cen[i])*ez[i] for i in range(3))]
                dmin = min(dmin, math.sqrt(sum(max(abs(x)-sz/2, 0.0)**2 for x, sz in zip(dd, f['size']))))
        fx[f['id']] = round(dmin, 3)
    return bounds, room_m, fx


# ---------------------------------------------------------------------------------------------------------------------------------
# SIM-027 redlines (owner 2026-10-11 16:45: 15!A152:A154 SP11-005..007): keeper clearance variants, SP-12 control cluster / stand A relocation

def fixture_gap(fa, fb):
    """Least distance from the corners and face centres of fixture box fa to fixture box fb (vehicle frame; boxes as ea.room fixtures): a study sample."""
    def frame(f):
        az = math.radians(f['az']); rc = (f['r0']+f['r1'])/2
        return (f['x'], rc*math.cos(az), rc*math.sin(az)), (0, -math.sin(az), math.cos(az)), (0, math.cos(az), math.sin(az))
    ca, ya, za = frame(fa); cb, yb, zb = frame(fb); best = 9.0; xa, wa, ha = fa['size']
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            for k in (-1, 0, 1):
                v = tuple(ca[n]+i*xa/2*(1 if n == 0 else 0)+j*wa/2*ya[n]+k*ha/2*za[n] for n in range(3))
                dd = [v[0]-cb[0], sum((v[n]-cb[n])*yb[n] for n in range(3)), sum((v[n]-cb[n])*zb[n] for n in range(3))]
                best = min(best, math.sqrt(sum(max(abs(x)-sz/2, 0.0)**2 for x, sz in zip(dd, fb['size']))))
    return round(best, 3)


def keeper_variants(s, data, V, keys, row, fit, margin, panel_ch):
    """Every redline_keeper variant: keeper clearance (stroke - lug hang) and the swept envelope against the bodies of every case, the SP-12 room and fixtures."""
    q0 = data['sp11_eva3']; pq0 = data['sp11_plug']; out = []
    for kv in pq0['redline_keeper']:
        q2 = dict(q0, plug_stroke_m=kv['stroke_m'], slide_rail_depth_m=kv['rail_m'])
        pq2 = dict(pq0, dog_h_m=kv['dog_h_m'], ledge_h_m=kv['ledge_h_m'], ledge_recess_m=kv['ledge_recess_m']); configure(pq2)
        states, box, meta = plug_states(row, q2, pq2); bounds, room_m, fx = envelope_room(s, data['sp12'], fit, states)
        hang = kv['dog_h_m']+kv['ledge_h_m']-kv['ledge_recess_m']; clr = round(kv['stroke_m']-hang, 3)
        cases = {}
        for name, pose, label in CASES:
            r = case_report(s, V, keys, row, fit, q2, pq2, margin, (states, box, meta), panel_ch, None, pose)
            cases[name] = dict(plug_to_bodies_m=r['plug_to_bodies_m'], status=r['plug_status'], plug_to_bodies_loose_straps_m=r['plug_to_bodies_loose_straps_m'], sets=r['sets'])
        out.append(dict(id=kv['id'], what=kv['what'], stroke_m=kv['stroke_m'], rail_m=kv['rail_m'], dog_h_m=kv['dog_h_m'], ledge_h_m=kv['ledge_h_m'], ledge_recess_m=kv['ledge_recess_m'],
                        lug_hang_m=round(hang, 3), keeper_clearance_m=clr, keeper_status=sp.status(clr, margin), sp12_room_margin_m=room_m, sp12_room_status=sp.status(room_m, margin),
                        sp12_fixture_min_m=min(fx.values()), swept_polar_bounds=bounds, envelope_a_m=box['a'], cases=cases,
                        plug_to_bodies_min_m=min(c['plug_to_bodies_m'] for c in cases.values()), swept_envelope_status=sp.status(min(c['plug_to_bodies_m'] for c in cases.values()), margin),
                        note='PROTOTYPE study variant; no keeper, seal or panel change to the model before FEA and clearance pass (owner 15!A152:A154)'))
    configure(pq0)
    return out


def control_variants(s, data, V, keys, row, fit, margin, box):
    """Every redline_controls variant on the SP-12 side: reach, operator clearance (room, chamber wall, plug envelope, fixtures, panel plate), buddy zone."""
    import copy
    q0 = data['sp11_eva3']; pq0 = data['sp11_plug']; out = []
    for cv in pq0['redline_controls']:
        d2 = copy.deepcopy(data)
        for f in d2['sp12']['fixtures']:
            if f['id'] == 'SP12_DON_STAND_A':
                f['x'] = cv['stand_a_x_m']; f['az'] = cv['stand_a_az_deg']
            if f['id'] == 'SP12_BUDDY_ZONE':
                f['x'] = cv['zone_x_m']; f['az'] = cv['zone_az_deg']
        ps = sp12_side(s, d2, V, keys, row, fit, pq0, q0, box, lay=cv); rm = ea.room(s, d2['sp12'], 'SP12'); fx = {f['id']: f for f in rm['fixtures']}
        rs = ps['reach_margin_m']; suited = {k: v for k, v in rs.items() if k.startswith('suited_')}; unsuited = {k: v for k, v in rs.items() if k.startswith('unsuited_')}
        op = ps['operator']; comp = {c: min(o[c] for o in op.values() if o[c] is not None) for c in ('room_m', 'chamber_wall_m', 'plug_envelope_m', 'fixtures_m', 'panel_m')
                                     if any(o[c] is not None for o in op.values())}
        least_body = min(comp.values()); worst_suited = min(suited, key=suited.get)
        out.append(dict(id=cv['id'], what=cv['what'], layout=cv['layout'], station_a_m=ps['station_a_m'], angle_deg=ps['angle_deg'], body_standoff_m=ps['body_standoff_m'],
                        stand_a=dict(x_m=cv['stand_a_x_m'], az_deg=cv['stand_a_az_deg'], min_edge_az_deg=round(cv['stand_a_az_deg']-math.degrees(math.atan2(0.5, data['sp12']['r_m'][0])), 1), room_min_az_deg=data['sp12']['az_deg'][0], to_stand_b_m=fixture_gap(fx['SP12_DON_STAND_A'], fx['SP12_DON_STAND_B']),
                                     to_buddy_zone_m=fixture_gap(fx['SP12_DON_STAND_A'], fx['SP12_BUDDY_ZONE'])),
                        buddy_zone=dict(x_m=cv['zone_x_m'], az_deg=cv['zone_az_deg'], operator_station_overlaps=ps['zone_overlap']),
                        reach_suited_min_m=min(suited.values()), reach_suited_worst=worst_suited, reach_unsuited_min_m=min(unsuited.values()),
                        reach_status=worst(*[sp.status(v, margin) for v in rs.values()]), reach_margin_m=rs,
                        operator_components_m=comp, operator_least_m=least_body, operator_least_component=min(comp, key=comp.get), operator_status=sp.status(least_body, margin),
                        head_to_gauge_m=ps['head_to_gauge_m'], gauge_view_status=worst(*['PASS' if v == 'PASS' else 'FAIL' for v in ps['gauge_view_status'].values()]),
                        points=ps['points'], operator=op,
                        note='worst case over both bodies, suited and unsuited, and release / valve / gauge; the Blender study measures the real meshes'))
    return out


def redlines(s, data, V, keys, row, fit, margin, box, panel_ch, cases):
    """SIM-027: keeper variants, SP-12 control relocation variants and the strap-tail readout (SP11-007) for the lead 1.20 m plug."""
    pq = data['sp11_plug']
    kv = keeper_variants(s, data, V, keys, row, fit, margin, panel_ch)
    cv = control_variants(s, data, V, keys, row, fit, margin, box)
    tails = {}
    for name, c in cases.items():
        if c.get('transit'):
            tails[name] = {kk: dict(bore_clearance_m=v['bore_clearance_m'], status=v['bore_status']) for kk, v in c['transit'].items() if kk.split('.')[1] in ('stowed', 'loose')}
    return dict(basis='SIM-027 (owner 2026-10-11 16:45): 15!A152 SP11-005, A153 SP11-006, A154 SP11-007; PASS >= 0.05 m, MARGINAL 0..0.05, FAIL < 0; every variant is a PROTOTYPE study choice',
                keeper=kv, controls_sp12=cv,
                strap_tails=dict(stowed_m=pq['strap_tail_stowed_m'], loose_m=pq['strap_tail_loose_m'], bore_by_case=tails,
                                 note='stowed tails (buckle tucked, 0.05 m beyond the rail) are the model; the loose 0.25 m tails are sensitivity only. Kit +0.036 MARGINAL and the limp casualty -0.099 FAIL are unchanged (geometry did not change).'))


def study_row(s, data, V, keys, row, fit, margin, cases=None):
    q = data['sp11_eva3']; pq = data['sp11_plug']; k = data['rescue_support']
    configure(pq)
    ch = row['chamber']; dr = row['door']; sp12 = data['sp12']; fl = sp12['r_m'][0]
    states, box, meta = plug_states(row, q, pq)
    # --- 1. polar envelope against SP-12 and the fixtures
    bounds, room_m, fx = envelope_room(s, sp12, fit, states)
    fmin = min(fx.values())
    shell_gap = round(ch['inner_bulkhead_a_m']-max(box['a']), 3)          # the plug stays below the inner bulkhead
    kin = dict(sequence=['dogs retract radially (lever, toggle)', f"leaf drops {q['plug_stroke_m']:.2f} m along the seat normal (-a), off the face seal",
                         f"leaf slides {meta['travel_m']:.2f} m toward -az on two rails and a carriage, parks beside the aperture"],
               states=[dict(state=st['state'], drop_m=st['drop_m'], lateral_m=st['lateral_m']) for st in states], envelope_box_chamber=box, meta=meta,
               polar_bounds=bounds, sp12_room_margin_m=room_m, sp12_room_status=sp.status(room_m, margin), sp12_fixtures_m=fx, sp12_fixture_min_m=fmin,
               sp12_fixture_status=sp.status(fmin, margin), under_bulkhead_m=shell_gap, parked_edge_to_bore_m=round(meta['travel_m']-dr['r_leaf']-dr['r_clear'], 3),
               parked_edge_status=sp.status(meta['travel_m']-dr['r_leaf']-dr['r_clear'], margin))
    # --- 2.
    ret = retention(s, row, pq, q)
    # --- 3.
    users = users_chamber(V, keys, row, margin)
    sets_for_gap = []
    for _n, pose, _l in CASES:
        sets_for_gap += body_items(V, keys, row, pose, margin, k, pq)
    pc = chamber_side(s, V, keys, row, sets_for_gap, users, pq, q)
    ps = sp12_side(s, data, V, keys, row, fit, pq, q, box)
    ctrl = dict(chamber=pc, sp12=ps, equalization='a manual valve through the chamber wall (PROTOTYPE, not the hull); sizes, flow and equalization times are Sheets items (OPEN)',
                gauge='a mechanical dial gauge readable without power; range and accuracy OPEN', release='a pull ring on a cable to the dog cam ring; location only')
    reach_all = list(pc['reach_status'].values())+list(ps['reach_status'].values())
    ctrl['reach_status'] = worst(*reach_all) if reach_all else 'PASS'
    # --- 4.
    il = interlock(pq)
    # --- 5.
    cs = {}
    for name, pose, label in CASES:
        if cases is not None and name not in cases:
            continue
        r = case_report(s, V, keys, row, fit, q, pq, margin, (states, box, meta), pc, ps, pose)
        tr = casualty_transit(V, keys, row, pose, margin, k, pq, data['airlock_study']['casualty_tilt_deg'], fl)
        if pose is None:
            door = {kk: v for kk, v in row['door_passage'].items() if v['routine']}
        else:
            door = {kk: v for kk, v in row['door_passage'].items() if kk.endswith('.'+pose)}
        dst = worst(*[v['status'] for v in door.values()])
        sts = [r['plug_status'], r['chamber_panel_status'], dst]
        if tr:
            sts += [v['bore_status'] for kk, v in tr.items() if not kk.endswith('.loose')]+[v['parked_plug_status'] for v in tr.values()]
        cs[name] = dict(label=label, door_status=dst, door_margin_m=min(v['margin_m'] for v in door.values()), transit=tr, **r, status=worst(*sts))
    red = redlines(s, data, V, keys, row, fit, margin, box, pc, cs) if cases is None and abs(row['aperture_m']-pq['aperture_m']) < 1e-9 else None
    return dict(id=row['id'], aperture_m=row['aperture_m'], kinematics=kin, retention=ret, controls=ctrl, interlock=il, cases=cs, redlines=red,
                strap_model=dict(fracs=list(pq['strap_fracs']), band_m=pq['strap_band_m'], stand_off_m=pq['strap_stand_off_m'], tail_stowed_m=pq['strap_tail_stowed_m'],
                                 tail_loose_m=pq['strap_tail_loose_m'], note='PROTOTYPE straps over the suit front between the rails, on the strapped litter cases'))


def study(s, data, V, keys, rows, fit, margin):
    lead = next(r for r in rows if abs(r['aperture_m']-data['sp11_plug']['aperture_m']) < 1e-9)
    out = study_row(s, data, V, keys, lead, fit, margin)
    fails = [n for n, c in out['cases'].items() if c['status'] == 'FAIL']
    out['recheck_135'] = None
    if fails:
        big = next(r for r in rows if abs(r['aperture_m']-data['sp11_eva3']['rescue_m']) < 1e-9)
        rr = study_row(s, data, V, keys, big, fit, margin, cases=fails)
        out['recheck_135'] = dict(cases=fails, aperture_m=big['aperture_m'], results={n: {kk: c[kk] for kk in ('status', 'door_status', 'door_margin_m', 'plug_status', 'chamber_panel_status')}
                                                                                      for n, c in rr['cases'].items()},
                                  retention_derived_reverse_kn=rr['retention']['derived_reverse_kn'])
    out['status'] = ('STUDY / PROTOTYPE: structural flight release HOLD (S&E 15!A134), pressure flight HOLD (43 EVA-062); no hull cutout, certified seal or latch, gas cycling '
                     'or casualty clearance is assumed')
    return out
