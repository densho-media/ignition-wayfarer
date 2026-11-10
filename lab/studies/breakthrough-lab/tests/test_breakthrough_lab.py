"""Breakthrough Lab: data, scientific and website integrity (lab tests, run on demand; not part of the pipeline or CI).

    python3 lab/studies/breakthrough-lab/tests/test_breakthrough_lab.py

Data integrity: valid records, stable and unique IDs, references and dependencies that resolve, evidence and canon vocabularies.
Scientific integrity: the imported research and the T00 generations are reproduced unchanged, each case's inputs are exactly the
reference plus its declared levels, no closing case loses a heat load, an advanced radiator never changes the heat per unit of
fusion power, beyond-limit values are refused, unmet dependencies are flagged, and the site copies every number from the results.
Website: the Engineering 2.0 pages build, link to each other and embed parseable data; tests/web_check.js drives them in Chromium
(selection, comparison, missing data, out-of-range, keyboard, phone width, 3D-free reading) when node and Playwright are installed.
"""
import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
ROOT = LAB.parents[2]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(ROOT / 'tools'))
import lab  # noqa: E402

# IDs published on the website. They may be retired (development REJECTED) but never removed or renumbered.
PUBLISHED_BT = ['BT-001', 'BT-002', 'BT-003', 'BT-004', 'BT-005', 'BT-006', 'BT-007']
PUBLISHED_WL = ['WL-001', 'WL-002', 'WL-003', 'WL-004', 'WL-005', 'WL-006', 'WL-007', 'WL-008', 'WL-009']


def site_data():
    run = subprocess.run([sys.executable, '-I', str(LAB / 'site.py'), '--json'], cwd=ROOT, capture_output=True, text=True, timeout=300)
    if run.returncode:
        raise AssertionError(run.stderr[-2000:])
    return json.loads(run.stdout)


class DataIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.R = lab.load()

    def errors(self, R):
        return lab.validate(R)

    def test_registries_valid(self):
        self.assertEqual(self.errors(self.R), [])

    def test_ids_stable(self):
        ids = [b['id'] for b in self.R['breakthroughs']]
        for i in PUBLISHED_BT:
            self.assertIn(i, ids, f'{i} was published; retire it (REJECTED), never delete or renumber it')
        wl = [w['id'] for w in self.R['links']]
        for i in PUBLISHED_WL:
            self.assertIn(i, wl, f'{i} was published; delete only when RESOLVED, never renumber')

    def test_at_least_three_breakthroughs_computed(self):
        self.assertGreaterEqual(len(lab.lever_ids(self.R)), 3)

    def mutated(self, fn):
        R = copy.deepcopy(self.R)
        R['results'] = None
        fn(R)
        return self.errors(R)

    def test_duplicate_id_rejected(self):
        e = self.mutated(lambda R: R['breakthroughs'].append(copy.deepcopy(R['breakthroughs'][0])))
        self.assertTrue(any('duplicate' in x for x in e), e)

    def test_unknown_reference_and_dependency_rejected(self):
        def f(R):
            R['breakthroughs'][0]['references'].append('S-NOPE')
            R['breakthroughs'][0]['depends_on'].append('BT-999')
            R['links'][0]['evidence'].append({'source': 'S-NOPE'})
        e = self.mutated(f)
        self.assertTrue(any('S-NOPE' in x for x in e) and any('BT-999' in x for x in e), e)

    def test_dependency_cycle_rejected(self):
        def f(R):
            by = {b['id']: b for b in R['breakthroughs']}
            by['BT-001']['depends_on'] = ['BT-005']           # BT-005 already depends on BT-001
        self.assertTrue(any('cycle' in x for x in self.mutated(f)))

    def test_evidence_and_level_vocabulary(self):
        e = self.mutated(lambda R: R['breakthroughs'][0].update(evidence='PROVEN'))
        self.assertTrue(any('evidence' in x for x in e))
        # A Level C proposal is never demonstrated or literature-supported.
        e = self.mutated(lambda R: next(b for b in R['breakthroughs'] if b['level'] == 'C').update(evidence='DEMONSTRATED'))
        self.assertTrue(any('Level C' in x for x in e), e)

    def test_canon_needs_owner_decision(self):
        e = self.mutated(lambda R: R['breakthroughs'][0].update(canon='APPROVED'))
        self.assertTrue(any('owner' in x for x in e), e)
        self.assertTrue(all(b['canon'] == 'NON_CANON' for b in self.R['breakthroughs']), 'no breakthrough is canon without an owner decision')

    def test_level_may_set_only_declared_parameters(self):
        def f(R):
            R['breakthroughs'][0]['levels'][1]['set']['base.overrides.pulsed.driver_efficiency.optimistic'] = 0.9
        self.assertTrue(any('modifies' in x for x in self.mutated(f)))

    def test_level_beyond_limit_rejected(self):
        def f(R):
            b = next(x for x in R['breakthroughs'] if x.get('limit'))
            b['levels'][-1]['set'][b['limit']['path']] = b['limit']['max'] * 1.5
        self.assertTrue(any('limit' in x for x in self.mutated(f)))

    def test_ranking_is_rule_based(self):
        order = [w['id'] for w in lab.ranked(self.R['links'])]
        tiers = [lab.tier(w) for w in lab.ranked(self.R['links'])]
        self.assertEqual(tiers, sorted(tiers))
        by = {w['id']: w for w in self.R['links']}
        self.assertEqual(lab.tier(by['WL-001']), 1, 'target physics is a fundamental blocker')
        self.assertLess(order.index('WL-001'), order.index('WL-005'), 'a fatal target problem ranks above an oversized radiator')


class ScientificIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.R = lab.load()
        cls.res = cls.R['results']
        if cls.res is None:
            raise unittest.SkipTest('results/scenarios.json not computed (compute.py)')

    def test_imports_unchanged(self):
        for m in self.R['imports']:
            for f in m['files']:
                self.assertEqual(lab.sha256(lab.IMPORTS / m['folder'] / f['path']), f['sha256'], f'{m["folder"]}/{f["path"]} changed after import')

    def test_baseline_generations_reproduced(self):
        rep = self.res['reproduces']
        self.assertTrue(rep, 'named scenarios must reproduce T00 generations')
        for k, r in rep.items():
            self.assertTrue(r['match'], f'{k} does not reproduce T00 {r["generation"]}: {r}')
        self.assertAlmostEqual(rep['SC-V4']['computed_departure_t'], 42915.78, delta=0.5)

    def test_provenance(self):
        p = self.res['provenance']
        t00 = next(m for m in self.R['imports'] if m['thread'] == 'T00')
        self.assertEqual(p['t00_commit'], t00['commit'])
        self.assertEqual(p['registry_sha256'], lab.registry_hash(), 'registries changed after compute.py ran')
        self.assertTrue(all(len(h) == 64 for h in p['calculator_files'].values()))

    def test_inputs_are_reference_plus_declared_levels(self):
        self.assertEqual(lab.validate_results(self.R), [])
        R = copy.deepcopy(self.R)
        k = next(iter(R['results']['cases']))
        R['results']['cases'][k]['inputs']['base.overrides.pulsed.driver_efficiency.optimistic'] = 0.95
        self.assertTrue(any('inputs differ' in x for x in lab.validate_results(R)))

    def test_no_vanishing_heat(self):
        for k, c in self.res['cases'].items():
            if c['status'] == 'CLOSES':
                self.assertGreater(c['summary']['hot_GW'], 0, k)
                self.assertGreater(c['summary']['warm_GW'], 0, k)

    def test_radiator_breakthrough_keeps_heat_per_fusion_power(self):
        """BT-004 changes radiator mass only: the heat per unit of fusion power must not change between otherwise equal cases."""
        cs = self.res['cases']
        pairs = 0
        for k, c in cs.items():
            if c['status'] != 'CLOSES' or c['levels']['BT-004'] != 'L1':
                continue
            other = cs.get(k.replace('BT-004:L1', 'BT-004:L0'))
            if other and other['status'] == 'CLOSES':
                pairs += 1
                for f in ('hot_GW', 'warm_GW'):
                    a = c['summary'][f] / c['summary']['fusion_TW']
                    b = other['summary'][f] / other['summary']['fusion_TW']
                    self.assertAlmostEqual(a / b, 1.0, delta=0.02, msg=f'{k} {f}: BT-004 changed the heat per fusion power')
        if not pairs:
            self.skipTest('no closing pair differs only in BT-004')

    def test_rate_cap_never_lightens(self):
        cs = self.res['cases']
        for k, c in cs.items():
            if c['status'] == 'CLOSES' and c['levels']['BT-005'] != 'L2':
                free = cs[k.replace(f'BT-005:{c["levels"]["BT-005"]}', 'BT-005:L2')]
                self.assertGreaterEqual(c['summary']['departure_t'], free['summary']['departure_t'] - 1.0, k)

    def test_not_computed_has_no_numbers(self):
        for k, c in self.res['cases'].items():
            if c['status'] in ('NOT_COMPUTED', 'OUT_OF_RANGE'):
                self.assertNotIn('summary', c, k)
                self.assertFalse(c['computed'], k)

    def test_site_copies_numbers_and_flags_dependencies(self):
        d = site_data()
        for k, c in self.res['cases'].items():
            s = d['cases'][k].get('summary', {})
            for f, v in s.items():
                self.assertEqual(v, c['summary'][f], f'{k} {f} differs from the computed result')
        free = next(n for n in d['named'] if n['id'] == 'SC-REF-FREE')
        key = '|'.join(f'{b}:{free["levels"][b]}' for b in d['order'])
        self.assertIn('BT-005 needs BT-001', d['cases'][key].get('dependency_unmet', []))
        for w in d['links']:
            for m in w['metrics']:
                self.assertEqual(m['value'], lab.metric(m))


