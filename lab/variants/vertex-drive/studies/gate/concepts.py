"""Feasibility gate Phase 1 (ISS-022): concepts against the axial plasma leak (T00, research only, NON-CANON).

  python3 lab/variants/vertex-drive/studies/gate/concepts.py     # needs results/axis_base.json; writes results/concepts.json (minutes)

Concepts, each with its costs, and each judged against what it must achieve (results/axis_base.json 'requirement'):
  E  axisymmetric field shaping (stronger closing field, a shadowed coil behind the shield): narrows the leak, cannot remove it
  A1 tilt the forward closure coils C1 and C2 together: moves the forward field zero off the axis, conductor unchanged
  A2 a transverse plug coil behind the shield, in its X-ray shadow: moves the zero sideways
  B  a forward cap on the target (momentum sharing): cuts the forward energy per steradian; it sits in the driver-beam path
  C  splayed twin nozzles: each forward channel passes beside the ship
  D  relocation of hardware out of the channel; the shield face cannot be relocated
  S  a sacrificial or renewable shield-centre insert
3D method: the stopping radius on each ray (th, phi) from the work against k^2 B_t^2/2mu0 of the summed vacuum field (k = flux-exclusion
factor, calibrated to T03's exact axisymmetric solution on the same coils). It is a vacuum-field estimate, not a plasma solution.
"""
import math
import time

import numpy as np

import axis as AX
import gate_common as G
import shell

TH_FINE = np.arange(0.0, 25.0001, 0.1)     # deg
PHI = np.arange(0.0, 360.0, 5.0)           # deg


def rays(ths, phis):
    t, p = np.meshgrid(np.radians(ths), np.radians(phis), indexing='ij')
    return np.stack([np.sin(t) * np.cos(p), np.sin(t) * np.sin(p), np.cos(t)], axis=-1)


def stop_map(field, v, ths, phis, k, rho_max=None, n_rho=400, E_scale=None):
    """R[th, phi] (NaN: not stopped by rho_max) for the vacuum field `field(P)`; also the residual energy fraction at rho_max."""
    rho_max = rho_max or 1.3 * v['shield_z_m']
    rho = np.linspace(rho_max / n_rho, rho_max, n_rho)
    N = rays(ths, phis).reshape(-1, 3)
    E_sr = v['E_plasma_J'] / (4 * math.pi) * (E_scale if E_scale is not None else np.ones(len(N)))
    R = np.full(len(N), np.nan)
    for c0 in range(0, len(N), 64):
        n = N[c0:c0 + 64]
        P = (rho[None, :, None] * n[:, None, :]).reshape(-1, 3)
        B = field(P).reshape(len(n), len(rho), 3)
        Bn = np.einsum('ijk,ik->ij', B, n)
        Bt2 = np.maximum(np.sum(B * B, axis=2) - Bn ** 2, 0.0)
        f = k * k * Bt2 / (2 * G.MU0) * rho[None, :] ** 2
        W = np.concatenate([np.zeros((len(n), 1)), np.cumsum(0.5 * (f[:, 1:] + f[:, :-1]) * np.diff(rho)[None, :], axis=1)], axis=1)
        for i in range(len(n)):
            e = E_sr[c0 + i]
            m = np.searchsorted(W[i], e)
            if 0 < m < len(rho):
                R[c0 + i] = rho[m - 1] + (e - W[i, m - 1]) / (W[i, m] - W[i, m - 1]) * (rho[m] - rho[m - 1])
    return R.reshape(len(ths), len(phis))


