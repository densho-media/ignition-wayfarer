"""M5 GNC / COMMS: the three attitude modes and the COAST comms contact picture as a visualization of the built model (owner 2026-10-18,
S&E 15!A210 OWN-S02-Q1 G "Animate COAST contacts, obstruction/pointing maps, data backlog, light-time and optional outage; keep unknown
infrastructure and achieved kb/s null", I "2 receiving-infrastructure scenarios: 34 m terrestrial reference and Y155 relay array study";
15!A211 OWN-S02-Q2 G "Show three modes: FORWARD_PROTECTED, LOW_HAZARD_SLEW, MAINTENANCE_HOLD; use CAD inertia and 21-minute IDEAL flip for
sensitivity ONLY", I "Model Earth pointing via turret/antenna gimbals, not routine whole-vehicle flips"; 98!A116).
L2 TARGET ONLY / HIGH-SPEED FLIP HOLD / OPERATIONS STUDY / PERFORMANCE OPEN: nothing in the vehicle changes.

Function: show what each mode asks of the vehicle and when Earth is in view of the aft gimbals, from geometry already measured. Fixed:
the shield-shadow tolerance per azimuth and the CAD inertia (references/m5_attitude.json, M5 slice 2), the RCS couples at the 100 N
REFERENCE unit (references/m5_rcs_balanced.json: as-built, B1, B1F), the gimbal positions and the obstacle model (exterior_hardware), the
<= 0.2 deg 3-sigma precision-hold DESIGN TARGET (15!C211), the 30-100 AU early design window and no guaranteed service at 6000 AU
(15!C210). Unknown (OPEN, null): link budget and achieved rate, ground / relay infrastructure, disturbance torques, dust-speed limit,
attitude sensor and actuator noise, thrust class and Isp. Design freedom (PROTOTYPE, this file): Earth geometry for a radial outbound
coast (Earth circles the anti-velocity axis at asin(1 / d_AU) once a year), the sampling.

    python3 src/wayfarer/studies/m5_gnc_comms.py --out runs/<stamp>-m5-gnc-comms   # -> references/m5_gnc_comms.json + sheets
"""
from pathlib import Path
import argparse
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/studies'), str(ROOT/'src/wayfarer/shots')]

OUT_JSON = ROOT/'references/m5_gnc_comms.json'
AU_LIGHT_S = 499.005                    # one-way light time per AU
HOLD_TARGET_DEG = 0.2                   # 15!C211: provisional precision-hold DESIGN TARGET (3-sigma), not a certified cap
SLEW_DEG_S = 0.05                       # reference low-hazard slew rate (as RCS-B)
DISTANCES_AU = (1.2, 2, 3, 5, 10, 30, 100, 1000, 6000)
PHASES = 72                             # Earth phase samples per year
PLUME_DEG = 15.0                        # main plume study cone during a burn (M5 slice 2 LOS maps)
SCENARIOS = (dict(id='GROUND_34M', name='34 m terrestrial reference station', achieved_kbps=None, status='REFERENCE / link budget OPEN'),
             dict(id='Y155_RELAY', name='Y155 relay array study', achieved_kbps=None, status='STUDY / infrastructure OPEN'))
MODES = ('FORWARD_PROTECTED', 'LOW_HAZARD_SLEW', 'MAINTENANCE_HOLD')
DISPLAY_DRAIN = 4.0                     # ILLUSTRATIVE display ratio (h of data sent per h of contact); the real rate is null


def earth_dir(d_au, phase):
    """Unit vector to Earth in body axes for a radial outbound coast (+X along velocity, away from the Sun): the Sun is on -X; Earth is
    1 AU from it, so it sits asin(1/d) off the -X axis (for d >= 1) at an azimuth that goes round once a year."""
    off = math.asin(min(1.0, 1.0/d_au)); return (-math.cos(off), math.sin(off)*math.cos(phase), math.sin(off)*math.sin(phase)), off


