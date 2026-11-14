"""Vertex engine and propulsion cluster (owner brief 2026-11-14): physical invariants and the single-source rule, pure modules only."""
import copy
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src/wayfarer'))
from spec import load
import drive_manifold as dm
import vertex_engine as ve
import vertex_cluster as vc

S = load(ROOT)[0]


class EngineTests(unittest.TestCase):
    def test_parts_carry_category_material_and_evidence(self):
        names = [p['name'] for p in ve.parts(S)]
        self.assertEqual(len(names), len(set(names)))
        for p in ve.parts(S):
            self.assertIn(p['category'], ve.CATEGORIES)
            self.assertIn(p['evidence'], ve.EVIDENCE)
            self.assertIn(p['material'], ve.config(S)['materials']['density_kg_m3'] | {'lamp': 0})
        # every functional category of the brief except visual effects is drawn as hardware
        self.assertEqual({p['category'] for p in ve.parts(S)}, set(ve.CATEGORIES)-{'VISUAL_EFFECTS'})

    def test_envelope_inside_its_limit(self):
        env = ve.envelope(S)
        self.assertLessEqual(env['max_radius'], ve.config(S)['geometry']['max_radius_m'])

    def test_burn_point_sits_in_the_shield_shadow_order(self):
        st = ve.stations(S)
        self.assertLess(st['burn'], st['shield_aft'])                    # aft of the shield
        self.assertAlmostEqual(st['shield_aft']-st['burn'], ve.config(S)['geometry']['standoff_m'])
        self.assertTrue(all(c['x'] < st['shield_aft'] and c['x'] > st['burn'] for c in st['coils']))
        xs = [l['x'] for l in st['loops']]
        self.assertEqual(xs, sorted(xs, reverse=True))                   # L1 forward ... L4 aft

    def test_compact_engine_is_not_a_uniform_scale_of_the_research_engine(self):
        r = S['vertex_research']; st = ve.stations(S)
        rs_r = -r['module_length_m']-r['shield_thickness_m']-r['burn_x_local_m']
        ratios = [l['r']/rl['r_m'] for l, rl in zip(st['loops'], r['loops'])]+[ve.config(S)['geometry']['standoff_m']/rs_r]
        self.assertGreater(max(ratios)/min(ratios), 1.5)

    def test_calculated_scalings(self):
        rows = {r['id']: r for r in ve.calculations(S)}
        r = S['vertex_research']; g = ve.config(S)['geometry']
        rs_r = -r['module_length_m']-r['shield_thickness_m']-r['burn_x_local_m']
        self.assertAlmostEqual(rows['C-02']['compact'], r['yield_t_TNT']*(g['standoff_m']/rs_r)**2, places=9)
        self.assertAlmostEqual(rows['C-06']['compact'], r['fusion_TW']*(g['standoff_m']/rs_r)**2, places=9)
        self.assertTrue(math.isclose(rows['C-03']['compact'], rows['C-06']['compact'], rel_tol=1e-5))   # same thing: Y_c x f_V4 at equal fluence
        self.assertGreater(rows['C-05']['compact'], 1.0)            # the quarter-power design point exceeds the research heat load ...
        self.assertEqual(rows['C-04']['evidence'], 'SPECULATIVE')    # ... so the rate and thrust rows that need it are SPECULATIVE
        self.assertEqual(rows['C-10']['evidence'], 'SPECULATIVE')
        self.assertTrue(all(r_['evidence'] in ve.EVIDENCE for r_ in rows.values()))

    def test_speculative_items_extend_breakthrough_lab_entries(self):
        for item in ve.config(S)['speculative']['items']:
            self.assertRegex(item['extends'], r'^BT-00\d(, BT-00\d)*$')


