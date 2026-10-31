"""Attitude control check (pass 6, WORKING, Claude under the owner's delegation of 2026-10-31; S&E 15 OWN-ATT-CHECK-2026-10-31).

Takes the B02 placed inertia (mass_model.burn_states) and asks which actuator carries each torque. Standard library only.

- flip: a bang-bang 180 deg pitch flip on the RCS couple (exterior_hardware.sizing: one jet at each end), time and propellant;
- burn trim: the thrust through the 26 mm lateral CG offset against the RCS couple, the CMG storage and the drive's differential channel
  thrust (physics.mass_placement.max_differential_thrust at the nozzle offset); the drive's thrust-axis alignment the remaining
  differential authority allows, and the trim a misaligned axis would need;
- rings: each ring's angular momentum turned through the flip loads its rotor bearings with H x omega (internal; the counter-rotating
  pair cancels it in the ship), and the net residual's gyroscopic torque on the ship;
- CMGs: the crew moving between rings, in people the storage absorbs before the rings retrim;
- gravity gradient near Earth (the station's orbit is not released, B04): 3 mu / r^3 (I_t - I_roll) sin(a) cos(a) at LEO and GEO.

    python3 src/wayfarer/attitude.py      # prints the check and writes references/p1_attitude.json
"""
import json
import math
from pathlib import Path

import body_equipment
import exterior_hardware as eh
import mass_model
from habitat_ring import G0

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'references/p1_attitude.json'


def q(s):
    return s['physics']['attitude']


def flip(I, tau, F, isp):
    """Bang-bang 180 deg flip: accelerate half the angle, decelerate the other half."""
    T = math.sqrt(4*math.pi*I/tau); J = 2*F*T
    return dict(flip_min=T/60, peak_rate_deg_s=math.degrees(tau*T/2/I), propellant_kg={f'isp_{int(i)}': J/(i*G0) for i in isp})


def report(s):
    z = eh.sizing(s); r = z['rcs']; ht = eh.table(s); F = ht['rcs_thrust_N']; tau = r['pitch_yaw_couple_N_m']
    states = mass_model.burn_states(s); dep, end = states[0], states[-1]
    mp = s['physics']['mass_placement']; lim = mp['max_differential_thrust']; r_noz = s['prototype']['nozzle_offset_m']
    x_thrust = eh.thrust_ring(s)[0]; storage = z['momentum']['storage_N_m_s']; rd = s['physics']['rotor_dynamics']
    H_ring = rd['angular_momentum_each_N_m_s']; H_res = rd['allowed_residual_momentum_N_m_s']; fails = []

    flips = {}
    for name, st in (('departure', dep), ('burnout', end)):
        I = max(st['I_pitch'], st['I_yaw']); f = flip(I, tau, F, ht['rcs_isp_s'])
        w = math.radians(f['peak_rate_deg_s'])
        f.update(I_transverse=I, I_roll=st['I_roll'], roll_accel_deg_s2=math.degrees(r['roll_couple_two_pods_N_m']/st['I_roll']),
                 ring_bearing_moment_N_m=H_ring*w, net_gyro_torque_N_m=H_res*w)
        flips[name] = f

    trim = []
    for st in states:
        need = st['steer_torque_N_m']; auth = lim*st['thrust_N']*r_noz; L = st['cg_m'][0]-x_thrust
        spare = auth-need; align = math.degrees(math.atan(spare/(st['thrust_N']*L))) if st['thrust_N'] else None
        trim.append(dict(t_h=st['t_s']/3600, thrust_N=st['thrust_N'], lateral_m=st['lateral_m'], torque_N_m=need, rcs_share=need/tau,
                         cmg_fill_s=storage/need if need else None, drive_authority_N_m=auth, thrust_lever_m=L, alignment_limit_deg=align))
    worst = max(trim, key=lambda t: t['torque_N_m']); live = [t for t in trim if t['thrust_N'] > 0]
    align_deg = min(t['alignment_limit_deg'] for t in live)
    if worst['torque_N_m'] > worst['drive_authority_N_m']:
        fails.append('drive differential thrust cannot hold the lateral CG offset')
    if align_deg <= 0:
        fails.append('no differential authority left for thrust-axis misalignment')
    mis = []
    for a in q(s)['misalignment_cases_deg']:
        t = end; L = t['cg_m'][0]-x_thrust; M = t['thrust_N']*math.sin(math.radians(a))*L
        mis.append(dict(misalignment_deg=a, torque_N_m=M, differential_thrust=(M+t['steer_torque_N_m'])/(t['thrust_N']*r_noz)))

    person = mp['person_kg']; import habitat_ring as hr
    per_person = 2*person*hr.floor(s)**2*rd['omega_rad_s']
    cmg = dict(storage_N_m_s=storage, residual_per_person_N_m_s=per_person, people_absorbed=storage/per_person,
               units=body_equipment.sizing(s)['units'])

    gg = []
    a = math.radians(q(s)['gravity_gradient_angle_deg'])
    for rr in q(s)['gravity_gradient_orbit_r_m']:
        n2 = q(s)['mu_earth_m3_s2']/rr**3
        T = 3*n2*(dep['I_pitch']-dep['I_roll'])*math.sin(a)*math.cos(a)
        gg.append(dict(orbit_r_m=rr, torque_N_m=T, rcs_share=T/tau))
    return dict(status=q(s)['canon_status'], rcs_couple_N_m=tau, rcs_lever_m=r['pitch_yaw_lever_m'], flips=flips,
                burn_trim=dict(worst=worst, alignment_limit_deg=align_deg, states=trim), misalignment=mis, cmg=cmg,
                gravity_gradient=gg, failures=fails)


def check(s):
    return report(s)['failures']


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load
    s = load()[0]; r = report(s)
    OUTPUT.write_text(json.dumps(r, indent=1, default=float)+'\n')
    print(json.dumps({k: v for k, v in r.items() if k != 'burn_trim'} | dict(burn_trim={k: v for k, v in r['burn_trim'].items() if k != 'states'}),
                     indent=1, default=lambda x: round(x, 4)))
