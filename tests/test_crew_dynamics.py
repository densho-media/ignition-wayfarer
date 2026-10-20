"""PHYS-001 crew dynamics: owner numbers (08/11/46) and physical invariants of the local field and frames."""
from pathlib import Path
import math
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/wayfarer'))
from spec import load
import crew_dynamics as cd


class CrewDynamicsTests(unittest.TestCase):
    def setUp(self):
        self.s=load()[0];self.fx={f['id']:f for f in cd.fixtures(self.s)}

    def test_ring_floor_and_head_gravity_match_08(self):
        for ring in 'AB':
            floor=self.fx[f'RING_{ring}_FLOOR'];head=self.fx[f'RING_{ring}_HEAD']
            self.assertAlmostEqual(floor['expect_g'],0.5009732933,places=6)   # 08 floor_g
            self.assertAlmostEqual(head['expect_g'],0.4651894866,places=6)    # 08 head_g
            self.assertLess(floor['expect'][2],0)                                # outward: toward the floor at r = (0, 0, -R)
            self.assertAlmostEqual(1-head['expect_g']/floor['expect_g'],0.07142857143,places=6)

    def test_coriolis_magnitude_direction_and_ring_sign(self):
        a=self.fx['RING_A_CORIOLIS_TANGENTIAL'];b=self.fx['RING_B_CORIOLIS_TANGENTIAL']
        self.assertAlmostEqual(cd.norm(a['expect']),0.8377580410,places=6)     # 2 * 0.41888 * 1 m/s (DYN-003 ~0.838)
        self.assertAlmostEqual(a['expect_g'],0.0854,places=4)
        self.assertLess(a['expect'][2],0)                                        # ring A: spinward +Y at the floor presses outward
        for i in range(3):self.assertAlmostEqual(a['expect'][i],-b['expect'][i])   # opposite ring, opposite deflection
        r=self.fx['RING_A_CORIOLIS_RADIAL']['expect']
        self.assertAlmostEqual(r[1],0.8377580410,places=6)                      # rising toward the axis (+Z) drifts spinward (+Y)
        self.assertAlmostEqual(cd.dot(r,(0,0,1)),0.0)

    def test_low_thrust_tilt_and_high_power_lock(self):
        self.assertAlmostEqual(self.fx['LOW_THRUST_TILT']['expect_tilt_deg'],11.29,places=2)
        for k in 'AB':
            e=self.fx[f'HIGH_POWER_RING_{k}_LOCKED']['expect']
            self.assertAlmostEqual(e[0],-1.5*cd.G0);self.assertEqual(e[1:],[0.0,0.0])   # no centrifugal floor when locked, aft down
        self.assertEqual(self.fx['SPINE_COAST_DRIFT']['expect'],[0.0,0.0,0.0])        # no generic floor gravity on the spine
        self.assertFalse(cd.ship_accel(self.s,'HIGH_POWER')['known'])                   # an envelope, not a flight value

    def test_frame_round_trip_keeps_position_and_inertial_velocity(self):
        w=cd.ring_omega(self.s,1,'COAST')
        for r,v,ang in [((60.0,3.0,-27.5),(0.2,-0.1,0.4),0.7),((54.0,0.0,0.0),(0.0,0.0,0.0),5.0)]:
            rr,vr=cd.to_ring(r,v,57.0,ang,w);r2,v2=cd.to_ship(rr,vr,57.0,ang,w)
            for x,y in zip(r+v,r2+v2):self.assertAlmostEqual(x,y,places=12)
        # A body at rest on the spine looks like it moves backwards against the spin in the ring frame, at w r.
        _,vr=cd.to_ring((57.0,0.0,-28.0),(0.0,0.0,0.0),57.0,0.0,w)
        self.assertAlmostEqual(cd.norm(vr),cd.norm(w)*28.0)

    def test_ring_signs_follow_owner_convention(self):
        # 08 ring_sign_convention / DYN-023: ring A (aft) +4 rpm, ring B (forward) -4 rpm about bowward +X (right-hand rule)
        import habitat_ring
        xa,xb=habitat_ring.centers(self.s)[:2];self.assertLess(xa,xb)                      # ring A is the aft ring
        wa=cd.ring_omega(self.s,0,'COAST');wb=cd.ring_omega(self.s,1,'COAST')
        self.assertAlmostEqual(wa[0],2*math.pi*4/60);self.assertAlmostEqual(wb[0],-2*math.pi*4/60)
        self.assertEqual(wa[1:]+wb[1:],(0.0,)*4)
        for k in (0,1):self.assertEqual(cd.ring_omega(self.s,k,'HIGH_POWER'),(0.0,0.0,0.0))   # locked under thrust

    def test_push_impulse_scales_with_mass(self):
        self.assertAlmostEqual(self.fx['PUSH_HUMAN_IVA']['expect_dv'][1]/self.fx['PUSH_HUMAN_SUITED']['expect_dv'][1],220/75)
        for m in (60.0,75.0,90.0,220.0):                                                    # DYN-024: vary the fixture mass
            self.assertAlmostEqual(cd.push_dv((0.0,30.0,0.0),m)[1]*m,30.0)

    def test_tether_fixtures_reproduce_owner_diagnostics(self):
        od=self.s['owner_diagnostics']    # 45 I-16..I-19: 75 / 66 N s; 4500 / 3960 N at dt 1/60 s (timestep artifacts, CALC-R06)
        for fid,j,f in (('TETHER_HUMAN_IVA','tether_impulse_iva_N_s','tether_force_iva_dt60_N'),('TETHER_HUMAN_SUITED','tether_impulse_suited_N_s','tether_force_suited_dt60_N')):
            x=self.fx[fid];self.assertAlmostEqual(math.hypot(*x['expect_impulse_n_s']),od[j],places=6);self.assertAlmostEqual(x['expect_anchor_force_n'],od[f],places=3)

    def test_tether_is_tension_only_and_accounts_its_impulse(self):
        m=75.0;dt=1/60
        p,v,taut,rec=cd.tether((3.0,0,0),(0.5,0.2,0),(0,0,0),2.0,m,dt)
        self.assertTrue(taut);self.assertEqual(p,(2.0,0.0,0.0));self.assertEqual(v,(0.0,0.2,0.0))
        for i in range(3):self.assertAlmostEqual(m*(v[i]-(0.5,0.2,0)[i]),rec['impulse_n_s'][i])   # J = m dv on the body
        self.assertAlmostEqual(rec['anchor_force_n'],m*0.5/dt)
        for case in [((1.0,0,0),(0.5,0,0)),((2.5,0,0),(-0.3,0.1,0))]:                    # slack, or taut but moving inward
            _,v2,_,r2=cd.tether(case[0],case[1],(0,0,0),2.0,m,dt)
            self.assertEqual(v2,case[1]);self.assertEqual(r2['impulse_mag_n_s'],0.0)
        a=self.fx['TETHER_HUMAN_IVA'];b=self.fx['TETHER_HUMAN_SUITED']
        self.assertAlmostEqual(b['expect_impulse_n_s'][0]/a['expect_impulse_n_s'][0],(220*0.3)/(75*1.0))
        self.assertFalse(cd.contract(self.s)['tether']['known'])

    def test_spin_down_ramp_and_euler_term(self):
        T=self.s['physics']['rotor_operations']['spin_up_time_s'];w0=2*math.pi*4/60
        for k,sg in ((0,1),(1,-1)):
            w,a=cd.spin_ramp(self.s,k,0.0);self.assertAlmostEqual(w[0],sg*w0);self.assertAlmostEqual(a[0],-sg*w0/T)
            self.assertAlmostEqual(cd.spin_ramp(self.s,k,T/2)[0][0],sg*w0/2)
            w,a=cd.spin_ramp(self.s,k,T);self.assertEqual((w[0],a[0]),(0.0,0.0))
            self.assertAlmostEqual(abs(cd.spin_ramp(self.s,k,1.0)[1][0]),0.0002327105669,places=12)   # 08 alpha
        ea=self.fx['SPIN_DOWN_RING_A_EULER']['expect_euler'];eb=self.fx['SPIN_DOWN_RING_B_EULER']['expect_euler']
        self.assertAlmostEqual(abs(ea[1]),0.0002327105669*28.0,places=9)                        # |alpha| r at the floor
        self.assertAlmostEqual(ea[1],-eb[1])                                                 # mirrored between the rings

    def test_transition_sequence_follows_owner_order(self):
        t=cd.transition(self.s,'COAST','HIGH_POWER')
        self.assertEqual(t['steps'],['OCCUPANTS_SECURED','RINGS_SPIN_DOWN','RINGS_LOCKED','DRIVE_ON']);self.assertFalse(t['timed'])
        self.assertEqual(cd.transition(self.s,'LOW_THRUST','HIGH_POWER')['steps'],['DRIVE_OFF','OCCUPANTS_SECURED','RINGS_SPIN_DOWN','RINGS_LOCKED','DRIVE_ON'])
        self.assertEqual(cd.transition(self.s,'HIGH_POWER','EVA')['steps'],['DRIVE_OFF','OCCUPANTS_SECURED','RINGS_UNLOCKED','RINGS_SPIN_UP'])
        for a in cd.MODES:
            for b in cd.MODES:
                st=cd.transition(self.s,a,b)['steps']
                if any(x in st for x in cd.RAMP_STEPS):                                          # no ring ramp with the drive on
                    self.assertTrue('DRIVE_ON' not in st[:st.index('OCCUPANTS_SECURED')] and self.s['configuration'][a]['drive']=='OFF' or 'DRIVE_OFF' in st)
        self.assertFalse(cd.ramp_allowed(True,True)['allowed']);self.assertFalse(cd.ramp_allowed(False,False)['allowed'])
        self.assertTrue(cd.ramp_allowed(False,True)['allowed'])
        self.assertFalse(cd.transition(self.s,'COAST','DAMAGED')['allowed'])

    def test_vestibule_gate_fails_closed(self):
        tol=0.004*2*math.pi/60;w=cd.ring_omega(self.s,0,'COAST')[0];shut={'STATIONARY':True,'RING':True}
        ok=lambda **k:cd.vestibule_gate(**({'side':'RING','drum_w':w,'side_w':w,'restrained':True,'closures':shut,'dp_equalized':True,'ramping':False,'tol':tol}|k))['open']
        self.assertTrue(ok())
        self.assertFalse(ok(ramping=True))                                                   # drum changing speed
        self.assertFalse(ok(closures={'STATIONARY':False,'RING':True}))                     # never both open
        self.assertFalse(ok(drum_w=w*0.9))                                                    # speed mismatch
        self.assertFalse(ok(dp_equalized=None))                                               # pressure unknown (threshold OPEN)
        self.assertFalse(ok(tol=None))
        self.assertTrue(ok(side='STATIONARY',drum_w=0.0,side_w=0.0))
        self.assertFalse(cd.vestibule_ramp_allowed(False,shut)['allowed'])
        self.assertFalse(cd.vestibule_ramp_allowed(True,{'STATIONARY':True,'RING':False})['allowed'])
        # handoff: a restrained occupant at rest in the synchronized drum keeps its inertial velocity through the frame change
        r=(85.0,0.0,-1.4);v_ship=cd.cross((w,0,0),cd.sub(r,(85.0,0,0)))
        rr,vr=cd.to_ring(r,v_ship,85.0,0.3,(w,0,0));self.assertAlmostEqual(cd.norm(vr),0.0)
        r2,v2=cd.to_ship(rr,vr,85.0,0.3,(w,0,0))
        for x,y in zip(v_ship,v2):self.assertAlmostEqual(x,y,places=12)

    def test_nav_graph_gates_by_boundary_mode_and_actor(self):
        g=cd.nav(self.s)
        self.assertEqual(cd.route(g,'SECTOR_1_1','REFUGE','COAST','human_iva'),['SECTOR_1_1','VESTIBULE_1','TRUNK','REFUGE'])
        self.assertIsNone(cd.route(g,'SECTOR_1_1','REFUGE','COAST','human_iva',closed={'TRUNK-VESTIBULE_1'}))   # closed hatch removes the path
        self.assertIsNone(cd.route(g,'TRUNK','DOCK_PRIMARY','COAST','human_iva'))                               # docks only when docked
        self.assertIsNone(cd.route(g,'TRUNK','EVA_EXTERIOR','EVA','human_iva'))                                 # unsuited never goes outside
        self.assertEqual(cd.route(g,'SP12','EVA_EXTERIOR','EVA','human_suited'),['SP12','AIRLOCK_EVA','EVA_EXTERIOR'])
        self.assertIsNone(cd.route(g,'SP12','EVA_EXTERIOR','COAST','human_suited'))                             # exterior only in EVA
        self.assertIsNone(cd.route(g,'TRUNK','SECTOR_1_1','COAST','human_suited'))                              # suited stays off the tubes
        self.assertEqual(g['casualty']['result'],'HOLD')
        hp=g['technique_by_mode']['HIGH_POWER'];co=g['technique_by_mode']['COAST']
        tube=next(i for i,e in enumerate(g['edges']) if e['to']=='SECTOR_1_1')
        self.assertEqual((co[tube],hp[tube]),('LADDER_RADIAL','LADDER_AFT_DOWN'))


if __name__=='__main__':unittest.main()
