"""FWD-V2 reversible alternate truss for an outer Eye placement (Eye 45 FD-A01/A02, S&E 50 AG-A01/A02, 15 FWD-V2-EYE-2026-10-13). Pure,
standard library only; STUDY in memory, never the production truss (r4 stays WORKING, FD-A06).

Owner selection (FD-A01): the four diagonal spokes bifurcate into a continuous load-bearing collar round each well; truss rings and disruptor
posts the wells cross are rerouted, never simply deleted; the 12-spoke pattern is not rotated onto the Crown bays. FD-A02: four independent
per-facet frames tied to the collar (on truss nodes) and protected radial power/data/coolant raceways on the aft face; crawler-first window
cartridge service from the protected aft side.

Every size below is PROTOTYPE (named); structure mass, stiffness, FEA, optical stability and impact rating stay OPEN.

    python3 src/wayfarer/eye_truss_study.py [radius ...]       # print the alternate truss screen
"""
import math
import eye_placement as ep
import forward_shield as fsh

BRANCH_PHI = (60.0, 120.0)        # PROTOTYPE: collar angles (from the outward radial) where the outer / inner spoke branches land
VERTICAL_STEP_DEG = 90.0          # PROTOTYPE: chord-to-chord verticals round each collar (90 deg leaves a hatch gap for the 2.6 m window cartridge)
COLLAR_STEP_DEG = 15.0            # PROTOTYPE: collar polyline vertex spacing (display resolution)
FRAME_PHI = (45.0, 135.0, 225.0, 315.0)   # PROTOTYPE: facet-frame struts to collar aft-chord nodes
RACEWAY_SIDE_M = 0.4              # PROTOTYPE: raceway envelope (power/data/coolant), protected aft face
RACEWAY_SAG_M = 0.05              # PROTOTYPE: extra aft standoff for straight chords between cone points (they sag aft of the cone)
RACEWAY_OFFSET_M = 1.0            # PROTOTYPE: raceway runs parallel to its spoke, offset away from the nearer sector keel (ties land on the spoke)
CARTRIDGE_STEP_DEG = 5.0          # search step for the window-cartridge withdrawal direction
CARTRIDGE_EXTRA_M = (0.0, 0.5, 1.0, 1.5, 2.0, 3.0)   # search: how far past the collar the cartridge slides before it goes aft


def collar_radius(s):
    """Collar centreline radius round a well: clear of the well wall by the shared clearance, and large enough that the relocated layer posts on
    its nodes stand outside the 2.25 m outer port (FD-A04) by the post radius and the clearance."""
    p = fsh.prototype(s); clr = fsh.clearance(s); rw = p['well_diameter_m']/2; m = p['truss_member_radius_m']
    port = max(fsh.eye_port_outer_radius(s, q) for q in fsh.disruptor_layers(s))       # a hexagonal port's corners
    return max(rw+clr+m, port+p['disruptor_post_radius_m']+clr)


def _frame(w):
    d = math.hypot(w['y'], w['z']); ur = (w['y']/d, w['z']/d); return d, ur, (-ur[1], ur[0])


def _xa(s, r):
    return fsh.truss_aft_at(s, r)+fsh.prototype(s)['truss_member_radius_m']


def _xf(s, r):
    return fsh.skin_aft_at(s, r)-fsh.prototype(s)['truss_member_radius_m']


def collar_point(s, w, phi_deg, chord, rc=None):
    rc = collar_radius(s) if rc is None else rc; d, ur, ut = _frame(w); a = math.radians(phi_deg)
    y, z = w['y']+rc*(math.cos(a)*ur[0]+math.sin(a)*ut[0]), w['z']+rc*(math.cos(a)*ur[1]+math.sin(a)*ut[1])
    r = math.hypot(y, z)
    return ((_xa if chord == 'aft' else _xf)(s, r), y, z)


def radial_point(s, w, r, chord):
    d, ur, _ = _frame(w)
    return ((_xa if chord == 'aft' else _xf)(s, r), r*ur[0], r*ur[1])


def ring_crossings(s, w, R):
    """Collar angles where a truss ring of radius R meets the collar circle (empty when it misses)."""
    d, rc = math.hypot(w['y'], w['z']), collar_radius(s)
    c = (R*R-d*d-rc*rc)/(2*d*rc)
    if abs(c) >= 1:
        return []
    phi = math.degrees(math.acos(c)); return [phi, 360-phi]


