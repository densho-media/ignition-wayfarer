"""FWD-V2 Eye placement study (Eye 45_EYE_CROWN_REDESIGN FD-E01..E03, S&E 50_FORWARD_DEFENSE_BUILD AG-004..AG-007): the four EYE wells at
centre radius r = 4 m (WORKING, 14!A28), 16 m and 24 m (both STUDY, not flight geometry) on the current Brow, screened against the existing forward
structure. Pure, standard library only. Nothing here changes a source value: `variant` returns an in-memory copy with only the well centre radius
moved; B_array (Eye 02!E8 = 8 m, WORKING) stays as it is (AG-006).

Every number carries its status. Margins are metres (negative = clash); angles are degrees. The Crown, truss, posts and shutter leaf are PROTOTYPE
geometry, so a clash is a layout finding, not a physical verdict. Field of view is OPEN (eye.field_of_view): the "well field" below is only the
geometric field the WORKING 3.5 m x 2 m well leaves a 2.5 m aperture, not an EYE FOV.

    python3 src/wayfarer/eye_placement.py            # the r4 / r16 / r24 screen as a table
"""
import copy
import math
import forward_shield as fsh

RADII = (4.0, 16.0, 24.0)
STATUS = {4.0: 'WORKING (14!A28)', 16.0: 'STUDY (Eye 45 FD-E01/E02)', 24.0: 'STUDY comparison (Eye 45 FD-E01)'}


def variant(s, r):
    """Copy of the spec with only the well centre radius moved to r (in memory)."""
    v = copy.deepcopy(s)
    v['forward_defense']['eye_wells']['centre_radius_m'] = float(r)
    if not math.isclose(r, s['forward_defense']['eye_wells']['centre_radius_m']):
        v['forward_defense']['eye_wells']['study'] = f'FWD-V2 r{r:g}'
    return v


def _seg_dist(p, a, b):
    return fsh.distance_point_segment(p, a, b)


def _square_dist(p, c, u, half):
    """Distance from point p to a square of half size `half` centred at c with one axis along unit u (in the YZ plane); 0 inside."""
    dx, dy = p[0]-c[0], p[1]-c[1]
    a, b = abs(dx*u[0]+dy*u[1]), abs(-dx*u[1]+dy*u[0])
    return math.hypot(max(a-half, 0.0), max(b-half, 0.0))


def well_field_deg(s):
    """Geometric half-angles of the WORKING well for the WORKING aperture: unvignetted (whole aperture sees past the lip) and cut-off (none does)."""
    rw = fsh.prototype(s)['well_diameter_m']/2; ra = s['eye']['aperture']['value']/2; depth = fsh.stations(s)['well_depth']
    return math.degrees(math.atan((rw-ra)/depth)), math.degrees(math.atan((rw+ra)/depth))


def lance_angle_deg(s, w):
    """Smallest angle from the boresight (+X) at which the aperture edge nearest the axis sees the Dust Lance surface."""
    st = fsh.stations(s); ra = s['eye']['aperture']['value']/2; d = math.hypot(w['y'], w['z']); best = 90.0
    for i in range(241):
        x = st['face']+(st['lance_tip']-st['face'])*i/240
        best = min(best, math.degrees(math.atan2(d-ra-fsh.lance_radius_at(s, x), x-w['x0'])))
    return best


def crown_angle_deg(s, w):
    """Smallest angle from the boresight at which the aperture edge nearest the rim sees an engaged Crown carriage front (full stroke)."""
    c = fsh.crown(s); ra = s['eye']['aperture']['value']/2; d = math.hypot(w['y'], w['z'])
    x_front = c['carriage_x']+c['carriage']['axial']/2+fsh.crown_stroke_m(s)
    lateral = c['stowed_r']-c['carriage']['radial']/2-(d+ra)
    return math.degrees(math.atan2(lateral, x_front-w['x0'])) if x_front > w['x0'] else 90.0


def truss_nodes(s):
    t = fsh.truss(s); n = fsh.prototype(s)['truss_spoke_count']
    return [(r*math.cos(2*math.pi*(k+.5)/n), r*math.sin(2*math.pi*(k+.5)/n)) for k in range(n) for r in fsh.prototype(s)['truss_ring_radii_m']]


