"""ECLSS-REC2 (S&E 15_MODEL_INTERFACES!A127, owner answer 2026-10-11; follow-up of ECLSS-REC, 15!A124): reverse-load closures and the
ring-local gas reserve. NONCANON comparative study; no model geometry, data file, generator or saved asset changes.

The owner approves a comparison of (option 1) bidirectionally rated hatches against (option 2) an independent reverse-seating secondary
closure, prefers a protected ring-local reserve R1 for the spinning emergency with stop/index transfer R4 for recharge and backup, lets R2 be
compared, does not adopt R3 (essential rotary gas union) and asks for the spine and refuge seat sides; remote isolation, controlled
equalization, relief and leak check are required. Release rule: no untested reverse-load latch-only closure, no gas added to an actively
leaking sector, no access through evacuated strips. Sheets owns reserve and pressure physics: no gas quantity, tank size, flow, time or mass
is computed here.

What this reads (built PROTOTYPE geometry; the EVA-003 district closures from references/p1_eva_district.json and p1_eva_sp11.json, labelled
STUDY):
  survey()     every pressure closure: seat side, normal and reverse Delta-p case, reverse load at the BASELINE 80 kPa cabin x seated leaf
               area (DERIVED, never a structural release), and whether the reverse case is held by latches alone today.
  options()    per latch-only closure family, option 1 vs option 2 with the envelopes measured in the vehicle (radial stacks, frame bands,
               parking pockets checked against the ship's rotor-local, stationary and swept obstacles).
  reserve()    R1 candidate envelopes on each ring's rotor drum (forward of the spoke plane, between the crew tubes), its path to every
               sector with the isolation / equalization / relief / leak-check points; R4, R2 and R3 compared.
  prohibitions()  the three release rules checked on every proposed path.

    python3 src/wayfarer/studies/eclss_rec2.py [--json references/p1_eclss_rec2.json] [--svg references/ECLSS_REC2_MAP.svg]
"""
from pathlib import Path
import argparse
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/studies')]
from spec import load
import crew_transfer as ct
import eclss_recovery as er
import habitat_ring
import human_entry as he
import layout
import rotor_interface as ri
import storeroom

CONTRACT = 'ECLSS-REC2-2026-10-11'
STATUS = 'NONCANON COMPARATIVE STUDY (PREFERRED STUDY / GAS MARGINS OPEN, 15!A127); no geometry, hatch, latch, seal or gas release'
DERIVED = 'cabin 80 kPa (BASELINE) x seated leaf area; DERIVED, not a structural release'


def kN(s, r):
    return None if r is None else round(s['habitat']['atmosphere']['cabin_pressure_kpa']*math.pi*r*r, 1)


def r2(x):
    return None if x is None else round(x, 3)


# ---------- (a) closure survey ---------------------------------------------------------------------------------------------------------

def _study_closures(s):
    """EVA-003 forward-district closures (STUDY, references/p1_eva_district.json topology, p1_eva_sp11.json for SP-11)."""
    lap = s['human_entry']['hatch_leaf_overlap_m']
    sp11 = {r['id']: r for r in json.loads((ROOT/'references/p1_eva_sp11.json').read_text())['rows']}
    lead = sp11['EVA3_SP11_120']['door']
    dist = json.loads((ROOT/'references/p1_eva_district.json').read_text())
    branch = dist['topology']['openings']['branch_port']['clear_m']/2+lap
    ext = dist['layouts']['L1-A']['access']['extension']['clear_m']/2+lap
    wport = dist['layouts']['L1-A']['access']['port']['clear_m']/2+lap
    return [
        dict(name='SP-12 branch hatch (STUDY)', family='F5 EVA district (STUDY)', a='Crew_Trunk', b='SP12', seats_from='Crew_Trunk', leaf_r_m=branch,
             kind='leaf at the trunk end of the 0.90 m branch; seat side from the district study', status='STUDY',
             source='p1_eva_district.json topology SP12; 0.90 m branch clear'),
        dict(name='SP-11 inner hatch (STUDY, 1.20 m lead)', family='F5 EVA district (STUDY)', a='SP12', b='SP11', seats_from='SP12', leaf_r_m=lead['r_leaf'],
             kind='parallel-linkage plug, drops 0.08 m and slides -az in the bulkhead plane', status='STUDY',
             source='p1_eva_sp11.json EVA3_SP11_120 parallel_plug_slide (the study lists reverse_load 0 for the EVA cycle; '
                    'the SP-12-loss case below is the one it does not cover); 1.10 / 1.35 m: 90.5 / 132.1 kN'),
        dict(name='SP-11 outer hatch (STUDY, 1.20 m lead)', family='F5 EVA district (STUDY)', a='OUTSIDE', b='SP11', seats_from='SP11', leaf_r_m=lead['r_leaf'],
             kind='plug opening into the chamber', status='STUDY', source='p1_eva_sp11.json EVA3_SP11_120 door'),
        dict(name='SP-12/13 door (STUDY)', family='F5 EVA district (STUDY)', a='SP12', b='SP13', seats_from='SP12', leaf_r_m=None,
             kind='door in SP-12\'s forward wall; size not set by the study', status='STUDY', source='p1_eva_district.json topology SP12/SP13'),
        dict(name='District hatch (STUDY, L1-A)', family='F5 EVA district (STUDY)', a='Crew_Trunk', b='DISTRICT', seats_from='Crew_Trunk', leaf_r_m=ext,
             kind='across the 1.6 m trunk extension at the trunk end (X 102.45 m)', status='STUDY', source='p1_eva_district.json L1-A access extension 1.6 m'),
        dict(name='Workshop port hatch (STUDY, L1-A)', family='F5 EVA district (STUDY)', a='DISTRICT', b='WORKSHOP', seats_from=None, leaf_r_m=wport,
             kind='0.90 m port off the district passage; seat side not set', status='STUDY', source='p1_eva_district.json L1-A access port 0.90 m'),
    ]


