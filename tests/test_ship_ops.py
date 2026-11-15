"""Deadship ship operations: DS-2C "Borrowed Air" on the ring services model. The scenario sets no engineering value; work on a running
machine, work away from the bay and switching away from the console are refused and change nothing; parts are conserved and fit only
their family; a fetch takes the real crossing and work times and leaves ring B without the part; the strategy families end as the
physics says (more than one viable way, each with a different cost); and a replay is identical."""
from pathlib import Path
import sys
import tomllib
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
import ring_services as rs   # noqa: E402
import ship_ops as so   # noqa: E402


class BorrowedAirTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sc = so.load('ds2c')
        cls.p = so.params()
        cls.cases = {n: a for n, _, a in so.cases('ds2c')}
        cls.runs = {n: so.play(cls.sc, cls.p, a) for n, a in cls.cases.items()}

    def deb(self, n):
        return self.runs[n][0].debrief()

    def test_the_scenario_sets_no_engineering_value(self):
        sc = tomllib.loads((ROOT / so.SCENARIOS['ds2c']).read_text())
        self.assertFalse(so.ENGINEERING_KEYS & set(so._keys(sc)))
        self.assertFalse(sc['scenario']['scored'])

    def test_refusals_change_nothing(self):
        r = so.Run(self.sc, self.p)
        before = r.config()
        self.assertIn('bay', r.act('isolate', 'CO2', True))
        self.assertIn('console', r.act('switch', 'A', 'GARDEN', False))
        r.act('trainee', 'A3')
        self.assertIn('not isolated', r.act('remove', 'CO2.FAN'))
        self.assertIn('not isolated', r.act('install', 'P1.PUMP'))
        self.assertIn('not installed in ring B', r.act('order', 'B', 'fetch', 'A.CO2.FAN'))
        self.assertEqual(r.config(), before)

    def test_incompatible_part_is_refused(self):
        r = so.Run(self.sc, self.p)
        r.act('trainee', 'A3'); r.act('isolate', 'P1', True); r.act('remove', 'P1.PUMP')
        for _ in range(31):
            r.tick()
        self.assertEqual(r.hands, 'A.P1.PUMP')
        r.act('isolate', 'CO2', True); r.act('remove', 'CO2.FAN')
        self.assertIn('hands are full', r.log[-1][3])
        r.act('stow')
        r.act('remove', 'CO2.FAN')
        for _ in range(31):
            r.tick()
        r.act('stow'); r.act('take', 'A.P1.PUMP')
        self.assertIn('does not fit', r.act('install', 'CO2.FAN'))

    def test_fetch_takes_the_crossings_and_strips_ring_b(self):
        r = so.Run(self.sc, self.p)
        r.act('order', 'B', 'fetch', 'B.CO2.FAN')
        T = self.sc['crew']['transfer_s']; W = self.sc['crew']['fetch_work_s']
        while r.st['parts']['B.CO2.FAN']['at'] != 'A.SHELF':
            r.tick()
        self.assertAlmostEqual(r.t, 2*T + W, delta=r.dt)
        self.assertTrue(r.st['ring']['B']['isolated']['CO2'])
        self.assertFalse(r.hostable('B'))

    def test_parts_are_conserved(self):
        for n, (r, _) in self.runs.items():
            parts = r.st['parts']
            self.assertEqual(sorted(parts), sorted(rs.start(self.p)['parts']), n)
            held = [v['at'] for v in parts.values() if v['at'] in rs.SLOTS_ALL() or v['at'].startswith('CARRY.')]
            self.assertEqual(len(held), len(set(held)), n)      # one part per slot and per pair of hands; a shelf holds several

    def test_every_ledger_closes(self):
        for n, (r, _) in self.runs.items():
            for k, v in rs.ledgers(r.st, self.p).items():
                self.assertLess(abs(v), 1e3 if k.endswith('_J') else 1e-9, f'{n} {k}')

    def test_outcomes(self):
        want = dict(nothing='CO2_LIMIT', borrow_fan='HEAT_LIMIT', borrow_fan_shed='STABLE', borrow_fan_pump='STABLE', relocate='STABLE',
                    relocate_cold='COLD_LIMIT', cannibalize='HEAT_LIMIT', shed_only='CO2_LIMIT')
        for n, v in want.items():
            self.assertEqual(self.deb(n)['watch']['verdict']['result'], v, n)
        self.assertTrue(self.deb('cannibalize')['watch']['verdict']['peak']['beyond_validity'])

    def test_viable_strategies_differ_in_cost(self):
        viable = {n: self.deb(n) for n in ('borrow_fan_shed', 'borrow_fan_pump', 'relocate')}
        fam = {n: d['watch']['family'] for n, d in viable.items()}
        self.assertEqual(len(set(fam.values())), 3)
        m = {n: d['metrics'] for n, d in viable.items()}
        self.assertEqual(m['relocate']['parts_moved'], [])
        self.assertGreater(m['borrow_fan_shed']['shed_kWh'], 100.0)
        self.assertLess(m['borrow_fan_pump']['shed_kWh'], 1.0)
        self.assertEqual(len(m['borrow_fan_pump']['parts_from_ring_b']), 2)
        self.assertGreater(m['relocate']['watch_declared_h'], m['borrow_fan_pump']['watch_declared_h'])
        for n, d in viable.items():
            self.assertEqual(sum(d['metrics']['hostable'].values()), 1, n)   # no strategy keeps both rings able to host

    def test_replay_is_identical(self):
        self.assertEqual(self.runs['replay_borrow_fan_shed'][1], self.runs['borrow_fan_shed'][1])
        self.assertEqual(self.deb('replay_borrow_fan_shed'), self.deb('borrow_fan_shed'))


