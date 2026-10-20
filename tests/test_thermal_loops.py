"""AFT-010 heat-loop screen: independent closed forms, reciprocity, synthetic scenes and spec mutations. Fast (synthetic scenes, small sampling
overrides); it never reads the stored report."""
from pathlib import Path
import copy
import json
import math
import re
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load as _load, validate
import thermal_budget as tb
import thermal_loops as tl

ROOT = Path(__file__).resolve().parents[1]
SIGMA = 5.670374419e-8                   # independent copy of 01_CONSTANTS; the module must agree with it
SMALL = dict(rays_per_point=324, points_per_zone=[2, 2])


_LOADED = []


def load():
    """Validated spec, loaded once (validation takes seconds); tests deep-copy before mutating."""
    if not _LOADED:
        _LOADED.append(_load())
    return _LOADED[0]


def point_zone(name, pts, loop='warm', area=100.0, index=0):
    return dict(name=name, loop=loop, surface='TEST', area_m2=area, points=lambda n1, n2: pts, index=index)


def hot_plane(O, A, B, u0, u1, v0, v1):
    return tl.plane(O, A, B, [(u0, u1, v0, v1, 'HOT')])


class RegimeTests(unittest.TestCase):
    def setUp(self):
        self.s, self.sources, *_ = load()

    def test_owner_examples(self):
        ex = tl.owner_examples(self.s)
        self.assertAlmostEqual(tl.ideal_area_m2(5e6, 450.0, 0.9), 2389.27, delta=0.01)
        self.assertLess(abs(ex['warm']['ideal_area_m2'] - 2390), 1)
        self.assertAlmostEqual(tl.ideal_area_m2(1e5, 320.0, 0.9), 186.87, delta=0.01)
        self.assertLess(abs(ex['cold']['ideal_area_m2'] - 187), 1)
        for name in ('warm', 'cold'):
            self.assertAlmostEqual(ex[name]['ideal_area_m2'] / ex[name]['stored_ideal_area_m2'], 1, delta=1e-9)

    def test_defense_band_areas_have_no_literals(self):
        want = [7167.82, 14335.64, 23892.73, 38228.36]
        got = [b['ideal_area_m2'] for b in tl.defense_band_areas(self.s)]
        for a, b in zip(got, want):
            self.assertAlmostEqual(a / b, 1, delta=1e-6)
        s2 = copy.deepcopy(self.s)
        s2['thermal']['loops']['defense_routing']['normal_W'] = [2.0e7, 3.0e7]
        self.assertAlmostEqual(tl.defense_band_areas(s2)[0]['ideal_area_m2'], 2.0e7/(0.9*SIGMA*450.0**4), delta=1e-6)
        self.assertNotAlmostEqual(tl.defense_band_areas(s2)[0]['ideal_area_m2'], got[0], places=0)

    def test_stefan_boltzmann_is_shared_and_unchanged(self):
        self.assertIs(tl.SIGMA, tb.SIGMA)
        self.assertEqual(tl.SIGMA, SIGMA)
        self.assertNotRegex((ROOT/'src/wayfarer/thermal_loops.py').read_text(), r'5\.67')
        self.assertAlmostEqual(tb.ideal_rejection_W(30000, 0.9, 1800.0) / 16.0718e9, 1, delta=1e-5)
        self.assertAlmostEqual(tb.ideal_rejection_W(30000, 0.9, 1800.0), 0.9*SIGMA*30000*1800.0**4, delta=1)
        self.assertAlmostEqual(tb.root_calibration_margin_W(self.s) / -1598528238, 1, delta=3e-5)     # 40!B73, Q52 option D
        self.assertAlmostEqual(self.s['radiators']['root_calibration_margin']['value'], tb.root_calibration_margin_W(self.s), delta=1)

    def test_break_even(self):
        reg = tl.regimes(self.s)
        h = reg['hot']
        for name, want in (('warm', 0.0043403), ('cold', 0.0011099)):
            r = reg[name]
            f = tl.break_even_F(r['T_K'], r['emissivity'], r['absorptance'], h['T_K'], h['emissivity'])
            self.assertAlmostEqual(f, want, delta=5e-8)
            self.assertAlmostEqual(f, (r['T_K']/h['T_K'])**4/h['emissivity'], delta=1e-12)         # alpha = eps closed form
            self.assertAlmostEqual(tl.net_flux_W_m2(r['T_K'], r['emissivity'], r['absorptance'], 1.0, [(f, h['emissivity'], h['T_K'])]), 0.0, delta=1e-9)


