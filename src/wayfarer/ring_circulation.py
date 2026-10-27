"""Continuous ring circulation (CIRC-001, owner design direction 2026-10-26): a walking circuit round the whole circumference of each habitat
ring that keeps every sector an independently closable compartment (PROTOTYPE, standard library only).

Each ring has three pressurized sectors on 120 deg and three fills between them (habitat_ring). The circuit joins them with:
- a tangential through-passage in every sector, the axial band passage_x_m just forward of the aft couch row, from side wall to side wall,
  crossing the axial aisle (the interior blocks keep out of it: interior.layouts);
- a sliding pressure door in each sector side wall at that band (seated on the frame, leaf parked in a pocket in the fill's flank frame);
- a pressurized walking corridor in each fill, from the side wall of one sector to the side wall of the next, through framed openings in the
  web frames, split into two compartments by a pressure bulkhead with a door at the structural spoke node half way.
The corridor floor is the cylinder through the sector deck plate's edge (floor / cos(arc/2)), so the threshold is flush and the corridor is
level in spin gravity. Its axis is the door band's centre, aft of the ring plane (the berths and the landing well hold the forward band).

The design is a response to a new requirement, not a free improvement: it conflicts with the BASELINE rule that pressurized rooms occupy only
the sectors (12_HABITAT_LAYOUT A13) and roughly doubles the gross pressurized volume against the BASELINE 400-460 m3 envelope; budget() gives the
consequences and conflicts() the owner rows they touch. Nothing here changes canon; every number under [ring_circulation] is PROTOTYPE.

Frames: ring-local as habitat_ring (origin on the rotor centre, u along +X, angle t about +X from +Y, r from the axis); sector frame as
habitat_interior (+X axial, +Y radially outward, +Z tangential = increasing t). at_index maps both to the vehicle frame at the index pose
(ring-frame coordinates, the frame the crew physics stages use).

    python3 src/wayfarer/ring_circulation.py      # fit screen: writes references/p1_ring_circulation.json and RING_CIRCULATION_PLAN.svg
"""
import json
import math
from pathlib import Path
import habitat_ring

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'references/p1_ring_circulation.json'
PLAN = ROOT/'references/RING_CIRCULATION_PLAN.svg'
STEP_DEG = 2.0       # IMPLEMENTATION: chord step of the corridor colliders and meshes (sagitta 4 mm at r 28 m)
GAS_R = 8.314462618  # J/(mol K)


def p(s):
    return s['ring_circulation']


# ---------- frames ----------------------------------------------------------------------------------------------------------------------------

def radial(u, r, t):
    return (u, r*math.cos(t), r*math.sin(t))


def sector_to_ring(s, a, q):
    """Ring-local point of sector-frame point q in the sector at ring-local angle a."""
    x, y, z = q; R = habitat_ring.floor(s)+y
    return (x, R*math.cos(a)-z*math.sin(a), R*math.sin(a)+z*math.cos(a))


def sector_dir(a, d):
    x, y, z = d
    return (x, y*math.cos(a)-z*math.sin(a), y*math.sin(a)+z*math.cos(a))


def rotor(s, j):
    import rotor_interface
    return next(r for r in rotor_interface.rotors(s) if r['index'] == j)


def at_index(s, j, q, point=True):
    """Ring-local point (or direction) of ring j -> vehicle frame at the index pose (human_entry.at_index)."""
    import crew_transfer
    rot = rotor(s, j)
    return crew_transfer.to_world(q, rot['x'] if point else 0.0, rot['phase'])


# ---------- derived stations ---------------------------------------------------------------------------------------------------------------------

def half_arc(s):
    return habitat_ring.sector_arc(s)/2


def floor_r(s):
    """Corridor floor radius: where the sector's flat deck plate meets its side wall plane (flush threshold)."""
    return habitat_ring.floor(s)/math.cos(half_arc(s))


def section(s):
    """Corridor and door section (ring-local u and r): clear passage, door opening, the pressure liner's cavity and the tunnel cut in the fill."""
    c = p(s); x0, x1 = c['passage_x_m']; uc = (x0+x1)/2; w = c['corridor_clear_width_m']/2
    rf = floor_r(s); rc = rf-c['corridor_clear_height_m']
    cav = (uc-w, uc+w, rc-c['overhead_m'], rf+c['deck_m']+c['subfloor_m'])
    t = c['liner_m']+c['tunnel_margin_m']
    return dict(u_centre=uc, clear_u=(uc-w, uc+w), floor_r=rf, ceiling_r=rc, door_u=(x0, x1), door_top_r=rf-c['door_clear_height_m'],
                door_width=x1-x0, door_height=c['door_clear_height_m'], cavity=cav,
                tunnel=(cav[0]-t, cav[1]+t, cav[2]-t, cav[3]+t))


def fills(s, j):
    """The fills of ring j in ring-local angles: from sector k's +z side wall (t0) to sector k+1's -z side wall (t1), the structural spoke node
    half way (tn) and the web-frame joints between."""
    h = half_arc(s); angles = habitat_ring.sector_angles(s); n = len(angles); out = []
    for k in range(n):
        t0 = angles[k]+h; t1 = angles[k]+math.tau/n-h
        out.append(dict(ring=j, fill=k+1, from_sector=k+1, to_sector=(k+1) % n+1, t0=t0, t1=t1, tn=(t0+t1)/2,
                        joints=habitat_ring.joints(s, t0, t1)))
    return out


def door_depths(s):
    """Angular half-depths (rad at the floor radius) of the door passages: through the sector skin and the fill's flank frame; through the node
    bulkhead."""
    rf = floor_r(s); hr = s['habitat_ring']
    return dict(side=(hr['sector_skin_m']/rf, hr['construction']['flank_m']/rf), node=p(s)['node_bulkhead_m']/2/rf)


