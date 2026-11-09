"""T03 driver: builds configurations A-D on the V1 nozzle, runs the thin-shell, perturbation, test-particle, coil and ledger
analyses, and writes results/nozzle_results.json and results/field_lines.json (ILLUSTRATIVE overlay data for T05).
Run from the repo root: python3 lab/variants/vertex-drive/studies/nozzle/run_nozzle.py   (about 4 min on 4 cores)
The calculator re-runs are separate: calc_rerun.py (about 3 min)."""
import json
import math
import sys
import time
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import configs as C      # noqa: E402
import fields as F       # noqa: E402
import optimise as O     # noqa: E402
import particles as PA   # noqa: E402
import perturb as PT     # noqa: E402
import pulse             # noqa: E402
import shell             # noqa: E402

warnings.filterwarnings('ignore')
RATIOS = (3.0, 6.0, 10.0, 15.0, 20.0, 30.0)
TUBE_M = 0.5            # ASSUMPTION: plasma must stay this far from a coil centre-line (envelope + armour) or it counts as a strike
FORWARD_COILS_DEG = (20.0, 40.0)


def loops_json(L):
    return [{'name': q['name'], 'polar_deg': q['alpha_deg'], 'distance_m': q['d'], 'radius_m': q['R'], 'z_m': q['z'],
             'current_MA': q['I'] / 1e6, 'winding_minor_m': q['a']} for q in L]


def summarise(o):
    keep = ('eta_mom', 'eta_T', 'strike_share', 'strike_by', 'unstopped_forward_share', 'forward_going_share', 'min_R_fwd')
    out = {k: o[k] for k in keep}
    R = o['R']; th = np.degrees(np.linspace(0, math.pi, len(R)))
    out['stopping_radius_m_by_polar_deg'] = {f'{t:.0f}': (None if not np.isfinite(r) else round(float(r), 2)) for t, r in zip(th, R)
                                             if abs(t % 10) < 1e-6 or abs(t % 10 - 10) < 1e-6}
    return out


def stresses(L):
    """Hoop tension and net (radial, axial) force on each loop from the others (N)."""
    out = []
    for i, a in enumerate(L):
        others = [b for j, b in enumerate(L) if j != i]
        Br, Bz = F.loops_field(others, a['R'], a['z'])
        f_r = a['I'] * float(Bz) * 2 * math.pi * a['R']; f_z = -a['I'] * float(Br) * 2 * math.pi * a['R']
        out.append({'loop': a['name'], 'hoop_tension_self_MN': F.hoop_tension(a['R'], a['a'], a['I']) / 1e6,
                    'net_radial_from_others_MN': f_r / 1e6, 'net_axial_from_others_MN': f_z / 1e6,
                    'solid_angle_share_envelope_x3': math.sin(math.radians(a['alpha_deg'])) * 3 * a['a'] / a['d']})
    return out


def ac_screen(L, E_p, rep, W):
    """Pulsed-field load on the windings (EXTRAPOLATION, factor-10 band): flux-conserving coils see a current swing
    dI/I ~ E_p/(2W) each pulse. Unscreened REBCO hysteresis (Bean, full penetration, perpendicular field):
    q = B_amp * Jc_layer * w * f_sc per cycle and m3 of winding. A warm eddy-current screen with time constant tau carries the
    transient instead and dissipates ~ (t_pulse/tau) of the transient energy."""
    dI = E_p / (2 * W)
    Jc, w, fsc = 1e10, 4e-3, 0.01                     # ASSUMPTION: REBCO layer Jc at ~20 K and ~20 T; 4 mm tape; 1 % superconductor
    vol = sum(2 * math.pi * q['R'] * math.pi * q['a'] ** 2 for q in L)
    Bamp = 0.5 * dI * C.B_LIMIT_T
    q_cycle = Bamp * Jc * w * fsc
    t_pulse = 4e-6; tau = 2e-3                        # ASSUMPTION: reflection time ~ 2 R / v; Cu screen 5 cm on 0.5 m (tau ~ 2 ms)
    return {'current_swing_per_pulse': dI, 'winding_volume_m3': vol, 'B_swing_amplitude_T': Bamp,
            'unscreened_hysteresis_W': q_cycle * vol * rep, 'screen_dissipation_share_of_plasma': (t_pulse / tau) * 0.5,
            'screen_dissipation_W': (t_pulse / tau) * 0.5 * E_p * rep}


