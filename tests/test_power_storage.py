"""P1-007 layered storage and black start: sourced values, owner rules, OPEN sizing and PROTOTYPE placement."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load, validate
import power_storage as ps
import sim_rig


class PowerStorageTests(unittest.TestCase):
    def setUp(self):
        self.s,self.sources,self.spec_text,self.source_text=load()

    def failures(self,mutate):
        s=copy.deepcopy(self.s);mutate(s)
        return ps.check(s)['failures']


    def test_energy_and_units(self):
        q=ps.quantities(self.s)
        self.assertAlmostEqual(q['main_usable_energy_J'],7.2e9)
        self.assertAlmostEqual(q['pulse_energy_J'],7.2e8)
        # 200 kWh at 50 MW empties in 14.4 s; the 2 MWh battery holds ten full pulse-bank charges.
        self.assertAlmostEqual(q['pulse_full_discharge_at_rated_power_s'],14.4)
        self.assertAlmostEqual(q['pulse_charges_per_main_battery'],10.0)
        self.assertAlmostEqual(q['main_battery_extrapolated_pack_mass_kg'],2500.0)
        self.assertTrue(self.failures(lambda s:s['power']['storage']['main_battery'].update(usable_energy_Wh=2000.0)))  # kWh typed as Wh
        self.assertTrue(self.failures(lambda s:s['power']['storage']['pulse_bank'].update(power_W=50.0)))              # MW typed as W

    def test_survival_power_is_not_restart_power(self):
        self.assertTrue(self.failures(lambda s:s['power']['storage']['pulse_bank']['charge_sources'].append('SURVIVAL_RESERVE')))
        def survival_charges(s):
            s['power']['black_start']['steps'][1]['supplied_by']=['SURVIVAL_RESERVE']
        self.assertTrue(self.failures(survival_charges))
        self.assertTrue(self.failures(lambda s:s['power']['storage']['rules'].update(survival_power_implies_restart=True)))
        caps=sim_rig.contract(self.s,self.spec_text,self.source_text)['power']['capabilities']
        self.assertFalse(caps['survival_power']['can_restart_fusion'])
        self.assertNotIn('SURVIVAL_RESERVE',caps['restart_capability']['requires']+caps['restart_capability']['pulse_charge_sources'])


    def test_mass_stays_inside_the_existing_allowance(self):
        item=ps.mass_allowance(self.s)
        self.assertEqual(item['id'],'power_computers_steering_comms');self.assertEqual(item['mass_kg'],50000.0)
        self.assertEqual(item.get('rotating_allowance_kg',0),0)
        # A separate storage mass line would break the sourced 1,100 t burnout sum.
        s=copy.deepcopy(self.s);s['physics']['mass_budget']['items'].append({'id':'storage','label':'Storage','mass_kg':2500.0})
        with self.assertRaises(ValueError):validate(s,self.sources)


if __name__=='__main__':
    unittest.main()
