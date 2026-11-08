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


class MagneticWalkway(unittest.TestCase):
    """LOCO-002 interfaces of the PROTOTYPE magnetic-boot walkway: it lies on the hull collar, a walker on it stays clear of the airlock
    fitting, the Brow truss and every keep-out, the gait always keeps a boot down, and the start is on the plate within tether reach."""
    M = PKG['mag_boots']
    R = PKG['ship']['route']

    def test_walkway_on_the_collar_clear_of_the_fitting_and_truss(self):
        import math
        m, r = self.M, self.R
        xs = [x for x, _ in r['collider']['samples']]
        self.assertTrue(min(xs) <= m['walkway_x_m'][0] < m['walkway_x_m'][1] <= max(xs))
        f = r['collider']['fitting']
        phi_rail = math.atan2(r['rail_up'][2], r['rail_up'][1])
        arc = min(abs(p - phi_rail) for p in m['walkway_phi_rad']) * m['surface_r_m']
        body = 0.32                                          # the suit capsule radius in the runtime (eva_ops.gd)
        self.assertGreater(arc - body, f['radius_m'])        # a walker at the walkway's near edge clears the hatch fitting
        truss = min(min(a[0], b[0]) for a, b in PKG['ship']['shield']['truss_segments'])
        self.assertLess(m['walkway_x_m'][1] + body, truss)   # the walkway ends before the Brow truss

    def test_walkway_outside_every_keep_out(self):
        import math
        m = self.M
        for x in m['walkway_x_m']:
            for phi in m['walkway_phi_rad']:
                p = (x, m['surface_r_m'] * math.cos(phi), m['surface_r_m'] * math.sin(phi))
                for h in PKG['hazards']:
                    if h['kind'] == 'annulus':
                        self.assertFalse(h['x0'] <= p[0] <= h['x1'], h['id'])
                    elif h['kind'] == 'sphere':
                        self.assertGreater(math.dist(p, h['centre']), h['r'] + 2.0, h['id'])
                    elif h['kind'] == 'cylinder_x':
                        self.assertLess(p[0], h['x0'], h['id'])

    def test_gait_keeps_one_boot_down_and_limits_are_bounded(self):
        m = self.M
        self.assertGreater(m['gait']['stance_fraction'], 0.5)
        self.assertLess(m['capture_gap_m'], m['release_gap_m'])
        self.assertGreater(m['attach_force_n'], 0.0)
        self.assertGreater(m['sole_friction'], 0.0)
        # the suit's own thrusters cannot pull one attached boot off the plate (no thruster "lift-off" through the magnets)
        self.assertLess(PKG['allocation']['suit_reserve']['thrust_n'] * 4, m['attach_force_n'])
        self.assertEqual(m['flight'], 'HOLD')

    def test_start_on_the_plate_within_tether_reach(self):
        import math
        m = self.M
        self.assertTrue(m['walkway_x_m'][0] < m['start_x_m'] < m['walkway_x_m'][1])
        self.assertTrue(m['walkway_phi_rad'][0] < m['start_phi_rad'] < m['walkway_phi_rad'][1])
        a = next(a for a in self.R['anchors'] if a['id'] == m['tether_anchor'])
        p = (m['start_x_m'], m['surface_r_m'] * math.cos(m['start_phi_rad']), m['surface_r_m'] * math.sin(m['start_phi_rad']))
        self.assertLess(math.dist(p, a['p']), PKG['rules']['tether_length_m'])
