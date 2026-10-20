"""AFT-002/AFT-007 drive hot section: replaceable plasma-facing liners, nozzle strike modules (Q40), the cryogenic feed lines and the shield penetrations.

Canon (drive_capture_2026-10-03): the plasma-facing shell is a WORKING replaceable refractory structure on the fusion core, the
convergence throat and the nozzle-adjacent hardware (06_PROPULSION_ARCHITECTURE A45); the cryogenic feed for D-3He and hydrogen is a
separately solved OPEN system (06!A46, OD-026). Heat flux, material, module size, erosion and replacement interval, and the whole
feed layout, are OPEN: every number here comes from the PROTOTYPE [drive_hot_section] table and the existing envelopes.

Tiles are annular-sector boxes (x0, x1, r_in, r_out, a0, a1) in the ship frame (core, throat) or the nozzle frame (nozzle bands,
x measured from the exit plane). The plasma is solid (06!A47, 15!A70), so the liners sit on the outer side only. One feed line runs per
tank (AFT-007, 15!A69): D and 3He keep a line to the core forward face; the two hydrogen lines step out to a corridor between the cage
and the hull skin inside the shadow-shield slab (the staggered offsets of 15!G68), run aft and enter a PROTOTYPE injection ring around the
common region. Inside the slab every line (and each optical bore) is a stepped dog-leg, so no straight line passes the sleeve bore
(sleeve_sight_lines). The shield is never cut elsewhere; the conservative sight-line reach is reported.

Standard library and the pure geometry modules only; imported by drive_manifold.check, the recipes, inspect and tests.
"""
import math
import drive_manifold as dm
import hull_geometry
import layout
import power_storage

CORE, THROAT, NOZZLE = 'core', 'throat', 'nozzle'
# Tank (y, z) quadrants of Tank_Volume_01..04 (recipes STORAGE, power_storage.obstacles). An implementation constant, deliberately not
# dm.quadrants(s): the nozzle order follows the owner nozzle_map (AFT-008) and never moves tanks or lines.
TANK_QUADRANTS = [(1, 1), (-1, 1), (-1, -1), (1, -1)]
# Inventory entry of propulsion.inventories.separate -> the tank family that holds it (water is not a drive tank).
FAMILY_MARK = {'deuterium': 'D ', 'helium-3': '3He', 'hydrogen': 'hydrogen'}
ZONES = (CORE, THROAT, NOZZLE)
# Implementation setting (mesh resolution of one tile's arc), not a physical value.
TILE_STEPS = 2
OPEN_SECTIONS = ('magnet_hardware', 'plasma_facing', 'cryogenic_feed')


# ---------- small geometry ------------------------------------------------------------------------------------------

def rect_point_distance(tile, x, r):
    """Distance in the (x, r) half-plane from a point to a tile cross-section (0 inside). Axisymmetric, so independent of azimuth."""
    return math.hypot(max(tile['x0']-x, 0.0, x-tile['x1']), max(tile['r_in']-r, 0.0, r-tile['r_out']))


def rect_rect_distance(a, b):
    return math.hypot(max(0.0, a['x0']-b['x1'], b['x0']-a['x1']), max(0.0, a['r_in']-b['r_out'], b['r_in']-a['r_out']))


def segment_distance(p0, p1, q0, q1):
    """Exact minimum distance between two 3D segments (closest-point method)."""
    d1, d2, r = dm.sub(p1, p0), dm.sub(q1, q0), dm.sub(p0, q0)
    a, e, f = dm.dot(d1, d1), dm.dot(d2, d2), dm.dot(d2, r)
    s = t = 0.0
    if a <= 1e-18 and e <= 1e-18:
        return dm.norm(r)
    if a <= 1e-18:
        t = max(0.0, min(1.0, f/e))
    else:
        c = dm.dot(d1, r)
        if e <= 1e-18:
            s = max(0.0, min(1.0, -c/a))
        else:
            b = dm.dot(d1, d2); den = a*e-b*b
            s = max(0.0, min(1.0, (b*f-c*e)/den)) if den > 1e-18 else 0.0
            t = (b*s+f)/e
            if t < 0.0:
                t, s = 0.0, max(0.0, min(1.0, -c/a))
            elif t > 1.0:
                t, s = 1.0, max(0.0, min(1.0, (b-c)/a))
    return dm.norm(dm.sub(tuple(p+s*d for p, d in zip(p0, d1)), tuple(q+t*d for q, d in zip(q0, d2))))


def point_box_distance(pt, center, size):
    return math.sqrt(sum(max(0.0, abs(pt[i]-center[i])-size[i]/2)**2 for i in range(3)))


