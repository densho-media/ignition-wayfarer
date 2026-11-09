"""Test-particle (low-beta limit) orbits in the vacuum nozzle field: Boris pusher, ions launched isotropically from the burn point.
Valid only for the dilute tail and late debris of a pulse, where the plasma no longer pushes the field; the main beta >> 1 shell is
the thin-shell model's job. Collective effects (diamagnetism, ambipolar fields, instabilities) are absent by construction."""
import math

import numpy as np

import fields as F
from pulse import QE, U, SPECIES


def boris(loops, q, m, X, V, dt, steps, stop):
    """Advance particles (N,3); stop(X) -> array of fate codes (0 = still flying). Returns final X, V, fate, step of fate."""
    fate = np.zeros(len(X), int); when = np.full(len(X), -1)
    for k in range(steps):
        live = fate == 0
        if not live.any():
            break
        B = F.loops_cart(loops, X[live])
        t = (q * dt / (2 * m)) * B
        s = 2 * t / (1 + np.sum(t * t, axis=1))[:, None]
        v = V[live]
        vp = v + np.cross(v, t)
        V[live] = v + np.cross(vp, s)
        X[live] = X[live] + V[live] * dt
        f = stop(X)
        new = live & (f != 0)
        fate[new] = f[new]; when[new] = k
    return X, V, fate, when


def launch(n, speed, seed=3):
    rng = np.random.default_rng(seed)
    u = rng.normal(size=(n, 3)); u /= np.linalg.norm(u, axis=1)[:, None]
    return np.zeros((n, 3)) + 1e-3 * u, speed * u


def run(p, loops, species, n=600, speed=None, t_max=None, dt_frac=0.05, extra_tubes=()):
    m = SPECIES[species][0] * U; q = SPECIES[species][1] * QE
    speed = speed or p['v_rms_m_s']
    X, V = launch(n, speed)
    B0 = float(np.linalg.norm(F.loops_cart(loops, np.zeros((1, 3)))[0]))
    Bmax = 2.5 * B0
    dt = dt_frac * 2 * math.pi * m / (abs(q) * Bmax)
    t_max = t_max or 1600.0 / speed
    steps = int(t_max / dt)
    zs, rs = p['shield_z_m'], p['shield_radius_m']
    tubes = [(L['R'], L['z'], max(0.5, L['a'] + 0.3)) for L in loops]

    def stop(X):
        r = np.hypot(X[:, 0], X[:, 1]); z = X[:, 2]
        f = np.zeros(len(X), int)
        f[(z >= zs) & (r <= rs)] = 1                       # shield face
        f[(f == 0) & (z >= zs) & (r > rs)] = 2             # forward past the shield plane: toward hull and wings
        for (R, zc, a) in tubes:
            f[(f == 0) & (np.hypot(r - R, z - zc) < a)] = 3  # coil envelope
        f[(f == 0) & (z < -500.0)] = 4                      # leaves aft
        f[(f == 0) & (np.hypot(r, z) > 700.0)] = 5          # leaves sideways
        return f
    X, V, fate, when = boris(loops, q, m, X, V, dt, steps, stop)
    out = V[fate == 4]
    ax = -out[:, 2] / np.linalg.norm(out, axis=1) if len(out) else np.array([0.0])
    names = {0: 'still_inside', 1: 'shield', 2: 'forward_ship', 3: 'coil', 4: 'aft_exhaust', 5: 'sideways'}
    share = {names[k]: float(np.mean(fate == k)) for k in names}
    rL = m * speed / (abs(q) * B0)
    return {'species': species, 'n': n, 'speed_m_s': speed, 'B_burn_T': B0, 'gyroradius_at_burn_m': rL, 'dt_s': dt, 'steps': steps,
            'fate_share': share, 'aft_mean_cos': float(np.mean(ax)), 'aft_eta_mom': float(np.mean(ax)) * share['aft_exhaust']}


def mirror_axis(loops, z_lo=-400.0, z_hi=60.0, n=4000):
    """On-axis field, its forward maximum and the forward loss-cone share of an isotropic point source (adiabatic theory)."""
    z = np.linspace(z_lo, z_hi, n)
    _, Bz = F.loops_field(loops, np.zeros_like(z), z)
    B = np.abs(Bz); B0 = float(np.interp(0.0, z, B))
    fw = z > 0
    Bm = float(B[fw].max()); zm = float(z[fw][np.argmax(B[fw])])
    Rm = Bm / B0
    lc = (1 - math.sqrt(max(0.0, 1 - 1 / Rm))) / 2 if Rm > 1 else 0.5
    return {'B_burn_T': B0, 'B_forward_max_T': Bm, 'z_forward_max_m': zm, 'mirror_ratio': Rm,
            'forward_loss_cone_share': lc, 'B_aft_100m_T': float(np.interp(-100.0, z, B))}
