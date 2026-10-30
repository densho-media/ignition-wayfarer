"""FWD-V2 Eye geometry-release evidence (Eye 45 FD-A06 G: "3 view renders, section/cutaway, collisions, FOV, service path, mass sensitivity
and known/unknown machine manifest"; S&E 50 AG-A05 F, AG-A04 E/F). Pure, standard library only; reads the in-memory r4 / r16 / r24 variants
(eye_placement.variant) and the alternate truss (eye_truss_study). Nothing here changes a source value or releases a geometry.

- collisions(s, r): every clearance the release needs in one table (structure, eyelids through their whole travel, skin, layer, Crown, Lance,
  service path), each with its margin in metres (negative = clash) and the shared clearance it is held to.
- fov(s, r, pose): ray trace from the WORKING 2.5 m aperture of facet F1 through the well, the eyelids in the pose, the disruptor layer and its
  2.25 m port, the layer posts, the Dust Lance and every Crown carriage at full engagement. The result is the protected geometric field the
  structure leaves the facet (transmission per direction). It is not an EYE field of view (eye.field_of_view OPEN), and because the same rays run
  in reverse it is also the directional exposure of the window to a flux, not an impact rating (OPEN).
- service(s, r): the window-cartridge path out of the well wall, aft out of the truss and inward under the aft face to the body hull.
- crawler_approach(s, r): how close the DR-EVA-01 Brow crawler gets to that path on its DS-10 track (drone_fleet PROTOTYPE docks and rails).
- handoff(s, r): the owner's L2 cartridge hand-off (16:25: in-well carrier, aft-face station, towed sled, swap safe state), geometry only.
- mass(s, r): structure added per role and the linear masses at which the change would reach set shares of the provisional 100 t Brow. The
  linear masses themselves are OPEN; no mass is computed.
- manifest(s): every quantity with its value or known=false, its status and source (AG-A05: known/unknown machine manifest).

The four facets are equivalent under the 90 degree rotations of the layout (spokes at (k+1/2) 30 deg, Crown bays at k 30 deg, one well per
quadrant), so F1 stands for all four; the test checks F3 against it.

    python3 src/wayfarer/eye_release_evidence.py [radius ...]     # print the evidence as JSON
"""
import copy
import math
import eye_placement as ep
import eye_truss_study as ets
import forward_shield as fsh

THETA_STEP_DEG = 1.0               # FOV grid: off-boresight angle step
THETA_MAX_DEG = 60.0               # the WORKING well alone cuts off at 56.3 deg
PSI_STEP_DEG = 15.0                # FOV grid: azimuth round the boresight, from the outward radial toward +tangential
APERTURE_RINGS = ((0.0, 1), (1/3, 8), (2/3, 14), (1.0, 20))   # aperture sample rings (fraction of the radius, points)
BROW_ALLOCATION_T = 100.0          # provisional Brow allocation incl. the Crown (FD-A02 "provisional 100 t Brow"); the shares below are of it
SHARES = (0.01, 0.05, 0.10)
POSES = {'open': 0.0, 'jammed': 0.6, 'closed': 1.0}             # eyelid control (0 open/observe, 1 closed); EYE_F1_JAMMED holds F1 at 0.6


def _axes(w):
    d = math.hypot(w['y'], w['z']); ur = (w['y']/d, w['z']/d)
    return d, ur, (-ur[1], ur[0])


def leaf_frames(v, pose_values):
    """3D frames of every eyelid leaf in a pose: centre, axial normal X', radial Y', tangential Z' (the frame tilts onto the local cone)."""
    out = []
    for e in fsh.eye_shutters(v):
        u = pose_values.get(e['index'], 0.0); ur = (math.cos(e['azimuth']), math.sin(e['azimuth'])); ut = (-ur[1], ur[0]); tl = e['tilt']
        X = (math.cos(tl), math.sin(tl)*ur[0], math.sin(tl)*ur[1]); Y = (-math.sin(tl), math.cos(tl)*ur[0], math.cos(tl)*ur[1]); Z = (0.0, ut[0], ut[1])
        t = e['open_t']-e['travel']*u
        for leaf in e['leaves']:
            c = (e['x']+leaf['sign']*t*Z[0], e['y']+leaf['sign']*t*Z[1], e['z']+leaf['sign']*t*Z[2])
            out.append(dict(name=leaf['name'], well=e['index'], c=c, X=X, Y=Y, Z=Z, half=(e['thickness']/2, e['radial']/2, e['tangential']/2)))
    return out


def _dot(a, b):
    return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]


def _sub(a, b):
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])


def obstacles(v, alt, pose_values):
    """Everything a ray from a facet can meet ahead of it, in the variant's truss (production posts at r4, the alternate's posts at r16/r24)."""
    gone = set(alt['removed']) if alt else set()
    posts = [dict(name=q['name'], x0=q['x0'], x1=q['x1'], y=q['a'][1], z=q['a'][2], r=q['radius']) for q in fsh.disruptor_posts(v) if q['name'] not in gone]
    if alt:
        posts += [dict(name=o['name'], x0=min(o['pts'][0][0], o['pts'][1][0]), x1=max(o['pts'][0][0], o['pts'][1][0]), y=o['pts'][0][1], z=o['pts'][0][2], r=o['radius'])
                  for o in alt['members'] if o['role'] == 'post']
    c = fsh.crown(v); car = c['carriage']; stroke = fsh.crown_stroke_m(v)
    boxes = [dict(name=f"Crown_Bay_{b['index']:02}", az=b['azimuth'], x=(c['carriage_x']-car['axial']/2+stroke, fsh.crown_muzzle_x(v)+stroke),
                  rad=(c['stowed_r']-car['radial']/2, c['stowed_r']+car['radial']/2), tan=car['tangential']/2) for b in c['bays']]
    layers = fsh.disruptor_layers(v)
    return dict(posts=posts, leaves=leaf_frames(v, pose_values), crown=boxes, layers=layers,
                ports=[[(q['y'], q['z'], q['radius']) for q in fsh.eye_ports(v, layer)] for layer in layers],
                lance_hole=[fsh.lance_hole_radius(v, layer) for layer in layers])


