"""M7 production layer: the physical invariant it must keep (every element outside the route's clearances), independent of Blender."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import modules
import production_detail as pd


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.s = load()[0]

    def test_every_assembly_keeps_the_route_clearances(self):
        # Every detail pack's assemblies (docs/MODULES.md).
        for a in pd.listed(self.s):
            self.assertEqual(pd.check(self.s, a), [], a)

    def test_pack_detail_stays_in_its_envelope(self):
        for a in modules.assemblies(self.s['detail_packs']):
            self.assertEqual(modules.envelope_fails(self.s, a), [], a)


if __name__ == '__main__':
    unittest.main()
