"""Runaway departure study (NON-CANON): what a sustained automated pulse-control failure means in time, speed and distance for the
Vertex V4 ship, and whether the IGNITION 'about six years' (Y155 -> Y161) holds the 6.35-year minimum four-burn round trip.

Reads the committed Vertex Phase 4 result (lab/variants/vertex-drive/results/convergence.json, read only) and integrates each 0.016 c
burn at constant thrust with the mass falling, as the FDP-1 mission model does. Standard library only.
Run from the repository root: python3 lab/studies/runaway-departure/runaway.py [--json]"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONV = ROOT / 'lab/variants/vertex-drive/results/convergence.json'
OUT = Path(__file__).resolve().parent / 'results/runaway.json'

C = 299792458.0
G0 = 9.80665
DAY = 86400.0
YEAR = 365.25 * DAY
AU = 1.495978707e11
V_CRUISE = 0.016 * C


def burn(m0, thrust, ve, dv, steps=20000):
    """Constant-thrust burn of delta-v dv from mass m0: duration, end mass, distance, start/end acceleration."""
    mdot = thrust / ve
    m1 = m0 / math.exp(dv / ve)
    t = (m0 - m1) / mdot
    # distance travelled while the speed (relative to the burn start frame) goes 0 -> dv
    h = t / steps
    x = 0.0
    for i in range(steps):
        tm = (i + 0.5) * h
        x += ve * math.log(m0 / (m0 - mdot * tm)) * h
    return {'start_t': m0 / 1e3, 'end_t': m1 / 1e3, 'propellant_t': (m0 - m1) / 1e3, 'years': t / YEAR, 'days': t / DAY,
            'distance_AU': x / AU, 'a_start_g': thrust / m0 / G0, 'a_end_g': thrust / m1 / G0}


def mission(gen):
    s = gen['summary']
    F = s['thrust_MN'] * 1e6
    ve = s['ve_km_s'] * 1e3
    m = s['departure_t'] * 1e3
    burns = []
    for _ in range(4):
        b = burn(m, F, ve, V_CRUISE)
        burns.append(b)
        m = b['end_t'] * 1e3
    d_out = burns[0]['distance_AU'] + burns[1]['distance_AU']
    d_home = burns[2]['distance_AU'] + burns[3]['distance_AU']
    coast_home = (d_out - d_home) * AU / V_CRUISE / YEAR      # the minimum trip turns at the end of burn 2
    engine = sum(b['years'] for b in burns)
    return F, ve, s, burns, {'engine_years': engine, 'coast_home_years': coast_home, 'round_trip_years': engine + coast_home,
                             'turn_distance_AU': d_out, 'first_loop_years': burns[1]['years'] + burns[2]['years']}


def speed_after(t_s, m0, F, ve):
    return ve * math.log(m0 / (m0 - F / ve * t_s))


def distance_after(t_s, m0, F, ve, steps=2000):
    h = t_s / steps
    return sum(speed_after((i + 0.5) * h, m0, F, ve) * h for i in range(steps))


def main():
    conv = json.loads(CONV.read_text())
    gen = conv['generations']['V4']
    F, ve, s, burns, trip = mission(gen)
    m0 = s['departure_t'] * 1e3
    rate = s['pellet_rate_Hz']

    # 1. the runaway is burn 1: how long, how many pulses, where it ends
    runaway = dict(burns[0])
    runaway['pulses'] = rate * burns[0]['years'] * YEAR
    runaway['share_of_propellant'] = burns[0]['propellant_t'] / s['propellant_t']
    runaway['propellant_left_t'] = s['propellant_t'] - burns[0]['propellant_t']

    # 2. the decision window: when the ship outruns a rescue vehicle of a given delta-v
    #    (the rescue craft needs to match velocity and come back: about 2x the ship's speed for a return, so both are shown)
    window = []
    for dv_rescue_km_s in (10, 20, 50, 100):
        for factor, label in ((1.0, 'match only'), (2.0, 'match and return')):
            v_lim = dv_rescue_km_s * 1e3 / factor
            t = 0.0
            lo, hi = 0.0, burns[0]['years'] * YEAR
            for _ in range(60):
                mid = (lo + hi) / 2
                (lo, hi) = (mid, hi) if speed_after(mid, m0, F, ve) < v_lim else (lo, mid)
            t = hi
            window.append({'rescue_dv_km_s': dv_rescue_km_s, 'case': label, 'days': t / DAY,
                           'ship_speed_km_s': speed_after(t, m0, F, ve) / 1e3, 'distance_AU': distance_after(t, m0, F, ve) / AU})
    milestones = []
    for d in (1, 7, 30, 100, 365):
        t = d * DAY
        milestones.append({'day': d, 'speed_km_s': speed_after(t, m0, F, ve) / 1e3, 'distance_AU': distance_after(t, m0, F, ve) / AU,
                           'one_way_light_hours': distance_after(t, m0, F, ve) / C / 3600})

    # 3. the six-year question
    rt = trip['round_trip_years']
    gamma = 1 / math.sqrt(1 - 0.016 ** 2)
    calendar = {
        'round_trip_years': rt,
        'latest_departure_fraction_of_Y155_for_return_in_Y161': 1 - (rt - 6),
        'latest_departure_day_of_Y155': (1 - (rt - 6)) * 365.25,
        'max_repair_coast_at_0.016c_years_if_departure_at_start_of_Y155': (1 - (rt - 6)) / 2,
        'max_repair_coast_days_if_departure_at_start_of_Y155': (1 - (rt - 6)) / 2 * 365.25,
        'gamma_at_0.016c': gamma,
        'ship_clock_saving_hours_upper_bound': rt * YEAR * (1 - 1 / gamma) / 3600,
        'six_year_case_from_convergence': gen['six_year'],
    }

    # 4. 'self-reinforcing' cannot mean growing power: what an overdriven burn 1 would need to reach 6.0 y
    need = rt - 6.0
    k = burns[0]['years'] / (burns[0]['years'] - need) if need < burns[0]['years'] else None
    path_m = 68.4                                # V4 injection path (Phase 4 report, structural envelope)
    overdrive = {'saving_needed_years': need, 'power_factor_burn1': k, 'pulse_rate_Hz': rate * k,
                 'radiator_temperature_factor': k ** 0.25, 'warm_loop_K_from_628': 628 * k ** 0.25,
                 'one_target_in_flight_launcher_km_s': path_m * rate * k / 1e3,
                 'nominal_launcher_km_s': path_m * rate / 1e3}

    # 5. why a forced stop is fatal for V4: the tin droplet sheet freezes in about a second without heat input
    q = 2 * 0.9 * 5.670374419e-8 * 628.0 ** 4   # W/m2, both faces, eps 0.9 (Phase 4 warm-area check)
    sheet = 0.5                                   # kg/m2, V4 warm sheet (D-05 TARGET)
    cp_sn, l_sn, t_melt = 228.0, 59.2e3, 505.1    # tin: J/kg K (liquid), J/kg, K
    freeze = {'reject_W_m2_at_628K': q, 'seconds_to_melting_point': sheet * cp_sn * (628 - t_melt) / q,
              'seconds_to_solid': sheet * (cp_sn * (628 - t_melt) + l_sn) / q,
              'warm_area_km2': s['warm_km2'], 'sheet_inventory_t': sheet * s['warm_km2'] * 1e6 / 1e3}

    out = {'generation': 'V4', 'source': str(CONV.relative_to(ROOT)), 'thrust_MN': s['thrust_MN'], 've_km_s': s['ve_km_s'],
           'departure_t': s['departure_t'], 'pulse_rate_Hz': rate, 'burns': burns, 'trip': trip,
           'check_round_trip_vs_convergence': {'here': rt, 'convergence': s['min_round_trip_years']},
           'runaway_burn1': runaway, 'decision_window': window, 'burn1_milestones': milestones, 'calendar': calendar,
           'overdrive_to_6y': overdrive, 'forced_stop_freeze': freeze}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1) + '\n')
    if '--json' in sys.argv:
        print(json.dumps(out, indent=1))
    else:
        for b in burns:
            print(f"burn {b['years']:.3f} y  {b['propellant_t']:,.0f} t  {b['distance_AU']:,.0f} AU  {b['a_start_g']:.4f}-{b['a_end_g']:.4f} g")
        print('trip', {k2: round(v, 3) for k2, v in trip.items()}, 'convergence', round(s['min_round_trip_years'], 3))
        print('runaway', {k2: round(v, 4) if isinstance(v, float) else v for k2, v in runaway.items()})
        for w in window: print('window', w)
        for mm in milestones: print('milestone', mm)
        print('calendar', calendar)
        print('overdrive', overdrive)
        print('freeze', freeze)


if __name__ == '__main__':
    main()
