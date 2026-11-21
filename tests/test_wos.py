"""WOS ship state: the shell shows the parameters' own values with their status and a mapped source, and an unknown as OPEN."""
from pathlib import Path
import sys
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'src' / 'wayfarer'))
import spec as spec_module  # noqa: E402
import wos  # noqa: E402


class WosStatus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = spec_module.load(ROOT)[0]
        cls.st = wos.status(cls.spec)

    def test_values_are_the_parameters(self):
        it, s = self.st['items'], self.spec
        self.assertEqual(it['crew_rated']['value'], 12)          # the design crew (owner, 2026-11-08); 6 is the story manifest
        self.assertEqual(it['ring_rpm']['value'], float(s['habitat']['rpm']))
        self.assertEqual(it['target_speed']['value'], float(s['mission']['target_speed']['value']))
        self.assertEqual(it['configuration']['value'], s['vehicle']['saved_preset'])

    def test_every_value_is_sourced_and_unknowns_stay_open(self):
        source_map = tomllib.loads((ROOT / 'data' / 'source_map.toml').read_text())['sources']
        self.assertEqual(wos.validate(self.st, source_map), [])
        self.assertFalse(self.st['items']['power_rating']['known'])
        self.assertNotIn('value', self.st['items']['power_rating'])


if __name__ == '__main__':
    unittest.main()