def segments(s, j):
    """The walking volumes of ring j's fills in order round the ring, each (fill, kind, t0, t1, u0, u1, r_top, r_floor): door passages
    (kind 'door', door section) and corridor runs (kind 'corridor', clear section). t is ring-local and increases round the ring."""
    sec = section(s); d = door_depths(s); out = []
    for f in fills(s, j):
        door = dict(u=sec['door_u'], r=(sec['door_top_r'], sec['floor_r']))
        run = dict(u=sec['clear_u'], r=(sec['ceiling_r'], sec['floor_r']))
        a, b, n = f['t0'], f['t1'], f['tn']
        for kind, t0, t1, q in (('door', a-d['side'][0], a+d['side'][1], door), ('corridor', a+d['side'][1], n-d['node'], run),
                                ('door', n-d['node'], n+d['node'], door), ('corridor', n+d['node'], b-d['side'][1], run),
                                ('door', b-d['side'][1], b+d['side'][0], door)):
            out.append(dict(fill=f['fill'], kind=kind, t0=t0, t1=t1, u0=q['u'][0], u1=q['u'][1], r_top=q['r'][0], r_floor=q['r'][1]))
    return out


# ---------- doors and compartments --------------------------------------------------------------------------------------------------------------

def compartments(s, j):
    """Pressure compartments of ring j: the sectors and two corridor halves per fill (split at the spoke-node bulkhead)."""
    out = []
    for q in habitat_ring.sectors(s):
        if q['ring'] == j:
            out.append(dict(id=f"{'AB'[j-1]}{q['index']}", kind='sector', name=q['name'], function=q['function'], gross_m3=q['gross_m3']))
    for f in fills(s, j):
        for half, (t0, t1) in (('a', (f['t0'], f['tn'])), ('b', (f['tn'], f['t1']))):
            out.append(dict(id=f"{'AB'[j-1]}C{f['fill']}{half}", kind='corridor', fill=f['fill'], t0=t0, t1=t1, gross_m3=cavity_m3(s, t1-t0)))
    return out


def doors(s, j):
    """Pressure doors of ring j: one in each sector side wall at the passage band and one in each spoke-node bulkhead. Each slides axially aft into
    a pocket (leaf travel = door width + pocket margin), seats on its frame and is normally closed (PROTOTYPE). `between` names the two
    compartments in ring order (lower t first); t is the plane of the leaf (ring-local); `name` is the leaf object of the ring asset."""
    sec = section(s); c = p(s); R = 'AB'[j-1]; out = []
    travel = sec['door_width']+c['door_pocket_margin_m']
    for f in fills(s, j):
        k, k2 = f['from_sector'], f['to_sector']
        for kind, t, sector, side, comp in (('sector', f['t0'], k, 1, f"{R}C{f['fill']}a"), ('node', f['tn'], None, 0, None),
                                            ('sector', f['t1'], k2, -1, f"{R}C{f['fill']}b")):
            if kind == 'sector':
                ident = f"{R}{sector}{'P' if side > 0 else 'N'}"
                between = [f'{R}{sector}', comp] if side > 0 else [comp, f'{R}{sector}']
            else:
                ident = f"{R}C{f['fill']}"
                between = [f"{R}C{f['fill']}a", f"{R}C{f['fill']}b"]
            out.append(dict(id=f'CIRC.{ident}', ring=j, kind=kind, fill=f['fill'], sector=sector, side=side, t=t, u=sec['door_u'],
                            r=(sec['door_top_r'], sec['floor_r']), width=sec['door_width'], height=sec['door_height'], between=between,
                            name=f'Ring_{j}_Circ_Door_{ident}', slide=(-1.0, 0.0, 0.0), travel=travel, normally='CLOSED'))
    return out


# ---------- volumes and budgets ----------------------------------------------------------------------------------------------------------------

def cavity_m3(s, dt):
    """Pressurized cavity (inside the liner: clear passage plus the overhead and subfloor utility zones) over dt radians."""
    u0, u1, r0, r1 = section(s)['cavity']
    return (u1-u0)*habitat_ring.annulus_area_factor(r0, r1)*dt


def corridor_m3(s, j=None):
    """Gross pressurized volume of the corridors of one ring (cavity over every fill's arc; the door passages counted as cavity too)."""
    return sum(cavity_m3(s, f['t1']-f['t0']) for f in fills(s, j or 1))


def tunnel_m3(s):
    u0, u1, r0, r1 = section(s)['tunnel']
    return (u1-u0)*habitat_ring.annulus_area_factor(r0, r1)*sum(f['t1']-f['t0'] for f in fills(s, 1))


def fill_m3(s):
    """Volume of the fills of one ring (frame axial width over the sector band, between the sectors)."""
    r = s['habitat_ring']
    return r['frame_axial_m']*habitat_ring.annulus_area_factor(r['sector_inner_radius_m'], r['sector_outer_radius_m'])*sum(f['t1']-f['t0'] for f in fills(s, 1))


def corridor_length_m(s):
    """Centreline length of one ring's corridors at the floor radius."""
    return floor_r(s)*sum(f['t1']-f['t0'] for f in fills(s, 1))


def gas_density(s):
    """Cabin gas density at the BASELINE 80 kPa, 25 % O2 / 75 % N2 dry mix and the PROTOTYPE cabin temperature."""
    a = s['habitat']['atmosphere']; m = a['o2_fraction']*0.031998+a['n2_balance_fraction']*0.028014
    return a['cabin_pressure_kpa']*1000.0*m/(GAS_R*p(s)['budget']['cabin_temperature_k'])


def sector_skin_area_m2(s):
    """Inner area of one sector's pressure envelope (outer and inner arcs, two side walls, two end walls), the comparison basis for the
    sector-equivalent areal mass."""
    r = s['habitat_ring']; a = habitat_ring.sector_arc(s); r0, r1, L = r['sector_inner_radius_m'], r['sector_outer_radius_m'], r['sector_axial_m']
    return (r0+r1)*a*L+2*(r1-r0)*L+2*a*habitat_ring.annulus_area_factor(r0, r1)


