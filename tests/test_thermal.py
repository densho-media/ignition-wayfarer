"""Thermal-compliance inputs and geometry (AFT-001), independent of Blender. Capture values come from
references/drive_capture_2026-10-03/engineering.xlsx (S&E 40_THERMAL) and are test-only fixtures."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load, derived
import thermal_budget as tb
import thermal_geometry as tg


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.s,self.sources,*_=load();self.d=derived(self.s)
    def test_formula_reproduces_the_owner_cells(self):
        r=self.s['radiators']
        # 40!B7 26,882.064 m2 and 40!B10 14,401,471,762 W use the blade rounded to 182.149 m; the built 182.1494 m is 0.36 mm longer.
        self.assertAlmostEqual(tb.ideal_rejection_W(26882.064,.9,1800),14401471762,delta=1)
        self.assertAlmostEqual(r['effective_area']['value']/26882.064,1,delta=3e-6)
        self.assertAlmostEqual(tb.root_calibration_margin_W(self.s)/-1598528238,1,delta=3e-5)       # 40!B73
        self.assertAlmostEqual(r['root_calibration_margin']['value'],tb.root_calibration_margin_W(self.s),delta=1)
        self.assertAlmostEqual(self.d['root_calibration_margin_W'],r['root_calibration_margin']['value'],delta=.01)
        # 40!B53 emissivity-only benefit at 27,000 m2.
        for eps,watts in [(.95,15.268e9),(.98,15.750e9),(1.0,16.072e9)]:
            self.assertAlmostEqual(tb.ideal_rejection_W(27000,eps,1800)/watts,1,delta=1e-3)
    def test_y155_scenario_reproduces_the_owner_cells(self):
        # OWN-RAD-Y155, 40!B114:B122 (capture 2026-10-17); the rejections differ by the built blade's 0.36 mm (2e-6).
        base,study,opt=tb.y155(self.s)
        self.assertEqual(base['uplift'],1.0)
        self.assertAlmostEqual(study['uplift'],1.09037037,delta=1e-8)
        self.assertAlmostEqual(study['rejection_W']/15702938099,1,delta=3e-6)
        self.assertAlmostEqual(study['area_reduction'],0.08288043478,delta=1e-10)
        self.assertAlmostEqual(study['residual_W']/297061901.2,1,delta=2e-4)
        self.assertAlmostEqual(opt['uplift'],1.125185185,delta=1e-8)
        self.assertAlmostEqual(opt['residual_W']/-204322671.2,1,delta=2e-4)
        # The root baseline (40!B7:B10, B23) is untouched and never a build input.
        r=self.s['radiators'];self.assertEqual((r['emissivity']['value'],r['view_factor']['value']),(.9,.9))
        self.assertFalse(r['y155_scenario']['build_input'])
    def test_area_and_rejection_are_inverses(self):
        self.assertAlmostEqual(tb.ideal_area_m2(tb.ideal_rejection_W(1234.5,.7,1500),.7,1500),1234.5,delta=1e-9)


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.s,self.sources,*_=load();self.d=derived(self.s);self.blade=tg.blade_of(self.s)
    def test_root_band_and_hot_face_sum_to_the_cells(self):
        # AFT-009: the cells are the gross rectangle less nine 0.125 m joints across the 30.5 m blade; their net of the 3 m root band is
        # the owner's as-built net area at the working seam (07!D59:D63, Q52 option D).
        b=tg.root_band(self.s);area=self.s['radiators']['physical_area']['value'];cells=area-9*.125*30.5
        self.assertAlmostEqual(tg.emitting_planform(self.s),cells,delta=1e-9)
        self.assertAlmostEqual(b['planform_m2']+b['hot_face_planform_m2'],cells,delta=1e-9)
        self.assertAlmostEqual(cells*(30.5-3.0)/30.5,4978.1699681238615,delta=1e-6)
        self.assertAlmostEqual(b['width_m'],3.8125,delta=1e-12)
        self.assertAlmostEqual(b['planform_m2'],cells/8,delta=1e-9)
        self.assertEqual(b['cells_per_blade'],20)
        # Independent: one row of 8 equal rows of a 30.5 m wide blade.
        self.assertAlmostEqual(b['width_m']*8,30.5,delta=1e-12)


if __name__=='__main__':unittest.main()
