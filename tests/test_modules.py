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
        self.assertEqual(modules.validate(self.s, ROOT), [])
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

    def test_rotor_and_drum_anchors_follow_the_rotor_formulas(self):
        # Rotor_j and the despun Drum_j sit at the ring centre at the index angle (components/revision.py, components/crew.py).
        import crew_transfer
        import rotor_interface
        anc = modules.anchors(self.s); reg = modules.registry(ROOT)
        for r in rotor_interface.rotors(self.s):
            mid = modules.ring_module(reg, r['index'])
            for kind in ('ROTOR', 'DRUM'):
                q = anc.get(f"{mid}.{kind}.{r['index']}")
                if kind == 'DRUM' and not crew_transfer.vestibule(self.s, r['index'])['human']:
                    self.assertIsNone(q); continue
                self.assertEqual(modules.anchor_host(f"{mid}.{kind}.{r['index']}"), f"HABITAT_{'AB'[r['index']-1]}")
                self.assertEqual(q['host'], f"HABITAT_{'AB'[r['index']-1]}")
                self.assertIn(q['host'], modules.registry(ROOT)['module'][mid]['targets'])     # each ring module owns its ring's asset
                self.assertAlmostEqual(q['matrix'][0][3], r['x'], places=9)
                self.assertAlmostEqual(q['matrix'][1][1], __import__('math').cos(r['phase']), places=9)

    def test_a_contract_change_changes_the_hash(self):
        s2 = load()[0]; s2['habitat_ring']['sector_outer_radius_m'] += 0.0     # same input, same hash
        self.assertEqual(modules.contracts(s2, ROOT)['modules']['WF-RING-A']['hash'], modules.contracts(self.s, ROOT)['modules']['WF-RING-A']['hash'])
        reg = modules.registry(ROOT); reg['interface_version'] += 1
        self.assertNotEqual(modules.contracts(self.s, ROOT, reg)['modules']['WF-RING-A']['hash'],
                            modules.contracts(self.s, ROOT)['modules']['WF-RING-A']['hash'])
        self.assertNotEqual(modules.pack_contract(self.s, reg, modules.packs(ROOT), 'm7_ra1'),
                            modules.pack_contract(self.s, modules.registry(ROOT), modules.packs(ROOT), 'm7_ra1'))

    def test_a_new_pack_leaves_the_other_packs_contracts(self):
        # Parallel sessions: a pack added to the same module changes no other pack's contract and not the module's contract file.
        reg = modules.registry(ROOT); packs_ = modules.packs(ROOT)
        before = {n: modules.pack_contract(self.s, reg, packs_, n) for n in packs_}
        more = dict(packs_, probe={'pack': dict(packs_['ra2_equip']['pack']), 'assembly': {'PROBE.X': dict(
            anchor='WF-RING-A.SECTOR.1.3', envelope_min=[-1.0, -1.0, -1.0], envelope_max=[1.0, 1.0, 1.0])}})
        self.assertEqual({n: modules.pack_contract(self.s, reg, more, n) for n in packs_}, before)
        self.assertEqual(modules.check_packs(more), [])

    def test_incompatible_packs_fail_with_a_remedy(self):
        p = {'pack': {'module': 'WF-RING-A', 'version': 1, 'scope': 'M7', 'enabled': True, 'detail_class': 'PRODUCTION'}}
        two = {'a': dict(p, assembly={'A.1': dict(anchor='WF-RING-A.SECTOR.1.3', envelope_min=[0, 0, 0], envelope_max=[2, 2, 2])},
                         materials={'k': [0, 0, 0, 0, 0]}),
               'b': dict(p, assembly={'B.1': dict(anchor='WF-RING-A.SECTOR.1.3', envelope_min=[1, 1, 1], envelope_max=[3, 3, 3])},
                         materials={'k': [0, 0, 0, 0, 0]})}
        fails = ' | '.join(modules.check_packs(two))
        self.assertIn('overlapping space on WF-RING-A.SECTOR.1.3', fails)
        self.assertIn('material k is already defined by pack a', fails)

    def test_authored_meshes_are_checked_against_their_manifest(self):
        # Committed glTF detail (docs/MODULES.md): structure, then the file against its checksum, its anchor frame and the size cap.
        import hashlib
        import tempfile
        reg = modules.registry(ROOT); anchor = 'WF-RING-A.SECTOR.1.3'
        now = modules.anchor_hash(reg, modules.anchors(self.s, reg)[anchor])
        bad = dict(id='lower', file='../x.glb', sha256='XYZ', authored_against=now, license='CC0-1.0', author='a', provenance='p')
        fails = ' | '.join(modules.authored_entry_fails('p', 'P.1', bad))
        for word in ('A-Z', '.glb path inside', '64 lowercase hex'):
            self.assertIn(word, fails)
        self.assertIn('lacks license', ' '.join(modules.authored_entry_fails('p', 'P.1', dict(bad, license=''))))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'data/detail/p').mkdir(parents=True); f = root/'data/detail/p/a.glb'; f.write_bytes(b'glTF test')
            sha = hashlib.sha256(b'glTF test').hexdigest()
            entry = dict(id='A', file='a.glb', sha256=sha, authored_against=now, license='CC0-1.0', author='a', provenance='p')
            pack = {'pack': {'module': 'WF-RING-A', 'version': 1, 'scope': 'M7', 'enabled': True, 'detail_class': 'PRODUCTION'},
                    'assembly': {'P.1': dict(anchor=anchor, envelope_min=[-1, -1, -1], envelope_max=[1, 1, 1], authored=[entry])}}
            fails = lambda e: ' | '.join(modules.authored_fails(self.s, root, reg, {'p': dict(pack, assembly={'P.1': dict(pack['assembly']['P.1'], authored=[e])})}))
            self.assertEqual(fails(entry), '')
            self.assertIn('WF_DETAIL_STALE', fails(dict(entry, sha256='0'*64)))
            self.assertIn('WF_DETAIL_REVIEW', fails(dict(entry, authored_against='0'*16)))
            self.assertIn('WF_DETAIL_MISSING', fails(dict(entry, file='b.glb')))
            before = modules.inputs_hash(root, 'p'); f.write_bytes(b'glTF test, edited')
            self.assertNotEqual(modules.inputs_hash(root, 'p'), before)        # an edited mesh stales the pack's publication
            f.write_bytes(b'0'*(modules.AUTHORED_MAX_BYTES+1))
            self.assertIn('byte cap', fails(dict(entry, sha256=hashlib.sha256(f.read_bytes()).hexdigest())))


class SelectionTests(unittest.TestCase):
    def test_pack_edit_selects_its_detail_target(self):
        # A committed pack edited in place: only its detail assets, its tests and its declared groups (no full build).
        for name, q in modules.packs(ROOT).items():
            plan = checks.plan(ROOT, [q['manifest']])
            hosts = {modules.anchor_host(t['anchor']) for t in q['assembly'].values()}
            self.assertTrue(set(plan['build_target'].split('+')) <= {*(modules.target(a) for a in q['assembly']), *hosts}, (name, plan['build_target']))
            self.assertIn('test_production', plan['tests'])
            self.assertTrue(set(q['pack'].get('inspect', [])) <= set(plan['inspect_groups']), name)


if __name__ == '__main__':
    unittest.main()
