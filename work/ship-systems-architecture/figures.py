"""Model-derived SVG figures from results/survey.json (pure). Writes results/fig_*.svg (inline-able, themed by CSS variables)."""
import json
from pathlib import Path

from districts import DISTRICTS, table

R = Path(__file__).resolve().parent / 'results'
COL = {'O': 'var(--occ)', 'R': 'var(--res)', 'D': 'var(--dry)', 'F': 'var(--free)', 'U': 'var(--use)'}
LBL = {'O': 'occupied by built geometry (+0.3 m)', 'R': 'reserved (spine/trunk, keel lanes, skin standoff)',
       'D': 'dry-store modules (contents unallocated)', 'F': 'free, fragmented', 'U': 'usable block (2 x 2 m clear)'}


def longitudinal():
    d = json.loads((R / 'survey.json').read_text())
    S = d['sections']; x0, x1 = S[0]['x'], S[-1]['x']
    W, H, pad = 980, 230, 30
    sx = lambda x: pad + (x - x0) / (x1 - x0) * (W - 2*pad)
    out = [f'<svg viewBox="0 0 {W} {H+70}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Longitudinal occupancy of the casing interior">']
    for s in S:
        tot = sum(s['counts'].get(c, 0) for c in 'OFRUD') or 1
        y = 20
        for c in 'ODRFU':
            h = s['counts'].get(c, 0)/tot*H
            out.append(f'<rect x="{sx(s["x"]):.1f}" y="{y:.1f}" width="{(W-2*pad)/len(S)+0.4:.2f}" height="{h:.1f}" fill="{COL[c]}"/>')
            y += h
    for i, n, a, b in DISTRICTS:
        out.append(f'<line x1="{sx(a):.1f}" y1="14" x2="{sx(a):.1f}" y2="{H+24}" stroke="var(--ink)" stroke-width="1"/>')
        out.append(f'<text x="{(sx(a)+sx(b))/2:.1f}" y="12" font-size="11" text-anchor="middle" fill="var(--ink)">{i}</text>')
    for xm in range(-125, 150, 25):
        out.append(f'<text x="{sx(xm):.1f}" y="{H+38}" font-size="10" text-anchor="middle" fill="var(--muted)">{xm}</text>')
    out.append(f'<text x="{W/2}" y="{H+54}" font-size="10" text-anchor="middle" fill="var(--muted)">X (m), aft ← → bow; share of the casing cross-section at each station</text>')
    out.append('</svg>')
    (R / 'fig_longitudinal.svg').write_text('\n'.join(out))


def sections(xs=(-120.75, -100.75, -70.75, -10.75, 35.25, 70.25, 120.25)):
    d = json.loads((R / 'survey.json').read_text())
    pick = [min(d['sections'], key=lambda s: abs(s['x']-x)) for x in xs]
    cell, gap = 5, 16
    widths = [len(s['grid'][0])*cell for s in pick]
    W = sum(widths) + gap*(len(pick)+1); Hh = max(len(s['grid']) for s in pick)*cell + 40
    out = [f'<svg viewBox="0 0 {W} {Hh}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Casing cross-sections from the built model">']
    ox = gap
    for s, w in zip(pick, widths):
        for j, row in enumerate(s['grid']):
            for i, c in enumerate(row):
                if c in COL:
                    out.append(f'<rect x="{ox+i*cell}" y="{10+j*cell}" width="{cell}" height="{cell}" fill="{COL[c]}"/>')
        out.append(f'<text x="{ox+w/2}" y="{Hh-12}" font-size="11" text-anchor="middle" fill="var(--ink)">X {s["x"]:.0f}</text>')
        ox += w + gap
    out.append('</svg>')
    (R / 'fig_sections.svg').write_text('\n'.join(out))


if __name__ == '__main__':
    longitudinal(); sections(); print('ok', [p.name for p in R.glob('fig_*.svg')])
