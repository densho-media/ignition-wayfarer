#!/usr/bin/env python3
"""AMPN Phase 5: protected coil cross-section, cooling, quench, structure and the full engine mass account (research, not canon).

Reads results/optimize.json (Phase 2 optima, which already carry the audit and dust additions) and adds what the optimiser does not
price: the thermal-break stack between the hot eddy shield and the 20 K winding, sectioned quench protection, local cryoplant and
boom cryogenic loop, carriage and locks, power supplies, spares. Checks hoop and fatigue stress, breathing-mode frequency against the
20 kHz pulse, thermal contraction and expansion, erosion and displacement damage. Writes results/coilpack.json and coilpack.log.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'vertex-ron')); sys.path.insert(0, str(HERE))
import ron  # noqa: E402

SIGMA = 5.670374e-8
MU0 = 4e-7 * math.pi
I_TURN = 20e3
MIITS_CU = 1e17          # A^2 s / m^4, copper to a 300 K hot spot (LITERATURE order)
CP_HE20 = 5.2e3          # J/kg/K, supercritical He near 20 K
RHO_HE20 = 22.0          # kg/m3 at ~10 bar
FATIGUE_CFRP_1E10 = 0.6  # endurance fraction of UTS at 1e10 cycles, tension-tension (EXTRAPOLATION of 1e7-1e8 data)


def foil_leak(T_hot, T_cold, n, eps=0.05):
    """Radiative leak through n refractory foils (Mo) in vacuum, equal emissivity: q = eps sigma (Th^4 - Tc^4) / ((n+1)(2-eps))."""
    return eps * SIGMA * (T_hot ** 4 - T_cold ** 4) / ((n + 1) * (2 - eps))


def cross_section(best, dust_rows):
    """Layers of one ring from the burn-facing tip inward, with thickness, areal mass and temperature (PROTOTYPE stack)."""
    mt = best['mass_t']; add = best['add_t']
    R = best['x'][0]
    arm_aft = next((r for r in dust_rows if r['face'].startswith('ring aft')), None)
    arm_fwd = next((r for r in dust_rows if r['face'].startswith('ring forward')), None)
    hoop = 2 * math.pi * R
    L = [
        dict(layer='dust and plasma armour, C/C tiles (replaceable)', t_m=arm_aft['armour_t_m'] if arm_aft else None, T_K=2000,
             mass_t=(arm_aft['mass_t'] + arm_fwd['mass_t']) / 4 if arm_aft else None, life='replace on erosion; tiles 0.6 m',
             why='grains up to the 0.1-event design grain (dust.py NOMINAL), both faces'),
        dict(layer='W-B4C nose wedge, fluence-sized (replaceable cassettes)', t_m=None, T_K=2000, mass_t=mt.get('nose_t'),
             life='cassettes, 20-50 dpa per mission at the tip', why='keeps the 20 K winding under 3e22 n/m2 (RON rule)'),
        dict(layer='edge-on C/C fins in the ray planes', t_m=0.0028, T_K=2000, mass_t=mt.get('fins_t', 0.0) * 0.6 + add.get('nose_fins_extra_t', 0.0),
             life='permanent', why='radiate the nose heat without adding sky'),
        dict(layer='Mo eddy shield, 3 skin depths, both faces', t_m=0.0077, T_K=None, mass_t=add.get('eddy_shield_t'),
             life='permanent', why='20 kHz field ripple; radiates its heat outward edge-on'),
        dict(layer='Mo foil stack (30 foils) + 500 K intercept', t_m=0.05, T_K=500, mass_t=None, life='permanent', why='thermal break'),
        dict(layer='MLI 40 layers + 80 K shield', t_m=0.03, T_K=80, mass_t=None, life='permanent', why='thermal break'),
        dict(layer='cryostat vacuum vessel (Ti)', t_m=0.01, T_K=None, mass_t=mt.get('cryostat_t'), life='permanent', why='vacuum boundary'),
        dict(layer='REBCO winding, Cu stabiliser in Je', t_m=None, T_K=20, mass_t=mt.get('conductor_t'), life='permanent',
             why='the field'),
        dict(layer='winding support (CFRP, virial x2)', t_m=None, T_K=20, mass_t=mt.get('coil_structure_t'), life='permanent',
             why='hoop load'),
    ]
    return L, hoop


def main():
    log = []
    def say(s=''):
        print(s, flush=True); log.append(s)
    k = ron.canon()
    opt = json.loads((HERE / 'results' / 'optimize.json').read_text())
    import dust
    out = {}
    for key in [kk for kk in ('B_start', 'B_today', 'B_advanced', 'B_speculative', 'E_start', 'E_today', 'E_advanced', 'E_speculative') if kk in opt]:
        b = opt[key]
        if 'x' not in b:
            continue
        R, kap, D, S = b['x'][:4]
        say(f'== {key}: R {R:.1f} m, kappa {kap:.2f}, D {D:.0f} m, S {S:.0f} m, x{b["x"][4]:.2f}; engine {b["engine_t"]:.0f} t, departure {b["departure_t"]:,.0f} t')
        dmass, drows = dust.dust_mass_t(R, b['plug_r_m'], S, D)
        layers, hoop = cross_section(b, drows)
        heat = b['heat_W']
        # eddy shield temperature and the stack leaks
        A_sh = 2 * 2.0 * hoop                                            # both faces of a 2 m deep ribbon
        q_sh = heat.get('eddy_shield_W', 0.0) / A_sh if A_sh else 0.0
        T_sh = (q_sh / (0.85 * SIGMA)) ** 0.25 if q_sh > 0 else 300.0
        T_sh_bare = T_sh; T_sh = min(T_sh, 2300.0)
        q500 = foil_leak(T_sh, 500.0, 30)
        q80 = foil_leak(500.0, 80.0, 10, eps=0.03)                      # MLI-equivalent at the 500 K/80 K step
        q20 = 0.5                                                       # W/m2 through 40-layer MLI 80 K -> 20 K (LITERATURE order)
        leaks = dict(eddy_shield_T_K=T_sh, eddy_shield_T_bare_K=T_sh_bare, q_to_500K_W_m2=q500, q_to_80K_W_m2=q80, q_to_20K_W_m2=q20,
                     P_500K_W=q500 * A_sh, P_80K_W=q80 * A_sh, P_20K_static_W=q20 * A_sh)
        r500 = q500 * A_sh / (2 * 0.85 * SIGMA * 500.0 ** 4)            # 500 K radiator (two-sided) area
        cold = b['heat_W'].get('refrigerator_rejected_W', 0.0) / k['cold_cost']    # 20 K load the optimiser booked
        cold_total = cold + leaks['P_20K_static_W']
        P80_elec = leaks['P_80K_W'] * (300 / 80 - 1) * 3                # 80 K stage, Carnot x3
        # cryogenic loop: local cryoplant at the plug node (in the shadow); He loop only round the ring
        mdot = cold_total / (CP_HE20 * 4.0)
        d = 0.08; Lp = 2 * hoop
        vflow = mdot / (RHO_HE20 * math.pi * d * d / 4)
        dp = 0.02 * Lp / d * RHO_HE20 * vflow ** 2 / 2
        pump_W = mdot * dp / RHO_HE20
        # quench: sectioned dump; MIITs sets the discharge time for Cu inside Je
        W = b['field_ratio'] * 2.95e9 if b.get('field_ratio') else None
        Je = b.get('Je', 1.53e8)
        tau_max = 2 * MIITS_CU / (0.5 * Je) ** 2                        # Cu is about half the cable section
        Ltot = 2 * W / I_TURN ** 2 if W else None
        V_total = Ltot * I_TURN / tau_max if W else None
        n_sec = math.ceil(V_total / 5e3) if W else None
        # structure: hoop stress (virial design), breathing mode, ripple fatigue, contraction and expansion
        f_breath = math.sqrt(150e9 / 1600.0) / (2 * math.pi * R)
        ripple = 0.3 * 2.95e9 / (2 * W) if W else None                  # dB/B (eps_c 0.3)
        sig_a = 2 * ripple * 1.5e9 / 2                                  # force ~ B^2: 2 dB/B; design stress 1.5 GPa / safety 2 as mean
        sig_m = 0.75e9
        goodman = sig_a / (FATIGUE_CFRP_1E10 * 3e9) + sig_m / 3e9       # CFRP UTS 3 GPa
        contraction = 0.003 * R                                         # REBCO/steel 300 -> 20 K, radial
        w_growth = 4.5e-6 * 1700 * hoop                                 # W nose ring 300 -> 2,000 K circumference growth
        cycles = 2e4 * 4 * (b['ship']['burn1_days'] * 86400) * 2.7      # four burns ~ 2.7 x burn 1
        # displacement damage at the nose tip and armour erosion
        flu = 7.16e23 / (4 * math.pi * (R * math.hypot(kap, 1)) ** 2) * cycles / 2e4
        dpa = flu * 1e-25 * 1.0                                         # ~1 dpa per 1e25 n/m2 fast fluence in W (LITERATURE order)
        ero = next((r['erosion_m'] for r in drows if r['face'].startswith('ring aft')), None)
        # full mass account per engine
        a = b['add_t']; m = b['mass_t']
        extra = {
            'thermal_break_stack_t': A_sh * (30 * 0.025 * 10.2 + 1.5 + 2.0) / 1e3,     # 30 Mo foils 25 um, 500 K shield 1.5 kg/m2, MLI+80 K 2 kg/m2
            '500K_intercept_radiator_t': r500 * 2 * 5.0 / 1e3,
            '80K_stage_t': leaks['P_80K_W'] * 0.2 / 1e3 + P80_elec / (2 * 0.9 * SIGMA * 400 ** 4) * 5.0 / 1e3,
            'quench_sections_t': (n_sec or 0) * 0.15,                     # switch, dump lead and detection per section
            'carriage_locks_actuators_t': 0.08 * (m.get('conductor_t', 0) + m.get('coil_structure_t', 0) + m.get('cryostat_t', 0)
                                                  + m.get('nose_t', 0)) + 9.0,
            'power_supply_ramp_t': 10.0,                                  # 2 MW, 100 V class supply and dynamo, 5 kg/kW
            'he_loop_t': Lp * 6.0 / 1e3,
            'eddy_shield_fins_t': A_sh * max(0.0, (T_sh_bare / 2300.0) ** 4 - 1) / 0.7 / 2 * 5.0 / 1e3,   # edge-on fins hold the shield at 2,300 K
            'spares_replaceables_t': 0.1 * ((a.get('dust_protection_t', 0)) + m.get('nose_t', 0) + m.get('fins_t', 0)),
        }
        eng_full = b['engine_t'] + sum(extra.values())
        sh = ron.ship(k, eng_full, 4 * b['piped_W'], max(0.05, b['eta']), cant_deg=b['cant_deg'])
        say(f'  eddy shield {T_sh_bare:.0f} K bare -> {T_sh:.0f} K with fins ({q_sh / 1e3:.0f} kW/m2); leaks 500 K {q500:.0f} W/m2, 80 K {q80:.1f} W/m2; 20 K total {cold_total / 1e3:.1f} kW; '
            f'He loop {mdot:.2f} kg/s, pump {pump_W / 1e3:.2f} kW')
        say(f'  quench: W {W:.2e} J, Cu MIITs allow tau {tau_max:.1f} s, total dump voltage {V_total / 1e3:.0f} kV -> {n_sec} sections at 5 kV')
        say(f'  structure: breathing mode {f_breath:.0f} Hz vs 20 kHz pulse; ripple stress amplitude {sig_a / 1e6:.0f} MPa, Goodman {goodman:.2f} '
            f'at {cycles:.1e} cycles; winding contraction {contraction * 100:.0f} cm radial; W nose growth {w_growth:.2f} m of {hoop:.0f} m hoop (segment it)')
        say(f'  nose tip fluence {flu:.1e} n/m2 (~{dpa:.0f} dpa); armour erosion {ero * 1e3 if ero else 0:.1f} mm per mission')
        say('  added here: ' + ', '.join(f'{kk} {vv:.1f}' for kk, vv in extra.items()))
        say(f'  FULL engine {eng_full:.0f} t; departure {sh["departure_t"]:,.0f} t (was {b["departure_t"]:,.0f}); ve {sh["ve_eff_m_s"]:.3e}, '
            f'thrust {sh["thrust_N"] / 1e6:.1f} MN, a0 {sh["accel_g_departure"] * 1e3:.1f} mg, burn 1 {sh["burn1_days"]:.1f} d')
        out[key] = dict(x=b['x'], layers=layers, leaks=leaks, cold_total_W=cold_total, he_loop=dict(mdot=mdot, dp_Pa=dp, pump_W=pump_W),
                        quench=dict(W_J=W, tau_max_s=tau_max, V_total_V=V_total, sections=n_sec),
                        structure=dict(f_breath_Hz=f_breath, ripple_dB_B=ripple, sigma_a_Pa=sig_a, goodman=goodman, cycles=cycles,
                                       contraction_m=contraction, w_growth_m=w_growth),
                        damage=dict(tip_fluence=flu, dpa=dpa, erosion_m=ero), dust_t=dmass, dust_rows=drows,
                        engine_optimiser_t=b['engine_t'], extra_t=extra, engine_full_t=eng_full, ship=sh,
                        parts_t=m, additions_t=a)
    (HERE / 'results' / 'coilpack.json').write_text(json.dumps(out, indent=1, default=str))
    (HERE / 'results' / 'coilpack.log').write_text('\n'.join(log) + '\n')


if __name__ == '__main__':
    main()
