"""Vertex 2.9 reduced-hybrid runs (research, not canon): benchmarks, B2d convergence and sensitivity.

    NUMBA_NUM_THREADS=1 python3 lab/studies/vertex-closure/vertex-2-9/scan.py [set]     writes lab/studies/vertex-closure/vertex-2-9/scan_<set>.json

Every run reports its own energy and momentum closure; a run is only as credible as that closure (see NOTES.md).
"""
import json
import math
import os
import sys
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent/'vertex-2-8'))
import hybrid as H  # noqa: E402
import nozzle as Z  # noqa: E402
import nozzle_core as NC  # noqa: E402

KEEP = ('kappa', 'fractions', 'forward_energy', 'forward_on_ship', 'forward_number', 'aft_cos', 'coil_impulse_grid', 'coil_hit_E',
        'E_on_grid_at_end', 'max_energy_error', 'max_momentum_error', 'cavity_R_max', 'steps', 'dt', 'dx', 'n_part', 'n_c', 'Ep', 'seconds',
        'spectrum')


def b2d(B_plug=5.0, B_main=1.5, zp=-6.0, Rp=3.0):
    return [Z.plug(B_plug, Rp=Rp, zp=zp), Z.main(B_main)]


def job(spec):
    name, kw = spec
    kw = dict(kw)
    co = kw.pop('coils'); ratio = kw.pop('ratio', 150.0); comp = kw.pop('comp', (0.080, 'thermal', 0.95))
    spc = NC.species_set(*comp)
    if 'Ep' not in kw:
        kw['Ep'] = NC.stored_energy(co)/ratio if co else None
    uniform = kw.pop('uniform_B', None)
    zb = kw.pop('zb', 9.0)
    r = H.run(co, zb, kw.pop('Ep'), spc, ship=Z.SHIP, uniform_B=uniform, record=True, **kw)
    out = {k: r[k] for k in KEEP}
    out['final'] = r['hist'][-1] if r['hist'] else None
    print(f"{name:28s} kappa {r['kappa']:.3f} fwd {r['forward_energy']:.4f} ship {r['forward_on_ship']:.4f} aftcos {r['aft_cos']:.3f} "
          f"dE {r['max_energy_error']:.3f} dP {r['max_momentum_error']:.3f} {r['seconds']:.0f}s", flush=True)
    return name, out


BASE = dict(coils=b2d(), n_part=20000, dx=0.5, n_c=1e17, t_max=6e-6)
SETS = {
    'conv': [
        ('B2d_nc3e16', dict(BASE, n_c=3e16)),
        ('B2d_nc1e17', dict(BASE)),
        ('B2d_nc3e17', dict(BASE, n_c=3e17)),
        ('B2d_nc1e18', dict(BASE, n_c=1e18)),
        ('B2d_dx0.35', dict(BASE, dx=0.35)),
        ('B2d_np40k', dict(BASE, n_part=40000)),
        ('B2d_seed2', dict(BASE, seed=2)),
        ('B2d_lowbeta', dict(BASE, ratio=1e5)),
    ],
    'bench': [
        ('A_lowbeta', dict(BASE, coils=[Z.main(0.96)], zb=20.0, ratio=1e5)),
        ('B4_single_30deg', dict(BASE, coils=[Z.main(0.96)], zb=10.0/math.tan(math.radians(30)), ratio=5.0)),
        ('B4_single_50deg', dict(BASE, coils=[Z.main(0.96)], zb=10.0/math.tan(math.radians(50)), ratio=5.0)),
        ('B4_single_70deg', dict(BASE, coils=[Z.main(0.96)], zb=10.0/math.tan(math.radians(70)), ratio=5.0)),
    ],
    'sens': [
        ('B2d_Ep_x0.5', dict(BASE, ratio=300.0)),
        ('B2d_Ep_x2', dict(BASE, ratio=75.0)),
        ('B2d_field_x0.7', dict(BASE, coils=b2d(3.5, 1.05), ratio=150.0*0.49)),
        ('B2d_plug_z-9', dict(BASE, coils=b2d(zp=-9.0))),
        ('B2d_plug_R2', dict(BASE, coils=b2d(Rp=2.0))),
        ('B2d_burn_z7', dict(BASE, zb=7.0)),
        ('B2d_burn_z11', dict(BASE, zb=11.0)),
        ('B2d_comp_b0.99', dict(BASE, comp=(0.080, 'charge', 0.99))),
        ('B2d_r0_2m', dict(BASE, r0=2.0)),
        ('B2d_Te10keV', dict(BASE, Te_keV=10.0)),
    ],
}

SETS['sens18'] = [(n+'_nc1e18', dict(kw, n_c=1e18)) for n, kw in SETS['sens']]
SETS['all2'] = SETS['bench']+SETS['sens']+SETS['sens18']

if __name__ == '__main__':
    which = sys.argv[1]
    with Pool(4) as p:
        res = dict(p.map(job, SETS[which], chunksize=1))
    (HERE/f'scan_{which}.json').write_text(json.dumps(res, indent=1, default=float)+'\n')
