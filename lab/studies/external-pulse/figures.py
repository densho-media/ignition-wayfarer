"""EXT-01 figures (stdlib SVG): the assumption ladder and the exhaust-velocity comparison."""
import math
from pathlib import Path

FIG = Path(__file__).resolve().parent/'figures'
G0 = 9.80665
INK, MUTED, GRID, BG = '#1f2328', '#57606a', '#d0d7de', '#ffffff'
COL = {'A': '#b35c1e', 'B': '#1f6feb', 'C': '#8250df'}
STEPS = ['all brackets (incl. UNVERIFIED)', 'no photon conversion', 'isotropic pulse', 'leak >= 1 % (Vertex 1.4)']


def _svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-label="{title}" font-family="system-ui, sans-serif" font-size="12">'
            f'<rect width="{w}" height="{h}" fill="{BG}"/>{body}</svg>\n')


def _x(v, lo, hi, x0, x1):
    return x0+(math.log10(v)-math.log10(lo))/(math.log10(hi)-math.log10(lo))*(x1-x0)


def ladder(R):
    lo, hi = 0.3, 1e4; x0, x1 = 250, 760; rows = []
    for c in ('A', 'B', 'C'):
        for i, st in enumerate(R['concepts'][c]['summary']['ladder']):
            rows.append((c, STEPS[i], st['best_closure']))
    h = 70+len(rows)*22+40; b = []
    b.append(f'<text x="16" y="24" font-size="14" font-weight="600" fill="{INK}">Best closure factor per concept as assumptions are removed</text>')
    b.append(f'<text x="16" y="42" fill="{MUTED}">Largest gate ratio of the best case (1 = closes; log scale). Gates: departure mass, radiator heat, debris speed, fatigue, schedule.</text>')
    y0 = 60
    for t in (1, 10, 100, 1000, 10000):
        x = _x(t, lo, hi, x0, x1)
        b.append(f'<line x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" y2="{y0+len(rows)*22}" stroke="{GRID}"/>')
        b.append(f'<text x="{x:.1f}" y="{y0+len(rows)*22+16}" text-anchor="middle" fill="{MUTED}">{t:g}</text>')
    x1v = _x(1, lo, hi, x0, x1)
    b.append(f'<line x1="{x1v:.1f}" y1="{y0-4}" x2="{x1v:.1f}" y2="{y0+len(rows)*22}" stroke="{INK}" stroke-width="1.5"/>')
    for i, (c, st, v) in enumerate(rows):
        y = y0+i*22
        b.append(f'<text x="16" y="{y+15}" fill="{INK}">{c}: {st}</text>')
        if v is None or not math.isfinite(v):
            b.append(f'<text x="{x0+4}" y="{y+15}" fill="{MUTED}">no solution (mass ratio beyond the tank-growth limit)</text>')
            continue
        xe = _x(min(max(v, lo), hi), lo, hi, x0, x1)
        b.append(f'<rect x="{x0}" y="{y+4}" width="{max(xe-x0, 1):.1f}" height="14" fill="{COL[c]}" rx="2"/>')
        b.append(f'<text x="{min(xe+6, x1-40):.1f}" y="{y+15}" fill="{INK}">{v:.3g}</text>')
    return _svg(780, h, ''.join(b), 'EXT-01 assumption ladder')


def velocities(R):
    lo, hi = 1e4, 1e8; x0, x1 = 250, 760
    req = R['requirement']; ref = R['reference']
    rows = [('Needed: 4.6 kt departure', req['v_eff_needed']['1.0'], INK), ('Tank-growth limit (any departure)', req['tank_growth_limit_v_eff'], MUTED),
            ('Vertex 1.5 design jet (thermally blocked)', ref['ve_ref'], '#cf222e')]
    for c in ('A', 'B', 'C'):
        L = R['concepts'][c]['summary']['ladder']
        rows.append((f'{c}: fastest, all brackets', L[0]['v_eff_max'], COL[c]))
        rows.append((f'{c}: fastest, isotropic bare pulse', L[2]['v_eff_max'], COL[c]))
    for p in R['precedents']:
        if p['isp_s']:
            rows.append((f"{p['id']} (claim, Isp {p['isp_s'][0]:,.0f}-{p['isp_s'][-1]:,.0f} s)", p['isp_s'][-1]*G0, '#6e7781'))
    h = 70+len(rows)*22+40; b = []
    b.append(f'<text x="16" y="24" font-size="14" font-weight="600" fill="{INK}">Effective exhaust velocity: needed, modelled, claimed</text>')
    b.append(f'<text x="16" y="42" fill="{MUTED}">km/s, log scale. Modelled bars are the fastest case of each search step, whether or not it closes on heat or mass.</text>')
    y0 = 60
    for t in (1e4, 1e5, 1e6, 1e7, 1e8):
        x = _x(t, lo, hi, x0, x1)
        b.append(f'<line x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" y2="{y0+len(rows)*22}" stroke="{GRID}"/>')
        b.append(f'<text x="{x:.1f}" y="{y0+len(rows)*22+16}" text-anchor="middle" fill="{MUTED}">{t/1e3:g}</text>')
    xr = _x(req['v_eff_needed']['1.0'], lo, hi, x0, x1)
    b.append(f'<line x1="{xr:.1f}" y1="{y0-4}" x2="{xr:.1f}" y2="{y0+len(rows)*22}" stroke="{INK}" stroke-width="1.5" stroke-dasharray="4 3"/>')
    for i, (lab, v, col) in enumerate(rows):
        y = y0+i*22
        b.append(f'<text x="16" y="{y+15}" fill="{INK}">{lab}</text>')
        if not v:
            continue
        xe = _x(min(max(v, lo), hi), lo, hi, x0, x1)
        b.append(f'<rect x="{x0}" y="{y+4}" width="{max(xe-x0, 1):.1f}" height="14" fill="{col}" rx="2"/>')
        b.append(f'<text x="{min(xe+6, x1-50):.1f}" y="{y+15}" fill="{INK}">{v/1e3:,.0f}</text>')
    return _svg(780, h, ''.join(b), 'EXT-01 exhaust velocities')


def write(R):
    FIG.mkdir(exist_ok=True)
    (FIG/'ext01_ladder.svg').write_text(ladder(R))
    (FIG/'ext01_velocity.svg').write_text(velocities(R))
