"""Feasibility gate checks (lab tests, run by hand: python3 lab/variants/vertex-drive/studies/gate/test_gate.py).

They check physics bookkeeping and the methods against known answers, not the engineering verdicts: a failed or non-converging
configuration is a valid result and stays recorded as such.
"""
import math
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gate_common as G   # noqa: E402
import target as TG       # noqa: E402

ROOT = HERE.parents[4]


class Axis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.A = G.read('axis_base.json'); cls.C = G.read('concepts.json')

    def test_centre_fluence_is_free_expansion(self):
        v = self.A['v4']
        F = v['E_plasma_J'] / (4 * math.pi) / (v['shield_z_m'] * 100) ** 2
        self.assertAlmostEqual(self.A['baseline']['centre_fluence_J_cm2'] / F, 1.0, delta=1e-9)
        for r in self.C['E']['rows']:                      # narrowing the channel never lowers the centre fluence
            self.assertAlmostEqual(r['centre_fluence_J_cm2'] / F, 1.0, delta=1e-9)

    def test_leak_falls_with_closing_field_as_one_over_energy(self):
        cs = self.A['current_scale']
        xs = sorted(cs, key=float)
        sh = [cs[x]['leak_share_of_plasma'] for x in xs]
        self.assertTrue(all(a > b for a, b in zip(sh, sh[1:])))
        k = [cs[x]['leak_share_of_plasma'] * float(x) ** 2 for x in xs]
        self.assertLess(max(k) / min(k), 1.3)               # share ~ 1 / I^2 (the zero stays; only its neighbourhood shrinks)

    def test_3d_method_reproduces_axisymmetric_leak(self):
        self.assertAlmostEqual(self.C['base_3d']['shield_share'] / self.A['baseline']['leak_share_of_plasma'], 1.0, delta=0.1)

    def test_axisymmetric_closure_has_no_side_thrust(self):
        self.assertLess(abs(self.C['base_momentum']['side_over_axial']), 1e-9)
        self.assertLess(abs(self.C['A1']['rows'][0]['momentum']['side_over_axial']), 1e-9)

    def test_tilted_closure_still_has_a_field_zero(self):
        # Morse/Poincare-Hopf: B_t on a closed surface is a surface gradient and vanishes somewhere; tilting only moves the zero
        for r in self.C['A1']['rows'][1:]:
            self.assertGreater(r['null']['polar_deg'], 0.5 * r['tilt_deg'])
            self.assertLess(r['null']['Bt_T'], 0.05)

    def test_aligned_tilt_cancels_side_thrust(self):
        for r in self.C['A1_aligned'].values():
            self.assertLess(r['momentum']['side_over_axial'], 1e-3)


class Coupled(unittest.TestCase):
    def test_no_extras_reproduces_v4(self):
        import coupled as CP
        import spine as SP
        ov = G.v4_overrides(); R4 = G.solve_full(ov)
        m0 = CP.MAX_IT; CP.MAX_IT = 1
        try:
            r = CP.run('zero', ov, R4, SP.t05(), None, ())
        finally:
            CP.MAX_IT = m0
        self.assertAlmostEqual(r['departure_trajectory_t'][-1], 42915.783853018824, delta=1e-3)

    def test_statuses_are_honest(self):
        cp = G.read('coupled.json')
        for c in cp['cases']:
            t = c['departure_trajectory_t']
            if c['status'] == 'CONVERGED':
                self.assertLess(abs(t[-1] - t[-2]), 1.0 + 1e-9, c['label'])
            else:
                self.assertTrue(c['status'].startswith(('NON-CONVERGING', 'FDP-1', 'SINGLE')), c['label'])

    def test_iteration_never_lighter_than_single_pass(self):
        cp = G.read('coupled.json')
        sp = next(c for c in cp['cases'] if c['status'].startswith('SINGLE'))
        it = next(c for c in cp['cases'] if c['label'] == 'coils only, rate free')
        self.assertGreaterEqual(it['summary']['departure_t'], sp['departure_trajectory_t'][-1])


class Target(unittest.TestCase):
    def test_bethe_proton_in_water(self):
        # NIST PSTAR CSDA range of a 100 MeV proton in water: 7.718 g/cm2
        r = TG.bethe_range_g_cm2(0.1, A=1.00728 / 1.0, Z=1, Zt=10 / 18.015 * 1.0, At=1.0, I_eV=75.0)
        self.assertAlmostEqual(r / 7.718, 1.0, delta=0.05)

    def test_fermi_energy_of_dt(self):
        # Lindl: degenerate DT at 1,000 g/cc holds 0.326 MJ/g x 1000^(2/3)
        self.assertAlmostEqual(TG.fermi_specific_MJ_g(1000.0, 0.3975) / (0.3255 * 100.0), 1.0, delta=0.01)

    def test_clean_fuel_has_no_bremsstrahlung_excess(self):
        self.assertAlmostEqual(TG.brems_factor(0.0), 1.0, delta=1e-12)


class Canon(unittest.TestCase):
    def test_only_vertex_entry_changed(self):
        out = subprocess.run(['git', 'diff', '--name-only', 'a1c8246'], capture_output=True, text=True, cwd=ROOT).stdout.split()
        out += subprocess.run(['git', 'ls-files', '--others', '--exclude-standard'], capture_output=True, text=True, cwd=ROOT).stdout.split()
        self.assertEqual([p for p in out if not p.startswith('lab/variants/vertex-drive/')], [])


if __name__ == '__main__':
    unittest.main(verbosity=1)