def _layer_t(v, A, D, offset, t_hi):
    """Ray parameter where the ray meets the conical surface face_x(r) + offset (bisection; the ray rises faster than the 4.6 deg cone below 80 deg)."""
    f = lambda t: A[0]+t*D[0]-fsh.face_x_at(v, math.hypot(A[1]+t*D[1], A[2]+t*D[2]))-offset
    lo, hi = 0.0, t_hi
    if f(hi) < 0:
        return None
    for _ in range(40):
        mid = (lo+hi)/2
        lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
    return hi


def trace(v, w, A, D, obs):
    """First obstacle a ray A + t D meets ahead of facet w (None = clear to space). Window cartridge: transparent, ignored."""
    st = fsh.stations(v); rw = w['radius']; dyz = (D[1], D[2]); s2 = dyz[0]**2+dyz[1]**2
    # well wall: the cylinder exists from the facet face to the local skin face
    if s2 > 1e-12:
        py, pz = A[1]-w['y'], A[2]-w['z']; b = py*dyz[0]+pz*dyz[1]; cc = py*py+pz*pz-rw*rw
        t = (-b+math.sqrt(max(b*b-s2*cc, 0.0)))/s2; x = A[0]+t*D[0]
        if x < fsh.face_x_at(v, math.hypot(A[1]+t*D[1], A[2]+t*D[2])):
            return 'well_wall'
    # eyelid leaves (every well's), both faces of each slab
    for lf in obs['leaves']:
        dn = _dot(D, lf['X'])
        if abs(dn) < 1e-12:
            continue
        for sg in (-1, 1):
            t = _dot(_sub((lf['c'][0]+sg*lf['half'][0]*lf['X'][0], lf['c'][1]+sg*lf['half'][0]*lf['X'][1], lf['c'][2]+sg*lf['half'][0]*lf['X'][2]), A), lf['X'])/dn
            if t > 0:
                p = _sub((A[0]+t*D[0], A[1]+t*D[1], A[2]+t*D[2]), lf['c'])
                if abs(_dot(p, lf['Y'])) <= lf['half'][1]+1e-9 and abs(_dot(p, lf['Z'])) <= lf['half'][2]+1e-9:   # closed leaves butt on the axis
                    return 'eyelid'
    # posts (cylinders along +X between the face and the layer)
    if s2 > 1e-12:
        for q in obs['posts']:
            py, pz = A[1]-q['y'], A[2]-q['z']; b = py*dyz[0]+pz*dyz[1]; cc = py*py+pz*pz-q['r']**2; disc = b*b-s2*cc
            if disc < 0:
                continue
            t0, t1 = (-b-math.sqrt(disc))/s2, (-b+math.sqrt(disc))/s2
            if t1 < 0:
                continue
            xa, xb = A[0]+max(t0, 0)*D[0], A[0]+t1*D[0]
            if xa <= q['x1'] and xb >= q['x0']:
                return 'layer_post'
    # disruptor layers: aft and front faces must lie inside a port (or the Lance hole, where the Lance decides)
    t_far = (st['lance_tip']+60.0-A[0])/max(D[0], 1e-6)
    for layer, ports, hole in zip(obs['layers'], obs['ports'], obs['lance_hole']):
        for off in (layer['standoff'], layer['standoff']+layer['thickness']):
            t = _layer_t(v, A, D, off, t_far)
            if t is None:
                return 'disruptor_layer'
            y, z = A[1]+t*D[1], A[2]+t*D[2]
            if not (any(math.hypot(y-py, z-pz) <= pr for py, pz, pr in ports) or math.hypot(y, z) <= hole):
                return 'disruptor_layer'
    # Dust Lance (cone and tip cartridge ahead of the face)
    if D[0] > 1e-6:
        ta, tb = (st['face']-A[0])/D[0], (st['lance_tip']-A[0])/D[0]
        for i in range(49):
            t = ta+(tb-ta)*i/48
            if t > 0 and math.hypot(A[1]+t*D[1], A[2]+t*D[2]) <= fsh.lance_radius_at(v, A[0]+t*D[0]):
                return 'dust_lance'
    # Crown carriages at full engagement (worst case: all twelve bays engaged), slab test in each bay frame
    for b in obs['crown']:
        ca, sa = math.cos(b['az']), math.sin(b['az'])
        o = (A[0], A[1]*ca+A[2]*sa, -A[1]*sa+A[2]*ca); d = (D[0], D[1]*ca+D[2]*sa, -D[1]*sa+D[2]*ca)
        lo, hi = 0.0, math.inf
        for k, (a0, a1) in enumerate((b['x'], b['rad'], (-b['tan'], b['tan']))):
            if abs(d[k]) < 1e-12:
                if not a0 <= o[k] <= a1:
                    lo, hi = 1, 0
                    break
                continue
            t0, t1 = sorted(((a0-o[k])/d[k], (a1-o[k])/d[k])); lo, hi = max(lo, t0), min(hi, t1)
        if lo <= hi:
            return 'crown_engaged'
    return None


def aperture_points(v, w):
    ra = v['eye']['aperture']['value']/2; _, ur, ut = _axes(w); out = []
    for f, n in APERTURE_RINGS:
        for i in range(n):
            a = 2*math.pi*i/n; u, t = f*ra*math.cos(a), f*ra*math.sin(a)
            out.append((w['x0'], w['y']+u*ur[0]+t*ut[0], w['z']+u*ur[1]+t*ut[1]))
    return out


