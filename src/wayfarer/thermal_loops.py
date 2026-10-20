"""AFT-010 heat-loop rejection screen (Q38). Pure standard library, no Blender and no module-level spec import; callers pass the spec mapping and
nothing here mutates it.

The three regimes are 40_THERMAL A60:A66: hot ~1800 K blade faces, warm ~450 K stationary casing/panel radiators, cold ~320 K ring surfaces. A gray
surface at Ts with emissivity eps and absorptance alpha = eps nets

    q = eps*SIGMA*Ts^4*F_space - alpha*sum(F_hot*eps_h*SIGMA*Th^4)

so a 450 K surface is net-heated once F_hot exceeds 0.0043 of F_space. The screen casts cosine-weighted rays from candidate zones at the live blade,
hull, ring and shield geometry and compares them with an exact contour-integral view factor. Everything is DIAGNOSTIC: the candidate zones are
PROTOTYPE, `thermal.loops.warm.area` and `.cold.area` stay OPEN, and `radiators.view_factor` is never written.

Assumptions: blades are thin planes with both faces emitting; the root band is treated as hot (its temperature map is OPEN); non-hot blockers (hull,
rings, shield) exchange net zero with the receiver (equal temperature, adiabatic), so emission into them is neither rejection nor gain; the open
rotor bay is filled at the hull radius_at; panels are receivers only; single bounce, gray, no sunlight, drive hot section or plume.
"""
import json
import math
import random
import sys
from pathlib import Path

import forward_shield
import habitat_ring
import hull_geometry
import layout
import thermal_budget
import thermal_geometry

SIGMA = thermal_budget.SIGMA
CASES = ('HIGH_POWER', 'BLADES_NOT_RADIATING')
PANEL_FAMILIES = ('BLADE_PLANE', 'BISECTOR')
OFFSET = 1e-6
TMIN = 1e-9
INF = math.inf
REPORT_PATH = 'references/p1_thermal_loops.json'
CAPTURE = 'references/drive_capture_2026-10-03b'


# ---------- regimes (pure formulas) -------------------------------------------------------------------------------------

def _ref(s, path):
    node = s
    for part in path.split('.'):
        node = node[part]
    return node


def study(s):
    return s['thermal']['loops']['study']


def ideal_area_m2(load_W, T, eps):
    """Emitting area that rejects load_W facing space at temperature T and emissivity eps (delegates to thermal_budget)."""
    return thermal_budget.ideal_area_m2(load_W, eps, T)


def regimes(s):
    """Temperature, emissivity and absorptance (= emissivity) of the three loops. Warm/cold emissivity is the owner illustration (40!F61, F62)."""
    loops = s['thermal']['loops']
    eps_h = s['radiators']['emissivity']['value']
    out = {'hot': dict(T_K=_ref(s, loops['hot']['temperature_ref'])['value'], emissivity=eps_h, absorptance=eps_h)}
    for name in ('warm', 'cold'):
        eps = loops[name]['example']['emissivity']
        out[name] = dict(T_K=loops[name]['temperature_K'], emissivity=eps, absorptance=eps)
    return out


def owner_examples(s):
    loops = s['thermal']['loops']
    out = {}
    for name in ('warm', 'cold'):
        ex = loops[name]['example']
        out[name] = dict(load_W=ex['load_W'], T_K=loops[name]['temperature_K'], emissivity=ex['emissivity'],
                         ideal_area_m2=ideal_area_m2(ex['load_W'], loops[name]['temperature_K'], ex['emissivity']), stored_ideal_area_m2=ex['ideal_area_m2'])
    return out


def defense_band_areas(s):
    """Ideal warm-loop area at each defense-band endpoint (normal, limited duty, short burst), read from defense_routing."""
    df = s['thermal']['loops']['defense_routing']
    warm = regimes(s)['warm']
    loads = [df['normal_W'][0], df['normal_W'][1], df['limited_duty_W'][1], df['short_burst_W'][1]]
    return [dict(load_W=w, ideal_area_m2=ideal_area_m2(w, warm['T_K'], warm['emissivity'])) for w in loads]


def break_even_F(Ts, eps_s, alpha_s, Th, eps_h, F_space=1.0):
    """F_hot at which a surface neither gains nor loses net heat: eps_s*Ts^4*F_space / (alpha_s*eps_h*Th^4)."""
    return eps_s * Ts ** 4 * F_space / (alpha_s * eps_h * Th ** 4)


def net_flux_W_m2(Ts, eps_s, alpha_s, F_space, hot_terms):
    """Net emitted flux (positive = rejects). hot_terms: iterable of (F_hot, eps_h, Th)."""
    return eps_s * SIGMA * Ts ** 4 * F_space - alpha_s * sum(F * eh * SIGMA * Th ** 4 for F, eh, Th in hot_terms)


# ---------- spec check (schema only, no ray casting) --------------------------------------------------------------------

def _forbidden(node, path, bad):
    if isinstance(node, dict):
        if {'datum', 'offset_m'} <= set(node):
            bad.append(path)
        for k, v in node.items():
            if isinstance(k, str) and k.endswith(('_m', '_m2', '_x', '_deg')):
                bad.append(f'{path}.{k}')
            _forbidden(v, f'{path}.{k}', bad)


