"""Rigid habitat rings (FGR-003): ring-equivalent dynamics against the owner's captured numbers, sector arc and volumes, frame and
spokes, and the layout checks. Independent of Blender; expected values come from the 2026-10-02 capture and hand arithmetic."""
from pathlib import Path
import math
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load, derived
import habitat_ring as hr


class HabitatRingTests(unittest.TestCase):
    def setUp(self):
        self.s,self.sources,*_=load()

    def test_owner_ring_diagnostics_10_03(self):
        # 08!C37, C39, C41:C45 as exported 2026-10-03b for the 330 t rotating model (Q32). C37 is unchanged; the others were recalculated.
        d=hr.diagnostics(self.s)
        for key,want in [('high_thrust_combined_g',1.581446882),('gyro_torque_example_N_m',87.93817521),('single_ring_angular_momentum_N_m_s',100769726.0),
                         ('flywheel_example_rpm',1924.56),('flywheel_example_rim_speed_m_s',1007.69726),('flywheel_example_energy_J',10154537669.0)]:
            self.assertAlmostEqual(d[key]/want,1.0,delta=1e-6,msg=key)
            self.assertAlmostEqual(self.s['physics']['rotor_dynamics_diagnostic'][key]/d[key],1.0,delta=1e-6,msg=key)
        self.assertAlmostEqual(hr.dynamics(self.s)['allowed_residual_momentum_N_m_s']/50384.86298,1.0,delta=1e-9)
        self.assertAlmostEqual(hr.tilt_deg(self.s,1.5),71.5,delta=0.05)
        self.assertAlmostEqual(hr.tilt_deg(self.s),11.2885,places=3)
        self.assertEqual(self.s['physics']['rotor_dynamics_diagnostic']['canon_status'],'DIAGNOSTIC')
        self.assertEqual(self.sources['sources']['ring_dynamics_diag']['range'],'A37:H37,A41:H45')

    def test_dynamics_match_the_owner_captures(self):
        # 08_ROTATING_HABITAT C10:C36 (DERIVED), as exported 2026-10-03b (330 t, 165 t per ring).
        d=hr.dynamics(self.s)
        for key,want in [('com_radius_m',27.0),('mass_each_kg',165000.0),('inertia_each_kg_m2',120285000.0),('angular_momentum_each_N_m_s',50384862.98),
                         ('spin_torque_each_N_m',27991.59054),('peak_spin_power_total_W',23450.18006),('centripetal_force_per_ring_N',781672.6686),
                         ('high_thrust_axial_load_each_N',2427145.875),('high_thrust_axial_load_total_N',4854291.75),('rpm_match_tolerance_rpm',0.004),
                         ('omega_rad_s',0.4188790205)]:
            self.assertAlmostEqual(d[key]/want,1.0,delta=1e-9,msg=key)
        self.assertAlmostEqual(hr.kinetic_energy_each(self.s)/10552581.03,1.0,delta=1e-9)
        self.assertAlmostEqual(hr.floor_gravity_g(self.s)/0.5009732933,1.0,delta=1e-9)
        self.assertAlmostEqual(hr.floor_gravity_g(self.s,26.0)/0.4651894866,1.0,delta=1e-9)       # head_g, 2 m inward
        # The stored DERIVED values are what the formulas give (rel 1e-6).
        rd=self.s['physics']['rotor_dynamics']
        for key,value in d.items():self.assertTrue(math.isclose(rd[key],value,rel_tol=1e-6),key)
        # Two rings carry equal and opposite momentum: the rig contract signs them.
        self.assertEqual(d['mass_each_kg']*hr.ring_count(self.s),self.s['physics']['rotor_sizing']['mass_kg'])
        self.assertEqual(rd['model'],'ring-equivalent, per ring')

    def test_low_thrust_tilt_matches_the_owner_note(self):
        self.assertAlmostEqual(hr.tilt_deg(self.s),11.29,delta=0.05)           # 08!H54: ~11.29 degrees at 28 m / 4 rpm for 0.1 g
        self.assertAlmostEqual(hr.tilt_deg(self.s),math.degrees(math.atan(0.1/0.5009732933)),places=6)

    def test_sector_arc_and_volumes(self):
        theta=hr.sector_arc(self.s)
        self.assertAlmostEqual(theta,0.2081720987,places=9);self.assertAlmostEqual(math.degrees(theta),11.927383,places=6)
        self.assertAlmostEqual(hr.sector_gross_m3(self.s),72.383,places=9)
        # The closed form and an independent midpoint integration agree.
        self.assertAlmostEqual(hr.volume_numeric(self.s,200)/hr.sector_gross_m3(self.s),1.0,delta=1e-9)
        self.assertAlmostEqual(hr.polygon_volume(self.s),72.37483,places=5)           # 8 straight chords across the arc
        self.assertLess(hr.polygon_volume(self.s),hr.sector_gross_m3(self.s))
        self.assertAlmostEqual(hr.gross_total(self.s),434.298,places=6)
        self.assertTrue(400.0<=hr.gross_total(self.s)<=460.0)
        self.assertAlmostEqual(hr.deck_to_overhead_m3(self.s),57.92389,places=5);self.assertGreaterEqual(hr.deck_to_overhead_m3(self.s),40.0)
        secs=hr.sectors(self.s);self.assertEqual(len(secs),6)
        self.assertEqual(sum(q['usable_alloc_m3'] for q in secs),240.0);self.assertTrue(230.0<=sum(q['usable_alloc_m3'] for q in secs)<=260.0)
        self.assertEqual([q['name'] for q in secs],[f'Sector_{j}_{k}' for j in (1,2) for k in (1,2,3)])
        self.assertEqual([q['ident'] for q in secs][:3],['WF.SECTOR.1.1','WF.SECTOR.1.2','WF.SECTOR.1.3'])
        self.assertEqual([q['function'] for q in secs][3:],['HABITATION','WORK_MEDICAL_OPS','LIFE_SUPPORT_GARDEN_COMMON'])      # mirrored in ring 2
        self.assertEqual([round(math.degrees(q['angle'])) for q in secs[:3]],[0,120,240])


    def test_derived_values_follow_the_formulas(self):
        d=derived(self.s)
        self.assertAlmostEqual(d['ring_com_radius_m'],27.0);self.assertAlmostEqual(d['ring_outer_radius_m'],30.0);self.assertAlmostEqual(d['ring_sweep_half_m'],2.15)
        self.assertAlmostEqual(d['sector_arc_deg'],11.927383,places=6);self.assertAlmostEqual(d['sector_gross_m3'],72.383)
        self.assertAlmostEqual(d['sector_deck_to_overhead_m3'],57.92389,places=5);self.assertAlmostEqual(d['usable_per_sector_m3'],40.0)
        self.assertAlmostEqual(d['gross_pressure_volume_m3'],434.298,places=6);self.assertAlmostEqual(d['low_thrust_gravity_tilt_deg'],11.2885,places=4)


if __name__=='__main__':unittest.main()
