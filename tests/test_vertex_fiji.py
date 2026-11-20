"""Vertex Engine 1.6 (vertex_fiji): the Fiji constitutive model stays bounded, fields come from currents plus magnetization, forces and
energies are accounted, the fusion levers keep the 1.5 physics, no heat is credited twice or lost, material and Jc limits hold, the four
engines and the released engine are unchanged, and the evidence is current."""
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'/'wayfarer'))
import spec  # noqa: E402
import vertex_fiji as vf  # noqa: E402
import vertex_radiation as vr  # noqa: E402
import vertex_structure as vs  # noqa: E402

S = spec.load(ROOT)[0]
C = vf.config(S)
R = json.loads(vf.EVIDENCE_PATH.read_text())
V = {v['id']: v for v in R['variants']}


class Material(unittest.TestCase):
    def test_magnetization_bounded_and_seeded(self):
        for k in (0, 1, 2):
            top = C['mu0_Ms_T'][k]/vf.MU0
            for T in range(200, 1600, 20):
                for B in (0.0, 0.1, 5.0, 30.0):
                    for br in ('heating', 'cooling'):
                        M, _ = vf.magnetization(C, float(T), B, br, k=k)
                        self.assertGreaterEqual(M, 0.0); self.assertLessEqual(M, top*(1+1e-12))
                        if B == 0.0:
                            self.assertEqual(M, 0.0)

    def test_rises_with_temperature_then_collapses(self):
        Ms = [vf.magnetization(C, float(T), 5.0)[0] for T in range(int(C['T_activation_K']), int(C['T_saturation_K'])+1, 10)]
        self.assertTrue(all(b >= a for a, b in zip(Ms, Ms[1:])))
        self.assertAlmostEqual(Ms[-1]/Ms[0], C['A_max'], delta=1e-6)
        self.assertEqual(vf.magnetization(C, C['T_quench_K'], 5.0)[0], 0.0)
        self.assertEqual(vf.state(C, C['T_quench_K'])[1], 'COLLAPSED')
        self.assertEqual(vf.state(C, C['T_operating_K'], strain=2*C['strain_limit'])[1], 'COLLAPSED')

    def test_hysteresis(self):
        for T in range(int(C['T_release_K']), int(C['T_saturation_K']), 25):
            self.assertGreaterEqual(vf.state(C, float(T), 'cooling')[0], vf.state(C, float(T), 'heating')[0])

    def test_canon_law_shape(self):
        """The model's temperature shape is the canon smoothstep; A_B(1000 K) is the workbook's 26.34."""
        self.assertAlmostEqual(vf.lattice_law(C, 1000.0), 26.34, delta=0.01)
        f = lambda T: vf.state(C, T)[0]*C['A_max']
        for T in (600.0, 700.0, 900.0, 1000.0, 1100.0, 1200.0):
            self.assertAlmostEqual(f(T), vf.lattice_law(C, T), delta=1e-9)

    def test_inverse_magnetocaloric(self):
        th = vf.thermodynamics(C)
        self.assertGreater(th['dM_dT_A_mK'], 0.0); self.assertGreater(th['isothermal_heat_J_m3'], 0.0)
        self.assertAlmostEqual(th['seed_work_J_m3'], th['M_A_m']*5.0, delta=1e-6*th['seed_work_J_m3'])


class Field(unittest.TestCase):
    def test_kernel_matches_spherical_shell(self):
        """Rings filling a shell 2-6 m around the target reproduce G = K ln(ro/ri) (exact dipole kernel, optimal orientation)."""
        rings = []; n = 60; ri, ro = 2.0, 6.0
        for i in range(n):
            for j in range(n):
                rr = ri+(i+0.5)*(ro-ri)/n; th = (j+0.5)*math.pi/n
                rings.append((rr*math.cos(th), rr*math.sin(th), 2*math.pi*rr*math.sin(th)*rr*(ro-ri)/n*math.pi/n))
        g = sum(vf.kernel(x, r, 0.0)[1]*dV/vf.MU0 for x, r, dV in rings)
        self.assertAlmostEqual(g/vf.shell_factor(ri, ro), 1.0, delta=0.01)
        self.assertAlmostEqual(vf.K_SPHERE, 1.3801, delta=1e-4)

    def test_field_linear_and_orientation_matters(self):
        g, ga = vf.geometry_factor(vf.liners(S, 0.2), vs.coils(S)[0]['x'])
        self.assertGreater(g, 0.0); self.assertLess(abs(ga), g)
        F = R['field']['targets']['burn']['cases']['0.2']
        self.assertAlmostEqual(F['B_fiji_T'][0]/F['B_fiji_T'][2], C['mu0_Ms_T'][0]/C['mu0_Ms_T'][2], delta=1e-9)

    def test_force_is_energy_gradient(self):
        """F_x on a magnetized ring in the coil field equals d(M.B)/dx integrated (finite difference of the interaction energy)."""
        cs = vs.coils(S); I = vs.currents(S, 'NOMINAL'); ring = vf.liners(S, 0.2)[3]; M = 2e6; xt = -10.0; h = 1e-2
        def W(dx):
            tot = 0.0
            for x, r, dV in vf.cells(dict(ring, x=ring['x']+dx), 4):
                (ux, ur), _, _ = vf.kernel(x-dx, r, xt); bz, br = vf.coil_B(cs, I, x, r); tot += M*(ux*bz+ur*br)*dV
            return tot
        F = 0.0
        for x, r, dV in vf.cells(ring, 4):
            (ux, ur), _, _ = vf.kernel(x, r, xt)
            mB = lambda xx: (lambda b: M*(ux*b[0]+ur*b[1]))(vf.coil_B(cs, I, xx, r))
            F += (mB(x+1e-3)-mB(x-1e-3))/2e-3*dV
        self.assertAlmostEqual(F/((W(h)-W(-h))/(2*h)), 1.0, delta=0.01)

    def test_canon_needs_more_than_the_bound(self):
        sh = R['field']['targets']['burn']['shell']
        self.assertGreater(min(x['mu0Ms_for_canon_T'] for x in sh.values()), C['mu0_Ms_T'][0])


