"""Route import (NAV-001): import fidelity of the sheet-computed First Ignition route only, no kinematics (26_BLENDER_CONTRACT C-009/C-010)."""
from pathlib import Path
import copy
import json
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import route_import as ri


class RouteImportTests(unittest.TestCase):
    # The committed import (data/simulations/wf_route_v1.json) is the production route; Drive captures are maintainer-local and not published.
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads(ri.output(ROOT).read_text())
    def test_one_row_per_frame_in_time_order(self):
        rows=self.data['frames'];self.assertEqual(len(rows),900)
        self.assertEqual([r[0] for r in rows],[float(n) for n in range(1,901)])
        self.assertTrue(all(b[1]>a[1] for a,b in zip(rows,rows[1:])))
    def test_end_row_matches_the_owner_check_references(self):
        # 22_ROUTE_MODEL!B26:B28 against 23!G901, B901, D901 within the 25_ROUTE_VALIDATION tolerances (E3, E5, E6).
        m=self.data['model'];end=dict(zip(self.data['columns'],self.data['frames'][-1]))
        self.assertAlmostEqual(end['vx_mps'],m['owner_expected_velocity']['value'],delta=0.02)
        self.assertAlmostEqual(end['mission_t_s'],m['owner_expected_time']['value'],delta=0.01)
        self.assertAlmostEqual(end['local_x_m'],m['owner_expected_distance']['value'],delta=1.0)
        self.assertEqual(end['phase'],'TARGET_SPEED')
    def test_a_failed_gate_row_refuses_the_import(self):
        params,header,rows,val=self.data['model'],self.data['columns'],self.data['frames'],self.data['validation']
        self.assertEqual(ri.failures(params,header,rows,val),[])
        bad=copy.deepcopy(val);next(v for v in bad if v['check_id']=='TARGET_TIME')['result']='FAIL'
        self.assertTrue(any('TARGET_TIME' in f for f in ri.failures(params,header,rows,bad)))
        self.assertTrue(ri.failures(params,header,rows[:-1],val))
    @unittest.skipUnless((ROOT/ri.tomllib.loads((ROOT/'data/source_map.toml').read_text())['sources']['route_frames']['capture']).exists(),
                         'Drive capture not present (maintainer-local)')
    def test_the_written_import_is_current(self):
        self.assertEqual(ri.run(ROOT,check=True)['result'],'CURRENT')


if __name__=='__main__':unittest.main()
