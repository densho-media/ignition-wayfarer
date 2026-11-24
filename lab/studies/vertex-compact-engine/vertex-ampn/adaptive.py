#!/usr/bin/env python3
"""AMPN Phase 4: adaptive field and geometry states (research, not canon; standard library only).

States studied (owner AMPN brief section 5): concentrated propulsion, expanded braking shield, safe shutdown / stowed.
  * EM adjustments: current multiple (field strength) and, for E, the mirror coil share; what they change (eta, forward leakage, cant,
    heat) and how fast they can change (inductive energy, ramp time at a terminal voltage, AC ripple of a ramp).
  * Mechanical adjustments: the A+ L4 carriage idea (Vertex 1.8) applied to the RON ring; strokes, times, forces, locks.
  * Forces between the four engines' fields, transients, failure cases and recovery.
`python3 lab/studies/vertex-compact-engine/vertex-ampn/adaptive.py` writes results/adaptive.json and results/adaptive.log.
"""
import json
import math
import sys
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'vertex-ron')); sys.path.insert(0, str(HERE))
import ron  # noqa: E402
import optimize as O  # noqa: E402
import dust  # noqa: E402

MU0 = 4e-7 * math.pi
I_TURN = 20e3            # A per turn (REBCO cable class; PROTOTYPE)
V_TERM = (1.0, 100.0, 1e3, 1e4)   # terminal voltages: A+ dynamo 1 V, power supply 100 V-1 kV, quench-dump 10 kV


def ring_dipole(v, cap):
    c = next(c for c in v['coils'] if not c.get('shadowed'))
    I = abs(c['I']) * cap['k']
    R = ron.hoop_r(c)
    return I, R, I * math.pi * R * R


def mutual_force(m, S):
    """Axial force between two coaxial-parallel dipoles side by side at distance S (both moments along x, separation lateral):
    F = 3 mu0 m^2 / (4 pi S^4) (repulsive); the diagonal pair at S sqrt2 adds a smaller term."""
    f1 = 3 * MU0 * m * m / (4 * math.pi * S ** 4)
    f2 = 3 * MU0 * m * m / (4 * math.pi * (S * math.sqrt(2)) ** 4)
    return f1, f2


def em_scan(fam, x, k, pool, mults):
    rows = []
    for mlt in mults:
        xx = list(x); xx[4] = mlt
        r = O.evaluate(fam, xx, k, pool, n=160)
        if 'error' in r:
            continue
        rows.append(dict(mult=mlt, departure_t=r['departure_t'], engine_t=r['engine_t'], eta=r['eta'], forward_share=r['fwd'],
                         cant_deg=r['cant_deg'], field_ratio=r['field_ratio'], self_W=r['self_W']))
    return rows


