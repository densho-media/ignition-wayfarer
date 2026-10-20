"""M7 production layer: the physical invariant it must keep (every element outside the route's clearances), independent of Blender."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import production_detail as pd


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.s = load()[0]

    def test_every_assembly_keeps_the_route_clearances(self):
        for a in pd.ASSEMBLIES:
            self.assertEqual(pd.check(self.s, a), [], a)


if __name__ == '__main__':
    unittest.main()
