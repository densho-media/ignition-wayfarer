"""DRONE-001: the study maintenance fleet (S&E 51_DRONE_FLEET .. 54_DRONE_VALIDATION, Eye 46, Tale 29), L2 proxies. Pure standard library.

The owner's inventory is STUDY only: seven task classes, 11 IVA + 13 EVA = 24 mobile units (20 active, 4 reserve) and two fixed arms outside
the 24. Every mass, power, speed, reach, load and latch rating is OPEN, and every station is UNPLACED / CAD OPEN (52), so each station here is a
PROTOTYPE anchor on geometry that already exists; no new room, pressure boundary, interface or mass. Proxy sizes take the upper end of each
class's envelope (51 column G).

- manifest(): one record per unit, DR-<class>-Unn, its station and role.
- stations(): docks, units, rails and arm bases per station (vehicle frame; DS-05..08 in their ring sector's frame, see sector()).
- sector(s, function): the ring rover and duct cassettes as route_fitout elements (route_fitout.sector_elements appends them).
- spine_route(): the DR-EVA-03 track and its three docks (the L3 demonstration's path).
- check(): the L2 fit screen of 54 DGT-002/003/004/005/006/007/008 (Claude evidence only; every owner gate stays HOLD).
- contract(): the rig block.

    python3 src/wayfarer/drone_fleet.py
"""
import math

import crew_transfer
import forward_shield
import habitat_ring
import human_entry as he
import hull_geometry
import layout
import storeroom as sr
import survival_fit
import thermal_geometry

SOURCES = ('drone_fleet', 'drone_eye_interface', 'drone_story', 'owner_drones_2026_10_13')
GATES_OPEN = {
    'DGT-004': 'latch load F_axial = m x 1.5 x 9.80665 m/s2 (15!A186, formula approved); unit mass OPEN (51), so only orientation and egress are screened',
    'DGT-009': 'route coverage and tool reach per job: only the DR-EVA-03 spine track is routed (P1)',
    'DGT-010': 'charge / duty / heat: DOP-12 OPEN, reactor-off generator OPEN',
    'DGT-011': 'mass and CG: every class mass OPEN; DRV-GUARD 5-15 t not verified, never additive',
    'DGT-012': 'tool coupling and fastener standard: one shared tool-changer proxy in the L3 demo only',
    'DGT-013': 'fault replay: three scenarios in the L3 demo (drone_demo); stranded-object swept volumes OPEN',
    'DGT-016': 'precedent matrix accepted as PROVENANCE only (15!A187); DR-IVA-03 and DR-EVA-04: NO DIRECT FLIGHT PRECEDENT IDENTIFIED',
}


def table(s):
    return s['drones']


def classes(s):
    return {c['id']: c for c in table(s)['classes']}


def unit_size(c):
    """Proxy box (along, across, depth): the class's upper envelope; EVA crawlers sit flat on their track (depth 0.6 of it, PROTOTYPE)."""
    u = c['envelope_m'][1]
    return (u, u, u*.6) if c['domain'] == 'EVA' else (u, u, u)


def dock_size(s, c):
    m = table(s)['dock_margin_m']; L, W, D = unit_size(c)
    return (L+2*m, W+2*m, D+m)


def manifest(s):
    """Per unit: id (numbered per class in station order), class, domain, role (active / reserve / fixed) and station."""
    cl = classes(s); count = {}; out = []
    for st in table(s)['stations']:
        c = cl[st['cls']]
        for _ in range(st['units']):
            count[c['id']] = count.get(c['id'], 0)+1
            uid = c['id'] if c['domain'] == 'FIXED' else f"{c['id']}-U{count[c['id']]:02}"
            out.append(dict(id=uid, cls=c['id'], domain=c['domain'], role=st['role'], station=st['id'], name=c['name']))
    return out


def _x(s, ref):
    return layout.at(s, ref) if isinstance(ref, dict) else float(ref)


def _list(v):
    return v if isinstance(v, list) else [v]


def _box(name, sp, role, centre, axes, size, **kw):
    return survival_fit.env(name, sp, role, centre, axes, size, source='drone_fleet', **kw)


def _on_box(base, size, name, sp, role):
    """A unit seated on a dock: same axes, pushed out along the dock's depth axis."""
    c, ax = base['world_centre'], base['axes']; d = base['size'][2]/2+size[2]/2+.005      # 5 mm seat gap: proxies never share a face
    return _box(name, sp, role, tuple(c[i]+d*ax[2][i] for i in range(3)), ax, size)