def survey(s):
    """Every pressure closure on the spine, trunk, refuge, vestibules, crew tubes and sectors (built PROTOTYPE, er.closures) plus the
    unmodelled trunk-branch hatches (OPEN) and the EVA-003 study closures. Per closure: the compartment whose pressure seats it, the normal case
    (a loss on the other side: held by pressure), the reverse case (the seating side loses pressure while the other side is still at cabin
    pressure: only latches, dogs and drives hold the leaf) and its load at 80 kPa (DERIVED)."""
    fam = lambda n: ('F1 sector hatch' if n.startswith('Sector hatch') else 'F2 transfer pair (drum door + tube hatch)' if n.startswith(('Drum door', 'Tube hatch'))
                     else 'F3 spine-shell branch (trunk side)' if n.startswith(('Spine port gate', 'Refuge', 'Storeroom')) else 'F4 primary dock')
    rows = []
    for c in er.closures(s):
        rows.append(dict(name=c['name'], family=fam(c['name']), a=c['a'], b=c['b'], seats_from=c['seats_from'], leaf_r_m=c['leaf_r_m'],
                         kind={'F1 sector hatch': 'sliding plug: leaf on the sector side, drops 0.02 m and slides 1.75 m toward the aisle',
                               'F2 transfer pair (drum door + tube hatch)': 'curved plate sliding round the drum wall (door) / ring face (hatch), tube side',
                               'F3 spine-shell branch (trunk side)': ('gate sliding +X in the spine-shell slot (r 0.88-0.92 m)' if c['name'].startswith('Spine')
                                                                     else 'leaf hinged on the room side, folds 180 deg flat' if c['name'].startswith('Store')
                                                                     else 'no closure modelled'),
                               'F4 primary dock': 'plug leaf hinged inboard'}[fam(c['name'])],
                         status='BUILT PROTOTYPE' if c['seats_from'] or c['leaf_r_m'] is None else 'BUILT PROTOTYPE, seat side OPEN', source=c['source']))
    # Built trunk branches whose hatch is not designed (OPEN D1/E4 in crew_transfer.interfaces).
    for name, x, ang, rad in he.openings(s):
        if name in ('Crew_Connector_Dock_Service', 'Crew_Connector_Airlock_EVA'):
            rows.append(dict(name=f'{name} hatch', family='F3 spine-shell branch (trunk side)', a='Crew_Trunk', b=name.replace('Crew_Connector_', ''),
                             seats_from=None, leaf_r_m=None, kind='proxy connector; hatch and isolation not designed', status='BUILT PROXY, hatch OPEN (D1/E4)',
                             source='crew_transfer.interfaces FITTING_CONNECTOR'))
    rows += _study_closures(s)
    for r in rows:
        r['leaf_r_m'] = r2(r['leaf_r_m']); seat, other = r['seats_from'], (r['b'] if r['seats_from'] == r['a'] else r['a'])
        if r['a'] == 'OUTSIDE' or r['b'] == 'OUTSIDE':
            inside = r['b'] if r['a'] == 'OUTSIDE' else r['a']
            r['normal_case'] = f'{inside} pressurized against space: pressure seats it'
            if r['name'].startswith('Dock outer'):
                r.update(reverse_case='a docked vehicle at pressure while the entry chamber is vented (docking leak check, chamber loss)',
                         reverse_load_kN=kN(s, r['leaf_r_m']), held_today='latches only (conditional: docked and pressurized)')
            else:
                r.update(reverse_case='none: the exterior is vacuum', reverse_load_kN=None, held_today='n/a')
        elif seat is None:
            r.update(normal_case='OPEN: seat side not set', reverse_case=f'whichever side is chosen, a loss of that side ({r["a"]} or {r["b"]})',
                     reverse_load_kN=kN(s, r['leaf_r_m']), held_today='OPEN (one direction will be latch-only)')
        else:
            r.update(normal_case=f'{other} loses pressure: {seat} pressure seats the leaf', reverse_case=f'{seat} loses pressure while {other} is at cabin pressure',
                     reverse_load_kN=kN(s, r['leaf_r_m']), held_today='latches only')
        r['load_basis'] = DERIVED
    return rows


# ---------- (b) option 1 vs option 2, measured ------------------------------------------------------------------------------------------

def _gap_report(cands, local, world, other, rot, own=(), clr_same=None, clr_other=None):
    """Clearance of each candidate (rotor-local primitive) to the same-rotor parts (exact) and to stationary / other-rotor parts (swept).
    `own` are the parts it is mounted on: it may touch them but not overlap them (reported separately)."""
    out = {}
    for tag, o in cands.items():
        best, mount = [], []
        for q in local:
            g = ct.gap(o, q, 'exact')
            (mount if q['name'] in own else best).append((g-(0.0 if q['name'] in own else clr_same), g, q['name'], 'same rotor'))
        po = ct.posed(o, rot['x'], 0.0)
        for q in world+other:
            g = ct.gap(po, q, 'swept'); best.append((g-clr_other, g, q['name'], 'swept'))
        m, g, n, how = min(best); mm = min(mount) if mount else (0.0, None, None, None)
        out[tag] = dict(min_gap_m=round(g, 3), nearest=n, check=how, need_m=clr_same if how == 'same rotor' else clr_other,
                        mount_gap_m=None if mm[1] is None else round(mm[1], 3), mount=mm[2],
                        result='CLEAR' if m >= -1e-9 and mm[0] >= -1e-9 else 'BLOCKED')
    return out