def destination(R, v, ths, phis, g=None):
    """Where the unstopped shell goes: the shield face (inside its angular radius) or, outside it, the parts in T05's kernel
    (azimuth-averaged: the kernel has no azimuth) or space."""
    zs, rs = v['shield_z_m'], v['shield_r_m']
    th = np.radians(ths); dth = np.gradient(th); dphi = math.radians(phis[1] - phis[0])
    dOm = (np.sin(th) * dth)[:, None] * dphi * np.ones((1, len(phis)))
    if th[0] == 0.0:
        dOm[0, :] = math.pi * (dth[0] / 2) ** 2 / len(phis)
    g = np.ones_like(R) if g is None else g
    inside = (th < math.atan(rs / zs))[:, None]
    path = (zs / np.cos(th))[:, None]
    shield = inside & (~np.isfinite(R) | (R > path))
    K = G.json.loads(G.KERNEL.read_text())['kernel']['bins']
    parts = {}
    escape = 0.0
    for i, t in enumerate(ths):
        if inside[i, 0]:
            continue
        b = next((x for x in K if x['polar_deg'][0] <= t < x['polar_deg'][1]), None)
        un = ~np.isfinite(R[i])
        if b is None:
            escape += float(np.sum((dOm[i] * g[i])[un])); continue
        hit = 0.0
        for cat, fr in b['first_hit_fraction'].items():
            d = b['mean_hit_distance_m'].get(cat)
            if cat == 'NO_HIT' or d is None:
                continue                                  # rays that meet no T05 part: counted below as escape if unstopped
            e = fr * float(np.sum((dOm[i] * g[i])[~np.isfinite(R[i]) | (R[i] > d)]))
            parts[cat] = parts.get(cat, 0.0) + e; hit += fr
        escape += (1 - hit) * float(np.sum((dOm[i] * g[i])[un]))
    to = lambda om: om / (4 * math.pi)
    peak = None
    if shield.any():
        peak = float(np.max(np.where(shield, g, 0.0))) * v['E_plasma_J'] / (4 * math.pi) / (zs * 100) ** 2
    return {'shield_share': to(float(np.sum(dOm * g * shield))), 'shield_peak_J_cm2': peak,
            'parts_share': {k: to(x) for k, x in parts.items()}, 'escape_share_within_grid': to(escape),
            'shield_spot_deg': (float(ths[np.any(shield, axis=1)].max()) if shield.any() else 0.0)}


def null(field, v, d, k, th_max=30.0):
    best = (1e30, 0.0, 0.0)
    for t in np.arange(0.0, th_max, 0.1):
        for p in np.arange(0.0, 360.0, 5.0):
            n = np.array([[math.sin(math.radians(t)) * math.cos(math.radians(p)), math.sin(math.radians(t)) * math.sin(math.radians(p)),
                           math.cos(math.radians(t))]])
            B = field(d * n)[0]
            bt = math.sqrt(max(float(B @ B - (B @ n[0]) ** 2), 0.0))
            if bt < best[0]:
                best = (bt, t, p)
            if t == 0.0:
                break
    return {'polar_deg': best[1], 'azimuth_deg': best[2], 'Bt_T': best[0] * k, 'sphere_m': d}


def momentum(field, v, k, dth=1.0, dphi=10.0):
    """Full-sphere specular-reflection momentum (thin shell): axial efficiency and side share, for the side-thrust cost of a
    non-axisymmetric closure. Hardware strikes are ignored here (they are in T03's axisymmetric ledger)."""
    ths = np.arange(dth / 2, 180.0, dth); phis = np.arange(0.0, 360.0, dphi)
    R = stop_map(field, v, ths, phis, k, rho_max=1.25 * 194.1 * 1.0, n_rho=500)
    t = np.radians(ths)[:, None]; p = np.radians(phis)[None, :]
    rh = np.stack(np.broadcast_arrays(np.sin(t) * np.cos(p), np.sin(t) * np.sin(p), np.cos(t)), axis=-1)
    th_h = np.stack(np.broadcast_arrays(np.cos(t) * np.cos(p), np.cos(t) * np.sin(p), -np.sin(t)), axis=-1)
    ph_h = np.stack(np.broadcast_arrays(-np.sin(p), np.cos(p), 0 * t), axis=-1)
    Rf = np.where(np.isfinite(R), R, np.nan)
    dRt = np.gradient(Rf, np.radians(dth), axis=0)
    dRp = (np.roll(Rf, -1, axis=1) - np.roll(Rf, 1, axis=1)) / (2 * np.radians(dphi))
    nrm = rh - (dRt / Rf)[..., None] * th_h - (dRp / (Rf * np.sin(t)))[..., None] * ph_h
    ok = np.all(np.isfinite(nrm), axis=-1)
    nrm = np.where(ok[..., None], nrm, rh)
    nrm /= np.linalg.norm(nrm, axis=-1)[..., None]
    outd = np.where(ok[..., None], rh - 2 * np.sum(rh * nrm, axis=-1)[..., None] * nrm, rh)
    w = (np.sin(t) * np.radians(dth) * np.radians(dphi)) * np.ones_like(p) / (4 * math.pi)
    Pm = np.sum(w[..., None] * outd, axis=(0, 1))
    return {'thrust_axis_share': float(-Pm[2]), 'side_share_x': float(-Pm[0]), 'side_share_y': float(-Pm[1]),
            'side_over_axial': float(math.hypot(Pm[0], Pm[1]) / max(-Pm[2], 1e-12)),
            'thrust_line_tilt_deg': math.degrees(math.atan2(math.hypot(Pm[0], Pm[1]), -Pm[2]))}