def segment_box_distance(a, b, center, size, samples=400):
    return min(point_box_distance(tuple(p+k/samples*(q-p) for p, q in zip(a, b)), center, size) for k in range(samples+1))


def open_text(ref):
    """Metadata string of an OPEN quantity: its owner open-design item."""
    return 'OPEN '+ref.replace('od_', 'OD-')


def open_keys(s):
    """Dotted keys of the OPEN unknowns under the three AFT-002 source tables: {path: source_ref}."""
    out = {}
    for section in OPEN_SECTIONS:
        for key, node in s['propulsion'][section].items():
            if isinstance(node, dict) and node.get('known') is False:
                out[f'propulsion.{section}.{key}'] = node['source_ref']
    return out


# ---------- tiles ---------------------------------------------------------------------------------------------------

def segments(r_mid, count, seam):
    """Angular extents of count tiles around the axis, separated by a seam of linear width `seam` at r_mid."""
    half = seam/(2*r_mid)
    return [(k*math.tau/count+half, (k+1)*math.tau/count-half) for k in range(count)]


def throat_plasma_outer(g, x):
    """Outer radius of the PLASMA_THROAT loft at x (piecewise linear through the throat rings)."""
    rings = g['throat_rings']
    for (x0, _, r0), (x1, _, r1) in zip(rings, rings[1:]):
        if x1 <= x <= x0:
            return r0+(r1-r0)*(x0-x)/(x0-x1)
    return rings[-1][2] if x < rings[-1][0] else rings[0][2]


def throat_plasma_profile(g, samples=40):
    """(x, outer radius) samples along the throat plasma surface, ring to ring."""
    rings = g['throat_rings']; out = []
    for (x0, _, r0), (x1, _, r1) in zip(rings, rings[1:]):
        out += [(x0+(x1-x0)*k/samples, r0+(r1-r0)*k/samples) for k in range(samples+1)]
    return out


def modules(x_fwd, x_aft, count, seam):
    """Axial module extents from forward to aft; the seam is taken off every module face."""
    w = (x_fwd-x_aft)/count
    return [dict(x1=x_fwd-k*w-seam/2, x0=x_fwd-(k+1)*w+seam/2, span=(x_fwd-(k+1)*w, x_fwd-k*w)) for k in range(count)]


def liner_tiles(s, zone):
    """Tile boxes of one zone. core/throat: ship frame. nozzle: nozzle frame (x from the exit plane), one band per Nozzle_Coil."""
    h, p = s['drive_hot_section'], s['prototype']; g = dm.geometry(s); st = g['stations']; seam = h['liner_seam_m']; out = []
    if zone == CORE:
        r_in, r_out = h['core_liner_inner_radius_m'], h['core_liner_inner_radius_m']+h['core_liner_thickness_m']
        mods = modules(st['core_fwd']-h['core_liner_end_margin_m'], st['core_aft']+h['core_liner_end_margin_m'], h['core_liner_axial_modules'], seam)
        arcs = segments((r_in+r_out)/2, h['core_liner_segments'], seam)
        for i, mod in enumerate(mods):
            for k, (a0, a1) in enumerate(arcs):
                out.append(dict(zone=zone, module=i, segment=k, x0=mod['x0'], x1=mod['x1'], r_in=r_in, r_out=r_out, a0=a0, a1=a1))
    elif zone == THROAT:
        mods = modules(st['throat_entry'], st['throat_exit'], h['throat_liner_axial_modules'], seam)
        for i, mod in enumerate(mods):
            lo, hi = mod['span']
            # Profile of the plasma over the module (throat loft plus the largest branch envelope where the branches begin).
            heights = [r for xx, r in throat_plasma_profile(g) if lo-1e-12 <= xx <= hi+1e-12]
            if abs(lo-st['throat_exit']) < 1e-9:
                heights.append(s['drive_manifold']['branch_start_radius_m']+s['drive_manifold']['plasma_branch_max_radius_m'])
            r_in = max(heights)+h['throat_liner_gap_m']; r_out = r_in+h['throat_liner_thickness_m']
            for k, (a0, a1) in enumerate(segments((r_in+r_out)/2, h['throat_liner_segments'], seam)):
                out.append(dict(zone=zone, module=i, segment=k, x0=mod['x0'], x1=mod['x1'], r_in=r_in, r_out=r_out, a0=a0, a1=a1))
    elif zone == NOZZLE:
        # Q40: local strike modules at the PROTOTYPE contact-risk coil stations only; magnetic standoff elsewhere.
        for c in [c for c in dm.nozzle_coils(s) if c['index'] in h['nozzle_strike_module_coils']]:
            r_out = c['inner']; r_in = r_out-h['nozzle_liner_thickness_m']
            for k, (a0, a1) in enumerate(segments((r_in+r_out)/2, h['nozzle_liner_segments'], seam)):
                out.append(dict(zone=zone, module=c['index'], segment=k, coil=c['index'], x0=c['x']-c['tube'], x1=c['x']+c['tube'], r_in=r_in, r_out=r_out, a0=a0, a1=a1))
    else:
        raise ValueError(f'unknown liner zone {zone!r}')
    return out


