"""EVA-003 SP-11 comparison: the two-person chamber at the 1.10 m benchmark, the 1.20 m lead and the 1.35 m rescue comparison, with
the inner-hatch mechanisms, every pose's door passage, the extension latch on the real rigs, the rescue cases and the pressure-boundary
consequences (S&E 43 EVA-056..058/061, 44 EVA3-001..003, 45 G-11..G-15; docs/EVA.md "EVA-003"). Standard library only.

Inputs: the as-built suit hulls and rig joints of references/p1_eva_envelopes.json (validation/eva_fit.py, incl. the EVA-003 poses
latch / pitch / supported and the rescue-support hulls), eva_access.py (door, chamber, layouts) and data/eva_suit.toml [sp11_eva3].
Every result is a geometric readback of disposable study geometry on the existing PROTOTYPE airlock axis: no hatch, seal, latch, medical
or pressure-vessel claim, and nothing is cut into the ship (EVA-061). Gas quantities and pressure physics stay with the Sheets.

Statuses: PASS (at least the 0.05 m study margin), MARGINAL (0 to 0.05 m), FAIL (negative), and per mechanism REJECTED when it breaks an
owner rule. The Blender side (validation/eva_sp11_study.py) checks the mechanisms and the posed rigs in the vehicle and renders them.

  python3 src/wayfarer/eva_sp11.py [--out references/p1_eva_sp11.json]
"""
import argparse
import json
import math
from pathlib import Path

import eva_access as ea
import eva_suit
import human_entry
import hull_geometry
import layout
import spec

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'references/p1_eva_sp11.json'


def status(m, margin):
    return 'PASS' if m >= margin-1e-9 else ('MARGINAL' if m >= -1e-9 else 'FAIL')


# ---------------------------------------------------------------------------------------------------------------------------------
# chamber frame -> vehicle frame (as validation/eva_airlock_study.world): a outward radial at the fitting's angle, p along X, q = X x u

def to_vehicle(fit, a, p, q):
    th = math.radians(fit['theta_deg']); u = (0.0, math.cos(th), math.sin(th)); w = (0.0, -math.sin(th), math.cos(th))
    return (fit['x']+p, u[1]*a+w[1]*q, u[2]*a+w[2]*q)


def polar(v):
    """(x, azimuth deg, r) of a vehicle point."""
    return v[0], math.degrees(math.atan2(v[2], v[1])) % 360.0, math.hypot(v[1], v[2])


# ---------------------------------------------------------------------------------------------------------------------------------
# bodies

def place_joint(h, theta, shift, a_top, pt):
    """A rig-frame point of hull h placed as eva_access.placed places the hull (head outboard, top at a_top): chamber (a, p, q)."""
    zmax = max(v[2] for v in h['verts']); p, q = ea.rot2((pt[0], pt[1]), theta)
    return (a_top-(zmax-pt[2]), p+shift[0], q+shift[1])


def root_top(h_ref, a_top, h):
    """a_top for pose h standing on the same foot restraint (the same rig root) as pose h_ref with its top at a_top."""
    return a_top-max(v[2] for v in h_ref['verts'])+max(v[2] for v in h['verts'])


def grip(jf, shoulder='shoulder_r', hand='hand_r'):
    """The palm on a lever or strap: PALM beyond the rig's wrist, away from its shoulder."""
    w, s = jf[hand], jf[shoulder]; d = math.dist(w, s) or 1.0
    return tuple(wi+(wi-si)/d*ea.PALM for wi, si in zip(w, s))


def circumcentre(a, b, c):
    """Centre of the circle through three 3-D points (the lever pivot from its grip arc)."""
    ab = [y-x for x, y in zip(a, b)]; ac = [y-x for x, y in zip(a, c)]
    n = (ab[1]*ac[2]-ab[2]*ac[1], ab[2]*ac[0]-ab[0]*ac[2], ab[0]*ac[1]-ab[1]*ac[0]); nn = sum(x*x for x in n)
    if nn < 1e-12:
        return tuple((x+y)/2 for x, y in zip(a, c))
    ab2 = sum(x*x for x in ab); ac2 = sum(x*x for x in ac)
    t1 = (ac[1]*n[2]-ac[2]*n[1], ac[2]*n[0]-ac[0]*n[2], ac[0]*n[1]-ac[1]*n[0])
    t2 = (n[1]*ab[2]-n[2]*ab[1], n[2]*ab[0]-n[0]*ab[2], n[0]*ab[1]-n[1]*ab[0])
    return tuple(a[i]+(ab2*t1[i]+ac2*t2[i])/(2*nn) for i in range(3))


def gap(planes, pts):
    """Lower bound of the least distance from points to a convex hull (negative: a point inside)."""
    return min(ea.outside(planes, p) for p in pts)


# ---------------------------------------------------------------------------------------------------------------------------------
# door passage, every pose (EVA-056 H57: real swept passage in ALL poses)

PASSES = [  # (pose, label, required for routine operation, tilts allowed); the work poses (operate, latch, strap, rescue hold) are not
            # passage poses: they are checked inside the chamber (latch)
    ('chamber', 'suited, arms along the body', True, False), ('hatch_pass', 'suited, hands ahead (hatch passage)', True, False),
    ('casualty', 'casualty, free limp (unrestrained)', False, True), ('supported', 'casualty, limbs secured, no support', False, True),
    ('supported_frame', 'casualty on a full-length litter frame', False, True), ('supported_mattress', 'casualty in a vacuum mattress', False, True),
    ('supported_kit', 'casualty on the frame with a med/O2 kit', False, True)]
