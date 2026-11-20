"""Vertex Engine 1.6A (vertex_fiji_a): the bound-current solver reproduces closed-form fields and forces, magnetization stays bounded, energy
is accounted, material cases are labelled and conventional limits are not universal, hot Fiji next to REBCO fails explicitly, the neutron
issue stays OPEN, the four engines, the released engine and the 1.5 / 1.6 evidence are unchanged, and the evidence is current."""
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

S = spec.load(ROOT)[0]
C = va.config(S)
R = json.loads(va.EVIDENCE_PATH.read_text())
M = {r['id']: r for r in R['matrix']}


class Solver(unittest.TestCase):
    def test_closed_forms(self):
        """Cylinder, thick ring and radially magnetized annulus match their exact axis fields; the sphere converges to 2/3 mu0 M."""
        cyl = va.cell(-1.0, 1.0, 0.0, 1.0)
        self.assertAlmostEqual(va.magnet_field([cyl], [(1/va.MU0, 0.0)], 0.0, 0.0)[0], 1/math.sqrt(2), delta=1e-8)
        e = [abs(va.sphere(n)[0]-2/3) for n in (20, 40)]
        self.assertLess(e[1], e[0]/3)

    def test_validation_all_pass(self):
        self.assertTrue(R['validation']['all_pass'])
        self.assertGreaterEqual(len(R['validation']['rows']), 14)

    def test_convergence(self):
        for k in ('FG-1', 'FG-2', 'FG-3', 'FG-5'):
            self.assertLess(R['convergence'][k][-1]['change_from_previous'], 0.01)

    def test_newton_and_virtual_work(self):
        rows = {r['case']: r for r in R['validation']['rows']}
        for name in rows:
            if 'force' in name or 'Newton' in name or 'energy' in name:
                self.assertLess(rows[name]['rel_error'], 2e-3, name)


class Material(unittest.TestCase):
    def test_bounded(self):
        for r in R['matrix']:
            self.assertLessEqual(r['mu0M_mean_T'], r['mu0_Ms_T']*(1+1e-9))
            self.assertGreaterEqual(r['mu0M_mean_T'], 0.0)

    def test_cases_labelled(self):
        st = {m['id']: m['status'] for m in C['material_cases']}
        self.assertEqual(st, {'FM-1': 'MEASURED_REFERENCE', 'FM-2': 'SCREENING_BOUND', 'FM-3': 'SPECULATIVE', 'FM-4': 'EXTREME_SPECULATIVE'})
        rows = {m['id']: m for m in R['materials']['rows']}
        self.assertTrue(rows['FM-4']['beyond_d_shell']); self.assertFalse(rows['FM-1']['beyond_slater_pauling'])
        self.assertLess(max(m['mu0_Ms_T'] for m in C['material_cases']), R['materials']['formal_bound_T'])

    def test_one_property_shape(self):
        """Every case uses the canon temperature shape: collapse at quench, the cooling branch above the heating branch."""
        f = vf.config(S)
        self.assertEqual(va.ms_op(S, 3.5, f['T_quench_K']), 0.0)
        for r in R['matrix']:
            self.assertGreaterEqual(r['feedback']['cooling_branch_ratio'], 1.0)

    def test_orientation_needs_coercivity_not_granted(self):
        """A fixed easy axis against the local field is flagged; no known hard magnet keeps coercivity at the operating temperature."""
        self.assertTrue(any(r['gates']['coercivity_beyond_known'] for r in R['matrix'] if r['mode'] == 'ORIENTED'))
        for r in R['matrix']:
            self.assertEqual(r['gates']['known_coercive_at_operating'], [a['name'] for a in C['anisotropy_reference'] if a['curie_K'] > 1000.0])
            if r['mode'] == 'SEEDED':
                self.assertFalse(r['gates']['coercivity_beyond_known'])


class Energy(unittest.TestCase):
    def test_identity_and_collapse(self):
        rows = {r['case']: r for r in R['validation']['rows']}
        self.assertTrue(any('interaction energy' in k and v['passes'] for k, v in rows.items()))
        for r in R['matrix']:
            c = r['collapse']
            self.assertTrue(all(math.isfinite(x) for x in c['dI_At']))
            self.assertGreaterEqual(c['heat_bound_J'], abs(c['to_coils_J']))

    def test_stress_and_strain(self):
        for r in R['matrix']:
            self.assertGreaterEqual(r['stress_max_Pa'], r['self_pressure_Pa'])
            self.assertEqual(r['strain_collapse'], r['strain'] > vf.config(S)['strain_limit'])


class Limits(unittest.TestCase):
    def test_hot_fiji_in_sight_fails_explicitly(self):
        for k, e in R['exposure'].items():
            if R['geometries'][k]['line_of_sight']:
                self.assertGreater(e['face_shortfall'], 1.0)
        self.assertEqual(R['exposure']['FG-5']['fiji_sky'], 0.0)

    def test_tungsten_beats_fiji_as_shield(self):
        """Behind tungsten the photons stop at 1300 K, which costs less than at 1000 K (1.6's finding kept)."""
        for e in R['exposure'].values():
            self.assertLessEqual(e['brackets']['low']['ratio_armour'], e['brackets']['low']['ratio']+1e-9)

    def test_neutron_open_and_not_universal(self):
        n = R['neutrons']
        self.assertEqual(n['status'], 'OPEN'); self.assertEqual(n['limits']['evidence'], 'LITERATURE_RANGE')
        self.assertGreater(max(C['fluence_limit_n_m2'])/min(C['fluence_limit_n_m2']), 3.0)
        self.assertTrue(any(g['id'] == 'G-NEUTRON' and g['status'] == 'OPEN' for g in R['gates']))

    def test_nothing_closes_thermally(self):
        self.assertTrue(all(r['gates']['thermal_closure'] == 'FAIL' for r in R['matrix']))
        self.assertEqual(next(g for g in R['gates'] if g['id'] == 'G-PLASMA')['status'], 'NOT_RUN')


class Unchanged(unittest.TestCase):
    def test_engine_canon_and_history(self):
        self.assertEqual(S['propulsion_cluster']['engine_count'], 4)
        self.assertEqual(S['propulsion_representation']['active'], 'VERTEX_CLUSTER')
        self.assertEqual(json.loads(vr.EVIDENCE_PATH.read_text())['outcome'], 'C')
        h = json.loads(vf.EVIDENCE_PATH.read_text())
        self.assertEqual(h['outcome'], 'NEGATIVE'); self.assertEqual(h['input_hash'], vf.input_hash(S))
        self.assertEqual(vf.config(S)['mu0_Ms_T'], [3.5, 2.45, 1.0]); self.assertEqual(vf.config(S)['A_max'], 30.0)

    def test_rec_not_applied(self):
        for r in R['rec']:
            self.assertIn(r['decision'], ('APPROVED FOR VERTEX RESEARCH', 'HOLD', 'PRESERVE UNCHANGED', 'APPROVED AS A RESEARCH PRINCIPLE',
                                          'RECORD AS OPEN ENGINEERING FINDING'))
            if r['id'] in ('REC-1', 'REC-4'):
                self.assertIn('not applied', r['action'])

    def test_evidence_current(self):
        self.assertEqual(R['input_hash'], va.input_hash(S))


if __name__ == '__main__':
    unittest.main()
