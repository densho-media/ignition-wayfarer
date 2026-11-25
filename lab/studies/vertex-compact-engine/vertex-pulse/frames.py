#!/usr/bin/env python3
"""Integrated parametric engine hardware for the approved research geometry (burn 4 m aft, closure x4; owner brief 2026-11-25 08:55Z,
item 5). WORK / PROTOTYPE, not canon. Pure Python: it writes results/frames.json, which blender_pulse.py turns into meshes.

Per coil station (C1, C2, L1-L4 of vertex-optimize coils.json, engine frame, +X forward, burn at x = -22.8):
  LIP        sacrificial tungsten armour re-aimed at the moved burn: a poloidal shell round the burn-facing side of the cryostat, eight
             toroidal modules split at the cage longerons (the exchange interface), lithium-cooled from behind;
  HOT        supply and return headers along the lip's outer edge, feeders into each module, and branches to the existing lithium
             supply and return lines on the cage (replacing the approved armour headers and jumpers, which faced the drawn burn);
  CRYO       a 20 K distribution ring on the cryostat skin, fed from both existing cryogen lines on the cage;
  WARM       a 300-600 K ring (cryostat thermal shield and frame cooling) on two new warm headers along the cage;
  MIRROR     grazing-incidence supermirror strips on both lip edges: conical facets with their apex at the burn, set 0.2 deg off the ray,
             so only X-rays striking within the reflecting angle (a few mrad at 100 keV) are turned away;
  TRAY       a busbar / instrumentation tray from the cryostat to the existing coil current lead line.
The approved seats, struts, longerons and lines stay; the checks treat them as fixed neighbours.

Checks (written to the JSON, PROTOTYPE limits in P): every network is one connected graph from its plant, by geometry, not by
declaration; no two parts that are not joined come closer than P['gap']; no pipe runs farther than P['span'] between supports.

    python3 lab/studies/vertex-compact-engine/vertex-pulse/frames.py
"""
import json
import math
import sys
import tomllib
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
import vertex_engine as ve  # noqa: E402

CO = json.loads((ROOT / 'lab/studies/vertex-compact-engine/vertex-optimize/results/coils.json').read_text())
P = dict(lip_half_deg=70.0, lip_gap=0.06, lip_t=0.05, hot_r=0.10, hot_off=0.25, hot_step_deg=14.0, edge_deg=8.0, edge_steps=(8.0, 20.0, 32.0, 44.0, 56.0),
         cryo_r=0.06, cryo_off=0.09, warm_r=0.07, warm_off=0.12, warm_stack=0.23, branch_r=0.07, feeder_r=0.04, tray_w=0.24, tray_h=0.10,
         mirror_len=0.9, mirror_off_deg=0.2, mirror_facets=48, modules=8, gap=0.02, span=3.0, lead_in=0.6,
         warm_az=(118.5, 298.5), cryo_side_deg=35.0, warm_side_deg=62.0)
BX = CO['burn_x_moved']
LONG_AZ = [22.5 + 45 * j for j in range(8)]


def pol(x, r, az):
    a = math.radians(az)
    return (x, r * math.cos(a), r * math.sin(a))


def xr(c, a, th):
    """Point at poloidal angle th (deg; 0 = +x, 90 = radially out) and distance a from the coil centre c = (x, r)."""
    t = math.radians(th)
    return (c[0] + a * math.cos(t), c[1] + a * math.sin(t))


def ang(v):
    return math.degrees(math.atan2(v[1], v[0])) % 360


