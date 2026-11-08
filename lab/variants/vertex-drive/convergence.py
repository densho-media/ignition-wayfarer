"""Vertex Drive Technology Atlas: convergence analysis of the three Vertex generations against the mission benchmarks.

  python3 lab/variants/vertex-drive/convergence.py      # writes results/convergence.json and results/CONVERGENCE.md (about 3-6 min)

Adapter, not a new physics model: every ship number comes from the FDP-1 calculator (lab/variants/fdp1, run.solve with overrides), which
itself calls the four-burn study's engine. The liner study calls the four-burn pulse ledger (fourburn.architectures._pulse) directly.
Nothing here changes FDP-1, the four-burn study, data/ or src/; generation changes come from registry/generations.toml, each tied to a
technology record. Benefits no model quantifies are reported as bands, never folded into a generation.
"""
import copy
import json
import math
import sys
import time
import tomllib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FDP1 = ROOT / 'lab/variants/fdp1'
sys.path.insert(0, str(FDP1))
import run as fdp1                     # noqa: E402
from engineering import config         # noqa: E402

SIX_YEARS = 6.0                       # canon mission duration (LOCKED)
G_TARGETS = (1.0, 1.5)                # spin-gravity range used as a thrust benchmark: what a 1-1.5 g drive would need
C_KM_S = 299792.458


# ----------------------------------------------------------------------------------------------------------------------------------
# overrides
# ----------------------------------------------------------------------------------------------------------------------------------

def put(tree, path, value):
    keys = path.split('.')
    node = tree
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = value
    return tree


def merge(a, b):
    out = copy.deepcopy(a)
    for k, v in b.items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def generations():
    with open(HERE / 'registry/generations.toml', 'rb') as f:
        G = tomllib.load(f)['generation']
    out = {}
    for g in G:
        ov = {}
        for c in g.get('change', []):
            put(ov, c['path'], c['value'])
        out[g['id']] = {'record': g, 'overrides': ov}
    return out


def with_paths(base, **paths):
    ov = copy.deepcopy(base)
    for p, v in paths.items():
        put(ov, p.replace('__', '.'), v)
    return ov


A0 = 'mission.a0_g.value'
GAIN = 'base.overrides.pulsed.gain.optimistic'
ETA = 'base.overrides.pulsed.nozzle_efficiency.optimistic'
PTW = 'base.overrides.continuous.plume_to_hardware.value'
WARM = 'base.overrides.radiators.warm.T_K.optimistic'
HOUSE = 'base.overrides.pulsed.house_fraction.value'
DRIVER = 'base.overrides.pulsed.driver_efficiency.optimistic'
GALLERY = 'drivers.gallery_radius_m.value'
H2 = 'integration.keep_idle_hydrogen_vessels.value'


def P(ov, **kv):
    out = copy.deepcopy(ov)
    for k, v in kv.items():
        put(out, k, v)
    return out


# ----------------------------------------------------------------------------------------------------------------------------------
# solving
# ----------------------------------------------------------------------------------------------------------------------------------

def solve(ov):
    R = fdp1.solve('baseline', ov)
    s = fdp1.summary(R)
    if not R.get('converged'):
        return {'summary': s}
    L = R['fusion']['ledger_W']; Pf = R['fusion']['gross_fusion_power_W']; lay = R['layout']
    return {'summary': s, 'ledger_share': {k: L[k] / Pf for k in L},
            'hot_GW': R['thermal']['circuits']['hot_total_W'] / 1e9, 'warm_GW': R['thermal']['circuits']['warm_total_W'] / 1e9,
            'loop_radii_m': [l['r'] for l in R['nozzle']['loops']], 'hardware_cone_deg': R['shield']['hardware_half_angle_deg'],
            'burn_aft_of_shield_m': lay['d_shield'], 'xray_standoff_m': R['fusion']['xray_standoff_m'],
            'escape_share': R['fusion']['xray_escape_fraction'] + R['fusion']['neutron_escape_fraction'],
            'jet_specific_energy_J_kg': 0.5 * (R['closure']['ve_km_s'] * 1e3) ** 2,
            'gain': R['fusion']['target_gain'], 'pellet_rate_Hz': R['fusion']['pellet_rate_Hz']}


def closes(r):
    return bool(r['summary'].get('converged'))