class ViewFactorTests(unittest.TestCase):
    def test_differential_element_to_coaxial_disc(self):
        a, h = 3.0, 4.0
        want = a*a/(a*a + h*h)
        poly = [(h, a*math.cos(2*math.pi*i/256), a*math.sin(2*math.pi*i/256)) for i in range(256)]
        self.assertAlmostEqual(tl.contour_F((0, 0, 0), (1, 0, 0), poly), want, delta=1e-4)
        sc = tl.empty_scene()
        sc['annuli'].append(tl.annulus(h, 0.0, a, 'HOT'))
        mc = tl.view_factors(sc, point_zone('DISC', [((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))]), dict(rays_per_point=10000, seed=7, sigma_multiple=3, points_per_zone=[1, 1]))
        self.assertLessEqual(abs(mc['F_hot'] - want), mc['F_hot_bound'])
        self.assertAlmostEqual(mc['F_hot'] + mc['F_space'], 1.0, places=12)

    def test_long_wedge_against_the_strip_formula(self):
        # Two 10^4 m blades at 30 and 150 degrees, radial 6.5..37; a casing point at 90 degrees, radius 6.
        half = 1e4/2
        sc = tl.empty_scene()
        for deg in (30.0, 150.0):
            a = math.radians(deg)
            sc['planes'].append(hot_plane((0, 0, 0), (1, 0, 0), (0, math.cos(a), math.sin(a)), -half, half, 6.5, 37.0))
        p, n = (0.0, 0.0, 6.0), (0.0, 0.0, 1.0)
        want = 0.0
        for deg in (30.0, 150.0):
            a = math.radians(deg)
            phis = [math.atan2(r*math.cos(a), max(r*math.sin(a) - 6.0, 0.0)) for r in (6.5, 37.0)]    # angle from the normal; the part below the horizon is clipped
            want += abs(math.sin(phis[1]) - math.sin(phis[0]))/2
        self.assertAlmostEqual(tl.exact_hot_F(sc, p, n)[0], want, delta=2e-3)

    def test_perpendicular_plates_and_reciprocity(self):
        n1, n2 = 40, 40
        grid = [((i + 0.5)/n1, (j + 0.5)/n2) for i in range(n1) for j in range(n2)]
        plate1 = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]          # z = 0, normal +z
        plate2 = [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]          # y = 0, normal +y
        f12 = sum(tl.contour_F((x, y, 0.0), (0, 0, 1), plate2) for x, y in grid)/len(grid)
        f21 = sum(tl.contour_F((x, 0.0, z), (0, 1, 0), plate1) for x, z in grid)/len(grid)
        self.assertAlmostEqual(f12, 0.2000, delta=1e-3)
        self.assertAlmostEqual(1.0*f12, 1.0*f21, delta=1e-3)

    def test_ship_casing_zone_reciprocity(self):
        s, *_ = load()
        sc = tl.scene(s)
        zone = next(z for z in tl.zones(s) if z['name'] == 'CASING_1_5')
        pl = sc['planes'][0]
        one = dict(planes=[pl], frusta=[], annuli=[])
        pts = zone['points'](8, 8)
        a_zone = zone['area_m2']/3
        a_f_c = a_zone*sum(tl.exact_hot_F(one, p, n)[0] for p, n in pts)/len(pts)             # casing zone to the blade plane
        # The same patch as planar facets, seen from blade-face points on a graded grid near the root.
        rc = tl.thermal_geometry.casing_radius(s)
        xa, xb = tl._casing_span(s)
        sm = tl.study(s)['sampling']
        th0 = math.radians(s['prototype']['radiator_phase_deg'])
        dth, dx = math.radians(s['radiators']['separation_deg'])/sm['casing_azimuth_bands'], (xb - xa)/sm['casing_axial_bands']
        x0 = xa + 4*dx

        def corner(i, j):
            t = th0 + dth*i/8
            return (x0 + dx*j/4, rc*math.cos(t), rc*math.sin(t))
        facets = [[corner(i, j), corner(i + 1, j), corner(i + 1, j + 1), corner(i, j + 1)] for i in range(8) for j in range(4)]
        ox, oy, oz, ax, ay, az, bx, by, bz, nx, ny, nz, rects = pl
        w = rects[-1][3]
        mid = (x0 + dx/2, rc*math.cos(th0 + dth/2), rc*math.sin(th0 + dth/2))
        cu = (mid[0] - ox)*ax + (mid[1] - oy)*ay + (mid[2] - oz)*az
        nu, nv, span = 60, 24, 160.0
        acc = 0.0
        for i in range(nu):
            u = cu + (i + 0.5)/nu*span - span/2
            for j in range(nv):
                t = (j + 0.5)/nv
                v, weight = w*t*t, span/nu*w*2*t/nv
                p = (ox + u*ax + v*bx, oy + u*ay + v*by, oz + u*az + v*bz)
                sign = 1.0 if sum((mid[k] - p[k])*(nx, ny, nz)[k] for k in range(3)) > 0 else -1.0
                acc += weight*sum(tl.contour_F(p, (sign*nx, sign*ny, sign*nz), f) for f in facets)
        self.assertAlmostEqual(acc/a_f_c, 1.0, delta=0.02)


