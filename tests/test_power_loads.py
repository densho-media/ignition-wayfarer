"""EPS-A load foundation and the systems registry: physical invariants only (energy, units, OPEN values, reserves, single ownership)."""
import copy
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import power_loads as pl
import systems


class PowerLoadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = load()[0]
        cls.L = pl.ledgers(cls.s)

    def mutated(self, fn):
        s = copy.deepcopy(self.s); fn(s); return pl.check(s)

    def test_model_is_consistent(self):
        self.assertEqual(pl.check(self.s), [])

    def test_energy_is_conserved_in_every_state(self):
        for sid, L in self.L.items():
            for i in range(3):
                lifted = -L['heat_W']['TANKS'][i]
                out = sum(L['heat_W'][k][i] for k in pl.LOOPS)+L['exported_W'][i]+L['stored_W'][i]
                self.assertAlmostEqual(out, L['electrical_W'][i]+lifted, delta=1e-6*max(1.0, out), msg=sid)
                self.assertGreaterEqual(lifted, 0.0)
            self.assertLessEqual(L['continuous_W'][1], L['peak_W'][1])

    def test_black_start_reserve_breakdown_is_whole(self):
        st = pl.storage(self.s)
        self.assertAlmostEqual(sum(st['reserve_breakdown_J'].values()), st['black_start_reserve_J'], delta=1.0)
        self.assertAlmostEqual(st['black_start_reserve_J']+st['ride_through_J'], st['main_usable_J'], delta=1.0)
        self.assertAlmostEqual(st['kWh']['main_usable']*3.6e6, st['main_usable_J'], delta=1.0)

    def test_proactive_burn_needs_no_heat_pump_lift(self):
        # ISSA Phase III (DR-01 working doctrine): with defense proactive in a burn the warm heat fits the WARM section, so the
        # burn heat pumps lift nothing and draw nothing
        L = self.L['HIGH_THRUST_PROACTIVE']; row = next((r for r in L['loads'] if r['id'] == 'TMS.BURN_HEAT_PUMPS'), None)
        self.assertLessEqual(L['heat_W']['WARM'][1], pl.items(self.s)['TMS.BURN_HEAT_PUMPS']['lift']['sink_W'])
        if row is not None:
            self.assertEqual(row['W'][1], 0.0)

    def test_engagement_losses_conserve_energy(self):
        e = pl.engagement(3e6, 24e6, 10.0, 600.0, 5e6, 1e9, eta_c=0.95, eta_d=0.95)
        delivered = (24e6-5e6)*10.0
        self.assertAlmostEqual(e['buffer_draw_J']*0.95, delivered, delta=1.0)
        self.assertAlmostEqual(e['storage_loss_heat_J'], e['buffer_draw_J']/0.95-delivered, delta=1.0)
        self.assertFalse(pl.engagement(3e6, 24e6, 10.0, 600.0, 5e6, 1e9, P_dis_max=1e6)['sustainable'])

    def test_heat_pumps_move_heat_without_creating_it(self):
        L = self.L['HIGH_THRUST']; it = pl.items(self.s)['TMS.BURN_HEAT_PUMPS']
        row = next(r for r in L['loads'] if r['id'] == 'TMS.BURN_HEAT_PUMPS')
        # the warm loop keeps exactly what its section rejects; the hot loop receives the lifted heat plus the pumps' work
        self.assertAlmostEqual(L['heat_W']['WARM'][1], it['lift']['sink_W'], delta=1.0)
        self.assertAlmostEqual(row['W'][1], row['lift_W'][1]*pl.pump_factor(self.s), delta=1.0)
        # plus the burn bus's own conversion loss, which sits with the drive generators on the hot loop
        l1_loss = L['by_supply_W']['L1'][1]*self.s['power']['loads']['pmad_loss_fraction'][1]
        self.assertAlmostEqual(L['heat_W']['HOT'][1], row['W'][1]+row['lift_W'][1]+l1_loss, delta=1.0)
        self.assertLessEqual(row['W'][2], it['rated_W'])
        # Carnot bound: no heat pump beats (T_hot/T_warm - 1) work per watt lifted
        a = self.s['thermal']['loops']
        self.assertGreaterEqual(pl.pump_factor(self.s), self.s['radiators']['temperature']['value']/a['warm']['temperature_K']-1.0)

    def test_exported_energy_is_not_heat_aboard(self):
        L = self.L['COAST_HV_CONTINUOUS_ACTIVE']
        optical = self.s['forward_defense']['power']['crown_normal']['optical_W']
        self.assertAlmostEqual(L['exported_W'][1]-sum(r['exported_W'][1] for r in L['loads'] if r['id'] != 'PROT.DEF_ACTIVE'), optical, delta=1.0)

    def test_open_loads_stay_open(self):
        for L in self.L.values():
            ids = {r['id'] for r in L['loads']}
            for o in L['open']:
                self.assertNotIn(o['id'], ids)
        def give_value(s):
            for it in s['power']['loads']['items']:
                if it['id'] == 'PROP.DRIVE_STANDBY':
                    it['W'] = [1.0, 2.0, 3.0]
        self.assertTrue(self.mutated(give_value))

    def test_doctrine_duty_is_never_defaulted(self):
        L = self.L['COAST_HV_TRIGGERED']
        self.assertIsNone(L['time_averaged_W'])
        self.assertIn('PROT.DEF_ACTIVE', L['param_duties'])
        I = pl.items(self.s); base = self.L['COAST_HV_PROACTIVE']
        for d in (0.0, 0.05, 1.0):
            T = pl.ledger(self.s, 'COAST_HV_TRIGGERED', {'PROT.DEF_ACTIVE': d})
            want = base['time_averaged_W'][1]+d*(I['PROT.DEF_ACTIVE']['W'][1]-I['PROT.DEF_PROACTIVE']['W'][1])*(1+self.s['power']['loads']['pmad_loss_fraction'][1])
            self.assertAlmostEqual(T['time_averaged_W'][1], want, delta=1.0)

    def test_battery_endurance_units(self):
        st = pl.storage(self.s, self.L); eta = pl.band(self.s['power']['loads']['storage']['discharge_efficiency'])
        self.assertAlmostEqual(st['main_usable_J'], 2.0e6*3600.0)
        for sid, e in st['endurance'].items():
            g = self.L[sid]['generation_W']
            self.assertAlmostEqual(e['ride_through_h'][1]*3600.0*g[1], st['ride_through_J']*eta[1], delta=1e-3*st['ride_through_J'])
        # the 800 Wh/kg figure is pack-level: the pack mass is energy / specific energy with no second packaging factor
        self.assertAlmostEqual(st['pack_mass_kg'], 2500.0)

    def test_reserves_are_protected(self):
        st = pl.storage(self.s, self.L)
        self.assertGreater(st['black_start_reserve_J'], st['pulse_J'])
        self.assertAlmostEqual(st['ride_through_J'], st['main_usable_J']-st['black_start_reserve_J'])
        self.assertTrue(self.mutated(lambda s: s['power']['storage']['main_battery'].update(usable_energy_Wh=1.0e5)))
        self.assertTrue(self.mutated(lambda s: s['power']['storage']['pulse_bank']['charge_sources'].append('SURVIVAL_RESERVE')))
        def survival_restarts(s):
            s['power']['black_start']['steps'][4]['supplied_by'] = ['SURVIVAL_RESERVE']
        self.assertTrue(self.mutated(survival_restarts))
        def survival_burns(s):
            for st_ in s['power']['loads']['states']:
                if st_['id'] == 'SURVIVAL_CREW':
                    st_['levels']['TMS.BURN_HEAT_PUMPS'] = 1
        self.assertTrue(self.mutated(survival_burns))

    def test_engagement_cycle(self):
        e = pl.engagement(3e6, 25e6, 60.0, 3600.0, 8e6, 2e9)
        self.assertAlmostEqual(e['average_W'], 3e6+22e6*60/3600)
        self.assertAlmostEqual(e['buffer_draw_J'], 17e6*60)
        self.assertAlmostEqual(e['recharge_s'], 17e6*60/5e6)
        self.assertTrue(e['sustainable'])
        self.assertFalse(pl.engagement(3e6, 25e6, 60.0, 3600.0, 8e6, 1e8)['sustainable'])       # buffer too small
        self.assertFalse(pl.engagement(3e6, 25e6, 600.0, 900.0, 4e6, 2e10)['sustainable'])      # recharge longer than the gap
        h = pl.engagement(3e6, 25e6, 60.0, 3600.0, 30e6, 0.0, P_export=5e6, Q_reject_def=10e6)
        self.assertAlmostEqual(h['heat_debt_J'], 10e6*60)
        self.assertAlmostEqual(h['thermal_recovery_s'], 10e6*60/7e6)


class RegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = load()[0]; cls.reg = systems.load()

    def test_registry_is_consistent(self):
        self.assertEqual(systems.check(self.s, self.reg), [])

    def test_single_ownership(self):
        reg = copy.deepcopy(self.reg)
        reg['system'][1]['loads'].append(reg['system'][3]['loads'][0])       # one load claimed twice
        self.assertTrue(systems.check(self.s, reg))
        reg = copy.deepcopy(self.reg); reg['system'][0]['budget_item'] = 'nowhere'
        self.assertTrue(systems.check(self.s, reg))
        reg = copy.deepcopy(self.reg); reg['system'][0]['mass_kg'] = [1.0, 2.0, 3.0]  # OPEN row with a value
        self.assertTrue(systems.check(self.s, reg))

    def test_open_mass_is_never_summed(self):
        roll = systems.rollup(self.s, self.reg)
        for b in roll.values():
            known = sum(r['mass_kg'][1] for r in self.reg['system'] if r['id'] in b['rows'])
            self.assertAlmostEqual(b['known_kg'][1], known)
            self.assertFalse(set(b['rows']) & {o['id'] for o in b['open']})


if __name__ == '__main__':
    unittest.main()
