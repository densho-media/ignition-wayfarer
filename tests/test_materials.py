"""PMDS (docs/MATERIALS.md): the catalogue's rules and the physical invariants of its lookups, independent of Blender."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import materials as mats
import material_physics as mp


class MaterialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s, cls.src, *_ = load()
        cls.db = mats.load(sources=cls.src['sources'], families=cls.s['production']['exterior']['families'])

    def test_fourteen_purposes(self):
        self.assertEqual(sorted(self.db['purposes']), [f'P{i:02}' for i in range(1, 15)])

    def test_unknown_data_stays_explicit(self):
        # Every core property is given or listed open; an OPEN property is unknown and cannot be required.
        for mid, m in self.db['materials'].items():
            for name in mats.CORE:
                self.assertTrue(name in m.get('properties', {}) or name in m.get('open', []), (mid, name))
        q = mp.get_property('MAT-W', 'emissivity', 1000.0, self.db)
        self.assertFalse(q['known']); self.assertEqual(q['status'], 'OPEN')
        with self.assertRaises(mp.UnknownProperty):
            mp.require(q)

    def test_no_extrapolation(self):
        q = mp.get_property('MAT-W', 'thermal_conductivity', 1000.0, self.db)
        self.assertEqual((q['value'], q['unit']), (118.0, 'W/(m K)'))
        self.assertAlmostEqual(mp.get_property('MAT-W', 'thermal_conductivity', 700.0, self.db)['value'], 131.0)
        for T in (250.0, 2500.0):
            self.assertEqual(mp.get_property('MAT-W', 'thermal_conductivity', T, self.db)['status'], 'OUT_OF_RANGE')
        self.assertEqual(mp.get_property('MAT-SS-316L', 'thermal_conductivity', 900.0, self.db)['status'], 'OUT_OF_RANGE')
        with self.assertRaises(mp.UnknownProperty):
            mp.conduction_drop('MAT-W', 1e9, 0.01, 600.0, self.db)

    def test_service_limit_below_phase_change(self):
        for mid, m in self.db['materials'].items():
            tm, ts = m.get('properties', {}).get('melting_point'), m.get('properties', {}).get('max_service_temperature')
            if tm and ts:
                self.assertLess(mats.bound(ts, True), mats.bound(tm), mid)

    def test_variants_do_not_inherit_silently_and_speculation_is_blocked(self):
        self.assertEqual(mp.get_property('MAT-W-ADV01', 'density', 293.0, self.db)['status'], 'NOT_INHERITED')
        self.assertTrue(mp.get_property('MAT-REBCO-APC01', 'critical_temperature', db=self.db)['known'])
        self.assertEqual(mp.get_property('MAT-W-FIJI01', 'melting_point', db=self.db)['status'], 'SPECULATIVE_BLOCKED')

    def test_conduction_matches_the_integral(self):
        # Steady 1-D conduction: the hot side carries q L = integral of k dT exactly.
        Th = mp.conduction_drop('MAT-W', 10e6, 0.006, 600.0, self.db)
        self.assertAlmostEqual(mp.conductivity_integral('MAT-W', 600.0, Th, self.db), 10e6*0.006, delta=1.0)

    def test_screens_never_approve(self):
        r = mp.screen_application('APP-DRV-PFC', {'hot_face': {'temperature_K': 1100.0}}, self.db)
        self.assertFalse(r['approved']); self.assertEqual(r['qualification'], 'NOT_QUALIFIED')
        self.assertTrue(all(l['verdict'] == 'NOT_EVALUABLE' for l in r['layers']))      # OD-025 requirements are OPEN
        hot = mp.screen_application('APP-DRV-PFC', {'cooling_conduit': {'temperature_K': 900.0}}, self.db)
        self.assertEqual(mats.layer({'layers': hot['layers']}, 'cooling_conduit')['verdict'], 'EXCEEDS_LIMIT')
        self.assertEqual(hot['verdict'], 'EXCEEDS_LIMIT')

    # Screening regressions on a small fixture application, so the cases do not depend on which catalogue rows are OPEN today.
    def fixture(self, material='MAT-FIX', props=None, level='A', requirements=None, purposes=('P99',), required=('yield_strength',)):
        db = copy.deepcopy(self.db)
        base = {'density': {'value': 1000.0, 'unit': 'kg/m3', 'at_K': 293.0, 'valid_K': [200.0, 800.0], 'basis': 'HANDBOOK',
                            'confidence': 'HIGH', 'source': 'crc'},
                'max_service_temperature': {'value': 700.0, 'unit': 'K', 'basis': 'ESTIMATE', 'confidence': 'MEDIUM', 'source': 'crc',
                                            'rating': 'SCREENING_ESTIMATE'}}
        base.update(props or {})
        db['materials'][material] = dict(name='fixture', level=level, family='f', composition='c', properties=base, open=[],
                                         **({'parent': 'MAT-W'} if level == 'C' else {}))
        db['purposes']['P99'] = dict(required_properties=list(required))
        db['applications']['APP-FIX'] = dict(title='fixture', engineering_status='PROTOTYPE', requirements=requirements or {},
                                             layers=[dict(role='part', purposes=list(purposes), material=material, selection='CANDIDATE',
                                                          geometry='NOT_DRAWN')])
        return db

    def screen(self, db, cond, **kw):
        return mp.screen_application('APP-FIX', {'part': cond}, db, **kw)['layers'][0]

    def test_screen_missing_mechanical_property_is_not_favourable(self):
        l = self.screen(self.fixture(), {'temperature_K': 500.0})               # below the 700 K limit, yield strength absent
        self.assertEqual(l['verdict'], 'NOT_EVALUABLE'); self.assertIn('yield_strength', l['missing_properties'])
        self.assertEqual([c['limit'] for c in l['checked_limits']], ['max_service_temperature'])

    def test_screen_outside_measured_range(self):
        db = self.fixture(props={'yield_strength': {'value': 2e8, 'unit': 'Pa', 'at_K': 293.0, 'basis': 'TYPICAL', 'confidence': 'MEDIUM',
                                                    'source': 'crc'}})
        l = self.screen(db, {'temperature_K': 600.0})                           # room-temperature strength only
        self.assertEqual(l['verdict'], 'NOT_EVALUABLE'); self.assertEqual(l['out_of_range'][0]['property'], 'yield_strength')

    def test_screen_unknown_radiation_exposure(self):
        db = self.fixture(required=('density', 'radiation_response'))
        self.assertEqual(self.screen(db, {'temperature_K': 500.0})['missing_conditions'], ['neutron_fluence_dpa'])
        self.assertEqual(self.screen(db, {'temperature_K': 500.0})['verdict'], 'NOT_EVALUABLE')
        l = self.screen(db, {'temperature_K': 500.0, 'neutron_fluence_dpa': 1.0})   # unirradiated density at a stated dose
        self.assertEqual((l['verdict'], l['unirradiated']), ('NOT_EVALUABLE', ['density']))

    def test_screen_known_violation_stays_visible(self):
        l = self.screen(self.fixture(), {'temperature_K': 800.0})               # also missing yield strength
        self.assertEqual(l['verdict'], 'EXCEEDS_LIMIT'); self.assertIn('yield_strength', l['missing_properties'])

    def test_screen_narrow_pass_lists_what_was_checked(self):
        l = self.screen(self.fixture(required=('density',)), {'temperature_K': 500.0})
        self.assertEqual(l['verdict'], 'WITHIN_CHECKED_LIMITS')
        self.assertEqual(sorted(l['evaluated_properties']), ['density'])
        self.assertTrue(any('SCREENING_ESTIMATE' in r for r in l['reasons']))
        self.assertFalse(l['lifetime_evaluated'])
        self.assertEqual(self.screen(self.fixture(required=('density',)), {'temperature_K': 750.0})['verdict'], 'EXCEEDS_LIMIT')

    def test_screen_level_c_needs_explicit_permission(self):
        db = self.fixture(level='C', required=('density',))
        self.assertEqual(self.screen(db, {'temperature_K': 500.0})['verdict'], 'NOT_EVALUABLE')
        l = self.screen(db, {'temperature_K': 500.0}, allow_speculative=True)
        self.assertTrue(l['speculative'] and l['speculative_allowed'])

    def test_screen_reports_evidence_strength(self):
        sec = {'verification': 'SECONDARY_VERIFIED', 'verified': 'fixture', 'condition': 'fixture'}
        db = self.fixture(required=('density',)); db['materials']['MAT-FIX']['properties']['density'].update(sec)
        db['materials']['MAT-FIX']['properties']['max_service_temperature'].update(sec)
        l = self.screen(db, {'temperature_K': 500.0})
        self.assertEqual((l['verdict'], l['weakest_evidence']), ('WITHIN_CHECKED_LIMITS', 'SECONDARY_VERIFIED'))
        db['materials']['MAT-FIX']['properties']['density']['verification'] = 'UNVERIFIED'
        self.assertEqual(self.screen(db, {'temperature_K': 500.0})['verdict'], 'NOT_EVALUABLE')

    def test_screen_incomplete_lifetime_data(self):
        db = self.fixture(required=('density',), requirements={'replacement_interval': 'PROTOTYPE fixture'})
        self.assertEqual(self.screen(db, {'temperature_K': 500.0})['missing_conditions'], ['life_h'])
        l = self.screen(db, {'temperature_K': 500.0, 'life_h': 2e4})            # a screening estimate is not a lifetime rating
        self.assertEqual(l['verdict'], 'NOT_EVALUABLE'); self.assertFalse(l['lifetime_evaluated'])

    def test_verification_labels_are_earned(self):
        # How many numbers are verified is a state of the catalogue, not a rule: only the evidence each label needs is checked.
        self.assertEqual(mats.validate(self.db), [])
        counts = mats.evidence_counts(self.db)
        self.assertEqual(sum(counts.values()), sum(len(m.get('properties', {})) for m in self.db['materials'].values()))
        for m in self.db['materials'].values():
            for p in m.get('properties', {}).values():
                if mats.verification(p, self.db) in mats.VERIFIED:
                    self.assertTrue(p.get('verified') and p.get('condition') and p.get('verified_against'))
        self.assertTrue(all(r['verification'] in mats.REFERENCE_VERIFICATION for r in self.db['references'].values()))

    def primary(self, **change):
        """The fixture with a primary-source check on its density; returns the validation failures of that number."""
        db = self.fixture(required=('density',))
        db['references']['fix_primary'] = dict(title='fixture primary table', kind='handbook', verification='TRANSCRIBED')
        db['references']['fix_listing'] = dict(title='fixture listing', kind='secondary', verification='UNVERIFIED')
        d = db['materials']['MAT-FIX']['properties']['density']
        d.update(verification='PRIMARY_VERIFIED', verified='1000 kg/m3 read in the table (fixture)', verified_against='fix_primary',
                 locator='Table 1, row fixture', condition='fixture grade, annealed bar, unirradiated')
        for k, v in change.items():
            d.pop(k, None) if v is None else d.__setitem__(k, v)
        return [f for f in mats.validate(db) if 'MAT-FIX.density' in f]

    def test_primary_verification_is_possible_when_documented(self):
        self.assertEqual(self.primary(), [])
        self.assertEqual(self.primary(verified_against='crc'), [])      # reading the cited handbook itself is a primary check

    def test_unsupported_primary_claims_are_rejected(self):
        for change in (dict(verified_against='fix_listing'), dict(verified_against=None), dict(verified_against='no_such_ref'),
                       dict(locator=None), dict(verified=None), dict(condition=None), dict(valid_K=None), dict(unit='g/cm3')):
            self.assertTrue(self.primary(**change), change)
        self.assertTrue(self.primary(verification='SECONDARY_VERIFIED', verified_against='crc'))   # a source cannot check itself

    def test_material_edit_stales_only_its_assets(self):
        old = mats.texts()
        new = dict(old, catalogue=old['catalogue'].replace('value = 0.91, unit = "1", at_K = 300.0', 'value = 0.90, unit = "1", at_K = 300.0'))
        self.assertNotEqual(old, new)
        self.assertEqual(mats.affected_assets(old, new), ['THERMAL'])

    def test_spec_material_values_agree_with_the_catalogue(self):
        # The spec keeps authority; a difference is a review item, so the known ones are named and a new one fails here.
        rows = mp.spec_crosscheck(self.s, self.db)
        self.assertEqual({r['spec_key'] for r in rows if r['status'] == 'DIFFERS'}, {'radiators.zones.bulkhead.layers.2.emissivity'})
        self.assertTrue(all(r['status'] in ('CONSISTENT', 'DIFFERS', 'NOT_CHECKABLE') for r in rows if r['usage'] == 'CROSS_CHECK'))

if __name__ == '__main__':
    unittest.main()
