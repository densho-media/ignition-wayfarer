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

# Canon guard (shared rule with lab/variants/fdp1/tests/test_fdp1.py): only lab/ and work/ may change, never the calculators this
# entry builds on (FDP-1 engineering, config and run.py; the four-burn engine). T05 writes work/vertex-blender/, so work/ is allowed.
ALLOWED_ROOTS = ('lab/', 'work/')
PROTECTED_IN_LAB = ('lab/variants/fdp1/engineering/', 'lab/variants/fdp1/config/', 'lab/variants/fdp1/run.py',
                    'lab/studies/four-burn-mission/fourburn/', 'lab/studies/four-burn-mission/scenarios/')


def guard_violations(paths):
    return [p for p in paths if not p.startswith(ALLOWED_ROOTS) or p.startswith(PROTECTED_IN_LAB)]


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


class ResultArithmetic(unittest.TestCase):
    """Independent hand checks of the committed results (T00, 2026-11-09): each generation's summary must obey the physics it reports,
    recomputed here without the FDP-1 calculator."""
    G0, C, SIGMA, EPS, YEAR = 9.80665, 299792458.0, 5.670374419e-8, 0.9, 3.15576e7

    @classmethod
    def setUpClass(cls):
        cls.R = json.loads((HERE / 'results/convergence.json').read_text())

    def each(self):
        for name, g in self.R['generations'].items():
            yield name, g, g['summary']

    def test_energy_ledger_closes(self):
        for name, g, _ in self.each():
            self.assertAlmostEqual(sum(g['ledger_share'].values()), 1.0, places=9, msg=name)

    def test_thrust_power_and_burn_time(self):
        for name, g, s in self.each():
            m0, F, ve = s['departure_t'] * 1e3, s['thrust_MN'] * 1e6, s['ve_km_s'] * 1e3
            self.assertAlmostEqual(F / m0 / self.G0, s['a0_g'], delta=1e-6 * s['a0_g'], msg=name)
            self.assertAlmostEqual(0.5 * F * ve / 1e12, s['jet_TW'], delta=1e-6 * s['jet_TW'], msg=name)
            self.assertAlmostEqual(s['jet_TW'] / s['fusion_TW'], g['ledger_share']['jet'], delta=1e-6, msg=name)
            self.assertAlmostEqual(s['propellant_t'] * 1e3 / (F / ve) / self.YEAR, s['burn_years'], delta=1e-3, msg=name)

    def test_rocket_equation_four_burns(self):
        for name, g, s in self.each():
            dv = 4 * 0.016 * self.C
            self.assertAlmostEqual(s['departure_t'] / s['end_t'], 2.718281828 ** (dv / (s['ve_km_s'] * 1e3)), delta=1e-4, msg=name)
            self.assertAlmostEqual(s['propellant_t'] + s['end_t'], s['departure_t'], delta=1e-6 * s['departure_t'], msg=name)

    def test_warm_radiator_stefan_boltzmann(self):
        for name, g, s in self.each():
            T = 600.0
            for c in g['changes']:
                if c['path'] == 'base.overrides.radiators.warm.T_K.optimistic':
                    T = c['value']
            area = g['warm_GW'] * 1e9 / (2 * self.EPS * self.SIGMA * T ** 4)
            self.assertAlmostEqual(area / 1e6, s['warm_km2'], delta=1e-4 * s['warm_km2'], msg=name)


class CanonGuard(unittest.TestCase):
    def test_guard_rule(self):
        ok = ['lab/README.md', 'lab/variants/vertex-drive/studies/thermal/HANDOFF.md', 'work/vertex-blender/NOTES.md']
        self.assertEqual(guard_violations(ok), [])
        bad = ['data/wayfarer_3d.toml', 'src/wayfarer/spec.py', 'tests/test_spec.py', 'tools/workflow.py', 'godot/project.godot',
               'web/index.html', 'assets/WF_WAYFARER_001.blend', 'references/geometry_baseline.json', 'docs/MODEL.md',
               '.github/workflows/web-explorer.yml', 'AGENTS.md', 'CLAUDE.md', 'README.md', 'TODO.md', '.gitignore',
               'lab/variants/fdp1/engineering/model.py', 'lab/variants/fdp1/config/fdp1.toml', 'lab/variants/fdp1/run.py',
               'lab/studies/four-burn-mission/fourburn/closure.py']
        self.assertEqual(guard_violations(bad), bad)

    def test_only_lab_and_work_changed(self):
        try:
            base = subprocess.run(['git', 'merge-base', 'HEAD', 'origin/main'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
            out = subprocess.run(['git', 'diff', '--name-only', base], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
            out += subprocess.run(['git', 'ls-files', '--others', '--exclude-standard'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.skipTest('git or origin/main not available')
        self.assertEqual(guard_violations(out), [], 'canon, geometry, data, code or a shared lab calculator changed')


if __name__ == '__main__':
    unittest.main(verbosity=1)