class CastTests(unittest.TestCase):
    def setUp(self):
        self.s, *_ = load()
        self.regs = tl.regimes(self.s)
        self.sm = dict(rays_per_point=400, seed=3, sigma_multiple=3, points_per_zone=[1, 1])

    def test_hidden_surface_free_to_space(self):
        reg = self.regs['warm']
        zone = point_zone('FREE', [((0.0, 0.0, 0.0), (0.0, 0.0, 1.0))])
        row = tl.zone_row(tl.empty_scene(), zone, self.sm, self.regs)
        self.assertEqual(row['F_space'], 1.0)
        flux = reg['emissivity']*SIGMA*reg['T_K']**4
        for case in tl.CASES:
            self.assertAlmostEqual(row['cases'][case]['q_W_m2']/flux, 1.0, delta=1e-12)
            self.assertEqual(row['cases'][case]['cls'], 'USABLE')

    def test_blades_not_radiating_removes_only_the_hot_term(self):
        sc = tl.empty_scene()
        sc['planes'].append(hot_plane((0, 0, 2.0), (1, 0, 0), (0, 1, 0), -91.0, 91.0, 0.0, 30.0))
        zone = point_zone('FACING', [((0.0, 15.0, 0.0), (0.0, 0.0, 1.0))])
        row = tl.zone_row(sc, zone, self.sm, self.regs)
        reg, h = self.regs['warm'], self.regs['hot']
        bnr = row['cases']['BLADES_NOT_RADIATING']['q_W_m2']
        self.assertAlmostEqual(bnr, reg['emissivity']*SIGMA*reg['T_K']**4*row['F_space'], delta=1e-9)
        self.assertAlmostEqual(row['cases']['HIGH_POWER']['q_W_m2'], bnr - reg['absorptance']*row['F_hot']*h['emissivity']*SIGMA*h['T_K']**4, delta=1e-6)

    def test_panel_two_metres_off_a_blade_face(self):
        sc = tl.empty_scene()
        sc['planes'].append(hot_plane((0, 0, 0), (1, 0, 0), (0, 1, 0), -91.0, 91.0, 0.0, 30.0))
        sm = dict(self.sm, points_per_zone=[3, 3])
        grid = [(x, y) for x in (-3.0, 0.0, 3.0) for y in (12.0, 15.0, 18.0)]
        facing = point_zone('FACING', [((x, y, 2.0), (0.0, 0.0, -1.0)) for x, y in grid], area=100.0)
        away = point_zone('AWAY', [((x, y, 2.0), (0.0, 0.0, 1.0)) for x, y in grid], area=100.0)
        rf, ra = tl.zone_row(sc, facing, sm, self.regs), tl.zone_row(sc, away, sm, self.regs)
        self.assertEqual((rf['cases']['HIGH_POWER']['cls'], rf['cases']['BLADES_NOT_RADIATING']['cls']), ('NET_HEATED', 'USABLE'))
        self.assertEqual((ra['cases']['HIGH_POWER']['cls'], ra['cases']['BLADES_NOT_RADIATING']['cls']), ('USABLE', 'USABLE'))
        self.assertGreater(rf['cases']['HIGH_POWER']['absorbed_W'], 0)
        self.assertEqual(ra['F_hot'], 0.0)

    def test_blocker_shades_the_receiver(self):
        planes = [hot_plane((0, 0, 0), (1, 0, 0), (0, 1, 0), -91.0, 91.0, 0.0, 30.0)]
        zone = point_zone('FACING', [((0.0, 15.0, 2.0), (0.0, 0.0, -1.0))])
        open_sc = dict(planes=planes, frusta=[], annuli=[])
        wall = dict(planes=planes, frusta=[], annuli=[tl.annulus(0.05, 0.0, 1e3, 'BLOCKER')])     # hides the plate beyond x = 0.05
        f_open, f_wall = tl.view_factors(open_sc, zone, self.sm), tl.view_factors(wall, zone, self.sm)
        self.assertLess(f_wall['F_hot'], 0.6*f_open['F_hot'])
        self.assertGreater(f_wall['F_blocker'], 0.3)
        self.assertAlmostEqual(f_wall['F_hot'] + f_wall['F_blocker'] + f_wall['F_space'], 1.0, places=12)


