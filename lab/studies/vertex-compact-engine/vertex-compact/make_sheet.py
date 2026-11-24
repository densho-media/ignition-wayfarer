#!/usr/bin/env python3
"""Comparison sheet of the compact variants (renders + results/compact.json). Needs Pillow. Writes renders/compact_comparison_sheet.png."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / 'results' / 'compact.json').read_text())['variants']
F = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
fb, fm, fs = (ImageFont.truetype(F.replace('.ttf', '-Bold.ttf'), 34), ImageFont.truetype(F, 24), ImageFont.truetype(F, 20))
W, H = 1200, 675
img = Image.new('RGB', (2 * W + 60, 2 * H + 640), (16, 20, 28))
d = ImageDraw.Draw(img)
d.text((30, 20), 'Compact Wayfarer engine variants C1-C4: WORK, not canon. None closes: the engine heat is 10,000x the canon budget.', font=fb, fill=(255, 210, 210))
caps = dict(C1='C1 as built (approved cluster)', C2='C2 cluster 30 m aft', C3='C3 +6 m nozzle, ribbon loops, field x4, big shields',
            C4='C4 = C3 + braking package (screens, armour)')
files = dict(C1='compact_aft_cluster.png', C2='compact_aft_C2.png', C3='compact_aft_C3.png', C4='compact_aft_C4.png')
for i, k in enumerate(('C1', 'C2', 'C3', 'C4')):
    x, y = 30 + (i % 2) * (W + 0), 80 + (i // 2) * (H + 50)
    im = Image.open(HERE / 'renders' / files[k]).convert('RGB').resize((W - 10, H - 10))
    img.paste(im, (x, y + 40)); d.text((x, y + 6), caps[k], font=fm, fill=(230, 235, 255))
rows = [('', 'C1', 'C2', 'C3', 'C4'),
        ('Burn x (m)', *[f"{R[k]['x_burn']:.0f}" if 'x_burn' in R[k] else '' for k in 'C1 C2 C3 C4'.split()]),
        ('Engine piped heat / 10.8 GW budget', *[f"{R[k]['piped_over_budget']:,.0f} x" for k in 'C1 C2 C3 C4'.split()]),
        ('Direct burn on the ship (GW, limit 0.1)', *[f"{R[k]['ship_lit_W'] / 1e9:,.1f}" for k in 'C1 C2 C3 C4'.split()]),
        ('Axial efficiency (canon ~0.95)', *[f"{R[k]['eta']:.2f}" for k in 'C1 C2 C3 C4'.split()]),
        ('Winding fluence / limit', *[f"{R[k]['winding_over_limit']:,.0f} x" for k in 'C1 C2 C3 C4'.split()]),
        ('Braking dust protection NOM / JUST (t)', *[f"{R[k]['dust_nominal_t']:,.0f} / {R[k]['dust_justified_t']:,.0f}" for k in 'C1 C2 C3 C4'.split()]),
        ('Departure mass if heat closed (t)', *[f"{R[k]['departure_if_heat_closed_t']:,.0f}" for k in 'C1 C2 C3 C4'.split()])]
y0 = 80 + 2 * (H + 50) + 20
cw = [760, 380, 380, 380, 380]
for r, row in enumerate(rows):
    x = 30
    for c, cell in enumerate(row):
        col = (255, 255, 255) if r == 0 or c == 0 else ((255, 150, 150) if r in (2, 3, 5) else (220, 225, 235))
        d.text((x, y0 + r * 44), cell, font=fm if r else fb, fill=col); x += cw[c]
d.text((30, y0 + len(rows) * 44 + 20), 'Red rows fail by orders of magnitude in every variant. C4 is recommended as the compact working direction, not as a solution. '
       'Quick run, 48 directions x 4 species; numbers from lab/studies/vertex-compact-engine/vertex-compact/results/compact.json.', font=fs, fill=(190, 195, 210))
img.save(HERE / 'renders' / 'compact_comparison_sheet.png')
print('ok')
