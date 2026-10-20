"""FWD-V2 scenario contract (S&E 50 AG-014 F): the schema holds, the 0.016 c warning horizon and the 1 ug/mg/g impact-energy orders
reproduce the Eye owner rows, and the scenario names its source version (Eye 15_ACTIVE_LIDAR, 35_SCALING_LIMITS, 40_BROW_SHIELD)."""
from pathlib import Path
import copy
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import forward_explorer as fx
import forward_scenario as fsc


class ForwardScenarioTests(unittest.TestCase):
    def setUp(self):
        self.s,self.src,*_=load()
        self.sc=fx.microdust(self.s,self.src)['state']

    def test_warning_horizon(self):
        rows={r['range_m']:r for r in fsc.warning_horizon(self.s)}
        for m,ttr,rt in ((1e9,208.4775595,6.671281904),(1e10,2084.775595,66.71281904),(149597870700.0,31187.79899,998.0095677)):  # 15!E4:F6
            self.assertAlmostEqual(rows[m]['time_to_range_s']/ttr,1.0,places=9)
            self.assertAlmostEqual(rows[m]['round_trip_s']/rt,1.0,places=9)
        self.assertAlmostEqual(rows[1e6]['time_to_range_s']/60,0.003474625992,places=12)                                      # 35!F4

    def test_energy_orders(self):
        e={r['label']:r['energy_j'] for r in fsc.energy_orders(self.s)}
        for label,j in (('1 ug',11506.27554),('1 mg',11506275.54),('1 g',11506275540)):                                       # 40!F4:F6
            self.assertAlmostEqual(e[label]/j,1.0,places=9)

    def test_schema_and_source_version(self):
        self.assertEqual(fsc.validate(self.s,self.sc),[])
        self.assertEqual(set(self.sc['source_snapshot']),set(fsc.SOURCES))
        self.assertEqual(self.sc['source_snapshot']['eye_lidar_horizon']['modified_at_utc'],self.src['sources']['eye_lidar_horizon']['modified_at_utc'])
        bad=copy.deepcopy(self.sc)
        bad['frames'][0]['target']['cross_section_m2']=1.0
        bad['frames'][1]['permitted_response']=['FRAGMENT']
        bad['frames'][2]['vehicle_state']['thermal']=fsc.value(1.0,'K','PROTOTYPE')
        bad['outcome']='SURVIVED'
        problems=' | '.join(fsc.validate(self.s,bad))
        for word in ('forbidden','FRAGMENT','vehicle state','UNKNOWN'):
            self.assertIn(word,problems)


if __name__=='__main__':
    unittest.main()
