"""DRONE-001 DGT-009: route graph and coverage map of the seven mobile classes and the two fixed arms (S&E 54 DGT-009). Pure standard library.

Each class gets the declared jobs of 51 column J and the travel rules of 52 column G / 51 column M / 53, mapped onto geometry that exists:
- edges: ROUTED (modelled geometry the class may use, with its length and the unit's swept clearance), CARRIED (the crew carries the unit
  along the crew route; 52 DS-02..04 G "carry / deployment by human route only"), HOLD (the owner has not designed the path, a raceway, a
  transfer or a shielded aft path) and PROHIBITED (a hard hold in 51 M / 53: hot blades, the ram face, rotating hubs, the trunk).
- jobs: each job's targets with the route status that reaches them and the reach a tool would need from the route (straight-line, from the
  nearest route point to the target). Tool reach and arm reach are OPEN (51 G10/G11, 15!A186), so no job has a "tool reach" PASS; the reach
  numbers are what Claude supplies for the owner's sizing (15!A186 G).
Passing this screen is Claude L2 evidence only; DGT-009 stays HOLD (every route still needs reach, anchors, loads and the 53 operating gates).

    python3 src/wayfarer/drone_routes.py
"""
import math

import crew_transfer as ct
import drone_fleet as df
import eye_placement
import forward_shield
import habitat_interior
import layout
import storeroom as sr
import thermal_geometry

ROUTED, CARRIED, HOLD, PROHIBITED = 'ROUTED', 'CARRIED', 'HOLD', 'PROHIBITED'
FLY = ['COAST']                                    # 53 DOP-01..03: flyers in COAST only; LOW_THRUST docked by default; HIGH_POWER locked
DRIVE = ['COAST', 'DOCKED']                        # rovers / crawlers; LOW_THRUST only where separately certified (DOP-02)


def _f(v):
    return [round(x, 3) for x in v]


