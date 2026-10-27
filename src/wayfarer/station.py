"""The development station's boarding area (STN-001, the owner's excursion direction of 2026-10-26): the least of the station the player's
excursion needs, docked to Wayfarer's primary boarding port, and the boarding line from the station into the crew trunk (PROTOTYPE, standard
library only).

The station is not part of Wayfarer and nothing here is canon. Its docking side follows Wayfarer's sourced interface only: the common
androgynous soft-capture standard with the 1.6 m clear passage (Q33, 14!A30, dock_clear_radius_m) on the primary port (Dock_Primary,
X 99.40 m, 195 deg), inside the 3 m docking corridor (dock_corridor_radius_m). Beyond it everything is a PROTOTYPE choice under [station]: a
docking adapter with the station's own hatch, a boarding tunnel and a boarding node, the trainee's starting area. Docked, the station and the
ship form one rigid stack in free fall: the stack's SHIP frame (zero field in DOCKED, 46 DYN-007), so the node has no floor to stand on;
handrails, a painted deck convention and lights orient the crew, who move hand over hand. While docked Wayfarer's rings are stopped and
locked (14_HULL_SERVICE!A8 BASELINE): a ring walk needs UNDOCK and spin-up first, and DOCK after spin-down (crew_dynamics.transition).

Dock-local coordinates as human_entry: a from the ship axis along the port's outward radial u, rho/phi round the port axis.

boarding_line() is the body line from the trainee's start in the node, head first down the port axis through the station hatch, Wayfarer's
outer hatch, the entry chamber and its inner hatch into the trunk node, and a pivot head-aft into the crew trunk (crew_dynamics._pivot on a
free-space model of the node, the neck and the trunk), then aft along the trunk axis to the ring B and ring A access starts. The hands move
the body along it (the M2 line technique); where no grip is in reach the body coasts.

    python3 src/wayfarer/station.py        # fit screen: references/p1_station.json
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'references/p1_station.json'


def port(s):
    import human_entry
    return human_entry.ports(s)[0]


def stations(s):
    """Dock-local stations of the boarding area (a, m from the ship axis along the port's radial), the ship side from human_entry.stations."""
    import human_entry
    f = port(s); st = human_entry.stations(s, f); c = s['station']; face = st['port_face']
    hatch = face+c['adapter_length_m']-c['hatch_frame_m']
    tunnel = face+c['adapter_length_m']; node = tunnel+c['tunnel_length_m']; end = node+c['node_length_m']
    return dict(ship=st, face=face, hatch=(hatch, hatch+c['hatch_frame_m']), tunnel=(tunnel, node), node=(node, end), start=end-c['start_from_end_m'],
                clear=st['clear'], node_r=c['node_clear_radius_m'], tunnel_r=st['clear'], wall=c['wall_m'])


def world(s, a, rho=0.0, phi=0.0):
    import human_entry
    return human_entry.world(port(s), a, rho, phi)


def bores(s):
    """The free space of the boarding area and the ship's entry as coaxial bores about the port axis, (name, a0, a1, clear radius), and the
    end annuli between them (name, a, r_in, r_out): the stage colliders (the walls lie outside these surfaces)."""
    q = stations(s); st = q['ship']; c = q['clear']
    out = [('station_node', q['node'][0], q['node'][1], q['node_r']), ('station_tunnel', q['tunnel'][0], q['tunnel'][1], c),
           ('station_adapter', q['face'], q['tunnel'][0], c), ('outer_neck', st['top'], q['face'], c),
           ('outer_frame', st['outer_frame'][0], st['top'], c), ('entry_chamber', st['a_in'], st['outer_frame'][0], st['chamber_r']),
           ('inner_frame', st['inner_frame'][0], st['a_in'], c), ('trunk_node', st['node_in'], st['inner_frame'][0], st['node_r']),
           ('inboard_neck', s['crew_transfer']['trunk_clear_radius_m']*0.5, st['node_in'], c)]
    ends = [('station_node_end', q['node'][1], 0.0, q['node_r']), ('station_node_inboard', q['node'][0], c, q['node_r']),
            ('chamber_outboard', st['outer_frame'][0], c, st['chamber_r']), ('chamber_inboard', st['a_in'], c, st['chamber_r']),
            ('node_outboard', st['inner_frame'][0], c, st['node_r']), ('node_floor', st['node_in'], c, st['node_r'])]
    return out, ends


def hatches(s):
    """The closures on the boarding line, each (id, a of its plane, kind, side it seats from, normally): the station hatch (station side), the
    ship's outer and inner hatches (ship side, the airlock pair: never both open, human_entry). Open/closed is the runtime's state."""
    q = stations(s); st = q['ship']
    return [dict(id='STATION_HATCH', a=sum(q['hatch'])/2, kind='STATION', leaf='sliding into the adapter collar', normally='CLOSED'),
            dict(id='OUTER_HATCH', a=sum(st['outer_frame'])/2, kind='AIRLOCK_OUTER', leaf='hinged, into the entry chamber (human_entry)', normally='CLOSED'),
            dict(id='INNER_HATCH', a=sum(st['inner_frame'])/2, kind='AIRLOCK_INNER', leaf='hinged, into the trunk node (human_entry)', normally='CLOSED')]


def fixtures(s):
    """Handrails (rods), light strips, the boarding panel, the start marker, the windows and the closed hatch to the station core, vehicle frame."""
    c = s['station']; q = stations(s); out = []; rr = q['node_r']-c['handrail_standoff_m']; rt = q['clear']+0.0
    for k, deg in enumerate(c['handrail_deg'], 1):
        phi = math.radians(deg)
        out.append(dict(name=f'Station_Node_Handrail_{k}', shape='rod', role='handrail', radius=c['handrail_radius_m'],
                        points=[world(s, q['node'][0]+.25, rr, phi), world(s, q['node'][1]-.25, rr, phi)]))
        out.append(dict(name=f'Station_Tunnel_Handrail_{k}', shape='rod', role='handrail', radius=c['handrail_radius_m'],
                        points=[world(s, q['tunnel'][0]+.10, rt-c['tunnel_rail_standoff_m'], phi), world(s, q['tunnel'][1]+.20, rt-c['tunnel_rail_standoff_m'], phi)]))
    # the boarding kit's straps in Wayfarer's entry chamber and trunk node (port axis, offset to clear the body; never across a hatch plane)
    st = q['ship']; g = c['strap_frame_gap_m']; phi = math.radians(c['strap_deg'])
    for name, a0, a1 in (('Chamber', st['inner_frame'][1]+g, st['outer_frame'][0]-g), ('Node', st['node_floor']+.10, st['inner_frame'][0]-g)):
        out.append(dict(name=f'Station_Boarding_Strap_{name}', shape='rod', role='boarding strap', radius=0.012,
                        points=[world(s, a0, c['strap_offset_m'], phi), world(s, a1, c['strap_offset_m'], phi)]))
    for k, deg in enumerate(c['light_deg'], 1):
        out.append(dict(name=f'Station_Node_Light_{k}', shape='box', role='light strip', a=sum(q['node'])/2, rho=q['node_r']-.02, phi=math.radians(deg),
                        size=(q['node'][1]-q['node'][0]-.6, .10, .02)))
    out.append(dict(name='Station_Boarding_Panel', shape='box', role='boarding panel: hatch status, docking state, Wayfarer link', a=q['node'][0]+.7,
                    rho=q['node_r']-.04, phi=math.radians(c['panel_deg']), size=(.6, .45, .06)))
    for k, deg in enumerate(c['window_deg'], 1):
        out.append(dict(name=f'Station_Window_{k}', shape='window', role='window toward Wayfarer (inboard end wall)', a=q['node'][0], rho=(q['clear']+q['node_r'])/2+.1,
                        phi=math.radians(deg), radius=c['window_radius_m']))
    out.append(dict(name='Station_Core_Hatch', shape='disc', role='closed hatch to the station core (not modelled)', a=q['node'][1]-.02, rho=0.0, phi=0.0,
                    radius=c['core_hatch_radius_m']))
    return out


# ---------- the boarding line ---------------------------------------------------------------------------------------------------------------

def _world_model(s):
    """Free-space model of the boarding area, the ship's entry and the trunk: clear(p) is the least clearance to the walls (the largest of the
    region clearances; a region's end wall counts only beside a narrower neighbour), vehicle frame. The trunk is a cylinder about X, the rest
    coaxial bores about the port axis (bores)."""
    import crew_transfer
    f = port(s); tr = crew_transfer.stationary(s)[0]; x0, x1 = sorted(p_[0] for p_ in tr['points']); R = tr['hollow']
    u = (0.0, math.cos(f['theta']), math.sin(f['theta'])); ox = f['x']
    regions = sorted(((a0, a1, r) for _, a0, a1, r in bores(s)[0]), key=lambda q_: q_[0])
    def clear(p_, *_):
        rho = math.hypot(p_[1], p_[2]); a = p_[1]*u[1]+p_[2]*u[2]; lat = math.sqrt(max((p_[0]-ox)**2+rho*rho-a*a, 0.0)); best = -9.0
        if x0 < p_[0] < x1:
            best = max(best, R-rho)
        for i, (a0, a1, r) in enumerate(regions):
            if a0 <= a <= a1:
                c = r-lat
                lo = regions[i-1][2] if i > 0 and abs(regions[i-1][1]-a0) < 1e-6 else (R if a0 < R+1e-6 else 0.0)
                hi = regions[i+1][2] if i+1 < len(regions) and abs(regions[i+1][0]-a1) < 1e-6 else 0.0
                if lat > lo:
                    c = min(c, a-a0)
                if lat > hi:
                    c = min(c, a1-a)
                best = max(best, c)
        return best
    return dict(clear=clear, u=u)


def boarding_line(s):
    """The body line from the station start into the trunk and aft to the access starts: poses (p, up = head direction, phase, s_m), the
    closures' blocked spans, the coasts and the junctions where the ring access lines begin (vehicle frame, SHIP frame)."""
    import crew_dynamics as cd
    import crew_transfer
    q = stations(s); st = q['ship']; f = port(s); w = _world_model(s); u = w['u']; ox = f['x']
    prof = cd.profiles(s)['human_iva']; half, radius, H = prof['height_m']/2-prof['radius_m'], prof['radius_m'], prof['height_m']
    inward = tuple(-x for x in u); aft = (-1.0, 0.0, 0.0); X = (1.0, 0.0, 0.0); stp = cd.ACCESS_GRID[0]
    # the pivot: from head-inward on the port axis in the trunk node to head-aft on the trunk axis (pose grid: centre ox + i X + j u)
    j0 = round((st['node_in']+0.10+H/2)/stp)
    turn = cd._pivot(w, (ox, 0.0, 0.0), X, u, aft, inward, (0, j0, 18), (-round(s['station']['trunk_settle_m']/stp), 0, 0), True, True, half, radius)
    c = s['station']; rail = math.radians(c['handrail_deg'][0])
    line = [dict(p=world(s, q['start'], c['start_rho_m'], rail), up=inward, phase='station'),
            dict(p=world(s, q['node'][0]+c['entry_catch_m']), up=inward, phase='station')]
    # in the entry chamber the body comes off the axis to its handrail (within reach) and back, the whole body inside the chamber
    # the stop in the entry chamber on the axis, the whole body inside it, holding the strap (the airlock cycle is worked from here)
    a_ch = st['outer_frame'][0]-H/2-c['mouth_gap_m']
    line += [dict(p=world(s, a_ch), up=inward, phase='chamber_rail'), dict(p=turn[0][0], up=turn[0][1], phase='node')]
    line += [dict(p=p_, up=v, phase='pivot') for p_, v in turn[1:]]
    tr = crew_transfer.stationary(s)[0]
    starts = {}
    for j, ring in ((2, 'RING_B'), (1, 'RING_A')):
        port_x = [p_ for p_ in crew_transfer.stationary(s) if p_['name'] == f'Crew_Port_{j}_{s["human_entry"]["vestibule_port_sectors"][j-1]}'][0]['points'][0][0]
        starts[ring] = port_x+cd.ACCESS_START_M
        line.append(dict(p=(starts[ring], 0.0, 0.0), up=aft, phase='trunk', junction=ring))
    sv = [0.0]
    for a, b in zip(line, line[1:]):
        sv.append(sv[-1]+cd._span((a['p'], a['up']), (b['p'], b['up']), H))
    for k, d in enumerate(line):
        d['s_m'] = sv[k]
    # the least clearance of the whole line against the bores, the trunk node, the neck and the trunk
    least = min(cd._segment_clear(w, (a['p'], a['up']), (b['p'], b['up']), True, True, half, radius) for a, b in zip(line, line[1:]))
    # closure spans: the line parameters over which the body crosses a hatch plane (blocked while it is not open)
    def a_of(pt):
        return (pt[1]*u[1]+pt[2]*u[2])
    spans = []
    for h in hatches(s):
        on = []
        for k in range(len(line)-1):
            A, B = line[k], line[k+1]; n = max(1, math.ceil((sv[k+1]-sv[k])/0.01))
            for i in range(n+1):
                c, v = cd._along((A['p'], A['up']), (B['p'], B['up']), i/n)
                ends = [a_of(cd.add(c, cd.mul(v, half+radius))), a_of(cd.add(c, cd.mul(v, -half-radius)))]
                lat = math.sqrt(max((c[0]-ox)**2+(c[1]**2+c[2]**2)-a_of(c)**2, 0.0))
                if min(ends) <= h['a'] <= max(ends) and lat < q['clear']:
                    on.append(sv[k]+(sv[k+1]-sv[k])*i/n)
        spans.append(dict(h, s=[min(on)-s['station']['hatch_gap_m'], max(on)+s['station']['hatch_gap_m']]))
    # grips: the station rails, the ship's chamber and node rails, the trunk's rails; coasts where none is in reach
    import human_entry
    grips = [(fx['name'], fx['points']) for fx in fixtures(s) if fx['shape'] == 'rod']
    grips += [(fx['name'], fx['points']) for fx in human_entry.fixtures(s, f) if fx['shape'] == 'rod' and fx['role'] == 'handrail']
    grips += [(fx['name'], fx['points']) for fx in human_entry.trunk_fixtures(s) if fx.get('role') in cd.TRUNK_GRIPS]
    segs = [(a, b) for _, pts in grips for a, b in zip(pts, pts[1:])]; reach = prof['reach_m']-0.01
    held = lambda c: any(cd._seg_dist(c, a, b) <= reach for a, b in segs)
    coasts = []
    for k in range(len(line)-1):
        A, B = line[k], line[k+1]; n = max(1, math.ceil((sv[k+1]-sv[k])/0.01))
        for i in range(n+1):
            if not held(cd._along((A['p'], A['up']), (B['p'], B['up']), i/n)[0]):
                sk = sv[k]+(sv[k+1]-sv[k])*i/n
                if coasts and sk-coasts[-1][1] < 0.011:
                    coasts[-1][1] = sk
                else:
                    coasts.append([sk, sk])
    return dict(line=[dict(p=list(d['p']), up=list(d['up']), phase=d['phase'], s_m=d['s_m'], **({'junction': d['junction']} if 'junction' in d else {}))
                      for d in line], hatches=spans, coasts=coasts, grips=[dict(anchor_id=n_, rail_start=list(a), rail_end=list(b), radius_m=0.0175)
                                                                            for n_, pts in grips for a, b in zip(pts, pts[1:])],
                junctions={k: v for k, v in ((d['junction'], d['s_m']) for d in line if 'junction' in d)}, least_clearance_m=least,
                margin_m=cd.ACCESS_MARGIN_M, reach_m=prof['reach_m'])


def stage(s):
    """The rig's boarding stage (SHIP frame, vehicle frame): the port axis, bores and end annuli, hatches, fixtures and the boarding line."""
    f = port(s); q = stations(s); bs, ends = bores(s); bl = boarding_line(s); c = s['station']
    return {'frame': 'SHIP', 'zone': 'boarding', 'axis': {'origin_m': [f['x'], 0.0, 0.0], 'radial': [0.0, math.cos(f['theta']), math.sin(f['theta'])],
                                                          'tangent': [0.0, -math.sin(f['theta']), math.cos(f['theta'])]},
            'bores': [{'name': n, 'a_m': [a0, a1], 'clear_radius_m': r} for n, a0, a1, r in bs],
            'ends': [{'name': n, 'a_m': a, 'r_in_m': r0, 'r_out_m': r1} for n, a, r0, r1 in ends],
            'station': {'start_a_m': q['start'], 'node_a_m': list(q['node']), 'tunnel_a_m': list(q['tunnel']), 'hatch_a_m': list(q['hatch']),
                        'node_clear_radius_m': q['node_r'], 'wall_m': q['wall'], 'standoff_m': c['undock_standoff_m'],
                        'gravity': 'microgravity: the docked stack is one rigid body in free fall (SHIP frame, zero field in DOCKED, DYN-007); no floor to '
                                   'stand on, hand-over-hand movement on handrails; the painted deck band is an orientation convention only',
                        'docked_rule': 'rings stopped and locked while docked (14_HULL_SERVICE!A8 BASELINE): UNDOCK before spin-up, DOCK after spin-down'},
            'fixtures': [dict(x, points=[list(v) for v in x['points']]) if x['shape'] == 'rod' else dict(x, size=list(x['size'])) if 'size' in x else x
                         for x in fixtures(s)],
            'hatches': bl['hatches'], 'line': bl['line'], 'coasts_s_m': bl['coasts'], 'grips': bl['grips'], 'junctions': bl['junctions'],
            'least_clearance_m': bl['least_clearance_m'], 'margin_m': bl['margin_m'], 'reach_m': bl['reach_m'],
            'source': 'station (STN-001 owner direction 2026-10-26; Q33 docking interface), human_entry.stations / fixtures, crew_transfer.stationary',
            'status': 'PROTOTYPE geometry and technique line; the station is not part of Wayfarer'}


def check(s):
    import crew_transfer
    import hull_geometry
    failures = []
    def need(ok, msg):
        if not ok:
            failures.append(msg)
    c = s['station']; q = stations(s); p = s['prototype']
    need(c['status'] == 'PROTOTYPE', 'station stays PROTOTYPE')
    need(q['node_r']+q['wall'] <= p['dock_corridor_radius_m'], 'Station node wider than the 3 m docking corridor')
    need(q['tunnel'][1] > q['tunnel'][0] and q['node'][1] > q['node'][0], 'Tunnel and node must have length')
    need(q['node'][0] < q['start'] < q['node'][1], 'Start inside the node')
    bl = boarding_line(s)
    need(bl['least_clearance_m'] >= bl['margin_m']-1e-9, f"Pivot keeps {bl['least_clearance_m']:.3f} m < {bl['margin_m']} m")
    need(len(bl['hatches']) == 3 and all(h['s'][0] < h['s'][1] for h in bl['hatches']), 'Hatch spans')
    need(set(bl['junctions']) == {'RING_A', 'RING_B'}, 'Both ring access starts on the line')
    # the station stays inside the docking corridor until clear of the ring sweep and radiators (the corridor is the keep-out, D1)
    import habitat_ring
    need(q['node'][1] < hull_geometry.inner_radius_at(s, port(s)['x'])+40.0, 'Station node within the modelled reach')
    need(port(s)['x']-p['dock_corridor_radius_m'] > habitat_ring.centers(s)[1]+habitat_ring.sweep_half(s), 'Docking corridor clear of ring B sweep')
    return failures


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import spec
    sp = spec.load()[0]
    st = stage(sp); fails = check(sp)
    OUTPUT.write_text(json.dumps({'failures': fails, 'stage': st}, indent=1, default=list)+'\n')
    print(json.dumps({'failures': fails, 'line_length_m': st['line'][-1]['s_m'], 'least_clearance_m': st['least_clearance_m'],
                      'hatches': [(h['id'], [round(x, 3) for x in h['s']]) for h in st['hatches']], 'junctions': st['junctions'],
                      'coasts': [[round(a, 2), round(b, 2)] for a, b in st['coasts_s_m']]}, indent=1))
