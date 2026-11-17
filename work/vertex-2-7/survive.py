"""Vertex 2.7: candidate C closed inside the JUSTIFIED dust envelope (research, not canon).

    python3 work/vertex-2-7/survive.py      writes work/vertex-2-7/survive.json and survive.log (needs dust.py, mission.py; ~2 min)

The stern annulus needs a 420 m bumper stand-off in JUSTIFIED (dust.py). Two ways to carry it: monolithic armour at today's 200 m spine,
or a spine long enough for the bumper (stand-off = spine - 50 m, the 2.6 rule). Both are closed on the 2.7 ledger (thermal velocity
spread, b 0.95, traced nozzle, SR-26A x0.03, SR-26F 2.4e-4) and on the lever set of gap.py.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dust as DU  # noqa: E402
import mission as MI  # noqa: E402
import fuel as FU  # noqa: E402
import protect as PR  # noqa: E402

DAY = 86400.0; C = 299792458.0


def main():
    just_env = dict(ipd_scale=2.0, kb_scale=3.0, kb_alpha=0.83, kb_mmax=1e-6, isd_rho=6.2e-24, isd_tail='EXTRAPOLATED')
    DU.add_case('JUSTIFIED', just_env, damage_from='HIGH')
    segs, _ = PR.mission(466.85*DAY, 0.072*C, None)
    s, S, Sx, vbc, lk, noz = MI.setup()
    out = {}
    for ext in (200.0, 300.0, 475.0, 600.0):
        m = DU.protection('JUSTIFIED', segs, ext-50.0)['total_t']
        MI._DUST[(ext, 'NOMINAL')] = m          # the solver reads its dust by (ext, case); JUSTIFIED is injected under the default key
        for name, b, kap, mode, iso, fwd in (('2.7_point', 0.95, None, 'thermal', 0.03, MI.F_FWD_MIN),
                                             ('levers', 0.99, 0.97, 'charge', 0.01, MI.F_FWD_MIN/10)):
            d = MI.design(vbc, Sx, lk, iso=iso, fwd=fwd, b=b)
            nz = MI.nozzle_set(noz, kap, FU.dispersion(FU.exhaust_species(b, 1.0, mode)))
            r = MI.solve(Sx, s, d, nz, ext, MI.VE_GRID, 0.6)
            x = r.get('best')
            out[f'{name}_ext{ext:g}'] = dict(ext=ext, dust_t=m, best=x)
            print(f"JUSTIFIED ext {ext:4.0f} m dust {m:6.0f} t {name:10s} {MI.short(x)}", flush=True)
    return out


if __name__ == '__main__':
    o = main()
    (HERE/'survive.json').write_text(json.dumps(o, indent=1, default=str)+'\n')