def contacts(s):
    """Per antenna, distance and state: the fraction of the year Earth is unobstructed from the gimbal (blade, ring, shield, hull; the
    main plume cone during a burn). COAST pose, gimbals free (15!I211: Earth pointing by gimbal, not by whole-vehicle turns)."""
    import exterior_hardware as eh
    o = eh.obstacles(s); ants = {}
    for p in eh.comms(s):
        ants.setdefault(p['antenna'], p['gimbal'])
    out = {}
    for name, c in ants.items():
        rows = {}
        for d in DISTANCES_AU:
            for state, plume in (('coast', None), ('burn', math.radians(PLUME_DEG))):
                clear = []
                for k in range(PHASES):
                    r, off = earth_dir(d, 2*math.pi*k/PHASES)
                    clear.append(eh.ray_hit(o, c, r, plume=plume) is None)
                rows[f'{d}_{state}'] = dict(au=d, state=state, earth_off_axis_deg=round(math.degrees(off), 3),
                                            clear_fraction=round(sum(clear)/PHASES, 3), clear=[int(v) for v in clear])
        out[name] = dict(gimbal=[round(v, 2) for v in c], cases=rows)
    return out


SKY_STEP_DEG = 4.0                      # Godot looks Earth up in these grids at any attitude (slews included)


def sky_grids(s):
    """Per antenna gimbal, coast and burn: a pol x az grid (pol from -X 0..180, az from +Y through +Z), '1' clear, '0' blocked; the
    same ray model as the M5 slice 2 LOS maps (the plume cone only for aft-looking rays in a burn)."""
    import exterior_hardware as eh
    o = eh.obstacles(s); ants = {}
    for p in eh.comms(s):
        ants.setdefault(p['antenna'], p['gimbal'])
    n_az, n_pol = int(360/SKY_STEP_DEG), int(180/SKY_STEP_DEG); out = {}
    for name, c in ants.items():
        g = {}
        for state, plume in (('coast', None), ('burn', math.radians(PLUME_DEG))):
            rows = []
            for j in range(n_pol):
                pol = math.radians((j+.5)*SKY_STEP_DEG); row = ''
                for i in range(n_az):
                    az = math.radians((i+.5)*SKY_STEP_DEG)
                    r = (-math.cos(pol), math.sin(pol)*math.cos(az), math.sin(pol)*math.sin(az))
                    h = eh.ray_hit(o, c, r, plume=plume) if plume is None or r[0] < 0.2 else eh.ray_hit(o, c, r)
                    row += '1' if h is None else '0'
                rows.append(row)
            g[state] = rows
        out[name] = dict(gimbal=[round(v, 3) for v in c], step_deg=SKY_STEP_DEG, **g)
    return out


def rcs_patterns(rcs):
    """Jets of the most efficient start / stop pattern per axis (the slew pattern), as-built and B1F, for the display pulses."""
    out = {}
    for k, v in (('as_built', rcs['as_built']), ('B1F', rcs['variants']['B1F'])):
        out[k] = {ax: dict(jets=sorted((t.get('efficient') or {}).get('jets', {})), burn_s=t['slew_start_stop']['burn_s'],
                           h2_kg=t['slew_start_stop']['h2_kg'], torque_N_m=t['torque_N_m'], parasitic_force_N=t['parasitic_force_N'])
                  for ax, t in v.items() if t.get('torque_N_m')}
    return out


def light_time():
    return [dict(au=d, one_way_h=round(d*AU_LIGHT_S/3600, 2), round_trip_h=round(2*d*AU_LIGHT_S/3600, 2), one_way_days=round(d*AU_LIGHT_S/86400, 2))
            for d in DISTANCES_AU]


