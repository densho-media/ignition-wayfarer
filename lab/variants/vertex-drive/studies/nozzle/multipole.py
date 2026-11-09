"""Axisymmetric multipole expansion of coaxial loops about the burn point, and the exact work done by a perfectly diamagnetic
(flux-excluding) sphere expanding in that field with fixed coil currents.

External scalar potential (B = -grad Phi): Phi = sum_l a_l rho^l P_l(cos th), valid for rho < distance to the nearest loop.
A loop of current I at distance d and polar angle alpha gives a_l = -mu0 I sin^2(alpha) P'_l(cos alpha) / (2 l d^l).
A flux-excluding sphere of radius b adds c_l rho^-(l+1) P_l with c_l = l/(l+1) a_l b^(2l+1); its surface field is tangential,
B_th(b, th) = -(1/b) sum a_l b^l (2l+1)/(l+1) dP_l/dth, and the work to expand it from 0 to b is
W(b) = (2 pi / mu0) sum_l a_l^2 l b^(2l+1) / (l+1)   (uniform field: 3/2 x B^2/2mu0 x volume).
"""
import math

import numpy as np

from fields import MU0


def legendre_all(lmax, x):
    """P_0..P_lmax and P'_0..P'_lmax at x (arrays, shape (lmax+1, ...))."""
    x = np.asarray(x, float)
    P = [np.ones_like(x), x.copy()]
    for l in range(1, lmax):
        P.append(((2 * l + 1) * x * P[l] - l * P[l - 1]) / (l + 1))
    P = np.array(P[:lmax + 1])
    dP = np.zeros_like(P)
    for l in range(1, lmax + 1):            # P'_l = l (x P_l - P_{l-1}) / (x^2 - 1), or recurrence P'_{l} = P'_{l-2} + (2l-1) P_{l-1}
        dP[l] = (dP[l - 2] if l >= 2 else 0.0) + (2 * l - 1) * P[l - 1]
    return P, dP


class Expansion:
    """Scaled coefficients alpha_l = a_l d0^l (d0 = distance of the nearest loop), so high orders neither overflow nor underflow."""

    def __init__(self, loops, lmax=120):
        self.d0 = min(L['d'] for L in loops); self.lmax = lmax
        al = np.zeros(lmax + 1)
        for L in loops:
            ang = math.radians(L['alpha_deg']); s2 = math.sin(ang) ** 2
            _, dP = legendre_all(lmax, np.array(math.cos(ang)))
            q = self.d0 / L['d']
            for l in range(1, lmax + 1):
                al[l] += -MU0 * L['I'] * s2 * float(dP[l]) / (2 * l) * q ** l     # a_l d0^l
        self.alpha = al                                   # a_l d0^l, in T m (scalar potential units)

    def _A(self, rho, shift):
        """a_l rho^(l+shift) as (lmax+1, n)."""
        l = np.arange(self.lmax + 1)[:, None]
        x = np.atleast_1d(np.asarray(rho, float))[None, :] / self.d0
        return self.alpha[:, None] * x ** l * np.atleast_1d(np.asarray(rho, float))[None, :] ** shift

    @property
    def B0(self):
        return -self.alpha[1] / self.d0

    def field_inside(self, rho, th):
        """Vacuum (B_rho, B_th) from the expansion (checked against fields.loop_field)."""
        P, dP = legendre_all(self.lmax, np.cos(th))
        l = np.arange(self.lmax + 1)[:, None]
        A = self._A(rho, -1.0)
        return -np.sum(l * A * P, axis=0), np.sum(A * dP * np.sin(th), axis=0)

    def surface_field(self, b, th):
        """Tangential surface field on a flux-excluding sphere of radius b (fixed coil currents)."""
        th = np.atleast_1d(th)
        P, dP = legendre_all(self.lmax, np.cos(th))
        l = np.arange(self.lmax + 1)[:, None]
        A = self._A(np.full(th.shape, b), -1.0)
        return np.sum(A * (2 * l + 1) / (l + 1) * dP * np.sin(th), axis=0)

    def work(self, b):
        """Work to expand the sphere from 0 to b (J)."""
        l = np.arange(self.lmax + 1)
        A = self._A(b, 0.0)[:, 0]
        return float(2 * math.pi / MU0 * np.sum(A ** 2 * l * b / (l + 1)))
