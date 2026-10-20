"""HAB-002 cabin atmosphere and ECLSS data (drive_capture_2026-10-03): values, statuses, OPEN nodes, provenance, mutations."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import cabin_atmosphere as ca


class CabinAtmosphereTests(unittest.TestCase):
    def setUp(self):
        self.s,self.sources,*_=load()
        self.a=self.s['habitat']['atmosphere']

    def test_values_and_statuses(self):
        a=self.a;c=a['control']
        self.assertEqual((a['cabin_pressure_kpa'],a['o2_fraction'],a['n2_balance_fraction'],a['canon_status']),(80.0,0.25,0.75,'BASELINE'))
        self.assertEqual((c['co2_target_fraction'],c['co2_max_fraction'],c['rh_min'],c['rh_max'],c['canon_status']),(0.003,0.005,0.4,0.5,'WORKING'))
        self.assertEqual((a['o2_partial']['value'],a['o2_partial']['canon_status']),(20.0,'DERIVED'))
        self.assertEqual(ca.o2_partial_kpa(80.0,0.25),20.0)
        self.assertEqual(a['fire_rule']['canon_status'],'BASELINE')
        self.assertEqual((a['eva_interface']['canon_status'],self.s['habitat']['eclss']['canon_status']),('WORKING','WORKING'))
        self.assertEqual(ca.check(self.s),[])


if __name__=='__main__':
    unittest.main()