def fov(s, r, pose='open', facet=1, theta_step=THETA_STEP_DEG, psi_step=PSI_STEP_DEG):
    """Transmission T(theta, psi) of facet `facet` (fraction of aperture samples whose ray reaches space) and the angles that summarise it."""
    v = ep.variant(s, r); alt = ets.alternate(v) if not all(fsh.in_hub(v, x) for x in fsh.wells(v)) else None
    w = fsh.wells(v)[facet-1]; _, ur, ut = _axes(w); obs = obstacles(v, alt, {facet: POSES[pose]}); pts = aperture_points(v, w)
    thetas = [i*theta_step for i in range(int(THETA_MAX_DEG/theta_step)+1)]; psis = [i*psi_step for i in range(int(360/psi_step))]
    grid, blockers = [], {}
    for ps in psis:
        row = []
        for th in thetas:
            if len(row) >= 3 and row[-1] == row[-2] == row[-3] == 0:      # dark three steps running: the rest of the row is dark
                row.append(0.0)
                continue
            t, p = math.radians(th), math.radians(ps)
            D = (math.cos(t), math.sin(t)*(math.cos(p)*ur[0]+math.sin(p)*ut[0]), math.sin(t)*(math.cos(p)*ur[1]+math.sin(p)*ut[1]))
            hits = [trace(v, w, A, D, obs) for A in pts]
            for h in hits:
                if h:
                    blockers[h] = blockers.get(h, 0)+1
            row.append(sum(h is None for h in hits)/len(hits))
        grid.append(row)

    def first(row, test):
        return next((thetas[i] for i, T in enumerate(row) if test(T)), None)
    per_psi = [dict(psi_deg=ps, full_deg=(first(row, lambda T: T < 1) or thetas[-1]+theta_step)-theta_step if row[0] == 1 else None,
                    half_deg=first(row, lambda T: T < .5), zero_deg=first(row, lambda T: T == 0)) for ps, row in zip(psis, grid)]
    dth, dps = math.radians(theta_step), math.radians(psi_step)
    omega = sum(T*math.sin(math.radians(th))*dth*dps for row in grid for th, T in zip(thetas, row))
    full = [x['full_deg'] for x in per_psi if x['full_deg'] is not None]
    return dict(radius_m=r, pose=pose, facet=w['label'], on_axis_transmission=round(grid[0][0], 3),
                unvignetted_half_angle_deg=min(full) if full and len(full) == len(per_psi) else None,
                half_transmission_deg=dict(min=min((x['half_deg'] for x in per_psi if x['half_deg'] is not None), default=None),
                                           max=max((x['half_deg'] for x in per_psi if x['half_deg'] is not None), default=None)),
                cutoff_deg=dict(min=min((x['zero_deg'] for x in per_psi if x['zero_deg'] is not None), default=None),
                                max=max((x['zero_deg'] for x in per_psi if x['zero_deg'] is not None), default=None)),
                clear_solid_angle_sr=round(omega, 4), blocked_ray_share={k: round(n/sum(blockers.values()), 3) for k, n in sorted(blockers.items())} if blockers else {},
                per_psi=per_psi, thetas_deg=thetas, psis_deg=psis, transmission=[[round(T, 3) for T in row] for row in grid],
                well_only_deg=[round(x, 2) for x in ep.well_field_deg(v)],
                status='GEOMETRIC protected field only; EYE field of view OPEN (eye.field_of_view); exposure, not an impact rating (OPEN)')


# ---------- collisions -------------------------------------------------------------------------------------------------

def _leaf_skin_gap(v, lf):
    """Smallest gap between a leaf's aft face and the skin face under it (sampled over the leaf)."""
    worst = math.inf
    for i in range(11):
        for k in range(11):
            a, b = -lf['half'][1]+2*lf['half'][1]*i/10, -lf['half'][2]+2*lf['half'][2]*k/10
            p = tuple(lf['c'][j]-lf['half'][0]*lf['X'][j]+a*lf['Y'][j]+b*lf['Z'][j] for j in range(3))
            worst = min(worst, p[0]-fsh.face_x_at(v, math.hypot(p[1], p[2])))
    return worst


def _leaf_layer_gap(v, lf):
    worst = math.inf
    for i in range(11):
        for k in range(11):
            a, b = -lf['half'][1]+2*lf['half'][1]*i/10, -lf['half'][2]+2*lf['half'][2]*k/10
            p = tuple(lf['c'][j]+lf['half'][0]*lf['X'][j]+a*lf['Y'][j]+b*lf['Z'][j] for j in range(3))
            worst = min(worst, min(fsh.layer_x(v, layer, math.hypot(p[1], p[2]))[0] for layer in fsh.disruptor_layers(v))-p[0])
    return worst


def _leaf_point_gap(lf, y, z):
    """In-plane (YZ projection) distance from a vertical post axis to a leaf rectangle (0 inside)."""
    p = (0.0, y-lf['c'][1], z-lf['c'][2]); a = abs(p[1]*lf['Y'][1]+p[2]*lf['Y'][2])/max(math.hypot(lf['Y'][1], lf['Y'][2]), 1e-9)
    b = abs(_dot(p, lf['Z'])); ha = lf['half'][1]*math.hypot(lf['Y'][1], lf['Y'][2])
    return math.hypot(max(a-ha, 0.0), max(b-lf['half'][2], 0.0))