def _frames(s):
    rot = {r['index']: r for r in ri.rotors(s)}; world = ct.world_obstacles(s); crew_rot = ct.rotating(s)
    local = {j: ct.rotor_obstacles(s, j)+[q for q in crew_rot if q['rotor'] == j] for j in rot}
    posed = {j: [ct.posed(o, rot[j]['x'], 0.0) for o in local[j]] for j in rot}
    return rot, world+ct.stationary(s), local, posed


def sector_hatch_options(s, F):
    """F1: the sector hatch (1.70 m sliding plug, seats from the sector). Option 1: the same leaf with reverse dogs and a seal that holds both
    ways; what the landing leaves for them. Option 2: a reverse-seating closure on the tube side (a hinged leaf in the tube; a slide gate
    just inboard of the inner hoop with a pocket in four directions) or below the primary on the sector side."""
    h = s['human_entry']; L = he.landing(s); rot, world, local, posed = F; t, g = h['hatch_leaf_thickness_m'], s['crew_transfer']['transfer_track_gap_m']
    clr = h['leaf_swing_clearance_m']; fl = habitat_ring.floor(s); hoop = s['habitat_ring']['frame_inner_radius_m']-fl
    out = dict(option_1=dict(
        meaning='one leaf, seal and dogs rated for the full Delta-p from either side: a dog ring on the frame engaging the leaf\'s deck face '
                'besides the seat it already has on the tube side, a seal that is pressure-energized both ways, leaf structure checked for both '
                'load directions; the dogs retract before the 0.02 m drop and the 1.75 m slide',
        frame_depth_m=r2(L['seat']-L['frame_top']), leaf_lap_on_seat_m=r2(L['leaf_r']-L['clear_r']), frame_beyond_leaf_rim_m=r2(L['frame_r']-L['leaf_r']),
        band_rim_to_guide_rail_m=r2(h['leaf_swing_clearance_m']), leaf_open_to_stile_top_m=r2(L['stile_top']-L['leaf_open'][1]),
        geometry='reverse dogs sit in the 0.05 m band between the leaf rim (r 0.85 m) and the guide rails (r 0.92 m) and must retract out of the '
                 'leaf\'s slide path; the frame (0.22 m deep, skin to seat) carries them; no headroom or route change',
        reverse_load_kN=kN(s, L['leaf_r']), mass_complexity='moderate: one more dog set and drive per hatch (x6); no new seal plane or pocket'))
    # Option 2a: a leaf hinged into the tube.
    out['option_2a_hinged_in_tube'] = dict(leaf_diameter_m=r2(2*L['leaf_r']), tube_clear_diameter_m=r2(2*L['clear_r']),
                                          result='FAIL: a 1.70 m leaf cannot stand edge-on in a 1.60 m bore')
    # Option 2b: a slide gate across the tube bore just inboard of the inner hoop, seat on the hoop's inner face, pocket outside the tube.
    y1 = hoop-g; y0 = y1-t; k, la = ct.sectors(s)[0]; travel = 2*L['leaf_r']+clr; res = {}
    for j in rot:
        pt = lambda x, y, z: ct.sector_point(s, dict(ct.sectors(s))[1], (x, y, z))
        cands = {}
        for tag, (dx, dz) in {'+X (fwd)': (travel, 0), '-X (aft)': (-travel, 0), 'toward spoke (+z)': (0, -L['side']*travel), 'away from spoke (-z)': (0, L['side']*travel)}.items():
            cands[tag] = ct.cyl('gate', pt(L['x']+dx, y0, L['z']+dz), pt(L['x']+dx, y1, L['z']+dz), L['leaf_r'])
        own = {f'Crew_Tube_{j}_1', f'Ring_{j}_Hoop_Inner'}
        res['AB'[j-1]] = _gap_report(cands, local[j], world, [q for i in posed if i != j for q in posed[i]], rot[j], own, clr, s['prototype']['mechanical_clearance_m'])
    out['option_2b_tube_end_slide_gate'] = dict(
        plate=f'r {r2(L["leaf_r"])} m x {t} m at {r2(fl+y0)}-{r2(fl+y1)} m from the ring axis (seat on the inner hoop\'s inner face), travel {r2(travel)} m',
        pockets=res, note='the tube ladder breaks for the closed plate; the plate carries the tube-side seal; same-rotor need = leaf swing clearance, swept need = mechanical clearance')
    # Option 2c: a second sliding plate below the primary (sector side), seating on a lip, pressed by tube pressure through the primary.
    need = t+g+g
    out['option_2c_sector_side_plate'] = dict(stack_needed_m=r2(need), leaf_open_to_stile_top_m=r2(L['stile_top']-L['leaf_open'][1]),
                                             margin_m=r2(L['stile_top']-L['leaf_open'][1]-need),
                                             result='FAIL without lowering the ladder top and the landing light: the plate stack below the open leaf does not fit',
                                             note='also puts the secondary inside the compartment it isolates (operated remotely only)')
    return out


