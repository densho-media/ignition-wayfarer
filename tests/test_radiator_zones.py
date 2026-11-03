"""Graded Thermal Blade bulkhead: physical invariants of the zoning, the construction and the gate mechanism (radiator_zones)."""
from pathlib import Path
import copy
import math
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import radiator_zones as rz

SIGMA = 5.670374419e-8
S = load()[0]


class RadiatorZones(unittest.TestCase):
    def test_check_passes(self):
        self.assertEqual(rz.check(S), [])

    def test_open_gates_forbidden_under_thrust(self):
        # three aligned notches open at 1800 K would carry more than either cool section's spare capacity
        il = rz.interlock(S)
        self.assertGreater(il['full_power_leak_W'], max(il['margins_W'].values()))
        self.assertLessEqual(il['open_leak_W'], il['open_leak_limit_W'])

    def test_interlock_temperatures(self):
        il = rz.interlock(S); secs = {x['id']: x for x in rz.placed(S)}
        self.assertEqual(il['t_open_K'], secs['WARM']['T_K'])          # open gates never move heat uphill into WARM
        self.assertLess(il['t_crew_K'], il['t_open_K'])
        q = S['radiators']['zones']['bulkhead']['interlock']
        absorbed = q['suit_eps_ir']*q['view_factor']*S['radiators']['emissivity']['value']*SIGMA*il['t_crew_K']**4
        self.assertAlmostEqual(absorbed, q['suit_alpha_solar']*q['solar_W_m2'], places=6)

    def test_closed_gate_seals(self):
        c = rz.gate_checks(S)
        for x in c['layers']:
            self.assertLess(x['door_bottom_hot_u'], x['layer_edge_u'])
            self.assertLess(x['leak_bound_fraction'], 1e-4)
        self.assertTrue(c['passage']['bridge_blocks_door'])

    def test_notch_passes_envelopes(self):
        p = rz.gate_checks(S)['passage']
        self.assertGreaterEqual(min(p['crawler_clear_w'], p['crawler_clear_top'], p['crew_clear_w'], p['crew_clear_top']), 0.0)

    def test_hub_brackets_clear_the_notches(self):
        gates = [g for g in rz.gates(S) if g['layer'] == 1]
        for a in rz.hub_bracket_angles(S):
            for g in gates:
                self.assertGreaterEqual(abs((a-g['az']+math.pi) % (2*math.pi)-math.pi), g['da'])

    def test_short_overlap_fails(self):
        s = copy.deepcopy(S); s['radiators']['zones']['bulkhead']['gate_mechanism']['overlap_m'] = 0.005
        self.assertTrue(any('overlap' in e for e in rz.check(s)))


if __name__ == '__main__':
    unittest.main()
