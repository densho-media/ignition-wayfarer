"""Vertex Engine 1.5 radiation (vertex_radiation): source physics anchors and ledger closure, the ray tracer against analytic solid
angles and path lengths, transport conservation, the thermal aggregation, and that the research never changes the engine."""
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'/'wayfarer'))
import spec  # noqa: E402
import vertex_engine as ve  # noqa: E402
import vertex_magnet as vm  # noqa: E402
import vertex_plasma as vp  # noqa: E402
import vertex_radiation as vr  # noqa: E402

S = spec.load(ROOT)[0]
SIGMA_T = 8.0*math.pi/3.0*vr.R_E**2


def scene(parts):
    return vr.triangles(parts)


def intercepted(parts, src=(0.0, 0.0, 0.0), n=4096):
    tris, meta = scene(parts)
    dirs, rays = vr.trace(tris, meta, src, n, 0.01, workers=1)
    return vr.exposure(dirs, rays, meta), rays, meta


class Physics(unittest.TestCase):
    def test_reactivity_anchors(self):
        """Bosch-Hale (m3/s): D-T at 10 keV is 1.136e-16 cm3/s; D-3He stays below D-T at 50 keV."""
        self.assertAlmostEqual(vr.sigma_v('DT', 10.0)/1.136e-22, 1.0, delta=0.01)
        self.assertLess(vr.sigma_v('DHe3', 50.0), vr.sigma_v('DT', 50.0))

    def test_reaction_energies(self):
        for r, prods in vr.PRODUCTS.items():
            self.assertAlmostEqual(sum(prods.values()), vr.Q[r], delta=0.02)

    def test_klein_nishina(self):
        """sigma -> Thomson at low energy, 0.74 sigma_T at 100 keV; the energy-transfer share is 0.138 at 100 keV."""
        self.assertAlmostEqual(vr.sigma_kn(0.01)/SIGMA_T, 1.0, places=3)
        self.assertAlmostEqual(vr.sigma_kn(100.0)/SIGMA_T, 0.74, delta=0.01)
        self.assertAlmostEqual(vr.sigma_kn_transfer(100.0)/vr.sigma_kn(100.0), 0.138, delta=0.005)

    def test_bremsstrahlung_floor(self):
        """Thermal D-3He radiates at least about a fifth of its fusion power as bremsstrahlung (Te = Ti); hot-ion mode lowers it."""
        best = min(vr.ratio_at(T)['photon'] for T in (50.0, 70.0, 100.0, 150.0))
        self.assertGreater(best, 0.2)
        self.assertLess(vr.ratio_at(100.0, 0.5)['photon'], best)

    def test_ledger_closes_and_spectrum_normalised(self):
        src = vr.sources(S)
        for cid, x in src['cases'].items():
            L = x['ledger']
            self.assertTrue(L['closes'], cid)
            self.assertAlmostEqual(L['charged_J']+L['photon_J']+L['gamma_J']+L['neutron_J'], L['total_J'], delta=1e-6*L['total_J'])
            self.assertAlmostEqual(sum(x['spectrum_share']), 1.0, places=6)
            self.assertGreater(x['neutron_share'], 0.0)                               # D-D side reactions are never zero
        self.assertLessEqual(src['photon_share_range'][0], src['old_xray_share'])
        self.assertGreaterEqual(src['photon_share_range'][1], src['old_xray_share'])


class Geometry(unittest.TestCase):
    def test_sphere_solid_angle(self):
        r, d = 2.0, 10.0
        e, _, _ = intercepted([ve.part('S', 'STRUCTURE', 'sphere', 'structure', center=(d, 0.0, 0.0), radius=r, n=48)], n=16384)
        exact = (1.0-math.sqrt(1.0-(r/d)**2))/2.0
        self.assertAlmostEqual(e['intercepted'], exact, delta=0.1*exact)

    def test_torus_band(self):
        """A torus of radius R and tube a around the source covers |sin(elevation)| < a/R: a share a/R of the sky."""
        R_, a = 10.0, 1.0
        e, _, _ = intercepted([ve.part('T', 'STRUCTURE', 'torus', 'structure', x=0.0, R=R_, a=a, nu=96, nv=16)], n=16384)
        self.assertAlmostEqual(e['intercepted'], a/R_, delta=0.01)

    def test_box_path_length_and_closed_pairs(self):
        e, rays, meta = intercepted([ve.part('B', 'STRUCTURE', 'box', 'structure', center=(5.0, 0.0, 0.0), size=(2.0, 20.0, 20.0), az=0.0)])
        self.assertEqual(e['unpaired_rays'], 0)
        t0, k, L, cs = max((seg[0] for seg, ok in rays if seg), key=lambda x: x[3])
        self.assertAlmostEqual(L*cs, 2.0, delta=0.01)                               # the most normal ray crosses 2 m / cos
        self.assertAlmostEqual(t0*cs, 4.0, delta=0.01)

    def test_open_shell_counts_shell_thickness(self):
        p = ve.part('C', 'STRUCTURE', 'revolve', 'structure', profile=[(-5.0, 3.0), (5.0, 3.0)], n=64)
        e, rays, meta = intercepted([p])
        self.assertFalse(meta[0]['closed'])
        for seg, ok in rays:
            if seg:
                self.assertAlmostEqual(seg[0][2], 0.01/max(seg[0][3], 0.05), places=9)

    def test_translation_invariance(self):
        p = [ve.part('S', 'STRUCTURE', 'sphere', 'structure', center=(5.0, 1.0, 0.0), radius=1.5, n=24)]
        q = [ve.part('S', 'STRUCTURE', 'sphere', 'structure', center=(15.0, -2.0, 3.0), radius=1.5, n=24)]
        a, _, _ = intercepted(p, (0.0, 0.0, 0.0)); b, _, _ = intercepted(q, (10.0, -3.0, 3.0))
        self.assertAlmostEqual(a['intercepted'], b['intercepted'], delta=2.0/4096)   # grazing rays may flip in floating point

    def test_engine_trace_converged_and_below_1_4(self):
        R = json.loads(vr.EVIDENCE_PATH.read_text()); lad = R['geometry']['ladder']
        ns = sorted(lad, key=int)
        self.assertLess(abs(lad[ns[-1]]['intercepted']-lad[ns[-2]]['intercepted']), 0.01)
        self.assertLess(abs(R['geometry']['mesh_refinement']['difference']), 0.02)
        self.assertLess(lad[ns[-1]]['intercepted'], R['geometry']['legacy_hardware'])
        self.assertAlmostEqual(R['geometry']['legacy_hardware'], vr.audit_1_4(S)['hardware_sky'], places=9)   # the 87 % reproduces

    def test_cluster_shares_sum_to_one(self):
        R = json.loads(vr.EVIDENCE_PATH.read_text())
        self.assertAlmostEqual(sum(R['cluster']['first_hit'].values()), 1.0, places=9)
        self.assertAlmostEqual(R['cluster']['first_hit']['OWN_ENGINE'], R['geometry']['ladder']['16384']['intercepted'], delta=0.01)


