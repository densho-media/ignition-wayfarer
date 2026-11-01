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


def mission(s):
    """The full return (owner choice 2026-10-31: keep 0.016 c, grow the ship): four equal burns of the First Ignition delta-v at ve
    (out-accelerate, arrive-brake, home-accelerate, home-brake) ending at the protected + operational ship. The tanks' dry mass grows with
    the capacity beyond today's inventory (physics.fuel_loads.tank_dry_fraction), so the end mass grows with the propellant."""
    q = p(s); ve = q['exhaust_velocity_m_s']; dv = first_ignition.result(s)['ramp_m_s3']*first_ignition.result(s)['time_s']**2/2
    R = math.exp(dv/ve); n = q['mission_burns']; f = s['physics']['fuel_loads']['tank_dry_fraction']
    end0 = q['protected_and_operational_kg']; p0 = q['legacy_inventory_kg']
    P = (R**n-1)*(end0-f*p0)/(1-(R**n-1)*f); end = end0+f*(P-p0); m0 = end+P
    masses = [m0/R**i for i in range(n+1)]
    return dict(burns=n, mass_ratio_per_burn=R, propellant_kg=P, end_mass_kg=end, added_tank_kg=f*(P-p0), departure_mass_kg=m0,
                burn_masses_kg=masses, burn_expelled_kg=[a-b for a, b in zip(masses, masses[1:])])


def power_cap_N(s):
    """The drive's thrust at its peak jet power: the B01 operating point's burnout thrust (1.5 g at the owner's case-E burnout mass). The
    full-return ship keeps this power, so its hot loop, nozzle and structure loads stay those of B01."""
    q = p(s); fi = first_ignition.result(s); dv = fi['ramp_m_s3']*fi['time_s']**2/2
    return q['owner_case_e_departure_mass_kg']*math.exp(-dv/q['exhaust_velocity_m_s'])*s['mission']['first_ignition']['max_accel']*G0


def burn(s, f_hot=None, steps=2000, profile=None, m0=None):
    """The First Ignition burn at the operating point (or with another absorbed fraction f_hot): totals, peaks and the hot-loop check.
    profile 'power_limited' (the flight, q.profile): constant thrust at the drive's power cap from the full-return departure mass.
    profile 'ramp': the owner's linear 0 to 1.5 g ramp (S&E 20/65, case E at 1.9 kt), kept as the reference and design-load case."""
    q = p(s); fi = first_ignition.result(s); a_max = s['mission']['first_ignition']['max_accel']*G0
    dv = fi['ramp_m_s3']*fi['time_s']**2/2; ve = q['exhaust_velocity_m_s']; eta = q['directed_efficiency']
    profile = profile or q['profile']; f_hot = q['absorbed_fraction'] if f_hot is None else f_hot
    if m0 is None:
        m0 = mission(s)['departure_mass_kg'] if profile == 'power_limited' else q['owner_case_e_departure_mass_kg']
    mf = m0*math.exp(-dv/ve); expelled = m0-mf
    jet_J = expelled*ve**2/2; fusion_J = jet_J/eta
    reacted = fusion_J/q['dhe3_specific_energy_J_kg']; lost = reacted/q['burnup']*(1-q['burnup'])*(1-q['recovery'])
    r = s['radiators']
    reject = thermal_budget.ideal_rejection_W(r['effective_area']['value'], r['emissivity']['value'], r['temperature']['value'])
    if profile == 'power_limited':
        peak_F = power_cap_N(s); T = expelled/(peak_F/ve); over_s = 0.0 if f_hot*peak_F*ve/2/eta > q['hot_share']*reject else None
        accel = [peak_F/m0/G0, peak_F/mf/G0]
        # distance: v(t) = ve ln(m0/m(t)), m = m0 - mdot t; integrate
        mdot = peak_F/ve; n = steps; x = 0.0
        for i in range(n):
            tm = T*(i+.5)/n; x += ve*math.log(m0/(m0-mdot*tm))*T/n
    else:
        T = fi['time_s']; peak_F = mf*a_max; accel = [0.0, a_max/G0]; x = fi['distance_m']
        over_s = None
        for i in range(steps+1):                  # time of first hot-loop overload along the ramp (absorbed heat grows as t exp(-v/ve))
            t = T*i/steps; a = a_max*t/T; v = a_max*t*t/(2*T); m = m0*math.exp(-v/ve)
            if f_hot*m*a*ve/2/eta > q['hot_share']*reject:
                over_s = t; break
    peak_jet = peak_F*ve/2; peak_fus = peak_jet/eta; peak_hot = f_hot*peak_fus
    share_he3 = q['he3_mass_share']
    return {'profile': profile, 'duration_s': T, 'duration_d': T/first_ignition.DAY_S, 'distance_AU': x/first_ignition.AU_M,
            'accel_g': accel, 'delta_v_m_s': dv, 'exhaust_velocity_m_s': ve, 'exhaust_velocity_c': ve/299792458.0, 'departure_mass_kg': m0,
            'burnout_mass_kg': mf, 'expelled_kg': expelled, 'reserve_kg': mf-q['protected_and_operational_kg'],
            'reacted_dhe3_kg': reacted, 'reacted_he3_kg': reacted*share_he3, 'reacted_d_kg': reacted*(1-share_he3), 'lost_feed_kg': lost,
            'hydrogen_expelled_kg': expelled-reacted-lost, 'jet_energy_J': jet_J, 'fusion_energy_J': fusion_J,
            'peak_thrust_N': peak_F, 'peak_mass_flow_kg_s': peak_F/ve, 'peak_jet_power_W': peak_jet, 'peak_fusion_power_W': peak_fus,
            'absorbed_fraction': f_hot, 'peak_absorbed_heat_W': peak_hot, 'ideal_rejection_W': reject,
            'hot_budget_W': q['hot_share']*reject, 'hot_margin_W': q['hot_share']*reject-peak_hot,
            'other_hot_loads_allowance_W': (1-q['hot_share'])*reject, 'first_overload_s': over_s,
            'max_absorbed_fraction': q['hot_share']*reject/peak_fus}


