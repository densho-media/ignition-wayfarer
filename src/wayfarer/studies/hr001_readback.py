"""HR-001 / TODO E04: readback and owner input packet for the selected heat-recovery branch (NONCANON study; owner numbers OPEN).

Collects what the owner needs to review the L2 study (C-021 acceptance gates, HR-P10/P11/P14/P15/P17): the geometry regression against
the built model and its keepouts, the measured proxy quantities (geometric volume, never mass), the state / fault results, the symbolic
energy accounting on one control volume for BYPASS / PREHEAT / BRAYTON / HYBRID at equal fusion power and at equal thrust, the input
packet (variable, unit, owning sheet) and a mode schematic. No value is invented: every physical quantity is a symbol with known = false.

    python3 src/wayfarer/studies/hr001_readback.py --out runs/<stamp>-hr001-readback     # JSON, CSV packet, SVG schematic
    /snap/bin/blender -b --python src/wayfarer/studies/hr001_readback.py -- --out runs/<stamp>-hr001-readback --views   # + annotated views
"""
from pathlib import Path
import argparse
import csv
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/studies'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation')]
from spec import load
import drive_manifold as dm
import human_entry
import thermal_geometry as tg
import hr001_packaging as hp
import hr001_states as hs_


# ---------- geometry regression (HR-P14) -------------------------------------------------------------------------------------------------

def part_points(s, key):
    pts = []
    for p in hp.CANDIDATES[key](s):
        q, _ = hp.samples(p, step=0.2); pts += q
    return pts


def regression(s, key=hp.SELECTED):
    """Distances from the selected study parts to things the study must not change or approach, plus the statement that the saved model
    is untouched (the study is an overlay; the full pipeline fingerprint is the proof)."""
    pts = part_points(s, key); st = dm.stations(s)
    xs = [q[0] for q in pts]; rs = [math.hypot(q[1], q[2]) for q in pts]
    crew = [pt for r in human_entry.route(s).values() for _, pt in r['path']]
    crew_gap = min(math.dist(a, b) for a in pts[::4] for b in crew)
    # Radiator blades: the root edge (r = root radius) runs from the aft edge to the front in the three blade planes.
    root_r = s['radiators']['root_radius']['value']; blade_gap = root_r-max(rs)      # the blades span X -101..+81 m, so they pass over the bay
    sc = hp.screen(s)[key]
    return dict(
        candidate=key, saved_model_changed=False,
        saved_model_note='overlay only: nothing is written to assets/; the 2026-10-16 full pipeline (zero geometry change) is the fingerprint of the untouched model',
        envelope=dict(x_min=round(min(xs), 2), x_max=round(max(xs), 2), r_min=round(min(rs), 2), r_max=round(max(rs), 2)),
        least_gaps_m={k: v['gap_m'] for k, v in list(sc['gaps'].items())[:10]},
        hull_skin='inside the 5.9 m inner wall (no hull change)', shadow_shield='no penetration' if sc['new_slab_sleeves'] == 0 else f"{sc['new_slab_sleeves']} new sleeves",
        radiator_root_edge_radial_m=round(blade_gap, 2), radiator_blade_aft_edge_x=round(-101.0, 1),
        nozzle_inlet_axial_m=round(min(xs)-st['inlet'], 2), seed_lattice_axial_m=round(min(xs)-st['lattice_fwd'], 2),
        crew_route_m=round(crew_gap, 1),
        keepouts_hold=['nozzle plume and strong-field exclusion (R2): boundary OPEN', 'seed-field / magnetic envelope of the lattice and coils: OPEN',
                       'neutron / gamma dose at the drive annulus: OPEN (no shadow)', 'H2 leak / venting zone: OPEN'],
        radiators='three blades, warm panels, joints and roots untouched; no area, emissivity or margin change')


# ---------- measured proxy quantities (HR-P15: geometric volume reported apart from mass) ---------------------------------------------------

