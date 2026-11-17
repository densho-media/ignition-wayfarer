"""Dust-impacts study: physical invariants and agreement with the Vertex 2.6 model it reuses.

    python3 lab/studies/dust-impacts/tests/test_model.py
"""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import model as M  # noqa: E402


class DustModel(unittest.TestCase):
    def test_energy_at_cruise(self):
        # MODEL.md: a 1 mg grain at 0.016 c carries 11.5 MJ
        self.assertAlmostEqual(M.impact(1e-6, M.V_CRUISE)['E_J'] / 1e6, 11.5, delta=0.05)

    def test_energy_per_nucleon(self):
        self.assertAlmostEqual(M.impact(1e-9, M.V_CRUISE)['keV_per_u'], 119.3, delta=0.5)

    def test_faster_stops_less(self):
        a, b, c = (M.largest_stopped(v) for v in (7e3, 68.4e3, M.V_CRUISE))
        self.assertGreater(a, b)
        self.assertGreater(b, c)

    def test_brow_matches_vertex_2_6(self):
        # Vertex 2.6 NOMINAL with its own path: about 2,990 grains beyond the 2 m disruptor, 43,000 engine-front breaches
        v = M.as_vertex_2_6()
        self.assertAlmostEqual(v['brow_breaches'], 2995, delta=30)
        self.assertAlmostEqual(v['engine_breaches'], 4.3e4, delta=1e3)

    def test_corrected_path_stays_outside_1_au(self):
        segs, meta = M.mission()
        self.assertGreaterEqual(min(s['r'] for s in segs), 1.0)
        self.assertGreater(meta['brake_AU'], meta['burn_AU'])     # braking covers more distance than accelerating
        # the correction leaves the outbound Brow numbers and lowers the home braking numbers
        t = M.trip('NOMINAL')['rows'][-1]
        self.assertAlmostEqual(t['cum_brow'], 2995, delta=30)
        self.assertLess(t['cum_engines'], 0.5 * M.as_vertex_2_6()['engine_breaches'])

    def test_levers_monotonic(self):
        lv = M.levers('NOMINAL')
        b = lv['brow'][1:]
        self.assertTrue(all(x >= y for x, y in zip(b, b[1:])))
        self.assertTrue(math.isclose(lv['S'][lv['S'].index(2.0)], 2.0))


if __name__ == '__main__':
    unittest.main()
