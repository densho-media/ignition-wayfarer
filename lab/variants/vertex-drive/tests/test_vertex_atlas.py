"""Vertex Drive Technology Atlas checks (run by hand: python3 lab/variants/vertex-drive/tests/test_vertex_atlas.py).

Lab tests are not part of tests/ or CI. They check the registry's consistency, that the validator catches each class of error the brief
lists, that the generated documents match the registry, that V0 reproduces FDP-1, and that this lab entry changed nothing outside itself.
"""
import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import atlas  # noqa: E402

ALLOWED = ('lab/variants/vertex-drive/', 'lab/README.md')


class Registry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.A = atlas.load()
        cls.pmds = atlas.pmds_ids()

    def errs(self, A):
        return atlas.validate(A, self.pmds)

    def test_registry_is_consistent(self):
        self.assertEqual(self.errs(self.A), [])

    def test_all_eight_workstreams(self):
        ws = sorted(t['id'] for t in self.A['technologies'] if t['kind'] == 'workstream')
        self.assertEqual(ws, [f'VTX-0{n}' for n in range(1, 9)])

    def _mut(self, fn):
        A = copy.deepcopy(self.A)
        fn(A)
        return self.errs(A)

    def test_detects_duplicate_id(self):
        e = self._mut(lambda A: A['technologies'].append(copy.deepcopy(A['technologies'][1])))
        self.assertTrue(any('duplicate technology id' in x for x in e))

    def test_detects_missing_attribute(self):
        e = self._mut(lambda A: A['technologies'][1].pop('breakthrough'))
        self.assertTrue(any('missing attribute breakthrough' in x for x in e))

    def test_detects_broken_dependency(self):
        e = self._mut(lambda A: A['technologies'][1]['depends_on'].append('VTX-09Z'))
        self.assertTrue(any('depends_on unknown' in x for x in e))

    def test_detects_cycle(self):
        def f(A):
            by = {t['id']: t for t in A['technologies']}
            by['VTX-02B']['depends_on'] = ['VTX-02C']          # VTX-02C already requires VTX-02B
        self.assertTrue(any('dependency cycle' in x for x in self._mut(f)))

    def test_detects_invalid_classifications(self):
        def f(A):
            t = A['technologies'][1]
            t['credibility'] = 'LIKELY'; t['research_status'] = 'DONE'; t['canon_status'] = 'MAYBE'; t['geometry']['status'] = 'DRAWN'
        e = self._mut(f)
        for k in ('credibility', 'research_status', 'canon_status', 'geometry status'):
            self.assertTrue(any(f'invalid {k}' in x for x in e), k)

    def test_detects_unproven_claim(self):
        def f(A):
            A['technologies'][1].setdefault('claims', []).append({'quantity': 'x', 'value': 1.0, 'unit': 'm'})
        e = self._mut(f)
        self.assertTrue(any('missing basis' in x for x in e) and any('missing source' in x for x in e))

    def test_detects_unit_conflict(self):
        def f(A):
            c = [t for t in A['technologies'] if t.get('claims')]
            q = c[0]['claims'][0]
            c[1].setdefault('claims', []).append({**q, 'unit': 'furlong'})
        self.assertTrue(any('conflicts with' in x for x in self._mut(f)))

    def test_detects_unknown_source_and_material(self):
        def f(A):
            A['technologies'][1]['evidence'].append('S-NOWHERE'); A['technologies'][1]['materials'].append('MAT-UNOBTAINIUM')
        e = self._mut(f)
        self.assertTrue(any('unknown source S-NOWHERE' in x for x in e) and any('MAT-UNOBTAINIUM' in x for x in e))

    def test_canon_approval_only_with_canon_evidence(self):
        def f(A):
            A['technologies'][1]['canon_status'] = 'APPROVED'
        self.assertTrue(any('APPROVED canon status' in x for x in self._mut(f)))

    def test_generation_change_needs_technology(self):
        def f(A):
            A['generations'][1]['change'][0]['technology'] = 'VTX-09'
        self.assertTrue(any('unknown technology' in x for x in self._mut(f)))

    def test_generated_documents_in_sync(self):
        for name, text in (('ATLAS.md', atlas.render_atlas(self.A)), ('READINESS.md', atlas.render_readiness(self.A)),
                           ('figures/dependency_map.svg', atlas.render_svg(self.A))):
            self.assertEqual((HERE / name).read_text(), text, f'{name} is stale: run atlas.py render')


class Results(unittest.TestCase):
    def test_v0_reproduces_fdp1(self):
        R = json.loads((HERE / 'results/convergence.json').read_text())
        self.assertTrue(R['v0_reproduces_fdp1'])
        self.assertAlmostEqual(R['generations']['V0']['summary']['departure_t'], 20760.0, delta=0.01 * 20760.0)

    def test_generations_do_not_beat_physics(self):
        R = json.loads((HERE / 'results/convergence.json').read_text())
        for k, g in R['generations'].items():
            if g['summary'].get('converged'):
                share = g['ledger_share']
                self.assertAlmostEqual(sum(share.values()), 1.0, delta=1e-6, msg=k)   # every watt of fusion is booked once


class CanonGuard(unittest.TestCase):
    def test_only_this_lab_entry_changed(self):
        try:
            base = subprocess.run(['git', 'merge-base', 'HEAD', 'origin/main'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
            out = subprocess.run(['git', 'diff', '--name-only', base], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
            out += subprocess.run(['git', 'ls-files', '--others', '--exclude-standard'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.skipTest('git or origin/main not available')
        stray = [p for p in out if not p.startswith(ALLOWED)]
        self.assertEqual(stray, [], 'files outside the Vertex lab entry changed (canon, geometry, data or code)')


if __name__ == '__main__':
    unittest.main(verbosity=1)