def budget(s):
    """Consequences of the circuit for both rings (PROTOTYPE estimates against the sourced budgets; nothing is fed back into canon)."""
    b = p(s)['budget']; n = habitat_ring.ring_count(s); sec = section(s); L = corridor_length_m(s)
    u0, u1, r0, r1 = sec['cavity']; perim = 2*((u1-u0)+(r1-r0))
    vol_ring = corridor_m3(s); vol = n*vol_ring; sectors = habitat_ring.gross_total(s); env = s['habitat']['volume']
    liner = n*perim*L*b['liner_areal_kg_m2']; deck = n*(sec['clear_u'][1]-sec['clear_u'][0])*L*b['deck_areal_kg_m2']
    ndoors = n*len(doors(s, 1)); door = ndoors*b['door_kg']; fit = n*L*b['fitout_kg_per_m']; mass = liner+deck+door+fit
    sector_areal = s['physics']['mass_budget']['items'][[i['id'] for i in s['physics']['mass_budget']['items']].index('habitat_pressure_structure')]['rotating_allowance_kg']\
        / (len(habitat_ring.sectors(s))*sector_skin_area_m2(s))
    rot = s['physics']['rotor_sizing']['mass_kg']; dyn = habitat_ring.dynamics(s); f = mass/rot
    rho = gas_density(s); comp = compartments(s, 1)
    return {'rings': n, 'corridor_length_per_ring_m': L, 'corridor_gross_per_ring_m3': vol_ring, 'corridor_gross_m3': vol,
            'sector_gross_m3': sectors, 'total_gross_m3': sectors+vol, 'baseline_gross_m3': [env['gross_min_m3'], env['gross_max_m3']],
            'gross_over_baseline_max': (sectors+vol)/env['gross_max_m3'],
            'atmosphere_kg': vol*rho, 'gas_density_kg_m3': rho,
            'largest_corridor_compartment_m3': max(q['gross_m3'] for q in comp if q['kind'] == 'corridor'),
            'doors': ndoors, 'compartments_per_ring': len(comp),
            'mass_kg': {'liner': liner, 'deck': deck, 'doors': door, 'fitout': fit, 'total': mass},
            'mass_fraction_of_rotating': f, 'rotating_budget_kg': rot,
            'sector_equivalent_areal_kg_m2': sector_areal, 'sector_equivalent_mass_kg': n*perim*L*sector_areal,
            'spoke_axial_load_increase_N': habitat_ring.spoke_axial_load_N(s)*f,
            'spin_energy_increase_J': 0.5*mass*(habitat_ring.omega(s)*(sec['cavity'][2]+sec['cavity'][3])/2)**2,
            'fill_m3_per_ring': fill_m3(s), 'tunnel_m3_per_ring': tunnel_m3(s),
            'fill_remaining_m3_per_ring': fill_m3(s)-tunnel_m3(s),
            'rotating_water_m3_per_ring': habitat_ring.water_item(s)['rotating_allowance_kg']/1000.0/n,
            'basis': 'liner = cavity perimeter x centreline length x PROTOTYPE areal mass (an internal shell shielded by the fill: no MMOD or exterior '
                     'thermal layer); the sector-equivalent figure applies the habitat_pressure_structure allowance per sector skin area as an upper '
                     'comparison; spin energy and spoke load scale with the added mass at the corridor radius (ring-equivalent dynamics)'}


def conflicts(s):
    """Owner rows the circuit touches (reported, never resolved here)."""
    b = budget(s)
    return [
        dict(id='CIRC-C1', ref='12_HABITAT_LAYOUT!A13 ring_shielding (BASELINE)', status='CONFLICT',
             text=f"Pressurized rooms occupy only the sectors; the circuit adds {b['corridor_gross_per_ring_m3']:.0f} m3 of pressurized corridor per ring "
                  f"inside the fills (tunnel {b['tunnel_m3_per_ring']:.0f} m3 of the {b['fill_m3_per_ring']:.0f} m3 fill)."),
        dict(id='CIRC-C2', ref='habitat.volume 400-460 m3 gross (BASELINE, 02/12)', status='CONFLICT',
             text=f"Gross pressurized volume {b['sector_gross_m3']:.0f} -> {b['total_gross_m3']:.0f} m3 "
                  f"({b['gross_over_baseline_max']:.2f} x the 460 m3 maximum); atmosphere +{b['atmosphere_kg']:.0f} kg; leak, repressurization "
                  "gas and ECLSS circulation OPEN."),
        dict(id='CIRC-C3', ref='physics.rotor_sizing 330 t rotating (PROVISIONAL, Q32)', status='CONFLICT',
             text=f"Corridor liner, decks, {b['doors']} doors and fit-out ~{b['mass_kg']['total']/1000:.1f} t "
                  f"({100*b['mass_fraction_of_rotating']:.1f} % of the rotating allowance, unbudgeted; "
                  f"{b['sector_equivalent_mass_kg']/1000:.0f} t at the sectors' areal mass); spoke load and spin energy scale with it."),
        dict(id='CIRC-C4', ref='12_HABITAT_LAYOUT!A5 seraph_volume (BASELINE), A29 Q51 (ACCEPTED, dimensions OPEN)', status='CHANGED PROTOTYPE',
             text="The habitation sector's -z aft slot that held Seraph's niche is the only band reaching that side wall; the niche moves to a reserved "
                  "alcove at the corridor side of that door, still beside the berths (outside the sector boundary). Owner to confirm."),
        dict(id='CIRC-C5', ref='12_HABITAT_LAYOUT!A21 full_thrust_route (BASELINE, Q47)', status='NOT AN ESSENTIAL ROUTE',
             text="Aft down (rings stopped) a corridor is a 0.9 m high tunnel; the essential 1.5 g route stays the crew tubes and the spine."),
        dict(id='CIRC-C6', ref='14_HULL_SERVICE!A8 dock_config (BASELINE)', status='OPERATIONAL CONSEQUENCE',
             text='Docked, the rings are stopped and locked: a ring walk from the station needs UNDOCK, spin-up, then spin-down, lock and DOCK.'),
        dict(id='CIRC-C7', ref='habitat_ring.construction / OD-016 ring section (OPEN)', status='OPEN',
             text='Each web frame takes a framed portal round the corridor and the spoke-node housing splits round it; the load path is OPEN (FEA).'),
        dict(id='CIRC-C8', ref='interior.layouts (PROTOTYPE), Q50 Garden trays (12!A28 WORKING)', status='CHANGED PROTOTYPE',
             text='Work and Garden couch-2 lockers end at x -1.15 m like the habitation ones; the Garden rack and mess start at x -0.50 m '
                  '(rack 0.05 m shorter).'),
    ]