def _polar(p):
    return math.atan2(p[2], p[1]) % (2*math.pi)


def alternate(s):
    """The alternate truss of the current placement (s already carries the study radius): the production members it replaces and the members,
    posts, frames and raceways it adds. Each item: name, role, polyline points (ship frame) and radius."""
    p = fsh.prototype(s); st = fsh.stations(s); m = p['truss_member_radius_m']; n = p['truss_spoke_count']; rc = collar_radius(s)
    t = fsh.truss(s, base=True); r_in, r_out = st['hub_opening_r']+p['truss_hub_ring_width_m'], p['crown_housing_inner_radius_m']
    ws = [w for w in fsh.wells(s) if not fsh.in_hub(s, w)]
    removed, add = [], []
    rings_hit = sorted({R for w in ws for R in p['truss_ring_radii_m'] if ring_crossings(s, w, R)})
    for w in ws:
        d, ur, ut = _frame(w); j = w['index']; az = math.atan2(w['z'], w['y'])
        k = next(i for i in range(n) if abs(((2*math.pi*(i+.5)/n-az+math.pi) % (2*math.pi))-math.pi) < 1e-6)
        removed += [f'Truss_Spoke_{k+1:02}_{lab}' for lab in ('aft', 'fwd', 'diagonal')]
        r_si, r_so = d-2*rc, d+2*rc                                     # PROTOTYPE split nodes one collar radius before / after the collar
        tag = f'Study_Eye{j}'
        for seg, (r0, r1) in (('in', (r_in, r_si)), ('out', (r_so, r_out))):
            for chord in ('aft', 'fwd'):
                add.append(dict(name=f'{tag}_Spoke_{seg}_{chord}', role='spoke', well=j, pts=[radial_point(s, w, r0, chord), radial_point(s, w, r1, chord)], radius=m))
            add.append(dict(name=f'{tag}_Spoke_{seg}_diagonal', role='spoke', well=j, pts=[radial_point(s, w, r0, 'aft'), radial_point(s, w, r1, 'fwd')], radius=m))
        for seg, r_split, phis in (('in', r_si, (BRANCH_PHI[1], 360-BRANCH_PHI[1])),
                                   ('out', r_so, (BRANCH_PHI[0], 360-BRANCH_PHI[0]))):
            for phi in phis:
                for chord in ('aft', 'fwd'):
                    add.append(dict(name=f'{tag}_Branch_{seg}_{phi:g}_{chord}', role='branch', well=j,
                                    pts=[radial_point(s, w, r_split, chord), collar_point(s, w, phi, chord)], radius=m))
        verts = sorted({round(i*COLLAR_STEP_DEG, 6) for i in range(int(360/COLLAR_STEP_DEG))} | {round(x, 6) for R in rings_hit for x in ring_crossings(s, w, R)})
        for chord in ('aft', 'fwd'):
            add.append(dict(name=f'{tag}_Collar_{chord}', role='collar', well=j, pts=[collar_point(s, w, a, chord) for a in verts+[verts[0]]], radius=m, phis=verts))
        for i in range(int(360/VERTICAL_STEP_DEG)):
            a = i*VERTICAL_STEP_DEG
            add.append(dict(name=f'{tag}_Collar_Vertical_{a:g}', role='collar', well=j, pts=[collar_point(s, w, a, 'aft'), collar_point(s, w, a, 'fwd')], radius=m))
        # FD-A02 per-facet frame: a backing plate behind the facet module, four struts to collar aft-chord nodes.
        pr = p['well_diameter_m']/2; bx = w['x0']-s['prototype']['eye_module_depth_m']-s['prototype']['eye_backing_depth_m']/2
        add.append(dict(name=f'{tag}_Facet_Frame_Plate', role='facet_frame', well=j, pts=[(bx-s['prototype']['eye_backing_depth_m']/2, w['y'], w['z']),
                        (bx+s['prototype']['eye_backing_depth_m']/2, w['y'], w['z'])], radius=pr, plate=True))
        for a in FRAME_PHI:
            e = math.radians(a); q = (bx, w['y']+pr*(math.cos(e)*ur[0]+math.sin(e)*ut[0]), w['z']+pr*(math.cos(e)*ur[1]+math.sin(e)*ut[1]))
            add.append(dict(name=f'{tag}_Facet_Frame_Strut_{a:g}', role='facet_frame', well=j, pts=[q, collar_point(s, w, a, 'aft')], radius=m))
        # FD-A02 raceway: from the plate straight aft out of the truss, then inward on the protected aft face, parallel to its spoke and offset
        # away from the nearer sector keel, to the body hull. The aft offset is taken normal to the cone (shared clearance to the aft chords).
        rr = RACEWAY_SIDE_M/2
        def xoff(r):
            slope = math.atan2(abs(fsh.truss_aft_at(s, r+.5)-fsh.truss_aft_at(s, r-.5)), 1.0)
            return fsh.truss_aft_at(s, r)+m-(m+fsh.clearance(s)+RACEWAY_SAG_M+rr)/math.cos(slope)
        keel = min(fsh.sector_azimuths(s), key=lambda a: abs(((a-az+math.pi) % (2*math.pi))-math.pi))
        side = -1.0 if ((keel-az+math.pi) % (2*math.pi))-math.pi > 0 else 1.0; off = side*RACEWAY_OFFSET_M
        rho_end = math.sqrt(fsh.body_radius(s)**2-off*off); steps = max(2, int(d-rho_end))
        pt = lambda rho: (xoff(math.hypot(rho, off)), rho*ur[0]+off*ut[0], rho*ur[1]+off*ut[1])
        run = [pt(d-(d-rho_end)*i/steps) for i in range(steps+1)]
        add.append(dict(name=f'{tag}_Raceway', role='raceway', well=j, radius=rr,
                        pts=[(bx-s['prototype']['eye_backing_depth_m']/2, w['y'], w['z']), (xoff(d), w['y'], w['z'])]+run))
    # Truss rings the collars cross: each chord becomes arcs from collar to collar (the collars carry the ring through).
    for k, ring in enumerate(t['rings']):
        R = ring['radius']
        if R not in rings_hit:
            continue
        removed.append(f'Truss_Ring_{k+1:02}')
        chord = 'aft' if math.isclose(ring['x'], _xa(s, R)) else 'fwd'
        gaps = []
        for w in ws:
            pts = [collar_point(s, w, a, chord) for a in ring_crossings(s, w, R)]
            a0, a1 = sorted(_polar(q) for q in pts)
            gaps.append((a0, a1) if a1-a0 < math.pi else (a1, a0+2*math.pi))
        gaps.sort()
        for i, (g0, g1) in enumerate(gaps):
            h0 = gaps[(i+1) % len(gaps)][0]+(2*math.pi if i+1 == len(gaps) else 0)
            seg = max(2, int(math.degrees(h0-g1)/3))
            add.append(dict(name=f'Study_Ring_{k+1:02}_Arc_{i+1}', role='ring_arc', well=0, radius=m,
                            pts=[(ring['x'], R*math.cos(g1+(h0-g1)*u/seg), R*math.sin(g1+(h0-g1)*u/seg)) for u in range(seg+1)]))
    # Disruptor posts inside a port (plus clearance): replaced by two posts on the collar's radial nodes (clear of the tangential eyelids).
    layers = fsh.disruptor_layers(s); port = max(fsh.eye_port_outer_radius(s, q) for q in layers); pr_ = p['disruptor_post_radius_m']; clr = fsh.clearance(s)
    for q in fsh.disruptor_posts(s, base=True):
        y, z = q['r']*math.cos(q['azimuth']), q['r']*math.sin(q['azimuth'])
        if any(math.hypot(y-w['y'], z-w['z']) < port+pr_+clr for w in ws):
            removed.append(q['name'])
    for w in ws:
        d, ur, _ = _frame(w)
        for li, layer in enumerate(layers, 1):
            for tag, r in (('in', d-rc), ('out', d+rc)):
                x0 = fsh.face_x_at(s, r) if li == 1 else fsh.layer_x(s, layers[li-2], r)[1]; x1 = fsh.layer_x(s, layer, r)[0]
                add.append(dict(name=f'Study_Eye{w["index"]}_Post_{li:02}_{tag}', role='post', well=w['index'], radius=pr_, pts=[(x0, r*ur[0], r*ur[1]), (x1, r*ur[0], r*ur[1])]))
    # Sector ties landing on a replaced spoke/ring node: rerouted to the collar node where that same ring meets the collar (keel side), so the
    # tie keeps its ring node and stays off the radial raceway line.
    for tie in fsh.sector_ties(s, base=True):
        b = tie['b']
        near = [w for w in ws if math.hypot(b[1]-w['y'], b[2]-w['z']) < 2*rc]
        if near:
            w = near[0]; phis = ring_crossings(s, w, math.hypot(b[1], b[2])) or list(range(0, 360, int(COLLAR_STEP_DEG)))
            cands = [collar_point(s, w, a, 'aft') for a in phis]
            nb = min(cands, key=lambda c: math.dist(c, tie['a']))
            removed.append(tie['name'])
            add.append(dict(name=f'Study_{tie["name"]}', role='sector_tie', well=w['index'], pts=[tie['a'], nb], radius=tie['radius']))
    return dict(radius_m=math.hypot(ws[0]['y'], ws[0]['z']) if ws else None, collar_radius_m=rc, removed=removed, members=add, rings_rerouted=rings_hit)


