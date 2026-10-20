"""HUM-002: the SP-45 walk-in general storeroom (12A!A48:I48, 33!A70:A95, 34!A107:A108), PROTOTYPE geometry and its fit screen.

The owner's compact program (33!C85:C88: 5 x 2.5 x 2.4 m clear, 30 m3 net, two 0.6 m rack depths, >= 1.3 m aisle) is WORKING with its
dimensions PROVISIONAL; placement, shell, port, hatch, racks, nets and rails are PROTOTYPE ([storeroom] rationale). The room's 2.4 m clear
height runs along +X, so with aft down its aft wall is the floor; in the cross-section its 5 m side is tangential (t) and its 2.5 m side radial
(u) about the angle phi, from the inner face at inner_face_m. One radial port off the crew trunk (crew_transfer.stationary role STORE_PORT)
has its sill on the room's floor. Vehicle frame; pure standard library.
"""
import math

import crew_transfer
import hull_geometry
import layout


def table(s):
    return s['storeroom']


def frame(s):
    phi = math.radians(table(s)['angle_deg'])
    return phi, (0.0, math.cos(phi), math.sin(phi)), (0.0, -math.sin(phi), math.cos(phi))


def world(s, x, u, t):
    _, eu, et = frame(s)
    return (x, u*eu[1]+t*et[1], u*eu[2]+t*et[2])


def station(s):
    """Outer and clear bounds: x (floor, ceiling), u (inner, outer face), t (half-lengths), with the wall."""
    q = table(s); P = q['program']; w = s['human_entry']['chamber_wall_m']
    L, W, H = P['clear_length_m'], P['clear_width_m'], P['clear_height_m']
    x0 = layout.at(s, q['floor_x']); d = q['inner_face_m']
    return dict(w=w, L=L, W=W, H=H, x0=x0, xf=x0+w, xc=x0+w+H, x1=x0+2*w+H, d=d, ui=d+w, uo=d+w+W, uout=d+2*w+W, half=L/2, half_out=L/2+w,
                phi=frame(s)[0], rack=P['rack_depth_m'], aisle=W-2*P['rack_depth_m'])


def port(s):
    """The radial port off the trunk: its station x (sill on the clear floor), clear and outer radius and its ends (trunk bore, room's clear
    inner face)."""
    st = station(s); c = s['crew_transfer']; rc = table(s)['port_clear_m']/2; x = st['xf']+rc
    return dict(x=x, clear=rc, outer=rc+c['passage_wall_m'], a=crew_transfer.radial(x, c['trunk_clear_radius_m'], st['phi']),
                b=crew_transfer.radial(x, st['ui'], st['phi']))


def corners(s, st=None):
    st = st or station(s)
    return [world(s, x, u, t) for x in (st['x0'], st['x1']) for u in (st['d'], st['uout']) for t in (-st['half_out'], st['half_out'])]


def leaf(s):
    """The sealed hatch: a round leaf on the room side of the inner wall, hinged on an axis along X at the +t edge, folding 180 deg flat against
    the wall. Hinge point and the leaf's closed centre (vehicle frame), radius, thickness, and the t span it parks over."""
    st, p, h = station(s), port(s), s['human_entry']; r = p['clear']+h['hatch_leaf_overlap_m']; tl = h['hatch_leaf_thickness_m']
    return dict(radius=r, thickness=tl, hinge=world(s, p['x'], st['ui']+tl, r), centre=world(s, p['x'], st['ui']+tl/2, 0.0),
                park=(r, 3*r), open_deg=180.0)


def rows(s):
    """Rack rows as (name, u0, u1, [(t0, t1) segments]): the outer row the full length, the inner row broken for the door and the parked leaf
    (mechanical_clearance_m clear of both)."""
    st, lf = station(s), leaf(s); c = s['prototype']['mechanical_clearance_m']; r = lf['radius']
    return [('Outer', st['uo']-st['rack'], st['uo'], [(-st['half'], st['half'])]),
            ('Inner', st['ui'], st['ui']+st['rack'], [(-st['half'], -r-c), (lf['park'][1]+c, st['half'])])]