def tile_volume_m3(tile):
    return (tile['x1']-tile['x0'])*(tile['a1']-tile['a0'])*(tile['r_out']**2-tile['r_in']**2)/2


# ---------- cryogenic feed ------------------------------------------------------------------------------------------

def inventory_families(s):
    """Tank families named by propulsion.inventories.separate (water excluded): the set the tank assignment must cover."""
    return {fam for entry in s['propulsion']['inventories']['separate'] for fam, mark in FAMILY_MARK.items() if entry.startswith(mark) or (mark == 'hydrogen' and 'hydrogen' in entry)}


def injection_x(s):
    return layout.at(s, s['drive_hot_section']['h2_injection_x'])


def cryo_feed(s):
    """One jacketed line per Tank_Volume_0n at the tank's (y, z) offset (TANK_QUADRANTS), from the tank aft cap to its terminus.
    Inside the shadow-shield slab every line is a stepped dog-leg between two planes cryo_feed_sleeve_jog_inset_m inside each slab face.
    D and 3He (terminus core) step out by cryo_feed_sleeve_step_m and back to the core forward face. Hydrogen (terminus injection_ring)
    steps out to h2_corridor_radius_m: jog 'aft' first steps by the sleeve step at the forward plane and goes out to the corridor at the aft
    plane; jog 'forward' goes out to the corridor at the forward plane (the staggered offsets of 15!G68). The line then runs aft in the
    corridor and turns in to the injection ring at h2_injection_x. points: polyline a..b. shield_point is the sleeve centre on the
    offset leg; axis_point the same plane on the straight tank axis."""
    p, h = s['prototype'], s['drive_hot_section']; st = dm.stations(s)
    cap = layout.at(s, p['tank_center_x'])-p['tank_length_m']/2; mid = (st['shield_aft']+st['shield_fwd'])/2; out = []
    xf, xa, xi = st['shield_fwd']-h['cryo_feed_sleeve_jog_inset_m'], st['shield_aft']+h['cryo_feed_sleeve_jog_inset_m'], injection_x(s)
    jogs = iter(h['h2_outward_jog'])
    for j, (yy, zz) in enumerate(TANK_QUADRANTS, 1):
        y, z = yy*p['tank_offset_m'], zz*p['tank_offset_m']
        r = math.hypot(y, z); at = lambda rad: (y*rad/r, z*rad/r)
        y2, z2 = at(r+h['cryo_feed_sleeve_step_m']); terminus = h['feed_terminus'][j-1]
        if terminus == 'core':
            points = [(cap, y, z), (xf, y, z), (xf, y2, z2), (xa, y2, z2), (xa, y, z), (st['core_fwd'], y, z)]; sleeve = (mid, y2, z2)
        else:
            yc, zc = at(h['h2_corridor_radius_m']); yr, zr = at(h['h2_injection_ring_radius_m'])
            if next(jogs) == 'aft':
                points = [(cap, y, z), (xf, y, z), (xf, y2, z2), (xa, y2, z2), (xa, yc, zc)]; sleeve = (mid, y2, z2)
            else:
                points = [(cap, y, z), (xf, y, z), (xf, yc, zc)]; sleeve = (mid, yc, zc)
            points += [(xi, yc, zc), (xi, yr, zr)]
        out.append(dict(index=j, name=f'CRYO_FEED_LINE_{j:02}', tank=f'Tank_Volume_{j:02}', a=(cap, y, z), b=points[-1], points=points, terminus=terminus,
                        family=h['tank_families'][j-1], own=('Fusion_Core',) if terminus == 'core' else ('H2_INJECTION_RING',),
                        radius=h['cryo_feed_line_radius_m'], sleeve_radius=h['cryo_feed_line_radius_m']+h['cryo_feed_sleeve_gap_m'],
                        shield_point=sleeve, axis_point=(mid, y, z)))
    return out


def injection_ring(s):
    """H2 injection ring around the common region (PROTOTYPE): station, centreline radius, tube radius."""
    h = s['drive_hot_section']
    return dict(x=injection_x(s), radius=h['h2_injection_ring_radius_m'], tube=h['h2_injection_ring_tube_m'])