CASUALTY = ('casualty', 'supported_frame', 'supported_mattress', 'supported_kit')    # the rescue pairings the EVA-003 chamber is sized for


def door_passage(V, D, margin, tilts):
    out = {}
    for k, v in V.items():
        for pose, label, routine, tilt in PASSES:
            if pose not in v:
                continue
            c = ea.passage_circle(v[pose], tilts if tilt else (0.0,)); m = round(D-c['diameter_m'], 3)
            out[f'{k}.{pose}'] = dict(label=label, routine=routine, need_m=c['diameter_m'], tilt_deg=c['tilt_deg'], margin_m=m, status=status(m, margin))
    return out


# ---------------------------------------------------------------------------------------------------------------------------------
# inner-hatch mechanisms (EVA-056 / G-12: the 1.20 m inner leaf swung 0.09 m below the PROTOTYPE SP-12 floor)

def mechanisms(s, fit, dr, ch, q, sp12):
    h = s['human_entry']; clr = h['leaf_swing_clearance_m']; bottom = ch['inner_bulkhead_a_m']; fd = dr['frame_depth']; t = dr['t']
    floor = sp12['r_m'][0]; cabin = eva_suit.load()['telemetry']['cabin_pressure_kpa']['value']; load = round(cabin*math.pi*dr['r_leaf']**2, 1)
    seal = round(2*math.pi*dr['r_leaf'], 2); out = {}
    node = bottom-fd-t-dr['swing_depth_m']-clr
    out['hinged_into_sp12'] = dict(
        concept='EVA-002 plug leaf: hinged on the frame, seats from SP-12, swings 90 deg into SP-12',
        lowest_a_m=round(node, 3), floor_r_m=floor, radial_budget_m=round(node-floor, 3), pressure='SEATED by cabin pressure when the chamber is evacuated',
        reverse_load_kn=0.0, seat_load_kn=load, seal_m=seal, parts='hinge, latch dogs, seal', status='PASS' if node >= floor-1e-9 else 'FAIL',
        note='the swing depth (hinge offset + leaf radius) grows with the aperture')
    rf = q['recess_floor_r_m']
    out['hinged_floor_recess'] = dict(
        concept='the same leaf; the SP-12 floor utility layer is removed under the swing (a local well down to the spine clearance)',
        lowest_a_m=round(node, 3), floor_r_m=rf, radial_budget_m=round(node-rf, 3), recess_depth_m=round(max(0.0, floor-node), 3),
        recess_plan_m=[round(2*dr['r_leaf'], 2), round(dr['r_hinge']+dr['r_leaf'], 2)], pressure='SEATED (unchanged)', reverse_load_kn=0.0,
        seat_load_kn=load, seal_m=seal, parts='hinge, latch dogs, seal; floor well, utilities rerouted round it',
        status='PASS' if node >= rf-1e-9 else 'FAIL',
        note='uses up the spine mechanical clearance as the only margin; a trip/snag well in the room floor; utilities leave the floor there')
    drop = q['plug_stroke_m']; rail = q['slide_rail_depth_m']; low = bottom-fd-t-drop-rail-clr
    travel = dr['r_clear']+dr['r_leaf']+clr                  # the leaf centre moves this far in the bulkhead plane to clear the aperture
    a_park = bottom-fd-drop-t/2
    parks = {}
    for d in q['slide_directions']:
        sgn = 1.0 if d[0] == '+' else -1.0; along = d[1:] == 'X'
        cp = (a_park, sgn*travel if along else 0.0, 0.0 if along else sgn*travel)
        corners = [(cp[0]+da, cp[1]+dp, cp[2]+dq) for da in (-(t/2+rail), t/2) for dp in (-dr['r_leaf']-.05, dr['r_leaf']+.05)
                   for dq in (-dr['r_leaf']-.05, dr['r_leaf']+.05)]
        V = [polar(to_vehicle(fit, *c)) for c in corners]; xs = [v[0] for v in V]; az = [v[1] for v in V]; rr = [v[2] for v in V]
        inside = sp12['x_m'][0] <= min(xs) and max(xs) <= sp12['x_m'][1] and sp12['az_deg'][0] <= min(az) and max(az) <= sp12['az_deg'][1] \
            and sp12['r_m'][0] <= min(rr) and max(rr) <= sp12['r_m'][1]
        parks[d] = dict(centre_chamber=[round(x, 3) for x in cp], x_m=[round(min(xs), 3), round(max(xs), 3)], az_deg=[round(min(az), 1), round(max(az), 1)],
                        r_m=[round(min(rr), 3), round(max(rr), 3)], inside_sp12=inside, corners_chamber=[[round(x, 3) for x in c] for c in corners])
    out['parallel_plug_slide'] = dict(
        concept='a plug door on a parallel linkage: the leaf drops off its seat by a short stroke and slides sideways in the bulkhead plane '
                '(aircraft / bus plug-door kinematics); it never swings toward the floor',
        lowest_a_m=round(low, 3), floor_r_m=floor, radial_budget_m=round(low-floor, 3), stroke_m=drop, travel_m=round(travel, 3), parking=parks,
        lead_direction=q['slide_lead'], lead_inside_sp12=parks[q['slide_lead']]['inside_sp12'],
        pressure='SEATED (a plug, unchanged)', reverse_load_kn=0.0, seat_load_kn=load, seal_m=seal,
        parts='linkage arms, two rails and a carriage, latch dogs, seal; the seal leaves its seat before any slide (no seal scrub)',
        status='PASS' if low >= floor-1e-9 and any(p['inside_sp12'] for p in parks.values()) else 'FAIL',
        note='needs a clear parking pocket one leaf wide beside the aperture (the Blender study checks it against the ship and the fixtures)')
    grow = dr['swing_depth_m']+clr
    b3 = bottom-grow; low3 = b3-fd
    out['hinged_into_chamber'] = dict(
        concept='the inner leaf hinged to open up into the chamber (no swing into SP-12): the chamber grows by its swing',
        lowest_a_m=round(low3, 3), floor_r_m=floor, radial_budget_m=round(low3-floor, 3), chamber_length_added_m=round(grow, 3),
        pressure='UNSEATED: cabin pressure pushes the leaf off its seat whenever the chamber is below cabin pressure; the latches alone carry it',
        reverse_load_kn=load, seat_load_kn=load, seal_m=seal, parts='hinge, latch dogs rated for the full reverse load, seal',
        status='REJECTED', note='a latch-only closure under the full cabin load (15!G127 forbids untested reverse-load latch-only closures); '
                                'also longer chamber, longer cycle volume')
    half = dr['r_hinge']+clr; low4 = bottom-fd-t-half
    out['bi_parting'] = dict(
        concept='two half leaves hinged at opposite rims, meeting on a centre seam: each swings half as deep',
        lowest_a_m=round(low4, 3), floor_r_m=floor, radial_budget_m=round(low4-floor, 3), clear_aperture_with_mullion_m=round((dr['clear_m']-q['mullion_m'])/2, 3),
        pressure='a seam beam (mullion) across the opening, or a latch-only seam between the leaves', reverse_load_kn=None, seat_load_kn=load,
        seal_m=round(seal+2*dr['r_leaf'], 2), parts='two hinges, two latch sets, seam seal or mullion',
        status='REJECTED', note=f"with a {q['mullion_m']} m mullion no suited body passes either half; without it the seam is a latch-only seal")
    for m in out.values():                 # the emergency case every inner hatch shares (ECLSS-REC2, references/ECLSS_REC2_CLOSURES.md)
        m['sp12_loss_reverse_kn'] = load
        m['sp12_loss_note'] = ('SP-12 loses pressure while the chamber is at cabin pressure: the inner closure is loaded off its seat; it needs '
                               'a bidirectional rating (ECLSS-REC2 option 1) or a second closure; reverse_load_kn is the normal-cycle case')
    return out