def _box(name, role, x, u, t, size, s):
    """A fixture box: centre (x, u, t) in room coordinates, size along (X, t, u), axes (X, tangential, radial) as human_entry boxes use."""
    _, eu, et = frame(s)
    return dict(name=name, shape='box', role=role, world_centre=world(s, x, u, t), axes=((1.0, 0.0, 0.0), et, eu), size=size)


def fixtures(s):
    """Racks (uprights per bay at front and back, shelves), a retention net on each rack face, illustrative containers on the shelves, two floor
    tie-down rails along the aisle, a ceiling light strip over the aisle and the room panel above the door. Shapes as human_entry fixtures."""
    q, st, h = table(s), station(s), s['human_entry']; out = []; R = lambda x, u, t: world(s, x, u, t)
    rr = q['upright_radius_m']; ts = q['shelf_thickness_m']; fill_d, fill_h = q['container_fill']
    # DRONE-001: shelf cells holding a drone cassette (first bay of the station's row segment) get no illustrative container.
    drone_cells = {(d['row'], d['segment'], j) for d in s.get('drones', {}).get('stations', []) if d['anchor'] == 'storeroom' for j in d['shelves']}
    for name, u0, u1, segs in rows(s):
        front = u0 if name == 'Outer' else u1; ups = []
        for k, (t0, t1) in enumerate(segs, 1):
            n = max(1, math.ceil((t1-t0)/q['bay_max_m']-1e-9)); pitch = (t1-t0)/n
            for i in range(n+1):
                t = t0+pitch*i; t = min(max(t, t0+rr), t1-rr)
                ups += [(R(st['xf'], u, t), R(st['xc'], u, t)) for u in (u0+rr, u1-rr)]
            for j, lv in enumerate(q['shelf_levels_m'], 1):
                x = st['xf']+lv+ts/2
                out.append(_box(f'Storeroom_Rack_{name}_{k}_Shelf_{j}', 'rack shelf', x, (u0+u1)/2, (t0+t1)/2, (ts, t1-t0, st['rack']), s))
                top = (q['shelf_levels_m']+[st['H']])[j]-lv-ts
                for i in range(n):
                    if i == 0 and (name, k, j) in drone_cells:
                        continue
                    tc = t0+pitch*(i+.5); dz = top*fill_h
                    out.append(_box(f'Storeroom_Container_{name}_{k}_{j}_{i+1}', 'illustrative container (no inventory)', x+ts/2+dz/2,
                                    (u0+u1)/2, tc, (dz, pitch*fill_d, st['rack']*fill_d), s))
            fn = q['net_thickness_m']
            out.append(_box(f'Storeroom_Rack_{name}_{k}_Net', 'retention net (0 g)', (st['xf']+st['xc'])/2, front+(fn/2 if name == 'Outer' else -fn/2),
                            (t0+t1)/2, (st['H'], t1-t0, fn), s))
        out.append(dict(name=f'Storeroom_Rack_{name}_Uprights', shape='rods', role='rack upright', radius=rr, segments=ups))
    rows_ = rows(s); fo, fi = rows_[0][1], rows_[1][2]; td = q['tie_down_offset_m']; rt = q['tie_down_radius_m']; xr = st['xf']+rt
    out.append(dict(name='Storeroom_Tie_Down_Rail_Outer', shape='rod', role='floor tie-down rail', radius=rt,
                    points=[R(xr, fo-td, -st['half']+.1), R(xr, fo-td, st['half']-.1)]))
    for k, (t0, t1) in enumerate(rows_[1][3], 1):
        out.append(dict(name=f'Storeroom_Tie_Down_Rail_Inner_{k}', shape='rod', role='floor tie-down rail', radius=rt,
                        points=[R(xr, fi+td, t0+.1), R(xr, fi+td, t1-.1)]))
    la, lt, lr = h['light_size_m']
    out.append(_box('Storeroom_Light', 'light strip', st['xc']-lr/2, (fo+fi)/2, 0.0, (lr, min(st['L']-1.0, 2*la), lt), s))
    pa, pt, pr = h['panel_size_m']; p = port(s)
    out.append(_box('Storeroom_Panel', 'storeroom panel: fire and smoke detection, ventilation, cabin pressure and hatch status (all OPEN)',
                    p['x']+p['outer']+h['opening_margin_m']+pt/2, st['ui']+pr/2, 0.0, (pt, pa, pr), s))
    return out


