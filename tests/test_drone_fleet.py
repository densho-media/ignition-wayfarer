"""DRONE-001 study fleet (S&E 51/52, 54 DGT-002/005/006/007/008): the owner's counts hold and no proxy dock, unit or rail enters a ring
sweep, a hot blade, the Brow ram side or the drive zone. Placements themselves are PROTOTYPE and not tested."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import drone_fleet as df


class DroneFleetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s,*_=load()
        cls.rows,cls.fails=df.check(cls.s)

    def test_owner_counts(self):
        c=self.rows['DGT-002']['counts']                                       # 51!D4:F12, 54!C3 "11 IVA, 13 EVA; 20+4; 2 arms"
        self.assertEqual((c['iva'],c['eva'],c['active'],c['reserve'],c['total'],c['fixed_arms']),(11,13,20,4,24,2))
        self.assertEqual(len(df.table(self.s)['stations']),16)                 # 52 DS-01..16
        self.assertEqual(self.rows['DGT-002']['units_placed'],24)

    def test_unknowns_stay_open(self):
        q=df.table(self.s)
        for k in ('mass','power','speed','latch_load','arm_reach'):
            self.assertIs(q[k]['known'],False); self.assertNotIn('value',q[k])

    def test_physical_keepouts(self):
        self.assertGreaterEqual(self.rows['DGT-005']['ring_sweep_gap_m'],df.table(self.s)['ring_keepout_margin_m']-1e-9)
        self.assertGreaterEqual(self.rows['DGT-007']['blade_gap_m'],df.table(self.s)['blade_clearance_m']-1e-9)
        self.assertLessEqual(self.rows['DGT-006']['forward_of_truss_aft_m'],0.0)
        self.assertGreaterEqual(self.rows['DGT-008']['aftmost_x_m'],self.rows['DGT-008']['casing_start_x_m'])
        self.assertLessEqual(self.rows['DGT-003']['casing_top_radius_m'],self.s['ship']['body_diameter']['max']/2)   # 14 m BASELINE maximum body
        self.assertEqual(self.fails,[])

    def test_routed_edges_clear_hardware(self):
        import drone_routes                                                   # 54 DGT-009: a ROUTED unit's sweep clears existing hardware
        rows,fails=drone_routes.check(self.s)
        self.assertEqual(fails,[])


if __name__=='__main__':
    unittest.main()
