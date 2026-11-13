"""Deadship DS-1 scenario: it sets no engineering value, names only model operations, and its reference replay ends stable."""
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
import cabin_air as ca
import deadship


class DeadshipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sc = deadship.load()
        cls.p = ca.params()

    def test_the_scenario_owns_no_engineering_value(self):
        import json
        import tempfile
        bad = dict(self.sc, initial=dict(self.sc['initial'], co2_max=0.01))
        lines = []                                    # a minimal TOML writer for the fixture: the tables only
        for table, body in bad.items():
            if isinstance(body, dict):
                lines.append(f'[{table}]')
                lines += [f'{k} = {json.dumps(v)}' for k, v in body.items()]
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'bad.toml').write_text('\n'.join(lines) + '\n')
            with self.assertRaises(ValueError):
                deadship.load(d, 'bad.toml')

    def test_the_trainee_meets_a_model_result_not_a_set_value(self):
        st = deadship.begin(self.sc, self.p)
        lead = self.sc['initial']['fault_lead_h']
        x = ca.readout(st, self.p)['x']
        self.assertAlmostEqual(x, ca.steady_x(self.p) + lead * 3600.0 * self.p['occupants'] * self.p['per_person_kg_s']
                               / ca.M_CO2 / self.p['n_mol'], delta=1e-12)
        self.assertEqual(ca.status(st), 'RUNNING_NOT_REMOVING')
        self.assertLess(x, self.p['co2_max'])                    # the trainee starts with time in hand
        self.assertGreater(x, self.p['co2_target'])              # and the board shows the warning band

    def test_the_reference_run_repairs_and_stabilizes(self):
        ref = deadship.reference(self.sc, self.p)
        self.assertEqual([e['op'] for e in ref['events']], ['isolate', 'take_spare', 'install_spare', 'restore'])
        self.assertTrue(ref['watch']['passed'])
        self.assertLessEqual(ref['watch']['x_end'], self.p['co2_target'])
        self.assertLess(ref['watch']['x_max'], self.p['co2_max'])
        self.assertLess(abs(ref['ledger_kg']), ca.TOLERANCE['abs_kg'])
        self.assertEqual(deadship.reference(self.sc, self.p), ref)    # deterministic

    def test_an_unrepaired_ring_fails_the_watch(self):
        st = deadship.begin(self.sc, self.p)
        w = deadship.watch(st, self.p, self.sc['watch']['ship_h'])
        self.assertFalse(w['passed'])
        self.assertFalse(w['removing'])


if __name__ == '__main__':
    unittest.main()
