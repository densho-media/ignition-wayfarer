"""The lever model reproduces the recorded ledger (python3 lab/studies/ignition-failures/tests/test_model.py)."""
import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ignition_model', HERE / 'model.py')
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)


class LedgerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        I, _ = M.imports()
        cls.I = I
        cls.K = M.constants(I)
        cls.K['E1000'] = M.radiation()['treg']['T3']['energy_J']
        cls.base = {l['id']: l['value'] for l in M.levers()}

    def test_reference_ratio(self):
        o = M.evaluate(self.K, dict(self.base, G=1e15))
        self.assertAlmostEqual(o['ratio'], self.I['ledger']['reference']['ratio'], delta=0.5)

    def test_driver_share(self):
        o = M.evaluate(self.K, self.base)
        self.assertAlmostEqual((o['ratio'] - o['burn_ratio']), self.I['ledger']['driver']['ratio'], delta=0.5)

    def test_unshielded_coil_life(self):
        o = M.evaluate(self.K, self.base)
        c2 = next(c for c in self.I['neutrons']['coils'] if c['coil'] == 'C2')
        self.assertAlmostEqual(o['coil_life_s'], c2['life_unshielded_s'] * self.I['neutrons']['Pf_W'] / self.K['Pf'], places=6)

    def test_throttle_does_not_fix_fluence(self):
        a, b = M.evaluate(self.K, self.base), M.evaluate(self.K, dict(self.base, tau=1e-3))
        self.assertAlmostEqual(a['coil_life_s'] / a['run_s'], b['coil_life_s'] / b['run_s'], places=9)

    def test_part_shares_sum_to_one(self):
        d = json.loads((HERE / 'results/ignition.json').read_text())
        self.assertAlmostEqual(sum(p['pn'] for p in d['parts']), 1.0, places=4)
        self.assertAlmostEqual(sum(p['ch'] for p in d['parts']), 1.0, places=4)
        self.assertEqual(len(d['parts']), 264)


if __name__ == '__main__':
    unittest.main()