class ClusterTests(unittest.TestCase):
    def test_owner_nozzle_order(self):
        for pl, (yy, zz) in zip(vc.placements(S), dm.quadrants(S)):
            self.assertEqual((math.copysign(1, pl['origin'][1]), math.copysign(1, pl['origin'][2])), (math.copysign(1, yy), math.copysign(1, zz)))

    def test_neighbours_have_opposite_polarity(self):
        pol = {pl['n']: pl['polarity'] for pl in vc.placements(S)}
        self.assertTrue(all(pol[a] == -pol[b] for a, b in vc.ADJACENT))

    def test_rotations_are_proper(self):
        for pl in vc.placements(S):
            X, Y, Z = pl['axes']
            self.assertAlmostEqual(vc.dot(X, Y), 0); self.assertAlmostEqual(vc.dot(Y, Z), 0); self.assertAlmostEqual(vc.dot(X, Z), 0)
            cross = (X[1]*Y[2]-X[2]*Y[1], X[2]*Y[0]-X[0]*Y[2], X[0]*Y[1]-X[1]*Y[0])
            self.assertTrue(all(math.isclose(a, b, abs_tol=1e-12) for a, b in zip(cross, Z)))
            self.assertGreater(X[0], 0.99)                              # thrust forward; the cant only tips it

    def test_selected_layout_passes_its_screen(self):
        rep = vc.check(S)
        self.assertTrue(rep['study']['selection']['passes'])
        self.assertLessEqual(rep['overall_hardware_length_m'], S['ship']['length']['max'])

    def test_frame_clears_comms_sweeps(self):
        for p in vc.frame(S)+vc.distribution(S):
            if p['shape'] == 'tube' and not p.get('placement'):
                self.assertTrue(all(vc.clear_of_keepouts(S, a, b, p['radius']) for a, b in zip(p['points'], p['points'][1:])), p['name'])

    def test_each_engine_reads_only_its_own_share(self):
        for o, path, i, expr in vc.drivers(S):
            if o[:2] in ('N1', 'N2', 'N3', 'N4') and 's1+s2+s3+s4' in expr:
                own = o[1]
                self.assertIn(f'4*s{own}/', expr)
                self.assertFalse(any(f'4*s{k}/' in expr for k in '1234' if k != own))

    def test_states_follow_the_shares(self):
        off = vc.display(S, vc.state_values(S, 'OFF'))
        self.assertTrue(all(v == 0 for (o, p, i), v in off.items() if not p.startswith('hide')))
        one = vc.display(S, vc.state_values(S, 'SUSTAINED', [1.0, 0.0, 0.0, 0.0]))
        self.assertEqual(one[('N1_FX_BURN_CORE', 'color', 3)], 1.0)
        self.assertTrue(all(one[(f'N{j}_FX_BURN_CORE', 'color', 3)] == 0 for j in (2, 3, 4)))
        full = vc.effect_states(S)['states']
        self.assertTrue(all(full['SUSTAINED']['opacity'][f'N{j}_FX_PLUME'] == 1.0 for j in (1, 2, 3, 4)))
        self.assertTrue(all(full['SHUTDOWN']['opacity'][f'N{j}_FX_HOT_L2'] > 0 for j in (1, 2, 3, 4)))   # hardware stays hot after the burn

    def test_engine_change_reaches_every_instance(self):
        """Single source: a shared engine parameter moves the same part in all four placed engines, and only through the engine."""
        s2 = copy.deepcopy(S)
        c1 = next(c for c in s2['vertex_engine']['geometry']['closure_coils'] if c['name'] == 'C1'); c1['r_m'] += 0.4
        part = lambda s: next(p for p in ve.parts(s) if p['name'] == 'VTX_C1_Winding')
        self.assertAlmostEqual(part(s2)['R']-part(S)['R'], 0.4)
        for pl in vc.placements(S):
            a = vc.to_ship(pl, ve.pol(part(S)['x'], part(S)['R'], 0)); b = vc.to_ship(pl, ve.pol(part(s2)['x'], part(s2)['R'], 0))
            self.assertAlmostEqual(math.dist(a, b), 0.4)


class SelectionTests(unittest.TestCase):
    def test_engine_tables_have_their_own_build_target(self):
        sys.path.insert(0, str(ROOT/'tools'))
        import checks
        self.assertEqual(checks.TABLE_TARGETS['vertex_engine'], 'VERTEX_ENGINE')
        sys.path.insert(0, str(ROOT/'src/wayfarer/build'))
        self.assertIn('VERTEX_ENGINE', checks.TARGET_ENTRIES)


if __name__ == '__main__':
    unittest.main()
