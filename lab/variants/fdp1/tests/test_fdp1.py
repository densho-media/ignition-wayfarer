"""FDP-1 study tests: physical invariants of the integrated solve and the parametric geometry (work/ only; nothing in tests/ reads it).

  python3 -m unittest discover -s lab/variants/fdp1/tests -v
"""
import math
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from engineering import config, model, geometry as G   # noqa: E402

G0 = 9.80665
C = 299792.458
_CACHE = {}


def solve(variant='baseline', overrides=None, key=None):
    k = key or variant
    if k not in _CACHE:
        _CACHE[k] = model.solve(config.load(variant, overrides))
    return _CACHE[k]


class Invariants:
    variant = 'baseline'

    @classmethod
    def setUpClass(cls):
        cls.R = solve(cls.variant)

    def test_closes(self):
        self.assertTrue(self.R['converged'])

    def test_all_checks_and_clearances(self):
        bad = [c for c in self.R['checks'] if not c['ok']]+[c for c in self.R['clearances'] if not c['ok']]
        self.assertEqual(bad, [])

    def test_four_burns_rocket_equation(self):
        ve = self.R['closure']['ve_km_s']; burns = self.R['mission']['burns']
        self.assertEqual(len(burns), 4)
        for b in burns:
            dv = ve*math.log(b['start_mass_t']/b['end_mass_t'])
            self.assertAlmostEqual(dv, 0.016*C, delta=1e-6*C)
        for b0, b1 in zip(burns, burns[1:]):
            self.assertAlmostEqual(b0['end_mass_t'], b1['start_mass_t'], places=6)

    def test_mass_balance(self):
        c = self.R['closure']; m = self.R['mass']
        self.assertAlmostEqual(c['departure_t'], c['end_t']+c['propellant_t'], delta=1e-6*c['departure_t'])
        self.assertAlmostEqual(sum(m['items_kg'].values()), m['departure_kg'], delta=1.0)
        self.assertAlmostEqual(sum(b['propellant_t'] for b in self.R['mission']['burns']), c['propellant_t'], delta=1e-6*c['propellant_t'])

    def test_momentum_and_jet_power(self):
        c = self.R['closure']
        self.assertAlmostEqual(c['thrust_MN']*1e6, c['mass_flow_kg_s']*c['ve_km_s']*1e3, delta=1e-6*c['thrust_MN']*1e6)
        self.assertAlmostEqual(c['jet_power_TW']*1e12, 0.5*c['thrust_MN']*1e6*c['ve_km_s']*1e3, delta=1e-6*c['jet_power_TW']*1e12)
        self.assertAlmostEqual(c['a0_g']*G0, c['thrust_MN']*1e6/(c['departure_t']*1e3), delta=1e-6*c['a0_g']*G0)

    def test_acceleration_ceiling(self):
        for b in self.R['mission']['burns']:
            self.assertLessEqual(max(b['accel_start_g'], b['accel_end_g']), 1.5)

    def test_propellant_nonnegative_and_fused_plus_unburned(self):
        c = self.R['closure']
        for k, x in c['species_t'].items():
            self.assertGreaterEqual(x, -1e-9, k)
        self.assertAlmostEqual(c['fused_t']+c['lost_unburned_t']+c['recovered_t'], c['propellant_t'], delta=1e-6*c['propellant_t'])

    def test_energy_ledger_and_heat(self):
        f = self.R['fusion']; circ = self.R['thermal']['circuits']
        self.assertAlmostEqual(sum(f['ledger_per_W_fusion'].values()), 1.0, places=9)
        self.assertAlmostEqual(circ['unaccounted_W'], 0.0, delta=1e-6*circ['hot_total_W'])
        self.assertAlmostEqual(circ['hot_total_W'], sum(circ['hot_W'].values()), delta=1e-6*circ['hot_total_W'])
        self.assertAlmostEqual(circ['warm_total_W'], sum(circ['warm_W'].values()), delta=1e-6*circ['warm_total_W'])
        self.assertAlmostEqual(f['ledger_W']['jet'], self.R['closure']['jet_power_TW']*1e12, delta=1e-6*f['ledger_W']['jet'])

    def test_radiators_carry_their_heat(self):
        sb = 5.670374419e-8; rad = self.R['thermal']['radiators']; circ = self.R['thermal']['circuits']
        for kind, W in (('hot', circ['hot_total_W']), ('warm', circ['warm_total_W'])):
            r = rad[kind]
            self.assertGreaterEqual(r['planform_m2']*r['flux_W_m2'], W*(1-1e-6), kind)
            self.assertLessEqual(r['flux_W_m2'], 2*sb*r['T_K']**4*(1+1e-9), kind)     # two faces, emissivity <= 1
        self.assertAlmostEqual(rad['hot']['mass_kg']+rad['warm']['mass_kg'], rad['closure_radiator_kg'], delta=1.0)
        lay = self.R['thermal']['layouts'][self.R['thermal']['selected_layout']]
        self.assertGreaterEqual(lay['total_planform_m2'], rad['warm']['planform_m2']*(1-1e-9))   # never shrunk to fit

    def test_tanks_cover_requirement(self):
        ts = self.R['tanks']['summary']; o = self.R['tanks']['options'][self.R['tanks']['selected']]
        for sp in ('helium_3', 'deuterium'):
            self.assertGreaterEqual(ts['existing_m3'][sp]+o['added_m3'][sp], ts['required_m3'][sp]*(1-1e-9), sp)
        self.assertEqual(len(self.R['tanks']['existing']), 13)

    def test_shield_meets_dose(self):
        sh = self.R['shield']
        lam = config.v(config.load(self.variant)['shielding']['lambda_LiH_m'])
        self.assertGreaterEqual(sh['lih_core_m'], lam*math.log(10)*sh['neutron_decades']*(1-1e-9))
        self.assertGreaterEqual(sh['w_face_m'], sh['w_needed_m'])
        self.assertGreater(sh['mass_kg']['total'], 0.0)

    def test_feedback_converged(self):
        sa = self.R['solid_angle']
        self.assertAlmostEqual(sa['total'], sa['used_in_closure'], delta=1e-5*sa['total'])