def species(s):
    """The full mission's propellant by species, in the B01 burn's proportions (reacted He-3 and D, the rest hydrogen with the lost feed)."""
    b = burn(s); P = mission(s)['propellant_kg']; k_he = b['reacted_he3_kg']/b['expelled_kg']; k_d = b['reacted_d_kg']/b['expelled_kg']
    return dict(helium_3=P*k_he, deuterium=P*k_d, hydrogen=P*(1-k_he-k_d))


def braking(s):
    """The return legs: each of the four burns' start mass and propellant, ending at the protected + operational ship (S&E 69 closed by
    the owner's choice to carry the return propellant)."""
    m = mission(s)
    return {'legs': ['out: accelerate', 'arrive: brake', 'home: accelerate', 'home: brake'], 'start_mass_kg': m['burn_masses_kg'][:-1],
            'expelled_kg': m['burn_expelled_kg'], 'end_mass_kg': m['end_mass_kg'],
            'note': 'Ideal, impulsive-equivalent, no assists or replenishment; each burn is power-limited at the B01 drive power.'}


def check(s):
    """Reproduce the owner's case-E numbers (65) on the 1.5 g ramp at f_hot = 1e-4, then require the flight to close the hot loop."""
    q = p(s); fails = []
    e = burn(s, f_hot=q['owner_case_e_absorbed_fraction'], profile='ramp')
    for key, want, tol in (('burnout_mass_kg', 1480000.0, 1.0), ('expelled_kg', 420000.0, 1.0), ('reacted_dhe3_kg', 274057.9504, 0.5),
                           ('lost_feed_kg', 3425.72438, 0.05), ('hydrogen_expelled_kg', 142516.3252, 0.5),
                           ('peak_fusion_power_W', 261265104138503.0, 1e6), ('peak_absorbed_heat_W', 26126510414.0, 1e3)):
        if abs(e[key]-want) > tol:
            fails.append(f'case E {key} {e[key]:.6g}, owner 65 gives {want:.6g}')
    b = burn(s); m = mission(s)
    if b['hot_margin_W'] < 0:
        fails.append(f"operating point overloads the hot loop by {-b['hot_margin_W']/1e9:.2f} GW")
    if not (s['physics']['departure_mass']['lower_kg'] <= b['departure_mass_kg'] <= s['physics']['departure_mass']['upper_kg']):
        fails.append('departure mass outside the departure_mass envelope')
    if b['peak_thrust_N'] > s['propulsion']['design_thrust']['value']*1e6:
        fails.append('peak thrust above the structural design load')
    if not (s['physics']['propulsion_inventory']['lower_kg'] <= m['propellant_kg'] <= s['physics']['propulsion_inventory']['upper_kg']):
        fails.append('mission propellant outside the propulsion inventory envelope')
    if abs(m['burn_masses_kg'][-1]-m['end_mass_kg']) > 1.0:
        fails.append('the four burns do not end at the protected + operational ship')
    return fails


def report(s):
    return {'operating_point': burn(s), 'mission': mission(s), 'species_kg': species(s), 'design_ramp_1_5g': burn(s, profile='ramp'),
            'owner_case_e': burn(s, f_hot=p(s)['owner_case_e_absorbed_fraction'], profile='ramp'), 'braking': braking(s),
            'failures': check(s), 'status': p(s)['canon_status']}


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load
    out = report(load(ROOT)[0])
    OUTPUT.write_text(json.dumps(out, indent=1, default=float)+'\n')
    o = out['operating_point']
    print(f"{o['profile']}: {o['duration_d']:.2f} d, {o['accel_g'][0]:.2f}-{o['accel_g'][1]:.2f} g, {o['distance_AU']:.2f} AU; mission {out['mission']['propellant_kg']/1e3:.0f} t propellant")
    print(f"ve {o['exhaust_velocity_m_s']/1e3:.0f} km/s ({o['exhaust_velocity_c']:.4f} c); {o['departure_mass_kg']/1e3:.0f} t -> {o['burnout_mass_kg']/1e3:.0f} t; "
          f"peak {o['peak_thrust_N']/1e6:.2f} MN, fusion {o['peak_fusion_power_W']/1e12:.1f} TW, absorbed {o['peak_absorbed_heat_W']/1e9:.2f} GW of "
          f"{o['ideal_rejection_W']/1e9:.2f} GW (margin {o['hot_margin_W']/1e9:.2f} GW); failures {out['failures']}")