class Fusion(unittest.TestCase):
    def test_levers_off_reproduce_1_5(self):
        low = next(x for x in S['vertex_radiation']['cases'] if x['id'] == 'LOW')
        a = vf.analytic(S, low, 0.5); b = vr.analytic_case(S, low, 0.5)
        self.assertEqual(a['photon_share'], b['photon_share'])
        self.assertAlmostEqual(R['fusion']['reference']['photon_share'], R['fusion']['reference']['released'], places=12)
        self.assertIs(vr.sigma_v.__name__, 'sigma_v')                  # levers restored

    def test_polarization_labelled_and_bounded(self):
        self.assertIn('THEORETICAL', R['fusion']['polarization_note'])
        for k in (0, 1, 2):
            self.assertLessEqual(vf.pol_factor(C, k), 1.5)
        self.assertEqual(C['dd_factor'][1], 1.0)

    def test_exchange_explicit(self):
        """Even with every product's electron share channelled, e-i exchange heats the electrons: the floor stays above zero."""
        f = vf.floor(C, 150.0, channel=1.0)
        self.assertGreater(f['exchange_share'], 0.0); self.assertGreater(f['photon_share'], 0.01); self.assertLess(f['Te_over_Ti'], 1.0)

    def test_ledgers_close(self):
        for v in V.values():
            self.assertAlmostEqual(v['photon_share']+v['neutron_share']+v['charged_share'], 1.0, places=12)
            e = v['per_engine']
            self.assertAlmostEqual((e['exhaust_W']+e['hardware_W']+e['escaping_W'])/e['fusion_W'], 1.0, places=9)


class Closure(unittest.TestCase):
    def test_reproduces_1_5(self):
        r15 = vf.r15()['thermal']['cases']['LOW']
        self.assertAlmostEqual(V['F0']['ratio'][0]/r15['RADIATION_low']['ratio'], 1.0, places=9)
        self.assertAlmostEqual(V['F0']['ratio'][1]/r15['RADIATION_high']['ratio'], 1.0, places=9)

    def test_no_heat_lost_or_double_counted(self):
        """A liner moves heat to another temperature; it does not remove it. No configuration takes radiator credit for reaction mass."""
        f0 = vf.closure(S, 'a', 1.0, 1.0); f1 = vf.closure(S, 'b', 1.0, 1.0, liner=dict(T_K=1000.0, n_share=0.5))
        for b in ('low', 'high'):
            x, y = f0['brackets'][b], f1['brackets'][b]
            self.assertAlmostEqual(x['hot_W']+x['cold_W']+x['warm_W'], y['hot_W']+y['cold_W']+y['warm_W'], delta=1e-6*x['hot_W'])
        for v in V.values():
            self.assertEqual(v['per_engine']['reaction_mass_W'], 0.0)

    def test_four_engines(self):
        self.assertEqual(S['propulsion_cluster']['engine_count'], 4)
        f = vf.closure(S, 'a', 1.0, 1.0)['brackets']['low']
        self.assertAlmostEqual(f['four_W'], 4*f['reject_W'], delta=1e-6*f['four_W'])

    def test_nothing_closes(self):
        self.assertFalse(any(v['closes'] for v in V.values()))
        self.assertEqual(R['outcome'], 'NEGATIVE')


class Limits(unittest.TestCase):
    def test_speculative_material_blocked(self):
        row = next(m for m in R['materials'] if m['material'] == 'MAT-W-FIJI01')
        self.assertEqual(row['max_service_temperature'], 'SPECULATIVE_BLOCKED')

    def test_jc_finite_and_falls_with_field(self):
        for r in R['rebco']['rows']:
            self.assertTrue(all(math.isfinite(x) and x > 0 for x in r['Jc_A_m2']))
            self.assertLessEqual(max(r['margin_with_fiji']), max(r['margin']))
            self.assertLess(r['lifetime_s'][0], C['burn_time_s'])


class Unchanged(unittest.TestCase):
    def test_engine_and_canon_unchanged(self):
        self.assertEqual(S['propulsion_representation']['active'], 'VERTEX_CLUSTER')
        self.assertEqual(vr.config(S)['verdict'], 'PROPULSION_FEASIBILITY_BLOCKED')
        self.assertEqual(json.loads(vr.EVIDENCE_PATH.read_text())['outcome'], 'C')

    def test_evidence_current(self):
        self.assertEqual(R['input_hash'], vf.input_hash(S))


if __name__ == '__main__':
    unittest.main()
