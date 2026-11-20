"""Vertex Engine 1.8 (vertex_adaptive): the stowed ring clears its neighbour and stays inside today's envelope, every moved geometry is
re-solved to the canon stop field, a closed winding cannot open as a petal without joints and those joints obey I^2 R and L/R, the
alignment error field is first order in the offset, the concepts respect the cluster clearance, and the evidence is current."""
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'/'wayfarer'))
import spec  # noqa: E402
import vertex_adaptive as vad  # noqa: E402
import vertex_dynamic as vd  # noqa: E402

S = spec.load(ROOT)[0]
R = json.loads(vad.EVIDENCE_PATH.read_text())


class Mechanism(unittest.TestCase):
    def test_stowed_ring_clears_and_fits(self):
        C = R['carriages']; c = vad.config(S)
        for n, d in C['stow_stroke_m'].items():
            self.assertGreater(d, 0.0)
        self.assertLess(C['rail']['envelope_change_m'], 0.05)
        stowed = next(r for r in C['rows'] if r['case'] == 'STOWED')
        self.assertLess(stowed['length_m'], R['audit']['envelope']['length_m'])
        self.assertGreater(c['stow_gap_m'], 0.0)

    def test_stop_field_held(self):
        B0 = R['alignment']['B_burn_T']
        for r in R['carriages']['rows']:
            self.assertAlmostEqual(r['B_burn_T']/B0, 1.0, places=5)

    def test_petals_need_joints(self):
        P = R['petals']
        for r in P['rows']:
            self.assertGreater(r['strain_if_continuous'], P['rebco_strain_limit'])
            self.assertGreater(r['joints'], 0)
            taus = [j['tau_s'] for j in r['joint_rows']]
            self.assertEqual(taus, sorted(taus, reverse=True))           # more resistance, faster decay
            for j in r['joint_rows']:
                self.assertAlmostEqual(j['cold_W'], r['joints']*P['lead_current_A']**2*j['joint_ohm'], delta=1e-5*j['cold_W'])
                self.assertEqual(j['persistent_ok'], j['joint_ohm'] <= r['joint_ohm_needed'])

    def test_alignment_first_order(self):
        A = R['alignment']
        for row in A['rows']:
            t = row['tilt_rad']; d = A['offsets_m']
            for k in range(1, len(d)):
                self.assertAlmostEqual(t[k]*d[0], t[0]*d[k], delta=1e-9+1e-5*abs(t[0]*d[k]))
        self.assertEqual(next(r for r in A['rows'] if r['name'] == 'L2')['B_perp_T_per_mm'], 0.0)   # L2 sits in the burn plane

    def test_concepts_inside_cluster_clearance(self):
        kmax = R['petals']['k_max']; outer = R['audit']['envelope']['max_radius_m']
        for r in R['concepts']['rows']:
            self.assertLessEqual(r['envelope_m'], outer*kmax+1e-6)


class Unchanged(unittest.TestCase):
    def test_earlier_evidence_and_architecture(self):
        self.assertEqual(json.loads(vd.EVIDENCE_PATH.read_text())['input_hash'], vd.input_hash(S))
        self.assertEqual(S['propulsion_cluster']['engine_count'], 4)
        self.assertEqual(R['audit']['instances']['count'], 4)

    def test_evidence_current(self):
        self.assertEqual(R['input_hash'], vad.input_hash(S))


if __name__ == '__main__':
    unittest.main()
