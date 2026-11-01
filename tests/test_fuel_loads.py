"""Tank-farm loads (TANK-AXIAL): every vessel only drains, the skirts hold 1.5 g full, the forward links absorb cold contraction."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import fuel_loads
import fuel_storage


class FuelLoadTests(unittest.TestCase):
    def setUp(self):
        self.s = load()[0]

    def test_loads_close(self):
        self.assertEqual(fuel_loads.check(self.s), [])
        self.assertEqual(fuel_storage.check(self.s), [])

    def test_skirt_carries_the_design_load(self):
        # the skirt struts' axial components return each vessel's 1.5 g load
        for t in fuel_storage.tanks(self.s):
            st = fuel_loads._struts(self.s, t); W = 1.0
            F = W/sum(abs(c['ux']) for c in st)
            self.assertAlmostEqual(sum(F*abs(c['ux']) for c in st), W, places=9)
            self.assertTrue(all(c['ux'] > 0.3 for c in st))       # struts lean along the thrust axis, not across it


if __name__ == '__main__':
    unittest.main()
