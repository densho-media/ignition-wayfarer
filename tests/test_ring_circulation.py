"""Continuous ring circulation (CIRC-001) and the station boarding area (STN-001): the physical promises of the PROTOTYPE layout, not its
positions. Every compartment stays closable (a ring of doors), the threshold is flush, the body walks both circuits and boards from the
station clear of every collider, and the volume and gas budgets add up by hand arithmetic."""
from pathlib import Path
from collections import Counter
import math
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import habitat_ring as hr
import ring_circulation as rc
import station


class RingCirculationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s, *_ = load()

    def test_every_compartment_is_closed_by_doors(self):
        # one loop per ring: each compartment is bounded by exactly two normally-closed doors, so any door isolates its neighbours
        for j in (1, 2):
            comps = {c['id'] for c in rc.compartments(self.s, j)}
            ds = rc.doors(self.s, j)
            self.assertEqual((len(comps), len(ds)), (9, 9))
            ends = Counter(x for d in ds for x in d['between'])
            self.assertEqual(set(ends), comps)
            self.assertTrue(all(n == 2 for n in ends.values()))
            self.assertTrue(all(d['normally'] == 'CLOSED' and d['between'][0] != d['between'][1] for d in ds))

    def test_flush_threshold_and_clear_section(self):
        # the corridor floor runs through the edge of the sector's flat deck plate (deck r 28 m, sector arc 11.927 deg): no step at the door
        sec = rc.section(self.s)
        self.assertAlmostEqual(sec['floor_r'], hr.floor(self.s)/math.cos(rc.half_arc(self.s)), places=9)
        self.assertAlmostEqual(sec['floor_r'], 28.0/math.cos(math.radians(11.927/2)), delta=2e-3)
        self.assertGreaterEqual(sec['floor_r']-sec['ceiling_r'], self.s['interior']['min_headroom_m']-1e-9)

    def test_circuit_and_station_fit(self):
        self.assertEqual(rc.check(self.s), [])
        self.assertEqual(station.check(self.s), [])

    def test_budget_hand_arithmetic(self):
        b = rc.budget(self.s)
        self.assertAlmostEqual(b['total_gross_m3'], b['sector_gross_m3']+b['corridor_gross_m3'], places=6)
        self.assertAlmostEqual(b['corridor_gross_m3'], 2*b['corridor_gross_per_ring_m3'], places=6)
        # the 80 kPa 25 % O2 / 75 % N2 dry mix at 295 K: rho = p M / (R T), M = 0.25*31.998 + 0.75*28.014 g/mol
        self.assertAlmostEqual(b['atmosphere_kg'], b['corridor_gross_m3']*b['gas_density_kg_m3'], places=6)
        self.assertAlmostEqual(b['gas_density_kg_m3'], 80000.0*(0.25*0.031998+0.75*0.028014)/(8.314462618*295.0), delta=1e-3)
        self.assertGreater(b['gross_over_baseline_max'], 1.0)          # the conflict is reported, not hidden
        self.assertLessEqual({'CIRC-C1', 'CIRC-C2', 'CIRC-C3'}, {c['id'] for c in rc.conflicts(self.s)})


if __name__ == '__main__':
    unittest.main()