# ---------- circuit and colliders (rig) --------------------------------------------------------------------------------------------------------

def sector_wall_half(s, y):
    import habitat_interior
    return habitat_interior.wall_half_width(s, y)-s['habitat_ring']['sector_skin_m']


def circuit(s, j):
    """The walking centreline of ring j at the deck, ring-local, closed: across every sector on its through-passage (the -z door, the aisle,
    the +z door) and along every corridor at its centre. Points every STEP_DEG in the corridors."""
    sec = section(s); x = sec['u_centre']; rf = sec['floor_r']; out = []
    angles = habitat_ring.sector_angles(s)
    for k, f in enumerate(fills(s, j)):
        a = angles[k]; w = sector_wall_half(s, 0.0)
        out += [sector_to_ring(s, a, (x, 0.0, -w)), sector_to_ring(s, a, (x, 0.0, 0.0)), sector_to_ring(s, a, (x, 0.0, w))]
        n = max(1, math.ceil(math.degrees(f['t1']-f['t0'])/STEP_DEG))
        out += [radial(x, rf, f['t0']+(f['t1']-f['t0'])*i/n) for i in range(n+1)]
    return out


def _arc(t0, t1):
    n = max(1, math.ceil(math.degrees(t1-t0)/STEP_DEG))
    return [t0+(t1-t0)*i/n for i in range(n+1)]


def corridor_quads(s, j):
    """Collider surfaces of ring j's corridors, ring-local quads on the clear surfaces (Godot builds them as a two-sided trimesh): floor,
    ceiling and both walls of every segment, and the step faces where a corridor run meets a narrower door passage."""
    out = []
    for g in segments(s, j):
        ts = _arc(g['t0'], g['t1'])
        for a, b in zip(ts, ts[1:]):
            for r, part in ((g['r_floor'], 'floor'), (g['r_top'], 'ceiling')):
                out.append((part, [radial(g['u0'], r, a), radial(g['u1'], r, a), radial(g['u1'], r, b), radial(g['u0'], r, b)]))
            for u in (g['u0'], g['u1']):
                out.append(('wall', [radial(u, g['r_top'], a), radial(u, g['r_floor'], a), radial(u, g['r_floor'], b), radial(u, g['r_top'], b)]))
    sec = section(s); (cu0, cu1), (du0, du1) = sec['clear_u'], sec['door_u']; rf, rc, rd = sec['floor_r'], sec['ceiling_r'], sec['door_top_r']
    for g in segments(s, j):
        if g['kind'] != 'corridor':
            continue
        for t in (g['t0'], g['t1']):
            for u0, u1, r0, r1 in ((cu0, du0, rc, rf), (du1, cu1, rc, rf), (du0, du1, rc, rd)):
                out.append(('step', [radial(u0, r0, t), radial(u1, r0, t), radial(u1, r1, t), radial(u0, r1, t)]))
    return out


def sector_colliders(s, j):
    """Collider boxes of every sector of ring j in the sector frame (centre, half sizes; axes = the sector frame): the deck plate, the overhead
    (open round the crew-tube hatch), the end bulkheads, the interior blocks of the sector's function and the landing chase; and the side walls
    as boxes in their own wall frame (u, in-plane radial, normal) with the door opening left out. Slabs lie outside the free space."""
    import habitat_interior
    import human_entry
    SL = 0.2; r = s['habitat_ring']; sec = habitat_interior.section(s); skin = r['sector_skin_m']; x_end = sec['length_m']/2-skin
    hx, _, hz = habitat_interior.hatch(s); hr_ = habitat_interior.hatch_opening(s)[2]
    out = []
    for q in habitat_ring.sectors(s):
        if q['ring'] != j:
            continue
        a, k, fn = q['angle'], q['index'], q['function']; boxes = []
        W = sector_wall_half(s, 0.0)+SL; c = sec['ceiling_y_m']
        boxes.append(('deck', (-x_end, 0.0, -W), (x_end, SL, W)))
        for lo, hi in (((-x_end, -W), (x_end, hz-hr_)), ((-x_end, hz+hr_), (x_end, W)), ((-x_end, hz-hr_), (hx-hr_, hz+hr_)), ((hx+hr_, hz-hr_), (x_end, hz+hr_))):
            boxes.append(('overhead', (lo[0], c-SL, lo[1]), (hi[0], c, hi[1])))
        for sx in (-1, 1):
            xa, xb = sorted((sx*x_end, sx*(x_end+SL)))
            boxes.append(('end', (xa, c-SL, -W), (xb, SL, W)))
        for b in habitat_interior.zones(s, fn):
            boxes.append((f"block {b['name']}", b['min'], b['max']))
        ch = next(f for f in human_entry.landing_fixtures(s) if f['name'] == 'Sector_Landing_Chase')
        cc, size = ch['world_centre'], ch['size']; ax = ch['axes']
        half = [sum(abs(ax[m][i])*size[m]/2 for m in range(3)) for i in range(3)]
        boxes.append(('block Sector_Landing_Chase', tuple(cc[i]-half[i] for i in range(3)), tuple(cc[i]+half[i] for i in range(3))))
        for name, lo, hi in boxes:
            out.append(dict(ring=j, sector=k, part=name, frame='sector', angle=a, centre=[(lo[i]+hi[i])/2 for i in range(3)],
                            half=[(hi[i]-lo[i])/2 for i in range(3)]))
        # side walls: the planes of the skin's inner faces (habitat_ring.cavity_section), door opening cut out
        d = section(s); (du0, du1) = d['door_u']; rf, rd = d['floor_r'], d['door_top_r']; r0, r1 = r['sector_inner_radius_m'], r['sector_outer_radius_m']
        for side in (-1, 1):
            t = a+side*half_arc(s)
            pieces = [(-x_end, du0, r0, r1), (du1, x_end, r0, r1), (du0, du1, r0, rd)]
            for u0, u1, ra, rb in pieces:
                out.append(dict(ring=j, sector=k, part=f"side wall {'+' if side > 0 else '-'}", frame='wall', angle=t, side=side,
                                u=[u0, u1], r=[ra, rb], skin=skin, thickness=SL))
    return out