class SceneTests(unittest.TestCase):
    def setUp(self):
        self.s, self.sources, *_ = load()

    def test_hot_area_and_live_ring_reads(self):
        sc = tl.scene(self.s)
        self.assertAlmostEqual(sc['hot_area_per_face_m2']/self.s['radiators']['physical_area']['value'], 1.0, delta=1e-9)
        self.assertEqual(len(sc['planes']), self.s['radiators']['count'])
        s2 = copy.deepcopy(self.s)
        s2['habitat']['ring_service_clearance']['min_m'] += 2.025      # RING_A is DERIVED (layout.ring_a_offset_m) since HAB-001
        sc2 = tl.scene(s2)
        ro = tl.habitat_ring.outer(self.s)
        rings = [(f[0], f[1]) for f in sc['frusta'] if math.isclose(f[2], ro)]
        rings2 = [(f[0], f[1]) for f in sc2['frusta'] if math.isclose(f[2], ro)]
        self.assertEqual(len(rings), 2)
        for (a, b), (c, d) in zip(rings, rings2):
            self.assertAlmostEqual(c - a, 2.025, places=9)
            self.assertAlmostEqual(d - b, 2.025, places=9)
        z1 = {z['name']: z for z in tl.zones(self.s)}
        z2 = {z['name']: z for z in tl.zones(s2)}
        for name in z1:
            if name.startswith('RING_'):
                p1, p2 = z1[name]['points'](2, 2), z2[name]['points'](2, 2)
                for (a, _), (b, _) in zip(p1, p2):
                    self.assertAlmostEqual(b[0] - a[0], 2.025, places=9, msg=name)

    def test_zone_points_keep_their_own_ring_and_panel_geometry(self):
        zs = {z['name']: z for z in tl.zones(self.s)}
        c1, c2 = tl.habitat_ring.centers(self.s)
        for label in ('OUTER_RIM', 'INNER_RIM'):
            x1 = sum(p[0] for p, _ in zs[f'RING_1_{label}']['points'](1, 4))/4
            x2 = sum(p[0] for p, _ in zs[f'RING_2_{label}']['points'](1, 4))/4
            self.assertAlmostEqual(x1, c1, places=9)
            self.assertAlmostEqual(x2, c2, places=9)
        for sign in '+-':
            plate = [p for p, _ in zs[f'PANEL_BLADE_PLANE_1_{sign}']['points'](1, 1)][0]
            bis = [p for p, _ in zs[f'PANEL_BISECTOR_1_{sign}']['points'](1, 1)][0]
            sep = math.radians(self.s['radiators']['separation_deg'])
            th0 = math.radians(self.s['prototype']['radiator_phase_deg'])
            self.assertAlmostEqual(math.atan2(plate[2], plate[1]) % math.tau, th0 % math.tau, places=9)
            self.assertAlmostEqual(math.atan2(bis[2], bis[1]) % math.tau, (th0 + sep/2) % math.tau, places=9)

    def test_moving_the_blade_front_moves_scene_and_panels(self):
        s2 = copy.deepcopy(self.s)
        s2['layout']['datums']['radiator_aft_gap_m'] += 1.125
        sc1, sc2 = tl.scene(self.s), tl.scene(s2)
        self.assertAlmostEqual(sc2['planes'][0][0] - sc1['planes'][0][0], 1.125, places=9)
        e1, e2 = tl._panel_envelope(self.s), tl._panel_envelope(s2)
        self.assertAlmostEqual(e2['x_lo'] - e1['x_lo'], 1.125, places=9)
        p1 = {z['name']: z for z in tl.zones(self.s)}['PANEL_BISECTOR_1_+']['points'](1, 1)[0][0][0]
        p2 = {z['name']: z for z in tl.zones(s2)}['PANEL_BISECTOR_1_+']['points'](1, 1)[0][0][0]
        self.assertGreater(p2 - p1, 0.0)

    def test_stale_check_sees_a_study_change(self):
        s2 = copy.deepcopy(self.s)
        s2['thermal']['loops']['study']['sampling']['seed'] += 1
        self.assertNotEqual(json.dumps(tl.live_inputs(self.s), default=str), json.dumps(tl.live_inputs(s2), default=str))

    def test_zero_exchange_direction_is_reported(self):
        rep = tl.report(self.s, sampling=dict(rays_per_point=144, points_per_zone=[2, 2]), zone_filter=lambda n: n.startswith('RING_'), exact=False)
        zx = rep['zero_exchange_assumption']
        self.assertIn('OPTIMISTIC', zx['direction']['cold']['HIGH_POWER'])
        self.assertIn('PESSIMISTIC', zx['direction']['warm']['BLADES_NOT_RADIATING'])
        codes = {f['code']: f for f in rep['findings']}
        self.assertTrue(codes['COLD_EXAMPLE_COVERAGE']['depends_on_zero_exchange'])
        self.assertIn('BNR_CLASSES_ASSUMPTION_DEPENDENT', codes)
        self.assertNotIn('best case', ' '.join(rep['assumptions']).replace('not a strict best case', ''))

    def test_zones_are_derived_and_complete(self):
        zs = tl.zones(self.s)
        self.assertEqual(len(zs), 90)
        casing = sum(z['area_m2'] for z in zs if z['surface'] == 'CASING')
        xa, xb = tl._casing_span(self.s)
        self.assertAlmostEqual(casing, 2*math.pi*tl.thermal_geometry.casing_radius(self.s)*(xb - xa), delta=1e-6)
        self.assertAlmostEqual(casing, 6866.9, delta=0.1)
        self.assertFalse(any(z.get('dock_corridor_conflict') for z in zs))
        env = tl._panel_envelope(self.s)
        self.assertAlmostEqual(env['r_lo'], 30.15, places=9)
        self.assertAlmostEqual(env['r_hi'], 37.0, places=9)

    def test_report_leaves_the_spec_untouched(self):
        before = copy.deepcopy(self.s)
        tl.report(self.s, sampling=dict(rays_per_point=16, points_per_zone=[1, 1]), zone_filter=lambda n: n.endswith('_1') or n.startswith('RING_1_O'), exact=False)
        self.assertEqual(before, self.s)

    def test_monte_carlo_agrees_with_exact_on_casing_zones(self):
        rep = tl.report(self.s, sampling=SMALL, zone_filter=lambda n: n.startswith('CASING'))
        self.assertEqual(len(rep['zones']), 60)
        for r in rep['zones']:
            self.assertLessEqual(abs(r['F_hot'] - r['F_hot_exact_unoccluded']), r['F_hot_bound'] + 1e-12, r['name'])
            self.assertGreaterEqual(r['exact_refinement_delta'], 0.0)
            self.assertLess(r['exact_refinement_delta'], 0.05, r['name'])      # quadrature error of the 3 x 3 grid
        self.assertTrue(any(f['code'] == 'WARM_CASING_IDEAL_BOUND_BELOW_NORMAL' for f in rep['findings']))
        bound = rep['deterministic_bound']
        self.assertAlmostEqual(bound['casing_ideal_W']/1e6, 14.37, delta=0.01)


