"""Vertex Engine 1.7 (vertex_dynamic): motion cannot act inside a pulse, rotation of an axisymmetric crown changes no field and stays
inside its band strength, storage and conversion obey their energy and Carnot bounds, deployment keeps the field energy and the cluster
spacing, the mission-point budget reproduces 1.6B and holds the canon thrust, the verdict follows the results, the earlier evidence and
the architecture are unchanged, and the evidence is current."""
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'/'wayfarer'))
import spec  # noqa: E402
import vertex_dynamic as vd  # noqa: E402
import vertex_fiji as vf  # noqa: E402
import vertex_fiji_a as va  # noqa: E402
import vertex_source as vso  # noqa: E402

S = spec.load(ROOT)[0]
R = json.loads(vd.EVIDENCE_PATH.read_text())


class Physics(unittest.TestCase):
    def test_motion_is_quasi_static(self):
        """Every rim modulates the field far below the pulse rate and moves less than a millimetre while the exhaust crosses the nozzle."""
        T = R['timescales']
        for m in T['mechanical']:
            self.assertLess(m['modulation_over_pulse'], 0.01)
            self.assertLess(m['travel_in_transit_m'], 1e-3)
        self.assertGreater(T['rmf']['gap'], 1e3)
        self.assertLess(max(T['switch_s']), T['pulse_period_s']['mission'])

    def test_crown_mechanics(self):
        cr = R['crown']
        lim = [r for r in cr['rows'] if abs(r['rim_m_s']-cr['v_max_m_s']) < 1e-6][0]
        self.assertTrue(lim['stress_ok'])
        self.assertAlmostEqual(lim['KE_J'], 0.5*cr['mass_kg_each']*lim['rim_m_s']**2, delta=1e-5*lim['KE_J'])

    def test_storage_and_cycles_bounded(self):
        d = R['dynamo']
        self.assertGreater(d['switched']['required_recovery'], max(d['switched']['literature']))
        for c in d['fiji_cycle']:
            self.assertLess(c['efficiency'], c['carnot'])
        self.assertGreater(d['thermodynamics']['cost_at_Th'], 1.0)      # Fiji runs below the radiator temperature
        self.assertGreater(d['sustained_flywheel_kg']['1'], R['audit']['mass']['departure_kg'])   # stored is not generated

    def test_deployment_scaling(self):
        p = R['petals']
        for r in p['rows']:
            self.assertEqual(r['stored_factor'], 1.0)
            if r['k'] > 1:
                self.assertLess(r['coil_factor'], 1.0); self.assertLess(r['hardware_factor'], 1.0)
        self.assertTrue(p['best']['fits'])
        self.assertLessEqual(p['best']['k'], p['k_max']+1e-9)


class Budget(unittest.TestCase):
    def test_reproduces_1_6b(self):
        self.assertTrue(R['budget']['reproduces_1_6b'])
        for r in R['budget']['rows']:
            self.assertLess(abs(r['energy_error']), 1e-6)

    def test_no_pass_by_less_thrust(self):
        b = R['audit']['power']
        for r in R['mission']['rows']:
            self.assertAlmostEqual(r['thrust_N']/(R['audit']['loads']['thrust_mission_N']*4), 1.0, delta=1e-5)
            self.assertAlmostEqual(r['ve_m_s']/b['ve_m_s'], 1.0, delta=1e-5)

    def test_motion_never_beats_its_own_factors(self):
        """A candidate improves a configuration by no more than the deposition it removes and the sink it adds allow."""
        for r in R['budget']['rows']:
            self.assertGreaterEqual(r['improvement'], 1.0-1e-9)
            self.assertLess(r['improvement'], 2.0)

    def test_radiator_capacity_is_canon(self):
        rd = R['audit']['radiators']
        self.assertAlmostEqual(rd['recomputed_W']/rd['installed_W'], 1.0, places=6)


class Verdict(unittest.TestCase):
    def test_verdict_follows_results(self):
        v = R['verdict']
        if v['hybrid_ratio'] > 1:
            self.assertNotEqual(v['outcome'], 'A')
        self.assertEqual(v['outcome'], vd.config(S)['outcome'])
        self.assertTrue(all(x['status'] == 'PROPOSED_FOR_AUTHOR_APPROVAL' for x in v['speculative']))


class Unchanged(unittest.TestCase):
    def test_architecture_and_history(self):
        self.assertEqual(S['propulsion_cluster']['engine_count'], 4)
        self.assertEqual(S['propulsion_representation']['active'], 'VERTEX_CLUSTER')
        self.assertEqual(json.loads(vso.EVIDENCE_PATH.read_text())['input_hash'], vso.input_hash(S))
        self.assertEqual(json.loads(vf.EVIDENCE_PATH.read_text())['input_hash'], vf.input_hash(S))
        self.assertEqual(json.loads(va.EVIDENCE_PATH.read_text())['input_hash'], va.input_hash(S))

    def test_evidence_current(self):
        self.assertEqual(R['input_hash'], vd.input_hash(S))


if __name__ == '__main__':
    unittest.main()
