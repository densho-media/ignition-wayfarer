"""Reproduce the four-burn study: python3 lab/studies/four-burn-mission/run.py [--stage all|fast]

Writes results/results.json (everything), results/pareto.json (the slow optimisation, reused when present unless --fresh) and
results/MATRICES.md (matrices A-E and the ledgers as tables). Deterministic: no random numbers, fixed grids."""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fourburn import canon, closure, study, architectures                      # noqa: E402
from fourburn.canon import val                                                   # noqa: E402

RES = HERE/'results'
CAPS = [4500, 6000, 8000, 10000, 15000, 20000, 30000, 50000, 100000, 300000, 1000000]


def main(fresh=False):
    t0 = time.time()
    sc = canon.scenario(); ref = canon.reference()
    pay = val(sc['payload']['existing_kg']); pay_red = val(sc['payload']['reduced_kg'])
    out = {'scenario': sc['version'], 'date': sc['date']}
    out['canon_audit'] = study.canon_audit(sc, ref)
    out['matrix_A'] = study.matrix_A(sc, ref)
    out['matrix_B'] = study.matrix_B(sc, ref)
    out['fuel_ratio'] = study.fuel_ratio(sc)
    out['architectures_at_10TW'] = {f'{a}/{t}': _arch_summary(architectures.evaluate(a, sc, t, 1e13, 13e6, ref))
                                     for a in architectures.ARCHS for t in canon.TIERS}
    print(f'audit and matrices A/B {time.time()-t0:.0f}s', flush=True)
    pf = RES/'pareto.json'
    if pf.exists() and not fresh:
        par = json.loads(pf.read_text())
    else:
        par = {'existing_payload': study.pareto(sc, ref, pay, CAPS)}
        print(f'pareto {time.time()-t0:.0f}s', flush=True)
        par['accel_limit'] = {f'{a}/{t}': study.accel_limit(a, t, sc, ref, pay) for a, t in study.ARCH_TIERS}
        par['accel_limit']['CANON/central'] = study.accel_limit('CANON', 'central', sc, ref, pay)
        print(f'limits {time.time()-t0:.0f}s', flush=True)
        D = {}
        for a, t in study.ARCH_TIERS:
            for cap in (10000, 30000):
                b = study.best_at_cap(a, t, sc, ref, cap, pay)
                D[f'{a}/{t}/cap{cap//1000}kt'] = None if b is None else study._summ(b)
        D['CANON/central/1g'] = study._summ(closure.close('CANON', 'central', sc, ref, ref['ve_m_s'], 1.0, pay))
        b = study.best_at_cap('IFD-PH', 'central', sc, ref, 30000, pay_red)
        D['reduced/IFD-PH/central/cap30kt'] = None if b is None else study._summ(b)
        b = study.best_at_cap('IFD-PH', 'optimistic', sc, ref, 10000, pay_red)
        D['reduced/IFD-PH/optimistic/cap10kt'] = None if b is None else study._summ(b)
        par['designs'] = D
        print(f'designs {time.time()-t0:.0f}s', flush=True)
        par['sensitivity'] = {'IFD-PH/optimistic/10kt': study.sensitivity(sc, ref, 'IFD-PH', 'optimistic', 10000, pay),
                              'IFD-PH/central/30kt': study.sensitivity(sc, ref, 'IFD-PH', 'central', 30000, pay)}
        print(f'sensitivity {time.time()-t0:.0f}s', flush=True)
        pf.write_text(json.dumps(par, indent=1, default=float)+'\n')
    out.update(par)
    out['one_g'] = study.one_g(sc, ref, pay)
    designs = par['designs']
    out['matrix_C'] = study.matrix_C(sc, ref, [d for k, d in designs.items() if k in ('IFD-PH/optimistic/cap10kt', 'IFD-PH/central/cap30kt') and d])
    # matrix D: re-close the chosen designs to get their full tank comparison
    full = []
    for key in ('IFD-PH/optimistic/cap10kt', 'IFD-PH/central/cap30kt', 'IFD-P/optimistic/cap10kt', 'IFD-CH/optimistic/cap10kt',
                'IFD-C/optimistic/cap10kt', 'CANON/central/1g'):
        d = designs.get(key)
        if d:
            a, t = key.split('/')[:2]
            r = closure.close(a, t, sc, ref, d['ve_km_s']*1e3, d['a0_g'], pay)
            if r['converged']:
                full.append(r)
                out.setdefault('dose', {})[key] = study.dose(r)
    out['matrix_D'] = study.matrix_D(full)
    out['matrix_E'] = study.matrix_E({k: v for k, v in designs.items() if not k.startswith('reduced')})
    out['mass_cases'] = mass_cases(sc, ref, designs)
    (RES/'results.json').write_text(json.dumps(out, indent=1, default=float)+'\n')
    import report_tables
    (RES/'MATRICES.md').write_text(report_tables.render(out))
    print(f'done {time.time()-t0:.0f}s')