def transfer_pair_options(s, F):
    """F2: drum door (on the drum wall's outer face) + tube hatch (on the ring face, tube side), both seated from the tube. Option 1: one of the
    pair rated both ways. Option 2: re-hand one of the pair (door to the drum wall's inner face, or hatch into the running gap) or add a
    reverse-seating slide gate across the tube collar."""
    c, h = s['crew_transfer'], s['human_entry']; m = h['mannequin']; t, g = c['transfer_closure_thickness_m'], c['transfer_track_gap_m']
    rot, world, local, posed = F; out = {}
    for j in h['vestibule_rotors']:
        tag = 'AB'[j-1]; v = ct.vestibule(s, j); st = ct.transfer_stack(s, j); neck = ct.tube_neck(s, j)
        tc = neck['clear'] if neck else ct.tube_radii(s, j)[1]; plate_r = tc+c['transfer_closure_lap_m']
        depth = v['clear']-v['r0']; need_depth = m['suited_envelope_diameter_m']+2*(h['handrail_standoff_m']+2*h['handrail_radius_m'])
        b = math.asin(min(1.0, plate_r/(v['clear']-g-t))); turn = math.degrees(2*b)+c['transfer_park_margin_deg']
        row = dict(
            stack=dict(drum_wall_outer=r2(st['wall']), door=[r2(x) for x in st['door']], ring_face=r2(st['ring_face']), hatch=[r2(x) for x in st['hatch']],
                       running_gap_m=c['transfer_running_gap_m']),
            reverse_load_kN_each=kN(s, plate_r),
            option_1=dict(meaning='rate the tube hatch (or the drum door) for the full Delta-p from the vestibule side: dogs on its slide edges '
                                  'or a cam that clamps it to the face, a seal energized both ways; plate stiffness for the reverse load',
                          geometry='inside the existing 0.04 m plate and 0.01 m track gap; the clamp/dog hardware sits in the track ends, '
                                   'outside the bore; no stack change measured', mass_complexity='moderate: x6 per ring, one of each pair'),
            option_2a_door_on_inner_face=dict(chamber_depth_m=r2(depth), required_depth_m=r2(need_depth), plate_band_m=r2(t+g),
                                              margin_m=r2(depth-need_depth-(t+g)), park_turn_deg=round(turn, 1),
                                              handrail_at_deg=h['vestibule_handrail_offset_deg'],
                                              result='FAIL: the chamber holds the suited envelope between handrails with only '
                                                     f'{depth-need_depth:.2f} m spare, and the parked plate crosses the handrail between hatches'),
            option_2b_hatch_in_running_gap=dict(running_gap_m=c['transfer_running_gap_m'], needed_m=r2(c['transfer_running_gap_m']+t+g),
                                                ring_face_shift_m=r2(t+g),
                                                result=f'needs the ring face {t+g:.2f} m further out (tube root, collar and, on ring B, the neck base move); '
                                                       'one plate then seats each way across the running gap'))
        # Option 2c: an added slide gate across the collar, plate perpendicular to the collar axis, pocket outside the tube.
        root = ct.tube_floor(s, j); collar = (neck['base']+neck['wall'] if neck else v['r1'])+ct.tube_radii(s, j)[0]; rp = (root+collar)/2
        la = dict(ct.sectors(s)); cands = {}
        travel = 2*(ct.tube_radii(s, j)[1]+c['transfer_closure_lap_m'])+h['leaf_swing_clearance_m']; pr = ct.tube_radii(s, j)[1]+c['transfer_closure_lap_m']
        for k in (1,):
            a = la[k]; rad = (0.0, math.cos(a), math.sin(a)); tan = (0.0, -math.sin(a), math.cos(a))
            ctr = ct.radial(v['hatch_u'], rp, a)
            for name, d in {'+u (toward spokes)': (1.0, 0.0, 0.0), '-u (aft)': (-1.0, 0.0, 0.0), '+tangent': tan, '-tangent': tuple(-x for x in tan)}.items():
                c0 = ct.add(ctr, d, travel)
                cands[name] = ct.cyl('collar_gate', ct.add(c0, rad, -t/2), ct.add(c0, rad, t/2), pr)
        row['option_2c_collar_slide_gate'] = dict(plate=f'r {r2(pr)} m x {t} m at r {r2(rp)} m in the {r2(collar-root)} m radial collar, travel {r2(travel)} m',
                                                 pockets=_gap_report(cands, local[j], world, [q for i in posed if i != j for q in posed[i]], rot[j],
                                                                     {f'Crew_Tube_{j}_1'}, h['leaf_swing_clearance_m'], s['prototype']['mechanical_clearance_m']),
                                                 note='a third closure per tube; seats from the vestibule side; needs a pocket enclosure on the collar')
        out[tag] = row
    return out


