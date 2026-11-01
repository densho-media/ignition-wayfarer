"""B02 mass placement (S&E 15 OWN-B02-MASS-PLACEMENT-2026-10-31): mass closure, thrust-axis balance through the burn, ring balance; the axial vessel farm (TANK-AXIAL)."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import mass_model as mm
import fuel_storage


class MassModelTests(unittest.TestCase):
    def setUp(self):
        self.s = load()[0]

    def test_mass_closes(self):
        # departure = the full-return mission (1.3 kt ship + return tankage + 2.8 kt propellant, pass 7) + the unbudgeted CIRC-001 corridors
        import ring_circulation
        import operating_point
        st = mm.burn_states(self.s, steps=2)
        want = operating_point.mission(self.s)['departure_mass_kg']+ring_circulation.budget(self.s)['mass_kg']['total']
        self.assertAlmostEqual(st[0]['mass_kg'], want, delta=1.0)

    def test_balanced_load_keeps_the_thrust_line(self):
        self.assertEqual(mm.check(self.s), [])
        for row in mm.burn_states(self.s):
            self.assertLessEqual(row['differential_thrust'], self.s['physics']['mass_placement']['max_differential_thrust'])

    def test_each_species_fits_its_vessels(self):
        # the full-return inventory per species loads within fill_max of its vessels with no lateral moment of its own
        inv = fuel_storage.inventory(self.s); lim = fuel_storage.fill_max(self.s)+1e-9
        for sp, key in (('helium-3', 'helium_3'), ('deuterium', 'deuterium'), ('hydrogen', 'hydrogen')):
            rows, res = mm.balance(self.s, sp, inv[key])
            self.assertAlmostEqual(sum(r['kg'] for r in rows), inv[key], delta=1.0)
            self.assertTrue(all(r['fill'] <= lim for r in rows))
            self.assertLess(res, 1.0)

if __name__ == '__main__':
    unittest.main()