def mannequin(s):
    """Thrust-review figure (non-canon scale guide) standing on the floor in the aisle with aft down, head forward, facing the outer rack
    landing_body_gap_m off its face: one hand on the front of the highest shelf below landing_grip_height_m, the other at its side. Its eye looks along the aisle toward the door. Vehicle frame."""
    m = s['human_entry']['mannequin']; H = s['prototype']['human_height_m']; st = station(s); rows_ = rows(s)
    fo, fi = rows_[0][1], rows_[1][2]; ua = fo-m['landing_body_gap_m']; tb = -st['half']+1.0     # the body landing_body_gap_m off the rack face
    def at(x, y, z):                 # x across the body (along t), y toward the face (+u, the outer rack), z from the feet toward the head (+X)
        return world(s, st['xf']+z, ua+y, tb+x)
    shoulder = at(.20, 0, .75*H); level = max(v for v in s['storeroom']['shelf_levels_m'] if v <= m['landing_grip_height_m'])
    grip = world(s, st['xf']+level, fo, tb+.30)
    rods = [('Human_Store_Torso', [at(0, 0, .38*H), at(0, 0, .78*H)], .13),
            ('Human_Store_Head', [at(0, 0, H-.20), at(0, 0, H-.11)], .11),
            ('Human_Store_Arm_Shelf', [shoulder, grip], .055),
            ('Human_Store_Arm_Side', [at(-.20, 0, .75*H), at(-.28, 0, .43*H)], .055)]
    for sign in (-1, 1):
        rods.append((f'Human_Store_Leg_{sign}', [at(sign*.13, 0, .07), at(0, 0, .40*H)], .07))
    eye = at(0, .08, m['eye_height_m']); door = world(s, st['xf']+1.0, st['ui'], 0.0)
    return dict(rods=rods, eye=eye, look=crew_transfer.sub(door, eye), up=(1.0, 0.0, 0.0), grip=grip, reach=math.dist(shoulder, grip),
                headroom=st['H']-H, aisle=fo-fi)


def cameras(s):
    """First-person review cameras: from the trunk axis across the port into the room (the hatch closed in the saved file), and at the
    storeroom figure's eye along the aisle toward the door."""
    m = s['human_entry']['mannequin']; p = port(s); st = station(s); man = mannequin(s)
    return [dict(name='CAM_HUM_STORE_PORT', at=crew_transfer.radial(p['x']+.15, -m['vestibule_camera_offset_m'], st['phi']), look=crew_transfer.radial(0.0, 1.0, st['phi']),
                 up=(1.0, 0.0, 0.0), lens=m['camera_lens_mm'], clip_start=.05, role='eye of crew in the trunk at the storeroom port, looking out through the port into SP-45'),
            dict(name='CAM_HUM_STORE_EYE', at=man['eye'], look=man['look'], up=man['up'], lens=m['camera_lens_mm'], clip_start=.2,
                 role="storeroom figure's eye with aft down, looking along the aisle to the door and the parked leaf")]


# ---------- fit screen -------------------------------------------------------------------------------------------------------------------