def slot_options(s):
    """F3: trunk branches through the spine-shell slot between the trunk wall and the spine core (where the spine gates slide). Radial stack
    for one bidirectional gate vs two gates, and for every branch a gate's parking run (+X / -X) against the other branches."""
    c = s['crew_transfer']; to = c['trunk_clear_radius_m']+c['passage_wall_m']; core = layout.spine_core(s)[2]
    t, g, lap = c['transfer_closure_thickness_m'], c['transfer_track_gap_m'], c['transfer_closure_lap_m']; rm = (to+core)/2
    stack = dict(trunk_outer_r_m=r2(to), spine_core_r_m=r2(core), slot_m=r2(core-to), gate_m=t, track_gap_m=g,
                 option_1_free_per_face_m=r2((core-to-t)/2-g), option_2_needed_m=r2(2*t+3*g), option_2_margin_m=r2(core-to-(2*t+3*g)),
                 option_2_result='FAIL in the slot: two plates with their track gaps and no seat land between them exceed the 0.10 m slot',
                 option_1_result=f'fits: {(core-to-t)/2-g:.2f} m per face for a seat land and seal after the track gap')
    clear = {'Crew_Port_1_1': ct.vestibule(s, 1)['port_clear'], 'Crew_Port_2_2': ct.vestibule(s, 2)['port_clear'],
             'Crew_Connector_Dock_Primary': s['prototype']['dock_clear_radius_m'], 'Crew_Refuge_Port': s['human_entry']['refuge_port_clear_m']/2,
             'Crew_Store_Port': storeroom.port(s)['clear'], 'Crew_Connector_Airlock_EVA': 0.45, 'Crew_Connector_Dock_Service': c['passage_clear_radius_m']}
    ops = he.openings(s); (x0, _, _), (x1, _, _) = ct.stationary(s)[0]['points']; parks = {}
    for name, x, ang, rad in ops:
        half = clear[name]+lap; slide = 2*half+c['port_gate_park_margin_m']; hw = math.asin(min(1.0, half/rm)); row = {}
        for d in (1, -1):
            lo, hi = sorted((x+d*slide-half, x+d*slide+half)); hits = []
            if lo < x0+c['passage_wall_m'] or hi > x1-c['passage_wall_m']:
                hits.append('trunk end')
            for n2, xx, a2, r2_ in ops:
                if n2 == name:
                    continue
                hw2 = math.asin(min(1.0, r2_/rm))
                if lo < xx+r2_ and hi > xx-r2_ and ct.angle_diff(ang, a2) < hw+hw2:
                    hits.append(n2)
            row['+X' if d > 0 else '-X'] = dict(span_x_m=[round(lo, 2), round(hi, 2)], blocked_by=hits, result='CLEAR' if not hits else 'BLOCKED')
        parks[name] = dict(x_m=round(x, 2), azimuth_deg=round(math.degrees(ang) % 360, 1), gate_half_m=r2(half), slide_m=r2(slide), **row)
    return dict(stack=stack, parks=parks)


def refuge_options(s):
    """Refuge port (0.90 m, no closure modelled): seat side and the two options."""
    h = s['human_entry']; rc = h['refuge_port_clear_m']/2; ref = ct.hull_geometry.refuge(s)
    rh, rl = rc+h['hatch_frame_width_m'], rc+h['hatch_leaf_overlap_m']; reach = rh+rl+h['leaf_swing_clearance_m']
    return dict(recommended_seat='from the refuge side (refuge pressure holds it when the trunk is lost: the haven case)',
                reverse_case='refuge breach while the trunk is at pressure', reverse_load_kN=kN(s, rl),
                option_1='one bidirectional gate in the spine-shell slot (fits, see slot stack) or one hinged leaf with reverse dogs',
                option_2=dict(primary='leaf hinged into the refuge, seats from the refuge side', secondary='slot gate seating from the trunk side',
                              hinged_leaf_reach_m=r2(reach), refuge_annulus_depth_m=r2(ref['pressure']-ref['inner']),
                              radial_margin_m=r2(ref['pressure']-ref['inner']-reach),
                              result='fits radially; the hoop and anchor rails beside the port are not checked against the swing (Blender)'))


def spine_gate_seat(s):
    return dict(recommended_seat='from the trunk side',
                why='a vestibule or tube loss is then held by trunk pressure (the trunk serves the refuge, the other ring, docking, EVA and the '
                    'storeroom); after a trunk loss the vestibule is reverse-loaded, but beyond it the drum doors and tube hatches seat from the '
                    'tube side, so tubes and sectors stay pressure-held: the vestibule is an unoccupied transfer volume in that case',
                reverse_case='trunk loss with the vestibule at pressure', reverse_load_kN={'A': kN(s, ct.vestibule(s, 1)['port_clear']+s['crew_transfer']['transfer_closure_lap_m']),
                                                                                          'B': kN(s, ct.vestibule(s, 2)['port_clear']+s['crew_transfer']['transfer_closure_lap_m'])},
                recommended_option='option 1 (bidirectional gate): option 2 does not fit the slot; a crew member in the drum during a trunk loss is the '
                                   'case that needs it')


# ---------- (c) gas recovery ---------------------------------------------------------------------------------------------------------