def _edge(a, b, status, why, length=None, modes=None, clearance=None, points=None):
    """`points`: the leg's polyline (vehicle frame, decimated) for the Ship Navigator's route overlay."""
    e = dict(a=a, b=b, status=status, why=why, length_m=None if length is None else round(length, 2), modes=modes or [],
             swept_clearance_m=None if clearance is None else round(clearance, 3))
    if points:
        e['points_m'] = [_f(q) for q in points[::max(1, len(points)//24)]]+([_f(points[-1])] if (len(points)-1) % max(1, len(points)//24) else [])
    return e


def _target(name, status, route_m=None, reach=None, note='', pair=None):
    """`pair`: (target point, the route / base point the reach is measured from), vehicle frame; |pair| == reach_needed_m."""
    q = dict(target=name, status=status, route_m=None if route_m is None else round(route_m, 2),
             reach_needed_m=None if reach is None else round(reach, 2), note=note)
    if pair:
        q['point_m'], q['from_m'] = _f(pair[0]), _f(pair[1])
    return q


def _near(p, lines):
    """Nearest point to p on any of the polylines: (distance, point)."""
    best = (math.inf, None)
    for pts in lines:
        for a, b in zip(pts, pts[1:]):
            e = [b[m]-a[m] for m in range(3)]; ee = sum(v*v for v in e) or 1e-12
            u = max(0.0, min(1.0, sum((p[m]-a[m])*e[m] for m in range(3))/ee)); q = tuple(a[m]+u*e[m] for m in range(3))
            d = math.dist(p, q)
            if d < best[0]:
                best = (d, q)
    return best


def _far(points, lines):
    """The farthest of `points` from the polylines: (distance, point, nearest route point)."""
    return max(((*_near(p, lines), p) for p in points), key=lambda r: r[0])


def _polyline_dist(p, pts):
    return min(ct.seg_dist(p, a, b) for a, b in zip(pts, pts[1:]))


def _along(pts):
    return ct.length(pts)


def _sweep(s, rail, size, axes_at, hosts=(), step=2.0):
    """Least clearance of the class's unit box swept along a rail (centre on the rail, `axes_at(point)`) to the existing exterior hardware,
    except its own hosts (the members it rides on); sampled every `step` metres along the rail."""
    obs = [o for o in df.obstacles(s) if not any(o['name'].startswith(h) for h in hosts)]
    ends = {o['name']: df._points(o)[0] for o in obs}
    best, where = math.inf, None; n = max(2, int(_along(rail)/step)); acc = [0.0]
    for a, b in zip(rail, rail[1:]):
        acc.append(acc[-1]+math.dist(a, b))
    for i in range(n+1):
        d = acc[-1]*i/n; k = max(j for j in range(len(acc)) if acc[j] <= d+1e-9); k = min(k, len(rail)-2)
        t = (d-acc[k])/max(acc[k+1]-acc[k], 1e-9); c = tuple(rail[k][m]+(rail[k+1][m]-rail[k][m])*t for m in range(3))
        u = df._box('sweep', '', '', c, axes_at(c), size)
        for o in obs:
            if min(math.dist(c, p) for p in ends[o['name']]) > 12.0:
                continue
            g = df._gap(u, o)
            if g < best:
                best, where = g, (o['name'], round(c[0], 2))
    return best, where


# ---------------------------------------------------------------- IVA

def _crew_ports(s):
    return {q['edge'][1]: q for q in ct.stationary(s) if q.get('edge')}


def _trunk_leg(ports, a, b):
    """Crew route between two trunk branches: both branch lengths plus the run along the trunk."""
    pa, pb = ports[a]['points'], ports[b]['points']
    return _along(pa)+abs(pa[0][0]-pb[0][0])+_along(pb)


def iva_flyer(s):
    """DR-IVA-01: survey in the stationary microgravity compartments (51 J2). Flight only inside a compartment in COAST; never in the 0.80 m
    crew trunk or a rotating ring (15!A183 H, 51 M2), so the trunk legs are CARRIED."""
    st = sr.station(s); ports = _crew_ports(s); c = df.classes(s)['DR-IVA-01']; u = df.unit_size(c)[0]
    clr = (st['aisle']-u)/2
    edges = [_edge('DS-01', 'STOREROOM', ROUTED, 'free flight in the SP-45 aisle (COAST); dock beside SP-49', st['x1']-st['x0'], FLY, clr),
             _edge('STOREROOM', 'TRUNK', CARRIED, 'no flight in the crowded 0.80 m crew trunk (15!A183 H)', _along(ports['STOREROOM']['points'])),
             _edge('TRUNK', 'REFUGE', CARRIED, 'carried along the trunk; flight in the refuge once inside (COAST)', _trunk_leg(ports, 'STOREROOM', 'REFUGE')),
             _edge('TRUNK', 'AIRLOCK_EVA', CARRIED, 'carried; airlock survey only with the chamber pressurized', _trunk_leg(ports, 'STOREROOM', 'AIRLOCK_EVA')),
             _edge('TRUNK', 'DOCK_PRIMARY', CARRIED, 'carried; DOCKED only', _trunk_leg(ports, 'STOREROOM', 'DOCK_PRIMARY')),
             _edge('TRUNK', 'VESTIBULE_1', PROHIBITED, 'no free flyer through the rotary vestibule (53 DOP-01)'),
             _edge('TRUNK', 'VESTIBULE_2', PROHIBITED, 'no free flyer through the rotary vestibule (53 DOP-01)')]
    jobs = {'atmosphere / visual / acoustic survey, leak localization (stationary compartments)': [
                _target('SP-45 storeroom', ROUTED, st['x1']-st['x0'], 0.0),
                _target('crew trunk', CARRIED, note='surveyed while carried; no flight in the trunk'),
                _target('storm refuge', CARRIED, _trunk_leg(ports, 'STOREROOM', 'REFUGE'), 0.0),
                _target('EVA airlock / entry chamber', CARRIED, _trunk_leg(ports, 'STOREROOM', 'AIRLOCK_EVA'), 0.0),
                _target('ring sectors', PROHIBITED, note='no flight during ring spin (51 M2); rings have their own rovers')],
            'inventory (SP-45 / SP-49 racks)': [_target('SP-45 racks incl. SP-49 bay', ROUTED, st['x1']-st['x0'], (st['aisle']-u)/2+.6,
                                                         note='camera standoff from the aisle centre to the rack back')]}
    return dict(cls='DR-IVA-01', stations=['DS-01', 'DS-02'], edges=edges, jobs=jobs)


def iva_rover(s):
    """DR-IVA-02: one rover per ring on its WORK_MEDICAL_OPS deck (DS-05/07); the sectors connect only through the crew tubes' ladders and the
    despun drum, which a rover cannot use (51 M3, 52 G4), so every other sector is CARRIED. Reserve DS-03 reaches a ring only by the crew route."""
    i = s['interior']; sec = habitat_interior.section(s); c = df.classes(s)['DR-IVA-02']; u = df.unit_size(c)[0]
    work = {z['name']: z for z in habitat_interior.zones(s, 'WORK_MEDICAL_OPS')}
    aisle_len = 2*(sec['length_m']/2-i['end_allowance_m']); clr = (i['aisle_m']-u)/2
    # Cassette (outer side wall) to the aisle through the gap between Couch_Lockers_2 and the Lab_Bench / Workbench.
    gap = work['Lab_Bench']['min'][0]-work['Couch_Lockers_2']['max'][0]; side = sec['half_width_deck_m']-i['aisle_m']/2
    ports = _crew_ports(s); edges = []; jobs = {'small delivery within the ring': [], 'Garden services': [], 'replace accessible cartridges': []}
    for j, ring, dock in ((1, 'A', 'DS-05'), (2, 'B', 'DS-07')):
        w = f'SECTOR_{j}_WORK'
        edges += [_edge(dock, w, ROUTED, 'floor cassette to the aisle through the side gap', side, DRIVE, (gap-u)/2),
                  _edge(w, f'{w}_AISLE', ROUTED, 'along the 0.9 m centre aisle (ring floor; traction under spin OPEN)', aisle_len, DRIVE, clr),
                  _edge(w, f'SECTOR_{j}_GARDEN', CARRIED, 'crew tube ladders and the despun drum: no rover passage (51 M3)'),
                  _edge(w, f'SECTOR_{j}_HABITATION', CARRIED, 'crew tube ladders and the despun drum: no rover passage (51 M3)')]
        jobs['small delivery within the ring'] += [_target(f'ring {ring} WORK_MEDICAL_OPS benches, ops stations, medical stowage', ROUTED, side+aisle_len, None),
                                                  _target(f'ring {ring} HABITATION', CARRIED)]
        jobs['Garden services'].append(_target(f'ring {ring} Garden rack and mess', CARRIED, note='the rover is docked in WORK_MEDICAL_OPS'))
        jobs['replace accessible cartridges'].append(_target(f'ring {ring} ECLSS bay (Garden sector)', CARRIED,
                                                              note='cartridge handling force and reach OPEN'))
    edges.append(_edge('DS-03', 'VESTIBULE_1 / VESTIBULE_2', CARRIED, 'reserve deployed by the crew route only (52 G4); ring B port Ø 1.0 m, 0.90 m restriction OPEN',
                       _trunk_leg(ports, 'STOREROOM', 'VESTIBULE_1')))
    return dict(cls='DR-IVA-02', stations=['DS-05', 'DS-07', 'DS-03'], edges=edges, jobs=jobs)


def iva_crawler(s):
    """DR-IVA-03: designed duct / cable raceways only (51 M4); no raceway geometry exists (15!A185), so every crawl is HOLD; the cassettes
    are carried to a service port."""
    ports = _crew_ports(s)
    edges = [_edge('DS-06 / DS-08', 'ECLSS bay conduits (each ring)', HOLD, 'designed raceway geometry OPEN; Garden bio isolation (52 I7)'),
             _edge('DS-09', 'stationary spine instrument conduits', HOLD, 'conduits outside the crew walk path OPEN (15!A185); not the 0.80 m trunk'),
             _edge('DS-09 / DS-04', 'service port', CARRIED, 'carried from the SP-49 area to a designated service port (52 G5)', _along(ports['STOREROOM']['points'])),
             _edge('crew trunk', 'crawl', PROHIBITED, 'no crawlers in the 0.80 m clear crew trunk (15!A185)')]
    jobs = {'conduits, leak detection, cameras, accessible sensor probes': [
        _target('ring A / B ECLSS bay conduits', HOLD, note='raceway OPEN'), _target('spine instrumentation conduits', HOLD, note='raceway OPEN')]}
    return dict(cls='DR-IVA-03', stations=['DS-06', 'DS-08', 'DS-09', 'DS-04'], edges=edges, jobs=jobs)


# ---------------------------------------------------------------- EVA

def eva_brow(s):
    """DR-EVA-01: four radial rails on the truss spokes' aft side (DS-10), rear side only. No circumferential transfer between rails (HOLD), no
    ram-face traversal (PROHIBITED). Reach needed from the nearest rail to each EYE well (r4 built; r16 / r24 study) and Crown bay, and the
    share of the rear backplane within a given reach of a rail."""
    st = next(q for q in df.table(s)['stations'] if q['id'] == 'DS-10'); c = df.classes(s)[st['cls']]
    rec = next(r for r in df.stations(s) if r['id'] == 'DS-10'); rails = [q['points'] for q in rec['rails'] if q['name'].endswith('_1')]
    cd = df.table(s)['cassette_depth_m']; edges = []; size = df.unit_size(c)
    for k, (deg, pts) in enumerate(zip(df._list(st['deg']), rails), 1):
        a = math.radians(deg)
        clr, at = _sweep(s, pts, size, lambda p, a=a: df._brow_axes(a), hosts=('Shield_Spoke_',))
        edges.append(_edge(f'DS-10_{k}', f'Brow rail {deg:g} deg', ROUTED, f'radial rail r {st["rail_r"][0]:g}-{st["rail_r"][1]:g} m on the spoke aft side; nearest {at[0] if at else "-"}',
                           _along(pts), DRIVE, clr, pts))
    edges += [_edge('Brow rail', 'Brow rail (next sector)', HOLD, 'no circumferential transfer rail on the backplane'),
              _edge('Brow rail', 'ram face', PROHIBITED, 'no exposed 0.016c ram-facing traversal (51 M5, Eye 46)')]
    def rail_x(rho):
        return forward_shield.truss_aft_at(s, rho)-cd/2
    def on_face(y, z):
        return (rail_x(math.hypot(y, z)), y, z)
    wells = []
    for R in eye_placement.RADII:
        v = eye_placement.variant(s, R); ws = [on_face(y, z) for y, z in forward_shield.well_centres(v)]
        d, q, p = _far(ws, rails)
        wells.append(_target(f'EYE wells r{R:g} ({"built" if R == 4 else "study"})', ROUTED, None, d, note=f'reach to the farthest of {len(ws)} wells', pair=(p, q)))
    cps = [on_face(cp['r0']*math.cos(cp['azimuth']), cp['r0']*math.sin(cp['azimuth'])) for cp in forward_shield.crown_ports(s)]
    crown = [_near(p, rails)[0] for p in cps]; cfar = _far(cps, rails)
    # Backplane share within reach of a rail, in plan (y, z): each rail is the radial segment at its spoke azimuth.
    r0, r1 = st['rail_r'][0], max(cp['r1'] for cp in forward_shield.crown_ports(s)); ra, rb = st['rail_r']
    def plan(rho, a):
        best = math.inf
        for deg in df._list(st['deg']):
            da = abs(ct.angle_diff(a, math.radians(deg))); along = rho*math.cos(da)
            if da < math.pi/2 and ra <= along <= rb:
                best = min(best, rho*math.sin(da))
            else:
                best = min(best, *(math.sqrt(rho*rho+e*e-2*rho*e*math.cos(da)) for e in (ra, rb)))
        return best
    cells = [(r0+(r1-r0)*(i+.5)/80, 2*math.pi*(k+.5)/360) for i in range(80) for k in range(360)]
    d2 = [(rho, plan(rho, a)) for rho, a in cells]; tot = sum(rho for rho, _ in d2)
    cover = {f'{reach:g}': round(sum(rho for rho, v in d2 if v <= reach)/tot, 3) for reach in (1.0, 2.0, 5.0, 10.0)}
    jobs = {'Brow rear-side panel service, damage survey': [_target(f'rear backplane r {r0:g}-{r1:g} m', ROUTED, None, None,
                                                                    note=f'share of the backplane within reach of a rail: {cover} (reach m: share)')],
            'EYE / Crown inspection': wells+[_target('Crown bays (12)', ROUTED, None, max(crown), note=f'nearest {min(crown):.2f} m, farthest {max(crown):.2f} m', pair=(cfar[2], cfar[1]))]}
    return dict(cls='DR-EVA-01', stations=['DS-10'], edges=edges, jobs=jobs, backplane_cover=cover)


def eva_radiator(s):
    """DR-EVA-02: the SP-51 track of each blade from its HOME dock (DS-11, first root); stops elsewhere unpowered (15!A182). Blade surface
    PROHIBITED (1800 K); the reserve DS-12 has no qualified transfer to a blade track (HOLD, 52 G13). Reach from the track to each root,
    stay, bay joint and the coolant feed end, on the blade's root edge."""
    import survival_fit
    d = thermal_geometry.blade_of(s); stn = thermal_geometry.stations(s, d); q = s['survival']
    tracks = {o['name']: o['points'] for o in survival_fit.exterior(s) if o['name'].startswith('Survival_Crawler_Rail_') and o['name'].endswith('_1')}
    edges = []; jobs = {'radiator root / joint / valve survey': [], 'cold-state cartridge exchange': []}
    c = df.classes(s)['DR-EVA-02']; size = df.unit_size(c)
    for j in range(s['radiators']['count']):
        ab = math.radians(s['prototype']['radiator_phase_deg']+j*120); pts = tracks[f'Survival_Crawler_Rail_{j}_1']
        clr, at = _sweep(s, pts, size, lambda p, ab=ab: df.he.axes_at(ab), hosts=('Survival_Crawler',))
        edges.append(_edge(f'DS-11 home dock {j}', f'SP-51 track blade {j}', ROUTED, f'track X {pts[0][0]:.1f} to {pts[-1][0]:.1f} m; seven stops, one powered; nearest {at[0] if at else "-"}',
                           _along(pts), ['DOCKED', 'COAST'], clr, pts))
        edge = lambda x: ct.radial(x, d['root_radius_m'], ab)
        survey = [('roots', x) for x in stn['roots']]+[('stays', x) for x in stn['stays']]+[('joints', jj['x']) for jj in thermal_geometry.bay_joints(s, d)]
        far = {}
        for kind, x in survey:
            far[kind] = max(far.get(kind, 0.0), _polyline_dist(edge(x), pts))
        fs = _far([edge(x) for _, x in survey], [pts])
        jobs['radiator root / joint / valve survey'].append(_target(f'blade {j}: roots, stays, 9 bay joints', ROUTED, _along(pts), max(far.values()),
                                                                     note=f'farthest per kind {dict((k, round(v, 2)) for k, v in far.items())}; cold state and view factor OPEN (DOP-08)',
                                                                     pair=(fs[2], fs[1])))
        fe = thermal_geometry.feed_end(s, d, ab); dn, qn = _near(fe, [pts])
        jobs['cold-state cartridge exchange'].append(_target(f'blade {j}: coolant feed end at the root', ROUTED, None, dn,
                                                              note='cartridge interface OPEN; thermal release HOLD', pair=(fe, qn)))
    edges += [_edge('SP-51 track', 'blade surface', PROHIBITED, 'no contact with the 1800 K blade (51 M6, DOP-08)'),
              _edge('DS-12 reserve', 'SP-51 track', HOLD, 'no qualified transfer from the casing reserve to a blade track (52 G13)'),
              _edge('SP-51 track', 'SP-51 track (next blade)', PROHIBITED, 'no arbitrary cross-blade traversal (52 I13)')]
    return dict(cls='DR-EVA-02', stations=['DS-11', 'DS-12'], edges=edges, jobs=jobs)


def eva_spine(s):
    """DR-EVA-03: the DS-13 casing track at 110 deg (operations HOLD, 15!A184); it stops 0.5 m short of ring A's sweep. Reach from the
    track to the hull fittings, survival masts, trackers and the other classes' docks (robot recovery, 51 J7)."""
    import survival_fit
    r = df.spine_route(s); pts = r['rails'][0]['points']; c = df.classes(s)['DR-EVA-03']; a = r['azimuth']
    clr, at = _sweep(s, pts, df.unit_size(c), lambda p: df.he.axes_at(a))
    edges = [_edge('DS-13 docks (3)', 'spine track', ROUTED, f'X {r["x0"]:.1f} to {r["x1"]:.1f} m at {math.degrees(a):.0f} deg, segmented at the docks; nearest {at[0] if at else "-"}',
                   _along(pts), DRIVE, clr, pts),
             _edge('spine track', 'ring A / B sweep', PROHIBITED, 'tracks never cross moving rings (51 M7)'),
             _edge('spine track', 'SP-51 tracks', HOLD, 'no transfer between the spine track and the blade tracks'),
             _edge('spine track', 'blade view', HOLD, 'no traversal while hot blades operate; view factor, baffle, cooldown OPEN (15!A184)')]
    ext = {o['name']: o for o in survival_fit.exterior(s)}
    def reach(o):
        return min(_polyline_dist(p, pts) for p in df._points(o)[0])
    def closest(items):
        best = min(((*_near(p, [pts]), p) for o in items for p in df._points(o)[0]), key=lambda r: r[0])
        return best[2], best[1]
    harness = [_target(n, ROUTED, None, reach(ext[n]), pair=closest([ext[n]])) for n in ('Survival_Lasercom_Mast', 'Survival_RF_Mast', 'Survival_Star_Tracker_1', 'Survival_Star_Tracker_2')]
    recs = {x['id']: x for x in df.stations(s)}
    rec_t = []
    for sid in ('DS-11', 'DS-12', 'DS-14', 'DS-16'):
        items = recs[sid]['docks']+recs[sid]['existing']
        worst = max(items, key=reach)
        rec_t.append(_target(f'{sid} docks', ROUTED, None, reach(worst), note='reach to the farthest dock of the station', pair=closest([worst])))
    rs = r['surface_r'](0.0)
    jobs = {'structural / harness inspection': harness+[_target('hull circumference at one X', ROUTED, None, math.pi*rs,
                                                                note='half the casing circumference: the far side of the hull from a single track (along the surface, not drawn)')],
            'small tools / parts delivery': [_target('along the track', ROUTED, _along(pts), 0.0)],
            'robot recovery': rec_t}
    return dict(cls='DR-EVA-03', stations=['DS-13'], edges=edges, jobs=jobs)


def eva_aft(s):
    """DR-EVA-04: the aft cradles (DS-14) sit forward of the casing start; every drive target lies aft of it, in the zone the DGT-008 keep-out
    closes. The shielded retained maintenance path (51 I8) is not designed: every route is HOLD, and PROHIBITED while the drive, field,
    plume, radiation or cryo states are live (DOP-09)."""
    x0 = layout.at(s, {'datum': 'RADIATOR_AFT', 'offset_m': 0.0}); ring = layout.at(s, s['prototype']['thrust_ring_x']); nozzle = layout.origin(s, 'AFT')
    cr = next(r for r in df.stations(s) if r['id'] == 'DS-14')['docks']; xc = min(q['world_centre'][0] for q in cr)
    c0 = min(cr, key=lambda q: q['world_centre'][0])['world_centre']; at = lambda x: (x, c0[1], c0[2])
    edges = [_edge('DS-14 cradles', 'casing aft end', ROUTED, 'on the casing, forward of the casing start', abs(xc-x0), DRIVE),
             _edge('casing aft end', 'drive / thrust ring / nozzle peripherals', HOLD, 'shielded retained maintenance path not designed (51 I8)'),
             _edge('casing aft end', 'drive zone (live)', PROHIBITED, 'drive on, plume, field, radiation, cryo => HOLD (52 I15, DOP-09)')]
    jobs = {'cold drive interfaces, cryogenic support, nozzle peripherals': [
        _target('thrust ring', HOLD, None, abs(xc-ring), note=f'X {ring:.2f} m, {abs(x0-ring):.2f} m aft of the casing start (axial distance)', pair=(at(ring), c0)),
        _target('nozzle exits', HOLD, None, abs(xc-nozzle), note=f'X {nozzle:.2f} m (axial distance)', pair=(at(nozzle), c0))]}
    return dict(cls='DR-EVA-04', stations=['DS-14'], edges=edges, jobs=jobs)


def arms(s):
    """DR-FIX-01/02: fixed bases, reach and load OPEN (51 G10/11). Reach each declared job would need from the base."""
    recs = {x['id']: x for x in df.stations(s)}
    def base(sid):
        q = recs[sid]['docks'][0]; return q['a']
    def far(p, items):
        return max(min(math.dist(p, x) for x in df._points(o)[0]) for o in items)
    def farpt(p, items):
        return max((min(df._points(o)[0], key=lambda x: math.dist(p, x)) for o in items), key=lambda x: math.dist(p, x))
    def farp(p, pts):
        return max(pts, key=lambda x: math.dist(p, x))
    f, b = base('DS-15'), base('DS-16')
    v = eye_placement.variant(s, 4); cd = df.table(s)['cassette_depth_m']
    wells = [(forward_shield.truss_aft_at(s, math.hypot(y, z))-cd, y, z) for y, z in forward_shield.well_centres(v)]
    rails = [q for q in recs['DS-10']['rails']]
    crowns = [ct.radial(forward_shield.truss_aft_at(s, cp['r0'])-cd, cp['r0'], cp['azimuth']) for cp in forward_shield.crown_ports(s)]
    d = thermal_geometry.blade_of(s); stn = thermal_geometry.stations(s, d)
    roots = [ct.radial(x, d['root_radius_m'], math.radians(s['prototype']['radiator_phase_deg']+j*120)) for j in range(s['radiators']['count']) for x in stn['roots']]
    return dict(cls='DR-FIX-01/02', stations=['DS-15', 'DS-16'], edges=[_edge('DS-15 / DS-16', 'arm envelope', HOLD, 'reach and load OPEN (51 G10/11, 15!A186)')], jobs={
        'DR-FIX-01: Brow / Crown / shield modules, stranded-crawler recovery': [
            _target('EYE wells r4', HOLD, None, max(math.dist(f, w) for w in wells), pair=(farp(f, wells), f)),
            _target('Brow rails (stranded crawler, farthest point)', HOLD, None, far(f, rails), pair=(farpt(f, rails), f)),
            _target('Crown bays', HOLD, None, max(math.dist(f, q) for q in crowns), note='cannot reach all of the 90 m shield (51 M10)', pair=(farp(f, crowns), f))],
        'DR-FIX-02: radiator roots, aft utilities, recoveries': [
            _target('radiator root stations (3 blades)', HOLD, None, max(math.dist(b, p) for p in roots), pair=(farp(b, roots), b)),
            _target('DS-14 aft cradles', HOLD, None, far(b, recs['DS-14']['docks']), pair=(farpt(b, recs['DS-14']['docks']), b))]})


def graph(s):
    return [iva_flyer(s), iva_rover(s), iva_crawler(s), eva_brow(s), eva_radiator(s), eva_spine(s), eva_aft(s), arms(s)]


def check(s):
    """Rows per class: edge and job-target counts by status, the least swept clearance on ROUTED edges. Fails only where a ROUTED edge's
    swept unit comes closer than the mechanical clearance to existing hardware."""
    clr = s['prototype']['mechanical_clearance_m']; rows = {}; fails = []
    for g in graph(s):
        e = {k: sum(x['status'] == k for x in g['edges']) for k in (ROUTED, CARRIED, HOLD, PROHIBITED)}
        t = [x for v in g['jobs'].values() for x in v]
        tj = {k: sum(x['status'] == k for x in t) for k in (ROUTED, CARRIED, HOLD, PROHIBITED)}
        sw = [x['swept_clearance_m'] for x in g['edges'] if x['status'] == ROUTED and x['swept_clearance_m'] is not None]
        rows[g['cls']] = dict(edges=e, targets=tj, jobs=len(g['jobs']), least_swept_clearance_m=min(sw) if sw else None,
                              routed_m=round(sum(x['length_m'] or 0 for x in g['edges'] if x['status'] == ROUTED), 1))
        for x in g['edges']:
            if x['status'] == ROUTED and x['swept_clearance_m'] is not None and x['swept_clearance_m'] < clr-1e-9:
                fails.append(f"{g['cls']} {x['a']} -> {x['b']}: swept unit {x['swept_clearance_m']} m from hardware ({x['why']})")
    rows['DGT-009'] = 'HOLD: tool and arm reach OPEN; routes are Claude L2 geometry (15!A186: owner sizes reach, mass and bus)'
    rows['DGT-019'] = {k: v for k, v in dgt019(s).items() if k != 'rows'}
    return rows, fails


def dgt019(s):
    """Owner 2026-10-17 (S&E 15!A201 OWN-DR-ROUTE, 54!A29 DGT-019, 98!A111): the five L2 route choices as a per-job gap matrix. Each row: the
    owner's choice, the means that does the job (an existing track, a fixed arm, or the crew carrying the robot), the route status and the
    reach the job still needs from that means (measured on this model by graph()). No job passes: end-effector reach, force, mass, power,
    thermal and anchors are OPEN for every robot (DGT-019 F), so every row keeps a deficit. Nothing is added: no rail, station or drone."""
    g = {c['cls']: c for c in graph(s)}
    def tg(cls, job, name=None):
        for j, ts in g[cls]['jobs'].items():
            if j.startswith(job):
                return [t for t in ts if name is None or t['target'].startswith(name)]
        raise KeyError((cls, job, name))
    def row(choice, job, means, t, deficit):
        need = t['reach_needed_m']
        return dict(choice=choice, job=job, target=t['target'], means=means, route_status=t['status'], route_m=t['route_m'], reach_needed_m=need,
                    deficit=deficit.format(need=need if need is not None else float('nan')), gate='HOLD')
    rows = []
    arm = 'fixed-arm reach and load OPEN (51 G10/11, 15!A186)'
    for t in tg('DR-FIX-01/02', 'DR-FIX-02', 'DS-14'):
        rows.append(row('a', 'aft utilities / DS-14 recovery', 'DR-FIX-02 arm at DS-16', t, 'arm must reach {need:.1f} m: ' + arm))
    for t in tg('DR-FIX-01/02', 'DR-FIX-02', 'radiator root'):
        rows.append(row('a', 'radiator root service', 'NOT DS-16 (owner: no 94 m root service from DS-16)', t,
                        '{need:.1f} m from DS-16 is excluded; roots go to DS-11 / DR-EVA-02 below'))
    for t in tg('DR-EVA-02', 'radiator root'):
        rows.append(row('a', 'radiator root inspection', 'DR-EVA-02 on its SP-51 track from DS-11 (cold state only)', t,
                        'tool reach {need:.2f} m from the track OPEN; never hot service of 1800 K blades'))
    for t in tg('DR-IVA-02', 'small delivery') + tg('DR-IVA-02', 'Garden') + tg('DR-IVA-02', 'replace'):
        rows.append(row('b', 'ring service', 'DR-IVA-02 sector-bound; crew carries it between sectors and rings', t,
                        'no robot route between sectors or rings (crew carry); manipulator reach and payload OPEN'))
    for t in tg('DR-EVA-03', 'structural'):
        far = t['target'].startswith('hull circumference')
        rows.append(row('c', 'hull / harness inspection', ('DR-FIX arm or crew EVA for the far side' if far else 'DR-EVA-03 on the one-sided 110 deg spine track'), t,
                        ('far side {need:.1f} m along the surface: not reachable from one 110 deg track; arm or crew EVA, reach OPEN' if far else
                         'tool reach {need:.2f} m from the track OPEN')))
    for t in tg('DR-EVA-03', 'robot recovery'):
        rows.append(row('d', 'remote dock recovery (DOP-14)', 'existing fixed arms or crew (DR-EVA-03 track as geometry reference)', t,
                        'recovery reach {need:.1f} m is a geometry demand, not a verified capacity; no magic reach'))
    for t in tg('DR-EVA-01', 'EYE') + tg('DR-FIX-01/02', 'DR-FIX-01'):
        rows.append(row('e', 'Brow / EYE / Crown service', 'Brow rear rail (DR-EVA-01) + DR-FIX-01 arm first; circumferential rails only if a verified gap requires',
                        t, 'reach {need:.1f} m OPEN (a geometry demand, not a verified robot capacity)'))
    counts = {k: sum(r['choice'] == k for r in rows) for k in 'abcde'}
    return dict(gate='DGT-019 HOLD / SELECTED L2 PLAN ONLY; DGT-009 HOLD', source='S&E 15!A201, 54!A29, 98!A111 (2026-10-17)',
                inventory='24 mobile + 2 fixed arms (study counts unchanged)', passes=0, rows=rows, rows_per_choice=counts,
                rule='every job keeps a deficit until end-effector reach, mass/power and anchor tests exist (98!A111 H)')


def contract(s):
    return dict(contract='WF_DRONE_ROUTES', version=2, dgt019=dgt019(s), gate='DGT-009 HOLD', status='CLAUDE L2 ROUTE / COVERAGE MAP, NOT A REACH OR SAFETY RELEASE',
                statuses={ROUTED: 'modelled geometry the class may use', CARRIED: 'crew carries the unit along the crew route',
                          HOLD: 'path, raceway, transfer or reach not designed / OPEN', PROHIBITED: 'hard hold in S&E 51 M / 53'},
                classes=graph(s))


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
