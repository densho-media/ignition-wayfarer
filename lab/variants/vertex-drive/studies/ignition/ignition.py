"""T04 ignition and target study: reproduce the Atlas, then extend it.

  python3 lab/variants/vertex-drive/studies/ignition/ignition.py          # all cases, writes results/ignition.json + results/IGNITION.md
  python3 lab/variants/vertex-drive/studies/ignition/ignition.py --quick  # the pure-model cases only (no ship solves, a few seconds)

Adapter, not a calculator change: ship numbers come from the FDP-1 calculator through convergence.py's own solve() and bisect()
(read-only imports); the pulse ledger is fourburn.architectures._pulse. New physics (gain ceiling, hot-spot boundary, D-T core,
tamper inertia, target in flight) lives in targets.py and is reported beside, never instead of, the Atlas results.
"""
import copy
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ATLAS = HERE.parents[1]
ROOT = HERE.parents[4]
sys.path.insert(0, str(ATLAS))
sys.path.insert(0, str(HERE))
import convergence as cv                     # noqa: E402  (also puts lab/variants/fdp1 on the path)
import targets as tg                         # noqa: E402
from engineering import config               # noqa: E402

YEAR = 365.25 * 86400
G0 = 9.80665
HB = 'base.overrides.pulsed.HB_calibration'
RHO = 'base.overrides.pulsed.rho_g_cc.optimistic'

# H_B cases: the calculator's calibration (D-T 7.0 g/cm2 at 20 keV) gives D-3He 44.2 g/cm2 at 100 keV. Atzeni & Meyer-ter-Vehn (2004),
# as tabulated in arXiv:2410.18054, give minimum H_B 7.3 (D-T) and 51 (D-3He); the calculator's own D-T minimum is 5.36 (39 keV).
HB_CASES = {
    'calculator (7.0 @ D-T 20 keV)': 7.0,
    'published D-3He minimum (51 g/cm2)': 7.0 * 51.0 / 44.229,
    'published D-T minimum matched (7.3 / 5.36)': 7.0 * 7.3 / 5.357,
    'spin-polarised fuel (<sv> x 1.5)': 7.0 / 1.5,
}


def committed():
    return json.loads((ATLAS / 'results/convergence.json').read_text())


# ----------------------------------------------------------------------------------------------------------------------------------
# ship-solve jobs (parallel)
# ----------------------------------------------------------------------------------------------------------------------------------

def gain_cliff(ov):
    g, good, _ = cv.bisect(ov, cv.GAIN, 100.0, 3000.0, cv.closes, n=9, log=True)
    return g


def job(spec):
    kind, name, ov = spec
    t = time.time()
    if kind == 'cliff':
        base = cv.solve(ov)
        out = {'gain_cliff': gain_cliff(ov), 'summary_at_3000': base['summary']}
    else:
        r = cv.solve(ov)
        out = {'summary': r['summary'], 'gain': r.get('gain'), 'rate_Hz': r.get('pellet_rate_Hz'), 'xray_standoff_m': r.get('xray_standoff_m'),
               'escape_share': r.get('escape_share'), 'hot_GW': r.get('hot_GW'), 'warm_GW': r.get('warm_GW')}
    print(f'{name}: {time.time() - t:.0f} s', flush=True)
    return kind, name, out


def ship_jobs(G):
    V = {k: G[k]['overrides'] for k in ('V0', 'V1', 'V2')}
    jobs = [('cliff', f'cliff_{k}', V[k]) for k in V]
    for label, c in HB_CASES.items():
        if c == 7.0:
            continue
        jobs.append(('cliff', f'cliff_V1_HB::{label}', cv.P(V['V1'], **{HB: {'DT_20keV_g_cm2': c}})))
    # gain cliff of V1 at lower compressed density (bigger, slower pulses): with the ceiling, the coupling each density needs
    for rho in (500.0, 1000.0, 1500.0, 2000.0):
        jobs.append(('cliff', f'cliff_V1_rho::{rho:g}', cv.P(V['V1'], **{RHO: rho})))
    # consistent-target frontier: V1 at lower compressed density with the gain capped by the compression ceiling
    for rho in (3000.0, 1500.0, 1000.0, 500.0):
        for ec in (0.1, 0.2, 0.3):
            G_cap = min(3000.0, ceiling_V1(rho, ec))
            jobs.append(('solve', f'frontier::rho{rho:g}::eta{ec:g}', cv.P(V['V1'], **{RHO: rho, cv.GAIN: G_cap})))
    return jobs