def check_study(s):
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    st = study(s)
    sm = st['sampling']
    require(st['status'] == 'PROTOTYPE' and st['evidence_ref'] == 'thermal_warm_regime', 'thermal.loops.study: PROTOTYPE with evidence_ref thermal_warm_regime')
    require(sm['kind'] == 'IMPLEMENTATION', 'thermal.loops.study.sampling: kind IMPLEMENTATION')
    fam = st['panel_families']
    require(fam and len(set(fam)) == len(fam) and set(fam) <= set(PANEL_FAMILIES), 'thermal.loops.study: unknown panel family')
    require(st['panel_double_sided'] is True and st['absorptance_rule'] == 'GRAY_EQUALS_EMISSIVITY' and st['hot_root_band_rule'] == 'HOT',
            'thermal.loops.study: double-sided gray panels, hot root band')
    require(list(st['cases']) == list(CASES), 'thermal.loops.study: cases')
    require(st['excluded'] and all(isinstance(x, str) for x in st['excluded']), 'thermal.loops.study: exclusions are listed')
    rays = sm['rays_per_point']
    require(type(rays) is int and rays > 0 and math.isqrt(rays) ** 2 == rays, 'thermal.loops.study.sampling: rays_per_point is a positive perfect square')
    for key in ('casing_azimuth_bands', 'casing_axial_bands', 'collar_azimuth_bands', 'panel_axial_bands'):
        require(type(sm[key]) is int and sm[key] > 0, f'thermal.loops.study.sampling.{key}: positive integer')
    pz = sm['points_per_zone']
    require(len(pz) == 2 and all(type(n) is int and n > 0 for n in pz), 'thermal.loops.study.sampling.points_per_zone: two positive integers')
    require(type(sm['seed']) is int and sm['sigma_multiple'] > 0, 'thermal.loops.study.sampling: seed and sigma_multiple')
    bad = []
    _forbidden(st, 'thermal.loops.study', bad)
    require(not bad, f'thermal.loops.study carries no length, angle or datum keys: {bad}')
    r = s['radiators']
    require(r['count'] * r['separation_deg'] == 360, 'thermal.loops.study: 3-fold symmetry')
    for name in ('warm', 'cold'):
        require(s['thermal']['loops'][name]['area'].get('known') is False, f'thermal.loops.{name}.area stays OPEN (Q38)')


# ---------- geometry primitives -----------------------------------------------------------------------------------------

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _norm(a)
    return (a[0] / n, a[1] / n, a[2] / n)


def plane(O, A, B, rects):
    """A double-sided plane with orthonormal in-plane axes A, B; rects are (u0, u1, v0, v1, tag) with tag HOT or ROOT_BAND."""
    N = _cross(A, B)
    return (*O, *A, *B, *N, tuple(rects))


def frustum(x0, r0, x1, r1):
    """Blocker surface of revolution about the ship X axis between two stations."""
    return (x0, x1, r0, (r1 - r0) / (x1 - x0))


def annulus(x, r_in, r_out, tag='BLOCKER'):
    return (x, r_in * r_in, r_out * r_out, tag)


def empty_scene():
    return dict(planes=[], frusta=[], annuli=[])


def plane_polys(pl):
    """Polygons (corner lists) and tags of one plane's rectangles."""
    ox, oy, oz, ax, ay, az, bx, by, bz = pl[:9]
    out = []
    for u0, u1, v0, v1, tag in pl[12]:
        out.append(([(ox + u * ax + v * bx, oy + u * ay + v * by, oz + u * az + v * bz) for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))], tag))
    return out


def trace(sc, px, py, pz, dx, dy, dz):
    """Tag of the nearest hit along the ray (HOT, ROOT_BAND, BLOCKER) or None for space."""
    best = INF
    tag = None
    for ox, oy, oz, ax, ay, az, bx, by, bz, nx, ny, nz, rects in sc['planes']:
        den = dx * nx + dy * ny + dz * nz
        if -1e-12 < den < 1e-12:
            continue
        t = ((ox - px) * nx + (oy - py) * ny + (oz - pz) * nz) / den
        if t <= TMIN or t >= best:
            continue
        qx = px + t * dx - ox
        qy = py + t * dy - oy
        qz = pz + t * dz - oz
        u = qx * ax + qy * ay + qz * az
        v = qx * bx + qy * by + qz * bz
        for u0, u1, v0, v1, tg in rects:
            if u0 <= u <= u1 and v0 <= v <= v1:
                best = t
                tag = tg
                break
    for x0, x1, r0, k in sc['frusta']:
        c0 = r0 + k * (px - x0)
        a = dy * dy + dz * dz - k * k * dx * dx
        b = 2 * (py * dy + pz * dz - c0 * k * dx)
        c = py * py + pz * pz - c0 * c0
        if -1e-14 < a < 1e-14:
            if -1e-14 < b < 1e-14:
                continue
            roots = (-c / b,)
        else:
            disc = b * b - 4 * a * c
            if disc < 0:
                continue
            sq = math.sqrt(disc)
            r1, r2 = (-b - sq) / (2 * a), (-b + sq) / (2 * a)
            roots = (r1, r2) if r1 < r2 else (r2, r1)
        for t in roots:
            if t <= TMIN:
                continue
            if t >= best:
                break
            x = px + t * dx
            if x0 <= x <= x1 and c0 + k * t * dx >= 0:
                best = t
                tag = 'BLOCKER'
                break
    for xa, ri2, ro2, tg in sc['annuli']:
        if -1e-12 < dx < 1e-12:
            continue
        t = (xa - px) / dx
        if t <= TMIN or t >= best:
            continue
        yy = py + t * dy
        zz = pz + t * dz
        rr = yy * yy + zz * zz
        if ri2 <= rr <= ro2:
            best = t
            tag = tg
    return tag


# ---------- exact view factor to a polygon ------------------------------------------------------------------------------

def clip_halfspace(poly, p, n):
    """Sutherland-Hodgman clip of a polygon to n.(q - p) >= 0."""
    out = []
    for i, a in enumerate(poly):
        b = poly[(i + 1) % len(poly)]
        sa, sb = _dot(n, _sub(a, p)), _dot(n, _sub(b, p))
        if sa >= 0:
            out.append(a)
        if (sa >= 0) != (sb >= 0):
            t = sa / (sa - sb)
            out.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), a[2] + t * (b[2] - a[2])))
    return out