def collisions(s, r):
    """All release clearances for one placement. Each row: margin (m), the clearance it is held to, ok."""
    v = ep.variant(s, r); clr = fsh.clearance(v); scr = ep.screen(s, r); outer = not all(fsh.in_hub(v, x) for x in fsh.wells(v))
    alt = ets.alternate(v) if outer else None; ts = ets.screen(s, r) if outer else None; rows = []

    def row(name, margin, need=clr, note=''):
        rows.append(dict(item=name, margin_m=round(margin, 3), required_m=need, ok=margin >= need-1e-9, note=note))
    st = scr['structure']
    if outer:
        c = ts['clearances']
        row('wells and facet stacks to every truss member (alternate)', c['well_and_stack_m'])
        row('relocated layer posts outside the 2.25 m outer port', c['posts_outside_port_m'])
        row('raceways to the structure (aft face)', c['raceway_to_structure_m'])
        row('continuity: one connected structure, no member deleted without replacement', 0.0 if ts['continuity']['connected'] and not ts['continuity']['members_deleted_without_replacement'] else -1.0, 0.0)
    else:
        row('wells to the nearest truss spoke (production)', st['spoke_m']); row('wells to the truss rings (production)', st['truss_ring_m'])
        row('wells to the layer posts (production)', st['layer_post_m'])
    row('well to the Dust Lance base', st['lance_m']); row('well to the Crown housing', st['crown_housing_m']); row('well to the shield rim', st['rim_m'])
    row('facet stack inside skin + truss depth', st['skin_plus_truss_depth_m']-st['facet_stack_m'], 0.0)
    # The boresight is held to the truss as it would be built: an outer well comes with the alternate truss (forward_shield.truss is
    # layout-aware since the Eye layout switch), so the line of sight is taken on a copy with that layout selected.
    lv = v
    if outer:
        lv = copy.deepcopy(v); lv['forward_defense']['eye_layout'] = dict(lv['forward_defense'].get('eye_layout') or {}, selected=f'r{r:g}',
                                                                          radii_m={f'r{r:g}': float(r)}, status='STUDY')
    for los in fsh.eye_line_of_sight(lv)[:1]:
        m = {k: x for k, x in los['margins'].items() if not k.startswith(('posts', 'struts')) and not (outer and k == 'hub_ring')}   # outer wells lie outside the hub ring
        row('boresight cylinder to the ports, Lance hole, Lance and Crown', min(m.values()), 0.0, 'eye_line_of_sight')
    # eyelids through their whole travel (21 steps): skin, layer, posts, the other wells, the other leaves
    posts = obstacles(v, alt, {})['posts']
    skin = layer = post = other = math.inf
    for k in range(21):
        u = k/20; lfs = leaf_frames(v, {j: u for j in range(1, 5)})
        for lf in lfs:
            skin = min(skin, _leaf_skin_gap(v, lf)); layer = min(layer, _leaf_layer_gap(v, lf))
            post = min(post, min(_leaf_point_gap(lf, q['y'], q['z'])-q['r'] for q in posts))
            other = min(other, min(_leaf_point_gap(lf, w['y'], w['z'])-w['radius'] for w in fsh.wells(v) if w['index'] != lf['well']))
    gap = v['forward_shield']['prototype']['eye_shutter_gap_m']
    row('eyelid leaves to the skin face, whole travel', skin, gap, f'held to the PROTOTYPE eyelid gap {gap} m (eye_shutter_gap_m)')
    row('eyelid leaves to the disruptor layer, whole travel', layer, 0.0)
    row('eyelid leaves to the layer posts, whole travel', post)
    row('eyelid leaves to the other wells, whole travel', other)
    sv = service(s, r)
    if sv:
        row('window cartridge out of the well wall and aft out of the truss', sv['well_exit']['margin_m'])
        row('window cartridge under the aft face to the body hull', sv['aft_leg']['margin_m'])
    return dict(radius_m=r, status=ep.STATUS.get(r, 'STUDY'), shared_clearance_m=clr, rows=rows, all_ok=all(x['ok'] for x in rows),
                note='Margins against PROTOTYPE geometry; a pass is a layout finding, not a structural, optical or impact verification (AG-A05 G).')


# ---------- service path -------------------------------------------------------------------------------------------------

def service(s, r):
    """FD-A02 / AG-A04 window-cartridge path per facet (crawler first, FLIGHT_EVA HOLD): out of the well wall at the window station, aft out of the
    truss, then radially inward under the aft face, aft of the raceway layer, to the body hull. The sector keels and ties are not 90 degree
    symmetric, so every facet is checked. None at r4 (served from inside the hub)."""
    v = ep.variant(s, r)
    if all(fsh.in_hub(v, x) for x in fsh.wells(v)):
        return None
    alt = ets.alternate(v); clr = fsh.clearance(v); kept = ets._kept(v, alt); R = fsh.body_radius(v)
    obstacles_ = [o for o in alt['members'] if o['role'] in ('raceway', 'sector_tie')]+[o for o in kept if o['name'].startswith(('Shield_Sector_Tie', 'Shield_Mount'))]
    obstacles_ += [dict(name=k['name'], pts=[k['a'], k['b']], radius=k['radius']) for k in fsh.sector_keels(v)]
    facets = []
    for w in [x for x in fsh.wells(v) if not fsh.in_hub(v, x)]:
        acc = ets.cartridge_access(v, alt, w, alt['members']+kept)
        win = next(e for e in fsh.eye_shutters(v) if e['index'] == w['index'])['window']; wr, th = win['radius'], win['thickness']
        # aft leg: the cartridge disc (face parallel to the cone) one raceway layer plus clearances aft of the truss aft face, until its rim is
        # one clearance off the body hull
        (_, y1, z1) = acc['path'][-1]; rho1 = math.hypot(y1, z1); u = (y1/rho1, z1/rho1)
        depth = 2*clr+ets.RACEWAY_SIDE_M+ets.RACEWAY_SAG_M+th/2
        rho_end = R+clr+wr; n = max(2, int((rho1-rho_end)/0.25))
        path = [(fsh.truss_aft_at(v, rho)-depth, rho*u[0], rho*u[1]) for rho in (rho1-(rho1-rho_end)*i/n for i in range(n+1))]
        worst, who = math.inf, None
        for o in obstacles_:
            for a0, b0 in ets._segs(o):
                for c0, c1 in zip(path, path[1:]):
                    q = ets._clip_yz(a0, b0, min(c0[0], c1[0])-th/2, max(c0[0], c1[0])+th/2)
                    if q:
                        m = ets._d2((c0[1], c0[2]), (c1[1], c1[2]), q[0], q[1])-wr-o['radius']
                        if m < worst:
                            worst, who = m, o['name']
        facets.append(dict(facet=w['label'], hatch_phi_deg=acc['best_phi_deg'], slide_m=acc['slide_m'], exit_margin_m=acc['margin_m'],
                           clear_directions_deg=acc['clear_directions_deg'], aft_leg_from_radius_m=round(rho1, 3), aft_leg_to_radius_m=round(rho_end, 3),
                           aft_leg_length_m=round(rho1-rho_end, 3), aft_leg_margin_m=round(worst, 3) if worst < math.inf else None, aft_leg_nearest=who,
                           path=acc['path']+path, aft_path=path))
    return dict(radius_m=r, facets=facets, aft_of_truss_m=round(depth, 3), cartridge=dict(radius_m=wr, thickness_m=th),
                well_exit=dict(margin_m=min(f['exit_margin_m'] for f in facets)),
                aft_leg=dict(margin_m=min(f['aft_leg_margin_m'] for f in facets if f['aft_leg_margin_m'] is not None)),
                poses={'open': 'cartridge path independent of the eyelids (well wall at the window station, under the face)',
                       'closed': 'recommended service pose: eyelids closed over the empty window station while the cartridge is out',
                       'jammed': 'service unaffected; the jammed leaf stays at 0.6 (EYE_F1_JAMMED) and the field loss is in fov(..., "jammed")'},
                open=['hatch, seal and latch design', 'crawler envelope and grip', 'cartridge mass', 'safe-mode interlocks (FD-A02)', 'FLIGHT_EVA HOLD'])