def ceiling_V1(rho_g_cc, eta_c_over_alpha, b=0.6716):
    """Gain ceiling at the V1 burn fraction (same ve as V0: b 0.672), with the fast-ignition ignitor added (see ignitor())."""
    ign = ignitor(rho_g_cc)
    return tg.gain_ceiling(b, rho_g_cc * 1e3, eta_c_over_alpha, ignitor_J_per_kg=ign['per_kg_driver_J'] * eta_c_over_alpha)


# The 0-D boundary gives D-T 0.17 g/cm2 at 8 keV, where published fast-ignition hot spots need about 0.6 g/cm2 (Atzeni 1999 optimum):
# the burn dynamics the 0-D model leaves out cost a factor 0.6 / 0.17 = 3.5 in rhoR. The same factor applied to the D-3He minimum
# (1.97 g/cm2 at 50 keV) gives the calibrated D-3He ignitor hot spot used below. EXTRAPOLATION.
DYNAMICS_FACTOR = 0.6 / 0.171
RHOR_HS_DHE3 = 1.97 * DYNAMICS_FACTOR


def eta_needed(G, rho_g_cc, b=0.6716, alpha=1.0):
    """Coupling eta_c at which the ceiling equals G: G = eta b eps / (alpha eps_F + eta e_ig)  ->  eta = G alpha eps_F / (b eps - G e_ig)."""
    e_ig = ignitor(rho_g_cc)['per_kg_driver_J']
    den = b * tg.EPS_DHE3 - G * e_ig
    return G * alpha * tg.fermi_energy_J_kg('DHe3', rho_g_cc * 1e3) / den if den > 0 else math.inf


def ignitor(rho_g_cc, rhoR_hs=RHOR_HS_DHE3, T_keV=50.0, eta_ig=0.2, rhoR_fuel=90.4):
    """Isochoric D-3He hot spot (calibrated, about 6.9 g/cm2 at 50 keV), delivered by a separate ignitor beam with coupling eta_ig
    (ASSUMPTION). Returned per kg of fuel, as driver energy, so it adds to the compression term."""
    rho = rho_g_cc * 1e3
    E = tg.isochoric_hotspot_J('DHe3', rhoR_hs, T_keV, rho)
    m = 4 / 3 * math.pi * (rhoR_fuel * 10 / rho) ** 3 * rho
    return {'hotspot_J': E, 'ignitor_driver_J': E / eta_ig, 'per_kg_fuel_J': E / m, 'per_kg_driver_J': E / eta_ig / m}


# ----------------------------------------------------------------------------------------------------------------------------------
# pure-model cases
# ----------------------------------------------------------------------------------------------------------------------------------

def liner_with_inertia(ks=(0.0, 0.5, 1.0)):
    """The Atlas liner table (k = 0 reproduces it) plus tamper inertial confinement on b (k > 0). Escape capture from the pulse ledger."""
    cfg = config.load('baseline'); fb = config.fourburn(cfg); sc = config.scenario(cfg, fb)
    arch, plasma = fb['architectures'], fb['plasma']
    p = sc['pulsed']; tier = 'optimistic'
    H_B = plasma.burn_parameter_kg_m2(config.v(p['burn_T_keV']), calib_DT_g_cm2=p['HB_calibration']['DT_20keV_g_cm2'])
    eps = arch.EPS_DHE3
    mus = [0.0, 0.001, 0.003, 0.01, 0.03, 0.1, 0.18, 0.3, 0.5, 1.0, 3.0]
    out = {}
    for k in ks:
        rows = []
        for rhoR_g in (1.0, 3.0, 10.0, 30.0, 90.0):
            rhoR = rhoR_g * 10.0
            line = []
            for mu in mus:
                q = arch._pulse(sc, tier, rhoR, mu)
                b = tg.tamped_burn_fraction(rhoR, H_B, mu, k)
                ve = math.sqrt(2 * q['eta_jet'] * b * eps / (1 + mu))
                line.append({'mu': mu, 'b': b, 've_km_s': ve / 1e3, 'escape_share': q['esc_x'] + q['esc_n']})
            best = max(line, key=lambda x: x['ve_km_s'])
            rows.append({'rhoR_g_cm2': rhoR_g, 'b0': line[0]['b'], 'escape0': line[0]['escape_share'], 've0_km_s': line[0]['ve_km_s'],
                         'best_mu': best['mu'], 'best_ve_km_s': best['ve_km_s'], 'gain_from_tamper': best['ve_km_s'] / line[0]['ve_km_s'] - 1,
                         'sweep': line})
        out[f'k={k:g}'] = rows
    # what fuel rhoR a tamped target needs for the mission ve (19,201 km/s), against the fuel-only 90.4 g/cm2
    ve_need = 19201.17e3
    need = {}
    for k in ks:
        best = None
        for mu in mus[:9]:
            lo, hi = 1.0, 400.0
            def ve(rr):
                q = arch._pulse(sc, tier, rr, mu)
                return math.sqrt(2 * q['eta_jet'] * tg.tamped_burn_fraction(rr, H_B, mu, k) * eps / (1 + mu))
            if ve(hi * 10) < ve_need:
                continue
            for _ in range(60):
                mid = (lo + hi) / 2
                if ve(mid * 10) >= ve_need:
                    hi = mid
                else:
                    lo = mid
            cand = {'mu': mu, 'fuel_rhoR_g_cm2': hi, 'fuel_mass_ratio_vs_untamped': (hi / 90.45) ** 3}
            if best is None or hi < best['fuel_rhoR_g_cm2']:
                best = cand
        need[f'k={k:g}'] = best
    return {'H_B_g_cm2': H_B / 10, 'tables': out, 'mission_ve_need': need,
            'note': 'b = F rhoR / (F rhoR + H_B), F = 1 + k sqrt(2 gamma mu / 3) (thin-shell inertia, EXTRAPOLATION); k = 0 is the Atlas liner '
                    'study exactly. Escape capture as the pulse ledger (hydrogen tamper opacities). Tamper compression energy not charged here.'}


