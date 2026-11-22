"""Physical invariants of the selective-fusion explainer model (lab test, outside CI; D-T00-1)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import model  # noqa: E402

K = model.canon()


class Invariants(unittest.TestCase):
    def test_ledger_closes(self):
        for pol in model.POL:
            for mode in model.MODES:
                for Ti in (60.0, 100.0, 160.0):
                    for d in (0.2, 0.5):
                        lg = model.ledger(model.point(d, Ti, mode, pol), 0.5, K)
                        if lg['sustains']:
                            self.assertAlmostEqual(lg['closure'], 1.0, places=9)

    def test_d_lean_cuts_neutrons_raises_photons(self):
        a, b = model.point(0.5, 100.0, 'thermal', 'none'), model.point(0.25, 100.0, 'thermal', 'none')
        self.assertLess(b['neutron'], a['neutron'])
        self.assertGreater(b['photon'], a['photon'])

    def test_polarisation_raises_charged_share(self):
        a, b = model.point(0.5, 100.0, 'thermal', 'none'), model.point(0.5, 100.0, 'thermal', 'polarised')
        self.assertLess(b['neutron'], a['neutron'])
        self.assertLess(b['photon'], a['photon'])

    def test_hot_ion_trades_photons_for_injector_power(self):
        a, b = model.point(0.5, 100.0, 'thermal', 'none'), model.point(0.5, 100.0, 'hot-ion', 'none')
        self.assertLess(b['photon'], a['photon'])
        self.assertEqual(a['ei'], 0.0)
        self.assertGreater(b['ei'], 0.0)

    def test_nothing_closes_the_b01_budget(self):
        best = min(model.ledger(model.point(d, Ti, m, p), 0.0, K)['radiator_multiple'] or 1e99
                   for p in model.POL for m in model.MODES for Ti in model.TI_KEV for d in model.D_SHARES)
        self.assertGreater(best, 1.0)       # even with no photon exposure, neutrons alone exceed the drive's radiator share


if __name__ == '__main__':
    unittest.main()
