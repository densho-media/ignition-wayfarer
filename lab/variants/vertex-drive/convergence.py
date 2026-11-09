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
        out[g['id']] = {'record': g, 'overrides': resolve(ov)}
    return out


# ----------------------------------------------------------------------------------------------------------------------------------
# Vertex adapter inputs (T00 Phase 4). They live under the `vertex` key of an override tree and never reach FDP-1 as such:
#   compression_coupling + rho_g_cc  ->  target gain at the T04 compression ceiling (studies/ignition, ceiling_V1: Fermi-degenerate
#                                        compression energy plus the calibrated fast-ignitor hot spot, burn fraction of the V1 rhoR)
#   launcher_speed_m_s               ->  pulse-rate cap so that only one target is in the open per period (T01, T04): f <= v / path,
#                                        path = muzzle (shield face) to burn point, iterated because the path grows with pulse energy
# The FDP-1 calculator is not changed; these are inputs it already has (gain, rho_g_cc, max_rep_Hz).
# ----------------------------------------------------------------------------------------------------------------------------------

RHO = 'base.overrides.pulsed.rho_g_cc.optimistic'
MAXREP = 'base.overrides.pulsed.max_rep_Hz.optimistic'
COUPLING = 'vertex.compression_coupling'
VRHO = 'vertex.rho_g_cc'
LAUNCH = 'vertex.launcher_speed_m_s'


def gain_ceiling(rho_g_cc, coupling):
    """T04's compression-consistent gain ceiling (read-only import of the T04 study; T04 owns this physics)."""
    sys.path.insert(0, str(HERE / 'studies/ignition'))
    import ignition                                   # noqa: E402  (lazy: ignition imports this module)
    return ignition.ceiling_V1(rho_g_cc, coupling)


def resolve(ov):
    """Turn vertex.compression_coupling / vertex.rho_g_cc into the FDP-1 gain and density; leave the launcher for solve()."""
    vx = ov.get('vertex', {})
    if 'compression_coupling' in vx:
        rho = vx.get('rho_g_cc', 3000.0)
        ov = P(ov, **{RHO: rho, GAIN: gain_ceiling(rho, vx['compression_coupling'])})
    return ov


def coupling_needed(rho_g_cc, gain):
    """eta_c/alpha a target of this gain and density needs under the T04 bound (inf if no coupling reaches it)."""
    sys.path.insert(0, str(HERE / 'studies/ignition'))
    import ignition                                   # noqa: E402
    return ignition.eta_needed(gain, rho_g_cc)


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
FIELD = 'base.overrides.pulsed.nozzle_field_energy_ratio.value'
DRVKG = 'base.overrides.pulsed.driver_kg_per_W.optimistic'
WAREAL = 'base.overrides.radiators.warm.areal_kg_m2.optimistic'


def P(ov, **kv):
    """Copy of ov with each dotted path set; a value of None removes the path."""
    out = copy.deepcopy(ov)
    for k, v in kv.items():
        if v is None:
            node = out
            keys = k.split('.')
            for x in keys[:-1]:
                node = node.get(x, {})
            node.pop(keys[-1], None)
        else:
            put(out, k, v)
    return out


# ----------------------------------------------------------------------------------------------------------------------------------
# solving
# ----------------------------------------------------------------------------------------------------------------------------------

def solve(ov):
    """Solve one override tree; with vertex.launcher_speed_m_s the pulse rate is capped until one target is in the open per period."""
    vx = ov.get('vertex', {})
    core = {k: v for k, v in ov.items() if k != 'vertex'}
    v_inj = vx.get('launcher_speed_m_s')
    if not v_inj:
        return _solve(core)
    f_cap, out = None, None
    for _ in range(10):
        R = fdp1.solve('baseline', core if f_cap is None else P(core, **{MAXREP: f_cap}))
        if not R.get('converged'):
            out = _pack(R); break
        path = R['injection']['path_m']; rate = R['fusion']['pellet_rate_Hz']; f_new = v_inj / path
        out = _pack(R)
        if rate <= f_new * 1.001:                          # one target in the open: the cap does not bind (or is met)
            break
        f_cap = f_new if f_cap is None else min(f_new, f_cap * 0.999)
    out['launcher'] = {'speed_m_s': v_inj, 'rate_cap_Hz': f_cap, 'path_m': out.get('injection_path_m'),
                       'binding': f_cap is not None}
    return out