def contour_F(p, n, poly):
    """Exact view factor from a differential element (p, unit normal n) to a planar polygon, unoccluded:
    F = |sum beta_i n.(r_i x r_i+1)/|r_i x r_i+1|| / 2 pi over the polygon clipped to the receiver half-space."""
    poly = clip_halfspace(poly, p, n)
    if len(poly) < 3:
        return 0.0
    vs = []
    for q in poly:
        v = _sub(q, p)
        length = _norm(v)
        if length < 1e-12:
            continue
        vs.append((v[0] / length, v[1] / length, v[2] / length))
    total = 0.0
    for i, a in enumerate(vs):
        b = vs[(i + 1) % len(vs)]
        c = _cross(a, b)
        cn = _norm(c)
        if cn < 1e-15:
            continue
        total += math.atan2(cn, _dot(a, b)) * _dot(n, c) / cn
    return abs(total) / (2 * math.pi)


def exact_hot_F(sc, point, normal):
    """Unoccluded F from a differential element to every hot rectangle: (F_hot_total, F_root_band). The root band counts as hot."""
    total = root = 0.0
    for pl in sc['planes']:
        for poly, tag in plane_polys(pl):
            f = contour_F(point, normal, poly)
            total += f
            if tag == 'ROOT_BAND':
                root += f
    return total, root


# ---------- Monte Carlo view factors -----------------------------------------------------------------------------------

def _frame(n):
    a = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
    t1 = _unit(_cross(n, a))
    return t1, _cross(n, t1)


def view_factors(sc, zone, sampling, grid=None):
    """Stratified cosine-weighted ray cast from the zone's grid points. Returns F_hot (HOT plus ROOT_BAND), F_root_band, F_blocker, F_space and
    the sigma_multiple * sqrt(F (1 - F) / N) bound of each (a conservative binomial bound under stratification)."""
    n1, n2 = grid or sampling['points_per_zone']
    m = math.isqrt(sampling['rays_per_point'])
    rng = random.Random(sampling['seed'] + zone['index'])
    counts = {'HOT': 0, 'ROOT_BAND': 0, 'BLOCKER': 0, None: 0}
    pts = zone['points'](n1, n2)
    two_pi = 2 * math.pi
    for p, n in pts:
        t1, t2 = _frame(n)
        px, py, pz = p[0] + OFFSET * n[0], p[1] + OFFSET * n[1], p[2] + OFFSET * n[2]
        for i in range(m):
            for j in range(m):
                u1 = (i + rng.random()) / m
                phi = two_pi * (j + rng.random()) / m
                rr = math.sqrt(u1)
                lx, ly, lz = rr * math.cos(phi), rr * math.sin(phi), math.sqrt(1.0 - u1)
                counts[trace(sc, px, py, pz, lx * t1[0] + ly * t2[0] + lz * n[0], lx * t1[1] + ly * t2[1] + lz * n[1], lx * t1[2] + ly * t2[2] + lz * n[2])] += 1
    big_n = len(pts) * m * m
    k = sampling['sigma_multiple']

    def pair(c):
        f = c / big_n
        return f, k * math.sqrt(f * (1 - f) / big_n)
    f_hot, b_hot = pair(counts['HOT'] + counts['ROOT_BAND'])
    f_root, b_root = pair(counts['ROOT_BAND'])
    f_blk, b_blk = pair(counts['BLOCKER'])
    f_space, b_space = pair(counts[None])
    return dict(F_hot=f_hot, F_hot_bound=b_hot, F_root_band=f_root, F_root_band_bound=b_root, F_blocker=f_blk, F_blocker_bound=b_blk,
                F_space=f_space, F_space_bound=b_space, rays=big_n)


def exact_zone_F(sc, zone, grid):
    """Mean unoccluded exact (F_hot, F_root_band) over the zone's grid points."""
    pts = zone['points'](*grid)
    tot = root = 0.0
    for p, n in pts:
        a, b = exact_hot_F(sc, p, n)
        tot += a
        root += b
    return tot / len(pts), root / len(pts)


# ---------- scene, read live ---------------------------------------------------------------------------------------------

def blade_angles(s):
    p, r = s['prototype'], s['radiators']
    return [math.radians(p['radiator_phase_deg'] + j * r['separation_deg']) for j in range(r['count'])]


def scene(s):
    """Hot blade planes, hull, ring and shield blockers from the live pure modules. One 120-degree sector is computed; the receivers are x3."""
    r = s['radiators']
    if r['count'] * r['separation_deg'] != 360:
        raise ValueError('thermal_loops: the screen needs a 3-fold symmetric blade set')
    d = thermal_geometry.blade_of(s)
    L, w, gap = d['blade_length_m'], d['ribbon_width_m'], d['gap_m']
    rb = thermal_geometry.root_band(s)['width_m']
    sc = empty_scene()
    face_area = 0.0
    for a in blade_angles(s):
        rects = []
        for k in range(d['ribbons']):
            v0 = k * (w + gap)
            if k == 0:
                rects += [(-L / 2, L / 2, 0.0, rb, 'ROOT_BAND'), (-L / 2, L / 2, rb, w, 'HOT')]
            else:
                rects.append((-L / 2, L / 2, v0, v0 + w, 'HOT'))
        O = thermal_geometry.local_to_ship(d, a, 0.0, 0.0, 0.0)
        A = _sub(thermal_geometry.local_to_ship(d, a, 1.0, 0.0, 0.0), O)
        B = _sub(thermal_geometry.local_to_ship(d, a, 0.0, 1.0, 0.0), O)
        sc['planes'].append(plane(O, A, B, rects))
        face_area = sum((u1 - u0) * (v1 - v0) for u0, u1, v0, v1, _ in rects)
    if not math.isclose(face_area, r['physical_area']['value'], rel_tol=1e-9):
        raise ValueError('thermal_loops: hot rectangles differ from radiators.physical_area')
    sc['hot_area_per_face_m2'] = face_area
    # Hull: solid of revolution between the skinned-span limits; the open rotor bay is filled at radius_at (conservative).
    iv = hull_geometry.intervals(s)
    lo, hi = iv[0][1], iv[1][2]
    xs = [lo] + [p['x'] for p in hull_geometry.profile(s) if lo < p['x'] < hi] + [hi]
    for xa, xb in zip(xs, xs[1:]):
        sc['frusta'].append(frustum(xa, hull_geometry.radius_at(s, xa), xb, hull_geometry.radius_at(s, xb)))
    sc['annuli'].append(annulus(lo, 0.0, hull_geometry.radius_at(s, lo)))
    # Rings: the full annulus of habitat_ring.frame_parts (spokes ignored), read live so a moved ring moves its zones and blockers.
    h = s['habitat_ring']['frame_axial_m'] / 2
    ri, ro = s['habitat_ring']['frame_inner_radius_m'], habitat_ring.outer(s)
    for c in habitat_ring.centers(s):
        sc['frusta'] += [frustum(c - h, ro, c + h, ro), frustum(c - h, ri, c + h, ri)]
        sc['annuli'] += [annulus(c - h, ri, ro), annulus(c + h, ri, ro)]
    sc['annuli'].append(annulus(forward_shield.stations(s)['truss_aft'], 0.0, forward_shield.shield_radius(s)))
    return sc


