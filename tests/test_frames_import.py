"""FRM-002-2026-10-10 (S&E 15!A125, C-017/C-018): unreleased channels and streams carry no number; a released table imports unchanged or is refused."""
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import frames_import as fi


def sheet(rows):
    return {(r,c):SimpleNamespace(value=v) for r,row in enumerate(rows,1) for c,v in enumerate(row,1)}


class FramesImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=fi.frames(ROOT);cls.route=json.loads((ROOT/'simulations/wf_route_v1.json').read_text())
        t=cls.route['columns'].index('mission_t_s');cls.t=[r[t] for r in cls.route['frames']]
    def table(self,frames=True):
        rows=[['mission_t_s','frame','thrust','scenario_id','scenario_version','status','source','validation'],['s',None,'N',None,None,None,None,None]]
        rows+=[[t,float(n) if frames else None,1.0e6*n,'S-TEST','v1','WORKING','15!A125 test','PASS'] for n,t in enumerate(self.t,1)]
        return rows
    def test_unreleased_channels_are_unknown_and_null(self):
        for g in ('channels','streams'):
            for cid,c in self.data[g].items():
                self.assertEqual(c['status'],'UNKNOWN');self.assertIsNone(c['values']);self.assertIsNone(c['scenario_id'])
    def test_a_released_table_imports_unchanged(self):
        for frames in (True,False):
            rows=self.table(frames);header,units,got=fi.read_table(sheet(rows))
            self.assertEqual(fi.failures('thrust',fi.CHANNELS['thrust'],header,units,got,self.route),[])
            self.assertEqual([r['thrust'] for r in got],[r[2] for r in rows[2:]])
        # time-tagged samples need not fall on the route frames (C-017: a frame only if matched)
        rows=self.table(False)[:2]+[[0.5,None,1.0,'S-TEST','v1','WORKING','x','PASS'],[7.25,None,2.0,'S-TEST','v1','WORKING','x','PASS']]
        self.assertEqual(fi.failures('thrust',fi.CHANNELS['thrust'],*fi.read_table(sheet(rows)),self.route),[])
    def test_fidelity_failures_refuse_the_import(self):
        c=fi.CHANNELS['thrust']
        def bad(edit):
            rows=self.table();edit(rows);return fi.failures('thrust',c,*fi.read_table(sheet(rows)),self.route)
        self.assertTrue(bad(lambda r:r[1].__setitem__(2,'MN')))              # unit
        self.assertTrue(bad(lambda r:r[3].__setitem__(5,'UNKNOWN')))         # a number under UNKNOWN status
        self.assertTrue(bad(lambda r:r[3].__setitem__(7,'FAIL')))            # validation flag
        self.assertTrue(bad(lambda r:r[3].__setitem__(4,'v2')))              # one scenario version
        self.assertTrue(bad(lambda r:r[3].__setitem__(6,None)))              # a source on every row
        self.assertTrue(bad(lambda r:r[3].__setitem__(1,7.0)))               # a frame that is not the route frame at that time
        self.assertTrue(bad(lambda r:r[4].__setitem__(0,r[3][0])))           # mission time strictly increasing
        self.assertTrue(bad(lambda r:r[3].__setitem__(2,None)))              # an empty value is not filled
    def test_phase_and_event_streams(self):
        # C-018: separate tables; an unknown onset stays untimed, never interpolated; a phase never ends before it starts.
        c={**fi.STREAMS['degraded_mode']}
        rows=[['phase_id','start_mission_t_s','end_mission_t_s','scenario_id','scenario_version','status','source','validation'],
              [None,'s','s',None,None,None,None,None],
              ['RAD_LOSS',100.0,None,'S-TEST','v1','WORKING','x','PASS'],['RING_STOP',None,None,'S-TEST','v1','WORKING','x','PASS']]
        self.assertEqual(fi.stream_failures('degraded_mode',c,*fi.read_table(sheet(rows))),[])
        rows[2][2]=50.0;self.assertTrue(fi.stream_failures('degraded_mode',c,*fi.read_table(sheet(rows))))
        rows[2][2]=None;rows[3][0]='RAD_LOSS';self.assertTrue(fi.stream_failures('degraded_mode',c,*fi.read_table(sheet(rows))))
    def test_the_written_contract_is_current(self):
        self.assertEqual(fi.run(ROOT,check=True)['result'],'CURRENT')


if __name__=='__main__':unittest.main()