# ---------------------------------------------------------------------------------------------------------------------------------
# extension latch on the real rigs (EVA-057, EVA3-002)

PITCH = [None]                      # the backup's body pitch on the rig (eva_suit.latch_pitch), set by study()


def latch(V, keys, occupants, ch, dr, q, margin, mob):
    """For each occupant: its rig's own hand positions in eva_latch_extension, placed on the routine foot restraint, give the lever
    pivot, its wall bracket, the torque tube up to the outer frame, the strap on the outer leaf; the arm and helmet against the wall,
    the partner and the leaf's sweep. Then the backup: the rig pitched by the foot restraint (eva_latch_pitch) in the same chamber."""
    R = ch['clear_radius_m']; out = {}; sweep_hinge_a = ch['leaf_face_a_m']+dr['t']
    sweep = ea.leaf_sweep(dr, math.radians(ch['outer_leaf']['hinge_deg']), sweep_hinge_a)
    for i, (k, (hull, th, sh)) in enumerate(zip(keys, occupants)):
        v = V[k]; top = ch['body_top_a_m']; lt = root_top(v['chamber'], top, v['latch']); st_ = root_top(v['chamber'], top, v['strap'])
        P = lambda pt: place_joint(v['latch'], th, sh, lt, pt); S = lambda pt: place_joint(v['strap'], th, sh, st_, pt)
        g0, g1, g2 = (P(grip(f, 'shoulder_l', 'hand_l')) for f in v['latch']['joints_frames'])
        s_hi, s_lo = (S(grip(f, 'shoulder_l', 'hand_l')) for f in v['strap']['joints_frames'])
        piv = circumcentre(g0, g1, g2); rho = lambda x: math.hypot(x[1], x[2])
        verts, planes = ea.placed(v['latch'], th, sh, lt); sverts, _ = ea.placed(v['strap'], th, sh, st_)
        other = [(h2, t2, s2) for j, (h2, t2, s2) in enumerate(occupants) if j != i]
        partner = [ea.placed(v2['chamber'], t2, s2, top)[1] for (h2, t2, s2), v2 in ((o, V[keys[1-i]]) for o in other)]
        wall = round(R-max(rho(p) for p in verts+sverts), 3)
        grips = [g0, g1, g2]
        lever_wall = round(R-max(rho(g) for g in grips)-q['glove_clear_m'], 3)
        pp = partner[0] if partner else None
        partner_gap = round(gap(pp, verts+sverts), 3) if pp else None
        grip_partner = round(min(ea.outside(pp, g) for g in grips+[s_hi, s_lo]), 3) if pp else None
        sweep_gap = round(min(ea.outside(planes, p) for p in sweep), 3)
        strap_on_leaf = (round(min(rho(s_hi), dr['r_leaf']-.05), 3))
        out[k] = dict(
            hand='left on the lever and the strap (right hand on a handhold ahead of the waist, feet in the restraint)', routine_position=True,
            lever_pivot_chamber=[round(x, 3) for x in piv], lever_grip_radius_m=round(math.dist(piv, g0), 3),
            lever_station_a_m=round(piv[0], 3), bracket_m=round(R-rho(piv), 3), bracket_ok=R-rho(piv) <= q['bracket_max_m'],
            lever_to_wall_m=lever_wall, lever_status=status(lever_wall, 0.0),
            torque_tube_m=round(ch['leaf_face_a_m']+dr['t']-piv[0], 3),            # up the wall to the latch drive on the outer frame
            strap_grip_high_a_m=round(s_hi[0], 3), strap_length_m=round(ch['leaf_face_a_m']-s_hi[0], 3), strap_attach_rho_m=strap_on_leaf,
            body_to_wall_m=wall, body_status=status(wall, margin), partner_gap_m=partner_gap,
            partner_status=status(partner_gap, 0.0) if partner_gap is not None else None, grips_to_partner_m=grip_partner,
            body_to_leaf_sweep_m=sweep_gap, sweep_status=status(sweep_gap, margin),
            strap_note='the strap hand meets the shut leaf and follows it down as it swings in: the hand moves with the leaf, the body stays below its sweep',
            shoulder_flex_ok=mob['eva_latch_extension']['shoulder']['ok'], shoulder_flex_max_deg=mob['eva_latch_extension']['shoulder']['max_deg'],
            shoulder_limit_deg=mob['eva_latch_extension']['shoulder']['limit_deg'])
        # backup: pitched by the articulating foot restraint, alone in the chamber (the partner out of the way) and with the partner
        pv = v['pitch']; pt = root_top(v['chamber'], top, pv); best = None
        for ang in range(0, 360, 15):
            pverts, _ = ea.placed(pv, th+ang, sh, pt); r_out = max(rho(p) for p in pverts)
            r_alone = max(rho((p[0], p[1]-sh[0], p[2]-sh[1])) for p in pverts)
            if best is None or r_alone < best[1]:
                best = (ang, r_alone, r_out)
        out[k]['pitch_backup'] = dict(pitch_deg=PITCH[0], needed_radius_alone_m=round(best[1], 3), chamber_radius_m=round(R, 3),
                                      status='FAIL' if best[1] > R-margin else status(R-best[1], margin),
                                      note='the rigid suited body tilted about its feet sweeps far across the chamber axis')
    return out


