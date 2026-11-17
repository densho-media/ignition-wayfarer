"""Vertex 2.9 analytic 3D-instability screen of the B2d cavity (research, not canon; NOT a 3D simulation).

    python3 work/vertex-2-9/instab.py        writes work/vertex-2-9/instab.json

Magnetic Rayleigh-Taylor (flute) modes on the decelerating cavity edge: growth rate gamma = sqrt(k g), k = l / R, g = v^2 / R during the
stopping time R / v, so the e-folds are N(l) = sqrt(l) for every cavity, independent of size (classical, no stabilisation).
Large-Larmor-radius (LLR) stabilisation cuts modes with k rho_i > 1 (Ripin et al. 1987 laser-plasma flutes; Hassam & Huba 1987),
so the fastest surviving mode has l_max = R / rho_i and N_max = sqrt(l_max). Amplification exp(N_max) of a seed asymmetry tells
whether an axisymmetric result can stand for the 3D pulse.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
QE = 1.602176634e-19; MP = 1.67262192e-27; C = 2.99792458e8
IONS = (('p 14.7 MeV', MP, 1, 14.7), ('p 8 MeV (thermal set)', MP, 1, 8.25), ('alpha 3.6 MeV', 4*MP, 2, 3.6), ('alpha 8 MeV', 4*MP, 2, 8.25))
CASES = (('B2d main-coil edge, R 5 m, B 1.5 T', 5.0, 1.5), ('B2d near plug, R 3 m, B 5 T', 3.0, 5.0),
         ('B2d compressed edge, R 5 m, B 3 T', 5.0, 3.0), ('cavity at 14 m (hybrid max), B 1.5 T', 14.0, 1.5))


def larmor(m, Z, E_MeV, B):
    E = E_MeV*1e6*QE; g = 1+E/(m*C*C); p = m*C*math.sqrt(g*g-1)
    return p/(Z*QE*B)


def main():
    out = []
    for cname, R, B in CASES:
        for iname, m, Z, E in IONS:
            rho = larmor(m, Z, E, B); lmax = max(R/rho, 1.0); N = math.sqrt(lmax)
            out.append(dict(case=cname, ion=iname, R_m=R, B_T=B, rho_m=rho, l_max=lmax, efolds=N, amplification=math.exp(N),
                            seed_for_order_unity=math.exp(-N)))
            print(f"{cname:40s} {iname:22s} rho {rho:5.2f} m  l_max {lmax:6.1f}  e-folds {N:4.1f}  x{math.exp(N):8.0f}  seed->1 at {math.exp(-N):.1e}")
    (HERE/'instab.json').write_text(json.dumps(out, indent=1)+'\n')


if __name__ == '__main__':
    main()
