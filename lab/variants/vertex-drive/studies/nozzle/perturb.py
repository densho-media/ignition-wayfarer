"""Non-axisymmetric field perturbations on an axisymmetric nozzle design, and their first-order effect on the thin-shell stopping
surface: sector gaps and differential sector currents (B, VTX-03A), counter-clocked sectors (D, VTX-03C), and helical windings on the
paraboloid (C3D, VTX-03B). MODEL: perturbations are vacuum fields at the unperturbed stopping surface; the surface moves by the
first-order energy balance dR = -g E_sr / (p R^2) with g the fractional change of tangential magnetic pressure."""
import math

import numpy as np

import fields as F
import shell


def _arc(R, z, a0, a1, step_deg=1.0):
    n = max(2, int(abs(math.degrees(a1 - a0)) / step_deg))
    return F.arc_polyline(R, z, a0, a1, n)


def _radial(R0, R1, z, ang):
    return np.array([[R0 * math.cos(ang), R0 * math.sin(ang), z], [R1 * math.cos(ang), R1 * math.sin(ang), z]])


def segs_from_paths(paths):
    A, B, I = [], [], []
    for pts, cur in paths:
        A.append(pts[:-1]); B.append(pts[1:]); I.append(np.full(len(pts) - 1, cur))
    return np.vstack(A), np.vstack(B), np.concatenate(I)


def sector_paths(loop, clock_deg, gap_deg=5.0, eps=0.0, m_pattern=2, detour_m=1.0, bus_m=5.0):
    """Perturbation current paths of one loop split into four sectors (relative to the full ring at current I):
    gaps (the ring current detours outward around each gap by detour_m) and a differential current eps*I*s_q,
    s_q = cos(m_pattern*phi_q), each closed through radial leads and a feeder bus arc bus_m outside the ring."""
    R, z, I = loop['R'], loop['z'], loop['I']
    paths = []
    g = math.radians(gap_deg)
    for q in range(4):
        c = math.radians(clock_deg + 90.0 * q)                    # gap centre
        a0, a1 = c - g / 2, c + g / 2
        paths.append((_arc(R, z, a0, a1, 0.25), -I))              # remove the ring current across the gap
        det = np.vstack([_radial(R, R + detour_m, z, a0), _arc(R + detour_m, z, a0, a1, 0.25), _radial(R + detour_m, R, z, a1)])
        paths.append((det, I))                                    # the detour carries it outside
    if eps:
        for q in range(4):
            c0 = math.radians(clock_deg + 90.0 * q) + g / 2; c1 = c0 + math.radians(90.0) - g
            s = math.cos(m_pattern * (0.5 * (c0 + c1) - math.radians(clock_deg + 45.0)))
            dI = eps * I * s
            loop_path = np.vstack([_arc(R, z, c0, c1), _radial(R, R + bus_m, z, c1), _arc(R + bus_m, z, c1, c0), _radial(R + bus_m, R, z, c0)])
            paths.append((loop_path, dI))
    return paths


def helical_paths(p, I_h, twist_deg, alpha0=60.0, alpha1=120.0, balanced=False, n=240, l=2):
    """Closed l = 2 helical windings on the V1 paraboloid between polar angles alpha0 and alpha1. Each of l pairs runs out along
    a helix (current +I_h), along the alpha1 ring by 90/l deg, back along the neighbouring helix (-I_h) and along the alpha0 ring.
    balanced=True reverses the twist half-way (counter-helical, VTX-03C)."""
    f = p['focal_m']; paths = []
    al = np.radians(np.linspace(alpha0, alpha1, n))
    t = (al - al[0]) / (al[-1] - al[0])
    tw = math.radians(twist_deg)
    phase = tw * (np.where(t < 0.5, t, 1 - t) if balanced else t)
    d = 2 * f / (1 + np.cos(al)); r = d * np.sin(al); z = d * np.cos(al)
    for k in range(l):
        ph0 = 2 * math.pi * k / l
        def helix(off):
            return np.stack([r * np.cos(ph0 + off + phase), r * np.sin(ph0 + off + phase), z], axis=1)
        h1 = helix(0.0); h2 = helix(math.pi / (2 * l) * 2)
        e1 = h1[-1]; e2 = h2[-1]
        R1 = math.hypot(e1[0], e1[1]); a_e1 = math.atan2(e1[1], e1[0]); a_e2 = math.atan2(e2[1], e2[0])
        if a_e2 < a_e1:
            a_e2 += 2 * math.pi
        R0 = math.hypot(h1[0, 0], h1[0, 1]); a_s1 = math.atan2(h1[0, 1], h1[0, 0]); a_s2 = math.atan2(h2[0, 1], h2[0, 0])
        if a_s2 < a_s1:
            a_s2 += 2 * math.pi
        path = np.vstack([h1, _arc(R1, e1[2], a_e1, a_e2), h2[::-1], _arc(R0, h1[0, 2], a_s2, a_s1)])
        paths.append((path, I_h))
    return paths


