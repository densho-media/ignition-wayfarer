"""Cabin atmosphere and ECLSS rules (HAB-002): pure checks over the captured data. Leaf module, standard library only.

Canon (drive_capture_2026-10-03, S&E 02_SHIP_INPUTS A46:H52, 12_HABITAT_LAYOUT A18:H27, 98_DECISION_LOG A51, A57). The O2 and N2
fractions are nominal dry-gas fractions; the CO2 target and humidity are additional. No geometry reads these values.
"""
import math


def o2_partial_kpa(pressure_kpa, o2_fraction):
    """12!F20: dry-gas approximation, humidity and trace gases not subtracted."""
    return pressure_kpa*o2_fraction


def check(s):
    """Failure strings for the cabin atmosphere data; empty when consistent."""
    a = s['habitat']['atmosphere']; c = a['control']; bad = []
    for key in ('o2_fraction', 'n2_balance_fraction'):
        if not 0 < a[key] < 1:
            bad.append(f'{key} outside (0, 1)')
    if not math.isclose(a['o2_fraction']+a['n2_balance_fraction'], 1.0, abs_tol=1e-9):
        bad.append('O2 + N2 dry-gas fractions must sum to 1 (02!A47:A48)')
    if not 0 < c['co2_target_fraction'] < c['co2_max_fraction'] < 1:
        bad.append('CO2 must satisfy 0 < target < max < 1')
    if not 0 < c['rh_min'] < c['rh_max'] < 1:
        bad.append('RH must satisfy 0 < min < max < 1')
    p = a['o2_partial']
    if p.get('unit') != 'kPa' or not 0 < p['value'] < a['cabin_pressure_kpa']:
        bad.append('o2_partial must be in kPa and below the cabin pressure')
    for name, node in [('control.tolerances', c['tolerances']), ('emergency_o2', a['emergency_o2']),
                       ('eva_interface.suit', a['eva_interface']['suit']), ('eclss.open', s['habitat']['eclss']['open'])]:
        if node.get('known') is not False or 'value' in node:
            bad.append(f'{name} must stay known = false with no value')
    return bad
