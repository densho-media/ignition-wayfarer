"""FDP-1: solve every variant and sensitivity, write the results JSON, the report tables and the energy-flow diagram.

  python3 lab/variants/fdp1/run.py              # all variants + sensitivities -> results/<version>/, diagrams/
  python3 lab/variants/fdp1/run.py --variant baseline

Study helper (work/); nothing in src/, tests/ or tools/ reads it. The Blender review file is built from the same engineering package
(blender/build_fdp1.py), so the numbers in the tables, the JSON and the drawn geometry are one record.
"""
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from engineering import config, model   # noqa: E402

SENSITIVITIES = {
    # name: (variant, overrides, what it isolates)
    'study_reproduction_no_feedback': ('baseline', {'integration': {'feedback': False}, 'mission': {'payload': {'source': 'reference', 'reference_t': 860.0}}},
                                       'four-burn study as published: 100 t shield placeholder, scenario solid angle 0.002, 860 t payload'),
    'payload_860t': ('baseline', {'mission': {'payload': {'source': 'reference', 'reference_t': 860.0}}}, 'payload as the four-burn study (860 t)'),
    'payload_plus_100t': ('baseline', {'mission': {'payload': {'source': 'reference', 'reference_t': None}}}, 'mass leverage: +100 t payload'),
    'no_idle_hydrogen_vessels': ('baseline', {'integration': {'keep_idle_hydrogen_vessels': {'value': False}}}, 'the three idle H2 vessels removed'),
    'tanks_T-A': ('baseline', {'tanks': {'selected': {'value': 'T-A'}}}, 'tank layout T-A (aft stack)'),
    'tanks_T-C': ('baseline', {'tanks': {'selected': {'value': 'T-C'}}}, 'tank layout T-C (outer ring)'),
    'radiators_W3': ('baseline', {'radiators': {'layout': {'value': 'W3'}}}, 'three warm wings between the blades'),
    'radiators_W6': ('baseline', {'radiators': {'layout': {'value': 'W6'}}}, 'six warm wings'),
    'struts_star': ('baseline', {'nozzle': {'strut_topology': {'value': 'star'}}}, 'every loop strutted straight to the shield'),
    'gain_1000': ('baseline', {'base': {'overrides': {'pulsed': {'gain': {'optimistic': 1000.0}}}}}, 'target gain 1,000 instead of 3,000 (rest optimistic)'),
    'gain_300': ('baseline', {'base': {'overrides': {'pulsed': {'gain': {'optimistic': 300.0}}}}}, 'target gain 300 (the CLASS label value), rest optimistic'),
    'house_load_half': ('baseline', {'base': {'overrides': {'pulsed': {'house_fraction': {'value': 5.0e-4}}}}}, 'target factory + controls load 0.05 % of fusion instead of 0.1 %'),
    'warm_loop_800K': ('baseline', {'base': {'overrides': {'radiators': {'warm': {'T_K': {'optimistic': 800.0}}}}}}, 'warm loop at 800 K (needs hotter power electronics)'),
    'coils_4': ('baseline', {'nozzle': {'coil_count': {'value': 4}}}, 'four nozzle loops'),
}


def solve(variant, overrides=None):
    cfg = config.load(variant, overrides)
    try:
        return model.solve(cfg)
    except (ValueError, RuntimeError, OverflowError, ZeroDivisionError) as e:
        # a diverging integration (the added mass grows faster than it lifts) is a 'does not close', reported, never hidden
        return {'variant': cfg['variant'], 'converged': False, 'reason': f'integration diverged ({type(e).__name__}: {e})',
                'requested_a0_g': config.v(cfg['mission']['a0_g']), 'max_a0_g_any_size': None, 'deficit_factor': None}


def g(x, n=1):
    return f'{x:,.{n}f}'


