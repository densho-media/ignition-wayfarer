"""T06 futures: convergence chains for the Vertex Drive, run through the FDP-1 calculator (read-only).

  python3 lab/variants/vertex-drive/studies/futures/futures.py      # writes results/futures.json and results/CHAINS.md (about 2-4 min)

Adapter only. Every ship number is an FDP-1 solve (lab/variants/fdp1 run.solve) reached through the Atlas adapter convergence.py,
imported read-only; nothing in FDP-1, the four-burn engine, convergence.py or the registry is changed. Each chain is a list of steps, one
technology mechanism per step, expressed as FDP-1 overrides. For every chain the script reports:

  - each step alone on the chain's base,
  - the steps combined,
  - the additive expectation (sum of single mass changes) and the multiplicative expectation (product of single mass ratios),
  - the interaction: combined against the multiplicative expectation (the mass feedback compounds ratios, so a product is the
    no-interaction null; the additive sum is shown so double counting is visible).

Energy is booked once by construction: the four-burn pulse ledger (_ledger_check) closes every solve, and the script re-checks that the
ledger shares of every combined solve sum to 1. Steps that touch the same ledger term (nozzle efficiency and recovery, both taken from
the expanding plasma) are flagged, not silently added.
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
ATLAS = HERE.parents[1]                        # lab/variants/vertex-drive
sys.path.insert(0, str(ATLAS))
import convergence as cv                       # noqa: E402  (read-only: solve, P, bisect, benchmarks, generations)

S = 'base.overrides.'
K = {
    'gain': cv.GAIN, 'eta': cv.ETA, 'ptw': cv.PTW, 'warm': cv.WARM, 'house': cv.HOUSE, 'driver': cv.DRIVER, 'a0': cv.A0,
    'driver_kg': S + 'pulsed.driver_kg_per_W.optimistic',
    'recovery': S + 'pulsed.recovery_efficiency.optimistic',
    'rho': S + 'pulsed.rho_g_cc.optimistic',
    'armor': S + 'pulsed.loop_armor_kg_m2.optimistic',
    'nozzle_kg': S + 'pulsed.nozzle_kg_per_J.optimistic',
    'other_kg': S + 'pulsed.other_kg_per_W.optimistic',
    'warm_areal': S + 'radiators.warm.areal_kg_m2.optimistic',
    'warm_transport': S + 'radiators.warm.transport_kg_per_W.optimistic',
    'hot_areal': S + 'radiators.hot.areal_kg_m2.optimistic',
    'hot_transport': S + 'radiators.hot.transport_kg_per_W.optimistic',
    'spar': 'structure.wing_spar_kg_per_m.value',
    'gallery_kg': 'structure.gallery_kg_per_m.value',
    'frame': 'structure.module_frame_kg_per_m.value',
}

# Defaults read from the FDP-1 / four-burn optimistic tier (checked against the files at the base commit, 8de3ffa)
DEFAULT = {'driver_kg': 0.05e-3, 'nozzle_kg': 1.07e-6, 'other_kg': 0.05e-6, 'warm_areal': 1.0, 'warm_transport': 2.0e-6,
           'hot_areal': 3.0, 'hot_transport': 0.5e-6, 'spar': 25.0, 'gallery_kg': 120.0, 'frame': 1500.0, 'armor': 200.0}

# Link status vocabulary (T06 prompt section 3)
MODELLED, UNMODELLED, SPECULATIVE = 'CAUSAL_MODELLED', 'CAUSAL_UNMODELLED', 'SPECULATIVE'


def bases():
    G = cv.generations()
    V0, V1, V2 = (G[k]['overrides'] for k in ('V0', 'V1', 'V2'))
    return {'V0': V0, 'V1': V1, 'V2': V2,
            # conservative research baseline: V1 at the published heavy-ion driver efficiency (Atlas roadmap item 2)
            'V1c': cv.P(V1, **{cv.DRIVER: 0.30})}


# ----------------------------------------------------------------------------------------------------------------------------------
# chains: one technology mechanism per step. basis TARGET = a requirement the technology must meet (never a result).
# ----------------------------------------------------------------------------------------------------------------------------------

CHAINS = [
    {'id': 'K1', 'name': 'Recirculating-power chain (ignition and driver)', 'base': 'V1c',
     'story': 'Better targets and drivers lower the recirculating power, which lowers warm-loop heat and driver mass, which lowers the '
              'mass the drive must push. Gain does not lower the fusion power needed for a given thrust; fusion power falls only '
              'because the lighter ship needs less thrust at the same acceleration.',
     'steps': [
         {'tech': 'VTX-01A', 'key': 'gain', 'value': 6000.0, 'basis': 'TARGET', 'link': MODELLED,
          'mechanism': 'magnetised fuel-only targets double target gain (3,000 to 6,000): driver power 1/(G eta_d) halves'},
         {'tech': 'VTX-01B', 'key': 'driver', 'value': 0.45, 'basis': 'TARGET', 'link': MODELLED,
          'mechanism': 'heavy-ion driver wall-plug 0.30 (published) to 0.45 (FDP-1 optimistic): less driver loss heat'},
         {'tech': 'VTX-01B', 'key': 'driver_kg', 'value': 0.025e-3, 'basis': 'TARGET', 'link': MODELLED,
          'mechanism': 'driver hardware 0.05 to 0.025 kg/kW (lighter induction cores, higher gradient)'},
         {'tech': 'VTX-01C', 'key': 'house', 'value': 2.5e-4, 'basis': 'TARGET', 'link': MODELLED,
          'mechanism': 'target factory and controls 0.05 % to 0.025 % of fusion'},
     ]},
    {'id': 'K2', 'name': 'Thermal chain (hot machinery and light radiators)', 'base': 'V1c',
     'story': 'Hotter machinery and lighter radiator surfaces shrink the wings; smaller wings shrink spars, view-factor penalties and '
              'the dust-exposed edge.',
     'steps': [
         {'tech': 'VTX-07A', 'key': 'warm', 'value': 800.0, 'basis': 'TARGET', 'link': MODELLED,
          'mechanism': 'warm loop 700 to 800 K: MW power electronics at 800 K, cores near the FINEMET limit'},
         {'tech': 'VTX-07B', 'key': 'warm_areal', 'value': 0.5, 'basis': 'TARGET', 'link': MODELLED,
          'mechanism': 'liquid-sheet or droplet surfaces for the warm field: 1.0 to 0.5 kg/m2'},
         {'tech': 'T06-NEW-1', 'key': 'hot_areal', 'value': 1.5, 'basis': 'TARGET', 'link': MODELLED,
          'mechanism': 'thin-wall refractory heat pipes (Mo-Re / C-C) for the 1,800 K band: 3.0 to 1.5 kg/m2'},
     ]},
    {'id': 'K3', 'name': 'Nozzle chain (collimation and recovery)', 'base': 'V1c',
     'story': 'A validated 3D nozzle field raises efficiency and lowers the plume share that strikes hardware; pulse-to-pulse control '
              'keeps burns centred so the design efficiency holds. Recovery and nozzle efficiency draw on the same expanding plasma.',
     'steps': [
         {'tech': 'VTX-03', 'key': 'eta', 'value': 0.86, 'basis': 'TARGET', 'link': UNMODELLED,
          'mechanism': 'nozzle efficiency 0.79 to 0.86 (top of the MSFC theoretical range); the sign of the helical effect is unresolved (D-09)'},
         {'tech': 'VTX-03B', 'key': 'ptw', 'value': 0.01, 'basis': 'TARGET', 'link': SPECULATIVE,
          'mechanism': 'shaped field halves the plume share striking hardware (2 % to 1 % of the nozzle loss)'},
         {'tech': 'VTX-02C', 'key': 'recovery', 'value': 0.98, 'basis': 'TARGET', 'link': MODELLED,
          'mechanism': 'inductive recovery 0.95 to 0.98', 'shares_ledger_with': 'VTX-03'},
     ]},
    {'id': 'K4', 'name': 'Compression chain (small pulses, small nozzle)', 'base': 'V1c',
     'story': 'Denser compression gives the same burn fraction from a smaller pellet: smaller yield per pulse, a closer X-ray stand-off, '
              'loops of half the radius, a smaller shield and less dust-exposed loop area, paid for by a higher pulse rate.',
     'steps': [
         {'tech': 'VTX-01A', 'key': 'rho', 'value': 6000.0, 'basis': 'TARGET', 'link': MODELLED,
          'mechanism': 'compressed fuel density 3,000 to 6,000 g/cm3 (pellet mass /4 at the same rhoR); rate rises about 3.4x'},
         {'tech': 'VTX-06B', 'key': 'armor', 'value': 100.0, 'basis': 'TARGET', 'link': MODELLED,
          'mechanism': 'advanced W armour (MAT-W-ADV01) at half areal mass'},
     ]},
    {'id': 'K5', 'name': 'Structure chain (strength per mass)', 'base': 'V1c',
     'story': 'The nozzle structure obeys the virial bound M >= rho W / sigma; only a stronger-per-mass material lowers it. Lighter '
              'spars and frames follow from the same material class.',
     'steps': [
         {'tech': 'T06-NEW-2', 'key': 'nozzle_kg', 'value': 0.535e-6, 'basis': 'TARGET', 'link': MODELLED,
          'mechanism': 'hoop structure at twice the specific strength of 1.5 GPa CFRP (3 GPa at 1.6 t/m3): virial mass halves'},
         {'tech': 'T06-NEW-2', 'key': 'spar', 'value': 12.5, 'basis': 'TARGET', 'link': MODELLED,
          'mechanism': 'wing spars 25 to 12.5 kg/m'},
         {'tech': 'T06-NEW-2', 'key': 'gallery_kg', 'value': 60.0, 'basis': 'TARGET', 'link': MODELLED,
          'mechanism': 'driver gallery truss 120 to 60 kg/m'},
     ]},
]

# Downside checks: the same levers in the pessimistic direction (negative results stay visible)
DOWNSIDE = [
    ('gain_1500', 'VTX-01', {'gain': 1500.0}, 'target gain halved (3,000 to 1,500)'),
    ('eta_0.72', 'VTX-03A', {'eta': 0.72}, 'm = 4 ripple costs 0.07 of nozzle efficiency'),
    ('warm_600', 'VTX-07A', {'warm': 600.0}, 'warm loop held at the 600 K core limit'),
    ('house_1e-3', 'VTX-07C', {'house': 1.0e-3}, 'house load at the unsourced FDP-1 0.1 %'),
    ('recovery_0.90', 'VTX-02C', {'recovery': 0.90}, 'recovery at the central tier 0.90'),
]

# Specific-mass keys scaled together for the 1 g question (drive, power, radiators, nozzle, light structure). Shield (LiH/W thickness
# set by dose), tanks (kg per m3) and the canon payload are physical masses and are NOT scaled.
SPECIFIC = ['driver_kg', 'nozzle_kg', 'other_kg', 'warm_areal', 'warm_transport', 'hot_areal', 'hot_transport', 'armor', 'spar',
            'gallery_kg', 'frame']


def ov_for(base_ov, kv):
    return cv.P(base_ov, **{K[k]: v for k, v in kv.items()})


def brief(r):
    s = r['summary']
    if not s.get('converged'):
        return {'converged': False, 'reason': s.get('reason'), 'max_a0_g': s.get('max_a0_g')}
    out = {k: s[k] for k in ('departure_t', 'payload_t', 'fusion_TW', 'burn_years', 'min_round_trip_years', 'drive_t', 'radiator_t', 'shield_t',
                             'structure_t', 'tank_t', 'propellant_t', 'warm_km2', 'hot_km2', 'wing_tip_radius_m', 'pellet_rate_Hz',
                             'yield_t_TNT', 'solid_angle', 'checks_ok')}
    out.update(converged=True, loop_radii_m=r['loop_radii_m'], xray_standoff_m=r['xray_standoff_m'], hot_GW=r['hot_GW'],
               warm_GW=r['warm_GW'], ledger_sum=sum(r['ledger_share'].values()))
    return out


def run_chain(ch):
    B = bases()[ch['base']]
    base = brief(cv.solve(B))
    m0 = base['departure_t']
    singles = []
    for st in ch['steps']:
        r = brief(cv.solve(ov_for(B, {st['key']: st['value']})))
        singles.append({**st, 'path': K[st['key']], 'result': r, 'delta_t': r['departure_t'] - m0, 'ratio': r['departure_t'] / m0})
    comb_ov = ov_for(B, {st['key']: st['value'] for st in ch['steps']})
    comb = brief(cv.solve(comb_ov))
    add = m0 + sum(s['delta_t'] for s in singles)
    mult = m0 * math.prod(s['ratio'] for s in singles)
    bench = cv.benchmarks(ch['id'], comb_ov)
    return {'id': ch['id'], 'name': ch['name'], 'base_name': ch['base'], 'story': ch['story'], 'base': base, 'singles': singles,
            'combined': comb, 'additive_expectation_t': add, 'multiplicative_expectation_t': mult,
            'interaction_vs_product': comb['departure_t'] / mult - 1, 'combined_vs_sum_t': comb['departure_t'] - add,
            'ambitions': ambitions(bench)}


def ambitions(b):
    six = b['six_year']
    return {'four_burns_close': b['four_burn_closes'], 'min_round_trip_years': b['base']['summary'].get('min_round_trip_years'),
            'six_year_a0_g': six.get('a0_g'), 'six_year_departure_t': six.get('departure_t'), 'six_year_met_at_base_a0': six.get('met_at_base_a0'),
            'ceiling_a0_g': b['max_a0_g'], 'deficit_1g': b['g_deficit']['1'], 'deficit_1p5g': b['g_deficit']['1.5'],
            'gain_cliff': b['gain_threshold'], 'nozzle_eff_cliff': b['nozzle_efficiency_threshold']}


def grand(_=None):
    """All K1-K5 steps together on V1c: the convergence endpoint, against the product of the five chain ratios."""
    B = bases()['V1c']
    kv = {st['key']: st['value'] for ch in CHAINS for st in ch['steps']}
    ov = ov_for(B, kv)
    r = brief(cv.solve(ov))
    return {'overrides': {K[k]: v for k, v in kv.items()}, 'result': r, 'ambitions': ambitions(cv.benchmarks('GRAND', ov))}


def downside(_=None):
    B = bases()['V1c']
    m0 = brief(cv.solve(B))['departure_t']
    rows = []
    for name, tech, kv, what in DOWNSIDE:
        r = brief(cv.solve(ov_for(B, kv)))
        rows.append({'case': name, 'tech': tech, 'what': what, 'result': r,
                     'ratio': (r['departure_t'] / m0) if r.get('converged') else None})
    return rows


def one_g(_=None):
    """Smallest uniform scale on every specific mass (SPECIFIC) at which the grand endpoint closes at a0 = 1 g and 1.5 g."""
    B = bases()['V1c']
    kv = {st['key']: st['value'] for ch in CHAINS for st in ch['steps']}
    out = {}
    for g in (1.0, 1.5):
        def at(s):
            vals = dict(kv)
            for k in SPECIFIC:
                vals[k] = vals.get(k, DEFAULT[k]) * s
            vals['a0'] = g
            return cv.solve(ov_for(B, vals))
        lo, hi = math.log(1e-5), math.log(1.0)
        r_lo = at(math.exp(lo))
        if not r_lo['summary'].get('converged'):
            out[f'{g:g}'] = {'closes_at_any_scale': False, 'reason': r_lo['summary'].get('reason'), 'tested_scale_min': 1e-5}
            continue
        good = r_lo
        for _ in range(16):
            m = (lo + hi) / 2; r = at(math.exp(m))
            if r['summary'].get('converged'):
                lo, good = m, r
            else:
                hi = m
        s = math.exp(lo)
        out[f'{g:g}'] = {'closes_at_any_scale': True, 'scale': s, 'reduction_factor': 1 / s, 'result': brief(good)}
    return out


def floor(_=None):
    """Convergence asymptote: the grand endpoint with every SPECIFIC mass at 1e-4 of its value, at the FDP-1 a0. What remains is the
    payload, the propellant the rocket equation demands at ve 19,201 km/s, its tanks and the dose-set shield: no hardware improvement
    in this model can go below it."""
    B = bases()['V1c']
    kv = {st['key']: st['value'] for ch in CHAINS for st in ch['steps']}
    for k in SPECIFIC:
        kv[k] = kv.get(k, DEFAULT[k]) * 1e-4
    return brief(cv.solve(ov_for(B, kv)))


# T04 EARLY (claude/project-thread-9hxayw 1b85941, studies/ignition/EARLY.md section 1): compressing fuel to rho costs at least its
# Fermi-degenerate energy, so target gain is bounded by G <= 1,787 x (eta_c / alpha) at 3,000 g/cm3, scaling as rho^(-2/3) (checked
# against T04's table: eta_c/alpha needed for gain 705 is 0.41 / 0.26 / 0.20 / 0.13 at 3,000 / 1,500 / 1,000 / 500 g/cm3).
G_BOUND_3000 = 1787.0


def gain_bound(rho_g_cc, coupling):
    return G_BOUND_3000 * coupling * (rho_g_cc / 3000.0) ** (-2.0 / 3.0)


# T01 EARLY (claude/project-thread-93sqqi 57fe625, studies/thermal/EARLY.md): split warm loop collapses to an equivalent 628 K with every
# component at its TARGET temperature; bottom-up house load 0.003-0.005 % (advanced). Used only in the EARLY-INFORMED frontier below.
T01_EARLY = {'warm': 628.0, 'house': 5e-5}
RHOS = [500.0, 1000.0, 1500.0, 2000.0, 3000.0, 6000.0]
COUPLINGS = [0.1, 0.2, 0.3, 0.5, 1.0]


def consistency(_=None):
    """Gain-compression consistency of every T06 case, and the frontier: for each coupling eta_c/alpha, the best density when the
    gain is set to its bound (gain = G_max(rho)), on (a) V1c, (b) the grand endpoint's non-ignition levers, (c) (b) with T01 EARLY inputs."""
    G = {}
    for ch in CHAINS:
        kv = {st['key']: st['value'] for st in ch['steps']}
        G[ch['id']] = (kv.get('rho', 3000.0), kv.get('gain', 3000.0))
    G['grand (all chains)'] = (6000.0, 6000.0); G['V0-V2 (Atlas)'] = (3000.0, 3000.0)
    for gid, pg in proposals().items():
        if gid.endswith('c'):
            continue
        tree = pg['overrides']['base']['overrides']['pulsed']
        G[gid + ' (proposal)'] = (tree.get('rho_g_cc', {}).get('optimistic', 3000.0), tree.get('gain', {}).get('optimistic', 3000.0))
    checks = {k: {'rho': r, 'gain': g, 'coupling_needed': g / gain_bound(r, 1.0), 'possible': g <= gain_bound(r, 1.0)} for k, (r, g) in G.items()}
    grand_kv = {st['key']: st['value'] for ch in CHAINS for st in ch['steps'] if st['key'] not in ('gain', 'rho')}
    sets = {'V1c': {}, 'grand_levers': grand_kv, 'grand_levers_T01_early': {**grand_kv, **T01_EARLY}}
    B = bases()['V1c']
    frontier = {}
    for sname, kv in sets.items():
        frontier[sname] = {}
        for cpl in COUPLINGS:
            rows = []
            for rho in RHOS:
                g = gain_bound(rho, cpl)
                r = brief(cv.solve(ov_for(B, {**kv, 'rho': rho, 'gain': g})))
                rows.append({'rho': rho, 'gain': g, 'departure_t': r.get('departure_t'), 'converged': r.get('converged'),
                             'rate_Hz': r.get('pellet_rate_Hz'), 'loop3_r_m': (r.get('loop_radii_m') or [None])[-1],
                             'wing_tip_m': r.get('wing_tip_radius_m'), 'yield_t_TNT': r.get('yield_t_TNT')})
            ok = [x for x in rows if x['converged']]
            frontier[sname][f'{cpl:g}'] = {'rows': rows, 'best': min(ok, key=lambda x: x['departure_t']) if ok else None}
    return {'bound_at_3000': G_BOUND_3000, 'checks': checks, 'frontier': frontier,
            'source': 'T04 EARLY 1b85941 section 1 (bound); T01 EARLY 57fe625 (628 K, 0.005 %)'}


