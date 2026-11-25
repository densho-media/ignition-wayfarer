#!/usr/bin/env python3
"""Findings of the pulse-architecture work and the slim page import (lab/studies/fusion-ignition/imports/pulse.json).

Reads results/pulse.json, magnets.json, transfer.json and frames.json; writes results/findings.json and the import. Nothing is recomputed
except ratios of numbers those files hold.

    python3 lab/studies/vertex-compact-engine/vertex-pulse/findings.py
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
R = {k: json.loads((HERE / 'results' / f'{k}.json').read_text()) for k in ('pulse', 'magnets', 'transfer', 'frames')}


def main():
    pu, mg, tr, fr = R['pulse'], R['magnets'], R['transfer'], R['frames']
    rows = pu['rows']; base = next(r for r in rows if r['label'] == 'Target mass x1')
    size = [r for r in rows if r['lever'] == 'size']
    W = pu['window']
    cb = base['capture']['burn']; co = base['capture']['operating']
    best_eq = min(pu['equal_thrust'], key=lambda r: r['heat_over'])
    dist = mg['distribution']; cases = {(c['basis'], c['distribution'].startswith('research, opt')): c for c in mg['cases']}
    op0, op1 = cases[('operating', False)], cases[('operating', True)]
    sc_best = min(op1['scenarios'], key=lambda q: q['total_t']); sc_today = op1['scenarios'][0]
    ck = fr['checks']; nets = ck['connectivity']
    sh = {s['purpose'][:6] + s['where']: s for s in tr['shells']}
    xshell = next(s for s in tr['shells'] if 'X-ray' in s['purpose'] and 'target' in s['where'])
    F = dict(
        size=(f'At the mission power ({pu["P_need_W"] / 1e12:.1f} TW per engine) the pulse size changes the rate, not the averages: from x1/64 to x16 '
              f'(the R2-B target scaled at the design areal density) thrust stays {base["thrust_N"] / 1e6:.2f} MN per engine and heat {base["heat_over"]:,.0f}x the radiator '
              f'share, because yield, X-ray share and gain ({base["gain"]:.1f}) do not move with the target mass. Smaller pulses do not reduce the average waste heat.'),
        per_pulse=(f'What smaller pulses do reduce is everything per pulse: capture energy scales with the pulse (W = {cb["W_over_E"]:.1f} x the charged energy in the research '
                   f'topology), so the design target at the mission rate ({base["Hz"] / 1e3:.0f} kHz) needs {cb["W_J"] / 1e9:.1f} GJ, inside the {pu["W_built_J"] / 1e9:.0f} GJ the drawn research '
                   f'coils hold; the surface spike on the nearest cryostat is {base["dT_K"]:,.0f} K at x1 and {size[0]["dT_K"]:.0f} K at x1/64.'),
        window=(f'No pulse size passes the surface spike, the injection speed and the nozzle transit together: the tungsten face needs the target at most x{W["mass_max_surface"]:.3f} '
                f'(spike under {W["dT_limit_K"]:.0f} K), the injector (under {pu["P"]["v_inj_max"] / 1e3:.0f} km/s, cavity collapse before the next target) at least '
                f'x{W["mass_min_injection"]:.0f}: a gap of {W["gap"]:,.0f} in target mass. Moving the face to keep x1 needs {W["face_m_for_x1"]:.0f} m from the burn (not compact).'),
        levers=(f'At equal thrust the best pulse lever is {best_eq["label"].lower()}: heat {best_eq["heat_over"]:,.0f}x against {base["heat_over"]:,.0f}x, because '
                f'its X-ray share falls to {next(r for r in rows if r["label"] == best_eq["label"])["xray_share"]:.0%}; tamping and a 3He-rich mix raise it.'),
        basis=(f'The capture energy depends on which charged share is used: the burn ledger (plasma + escaped products, {base["plasma_share"] + base["escaped_share"]:.0%} of the yield) '
               f'gives {cb["W_J"] / 1e9:.1f} GJ at the mission rate; the mission operating point ({pu["charged_share_operating"]:.0%} charged) gives {co["W_J"] / 1e9:.0f} GJ at the '
               f'same rate and 286 GJ at the design rate. The two source models are not reconciled (ENG-075).'),
        magnets=(f'Field strength is not the lever. Per-coil current distribution cuts the stored energy for the same capture from {dist["W0_J"] / 1e9:.0f} to {dist["W_J"] / 1e9:.0f} GJ '
                 f'(x{mg["floor"]["gain"]:.1f}) and the peak at the windings from {op0["B_wind_T"]:.0f} to {op1["B_wind_T"]:.0f} T, inside today\'s REBCO margin; the best scanned '
                 f'topology has W/E {mg["floor"]["best_topology_W_over_E"]:.0f} against the floor of 1. The new distribution has not been re-traced for steering (ENG-076).'),
        conductor=(f'Conductor and structure at capture (operating basis, optimised distribution): {sc_today["total_t"]:,.0f} t with today\'s REBCO and 1.5 GPa reinforcement, '
                   f'{sc_best["total_t"]:,.0f} t only with 4x current density and 6 GPa fibre (assumed, not credited). Quench: {op1["quench_modules"]} modules of '
                   f'{op1["module_energy_GJ"]:.1f} GJ each dump within {mg["P"]["t_dump_safe_s"]:.0f} s at 50 kA and 10 kV.'),
        loads=(f'The coil forces close inside the coil set: up to {op0["Fx_max_GN"]:.1f} GN on one coil (drawn distribution) against a net {abs(op0["Fx_net_MN"]):.0f} MN '
               f'(optimised {op1["Fx_max_GN"]:.1f} GN, net {abs(op1["Fx_net_MN"]):.1f} MN); the cage carries a self-balanced load, the ship sees only the thrust.'),
        extraction=(f'Extraction at equal thrust: 80 % early extraction halves the heat per newton ({tr["equal_thrust"][1]["heat_over"]:,.0f}x against '
                    f'{tr["equal_thrust"][0]["heat_over"]:,.0f}x) but needs {tr["equal_thrust"][1]["fusion_factor"]:.1f}x the fusion power and gives '
                    f'{tr["equal_thrust"][1]["exhaust_m_s"] / 1e3:,.0f} km/s ({tr["equal_thrust"][1]["ve_over_need"]:.2f} of the requirement).'),
        transfer=(f'Upstream transfer has a hard condition: the mission thrust at the mission exhaust speed means the jet must carry {tr["mission"]["jet_share_needed"]:.0%} of the '
                  f'fusion power; the coupled pulse carries {tr["mission"]["jet_share_now"]:.1%}. Charged products already give their energy to the fuel (its areal density is '
                  f'{tr["ranges"]["fuel_rhoR_g_cm2"] / tr["ranges"]["proton_g_cm2"]:.0f}x the proton range), so outside hydrogen would only lower the exhaust speed. The one '
                  f'upstream route that raises it is a low-Z shell at the target that absorbs X-rays ({xshell["column_g_cm2"]:.0f} g/cm2, {xshell["mass_over_fuel"]:.2f}x the fuel): '
                  f'exhaust {xshell["ve_over_need"]:.2f} of the need, impulse x{xshell["impulse_ratio"]:.1f}, as a cold-opacity upper bound (a shell heated to keV stops absorbing).'),
        geometry=(f'Integrated hardware: {ck["n_parts"]} parametric parts placed by search against the approved engine and each other; {len(ck["clashes"])} clashes, every network '
                  f'connected from its plant (hot {nets["hot"]["reached"]}/{nets["hot"]["parts"]}, 20 K {nets["cryo"]["reached"]}/{nets["cryo"]["parts"]}, warm '
                  f'{nets["warm"]["reached"]}/{nets["warm"]["parts"]}, electrical {nets["electrical"]["reached"]}/{nets["electrical"]["parts"]}), longest unsupported run '
                  f'{ck["max_span_m"]:.1f} m; {len([e for e in ck["exposed"] if e["kind"] == "ring"])} header in the burn\'s view, {len([e for e in ck["exposed"] if e["kind"] != "ring"])} '
                  f'line runs that need armour covers.'),
        none=('No pulse architecture, coil distribution or transfer route closes the engine. The pulse study moves the problem: smaller pulses relieve the magnets but not the heat, '
              'and the per-pulse surface load and the injector bound the size from both sides.'))
    # page import (slim)
    keep = ('label', 'lever', 'cls', 'mass_factor', 'R0_um', 'rho0_kg_m3', 'fusion_J', 'gain', 'xray_share', 'plasma_share', 'escaped_share', 'Hz', 'driver_abs_W',
            'driver_elec_W', 'thrust_N', 'exhaust_m_s', 'heat_over', 'v_inj_m_s', 'dT_K', 'stress_MPa', 'cycles_per_year', 'fluence_J_m2', 'transit_s', 'f_max_Hz', 'fails',
            'heat_vs_base')
    prow = []
    for r in rows:
        d = {k: r[k] for k in keep}
        d['W_burn_J'] = r['capture']['burn']['W_J']; d['W_op_J'] = r['capture']['operating']['W_J']; d['B_burn_T'] = r['capture']['burn']['B_burn_T']
        d['B_wind_T'] = r['capture']['burn']['B_wind_T']; d['cavity_m'] = r['capture']['burn']['cavity_built_m']; d['ripple'] = r['capture']['burn']['ripple_built']
        prow.append(d)
    future = [
        dict(area='Superconductor', need=f'{op1["B_wind_T"]:.0f} T at the winding with the optimised distribution ({op0["B_wind_T"]:.0f} T drawn)', today='REBCO about 20-30 T at 20 K',
             gap='met if the distribution holds the steering (ENG-076)', cls='CALCULATED'),
        dict(area='Structural fibre', need=f'{op0["hoop_GN"]:.1f} GN hoop (drawn distribution) at 1.5 GPa = {cases[("operating", False)]["scenarios"][0]["structure_t"]:,.0f} t', today='1.5 GPa steels and Hastelloy at 4 K',
             gap='x4 lighter at 6 GPa; not credited', cls='SCENARIO'),
        dict(area='Plasma-facing surface', need=f'{base["fluence_J_m2"] / 1e6:.1f} MJ/m2 per pulse at {pu["d_face_m"]:.1f} m, {base["Hz"] / 1e3:.0f} kHz, {base["cycles_per_year"]:.1e} cycles a year',
             today=f'tungsten: about {W["dT_limit_K"]:.0f} K spike for 300 MPa fatigue amplitude', gap=f'x{base["dT_K"] / W["dT_limit_K"]:.0f} over; a renewable or vapour-shielded face is needed', cls='CALCULATED'),
        dict(area='Target injection', need=f'{base["v_inj_m_s"] / 1e3:.0f} km/s through the collapsing cavity at x1 ({size[-1]["v_inj_m_s"] / 1e3:.0f} km/s at x16)', today='gas guns about 1 km/s, electromagnetic about 10 km/s',
             gap='x7-14; or a protected injection path (OPEN)', cls='CALCULATED'),
        dict(area='Driver', need=f'{base["driver_abs_W"] / 1e12:.1f} TW absorbed per engine at gain {base["gain"]:.0f}, {base["Hz"] / 1e3:.0f} kHz', today='no driver at this rate or power',
             gap='independent of pulse size; wall-plug 50 % assumed', cls='IMPORTED'),
        dict(area='Burn physics', need=f'jet {tr["mission"]["jet_share_needed"]:.0%} of the fusion power', today=f'R2-B coupled pulse {tr["mission"]["jet_share_now"]:.1%} (X-rays {base["xray_share"]:.0%})',
             gap='needs a photon share near 10 % and a lossless nozzle together (OPEN)', cls='CALCULATED'),
        dict(area='Control (AI)', need='target placement, timing and coil current trimmed pulse by pulse at tens of kHz', today='no number computed: the placement tolerance of the capture field is OPEN',
             gap='requirement to be set by a coupled model', cls='OPEN'),
        dict(area='Manufacture', need=f'{base["Hz"] * 3600 * 24:.1e} targets a day per engine at {base["R0_um"]:.0f} um and {base["rho0_kg_m3"] / 1e3:,.0f} g/cm3 burn density',
             today='laboratory target fabrication: a few per day', gap='several orders of magnitude', cls='CALCULATED')]
    assembly = [
        dict(title='Re-aimed tungsten lips', why='Each coil\'s burn-facing side gets a sacrificial lip aimed at the moved burn, eight modules split at the longerons so the crawler can exchange them',
             effect=f'replaces the armour aimed at the drawn burn; spike {base["dT_K"]:,.0f} K per pulse at x1', problem='ENG-074', closes=False),
        dict(title='Twin-bore lithium headers', why='One header carries supply and return along the lip edge, inside the coil\'s shadow, with a feeder into every module',
             effect=f'hot network connected ({nets["hot"]["reached"]}/{nets["hot"]["parts"]})', problem='ENG-079', closes=True),
        dict(title='20 K distribution rings', why='A ring on every cryostat skin, fed from both cage cryogen lines, so a coil keeps cooling if one feed is lost',
             effect=f'cryo network connected ({nets["cryo"]["reached"]}/{nets["cryo"]["parts"]})', problem='ENG-077', closes=True),
        dict(title='Warm manifold and headers', why='A manifold on the thrust collar rim and two headers along the cage cool the cryostat shields and frames',
             effect=f'warm network connected ({nets["warm"]["reached"]}/{nets["warm"]["parts"]})', problem='ENG-079', closes=True),
        dict(title='Supermirror strips', why='Conical strips on the lip edges, set grazing to the burn rays, turn the X-rays that would skim the lip edge',
             effect='reflect only within a few mrad; most X-ray energy still reaches the lip', problem='ENG-074', closes=False),
        dict(title='Trays and brackets', why='Busbar and instrumentation trays to the lead line; brackets wherever a run would exceed 3 m',
             effect=f'longest unsupported run {ck["max_span_m"]:.1f} m', problem='ENG-079', closes=True)]
    imp = dict(cls='CALCULATED', source='lab/studies/vertex-compact-engine/vertex-pulse (pulse.py, magnets.py, transfer.py, frames.py)', P_need_W=pu['P_need_W'],
               Hz_design=pu['Hz_design'], W_built_J=pu['W_built_J'], d_face_m=pu['d_face_m'], charged_share_operating=pu['charged_share_operating'], rows=prow,
               window=W, equal_thrust=pu['equal_thrust'],
               magnets=dict(topology=mg['topology'][:6] + [mg['topology'][-1]], distribution=dict(mult=dist['mult'], W0_J=dist['W0_J'], W_J=dist['W_J']), floor=mg['floor'],
                            cases=[{k: c[k] for k in ('basis', 'distribution', 'W_J', 'W_over_E', 'B_burn_T', 'B_wind_T', 'hoop_GN', 'Fx_max_GN', 'Fx_net_MN', 'quench_modules',
                                                      'module_energy_GJ', 'dump_steel_t')} | dict(today_t=c['scenarios'][0]['total_t'], best_t=min(q['total_t'] for q in c['scenarios']))
                                   for c in mg['cases']], built=mg['built']),
               transfer=dict(equal_thrust=tr['equal_thrust'], mission=tr['mission'], ranges=tr['ranges'], requirements=tr['requirements'],
                             shells=[{k: s[k] for k in ('where', 'purpose', 'column_g_cm2', 'mass_kg', 'mass_over_fuel', 'impulse_ratio', 've_over_need')} for s in tr['shells']]),
               frames=dict(checks=dict(n_parts=ck['n_parts'], clashes=len(ck['clashes']), connectivity=nets, max_span_m=ck['max_span_m'],
                                       exposed_headers=[e['part'] for e in ck['exposed'] if e['kind'] == 'ring'],
                                       exposed_runs=len([e for e in ck['exposed'] if e['kind'] != 'ring'])),
                           stations=[{k: s[k] for k in ('name', 'x', 'r', 'cm', 'u_deg', 'lip_half_deg', 'th_sup', 'th_cryo', 'th_warm', 'a_lip')} for s in fr['stations']],
                           replaced=fr['replaced_approved']),
               future=future, assembly=assembly, findings=F)
    (HERE / 'results' / 'findings.json').write_text(json.dumps(dict(findings=F, future=future, assembly=assembly), indent=1))
    out = ROOT / 'lab/studies/fusion-ignition/imports/pulse.json'
    out.write_text(json.dumps(imp, separators=(',', ':')))
    print(out, out.stat().st_size, 'bytes')
    for k, v in F.items():
        print(f'- {k}: {v}')


if __name__ == '__main__':
    main()