def mode_table(att, rcs):
    """What each mode asks: pointing, rate, gates, RCS use. Figures come from the built model at REFERENCE units; nothing is released."""
    sh = att['shadow']; mn = sh['minimum']; c = att['cases']['burnout_1100t']
    def couple(v, ax):
        t = v[ax]; return dict(torque_N_m=t['torque_N_m'], lever_m=(t.get('efficient') or {}).get('lever_m'),
                               parasitic_force_N=t['parasitic_force_N'], slew_burn_s=t['slew_start_stop']['burn_s'],
                               h2_kg_per_slew=t['slew_start_stop']['h2_kg'], sensitivity_180_min=t['sensitivity_only_180']['minutes'])
    sets = dict(as_built=rcs['as_built'], B1=rcs['variants']['B1'], B1F=rcs['variants']['B1F'])
    rcs_rows = {k: {ax: couple(v, ax) for ax in ('roll+', 'pitch+', 'yaw+')} for k, v in sets.items()}
    t90 = 90/SLEW_DEG_S/60
    return dict(
        FORWARD_PROTECTED=dict(
            purpose='high-speed cruise and burns: shield aligned to ram (15!C211)', pointing_target_deg_3sigma=HOLD_TARGET_DEG,
            geometric_limit_deg=mn['theta_max_deg'], geometric_limit_azimuth_deg=mn['phi_deg'], binding_part=mn['binding'],
            target_over_limit=round(HOLD_TARGET_DEG/mn['theta_max_deg'], 3),
            rates='minimum-impulse hold only; whole-vehicle slews FORBIDDEN', flip='FORBIDDEN in unshielded high-speed travel (15!C211)',
            comms='Earth by gimbal only; burns need no Earth LOS (15!C210)', gates=['shield aligned', 'dust / disturbance allowance OPEN'],
            open=['disturbance torques', 'sensor / actuator noise', 'dust allowance', 'real safe tolerance < geometric limit (63)']),
        LOW_HAZARD_SLEW=dict(
            purpose='orientation changes only where the hazard allows (below the dust-speed limit, OPEN)',
            reference_rate_deg_s=SLEW_DEG_S, minutes_per_90_deg_at_rate=round(t90, 1),
            flip_sensitivity_only=dict(ideal_180_min_as_built=round(att['modes']['axes']['pitch+']['flip_180_min'], 1),
                                       note='21-minute IDEAL flip from CAD inertia: SENSITIVITY ONLY, never an operational rate (15!H211)'),
            gates=['speed below the dust limit (OPEN)', 'propulsion / thermal / attitude / shield constraints debited (15!H211)'],
            comms='contact may drop while booms or blades cross the Earth line; store and forward'),
        MAINTENANCE_HOLD=dict(
            purpose='a steady attitude for robotic service (AFT-R): drive off, blades cold',
            gates=['DRIVE_SAFE', 'BLADES_COLD', 'aft RCS inhibited near robot work (aft pods X -92 sit in the AFT-R track zone)'],
            finding='with the aft jets inhibited, the forward pods alone act in one plane (zero net force): they give a pure ROLL couple only; '
                    'pitch / yaw hold then needs momentum storage (Momentum Spine, 50 t power / steering bucket) or a pause in robot work',
            comms='Earth by gimbal; hold attitude chosen for the work, not for comms'),
        rcs_reference=dict(units='100 N REFERENCE per nozzle, Isp 300 s REFERENCE (15!A212 H)', sets=rcs_rows),
        inertia=dict(I_pitch_yaw_kg_m2=c['I_kg_m2'][1][1], I_roll_stationary_kg_m2=c['roll_stationary_only_kg_m2'],
                     note='CAD screen (M5 slice 2); physics.inertia OPEN'))


# ---------------------------------------------------------------- sheets (PIL)

def _font(px, bold=False):
    from PIL import ImageFont
    try:
        return ImageFont.truetype('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf', px)
    except OSError:
        return ImageFont.load_default()