def summary(R):
    if not R.get('converged'):
        return {'variant': R['variant'], 'converged': False, 'requested_a0_g': R['requested_a0_g'], 'max_a0_g': R.get('max_a0_g_any_size'),
                'deficit_factor': R['deficit_factor'], 'reason': R['reason']}
    c = R['closure']; m = R['mass']
    return {'variant': R['variant'], 'converged': True, 'a0_g': c['a0_g'], 'peak_g': c['a_end_g'], 've_km_s': c['ve_km_s'],
            'departure_t': c['departure_t'], 'end_t': c['end_t'], 'propellant_t': c['propellant_t'], 'fusion_TW': c['fusion_power_TW'],
            'jet_TW': c['jet_power_TW'], 'thrust_MN': c['thrust_MN'], 'burn_years': c['burn_time_years'],
            'min_round_trip_years': R['mission']['minimum_round_trip_years'], 'shield_t': R['shield']['mass_kg']['total']/1e3,
            'structure_t': R['structure']['mass_kg']['total']/1e3, 'radiator_t': c['radiator_t'], 'tank_t': c['tank_t'],
            'drive_t': c['drive_t'], 'payload_t': R['payload_kg']/1e3, 'solid_angle': R['solid_angle']['total'],
            'warm_km2': c['radiator_area_km2']['warm'], 'hot_km2': c['radiator_area_km2']['hot'],
            'wing_layout': R['thermal']['selected_layout'], 'wing_tip_radius_m': R['thermal']['layouts'][R['thermal']['selected_layout']]['tip_radius_m'],
            'pellet_rate_Hz': R['fusion']['pellet_rate_Hz'], 'yield_t_TNT': R['fusion']['yield_per_pulse_t_TNT'],
            'checks_ok': all(x['ok'] for x in R['checks']), 'clearances_ok': all(x['ok'] for x in R['clearances'])}


# ----------------------------------------------------------------------------------------------------------------------------------
# energy-flow diagram (SVG -> PNG through the preinstalled Playwright Chromium)
# ----------------------------------------------------------------------------------------------------------------------------------

