"""First Ignition timing (Q35, 2026-10-03b): the exact S&E result of the linear 0 to a_max acceleration ramp (20_FIRST_IGNITION C11:C16).

a(t) = k t and v = k t^2 / 2, so reaching the target speed v at the peak acceleration a_max takes t = 2 v / a_max, with k = a_max / t, and the
distance is x = k t^3 / 6. Pure functions over the spec dict; g0 comes from habitat_ring and c from forward_shield (one place each). The Sanity
Check copy of the duration follows this result (owner wins); nothing here is an input to geometry.
"""
from habitat_ring import G0
from forward_shield import SPEED_OF_LIGHT

DAY_S = 86400.0              # 01_CONSTANTS!A5 (Locked)
AU_M = 1.495978707e11        # 01_CONSTANTS!A4 (Locked)


def result(s):
    """Time to the target speed and the distance covered under the linear acceleration ramp."""
    v = s['mission']['target_speed']['value']*SPEED_OF_LIGHT
    a_max = s['mission']['first_ignition']['max_accel']*G0
    t = 2*v/a_max
    k = a_max/t
    x = k*t**3/6
    return {'time_s': t, 'duration_d': t/DAY_S, 'ramp_m_s3': k, 'distance_m': x, 'distance_AU': x/AU_M}
