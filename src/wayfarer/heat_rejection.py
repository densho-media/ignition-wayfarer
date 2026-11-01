"""F02 warm/cold loop architecture (pass 7, WORKING, Claude under the owner's delegation of 2026-10-31; S&E 15 OWN-F02-LOOPS-2026-10-31).

The AFT-010 screen (references/p1_thermal_loops.json) found that with the blades at 1800 K every warm candidate surface is
net-heated, and that with the blades dark the casing and candidate panels give 13.8 MW against a 15-30 MW normal warm band. This module
sizes the two-mode answer, keeping the three loops separate:
- burn (blades hot): the warm load is heat-pumped into the hot loop; work W = Q (T_hot / T_warm - 1) / eta_II from the drive's electric
  supply, and Q + W lands in the hot loop's 'other hot loads' allowance (operating_point.burn: ideal rejection - drive share);
- coast (blades dark): drain-back warm channels in the blade panels radiate at blade_warm_T_K over the blades' effective area;
- defense heat follows the cube of speed during the burn (dust kinetic-energy flux), so it is at full value only at burnout;
- cold loop: each ring's usable faces from the screen against the cold bound.
Standard library only.

    python3 src/wayfarer/heat_rejection.py      # prints the result and writes references/p1_heat_rejection.json
"""
import json
from pathlib import Path

import operating_point

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'references/p1_heat_rejection.json'
SCREEN = ROOT/'references/p1_thermal_loops.json'
SIGMA = 5.670374419e-8


def q(s):
    return s['thermal']['loops']['architecture']


def report(s, screen=None):
    a = q(s); L = s['thermal']['loops']; eps = L['warm']['example']['emissivity']
    Th = s['radiators']['temperature']['value']
    Tw = L['warm']['temperature_K']; eta = a['heat_pump_second_law_efficiency']
    b = operating_point.burn(s); allowance = b['ideal_rejection_W']-b['hot_budget_W']
    lo, hi = a['defense_normal_W']; fails = []
    burn = []
    for frac in (0.25, 0.5, 0.75, 1.0):                        # time fraction of the burn; speed fraction = time fraction (linear ramp)
        Q = a['burn_machinery_W']+hi*frac**3
        W = Q*(Th/Tw-1)/eta
        burn.append(dict(time_fraction=frac, warm_load_W=Q, pump_work_W=W, into_hot_loop_W=Q+W, share_of_allowance=(Q+W)/allowance))
    worst = burn[-1]
    if worst['into_hot_loop_W'] > allowance:
        fails.append('pumped warm heat exceeds the hot loop allowance for other loads')
    A = s['radiators']['effective_area']['value']; flux = eps*SIGMA*a['blade_warm_T_K']**4
    coast = dict(blade_effective_area_m2=A, flux_W_m2=flux, capacity_W=A*flux,
                 area_for_band_m2=[lo/flux, hi/flux], blade_fraction_for_band=[lo/(A*flux), hi/(A*flux)],
                 limited_duty_top_W=L['defense_routing']['limited_duty_W'][1], covers_limited_duty=A*flux >= L['defense_routing']['limited_duty_W'][1])
    if A*flux < hi:
        fails.append('blade warm channels cannot carry the top of the normal defense band')
    sc = json.loads((screen or SCREEN).read_text())
    cold_hp = sc['loops']['cold']['HIGH_POWER']['capacity_W']; cold_dark = sc['loops']['cold']['BLADES_NOT_RADIATING']['capacity_W']
    cold = dict(load_bound_W=a['cold_load_bound_W'], high_power_capacity_W=cold_hp, coast_capacity_W=cold_dark,
                high_power_usable_m2=sc['loops']['cold']['HIGH_POWER']['usable_area_m2'], margin_high_power=cold_hp/a['cold_load_bound_W']-1)
    if cold_hp < a['cold_load_bound_W']:
        fails.append('ring faces cannot carry the cold bound in HIGH_POWER')
    return dict(status=a['canon_status'], hot_T_K=Th, warm_T_K=Tw, hot_allowance_other_loads_W=allowance, burn=burn, coast=coast, cold=cold,
                short_burst='50-80 MW defense bursts exceed even the blades in coast: load shedding / Heat Debt (defense_routing), buffer OPEN',
                failures=fails)


def check(s):
    return report(s)['failures']


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load
    s = load()[0]; r = report(s)
    OUTPUT.write_text(json.dumps(r, indent=1)+'\n')
    print(json.dumps(r, indent=1, default=lambda x: round(x, 3)))