def _arch_summary(A):
    keep = ('arch', 'tier', 'eta_jet', 'burn_fraction', 've_max', 'heat', 'alpha_hw', 'alpha_rad', 'alpha_parts', 'fixed_kg', 'geometry',
            'ledger', 'feasible', 'reason')
    return {k: A.get(k) for k in keep}


def mass_cases(sc, ref, designs):
    """Owner brief section 5: five mass cases. Cases 1-2 fix the end mass (rocket equation only; thrust and power quoted at 1 g);
    cases 3-5 are closed designs."""
    from fourburn import rocket, kinematics
    from fourburn.const import C, G0, DAY
    dvv = val(sc['mission']['target_speed_c'])*C; out = {}
    al = closure.allowances(sc)
    for name, m_end in (('1 existing final mass', ref['op']['mission']['end_mass_kg']), ('2 illustrative 1,000 t dry', val(sc['payload']['illustrative_dry_kg']))):
        rows = []
        for ve_k in (10000, 15000, ref['ve_m_s']/1e3, 20000):
            ve = ve_k*1e3; L = rocket.ledger(m_end, ve, dvv)
            P = L['propellant_kg']; k = ref['tank_dry_fraction']
            rows.append({'ve_km_s': ve_k, 'departure_t': L['departure_kg']/1e3, 'final_t': m_end/1e3,
                         'burn_propellant_t': [x/1e3 for x in L['burn_propellant_kg']], 'propellant_t': P/1e3,
                         'propellant_fraction': P/L['departure_kg'], 'tank_t_at_0.15': k*P/1e3,
                         'reserve_t_at_2pct': al['reserve']*P/1e3,
                         'departure_thrust_MN_1g': L['departure_kg']*G0/1e6, 'departure_jet_TW_1g': L['departure_kg']*G0*ve/2/1e12,
                         'burn_days_1g': kinematics.const_accel(dvv, G0)['t_s']/DAY,
                         'burn_days_const_thrust_1g_departure': [kinematics.throttled_burn(dvv, ve, L['departure_kg']*G0, m, 1.5*G0)['t_s']/DAY
                                                                for m in L['masses_kg'][:-1]]})
        out[name] = {'note': 'end mass fixed: tanks counted inside it (no tank feedback); thrust and power if flown at 1 g', 'rows': rows}
    out['3 reduced-mass ship (560 t payload, IFD-PH central)'] = designs.get('reduced/IFD-PH/central/cap30kt')
    out['3b reduced-mass ship (560 t payload, IFD-PH optimistic)'] = designs.get('reduced/IFD-PH/optimistic/cap10kt')
    out['4 enlarged ship (IFD-PH optimistic, 30 kt)'] = designs.get('IFD-PH/optimistic/cap30kt')
    out['5 iterated ship (IFD-PH optimistic, 10 kt)'] = designs.get('IFD-PH/optimistic/cap10kt')
    out['5b iterated ship, credible tier (IFD-PH central, 30 kt)'] = designs.get('IFD-PH/central/cap30kt')
    return out


if __name__ == '__main__':
    main(fresh='--fresh' in sys.argv)
