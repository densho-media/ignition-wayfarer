"""Gate 2 checks (lab tests, run by hand: python3 lab/variants/vertex-drive/studies/gate2/test_gate2.py).

Physics bookkeeping and methods against known answers; not the verdicts (failed and non-converging variants are valid results).
"""
import math
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import g2                  # noqa: E402
import target2 as T2       # noqa: E402

G = g2.G
ROOT = HERE.parents[4]


class Target(unittest.TestCase):
    def test_bosch_hale_dt_table(self):
        self.assertAlmostEqual(T2.sigv('DT', 10.0) / 1.136e-22, 1.0, delta=0.005)
        self.assertAlmostEqual(T2.sigv('DT', 20.0) / 4.330e-22, 1.0, delta=0.005)

    def test_fermi_gas_matches_lindl_scaling(self):
        pa = T2.per_amu('DHe3')
        fp = T2.fermi_first_principles(2000.0, pa['electrons'])
        self.assertAlmostEqual(T2.lindl(2000.0, pa['electrons']) / fp['kinetic_MJ_g'], 1.0, delta=0.02)
        self.assertLess(fp['x_rel'], 0.2)                      # non-relativistic regime: the Lindl form applies

    def test_dt_ideal_ignition_temperature(self):
        self.assertAlmostEqual(T2.ideal_ignition_T('DT'), 4.3, delta=0.3)      # textbook 4.3 keV (Atzeni & Meyer-ter-Vehn)


class Shadow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import coupled2 as C2
        cls.C2 = C2
        cls.R = G.solve_full(G.v4_overrides())

    def test_cones_reproduce_fdp1(self):
        cn = self.C2.cones(self.R, 34.5, 0.0, 0.0)
        self.assertAlmostEqual(cn['theta_hw_deg'], self.R['shield']['hardware_half_angle_deg'], delta=1e-6)
        self.assertAlmostEqual(math.radians(cn['rim_deg']), math.atan2(self.R['shield']['radius_hw_aft_m'], self.R['shield']['distance_from_burn_m']), delta=1e-9)

    def test_shield_formula_reproduces_fdp1_mass(self):
        sh = self.R['shield']
        e = self.C2.shield_eval(self.R, sh['distance_from_burn_m'], sh['hardware_half_angle_deg'], sh['crew_half_angle_deg'])
        self.assertAlmostEqual(e['total_kg'] / sh['mass_kg']['total'], 1.0, delta=1e-6)


class Nozzle(unittest.TestCase):
    def test_v4_eta_is_one_degree_ledger(self):
        g = g2.read('g1.json')
        r = next(x for x in g['resolution'] if x['n_th'] == 181 and x['n_rho'] == 1400)
        self.assertAlmostEqual(r['eta_T'], g['v4_calculator_eta_T'], delta=1e-3)

    def test_ledger_converges_in_resolution(self):
        g = g2.read('g1.json')
        e = {x['n_th']: x['eta_T'] for x in g['resolution'] if x['n_rho'] == 1400}
        self.assertLess(abs(e[2881] - e[1441]), 0.005)


class Matrix(unittest.TestCase):
    def test_statuses_are_honest(self):
        for r in g2.read('matrix.json')['rows']:
            t = r['departure_trajectory_t']
            if r['status'] == 'CONVERGED':
                self.assertLess(abs(t[-1] - t[-2]), 1.0 + 1e-9, r['name'])
            else:
                self.assertTrue(r['status'].startswith(('NON-CONVERGING', 'FDP-1')), r['name'])


class Canon(unittest.TestCase):
    def test_only_vertex_entry_changed(self):
        out = subprocess.run(['git', 'diff', '--name-only', 'a1c8246'], capture_output=True, text=True, cwd=ROOT).stdout.split()
        out += subprocess.run(['git', 'ls-files', '--others', '--exclude-standard'], capture_output=True, text=True, cwd=ROOT).stdout.split()
        self.assertEqual([p for p in out if not p.startswith('lab/variants/vertex-drive/')], [])


if __name__ == '__main__':
    unittest.main(verbosity=1)
