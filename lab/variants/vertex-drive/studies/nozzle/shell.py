"""Thin-shell ("Newtonian") stopping-surface and reflection model of a beta >> 1 pulse in a vacuum nozzle field.

MODEL, not MHD. Each solid-angle element of the expanding shell carries E_p/(4 pi) per steradian and moves radially from the burn
point. It does work against the magnetic pressure p = B_t^2/(2 mu0) of the flux it excludes, with B_t the tangential surface field
of a flux-excluding sphere (exact multipole solution, fixed coil currents) out to 0.97 of the nearest-loop distance and, beyond,
the vacuum tangential field scaled to join it continuously along each ray. The element stops where its work equals its energy and
is reflected specularly (normal velocity reversed, tangential kept, speed unchanged: elastic, ideal flux conservation). Left out:
lateral flow along the surface, shell thickness and velocity spread, the coils' flux-conserving current rise (which would stop the
shell slightly earlier), instabilities, resistivity, reconnection and detachment. Pressure scales with current squared, so one
work table per current pattern serves every current scale.
"""
import math

import numpy as np

import fields as F
from multipole import Expansion, legendre_all


class WorkTable:
    """Cumulative work per steradian along rays, for a current pattern at unit scale (loops carry I as given)."""

    def __init__(self, loops, n_th=181, n_rho=700, rmax=None, lmax=160, extra_vac=None):
        self.loops = loops
        self.th = np.linspace(0.0, math.pi, n_th)
        X = Expansion(loops, lmax); self.d0 = X.d0
        rmax = rmax or 1.25 * max(L['d'] for L in loops)
        self.rho = np.linspace(rmax / n_rho, rmax, n_rho)
        rj = 0.97 * X.d0
        st, ct = np.sin(self.th), np.cos(self.th)
        # inner part: exact sphere surface field on the (rho, th) grid
        P, dP = legendre_all(lmax, ct)
        l = np.arange(lmax + 1)[:, None]
        inn = self.rho <= rj
        x = self.rho[inn][None, :] / X.d0
        A = X.alpha[:, None] * x ** l / self.rho[inn][None, :] * (2 * l + 1) / (l + 1)     # (L, n_in)
        Bt = np.zeros((n_rho, n_th))
        Bt[inn] = A.T @ (dP * st[None, :])
        # outer part: vacuum tangential field, scaled per ray to be continuous at rj
        Rg, Tg = np.meshgrid(self.rho, self.th, indexing='ij')
        Br, Bz = F.loops_field(loops, Rg * np.sin(Tg), Rg * np.cos(Tg))
        if extra_vac is not None:
            Br = Br + extra_vac[0]; Bz = Bz + extra_vac[1]
        Brho = Br * np.sin(Tg) + Bz * np.cos(Tg)
        Vt = np.sqrt(np.maximum(Br ** 2 + Bz ** 2 - Brho ** 2, 0.0))
        bj = np.abs(A.T[-1] @ (dP * st[None, :])) if np.any(inn) else np.zeros(n_th)
        k = np.where(Vt[np.sum(inn) - 1] > 0, bj / np.maximum(Vt[np.sum(inn) - 1], 1e-300), 1.5)
        Bt[~inn] = Vt[~inn] * k[None, :]
        self.Bt = Bt
        p = Bt ** 2 / (2 * F.MU0)
        f = p * self.rho[:, None] ** 2
        self.work = np.vstack([np.zeros((1, n_th)), np.cumsum(0.5 * (f[1:] + f[:-1]) * np.diff(self.rho)[:, None], axis=0)])
        self.rho_w = np.concatenate([[0.0], self.rho[1:]]) if False else np.concatenate([[self.rho[0]], self.rho[1:]])

    def stopping(self, scale, E_sr):
        """R(th) for currents x scale (NaN where unstopped inside rmax)."""
        W = self.work * scale ** 2
        R = np.full(len(self.th), np.nan)
        for j in range(len(self.th)):
            i = np.searchsorted(W[:, j], E_sr)
            if 0 < i < len(self.rho):
                f = (E_sr - W[i - 1, j]) / (W[i, j] - W[i - 1, j])
                R[j] = self.rho[i - 1] + f * (self.rho[i] - self.rho[i - 1])
        return R


