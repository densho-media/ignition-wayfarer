"""FGR-004 axial datums: origins, the golden position table, coverage, behaviour at another length and error cases."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import layout

# path -> (datum, offset_m, ship-frame X at L = 225 m). Literal values worked out by hand (thrust ring -103.0, blade aft -101.0,
# blade length 50000/9/30.5 = 182.149362477, so front +81.149362477 and RING_A +84.149362477), not recomputed from the spec.
# Kept as lengths or local-frame numbers (plan "Not converted"): they must stay plain numbers, not position tables.


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.s,self.sources,*_=load()

    def test_origins_at_225(self):
        o=layout.origins(self.s)
        for k,v in {'AFT':-112.5,'RADIATOR_AFT':-101.0,'RADIATOR_FRONT':81.149362477,'RING_A':85.049362477,'FWD':112.5}.items():self.assertAlmostEqual(o[k],v,delta=1e-9)
        self.assertEqual(layout.check(self.s),[])
        # Independent relationships: blade length = area / (outer - root); aft edge 1.0 m ahead of the thrust ring's forward face.
        length=50000/9/(37.0-6.5)
        self.assertAlmostEqual(o['RADIATOR_FRONT']-o['RADIATOR_AFT'],length,delta=1e-9)
        ring=layout.at(self.s,self.s['prototype']['thrust_ring_x'])
        self.assertAlmostEqual(o['RADIATOR_AFT']-(ring+self.s['structure']['ring_depth_m']/2),1.0,delta=1e-12)
        # HAB-001: RING_A is derived: 0.25 spar radius + 1.5 owner clearance + 2.15 half sweep (2.0 half frame + 0.15 allowance) ahead of the blade front, so the
        # ring-A aft sweep face is 1.5 m ahead of the spar front (hand numbers, not the formula); ring B is 6.0 m ahead of ring A.
        self.assertAlmostEqual(o['RING_A']-o['RADIATOR_FRONT'],0.25+1.5+2.15,delta=1e-12)
        self.assertAlmostEqual(layout.ring_a_offset_m(self.s),3.9,delta=1e-12)
        self.assertAlmostEqual((o['RING_A']-(2.0+0.15))-(o['RADIATOR_FRONT']+0.25),1.5,delta=1e-12)
        a,b=[layout.at(self.s,r) for r in self.s['prototype']['rotor_centers_x']]
        self.assertAlmostEqual(b-a,6.0,delta=1e-12)


if __name__=='__main__':unittest.main()