def _surface(s, step=0.1):
    st = station(s); pts = []
    xs = [st['x0']+(st['x1']-st['x0'])*i/max(1, round((st['x1']-st['x0'])/step)) for i in range(round((st['x1']-st['x0'])/step)+1)]
    us = [st['d']+(st['uout']-st['d'])*i/max(1, round((st['uout']-st['d'])/step)) for i in range(round((st['uout']-st['d'])/step)+1)]
    ts = [-st['half_out']+2*st['half_out']*i/round(2*st['half_out']/step) for i in range(round(2*st['half_out']/step)+1)]
    for x in xs:
        for u in us:
            for t in ts:
                if x in (xs[0], xs[-1]) or u in (us[0], us[-1]) or t in (ts[0], ts[-1]):
                    pts.append(world(s, x, u, t))
    return pts


def _segment(p, a, b):
    ab = crew_transfer.sub(b, a); ap = crew_transfer.sub(p, a); L2 = crew_transfer.dot(ab, ab)
    k = 0.0 if L2 == 0 else max(0.0, min(1.0, crew_transfer.dot(ap, ab)/L2))
    return math.dist(p, crew_transfer.add(a, ab, k))


def _obb(p, centre, axes, half):
    d = crew_transfer.sub(p, centre)
    return math.sqrt(sum(max(abs(crew_transfer.dot(d, e))-h, 0.0)**2 for e, h in zip(axes, half)))