def _casing_span(s):
    rc = thermal_geometry.casing_radius(s)
    xs = [p['x'] for p in hull_geometry.profile(s) if math.isclose(p['r'], rc)]
    iv = hull_geometry.intervals(s)[0]
    return max(min(xs), iv[1]), min(max(xs), iv[2])


def _collar_span(s):
    return hull_geometry.intervals(s)[1][1], forward_shield.stations(s)['truss_aft']


def _slope(s, x):
    pts = hull_geometry.profile(s)
    for a, b in zip(pts, pts[1:]):
        if x <= b['x']:
            return (b['r'] - a['r']) / (b['x'] - a['x'])
    return 0.0


def _panel_envelope(s):
    p = s['prototype']
    clr = p['mechanical_clearance_m']
    return dict(r_lo=habitat_ring.outer(s) + clr, r_hi=forward_shield.shield_radius(s) - s['forward_shield']['radiator_shadow_margin']['value'],
                x_lo=layout.origin(s, 'RADIATOR_FRONT') + p['radiator_leading_spar_radius_m'] + clr, x_hi=forward_shield.stations(s)['truss_aft'] - clr)


def _mid(lo, hi, i, n):
    return lo + (hi - lo) * (i + 0.5) / n


def _corridor_conflict(s, env, x0, x1, theta0):
    """Dock keep-out cylinders (axis radial at the dock azimuth) against a radial plate at theta0 (and its 3-fold copies)."""
    r_cnt = s['radiators']['count']
    for c in hull_geometry.dock_corridors(s):
        if x1 < c['x'] - c['radius'] or x0 > c['x'] + c['radius']:
            continue
        for k in range(r_cnt):
            dth = c['theta'] - (theta0 + k * 2 * math.pi / r_cnt)
            if math.cos(dth) <= 0:
                continue
            lo, hi = max(env['r_lo'], c['r0']), min(env['r_hi'], c['r1'])
            if lo <= hi and lo * abs(math.sin(dth)) < c['radius']:
                return True
    return False


def zones(s):
    """Candidate receiver zones, all bounds derived live. area_m2 is the whole ship (x3 symmetric sectors for casing, collar and panels; the
    full ring for ring surfaces, sampled over one sector = the rotation average). points(n1, n2) gives a midpoint grid of (point, outward normal)."""
    sm, r = study(s)['sampling'], s['radiators']
    n_sym = r['count']
    sep = math.radians(r['separation_deg'])
    th0 = math.radians(s['prototype']['radiator_phase_deg'])
    out = []

    def add(name, loop, surface, area, pts, **extra):
        out.append(dict(name=name, loop=loop, surface=surface, area_m2=area, points=pts, index=len(out), **extra))

    # Warm: stationary casing under the blade span.
    rc = thermal_geometry.casing_radius(s)
    xa, xb = _casing_span(s)
    na, nx = sm['casing_azimuth_bands'], sm['casing_axial_bands']
    dth, dx = sep / na, (xb - xa) / nx
    for a in range(na):
        for k in range(nx):
            def pts(n1, n2, a=a, k=k, dth=dth, dx=dx):
                return [((_mid(xa + k * dx, xa + (k + 1) * dx, j, n2), rc * math.cos(t), rc * math.sin(t)), (0.0, math.cos(t), math.sin(t)))
                        for i in range(n1) for j in range(n2) for t in (_mid(th0 + a * dth, th0 + (a + 1) * dth, i, n1),)]
            add(f'CASING_{a + 1}_{k + 1}', 'warm', 'CASING', n_sym * rc * dth * dx, pts, azimuth_band=a + 1, axial_band=k + 1)
    # Warm: forward collar to the shield truss.
    ca, cb = _collar_span(s)
    na = sm['collar_azimuth_bands']
    dth = sep / na
    prof = hull_geometry.profile(s)
    knots = [ca] + [p['x'] for p in prof if ca < p['x'] < cb] + [cb]
    slant = sum((hull_geometry.radius_at(s, u) + hull_geometry.radius_at(s, v)) / 2 * math.hypot(v - u, hull_geometry.radius_at(s, v) - hull_geometry.radius_at(s, u))
                for u, v in zip(knots, knots[1:]))
    for a in range(na):
        def pts(n1, n2, a=a, dth=dth):
            res = []
            for i in range(n1):
                t = _mid(th0 + a * dth, th0 + (a + 1) * dth, i, n1)
                for j in range(n2):
                    x = _mid(ca, cb, j, n2)
                    k = _slope(s, x)
                    rr = hull_geometry.radius_at(s, x)
                    res.append(((x, rr * math.cos(t), rr * math.sin(t)), (-k / math.sqrt(1 + k * k), math.cos(t) / math.sqrt(1 + k * k), math.sin(t) / math.sqrt(1 + k * k))))
            return res
        add(f'COLLAR_{a + 1}', 'warm', 'COLLAR', n_sym * dth * slant, pts, azimuth_band=a + 1)
    # Cold: ring A/B surfaces over the full annulus of the ring frame.
    h = s['habitat_ring']['frame_axial_m'] / 2
    ri, ro = s['habitat_ring']['frame_inner_radius_m'], habitat_ring.outer(s)
    for j, c in enumerate(habitat_ring.centers(s), 1):
        def az(n1):                                 # the sector is the same for every ring
            return [_mid(th0, th0 + sep, i, n1) for i in range(n1)]

        def rim(radius, sign, c=c):
            return lambda n1, n2: [((_mid(c - h, c + h, k, n2), radius * math.cos(t), radius * math.sin(t)), (0.0, sign * math.cos(t), sign * math.sin(t))) for t in az(n1) for k in range(n2)]

        def face(xf, sign):
            def pts(n1, n2):
                res = []
                for t in az(n1):
                    for k in range(n2):
                        rr = math.sqrt(ri * ri + (ro * ro - ri * ri) * (k + 0.5) / n2)
                        res.append(((xf, rr * math.cos(t), rr * math.sin(t)), (float(sign), 0.0, 0.0)))
                return res
            return pts
        for label, area, pts in (('OUTER_RIM', 2 * math.pi * ro * 2 * h, rim(ro, 1)), ('INNER_RIM', 2 * math.pi * ri * 2 * h, rim(ri, -1)),
                                 ('AFT_FACE', math.pi * (ro * ro - ri * ri), face(c - h, -1)), ('FORE_FACE', math.pi * (ro * ro - ri * ri), face(c + h, 1))):
            add(f'RING_{j}_{label}', 'cold', f'RING_{label}', area, pts, ring=j)
    # Warm: candidate shadow panels (radial-axial plates at the blade angle or the bisector).
    env = _panel_envelope(s)
    nb = sm['panel_axial_bands']
    dxp = (env['x_hi'] - env['x_lo']) / nb
    for fam in study(s)['panel_families']:
        theta = th0 + (sep / 2 if fam == 'BISECTOR' else 0.0)
        for k in range(nb):
            x0, x1 = env['x_lo'] + k * dxp, env['x_lo'] + (k + 1) * dxp
            conflict = _corridor_conflict(s, env, x0, x1, theta)
            for sign, label in ((1, '+'), (-1, '-')):
                def pts(n1, n2, x0=x0, x1=x1, sign=sign, theta=theta):
                    return [((_mid(x0, x1, i, n1), rr * math.cos(theta), rr * math.sin(theta)), (0.0, -sign * math.sin(theta), sign * math.cos(theta)))
                            for i in range(n1) for j in range(n2) for rr in (_mid(env['r_lo'], env['r_hi'], j, n2),)]
                add(f'PANEL_{fam}_{k + 1}_{label}', 'warm', f'PANEL_{fam}', n_sym * dxp * (env['r_hi'] - env['r_lo']), pts, dock_corridor_conflict=conflict)
    return out


