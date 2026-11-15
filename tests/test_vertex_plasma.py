"""Vertex Engine 1.4 coupled plasma (vertex_plasma): benchmarks, conservation, the particle audit's mirror check, the bounds of the
thermal screens, and that the research results never change the engine."""
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'/'wayfarer'))
import spec  # noqa: E402
import vertex_magnet as vm  # noqa: E402
import vertex_plasma as vp  # noqa: E402

S = spec.load(ROOT)[0]


class Benchmarks(unittest.TestCase):
    def test_diamagnetic_sphere_in_uniform_field(self):
        """The sheet solver reproduces B_t = 1.5 B0 sin(theta) on a perfectly diamagnetic sphere, with B_n small just outside."""
        r = vp.sphere_check(24)
        self.assertLess(r['max_error'], 0.01)
        self.assertLess(r['bn_over_bt'], 0.1)

    def test_populations_sum_to_one(self):
        for f in vp.config(S)['fast_product_share']:
            w = vp.populations(S, f)
            self.assertAlmostEqual(sum(w.values()), 1.0, places=12)
            self.assertAlmostEqual(w['p_14.7MeV']/w['alpha_3.6MeV'], 14.7/3.6, places=9)   # D-3He products split by birth energy

    def test_mirror_loss_cone_matches_particles(self):
        """The 1.3 shield share in the M2 mirror is the adiabatic loss cone: rigidity-independent, (1 - sqrt(1 - 1/R_m)) / 2."""
        m = vp.mirror_loss_cone(S, 'M2')
        self.assertGreater(m['mirror_ratio'], 1.0)
        vp._S['s'] = S
        _, rows, _ = vp._particle_task(('M2', 'p_14.7MeV', 100, 40, (0.0, 0.0, 0.0), 1.0))
        self.assertAlmostEqual(vp.summarise(rows)['shield'], m['forward_loss'], delta=0.05)
        self.assertEqual(vp.mirror_loss_cone(S, 'NOMINAL')['forward_loss'], 0.5)    # the 1.2 cusp confines nothing forward


class Cavity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m2 = vp.cavity(S, 'M2', n=16, ds=0.08)
        cls.m0 = vp.cavity(S, 'NOMINAL', n=16, ds=0.08)

    def test_energy_ledger(self):
        for cv in (self.m2, self.m0):
            self.assertLess(abs(cv['energy_error']), 0.03)

    def test_newton_third_law_between_sheet_and_coils(self):
        self.assertLess(self.m2['momentum_error'], 0.15)

    def test_shares_and_closures_sum_to_one(self):
        for cv in (self.m2, self.m0):
            self.assertAlmostEqual(sum(cv['first_pass'].values()), 1.0, places=9)
            for k, part in cv['closures'].items():
                self.assertAlmostEqual(sum(part.values()), 1.0, places=9, msg=k)

    def test_cusp_puts_plasma_on_hardware_mirror_far_less(self):
        hard = lambda cv: sum(v for k, v in cv['first_pass'].items() if k not in ('AFT', 'OUT', 'STOPPED'))
        self.assertIsNotNone(self.m0['coil_contact'])        # the 1.2 cusp lets the pulse reach a closure-coil cryostat
        self.assertIsNone(self.m2['coil_contact'])
        self.assertGreater(hard(self.m0), 3*hard(self.m2))

    def test_flux_conserving_coils_take_the_pulse(self):
        """Superconducting coils keep their flux: the pulse raises the stored field energy by about the stopped share of its energy."""
        cv = self.m2; dW = cv['W_peak_J']-cv['W0_J']
        self.assertGreater(dW, 0.5*cv['first_pass']['STOPPED']*cv['energy_J'])
        self.assertLess(dW, 1.05*cv['energy_J'])

    def test_wall_screens_the_pulse(self):
        e = vp.eddy(S, 'M2', self.m2)
        self.assertTrue(e['screened'])                         # wall diffusion time longer than the pulse period
        self.assertLessEqual(e['energy_J'][0], e['energy_J'][1])
        self.assertLess(e['skin_depth_m'], vm.config(S)['cryostat_wall_m'])


class Thermal(unittest.TestCase):
    def test_regenerative_cooling_cannot_replace_radiators(self):
        """Heat leaving with a thermal working fluid needs a flow far beyond the engine's propellant flow (exhaust speed ratio)."""
        th = {'deposition': {'isotropic': {'SHIELD': {'W': 1.0e10}}}, 'xray_absorbed_W': 1.0e11, 'neutron_absorbed_W': [0.0, 1.0e9, 0.0]}
        t = vp.treg(S, th)
        self.assertGreater(t['T1']['flow_ratio'], 1e5)
        self.assertLess(t['T1']['exhaust_ratio'], 1e-2)
        self.assertGreater(t['T2']['radiator_m2'], t['T0']['radiator_m2'])

    def test_sky_fractions_cover_the_sphere(self):
        sky = vp.sky_fractions(S, 'M2', step_deg=2)
        self.assertAlmostEqual(sum(sky.values()), 1.0, places=9)
        self.assertGreater(sky.get('SHIELD', 0.0), 0.05)


class Evidence(unittest.TestCase):
    def test_engine_unchanged_by_research(self):
        c = vp.config(S); mc = vm.config(S)
        self.assertEqual(mc['selected'], 'M0-NOMINAL')
        self.assertEqual(c['verdict'], 'PROPULSION_FEASIBILITY_BLOCKED')
        self.assertEqual(c['thrust'], 'THRUST_UNPROVEN')
        self.assertEqual(c['detachment'], 'DETACHMENT_OPEN')

    def test_evidence_is_current(self):
        """The engineering page reads references/evidence/vertex_plasma.json: it must come from the current inputs and code
        (python3 src/wayfarer/vertex_plasma.py --evidence rewrites it)."""
        R = json.loads(vp.EVIDENCE_PATH.read_text())
        self.assertEqual(R['input_hash'], vp.input_hash(S))
        for k in ('M0-NOMINAL', 'M2'):
            self.assertLess(abs(R['coupled'][k]['energy_error']), 0.02)
            self.assertIsNone(R['coupled'][k]['unstable'])
            self.assertLess(R['convergence'][k]['finest_change'], 0.05)     # hardware share between the two finest marker counts
        self.assertLess(R['convergence']['M2']['spread'], 0.05)
        self.assertEqual(R['decision']['outcome'], vp.config(S)['outcome'])


if __name__ == '__main__':
    unittest.main()