def reproduce(_=None):
    r = cv.solve(bases()['V0'])['summary']
    return {'V0_departure_t': r['departure_t'], 'target_t': 20760.0, 'within_1pct': abs(r['departure_t'] - 20760.0) <= 207.6}


def proposals():
    """generations_proposal.toml applied on V0 the way convergence.generations() applies the registry, plus driver-0.30 twins."""
    with open(HERE / 'generations_proposal.toml', 'rb') as fh:
        gens = tomllib.load(fh)['generation']
    V0 = bases()['V0']
    out = {}
    for g in gens:
        ov = copy.deepcopy(V0)
        for c in g.get('change', []):
            cv.put(ov, c['path'], c['value'])
        out[g['id']] = {'record': g, 'overrides': ov}
        out[g['id'] + 'c'] = {'record': {**g, 'id': g['id'] + 'c', 'name': g['name'] + ' at driver efficiency 0.30'},
                              'overrides': cv.P(ov, **{cv.DRIVER: 0.30})}
    return out


def run_proposal(gid):
    g = proposals()[gid]
    b = cv.benchmarks(gid, g['overrides'])
    return {'name': g['record']['name'], 'fictional': g['record'].get('fictional'), 'result': brief(b['base']), 'ambitions': ambitions(b)}


# Elasticities d ln(departure) / d ln(lever) at V1c (+-10 % steps): which engine parameters the ship is steepest in.
ELASTIC = [('gain', 3000.0, 'VTX-01/01A'), ('driver', 0.30, 'VTX-01B'), ('driver_kg', 0.05e-3, 'VTX-01B'), ('house', 5e-4, 'VTX-07C/01C'),
           ('warm', 700.0, 'VTX-07A'), ('warm_areal', 1.0, 'VTX-07B'), ('hot_areal', 3.0, 'T06-NEW-1'), ('eta', 0.79, 'VTX-03'),
           ('ptw', 0.02, 'VTX-03/03B'), ('recovery', 0.95, 'VTX-02C'), ('rho', 3000.0, 'VTX-01A'), ('armor', 200.0, 'VTX-06B'),
           ('nozzle_kg', 1.07e-6, 'T06-NEW-2'), ('spar', 25.0, 'T06-NEW-2'), ('gallery_kg', 120.0, 'T06-NEW-2')]