def _storeroom(s, st, c):
    """SP-45 rack bay: bay `bay` (default the first) of the named row segment; one cassette per listed shelf (centred on the shelf, in the rack
    depth). The SP-49 bay is the Outer row's first (survival_fit.storeroom)."""
    q = s['storeroom']; geo = sr.station(s); _, eu, et = sr.frame(s)
    rows = {name: (u0, u1, segs) for name, u0, u1, segs in sr.rows(s)}
    u0, u1, segs = rows[st['row']]; t0, t1 = segs[st['segment']-1]; n = max(1, math.ceil((t1-t0)/q['bay_max_m']-1e-9)); pitch = (t1-t0)/n
    b = st.get('bay', 1); t0 += (b-1)*pitch
    levels = q['shelf_levels_m']+[geo['H']]; ts = q['shelf_thickness_m']; L, W, D = dock_size(s, c); out = []
    W = unit_size(c)[1]+.02                            # across the 0.6 m rack depth: a thin cassette wall, clear of the room's shell
    axes = (et, eu, (1.0, 0.0, 0.0))                   # along the bay (t), across the rack depth (u), depth up off the shelf (+X)
    for k, j in enumerate(st['shelves']):
        lv = levels[j-1]; cell = levels[j]-lv-ts; x = geo['xf']+lv+ts+D/2
        dock = _box(f"Drone_Dock_{st['id']}_{k+1}", st['id'], f"{c['name']} cassette (SP-45 rack, {st['row']} bay {st['segment']}.{b} shelf {j})",
                    sr.world(s, x, (u0+u1)/2, t0+pitch/2), axes, (L, W, D), cell_m=(pitch, u1-u0, cell), shelf=j, row=st['row'])
        out.append(dock)
    return out


def _brow_x(s, r, depth):
    """X of a box centre whose forward face sits standoff aft of the shield truss envelope at radius r."""
    return forward_shield.truss_aft_at(s, r)-table(s)['cassette_depth_m']-depth/2


def _brow_axes(a):
    eu = (0.0, math.cos(a), math.sin(a)); et = (0.0, -math.sin(a), math.cos(a))
    return (eu, et, (-1.0, 0.0, 0.0))               # along the spoke, across it, depth aft


def _brow(s, st, c):
    out = []; L, W, D = dock_size(s, c) if c['domain'] != 'FIXED' else (c['base_m'][0], c['base_m'][0], c['base_m'][1])
    g = s['survival']['crawler_rail_gauge_m']; rr = s['survival']['crawler_rail_radius_m']; cd = table(s)['cassette_depth_m']
    for k, deg in enumerate(_list(st['deg']), 1):
        a = math.radians(deg); r = st['dock_r']; x = _brow_x(s, r, D)
        if c['domain'] == 'FIXED':
            base = crew_transfer.radial(forward_shield.truss_aft_at(s, r)-cd, r, a)
            out.append(dict(name=f"Drone_ArmBase_{st['id']}", sp=st['id'], role=f"{c['name']} base (reach OPEN)", shape='tube', r0=0.0, r1=L/2,
                            a=base, b=(base[0]-D, base[1], base[2]), volume_m3=math.pi*(L/2)**2*D, source_ref='drone_fleet', geometry_status='PROTOTYPE'))
            continue
        out.append(_box(f"Drone_Dock_{st['id']}_{k}", st['id'], f"{c['name']} dock, shield truss spoke at {deg:g} deg (aft side)",
                        crew_transfer.radial(x, r, a), _brow_axes(a), (L, W, D)))
        for side, dt in ((1, -g/2), (2, g/2)):
            pts = []
            for i in range(25):
                rho = st['rail_r'][0]+(st['rail_r'][1]-st['rail_r'][0])*i/24
                pts.append(crew_transfer.radial(forward_shield.truss_aft_at(s, rho)-cd/2, rho, a+dt/rho))
            out.append(dict(name=f"Drone_Rail_{st['id']}_{k}_{side}", sp=st['id'], role='Brow service rail (aft of the truss, rear side only)', shape='rod',
                            radius=rr, points=pts, source_ref='drone_fleet', geometry_status='PROTOTYPE'))
    return out


def _casing(s, st, c, x, deg, name):
    a = math.radians(deg); rh = hull_geometry.radius_at(s, x)+s['survival']['crawler_rail_standoff_m']
    if c['domain'] == 'FIXED':
        Dm, H = c['base_m']; base = crew_transfer.radial(x, rh, a)
        return dict(name=f"Drone_ArmBase_{st['id']}", sp=st['id'], role=f"{c['name']} base (reach OPEN)", shape='tube', r0=0.0, r1=Dm/2,
                    a=base, b=crew_transfer.radial(x, rh+H, a), volume_m3=math.pi*(Dm/2)**2*H, source_ref='drone_fleet', geometry_status='PROTOTYPE')
    L, W, _ = dock_size(s, c); D = table(s)['cassette_depth_m']          # a flat latch cradle: the unit stays inside the 14 m maximum body
    return _box(name, st['id'], f"{c['name']} dock cradle on the casing at {deg:g} deg", crew_transfer.radial(x, rh+D/2, a), he.axes_at(a), (L, W, D))


