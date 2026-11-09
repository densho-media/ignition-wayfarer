"""Analytic checks of the T03 field and particle codes. Run: python3 lab/variants/vertex-drive/studies/nozzle/test_nozzle.py"""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fields as F  # noqa: E402


class Fields(unittest.TestCase):
    def test_on_axis_loop(self):
        R, I = 50.0, 1e7
        for z in (0.0, 13.0, -80.0, 400.0):
            br, bz = F.loop_field(R, 0.0, I, 0.0, z)
            self.assertAlmostEqual(float(bz), F.MU0 * I * R * R / (2 * (R * R + z * z) ** 1.5), delta=1e-9 * abs(float(bz)) + 1e-15)
            self.assertEqual(float(br), 0.0)

    def test_offaxis_matches_biot_savart(self):
        R, I = 40.0, 3e6
        pts = F.arc_polyline(R, 5.0, 0, 2 * math.pi, 3600)
        A, B, cur = F.polyline_segments(pts, I)
        P = np.array([[10.0, 0.0, -3.0], [35.0, 0.0, 9.0], [70.0, 0.0, 20.0], [0.0, 25.0, 0.0]])
        Bs = F.segments_field(A, B, cur, P)
        Be = F.loops_cart([{'R': R, 'z': 5.0, 'I': I}], P)
        np.testing.assert_allclose(Bs, Be, rtol=2e-5, atol=1e-9)

    def test_divergence_free_and_psi(self):
        L = [{'R': 30.0, 'z': 4.0, 'I': 2e6}]
        r, z, h = 12.0, 7.0, 1e-3
        br1, _ = F.loops_field(L, r + h, z); br0, _ = F.loops_field(L, r - h, z)
        _, bz1 = F.loops_field(L, r, z + h); _, bz0 = F.loops_field(L, r, z - h)
        br, bz = F.loops_field(L, r, z)
        div = (br1 - br0) / (2 * h) + br / r + (bz1 - bz0) / (2 * h)
        self.assertLess(abs(float(div)), 1e-8 * abs(float(bz)))
        # B_z = (1/r) dpsi/dr
        p1 = F.loops_psi(L, r + h, z); p0 = F.loops_psi(L, r - h, z)
        self.assertAlmostEqual(float((p1 - p0) / (2 * h) / r), float(bz), delta=1e-6 * abs(float(bz)))

    def test_mutual_far_dipole(self):
        R1, R2, d = 1.0, 2.0, 400.0
        self.assertAlmostEqual(F.mutual(R1, 0, R2, d), F.MU0 * math.pi * R1 ** 2 * R2 ** 2 / (2 * d ** 3), delta=1e-3 * F.mutual(R1, 0, R2, d))

    def test_mutual_equals_flux(self):
        M = F.mutual(30.0, 0.0, 55.0, -20.0)
        flux = 2 * math.pi * float(F.loop_psi(30.0, 0.0, 1.0, 55.0, -20.0))
        self.assertAlmostEqual(M, flux, delta=1e-9 * M)

    def test_energy_quadrature_vs_inductance(self):
        # far-field-limited quadrature approaches L I^2/2 minus the conductor interior and the cut-off tail
        L = [{'R': 10.0, 'z': 0.0, 'I': 1e5, 'a': 0.5}]
        W = F.field_energy_axisym(L, 300.0, -300.0, 300.0, n=1500)
        Wl = 0.5 * F.self_inductance(10.0, 0.5, Y=0.0) * 1e10
        self.assertLess(abs(W / Wl - 1), 0.05)



