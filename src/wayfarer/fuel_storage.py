"""S01/F01 fuel storage: the longitudinal tank farm (TANK-AXIAL, WORKING architecture, owner brief 2026-11-01; every dimension PROTOTYPE).

Function: hold the full-return propellant (operating_point.species: helium-3, deuterium, hydrogen; pass 7) as three separated cryogens in
straight cylindrical pressure vessels whose axes run parallel to the thrust axis, and bring each species to the drive's four feed run tanks.
- The farm sits in the Brow's shadow between ring B's service clearance and the Brow truss (X 87.0-115.6), the zone the two tori used. Thirteen
  vessels in two rings round the forward collar: nine of class L (13.5 m insulated envelope) on the outer ring, four of class M (11.0 m) on the
  inner ring. Every vessel is one barrel with 2:1 ellipsoidal heads inside a 0.30 m wall stack (shell, MLI, standoff). The lanes of the EVA
  airlock (50 deg) and both docking corridors (195, 315 deg) stay open the full length, and the outer vessels keep clear of the bypass girders
  and their Q38 panels (30, 150, 270 deg). Species never share a vessel: helium-3 in six outer vessels, hydrogen in three outer and two inner,
  deuterium in the opposite inner pair.
- Load path (PROTOTYPE judgment): under thrust the propellant settles aft, so each vessel stands on its aft head: a ring of insulating
  composite struts from the aft Y-ring (head/barrel joint) down to a seat ring on the aft thrust deck, a wheel of radial trusses (one under
  each vessel) cantilevered from the collar frame at X 84.9-86.7, aft of every vessel and 1.7 m clear of ring B's sweep. The forward end is
  guided laterally only (two sliding V-links per vessel; the barrel contracts ~0.1 m when cold): inner vessels to the collar, outer vessels
  to a longitudinal keel rail on their inboard side, the rails tied to the deck and to a forward hoop that is strutted to the collar.
- Transfer: each vessel's outlet is its aft apex (the sump under thrust) with an isolation valve; the outlets of a species join a ring main
  on the deck (two-way fed, so one segment can be isolated). Two trunks per species leave the ring mains, run out along the deck to the
  bypass radius, aft along the bypass girders, down the aft-spoke slot and aft in the keel lanes to the run tanks (the pass-7 routes, with
  the torus legs and their circumferential runs gone). Two cryocooler cold boxes per species sit on the deck's aft face.
- The body bay (X -67.5..43.5), which held the 27 curved helium-3 lobes, becomes the dry store: 54 standard rectangular containers on
  racks between the keel lanes (workshop, spares and cargo, S&E 13 "midship stationary service volume"), away from the cryogens.

Fixed: the operating point's inventory and densities, ring B's sweep and service clearance, the docking corridors and airlock, the bypass
collar, the Brow truss, the feed run tanks. OPEN: wall, insulation and support sizing beyond first order, cryocooler capacity and heat
rejection, hull penetrations, FEA, fatigue, PMDs for the coast.

    python3 src/wayfarer/fuel_storage.py      # fit screen: capacity against need, clearances
"""
import json
import math

import layout

TAU = 2*math.pi
SPECIES_TAG = {'helium-3': 'He3', 'deuterium': 'D2', 'hydrogen': 'H2'}
INV_KEY = {'helium-3': 'helium_3', 'deuterium': 'deuterium', 'hydrogen': 'hydrogen'}


def cfg(s):
    return s['fuel_storage']


def farm_cfg(s):
    return cfg(s)['farm']


def unit(deg):
    a = math.radians(deg)
    return math.cos(a), math.sin(a)


def lane_point(x, r, deg):
    c, sn = unit(deg)
    return (x, r*c, r*sn)


# ---------- inventory ------------------------------------------------------------------------------------------------

def inventory(s):
    """The mission propellant by species (kg): the full return of pass 7 (operating_point.species)."""
    import operating_point
    return operating_point.species(s)


def allowance(s):
    """Volume allowances (PROTOTYPE): ullage on the loaded liquid; residual (unusable) and boil-off reserve loaded on top of the mission."""
    f = cfg(s); a = f['allowance']
    return dict(ullage=f['ullage'], residual=a['residual'], boiloff_reserve=a['boiloff_reserve'])