# ---------- crawler approach -----------------------------------------------------------------------------------------------

def _rail_axis(rails):
    """Centreline of a two-rail track (the mean of its two rails, point by point), refined to about 0.1 m steps."""
    pts = [tuple((a+b)/2 for a, b in zip(p, q)) for p, q in zip(rails[0]['points'], rails[1]['points'])]
    out = []
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.dist(a, b)/0.1))
        out += [tuple(a[i]+(b[i]-a[i])*k/n for i in range(3)) for k in range(n)]
    return out+[pts[-1]]


def crawler_approach(s, r):
    """AG-A04 / DGT-006: how far the DR-EVA-01 Brow crawler (S&E 51!A5, "0.40-0.60 m class") on its DS-10 track (drone_fleet, PROTOTYPE docks
    and rails aft of the truss along the spokes) gets to each facet's window-cartridge aft leg. Per facet: the nearest track, the smallest
    centreline gap between the track and the cartridge path and where it falls, the rail travel from the dock to that point, and the gap
    left between the crawler's upper envelope and the cartridge rim. A positive rim gap means the crawler cannot touch the cartridge from its
    track: a cross track, an arm or a carrier is needed (owner question 2026-10-13T16:25). The DS-15 arm base distance is reported; its reach is
    OPEN. None at r4 (cartridge served from inside the hub)."""
    import drone_fleet as df
    v = ep.variant(s, r); sv = service(s, r)
    if sv is None:
        return None
    recs = {q['id']: q for q in df.stations(v)}; ds = recs['DS-10']; cls = df.classes(v)[ds['cls']]; env = cls['envelope_m'][1]
    wr = sv['cartridge']['radius_m']
    tracks = []
    for d in ds['docks']:
        k = d['name'].rsplit('_', 1)[1]
        tracks.append(dict(dock=d['name'], centre=d['world_centre'], axis=_rail_axis([q for q in ds['rails'] if q['name'].startswith(f"Drone_Rail_DS-10_{k}_")])))
    arm = recs['DS-15']['docks'][0]['a']; rr = v['survival']['crawler_rail_radius_m']
    hardware = [(p, rr) for q in ds['rails'] for p in _rail_axis([q, q])]+[(d['world_centre'], math.hypot(*d['size'])/2) for d in ds['docks']]
    facets = []
    for f in sv['facets']:
        P = f['aft_path']; best = None
        for t in tracks:
            for i, q in enumerate(t['axis']):
                for c in P:
                    g = math.dist(q, c)
                    if best is None or g < best[0]:
                        best = (g, t, i, q, c)
        g, t, i, q, c = best
        rho_q = math.hypot(q[1], q[2]); rho_dock = math.hypot(t['centre'][1], t['centre'][2])
        az = lambda p: round(math.degrees(math.atan2(p[2], p[1])) % 360, 1)
        facets.append(dict(facet=f['facet'], dock=t['dock'], dock_azimuth_deg=az(t['centre']), cartridge_azimuth_deg=az(P[0]),
                           centreline_gap_m=round(g, 3), at_rail_radius_m=round(rho_q, 3), at_cartridge_radius_m=round(math.hypot(c[1], c[2]), 3),
                           rail_travel_from_dock_m=round(abs(rho_q-rho_dock), 3), rim_gap_after_crawler_m=round(g-wr-env/2, 3),
                           reachable_from_track=g-wr-env/2 <= 0.0,
                           arm_base_to_aft_leg_m=round(min(math.dist(arm, p) for p in P), 3),
                           cartridge_clear_of_ds10_m=round(min(math.dist(h, p)-wr-hr for h, hr in hardware for p in P), 3)))
    return dict(radius_m=r, crawler=dict(cls=cls['id'], envelope_upper_m=env, status='PROPOSED / NOT SIZED (51!A5)', mass='OPEN', payload='OPEN'),
                tracks='DS-10 docks and rails, drone_fleet PROTOTYPE (52!A11 UNPLACED / CAD OPEN)', facets=facets,
                all_reachable=all(x['reachable_from_track'] for x in facets),
                open=['cartridge carrier, aft-face station and sled sizing, stroke drive and latches (15!A189:A191, PROTOTYPE geometry only)', 'crawler payload and grip', 'DS-15 arm reach (51!G10)'])


# ---------- cartridge hand-off (owner 2026-10-13T16:25: S&E 15!A189:A192 OWN-EYE-H1..H4, Eye 45 FD-B11) -----------------------

SLED_FRAME_M = 0.10       # PROTOTYPE sled frame round the cartridge rim (captured edge, guides), each side
SLED_DEPTH_M = 0.15       # PROTOTYPE sled frame depth across the disc (aft of the cartridge face)


SAFE_STATE = ['facet eyelids CLOSED (the outer debris port stays open)', 'adjacent Crown bays DISABLED and LOCKED', 'verified low-hazard state',
              'robot positive support', 'thermal and electrical isolation', 'no swap during forward dust hazard (FD-B11)', 'FLIGHT_EVA HOLD']


