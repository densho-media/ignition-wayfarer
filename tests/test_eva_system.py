"""Physical invariants of the EVA system (docs/WAYFARER_EVA_SYSTEM.md): gas budget, 6-DOF authority, near-suit retreat, arm reach.
PROTOTYPE values are not protected here, only the physics that must hold whatever they are."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
import eva_system as ev

# a representative drone cluster layout (local frame: nose +Y, dock face -Z); the build places them on the real shell
CLUSTERS = {'NP': ((.19, .20, .06), 1, 1), 'NS': ((-.19, .20, .06), -1, 1), 'TP': ((.12, -.22, .06), 1, -1), 'TS': ((-.12, -.22, .06), -1, -1)}
COM = (0.0, .012, .057)


class Budget(unittest.TestCase):
    def test_rocket_equation(self):
        b = ev.budget(); ve = ev.P['isp_s']*9.80665
        self.assertAlmostEqual(b['total_impulse_drone_ns'], b['drone_vessels']['usable_kg']*ve, delta=1.0)
        self.assertGreater(b['dv_drone_alone_m_s'], b['dv_docked_drone_gas_m_s'])
        self.assertAlmostEqual(b['docked_kg'], b['drone_wet_kg']+b['suited_crew_wet_kg'], delta=.02)
        self.assertLess(ev.P['isp_s'], 73.0)                     # cold N2 cannot beat its ideal vacuum Isp

    def test_n2_density(self):
        rho = ev.n2_density(30e6, 293.0, 1.10)                    # p / (Z R T): about 315 kg/m3
        self.assertAlmostEqual(rho, 30e6/(1.10*8.314462/0.0280134*293.0), delta=1.0)

    def test_suit_reserve_is_a_rescue_capability(self):
        self.assertGreaterEqual(ev.budget()['dv_suit_reserve_alone_m_s'], 2.0)   # stop and return, SAFER class

    def test_life_support_packs_into_the_module(self):
        self.assertGreaterEqual(ev.life_support_volume()['margin_l'], 0.0)


class LifeSupport(unittest.TestCase):
    """Mass and energy balances of the PROVISIONAL budget: whatever the targets are, the physics must hold."""
    def setUp(self):
        self.b = ev.life_support_budget()

    def test_oxygen_and_co2_follow_metabolism(self):
        for c in self.b['cases'].values():
            self.assertAlmostEqual(c['o2_kg_h'], c['metabolic_w']*3600/14.1e6, places=4)          # 14.1 MJ per kg O2
            self.assertAlmostEqual(c['co2_kg_h']/c['o2_kg_h'], 0.85*44.01/32.0, places=2)         # RQ 0.85

    def test_evaporator_rejects_the_sensible_load(self):
        for c in self.b['cases'].values():
            self.assertAlmostEqual(c['feedwater_kg_h']*2.45e6/3600, c['swme_load_w'], delta=1.0)

    def test_nominal_case_meets_duration_and_purge(self):
        n = self.b['cases']['nominal']; t = self.b['target_h']
        self.assertGreaterEqual(n['duration_limit_h'], t['nominal']+t['reserve'])
        self.assertGreaterEqual(self.b['emergency']['purge_minutes'], t['emergency_return_min'])

    def test_more_work_never_lasts_longer(self):
        d = list(self.b['o2_duration_sensitivity_h'].values())
        self.assertEqual(d, sorted(d, reverse=True))


class Structure(unittest.TestCase):
    def test_limit_loads_inside_ratings(self):
        s = ev.structure()
        self.assertLessEqual(s['dock']['limit_moment_nm']*s['fos_ultimate'], ev.ANCHOR['latch_moment_nm'])
        self.assertLessEqual(s['dock']['limit_pull_n']*s['fos_ultimate'], ev.ANCHOR['latch_pull_n'])
        self.assertLessEqual(s['release']['loaded_n'], s['release']['glove_limit_n'])
        for v in list(s['arm_roots'].values())+list(s['couplings'].values()):
            self.assertGreater(v['margin'], 0.0)


class Authority(unittest.TestCase):
    def setUp(self):
        self.nz = ev.nozzles_from_clusters(CLUSTERS)

    def test_free_flight_six_dof_and_single_fault(self):
        noz = [(p, e) for _, p, e, _, _ in self.nz]
        self.assertEqual(ev.axes_ok(ev.authority(noz, ev.THRUST_N, COM)), 12)
        self.assertEqual(ev.single_failure([noz], [ev.THRUST_N], COM)['worst_axes_reachable'], 12)

    def test_near_suit_keeps_retreat(self):
        """Fix 4.1: with the ventral nozzles valved off near a suit, all 12 axes remain, including +Z (back away from the suit)."""
        near = [(p, e) for _, p, e, _, inh in self.nz if not inh]
        self.assertEqual(len(near), 22)
        a = ev.authority(near, ev.THRUST_N, COM)
        self.assertEqual(ev.axes_ok(a), 12)
        self.assertTrue(a['+Fz']['ok'])
        self.assertGreater(a['+Fz']['max'], 1.0)

    def test_near_suit_stages_survive_any_single_failure(self):
        """Approach, braking, alignment, capture and abort with the real mass and inertia: every stage keeps its force and torque
        (x margin) with any one live nozzle failed closed, and the undecelerated contact stays inside the capture capacity."""
        tg = [(n, p, e, t) for n, p, e, t, inh in self.nz if not inh]
        r = ev.near_suit_faults([(p, e) for _, p, e, _ in tg], COM, tagged=tg)
        self.assertTrue(all(r['stage_ok_all_single_failures'].values()), r['failures_breaking_a_stage'])
        self.assertTrue(r['energy_j']['ok'])
        m = r['mass_kg']; ns = ev.PROP['near_suit']; v0 = ns['approach_speed_m_s']
        self.assertAlmostEqual(r['energy_j']['braking_lost'], .5*m*v0*v0, places=3)
        self.assertLess(r['propellant']['gas_kg'], .1*r['propellant']['usable_kg'])

    def test_braking_needs_more_than_a_slow_approach(self):
        tg = [(n, p, e, t) for n, p, e, t, inh in self.nz if not inh]
        r = ev.near_suit_faults([(p, e) for _, p, e, _ in tg], COM)
        need = r['requirements']['brake_force_n']; m = r['mass_kg']; ns = ev.PROP['near_suit']
        a = (ns['approach_speed_m_s']**2-ev.PROP['approach_speed_max_m_s']**2)/(2*(ns['approach_m'][1]-ns['brake_to_m']))
        self.assertAlmostEqual(need, m*a, places=3)

    def test_inhibited_nozzles_face_the_dock(self):
        for name, _, e, _, inh in self.nz:
            self.assertEqual(inh, name.endswith('VEN'), name)
            if inh:
                self.assertLess(e[2], -0.8)


class Arms(unittest.TestCase):
    def test_named_poses_reachable_inside_joint_limits(self):
        for nm, pose in ev.ARM_POSES.items():
            for K, (t, ap) in pose.items():
                arm = ev.ARMS[K]; sh = (arm['side']*arm['shoulder_x_m'], arm['shoulder_y_m'], 0.0)
                ang = ev.arm_ik(arm, t, ap or (0.0, 1.0, 0.0), sh)
                self.assertTrue(ang['reach_ok'], (nm, K))
                self.assertGreater(math.degrees(ang['pitch']), -180.0, (nm, K))       # the in-file IK control clips at -180

    def test_dock_loads_inside_rating(self):
        for K, a in ev.ARMS.items():
            self.assertLess(a['tip_force_n']*0.6, ev.ANCHOR['latch_moment_nm'], K)


if __name__ == '__main__':
    unittest.main()
