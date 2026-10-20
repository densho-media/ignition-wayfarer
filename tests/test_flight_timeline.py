"""First Ignition timeline (FUT-004): owner numbers at the marks and the thrust/rotor rules, independent of Blender."""
from pathlib import Path
import copy
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import flight_timeline as ft


class FlightTimelineTests(unittest.TestCase):
    def setUp(self):
        self.s,self.sources,_,_=load()
        self.ps=ft.phases(self.s);self.ch=ft.channels(self.s,self.ps)
    def value(self,mark,name):
        return ft.sample(self.s,mark,self.ch,self.ps)['values'][name]
    def test_burn_end_is_the_exact_owner_result(self):
        # 20_FIRST_IGNITION C11, C13, C16 (Q35) through the imported route: exact, at a key of its own, never the 7.75 d Sanity label (P1-009).
        self.assertAlmostEqual(self.value('TL_BURN_END','kinematics.burn_elapsed_s'),652166.8906,delta=1e-3)
        self.assertAlmostEqual(self.value('TL_BURN_END','kinematics.burn_elapsed_s')/86400,7.5482279,places=7)
        self.assertAlmostEqual(self.value('TL_BURN_END','kinematics.distance_AU'),6.970320784,places=9)
        self.assertAlmostEqual(self.value('TL_BURN_END','kinematics.speed_c'),0.016,places=12)
        self.assertAlmostEqual(self.value('TL_BURN_END','kinematics.acceleration_g'),1.5,places=12)
    def test_burn_plays_one_imported_route_row_per_frame(self):
        # 26_BLENDER_CONTRACT C-010 / NAV-027: every burn frame shows the route row of the same number, unchanged.
        burn=next(p for p in self.ps if p['id']=='BURN');r=ft.route(self.s);cols=r['columns']
        self.assertEqual(burn['frame_end']-burn['frame_start']+1,len(r['frames']))
        for n,row in enumerate(r['frames']):
            for name,col in ft.ROUTE_COLUMNS.items():
                self.assertEqual(ft.value_at(self.ch[f'kinematics.{name}']['keys'],burn['frame_start']+n),row[cols.index(col)])
    def test_acceleration_never_exceeds_the_peak_and_speed_holds_after_the_burn(self):
        burn=next(p for p in self.ps if p['id']=='BURN')
        for f in range(1,self.ps[-1]['frame_end']+1):
            self.assertLessEqual(ft.value_at(self.ch['kinematics.acceleration_g']['keys'],f),1.5+1e-12)
        speeds=[ft.value_at(self.ch['kinematics.speed_c']['keys'],f) for f in range(burn['frame_end'],self.ps[-1]['frame_end']+1)]
        self.assertEqual(len(set(speeds)),1)
    def test_both_rotors_share_one_spin_channel(self):
        self.assertEqual(len(self.ch['rotor.spin_fraction']['binding']['controls']),2)
    def test_thrust_needs_the_rings_stopped_and_locked(self):
        # 08!A47, MEC-011: starting the drive during the spin-down is rejected.
        s=copy.deepcopy(self.s);rows=s['flight_timeline']['phases']['list']
        next(r for r in rows if r.get('id')=='SPIN_DOWN')['drive']='startup';del next(r for r in rows if r.get('id')=='DRIVE_START')['drive']
        with self.assertRaisesRegex(ValueError,'rings not stopped and locked'):ft.validate(s,self.sources)
    def test_open_phases_carry_no_seconds_and_unknowns_stay_unknown(self):
        self.assertTrue(all(ft.display(self.s,p)['duration_s'] is None for p in self.ps if p['duration'] in ('OPEN','UNSCALED')))
        s=copy.deepcopy(self.s);next(r for r in s['flight_timeline']['phases']['list'] if r.get('id')=='SPIN_DOWN')['duration_s']=1800.0
        with self.assertRaisesRegex(ValueError,'no seconds'):ft.validate(s,self.sources)
        for path in self.s['flight_timeline']['unknown']['paths']:
            self.assertIs(ft.path_value(self.s,path)['known'],False)
    def test_frame_channels_carry_no_number_until_released(self):
        # FLIGHT-FRAMES-2026-10-10 (15!H117): an UNKNOWN channel is null at every frame; the route stays DIAGNOSTIC (15!I117).
        for f in (1,self.ps[-1]['frame_end']):
            v=ft.sample(self.s,f,self.ch,self.ps)['values']
            self.assertTrue(all(v[n] is None for n,c in self.ch.items() if c.get('status')=='UNKNOWN' and n.startswith('frames.')))
        self.assertEqual(self.ch['drive.thrust_level']['status'],'UNKNOWN')
        self.assertTrue(all(self.ch[f'kinematics.{n}']['status']=='DIAGNOSTIC' for n in ft.ROUTE_COLUMNS))
    def test_a_released_frame_channel_plays_its_rows_and_supersedes_the_presentation(self):
        fr=copy.deepcopy(ft.frames(self.s));c=fr['channels']['thrust'];n=ft.route(self.s)['frame_count']
        c.update(status='WORKING',values=[float(i) for i in range(n)],frame=list(range(1,n+1)),mission_t_s=list(range(n)));c.pop('placeholder')
        burn=next(p for p in self.ps if p['id']=='BURN');orig=ft.frames;ft.frames=lambda s:fr
        try:ch=ft.channels(self.s,self.ps)
        finally:ft.frames=orig
        for i in (0,n//2,n-1):self.assertEqual(ft.value_at(ch['frames.thrust']['keys'],burn['frame_start']+i),float(i))
        self.assertIsNone(ft.value_at(ch['frames.thrust']['keys'],burn['frame_end']+1))
        self.assertEqual(ch['drive.thrust_level']['superseded_by'],['frames.thrust'])
    def test_rings_never_reverse_and_rest_at_their_index(self):
        # FUT-007: the integrated turn under every keyed spin ramp (rotor actions and the timeline).
        import rotor_interface as ri
        rev=ri.frames_per_turn(self.s)
        runs=[[(f,v['spin_fraction']) for f,v in keys] for a in ri.actions(self.s).values() for keys in a['slots'].values()]
        runs.append([(f,v) for f,v,_ in self.ch['rotor.spin_fraction']['keys']])
        for spin in runs:
            turned=ri.spin_turned(self.s,spin);values=[v for _,v in turned]
            self.assertTrue(all(b>=a-1e-9 for a,b in zip(values,values[1:])))
            at=dict(turned)
            for f,v in spin:
                if v==0:self.assertAlmostEqual(min(at[f]%rev,rev-at[f]%rev),0,places=6)


if __name__=='__main__':unittest.main()
