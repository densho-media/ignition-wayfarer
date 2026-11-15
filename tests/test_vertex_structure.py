"""Vertex Engine 1.2 structural validation (owner brief 2026-11-14): field model, frame FE, material access and the sized members' invariants.
Pure modules only. The physics checks are closed forms; the sizing checks protect the physical invariant that every drawn member carries
the design-case loads, and that nothing is reported as sized that is not."""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src/wayfarer'))
from spec import load
import fe_frame as fe
import material_physics as mp
import vertex_engine as ve
import vertex_structure as vs

S = load(ROOT)[0]
_SIZING = {}


def sizing():
    if not _SIZING:
        _SIZING['s'] = vs.sizing(S)
    return _SIZING['s']


class FieldTests(unittest.TestCase):
    def test_loop_field_matches_the_axis_formula(self):
        a, I = 2.0, 1.0e6
        for z in (0.0, 0.7, 3.0):
            self.assertAlmostEqual(vs.loop_field(a, I, 0.0, z)[1], vs.MU0*I*a*a/(2*(a*a+z*z)**1.5), delta=1e-12)

    def test_loop_field_far_away_is_a_dipole(self):
        a, I, r = 1.0, 1.0e6, 200.0
        m = I*math.pi*a*a
        self.assertAlmostEqual(vs.loop_field(a, I, r, 0.0)[1]/(-vs.MU0*m/(4*math.pi*r**3)), 1.0, places=3)

    def test_mutual_inductance_is_symmetric_and_matches_flux(self):
        M = vs.mutual(2.0, 3.0, 1.5)
        self.assertAlmostEqual(M, vs.mutual(3.0, 2.0, -1.5), delta=1e-15)
        # flux of loop 1 (1 A) through loop 2 by direct integration of B_z over its disc
        n = 4000; flux = sum(vs.loop_field(2.0, 1.0, (i+0.5)*3.0/n, 1.5)[1]*2*math.pi*(i+0.5)*3.0/n*3.0/n for i in range(n))
        self.assertAlmostEqual(flux/M, 1.0, places=3)

    def test_nominal_currents_meet_their_two_conditions(self):
        cs, st = vs.coils(S), ve.stations(S)
        I = vs.currents(S, 'NOMINAL')
        self.assertAlmostEqual(vs.axis_field(cs, I, st['burn']), vs.stop_field(S), places=9)
        self.assertAlmostEqual(vs.axis_field(cs, I, st['shield_aft']), 0.0, places=9)
        self.assertEqual([c['name'] for c in cs], ['C1', 'C2', 'L1', 'L2', 'L3', 'L4'])        # no third closure coil

    def test_coil_forces_are_internal(self):
        for case in vs.config(S)['current_cases']:
            f = vs.coil_forces(S, case)
            self.assertLess(abs(sum(c['Fz_N'] for c in f)), 1e-6*max(abs(c['Fz_N']) for c in f), case)

    def test_cut_forces_balance_at_the_collar(self):
        em = vs.engine_members(S, 'NOMINAL')['collar']
        self.assertAlmostEqual(em['net_N']/em['closure_in_N'], 0.0, places=9)

    def test_neighbours_attract_and_the_cluster_force_is_internal(self):
        r = vs.inter_engine(S, 'NOMINAL')
        tot = [sum(e['force_N'][i] for e in r) for i in range(3)]
        big = max(abs(e['radial_N']) for e in r)
        self.assertLess(max(abs(v) for v in tot), 1e-6*big)
        self.assertTrue(all(e['radial_N'] < 0 for e in r))                  # pulled toward the axis: opposite-polarity neighbours attract
        d = vs.dipole_estimate(S)
        self.assertLess(abs(math.log(big/d['adjacent_N'])), math.log(2.0))   # the exact answer is of the dipole's order

    def test_segment_count_converges(self):
        a = vs.inter_engine(S, 'NOMINAL', N=24)[0]['radial_N']; b = vs.inter_engine(S, 'NOMINAL', N=48)[0]['radial_N']
        self.assertLess(abs(a/b-1), 1e-3)


