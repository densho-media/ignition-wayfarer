"""Detail pack spine_casing (docs/MODULES.md): the aft body casing in the selected Phase 4 grammar (slice S6), assembly SP.CASING on the
anchor WF-SPINE.HULL.ORIGIN (vehicle frame). Owned with data/detail/spine_casing.toml; the function and the fixed parts are in its header.

Reads (never changes): the casing radius and range (hull_geometry, casing_panels), the radiator stay stations (thermal_geometry), the hull
openings, the access panels, the SP-51 crawler rails and stops (survival_fit), the drone docks and rails (drone_fleet) and the service
fittings. Unknown and not modelled: casing joint design, rail bed attachment and loads, crawler operations (all OPEN).
"""
import math

import casing_panels as cp
import drone_fleet
import hull_geometry as hg
import production_detail as pd
import survival_fit
import thermal_geometry as tg

PACK = 'spine_casing'
A = 'SP.CASING'


def rad(x, r, a):
    return (x, r*math.cos(a), r*math.sin(a))


def strip(name, family, material, cls, function, x0, x1, r0, r1, t0, t1):
    """A strip on the casing: X x0..x1, radius r0..r1, angle t0..t1 (rad), bent round the ship axis in <= 3 deg chords."""
    vs, fs = pd.bent(rad, x0, x1, r0, r1, math.degrees(t0), math.degrees(t1), step_deg=3.0)
    q = pd.element(A, family, name, material, cls, function, vs, fs)
    q['patch'] = (x0, x1, t0, t1)
    return q


def tracks(s):
    """Per blade j: the SP-51 track centre angle on the casing (rad), its X range and its stops (X)."""
    q = s['survival']; d = tg.blade_of(s); st = tg.stations(s, d)
    x0, x1 = d['aft_x_m']+q['crawler_rail_end_gap_m'], d['front_x_m']-q['crawler_rail_end_gap_m']
    rr = hg.radius_at(s, 0.0)+q['crawler_rail_standoff_m']
    stops = sorted(st['roots']+st['stays'])+[x1]
    return [dict(j=j, a=math.radians(s['prototype']['radiator_phase_deg']+j*120)+q['crawler_rail_offset_m']/rr, x0=x0, x1=x1, stops=stops)
            for j in range(s['radiators']['count'])]


def module_x(s):
    """Casing module boundaries: the casing ends and the radiator stay stations (the frames the bay stays bear on)."""
    x0, x1 = cp.table(s)['x_range_m']
    return [x0]+sorted(tg.stations(s, tg.blade_of(s))['stays'])+[x1]


def keepouts(s, m):
    """(x0, x1, t0, t1) windows nothing may cover: every hull opening grown by m, every casing access panel."""
    R = hg.radius_at(s, 0.0); out = []
    for w in hg.openings(s, tg.blade_of(s)):
        out.append((w['x0']-m, w['x1']+m, w['t0']-m/R, w['t1']+m/R))
    for p in cp.access_panels(s):
        L, W, _ = p['size']; out.append((p['x']-L/2, p['x']+L/2, p['theta']-W/2/R, p['theta']+W/2/R))
    return out


def overlaps(patch, w):
    x0, x1, t0, t1 = patch; c = (w[2]+w[3])/2; h = (w[3]-w[2])/2
    return x0 < w[1] and w[0] < x1 and cp.adiff((t0+t1)/2, c) < (t1-t0)/2+h