def elasticities(_=None):
    B = bases()['V1c']
    m0 = brief(cv.solve(B))['departure_t']
    rows = []
    for key, x0, tech in ELASTIC:
        up = brief(cv.solve(ov_for(B, {key: x0 * 1.1}))); dn = brief(cv.solve(ov_for(B, {key: x0 / 1.1})))
        e = (math.log(up['departure_t']) - math.log(dn['departure_t'])) / (2 * math.log(1.1)) if up.get('converged') and dn.get('converged') else None
        rows.append({'lever': key, 'path': K[key], 'value': x0, 'tech': tech, 'elasticity': e,
                     'up_t': up.get('departure_t'), 'down_t': dn.get('departure_t')})
    return {'base': 'V1c', 'departure_t': m0, 'rows': rows}


def ve_gate(_=None):
    """The nozzle-efficiency cliff near 0.53 is the exhaust-velocity gate eta_jet x b >= ve^2 / (2 eps) (S-FIJI-V4), not mass."""
    sys.path.insert(0, str(ATLAS.parents[2] / 'lab/studies/four-burn-mission'))
    from fourburn.const import EPS_DHE3
    ve = 19201.17208e3
    gate = ve ** 2 / (2 * EPS_DHE3)
    return {'ve_km_s': ve / 1e3, 'eps_J_kg': EPS_DHE3, 'gate_eta_jet_times_b': gate,
            'note': 'With burn fraction capped at 0.999 and about 1.2 % of fusion escaping as radiation, the lowest nozzle efficiency that can '
                    'reach the mission ve is about gate / 0.988; the Atlas bisection (0.40-0.86, 9 steps) lands at 0.528 for every '
                    'generation because it hits this gate, which no mass or thermal improvement moves.'}