def reserve(s, F):
    """R1 candidate envelopes: on each rotor drum, forward of the spoke plane, in three segments midway between the crew tubes (60/180/300 deg
    ring-local), from one mechanical clearance above the hub drum outward; the largest outer radius (0.1 m grid) whose envelope clears the
    rotor's own parts (exact) and every stationary or other-ring part (swept). An envelope, not a tank size."""
    rot, world, local, posed = F; p = s['prototype']; c = s['crew_transfer']; ri_ = s['rotor_interface']; out = {}  # noqa
    clr = p['mechanical_clearance_m']; half = math.radians(20.0)
    for j in rot:
        tag = 'AB'[j-1]; rail = s['habitat_ring']['spoke_rail_u_m']+s['habitat_ring']['spoke_rail_radius_m']
        u0 = rail+clr; r0 = ri_['drum_outer_radius_m']+clr
        # Axial limit: the next ring's vestibule (or the refuge for ring B), less a mechanical clearance, found by search below.
        mids = [a+math.pi/3 for _, a in ct.sectors(s)]; best = None; others = [q for i in posed if i != j for q in posed[i]]
        seg = lambda a, b, r1: [ct.ring(f'R1_{tag}_{i}', a, b, r0, r1, (m-half, m+half)) for i, m in enumerate(mids)]
        ax_block = None
        for u1 in [u0+0.1*k for k in range(1, 40)]:
            ax_block = _blocked(seg(u0, u1, r0+0.5), local[j], world, others, rot[j], clr)
            if ax_block:
                break
            best = u1
        if best is None:
            out[tag] = dict(result='no envelope', blocked_by=ax_block); continue
        u1 = best; rb = None; cap = c['coast_tube_bend_radius_m']; rad_block = None
        for r1 in [r0+0.1*k for k in range(5, int((c['coast_tube_bend_radius_m']-r0)/0.1)+2)]:
            rad_block = _blocked(seg(u0, u1, r1), local[j], world, others, rot[j], clr)
            if rad_block:
                break
            rb = r1
        rcap = min(rb, cap)
        vol = 3*(2*half/2)*(rcap**2-r0**2)*(u1-u0)
        x = rot[j]['x']
        # Path to each sector: the manifold at the envelope, a hub line aft to the tube collar, then the tube (ct.length of its axis).
        paths = {}
        for k, la in ct.sectors(s):
            tube = next(q for q in ct.rotating(s) if q['name'] == f'Crew_Tube_{j}_{k}')
            hub_leg = math.dist(ct.radial((u0+u1)/2, (r0+rcap)/2, la+math.pi/3), tube['points'][1])
            paths[f'{tag}{k}'] = dict(hub_leg_m=round(hub_leg, 1), tube_leg_m=round(ct.length(tube['points']), 1),
                                      valves=['V-RES (reserve isolation, remote, fail-closed)', f'V-BR-{tag}{k} (branch isolation at the hub manifold, remote, fail-closed)',
                                              f'LC-{tag}{k} (branch line pressure-decay check between V-BR and V-EQ)',
                                              f'V-EQ-{tag}{k} (controlled equalization, tube-side hatch panel, remote + manual, flow-limited)',
                                              f'V-REL-{tag}{k} (sector relief/vent to space, remote + tube-side manual)',
                                              f'PT-{tag}{k} (sector and tube pressure, ppO2, decay; remote and at the panel)',
                                              f'V-TB-{tag}{k} (tube tap off the same branch, for a tube recovery)'])
        out[tag] = dict(rotor_x_m=x, u_m=[round(u0, 2), round(u1, 2)], x_m=[round(x+u0, 2), round(x+u1, 2)], r_m=[round(r0, 2), round(rcap, 2)],
                        axial_limit=dict(u_m=round(u1, 2), next_step_blocked_by=ax_block),
                        radial_limit=dict(study_cap_r_m=cap, cap_basis='PROTOTYPE: kept inside the crew tubes\' bend radius (hub zone)',
                                          free_to_r_m=None if rb is None else round(rb, 2), next_step_blocked_by=rad_block),
                        segments_deg_ring_local=[round(math.degrees(m)) for m in mids], segment_width_deg=round(math.degrees(2*half)),
                        envelope_m3=round(vol, 2), distance_to_sector_floor_m=round(habitat_ring.floor(s)-rcap, 1), distance_to_sector_overhead_m=round(s['habitat_ring']['sector_inner_radius_m']-rcap, 1),
                        note='envelope available on the rotating drum (three segments, 120 deg symmetric: no static imbalance before draw-down); '
                             'tank size, gas, pressure and mass are Sheets items', paths=paths)
    return out


def _blocked(seg, local, world, other, rot, clr):
    for o in seg:
        for q in local:
            if ct.gap(o, q, 'exact') < clr-1e-9:
                return q['name']
        po = ct.posed(o, rot['x'], 0.0)
        for q in world+other:
            if ct.gap(po, q, 'swept') < clr-1e-9:
                return q['name']
    return None


def gas_paths(s, R):
    """R1, R4, R2, R3 compared (no quantities)."""
    ri_ = s['rotor_interface']
    return {
        'R1 ring-local reserve (PREFERRED, spinning emergency)': dict(
            where=f'on each rotor drum forward of its spoke plane, three segments between the crew tubes (ring A x {R["A"]["x_m"]} m, '
                  f'ring B x {R["B"]["x_m"]} m, r {R["A"]["r_m"]} m)',
            protected_by=f'about {R["A"]["distance_to_sector_floor_m"]} m radially from every sector, outside every pressure compartment, behind '
                         'the remote fail-closed branch valve of each sector; a leaking sector or tube cannot reach it',
            path='reserve -> V-RES -> hub manifold -> V-BR-k -> line along crew tube k (in the tube wall chase) -> V-EQ-k at the tube-side hatch panel -> sector k; '
                 'tube recovery via V-TB-k',
            works_while_spinning=True, new_rotary_fluid_interface=False,
            source='S&E 16!A7 MEC-006: store/condition most fluids on the rotating side; bypass/isolation and local reserve'),
        'R4 stop and index (PREFERRED, recharge and backup)': dict(
            where=f'a recharge stab coupling beside the ring-stop lock housings (u {ri_["ring_lock_u_m"]} m, r {ri_["ring_lock_pin_outer_radius_m"]} m outer pin), '
                  'engaged only in STOPPED_LOCKED; stationary supply to the rotor manifold',
            path='stationary supply (source OPEN) -> stationary isolation + leak check -> stab coupling (engaged at index) -> V-RES fill valve -> reserve; '
                 'backup: the same coupling feeds the hub manifold directly',
            works_while_spinning=False, new_rotary_fluid_interface=False,
            limits='the ring\'s gravity is lost while stopped; the coupling geometry and mechanism belong with MEC-011 (OPEN)'),
        'R2 drum batch transfer (compared)': dict(
            path='pressurize the despun drum from the stationary side, synchronize, open drum door + tube hatch to the tube, repeat',
            works_while_spinning='per cycle', new_rotary_fluid_interface=False,
            limits='opens the transfer pair into the tube, so it cannot serve a leaking tube; each batch is bounded by the drum volume and the '
                   'MEC-019 cycle (OPEN); the closures cycle under Delta-p; slower than R1, no hardware beyond the drum: kept as a tertiary path'),
        'R3 rotary gas union (NOT ADOPTED)': dict(
            why_not_needed='R1 covers the spinning emergency from rotating-side storage and R4 recharges at index, so no stationary-to-ring gas '
                           'flow is needed while spinning; the hub keeps its one existing fluid coupling cartridge (Hub_FLUID_COUPLING, MEC-006) '
                           'and adds no essential rotary gas interface (MEC-019)'),
    }