def spine_route(s):
    """DR-EVA-03: a two-rail track on the stationary casing at the station's azimuth, from rail_x to ring_keepout_margin_m short of ring A's
    sweep; docks at the station's three X. Returns the rails, docks, the track's end X and its segment breaks (one per dock)."""
    st = next(q for q in table(s)['stations'] if q['id'] == 'DS-13'); c = classes(s)[st['cls']]; a = math.radians(st['deg'])
    g = s['survival']['crawler_rail_gauge_m']; so = s['survival']['crawler_rail_standoff_m']
    x0 = _x(s, st['rail_x'][0]); x1 = min(habitat_ring.centers(s))-habitat_ring.sweep_half(s)-table(s)['ring_keepout_margin_m']-s['survival']['crawler_rail_radius_m']
    xs = [x0+(x1-x0)*k/60 for k in range(61)]; rails = []
    for side, dt in ((1, -g/2), (2, g/2)):
        pts = [crew_transfer.radial(x, hull_geometry.radius_at(s, x)+so, a+dt/(hull_geometry.radius_at(s, x)+so)) for x in xs]
        rails.append(dict(name=f'Drone_Rail_DS-13_{side}', sp='DS-13', role='spine utility crawler track (segmented, anchor-rated: rating OPEN)', shape='rod',
                          radius=s['survival']['crawler_rail_radius_m'], points=pts, source_ref='drone_fleet', geometry_status='PROTOTYPE'))
    docks = [_casing(s, st, c, _x(s, xr), st['deg'], f'Drone_Dock_DS-13_{k}') for k, xr in enumerate(st['x'], 1)]
    return dict(rails=rails, docks=docks, x0=x0, x1=x1, azimuth=a, dock_x=[_x(s, xr) for xr in st['x']],
                surface_r=lambda x: hull_geometry.radius_at(s, x)+so)


def _root_docks(s, st):
    """DS-11: the SP-51 dock at each blade's first root station (existing geometry, referenced, not rebuilt)."""
    d = thermal_geometry.blade_of(s); stn = thermal_geometry.stations(s, d); order = sorted(stn['roots']+stn['stays'])
    n = order.index(min(stn['roots']))+1; ext = {q['name']: q for q in survival_fit.exterior(s)}
    return [ext[f'Survival_Crawler_Dock_{j}_{n}'] for j in range(s['radiators']['count'])]


def stations(s):
    """Per station: id, class, role, frame ('VEHICLE' or 'SECTOR'), docks (new proxies), existing (referenced docks), units, rails, note."""
    cl = classes(s); out = []; units = iter(manifest(s))
    for st in table(s)['stations']:
        c = cl[st['cls']]; rec = dict(id=st['id'], cls=c['id'], role=st['role'], units_n=st['units'], frame='VEHICLE', anchor=st['anchor'],
                                     docks=[], existing=[], units=[], rails=[], note=st.get('note', ''), operations=st.get('operations'))
        if st['anchor'] == 'storeroom':
            rec['docks'] = _storeroom(s, st, c)
        elif st['anchor'] == 'brow':
            got = _brow(s, st, c); rec['docks'] = [q for q in got if not q['name'].startswith('Drone_Rail')]; rec['rails'] = [q for q in got if q['name'].startswith('Drone_Rail')]
        elif st['anchor'] == 'radiator_root':
            rec['existing'] = _root_docks(s, st)
        elif st['anchor'] == 'spine':
            r = spine_route(s); rec['docks'] = r['docks']; rec['rails'] = r['rails']
        elif st['anchor'] == 'casing':
            xs = [_x(s, st['x'])]*len(_list(st['deg']))
            rec['docks'] = [_casing(s, st, c, x, deg, f"Drone_Dock_{st['id']}_{k}") for k, (x, deg) in enumerate(zip(xs, _list(st['deg'])), 1)]
        elif st['anchor'] == 'sector':
            rec.update(frame='SECTOR', ring=st['ring'], function=st['function'])
            rec['docks'] = [q for q in sector(s, st['function']) if st['id'] in q['sp'].split('/')]
        hosts = rec['docks']+rec['existing']
        for k in range(st['units']):
            u = next(units)
            if c['domain'] == 'FIXED':
                continue
            if rec['frame'] == 'SECTOR':
                rec['units'].append(dict(id=u['id'], host=hosts[0]['name'])); continue
            host = hosts[k % len(hosts)] if st['anchor'] != 'storeroom' else hosts[k]
            q = _on_box(host, unit_size(c), f"Drone_Unit_{u['id']}", st['id'], f"{c['name']} {u['role']} (proxy; mass, power OPEN)") \
                if st['anchor'] in ('radiator_root', 'spine', 'casing', 'brow') else \
                _box(f"Drone_Unit_{u['id']}", st['id'], f"{c['name']} {u['role']} (proxy; mass, power OPEN)", host['world_centre'], host['axes'], unit_size(c))
            q.update(unit=u['id'], role_state=u['role']); rec['units'].append(q)
        out.append(rec)
    return out