def hb_check():
    pl = tg.plasma
    rows = []
    for T in (50.0, 70.0, 100.0, 150.0, 200.0):
        rows.append({'T_keV': T, 'H_B_calc_g_cm2': pl.burn_parameter_kg_m2(T) / 10})
    Tmin = min(range(30, 400), key=lambda T: pl.burn_parameter_kg_m2(float(T)))
    dTmin = min(range(5, 200), key=lambda T: pl.burn_parameter_kg_m2(float(T), 'DT'))
    return {'D-3He': rows, 'calc_min_DHe3': {'T_keV': Tmin, 'H_B': pl.burn_parameter_kg_m2(float(Tmin)) / 10},
            'calc_min_DT': {'T_keV': dTmin, 'H_B': pl.burn_parameter_kg_m2(float(dTmin), 'DT') / 10},
            'published_min': {'DT': 7.3, 'DD': 52.0, 'DHe3': 51.0, 'pB11': 73.0, 'source': 'S-T04-ATZENI-2004 via arXiv:2410.18054 (SECONDARY_VERIFIED)'},
            'b_at_90_g_cm2': {lbl: 904.5 / (904.5 + pl.burn_parameter_kg_m2(100.0, calib_DT_g_cm2=c)) for lbl, c in HB_CASES.items()},
            'rhoR_for_b0672': {lbl: pl.rhoR_needed(0.6716, pl.burn_parameter_kg_m2(100.0, calib_DT_g_cm2=c)) / 10 for lbl, c in HB_CASES.items()}}


def hotspot_cases():
    Ts_dt = [4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0, 20.0, 30.0]
    Ts = [35.0, 40.0, 50.0, 60.0, 70.0, 80.0, 100.0, 150.0, 200.0]
    dt = tg.hotspot_boundary('DT', Ts_dt)
    dh = tg.hotspot_boundary('DHe3', Ts)
    dh_lo = tg.hotspot_boundary('DHe3', Ts, range_scale=0.5)
    dh_hi = tg.hotspot_boundary('DHe3', Ts, range_scale=2.0)
    mdt = min((r for r in dt if r['rhoR_g_cm2']), key=lambda r: r['rhoR_g_cm2'])
    mdh = min((r for r in dh if r['rhoR_g_cm2']), key=lambda r: r['rhoR_g_cm2'])
    BR_p = tg.larmor_BR_T_m(); BR_a = tg.larmor_BR_T_m('alpha', 3.52, 4, 2)
    # energies: isochoric (fast ignition) at fuel density; isobaric (central hot spot) at the cold-fuel Fermi pressure
    E = {}
    for rho in (300.0, 1000.0, 3000.0):
        E[f'{rho:g}'] = {'DT_isochoric_J': tg.isochoric_hotspot_J('DT', mdt['rhoR_g_cm2'], mdt['T_keV'], rho * 1e3),
                         'DHe3_isochoric_J': tg.isochoric_hotspot_J('DHe3', mdh['rhoR_g_cm2'], mdh['T_keV'], rho * 1e3),
                         'DT_isochoric_calibrated_J': tg.isochoric_hotspot_J('DT', 0.6, 12.0, rho * 1e3),
                         'DHe3_isochoric_calibrated_J': tg.isochoric_hotspot_J('DHe3', RHOR_HS_DHE3, mdh['T_keV'], rho * 1e3),
                         'DHe3_isobaric': tg.isobaric_hotspot('DHe3', mdh['rhoR_g_cm2'], mdh['T_keV'], tg.fermi_pressure_Pa('DHe3', rho * 1e3)),
                         'fuel_radius_mm_at_90': 904.5 / (rho * 1e3) * 1e3}
    return {'DT_boundary': dt, 'DHe3_boundary': dh, 'DHe3_range_x0.5': dh_lo, 'DHe3_range_x2': dh_hi,
            'DT_min': mdt, 'DHe3_min': mdh, 'ratio_rhoR_min': mdh['rhoR_g_cm2'] / mdt['rhoR_g_cm2'],
            'ideal_window': {'DT': tg.ideal_ignition_window('DT'), 'DHe3': tg.ideal_ignition_window('DHe3')},
            'ranges_100keV_g_cm2': {'DHe3_proton': tg.range_g_cm2('DHe3', 'proton', 100.0), 'DHe3_alpha': tg.range_g_cm2('DHe3', 'alpha', 100.0),
                                    'DT_alpha_10keV': tg.range_g_cm2('DT', 'alpha', 10.0)},
            'magnetisation_BR_T_m': {'DT_alpha_rL': BR_a, 'DHe3_proton_rL': BR_p, 'published_DT_threshold': 0.6, 'published_DT_saturation': 1.0,
                                     'demonstrated_MagLIF': 0.45,
                                     'DHe3_threshold_scaled': 0.6 * BR_p / BR_a, 'DHe3_saturation_scaled': 1.0 * BR_p / BR_a},
            'hotspot_energy': E}


