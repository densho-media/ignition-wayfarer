"""Gate 2 Task A, part 1: the tilted closure A1 as a function of tilt (T00, research only, NON-CANON).

  python3 lab/variants/vertex-drive/studies/gate2/cone.py      # writes results/cone.json (minutes)

For C1 + C2 tilted chi (rigid pair) and the whole field set turned back so the net thrust lies on the ship axis (gate concepts.py
'aligned'), this gives what limits the ship's shadow cone: where the moved leak goes (centre, radius, inner edge), the shield-rim limit
(inner edge minus the gate's 0.34 deg margin), the C1 conductor's nearest polar angle, the thrust cost (momentum factor and the
calculator's thrust-efficiency factor = momentum factor squared), the residual torque and the driver-beam deflection.

Torque: the reaction on the field of a radially expanding pulse has zero moment about the burn point except for the angular momentum
the reflected plasma carries away (r x p of each reflected element, thin shell). With the net thrust on the ship axis and the burn point
on it, this is the only thrust torque about the centre of mass; the lateral CoM shift of the turned coils adds T x dy. The static
magnetic torque between the tilted pair and the loops is an internal strut load, not a ship torque. Vacuum field, thin shell, no MHD.
"""
import math
import time

import numpy as np

import g2
import concepts as CC
G = g2.G

TILTS = (14.0, 15.0, 16.0, 18.0, 20.0, 22.0)
MARGIN = 10.828821274840449 - 2.9884841042408197 - 7.5     # the gate's 7.5 deg rim limit at 14 deg, as a margin below the leak edge
COIL_T = {'C1@20': None, 'C2@40': None}


def moments(field, v, k, dth=1.0, dphi=10.0):
    """momentum() of the gate plus the reflected angular momentum about the burn point (per unit pulse momentum m v, metres)."""
    ths = np.arange(dth / 2, 180.0, dth); phis = np.arange(0.0, 360.0, dphi)
    R = CC.stop_map(field, v, ths, phis, k, rho_max=1.25 * 194.1, n_rho=500)
    t = np.radians(ths)[:, None]; p = np.radians(phis)[None, :]
    rh = np.stack(np.broadcast_arrays(np.sin(t) * np.cos(p), np.sin(t) * np.sin(p), np.cos(t)), axis=-1)
    th_h = np.stack(np.broadcast_arrays(np.cos(t) * np.cos(p), np.cos(t) * np.sin(p), -np.sin(t)), axis=-1)
    ph_h = np.stack(np.broadcast_arrays(-np.sin(p), np.cos(p), 0 * t), axis=-1)
    Rf = np.where(np.isfinite(R), R, np.nan)
    dRt = np.gradient(Rf, np.radians(dth), axis=0)
    dRp = (np.roll(Rf, -1, axis=1) - np.roll(Rf, 1, axis=1)) / (2 * np.radians(dphi))
    nrm = rh - (dRt / Rf)[..., None] * th_h - (dRp / (Rf * np.sin(t)))[..., None] * ph_h
    ok = np.all(np.isfinite(nrm), axis=-1)
    nrm = np.where(ok[..., None], nrm, rh); nrm /= np.linalg.norm(nrm, axis=-1)[..., None]
    outd = np.where(ok[..., None], rh - 2 * np.sum(rh * nrm, axis=-1)[..., None] * nrm, rh)
    w = (np.sin(t) * np.radians(dth) * np.radians(dphi)) * np.ones_like(p) / (4 * math.pi)
    Pm = np.sum(w[..., None] * outd, axis=(0, 1))
    pos = np.where(ok[..., None], np.nan_to_num(Rf)[..., None] * rh, 0.0)
    Lm = np.sum(w[..., None] * np.cross(pos, outd), axis=(0, 1))          # angular momentum carried away, per unit m v
    tq = -Lm                                                              # torque on the ship (reaction)
    ax = -Pm[2]
    return {'thrust_axis_share': float(ax), 'side_over_axial': float(math.hypot(Pm[0], Pm[1]) / max(ax, 1e-12)),
            'torque_per_unit_mv_m': [float(x) for x in tq], 'lever_arm_m': float(np.linalg.norm(tq[:2]) / max(ax, 1e-12)),
            'roll_lever_m': float(abs(tq[2]) / max(ax, 1e-12))}


def loop_points(L, n=360):
    a = np.asarray(L['axis'], float); a /= np.linalg.norm(a)
    e1 = np.cross(a, [0, 1.0, 0]); e1 = e1 / np.linalg.norm(e1) if np.linalg.norm(e1) > 1e-9 else np.array([1.0, 0, 0])
    e2 = np.cross(a, e1)
    ph = np.linspace(0, 2 * math.pi, n, endpoint=False)
    P = np.asarray(L['centre'])[None, :] + L['R'] * (np.cos(ph)[:, None] * e1 + np.sin(ph)[:, None] * e2)
    dl = L['R'] * (2 * math.pi / n) * (-np.sin(ph)[:, None] * e1 + np.cos(ph)[:, None] * e2)
    return P, dl


def static_load(gl, movers=('C1@20', 'C2@40')):
    """Net force and torque (about the burn point) on the tilted pair from the other loops' field (filaments; internal strut load)."""
    others = [L for L in gl if L['name'] not in movers]
    F = np.zeros(3); T = np.zeros(3)
    for L in gl:
        if L['name'] not in movers:
            continue
        P, dl = loop_points(L)
        B = G.field_general(others, P)
        dF = L['I'] * np.cross(dl, B)
        F += dF.sum(axis=0); T += np.cross(P, dF).sum(axis=0)
    return {'force_MN': [float(x) / 1e6 for x in F], 'torque_MN_m': [float(x) / 1e6 for x in T],
            'torque_mag_MN_m': float(np.linalg.norm(T)) / 1e6}


