"""FWD-V2 Eye geometry-release evidence sheets (Eye 45 FD-A06 G, S&E 50 AG-A04/A05), drawn exactly from the pure modules with Pillow:

- section.png: radial cut through facet F1 (its azimuth plane, +X up) for r 4 / 16 / 24: skin, truss chords, collar nodes, disruptor layer and its
  2.25 m port, layer posts, well, facet stack and mount (shared mount at r4, per-facet plate at r16/r24), window cartridge, eyelids (closed leaves
  dashed; the open leaves lie out of the cut, tangentially), the Dust Lance, and the protected-field rays at psi 0 / 180 deg.
- fov.png: transmission maps T(theta, psi) of F1 per radius and pose (open, F1 jammed), with the WORKING well's own 14.0 / 56.3 deg circles.
- poses.png: the r16 eye_facet_detail renders open / closed / F1 jammed (when rendered).
- evidence.md: collisions, protected field, service path, mass sensitivity and the known/unknown manifest, with the render sheet names.

    python3 src/wayfarer/studies/eye_release_sheets.py runs/<stamp>-fwd-a06     # reads evidence.json there (eye_release_evidence.py output)
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

BG, GREY, BLUE, ORANGE, GREEN, DARK, PALE, TEXT, RED, YEL = (14, 19, 26), (110, 120, 130), (70, 140, 245), (245, 150, 40), (60, 210, 100), (5, 8, 12), (150, 170, 185), (210, 225, 235), (225, 60, 50), (235, 210, 80)
W, H = 760, 560


def section_panel(s, r, ev):
    v = ep.variant(s, r); w = fsh.wells(v)[0]; d = math.hypot(w['y'], w['z']); st = fsh.stations(v); p = fsh.prototype(v); P = s['prototype']
    outer = not fsh.in_hub(v, w); rc = ets.collar_radius(v) if outer else None
    rho0, rho1 = (min(-1.5, d-9), d+9) if not outer else (d-9, d+9)
    x0, x1 = w['x0']-P['eye_module_depth_m']-P['eye_backing_depth_m']-4.6, st['face']+5.2
    k = min((W-40)/(rho1-rho0), (H-70)/(x1-x0))
    S = lambda rho, x: (20+(rho-rho0)*k, H-30-(x-x0)*k)
    img = Image.new('RGB', (W, H), BG); g = ImageDraw.Draw(img)
    def poly(pts, col, width=1):
        g.line([S(*q) for q in pts], fill=col, width=width)
    def rect(ra, rb, xa, xb, col, fill=None):
        (a, b), (c, e) = S(ra, xb), S(rb, xa); g.rectangle([min(a, c), min(b, e), max(a, c), max(b, e)], outline=col, fill=fill)
    def dashed(pts, col):
        for (a, b), (c, e) in zip(pts, pts[1:]):
            n = max(1, int(math.dist((a, b), (c, e))*k/6))
            for i in range(0, n, 2):
                poly([(a+(c-a)*i/n, b+(e-b)*i/n), (a+(c-a)*(i+1)/n, b+(e-b)*(i+1)/n)], col)
    rr = [rho0+(rho1-rho0)*i/200 for i in range(201)]
    face = lambda q: fsh.face_x_at(v, abs(q))
    poly([(q, face(q)) for q in rr], TEXT, 2); poly([(q, fsh.skin_aft_at(v, abs(q))) for q in rr], GREY)
    poly([(q, fsh.truss_aft_at(v, abs(q))) for q in rr], GREY)
    m = p['truss_member_radius_m']
    for chord in ('aft', 'fwd'):                                                    # spoke chords in the cut (production at r4; in/out legs at r16/r24)
        xs = (lambda q: fsh.truss_aft_at(v, q)+m) if chord == 'aft' else (lambda q: fsh.skin_aft_at(v, q)-m)
        legs = [(st['hub_opening_r']+p['truss_hub_ring_width_m'], d-2*rc), (d+2*rc, p['crown_housing_inner_radius_m'])] if outer else [(st['hub_opening_r']+p['truss_hub_ring_width_m'], p['crown_housing_inner_radius_m'])]
        for a, b in legs:
            q = [x for x in rr if a <= x <= b]
            if q:
                poly([(x, xs(x)) for x in q], BLUE if outer else GREY, max(1, int(2*m*k)))
    for layer in fsh.disruptor_layers(v):                                            # layer with its port gap round the well
        port = fsh.eye_port_radius(v, layer)
        for seg in ([q for q in rr if q < d-port], [q for q in rr if q > d+port]):
            seg = [q for q in seg if not (abs(q) < fsh.lance_hole_radius(v, layer))]
            if seg:
                poly([(q, fsh.layer_x(v, layer, abs(q))[0]) for q in seg], PALE, max(1, int(layer['thickness']*k)+1))
        g.text(S(d+port+.2, fsh.layer_x(v, layer, d+port)[1]+.5), f'layer +{layer["standoff"]:g} m, port R {port:.2f} m', fill=PALE)
    posts = [(q['r'], q['x0'], q['x1']) for q in fsh.disruptor_posts(v) if abs(((q['azimuth']-math.atan2(w['z'], w['y'])+math.pi) % (2*math.pi))-math.pi) < 1e-6]
    if outer:
        alt = ets.alternate(v); gone = set(alt['removed'])
        posts = [(q['r'], q['x0'], q['x1']) for q in fsh.disruptor_posts(v) if q['name'] not in gone and abs(((q['azimuth']-math.atan2(w['z'], w['y'])+math.pi) % (2*math.pi))-math.pi) < 1e-6]
        posts += [(math.hypot(o['pts'][0][1], o['pts'][0][2]), o['pts'][0][0], o['pts'][1][0]) for o in alt['members'] if o['role'] == 'post' and o['well'] == w['index']]
        for sg in (-1, 1):                                                           # collar chords crossing the cut, verticals between them
            q = d+sg*rc; xa, xf = fsh.truss_aft_at(v, q)+m, fsh.skin_aft_at(v, q)-m
            for x in (xa, xf):
                (a, b) = S(q, x); g.ellipse([a-m*k, b-m*k, a+m*k, b+m*k], outline=BLUE, fill=BLUE)
            poly([(q, xa), (q, xf)], BLUE, max(1, int(m*k)))
        g.text(S(d+rc+.3, fsh.truss_aft_at(v, d+rc)-.6), f'collar R {rc:.2f} m', fill=BLUE)
    for q, a, b in posts:
        if rho0 <= q <= rho1:
            poly([(q, a), (q, b)], BLUE if outer and abs(abs(q-d)-rc) < 1e-6 else GREY, max(1, int(2*p['disruptor_post_radius_m']*k)))
    rw = w['radius']; ra = s['eye']['aperture']['value']/2
    for sg in (-1, 1):
        poly([(d+sg*rw, w['x0']), (d+sg*rw, face(d+sg*rw))], TEXT, 2)                   # well wall to the local face
    rect(d-ra, d+ra, w['x0']-P['eye_module_depth_m'], w['x0'], YEL)                  # facet module
    bx0 = w['x0']-P['eye_module_depth_m']-P['eye_backing_depth_m']
    if outer:
        rect(d-rw, d+rw, bx0, bx0+P['eye_backing_depth_m'], BLUE, BLUE)              # per-facet plate
        for phi in ets.FRAME_PHI:
            e = math.radians(phi); q = d+rw*math.cos(e); cq = d+rc*math.cos(e)
            poly([(q, bx0+P['eye_backing_depth_m']/2), (cq, fsh.truss_aft_at(v, cq)+m)], BLUE)
        race = next(o for o in alt['members'] if o['role'] == 'raceway' and o['well'] == w['index'])
        dashed([(math.hypot(q[1], q[2]), q[0]) for q in race['pts']], ORANGE)
        g.text(S(d-8.6, fsh.truss_aft_at(v, d-6)-1.2), 'raceway (1.0 m off the cut, projected)', fill=ORANGE)
    else:
        rect(max(rho0, -P['eye_backing_radius_m']), P['eye_backing_radius_m'], bx0, bx0+P['eye_backing_depth_m'], GREY, GREY)
        g.text(S(-1.2, bx0-.8), 'shared mount (r4)', fill=PALE)
    e = fsh.eye_shutters(v)[0]; win = e['window']
    rect(d-win['radius'], d+win['radius'], win['x']-win['thickness']/2, win['x']+win['thickness']/2, GREEN)
    g.text(S(d+rw+.2, win['x']), 'window cartridge', fill=GREEN)
    tl = e['tilt']; half = e['radial']/2
    dashed([(d-half*math.cos(tl), e['x']+half*math.sin(tl)), (d+half*math.cos(tl), e['x']-half*math.sin(tl))], TEXT)
    g.text(S(d-half, e['x']+.45), f'eyelids closed (dashed; open leaves part tangentially), tilt {math.degrees(tl):.1f} deg', fill=TEXT)
    if d < 12:                                                                       # Dust Lance root
        L = fsh.lance(v)
        poly([(L['base_r'], L['x0']), (L['tip_r'], min(L['cone_end'], x1))], GREY, 2)
        poly([(L['base_r'], st['spine_end']), (L['base_r'], L['x0'])], GREY, 2)
    f = ev['fov']['open']
    for ps, sg in ((0, 1), (180, -1)):                                               # protected-field rays from the far aperture edge
        row = next(x for x in f['per_psi'] if x['psi_deg'] == ps)
        for key, col in (('full_deg', GREEN), ('zero_deg', RED)):
            if row[key] is not None:
                t = math.radians(row[key]); a = (d-sg*ra, w['x0']); L_ = (x1-w['x0'])/math.cos(t)
                poly([a, (a[0]+sg*L_*math.sin(t), a[1]+L_*math.cos(t))], col)
    g.text((10, 8), f"r {r:g} m - {ep.STATUS[r]} - radial cut through F1, +X up", fill=TEXT)
    g.text((10, H-20), f"{(rho1-rho0):g} m across; green = last fully clear ray, red = first dark ray (psi 0 / 180 deg); FOV OPEN", fill=PALE)
    return img


def fov_panel(f):
    img = Image.new('RGB', (380, 400), BG); g = ImageDraw.Draw(img); cx, cy, R = 190, 205, 165; tmax = f['thetas_deg'][-1]
    dps = 2*math.pi/len(f['psis_deg']); dth = f['thetas_deg'][1]-f['thetas_deg'][0]
    for ps, row in zip(f['psis_deg'], f['transmission']):
        for th, T in zip(f['thetas_deg'], row):
            col = (int(14+(60-14)*T), int(19+(210-19)*T), int(26+(100-26)*T)) if T > 0 else (40, 10, 12)
            a0 = math.radians(ps)-dps/2; r0, r1 = max(th-dth/2, 0)/tmax*R, (th+dth/2)/tmax*R
            pts = [(cx+rr*math.cos(a0+dps*i/6), cy-rr*math.sin(a0+dps*i/6)) for rr in (r0,) for i in range(7)]+[(cx+r1*math.cos(a0+dps*i/6), cy-r1*math.sin(a0+dps*i/6)) for i in range(6, -1, -1)]
            g.polygon(pts, fill=col)
    for th, col in ((f['well_only_deg'][0], TEXT), (f['well_only_deg'][1], PALE)):
        rr = th/tmax*R; g.ellipse([cx-rr, cy-rr, cx+rr, cy+rr], outline=col)
    for th in (20, 40, 60):
        g.text((cx+th/tmax*R-12, cy+2), f'{th}', fill=PALE)
    g.text((cx+R-60, cy-12), 'outward', fill=PALE); g.text((cx-R, cy-12), 'axis', fill=PALE)
    g.text((8, 6), f"r {f['radius_m']:g} m - {f['pose']} - T on axis {f['on_axis_transmission']}", fill=TEXT)
    g.text((8, 20), f"clear {f['unvignetted_half_angle_deg']} deg, 50% {f['half_transmission_deg']['min']}-{f['half_transmission_deg']['max']}, dark {f['cutoff_deg']['min']}-{f['cutoff_deg']['max']}", fill=TEXT)
    g.text((8, 382), 'circles: well alone 14.0 / 56.3 deg', fill=PALE)
    return img


def table(rows, head):
    return ['| '+' | '.join(head)+' |', '|'+'---|'*len(head)]+['| '+' | '.join(str(x) for x in r)+' |' for r in rows]


def main(run):
    s, *_ = load(); E = json.loads((run/'evidence.json').read_text()); ev = {float(k): x for k, x in E['evidence'].items()}
    sec = [section_panel(s, r, ev[r]) for r in sorted(ev)]
    sheet = Image.new('RGB', (W, H*len(sec)), BG)
    for i, im in enumerate(sec):
        sheet.paste(im, (0, i*H))
    sheet.save(run/'section.png')
    panels = [[fov_panel(ev[r]['fov'][p]) for p in ('open', 'jammed')] for r in sorted(ev)]
    sheet = Image.new('RGB', (760, 400*len(panels)), BG)
    for i, (a, b) in enumerate(panels):
        sheet.paste(a, (0, i*400)); sheet.paste(b, (380, i*400))
    sheet.save(run/'fov.png')
    tiles = [(lab, run/'r16'/st/'preview_eye_facet_detail.png') for lab, st in (('open (DEFENSE_ENGAGED)', 'defense_engaged'), ('closed', 'eye_shutters_closed'), ('F1 jammed 0.6', 'eye_f1_jammed'))]
    tiles = [(lab, Image.open(p)) for lab, p in tiles if p.exists()]
    if tiles:
        w_, h_ = tiles[0][1].size; sh = Image.new('RGB', (w_*len(tiles), h_+28), BG); g = ImageDraw.Draw(sh)
        for i, (lab, im) in enumerate(tiles):
            sh.paste(im, (i*w_, 28)); g.text((i*w_+8, 8), f'r 16 m STUDY - eyelids {lab}', fill=TEXT)
        sh.save(run/'poses.png')
    md = ['# FWD-V2 Eye geometry-release evidence (Eye 45 FD-A06, S&E 50 AG-A04/A05)', '', E['boundary'], '',
          'Renders: `compare_bow.png` (front), `compare_side.png`, `compare_threequarter.png`, `compare_eye_facet_detail.png`, `poses.png`. '
          'Section: `section.png`. Field: `fov.png`. Data: `evidence.json` (contract WF_EYE_RELEASE_EVIDENCE v1), `manifest.json`.', '',
          '## Collisions (margins in m; negative = clash)', '']
    radii = sorted(ev); items = [x['item'] for x in ev[radii[-1]]['collisions']['rows']]
    allitems = list(dict.fromkeys([x['item'] for r in radii for x in ev[r]['collisions']['rows']]))
    rows = []
    for it in allitems:
        cells = []
        for r in radii:
            x = next((y for y in ev[r]['collisions']['rows'] if y['item'] == it), None)
            cells.append('-' if x is None else f"{x['margin_m']:+.3f} {'ok' if x['ok'] else 'CLASH'} (>= {x['required_m']})")
        rows.append([it]+cells)
    md += table(rows, ['check']+[f'r {r:g}' for r in radii])+['', 'Every collision check passes at r4, r16 and r24 once the eyelid frame lies on the local cone (study wells only; '
                                                                 'r4 is flat, tilt 0). Without that tilt the flat leaves cut the cone skin by 0.094 m at r16 and r24.' if all(ev[r]['collisions']['all_ok'] for r in radii) else 'Some checks fail: see the table.', '']
    md += ['## Protected field of F1 (geometric; EYE FOV OPEN)', '']
    rows = []
    for r in radii:
        for p in ('open', 'jammed', 'closed'):
            f = ev[r]['fov'][p]
            rows.append([f'r {r:g}', p, f['on_axis_transmission'], f['unvignetted_half_angle_deg'], f"{f['half_transmission_deg']['min']}-{f['half_transmission_deg']['max']}",
                         f"{f['cutoff_deg']['min']}-{f['cutoff_deg']['max']}", f['clear_solid_angle_sr'], ', '.join(f'{k} {v_:.0%}' for k, v_ in f['blocked_ray_share'].items())])
    md += table(rows, ['radius', 'eyelids', 'T on axis', 'fully clear half-angle (deg)', '50 % (deg)', 'dark (deg)', 'clear solid angle (sr)', 'blocked rays by'])
    md += ['', f"Ray trace from 43 points on the 2.5 m aperture, theta 0-60 deg in 1 deg steps, psi in 15 deg steps (closed: 10/90 deg). The WORKING well "
               f"alone gives {ev[radii[0]]['fov']['open']['well_only_deg'][0]} deg unvignetted and {ev[radii[0]]['fov']['open']['well_only_deg'][1]} deg cut-off; the 2.25 m outer port is sized "
               "to the unvignetted cone only, so it is what darkens the field between about 28 and 44 deg. At r4 the Dust Lance cuts the side toward the axis; at r16 "
               "and r24 it no longer reaches the field. The same rays reversed give the window's geometric exposure to a directional flux; impact rating OPEN.", '']
    md += ['## Window-cartridge service path (crawler first; FLIGHT_EVA HOLD)', '']
    rows = []
    for r in radii:
        sv = ev[r]['service']
        if not sv:
            rows.append([f'r {r:g}', 'served from inside the body hub', '-', '-', '-']); continue
        for f in sv['facets']:
            rows.append([f'r {r:g} {f["facet"]}', f"hatch {f['hatch_phi_deg']:g} deg, slide {f['slide_m']} m", f"{f['exit_margin_m']:+.3f}",
                         f"{f['aft_leg_length_m']} m to the hull", f"{f['aft_leg_margin_m']:+.3f} ({f['aft_leg_nearest']})"])
    md += table(rows, ['facet', 'well exit', 'exit margin', 'aft leg', 'aft-leg margin (nearest)'])
    sv = ev[16.0]['service']
    md += ['', f"Service poses (AG-A04): {'; '.join(f'{k}: {x}' for k, x in sv['poses'].items())}. OPEN: {', '.join(sv['open'])}.", '']
    if any(ev[r].get('crawler') for r in radii):
        md += ['## Brow crawler approach (DR-EVA-01 on the DS-10 track; AG-A04, DGT-006)', '']
        rows = []
        for r in radii:
            c = ev[r].get('crawler')
            if not c:
                rows.append([f'r {r:g}', '-', '-', '-', '-', '-', '-']); continue
            for f in c['facets']:
                rows.append([f'r {r:g} {f["facet"]}', f"{f['dock']} ({f['dock_azimuth_deg']:g} deg)", f"{f['rail_travel_from_dock_m']} m to r {f['at_rail_radius_m']}",
                             f"{f['centreline_gap_m']}", f"{f['rim_gap_after_crawler_m']:+.3f} {'reachable' if f['reachable_from_track'] else 'NOT reachable'}",
                             f"{f['cartridge_clear_of_ds10_m']:+.3f}", f"{f['arm_base_to_aft_leg_m']}"])
        md += table(rows, ['facet', 'nearest dock', 'rail travel', 'track to cartridge path (m)', 'rim gap after the crawler half-envelope (m)',
                           'cartridge clear of DS-10 hardware (m)', 'DS-15 arm base to the aft leg (m)'])
        c = next(ev[r]['crawler'] for r in radii if ev[r].get('crawler'))
        md += ['', f"Crawler {c['crawler']['cls']}: upper envelope {c['crawler']['envelope_upper_m']} m, {c['crawler']['status']}, mass and payload OPEN. Tracks: "
                   f"{c['tracks']}. The DS-10 tracks run along the spokes, 30 deg off the wells; the closest approach to each cartridge path is at the "
                   "track's inner end by the hull, and there the crawler still cannot touch the cartridge rim. The owner selected a well-wall carrier, "
                   f"an aft-face station and a captured sled the crawler tows (15!A189:A191; next section). The cartridge passes clear of the DS-10 rails and docks. OPEN: {', '.join(c['open'])}.", '']
    if any(ev[r].get('handoff') for r in radii):
        md += ['## Cartridge hand-off (OWN-EYE-H1..H4, Eye 45 FD-B11; L2 kinematic concept, geometry only)', '']
        rows = []
        for r in radii:
            h = ev[r].get('handoff')
            if not h:
                continue
            for f in h['facets']:
                if 'carrier_stroke_m' not in f:
                    rows.append([f'r {r:g} {f["facet"]}', h['mode'], '-', '-', '-', '-', ', '.join(map(str, f['crown_bays_locked']))]); continue
                rows.append([f'r {r:g} {f["facet"]}', f"{f['carrier_stroke_m']} m, exit {f['carrier_exit_margin_m']:+.3f}", f"{f['handoff_turn_deg']} deg",
                             f"{f['sled_run_m']} m, {f['sled_margin_m']:+.3f} ({f['sled_nearest']}), max bend {f['raceway_max_bend_deg']} deg",
                             f"{f['tow_track']}: {f['tow_gap_to_sled_edge_m']:+.3f}", f"{f['recovery_track']}: {f['recovery_gap_to_sled_edge_m']:+.3f}",
                             ', '.join(map(str, f['crown_bays_locked']))])
        md += table(rows, ['facet', 'carrier stroke', 'turn at the aft-face station', 'sled run, margin, raceway bend', 'tow track gap to the sled edge (m)',
                           'recovery from the neighbouring track (m)', 'Crown bays locked'])
        h = next(ev[r]['handoff'] for r in radii if ev[r].get('handoff') and ev[r]['handoff'].get('stranded'))
        md += ['', 'Positive support (15!G189): ' + ' -> '.join(f"{st['step']} [{' + '.join(st['holders'])}]" for st in h['support_sequence'])
               + f" — {h['positive_support']['result']} ({h['positive_support']['rule']}).", '',
               'Stranded cases: ' + '; '.join(f"{x['where']}: {x['state']}; {x['recovery']}" for x in h['stranded']) + '.', '',
               f"Safe state for a swap: {'; '.join(h['safe_state'])}. Loads: {h['anchor_reactions']}. OPEN: {', '.join(h['open'])}.", '']
    md += ['## Mass sensitivity (lengths only; linear masses OPEN)', '']
    rows = []
    for r in radii:
        m = ev[r]['mass']
        if not m['alternate']:
            rows.append([f'r {r:g}', 'production truss', '-', '-', '-']); continue
        rows.append([f'r {r:g}', m['replaced_m'], m['net_structure_m'], m['raceway_m'], ', '.join(f'{k}: {x} kg/m' for k, x in m['break_even_lambda_truss_kg_per_m'].items())])
    md += table(rows, ['radius', 'replaced (m)', 'net structure added (m)', 'raceway (m)', 'linear mass at which the net change equals'])
    md += ['', f"{ev[16.0]['mass']['formula']}. Four facet plates, {ev[16.0]['mass']['facet_plates']['area_m2']} m2 together. {ev[16.0]['mass']['note']}.", '',
           '## Known / unknown manifest', '']
    rows = [[q['key'], q.get('value', '') if q['known'] else 'UNKNOWN', q['unit'], q['status'], q['source']] for q in E['manifest']]
    md += table(rows, ['quantity', 'value', 'unit', 'status', 'source'])
    (run/'manifest.json').write_text(json.dumps(E['manifest'], indent=1)+'\n')
    (run/'evidence.md').write_text('\n'.join(md)+'\n')


if __name__ == '__main__':
    main(Path(sys.argv[1]))