def quantities(s, key=hp.SELECTED):
    parts = hp.CANDIDATES[key](s); out = dict(per_ship={}, per_line={})
    vol = lambda p: (p['x1']-p['x0'])*(p['r1']-p['r0'])*p['width']
    pipe_len = lambda p: hp.path_length(p['points'])
    groups = {'hx_core': 'preheater cassette', 'inter_hx': 'intermediate exchanger'}
    for kind, label in groups.items():
        bs = [p for p in parts if p['kind'] == kind]
        out['per_ship'][f'{label} proxy volume m3'] = round(sum(vol(p) for p in bs), 3)
        out['per_ship'][f'{label} count'] = len(bs)
    for kind, label in (('h2_branch', 'H2 branch pipe'), ('intermediate', 'intermediate loop pipe'), ('hot', 'hot branch stub')):
        ps_ = [p for p in parts if p['kind'] == kind]
        out['per_ship'][f'{label} length m'] = round(sum(pipe_len(p) for p in ps_), 2)
        out['per_ship'][f'{label} proxy radius m'] = ps_[0]['radius'] if ps_ else None
    out['per_ship']['valves'] = sum(p['kind'] == 'valve' for p in parts)
    out['per_ship']['sensors'] = sum(p['kind'] == 'sensor' for p in parts)
    out['per_ship']['mass kg'] = dict(known=False, reason='no material, wall, fluid or density released (HR-P15, 34_HARDWARE_PACKING)')
    out['per_line'] = {'preheated H2 run to the injection ring m': hp.screen(s)[key]['preheated_h2_run_m'][0]}
    return out


# ---------- symbolic accounting (HR-003, HR-P10/P11; Fiji 15!A49:A54) ------------------------------------------------------------------

CONTROL_VOLUME = ('Single control volume: the drive hot loop, the HR exchanger and intermediate loop, the H2 branch to the injection ring, '
                  'Brayton A/B and the hot radiators. Inputs: Q_src (heat the hot loop absorbs from the drive). Outputs: Q_rad (hot radiators), '
                  'P_e (Brayton electric output, later dissipated in the warm/cold loops), Q_sink (Brayton cold-side rejection), '
                  'Q_H2 = mdot_H2 * (h_out - h_in) carried out on departing hydrogen, Q_loss, dU/dt.')
CASES = {
    'BYPASS':           dict(balance='Q_src = Q_rad + Q_B,in + dU/dt + Q_loss;  Q_H2 = 0', brayton='as built (Q_B,in = P_e + Q_sink)'),
    'PREHEAT_STUDY':    dict(balance='Q_src = Q_rad + Q_H2 + Q_B,in + dU/dt + Q_loss;  0 <= Q_H2 <= Q_avail(T_src, pinch)', brayton='as built'),
    'BRAYTON_BASELINE': dict(balance='same as BYPASS: the existing Brayton A/B take Q_B,in from the hot loop', brayton='Q_B,in = P_e + Q_sink'),
    'HYBRID_STUDY':     dict(balance='Q_src = Q_rad + Q_H2 + Q_B,in + dU/dt + Q_loss with a controlled split x: Q_H2 = x * Q_avail', brayton='as built; split OPEN'),
}
COMPARISONS = {
    'equal fusion power': 'Fix P_fus and the core absorption; compare Q_rad across cases. Radiator relief = Q_H2 only for heat that leaves on the exhaust, net of '
                          'pump work and pressure / nozzle losses (HR-003). If downstream plasma heating then falls by the same Q_H2 (preheat replaces '
                          'heating rather than adding to it), exhaust enthalpy and thrust are unchanged and the relief is real; if not, thrust changes '
                          'and the comparison is no longer like for like.',
    'equal thrust':       'Fix F and Isp (commanded mdot_H2 and exhaust enthalpy); preheat lowers the downstream heating needed, so P_fus or the heating '
                          'power may fall; compare the fuel and Q_src saved against the added pumps, Δp and mass. Δv benefit is not assumed (Fiji 15!A54, HR-P11).',
}
NO_DOUBLE_COUNT = ('A joule moved from the hot loop to H2 is not also Brayton input, radiator load or extra exhaust power (Fiji 15!A52); '
                   'the 160 TW / 16 GW / 14.4 GW figures stay DIAGNOSTIC and the -1.60 GW shortfall is not claimed solved (Fiji 15!A57, 40!A104).')


# ---------- owner input packet (HR-P10, HR-P15, 40!A108) ---------------------------------------------------------------------------------