def support_sequence(hub=False):
    """Exchange steps with the mechanisms holding the cartridge at each (OWN-EYE-H1: positive support throughout, hard stops, secondary
    retainer, position feedback). A transfer step lists both holders: the giver releases only after the taker reports latched."""
    if hub:
        return [dict(step='window station latched', holders=['window station']),
                dict(step='hub carrier engages, station releases', holders=['window station', 'hub carrier']),
                dict(step='carrier stroke into the hub', holders=['hub carrier']),
                dict(step='bench clamp engages, carrier releases', holders=['hub carrier', 'bench clamp'])]
    return [dict(step='window station latched (eyelids closed, Crown bays locked)', holders=['window station']),
            dict(step='well-wall carrier engages, station releases', holders=['window station', 'well-wall carrier']),
            dict(step='carrier stroke to the truss aft face (hard stops, secondary retainer)', holders=['well-wall carrier']),
            dict(step='sled captures at the aft-face station, carrier releases', holders=['well-wall carrier', 'raceway sled']),
            dict(step='sled towed / guided inboard on the captured raceway', holders=['raceway sled']),
            dict(step='service-station clamp engages, sled releases', holders=['raceway sled', 'service station'])]


def positive_support(seq):
    """Every step holds the cartridge, and every change of holder overlaps (the previous holder is still present)."""
    ok = all(st['holders'] for st in seq) and all(set(a['holders']) & set(b['holders']) for a, b in zip(seq, seq[1:]))
    return dict(result='PASS' if ok else 'FAIL', rule='no step without a holder; each hand-over shares a holder with the step before')


def _unit(a):
    n = math.sqrt(_dot(a, a)); return tuple(x/n for x in a)


def c_env(v):
    import drone_fleet as df
    recs = {q['id']: q for q in df.stations(v)}; return df.classes(v)[recs['DS-10']['cls']]['envelope_m'][1]


def _tracks(v):
    import drone_fleet as df
    ds = next(q for q in df.stations(v) if q['id'] == 'DS-10'); out = []
    for d in ds['docks']:
        k = d['name'].rsplit('_', 1)[1]
        out.append(dict(dock=d['name'], axis=_rail_axis([q for q in ds['rails'] if q['name'].startswith(f"Drone_Rail_DS-10_{k}_")])))
    return out


def handoff(s, r):
    """L2 kinematic concept the owner authorized (OWN-EYE-H1..H4, FD-B11), geometry only: (1) a fixed, positively captured linear carrier inside
    the well-wall hatch takes the cartridge from the window station out to the truss aft face (H1, the 7.15 m slide); (2) the hand-off station
    sits at the truss aft face directly behind the well (H2); (3) a captured sled on a supported raceway carries it the aft leg inward to the
    hull-side service station, and a crawler only tows or guides the sled (H3: never a suspended carrier for the 2.6 m disc); (4) the swap
    needs the facet's eyelids closed, the Crown sectors beside the well disabled and locked, a verified low-hazard state, positive robot
    support and thermal/electrical isolation; the outer debris port stays open, so a closed eyelid alone is not a safe state (H4, 16:25 d).
    The sled envelope (cartridge plus SLED_FRAME_M) is held to the aft-leg obstacles; the tow gap is how far the nearest DS-10 crawler track
    lies from the sled edge. Mass, payload, tow load, latch and safe state stay OPEN. None at r4 (served from inside the hub)."""
    v = ep.variant(s, r); n = fsh.prototype(v)['crown_bay_count']
    bays_at = lambda az: sorted(k+1 for k in range(n) if abs((k*360/n-az+180) % 360-180) <= 360/n)
    sv = service(s, r)
    if sv is None:     # r4: the wells sit in the body hub; the owner keeps that local access as a candidate (15!I190, H2)
        facets = [dict(facet=w['label'], azimuth_deg=round(math.degrees(math.atan2(w['z'], w['y'])) % 360, 1),
                       crown_bays_locked=bays_at(math.degrees(math.atan2(w['z'], w['y'])) % 360)) for w in fsh.wells(v)]
        return dict(radius_m=r, mode='hub interior (local candidate, 15!I190)', facets=facets, support_sequence=support_sequence(hub=True),
                    positive_support=positive_support(support_sequence(hub=True)), safe_state=SAFE_STATE,
                    open=['hub-interior carrier, bench and hatch: not modelled (no hub service room built)', 'cartridge mass and payload',
                          'flight-time safe state (15!A192 not released)'])
    ca = {f['facet']: f for f in crawler_approach(s, r)['facets']}; wr = sv['cartridge']['radius_m']
    tracks = _tracks(v)
    facets = []
    for f in sv['facets']:
        P = f['aft_path']; az = math.degrees(math.atan2(P[0][2], P[0][1])) % 360
        c = ca[f['facet']]
        carrier_dir = _unit(_sub(f['path'][len(f['path'])-len(P)], f['path'][len(f['path'])-len(P)-1])) if len(f['path']) > len(P) else None
        sled_dir = _unit(_sub(P[1], P[0]))
        bends = [round(math.degrees(math.acos(max(-1.0, min(1.0, _dot(_unit(_sub(b, a)), _unit(_sub(c_, b))))))), 2) for a, b, c_ in zip(P, P[1:], P[2:])]
        gaps = sorted((min(math.dist(q, p) for q in t['axis'] for p in P[::2])-wr-SLED_FRAME_M-c_env(v)/2, t['dock']) for t in tracks)
        facets.append(dict(facet=f['facet'], carrier_stroke_m=f['slide_m'], carrier_exit_margin_m=f['exit_margin_m'],
                           handoff_station=[round(x, 3) for x in P[0]], service_station=[round(x, 3) for x in P[-1]],
                           handoff_turn_deg=round(math.degrees(math.acos(max(-1.0, min(1.0, _dot(carrier_dir, sled_dir))))), 1) if carrier_dir else None,
                           raceway_max_bend_deg=max(bends) if bends else 0.0,
                           sled_run_m=f['aft_leg_length_m'], sled_margin_m=round(f['aft_leg_margin_m']-SLED_FRAME_M, 3), sled_nearest=f['aft_leg_nearest'],
                           tow_track=c['dock'], tow_gap_to_sled_edge_m=round(c['rim_gap_after_crawler_m']-SLED_FRAME_M, 3),
                           tow_reach='tow arm or lanyard across the gap (OPEN)' if c['rim_gap_after_crawler_m']-SLED_FRAME_M > 0 else 'track touches the sled',
                           recovery_track=gaps[1][1], recovery_gap_to_sled_edge_m=round(gaps[1][0], 3),
                           recovery=('neighbouring track cannot reach: a second crawler on the same track (pushing or coupling the failed one) or a cross '
                                     'track is needed (15!A191 one or two crawlers, OPEN); the sled stays captured on the raceway meanwhile')
                                    if gaps[1][0] > 0 else 'neighbouring DS-10 crawler reaches the sled edge',
                           crown_bays_locked=bays_at(az), azimuth_deg=round(az, 1)))
    seq = support_sequence(hub=False)
    return dict(radius_m=r, mode='well-wall carrier -> truss aft-face station -> captured raceway sled (15!A189:A191)',
                sled=dict(radius_m=round(wr+SLED_FRAME_M, 3), depth_m=SLED_DEPTH_M, frame_m=SLED_FRAME_M, status='PROTOTYPE'),
                facets=facets, carrier_min_margin_m=min(f['carrier_exit_margin_m'] for f in facets),
                sled_min_margin_m=min(f['sled_margin_m'] for f in facets),
                support_sequence=seq, positive_support=positive_support(seq),
                stranded=[dict(where='carrier mid-stroke', state='cartridge retained in the well-wall carrier, eyelids closed over the station', recovery='manual carrier drive / backdrive (OPEN, 15!H189)'),
                          dict(where='hand-off station', state='both carrier and sled latched until the transfer completes', recovery='either holder alone keeps support'),
                          dict(where='sled mid-raceway (tow crawler fails)', state='sled captured on the raceway, braked (OPEN)',
                               recovery='per facet recovery_gap: the neighbouring DS-10 track is metres away, so a same-track second crawler or a cross track; FLIGHT_EVA HOLD')],
                anchor_reactions='F = m_cartridge+sled x a_tow and the 1.5 g locked-drive case: masses OPEN, so no load (15!G191)',
                safe_state=SAFE_STATE,
                open=['cartridge mass and payload', 'sled latch, hard stops, secondary retainer, position feedback, manual recovery', 'raceway support and tow load',
                      'one or two crawlers (15!A191)', 'flight-time safe state (15!A192 not released)'])