def bisect(ov, path, lo, hi, ok, n=9, log=False):
    """Boundary of `ok` on [lo, hi] where ok(hi) differs from ok(lo); returns (boundary, last solve on the ok side)."""
    f = (lambda x: math.log(x)) if log else (lambda x: x)
    finv = (lambda y: math.exp(y)) if log else (lambda y: y)
    a, b = f(lo), f(hi)
    ra, rb = solve(P(ov, **{path: lo})), solve(P(ov, **{path: hi}))
    oa, ob = ok(ra), ok(rb)
    if oa == ob:
        return None, (ra if oa else None), oa
    good = ra if oa else rb
    for _ in range(n):
        m = (a + b) / 2; rm = solve(P(ov, **{path: finv(m)})); om = ok(rm)
        if om == oa:
            a, ra = m, rm
        else:
            b, rb = m, rm
        good = ra if oa else rb
    return finv(a if oa else b), good, oa


def benchmarks(name, ov):
    t = time.time()
    base = solve(ov)
    s = base['summary']
    a0 = config.v(config.load('baseline', ov)['mission']['a0_g'])
    out = {'generation': name, 'base': base, 'a0_g': a0}
    # four 0.016 c burns at the FDP-1 departure acceleration
    out['four_burn_closes'] = closes(base)
    # ceiling: highest departure acceleration any size of this ship reaches
    ceil, rc, _ = bisect(ov, A0, a0, 0.05, closes, n=10)
    out['max_a0_g'] = ceil if ceil else (a0 if closes(base) else None)
    out['g_deficit'] = {f'{g:g}': (g / out['max_a0_g'] if out['max_a0_g'] else None) for g in G_TARGETS}
    # six-year benchmark: the lowest a0 whose minimum round trip fits the LOCKED 6.0 y mission
    if closes(base) and s['min_round_trip_years'] <= SIX_YEARS:
        out['six_year'] = {'met_at_base_a0': True, 'a0_g': a0, 'departure_t': s['departure_t'], 'min_round_trip_years': s['min_round_trip_years']}
    elif out['max_a0_g']:
        fits = lambda r: closes(r) and r['summary']['min_round_trip_years'] <= SIX_YEARS
        b6, r6, _ = bisect(ov, A0, a0, out['max_a0_g'] * 0.999, fits, n=10)
        out['six_year'] = ({'met_at_base_a0': False, 'a0_g': b6, 'departure_t': r6['summary']['departure_t'],
                            'min_round_trip_years': r6['summary']['min_round_trip_years'], 'burn_years': r6['summary']['burn_years']}
                           if r6 else {'met_at_base_a0': False, 'a0_g': None, 'reason': 'no closing a0 reaches 6.0 y'})
    else:
        out['six_year'] = {'met_at_base_a0': False, 'a0_g': None, 'reason': 'does not close'}
    # breakthrough thresholds: the target gain and the nozzle efficiency at which the ship stops closing
    g_lo, _, _ = bisect(ov, GAIN, 100.0, 3000.0, closes, n=9, log=True)
    out['gain_threshold'] = g_lo
    e_lo, _, _ = bisect(ov, ETA, 0.40, 0.86, closes, n=9)
    out['nozzle_efficiency_threshold'] = e_lo
    out['secs'] = round(time.time() - t, 1)
    return out


def sweep(name, ov, path, values, label):
    rows = []
    for v in values:
        r = solve(P(ov, **{path: v}))
        rows.append({'value': v, **r})
    return name, {'label': label, 'path': path, 'rows': rows}


# ----------------------------------------------------------------------------------------------------------------------------------
# VTX-04 analyses that need the pulse ledger or the rocket equation, not the whole ship
# ----------------------------------------------------------------------------------------------------------------------------------