def _box_world(s, j, q):
    """Vehicle-frame centre, axes and half sizes of a sector_colliders record (at the index pose)."""
    if q['frame'] == 'sector':
        a = q['angle']; c = sector_to_ring(s, a, q['centre'])
        axes = [sector_dir(a, (1.0, 0.0, 0.0)), sector_dir(a, (0.0, 1.0, 0.0)), sector_dir(a, (0.0, 0.0, 1.0))]
        half = q['half']
    else:
        t, side = q['angle'], q['side']; n = (0.0, -math.sin(t), math.cos(t)); er = (0.0, math.cos(t), math.sin(t))
        # the wall's inner face lies skin inside the envelope plane (toward the sector); the slab lies outside that face
        off = side*(-q['skin']+q['thickness']/2); um, rm = sum(q['u'])/2, sum(q['r'])/2
        c = tuple(um*(1.0 if i == 0 else 0.0)+rm*er[i]+off*n[i] for i in range(3))
        axes = [(1.0, 0.0, 0.0), er, n]; half = [(q['u'][1]-q['u'][0])/2, (q['r'][1]-q['r'][0])/2, q['thickness']/2]
    return at_index(s, j, c), [at_index(s, j, x, False) for x in axes], half


def landing_exit(s, j):
    """From the foot of ring j's crew-tube ladder (the landing well) straight out onto the through-passage at the same tangential station:
    the well's open side faces the passage, its chase closes the other (human_entry.landing). Deck points, vehicle frame at the index pose."""
    import human_entry
    L = human_entry.landing(s); k = s['human_entry']['vestibule_port_sectors'][j-1]; a = habitat_ring.sector_angles(s)[k-1]
    return [at_index(s, j, sector_to_ring(s, a, (x, 0.0, L['z']))) for x in (L['x'], section(s)['u_centre'])]


def stage(s, j):
    """The rig's circulation stage of ring j (RING frame, vehicle frame at the index pose = ring-frame coordinates)."""
    import crew_dynamics
    boxes = []
    for q in sector_colliders(s, j):
        c, axes, half = _box_world(s, j, q)
        boxes.append({'part': q['part'], 'sector': q['sector'], 'centre_m': list(c), 'axes': [list(x) for x in axes], 'half_m': list(half)})
    rot = rotor(s, j)
    segs = [{'fill': g['fill'], 'kind': g['kind'], 't_rad': [g['t0'], g['t1']], 'u_m': [g['u0'], g['u1']], 'r_m': [g['r_top'], g['r_floor']]}
            for g in segments(s, j)]
    ds = []
    for d in doors(s, j):
        t = d['t']; um = sum(d['u'])/2; rm = sum(d['r'])/2; n = (0.0, -math.sin(t), math.cos(t)); er = (0.0, math.cos(t), math.sin(t))
        ds.append({'id': d['id'], 'kind': d['kind'], 'fill': d['fill'], 'sector': d['sector'], 'between': d['between'], 'name': d['name'],
                   'centre_m': list(at_index(s, j, (um, rm*er[1], rm*er[2]))), 'axes': [list(at_index(s, j, x, False)) for x in ((1.0, 0.0, 0.0), er, n)],
                   'half_m': [d['width']/2, d['height']/2, p(s)['door_leaf_m']/2], 'slide': list(d['slide']), 'travel_m': d['travel'],
                   'width_m': d['width'], 'height_m': d['height'], 'normally': d['normally']})
    pts = [list(at_index(s, j, q)) for q in circuit(s, j)]
    sec = section(s); prof = crew_dynamics.profiles(s)['human_iva']
    return {'frame': 'RING', 'ring': j-1, 'zone': f"RING_{'AB'[j-1]}", 'boxes': boxes, 'segments': segs, 'doors': ds,
            'centre_x_m': rot['x'], 'phase_rad': rot['phase'], 'step_deg': STEP_DEG,
            'compartments': compartments(s, j), 'circuit_m': pts, 'circuit_length_m': sum(math.dist(a, b) for a, b in zip(pts, pts[1:]+pts[:1])),
            'floor_radius_m': sec['floor_r'], 'clear_height_m': p(s)['corridor_clear_height_m'], 'door_clear_m': [sec['door_width'], sec['door_height']],
            'landing_sector': s['human_entry']['vestibule_port_sectors'][j-1], 'body_radius_m': prof['radius_m'],
            'landing_m': [list(q) for q in landing_exit(s, j)],
            'source': 'ring_circulation (CIRC-001 owner direction 2026-10-26)', 'status': 'PROTOTYPE geometry',
            'note': 'boxes: sector deck, overhead, end bulkheads, interior blocks, landing chase, side walls with the door openings (vehicle frame at the '
                    'index). segments: the corridor walking volumes in ring-local cylinder coordinates (u along +X from centre_x_m, r from the axis, t '
                    'about +X from +Y; vehicle angle = t + phase_rad); their clear surfaces are the colliders, chorded every step_deg, with a step face where '
                    'a corridor run meets a narrower door passage. doors: closed-leaf colliders (the leaf slides along slide x travel when open). '
                    'Shirt-sleeve only (suited crew use the tubes).'}


# ---------- display geometry (the generators build these; ring-local, or sector frame where named) ------------------------------------------