def calibrate(v, base_leak):
    """Flux-exclusion factor k for the 3D vacuum method that reproduces T03's exact leak half-angle and share on the V4 coils."""
    f = lambda P: G.F.loops_cart(v['loops'], P)
    ths = np.arange(0.0, 8.0001, 0.05); phis = np.array([0.0, 180.0])
    rows = []
    for k in (1.2, 1.35, 1.5, 1.65, 1.8):
        R = stop_map(f, v, ths, phis, k)
        d = destination(R, v, ths, phis)
        rows.append({'k': k, 'shield_share': d['shield_share'], 'spot_deg': d['shield_spot_deg']})
    ks = np.array([r['k'] for r in rows]); sh = np.array([r['shield_share'] for r in rows])
    k_fit = float(np.interp(base_leak, sh[::-1], ks[::-1]))
    return k_fit, rows


# ------------------------------------------------------------------------------------------------------------------------ concepts
def concept_E(v, T_base):
    """A shadowed axisymmetric coil just behind the shield (same sense as C1), current scan: narrower leak, same centre fluence."""
    rows = []
    zs, rs = v['shield_z_m'], v['shield_r_m']
    for frac in (0.25, 0.5, 1.0):
        I = frac * v['loops'][0]['I']
        Rc = 0.8 * rs; zc = zs + 1.5
        extra = {'name': 'E_shield_coil', 'alpha_deg': math.degrees(math.atan2(Rc, zc)), 'd': math.hypot(Rc, zc), 'R': Rc, 'z': zc, 'I': I,
                 'a': max(G.MU0 * abs(I) / (2 * math.pi * 25.0), 0.02)}
        L = v['loops'] + [extra]
        T = shell.WorkTable(L, n_th=AX.N_TH, n_rho=AX.N_RHO)
        r = AX.leak(T, np.ones_like(T.th), v)
        M = G.F.inductance_matrix(L); Iv = np.array([q['I'] for q in L])
        W = 0.5 * Iv @ M @ Iv
        Br, Bz = G.F.loops_field(v['loops'], np.array([Rc]), np.array([zc]))
        rows.append({'current_MA': I / 1e6, 'coil_radius_m': Rc, 'coil_z_m': zc, 'in_shield_shadow': Rc / zc < rs / zs,
                     'leak_share_of_plasma': r['leak_share_of_plasma'], 'leak_W': r['leak_W'], 'leak_half_angle_deg': r['leak_half_angle_deg'],
                     'centre_fluence_J_cm2': r['centre_fluence_J_cm2'], 'stored_J_total': float(W),
                     'stored_increase_J': float(W) - T03_W(v), 'virial_mass_increase_t': (float(W) - T03_W(v)) * 1.07e-6 / 1e3,
                     'hoop_tension_MN': G.F.hoop_tension(Rc, extra['a'], I) / 1e6,
                     'axial_force_from_main_MN': float(-I * Br[0] * 2 * math.pi * Rc) / 1e6})
    return {'what': 'axisymmetric coil behind the shield, in its shadow', 'rows': rows,
            'verdict': 'NARROWS, DOES NOT REMOVE: the leak area falls with the extra field, but the forward pole stays a field zero, so the '
                       'shield centre still takes the full free-expansion fluence inside a smaller spot. It only shrinks a sacrificial insert.'}


def T03_W(v):
    M = G.F.inductance_matrix(v['loops']); Iv = np.array([q['I'] for q in v['loops']])
    return float(0.5 * Iv @ M @ Iv)