def modes_sheet(att, mt, path):
    """Three panels: the pointing envelope of each mode on the shield-shadow polar (the built geometric limit per azimuth, the 0.2 deg
    target), with its rate, gates and RCS use underneath."""
    from PIL import Image, ImageDraw
    import textwrap
    W, Hp = 1500, 980; im = Image.new('RGB', (W, Hp), (14, 16, 20)); d = ImageDraw.Draw(im); f, fb, fs = _font(15), _font(19, True), _font(13)
    d.text((20, 14), 'M5 attitude modes (15!A211, L2 TARGET ONLY / HIGH-SPEED FLIP HOLD): pointing envelope over the built shield shadow', font=fb, fill=(235, 235, 235))
    sh = att['shadow']['per_azimuth']; pw = W//3; k = 62.0; cy = 330
    col = dict(FORWARD_PROTECTED=(60, 200, 120), LOW_HAZARD_SLEW=(240, 170, 60), MAINTENANCE_HOLD=(110, 170, 240))
    for n, m in enumerate(MODES):
        cx = n*pw+pw//2; info = mt[m]; c = col[m]
        d.text((n*pw+20, 52), m, font=fb, fill=c)
        for deg in (1, 2, 3, 4):
            d.ellipse((cx-deg*k, cy-deg*k, cx+deg*k, cy+deg*k), outline=(55, 58, 64)); d.text((cx+deg*k+2, cy-14), f'{deg}°', font=fs, fill=(130, 130, 130))
        pts = [(cx+r['theta_max_deg']*k*math.cos(math.radians(r['phi_deg'])), cy-r['theta_max_deg']*k*math.sin(math.radians(r['phi_deg']))) for r in sh]
        d.polygon(pts, outline=(225, 85, 85))
        if m == 'FORWARD_PROTECTED':
            r = HOLD_TARGET_DEG*k; d.ellipse((cx-r, cy-r, cx+r, cy+r), fill=c)
        elif m == 'LOW_HAZARD_SLEW':
            for a in range(0, 360, 45):
                x1, y1 = cx+4.2*k*math.cos(math.radians(a)), cy-4.2*k*math.sin(math.radians(a)); d.line((cx, cy, x1, y1), fill=c, width=2)
            d.text((cx-110, cy+4.4*k), 'any attitude, only below the dust-speed limit', font=fs, fill=c)
        else:
            r = HOLD_TARGET_DEG*k*2; d.ellipse((cx-r, cy-r, cx+r, cy+r), outline=c, width=3)
            d.text((cx-120, cy+4.4*k), 'steady hold for robot work (accuracy OPEN)', font=fs, fill=c)
        y = cy+4.4*k+30
        lines = []
        if m == 'FORWARD_PROTECTED':
            lines = [f"hold target ≤ {HOLD_TARGET_DEG}° (3σ) vs geometric limit {info['geometric_limit_deg']:.2f}° at {info['geometric_limit_azimuth_deg']:.0f}°",
                     f"bound by {info['binding_part']}; target uses {info['target_over_limit']:.0%} of the zero-margin limit",
                     'whole-vehicle slews and the 180° flip FORBIDDEN at speed', 'Earth by antenna gimbal only; no Earth LOS needed in a burn',
                     'OPEN: disturbances, sensor / actuator noise, dust allowance']
        elif m == 'LOW_HAZARD_SLEW':
            r = mt['rcs_reference']['sets']
            lines = [f"reference rate {SLEW_DEG_S}°/s: {info['minutes_per_90_deg_at_rate']:.0f} min per 90° (plus start / stop)",
                     f"start+stop H2 per pitch slew (300 s ref): as-built {r['as_built']['pitch+']['h2_kg_per_slew']:.0f} kg, "
                     f"B1 {r['B1']['pitch+']['h2_kg_per_slew']:.0f} kg, B1F {r['B1F']['pitch+']['h2_kg_per_slew']:.0f} kg",
                     f"ideal 180° {info['flip_sensitivity_only']['ideal_180_min_as_built']:.0f} min as built: SENSITIVITY ONLY",
                     'gates: below the dust limit (OPEN); propulsion / thermal / shield debited', 'comms: store and forward while booms cross the Earth line']
        else:
            lines = ['gates: DRIVE_SAFE, BLADES_COLD; aft RCS inhibited near robot work', 'forward pods alone (one plane, zero net force): pure ROLL only',
                     'pitch / yaw hold then needs momentum storage (Momentum Spine)', 'or a pause in robot work; hold accuracy OPEN',
                     'comms: Earth by gimbal, attitude set by the work']
        for line in lines:
            for w in textwrap.wrap(line, 56):
                d.text((n*pw+20, y), w, font=f, fill=(215, 215, 215)); y += 21
    d.text((20, Hp-60), 'Polar: velocity-vector tilt from +X (looking aft from ahead, right +Y, up +Z). Red: the built geometric shield-shadow limit per azimuth '
                        '(M5 slice 2, no margin).', font=fs, fill=(170, 170, 170))
    d.text((20, Hp-38), 'RCS figures per 100 N REFERENCE nozzle and 300 s REFERENCE Isp (15!A212 H). Inertia: CAD screen, physics.inertia OPEN. '
                        'Nothing here is an operational rate or a release.', font=fs, fill=(170, 170, 170))
    im.save(path)