def energy_svg(R):
    f = R['fusion']; L = f['ledger_W']; P = f['gross_fusion_power_W']; circ = R['thermal']['circuits']; rad = R['thermal']['radiators']
    hot, warm = circ['hot_total_W'], circ['warm_total_W']

    def W(x):
        return f'{x/1e12:.2f} TW' if x >= 1e11 else f'{x/1e9:.2f} GW' if x >= 1e8 else f'{x/1e6:.1f} MW'

    def pct(x):
        return f'{100*x/P:.3g} %'
    C = {'fus': '#d14fd1', 'jet': '#d14fd1', 'space': '#7a6f99', 'hot': '#d9412b', 'warm': '#e8892c', 'low': '#a9cbe8', 'elec': '#5960c9',
         'drv': '#5960c9', 'fuel': '#2fa7a0'}
    boxes = []

    def box(x, y, w, h, title, sub, col, text='#111'):
        boxes.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{col}" fill-opacity="0.92" stroke="#222" stroke-width="1.5"/>'
                     f'<text x="{x+w/2}" y="{y+h/2-4}" text-anchor="middle" font-size="19" font-weight="700" fill="{text}">{title}</text>'
                     f'<text x="{x+w/2}" y="{y+h/2+19}" text-anchor="middle" font-size="15" fill="{text}">{sub}</text>')
    arrows = []

    def arrow(x0, y0, x1, y1, power, col, label, lx=None, ly=None, anchor='middle'):
        w = max(2.0, min(26.0, 3.5*math.log10(max(power, 1e6)/1e6)))
        arrows.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" stroke="{col}" stroke-width="{w:.1f}" stroke-opacity="0.75" marker-end="url(#a)"/>')
        lx = (x0+x1)/2 if lx is None else lx; ly = (y0+y1)/2-8 if ly is None else ly
        arrows.append(f'<text x="{lx}" y="{ly}" text-anchor="{anchor}" font-size="15" fill="#eee">{label}</text>')
    # columns
    box(40, 330, 230, 90, 'Fuel 3He + D', f"{R['closure']['mass_flow_kg_s']*1e3:.1f} g/s, {f['pellet_rate_Hz']:.0f} pellets/s", C['fuel'])
    box(370, 320, 270, 110, 'Pulsed D-3He burn', f"{W(P)} gross, gain {f['target_gain']:.0f}", C['fus'])
    box(370, 610, 270, 90, 'Heavy-ion drivers', f"beam {W(f['driver_beam_power_W'])}, plug {W(f['driver_wall_plug_power_W'])}", C['drv'], '#fff')
    box(40, 610, 230, 90, 'Power bus', f"recovered {W(f['recovered_power_W'])}", C['elec'], '#fff')
    box(800, 60, 330, 90, 'JET (thrust)', f"{W(L['jet'])} = {pct(L['jet'])}, {R['closure']['thrust_MN']:.2f} MN", C['jet'])
    box(800, 190, 330, 90, 'Plume to space', f"{W(L['plume_to_space'])} = {pct(L['plume_to_space'])}", C['space'], '#fff')
    box(800, 320, 330, 90, 'Radiation to space', f"X-ray/n escaping past hardware {W(L['radiation_to_space'])}", C['space'], '#fff')
    box(800, 450, 330, 100, 'HOT loop 1800 K', f"{W(hot)}  ->  {rad['hot']['planform_m2']/1e3:,.0f}k m2 planform", C['hot'], '#fff')
    box(800, 600, 330, 100, 'WARM loop 600 K', f"{W(warm)}  ->  {rad['warm']['planform_m2']/1e6:.2f} km2 planform", C['warm'])
    box(800, 750, 330, 80, 'LOW loop 300 K', f"cryo for added tanks {W(R['thermal']['low_loop']['added_cooling_W'])}", C['low'])
    box(1260, 450, 260, 100, 'Space (radiated)', 'all waste heat leaves', '#444', '#fff')
    box(1260, 600, 260, 100, 'Space (radiated)', '', '#444', '#fff')
    arrow(270, 375, 365, 375, R['closure']['mass_flow_kg_s']*R['closure']['ve_km_s']**2*1e6, C['fuel'], 'pellets')
    arrow(505, 610, 505, 435, f['driver_beam_power_W'], C['drv'], 'beam pulses', 560, 520)
    arrow(270, 655, 365, 655, f['electric_load_W'], C['elec'], 'electric', 318, 645)
    arrow(640, 340, 795, 105, L['jet'], C['jet'], 'directed exhaust')
    arrow(640, 360, 795, 235, L['plume_to_space'], C['space'], 'off-axis plume')
    arrow(640, 380, 795, 365, L['radiation_to_space'], C['space'], 'escaping X-rays, neutrons', 718, 350)
    arrow(640, 410, 795, 495, hot, C['hot'], f"on hardware {pct(hot)}", 690, 470)
    arrow(640, 690, 795, 650, f['driver_wall_plug_power_W']-f['driver_beam_power_W']+L['electric_house'], C['warm'], 'driver + house losses', 720, 690)
    arrow(1130, 500, 1255, 500, hot, C['hot'], '')
    arrow(1130, 650, 1255, 650, warm, C['warm'], '')
    arrow(1130, 790, 1255, 680, R['thermal']['low_loop']['added_cooling_W'], C['low'], '')
    arrow(380, 425, 200, 605, f['recovered_power_W'], C['elec'], 'inductive recovery', 215, 520, 'start')
    ok = R['thermal']['circuits']['unaccounted_W']
    foot = (f"FDP-1 {R['version']} / {R['variant']}: {R['architecture']} {R['tier']} tier. Arrow widths are logarithmic. "
            f"Ledger closes to {sum(f['ledger_per_W_fusion'].values()):.9f} of gross fusion; unaccounted heat {ok:.3g} W.")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="1560" height="900" viewBox="0 0 1560 900" font-family="DejaVu Sans, sans-serif">'
            f'<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="16" markerHeight="16" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#ddd"/></marker></defs>'
            f'<rect width="1560" height="900" fill="#1e2024"/>'
            f'<text x="40" y="40" font-size="26" font-weight="700" fill="#fff">FDP-1 energy flow at departure ({R["closure"]["a0_g"]:.4f} g, {W(P)} fusion)</text>'
            + ''.join(arrows)+''.join(boxes)+f'<text x="40" y="880" font-size="15" fill="#bbb">{foot}</text></svg>')


