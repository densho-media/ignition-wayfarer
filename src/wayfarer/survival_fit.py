"""SP-46..54 survival envelopes and the Eye 50!A25:A30 terminals (12A A49:I57; 34!B110): PROTOTYPE envelopes inside existing spaces, each
with its installed (and, for the crawler, swept) volume, never a new room, pressure boundary or interface. Mass, power, heat, contents and
service stay OPEN in the owner rows; nothing here feeds a budget. Pure standard library.

- refuge(): the SP-48 service racks, the SP-50 triage kit and the SP-54 / Eye A30 hazard alarm in the storm refuge's end zones (vehicle frame,
  human_entry box format), clear of the port leg (routes R and E), the hoop rails and the twelve occupants' envelopes.
- sector(s, function): ring-sector elements in route_fitout's format (route_fitout.sector_elements appends them): the SP-50 overhead medical
  unit, the SP-47 incubator on the lab shelf, the SP-46 sealed waste collection point's door on the workbench cabinet (the cabinet is its
  envelope; collection only, processing belongs to the stationary machine-bay candidate, WK-HYBRID-2026-10-10, 15!I115) and an
  SP-54 hazard and cue panel in every sector's overhead zone.
- storeroom(): the SP-49 stock bay's placard in the SP-45 storeroom (vehicle frame): general clean stock only; cartridge exchange belongs to
  the stationary machine-bay candidate (15!C115, 12A I52).
- exterior(): the SP-53 / A25 lasercom and A26 RF terminals on masts, the A29 star trackers and the SP-51 crawler rails and docks.
- check(): the fit screen (clearances, the terminals' pointing cone, the sector screen) and the volumes. SP-52 waits on the owner.

    python3 src/wayfarer/survival_fit.py
"""
import math
import crew_transfer
import human_entry as he
import hull_geometry
import thermal_geometry


def table(s):
    return s['survival']


def env(name, sp, role, centre, axes, size, source='survival_spaces', **kw):
    """A PROTOTYPE envelope box: centre and (along, across, depth) axes in its frame, its installed volume."""
    return dict(dict(name=name, sp=sp, role=role, shape='box', world_centre=tuple(centre), axes=axes, size=tuple(size), volume_m3=size[0]*size[1]*size[2],
                     source_ref=source, geometry_status='PROTOTYPE'), **kw)


def refuge(s):
    q = table(s); h = s['human_entry']; r = he.refuge_station(s); rh = h['handrail_radius_m']; clr = s['prototype']['mechanical_clearance_m']; g = q['end_gap_m']
    out = []; r0, r1 = q['refuge_rack_radial_m']; a = r['th']+math.radians(q['refuge_rack_deg'])
    ends = (('Aft', r['cavity_x0']+g, r['hoop_x'][0]-rh-clr), ('Fwd', r['hoop_x'][1]+rh+clr, r['cavity_x1']-g))
    for tag, x0, x1 in ends:
        out.append(env(f'Survival_Refuge_Service_Rack_{tag}', 'SP-48', 'independent refuge service rack: stored gas, CO2 removal, filtration, water, survival bus (envelope)',
                       crew_transfer.radial((x0+x1)/2, (r0+r1)/2, a), he.axes_at(a), (x1-x0, q['refuge_rack_tangential_m'], r1-r0)))
    ax, tg, rd = q['refuge_triage_m']; a = r['th']+math.radians(q['refuge_triage_deg']); x0 = r['cavity_x0']+g
    out.append(env('Survival_Refuge_Triage_Kit', 'SP-50', 'refuge triage kit (envelope)', crew_transfer.radial(x0+ax/2, r0+rd/2, a), he.axes_at(a), (ax, tg, rd)))
    ax, tg, rd = q['refuge_alarm_m']; x1 = r['cavity_x1']-g
    out.append(env('Survival_Refuge_Hazard_Alarm', 'SP-54', 'radiation, event and hull-damage alarm on a separated safe-state link (Eye A30), refuge forward end cap',
                   crew_transfer.radial(x1-ax/2, q['refuge_alarm_radius_m'], r['th']), he.axes_at(r['th']), (ax, tg, rd), source='eye_survival_interface'))
    return out


