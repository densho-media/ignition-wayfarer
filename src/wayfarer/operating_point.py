"""B01 First Ignition operating point (WORKING, Claude under the owner's delegation of 2026-10-31; S&E 15 OWN-B01-OPERATING-POINT-2026-10-31).

The owner's coupled research model (S&E 64_COUPLED_INPUTS, 65_BURN_MASSFLOW, 67_SCENARIO_TRADE case E) taken as the ship's one consistent
operating point, with the single change that closes its hot loop: the absorbed fraction of gross fusion power. Standard library only.

A linear 0 to a_max ramp to the LOCKED target speed (first_ignition) at a constant effective exhaust velocity ve:
- the mass falls as m(t) = m0 exp(-v(t)/ve), so the expelled mass is m0 (1 - exp(-dv/ve)) (65 B39:B41);
- thrust F = m a, directed jet power P = F ve / 2 and gross fusion power P / eta, all peaking at burnout (65 row 34);
- the jet's kinetic energy over the burn is expelled ve^2 / 2, so the reacted D-3He is that energy / eta / its specific energy (65 B42),
  split by stoichiometry (64 B23:B24); unburned feed that is not recovered leaves in the jet (64 B25:B26); the rest of the jet is hydrogen;
- absorbed drive heat = f_hot x gross fusion power, against the ideal hot-loop rejection (thermal_budget, 40!B7:B9).

    python3 src/wayfarer/operating_point.py      # prints the point and writes references/p1_operating_point.json
"""
import json
import math
from pathlib import Path

import first_ignition
import thermal_budget
from habitat_ring import G0

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'references/p1_operating_point.json'


def p(s):
    return s['physics']['operating_point']


def burn(s, f_hot=None, steps=2000):
    """The First Ignition burn at the operating point (or with another absorbed fraction f_hot): totals, peaks and the hot-loop check."""
    q = p(s); fi = first_ignition.result(s); T = fi['time_s']; a_max = s['mission']['first_ignition']['max_accel']*G0
    dv = fi['ramp_m_s3']*T**2/2; ve = q['exhaust_velocity_m_s']; m0 = q['departure_mass_kg']; eta = q['directed_efficiency']
    f_hot = q['absorbed_fraction'] if f_hot is None else f_hot
    mf = m0*math.exp(-dv/ve); expelled = m0-mf
    jet_J = expelled*ve**2/2; fusion_J = jet_J/eta
    reacted = fusion_J/q['dhe3_specific_energy_J_kg']; lost = reacted/q['burnup']*(1-q['burnup'])*(1-q['recovery'])
    peak_F = mf*a_max; peak_jet = peak_F*ve/2; peak_fus = peak_jet/eta; peak_hot = f_hot*peak_fus
    r = s['radiators']
    reject = thermal_budget.ideal_rejection_W(r['effective_area']['value'], r['emissivity']['value'], r['temperature']['value'])
    # time of first hot-loop overload along the ramp (absorbed heat grows as t exp(-v/ve))
    over_s = None
    for i in range(steps+1):
        t = T*i/steps; a = a_max*t/T; v = a_max*t*t/(2*T); m = m0*math.exp(-v/ve)
        if f_hot*m*a*ve/2/eta > q['hot_share']*reject:
            over_s = t; break
    share_he3 = q['he3_mass_share']
    return {'duration_s': T, 'delta_v_m_s': dv, 'exhaust_velocity_m_s': ve, 'exhaust_velocity_c': ve/299792458.0, 'departure_mass_kg': m0,
            'burnout_mass_kg': mf, 'expelled_kg': expelled, 'reserve_kg': mf-q['protected_and_operational_kg'],
            'reacted_dhe3_kg': reacted, 'reacted_he3_kg': reacted*share_he3, 'reacted_d_kg': reacted*(1-share_he3), 'lost_feed_kg': lost,
            'hydrogen_expelled_kg': expelled-reacted-lost, 'jet_energy_J': jet_J, 'fusion_energy_J': fusion_J,
            'peak_thrust_N': peak_F, 'peak_mass_flow_kg_s': peak_F/ve, 'peak_jet_power_W': peak_jet, 'peak_fusion_power_W': peak_fus,
            'absorbed_fraction': f_hot, 'peak_absorbed_heat_W': peak_hot, 'ideal_rejection_W': reject,
            'hot_budget_W': q['hot_share']*reject, 'hot_margin_W': q['hot_share']*reject-peak_hot,
            'other_hot_loads_allowance_W': (1-q['hot_share'])*reject, 'first_overload_s': over_s,
            'max_absorbed_fraction': q['hot_share']*reject/peak_fus}


