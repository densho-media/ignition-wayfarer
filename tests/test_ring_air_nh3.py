"""SYS-002 v2: ammonia (NH3) as a second, trace species in ring A's compartment model. Transport, the finite source, the separate
trace-contaminant sink, conservation of each species, units, exact exposure integrals and the exposure-duration windows."""
from pathlib import Path
import math
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
import air_exposure as ax
import ring_air as ra

S0 = 0.007          # kg: a test inventory (not a scenario value)
TAU = 3600.0


class RingAirNH3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import spec
        cls.s = spec.load()[0]
        cls.p = ra.params(cls.s)
        cls.ix = {k: i for i, k in enumerate(cls.p['ids'])}
        cls.N = len(cls.p['ids'])

    def run_for(self, st, hours, dt=60.0):
        for _ in range(int(round(hours * 3600.0 / dt))):
            ra.step(st, self.p, dt)
        return st

    def sealed(self, tcc=True):
        st = ra.start(self.p)
        ra.set_vent(st, False)
        ra.set_tcc(st, tcc)
        return st

    def assertConserved(self, st):
        scale = st['S0'] + st['c0']
        self.assertLess(abs(ra.trace_ledger_error(st)), 1e-15 + 1e-10 * scale, ra.trace_ledger_error(st))
        self.assertLess(abs(ra.release_ledger_error(st)), 1e-15 + 1e-10 * scale, ra.release_ledger_error(st))
        self.assertLess(abs(ra.ledger_error(st)), 1e-12 + 1e-12 * (st['m0'] + st['generated'] + st['removed']))

    def others_zero(self, st, keep):
        for k, i in self.ix.items():
            if k not in keep:
                self.assertEqual(st['c'][i], 0.0, k)

    # ---- transport ----

    def test_release_into_an_isolated_compartment_stays_there(self):
        st = self.sealed()
        ra.set_source(st, self.p, 'A1', S0, TAU)
        self.run_for(st, 3.0)
        self.others_zero(st, {'A1'})
        a1 = self.ix['A1']
        self.assertAlmostEqual(st['c'][a1], S0 * (1.0 - math.exp(-3.0 * 3600.0 / TAU)), delta=1e-14)
        self.assertConserved(st)

    def test_an_open_door_carries_it_to_the_next_compartment_only(self):
        st = self.sealed()
        ra.set_edge(st, 'CIRC.A1P', True)
        ra.set_source(st, self.p, 'A1', S0, TAU)
        self.run_for(st, 2.0)
        self.others_zero(st, {'A1', 'AC1a'})
        self.assertGreater(st['c'][self.ix['AC1a']], 0.0)
        self.assertGreater(ra.ppm(st, self.p, self.ix['A1']), ra.ppm(st, self.p, self.ix['AC1a']))   # gradual, not instant
        self.assertConserved(st)

    def test_ventilation_spreads_it_with_every_door_closed(self):
        st = ra.start(self.p)
        ra.set_source(st, self.p, 'A1', S0, TAU)
        self.run_for(st, 2.0)
        for k, i in self.ix.items():
            self.assertGreater(st['c'][i], 0.0, k)
        self.assertConserved(st)

    def test_closing_a_compartments_doors_and_dampers_confines_it(self):
        st = ra.start(self.p)
        for e in ('CIRC.A1P', 'CIRC.A1N', 'IMV.A1P', 'IMV.A1N'):
            ra.set_edge(st, e, False)
        ra.set_source(st, self.p, 'A1', S0, TAU)
        self.run_for(st, 2.0)
        self.others_zero(st, {'A1'})
        self.assertConserved(st)

    def test_both_species_ride_the_same_flows(self):
        """With the same initial pattern and no sources or sinks, CO2's excess and NH3 redistribute identically."""
        st = ra.start(self.p, x0=0.0)
        ra.set_removal(st, False); ra.set_tcc(st, False); ra.set_occupants(st, [0] * self.N)
        ra.set_edge(st, 'CIRC.A1P', True); ra.set_vent(st, False)
        a1 = self.ix['A1']
        st['m'][a1] = 0.01; st['m0'] = 0.01
        st['c'][a1] = 0.01; st['c0'] = 0.01
        self.run_for(st, 1.5)
        for i in range(self.N):
            self.assertAlmostEqual(st['m'][i], st['c'][i], delta=1e-12 * 0.01)

    # ---- sources and sinks ----

    def test_the_tcc_removes_it_at_its_own_flow(self):
        st = self.sealed()
        a3 = self.ix['A3']
        st['c'][a3] = 0.002; st['c0'] = 0.002
        self.run_for(st, 4.0)
        k = self.p['tcc_k_m3_s'] / self.p['V_m3'][a3]
        self.assertAlmostEqual(st['c'][a3], 0.002 * math.exp(-k * 4.0 * 3600.0), delta=1e-15)
        self.assertAlmostEqual(st['nh3_removed'], 0.002 - st['c'][a3], delta=1e-15)
        self.assertConserved(st)

    def test_the_tcc_reaches_only_what_is_connected_to_it(self):
        st = self.sealed()
        ra.set_source(st, self.p, 'A1', S0, TAU)
        self.run_for(st, 6.0)
        self.assertEqual(st['nh3_removed'], 0.0)

    def test_co2_and_nh3_removal_are_independent(self):
        def pair(co2_unit, tcc):
            st = ra.start(self.p)
            ra.set_removal(st, co2_unit); ra.set_tcc(st, tcc)
            ra.set_source(st, self.p, 'A2', S0, TAU)
            self.run_for(st, 5.0)
            return st
        ref = pair(True, True)
        no_co2_unit = pair(False, True)
        no_tcc = pair(True, False)
        self.assertEqual(no_co2_unit['c'], ref['c'])           # NH3 does not see the CO2 unit
        self.assertEqual(no_co2_unit['nh3_removed'], ref['nh3_removed'])
        self.assertEqual(no_tcc['m'], ref['m'])                 # CO2 does not see the TCC
        self.assertEqual(no_tcc['nh3_removed'], 0.0)
        self.assertGreater(no_co2_unit['m'][self.ix['A3']], ref['m'][self.ix['A3']])

    def test_a_release_does_not_change_the_co2_equations(self):
        a = ra.start(self.p); b = ra.start(self.p)
        ra.set_source(b, self.p, 'A1', S0, TAU)
        for st in (a, b):
            ra.set_vent(st, False); ra.set_edge(st, 'CIRC.A3P', True)
            self.run_for(st, 3.0)
        self.assertEqual(a['m'], b['m'])
        self.assertEqual((a['generated'], a['removed']), (b['generated'], b['removed']))

    def test_the_source_runs_out_and_never_goes_negative(self):
        st = self.sealed()
        ra.set_source(st, self.p, 'A1', S0, 600.0)
        for _ in range(48):
            ra.step(st, self.p, 3600.0)
            self.assertGreaterEqual(st['S'], 0.0)
            self.assertTrue(all(v >= -1e-18 for v in st['c']))
        self.assertLess(st['S'], 1e-15)
        self.assertAlmostEqual(st['released'], S0, delta=1e-15)
        self.assertConserved(st)

    def test_isolating_the_source_stops_the_release_and_keeps_its_rest(self):
        st = self.sealed()
        ra.set_source(st, self.p, 'A1', S0, TAU)
        self.run_for(st, 1.0)
        ra.isolate_source(st)
        held, out = st['S'], st['released']
        self.run_for(st, 5.0)
        self.assertEqual(st['source']['state'], 'ISOLATED')
        self.assertEqual((st['S'], st['released']), (held, out))
        self.assertAlmostEqual(held, S0 * math.exp(-1.0), delta=1e-14)
        self.assertConserved(st)

    def test_no_source_and_an_empty_source_cost_nothing(self):
        st = ra.start(self.p)
        self.run_for(st, 2.0)
        self.assertFalse(ra.trace_active(st))
        self.assertEqual((sum(st['c']), st['S'], sum(st['I'])), (0.0, 0.0, 0.0))
        ra.set_source(st, self.p, 'A2', 0.0, TAU)
        self.assertEqual(st['source']['state'], 'NONE')
        self.run_for(st, 1.0)
        self.assertEqual(sum(st['c']), 0.0)
        with self.assertRaises(ValueError):
            ra.set_source(st, self.p, 'A2', -1.0, TAU)
        with self.assertRaises(ValueError):
            ra.set_source(st, self.p, 'A2', S0, 0.0)

    # ---- numerics ----

    def test_each_species_is_conserved_through_every_kind_of_change(self):
        st = ra.start(self.p)
        ra.set_source(st, self.p, 'A1', S0, TAU)
        for ev, h in ((lambda: ra.set_vent(st, False), 0.5), (lambda: ra.set_edge(st, 'CIRC.A1N', True), 1.0),
                      (lambda: ra.set_occupants(st, [0, 3, 3, 0, 0, 0, 0, 0, 0]), 1.0), (lambda: ra.isolate_source(st), 2.0),
                      (lambda: ra.set_tcc(st, False), 1.0), (lambda: ra.set_vent(st, True), 3.0)):
            ev()
            self.run_for(st, h, dt=30.0)
            self.assertConserved(st)
            self.assertTrue(all(v >= -1e-18 for v in st['c']))

    def test_the_step_length_does_not_change_the_result(self):
        def run(dt):
            st = ra.start(self.p)
            ra.set_vent(st, False); ra.set_edge(st, 'CIRC.A1N', True); ra.set_edge(st, 'CIRC.AC3', True)
            ra.set_source(st, self.p, 'A1', S0, TAU)
            self.run_for(st, 6.0, dt)
            return st
        a, b, c = run(10.0), run(60.0), run(600.0)
        for x in (b, c):
            for i in range(self.N):
                self.assertAlmostEqual(a['c'][i], x['c'][i], delta=1e-11 * S0)
                self.assertAlmostEqual(a['I'][i], x['I'][i], delta=1e-10 * S0 * 3600.0)
            self.assertAlmostEqual(a['nh3_removed'], x['nh3_removed'], delta=1e-11 * S0)

    def test_thirty_days_stay_stable_and_the_tcc_clears_the_ring(self):
        st = ra.start(self.p)
        ra.set_source(st, self.p, 'A1', S0, TAU)
        for _ in range(30 * 24):
            ra.step(st, self.p, 3600.0)
        self.assertTrue(all(math.isfinite(v) and v >= -1e-18 for v in st['c']))
        self.assertLess(max(ra.ppm(st, self.p, i) for i in range(self.N)), 0.01)
        self.assertConserved(st)

    def test_the_proof_run_is_reproducible(self):
        a = ra.trace_checkpoints(self.p); b = ra.trace_checkpoints(self.p)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 11)

    # ---- units and exposure ----

    def test_units_are_kept_apart_and_agree(self):
        st = self.sealed()
        ra.set_source(st, self.p, 'A1', S0, TAU)
        self.run_for(st, 2.0)
        i = self.ix['A1']
        u = ra.trace_units(st, self.p, i)
        self.assertAlmostEqual(u['x'], u['mol_m3'] * self.p['R'] * self.p['T_K'] / self.p['P_Pa'], delta=1e-15)
        self.assertAlmostEqual(u['ppm'], u['x'] * 1e6, delta=1e-9)
        self.assertAlmostEqual(u['pp_Pa'], u['x'] * self.p['P_Pa'], delta=1e-12)
        self.assertAlmostEqual(u['kg'], u['mol_m3'] * self.p['V_m3'][i] * ra.M_NH3, delta=1e-15)

    def test_the_exposure_integral_is_exact(self):
        st = self.sealed()
        ra.set_source(st, self.p, 'A1', S0, TAU)
        t = 5.0 * 3600.0
        self.run_for(st, 5.0, dt=900.0)
        i = self.ix['A1']
        want = S0 * (t - TAU * (1.0 - math.exp(-t / TAU)))      # integral of S0 (1 - exp(-t / tau)) dt
        self.assertAlmostEqual(st['I'][i], want, delta=1e-12 * want)

    def test_a_person_is_exposed_only_where_they_are(self):
        st = self.sealed()
        ra.set_edge(st, 'CIRC.A1P', True)
        ra.set_source(st, self.p, 'A1', S0, TAU)
        i1, i2 = self.ix['A1'], self.ix['A2']
        a, b = ax.Track('a', i1), ax.Track('b', i2)
        X = lambda: [ra.exposure_ppm_s(st, self.p, k) for k in range(self.N)]
        P = lambda: [ra.ppm(st, self.p, k) for k in range(self.N)]
        for tr in (a, b):
            tr.begin(X(), P())
        at_move = None
        for k in range(120):
            ra.step(st, self.p, 60.0)
            for tr in (a, b):
                tr.sample(st['t_s'], X(), P())
            if k == 59:
                at_move = X()[i1]
                a.move(st['t_s'], i2, X(), P())            # a leaves for sealed A2 after an hour
        self.assertEqual(b.E[-1], 0.0)                     # b never left clean, sealed A2
        self.assertAlmostEqual(a.E[60], at_move, delta=1e-9 * at_move)   # a's first hour is A1's integral over that hour
        self.assertEqual(a.E[-1], a.E[60])                 # nothing more once in clean air
        self.assertGreater(X()[i1], at_move)               # while A1 kept accumulating

    def test_duration_windows_are_time_weighted_not_instantaneous(self):
        smac = ra.NH3_SMAC['value_ppm']
        tr = ax.Track('x', 0)
        tr.t = [k * 60.0 for k in range(0, 25 * 60 + 1)]
        # 60 ppm for 30 min, then clean: a peak above the 1 h value, but a 1 h mean of exactly 30 ppm
        tr.ppm = [60.0 if t < 1800.0 else 0.0 for t in tr.t]
        E = [0.0]
        for k in range(1, len(tr.t)):
            E.append(E[-1] + tr.ppm[k - 1] * 60.0)
        tr.E = E
        a = ax.assess(tr, smac)
        self.assertEqual(a['peak_ppm'], 60.0)
        self.assertAlmostEqual(a['max_1h_ppm'], 30.0, delta=1e-9)
        self.assertAlmostEqual(a['max_24h_ppm'], 30.0 * 3600.0 / 86400.0 * 1.0 / 1.0 * 1.0, delta=1e-9)
        self.assertTrue(a['complete_24h'])
        short = ax.Track('y', 0)
        short.t, short.E, short.ppm = tr.t[:12 * 60 + 1], tr.E[:12 * 60 + 1], tr.ppm[:12 * 60 + 1]
        self.assertFalse(ax.assess(short, smac)['complete_24h'])     # 12 h cannot judge a 24 h value
        self.assertIsNone(ax.assess(short, smac)['max_24h_ppm'])

    def test_the_reference_values_are_rev_d(self):
        v = ra.NH3_SMAC['value_ppm']
        self.assertEqual((v['1h'], v['24h'], v['7d'], v['1000d']), (30.0, 20.0, 3.0, 3.0))
        self.assertIn('JSC 20584 Rev D', ra.NH3_SMAC['reference'])


if __name__ == '__main__':
    unittest.main()