def liner(s, j, fill):
    """The corridor's visible clear surfaces of one fill as one mesh, faces wound toward the walker (seen from inside only): vertices, faces and
    a class per face (floor, ceiling, wall, step)."""
    vs, fs, cls = [], [], []
    for g in [g for g in segments(s, j) if g['fill'] == fill]:
        ts = _arc(g['t0'], g['t1'])
        for a, b in zip(ts, ts[1:]):
            for part, q in (('floor', [radial(g['u0'], g['r_floor'], a), radial(g['u0'], g['r_floor'], b), radial(g['u1'], g['r_floor'], b), radial(g['u1'], g['r_floor'], a)]),
                            ('ceiling', [radial(g['u0'], g['r_top'], a), radial(g['u1'], g['r_top'], a), radial(g['u1'], g['r_top'], b), radial(g['u0'], g['r_top'], b)]),
                            ('wall', [radial(g['u0'], g['r_top'], a), radial(g['u0'], g['r_top'], b), radial(g['u0'], g['r_floor'], b), radial(g['u0'], g['r_floor'], a)]),
                            ('wall', [radial(g['u1'], g['r_top'], a), radial(g['u1'], g['r_floor'], a), radial(g['u1'], g['r_floor'], b), radial(g['u1'], g['r_top'], b)])):
                fs.append(tuple(range(len(vs), len(vs)+4))); vs.extend(q); cls.append(part)
    sec = section(s); (cu0, cu1), (du0, du1) = sec['clear_u'], sec['door_u']; rf, rc, rd = sec['floor_r'], sec['ceiling_r'], sec['door_top_r']
    for g in [g for g in segments(s, j) if g['fill'] == fill and g['kind'] == 'corridor']:
        for t, sgn in ((g['t0'], 1), (g['t1'], -1)):
            for u0, u1, r0, r1 in ((cu0, du0, rc, rf), (du1, cu1, rc, rf), (du0, du1, rc, rd)):
                q = [radial(u0, r0, t), radial(u1, r0, t), radial(u1, r1, t), radial(u0, r1, t)]
                fs.append(tuple(range(len(vs), len(vs)+4)) if sgn < 0 else tuple(reversed(range(len(vs), len(vs)+4)))); vs.extend(q); cls.append('step')
    return vs, fs, cls


def portals(s, j):
    """Pressure portals of ring j round each door opening: the plates filling the tunnel cross-section outside the opening, through the sector
    side walls' flank frames and the spoke-node bulkheads; (fill, kind, u0, u1, r0, r1, t0, t1) ring solids."""
    sec = section(s); tu0, tu1, tr0, tr1 = sec['tunnel']; (du0, du1), rf, rd = sec['door_u'], sec['floor_r'], sec['door_top_r']; out = []
    span = {f['fill']: (f['t0'], f['t1']) for f in fills(s, j)}
    for g in segments(s, j):
        if g['kind'] != 'door':
            continue
        t0, t1 = max(g['t0'], span[g['fill']][0]), min(g['t1'], span[g['fill']][1])     # the sector skin holds the rest of the passage
        for u0, u1, r0, r1 in ((tu0, du0, tr0, tr1), (du1, tu1, tr0, tr1), (du0, du1, tr0, rd), (du0, du1, rf, tr1)):
            out.append(dict(fill=g['fill'], u0=u0, u1=u1, r0=r0, r1=r1, t0=t0, t1=t1))
    return out


def leaf(s, d):
    """Closed leaf of door d as a ring solid (u0, u1, r0, r1, t0, t1): the opening plus one jamb width round it, the door leaf's thickness on the
    corridor side of the door plane (a sector door) or centred (a node door)."""
    c = p(s); rf = floor_r(s); dt = c['door_leaf_m']/rf; jm = c['door_jamb_m']
    if d['kind'] == 'sector':
        t0, t1 = (d['t'], d['t']+dt) if d['side'] > 0 else (d['t']-dt, d['t'])
    else:
        t0, t1 = d['t']-dt/2, d['t']+dt/2
    return (d['u'][0]-jm, d['u'][1]+jm, d['r'][0]-jm, d['r'][1], t0, t1)


def fitout(s, j, fill):
    """The corridor's fit-out in the interior design language of the sectors (route_fitout scheme A): ring solids (u0, u1, r0, r1, t0, t1)
    per class: 'frame' ribs across the walls and ceiling every sector_frame_pitch_m (the overhead frame rhythm), the blue 'band' along the
    floor by the forward wall (the route band), and 'safety' trims round both faces of every door opening. Depiction only, PROTOTYPE."""
    sec = section(s); (cu0, cu1), (du0, du1) = sec['clear_u'], sec['door_u']; rf, rc, rd = sec['floor_r'], sec['ceiling_r'], sec['door_top_r']
    pitch = s['route_fitout']['sector_frame_pitch_m']; rib, depth, trim = 0.06, 0.01, 0.05     # flush strips: the clear section stays clear
    out = {'frame': [], 'band': [], 'safety': []}
    for g in [g for g in segments(s, j) if g['fill'] == fill]:
        if g['kind'] == 'corridor':
            L = (g['t1']-g['t0'])*rf; n = int(L/pitch)
            for i in range(1, n):
                t = g['t0']+(g['t1']-g['t0'])*i/n; w = rib/2/rf
                out['frame'] += [(cu0, cu0+depth, rc, rf-0.10, t-w, t+w), (cu1-depth, cu1, rc, rf-0.10, t-w, t+w), (cu0, cu1, rc, rc+depth, t-w, t+w)]
            ts = _arc(g['t0'], g['t1'])     # at the liner's floor stations, so the band lies on its chords
            out['band'] += [(cu1-0.22, cu1-0.10, rf-0.010, rf-0.005, a, b) for a, b in zip(ts, ts[1:])]
        else:
            for t, sgn in ((g['t0'], -1.0), (g['t1'], 1.0)):
                a, b = sorted((t, t+sgn*0.012/rf))
                out['safety'] += [(du0-trim, du0, rd-trim, rf, a, b), (du1, du1+trim, rd-trim, rf, a, b), (du0-trim, du1+trim, rd-trim, rd, a, b)]
    return out


SILL_CUT_M = 0.3     # IMPLEMENTATION: the wall cut runs this far below the sill into the subfloor, where the portal plate closes it


def sector_door_opening_m3(s):
    """Skin volume the two side-wall openings remove from WF_RING_SECTOR (width x cut height x skin; the wall is a radial plane)."""
    sec = section(s)
    return 2*sec['door_width']*(sec['floor_r']+SILL_CUT_M-sec['door_top_r'])*s['habitat_ring']['sector_skin_m']


def sector_door_cutters(s):
    """The side-wall openings of WF_RING_SECTOR (the same in every sector) as closed boxes in the sector frame: 8 corners each, ordered
    (u, radial, normal) low/high, through the skin."""
    sec = section(s); (u0, u1), rf, rd = sec['door_u'], sec['floor_r'], sec['door_top_r']; out = []
    for side in (-1, 1):
        t = side*half_arc(s); er = (0.0, math.cos(t), math.sin(t)); n = (0.0, -math.sin(t), math.cos(t))
        corners = [tuple(radial(u, r, t)[i]+w*n[i]-(habitat_ring.floor(s) if i == 1 else 0.0) for i in range(3))
                   for u in (u0, u1) for r in (rd, rf+SILL_CUT_M) for w in (-0.25, 0.25)]
        out.append(corners)
    return out


