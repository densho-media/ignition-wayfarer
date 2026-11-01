"""B01 First Ignition operating point (S&E 15 OWN-B01-OPERATING-POINT-2026-10-31): owner case E numbers and the closed hot loop."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import operating_point as op


class OperatingPointTests(unittest.TestCase):
    def setUp(self):
        self.s = load()[0]

    def test_reproduces_owner_case_e(self):
        # S&E 65_BURN_MASSFLOW case E (absorbed fraction 1e-4): 65!B39:B42, B48:B50, 64!B25:B26.
        e = op.burn(self.s, f_hot=1e-4, profile='ramp')
        self.assertAlmostEqual(e['burnout_mass_kg'], 1480000.0, delta=1.0)
        self.assertAlmostEqual(e['reacted_dhe3_kg'], 274057.95, delta=0.5)
        self.assertAlmostEqual(e['lost_feed_kg'], 3425.72, delta=0.05)
        self.assertAlmostEqual(e['peak_fusion_power_W']/261.265e12, 1, delta=1e-4)
        self.assertLess(e['ideal_rejection_W']-e['peak_absorbed_heat_W'], 0)   # the owner's case E overloads the hot loop

    def test_operating_point_closes(self):
        self.assertEqual(op.check(self.s), [])
        b = op.burn(self.s)
        self.assertGreaterEqual(b['hot_margin_W'], 0)
        self.assertLessEqual(b['absorbed_fraction'], b['max_absorbed_fraction'])

    def test_full_return_closes(self):
        # owner choice 2026-10-31: four equal burns at ve from the departure mass end at the protected + operational ship (+ return tankage)
        m = op.mission(self.s); R = m['mass_ratio_per_burn']
        self.assertAlmostEqual(m['departure_mass_kg']/R**4, m['end_mass_kg'], delta=1.0)
        self.assertAlmostEqual(m['departure_mass_kg']-m['end_mass_kg'], m['propellant_kg'], delta=1.0)

    def test_power_limited_burn_keeps_the_drive_power(self):
        # gentler first burn: constant thrust at the B01 drive power cap, so the hot loop and the peak loads are B01's
        b = op.burn(self.s); e = op.burn(self.s, profile='ramp')
        self.assertAlmostEqual(b['peak_thrust_N'], e['peak_thrust_N'], delta=1.0)
        self.assertAlmostEqual(b['duration_s']*b['peak_mass_flow_kg_s'], b['expelled_kg'], delta=1.0)


if __name__ == '__main__':
    unittest.main()