def main():
    log = []
    def say(s=''):
        print(s, flush=True); log.append(s)
    k = ron.canon(); out = dict(designs={})
    cases = {'B_D800': ('B', [50.0, 2.0, 800.0, 400.0, 1.6]), 'E_S250': ('E', [50.0, 2.0, 800.0, 250.0, 2.5, 4.0])}
    with Pool(2) as pool:
        for name, (fam, x) in cases.items():
            p = O.design(fam, x)
            v, src, E, cap = ron.configure(p, k)
            r = ron.evaluate(v, k, src, E, cap, x[4], pool, 160)
            W = r['capture']['W_J']
            I, R, m = ring_dipole(v, r['capture'])
            N = I / I_TURN
            L = 2 * W / I_TURN ** 2
            res = dict(W_J=W, ring_current_A=I, ring_R_m=R, dipole_A_m2=m, turns=N, L_H=L)
            say(f'== {name}: stored field energy {W:.3e} J per engine ({W / E:.1f} x the 2.95 GJ pulse), ring {I / 1e6:.1f} MA-turns at R {R:.1f} m, '
                f'{N:.0f} turns of {I_TURN / 1e3:.0f} kA, L {L:.1f} H')
            # ramps
            res['ramps'] = []
            for Vt in V_TERM:
                t = L * I_TURN / Vt
                res['ramps'].append(dict(V=Vt, t_s=t, P_peak_W=Vt * I_TURN))
                say(f'  ramp 0 to full at {Vt:>7.0f} V: {t / 3600:8.2f} h, peak power {Vt * I_TURN / 1e6:.2f} MW')
            # ramp-rate AC loss relative to the 20 kHz ripple: dB/dt of a 1 h ramp vs the ripple's 2 pi f dB
            Bw = 4e-7 * math.pi * I / (2 * next(c for c in v['coils'] if not c.get('shadowed'))['depth'])
            ripple = O.EPS_C * E / (2 * W) * Bw * 2 * math.pi * 2e4
            ramp_1h = Bw / 3600
            res['ramp_dBdt_over_ripple_1h'] = ramp_1h / ripple
            say(f'  winding field {Bw:.2f} T; a 1 h ramp is {ramp_1h:.1e} T/s, {ramp_1h / ripple:.1e} of the 20 kHz ripple dB/dt (negligible)')
            # forces between engines
            f1, f2 = mutual_force(m, x[3])
            res['engine_pair_force_N'] = f1; res['diagonal_force_N'] = f2
            say(f'  field forces between engines at S {x[3]:.0f} m: neighbour {f1 / 1e3:.0f} kN, diagonal {f2 / 1e3:.0f} kN '
                f'({(2 * f1 + f2) / 5.44e6 * 100:.2f} % of one engine\'s thrust, pushing the four apart; static, carried by the boom frame)')
            # one engine quenched or ramped down while three stay up: the net lateral force on the survivors becomes asymmetric
            res['asymmetric_force_N'] = f1 + f2 / math.sqrt(2)
            # EM scan: what the field can trade quickly
            res['em_scan'] = em_scan(fam, x, k, pool, [1.0, 1.3, 1.6, 2.0, 2.5, 3.2] if fam == 'B' else [1.6, 2.0, 2.5, 3.2])
            say('  EM scan (current multiple):')
            for s in res['em_scan']:
                say(f'    x{s["mult"]:.1f}: eta {s["eta"]:.3f}, forward {s["forward_share"] * 100:.2f} %, cant {s["cant_deg"]:.1f}, field/pulse '
                    f'{s["field_ratio"]:.1f}, engine {s["engine_t"]:.0f} t, departure {s["departure_t"]:,.0f} t')
            # Mode B by field change: widen the plume = weaken the field. Dust (dust.py) shows no width gives protection.
            mb = dust.mode_b(dict(S=x[3], D=x[2], m_damage=2 * 2586 / dust.V ** 2))
            res['mode_b'] = [dict(theta_deg=r_['theta_deg'], shortfall=r_['shortfall'], axial_share=r_['thrust_axial_share']) for r_ in mb]
            # mechanical: L4-style carriage. Stroke to stow the ring onto the plug node (kappa R to plug): length and time at 1 cm/s
            stroke = (v['plug_x_m'] - next(c for c in v['coils'] if not c.get('shadowed'))['p0'][0])
            res['stow_stroke_m'] = stroke
            res['stow_time_s'] = stroke / 0.01
            # carriage mass: A+ bracket 9-37 t per engine for a 4.8 m stroke on the cage; RON ring is ~10x larger in hoop, so the
            # carriage is sized by ring mass: rails + drives + locks ~ 8 % of the moved mass (PROTOTYPE)
            moved = sum(val for kk, val in r['mass_t'].items() if kk.lower().startswith(('ring', 'cond', 'cryo', 'nose', 'coil')))
            res['moved_mass_t'] = moved
            res['carriage_t'] = 0.08 * moved + 9.0
            say(f'  stow stroke ring to plug node {stroke:.0f} m, {stroke / 0.01 / 3600:.1f} h at 1 cm/s; moved mass {moved:.0f} t, carriage ~{res["carriage_t"]:.0f} t')
            out['designs'][name] = res
    out['states'] = [
        dict(state='PROPULSION (concentrated)', field='full current, persistent', geometry='ring at kappa R, plug at (kappa+1) R, cant set',
             dust='bow-first faces armoured; stern screen idle', ship_orientation='bow first', change_from_prev='none'),
        dict(state='BRAKING (ship flipped)', field='same field: in the ship frame the engines still push toward the ship',
             geometry='unchanged', dust='ring and plug aft faces armoured; stern screen in the plug shadow takes the stern',
             ship_orientation='engines first', change_from_prev='300 s flip at cruise (field stays persistent; no ramp)'),
        dict(state='EXPANDED PLUME (Mode B as briefed)', field='reduced current (wider detachment) or mirror share changed',
             geometry='unchanged', dust='no protection: column 10^7 to 10^9 short (dust.py)', ship_orientation='engines first',
             change_from_prev='REJECTED: costs thrust, protects nothing'),
        dict(state='SAFE / STOWED', field='ramped down (or quenched into the dump)', geometry='ring carriage locked, petals closed',
             dust='armour stays', ship_orientation='any', change_from_prev='ramp 0.5-6 h at 1-10 kV; emergency dump 10 kV'),
    ]
    out['failures'] = [
        dict(case='one engine out (shutdown, field up)', effect='thrust 3/4, ship torque from the offset engine (balance by throttling the '
             'opposite engine or by cant)', dust='unchanged: passive protection does not depend on the exhaust'),
        dict(case='one engine quench', effect='stored energy into the dump in seconds; the three remaining rings feel an unbalanced '
             'mutual force (tens of kN, see log) on the boom frame; the dump heats to 1,500 K', dust='unchanged'),
        dict(case='low plasma / reduced thrust', effect='burn lengthens; eta falls with the field-to-pulse ratio only if the field is reduced',
             dust='unchanged'),
        dict(case='carriage stuck part-way', effect='ring off its kappa R: eta and forward leakage change; the cant criterion must be '
             're-run; locks hold the ring at any position (brake-type locks every metre)', dust='unchanged'),
        dict(case='stern screen torn', effect='a replacement roll on the mast (screen is 37-90 t; spares 10 %)', dust='stern exposed for the '
             'rest of the braking burn: expected breaches 6.8e4 x remaining share (NOMINAL)'),
    ]
    (HERE / 'results').mkdir(exist_ok=True)
    (HERE / 'results' / 'adaptive.json').write_text(json.dumps(out, indent=1, default=str))
    (HERE / 'results' / 'adaptive.log').write_text('\n'.join(log) + '\n')


if __name__ == '__main__':
    main()