def sector(s, function):
    """Ring-sector envelopes as route_fitout elements (sector frame); each carries sp and its installed volume."""
    import habitat_interior
    import route_fitout as rf
    import sector_whitebox as sw
    q = table(s); w = s['sector_whitebox']; sec = habitat_interior.section(s); c = sec['ceiling_y_m']; blocks = {b['name']: b for b in habitat_interior.zones(s, function)}
    I = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)); out = []

    def box(name, sp, fn, paint, lo, hi, volume=None, signage=False, text=None):
        size = tuple(hi[k]-lo[k] for k in range(3))
        el = rf.element(name, 'SPACER', fn, 'ENGINEERING_FLEXIBLE', paint, 'wbox', signage, centre=tuple((lo[k]+hi[k])/2 for k in range(3)), axes=I, size=size,
                        sp=sp, volume_m3=volume if volume is not None else size[0]*size[1]*size[2], source_ref='survival_spaces')
        if text:
            el['text'] = text
        out.append(el)
    xl = sec['length_m']/2-s['interior']['end_allowance_m']; ax, ay, az = q['alarm_panel_m']
    box('Survival_Sector_Alarm_Panel', 'SP-54', 'hazard and cue panel: radiation, CO2, noise, 0 g / 4 rpm / 1.5 g orientation cues (Eye A30 link)', 'bezel',
        (-xl-.10, c+.30, .50), (-xl-.10+ax, c+.30+ay, .50+az))
    if function == 'WORK_MEDICAL_OPS':
        b = blocks['Medical_Couch']; L, H, D = q['medical_overhead_m']; xm = (b['min'][0]+b['max'][0])/2; zm = (b['min'][2]+b['max'][2])/2
        box('Survival_Medical_Overhead_Unit', 'SP-50', 'overhead medical unit over the treatment couch: imaging, monitoring, lights (envelope)', 'cover',
            (xm-L/2, c+.04, zm-D/2), (xm+L/2, c+.04+H, zm+D/2))
        b = blocks['Lab_Bench']; n = sw.facing(b); back = b['min'][2] if n[2] > 0 else b['max'][2]; inward = 1.0 if n[2] > 0 else -1.0
        top = b['max'][1]-w['bench_height_m']-.64; L, H, D = q['incubator_m']
        z0, z1 = sorted((back+inward*.035, back+inward*(.035+D)))
        box('Survival_Micronutrient_Incubator', 'SP-47', 'sealed micronutrient incubator rack on the lab shelf (no calorie credit)', 'locker',
            (b['max'][0]-.05-L, top-H, z0), (b['max'][0]-.05, top, z1))
        b = blocks['Workbench']; n = sw.facing(b); k = 2 if n[2] else 0; front = b['max'][k] if n[k] > 0 else b['min'][k]; inward = -1.0 if n[k] > 0 else 1.0
        cab = (b['max'][0]-b['min'][0])*(w['bench_height_m']-.04)*(sw.depth(b)-.08)
        face = front+inward*.08; lo, hi = [b['min'][0]+.05, -w['bench_height_m']+.10, 0.0], [b['max'][0]-.05, -.08, 0.0]; lo[k], hi[k] = sorted((face, face-inward*.015))
        box('Survival_Waste_Station_Door', 'SP-46', 'sealed waste collection point in the workbench cabinet: door, own offgas filter (the cabinet is the envelope); collection only, not processing (WK-HYBRID, 15!I115)',
            'safety', tuple(lo), tuple(hi), volume=cab)
    return out


def storeroom(s):
    """SP-49: the general clean stock bay of the SP-45 storeroom, a placard on its rack front (the bay is the envelope); cartridge exchange is
    at the stationary machine-bay candidate (WK-HYBRID-2026-10-10)."""
    import storeroom as sr
    st = sr.station(s); rows = sr.rows(s); name, u0, u1, segs = rows[0]; a = st['phi']; bay = s['storeroom']['bay_max_m']
    t0 = -st['half']; tc = t0+bay/2; x = st['xf']+1.55; u = u0-.03
    _, eu, et = sr.frame(s); ex = (1.0, 0.0, 0.0); n = tuple(-v for v in eu)       # faces the aisle; text upright along +X (aft is the floor)
    return [env('Survival_Cartridge_Bay_Placard', 'SP-49', 'placard: SP-49 general nonhazardous stock and sealed spare cartridges (SP-49 allocation in SP-45; exchange at the stationary machine-bay candidate)', sr.world(s, x, u, tc),
                (et, ex, n), (.30, .09, .012), volume_m3=0.0, volume_bay_m3=bay*(u1-u0)*st['H'], text='SP-49 STOCK')]


