"""Ring services (SYS-003): each ring's cabin heat, water vapour and CO2 with its cooling chain, the buses and stores that power it, and
the parts its machines need. Every inventory closes, a temperature changes only through a heat flow, a part is in one place only and
fits only its own family, a bus that is asked for more than it can supply trips, and the survival packs carry only survival loads."""
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
import life_support   # noqa: E402
import ring_services as rs   # noqa: E402
import spec   # noqa: E402


def run(st, p, hours, dt=60.0):
    for _ in range(int(round(hours*3600.0/dt))):
        rs.step(st, p, dt)
    return st


class RingServicesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = rs.params(spec.load(ROOT)[0], life_support.load(ROOT))

    def close(self, st):
        for k, v in rs.ledgers(st, self.p).items():
            scale = 1e3 if k.endswith('_J') else 1e-9
            self.assertLess(abs(v), scale, k)

    def test_normal_ring_holds_in_band(self):
        st = run(rs.start(self.p), self.p, 24)
        a = st['ring']['A']
        self.assertLess(abs(a['T'] - self.p['T_set']), 1.5)
        self.assertTrue(self.p['rh_min'] - 0.05 < rs.rh(self.p, a['T'], a['m_w']) < self.p['rh_max'])
        self.assertLess(rs.x_co2(self.p, a['T'], a['m_c']), self.p['co2_target'])
        self.close(st)

    def test_co2_fan_failure_rises_to_the_limit(self):
        st = rs.start(self.p); rs.fail_part(st, 'A.CO2.FAN')
        run(st, self.p, 12)
        a = st['ring']['A']
        self.assertGreater(rs.x_co2(self.p, a['T'], a['m_c']), self.p['co2_max'])
        self.close(st)

    def test_pump_failure_warms_the_cabin(self):
        st = rs.start(self.p); rs.fail_part(st, 'A.P1.PUMP')
        run(st, self.p, 24)
        self.assertGreater(st['ring']['A']['T'], self.p['T_max'])
        self.close(st)

    def test_no_temperature_change_without_a_flow(self):
        st = rs.start(self.p, occupants={'A': 0, 'B': 0})
        for r in rs.RINGS:
            for e in self.p['equipment']:
                rs.set_on(st, r, e['id'], False)
        T0 = {r: st['ring'][r]['T'] for r in rs.RINGS}
        run(st, self.p, 6)
        for r in rs.RINGS:
            self.assertAlmostEqual(st['ring'][r]['T'], T0[r], places=9)
        self.close(st)

    def test_condensate_only_when_the_coil_is_below_the_dew_point(self):
        st = rs.start(self.p)
        a = st['ring']['A']
        wet = rs.coil(self.p, a['T'], a['m_w'], True, 2, True)
        self.assertGreater(wet['cond'], 0.0)
        dry = rs.coil(self.p, a['T'], rs.m_w_at(self.p, a['T'], 0.05), True, 2, True)
        self.assertEqual(dry['cond'], 0.0)
        self.assertEqual(rs.coil(self.p, a['T'], a['m_w'], False, 2, True)['Q_s'], 0.0)

    def test_parts_one_place_and_compatible(self):
        st = rs.start(self.p)
        self.assertIn('does not fit', rs.move_part(st, 'A.P1.PUMP', 'A.CO2.FAN'))
        self.assertIn('already holds', rs.move_part(st, 'A.CHX.FAN', 'A.CO2.FAN'))
        self.assertEqual(rs.move_part(st, 'B.CO2.FAN', 'CARRY.B'), '')
        self.assertFalse(rs.slot_ok(st, 'B.CO2.FAN'))
        self.assertEqual(rs.move_part(st, 'A.CO2.FAN', 'A.SHELF'), '')
        self.assertEqual(rs.move_part(st, 'B.CO2.FAN', 'A.CO2.FAN'), '')
        self.assertTrue(rs.slot_ok(st, 'A.CO2.FAN'))
        places = [q['at'] for q in st['parts'].values()]
        self.assertEqual(len(places), len(set(places)))
        self.assertEqual(rs.ledgers(st, self.p)['parts'], 0)

    def test_overload_trips_and_packs_carry_only_survival_loads(self):
        st = rs.start(self.p)
        rs.set_fusion(st, False); rs.fail_part(st, 'BC-B')
        rs.step(st, self.p, 10.0)
        run_b = st['plan']['run']['A']
        self.assertFalse(st['plan']['live']['B'])
        self.assertEqual(run_b['CHX'], 'PACK')
        self.assertEqual(run_b['GARDEN'], 'DARK')
        rs.set_tie(st, True)
        rs.reset_breaker(st, 'B')
        rs.step(st, self.p, 10.0)
        self.assertFalse(st['breaker']['A'])      # 40 kW cannot carry both buses with every load on
        self.assertTrue(st['trips'])
        run(st, self.p, 12)
        self.assertEqual(st['pack']['A'], 0.0)
        self.assertGreater(st['acc']['E_unserved'], 0.0)
        self.close(st)

    def test_proof_is_deterministic(self):
        a = rs.checkpoints(self.p, dt=60.0)
        b = rs.checkpoints(self.p, dt=60.0)
        self.assertEqual(a, b)


if __name__ == '__main__':
    unittest.main()
