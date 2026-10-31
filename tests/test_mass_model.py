"""B02 mass placement (S&E 15 OWN-B02-MASS-PLACEMENT-2026-10-31): mass closure, thrust-axis balance through the burn, ring balance."""
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
        # departure = the B01 1,300 t protected and operational ship + the 600 t inventory + the unbudgeted CIRC-001 corridors
        import ring_circulation
        st = mm.burn_states(self.s, steps=2)
        inv = sum(fuel_storage.cfg(self.s)['inventory_kg'].values())
        want = self.s['physics']['operating_point']['protected_and_operational_kg']+inv+ring_circulation.budget(self.s)['mass_kg']['total']
        self.assertAlmostEqual(st[0]['mass_kg'], want, delta=1.0)

    def test_balanced_load_keeps_the_thrust_line(self):
        self.assertEqual(mm.check(self.s), [])
        for row in mm.burn_states(self.s):
            self.assertLessEqual(row['differential_thrust'], self.s['physics']['mass_placement']['max_differential_thrust'])

    def test_each_species_fits_its_cells(self):
        inv = fuel_storage.cfg(self.s)['inventory_kg']; lim = 1/(1+fuel_storage.cfg(self.s)['ullage'])+1e-9
        for sp, kg in (('deuterium', inv['deuterium']), ('hydrogen', inv['hydrogen_first_ignition']+inv['hydrogen_reserve'])):
            rows, _ = mm.balance(self.s, sp, kg)
            self.assertAlmostEqual(sum(r['kg'] for r in rows), kg, delta=1.0)
            self.assertTrue(all(r['fill'] <= lim for r in rows))


if __name__ == '__main__':
    unittest.main()
