"""Revision 4 checks (lab tests, run by hand: python3 lab/variants/vertex-drive/studies/rev4/test_rev4.py).

They check accounting, not engineering verdicts: a failed engineering candidate is a valid result and stays failed in the results.
"""
import math
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import durability as DU   # noqa: E402
import injection as IN    # noqa: E402
import ledger as LG       # noqa: E402
import spine as SP        # noqa: E402
from common import C, core, read_json, solve_full, v4_overrides, VX   # noqa: E402

ROOT = VX.parents[2]
REL = 1e-9


class Ledger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.R = read_json('ledger.json')
        cls.Pf = cls.R['v4']['fusion_W']
        cls.L = cls.R['v4']['ledger_W']

    def all_cases(self):
        return self.R['cases'] + self.R['sensitivities']

    def test_eight_terms_conserve_energy(self):
        for c in self.all_cases():
            self.assertEqual(set(c['eight_W']), set(LG.TERMS))
            self.assertAlmostEqual(sum(c['eight_W'].values()) / self.Pf, 1.0, delta=REL, msg=c['label'])
            if c.get('coupled', {}).get('eight_W'):
                cp = c['coupled']
                self.assertAlmostEqual(sum(cp['eight_W'].values()) / cp['fusion_W'], 1.0, delta=REL, msg=c['label'])

    def test_interception_reduces_escaping_radiation_only(self):
        esc = self.L['radiation_to_space'] + self.L['radiation_on_hardware'] + self.L['radiation_on_conductor']
        for c in self.all_cases():
            e = c['eight_W']
            self.assertAlmostEqual((e['radiation_to_space'] + e['radiation_on_closure_coils'] + e['radiation_on_other_hardware']) / esc, 1.0,
                                   delta=1e-9, msg=c['label'])
            self.assertLess(e['radiation_to_space'], self.L['radiation_to_space'] + 1.0)

    def test_thrust_energy_untouched_and_plasma_separate(self):
        for c in self.all_cases():
            e = c['eight_W']
            self.assertEqual(e['useful_jet'], self.L['jet'])
            self.assertEqual(e['plasma_on_hardware'], self.L['plume_to_hardware'])
            W_e = e['coil_cooling_loads']
            self.assertAlmostEqual(e['plasma_through_nozzle'] + W_e / c['eta_recovery'], self.L['plume_to_space'], delta=1.0)

    def test_heat_split_once(self):
        for c in self.all_cases():
            ch = c['coil_heat']
            self.assertLess(abs(ch['check_split_W']), 1e-6 * max(1.0, ch['xray_W']), msg=c['label'])
            per = sum(p['xray_W'] + p['neutron_W'] for p in ch['per_coil'])
            self.assertAlmostEqual(per / (ch['xray_W'] + ch['neutron_W']), 1.0, delta=1e-12)

    def test_circuits_add_only_coil_terms(self):
        for c in self.all_cases():
            ci, ch = c['circuits'], c['coil_heat']
            W_e = ch['cryo_input_W'] + ch['pump_electric_W']
            hot = ch['hot_W'] + ch['pump_hydraulic_W'] + W_e * (1 / c['eta_recovery'] - 1) + ch['other_hw_W']
            warm = ch['warm_radiation_W'] + ch['lifted_cold_W'] + ch['cryo_input_W'] + ch['pump_electric_W'] - ch['pump_hydraulic_W']
            self.assertAlmostEqual(ci['hot_added_W'], hot, delta=1e-6 * hot + 1)
            self.assertAlmostEqual(ci['warm_added_W'], warm, delta=1e-6 * warm + 1)

    def test_kept_cases_present(self):
        labs = [c['label'] for c in self.R['cases']]
        for k in ('11.9 GW', '15.5 GW', '30.1 GW'):
            self.assertTrue(any(k in x for x in labs), k)

    def test_coupled_with_nothing_reproduces_v4(self):
        ov = v4_overrides()
        R = solve_full(ov)
        z = {'xray_W': 0, 'neutron_W': 0, 'hot_W': 0, 'pump_hydraulic_W': 0, 'other_hw_W': 0}
        kv, Rc = LG.coupled(ov, R, z, {'warm_added_W': 0.0}, 0.0)
        self.assertAlmostEqual(C.fdp1.summary(Rc)['departure_t'], 42915.783853018824, delta=1e-3)

    def test_hoop_tension_matches_T03(self):
        c = LG.T03['designs']['C_W15']['loops'][0]
        T = LG.self_tension(c['current_MA'] * 1e6, c['radius_m'], c['winding_minor_m'])
        self.assertAlmostEqual(T / 6919.705140857786e6, 1.0, delta=0.01)

    def test_strut_share_matches_a_radial_strip(self):
        d, w, th0, th1 = 60.0, 0.5, 0.1, 0.4
        p0 = (d * math.sin(th0), d * math.cos(th0)); p1 = (d * math.sin(th1), d * math.cos(th1))   # chord; near an arc
        exact = w * d * (th1 - th0) / d ** 2 / (4 * math.pi)
        self.assertAlmostEqual(LG.strut_share(p0, p1, w) / exact, 1.0, delta=0.02)