def hardware_set(p, tube_m, struts=True):
    hw = [{'kind': 'loop', 'name': L['name'], 'R': L['R'], 'z': L['z'], 'tube': tube_m} for L in p['loops']]
    hw.append({'kind': 'disc', 'name': 'shield', 'z': p['shield_z_m'], 'R': p['shield_radius_m']})
    return hw


def ray_hits_many(P0, D, hardware, s_max=1500.0, n=3000):
    """Name of the first hardware item each ray P0 + s D (rays as rows) meets, or None."""
    s = np.linspace(0.05, s_max, n)
    X = P0[:, None, :] + s[None, :, None] * D[:, None, :]
    r = np.hypot(X[..., 0], X[..., 1]); z = X[..., 2]
    best = np.full(len(P0), np.inf); name = np.array([None] * len(P0), dtype=object)
    for h in hardware:
        if h['kind'] == 'loop':
            hit = np.hypot(r - h['R'], z - h['z']) < h['tube']
        else:
            zs = z - h['z']
            hit = np.zeros_like(z, dtype=bool)
            hit[:, 1:] = (np.sign(zs[:, 1:]) != np.sign(zs[:, :-1])) & (r[:, 1:] < h['R'])
        any_ = hit.any(axis=1)
        k = np.argmax(hit, axis=1)
        sk = np.where(any_, s[k], np.inf)
        upd = sk < best
        best[upd] = sk[upd]; name[upd] = h['name']
    return name


def reflect(table, scale, E_p, hardware):
    """Stopping surface and reflected rays (axisymmetric), with momentum/energy ledgers by solid angle."""
    th = table.th; E_sr = E_p / (4 * math.pi)
    R = table.stopping(scale, E_sr)
    stopped = np.isfinite(R)
    dR = np.gradient(R, th)
    rh = np.stack([np.sin(th), np.zeros_like(th), np.cos(th)], axis=1)
    thh = np.stack([np.cos(th), np.zeros_like(th), -np.sin(th)], axis=1)
    ok = stopped & np.isfinite(dR)
    n = rh - np.where(ok, dR / np.where(ok, R, 1.0), 0.0)[:, None] * thh
    n /= np.linalg.norm(n, axis=1)[:, None]
    out = np.where(ok[:, None], rh - 2 * np.sum(rh * n, axis=1)[:, None] * n, rh)
    P0 = np.where(ok[:, None], np.nan_to_num(R)[:, None] * rh, 0.0) + 1e-3 * out
    hit = ray_hits_many(P0, out, hardware)
    # the inbound path from the burn point to the stopping point must not cross hardware either
    inbound = ray_hits_many(np.zeros_like(rh) + 1e-3 * rh, rh, hardware, s_max=1.0)
    for j in range(len(th)):
        if ok[j]:
            hj = ray_hits_many(1e-3 * rh[j:j + 1], rh[j:j + 1], hardware, s_max=float(R[j]), n=600)[0]
            if hj is not None:
                hit[j] = hj
    # outgoing rays that head forward and miss the shield and loops fly along the ship (hull, radiator wings)
    for j in range(len(th)):
        if hit[j] is None and -out[j, 2] < 0:
            hit[j] = 'ship_forward'
    del inbound
    w = np.sin(th) * np.gradient(th); w /= w.sum()
    ax = -out[:, 2]
    clean = np.array([h is None for h in hit])
    by = {}
    for h, ww in zip(hit, w):
        if h is not None:
            by[h] = by.get(h, 0.0) + float(ww)
    unst_fwd = float(np.sum(w * (~ok) * (th < math.pi / 2)))
    eta_mom = float(np.sum(w * ax * clean))
    return {'R': R, 'dir': out, 'hit': hit, 'w': w, 'eta_mom': eta_mom, 'eta_T': eta_mom ** 2,
            'strike_share': float(np.sum(w * ~clean)), 'strike_by': by, 'unstopped_forward_share': unst_fwd,
            'forward_going_share': float(np.sum(w * (ax < 0))), 'min_R_fwd': float(np.nanmin(np.where(th < math.pi / 2, R, np.nan)))
            if np.any(ok & (th < math.pi / 2)) else None}