ZERO_EXCHANGE = dict(
    statement='Non-hot blockers (hull, casing, rings, shield) and dark blades exchange net zero with the receiver. DIAGNOSTIC: the direction of the error is stated, not simulated.',
    direction={
        'cold': {'HIGH_POWER': 'OPTIMISTIC: the hull/casing is a >=450 K warm surface (and HP-heated) under the study\'s own premise, not a 320 K neighbour, so zero exchange overstates ring capacity; q_if_blockers_at_warm_W_m2 bounds it',
                 'BLADES_NOT_RADIATING': 'OPTIMISTIC: same, the warm hull/casing seen by the rings would reduce or reverse ring capacity (q_if_blockers_at_warm_W_m2); dark blades can act either way (sink or source) depending on their temperature, and blade duty outside burns is OPEN (Q41)'},
        'warm': {'HIGH_POWER': 'NEUTRAL TO PESSIMISTIC: the casing, collar and panels are net-heated by the blades regardless; hot-neighbour blockers are already hot-class',
                 'BLADES_NOT_RADIATING': 'PESSIMISTIC: dark blades treated as adiabatic; if colder than the receiver they are sinks, which would add capacity (reviewer estimate about +2.6 MW at the casing, enough to erase the 1.15 MW shortfall; not simulated here)'}},
    dependent_findings=['COLD_EXAMPLE_COVERAGE', 'BNR_CLASSES_ASSUMPTION_DEPENDENT', 'WARM_LOOP_AREA_SHORTFALL (BLADES_NOT_RADIATING)'])


# ---------- evaluation --------------------------------------------------------------------------------------------------

def classify(q_lo, q_hi):
    if q_lo > 0:
        return 'USABLE'
    if q_hi < 0:
        return 'NET_HEATED'
    return 'MARGINAL'


def evaluate_case(case, regs, loop, mc):
    """Net flux, class and capacity/absorbed power for one zone and case. The class is judged at the worst/best end of the sampling bounds."""
    reg, hot = regs[loop], regs['hot']
    eps, alpha, ts = reg['emissivity'], reg['absorptance'], reg['T_K']

    def q(f_hot, f_space):
        terms = [(f_hot, hot['emissivity'], hot['T_K'])] if case == 'HIGH_POWER' else []
        return net_flux_W_m2(ts, eps, alpha, f_space, terms)
    nominal = q(mc['F_hot'], mc['F_space'])
    lo = q(mc['F_hot'] + mc['F_hot_bound'], max(0.0, mc['F_space'] - mc['F_space_bound']))
    hi = q(max(0.0, mc['F_hot'] - mc['F_hot_bound']), min(1.0, mc['F_space'] + mc['F_space_bound']))
    return dict(q_W_m2=nominal, q_low_W_m2=lo, q_high_W_m2=hi, cls=classify(lo, hi))


