"""Vertex 2.11 Stern Mirror PIC cases: designs x spectra x single-ion share, sensitivities and convergence (research, not canon).

    python3 lab/studies/vertex-closure/vertex-2-11/cases.py [set]     sets: main, sens, conv (default all); writes cases_<set>.json/.log

Per engine the forward stream lands on one quarter of the r 45 m stern disk (1,590 m^2). Single-ion share (SR-26F quantity) 10 %:
13.2 GW per engine = 8.3 MW/m^2 average; 30 %: 40.6 GW = 25.5 MW/m^2 (Vertex 2.10 B2, A1 nozzle B2d_z12, forward 1.75 % of each pulse).
"""
import json, sys, time
from multiprocessing import Pool
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import pic1d as P

S10, S30 = 8.3e6, 25.5e6
DESIGNS = {
    # 2.10 Stern Mirror as described: 10 MV, ten 0.8 m stages (1.34 MV/m), ribbon grids 0.5 % opaque
    'D210': dict(V_top=10e6, n_stage=10, d_stage=0.8, T=0.995),
    'D210_o1': dict(V_top=10e6, n_stage=10, d_stage=0.8, T=0.999),
    # hold-off compliant on large-area MeV-accelerator data (screen.py): 53 stages of 0.2 MV over 40 m, 0.1 % grids, long suppressor
    # gaps with 1 % grids so the field-terminating grids stay near 10 MV/m on the wire surface
    'DBD': dict(V_top=10e6, n_stage=53, d_stage=0.75, T=0.999, V_s=0.75e6, d_s=10.0, T_supp=0.99, T_entr=0.99),
    # fully hold-off compliant on H1+H2 (screen.py): 18 stages of 0.56 MV over 100 m, 0.1 % grids, 13 m terminating gaps at 0.5 %
    'DBD100': dict(V_top=10e6, n_stage=18, d_stage=5.56, T=0.999, V_s=0.75e6, d_s=13.0, T_supp=0.995, T_entr=0.995),
    # 17 MV for unthermalized 14.7 MeV protons
    'D17': dict(V_top=17e6, n_stage=17, d_stage=0.8, T=0.995),
}


def job(a):
    name, design, kw = a
    els = P.stack(**DESIGNS[design])
    t = time.time()
    r = P.run(els, **kw)
    r['seconds'] = time.time()-t; r['name'] = name; r['design'] = design; r['design_params'] = DESIGNS[design]
    r['kw'] = {k: (v if not isinstance(v, tuple) else list(v)) for k, v in kw.items()}
    return r


def plan(which):
    J = []
    if which in ('main', 'all'):
        for d in ('D210', 'D210_o1', 'DBD'):
            for tag, S in (('10', S10), ('30', S30)):
                for sp in ('thermal', 'thermal_broad', 'charge', 'birth'):
                    dx = 0.02 if d == 'DBD' else 0.01
                    J.append((f'{d}_{sp}_{tag}', d, dict(spec=sp, S_W_m2=S, dx=dx, n_mac=50000)))
        for tag, S in (('10', S10), ('30', S30)):
            J.append((f'D17_birth_{tag}', 'D17', dict(spec='birth', S_W_m2=S, dx=0.01, n_mac=50000)))
    if which in ('sens', 'all'):
        base = dict(spec='thermal', S_W_m2=S10, dx=0.01, n_mac=50000)
        for nm, kw in (('Yp0.3', dict(Yp=0.3)), ('Yp3', dict(Yp=3.0)), ('fesc0.3', dict(f_esc=0.3)), ('fesc0.1', dict(f_esc=0.1)),
                       ('nosec', dict(sec=False)), ('Te100', dict(Te=100e3)), ('floc2', dict(S_W_m2=2*S10)),
                       ('tau_s0.3', dict(tau_s=0.3e-6)), ('photo', dict(ph_rate=3e15))):
            J.append((f'sens_D210_{nm}', 'D210', dict(base, **kw)))
        DESIGNS['D210_Vs1.5'] = dict(DESIGNS['D210'], V_s=1.5e6)
        J.append(('sens_D210_Te100_Vs1.5', 'D210_Vs1.5', dict(base, Te=100e3)))
    if which in ('bd100', 'all'):
        for tag, S in (('10', S10), ('30', S30)):
            for sp in ('thermal', 'charge'):
                J.append((f'DBD100_{sp}_{tag}', 'DBD100', dict(spec=sp, S_W_m2=S, dx=0.02, n_mac=50000)))
    if which in ('conv', 'all'):
        base = dict(spec='thermal', S_W_m2=S30)
        for nm, kw in (('dx2', dict(dx=0.02, n_mac=50000)), ('dx1', dict(dx=0.01, n_mac=50000)), ('dx0.5', dict(dx=0.005, n_mac=50000)),
                       ('n25k', dict(dx=0.01, n_mac=25000)), ('n200k', dict(dx=0.01, n_mac=200000)),
                       ('cfl0.25', dict(dx=0.01, n_mac=50000, cfl=0.25)), ('seed2', dict(dx=0.01, n_mac=50000, seed=2)),
                       ('nper3', dict(dx=0.01, n_mac=50000, n_per=3))):
            J.append((f'conv_D210_{nm}', 'D210', dict(base, **kw)))
    return J


def line(r):
    e = r['electrodes']
    hot = max(e[:-1], key=lambda x: x['heat_W_m2'])
    sp = r['species']
    return (f"{r['name']:28s} L {r['L_m']:5.1f} m | reflect {r['reflect']:.3f} heat {r['heat']:.3f} (ion {r['heat_ion']:.3f}, "
            f"e- {r['heat_elec']:.3f}) elec {r['electrical']:+.3f} (ion {r['electrical_ion']:+.3f}, e- {r['electrical_elec']:+.3f}) "
            f"esc {r['e_escape_up']:.4f} | plate {e[-1]['heat_W_m2']/1e6:.2f} MW/m2, hottest grid {hot['heat_W_m2']/1e3:.0f} kW/m2 "
            f"at x {hot['x']:.1f} | Esurf max {max(max(x['Esurf_up_MV_m'], x['Esurf_dn_MV_m']) for x in e):.2f} MV/m "
            f"(vac {max(x['E_vac_MV_m'] for x in e):.2f}) | phimax {r['phi_max_window_MV']:.2f} | sec/ion {r['sec_per_ion']:.3f} | "
            f"p refl {sp.get('p', {}).get('reflect', 0):.3f} | closure {r['closure']:.1e} | {r['seconds']:.0f} s")


def main(which):
    J = plan(which)
    with Pool(4) as pool:
        res = []
        for r in pool.imap(job, J):
            print(line(r), flush=True); res.append(r)
    for r in res:
        r.pop('phi_end_MV', None)
        ts = r['ts']; k = max(1, len(ts['ref'])//400)
        r['ts'] = {kk: (v[::k] if isinstance(v, list) else v) for kk, v in ts.items()}
    return res


if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'all'
    import contextlib, io
    buf = io.StringIO()
    class Tee(io.TextIOBase):
        def write(self, s):
            sys.__stdout__.write(s); buf.write(s); return len(s)
    with contextlib.redirect_stdout(Tee()):
        o = main(which)
    (HERE/f'cases_{which}.json').write_text(json.dumps(o, indent=0, default=float)+'\n')
    (HERE/f'cases_{which}.log').write_text(buf.getvalue())
