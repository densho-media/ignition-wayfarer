"""Vertex 2.10 candidate A: forward magnetic plug variants, traced (research, not canon).

    NUMBA_NUM_THREADS=1 python3 work/vertex-2-10/forward.py [set]     writes work/vertex-2-10/forward_<set>.json and .log

Screening rule (owner O2, kept): kappa = min(collective cavity c = 1.0, single-ion Boris trace); forward stream = the larger regime.
The 2.9 reduced hybrid is NOT used for credit. Every config is one engine: +z aft, main coil R 10 m at z = 0, burn on axis at zb.
Where every escape goes: AFT (space), FORWARD onto the ship disk (r 45 m, offset 24 m, 200 m spine), FORWARD past the ship, RADIAL,
and onto the three neighbour engines of the A+ cluster (envelope r 11.44 m, z -31.9 .. +5 m, axes 33.9, 33.9 and 48 m away): a
straight ray from the escape's last point along its last direction, averaged over azimuth (axisymmetric source).
"""
import json
import math
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'vertex-2-8'))
import nozzle as Z  # noqa: E402
import nozzle_core as N  # noqa: E402

MU0 = N.MU0
NEIGH = ((33.94, 0.0), (33.94, 0.0), (48.0, 0.0))     # axis distance of the three neighbours (the azimuth is averaged anyway)
A_ENV = 11.44; Z_LO = -31.93; Z_HI = 5.0


def coil(B, R, z, name, a=0.2, fin=0.5):
    return dict(I=2*R*B/MU0, R=R, z=z, a=a, fin=fin, name=name)


def neighbour_fraction(p, d, nphi=180):
    """Azimuth-averaged share of a ray from p (r, z in the own frame) with direction d that strikes a neighbour engine envelope."""
    r0 = math.hypot(p[0], p[1]); z0 = p[2]
    dh = math.hypot(d[0], d[1]); dz = d[2]
    if dh < 1e-6:
        return 0.0
    hit = 0.0
    for D, _ in NEIGH:
        cnt = 0
        for k in range(nphi):
            ph = (k+0.5)*2*math.pi/nphi
            # start at radius r0 at azimuth 0 heading horizontally at angle ph from the outward radial, neighbour at angle psi = 0 ..
            # averaging over the neighbour's azimuth is the same as averaging over the ray azimuth: neighbour at (D cos ph, D sin ph)
            cx, cy = D*math.cos(ph)-r0, D*math.sin(ph)
            ux, uy = d[0]/dh, d[1]/dh if False else 0.0
            ux, uy = 1.0, 0.0                      # ray direction in the horizontal plane (outward radial; the start radius is small)
            b = cx*ux+cy*uy; c = cx*cx+cy*cy-A_ENV*A_ENV; disc = b*b-c
            if disc < 0 or b < 0:
                continue
            s = b-math.sqrt(disc)                   # horizontal distance to the envelope
            if s < 0:
                s = 0.0
            z = z0+s*dz/dh
            if Z_LO <= z <= Z_HI:
                cnt += 1
        hit += cnt/nphi
    return min(hit, 1.0)