def svg_to_png(svg_path, png_path):
    js = f"""const {{chromium}}=require('playwright');(async()=>{{const b=await chromium.launch();const p=await b.newPage({{viewport:{{width:1560,height:900}}}});
await p.goto('file://{svg_path}');await p.screenshot({{path:'{png_path}'}});await b.close();}})();"""
    try:
        subprocess.run(['node', '-e', js], check=True, capture_output=True, timeout=120)
        return True
    except Exception as e:
        print('PNG conversion skipped:', e)
        return False


# ----------------------------------------------------------------------------------------------------------------------------------

def tables(results, sens):
    B = results['baseline']; c = B['closure']; out = []
    out.append('# FDP-1 result tables (generated by run.py; do not edit)\n')
    out.append('## Variants\n\n| variant | closes | a0 g | peak g | departure t | end t | propellant t | fusion TW | thrust MN | engine years | min round trip y | shield t | radiators t | tanks t |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for k, R in results.items():
        s = summary(R)
        if s['converged']:
            out.append(f"| {k} | yes | {s['a0_g']:.4f} | {s['peak_g']:.4f} | {g(s['departure_t'],0)} | {g(s['end_t'],0)} | {g(s['propellant_t'],0)} | {s['fusion_TW']:.2f} | {s['thrust_MN']:.3f} | {s['burn_years']:.2f} | {s['min_round_trip_years']:.2f} | {g(s['shield_t'],0)} | {g(s['radiator_t'],0)} | {g(s['tank_t'],0)} |")
        else:
            out.append(f"| {k} | **no** | {s['requested_a0_g']:.4f} | | | | | | | | | | | max a0 {s['max_a0_g']:.4f} g, deficit x{s['deficit_factor']:.0f} |" if s['max_a0_g'] else f"| {k} | **no** | | | | | | | | | | | | {s['reason']} |")
    out.append('\n## Sensitivities (baseline unless named)\n\n| case | what it isolates | departure t | Δ vs baseline t | a0 g | engine years |\n|---|---|---|---|---|---|')
    for k, (R, why) in sens.items():
        s = summary(R)
        if s['converged']:
            out.append(f"| {k} | {why} | {g(s['departure_t'],0)} | {s['departure_t']-c['departure_t']:+,.0f} | {s['a0_g']:.4f} | {s['burn_years']:.2f} |")
        else:
            out.append(f"| {k} | {why} | does not close: {s['reason']} | | max {s['max_a0_g']:.4f} |" if s['max_a0_g'] else f"| {k} | {why} | does not close: {s['reason']} | | | |")
    out.append('\n## Four-burn mass history (baseline)\n\n| burn | start t | end t | propellant t | days | distance AU | accel start g | accel end g | Δv km/s |\n|---|---|---|---|---|---|---|---|---|')
    for b in B['mission']['burns']:
        out.append(f"| {b['burn']} | {g(b['start_mass_t'],0)} | {g(b['end_mass_t'],0)} | {g(b['propellant_t'],0)} | {b['duration_days']:.0f} | {b['distance_AU']:.0f} | {b['accel_start_g']:.4f} | {b['accel_end_g']:.4f} | {b['delta_v_km_s']:.1f} |")
    out.append('\n## Round trips (baseline)\n\n| destination AU | engine years | coast years | total years |\n|---|---|---|---|')
    for t in B['mission']['round_trips']:
        out.append(f"| {t['destination_AU']:,.0f} | {t['engine_years']:.2f} | {t['coast_years']:.2f} | {t['total_years']:.2f} |")
    out.append('\n## Mass breakdown (baseline)\n\n| item | t | share of departure |\n|---|---|---|')
    for k, x in B['mass']['items_kg'].items():
        out.append(f"| {k} | {g(x/1e3)} | {100*x/B['mass']['departure_kg']:.2f} % |")
    out.append(f"| **departure** | **{g(B['mass']['departure_kg']/1e3)}** | 100 % |")
    out.append('\n## Energy and radiation ledger (baseline, share of gross fusion)\n\n| channel | W | share |\n|---|---|---|')
    P = B['fusion']['gross_fusion_power_W']
    for k, x in B['fusion']['ledger_W'].items():
        out.append(f"| {k} | {x:.4g} | {100*x/P:.4f} % |")
    out.append(f"| **sum** | {sum(B['fusion']['ledger_W'].values()):.6g} | {100*sum(B['fusion']['ledger_per_W_fusion'].values()):.6f} % |")
    out.append('\n### Heat circuits\n\n| circuit | source | W |\n|---|---|---|')
    for circ in ('hot_W', 'warm_W'):
        for k, x in B['thermal']['circuits'][circ].items():
            out.append(f"| {circ[:-2]} | {k} | {x:.4g} |")
    out.append(f"| low | added cryocooling | {B['thermal']['low_loop']['added_cooling_W']:.4g} |")
    out.append('\n## Radiator study (baseline)\n\n| layout | wings | azimuths | span m | tip radius m | area penalty | extra mass t | note |\n|---|---|---|---|---|---|---|---|')
    for k, w in B['thermal']['layouts'].items():
        out.append(f"| {k}{' (selected)' if k == B['thermal']['selected_layout'] else ''} | {w['wings']} | {w['azimuths_deg']} | {w['span_m']:,.0f} | {w['tip_radius_m']:,.0f} | {w.get('area_penalty', float('nan')):.3f} | {w.get('extra_mass_kg', float('nan'))/1e3:,.0f} | {w['note']} |")
    rad = B['thermal']['radiators']
    out.append(f"\nHot: {rad['hot']['planform_m2']:,.0f} m² planform at {rad['hot']['T_K']:.0f} K ({rad['hot']['mass_kg']/1e3:,.0f} t), of which the three existing blades carry {rad['hot']['reused_m2']:,.0f} m². "
               f"Warm: {rad['warm']['planform_m2']:,.0f} m² at {rad['warm']['T_K']:.0f} K ({rad['warm']['mass_kg']/1e3:,.0f} t). Areas are the four-burn closure's, never reduced to fit.")
    ts = B['tanks']['summary']
    out.append('\n## Tank comparison (baseline)\n\n| species | required m³ | existing m³ | ratio | deficit m³ | loaded t |\n|---|---|---|---|---|---|')
    for sp in ('helium_3', 'deuterium', 'hydrogen'):
        out.append(f"| {sp} | {ts['required_m3'][sp]:,.0f} | {ts['existing_m3'][sp]:,.0f} | {ts['ratio'][sp]:.2f} | {ts['deficit_m3'][sp]:,.0f} | {ts['loaded_t'][sp]:,.1f} |")
    out.append(f"\nOutcome: **{ts['outcome']}**. Tank mass {ts['tank_mass_kg']/1e3:,.0f} t, cryocooling {ts['cooling_W']/1e6:.2f} MW, axial load at 1.5 g {ts['axial_load_1p5g_N']/1e6:,.0f} MN "
               f"({ts['axial_load_ratio_1p5g']:.1f}x the existing farm's), idle hydrogen volume {ts['idle_hydrogen_m3']:,.0f} m³.\n")
    out.append('| option | where | added vessels | added length m | max radius m | added He-3 m³ | added D m³ | spare He-3 / D m³ |\n|---|---|---|---|---|---|---|---|')
    for k, o in B['tanks']['options'].items():
        out.append(f"| {k}{' (selected)' if k == B['tanks']['selected'] else ''} | {o['where']} | {o['count']} | {o['added_length_m']:.1f} | {o['max_radius_m']:.1f} | {o['added_m3']['helium_3']:,.0f} | {o['added_m3']['deuterium']:,.0f} | {o['spare_m3']['helium_3']:,.0f} / {o['spare_m3']['deuterium']:,.0f} |")
    cm = B['com']
    out.append(f"\nCentre of mass: baseline dry ship x = {cm['baseline_dry_x_m']:.1f} m; FDP-1 end (dry) x = {cm['fdp1_end_x_m']:.1f} m; departure x = {cm['fdp1_departure_x_m']:.1f} m; propellant centroid x = {cm['propellant_centroid_x_m']:.1f} m.")
    out.append('\n## Shield\n')
    sh = B['shield']
    out.append(f"LiH core {sh['lih_core_m']:.2f} m + annulus {sh['lih_annulus_m']:.2f} m, W face {sh['w_face_m']*100:.0f} cm (needs {sh['w_needed_m']*1000:.1f} mm); crew cone {sh['crew_half_angle_deg']:.2f}°, hardware cone {sh['hardware_half_angle_deg']:.2f}° (set by {sh['hardware_cone_set_by']}); "
               f"neutron decades {sh['neutron_decades']:.1f}, X-ray decades {sh['xray_decades']:.1f}; radius {sh['radius_hw_aft_m']:.2f}-{sh['radius_hw_fwd_m']:.2f} m; mass {sh['mass_kg']['total']/1e3:,.0f} t (the four-burn placeholder was {sh['placeholder_kg']/1e3:.0f} t).\n")
    out.append('| part | t |\n|---|---|')
    for k, x in sh['mass_kg'].items():
        out.append(f"| {k} | {x/1e3:,.1f} |")
    out.append('\n## Solid angle seen by the burn (fed back into the closure)\n\n| part | share of 4π |\n|---|---|')
    for k, x in B['solid_angle']['shares'].items():
        out.append(f"| {k} | {x:.5f} |")
    out.append(f"| **total** | **{B['solid_angle']['total']:.5f}** (four-burn scenario assumed {B['solid_angle']['scenario_value']}) |")
    out.append('\n## Checks (baseline)\n\n| check | ok | detail |\n|---|---|---|')
    for x in B['checks']:
        out.append(f"| {x['check']} | {'yes' if x['ok'] else '**NO**'} | {x['detail']} |")
    out.append('\n## Clearances (baseline)\n\n| item | value | unit | required | ok |\n|---|---|---|---|---|')
    for x in B['clearances']:
        out.append(f"| {x['item']} | {x['value']} | {x['unit']} | {x['required']} | {'yes' if x['ok'] else '**NO**'} |")
    return '\n'.join(out)+'\n'


def main():
    a = argparse.ArgumentParser(); a.add_argument('--variant'); a.add_argument('--no-sensitivities', action='store_true')
    a = a.parse_args()
    base_cfg = config.load()
    out = HERE/'results'/base_cfg['version']; out.mkdir(parents=True, exist_ok=True)
    (HERE/'diagrams').mkdir(exist_ok=True)
    names = [a.variant] if a.variant else config.variants()
    results = {}
    for n in names:
        R = solve(n); results[n] = R
        (out/f'{n}.json').write_text(json.dumps(R, indent=1, default=float))
        print(n, json.dumps(summary(R), default=float))
        if R.get('converged'):
            svg = HERE/'diagrams'/f'energy_flow_{n}.svg'; svg.write_text(energy_svg(R))
            svg_to_png(svg, HERE/'diagrams'/f'energy_flow_{n}.png')
    if a.variant:
        return
    sens = {}
    if not a.no_sensitivities:
        pay = results['baseline']['payload_kg']/1e3
        for k, (var, ov, why) in SENSITIVITIES.items():
            if k == 'payload_plus_100t':
                ov = {'mission': {'payload': {'source': 'reference', 'reference_t': pay+100.0}}}
            R = solve(var, ov); sens[k] = (R, why)
            print(k, json.dumps(summary(R), default=float))
        b = results['baseline']['closure']['departure_t']; p = sens['payload_plus_100t'][0]
        lev = (p['closure']['departure_t']-b)/100.0 if p.get('converged') else None
        (out/'sensitivities.json').write_text(json.dumps({k: {'why': w, 'summary': summary(R)} for k, (R, w) in sens.items()} | {'mass_leverage_t_per_t': lev}, indent=1, default=float))
    (out/'summary.json').write_text(json.dumps({k: summary(R) for k, R in results.items()}, indent=1, default=float))
    t = tables(results, sens)
    if sens:
        lev = json.loads((out/'sensitivities.json').read_text())['mass_leverage_t_per_t']
        t += f'\nMass leverage: each added tonne of dry mass costs {lev:.1f} t of departure mass (baseline, +100 t payload case).\n'
    (out/'TABLES.md').write_text(t)
    print('wrote', out)


if __name__ == '__main__':
    main()