# ---------------------------------------------------------------------------------------------------------------------------------
# rescue (EVA-058, EVA3-003)

def rescue(s, V, keys, D, dr, ch, f, data, margin, doors):
    """Patient routes through this aperture and chamber. The casualty passes the doors alone, head first, moved by the rescuer and
    a tether; the chamber must hold the casualty (as secured) and the rescuer together for the cycle."""
    st = data['airlock_study']; out = {}; fr = data['sp12']['r_m'][0]
    worst = lambda pose: min((v for kk, v in doors.items() if kk.endswith('.'+pose)), key=lambda v: v['margin_m'])
    cases = [('full_length_supported', 'supported_frame', 'full-length supported casualty on a litter frame (EVA-058 preferred)'),
             ('unrestrained_limp', 'casualty', 'unrestrained limp casualty (free neutral body posture)'),
             ('stabilized_no_support', 'supported', 'limbs secured, straight and neutral, no support (permissible only medically)'),
             ('vacuum_mattress', 'supported_mattress', 'casualty in a vacuum mattress'),
             ('with_equipment', 'supported_kit', 'casualty on the frame with a medical/O2 kit')]
    for name, pose, label in cases:
        w = worst(pose); sets = rescue_sets(V, keys, margin, (pose,))
        need = ea.chamber(s, f, dr, sets, margin, st['step_m'], st['hinge_steps'], fr)
        fits = need['clear_radius_m'] <= ch['clear_radius_m']+1e-9 and need['clear_length_m'] <= ch['clear_length_m']+1e-9
        out[name] = dict(label=label, door_need_m=w['need_m'], door_margin_m=w['margin_m'], door_status=w['status'],
                         chamber_need=[need['clear_diameter_m'], need['clear_length_m']], chamber_has=[ch['clear_diameter_m'], ch['clear_length_m']],
                         chamber_fits=fits, status='PASS' if w['status'] == 'PASS' and fits else ('MARGINAL' if w['status'] == 'MARGINAL' and fits else 'FAIL'))
    out['patient_and_rescuer'] = dict(label='casualty (each secured case) and the assisting astronaut together in the chamber for the cycle',
                                      status='PASS' if all(out[c]['chamber_fits'] for c, _, _ in cases) else 'FAIL',
                                      note='the EVA-003 chamber is sized for the routine pair and every rescue pairing; the door passage is the limit')
    out['no_power'] = dict(label='recovery with limited or no electrical power',
                           requires=['manual latch lever and opening strap (both hatches)', 'manual depress/equalization valve at each bulkhead, at the lever station',
                                     'mechanical door interlock (no power needed)', 'tether hand-over-hand moves of the casualty'],
                           status='STUDY: mechanically possible in this layout (the lever stations are reachable from the routine positions); '
                                  'valve sizes, equalization times and the gas budget are Sheets items (OPEN)')
    return out