@pd.builder(A)
def casing(s):
    q = pd.params(s, PACK); R = hg.radius_at(s, 0.0); out = []; xr = cp.table(s)['x_range_m']
    rb = R+cp.table(s)['seam_height_m']+q['seat_gap_m']     # every strip seats on the casing straps, never in them (hull contacts)
    # Module frame bands at the cage frames the radiator stays bear on, broken across each keel lane like the hoop straps.
    xs = module_x(s); w = q['module_band_m']
    for i, x in enumerate(xs):
        a, b = max(x-w/2, xr[0]), min(x+w/2, xr[1])
        for k, (t0, t1) in enumerate(cp.hoop_arcs(s)):
            out.append(strip(f'SP_ModuleBand_{i}_{k}', 'modules', 'xf_structure', 'ENGINEERING_FLEXIBLE',
                             'casing module frame band at a primary-cage frame (radiator stay station)', a, b, rb, rb+q['module_band_h_m'], t0, t1))
    # SP-51 rail beds: one followable strip under each crawler track, broken round the hull openings.
    keep = keepouts(s, q['opening_margin_m']); hb = q['rail_bed_m']/2/R
    for t in tracks(s):
        cuts = sorted((w[0], w[1]) for w in keep if overlaps((t['x0'], t['x1'], t['a']-hb, t['a']+hb), w))
        at, k = t['x0'], 0
        for c0, c1 in cuts+[(t['x1'], t['x1'])]:
            if c0 > at+.5:
                out.append(strip(f"SP_RailBed_{t['j']}_{k}", 'route', 'xf_structure', 'ENGINEERING_FLEXIBLE',
                                 'SP-51 crawler rail bed (the track the eye follows; attachment OPEN)', at, c0, rb, rb+q['rail_bed_h_m'],
                                 t['a']-hb, t['a']+hb)); k += 1
            at = max(at, c1)
        # A blue approach marker either side of the bed and a text ID at each stop (C<track>-<stop>, aft to forward).
        L, W = q['stop_marker_m']; g = q['stop_marker_gap_m']
        for n, x in enumerate(t['stops'], 1):
            x0, x1 = max(x-L/2, t['x0']), min(x+L/2, t['x1'])
            for side in (-1, 1):
                e0 = t['a']+side*(hb+g/R); e1 = e0+side*W/R
                out.append(strip(f"SP_StopMarker_{t['j']}_{n}_{'LR'[side > 0]}", 'wayfinding', 'xf_wayfinding', 'ARTISTIC',
                                 'crawler stop approach marker (functional wayfinding)', x0, x1, rb, rb+q['film_m'], min(e0, e1), max(e0, e1)))
            h = pd.marking_height(s, 'lane_label'); ta = t['a']+hb+(g+W+q['stop_id_gap_m']+h/2)/R
            out.append(text(s, q, f"SP_StopID_{t['j']}_{n}", 'crawler stop ID (text only)', f"C{t['j']+1}-{n}", x, ta, h))
    # Module numbers between the blades at each module's aft end; the ship name (S9) along its module, forward of the number.
    h = pd.marking_height(s, 'bay_numeral'); w = q['module_band_m']/2
    for i, (a, b) in enumerate(zip(xs, xs[1:]), 1):
        xn = a+w+q['module_id_inset_m']+.6*h
        for deg in q['module_id_deg']:
            out.append(text(s, q, f'SP_ModuleID_K{i}_{int(deg):03d}', 'casing module number (text only)', f'K{i}', xn, math.radians(deg), h))
        if i == q['ship_name_module']:
            x0, x1 = xn+.6*h+q['ship_name_gap_m'], b-w-q['ship_name_gap_m']; name = q['ship_name']
            hn = min(pd.marking_height(s, 'ship_name'), (x1-x0)/(.6*len(name)))
            for deg in q['module_id_deg']:
                out.append(text(s, q, f'SP_ShipName_{int(deg):03d}', 'ship name (text only; Y155, no G.U.C., no crest)', name, (x0+x1)/2,
                                math.radians(deg), hn))
    return out


def text(s, q, name, function, body, x, t, h):
    """Charcoal lettering on the casing at (x, angle t), reading aft along the axis from outside, bent onto the casing (wrap_r)."""
    r = hg.radius_at(s, 0.0)+q['text_lift_m']
    e = pd.lettering(A, 'markings', name, 'xf_mark', function, body, rad(x, r, t), (-1.0, 0.0, 0.0), (0.0, -math.sin(t), math.cos(t)), h)
    e['wrap_r'] = r; e['wrap_max_edge_m'] = q['text_max_edge_m']
    return e


def obstacles(s):
    """Fixed exterior parts on the casing as primitives: ('seg', a, b, radius) for rods and tubes, ('box', centre, axes, size). Survival masts,
    terminals, trackers, rails and stops; drone rails, docks and units; service fittings, dock corridors and the shield spokes' aft members."""
    out = []
    for e in survival_fit.exterior(s)+drone_fleet._exterior(drone_fleet.stations(s))+drone_fleet.obstacles(s):
        if e.get('shape') == 'rod':
            out += [('seg', a, b, e['radius']) for a, b in zip(e['points'], e['points'][1:])]
        elif 'world_centre' in e:
            out.append(('box', e['world_centre'], e['axes'], e['size']))
        else:
            out.append(('seg', e['a'], e['b'], e.get('r1', 0.1)))
    return out


