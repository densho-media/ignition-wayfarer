"""FWD-V2 alternate-truss plan sheet (Eye 45 FD-A01/A02, FD-A06 evidence): the forward truss seen from ahead (+X toward the viewer, +Y right,
+Z up) for r 4 / 16 / 24, whole disc and the F1 well close up, drawn exactly from forward_shield and eye_truss_study. Grey = production
members kept; red = production members the alternate replaces; blue = alternate members and posts; orange = raceways; green = window-cartridge
service path; dark = wells, dashed = outer ports (radius 2.25 m); pale = open eyelid leaves. STUDY, PROTOTYPE sizes; mass and rating OPEN.
Writes plan_truss.png and alternate.md into the run directory.

    python3 src/wayfarer/studies/eye_truss_plan.py runs/<stamp>-fwd-r16-alt
"""
from pathlib import Path
import json
import math
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw
from spec import load
import eye_placement as ep
import eye_truss_study as ets
import forward_shield as fsh

PANEL = 620
BG, GREY, RED, BLUE, ORANGE, GREEN, DARK, PALE, TEXT = (14, 19, 26), (95, 105, 115), (225, 60, 50), (70, 140, 245), (245, 150, 40), (60, 210, 100), (5, 8, 12), (150, 170, 185), (210, 225, 235)


def panel(v, alt, centre, half, title):
    img = Image.new('RGB', (PANEL, PANEL), BG); d = ImageDraw.Draw(img); k = PANEL/(2*half)
    P = lambda y, z: (PANEL/2+(y-centre[0])*k, PANEL/2-(z-centre[1])*k)
    W = lambda r: max(1, int(round(2*r*k)))
    def poly(pts, col, r):
        d.line([P(p[1], p[2]) for p in pts], fill=col, width=W(r))
    def circle(y, z, r, col, width=1, fill=None):
        (x0, y0), (x1, y1) = P(y-r, z+r), P(y+r, z-r); d.ellipse([x0, y0, x1, y1], outline=col, width=width, fill=fill)
    t = fsh.truss(v); gone = set(alt['removed']) if alt else set(); p = fsh.prototype(v)
    circle(0, 0, fsh.shield_radius(v), GREY, 2); circle(0, 0, p['crown_housing_inner_radius_m'], GREY, 1)
    for b in fsh.crown(v)['bays']:                                                   # Crown bay axes (unchanged)
        a = b['azimuth']; d.line([P(41*math.cos(a), 41*math.sin(a)), P(45*math.cos(a), 45*math.sin(a))], fill=TEXT, width=2)
    x0, x1, ro, ri = t['hub_ring']; circle(0, 0, (ro+ri)/2, GREY, W(ro-ri))
    for sp in t['spokes']:
        for lab, pts in sp['members']:
            if lab == 'aft':
                poly(pts, RED if f"Truss_Spoke_{sp['index']:02}_{lab}" in gone else GREY, t['member_radius'])
    for kk, r in enumerate(t['rings']):
        circle(0, 0, r['radius'], RED if f'Truss_Ring_{kk+1:02}' in gone else GREY, W(t['member_radius']))
    for x in fsh.sector_ties(v):
        poly([x['a'], x['b']], RED if x['name'] in gone else GREY, x['radius'])
    for q in fsh.disruptor_posts(v):
        circle(q['r']*math.cos(q['azimuth']), q['r']*math.sin(q['azimuth']), q['radius']*3, RED if q['name'] in gone else GREY, 1, RED if q['name'] in gone else GREY)
    port = fsh.eye_port_radius(v, fsh.disruptor_layers(v)[0])
    for e in fsh.eye_shutters(v):
        ur = (math.cos(e['azimuth']), math.sin(e['azimuth'])); ut = (-ur[1], ur[0])
        for leaf in e['leaves']:
            c = (e['y']+leaf['sign']*e['open_t']*ut[0], e['z']+leaf['sign']*e['open_t']*ut[1])
            corners = [(c[0]+sr*e['radial']/2*ur[0]+st*e['tangential']/2*ut[0], c[1]+sr*e['radial']/2*ur[1]+st*e['tangential']/2*ut[1]) for sr, st in ((1, 1), (1, -1), (-1, -1), (-1, 1))]
            d.polygon([P(*q) for q in corners], outline=PALE)
    for w in fsh.wells(v):
        circle(w['y'], w['z'], w['radius'], DARK, 1, DARK)
        for i in range(0, 360, 12):                                                   # dashed outer port
            a0, a1 = math.radians(i), math.radians(i+6)
            d.line([P(w['y']+port*math.cos(a0), w['z']+port*math.sin(a0)), P(w['y']+port*math.cos(a1), w['z']+port*math.sin(a1))], fill=PALE, width=1)
    if alt:
        for o in alt['members']:
            col = ORANGE if o['role'] == 'raceway' else BLUE
            if o.get('plate'):
                circle(o['pts'][0][1], o['pts'][0][2], o['radius'], BLUE, 2)
            elif o['role'] == 'post':
                circle(o['pts'][0][1], o['pts'][0][2], o['radius']*3, BLUE, 1, BLUE)
            elif o['role'] == 'spoke' and not o['name'].endswith('_aft'):
                continue
            elif o['role'] == 'branch' and not o['name'].endswith('_aft'):
                continue
            else:
                poly(o['pts'], col, o['radius'])
        obstacles = alt['members']+ets._kept(v, alt)
        for w in fsh.wells(v):
            if not fsh.in_hub(v, w):
                acc = ets.cartridge_access(v, alt, w, obstacles)
                poly(acc['path'], GREEN, 0.08); (_, y, z) = acc['path'][-1]; circle(y, z, acc['window_radius_m'], GREEN, 2)
    d.text((8, 8), title, fill=TEXT)
    d.text((8, PANEL-18), f'{2*half:g} m across | seen from ahead, +Y right, +Z up', fill=PALE)
    return img


