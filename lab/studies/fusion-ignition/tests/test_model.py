"""Physical invariants of the Fusion Ignition data (lab test, outside CI; D-T00-1)."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import model  # noqa: E402

D = json.loads((Path(model.HERE) / 'results/fusion_ignition.json').read_text())


class Invariants(unittest.TestCase):
    def test_products_share_the_q_value(self):
        n = D['nuclear']
        self.assertAlmostEqual(n['products']['p']['MeV'] + n['products']['alpha']['MeV'], n['Q_MeV'], delta=0.01)

    def test_barrier_and_gamow(self):
        n = D['nuclear']
        self.assertTrue(0.8 < n['barrier_MeV'] < 1.0)                 # about 0.9 MeV at touching radii
        self.assertTrue(4600 < n['gamow_keV'] < 4850)                  # E_G = 2 mu c^2 (pi alpha Z1 Z2)^2
        self.assertTrue(200 < n['gamow_peak_keV'] < 260)               # at 100 keV

    def test_cross_section_peak(self):
        E, s = D['nuclear']['peak']
        self.assertTrue(200 <= E <= 450 and 0.6 < s < 1.0)             # D-3He peaks near 0.7-0.9 b

    def test_fusion_is_rare_against_scattering(self):
        for p in D['nuclear']['points']:
            self.assertLess(p['fuse_per_scatter'], 0.01)

    def test_brems_forbids_cold_ignition(self):
        th = {T: nt for T, nt, _ in D['plasma']['lawson']['thermal']}
        self.assertIsNone(th[20])
        self.assertGreater(min(v for v in th.values() if v), D['plasma']['dt_ref']['n_tau_min'])

    def test_burn_grows_with_areal_density(self):
        b = D['plasma']['burn']
        f = [b['grid'][f'{r:g}|{b["Ti_design"]:g}']['burn_fraction'] for r in b['rhoR']]
        self.assertEqual(f, sorted(f))

    def test_design_burn_gives_the_engine_yield(self):
        b = D['plasma']['burn']; g = b['grid'][f'{b["rhoR_design"]:g}|{b["Ti_design"]:g}']
        self.assertAlmostEqual(g['fusion_J'] / b['yield_J'], 1.0, delta=0.02)

    def test_no_variant_closes_the_heat(self):
        for v in D['channels']['variants'].values():
            self.assertGreater(v['over'], 1000)

    def test_mirrors_never_reflect_all(self):
        for r in D['lab']['mirrors']['rows']:
            self.assertLess(r['reflected'], 0.5 + 1e-9)


    def test_pulse_accounting_closes_per_state(self):
        a = D['accounting']; st = {x['id']: x for x in a['states']}; p = st['pulse']
        self.assertAlmostEqual(p['yield_J'] * p['Hz'] / p['per_engine_W'], 1.0, delta=1e-9)
        for x in a['states']:
            self.assertAlmostEqual(x['cluster_W'] / x['per_engine_W'] if 'cluster_W' in x else 4.0, 4.0, delta=1e-9)
        self.assertAlmostEqual(a['gap']['power_ratio'], st['need']['per_engine_W'] / p['per_engine_W'], delta=1e-9)

    def test_burn_energy_balance(self):
        b = D['accounting']['burn']
        self.assertAlmostEqual(b['xray'] + b['neutron'] + b['left_in_plasma'], 1.0 + b['heat_J'] / b['fusion_J'], delta=1e-9)

class Ledger(unittest.TestCase):
    """The unified pulse ledger: same burn as vertex_radiation, energy and particles conserved, states kept apart."""
    L = D['ledger']

    def test_ledger_burn_is_vertex_radiation_burn(self):
        import ledger
        import vertex_radiation as vr
        s = model.S.load()[0]; c = dict(ledger.base_case(s), rhoR_g_cm2=30.0, Ti_keV=50.0)
        a = ledger.burn(s, c); b = vr.burn(s, c, spectrum=False)
        for x, y in ((a['energy']['fusion_J'], b['fusion_J']), (a['energy']['xray_J'], b['brems_J']), (a['energy']['neutron_J'], b['neutron_J']),
                     (a['particles']['burn_fraction_D'], b['burn_fraction']), (a['energy']['expansion_J'], b['adiabatic_J'])):
            self.assertAlmostEqual(x / y, 1.0, places=9)

    def test_energy_and_particles_conserved(self):
        c = self.L['checks']
        self.assertLess(abs(c['energy_residual_share']), 0.01)       # the only leak: ions created or lost at fixed temperature
        self.assertAlmostEqual(c['nucleons'][1] / c['nucleons'][0], 1.0, places=9)
        self.assertAlmostEqual(c['charge'][1] / c['charge'][0], 1.0, places=9)
        self.assertLess(abs(c['mass_check']), 1e-3)
        self.assertAlmostEqual(c['pulse_balance'], 0.0, places=9)
        self.assertAlmostEqual(c['nozzle_balance'], 0.0, places=9)

    def test_every_grid_cell_closes(self):
        for k, g in self.L['grid']['cells'].items():
            self.assertLess(abs(g['residual_J']) / (g['fusion_J'] + g['heat_J']), 0.02, k)
            self.assertTrue(0.0 < g['burn_fraction'] < 1.0, k)

    def test_states_keep_their_sources(self):
        st = {x['id']: x for x in self.L['states']}
        self.assertAlmostEqual(st['MISSION']['fusion_W'] * 4 / D['need']['fusion_W'], 1.0, places=9)
        self.assertAlmostEqual(st['DESIGN']['fusion_W'] / D['engine']['pulse']['power_W'], 1.0, places=6)
        self.assertAlmostEqual(st['DESIGN']['jet_share'], D['engine']['pulse']['charged_share'], places=9)
        self.assertLess(st['COUPLED']['jet_share'], st['DESIGN']['jet_share'])   # the burn leaves less than the design assumes
        self.assertAlmostEqual(st['COUPLED']['yield_J'] / st['DESIGN']['yield_J'], 1.0, places=4)   # same target, same yield

    def test_thrust_from_energy_and_mass(self):
        p = self.L['pulse']
        self.assertAlmostEqual(p['impulse_Ns'] ** 2 / (2 * p['exhaust_mass_kg'] * p['jet_J']), 1.0, places=9)
        self.assertAlmostEqual(p['thrust_N'] / (p['impulse_Ns'] * p['Hz']), 1.0, places=9)

    def test_thermal_heat_is_booked_once(self):
        t = D['thermal']; pw = t['powers']
        cmp = {c['id']: c for c in t['comparison']}
        base = cmp['BASE']
        # what lands on the drawn engine cannot exceed the X-rays, neutrons and charged hits the pulse delivers
        self.assertLessEqual(base['hot_W'] + base['warm_W'] + base['cryo_W'], 1.0001 * (pw['xray_W'] + pw['neutron_W'] + pw['charged_hit_W']))
        for k in ('A', 'B', 'C', 'D', 'B+C'):
            c = cmp[k]
            self.assertGreaterEqual(c['mass_t'], 0.0, k)                      # every strategy carries its mass
            self.assertLessEqual(c['removed_W'] + c['moved_W'], base['hot_W'] + base['warm_W'] + 1.0, k)
        self.assertLess(cmp['A']['removed_W'] / pw['xray_W'], 1e-3)          # mirrors do not return MeV-era or steep-angle X-rays
        self.assertEqual(cmp['D']['removed_W'], 0.0)

    def test_thermal_problems_registered(self):
        ids = {p['id'] for p in D['problems']['items']}
        for n in range(40, 64):
            self.assertIn(f'ENG-0{n}', ids)

    def test_source_shares_close(self):
        # X-rays + neutrons + plasma = fusion + driver heat - energy lost with reacted ions, for every burn lever
        for lv in D['source']['levers']:
            if lv['lever'] in ('extraction',):
                continue
            tot = lv['xray_share'] + lv['neutron_share'] + lv['plasma_share'] + lv['escaped_share']
            self.assertGreater(tot, 1.0 - lv['number_change_share'] - 1e-3, lv['label'])
            self.assertLess(tot, 1.10, lv['label'])
            self.assertLess(abs(lv['residual_share']), 1e-3, lv['label'])

    def test_heat_direction_is_not_closed(self):
        row = next(r for r in D['thermal']['comparison'] if r['id'] == 'B+Ct')
        self.assertGreater(row['over_budget_after'], 1.0)
        self.assertLess(row['over_budget_after'], row['over_budget_before'])
        self.assertGreaterEqual(D['source']['best']['engine']['heat_over'], 1.0)

    def test_pulse_momentum_and_mass_close(self):
        r = D['ledger']['pulse']                                                     # struck plasma stays in the engine (ENG-064)
        self.assertAlmostEqual(r['exhaust_mass_kg'] + r['deposited_kg'], r['debris_kg'], delta=1e-6 * r['debris_kg'])
        self.assertAlmostEqual(r['impulse_Ns'] / r['exhaust_mass_kg'], r['exhaust_m_s'], delta=1.0)
        self.assertAlmostEqual(r['impulse_Ns'] ** 2 / (2 * r['exhaust_mass_kg']), r['jet_J'], delta=1e-6 * r['jet_J'])
        self.assertLessEqual(r['jet_J'] + r['hit_J'] + r['side_J'], r['plasma_J'] * (1 + 1e-9))
        self.assertAlmostEqual(r['thrust_N'], r['impulse_Ns'] * r['Hz'], delta=1e-6 * r['thrust_N'])

    def test_chapters_cover_the_register(self):
        ids = {i['id'] for i in D['problems']['items']}
        self.assertTrue({'ENG-064', 'ENG-065'} <= ids)
        for i in D['problems']['items']:
            for k in ('cause', 'component', 'intended', 'deficit', 'future', 'maturity'):
                self.assertIn(k, i)
        self.assertTrue(all(c['status'] for c in D['problems']['concepts']))
        self.assertFalse(any(r['heat_over'] <= 1.0 for r in D['chapters']['compare']['rows']))      # nothing closes; the page must not say so

    def test_research_geometry_is_momentum_consistent(self):
        O = D['chapters']['optimize']
        self.assertTrue({'ENG-066', 'ENG-072'} <= {i['id'] for i in D['problems']['items']})
        for g in O['geos']:                                     # ship impulse = initial - escaping - trapped = field + hardware
            b = g['bal']
            self.assertLess(b['closure'], 1e-3)
            self.assertAlmostEqual(b['ship'], b['via_field'] + b['via_hardware'], places=3)        # page JSON keeps 4 significant digits
            self.assertLess(abs(b['p_init']), 1e-3)
        K = O['combination']                                    # the combination is computed, never the product of the separate gains
        self.assertLess(K['computed']['thrust_N'], K['best']['base']['thrust_N'])
        self.assertGreater(K['computed']['heat_over'], 1.0)
        R = D['ledger']['nozzle']['R|1']; C1 = D['ledger']['nozzle']['C1|1']
        self.assertLess(R['hit'], C1['hit'])
        self.assertTrue(all(c['gap_m'] > 0 for c in O['research']['clearances']))


if __name__ == '__main__':
    unittest.main()