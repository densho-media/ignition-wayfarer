"""Feasibility gate Phase 1 (ISS-022): the axial plasma leak of the V4 closure nozzle (T00, research only, NON-CANON).

  python3 lab/variants/vertex-drive/studies/gate/axis.py        # writes results/axis.json (about 2 min)

Methods: T03's thin-shell model (analytical, vacuum field, flux-excluding shell) at 0.025 deg polar resolution, T05's first-hit kernel
(4c1a29b, 600k rays on the drawn V4 set), a 3D vacuum-field ray integration for non-axisymmetric fields and closed-form estimates.
No MHD, no PIC, no external computing (D-21 not requested).

Key physical statement, used to rank the concepts. Just outside the expanding plasma there is no current, so the tangential field on
the plasma surface is curl-free on that surface (its normal curl is mu0 J_n = 0) and the surface is a topological sphere. So
B_t = grad_s(Phi) of a single-valued surface potential, and a smooth function on a sphere has at least a maximum and a minimum:
B_t has at least two zeros on any closed flux-excluding surface, whatever coils produce the field (Morse, Poincare-Hopf). There the
magnetic pressure vanishes and the shell is not stopped. In an axisymmetric nozzle the zeros are the two poles: the aft one is the
exhaust, the forward one is ISS-022. No field topology removes the forward leak; a field can only move it or narrow it.
"""
import math

import numpy as np

import gate_common as G
import shell

N_TH = 7201            # 0.025 deg polar bins
N_RHO = 1400
TUBE_V4 = 0.75         # ASSUMPTION: T03's 0.5 m strike tube at V1 scaled by the stand-off ratio
ANISO = {               # angular plasma-energy profiles g(th), normalised to a mean of 1 over 4 pi (forward = +z = toward the shield)
    'isotropic': lambda c: np.ones_like(c),
    'P2 +0.25 (prolate, polar-heavy)': lambda c: 1 + 0.25 * (1.5 * c * c - 0.5),
    'P2 +0.5 (prolate, polar-heavy)': lambda c: 1 + 0.5 * (1.5 * c * c - 0.5),
    'P2 -0.25 (oblate, equator-heavy)': lambda c: 1 - 0.25 * (1.5 * c * c - 0.5),
    'P1 +0.2 (forward-heavy, target side)': lambda c: 1 + 0.2 * c,
    'P1 -0.2 (aft-heavy)': lambda c: 1 - 0.2 * c,
    'forward jet x2 within 10 deg': None,
    'forward jet x5 within 10 deg': None,
}


def jet(th, amp, sig_deg=10.0):
    g = 1 + amp * np.exp(-0.5 * (np.degrees(th) / sig_deg) ** 2)
    return g / np.sum(G.shell_weights(th) * g)


def profile(name, th):
    if name.startswith('forward jet'):
        return jet(th, 1.0 if 'x2' in name else 4.0)
    g = ANISO[name](np.cos(th))
    return g / np.sum(G.shell_weights(th) * g)


def stop_profile(T, E_sr):
    """R(th) for a per-ray energy array E_sr (NaN where unstopped inside rmax)."""
    R = np.full(len(T.th), np.nan)
    for j in range(len(T.th)):
        i = np.searchsorted(T.work[:, j], E_sr[j])
        if 0 < i < len(T.rho):
            f = (E_sr[j] - T.work[i - 1, j]) / (T.work[i, j] - T.work[i - 1, j])
            R[j] = T.rho[i - 1] + f * (T.rho[i] - T.rho[i - 1])
    return R


def leak(T, g, v, scale_I=1.0):
    """Shell elements that reach the shield plane inside the shield radius before stopping."""
    th = T.th; w = G.shell_weights(th)
    E_sr = v['E_plasma_J'] * g / (4 * math.pi) / scale_I ** 2
    R = stop_profile(T, E_sr)
    zs, rs = v['shield_z_m'], v['shield_r_m']
    th_sh = math.atan(rs / zs)
    path = zs / np.cos(th)
    reach = (th < th_sh) & (~np.isfinite(R) | (R > path))
    Ef = float(np.sum(w * g * reach)) * v['E_plasma_J']
    th_u = float(np.degrees(th[reach].max())) if reach.any() else 0.0
    # half-angle where the shell is not stopped before 0.9 of the shield distance (a margin for shell thickness and spread)
    near = (th < th_sh) & (~np.isfinite(R) | (R > 0.9 * path))
    return {'R': R, 'reach': reach, 'leak_share_of_plasma': float(np.sum(w * g * reach)), 'leak_J_per_pulse': Ef,
            'leak_W': Ef * v['rate_Hz'], 'leak_half_angle_deg': th_u,
            'half_angle_within_0.9_of_shield_deg': float(np.degrees(th[near].max())) if near.any() else 0.0,
            'centre_fluence_J_cm2': float(v['E_plasma_J'] * g[0] / (4 * math.pi) / (zs * 100) ** 2),
            'shield_angular_radius_deg': math.degrees(th_sh)}


