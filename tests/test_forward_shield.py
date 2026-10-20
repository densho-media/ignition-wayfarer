"""Forward shield, EYE wells, Dust Lance, displays and the Dustbreak Crown (FGR-006, FWD-001), independent of Blender."""
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import forward_shield as fs


class ForwardShieldTests(unittest.TestCase):
    def setUp(self):
        self.s,self.sources,*_=load()
        self.st=fs.stations(self.s)

    # ---- stations: literal numbers worked out from the sourced 225 m length, the ~3 m crown depth and the PROTOTYPE table


    # ---- wells and the Lance


    def test_lance_profile_and_working_length(self):
        L=fs.lance(self.s)
        self.assertAlmostEqual(L['x1']-L['x0'],12.0);self.assertAlmostEqual(L['x1']-L['cone_end'],1.5)
        self.assertAlmostEqual(fs.lance_radius_at(self.s,L['x0']),1.0);self.assertAlmostEqual(fs.lance_radius_at(self.s,L['cone_end']),0.25);self.assertAlmostEqual(fs.lance_radius_at(self.s,L['x1']),0.25)
        radii=[fs.lance_radius_at(self.s,L['x0']+i*.5) for i in range(25)]
        self.assertTrue(all(a>=b for a,b in zip(radii,radii[1:])),'the Lance never widens ahead of the shield')
        # Q2 (2026-10-03b): the 12 m length and the 1.0 -> 0.25 m taper with the 1.5 m tip are WORKING source values; the geometry reads them from the
        # sourced tables, not from forward_shield.prototype (one place per value), and the overall length INCLUDES the Lance.
        d=self.s['forward_defense']['dust_lance'];ln=d['length']
        self.assertEqual((ln['known'],ln['value'],ln['unit'],ln['canon_status'],d['canon_status'],d['geometry']['canon_status']),(True,12.0,'m','WORKING','WORKING','WORKING'))
        self.assertEqual((d['geometry']['base_radius_m'],d['geometry']['tip_radius_m'],d['geometry']['tip_cartridge_m']),(1.0,0.25,1.5))
        for key in ('lance_length_m','lance_base_radius_m','lance_tip_radius_m','lance_tip_cartridge_m','well_diameter_m'):
            self.assertNotIn(key,self.s['forward_shield']['prototype'])
        self.assertAlmostEqual(fs.overall_length(self.s)-self.s['ship']['length']['value'],ln['value'])

    # ---- the diversion field zone (display only)

    # ---- truss: conical, constant depth, inside the envelope


    # ---- sector keels and ties (Q1)


    # ---- full-area disruptor, EYE ports and line of sight (FWD1)


    # ---- Crown


    # ---- controls, presets, poses


    # ---- docking corridors, fittings and the neighbours (read-only use of the aft modules)


    # ---- HSFP design classes (98!A58)

    # ---- study formulas and budgets (DIAGNOSTIC / WORKING; never geometry)
    def test_study_formulas_reproduce_the_captured_rows(self):
        v=fs.study(self.s)
        self.assertAlmostEqual(v['optical_W'],5.0e6);self.assertAlmostEqual(v['electrical_W'],1.0e7);self.assertAlmostEqual(v['heat_W'],5.0e6)
        self.assertAlmostEqual(v['local_store_J'],2.0e7);self.assertAlmostEqual(v['interceptor_kinetic_J'],1.0e7)
        self.assertAlmostEqual(v['interceptor_input_J'],1.4286e7,delta=1.4286e7*1e-4);self.assertAlmostEqual(v['interceptor_loss_J'],4285714.286,delta=1e-2)
        self.assertAlmostEqual(v['field_energy_J'],0.5*10000/(4e-7*math.pi),delta=1e3)     # B2 V / (2 mu0) with mu0 = 4 pi 1e-7: 3.979 GJ
        self.assertAlmostEqual(v['shadow_angle_deg'],2.2906,places=4);self.assertAlmostEqual(v['mass_loading_kg_m2'],15.719,places=3)
        self.assertAlmostEqual(v['seconds_per_metre']*1e6,0.2085,places=4);self.assertAlmostEqual(v['standoff_s']*1e6,4.17,places=2)
        pw=self.s['forward_defense']['power']
        for name,factor in [('crown_normal',1),('crown_heavy',2),('crown_extreme',4)]:
            self.assertAlmostEqual(pw[name]['electrical_W'],2*pw[name]['optical_W']);self.assertAlmostEqual(pw[name]['heat_W'],pw[name]['optical_W'])
            self.assertAlmostEqual(pw[name]['optical_W'],5.0e6*factor)
        self.assertEqual(fs.validate_budgets(self.s),[])


if __name__=='__main__':unittest.main()
