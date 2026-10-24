"""EVA-001 safety invariants of the suit contract, the tether protocol and the training route (S&E 43/44, RUN-012, RIG-01)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
import eva_access
import eva_route
import eva_suit as es
import hull_geometry
import spec


class Contract(unittest.TestCase):
    def test_open_values_stay_null(self):
        data = es.load()
        for k, f in es.telemetry_contract(data).items():
            if f['status'] == 'OPEN':
                self.assertIsNone(f['value'], k)
        for k in ('suit_pressure_kpa', 'prebreathe_protocol', 'suit_dry_mass_kg', 'eva_duration_h', 'heat_rejection_w', 'radiator_proximity_gate',
                  'ring_keepout_m', 'tether_length_m'):
            self.assertIsNone(data['telemetry'][k]['value'], k)
        self.assertEqual(data['telemetry']['cabin_pressure_kpa']['value'], 80.0)
        self.assertIn('NOT CERTIFIED', data['suit']['certification'])

    def test_actions_inside_suit_mobility(self):
        data = es.load()
        for H in (1.70, 1.78):
            rep = es.mobility_report(es.actions(H, data, 30), data['mobility'])
            bad = [(a, j) for a, v in rep.items() for j, x in v.items() if not x['ok']]
            self.assertEqual(bad, [], H)

    def test_unsuited_actions_are_never_eva(self):
        # the shared crawl / climb fail suited coverage: they must never enter the EVA library the runtime plays
        self.assertFalse(set(es.SHARED_ACTIONS) & set(es.EVA_ACTIONS))


class Tethers(unittest.TestCase):
    def test_protocol(self):
        t = es.Tethers([0.0, 1.5, 3.0, 4.5], reach=2.0)
        self.assertIn('refused', t.release('A'))                    # the only tether
        self.assertIsNotNone(t.clip('B', 0, 0.0))                   # one anchor for both is not independent
        self.assertIsNotNone(t.clip('B', 2, 0.0))                   # out of reach
        self.assertEqual(t.move(0.0, 3.0), 2.0)                     # reach clamps the body
        self.assertIsNone(t.clip('B', 1, 1.4))
        self.assertIn('refused', t.release('A'))                    # B untested
        self.assertIsNone(t.test('B')); self.assertIsNone(t.release('A'))
        self.assertEqual(t.live(), ['B'])

    def test_handoff_plan_never_zero(self):
        anchors = [0.0, 1.5, 3.0, 4.5]
        for start, goal in ((0, 3), (3, 0)):
            t = es.Tethers(anchors, 2.0, start); at = anchors[start]; t.t = dict(A=dict(anchor=start, tested=True), B=None)
            for verb, which, a in es.handoff_plan(anchors, start, goal):
                if verb == 'move':
                    at = t.move(at, anchors[a])
                else:
                    self.assertIsNone(t.clip(which, a, at) if verb == 'clip' else getattr(t, verb)(which))
                self.assertGreaterEqual(len(t.live()), 1)
            self.assertAlmostEqual(at, anchors[goal])


class Route(unittest.TestCase):
    def test_gates_fail_closed(self):
        s = spec.load()[0]; data = es.load(); rt = eva_route.route(s, data)
        for k, h in rt['holds'].items():
            self.assertNotEqual(h['status'], 'GO', k)                # OPEN limits never become GO
            g = {x['id']: x for x in h['gates']}
            self.assertEqual(g['drive']['status'], 'PASS')           # EVA config: drive OFF
            self.assertGreater(g['ring']['measured'], 0.0, k)        # the suited sweep stays out of ring B's
            self.assertEqual(g['ring']['status'], 'UNKNOWN')         # its margin is OPEN
            self.assertNotEqual(g['thermal']['status'], 'PASS')      # blade 1 is in sight: no safe distance exists (EVA-045)
            self.assertTrue(all(x['state'] != 'VALIDATED' for x in h['gates']), k)
        self.assertEqual(rt['flight']['state'], 'HOLD'); self.assertFalse(rt['flight']['available'])   # EVA-049, 45 O-07
        for a in rt['anchors']:                                      # rails and anchors only on the stationary forward collar
            self.assertGreater(eva_route.body_radius(s, a['x']), 6.0)


class Eva002(unittest.TestCase):
    """EVA-002 (43 EVA-040..055): the trade case stays a study, the stations are Tale's, suits never use the interior route, and every
    SP-11 candidate keeps its bodies clear of the outer leaf's swing inside the forward collar."""

    def test_trade_case_is_not_a_setpoint(self):
        data = es.load()
        self.assertEqual(data['reference_case']['suit_pressure_kpa'], 40.0)               # 45 P-06 WORKING TRADE CASE
        self.assertEqual(data['reference_case']['status'], 'WORKING TRADE CASE')
        self.assertIsNone(data['telemetry']['suit_pressure_kpa']['value'])                 # still OPEN as a suit value
        self.assertIsNone(data['telemetry']['prebreathe_protocol']['value'])
        for k, f in data['thermal_case'].items():
            if f['status'].startswith('OPEN'):
                self.assertIsNone(f['value'], k)
        self.assertFalse(data['modes']['flight']['available'])

    def test_stations_are_tale_scripts(self):
        st = es.load()['station']
        self.assertEqual([s['script'] for s in st], [f'SCRIPT-{n:02d}' for n in range(5, 12)])

    @unittest.skipUnless(eva_access.ENVELOPES.exists(), 'run `workflow.py eva` first')
    def test_suits_not_on_the_interior_route(self):
        s = spec.load()[0]; env = eva_access.load_envelopes(); fit = __import__('json').loads((eva_access.ROOT/'references/p1_eva_fit.json').read_text())
        for row in eva_access.route_access(s, fit, eva_access.classes(s, env)):
            for k, v in row.items():
                if isinstance(v, dict):
                    self.assertTrue(v['permitted'].startswith('NOT'), (row['bottleneck'], k))

    @unittest.skipUnless(eva_access.ENVELOPES.exists(), 'run `workflow.py eva` first')
    def test_sp11_candidates_clear_the_leaf(self):
        s = spec.load()[0]; data = es.load(); env = eva_access.load_envelopes(); V = env['variants']; m = data['access']['suit_margin_m']
        f = next(x for x in hull_geometry.service_fittings(s) if x['name'] == 'Airlock_EVA'); clr = s['prototype']['mechanical_clearance_m']
        for r in eva_access.candidates(s, env, data):
            ch, dr = r['chamber'], r['door']
            sweep = eva_access.leaf_sweep(dr, __import__('math').radians(ch['outer_leaf']['hinge_deg']), ch['leaf_face_a_m']+dr['t'])
            for o in r['occupants']:
                planes = eva_access.placed(V[o['variant']][o['pose']], o['theta_deg'], o['shift_m'], o['a_top_m'])[1]
                self.assertTrue(eva_access.clear_of(planes, sweep, m), (r['id'], o['variant']))
            self.assertLessEqual(__import__('math').hypot(ch['outer_bulkhead_a_m'], ch['clear_radius_m']+.05), ch['hull_skin_m']-clr+1e-9, r['id'])