def rt_estimate(R_stop, v, rL):
    """Rayleigh-Taylor e-folds of the decelerating then re-accelerated shell: N = sqrt(2 l Delta/R) per phase with stopping depth
    Delta ~ R/3, two phases, FLR cut-off l_max ~ R / r_L. Tension stabilises modes with k within 45 deg of B: gamma^2 = g k (1 - 2 sin^2 psi)."""
    Delta = R_stop / 3
    lmax = R_stop / rL
    N = lambda l: 2 * math.sqrt(2 * l * Delta / R_stop)
    return {'stopping_depth_m': Delta, 'l_max_FLR': lmax, 'efolds_l10': N(10), 'efolds_l_max': N(lmax), 'growth_l_max': math.exp(N(lmax)),
            'shear_needed_deg': 45.0, 'wavelength_at_l_max_m': 2 * math.pi * R_stop / lmax}


def field_lines(L, seeds, step=0.5, n=3000, box=(0, 260, -320, 80)):
    """Field lines in the (r, z) half-plane by RK2 along the unit field direction (ILLUSTRATIVE overlay data)."""
    lines = []
    for r0, z0 in seeds:
        for sgn in (1, -1):
            pts = [(r0, z0)]; r, z = r0, z0
            for _ in range(n):
                br, bz = F.loops_field(L, r, z); b = math.hypot(float(br), float(bz)) or 1e-30
                rm, zm = r + 0.5 * sgn * step * float(br) / b, z + 0.5 * sgn * step * float(bz) / b
                br, bz = F.loops_field(L, max(rm, 0.0), zm); b = math.hypot(float(br), float(bz)) or 1e-30
                r, z = r + sgn * step * float(br) / b, z + sgn * step * float(bz) / b
                if r < 0 or not (box[0] <= r <= box[1] and box[2] <= z <= box[3]):
                    break
                if any(math.hypot(r - q['R'], z - q['z']) < q['a'] for q in L):
                    break
                pts.append((round(r, 2), round(z, 2)))
            lines.append(pts[::4] if sgn == 1 else pts[::-4])
    return lines