class Baseline(Invariants, unittest.TestCase):
    variant = 'baseline'

    def test_shield_not_placeholder(self):
        self.assertGreater(self.R['shield']['mass_kg']['total'], self.R['shield']['placeholder_kg'])


class LowPower(Invariants, unittest.TestCase):
    variant = 'low_power'


class HighPower(Invariants, unittest.TestCase):
    variant = 'high_power'


class Deficit(unittest.TestCase):
    def test_one_g_reports_deficit(self):
        R = solve('goal_1g')
        self.assertFalse(R['converged'])
        self.assertLess(R['max_a0_g_any_size'], 1.0)
        self.assertGreater(R['deficit_factor'], 1.0)

    def test_power_order(self):
        lo, base, hi = solve('low_power'), solve('baseline'), solve('high_power')
        self.assertLess(lo['closure']['fusion_power_TW'], base['closure']['fusion_power_TW'])
        self.assertLess(base['closure']['fusion_power_TW'], hi['closure']['fusion_power_TW'])
        self.assertGreater(lo['closure']['burn_time_years'], hi['closure']['burn_time_years'])


class Parametric(unittest.TestCase):
    def test_coil_count_regenerates_geometry(self):
        b = G.parts(solve('baseline'))
        R4 = solve('baseline', {'nozzle': {'coil_count': {'value': 4}}}, key='coils4')
        p4 = G.parts(R4)
        loops = lambda ps: {p['name'].split('_')[4] for p in ps if p['name'].startswith('FDP1_Nozzle_Strut_Loop_')}
        self.assertEqual(len(loops(b)), 3)
        self.assertEqual(len(loops(p4)), 4)

    def test_gallery_radius_moves_drivers(self):
        R = solve('baseline', {'drivers': {'gallery_radius_m': {'value': 16.0}}}, key='gal16')
        self.assertEqual(R['drivers']['radius_m'], 16.0)
        walk = next(p for p in G.parts(R) if p['name'] == 'FDP1_Gallery_1_Walkway')
        base = next(p for p in G.parts(solve('baseline')) if p['name'] == 'FDP1_Gallery_1_Walkway')
        r = lambda p: math.hypot(*p['points'][0][1:])
        self.assertAlmostEqual(r(walk)-r(base), 4.0, places=6)

    def test_geometry_from_record_only(self):
        R = solve('baseline'); ps = G.parts(R)+G.tank_parts(R)
        self.assertEqual(len({p['name'] for p in ps}), len(ps))           # unique names
        for p in ps:
            self.assertIn(p['status'], ('ENGINEERED', 'PLACEHOLDER', 'ILLUSTRATIVE'))
            self.assertIn(p['coll'].split(':')[0], G.COLLECTIONS)


class BaselineUnchanged(unittest.TestCase):
    def test_no_tracked_change_outside_work(self):
        try:
            base = subprocess.run(['git', 'merge-base', 'HEAD', 'origin/main'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        except Exception:
            self.skipTest('git or origin/main unavailable')
        diff = subprocess.run(['git', 'diff', '--name-only', base, '--', '.', ':!work'], cwd=ROOT, capture_output=True, text=True).stdout.split()
        self.assertEqual(diff, [], 'FDP-1 must not change canon, generators or tests')

    def test_review_written_inside_work(self):
        src = (HERE/'blender'/'build_fdp1.py').read_text()
        self.assertIn("default=FDP/'REVIEW_FDP1.blend'", src)
        self.assertNotIn('save_as_mainfile(filepath=str(SHIP', src)


if __name__ == '__main__':
    unittest.main()