def loaded_m3(s):
    """Liquid loaded per species (m3): the mission plus residual and boil-off reserve."""
    al = allowance(s); rho = cfg(s)['density_kg_m3']; inv = inventory(s)
    return {k: inv[k]/rho[k]*(1+al['residual']+al['boiloff_reserve']) for k in inv}


def need_m3(s):
    """Vessel capacity each species needs: the loaded liquid plus its ullage."""
    return {k: v*(1+cfg(s)['ullage']) for k, v in loaded_m3(s).items()}


def fill_max(s):
    return 1/(1+cfg(s)['ullage'])


# ---------- the farm ---------------------------------------------------------------------------------------------------

def span(s):
    f = farm_cfg(s)
    return layout.at(s, f['x_aft_apex']), layout.at(s, f['x_fwd_apex'])


def lane_halfwidth(s):
    """A lane's keep-out half-width: the docking corridor radius (prototype.dock_corridor_radius_m) plus the mechanical clearance."""
    p = s['prototype']
    return p['dock_corridor_radius_m']+p['mechanical_clearance_m']


def vessel_volume(a_env, length, wall, head_ratio):
    """Liquid volume of a vessel whose insulated envelope is radius a_env and apex-to-apex length `length`: the shell's inside (a_env less the
    wall stack) as a barrel plus two 2:1 ellipsoidal heads."""
    a = a_env-wall; h = head_ratio*a; Lc = length-2*wall-2*h
    return math.pi*a*a*Lc+2*(2/3)*math.pi*a*a*h


def tanks(s):
    """The thirteen vessels: name, species, ring, azimuth, axis radius, envelope and shell radii, apex and Y-ring stations, liquid volume.
    Names: Fuel_Tank_<ring><n>_<species> (O outer, I inner; numbered by azimuth from 0 deg)."""
    f = farm_cfg(s); x0, x1 = span(s); w, hr = f['wall_m'], f['head_ratio']; out = []
    rows = sorted(f['tanks'], key=lambda t: (t['ring'] != 'outer', t['azimuth_deg']))
    count = {}
    for t in rows:
        ring = f['rings'][t['ring']]; cls = f['classes'][ring['class']]; a_env = cls['envelope_radius_m']; a = a_env-w
        k = count[t['ring']] = count.get(t['ring'], 0)+1; tag = 'O' if t['ring'] == 'outer' else 'I'
        c = unit(t['azimuth_deg']); R = ring['radius_m']
        out.append(dict(name=f"Fuel_Tank_{tag}{k}_{SPECIES_TAG[t['species']]}", id=f'{tag}{k}', species=t['species'], ring=t['ring'],
                        tank_class=ring['class'], azimuth_deg=t['azimuth_deg'], R=R, y=R*c[0], z=R*c[1], a_env=a_env, a=a,
                        head=hr*a, x0=x0, x1=x1, x_shell=(x0+w, x1-w), y_ring=(x0+w+hr*a, x1-w-hr*a),
                        liquid_m3=vessel_volume(a_env, x1-x0, w, hr), length=x1-x0))
    return out


def by_species(s):
    out = {}
    for t in tanks(s):
        out.setdefault(t['species'], []).append(t)
    return out


def capacity_m3(s):
    return {INV_KEY[sp]: sum(t['liquid_m3'] for t in ts) for sp, ts in by_species(s).items()}


# ---------- aft thrust deck, skirts, forward guides -------------------------------------------------------------------