class Website(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if lab.load()['results'] is None:
            raise unittest.SkipTest('results/scenarios.json not computed')
        cls.tmp = Path(tempfile.mkdtemp(prefix='btlab-site-'))
        shutil.copy2(ROOT / 'web/site.css', cls.tmp / 'site.css')
        import story
        cls.record = story.build(ROOT, cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_pages_and_navigation(self):
        for p in ('baseline', 'weakest-links', 'breakthrough-lab', 'evolution'):
            self.assertIn(f'engineering/{p}/index.html', self.record['pages'])
        self.assertIn('engineering/index.html', self.record['pages'])
        for page in self.record['pages']:
            f = self.tmp / page
            text = f.read_text()
            for href in re.findall(r'href="([^"#:]+)(?:#[^"]*)?"', text):
                if href.startswith(('http', 'mailto', 'data:')):
                    continue
                target = (f.parent / href).resolve()
                if not target.is_relative_to((self.tmp / 'engineering').resolve()):
                    continue  # another site section (viewer, play, status), built by web_export
                if target.is_dir():
                    target = target / 'index.html'
                self.assertTrue(target.exists(), f'{page}: broken link {href}')

    def test_embedded_data_parses(self):
        for p in ('breakthrough-lab', 'evolution'):
            text = (self.tmp / f'engineering/{p}/index.html').read_text()
            m = re.search(r'<script type="application/json" id="bt-data">(.*?)</script>', text, re.S)
            data = json.loads(m.group(1))
            self.assertIn(data['v4_key'], data['cases'])

    def test_browser(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node not installed')
        run = subprocess.run([node, str(HERE / 'web_check.js'), str(self.tmp)], capture_output=True, text=True, timeout=600)
        if 'Cannot find module' in run.stderr:
            self.skipTest('Playwright not installed')
        self.assertEqual(run.returncode, 0, run.stdout[-3000:] + run.stderr[-3000:])


if __name__ == '__main__':
    unittest.main(verbosity=2)
