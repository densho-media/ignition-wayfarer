"""HUM-001 zones 1-5: the primary boarding entry, the stationary trunk, the rotary vestibules and crew spokes of both rings and the sector
landing at human scale (PROTOTYPE, standard library only).

The owner's workflow (S&E 15_MODEL_INTERFACES!A86, 98_DECISION_LOG!A60, 14_HULL_SERVICE!A32) builds the Blender model from the
primary boarding port at 1:1, one zone at a time, and reviews each zone from crew eye level before the next. Zone 1 turns the solid
dock fitting into a hollow pressure route: outer neck through the hull -> outer docking hatch -> entry chamber -> inner hatch. Zone 2:
the inner hatch opens inboard into the trunk node -> inboard neck -> crew connector -> the 1.6 m crew trunk in the spine bore
(crew_transfer), with handrails and lights. Zone 3: the trunk -> the 1.6 m spine port -> the hollow rotary vestibule of ring A, whose
annular chamber reaches every sector hatch (crew_transfer.vestibule); ring B's vestibule the same way through a 0.90 m port, the largest
hub 1's withdrawal paths leave room for. Zone 4: each sector hatch -> a 1.6 m crew tube that turns in two
mitered elbows and runs out beside its crew spoke to the sector's overhead (crew_transfer.tube_path), with a ladder on the wall facing away
from the spoke; on ring B the 0.90 m hatch opens into a neck through a bulkhead into the tube (crew_transfer.tube_neck). Zone 5: the tube
-> the sector hatch with its sliding leaf -> the ladder down to the deck of a landing well beside the aisle. ladder_push() gives the spin and
Coriolis push across the tube ladders of each ring (eye-level review). The refuge leg (OD-011 access path): the trunk -> the 0.90 m refuge port
-> the storm refuge, closed by an inner pressure wall, with hoop rails, one anchor rail per rated occupant, lights and a panel. Thrust review
(aft down when the rings stop and lock for major thrust): trunk_ladder() is a ladder with a fall-arrest rail up the trunk from its aft end past
ring B's spine port and the refuge port to the primary branch, and trunk_climber() a figure on it at the refuge port. Q47 (every essential route
passable aft-down to 1.5 g): floor_ladders() on each crew-tube leg that rises with aft down, thrust_step() below each sector hatch and a crawl
rail in each drum chamber (vestibule_fixtures), with elbow_climber() and thrust_stepper() as their figures.
route() and route_bodies() give the whole route and the suited body swept along it (inspect checks it against the built geometry). components/hull.py builds the port shells, components/crew.py the hollow connectors, trunk, vestibule, crew tubes and their fixtures,
components/revision.py the bored spine; the vehicle build places the mannequins and the first-person cameras, and
presentation/entry_preview.py renders the eye-level views. check() is the fit screen: `python3 src/wayfarer/human_entry.py` writes
references/p1_human_entry.json.

Dock-local coordinates: a = distance from the ship axis along the port's outward radial u; across the port axis a point sits at
radius rho and angle phi, measured from ship +X toward the tangent w = X x u. world(f, a, rho, phi) maps them to the vehicle frame.
"""
import json
import math
from pathlib import Path
import crew_transfer
import forward_shield
import habitat_ring
import hull_geometry
import layout
import rotor_interface

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'references/p1_human_entry.json'
STEP = 0.05          # IMPLEMENTATION: derived stations are rounded to this grid, toward the safe side
SWING_STEPS = 18     # IMPLEMENTATION: sampled leaf angles from closed to open


def ports(s):
    return [f for f in hull_geometry.service_fittings(s) if f['name'] in s['human_entry']['ports']]


def axes(f):
    """Outward radial u and tangent w = X x u of a port (both in the YZ plane)."""
    th = f['theta']
    return (0.0, math.cos(th), math.sin(th)), (0.0, -math.sin(th), math.cos(th))


def vec(f, a=0.0, p=0.0, q=0.0):
    """Vehicle-frame vector of local components along u, X and w."""
    u, w = axes(f)
    return (p, a*u[1]+q*w[1], a*u[2]+q*w[2])


def world(f, a, rho=0.0, phi=0.0):
    v = vec(f, a, rho*math.cos(phi), rho*math.sin(phi))
    return (f['x']+v[0], v[1], v[2])


def local(f, v):
    """(a, rho, phi) of a vehicle-frame point."""
    u, w = axes(f); p = v[0]-f['x']; a = v[1]*u[1]+v[2]*u[2]; q = v[1]*w[1]+v[2]*w[2]
    return a, math.hypot(p, q), math.atan2(q, p)


def ceil_step(x):
    return math.ceil(x/STEP-1e-9)*STEP


def floor_step(x):
    return math.floor(x/STEP+1e-9)*STEP


def stations(s, f):
    """Radial stations and radii of the entry route of port f, all derived from the PROTOTYPE selections and the hull."""
    h, p = s['human_entry'], s['prototype']
    clear, outer, wall = p['dock_clear_radius_m'], p['dock_radius_m'], h['chamber_wall_m']
    r_leaf = clear+h['hatch_leaf_overlap_m']; r_hinge = clear+h['hatch_frame_width_m']
    # A leaf hinged at r_hinge and opened 90 deg lies beside the passage; its far corners reach hypot(r_hinge, r_leaf) from the axis.
    chamber_r = ceil_step(math.hypot(r_hinge, r_leaf)+h['leaf_swing_clearance_m'])
    span = chamber_r+wall
    skin = min(hull_geometry.inner_radius_at(s, f['x']+k*span/4) for k in range(-4, 5))
    top = floor_step(math.sqrt((skin-p['mechanical_clearance_m'])**2-span**2))     # outboard face of the outboard bulkhead
    a_out = top-wall; a_in = a_out-h['chamber_clear_length_m']; bottom = a_in-wall
    fd, t = h['hatch_frame_depth_m'], h['hatch_leaf_thickness_m']; inner_hinge_a = bottom-fd-t
    # Zone 2: the inner leaf opens inboard; at hatch_open_deg its far edge reaches (r_hinge + r_leaf) sin(open) below the hinge, and the node
    # floor sits one swing clearance lower. The node takes the chamber radius (same leaf, same hinge).
    node_in = floor_step(inner_hinge_a-(r_hinge+r_leaf)*math.sin(math.radians(h['hatch_open_deg']))-h['leaf_swing_clearance_m'])
    return dict(clear=clear, outer=outer, wall=wall, r_leaf=r_leaf, r_hinge=r_hinge, chamber_r=chamber_r, skin=skin, top=top,
                a_out=a_out, a_in=a_in, bottom=bottom, port_face=f['r1'], root=f['r0'],
                outer_frame=(a_out-fd, a_out), outer_hinge_a=a_out-fd-t, inner_frame=(bottom-fd, bottom), inner_hinge_a=inner_hinge_a,
                node_r=chamber_r, node_in=node_in, node_floor=node_in-wall)


def shells(s, f):
    """Pressure shells (kind service_fitting) as closed (a, rho) profiles revolved about the port axis."""
    st = stations(s, f); c, o, w = st['clear'], st['outer'], st['wall']; R = st['chamber_r']; n = f['name']
    return [
        dict(name=n, role='outer neck: hull penetration to the docking face', profile=[(st['top'], c), (st['port_face'], c), (st['port_face'], o), (st['top'], o)]),
        dict(name=f'{n}_Entry_Chamber', role='entry chamber between the outer and inner hatches',
             profile=[(st['bottom'], c), (st['bottom'], R+w), (st['top'], R+w), (st['top'], c), (st['a_out'], c), (st['a_out'], R), (st['a_in'], R), (st['a_in'], c)]),
        dict(name=f'{n}_Trunk_Node', role='trunk node: the inner hatch opens inboard into it, and the route turns down the neck into the trunk',
             profile=[(st['node_floor'], c), (st['node_floor'], st['node_r']+w), (st['bottom'], st['node_r']+w), (st['bottom'], st['node_r']),
                      (st['node_in'], st['node_r']), (st['node_in'], c)]),
        dict(name=f'{n}_Inboard_Neck', role='inboard neck from the crew connector to the trunk node',
             profile=[(st['root'], c), (st['node_floor'], c), (st['node_floor'], o), (st['root'], o)]),
    ]


def hinge(s, f, which):
    """Hinge frame of the outer or inner hatch: origin on the leaf's inboard face at r_hinge, e1 the hinge axis (tangent), e2 the
    hinge's radial direction, e3 = u. A positive rotation about e1 swings the leaf inboard (the outer one into the chamber, the inner
    one toward the trunk)."""
    h = s['human_entry']; st = stations(s, f); u, w = axes(f)
    phi = math.radians(h['outer_hinge_deg' if which == 'outer' else 'inner_hinge_deg'])
    a = st['outer_hinge_a' if which == 'outer' else 'inner_hinge_a']
    return dict(origin=world(f, a, st['r_hinge'], phi), e1=vec(f, 0.0, -math.sin(phi), math.cos(phi)),
                e2=vec(f, 0.0, math.cos(phi), math.sin(phi)), e3=u, open_deg=h['hatch_open_deg'], r_hinge=st['r_hinge'],
                r_leaf=st['r_leaf'], thickness=h['hatch_leaf_thickness_m'])


def leaf_local(s, f, which, n=32):
    """Closed-leaf disc in hinge coordinates (e1, e2, e3): centre at e2 = -r_hinge, faces at e3 = 0 and the leaf thickness."""
    g = hinge(s, f, which)
    rim = [(g['r_leaf']*math.sin(2*math.pi*k/n), -g['r_hinge']+g['r_leaf']*math.cos(2*math.pi*k/n)) for k in range(n)]
    return [(x, y, z) for z in (0.0, g['thickness']) for x, y in rim]


def leaf_points(s, f, which, angle_deg, n=24, rings=3):
    """Vehicle-frame samples of a leaf opened by angle_deg: rims and inner circles on both faces, and the centres."""
    g = hinge(s, f, which); c, sn = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg)); out = []
    for z in (0.0, g['thickness']):
        pts = [(0.0, -g['r_hinge'])]+[(g['r_leaf']*k/rings*math.sin(2*math.pi*j/n), -g['r_hinge']+g['r_leaf']*k/rings*math.cos(2*math.pi*j/n))
                                      for k in range(1, rings+1) for j in range(n)]
        for x, y in pts:
            y2, z2 = y*c-z*sn, y*sn+z*c
            out.append(tuple(g['origin'][i]+x*g['e1'][i]+y2*g['e2'][i]+z2*g['e3'][i] for i in range(3)))
    return out


def fixtures(s, f):
    """Hatch frames, handrails with brackets, lights, panels and equalization valves of the entry chamber and the trunk node (kind
    entry_fixture). Rings are (a, rho) profiles, rods are point lists with a radius, boxes are centre (a, rho, phi) and size (along u,
    tangential, radial)."""
    h = s['human_entry']; st = stations(s, f); n = f['name']; R = st['chamber_r']; out = []
    for which in ('outer', 'inner'):
        a0, a1 = st[f'{which}_frame']
        out.append(dict(name=f'{n}_{which.title()}_Hatch_Frame', shape='ring', role=f'{which} hatch frame and seal land',
                        profile=[(a0, st['clear']), (a0, st['r_hinge']), (a1, st['r_hinge']), (a1, st['clear'])]))
    rr = R-h['handrail_standoff_m']; la, lt, lr = h['light_size_m']
    # Zone 1 is the entry chamber, zone 2 the trunk node below the inner hatch (its parked leaf lies on the aft side, so its lights face forward).
    for room, (lo, hi), lights in (('', (st['a_in'], st['a_out']), h['light_deg']), ('Node_', (st['node_in'], st['bottom']), h['node_light_deg'])):
        a0, a1 = lo+h['handrail_end_gap_m'], hi-h['handrail_end_gap_m']
        for k, deg in enumerate(h['handrail_deg'], 1):
            phi = math.radians(deg)
            out.append(dict(name=f'{n}_{room}Handrail_{k}', shape='rod', role='handrail', radius=h['handrail_radius_m'], points=[world(f, a0, rr, phi), world(f, a1, rr, phi)]))
            for j, a in enumerate((a0+.05, (a0+a1)/2, a1-.05), 1):
                out.append(dict(name=f'{n}_{room}Handrail_{k}_Bracket_{j}', shape='rod', role='handrail bracket', radius=h['handrail_radius_m']*.7,
                                points=[world(f, a, rr+h['handrail_radius_m'], phi), world(f, a, R, phi)]))
        for k, deg in enumerate(lights, 1):
            out.append(dict(name=f'{n}_{room}Light_{k}', shape='box', role='light strip', centre=((lo+hi)/2, R-lr/2, math.radians(deg)), size=(la, lt, lr)))
    pa, pt, pr = h['panel_size_m']
    out.append(dict(name=f'{n}_Entry_Panel', shape='box', role='leak-check, equalization and hatch-status panel',
                    centre=(st['a_in']+.2+pa/2, R-pr/2, math.radians(h['panel_deg'])), size=(pa, pt, pr)))
    out.append(dict(name=f'{n}_Node_Panel', shape='box', role='inner-hatch status and equalization panel (ship side)',
                    centre=(st['bottom']-.2-pa/2, R-pr/2, math.radians(h['node_panel_deg'])), size=(pa, pt, pr)))
    for which, (b0, b1), deg in (('Outer', (st['a_out']-h['valve_length_m'], st['a_out']), h['valve_deg']), ('Inner', (st['a_in'], st['a_in']+h['valve_length_m']), h['valve_deg']),
                                 ('Inner_Node', (st['bottom']-h['valve_length_m'], st['bottom']), h['node_valve_deg'])):
        out.append(dict(name=f'{n}_Equalization_Valve_{which}', shape='rod', role=f"{which.split('_')[0].lower()} hatch pressure-equalization valve", radius=h['valve_radius_m'],
                        points=[world(f, b0, h['valve_rho_m'], math.radians(deg)), world(f, b1, h['valve_rho_m'], math.radians(deg))]))
    return out


def openings(s):
    """Branch openings off the trunk as (name, x, angle, radius): every fitting connector, the refuge port and the spine ports; the hollow
    connectors are open now, the others mark where later zones cut their hatches."""
    return [(q['name'], q['points'][0][0], math.atan2(q['points'][0][2], q['points'][0][1]), q['radius']) for q in crew_transfer.stationary(s)[1:]]


def clear_spans(s, rho, angle, x0, x1, margin=None):
    """Pieces of [x0, x1] along the trunk at radius rho and angle that stay `margin` (default opening_margin_m) clear of every branch opening."""
    m = s['human_entry']['opening_margin_m'] if margin is None else margin; spans = [(x0, x1)]
    for _, x, th, r in openings(s):
        d = crew_transfer.angle_diff(angle, th); lateral = rho*math.sin(d)
        if math.cos(d) <= 0 or lateral >= r+m:
            continue
        half = math.sqrt((r+m)**2-lateral**2)
        spans = [piece for a, b in spans for piece in ((a, min(b, x-half)), (max(a, x+half), b)) if piece[1] > piece[0]]
    return spans


def trunk_ladder(s):
    """Thrust review: the trunk ladder in the vehicle frame. Angle th about the ship axis; stiles at radius rl and half-angle phi (the tube
    ladders' width and standoff); from the floor (the trunk's aft end; under thrust aft is down) to the top, where the first branch passage either
    stile line would cross stops it, less handrail_end_gap_m (`spans` are each stile line's clear pieces, none required beside a mouth); rung
    stations on the tube ladders' pitch from landing_first_rung_m above the floor; the fall-arrest rail's radius (on the centre line, resting on
    the climber's side of the rungs) and rod radius, from one end gap above the floor to the top."""
    h = s['human_entry']; c = s['crew_transfer']; trunk = crew_transfer.stationary(s)[0]; rl = c['trunk_clear_radius_m']-h['spoke_ladder_standoff_m']
    phi = math.asin(h['spoke_ladder_width_m']/2/rl); th = math.radians(h['trunk_ladder_deg'])
    floor, x1 = trunk['points'][0][0]+c['passage_wall_m'], trunk['points'][1][0]-c['passage_wall_m']
    spans = {a: clear_spans(s, rl, a, floor, x1, margin=0.0) for a in (th-phi, th+phi)}
    top = min(sp[0][1] for sp in spans.values())-h['handrail_end_gap_m']; r = h['handrail_radius_m']; a, p = h['landing_first_rung_m'], h['spoke_rung_pitch_m']
    rungs = [floor+a+p*i for i in range(int((top-r-floor-a)/p+1e-9)+1)]; rr = h['spoke_arrest_rail_radius_m']
    return dict(th=th, rl=rl, phi=phi, stiles=(th-phi, th+phi), floor=floor, top=top, spans=spans, rungs=rungs,
                rail_r=rl*math.cos(phi)-r-rr, rail_rr=rr, rail=(floor+h['handrail_end_gap_m'], top))


def port_rail_stations(s):
    """(x, angle, outer radius) of the trunk ports that get a short rail on each side at their angle: the refuge port and, HUM-002, the
    storeroom port."""
    return [(q['points'][0][0], math.atan2(q['points'][0][2], q['points'][0][1]), q['radius']) for q in crew_transfer.stationary(s)
            if q['role'] in ('REFUGE_PORT', 'STORE_PORT')]


def trunk_fixtures(s):
    """Zone 2: the trunk's handrails with brackets and its light strips (kind entry_fixture), in the vehicle frame. Rails stop and lights are
    skipped clear of every branch opening; boxes carry a world centre and axes (along X, tangential, radial). Refuge leg (eye-level review): a
    short rail on each side of the refuge port at its angle (Crew_Trunk_Refuge_Rail_1 aft, _2 forward), to stop at the port and turn into it;
    HUM-002 the same pair at the storeroom port (Crew_Trunk_Store_Rail_*).
    Thrust review: the trunk ladder (trunk_ladder): two stiles from the floor to the top with brackets to the wall every trunk_bracket_pitch_m,
    the rungs, and the fall-arrest rail resting on them, bracketed to the wall at its ends ('rods' are segment lists)."""
    h = s['human_entry']; c = s['crew_transfer']; trunk = crew_transfer.stationary(s)[0]; tr = c['trunk_clear_radius_m']
    x0, x1 = trunk['points'][0][0]+c['passage_wall_m'], trunk['points'][1][0]-c['passage_wall_m']; rr = tr-h['handrail_standoff_m']; out = []
    (xr, thr, rr_), (xs, ths, rs) = port_rail_stations(s); g = h['opening_margin_m']+h['refuge_port_rail_m']
    rails = [(f'Crew_Trunk_Handrail_{k}', 'trunk handrail', math.radians(deg), x0+h['handrail_end_gap_m'], x1-h['handrail_end_gap_m'])
             for k, deg in enumerate(h['trunk_handrail_deg'], 1)]+[('Crew_Trunk_Refuge_Rail', 'refuge port handrail', thr, xr-rr_-g, xr+rr_+g),
                                                                   ('Crew_Trunk_Store_Rail', 'storeroom port handrail', ths, xs-rs-g, xs+rs+g)]
    for base, role, th, lo, hi in rails:
        for j, (a, b) in enumerate(clear_spans(s, rr, th, lo, hi), 1):
            if b-a < .5:
                continue
            out.append(dict(name=f'{base}_{j}', shape='rod', role=role, radius=h['handrail_radius_m'],
                            points=[crew_transfer.radial(a, rr, th), crew_transfer.radial(b, rr, th)]))
            nb = math.ceil((b-a-.1)/h['trunk_bracket_pitch_m'])
            for i in range(nb+1):
                x = a+.05+(b-a-.1)*i/nb
                out.append(dict(name=f'{base}_{j}_Bracket_{i+1}', shape='rod', role='handrail bracket', radius=h['handrail_radius_m']*.7,
                                points=[crew_transfer.radial(x, rr+h['handrail_radius_m'], th), crew_transfer.radial(x, tr, th)]))
    la, lt, lr = h['light_size_m']; pitch = h['trunk_light_pitch_m']
    for k, deg in enumerate(h['trunk_light_deg'], 1):
        th = math.radians(deg); ax = ((1.0, 0.0, 0.0), (0.0, -math.sin(th), math.cos(th)), (0.0, math.cos(th), math.sin(th)))
        spans = clear_spans(s, tr-lr, th, x0, x1)
        for i in range(int((x1-x0)/pitch)):
            x = x0+pitch*(i+.5)
            if any(a <= x-la/2 and x+la/2 <= b for a, b in spans):
                out.append(dict(name=f'Crew_Trunk_Light_{k}_{i+1}', shape='box', role='light strip', world_centre=crew_transfer.radial(x, tr-lr/2, th), axes=ax, size=(la, lt, lr)))
    L = trunk_ladder(s); r = h['handrail_radius_m']; R = crew_transfer.radial; brackets = []
    for j, a in enumerate(L['stiles'], 1):
        out.append(dict(name=f'Crew_Trunk_Ladder_Stile_{j}', shape='rod', role='ladder stile', radius=r, points=[R(L['floor']+r, L['rl'], a), R(L['top'], L['rl'], a)]))
        nb = math.ceil((L['top']-L['floor']-.2)/h['trunk_bracket_pitch_m'])
        brackets += [(R(x, L['rl']+r, a), R(x, tr, a)) for x in (L['floor']+.1+(L['top']-L['floor']-.2)*i/nb for i in range(nb+1))]
    out.append(dict(name='Crew_Trunk_Ladder_Brackets', shape='rods', role='ladder bracket', radius=r*.7, segments=brackets))
    out.append(dict(name='Crew_Trunk_Ladder_Rungs', shape='rods', role='ladder rungs', radius=r, segments=[tuple(R(x, L['rl'], a) for a in L['stiles']) for x in L['rungs']]))
    (a, b), ra, rr = L['rail'], L['rail_r'], L['rail_rr']
    out.append(dict(name='Crew_Trunk_Arrest_Rail', shape='rod', role='fall-arrest guide rail', radius=rr, points=[R(a, ra, L['th']), R(b, ra, L['th'])]))
    out.append(dict(name='Crew_Trunk_Arrest_Rail_Brackets', shape='rods', role='fall-arrest rail bracket', radius=r*.7,
                    segments=[(R(x, ra+rr, L['th']), R(x, tr, L['th'])) for x in (a+.05, b-.05)]))
    return out


def vestibule_station(s, j=None):
    """Zone 3: human-entry rotor j (default ring A, the first of vestibule_rotors), its vestibule stations (crew_transfer.vestibule) and its
    rotor-local sector angles."""
    j = j or s['human_entry']['vestibule_rotors'][0]
    rot = next(r for r in rotor_interface.rotors(s) if r['index'] == j)
    return rot, crew_transfer.vestibule(s, j), dict(crew_transfer.sectors(s))


def ring_tag(s, j):
    """Name tag of rotor j's guides: none on ring A (the first human-entry rotor), '_B' on ring B."""
    return '' if j == s['human_entry']['vestibule_rotors'][0] else '_'+'AB'[j-1]


def ring_fixtures(s, j):
    """The zone 3-4 fixtures that ride on rotor j: its vestibule's and, on the tube rotors, its crew tubes'."""
    h = s['human_entry']
    return (vestibule_fixtures(s, j) if j in h['vestibule_rotors'] else [])+(spoke_fixtures(s, j) if j in h['tube_rotors'] else [])


def at_index(rot, p, point=True):
    """Rotor-local point (or direction) -> vehicle frame with the rotor at its index angle (frame 1 and the docked state)."""
    return crew_transfer.to_world(p, rot['x'] if point else 0.0, rot['phase'])


def axes_at(th):
    """Unit axes (along X, tangential, radial) at angle th about the ship axis."""
    return ((1.0, 0.0, 0.0), (0.0, -math.sin(th), math.cos(th)), (0.0, math.cos(th), math.sin(th)))