def deck(s):
    """The aft thrust deck: X span, collar radius at its root, and one radial truss under each vessel from the collar to the vessel's seat
    ring's far edge, two chords (aft and forward faces) laced by diagonals. Hoops tie the trusses at the inner and outer seat circles."""
    import hull_geometry
    d = farm_cfg(s)['deck']; x0, x1 = layout.at(s, d['x_aft']), layout.at(s, d['x_fwd']); m = d['chord_radius_m']
    xa, xf = x0+m, x1-m; root = hull_geometry.radius_at(s, (x0+x1)/2)+d['root_standoff_m']+m; out = []   # the root vertical clears the skin
    for t in tanks(s):
        tip = t['R']+d['seat_fraction']*t['a']+d['tip_overhang_m']
        n = max(2, math.ceil((tip-root)/d['panel_m'])); rs = [root+(tip-root)*i/n for i in range(n+1)]
        members = [(lane_point(xa, root, t['azimuth_deg']), lane_point(xa, tip, t['azimuth_deg'])),
                   (lane_point(xf, root, t['azimuth_deg']), lane_point(xf, tip, t['azimuth_deg']))]
        for i, r in enumerate(rs):
            members.append((lane_point(xa, r, t['azimuth_deg']), lane_point(xf, r, t['azimuth_deg'])))
            if i:
                lo, hi = (xa, xf) if i % 2 else (xf, xa)
                members.append((lane_point(lo, rs[i-1], t['azimuth_deg']), lane_point(hi, r, t['azimuth_deg'])))
        out.append(dict(name=f"Fuel_Deck_Truss_{t['id']}", tank=t['name'], azimuth_deg=t['azimuth_deg'], root=root, tip=tip, members=members,
                        radius=m, depth=xf-xa, R=t['R']))
    hoops = []
    for ring, key in (('inner', 'Inner'), ('outer', 'Outer')):
        r = farm_cfg(s)['rings'][ring]['radius_m']
        for face, x in (('Aft', xa), ('Fwd', xf)):
            hoops.append(dict(name=f'Fuel_Deck_Hoop_{key}_{face}', x=x, r=r, radius=m*d['hoop_fraction']))
    return dict(x0=x0, x1=x1, xa=xa, xf=xf, root=root, trusses=out, hoops=hoops, chord_radius=m)


def collar_ties(s):
    """Two struts per outer deck truss from its tip nodes (aft and forward chord) to the bypass collar's forward hoop at the truss azimuth."""
    import forward_shield
    d = farm_cfg(s)['deck']; hp = {h['name']: h for h in forward_shield.bypass_collar(s)['hoops']}['Bypass_Hoop_Fwd']; out = []
    for tr in deck(s)['trusses']:
        if tr['R'] < farm_cfg(s)['rings']['outer']['radius_m']-1e-6:
            continue
        foot = lane_point(hp['x'], hp['r'], tr['azimuth_deg']); tid = tr['name'].rsplit('_', 1)[1]
        out.append(dict(name=f'Fuel_Deck_Collar_Tie_{tid}', truss=tr['name'], tank=tr['tank'], azimuth_deg=tr['azimuth_deg'], foot=foot,
                        members=[(tr['members'][0][1], foot), (tr['members'][1][1], foot)], radius=d['collar_tie_radius_m']))
    return out


def ring_lacing(s):
    """Diagonal lacing on the r of the bypass collar's hoops between its mid and forward hoops, making them a deep ring girder (Warren)."""
    import forward_shield
    q = farm_cfg(s)['deck']['ring_lacing']; hp = {h['name']: h for h in forward_shield.bypass_collar(s)['hoops']}
    a, b = hp['Bypass_Hoop_Mid'], hp['Bypass_Hoop_Fwd']; n = q['panels']; r = b['r']
    members = [(lane_point(a['x'] if k % 2 == 0 else b['x'], r, 360*k/n), lane_point(b['x'] if k % 2 == 0 else a['x'], r, 360*(k+1)/n)) for k in range(n)]
    return dict(name='Fuel_Deck_Ring_Lacing', r=r, x0=a['x'], x1=b['x'], depth=b['x']-a['x'], panels=n, members=members, radius=q['radius_m'])


def seat(s, t):
    """A vessel's seat ring on the deck: centred on its axis on the deck's forward face, radius seat_fraction x the shell radius."""
    d = farm_cfg(s)['deck']; dk = deck(s)
    return dict(x=dk['x1']+d['seat_height_m'], r=d['seat_fraction']*t['a'])


