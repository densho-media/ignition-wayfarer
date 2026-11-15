"""Vertex Engine 1.3 magnetic design closure (owner brief 2026-11-15): field-solver validation, force cross-checks, the test-particle
pusher, and the stored candidates' hard requirements. Pure modules only. The physics checks are closed forms or conservation laws; the
candidate checks protect the invariant that a stored candidate meets the requirements it is reported to meet, and that the 1.2 cases
stay reproducible."""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src/wayfarer'))
from spec import load
import vertex_engine as ve
import vertex_magnet as vm
import vertex_structure as vs

S = load(ROOT)[0]
CS = vm.coil_set(S)
NOM = vs.currents(S, 'NOMINAL')


class FieldSolverTests(unittest.TestCase):
    def test_on_axis_field_matches_the_analytic_sum(self):
        for x in (-12.0, -18.8, -25.0, -40.0):
            exact = sum(vs.MU0*i*c['r']**2/(2*(c['r']**2+(x-c['x'])**2)**1.5) for c, i in zip(CS, NOM))
            self.assertAlmostEqual(vm.field(CS, NOM, x, 0.0)[1], exact, delta=1e-9)

    def test_superposition_and_linearity(self):
        a = [1e6, 0, 0, 0, 0, 0]; b = [0, 0, 0, 2e6, 0, 0]; ab = [x+y for x, y in zip(a, b)]
        fa, fb, fab = vm.field(CS, a, -20.0, 3.0), vm.field(CS, b, -20.0, 3.0), vm.field(CS, ab, -20.0, 3.0)
        for k in range(2):
            self.assertAlmostEqual(fab[k], fa[k]+fb[k], delta=1e-12)
        self.assertAlmostEqual(vm.field(CS, [2*v for v in NOM], -20.0, 3.0)[1], 2*vm.field(CS, NOM, -20.0, 3.0)[1], delta=1e-9)

    def test_axisymmetry_of_the_cartesian_field(self):
        for ph in (0.3, 1.9, 4.0):
            B = vm.field3(CS, NOM, (-20.0, 3.0*math.cos(ph), 3.0*math.sin(ph)))
            br, bx = vm.field(CS, NOM, -20.0, 3.0)
            self.assertAlmostEqual(B[0], bx, delta=1e-12)
            self.assertAlmostEqual(math.hypot(B[1], B[2]), abs(br), delta=1e-12)

    def test_divergence_free(self):
        h = 1e-4
        for p in ((-17.0, 2.0, 1.0), (-22.0, -4.0, 3.0), (-30.0, 6.0, -2.0)):
            div = 0.0
            for k in range(3):
                pp = list(p); pm = list(p); pp[k] += h; pm[k] -= h
                div += (vm.field3(CS, NOM, pp)[k]-vm.field3(CS, NOM, pm)[k])/(2*h)
            scale = math.sqrt(sum(b*b for b in vm.field3(CS, NOM, p)))/h
            self.assertLess(abs(div), 1e-6*scale)

    def test_finite_winding_converges_to_the_filament_away_from_the_conductor(self):
        c = CS[3]
        thin = vs.loop_field(c['r'], 1e6, 2.0, 1.5)
        for n in (2, 4, 6):
            br, bx = vm.field_finite(c, 1e6, c['x']+1.5, 2.0, n)
            self.assertAlmostEqual(bx/thin[1], 1.0, places=3)
        # at the winding surface the bundle stays finite and close to the long-wire field mu0 I / (2 pi a)
        Bs = math.hypot(*vm.field_finite(c, 1e6, c['x'], c['r']+c['a'], 6))
        self.assertLess(abs(Bs/(vs.MU0*1e6/(2*math.pi*c['a']))-1.0), 0.25)

    def test_lorentz_forces_match_the_energy_gradient_and_sum_to_zero(self):
        for name in ('NOMINAL', 'CONSERVATIVE'):
            I = vs.currents(S, name)
            F, Fe = vm.axial_forces(CS, I), vm.energy_forces(CS, I)
            for a, b in zip(F, Fe):
                self.assertAlmostEqual(a/max(abs(x) for x in F), b/max(abs(x) for x in F), places=5)
            self.assertLess(abs(sum(F)), 1e-9*max(abs(x) for x in F))

    def test_1_2_cases_are_reproduced(self):
        for name in vm.HISTORICAL:
            k = vs.compression_factor(S, name)
            for row, f in zip(vs.coil_forces(S, name), vm.axial_forces(CS, vs.currents(S, name))):
                self.assertAlmostEqual(row['Fz_N'], f*k, delta=1e-6*abs(row['Fz_N'])+1.0)
        self.assertAlmostEqual(vm.stored_energy(CS, NOM), vs.stored_energy(S, 'NOMINAL')[0], delta=1e-6*vm.stored_energy(CS, NOM))

    def test_nominal_is_a_cusp_with_a_null_at_the_shield(self):
        st = ve.stations(S)
        self.assertLess(abs(vm.field(CS, NOM, st['shield_aft'], 0.0)[1]), 1e-6)
        self.assertGreater(len(vm.nulls(CS, NOM, st['shield_aft']-0.01, st['exit'])), 0)