def compression_table(b=0.6716):
    rows = []
    for rho in (300.0, 500.0, 1000.0, 1500.0, 3000.0):
        r = rho * 1e3
        eF = tg.fermi_energy_J_kg('DHe3', r)
        ig = ignitor(rho)
        rows.append({'rho_g_cc': rho, 'fermi_MJ_per_g': eF / 1e9, 'fermi_pressure_Gbar': tg.fermi_pressure_Pa('DHe3', r) / 1e14,
                     'ceiling_per_eta': tg.gain_ceiling(b, r, 1.0),
                     'ceilings': {f'{e:g}': tg.gain_ceiling(b, r, e, ignitor_J_per_kg=ig['per_kg_driver_J'] * e) for e in (0.05, 0.1, 0.2, 0.3, 0.5)},
                     'eta_over_alpha_for': {f'{G:g}': G / tg.gain_ceiling(b, r, 1.0) for G in (581.0, 705.0, 1257.0, 3000.0)},
                     'pellet_V1': tg.pellet_at(b, tg.plasma.burn_parameter_kg_m2(100.0), r, 8.6745e12), 'ignitor': ig})
    return rows


def spark_cases(P_fus=8.6745e12, burn_s=5.69 * YEAR):
    """D-T cores inside the FDP-1 target (fuel 0.344 g at rhoR 90.4, yield 8.14e10 J, V1 power)."""
    m_g = 0.3444; rr = 90.45; E = 8.1417e10; f = P_fus / E
    rows = [tg.spark(x, rr, m_g, E, f, burn_s) for x in (0.3, 0.5, 1.0, 2.0, 3.0, 4.0)]
    # Nakao 1992 style: D-T 3 g/cm2 inside a 14 g/cm2 target (their published geometry), scaled to the same yield
    return {'rows': rows, 'rate_Hz': f, 'burn_years': burn_s / YEAR,
            'note': 'Central D-T sphere at the main-fuel density; 14.1 MeV removal opacity 0.05 cm2/g in D-3He (ASSUMPTION). '
                    'Tritium is consumed or exhausted: none is recovered. Spark energy is counted in the yield, not added.'}


def staged_case(E_comp_J=4.56e7, coupling=(0.1, 0.2), dt_gain=(10.0, 30.0), P_fus=8.6745e12, burn_s=5.69 * YEAR, Y=8.1417e10):
    """A two-stage target whose D-T primary supplies the D-3He compression energy (removes the gain ceiling). Ledger only."""
    rows = []
    eps_dt = 17.589 * 1.602176634e-13 / ((2.01410178 + 3.01604928) * 1.66053906660e-27)
    for c in coupling:
        for g in dt_gain:
            Yp = E_comp_J / c
            m_dt = Yp / (0.3 * eps_dt)                       # primary burn fraction 0.3 (ASSUMPTION)
            t = m_dt * 3.016 / 5.030
            rows.append({'stage_coupling': c, 'primary_gain': g, 'primary_yield_MJ': Yp / 1e6, 'driver_MJ': Yp / g / 1e6,
                         'overall_gain': Y / (Yp / g), 'n14_share': 0.8 * Yp / Y, 'tritium_per_pulse_mg': t * 1e6,
                         'tritium_mission_t': t * P_fus / Y * burn_s / 1e3})
    return rows