def vestibule_fixtures(s, j=None):
    """Zone 3: fixtures of rotor j's hollow vestibule, rotor-local at the index (since Q46 parented to the despun transfer drum Drum_j, kind
    entry_fixture): a frame around each sector's opening (the port's size: on ring A the 1.6 m crew-tube opening of zone 4), the drum door's
    seal land from the wall's crown out to the door's track (crew_transfer.transfer_stack), so no part of it hangs into the annulus or crosses
    the running gap to the ring side, an axial handrail with brackets on the outer wall between each pair of hatches,
    a light strip beside each rail (trimmed to a shorter chamber), and the transfer panel (seal and guard-cavity pressure, hatch, spin and
    index-lock status) beside the rail next to the spine port. Tubes are an axis a -> b with inner and outer radius; boxes carry a rotor-local
    centre and axes (along X, tangential, radial)."""
    h = s['human_entry']; rot, v, la = vestibule_station(s, j); n = f"Crew_Vestibule_{rot['index']}"; R = v['clear']; w = h['chamber_wall_m']; out = []
    r0 = v['port_clear']; r1 = r0+h['hatch_frame_width_m']
    # The frame runs from the crown out to the door track: a boss inside the curved wall would leave less than the suited envelope between it
    # and the spine (zone 3 review).
    top = crew_transfer.transfer_stack(s, rot['index'])['door'][0]
    for k, a in la.items():
        out.append(dict(name=f'{n}_Hatch_Frame_{k}', shape='tube', role='drum opening frame and door seal land (crew tube)', r0=r0, r1=r1,
                        a=crew_transfer.radial(v['hatch_u'], R, a), b=crew_transfer.radial(v['hatch_u'], top, a)))
    rr = R-h['handrail_standoff_m']; u0, u1 = v['cu0']+w+h['handrail_end_gap_m'], v['cu1']-w-h['handrail_end_gap_m']; mid = (v['cu0']+v['cu1'])/2
    ll, lt, lr = h['light_size_m']; ll = min(ll, v['cu1']-v['cu0']-2*w-h['handrail_end_gap_m'])
    for k, a in la.items():
        th = a+math.radians(h['vestibule_handrail_offset_deg'])
        out.append(dict(name=f'{n}_Handrail_{k}', shape='rod', role='handrail', radius=h['handrail_radius_m'],
                        points=[crew_transfer.radial(u0, rr, th), crew_transfer.radial(u1, rr, th)]))
        for i, u in enumerate((u0+.05, (u0+u1)/2, u1-.05), 1):
            out.append(dict(name=f'{n}_Handrail_{k}_Bracket_{i}', shape='rod', role='handrail bracket', radius=h['handrail_radius_m']*.7,
                            points=[crew_transfer.radial(u, rr+h['handrail_radius_m'], th), crew_transfer.radial(u, R, th)]))
        th = a+math.radians(h['vestibule_light_offset_deg'])
        out.append(dict(name=f'{n}_Light_{k}', shape='box', role='light strip', world_centre=crew_transfer.radial(mid, R-lr/2, th), axes=axes_at(th), size=(ll, lt, lr)))
    # Q47: a crawl rail round the outer wall crawl_rail_height_m above the aft end wall (the floor with aft down), at the handrails' standoff, in
    # one arc between each pair of openings, opening_margin_m clear of them at its height, below the axial handrails' ends; bracketed to the
    # wall at its ends and every trunk_bracket_pitch_m.
    uc = v['cu0']+w+h['crawl_rail_height_m']; edge = math.sqrt(max(r0**2-(uc-v['hatch_u'])**2, 0.0))+h['opening_margin_m']
    gap = math.asin(min(1.0, edge/rr)); angles = sorted(la.values()); hr = h['handrail_radius_m']
    for k, (a, b) in enumerate(zip(angles, angles[1:]+[angles[0]+math.tau]), 1):
        lo, hi = a+gap, b-gap; m = math.ceil((hi-lo)/math.radians(5)); nb = max(1, math.ceil(((hi-lo)*rr-.1)/h['trunk_bracket_pitch_m']))
        out.append(dict(name=f'{n}_Crawl_Rail_{k}', shape='rod', role='crawl rail (aft down)', radius=hr,
                        points=[crew_transfer.radial(uc, rr, lo+(hi-lo)*i/m) for i in range(m+1)]))
        out.append(dict(name=f'{n}_Crawl_Rail_{k}_Brackets', shape='rods', role='handrail bracket', radius=hr*.7,
                        segments=[(crew_transfer.radial(uc, rr+hr, th), crew_transfer.radial(uc, R, th))
                                  for th in (lo+(.05+((hi-lo)*rr-.1)*i/nb)/rr for i in range(nb+1))]))
    pa, pt, pr = h['panel_size_m']; th = la[v['ports'][0]]+math.radians(h['vestibule_handrail_offset_deg']+h['vestibule_panel_offset_deg'])
    out.append(dict(name=f'{n}_Transfer_Panel', shape='box', role='transfer panel: seal and guard-cavity pressure, hatch, spin and index-lock status',
                    world_centre=crew_transfer.radial(mid, R-pr/2, th), axes=axes_at(th), size=(pa, pt, pr)))
    return out


def spoke_station(s, j=None):
    """Zone 4: tube rotor j (default the first of tube_rotors, ring A), its vestibule, its rotor-local sector angles and the sweep frames of its
    crew tubes (crew_transfer.tube_frames: n1 faces the crew spoke on the run, the last segment, index RUN)."""
    rot, v, la = vestibule_station(s, j or s['human_entry']['tube_rotors'][0])
    return rot, v, la, {k: crew_transfer.tube_frames_of(s, rot['index'], a) for k, a in la.items()}


RUN = 3   # IMPLEMENTATION: segment index of the radial run in crew_transfer.tube_path (root, collar, side, bend, tip)


def ladder(s):
    """Stile radius from the tube axis and the stiles' half-angle about -n1, the wall facing away from the crew spoke (stile angles STILES)."""
    h = s['human_entry']; rl = crew_transfer.tube_radii(s, h['tube_rotors'][0])[1]-h['spoke_ladder_standoff_m']
    return rl, math.asin(h['spoke_ladder_width_m']/2/rl)


def arrest_rail(s):
    """Fall-arrest rail on the ladder's centre line (angle pi from n1): its radius from the tube axis, resting on the climber's side of the rungs
    (whose axes lie rl cos(phi) from the tube axis), and its rod radius."""
    h = s['human_entry']; rl, phi = ladder(s); rr = h['spoke_arrest_rail_radius_m']
    return rl*math.cos(phi)-h['handrail_radius_m']-rr, rr


def stiles(s):
    """Angles (from n1) of the two stile lines on the tube wall."""
    _, phi = ladder(s)
    return (math.pi-phi, math.pi+phi)


def rung_heights(s, lo, hi):
    """Sector-frame heights y (deck 0, inboard negative) of the zone 4-5 rung grid inside [lo, hi]: landing_first_rung_m above the deck, then
    every spoke_rung_pitch_m inboard, one rhythm from the deck up the crew tube's run."""
    h = s['human_entry']; a, p = h['landing_first_rung_m'], h['spoke_rung_pitch_m']
    i0 = math.ceil((-hi-a)/p-1e-9); i1 = math.floor((-lo-a)/p+1e-9)
    return [-(a+p*i) for i in range(max(i0, 0), i1+1)]


def run_span(s, fr):
    """Range of t (from the bend joint along the run) that the ladder uses: from where both stile lines have left the bend's miter plane to one
    leaf clearance above the sector hatch's seat (zone 5: the ladder breaks at the leaf). The run is parallel to its sector's radial, so
    t = sector-frame height y + deck radius - the bend's radial coordinate."""
    rl, _ = ladder(s); p0, d = fr['points'][RUN], fr['d'][RUN]
    start = max(crew_transfer.dot(crew_transfer.sub(crew_transfer.tube_point(fr, RUN, rl, a, None), p0), d) for a in stiles(s))
    return start, landing(s)['tube_end']+habitat_ring.floor(s)-crew_transfer.dot(p0, d)


def floor_ladders(s, fr):
    """Q47 aft-down footing of one crew tube (sweep frames fr, rotor-local; with aft down +X is up): per leg i that rises along X, the angle psi
    (from n1) of its floor line (where the leg's section is lowest, the wall the apparent weight presses on), its slope from the horizontal and a
    floor ladder on that line: stiles at psi -/+ the ladder half-angle from where both stile lines have left the leg's lower miter plane to
    where the first meets its upper one, less a FLOOR_LADDER_GAP at each end, and rungs whose tops rise spoke_rung_pitch_m at a time from the
    floor where the leg begins (its lower joint), as far as the stiles reach. t is measured along the leg from joint i."""
    h = s['human_entry']; rl, phi = ladder(s); r = h['handrail_radius_m']; rc = crew_transfer.tube_radii(s, h['tube_rotors'][0])[1]
    P, dot, sub = crew_transfer.tube_point, crew_transfer.dot, crew_transfer.sub; out = []
    for i, d in enumerate(fr['d']):
        if abs(d[0]) < 1e-6:
            continue
        down = (-1.0, 0.0, 0.0); f = crew_transfer.unit(sub(down, tuple(x*dot(down, d) for x in d)))
        psi = math.atan2(dot(f, fr['n2'][i]), dot(f, fr['n1'][i])); st = (psi-phi, psi+phi); p0 = fr['points'][i]
        t0 = max(dot(sub(P(fr, i, rl, a, None), p0), d) for a in st)+FLOOR_LADDER_GAP
        t1 = min(dot(sub(P(fr, i+1, rl, a, None), p0), d) for a in st)-FLOOR_LADDER_GAP
        floor = min(P(fr, e, rc, psi, None)[0] for e in (i, i+1)); x0 = P(fr, i, rl*math.cos(phi), psi, 0.0)[0]+r      # a rung's top at t is x0 + d_x t
        ts = sorted((floor+h['spoke_rung_pitch_m']*k-x0)/d[0] for k in range(1, int(abs(d[0])*(t1-t0)/h['spoke_rung_pitch_m'])+3))
        out.append(dict(leg=i, psi=psi, stiles=st, slope_deg=math.degrees(math.asin(abs(d[0]))), t=(t0, t1), rungs=[x for x in ts if t0+r <= x <= t1-r],
                        floor=f))
    return out


FLOOR_LADDER_GAP = 0.05     # IMPLEMENTATION: a floor ladder's stiles stop this far short of where they meet a miter plane


def spoke_fixtures(s, j=None):
    """Zone 4: fixtures of tube rotor j's crew tubes, rotor-local (parented to Rotor_j, kind entry_fixture). A ladder on the wall facing
    away from the crew spoke: two stiles from just outside the vestibule wall (ring B: above the bulkhead) through both elbows to just above the
    sector hatch's leaf, with brackets to the wall every trunk_bracket_pitch_m, and rungs on the radial run, where spin gravity grows outward,
    on the deck-referenced rung grid (one object of segments each); a fall-arrest rail on the ladder's centre line, resting on the climber's side
    of every rung, from the stiles' start through both elbows to their end above the sector hatch, bracketed to the wall where no rung carries it
    (arrest_rail); light strips on the wall facing the spoke, one in each elbow leg and along the run; above the sector hatch, the tube-side
    hatch panel beside the ladder. Rods are point lists, 'rods' are segment lists."""
    h = s['human_entry']; rot, v, la, frames = spoke_station(s, j); _, rc = crew_transfer.tube_radii(s, rot['index']); rl, phi = ladder(s)
    r = h['handrail_radius_m']; ll, lt, lr = h['light_size_m']; P = crew_transfer.tube_point; out = []; floor = habitat_ring.floor(s)
    for k, fr in frames.items():
        n = f"Crew_Tube_{rot['index']}_{k}"; pts = fr['points']; t0, t1 = run_span(s, fr)
        # The stiles start one end gap outside the vestibule's outer wall (on ring B, above the bulkhead), on the collar.
        c0 = crew_transfer.tube_floor(s, rot['index'])+h['handrail_end_gap_m']-math.dist(pts[0], (pts[0][0], 0.0, 0.0))
        lines = {a: [P(fr, 0, rl, a, c0)]+[P(fr, i, rl, a, None) for i in range(1, RUN+1)]+[P(fr, RUN, rl, a, t1)] for a in stiles(s)}
        for j, (a, line) in enumerate(lines.items(), 1):
            out.append(dict(name=f'{n}_Ladder_Stile_{j}', shape='rod', role='ladder stile', radius=r, points=line))
        brackets = []
        for a, line in lines.items():
            for i, (p, q) in enumerate(zip(line, line[1:])):
                seg = min(i, RUN); m = math.ceil((math.dist(p, q)-.2)/h['trunk_bracket_pitch_m'])
                for b in range(m+1):
                    x = crew_transfer.add(p, crew_transfer.sub(q, p), (.1+(math.dist(p, q)-.2)*b/m)/math.dist(p, q))
                    t = crew_transfer.dot(crew_transfer.sub(x, pts[seg]), fr['d'][seg])
                    brackets.append((P(fr, seg, rl+r, a, t), P(fr, seg, rc, a, t)))
        out.append(dict(name=f'{n}_Ladder_Brackets', shape='rods', role='ladder bracket', radius=r*.7, segments=brackets))
        base = floor-crew_transfer.dot(pts[RUN], fr['d'][RUN])     # t of the sector-frame height y is y + base
        ys = rung_heights(s, t0+r-base, t1-r-base); rungs = [tuple(P(fr, RUN, rl, a, y+base) for a in stiles(s)) for y in ys]
        out.append(dict(name=f'{n}_Ladder_Rungs', shape='rods', role='ladder rungs', radius=r, segments=rungs))
        ra, rr = arrest_rail(s); top = min(min(crew_transfer.dot(crew_transfer.sub(a, pts[RUN]), fr['d'][RUN]) for a in seg) for seg in rungs)-r-rr
        rail = [P(fr, 0, ra, math.pi, c0)]+[P(fr, i, ra, math.pi, None) for i in range(1, RUN+1)]+[P(fr, RUN, ra, math.pi, t1)]
        out.append(dict(name=f'{n}_Arrest_Rail', shape='rod', role='fall-arrest guide rail', radius=rr, points=rail))
        # Brackets every trunk_bracket_pitch_m from the rail's start down to just above the first rung; the rungs carry it on the run.
        mounts = []
        for i, (p, q) in enumerate(zip(rail, rail[1:])):
            span = math.dist(p, q) if i < RUN else crew_transfer.dot(crew_transfer.sub(P(fr, RUN, ra, math.pi, top), p), fr['d'][RUN])
            m = math.ceil((span-.2)/h['trunk_bracket_pitch_m']) if span > .2 else -1
            for b in range(m+1):
                x = crew_transfer.add(p, crew_transfer.sub(q, p), (.1+(span-.2)*b/m)/math.dist(p, q))
                tt = crew_transfer.dot(crew_transfer.sub(x, pts[i]), fr['d'][i])
                mounts.append((P(fr, i, ra+rr, math.pi, tt), P(fr, i, rc, math.pi, tt)))
        out.append(dict(name=f'{n}_Arrest_Rail_Brackets', shape='rods', role='fall-arrest rail bracket', radius=r*.7, segments=mounts))
        # Q47: a floor ladder on each leg that rises with aft down (floor_ladders), its stiles bracketed to the wall at their ends and every
        # trunk_bracket_pitch_m, and a fall-arrest rail on its centre line resting on the climber's side of its rungs (as arrest_rail on the
        # side-wall ladder) along the stiles, bracketed to the wall at both ends, so the climber clips beside the body, not across the bore.
        for fl in floor_ladders(s, fr):
            i, (a0, a1), m = fl['leg'], fl['t'], f"{n}_Floor_Ladder_{fl['leg']}"; nb = max(1, math.ceil((a1-a0-.2)/h['trunk_bracket_pitch_m']))
            for b, a in enumerate(fl['stiles'], 1):
                out.append(dict(name=f'{m}_Stile_{b}', shape='rod', role='aft-down floor ladder stile (handhold)', radius=r, points=[P(fr, i, rl, a, a0), P(fr, i, rl, a, a1)]))
            out.append(dict(name=f'{m}_Brackets', shape='rods', role='ladder bracket', radius=r*.7,
                            segments=[(P(fr, i, rl+r, a, t), P(fr, i, rc, a, t)) for a in fl['stiles'] for t in (a0+.1+(a1-a0-.2)*k/nb for k in range(nb+1))]))
            out.append(dict(name=f'{m}_Rungs', shape='rods', role='aft-down floor ladder rungs', radius=r,
                            segments=[tuple(P(fr, i, rl, a, t) for a in fl['stiles']) for t in fl['rungs']]))
            out.append(dict(name=f'{m}_Arrest_Rail', shape='rod', role='aft-down floor ladder fall-arrest guide rail', radius=rr,
                            points=[P(fr, i, ra, fl['psi'], a0), P(fr, i, ra, fl['psi'], a1)]))
            out.append(dict(name=f'{m}_Arrest_Rail_Brackets', shape='rods', role='floor ladder fall-arrest rail bracket', radius=r*.7,
                            segments=[(P(fr, i, ra+rr, fl['psi'], t), P(fr, i, rc, fl['psi'], t)) for t in (a0+.05, a1-.05)]))
        # Lights on the wall facing the spoke (phi = 0): one in each elbow leg, centred on its straight wall line between the miters and trimmed to
        # it, then every spoke_light_pitch_m along the run.
        spots = []
        for i in (1, 2):
            a, b = (crew_transfer.dot(crew_transfer.sub(P(fr, e, rc, 0.0, None), pts[i]), fr['d'][i]) for e in (i, i+1))
            spots.append((i, (a+b)/2, min(ll, b-a-.2)))
        spots += [(RUN, t0+h['spoke_light_pitch_m']*(i+.5), ll) for i in range(int((t1-t0)/h['spoke_light_pitch_m']))]
        for j, (seg, t, length) in enumerate(spots, 1):
            out.append(dict(name=f'{n}_Light_{j}', shape='box', role='light strip', world_centre=P(fr, seg, rc-lr/2, 0.0, t),
                            axes=(fr['d'][seg], fr['n2'][seg], fr['n1'][seg]), size=(length, lt, lr)))
        pw, ph, pd = h['landing_panel_size_m']; th = math.pi-math.radians(h['spoke_hatch_panel_deg']); n1, n2 = fr['n1'][RUN], fr['n2'][RUN]
        rad = tuple(math.cos(th)*a+math.sin(th)*b for a, b in zip(n1, n2)); tan = tuple(-math.sin(th)*a+math.cos(th)*b for a, b in zip(n1, n2))
        out.append(dict(name=f'{n}_Hatch_Panel', shape='box', role='sector hatch panel, tube side: leaf drive, equalization, sector pressure',
                        world_centre=P(fr, RUN, rc-pd/2, th, max(ys)-h['landing_panel_height_m']+base), axes=(fr['d'][RUN], tan, rad),
                        size=(ph, pw, pd)))
    return out


def spoke_mannequin(s, j=None):
    """Zone 4 figure (non-canon scale guide) on the ladder of the crew tube of tube rotor j's spine-port sector (default ring A, sector 1), head
    inboard: the toes on the rung nearest that rotor's spoke_feet_radius_m, the body spoke_body_offset_m off the tube axis toward the ladder, both
    hands on the stiles above the shoulder, clipped to the fall-arrest rail: a sliding arrester on the rail at chest height and a short link to the
    chest ring. Its eye looks up the shaft toward the elbows (looking down, the body fills the view). Rods are rotor-local ('local') and in the
    vehicle frame at the index pose ('rods', eye, look, up)."""
    m = s['human_entry']['mannequin']; H = s['prototype']['human_height_m']; rot, v, la, frames = spoke_station(s, j); k = v['ports'][0]; fr = frames[k]
    rl, phi = ladder(s); p0, d, n1, n2 = fr['points'][RUN], fr['d'][RUN], fr['n1'][RUN], fr['n2'][RUN]; face = tuple(-x for x in n1)
    rungs = next(q for q in spoke_fixtures(s, rot['index']) if q['name'] == f"Crew_Tube_{rot['index']}_{k}_Ladder_Rungs")
    n = f"Human_Spoke{ring_tag(s, rot['index'])}"
    goal = m['spoke_feet_radius_m'][s['human_entry']['tube_rotors'].index(rot['index'])]-crew_transfer.dot(p0, d)
    t_r = min((crew_transfer.dot(crew_transfer.sub(a, p0), d) for a, _ in rungs['segments']), key=lambda t: abs(t-goal))
    t_f = t_r-rungs['radius']; y0 = m['spoke_body_offset_m']; rung_y = rl*math.cos(phi)
    def at(x, y, z):                 # x across the body (n2), y toward the face (-n1, the ladder), z from the feet toward the head (inboard, -d)
        return crew_transfer.add(crew_transfer.add(crew_transfer.add(p0, d, t_f-z), n2, x), face, y0+y)
    shoulder = at(0, 0, .75*H); grips = [crew_transfer.tube_point(fr, RUN, rl, a, t_f-.87*H) for a in stiles(s)]
    toe = rung_y-y0-.07              # each foot one foot-radius short of the rung axis, its sole on the rung's inboard face
    local_rods = [(f'{n}_Torso', [at(0, 0, .38*H), at(0, 0, .78*H)], .13),
                  (f'{n}_Head', [at(0, 0, H-.20), at(0, 0, H-.11)], .11),
                  (f'{n}_Arm_1', [shoulder, grips[0]], .055),
                  (f'{n}_Arm_2', [shoulder, grips[1]], .055)]
    for sign in (-1, 1):
        local_rods.append((f'{n}_Leg_{sign}', [at(sign*.13, toe, .07), at(0, 0, .40*H)], .07))
    ra, rr = arrest_rail(s); tc = t_f-.72*H; sleeve = rr+.015     # the chest ring at 0.72 H; the arrester a sleeve 0.12 m long round the rail
    local_rods += [(f'{n}_Arrester', [crew_transfer.tube_point(fr, RUN, ra, math.pi, tc+e) for e in (-.06, .06)], sleeve),
                   (f'{n}_Arrester_Link', [at(0, .13, .72*H), crew_transfer.tube_point(fr, RUN, ra-sleeve, math.pi, tc)], .012)]
    eye = at(0, .08, m['eye_height_m']); look = tuple(-x for x in d); up = n1
    reach = {name: math.dist(*pts) for name, pts, _ in local_rods if 'Arm' in name}
    return dict(local=local_rods, rods=[(n, [at_index(rot, q) for q in pts], r) for n, pts, r in local_rods], eye=at_index(rot, eye),
                look=at_index(rot, look, False), up=at_index(rot, up, False), local_eye=eye, grips=grips, feet_t=t_f, head_t=t_f-H,
                feet_radius_m=t_f+crew_transfer.dot(p0, d), reach=reach, sector=k)


def ladder_push(s, j=None):
    """Across-ladder push on crew on tube rotor j's ladder run while the ring spins, in g (eye-level review). The run lies overhead_hatch_z_m
    off its sector's radial, so spin gravity leans the body (spoke_body_offset_m further out, on the ladder side) toward the ladder wall on both
    rings. Moving along the run at v adds the Coriolis push 2 omega v across it: onto the rungs in one direction, off them in the other. Rotor 1
    turns about +X and rotor 2 against it (revision.habitat), so the ladder wall, which faces away from the spoke in the shared sector, is
    antispinward on ring A (pulled off climbing) and spinward on ring B (pulled off descending). At climb_review_speed_m_s: the net push in each
    direction, and the angle by which the apparent down tilts over the climber (the ladder overhangs) or toward the ladder, at the top of the run
    and at the tube tip. The fall from rest at the top of the run to the deck radius, unobstructed (an upper bound): its speed and the 1 g drop
    that gives it."""
    h = s['human_entry']; m = h['mannequin']; w, g = habitat_ring.omega(s), habitat_ring.G0
    rot, v, la, frames = spoke_station(s, j); fr = frames[v['ports'][0]]; L = landing(s); spin = 1 if rot['index'] == 1 else -1
    z = abs(L['z'])+m['spoke_body_offset_m']; lean = w*w*z/g; cor = 2*w*m['climb_review_speed_m_s']/g
    radii = {'run_top': run_span(s, fr)[0]+crew_transfer.dot(fr['points'][RUN], fr['d'][RUN]), 'tube_tip': crew_transfer.dot(fr['points'][-1], fr['d'][RUN])}
    down = {k: w*w*r/g for k, r in radii.items()}; fall = w*math.sqrt(math.hypot(habitat_ring.floor(s), z)**2-math.hypot(radii['run_top'], z)**2)
    return {'ladder_wall': 'antispinward' if spin*L['side'] < 0 else 'spinward', 'pulled_off_when': 'descending' if spin*L['side'] > 0 else 'climbing',
            'body_off_radial_m': z, 'lean_toward_ladder_g': lean, 'coriolis_g_per_m_s': 2*w/g, 'neutral_speed_m_s': w*z/2,
            'review_speed_m_s': m['climb_review_speed_m_s'], 'pulled_off_g': cor-lean, 'pressed_on_g': cor+lean, 'radius_m': radii, 'spin_gravity_g': down,
            'overhang_deg': {k: math.degrees(math.atan2(cor-lean, x)) for k, x in down.items()},
            'at_rest_lean_deg': {k: math.degrees(math.atan2(lean, x)) for k, x in down.items()},
            'fall_speed_m_s': fall, 'fall_height_1g_m': fall**2/2/g}