def zone_row(sc, zone, sampling, regs, exact=True):
    """MC view factors, the exact unoccluded F_hot and its grid-refinement delta, and both cases for one zone."""
    mc = view_factors(sc, zone, sampling)
    reg = regs[zone['loop']]
    row = dict(name=zone['name'], loop=zone['loop'], surface=zone['surface'], area_m2=zone['area_m2'], T_K=reg['T_K'], emissivity=reg['emissivity'],
               absorptance=reg['absorptance'], **{k: v for k, v in mc.items()},
               break_even_F=break_even_F(reg['T_K'], reg['emissivity'], reg['absorptance'], regs['hot']['T_K'], regs['hot']['emissivity']))
    if 'dock_corridor_conflict' in zone:
        row['dock_corridor_conflict'] = zone['dock_corridor_conflict']
    if exact:
        grid = tuple(sampling['points_per_zone'])
        e1, root1 = exact_zone_F(sc, zone, grid)
        e2, _ = exact_zone_F(sc, zone, (2 * grid[0], 2 * grid[1]))
        row.update(F_hot_exact_unoccluded=e1, F_root_band_exact_unoccluded=root1, exact_refinement_delta=abs(e2 - e1))
    row['cases'] = {}
    for case in CASES:
        ev = evaluate_case(case, regs, zone['loop'], mc)
        a, q = zone['area_m2'], ev['q_W_m2']
        ev.update(capacity_W=max(q, 0.0) * a, absorbed_W=max(-q, 0.0) * a)
        if zone['loop'] == 'cold':
            # DIAGNOSTIC bound: the blocked fraction (hull, casing, other rings, shield) radiates at the warm-loop temperature, not at the receiver's.
            w = regs['warm']
            ev['q_if_blockers_at_warm_W_m2'] = ev['q_W_m2'] - reg['absorptance']*w['emissivity']*SIGMA*w['T_K']**4*mc['F_blocker']
        row['cases'][case] = ev
    return row


_WORK = {}


def _work(i):
    sc, zs, sampling, regs, exact = _WORK['args']
    return zone_row(sc, zs[i], sampling, regs, exact)


def sampling_of(s, override=None):
    out = dict(study(s)['sampling'])
    out.update(override or {})
    return out


def live_inputs(s):
    """The live values the report depends on; --check compares them with the stored report to detect a stale file."""
    d = thermal_geometry.blade_of(s)
    env = _panel_envelope(s)
    ca, cb = _collar_span(s)
    xa, xb = _casing_span(s)
    return dict(blade_aft_x_m=d['aft_x_m'], blade_front_x_m=d['front_x_m'], blade_cant_deg=d['cant_deg'], blade_ribbons=d['ribbons'],
                blade_length_m=d['blade_length_m'], blade_phase_deg=s['prototype']['radiator_phase_deg'], blade_count=s['radiators']['count'],
                radiator_front_x_m=layout.origin(s, 'RADIATOR_FRONT'), ring_a_x_m=layout.origin(s, 'RING_A'), ring_centers_x_m=habitat_ring.centers(s),
                ring_inner_radius_m=s['habitat_ring']['frame_inner_radius_m'], ring_outer_radius_m=habitat_ring.outer(s),
                casing_radius_m=thermal_geometry.casing_radius(s), casing_span_x_m=[xa, xb], collar_span_x_m=[ca, cb],
                shield_truss_aft_x_m=forward_shield.stations(s)['truss_aft'], shield_radius_m=forward_shield.shield_radius(s), panel_envelope=env,
                dock_corridors=hull_geometry.dock_corridors(s), regimes=regimes(s), defense_routing=s['thermal']['loops']['defense_routing'],
                root_band_width_m=thermal_geometry.root_band(s)['width_m'], study=study(s))


def _totals(rows):
    out = {}
    for case in CASES:
        t = dict(screened_area_m2=0.0, usable_area_m2=0.0, marginal_area_m2=0.0, net_heated_area_m2=0.0, capacity_W=0.0, capacity_with_marginal_W=0.0, absorbed_W=0.0)
        for r in rows:
            c = r['cases'][case]
            t['screened_area_m2'] += r['area_m2']
            t['absorbed_W'] += c['absorbed_W']
            key = {'USABLE': 'usable_area_m2', 'MARGINAL': 'marginal_area_m2', 'NET_HEATED': 'net_heated_area_m2'}[c['cls']]
            t[key] += r['area_m2']
            if c['cls'] == 'USABLE':
                t['capacity_W'] += c['capacity_W']
            if c['cls'] != 'NET_HEATED':
                t['capacity_with_marginal_W'] += c['capacity_W']
        t['capacity_MW'] = t['capacity_W'] / 1e6
        t['capacity_with_marginal_MW'] = t['capacity_with_marginal_W'] / 1e6
        out[case] = t
    return out