def shutter_travel(s, w, others):
    """FD-E03 shutter-travel screen: an armoured square leaf (well diameter + 2 x crown_shutter_overlap_m) sliding by its own size radially out,
    radially in or tangentially, in two planes: on the shield face under the layer (obstacles: other wells, the Lance hole, layer posts, the hub/cone
    fold) and in a pocket behind the skin at the well (Q43 keeps the shutter in the well: other wells, the Lance column, truss spokes and rings,
    the body shell). Margin of the open leaf in metres (negative = blocked). PROTOTYPE leaf; mechanism OPEN (OD-020)."""
    p = fsh.prototype(s); st = fsh.stations(s); leaf = p['well_diameter_m']+2*p['crown_shutter_overlap_m']; half = leaf/2
    d = math.hypot(w['y'], w['z']); ur = (w['y']/d, w['z']/d); ut = (-ur[1], ur[0]); rc = fsh.cone_start_radius(s); R = fsh.body_radius(s)
    posts = [((q['r']*math.cos(q['azimuth']), q['r']*math.sin(q['azimuth'])), q['radius']) for q in fsh.disruptor_posts(s) if q['layer'] == 1]
    n = p['truss_spoke_count']; m = fsh.truss(s)['member_radius']; members = []
    for k in range(n):
        a = 2*math.pi*(k+.5)/n
        members += [((r*math.cos(a), r*math.sin(a)), m) for r in [st['hub_opening_r']+(p['crown_housing_inner_radius_m']-st['hub_opening_r'])*i/200 for i in range(201)]]
    for r in [st['hub_opening_r'], *p['truss_ring_radii_m']]:
        members += [((r*math.cos(2*math.pi*i/720), r*math.sin(2*math.pi*i/720)), m) for i in range(720)]
    wells_ = [((o['y'], o['z']), o['radius']) for o in others]; lance = [((0.0, 0.0), p['lance_base_radius_m']+fsh.clearance(s))]
    out = {}
    for name, u in (('radial_out', ur), ('radial_in', (-ur[0], -ur[1])), ('tangential', ut)):
        c = (w['y']+u[0]*leaf, w['z']+u[1]*leaf)
        corners = [math.hypot(c[0]+a*half*ur[0]+b*half*ut[0], c[1]+a*half*ur[1]+b*half*ut[1]) for a in (-1, 1) for b in (-1, 1)]
        lo, hi = min(corners+[math.hypot(*c)-half]), max(corners)
        margin = lambda obs: min(_square_dist(q, c, ur, half)-r for q, r in obs)
        out[name] = dict(face_margin_m=round(margin(wells_+lance+posts), 3), face_crosses_fold=lo < rc < hi,
                         pocket_margin_m=round(margin(wells_+lance+members), 3), pocket_crosses_body_shell=lo < R < hi)
    return dict(leaf_m=leaf, travel_m=leaf, directions=out)