def kernel_exposure(T, R, g, v):
    """Energy per pulse on each part category: T05 first-hit fractions folded with the unstopped plasma per steradian."""
    k = G.json.loads(G.KERNEL.read_text())['kernel']['bins']
    th = np.degrees(T.th); w = G.shell_weights(T.th)
    out = {}
    for b in k:
        t0, t1 = b['polar_deg']
        sel = (th >= t0) & (th < t1)
        if not sel.any():
            continue
        for cat, frac in b['first_hit_fraction'].items():
            d = b['mean_hit_distance_m'].get(cat)
            if d is None:
                continue
            un = sel & (~np.isfinite(R) | (R > d))
            e = frac * float(np.sum(w[un] * g[un])) * v['E_plasma_J']
            if e <= 0:
                continue
            o = out.setdefault(cat, {'J_per_pulse': 0.0, 'polar_deg': [t0, t1], 'distance_m': d, 'peak_J_cm2': 0.0})
            o['J_per_pulse'] += e
            o['polar_deg'] = [min(o['polar_deg'][0], t0), max(o['polar_deg'][1], t1)]
            o['peak_J_cm2'] = max(o['peak_J_cm2'], float(np.max(g[un])) * v['E_plasma_J'] / (4 * math.pi) / (d * 100) ** 2)
    for o in out.values():
        o['W'] = o['J_per_pulse'] * v['rate_Hz']
        o['MW_m2_peak'] = o['peak_J_cm2'] * 1e4 * v['rate_Hz'] / 1e6
    return dict(sorted(out.items(), key=lambda x: -x[1]['J_per_pulse']))


def hardware(v):
    hw = [{'kind': 'loop', 'name': L['name'], 'R': L['R'], 'z': L['z'], 'tube': max(TUBE_V4, L['a'] + 0.3)} for L in v['loops']]
    hw.append({'kind': 'disc', 'name': 'shield', 'z': v['shield_z_m'], 'R': v['shield_r_m']})
    return hw


# ---------------------------------------------------------------------------------------------------------------------------- surfaces
def surface_damage(F_J_cm2, rate, tau_s=3e-6):
    """What a solid or liquid face can take: the heat-flux factor F/sqrt(tau) against melt limits, and the ablation if it all vaporises.
    tau: arrival spread of the shell at about 65 m (thickness and velocity spread, ASSUMPTION 1-10 us; 3 us nominal)."""
    q = F_J_cm2 * 1e4
    mats = {'W': (19300.0, 4.8e6 + 134 * 3400, 50.0), 'C (CFC)': (1850.0, 59e6, 60.0), 'Li (liquid surface)': (480.0, 19.6e6 + 4200 * 800, None)}
    out = {'fluence_J_cm2': F_J_cm2, 'heat_flux_factor_MJ_m2_s05': q / math.sqrt(tau_s) / 1e6, 'average_MW_m2': q * rate / 1e6, 'materials': {}}
    for m, (rho, h, hff) in mats.items():
        ab = q / (rho * h)
        out['materials'][m] = {'melt_or_crack_limit_MJ_m2_s05': hff, 'over_limit_x': (q / math.sqrt(tau_s) / 1e6 / hff) if hff else None,
                               'ablation_um_per_pulse_if_all_vaporises': ab * 1e6, 'mm_per_hour_at_rate': ab * rate * 3600 * 1e3,
                               'mm_per_hour_with_99pc_vapour_shielding': ab * rate * 3600 * 1e3 * 0.01}
    return out


def required_reduction(v):
    """Fluence a permanent face can take for the mission's pulses: below the crack/melt limits with margin (W, CFC about 10 MJ m-2 s-0.5
    for 1e9+ pulses, ITER ELM experience; ASSUMPTION) and an average below 10 MW/m2 (actively cooled divertor class)."""
    tau = 3e-6
    F_hff = 10e6 * math.sqrt(tau) / 1e4
    F_avg = 10e6 / v['rate_Hz'] / 1e4
    return {'pulses_in_mission': v['rate_Hz'] * 5.685 * G.YEAR, 'fluence_limit_from_fatigue_J_cm2': F_hff,
            'fluence_limit_from_average_10MW_m2_J_cm2': F_avg, 'limit_J_cm2': min(F_hff, F_avg)}