def skirt_struts(s, t):
    """The aft support: n_struts insulating composite struts in V-pairs from the seat ring to the aft Y-ring (the head/barrel joint)."""
    k = farm_cfg(s)['skirt']; st = seat(s, t); n = k['struts']; out = []
    ux, uz = unit(t['azimuth_deg'])
    def p(x, r, phi):          # point on a circle of radius r about the vessel axis at angle phi (local frame: radial, tangential)
        return (x, t['y']+r*(math.cos(phi)*ux-math.sin(phi)*uz), t['z']+r*(math.cos(phi)*uz+math.sin(phi)*ux))
    for i in range(n//2):
        base = TAU*i/(n//2)
        for j, d in enumerate((-1, 1)):
            out.append(dict(a=p(st['x'], st['r'], base), b=p(t['y_ring'][0], t['a'], base+d*math.pi/(n//2)*k['spread']), radius=k['radius_m']))
    return out


def keel_rails(s):
    """One longitudinal keel rail on the inboard side of each outer vessel, from the deck's forward face to the forward hoop."""
    g = farm_cfg(s)['guides']; x0 = deck(s)['x1']; x1 = layout.at(s, g['hoop_x'])
    return [dict(name=f"Fuel_Keel_Rail_{t['id']}", tank=t['name'], a=lane_point(x0, g['rail_r_m'], t['azimuth_deg']),
                 b=lane_point(x1, g['rail_r_m'], t['azimuth_deg']), radius=g['rail_radius_m'])
            for t in tanks(s) if t['ring'] == 'outer']


def forward_hoop(s):
    """The forward hoop on the keel-rail circle and its ties to the collar at tie_deg (clear of the inner vessels and the lanes)."""
    import hull_geometry
    g = farm_cfg(s)['guides']; x = layout.at(s, g['hoop_x']); hull = hull_geometry.radius_at(s, x)
    ties = [dict(name=f'Fuel_Forward_Tie_{k}', a=lane_point(x, hull+g['tie_root_standoff_m'], deg), b=lane_point(x, g['rail_r_m'], deg),
                 radius=g['rail_radius_m']) for k, deg in enumerate(g['tie_deg'], 1)]
    return dict(name='Fuel_Forward_Hoop', x=x, r=g['rail_r_m'], radius=g['rail_radius_m'], ties=ties)


def forward_links(s, t):
    """Two sliding V-links from the forward Y-ring's inboard side: to the collar (inner vessels) or to the vessel's keel rail (outer)."""
    import hull_geometry
    g = farm_cfg(s)['guides']; x = t['y_ring'][1]; ux, uz = unit(t['azimuth_deg']); out = []
    r_in = (hull_geometry.radius_at(s, x-g['link_rake_m'])+g['tie_root_standoff_m']+g['link_radius_m']) if t['ring'] == 'inner' else g['rail_r_m']
    for d in (-1, 1):
        phi = math.radians(180+d*g['link_spread_deg'])           # on the inboard side of the vessel
        a = (x, t['y']+t['a']*(math.cos(phi)*ux-math.sin(phi)*uz), t['z']+t['a']*(math.cos(phi)*uz+math.sin(phi)*ux))
        b = lane_point(x-g['link_rake_m'], r_in, t['azimuth_deg']+d*math.degrees(g['link_foot_m']/r_in))
        out.append(dict(a=a, b=b, radius=g['link_radius_m']))
    return out


# ---------- manifolds, valves, cryocoolers, trunks, run tanks ---------------------------------------------------------

def ring_mains(s):
    """One ring main per species and ring on the deck's forward face at the ring radius, each at its own X so they never cross."""
    m = farm_cfg(s)['manifold']; dk = deck(s); out = []
    for sp, ts in by_species(s).items():
        for ring in sorted({t['ring'] for t in ts}):
            r = farm_cfg(s)['rings'][ring]['radius_m']
            out.append(dict(name=f"Fuel_Ring_Main_{SPECIES_TAG[sp]}_{'O' if ring == 'outer' else 'I'}", species=sp, ring=ring, r=r,
                            x=dk['x1']+m['x_offset_m'][SPECIES_TAG[sp]], radius=m['line_radius_m']))
    return out


def outlets(s):
    """Each vessel's outlet: a drop line from its aft apex to its species' ring main, with an isolation valve box on it."""
    mains = {(rm['species'], rm['ring']): rm for rm in ring_mains(s)}; v = farm_cfg(s)['manifold']; out = []
    for t in tanks(s):
        rm = mains[(t['species'], t['ring'])]; apex = (t['x0'], t['y'], t['z']); low = (rm['x'], t['y'], t['z'])
        out.append(dict(name=f"Fuel_Outlet_{t['id']}_{SPECIES_TAG[t['species']]}", tank=t['name'], species=t['species'], points=[apex, low],
                        radius=v['line_radius_m'], valve=dict(name=f"Fuel_Valve_{t['id']}", x=(apex[0]+low[0])/2, y=t['y'], z=t['z'],
                                                             size=v['valve_box_m'])))
    return out


def cryocoolers(s):
    """Two cold boxes per species (A/B) on the deck's aft face beside the species' trunk lane (lift, power and heat rejection OPEN)."""
    q = farm_cfg(s)['cryocooler']; dk = deck(s); out = []
    for sp, lane in q['lane_deg'].items():
        for tag, d in (('A', -1), ('B', 1)):
            out.append(dict(name=f'Fuel_Cryocooler_{sp}_{tag}', species=sp, x=dk['x0']-q['length_m']/2-q['standoff_m'],
                            azimuth=math.radians(lane+d*q['offset_deg']), r0=q['r0_m'], r1=q['r1_m'], width=q['width_m'], length=q['length_m']))
    return out


def run_tanks(s):
    """The four feed run tanks ahead of the shadow shield (prototype.tank_*), quadrant order of drive_hot_section.TANK_QUADRANTS."""
    p = s['prototype']; c = layout.at(s, p['tank_center_x']); o = p['tank_offset_m']; out = []
    for j, (yy, zz) in enumerate([(1, 1), (-1, 1), (-1, -1), (1, -1)], 1):
        out.append(dict(name=f'Feed_Run_Tank_{j:02}', x0=c-p['tank_length_m']/2, x1=c+p['tank_length_m']/2, y=yy*o, z=zz*o, radius=p['tank_radius_m']))
    return out


def transfer_lines(s):
    """Two trunks per species from its ring main to its run tank. The exterior leg leaves the ring main at the trunk azimuth (the species'
    lane plus its offset), runs out along the deck to bypass_r_m (outside both rings' swept radius, inside the bypass collar's inner chord),
    aft along the collar to its aft frame, down beside the aft spoke in the slot between the radiator blade front and ring A, aft over the
    hull skin to the penetration station and stops hull_clearance_m off the skin. The interior leg starts the same distance inside it (the
    penetration is an OPEN interface), runs at lane_r_m on the trunk azimuth and ends standoff_m off its run tank."""
    import eva_route
    import forward_shield
    f = cfg(s); tl = f['transfer']; tanks_ = {t['name']: t for t in run_tanks(s)}
    mains = {}
    for rm in ring_mains(s):
        if rm['species'] not in mains or rm['ring'] == 'outer':
            mains[rm['species']] = rm
    col = forward_shield.bypass_collar(s); x_slot = col['stations']['aft']+tl['slot_offset_m']; x_pen = x_slot+tl['penetration_offset_m']
    hull_r = eva_route.body_radius(s, x_pen); clr = tl['hull_clearance_m']; run_r = hull_r+tl['hull_run_m']
    out = []
    for ln in tl['lines']:
        deg = ln['lane_deg']+ln['offset_deg']; tank = tanks_[ln['tank']]; lane_r = tl['lane_r_m']; rm = mains[ln['species']]
        x_end = tank['x1']-tl['tank_overlap_m']
        lane_end = lane_point(x_end, lane_r, deg)
        ty, tz = lane_end[1]-tank['y'], lane_end[2]-tank['z']; d = math.hypot(ty, tz); k = (tank['radius']+tl['standoff_m'])/d
        tail = [lane_end, (x_end, tank['y']+ty*k, tank['z']+tz*k)]
        base = dict(species=ln['species'], source=rm['name'], tank=ln['tank'], radius=tl['line_radius_m'])
        ext = [lane_point(rm['x'], rm['r'], deg), lane_point(rm['x'], tl['bypass_r_m'], deg), lane_point(x_slot, tl['bypass_r_m'], deg),
               lane_point(x_slot, run_r, deg), lane_point(x_pen, run_r, deg), lane_point(x_pen, hull_r+clr, deg)]
        out.append(dict(base, name=ln['name']+'_Ext', points=ext, leg='exterior'))
        out.append(dict(base, name=ln['name'], points=[lane_point(x_pen, hull_r-clr, deg), lane_point(x_pen, lane_r, deg)]+tail, leg='interior',
                        hull_penetration=lane_point(x_pen, hull_r, deg)))
    return out


# ---------- body bay: dry store ----------------------------------------------------------------------------------------

def body_modules(s):
    b = cfg(s)['body']; x0 = layout.at(s, b['bay_aft_x'])
    return [dict(index=m, x0=x0+o, x1=x0+o+b['module_length_m']) for m, o in enumerate(b['module_offsets_m'])]


def dry_containers(s):
    """Standard rectangular containers on racks in each body module, one rack per sector between the keel lanes (centred on the lane
    bisectors), `per_module` containers along X. Box: X span, radial r0..r1 on the bisector, width across it."""
    q = cfg(s)['body']['dry_store']; out = []
    for m in body_modules(s):
        L = (m['x1']-m['x0']-q['end_gap_m']*2-(q['per_module']-1)*q['between_m'])/q['per_module']
        for k, lane in enumerate(cfg(s)['body']['keel_lanes_deg'], 1):
            mid = lane+60.0
            for j in range(q['per_module']):
                x0 = m['x0']+q['end_gap_m']+j*(L+q['between_m'])
                out.append(dict(name=f"Dry_Store_M{m['index']+1}_S{k}_{j+1}", module=m['index']+1, sector=k, x0=x0, x1=x0+L, r0=q['r0_m'],
                                r1=q['r1_m'], width=q['width_m'], azimuth_deg=mid, volume_m3=L*(q['r1_m']-q['r0_m'])*q['width_m']))
    return out


# ---------- fit screen ------------------------------------------------------------------------------------------------

def _segdist2(p, a, b):
    ax, ay = a; bx, by = b; px, py = p; dx, dy = bx-ax, by-ay
    t = max(0.0, min(1.0, ((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy)))
    return math.hypot(px-ax-t*dx, py-ay-t*dy)


def _seg3(p, a, b):
    d = [b[i]-a[i] for i in range(3)]; L2 = sum(x*x for x in d) or 1e-12
    t = max(0.0, min(1.0, sum((p[i]-a[i])*d[i] for i in range(3))/L2))
    return math.dist(p, [a[i]+t*d[i] for i in range(3)])


def clearances(s):
    """Clearances (m) of every vessel envelope: to the other vessels, the lanes, the bypass girders' Q38 panels, ring B's sweep (the deck),
    the collar, the Brow truss and the EYE service sleds; and the radial reach."""
    import habitat_ring
    import hull_geometry
    import forward_shield
    f = farm_cfg(s); ts = tanks(s); W = lane_halfwidth(s); out = {}
    pair = min(math.hypot(a['y']-b['y'], a['z']-b['z'])-a['a_env']-b['a_env'] for i, a in enumerate(ts) for b in ts[i+1:])
    out['vessel_to_vessel'] = pair
    lanes = {'airlock': s['prototype'].get('airlock_angle_deg', 50.0)}
    for q in hull_geometry.dock_corridors(s):
        lanes[q['name']] = math.degrees(q['theta']) % 360
    for name, deg in lanes.items():
        c, sn = unit(deg)
        out[f'lane_{name}'] = min(_segdist2((t['y'], t['z']), (0.0, 0.0), (60*c, 60*sn))-t['a_env']-W for t in ts)
    g = f['girder']; worst = 1e9
    for deg in g['azimuth_deg']:
        c, sn = unit(deg)
        for t in ts:
            worst = min(worst, _segdist2((t['y'], t['z']), (g['r0_m']*c, g['r0_m']*sn), (g['r1_m']*c, g['r1_m']*sn))-t['a_env'])
    out['girder_panels'] = worst
    ring_front = max(habitat_ring.centers(s))+habitat_ring.sweep_half(s)
    out['deck_to_ring_B_sweep'] = deck(s)['x0']-ring_front
    out['collar'] = min(t['R']-t['a_env']-hull_geometry.radius_at(s, t['x0']) for t in ts)
    out['brow_truss'] = min(forward_shield.truss_aft_at(s, r)-t['x1'] for t in ts for r in (t['R']-t['a_env'], t['R'], t['R']+t['a_env']))
    sled = f['eye_sled_x']
    out['eye_sleds'] = layout.at(s, sled)-max(t['x1'] for t in ts)
    out['reach_m'] = max(t['R']+t['a_env'] for t in ts)
    return out


def screen(s):
    n, cap = need_m3(s), capacity_m3(s); ts = tanks(s); x0, x1 = span(s)
    return dict(
        status='PROTOTYPE fit screen (TANK-AXIAL, owner brief 2026-11-01); wall, supports, boil-off and mass first order only',
        inventory_t={k: round(v/1e3, 1) for k, v in inventory(s).items()}, allowance=allowance(s),
        need_m3={k: round(v, 1) for k, v in n.items()}, capacity_m3={k: round(v, 1) for k, v in cap.items()},
        margin={k: round(cap[k]/n[k]-1, 4) for k in n},
        farm=dict(x=[round(x0, 2), round(x1, 2)], length_m=round(x1-x0, 2), vessels=len(ts),
                  classes={c: dict(count=sum(t['tank_class'] == c for t in ts), envelope_d_m=2*farm_cfg(s)['classes'][c]['envelope_radius_m'],
                                   liquid_m3=round(next(t['liquid_m3'] for t in ts if t['tank_class'] == c), 1))
                           for c in sorted({t['tank_class'] for t in ts})},
                  tanks=[dict(name=t['name'], azimuth_deg=t['azimuth_deg'], R=t['R'], liquid_m3=round(t['liquid_m3'], 1)) for t in ts]),
        clearances_m={k: round(v, 3) for k, v in clearances(s).items()},
        dry_store=dict(containers=len(dry_containers(s)), volume_m3=round(sum(c['volume_m3'] for c in dry_containers(s)), 1)),
        transfer=[dict(name=l['name'], length_m=round(sum(math.dist(a, b) for a, b in zip(l['points'], l['points'][1:])), 1)) for l in transfer_lines(s)])


def check(s):
    """Physical invariants: each species fits its vessels with its allowances, vessels keep their gap, the lanes, the girder panels, ring B's
    service clearance (the deck), the collar and the Brow truss."""
    r = screen(s); f = farm_cfg(s); c = r['clearances_m']; errs = []
    for k, m in r['margin'].items():
        if m < 0:
            errs.append(f'{k}: capacity short by {-m:.1%}')
    if c['vessel_to_vessel'] < f['gap_m']-1e-3:
        errs.append(f"vessels {c['vessel_to_vessel']} m apart (< {f['gap_m']})")
    for k, v in c.items():
        if k.startswith('lane_') and v < -1e-3:
            errs.append(f'{k}: a vessel enters the lane by {-v:.2f} m')
    if c['girder_panels'] < f['girder']['clearance_m']-1e-3:
        errs.append('a vessel within the girder-panel clearance')
    if c['deck_to_ring_B_sweep'] < s['habitat']['ring_service_clearance']['min_m']:
        errs.append('thrust deck inside ring B service clearance')
    if c['collar'] < f['collar_clearance_m']-1e-3:
        errs.append('a vessel within the collar clearance')
    if c['brow_truss'] < f['truss_clearance_m']-1e-3 or c['eye_sleds'] < f['truss_clearance_m']-1e-3:
        errs.append('a vessel within the Brow truss / EYE sled clearance')
    return errs


if __name__ == '__main__':
    import spec
    s = spec.load()[0]
    print(json.dumps(screen(s), indent=1)); e = check(s); print('check', e or 'PASS')