class Multipole(unittest.TestCase):
    def setUp(self):
        import multipole as M
        self.M = M
        self.loops = [{'alpha_deg': 60.0, 'd': 43.0, 'R': 43 * math.sin(math.radians(60)), 'z': 43 * 0.5, 'I': 2e7},
                      {'alpha_deg': 90.0, 'd': 64.0, 'R': 64.0, 'z': 0.0, 'I': 3e7}]

    def test_expansion_matches_exact(self):
        X = self.M.Expansion(self.loops, 120)
        for rho, th in ((10.0, 0.3), (25.0, 1.9), (30.0, 2.8)):
            Br, Bt = X.field_inside(np.array([rho]), np.array([th]))
            r, z = rho * math.sin(th), rho * math.cos(th)
            br, bz = F.loops_field(self.loops, r, z)
            Brho_e = float(br) * math.sin(th) + float(bz) * math.cos(th); Bth_e = float(br) * math.cos(th) - float(bz) * math.sin(th)
            self.assertAlmostEqual(float(Br[0]), Brho_e, delta=1e-6 * math.hypot(Brho_e, Bth_e))
            self.assertAlmostEqual(float(Bt[0]), Bth_e, delta=1e-6 * math.hypot(Brho_e, Bth_e))

    def test_uniform_sphere_work(self):
        # a single far loop: its field near the centre is uniform to O((b/d)^2)
        X = self.M.Expansion([{'alpha_deg': 90.0, 'd': 1e4, 'R': 1e4, 'z': 0.0, 'I': 1e10}], 20)
        B0 = X.B0; b = 7.0
        self.assertAlmostEqual(B0, F.MU0 * 1e10 / 2e4, delta=1e-9 * B0)
        self.assertAlmostEqual(X.work(b) / (1.5 * B0 ** 2 / (2 * F.MU0) * 4 / 3 * math.pi * b ** 3), 1.0, delta=1e-5)
        self.assertAlmostEqual(abs(float(X.surface_field(b, np.array([math.pi / 2]))[0])) / (1.5 * B0), 1.0, delta=1e-5)

    def test_work_equals_surface_pressure_integral(self):
        X = self.M.Expansion(self.loops, 80)
        b, h = 20.0, 1e-3
        dW = (X.work(b + h) - X.work(b - h)) / (2 * h)
        th = np.linspace(0, math.pi, 4001); Bt = X.surface_field(b, th)
        integ = np.trapezoid(Bt ** 2 / (2 * F.MU0) * 2 * math.pi * b * b * np.sin(th), th)
        self.assertAlmostEqual(dW, float(integ), delta=1e-4 * dW)



class Particles(unittest.TestCase):
    def test_gyration_uniform(self):
        import particles as P
        # far huge loop -> uniform field near the origin: one gyro orbit returns to start, radius m v / q B
        L = [{'R': 1e5, 'z': 0.0, 'I': 1e11}]
        B = F.MU0 * 1e11 / 2e5
        m, q, v = 4.0 * 1.6605e-27, 2 * 1.602e-19, 1e6
        T = 2 * math.pi * m / (q * B)
        X = np.array([[0.0, 0.0, 0.0]]); V = np.array([[v, 0.0, 0.0]])
        X, V, f, w = P.boris(L, q, m, X, V, T / 2000, 2000, lambda X: np.zeros(len(X), int))
        self.assertLess(np.linalg.norm(X[0]), 1e-3 * m * v / (q * B))
        self.assertAlmostEqual(np.linalg.norm(V[0]) / v, 1.0, delta=1e-12)

    def test_mirror_reflection_adiabatic(self):
        import particles as P
        # two coaxial loops: a particle with pitch outside the loss cone is reflected, inside it passes
        L = [{'R': 10.0, 'z': -30.0, 'I': 2e6}, {'R': 10.0, 'z': 30.0, 'I': 2e6}]
        M = P.mirror_axis(L, -29.0, 29.5)
        m, q, v = 1.6726e-27, 1.602e-19, 1e6
        sin_lc = math.sqrt(1 / M['mirror_ratio'])
        for s, expect_pass in ((sin_lc * 0.7, True), (min(0.99, sin_lc * 1.4), False)):
            V = np.array([[v * s, 0.0, v * math.sqrt(1 - s * s)]]); X = np.array([[0.0, 0.0, 0.0]])
            X, V, f, w = P.boris(L, q, m, X, V, 1e-9, 120000, lambda X: (X[:, 2] > 29.0).astype(int) + 2 * (X[:, 2] < -0.5).astype(int))
            self.assertEqual(int(f[0]), 1 if expect_pass else 2)


if __name__ == '__main__':
    unittest.main()
