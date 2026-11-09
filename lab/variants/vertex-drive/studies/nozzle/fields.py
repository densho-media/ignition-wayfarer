"""T03 vacuum-field toolkit (standard library + numpy only).

Coaxial circular loops are evaluated exactly with complete elliptic integrals (AGM); arbitrary 3D conductors (sector arcs, gap leads,
helical windings) by straight-segment Biot-Savart. Units SI. Nozzle frame: origin at the burn point, +z = ship +X (bow), exhaust toward -z.
Every function here is checked against an analytic case in test_nozzle.py.
"""
import math

import numpy as np

MU0 = 4e-7 * math.pi


def ellipke(m):
    """Complete elliptic integrals K(m), E(m) (parameter m = k^2, 0 <= m < 1) by the arithmetic-geometric mean."""
    m = np.asarray(m, dtype=float)
    a = np.ones_like(m); b = np.sqrt(1.0 - m); c = np.sqrt(m)
    s = 0.5 * c * c; p = 1.0
    for _ in range(40):
        an = 0.5 * (a + b); bn = np.sqrt(a * b); cn = 0.5 * (a - b)
        p *= 2.0; s = s + p * 0.5 * cn * cn
        a, b = an, bn
        if np.all(np.abs(cn) < 1e-16):
            break
    K = math.pi / (2.0 * a)
    E = K * (1.0 - s)
    return K, E


def loop_field(R, z0, I, r, z):
    """(B_r, B_z) of a coaxial loop (radius R, plane z0, current I in +phi) at cylindrical points (r, z); exact."""
    r = np.asarray(r, dtype=float); z = np.asarray(z, dtype=float)
    zeta = z - z0
    rr = np.maximum(r, 1e-12)
    D = (R + rr) ** 2 + zeta ** 2
    m = np.clip(4 * R * rr / D, 0.0, 1 - 1e-15)
    K, E = ellipke(m)
    G = np.maximum((R - rr) ** 2 + zeta ** 2, 1e-12)
    c = MU0 * I / (2 * math.pi * np.sqrt(D))
    Bz = c * (K + (R * R - rr * rr - zeta ** 2) / G * E)
    Br = c * zeta / rr * (-K + (R * R + rr * rr + zeta ** 2) / G * E)
    Br = np.where(r < 1e-9, 0.0, Br)
    return Br, Bz


def loop_psi(R, z0, I, r, z):
    """Poloidal flux function psi = r A_phi (Wb/rad) of a coaxial loop; the flux through the disc of radius r is 2 pi psi."""
    r = np.asarray(r, dtype=float); z = np.asarray(z, dtype=float)
    zeta = z - z0
    rr = np.maximum(r, 1e-12)
    m = np.clip(4 * R * rr / ((R + rr) ** 2 + zeta ** 2), 1e-15, 1 - 1e-15)
    k = np.sqrt(m)
    K, E = ellipke(m)
    A = MU0 * I / (math.pi * k) * np.sqrt(R / rr) * ((1 - m / 2) * K - E)
    return np.where(r < 1e-9, 0.0, rr * A)


def mutual(R1, z1, R2, z2):
    """Mutual inductance of two coaxial loops (H), Maxwell's formula."""
    m = 4 * R1 * R2 / ((R1 + R2) ** 2 + (z1 - z2) ** 2)
    k = math.sqrt(m)
    K, E = ellipke(m)
    return MU0 * math.sqrt(R1 * R2) * ((2 / k - k) * float(K) - 2 / k * float(E))


def self_inductance(R, a, Y=0.5):
    """Self inductance of a thin ring (major R, minor a). Y = 0.5 uniform current, 0 surface current."""
    return MU0 * R * (math.log(8 * R / a) - 2 + Y / 2)


def hoop_tension(R, a, I, Y=0.5):
    """Self-force hoop tension (N) of a ring: T = (I^2/2) dL/dR / (2 pi)."""
    return I * I / 2 * MU0 * (math.log(8 * R / a) - 1 + Y / 2) / (2 * math.pi)


def inductance_matrix(loops, Y=0.5):
    n = len(loops); M = np.zeros((n, n))
    for i, a in enumerate(loops):
        for j, b in enumerate(loops):
            M[i, j] = self_inductance(a['R'], a['a'], Y) if i == j else mutual(a['R'], a['z'], b['R'], b['z'])
    return M


def loops_field(loops, r, z):
    Br = 0.0; Bz = 0.0
    for L in loops:
        br, bz = loop_field(L['R'], L['z'], L['I'], r, z)
        Br = Br + br; Bz = Bz + bz
    return Br, Bz


def loops_psi(loops, r, z):
    return sum(loop_psi(L['R'], L['z'], L['I'], r, z) for L in loops)


def loops_cart(loops, P):
    """Cartesian B of coaxial loops at points P (N,3)."""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    r = np.hypot(x, y)
    Br, Bz = loops_field(loops, r, z)
    c = np.where(r > 1e-12, x / np.maximum(r, 1e-12), 0.0); s = np.where(r > 1e-12, y / np.maximum(r, 1e-12), 0.0)
    return np.stack([Br * c, Br * s, Bz], axis=1)


def segments_field(A, B, I, P, core=1e-3):
    """Biot-Savart of straight segments A->B (M,3) with currents I (M,) at points P (N,3). Returns (N,3).
    Uses the exact finite-segment formula; `core` (m) regularises points on a conductor."""
    P = np.asarray(P, float)
    out = np.zeros_like(P)
    for k0 in range(0, len(A), 512):
        a = P[:, None, :] - A[None, k0:k0 + 512, :]
        b = P[:, None, :] - B[None, k0:k0 + 512, :]
        na = np.linalg.norm(a, axis=2); nb = np.linalg.norm(b, axis=2)
        cr = np.cross(a, b)
        den = na * nb * (na * nb + np.einsum('ijk,ijk->ij', a, b)) + core ** 2 * (na + nb) ** 2
        f = MU0 * I[None, k0:k0 + 512] / (4 * math.pi) * (na + nb) / den
        out += np.einsum('ij,ijk->ik', f, cr)
    return out


def arc_polyline(R, z, a0, a1, n):
    """Points of an arc (radians a0 -> a1) at radius R in plane z."""
    t = np.linspace(a0, a1, n + 1)
    return np.stack([R * np.cos(t), R * np.sin(t), np.full_like(t, z)], axis=1)


def polyline_segments(pts, I):
    return pts[:-1], pts[1:], np.full(len(pts) - 1, float(I))


def field_energy_axisym(loops, rmax, zmin, zmax, n=600):
    """Vacuum magnetic energy inside a cylinder (r < rmax, zmin < z < zmax) by midpoint quadrature (J). Excludes conductor cores."""
    r = (np.arange(n) + 0.5) * rmax / n
    z = zmin + (np.arange(n) + 0.5) * (zmax - zmin) / n
    Rg, Zg = np.meshgrid(r, z)
    Br, Bz = loops_field(loops, Rg, Zg)
    u = (Br ** 2 + Bz ** 2) / (2 * MU0)
    near = np.zeros_like(u, dtype=bool)
    for L in loops:
        near |= np.hypot(Rg - L['R'], Zg - L['z']) < L['a']
    u = np.where(near, 0.0, u)
    return float(np.sum(u * 2 * math.pi * Rg) * (rmax / n) * ((zmax - zmin) / n))
