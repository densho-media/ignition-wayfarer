"""FWD-V2 forward explorer: the owner impact-energy and time-to-range rows reproduced at 0.016 c, and the microdust case never resolves to a
safety claim (Eye 40!F4:F7, 35_SCALING_LIMITS, Tale 28 AVA-005)."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import forward_explorer as fx


class ForwardExplorerTests(unittest.TestCase):
    def setUp(self):
        self.s,*_=load()

    def test_owner_rows_reproduced(self):
        for kg,j in ((1e-9,11506.27554),(1e-6,11506275.54),(1e-3,11506275540),(1.0,11506275539871)):    # Eye 40!F4:F7
            self.assertAlmostEqual(fx.impact_energy_j(self.s,kg)/j,1.0,places=9)
        self.assertAlmostEqual(fx.speed_m_s(self.s),4796679.328,places=3)                                 # Eye 40!D4
        self.assertAlmostEqual(fx.time_to_range_s(self.s,1e6)/60,0.003474625992,places=12)               # 35!A4, 1,000 km
        self.assertAlmostEqual(fx.time_to_range_s(self.s,1e9),208.4775595,places=6)                     # 15!F4, 1,000,000 km

    def test_microdust_stays_unknown(self):
        sc=fx.microdust(self.s)
        self.assertTrue(sc['outcome'].startswith('UNKNOWN') and 'SIMULATION_ONLY' in sc['status'])
        ids=[x['id'] for x in sc['steps']]
        self.assertEqual(ids[-1],'BROW');self.assertIn('DISRUPTOR_LAYER',ids)
        self.assertTrue({'dust flux','survival at 0.016 c'}<=set(sc['unknown']))


if __name__=='__main__':
    unittest.main()
