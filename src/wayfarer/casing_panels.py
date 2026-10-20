"""S04 slice 1: the aft body casing's panel grammar ([casing_panels], PROTOTYPE judgment, no owner row).

The casing is carried by the primary cage, so its joints follow the cage: a raised strap at every frame station (hull_geometry.frame_stations)
and longitudinal straps on lines that miss the keels, blade roots, masts and trackers. Access panels open the cage-to-skin corridor beside each
keel lane. Parts are strips and plates in the hull's own frame; screen() checks them against the fittings, masts, trackers and crawler track.

    python3 src/wayfarer/casing_panels.py        # counts and screen (JSON)
"""
import math
from pathlib import Path

import hull_geometry as hg


def table(s):
    return s['casing_panels']


def keels(s):
    st = s['structure']; ph = s['prototype']['ring_phase_deg']
    return [math.radians(ph+n*360/st['ring_nodes']) for n in st['sector_pickup_nodes']]


def adiff(a, b):
    return abs((a-b+math.pi) % (2*math.pi)-math.pi)


def stations(s):
    q = table(s); x0, x1 = q['x_range_m']
    return [x for x in hg.frame_stations(s) if x0 <= x <= x1]


def hoop_arcs(s):
    """Angular intervals (rad) of a circumferential strap: the full circle less keel_break_deg either side of each keel."""
    b = math.radians(table(s)['keel_break_deg']); out = []
    ks = sorted(k % (2*math.pi) for k in keels(s))
    for i, k in enumerate(ks):
        nxt = ks[(i+1) % len(ks)]+(2*math.pi if i == len(ks)-1 else 0)
        out.append((k+b, nxt-b))
    return out


def long_lines(s):
    q = table(s); n = int(round(360/q['long_seam_pitch_deg']))
    return [math.radians(q['long_seam_deg0']+k*q['long_seam_pitch_deg']) for k in range(n)]


def access_panels(s):
    """One panel centred in every access_every-th frame bay at each access azimuth: (name, x centre, azimuth, size)."""
    q = table(s); xs = stations(s); out = []
    bays = [(a, b) for a, b in zip(xs, xs[1:]) if b-a >= q['access_m'][0]+2*q['seam_width_m']]
    for i, (a, b) in enumerate(bays[1::q['access_every']]):
        for deg in q['access_deg']:
            out.append(dict(name=f'Casing_Access_{i+1:02d}_{int(deg):03d}', x=(a+b)/2, theta=math.radians(deg), size=tuple(q['access_m'])))
    return out


def collar(s):
    """The forward collar span (x0, x1, radius) from hull_geometry.intervals."""
    _, x0, x1 = next(i for i in hg.intervals(s) if i[0] == 'Hull_Forward_Collar')
    return x0, x1, hg.radius_at(s, (x0+x1)/2)


def collar_keepouts(s):
    """(x0, x1, theta0, theta1) windows on the collar the straps break round: every hull opening on it, and every service fitting's
    exterior aids (exterior_hardware), each grown by collar_opening_margin_m."""
    import exterior_hardware as eh
    import thermal_geometry as tg
    q = table(s); m = q['collar_opening_margin_m']; x0, x1, R = collar(s); out = []
    for w in hg.openings(s, tg.blade_of(s)):
        if w['x1'] >= x0 and w['x0'] <= x1:
            out.append((w['x0']-m, w['x1']+m, w['t0']-m/R, w['t1']+m/R))
    for f in hg.service_fittings(s):
        pts = [f['x']]; ang = [f['theta']]
        for p in eh.service_parts(s):
            if p.get('fitting') != f['name']:
                continue
            for v in ([p['a'], p['b']] if 'a' in p else __import__('human_entry').box_corners(None, p)):
                pts.append(v[0]); ang.append(math.atan2(v[2], v[1]))
        da = max(adiff(a, f['theta']) for a in ang)
        out.append((min(pts)-m, max(pts)+m, f['theta']-da-m/R, f['theta']+da+m/R))
    return out


def blocked(s, x, a, keep=None):
    for x0, x1, t0, t1 in keep if keep is not None else collar_keepouts(s):
        if x0 <= x <= x1 and adiff(a, (t0+t1)/2) <= (t1-t0)/2:
            return True
    return False