def screen(s, r):
    """One placement: positions, separations, structure margins, optics angles, shutter travel, support. Never changes B_array."""
    v = variant(s, r); st = fsh.stations(v); p = fsh.prototype(v); ws = fsh.wells(v); w = ws[0]; rw = w['radius']
    d = math.hypot(w['y'], w['z']); t = fsh.truss(v); m = t['member_radius']; n = p['truss_spoke_count']
    spokes = [2*math.pi*(k+.5)/n for k in range(n)]
    hub_r = fsh.body_radius(v)
    spoke_m = min(_seg_dist((w['y'], w['z']), (st['hub_opening_r']*math.cos(a), st['hub_opening_r']*math.sin(a)),
                            (p['crown_housing_inner_radius_m']*math.cos(a), p['crown_housing_inner_radius_m']*math.sin(a))) for a in spokes)-rw-m
    ring_radii = [st['hub_opening_r'], st['hub_opening_r']+p['truss_hub_ring_width_m']]+list(p['truss_ring_radii_m'])
    rings_hit = [R for R in p['truss_ring_radii_m'] if abs(R-d) < rw+m]
    ring_m = min(abs(R-d) for R in ring_radii)-rw-m
    posts = [q for q in fsh.disruptor_posts(v) if q['layer'] == 1]
    post_m = min(math.hypot(q['r']*math.cos(q['azimuth'])-w['y'], q['r']*math.sin(q['azimuth'])-w['z'])-rw-q['radius'] for q in posts)
    posts_hit = sorted({q['name'] for x in ws for q in posts if math.hypot(q['r']*math.cos(q['azimuth'])-x['y'], q['r']*math.sin(q['azimuth'])-x['z']) < rw+q['radius']})
    stack = st['well_depth']+v['prototype']['eye_module_depth_m']+v['prototype']['eye_backing_depth_m']
    behind = p['skin_thickness_m']+p['truss_depth_m']
    inside_body = d+rw < hub_r
    shared_mount = d+s['eye']['aperture']['value']/2 <= v['prototype']['eye_backing_radius_m']
    unv, cut = well_field_deg(v)
    nodes = truss_nodes(v)
    cells = sum(1 for x in ws for c in fsh.damage_cells(v) if c['r0']-rw < math.hypot(x['y'], x['z']) < c['r1']+rw
                and abs(((math.atan2(x['z'], x['y'])-(c['a0']+c['a1'])/2+math.pi) % (2*math.pi))-math.pi) < (c['a1']-c['a0'])/2+rw/d)
    lance_deg = lance_angle_deg(v, w)
    return dict(
        radius_m=r, status=STATUS.get(r, 'STUDY'),
        facets=[dict(label=x['label'], y=round(x['y'], 3), z=round(x['z'], 3), azimuth_deg=round(math.degrees(math.atan2(x['z'], x['y'])) % 360, 1),
                     facet_face_x=round(x['x0'], 3), local_face_x=round(x['x1'], 3)) for x in ws],
        separation=dict(adjacent_m=round(r*math.sqrt(2), 3), diagonal_m=round(2*r, 3), b_array_m=s['eye']['array_baseline']['value'],
                        b_array_status='WORKING r4 calibration input only (Eye 02!E8, FD-A03); geometric baselines derive from r; coherent baseline OPEN',
                        well_gap_m=round(r*math.sqrt(2)-2*rw, 3)),
        face=dict(zone='flat hub inside the body' if inside_body else 'conical Brow face outside the body',
                  lip_slope_m=round(fsh.face_x_at(v, max(d-rw, 0))-fsh.face_x_at(v, d+rw), 3)),
        structure=dict(lance_m=round(d-rw-p['lance_base_radius_m'], 3), hub_ring_m=round(st['hub_opening_r']-(d+rw), 3) if d < st['hub_opening_r'] else None,
                       spoke_m=round(spoke_m, 3), truss_ring_m=round(ring_m, 3), truss_rings_crossed=rings_hit,
                       layer_post_m=round(post_m, 3), layer_posts_crossed=posts_hit,
                       crown_housing_m=round(p['crown_housing_inner_radius_m']-(d+rw), 3), rim_m=round(p['rim_inner_radius_m']-(d+rw), 3),
                       facet_stack_m=round(stack, 3), skin_plus_truss_depth_m=round(behind, 3),
                       support='shared EYE mount on the spine column (PROTOTYPE)' if shared_mount else 'NONE modelled: per-facet frame into the truss needed (OPEN)',
                       nearest_truss_node_m=round(min(math.hypot(a-w['y'], b-w['z']) for a, b in nodes), 3),
                       service='from inside the body hub' if inside_body else 'outside the hull: crawler / EVA only (OPEN)',
                       damage_cells_overlapped=cells),
        optics=dict(well_unvignetted_deg=round(unv, 2), well_cutoff_deg=round(cut, 2), lance_clear_deg=round(lance_deg, 2),
                    lance_inside_well_field=lance_deg < cut, lance_inside_unvignetted=lance_deg < unv,
                    crown_engaged_deg=round(crown_angle_deg(v, w), 2), fov='OPEN (eye.field_of_view)',
                    port_note='outer port RADIUS 2.25 m, diameter 4.50 m (FD-A04, WORKING interpretation); ray / impact field OPEN'),
        shutter=shutter_travel(v, w, ws[1:]),
        mass='no allocation change: EYE 25 t and Brow 100 t (incl. Crown 25 t) unchanged; per-facet frames would add structure (OPEN)')


def screens(s):
    return [screen(s, r) for r in RADII]


if __name__ == '__main__':
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from spec import load
    s, *_ = load(Path(__file__).resolve().parents[2])
    print(json.dumps(screens(s), indent=1))
