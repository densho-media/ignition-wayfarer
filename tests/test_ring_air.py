"""SYS-002 ring A atmospheric connectivity (Deadship Phase 2A): the compartment volumes, the topology, the exact step, conservation and
the test cases A-G of the brief (fully connected; a closed door with the other way round open; closed doors with ventilation on; isolated;
reopening; occupants apart; removal in another compartment)."""
from pathlib import Path
import math
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
import cabin_air as ca
import ring_air as ra

DOORS = ['CIRC.A1P', 'CIRC.AC1', 'CIRC.A2N', 'CIRC.A2P', 'CIRC.AC2', 'CIRC.A3N', 'CIRC.A3P', 'CIRC.AC3', 'CIRC.A1N']


class RingAirTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import spec
        cls.s = spec.load()[0]
        cls.p = ra.params(cls.s)
        cls.topo = ra.topology(cls.s)
        cls.ix = {k: i for i, k in enumerate(cls.p['ids'])}

    def x(self, st, node):
        i = self.ix[node]
        return st['m'][i] / self.p['M_CO2'] / ra.n_mol(self.p, i)

    def run_for(self, st, hours, dt=10.0):
        for _ in range(int(round(hours * 3600.0 / dt))):
            ra.step(st, self.p, dt)
        return st

    def assertLedger(self, st):
        scale = st['m0'] + st['generated'] + st['removed']        # kg moved in all
        self.assertLess(abs(ra.ledger_error(st)), 1e-12 + 1e-12 * scale, ra.ledger_error(st))

    def isolated(self):
        st = ra.start(self.p)
        ra.set_vent(st, False)
        return st

    # ---- volumes and topology ----

    def test_compartments_are_the_ds1_volume_without_double_counting(self):
        V = self.p['V_m3']
        self.assertEqual(len(V), 9)
        self.assertEqual(len(set(self.p['ids'])), 9)
        self.assertAlmostEqual(sum(V), ca.volume(self.s)['value'], places=9)
        for n in self.topo['nodes']:
            self.assertLessEqual(n['V_m3'], n['gross_m3'] + 1e-9, n['id'])
            self.assertEqual(n['basis'], 'net' if n['kind'] == 'sector' else 'gross')
        for b in self.topo['boundaries']:       # the crew tubes are outside the model, sealed
            self.assertEqual((b['state'], b['modelled']), ('CLOSED', False))
            self.assertNotIn(b['outside'], self.p['ids'])

    def test_the_doors_form_one_loop_round_the_ring(self):
        doors = [e for e in self.p['edges'] if e['kind'] == 'door']
        self.assertEqual(sorted(e['id'] for e in doors), sorted(DOORS))
        degree = [0] * 9
        for e in doors:
            degree[e['i']] += 1
            degree[e['j']] += 1
        self.assertEqual(degree, [2] * 9)
        st = ra.start(self.p, doors='OPEN', vent='OFF')
        self.assertEqual(len(ra.components(st, self.p)), 1)
        imv = [e for e in self.p['edges'] if e['kind'] == 'imv']
        self.assertEqual(sorted((e['i'], e['j']) for e in imv), sorted((e['i'], e['j']) for e in doors))

    def test_the_doorway_exchange_follows_its_formula(self):
        door = next(e for e in self.topo['edges'] if e['kind'] == 'door')
        import habitat_ring
        g = habitat_ring.floor_gravity_g(self.s) * ra.G0
        want = 0.6 / 3.0 * door['width_m'] * door['height_m'] * math.sqrt(g * door['height_m'] * 0.5 / ca.PROTOTYPE['temperature_K']['value'])
        self.assertAlmostEqual(ra.door_flow(self.s, door), want, places=12)
        self.assertGreater(want, 0.0)

    # ---- the step ----

    def test_the_step_is_exact_whatever_its_length(self):
        out = []
        for dt in (1.0, 10.0, 600.0, 3600.0):
            st = self.isolated()
            ra.set_edge(st, 'CIRC.A2N', True)
            out.append(self.run_for(st, 3.0, dt)['m'])
        for m in out[1:]:
            for a, b in zip(m, out[0]):
                self.assertLess(abs(a - b), 1e-12 + 1e-10 * abs(b))

    def test_the_reference_run_conserves_and_stays_non_negative(self):
        st = ra.start(self.p); events = list(ra.PROOF_EVENTS)
        for i in range(3600):
            while events and st['t_s'] >= events[0][0] - 1e-9:
                ra.apply(st, events.pop(0))
            ra.step(st, self.p, 10.0)
            self.assertTrue(all(m >= 0.0 for m in st['m']))
        self.assertLedger(st)
        cp = ra.checkpoints(self.p)
        self.assertEqual(len(cp), 11)
        self.assertEqual(cp[-1]['m'], st['m'])

    def test_from_zero_co2_nothing_goes_negative(self):
        st = ra.start(self.p, x0=0.0, doors='OPEN')
        for dt in (1.0, 3600.0, 36000.0):
            ra.step(st, self.p, dt)
            self.assertTrue(all(m >= 0.0 for m in st['m']), st['m'])
        self.assertLedger(st)

    # ---- cases A-G ----

    def test_A_fully_connected_settles_with_removal_balancing_generation(self):
        st = ra.steady(ra.start(self.p, doors='OPEN'), self.p)
        r = ra.readout(st, self.p)
        G = 6 * self.p['per_person_kg_s']
        k = self.p['k_m3_s']
        # at steady state the unit removes exactly the generation, so its compartment holds G / k: the well-mixed value
        self.assertAlmostEqual(self.x(st, 'A3'), self.p['well_mixed_x'], delta=1e-9)
        self.assertTrue(all(q['x'] >= self.p['well_mixed_x'] - 1e-12 for q in r['nodes']))
        self.assertTrue(all(abs(q['dxdt_per_h']) < 1e-9 for q in r['nodes']))
        self.assertEqual(r['groups'], 1)
        self.assertAlmostEqual(k * st['m'][self.ix['A3']] / self.p['V_m3'][self.ix['A3']], G, delta=1e-15)
        self.assertLedger(st)

    def test_B_a_closed_door_with_the_other_way_open_still_connects(self):
        st = ra.start(self.p, doors='OPEN', vent='OFF', removal='OFF')
        ra.set_edge(st, 'CIRC.AC1', False)      # the node door between AC1a and AC1b
        self.assertEqual(len(ra.components(st, self.p)), 1)
        ra.set_occupants(st, [0] * 9)
        st['m'][self.ix['AC1a']] *= 2.0          # a pulse on one side of the closed door
        st['m0'] = sum(st['m'])
        before = self.x(st, 'AC1b')
        direct = ra.start(self.p, doors='OPEN', vent='OFF', removal='OFF')
        ra.set_occupants(direct, [0] * 9)
        direct['m'][self.ix['AC1a']] *= 2.0
        direct['m0'] = sum(direct['m'])
        self.run_for(direct, 0.5)
        self.run_for(st, 0.5)
        self.assertGreater(self.x(direct, 'AC1b') - before, 100.0 * (self.x(st, 'AC1b') - before))   # connected is not well mixed
        self.run_for(st, 5.5)
        self.assertGreater(self.x(st, 'AC1b'), before + 1e-5)      # but it arrives the long way round, through eight doors
        self.assertLedger(st)

    def test_C_closed_doors_with_ventilation_on_still_exchange(self):
        st = ra.start(self.p)                    # doors closed (normally closed), ventilation on
        self.assertTrue(all(not v for k, v in st['open'].items() if k.startswith('CIRC.')))
        self.assertEqual(len(ra.components(st, self.p)), 1)
        ra.set_occupants(st, [0] * 9)
        ra.set_removal(st, False)
        st['m'][self.ix['A1']] *= 3.0
        st['m0'] = sum(st['m'])
        before = self.x(st, 'AC1a')
        self.run_for(st, 1.0)
        self.assertGreater(self.x(st, 'AC1a'), before + 1e-5)
        self.assertLedger(st)

    def test_D_closed_doors_and_ventilation_off_isolate_every_compartment(self):
        st = self.isolated()
        self.assertEqual(len(ra.components(st, self.p)), 9)
        m0 = list(st['m'])
        self.run_for(st, 4.0, dt=60.0)
        g = self.p['per_person_kg_s'] * 4 * 3600.0
        for k in ('AC1a', 'AC1b', 'AC2a', 'AC2b', 'AC3a', 'AC3b'):
            self.assertEqual(st['m'][self.ix[k]], m0[self.ix[k]], k)               # sealed and empty: not a molecule moves
        for k in ('A1', 'A2'):
            self.assertAlmostEqual(st['m'][self.ix[k]], m0[self.ix[k]] + 2 * g, delta=1e-12)   # the linear rise, nothing removes it
        self.assertLess(self.x(st, 'A3'), self.x(st, 'A1'))
        r = ra.readout(st, self.p)
        self.assertTrue(all(q['isolated'] for q in r['nodes']))
        self.assertEqual([q['removal_reaches'] for q in r['nodes']], [k == 'A3' for k in self.p['ids']])
        self.assertLedger(st)

    def test_E_reopening_a_door_joins_two_compartments_gradually(self):
        st = self.run_for(self.isolated(), 2.0)
        gap0 = self.x(st, 'A2') - self.x(st, 'AC1b')
        self.assertGreater(gap0, 1e-4)
        ra.set_edge(st, 'CIRC.A2N', True)
        self.assertEqual(len(ra.components(st, self.p)), 8)
        ra.step(st, self.p, 10.0)
        gap1 = self.x(st, 'A2') - self.x(st, 'AC1b')
        self.assertLess(gap1, gap0)
        self.assertGreater(gap1, 0.9 * gap0)                    # not instant: 10 s against a V / Q of several minutes
        self.run_for(st, 2.0)
        self.assertLess(self.x(st, 'A2') - self.x(st, 'AC1b'), 0.25 * gap0)
        ra.set_edge(st, 'CIRC.A2N', False)                    # closed again: isolated again
        self.assertEqual(len(ra.components(st, self.p)), 9)
        self.assertLedger(st)

    def test_F_occupants_apart_make_a_gradient_along_the_path(self):
        st = ra.start(self.p)
        ra.set_occupants(st, [6, 0, 0, 0, 0, 0, 0, 0, 0])
        ra.steady(st, self.p)
        # A1 -> AC1a -> AC1b -> A2 one way and A1 -> AC3b -> AC3a -> A3 the other; the unit in A3 is the sink
        self.assertGreater(self.x(st, 'A1'), self.x(st, 'AC3b'))
        self.assertGreater(self.x(st, 'AC3b'), self.x(st, 'AC3a'))
        self.assertGreater(self.x(st, 'AC3a'), self.x(st, 'A3'))
        self.assertAlmostEqual(self.x(st, 'A3'), self.p['well_mixed_x'], delta=1e-9)
        self.assertLedger(st)

    def test_G_removal_in_another_compartment_needs_a_connection(self):
        st = self.isolated()
        ra.set_occupants(st, [6, 0, 0, 0, 0, 0, 0, 0, 0])
        self.run_for(st, 1.0)
        self.assertLess(st['removed'], st['m0'])                # A3 sheds only what it held; A1's CO2 never reaches it
        a1 = self.x(st, 'A1')
        removed_before = st['removed']
        ra.set_vent(st, True)                                   # connect through the ventilation
        self.run_for(st, 6.0)
        self.assertLess(self.x(st, 'A1'), a1)
        self.assertGreater(st['removed'] - removed_before, 0.0)
        self.assertLedger(st)

    def test_ds1_stays_on_its_well_mixed_volume(self):
        gap = ra.well_mixed_gap(self.p)
        self.assertAlmostEqual(gap['min_x'], ca.steady_x(ca.params(self.s)), delta=1e-9)   # the unit's own compartment
        self.assertEqual(gap['min_id'], 'A3')
        self.assertLess(gap['max_x'], self.p['co2_target'])     # every compartment stays below the target in DS-1's configuration


if __name__ == '__main__':
    unittest.main()