def shield_reach(g, line, point, thickness):
    """Conservative reach of a straight sight line through the sleeve (same rule as drive_manifold.los_reach: a line that clears a
    tunnel of length t and radius rc is within rc + 2 rc D/t of its axis a distance D beyond it)."""
    D = point[0]-(line['axis_point'][0]+thickness/2)
    if D < 0:
        return True
    return math.hypot(point[1]-line['axis_point'][1], point[2]-line['axis_point'][2]) <= line['sleeve_radius']*(1+2*D/thickness)


def polyline(line):
    return line.get('points') or [line['a'], line['b']]


def polyline_distance(pts, q, x0, x1):
    """Distance from q to the part of a polyline lying in x0..x1 (each segment clipped to the slab; segments are monotone in x or lateral)."""
    best = math.inf
    for a, b in zip(pts, pts[1:]):
        if max(a[0], b[0]) < x0 or min(a[0], b[0]) > x1:
            continue
        if a[0] != b[0]:
            ta, tb = sorted(((x0-a[0])/(b[0]-a[0]), (x1-a[0])/(b[0]-a[0])))
            ta, tb = max(0.0, ta), min(1.0, tb)
            a, b = tuple(u+ta*(v-u) for u, v in zip(a, b)), tuple(u+tb*(v-u) for u, v in zip(a, b))
        best = min(best, dm.point_segment(q, a, b))
    return best


def sleeve_sight_lines(line, x_aft, x_fwd, n=24, samples=60):
    """Count straight lines through the whole slab that stay inside the sleeve bore. Lines are taken between points on the bore
    outline (and centre) at the aft and forward slab faces, since any straight line through the slab is fixed by those two points, and
    followed through the slab; one that never leaves the 3D bore (radius sleeve_radius about every polyline leg inside the slab, jog legs included) is an open sight line.
    0 means no core-to-tank line of sight; a straight sleeve returns more than 0 (same rule as the optical chicane)."""
    pts = polyline(line); rs = line['sleeve_radius']; eps = 1e-9; open_lines = 0
    x0, x1 = min(x_aft, x_fwd), max(x_aft, x_fwd)
    def face(x):
        axis = polyline_point(pts, x)
        return [axis]+[(x, axis[1]+rs*math.cos(2*math.pi*k/n), axis[2]+rs*math.sin(2*math.pi*k/n)) for k in range(n)]
    for pa in face(x_aft):
        for pf in face(x_fwd):
            ok = True
            for k in range(1, samples):
                q = tuple(u+(v-u)*k/samples for u, v in zip(pa, pf))
                if polyline_distance(pts, q, x0, x1) > rs+eps:   # true 3D distance to every leg inside the slab
                    ok = False
                    break
            open_lines += ok
    return open_lines


def polyline_point(pts, x):
    """Point where the polyline first reaches axial position x (the ends of a straight leg, not a jog)."""
    for a, b in zip(pts, pts[1:]):
        if a[0] != b[0] and (a[0]-x)*(b[0]-x) <= 0:
            t = (x-a[0])/(b[0]-a[0])
            return tuple(u+t*(v-u) for u, v in zip(a, b))
    raise ValueError('x outside the polyline')


def tank_points(s, j):
    p = s['prototype']; yy, zz = TANK_QUADRANTS[j-1]; c = layout.at(s, p['tank_center_x'])
    return [(c+u*p['tank_length_m']/2, yy*p['tank_offset_m']+p['tank_radius_m']*math.cos(a), zz*p['tank_offset_m']+p['tank_radius_m']*math.sin(a))
            for u in (-1, -.5, 0, .5, 1) for a in [k*math.pi/4 for k in range(8)]]