# ---------- mass sensitivity ---------------------------------------------------------------------------------------------

def mass(s, r):
    """Structure lengths the alternate adds (lengths only: linear masses OPEN) and the break-even linear masses at which the net structure change
    would equal 1 / 5 / 10 % of the provisional 100 t Brow allocation."""
    v = ep.variant(s, r)
    if all(fsh.in_hub(v, x) for x in fsh.wells(v)):
        return dict(radius_m=r, alternate=False, note='production truss, no change')
    ts = ets.screen(s, r); L = ts['lengths_m']; net = L['net_structure_added']; race = L['added_by_role'].get('raceway', 0.0)
    plate_area = 4*math.pi*(fsh.prototype(v)['well_diameter_m']/2)**2
    return dict(radius_m=r, alternate=True, replaced_m=L['replaced'], added_by_role_m=L['added_by_role'], net_structure_m=net, raceway_m=race,
                facet_plates=dict(count=4, area_m2=round(plate_area, 2)),
                formula='dM = lambda_truss * net_structure_m + lambda_raceway * raceway_m + sigma_plate * plate_area_m2 (all three OPEN)',
                break_even_lambda_truss_kg_per_m={f'{int(f*100)}% of {BROW_ALLOCATION_T:g} t': round(f*BROW_ALLOCATION_T*1000/net, 2) for f in SHARES},
                known=False, canon_status='OPEN', note='needs the owner linear mass per member class; no mass is invented (FD-A02, AG-A05 D)')


# ---------- manifest -----------------------------------------------------------------------------------------------------

def _q(key, value=None, unit='', status='OPEN', source='', known=None):
    k = value is not None if known is None else known
    return dict(key=key, known=k, **({'value': value} if k else {}), unit=unit, status=status, source=source)


