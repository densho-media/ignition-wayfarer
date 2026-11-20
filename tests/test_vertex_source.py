"""Vertex Engine 1.6B (vertex_source): the reactivity extension reproduces the Bosch-Hale fit, every case conserves energy and partitions its
products, the 1.5 reference reproduces, the source floors are computed (never prescribed), the allowable leakage follows the canon radiator
allocation, neutrons stay a separate gate, the verdict follows the results, the architecture and the earlier evidence are unchanged, and the
evidence is current."""
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'/'wayfarer'))
import spec  # noqa: E402
import vertex_fiji as vf  # noqa: E402
import vertex_fiji_a as va  # noqa: E402
import vertex_radiation as vr  # noqa: E402
import vertex_source as vso  # noqa: E402

S = spec.load(ROOT)[0]
C = vso.config(S)
R = json.loads(vso.EVIDENCE_PATH.read_text())


class Source(unittest.TestCase):
    def test_reactivity_extension(self):
        """Cross-section integrals match the reactivity fit inside its range; above it D-D rises (the held fit undercounts it)."""
        for T in (20.0, 60.0, 100.0):
            for r in ('DT', 'DDn', 'DDp'):
                self.assertAlmostEqual(vso.sv_xs(r, T, 2000)/vr.sigma_v(r, T), 1.0, delta=0.03)
        self.assertGreater(vso.sv(S, 'DDn', 200.0), 1.5*vr.sigma_v('DDn', 200.0))
        self.assertTrue(R['validation']['all_pass'])

    def test_bi_temperature_reactivity(self):
        self.assertAlmostEqual(vso.t_eff('D', 100.0, 'He3', 100.0), 100.0, places=9)
        self.assertAlmostEqual(vso.t_eff('D', 0.0, 'He3', 100.0), 100.0*vr.M_ION['D']/(vr.M_ION['D']+vr.M_ION['He3']))

    def test_energy_and_partition(self):
        for cs in R['cases'].values():
            for b in cs['brackets'].values():
                for row in (b['best'], b['radiative']):
                    if row:
                        self.assertLess(abs(row['energy_error']), 1e-9)
                        self.assertLess(abs(row['partition_error']), 1e-9)
                        self.assertAlmostEqual(row['charged_share']+row['neutron_share']+row['gamma_share'], 1.0, places=5)

    def test_reference_reproduced(self):
        rep = R['cases']['S0']['reproduction']
        self.assertTrue(rep['matches'])
        self.assertGreater(rep['electron_imbalance_share'], 0.0)   # the prescribed state needs an electron sink 1.5 did not model

    def test_floor_computed_not_prescribed(self):
        """1.6's floor re-derived with quasineutral electrons is lower; no case's photon share is below its own computed balance."""
        fa = R['floor_audit']
        self.assertAlmostEqual(fa['released_1_6'], json.loads(vf.EVIDENCE_PATH.read_text())['fusion']['best_floor_polarized']['photon_share'], delta=1e-5)
        self.assertGreater(fa['factor'], 1.0)
        for cs in R['cases'].values():
            for b in cs['brackets'].values():
                if b['best']:
                    self.assertGreater(b['best']['photon_share'], 0.01)
                    self.assertGreaterEqual(b['best']['electron_imbalance_share'], -1e-9)

    def test_auxiliary_costs_counted(self):
        """Hot-ion states pay their exchange: a case with auxiliary heating has finite gain and less useful energy than its exhaust."""
        for cs in R['cases'].values():
            for b in cs['brackets'].values():
                r = b['best']
                if r and r['aux_share'] > 0:
                    self.assertLess(r['useful_share'], r['exhaust_share'])
                    self.assertTrue(math.isfinite(r['gain']))


class Interface(unittest.TestCase):
    def test_allocation_is_canon(self):
        a = R['allocation']; q = S['physics']['operating_point']
        self.assertAlmostEqual(a['drive_W']/(q['hot_share']*a['installed_W']), 1.0, places=5)
        self.assertLess(a['drive_W'], a['installed_W'])

    def test_leakage_ordering(self):
        """Colder classes allow less leakage; the computed 1.4 leakage exceeds every allowance."""
        al = [x['mission']['allowed_share'] for x in R['interface']['allowable']]
        self.assertEqual(al, sorted(al, reverse=True))
        self.assertGreater(R['interface']['best_computed_leak'], max(al))

    def test_coil_sky_is_a_floor(self):
        g = R['geometry']
        self.assertGreater(g['coil_sky'], 0.0); self.assertLessEqual(g['coil_sky'], g['hardware_sky_mesh']+1e-9)


class Budget(unittest.TestCase):
    def test_conservation(self):
        for r in R['combined']['rows']:
            if 'energy_error' in r:
                self.assertLess(abs(r['energy_error']), 1e-6)

    def test_nonphoton_failure_reported(self):
        """A case whose neutrons, leakage and losses alone exceed the drive share fails SR-1 instead of getting a photon allowance."""
        for r in R['combined']['rows']:
            if r.get('sr1_status') == 'FAIL_NONPHOTON':
                self.assertIsNone(r['sr1_photon_share']); self.assertGreater(r['nonphoton_ratio'], 1.0)

    def test_no_pass_by_less_thrust(self):
        op = R['mission']['operating_point']
        for r in R['mission']['rows']:
            if 'thrust_N' in r:
                self.assertEqual(r['thrust_N'], op['thrust_N']); self.assertGreaterEqual(r['fusion_four_W'], r['jet_W'])

    def test_map_classes(self):
        for p, cl in R['feasibility']['counts'].items():
            self.assertEqual(set(cl), set(vso.CLASSES))
            for n, closing in cl.values():
                self.assertLessEqual(closing, n)


class Verdict(unittest.TestCase):
    def test_verdict_follows_results(self):
        fe = R['feasibility']['best_closing'].get('mission')
        if R['outcome'] == 'A':
            self.assertIn(fe['cls'], ('SUPPORTED', 'PLAUSIBLE_EXTRAPOLATION'))
        if fe and fe['cls'] not in ('SUPPORTED', 'PLAUSIBLE_EXTRAPOLATION', 'SPECULATIVE_MOTIVATED'):
            self.assertIn(R['outcome'], ('C', 'D'))
        self.assertEqual(R['outcome'], C['outcome'])

    def test_neutrons_separate_gate(self):
        self.assertTrue(any(g['id'] == 'R16B-6' for g in R['gates']))
        self.assertEqual(R['neutrons']['limits']['evidence'], 'LITERATURE_RANGE')
        self.assertEqual(len(R['answers']), 10)


class Unchanged(unittest.TestCase):
    def test_architecture_and_history(self):
        self.assertEqual(S['propulsion_cluster']['engine_count'], 4)
        self.assertEqual(S['propulsion_representation']['active'], 'VERTEX_CLUSTER')
        self.assertEqual(json.loads(vr.EVIDENCE_PATH.read_text())['outcome'], 'C')
        self.assertEqual(json.loads(vf.EVIDENCE_PATH.read_text())['input_hash'], vf.input_hash(S))
        self.assertEqual(json.loads(va.EVIDENCE_PATH.read_text())['input_hash'], va.input_hash(S))
        self.assertTrue(R['ledger']['all_reproduced'])

    def test_rec_not_applied(self):
        for r in R['rec']:
            if r['id'] in ('REC-1', 'REC-4'):
                self.assertIn('not applied', r['action'])

    def test_evidence_current(self):
        self.assertEqual(R['input_hash'], vso.input_hash(S))


if __name__ == '__main__':
    unittest.main()
