"""Module registry and detail packs (docs/MODULES.md): the registry resolves, the generated contract file is current, and a pack edit
selects only its own detail assets. Tooling checks with their own fixtures; no Blender."""
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'tools')]
from spec import load
import checks
import modules
import production_detail as pd


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.s = load()[0]

    def test_registry_and_packs_resolve(self):
        self.assertEqual(modules.validate(self.s, ROOT, legacy=pd.ASSEMBLIES), [])
        self.assertEqual(modules.order(modules.registry(ROOT))[0], 'WF-CORE')

    def test_contract_file_is_current(self):
        self.assertEqual(json.loads((ROOT/modules.CONTRACTS).read_text()), json.loads(json.dumps(modules.contracts(self.s, ROOT), sort_keys=True)),
                         'regenerate with: python3 tools/workflow.py module contracts --write')

    def test_anchor_frames_follow_the_engineering_formulas(self):
        # A sector anchor is the sector instance's frame: deck radius on the sector angle, rotated about +X by it.
        import habitat_ring
        anc = modules.anchors(self.s)
        for q in habitat_ring.sectors(self.s):
            m = anc[f"{modules.ring_module(modules.registry(ROOT), q['ring'])}.SECTOR.{q['ring']}.{q['index']}"]['matrix']
            self.assertAlmostEqual(m[1][3]**2+m[2][3]**2, q['deck_radius']**2, places=6)
            self.assertAlmostEqual(m[1][1], __import__('math').cos(q['angle']), places=9)

    def test_malformed_packs_are_refused(self):
        bad = {'x': {'pack': {'module': 'WF-RING-A', 'version': 1, 'scope': 'M9', 'enabled': True, 'detail_class': 'SHINY', 'mass_kg': 3.0},
                     'assembly': {'X.1': {'anchor': 'WF-RING-A.SECTOR.1.1', 'envelope_min': [0, 0, 0], 'envelope_max': [1, 1, -1]}}}}
        fails = ' '.join(modules.check_packs(bad))
        for word in ('scope', 'detail_class', 'envelope', 'mass_kg'):
            self.assertIn(word, fails)

    def test_a_contract_change_changes_the_hash(self):
        s2 = load()[0]; s2['habitat_ring']['sector_outer_radius_m'] += 0.0     # same input, same hash
        self.assertEqual(modules.contracts(s2, ROOT)['modules']['WF-RING-A']['hash'], modules.contracts(self.s, ROOT)['modules']['WF-RING-A']['hash'])
        reg = modules.registry(ROOT); reg['interface_version'] += 1
        self.assertNotEqual(modules.contracts(self.s, ROOT, reg)['modules']['WF-RING-A']['hash'],
                            modules.contracts(self.s, ROOT)['modules']['WF-RING-A']['hash'])


class SelectionTests(unittest.TestCase):
    def test_pack_edit_selects_its_detail_target(self):
        # A committed pack edited in place: only its detail assets, its tests and its declared groups (no full build).
        for name, q in modules.packs(ROOT).items():
            plan = checks.plan(ROOT, [q['manifest']])
            hosts = {modules.anchor_host(t['anchor']) for t in q['assembly'].values()}
            self.assertIn(plan['build_target'], {*(modules.target(a) for a in q['assembly']), *hosts}, name)
            self.assertIn('test_production', plan['tests'])
            self.assertTrue(set(q['pack'].get('inspect', [])) <= set(plan['inspect_groups']), name)


if __name__ == '__main__':
    unittest.main()
