"""P1F optically gated manifold: geometry screen, normalized rig state and action tables, independent of Blender."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import drive_manifold as dm


class DriveManifoldTests(unittest.TestCase):
    def setUp(self):
        self.s,self.sources,*_=load()
        self.acts=dm.actions(self.s)


    def test_shares_normalize_and_couples_follow_the_quadrants(self):
        self.assertAlmostEqual(sum(dm.normalize([.3,.3,.2,.2])),1)
        self.assertEqual([round(x,12) for x in dm.normalize([1,1,0,1])],[round(1/3,12),round(1/3,12),0.0,round(1/3,12)])
        pitch=dm.couple_arm(self.s,[.3,.3,.2,.2]);yaw=dm.couple_arm(self.s,[.3,.2,.3,.2])
        self.assertAlmostEqual(pitch['pitch_arm_m'],.52);self.assertAlmostEqual(pitch['yaw_arm_m'],0)
        self.assertAlmostEqual(yaw['yaw_arm_m'],-.52);self.assertAlmostEqual(yaw['pitch_arm_m'],0)
        ex=dm.couple_arm(self.s,self.s['propulsion']['manifold']['example_maneuver']['shares'])
        self.assertEqual(ex['pitch_arm_m'],0);self.assertAlmostEqual(ex['yaw_arm_m'],.52)    # the owner example is a yaw couple under the owner map
        for shares in [[.25]*4,[.3,.3,.2,.2],[.2,.3,.2,.3]]:
            self.assertEqual(dm.couple_arm(self.s,shares)['roll_arm_m'],0.0)


if __name__=='__main__':
    unittest.main()
