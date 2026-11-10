"""Solve the Breakthrough Lab scenario grid with the T00 calculators at the pinned commit (research only, NOT canon).

Nothing here is a new engineering model. Every number comes from the Technology Atlas adapter and the FDP-1 calculator
(lab/variants/vertex-drive/convergence.py on claude/project-thread-9rsgog at the imported commit) and, for the coupled check, the T00
feasibility gate's fixed-point solver (studies/gate/coupled.py: closure-coil hardware re-sized on every solve, the A1 axis fix as its
nozzle-efficiency factor, squared as Gate 2 corrects it). This script only builds the override tree of each scenario (reference + declared breakthrough levels),
calls those solvers in separate processes and records what they return, with provenance.

    git worktree add /tmp/t00 030fc14259e20eeeb224aa2c78dd06459c3afc7a       # the pinned T00 commit, read-only use
    python3 lab/studies/breakthrough-lab/compute.py --t00 /tmp/t00 [--jobs 4]   # writes results/scenarios.json (about 15 min on 4 cores)

Order: (1) every combination of the grid levers at the unconstrained launcher level; (2) the finite launcher levels for each case that
closes (a cap only adds a constraint, so the others are NOT_COMPUTED, inferred not to close), and every named scenario directly;
(3) the coupled check for every closing case, a finite launcher entering as the pulse-rate cap of its uncoupled solve, held fixed. A case closes when FDP-1 converges with its checks and clearances passing.
"""
import argparse
import copy
import itertools
import json
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lab  # noqa: E402

T00_FILES = ['lab/variants/vertex-drive/convergence.py', 'lab/variants/vertex-drive/studies/ignition/ignition.py',
             'lab/variants/fdp1/run.py', 'lab/variants/fdp1/engineering/model.py', 'lab/variants/fdp1/engineering/config.py',
             'lab/variants/fdp1/config/fdp1.toml', 'lab/studies/four-burn-mission/scenarios/v1.toml',
             'lab/variants/vertex-drive/studies/gate/coupled.py', 'lab/variants/vertex-drive/studies/rev4/ledger.py',
             'lab/variants/vertex-drive/studies/rev4/injection.py']
SUMMARY_KEYS = ('departure_t', 'end_t', 'propellant_t', 'fusion_TW', 'jet_TW', 'thrust_MN', 'peak_g', 'a0_g', 'burn_years',
                'min_round_trip_years', 'shield_t', 'structure_t', 'radiator_t', 'tank_t', 'drive_t', 'payload_t', 'warm_km2', 'hot_km2',
                'wing_layout', 'wing_tip_radius_m', 'pellet_rate_Hz', 'yield_t_TNT', 'solid_angle')
T00 = None


# ------------------------------------------------------------------------------------------------------------------ worker side
def _setup(t00):
    global T00, C, CP, G
    if T00:
        return
    T00 = Path(t00)
    sys.path.insert(0, str(T00 / 'lab/variants/vertex-drive'))
    sys.path.insert(0, str(T00 / 'lab/variants/vertex-drive/studies/gate'))
    import convergence as C          # noqa: E402,F811
    import coupled as CP             # noqa: E402,F811
    import gate_common as G          # noqa: E402,F811
    globals().update(C=C, CP=CP, G=G)
    orig = C.fdp1.solve

    def spy(*a, **k):                # keep the full FDP-1 record of the last solve for the layout envelope
        r = orig(*a, **k)
        spy.last = r
        return r
    spy.last = None
    C.fdp1.solve = spy


def tree(inputs):
    ov = {}
    for path, v in inputs.items():
        if path == 'vertex.launcher_speed_m_s' and v == 'none':
            continue
        C.put(ov, path, copy.deepcopy(v))
    return C.resolve(ov)