def tp_full(coils, zb, src_r=0.0):
    sp = N.species_set(Z.VE_C, 'thermal', 0.95)
    mu, dmu = Z.mu_grid()
    tr = N.trace(coils, zb, sp, list(mu), src_r=src_r, box=150.0, ship=Z.SHIP)
    w = np.array([s['n'] for s in sp for _ in dmu])*np.array(list(dmu)*len(sp))
    S = N.summarize(tr, coils, weights=w)
    st = tr['status']; E0 = tr['E0']; W0 = float(np.sum(w*E0)); pf = tr['pf']; p0 = np.linalg.norm(tr['u0'], axis=1); P0 = float(np.sum(w*p0))
    nb = np.zeros(len(st))
    for i in np.where((st == 'RADIAL') | (st == 'FORWARD'))[0]:
        d = pf[i]/np.linalg.norm(pf[i])
        nb[i] = neighbour_fraction(tr['xf'][i], d)*(1.0-tr['ship_frac'][i])
    S['radial_or_forward_on_neighbours'] = float(np.sum(w*nb*E0)/W0)
    # kappa with the neighbour strikes also absorbed (they no longer leave the ship system)
    space = (st == 'AFT') | (st == 'RADIAL') | (st == 'FORWARD')
    leave = np.where(space, 1.0-tr['ship_frac']-nb, 0.0)
    S['kappa_cluster'] = float(np.sum(w*leave*pf[:, 2])/P0)
    # forward-escape spectrum (energy per ion and E/q, MeV and MV), energy-weighted quantiles, for the recovery candidate B
    fw = st == 'FORWARD'
    if fw.any():
        Ef = tr['Ef'][fw]/N.MEV if hasattr(N, 'MEV') else tr['Ef'][fw]/1.602176634e-13
        q = np.array([s['Z'] for (s, _, _) in tr['rows']])[fw]
        ww = (w*tr['Ef'])[fw]
        order = np.argsort(Ef/q); cum = np.cumsum(ww[order])/ww.sum()
        S['forward_Eq_MV_quantiles'] = {f'{p}': float((Ef/q)[order][np.searchsorted(cum, p/100)]) for p in (10, 50, 90, 99)}
        S['forward_species_energy_share'] = {}
        for nm in set(s['name'] for s, _, _ in tr['rows']):
            sel = np.array([s['name'] == nm for (s, _, _) in tr['rows']])[fw]
            S['forward_species_energy_share'][nm] = float(ww[sel].sum()/ww.sum())
        S['forward_samples'] = [dict(E_MeV=float(e), Z=int(z), w=float(x)) for e, z, x in zip(Ef, q, ww/W0)]
        r_end = np.hypot(tr['xf'][fw, 0], tr['xf'][fw, 1])
        S['forward_r_at_exit_m'] = [float(np.percentile(r_end, p)) for p in (50, 90)]
    return S


def evaluate(spec):
    key, label, coils, zb, ratio, coll = spec
    t0 = time.time()
    EB = N.stored_energy(coils); Ep = EB/ratio
    S = tp_full(coils, zb)
    row = dict(key=key, label=label, zb_m=zb, coils=[dict(name=c['name'], R_m=c['R'], z_m=c['z'], I_MA=c['I']/1e6,
               B_centre_T=MU0*c['I']/(2*c['R'])) for c in coils], E_B_GJ=EB/1e9, E_p_MJ=Ep/1e6, EB_over_Ep=ratio, test_particle=S,
               coil_force_z_MN=[f/1e6 for f in N.coil_force_z(coils)], B_burn_T=Z.burn_field(coils, zb))
    if coll:
        a, b = Z.coll(coils, zb, Ep)
        row['collective'] = dict(c1=dict(kappa=a['kappa'], fractions=a['fractions'], aft_cos=a['aft_cos']),
                                 c15=dict(kappa=b['kappa'], fractions=b['fractions']))
        trap = a['fractions']['TRAPPED']
        row['kappa_credit'] = min(a['kappa'], S['kappa_cluster']) if trap < 0.5 else 0.0
        row['forward_coll'] = a['fractions']['FORWARD']
    row['seconds'] = time.time()-t0
    f = S['fractions']
    print(f"{key:10s} {label:52s} EB {EB/1e9:6.1f} GJ | TP k {S['kappa']:.3f} kc {S['kappa_cluster']:.3f} fwd {f['FORWARD']:.4f} "
          f"ship {S['forward_on_ship']:.4f} rad {f['RADIAL']:.4f} nb {S['radial_or_forward_on_neighbours']:.4f} coil {f['COIL']:.4f} "
          f"trap {f['TRAPPED']:.4f} | " + (f"coll {row['collective']['c1']['kappa']:.3f} fwdc {row['forward_coll']:.4f} credit {row['kappa_credit']:.3f} | " if coll else '')
          + f"Fz {[round(x, 1) for x in row['coil_force_z_MN']]} MN ({row['seconds']:.0f}s)", flush=True)
    return row