def landing(s):
    """Zone 5 stations in the sector frame (origin on the centreline at the deck, +X axial, +Y radially outward, +Z tangential), the same in every
    sector: the hatch axis (x, z) under the crew tube's run, `side` (the sign of z, the ladder's side, away from the crew spoke), the frame from
    inside the skin to its seat hatch_frame_depth_m below the overhead, the leaf closed on the seat and slid open toward the aisle, the stile
    line, the two stile ends one leaf clearance from the leaf, the landing well between the aisle and the utility chase and the chase itself."""
    import habitat_interior
    h, r = s['human_entry'], s['habitat_ring']; clr = h['leaf_swing_clearance_m']; sec = habitat_interior.section(s)
    x_h, y_w, z_h = crew_transfer.sector_hatches(s)['overhead_wall']; side = math.copysign(1.0, z_h)
    rc = crew_transfer.tube_radii(s, h['tube_rotors'][0])[1]; rf = rc+h['hatch_frame_width_m']; rleaf = rc+h['hatch_leaf_overlap_m']
    seat = sec['ceiling_y_m']+h['hatch_frame_depth_m']; tl = h['hatch_leaf_thickness_m']; drop = h['landing_leaf_drop_m']
    # The flat frame reaches into the skin where its curved inner face is farthest from the deck: at the frame's outer edge, off the centreline.
    top = math.sqrt((r['sector_inner_radius_m']+r['sector_skin_m'])**2-(abs(z_h)+rf)**2)-habitat_ring.floor(s)-.005
    rl, phi = ladder(s); opened = (seat+drop, seat+drop+tl); chase = abs(z_h)+rf+h['landing_chase_gap_m']; half = h['landing_well_width_m']/2
    end = clr+h['handrail_radius_m']     # a stile's rounded end stays one leaf clearance from the leaf
    wall = habitat_interior.wall_half_width(s, sec['ceiling_y_m'])-s['interior']['wall_allowance_m']
    return dict(x=x_h, z=z_h, side=side, tip_y=y_w, ceiling=sec['ceiling_y_m'], clear_r=rc, frame_r=rf, frame_top=top, seat=seat,
                leaf_r=rleaf, leaf_closed=(seat, seat+tl), leaf_open=opened, leaf_open_z=z_h-side*(2*rleaf+clr), travel=2*rleaf+clr,
                stile_x=(x_h-rl*math.sin(phi), x_h+rl*math.sin(phi)), stile_z=z_h+side*rl*math.cos(phi), stile_top=opened[1]+end, tube_end=seat-end,
                well_x=(x_h-half, x_h+half), well_z=tuple(sorted((side*s['interior']['aisle_m']/2, side*chase))), chase_face=side*chase,
                chase_z=tuple(sorted((side*chase, side*wall))))


def thrust_step(s):
    """Q47: the step ladder below the sector hatch in the sector frame. With aft down the aft skin's inner face is the floor and the overhead a
    side wall, the hatch in it with its sill (the clear opening's aft edge) above the floor. The ladder stands spoke_ladder_standoff_m off the
    overhead, spoke_ladder_width_m wide, centred thrust_step_offset_m off the hatch axis toward the landing ladder: rungs on the landing rung grid
    from the floor (landing_first_rung_m, then spoke_rung_pitch_m) up to the top of the stiles, which end one leaf clearance below the leaf's
    guide rails; the stiles start one end gap above the floor."""
    import habitat_interior
    h = s['human_entry']; L = landing(s); r = h['handrail_radius_m']; clr = h['leaf_swing_clearance_m']
    floor = -(habitat_interior.section(s)['length_m']/2-s['habitat_ring']['sector_skin_m']); rx = L['leaf_r']+clr+h['landing_rail_radius_m']
    top = -(rx+h['landing_rail_radius_m']+clr+r); zc = L['z']+L['side']*h['thrust_step_offset_m']; w = h['spoke_ladder_width_m']/2
    a, p = h['landing_first_rung_m'], h['spoke_rung_pitch_m']; rungs = [floor+a+p*i for i in range(int((top-r-floor-a)/p+1e-9)+1)]
    return dict(floor=floor, x=(floor+h['handrail_end_gap_m']/4, top), y=L['ceiling']+h['spoke_ladder_standoff_m'], z=zc, stile_z=(zc-w, zc+w),
                rungs=rungs, sill=L['x']-L['clear_r'])


def landing_fixtures(s):
    """Zone 5: the sector landing in the sector frame (WF_RING_SECTOR, kind entry_fixture): the hatch frame and seat under the skin's opening,
    the leaf slid open on its two guide rails, the ladder from below the leaf to the deck (stiles, rungs on the shared rung grid, brackets to the
    chase), the utility chase behind it with the hatch panel (leaf drive, equalization, tube pressure) and a light strip on its face, and two
    light strips over the aisle ends. Tubes run a -> b (r0 0 is a solid disc); boxes carry a centre and axes in the sector frame."""
    h = s['human_entry']; L = landing(s); x, z, side = L['x'], L['z'], L['side']; r = h['handrail_radius_m']; ll, lt, lr = h['light_size_m']
    X, Y, Z = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0); zl, zc = L['stile_z'], L['chase_face']; half = h['landing_well_width_m']/2
    out = [dict(name='Sector_Hatch_Frame', shape='tube', role='overhead hatch frame and leaf seat', r0=L['clear_r'], r1=L['frame_r'],
                a=(x, L['frame_top'], z), b=(x, L['seat'], z)),
           dict(name='Sector_Hatch_Leaf', shape='tube', role='overhead hatch leaf, slid open', r0=0.0, r1=L['leaf_r'],
                a=(x, L['leaf_open'][0], L['leaf_open_z']), b=(x, L['leaf_open'][1], L['leaf_open_z']))]
    # Guide rails one clearance outside the leaf's edge, at its mid-thickness, from behind the closed leaf to beyond the open one.
    rx = L['leaf_r']+h['leaf_swing_clearance_m']+h['landing_rail_radius_m']; ym = sum(L['leaf_open'])/2; reach = L['leaf_r']+h['leaf_swing_clearance_m']
    z0, z1 = sorted((z+side*reach, L['leaf_open_z']-side*reach))
    for j, sx in enumerate((-1, 1), 1):
        out.append(dict(name=f'Sector_Hatch_Rail_{j}', shape='rod', role='leaf guide rail', radius=h['landing_rail_radius_m'], points=[(x+sx*rx, ym, z0), (x+sx*rx, ym, z1)]))
    for j, xs in enumerate(L['stile_x'], 1):
        out.append(dict(name=f'Sector_Ladder_Stile_{j}', shape='rod', role='ladder stile', radius=r, points=[(xs, L['stile_top'], zl), (xs, 0.0, zl)]))
    out.append(dict(name='Sector_Ladder_Rungs', shape='rods', role='ladder rungs', radius=r,
                    segments=[((L['stile_x'][0], y, zl), (L['stile_x'][1], y, zl)) for y in rung_heights(s, L['stile_top']+r, -r)]))
    out.append(dict(name='Sector_Ladder_Brackets', shape='rods', role='ladder bracket', radius=r*.7,
                    segments=[((xs, -y, zl+side*r), (xs, -y, zc)) for xs in L['stile_x'] for y in h['landing_bracket_heights_m']]))
    (c0, c1), ceiling = L['chase_z'], L['ceiling']
    out.append(dict(name='Sector_Landing_Chase', shape='box', role='utility chase: leaf drive, equalization valve, power and data',
                    world_centre=(x, ceiling/2, (c0+c1)/2), axes=(X, Z, Y), size=(2*half, c1-c0, -ceiling)))
    pw, ph, pd = h['landing_panel_size_m']; inset = .04
    out.append(dict(name='Sector_Hatch_Panel', shape='box', role='hatch panel: leaf drive, equalization, tube and sector pressure',
                    world_centre=(x-half+inset+pw/2, -h['landing_panel_height_m'], zc-side*pd/2), axes=(X, Y, Z), size=(pw, ph, pd)))
    out.append(dict(name='Sector_Landing_Light', shape='box', role='light strip', world_centre=(x+half-inset-lt/2, -h['landing_panel_height_m']-.25, zc-side*lr/2),
                    axes=(Y, X, Z), size=(ll, lt, lr)))
    for j, xa in enumerate(h['landing_aisle_light_x_m'], 1):
        out.append(dict(name=f'Sector_Aisle_Light_{j}', shape='box', role='light strip', world_centre=(xa, ceiling+lr/2, 0.0), axes=(Z, X, Y), size=(ll, lt, lr)))
    # Q47: the step ladder below the hatch for aft down (thrust_step), bracketed to the overhead at both ends of each stile.
    S = thrust_step(s); (x0, x1), y = S['x'], S['y']
    for j, zs in enumerate(S['stile_z'], 1):
        out.append(dict(name=f'Sector_Thrust_Step_Stile_{j}', shape='rod', role='aft-down step stile', radius=r, points=[(x0, y, zs), (x1, y, zs)]))
    out.append(dict(name='Sector_Thrust_Step_Rungs', shape='rods', role='aft-down steps', radius=r,
                    segments=[((x, y, S['stile_z'][0]), (x, y, S['stile_z'][1])) for x in S['rungs']]))
    out.append(dict(name='Sector_Thrust_Step_Brackets', shape='rods', role='ladder bracket', radius=r*.7,
                    segments=[((x, y-r, zs), (x, ceiling, zs)) for x in (x0+.05, x1-.05) for zs in S['stile_z']]))
    return out


def sector_frame(s):
    """The human-entry rotor, the landing sector (the spine port's) and maps from its sector frame to the vehicle frame at the index pose."""
    rot, v, la = vestibule_station(s); k = v['ports'][0]; _, X, Y, Z = crew_transfer.sector_axes(s, la[k])
    point = lambda p: at_index(rot, crew_transfer.sector_point(s, la[k], p))
    vector = lambda d: at_index(rot, tuple(X[i]*d[0]+Y[i]*d[1]+Z[i]*d[2] for i in range(3)), False)
    return rot, k, point, vector


def landing_mannequin(s):
    """Zone 5 figure (non-canon scale guide) standing on the deck of the ring-A sector-1 landing well at the foot of the ladder, facing it: the body
    axis landing_body_gap_m from the stile line, both hands on the stiles at landing_grip_height_m. Its eye looks up the ladder through the open
    hatch into the crew tube. Rods are in the sector frame ('local') and in the vehicle frame at the index pose ('rods', eye, look, up)."""
    m = s['human_entry']['mannequin']; H = s['prototype']['human_height_m']; L = landing(s); side = L['side']; r = s['human_entry']['handrail_radius_m']
    zb = L['stile_z']-side*m['landing_body_gap_m']; rot, k, point, vector = sector_frame(s)
    def at(x, y, z):                 # x across the body (+X), y toward the face (the ladder, +side), z up from the soles (-Y)
        return (L['x']+x, -z, zb+side*y)
    shoulder = at(0, 0, .75*H); grips = [(xs, -m['landing_grip_height_m'], L['stile_z']-side*r) for xs in L['stile_x']]
    local_rods = [('Human_Landing_Torso', [at(0, 0, .38*H), at(0, 0, .78*H)], .13),
                  ('Human_Landing_Head', [at(0, 0, H-.20), at(0, 0, H-.11)], .11),
                  ('Human_Landing_Arm_1', [shoulder, grips[0]], .055),
                  ('Human_Landing_Arm_2', [shoulder, grips[1]], .055)]
    for sign in (-1, 1):
        local_rods.append((f'Human_Landing_Leg_{sign}', [at(sign*.13, 0, .07), at(0, 0, .40*H)], .07))
    eye = at(0, .08, m['eye_height_m']); aim = (L['x'], L['tip_y']-9.0, L['z'])
    look = crew_transfer.unit(crew_transfer.sub(aim, eye)); up = crew_transfer.unit(crew_transfer.sub((0.0, 0.0, -side), tuple(x*-side*look[2] for x in look)))
    reach = {name: math.dist(*pts) for name, pts, _ in local_rods if 'Arm' in name}
    return dict(local=local_rods, rods=[(n, [point(q) for q in pts], rr) for n, pts, rr in local_rods], eye=point(eye), look=vector(look), up=vector(up),
                local_eye=eye, grips=grips, reach=reach, sector=k, body_z=zb)


def landing_aisle_view(s):
    """Camera standing in the landing sector's aisle at eye height, landing_aisle_camera_z_m across the centreline from the well, looking at the
    hatch frame's underside (vehicle frame at the index pose)."""
    m = s['human_entry']['mannequin']; L = landing(s); _, _, point, vector = sector_frame(s)
    at = (L['x'], -m['eye_height_m'], -L['side']*m['landing_aisle_camera_z_m']); look = crew_transfer.unit(crew_transfer.sub((L['x'], L['seat']+.5, L['z']), at))
    up = crew_transfer.unit(crew_transfer.sub((0.0, -1.0, 0.0), tuple(x*-look[1] for x in look)))
    return dict(at=point(at), look=vector(look), up=vector(up), local=at)


def refuge_station(s):
    """Refuge leg (OD-011 access path): the storm refuge (hull_geometry.refuge) with its port off the trunk (crew_transfer.stationary): the port's
    station x, angle th, clear and outer radius; the inner pressure wall (chamber_wall_m inside the cavity's inner face, so the cavity keeps its
    volume); the stations of the hoop rails (opening_margin_m beyond the port on each side, aft first); one occupant station per rated occupant,
    each a suited body lying axially inboard of its anchor rail on the outer wall (rail angles from half a pitch beside the port, rail and
    body-axis radii); and the circulation radius midway between the inner-wall fixtures and the occupants' envelopes."""
    h = s['human_entry']; ref = hull_geometry.refuge(s); R = h['mannequin']['suited_envelope_diameter_m']/2; rh = h['handrail_radius_m']
    port = next(q for q in crew_transfer.stationary(s) if q['role'] == 'REFUGE_PORT'); (x, y, z), _ = port['points']; th = math.atan2(z, y)
    n = ref['capacity_persons']; pitch = 2*math.pi/n; anchor = ref['pressure']-h['handrail_standoff_m']; body = anchor-rh-R
    # The panel's back rests on the convex wall at its edges; the hoop rails stand furthest from the wall.
    hoop = ref['inner']+h['handrail_standoff_m']; inner_fix = max(hoop+rh, math.sqrt(ref['inner']**2-(h['panel_size_m'][1]/2)**2)+h['panel_size_m'][2])
    return dict(ref, x=x, th=th, clear=port['hollow'], outer_r=port['radius'], wall=(ref['inner']-h['chamber_wall_m'], ref['inner']),
                hoop_r=hoop, hoop_x=[x-port['radius']-h['opening_margin_m'], x+port['radius']+h['opening_margin_m']],
                pitch=pitch, anchors=[th+pitch*(k+.5) for k in range(n)], anchor_r=anchor, body_r=body, inner_fixture_r=inner_fix,
                circulation_r=(inner_fix+body-R)/2)