def sector(s, function):
    """Ring rover and duct cassettes (sector frame, route_fitout elements): the rover's floor cassette in WORK_MEDICAL_OPS between the couch
    lockers and the workbench on the outer side wall; the duct crawler's service-port door on the ECLSS bay face in LIFE_SUPPORT_GARDEN_COMMON
    (the cassette is inside the bay, as SP-46's door is in its cabinet). The mirrored rings give one of each per ring (DS-05..08)."""
    import route_fitout as rf
    cl = classes(s); I = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)); out = []
    group = [st for st in table(s)['stations'] if st['anchor'] == 'sector' and st['function'] == function]
    if not group:
        return out
    import habitat_interior
    blocks = {b['name']: b for b in habitat_interior.zones(s, function)}; sec = habitat_interior.section(s)
    st = group[0]; c = cl[st['cls']]; L, W, D = dock_size(s, c); sp = '/'.join(q['id'] for q in group)
    if st['place'] == 'floor_cassette':
        # Along the axis (x), up from the deck (-y), tangential depth (z) against the outer side wall.
        zw = -sec['half_width_deck_m']+.10; lo, hi = (-L/2, -W, zw), (L/2, 0.0, zw+D)
        fn = f"{c['name']} floor cassette: secured wall/floor dock, local charging ({sp}; ring-local, no rotary transfer)"
        paint = 'locker'
    else:
        b = blocks['ECLSS_Bay']; face = b['min'][0]; zc = (b['min'][2]+b['max'][2])/2; yc = -1.0
        lo, hi = (face-.015, yc-W/2, zc-L/2), (face, yc+W/2, zc+L/2)
        fn = f"{c['name']} service-port door: instrument access cassette in the ECLSS bay ({sp}; designed raceway only, Garden bio isolation)"
        paint = 'safety'
    size = tuple(hi[k]-lo[k] for k in range(3))
    out.append(rf.element(f"Drone_Dock_{st['place'].title().replace('_', '')}", 'SPACER', fn, 'ENGINEERING_FLEXIBLE', paint, 'wbox', False,
                          centre=tuple((lo[k]+hi[k])/2 for k in range(3)), axes=I, size=size, sp=sp, volume_m3=L*W*D, source_ref='drone_fleet'))
    return out


# ---------------------------------------------------------------- checks

def _points(q, step=0.25):
    if q['shape'] == 'box':
        c, ax, sz = q['world_centre'], q['axes'], q['size']; pts = []
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                for k in (-1, 0, 1):
                    pts.append(tuple(c[m]+i*sz[0]/2*ax[0][m]+j*sz[1]/2*ax[1][m]+k*sz[2]/2*ax[2][m] for m in range(3)))
        return pts, 0.0
    if q['shape'] == 'tube':                         # rim points of both end discs and the axis
        a, b = q['a'], q['b']; e = [b[m]-a[m] for m in range(3)]; n = math.sqrt(sum(v*v for v in e)); e = [v/n for v in e]
        h = (1.0, 0.0, 0.0) if abs(e[0]) < .9 else (0.0, 1.0, 0.0)
        u = [e[1]*h[2]-e[2]*h[1], e[2]*h[0]-e[0]*h[2], e[0]*h[1]-e[1]*h[0]]; un = math.sqrt(sum(v*v for v in u)); u = [v/un for v in u]
        w = [e[1]*u[2]-e[2]*u[1], e[2]*u[0]-e[0]*u[2], e[0]*u[1]-e[1]*u[0]]; R = q['r1']
        return [tuple(c[m]+R*(math.cos(k*math.pi/6)*u[m]+math.sin(k*math.pi/6)*w[m]) for m in range(3)) for c in (a, b) for k in range(12)]+[a, b], 0.0
    pts = []
    for a, b in zip(q['points'], q['points'][1:]):
        n = max(1, int(math.dist(a, b)/step))
        pts += [tuple(a[m]+(b[m]-a[m])*t/n for m in range(3)) for t in range(n)]
    return pts+[q['points'][-1]], q.get('radius', 0.0)


def _gap(q, other):
    """Clearance between two records (sampled; box-to-box uses the exact point-to-box distance both ways)."""
    pa, ra = _points(q); pb, rb = _points(other)
    best = math.inf
    if other['shape'] == 'box':
        best = min(survival_fit._box_point_distance(other, p) for p in pa)-ra
    if q['shape'] == 'box':
        best = min(best, min(survival_fit._box_point_distance(q, p) for p in pb)-rb)
    if q['shape'] != 'box' and other['shape'] != 'box':
        best = min(math.dist(a, b) for a in pa for b in pb)-ra-rb
    return best


