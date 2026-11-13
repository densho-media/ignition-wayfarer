"""SYS-001 ring cabin CO2 balance: canon parameters, the exact step, conservation, and the unit's fault, isolation, spare-part, repair
and restore transitions (DS-1)."""
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

    def fields(self, st):
        return {f: st[f] for f in ca.FIELDS}

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
        # coarser steps (as a faster time compression gives) land on the same states: every event time is a multiple of 300 s
        for dt in (7.5, 60.0, 300.0):
            coarse = ca.checkpoints(self.p, dt=dt)
            self.assertEqual(len(coarse), len(self.c['proof']['checkpoints']))
            for a, b in zip(coarse, self.c['proof']['checkpoints']):
                self.assertLessEqual(abs(a['m_kg'] - b['m_kg']), ca.TOLERANCE['rel'] * b['m_kg'], (dt, a['t_s']))
                self.assertEqual((a['mode'], a['fan'], a['spare']), (b['mode'], b['fan'], b['spare']))

    def test_every_kilogram_is_accounted_for(self):
        st = ca.start(self.p, spare='BENCH')
        for t, op in [(600.0, 'fault_fan'), (1800.0, 'isolate'), (3600.0, 'take_spare'), (5400.0, 'install_spare'), (7200.0, 'restore'),
                      (20000.0, 'isolate')]:
            while st['t_s'] < t:
                ca.step(st, self.p, 1.0)
                self.assertLess(abs(ca.ledger_error(st)), 1e-12)
                self.assertGreaterEqual(st['m_kg'], 0.0)
            self.assertEqual(ca.operate(st, op), '')
        for cp in self.c['proof']['checkpoints']:
            self.assertGreaterEqual(cp['removed_kg'], -1e-15)
            self.assertLessEqual(cp['removed_kg'], cp['generated_kg'] + cp['m_kg'])

    def test_a_failed_fan_removes_nothing_even_when_running(self):
        st = ca.start(self.p, spare='BENCH')
        self.assertEqual(ca.operate(st, 'fault_fan'), '')
        r = ca.readout(st, self.p)
        want = self.p['occupants'] * self.p['per_person_kg_s'] / ca.M_CO2 / self.p['n_mol'] * 3600.0
        self.assertEqual((r['mode'], r['removing'], r['status']), ('RUNNING', False, 'RUNNING_NOT_REMOVING'))
        self.assertAlmostEqual(r['dxdt_per_h'], want, delta=1e-15)
        self.assertAlmostEqual(r['hours_to_control_limit'], ca.hours_between(self.p, r['x'], self.p['co2_max']), delta=1e-9)
        d = ca.diagnostics(st, self.p)
        self.assertEqual((d['supply'], d['fan_command'], d['fan_speed_pct'], d['scrubbed_flow_m3_h']), ('ENERGIZED', 'ON', 0.0, 0.0))
        removed = st['removed_kg']
        ca.step(st, self.p, 3600.0)
        self.assertAlmostEqual(st['removed_kg'], removed, delta=1e-15)

    def test_isolation_makes_it_safe_but_repairs_nothing(self):
        st = ca.start(self.p, spare='BENCH')
        ca.operate(st, 'fault_fan')
        self.assertEqual(ca.operate(st, 'isolate'), '')
        self.assertEqual(ca.status(st), 'ISOLATED_FAULT')
        self.assertIn('Replace the fan', ca.operate(st, 'restore'))
        self.assertEqual(ca.readout(st, self.p)['removing'], False)

    def test_repair_needs_isolation_and_the_spare(self):
        st = ca.start(self.p, spare='BENCH')
        ca.operate(st, 'fault_fan')
        ca.operate(st, 'take_spare')
        before = self.fields(st)
        self.assertIn('isolate it before opening it', ca.operate(st, 'install_spare'))    # running: refused, nothing changes
        self.assertEqual(self.fields(st), before)
        ca.operate(st, 'isolate')
        self.assertEqual(ca.operate(st, 'install_spare'), '')
        self.assertEqual((st['fan'], st['spare'], st['mode'], ca.status(st)), ('OK', 'INSTALLED', 'ISOLATED', 'ISOLATED_READY'))
        self.assertFalse(ca.removing(st))                                                    # repaired but not restored
        self.assertIn('already installed', ca.operate(st, 'take_spare'))
        st2 = ca.start(self.p, spare='BENCH')
        ca.operate(st2, 'fault_fan'); ca.operate(st2, 'isolate')
        self.assertIn('still at the sector 2 workbench', ca.operate(st2, 'install_spare'))
        st3 = ca.start(self.p)                                                               # no spare aboard
        ca.operate(st3, 'fault_fan'); ca.operate(st3, 'isolate')
        self.assertIn('no spare', ca.operate(st3, 'install_spare'))
        self.assertIn('no spare', ca.operate(st3, 'take_spare'))

    def test_restored_the_ring_returns_to_a_stable_steady_state(self):
        st = ca.start(self.p, spare='BENCH')
        for op in ('fault_fan', 'isolate', 'take_spare'):
            ca.operate(st, op)
        ca.step(st, self.p, 6 * 3600.0)
        ca.operate(st, 'install_spare')
        self.assertEqual(ca.operate(st, 'restore'), '')
        r0 = ca.readout(st, self.p)
        self.assertTrue(r0['removing'])
        self.assertLess(r0['dxdt_per_h'], 0.0)
        self.assertIsNone(r0['hours_to_control_limit'])
        xs = []
        for _ in range(96):                                                                  # 48 h, 12 time constants V/k
            ca.step(st, self.p, 1800.0)
            xs.append(ca.readout(st, self.p)['x'])
        self.assertEqual(xs, sorted(xs, reverse=True))                                       # monotonic, no overshoot
        self.assertAlmostEqual(xs[-1], ca.steady_x(self.p), delta=1e-6)
        self.assertLess(ca.steady_x(self.p), self.p['co2_target'])

    def test_refused_operations_change_nothing(self):
        st = ca.start(self.p, spare='BENCH')
        for op, field in (('restore', 'mode'), ('install_spare', 'mode'), ('take_spare', ''), ('take_spare', 'spare')):
            before = (self.fields(st), len(st['log']))
            self.assertEqual(ca.blocked(st, op), field)
            reason = ca.operate(st, op)
            if field:
                self.assertTrue(reason)
                self.assertEqual((self.fields(st), len(st['log'])), before)
        self.assertIn('unknown', ca.operate(st, 'repair'))
        self.assertEqual(ca.blocked(st, 'repair'), 'op')

    def test_every_refusal_has_an_engineering_reason(self):
        for op, spec in ca.OPERATIONS.items():
            for field, allowed in spec['requires'].items():
                for value in ca.FIELDS[field]:
                    if value not in allowed:
                        self.assertIn(value, ca.REFUSALS[op][field], (op, field, value))

    def test_the_time_to_the_limit_counts_from_the_present_state(self):
        for x0 in (0.0015, 0.003, 0.004):
            st = ca.start(self.p, mode='ISOLATED', x0=x0)
            self.assertAlmostEqual(ca.readout(st, self.p)['hours_to_control_limit'], ca.hours_between(self.p, x0, 0.005), delta=1e-9)
        # a removing unit that cannot hold the ring (too many people) reaches the limit later than the linear rise says
        p = dict(self.p, occupants=24)
        st = ca.start(p, x0=0.003)
        h = ca.readout(st, p)['hours_to_control_limit']
        self.assertGreater(h, ca.hours_between(p, 0.003, 0.005))
        ca.step(st, p, h * 3600.0)
        self.assertAlmostEqual(ca.readout(st, p)['x'], 0.005, delta=1e-12)

    def test_bands_rise_in_order(self):
        kpa = [b['kpa'] for b in self.c['bands']]
        self.assertEqual(kpa, sorted(kpa))
        self.assertAlmostEqual(kpa[0], 0.4, places=12)


if __name__ == '__main__':
    unittest.main()
