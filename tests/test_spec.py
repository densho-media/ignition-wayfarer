"""Input validation failures, independent of Blender."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load, validate, derived

import layout

class SpecificationTests(unittest.TestCase):
    def setUp(self):
        self.s,self.sources,*_=load()
    def test_snapshot_and_area_conversion(self):
        d=validate(self.s,self.sources)
        self.assertAlmostEqual(d['petal_planform_m2'],5555.555555555555)
        self.assertAlmostEqual(d['total_planform_m2']*2*.9,30000)
    def test_unknown_physics_is_not_zero(self):
        self.assertNotIn('value',self.s['physics']['inertia'])
        validate(self.s,self.sources)
    def test_blade_is_derived_from_area_root_and_outer_radius(self):
        d=derived(self.s);area=50000/9
        self.assertAlmostEqual(d['net_width_m'],37.0-6.5,delta=1e-12)                         # 07!A54: 37 m outer radius - 6.5 m root radius
        self.assertAlmostEqual(d['blade_length_m'],182.149362477,delta=1e-8)                  # 07!A55 quotes 182.149377 from the rounded 5,555.556 m2
        self.assertAlmostEqual(d['blade_length_m'],182.149377,delta=182.149377*1e-6)
        self.assertAlmostEqual(d['ratio'],5.972110723,delta=5.972110723*1e-6)                 # 07!A44
        self.assertAlmostEqual(d['blade_length_m']*d['net_width_m'],area,delta=1e-9)           # physical area kept, independent of the view factor
        self.assertAlmostEqual(d['outer_radius_m'],37.0,delta=1e-9)
        self.assertAlmostEqual(d['local_circumscribed_diameter_m'],74.0,delta=1e-9)
        self.assertAlmostEqual(d['bay_length_m']*10,d['blade_length_m'],delta=1e-9)
        self.assertAlmostEqual(d['casing_radius_m'],6.0,delta=1e-12)
        self.assertAlmostEqual(d['forward_shield_radius_m'],45.0,delta=1e-12)
        self.assertAlmostEqual(d['front_x_m'],layout.origin(self.s,'RADIATOR_FRONT'),delta=1e-9)
        eq=self.s['radiators']['equivalent_blade'];self.assertEqual(eq['canon_status'],'DIAGNOSTIC')
        # Captured DERIVED values are checked against the inputs, never read as inputs: a stale capture or a changed radius is rejected.
        for change in [lambda s:s['radiators']['equivalent_blade'].update(length_m=170.0),
                       lambda s:s['radiators']['equivalent_blade'].update(aspect_ratio=5.0),
                       lambda s:s['radiators']['equivalent_blade'].update(width_m=31.0),
                       lambda s:s['forward_shield']['ring_shadow_margin'].update(value=14.0),
                       lambda s:s['radiators']['physical_area'].update(value=5500.0)]:
            v=copy.deepcopy(self.s);change(v)
            with self.assertRaises(ValueError):validate(v,self.sources)


    def test_volume_gravity_and_diameter_definitions(self):
        d=derived(self.s)
        self.assertAlmostEqual(d['gross_pressure_volume_m3'],434.298,places=6)        # 6 sectors x 434.3/6, inside the BASELINE 400-460 m3
        self.assertAlmostEqual(d['floor_gravity_g'],.5009732933)                       # 08!C14: 0.501 g at the 28 m floor
        self.assertAlmostEqual(d['ring_com_radius_m'],27.0)
        self.assertAlmostEqual(d['local_circumscribed_diameter_m'],74.0)
        self.assertLess(d['blade_length_m'],d['length_m'])


    def test_view_factor_does_not_resize_physical_area(self):
        s=copy.deepcopy(self.s);s['radiators']['view_factor']['value']=.6
        d=derived(s)
        self.assertAlmostEqual(d['total_planform_m2'],16666.666666666668)     # the retained blades: the view factor resizes nothing
        self.assertAlmostEqual(d['total_net_area_m2'],3*4978.16,delta=0.05)    # 40!B21 as-built
        self.assertAlmostEqual(d['assumed_effective_area_m2'],d['total_net_area_m2']*2*.6)
    def test_ribbons_preserve_net_area_and_add_gap(self):
        from thermal_geometry import dimensions,point
        d=dimensions(ribbons=2,cant=3,aft_x=-100.0)
        self.assertAlmostEqual(2*d['blade_length_m']*d['ribbon_width_m'],d['area_m2'])
        self.assertAlmostEqual(d['radial_pack_width_m']-d['net_width_m'],2)
        x0,r0=point(d,0,0);x1,r1=point(d,d['blade_length_m'],0)
        self.assertAlmostEqual((x1-x0)**2+(r1-r0)**2,d['blade_length_m']**2)
        self.assertAlmostEqual(d['aft_x_m'],-100.0)
        # With cant the front moves forward by the span times sin(cant): placement is from the aft edge.
        import math
        self.assertAlmostEqual(d['front_x_m'],-100.0+d['blade_length_m']*math.cos(math.radians(3))+d['radial_pack_width_m']*math.sin(math.radians(3)),delta=1e-9)


    def test_drive_capture_budgets(self):
        items=self.s['physics']['mass_budget']['items']
        self.assertEqual(len(items),12)
        self.assertEqual(sum(i['mass_kg'] for i in items),self.s['physics']['protected_burnout_mass']['value'])
        self.assertEqual(sum(i.get('rotating_allowance_kg',0) for i in items),self.s['physics']['rotor_sizing']['mass_kg'])
        self.assertEqual(self.s['eye']['electrical_demand']['burn_watch_W'],1050000.0)
        self.assertNotIn('value',self.s['radiators']['drive_waste_heat'])
        budget=lambda s,ident:next(i for i in s['physics']['mass_budget']['items'] if i['id']==ident)
        for change,message in [(lambda s:budget(s,'drive_package').update(mass_kg=260000.0),'burnout'),
                               (lambda s:budget(s,'main_structure').update(rotating_allowance_kg=30000.0),'rotating'),
                               (lambda s:budget(s,'eye_sensors').update(rotating_allowance_kg=30000.0),'items'),
                               (lambda s:s['physics']['mass_budget'].update(positions_known=True),'positions'),
                               (lambda s:s['physics']['mass_regions']['items'].pop(),'regions'),
                               (lambda s:s['physics']['mass_regions']['items'][5].update(rotating_kg=0.0),'regions'),
                               (lambda s:s['radiators']['layout'].update(canon_status='WORKING'),'status mismatch'),
                               (lambda s:s['eye']['mass'].update(value=30000.0),'eye mass'),
                               (lambda s:s['brow']['mass'].update(budget_item='missing'),'brow mass'),
                               (lambda s:s['eye']['power_inputs'].update(laser_wall_plug_efficiency=.4),'BURN_WATCH|SURVEY_LIDAR'),
                               (lambda s:s['eye']['laser_modes']['BURN_WATCH'].update(active_facets=2),'BURN_WATCH'),
                               (lambda s:s['eye']['power_inputs'].update(active_non_laser_W=200000.0),'electrical demand'),
                               (lambda s:s['eye']['facet_modes']['ABLATION']['facet_roles'].pop(),'facet mode'),
                               (lambda s:s['propulsion']['internal_waste_heat_fraction'].update(value=2e-4),'drive heat'),
                               (lambda s:s['radiators']['temperature'].update(value=1500.0),'drive heat'),
                               (lambda s:s['radiators']['drive_waste_heat'].update(known=True,value=1.6e10),'waste heat is OPEN'),
                               (lambda s:s['eye']['facet_modes']['QUIET_WATCH'].update(canon_status='WORKING'),'status mismatch')]:
            v=copy.deepcopy(self.s);change(v)
            with self.assertRaisesRegex(ValueError,message):validate(v,self.sources)

if __name__=='__main__':unittest.main()
