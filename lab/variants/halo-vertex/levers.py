"""Vertex 2.5: mass levers for Halo Vertex (research, not canon). Owner choice 2026-11-16 17:16Z: research the levers before 2.4.

  python3 lab/variants/halo-vertex/levers.py       writes lab/variants/halo-vertex/levers.json (ledger2.py closure; about 15 min on 4 cores)

Each lever alone on the 2.2 best case (1:1 feed, burnup 0.8, +0.6 yr), then combined. Lever values are brackets, each with its basis:
- burnup b 0.95: inertial burn fraction rho R / (rho R + H_B) at rho R several times H_B (LITERATURE ICF burn fraction; D-He3 H_B larger
  than D-T's 7 g/cm2), so b 0.95 needs about 20 H_B: a VBC requirement, not established;
- radiation-tolerant superconductor: REBCO fluence limit 1e22 -> 1e23 n/m2 (LITERATURE: REBCO degrades from about 3e22 at fusion
  spectra; annealing and defect-engineered tapes recover part) -> ADVANCED ENGINEERING;
- J_e x2 / x3: REBCO engineering current density 1-1.5e9 A/m2 at 20 K (LITERATURE thin-substrate tapes) -> ADVANCED ENGINEERING;
- channelling 0.95 (VBC, the speculative principle itself);
- ship dose credit: two more e-folds in the habitat water and stores (phi_ship x e^2) -> PROTOTYPE layout choice.
"""
import json
import math
import sys
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ledger2 as L2  # noqa: E402


def run(procs=4):
    vbc = json.loads((HERE/'vbc.json').read_text()); lk = L2.leakage(json.loads((HERE/'leak.json').read_text()))
    noz = [z for z in L2.nozzles(json.loads((HERE/'trace.json').read_text())) if z['z0'] >= 1.5 and z['BR'] >= 6.0]
    s = L2.spec.load(L2.ROOT)[0]; S0 = L2.L.shared(s)
    ship2 = dict(phi_ship=S0['phi_ship']*math.e**2)
    lev = {
        'base': ({}, {}),
        'burnup_095': (dict(b=0.95), {}),
        'fluence_1e23': ({}, dict(phi_lim=1e23)),
        'Je_x2': (dict(Je_factor=2.0), {}),
        'Je_x3': (dict(Je_factor=3.0), {}),
        'channel_095': (dict(channel=0.95), {}),
        'ship_credit_e2': ({}, ship2),
        'all_but_burnup': (dict(Je_factor=2.0, channel=0.95), dict(phi_lim=1e23, **ship2)),
        'all_advanced': (dict(b=0.95, Je_factor=2.0, channel=0.95), dict(phi_lim=1e23, **ship2)),
        'all_stretch': (dict(b=0.95, Je_factor=3.0, channel=0.95), dict(phi_lim=1e23, **ship2)),
        'all_stretch_trip03': (dict(b=0.95, Je_factor=3.0, channel=0.95), dict(phi_lim=1e23, **ship2)),
    }
    jobs = []
    for k, (dk, so) in lev.items():
        kw = dict(r=1.0, b=0.8); kw.update(dk)
        jobs.append((k, L2.design(vbc, **kw), noz, lk, 0.3 if 'trip03' in k else 0.6, so))
    with Pool(procs) as pool:
        res = dict(pool.map(L2.best, jobs))
    out = dict(levers={k: dict(design=v[0], shared=v[1]) for k, v in lev.items()}, results={})
    for name, d, *_ in jobs:
        x = res[name]; S = dict(S0); S.update(lev[name][1]); g = L2.gates(x, S, d)
        out['results'][name] = dict(result=x, gates=g)
        print(f"{name:20s} " + (f"dep {x['departure_t']:.0f} t, sys {x['system_t']:.0f} t, He-3 {x['he3_t']:.0f} t, ve {x['ve_c']:.3f} c, fusion {x['fusion_TW']:.1f} TW, "
                                f"trip +{x['trip_extra_yr']:.2f}, R {x['detail']['R_m']:.0f} m, I {x['detail']['I_MA']:.1f} MA, fin {x['engine_t']['ring_neutron_fin']:.0f} t, "
                                f"ship sh {x['engine_t']['ship_shadow_shield']:.0f} t" if x.get('closes') else 'no closure')
              + '  fails: ' + ','.join(k for k, v in g.items() if not v), flush=True)
    return out


if __name__ == '__main__':
    o = run()
    (HERE/'levers.json').write_text(json.dumps(o, indent=1, default=str)+'\n')
