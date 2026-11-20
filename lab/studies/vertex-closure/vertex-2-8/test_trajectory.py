"""Vertex 2.8 regression checks for the corrected braking path in the shared Vertex dust model (research, not canon; outside CI).

    python3 lab/studies/vertex-closure/vertex-2-8/test_trajectory.py

The Vertex 2.6 impact model (lab/studies/vertex-closure/vertex-2-6/protect.py) is the shared trajectory and impact pipeline of Vertex 2.6-2.8; the website's
dust-impacts study (lab/studies/dust-impacts, claude/project-thread-6ryvmv) carries its own copy of the 874dca7 model with the same fix.
These checks hold the fix in place: turn-around, closest approach, braking direction and exposure, agreement with the dust-impacts model,
and that the committed Vertex 2.7 results were made on the corrected path.
"""
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent/'vertex-2-6'))
import protect as P  # noqa: E402

TB = 466.85*P.DAY
VE = 0.072*P.C
DUST_BRANCH = 'origin/claude/project-thread-6ryvmv'


def phase(segs, name):
    return [s for s in segs if s['phase'] == name]


class CorrectedPath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.segs, cls.meta = P.mission(TB, VE)

    def test_turnaround_324_au(self):
        self.assertAlmostEqual(self.meta['destination_AU'], 324.33, delta=0.01)
        self.assertAlmostEqual(self.meta['destination_AU'], 1.0+self.meta['burn_AU']+self.meta['brake_AU'], places=9)

    def test_minimum_distance_1_au(self):
        self.assertGreaterEqual(min(s['r'] for s in self.segs), 1.0)
        self.assertAlmostEqual(self.meta['min_r_AU'], 1.0, delta=0.01)

    def test_braking_direction(self):
        for name, sign, end in (('brake at destination', +1, self.meta['destination_AU']), ('brake at home', -1, 1.0)):
            b = phase(self.segs, name)
            self.assertTrue(all(s['orient'] == 'ENGINE_FIRST' for s in b), name)
            self.assertTrue(all(sign*(y['r']-x['r']) > 0 for x, y in zip(b, b[1:])), f'{name}: moves the wrong way')
            self.assertTrue(all(y['v'] <= x['v'] for x, y in zip(b, b[1:])), f'{name}: speed must fall')
            last = b[-1]['r']+sign*b[-1]['ds']/2/P.AU
            self.assertAlmostEqual(last, end, delta=1e-6, msg=f'{name} must end at {end} AU')
        for name in ('accelerate out', 'accelerate home'):
            self.assertTrue(all(s['orient'] == 'BOW_FIRST' for s in phase(self.segs, name)))

    def test_braking_longer_than_accelerating(self):
        # constant thrust: the ship is heaviest at the start of a burn, so a braking burn spends more of its time fast
        self.assertGreater(self.meta['brake_AU'], self.meta['burn_AU'])
        self.assertAlmostEqual(self.meta['burn_AU'], 155.68, delta=0.01)
        self.assertAlmostEqual(self.meta['brake_AU'], 167.65, delta=0.01)

    def test_superseded_path_kept_and_wrong(self):
        segs, meta = P.mission_superseded_874dca7(TB, VE)
        self.assertLess(min(s['r'] for s in segs), -10.0)
        self.assertAlmostEqual(meta['destination_AU'], 312.36, delta=0.01)

    def test_exposure_engine_fronts(self):
        # bore-less engine fronts, events above the 5 mm face's perforation energy: corrected / superseded = 0.365
        item = dict(P.lead_item('engine fronts', 4*math.pi*11.4358**2), leads='ENGINE_FIRST')
        E5 = P.perforation_energy(0.005, P.K_CRATER['NOMINAL'])
        new = P.events(item, self.segs, E5, 'NOMINAL')
        old = P.events(item, P.mission_superseded_874dca7(TB, VE)[0], E5, 'NOMINAL')
        self.assertAlmostEqual(new/old, 0.365, delta=0.01)
        self.assertGreater(new, 1000.0)

    def test_agrees_with_dust_impacts_model(self):
        try:
            src = subprocess.run(['git', 'show', f'{DUST_BRANCH}:lab/studies/dust-impacts/model.py'], cwd=ROOT, capture_output=True,
                                 text=True, check=True).stdout
            imp = subprocess.run(['git', 'show', f'{DUST_BRANCH}:lab/studies/dust-impacts/imports/vertex_2_6_874dca7/protect.py'],
                                 cwd=ROOT, capture_output=True, text=True, check=True).stdout
            env = subprocess.run(['git', 'show', f'{DUST_BRANCH}:lab/studies/dust-impacts/imports/vertex_2_6_874dca7/t02_environment.py'],
                                 cwd=ROOT, capture_output=True, text=True, check=True).stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.skipTest(f'{DUST_BRANCH} not fetched')
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); (d/'imports'/'vertex_2_6_874dca7').mkdir(parents=True)
            (d/'model.py').write_text(src)
            (d/'imports'/'vertex_2_6_874dca7'/'protect.py').write_text(imp)
            (d/'imports'/'vertex_2_6_874dca7'/'t02_environment.py').write_text(env)
            saved = {k: sys.modules.pop(k) for k in ('protect', 't02_environment') if k in sys.modules}
            try:
                spec = importlib.util.spec_from_file_location('dust_model', d/'model.py')
                M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
                segs, meta = M.mission(TB, VE, n=240)
            finally:
                for k in ('protect', 't02_environment'):
                    sys.modules.pop(k, None)
                sys.modules.update(saved)
        self.assertEqual(len(segs), len(self.segs))
        for a, b in zip(segs, self.segs):
            self.assertEqual((a['phase'], a['orient']), (b['phase'], b['orient']))
            for k in ('r', 'v', 'ds', 'dt'):
                self.assertTrue(math.isclose(a[k], b[k], rel_tol=1e-12, abs_tol=1e-12), (k, a[k], b[k]))
        self.assertAlmostEqual(meta['destination_AU'], self.meta['destination_AU'], places=9)

    def test_vertex_2_7_results_on_corrected_path(self):
        dust = json.loads((HERE.parent/'vertex-2-7'/'dust.json').read_text())
        self.assertAlmostEqual(dust['meta']['path']['destination_AU'], 324.33, delta=0.01)
        self.assertGreaterEqual(dust['meta']['path']['min_r_AU'], 1.0)
        self.assertAlmostEqual(dust['cases']['NOMINAL']['total_t'], 129.0, delta=1.0)
        self.assertAlmostEqual(dust['standoff']['JUSTIFIED'], 127.15, delta=0.5)


if __name__ == '__main__':
    unittest.main()