def manifest(s, evidence=None):
    """AG-A05 known/unknown machine manifest for the release request: each quantity with value or known=false, status and source."""
    e = s['eye']; wl = s['forward_defense']['eye_wells']; port = wl['outer_port']; out = [
        _q('eye.aperture', e['aperture']['value'], 'm', e['aperture']['canon_status'], e['aperture']['source_ref']),
        _q('forward_defense.eye_wells.diameter_m', wl['diameter_m'], 'm', wl.get('canon_status', 'WORKING'), wl.get('source_ref', '')),
        _q('forward_defense.eye_wells.centre_radius_m (production)', wl['centre_radius_m'], 'm', 'WORKING', '14!A28'),
        _q('forward_defense.eye_wells.outer_port.radius_m', port['radius_m'], 'm', port['canon_status'], port.get('evidence_ref', '')),
        _q('eye.array_baseline (r4 calibration only)', e['array_baseline']['value'], 'm', e['array_baseline']['canon_status'], e['array_baseline']['source_ref']),
        _q('eye.coherent_baseline', status='OPEN', source='FD-A03', known=False),
        _q('eye.field_of_view', status='OPEN', source='eye.field_of_view', known=False)]
    for r in (16.0, 24.0):
        b = fsh.eye_baselines(ep.variant(s, r))
        out += [_q(f'r{r:g}.geometric_opposite', b['geometric_opposite_m']['value'], 'm', 'DERIVED (STUDY placement)', 'FD-A03'),
                _q(f'r{r:g}.geometric_adjacent', round(b['geometric_adjacent_m']['value'], 3), 'm', 'DERIVED (STUDY placement)', 'FD-A03'),
                _q(f'r{r:g}.collar_radius', round(ets.collar_radius(ep.variant(s, r)), 3), 'm', 'PROTOTYPE', 'eye_truss_study.collar_radius')]
    for key in ('frame and truss linear mass', 'facet plate areal mass', 'raceway linear mass', 'FEA / load continuity rating', 'stiffness and modal',
                'optical pointing stability', 'hypervelocity impact rating of ports, eyelids and window (0.016c)', 'eyelid drive, latch, closing time, erosion life', 'eyelid lap-seam overlap, latch force and leakage (FD-B10: lap seam built, width PROTOTYPE)',
                'window cartridge material, thickness, mass', 'hatch, seal and latch', 'crawler payload and grip', 'cartridge carrier, aft-face station and sled sizing, stroke drive and latches (15!A189:A191, PROTOTYPE geometry only)', 'raceway thermal and protection'):
        out.append(_q(key, status='OPEN', source='FD-A01/A02/A04/A06, AG-A01/A02/A04', known=False))
    out.append(_q('crawler envelope (DR-EVA-01)', '0.40-0.60 m class', '', 'PROPOSED / NOT SIZED', 'S&E 51!G5'))
    if evidence:
        for r, ev in evidence.items():
            f = ev['fov']['open']
            out += [_q(f'r{r:g}.protected_field.unvignetted_half_angle', f['unvignetted_half_angle_deg'], 'deg', 'GEOMETRIC (not an EYE FOV)', 'eye_release_evidence.fov'),
                    _q(f'r{r:g}.protected_field.clear_solid_angle', f['clear_solid_angle_sr'], 'sr', 'GEOMETRIC', 'eye_release_evidence.fov'),
                    _q(f'r{r:g}.collisions.all_ok', ev['collisions']['all_ok'], '', 'PROTOTYPE layout check', 'eye_release_evidence.collisions')]
    return out


def evidence(s, radii=ep.RADII, poses=('open', 'jammed')):
    ev = {r: dict(collisions=collisions(s, r), fov={**{p: fov(s, r, p) for p in poses}, 'closed': fov(s, r, 'closed', theta_step=10.0, psi_step=90.0)},
                  service=service(s, r), crawler=crawler_approach(s, r), handoff=handoff(s, r), mass=mass(s, r)) for r in radii}
    return dict(contract='WF_EYE_RELEASE_EVIDENCE', version=1, radii=list(radii), evidence=ev, manifest=manifest(s, ev),
                boundary='STUDY in memory; r4 and B_array 8 m stay WORKING until the owner releases a tested geometry (FD-A06). Passing checks are not '
                         'ballistic, optical or flight certification (AG-A05 G); mouth eyelid animation is not orbital dust armour at 0.016c (FD-A06 F).')


if __name__ == '__main__':
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from spec import load
    s, *_ = load(Path(__file__).resolve().parents[2])
    radii = [float(x) for x in sys.argv[1:]] or list(ep.RADII)
    print(json.dumps(evidence(s, radii), indent=1, default=str))


# ---------- H02 service hardware (PROTOTYPE geometry for the built layout) ------------------------------------------------------

RAIL_OFFSET_M = 1.2       # PROTOTYPE: the sled's two captured rails, either side of the path inside the sled rim (tangential)
RAIL_RADIUS_M = 0.045
GUIDE_RADIUS_M = 0.05     # PROTOTYPE: the well-wall carrier's guide spine outside the hatch
GUIDE_START_M = 0.6       # the guide starts this far outside the hatch (the hatch and the in-well carrier stay unmodelled, OPEN)
STATION_SIZE_M = (0.30, 0.25)   # PROTOTYPE clamp frame section at the hand-off and the service station (axial, radial)


def service_hardware(s):
    """H02 (TODO; owner hand-off concept 15!A189:A191, Claude decision 2026-10-30 under the owner's delegation): per facet of the built
    outer layout, the well-wall carrier's guide outside the hatch, the truss aft-face hand-off station, the parked raceway sled, its two
    captured rails along the aft leg and the hull-side service station, as primitives in the ship frame. None at r4 (hub service).
    Every size is PROTOTYPE; support, mass, tow load, latches and the safe state stay OPEN (handoff)."""
    r = s['forward_defense']['eye_wells']['centre_radius_m']; sv = service(s, r)
    if sv is None:
        return []
    wr = sv['cartridge']['radius_m']; out = []
    for f in sv['facets']:
        tag = f"Eye_Service_F{f['facet'][1]}"; P = f['aft_path']; pre = f['path'][:len(f['path'])-len(P)+1]
        az = math.atan2(P[0][2], P[0][1]); t = (0.0, -math.sin(az), math.cos(az)); u = (0.0, math.cos(az), math.sin(az))
        a, b = pre[1], pre[-1]; d = _unit(_sub(b, a)); a = tuple(a[i]+d[i]*GUIDE_START_M for i in range(3))
        out.append(dict(name=f'{tag}_Carrier_Guide', role='carrier_guide', kind='line', pts=[a]+list(pre[2:]), radius=GUIDE_RADIUS_M))
        for side, sg in (('A', 1), ('B', -1)):
            out.append(dict(name=f'{tag}_Sled_Rail_{side}', role='sled_rail', kind='line', radius=RAIL_RADIUS_M,
                            pts=[tuple(p[i]+sg*RAIL_OFFSET_M*t[i] for i in range(3)) for p in (P[0], P[-1])]))
        for name, p in (('Handoff_Station', P[0]), ('Service_Station', P[-1])):
            out.append(dict(name=f'{tag}_{name}', role=name.lower(), kind='frame', centre=p, radial=u, tangential=t,
                            half_span=RAIL_OFFSET_M+0.25, section=STATION_SIZE_M))
        out.append(dict(name=f'{tag}_Sled', role='sled', kind='disc', centre=P[0], radius=wr+SLED_FRAME_M, depth=SLED_DEPTH_M, inner=wr))
    return out