def seg_dist(p, a, b):
    d = [b[i]-a[i] for i in range(3)]; L2 = sum(x*x for x in d) or 1e-12
    t = max(0.0, min(1.0, sum((p[i]-a[i])*d[i] for i in range(3))/L2))
    return math.dist(p, [a[i]+t*d[i] for i in range(3)])


def distance(p, o):
    """Clear distance from point p to a primitive."""
    if o[0] == 'seg':
        return seg_dist(p, o[1], o[2])-o[3]
    c, ax, sz = o[1], o[2], o[3]
    loc = [sum((p[i]-c[i])*ax[k][i] for i in range(3)) for k in range(3)]
    return math.sqrt(sum(max(abs(loc[k])-sz[k]/2, 0.0)**2 for k in range(3)))


def xspan(o):
    if o[0] == 'seg':
        return min(o[1][0], o[2][0])-o[3], max(o[1][0], o[2][0])+o[3]
    h = math.sqrt(sum(v*v for v in o[3]))/2
    return o[1][0]-h, o[1][0]+h


def samples(q, step=0.25):
    """Points on an element: a strip's patch on a grid of about step m (both radii), or a lettering's cap-height box."""
    if 'text' in q:      # the cap-height box, bent onto the casing like the generator bends it (wrap_r)
        c, r, h = q['centre'], q['right'], q['height']; w = .6*h*len(q['text']); a0 = math.atan2(c[2], c[1])
        return [rad(c[0]+sx*w/2*r[0], q['wrap_r'], a0+sy*h/2/q['wrap_r']) for sx in (-1, 0, 1) for sy in (-1, 0, 1)]
    x0, x1, t0, t1 = q['patch']; rs = [math.hypot(v[1], v[2]) for v in q['vs']]; R = max(rs)
    nx = max(1, math.ceil((x1-x0)/step)); nt = max(1, math.ceil((t1-t0)*R/step))
    return [rad(x0+(x1-x0)*i/nx, r, t0+(t1-t0)*j/nt) for i in range(nx+1) for j in range(nt+1) for r in (min(rs), R)]


def check(s, els):
    """Every element inside the claimed band (casing x range, r <= casing + 0.12 m), off every hull opening (grown by the margin) and access
    panel, and static_gap_m clear of every fixed exterior part."""
    q = pd.params(s, PACK); R = hg.radius_at(s, 0.0); xr = cp.table(s)['x_range_m']; fails = []
    keep = keepouts(s, q['opening_margin_m']); obs = [(o, xspan(o)) for o in obstacles(s)]; gap = q['static_gap_m']
    for e in els:
        pts = samples(e)
        if any(p[0] < xr[0]-1e-6 or p[0] > xr[1]+1e-6 or math.hypot(p[1], p[2]) > R+.12 for p in pts):
            fails.append(f"{e['name']}: outside the casing band"); continue
        patch = e.get('patch') or (min(p[0] for p in pts), max(p[0] for p in pts), *(lambda ts: (min(ts), max(ts)))(
            [math.atan2(p[2], p[1]) for p in pts]))
        if 'text' in e:
            ts = [math.atan2(p[2], p[1]) for p in pts]; c = math.atan2(e['centre'][2], e['centre'][1])
            d = [math.remainder(t-c, math.tau) for t in ts]; patch = (patch[0], patch[1], c+min(d), c+max(d))
        hit = next((w for w in keep if overlaps(patch, w)), None)
        if hit:
            fails.append(f"{e['name']}: covers a hull opening or access panel at X {hit[0]:.2f}-{hit[1]:.2f}"); continue
        for p in pts:
            near = [o for o, (a, b) in obs if a-gap <= p[0] <= b+gap]
            g = min((distance(p, o) for o in near), default=math.inf)
            if g < gap:
                fails.append(f"{e['name']}: {g:.3f} m from a fixed exterior part at X {p[0]:.2f} (< {gap} m)"); break
    return fails


pd.CHECKS[A] = check