def report(s, sampling=None, zone_filter=None, workers=1, digest=None, exact=True):
    """The DIAGNOSTIC heat-loop screen. s is never modified; zone_filter (a name predicate) and sampling overrides exist for fast tests only."""
    check_study(s)
    sm = sampling_of(s, sampling)
    regs = regimes(s)
    sc = scene(s)
    zs = [z for z in zones(s) if zone_filter is None or zone_filter(z['name'])]
    if workers > 1:
        import multiprocessing
        _WORK['args'] = (sc, zs, sm, regs, exact)
        with multiprocessing.get_context('fork').Pool(workers) as pool:
            rows = pool.map(_work, range(len(zs)), chunksize=1)
    else:
        rows = [zone_row(sc, z, sm, regs, exact) for z in zs]
    surfaces = {}
    for name in dict.fromkeys(r['surface'] for r in rows):
        surfaces[name] = _totals([r for r in rows if r['surface'] == name])
    loops = {name: _totals([r for r in rows if r['loop'] == name]) for name in ('warm', 'cold') if any(r['loop'] == name for r in rows)}
    df = s['thermal']['loops']['defense_routing']
    warm = regs['warm']
    unit_flux = warm['emissivity'] * SIGMA * warm['T_K'] ** 4
    rc = thermal_geometry.casing_radius(s)
    xa, xb = _casing_span(s)
    casing_area = 2 * math.pi * rc * (xb - xa)
    bound = dict(casing_area_m2=casing_area, casing_ideal_W=casing_area * unit_flux,
                 all_warm_zones_ideal_W=sum(z['area_m2'] for z in zs if z['loop'] == 'warm') * unit_flux,
                 flux_W_m2=unit_flux)
    return dict(
        note='Candidate-zone screen; thermal.loops.warm.area and cold.area stay OPEN (Q38). Every value is DIAGNOSTIC; the zones are PROTOTYPE.',
        status='DIAGNOSTIC', capture=CAPTURE, spec_digest=digest, inputs=live_inputs(s), sampling=sm, cases=list(CASES),
        assumptions=['thin blade planes, both faces emitting, spar and truss ignored', 'root band treated as hot (temperature map OPEN)',
                     'gray surfaces, alpha = emissivity (owner illustration emissivity)', 'non-hot blockers (hull, rings, shield) exchange net zero with the receiver',
                     'open rotor bay filled at the hull radius_at; shield modelled as an aft-most disc', 'panels are receivers only, not blockers',
                     'ring results are averaged over azimuth (rotation average); spokes ignored',
                     'BLADES_NOT_RADIATING bounds the case only under the stated blade assumption (dark blades adiabatic); it is not a strict best case, and real COAST hot-loop duty is OPEN (Q41)',
                     'the zero-exchange assumption errs in a known direction per loop and case (zero_exchange_assumption); classes that depend on it are flagged'],
        excluded=list(study(s)['excluded']), zero_exchange_assumption=ZERO_EXCHANGE,
        regimes=dict(temperatures_emissivity=regs, owner_examples=owner_examples(s), defense_band_areas=defense_band_areas(s),
                     break_even_F=dict(warm=break_even_F(warm['T_K'], warm['emissivity'], warm['absorptance'], regs['hot']['T_K'], regs['hot']['emissivity']),
                                       cold=break_even_F(regs['cold']['T_K'], regs['cold']['emissivity'], regs['cold']['absorptance'], regs['hot']['T_K'], regs['hot']['emissivity']))),
        deterministic_bound=bound, zones=rows, surfaces=surfaces, loops=loops, findings=findings(s, rows, loops, bound, regs, zs),
        comparison_loads_W=dict(warm_example=s['thermal']['loops']['warm']['example']['load_W'], normal=df['normal_W'], limited_duty=df['limited_duty_W'],
                                short_burst=df['short_burst_W'], cold_example=s['thermal']['loops']['cold']['example']['load_W']))


def findings(s, rows, loops, bound, regs, zs):
    df = s['thermal']['loops']['defense_routing']
    normal_lo = df['normal_W'][0]
    out = []
    if bound['casing_ideal_W'] < normal_lo:
        out.append(dict(code='WARM_CASING_IDEAL_BOUND_BELOW_NORMAL', casing_area_m2=bound['casing_area_m2'], casing_ideal_MW=bound['casing_ideal_W'] / 1e6,
                        all_warm_zones_ideal_MW=bound['all_warm_zones_ideal_W'] / 1e6, normal_low_MW=normal_lo / 1e6, ref='Q38'))
    for case in CASES:
        if 'warm' in loops:
            cap = loops['warm'][case]['capacity_W']
            if cap < normal_lo:
                out.append(dict(code='WARM_LOOP_AREA_SHORTFALL', case=case, depends_on_zero_exchange=(case == 'BLADES_NOT_RADIATING'),
                                assumption_direction=ZERO_EXCHANGE['direction']['warm'][case], usable_capacity_MW=cap / 1e6, with_marginal_MW=loops['warm'][case]['capacity_with_marginal_W'] / 1e6,
                                normal_low_MW=normal_lo / 1e6, shortfall_MW=(normal_lo - cap) / 1e6, ref='Q38'))
    hp = 'HIGH_POWER'
    heated = [r['name'] for r in rows if r['cases'][hp]['cls'] == 'NET_HEATED']
    if heated:
        out.append(dict(code='SURFACES_NET_HEATED_HIGH_POWER', count=len(heated), zones=heated, ref='Q38'))
    hot = regs['hot']
    gross = sum(regs[r['loop']]['absorptance'] * r['F_hot'] * hot['emissivity'] * SIGMA * hot['T_K'] ** 4 * r['area_m2'] for r in rows if r['surface'] == 'CASING')
    if gross > 0:
        out.append(dict(code='CASING_ABSORBS_BLADE_HEAT', case=hp, absorbed_gross_W=gross,
                        net_absorbed_W=sum(r['cases'][hp]['absorbed_W'] for r in rows if r['surface'] == 'CASING'), ref='Q38'))
    ring_heated = [r['name'] for r in rows if r['loop'] == 'cold' and r['cases'][hp]['cls'] == 'NET_HEATED']
    if ring_heated:
        out.append(dict(code='COLD_RING_SURFACES_NET_HEATED', case=hp, zones=ring_heated, ref='Q38'))
    if 'cold' in loops:
        ex = s['thermal']['loops']['cold']['example']
        cold_ideal = ideal_area_m2(ex['load_W'], regs['cold']['T_K'], regs['cold']['emissivity'])
        fore = [r for r in rows if r['surface'] == 'RING_FORE_FACE']
        alt = {c: sum(max(r['cases'][c].get('q_if_blockers_at_warm_W_m2', 0.0), 0.0)*r['area_m2'] for r in fore)/1e3 for c in CASES}
        out.append(dict(code='COLD_EXAMPLE_COVERAGE', depends_on_zero_exchange=True, assumption_direction=ZERO_EXCHANGE['direction']['cold'],
                        fore_face_capacity_kW_if_blockers_at_warm=alt, label='DIAGNOSTIC pessimistic extreme, not a simulation: the whole blocked fraction (incl. the shield) at 450 K, and it omits the receiver\'s own emission toward the blocked fraction. The reviewer estimate of about 76 kW for the fore faces is HIGH_POWER with only the hull at 450 K and the shield excluded',
                        example_load_kW=ex['load_W'] / 1e3, example_ideal_area_m2=cold_ideal,
                        usable_area_m2={c: loops['cold'][c]['usable_area_m2'] for c in CASES}, capacity_MW={c: loops['cold'][c]['capacity_MW'] for c in CASES},
                        note='the actual cold load is OPEN; only the 100 kW illustration exists (40!F62)', ref='Q38'))
    dep = [r['name'] for r in rows if r['loop'] == 'cold' and r['cases']['BLADES_NOT_RADIATING']['cls'] == 'USABLE'
           and r['cases']['BLADES_NOT_RADIATING'].get('q_if_blockers_at_warm_W_m2', 1.0) < 0]
    if dep:
        out.append(dict(code='BNR_CLASSES_ASSUMPTION_DEPENDENT', case='BLADES_NOT_RADIATING', zones_usable_only_under_zero_exchange=dep, depends_on_zero_exchange=True,
                        assumption_direction=ZERO_EXCHANGE['direction']['cold']['BLADES_NOT_RADIATING'], ref='Q38'))
    rims = [r['name'] for r in rows if r['surface'] == 'RING_OUTER_RIM' and r['cases'][hp]['cls'] == 'NET_HEATED']
    if rims:
        out.append(dict(code='COLD_RIM_PLAN_CONTRADICTION', case=hp, zones=rims, rings_absorbed_W=loops['cold'][hp]['absorbed_W'] if 'cold' in loops else None,
                        note='the plan\'s cold radiators on the ring rims are net-heated in HIGH_POWER; the rings absorb the stated power from the blades', ref='Q38'))
    marginal = {c: [r['name'] for r in rows if r['cases'][c]['cls'] == 'MARGINAL'] for c in CASES}
    if any(marginal.values()):
        out.append(dict(code='MARGINAL_SURFACES', zones=marginal, ref='Q38'))
    casing = [r for r in rows if r['surface'] == 'CASING']
    if casing:
        a_c = sum(r['area_m2'] for r in casing)
        f_c = sum(r['area_m2'] * r['F_hot'] for r in casing) / a_c
        a_h = 2 * s['radiators']['count'] * s['radiators']['physical_area']['value']
        f_h = a_c * f_c / a_h
        out.append(dict(code='BLADE_HULL_SELF_VIEW', casing_mean_F_to_blades=f_c, blade_to_casing_F=f_h, hot_face_area_m2=a_h,
                        note='context for 40!A23 (view factor 0.9 must be revalidated for hull self-view); radiators.view_factor is never written', ref='40!A23'))
    return out