# ---------- (d) prohibitions ---------------------------------------------------------------------------------------------------------

def prohibitions(s):
    P1, P2, P3 = 'no untested reverse-load latch-only closure', 'no gas into an actively leaking sector', 'no access through evacuated strips'
    rows = [
        dict(path='R1 sector recovery', crosses=['sector hatch (closed; tube at 80 kPa, sector low: REVERSE-loaded)'],
             P1='BLOCKED until F1 has its rated reverse closure (option 1 dogs or option 2b gate) and it is tested: the repressurization itself '
                'holds the tube against the low sector on that hatch', P2='interlock: V-EQ enables only after LC passes and the sector decay test '
                'shows the leak is stopped (threshold OPEN, Sheets); V-BR fail-closed', P3='PASS: every valve on the tube side, at the hub or remote; '
                'no entry before the sector is at pressure'),
        dict(path='R1 tube recovery', crosses=['drum door + tube hatch (vestibule at pressure, tube low: REVERSE-loaded)', 'sector hatch (pressure-seated)'],
             P1='BLOCKED until F2 has one closure per pair rated or re-handed (option 1, or option 2b)', P2='same interlock on V-TB',
             P3='PASS: no strip is involved; the tube is entered only at pressure'),
        dict(path='R4 recharge at index', crosses=['stab coupling (stationary <-> rotor), no hatch'], P1='PASS: no closure under reverse load',
             P2='PASS: fills the reserve, never a sector directly', P3='PASS: mechanism-engaged; no crew passage'),
        dict(path='R4 backup feed', crosses=['stab coupling -> hub manifold -> V-BR-k'], P1='as R1 (sector hatch reverse-loaded)', P2='as R1', P3='PASS'),
        dict(path='R2 batch transfer', crosses=['spine gate', 'drum door + tube hatch (opened under equal pressure, cycled)'],
             P1='conditional: each cycle closes the pair with the drum at higher pressure than the tube unless equalized first (procedure, OPEN)',
             P2='cannot serve a leaking tube; a sector only through V-EQ after LC', P3='PASS: drum and tube are pressurized; never into a strip'),
        dict(path='R3 rotary union', crosses=['continuous rotary gas seal'], P1='n/a', P2='n/a', P3='n/a', note='NOT ADOPTED'),
    ]
    return dict(rules=[P1, P2, P3], rows=rows)


OCCUPANCY = {'SP-11 chamber': 'TRANSIENTLY OCCUPIED', 'district passage': 'TRANSIENTLY OCCUPIED', 'vestibule / drum': 'TRANSIENTLY OCCUPIED',
             'trunk': 'OCCUPIED ROUTE', 'refuge': 'HAVEN', 'sectors': 'INHABITED'}


def disposition(s, sv):
    """Owner disposition PRESS-004 / EVA-064 (15!A137, 43 EVA-064, 2026-10-11) applied to the survey: every life-critical closure needs a
    positive mechanically supported load path in both polarities (option 1 is the requirement, not a choice) with two-side manual equalization
    and indication; an independent second closure is studied only where the fault matrix needs it (refuge, SP-12 branch); the spine gates seat
    from the trunk and the refuge from the refuge side as study choices still to be verified both ways. Transit volumes count as transiently
    occupied, never as empty for safety accounting. Every gas, pressure and force quantity stays unknown (data [pressure_release])."""
    pr = s['pressure_release']
    rows = [dict(closure=r['name'], family=r.get('family'), reverse_load_kN=r.get('reverse_load_kN'), held_today=r['held_today'],
                 requirement='positive bidirectional load path + two-side equalization/indication (PRESS-004)',
                 second_closure='study (fault matrix)' if any(k in r['name'].lower() for k in ('refuge', 'sp-12', 'sp12', 'branch')) else 'only if the fault matrix requires',
                 compliant_today=not r['held_today'].startswith(('latches only', 'OPEN'))) for r in sv]
    return dict(source='15!A137 PRESS-004, 43 EVA-064 (owner 2026-10-11)', architecture=pr['architecture'], closures=rows,
                non_compliant_today=sum(not r['compliant_today'] for r in rows), occupancy=OCCUPANCY,
                seat_sides={'spine gates': 'trunk side (study choice; verify both ways)', 'refuge': 'refuge side (study choice; verify both ways)'},
                reserve={'R1': 'preferred, protected ring-local, fail-closed isolation and leak test', 'R4': 'coupling only with the rotor stopped/locked',
                         'R2': 'tertiary', 'R3': 'not needed'},
                open_quantities=[dict(q) for q in pr['quantities']],
                released=[q['id'] for q in pr['quantities'] if q.get('known')])


def report(s):
    F = _frames(s); R = reserve(s, F); sv = survey(s)
    latch = [r for r in sv if r['held_today'] == 'latches only']
    cond = [r['name'] for r in sv if r['held_today'].startswith('latches only (')]; opn = [r['name'] for r in sv if r['held_today'].startswith('OPEN')]
    return dict(contract=CONTRACT, status=STATUS, source='S&E 15!A127 (ECLSS-REC2), 15!A124, 16!A7 MEC-006, MEC-019; previous study references/ECLSS_RECOVERY.md',
                cabin_pressure_kpa=s['habitat']['atmosphere']['cabin_pressure_kpa'], load_basis=DERIVED,
                survey=sv, latch_only_reverse=dict(count=len(latch), built=[r['name'] for r in latch if r['status'] != 'STUDY'], study=[r['name'] for r in latch if r['status'] == 'STUDY'],
                                        conditional=cond, seat_side_open=opn),
                options=dict(F1_sector_hatch=sector_hatch_options(s, F), F2_transfer_pair=transfer_pair_options(s, F), F3_slot=slot_options(s),
                             spine_gates=spine_gate_seat(s), refuge=refuge_options(s)),
                reserve=R, gas_paths=gas_paths(s, R), prohibitions=prohibitions(s),
                compartments=er.compartments(s), owner_disposition=disposition(s, sv))


