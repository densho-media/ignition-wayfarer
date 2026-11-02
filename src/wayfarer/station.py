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
                        'boom': _boom_stage(s),
                        'gravity': 'microgravity: the docked stack is one rigid body in free fall (SHIP frame, zero field in DOCKED, DYN-007); no floor to '
                                   'stand on, hand-over-hand movement on handrails; the painted deck band is an orientation convention only',
                        'docked_rule': 'rings stopped and locked while docked (14_HULL_SERVICE!A8 BASELINE): UNDOCK before spin-up, DOCK after spin-down'},
            'fixtures': [dict(x, points=[list(v) for v in x['points']]) if x['shape'] == 'rod' else dict(x, size=list(x['size'])) if 'size' in x else x
                         for x in fixtures(s)],
            'hatches': bl['hatches'], 'line': bl['line'], 'coasts_s_m': bl['coasts'], 'grips': bl['grips'], 'junctions': bl['junctions'],
            'least_clearance_m': bl['least_clearance_m'], 'margin_m': bl['margin_m'], 'reach_m': bl['reach_m'],
            'source': 'station (STN-001 owner direction 2026-10-26; Q33 docking interface), human_entry.stations / fixtures, crew_transfer.stationary',
            'status': 'PROTOTYPE geometry and technique line; the station is not part of Wayfarer'}


# ---------- the station context (STN-002): boarding boom, hub, service and access -------------------------------------------------------




def _boom_stage(s):
    """The rig's view of the boarding boom (STN-002): each stage as a coaxial tube about the port axis (docked a range, outer radius, how far it
    moves out at full retraction) and the hub; the head (adapter, tunnel, node) moves with the last stage by the whole stroke."""
    g = context_geometry(s); P = s['station']['context']; step = P['stage_length_m']-P['stage_overlap_m']
    return {'stages': [{'name': st['name'], 'a_m': list(st['a']), 'radius_m': st['r'], 'retract_m': k*step} for k, st in enumerate(g['stages'])],
            'head_retract_m': g['stroke'], 'stroke_m': g['stroke'],
            'hub': {'centre_a_m': g['hub_centre_a'], 'radius_m': P['hub_radius_m'], 'length_m': P['hub_length_m']},
            'status': 'PROTOTYPE (STN-002): the head retracts with the inner stage; the outer stage and the hub stay with the station'}


def context_geometry(s, retracted=False):
    """Port-frame stations (a along the port's outward radial) of the head, the boom stages and the hub, extended or retracted."""
    P = s['station']['context']
    q = stations(s); n = P['stage_count']; L = P['stage_length_m']; o = P['stage_overlap_m']
    head_end = q['node'][1]                                     # the node's far end: its closed hatch now opens into the boom
    hub_face = head_end+n*L-(n-1)*o
    stroke = (n-1)*(L-o)
    shift = stroke if retracted else 0.0
    stages = []                                                 # outer first: stage 1 fixed at the hub
    for k in range(n):
        if retracted:
            a1 = hub_face; a0 = hub_face-L
        else:
            a1 = hub_face-k*(L-o); a0 = a1-L
        stages.append(dict(name=f'Boom_Stage_{k+1}', a=(a0, a1), r=P['stage_radius_m'][k]))
    head = dict(face=q['face']+shift, hatch=tuple(x+shift for x in q['hatch']), tunnel=tuple(x+shift for x in q['tunnel']),
                node=tuple(x+shift for x in q['node']), clear=q['clear'], node_r=q['node_r'], wall=q['wall'])
    hub_c = hub_face+P['hub_radius_m']
    return dict(head=head, stages=stages, hub_face=hub_face, hub_centre_a=hub_c, stroke=stroke, retracted=retracted,
                port=port(s), shield_r=s['forward_shield']['diameter']['value']/2, corridor_r=s['prototype']['dock_corridor_radius_m'])


def _cw(s, a, rho=0.0, phi=0.0, dx=0.0):
    x, y, z = world(s, a, rho, phi)
    return (x+dx, y, z)