def _solve(ov):
    return _pack(fdp1.solve('baseline', ov))


def _pack(R):
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
            'gain': R['fusion']['target_gain'], 'pellet_rate_Hz': R['fusion']['pellet_rate_Hz'],
            'injection_path_m': R['injection']['path_m'], 'yield_J': R['fusion']['yield_per_pulse_J'],
            'fuel_rhoR_g_cm2': R['fusion']['fuel_rhoR_g_cm2']}


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
    a0 = config.v(config.load('baseline', {k: x for k, x in ov.items() if k != 'vertex'})['mission']['a0_g'])
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
    # corrected research generations (T00 Phase 4, 2026-11-09)
    V3, V4 = G['V3']['overrides'], G['V4']['overrides']
    jobs += [('gen', k, G[k]['overrides']) for k in G if k not in ('V0', 'V1', 'V2')]
    jobs += [('gen', 'V4_keep_idle_H2', P(V4, **{H2: True}))]
    noz = [('eta_T 0.791, 15 E_p (ideal model, upper bound)', {ETA: 0.791, FIELD: 15.0}),
           ('eta_T 0.740, 10 E_p (ideal model)', {ETA: 0.740, FIELD: 10.0}),
           ('eta_T 0.64, 15 E_p (best published, read as momentum 0.80)', {ETA: 0.64, FIELD: 15.0})]
    jobs += [('multi', 'V3_nozzle_band', V3, noz, 'closure-coil nozzle efficiency: ideal model vs literature (VTX-03D, D-24)'),
             ('multi', 'V4_nozzle_band', V4, noz, 'closure-coil nozzle efficiency: ideal model vs literature (VTX-03D, D-24)'),
             ('multi', 'V4_launcher_sweep', V4, [(f'launcher {v / 1e3:g} km/s', {LAUNCH: v}) for v in (20000.0, 15000.0, 12000.0, 10000.0, 8000.0, 6000.0)],
              'one target in flight: launcher speed caps the pulse rate (VTX-01H, D-14); the generation itself assumes targets survive in flight'),
             ('multi', 'V5_launcher_sweep', G['V5']['overrides'], [(f'launcher {v / 1e3:g} km/s', {LAUNCH: v}) for v in (10000.0, 8000.0, 6000.0, 4000.0)],
              'one target in flight on the ideal-compression bound (VTX-01H, D-14)'),
             ('multi', 'V4_density_scan', V4, [(f'{r:,.0f} g/cm3, coupling 0.5', resolve_kv(r, 0.5)) for r in (1000.0, 1500.0, 2000.0, 3000.0)],
              'compressed density at coupling 0.5, gain at the T04 ceiling (VTX-01E)'),
             ('multi', 'V4_coupling_band', V4, [(f'coupling {c:g} at {r:,.0f} g/cm3', resolve_kv(r, c))
                                                for c, r in ((0.2, 1000.0), (0.3, 1000.0), (0.3, 2000.0), (0.5, 2000.0), (1.0, 3000.0))],
              'driver-to-fuel compression coupling eta_c/alpha (D-22: 0.5 is a research target, present values are percent-range)'),
             ('multi', 'V4_driver_band', V4, [('driver efficiency 0.25', {DRIVER: 0.25}), ('driver efficiency 0.45', {DRIVER: 0.45}),
                                              ('driver 0.05 kg/kW (Atlas)', {DRVKG: 5e-5}), ('driver 0.1 kg/kW', {DRVKG: 1e-4})],
              'heavy-ion driver efficiency and specific mass (VTX-01B; T01: volt-second scaling suggests far more than 0.05 kg/kW)'),
             ('multi', 'V4_warm_band', V4, [('warm 489 K (near-term components, T01 conservative)', {WARM: 489.0}),
                                            ('warm 670 K (sheet emissivity 0.8)', {WARM: 670.0}),
                                            ('warm areal 0.96 kg/m2 (circuit panels, V3 value)', {WAREAL: 0.96})],
              'warm-circuit equivalent temperature and areal mass (VTX-07E, VTX-07B)'),
             ('multi', 'V3_density_scan', V3, [(f'{r:,.0f} g/cm3, coupling 0.5', resolve_kv(r, 0.5)) for r in (1000.0, 2000.0, 3000.0)],
              'compressed density at coupling 0.5 without the T06 package')]
    return jobs