def surface_effect(p, loops, table, R_th, paths, E_p, n_phi=72, hardware=None, base=None):
    """Ripple, shear, stopping-surface deformation, momentum efficiency and roll torque from perturbation paths."""
    th = table.th; ok = np.isfinite(R_th)
    phi = np.linspace(0, 2 * math.pi, n_phi, endpoint=False)
    TT, PP = np.meshgrid(th[ok], phi, indexing='ij')
    RR = np.repeat(R_th[ok][:, None], n_phi, axis=1)
    P = np.stack([RR * np.sin(TT) * np.cos(PP), RR * np.sin(TT) * np.sin(PP), RR * np.cos(TT)], axis=-1).reshape(-1, 3)
    B0 = F.loops_cart(loops, P)
    if paths:
        A, B, I = segs_from_paths(paths)
        dB = F.segments_field(A, B, I, P, core=0.05)
    else:
        dB = np.zeros_like(P)
    rh = P / np.linalg.norm(P, axis=1)[:, None]
    tang = lambda v: v - np.sum(v * rh, axis=1)[:, None] * rh
    B0t = tang(B0); dBt = tang(dB)
    ph_hat = np.stack([-np.sin(PP).ravel(), np.cos(PP).ravel(), np.zeros(P.shape[0])], axis=1)
    mag0 = np.linalg.norm(B0t, axis=1)
    g = np.sum((B0t + dBt) ** 2, axis=1) / np.maximum(mag0 ** 2, 1e-30) - 1
    shear = np.degrees(np.arctan2(np.abs(np.sum((B0t + dBt) * ph_hat, axis=1)), mag0))
    # surface pressure at R from the table (kappa-scaled), then first-order radius shift
    E_sr = E_p / (4 * math.pi)
    j_ok = np.where(ok)[0]
    p_R = np.array([np.interp(R_th[j], table.rho, table.Bt[:, j] ** 2 / (2 * F.MU0)) for j in j_ok])
    dR = (-g.reshape(len(j_ok), n_phi) * E_sr / (p_R[:, None] * R_th[ok][:, None] ** 2))
    Rp = RR + dR
    # 3D normals and reflection
    dth = np.gradient(Rp, th[ok], axis=0); dph = (np.roll(Rp, -1, axis=1) - np.roll(Rp, 1, axis=1)) / (2 * (phi[1] - phi[0]))
    st = np.sin(TT); ct = np.cos(TT); cp = np.cos(PP); sp = np.sin(PP)
    rhat = np.stack([st * cp, st * sp, ct], -1); thhat = np.stack([ct * cp, ct * sp, -st], -1); phhat = np.stack([-sp, cp, 0 * cp], -1)
    n = rhat - (dth / Rp)[..., None] * thhat - (dph / (Rp * np.maximum(st, 1e-6)))[..., None] * phhat
    n /= np.linalg.norm(n, axis=-1)[..., None]
    out = rhat - 2 * np.sum(rhat * n, -1)[..., None] * n
    P0 = Rp[..., None] * rhat
    w = (np.sin(TT) * np.gradient(th)[ok][:, None]) / (np.sum(np.sin(th) * np.gradient(th)) * n_phi)
    hit = None
    if hardware is not None:
        flatP = P0.reshape(-1, 3); flatD = out.reshape(-1, 3)
        hit = shell.ray_hits_many(flatP + 1e-3 * flatD, flatD, hardware, n=1500).reshape(out.shape[:2])
        fwd = -out[..., 2] < 0
        hit = np.where((hit == None) & fwd, 'ship_forward', hit)  # noqa: E711
    clean = np.ones(out.shape[:2], bool) if hit is None else (hit == None)  # noqa: E711
    ax = -out[..., 2]
    Lz_unit = np.cross(P0, out)[..., 2]                                            # m per unit speed and mass
    m_sr = p['mass_per_pulse_kg'] / (4 * math.pi); v = p['v_rms_m_s']
    dL = float(np.sum(w * 4 * math.pi * m_sr * v * Lz_unit * clean))               # angular momentum per pulse (N m s)
    swirl = float(np.sum(w * np.abs(np.sum(out * phhat, -1)) * clean) / max(np.sum(w * clean), 1e-12))
    net_swirl = float(np.sum(w * np.sum(out * phhat, -1) * clean) / max(np.sum(w * clean), 1e-12))
    # rays the shell does not stop (aft cone) leave unperturbed to first order: take them from the axisymmetric result
    extra = 0.0
    if base is not None:
        ax0 = -base['dir'][:, 2]; cl0 = np.array([h is None for h in base['hit']])
        extra = float(np.sum(base['w'] * ax0 * cl0 * ~ok))
    dRf = np.abs(dR).ravel()
    lat = np.array([float(np.sum(w * out[..., 0] * clean)), float(np.sum(w * out[..., 1] * clean))])
    return {'dR_p50_m': float(np.percentile(dRf, 50)), 'dR_p95_m': float(np.percentile(dRf, 95)),
            'eta_mom_total': float(np.sum(w * ax * clean)) + extra, 'ripple_max': float(np.max(np.abs(g)) / 2), 'ripple_rms': float(np.sqrt(np.mean(g ** 2)) / 2),
            'shear_max_deg': float(np.max(shear)), 'shear_rms_deg': float(np.sqrt(np.mean(shear ** 2))),
            'dR_max_m': float(np.max(np.abs(dR))), 'eta_mom': float(np.sum(w * ax * clean)),
            'strike_share': float(np.sum(w * ~clean)), 'roll_torque_Nm': dL * p['rep_Hz'],
            'mean_abs_swirl': swirl, 'net_swirl': net_swirl,
            'lateral_momentum_share': float(np.hypot(*lat)), 'lateral_direction_deg': float(np.degrees(np.arctan2(lat[1], lat[0])))}


def lost_sector_paths(loop, q, clock_deg=0.0, gap_deg=5.0, bus_m=5.0):
    """One sector of a loop at zero current: a closed circuit carrying -I around that sector (its arc, radial leads, feeder bus)."""
    R, z, I = loop['R'], loop['z'], loop['I']
    g = math.radians(gap_deg)
    c0 = math.radians(clock_deg + 90.0 * q) + g / 2; c1 = c0 + math.radians(90.0) - g
    path = np.vstack([_arc(R, z, c0, c1), _radial(R, R + bus_m, z, c1), _arc(R + bus_m, z, c1, c0), _radial(R + bus_m, R, z, c0)])
    return [(path, -I)]