# ---------- screen ---------------------------------------------------------------------------------------------------------

def _segs(item):
    return list(zip(item['pts'], item['pts'][1:]))


def _kept(s, alt):
    """Production truss members the alternate keeps (spokes, ring polylines, sector ties, mount struts) as polylines with radius."""
    t = fsh.truss(s, base=True); gone = set(alt['removed']); out = []
    for sp in t['spokes']:
        for lab, pts in sp['members']:
            if f"Truss_Spoke_{sp['index']:02}_{lab}" not in gone:
                out.append(dict(name=f"Truss_Spoke_{sp['index']:02}_{lab}", pts=pts, radius=t['member_radius']))
    for k, r in enumerate(t['rings']):
        if f'Truss_Ring_{k+1:02}' not in gone:
            out.append(dict(name=f'Truss_Ring_{k+1:02}', radius=t['member_radius'],
                            pts=[(r['x'], r['radius']*math.cos(2*math.pi*i/96), r['radius']*math.sin(2*math.pi*i/96)) for i in range(97)]))
    out += [dict(name=x['name'], pts=[x['a'], x['b']], radius=x['radius']) for x in fsh.sector_ties(s, base=True) if x['name'] not in gone]
    out += [dict(name=x['name'], pts=[x['a'], x['b']], radius=x['radius']) for x in fsh.mount_struts(s)]
    return out