class ParticleTests(unittest.TestCase):
    D = dict(mass_amu=2.0141, charge=1)

    def test_zero_field_is_a_straight_line(self):
        hw = vm.hardware(S, CS)
        r = vm.push(S, CS, [0.0]*6, self.D, 1e7, (-1.0, 0.0, 0.0), hw)
        self.assertEqual(r['outcome'], 'AFT')
        self.assertAlmostEqual(r['x'][1], 0.0, delta=1e-9)
        self.assertLess(r['err'], 1e-12)

    def test_boris_gyration_in_a_uniform_field(self):
        """Hand-rolled uniform B: the Boris rotation keeps |v| exactly and returns to the start after one gyro period."""
        m = self.D['mass_amu']*vm.AMU; q = vm.E_CHARGE; B = (2.0, 0.0, 0.0); v = 1e6
        rl = vm.larmor(self.D, 2.0, v); self.assertAlmostEqual(rl, m*v/(q*2.0), delta=1e-12)
        T = 2*math.pi*m/(q*2.0); n = 2000; dt = T/n
        x = [0.0, 0.0, 0.0]; u = [0.0, v, 0.0]
        for _ in range(n):
            h = q*dt/(2*m); tv = [h*b for b in B]; t2 = sum(a*a for a in tv); sv = [2*a/(1+t2) for a in tv]
            up = [u[0]+(u[1]*tv[2]-u[2]*tv[1]), u[1]+(u[2]*tv[0]-u[0]*tv[2]), u[2]+(u[0]*tv[1]-u[1]*tv[0])]
            u = [u[0]+(up[1]*sv[2]-up[2]*sv[1]), u[1]+(up[2]*sv[0]-up[0]*sv[2]), u[2]+(up[0]*sv[1]-up[1]*sv[0])]
            x = [x[k]+u[k]*dt for k in range(3)]
        self.assertAlmostEqual(math.sqrt(sum(a*a for a in u)), v, delta=1e-6*v)
        self.assertLess(math.dist(x, (0.0, 0.0, 0.0)), 1e-3*rl)

    def test_energy_is_conserved_in_the_engine_field(self):
        hw = vm.hardware(S, CS)
        for d in vm._dirs(12):
            r = vm.push(S, CS, NOM, self.D, 1.9e7, d, hw)
            self.assertLess(r['err'], 1e-9)

    def test_outcomes_converge_with_the_time_step(self):
        a = vm.particles(S, CS, NOM, n=60, species=[dict(id='D', mass_amu=2.0141, charge=1, bulk_speed_factor=1.0)])['D']
        hw = vm.hardware(S, CS); fine = []
        for d in vm._dirs(60):
            fine.append(vm.push(S, CS, NOM, self.D, a['speed_m_s'], d, hw, dt_gyro=80)['outcome'] == 'AFT')
        self.assertLess(abs(sum(fine)/60-a['aft']), 0.05)

    def test_obstacle_intersection(self):
        hw = vm.hardware(S, CS); c = CS[3]
        self.assertEqual(vm.obstacle(hw, c['x'], c['r']), c['name'])
        self.assertEqual(vm.obstacle(hw, ve.stations(S)['shield_aft']+0.01, 0.5), 'SHIELD')
        self.assertIsNone(vm.obstacle(hw, ve.stations(S)['burn'], 0.0))