JOBS = [('chain', ch) for ch in CHAINS] + [('grand', None), ('downside', None), ('one_g', None), ('reproduce', None),
                                          ('elasticities', None), ('ve_gate', None), ('floor', None), ('consistency', None)] + [('proposal', g) for g in ('V3', 'V3c', 'V4', 'V4c')]


def do(job):
    kind, arg = job
    t = time.time()
    fn = {'chain': run_chain, 'grand': grand, 'downside': downside, 'one_g': one_g, 'reproduce': reproduce,
          'elasticities': elasticities, 've_gate': ve_gate, 'floor': floor, 'consistency': consistency, 'proposal': run_proposal}[kind]
    res = fn(arg)
    name = arg['id'] if isinstance(arg, dict) else (arg or kind)
    print(f'{kind} {name}: {time.time() - t:.0f} s', flush=True)
    return kind, name, res


def main():
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=4) as ex:
        done = list(ex.map(do, JOBS))
    out = {'chains': {}, 'basis_note': 'FDP-1 fdp1-v1 optimistic tier via convergence.py; base V1c = Atlas V1 at driver efficiency 0.30'}
    for kind, name, res in done:
        if kind == 'chain':
            out['chains'][name] = res
        elif kind == 'proposal':
            out.setdefault('proposals', {})[name] = res
        else:
            out[name] = res
    # product of the five chain ratios: does the grand endpoint add anything beyond the chains?
    m0 = out['chains']['K1']['base']['departure_t']
    out['grand']['product_of_chain_ratios_t'] = m0 * math.prod(c['combined']['departure_t'] / m0 for c in out['chains'].values())
    out['grand']['interaction_vs_chain_product'] = out['grand']['result']['departure_t'] / out['grand']['product_of_chain_ratios_t'] - 1
    sums = [c['combined']['ledger_sum'] for c in out['chains'].values()] + [out['grand']['result']['ledger_sum']]
    out['ledger_closes'] = all(abs(x - 1) < 1e-9 for x in sums)
    out['runtime_s'] = round(time.time() - t0, 1)
    (HERE / 'results').mkdir(exist_ok=True)
    (HERE / 'results/futures.json').write_text(json.dumps(out, indent=1, default=float) + '\n')
    (HERE / 'results/CHAINS.md').write_text(report(out))
    print(f'V0 {out["reproduce"]["V0_departure_t"]:,.0f} t (within 1 %: {out["reproduce"]["within_1pct"]}); ledger closes: '
          f'{out["ledger_closes"]}; {out["runtime_s"]} s')
    return 0 if out['reproduce']['within_1pct'] and out['ledger_closes'] else 1


