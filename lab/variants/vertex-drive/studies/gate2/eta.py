"""Gate 2 Task D: nozzle thrust efficiency against FDP-1 closure on V4 alone (T00, research only, NON-CANON).

  python3 lab/variants/vertex-drive/studies/gate2/eta.py      # writes results/eta.json (about a minute)

eta_T (the calculator's nozzle_efficiency, = eta_mom^2) is swept on the plain V4 solve (no coupled extras) and the closure threshold is
bisected. The G1 band (results/g1.json) runs from 0.67 (fine grid) to 0.80 (regularised); V4 books 0.791 (1 deg grid).
"""
import g2
G = g2.G
NOZ = 'base.overrides.pulsed.nozzle_efficiency.optimistic'


def solve(ov, eta):
    R = G.C.fdp1.solve('baseline', G.core(G.C.P(ov, **{NOZ: eta})))
    return R, (G.C.fdp1.summary(R) if R.get('converged') else None)


def main():
    ov = G.v4_overrides(); rows = []
    for eta in (0.82, 0.80, 0.791, 0.78, 0.765, 0.75, 0.74, 0.72, 0.70, 0.67):
        R, s = solve(ov, eta)
        rows.append({'eta_T': eta, 'converged': bool(s), 'departure_t': s['departure_t'] if s else None,
                     'rate_Hz': R['fusion']['pellet_rate_Hz'] if s else None, 'reason': None if s else str(R.get('reason'))[:160]})
        print(rows[-1], flush=True)
    lo, hi = 0.60, 0.791
    for _ in range(12):
        m = 0.5 * (lo + hi)
        _, s = solve(ov, m)
        lo, hi = (lo, m) if s else (m, hi)
    g2.write('eta.json', {'study': 'Gate 2 Task D: eta_T vs FDP-1 closure (V4 alone)', 'status': 'MODEL, research only, NON-CANON',
                          'rows': rows, 'closure_threshold_eta_T': hi,
                          'd_departure_d_eta_near_V4_t_per_0.01': None})
    print('threshold', hi)


if __name__ == '__main__':
    main()