def context_parts(s, retracted=False):
    """Station parts in the vehicle frame, in the exterior_hardware shape vocabulary: tube (a, b, r1[, r0]), box (world_centre, axes, size),
    torus (centre, axis, R, r). Each carries group, role and status."""
    import human_entry
    P = s['station']['context']
    # built docked; each part rides one mover (0 the hub side, k the boom stage k, stage_count the head) and a retracted part is shifted
    # outward along the port axis by its mover's share of the stroke (context_geometry)
    g = context_geometry(s); f = g['port']; u, w = human_entry.axes(f); X = (1.0, 0.0, 0.0); h = g['head']; out = []

    def tube(name, a0, a1, r, group, role, rho=0.0, phi=0.0, r_in=None, dx0=0.0, dx1=0.0):
        out.append(dict(name=name, shape='tube', a=_cw(s, a0, rho, phi, dx0), b=_cw(s, a1, rho, phi, dx1), r1=r, r_in=r_in, group=group, role=role,
                        port_a=(a0, a1), port_rho=rho+r))

    def box(name, c, axes, size, group, role, rho_max):
        out.append(dict(name=name, shape='box', world_centre=c, axes=axes, size=size, group=group, role=role, port_rho=rho_max))

    # head (STN-001 geometry, wall outside the clear bore)
    cap_r = s['prototype']['dock_capture_ring_radius_m']
    tube('STN_Adapter', h['face'], h['tunnel'][0], h['clear']+h['wall'], 'HEAD', 'docking adapter with the station hatch, soft-capture side (Q33 standard)', r_in=h['clear'])
    tube('STN_Adapter_CaptureRing', h['face'], h['face']+0.12, cap_r, 'HEAD', 'soft-capture ring, guide petals and bonding contacts (mechanism OPEN, Q33)', r_in=h['clear']+h['wall'])
    tube('STN_Tunnel', h['tunnel'][0], h['tunnel'][1], h['clear']+h['wall'], 'HEAD', 'boarding tunnel, 1.6 m clear', r_in=h['clear'])
    tube('STN_Node', h['node'][0], h['node'][1], h['node_r']+h['wall'], 'HEAD', "boarding node: the trainee's start (STN-001)", r_in=h['node_r'])
    for d in s['station']['window_deg']:
        tube(f'STN_Node_Window_{int(d)}', h['node'][0]-0.03, h['node'][0]+0.01, 0.22, 'HEAD', 'node window looking at the collar', rho=(h['clear']+h['wall']+h['node_r'])/2, phi=math.radians(d))
    # boom stages and their seal rings
    for st in g['stages']:
        a0, a1 = st['a']; r = st['r']
        tube('STN_'+st['name'], a0, a1, r, 'BOOM', 'telescoping pressure stage (sliding seals at each overlap; seal wear and dynamic loads OPEN)', r_in=r-0.08)
        tube('STN_'+st['name']+'_SealRing', a0, a0+P['seal_ring_length_m'], r+P['seal_ring_extra_m'], 'BOOM', 'seal and bearing ring at the stage end')
    # head-to-boom transition (node far end bulkhead to the inner stage)
    inner = g['stages'][-1]
    tube('STN_Head_Bulkhead', h['node'][1], h['node'][1]+0.25, h['node_r']+h['wall'], 'HEAD', 'node far-end bulkhead with the hatch into the boom (was the closed hatch to the station core)', r_in=inner['r'])
    # EVA inspection hoop and head handrails
    ha = h['tunnel'][0]+P['hoop_a_offset_m']; n = 24
    for i in range(n):
        p0 = 2*math.pi*i/n; p1 = 2*math.pi*(i+1)/n
        out.append(dict(name=f'STN_Inspection_Hoop_{i:02d}', shape='tube', a=_cw(s, ha, P['hoop_rho_m'], p0), b=_cw(s, ha, P['hoop_rho_m'], p1),
                        r1=P['hoop_radius_m'], group='ACCESS', role='EVA handrail hoop for capture-ring and collar inspection', port_a=(ha, ha), port_rho=P['hoop_rho_m']+P['hoop_radius_m']))
    for d in (45.0, 135.0, 225.0, 315.0):
        tube(f'STN_Hoop_Standoff_{int(d)}', ha, ha, P['hoop_radius_m'], 'ACCESS', 'hoop standoff', rho=h['clear']+h['wall'], phi=math.radians(d))
        out[-1]['b'] = _cw(s, ha, P['hoop_rho_m'], math.radians(d)); out[-1]['port_rho'] = P['hoop_rho_m']
    for d in P['pfr_deg']:
        c = _cw(s, ha, P['hoop_rho_m']+0.05, math.radians(d))
        out.append(dict(name=f'STN_PFR_Socket_{int(d)}', shape='box', world_centre=c, axes=(u, X, w), size=(0.12, 0.25, 0.25), group='ACCESS',
                        role='portable foot-restraint socket for the inspector', port_a=(ha, ha), port_rho=P['hoop_rho_m']+0.2))
    for d in P['head_rail_deg']:
        tube(f'STN_Head_Rail_{int(d)}', h['node'][0]+0.2, h['node'][1]-0.2, 0.0175, 'ACCESS', 'EVA handrail along the node', rho=P['head_rail_rho_m'], phi=math.radians(d))
    # umbilical along the boom, clipped; utility panel on the adapter; reel at the hub
    up = math.radians(P['umbilical_phi_deg']); ur = P['umbilical_rho_m']
    tube('STN_Utility_Panel', h['face']+0.15, h['face']+0.55, 0.22, 'SERVICE', 'adapter utility panel: power, data, water, N2/O2, bonding (standard connectors OPEN)', rho=h['node_r']+h['wall']+0.05, phi=up)
    tube('STN_Umbilical_Head', h['face']+0.35, h['node'][1], P['umbilical_radius_m'], 'SERVICE', 'umbilical run along the head', rho=h['node_r']+h['wall']+0.12, phi=up)
    tube('STN_Umbilical_Jog', h['node'][1], h['node'][1]+0.3, P['umbilical_radius_m'], 'SERVICE', 'umbilical jog to the boom clips', rho=ur, phi=up)
    out[-1]['a'] = _cw(s, h['node'][1], h['node_r']+h['wall']+0.12, up)
    for o in out:
        o['mover'] = P['stage_count'] if o['group'] in ('HEAD', 'ACCESS', 'SERVICE') else int(o['name'].split('_')[3]) if o['name'].startswith('STN_Boom_Stage_') else 0
    nst = len(g['stages'])
    for k, st in enumerate(g['stages'], 1):
        a0 = h['node'][1]+0.3 if k == nst else st['a'][0]+P['seal_ring_length_m']; a1 = g['hub_face'] if k == 1 else st['a'][1]
        tube(f'STN_Umbilical_Boom_{k}', a0, a1, P['umbilical_radius_m'], 'SERVICE', 'umbilical on clips along the boom (paid out and reeled in with the stroke)', rho=ur, phi=up)
        out[-1]['mover'] = k
        a = a0+0.7
        while a < a1-0.5:
            tube(f'STN_Umbilical_Clip_{k}_{int(a*10):04d}', a, a+0.08, 0.06, 'SERVICE', 'umbilical guide clip on the boom', rho=ur, phi=up)
            out[-1]['a'] = _cw(s, a, st['r'], up); out[-1]['b'] = _cw(s, a, ur, up); out[-1]['mover'] = k
            a += P['clip_pitch_m']
    # hub, gimbal, airlock, core stub, platform, lights, reel, truss: the hub axis runs along X through the port's x at a = hub_centre_a
    hc = g['hub_centre_a']; R = P['hub_radius_m']; HL = P['hub_length_m']
    tube('STN_Boom_Gimbal', g['hub_face']-0.35, g['hub_face'], P['gimbal_radius_m'], 'HUB', 'two-axis compliant gimbal at the boom root (misalignment and relative motion; stiffness OPEN)', r_in=P['stage_radius_m'][0])
    c0 = _cw(s, hc, 0, 0, -HL/2); c1 = _cw(s, hc, 0, 0, HL/2)
    out.append(dict(name='STN_Hub', shape='tube', a=c0, b=c1, r1=R, group='HUB', role='pressurized berthing hub of the development station', port_a=(hc-R, hc+R), port_rho=HL/2, x_axis=True))
    out.append(dict(name='STN_Hub_Airlock', shape='tube', a=c1, b=_cw(s, hc, 0, 0, HL/2+P['airlock_length_m']), r1=P['airlock_radius_m'], group='HUB',
                    role="station EVA airlock (inspection and boom-root work)", port_a=(hc-1, hc+1), port_rho=0, x_axis=True))
    out.append(dict(name='STN_Core_Stub', shape='tube', a=_cw(s, hc, 0, 0, -HL/2-P['core_stub_length_m']), b=c0, r1=P['core_stub_radius_m'], group='HUB',
                    role='station core module (continues beyond, not modelled)', port_a=(hc-R, hc+R), port_rho=0, x_axis=True))
    reel_c = _cw(s, g['hub_face']+0.3, ur+0.4, up)
    out.append(dict(name='STN_Umbilical_Reel', shape='tube', a=(reel_c[0]-P['reel_width_m']/2, reel_c[1], reel_c[2]), b=(reel_c[0]+P['reel_width_m']/2, reel_c[1], reel_c[2]),
                    r1=P['reel_radius_m'], group='SERVICE', role='umbilical reel (takes up the 25 m stroke)', port_a=(g['hub_face'], g['hub_face']), port_rho=0, x_axis=True))
    # platform on the hub's inboard side, aft of the boom (toward ring B is -X; put it at +X, forward, beside the airlock)
    px0, px1 = P['platform_x_m']; pw, pd = P['platform_size_m']
    pc = _cw(s, hc-R-0.1, 0, 0, (px0+px1)/2)
    out.append(dict(name='STN_Work_Platform', shape='box', world_centre=pc, axes=(u, X, w), size=(0.15, px1-px0, pd), group='ACCESS',
                    role='EVA work platform: boom-root and gimbal maintenance, tool stowage, foot restraints', port_a=(hc-R-0.2, hc-R), port_rho=0))
    for sx in (px0, px1):
        for sw in (-pd/2, pd/2):
            out.append(dict(name=f'STN_Rail_Post_{int(sx*10)}_{"p" if sw > 0 else "m"}', shape='tube', a=_cw(s, hc-R-0.1, abs(sw), math.pi/2 if sw > 0 else -math.pi/2, sx),
                            b=_cw(s, hc-R-0.1-P['railing_h_m'], abs(sw), math.pi/2 if sw > 0 else -math.pi/2, sx), r1=0.03, group='ACCESS', role='railing post', port_a=(0, 0), port_rho=0))
    for sw in (-pd/2, pd/2):
        out.append(dict(name=f'STN_Rail_Top_{"p" if sw > 0 else "m"}', shape='tube', a=_cw(s, hc-R-0.1-P['railing_h_m'], abs(sw), math.pi/2 if sw > 0 else -math.pi/2, px0),
                        b=_cw(s, hc-R-0.1-P['railing_h_m'], abs(sw), math.pi/2 if sw > 0 else -math.pi/2, px1), r1=0.025, group='ACCESS', role='railing', port_a=(0, 0), port_rho=0))
    for k, sw in enumerate((-pd/2+0.3, pd/2-0.3)):
        base = _cw(s, hc-R-0.1, abs(sw), math.pi/2 if sw > 0 else -math.pi/2, px1-0.4); top = _cw(s, hc-R-0.1-P['light_post_h_m'], abs(sw), math.pi/2 if sw > 0 else -math.pi/2, px1-0.4)
        out.append(dict(name=f'STN_Floodlight_Post_{k+1}', shape='tube', a=base, b=top, r1=0.05, group='SERVICE', role='floodlight post', port_a=(0, 0), port_rho=0))
        out.append(dict(name=f'STN_Floodlight_{k+1}', shape='light', at=top, target=_cw(s, h['face']+1.0), group='SERVICE',
                        role='floodlight aimed down the boom at the collar (station light, not Wayfarer)', port_a=(0, 0), port_rho=0))
    # station truss segment outboard of the hub (four longerons and bay frames), cut ends
    ta = hc+R+P['truss_gap_m']+P['truss_width_m']/2; tw = P['truss_width_m']/2; x0, x1 = P['truss_x']; rod = P['truss_rod_m']
    corners = [(-tw, -tw), (-tw, tw), (tw, tw), (tw, -tw)]

    def tp(da, dw, dx):
        x, y, z = _cw(s, ta+da, 0, 0, dx); return (x, y+dw*w[1], z+dw*w[2])
    for i, (da, dw) in enumerate(corners):
        out.append(dict(name=f'STN_Truss_Longeron_{i}', shape='tube', a=tp(da, dw, x0), b=tp(da, dw, x1), r1=rod, group='TRUSS', role='station spine truss longeron (cut: continues)', port_a=(ta-tw, ta+tw), port_rho=0))
    nb = int(round((x1-x0)/P['truss_bay_m']))
    for b in range(nb+1):
        dx = x0+b*(x1-x0)/nb
        for i in range(4):
            (da0, dw0), (da1, dw1) = corners[i], corners[(i+1) % 4]
            out.append(dict(name=f'STN_Truss_Frame_{b:02d}_{i}', shape='tube', a=tp(da0, dw0, dx), b=tp(da1, dw1, dx), r1=rod*0.8, group='TRUSS', role='truss bay frame', port_a=(ta-tw, ta+tw), port_rho=0))
        if b < nb:
            dx1 = x0+(b+1)*(x1-x0)/nb
            for i in range(4):
                (da0, dw0), (da1, dw1) = corners[i], corners[(i+1) % 4]
                p, q2 = (tp(da0, dw0, dx), tp(da1, dw1, dx1)) if b % 2 == 0 else (tp(da1, dw1, dx), tp(da0, dw0, dx1))
                out.append(dict(name=f'STN_Truss_Diag_{b:02d}_{i}', shape='tube', a=p, b=q2, r1=rod*0.6, group='TRUSS', role='truss diagonal', port_a=(ta-tw, ta+tw), port_rho=0))
    out.append(dict(name='STN_Hub_Truss_Tie', shape='tube', a=_cw(s, hc+R-0.1), b=_cw(s, ta-tw), r1=0.35, group='TRUSS', role='hub-to-truss structural tie', port_a=(hc+R, ta-tw), port_rho=0))
    shift = {k: (k-1)*(P['stage_length_m']-P['stage_overlap_m']) for k in range(1, P['stage_count']+1)}; shift[0] = 0.0
    for o in out:
        o.setdefault('mover', 0); o['status'] = 'PROTOTYPE'; o['state'] = 'RETRACTED' if retracted else 'DOCKED'
        o['retract_m'] = shift[o['mover']]
        if retracted and o['retract_m']:
            d = tuple(c*o['retract_m'] for c in (0.0, u[1], u[2])); mv = lambda p_: tuple(p_[i]+d[i] for i in range(3))
            for key in ('a', 'b', 'world_centre', 'at', 'target'):
                if key in o and not (key == 'target' and o['shape'] == 'light'):
                    o[key] = mv(o[key])
            o['port_a'] = tuple(x+o['retract_m'] for x in o['port_a'])
    return out