def _well_axis(s, w):
    stack = s['prototype']['eye_module_depth_m']+s['prototype']['eye_backing_depth_m']
    return (w['x0']-stack, w['y'], w['z']), (w['x1'], w['y'], w['z'])


def _clip_yz(a, b, lo, hi):
    """Part of segment ab with lo <= x <= hi, projected to (y, z); None when it misses the slab."""
    (xa, ya, za), (xb, yb, zb) = a, b
    if xa == xb:
        return ((ya, za), (yb, zb)) if lo <= xa <= hi else None
    t0, t1 = sorted(((lo-xa)/(xb-xa), (hi-xa)/(xb-xa)))
    t0, t1 = max(t0, 0.0), min(t1, 1.0)
    if t0 > t1:
        return None
    f = lambda t: (ya+(yb-ya)*t, za+(zb-za)*t)
    return f(t0), f(t1)


def _d2(p0, p1, q0, q1):
    pad = lambda u: (0.0, *u)
    return fsh.segment_distance(pad(p0), pad(p1), pad(q0), pad(q1))


def cartridge_access(s, alt, w, obstacles):
    """FD-A02 / AG-A04 window-cartridge service path, crawler first from the protected aft side: the cartridge slides out of the well wall at the
    window station (a well-wall hatch, design OPEN) in collar direction phi, past the collar, then aft out of the truss. Best direction and margin."""
    e = next(x for x in fsh.eye_shutters(s) if x['index'] == w['index'])['window']; wr, th = e['radius'], e['thickness']
    rc = alt['collar_radius_m']; clr = fsh.clearance(s); d, ur, ut = _frame(w); out = []
    for i in range(int(360/CARTRIDGE_STEP_DEG)):
      for extra in CARTRIDGE_EXTRA_M:
        a = math.radians(i*CARTRIDGE_STEP_DEG); u = (math.cos(a)*ur[0]+math.sin(a)*ut[0], math.cos(a)*ur[1]+math.sin(a)*ut[1])
        reach = rc+fsh.prototype(s)['truss_member_radius_m']+clr+wr+extra
        c0, c1 = (w['y'], w['z']), (w['y']+reach*u[0], w['z']+reach*u[1])
        x_end = fsh.truss_aft_at(s, math.hypot(*c1))-clr
        worst = math.inf
        for o in obstacles:
            for a0, b0 in _segs(o):
                for path, lo, hi in (((c0, c1), e['x']-th/2, e['x']+th/2), ((c1, c1), x_end, e['x'])):
                    q = _clip_yz(a0, b0, lo, hi)
                    if q:
                        worst = min(worst, _d2(path[0], path[1], q[0], q[1])-wr-o['radius'])
        out.append((worst, i*CARTRIDGE_STEP_DEG, reach, c1, x_end))
    best = max(out)
    clear = sorted({a for m, a, *_ in out if m >= clr})
    return dict(best_phi_deg=best[1], margin_m=round(best[0], 3), slide_m=round(best[2], 3), clear_directions_deg=clear, window_radius_m=wr,
                path=[(e['x'], w['y'], w['z']), (e['x'], *best[3]), (best[4], *best[3])],
                hatch='well-wall hatch at the window station: design, seal and latch OPEN', crawler='protected aft face; safe-mode interlocks (FD-A02); FLIGHT_EVA HOLD')