def segdist(P0, P1, Q0, Q1):
    """Exact distances between every segment P0-P1 (n) and Q0-Q1 (m), an n x m array (clamped closest points)."""
    d1 = P1 - P0; d2 = Q1 - Q0; r = P0[:, None, :] - Q0[None, :, :]
    a = np.maximum((d1 * d1).sum(-1), 1e-12)[:, None]; e = np.maximum((d2 * d2).sum(-1), 1e-12)[None, :]
    b = d1 @ d2.T; c = (d1[:, None, :] * r).sum(-1); f = (d2[None, :, :] * r).sum(-1)
    den = a * e - b * b
    s = np.where(den > 1e-12, np.clip((b * f - c * e) / np.where(den > 1e-12, den, 1.0), 0, 1), 0.0)
    tt = (b * s + f) / e
    s = np.where(tt < 0, np.clip(-c / a, 0, 1), np.where(tt > 1, np.clip((b - c) / a, 0, 1), s))
    tt = np.clip(tt, 0, 1)
    D = P0[:, None, :] + d1[:, None, :] * s[..., None] - Q0[None, :, :] - d2[None, :, :] * tt[..., None]
    return np.sqrt((D * D).sum(-1))


def dseg_(p, a, b):
    ab = [b[i] - a[i] for i in range(3)]; L2 = sum(q * q for q in ab) or 1e-12
    t = max(0.0, min(1.0, sum((p[i] - a[i]) * ab[i] for i in range(3)) / L2))
    return math.dist(p, [a[i] + t * ab[i] for i in range(3)])


def gap_rows(segs, F, chunk=200):
    """Smallest gap of each capsule in segs to the set F (array per row)."""
    A0, A1, Ar = arr(segs)
    out = []
    for i in range(0, len(A0), chunk):
        D = segdist(A0[i:i + chunk], A1[i:i + chunk], F[0], F[1]) - Ar[i:i + chunk, None] - F[2][None, :]
        out.append(D.min(1))
    return np.concatenate(out)


def seen_from_burn(p, circles):
    """True if the meridian ray from the burn (on the axis) to the point p = (x, r) misses every blocking circle
    (cx, cr, radius, arc or None); a ray stops at its first crossing, and a circle the point itself sits on does not hide it."""
    bx, by = BX, 0.0; dx, dy = p[0] - bx, p[1] - by; L = math.hypot(dx, dy); ux, uy = dx / L, dy / L
    for cx, cr, rad, arc in circles:
        fx, fy = bx - cx, by - cr
        b = fx * ux + fy * uy; c = fx * fx + fy * fy - rad * rad; disc = b * b - c
        if disc <= 0:
            continue
        for s_ in (-b - math.sqrt(disc), -b + math.sqrt(disc)):
            if 0 < s_ < L - 1e-3:
                hx, hy = bx + s_ * ux, by + s_ * uy
                if arc is None:
                    return False
                th = ang((hx - cx, hy - cr)); lo, hi = arc
                if (th - lo) % 360 <= (hi - lo):
                    return False
    return True


def arr(segs):
    return (np.array([s_[0] for s_ in segs], float), np.array([s_[1] for s_ in segs], float), np.array([s_[2] for s_ in segs], float))


def gap(sa, sb, chunk=400):
    """Smallest surface gap between two capsule sets."""
    A0, A1, Ar = arr(sa) if not isinstance(sa, tuple) else sa
    B0, B1, Br = arr(sb) if not isinstance(sb, tuple) else sb
    if len(A0) == 0 or len(B0) == 0:
        return 1e9
    g = 1e9
    for i in range(0, len(A0), chunk):
        D = segdist(A0[i:i + chunk], A1[i:i + chunk], B0, B1) - Ar[i:i + chunk, None] - Br[None, :]
        g = min(g, float(D.min()))
    return g


def ring_pts(x, R, n=96, arc=None):
    a0, a1 = arc or (0.0, 360.0)
    m = max(2, int(n * (a1 - a0) / 360))
    return [pol(x, R, a0 + (a1 - a0) * i / m) for i in range(m + 1)]


def on_poly(poly, x):
    """Point of a cage polyline (sorted by decreasing x) at station x, clamped to its ends."""
    if x >= poly[0][0]:
        return poly[0]
    for a, b in zip(poly, poly[1:]):
        if b[0] <= x <= a[0]:
            t = (a[0] - x) / (a[0] - b[0]) if a[0] != b[0] else 0.0
            return tuple(a[i] + t * (b[i] - a[i]) for i in range(3))
    return poly[-1]