def feed_members(s, g):
    """Everything a feed line must clear, as (name, kind, payload). Exempt per line: its own tank, `own` members (the core face or the
    injection ring it ends on) and Engineering_Envelope (the bay it passes through); the shield slab holds the declared sleeve penetrations."""
    p, m = s['prototype'], s['drive_manifold']; st = g['stations']; out = []
    for name, a, b, r in power_storage.obstacles(s):
        if name != 'Engineering_Envelope':
            out.append((name, 'cylinder', (a, b, r)))
    hub = g['hub']
    out.append(('SPINE_TERMINATION_HUB', 'cylinder', ((hub['x0'], 0.0, 0.0), (hub['x1'], 0.0, 0.0), hub['radius'])))
    for key, r in g['routes'].items():
        for a, b in zip(r['bore'], r['bore'][1:]):
            out.append((f'OPTICAL_BORE_{key}', 'cylinder', (a, b, m['optical_channel_radius_m'])))
    for key, las in g['lasers'].items():
        out.append((f'LASER_{key}', 'box', (las['center'], las['size'])))
    for name, pts in dm.route_beams(g).items():
        for k, (a, b) in enumerate(zip(pts, pts[1:])):
            out.append((f'{name}[{k}]', 'cylinder', (a, b, m['beam_radius_m'])))
    for name, pt in g['mirrors'].items():
        out.append((name, 'cylinder', ((pt[0]-.025, pt[1], pt[2]), (pt[0]+.025, pt[1], pt[2]), m['mirror_radius_m'])))
    for key, r in g['routes'].items():
        for name, pt in r['heads'].items():
            out.append((name, 'cylinder', ((pt[0]-.25, pt[1], pt[2]), (pt[0]+.25, pt[1], pt[2]), m['head_size_m'])))
    ring_ = injection_ring(s); pts = [(ring_['x'], ring_['radius']*math.cos(k*math.tau/24), ring_['radius']*math.sin(k*math.tau/24)) for k in range(25)]
    out += [(f'H2_INJECTION_RING[{k}]', 'cylinder', (a, b, ring_['tube'])) for k, (a, b) in enumerate(zip(pts, pts[1:]))]
    # Flat-ended envelopes: a capsule (axis segment minus radius) would overstate their ends, so they use the exact cylinder distance.
    out += [('Fusion_Core', 'envelope', (st['core_aft'], st['core_fwd'], p['reactor_radius_m'])),
            ('Common_Plasma_Region', 'envelope', (st['common_aft'], st['common_fwd'], p['common_radius_m'])),
            ('Magnetic_Manifold', 'envelope', (st['manifold_aft'], st['throat_entry'], p['manifold_radius_m']))]
    for p_ in power_storage.packs(s):
        out.append((p_['name'], 'pack', p_))
    return out


def feed_member_gap(line, kind, payload):
    r = line['radius']; segs = list(zip(polyline(line), polyline(line)[1:]))
    if kind == 'cylinder':
        return min(segment_distance(a, b, payload[0], payload[1]) for a, b in segs)-payload[2]-r
    if kind == 'envelope':
        return min(dm.segment_cylinder_gap(a, b, *payload, samples=max(8, math.ceil(dm.norm(dm.sub(b, a))/.05))) for a, b in segs)-r
    if kind == 'box':
        return min(segment_box_distance(a, b, *payload) for a, b in segs)-r
    return min(power_storage.cylinder_box(a, b, r, payload) for a, b in segs)


def cryo_clearances(s, g, lines):
    """Per line: nearest member and gap, including the primary cage and the hull inner skin."""
    cage = hull_geometry.cage_points(s); members = feed_members(s, g); rows = {}
    for line in lines:
        xs = [q[0] for q in polyline(line)]
        best = (math.inf, None)
        for name, kind, payload in members:
            if name == line['tank'] or name.startswith(tuple(line.get('own', ()))):
                continue
            gap = feed_member_gap(line, kind, payload)
            best = min(best, (gap, name), key=lambda t: t[0])
        for x, y, z, rr in cage:
            if min(xs)-6 < x < max(xs)+6:   # window around the whole polyline, every leg
                gap = min(dm.point_segment((x, y, z), a, b) for a, b in zip(polyline(line), polyline(line)[1:]))-rr-line['radius']
                best = min(best, (gap, 'Primary_cage'), key=lambda t: t[0])
        n = 40; skin = min(hull_geometry.inner_radius_at(s, a[0]+(b[0]-a[0])*k/n)-math.hypot(a[1]+(b[1]-a[1])*k/n, a[2]+(b[2]-a[2])*k/n)-line['radius']
                           for a, b in zip(polyline(line), polyline(line)[1:]) for k in range(n+1))
        best = min(best, (skin, 'Hull_inner_skin'), key=lambda t: t[0])
        rows[line['name']] = dict(gap_m=best[0], nearest=best[1])
    return rows


# ---------- screen --------------------------------------------------------------------------------------------------