class Eva003(unittest.TestCase):
    """EVA-003 owner numbers (45 G-11..G-14) and the pressure rule on the inner-hatch mechanisms (15!G127)."""
    def test_owner_apertures(self):
        q = es.load()['sp11_eva3']
        self.assertEqual((q['benchmark_m'], q['lead_m'], q['rescue_m']), (1.10, 1.20, 1.35))

    @unittest.skipUnless(eva_access.ENVELOPES.exists(), 'run `workflow.py eva` first')
    def test_no_latch_only_reverse_load_passes(self):
        import eva_sp11
        for r in eva_sp11.mechanism_rows():
            for k, m in r['mechanisms'].items():
                if m['reverse_load_kn'] is None or m['reverse_load_kn'] > 0:
                    self.assertNotEqual(m['status'], 'PASS', (r['id'], k))


class SlidingPlug(unittest.TestCase):
    """S&E 15!A134 / 45 I-01..I-04: the interlock fails closed while its threshold is OPEN, the diagnostic forces and the reverse-load readback."""
    def test_interlock_and_forces(self):
        import eva_sp11_plug as pl
        pq = es.load()['sp11_plug']; t = pl.interlock(pq)
        self.assertIsNone(t['inputs']['dp_threshold_kpa']); self.assertIsNone(t['forces']['lever_force_actual_n'])
        self.assertAlmostEqual(t['forces']['ideal_aperture_force_derived_n'], pq['ideal_aperture_force_n'], places=5)
        self.assertFalse(pl.permits(t, 'unlatch the inner plug (chamber', 0.0, None, True)[0])        # OPEN threshold: no permission
        self.assertFalse(pl.permits(t, 'unlatch the inner plug (chamber', 0.05, 0.05, False)[0])      # the other closure not confirmed
        self.assertTrue(pl.permits(t, 'unlatch the inner plug (chamber', 0.05, 0.05, True)[0])

    def test_reverse_load_derivation(self):
        import eva_sp11_plug as pl
        s = spec.load()[0]; d = es.load(); pq = d['sp11_plug']; dr = eva_access.door(s, pq['aperture_m'])
        r = pl.retention(s, dict(door=dr, chamber=dict(inner_bulkhead_a_m=2.5, clear_radius_m=1.05), latch={}), pq, d['sp11_eva3'])
        self.assertTrue(r['readback_matches_leaf_outer'])                     # 45 I-08: 106.19 kN is the leaf-outer-diameter bound
        self.assertAlmostEqual(r['per_dog_kn'], 8.85, places=2)              # 45 I-09
        self.assertAlmostEqual(r['per_dog_one_failed_kn'], 9.65, places=2)   # 45 I-10
        self.assertLess(r['seal_line_comparison_kn'], r['derived_reverse_kn'])
        self.assertLess(r['lever']['back_drive_nominal_n'] + 1e-9, 1e-6)      # the pressure load has no component on the lever


