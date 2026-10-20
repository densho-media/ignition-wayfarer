"""AFT-011 stage A1: the owner's aft answers recorded as data (drive_capture_2026-10-03b), independent of Blender."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load, derived
import drive_manifold as dm
import radiator_net_area as rna
import thermal_budget as tb

# record -> (sheet, range, status, first cross range or None)


class AftAnswerValues(unittest.TestCase):
    def setUp(self):
        self.s,self.sources,*_=load()

    def test_nozzle_map_matches_the_eye_grammar_and_makes_the_example_a_yaw_couple(self):
        q=self.s['propulsion']['manifold']['nozzle_map']['quadrants']
        self.assertEqual(q,self.s['eye']['facet_map']['quadrants'])
        sh=self.s['propulsion']['manifold']['example_maneuver']['shares']
        self.assertAlmostEqual(sum(x*z for x,(y,z) in zip(sh,q)),0.0);self.assertNotAlmostEqual(sum(x*y for x,(y,z) in zip(sh,q)),0.0)
        # Independent of the arrays: N1=+Y+Z, N2=-Y+Z, N3=+Y-Z, N4=-Y-Z.
        self.assertEqual([tuple(x) for x in q],[(1,1),(-1,1),(1,-1),(-1,-1)])


    def test_throat_and_placement_reproduce_the_owner_figures(self):
        s=self.s;g=s['propulsion']['manifold']['throat_geometry'];d=s['drive_manifold']
        self.assertEqual((g['length_m'],g['waist_radius_m']),(1.5,2.4));self.assertEqual(dm.throat_geometry(s),(1.5,2.4));self.assertFalse([k for k in d if k.startswith('throat_')])
        meas=dm.check(s,derived(s))['measurements']
        self.assertAlmostEqual(meas['exhaust_nozzle_coil_gap_m'],0.09,delta=0.005);self.assertAlmostEqual(meas['branch_max_off_axis_deg'],21.6,delta=0.05)
        self.assertAlmostEqual(meas['branch_min_bend_radius_m'],4.74,delta=0.005)

    def test_channel_loss_recovery_survivors_are_a_diametric_pair(self):
        q=[tuple(x) for x in self.s['propulsion']['manifold']['nozzle_map']['quadrants']]
        for failed in range(4):
            opposite=q.index((-q[failed][0],-q[failed][1]))
            alive=[i for i in range(4) if i not in (failed,opposite)]
            self.assertEqual(len(alive),self.s['propulsion']['manifold']['channel_loss_recovery']['surviving_channels'])
            self.assertEqual(q[alive[0]],(-q[alive[1]][0],-q[alive[1]][1]))
        self.assertEqual(self.s['propulsion']['manifold']['channel_loss_recovery']['surviving_thrust_fraction'],0.5)


    def test_compliance_and_joint_numbers(self):
        r=self.s['radiators'];c=r['thermal_expansion']['distributed_compliance']
        self.assertEqual((c['local_travel_m'],c['local_travel_range_m'],c['aggregate_envelope_m']),(0.2,[0.1,0.2],1.5))
        self.assertGreaterEqual((r['geometry']['major_bays']-1)*c['local_travel_m'],c['aggregate_envelope_m'])   # 9 x 0.20 = 1.8 >= 1.5
        self.assertEqual((r['bay_joints']['width_low_m'],r['bay_joints']['width_high_m'],r['root_band']['width_m']),(0.10,0.15,3.0))
        self.assertEqual(r['nominal_net_area']['value'],5000.0)                                                   # 07!D19 nominal target, Q52
        self.assertEqual(r['bay_joints']['width_working_m'],0.125)                                        # 07!D60
        self.assertEqual(r['thermal_expansion']['axial_datum']['datums_per_blade'],1)

    def test_thermal_loops_match_the_owner_examples(self):
        L=self.s['thermal']['loops'];self.assertEqual((L['warm']['temperature_K'],L['cold']['temperature_K']),(450.0,320.0))
        # Independent arithmetic: A = Q / (eps * sigma * T^4).
        self.assertAlmostEqual(L['warm']['example']['ideal_area_m2'],5e6/(0.9*5.670374419e-8*450.0**4),places=6)
        self.assertAlmostEqual(L['cold']['example']['ideal_area_m2'],1e5/(0.9*5.670374419e-8*320.0**4),places=6)
        self.assertAlmostEqual(L['warm']['example']['ideal_area_m2'],2390,delta=1);self.assertAlmostEqual(L['cold']['example']['ideal_area_m2'],187,delta=1)
        self.assertEqual(L['defense_routing']['limited_duty_W'],[3.0e7,5.0e7]);self.assertEqual(L['hot']['temperature_ref'],'radiators.temperature')


# Verbatim from the capture (S&E 14_HULL_SERVICE!C22 and 06_PROPULSION_ARCHITECTURE!C46), written out here as the independent source.


class NetAreaTests(unittest.TestCase):
    def setUp(self):
        self.s,*_=load()
        r=self.s['radiators'];self.area=r['physical_area']['value'];self.W=30.5;self.L=self.area/self.W

    def test_net_area_at_a_mid_joint(self):
        # Hand accounting: gross - 9 joint strips (full width) - root band (full length) + the 9 strip/band overlaps.
        by_hand=self.area-9*0.125*self.W-3*self.L+9*0.125*3
        self.assertAlmostEqual(rna.net_area(self.L,self.W,9,0.125,3.0),by_hand,places=6);self.assertAlmostEqual(by_hand,4978.17,delta=0.01)
        self.assertLess(by_hand,self.s['radiators']['nominal_net_area']['value'])        # the accepted blade is short of the nominal 5,000 m2 (option D)


    def test_as_built_matches_the_owner_cells(self):
        # 07!D61 4,978.16 m2 at 0.125 m (4,971.97-4,984.35 m2 across the seam range), 07!D63 21.84 m2 short; the owner rounds the blade to 182.149 m.
        c=rna.as_built(self.s)
        for got,want in zip(c['net_area_m2'],(4984.35,4978.16,4971.97)):self.assertAlmostEqual(got,want,delta=0.015)
        self.assertAlmostEqual(c['nominal_shortfall_m2'][1],21.84,delta=0.015)
        self.assertAlmostEqual(rna.working_net_area(self.s)*3*2*0.9/26882.064,1,delta=3e-6)          # 07!D62, 40!B7


if __name__=='__main__':
    unittest.main()
