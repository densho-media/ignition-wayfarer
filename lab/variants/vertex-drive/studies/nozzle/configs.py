"""Configurations A-D on the V1 nozzle geometry, coil sizing limits and the stored-energy ledger."""
import math

import numpy as np

import fields as F

B_LIMIT_T = 25.0          # TARGET: peak field on the winding (REBCO insert record 45.5 T, S-HAHN-2019; large coils far lower)
J_ENG_A_M2 = 1.0e9        # TARGET: engineering current density of the winding pack (Hahn 2019 insert 1.26e9 A/m2)
SIGMA_OVER_RHO = 1.0 / 1.07e-6   # J/kg: FDP-1/four-burn optimistic virial structure 1.07e-6 kg per J stored


def minor_radius(I):
    """Winding radius set by the surface-field and current-density limits (m)."""
    I = abs(I)
    return max(F.MU0 * I / (2 * math.pi * B_LIMIT_T), math.sqrt(I / (math.pi * J_ENG_A_M2)), 0.02)


def place(p, alphas_deg, d_rule='paraboloid'):
    """Loops at polar angles (deg from +z, the bow) on the V1 paraboloid or on the X-ray stand-off sphere (d = R_s)."""
    out = []
    for i, a in enumerate(alphas_deg):
        ar = math.radians(a)
        d = 2 * p['focal_m'] / (1 + math.cos(ar)) if d_rule == 'paraboloid' else p['R_s_m']
        out.append({'name': f'C{i+1}@{a:g}', 'alpha_deg': a, 'd': d, 'R': d * math.sin(ar), 'z': d * math.cos(ar)})
    return out


def with_currents(loops, I):
    out = []
    for L, i in zip(loops, I):
        q = dict(L); q['I'] = float(i); q['a'] = minor_radius(i); out.append(q)
    return out


def stored_energy(loops):
    M = F.inductance_matrix(loops)
    I = np.array([L['I'] for L in loops])
    return float(0.5 * I @ M @ I)


def ledger(loops, E_p):
    W = stored_energy(loops)
    return {'stored_J': W, 'W_over_Ep': W / E_p, 'virial_mass_t': W / SIGMA_OVER_RHO / 1e3,
            'conductor_minor_m': [L['a'] for L in loops], 'currents_MA': [L['I'] / 1e6 for L in loops],
            'B_surface_T': [F.MU0 * abs(L['I']) / (2 * math.pi * L['a']) for L in loops],
            'hoop_tension_MN': [F.hoop_tension(L['R'], L['a'], L['I']) / 1e6 for L in loops]}