def check(s):
    """Fit screen (PROTOTYPE): clearances to the spine, hull, refuge, service fittings (the human-entry chamber and node by their radius),
    survival packs, sector keels and the airlock; the port against the trunk's existing branches and the thrust ladder's reach; the owner's
    program (clear volume, aisle). Returns (rows, failures)."""
    import forward_shield
    import human_entry
    import power_storage
    st, p, q = station(s), port(s), table(s); P = q['program']; clr = s['prototype']['mechanical_clearance_m']; out = {}
    pts = _surface(s); cs = corners(s, st)
    out['spine_gap_m'] = st['d']-max(layout.spine_radius_at(s, x) for x in (st['x0'], st['x1']))
    out['hull_gap_m'] = min(hull_geometry.inner_radius_at(s, c[0])-math.hypot(c[1], c[2]) for c in cs)
    ref = hull_geometry.refuge(s)
    out['refuge_gap_m'] = st['x0']-ref['x1'] if st['d'] < ref['outer'] else None
    fits = {}
    for f in hull_geometry.service_fittings(s):
        rad = f['radius']
        if f['name'] in {g['name'] for g in human_entry.ports(s)}:
            e = human_entry.stations(s, f); rad = max(rad, e['chamber_r']+e['wall'])
        a, b = crew_transfer.radial(f['x'], f['r0'], f['theta']), crew_transfer.radial(f['x'], f['r1'], f['theta'])
        fits[f['name']] = min(_segment(v, a, b) for v in pts)-rad
    out['fitting_gaps_m'] = fits
    out['pack_gaps_m'] = {k['name']: min(_obb(v, k['center'], ((1.0, 0.0, 0.0), k['t'], k['u']), ((k['x1']-k['x0'])/2, k['width']/2, (k['r1']-k['r0'])/2)) for v in pts)
                          for k in power_storage.packs(s)}
    out['keel_gaps_m'] = {k['name']: min(_segment(v, crew_transfer.radial(k['x0'], k['r'], k['theta']), crew_transfer.radial(k['x1'], k['r'], k['theta'])) for v in pts)-k['radius']
                          for k in forward_shield.sector_keels(s)}
    # The port: clear of the trunk's other branches, inside the trunk, and its run from the spine to the room clear of the survival packs.
    m = s['human_entry']['opening_margin_m']; tr = s['crew_transfer']['trunk_clear_radius_m']; worst = math.inf; near = None
    for name, x, th, r in human_entry.openings(s):
        if name == 'Crew_Store_Port':
            continue
        d = crew_transfer.angle_diff(st['phi'], th)
        if math.cos(d) <= 0:
            continue
        gap = max(abs(x-p['x'])-r-p['outer'], tr*abs(math.sin(d))-r-p['outer'])
        if gap < worst:
            worst, near = gap, name
    out['port_branch_gap_m'] = worst; out['port_nearest_branch'] = near
    trunk = crew_transfer.stationary(s)[0]; w = s['crew_transfer']['passage_wall_m']
    out['port_in_trunk'] = trunk['points'][0][0]+w <= p['x']-p['outer'] and p['x']+p['outer'] <= trunk['points'][1][0]-w
    run = [crew_transfer.radial(p['x']+p['outer']*math.cos(a), r, st['phi']+p['outer']*math.sin(a)/r) for r in (1.0, (1.0+st['d'])/2, st['d']) for a in [k*math.pi/8 for k in range(16)]]
    out['port_pack_gap_m'] = min(_obb(v, k['center'], ((1.0, 0.0, 0.0), k['t'], k['u']), ((k['x1']-k['x0'])/2, k['width']/2, (k['r1']-k['r0'])/2)) for v in run for k in power_storage.packs(s))
    L = human_entry.trunk_ladder(s)
    out['sill_x'] = st['xf']; out['ladder_span_x'] = [L['floor'], L['top']]; out['ladder_reaches_sill'] = L['floor'] <= st['xf'] <= L['top']
    out['ladder_to_port_m'] = math.dist(crew_transfer.radial(p['x'], L['rl'], L['th']), crew_transfer.radial(p['x'], tr, st['phi']))
    out['clear_m3'] = st['L']*st['W']*st['H']; out['aisle_m'] = st['aisle']
    racks = sum((t1-t0)*(u1-u0)*st['H'] for _, u0, u1, segs in rows(s) for t0, t1 in segs)
    out['rack_m3'] = racks; out['net_after_racks_m3'] = out['clear_m3']-racks
    man = mannequin(s); out['headroom_m'] = man['headroom']; out['shelf_reach_m'] = man['reach']
    fails = []
    for key, v in (('spine_gap_m', out['spine_gap_m']), ('hull_gap_m', out['hull_gap_m']), ('refuge_gap_m', out['refuge_gap_m']),
                   *((f'fitting {k}', v) for k, v in fits.items()), *((f'pack {k}', v) for k, v in out['pack_gaps_m'].items()),
                   *((f'keel {k}', v) for k, v in out['keel_gaps_m'].items()), ('port_pack_gap_m', out['port_pack_gap_m'])):
        if v is not None and v < clr-1e-6:
            fails.append(f'{key} {v:.3f} m below {clr} m')
    if out['port_branch_gap_m'] < m-1e-6:
        fails.append(f"port within {out['port_branch_gap_m']:.3f} m of {near} (opening margin {m} m)")
    if not out['port_in_trunk']:
        fails.append('the port leaves the trunk span')
    if not out['ladder_reaches_sill']:
        fails.append(f"sill X {st['xf']:.2f} m outside the thrust ladder ({L['floor']:.2f}-{L['top']:.2f} m)")
    if abs(out['clear_m3']-P['net_m3']) > 1e-6:
        fails.append(f"clear cuboid {out['clear_m3']:.2f} m3 is not the owner's {P['net_m3']} m3")
    if st['aisle'] < P['aisle_min_m']-1e-9:
        fails.append(f"aisle {st['aisle']:.2f} m below {P['aisle_min_m']} m")
    return out, fails


if __name__ == '__main__':
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import spec
    s, *_ = spec.load()
    rows_, fails = check(s)
    print(json.dumps({'station': {k: round(v, 3) if isinstance(v, float) else v for k, v in station(s).items()}, **rows_, 'failures': fails}, indent=1, default=str))
    sys.exit(1 if fails else 0)
