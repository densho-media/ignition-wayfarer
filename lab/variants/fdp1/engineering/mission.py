"""Four-burn mission timeline from the closure's burn list: engine time, coast, distances, and the round trip for given destinations.
The closure already integrates each burn at constant thrust with the mass falling (throttled at the 1.5 g cap); this module checks each
burn's delta-v against 0.016 c with the rocket equation and adds the coasts."""
import math

C = 299792458.0
DAY = 86400.0
YEAR = 365.25*DAY
AU = 1.495978707e11


def solve(cfg, r, distances_AU):
    ve = r['ve_km_s']*1e3; v_c = 0.016*C
    burns = []
    names = ['1 accelerate outbound', '2 brake at destination', '3 accelerate home', '4 brake at home']
    for i, b in enumerate(r['burns']):
        m0 = b['start_t']*1e3; m1 = m0-b['propellant_t']*1e3
        dv = ve*math.log(m0/m1)
        burns.append({'burn': names[i], 'start_mass_t': b['start_t'], 'end_mass_t': m1/1e3, 'propellant_t': b['propellant_t'],
                      'duration_days': b['days'], 'distance_AU': b['distance_AU'], 'accel_start_g': b['a_start_g'], 'accel_end_g': b['a_end_g'],
                      'delta_v_km_s': dv/1e3, 'delta_v_error': dv/v_c-1})
    d_out = (burns[0]['distance_AU']+burns[1]['distance_AU']); d_home = (burns[2]['distance_AU']+burns[3]['distance_AU'])
    d_min = max(d_out, d_home)
    t_engine = sum(b['duration_days'] for b in burns)*DAY
    trips = []
    for D in distances_AU:
        D_eff = max(D, d_min)
        coast_out = (D_eff-d_out)*AU/v_c; coast_home = (D_eff-d_home)*AU/v_c
        trips.append({'destination_AU': D_eff, 'requested_AU': D, 'engine_years': t_engine/YEAR, 'coast_years': (coast_out+coast_home)/YEAR,
                      'total_years': (t_engine+coast_out+coast_home)/YEAR})
    return {'cruise_speed_km_s': v_c/1e3, 'burns': burns, 'outbound_burn_distance_AU': d_out, 'return_burn_distance_AU': d_home,
            'minimum_destination_AU': d_min, 'engine_time_years': t_engine/YEAR, 'round_trips': trips,
            'minimum_round_trip_years': trips[0]['total_years'] if distances_AU and distances_AU[0] == 0 else None}
