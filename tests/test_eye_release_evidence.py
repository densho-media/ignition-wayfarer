"""FWD-V2 release evidence (Eye 45 FD-A05/A06): closed eyelids cover the facet at every placement, and the eyelid leaves never cut the skin
over their whole travel (on the cone the frame lies on the local face)."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import eye_placement as ep
import eye_release_evidence as ere


class EyeReleaseEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.s,*_=load()

    def test_closed_eyelids_cover_the_facet(self):
        for r in (4.0,16.0):
            self.assertEqual(ere.fov(self.s,r,'closed',theta_step=10.0,psi_step=90.0)['on_axis_transmission'],0.0)

    def test_eyelids_clear_the_skin(self):
        for r in ep.RADII:
            v=ep.variant(self.s,r); gap=v['forward_shield']['prototype']['eye_shutter_gap_m']
            for u in (0.0,0.5,1.0):
                for lf in ere.leaf_frames(v,{j:u for j in range(1,5)}):
                    self.assertGreaterEqual(ere._leaf_skin_gap(v,lf),gap-1e-6,(r,u,lf['name']))


if __name__=='__main__':
    unittest.main()
