"""Gate 2 Task D: the G1 reflection-ledger resolution sensitivity and what it means for nozzle efficiency (T00, research only, NON-CANON).

  python3 lab/variants/vertex-drive/studies/gate2/g1.py       # writes results/g1.json (minutes)

The calculator books nozzle_efficiency as a thrust efficiency eta_T = eta_mom^2 (T03; V4 0.791 = 0.8894^2, T03's reflection ledger at
1 deg). The gate found the ledger moves with resolution. This study separates the causes on the V4 coils (T03 thin shell, vacuum field):
  1. polar resolution n_th 91..2881 at two radial resolutions (numerics of the stopping surface)
  2. where the forward-going reflection comes from (polar band, surface slope |dR/dth|/R)
  3. a physical regularisation: the stopping surface smoothed over an arc of s metres (a shell of finite thickness cannot follow kinks
     finer than itself; s = 0.5-8 m against a shell thickness of order 10 % of the 50-70 m stopping radius)
  4. what each eta_T does: the momentum ledger vs the energy ledger (energy leaving as directed exhaust vs as momentum along the axis)
"""
import math
import time

import numpy as np

import g2
import axis as AX
import shell
G = g2.G


def ledger(T, v, hw, smooth_m=0.0):
    """shell.reflect on table T, optionally with the stopping surface smoothed over an arc of smooth_m metres (Gaussian sigma)."""
    if smooth_m > 0:
        raw = T.stopping
        def sm(scale, E_sr, raw=raw):
            R = raw(scale, E_sr)
            ok = np.isfinite(R)
            th = T.th; out = R.copy()
            for j in np.where(ok)[0]:
                sig = smooth_m / R[j]
                wts = np.exp(-0.5 * ((th - th[j]) / sig) ** 2) * ok
                if wts.sum() > 0:
                    out[j] = float(np.sum(wts * np.nan_to_num(R)) / wts.sum())
            return out
        T.stopping = sm
    try:
        o = shell.reflect(T, 1.0, v['E_plasma_J'], hw)
    finally:
        if smooth_m > 0:
            T.stopping = raw
    th = np.degrees(T.th)
    sf = np.array([h == 'ship_forward' for h in o['hit']])
    R = T.stopping(1.0, v['E_plasma_J'] / (4 * math.pi)) if smooth_m == 0 else None
    # energy ledger: share of the pulse energy leaving clean (any direction) and leaving clean aftward
    ax = -o['dir'][:, 2]
    clean = np.array([h is None for h in o['hit']])
    E_clean = float(np.sum(o['w'] * clean)); E_aft = float(np.sum(o['w'] * clean * (ax > 0)))
    bands = {}
    for lo, hi in ((0, 30), (30, 60), (60, 90), (90, 120), (120, 150), (150, 180)):
        m = (th >= lo) & (th < hi)
        bands[f'{lo}-{hi}'] = float(np.sum(o['w'][m & sf]))
    return {'eta_mom': o['eta_mom'], 'eta_T': o['eta_mom'] ** 2, 'strike_by': o['strike_by'],
            'ship_forward_share': float(np.sum(o['w'][sf])), 'ship_forward_by_polar_band': bands,
            'energy_clean_share': E_clean, 'energy_clean_aftward_share': E_aft,
            'mean_axial_cos_of_clean_aftward': float(np.sum(o['w'] * clean * np.clip(ax, 0, None)) / max(E_aft, 1e-12))}


def slope_census(T, v):
    R = T.stopping(1.0, v['E_plasma_J'] / (4 * math.pi)); th = T.th
    s = np.abs(np.gradient(R, th)) / R
    ok = np.isfinite(s)
    w = np.sin(th) * np.gradient(th); w /= w.sum()
    out = {}
    for c in (0.5, 1.0, 2.0, 5.0):
        out[f'>{c:g}'] = float(np.sum(w[ok & (s > c)]))
    jumps = [{'polar_deg': float(np.degrees(th[j])), 'R_m': float(R[j]), 'slope': float(s[j])}
             for j in np.where(ok & (s > 2.0))[0][:: max(1, int(np.sum(ok & (s > 2.0)) / 25) or 1)]]
    return {'share_with_|dR/dth|/R_above': out, 'steep_points_sample': jumps}


def main():
    t0 = time.time()
    v = G.v4(); hw = AX.hardware(v)
    out = {'study': 'Gate 2 Task D: G1 reflection-ledger resolution (T00)', 'status': 'MODEL, research only, NON-CANON',
           'v4_calculator_eta_T': v['ov']['base']['overrides']['pulsed']['nozzle_efficiency']['optimistic'], 'resolution': [], 'smoothing': []}
    tabs = {}
    for n_rho in (1400, 2800):
        for n_th in (91, 181, 361, 721, 1441, 2881):
            if n_rho == 2800 and n_th not in (181, 721, 2881):
                continue
            T = shell.WorkTable(v['loops'], n_th=n_th, n_rho=n_rho)
            r = ledger(T, v, hw); r.update({'n_th': n_th, 'dth_deg': 180 / (n_th - 1), 'n_rho': n_rho})
            out['resolution'].append(r); tabs[(n_th, n_rho)] = T
            print(f"n_th {n_th:5d} n_rho {n_rho}: eta_mom {r['eta_mom']:.4f} eta_T {r['eta_T']:.4f} fwd {r['ship_forward_share']:.4f} "
                  f"bands { {k: round(x, 4) for k, x in r['ship_forward_by_polar_band'].items() if x > 1e-4} } [{time.time() - t0:.0f} s]", flush=True)
    T = tabs[(2881, 1400)]
    out['slope_census_2881'] = slope_census(T, v)
    for s in (0.5, 1.0, 2.0, 4.0, 8.0):
        for n_th in (721, 2881):
            r = ledger(tabs[(n_th, 1400)], v, hw, smooth_m=s); r.update({'smooth_m': s, 'n_th': n_th})
            out['smoothing'].append(r)
            print(f"smooth {s:4.1f} m n_th {n_th}: eta_mom {r['eta_mom']:.4f} eta_T {r['eta_T']:.4f} fwd {r['ship_forward_share']:.4f} [{time.time() - t0:.0f} s]", flush=True)
    out['runtime_s'] = time.time() - t0
    g2.write('g1.json', out)


if __name__ == '__main__':
    main()
