"""EVA-OPS-001 physical invariants of the runtime package (data/simulations/wf_eva_ops.json, src/wayfarer/eva_ops.py): the masses and
tanks the Godot runtime integrates reproduce the canonical EVA delta-v budget, every flight configuration flies on the canonical
nozzle set, the allocation tables never ask a valve for more than it has, and resupply is finite."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src/wayfarer'))
import eva_ops

PKG = json.loads((ROOT/'data/simulations/wf_eva_ops.json').read_text())


class Package(unittest.TestCase):
    def test_delta_v_matches_the_canonical_budget(self):
        for k, (got, canon) in eva_ops.parity(PKG).items():
            self.assertAlmostEqual(got, canon, delta=0.005*canon + 0.01, msg=k)

    def test_configurations_use_the_canonical_nozzles(self):
        a = PKG['allocation']
        self.assertEqual(len(a['suit_reserve']['nozzles']), 16)
        self.assertEqual(len(a['drone_free']['nozzles']), 26)
        self.assertEqual(len(a['drone_near_suit']['nozzles']), 22)
        self.assertEqual(set(a['docked']['nozzles']), set(a['drone_near_suit']['nozzles']))
        self.assertEqual(a['suit_reserve']['thrust_n'], 8.0)
        self.assertEqual(a['drone_free']['thrust_n'], 4.0)

    def test_allocation_is_physical(self):
        for key, t in PKG['allocation'].items():
            for ax, v in t['axes'].items():
                duty = v['duty_per_unit']
                self.assertTrue(all(d >= 0.0 for d in duty), (key, ax))
                if v['ok']:
                    # the largest pure value keeps every valve at or under full duty, and costs at least |F| / thrust of valve time
                    self.assertLessEqual(max(duty)*v['max'], 1.0 + 1e-4, (key, ax))     # 5-digit rounding
                    if ax[1] == 'F':
                        self.assertGreaterEqual(sum(duty)*t['thrust_n'], 1.0 - 1e-6, (key, ax))
                    self.assertLess(v['residual'], 1e-3, (key, ax))
            self.assertTrue(all(t['axes'][ax]['ok'] for ax in t['axes']), key)

    def test_resupply_is_finite(self):
        c = PKG['cartridge']; st = PKG['station']
        self.assertGreater(c['usable_kg'], 0.0)
        self.assertLess(c['usable_kg'], c['n2_kg'])
        self.assertLess(c['n2_kg'], PKG['drone']['vessels']['n2_kg'])
        self.assertIsInstance(st['cartridges'], int)
        self.assertEqual(st['drone_refill_kg'], 0)
        # the cartridge regulator wins over the suit reserve at the check valves, so the reserve is spent last
        self.assertGreater(c['regulator_pa'], PKG['suit']['reserve']['feed_pa'])

    def test_burn_presets_cannot_be_flown_off_on_cold_gas(self):
        g0 = PKG['standard_gravity_m_s2']
        pair = PKG['budget']['docked_kg']
        for k, m in PKG['modes'].items():
            if m['accel_g'] > 0.0:
                self.assertEqual(m['kind'], 'TRAINING_SIMULATION', k)
                self.assertGreater(pair*m['accel_g']*g0, 10*PKG['allocation']['docked']['axes']['+Fz']['max'], k)


if __name__ == '__main__':
    unittest.main()