PACKET = [
    ('Q_src', 'hot-loop heat available at the tap per operating point', 'W', 'S&E 40_THERMAL / Fiji 30_DRIVE_THERMAL'),
    ('T_src', 'hot-loop supply temperature at the tap (fluid, not the 1800 K skin)', 'K', 'Fiji 30_DRIVE_THERMAL A14'),
    ('hot_fluid', 'hot-loop fluid and its pressure', '-, Pa', 'S&E 40_THERMAL'),
    ('mdot_H2', 'hydrogen reaction-mass flow per line through the branch', 'kg/s', 'Fiji 20_PROPULSION / S&E fuel inventory (P0)'),
    ('T_in, p_in, phase_in', 'H2 state after conditioning at the branch inlet', 'K, Pa, -', 'Fiji 30_DRIVE_THERMAL A11'),
    ('T_out, phase_out', 'H2 state allowed at the injection ring', 'K, -', 'Fiji 30_DRIVE_THERMAL A11 / 20_PROPULSION'),
    ('h(T,p)', 'hydrogen enthalpy data (ortho/para, phase)', 'J/kg', 'Fiji 15_ENERGY_FLOW A49'),
    ('pinch', 'HX approach temperature / effectiveness', 'K, -', 'Fiji 30_DRIVE_THERMAL A14'),
    ('dp_branch', 'allowable pressure drop of the branch at full flow (also the F05 cold pass-through)', 'Pa', 'S&E 06 / injector demand'),
    ('P_pump, P_ctrl', 'pump and control power of the intermediate loop and valves', 'W', 'S&E 17_POWER_STORAGE'),
    ('Q_B,in, P_e, Q_sink', 'Brayton A/B ratings per operating point', 'W', 'S&E 17 / 40 (ratings OPEN)'),
    ('m_HX, m_pipe, m_fluid', 'masses of exchanger, piping, intermediate fluid, insulation, supports', 'kg', 'S&E 10_WAYFARER_MASS / 34_HARDWARE_PACKING'),
    ('materials', 'H2-side and hot-side materials, embrittlement and leak class', '-', 'S&E OD-022..028, OD-041'),
    ('trip limits', 'overtemperature, underflow, Δp and leak trip limits and delays', 'K, kg/s, Pa, s', 'S&E 39_FAILURE_SCENARIOS / 11_OPERATING_CONFIGS'),
    ('keepouts', 'plume, seed-field / magnetic and dose envelopes at the drive annulus', 'm, T, Sv/h', 'S&E 07 / 14 / 15 R2-R3'),
    ('time series', 'approved samples of the 12 HR channels for a released scenario', 'see units', 'C-020 heat-state importer'),
]


# ---------- schematic (SVG, hand-laid boxes; no physical scale) ------------------------------------------------------------------------