def exterior(s):
    """Outside the hull: masts, terminals, trackers, crawler rails and docks (vehicle frame). Rods as (name, points, radius)."""
    q = table(s); out = []; d = thermal_geometry.blade_of(s)

    def mast(name, sp, deg, x, role, source):
        a = math.radians(deg); rh = hull_geometry.radius_at(s, x); top = rh+q['mast_height_m']
        out.append(dict(name=f'{name}_Mast', sp=sp, role=f'{role} mast', shape='rod', radius=q['mast_radius_m'],
                        points=[crew_transfer.radial(x, rh-.05, a), crew_transfer.radial(x, top, a)], source_ref=source, geometry_status='PROTOTYPE'))
        return a, top
    a, top = mast('Survival_Lasercom', 'SP-53', q['lasercom_deg'], q['terminal_x_m'], 'steerable lasercom terminal (Eye A25)', 'eye_survival_interface')
    L, W, D = q['lasercom_head_m']
    out.append(env('Survival_Lasercom_Head', 'SP-53', 'steerable lasercom terminal on its own pointing and supply (Eye A25)', crew_transfer.radial(q['terminal_x_m'], top+D/2, a),
                   he.axes_at(a), (L, W, D), source='eye_survival_interface', boresight=crew_transfer.radial(0.0, 1.0, a)))
    a, top = mast('Survival_RF', 'SP-53', q['rf_deg'], q['terminal_x_m'], 'low-rate RF fallback antenna (Eye A26)', 'eye_survival_interface')
    R = q['rf_dish_radius_m']
    out.append(dict(name='Survival_RF_Dish', sp='SP-53', role='low-rate RF dish and emergency transponder (Eye A26)', shape='tube', r0=0.0, r1=R,
                    a=crew_transfer.radial(q['terminal_x_m'], top, a), b=crew_transfer.radial(q['terminal_x_m'], top+.06, a), volume_m3=math.pi*R*R*.06,
                    source_ref='eye_survival_interface', geometry_status='PROTOTYPE', boresight=crew_transfer.radial(0.0, 1.0, a)))
    a = math.radians(q['tracker_deg']); L, W, D = q['tracker_m']
    for k, x in enumerate(q['tracker_x_m'], 1):
        rh = hull_geometry.radius_at(s, x)
        out.append(env(f'Survival_Star_Tracker_{k}', 'A29', 'independent star tracker (Eye A29)', crew_transfer.radial(x, rh+.05+D/2, a), he.axes_at(a), (L, W, D),
                       source='eye_survival_interface', boresight=crew_transfer.radial(0.0, 1.0, a)))
    # SP-51: per blade a two-rail track on the casing, offset from the blade plane, aft end to forward end less the end gap; a stop at each stay
    # and root station and at the forward end, of which only the first root's is the powered HOME dock (DS-11, 15!A182); the others are
    # unpowered track / tool stops; the crawler's swept box along the track.
    st = thermal_geometry.stations(s, d); g = q['crawler_rail_gauge_m']; x0, x1 = d['aft_x_m']+q['crawler_rail_end_gap_m'], d['front_x_m']-q['crawler_rail_end_gap_m']
    xs = [x0+(x1-x0)*k/40 for k in range(41)]
    for j in range(s['radiators']['count']):
        ab = math.radians(s['prototype']['radiator_phase_deg']+j*120)
        for side, dz in ((1, -g/2), (2, g/2)):
            pts = []
            for x in xs:
                rr = hull_geometry.radius_at(s, x)+q['crawler_rail_standoff_m']
                pts.append(crew_transfer.radial(x, rr, ab+(q['crawler_rail_offset_m']+dz)/rr))
            out.append(dict(name=f'Survival_Crawler_Rail_{j}_{side}', sp='SP-51', role='service crawler rail (unpressurized)', shape='rod', radius=q['crawler_rail_radius_m'],
                            points=pts, source_ref='survival_spaces', geometry_status='PROTOTYPE'))
        L, W, D = q['crawler_dock_m']
        home = sorted(st['roots']+st['stays']).index(min(st['roots']))+1        # 15!A182: one HOME dock per blade at its first root (DS-11)
        for n, x in enumerate(sorted(st['roots']+st['stays'])+[x1], 1):
            rr = hull_geometry.radius_at(s, x)+q['crawler_rail_standoff_m']; a = ab+q['crawler_rail_offset_m']/rr
            out.append(env(f'Survival_Crawler_Dock_{j}_{n}', 'SP-51', 'crawler HOME dock: charging, tool cartridges, recovery (DS-11, 15!A182)' if n == home else
                           'unpowered track stop / tool stop, mechanically retained (no charging; 15!A182)',
                           crew_transfer.radial(x, rr+D/2, a), he.axes_at(a), (L, W, D)))
        cl, cw, cd = q['crawler_m']
        out[-1]['swept_m3'] = cw*cd*(x1-x0)       # the crawler's box swept along its track (on the charging dock's record, once per blade)
    return out