def resolve_kv(rho, coupling):
    return {VRHO: rho, COUPLING: coupling, RHO: rho, GAIN: gain_ceiling(rho, coupling)}


def multi(name, ov, rows, label):
    out = []
    for lab, kv in rows:
        r = solve(P(ov, **kv))
        out.append({'label': lab, 'set': {k: v for k, v in kv.items()}, **r})
    return name, {'label': label, 'multi': True, 'rows': out}


def do(job):
    kind, name = job[0], job[1]
    t = time.time()
    if kind == 'gen':
        r = benchmarks(name, job[2])
    elif kind == 'case':
        r = solve(job[2])
    elif kind == 'multi':
        _, r = multi(name, job[2], job[3], job[4])
    else:
        _, r = sweep(name, job[2], job[3], job[4], job[5])
    print(f'{name}: {time.time() - t:.0f} s', flush=True)
    return kind, name, r


def rereport():
    """--report: refresh the generation record text from the registry and rewrite CONVERGENCE.md without re-solving (numbers unchanged)."""
    out = json.loads((HERE / 'results/convergence.json').read_text())
    with open(HERE / 'registry/generations.toml', 'rb') as fh:
        recs = {g['id']: g for g in tomllib.load(fh)['generation']}
    for k, g in out['generations'].items():
        g['record'] = {x: recs[k].get(x) for x in ('name', 'definition', 'fictional', 'status', 'consistency')}
    (HERE / 'results/convergence.json').write_text(json.dumps(out, indent=1, default=float) + '\n')
    (HERE / 'results/CONVERGENCE.md').write_text(report(out))
    return 0


def main():
    if '--report' in sys.argv:
        return rereport()
    t0 = time.time()
    G = generations()
    with ProcessPoolExecutor(max_workers=4) as ex:
        done = list(ex.map(do, tasks(G)))
    gens = {n: r for k, n, r in done if k == 'gen'}
    cases = {n: r for k, n, r in done if k in ('case', 'sweep', 'multi')}
    V0 = gens['V0']['base']
    cases['V0'] = V0
    cases['liner_study'] = liner_study()
    cases['ve_sweep'] = ve_sweep(V0['summary']['ve_km_s'], V0['summary']['departure_t'])
    cases['gain_threshold'] = {g: gens[g]['gain_threshold'] for g in gens}
    out = {'fdp1_version': fdp1.solve('baseline').get('version'), 'six_year_benchmark_years': SIX_YEARS, 'g_targets': list(G_TARGETS),
           'generations': {k: {'record': {x: G[k]['record'][x] for x in ('name', 'definition', 'fictional', 'status', 'consistency')},
                               'changes': G[k]['record'].get('change', []), **{x: gens[k]['base'][x] for x in gens[k]['base']}, **{
                                   x: gens[k][x] for x in gens[k] if x != 'base'}} for k in G},
           'variants': {k: gens[k] for k in gens if k not in G},
           'cases': cases, 'runtime_s': round(time.time() - t0, 1)}
    out['consistency'] = {k: consistency(G[k]['overrides'], out['generations'][k]) for k in G}
    must = G['V0']['record']['must_reproduce']
    d = out['generations']['V0']['summary'].get('departure_t', 0)
    out['v0_reproduces_fdp1'] = abs(d - must['departure_t']) <= must['tolerance'] * must['departure_t']
    (HERE / 'results').mkdir(exist_ok=True)
    (HERE / 'results/convergence.json').write_text(json.dumps(out, indent=1, default=float) + '\n')
    (HERE / 'results/CONVERGENCE.md').write_text(report(out))
    print(f'V0 reproduces FDP-1: {out["v0_reproduces_fdp1"]} ({d:,.0f} t); {out["runtime_s"]} s')
    return 0 if out['v0_reproduces_fdp1'] else 1


