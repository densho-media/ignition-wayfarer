"""Vertex 2.8: speculative-coupling cases (candidate D) and robustness of the best credited closure (research, not canon).

    python3 work/vertex-2-8/robust.py        writes work/vertex-2-8/robust.json and robust.log (needs nozzle.json; about 3-5 min)

Reference: B2d (plugged near-burn nozzle, E_B/E_p 150, credited kappa 0.906) on the lever set (b 0.99, charge-mode spread, SR-26A x0.01)
with the restated forward requirement f_tail 0.01, JUSTIFIED dust, 200 m spine, +0.6 yr trip. One input at a time is moved to its
pessimistic band; then all together; then the reserve a credible design would carry.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mission28 as LG  # noqa: E402

MI = LG.MI


def main():
    s, S, Sx, vbc, lk, noz = MI.setup()
    LG.dust_justified(200.0)
    nzj = json.loads((HERE/'nozzle.json').read_text())
    rows = {r['key']: r for r in nzj['rows']}
    for r in rows.values():
        r['forward_credit_tp'] = r['test_particle']['forward_on_ship']; r['forward_coll'] = r['collective']['c1']['fractions']['FORWARD']
    ref = rows['B2d']; out = dict(cases={})

    def go(name, row=ref, Sxx=None, **kw):
        res = LG.case(Sxx or Sx, s, vbc, lk, row, **kw); out['cases'][name] = res
        print(f"{name:40s} {LG.short(res)}", flush=True)
        return res
    base = dict(f_tail=0.01)
    go('ref_B2d', **base)
    # D: bounded speculative coupling on the same hardware (stated levels, not traced)
    go('D_kappa0.95', kappa=0.95, **base, extra_spec=('SR-28K collective nozzle cosine 0.95 (not traced)',))
    go('D_kappa0.97', kappa=0.97, **base, extra_spec=('SR-28K collective nozzle cosine 0.97 (not traced)',))
    go('D_kappa0.97_tail0.001', kappa=0.97, f_tail=0.001, extra_spec=('SR-28K collective nozzle cosine 0.97 (not traced)',))
    go('D_tail0.001', f_tail=0.001)
    go('ref_trip1.0', trip=1.0, **base)
    go('D_kappa0.97_trip1.0', kappa=0.97, trip=1.0, **base, extra_spec=('SR-28K',))
    # robustness, one at a time (pessimistic band)
    go('R_kappa-0.03', kappa=ref['kappa_credit']-0.03, **base)
    go('R_iso_x1.5', iso=0.015, **base)
    go('R_tail_x3', f_tail=0.03)
    go('R_burnup_0.95_thermal', b=0.95, mode='thermal', **base)
    go('R_radiator_kg_x1.5', Sxx=dict(Sx, rad_kg_m2=Sx['rad_kg_m2']*1.5), **base)
    go('R_conductor_Je_x0.7', Sxx=dict(Sx, J_e=Sx['J_e']*0.7), **base)
    go('R_magnet_virial_x1.5', Sxx=dict(Sx, k_virial=Sx['k_virial']*1.5), **base)
    go('R_qmax_7MW', Sxx=dict(Sx, q_max=7e6), **base)
    go('R_tank_fraction_x1.2', Sxx=dict(Sx, f_tank=Sx['f_tank']*1.2), **base)
    go('R_dry_core_+5pct', Sxx=dict(Sx, core_kg=Sx['core_kg']*1.05), **base)
    go('R_all_pessimistic', kappa=ref['kappa_credit']-0.03, iso=0.015, f_tail=0.03,
       Sxx=dict(Sx, rad_kg_m2=Sx['rad_kg_m2']*1.5, J_e=Sx['J_e']*0.7, k_virial=Sx['k_virial']*1.5, f_tank=Sx['f_tank']*1.2, core_kg=Sx['core_kg']*1.05))
    # reserve a credible design carries: 10 % propellant reserve (delta-v x1.05 for all four burns) on the reference and on D 0.97
    go('reserve_dv_x1.05', Sxx=dict(Sx, dv=Sx['dv']*1.05), **base)
    go('D_kappa0.97_reserve_dv_x1.05', kappa=0.97, Sxx=dict(Sx, dv=Sx['dv']*1.05), **base, extra_spec=('SR-28K',))
    return out


if __name__ == '__main__':
    import contextlib, io
    buf = io.StringIO()

    class Tee(io.TextIOBase):
        def write(self, s):
            sys.__stdout__.write(s); buf.write(s); return len(s)
    with contextlib.redirect_stdout(Tee()):
        o = main()
    (HERE/'robust.json').write_text(json.dumps(o, indent=1, default=str)+'\n')
    (HERE/'robust.log').write_text(buf.getvalue())