def _blade_gap(s, p):
    """Distance from a point to the nearest blade's planform (root to outer radius, aft to front edge) less the root truss half depth."""
    d = thermal_geometry.blade_of(s); half = s['radiators']['geometry']['truss_depth_m']/2; best = math.inf
    for j in range(s['radiators']['count']):
        a = math.radians(s['prototype']['radiator_phase_deg']+j*120)
        rho = p[1]*math.cos(a)+p[2]*math.sin(a); h = -p[1]*math.sin(a)+p[2]*math.cos(a)
        dx = max(d['aft_x_m']-p[0], 0.0, p[0]-d['front_x_m']); dr = max(d['root_radius_m']-rho, 0.0, rho-d['outer_radius_m'])
        best = min(best, math.sqrt(dx*dx+dr*dr+max(abs(h)-half, 0.0)**2) if rho > 0 else math.inf)
    return best


def _exterior(recs):
    return [q for r in recs if r['frame'] == 'VEHICLE' and r['anchor'] != 'storeroom' for q in r['docks']+r['units']+r['rails']]


def obstacles(s):
    """Existing exterior hardware the drone docks, rails and swept units must clear: the survival envelopes, hull fittings, docking corridors
    and the shield truss spokes' aft members."""
    others = [it for it in survival_fit.exterior(s)]
    for fit in hull_geometry.service_fittings(s):
        others.append(dict(name=fit['name'], shape='rod', radius=fit['radius'], points=[crew_transfer.radial(fit['x'], fit['r0'], fit['theta']), crew_transfer.radial(fit['x'], fit['r1'], fit['theta'])]))
    for cor in hull_geometry.dock_corridors(s):
        others.append(dict(name=f"{cor['name']}_Corridor", shape='rod', radius=cor['radius'], points=[crew_transfer.radial(cor['x'], cor['r0'], cor['theta']), crew_transfer.radial(cor['x'], cor['r1'], cor['theta'])]))
    for sp in forward_shield.truss(s)['spokes']:
        for kind, pts in sp['members']:
            if kind == 'aft':
                others.append(dict(name=f"Shield_Spoke_{sp['index']}_aft", shape='rod', radius=forward_shield.truss(s)['member_radius'], points=pts))
    return others