def liner_study():
    cfg = config.load('baseline'); fb = config.fourburn(cfg); sc = config.scenario(cfg, fb)
    arch, plasma = fb['architectures'], fb['plasma']
    p = sc['pulsed']; tier = 'optimistic'
    H_B = plasma.burn_parameter_kg_m2(config.v(p['burn_T_keV']), calib_DT_g_cm2=p['HB_calibration']['DT_20keV_g_cm2'])
    eps = arch.EPS_DHE3
    mus = [0.0, 0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0]
    rows = []
    for rhoR_g in (1.0, 3.0, 10.0, 30.0, 90.0):
        rhoR = rhoR_g * 10.0; b = plasma.pulsed_burn_fraction(rhoR, H_B)
        line = []
        for mu in mus:
            q = arch._pulse(sc, tier, rhoR, mu)
            ve = math.sqrt(2 * q['eta_jet'] * b * eps / (1 + mu))
            line.append({'mu': mu, 've_km_s': ve / 1e3, 'escape_share': q['esc_x'] + q['esc_n'], 'hot_per_W': q['heat']['hot'],
                         'eta_jet': q['eta_jet']})
        best = max(line, key=lambda x: x['ve_km_s'])
        v0 = line[0]['ve_km_s']
        # analytic break-even: the tamper pays only if the jet energy it recovers per kg exceeds the jet's own specific energy
        rows.append({'rhoR_g_cm2': rhoR_g, 'burn_fraction': b, 'escape_share_untampered': line[0]['escape_share'],
                     've0_km_s': v0, 'best_mu': best['mu'], 'best_ve_km_s': best['ve_km_s'], 'gain_from_tamper': best['ve_km_s'] / v0 - 1,
                     'sweep': line})
    return {'tier': tier, 'eps_J_kg': eps, 'rows': rows,
            'note': 'Fixed fuel rhoR, tamper mu kg per kg fuel, rest optimistic. ve = sqrt(2 eta_jet b eps / (1 + mu)). Tamper-enhanced burnup '
                    '(inertial confinement by the tamper) is not modelled: b is held at the untampered value, so a burnup gain is UNKNOWN.'}


def ve_sweep(ve_km_s, departure_t):
    """VTX-04B hydrogen low gear: ve x 1/sqrt(1+mu), thrust x sqrt(1+mu) at fixed jet power; propellant ratio from the rocket equation."""
    dv = 4 * 0.016 * C_KM_S
    rows = []
    for mu in (0.0, 0.1, 0.3, 1.0, 3.0):
        ve = ve_km_s / math.sqrt(1 + mu)
        rows.append({'mu': mu, 've_km_s': ve, 'thrust_factor': math.sqrt(1 + mu), 'mass_ratio_4burns': math.exp(dv / ve),
                     'mass_ratio_vs_mu0': math.exp(dv / ve) / math.exp(dv / ve_km_s)})
    return {'delta_v_4burns_km_s': dv, 'reference_ve_km_s': ve_km_s, 'reference_departure_t': departure_t, 'rows': rows,
            'note': 'Rocket equation on the whole four-burn delta-v; tanks, radiators and drive that scale with propellant are not included, '
                    'so the real penalty is larger. Use of the low gear for short phases is a mission question (decision D-04).'}


# ----------------------------------------------------------------------------------------------------------------------------------

def tasks(G):
    V0, V1, V2 = (G[k]['overrides'] for k in ('V0', 'V1', 'V2'))
    jobs = [('gen', k, G[k]['overrides']) for k in ('V0', 'V1', 'V2')]
    jobs += [('gen', 'V1_keep_idle_H2', P(V1, **{H2: True})),
             ('gen', 'V1_driver_eff_0.30', P(V1, **{DRIVER: 0.30})),
             ('gen', 'V2_collimation_band', P(V2, **{PTW: 0.01}))]
    jobs += [('case', 'galleries_r4p5', P(V0, **{GALLERY: 4.5})),
             ('case', 'study_package_800K', P(V0, **{PTW: 0.01, WARM: 800.0, HOUSE: 5e-4, H2: False})),
             ('case', 'study_package_600K', P(V0, **{PTW: 0.01, HOUSE: 5e-4, H2: False}))]
    jobs += [('sweep', 'plume_strike_sweep', V1, PTW, [0.005, 0.01, 0.02, 0.04], 'plume-to-hardware share of the nozzle loss (VTX-03 band)'),
             ('sweep', 'nozzle_efficiency_sweep', V1, ETA, [0.65, 0.72, 0.79, 0.86], 'nozzle efficiency (VTX-03 risk and band)'),
             ('sweep', 'warm_sweep', V1, WARM, [600.0, 700.0, 800.0], 'warm-loop temperature (VTX-07A)'),
             ('sweep', 'house_sweep', V1, HOUSE, [1e-3, 5e-4, 2.5e-4], 'house load as a fraction of fusion (VTX-07C, VTX-01C)'),
             ('sweep', 'driver_efficiency_sweep', V1, DRIVER, [0.25, 0.30, 0.45], 'driver wall-plug efficiency (VTX-01B; published 0.20-0.30)')]
    return jobs


