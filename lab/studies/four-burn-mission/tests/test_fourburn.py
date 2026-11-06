"""Unit tests for the four-burn study: rocket equation, kinematics, mass and energy conservation, plasma data, closure.
    python3 -m unittest discover -s lab/studies/four-burn-mission/tests"""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fourburn import architectures, canon, closure, kinematics, plasma, rocket, tanks   # noqa: E402
from fourburn.const import C, G0, EPS_DHE3                                             # noqa: E402

SC = canon.scenario(); REF = canon.reference(); DV = 0.016*C


class Rocket(unittest.TestCase):
    def test_tsiolkovsky(self):
        self.assertAlmostEqual(rocket.mass_ratio(DV, 1e7), math.exp(DV/1e7), places=12)
        rel = rocket.mass_ratio(DV, 1e7, relativistic=True)
        self.assertGreater(rel, rocket.mass_ratio(DV, 1e7))
        self.assertLess(math.log(rel)/math.log(rocket.mass_ratio(DV, 1e7))-1, 1e-4)   # Newtonian is enough at 0.016 c

    def test_ledger_ends_at_end_mass(self):
        L = rocket.ledger(1.0e6, 1.5e7, DV)
        self.assertAlmostEqual(L['masses_kg'][-1], 1.0e6, delta=1e-6)
        self.assertAlmostEqual(sum(L['burn_propellant_kg']), L['propellant_kg'], delta=1e-3)
        for a, b in zip(L['masses_kg'], L['masses_kg'][1:]):
            self.assertAlmostEqual(a/b, L['mass_ratio_per_burn'], places=10)

    def test_reproduces_canon_operating_point(self):
        op = REF['op']
        L = rocket.ledger(op['mission']['end_mass_kg'], REF['ve_m_s'], DV)
        self.assertAlmostEqual(L['departure_kg'], op['mission']['departure_mass_kg'], delta=50.0)
        sp = rocket.split(L['propellant_kg'], REF['ve_m_s'], REF['eta'], REF['burnup'], REF['recovery'], eps=REF['eps_J_kg'],
                          he3_share=REF['he3_share'])
        # canon books only the reacted fuel as He-3/D and the lost unburned feed as 'hydrogen'; this model draws it from the fuel tanks
        s = REF['he3_share']; lost = sp['lost_unburned_kg']
        self.assertAlmostEqual(sp['helium_3_kg']-lost*s, op['species_kg']['helium_3'], delta=500.0)
        self.assertAlmostEqual(sp['deuterium_kg']-lost*(1-s), op['species_kg']['deuterium'], delta=500.0)
        self.assertAlmostEqual(sp['hydrogen_kg']+lost, op['species_kg']['hydrogen'], delta=500.0)

    def test_split_conserves_mass_and_energy(self):
        for ve, eta, b, r in ((1.92e7, 0.8, 0.8, 0.95), (1.3e7, 0.62, 0.55, 0.0), (8e6, 0.5, 0.3, 0.0)):
            s = rocket.split(1000.0, ve, eta, b, r)
            self.assertEqual(rocket.check_split(s), [])
            self.assertAlmostEqual(s['energy_mass_kg']*C**2, s['fusion_energy_J'], delta=1e-6*s['fusion_energy_J'])

    def test_ve_max_is_the_inert_free_limit(self):
        v = rocket.ve_max(0.6, 0.5, 0.0)
        s = rocket.split(1.0, v*(1-1e-9), 0.6, 0.5, 0.0)
        self.assertLess(s['hydrogen_kg'], 1e-6)
        self.assertIsNone(rocket.split(1.0, v*1.01, 0.6, 0.5, 0.0))


class Kinematics(unittest.TestCase):
    def test_constant_acceleration(self):
        r = kinematics.const_accel(DV, G0); n = kinematics.const_accel(DV, G0, relativistic=False)
        self.assertAlmostEqual(r['t_s'], C/G0*math.sinh(math.atanh(0.016)), delta=1e-3)
        self.assertLess(abs(n['t_s']/r['t_s']-1), 2e-4)
        self.assertAlmostEqual(n['d_m'], DV**2/(2*G0), delta=1.0)

    def test_constant_thrust_matches_integration(self):
        ve, a0 = 1.5e7, 0.01*G0; r = kinematics.const_thrust(DV, ve, a0)
        m, v, x, t, dt = 1.0, 0.0, 0.0, 0.0, r['t_s']/200000
        mdot = a0/ve
        while v < DV:
            a = mdot*ve/m; x += (v+0.5*a*dt)*dt; v += a*dt; m -= mdot*dt; t += dt
        self.assertLess(abs(t/r['t_s']-1), 1e-3)
        self.assertLess(abs(x/r['d_m']-1), 1e-3)

    def test_throttled_burn_momentum(self):
        ve = 1.2e7; m0 = 1e7; F = 1.2*G0*m0
        b = kinematics.throttled_burn(DV, ve, F, m0, 1.5*G0)
        self.assertAlmostEqual(b['m_end'], m0*math.exp(-DV/ve), delta=1e-3)
        self.assertLessEqual(b['a_peak'], 1.5*G0*(1+1e-12))
        # integrate: constant thrust capped at 1.5 g
        m, v, t = m0, 0.0, 0.0; dt = b['t_s']/200000
        while v < DV:
            Fe = min(F, 1.5*G0*m); a = Fe/m; v += a*dt; m -= Fe/ve*dt; t += dt
        self.assertLess(abs(t/b['t_s']-1), 1e-3)
        self.assertLess(abs(m/b['m_end']-1), 1e-4)