def runs(flags):
    """Index runs (i0, i1) of consecutive True flags."""
    out, i0 = [], None
    for i, f in enumerate(flags+[False]):
        if f and i0 is None:
            i0 = i
        elif not f and i0 is not None:
            if i-1 > i0:
                out.append((i0, i-1))
            i0 = None
    return out


def collar_straps(s):
    """Collar strap segments: ('long', a, x_start, x_end) and ('hoop', x, a_start, a_end), each clear of every keep-out (sampled, the
    strap's half-width added)."""
    q = table(s); x0, x1, R = collar(s); e = q['collar_end_inset_m']; w = q['seam_width_m']; keep = collar_keepouts(s); out = []
    n = 160; xs = [x0+e+(x1-x0-2*e)*k/n for k in range(n+1)]
    for a in long_lines(s):
        ok = [not any(blocked(s, x, a+d/R, keep) for d in (-w/2, w/2)) for x in xs]
        out += [('long', a, xs[i], xs[j]) for i, j in runs(ok)]
    x = x0+e
    while x <= x1-e+1e-9:
        m = 240; As = [2*math.pi*k/m for k in range(m+1)]
        ok = [not any(blocked(s, x+d, a, keep) for d in (-w/2, w/2)) for a in As]
        out += [('hoop', x, As[i], As[j]) for i, j in runs(ok)]
        x += q['collar_hoop_pitch_m']
    return out


def screen(s):
    """Rows: the nearest fixed exterior part (masts, terminals, trackers, crawler rails and docks) to any strap or panel; static_gap_m
    applies (fixed parts on stand-offs over a casing joint), the crawler's own swept envelope rides above its rail."""
    import human_entry as he
    import survival_fit
    q = table(s); R = hg.radius_at(s, 0.0); h = q['seam_height_m']; w = q['seam_width_m']
    ext = survival_fit.exterior(s); pts = []
    for e in ext:
        if e.get('shape') == 'rod':
            pts += [(p, e['radius']) for p in e['points']]
        elif 'world_centre' in e:                      # a box: only its corners matter, and only if it comes down to the straps
            cs = he.box_corners(None, e)
            if min(math.hypot(c[1], c[2]) for c in cs)-(R+h) < q['static_gap_m']:
                pts += [(c, 0.0) for c in cs]
        else:
            pts += [(e['a'], e.get('r1', 0.1)), (e['b'], e.get('r1', 0.1))]
    def near(x, a, half_x, half_t):
        """Clear gap from a strap / panel patch (R..R+h) to the nearest sampled exterior part (as spheres)."""
        best = math.inf
        for p, rr in pts:
            rp = math.hypot(p[1], p[2])
            if abs(rp-R) > 2.5:
                continue
            dx = max(abs(p[0]-x)-half_x, 0.0); dt = max(adiff(math.atan2(p[2], p[1]), a)*R-half_t, 0.0); dr = max(rp-(R+h), 0.0)
            best = min(best, math.sqrt(dx*dx+dt*dt+dr*dr)-rr)
        return best
    rows = []
    gl = min(near(x, a, 0.0, w/2) for a in long_lines(s) for x in [q['x_range_m'][0]+k*(q['x_range_m'][1]-q['x_range_m'][0])/400 for k in range(401)])
    gh = min(near(x, a0+(a1-a0)*k/60, w/2, 0.0) for x in stations(s) for a0, a1 in hoop_arcs(s) for k in range(61))
    gp = min(near(p['x'], p['theta'], p['size'][0]/2, p['size'][1]/2) for p in access_panels(s))
    clr = q['static_gap_m']
    for name, g in (('long_seams', gl), ('hoop_seams', gh), ('access_panels', gp)):
        rows.append(dict(name=name, nearest_exterior_part_m=round(g, 3), ok=g >= clr))
    return rows


if __name__ == '__main__':
    import json
    ROOT = Path(__file__).resolve().parents[2]
    from spec import load
    s = load(ROOT)[0]; rows = screen(s)
    print(json.dumps(dict(collar_segments=len(collar_straps(s)), collar_keepouts=len(collar_keepouts(s)), stations=len(stations(s)), long_lines=len(long_lines(s)), access_panels=len(access_panels(s)), rows=rows, ok=all(r['ok'] for r in rows)), indent=1))
