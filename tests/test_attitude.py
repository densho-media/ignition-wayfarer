"""Attitude control check (S&E 15 OWN-ATT-CHECK-2026-10-31): the drive holds the placed CG offset, a flip conserves impulse."""
from pathlib import Path
import math
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import attitude


class AttitudeTests(unittest.TestCase):
    def setUp(self):
        self.s = load()[0]; self.r = attitude.report(self.s)

    def test_drive_trim_closes(self):
        self.assertEqual(self.r['failures'], [])
        for t in self.r['burn_trim']['states']:
            self.assertLessEqual(t['torque_N_m'], t['drive_authority_N_m'])

    def test_flip_is_bang_bang(self):
        # half the flip accelerates through pi/2: the peak rate times half the time is the half angle, pi/2.
        f = attitude.flip(1e10, 2e4, 100.0, [300.0])
        self.assertAlmostEqual(math.radians(f['peak_rate_deg_s'])*f['flip_min']*60/2, math.pi, delta=1e-9)


if __name__ == '__main__':
    unittest.main()
