"""Two v4 figures (SVG -> PNG with Chromium): the pulsed architecture to scale beside the ship, and the mission comparison."""
import json, math, subprocess
from pathlib import Path
HERE = Path(__file__).resolve().parent; R = json.loads((HERE/'results/v4.json').read_text())
D = R['pulsed']['designs']; rows = R['comparison']['rows']
COL = {'prop': '#DB29C2', 'hot': '#DB1F1A', 'h2': '#2452EB', 'struct': '#8F8F94', 'esc': '#B8B8A0', 'power': '#45389E'}

def svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="DejaVu Sans, Arial">'
            f'<rect width="{w}" height="{h}" fill="#FAFAF7"/><text x="20" y="34" font-size="22" font-weight="700">{title}</text>{body}</svg>')

def scale_fig():
    b = []; W = 1400; y = 60
    for case in ('heavy_ion_beam/optimistic', 'heavy_ion_beam/central'):
        d = D[case]['best']; Rs = d['standoff_m']
        ext = 289.5+150+Rs*1.9; s = (W-80)/ext; h = 2*Rs*s+110
        y0 = y+60+Rs*s; x_ship0 = 40; x_aft = x_ship0+289.5*s; bx = x_aft+(Rs+150)*s
        b.append(f'<text x="20" y="{y+24}" font-size="16" font-weight="700">{case.split("/")[1]} case: pulse {D[case]["pulse"]["yield_t_TNT"]:.0f} t TNT every '
                 f'{1/d["rep_Hz"]:.2f} s, stand-off {Rs:.0f} m, {d["P_fus_TW"]:.1f} TW fusion, drive {d["drive_t"]:,.0f} t</text>')
        b.append(f'<rect x="{x_ship0}" y="{y0-max(7.2*s,2)}" width="{289.5*s}" height="{max(14.4*s,4)}" fill="{COL["struct"]}"/>')
        b.append(f'<rect x="{x_aft-90*s}" y="{y0-37*s}" width="{44.5*s}" height="{74*s}" fill="{COL["hot"]}" opacity="0.6"/>')
        b.append(f'<text x="{x_ship0}" y="{y0-max(37*s,8)-8}" font-size="12">Wayfarer 289.5 m (radiator blades red)</text>')
        b.append(f'<circle cx="{bx}" cy="{y0}" r="{0.8*Rs*s}" fill="{COL["prop"]}" opacity="0.07" stroke="{COL["prop"]}" stroke-dasharray="5,4"/>')
        for dx in (-0.5, 0.0, 0.5):
            b.append(f'<ellipse cx="{bx+dx*Rs*s}" cy="{y0}" rx="5" ry="{Rs*s*math.sqrt(1-dx**2*0.5)}" fill="none" stroke="{COL["prop"]}" stroke-width="4"/>')
        b.append(f'<path d="M{bx} {y0} L{bx+Rs*s*0.9} {y0-Rs*s*0.45} L{bx+Rs*s*0.9} {y0+Rs*s*0.45} z" fill="{COL["h2"]}" opacity="0.15"/>')
        b.append(f'<circle cx="{bx}" cy="{y0}" r="5" fill="{COL["prop"]}"/><text x="{bx+10}" y="{y0+4}" font-size="12">burn point</text>')
        b.append(f'<text x="{bx+Rs*s*0.55}" y="{y0+Rs*s*0.5}" font-size="12">exhaust</text>')
        bar = 100 if Rs < 500 else 500
        b.append(f'<line x1="40" y1="{y0+Rs*s+20}" x2="{40+bar*s}" y2="{y0+Rs*s+20}" stroke="#000" stroke-width="3"/><text x="40" y="{y0+Rs*s+38}" font-size="12">{bar} m</text>')
        b.append(f'<text x="{bx-Rs*s*0.5}" y="{y0+Rs*s+38}" font-size="12">3 Fiji-amplified superconducting loops, r {Rs:.0f} m; dashed: plasma stopping sphere</text>')
        y += h+40
    b.append(f'<text x="20" y="{y}" font-size="13">Stand-off = escaping X-ray fluence per pulse below 4 J/cm2 (optimistic) or 1 J/cm2 (tungsten melt). Driver beams arrive from the stand-off.</text>')
    return svg(W, int(y+20), ''.join(b), 'Pulsed Fiji Drive (IFD-P) to scale beside the ship')


def compare_fig():
    items = [('Today (canon, eta 0.8, burnup 0.8, recovery 0.95)', rows['today (canon WORKING, eta 0.8, burnup 0.8, recovery 0.95)'], '#777'),
             ('IFD-1 continuous, v4 recheck', rows['IFD-1 continuous (v4 recheck)'], COL['hot']),
             ('Pulsed, heavy-ion driver, optimistic', rows['pulsed heavy_ion_beam/optimistic'], COL['prop']),
             ('Pulsed, heavy-ion driver, central', rows['pulsed heavy_ion_beam/central'], COL['prop']),
             ('Pulsed, laser driver, central', rows['pulsed standoff_laser/central'], COL['prop'])]
    b = []; x0 = 470; W = 1400
    lo, hi = -2, 4
    def X(v): return x0+(math.log10(v)-lo)/(hi-lo)*(W-x0-60)
    for e in range(lo, hi+1):
        b.append(f'<line x1="{X(10**e)}" y1="70" x2="{X(10**e)}" y2="{80+len(items)*70}" stroke="#ddd"/><text x="{X(10**e)-14}" y="66" font-size="12">1e{e} y</text>')
    for i, (lab, r, c) in enumerate(items):
        y = 90+i*70; t = r['mission_burn_years']
        b.append(f'<text x="20" y="{y+18}" font-size="14" font-weight="700">{lab}</text>')
        b.append(f'<text x="20" y="{y+38}" font-size="12">{r["P_fus_TW"]:.3g} TW fusion, departure {r["departure_t"]:,.0f} t, start {r["a0_g"]*1e3:.3g} mg</text>')
        b.append(f'<rect x="{x0}" y="{y}" width="{X(t)-x0}" height="34" fill="{c}" opacity="0.8"/><text x="{X(t)+6}" y="{y+22}" font-size="13">{t:,.3g} y of burning</text>')
    b.append(f'<text x="20" y="{110+len(items)*70}" font-size="13">Same mission: four 0.016 c burns at ve 19,201 km/s, complete ship mass, drive heat in the 10.8 GW 1800 K share; driver waste heat gets its own 350-400 K radiators (counted in mass).</text>')
    return svg(W, 140+len(items)*70, ''.join(b), 'Total burn time for the same mission (log scale)')

out = HERE/'diagrams'
for n, s in (('pulsed_to_scale', scale_fig()), ('mission_comparison', compare_fig())):
    (out/f'{n}.svg').write_text(s)
print('ok')