def consistency(ov, g):
    """Compression coupling a generation's target needs under the T04 bound (> 1 is impossible: more energy than the driver delivers)."""
    tree = ov.get('base', {}).get('overrides', {}).get('pulsed', {})
    rho = tree.get('rho_g_cc', {}).get('optimistic', 3000.0)
    gain = g.get('gain') or tree.get('gain', {}).get('optimistic', 3000.0)
    need = coupling_needed(rho, gain)
    return {'rho_g_cc': rho, 'gain': gain, 'coupling_needed': need, 'possible': need <= 1.0,
            'declared_coupling': ov.get('vertex', {}).get('compression_coupling')}


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
    L += ['## Energy consistency (T04 compression bound)', '',
          'Coupling needed: the driver-to-fuel compression coupling eta_c/alpha that the generation\'s target (gain at its density) requires',
          'under the T04 ceiling. Above 1 the target needs more energy in the cold fuel than the driver delivers.', '',
          '| Generation | Status | Density g/cm3 | Gain | Coupling needed | Possible | Declared coupling |', '|---|---|---|---|---|---|---|']
    for k, c in o['consistency'].items():
        L.append(f'| {k} | {o["generations"][k]["record"]["status"]} | {c["rho_g_cc"]:,.0f} | {c["gain"]:,.0f} | {c["coupling_needed"]:.2f} | '
                 f'{"yes" if c["possible"] else "NO"} | {f(c["declared_coupling"], "{:g}")} |')
    L.append('')
    for k in o['generations']:
        g = o['generations'][k]
        L += [f'### {k}: {g["record"]["name"]}', '', f'Status **{g["record"]["status"]}**. {g["record"]["consistency"]}', '',
              g['record']['definition'], '', f'Fictional content: {g["record"]["fictional"]}', '']
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
            L += [f'Target gain {g["gain"]:,.0f}, pulse yield {g["yield_J"] / 4.184e9:,.1f} t TNT at {g["pellet_rate_Hz"]:.0f} Hz, X-ray stand-off '
                  f'{g["xray_standoff_m"]:.1f} m, injection path {g["injection_path_m"]:.1f} m'
                  + (f', launcher {g["launcher"]["speed_m_s"] / 1e3:g} km/s ({"rate capped at " + f(g["launcher"]["rate_cap_Hz"], "{:.0f}") + " Hz" if g["launcher"]["binding"] else "cap not binding"})'
                     if g.get('launcher') else ', no launcher limit (FDP-1 400 m/s, many targets in flight)') + '.', '']
        else:
            L += ['Does not close at the FDP-1 departure acceleration.', '']
    L += ['## Sensitivity bands (not credited to any generation)', '']
    for k, c in o['cases'].items():
        if isinstance(c, dict) and 'rows' in c and 'path' in c:
            L += [f'### {k}: {c["label"]}', '', '| Value | Departure t | Burn y | Warm km2 | Wing tip m | Hot GW |', '|---|---|---|---|---|---|']
            for r in c['rows']:
                s = r['summary']
                L.append(f'| {r["value"]:g} | ' + (f'{s["departure_t"]:,.0f} | {s["burn_years"]:.2f} | {s["warm_km2"]:.2f} | {s["wing_tip_radius_m"]:,.0f} | {r["hot_GW"]:.1f} |'
                                                   if s.get('converged') else 'does not close | | | | |'))
            L.append('')
    for k, c in o['cases'].items():
        if isinstance(c, dict) and c.get('multi'):
            L += [f'### {k}: {c["label"]}', '', '| Case | Departure t | Fusion TW | Gain | Rate Hz | Warm km2 | Wing tip m | Hot GW | Loop 3 r m |',
                  '|---|---|---|---|---|---|---|---|---|']
            for r in c['rows']:
                s = r['summary']
                L.append(f'| {r["label"]} | ' + (f'{s["departure_t"]:,.0f} | {s["fusion_TW"]:.1f} | {r["gain"]:,.0f} | {r["pellet_rate_Hz"]:.0f} | '
                                                 f'{s["warm_km2"]:.2f} | {s["wing_tip_radius_m"]:,.0f} | {r["hot_GW"]:.1f} | {r["loop_radii_m"][-1]:.0f} |'
                                                 if s.get('converged') else 'does not close | | | | | | | |'))
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