def main():
    v = G.v4()
    T = shell.WorkTable(v['loops'], n_th=N_TH, n_rho=N_RHO)
    out = {'study': 'Feasibility gate Phase 1: ISS-022 axial plasma leak (T00)', 'status': 'MODEL, research only, NON-CANON',
           'methods': 'T03 thin shell at 0.025 deg; T05 first-hit kernel 4c1a29b; 3D vacuum-field ray work; closed-form estimates. No MHD/PIC.',
           'v4': {'E_plasma_J': v['E_plasma_J'], 'rate_Hz': v['rate_Hz'], 'shield_z_m': v['shield_z_m'], 'shield_r_m': v['shield_r_m'],
                  'scale_from_V1': v['scale'], 'current_factor': v['current_factor'],
                  'loops': [{k: L[k] for k in ('name', 'R', 'z', 'I', 'a')} for L in v['loops']]}}
    # 1. baseline, fine angle
    th = T.th; g0 = np.ones_like(th)
    b = leak(T, g0, v)
    T181 = shell.WorkTable(v['loops'], n_th=181, n_rho=N_RHO)              # T03's resolution for the reflection ledger
    o = shell.reflect(T181, 1.0, v['E_plasma_J'], hardware(v))
    sens = {}
    for n in (181, 721, 2881):
        Tn = T181 if n == 181 else shell.WorkTable(v['loops'], n_th=n, n_rho=N_RHO)
        on = shell.reflect(Tn, 1.0, v['E_plasma_J'], hardware(v))
        thn = np.degrees(Tn.th); sf = np.array([h == 'ship_forward' for h in on['hit']])
        sens[str(n)] = {'strike_by_share': on['strike_by'], 'eta_mom': on['eta_mom'],
                        'ship_forward_from_aft_hemisphere': float(np.sum(on['w'][sf & (thn > 90)]))}
    out['baseline'] = {k: b[k] for k in b if k not in ('R', 'reach')}
    out['baseline']['stopping_radius_m'] = {f'{t:g}': (None if not np.isfinite(r) else round(float(r), 2))
                                            for t, r in zip(np.degrees(th), b['R']) if t <= 30.0 and abs((t * 4) % 2) < 1e-6}
    out['baseline']['reflect'] = {'strike_by_share': o['strike_by'], 'strike_W': {k: s * v['E_plasma_J'] * v['rate_Hz'] for k, s in o['strike_by'].items()},
                                  'unstopped_forward_share': o['unstopped_forward_share'], 'eta_mom': o['eta_mom'], 'n_th': 181,
                                  'resolution_sensitivity': sens,
                                  'note': 'the specular-reflection ledger is resolution-sensitive: at 0.25 deg and finer about 5-6 % of the plasma '
                                          'is reflected forward from kinks of the aft stopping surface near L2 and L3 (1.2 % at 1 deg). The '
                                          'stopping-based axial leak is not sensitive. New issue for the D-21 nozzle-efficiency question.'}
    out['baseline']['exposure_by_part'] = kernel_exposure(T, b['R'], g0, v)
    out['baseline']['shield_centre_surface'] = surface_damage(b['centre_fluence_J_cm2'], v['rate_Hz'])
    out['baseline']['booked'] = {
        'fdp1_plume_to_hardware_W': v['R']['fusion']['ledger_W']['plume_to_hardware'],
        'note': 'FDP-1 books plume_to_hardware as one aggregate heat (a share of the plume, PROTOTYPE) with no location; the shield-face '
                'leak fits inside it as heat, but nothing in V4 books its surface fluence, erosion or the parts inside the channel.'}
    out['requirement'] = required_reduction(v)
    # 2. sensitivity to the angular plasma distribution
    out['anisotropy'] = {}
    for name in ANISO:
        g = profile(name, th)
        r = leak(T, g, v)
        out['anisotropy'][name] = {k: r[k] for k in ('leak_share_of_plasma', 'leak_W', 'leak_half_angle_deg', 'centre_fluence_J_cm2')}
    # 3. sensitivity to the closing field (current scale: B^2 ~ I^2)
    out['current_scale'] = {}
    for sI in (0.8, 1.0, 1.25, 1.5, 2.0, 3.0):
        r = leak(T, g0, v, sI)
        out['current_scale'][f'{sI:g}'] = {'stored_energy_x': sI ** 2, 'leak_share_of_plasma': r['leak_share_of_plasma'],
                                           'leak_half_angle_deg': r['leak_half_angle_deg']}
    print('baseline', {k: out['baseline'][k] for k in ('leak_share_of_plasma', 'leak_W', 'leak_half_angle_deg', 'centre_fluence_J_cm2')})
    for k, x in out['baseline']['exposure_by_part'].items():
        print(f'  {k:28s} {x["J_per_pulse"] / 1e6:9.2f} MJ/pulse {x["W"] / 1e9:7.2f} GW {x["peak_J_cm2"]:7.1f} J/cm2 at {x["distance_m"]:.0f} m {x["polar_deg"]}')
    for k, x in out['anisotropy'].items():
        print(f'  {k:40s} leak {x["leak_share_of_plasma"]:.5f} {x["leak_W"] / 1e9:6.1f} GW half-angle {x["leak_half_angle_deg"]:.2f}')
    print('current scale', {k: (round(x['leak_share_of_plasma'], 5), round(x['leak_half_angle_deg'], 2)) for k, x in out['current_scale'].items()})
    G.write('axis_base.json', out)
    return out


if __name__ == '__main__':
    main()
