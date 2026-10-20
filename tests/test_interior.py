"""P1-004 rough ring-sector interiors (FGR-003), independent of Blender."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import habitat_interior as hi

THETA=0.2081720987      # rad: arc that holds 72.383 m3 gross in a 3.5 m axial sector between r 25.0 and 28.7 m (owner 434.3 m3 / 6)


class InteriorTests(unittest.TestCase):
    def setUp(self):
        self.s,self.sources,*_=load()
    def test_section_volumes_follow_the_owner_numbers(self):
        sec=hi.section(self.s)
        self.assertAlmostEqual(sec['deck_to_overhead_m3'],0.5*THETA*(28**2-25**2)*3.5,places=4);self.assertAlmostEqual(sec['deck_to_overhead_m3'],57.92389,places=4)
        self.assertGreaterEqual(sec['deck_to_overhead_m3'],40.0)           # holds the owner's 40 m3 usable per sector
        self.assertEqual(sec['usable_m3'],self.s['habitat']['layout']['usable_per_ring_m3']/3);self.assertEqual(sec['usable_m3'],40.0)
        self.assertAlmostEqual(sec['subfloor_m3'],0.5*THETA*(28.7**2-28**2)*3.5,places=4);self.assertAlmostEqual(sec['subfloor_m3'],14.459,places=3)
        self.assertAlmostEqual(sec['subfloor_m3']+sec['deck_to_overhead_m3'],72.383,places=4)


if __name__=='__main__':unittest.main()