def refuge_fixtures(s):
    """Refuge leg: fixtures of the storm refuge in the vehicle frame (kind entry_fixture): a hoop handrail round the inner wall on each side of the
    port, bracketed at every anchor angle; an axial anchor rail on the outer wall for each occupant with three brackets; a light strip on the outer
    wall between every other pair of anchor rails (one across from the port); and the refuge panel on the inner wall beside the port."""
    h = s['human_entry']; r = refuge_station(s); rh = h['handrail_radius_m']; out = []; n = 72
    for tag, x in zip(('Aft', 'Fwd'), r['hoop_x']):
        out.append(dict(name=f'Refuge_Hoop_Rail_{tag}', shape='rod', role='handrail', radius=rh,
                        points=[crew_transfer.radial(x, r['hoop_r'], r['th']+2*math.pi*k/n) for k in range(n+1)]))
        out.append(dict(name=f'Refuge_Hoop_Rail_{tag}_Brackets', shape='rods', role='handrail bracket', radius=rh*.7,
                        segments=[(crew_transfer.radial(x, r['hoop_r']-rh, a), crew_transfer.radial(x, r['inner'], a)) for a in r['anchors']]))
    a0, a1 = r['cavity_x0']+h['handrail_end_gap_m'], r['cavity_x1']-h['handrail_end_gap_m']; ra = r['anchor_r']
    for k, a in enumerate(r['anchors'], 1):
        out.append(dict(name=f'Refuge_Anchor_Rail_{k}', shape='rod', role='occupant anchor rail', radius=rh,
                        points=[crew_transfer.radial(a0, ra, a), crew_transfer.radial(a1, ra, a)]))
        out.append(dict(name=f'Refuge_Anchor_Rail_{k}_Brackets', shape='rods', role='handrail bracket', radius=rh*.7,
                        segments=[(crew_transfer.radial(x, ra+rh, a), crew_transfer.radial(x, r['pressure'], a)) for x in (a0+.05, (a0+a1)/2, a1-.05)]))
    ll, lt, lr = h['light_size_m']; ll = min(ll, a1-a0)
    for k in range(len(r['anchors'])//2):
        a = r['th']+2*r['pitch']*k
        out.append(dict(name=f'Refuge_Light_{k+1}', shape='box', role='light strip', world_centre=crew_transfer.radial(r['x'], r['pressure']-lr/2, a),
                        axes=axes_at(a), size=(ll, lt, lr)))
    pa, pt, pr = h['panel_size_m']; a = r['th']+math.radians(h['refuge_panel_deg'])
    out.append(dict(name='Refuge_Panel', shape='box', role='refuge panel: dose rate, cabin pressure and air, communications and port status',
                    world_centre=crew_transfer.radial(r['x'], math.sqrt(r['inner']**2-(pt/2)**2)+pr/2, a), axes=axes_at(a), size=(pa, pt, pr)))
    return out


def refuge_mannequin(s):
    """Refuge-leg figure (non-canon scale guide) floating in the storm refuge beside its port, along a tangential chord at refuge_body_radius_m
    over the aft hoop rail, head toward the port, facing the inner wall: the shoulder at the refuge panel's angle, one hand on the rail straight in
    from it, the other reaching toward the panel. Its eye looks round the annulus past the port to the first anchor rail beyond it. Vehicle frame."""
    h, m = s['human_entry'], s['human_entry']['mannequin']; H = s['prototype']['human_height_m']; r = refuge_station(s); fx = refuge_fixtures(s)
    panel = next(q for q in fx if q['name'] == 'Refuge_Panel'); sg = -1 if h['refuge_panel_deg'] >= 0 else 1
    Rc = m['refuge_body_radius_m']; xb = r['hoop_x'][0]; th = r['th']+math.radians(h['refuge_panel_deg'])-sg*math.atan2(.75*H-H/2, Rc)
    C = crew_transfer.radial(xb, Rc, th); _, t, y = axes_at(th)
    def at(x, yy, z):                # x across the body (+X), yy toward the face (inward), z from the feet toward the head (sg t)
        return (C[0]+x, C[1]-yy*y[1]+sg*(z-H/2)*t[1], C[2]-yy*y[2]+sg*(z-H/2)*t[2])
    shoulder = at(0, 0, .75*H); grip = crew_transfer.radial(xb, r['hoop_r']+h['handrail_radius_m'], math.atan2(shoulder[2], shoulder[1]))
    d = crew_transfer.unit(crew_transfer.sub(panel['world_centre'], shoulder))
    rods = [('Human_Refuge_Torso', [at(0, 0, .38*H), at(0, 0, .78*H)], .13),
            ('Human_Refuge_Head', [at(0, 0, H-.20), at(0, 0, H-.11)], .11),
            ('Human_Refuge_Arm_Rail', [shoulder, grip], .055),
            ('Human_Refuge_Arm_Reach', [shoulder, crew_transfer.add(shoulder, d, .50)], .055)]
    for sign in (-1, 1):
        rods.append((f'Human_Refuge_Leg_{sign}', [at(sign*.13, 0, .07), at(0, 0, .40*H)], .07))
    eye = at(0, .08, m['eye_height_m']); aim = crew_transfer.radial(r['x'], r['body_r'], r['th']+sg*r['pitch']/2)
    up = crew_transfer.unit(crew_transfer.radial(0.0, 1.0, math.atan2(eye[2], eye[1])))
    reach = {name: math.dist(*pts) for name, pts, _ in rods if 'Arm' in name}
    return dict(rods=rods, eye=eye, look=crew_transfer.sub(aim, eye), up=up, grip=grip, reach=reach)


def route(s):
    """The primary boarding route to each sector of each human-entry ring, keyed ring letter + sector ('A1'...), in the vehicle frame at the
    docked pose (the rotors at their index angle): 'path' is a waypoint polyline, each waypoint tagged with the zone of the leg that ends there.
    It runs along the port axis from one body length outside the docking face through the chamber (zone 1) and the trunk node, neck and
    connector to the trunk axis, aft along the trunk to the ring's spine port (zone 2), up the port's axis to the vestibule chamber's mid-depth,
    around the annulus to the sector's hatch (zone 3); on a tube rotor along the crew tube's axis through its elbows to the tip (zone 4) and
    down the hatch axis until the suited envelope touches the deck (zone 5), where 'walk' holds the upright suited body's axis (feet to head
    sphere centres) from the foot of the ladder across the deck to the aisle centre. On ring B the tube leg starts through the neck at the
    bulkhead (crew_transfer.tube_neck). A ring that is not a tube rotor ends at each hatch. Route 'R' (the refuge leg, zone 'R') leaves the trunk
    axis at the refuge port, rises along the port's axis to the refuge's circulation radius and goes half way round the annulus there, past the
    refuge panel. Route 'E' (emergency, eye-level review) comes forward along the trunk axis from the nearest spine port aft of the refuge, turns
    up the same port and goes round the other half. The two-chord body is the same in either direction (route_bodies), so the sector routes
    reversed and then route 'E' give the emergency route from any sector into the refuge. IND-001 adds the induction ring's legs between its
    sectors ('A1-A3', 'A3-A2'; induction()): from the first sector's deck up its tube, round the annulus, down the next one's tube to its aisle;
    Q51 adds Seraph's service path from the habitation sector to the workshop's ('A1-A2', [route_fitout] seraph_service_sectors) the same way.
    The route that ends in an induction sector carries 'stops': per sector stop in order, its key and the upright walk along the aisle
    centreline from the previous stop (first from the aisle centre at the landing) to it (induction_stations)."""
    R = s['human_entry']['mannequin']['suited_envelope_diameter_m']/2; H = s['prototype']['human_height_m']; f = ports(s)[0]; st = stations(s, f); L = landing(s)
    out = {}; entry = [(1, world(f, st['port_face']+H-2*R)), (1, world(f, st['bottom'])), (2, world(f, 0.0))]
    for j in s['human_entry']['vestibule_rotors']:
        rot, v, la = vestibule_station(s, j); k0 = v['ports'][0]; mid = (v['r0']+v['clear'])/2; tag = 'AB'[j-1]
        frames = spoke_station(s, j)[3] if j in s['human_entry']['tube_rotors'] else {}
        head = entry+[(2, (rot['x']+v['port_u'], 0.0, 0.0))]; descent, walks = {}, {}
        def around(a0, a1, rot=rot, pu=v['port_u'], mid=mid):
            turn = math.remainder(a1-a0, 2*math.pi); n = max(1, math.ceil(abs(turn)/math.radians(5)))
            return [(3, at_index(rot, crew_transfer.radial(pu, mid, a0+turn*i/n))) for i in range(n+1)]
        for k in la:
            annulus = around(la[k0], la[k])
            if k not in frames:
                out[f'{tag}{k}'] = dict(path=head+annulus, walk=[])
                continue
            tube = [(3 if i == 0 else 4, at_index(rot, p)) for i, p in enumerate(frames[k]['points'])]
            point = lambda p, a=la[k]: at_index(rot, crew_transfer.sector_point(s, a, p))
            walks[k] = [(point((L['x'], -R, L['z']*(1-i/10))), point((L['x'], R-H, L['z']*(1-i/10)))) for i in range(11)]
            descent[k] = tube+[(5, point((L['x'], -R, L['z'])))]
            out[f'{tag}{k}'] = dict(path=head+annulus+descent[k], walk=walks[k])
        if j == s['induction']['ring'] and frames:
            # IND-001: from one induction sector's deck up its tube, round the annulus and down the next sector's tube. Reversed, a waypoint
            # takes the zone of the leg that now ends there (the one that started there).
            # Q51: Seraph's service path from its niche's sector to the workshop's ([route_fitout] seraph_service_sectors), built the same way.
            order = induction_sectors(s)
            for k1, k2 in list(zip(order, order[1:]))+[tuple(s['route_fitout']['seraph_service_sectors'])]:
                up = descent[k1]; back = [(up[i+1][0], up[i][1]) for i in reversed(range(len(up)-1))]
                out[f'{tag}{k1}-{tag}{k2}'] = dict(path=[up[-1]]+back+around(la[k1], la[k2])+descent[k2], walk=walks[k2])
            # 2.5: from the aisle centre at the landing along the centreline to each of the sector's stops in turn, upright, keyed by stop.
            st = induction_stations(s)
            for n, k in enumerate(order):
                point = lambda p, a=la[k]: at_index(rot, crew_transfer.sector_point(s, a, p)); x0, stops = L['x'], []
                for q in [q for q in s['induction']['stops'] if q['at'] == 'sector' and q['sector'] == k]:
                    x1 = st[q['key']]['aisle_x']; m = max(1, math.ceil(abs(x1-x0)/.1))
                    stops.append((q['key'], [(point((x0+(x1-x0)*i/m, -R, 0.0)), point((x0+(x1-x0)*i/m, R-H, 0.0))) for i in range(m+1)])); x0 = x1
                out[f'{tag}{k}' if n == 0 else f'{tag}{order[n-1]}-{tag}{k}']['stops'] = stops
    r = refuge_station(s); sg = 1 if s['human_entry']['refuge_panel_deg'] >= 0 else -1; n = 36
    rise = lambda d: [(2, (r['x'], 0.0, 0.0))]+[('R', crew_transfer.radial(r['x'], r['circulation_r'], r['th']+d*math.pi*i/n)) for i in range(n+1)]
    out['R'] = dict(path=entry+rise(sg), walk=[])
    aft = max(x for x in (rot['x']+v['port_u'] for rot, v, _ in map(lambda j: vestibule_station(s, j), s['human_entry']['vestibule_rotors'])) if x < r['x'])
    out['E'] = dict(path=[(2, (aft, 0.0, 0.0))]+rise(-sg), walk=[])
    return out


def route_bodies(s, step=0.1):
    """The suited body sampled along route(s), per sector: (zone, axis points) every `step` of travel, each axis point the centre of a sphere of the
    suited envelope. Floating, the body is two chords of the path, head to hip and hip to feet ((human height - envelope)/2 each), so it bends at
    the hip where the route turns (zone = the head's leg; the same chords serve the reverse traversal); on the deck it stands upright (zone 5;
    on the walks to the induction stops, zone = the stop's key)."""
    R = s['human_entry']['mannequin']['suited_envelope_diameter_m']/2; half = (s['prototype']['human_height_m']-2*R)/2; out = {}
    for k, r in route(s).items():
        zones, pts = zip(*r['path']); cum = [0.0]
        for a, b in zip(pts, pts[1:]):
            cum.append(cum[-1]+math.dist(a, b))
        def at(t):
            i = next((j for j in range(1, len(cum)) if t <= cum[j]), len(cum)-1)
            return zones[i], crew_transfer.add(pts[i-1], crew_transfer.sub(pts[i], pts[i-1]), min(max((t-cum[i-1])/(cum[i]-cum[i-1]), 0.0), 1.0))
        bodies = []
        for t in [2*half+i*step for i in range(int((cum[-1]-2*half)/step)+1)]+[cum[-1]]:
            zone, hd = at(t); hp, ft = at(t-half)[1], at(t-2*half)[1]
            bodies.append((zone, [crew_transfer.add(hd, crew_transfer.sub(hp, hd), j/4) for j in range(4)]+[crew_transfer.add(hp, crew_transfer.sub(ft, hp), j/4) for j in range(5)]))
        bodies += [(5, [crew_transfer.add(a, crew_transfer.sub(b, a), j/4) for j in range(5)]) for a, b in r['walk']]
        bodies += [(stop, [crew_transfer.add(a, crew_transfer.sub(b, a), j/4) for j in range(5)]) for stop, walk in r.get('stops', []) for a, b in walk]
        out[k] = bodies
    return out


def induction_sectors(s):
    """IND-001: the induction ring's sectors in the order of their first stop ([induction].stops)."""
    return list(dict.fromkeys(q['sector'] for q in s['induction']['stops'] if q['at'] == 'sector'))


def induction_stations(s):
    """IND-001 2.5: each sector stop's station in its sector frame, keyed by stop. `pose` names the sector_whitebox figure of the sector's
    function the stop is about; 'aisle_x' is where the stop stands on the aisle centreline, where the newcomer leaves the aisle for it: abreast
    the figure's eye or, for a block entered from a fore or aft strip, the strip's centre, within the walkable aisle (the suited radius inside
    the end allowance). The review camera ('camera') stands in the aisle at eye height, stop_camera_z_m across the centreline from the figure's
    block, and looks at the figure's eye ('look'): at the stop or, for a figure standing in the aisle (outside its block), stop_camera_back_m
    along the aisle toward the landing."""
    import habitat_interior
    import sector_whitebox
    ind, m = s['induction'], s['human_entry']['mannequin']; L = landing(s)
    lim = habitat_interior.section(s)['length_m']/2-s['interior']['end_allowance_m']-m['suited_envelope_diameter_m']/2
    clamp = lambda x: min(max(x, -lim), lim); out = {}
    for q in [q for q in ind['stops'] if q['at'] == 'sector']:
        fn = s['habitat_ring']['sector_functions'][q['sector']-1]; blocks = habitat_interior.zones(s, fn)
        fg = sector_whitebox.figures(s, blocks)[q['pose']]; b = next(b for b in blocks if b['name'] == fg['block']); eye = fg['eye']
        strip = sector_whitebox.access_strip(s, b) if sector_whitebox.face(b) in ('fore', 'aft') else None
        x = clamp((strip['min'][0]+strip['max'][0])/2 if strip else eye[0])
        cx = clamp(eye[0]+math.copysign(ind['stop_camera_back_m'], (L['x']-eye[0]) or 1.0)) if fg.get('outside') else x
        out[q['key']] = dict(sector=q['sector'], function=fn, pose=q['pose'], block=b['name'], figure=fg, aisle_x=x,
                             camera=(cx, -m['eye_height_m'], -b['side']*ind['stop_camera_z_m']), look=eye)
    return out


def induction(s):
    """IND-001 (S&E 98!A36, step 2.1): the induction route on its ring as legs in order (route keys; a leading '-' would run a leg
    backwards; since Q48 the route ends at the last sector, the newcomer's departure being Tale-owned) and its stops ([induction].stops), each with a point in the vehicle frame at
    the docked pose: 'entry' the entry chamber's centre on the port axis, 'refuge_port' the trunk axis under the refuge port's centre,
    'vestibule' the annulus at mid-depth under the spine port, 'sector' the deck on that sector's aisle centreline at the stop's station
    (induction_stations)."""
    ind = s['induction']; j = ind['ring']; tag = 'AB'[j-1]; order = induction_sectors(s)
    legs = [f'{tag}{order[0]}']+[f'{tag}{a}-{tag}{b}' for a, b in zip(order, order[1:])]
    f = ports(s)[0]; st = stations(s, f); rot, v, la = vestibule_station(s, j); ss = induction_stations(s)
    where = {'entry': world(f, (st['a_in']+st['a_out'])/2), 'refuge_port': (refuge_station(s)['x'], 0.0, 0.0),
             'vestibule': at_index(rot, crew_transfer.radial(v['port_u'], (v['r0']+v['clear'])/2, la[v['ports'][0]]))}
    stops = [dict(q, point=at_index(rot, crew_transfer.sector_point(s, la[q['sector']], (ss[q['key']]['aisle_x'], 0.0, 0.0))) if q['at'] == 'sector'
                  else where[q['at']]) for q in ind['stops']]
    return dict(ring=tag, sectors=order, legs=legs, stops=stops)


def induction_sequence(s):
    """IND-001 4.1: the induction as operating states ([induction].sequence; Q48, 15!A89). Each step is a buildable configuration holding
    stops, or a transition between its neighbours' configurations (no duration: not to scale). Every stop belongs to exactly one step, in the
    stops' order. The owner's doctrine: the first step is docked with the rings stopped, and every ring stop (the transfer drum and the
    sectors) is held by one step with the rings spinning, so no ring stops between sectors (15!H89). Returns the steps and per stop its step,
    configuration, habitat state, ring rate and the spin gravity at the stop (the sectors' deck, or mid-depth in the transfer drum,
    synchronized with its ring; 0 when stopped or stationary)."""
    import spec
    ind = s['induction']; cfg = spec.buildable_configurations(s); order = [q['key'] for q in ind['stops']]
    stops = {q['key']: q for q in induction(s)['stops']}; seq = ind['sequence']; held = []; out = {}
    for n, st in enumerate(seq):
        if 'state' in st:
            if st['state'] not in cfg:
                raise ValueError(f"induction step {st['key']}: {st['state']} is not a buildable configuration")
            held += st['stops']
        elif not (0 < n < len(seq)-1 and seq[n-1].get('state') == st['from'] and seq[n+1].get('state') == st['to']):
            raise ValueError(f"induction step {st['key']}: a transition must join the states of its neighbours")
    if held != order:
        raise ValueError(f'induction sequence holds {held}, not the stops in order {order}')
    first = s['configuration'][seq[0]['state']]['habitat'] if 'state' in seq[0] else None
    ring = {st['key'] for st in seq for k in st.get('stops', []) if stops[k]['at'] in ('vestibule', 'sector')}
    if first != 'STOPPED_LOCKED' or len(ring) != 1 or s['configuration'][next(st for st in seq if st['key'] in ring)['state']]['habitat'] != 'ROTATING':
        raise ValueError(f'induction sequence must board with the rings stopped and hold every ring stop in one spinning state (Q48, 15!A89): {ring}')
    w = habitat_ring.omega(s); j = ind['ring']; v = crew_transfer.vestibule(s, j)
    for st in seq:
        for key in st.get('stops', []):
            c = s['configuration'][st['state']]; spin = c['habitat'] == 'ROTATING'; q = stops[key]
            r = math.hypot(q['point'][1], q['point'][2]) if q['at'] == 'sector' else (v['r0']+v['clear'])/2 if q['at'] == 'vestibule' else 0.0
            out[key] = dict(step=st['key'], state=st['state'], habitat=c['habitat'], rpm=s['habitat']['rpm'] if spin else 0.0,
                            g=w*w*r/habitat_ring.G0 if spin else 0.0)
    return dict(steps=[dict(st) for st in seq], stops=out)


ZONES = {1: 'entry', 2: 'trunk', 3: 'vestibule', 4: 'tube', 5: 'landing'}


def induction_graph(s):
    """IND-001 5.1: the induction route as a graph for a runtime (rig contract `induction_route`), with semantic IDs, in vehicle-frame metres
    at the docked pose (rotors at their index angle). A runtime reads it and computes nothing.
    - rail: one camera rail through the legs in order; each waypoint has its zone, leg and distance along the rail. Floating and on the
      ladders it follows the route's passage axis (route()); walking it is the eye eye_height_m over the deck on the aisle walks, with
      the deck's up.
    - stops: per stop its place on the rail (a sector stop ends its aisle walk; any other stop is projected onto its leg), the offset from
      the rail, its operating state (induction_sequence), scenes, title and eye-level view (characters.stop_views).
    - envelope: the radius about the rail inside which a free camera stays clear (the suited envelope the route sweeps check, RT-004).
    - legs: per leg its rail span, the ladders it climbs (each crew-tube and landing-ladder span with its rungs) and the openings it passes,
      found where the rail changes zone, each with its closure status. As in route(), a waypoint's zone is that of the rail segment ending
      there, so a zone boundary, and an opening's point, is the waypoint before the first one of the new zone."""
    import characters
    ind = induction(s); r = route(s); m = s['human_entry']['mannequin']; j = s['induction']['ring']; tag = ind['ring']
    seq = induction_sequence(s); views = characters.stop_views(s); stops = {q['key']: q for q in ind['stops']}
    rungs = {k: len(next(q for q in spoke_fixtures(s, j) if q['name'] == f'Crew_Tube_{j}_{k}_Ladder_Rungs')['segments']) for k in ind['sectors']}
    landing_rungs = len(next(q for q in landing_fixtures(s) if q['name'] == 'Sector_Ladder_Rungs')['segments'])
    rs = m['suited_envelope_diameter_m']/2

    def eye(pair):
        a, b = pair; u = crew_transfer.unit(crew_transfer.sub(b, a))
        return crew_transfer.add(a, u, m['eye_height_m']-rs)
    rail, legs, at_stop = [], [], {}
    for leg in ind['legs']:
        q = r[leg.lstrip('-')]; pts = [(ZONES[z], p) for z, p in q['path']]+[('aisle', eye(w)) for w in q['walk']]; marks = {}
        up = {tuple(eye(w)): crew_transfer.unit(crew_transfer.sub(w[1], w[0])) for w in q['walk']+[w for _, walk in q.get('stops', []) for w in walk]}
        for key, walk in q.get('stops', []):
            pts += [('aisle', eye(w)) for w in walk]; marks[len(pts)-1] = key
        if leg.startswith('-'):
            # A waypoint's zone is that of the segment ending there (route()); run backwards, each segment ends at its other waypoint.
            rev = pts[::-1]; pts = [(rev[max(n-1, 0)][0], p) for n, (_, p) in enumerate(rev)]
            marks = {len(pts)-1-n: key for n, key in marks.items()}
        start = len(rail)
        for n, (zone, p) in enumerate(pts):
            p = tuple(p)
            if rail and math.dist(rail[-1]['position_m'], p) < 1e-6:
                continue
            d = rail[-1]['rail_m']+math.dist(rail[-1]['position_m'], p) if rail else 0.0
            rail.append({'zone': zone, 'leg': leg, 'position_m': p, 'rail_m': d, **({'up': tuple(up[p])} if p in up else {})})
            if n in marks:
                at_stop[marks[n]] = len(rail)-1
        legs.append({'leg': leg, 'span': (start, len(rail)-1)})
    order = [q['key'] for q in ind['stops']]; sector_stops = [k for k in order if stops[k]['at'] == 'sector']
    out_stops = []
    for k in order:
        q = stops[k]
        if k in at_stop:
            i = at_stop[k]; leg = rail[i]['leg']; d, off, pos = rail[i]['rail_m'], 0.0, rail[i]['position_m']
        else:
            leg = ind['legs'][0] if order.index(k) < order.index(sector_stops[0]) else ind['legs'][-1]
            a0, a1 = next(x['span'] for x in legs if x['leg'] == leg); best = None
            for i in range(a0, a1):
                p0, p1 = rail[i]['position_m'], rail[i+1]['position_m']; v = crew_transfer.sub(p1, p0); L2 = crew_transfer.dot(v, v)
                t = 0.0 if L2 == 0 else max(0.0, min(1.0, crew_transfer.dot(crew_transfer.sub(q['point'], p0), v)/L2)); c = crew_transfer.add(p0, v, t)
                if best is None or math.dist(c, q['point']) < best[1]:
                    best = (rail[i]['rail_m']+t*math.sqrt(L2), math.dist(c, q['point']), c)
            d, off, pos = best
        o = seq['stops'][k]; v = views[k]
        out_stops.append({'id': f'WF.STOP.IND.{k.upper()}', 'key': k, 'title': q['title'], 'at': q['at'], **({'sector': q['sector']} if 'sector' in q else {}),
                          'scenes': q['scenes'], 'leg': leg, 'rail_m': d, 'rail_offset_m': off, 'point_m': tuple(q['point']), 'rail_point_m': tuple(pos),
                          'state': {'step': f"WF.STEP.IND.{o['step'].upper()}", 'configuration': o['state'], 'habitat': o['habitat'], 'ring_rpm': o['rpm'], 'spin_g': o['g']},
                          'view': {'camera': v['name'], 'eye_m': tuple(v['at']), 'look': tuple(crew_transfer.unit(v['look'])), 'up': tuple(crew_transfer.unit(v['up'])),
                                   'horizontal_fov_deg': math.degrees(2*math.atan(18.0/v['lens'])), 'role': v['role']}})
    out_legs = []; gate = [q['name'] for q in crew_transfer.closures(s, j) if q['kind'] == 'PORT_GATE']; port = ports(s)[0]['name']
    # RT-004: per crew tube the unit vector from the passage axis toward its ladder on the run (the wall away from the spoke, angle pi from n1).
    rot_j, _, _, tube_frames = spoke_station(s, j)
    toward = {k: tuple(at_index(rot_j, tuple(-x for x in fr['n1'][RUN]), False)) for k, fr in tube_frames.items()}
    for x in legs:
        leg = x['leg']; a0, a1 = x['span']; keys = leg.lstrip('-').split('-'); ends = [int(k[1:]) for k in keys]
        if leg.startswith('-'):
            ends = ends[::-1]
        ladders, openings = [], []
        seen_vestibule = False
        for i in range(a0, a1+1):
            z = rail[i]['zone']; prev = rail[i-1]['zone'] if i > a0 else None
            if z == 'vestibule':
                seen_vestibule = True
            k = ends[-1] if seen_vestibule and z != 'vestibule' else ends[0]
            if len(ends) == 1 and not leg.startswith('-'):
                k = ends[0]
            if z in ('tube', 'landing') and (prev != z):
                ladders.append({'id': f'WF.LADDER.{tag}{k}.{z.upper()}', 'kind': 'crew-tube ladder' if z == 'tube' else 'landing ladder',
                                'rungs': rungs[k] if z == 'tube' else landing_rungs, 'rail_m': [rail[i-1]['rail_m'], rail[i]['rail_m']],
                                **({'toward_ladder': toward[k]} if z == 'tube' else {})})
            if z in ('tube', 'landing') and ladders and ladders[-1]['id'].endswith(z.upper()):
                ladders[-1]['rail_m'][1] = rail[i]['rail_m']
            pair = {prev, z}
            if prev is None or prev == z:
                continue
            if pair == {'entry', 'trunk'}:
                o = ('WF.OPENING.DOCK_PRIMARY.INNER_HATCH', 'hinged leaf, shown open (display pose)')
            elif pair == {'trunk', 'vestibule'}:
                o = (f'WF.OPENING.{tag}.SPINE_PORT', 'port gate in the spine shell (Q46), shown open; seal and drive OPEN')
            elif pair == {'vestibule', 'tube'}:
                o = (f'WF.OPENING.{tag}{k}.VESTIBULE_HATCH', 'drum door and crew-tube hatch (Q46), shown open; seals and drives OPEN')
            elif pair == {'tube', 'landing'}:
                o = (f'WF.OPENING.{tag}{k}.SECTOR_HATCH', 'sliding leaf, shown open; seal, drive and latching OPEN')
            else:
                continue
            # RT-004: the closures a runtime opens and closes here, and which sequence rule they follow (`kind`).
            kind, names = {frozenset({'entry', 'trunk'}): ('AIRLOCK_INNER', [f'{port}_Inner_Hatch']), frozenset({'trunk', 'vestibule'}): ('PORT_GATE', gate),
                           frozenset({'vestibule', 'tube'}): ('DRUM_DOOR_TUBE_HATCH', [f'Crew_Vestibule_{j}_Door_{k}', f'Crew_Tube_{j}_{k}_Hatch']),
                           frozenset({'tube', 'landing'}): ('SECTOR_LEAF', [f'Sector_Hatch_Leaf_{j}_{k}'])}[frozenset(pair)]
            openings.append({'id': o[0], 'closure': o[1], 'rail_m': rail[i-1]['rail_m'], 'point_m': rail[i-1]['position_m'], 'kind': kind, 'closures': names})
        if rail[a0]['zone'] == 'entry' or rail[a1]['zone'] == 'entry':
            i = a0 if rail[a0]['zone'] == 'entry' else a1
            openings.insert(0 if i == a0 else len(openings), {'id': 'WF.OPENING.DOCK_PRIMARY.OUTER_HATCH', 'closure': 'hinged leaf, shown open (display pose)',
                                                              'rail_m': rail[i]['rail_m'], 'point_m': rail[i]['position_m'], 'kind': 'AIRLOCK_OUTER',
                                                              'closures': [f'{port}_Outer_Hatch']})
        out_legs.append({'id': f"WF.LEG.IND.{leg.replace('-', '_').strip('_') if not leg.startswith('-') else 'RETURN_'+leg[1:]}", 'route_key': leg,
                         'from': ('DOCK' if leg == ind['legs'][0] else f'{tag}{ends[0]}'), 'to': ('DOCK' if leg.startswith('-') else f'{tag}{ends[-1]}'),
                         'rail_m': [rail[max(a0-1, 0)]['rail_m'], rail[a1]['rail_m']], 'ladders': ladders, 'openings': openings})
    # Plain JSON types (lists, not tuples), so the rig file compares equal to its contract (sim_rig.check).
    return json.loads(json.dumps({'id': f'WF.ROUTE.INDUCTION.{tag}', 'generation': 'IND-001 5.1', 'geometry_status': 'PROTOTYPE', 'sequence_status': 'BASELINE physical sequence (Q48, 15!A89); stop staging PROTOTYPE',
            'coordinates': 'vehicle frame (+X bow, +Z dorsal), metres, docked pose with the rotors at their index angle; a runtime converts (x,y,z) -> (x,z,-y) once',
            'sources': [s['induction']['sequence_sources'], 'S&E 15_MODEL_INTERFACES!A86:I86', 'Tale 12_WAYFARER_CREW'],
            'zones': {'entry': 'HUM-001 zone 1, entry chamber', 'trunk': 'zone 2, stationary trunk', 'vestibule': 'zone 3, rotary vestibule',
                      'tube': 'zone 4, crew tube', 'landing': 'zone 5, sector landing', 'aisle': 'sector aisle (zones 6-8)'},
            'limits': 'Camera rail and route envelope only: no body collision or pressure cycling; spin gravity and the Coriolis push are shown, not '
                      'simulated. The airlock hatches, the Q46 closures (port gate, drum doors, tube hatches) and the sector leaves open and close in '
                      'a display sequence (`kind`), not a procedure or an interlock design. Characters are static proxies of the characters asset, '
                      'shown per scene; where the MPFB induction pair is exported, its posed bodies replace the S004A and S004B proxies (CHAR-001). The rail is given at the index pose; '
                      'each zone moves with its frame (frames), so in COAST the transfer drum, synchronized with ring A, carries the crew between '
                      'the same poses. The departure is Tale-owned; identities are open (Q49).',
            # RT-004: which frame each zone moves with, and the mechanism IDs (export manifest node `frame`) of ring A and its drum.
            # RT-004: what the runtime's body pace and its spin-gravity and Coriolis readout use; ladder_push is the Python result it is checked against.
            'body': {'review_speed_m_s': m['climb_review_speed_m_s'], 'rung_pitch_m': s['human_entry']['spoke_rung_pitch_m'], 'standard_gravity_m_s2': habitat_ring.G0,
                     'climber_offset_m': m['spoke_body_offset_m'],
                     'ladder_push': {k: v for k, v in ladder_push(s, j).items() if k in ('ladder_wall', 'pulled_off_when', 'coriolis_g_per_m_s', 'lean_toward_ladder_g',
                                                                                      'neutral_speed_m_s', 'review_speed_m_s', 'body_off_radial_m')},
                     'basis': 'Review pace and rung grid (PROTOTYPE); on a crew-tube ladder the climber\'s body stands climber_offset_m from the rail '
                              '(the passage axis) toward the ladder (toward_ladder). A runtime shows spin gravity '
                              'omega^2 r and the Coriolis push -2 omega x v of the moving camera in the ring frame, a presentation of the sourced spin, '
                              'not a body simulation.'},
            'frames': {'zones': {'entry': 'STATIONARY', 'trunk': 'STATIONARY', 'vestibule': 'DRUM', 'tube': 'RING', 'landing': 'RING', 'aisle': 'RING'},
                       'RING': f'WF.ROTOR.{j}', 'DRUM': f'WF.CREW.{j}.DRUM',
                       'basis': 'The trunk is stationary, the drum is despun at the index (Q46) or synchronized with its ring, and the tubes, '
                                'landings and sectors turn with the ring.'},
            # RT-004: the free camera's collision is the suited envelope swept along the rail, the volume the HUM-001 route sweeps prove clear of
            # every fixture and wall (route_bodies; check() margins), so it passes every opening the route passes and seals none.
            'envelope': {'radius_m': rs, 'status': 'PROTOTYPE',
                         'basis': 'suited envelope radius (human_entry.mannequin.suited_envelope_diameter_m / 2) about the rail: floating and on the '
                                  'ladders the rail is the suited body axis, which the route checks keep clear along every leg; on the aisles it is the eye, '
                                  'inside the walking body\'s head sphere, whose envelope reaches eye height + radius, below the sector headroom'},
            'sequence': [{'id': f"WF.STEP.IND.{st['key'].upper()}", 'title': st['title'], **({'configuration': st['state'], 'stops': [f'WF.STOP.IND.{k.upper()}' for k in st['stops']]}
                          if 'state' in st else {'transition': [st['from'], st['to']]})} for st in seq['steps']],
            # RT-006 (v25; v26 suited -> suited_access, SERV-STRIPS-2026-10-10): the clear volumes of the induction ring's sectors, for a free camera or a walking body off the rail.
            'rooms': {'boxes': room_volumes(s), 'frame': 'RING', 'eye_height_m': m['eye_height_m'],
                      'basis': 'sector_whitebox.clear_volumes: aisle, landing well, access and couch strips, berth spaces and Seraph\'s niche, '
                               'deck to overhead, clear of the whitebox blocks by construction (not swept); suited_access = the 0.70 m suited envelope fits; false is '
                               'shirt-sleeve-only maintenance access, not suited egress (15!A119). '
                               'A runtime keeps the eye inside their union (with the body: at eye height over the deck); PROTOTYPE.'},
            'rail': rail, 'stops': out_stops, 'legs': out_legs}))


def room_volumes(s, j=None):
    """RT-006: the clear volumes (sector_whitebox.clear_volumes) of every sector of ring j (default the induction ring) as oriented boxes in
    the vehicle frame at the index pose: centre, unit axes (sector X, Y, Z) and half sizes, the deck point under the centre and the up
    direction (toward the spin axis), kind and whether a suited body fits. On the induction ring every sector stop's eye and every aisle-walk
    point must lie in one of its sector's boxes. Ring B carries the same functions (habitat.layout.ring_functions MIRRORED) in the same
    sector frames (habitat_ring.sectors), so its boxes are the same clear volumes on its own rotor (J01)."""
    import sector_whitebox
    induction = j is None or j == s['induction']['ring']
    j = j or s['induction']['ring']; rot, _, la = vestibule_station(s, j); tag = 'AB'[j-1]; fns = s['habitat']['layout']['functions']; out = []
    _, X, Y, Z = crew_transfer.sector_axes(s, 0.0)
    for k in la:
        fn = fns[k-1]; pt = lambda p, k=k: at_index(rot, crew_transfer.sector_point(s, la[k], p))
        c0, Xk, Yk, Zk = crew_transfer.sector_axes(s, la[k])
        axes = [tuple(at_index(rot, v, False)) for v in (Xk, Yk, Zk)]
        for q in sector_whitebox.clear_volumes(s, fn):
            c = tuple((q['min'][i]+q['max'][i])/2 for i in range(3))
            out.append({'id': f"WF.ROOM.{tag}{k}.{q['name'].upper()}", 'sector': k, 'function': fn, 'kind': q['kind'], 'suited_access': q['suited_access'],
                        'centre_m': tuple(pt(c)), 'axes': axes, 'half_m': tuple((q['max'][i]-q['min'][i])/2 for i in range(3)),
                        'deck_m': tuple(pt((c[0], 0.0, c[2]))), 'up': tuple(-x for x in axes[1])})
    def inside(p, b):
        d = [p[i]-b['centre_m'][i] for i in range(3)]
        return all(abs(sum(d[i]*b['axes'][n][i] for i in range(3))) <= b['half_m'][n]+1e-6 for n in range(3))
    if not induction:
        return out
    r = route(s); m = s['human_entry']['mannequin']; rs = m['suited_envelope_diameter_m']/2
    for key, q in r.items():
        for stop, walk in q.get('stops', []):
            for a, b in walk:
                eye = crew_transfer.add(a, crew_transfer.unit(crew_transfer.sub(b, a)), m['eye_height_m']-rs)
                if not any(inside(eye, x) for x in out):
                    raise ValueError(f'RT-006: the {stop} walk leaves the exported clear volumes at {eye}')
    return out


def induction_figures(s):
    """IND-001 2.5: the sector_whitebox review figures (non-canon scale guides) of each induction sector's function, as rods in the vehicle
    frame at the docked pose, named Human_Ind_<ring><sector>_<pose>_<part>."""
    import habitat_interior
    import sector_whitebox
    j = s['induction']['ring']; rot, _, la = vestibule_station(s, j); out = []
    for k in induction_sectors(s):
        fn = s['habitat_ring']['sector_functions'][k-1]; point = lambda p, a=la[k]: at_index(rot, crew_transfer.sector_point(s, a, p))
        for pose, fg in sector_whitebox.figures(s, habitat_interior.zones(s, fn)).items():
            out += [(f"Human_Ind_{'AB'[j-1]}{k}_{pose.title()}_{n}", [point(p) for p in pts], r) for n, pts, r in fg['rods']]
    return out


def box_frame(f, q):
    """Centre and unit axes (along u, tangential, radial) of a box fixture; trunk boxes carry them in the vehicle frame, vestibule boxes in the
    rotor frame."""
    if 'world_centre' in q:
        return q['world_centre'], q['axes']
    a, rho, phi = q['centre']; u, _ = axes(f)
    return world(f, a, rho, phi), (u, vec(f, 0.0, -math.sin(phi), math.cos(phi)), vec(f, 0.0, math.cos(phi), math.sin(phi)))


def box_corners(f, q):
    c, ax = box_frame(f, q)
    return [tuple(c[i]+sum(sg*q['size'][k]/2*ax[k][i] for k, sg in enumerate(signs)) for i in range(3))
            for signs in [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]]


def segments(q):
    """Axis segments of a rod (a polyline) or of a 'rods' fixture (a segment list)."""
    return list(zip(q['points'], q['points'][1:])) if q['shape'] == 'rod' else q['segments']


def fixture_distance(f, q, v):
    """Distance from point v to a fixture's solid."""
    if q['shape'] in ('rod', 'rods'):
        return min(crew_transfer.seg_dist(v, a, b) for a, b in segments(q))-q['radius']
    if q['shape'] == 'box':
        c, ax = box_frame(f, q); d = [v[i]-c[i] for i in range(3)]
        return math.sqrt(sum(max(abs(sum(d[i]*ax[k][i] for i in range(3)))-q['size'][k]/2, 0.0)**2 for k in range(3)))
    if q['shape'] == 'tube':
        e = crew_transfer.sub(q['b'], q['a']); L = math.sqrt(crew_transfer.dot(e, e)); e = tuple(x/L for x in e); d = crew_transfer.sub(v, q['a'])
        t = crew_transfer.dot(d, e); rho = math.sqrt(max(crew_transfer.dot(d, d)-t*t, 0.0))
        return math.hypot(max(-t, 0.0, t-L), max(q['r0']-rho, 0.0, rho-q['r1']))
    a, rho, _ = local(f, v); (a0, r0), (_, r1), (a1, _) = q['profile'][0], q['profile'][1], q['profile'][2]
    return math.hypot(max(a0-a, 0.0, a-a1), max(r0-rho, 0.0, rho-r1))


def fixture_points(f, q, n=16):
    """Surface samples of a fixture, for the passage screen."""
    if q['shape'] in ('rod', 'rods'):
        out = []
        for a, b in segments(q):
            ax = crew_transfer.sub(b, a); L = math.sqrt(crew_transfer.dot(ax, ax)); ax = tuple(x/L for x in ax)
            # Two unit directions across the rod axis.
            ref = (1.0, 0.0, 0.0) if abs(ax[0]) < .9 else (0.0, 1.0, 0.0)
            e = crew_transfer.sub(ref, tuple(x*crew_transfer.dot(ref, ax) for x in ax)); e = tuple(x/math.sqrt(crew_transfer.dot(e, e)) for x in e)
            g = (ax[1]*e[2]-ax[2]*e[1], ax[2]*e[0]-ax[0]*e[2], ax[0]*e[1]-ax[1]*e[0])
            out += [tuple(a[i]+t*(b[i]-a[i])+q['radius']*(math.cos(2*math.pi*k/n)*e[i]+math.sin(2*math.pi*k/n)*g[i]) for i in range(3))
                    for t in (0.0, .5, 1.0) for k in range(n)]
        return out
    if q['shape'] == 'box':
        return box_corners(f, q)
    if q['shape'] == 'tube':
        e = crew_transfer.sub(q['b'], q['a']); L = math.sqrt(crew_transfer.dot(e, e)); e = tuple(x/L for x in e)
        ref = (1.0, 0.0, 0.0) if abs(e[0]) < .9 else (0.0, 1.0, 0.0)
        p1 = crew_transfer.sub(ref, tuple(x*crew_transfer.dot(ref, e) for x in e)); p1 = tuple(x/math.sqrt(crew_transfer.dot(p1, p1)) for x in p1)
        p2 = (e[1]*p1[2]-e[2]*p1[1], e[2]*p1[0]-e[0]*p1[2], e[0]*p1[1]-e[1]*p1[0])
        return [tuple(end[i]+r*(math.cos(2*math.pi*k/n)*p1[i]+math.sin(2*math.pi*k/n)*p2[i]) for i in range(3))
                for end in (q['a'], q['b']) for r in (q['r0'], q['r1']) for k in range(n)]
    return [world(f, a, rho, 2*math.pi*k/n) for a, rho in q['profile'] for k in range(n)]


def mannequin(s, f):
    """Generic 1.8 m figure (non-canon scale guide) floating along the passage axis, head inboard, facing the leak-check panel (toward
    panel_deg): feet feet_inset_m inside the outer bulkhead, offset toward the +w handrail; one hand on that rail, the other reaching toward
    the panel. Returns rods (name, points, radius), the eye, the look direction to the panel and the arm reaches."""
    h, m = s['human_entry'], s['human_entry']['mannequin']; st = stations(s, f); H = s['prototype']['human_height_m']
    a_f = st['a_out']-m['feet_inset_m']; off = m['rail_side_offset_m']
    ph = math.radians(h['panel_deg']); fy = (math.cos(ph), math.sin(ph)); fx = (math.sin(ph), -math.cos(ph))   # face and across, in (X, w)
    def at(x, y, z):                 # x across the body, y toward the face (the panel), z from the feet toward the head (-u)
        base, d = world(f, a_f-z), vec(f, 0.0, x*fx[0]+y*fy[0], off+x*fx[1]+y*fy[1])
        return tuple(base[i]+d[i] for i in range(3))
    rr = st['chamber_r']-h['handrail_standoff_m']
    grip = rr-h['handrail_radius_m']-off           # the hand closes on the rail's inboard face (the rail is at +w, X = 0)
    rods = [('Human_Entry_Torso', [at(0, 0, .38*H), at(0, 0, .78*H)], .13),
            ('Human_Entry_Head', [at(0, 0, H-.20), at(0, 0, H-.11)], .11),
            ('Human_Entry_Arm_Rail', [at(0, 0, .75*H), at(grip*fx[1], grip*fy[1], .75*H)], .055),
            ('Human_Entry_Arm_Reach', [at(0, 0, .75*H), at(-.10, .45, .75*H+.20)], .055)]
    for sign in (-1, 1):
        rods.append((f'Human_Entry_Leg_{sign}', [at(sign*.13, 0, .07), at(0, 0, .40*H)], .07))
    assert math.isclose(h['handrail_deg'][0], 90.0), 'The mannequin holds the first (+w) handrail'
    eye = at(0, .08, m['eye_height_m'])
    panel = next(q for q in fixtures(s, f) if q['name'].endswith('_Entry_Panel')); centre, _ = box_frame(f, panel)
    look = tuple(centre[i]-eye[i] for i in range(3))
    reach = {name: math.dist(*pts) for name, pts, _ in rods if 'Arm' in name}
    return dict(rods=rods, eye=eye, look=look, up=vec(f, -1.0), feet_a=a_f, head_a=a_f-H, reach=reach)


def trunk_mannequin(s, f):
    """Zone 2 figure (non-canon scale guide) floating head-first (-X) along the trunk just aft of port f's junction, centred
    trunk_axis_offset_m toward the last trunk handrail: one hand on that rail, the other reaching ahead. Returns rods, the eye, the look
    direction (aft along the trunk), feet and head stations and the arm reaches."""
    h, m = s['human_entry'], s['human_entry']['mannequin']; H = s['prototype']['human_height_m']; tr = s['crew_transfer']['trunk_clear_radius_m']
    th = math.radians(h['trunk_handrail_deg'][-1]); rad = (math.cos(th), math.sin(th)); tan = (-math.sin(th), math.cos(th))
    x_f = f['x']-s['prototype']['dock_clear_radius_m']-m['trunk_feet_gap_m']; off = m['trunk_axis_offset_m']
    def at(x, y, z):                 # x across the body toward the rail, y toward the face (tangential), z from the feet toward the head (-X)
        return (x_f-z, (off+x)*rad[0]+y*tan[0], (off+x)*rad[1]+y*tan[1])
    grip = tr-h['handrail_standoff_m']-h['handrail_radius_m']-off
    rods = [('Human_Trunk_Torso', [at(0, 0, .38*H), at(0, 0, .78*H)], .13),
            ('Human_Trunk_Head', [at(0, 0, H-.20), at(0, 0, H-.11)], .11),
            ('Human_Trunk_Arm_Rail', [at(0, 0, .75*H), at(grip, 0, .75*H)], .055),
            ('Human_Trunk_Arm_Reach', [at(0, 0, .75*H), at(-.10, .10, .75*H+.45)], .055)]
    for sign in (-1, 1):
        rods.append((f'Human_Trunk_Leg_{sign}', [at(sign*.13, 0, .07), at(0, 0, .40*H)], .07))
    reach = {name: math.dist(*pts) for name, pts, _ in rods if 'Arm' in name}
    return dict(rods=rods, eye=at(0, .08, m['eye_height_m']), look=(-1.0, 0.0, 0.0), up=vec(f, 1.0), feet_x=x_f, head_x=x_f-H, reach=reach,
                grip=at(grip, 0, .75*H))


def trunk_climber(s):
    """Thrust-review figure (non-canon scale guide) on the trunk ladder with aft down, head forward, climbing to the refuge port: the soles on the
    rung that brings its eye nearest the port's centre, facing the ladder, the body spoke_body_offset_m off the trunk axis toward it, both hands on
    the stiles above the shoulder, clipped to the fall-arrest rail (a sliding arrester at chest height and a short link to the chest ring), as on
    the tube ladders. Its eye looks across at the refuge port beside it, whose rim is in reach before it climbs on to the sill. Vehicle frame."""
    m = s['human_entry']['mannequin']; H = s['prototype']['human_height_m']; L = trunk_ladder(s); ref = refuge_station(s); r = s['human_entry']['handrail_radius_m']
    x_r = min(L['rungs'], key=lambda x: abs(x+r+m['eye_height_m']-ref['x'])); x_f = x_r+r; y0 = m['spoke_body_offset_m']; th = L['th']
    def at(x, y, z):                 # x across the body (tangential), y toward the face (the ladder), z from the feet toward the head (+X)
        return (x_f+z, (y0+y)*math.cos(th)-x*math.sin(th), (y0+y)*math.sin(th)+x*math.cos(th))
    shoulder = at(0, 0, .75*H); grips = [crew_transfer.radial(x_f+.87*H, L['rl'], a) for a in L['stiles']]
    toe = L['rl']*math.cos(L['phi'])-y0-.07     # each foot one foot-radius short of the rung axis, its sole on the rung
    rods = [('Human_Trunk_Climber_Torso', [at(0, 0, .38*H), at(0, 0, .78*H)], .13),
            ('Human_Trunk_Climber_Head', [at(0, 0, H-.20), at(0, 0, H-.11)], .11),
            ('Human_Trunk_Climber_Arm_1', [shoulder, grips[0]], .055),
            ('Human_Trunk_Climber_Arm_2', [shoulder, grips[1]], .055)]
    for sign in (-1, 1):
        rods.append((f'Human_Trunk_Climber_Leg_{sign}', [at(sign*.13, toe, .07), at(0, 0, .40*H)], .07))
    tc = x_f+.72*H; sleeve = L['rail_rr']+.015
    rods += [('Human_Trunk_Climber_Arrester', [crew_transfer.radial(tc+e, L['rail_r'], th) for e in (-.06, .06)], sleeve),
             ('Human_Trunk_Climber_Arrester_Link', [at(0, .13, .72*H), crew_transfer.radial(tc, L['rail_r']-sleeve, th)], .012)]
    eye = at(0, .08, m['eye_height_m']); mouth = crew_transfer.radial(ref['x'], s['crew_transfer']['trunk_clear_radius_m'], ref['th'])
    reach = {name: math.dist(*pts) for name, pts, _ in rods if 'Arm' in name}
    return dict(rods=rods, eye=eye, look=crew_transfer.sub(mouth, eye), up=(1.0, 0.0, 0.0), feet_x=x_f, rung_x=x_r, head_x=x_f+H, grips=grips,
                shoulder=shoulder, reach=reach)


def elbow_climber(s):
    """Q47 figure (non-canon scale guide) on the floor ladder of the steepest leg of ring A's spine-port-sector crew tube with aft down (rings
    stopped at the index): the soles on its middle rung, facing up the ladder, the body leaning thrust_climb_lean_deg from the vertical toward
    it, both hands on the floor ladder's stiles at the points nearest the shoulder, clipped to the floor ladder's fall-arrest rail (an arrester on the
    rail at its nearest point to the chest ring, and a link). Its eye looks up the leg to where the floor ladder meets the run. Rotor-local ('local') and in the vehicle frame at the
    index ('rods', eye, look, up)."""
    m = s['human_entry']['mannequin']; H = s['prototype']['human_height_m']; r = s['human_entry']['handrail_radius_m']; ct = crew_transfer
    rot, v, la, frames = spoke_station(s); k = v['ports'][0]; fr = frames[k]; rl, _ = ladder(s); fl = max(floor_ladders(s, fr), key=lambda q: q['slope_deg'])
    i, d = fl['leg'], fr['d'][fl['leg']]; X = (1.0, 0.0, 0.0); up = 1.0 if d[0] > 0 else -1.0
    e = ct.unit(ct.sub(tuple(up*x for x in d), (abs(d[0]), 0.0, 0.0))); lat = ct.cross(X, e); lean = math.radians(m['thrust_climb_lean_deg'])
    b = ct.add(tuple(x*math.cos(lean) for x in X), e, math.sin(lean)); fwd = ct.add(tuple(x*math.cos(lean) for x in e), X, -math.sin(lean))
    t = fl['rungs'][len(fl['rungs'])//2]; c = tuple((p+q)/2 for p, q in zip(*(ct.tube_point(fr, i, rl, a, t) for a in fl['stiles'])))
    base = ct.add(ct.add(c, X, r), e, -.10)        # the ball of each foot on the rung, the body's axis behind it
    def at(x, y, z):                 # x across the body, y toward the face (the ladder), z from the soles toward the head
        return ct.add(ct.add(ct.add(base, b, z), lat, x), fwd, y)
    n = 'Human_Elbow_Climber'; shoulder = at(0, 0, .75*H)
    def nearest(p0, p1, q):
        u = ct.sub(p1, p0); w = min(max(ct.dot(ct.sub(q, p0), u)/ct.dot(u, u), 0.0), 1.0)
        return ct.add(p0, u, w)
    grips = [nearest(ct.tube_point(fr, i, rl, a, fl['t'][0]), ct.tube_point(fr, i, rl, a, fl['t'][1]), shoulder) for a in fl['stiles']]
    grips = [ct.add(g, ct.unit(ct.sub(shoulder, g)), r) for g in grips]      # the hand on the stile's surface
    rods = [(f'{n}_Torso', [at(0, 0, .38*H), at(0, 0, .78*H)], .13), (f'{n}_Head', [at(0, 0, H-.20), at(0, 0, H-.11)], .11),
            (f'{n}_Arm_1', [shoulder, grips[0]], .055), (f'{n}_Arm_2', [shoulder, grips[1]], .055)]
    for sign in (-1, 1):
        rods.append((f'{n}_Leg_{sign}', [at(sign*.13, .07, .07), at(0, 0, .40*H)], .07))
    ra, rr = arrest_rail(s); chest = at(0, .13, .72*H); sleeve = rr+.015
    rail = [ct.tube_point(fr, i, ra, fl['psi'], x) for x in fl['t']]; g = nearest(*rail, chest)      # the floor ladder's own rail
    rods += [(f'{n}_Arrester', [ct.add(g, d, x) for x in (-.06, .06)], sleeve), (f'{n}_Arrester_Link', [chest, ct.add(g, ct.unit(ct.sub(chest, g)), sleeve)], .012)]
    eye = at(0, .08, m['eye_height_m']); top = ct.tube_point(fr, i+1, .3, fl['psi'], None)       # the eye looks at the top of the floor ladder
    look = ct.unit(ct.sub(top, eye)); eye_up = ct.unit(ct.sub(X, tuple(x*ct.dot(X, look) for x in look)))
    reach = {name: math.dist(*pts) for name, pts, _ in rods if 'Arm' in name}
    return dict(local=rods, rods=[(q, [at_index(rot, p) for p in pts], rad) for q, pts, rad in rods], eye=at_index(rot, eye), look=at_index(rot, look, False),
                up=at_index(rot, eye_up, False), local_eye=eye, grips=grips, sector=k, leg=i, rung_t=t, base=base, frame=fr, reach=reach,
                link_m=math.dist(*rods[-1][1]))


def thrust_stepper(s):
    """Q47 figure (non-canon scale guide) on the step below the ring-A spine-port-sector hatch with aft down: the soles on the step ladder's lower
    rung, facing the overhead (a side wall), the body upright spoke_body_offset_m off the rungs, both hands on the landing ladder's stiles where
    they cross the hatch opening at chest height; its next move is to the top rung and, leaning in, onto the sill. Sector frame ('local') and vehicle frame at the index ('rods', eye, look, up)."""
    m = s['human_entry']['mannequin']; H = s['prototype']['human_height_m']; r = s['human_entry']['handrail_radius_m']; S = thrust_step(s); L = landing(s)
    rot, k, point, vector = sector_frame(s); y0 = S['y']+m['spoke_body_offset_m']; xf = S['rungs'][0]+r
    def at(x, y, z):                 # x across the body (+Z), y toward the face (the overhead, -Y), z up from the soles (+X)
        return (xf+z, y0-y, S['z']+x)
    n = 'Human_Thrust_Step'; shoulder = at(0, 0, .75*H)
    grips = [(xs, shoulder[1], L['stile_z']-L['side']*r) for xs in L['stile_x']]
    rods = [(f'{n}_Torso', [at(0, 0, .38*H), at(0, 0, .78*H)], .13), (f'{n}_Head', [at(0, 0, H-.20), at(0, 0, H-.11)], .11),
            (f'{n}_Arm_1', [shoulder, grips[0]], .055), (f'{n}_Arm_2', [shoulder, grips[1]], .055)]
    for sign in (-1, 1):
        rods.append((f'{n}_Leg_{sign}', [at(sign*.13, m['spoke_body_offset_m']-.07, .07), at(0, 0, .40*H)], .07))
    eye = at(0, .08, m['eye_height_m']); look = crew_transfer.unit(crew_transfer.sub((L['x'], L['tip_y']-2.0, L['z']), eye))
    reach = {name: math.dist(*pts) for name, pts, _ in rods if 'Arm' in name}
    return dict(local=rods, rods=[(q, [point(p) for p in pts], rad) for q, pts, rad in rods], eye=point(eye), look=vector(look), up=vector((1.0, 0.0, 0.0)),
                local_eye=eye, grips=grips, sector=k, feet_x=xf, reach=reach)


def vestibule_mannequin(s, j=None):
    """Zone 3 figure (non-canon scale guide) floating in rotor j's vestibule chamber just past the spine port, along a chord centred at
    vestibule_body_radius_m: facing the outer wall, the shoulder under the handrail beside the port and the head toward the transfer panel;
    one hand on that rail, the other reaching toward the panel. Its eye looks around the annulus toward the next sector's hatch frame (the panel
    is too close for a useful view). Rods and points are rotor-local ('local') and in the vehicle frame at the index pose ('rods', eye, look, up)."""
    m = s['human_entry']['mannequin']; H = s['prototype']['human_height_m']; rot, v, la = vestibule_station(s, j); fx = vestibule_fixtures(s, j)
    n = f"Human_Vestibule{ring_tag(s, rot['index'])}"
    rail = next(q for q in fx if q['name'].endswith(f"_Handrail_{v['ports'][0]}")); panel = next(q for q in fx if q['name'].endswith('_Transfer_Panel'))
    th_r = math.atan2(rail['points'][0][2], rail['points'][0][1]); Rc = m['vestibule_body_radius_m']; th = th_r-math.atan2(.75*H-H/2, Rc)
    C = crew_transfer.radial((v['cu0']+v['cu1'])/2, Rc, th); _, t, y = axes_at(th)
    def at(x, yy, z):                # x across the body (+X), yy toward the face (outward), z from the feet toward the head (+t)
        return (C[0]+x, C[1]+yy*y[1]+(z-H/2)*t[1], C[2]+yy*y[2]+(z-H/2)*t[2])
    # The hand closes on the rail's inboard face, straight out from the shoulder.
    shoulder = at(0, 0, .75*H); grip = crew_transfer.radial(shoulder[0], v['clear']-s['human_entry']['handrail_standoff_m']-rail['radius'], th_r)
    d = crew_transfer.sub(panel['world_centre'], shoulder); d = tuple(x/math.sqrt(crew_transfer.dot(d, d)) for x in d)
    local_rods = [(f'{n}_Torso', [at(0, 0, .38*H), at(0, 0, .78*H)], .13),
                  (f'{n}_Head', [at(0, 0, H-.20), at(0, 0, H-.11)], .11),
                  (f'{n}_Arm_Rail', [shoulder, grip], .055),
                  (f'{n}_Arm_Reach', [shoulder, crew_transfer.add(shoulder, d, .50)], .055)]
    for sign in (-1, 1):
        local_rods.append((f'{n}_Leg_{sign}', [at(sign*.13, 0, .07), at(0, 0, .40*H)], .07))
    eye = at(0, .08, m['eye_height_m']); nxt = next(q for q in fx if q['name'].endswith(f"_Hatch_Frame_{v['ports'][0] % len(la)+1}"))
    look = crew_transfer.sub(crew_transfer.add(nxt['a'], crew_transfer.sub(nxt['b'], nxt['a']), .5), eye)
    reach = {name: math.dist(*pts) for name, pts, _ in local_rods if 'Arm' in name}
    return dict(local=local_rods, rods=[(n, [at_index(rot, q) for q in pts], r) for n, pts, r in local_rods], eye=at_index(rot, eye),
                look=at_index(rot, look, False), up=at_index(rot, y, False), local_eye=eye, grip=grip, rail=rail['name'], reach=reach)


def cameras(s, f):
    """First-person cameras (non-canon guides): entering at the port face, at the zone-1 mannequin's eye, coming through the open inner
    hatch into the trunk node, at the zone-2 mannequin's eye looking aft along the trunk, below the ring-A spine port looking up into the
    vestibule, at the zone-3 mannequin's eye looking around the annulus, at the top of the sector-1 spoke's run looking down the shaft past the
    climbing zone-4 mannequin, at that mannequin's eye looking up the ladder to the elbows, at the zone-5 mannequin's eye at the foot of the sector-1
    landing ladder looking up through the open hatch into the tube, from the sector aisle looking at the landing, the two vestibule views again
    at ring B, in the tube of ring B's spine-port sector at the first elbow looking down the collar at the bulkhead and its neck (the ring cameras assume the
    rotors at their index angle), and on the refuge leg in the trunk below the refuge port looking up into the refuge, at the refuge mannequin's
    eye looking round the annulus, and on the trunk axis aft of the refuge port looking forward at it, as crew from the rings arrive. Thrust
    review (aft down): standing on the trunk floor looking up the shaft, and at the trunk climber's eye looking across at the refuge port; Q47:
    at a tube's first elbow looking up at the elbow climber, and from a sector's aisle at the figure on the step below the hatch.
    IND-001 2.5: standing in the aisle at each induction sector stop, looking at its figure (CAM_IND_<STOP>)."""
    m = s['human_entry']['mannequin']; st = stations(s, f); u, _ = axes(f); inboard = tuple(-x for x in u); man = mannequin(s, f); crew = trunk_mannequin(s, f)
    node_eye = world(f, st['bottom']-m['node_camera_inset_m']); sp = spoke_mannequin(s); fr = spoke_station(s)[3][sp['sector']]
    top = crew_transfer.tube_point(fr, RUN, .20, 0.0, m['spoke_camera_inset_m']); d, n1 = fr['d'][RUN], tuple(-x for x in fr['n1'][RUN])
    lm = landing_mannequin(s); aisle = landing_aisle_view(s)
    def vestibule_views(j):
        rot, v, la = vestibule_station(s, j); th = rot['phase']+la[v['ports'][0]]; off = m['vestibule_camera_offset_m']; ves = vestibule_mannequin(s, j)
        tag, ring = ring_tag(s, j), 'AB'[j-1]
        return [dict(name=f'CAM_HUM_VESTIBULE{tag}_PORT', at=(rot['x']+v['port_u'], -off*math.cos(th), -off*math.sin(th)), look=(0.0, math.cos(th), math.sin(th)),
                     up=(1.0, 0.0, 0.0), lens=m['camera_lens_mm'], clip_start=.05,
                     role=f'eye of crew in the trunk below the ring-{ring} spine port, looking up through the port into the rotary vestibule'),
                dict(name=f'CAM_HUM_VESTIBULE{tag}_EYE', at=ves['eye'], look=ves['look'], up=ves['up'], lens=m['camera_lens_mm'],
                     clip_start=.2, role=f"zone-3 mannequin's eye at the transfer panel, looking around the ring-{ring} vestibule annulus to the next sector hatch")]
    def bulkhead_view(j):
        rot, v, la, frames = spoke_station(s, j); fr = frames[v['ports'][0]]; at = fr['points'][1]; down = tuple(-x for x in fr['d'][0])
        return dict(name=f'CAM_HUM_SPOKE{ring_tag(s, j)}_BULKHEAD', at=at_index(rot, at), look=at_index(rot, down, False),
                    up=at_index(rot, tuple(-x for x in fr['n1'][0]), False), lens=m['camera_lens_mm'], clip_start=.05,
                    role=f"eye of crew at the first elbow of ring {'AB'[j-1]}'s sector-{v['ports'][0]} tube, looking down the collar through the bulkhead's neck to the spine port")
    def stop_views():
        # IND-001 2.5: one eye-level review camera per induction sector stop (induction_stations).
        j = s['induction']['ring']; rot, _, la = vestibule_station(s, j); out = []
        for key, q in induction_stations(s).items():
            a = la[q['sector']]; _, X, Y, Z = crew_transfer.sector_axes(s, a)
            vector = lambda d: at_index(rot, tuple(X[i]*d[0]+Y[i]*d[1]+Z[i]*d[2] for i in range(3)), False)
            out.append(dict(name=f'CAM_IND_{key.upper()}', at=at_index(rot, crew_transfer.sector_point(s, a, q['camera'])),
                            look=vector(crew_transfer.unit(crew_transfer.sub(q['look'], q['camera']))), up=vector((0.0, -1.0, 0.0)),
                            lens=m['camera_lens_mm'], clip_start=.05,
                            role=f"eye of crew in the ring-{'AB'[j-1]} sector-{q['sector']} aisle at the '{key}' stop, looking at the {q['pose']} figure at {q['block']}"))
        return out
    def thrust_views():
        # Q47 (aft down, rings stopped at the index): in ring A's spine-port-sector tube at the first elbow, looking up the ramp leg at the
        # elbow climber on the steep leg's floor ladder (its own eye sees only its arms), and standing on the sector's aft wall in the aisle,
        # looking at the figure on the step below the hatch. Forward (+X) is up in both.
        ec = elbow_climber(s); er, efr = spoke_station(s)[0], ec['frame']; at = efr['points'][1]; chest = ec['local'][0][1][1]
        look = crew_transfer.unit(crew_transfer.sub(chest, at)); X = (1.0, 0.0, 0.0); up = crew_transfer.unit(crew_transfer.sub(X, tuple(x*look[0] for x in look)))
        ts = thrust_stepper(s); S = thrust_step(s); _, _, point, vector = sector_frame(s); eye = (S['floor']+m['eye_height_m'], -.60, .40)
        aim = crew_transfer.unit(crew_transfer.sub(ts['local'][0][1][1], eye))
        return [dict(name='CAM_HUM_THRUST_ELBOW', at=at_index(er, at), look=at_index(er, look, False), up=at_index(er, up, False), lens=m['camera_lens_mm'],
                     clip_start=.05, role="eye of crew at the first elbow of ring A's sector-1 tube under thrust (aft down), looking up the ramp leg at the climber on the steep leg's floor ladder; forward up"),
                dict(name='CAM_HUM_THRUST_STEP', at=point(eye), look=vector(aim), up=vector(X), lens=m['camera_lens_mm'], clip_start=.05,
                     role="eye of crew standing on the ring-A sector-1 aft wall in the aisle under thrust, looking at the figure on the step below the hatch; forward up")]
    rot = spoke_station(s)[0]; first, *others = s['human_entry']['vestibule_rotors']; ref = refuge_station(s); rm = refuge_mannequin(s)
    lad = trunk_ladder(s); tc = trunk_climber(s)
    # The eye cameras sit inside the mannequins' heads, so their near clip skips the head (IMPLEMENTATION).
    return [dict(name='CAM_HUM_ENTRY_PORT', at=world(f, st['port_face']-m['port_camera_inset_m']), look=inboard, up=(1.0, 0.0, 0.0), lens=m['camera_lens_mm'],
                 clip_start=.05, role='eye of crew entering through the open outer hatch'),
            dict(name='CAM_HUM_ENTRY_EYE', at=man['eye'], look=man['look'], up=man['up'], lens=m['camera_lens_mm'],
                 clip_start=.2, role="mannequin's eye on the leak-check panel beside the inner hatch"),
            dict(name='CAM_HUM_NODE', at=node_eye, look=inboard, up=(1.0, 0.0, 0.0), lens=m['camera_lens_mm'],
                 clip_start=.05, role='eye of crew coming through the open inner hatch into the trunk node, looking down the neck into the trunk'),
            dict(name='CAM_HUM_TRUNK_EYE', at=crew['eye'], look=crew['look'], up=crew['up'], lens=m['camera_lens_mm'],
                 clip_start=.2, role="zone-2 mannequin's eye looking aft along the trunk toward the hubs"),
            *vestibule_views(first),
            dict(name='CAM_HUM_SPOKE_TOP', at=at_index(rot, top), look=at_index(rot, d, False), up=at_index(rot, n1, False), lens=m['camera_lens_mm'], clip_start=.05,
                 role='eye of crew at the top of the ring-A sector-1 spoke run, looking down the shaft past the climbing mannequin; ladder at the top'),
            dict(name='CAM_HUM_SPOKE_EYE', at=sp['eye'], look=sp['look'], up=sp['up'], lens=m['camera_lens_mm'],
                 clip_start=.2, role="zone-4 mannequin's eye on the ladder, looking up the shaft to the elbows; ladder at the bottom"),
            dict(name='CAM_HUM_LANDING_EYE', at=lm['eye'], look=lm['look'], up=lm['up'], lens=m['camera_lens_mm'], clip_start=.2,
                 role="zone-5 mannequin's eye at the foot of the ring-A sector-1 landing ladder, looking up through the open hatch into the crew tube; ladder at the bottom"),
            dict(name='CAM_HUM_LANDING_AISLE', at=aisle['at'], look=aisle['look'], up=aisle['up'], lens=m['camera_lens_mm'], clip_start=.05,
                 role='eye of crew standing in the ring-A sector-1 aisle, looking at the landing well, the ladder and the open overhead hatch'),
            *(c for j in others for c in vestibule_views(j)),
            *(bulkhead_view(j) for j in s['human_entry']['tube_rotors'] if crew_transfer.tube_neck(s, j)),
            dict(name='CAM_HUM_REFUGE_PORT', at=crew_transfer.radial(ref['x'], -m['vestibule_camera_offset_m'], ref['th']), look=crew_transfer.radial(0.0, 1.0, ref['th']),
                 up=(1.0, 0.0, 0.0), lens=m['camera_lens_mm'], clip_start=.05,
                 role='eye of crew in the trunk below the refuge port, looking up through the port into the storm refuge'),
            dict(name='CAM_HUM_REFUGE_EYE', at=rm['eye'], look=rm['look'], up=rm['up'], lens=m['camera_lens_mm'], clip_start=.2,
                 role="refuge mannequin's eye at the refuge panel, looking round the annulus past the port to the occupants' anchor rails"),
            dict(name='CAM_HUM_REFUGE_APPROACH', at=(ref['x']-m['refuge_approach_camera_m'], 0.0, 0.0),
                 look=(m['refuge_approach_camera_m'], *crew_transfer.radial(0.0, s['crew_transfer']['trunk_clear_radius_m']/2, ref['th'])[1:]),
                 up=crew_transfer.radial(0.0, 1.0, ref['th']), lens=m['camera_lens_mm'], clip_start=.05,
                 role='eye of crew coming forward along the trunk from the rings, approaching the refuge port and its rails; port side up'),
            dict(name='CAM_HUM_TRUNK_SHAFT', at=crew_transfer.radial(lad['floor']+m['eye_height_m'], m['trunk_axis_offset_m'], lad['th']+math.pi),
                 look=(1.0, 0.0, 0.0), up=crew_transfer.radial(0.0, 1.0, lad['th']+math.pi), lens=m['camera_lens_mm'], clip_start=.05,
                 role='eye of crew standing on the trunk floor beside the ring-A spine port under thrust (aft down), looking up the shaft; ladder side down'),
            dict(name='CAM_HUM_TRUNK_CLIMB_EYE', at=tc['eye'], look=tc['look'], up=tc['up'], lens=m['camera_lens_mm'], clip_start=.2,
                 role="thrust climber's eye on the trunk ladder, level with the refuge port, looking across at the port it climbs into; forward up"),
            *thrust_views(),
            *stop_views()]


def envelope_points(s, f, n=36):
    """Samples of the chamber and trunk-node outer surfaces (the parts wider than the old fitting)."""
    st = stations(s, f); R = st['chamber_r']+st['wall']; out = []
    for k in range(17):
        a = st['node_floor']+(st['top']-st['node_floor'])*k/16
        out += [world(f, a, R, 2*math.pi*j/n) for j in range(n)]
    for a in (st['node_floor'], st['top']):
        out += [world(f, a, rho, 2*math.pi*j/n) for rho in (st['outer'], (st['outer']+R)/2) for j in range(n)]
    return out


def neighbours(s, f):
    """Obstacles the widened route must clear: the crew-transfer world obstacles (without this port's own fitting envelope and connector)
    plus the forward shield's sector keels and ties."""
    own = {f['name'], f"Crew_Connector_{f['name']}"}
    out = [o for o in crew_transfer.world_obstacles(s)+crew_transfer.stationary(s) if o['name'] not in own]
    for j, k in enumerate(forward_shield.sector_keels(s), 1):
        out.append(crew_transfer.rod(f'Shield_Sector_Keel_{j}', [k['a'], k['b']], k['radius']))
    for t in forward_shield.sector_ties(s):
        out.append(crew_transfer.rod(f"Shield_Sector_Tie_{t['sector']}_{t['target']}", [t['a'], t['b']], t['radius']))
    return out


def opening_gap(v, x, th, r):
    """How far point v sits outside the cylinder of a branch opening (x, angle th, radius r) on its side of the trunk; inf on the far side."""
    if v[1]*math.cos(th)+v[2]*math.sin(th) <= 0:
        return math.inf
    return math.hypot(v[0]-x, -v[1]*math.sin(th)+v[2]*math.cos(th))-r


def check(s):
    failures = []
    def require(ok, message):
        if not ok:
            failures.append(message)
    h = s['human_entry']; clr = s['prototype']['mechanical_clearance_m']; tol = 1e-9; suit = h['mannequin']['suited_envelope_diameter_m']
    require(h['status'] == s['human_entry']['mannequin']['status'] == 'PROTOTYPE', 'Entry geometry and guides stay PROTOTYPE')
    require(s['service']['docking']['standard']['clear_passage_m'] == 2*s['prototype']['dock_clear_radius_m'], 'Clear radius carries the 1.6 m passage (Q33)')
    parts = {q['name']: q for q in crew_transfer.stationary(s)}; trunk = parts['Crew_Trunk']
    rows = {}
    for f in ports(s):
        st = stations(s, f); R = st['chamber_r']; row = rows[f['name']] = {'stations_m': {k: v for k, v in st.items() if isinstance(v, float)}}
        # 1. Clear passage at every station from the docking face to the trunk, and the suited-envelope margin at the narrowest.
        passage = {'outer_neck': st['clear'], 'outer_hatch_frame': st['clear'], 'chamber': R, 'inner_hatch_frame': st['clear'], 'trunk_node': st['node_r'],
                   'inboard_neck': st['clear'], 'crew_connector': parts[f"Crew_Connector_{f['name']}"].get('hollow', 0.0), 'trunk': trunk['hollow']}
        narrow = min(passage.values())
        row['passage_radius_m'] = passage; row['suited_margin_m'] = narrow-suit/2
        require(narrow >= s['prototype']['dock_clear_radius_m']-1e-12, f"{f['name']}: passage narrower than the 1.6 m clear passage")
        # 2. The chamber stays inside the forward collar.
        corner = math.hypot(st['top'], R+st['wall'])
        row['hull_gap_m'] = st['skin']-corner
        require(row['hull_gap_m'] >= clr-tol, f"{f['name']}: chamber {row['hull_gap_m']:.3f} m from the hull skin (< {clr})")
        # 3. Each leaf swings inside its room (outer: chamber; inner: trunk node) and parks clear of the passage.
        sweeps = {}
        for which, (lo, hi, radius) in (('outer', (st['a_in'], st['a_out'], R)), ('inner', (st['node_in'], st['inner_frame'][0], st['node_r']))):
            swing = sweeps[which] = [leaf_points(s, f, which, h['hatch_open_deg']*k/SWING_STEPS) for k in range(SWING_STEPS+1)]
            loc = [[local(f, v) for v in pts] for pts in swing]; key = '' if which == 'outer' else 'inner_'
            row[f'{key}leaf_wall_gap_m'] = radius-max(rho for pts in loc for _, rho, _ in pts)
            row[f'{key}leaf_axial_m'] = [min(a for pts in loc for a, _, _ in pts), max(a for pts in loc for a, _, _ in pts)]
            row[f'{key}parked_leaf_min_radius_m'] = min(rho for _, rho, _ in loc[-1])
            require(row[f'{key}leaf_wall_gap_m'] >= h['leaf_swing_clearance_m']-tol, f"{f['name']}: {which} leaf {row[f'{key}leaf_wall_gap_m']:.3f} m from its wall")
            require(lo-tol <= row[f'{key}leaf_axial_m'][0] and row[f'{key}leaf_axial_m'][1] <= hi+tol, f"{f['name']}: {which} leaf leaves its room")
            require(row[f'{key}parked_leaf_min_radius_m'] >= st['clear']-tol, f"{f['name']}: parked {which} leaf intrudes into the clear passage")
        # 4. Fixtures stay outside the passage and both leaves' swings (each leaf seats on its own frame).
        fx = fixtures(s, f); row['fixture_min_radius_m'] = {}; row['fixture_leaf_gap_m'] = {}
        for q in fx:
            row['fixture_min_radius_m'][q['name']] = min(local(f, v)[1] for v in fixture_points(f, q))
            require(row['fixture_min_radius_m'][q['name']] >= st['clear']-tol, f"{q['name']} intrudes into the clear passage")
            gaps = {w: min(fixture_distance(f, q, v) for pts in sw for v in pts) for w, sw in sweeps.items() if q['name'] != f"{f['name']}_{w.title()}_Hatch_Frame"}
            row['fixture_leaf_gap_m'][q['name']] = min(gaps.values())
            for w, g in gaps.items():
                require(g >= .02, f"{q['name']} is in the {w} leaf's swing")
        # 5. The widened shells clear every neighbour by the shared mechanical clearance.
        env = envelope_points(s, f); best = (math.inf, None)
        for o in neighbours(s, f):
            d = min(crew_transfer.distance(o, v) for v in env)
            best = min(best, (d, o['name']))
        row['neighbour_gap_m'] = {'min': best[0], 'obstacle': best[1]}
        require(best[0] >= clr-tol, f"{f['name']}: entry chamber or trunk node {best[0]:.3f} m from {best[1]} (< {clr})")
        # 6. The zone-1 mannequin fits the passage and the chamber, and its hands reach the rail and ahead.
        if f['name'] == h['ports'][0]:
            man = mannequin(s, f); body = [(n, pts, r) for n, pts, r in man['rods'] if 'Arm' not in n]
            row['mannequin'] = {'feet_a_m': man['feet_a'], 'head_a_m': man['head_a'], 'reach_m': man['reach'],
                                'body_max_radius_m': max(local(f, v)[1]+r for _, pts, r in body for v in pts)}
            require(row['mannequin']['body_max_radius_m'] <= st['clear']+tol, 'Mannequin body leaves the clear passage')
            require(st['a_in'] <= man['head_a'] and man['feet_a'] <= st['outer_frame'][0], 'Mannequin outside the chamber')
            require(all(v <= h['mannequin']['reach_m']+tol for v in man['reach'].values()), f"Mannequin reach {man['reach']}")
            parked = sweeps['outer'][-1]
            row['mannequin']['leaf_gap_m'] = min(crew_transfer.seg_dist(v, *pts)-r for _, pts, r in man['rods'] for v in parked)
            require(row['mannequin']['leaf_gap_m'] >= .05, 'Mannequin touches the parked outer leaf')
            row['cameras'] = [{k: v for k, v in c.items() if k in ('name', 'at', 'lens', 'role')} for c in cameras(s, f)]
    # 7. Zone 2, trunk: fixtures inside the bore (brackets end in the wall), outside every branch opening, leaving a clear circle wider than the
    # suited envelope.
    tf = trunk_fixtures(s); f = ports(s)[0]; pts = [v for q in tf for v in fixture_points(f, q)]; radii = [math.hypot(v[1], v[2]) for v in pts]
    x0, x1 = trunk['points'][0][0]+s['crew_transfer']['passage_wall_m'], trunk['points'][1][0]-s['crew_transfer']['passage_wall_m']
    gaps = {n: min(opening_gap(v, x, th, r) for v in pts) for n, x, th, r in openings(s)}
    rows['trunk'] = {'clear_radius_m': trunk['hollow'], 'cavity_x_m': [x0, x1], 'clear_between_fixtures_m': 2*min(radii), 'fixture_max_radius_m': max(radii),
                     'handrail_pieces': len([q for q in tf if q['role'] == 'trunk handrail']), 'lights': len([q for q in tf if q['role'] == 'light strip']),
                     'fixture_opening_gap_m': gaps}
    require(max(radii) <= trunk['radius']+tol and all(x0-tol <= v[0] <= x1+tol for v in pts), 'Trunk fixtures leave the trunk shell')
    require(2*min(radii) >= suit, f'Trunk fixtures leave {2*min(radii):.3f} m, less than the suited envelope')
    require(min(gaps.values()) >= 0.0, f'A trunk fixture sits in a branch opening: {gaps}')
    # 8. The zone-2 mannequin floats in the trunk aft of the junction inside the clear circle (all but the gripping arm), clear of the rails and the
    # ladder, and reaches the rail.
    man = trunk_mannequin(s, f); body = [(n, p, r) for n, p, r in man['rods'] if 'Arm_Rail' not in n]
    rails = [q for q in tf if q['role'] != 'light strip']
    row = rows['trunk']['mannequin'] = {'feet_x_m': man['feet_x'], 'head_x_m': man['head_x'], 'reach_m': man['reach'],
                                        'body_max_radius_m': max(math.hypot(v[1], v[2])+r for _, p, r in body for v in p),
                                        'rail_gap_m': min(crew_transfer.seg_dist(v, *p)-r for _, p, r in body for q in rails for v in fixture_points(f, q)),
                                        'grip_on_rail_m': min(fixture_distance(f, q, man['grip']) for q in rails if q['role'] == 'trunk handrail')}
    require(row['body_max_radius_m'] <= rows['trunk']['clear_between_fixtures_m']/2+tol, 'Trunk mannequin leaves the clear circle between the fixtures')
    require(x0 <= man['head_x'] and man['feet_x'] <= f['x']-s['prototype']['dock_clear_radius_m'], 'Trunk mannequin outside the trunk, or in the junction')
    require(row['rail_gap_m'] >= .02 and row['grip_on_rail_m'] <= .01, f"Trunk mannequin rail gap {row['rail_gap_m']:.3f}, grip {row['grip_on_rail_m']:.3f}")
    require(all(v <= h['mannequin']['reach_m']+tol for v in man['reach'].values()), f"Trunk mannequin reach {man['reach']}")
    # 9. Zone 3, each rotary vestibule (rotor-local): the spine port (1.6 m on ring A; on ring B the largest its window allows) into a chamber deep
    # enough for the suited envelope; fixtures inside the shell, within the chamber and, except the hatch frames (in the tube collars, beyond the
    # crown), outside the port's straight passage to its sector hatch; the suited envelope around the annulus at mid-depth clear of the walls and every fixture; the mannequin inside the
    # cavity, clear of every fixture but the rail it holds, reaching the rail and toward the panel.
    for j in h['vestibule_rotors']:
        rot, v, la = vestibule_station(s, j); w = h['chamber_wall_m']; th_p = la[v['ports'][0]]; vf = vestibule_fixtures(s, j)
        port = parts[f"Crew_Port_{rot['index']}_{v['ports'][0]}"]
        span = (v['cu0']+w, v['cu1']-w); rho = lambda p: math.hypot(p[1], p[2])
        row = rows['vestibule'+ring_tag(s, j)] = {'rotor': rot['index'], 'x_m': [rot['x']+v['u0'], rot['x']+v['u1']], 'chamber_u_m': [v['cu0'], v['cu1']],
                                   'chamber_clear_length_m': span[1]-span[0], 'clear_radii_m': [v['r0'], v['clear']], 'clear_depth_m': v['clear']-v['r0'],
                                   'spine_port_clear_m': 2*port['hollow'], 'outer_hatch_clear_m': 2*vf[0]['r0'],
                                   'window_u_m': list(v['window']) if v['window'] else None}
        frames = [q for q in vf if '_Hatch_Frame_' in q['name']]; mid = (v['r0']+v['clear'])/2
        ring = [crew_transfer.radial(v['hatch_u'], mid, 2*math.pi*i/360) for i in range(360)]
        row['annulus_fixture_gap_m'] = {q['name']: min(fixture_distance(None, q, p) for p in ring) for q in vf}
        row['suited_margin_m'] = min(port['hollow'], mid-v['r0'], v['clear']-mid, min(row['annulus_fixture_gap_m'].values()))-suit/2
        require(math.isclose(port['hollow'], v['port_clear']) and (v['window'] or port['hollow'] >= s['prototype']['dock_clear_radius_m']-tol),
                f"Ring {rot['index']} spine port narrower than the 1.6 m passage without a window limit")
        require(row['suited_margin_m'] >= 0.0, f"The suited envelope does not pass the ring-{rot['index']} spine port and annulus ({row['suited_margin_m']:.3f} m)")
        out_of_shell = [q['name'] for q in vf if q not in frames and not all(span[0]-tol <= p[0] <= span[1]+tol and v['r0']-tol <= rho(p) <= v['r1']+tol
                                                                             for p in fixture_points(None, q))]
        require(not out_of_shell, f'Vestibule fixtures leave the chamber shell: {out_of_shell}')
        require(all(rho(p) >= v['clear']-tol for q in frames for p in fixture_points(None, q)), 'A vestibule hatch frame hangs into the chamber')
        row['fixture_passage_gap_m'] = {q['name']: min(opening_gap(p, v['port_u'], th_p, v['port_clear']) for p in fixture_points(None, q)) for q in vf if q['shape'] != 'tube'}
        require(min(row['fixture_passage_gap_m'].values()) >= 0.0, f"A vestibule fixture sits in the port passage: {row['fixture_passage_gap_m']}")
        vm = vestibule_mannequin(s, j); body = [(n, p, r) for n, p, r in vm['local'] if 'Arm_Rail' not in n]
        held = {vm['rail']}|{q['name'] for q in vf if q['name'].startswith(vm['rail']+'_Bracket')}
        pts = [(crew_transfer.add(ps[0], crew_transfer.sub(ps[1], ps[0]), k/8), r) for _, ps, r in body for k in range(9)]
        row['mannequin'] = {'reach_m': vm['reach'],
                            'cavity_margin_m': min(min(p[0]-r-span[0], span[1]-p[0]-r, rho(p)-r-v['r0'], v['clear']-rho(p)-r) for p, r in pts),
                            'fixture_gap_m': min(min(crew_transfer.seg_dist(p, *ps)-r for _, ps, r in body) for q in vf if q['name'] not in held for p in fixture_points(None, q)),
                            'grip_on_rail_m': fixture_distance(None, next(q for q in vf if q['name'] == vm['rail']), vm['grip'])}
        require(row['mannequin']['cavity_margin_m'] >= 0.0, 'Vestibule mannequin leaves the chamber')
        require(row['mannequin']['fixture_gap_m'] >= .02 and row['mannequin']['grip_on_rail_m'] <= .01,
                f"Vestibule mannequin fixture gap {row['mannequin']['fixture_gap_m']:.3f}, grip {row['mannequin']['grip_on_rail_m']:.3f}")
        require(all(x <= h['mannequin']['reach_m']+tol for x in vm['reach'].values()), f"Vestibule mannequin reach {vm['reach']}")
    # 10. Zone 4, crew spokes of each tube rotor (rotor-local): the 1.6 m tube through its vestibule hatch (ring B: the hatch-sized neck and the
    # bulkhead, the neck passing the suited envelope); ladder and lights inside the bore, leaving a clear circle wider than the suited envelope along
    # the whole axis (the swept suited-envelope passage from the vestibule wall or bulkhead to the inner hoop); on ring A the mannequin on the ladder
    # inside the bore, clear of every fixture but the stiles it holds and the rungs under its feet, reaching both stiles.
    for j in h['tube_rotors']:
        rot, v, la, frames = spoke_station(s, j); ro, rc = crew_transfer.tube_radii(s, j); sf = spoke_fixtures(s, j); vf = vestibule_fixtures(s, j)
        tubes = {q['sector']: q for q in crew_transfer.rotating(s) if q['role'] == 'COAST_TUBE' and q['rotor'] == j}; neck = crew_transfer.tube_neck(s, j)
        row = rows['spoke'+ring_tag(s, j)] = {'rotor': j, 'tube_clear_m': 2*rc, 'tube_outer_m': 2*ro, 'hatch_frame_clear_m': 2*vf[0]['r0'], 'sectors': {},
                                              'neck': neck and {'clear_m': 2*neck['clear'], 'outer_m': 2*neck['outer'], 'bulkhead_radius_m': [neck['base'], neck['base']+neck['wall']],
                                                                'above_outer_wall_m': neck['base']-v['r1'], 'suited_margin_m': neck['clear']-suit/2}}
        ring = 'AB'[j-1]; row['ladder_push'] = ladder_push(s, j)
        require(rc >= s['prototype']['dock_clear_radius_m']-tol and math.isclose(vf[0]['r0'], neck['clear'] if neck else rc),
                f'Ring-{ring} crew tube narrower than the 1.6 m passage, or its vestibule hatch differs from its bore or neck')
        require(not neck or neck['clear'] >= suit/2-tol, f'The ring-{ring} tube neck does not pass the suited envelope')
        for k, fr in frames.items():
            pts = fr['points']; mine = [q for q in sf if q['name'].startswith(f"Crew_Tube_{rot['index']}_{k}_")]; fpts = [p for q in mine for p in fixture_points(None, q)]
            tip, d_run = pts[-1], fr['d'][RUN]
            beyond = lambda p: math.sqrt(max(crew_transfer.dot(crew_transfer.sub(p, tip), crew_transfer.sub(p, tip))-crew_transfer.dot(crew_transfer.sub(p, tip), d_run)**2, 0.0))
            r_fix = [crew_transfer.tube_radius_at(fr, p) if crew_transfer.dot(crew_transfer.sub(p, tip), d_run) <= 0 else beyond(p) for p in fpts]
            # Axis samples from the vestibule's outer wall (ring B: the bulkhead) to the inner hoop, every STEP.
            t0, t1 = run_span(s, fr); w0 = math.dist(pts[0], (pts[0][0], 0.0, 0.0)); legs = list(zip(pts, pts[1:]))
            samples = [crew_transfer.add(a, crew_transfer.sub(b, a), i*STEP/math.dist(a, b)) for n, (a, b) in enumerate(legs) for i in range(int(math.dist(a, b)/STEP)+1)
                       if not (n == 0 and i*STEP < v['r1']-w0) and not (n == RUN and i*STEP > t1)]
            clear = min(min(fixture_distance(None, q, p) for q in mine) for p in samples[::4])
            bends = [math.degrees(math.acos(max(-1.0, min(1.0, crew_transfer.dot(a, b))))) for a, b in zip(fr['d'], fr['d'][1:])]
            # The tube-side hatch panel within reach of crew standing on the lowest tube rung, the body spoke_body_offset_m toward the ladder.
            H = s['prototype']['human_height_m']
            low = max(crew_transfer.dot(crew_transfer.sub(a, pts[RUN]), d_run) for a, _ in next(q for q in mine if q['role'] == 'ladder rungs')['segments'])
            shoulder = crew_transfer.add(crew_transfer.add(pts[RUN], d_run, low-.75*H), fr['n1'][RUN], -h['mannequin']['spoke_body_offset_m'])
            panel = next(q for q in mine if q['name'].endswith('_Hatch_Panel'))
            row['sectors'][k] = {'axis_m': [list(p) for p in pts], 'length_m': crew_transfer.length(pts), 'elbows_deg': bends, 'ladder_run_t_m': [t0, t1],
                                 'hatch_panel_reach_m': fixture_distance(None, panel, shoulder),
                                 'rungs': len(next(q for q in mine if q['role'] == 'ladder rungs')['segments']), 'lights': len([q for q in mine if q['role'] == 'light strip']),
                                 'fixture_max_radius_m': max(r_fix), 'clear_between_fixtures_m': 2*min(r_fix), 'suited_sweep_margin_m': min(clear, rc)-suit/2}
            require(max(r_fix) <= rc+.015, f'Ring-{ring} spoke {k} fixtures leave the tube bore ({max(r_fix):.3f} m)')
            require(2*min(r_fix) >= suit and clear >= suit/2, f'Ring-{ring} spoke {k} fixtures leave less than the suited envelope')
            require(math.dist(tubes[k]['points'][0], pts[0]) < 1e-9 and math.isclose(tubes[k]['hollow'], rc), f'Ring-{ring} spoke {k} frames differ from its crew tube')
            require(row['sectors'][k]['hatch_panel_reach_m'] <= h['mannequin']['reach_m'], f"Ring-{ring} spoke {k} hatch panel out of reach ({row['sectors'][k]['hatch_panel_reach_m']:.2f} m)")
    for j in h['tube_rotors']:
        rot, v, la, frames = spoke_station(s, j); ro, rc = crew_transfer.tube_radii(s, j); sf = spoke_fixtures(s, j); row = rows['spoke'+ring_tag(s, j)]
        sp = spoke_mannequin(s, j); fr = frames[sp['sector']]; pts = fr['points']; mine = [q for q in sf if q['name'].startswith(f"Crew_Tube_{j}_{sp['sector']}_")]
        body = [(n, p, r) for n, p, r in sp['local'] if 'Arm' not in n and 'Arrester' not in n]; held = {q['name'] for q in mine if q['role'] in ('ladder stile', 'ladder bracket')}
        bpts = [(crew_transfer.add(ps[0], crew_transfer.sub(ps[1], ps[0]), i/8), r) for _, ps, r in body for i in range(9)]
        rung = next(q for q in mine if q['role'] == 'ladder rungs'); stiles = [q for q in mine if q['role'] == 'ladder stile']
        feet = [ps[0] for n, ps, _ in sp['local'] if '_Leg_' in n]; free = [q for q in mine if q['name'] not in held and q is not rung]
        rail = next(q for q in mine if q['role'] == 'fall-arrest guide rail'); gear = {n.rsplit('_', 1)[-1]: ps for n, ps, _ in sp['local'] if 'Arrester' in n}
        # Fixture surface samples against the body's rods, and body samples against each fixture's exact solid (a long rod's surface samples are
        # metres apart).
        row['mannequin'] = {'sector': sp['sector'], 'feet_radius_m': sp['feet_radius_m'], 'reach_m': sp['reach'],
                            'bore_margin_m': min(rc-crew_transfer.tube_radius_at(fr, p)-r for p, r in bpts),
                            'fixture_gap_m': min(min(min(crew_transfer.seg_dist(p, *ps)-r for _, ps, r in body) for q in free for p in fixture_points(None, q)),
                                                 min(fixture_distance(None, q, p)-r for q in free for p, r in bpts)),
                            'rung_gap_m': min(fixture_distance(None, rung, p)-.07 for p in feet),
                            'grip_on_stile_m': max(min(fixture_distance(None, q, g) for q in stiles) for g in sp['grips']),
                            'arrester_off_rail_axis_m': fixture_distance(None, rail, crew_transfer.add(gear['Arrester'][0], crew_transfer.sub(*gear['Arrester'][::-1]), .5))+rail['radius'],
                            'arrester_link_m': math.dist(*gear['Link'])}
        L5 = landing(s); top = rail['points'][0]
        row['arrest_rail'] = {'radius_from_tube_axis_m': arrest_rail(s)[0], 'length_m': crew_transfer.length(rail['points']),
                              'brackets': len(next(q for q in mine if q['role'] == 'fall-arrest rail bracket')['segments']),
                              'clip_on_spin_gravity_g': habitat_ring.floor_gravity_g(s, math.hypot(top[1], top[2])),
                              'unclipped_drop_to_deck_m': -L5['tube_end']-.72*s['prototype']['human_height_m']}
        mm = row['mannequin']; ring = 'AB'[j-1]
        require(mm['bore_margin_m'] >= 0.0, f'Ring-{ring} spoke mannequin leaves the tube bore')
        require(mm['fixture_gap_m'] >= .02 and mm['grip_on_stile_m'] <= .01 and 0.0 <= mm['rung_gap_m'] <= .03 and mm['arrester_off_rail_axis_m'] <= 1e-6,
                f"Ring-{ring} spoke mannequin fixture gap {mm['fixture_gap_m']:.3f}, grip {mm['grip_on_stile_m']:.3f}, feet to rung {mm['rung_gap_m']:.3f}, "
                f"arrester off the rail {mm['arrester_off_rail_axis_m']:.3f}")
        require(all(x <= h['mannequin']['reach_m']+tol for x in sp['reach'].values()), f"Ring-{ring} spoke mannequin reach {sp['reach']}")
    # 11. Zone 5, sector landing (sector frame, every sector and every function's blocks): the 1.6 m hatch frame; the leaf seated and sliding
    # open clear of the ladder ends, rails, chase and blocks; the landing well free of blocks; fixtures inside the skin; the swept suited envelope
    # down the hatch axis from the tube tip to the deck and across to the aisle centre; the mannequin on the deck in the well, gripping both stiles.
    import habitat_interior
    L = landing(s); lf = landing_fixtures(s); named = {q['name']: q for q in lf}; sec = habitat_interior.section(s); clr_l = h['leaf_swing_clearance_m']
    blocks = [(f"{fn}:{b['name']}", b) for fn in s['interior']['layouts'] for b in habitat_interior.zones(s, fn)]
    def box_gap(b, p):
        return math.sqrt(sum(max(b['min'][i]-p[i], 0.0, p[i]-b['max'][i])**2 for i in range(3)))
    def disc(zc, y0, y1, n=24):
        return [(L['x']+L['leaf_r']*f*math.cos(2*math.pi*j/n), y, zc+L['leaf_r']*f*math.sin(2*math.pi*j/n)) for y in (y0, y1) for f in (0.0, .25, .5, .75, 1.0) for j in range(n)]
    sweep = [p for i in range(13) for p in disc(L['z']+(L['leaf_open_z']-L['z'])*i/12, *L['leaf_open'])]+disc(L['z'], L['seat'], L['leaf_open'][1])
    ends = [dict(shape='rod', radius=h['handrail_radius_m'], points=[(xs, L['tube_end']-.3, L['stile_z']), (xs, L['tube_end'], L['stile_z'])]) for xs in L['stile_x']]
    leaf_gaps = {'tube_stile_ends': min(fixture_distance(None, q, p) for q in ends for p in sweep),
                 **{q['name']: min(fixture_distance(None, q, p) for p in sweep) for q in lf if q['name'] not in ('Sector_Hatch_Frame', 'Sector_Hatch_Leaf')},
                 'blocks': min(box_gap(b, p) for _, b in blocks for p in sweep)}
    well = {'min': (L['well_x'][0], sec['ceiling_y_m'], L['well_z'][0]), 'max': (L['well_x'][1], sec['deck_y_m'], L['well_z'][1])}
    in_well = [n for n, b in blocks if habitat_interior.overlap(b, well)]
    fixture_block = {q['name']: min(box_gap(b, p) for _, b in blocks for p in fixture_points(None, q)) for q in lf if q['name'] != 'Sector_Hatch_Leaf'}
    fixture_block['Sector_Hatch_Leaf'] = min(box_gap(b, p) for _, b in blocks for p in disc(L['leaf_open_z'], *L['leaf_open']))
    m_skin = s['habitat_ring']['sector_skin_m']; x_in = sec['length_m']/2-m_skin
    outside = [q['name'] for q in lf if q['name'] != 'Sector_Hatch_Frame' and not all(
        abs(p[0]) <= x_in+tol and sec['ceiling_y_m']-tol <= p[1] <= sec['deck_y_m']+tol and abs(p[2]) <= habitat_interior.wall_half_width(s, p[1])-m_skin+tol
        for p in fixture_points(None, q))]
    # Suited envelope: sphere centres on the hatch axis from the tube tip down to standing on the deck, then across the deck to the aisle centre at
    # every body height.
    R = suit/2; sp_pts = [(L['x'], y, L['z']) for y in [L['tip_y']+i*STEP for i in range(int((-R-L['tip_y'])/STEP)+1)]]
    Hh = s['prototype']['human_height_m']; walk = [(L['x'], -hh, L['z']*(1-i/20)) for i in range(21) for hh in (R, Hh/2, Hh-R)]
    def env_gap(p):                  # to the landing fixtures, every block, and the frame's (and the tube's) bore above the seat
        return min(min(fixture_distance(None, q, p) for q in lf if q['name'] != 'Sector_Hatch_Frame'), min(box_gap(b, p) for _, b in blocks),
                   L['clear_r']-math.hypot(p[0]-L['x'], p[2]-L['z']) if p[1] <= L['seat'] else math.inf)
    lm = landing_mannequin(s); body = [(n, p, rr) for n, p, rr in lm['local'] if 'Arm' not in n]; held = {'Sector_Ladder_Stile_1', 'Sector_Ladder_Stile_2', 'Sector_Ladder_Brackets'}
    bpts = [(crew_transfer.add(ps[0], crew_transfer.sub(ps[1], ps[0]), i/8), rr) for _, ps, rr in body for i in range(9)]
    feet = [ps[0] for n, ps, _ in lm['local'] if '_Leg_' in n]
    row = rows['landing'] = {
        'hatch_clear_m': 2*L['clear_r'], 'frame_radii_m': [L['clear_r'], L['frame_r']], 'frame_y_m': [L['frame_top'], L['seat']], 'ceiling_y_m': sec['ceiling_y_m'],
        'headroom_m': sec['headroom_m'], 'leaf_radius_m': L['leaf_r'], 'leaf_travel_m': L['travel'], 'leaf_gaps_m': leaf_gaps,
        'ladder': {'stile_z_m': L['stile_z'], 'stile_y_m': [L['stile_top'], 0.0], 'tube_stile_end_y_m': L['tube_end'], 'rungs': len(named['Sector_Ladder_Rungs']['segments']),
                   'rung_y_m': [a[1] for a, _ in named['Sector_Ladder_Rungs']['segments']]},
        'well_m': {'x': list(L['well_x']), 'z': list(L['well_z']), 'width': L['well_x'][1]-L['well_x'][0], 'depth': L['well_z'][1]-L['well_z'][0]},
        'blocks_in_well': in_well, 'fixture_block_gap_m': fixture_block, 'fixtures_outside_skin': outside,
        'descent_suited_margin_m': min(env_gap(p) for p in sp_pts)-R, 'walk_suited_margin_m': min(env_gap(p) for p in walk)-R,
        'mannequin': {'sector': lm['sector'], 'reach_m': lm['reach'], 'feet_y_m': [p[1] for p in feet],
                      'fixture_gap_m': min(min(crew_transfer.seg_dist(p, *ps)-rr for _, ps, rr in body) for q in lf if q['name'] not in held for p in fixture_points(None, q)),
                      'block_gap_m': min(box_gap(b, p)-rr for _, b in blocks for p, rr in bpts),
                      'grip_on_stile_m': max(min(fixture_distance(None, named[f'Sector_Ladder_Stile_{j}'], g) for j in (1, 2)) for g in lm['grips']),
                      'in_well': all(L['well_x'][0] <= p[0] <= L['well_x'][1] and L['well_z'][0] <= p[2] <= L['well_z'][1] for p in feet)}}
    require(L['clear_r'] >= s['prototype']['dock_clear_radius_m']-tol, 'Sector hatch narrower than the 1.6 m passage')
    require(min(leaf_gaps.values()) >= clr_l-tol, f'Hatch leaf sweep too close: {leaf_gaps}')
    require(not in_well, f'Interior blocks in the landing well: {in_well}')
    require(min(fixture_block.values()) >= clr_l-tol, f"Landing fixtures too close to interior blocks: {fixture_block}")
    require(not outside, f'Landing fixtures leave the skin: {outside}')
    require(row['descent_suited_margin_m'] >= 0.0 and row['walk_suited_margin_m'] >= 0.0,
            f"Suited envelope does not pass the landing: descent {row['descent_suited_margin_m']:.3f}, walk {row['walk_suited_margin_m']:.3f}")
    mm = row['mannequin']
    require(mm['in_well'] and all(abs(y+.07) <= tol for y in mm['feet_y_m']), 'Landing mannequin not standing on the deck in the well')
    require(mm['fixture_gap_m'] >= .02 and mm['block_gap_m'] >= .02 and mm['grip_on_stile_m'] <= .01,
            f"Landing mannequin fixture gap {mm['fixture_gap_m']:.3f}, block gap {mm['block_gap_m']:.3f}, grip {mm['grip_on_stile_m']:.3f}")
    require(all(x <= h['mannequin']['reach_m']+tol for x in lm['reach'].values()), f"Landing mannequin reach {lm['reach']}")
    # 12. Refuge leg (vehicle frame): the hollow port off the trunk into the refuge's inner face passes the suited envelope; fixtures inside the
    # cavity's walls (the panel's back in the inner wall, the outer brackets and lights on the shell) and clear of the port's opening; one station per rated occupant, each a suited body lying
    # axially inboard of its anchor rail, inside the cavity and clear of its neighbours and of every fixture but that rail; the circulation annulus
    # passes the suited envelope between the inner-wall fixtures and the occupants; the mannequin inside the cavity, clear of every fixture but the
    # hoop rail it holds, reaching the rail and the panel.
    r = refuge_station(s); rf = refuge_fixtures(s); port = parts['Crew_Refuge_Port']; R = suit/2; rho = lambda p: math.hypot(p[1], p[2])
    H = s['prototype']['human_height_m']; xc = (r['cavity_x0']+r['cavity_x1'])/2; core = layout.spine_radius_at(s, r['x'])
    def station(a):                  # sphere centres of the suited body axis, centred in the cavity
        return [crew_transfer.radial(xc-H/2+R+(H-2*R)*i/8, r['body_r'], a) for i in range(9)]
    def own(q, k):
        return q['name'] in (f'Refuge_Anchor_Rail_{k}', f'Refuge_Anchor_Rail_{k}_Brackets')
    gaps = {q['name']: min(fixture_distance(None, q, p) for k, a in enumerate(r['anchors'], 1) for p in station(a) if not own(q, k))-R for q in rf}
    ring = [crew_transfer.radial(x, r['circulation_r'], 2*math.pi*i/360) for x in (r['x'], *r['hoop_x']) for i in range(360)]
    outside = [q['name'] for q in rf if not all(r['cavity_x0']-tol <= p[0] <= r['cavity_x1']+tol and r['wall'][0]-tol <= rho(p) <= r['outer']+tol
                                                 for p in fixture_points(None, q))]
    in_port = {q['name']: min(opening_gap(p, r['x'], r['th'], r['outer_r']) for p in fixture_points(None, q)) for q in rf}
    rm = refuge_mannequin(s); body = [(n, p, rr) for n, p, rr in rm['rods'] if 'Arm' not in n]; held = {'Refuge_Hoop_Rail_Aft', 'Refuge_Hoop_Rail_Aft_Brackets'}
    bpts = [(crew_transfer.add(ps[0], crew_transfer.sub(ps[1], ps[0]), i/8), rr) for _, ps, rr in body for i in range(9)]
    row = rows['refuge'] = {
        'port': {'x_m': r['x'], 'angle_deg': math.degrees(r['th']), 'clear_m': 2*port['hollow'], 'length_m': r['inner']-trunk['radius'],
                 'suited_margin_m': port['hollow']-R, 'spine_opening_deg': 2*math.degrees(math.asin(min(1.0, port['radius']/core)))},
        'cavity': {'x_m': [r['cavity_x0'], r['cavity_x1']], 'radii_m': [r['inner'], r['pressure']], 'length_m': r['cavity_x1']-r['cavity_x0'],
                   'depth_m': r['pressure']-r['inner'], 'inner_wall_radii_m': list(r['wall']), 'inner_wall_to_spine_m': r['wall'][0]-core,
                   'pressure_volume_m3': r['pressure_volume_m3'], 'volume_per_person_m3': r['volume_per_person_m3'],
                   'thrust_floor_m2_per_person': math.pi*(r['pressure']**2-r['inner']**2)/r['capacity_persons']},
        'occupants': {'stations': len(r['anchors']), 'rated_occupancy': s['crew']['rated_occupancy']['value'], 'body_axis_radius_m': r['body_r'],
                      'axial_margin_m': (r['cavity_x1']-r['cavity_x0']-H)/2, 'neighbour_gap_m': 2*r['body_r']*math.sin(r['pitch']/2)-2*R,
                      'outer_wall_gap_m': r['pressure']-r['body_r']-R, 'fixture_gap_m': min(gaps.values()),
                      'circulation_radius_m': r['circulation_r'], 'circulation_margin_m': min(min(min(fixture_distance(None, q, p) for q in rf) for p in ring)-R,
                                                                                            r['body_r']-2*R-r['circulation_r'])},
        'fixtures_outside_cavity': outside, 'fixture_port_gap_m': min(in_port.values()),
        'anchor_rails': len([q for q in rf if q['role'] == 'occupant anchor rail']), 'lights': len([q for q in rf if q['role'] == 'light strip']),
        'mannequin': {'reach_m': rm['reach'],
                      'cavity_margin_m': min(min(p[0]-rr-r['cavity_x0'], r['cavity_x1']-p[0]-rr, rho(p)-rr-r['inner'], r['pressure']-rho(p)-rr) for p, rr in bpts),
                      'fixture_gap_m': min(min(min(crew_transfer.seg_dist(p, *ps)-rr for _, ps, rr in body) for q in rf if q['name'] not in held for p in fixture_points(None, q)),
                                           min(fixture_distance(None, q, p)-rr for q in rf if q['name'] not in held for p, rr in bpts)),
                      'grip_on_rail_m': fixture_distance(None, next(q for q in rf if q['name'] == 'Refuge_Hoop_Rail_Aft'), rm['grip']),
                      'panel_from_shoulder_m': fixture_distance(None, next(q for q in rf if q['name'] == 'Refuge_Panel'), rm['rods'][2][1][0])}}
    oc = row['occupants']; mm = row['mannequin']
    require(port['hollow'] >= R-tol, f"The refuge port does not pass the suited envelope ({row['port']['suited_margin_m']:.3f} m)")
    require(oc['stations'] == r['capacity_persons'] >= oc['rated_occupancy'], 'The refuge holds fewer occupant stations than its rated occupancy')
    require(min(oc['axial_margin_m'], oc['neighbour_gap_m'], oc['outer_wall_gap_m'], oc['fixture_gap_m']) >= -tol,
            f"Refuge occupant stations collide: axial {oc['axial_margin_m']:.3f}, neighbours {oc['neighbour_gap_m']:.3f}, wall {oc['outer_wall_gap_m']:.3f}, fixtures {oc['fixture_gap_m']:.3f}")
    require(oc['circulation_margin_m'] >= 0.0, f"The refuge circulation annulus does not pass the suited envelope ({oc['circulation_margin_m']:.3f} m)")
    require(not outside and row['fixture_port_gap_m'] >= 0.0, f"Refuge fixtures outside the cavity {outside} or in the port ({row['fixture_port_gap_m']:.3f} m)")
    require(mm['cavity_margin_m'] >= 0.0, 'Refuge mannequin leaves the cavity')
    require(mm['fixture_gap_m'] >= .02 and mm['grip_on_rail_m'] <= .01, f"Refuge mannequin fixture gap {mm['fixture_gap_m']:.3f}, grip {mm['grip_on_rail_m']:.3f}")
    require(all(x <= h['mannequin']['reach_m']+tol for x in rm['reach'].values()) and mm['panel_from_shoulder_m'] <= h['mannequin']['reach_m'],
            f"Refuge mannequin reach {rm['reach']}, panel {mm['panel_from_shoulder_m']:.2f} m")
    # 13. Emergency route to the refuge (eye-level review). Crew floating trunk_axis_offset_m off the trunk axis toward the port, head-first from
    # either direction, the shoulder abreast the port's rim: its reach to the nearest refuge port rail (required) and to the nearest trunk handrail.
    # From each sector's aisle centre back up the ladders and tube, through the vestibule and spine port, forward along the trunk to the refuge's
    # inner face: the distance, the rungs climbed and the time at the review pace (not a procedure). Rings spinning, crossing between the
    # co-rotating vestibule and the stationary spine port: the speed of the port relative to the chamber at the spine, mid-depth and the
    # outer-wall rails, how often it passes, and the spin gravity at mid-depth.
    off = h['mannequin']['trunk_axis_offset_m']; reach = h['mannequin']['reach_m']; sh = [crew_transfer.radial(r['x']+e*r['clear'], off, r['th']) for e in (-1, 1)]
    near = lambda role: max(min(fixture_distance(None, q, p) for q in tf if q['role'] == role) for p in sh)
    w = habitat_ring.omega(s); pace = h['mannequin']['climb_review_speed_m_s']; routes = route(s); em = {}
    for j in h['tube_rotors']:
        rot, v, la = vestibule_station(s, j)
        for k in la:
            key = f"{'AB'[j-1]}{k}"; pts = [p for _, p in routes[key]['path']][3:]; walk = routes[key]['walk']
            d = math.dist(walk[0][0], walk[-1][0])+crew_transfer.length(pts)+abs(pts[0][0]-r['x'])+r['inner']
            em[key] = {'to_refuge_m': d, 'rungs': rows['spoke'+ring_tag(s, j)]['sectors'][k]['rungs']+rows['landing']['ladder']['rungs'],
                       'minutes_at_review_pace': d/pace/60}
    spin = {}
    for j in h['vestibule_rotors']:
        rot, v, _ = vestibule_station(s, j); mid = (v['r0']+v['clear'])/2
        spin['AB'[j-1]] = {'port_speed_m_s': {'spine': w*v['r0'], 'mid_depth': w*mid, 'outer_rails': w*(v['clear']-h['handrail_standoff_m'])},
                           'port_passes_every_s': 2*math.pi/w, 'mid_depth_g': w*w*mid/habitat_ring.G0}
    row['emergency'] = {'port_rail_reach_m': near('refuge port handrail'), 'trunk_rail_reach_m': near('trunk handrail'), 'reach_m': reach,
                        'sectors': em, 'review_speed_m_s': pace, 'round_to_far_station_m': math.pi*r['circulation_r'], 'spin_transfer': spin}
    require(row['emergency']['port_rail_reach_m'] <= reach, f"Refuge port rails out of reach from the trunk ({row['emergency']['port_rail_reach_m']:.2f} m)")
    # IND-001: the induction legs in order with their length (path and walk), rungs (every tube and landing ladder they pass) and time at the
    # review pace, docked; the route sweep checks them against the built model.
    # 2.5: a forward leg adds the aisle walks to its sector's stops (a reversed leg would start with the walk from the last stop to the landing).
    # Per sector stop: its station (pose, block, where it stands on the aisle and how far that is from the landing) and the way to the refuge.
    ind = induction(s); legs = {}; spoke = rows['spoke'+ring_tag(s, s['induction']['ring'])]['sectors']; per = rows['landing']['ladder']['rungs']
    ss = induction_stations(s); x_land = landing(s)['x']; last = [q['key'] for q in ind['stops'] if q['at'] == 'sector'][-1]
    for leg in ind['legs']:
        q = routes[leg.lstrip('-')]; walk = q['walk']; d = crew_transfer.length([p for _, p in q['path']])+(math.dist(walk[0][0], walk[-1][0]) if walk else 0.0)
        d += abs(ss[last]['aisle_x']-x_land) if leg.startswith('-') else sum(math.dist(w[0][0], w[-1][0]) for _, w in q.get('stops', []))
        legs[leg] = {'length_m': d, 'rungs': sum(spoke[int(k[1:])]['rungs']+per for k in leg.lstrip('-').split('-')), 'minutes_at_review_pace': d/pace/60}
    stops = []
    for q in ind['stops']:
        row = {k: q[k] for k in ('key', 'at', 'scenes', 'point')}
        if q['key'] in ss:
            t = ss[q['key']]; aisle = abs(t['aisle_x']-x_land); out = em[f"{ind['ring']}{t['sector']}"]['to_refuge_m']+aisle
            row.update(function=t['function'], pose=t['pose'], block=t['block'], aisle_x_m=t['aisle_x'], aisle_to_landing_m=aisle,
                       to_refuge_m=out, minutes_to_refuge_at_review_pace=out/pace/60)
        stops.append(row)
    # 4.1: each stop's operating state (induction_sequence).
    seq = induction_sequence(s)
    for row in stops:
        row.update(seq['stops'][row['key']])
    rows['induction'] = {'ring': ind['ring'], 'sectors': ind['sectors'], 'legs': legs, 'total_m': sum(x['length_m'] for x in legs.values()),
                         'total_rungs': sum(x['rungs'] for x in legs.values()), 'sequence': [st['key'] for st in seq['steps']], 'stops': stops}
    # 14. Thrust review: for major thrust the rings stop and lock and aft is down, so the trunk is a shaft. The ladder reaches the floor beside
    # ring A's spine port and stops short of the primary branch; for each branch it passes: the rung (or floor) at or below the mouth's sill (the
    # aft edge of its clear opening), the near stile's gap to the mouth and the rail's distance from the mouth's edge on the ladder side (to clip
    # on from inside the port). The climber stands on the ladder inside the clear circle, clear of the other fixtures, reaching the stiles and,
    # with its eye level with the refuge port, the port's rim. Falls from each step-off to the floor at the LOW_THRUST limit and the First
    # Ignition peak. Per sector, the way to the refuge with aft down: the drop from the deck's level to the spine port, the climb up the trunk
    # from the spine port's sill to the refuge port's and its rungs, the legs steeper than steep_leg_deg, and the sector hatch's sill above the
    # aft bulkhead (the floor under thrust). The climber's fixture gap also measures body samples against each fixture's exact solid.
    L = trunk_ladder(s); tr = s['crew_transfer']['trunk_clear_radius_m']; rad = lambda p: math.hypot(p[1], p[2]); g0 = habitat_ring.G0
    accel = {'low_thrust_g': s['habitat']['low_thrust_limit']['value'], 'first_ignition_peak_g': s['mission']['first_ignition']['max_accel']}
    stile_pts = {a: [crew_transfer.radial(L['floor']+(L['top']-L['floor'])*i/400, L['rl'], a) for i in range(401)] for a in L['stiles']}
    side = {}
    for n, x, th, _ in openings(s):
        clear = parts[n].get('hollow', parts[n]['radius']); sill = x-clear
        if not L['floor'] <= sill <= L['top']:
            side[n] = {'sill_x_m': sill, 'sill_above_floor_m': sill-L['floor'], 'served': False}
            continue
        e = min(L['stiles'], key=lambda a: crew_transfer.angle_diff(a, th)); s_e = math.copysign(1.0, math.remainder(e-th, math.tau))
        edge = crew_transfer.radial(x, tr, th+s_e*math.asin(clear/tr)); gap = min(opening_gap(p, x, th, clear) for p in stile_pts[e])-h['handrail_radius_m']
        side[n] = {'sill_x_m': sill, 'sill_above_floor_m': sill-L['floor'], 'served': True,
                   'sill_above_rung_m': sill-max([L['floor']]+[r_ for r_ in L['rungs'] if r_ <= sill+1e-6]),
                   'near_stile_gap_m': gap if gap < math.inf else None,     # None: both stiles on the trunk's far half
                   'rail_from_mouth_edge_m': math.dist(edge, crew_transfer.radial(x, L['rail_r'], L['th']))-L['rail_rr']}
    tc = trunk_climber(s); body = [(n, p, r_) for n, p, r_ in tc['rods'] if 'Arm' not in n and 'Arrester' not in n]
    held = {'Crew_Trunk_Ladder_Stile_1', 'Crew_Trunk_Ladder_Stile_2', 'Crew_Trunk_Ladder_Rungs', 'Crew_Trunk_Arrest_Rail'}
    others = [q for q in tf if q['name'] not in held]
    step = {'ring_B_port': side[next(n for n in side if n.startswith(f"Crew_Port_{h['vestibule_rotors'][1]}_"))]['sill_x_m'] if len(h['vestibule_rotors']) > 1 else None,
            'refuge_port': r['x']-r['clear'], 'ladder_top_rung': L['rungs'][-1]}
    falls = {k: {g: {'height_m': x-L['floor'], 'speed_m_s': math.sqrt(2*a*g0*(x-L['floor'])), 'height_1g_m': a*(x-L['floor'])} for g, a in accel.items()}
             for k, x in step.items() if x is not None}
    import habitat_interior
    sec = habitat_interior.section(s); land = landing(s); steep = h['steep_leg_deg']; thrust = {}
    for j in h['tube_rotors']:
        rot, v, la = vestibule_station(s, j)
        for k in la:
            key = f"{'AB'[j-1]}{k}"; pts = [p for _, p in routes[key]['path']][3:]; zs = [z for z, _ in routes[key]['path']][3:]
            legs = [(zs[i+1], math.degrees(math.atan2(abs(b[0]-a[0]), math.hypot(b[1]-a[1], b[2]-a[2]))), math.dist(a, b), b[0]-a[0]) for i, (a, b) in enumerate(zip(pts, pts[1:]))]
            sill = side[f"Crew_Port_{rot['index']}_{v['ports'][0]}"]['sill_x_m']; top = r['x']-r['clear']
            thrust[key] = {'deck_level_above_spine_port_m': pts[-1][0]-pts[0][0], 'trunk_climb_m': top-sill,
                           'trunk_rungs': len([x for x in L['rungs'] if sill < x <= top+1e-6]),
                           'steep_legs': [{'zone': z, 'slope_deg': a, 'length_m': d, 'rise_m': dx} for z, a, d, dx in legs if a > steep]}
    row = rows['trunk']['thrust'] = {
        'ladder': {'angle_deg': h['trunk_ladder_deg'], 'x_m': [L['floor'], L['top']], 'height_m': L['top']-L['floor'], 'rungs': len(L['rungs']),
                   'first_rung_above_floor_m': L['rungs'][0]-L['floor'], 'reaches_floor': all(abs(sp[0][0]-L['floor']) < tol for sp in L['spans'].values()),
                   'stile_radius_m': L['rl'], 'rail_radius_m': L['rail_r'], 'rail_x_m': list(L['rail'])},
        'ports': side, 'falls': falls, 'sectors': thrust, 'steep_leg_deg': steep,
        'sector_hatch_sill_above_aft_bulkhead_m': land['x']-land['clear_r']+sec['length_m']/2,
        'climber': {'feet_x_m': tc['feet_x'], 'rung_x_m': tc['rung_x'], 'reach_m': tc['reach'],
                    'body_max_radius_m': max(rad(p)+r_ for _, ps, r_ in body for p in ps),
                    'fixture_gap_m': min(min(crew_transfer.seg_dist(v, *ps)-r_ for _, ps, r_ in body for q in others for v in fixture_points(f, q)),
                                         min(fixture_distance(f, q, p)-r_ for q in others for _, ps, r_ in body
                                             for p in (crew_transfer.add(ps[0], crew_transfer.sub(ps[1], ps[0]), i/8) for i in range(9)))),
                    'grip_on_stile_m': max(min(fixture_distance(f, q, g) for q in tf if q['name'].startswith('Crew_Trunk_Ladder_Stile')) for g in tc['grips']),
                    'refuge_rim_from_shoulder_m': min(math.dist(tc['shoulder'], crew_transfer.radial(r['x']+r['clear']*math.cos(a), tr, r['th']+math.asin(r['clear']*math.sin(a)/tr)))
                                                      for a in (math.tau*i/360 for i in range(360)))}}
    # Q47: the aft-down footing (MEC-020). Per tube rotor (its spine-port sector; every tube has the same legs): each floor ladder's slope, rungs and
    # rise between them, and the step from the leg's floor at its lower joint to the first rung's top and from the last rung's top to the floor at
    # its upper joint; the run's clear height with aft down and the fall-arrest rail as a handrail along it (its height above the run's floor). On
    # ring A the elbow climber: inside the bore, clear of every fixture but the floor ladder it stands on and holds, its reach and its arrester
    # link. Below the sector hatch: the step rungs above the aft wall, the step from the top rung to the sill, the stepper's reach to the landing
    # ladder's stiles and its gap to every block of every function and to the landing fixtures it does not hold. Each drum chamber: its clear
    # length (the height with aft down) and what the crawl rails leave bare beside each opening.
    q47 = row['q47'] = {'tubes': {}, 'vestibules': {}}; X = lambda p: p[0]; P = crew_transfer.tube_point
    for j in h['tube_rotors']:
        rot, v, la, frames = spoke_station(s, j); k = v['ports'][0]; fr = frames[k]; rc = crew_transfer.tube_radii(s, j)[1]; ra, _ = arrest_rail(s)
        legs = []; rl, phi = ladder(s)
        for fl in floor_ladders(s, fr):
            i, psi = fl['leg'], fl['psi']; tops = [X(P(fr, i, rl*math.cos(phi), psi, t))+h['handrail_radius_m'] for t in fl['rungs']]
            legs.append({'leg': i, 'slope_deg': fl['slope_deg'], 'rungs': len(fl['rungs']), 'rise_per_rung_m': h['spoke_rung_pitch_m'],
                         'first_step_m': tops[0]-X(P(fr, i, rc, psi, None)), 'last_step_m': X(P(fr, i+1, rc, psi, None))-tops[-1],
                         'stile_length_m': fl['t'][1]-fl['t'][0]})
        d = fr['d'][RUN]; f = (-1.0, 0.0, 0.0); psi = math.atan2(crew_transfer.dot(f, fr['n2'][RUN]), crew_transfer.dot(f, fr['n1'][RUN]))
        # Resting on the run with aft down: no fixture, the walker sits on its floor (seated height about 0.52 H) and rises by the handrail.
        q47['tubes']['AB'[j-1]+str(k)] = {'floor_ladders': legs, 'run_clear_height_m': 2*rc, 'run_stoop_m': H-2*rc, 'run_seated_headroom_m': 2*rc-.52*H,
                                          'run_arrest_rail_above_floor_m': X(P(fr, RUN, ra, math.pi, 1.0))-X(P(fr, RUN, rc, psi, 1.0))}
        require(all(x['rungs'] >= 1 for x in legs) and len([x for x in legs if x['slope_deg'] > steep]) == len(thrust['AB'[j-1]+str(k)]['steep_legs']),
                f"Ring {'AB'[j-1]}: a crew-tube leg steeper than {steep} deg has no floor ladder")
    ec = elbow_climber(s); efr = ec['frame']; rc = crew_transfer.tube_radii(s, h['tube_rotors'][0])[1]; j0 = h['tube_rotors'][0]
    mine = [q for q in spoke_fixtures(s, j0) if q['name'].startswith(f"Crew_Tube_{j0}_{ec['sector']}_")]
    held = {q['name'] for q in mine if q['name'].startswith(f"Crew_Tube_{j0}_{ec['sector']}_Floor_Ladder_{ec['leg']}_")}
    ebody = [(n, p, r_) for n, p, r_ in ec['local'] if 'Arm' not in n and 'Arrester' not in n]
    epts = [(crew_transfer.add(ps[0], crew_transfer.sub(ps[1], ps[0]), i/8), r_) for _, ps, r_ in ebody for i in range(9)]
    free = [q for q in mine if q['name'] not in held]
    q47['elbow_climber'] = {'sector': ec['sector'], 'leg': ec['leg'], 'reach_m': ec['reach'], 'arrester_link_m': ec['link_m'],
                            'bore_margin_m': min(rc-crew_transfer.tube_radius_at(efr, p)-r_ for p, r_ in epts),
                            'fixture_gap_m': min(min(min(crew_transfer.seg_dist(p, *ps)-r_ for _, ps, r_ in ebody) for q in free for p in fixture_points(None, q)),
                                                 min(fixture_distance(None, q, p)-r_ for q in free for p, r_ in epts)),
                            'grip_on_stile_m': max(min(fixture_distance(None, q, g) for q in mine if q['name'] in held and '_Stile_' in q['name']) for g in ec['grips'])}
    S = thrust_step(s); ts = thrust_stepper(s); m_off = h['mannequin']['spoke_body_offset_m']; lf = landing_fixtures(s)
    held = {'Sector_Ladder_Stile_1', 'Sector_Ladder_Stile_2', 'Sector_Thrust_Step_Rungs', 'Sector_Thrust_Step_Stile_1', 'Sector_Thrust_Step_Stile_2'}
    tbody = [(n, p, r_) for n, p, r_ in ts['local'] if 'Arm' not in n]; tpts = [(crew_transfer.add(ps[0], crew_transfer.sub(ps[1], ps[0]), i/8), r_) for _, ps, r_ in tbody for i in range(9)]
    box_gap = lambda b, p: math.sqrt(sum(max(b['min'][a]-p[a], 0.0, p[a]-b['max'][a])**2 for a in range(3)))
    q47['sector_step'] = {'floor_x_m': S['floor'], 'rungs_above_floor_m': [x-S['floor'] for x in S['rungs']], 'sill_above_floor_m': S['sill']-S['floor'],
                          'sill_above_top_rung_m': S['sill']-S['rungs'][-1], 'stepper_reach_m': ts['reach'],
                          # Room above the top step to the nearest block standing over the step's column (with aft down), per sector function.
                          'headroom_above_top_step_m': {fn: min([b['min'][0] for b in habitat_interior.zones(s, fn) if b['min'][0] > S['rungs'][-1]
                                                                 and b['min'][1] < S['y']+m_off+.2 and b['max'][1] > S['y'] and b['min'][2] < S['z']+.3 and b['max'][2] > S['z']-.3]
                                                                + [-S['floor']])-S['rungs'][-1]-h['handrail_radius_m'] for fn in s['habitat']['layout']['functions']},
                          'stepper_block_gap_m': min(box_gap(b, p)-r_ for fn in s['habitat']['layout']['functions'] for b in habitat_interior.zones(s, fn) for p, r_ in tpts),
                          'stepper_fixture_gap_m': min(fixture_distance(None, q, p)-r_ for q in lf if q['name'] not in held for p, r_ in tpts),
                          'grip_on_stile_m': max(min(fixture_distance(None, q, g) for q in lf if q['name'].startswith('Sector_Ladder_Stile')) for g in ts['grips'])}
    for j in h['vestibule_rotors']:
        rot, v, la = vestibule_station(s, j); vf = vestibule_fixtures(s, j); rails = [q for q in vf if q['role'] == 'crawl rail (aft down)']
        arc = sum(crew_transfer.length(q['points']) for q in rails); rr = rails[0]['points'][0]; rr = math.hypot(rr[1], rr[2])
        q47['vestibules']['AB'[j-1]] = {'clear_length_m': v['cu1']-v['cu0']-2*h['chamber_wall_m'], 'clear_depth_m': v['clear']-v['r0'],
                                        'crawl_rail_above_floor_m': h['crawl_rail_height_m'], 'crawl_rail_m': arc,
                                        'bare_beside_each_opening_m': (2*math.pi*rr-arc)/len(rails)}
    ec_, st_ = q47['elbow_climber'], q47['sector_step']
    require(ec_['bore_margin_m'] >= 0.0 and ec_['fixture_gap_m'] >= .02 and ec_['grip_on_stile_m'] <= .01 and all(x <= reach+tol for x in ec['reach'].values()),
            f"Elbow climber: bore {ec_['bore_margin_m']:.3f}, fixture gap {ec_['fixture_gap_m']:.3f}, grip {ec_['grip_on_stile_m']:.3f}, reach {ec['reach']}")
    require(st_['stepper_block_gap_m'] >= 0.0 and st_['stepper_fixture_gap_m'] >= .02 and st_['grip_on_stile_m'] <= .01 and all(x <= reach+tol for x in ts['reach'].values()),
            f"Hatch stepper: block gap {st_['stepper_block_gap_m']:.3f}, fixture gap {st_['stepper_fixture_gap_m']:.3f}, grip {st_['grip_on_stile_m']:.3f}, reach {ts['reach']}")
    lad, cl = row['ladder'], row['climber']
    require(lad['reaches_floor'] and lad['first_rung_above_floor_m'] <= h['spoke_rung_pitch_m'], 'The trunk ladder does not start at the trunk floor')
    require(all(p['near_stile_gap_m'] is None or p['near_stile_gap_m'] >= 0.0 for p in side.values() if p['served']), f"A trunk ladder stile crosses a branch mouth: {side}")
    require(all(p['sill_above_rung_m'] <= h['spoke_rung_pitch_m'] for p in side.values() if p['served']), 'A port sill the ladder passes has no rung below it')
    require(cl['body_max_radius_m'] <= tr and cl['fixture_gap_m'] >= .02 and cl['grip_on_stile_m'] <= .01,
            f"Trunk climber: radius {cl['body_max_radius_m']:.3f}, fixture gap {cl['fixture_gap_m']:.3f}, grip {cl['grip_on_stile_m']:.3f}")
    require(all(x <= reach+tol for x in tc['reach'].values()) and cl['refuge_rim_from_shoulder_m'] <= reach,
            f"Trunk climber reach {tc['reach']}, refuge port rim {cl['refuge_rim_from_shoulder_m']:.2f} m")
    rings = ['vestibule'+ring_tag(s, j) for j in h['vestibule_rotors']]; spokes = ['spoke'+ring_tag(s, j) for j in h['tube_rotors']]
    return dict(passed=not failures, failures=failures, ports={k: v for k, v in rows.items() if k not in ('trunk', 'landing', 'refuge', 'induction', *rings, *spokes)}, trunk=rows['trunk'],
                **{k: rows[k] for k in rings+spokes}, landing=rows['landing'], refuge=rows['refuge'], induction=rows['induction'])


if __name__ == '__main__':
    import spec
    data, _, _, _ = spec.load()
    out = check(data)
    OUTPUT.write_text(json.dumps(out, indent=1, default=float)+'\n')
    print('WF_HUMAN_ENTRY', 'PASS' if out['passed'] else 'FAIL', OUTPUT)
    for f in out['failures']:
        print(' ', f)