def main():
    t0 = time.time()
    p = pulse.v1(); Ep = p['E_plasma_J']
    hw_main = shell.hardware_set(p, TUBE_M)
    fw = C.place(p, FORWARD_COILS_DEG, 'sphere')
    hw_C = hw_main + [{'kind': 'loop', 'name': q['name'], 'R': q['R'], 'z': q['z'], 'tube': TUBE_M} for q in fw]
    res = {'pulse': {k: p[k] for k in ('generation', 'E_pulse_J', 'E_plasma_J', 'mass_per_pulse_kg', 'v_rms_m_s', 'rep_Hz', 'R_s_m',
                                       'focal_m', 'shield_z_m', 'shield_radius_m', 'thrust_N')},
           'assumptions': {'B_limit_T': C.B_LIMIT_T, 'J_eng_A_m2': C.J_ENG_A_M2, 'virial_kg_per_J': 1 / C.SIGMA_OVER_RHO,
                           'strike_tube_m': TUBE_M, 'forward_coils_polar_deg': FORWARD_COILS_DEG}, 'designs': {}}
    designs = {}
    # A: FDP-1 three loops, equal currents (FDP-1 gives every loop the same conductor), scaled to each energy ratio
    for k in RATIOS:
        L = O.scaled(p['loops'], [1, 1, 1], k * Ep, Ep)
        designs[f'A_equal_W{k:g}'] = ('A', L, hw_main)
    # A*: three loops, current pattern optimised; C: plus two forward closure coils on the stand-off sphere, optimised
    for k in RATIOS:
        _, L, _ = O.best_pattern(p['loops'], k, Ep, hw_main, iters=80)
        designs[f'Astar_W{k:g}'] = ('A*', L, hw_main)
        _, L, _ = O.best_pattern(fw + p['loops'], k, Ep, hw_C, x0=[3, 1, 1, 1, 1], iters=150)
        designs[f'C_W{k:g}'] = ('C', L, hw_C)
    for name, (kind, L, hw) in designs.items():
        T = shell.WorkTable(L, n_th=181, n_rho=700)
        o = shell.reflect(T, 1.0, Ep, hw)
        lg = C.ledger(L, Ep)
        rec = {'kind': kind, 'loops': loops_json(L), 'ledger': lg, 'thin_shell': summarise(o), 'stresses': stresses(L),
               'axis': PA.mirror_axis(L), 'ac_screen': ac_screen(L, Ep, p['rep_Hz'], lg['stored_J'])}
        Rf = o['min_R_fwd'] or float('nan')
        rL = PA.SPECIES['He4'][0] * PA.U * p['v_rms_m_s'] / (2 * PA.QE * max(rec['axis']['B_burn_T'], 1e-6) * 1.5)
        rec['rt'] = rt_estimate(Rf, p['v_rms_m_s'], rL)
        res['designs'][name] = rec
        designs[name] = (kind, L, hw, T, o)
        print(f"{name:12s} eta_mom {o['eta_mom']:.3f} eta_T {o['eta_T']:.3f} strike {o['strike_share']:.4f} W/Ep {lg['W_over_Ep']:.1f} "
              f"mass {lg['virial_mass_t']:.0f} t  [{time.time()-t0:.0f} s]", flush=True)
    # B, D, C3D: 3D perturbations on the C design at W/Ep = 10 and on A* at 10
    pert = {}
    for base in ('C_W10', 'Astar_W10'):
        kind, L, hw, T, o = designs[base]
        main = [q for q in L if q['name'].startswith('L')]
        cases = {}
        for label, clocks, eps in (('B gaps only, clocked 0/45/90', (0, 45, 90), 0.0), ('B gaps + 5 % m=2 trim, clocked', (0, 45, 90), 0.05),
                                   ('B gaps + 20 % m=2 trim, clocked', (0, 45, 90), 0.2), ('D counter-clocked 0/45/0, 5 % trim', (0, 45, 0), 0.05),
                                   ('D counter-clocked 0/45/0, 20 % trim', (0, 45, 0), 0.2)):
            paths = []
            for q, c in zip(main, clocks):
                paths += PT.sector_paths(q, c, eps=eps)
            cases[label] = paths
        for Ih in (2e6, 5e6, 20e6):
            cases[f'C3D helix l=2, 90 deg twist, {Ih/1e6:g} MA'] = PT.helical_paths(p, Ih, 90.0)
            cases[f'D helix balanced, 90 deg twist, {Ih/1e6:g} MA'] = PT.helical_paths(p, Ih, 90.0, balanced=True)
        pert[base] = {}
        for label, paths in cases.items():
            r = PT.surface_effect(p, L, T, o['R'], paths, Ep, n_phi=48, hardware=hw, base=o)
            pert[base][label] = r
            print(f"  {base} {label:45s} eta {r['eta_mom_total']:.3f} shear {r['shear_max_deg']:.2f} deg torque {r['roll_torque_Nm']:.3g} N m",
                  flush=True)
    res['perturbations'] = pert
    # test particles in the vacuum field (low-beta tail) for A equal and C at W/Ep 10
    tp = {}
    for base in ('A_equal_W10', 'C_W10'):
        L = designs[base][1]
        tp[base] = {sp: PA.run(p, L, sp, n=400, dt_frac=0.08) for sp in ('p', 'D', 'He4')}
        tp[base]['slow_tail_He4_0.1v'] = PA.run(p, L, 'He4', n=300, speed=0.1 * p['v_rms_m_s'], dt_frac=0.08)
        print(f"  particles {base}: {tp[base]['He4']['fate_share']}", flush=True)
    res['test_particles'] = tp
    # recovery requirement (MODEL, V1 ledger): electric load / recovery efficiency, as share of fusion and of the plasma stream
    L_ = p['ledger_share']
    P_e = L_['driver_loss'] + 1 / 3000.0 + L_['electric_house'] + L_['cryo_input']
    res['recovery'] = {'electric_load_share_fusion': P_e, 'required_extraction_share_fusion_eta_r_0.95': P_e / 0.95,
                       'required_extraction_share_fusion_eta_r_0.80': P_e / 0.80,
                       'driver_eff_0.30_eta_r_0.80': (1 / (3000 * 0.30) + L_['electric_house']) / 0.80,
                       'stream_share_fusion': p['stream_share']}
    # field lines for the T05 overlay (ILLUSTRATIVE)
    seeds = [(r, 0.0) for r in (2, 6, 10, 15, 20, 30, 45, 55)] + [(r, -100.0) for r in (80, 100)]
    res_lines = {name: {'loops': loops_json(designs[name][1]), 'lines_rz_m': field_lines(designs[name][1], seeds),
                        'stopping_surface_rz_m': [(round(float(R * math.sin(t)), 2), round(float(R * math.cos(t)), 2))
                                                  for R, t in zip(designs[name][4]['R'], designs[name][3].th) if np.isfinite(R)]}
                 for name in ('A_equal_W10', 'Astar_W10', 'C_W10')}
    res['runtime_s'] = round(time.time() - t0, 1)
    (HERE / 'results/nozzle_results.json').write_text(json.dumps(res, indent=1, default=float))
    (HERE / 'results/field_lines.json').write_text(json.dumps({'status': 'ILLUSTRATIVE', 'frame': 'nozzle frame: origin burn point, '
                                                               '+z = ship +X (bow); ship x = x_burn + z, x_burn = shield aft face - R_s',
                                                               'designs': res_lines}, default=float))
    print('done', res['runtime_s'], 's')


if __name__ == '__main__':
    main()
