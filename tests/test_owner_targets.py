"""Owner targets of 2026-10-03b (OWN-002, F1): sourced WORKING targets, the pending registry and the Q32/Q35 numbers, independent of Blender."""
import copy
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load, validate
import owner_targets as ot
import first_ignition
import habitat_ring as hr


class OwnerTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s,cls.sources,*_=load()
        cls.rows={r['id']:r for r in ot.evaluate(cls.s)}


    def test_hab_001_targets_fail_when_the_geometry_misses_them(self):
        def fails(cid,mutate):
            s=copy.deepcopy(self.s);mutate(s);return any(f'Owner target {cid} not met' in f for f in ot.failures(s,only={cid}))
        self.assertTrue(fails('refuge_volume_m3',lambda s:s['prototype'].update(refuge_pressure_radius_m=3.1)))                     # about 63 m3
        self.assertTrue(fails('refuge_water_shell_kg',lambda s:s['prototype'].update(refuge_pressure_radius_m=3.0)))                 # shell over 20 t
        self.assertTrue(fails('ring_spar_clearance_m',lambda s:s['prototype'].update(rotor_centers_x=[{'datum':'RING_A','offset_m':-0.5},{'datum':'RING_A','offset_m':5.5}])))
        self.assertTrue(fails('spoke_depth_m',lambda s:s['habitat_ring'].update(spoke_rail_u_m=0.40)))                               # 1.04 m, below 1.2
        self.assertTrue(fails('vestibule_seal_planes',lambda s:s['crew_transfer'].update(vestibule_guard_m=0.0)))                    # one boundary
        self.assertTrue(fails('dock_capture_ring',lambda s:s['prototype'].update(dock_capture_ring_radius_m=0.80)))                  # not larger than the passage
        self.assertTrue(fails('dock_clear_passage_m',lambda s:s['prototype'].update(dock_clear_radius_m=0.70)))

    def test_hard_checks_pass_today_and_are_not_pending(self):
        for cid in ('ring_plane_spacing_m','spoke_layout','dock_clear_passage_m','dock_keep_out_corridor_m','shield_truss_depth_m','crown_bays','eye_wells',
                    'overall_length_with_lance_m','shield_shadow_margins_m',
                    # FWD-001 (F2): the five former pending entries and the four new rules are hard checks.
                    'shield_crown_depth_m','shield_sector_truss_count','disruptor_layer_count','crown_engaged_hardware_radius_m','crown_housing_radius_m',
                    'crown_engaged_motion','disruptor_ahead_of_crown','eye_line_of_sight','docking_corridor_clear_of_shield'):
            r=self.rows[cid]
            if r['study_deviation']:          # forward_defense.eye_layout selects a STUDY layout: the r4 target is reported unmet, never silently met
                self.assertFalse(r['ok'] or r['pending'],cid);continue
            self.assertTrue(r['ok'] and not r['pending'],cid)
        self.assertAlmostEqual(self.rows['shield_crown_depth_m']['current'],3.0,delta=1e-9);self.assertEqual(self.rows['shield_sector_truss_count']['current'],[3,4])
        self.assertAlmostEqual(self.rows['crown_engaged_hardware_radius_m']['current'],43.353,delta=1e-3);self.assertEqual(self.rows['crown_housing_radius_m']['current'],[41.0,44.5])
        self.assertEqual(self.rows['disruptor_layer_count']['current'],1);self.assertAlmostEqual(self.rows['disruptor_ahead_of_crown']['current'],0.15,delta=1e-9)
        self.assertEqual(self.rows['crown_engaged_motion']['current'][0],0.0);self.assertAlmostEqual(self.rows['crown_engaged_motion']['current'][1],2.949,delta=1e-3)
        self.assertAlmostEqual(self.rows['overall_length_with_lance_m']['current'],237.0)             # 225 m body + 12 m Lance (Q2)
        self.assertEqual(self.rows['eye_wells']['target'],[3.5,2.0,4.0])
        self.assertEqual(hr.plane_spacing_m(self.s),6.0)


    def test_mass_basis_330_t_splits_the_water_without_adding(self):
        s=self.s;ph=s['physics'];w=hr.water_item(s)
        self.assertEqual((ph['rotor_sizing']['mass_kg'],hr.rotating_total_kg(s),ph['rotor_dynamics']['mass_each_kg']),(330000.0,330000.0,165000.0))
        self.assertEqual((w['mass_kg'],w['rotating_allowance_kg'],w['refuge_allowance_kg']),(180000.0,160000.0,20000.0))
        self.assertEqual(hr.refuge_water_allocation_kg(s),20000.0)
        reg=next(i for i in ph['mass_regions']['items'] if i['id']=='water_radiation_shielding')
        self.assertEqual((reg['rotating_kg'],reg['stationary_refuge_kg'],reg['position_status']),(160000.0,20000.0,'WORKING'))
        total=sum(i['mass_kg'] for i in ph['mass_budget']['items']);self.assertEqual(total,ph['protected_burnout_mass']['value'])    # the refuge adds nothing
        self.assertEqual(ot.budget_failures(s),[])
        for name,change in {'350 t basis':lambda t:t['physics']['rotor_sizing'].update(mass_kg=350000.0),
                            'additive water':lambda t:hr.water_item(t).update(rotating_allowance_kg=180000.0),
                            'refuge missing':lambda t:hr.water_item(t).pop('refuge_allowance_kg'),
                            'region split differs':lambda t:next(i for i in t['physics']['mass_regions']['items'] if i['id']=='water_radiation_shielding').update(stationary_refuge_kg=10000.0),
                            'ring mass stale':lambda t:t['physics']['rotor_dynamics'].update(mass_each_kg=175000.0)}.items():
            with self.subTest(name):
                t=copy.deepcopy(s);change(t);self.assertTrue(ot.budget_failures(t))

    def test_rotor_numbers_for_330_t_from_independent_arithmetic(self):
        # Worked out by hand from 08!C18 = 330000 kg, two rings, COM radius 27 m, 4.0 rpm, 1.5 g (not read from the formulas under test).
        m=165000.0;r=27.0;w=4.0*2*math.pi/60;g=9.80665
        d=hr.dynamics(self.s)
        self.assertAlmostEqual(d['inertia_each_kg_m2'],m*r*r,delta=1e-3)
        self.assertAlmostEqual(d['angular_momentum_each_N_m_s']/(m*r*r*w),1.0,delta=1e-9)
        self.assertAlmostEqual(d['centripetal_force_per_ring_N']/(m*w*w*r),1.0,delta=1e-9)
        self.assertAlmostEqual(d['high_thrust_axial_load_each_N']/(m*1.5*g),1.0,delta=1e-9)
        self.assertAlmostEqual(hr.spoke_axial_load_N(self.s)/(m*1.5*g/6),1.0,delta=1e-9)        # ~404.5 kN per spoke before factors
        self.assertAlmostEqual(hr.spoke_axial_load_N(self.s),404524.3,delta=1.0)

    def test_first_ignition_result_matches_the_s_and_e_numbers(self):
        # Independent arithmetic for the linear ramp a(t) = k t: v = k t^2 / 2 gives t = 2 v / a_max, and x = k t^3 / 6 = a_max t^2 / 6.
        v=0.016*299792458.0;a=1.5*9.80665;t=2*v/a
        res=first_ignition.result(self.s)
        self.assertAlmostEqual(res['time_s'],t,delta=1e-6)
        self.assertAlmostEqual(res['duration_d']/7.5482279,1.0,delta=1e-8)                     # 20_FIRST_IGNITION!C13
        self.assertAlmostEqual(res['distance_AU']/6.970320784,1.0,delta=1e-8)                 # 20_FIRST_IGNITION!C16
        self.assertAlmostEqual(res['distance_m']/(a*t*t/6.0),1.0,delta=1e-12)                  # k t^3/6 with k = a/t
        m=self.s['mission'];self.assertAlmostEqual(m['first_ignition_result']['duration_d']/7.5482279,1.0,delta=1e-9)
        self.assertEqual(m['first_ignition_reference']['duration_d'],7.5482279);self.assertNotEqual(m['first_ignition_reference']['duration_d'],7.75)
        self.assertEqual((m['first_ignition_reference']['canon_status'],self.sources['sources']['sanity_time_to_target']['canon_status']),('DERIVED','DERIVED'))
        for name,change in {'result 7.75 d':lambda t:t['mission']['first_ignition_result'].update(duration_d=7.75),
                            'distance stale':lambda t:t['mission']['first_ignition_result'].update(distance_AU=6.970),
                            'reference 7.75 d':lambda t:t['mission']['first_ignition_reference'].update(duration_d=7.75),
                            'faster ship':lambda t:t['mission']['target_speed'].update(value=0.02)}.items():
            with self.subTest(name):
                t=copy.deepcopy(self.s);change(t)
                with self.assertRaises(ValueError):validate(t,self.sources)


if __name__=='__main__':
    unittest.main()