def concept_A1(v, k):
    rows = []
    for chi in (0.0, 4.0, 8.0, 12.0, 16.0):
        gl = G.tilted(v['loops'], ('C1@20', 'C2@40'), chi)
        f = lambda P, gl=gl: G.field_general(gl, P)
        R = stop_map(f, v, TH_FINE, PHI, k)
        d = destination(R, v, TH_FINE, PHI)
        nl = null(f, v, 0.85 * v['shield_z_m'], k)
        mo = momentum(f, v, k)
        rows.append({'tilt_deg': chi, 'null': nl, **d, 'momentum': mo,
                     'C1_nearest_polar_deg': 20.0 - chi})
        print(f"  A1 tilt {chi:4.1f}: null {nl['polar_deg']:.1f} deg, shield {d['shield_share']:.5f} spot {d['shield_spot_deg']:.1f}, parts "
              f"{ {a: round(b, 5) for a, b in d['parts_share'].items()} }, side/axial {mo['side_over_axial']:.4f} axial {mo['thrust_axis_share']:.4f}", flush=True)
    return {'what': 'C1 and C2 tilted together about the burn point in the x-z plane (conductor, currents and stand-off unchanged)', 'rows': rows}


def footprint(R, ths, phis, path_m):
    """Directions (polar, azimuth deg, ship frame from the burn point) of the rays not stopped by path_m, with a summary cone."""
    sel = ~np.isfinite(R) | (R > path_m)
    pts = [(float(t), float(p)) for i, t in enumerate(ths) for j, p in enumerate(phis) if sel[i, j]]
    if not pts:
        return {'rays': [], 'centre_polar_deg': None, 'radius_deg': 0.0}
    v = np.array([[math.sin(math.radians(t)) * math.cos(math.radians(p)), math.sin(math.radians(t)) * math.sin(math.radians(p)),
                   math.cos(math.radians(t))] for t, p in pts])
    c = v.mean(axis=0); c /= np.linalg.norm(c)
    rad = float(np.degrees(np.max(np.arccos(np.clip(v @ c, -1, 1)))))
    return {'rays_polar_azimuth_deg': pts, 'centre_polar_deg': math.degrees(math.acos(c[2])),
            'centre_azimuth_deg': math.degrees(math.atan2(c[1], c[0])) % 360, 'radius_deg': rad, 'path_m': path_m}


def concept_A1_aligned(v, k, chi=12.0):
    """A1 with the whole nozzle turned by -beta so the net thrust passes along the ship axis (and the centre of mass); shield and ship
    stay on the ship axis. beta from the momentum of the tilted case; one refinement."""
    beta = 0.0
    for _ in range(2):
        gl = G.rotated(v['loops'], {'C1@20': chi - beta, 'C2@40': chi - beta}, -beta)
        f = lambda P, gl=gl: G.field_general(gl, P)
        mo = momentum(f, v, k)
        beta += mo['thrust_line_tilt_deg'] * (1 if mo['side_share_x'] > 0 else -1)
    gl = G.rotated(v['loops'], {'C1@20': chi - beta, 'C2@40': chi - beta}, -beta)
    f = lambda P, gl=gl: G.field_general(gl, P)
    ths = np.arange(0.0, 30.0001, 0.1)
    R = stop_map(f, v, ths, PHI, k, rho_max=1.6 * v['shield_z_m'])
    d = destination(R, v, ths, PHI)
    mo = momentum(f, v, k)
    fp = footprint(R, ths, PHI, 1.6 * v['shield_z_m'] * 0.999)
    geo = [{'name': L['name'], 'radius_m': L['R'], 'centre_m': [float(x) for x in L['centre']], 'axis': [float(x) for x in L['axis']],
            'current_MA': L['I'] / 1e6} for L in gl]
    # the tilted C1 ring's closest approach to the ship axis (polar angle of its conductor seen from the burn point)
    c1 = next(L for L in gl if L['name'] == 'C1@20')
    ang = []
    for ph in np.radians(np.arange(0, 360, 1.0)):
        e1 = np.cross(c1['axis'], [0, 1.0, 0]); e1 = e1 / np.linalg.norm(e1); e2 = np.cross(c1['axis'], e1)
        P = c1['centre'] + c1['R'] * (math.cos(ph) * e1 + math.sin(ph) * e2)
        ang.append(math.degrees(math.acos(P[2] / np.linalg.norm(P))))
    return {'tilt_C1_C2_deg': chi, 'nozzle_turn_deg': -beta, 'C1_C2_net_tilt_deg': chi - beta, 'null': null(f, v, 0.85 * v['shield_z_m'], k),
            **d, 'momentum': mo, 'footprint': fp, 'loops_geometry': geo, 'C1_conductor_min_polar_deg': min(ang),
            'shield_rim_polar_deg': math.degrees(math.atan(v['shield_r_m'] / v['shield_z_m']))}