def check(s, g, d=None):
    """Hot-section rules and measurements, merged into drive_manifold.check. Returns failures, findings, measurements."""
    p, m, h = s['prototype'], s['drive_manifold'], s['drive_hot_section']; st = g['stations']
    gap, clr, beam_clr = m['plasma_hardware_clearance_m'], p['mechanical_clearance_m'], m['beam_clearance_m']
    rmax = m['plasma_branch_max_radius_m']
    failures, findings, meas = [], [], {}
    def need(ok, message):
        if not ok:
            failures.append(message)
    for key in ('core_liner_axial_modules', 'core_liner_segments', 'throat_liner_axial_modules', 'throat_liner_segments', 'nozzle_liner_segments'):
        need(type(h[key]) is int and h[key] > 0, f'drive_hot_section.{key}: positive integer')
    need(type(h['pickup_attach_yoke']) is int and 0 <= h['pickup_attach_yoke'] < 4, 'drive_hot_section.pickup_attach_yoke: nozzle yoke index 0..3')
    need(0 < len(h['nozzle_strike_module_coils']) < 4 and set(h['nozzle_strike_module_coils']) <= {0, 1, 2, 3}, 'drive_hot_section.nozzle_strike_module_coils: local modules at some coil stations, not a full nozzle shell (Q40)')
    if failures:
        return dict(failures=failures, findings=findings, measurements=meas)
    core, throat, bands = liner_tiles(s, CORE), liner_tiles(s, THROAT), liner_tiles(s, NOZZLE)
    lines = cryo_feed(s)
    # Fusion core: tiles inside the LOCKED Fusion_Core envelope and the end margin, on the outer side of a solid plasma (no spine, no inner layer).
    meas['core_liner_layers'] = len({(t['r_in'], t['r_out']) for t in core}); meas['throat_liner_layers_per_module'] = max(len({(t['r_in'], t['r_out']) for t in throat if t['module'] == i}) for i in {t['module'] for t in throat})
    meas['core_liner_plasma_gap_m'] = min(t['r_in'] for t in core)-m['common_stream_outer_radius_m']
    meas['core_liner_envelope_gap_m'] = p['reactor_radius_m']-max(t['r_out'] for t in core)
    meas['core_liner_end_gap_m'] = min(min(t['x0']-st['core_aft'], st['core_fwd']-t['x1']) for t in core)
    core_lines = [l for l in lines if l['terminus'] == 'core']
    meas['core_liner_feed_gap_m'] = min(min(rect_point_distance(t, x, math.hypot(l['a'][1], l['a'][2])) for x in [l['b'][0]+(l['a'][0]-l['b'][0])*k/200 for k in range(201)])-l['radius'] for t in core for l in core_lines)
    need(meas['core_liner_layers'] == 1 and meas['throat_liner_layers_per_module'] == 1, 'Core and throat liners must be a single outer layer: no inner layer on a solid plasma')
    need(meas['core_liner_plasma_gap_m'] >= gap, 'Core liner reaches the common plasma column')
    need(meas['core_liner_envelope_gap_m'] >= clr, 'Core liner leaves the Fusion_Core envelope')
    need(meas['core_liner_end_gap_m'] >= gap, 'Core liner reaches the core end faces')
    need(meas['core_liner_feed_gap_m'] >= clr, 'Core liner touches a cryogenic feed terminus')
    # Throat: stands off the plasma (throat loft and the largest branch envelope), clear of the seed coils, gate beams and lattice.
    profile = throat_plasma_profile(g)
    plasma_gap = min(rect_point_distance(t, x, r) for t in throat for x, r in profile)
    branch_gap = min(rect_point_distance(t, q[0], math.hypot(q[1], q[2]))-rmax for t in throat for b in g['branches'] for q in b)
    meas['throat_liner_plasma_gap_m'] = min(plasma_gap, branch_gap)
    meas['throat_liner_seed_coil_gap_m'] = min(rect_point_distance(t, c['x'], c['radius'])-c['tube'] for t in throat for c in g['coils'])
    meas['throat_liner_manifold_gap_m'] = p['manifold_radius_m']-max(t['r_out'] for t in throat)
    meas['throat_liner_lattice_gap_m'] = min(rect_rect_distance(t, dict(x0=l['x1'], x1=l['x0'], r_in=l['r_in'], r_out=l['r_out'])) for t in throat for l in g['lattice'])
    beam_gaps = []
    for beam in g['gate_beams'].values():
        a, b = beam
        for k in range(201):
            x = a[0]+(b[0]-a[0])*k/200; r = math.hypot(a[1]+(b[1]-a[1])*k/200, a[2]+(b[2]-a[2])*k/200)
            beam_gaps.append(min(rect_point_distance(t, x, r) for t in throat)-m['beam_radius_m'])
    meas['gate_beam_liner_gap_m'] = min(beam_gaps)
    need(min(t['x0'] for t in throat) > st['lattice_fwd'], 'Throat liner reaches the lattice (lattice_fwd)')
    need(max(t['x1'] for t in throat) <= st['throat_entry']+1e-9 and min(t['x0'] for t in throat) >= st['throat_exit']-1e-9, 'Throat liner leaves the throat span')
    need(meas['throat_liner_plasma_gap_m'] >= gap, 'Throat liner reaches the throat/branch plasma')
    need(meas['throat_liner_seed_coil_gap_m'] >= gap, 'Throat liner reaches a seed coil')
    need(meas['throat_liner_manifold_gap_m'] >= gap, 'Throat liner leaves the Magnetic_Manifold envelope')
    need(meas['throat_liner_lattice_gap_m'] >= gap, 'Throat liner reaches a lattice sector')
    need(meas['gate_beam_liner_gap_m'] >= beam_clr, 'Gate beam clips the throat liner')
    # Nozzle strike modules (Q40) on the coil inner faces: over each module band's whole axial width, clear of the exhaust plasma.
    ex = g['exhausts'][0]
    nz = min(t['r_in']-rmax*dm.exhaust_factor(ex, st, t['x0']+(t['x1']-t['x0'])*k/50) for t in bands for k in range(51))
    meas['nozzle_liner_plasma_gap_m'] = nz
    need(nz >= gap, 'Nozzle strike module reaches the exhaust plasma')
    need(all(t['r_in'] > 0 for t in bands), 'Nozzle strike module thicker than the coil bore')
    # Cryogenic feed: one line per tank, tank cap -> its terminus; clear of everything but its own tank and terminus (and the bay).
    need(all(l['a'][0] > st['shield_fwd'] > st['shield_aft'] > l['b'][0] for l in lines), 'Feed lines must run from forward of the shield to a terminus aft of it')
    rows = cryo_clearances(s, g, lines)
    worst = min(rows.values(), key=lambda r: r['gap_m'])
    meas['cryo_feed_member_min_gap_m'] = worst['gap_m']; meas['cryo_feed_nearest_member'] = worst['nearest']
    meas['cryo_feed_gaps_m'] = {k: v['gap_m'] for k, v in rows.items()}
    need(worst['gap_m'] >= clr, f'Cryogenic feed line too close to {worst["nearest"]}')
    thickness = st['shield_fwd']-st['shield_aft']
    cold = dm.cold_optics(g)
    need(all(math.hypot(*q[1:])+l['sleeve_radius'] <= p['shadow_radius_m']-clr for l in lines for q in polyline(l) if st['shield_aft'] <= q[0] <= st['shield_fwd']), 'Feed sleeve leaves the shadow shield')
    open_sight = {l['name']: sleeve_sight_lines(l, st['shield_aft'], st['shield_fwd']) for l in lines}
    meas['cryo_feed_sleeve_open_sight_lines'] = open_sight
    need(not any(open_sight.values()), f'Feed sleeve has a direct core-to-tank line of sight: {sorted(k for k, v in open_sight.items() if v)}')
    # Optical bores (15!A73): the same sleeve rule over the shield slab and the terminated hub.
    bore_r, x_hub = m['optical_channel_radius_m'], g['hub']['x1']
    bores = {f'OPTICAL_BORE_{k}': dict(points=r['bore'], sleeve_radius=bore_r) for k, r in g['routes'].items()}
    bore_sight = {n: sleeve_sight_lines(b, st['shield_aft'], x_hub) for n, b in bores.items()}
    meas['optical_bore_open_sight_lines'] = bore_sight
    need(not any(bore_sight.values()), f'Optical bore has a direct core line of sight: {sorted(k for k, v in bore_sight.items() if v)}')
    need(all(math.hypot(*q[1:])+bore_r <= p['shadow_radius_m']-clr for b in bores.values() for q in b['points']), 'Optical bore leaves the shadow shield')
    # Feed families (15!A69, 06!A53, 06!A54): D and 3He meter into the core, hydrogen is injected downstream into the common region.
    ring_ = injection_ring(s)
    need(len(h['tank_families']) == len(h['feed_terminus']) == len(TANK_QUADRANTS) == 4 and set(h['tank_families']) == inventory_families(s), 'Tank families must cover propulsion.inventories.separate (water excluded)')
    need(sorted(h['tank_families']) == ['deuterium', 'helium-3', 'hydrogen', 'hydrogen'], 'Four tanks: one deuterium, one helium-3, two hydrogen')
    need(all((f == 'hydrogen') == (tm == 'injection_ring') for f, tm in zip(h['tank_families'], h['feed_terminus'])) and set(h['feed_terminus']) <= {'core', 'injection_ring'}, 'Hydrogen enters the injection ring; D and 3He enter the core')
    need(st['common_aft'] < ring_['x'] < st['common_fwd'], 'Injection ring inside the common region span')
    meas['h2_injection_ring_gap_m'] = ring_['radius']-ring_['tube']-p['common_radius_m']
    need(meas['h2_injection_ring_gap_m'] >= clr, 'Injection ring too close to the common envelope')
    for l in lines:
        if l['terminus'] == 'core':
            need(l['b'][0] == st['core_fwd'] and math.hypot(*l['b'][1:]) < p['reactor_radius_m'], f'{l["name"]} must end on the core forward face')
        else:
            need(l['b'][0] == ring_['x'] and math.isclose(math.hypot(*l['b'][1:]), ring_['radius']), f'{l["name"]} must end on the injection ring')
            need(all(math.hypot(*q[1:]) >= p['reactor_radius_m']+clr for q in polyline(l) if st['core_aft'] <= q[0] <= st['core_fwd']), f'{l["name"]} passes inside the core radius')
    # Every forward feed point must lie in the shadow cone of the core envelope (the same crosses() test the lasers use).
    core_pts = [(x, r*math.cos(a), r*math.sin(a)) for x in (st['core_fwd'], (st['core_fwd']+st['core_aft'])/2) for r in (0.0, p['reactor_radius_m']/2, p['reactor_radius_m']) for a in [k*math.pi/6 for k in range(12)]]
    forward = [tuple(l['a'][i]+(l['points'][1][i]-l['a'][i])*k/10 for i in range(3)) for l in lines for k in range(11)]
    forward = [q for q in forward if q[0] > st['shield_fwd']]
    meas['cryo_feed_in_shadow'] = all(dm.crosses(c, q, st['shield_aft'], st['shield_fwd'], p['shadow_radius_m']) for c in core_pts for q in forward)
    need(meas['cryo_feed_in_shadow'], 'Forward feed points must sit in the shadow cone of the core envelope')
    exposed = {k: [l['name'] for l in lines if any(shield_reach(g, l, q, thickness) for q in pts)] for k, pts in cold.items()}
    meas['cryo_feed_cold_optics_exposed'] = {k: v for k, v in exposed.items() if v}
    need(not meas['cryo_feed_cold_optics_exposed'], f'Cold optics within reach of a feed sleeve sight line: {sorted(meas["cryo_feed_cold_optics_exposed"])}')
    tanks = {l['name']: [f'Tank_Volume_{j:02}' for j in range(1, 5) if any(shield_reach(g, l, q, thickness) for q in tank_points(s, j))] for l in lines}
    findings.append(dict(id='CRYO_FEED_SHIELD_PENETRATION',
                         detail='Each cryogenic feed line crosses the shadow-shield slab through a stepped (dog-leg) sleeve, the convention of the optical bores; the 0.3 m between the 5.7 m shield and the 6.0 m casing cannot carry a line around the rim. The D and 3He lines step by the sleeve step; the two hydrogen lines step out to the cage-to-skin corridor with staggered jog planes (15!G68). The PROTOTYPE steps and jog insets leave no straight core-to-tank line of sight through any sleeve bore and no cold optics or laser within conservative straight-sleeve reach; the cold tanks are within that conservative reach by construction. Thermal intercepts and labyrinth shielding are annotated on the sleeve interfaces, not drawn. The hydrogen run through the hot corridor sees nuclear and radiant heating, and its boil-off cost is OPEN (OD-026, 06!E46). The penetration design, scattering and dose are OPEN (OD-026).',
                         sleeves=[dict(line=l['name'], family=l['family'], terminus=l['terminus'], shield_point=l['shield_point'], sleeve_radius_m=l['sleeve_radius'], open_sight_lines=open_sight[l['name']]) for l in lines],
                         cold_items_in_reach=tanks, cold_optics_in_reach=meas['cryo_feed_cold_optics_exposed']))
    findings.append(dict(id='OPTICAL_ROUTE_PENETRATIONS',
                         detail='Each optical route passes the terminated hub and the shield through its own dog-leg bore beside the spine end: one in-bore jog of route_jog_m, so no straight line crosses the bore (zero open sight lines, screened). The bores are shield penetrations whose material, streaming dose and thermal intercepts are OPEN (15!C73).',
                         bores=[dict(bore=n, open_sight_lines=bore_sight[n], jog_m=m['route_jog_m'], offset_m=m['route_offset_m'], radius_m=bore_r) for n in bores]))
    findings.append(dict(id='H2_INJECTION_OPEN', detail='Hydrogen reaction mass enters a PROTOTYPE injection ring around the common region at h2_injection_x, downstream of the burn and ahead of the manifold. Injector ports, count, mixing and the heat load on the ring are OPEN; so are the nuclear and radiant heating and boil-off of the hydrogen run in the hot corridor (OD-026, 06!E46); only the ring station is drawn.',
                         ring=dict(x=ring_['x'], radius_m=ring_['radius'], tube_m=ring_['tube']), lines=[l['name'] for l in lines if l['terminus'] == 'injection_ring']))
    return dict(failures=failures, findings=findings, measurements=meas)