def main(run):
    s, *_ = load()
    rows, md = [], ['# FWD-V2 alternate truss (Eye 45 FD-A01/A02, S&E 50 AG-A01/A02) — STUDY, in memory', '',
                    'r4 and B_array = 8 m stay WORKING (FD-A06). Sizes are PROTOTYPE; mass, FEA, stiffness, optical stability and impact rating are OPEN.', '']
    for r in ep.RADII:
        v = ep.variant(s, r); outer = not all(fsh.in_hub(v, w) for w in fsh.wells(v)); alt = ets.alternate(v) if outer else None
        sc = ets.screen(s, r); w1 = fsh.wells(v)[0]
        label = f"r {r:g} m · {ep.STATUS[r]}" + (' · ALTERNATE TRUSS' if outer else ' · production truss')
        rows.append([panel(v, alt, (0, 0), 47, label), panel(v, alt, (w1['y'], w1['z']), 8.5, f'{label} · F1 close up')])
        b = fsh.eye_baselines(v)
        md += [f'## r {r:g} m — {ep.STATUS[r]}', '',
               f"Geometric baselines (DERIVED, FD-A03): opposite {b['geometric_opposite_m']['value']:.3f} m, adjacent {b['geometric_adjacent_m']['value']:.3f} m; "
               f"B_array {b['b_array']['value']:g} m (WORKING, r4 calibration only); coherent baseline OPEN.", '']
        if not sc['alternate']:
            md += ['Wells inside the hub: the production truss is unchanged.', '']
            continue
        c = sc['clearances']; k = sc['continuity']; L = sc['lengths_m']
        md += [f"- Collar radius {sc['collar_radius_m']} m; rings rerouted through the collars: {', '.join(f'{x:g} m' for x in sc['rings_rerouted_m'])}; "
               f"{len(sc['replaced'])} production members replaced, {sc['added_members']} alternate members added.",
               f"- Clearances (shared {c['shared_clearance_m']} m): wells and facet stacks {c['well_and_stack_m']} m; relocated posts outside the 2.25 m port "
               f"{c['posts_outside_port_m']} m; posts to the open eyelids {c['posts_to_open_eyelids_m']} m; aft-face raceways to the structure {c['raceway_to_structure_m']} m.",
               f"- Continuity: one connected structure {k['connected']}; spoke pattern unrotated {k['spoke_pattern_unrotated']}; Crown bays unchanged; "
               f"no member deleted without replacement.",
               f"- Lengths (m, linear mass OPEN): replaced {L['replaced']}; added {L['added_by_role']}; net structure {L['net_structure_added']:+}.",
               f"- Window cartridge: well-wall hatch at {sorted({a['best_phi_deg'] for a in sc['cartridge_access']})} deg, slide {sc['cartridge_access'][0]['slide_m']} m "
               f"then aft, margin {min(a['margin_m'] for a in sc['cartridge_access'])} m; clear directions {sc['cartridge_access'][0]['clear_directions_deg']}. "
               f"{sc['cartridge_access'][0]['hatch']}; {sc['cartridge_access'][0]['crawler']}.",
               f"- OPEN: {', '.join(sc['open'])}.", '']
    sheet = Image.new('RGB', (2*PANEL, len(rows)*PANEL), BG)
    for i, (a, b) in enumerate(rows):
        sheet.paste(a, (0, i*PANEL)); sheet.paste(b, (PANEL, i*PANEL))
    sheet.save(run/'plan_truss.png')
    (run/'alternate.md').write_text('\n'.join(md)+'\n')


if __name__ == '__main__':
    main(Path(sys.argv[1]))
