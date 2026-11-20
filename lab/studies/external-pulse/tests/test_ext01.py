"""EXT-01 lab tests (not CI): energy and momentum conservation, the capture bounds, the mission reproduction, the evidence.
    python3 lab/studies/external-pulse/tests/test_ext01.py"""
import itertools
import json
import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import ext01 as E  # noqa: E402

P = E.params(); REF = E.reference()
E._EPS.append(REF['eps'])


def cases(concept, n=400):
    ax = E._axes(P, concept); keys = list(ax)
    for k, vals in enumerate(itertools.product(*(ax[x] for x in keys))):
        if k % 97 == 0:
            yield E.case(P, concept, REF, dict(zip(keys, vals)))
        if k > 97*n:
            return


class Conservation(unittest.TestCase):
    def test_energy_ledger_closes(self):
        for c in 'ABC':
            for p in cases(c):
                L = E.ledger(c, p, 0.5*E.v_cap(p), REF)
                self.assertAlmostEqual(sum(L['hw'].values())+sum(L['esc'].values()), 1.0, places=12)
                for v in list(L['hw'].values())+list(L['esc'].values()):
                    self.assertGreaterEqual(v, -1e-15)

    def test_exhaust_carries_its_kinetic_energy(self):
        """The rocket's jet energy 1/2 m v_eff^2 never exceeds the kinetic energy that actually leaves (Jensen; e <= 1). Debris momentum only:
        absorbed photon momentum comes with absorbed, not exhausted, energy."""
        for c in 'ABC':
            for p in cases(c):
                for s in (0.1, 1.0):
                    L = E.ledger(c, p, s*E.v_cap(p), REF)
                    self.assertLessEqual(0.5*L['m_exp']*L['v_debris']**2, L['exhaust_KE']*(1+1e-12))

    def test_fuel_mass_within_debris(self):
        """At the speed cap the debris is exactly the pulse fuel: m_d = Y / (b eps)."""
        for c in 'ABC':
            for p in cases(c, 50):
                L = E.ledger(c, p, E.v_cap(p), REF)
                self.assertAlmostEqual(L['m_d']*p['burnup']*REF['eps'], 1.0, places=9)


class Bounds(unittest.TestCase):
    def test_isotropic_capture_bound(self):
        """Isotropic debris on a cone: impulse share sin^2(theta)/4, so v_eff <= (1 + e) v_d / 4 at a full hemisphere."""
        p = dict(E.case(P, 'A', REF, dict(case='LOW', burnup=0.8, photon_conversion=0.0, directed='iso', restitution=0.5,
                                          neutron_absorbed=0.1, rate_Hz=10.0, burn_fraction=0.1, half_angle_deg=60.0,
                                          stagnation_to_plate=0.5, cooling='radiator')))
        L = E.ledger('A', p, 1e7, REF)
        self.assertAlmostEqual(L['v_debris']/1e7, 1.5*math.sin(math.radians(60.0))**2/4.0, places=6)

    def test_directed_pulse_optimum_is_half(self):
        """An isolated pulse has no net momentum: v_eff at the burnup cap peaks at beta = 1/2, where it equals (1 + e)/2 x the
        isotropic speed cap."""
        base = dict(case='LOW', burnup=0.8, photon_conversion=0.0, restitution=1.0, neutron_absorbed=0.1, rate_Hz=10.0,
                    burn_fraction=0.1, reach=1.0, thickness_over_radius=0.005, leak=0.0, capture_deg=60.0)
        best = {}
        for b in (0.3, 0.4, 0.5, 0.6, 0.7):
            p = E.case(P, 'B', REF, dict(base, directed=str(b))); best[b] = E.ledger('B', p, E.v_cap(p), REF)['v_debris']
        self.assertEqual(max(best, key=best.get), 0.5)
        iso = E.case(P, 'B', REF, dict(base, directed='iso'))
        self.assertAlmostEqual(best[0.5]/E.v_cap(iso), 1.0, places=6)

    def test_coil_sky_share_is_the_torus_band(self):
        """With the burn in the coil plane (L -> 0) the ring of thickness w = 2a covers a/R of the sky (vertex_radiation's test)."""
        g_h, *_ = E.geometry('B', dict(capture_deg=90.0, reach=1e-9, thickness_over_radius=0.2, directed='iso'))
        self.assertAlmostEqual(g_h, 0.1, places=9)

    def test_mission_reproduces_operating_point(self):
        M = E.mission(REF, REF['ve_ref'], 0.0, 0.1)
        self.assertAlmostEqual(M['departure_kg']/REF['departure_kg'], 1.0, places=9)
        self.assertAlmostEqual(M['propellant_kg']/REF['propellant_kg'], 1.0, places=9)
        self.assertIsNone(E.mission(REF, 0.99*REF['dv_total']/math.log(1.0+1.0/REF['tank_fraction']), 0.0, 0.1))

    def test_heat_law(self):
        """kappa allowed at the reference exhaust velocity: 2 f_k mu^2 phi T H / (v^2 P), quadratic in mu."""
        k1 = E.heat_law(REF, P, mu=1.0); k2 = E.heat_law(REF, P, mu=2.0)
        self.assertAlmostEqual(k2/k1, 4.0, places=9)


class Evidence(unittest.TestCase):
    def test_results_current(self):
        R = json.loads(E.RESULTS.read_text())
        self.assertEqual(R['input_hash'], E.input_hash(E.spec.load(E.ROOT)[0]))

    def test_no_concept_closes_on_established_physics(self):
        R = json.loads(E.RESULTS.read_text())
        self.assertEqual(R['verdict']['established'], [])
        for c, v in R['concepts'].items():
            for st in v['summary']['ladder'][2:]:
                self.assertEqual(st['closes'], 0, c)

    def test_vertex_unchanged(self):
        import vertex_radiation as vr
        S = E.spec.load(E.ROOT)[0]
        self.assertEqual(vr.config(S)['verdict'], 'PROPULSION_FEASIBILITY_BLOCKED')
        self.assertEqual(json.loads(E.EVIDENCE.read_text())['outcome'], 'C')


if __name__ == '__main__':
    unittest.main()