def context_figures(s):
    """Scale figures (1.8 m): the trainee in the node window, an EVA inspector at the hoop, two suited crew on the hub platform."""
    import human_entry
    P = s['station']['context']
    g = context_geometry(s); h = g['head']; ha = h['tunnel'][0]+P['hoop_a_offset_m']; hc = g['hub_centre_a']; R = P['hub_radius_m']
    px0, px1 = P['platform_x_m']; f = g['port']; u, w = human_entry.axes(f)
    return [
        dict(name='STN_Figure_Trainee', kind='IVA', feet=_cw(s, h['node'][0]+1.1, 0.0, 0.0), up=tuple(-c for c in (0, u[1], u[2])), facing=(0, -w[1], -w[2]),
             role="trainee at the start in the node (STN-001), looking toward the collar windows"),
        dict(name='STN_Figure_Inspector', kind='EVA', feet=_cw(s, ha+0.2, P['hoop_rho_m']+0.25, math.radians(P['pfr_deg'][0])),
             up=human_entry.vec(f, 0.0, math.cos(math.radians(P['pfr_deg'][0])), math.sin(math.radians(P['pfr_deg'][0]))), facing=(0, -u[1], -u[2]),
             role='EVA inspector in the hoop foot restraint, facing the capture ring and collar'),
        dict(name='STN_Figure_Platform_1', kind='EVA', feet=_cw(s, hc-R-0.18, 0.6, math.pi/2, px1-2.0), up=(0, -u[1], -u[2]), facing=(1, 0, 0),
             role='suited crew on the hub platform (boom root)'),
        dict(name='STN_Figure_Platform_2', kind='EVA', feet=_cw(s, hc-R-0.18, 1.0, -math.pi/2, px1-4.2), up=(0, -u[1], -u[2]), facing=(0, -u[1], -u[2]),
             role='suited crew on the hub platform looking down the boom'),
    ]