class Transport(unittest.TestCase):
    def test_vacuum_transmits(self):
        self.assertEqual(vr.transport(S, [([], True)], [], [1.0]+[0.0]*8), {})

    def test_slab_attenuation(self):
        """One 0.1 m structure segment, one 100 keV-bin photon: Compton deposition = (1 - exp(-mu rho L)) x transfer share."""
        b = vr.bins(S); k = min(range(len(b)), key=lambda i: abs(b[i]-100.0)); sp = [0.0]*len(b); sp[k] = 1.0
        meta = [dict(name='slab', material='structure')]; L = 0.1
        out = vr.transport(S, [([(1.0, 0, L, 1.0)], True)], meta, sp)['slab']
        mu, mtr = vr.mu_compton(S, 'structure', b[k]); a = 1.0-math.exp(-mu*vr.smeared(S, 'structure')*L)
        self.assertAlmostEqual(out['low'], a*mtr/mu, places=12)
        self.assertAlmostEqual(out['low']+out['scattered']+out['transmitted'], out['high'], places=12)
        thick = vr.transport(S, [([(1.0, 0, 10*L, 1.0)], True)], meta, sp)['slab']
        self.assertGreater(thick['low'], out['low'])

    def test_engine_energy_conserved(self):
        R = json.loads(vr.EVIDENCE_PATH.read_text()); t = R['transport']['nominal']
        self.assertAlmostEqual(t['low']+t['scattered']+t['transmitted'], t['high'], places=9)
        self.assertLess(t['low'], t['high'])


class Thermal(unittest.TestCase):
    def test_radiator_capacity_and_aggregation(self):
        R = json.loads(vr.EVIDENCE_PATH.read_text()); th = R['thermal']; rad = S['radiators']
        cap = vr.SIGMA_SB*rad['emissivity']['value']*rad['temperature']['value']**4*rad['effective_area']['value']
        self.assertAlmostEqual(th['capacity_W'], cap, delta=1e-6*cap)
        cop = vr.config(S)['carnot_fraction']*vr.config(S)['cold_K']/(rad['temperature']['value']-vr.config(S)['cold_K'])
        self.assertAlmostEqual(th['cop'], cop, places=12)
        for cid, rows in th['cases'].items():
            for k, v in rows.items():
                self.assertAlmostEqual(v['reject_W'], v['hot_W']+v['cold_W']*(1+1/cop), delta=1e-6*v['reject_W'])
                self.assertAlmostEqual(v['four_W'], 4*v['reject_W']+v['radiator_direct_W'], delta=1e-6*v['four_W'])
            self.assertLessEqual(rows['RADIATION_low']['four_W'], rows['ALL_low']['four_W'])

    def test_pulse_vs_average(self):
        R = json.loads(vr.EVIDENCE_PATH.read_text()); f = vm.plasma(S)['pulse_Hz']
        for g, v in R['materials'].items():
            for cid, x in v['cases'].items():
                self.assertAlmostEqual(x['pulse_fluence_J_m2']*f, x['avg_flux_W_m2'], delta=1e-6*max(x['avg_flux_W_m2'], 1.0))

    def test_storage_is_not_closure(self):
        st = vr.storage(S, 1e11)
        self.assertLess(st['seconds'], 60.0)


class Integration(unittest.TestCase):
    def test_engine_unchanged_by_research(self):
        self.assertEqual(vm.config(S)['selected'], 'M0-NOMINAL')
        self.assertEqual(vp.config(S)['verdict'], 'PROPULSION_FEASIBILITY_BLOCKED')
        self.assertEqual(vr.config(S)['verdict'], 'PROPULSION_FEASIBILITY_BLOCKED')

    def test_1_4_evidence_still_current(self):
        R = json.loads(vp.EVIDENCE_PATH.read_text())
        self.assertEqual(R['input_hash'], vp.input_hash(S))

    def test_evidence_is_current(self):
        """The engineering page reads references/evidence/vertex_radiation.json (python3 src/wayfarer/vertex_radiation.py --evidence)."""
        R = json.loads(vr.EVIDENCE_PATH.read_text())
        self.assertEqual(R['input_hash'], vr.input_hash(S))
        self.assertEqual(R['outcome'], vr.config(S)['outcome'])
        self.assertEqual([g['id'] for g in R['gates']], [f'R15-{k}' for k in range(7)])


if __name__ == '__main__':
    unittest.main()