class Plasma(unittest.TestCase):
    def test_bosch_hale_dt(self):
        self.assertAlmostEqual(plasma.sigv('DT', 10.0)/1.136e-22, 1.0, delta=0.01)

    def test_partition_bounds(self):
        p = plasma.partition(100.0, 100.0, 1.0, 0.0, 0.0)
        self.assertTrue(0.2 < p['brems'] < 0.26)          # e-i + e-e bremsstrahlung, v4 recheck 0.237
        self.assertTrue(0.005 < p['neutron'] < 0.02)
        self.assertAlmostEqual(p['neutron']+p['brems']+p['charged_to_exhaust'], 1.0, places=12)

    def test_burn_parameter_calibration(self):
        self.assertAlmostEqual(plasma.burn_parameter_kg_m2(20.0, 'DT')/10.0, 7.0, places=9)
        self.assertTrue(35 < plasma.burn_parameter_kg_m2(100.0)/10.0 < 50)

    def test_dhe3_specific_energy(self):
        self.assertAlmostEqual(EPS_DHE3/3.52e14, 1.0, delta=0.002)


class Architectures(unittest.TestCase):
    def test_energy_ledgers_close(self):
        for a in architectures.ARCHS:
            for t in canon.TIERS:
                A = architectures.evaluate(a, SC, t, 5e12, 1.4e7, REF)
                self.assertAlmostEqual(sum(A['ledger'].values()), 1.0, places=9, msg=f'{a} {t}')
                self.assertTrue(0 < A['eta_jet'] < 1)
                # heat sent to radiators never includes the jet or radiation escaping to space
                self.assertLess(A['heat']['hot']+A['heat']['warm'], 1-A['eta_jet'])

    def test_exhaust_speed_never_exceeds_energy_limit(self):
        for a in ('IFD-C', 'IFD-CH', 'IFD-PH'):
            A = architectures.evaluate(a, SC, 'optimistic', 5e12, 1.4e7, REF)
            self.assertLessEqual(A['ve_max'], math.sqrt(2*A['eta_jet']*EPS_DHE3)*(1+1e-12))


class Closure(unittest.TestCase):
    def test_linear_closure_matches_closed_form(self):
        ve = REF['ve_m_s']; a0 = 0.05; pay = 860e3
        r = closure.close('CANON', 'central', SC, REF, ve, a0, pay)
        A = r['architecture']; RN = math.exp(4*DV/ve)
        al = closure.allowances(SC); extra = al['reserve']+al['residual']+al['boiloff']
        sp = rocket.split(1.0, ve, A['eta_jet'], A['burn_fraction'], A['recovery'], eps=A['eps'], he3_share=A['he3_share'])
        d = REF['density_kg_m3']; u = SC['tanks']['ullage']['value']; mpm = SC['tanks']['mass_per_m3']['central']
        k = mpm*(1+u)*(sp['helium_3_kg']/d['helium_3']+sp['deuterium_kg']/d['deuterium']+sp['hydrogen_kg']/d['hydrogen'])
        alpha_f = A['alpha_hw']+A['alpha_rad']
        m0 = RN*pay/(1-RN*alpha_f*a0*G0*ve/(2*A['eta_jet'])-(k*(1+extra)+extra)*(RN-1))
        self.assertAlmostEqual(r['departure_t']*1e3/m0, 1.0, places=8)

    def test_mass_and_energy_bookkeeping(self):
        r = closure.close('IFD-PH', 'optimistic', SC, REF, 1.6e7, 0.003, 860e3)
        self.assertTrue(r['converged'])
        self.assertAlmostEqual(r['departure_t']-r['propellant_t'], r['end_t'], places=6)
        self.assertAlmostEqual(r['end_t'], r['dry_t']+r['reserve_t'], places=6)
        self.assertAlmostEqual(r['dry_t'], r['payload_t']+r['drive_t']+r['radiator_t']+r['tank_t'], places=6)
        self.assertAlmostEqual(sum(r['burn_propellant_t']), r['propellant_t'], places=5)
        self.assertAlmostEqual(r['jet_energy_J'], r['propellant_t']*1e3*(1.6e7)**2/2, delta=1e-9*r['jet_energy_J'])
        self.assertAlmostEqual(r['jet_energy_J'], r['architecture']['eta_jet']*r['fusion_energy_J'], delta=1e-9*r['jet_energy_J'])
        self.assertAlmostEqual(sum(r['species_t'].values()), r['propellant_t'], places=5)
        self.assertLessEqual(r['a_end_g'], 1.5+1e-9)

    def test_divergence_is_reported(self):
        r = closure.close('IFD-C', 'central', SC, REF, 1.0e7, 1e-4, 860e3)
        self.assertFalse(r['converged'])
        r = closure.close('IFD-PH', 'central', SC, REF, 1.5e7, 1.0, 860e3)
        self.assertFalse(r['converged'])
        self.assertTrue('loop gain' in r['reason'] or 'exceeds' in r['reason'])

    def test_canon_split_fits_existing_tanks(self):
        c = tanks.compare(REF['op']['species_kg'], SC, REF['density_kg_m3'])
        self.assertTrue(all(v < 1.0 for v in c['ratio'].values()))


if __name__ == '__main__':
    unittest.main()