# ---------------------------------------------------------------------------------------------------------------------------------

def rescue_sets(V, keys, margin, poses=CASUALTY):
    out = []
    for pose in poses:
        for a, b in ((keys[0], keys[1]), (keys[1], keys[0])):
            pr = ea.pair_layout(V[a]['rescue'], V[b][pose], margin)
            out.append([(V[a]['rescue'], pr['theta'], pr['shift_a']), (V[b][pose], pr['theta']+180.0, pr['shift_b'])])
    return out


def eva3_chamber(s, f, V, keys, dr, data, margin):
    """The EVA-003 two-person chamber: sized for the routine pair and every rescue pairing (rescuer with the free limp casualty, the
    casualty on the litter frame, in the vacuum mattress, on the frame with a kit), with the routine pair's placement."""
    st = data['airlock_study']; pl = ea.pair_layout(V[keys[0]]['chamber'], V[keys[1]]['chamber'], margin)
    routine = [(V[keys[0]]['chamber'], pl['theta'], pl['shift_a']), (V[keys[1]]['chamber'], pl['theta']+180.0, pl['shift_b'])]
    ch = ea.chamber(s, f, dr, [routine]+rescue_sets(V, keys, margin), margin, st['step_m'], st['hinge_steps'], data['sp12']['r_m'][0])
    return ch, routine


def shell(ch, dr, fit, q, s):
    R = ch['clear_radius_m']; L = ch['clear_length_m']; w = fit['wall_m']
    area = 2*math.pi*(R+w)*L+2*math.pi*(R+w)**2
    return dict(clear_volume_m3=ch['volume_m3'], shell_m2=round(area, 1), shell_mass_t=round(area*q['shell_kg_m2']/1e3, 2),
                fitting_outside_m=ch['fitting_outside_m'], existing_fitting_outside_m=ch['existing_fitting_outside_m'],
                fits_existing_fitting=ch['fitting_outside_m'] <= ch['existing_fitting_outside_m']+1e-9,
                hull_penetration_outside_m=dr['hull_penetration_outside_m'],
                basis='PROTOTYPE shell areal mass (SERV-002 value), no MMOD, frames or hatches; cycle gas mass is a Sheets item (OPEN)')


def study(root=ROOT):
    s = spec.load(root)[0]; data = eva_suit.load(root); q = data['sp11_eva3']; env = ea.load_envelopes(root/'references/p1_eva_envelopes.json')
    V = env['variants']; keys = list(V); acc = ea.study(root, env); margin = data['access']['suit_margin_m']; tilts = data['airlock_study']['casualty_tilt_deg']
    f = next(x for x in hull_geometry.service_fittings(s) if x['name'] == 'Airlock_EVA')
    lib = eva_suit.actions(1.75, data, 30); mob = eva_suit.mobility_report(lib, data['mobility']); PITCH[0] = lib['eva_latch_pitch']['pitch_deg']
    rows = []
    for D in (q['benchmark_m'], q['lead_m'], q['rescue_m']):
        r = next(x for x in acc['sp11'] if x['layout'] == 'two_person' and abs(x['aperture_m']-D) < 1e-9)
        dr = r['door']; fit = r['fitting']; ch, occupants = eva3_chamber(s, f, V, keys, dr, data, margin)
        occ = [ea.occ(V, b, ch['body_top_a_m']) for b in occupants]
        sized_by = max(CASUALTY+('routine',), key=lambda c: ea.chamber(s, f, dr, [occupants] if c == 'routine' else rescue_sets(V, keys, margin, (c,)), margin,
                                                                       data['airlock_study']['step_m'], data['airlock_study']['hinge_steps'], data['sp12']['r_m'][0])['clear_length_m'])
        doors = door_passage(V, D, margin, tilts)
        mech = mechanisms(s, fit, dr, ch, q, data['sp12'])
        rows.append(dict(id=f'EVA3_SP11_{int(round(D*100)):03d}', aperture_m=D,
                         role={q['benchmark_m']: 'MARGINAL benchmark (45 G-11)', q['lead_m']: 'lead study (45 G-13)', q['rescue_m']: 'rescue comparison (45 G-14)'}[D],
                         door=dr, chamber=ch, chamber_length_set_by=sized_by,
                         eva002_chamber=dict(clear_diameter_m=r['chamber']['clear_diameter_m'], clear_length_m=r['chamber']['clear_length_m'],
                                             volume_m3=r['chamber']['volume_m3'], basis='EVA-002: routine pair and the free-limp rescue pairings only'),
                         fitting=fit, occupants=occ,
                         rescue_occupants=[[ea.occ(V, b, ch['body_top_a_m']) for b in st_] for st_ in rescue_sets(V, keys, margin)],
                         door_passage=doors, routine_door_ok=all(v['status'] == 'PASS' for v in doors.values() if v['routine']),
                         mechanisms=mech, latch=latch(V, keys, occupants, ch, dr, q, margin, mob),
                         rescue=rescue(s, V, keys, D, dr, ch, f, data, margin, doors), shell=shell(ch, dr, fit, q, s)))
    import eva_sp11_plug
    plug = eva_sp11_plug.study(s, data, V, keys, rows, rows[0]['fitting'], margin)
    return dict(contract='eva_sp11 v2', sliding_plug=plug, status='STUDY: geometric readback of disposable SP-11 alternatives; no pressure-shell change, no hatch, '
                                                'latch, medical or flight release (EVA-061)', margin_m=margin, rows=rows, preference=prefer(rows, q))


