"""T04 checks: the adapter reproduces the Atlas liner table, the new models meet their published anchors, ledgers close.

  python3 lab/variants/vertex-drive/studies/ignition/tests/test_ignition.py      # a few seconds; no ship solves
(The gain-cliff reproduction needs ship solves and is checked by ignition.py's exit code.)
"""
import json
import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import targets as tg          # noqa: E402
import ignition as ig         # noqa: E402


class Anchors(unittest.TestCase):
    def test_fermi_pressure_DT(self):
        # textbook: degenerate D-T at 1000 g/cm3 is about 2.2e5 Mbar (2.2 rho^(5/3) Mbar)
        self.assertAlmostEqual(tg.fermi_pressure_Pa('DT', 1e6) / 1e11 / 2.2e5, 1.0, delta=0.05)

    def test_DT_hotspot_boundary_near_published(self):
        m = min((r for r in tg.hotspot_boundary('DT', [6.0, 8.0, 10.0, 12.0, 15.0]) if r['rhoR_g_cm2']), key=lambda r: r['rhoR_g_cm2'])
        self.assertTrue(0.1 < m['rhoR_g_cm2'] < 0.4 and 5 <= m['T_keV'] <= 15, m)

    def test_DT_calibrated_fast_ignition_energy(self):
        # Atzeni 1999 class: about 10-20 kJ in the hot spot at 300 g/cm3
        E = tg.isochoric_hotspot_J('DT', 0.6, 12.0, 3e5)
        self.assertTrue(5e3 < E < 3e4, E)

    def test_DHe3_ignites_only_above_30_keV(self):
        w = tg.ideal_ignition_window('DHe3')
        self.assertTrue(25 <= w['T_min_keV'] <= 45, w)

    def test_tamper_k0_is_untamped(self):
        for mu in (0.0, 0.1, 1.0):
            self.assertEqual(tg.tamper_time_factor(mu, 0.0), 1.0)


class Reproduction(unittest.TestCase):
    def test_liner_table_reproduced(self):
        L = ig.liner_with_inertia(ks=(0.0,))
        ref = {r['rhoR_g_cm2']: r for r in ig.committed()['cases']['liner_study']['rows']}
        for r in L['tables']['k=0']:
            self.assertAlmostEqual(r['ve0_km_s'], ref[r['rhoR_g_cm2']]['ve0_km_s'], places=6)
            self.assertEqual(r['best_mu'], ref[r['rhoR_g_cm2']]['best_mu'])

    def test_pulse_ledger_sums_to_fusion(self):
        from engineering import config
        cfg = config.load('baseline'); fb = config.fourburn(cfg); sc = config.scenario(cfg, fb)
        for rr in (10.0, 300.0, 904.5):
            for mu in (0.0, 0.1, 1.0):
                q = fb['architectures']._pulse(sc, 'optimistic', rr, mu)
                self.assertAlmostEqual(sum(q['ledger'].values()), 1.0, places=9)


if __name__ == '__main__':
    unittest.main()