def main():
    s = tomllib.loads((ROOT / 'data/wayfarer_3d.toml').read_text())
    parts = ve.parts(s) + ve.refinements(s)
    byname = {p['name']: p for p in parts}
    replaced = sorted(p['name'] for p in parts if '_Armour' in p['name'] or 'Lithium_Supply_Jumper' in p['name']
                      or 'Lithium_Return_Jumper' in p['name'])
    # fixed neighbours as capsules: (name, [(a, b, r)])
    fixed = {}
    for p in parts:
        if p['name'] in replaced:
            continue
        if p['shape'] == 'tube' and p['category'] in ('STRUCTURE', 'CRYOGENIC', 'ELECTRICAL', 'HOT_THERMAL', 'SERVICE'):
            fixed[p['name']] = [(a, b, p['radius']) for a, b in zip(p['points'], p['points'][1:])]
        elif p['shape'] == 'torus' and p['category'] in ('STRUCTURE', 'HOT_THERMAL', 'SHIELDING') and p['name'] != 'VTX_C1_Cryostat':
            pts = ring_pts(p['x'], p['R'], 96, p.get('arc'))
            fixed[p['name']] = [(a, b, p['a']) for a, b in zip(pts, pts[1:])]
    coils = CO['research_geometry']
    for e in coils:                                  # research cryostats replace the approved coil bodies
        pts = ring_pts(e['x'], e['r'], 96)
        fixed[f'RES_{e["name"]}_Cryostat'] = [(a, b, e['cryostat_minor_m']) for a, b in zip(pts, pts[1:])]
    hot_sup = byname['VTX_Lithium_Supply']['points']; hot_ret = byname['VTX_Lithium_Return']['points']
    cryo3 = byname['VTX_Cryo_Feed_3']['points']; cryo7 = byname['VTX_Cryo_Feed_7']['points']
    leads = byname['VTX_Coil_Current_Leads']['points']
    cage = [(x, r) for x, r in ve.cage_points(s)]
    so = ve.service_offsets(s)['feed']
    WX, WR = -10.0, 5.6 + 0.15                         # warm manifold on the thrust collar's outer rim (collar r 3.4-5.6, x -9.2 to -10.6)
    warm_hdr = {az: [pol(WX, WR, az)] + [pol(x, r - so, az) for x, r in cage[1:]] + [pol(-31.6, cage[-1][1] + 0.4 - so, az)]
                for az in P['warm_az']}
    comps = []                                       # dict(name, net, kind, segs=[(a,b,r)], joins=[names], data)

    def add(name, net, kind, segs, joins=(), **data):
        comps.append(dict(name=name, net=net, kind=kind, segs=segs, joins=list(joins), **data))
        return comps[-1]

    def placed(excl=()):
        out = [(nm, ss) for nm, ss in fixed.items() if nm not in excl] + [(c_['name'], c_['segs']) for c_ in comps if c_['segs'] and c_['name'] not in excl]
        return arr([q for _, ss in out for q in ss])

    def clear(segs, F):
        return gap(segs, F) > P['gap']

    for az, poly in warm_hdr.items():
        add(f'INT_Warm_Header_{az:g}', 'warm', 'header', [(a, b, 0.09) for a, b in zip(poly, poly[1:])], ['INT_Warm_Manifold'],
            path=poly, radius=0.09)
    wm_pts = ring_pts(WX, WR, 96)
    add('INT_Warm_Manifold', 'warm', 'plant', [(a, b, 0.12) for a, b in zip(wm_pts, wm_pts[1:])], [], x=WX, R=WR, a=0.12)
    def route(name, net, hdr_name, poly, az, st, ring_tag=None, end=None, joins=(), dry=False):
        c = (st['x'], st['r']); cm = st['cm']
        if ring_tag:
            px, pr, rr, th0, dist = st['ring'][ring_tag]; E_ = pol(px, pr, az); excl_end = {st['ring_comp'][ring_tag]}
        else:
            E_, th0, dist = end, 90.0, cm; excl_end = {f'RES_{st["name"]}_Cryostat'}
        F_end = placed(excl_end | {hdr_name})
        F_hdr = placed({hdr_name})
        xs = [q[0] for q in poly]
        Hs = [on_poly(poly, max(xs) - (max(xs) - min(xs)) * k / 120) for k in range(121)]
        best = None
        for dth in [0, 10, -10, 20, -20, 30, -30, 45, -45, 60, -60, 80, -80, 100, -100, 120, -120, 150, -150]:
            for dd in (0.35, 0.6, 1.0, 1.5, 2.2, 3.0):
                W = xr(c, dist + dd, th0 + dth); Wp = pol(W[0], W[1], az)
                if not clear([(Wp, E_, P['branch_r'])], F_end):
                    continue
                g = gap_rows([(H, Wp, P['branch_r']) for H in Hs], F_hdr)
                for H, gg in zip(Hs, g):
                    L = math.dist(H, Wp) + math.dist(Wp, E_)
                    if gg > P['gap'] and (best is None or L < best[0]):
                        best = (L, H, Wp)
            if best and best[0] < 2.5 * math.dist(on_poly(poly, st['x']), E_):
                break
        if dry:
            return best is not None
        if best is None:
            H = on_poly(poly, st['x']); Wp = E_; routed = False
        else:
            _, H, Wp = best; routed = True
        segs = [(H, Wp, P['branch_r']), (Wp, E_, P['branch_r'])]
        return add(name, net, 'branch' if ring_tag else 'tray', segs, [hdr_name] + ([st['ring_comp'][ring_tag]] if ring_tag else [f'RES_{st["name"]}_Cryostat']) + list(joins),
                   station=st['name'], path=[H, Wp, E_], radius=P['branch_r'], routed=routed)

    stations = []
    # pass 1: lips, rings and feeders, each placed by a small search that keeps them clear of everything placed before
    for e in coils:
        n = e['name']; c = (e['x'], e['r']); cm = e['cryostat_minor_m']
        u = ang((BX - c[0], -c[1]))                 # poloidal direction from the coil centre to the burn
        a_lip = cm + P['lip_gap']; own = {f'RES_{n}_Cryostat'}
        F = placed(own)
        choice = None; fallback = None; anyfit = None
        for half in (88, 84, 80, 75, 70, 65, 60, 55, 50, 45, 40):
            lo, hi = u - half, u + half
            near90 = lambda q: min(abs(q % 360 - 90), 360 - abs(q % 360 - 90))
            for edge, sgn, off_ in sorted(((ed, sg_, o_) for ed, sg_ in ((lo, -1), (hi, 1)) for o_ in P['edge_steps']),
                                          key=lambda es: (es[2], near90(es[0] + es[1] * es[2]))):
                th_sup = (edge + sgn * off_) % 360; th_ret = th_sup        # one twin-bore header: supply and return bores
                segs = {}
                px, pr = xr(c, cm + P['hot_off'], th_sup); pts = ring_pts(px, pr, 96)
                segs['Hot_Header'] = [(a, b, P['hot_r']) for a, b in zip(pts, pts[1:])]
                lipsegs = []
                for k in range(9):
                    px, pr = xr(c, a_lip + P['lip_t'] / 2, lo + (hi - lo) * k / 8); pts = ring_pts(px, pr, 48)
                    lipsegs += [(a, b, P['lip_t'] / 2) for a, b in zip(pts, pts[1:])]
                hp_ = xr(c, cm + P['hot_off'], th_sup)
                shade = not seen_from_burn(hp_, [(c[0], c[1], cm, None), (c[0], c[1], a_lip + P['lip_t'], (lo, hi))])
                if all(clear(sg, F) for sg in segs.values()) and clear(lipsegs, F) and not shade:
                    anyfit = anyfit or (half, lo, hi, edge, sgn, th_sup, th_ret, segs, lipsegs)
                if all(clear(sg, F) for sg in segs.values()) and clear(lipsegs, F) and shade:
                    fallback = fallback or (half, lo, hi, edge, sgn, th_sup, th_ret, segs, lipsegs)
                    ok = True
                    for tag, th, hp, hn in (('Hot_Supply', th_sup, hot_sup, 'VTX_Lithium_Supply'), ('Hot_Return', th_ret, hot_ret, 'VTX_Lithium_Return')):
                        px, pr = xr(c, cm + P['hot_off'], th)
                        probe = dict(name=n, x=e['x'], r=e['r'], cm=cm, ring={tag: (px, pr, P['hot_r'], th, cm + P['hot_off'])}, ring_comp={tag: f'INT_{n}_Hot_Header'})
                        ok = ok and route('probe', 'hot', hn, hp, ang((hp[2][1], hp[2][2])), probe, tag, dry=True)
                    if ok:
                        choice = (half, lo, hi, edge, sgn, th_sup, th_ret, segs, lipsegs); break
            if choice:
                break
        half, lo, hi, edge, sgn, th_sup, th_ret, hsegs, lipsegs = choice or fallback or anyfit
        add(f'INT_{n}_Lip', 'hot', 'lip', lipsegs, [f'INT_{n}_Hot_Feeders'], station=n, a=a_lip, t=P['lip_t'], arc=(lo, hi),
            modules=P['modules'], split_az=LONG_AZ, center=c, half_deg=half)
        ring = {}; rc = {}
        px, pr = xr(c, cm + P['hot_off'], th_sup)
        ring['Hot_Supply'] = ring['Hot_Return'] = (px, pr, P['hot_r'], th_sup, cm + P['hot_off'])
        rc['Hot_Supply'] = rc['Hot_Return'] = f'INT_{n}_Hot_Header'
        add(f'INT_{n}_Hot_Header', 'hot', 'ring', hsegs['Hot_Header'], [], station=n, x=px, R=pr, a=P['hot_r'], twin_bore=True)
        fsegs = []
        ex, er = xr(c, a_lip + P['lip_t'], edge)
        for m in range(P['modules']):
            az = LONG_AZ[m] + 22.5
            fsegs.append((pol(ring['Hot_Supply'][0], ring['Hot_Supply'][1], az), pol(ex, er, az), P['feeder_r']))
        add(f'INT_{n}_Hot_Feeders', 'hot', 'feeder', fsegs, [f'INT_{n}_Hot_Header', f'INT_{n}_Lip'], station=n)
        # cryo and warm rings: the first clear angle away from the hot edge, outside the lip
        def in_lip(th):
            d = (th - lo) % 360
            return d <= (hi - lo) + 12
        for tag, off, rr, net in (('Cryo_Ring', P['cryo_off'], P['cryo_r'], 'cryo'), ('Warm_Ring', P['warm_off'], P['warm_r'], 'warm')):
            F = placed(own)
            used = [ring[k_][3] for k_ in ring]
            order = sorted(range(0, 360, 3), key=lambda q: min(abs(q - 90), 360 - abs(q - 90)))
            if tag == 'Warm_Ring':                   # first choice: stacked outside the cryo ring on the same angle
                off = P['cryo_off'] + P['warm_stack']; order = [ring['Cryo_Ring'][3]] + order; used = [q for q in used if q != ring['Cryo_Ring'][3]]
            found = False
            for want_shade, th in [(ws, q) for ws in (True, False) for q in order]:
                if in_lip(th) or any(min(abs(th - q) % 360, 360 - abs(th - q) % 360) < 10 for q in used):
                    continue
                px, pr = xr(c, cm + off, th); pts = ring_pts(px, pr, 96)
                sg = [(a, b, rr) for a, b in zip(pts, pts[1:])]
                if want_shade and seen_from_burn((px, pr), [(c[0], c[1], cm, None), (c[0], c[1], a_lip + P['lip_t'], (lo, hi))]):
                    continue
                if clear(sg, F):
                    probe = dict(name=n, x=e['x'], r=e['r'], cm=cm, ring={tag: (px, pr, rr, th, cm + off)}, ring_comp={tag: f'INT_{n}_{tag}'})
                    hp = (cryo3 if net == 'cryo' else warm_hdr[P['warm_az'][0]])
                    hn = ('VTX_Cryo_Feed_3' if net == 'cryo' else f'INT_Warm_Header_{P["warm_az"][0]:g}')
                    if route('probe', net, hn, hp, ang((hp[2][1], hp[2][2])) if net == 'cryo' else P['warm_az'][0], probe, tag, dry=True):
                        if tag != 'Warm_Ring':
                            break
                        # the warm ring must still let both cryo branches through
                        add('INT_probe_warm', 'warm', 'ring', sg, [])
                        pc = dict(name=n, x=e['x'], r=e['r'], cm=cm, ring={'Cryo_Ring': ring['Cryo_Ring']}, ring_comp={'Cryo_Ring': rc['Cryo_Ring']})
                        ok = all(route('probe', 'cryo', hn_, hp_, ang((hp_[2][1], hp_[2][2])), pc, 'Cryo_Ring', dry=True)
                                 for hn_, hp_ in (('VTX_Cryo_Feed_3', cryo3), ('VTX_Cryo_Feed_7', cryo7)))
                        comps.pop()
                        if ok:
                            break
            ring[tag] = (px, pr, rr, th, cm + off); rc[tag] = f'INT_{n}_{tag}'
            add(f'INT_{n}_{tag}', net, 'ring', sg, [], station=n, x=px, R=pr, a=rr)
        mir = []
        for th in (lo, hi):
            q = xr(c, a_lip + P['lip_t'], th)
            d = math.hypot(q[0] - BX, q[1]); al = math.atan2(q[1], q[0] - BX)
            mir.append(dict(edge_deg=th, apex_x=BX, d0=d - P['mirror_len'] * 0.7, d1=d + P['mirror_len'] * 0.3,
                            half_angle_deg=math.degrees(al) + (P['mirror_off_deg'] if th == hi else -P['mirror_off_deg'])))
        add(f'INT_{n}_Supermirror', 'hot', 'mirror', [], [f'INT_{n}_Lip'], station=n, strips=mir, facets=P['mirror_facets'])
        stations.append(dict(name=n, x=e['x'], r=e['r'], cm=cm, u_deg=u, lip=(lo, hi), lip_half_deg=half, th_sup=th_sup, th_ret=th_ret,
                             th_cryo=ring['Cryo_Ring'][3], th_warm=ring['Warm_Ring'][3], a_lip=a_lip, ring=ring, ring_comp=rc))

    # pass 2: branches and trays, routed header -> elbow -> ring through the free space (elbow grid round the coil)
    az_of = lambda poly: ang((poly[2][1], poly[2][2]))
    laz = az_of(leads)
    for st in stations:
        n = st['name']
        route(f'INT_{n}_Hot_Supply_Branch', 'hot', 'VTX_Lithium_Supply', hot_sup, az_of(hot_sup), st, 'Hot_Supply')
        route(f'INT_{n}_Hot_Return_Branch', 'hot', 'VTX_Lithium_Return', hot_ret, az_of(hot_ret), st, 'Hot_Return')
        route(f'INT_{n}_Cryo_Branch_A', 'cryo', 'VTX_Cryo_Feed_3', cryo3, az_of(cryo3), st, 'Cryo_Ring')
        route(f'INT_{n}_Cryo_Branch_B', 'cryo', 'VTX_Cryo_Feed_7', cryo7, az_of(cryo7), st, 'Cryo_Ring')
        for az, poly in warm_hdr.items():
            route(f'INT_{n}_Warm_Branch_{az:g}', 'warm', f'INT_Warm_Header_{az:g}', poly, az, st, 'Warm_Ring')
        # tray: cryostat skin at the first clear outward angle to the coil current lead line
        top = None
        Fc = placed({f'RES_{n}_Cryostat'})
        for th in (90, 75, 105, 60, 120, 45, 135, 30, 150):
            q = xr((st['x'], st['r']), st['cm'] + 0.02, th)
            if clear([(pol(q[0], q[1], laz), pol(q[0], q[1], laz), 0.06)], Fc):
                top = pol(q[0], q[1], laz); break
        route(f'INT_{n}_Busbar_Tray', 'electrical', 'VTX_Coil_Current_Leads', leads, laz, st, end=top or pol(*xr((st['x'], st['r']), st['cm'], 90), laz))
    # supports: a run longer than P['span'] gets a bracket from its midpoint to the nearest structural member
    struct = {nm: ss for nm, ss in fixed.items() if nm.startswith(('VTX_Cage', 'VTX_Loop_Seat', 'VTX_C1_Strut', 'VTX_C2_Strut', 'VTX_Coil_Reaction', 'VTX_Shield_Tie'))}
    for c_ in list(comps):
        if c_['kind'] not in ('branch', 'tray'):
            continue
        for a, b, _ in c_['segs']:
            if math.dist(a, b) <= P['span']:
                continue
            m = [(a[i] + b[i]) / 2 for i in range(3)]
            cands = []
            for nm, ss in struct.items():
                for p_, q_, rr in ss:
                    ab = [q_[i] - p_[i] for i in range(3)]; L2 = sum(v * v for v in ab) or 1e-12
                    t = max(0.0, min(1.0, sum((m[i] - p_[i]) * ab[i] for i in range(3)) / L2))
                    pt = [p_[i] + t * ab[i] for i in range(3)]; cands.append((math.dist(m, pt) - rr, nm, pt))
            cands.sort(key=lambda q: q[0]); bestS = None
            for d, nm, pt in cands[:60]:
                if d > 3.2:
                    break
                Fs = placed({c_['name'], nm})
                if clear([(tuple(m), tuple(pt), 0.04)], Fs):
                    bestS = (d, nm, pt); break
            if bestS:
                add(f'{c_["name"]}_Support', 'structure', 'support', [(tuple(m), tuple(bestS[2]), 0.04)], [c_['name'], bestS[1]],
                    station=c_.get('station'), length_m=bestS[0], path=[tuple(m), tuple(bestS[2])], radius=0.04)
                c_.setdefault('supports', []).append(tuple(m))

    # ---------- checks ----------
    names = {c_['name'] for c_ in comps} | set(fixed)
    allsegs = [(c_['name'], c_['segs']) for c_ in comps] + list(fixed.items())
    joined = {(c_['name'], j) for c_ in comps for j in c_['joins']} | {(j, c_['name']) for c_ in comps for j in c_['joins']}
    for c_ in comps:                                  # a part touches its own station's cryostat by design (lip excepted)
        if c_.get('station') and c_['kind'] in ('tray',):
            joined |= {(c_['name'], f'RES_{c_["station"]}_Cryostat'), (f'RES_{c_["station"]}_Cryostat', c_['name'])}
    clashes = []
    A = {nm: arr(ss) for nm, ss in allsegs if ss}
    for c_ in comps:
        if not c_['segs']:
            continue
        mine = A[c_['name']]; lo_ = mine[0].min(0) - 8; hi_ = mine[0].max(0) + 8
        for nm, ss in allsegs:
            if nm == c_['name'] or (c_['name'], nm) in joined or nm not in A:
                continue
            other = A[nm]
            if (other[0].max(0) < lo_).any() or (other[0].min(0) > hi_).any():
                continue
            g = gap(mine, other)
            if g < P['gap']:
                key = tuple(sorted((c_['name'], nm)))
                if not any(tuple(sorted((x['a'], x['b']))) == key for x in clashes):
                    clashes.append(dict(a=c_['name'], b=nm, gap_m=g))
    # connectivity: geometric contact between joined pairs, then a graph walk from each plant
    def touch(n1, n2):
        s1 = next((ss for nm, ss in allsegs if nm == n1), []); s2 = next((ss for nm, ss in allsegs if nm == n2), [])
        if not s1 or not s2:
            return n1 in ('INT_Warm_Plant',) or n2 in ('INT_Warm_Plant',) or n1.endswith('_Supermirror') or n2.endswith('_Supermirror')
        return gap(s1, s2) <= 0.01
    edges = {}
    for c_ in comps:
        for j in c_['joins']:
            if j in names and touch(c_['name'], j):
                edges.setdefault(c_['name'], set()).add(j); edges.setdefault(j, set()).add(c_['name'])
    plants = dict(hot=['VTX_Lithium_Supply', 'VTX_Lithium_Return'], cryo=['VTX_Cryo_Feed_3', 'VTX_Cryo_Feed_7'],
                  warm=['INT_Warm_Manifold'], electrical=['VTX_Coil_Current_Leads'])
    conn = {}
    for net, roots in plants.items():
        seen = set(roots); todo = list(roots)
        while todo:
            q = todo.pop()
            for w in edges.get(q, ()):
                if w not in seen:
                    seen.add(w); todo.append(w)
        mine = [c_['name'] for c_ in comps if c_['net'] == net or (net == 'hot' and c_['kind'] == 'mirror')]
        conn[net] = dict(parts=len(mine), reached=sum(1 for m in mine if m in seen), orphans=[m for m in mine if m not in seen])
    # exposure: which ring and branch points the burn sees directly (every cryostat and lip blocks, meridian rays)
    blockers = [(st_['x'], st_['r'], st_['cm'], None) for st_ in stations] + \
               [(st_['x'], st_['r'], st_['a_lip'] + P['lip_t'], tuple(st_['lip'])) for st_ in stations]
    exposed = []
    for c_ in comps:
        if c_['kind'] in ('ring', 'branch', 'feeder', 'tray', 'support'):
            pts = [(c_['x'], c_['R'])] if c_['kind'] == 'ring' else [(q[0], math.hypot(q[1], q[2])) for a, b, _ in c_['segs'] for q in (a, b)]
            vis = [q for q in pts if seen_from_burn(q, blockers)]
            if vis:
                exposed.append(dict(part=c_['name'], kind=c_['kind'], points_seen=len(vis), of=len(pts)))
    # spans: straight runs between supports (a branch is held at its header, its lead-in elbow and its ring)
    spans = []
    for c_ in comps:
        if c_['kind'] in ('branch', 'tray'):
            sup = c_.get('supports', [])
            for a, b, _ in c_['segs']:
                Lr = math.dist(a, b)
                held = any(dseg_(m, a, b) < 1e-6 for m in sup)
                Lr = Lr / 2 if held else Lr
                spans.append(dict(part=c_['name'], length_m=Lr, ok=Lr <= P['span'], bracket=held))
    long_ = [x for x in spans if not x['ok']]
    out = dict(cls='PROTOTYPE', source='lab/studies/vertex-compact-engine/vertex-pulse/frames.py', P=P, burn_x=BX,
               replaced_approved=replaced, stations=stations,
               components=[{k: v for k, v in c_.items() if k != 'segs'} for c_ in comps],
               checks=dict(clashes=clashes, connectivity=conn, spans_over=long_, n_spans=len(spans),
                           max_span_m=max(x['length_m'] for x in spans), n_parts=len(comps), exposed=exposed,
                           unrouted=[c_['name'] for c_ in comps if c_['kind'] == 'branch' and not c_.get('routed')]))
    (HERE / 'results').mkdir(exist_ok=True)
    (HERE / 'results' / 'frames.json').write_text(json.dumps(out, indent=1))
    print('parts', len(comps), 'clashes', len(clashes)); [print(' ', c_) for c_ in clashes[:40]]
    print('connectivity', conn); print('spans over', len(long_), 'max', round(out['checks']['max_span_m'], 2)); [print(' ', x) for x in long_[:20]]
    print('unrouted', out['checks']['unrouted']); print('exposed', exposed)
    for st in stations:
        print(st['name'], {k: round(v, 1) if isinstance(v, float) else v for k, v in st.items() if k in ('u_deg', 'th_sup', 'th_cryo', 'th_warm', 'lip_half_deg')})


if __name__ == '__main__':
    main()
