"""SYS-001 ring cabin CO2 balance: canon parameters, the exact step, conservation and the unit's state transitions."""
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
import cabin_air as ca


class CabinAirTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = ca.contract()
        cls.p = cls.c['params']

    def test_canon_parameters_are_read_not_restated(self):
        src = self.c['sources']
        self.assertEqual(self.p['P_Pa'], 80000.0)
        self.assertEqual((self.p['co2_target'], self.p['co2_max']), (0.003, 0.005))
        self.assertEqual(src['co2_rate']['value'], 1.0)
        self.assertAlmostEqual(self.p['per_person_kg_s'] * ca.DAY_S, 1.0, places=12)
        self.assertEqual(src['volume']['status'], 'PROTOTYPE')

    def test_the_rated_crew_is_held_at_the_target(self):
        p = dict(self.p, occupants=ca.PROTOTYPE['unit_rated_occupants']['value'])
        r = ca.readout(ca.start(p), p)
        self.assertAlmostEqual(r['x'], p['co2_target'], delta=1e-15)
        self.assertAlmostEqual(r['dxdt_per_h'], 0.0, delta=1e-12)

    def test_the_step_is_exact_and_independent_of_dt(self):
        for cp in self.c['proof']['checkpoints']:
            want = ca.analytic(self.p, cp['t_s'])
            self.assertLessEqual(abs(cp['m_kg'] - want), ca.TOLERANCE['abs_kg'] + ca.TOLERANCE['rel'] * want, cp['t_s'])
        coarse = ca.checkpoints(self.p, dt=60.0)
        for a, b in zip(coarse, self.c['proof']['checkpoints']):
            self.assertLessEqual(abs(a['m_kg'] - b['m_kg']), ca.TOLERANCE['rel'] * b['m_kg'], a['t_s'])

    def test_every_kilogram_is_accounted_for(self):
        st = ca.start(self.p)
        for t, op in [(0.0, 'isolate'), (7200.0, 'restore')]:
            while st['t_s'] < t:
                ca.step(st, self.p, 1.0)
                self.assertLess(abs(ca.ledger_error(st)), 1e-12)
                self.assertGreaterEqual(st['m_kg'], 0.0)
            self.assertEqual(ca.operate(st, op), '')
        for cp in self.c['proof']['checkpoints']:
            self.assertGreaterEqual(cp['removed_kg'], -1e-15)
            self.assertLessEqual(cp['removed_kg'], cp['generated_kg'] + cp['m_kg'])

    def test_isolated_the_fraction_rises_at_the_generation_rate(self):
        st = ca.start(self.p, state='ISOLATED', x0=0.003)
        r = ca.readout(st, self.p)
        want = self.p['occupants'] * self.p['per_person_kg_s'] / ca.M_CO2 / self.p['n_mol'] * 3600.0
        self.assertAlmostEqual(r['dxdt_per_h'], want, delta=1e-15)
        self.assertAlmostEqual(r['hours_to_control_limit'], ca.hours_between(self.p, 0.003, 0.005), delta=1e-9)

    def test_only_defined_transitions_happen(self):
        st = ca.start(self.p)
        self.assertIn('refused', ca.operate(st, 'restore'))
        self.assertEqual(st['state'], 'RUNNING')
        self.assertEqual(ca.operate(st, 'isolate'), '')
        self.assertIn('refused', ca.operate(st, 'isolate'))
        ca.fail(st)
        self.assertIn('refused', ca.operate(st, 'restore'))
        self.assertEqual(st['state'], 'FAILED')
        self.assertIn('unknown', ca.operate(st, 'repair'))

    def test_bands_rise_in_order(self):
        kpa = [b['kpa'] for b in self.c['bands']]
        self.assertEqual(kpa, sorted(kpa))
        self.assertAlmostEqual(kpa[0], 0.4, places=12)


if __name__ == '__main__':
    unittest.main()
