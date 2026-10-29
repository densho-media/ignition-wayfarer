"""Fractal shielding on the Brow's ram faces: the physical invariants of a surface-only pattern, independent of Blender and Godot."""
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import forward_shield as fs
import fractal_shield as fr


class FractalShieldTests(unittest.TestCase):
    def setUp(self):
        self.s, *_ = load()
        self.u = fr.uniforms(self.s)

    def test_relief_never_perforates_the_thinnest_sheet(self):
        p = fr.params(self.s); t = min(fs.prototype(self.s)['skin_thickness_m'], fs.disruptor_layers(self.s)[0]['thickness'])
        self.assertLessEqual(p['relief_m']+p['inset_m'], p['max_relief_fraction']*t)
        deepest = min(fr.sample(self.u, y*.211, z*.211, fw)['height'] for y in range(-215, 216, 3) for z in range(-215, 216, 3) for fw in (.002, .05))
        self.assertGreaterEqual(deepest, -2*p['relief_m']-1e-12)
        self.assertLess(2*p['relief_m'], t)

    def test_every_opening_sits_inside_a_plain_collar(self):
        c = fr.params(self.s)['closeout_m']; layer = fs.disruptor_layers(self.s)[0]
        for o in fs.crown_skin_windows(self.s)+fs.crown_ports(self.s):
            for r in (o['r0'], o['r1']):
                for k in (-1, 0, 1):
                    a = o['azimuth']+k*o['half_angle']
                    self.assertLessEqual(fr.closeout_distance(self.u, r*math.cos(a), r*math.sin(a)), -c+1e-9)
        if self.u['fs_well_hex']:          # a hexagonal EYE shell is one plate: its edge sits a plate gap inside the keep-out
            self.assertLessEqual(max(fr.eye_shell_probes(self.s, self.u)), -fr.params(self.s)['plate_gap_m']+1e-9)
        for w in [] if self.u['fs_well_hex'] else fs.wells(self.s)+fs.eye_ports(self.s, layer):
            for k in range(12):
                a = 2*math.pi*k/12
                self.assertLessEqual(fr.closeout_distance(self.u, w['y']+w['radius']*math.cos(a), w['z']+w['radius']*math.sin(a)), -c+1e-9)
        self.assertLessEqual(fr.closeout_distance(self.u, fs.lance_hole_radius(self.s, layer), 0.0), -c+1e-9)

    def test_each_plate_hangs_on_three_clamps_each_holding_three_plates(self):
        a = self.u['fs_side']; plates = {}
        for q in range(-3, 4):
            for r in range(-3, 4):
                cy, cz = a*1.5*q, a*math.sqrt(3)*(r+q/2)
                for k in (0, 2, 4):                   # the A corners
                    key = (round(cy+a*math.cos(k*math.pi/3), 6), round(cz+a*math.sin(k*math.pi/3), 6))
                    plates.setdefault(key, set()).add((q, r))
        inner = [v for (y, z), v in plates.items() if math.hypot(y, z) < 2*a]
        self.assertTrue(inner and all(len(v) == 3 for v in inner))
        self.assertLess(self.u['fs_gap'], self.u['fs_fastener'])