def do(job):
    kind, name = job[0], job[1]
    t = time.time()
    if kind == 'gen':
        r = benchmarks(name, job[2])
    elif kind == 'case':
        r = solve(job[2])
    else:
        _, r = sweep(name, job[2], job[3], job[4], job[5])
    print(f'{name}: {time.time() - t:.0f} s', flush=True)
    return kind, name, r


def main():
    t0 = time.time()
    G = generations()
    with ProcessPoolExecutor(max_workers=4) as ex:
        done = list(ex.map(do, tasks(G)))
    gens = {n: r for k, n, r in done if k == 'gen'}
    cases = {n: r for k, n, r in done if k in ('case', 'sweep')}
    V0 = gens['V0']['base']
    cases['V0'] = V0
    cases['liner_study'] = liner_study()
    cases['ve_sweep'] = ve_sweep(V0['summary']['ve_km_s'], V0['summary']['departure_t'])
    cases['gain_threshold'] = {g: gens[g]['gain_threshold'] for g in gens}
    out = {'fdp1_version': fdp1.solve('baseline').get('version'), 'six_year_benchmark_years': SIX_YEARS, 'g_targets': list(G_TARGETS),
           'generations': {k: {'record': {x: G[k]['record'][x] for x in ('name', 'definition', 'fictional')},
                               'changes': G[k]['record'].get('change', []), **{x: gens[k]['base'][x] for x in gens[k]['base']}, **{
                                   x: gens[k][x] for x in gens[k] if x != 'base'}} for k in ('V0', 'V1', 'V2')},
           'variants': {k: gens[k] for k in gens if k not in ('V0', 'V1', 'V2')},
           'cases': cases, 'runtime_s': round(time.time() - t0, 1)}
    must = G['V0']['record']['must_reproduce']
    d = out['generations']['V0']['summary'].get('departure_t', 0)
    out['v0_reproduces_fdp1'] = abs(d - must['departure_t']) <= must['tolerance'] * must['departure_t']
    (HERE / 'results').mkdir(exist_ok=True)
    (HERE / 'results/convergence.json').write_text(json.dumps(out, indent=1, default=float) + '\n')
    (HERE / 'results/CONVERGENCE.md').write_text(report(out))
    print(f'V0 reproduces FDP-1: {out["v0_reproduces_fdp1"]} ({d:,.0f} t); {out["runtime_s"]} s')
    return 0 if out['v0_reproduces_fdp1'] else 1


def f(x, fmt='{:,.0f}', none='-'):
    return none if x is None else fmt.format(x)