def in_flight_cases():
    rate = 212.31; E = 8.1417e10; esc = 0.011517; d = 43.19; R = 9.15e-3; m_he = 2.065e-4
    rows = []
    for v in (400.0, 1000.0, 3000.0, 9200.0, 20000.0):
        rows.append({'v_inj_m_s': v, **tg.in_flight(E, esc, rate, d, v, R, he3_mass_kg=m_he)})
    return {'rows': rows, 'note': 'FDP-1 V0 pulse (8.14e10 J, 212 Hz, X-ray stand-off 43.2 m), target 18.3 mm diameter, He-3 0.206 g. '
                                  'Plasma fluence assumes isotropic early expansion before the nozzle field turns it (upper bound).'}


def low_gear():
    """D-04: which mission phase would need more thrust at lower ve? Spiral escape at the departure acceleration, with and without."""
    a0 = 0.0069 * G0
    rows = []
    for name, dv in (('escape from a 400 km Earth orbit (spiral, ~v_circ)', 7.67e3), ('escape from GEO', 3.07e3),
                     ('solar escape from 1 AU (from Earth orbit speed)', 12.3e3), ('100 km/s course change', 1.0e5)):
        for mu in (0.0, 1.0, 3.0):
            a = a0 * math.sqrt(1 + mu)
            ve = 19201.17e3 / math.sqrt(1 + mu)
            rows.append({'phase': name, 'mu': mu, 'time_days': dv / a / 86400, 'propellant_share_of_mass': 1 - math.exp(-dv / ve)})
    C = committed()
    keep = C['variants']['V1_keep_idle_H2']['base']['summary']['departure_t'] if 'base' in C['variants']['V1_keep_idle_H2'] else None
    V1 = C['generations']['V1']['summary']['departure_t']
    return {'rows': rows, 'V1_departure_t': V1, 'V1_keep_idle_H2_departure_t': keep, 'idle_vessel_penalty_t': (keep - V1) if keep else None,
            'four_burn_mass_ratio_rows': C['cases']['ve_sweep']['rows']}


def diagnostics():
    E = 8.1417e10; f = 212.31; ve = 19201.17e3; eta_jet = 0.7797; E_beam = 2.714e7; eta_d = 0.45; d_loop = 37.3
    p = 2 * eta_jet * E / ve
    return {'pulse_period_ms': 1e3 / f, 'impulse_per_pulse_N_s': p, 'side_impulse_10pct_N_s': 0.1 * p,
            'driver_wall_plug_per_pulse_MJ': E_beam / eta_d / 1e6, 'light_time_to_loop1_us': d_loop / 2.998e8 * 1e6,
            'plasma_time_to_loop1_us': d_loop / (math.sqrt(2 * eta_jet * 0.6716 * 3.52e14) ) * 1e6,
            'dud_debris_speed_km_s': math.sqrt(2 * E_beam / 3.444e-4) / 1e3,
            'yield_per_pulse_t_TNT': E / 4.184e9}


# ----------------------------------------------------------------------------------------------------------------------------------

def run(quick=False):
    t0 = time.time()
    out = {'hb': hb_check(), 'hotspot': hotspot_cases(), 'compression': compression_table(), 'spark': spark_cases(),
           'staged': staged_case(), 'in_flight': in_flight_cases(), 'low_gear': low_gear(), 'diagnostics': diagnostics()}
    out['liner'] = liner_with_inertia()
    # reproduction of the Atlas liner table (k = 0)
    C = committed()
    ref = {r['rhoR_g_cm2']: r for r in C['cases']['liner_study']['rows']}
    out['liner_reproduction'] = [{'rhoR': r['rhoR_g_cm2'], 've0': r['ve0_km_s'], 've0_atlas': ref[r['rhoR_g_cm2']]['ve0_km_s'],
                                  'best_mu': r['best_mu'], 'best_mu_atlas': ref[r['rhoR_g_cm2']]['best_mu'],
                                  'match': abs(r['ve0_km_s'] - ref[r['rhoR_g_cm2']]['ve0_km_s']) < 1e-6 and r['best_mu'] == ref[r['rhoR_g_cm2']]['best_mu']}
                                 for r in out['liner']['tables']['k=0']]
    if not quick:
        G = cv.generations()
        with ProcessPoolExecutor(max_workers=4) as ex:
            done = list(ex.map(job, ship_jobs(G)))
        out['ship'] = {n: r for k, n, r in done}
        out['cliff_reproduction'] = {k: {'reproduced': out['ship'][f'cliff_{k}']['gain_cliff'], 'atlas': C['cases']['gain_threshold'][k],
                                         'rel_diff': out['ship'][f'cliff_{k}']['gain_cliff'] / C['cases']['gain_threshold'][k] - 1}
                                     for k in ('V0', 'V1', 'V2')}
    out['runtime_s'] = round(time.time() - t0, 1)
    (HERE / 'results').mkdir(exist_ok=True)
    name = 'ignition_quick.json' if quick else 'ignition.json'
    (HERE / 'results' / name).write_text(json.dumps(out, indent=1, default=float) + '\n')
    if not quick:
        (HERE / 'results/IGNITION.md').write_text(report(out))
    return out


