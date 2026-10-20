"""FWD-V2 owner answers 2026-10-13 (Eye 45 FD-A01..A04, S&E 50 AG-A01..A04): geometric baselines follow the placement radius
(r16 32 / 22.627 m, r24 48 / 33.941 m) while B_array stays 8 m; the outer port is radius 2.25 m (diameter 4.50 m); the reversible r16 / r24
alternate truss deletes no member without replacement, keeps the 12-spoke pattern on its azimuths and leaves r4 untouched."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import eye_placement as ep
import eye_truss_study as ets
import forward_shield as fsh


class EyeTrussStudyTests(unittest.TestCase):
    def setUp(self):
        self.s,*_=load()

    def test_baselines_follow_radius(self):
        for r,opp,adj in ((16.0,32.0,22.627),(24.0,48.0,33.941)):              # FD-A03, AG-A03
            b=fsh.eye_baselines(ep.variant(self.s,r))
            self.assertAlmostEqual(b['geometric_opposite_m']['value'],opp,places=3)
            self.assertAlmostEqual(b['geometric_adjacent_m']['value'],adj,places=3)
            self.assertEqual(b['b_array']['value'],8.0)
            self.assertFalse(b['coherent']['known'])

    def test_outer_port_radius(self):
        port=self.s['forward_defense']['eye_wells']['outer_port']                 # FD-A04, AG-A04
        self.assertEqual((port['radius_m'],port['diameter_m']),(2.25,4.5))
        self.assertGreaterEqual(fsh.eye_port_radius(self.s,fsh.disruptor_layers(self.s)[0]),port['radius_m'])

    def test_alternate_truss_rules(self):
        for r in (16.0,24.0):                                                     # FD-A01, AG-A01
            sc=ets.screen(self.s,r,access=False); clr=sc['clearances']['shared_clearance_m']
            self.assertTrue(sc['continuity']['connected'] and sc['continuity']['spoke_pattern_unrotated'])
            self.assertEqual(sc['continuity']['members_deleted_without_replacement'],[])
            for k in ('well_and_stack_m','posts_outside_port_m','raceway_to_structure_m'):
                self.assertGreaterEqual(sc['clearances'][k],clr-1e-9,k)
        self.assertFalse(ets.screen(self.s,4.0)['alternate'])                     # r4 stays the production truss (FD-A06)


if __name__=='__main__':
    unittest.main()