class SpecTests(unittest.TestCase):
    def setUp(self):
        self.s, self.sources, *_ = load()

    def mutate(self, path, value):
        s = copy.deepcopy(self.s)
        node = s['thermal']['loops']['study']
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
        return s

    def test_mutations_fail(self):
        tl.check_study(self.s)
        bad = [self.mutate(['status'], 'WORKING'), self.mutate(['sampling', 'kind'], 'PROTOTYPE'), self.mutate(['sampling', 'rays_per_point'], 2000),
               self.mutate(['sampling', 'rays_per_point'], 0), self.mutate(['panel_families'], ['BLADE_PLANE', 'DIAGONAL']),
               self.mutate(['sampling', 'panel_length_m'], 4.0), self.mutate(['panel_x'], 4.0), self.mutate(['tilt_deg'], 4.0),
               self.mutate(['panel_area_m2'], 4.0), self.mutate(['anchor'], {'datum': 'RING_A', 'offset_m': 1.0}),
               self.mutate(['cases'], ['HIGH_POWER']), self.mutate(['sampling', 'points_per_zone'], [4])]
        for s in bad:
            with self.assertRaises(ValueError):
                tl.check_study(s)
        s = copy.deepcopy(self.s)
        s['thermal']['loops']['warm']['area'] = {'unit': 'm2', 'value': 5000.0, 'canon_status': 'OPEN', 'evidence_ref': 'thermal_warm_regime'}
        with self.assertRaises(ValueError):
            validate(s, self.sources)
        with self.assertRaises(ValueError):
            validate(self.mutate(['status'], 'WORKING'), self.sources)

    def test_isolation(self):
        for path in (ROOT/'src/wayfarer').rglob('*.py'):
            if path.name in ('thermal_loops.py', 'spec.py'):
                continue
            text = path.read_text()
            self.assertNotIn('thermal_loops', text, path.name)
            self.assertNotIn("['loops']['study']", text, path.name)
        module = (ROOT/'src/wayfarer/thermal_loops.py').read_text().lower()
        self.assertNotIn('atmosphere', module)
        self.assertNotIn('eclss', module)
        self.assertIsNone(re.search(r'^(import spec|from spec)', module, re.M))


if __name__ == '__main__':
    unittest.main()
