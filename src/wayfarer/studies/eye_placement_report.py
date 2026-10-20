"""FWD-V2 Eye placement study report: summary.md (the screen side by side, with statuses) and one comparison sheet per view (r4 | r16 | r24).
Runs with system python3 (Pillow) after eye_placement_study.py has rendered into the run directory.

    python3 src/wayfarer/studies/eye_placement_report.py runs/<stamp>-fwd-eye
"""
from pathlib import Path
import json
import sys
from PIL import Image, ImageDraw

run = Path(sys.argv[1]); radii = sorted((json.loads((d/'screen.json').read_text()) for d in run.glob('r*') if (d/'screen.json').exists()), key=lambda v: v['radius_m'])
state = 'defense_engaged'
views = sorted({p.stem.removeprefix('preview_') for p in run.glob(f'r*/{state}/preview_*.png')})
for view in views:
    tiles = [Image.open(run/f"r{v['radius_m']:g}"/state/f'preview_{view}.png') for v in radii]
    w, h = tiles[0].size; sheet = Image.new('RGB', (w*len(tiles), h+28), (14, 19, 26)); draw = ImageDraw.Draw(sheet)
    for i, (v, tile) in enumerate(zip(radii, tiles)):
        sheet.paste(tile, (i*w, 28)); draw.text((i*w+8, 8), f"r {v['radius_m']:g} m - {v['status']}", fill=(200, 225, 235))
    sheet.save(run/f'compare_{view}.png')

row = lambda label, f: f"| {label} | "+' | '.join(str(f(v)) for v in radii)+' |'
S = lambda v: v['structure']; O = lambda v: v['optics']; D = lambda v, k: v['shutter']['directions'][k]
lines = ['# FWD-V2 Eye placement study (r4 / r16 / r24)', '',
         'In-memory study on the saved vehicle; no source value or asset changed. Statuses: r4 WORKING (S&E 14!A28), r16/r24 STUDY (Eye 45 FD-E01/E02). '
         'Truss, posts, Crown and shutter leaf are PROTOTYPE layout, so clashes are layout findings. Margins in m (negative = clash), angles in degrees.', '',
         '| | '+' | '.join(f"r {v['radius_m']:g} m" for v in radii)+' |', '|---|'+'---|'*len(radii),
         row('status', lambda v: v['status']),
         row('F1 centre (y, z)', lambda v: f"({v['facets'][0]['y']}, {v['facets'][0]['z']})"),
         row('adjacent / diagonal separation', lambda v: f"{v['separation']['adjacent_m']} / {v['separation']['diagonal_m']}"),
         row('B_array (WORKING, unchanged)', lambda v: v['separation']['b_array_m']),
         row('face zone', lambda v: v['face']['zone']),
         row('well lip slope across the well', lambda v: v['face']['lip_slope_m']),
         row('Lance margin', lambda v: S(v)['lance_m']),
         row('truss spoke margin', lambda v: S(v)['spoke_m']),
         row('truss ring margin (rings crossed)', lambda v: f"{S(v)['truss_ring_m']} ({', '.join(f'{x:g}' for x in S(v)['truss_rings_crossed']) or '-'})"),
         row('layer post margin (posts crossed)', lambda v: f"{S(v)['layer_post_m']} ({len(S(v)['layer_posts_crossed'])})"),
         row('Crown housing margin', lambda v: S(v)['crown_housing_m']),
         row('facet stack / skin+truss depth', lambda v: f"{S(v)['facet_stack_m']} / {S(v)['skin_plus_truss_depth_m']}"),
         row('support', lambda v: S(v)['support']),
         row('service access', lambda v: S(v)['service']),
         row('damage display cells overlapped', lambda v: S(v)['damage_cells_overlapped']),
         row('well field: unvignetted / cut-off', lambda v: f"{O(v)['well_unvignetted_deg']} / {O(v)['well_cutoff_deg']}"),
         row('Lance seen from boresight at', lambda v: f"{O(v)['lance_clear_deg']} ({'inside clear field' if O(v)['lance_inside_unvignetted'] else 'vignetted zone' if O(v)['lance_inside_well_field'] else 'outside'})"),
         row('engaged Crown carriage seen at', lambda v: O(v)['crown_engaged_deg']),
         row('EYE FOV', lambda v: O(v)['fov']),
         *[row(f'shutter {k}: face / pocket margin', lambda v, k=k: f"{D(v, k)['face_margin_m']}{' fold' if D(v, k)['face_crosses_fold'] else ''} / {D(v, k)['pocket_margin_m']}{' shell' if D(v, k)['pocket_crosses_body_shell'] else ''}")
           for k in ('radial_out', 'radial_in', 'tangential')],
         row('mass', lambda v: v['mass']), '',
         f"Port: {radii[0]['optics']['port_note']}", '',
         'Comparison sheets: '+', '.join(f'`compare_{v}.png`' for v in views)]
(run/'summary.md').write_text('\n'.join(lines)+'\n')
print(run/'summary.md')