if __name__ == '__main__':
    unittest.main()


class DarkBusTests(unittest.TestCase):
    """DS-3 "Dark Bus": a converter failure during a fusion-off coast. The tie trips when asked for more than BC-A's rating, the packs carry
    only survival loads until they are empty, the restart draws the pulse bank from the battery or fails, a load that grows with the
    cabin's temperature can trip the tie during the watch, and the viable strategies spend different things."""

    @classmethod
    def setUpClass(cls):
        cls.sc = so.load('ds3')
        cls.p = so.params()
        cls.runs = {n: so.play(cls.sc, cls.p, a) for n, _, a in so.cases('ds3')}

    def deb(self, n):
        return self.runs[n][0].debrief()

    def test_outcomes(self):
        want = dict(nothing='HEAT_LIMIT', tie_only='CO2_LIMIT', shed_garden='STABLE', shed_dark_b='STABLE', shed_economy='STABLE',
                    short_reserve='RESTART_FAILED', keep_garden='CO2_LIMIT')
        for n, v in want.items():
            self.assertEqual(self.deb(n)['watch']['verdict']['result'], v, n)

    def test_trips_are_physical(self):
        self.assertTrue(self.deb('tie_only')['metrics']['trips'])
        late = self.deb('keep_garden')['metrics']['trips']
        self.assertTrue(late and late[0][0] > 1.0)         # it held at first and tripped as the cabin warmed
        self.assertFalse(self.deb('shed_garden')['metrics']['trips'])

    def test_restart_draws_the_pulse_bank(self):
        for n in ('shed_garden', 'short_reserve'):
            r = self.runs[n][0]
            ok = r.restart['ok']
            self.assertEqual(ok, r.restart['battery_kWh'] >= self.p['pulse_Wh']/1000.0, n)
            self.assertEqual(r.st['pulse_J'], self.p['pulse_Wh']*3600.0 if ok else 0.0, n)

    def test_packs_only_carry_survival_loads(self):
        r = self.runs['nothing'][0]
        self.assertEqual(r.st['pack']['A'], 0.0)
        self.assertGreater(r.st['acc']['E_unserved'], 0.0)

    def test_viable_strategies_are_not_dominated(self):
        rows = {}
        for n in ('shed_garden', 'shed_dark_b', 'shed_economy'):
            m = self.deb(n)['metrics']; v = self.deb(n)['watch']['verdict']
            # lower is better in every column: service shed, reserve spent, humidity-band hours, rings left dark
            rows[n] = (m['shed_kWh'], -m['restart']['battery_kWh'], v['crew_h']['humidity_band'], len(m['dark_rings']))
        for a in rows:
            for b in rows:
                if a != b:
                    self.assertFalse(all(x <= y for x, y in zip(rows[b], rows[a])) and rows[a] != rows[b], f'{a} dominated by {b}')

    def test_every_ledger_closes(self):
        for n, (r, _) in self.runs.items():
            for k, v in rs.ledgers(r.st, self.p).items():
                self.assertLess(abs(v), 1e3 if k.endswith('_J') else 1e-9, f'{n} {k}')

    def test_replay_is_identical(self):
        self.assertEqual(self.runs['replay_shed_garden'][1], self.runs['shed_garden'][1])