def envelope(R):
    """The calculator's own layout of this solve (FDP-1 frame: +X bow, metres): what the website may draw as an envelope."""
    L = R['layout']; sh = R['shield']
    loops = [{'name': x['name'], 'x_m': x['x'], 'r_m': x['r']} for x in R['nozzle']['loops']]
    x_aft = min([L['x_burn']] + [x['x_m'] for x in loops])
    return {'x_burn_m': L['x_burn'], 'stand_off_m': L['R_s'], 'x_shield_aft_m': L['x_shield_aft'], 'x_shield_fwd_m': L['x_shield_fwd'],
            'shield_r_m': max(sh['radius_hw_aft_m'], sh['radius_crew_aft_m']), 'x_module_fwd_m': L['x_module_fwd'],
            'x_bow_m': L['x_forward_shield_aft'], 'x_aft_m': x_aft, 'length_m': L['x_forward_shield_aft'] - x_aft,
            'wing_x_m': [L['wing_aft_x'], L['wing_forward_x']], 'loops': loops, 'hardware_cone_deg': sh['hardware_half_angle_deg']}


def solve_case(args):
    t00, inputs = args
    _setup(t00)
    t0 = time.time()
    C.fdp1.solve.last = None
    try:
        r = C.solve(tree(inputs))
    except Exception as e:  # the calculator's own failure is a result, recorded as such
        return {'computed': True, 'closes': False, 'reason': f'{type(e).__name__}: {e}', 'seconds': time.time() - t0}
    s = r['summary']
    ok = bool(s.get('converged') and s.get('checks_ok', True) and s.get('clearances_ok', True))
    out = {'computed': True, 'closes': ok, 'seconds': time.time() - t0}
    if ok:
        out['summary'] = {k: s[k] for k in SUMMARY_KEYS if k in s}
        out['summary'].update({'hot_GW': r['hot_GW'], 'warm_GW': r['warm_GW'], 'gain': r['gain'], 'stand_off_m': r['xray_standoff_m'],
                               'fuel_rhoR_g_cm2': r['fuel_rhoR_g_cm2'], 'escape_share': r['escape_share']})
        out['ledger_share'] = r['ledger_share']
        R = C.fdp1.solve.last
        if R is not None and R.get('converged'):
            out['envelope'] = envelope(R)
        if 'launcher' in r:
            out['launcher'] = r['launcher']
    else:
        out['reason'] = s.get('reason') or ('checks or clearances fail' if s.get('converged') else 'did not converge')
        for k in ('deficit_factor', 'max_a0_g'):
            if s.get(k) is not None:
                out[k] = s[k]
    return out


def coupled_case(args):
    t00, inputs, cap = args
    _setup(t00)
    t0 = time.time()
    if not hasattr(coupled_case, 'R4'):
        coupled_case.R4 = G.solve_full(G.v4_overrides())
        coupled_case.axis = json.loads((T00 / 'lab/variants/vertex-drive/studies/gate/results/concepts.json').read_text())['chosen']
        # Gate 2 (section 1.1, Task D): the A1 thrust loss belongs in eta_T as the momentum factor squared; the first gate applied the
        # factor once. The corrected factor must equal Gate 2's own booking on its reference row (eta_T_booked / V4 eta_T).
        m = coupled_case.axis['nozzle_efficiency_factor']
        g2 = json.loads((T00 / 'lab/variants/vertex-drive/studies/gate2/results/matrix.json').read_text())['rows'][0]
        v4_eta = json.loads((T00 / 'lab/variants/vertex-drive/studies/gate2/results/g1.json').read_text())['v4_calculator_eta_T']
        assert abs(m * m - g2['eta_T_booked'] / v4_eta) < 1e-6, (m * m, g2['eta_T_booked'] / v4_eta)
        coupled_case.noz = m * m
        coupled_case.d0 = None
    ov = tree(inputs)
    ax = coupled_case.axis
    try:
        r = CP.run('coils + axis A1', ov, coupled_case.R4, coupled_case.d0, cap, ('coils',), None, ax.get('booked_kg', 0.0),
                   ax.get('house_W', 0.0), coupled_case.noz)
    except Exception as e:
        return {'status': 'FAILED', 'reason': f'{type(e).__name__}: {e}', 'seconds': time.time() - t0}
    out = {'status': r['status'], 'rate_cap_Hz': cap, 'iterations': r['iterations'], 'departure_trajectory_t': r['departure_trajectory_t'],
           'seconds': time.time() - t0, 'items': 'closure coils C1, C2 (re-sized each pass) + A1 tilted closure (eta_T x %.4f, Gate 2 booking)'
           % coupled_case.noz}
    if r['status'] == 'CONVERGED':
        s = r['summary']
        out['summary'] = {k: s[k] for k in ('departure_t', 'propellant_t', 'warm_km2', 'hot_km2', 'wing_tip_radius_m', 'thrust_MN')
                          if k in s}
        out['summary']['pellet_rate_Hz'] = r['fusion']['pellet_rate_Hz']
        out['summary']['stand_off_m'] = r['fusion']['stand_off_m']
        out['added_t'] = {k: v / 1e3 for k, v in r['added_kg'].items()}
    if 'loop_gain' in r:
        out['loop_gain'] = r['loop_gain']
    return out