# ----------------------------------------------------------------------------------------------------------------------------------

def f(x, fmt='{:,.0f}', none='-'):
    return none if x is None else fmt.format(x)


def amb_row(name, a, dep):
    six = (f'MET at base a0' if a['six_year_met_at_base_a0'] else
           (f'MET ONLY ABOVE {a["six_year_a0_g"]:.4f} g ({f(a["six_year_departure_t"])} t)' if a['six_year_a0_g'] else 'NOT MET'))
    return (f'| {name} | {f(dep)} | {"MET" if a["four_burns_close"] else "NOT MET"} | {f(a["min_round_trip_years"], "{:.2f}")} | {six} | '
            f'{f(a["ceiling_a0_g"], "{:.4f}")} | NOT MET ({f(a["deficit_1g"], "{:,.0f}x")} short) | {f(a["gain_cliff"])} | '
            f'{f(a["nozzle_eff_cliff"], "{:.3f}")} |')


def report(o):
    L = ['# T06 convergence chains (generated)', '',
         '_Generated by `futures.py`; do not edit by hand. Every number is an FDP-1 solve (fdp1-v1, optimistic tier, four 0.016 c burns) '
         'through `convergence.py`, read-only. Base V1c = Atlas V1 at the published heavy-ion driver efficiency 0.30. Every step value '
         'is a TARGET (a requirement the named technology must meet), never a demonstrated result._', '',
         f'V0 through this adapter: {o["reproduce"]["V0_departure_t"]:,.0f} t (FDP-1 20,760 t; within 1 %: '
         f'{"yes" if o["reproduce"]["within_1pct"] else "NO"}). Energy ledger closes in every combined solve: '
         f'{"yes" if o["ledger_closes"] else "NO"}.', '']
    for cid, c in o['chains'].items():
        b = c['base']; cm = c['combined']
        L += [f'## {cid}: {c["name"]}', '', c['story'], '',
              f'Base {c["base_name"]}: {b["departure_t"]:,.0f} t, fusion {b["fusion_TW"]:.2f} TW, wing tip {b["wing_tip_radius_m"]:,.0f} m, '
              f'loop 3 r {b["loop_radii_m"][-1]:.1f} m, {b["pellet_rate_Hz"]:.0f} Hz.', '',
              '| Step | Technology | Override | Link | Alone t | Change | Ratio |', '|---|---|---|---|---|---|---|']
        for s in c['singles']:
            L.append(f'| {s["mechanism"]} | {s["tech"]} | `{s["key"]}` = {s["value"]:g} | {s["link"]} | {s["result"]["departure_t"]:,.0f} | '
                     f'{s["delta_t"]:+,.0f} | {s["ratio"]:.3f} |')
        L += ['', '| Combined t | Additive expectation t | Multiplicative expectation t | Interaction vs product | Fusion TW | Wing tip m | '
              'Loop 3 r m | Rate Hz |', '|---|---|---|---|---|---|---|---|',
              f'| {cm["departure_t"]:,.0f} | {c["additive_expectation_t"]:,.0f} | {c["multiplicative_expectation_t"]:,.0f} | '
              f'{100 * c["interaction_vs_product"]:+.1f} % | {cm["fusion_TW"]:.2f} | {cm["wing_tip_radius_m"]:,.0f} | '
              f'{cm["loop_radii_m"][-1]:.1f} | {cm["pellet_rate_Hz"]:.0f} |', '']
        shared = [s for s in c['singles'] if s.get('shares_ledger_with')]
        for s in shared:
            L += [f'Ledger note: {s["tech"]} and {s["shares_ledger_with"]} both draw on the expanding plasma. The calculator treats them as '
                  'independent (Atlas link VTX-02C conflicts VTX-03), so this chain\'s combined value is an upper bound until T03 gives a '
                  'joint model.', '']
    g = o['grand']; gr = g['result']
    L += ['## Grand endpoint: every K1-K5 step on V1c', '',
          f'Departure {gr["departure_t"]:,.0f} t; product of the five chain ratios {g["product_of_chain_ratios_t"]:,.0f} t; interaction '
          f'{100 * g["interaction_vs_chain_product"]:+.1f} %. Fusion {gr["fusion_TW"]:.2f} TW, wing tip {gr["wing_tip_radius_m"]:,.0f} m, '
          f'loops r {", ".join(f"{x:.1f}" for x in gr["loop_radii_m"])} m, {gr["pellet_rate_Hz"]:.0f} Hz, yield {gr["yield_t_TNT"]:.1f} t TNT.', '']
    L += ['## Mission ambitions', '',
          '| Case | Departure t | Four 0.016 c burns | Min round trip y | LOCKED 6.0 y | Ceiling a0 g | 1 g | Gain cliff | Nozzle-eff. cliff |',
          '|---|---|---|---|---|---|---|---|---|']
    for cid, c in o['chains'].items():
        L.append(amb_row(f'{cid} combined', c['ambitions'], c['combined']['departure_t']))
    L.append(amb_row('Grand', g['ambitions'], gr['departure_t']))
    L += ['', '## Proposed generations (generations_proposal.toml; c = driver efficiency 0.30)', '',
          '| Generation | Departure t | Four 0.016 c burns | Min round trip y | LOCKED 6.0 y | Ceiling a0 g | 1 g | Gain cliff | Nozzle-eff. cliff |',
          '|---|---|---|---|---|---|---|---|---|']
    for gid, pr in o['proposals'].items():
        L.append(amb_row(gid, pr['ambitions'], pr['result'].get('departure_t')))
    L.append('')
    for gid, pr in o['proposals'].items():
        r = pr['result']
        if r.get('converged'):
            L.append(f'- {gid}: fusion {r["fusion_TW"]:.2f} TW, wing tip {r["wing_tip_radius_m"]:,.0f} m, loops r '
                     f'{", ".join(f"{x:.1f}" for x in r["loop_radii_m"])} m, stand-off {r["xray_standoff_m"]:.1f} m, {r["pellet_rate_Hz"]:.0f} Hz, '
                     f'yield {r["yield_t_TNT"]:.1f} t TNT; mass split payload {r["payload_t"]:,.0f} / propellant {r["propellant_t"]:,.0f} / tanks '
                     f'{r["tank_t"]:,.0f} / drive {r["drive_t"]:,.0f} / radiators {r["radiator_t"]:,.0f} / shield {r["shield_t"]:,.0f} / structure '
                     f'{r["structure_t"]:,.0f} t.')
    e = o['elasticities']
    L += ['', f'## Elasticities at V1c ({e["departure_t"]:,.0f} t): d ln(departure) / d ln(lever), +-10 % steps', '',
          '| Lever | Technology | Value | Elasticity | +10 % t | -10 % t |', '|---|---|---|---|---|---|']
    for r in sorted(e['rows'], key=lambda r: -abs(r['elasticity'] or 0)):
        L.append(f'| `{r["lever"]}` | {r["tech"]} | {r["value"]:g} | {f(r["elasticity"], "{:+.2f}")} | {f(r["up_t"])} | {f(r["down_t"])} |')
    vg = o['ve_gate']
    L += ['', '## Exhaust-velocity gate', '', f'eta_jet x b must be at least {vg["gate_eta_jet_times_b"]:.4f} at ve {vg["ve_km_s"]:,.0f} km/s. {vg["note"]}']
    L += ['', '## Downside checks on V1c (negative results kept)', '', '| Case | Technology | What | Departure t | Ratio |', '|---|---|---|---|---|']
    for r in o['downside']:
        res = r['result']
        L.append(f'| {r["case"]} | {r["tech"]} | {r["what"]} | {f(res.get("departure_t")) if res.get("converged") else "does not close"} | '
                 f'{f(r["ratio"], "{:.3f}")} |')
    L += ['', '## 1 g and 1.5 g: uniform specific-mass reduction on the grand endpoint', '',
          'Every drive, power, radiator, nozzle and light-structure specific mass scaled by one factor; shield, tanks and payload unscaled.', '']
    for g_, r in o['one_g'].items():
        if r['closes_at_any_scale']:
            L.append(f'- {g_} g closes at specific masses x{r["scale"]:.4f} (a {r["reduction_factor"]:,.0f}-fold reduction): departure '
                     f'{r["result"]["departure_t"]:,.0f} t, fusion {r["result"]["fusion_TW"]:,.0f} TW, warm {r["result"]["warm_km2"]:.2f} km2.')
        else:
            L.append(f'- {g_} g does not close even at x{r["tested_scale_min"]:g}: {r["reason"]}')
    fl = o['floor']
    if fl.get('converged'):
        L += ['', '## Convergence floor (specific masses x1e-4 on the grand endpoint, FDP-1 a0)', '',
              f'Departure {fl["departure_t"]:,.0f} t: payload {fl["payload_t"]:,.0f}, propellant {fl["propellant_t"]:,.0f}, tanks {fl["tank_t"]:,.0f}, '
              f'shield {fl["shield_t"]:,.0f}, drive {fl["drive_t"]:,.0f}, radiators {fl["radiator_t"]:,.0f}, structure {fl["structure_t"]:,.0f} t. '
              'No drive, thermal or structural improvement in this model goes below this at ve 19,201 km/s.']
    else:
        L += ['', f'Convergence floor: did not close ({fl.get("reason")}).']
    cs = o['consistency']
    L += ['', '## Gain-compression consistency (T04 EARLY bound)', '',
          f'G <= {cs["bound_at_3000"]:,.0f} x eta_c/alpha x (rho / 3,000 g/cm3)^(-2/3); eta_c/alpha <= 1 by definition. Source: {cs["source"]}.', '',
          '| Case | rho g/cm3 | Gain | eta_c/alpha needed | Possible at all |', '|---|---|---|---|---|']
    for k, c in cs['checks'].items():
        L.append(f'| {k} | {c["rho"]:,.0f} | {c["gain"]:,.0f} | {c["coupling_needed"]:.2f} | {"yes" if c["possible"] else "NO"} |')
    L += ['', 'Frontier: gain set to its bound at each density. Best (lightest closing) density per coupling; full rows in futures.json.', '',
          '| Lever set | eta_c/alpha | Best rho g/cm3 | Gain | Departure t | Rate Hz | Loop 3 r m | Wing tip m |', '|---|---|---|---|---|---|---|---|']
    for sname, byc in cs['frontier'].items():
        for cpl, fr in byc.items():
            b = fr['best']
            L.append(f'| {sname} | {cpl} | ' + (f'{b["rho"]:,.0f} | {b["gain"]:,.0f} | {b["departure_t"]:,.0f} | {b["rate_Hz"]:.0f} | {b["loop3_r_m"]:.0f} | '
                                                f'{b["wing_tip_m"]:,.0f} |' if b else 'none closes | | | | | |'))
    L += ['', f'Runtime {o["runtime_s"]:.0f} s.', '']
    return '\n'.join(L)


if __name__ == '__main__':
    sys.exit(main())