def braking(s):
    """69_RETURN_BOUNDS restated at the operating point: what the post-burn reserve can do at the same ve (ideal, impulsive, no assists)."""
    b = burn(s); ve = b['exhaust_velocity_m_s']; m = b['burnout_mass_kg']; keep = p(s)['protected_and_operational_kg']
    dv_max = ve*math.log(m/keep); need_stop = m*(1-math.exp(-b['delta_v_m_s']/ve))
    return {'reserve_kg': b['reserve_kg'], 'reserve_dv_m_s': dv_max, 'stop_needs_kg': need_stop, 'stop_shortfall_kg': need_stop-b['reserve_kg'],
            've_to_stop_on_reserve_m_s': b['delta_v_m_s']/math.log(m/keep),
            'note': 'Ideal screen only (S&E 69): the 180 t reserve cannot stop the ship from 0.016 c at this ve; the return needs B04 '
                    '(trajectory, assists, replenishment) and is not part of the First Ignition operating point.'}


def check(s):
    """Reproduce the owner's case-E numbers (65) at f_hot = 1e-4, then require the operating point to close the hot loop."""
    q = p(s); fails = []
    e = burn(s, f_hot=q['owner_case_e_absorbed_fraction'])
    for key, want, tol in (('burnout_mass_kg', 1480000.0, 1.0), ('expelled_kg', 420000.0, 1.0), ('reacted_dhe3_kg', 274057.9504, 0.5),
                           ('lost_feed_kg', 3425.72438, 0.05), ('hydrogen_expelled_kg', 142516.3252, 0.5),
                           ('peak_fusion_power_W', 261265104138503.0, 1e6), ('peak_absorbed_heat_W', 26126510414.0, 1e3)):
        if abs(e[key]-want) > tol:
            fails.append(f'case E {key} {e[key]:.6g}, owner 65 gives {want:.6g}')
    b = burn(s)
    if b['hot_margin_W'] < 0:
        fails.append(f"operating point overloads the hot loop by {-b['hot_margin_W']/1e9:.2f} GW")
    if not (s['physics']['departure_mass']['lower_kg'] <= b['departure_mass_kg'] <= s['physics']['departure_mass']['upper_kg']):
        fails.append('departure mass outside the PROVISIONAL 1.5-2.0 kt envelope')
    if b['peak_thrust_N'] > s['propulsion']['design_thrust']['value']*1e6:
        fails.append('peak thrust above the structural design load')
    if not (s['physics']['propulsion_inventory']['lower_kg'] <= b['expelled_kg']+b['reserve_kg'] <= s['physics']['propulsion_inventory']['upper_kg']):
        fails.append('expelled + reserve outside the 300-600 t propulsion inventory')
    return fails


def report(s):
    return {'operating_point': burn(s), 'owner_case_e': burn(s, f_hot=p(s)['owner_case_e_absorbed_fraction']), 'braking': braking(s),
            'failures': check(s), 'status': p(s)['canon_status']}


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load
    out = report(load(ROOT)[0])
    OUTPUT.write_text(json.dumps(out, indent=1, default=float)+'\n')
    o = out['operating_point']
    print(f"ve {o['exhaust_velocity_m_s']/1e3:.0f} km/s ({o['exhaust_velocity_c']:.4f} c); {o['departure_mass_kg']/1e3:.0f} t -> {o['burnout_mass_kg']/1e3:.0f} t; "
          f"peak {o['peak_thrust_N']/1e6:.2f} MN, fusion {o['peak_fusion_power_W']/1e12:.1f} TW, absorbed {o['peak_absorbed_heat_W']/1e9:.2f} GW of "
          f"{o['ideal_rejection_W']/1e9:.2f} GW (margin {o['hot_margin_W']/1e9:.2f} GW); failures {out['failures']}")