def schematic_svg():
    W, H = 1060, 600
    box = lambda x, y, w, h, t, fill: (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="#2b3440" stroke-width="1.5"/>'
                                       + ''.join(f'<text x="{x+w/2}" y="{y+h/2+5+16*(i-(len(t)-1)/2):.0f}" text-anchor="middle">{s}</text>' for i, s in enumerate(t)))
    arrow = lambda x1, y1, x2, y2, head=True: f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#333" stroke-width="2.5"' + (' marker-end="url(#a)"/>' if head else '/>')
    valve = lambda x, y, t: f'<circle cx="{x}" cy="{y}" r="10" fill="#fff" stroke="#222" stroke-width="2"/><text x="{x}" y="{y-16}" text-anchor="middle" font-size="12">{t}</text>'
    e = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="sans-serif" font-size="14">',
         '<defs><marker id="a" markerUnits="userSpaceOnUse" markerWidth="12" markerHeight="10" refX="11" refY="5" orient="auto"><path d="M0,0 L12,5 L0,10 z" fill="#333"/></marker></defs>',
         '<rect width="100%" height="100%" fill="#f6f7f9"/>',
         '<text x="20" y="30" font-size="18" font-weight="bold">HR-001 L2 study (candidate B) — per hydrogen line; PROTOTYPE, every number OPEN</text>',
         box(30, 70, 170, 60, ['H2 tank (cryogenic)', 'conditioning (OPEN)'], '#d9ecff'),
         box(30, 330, 170, 70, ['Drive hot loop', 'Q_src, T_src OPEN'], '#ffd9d2'),
         box(390, 230, 170, 60, ['Intermediate HX', '(hot | intermediate)'], '#f3b5a8'),
         box(390, 110, 170, 60, ['H2 preheater', 'cassette'], '#f7c98b'),
         box(780, 70, 250, 60, ['Injection ring', '→ common region → N1–N4'], '#cfe8e6'),
         box(780, 330, 250, 70, ['Hot radiators (3 blades)', 'Q_rad — unchanged'], '#e4e4e4'),
         box(390, 420, 170, 70, ['Brayton A / B (existing)', 'P_e + Q_sink'], '#e7dcf7'),
         arrow(200, 100, 780, 100), '<text x="470" y="92" text-anchor="middle" font-size="12">built line = BYPASS (default, fail-open)</text>',
         arrow(290, 100, 290, 140, False), arrow(290, 140, 390, 140), arrow(560, 140, 680, 140, False), arrow(680, 140, 680, 100),
         valve(625, 100, 'H2_Bypass'), valve(290, 122, ''), valve(680, 122, ''),
         '<text x="300" y="170" font-size="12">H2_In</text><text x="690" y="170" font-size="12">H2_Out</text>',
         arrow(200, 365, 780, 365), '<text x="470" y="385" text-anchor="middle" font-size="12">existing hot loop to the radiators (never in the branch)</text>',
         arrow(330, 365, 330, 260, False), arrow(330, 260, 390, 260), valve(330, 320, ''), '<text x="342" y="316" font-size="12">Hot_Isolation</text>',
         '<text x="575" y="252" font-size="12">hot and intermediate returns not drawn</text>',
         arrow(475, 230, 475, 170), '<text x="490" y="205" font-size="12">intermediate loop</text>',
         arrow(250, 365, 250, 455, False), arrow(250, 455, 390, 455),
         '<text x="30" y="528" font-size="13">Valves fail to BYPASS (branch closed, built line open, hot side closed).</text>',
         '<text x="30" y="548" font-size="13">PREHEAT_STUDY / HYBRID_STUDY open the branch; every other state is the built line.</text>',
         '<text x="30" y="572" font-size="13">Q_H2 = mdot_H2·(h_out − h_in) counts once inside one control volume; radiator relief only for heat leaving on the exhaust.</text>',
         '</svg>']
    return '\n'.join(e)


# ---------- annotated views (Blender) ----------------------------------------------------------------------------------------------------

LABELS = [  # part-name suffix on line 3 -> label
    ('L3_HX_Core', 'H2 preheater cassette'), ('L3_Intermediate_HX', 'intermediate HX (hot | intermediate)'),
    ('L3_Valve_H2_Bypass', 'built line = bypass valve'), ('L3_Valve_H2_In', 'branch inlet valve'), ('L3_Valve_H2_Out', 'branch outlet valve'),
    ('L3_Hot_Loop_Tap', 'hot-loop tap (route OPEN)'), ('L3_Valve_Hot_Isolation', 'hot isolation valve'),
]