# ---------- fit screen ------------------------------------------------------------------------------------------------------------------------

def _seg_box(a, b, c, axes, half, n=8):
    """Least distance from segment ab to an oriented box (sampled along the segment)."""
    best = 9e9
    for i in range(n+1):
        q = tuple(a[k]+(b[k]-a[k])*i/n-c[k] for k in range(3))
        loc = [sum(q[k]*axes[m][k] for k in range(3)) for m in range(3)]
        d = [max(abs(loc[m])-half[m], 0.0) for m in range(3)]
        inside = all(abs(loc[m]) <= half[m] for m in range(3))
        best = min(best, -min(half[m]-abs(loc[m]) for m in range(3)) if inside else math.sqrt(sum(x*x for x in d)))
    return best


def check(s):
    """Failure list: the section and doors fit, the passage band is free of every function's blocks, the tunnel stays inside the fill and clear of
    the hoops, and a standing body walks the whole circuit of both rings clear of every collider box."""
    import habitat_interior
    import crew_dynamics
    failures = []
    def need(ok, msg):
        if not ok:
            failures.append(msg)
    c, r, sec = p(s), s['habitat_ring'], section(s)
    prof = crew_dynamics.profiles(s)['human_iva']; H = s['prototype']['human_height_m']
    need(c['status'] == 'PROTOTYPE', 'ring_circulation stays PROTOTYPE')
    need(c['corridor_clear_height_m'] >= s['interior']['min_headroom_m'], 'Corridor headroom below interior.min_headroom_m')
    need(sec['door_width'] >= 2*prof['radius_m']+2*c['body_margin_m'], 'Door narrower than the body plus margins')
    need(sec['door_height'] >= H+c['body_margin_m'], 'Door lower than the human height plus margin')
    need(sec['clear_u'][0] <= sec['door_u'][0] and sec['door_u'][1] <= sec['clear_u'][1], 'Door band outside the corridor width')
    tu0, tu1, tr0, tr1 = sec['tunnel']
    need(-r['frame_axial_m']/2+r['construction']['inset_m'] < tu0 and tu1 < r['frame_axial_m']/2-r['construction']['inset_m'], 'Tunnel leaves the frame axially')
    need(r['sector_inner_radius_m'] < tr0 and tr1 < r['sector_outer_radius_m'], 'Tunnel leaves the fill band (hoops)')
    need(sec['door_top_r'] > r['sector_inner_radius_m']+r['sector_skin_m'], 'Door opening reaches the sector overhead')
    x0, x1 = c['passage_x_m']
    for fn in s['habitat']['layout']['functions']:
        for b in habitat_interior.zones(s, fn):
            if b['min'][0] < x1-1e-9 and b['max'][0] > x0+1e-9 and b['min'][1] < -0.01:
                failures.append(f'{fn}: {b["name"]} blocks the through-passage band')
    import human_entry
    L = human_entry.landing(s)
    need(L['well_x'][0] >= x1-1e-9, 'Landing well and chase reach into the through-passage band')
    for j in range(1, habitat_ring.ring_count(s)+1):
        st = stage(s, j); boxes = st['boxes']; pts = st['circuit_m']
        half_len = H/2-prof['radius_m']
        worst = 9e9
        for a, b in zip(pts, pts[1:]+pts[:1]):
            for i in range(max(1, math.ceil(math.dist(a, b)/0.25))):
                f = i/max(1, math.ceil(math.dist(a, b)/0.25)); q = tuple(a[k]+(b[k]-a[k])*f for k in range(3))
                rot = rotor(s, j); loc = tuple(q[k]-(rot['x'] if k == 0 else 0.0) for k in range(3)); rr = math.hypot(loc[1], loc[2])
                up = (0.0, -loc[1]/rr, -loc[2]/rr)
                foot = tuple(q[k]+up[k]*(prof['radius_m']+c['body_margin_m']+0.01) for k in range(3)); head = tuple(foot[k]+up[k]*2*half_len for k in range(3))
                for bx in boxes:
                    if math.dist(bx['centre_m'], q) > 4.0+max(bx['half_m']):
                        continue
                    worst = min(worst, _seg_box(foot, head, bx['centre_m'], bx['axes'], bx['half_m'])-prof['radius_m'])
        need(worst >= c['body_margin_m']-1e-6, f"Ring {'AB'[j-1]}: the body comes within {worst:.3f} m of a sector collider on the circuit")
        # the step out of the landing well onto the passage
        a_, b_ = landing_exit(s, j); rot = rotor(s, j); worst = 9e9
        for i in range(9):
            q = tuple(a_[k]+(b_[k]-a_[k])*i/8 for k in range(3)); loc = (q[0]-rot['x'], q[1], q[2]); rr = math.hypot(loc[1], loc[2]); up = (0.0, -loc[1]/rr, -loc[2]/rr)
            foot = tuple(q[k]+up[k]*(prof['radius_m']+c['body_margin_m']+0.01) for k in range(3)); head = tuple(foot[k]+up[k]*2*half_len for k in range(3))
            worst = min([worst]+[_seg_box(foot, head, bx['centre_m'], bx['axes'], bx['half_m'])-prof['radius_m'] for bx in boxes if math.dist(bx['centre_m'], q) < 6.0])
        need(worst >= c['body_margin_m']-1e-6, f"Ring {'AB'[j-1]}: the step out of the landing well comes within {worst:.3f} m of a collider")
    return failures