def _axis_distance(p, q):
    """Least distance of a segment from the ship axis (X)."""
    best = 1e9
    for i in range(41):
        t = i/40; y = p[1]+(q[1]-p[1])*t; z = p[2]+(q[2]-p[2])*t; best = min(best, math.hypot(y, z))
    return best


def context_checks(s):
    import habitat_ring
    import forward_shield
    P = s['station']['context']
    rows = []; fails = []
    p = s['prototype']; clr = p['mechanical_clearance_m']

    def need(ok, key, value, limit, msg):
        rows.append(dict(check=key, value=value, limit=limit, ok=bool(ok), note=msg))
        if not ok:
            fails.append(f'{key}: {msg} ({value} vs {limit})')
    for state in (False, True):
        g = context_geometry(s, state); tag = 'retracted' if state else 'docked'
        corridor_parts = [o for o in context_parts(s, state) if o['group'] in ('HEAD', 'BOOM', 'SERVICE', 'ACCESS') and o.get('port_a', (0, 0))[0] < g['shield_r']+1e-9
                          and o['shape'] != 'light' and not o.get('x_axis') and o['name'] not in ('STN_Work_Platform',) and not o['name'].startswith(('STN_Rail', 'STN_Floodlight'))]
        worst = max(corridor_parts, key=lambda o: o['port_rho'])
        need(worst['port_rho'] <= g['corridor_r']-clr+1e-9, f'corridor_{tag}', round(worst['port_rho'], 3), g['corridor_r']-clr,
             f"widest station part inside the shield radius ({worst['name']}) stays inside the 3 m docking corridor less the mechanical clearance")
        body = [o for o in context_parts(s, state) if o['group'] in ('HUB', 'TRUSS') or o['name'].startswith(('STN_Rail', 'STN_Floodlight_Post', 'STN_Work'))]
        dmin = 1e9; who = None
        for o in body:
            if o['shape'] == 'tube':
                d = _axis_distance(o['a'], o['b'])-o['r1']
            else:
                c = o['world_centre']; ax = o['axes']; sz = o['size']; n = 6
                d = min(math.hypot(*[c[j]+((i/n-0.5)*sz[0]*ax[0][j]+(k/n-0.5)*sz[1]*ax[1][j]+(m/n-0.5)*sz[2]*ax[2][j]) for j in (1, 2)])
                        for i in range(n+1) for k in range(n+1) for m in range(n+1))
            if d < dmin:
                dmin, who = d, o['name']
        need(dmin >= g['shield_r']+P['shield_margin_m'], f'station_body_radius_{tag}', round(dmin, 2), g['shield_r']+P['shield_margin_m'],
             f'nearest station-body surface ({who}) from the ship axis stays outside the shield radius plus margin, so no ship part can reach it')
    g = context_geometry(s); h = g['head']
    need(abs(g['stroke']-s['station']['undock_standoff_m']) < 1e-9, 'stroke_equals_walk_standoff', g['stroke'], s['station']['undock_standoff_m'],
         "boom stroke equals the walk's undock stand-off, so the walk's undock motion is the boom retraction")
    gr = context_geometry(s, True)
    need(gr['head']['face']-h['face'] >= g['stroke']-1e-9, 'retracted_gap', round(gr['head']['face']-h['face'], 2), g['stroke'], 'retracted head stands off the collar by the stroke')
    need(min(st['r'] for st in g['stages'])-0.08 >= h['clear']+0.1-1e-9, 'boom_clear_passage', round(min(st['r'] for st in g['stages'])-0.08, 3), h['clear']+0.1,
         'inner stage keeps the 1.6 m passage plus 0.1 m for its seal lands')
    rs = P['stage_radius_m']
    need(all(rs[i]-0.08 >= rs[i+1]+P['seal_ring_extra_m']+0.01 for i in range(len(rs)-1)), 'stage_nesting', rs, 'outer bore > inner + seal ring', 'stages nest with their seal rings')
    ring_b = habitat_ring.centers(s)[1]+habitat_ring.sweep_half(s)
    need(g['port']['x']-g['corridor_r'] > ring_b+clr, 'ring_b_sweep_gap', round(g['port']['x']-g['corridor_r']-ring_b, 3), clr, 'corridor clear of the ring B sweep')
    fs = forward_shield.stations(s)
    need(g['port']['x']+g['corridor_r'] < fs['truss_aft']-clr, 'shield_truss_gap', round(fs['truss_aft']-g['port']['x']-g['corridor_r'], 3), clr, 'corridor clear of the shield truss aft face')
    # operational interlock: the stack may exist only where the configuration allows it
    cfg = s['configuration']
    allowed = []
    for name, c in cfg.items():
        if not isinstance(c, dict) or not c.get('buildable'):
            continue
        ok = c.get('drive') == 'OFF' and c.get('habitat') == 'STOPPED_LOCKED'
        if ok:
            allowed.append(name)
    need(allowed == ['DOCKED'], 'docked_only_in', allowed, ['DOCKED'], 'the boom may be mated only with the drive OFF and both rings STOPPED_LOCKED')
    return rows, fails


def context_summary(s):
    P = s['station']['context']
    g = context_geometry(s); gr = context_geometry(s, True); h = g['head']
    return dict(port=dict(name=g['port']['name'], x=g['port']['x'], theta_deg=round(math.degrees(g['port']['theta']), 1), face_a=round(h['face'], 3)),
                head=dict(face=h['face'], tunnel=h['tunnel'], node=h['node']),
                boom=dict(stages=g['stages'], extended_length_m=round(g['hub_face']-h['node'][1], 2), stroke_m=g['stroke'],
                          retracted=[dict(name=st['name'], a=st['a']) for st in gr['stages']], retracted_head_face=gr['head']['face']),
                hub=dict(face_a=g['hub_face'], centre_a=g['hub_centre_a'], radius_m=P['hub_radius_m'], length_m=P['hub_length_m']),
                corridor=dict(radius_m=g['corridor_r'], r0=g['port']['r1'], r1=g['shield_r']),
                walk_distance_station_hub_to_node_m=round(g['hub_face']-h['node'][1], 2))


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
    failures += context_checks(s)[1]
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
