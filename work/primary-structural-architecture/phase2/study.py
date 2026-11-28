"""PSA Phase II study driver: sizes every concept variant on its configuration, runs stability, damage and sensitivities, and writes
results/p2_*.json (summary, per-variant detail, and Blender geometry for the review file).

    python3 work/primary-structural-architecture/phase2/study.py [--only H:bypass:F1,...] [--quick]

All numbers are STUDY / NONCANON. Production geometry and canon are untouched.
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import analysis as an  # noqa: E402
import configs  # noqa: E402
import failure  # noqa: E402
import model as mdl  # noqa: E402

OUT = H.parent / 'results'
VARIANTS = [
    # (concept, rotor bay, configuration, options)
    ('H', 'bypass', 'F1', {}), ('H', 'hub', 'F1', {}),
    ('HC', 'bypass', 'F1', {}), ('HC', 'hub', 'F1', {}),
    ('A', 'bypass', 'F1', {}), ('A', 'hub', 'F1', {}),
    ('C', 'bypass', 'F1', {}), ('C', 'hub', 'F1', {}),
    ('H3', 'hub', 'F1', {}),                                   # three single rails, same grammar: the redundancy penalty
    ('H', 'hub', 'P', {}), ('H', 'hub', 'R', {}),              # configuration dependence
    ('HC', 'hub', 'P', {}), ('HC', 'hub', 'R', {}),
    ('H', 'hub', 'F1', {'radius': 7.0}), ('H', 'hub', 'F1', {'radius': 9.0}),   # morphology: does a larger structural radius pay off?
]


def key(c, r, cfg, opt):
    return f'{c}:{r}:{cfg}' + ''.join(f':{k}={v}' for k, v in sorted(opt.items()))


def geometry(b, res, steady, ux=None):
    """Nodes and members with section, material, steady force and utilisation, for Blender and the report."""
    env = res['env']; nodes = [list(map(float, x)) for x in b.m.X]; mem = []
    for i, (e, md) in enumerate(zip(b.m.el, b.meta)):
        if e['kind'] == 'spring':
            continue
        s = b.sec.get(md['group'], dict(r=0.6, t=0.06, mat='IFACE'))
        f = steady['f'][i]
        u = res['sizing'].get(md['group'], {}).get('util', 0.0)
        mem.append(dict(a=e['a'], b=e['b'], fam=md['fam'], group=md['group'], r=round(s['r'], 4), t=round(s['t'], 4), mat=s['mat'],
                        N_MN=round(f['N']*steady['scale']/1e6, 4) if f else 0.0, M_MNm=round(math.hypot(f['My'], f['Mz'])*steady['scale']/1e6, 4) if f else 0.0,
                        T_MNm=round(f['T']/1e6, 4) if f else 0.0, Nc_env_MN=round(env['Nc'][i]/1e6, 3), group_util=round(u, 3)))
    return dict(nodes=nodes, ux_mm=[round(float(v)*1e3*steady['scale'], 2) for v in ux] if ux is not None else None, members=mem, nozzles=b.noz, deck=b.deck_nodes, brow=b.brow_nodes, spine=[b.spine[x] for x in sorted(b.spine)])


def section_loads(b, f, scale):
    """Axial force resultant through cut planes along X (steady case): the integrated section load (D01 reconciliation)."""
    out = []
    for xc in np.arange(-130.0, 140.0, 10.0):
        tot = 0.0
        for e, md, fe_ in zip(b.m.el, b.meta, f):
            if fe_ is None or e['kind'] == 'spring' or not e['on']:
                continue
            xa, xb = b.m.X[e['a']][0], b.m.X[e['b']][0]
            if min(xa, xb) < xc <= max(xa, xb) and abs(xb-xa) > 1e-6:
                L = np.linalg.norm(b.m.X[e['b']]-b.m.X[e['a']]); tot += fe_['N']*abs(xb-xa)/L
        out.append(dict(x=float(xc), N_MN=float(tot*scale/1e6)))
    return out


def run_variant(c, r, cfgname, opt, quick=False, log=print):
    t0 = time.time()
    hist = configs.history(cfgname, 2 if quick else 3)
    b = mdl.Build(c, hist[0]['cfg'], rotor=r, **opt)
    res = an.run(b, hist, iters=2 if quick else 4, log=log)
    sm, by = b.structure_mass()
    steady = next(x for x in res['cases'] if x['name'].startswith('steady x') and x['left'] == 1.0)
    end_steady = next(x for x in res['cases'] if x['name'].startswith('steady x') and x['left'] == 0.0)
    b.attach(hist[0]['cfg']['parts'])
    eq = max(x['res'] for x in res['cases'])
    out = dict(key=key(c, r, cfgname, opt), concept=c, rotor=r, config=cfgname, config_id=hist[0]['cfg']['id'], rails=b.rails,
               members_t=sm/1e3, joints_t=res['joints_t'], structure_t=sm/1e3+res['joints_t'], by_family_t={k: v/1e3 for k, v in by.items()},
               mass_hist_t=res['mass_hist_t'], stiffness=res['stiffness'], strength_members_t=res['strength_members_t'], stiffness_increment_t=res['stiffness_increment_t'], equilibrium_residual_N=eq, dlf=steady['dlf'], f_axial_Hz=steady['f_axial'],
               modes=steady['modes'][:8], failing=[g for g, v in res['sizing'].items() if not v['passes']],
               sizing=res['sizing'], departure_t=sum(p['m'] for p in hist[0]['cfg']['parts'])/1e3+sm/1e3+res['joints_t'],
               section_loads=section_loads(b, steady['f'], steady['scale']), section_loads_end=section_loads(b, end_steady['f'], end_steady['scale']))
    gov = {}
    for i, g in enumerate(res['env']['gov']):
        if g:
            gov[g.split(' (')[0]] = gov.get(g.split(' (')[0], 0)+1
    out['governing_case_count'] = gov
    if not quick:
        N = [f['N'] if f else 0.0 for f in steady['f']]
        b.attach(hist[0]['cfg']['parts']); rs, _ = an.solve(b)       # reset loads to the steady thrust for the follower matrix
        stab = {}
        for name, kw in (('fixed-direction', dict(partial=0.0)), ('follower', dict(partial=1.0)), ('partial follower 0.5', dict(partial=0.5)),
                         ('follower + TVC gain 1', dict(partial=1.0, tvc_gain=1.0))):
            try:
                stab[name] = an.reduced_stability(b, N, lam_hi=60.0, nbasis=40, **kw)
            except Exception as ex:
                stab[name] = dict(error=str(ex))
        out['stability'] = stab
        out['damage'] = failure.run(b, steady['dlf'])
        (OUT / 'p2_geom').mkdir(parents=True, exist_ok=True)
        (OUT / 'p2_geom' / (out['key'].replace(':', '_')+'.json')).write_text(json.dumps(geometry(b, res, steady, rs['u'][0::6])))
    out['seconds'] = time.time()-t0
    log(f"{out['key']}: members {out['members_t']:.1f} t + joints {out['joints_t']:.1f} t, failing {len(out['failing'])}, {out['seconds']:.0f} s")
    return out


def merge():
    path = OUT / 'p2_variants.json'
    allres = json.loads(path.read_text()) if path.exists() else {}
    for f in sorted((OUT / 'p2_var').glob('*.json')):
        r = json.loads(f.read_text()); allres[r['key']] = r
    order = [key(*v) for v in VARIANTS]
    allres = {k: allres[k] for k in sorted(allres, key=lambda k: order.index(k) if k in order else 99)}
    path.write_text(json.dumps(allres, indent=1, default=float))
    return allres


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--only', default=''); ap.add_argument('--quick', action='store_true')
    ap.add_argument('--merge', action='store_true'); ap.add_argument('--part', default='')
    a = ap.parse_args()
    (OUT / 'p2_var').mkdir(parents=True, exist_ok=True)
    if a.merge:
        merge(); return
    sel = [v for v in VARIANTS if not a.only or key(*v) in a.only.split(',')]
    if a.part:
        i, n = map(int, a.part.split('/')); sel = sel[i::n]
    for v in sel:
        r = run_variant(*v, quick=a.quick)
        (OUT / 'p2_var' / (r['key'].replace(':', '_')+'.json')).write_text(json.dumps(r, indent=1, default=float))
    merge()


if __name__ == '__main__':
    main()