def report(o):
    L = ['# Vertex convergence', '', '_Generated by `convergence.py`; do not edit by hand. Every ship number is an FDP-1 calculator result '
         f'({o["fdp1_version"]}), optimistic tier, four 0.016 c burns._', '',
         '## Generations against the benchmarks', '',
         '| Generation | Closes at FDP-1 a0 | Departure t | a0 g | Min round trip y | Six-year a0 g (departure t) | Ceiling a0 g | 1 g deficit | Gain cliff | Nozzle-eff. cliff |',
         '|---|---|---|---|---|---|---|---|---|---|']
    rows = list(o['generations'].items()) + list(o['variants'].items())
    for k, g in rows:
        s = g['summary'] if 'summary' in g else g['base']['summary']
        six = g['six_year']
        six_txt = f'{f(six.get("a0_g"), "{:.4f}")} ({f(six.get("departure_t"))})' if six.get('a0_g') else six.get('reason', '-')
        L.append(f'| {k} | {"yes" if g["four_burn_closes"] else "no"} | {f(s.get("departure_t"))} | {f(g["a0_g"], "{:.4f}")} | '
                 f'{f(s.get("min_round_trip_years"), "{:.2f}")} | {six_txt} | {f(g["max_a0_g"], "{:.4f}")} | '
                 f'{f(g["g_deficit"]["1"], "{:,.0f}x")} | {f(g["gain_threshold"])} | {f(g["nozzle_efficiency_threshold"], "{:.3f}")} |')
    L += ['', 'Gain cliff: lowest target gain at which the ship still closes (FDP-1 assumes 3,000; demonstrated 4.1, D-T). Nozzle-efficiency',
          'cliff: lowest nozzle efficiency that closes (assumed 0.79). 1 g deficit: how many times the ceiling acceleration falls short of 1 g.', '']
    for k in ('V0', 'V1', 'V2'):
        g = o['generations'][k]
        L += [f'### {k}: {g["record"]["name"]}', '', g['record']['definition'], '', f'Fictional content: {g["record"]["fictional"]}', '']
        if g['changes']:
            L += ['| Change | Value | Technology | Basis | Decision | Rationale |', '|---|---|---|---|---|---|']
            for c in g['changes']:
                L.append(f'| `{c["path"]}` | {c["value"]} | {c["technology"]} | {c["basis"]} | {c.get("needs_decision", "-")} | {c["rationale"]} |')
            L.append('')
        s = g['summary']
        if s.get('converged'):
            ls = g['ledger_share']
            L += [f'Departure {s["departure_t"]:,.0f} t, fusion {s["fusion_TW"]:.2f} TW, burn {s["burn_years"]:.2f} y, shield {s["shield_t"]:,.0f} t, '
                  f'warm {s["warm_km2"]:.2f} km2 (wing tip {s["wing_tip_radius_m"]:,.0f} m), hot {g["hot_GW"]:.1f} GW, warm {g["warm_GW"]:.1f} GW, '
                  f'loops r {", ".join(f"{r:.1f}" for r in g["loop_radii_m"])} m, hardware cone {g["hardware_cone_deg"]:.1f} deg, '
                  f'solid angle {s["solid_angle"]:.4f}, checks {"pass" if s["checks_ok"] else "FAIL"}.', '',
                  'Energy ledger (share of fusion): ' + ', '.join(f'{a} {100 * v:.3g} %' for a, v in ls.items()), '']
    L += ['## Sensitivity bands (not credited to any generation)', '']
    for k, c in o['cases'].items():
        if isinstance(c, dict) and 'rows' in c and 'path' in c:
            L += [f'### {k}: {c["label"]}', '', '| Value | Departure t | Burn y | Warm km2 | Wing tip m | Hot GW |', '|---|---|---|---|---|---|']
            for r in c['rows']:
                s = r['summary']
                L.append(f'| {r["value"]:g} | ' + (f'{s["departure_t"]:,.0f} | {s["burn_years"]:.2f} | {s["warm_km2"]:.2f} | {s["wing_tip_radius_m"]:,.0f} | {r["hot_GW"]:.1f} |'
                                                   if s.get('converged') else 'does not close | | | | |'))
            L.append('')
    L += ['### Single cases', '', '| Case | Departure t | Burn y | Warm km2 |', '|---|---|---|---|']
    for k in ('galleries_r4p5', 'study_package_800K', 'study_package_600K'):
        s = o['cases'][k]['summary']
        L.append(f'| {k} | {f(s.get("departure_t"))} | {f(s.get("burn_years"), "{:.2f}")} | {f(s.get("warm_km2"), "{:.2f}")} |')
    ls = o['cases']['liner_study']
    L += ['', '## VTX-04 liner and tamper study (four-burn pulse ledger)', '', ls['note'], '',
          '| Fuel rhoR g/cm2 | Burn fraction | Escaping share | ve, no tamper km/s | Best tamper mu | ve gain from tamper |', '|---|---|---|---|---|---|']
    for r in ls['rows']:
        L.append(f'| {r["rhoR_g_cm2"]:g} | {r["burn_fraction"]:.3f} | {100 * r["escape_share_untampered"]:.2f} % | {r["ve0_km_s"]:,.0f} | {r["best_mu"]:g} | '
                 f'{100 * r["gain_from_tamper"]:+.2f} % |')
    vs = o['cases']['ve_sweep']
    L += ['', '## VTX-04B hydrogen low gear (rocket equation)', '', vs['note'], '',
          '| mu | ve km/s | Thrust factor | Four-burn mass ratio | vs no hydrogen |', '|---|---|---|---|---|']
    for r in vs['rows']:
        L.append(f'| {r["mu"]:g} | {r["ve_km_s"]:,.0f} | {r["thrust_factor"]:.2f} | {r["mass_ratio_4burns"]:.3g} | {r["mass_ratio_vs_mu0"]:.3g}x |')
    L += ['', f'V0 reproduces FDP-1: {"yes" if o["v0_reproduces_fdp1"] else "NO"}. Runtime {o["runtime_s"]:.0f} s.', '']
    return '\n'.join(L)


if __name__ == '__main__':
    sys.exit(main())
