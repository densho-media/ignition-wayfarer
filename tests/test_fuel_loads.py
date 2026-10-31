"""F01 torus load path (S&E 15 OWN-F01-TORUS-LOADS-2026-10-31): the bipods carry the torus under thrust; the cells only drain."""
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

    def test_bipod_statics(self):
        # the two legs' axial components return the support load; their radial components cancel
        for sp in fuel_loads.legs(self.s).values():
            ua, uf = sp['Aft']['u'], sp['Fwd']['u']; P = 1.0
            D = ua[0]*uf[1]-ua[1]*uf[0]; Ta, Tf = P*uf[1]/D, -P*ua[1]/D
            self.assertAlmostEqual(Ta*ua[0]+Tf*uf[0], P, places=9)
            self.assertAlmostEqual(Ta*ua[1]+Tf*uf[1], 0.0, places=9)


if __name__ == '__main__':
    unittest.main()