def fmt(x, f='{:,.0f}'):
    return '-' if x is None else f.format(x)


def report(o):
    L = ['# T04 ignition and target results', '', '_Generated by `studies/ignition/ignition.py`; do not edit by hand. Ship numbers: FDP-1 '
         'calculator through `convergence.py` (read-only), optimistic tier, four 0.016 c burns. Labels: MODEL unless stated._', '']
    cr = o['cliff_reproduction']
    L += ['## 1. Reproduction of the Atlas', '', '| Generation | Gain cliff (this run) | Atlas | Difference |', '|---|---|---|---|']
    for k, r in cr.items():
        L.append(f'| {k} | {r["reproduced"]:,.0f} | {r["atlas"]:,.0f} | {100 * r["rel_diff"]:+.2f} % |')
    L += ['', 'Liner table (k = 0): ' + ', '.join(f'rhoR {r["rhoR"]:g}: ve {r["ve0"]:,.0f} km/s, best mu {r["best_mu"]:g} '
                                                 f'({"match" if r["match"] else "DIFFERS"})' for r in o['liner_reproduction']), '']
    h = o['hb']
    L += ['## 2. Burn parameter H_B', '', f'Calculator D-3He H_B: ' + ', '.join(f'{r["T_keV"]:g} keV {r["H_B_calc_g_cm2"]:.1f}' for r in h['D-3He'])
          + f' g/cm2; its minimum {h["calc_min_DHe3"]["H_B"]:.1f} at {h["calc_min_DHe3"]["T_keV"]} keV; its D-T minimum '
          f'{h["calc_min_DT"]["H_B"]:.2f} at {h["calc_min_DT"]["T_keV"]} keV. Published minima (Atzeni & Meyer-ter-Vehn 2004, secondary): '
          'D-T 7.3, D-D 52, D-3He 51, p-11B 73 g/cm2.', '',
          '| H_B case | b at 90.4 g/cm2 | rhoR for b 0.672 | V1 gain cliff | V1 departure t at gain 3,000 |', '|---|---|---|---|---|']
    for lbl in HB_CASES:
        key = 'cliff_V1' if HB_CASES[lbl] == 7.0 else f'cliff_V1_HB::{lbl}'
        s = o['ship'][key]
        L.append(f'| {lbl} | {h["b_at_90_g_cm2"][lbl]:.3f} | {h["rhoR_for_b0672"][lbl]:.1f} | {fmt(s["gain_cliff"])} | '
                 f'{fmt(s["summary_at_3000"].get("departure_t"))} |')
    hs = o['hotspot']
    L += ['', '## 3. Hot-spot self-heating boundary (0-D)', '',
          'Heating by charged products (Krokhin-Rozanov deposition) against optically thin bremsstrahlung and Spitzer conduction; no PdV term. '
          f'Validation: D-T minimum {hs["DT_min"]["rhoR_g_cm2"]:.2f} g/cm2 at {hs["DT_min"]["T_keV"]:g} keV (published isochoric region: '
          'T > 8 keV, rhoR > 0.25 g/cm2, Atzeni). The model is about 30 % optimistic for D-T; the D-3He/D-T ratio is the robust output.', '',
          '| T keV | D-3He rhoR_hs g/cm2 | range x0.5 | range x2 |', '|---|---|---|---|']
    for a, b, c in zip(hs['DHe3_boundary'], hs['DHe3_range_x0.5'], hs['DHe3_range_x2']):
        L.append(f'| {a["T_keV"]:g} | {fmt(a["rhoR_g_cm2"], "{:.2f}")} | {fmt(b["rhoR_g_cm2"], "{:.2f}")} | {fmt(c["rhoR_g_cm2"], "{:.2f}")} |')
    iw = hs['ideal_window']; mb = hs['magnetisation_BR_T_m']
    L += ['', f'D-3He minimum {hs["DHe3_min"]["rhoR_g_cm2"]:.2f} g/cm2 at {hs["DHe3_min"]["T_keV"]:g} keV, {hs["ratio_rhoR_min"]:.1f} x the D-T '
          f'minimum. Ideal ignition (charged power > bremsstrahlung, Te = Ti): D-T from {iw["DT"]["T_min_keV"]:g} keV; D-3He from '
          f'{iw["DHe3"]["T_min_keV"]:g} keV, best margin x{iw["DHe3"]["best_heating_over_brems"]:.1f} at {iw["DHe3"]["T_best_keV"]:g} keV '
          f'(D-T x{iw["DT"]["best_heating_over_brems"]:.0f}). 14.7 MeV proton range at 100 keV: {hs["ranges_100keV_g_cm2"]["DHe3_proton"]:.1f} g/cm2.', '',
          f'Magnetisation: B R for one Larmor radius, D-T alpha {mb["DT_alpha_rL"]:.2f} T m, D-3He proton {mb["DHe3_proton_rL"]:.2f} T m '
          f'(1 T m = 1 MG cm). Published D-T threshold 0.6, saturation about 1.0, MagLIF demonstrated 0.4-0.5 MG cm; scaled to protons: '
          f'threshold {mb["DHe3_threshold_scaled"]:.1f}, saturation {mb["DHe3_saturation_scaled"]:.1f} MG cm. With full trapping and '
          'suppressed conduction the rhoR limit disappears from this model: the requirement becomes B R and T >= 33-50 keV.', '',
          f'Hot-spot energies. 0-D minimum, and calibrated: D-T 0.6 g/cm2 at 12 keV (published fast-ignition optimum), D-3He x{DYNAMICS_FACTOR:.1f} '
          f'in rhoR ({RHOR_HS_DHE3:.1f} g/cm2 at 50 keV).', '',
          '| Fuel density g/cm3 | D-T 0-D J | D-T calibrated J | D-3He 0-D J | D-3He calibrated J | D-3He isobaric J (radius mm) | Fuel radius mm at 90 g/cm2 |',
          '|---|---|---|---|---|---|---|']
    for rho, e in hs['hotspot_energy'].items():
        L.append(f'| {rho} | {e["DT_isochoric_J"]:.3g} | {e["DT_isochoric_calibrated_J"]:.3g} | {e["DHe3_isochoric_J"]:.3g} | '
                 f'{e["DHe3_isochoric_calibrated_J"]:.3g} | {e["DHe3_isobaric"]["energy_J"]:.3g} '
                 f'({e["DHe3_isobaric"]["radius_mm"]:.2f}) | {e["fuel_radius_mm_at_90"]:.2f} |')
    L += ['', '## 4. Compression-energy gain ceiling (D-3He, b 0.672)', '',
          'G <= eta_c b eps / (alpha eps_F(rho) + ignitor): eta_c is driver-to-fuel coupling, alpha the adiabat. MODEL bound.', '',
          '| rho g/cm3 | eps_F MJ/g | ceiling / (eta_c/alpha) | eta_c/alpha for 705 (V1) | for 3,000 (FDP-1) | pellet g | yield t TNT | rate Hz (V1) |',
          '|---|---|---|---|---|---|---|---|']
    for r in o['compression']:
        p = r['pellet_V1']
        L.append(f'| {r["rho_g_cc"]:g} | {r["fermi_MJ_per_g"]:.0f} | {r["ceiling_per_eta"]:,.0f} | {r["eta_over_alpha_for"]["705"]:.2f} | '
                 f'{r["eta_over_alpha_for"]["3000"]:.2f} | {p["fuel_mass_g"]:.3g} | {p["yield_t_TNT"]:,.0f} | {p["rate_Hz"]:.3g} |')
    L += ['', '### Coupling needed per density (V1 gain cliff at that density against the ceiling, ignitor included)', '',
          '| rho g/cm3 | V1 gain cliff | Departure t at gain 3,000 | Ceiling per unit eta_c/alpha | eta_c/alpha needed (alpha = 1) |', '|---|---|---|---|---|']
    for rho in (500.0, 1000.0, 1500.0, 2000.0, 3000.0):
        key = 'cliff_V1' if rho == 3000.0 else f'cliff_V1_rho::{rho:g}'
        s = o['ship'][key]; G = s['gain_cliff']
        need = eta_needed(G, rho) if G else None
        L.append(f'| {rho:g} | {fmt(G)} | {fmt(s["summary_at_3000"].get("departure_t"))} | {tg.gain_ceiling(0.6716, rho * 1e3, 1.0):,.0f} | '
                 f'{fmt(need, "{:.2f}")} |')
    L += ['', '### Consistent-target frontier (V1 with the gain capped at the ceiling)', '',
          '| rho g/cm3 | eta_c/alpha | Gain used | Closes | Departure t | Rate Hz | X-ray stand-off m |', '|---|---|---|---|---|---|---|']
    for k, s in o['ship'].items():
        if not k.startswith('frontier'):
            continue
        _, rho, eta = k.split('::')
        ss = s['summary']
        L.append(f'| {rho[3:]} | {eta[3:]} | {fmt(s.get("gain"))} | {"yes" if ss.get("converged") else "no"} | {fmt(ss.get("departure_t"))} | '
                 f'{fmt(s.get("rate_Hz"), "{:.3g}")} | {fmt(s.get("xray_standoff_m"), "{:.0f}")} |')
    L += ['', '## 5. D-T core inside the FDP-1 target (V1 power, 5.69 y)', '',
          '| D-T rhoR g/cm2 | D-T mass ug | Share of yield | 14.1 MeV escaping share | Tritium per pulse ug | Tritium loaded per mission kg |',
          '|---|---|---|---|---|---|']
    for r in o['spark']['rows']:
        L.append(f'| {r["rhoR_DT_g_cm2"]:g} | {r["dt_mass_ug"]:.3g} | {r["dt_share_of_yield"]:.2e} | {r["n14_escaping_share"]:.2e} | '
                 f'{r["tritium_per_pulse_ug"]:.3g} | {r["tritium_loaded_mission_kg"]:,.1f} |')
    L += ['', '### Two-stage target (D-T primary compresses the D-3He secondary)', '',
          '| Stage coupling | Primary gain | Primary yield MJ | Driver MJ | Overall gain | 14.1 MeV share | Tritium t per mission |', '|---|---|---|---|---|---|---|']
    for r in o['staged']:
        L.append(f'| {r["stage_coupling"]:g} | {r["primary_gain"]:g} | {r["primary_yield_MJ"]:,.0f} | {r["driver_MJ"]:.1f} | {r["overall_gain"]:,.0f} | '
                 f'{r["n14_share"]:.2%} | {r["tritium_mission_t"]:,.0f} |')
    L += ['', '## 6. Tamper inertial confinement (new case beside the Atlas liner table)', '', o['liner']['note'], '',
          '| k | rhoR 1 | 3 | 10 | 30 | 90 (best mu, ve gain) |', '|---|---|---|---|---|---|']
    for k, rows in o['liner']['tables'].items():
        L.append(f'| {k} | ' + ' | '.join(f'mu {r["best_mu"]:g}, {100 * r["gain_from_tamper"]:+.1f} %' for r in rows) + ' |')
    L += ['', 'Fuel rhoR needed for the mission ve (19,201 km/s): ' + '; '.join(
        f'{k}: ' + (f'{v["fuel_rhoR_g_cm2"]:.1f} g/cm2 at mu {v["mu"]:g} (fuel mass x{v["fuel_mass_ratio_vs_untamped"]:.2f})' if v else 'not reached')
        for k, v in o['liner']['mission_ve_need'].items()), '']
    L += ['## 7. The next target in flight (FDP-1 V0 pulse)', '', o['in_flight']['note'], '',
          '| Injection m/s | Next target at m | Targets in the burn sky | X-ray J/cm2 | Plasma J/cm2 | X-ray J on target | He-3 boil-off J |', '|---|---|---|---|---|---|---|']
    for r in o['in_flight']['rows']:
        L.append(f'| {r["v_inj_m_s"]:,.0f} | {r["next_target_distance_m"]:.1f} | {r["targets_in_burn_sky"]:.1f} | {r["xray_fluence_J_cm2"]:,.3g} | '
                 f'{r["plasma_fluence_J_cm2"]:,.3g} | {r["xray_on_target_J"]:,.3g} | {r["he3_boil_off_J"]:.2f} |')
    lg = o['low_gear']
    L += ['', '## 8. Hydrogen low gear (D-04)', '', '| Phase | mu | Time days | Propellant share |', '|---|---|---|---|']
    for r in lg['rows']:
        L.append(f'| {r["phase"]} | {r["mu"]:g} | {r["time_days"]:.2f} | {r["propellant_share_of_mass"]:.2e} |')
    L += ['', f'Idle H2 vessels in V1: {fmt(lg["V1_keep_idle_H2_departure_t"])} t vs {fmt(lg["V1_departure_t"])} t departure '
          f'({fmt(lg["idle_vessel_penalty_t"])} t).', '']
    d = o['diagnostics']
    L += ['## 9. Pulse timing (diagnostics and safe stop)', '', ', '.join(f'{k} {v:.4g}' for k, v in d.items()), '',
          f'Runtime {o["runtime_s"]:.0f} s.', '']
    return '\n'.join(L)


if __name__ == '__main__':
    q = '--quick' in sys.argv
    o = run(quick=q)
    if not q:
        ok = all(abs(r['rel_diff']) < 0.01 for r in o['cliff_reproduction'].values()) and all(r['match'] for r in o['liner_reproduction'])
        print('reproduces Atlas:', ok, {k: round(v['reproduced']) for k, v in o['cliff_reproduction'].items()})
        sys.exit(0 if ok else 1)