def _box_point_distance(q, p):
    c, ax = q['world_centre'], q['axes']; d = [p[i]-c[i] for i in range(3)]
    return math.sqrt(sum(max(abs(sum(d[i]*ax[k][i] for i in range(3)))-q['size'][k]/2, 0.0)**2 for k in range(3)))


def _segment_point(a, b, p):
    v = [b[i]-a[i] for i in range(3)]; L2 = sum(x*x for x in v); t = 0.0 if L2 == 0 else max(0.0, min(1.0, sum((p[i]-a[i])*v[i] for i in range(3))/L2))
    return math.dist(p, [a[i]+t*v[i] for i in range(3)])


def pointing(s, q, deg, n=24):
    """Sampled pointing screen: rays from a terminal in a cone of half-angle deg about its boresight against the blade planes, the ring
    annuli and the shield disc. Returns the fraction of rays that hit nothing."""
    import habitat_ring
    d = thermal_geometry.blade_of(s); c = q.get('world_centre') or q['b']; b = q['boresight']
    # A basis about the boresight.
    e1 = (1.0, 0.0, 0.0); e2 = (b[1]*e1[2]-b[2]*e1[1], b[2]*e1[0]-b[0]*e1[2], b[0]*e1[1]-b[1]*e1[0])
    blades = [math.radians(s['prototype']['radiator_phase_deg']+j*120) for j in range(s['radiators']['count'])]
    rings = [(x, habitat_ring.sweep_half(s), habitat_ring.outer(s)) for x in habitat_ring.centers(s)]
    shield_x = 105.9; shield_r = s['forward_shield']['diameter']['value']/2
    hits = total = 0
    for i in range(1, n+1):
        th = math.radians(deg)*i/n
        for k in range(4*i):
            ph = 2*math.pi*k/(4*i); r = [math.cos(th)*b[m]+math.sin(th)*(math.cos(ph)*e1[m]+math.sin(ph)*e2[m]) for m in range(3)]; total += 1
            hit = False
            for a in blades:                                   # the blade plane: (y, z) . (-sin a, cos a) = 0, r in [root, outer], x in the span
                nrm = (0.0, -math.sin(a), math.cos(a)); den = sum(r[m]*nrm[m] for m in range(3))
                if abs(den) > 1e-9:
                    t = -sum(c[m]*nrm[m] for m in range(3))/den
                    if t > 0:
                        p = [c[m]+t*r[m] for m in range(3)]; rho = p[1]*math.cos(a)+p[2]*math.sin(a)
                        hit |= d['aft_x_m'] <= p[0] <= d['front_x_m'] and d['root_radius_m'] <= rho <= d['outer_radius_m']
            for x, half, ro in rings:                          # each ring's swept annulus as a disc slab out to its outer radius
                for xf in (x-half, x+half):
                    if abs(r[0]) > 1e-9:
                        t = (xf-c[0])/r[0]
                        if t > 0 and math.hypot(c[1]+t*r[1], c[2]+t*r[2]) <= ro:
                            hit = True
            if abs(r[0]) > 1e-9:
                t = (shield_x-c[0])/r[0]
                hit |= t > 0 and math.hypot(c[1]+t*r[1], c[2]+t*r[2]) <= shield_r
            hits += hit
    return 1.0-hits/total


