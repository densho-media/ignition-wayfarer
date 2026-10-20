"""MECH-003 life-support stock/flow: the owner's 41_SURVIVAL_RESOURCES results and mass conservation."""
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
import life_support as ls


class LifeSupportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = ls.load()

    def test_the_simulator_reproduces_the_owner_results(self):
        got = ls.owner_results(self.reg)
        for c in self.reg['check']:
            self.assertAlmostEqual(got[c['id']], c['expected'], delta=1e-6 * max(1.0, c['expected']), msg=c['id'])

    def test_every_kilogram_has_one_origin(self):
        for sc in ls.scenarios(self.reg):
            st = ls.start(self.reg, sc['params'])
            for day in ls.CHECKPOINTS:
                ls.run_to(st, self.reg, sc['params'], day)
                for k, e in ls.ledger_errors(st).items():
                    self.assertLess(abs(e), 1e-6, f"{sc['id']} {k} day {day}")

    def test_open_stores_stay_open_and_nothing_is_free(self):
        p = ls.params(self.reg)
        st = ls.run_to(ls.start(self.reg, p), self.reg, p, 2191.5)
        self.assertIsNone(st['store']['O2'])
        self.assertIsNone(st['store']['WATER_MAKEUP'])
        self.assertEqual(st['drawn']['O2'], 0.0)
        self.assertEqual(st['garden_food'] + st['o2_recovered'], 0.0)       # 41!B20, 38 S02: no credit by default
        self.assertGreater(st['required']['O2'], 0.0)

    def test_a_store_runs_out_and_the_rest_is_a_deficit(self):
        p = ls.params(self.reg)
        st = ls.run_to(ls.start(self.reg, p), self.reg, p, 2191.5)
        r = ls.rates(self.reg)
        self.assertAlmostEqual(st['depleted']['FOOD'], 10000.0 / (5 * r['FOOD']), places=9)
        self.assertEqual(st['store']['FOOD'], 0.0)
        self.assertAlmostEqual(st['deficit']['FOOD'], st['need']['FOOD'] - 10000.0, places=6)

    def test_fractions_outside_zero_one_are_refused(self):
        with self.assertRaises(ValueError):
            ls.params(self.reg, water_recovery=1.2)


if __name__ == '__main__':
    unittest.main()