M15 = coil(1.5, 10.0, 0.0, 'main', a=0.15, fin=1.0)
SETS = {
    'explore': [
        ('B2d', 'reference: plug 5 T R3 z-6, main 1.5 T, burn 9', [coil(5.0, 3.0, -6.0, 'plug'), M15], 9.0, 150, False),
        ('M10', 'mirror plug 10 T R3 z-6', [coil(10.0, 3.0, -6.0, 'plug'), M15], 9.0, 150, False),
        ('M20', 'mirror plug 20 T R3 z-6', [coil(20.0, 3.0, -6.0, 'plug'), M15], 9.0, 150, False),
        ('M5n', 'mirror plug 5 T R2 z-2 (near)', [coil(5.0, 2.0, -2.0, 'plug'), M15], 9.0, 150, False),
        ('W8', 'wide mirror plug 3 T R8 z-8', [coil(3.0, 8.0, -8.0, 'plug'), M15], 9.0, 150, False),
        ('K12', 'cusp: reversed 3 T R3 at z-12 (no plug)', [coil(-3.0, 3.0, -12.0, 'cusp'), M15], 9.0, 150, False),
        ('DP14', 'double: plug 5 T z-6 + reversed 3 T R5 z-14', [coil(5.0, 3.0, -6.0, 'plug'), coil(-3.0, 5.0, -14.0, 'cusp'), M15], 9.0, 150, False),
        ('DP20', 'double: plug 5 T z-6 + reversed 2 T R8 z-20', [coil(5.0, 3.0, -6.0, 'plug'), coil(-2.0, 8.0, -20.0, 'cusp'), M15], 9.0, 150, False),
        ('DP10', 'double: plug 5 T z-6 + reversed 5 T R3 z-10', [coil(5.0, 3.0, -6.0, 'plug'), coil(-5.0, 3.0, -10.0, 'cusp'), M15], 9.0, 150, False),
        ('TM', 'two mirrors: plug 5 T z-6 + 5 T R3 z-14', [coil(5.0, 3.0, -6.0, 'plug'), coil(5.0, 3.0, -14.0, 'plug2'), M15], 9.0, 150, False),
        ('B2d_z12', 'reference coils, burn 12 (further from plug)', [coil(5.0, 3.0, -6.0, 'plug'), M15], 12.0, 150, False),
        ('M5_main2', 'plug 5 T + main 2.0 T, burn 9', [coil(5.0, 3.0, -6.0, 'plug'), coil(2.0, 10.0, 0.0, 'main', a=0.15, fin=1.0)], 9.0, 150, False),
    ],
    'final': [
        ('B2d', 'reference: plug 5 T R3 z-6, main 1.5 T, burn 9', [coil(5.0, 3.0, -6.0, 'plug'), M15], 9.0, 150, True),
        ('B2d_z12', 'B2d coils, burn 12', [coil(5.0, 3.0, -6.0, 'plug'), M15], 12.0, 150, True),
        ('B2d_z15', 'B2d coils, burn 15', [coil(5.0, 3.0, -6.0, 'plug'), M15], 15.0, 150, True),
        ('M10', 'mirror plug 10 T, burn 9', [coil(10.0, 3.0, -6.0, 'plug'), M15], 9.0, 150, True),
        ('M10_z12', 'mirror plug 10 T, burn 12', [coil(10.0, 3.0, -6.0, 'plug'), M15], 12.0, 150, True),
        ('M20_z12', 'mirror plug 20 T, burn 12', [coil(20.0, 3.0, -6.0, 'plug'), M15], 12.0, 150, True),
        ('DP14', 'double: plug 5 T z-6 + reversed 3 T R5 z-14', [coil(5.0, 3.0, -6.0, 'plug'), coil(-3.0, 5.0, -14.0, 'cusp'), M15], 9.0, 150, True),
        ('K12', 'cusp only: reversed 3 T R3 z-12', [coil(-3.0, 3.0, -12.0, 'cusp'), M15], 9.0, 150, True),
    ],
}

if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'explore'
    with Pool(4) as p:
        rows = p.map(evaluate, SETS[which], chunksize=1)
    (HERE/f'forward_{which}.json').write_text(json.dumps(dict(rows=rows), indent=1, default=float)+'\n')