def plan_svg(s):
    """Whole-ring overview plan of both rings seen from aft (dorsal up): sectors, the corridor compartments in each fill, the pressure doors and the
    walking circuit, with the volumes, mass and conflicts in the caption (review drawing, not a design deliverable)."""
    b = budget(s); S = 8.6; out = []; r = s['habitat_ring']; sec = section(s); h = half_arc(s)
    def ring_path(cx, cy, r0, r1, t0, t1, n=48):
        xy = lambda rr, t: (cx-S*rr*math.cos(t), cy-S*rr*math.sin(t))      # seen from aft: dorsal (+Z) up, +Y to the left
        pts = [xy(r1, t0+(t1-t0)*i/n) for i in range(n+1)]+[xy(r0, t1-(t1-t0)*i/n) for i in range(n+1)]
        return 'M'+' L'.join(f'{x:.1f},{y:.1f}' for x, y in pts)+' Z'
    for j, cx in ((1, 350.0), (2, 1050.0)):
        cy = 330.0; ph = rotor(s, j)['phase']; R = 'AB'[j-1]
        xy = lambda rr, t, cx=cx, cy=cy: (cx-S*rr*math.cos(t), cy-S*rr*math.sin(t))
        out.append(f'<text x="{cx:.0f}" y="28" font-size="17" font-weight="bold" text-anchor="middle">Ring {R} seen from aft, dorsal up ({"+" if j == 1 else "-"}4 rpm about +X)</text>')
        out.append(f'<path d="{ring_path(cx, cy, r["frame_inner_radius_m"], habitat_ring.outer(s), 0, math.tau, 240)}" fill="#dfe6ea" stroke="#7a8a94"/>')
        for f in fills(s, j):
            for t0, t1, tone in ((f['t0'], f['tn'], '#8fcbbd'), (f['tn'], f['t1'], '#b3ded2')):
                out.append(f'<path d="{ring_path(cx, cy, sec["cavity"][2], sec["cavity"][3], t0+ph, t1+ph)}" fill="{tone}" stroke="#2f7f6f" stroke-width="0.8"/>')
            for half, (t0, t1) in (('a', (f['t0'], f['tn'])), ('b', (f['tn'], f['t1']))):
                x, y = xy(21.5, (t0+t1)/2+ph); out.append(f'<text x="{x:.0f}" y="{y:.0f}" font-size="11" fill="#1d5c50" text-anchor="middle">{R}C{f["fill"]}{half}</text>')
        for q in habitat_ring.sectors(s):
            if q['ring'] == j:
                out.append(f'<path d="{ring_path(cx, cy, r["sector_inner_radius_m"], r["sector_outer_radius_m"], q["angle"]-h+ph, q["angle"]+h+ph)}" fill="#f2c27a" stroke="#8a5a14"/>')
                x, y = xy(20.0, q['angle']+ph)
                port = q['index'] == s['human_entry']['vestibule_port_sectors'][j-1]
                out.append(f'<text x="{x:.0f}" y="{y:.0f}" font-size="12" text-anchor="middle">{R}{q["index"]} {q["function"].split("_")[0].lower()}{" (tube, landing)" if port else ""}</text>')
        for d in doors(s, j):
            x, y = xy(sec['floor_r']-1.0, d['t']+ph)
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.4" fill="{"#c0392b" if d["kind"] == "sector" else "#1f5fa8"}"/>')
        pts = [xy(math.hypot(q[1], q[2]), math.atan2(q[2], q[1])+ph) for q in circuit(s, j)]
        out.append('<polyline points="'+' '.join(f'{x:.1f},{y:.1f}' for x, y in pts+pts[:1])+'" fill="none" stroke="#123" stroke-width="1.1" stroke-dasharray="4 3"/>')
    lines = [f"CIRC-001 continuous circulation (PROTOTYPE): per ring {b['corridor_length_per_ring_m']:.0f} m of corridor in the three fills, {len(doors(s, 1))} sliding pressure doors "
             f"(red: sector side walls, blue: spoke-node bulkheads), {b['compartments_per_ring']} compartments (3 sectors, 6 corridor halves).",
             f"Corridor clear {p(s)['corridor_clear_width_m']:.2f} x {p(s)['corridor_clear_height_m']:.2f} m, level floor at r {sec['floor_r']:.3f} m (flush with the sector deck "
             f"edge); doors {sec['door_width']:.2f} x {sec['door_height']:.2f} m; through-passage in every sector at x {p(s)['passage_x_m'][0]:+.2f}..{p(s)['passage_x_m'][1]:+.2f} m.",
             f"Pressurized +{b['corridor_gross_per_ring_m3']:.0f} m3 per ring: both rings {b['sector_gross_m3']:.0f} -> {b['total_gross_m3']:.0f} m3 gross against the BASELINE "
             f"400-460 m3 (x{b['gross_over_baseline_max']:.2f}); atmosphere +{b['atmosphere_kg']:.0f} kg.",
             f"Mass ~{b['mass_kg']['total']/1000:.1f} t both rings, {100*b['mass_fraction_of_rotating']:.1f} % of the 330 t rotating allowance (unbudgeted; "
             f"{b['sector_equivalent_mass_kg']/1000:.0f} t at the sectors' areal mass). Conflicts: 12!A13, the 400-460 m3 envelope, 330 t (ring_circulation.conflicts).",
             "Shaded: corridor compartments; dashed: the walking circuit; amber: pressurized sectors; grey: frame (hoops and fills: water, storage, structure)."]
    for i, text in enumerate(lines):
        out.append(f'<text x="16" y="{680+18*i}" font-size="13">{text}</text>')
    return '<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="780" viewBox="0 0 1400 780" font-family="sans-serif"><rect width="1400" height="780" fill="white"/>'+''.join(out)+'</svg>'


def report(s):
    return {'section': section(s), 'budget': budget(s), 'conflicts': conflicts(s), 'doors': [dict(d, r=list(d['r']), u=list(d['u'])) for d in doors(s, 1)],
            'compartments': compartments(s, 1), 'circuit_length_m': {('AB'[j-1]): stage(s, j)['circuit_length_m'] for j in (1, 2)},
            'failures': check(s)}


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import spec
    sp = spec.load()[0]
    rep = report(sp)
    OUTPUT.write_text(json.dumps(rep, indent=1, default=list)+'\n')
    PLAN.write_text(plan_svg(sp))
    print(json.dumps({'failures': rep['failures'], 'budget': {k: v for k, v in rep['budget'].items() if k != 'basis'}}, indent=1, default=list))