# ---------- command line ------------------------------------------------------------------------------------------------

def _print_table(rep):
    rows = rep['zones']
    print('Heat-loop screen (DIAGNOSTIC, PROTOTYPE zones; warm/cold area OPEN, Q38)')
    print('regimes:', json.dumps({k: round(v, 5) for k, v in rep['regimes']['break_even_F'].items()}), 'break-even F_hot/F_space')
    print('defense-band warm areas (m2):', ', '.join(f"{b['load_W'] / 1e6:g} MW={b['ideal_area_m2']:.1f}" for b in rep['regimes']['defense_band_areas']))
    casing = {(r['name']): r for r in rows if r['surface'] == 'CASING'}
    if casing:
        na = max(int(n.split('_')[1]) for n in casing)
        nk = max(int(n.split('_')[2]) for n in casing)
        print('casing q in HIGH_POWER, kW/m2 (rows axial band aft->front, columns azimuth band):')
        for k in range(1, nk + 1):
            print('  k%02d ' % k + ' '.join('%8.1f' % (casing[f'CASING_{a}_{k}']['cases']['HIGH_POWER']['q_W_m2'] / 1e3) for a in range(1, na + 1)))
    print('%-28s %9s %8s %8s %8s | %10s %10s' % ('zone', 'area_m2', 'F_hot', 'F_exact', 'F_space', 'HP q W/m2', 'BNR q W/m2'))
    for r in rows:
        if r['surface'] == 'CASING':
            continue
        print('%-28s %9.1f %8.4f %8.4f %8.4f | %10.0f %10.0f  %s/%s' % (r['name'], r['area_m2'], r['F_hot'], r.get('F_hot_exact_unoccluded', float('nan')), r['F_space'],
              r['cases']['HIGH_POWER']['q_W_m2'], r['cases']['BLADES_NOT_RADIATING']['q_W_m2'], r['cases']['HIGH_POWER']['cls'], r['cases']['BLADES_NOT_RADIATING']['cls']))
    for title, group in (('surface', rep['surfaces']), ('loop', rep['loops'])):
        for name, cases in group.items():
            for case, t in cases.items():
                print(f"{title} {name:22s} {case:21s} screened {t['screened_area_m2']:9.1f} usable {t['usable_area_m2']:9.1f} marginal {t['marginal_area_m2']:8.1f} "
                      f"heated {t['net_heated_area_m2']:9.1f} m2 capacity {t['capacity_MW']:8.3f} MW (+marginal {t['capacity_with_marginal_MW']:.3f}) absorbed {t['absorbed_W'] / 1e6:9.2f} MW")
    for f in rep['findings']:
        print('FINDING', json.dumps(f, default=str)[:600])


def main(argv):
    import spec
    root = spec.ROOT
    s, _, text, _ = spec.load(root)
    path = Path(root) / REPORT_PATH
    if '--check' in argv:
        stored = json.loads(path.read_text())['inputs']
        live = json.loads(json.dumps(live_inputs(s)))
        if stored != live:
            print(f'{REPORT_PATH} is stale: live inputs differ; regenerate with python3 src/wayfarer/thermal_loops.py')
            return 1
        print(f'{REPORT_PATH} matches the live inputs')
        return 0
    import os
    workers = max(1, min(os.cpu_count() or 1, 16))
    rep = report(s, workers=workers, digest=spec.digest(text))
    path.write_text(json.dumps(rep, indent=1, default=str) + '\n')
    _print_table(rep)
    print(f'wrote {REPORT_PATH}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