def svg(r):
    """Schematic: compartments in a row from the trunk outward, closures coloured by today's reverse state, R1/R4 paths."""
    W, H = 1180, 620; o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 {W} {H}" font-family="sans-serif" font-size="12">',
                           '<rect width="100%" height="100%" fill="#ffffff"/>',
                           f'<text x="20" y="24" font-size="15" font-weight="bold">{CONTRACT}: reverse-load closures and ring-local reserve (NONCANON study map)</text>',
                           '<text x="20" y="42" fill="#555">Closure colour = the reverse case today: orange latches only, grey OPEN seat side, green pressure-held both ways after the recommended option. kN = 80 kPa x leaf area (DERIVED).</text>']
    def box(x, y, w, h, label, sub='', fill='#eef2f7'):
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="#334"/>')
        o.append(f'<text x="{x+w/2}" y="{y+h/2-2}" text-anchor="middle" font-weight="bold">{label}</text>')
        if sub:
            o.append(f'<text x="{x+w/2}" y="{y+h/2+14}" text-anchor="middle" fill="#444" font-size="11">{sub}</text>')
    def cl(x, y, col, label, below=''):
        o.append(f'<rect x="{x-5}" y="{y-22}" width="10" height="44" fill="{col}"/>')
        o.append(f'<text x="{x}" y="{y-28}" text-anchor="middle" font-size="10" fill="{col}">{label}</text>')
        if below:
            o.append(f'<text x="{x}" y="{y+36}" text-anchor="middle" font-size="10" fill="#333">{below}</text>')
    OR, GR, GN = '#e07a10', '#888', '#2a8a3a'
    loads = {q['name']: q['reverse_load_kN'] for q in r['survey']}
    for row, (y, ring) in enumerate(((180, "A"), (370, "B"))):
        j = row+1
        box(40, y-30, 150, 60, 'Trunk', '42.7 m3')
        cl(215, y, GR, f'spine gate {ring}', f'{loads[f"Spine port gate {ring}"]:.0f} kN')
        box(240, y-30, 150, 60, f'Vestibule {ring}', 'despun drum')
        cl(415, y, OR, 'drum door', f'{loads[f"Drum door {ring}1"]:.0f} kN')
        cl(440, y, OR, 'tube hatch', f'{loads[f"Tube hatch {ring}1"]:.0f} kN')
        box(465, y-30, 170, 60, f'Crew tube {ring}1-3', '49 m3 each')
        cl(660, y, OR, 'sector hatch', f'{loads[f"Sector hatch {ring}1"]:.0f} kN')
        box(685, y-30, 150, 60, f'Sector {ring}1-3', '72.4 m3 gross')
        R = r['reserve'][ring]
        box(900, y-70, 240, 50, f'R1 reserve ring {ring}', f'drum x {R["x_m"][0]}-{R["x_m"][1]} m, r {R["r_m"][0]}-{R["r_m"][1]} m', fill='#eaf5ea')
        o.append(f'<path d="M 1020 {y-20} L 1020 {y+50} L 550 {y+50} L 550 {y+30}" fill="none" stroke="#2266cc" stroke-width="2" stroke-dasharray="6 3"/>')
        o.append(f'<text x="790" y="{y+66}" text-anchor="middle" fill="#2266cc" font-size="11">V-RES - V-BR (hub, remote) - line in tube - LC - V-EQ (tube-side panel) ; V-REL sector to space</text>')
        o.append(f'<path d="M 1020 {y-70} L 1020 {y-95} L 300 {y-95} L 300 {y-30}" fill="none" stroke="#8844aa" stroke-width="2" stroke-dasharray="2 3"/>')
        o.append(f'<text x="660" y="{y-100}" text-anchor="middle" fill="#8844aa" font-size="11">R4: stab coupling at the ring-stop lock, STOPPED_LOCKED only (recharge, backup)</text>')
    o.append('<text x="20" y="520" fill="#333">Recommended: F1 sector hatch option 1 (reverse dogs in the 0.05 m rim band) or option 2b slide gate inboard of the hoop (pockets measured);</text>')
    o.append('<text x="20" y="538" fill="#333">F2 transfer pair option 1 on one closure per pair (2a fails the chamber depth, 2b moves the ring face 0.05 m); spine gates: seat from the trunk, option 1;</text>')
    o.append('<text x="20" y="556" fill="#333">refuge: seat from the refuge side, option 2 (slot gate from the trunk side + leaf into the refuge) fits; R3 not adopted.</text>')
    o.append('<text x="20" y="590" fill="#555">Gas quantities, tank sizes, flows, times and masses: Sheets (OPEN). Nothing here is model geometry.</text>')
    o.append('</svg>')
    return '\n'.join(o)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--json', type=Path); ap.add_argument('--svg', type=Path); a = ap.parse_args()
    r = report(load(ROOT)[0]); text = json.dumps(r, indent=1, default=str)
    if a.json:
        a.json.write_text(text+'\n')
    if a.svg:
        a.svg.write_text(svg(r))
    print(text)