def concept_A2(v, k):
    rows = []
    zs, rs = v['shield_z_m'], v['shield_r_m']
    a = 5.25; zc = zs + 0.75 + a
    for I in (20e6, 60e6, 120e6, 240e6):
        f = lambda P, I=I: G.F.loops_cart(v['loops'], P) + G.loop_general(a, (0.0, 0.0, zc), (1.0, 0.0, 0.0), I, P)
        R = stop_map(f, v, TH_FINE, PHI, k)
        d = destination(R, v, TH_FINE, PHI)
        nl = null(f, v, 0.85 * zs, k)
        aw = max(G.MU0 * I / (2 * math.pi * 25.0), math.sqrt(I / (math.pi * 1e9)))
        W = 0.5 * G.F.self_inductance(a, aw) * I * I
        m = I * math.pi * a * a
        P = np.array([[0.0, 0.0, zc - 0.5], [0.0, 0.0, zc], [0.0, 0.0, zc + 0.5]])
        Bz = G.F.loops_cart(v['loops'], P)[:, 2]
        rows.append({'current_MA': I / 1e6, 'coil_radius_m': a, 'centre_z_m': zc, 'in_shadow': (a / zc) < rs / zs, 'null': nl, **d,
                     'stored_J': W, 'winding_minor_m': aw, 'virial_mass_t': W * 1.07e-6 / 1e3,
                     'static_torque_MN_m': m * float(Bz[1]) / 1e6, 'static_side_force_MN': 0.5 * m * abs(float(Bz[2] - Bz[0])) / 1e6,
                     'beam_deflection': beams(v, lambda P, I=I: G.loop_general(a, (0.0, 0.0, zc), (1.0, 0.0, 0.0), I, P))})
        print(f"  A2 {I / 1e6:5.0f} MA: null {nl['polar_deg']:.1f} deg, shield {d['shield_share']:.5f} spot {d['shield_spot_deg']:.1f}, "
              f"W {W / 1e9:.0f} GJ, beams {rows[-1]['beam_deflection'][0]['deflection_mrad']:.1f} mrad", flush=True)
    return {'what': 'circular coil, axis across the nozzle axis, behind the shield inside its X-ray shadow', 'rows': rows}


def beams(v, field, beam_deg=3.75):
    """Deflection of the 4 GeV driver ions (species not in FDP-1; Bi-209 1+ as the HIF reference, ASSUMPTION) by a transverse field."""
    mc2 = 209 * 0.931494; T = 4.0
    Brho = math.sqrt((T + mc2) ** 2 - mc2 ** 2) / 0.299792458
    t = math.radians(beam_deg); out = []
    s = np.linspace(0.5, v['shield_z_m'] / math.cos(t), 400)
    for ph in (0.0, 90.0):
        n = np.array([math.sin(t) * math.cos(math.radians(ph)), math.sin(t) * math.sin(math.radians(ph)), math.cos(t)])
        B = field(s[:, None] * n[None, :])
        Bp = np.linalg.norm(B - (B @ n)[:, None] * n[None, :], axis=1)
        intB = float(np.sum(0.5 * (Bp[1:] + Bp[:-1]) * np.diff(s)))
        ang = intB / Brho
        out.append({'beam_azimuth_deg': ph, 'int_Bperp_dl_T_m': intB, 'deflection_mrad': ang * 1e3,
                    'chromatic_spot_shift_mm_dp_p_1e-3': ang * 1e-3 * float(s[-1]) / 2 * 1e3, 'rigidity_T_m': Brho})
    return out


