"""Simulation rig contract, independent of Blender."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
from sim_rig import anchors, contract


def walk(node):
    if isinstance(node,dict):
        for value in node.values():yield from walk(value)
    elif isinstance(node,list):
        for value in node:yield from walk(value)
    else:yield node


class SimRigTests(unittest.TestCase):
    def setUp(self):
        self.s,_,self.spec_text,self.source_text=load()
        self.anchors=anchors(self.s)
    def test_center_of_mass_and_inertia_stay_unknown(self):
        root=next(a for a in self.anchors if a['name']=='WF_SIM_ROOT')['quantities']
        for key in ['center_of_mass','inertia','mass_distribution']:
            self.assertIs(root[key]['known'],False);self.assertNotIn('value',root[key])
        self.assertFalse(any('COM' in a['name'] for a in self.anchors))
        mass=contract(self.s,self.spec_text,self.source_text)['mass_properties']
        self.assertIs(mass['center_of_mass']['known'],False);self.assertNotIn('value',mass['center_of_mass'])
    def test_flight_and_structural_thrust_channels_stay_separate(self):
        nozzles=[a['quantities'] for a in self.anchors if a['name'].startswith('WF_SIM_NOZZLE_')]
        self.assertEqual(len(nozzles),4)
        self.assertAlmostEqual(sum(q['flight_thrust_share']['value'] for q in nozzles),self.s['propulsion']['flight_thrust']['value']*1e6)
        self.assertAlmostEqual(sum(q['structural_design_load_share']['value'] for q in nozzles),self.s['propulsion']['design_thrust']['value']*1e6)
        self.assertFalse(any('design_thrust_share' in q for q in nozzles))
        thrust=next(a for a in self.anchors if a['name']=='WF_SIM_THRUST_CENTER')
        self.assertEqual(thrust['position_m'][1:],[0.0,0.0])
        self.assertLess(thrust['quantities']['flight_thrust']['value'],thrust['quantities']['structural_design_load']['value'])


if __name__=='__main__':unittest.main()
