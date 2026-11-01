"""F02 loop architecture (S&E 15 OWN-F02-LOOPS-2026-10-31): energy balance of the heat pump, the loops close."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import heat_rejection as hr


class HeatRejectionTests(unittest.TestCase):
    def setUp(self):
        self.s = load()[0]; self.r = hr.report(self.s)

    def test_loops_close(self):
        self.assertEqual(self.r['failures'], [])

    def test_heat_pump_energy(self):
        # first law: the hot loop receives the lifted heat plus the work; second law: the work is at least the Carnot work
        for b in self.r['burn']:
            self.assertAlmostEqual(b['into_hot_loop_W'], b['warm_load_W']+b['pump_work_W'], delta=1e-6)
            self.assertGreaterEqual(b['pump_work_W'], b['warm_load_W']*(self.r['hot_T_K']/self.r['warm_T_K']-1)-1e-6)


if __name__ == '__main__':
    unittest.main()