def concept_B(v, T, base):
    """Forward cap of mass m_d on the target covering polar 0..th_cap: the plasma in that cone shares momentum with it."""
    th = T.th; w = G.shell_weights(th)
    m_p = v['mass_per_pulse_kg']
    rows = []
    for th_cap in (5.0, 10.0):
        Om = 2 * math.pi * (1 - math.cos(math.radians(th_cap)))
        for m_d in (2e-6, 20e-6, 200e-6):
            mu_p = m_p / (4 * math.pi); mu_d = m_d / Om
            fac = mu_p / (mu_p + mu_d)                     # energy per sr after an inelastic share (momentum conserved)
            g = np.where(np.degrees(th) < th_cap, fac, 1.0)
            r = AX.leak(T, g, v)
            v_out = math.sqrt(2 * v['E_plasma_J'] / m_p) * fac
            rows.append({'cap_half_angle_deg': th_cap, 'cap_mass_mg': m_d * 1e6, 'cap_over_fuel': m_d / (v['R']['fusion']['pellet_fuel_mass_g'] / 1e3),
                         'energy_factor_in_cap': fac, 'leak_W': r['leak_W'], 'leak_half_angle_deg': r['leak_half_angle_deg'],
                         'centre_fluence_J_cm2': r['centre_fluence_J_cm2'], 'debris_speed_km_s': v_out / 1e3,
                         'debris_on_shield_mg_per_pulse': m_d * (1 - math.cos(math.radians(r['leak_half_angle_deg']))) / (1 - math.cos(math.radians(th_cap))) * 1e6,
                         'debris_on_shield_kg_per_year': m_d * (1 - math.cos(math.radians(r['leak_half_angle_deg']))) / (1 - math.cos(math.radians(th_cap)))
                         * v['rate_Hz'] * G.YEAR,
                         'thrust_loss_share': m_d / m_p * 0.0})
    return {'what': 'inert forward cap on the target (forward-suppressing target), momentum sharing only', 'rows': rows,
            'conflicts': ['the 9 driver beams arrive from polar 3.5-4 deg and the fast ignitor from 1-2 deg: a forward cap sits in their path, '
                          'so it is part of the target physics (T04 class), not an add-on',
                          'momentum sharing is an upper bound on the benefit: a hot cap re-expands and part of its energy comes back as radiation',
                          'the debris still flies along the field zero and lands on the shield centre, slower but as condensable mass']}


def concept_C(v):
    """Two nozzles splayed by +-alpha about the ship axis in a plane between the radiator wings, burn points offset laterally by y0."""
    R = v['R']; env = R['shield']['envelopes']
    rows = []
    th_u = 3.5
    for y0 in (40.0, 80.0):
        for alpha in (5.0, 10.0, 15.0):
            # forward channel of the +y nozzle: from (y0, -d_s...) direction tilted outward by alpha; nearest approach to the ship axis
            clear = []
            for e in env:
                x_rel = e['nearest_x_m'] - v['x_burn']
                lateral = y0 + x_rel * math.tan(math.radians(alpha - th_u))
                clear.append({'envelope': e['name'], 'radius_m': e['radius_m'], 'channel_inner_edge_m': lateral,
                              'clears': lateral > e['radius_m']})
            rows.append({'y0_m': y0, 'splay_deg': alpha, 'cosine_loss': 1 - math.cos(math.radians(alpha)),
                         'all_envelopes_clear': all(c['clears'] for c in clear), 'clearances': clear})
    return {'what': 'two nozzles splayed about the ship axis (alternate burn-point arrangement)', 'rows': rows,
            'costs': ['two coil sets, two shields, two driver/injector sets (each at half power, the coil mass per pulse energy is unchanged, '
                      'so total coil mass roughly x2 at the same pulse energy, or x2^(1/3)..x1 with smaller pulses)',
                      'each burn point now sees the ship from the side: the X-ray and neutron shadow geometry (FDP-1 Omega 0.025) is rebuilt',
                      'a single nozzle cannot be canted: its thrust must pass through the centre of mass, and its forward channel lies on that line'],
            'verdict': 'GEOMETRICALLY POSSIBLE, NOT EVALUATED AS A SHIP: it is a different propulsion architecture (two Fiji nozzles), '
                       'outside this gate; kept as an open lane.'}