def c1_near(gl, a_env=1.58):
    """The tilted C1 conductor point nearest the ship axis (polar from the burn point), its (z, r), and the envelope's reach
    (T05 assembly half-width 1.58 m) toward the axis and along z."""
    c1 = next(L for L in gl if L['name'] == 'C1@20')
    P, _ = loop_points(c1, 720)
    pol = np.degrees(np.arccos(P[:, 2] / np.linalg.norm(P, axis=1)))
    i = int(np.argmin(pol)); z, r = float(P[i, 2]), float(math.hypot(P[i, 0], P[i, 1]))
    return {'polar_deg': float(pol[i]), 'z_m': z, 'r_m': r, 'envelope_r_min_m': r - a_env, 'envelope_z_m': [z - a_env, z + a_env],
            'envelope_polar_deg': math.degrees(math.atan2(r - a_env, z))}


def beam_defl(v, gl):
    f = lambda P: G.field_general(gl, P)
    full = []
    mc2 = 209 * 0.931494; T = 4.0
    Brho = math.sqrt((T + mc2) ** 2 - mc2 ** 2) / 0.299792458
    t = math.radians(3.75)
    s = np.linspace(0.5, v['shield_z_m'] / math.cos(t), 400)
    for ph in np.arange(0.0, 360.0, 40.0):
        n = np.array([math.sin(t) * math.cos(math.radians(ph)), math.sin(t) * math.sin(math.radians(ph)), math.cos(t)])
        B = f(s[:, None] * n[None, :])
        Bp = np.linalg.norm(B - (B @ n)[:, None] * n[None, :], axis=1)
        full.append(float(np.sum(0.5 * (Bp[1:] + Bp[:-1]) * np.diff(s))) / Brho * 1e3)
    return {'beam_polar_deg': 3.75, 'deflection_mrad_by_azimuth_40deg': full, 'max_mrad': max(full), 'min_mrad': min(full)}


def tilt(v, k, chi):
    r = CC.concept_A1_aligned(v, k, chi)
    beta = -r['nozzle_turn_deg']
    gl = G.rotated(v['loops'], {'C1@20': chi - beta, 'C2@40': chi - beta}, -beta)
    f = lambda P, gl=gl: G.field_general(gl, P)
    mo = moments(f, v, k)
    fp = r['footprint']
    edge = fp['centre_polar_deg'] - fp['radius_deg'] if fp.get('centre_polar_deg') is not None else None
    c1 = next(L for L in gl if L['name'] == 'C1@20'); c2 = next(L for L in gl if L['name'] == 'C2@40')
    return {'tilt_deg': chi, 'nozzle_turn_deg': r['nozzle_turn_deg'], 'leak_centre_polar_deg': fp.get('centre_polar_deg'),
            'leak_radius_deg': fp.get('radius_deg'), 'leak_inner_edge_deg': edge, 'rim_limit_deg': (edge - MARGIN) if edge else None,
            'leak_share_of_plasma': r['escape_share_within_grid'] + sum(r['parts_share'].values()), 'shield_share': r['shield_share'],
            'parts_share_V4_kernel': r['parts_share'], 'C1_conductor_min_polar_deg': r['C1_conductor_min_polar_deg'],
            'momentum': mo, 'C1_centre_m': [float(x) for x in c1['centre']], 'C2_centre_m': [float(x) for x in c2['centre']],
            'static_pair_load': static_load(gl), 'C1_near_side': c1_near(gl), 'beams': beam_defl(v, gl), 'null': r['null'],
            'rays_polar_azimuth_deg': fp.get('rays_polar_azimuth_deg')}


def main():
    t0 = time.time()
    v = G.v4(); cc = g2.gate('concepts.json'); k = cc['k_flux_exclusion']
    f0 = lambda P: G.F.loops_cart(v['loops'], P)
    base = moments(f0, v, k)
    gl0 = G.rotated(v['loops'], {}, 0.0)
    out = {'study': 'Gate 2 Task A: A1 tilt sweep (T00)', 'status': 'MODEL, research only, NON-CANON (vacuum field, thin shell)',
           'k_flux_exclusion': k, 'margin_deg': MARGIN, 'base_momentum': base, 'base_beams': beam_defl(v, gl0), 'rows': []}
    for chi in TILTS:
        r = tilt(v, k, chi)
        r['momentum_factor'] = r['momentum']['thrust_axis_share'] / base['thrust_axis_share']
        r['thrust_efficiency_factor'] = r['momentum_factor'] ** 2
        out['rows'].append(r)
        print(f"chi {chi:4.1f}: turn {r['nozzle_turn_deg']:.2f} leak {r['leak_centre_polar_deg']:.2f}+-{r['leak_radius_deg']:.2f} edge "
              f"{r['leak_inner_edge_deg']:.2f} rim<= {r['rim_limit_deg']:.2f} C1 {r['C1_conductor_min_polar_deg']:.2f} mom {r['momentum_factor']:.4f} "
              f"lever {r['momentum']['lever_arm_m']:.3f} m static {r['static_pair_load']['torque_mag_MN_m']:.0f} MN.m beams "
              f"{r['beams']['max_mrad']:.1f} mrad [{time.time() - t0:.0f} s]", flush=True)
    out['runtime_s'] = time.time() - t0
    g2.write('cone.json', out)


if __name__ == '__main__':
    main()
