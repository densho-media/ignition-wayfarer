"""Drone body family (data/drone_bodies.toml, S&E 51): one design per owner class, the 24 + 2 inventory unchanged, every stowed body inside
its owner envelope class, the fixed bases at the owner size, and the unknown physics still OPEN. Forms, poses and looks are not tested."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
import drone_bodies as db
import drone_fleet as df


class DroneBodiesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s,cls.d=db.load(Path(__file__).resolve().parents[1])
        cls.rows,cls.fails=db.check(cls.s,cls.d)

    def test_screen_passes(self):
        self.assertEqual(self.fails,[])

    def test_one_design_per_owner_class_and_inventory(self):
        self.assertEqual(set(k for k in self.rows if k!='inventory'),set(df.classes(self.s)))   # 51 DR-IVA-01..DR-FIX-02
        self.assertEqual(self.rows['inventory'],dict(mobile=24,fixed=2,designs=9))           # 51 TOTAL-MOBILE 24; 2 arms outside it

    def test_envelope_class(self):
        for cid,c in df.classes(self.s).items():
            if c['domain']!='FIXED':
                self.assertLessEqual(max(self.rows[cid]['stowed_m']),c['envelope_m'][1]+1e-9,cid)  # 51 col G upper bound
            else:
                self.assertEqual(self.rows[cid]['base_m'],list(c['base_m']),cid)

    def test_unknowns_stay_open(self):
        for k,v in self.d['open'].items():
            self.assertIs(v['known'],False,k); self.assertNotIn('value',v)


if __name__=='__main__':
    unittest.main()