def concept_S(v, base):
    sd = base['baseline']['shield_centre_surface']
    req = base['requirement']
    return {'what': 'sacrificial or renewable shield-centre insert inside the leak spot',
            'spot_radius_m_at_shield': v['shield_z_m'] * math.tan(math.radians(base['baseline']['leak_half_angle_deg'])),
            'fluence_J_cm2': sd['fluence_J_cm2'], 'heat_flux_factor_MJ_m2_s05': sd['heat_flux_factor_MJ_m2_s05'],
            'average_MW_m2': sd['average_MW_m2'], 'materials': sd['materials'], 'requirement': req,
            'reduction_needed_x': sd['fluence_J_cm2'] / req['limit_J_cm2'],
            'verdict': 'NOT VIABLE: the spot takes about 340 J/cm2 per pulse (about 650 MW/m2 average); a solid face would ablate tens of '
                       'microns per pulse (metres per hour), and a renewable lithium face would consume lithium at plug-like rates. The '
                       f'fluence must fall by about {sd["fluence_J_cm2"] / req["limit_J_cm2"]:.0f}x before any permanent face survives.'}


def choose(out):
    """The retained concept and what the coupled ship books for it."""
    r = out['A1_aligned']['14']      # 12 deg aligned still grazes the shield rim (inner leak edge 6.2 deg); 14 deg clears it
    eta = r['momentum']['thrust_axis_share'] / out['base_momentum']['thrust_axis_share']
    return {'concept': 'A1: C1 and C2 tilted 14 deg as a rigid pair, whole nozzle turned 2.7 deg so the thrust passes through the centre of mass',
            'leak_direction_polar_deg': r['footprint']['centre_polar_deg'], 'leak_radius_deg': r['footprint']['radius_deg'],
            'leak_share_of_plasma': r['escape_share_within_grid'] + sum(r['parts_share'].values()),
            'C1_conductor_min_polar_deg': r['C1_conductor_min_polar_deg'],
            'status': 'ANALYTICALLY PROMISING (vacuum-field thin shell); NOT a demonstrated plasma solution',
            'nozzle_efficiency_factor': eta, 'booked_kg': 0.0, 'house_W': 0.0,
            'booked_note': 'no added conductor; the pulsed side load and the re-placed C1/C2 supports are inside the coil strut booking '
                           '(PROTOTYPE); the thrust loss is booked as a nozzle-efficiency factor'}


def main():
    t0 = time.time()
    base = G.read('axis_base.json')
    v = G.v4()
    T = shell.WorkTable(v['loops'], n_th=AX.N_TH, n_rho=AX.N_RHO)
    k, cal = calibrate(v, base['baseline']['leak_share_of_plasma'])
    print('k', k, cal, flush=True)
    f0 = lambda P: G.F.loops_cart(v['loops'], P)
    base3d = destination(stop_map(f0, v, TH_FINE, PHI, k), v, TH_FINE, PHI)
    mom0 = momentum(f0, v, k)
    print('3D base', base3d, mom0, f'[{time.time() - t0:.0f} s]', flush=True)
    out = {'study': 'Feasibility gate Phase 1: concepts against ISS-022 (T00)', 'status': 'MODEL, research only, NON-CANON',
           'k_flux_exclusion': k, 'calibration': cal, 'base_3d': base3d, 'base_momentum': mom0}
    out['E'] = concept_E(v, T); print('E', [(r['current_MA'], round(r['leak_half_angle_deg'], 2), r['leak_W'] / 1e9) for r in out['E']['rows']], flush=True)
    out['A1'] = concept_A1(v, k)
    out['A1_aligned'] = {f'{c:g}': concept_A1_aligned(v, k, c) for c in (12.0, 14.0)}
    for c, r in out['A1_aligned'].items():
        print('A1 aligned', c, {x: r[x] for x in ('nozzle_turn_deg', 'shield_share', 'shield_spot_deg', 'C1_conductor_min_polar_deg')},
              r['null'], r['parts_share'], r['momentum'], {x: r['footprint'][x] for x in ('centre_polar_deg', 'radius_deg')}
              if r['footprint'].get('centre_polar_deg') else None, flush=True)
    out['A2'] = concept_A2(v, k)
    out['B'] = concept_B(v, T, base)
    out['C'] = concept_C(v)
    out['S'] = concept_S(v, base)
    out['chosen'] = choose(out)
    out['runtime_s'] = time.time() - t0
    G.write('concepts.json', out)
    print('done', round(out['runtime_s']), 's')


if __name__ == '__main__':
    main()