def mechanism_rows(root=ROOT):
    """The inner-hatch mechanisms of every compared aperture on the same door, fitting and EVA-003 chamber as study(), without the latch,
    rescue, door-passage and shell searches (the fast invariant screen; study() is the full comparison)."""
    s = spec.load(root)[0]; data = eva_suit.load(root); q = data['sp11_eva3']; env = ea.load_envelopes(root/'references/p1_eva_envelopes.json')
    V = env['variants']; keys = list(V); acc = ea.study(root, env); margin = data['access']['suit_margin_m']
    f = next(x for x in hull_geometry.service_fittings(s) if x['name'] == 'Airlock_EVA')
    rows = []
    for D in (q['benchmark_m'], q['lead_m'], q['rescue_m']):
        r = next(x for x in acc['sp11'] if x['layout'] == 'two_person' and abs(x['aperture_m']-D) < 1e-9)
        ch, _ = eva3_chamber(s, f, V, keys, r['door'], data, margin)
        rows.append(dict(id=f'EVA3_SP11_{int(round(D*100)):03d}', aperture_m=D, mechanisms=mechanisms(s, r['fitting'], r['door'], ch, q, data['sp12'])))
    return rows


def prefer(rows, q):
    """The direction for owner review (never a promotion): the lead aperture with the best non-rejected inner-hatch mechanism, the
    rescue comparison's result, and what stays open."""
    out = {}
    for r in rows:
        ok = [k for k, m in r['mechanisms'].items() if m['status'] == 'PASS']
        out[r['id']] = dict(routine_door_ok=r['routine_door_ok'], mechanisms_pass=ok,
                            latch_ok=all(l['lever_status'] != 'FAIL' and l['body_status'] != 'FAIL' and (l['partner_status'] or 'PASS') != 'FAIL'
                                         and l['shoulder_flex_ok'] for l in r['latch'].values()),
                            rescue={k: v['status'] for k, v in r['rescue'].items() if isinstance(v, dict) and 'status' in v and k != 'no_power'})
    return out

# ---------------------------------------------------------------------------------------------------------------------------------
# SIM-027: references/p1_access_seg_sp11_sp12.json (segment table for the integrated access study)

SEG_OUT = ROOT/'references/p1_access_seg_sp11_sp12.json'
ALL_STATES = ['0g', 'spin', 'stopped', 'locked_1.5g']
BODY_STATES = ['0g', 'stopped']
CASE_LABEL = dict(routine_pair='routine pair', limp_casualty='unrestrained limp casualty', limbs_secured='limbs secured, no support', litter_frame='casualty on the litter frame (strapped)',
                  vacuum_mattress='vacuum mattress (strapped)', frame_with_kit='litter frame with med/O2 kit (strapped)')


def seg_status(m):
    return None if m is None else ('PASS' if m >= 0.05-1e-9 else ('MARGINAL' if m >= -1e-9 else 'FAIL'))