def check(s):
    """Fit screen. Returns (rows, failures)."""
    import route_fitout as rf
    clr = s['prototype']['mechanical_clearance_m']; h = s['human_entry']; R = h['mannequin']['suited_envelope_diameter_m']/2; r = he.refuge_station(s)
    rows, fails = {}, []
    ref = refuge(s); bodies = he.route_bodies(s)
    route_gap = min(_box_point_distance(q, p) for q in ref for k in ('R', 'E') for _, axis in bodies[k] for p in axis)-R
    occ = min(_box_point_distance(q, crew_transfer.radial(x, r['body_r'], a)) for q in ref for a in r['anchors']
              for x in [r['cavity_x0']+i*(r['cavity_x1']-r['cavity_x0'])/20 for i in range(21)])-R
    hoop = min(_box_point_distance(q, crew_transfer.radial(x, r['hoop_r'], r['th']+2*math.pi*k/72)) for q in ref for x in r['hoop_x'] for k in range(72))-h['handrail_radius_m']
    inside = all(r['cavity_x0']-1e-9 <= p[0] <= r['cavity_x1']+1e-9 and r['inner']-1e-9 <= math.hypot(p[1], p[2]) <= r['pressure']+1e-9 for q in ref for p in he.box_corners(None, q))
    rows['refuge'] = dict(route_gap_m=route_gap, occupant_gap_m=occ, hoop_rail_gap_m=hoop, inside_cavity=inside, installed_m3=sum(q['volume_m3'] for q in ref),
                          net_after_m3=r['pressure_volume_m3']-sum(q['volume_m3'] for q in ref))
    for k, v, need in (('refuge route_gap_m', route_gap, clr), ('refuge occupant_gap_m', occ, clr), ('refuge hoop_rail_gap_m', hoop, clr)):
        if v < need-1e-9:
            fails.append(f'{k} {v:.3f} m below {need:.3f} m')
    if not inside:
        fails.append('a refuge envelope leaves the pressure cavity')
    rows['sectors'] = {}
    for fn in s['sector_whitebox']['functions']:
        els = sector(s, fn); bad = rf.sector_check(s, fn, els)
        rows['sectors'][fn] = dict(elements=[q['name'] for q in els], installed_m3=sum(q['volume_m3'] for q in els), failures=bad)
        fails += [f'{fn}: {b}' for b in bad]
    ext = exterior(s); d = thermal_geometry.blade_of(s)
    members = thermal_geometry.supports(s, d)
    def seg_gap(q):
        pts = q['points'] if q['shape'] == 'rod' else he.box_corners(None, q)
        segs = list(zip(pts, pts[1:])) if q['shape'] == 'rod' else [(p, p) for p in pts]
        rad = q.get('radius', 0.0)
        return min((thermal_geometry.segment_distance(a, b, m0, m1, 16)-rad-(thermal_geometry.chase_radius(s) if m['kind'] == 'coolant_proxy' else m['radius'])
                    for a, b in segs for m in members for m0, m1 in thermal_geometry.legs(m) if abs(m0[0]-a[0]) < 30 or abs(m1[0]-a[0]) < 30), default=math.inf)
    rails = [q for q in ext if q['sp'] == 'SP-51']
    support = min(seg_gap(q) for q in rails)
    # The blade's root truss (chords and diagonals) fills |z| <= truss depth / 2 at the root edge: the track and docks stay outside it or below it.
    half = s['radiators']['geometry']['truss_depth_m']/2; truss = math.inf
    for q in rails:
        j = int(q['name'].split('_')[3]); ab = math.radians(s['prototype']['radiator_phase_deg']+j*120); rad = q.get('radius', 0.0)
        for p in (q['points'] if q['shape'] == 'rod' else he.box_corners(None, q)):
            u, v, z = thermal_geometry.ship_to_local(d, ab, p)
            if d['aft_x_m']-1 <= p[0] <= d['front_x_m']+1:
                truss = min(truss, max(abs(z)-half-thermal_geometry.CHORD_R-rad, -v-thermal_geometry.CHORD_R-rad))
    rows['exterior'] = dict(crawler_to_supports_m=support, crawler_to_root_truss_m=truss, crawler_swept_m3=sum(q.get('swept_m3', 0.0) for q in rails),
                            crawler_docks=sum(1 for q in rails if q['shape'] == 'box'), installed_m3=sum(q.get('volume_m3', 0.0) for q in ext),
                            pointing_clear={q['name']: pointing(s, q, table(s)['pointing_screen_deg']) for q in ext if 'boresight' in q})
    if support < clr:
        fails.append(f'crawler track {support:.3f} m from a radiator support')
    if truss < clr:
        fails.append(f'crawler track {truss:.3f} m from the blade root truss')
    fails += [f'{k}: {v:.3f} of the {table(s)["pointing_screen_deg"]} deg cone obstructed' for k, v in rows['exterior']['pointing_clear'].items() if v < 1.0-1e-9]
    rows['storeroom'] = dict(sp49_bay_m3=storeroom(s)[0]['volume_bay_m3'])
    return rows, fails


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
