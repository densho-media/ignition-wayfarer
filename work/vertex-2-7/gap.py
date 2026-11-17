"""Vertex 2.7: the smallest remaining gaps to the canon 4.6 kt envelope inside the +0.6 yr trip gate (research, not canon).

    python3 work/vertex-2-7/gap.py      writes work/vertex-2-7/gap.json and gap.log (needs mission.py's inputs; ~1 min)
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mission as MI  # noqa: E402
import fuel as FU  # noqa: E402

C = MI.C


def run():
    s, S, Sx, vbc, lk, noz = MI.setup()
    out = {}
    rows = [('levers_thermal_0.6', 0.99, 0.97, 'thermal', 0.01, MI.F_FWD_MIN/10, 0.6),
            ('levers_charge_0.6', 0.99, 0.97, 'charge', 0.01, MI.F_FWD_MIN/10, 0.6),
            ('ideal_nozzle_charge_0.6', 0.99, 1.0, 'charge', 0.01, MI.F_FWD_MIN/10, 0.6),
            ('levers_charge_iso003_0.6', 0.99, 0.97, 'charge', 0.03, MI.F_FWD_MIN, 0.6),
            ('levers_charge_1.0', 0.99, 0.97, 'charge', 0.01, MI.F_FWD_MIN/10, 1.0)]
    for name, b, kap, mode, iso, fwd, trip in rows:
        d = MI.design(vbc, Sx, lk, iso=iso, fwd=fwd, b=b)
        nz = MI.nozzle_set(noz, kap, FU.dispersion(FU.exhaust_species(b, 1.0, mode)))
        r = MI.solve(Sx, s, d, nz, 200.0, MI.VE_GRID, trip)
        x = r.get('best')
        if x:
            X = math.exp(S['burns']*S['dv']/(x['ve_c']*C))-1
            end_allowed = S['dep_upper']/(1+X)/1e3
            x['gap'] = dict(departure_over_t=x['departure_t']-S['dep_upper']/1e3, end_allowed_t=end_allowed, end_over_t=x['end_t']-end_allowed,
                            system_cut_needed_t=(x['end_t']-end_allowed)*(1+S['f_tank']*X)/(1+S['f_tank']*X) if False else None,
                            he3_over_t=x['he3_t']-S['he3_canon_kg']/1e3, propellant_ok=x['propellant_t'] <= S['prop_upper']/1e3)
            # system mass that would close at fixed ve: end = core + sys + f_tank X end  ->  sys = end (1 - f_tank X) - core
            x['gap']['system_allowed_t'] = end_allowed*(1-S['f_tank']*X)-S['core_kg']/1e3
            x['gap']['system_cut_needed_t'] = x['system_t']-x['gap']['system_allowed_t']
        out[name] = dict(inputs=dict(b=b, kappa=kap, spread=mode, iso=iso, fwd=fwd, trip=trip, speculative=d['speculative']), best=x,
                         he3_min=r.get('he3_min'), curve=[dict(ve_c=c['ve_c'], departure_t=c['departure_t'], he3_t=c['he3_t'],
                                                               fusion_TW=c['fusion_TW'], propellant_t=c['propellant_t']) for c in r.get('curve', [])])
        print(f"{name:26s} {MI.short(x)}")
        if x:
            print(f"    over 4.6 kt by {x['gap']['departure_over_t']:.0f} t; system {x['system_t']:.0f} t vs allowed {x['gap']['system_allowed_t']:.0f} t "
                  f"(cut {x['gap']['system_cut_needed_t']:.0f} t); He-3 over canon by {x['gap']['he3_over_t']:.0f} t; propellant ok {x['gap']['propellant_ok']}")
        if r.get('he3_min'):
            print(f"    He-3 minimum: {MI.short(r['he3_min'])}")
    return out


if __name__ == '__main__':
    o = run()
    (HERE/'gap.json').write_text(json.dumps(o, indent=1, default=str)+'\n')