def access_segments(root=ROOT):
    """Segment table: least_m is the MINIMUM over everything evaluated for that segment and variant (RINGB-006: worst case, not a chosen pose)."""
    import json as _j
    sp = _j.loads((root/'references/p1_eva_sp11.json').read_text()); sl = sp['sliding_plug']; red = sl['redlines']
    vp = root/'references/p1_eva_sp11_vehicle.json'; veh = _j.loads(vp.read_text()) if vp.exists() else {}; vr = veh.get('redlines', {})
    ep = root/'references/p1_eva_exits.json'; ex = _j.loads(ep.read_text()) if ep.exists() else {}; turn = ex.get('sp12_redline_turn', {}).get('variants', {})
    segs = []

    def add(id_, route, states, variant, case, least, worst_over, nearest, note, spread=None, status=None):
        segs.append(dict(id=id_, route=route, states=states, variant=variant, case=case, least_m=None if least is None else round(least, 3),
                         status=status or seg_status(least) or 'OPEN', worst_case_over=worst_over, seed_spread_m=spread, nearest=nearest, note=note))
    # --- SP-11 keeper and the swept envelope
    for k in red['keeper']:
        add(f"SP11.keeper_drop.{k['id']}", 'SP-11', ALL_STATES, k['id'], 'leaf drop vs the keeper lugs under the frame seat', k['keeper_clearance_m'],
            ['stroke minus lug hang (dog + ledge - recess): a dimension chain; tolerance stack, thermal growth and wear are OPEN'], 'keeper lug underside',
            f"{k['what']}; stroke {k['stroke_m']:.2f} m, lug hang {k['lug_hang_m']:.3f} m. PROTOTYPE study value, no keeper change to the model before FEA and clearance pass (owner 15!A153).")
        worst_case = min(k['cases'], key=lambda c: k['cases'][c]['plug_to_bodies_m']); loose = min(c['plug_to_bodies_loose_straps_m'] for c in k['cases'].values())
        add(f"SP11.plug_envelope_bodies.{k['id']}", 'SP-11', BODY_STATES, k['id'], f"swept envelope to bodies, all six cases (least: {CASE_LABEL[worst_case]})", k['plug_to_bodies_min_m'],
            ['6 cases (routine pair incl. lever and strap poses, limp, limbs secured, litter frame, vacuum mattress, kit frame)', 'swept states: seated, dropped, 8 lateral samples to the park',
             'both body sizes, both pairings', 'stowed strap tails'], 'plug swept envelope vs hull planes (lower bound)',
            f"hull-plane model; loose 0.25 m tails (sensitivity only) give {loose:.3f} m. Envelope depth {k['envelope_a_m'][0]:.3f}..{k['envelope_a_m'][1]:.3f} m; SP-12 room margin {k['sp12_room_margin_m']:+.3f} m, fixtures {k['sp12_fixture_min_m']:.3f} m.")
        m = vr.get('keeper', {}).get(k['id'])
        if m:
            least = min(m['envelope_least_m'], m['parked_leaf_carriage_least_m'])
            add(f"SP11.plug_envelope_meshes.{k['id']}", 'SP-11', BODY_STATES, k['id'], 'real suit / litter / strap meshes to the plug envelope, parked leaf and carriage', least,
                ['routine standing, lever and strap poses (first 6 frames each)', 'both rescue pairings on the litter with stowed straps', 'casualty centred in the aperture at depths 0-1.2 m', 'SP-12 suited operators'],
                m['envelope_least_at'] if m['envelope_least_m'] <= m['parked_leaf_carriage_least_m'] else m['parked_leaf_carriage_least_at'],
                f"Blender meshes; envelope least {m['envelope_least_m']:.3f}, parked leaf/carriage least {m['parked_leaf_carriage_least_m']:.3f}. Vehicle intersections: {m['vehicle_intersects'] or 'none'}.")
    # --- aperture passage with stowed strap tails (SP11-007)
    for name, c in sl['cases'].items():
        vals = {}
        if c.get('transit'):
            vals = {kk: v['bore_clearance_m'] for kk, v in c['transit'].items() if kk.endswith('.stowed')}
            vals.update({kk+'.parked': v['parked_plug_clearance_m'] for kk, v in c['transit'].items() if kk.endswith('.stowed')})
        vals['door_passage'] = c['door_margin_m']; nm = min(vals, key=vals.get)
        loose = [v['bore_clearance_m'] for kk, v in (c.get('transit') or {}).items() if kk.endswith('.loose')]
        add(f'SP11.aperture_passage.{name}', 'SP-11', BODY_STATES, 'all keeper variants (aperture geometry unchanged)', CASE_LABEL[name], vals[nm],
            ['door passage poses', 'both body sizes', 'casualty tilts', 'stowed strap tails (0.05 m beyond the rail)'], nm,
            ('Unchanged by the redline variants; never widened. ' + (f'Loose 0.25 m tails would give {min(loose):+.3f} m (sensitivity; tails stow positively).' if loose else '')))
    r135 = sl.get('recheck_135')
    if r135:
        add('SP11.aperture_passage.limp_casualty_1.35m', 'SP-11', BODY_STATES, '1.35 m comparator', CASE_LABEL['limp_casualty'], 0.026,
            ['door passage and aperture bore at 1.35 m'], 'aperture bore (EVA3_REPORT section 11 table: +0.026 / +0.065; the JSON door margin is +%.3f)' % r135['results']['limp_casualty']['door_margin_m'],
            'Comparator only, recorded value from EVA3_REPORT section 11; the 1.20 m limp case stays FAIL.')
    ch = sl['controls']['chamber']
    add('SP11.controls_chamber.reach', 'SP-11', BODY_STATES, 'published (unchanged by SIM-027)', 'chamber-side clusters, suited and unsuited, rescuers', min(ch['reach_margin_m'].values()),
        ['3 controls', 'suited, unsuited and rescuer users', 'nearest cluster'], 'reach margin = reach minus nearest-shoulder distance', f"body gap {ch['body_gap_m']:.3f} m; head to gauge limit 1.0 m")
    # --- SP-12 control cluster variants
    for c in red['controls_sp12']:
        a = c['stand_a']; z = c['buddy_zone']
        note = (f"{c['what']}. Station a {c['station_a_m']:.1f} m, angle {c['angle_deg']:.0f} deg; layout {c['layout']}. Stand A at X {a['x_m']:.2f} az {a['az_deg']:.0f} (its box edge reaches az {a['min_edge_az_deg']:.1f} "
                f"against the room wall at az {a['room_min_az_deg']:.0f}: the prototype stands already overhang it), stand A to stand B {a['to_stand_b_m']:.3f} m (touching), stand A to buddy zone {a['to_buddy_zone_m']:.3f} m. "
                f"Buddy zone X {z['x_m']:.2f} az {z['az_deg']:.0f}: operator station overlaps {z['operator_station_overlaps'] or 'none'}.")
        add(f"SP12.control_reach.{c['id']}", 'SP-12', BODY_STATES, c['id'], 'suited and unsuited, both bodies, release / valve / gauge', min(c['reach_suited_min_m'], c['reach_unsuited_min_m']),
            ['2 bodies x suited/unsuited', '3 controls', 'station search'], c['reach_suited_worst'], note + f" Suited least {c['reach_suited_min_m']:+.3f}, unsuited least {c['reach_unsuited_min_m']:+.3f}; head to gauge max {max(c['head_to_gauge_m'].values()):.2f} m.")
        mm = vr.get('controls', {}).get(c['id'])
        parts = dict(c['operator_components_m'])
        if mm:
            parts = {f'hull:{kk}': v for kk, v in parts.items()}; parts.update({f'mesh:{kk}': v for kk, v in mm['components_least_m'].items()})
        nm = min(parts, key=parts.get)
        add(f"SP12.operator_clearance.{c['id']}", 'SP-12', BODY_STATES, c['id'], 'suited operator on the SP-12 floor at the cluster', parts[nm],
            ['2 suited bodies (hull model: also unsuited)', 'room, chamber outer wall, plug envelope, fixtures (solid), panel plate', 'hull vertices and Blender meshes'], nm,
            'Least of the hull model and the real meshes over room, wall, plug envelope, fixtures and panel plate. ' + note)
    # --- SP-12 litter turn
    groups = {'turn: SP-11 chamber, aperture, corner, floor run to the lowering station': ['turn: chamber, aperture, corner, floor run to the lowering station'],
              'lowering through the SP-12 slot': ['lowering through the slot'], 'aft runs in the extension and the built trunk': ['run aft in the extension', 'run aft in the built trunk'],
              'rescuers (companion route, whole route)': ['rescuers: turn and floor run', 'rescuers: lowering', 'rescuers: aft runs']}
    carrier_lbl = dict(S='S suited casualty on the full-length frame', A='A rigid litter 2.00 x 0.55 x 0.30 m')
    for vid, row in turn.items():
        for cid, legs in row['legs'].items():
            for gname, members in groups.items():
                per = [[legs[m]['least_by_seed_m'][i] for m in members] for i in range(len(legs[members[0]]['least_by_seed_m']))]
                by_seed = [min(x) for x in per]; least = min(by_seed); worst = min(members, key=lambda m: legs[m]['least_m']); lw = legs[worst]
                add(f"SP12.litter_turn.{vid}.{cid}.{gname.split(':')[0].split(' ')[0]}", 'SP-12', BODY_STATES, vid, f'{carrier_lbl[cid]}; {gname}', least,
                    [f'seeds {legs[members[0]]["seeds"]} (sampled-pose search, cap 0.10 m = at least)', 'poses along the route', 'carrier and rescuer capsules', 'trunk fixtures from the saved vehicle'], lw.get('nearest'),
                    f"{row['what']}; fit-out {row['spec']['fitout']}, staff {row['spec']['staff']}, route {row['spec']['route']}. Vehicle screen of the slot: {row['vehicle']['status']} {row['vehicle'].get('hits') or ''}; "
                    f"ideal closure load {row['closure']['ideal_load_kn_80kpa']} kN (DIAGNOSTIC); spine-core cut {row['spine_core_cut_x_m']} m (OPEN). Sampled poses, not a motion proof.",
                    spread=[min(by_seed), max(by_seed)])
    for st_ in ('spin', 'locked_1.5g'):
        add(f'SP12.litter_turn.{st_}', 'SP-12', [st_], 'all', 'S and A carriers, SP-11 to SP-12 turn', None,
            ['not evaluated'], None, 'OPEN: no spin or 1.5 g geometry (the SP-12 floor direction, hoist line and X-vertical attitude are not modelled); release needs the owner state rules (15!A126).', status='OPEN')
    return dict(study='SIM-027 SP-11 keeper / SP-12 controls / SP-12 litter turn segments (owner 2026-10-11 16:45: 15!A152:A154 SP11-005..007, 15!A157 DIST-005)',
                source=['references/p1_eva_sp11.json', 'references/p1_eva_sp11_vehicle.json', 'references/p1_eva_exits.json'], segments=segs)