class CandidateTests(unittest.TestCase):
    def test_nominal_fails_capture_toward_the_shield(self):
        """The 1.2 NOMINAL rule nulls the field on the shield face: the cusp cannot stop forward plasma (MF-01/02)."""
        ev = vm.evaluate(S, CS, NOM)
        self.assertFalse(vm.checks(S, ev)['MF-01/02 capture, shield protected'][0])

    def test_stored_candidates_meet_what_they_claim(self):
        c = vm.config(S)
        for k in c['candidates']:
            cand = vm.candidate(S, k['id'])
            ev = vm.evaluate(S, cand['cs'], cand['I'], ys=cand['yield_share'])
            ch = vm.checks(S, ev)
            for name in ('Winding case stress', 'Field at the conductor', 'Winding current density'):
                self.assertTrue(ch[name][0], (k['id'], name, ch[name]))
            if k.get('capture_closed'):
                key = 'MF-01/02 capture, shield protected' if k['protect'] == 'strict' else 'MF-01/02 capture, burn face as armour'
                self.assertTrue(ch[key][0], (k['id'], key, ch[key]))

    def test_geometry_candidate_stays_inside_the_envelope(self):
        for k in vm.config(S)['candidates']:
            if k.get('geometry'):
                self.assertTrue(vm.geometry_ok(S, vm.candidate(S, k['id'])['cs'], k), k['id'])

    def test_yield_scaling_keeps_capture_and_quarters_forces(self):
        m1, m4 = vm.candidate(S, 'M1'), vm.candidate(S, 'M4')
        y = m4['yield_share']
        self.assertAlmostEqual(vm.evaluate(S, m4['cs'], m4['I'], ys=y)['capture']['worst'], vm.evaluate(S, m1['cs'], m1['I'])['capture']['worst'], places=2)
        self.assertAlmostEqual(max(map(abs, vm.axial_forces(m4['cs'], m4['I'])))/max(map(abs, vm.axial_forces(m1['cs'], m1['I']))), y, places=6)

    def test_the_active_engine_is_not_an_unvalidated_candidate(self):
        c = vm.config(S)
        if c['selected'] != 'M0-NOMINAL':
            row = next(r for r in vm.comparison(S, with_particles=False, with_structure=True) if r['id'] == c['selected'])
            self.assertTrue(all(ok for ok, _, _ in row['checks'].values()))
            self.assertLessEqual(row['structure']['peak_u_design'], 1.0)

    def test_structure_hook_reproduces_1_2_for_the_nominal_currents(self):
        t = vm.scaled_spec(S, dict(vm.candidate(S, 'NOMINAL'), upper=vs.currents(S, 'CONSERVATIVE')))
        a, b = vs.engine_members(S, 'NOMINAL'), vs.engine_members(t, 'NOMINAL')
        for k in vs.ENGINE_KEYS:
            self.assertAlmostEqual(a[k]['u'], b[k]['u'], places=6)


class EvidenceTests(unittest.TestCase):
    """The engineering page reads references/evidence/vertex_magnet.json; it must describe the current inputs."""
    @classmethod
    def setUpClass(cls):
        import json
        cls.R = json.loads((ROOT/'references/evidence/vertex_magnet.json').read_text())

    def test_evidence_is_current(self):
        self.assertEqual(self.R['input_hash'], vm.input_hash(S), 'run python3 src/wayfarer/vertex_magnet.py --evidence --no-pareto')
        self.assertEqual([r['id'] for r in self.R['candidates']], [vm.candidate(S, n)['id'] for n in vm.candidate_ids(S)])

    def test_pareto_points_reproduce(self):
        for p in self.R['pareto']:
            ev = vm.evaluate(S, CS, [v*1e6 for v in p['currents_MAt']])
            self.assertAlmostEqual(ev['capture']['worst'], p['margin'], delta=0.025)   # stored currents rounded to 0.1 kA-turn; 5 cm stopping steps
            self.assertLessEqual(ev['peak_case_u'], 1.0)

    def test_no_stored_candidate_is_claimed_to_pass_everything(self):
        if vm.config(S)['selected'] == 'M0-NOMINAL':
            self.assertTrue(all(not all(c['passed'] for c in r['checks'].values()) for r in self.R['candidates']))


if __name__ == '__main__':
    unittest.main()
