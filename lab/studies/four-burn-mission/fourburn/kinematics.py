"""Burn kinematics, independent of the propulsion technology.

Constant proper acceleration (hyperbolic motion) and its Newtonian limit, the constant-thrust (constant-power, constant-ve) burn whose
acceleration rises as mass falls, and the throttled burn that holds an acceleration ceiling. Burn time is time under thrust only;
the journey also contains coasting, which depends on the (independent) destination distance.
"""
import math

from .const import C, AU, DAY, YEAR


def rapidity(v):
    return math.atanh(v/C)


def const_accel(dv, a, relativistic=True):
    """Burn from rest to dv at constant proper acceleration a. Returns coordinate time, proper time and distance (start frame)."""
    if not relativistic:
        return {'t_s': dv/a, 'tau_s': dv/a, 'd_m': dv**2/(2*a)}
    phi = rapidity(dv)
    return {'t_s': C/a*math.sinh(phi), 'tau_s': C/a*phi, 'd_m': C**2/a*(math.cosh(phi)-1)}


def const_thrust(dv, ve, a0):
    """Constant mass flow and exhaust speed from rest: initial acceleration a0, final a0*R. Newtonian (beta 0.016: error ~1e-4)."""
    R = math.exp(dv/ve); mdot_over_m0 = a0/ve
    t = (1-1/R)/mdot_over_m0
    # x = (ve/mdot) [(m0 - mf) - mf ln(m0/mf)] with masses in units of m0
    x = ve/mdot_over_m0*((1-1/R)-(1/R)*math.log(R))
    return {'t_s': t, 'd_m': x, 'a_end': a0*R, 'mass_ratio': R}


def throttled_burn(dv, ve, F, m_start, a_cap):
    """Constant thrust F until F/m reaches a_cap, then throttled to hold a_cap. Returns time, distance, end mass, peak acceleration."""
    R = math.exp(dv/ve); m_end = m_start/R; mdot = F/ve
    m_star = F/a_cap                                   # mass at which the cap is reached
    if m_star <= m_end:                                # cap never reached
        t = (m_start-m_end)/mdot
        x = ve/mdot*((m_start-m_end)-m_end*math.log(m_start/m_end))
        return {'t_s': t, 'd_m': x, 'm_end': m_end, 'a_peak': F/m_end, 'capped_s': 0.0}
    if m_star >= m_start:                              # capped from the start: constant a_cap
        r = const_accel(dv, a_cap, relativistic=False)
        return {'t_s': r['t_s'], 'd_m': r['d_m'], 'm_end': m_end, 'a_peak': a_cap, 'capped_s': r['t_s']}
    dv1 = ve*math.log(m_start/m_star); t1 = (m_start-m_star)/mdot
    x1 = ve/mdot*((m_start-m_star)-m_star*math.log(m_start/m_star))
    t2 = (dv-dv1)/a_cap; x2 = dv1*t2+0.5*a_cap*t2**2
    return {'t_s': t1+t2, 'd_m': x1+x2, 'm_end': m_end, 'a_peak': a_cap, 'capped_s': t2}


def accel_matrix(dv, accels_g, g0, burns=4):
    """Matrix A rows: per acceleration, time per burn (relativistic coordinate and proper), Newtonian error, distance, four-burn time,
    and the minimum destination distance (accelerate then brake, no coast)."""
    rows = []
    for ag in accels_g:
        a = ag*g0; r = const_accel(dv, a); n = const_accel(dv, a, relativistic=False)
        rows.append({'accel_g': ag, 'burn_days': r['t_s']/DAY, 'burn_proper_days': r['tau_s']/DAY,
                     'newtonian_time_error': n['t_s']/r['t_s']-1, 'accel_distance_AU': r['d_m']/AU,
                     'newtonian_distance_error': n['d_m']/r['d_m']-1,
                     'four_burn_days': burns*r['t_s']/DAY, 'four_burn_years': burns*r['t_s']/YEAR,
                     'min_destination_AU': 2*r['d_m']/AU, 'specific_jet_power_W_kg_per_ve': a/2})
    return rows
