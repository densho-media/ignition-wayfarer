"""Deadship DS-2B "Shared Air": the scenario layer over ring A's two-gas model. The scenario sets no engineering value, the source keeps
its first-order release until the trainee's containment work is complete, refused actions change nothing, the pairs walk door routes
(never through a sealed wall), each species keeps its own ledger, and the watch neither resets nor quietly changes the run."""
from pathlib import Path
import math
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
import air_exposure as ax   # noqa: E402
import ring_air as ra   # noqa: E402
import shared_air as sa   # noqa: E402


class SharedAirTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sc = sa.load()
        cls.p = sa.params()
        cls.scripts = {n: a for n, _, a in sa.cases()}
        cls.scripts['replay'] = cls.scripts['isolate']
        cls.runs = {n: sa.play(cls.sc, cls.p, a) for n, a in cls.scripts.items()}

    def deb(self, name):
        return self.runs[name][0].debrief()

    # ---- the scenario layer -----------------------------------------------------------------------------------------------------------

    def test_the_scenario_sets_no_engineering_value(self):
        import tomllib
        sc = tomllib.loads((ROOT / sa.SCENARIO).read_text())
        sc['source']['co2_target'] = 0.01
        bad = sorted(p for p, k in sa._keys(sc) if k in sa.ENGINEERING_KEYS)
        self.assertEqual(bad, ['source.co2_target'])
        self.assertFalse(self.sc['scenario']['scored'])

    def test_initial_state(self):
        r = sa.Run(self.sc, self.p)
        self.assertEqual([r.ids[q['node']] for q in r.people], ['A1', 'A1', 'A2', 'A2', 'A3', 'A3'])
        self.assertEqual(r.st['occupants'][:3], [2, 2, 2])
        self.assertEqual(sum(r.st['c']), 0.0)
        self.assertEqual(r.st['source']['state'], 'LEAKING')
        self.assertTrue(all(not r.st['open'][e['id']] for e in self.p['edges'] if e['kind'] == 'door'))
        self.assertEqual((r.st['vent'], r.st['tcc'], r.st['removal']), ('ON', 'ON', 'ON'))

    def test_without_containment_the_release_stays_first_order(self):
        r = self.runs['no_containment'][0]
        S0, tau = self.sc['source']['inventory_kg'], self.sc['source']['tau_s']
        self.assertAlmostEqual(r.st['released'], S0*(1.0 - math.exp(-r.t/tau)), delta=1e-13)
        self.assertEqual(r.st['source']['state'], 'LEAKING')

    def test_containment_takes_the_full_work_in_reach(self):
        for name, start in (('isolate', 900.0), ('interrupted', 900.0)):
            r = self.runs[name][0]
            t_done = next(e[0] for e in r.log if e[1] == 'contained')
            work = self.sc['containment']['work_s']
            self.assertGreaterEqual(t_done - start, work)
            S0, tau = self.sc['source']['inventory_kg'], self.sc['source']['tau_s']
            self.assertAlmostEqual(r.st['released'], S0*(1.0 - math.exp(-t_done/tau)), delta=1e-13)
        # stepped out for 100 s: the work completes 100 s later, keeping what was done
        a = next(e[0] for e in self.runs['isolate'][0].log if e[1] == 'contained')
        b = next(e[0] for e in self.runs['interrupted'][0].log if e[1] == 'contained')
        self.assertAlmostEqual(b - a, 110.0)

    def test_containment_is_refused_away_from_the_store(self):
        r = sa.Run(self.sc, self.p)
        r.act('trainee', 'AC3b')
        self.assertIn('hygiene A', r.act('contain_start'))
        self.assertEqual(r.contain['state'], 'NONE')
        r.act('trainee', 'A1')
        self.assertEqual(r.act('contain_start'), '')
        for _ in range(30):
            r.tick()
        r.act('trainee', 'AC1a')
        self.assertEqual(r.contain['state'], 'PAUSED')
        p0 = r.contain['progress_s']
        for _ in range(30):
            r.tick()
        self.assertEqual(r.contain['progress_s'], p0)
        self.assertEqual(r.st['source']['state'], 'LEAKING')

    def test_refused_actions_leave_the_state_unchanged(self):
        r = sa.Run(self.sc, self.p)
        for _ in range(90):
            r.tick()
        before = r.checkpoint(), r.config()
        self.assertTrue(r.act('order', 'B', 'AC1a'))
        self.assertTrue(r.act('order', 'B', 'A2'))
        self.assertTrue(r.act('order', 'D', 'A1'))
        r.act('trainee', 'A3')
        self.assertTrue(r.act('contain_start'))
        r.act('trainee', 'A1')
        self.assertEqual(before[0]['c'], r.checkpoint()['c'])
        self.assertEqual(before[1], r.config())

    def test_a_door_cannot_close_on_a_pair_in_its_doorway(self):
        log = self.runs['doorway'][0].log
        closes = [e for e in log if e[1] == 'door' and e[2] == ['CIRC.A1P', False]]
        self.assertIn('occupied', closes[0][3])
        self.assertEqual(closes[1][3], '')

    def test_pairs_walk_door_routes_at_the_transit_time(self):
        r = sa.Run(self.sc, self.p)
        r.act('order', 'B', 'A1')
        self.assertEqual([r.ids[n] for n in r.people[2]['route']], ['AC1b', 'AC1a', 'A1'])
        for _ in range(13):                            # the arrival at 120 s applies at the boundary that starts the 13th step
            r.tick()
        q = r.people[2]
        self.assertEqual([round(t) for t, _ in q['places']], [0, 40, 80, 120])
        self.assertEqual(r.ids[q['node']], 'A1')
        self.assertEqual(r.st['occupants'][r.I['A1']], 4)
        # the trainee's partner moves, the trainee does not
        r.act('order', 'A', 'A3')
        self.assertEqual(r.people[0]['route'], [])
        self.assertTrue(r.people[1]['route'])

    def test_every_route_step_crosses_a_door(self):
        r = sa.Run(self.sc, self.p)
        for a in range(r.N):
            for b in range(r.N):
                path = r.route(a, b)
                for u, v in zip(path, path[1:]):
                    self.assertTrue(r.door_between(u, v))

    # ---- the model's numbers ------------------------------------------------------------------------------------------------------------

    def test_every_species_keeps_its_ledger(self):
        for name, (r, _, _) in self.runs.items():
            L = r.ledgers()
            scale = 1e-10*r.st['S0']                       # the model's own ledger tolerance (tests/test_ring_air_nh3.py)
            self.assertLess(abs(L['nh3_kg']), 1e-15 + scale, name)
            self.assertLess(abs(L['release_kg']), 1e-15 + scale, name)
            self.assertLess(abs(L['co2_kg']), 1e-9, name)
            d = r.debrief()
            self.assertAlmostEqual(d['released_g'] + d['retained_g'], d['inventory_g'], delta=1e-9)
            self.assertAlmostEqual(d['airborne_g'] + d['removed_g'], d['released_g'], delta=1e-9)

    def test_rolling_one_hour_mean_matches_the_exposure_windows(self):
        for name in ('isolate', 'late_containment', 'separate'):
            r = self.runs[name][0]
            for q in r.people:
                self.assertAlmostEqual(q['max1h'], ax.window_max(q['t'], q['Es'], 3600.0)[0], delta=1e-9)
                self.assertAlmostEqual(q['max24'], ax.window_max(q['t'], q['Es'], 24*3600.0)[0], delta=1e-9)

    def test_the_exposure_is_the_models_compartment_integral(self):
        r = self.runs['watch_none'][0]
        for q in r.people:
            if len(q['places']) == 1:
                self.assertAlmostEqual(q['E'], ra.exposure_ppm_s(r.st, self.p, q['node']), delta=1e-6)

    # ---- the watch ----------------------------------------------------------------------------------------------------------------------

    def test_the_watch_without_a_plan_changes_nothing(self):
        r = self.runs['watch_none'][0]
        self.assertEqual(r.watch['config'], {k: v for k, v in r.config().items()})
        self.assertFalse([e for e in r.log if e[0] > r.watch['t0'] and e[1] not in ('contained',)])
        self.assertGreaterEqual(r.watch['end_s'], 24*3600.0)
        self.assertAlmostEqual(r.t, 168*3600.0)

    def test_the_restore_plan_runs_only_its_declared_actions(self):
        r = self.runs['watch_restore'][0]
        after = [e for e in r.log if e[0] > r.watch['t0']]
        self.assertEqual({e[1] for e in after}, {'restore', 'home'})
        self.assertEqual(next(e for e in after if e[1] == 'restore')[0], r.watch['end_s'])
        reuse = self.sc['reuse']['ppm']
        d = r.debrief()
        for e in after:
            if e[1] == 'home':
                self.assertGreaterEqual(e[0], d['clear_h']['A1']*3600.0 - 1e-6)
        self.assertLessEqual(ra.ppm(r.st, self.p, r.I['A1']), reuse)

    def test_a_sealed_group_without_co2_removal_is_never_called_stable(self):
        self.assertEqual(self.deb('separate')['watch']['verdict']['result'], 'CO2_LIMIT')
        self.assertEqual(self.deb('vent_off')['watch']['verdict']['result'], 'CO2_LIMIT')
        self.assertEqual(self.deb('no_containment')['watch']['verdict']['result'], 'NOT_CONTAINED')
        self.assertEqual(self.deb('isolate')['watch']['verdict']['result'], 'STABLE')

    def test_trades_come_from_the_model(self):
        iso, pur, sep = self.deb('isolate'), self.deb('purge'), self.deb('separate')
        self.assertEqual((iso['watch']['family'], pur['watch']['family'], sep['watch']['family']), ('ISOLATE', 'ROUTE', 'SEPARATE'))
        # isolation keeps sector 1 out of use for the whole week; routing to the TCC clears it
        self.assertIsNone(iso['clear_h']['A1'])
        self.assertIsNotNone(pur['clear_h']['A1'])
        self.assertGreater(pur['removed_g'], iso['removed_g'])
        self.assertGreater(sum(q['co2_above_target_h'] for q in sep['people']), 0.0)
        self.assertEqual(sum(q['co2_above_target_h'] for q in iso['people']), 0.0)
        # removal off once contained: nothing more leaves the air
        r = self.runs['tcc_off'][0]
        off = next(e[0] for e in r.log if e[1] == 'tcc')
        self.assertLess(self.deb('tcc_off')['removed_g'], 0.01)
        self.assertEqual(r.st['tcc'], 'OFF')
        self.assertGreater(off, 0.0)

    def test_replay_is_exact(self):
        a, b = self.runs['isolate'][1], self.runs['replay'][1]
        self.assertEqual(a, b)
        r1, r2 = sa.play(self.sc, self.p, self.scripts['isolate'])[0], self.runs['isolate'][0]
        self.assertEqual(r1.checkpoint(), r2.checkpoint())

    def test_every_reference_case_runs(self):
        self.assertEqual(len(sa.cases()), 16)
        for n, (r, cps, _) in self.runs.items():
            self.assertEqual(r.phase, 'DONE', n)


if __name__ == '__main__':
    unittest.main()