class FrameTests(unittest.TestCase):
    def test_cantilever(self):
        f = fe.Frame(); sec = fe.tube(0.2, 0.25); E, G = 110e9, 42e9
        n = [f.node((i, 0, 0)) for i in range(11)]
        for a, b in zip(n, n[1:]):
            f.beam(a, b, sec, E, G)
        f.fix(n[0]); f.load(n[-1], F=(0, 0, -1e5))
        self.assertAlmostEqual(f.solve()['u'][n[-1]][2]/(-1e5*10**3/(3*E*sec['Iy'])), 1.0, places=9)

    def test_ring_under_equal_radial_loads(self):
        R, P, N, M = 5.0, 1e5, 8, 192
        f = fe.Frame(); sec = fe.tube(0.2, 0.25)
        nodes = [f.node((R*math.cos(2*math.pi*i/M), R*math.sin(2*math.pi*i/M), 0)) for i in range(M)]
        for i in range(M):
            f.beam(nodes[i], nodes[(i+1) % M], sec, 110e9, 42e9, ref=(0, 0, 1))
        for nd in nodes:
            for d in range(6):
                f.spring(nd, d, 1.0)
        for k in range(N):
            th = 2*math.pi*k/N; f.load(nodes[k*M//N], F=(-P*math.cos(th), -P*math.sin(th), 0))
        a = math.pi/N
        self.assertLess(abs(max(e['Mz'] for e in f.solve()['forces'])/(P*R/2*(1/a-1/math.tan(a)))-1), 0.005)

    def test_reaction_ring_model_converges_and_balances(self):
        c = vs.fe_ring_convergence(S)
        self.assertLess(abs(c[1]['ring_peak_M']/c[2]['ring_peak_M']-1), 0.01)
        self.assertLess(abs(c[1]['tie_N']/c[2]['tie_N']-1), 0.01)
        r = vs.fe_reaction_ring(S)['fe']
        self.assertAlmostEqual(r['reaction_sum_N'][0]/r['applied_sum_N'][0], -1.0, places=6)

    def test_euler_buckling(self):
        m = vs.material(S, 'MAT-TI6AL4V'); sec = vs.tube_section(0.3, S)
        c = vs.check_tube(-1e6, 0.3, 6.0, m, S)
        self.assertAlmostEqual(c['Pcr'], math.pi**2*m['E']*sec['Iy']/36.0, delta=1.0)
        self.assertAlmostEqual(c['u_buckling'], 1e6*vs.config(S)['buckling_safety_factor']/c['Pcr'], places=9)


class MaterialTests(unittest.TestCase):
    def test_design_values_come_from_the_catalogue(self):
        m = vs.material(S, 'MAT-TI6AL4V')
        self.assertEqual(m['E'], mp.require(mp.get_property('MAT-TI6AL4V', 'elastic_modulus', 293.0)))
        self.assertAlmostEqual(m['allow_tension'], mp.require(mp.get_property('MAT-TI6AL4V', 'yield_strength', 293.0))/vs.config(S)['yield_safety_factor'])

    def test_missing_properties_are_rejected(self):
        for mid in ('MAT-TZM', 'MAT-NB1ZR', 'MAT-MORE'):
            with self.assertRaises(mp.UnknownProperty):
                vs.material(S, mid)
        with self.assertRaises(mp.UnknownProperty):                         # no extrapolation of a room-temperature value
            vs.material(S, 'MAT-TI6AL4V', T=1800.0)

    def test_lithium_circuit_has_no_rated_material(self):
        li = vs.lithium(S)
        self.assertTrue(all(v['verdict'] != 'RANGE_REACHES_1800K' for v in li['materials'].values()))


class SizingTests(unittest.TestCase):
    def test_every_engine_member_carries_the_design_case(self):
        em = sizing()['engine'][vs.config(S)['design_case']]
        for grp in list(vs.ENGINE_KEYS)+['winding']:
            self.assertLessEqual(em[grp]['u'], 1.0, grp)

    def test_the_cluster_frame_carries_the_design_sets(self):
        cl = sizing()['cluster']['cases']
        for name in vs.DESIGN_SETS:
            for grp, d in cl[name]['groups'].items():
                if grp != 'other':
                    self.assertLessEqual(d['u'], 1.0, (name, grp))

    def test_frame_is_stiffer_than_the_field_pull(self):
        self.assertGreater(sizing()['cluster']['magnetic_margin'], 10.0)

    def test_cage_clearance_rule(self):
        g = ve.config(S)['geometry']
        self.assertAlmostEqual(g['cage_clearance_m'], vs.cage_clearance(g), places=6)

    def test_sized_members_do_not_interfere(self):
        names = [p['name'] for p in ve.parts(S) if p['category'] == 'STRUCTURE' and p['shape'] in ('tube', 'torus')]
        for n, r in vs.clearances(S, stems=names, ends=0.3).items():
            self.assertGreaterEqual(r['gap_m'], 0.0, (n, r))

    def test_statuses_are_honest(self):
        sz = sizing(); recs = vs.part_engineering(S, sz)
        self.assertEqual(len(recs), len(ve.parts(S)))
        self.assertTrue(all(r['status'] in vs.STATUSES for r in recs))
        sized = ('ANALYTICALLY_SIZED', 'CONDITIONALLY_SIZED', 'FEA_SCREENED')
        self.assertTrue(all(r['u_nominal'] <= 1.0 for r in recs if r['status'] in sized and r['u_nominal'] is not None))
        by = {p['name']: p for p in ve.parts(S)}
        self.assertTrue(all(r['status'] == 'BLOCKED' for r in recs if by[r['name']]['category'] == 'HOT_THERMAL'))
        self.assertEqual(S['vertex_research']['gate2_verdict'], 'BLOCKED')     # structure never changes the research verdict

    def test_thermal_contraction(self):
        th = vs.thermal(S)
        for c in vs.coils(S):
            self.assertAlmostEqual(th['coil_contraction_m'][c['name']], c['r']*vs.config(S)['contraction_steel_293_20'])


if __name__ == '__main__':
    unittest.main()
