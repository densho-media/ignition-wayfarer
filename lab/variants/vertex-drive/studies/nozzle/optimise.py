"""Current-pattern optimisation of axisymmetric nozzle coil sets in the thin-shell model (Nelder-Mead, standard library + numpy)."""
import math

import numpy as np

import configs as C
import shell


def nelder_mead(f, x0, step=0.4, iters=160, tol=1e-5):
    n = len(x0); pts = [np.array(x0, float)]
    for i in range(n):
        x = np.array(x0, float); x[i] += step; pts.append(x)
    vals = [f(x) for x in pts]
    for _ in range(iters):
        o = np.argsort(vals); pts = [pts[i] for i in o]; vals = [vals[i] for i in o]
        if abs(vals[-1] - vals[0]) < tol:
            break
        c = np.mean(pts[:-1], axis=0)
        xr = c + (c - pts[-1]); fr = f(xr)
        if fr < vals[0]:
            xe = c + 2 * (c - pts[-1]); fe = f(xe)
            pts[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            pts[-1], vals[-1] = xr, fr
        else:
            xc = c + 0.5 * (pts[-1] - c); fc = f(xc)
            if fc < vals[-1]:
                pts[-1], vals[-1] = xc, fc
            else:
                pts = [pts[0] + 0.5 * (q - pts[0]) for q in pts]; vals = [f(q) for q in pts]
    i = int(np.argmin(vals))
    return pts[i], vals[i]


def scaled(geom, x, W_target, E_p):
    """Currents with pattern x (signed, any scale) scaled so the stored energy equals W_target (two fixed-point steps)."""
    I = np.array(x, float) * 1e7
    for _ in range(3):
        L = C.with_currents(geom, I)
        W = C.stored_energy(L)
        I = I * math.sqrt(W_target / W)
    return C.with_currents(geom, I)


def evaluate(loops, E_p, hw, n_th=121):
    T = shell.WorkTable(loops, n_th=n_th, n_rho=500)
    return shell.reflect(T, 1.0, E_p, hw)


def best_pattern(geom, ratio, E_p, hw, x0=None, iters=120):
    W_t = ratio * E_p
    def cost(x):
        L = scaled(geom, x, W_t, E_p)
        o = evaluate(L, E_p, hw)
        return -(o['eta_mom'])
    x0 = np.ones(len(geom)) if x0 is None else np.array(x0)
    x, v = nelder_mead(cost, x0, step=0.5, iters=iters)
    L = scaled(geom, x, W_t, E_p)
    o = evaluate(L, E_p, hw, n_th=181)
    return x, L, o