def main_segments():
    import json as _j
    r = access_segments(); SEG_OUT.write_text(_j.dumps(r, indent=1)+'\n'); print(len(r['segments']), 'segments ->', SEG_OUT)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, default=OUTPUT); ap.add_argument('--segments', action='store_true', help='write references/p1_access_seg_sp11_sp12.json from the saved study files'); a = ap.parse_args()
    if a.segments:
        return main_segments()
    r = study(); a.out.write_text(json.dumps(r, indent=1)+'\n')
    for row in r['rows']:
        print(row['id'], row['role'], 'chamber', row['chamber']['clear_diameter_m'], row['chamber']['clear_length_m'], row['chamber']['volume_m3'],
              'set by', row['chamber_length_set_by'], 'eva002', row['eva002_chamber'], 'budget', row['chamber']['radial_budget_m'])
        print('  doors', {k: (v['margin_m'], v['status']) for k, v in row['door_passage'].items()})
        print('  mech', {k: (m['radial_budget_m'], m['status']) for k, m in row['mechanisms'].items()})
        print('  latch', {k: (l['bracket_m'], l['lever_to_wall_m'], l['body_to_wall_m'], l['partner_gap_m'], l['body_to_leaf_sweep_m'], l['pitch_backup']['status'],
                              l['pitch_backup']['needed_radius_alone_m']) for k, l in row['latch'].items()})
        print('  rescue', {k: (v.get('door_margin_m'), v.get('chamber_need'), v['status'][:40]) for k, v in row['rescue'].items()})
        print('  shell', row['shell'])
    print(json.dumps(r['preference'], indent=1))
    sl = r['sliding_plug']; print('sliding plug', {n: (c['status'], c['plug_to_bodies_m'], c['chamber_panel_to_bodies_m'], c['door_margin_m']) for n, c in sl['cases'].items()},
                                  'reverse', sl['retention']['derived_reverse_kn'], 'reach', sl['controls']['reach_status'], 'recheck', sl['recheck_135'])


if __name__ == '__main__':
    main()