def annotated_views(s, out, size):
    """Blender half: render the cutaway views and project each label anchor to pixels (_raw/labels.json). compose() draws them."""
    import bpy
    from mathutils import Vector, Matrix
    import bpy_extras.object_utils as ou
    tmp = out/'_raw'; tmp.mkdir(exist_ok=True)
    hp.renders(s, tmp, size)
    sc = bpy.context.scene; cam = sc.camera
    parts = {p['name']: p for p in hp.CANDIDATES[hp.SELECTED](s)}
    P = lambda x, r, deg: Vector(hp.radial(x, r, deg))
    cams = {'candidate_b': (P(-80, 13, 300), P(-90.5, 4.0, 280), 30, 'hr001_candidate_b.png'),
            'side': (P(-80, 45, 270), P(-80, 0, 270), 40, 'hr001_side.png')}
    labels = {}
    for view, (loc, look, lens, fname) in cams.items():
        z = (loc-look).normalized(); up = Vector((1, 0, 0)) if abs(z.x) < .9 else Vector((0, 0, 1)); x = up.cross(z).normalized(); y = z.cross(x)
        cam.location = loc; cam.rotation_euler = Matrix((x, y, z)).transposed().to_euler(); cam.data.lens = lens
        bpy.context.view_layer.update(); w, h = sc.render.resolution_x, sc.render.resolution_y; pts = []
        for suffix, text in LABELS:
            p = parts[f'HR_{hp.SELECTED}_{suffix}']
            c = p['point'] if p['shape'] == 'node' else tuple(sum(q[i] for q in p['corners'])/8 for i in range(3)) if p['shape'] == 'box' else p['points'][len(p['points'])//2]
            co = ou.world_to_camera_view(sc, cam, Vector(c))
            if 0 < co.x < 1 and 0 < co.y < 1 and co.z > 0:
                pts.append(dict(text=text, x=co.x*w, y=(1-co.y)*h))
        labels[view] = dict(image=fname, labels=pts)
    (tmp/'labels.json').write_text(json.dumps(labels, indent=1))
    return list(labels)


def compose(out):
    """System-Python half: draw leaders and labels on the raw renders (PIL)."""
    from PIL import Image, ImageDraw, ImageFont
    labels = json.loads((out/'_raw/labels.json').read_text()); paths = []
    for view, d in labels.items():
        im = Image.open(out/'_raw'/d['image']).convert('RGB'); dr = ImageDraw.Draw(im); w, h = im.size
        font = ImageFont.load_default(size=max(14, w//70))
        left = [l for l in d['labels'] if l['x'] < w/2]; right = [l for l in d['labels'] if l['x'] >= w/2]
        for side, group in (('L', sorted(left, key=lambda l: l['y'])), ('R', sorted(right, key=lambda l: l['y']))):
            for k, l in enumerate(group):
                tw = dr.textlength(l['text'], font=font); ty = 60+k*int(h/12)
                tx = 20 if side == 'L' else w-20-tw; ax = tx+tw+6 if side == 'L' else tx-6
                dr.line([(l['x'], l['y']), (ax, ty+9)], fill=(255, 230, 120), width=2)
                dr.ellipse([l['x']-5, l['y']-5, l['x']+5, l['y']+5], outline=(255, 230, 120), width=2)
                dr.text((tx, ty), l['text'], fill=(255, 255, 255), font=font)
        dr.text((20, 20), 'HR-001 candidate B: NONCANON L2 study; PROTOTYPE envelopes; duty, mass, ratings and keepouts OPEN', fill=(230, 230, 230), font=font)
        p = out/f'hr001_annotated_{view}.png'; im.save(p); paths.append(p.name)
    return paths


def main(out, views=False, size=1280):
    s = load(ROOT)[0]; out.mkdir(parents=True, exist_ok=True)
    states = hs_.report(s)
    r = dict(study='HR-001 E04 readback (NONCANON L2 study; owner numbers OPEN)', candidate=hp.SELECTED,
             sources=['S&E 15!A193:A196', '06!A58:A64', '40!A97:A109', '26 C-019..C-021', '09 OD-041', 'Fiji 15!A45:A57', 'Fiji 30!A10:A18'],
             regression=regression(s), quantities=quantities(s), topology=hp.topology(s)[hp.SELECTED],
             states=dict(result=states['result'], checks=states['checks'], configurations=states['configurations'],
                         faults=[{k: f[k] for k in ('id', 'fault', 'state', 'outcome', 'unresolved', 'owner', 'replay')} for f in states['faults']]),
             accounting=dict(control_volume=CONTROL_VOLUME, cases=CASES, comparisons=COMPARISONS, no_double_count=NO_DOUBLE_COUNT,
                             values=dict(known=False, reason='owner performs the energy accounting (HR-003, 40!A108)')),
             packet=[dict(symbol=a, quantity=b, unit=c, owner=d, known=False) for a, b, c, d in PACKET])
    (out/'hr001_schematic.svg').write_text(schematic_svg())
    with open(out/'hr001_input_packet.csv', 'w', newline='') as fh:
        wr = csv.writer(fh); wr.writerow(['symbol', 'quantity', 'unit', 'owner', 'status'])
        for a, b, c, d in PACKET:
            wr.writerow([a, b, c, d, 'OPEN'])
    if views:
        r['views_rendered'] = annotated_views(s, out, size)
    elif (out/'_raw/labels.json').exists():
        r['views'] = compose(out)
    (out/'hr001_readback.json').write_text(json.dumps(r, indent=1)+'\n')
    print('WF_HR001_READBACK done', out, r['topology']['result'], r['states']['result'], flush=True)
    return r


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); ap.add_argument('--views', action='store_true')
    ap.add_argument('--size', type=int, default=1280)
    a = ap.parse_args(argv)
    main(a.out if a.out.is_absolute() else ROOT/a.out, a.views, a.size)