class Injection(unittest.TestCase):
    def test_launcher_B_reproduces_T05(self):
        R = solve_full(v4_overrides())
        k = IN.kin(R, 45.0, 13700.0)
        self.assertAlmostEqual(k['muzzle_m_s'], 8808.2, delta=5)
        self.assertAlmostEqual(k['accelerator_m'], 289.0, delta=1.5)
        self.assertAlmostEqual(k['tip_xray_J_cm2'], 8.3, delta=0.1)

    def test_failed_candidates_stay_failed(self):
        r = read_json('injection.json')
        v = {c['label'][:2]: c['verdict'] for c in r['candidates']}
        self.assertEqual(v['B '], 'NOT DEFENSIBLE')
        self.assertTrue(all(c['verdict'] != 'CANDIDATE' for c in r['candidates'] if c['label'].startswith('B (')))


class Durability(unittest.TestCase):
    def test_deposited_energy_bounded_by_fluence(self):
        t = DU.attenuation()
        for m in ('W', 'C (CFC)'):
            for b in DU.BANDS:
                kind, kT = DU.BANDS[b]
                q, cum, _ = DU.deposition(t, DU.MAT[m], kind, kT, 4.0)
                self.assertLessEqual(cum(1.0), 4.0e4 * (1 + 1e-9))
                self.assertGreater(cum(1.0), 0.0)          # Compton-scattered energy leaves the local deposit (mu_en < mu)

    def test_spectrum_ordering_for_tungsten(self):
        t = DU.attenuation()
        soft = DU.assess(t, 'W', DU.MAT['W'], 'Planck 1 keV (soft surface)', 4.0)['surface_dT_K']
        hard = DU.assess(t, 'W', DU.MAT['W'], 'Wien 30 keV', 4.0)['surface_dT_K']
        self.assertGreater(soft, 10 * hard)


class Spine(unittest.TestCase):
    def test_uniform_cantilever_matches_analytic(self):
        import numpy as np
        L, EI, mpl, n = 100.0, 1e10, 1000.0, 41
        x = np.linspace(0, L, n); h = L / (n - 1)
        m = np.full(n, mpl * h); m[0] = m[-1] = mpl * h / 2
        K, M, free = SP.beam(x, {'EI': EI, 'GA': 1e30}, m, fix_root=True)
        M[1::2] = 1e-6
        f = SP.modes(K, M, free)[0]
        self.assertAlmostEqual(f / (1.8751 ** 2 / (2 * math.pi) * math.sqrt(EI / (mpl * L ** 4))), 1.0, delta=0.02)


class Canon(unittest.TestCase):
    def test_only_vertex_entry_changed(self):
        out = subprocess.run(['git', 'diff', '--name-only', 'a1c8246'], capture_output=True, text=True, cwd=ROOT).stdout.split()
        out += subprocess.run(['git', 'ls-files', '--others', '--exclude-standard'], capture_output=True, text=True, cwd=ROOT).stdout.split()
        bad = [p for p in out if not p.startswith('lab/variants/vertex-drive/')]
        self.assertEqual(bad, [])


if __name__ == '__main__':
    unittest.main(verbosity=1)
