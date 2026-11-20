"""Benchmark 1: the field solver against the exact loop field (a current ring represented on the grid)."""
import math, sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hybrid as H
NC = H.NC
out = {}
for FREE in (False, True):
 for dx in (0.5, 0.25):
      g = H.Grid(40.0, -30.0, 60.0, dx)
      I = 1e6; R = 10.0; zc = 0.0
      J = np.zeros((g.Nr, g.Nz)); i = int(round(R/dx)); j = int(round((zc-g.z0)/dx))
      J[i, j] = I/(dx*dx)
      psi = g.poisson(J, free=FREE)
      Br, Bz = g.B_of(psi)
      pts = [(0.0, 9.0), (0.0, 20.0), (5.0, 9.0), (15.0, 15.0), (3.0, -6.0)]
      errs = []
      for (rr, zz) in pts:
          ii = int(round(rr/dx)); jj = int(round((zz-g.z0)/dx))
          br, bz, _ = NC.loop(I, R, zc, np.array([rr]), np.array([zz]))
          Bn = math.hypot(Br[ii, jj], Bz[ii, jj]); Be = math.hypot(br[0], bz[0])
          errs.append(Bn/Be-1)
      out[(FREE,dx)] = errs
      print(f"free {FREE} dx {dx}: relative |B| error at {pts}: {[f'{e:+.4f}' for e in errs]}")