def check(s):
    """L2 fit screen. Returns (rows, failures). Passing it is Claude's proxy evidence, never an owner gate (54 current gate HOLD)."""
    q = table(s); clr = s['prototype']['mechanical_clearance_m']; recs = stations(s); man = manifest(s); rows = {}; fails = []
    by = {r['id']: r for r in recs}
    # DGT-002 counts by domain and role; class counts against the station rows.
    f = q['fleet']; mob = [u for u in man if u['domain'] != 'FIXED']
    cnt = dict(iva=sum(u['domain'] == 'IVA' for u in mob), eva=sum(u['domain'] == 'EVA' for u in mob), active=sum(u['role'] == 'active' for u in mob),
               reserve=sum(u['role'] == 'reserve' for u in mob), total=len(mob), fixed_arms=sum(u['domain'] == 'FIXED' for u in man))
    rows['DGT-002'] = dict(counts=cnt, owner=dict((k, f[k]) for k in cnt))
    for k, v in cnt.items():
        if v != f[k]:
            fails.append(f'DGT-002 {k} {v} != owner {f[k]}')
    for c in q['classes']:
        a = sum(st['units'] for st in q['stations'] if st['cls'] == c['id'] and st['role'] in ('active', 'fixed'))
        r = sum(st['units'] for st in q['stations'] if st['cls'] == c['id'] and st['role'] == 'reserve')
        if (a, r) != (c['active'], c['reserve']):
            fails.append(f"DGT-002 {c['id']} stations {a}+{r} != class {c['active']}+{c['reserve']}")
    rows['DGT-002']['units_placed'] = sum(len(r['units']) for r in recs); rows['DGT-002']['stations'] = len(recs)
    ext = _exterior(recs)
    # DGT-005 ring sweep: nothing stationary inside a ring's swept slab (out to the outer radius) plus the margin.
    half = habitat_ring.sweep_half(s); ro = habitat_ring.outer(s); m = q['ring_keepout_margin_m']; worst = math.inf
    for it in ext:
        pts, rad = _points(it)
        for p in pts:
            if math.hypot(p[1], p[2])-rad <= ro+m:
                worst = min(worst, min(abs(p[0]-xc)-half-rad for xc in habitat_ring.centers(s)))
    rows['DGT-005'] = dict(ring_sweep_gap_m=worst, ring_local=[r['id'] for r in recs if r['frame'] == 'SECTOR'])
    if worst < m-1e-9:
        fails.append(f'DGT-005 stationary drone hardware {worst:.3f} m from a ring sweep (margin {m} m)')
    # DGT-007 hot blades: every item but the DS-11 root docks stays blade_clearance_m off the blade planform and root truss.
    bg = {it['name']: (it['sp'], min(_blade_gap(s, p) for p in _points(it)[0])-_points(it)[1]) for it in ext}
    worst_b = min(v for sp, v in bg.values() if sp != 'DS-11')
    view = sorted({it['sp'] for it in ext if thermal_geometry.blade_of(s)['aft_x_m']-5 <= _points(it)[0][0][0] <= thermal_geometry.blade_of(s)['front_x_m']+5})
    rows['DGT-007'] = dict(blade_gap_m=worst_b, root_units={k: v for k, (sp, v) in bg.items() if sp == 'DS-11'},
                           stations_in_view_of_blades=view, rule='no 1800 K blade contact; casing work only in a released cold state (OPEN, DOP-08); no traversal while hot blades operate (15!A184)')
    if worst_b < q['blade_clearance_m']-1e-9:
        fails.append(f'DGT-007 drone hardware {worst_b:.3f} m from a blade (needs {q["blade_clearance_m"]} m)')
    # DGT-008 aft: everything on the casing (forward of the blade aft edge), none at the drive, thrust ring or nozzle exits.
    xa = min(min(p[0] for p in _points(it)[0]) for it in ext); casing0 = layout.at(s, {'datum': 'RADIATOR_AFT', 'offset_m': 0.0})
    rows['DGT-008'] = dict(aftmost_x_m=xa, casing_start_x_m=casing0, nozzle_exit_x_m=-s['ship']['length']['value']/2)
    if xa < casing0-1e-9:
        fails.append(f'DGT-008 drone hardware at X {xa:.2f} m, aft of the casing (drive / thrust ring / plume zone)')
    # DGT-006 Brow: aft of the truss envelope (never the ram face), clear of every EYE port in each r4/r16/r24 variant and of the Crown ports.
    import eye_placement
    brow = [it for r in recs if r['anchor'] == 'brow' for it in r['docks']+r['units']+r['rails']]
    ahead = max(max(p[0]-forward_shield.truss_aft_at(s, math.hypot(p[1], p[2])) for p in _points(it)[0]) for it in brow)
    port_r = s['forward_defense']['eye_wells'].get('outer_port', {}).get('radius_m', forward_shield.prototype(s)['well_diameter_m']/2)
    wells = {}
    for R in eye_placement.RADII:
        v = eye_placement.variant(s, R)
        wells[f'r{R:g}'] = min(math.hypot(p[1]-y, p[2]-z)-_points(it)[1]-port_r for it in brow for p in _points(it)[0] for y, z in forward_shield.well_centres(v))
    crown = min(min(abs(math.hypot(p[1], p[2])-(c['r0']+c['r1'])/2)-(c['r1']-c['r0'])/2 for c in forward_shield.crown_ports(s)) for it in brow for p in _points(it)[0])
    rows['DGT-006'] = dict(forward_of_truss_aft_m=ahead, eye_port_gap_m=wells, crown_port_radial_gap_m=crown,
                           rule='rear side only; no 0.016c ram-face traversal; Crown no-fire service zone and shutter interlock OPEN (EYS-DR-02/03)')
    if ahead > 1e-9:
        fails.append(f'DGT-006 Brow drone hardware {ahead:.3f} m forward of the truss aft face')
    for k, v in wells.items():
        if v < clr-1e-9:
            fails.append(f'DGT-006 Brow hardware {v:.3f} m from an EYE port ({k})')
    if crown < clr-1e-9:
        fails.append(f'DGT-006 Brow hardware {crown:.3f} m from the Crown ports')
    # DGT-003 docks against existing exterior hardware, hull fittings, the docking corridors, the trunk branches and each other.
    others = obstacles(s)
    def host(it, o):
        # Mounted by design: DS-11 units on their SP-51 root dock; Brow docks, units, rails and the arm base on the truss spoke at their azimuth.
        if it['sp'] == 'DS-11' and o['name'].startswith('Survival_Crawler_Dock'):
            return True
        if it['sp'] in ('DS-10', 'DS-15') and o['name'].startswith('Shield_Spoke_'):
            c = _points(it)[0][len(_points(it)[0])//2]; az = math.atan2(c[2], c[1]); oc = o['points'][0]
            return abs(crew_transfer.angle_diff(az, math.atan2(oc[2], oc[1]))) < math.radians(5)
        return False
    gaps = {it['name']: min((_gap(it, o) for o in others if not host(it, o)), default=math.inf) for it in ext}
    hard = gaps
    worst_k = min(hard, key=hard.get)
    rows['DGT-003'] = dict(worst=worst_k, worst_gap_m=hard[worst_k], docks_new=sum(len(r['docks']) for r in recs), docks_existing=sum(len(r['existing']) for r in recs),
                           dock_slots=sum(r['units_n'] for r in recs if r['role'] != 'fixed'), arm_bases=sum(1 for r in recs for d in r['docks'] if d['name'].startswith('Drone_ArmBase')))
    for k, v in hard.items():
        if v < clr-1e-9:
            fails.append(f'DGT-003 {k} {v:.3f} m from existing hardware')
    dd = [d for r in recs if r['frame'] == 'VEHICLE' and r['anchor'] not in ('storeroom',) for d in r['docks']]
    pair = min(((survival_fit._box_point_distance(a, p), a['name'], b['name']) for i, a in enumerate(dd) for b in dd[i+1:] if a['shape'] == b['shape'] == 'box'
                for p in _points(b)[0]), default=(math.inf, '', ''))
    rows['DGT-003']['dock_to_dock_m'] = pair[0]
    # Everything on the casing stays inside the BASELINE maximum body diameter, as the service fittings and survival envelopes do.
    rmax = s['ship']['body_diameter']['max']/2
    body = [it for it in ext if it['sp'] not in ('DS-10', 'DS-15')]
    top = max(math.hypot(p[1], p[2])+_points(it)[1] for it in body for p in _points(it)[0])
    rows['DGT-003']['casing_top_radius_m'] = top; rows['DGT-003']['body_max_radius_m'] = rmax
    if top > rmax+1e-9:
        fails.append(f'DGT-003 casing hardware reaches r {top:.3f} m, outside the {2*rmax:g} m maximum body diameter')
    if pair[0] < clr-1e-9:
        fails.append(f'DGT-003 docks {pair[1]} and {pair[2]} {pair[0]:.3f} m apart')
    # Interior: storeroom cassettes inside their shelf cells, no two on one shelf cell (DS-01 / DS-09 since 15!A183 / A185 beside the SP-49 bay).
    store = [st['id'] for st in q['stations'] if st['anchor'] == 'storeroom']
    cells = {d['name']: tuple(round(d['cell_m'][k]-d['size'][k], 3) for k in range(3)) for st in store for d in by[st]['docks']}
    seen = {}
    for st in q['stations']:
        if st['anchor'] == 'storeroom':
            for j in st['shelves']:
                seen.setdefault((st['row'], st['segment'], st.get('bay', 1), j), []).append(st['id'])
    rows['interior'] = dict(storeroom_cell_spare_m=cells, sp49_bay_used_m3=sum(d['volume_m3'] for st in ('DS-02', 'DS-03', 'DS-04') for d in by[st]['docks']),
                            sp49_bay_m3=survival_fit.storeroom(s)[0]['volume_bay_m3'], trunk_cassettes=0)
    for k, v in cells.items():
        if min(v) < 0:
            fails.append(f'{k} does not fit its shelf cell {v}')
    for k, v in seen.items():
        if len(v) > 1:
            fails.append(f'storeroom shelf {k} shared by {v}')
    # Ring cassettes: route_fitout's sector screen covers them (sector_elements appends sector()).
    import route_fitout as rf
    for fn in {st['function'] for st in q['stations'] if st['anchor'] == 'sector'}:
        bad = [b for b in rf.sector_check(s, fn, rf.sector_elements(s, fn)) if 'Drone_' in b]
        fails += [f'{fn}: {b}' for b in bad]
    # DGT-004 (geometric part only): every dock's depth axis is radial or axial-aft, the storeroom aisle and trunk bore are untouched.
    rows['DGT-004'] = dict(latch_load='OPEN (unit mass OPEN)', peak_axial_g=1.5, docks=sum(len(r['docks'])+len(r['existing']) for r in recs),
                           aisle_m=sr.station(s)['aisle'], formula=q['latch_load']['formula'],
                           note='Dock latch must hold each unit at 1.5 g axial (DOP-03, 15!A186): rating, latch and load path OPEN.')
    rows['open_gates'] = GATES_OPEN
    return rows, fails


def contract(s, sources=None):
    """Rig block: fleet manifest, stations (vehicle-frame dock and unit boxes; ring-local ones by ring and function), the spine route and the
    gate statuses. Values are PROTOTYPE placements of an OPEN study inventory."""
    f = lambda v: round(v, 4)
    def box(q):
        if 'world_centre' not in q and 'centre' in q:      # a ring cassette: route_fitout element in its sector's frame
            return dict(name=q['name'], shape='sector_box', frame='SECTOR', center_m=[f(v) for v in q['centre']], size_m=[f(v) for v in q['size']])
        if q['shape'] == 'box':
            return dict(name=q['name'], shape='box', center_m=[f(v) for v in q['world_centre']], axes=[[f(v) for v in a] for a in q['axes']], size_m=[f(v) for v in q['size']])
        if q['shape'] == 'tube':
            return dict(name=q['name'], shape='cylinder', a_m=[f(v) for v in q['a']], b_m=[f(v) for v in q['b']], radius_m=f(q['r1']))
        return dict(name=q['name'], shape='rod', points_m=[[f(v) for v in p] for p in q['points'][::4]+[q['points'][-1]]], radius_m=f(q['radius']))
    recs = stations(s); r = spine_route(s); cl = classes(s)
    return dict(contract='WF_DRONE_FLEET', version=3, status='STUDY INVENTORY / PROTOTYPE PLACEMENT', source_refs=list(SOURCES),
                note='Owner 24 + 2 is STUDY only (TOC 05 row 41); 52 stations UNPLACED / CAD OPEN; 54 gates HOLD. Positions are Claude L2 anchors; mass, power, speed, reach, latch load OPEN.',
                classes=[dict(id=c['id'], name=c['name'], domain=c['domain'], active=c['active'], reserve=c['reserve'], envelope_m=c.get('envelope_m'),
                              mobility=c['mobility'], precedent=c.get('precedent'), mass_kg=None, power_W=None) for c in cl.values()],
                units=manifest(s),
                stations=[dict(id=x['id'], cls=x['cls'], role=x['role'], frame=x['frame'], anchor=x['anchor'], ring=x.get('ring'), function=x.get('function'),
                               docks=[box(d) for d in x['docks']], existing=[box(d) for d in x['existing']],
                               units=[box(u) | {'unit': u['unit']} if 'shape' in u else u for u in x['units']],
                               rails=[box(d) for d in x['rails']], operations=x['operations'], note=x['note']) for x in recs],
                spine_route=dict(azimuth_deg=f(math.degrees(r['azimuth'])), x0_m=f(r['x0']), x1_m=f(r['x1']), dock_x_m=[f(v) for v in r['dock_x']],
                                 surface_r_m=[[f(x), f(r['surface_r'](x))] for x in (r['x0'], r['x1'])], stop_reason='ring A sweep less ring_keepout_margin_m',
                                 operations='HOLD (15!A184: L2 route accepted; no traversal while hot blades operate)'),
                keepouts=keepouts(s), gates_open=GATES_OPEN, mass=None, power=None, speed=None,
                formulas=dict(latch_load=table(s)['latch_load']['formula'], energy=table(s)['power']['formula']))


def keepouts(s):
    """The drone keep-out rules, each bound to the rig's existing massless proxy volume (sim_rig WF_SIMPROXY_*) or ship datum, with the drone
    margin and the gap the L2 screen measured. The volumes are not duplicated as drone meshes; gates stay HOLD."""
    rows, _ = check(s); q = table(s); f = lambda v: round(v, 4)
    return [
        dict(gate='DGT-005', volume=['WF_SIMPROXY_RING_1_SWEEP', 'WF_SIMPROXY_RING_2_SWEEP'], margin_m=q['ring_keepout_margin_m'],
             measured_gap_m=f(rows['DGT-005']['ring_sweep_gap_m']), rule='no stationary dock, unit, rail or cable in a ring sweep (spinning or locked)'),
        dict(gate='DGT-007', volume=[f'WF_SIMPROXY_RADIATOR_{j:02}' for j in range(1, s['radiators']['count']+1)], margin_m=q['blade_clearance_m'],
             measured_gap_m=f(rows['DGT-007']['blade_gap_m']), rule=rows['DGT-007']['rule'], exempt='DS-11 units on their SP-51 root docks',
             thermal='the geometric gap is not a radiant heat duty: view factor, baffle, cooldown and retrieval OPEN (15!A184)'),
        dict(gate='DGT-006', volume=['WF_SIMPROXY_SHIELD'], margin_m=0.0, measured_gap_m=f(-rows['DGT-006']['forward_of_truss_aft_m']),
             rule=rows['DGT-006']['rule'], eye_port_gap_m={k: f(v) for k, v in rows['DGT-006']['eye_port_gap_m'].items()}),
        dict(gate='DGT-008', volume=['WF_SIMPROXY_PLUME_STUDY'], margin_m=0.0, datum_x_m=f(rows['DGT-008']['casing_start_x_m']),
             measured_gap_m=f(rows['DGT-008']['aftmost_x_m']-rows['DGT-008']['casing_start_x_m']),
             rule='nothing aft of the casing start (drive, thrust ring, nozzle, plume); field and radiation zones OPEN'),
    ]


if __name__ == '__main__':
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import spec
    s, *_ = spec.load()
    rows, fails = check(s)
    print(json.dumps({**rows, 'failures': fails}, indent=1, default=str))
    sys.exit(1 if fails else 0)