def comms_sheet(ct, lt, path):
    """Earth visibility over a year per gimbal and distance (green clear, red blocked), coast and burn; light time; the two receiving
    scenarios with null rates; the store-and-forward backlog rule."""
    from PIL import Image, ImageDraw
    W = 1500; H = 60+len(ct)*(32+2*(16*len(DISTANCES_AU)+6))+200
    im = Image.new('RGB', (W, H), (14, 16, 20)); d = ImageDraw.Draw(im); f, fb, fs = _font(15), _font(19, True), _font(13)
    d.text((20, 14), 'M5 COAST comms contacts (15!A210, OPERATIONS STUDY / PERFORMANCE OPEN): Earth in view of the aft gimbals over one year',
           font=fb, fill=(235, 235, 235))
    x0, y = 260, 60; cw = (W-x0-40)/PHASES; rh = 16
    for name, a in ct.items():
        d.text((20, y), f'{name} gimbal  (X {a["gimbal"][0]:.1f} m)', font=_font(16, True), fill=(230, 230, 230)); y += 24
        for state in ('coast', 'burn'):
            for au in DISTANCES_AU:
                case = a['cases'][f'{au}_{state}']
                d.text((40, y), f'{state:5s} {au:>6g} AU  {case["earth_off_axis_deg"]:5.2f}°  {case["clear_fraction"]:.0%}', font=fs, fill=(190, 190, 190))
                for k, v in enumerate(case['clear']):
                    d.rectangle((x0+k*cw, y+1, x0+(k+1)*cw-1, y+rh-3), fill=(40, 170, 90) if v else (200, 70, 70))
                y += rh
            y += 6
        y += 8
    d.text((x0, y), 'columns: Earth phase over one year (Earth circles the anti-velocity axis at asin(1/d)); green clear, red blocked '
                    f'(blade / ring / shield / hull; main plume {PLUME_DEG:.0f}° cone in a burn)', font=fs, fill=(170, 170, 170))
    y += 30
    d.text((20, y), 'One-way light time: '+',  '.join(f"{r['au']} AU {r['one_way_h']:.1f} h" if r['one_way_h'] < 48 else f"{r['au']} AU {r['one_way_days']:.1f} d"
                                                     for r in lt), font=f, fill=(215, 215, 215)); y += 26
    for sc in SCENARIOS:
        d.text((20, y), f"{sc['name']} ({sc['id']}): achieved rate null, {sc['status']}", font=f, fill=(215, 215, 215)); y += 22
    d.text((20, y), 'Backlog: store and forward; data waiting = generation time since the last clear contact (bytes null until the link budget is '
                    'released). Burns need no Earth LOS (15!C210).', font=f, fill=(215, 215, 215)); y += 22
    d.text((20, y), 'No promised 0.02 Mbps at 100 AU, no constant 6000 AU connectivity, no plume-through telemetry (15!H210).', font=f, fill=(240, 170, 60))
    im.save(path)


def main(out=None):
    from spec import load
    s = load(ROOT)[0]
    att = json.loads((ROOT/'references/m5_attitude.json').read_text()); rcs = json.loads((ROOT/'references/m5_rcs_balanced.json').read_text())
    ct = contacts(s); lt = light_time(); mt = mode_table(att, rcs)
    res = dict(status='L2 TARGET ONLY / HIGH-SPEED FLIP HOLD / OPERATIONS STUDY / PERFORMANCE OPEN (S&E 15!A210:A212, 98!A116)',
               modes=mt, light_time=lt, scenarios=SCENARIOS, geometry='radial outbound coast: Sun on -X, Earth asin(1/d) off it, one turn a year '
               '(PROTOTYPE); gimbals in their COAST positions; obstacles from exterior_hardware.obstacles',
               contacts={n: dict(gimbal=a['gimbal'], clear_fraction={k: v['clear_fraction'] for k, v in a['cases'].items()}) for n, a in ct.items()},
               backlog=dict(rule='store and forward; backlog = generation time since the last clear contact', bytes=None, achieved_kbps=None,
                            display_drain_ratio=DISPLAY_DRAIN, display_note='ILLUSTRATIVE: the Godot demo drains the backlog at '
                            f'{DISPLAY_DRAIN:g} h of data per h of contact to show store-and-forward; the real rate is null (no link budget)'),
               sky=sky_grids(s), rcs_patterns=rcs_patterns(rcs),
               shadow=dict(per_azimuth=[[r['phi_deg'], r['theta_max_deg']] for r in att['shadow']['per_azimuth']],
                           shield_x_m=att['shadow']['shield_x_m'], shield_r_m=att['shadow']['shield_r_m']),
               com_m=att['cases']['burnout_1100t']['com_m'], year_s=365.25*86400, au_light_s=AU_LIGHT_S, distances_au=list(DISTANCES_AU),
               plume_deg=PLUME_DEG)
    OUT_JSON.write_text(json.dumps(res, indent=1)+'\n')
    if out is not None:
        out.mkdir(parents=True, exist_ok=True); modes_sheet(att, mt, out/'gnc_modes.png'); comms_sheet(ct, lt, out/'comms_contacts.png')
    for n, a in res['contacts'].items():
        print(n, a['clear_fraction'])
    print('limit', mt['FORWARD_PROTECTED']['geometric_limit_deg'], mt['FORWARD_PROTECTED']['binding_part'])
    return res


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path)
    a = ap.parse_args(argv); main(None if a.out is None else (a.out if a.out.is_absolute() else ROOT/a.out))