# ------------------------------------------------------------------------------------------------------------------ driver side
def inputs_for(R, levels):
    by = {b['id']: b for b in R['breakthroughs']}
    out = dict(lab.reference_paths(R))
    for b, lv in levels.items():
        out.update(next(x for x in by[b]['levels'] if x['key'] == lv)['set'])
    return json.loads(json.dumps(out))


def git(path, *args):
    return subprocess.run(['git', '-C', str(path), *args], capture_output=True, text=True, check=True).stdout.strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--t00', type=Path, required=True, help='a checkout of the pinned T00 commit (git worktree)')
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--no-coupled', action='store_true')
    a = ap.parse_args()
    R = lab.load()
    err = lab.validate({**R, 'results': None})
    if err:
        raise SystemExit('registries invalid:\n' + '\n'.join(err))
    t00 = next(m for m in R['imports'] if m['thread'] == 'T00')
    head = git(a.t00, 'rev-parse', 'HEAD')
    if head != t00['commit']:
        raise SystemExit(f'{a.t00} is at {head}, the import is {t00["commit"]}')
    if git(a.t00, 'status', '--porcelain', '--', 'lab'):
        raise SystemExit(f'{a.t00} has local changes under lab/')
    grid = R['scenarios']['grid']
    order = lab.lever_ids(R)
    lever_levels = {b: [x['key'] for x in lab.levels_of(R, b)] for b in order}
    t_start = time.time()
    cases = {}
    free = [dict(zip(grid['levers'], combo), **{grid['launcher']: grid['launcher_free']})
            for combo in itertools.product(*(lever_levels[b] for b in grid['levers']))]
    jobs = [(str(a.t00), inputs_for(R, lv)) for lv in free]
    with ProcessPoolExecutor(a.jobs) as ex:
        for lv, res, job in zip(free, ex.map(solve_case, jobs), jobs):
            cases[lab.key(lv, order)] = {'levels': lv, 'inputs': job[1], **res}
        print(f'stage 1: {len(free)} unconstrained cases, {sum(c["closes"] for c in cases.values())} close [{time.time() - t_start:.0f} s]', flush=True)
        capped, cjobs = [], []
        for lv in free:
            k = lab.key(lv, order)
            for L in lever_levels[grid['launcher']]:
                if L == grid['launcher_free']:
                    continue
                lv2 = dict(lv, **{grid['launcher']: L})
                if cases[k]['closes']:
                    capped.append(lv2); cjobs.append((str(a.t00), inputs_for(R, lv2)))
                else:
                    cases[lab.key(lv2, order)] = {'levels': lv2, 'inputs': inputs_for(R, lv2), 'computed': False, 'closes': False,
                                                  'inferred': f'not computed: {k} does not close without a launcher limit, and a pulse-rate cap only adds a constraint'}
        for lv, res, job in zip(capped, ex.map(solve_case, cjobs), cjobs):
            cases[lab.key(lv, order)] = {'levels': lv, 'inputs': job[1], **res}
        print(f'stage 2: {len(capped)} launcher-capped cases [{time.time() - t_start:.0f} s]', flush=True)
        # named scenarios are always solved, so the reference and the presets never rest on the inference above
        named = [lab.key(n['levels'], order) for n in R['scenarios'].get('named', [])]
        named = [k for k in dict.fromkeys(named) if not cases[k]['computed']]
        for k, res in zip(named, ex.map(solve_case, [(str(a.t00), cases[k]['inputs']) for k in named])):
            cases[k] = {'levels': cases[k]['levels'], 'inputs': cases[k]['inputs'], **res}
        print(f'stage 2b: {len(named)} named scenarios solved directly [{time.time() - t_start:.0f} s]', flush=True)
        if not a.no_coupled:
            # a finite launcher enters the coupled check as the pulse-rate cap of its own uncoupled solve (held fixed, as the gate's capped runs)
            closing = [k for k in cases if cases[k]['closes']]
            caps = [(cases[k].get('launcher') or {}).get('rate_cap_Hz') for k in closing]
            for k, res in zip(closing, ex.map(coupled_case, [(str(a.t00), cases[k]['inputs'], c) for k, c in zip(closing, caps)])):
                cases[k]['coupled'] = res
            print(f'stage 3: {len(closing)} coupled checks [{time.time() - t_start:.0f} s]', flush=True)
    for c in cases.values():
        c['status'] = 'CLOSES' if c['closes'] else ('DOES_NOT_CLOSE' if c['computed'] else 'NOT_COMPUTED')
    gens = json.loads((HERE / 'imports' / t00['folder'] / 'results/convergence.json').read_text())['generations']
    repro = {}
    for n in R['scenarios'].get('named', []):
        if n.get('reproduces'):
            c = cases[lab.key(n['levels'], order)]
            t = gens[n['reproduces']]['summary']
            if t.get('converged'):
                match = c['closes'] and abs(c['summary']['departure_t'] - t['departure_t']) / t['departure_t'] < 1e-6
            else:   # T00 records this generation as not closing: so must the grid, with the same reachable acceleration
                match = (not c['closes']) and c.get('max_a0_g') is not None and abs(c['max_a0_g'] - t['max_a0_g']) / t['max_a0_g'] < 1e-6
            repro[n['id']] = {'generation': n['reproduces'], 't00_closes': bool(t.get('converged')), 't00_departure_t': t.get('departure_t'),
                              't00_max_a0_g': t.get('max_a0_g'), 'computed_closes': c['closes'],
                              'computed_departure_t': c.get('summary', {}).get('departure_t'), 'computed_max_a0_g': c.get('max_a0_g'),
                              'match': bool(match)}
    out = {'study': 'Breakthrough Lab scenario grid', 'status': 'MODEL, research only, NON-CANON',
           'provenance': {'t00_branch': t00['branch'], 't00_commit': head, 'calculator_files': {f: lab.sha256(a.t00 / f) for f in T00_FILES},
                          'registry_sha256': lab.registry_hash(), 'computed_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                          'python': platform.python_version(), 'runtime_s': round(time.time() - t_start, 1),
                          'method': 'FDP-1 fdp1-v1 through the Technology Atlas adapter (convergence.solve: compression ceiling, launcher rate cap); '
                                    'coupled check by the T00 gate fixed-point solver (coupled.run, items coils + A1 thrust loss booked as Gate 2 corrects it, eta_T x momentum factor squared). '
                                    'Every value is the calculator output for the recorded inputs; nothing is interpolated.'},
           'reproduces': repro, 'order': order, 'cases': dict(sorted(cases.items()))}
    lab.RESULTS.parent.mkdir(exist_ok=True)
    lab.RESULTS.write_text(json.dumps(out, indent=1, default=float) + '\n')
    print(json.dumps(repro, indent=1))
    print(f'wrote {lab.RESULTS.relative_to(lab.ROOT)} ({len(cases)} cases, {time.time() - t_start:.0f} s)')


if __name__ == '__main__':
    main()