def screen(s, r, access=True):
    """Alternate truss at radius r: clearances, continuity, member lengths, cartridge access, unchanged Crown axes. STUDY, in memory.
    access=False skips the cartridge-access search (seconds per well) and reports cartridge_access None."""
    v = ep.variant(s, r); alt = alternate(v); p = fsh.prototype(v); clr = fsh.clearance(v)
    ws = [w for w in fsh.wells(v) if not fsh.in_hub(v, w)]
    if not ws:
        return dict(radius_m=r, status=ep.STATUS.get(r, 'STUDY'), alternate=False, note='wells inside the hub: production truss unchanged')
    kept = _kept(v, alt); added = alt['members']
    # Well clearance: every added and kept member stays outside each well and facet stack (own frame and raceway excluded).
    well_margin = math.inf
    for w in ws:
        a0, a1 = _well_axis(v, w)
        for o in added+kept:
            if o.get('well') == w['index'] and o['role'] in ('facet_frame', 'raceway'):
                continue
            if o.get('role') == 'post':
                continue
            for q0, q1 in _segs(o):
                well_margin = min(well_margin, fsh.segment_distance(a0, a1, q0, q1)-w['radius']-o['radius'])
    # Raceways (aft face): clear of every truss member, tie and mount strut except their own facet frame.
    race_margin = math.inf
    for o in [x for x in added if x['role'] == 'raceway']:
        for q in added+kept:
            if q is o or q.get('plate') or q['role' if 'role' in q else 'name'] == 'post' or (q.get('well') == o['well'] and q.get('role') == 'facet_frame'):
                continue
            for a0, a1 in _segs(o)[1:]:
                for q0, q1 in _segs(q):
                    race_margin = min(race_margin, fsh.segment_distance(a0, a1, q0, q1)-o['radius']-q['radius'])
    # Posts: outside the outer port, clear of the open eyelid leaves.
    ports = max(fsh.eye_port_outer_radius(v, q) for q in fsh.disruptor_layers(v))
    posts = [o for o in added if o['role'] == 'post']
    port_margin = min(math.hypot(o['pts'][0][1]-w['y'], o['pts'][0][2]-w['z'])-ports-o['radius'] for o in posts for w in ws)
    leaf_margin = math.inf
    for e in fsh.eye_shutters(v):
        ur = (math.cos(e['azimuth']), math.sin(e['azimuth'])); ut = (-ur[1], ur[0])
        for leaf in e['leaves']:
            c = (e['y']+leaf['sign']*e['open_t']*ut[0], e['z']+leaf['sign']*e['open_t']*ut[1])
            for o in posts:
                dy, dz = o['pts'][0][1]-c[0], o['pts'][0][2]-c[1]
                lr, lt = abs(dy*ur[0]+dz*ur[1])-e['radial']/2, abs(dy*ut[0]+dz*ut[1])-e['tangential']/2
                gap = math.hypot(max(lr, 0), max(lt, 0)) if max(lr, lt) > 0 else max(lr, lt)    # signed distance to the leaf rectangle
                leaf_margin = min(leaf_margin, gap-o['radius'])
    # Continuity: the spoke ends on the hub ring and the housing, the ring arcs and collars form one connected structure per placement.
    key = lambda q: tuple(round(x, 3) for x in q)
    parent = {}
    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for o in added:
        if o['role'] in ('facet_frame', 'raceway', 'post'):
            continue
        for q0, q1 in _segs(o):
            parent[find(key(q0))] = find(key(q1))
    # Spoke ends on the hub ring, the Crown housing or a kept truss ring land on the production frame, which is itself one structure: they
    # share one anchor (at r30 no ring crosses a collar, so no ring arcs join the four collars directly).
    st = fsh.stations(v); r_in, r_out = st['hub_opening_r']+p['truss_hub_ring_width_m'], p['crown_housing_inner_radius_m']
    anchors = [r_in, r_out]+[rr['radius'] for k, rr in enumerate(fsh.truss(v, base=True)['rings']) if f'Truss_Ring_{k+1:02}' not in alt['removed']]
    for o in added:
        if o['role'] == 'spoke':
            for q in (o['pts'][0], o['pts'][-1]):
                if any(abs(math.hypot(q[1], q[2])-R) < 1e-6 for R in anchors):
                    parent[find(key(q))] = find('ANCHOR')
    roots = {find(key(q)) for o in added if o['role'] not in ('facet_frame', 'raceway', 'post') for q in o['pts']}
    names = {o['name'] for o in added}
    def replaced(name):
        if name.startswith('Truss_Spoke_'):
            return any(x.startswith('Study_Eye') and '_Spoke_' in x for x in names)
        if name.startswith('Truss_Ring_'):
            return any(x.startswith(f'Study_Ring_{name[-2:]}_Arc_') for x in names)
        if name.startswith('Disruptor_Post_'):
            return any(x.startswith('Study_Eye') and f'_Post_{name.split("_")[2]}_' in x for x in names)
        return f'Study_{name}' in names
    orphans = [x for x in alt['removed'] if not replaced(x)]
    t = fsh.truss(v); n = p['truss_spoke_count']
    spoke_azimuths_kept = all(abs(((sp['azimuth']-2*math.pi*(sp['index']-.5)/n+math.pi) % (2*math.pi))-math.pi) < 1e-9 for sp in t['spokes'])
    unanchored = [o['name'] for o in added if o['role'] == 'branch' and find(key(o['pts'][-1])) != find(key(added[0]['pts'][0]))]
    # Lengths: replaced vs added, by role (mass per metre OPEN).
    length = lambda o: sum(math.dist(a, b) for a, b in _segs(o))
    removed_len = sum(length(o) for o in [dict(pts=pts) for sp in t['spokes'] for lab, pts in sp['members'] if f"Truss_Spoke_{sp['index']:02}_{lab}" in alt['removed']]) \
        + sum(2*math.pi*rr['radius'] for k, rr in enumerate(t['rings']) if f'Truss_Ring_{k+1:02}' in alt['removed'])
    by_role = {}
    for o in added:
        if not o.get('plate'):
            by_role[o['role']] = round(by_role.get(o['role'], 0)+length(o), 2)
    access = [dict(well=w['label'], **cartridge_access(v, alt, w, added+kept)) for w in ws] if access else None
    return dict(
        radius_m=r, status=ep.STATUS.get(r, 'STUDY'), alternate=True, collar_radius_m=round(alt['collar_radius_m'], 3),
        replaced=alt['removed'], rings_rerouted_m=alt['rings_rerouted'], added_members=len(added),
        clearances=dict(well_and_stack_m=round(well_margin, 3), posts_outside_port_m=round(port_margin, 3), posts_to_open_eyelids_m=round(leaf_margin, 3),
                        raceway_to_structure_m=round(race_margin, 3), shared_clearance_m=clr),
        continuity=dict(connected=len(roots) == 1, components=len(roots), branches_unanchored=unanchored, spoke_pattern_unrotated=spoke_azimuths_kept,
                        crown_bays_unchanged=True, members_deleted_without_replacement=orphans),
        lengths_m=dict(replaced=round(removed_len, 2), added_by_role=by_role, net_structure_added=round(sum(v_ for k, v_ in by_role.items() if k != 'raceway')-removed_len, 2)),
        mass=dict(known=False, canon_status='OPEN', note='member sizing and linear mass OPEN; no allocation inside the provisional 100 t Brow (FD-A02)'),
        cartridge_access=access,
        open=['FEA / load continuity rating', 'stiffness and modal', 'optical pointing stability', 'impact / debris open area', 'frame mass',
              'raceway routing protection and thermal', 'hatch, seal and latch', 'field of view'])


if __name__ == '__main__':
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from spec import load
    s, *_ = load(Path(__file__).resolve().parents[2])
    radii = [float(x) for x in sys.argv[1:]] or [16.0, 24.0]
    print(json.dumps([screen(s, r) for r in radii], indent=1))