class Sim027(unittest.TestCase):
    """SIM-027 redlines: the keeper clearance is stroke minus lug hang (the owner rejects the 0.040 m of the published chain) and the 106.19 kN bound is unchanged."""
    def test_keeper_chain(self):
        import eva_sp11_plug as pl
        s = spec.load()[0]; d = es.load(); pq = d['sp11_plug']; dr = eva_access.door(s, pq['aperture_m']); row = dict(door=dr, chamber=dict(inner_bulkhead_a_m=2.5, clear_radius_m=1.05), latch={})
        base = pl.retention(s, row, pq, d['sp11_eva3'])
        self.assertAlmostEqual(base['keeper_drop_clearance_m'], 0.040, places=3)           # the published chain, MARGINAL: the owner does not accept it
        for kv in pq['redline_keeper']:
            q2 = dict(d['sp11_eva3'], plug_stroke_m=kv['stroke_m']); pq2 = dict(pq, dog_h_m=kv['dog_h_m'], ledge_h_m=kv['ledge_h_m'], ledge_recess_m=kv['ledge_recess_m'])
            r = pl.retention(s, row, pq2, q2)
            self.assertAlmostEqual(r['keeper_drop_clearance_m'], kv['stroke_m']-(kv['dog_h_m']+kv['ledge_h_m']-kv['ledge_recess_m']), places=3, msg=kv['id'])
            self.assertAlmostEqual(r['derived_reverse_kn'], 106.2, places=1)                  # the 1.30 m leaf bound does not depend on the keeper profile

    def test_access_segments_schema(self):
        import json
        f = eva_access.ROOT/'references/p1_access_seg_sp11_sp12.json'
        if not f.exists():
            self.skipTest('run `python3 src/wayfarer/eva_sp11.py --segments`')
        r = json.loads(f.read_text()); self.assertEqual(set(r), {'study', 'source', 'segments'})
        keys = {'id', 'route', 'states', 'variant', 'case', 'least_m', 'status', 'worst_case_over', 'seed_spread_m', 'nearest', 'note'}
        for g in r['segments']:
            self.assertEqual(set(g), keys, g['id'])
            if g['least_m'] is None:
                self.assertEqual(g['status'], 'OPEN', g['id'])
            else:                                                                             # bands: PASS >= 0.05, MARGINAL 0..0.05, FAIL < 0
                self.assertEqual(g['status'], 'PASS' if g['least_m'] >= 0.05-1e-9 else ('MARGINAL' if g['least_m'] >= -1e-9 else 'FAIL'), g['id'])
            if g['seed_spread_m']:
                self.assertLessEqual(g['seed_spread_m'][0], g['least_m']+1e-9, g['id'])      # least_m is the minimum over the seeds


if __name__ == '__main__':
    unittest.main()
