"""Vertex 2.11 PIC benchmarks: single particle, Child-Langmuir, drift-space limiting current, energy/charge closure (research).

    python3 lab/studies/vertex-closure/vertex-2-11/bench.py      writes bench.json/.log
"""
import json, math, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import pic1d as P

QE, EPS0, MP = P.QE, P.EPS0, P.SPECIES['p'][0]


def jcl(V, d, m=MP, q=QE):
    return 4*EPS0/9*math.sqrt(2*q/m)*V**1.5/d**2


def cont(spec, S, tau, n_mac, seed=1):
    return P.make_injection(spec, S, tau, 2, n_mac, L_tof=0.0, tau_s=tau, seed=seed)


def main():
    out = {}
    t0 = time.time()
    # BM1 single particle (no space charge): 8.25 MeV p reflected by 10 MV; 14.7 MeV p reaches the plate
    els = [(0.0, 0.0, 1.0), (8.0, 10e6, 0.0)]
    for E in (8.25, 14.68):
        inj = P.make_injection(('mono', 'p', E), 1e6, 2e-6, 2, 200, L_tof=0.0, tau_s=1e-7)
        r = P.run(els, inj=inj, sc=False, boltz=False, sec=False, dx=0.01, tau_p=2e-6, n_per=1, t_end=4e-6, t_diag0=0.0)
        exp_heat = max(0.0, (E-10)/E); exp_el = 0.0 if E < 10 else 10/E
        out[f'BM1_p{E}'] = dict(reflect=r['reflect'], heat=r['heat'], electrical=r['electrical'], closure=r['closure'],
                                expected=dict(reflect=1.0 if E < 10 else 0.0, heat=exp_heat, electrical=exp_el))
        print(f"BM1 p {E} MeV vs 10 MV: reflect {r['reflect']:.6f} heat {r['heat']:.6f} (exp {exp_heat:.6f}) electrical "
              f"{r['electrical']:.6f} (exp {exp_el:.6f}) closure {r['closure']:.1e}", flush=True)
    # BM2 Child-Langmuir: cold protons (1 kV) into a 1 MV accelerating 1 m gap, driven at 0.5 and 2 J_CL
    V, d = 1e6, 1.0; J0 = jcl(V, d)
    els = [(0.0, 0.0, 1.0), (d, -V, 0.0)]
    for drive in (0.5, 2.0):
        for dx, nm in ((0.01, 20000), (0.005, 40000)):
            S = drive*J0*1e3          # W/m^2 at 1 keV per proton
            tau = 4e-6
            inj = cont(('mono', 'p', 1e-3), S, tau, nm)
            r = P.run(els, inj=inj, boltz=False, sec=False, dx=dx, tau_p=tau, n_per=1, t_end=2*tau, t_diag0=1.2*tau,
                      v_max=1.4e7)
            Jp = r['electrodes'][-1]['I_ion_A_m2']
            out[f'BM2_drive{drive}_dx{dx}'] = dict(J_plate_over_JCL=Jp/J0, closure=r['closure'], charge_closure=r['charge_closure'])
            print(f"BM2 CL drive {drive} dx {dx}: J_plate/J_CL {Jp/J0:.3f} (exp {min(drive, 1.0):.3f} +~1 % injection energy), "
                  f"closure {r['closure']:.1e}", flush=True)
    # BM3 drift space (both electrodes 0 V), 1 MeV protons: limit 8 J_CL(V0, d)
    V0, d = 1e6, 1.0; Jl = 8*jcl(V0, d)
    els = [(0.0, 0.0, 1.0), (d, 0.0, 0.0)]
    for drive in (0.9, 1.3):
        S = drive*Jl*1e6
        tau = 2e-6
        inj = cont(('mono', 'p', 1.0), S, tau, 40000)
        r = P.run(els, inj=inj, boltz=False, sec=False, dx=0.005, tau_p=tau, n_per=1, t_end=2*tau, t_diag0=1.2*tau)
        Jp = r['electrodes'][-1]['I_ion_A_m2']; Jin = drive*Jl
        out[f'BM3_drive{drive}'] = dict(transmitted=Jp/Jin, reflect=r['reflect'], closure=r['closure'])
        print(f"BM3 drift drive {drive} x 8 J_CL: transmitted {Jp/Jin:.3f} reflected {r['reflect']:.3f} (exp ~1 / partial) "
              f"closure {r['closure']:.1e}", flush=True)
    out['seconds'] = time.time()-t0
    return out


if __name__ == '__main__':
    import contextlib, io
    buf = io.StringIO()
    class Tee(io.TextIOBase):
        def write(self, s):
            sys.__stdout__.write(s); buf.write(s); return len(s)
    with contextlib.redirect_stdout(Tee()):
        o = main()
    (HERE/'bench.json').write_text(json.dumps(o, indent=1)+'\n'); (HERE/'bench.log').write_text(buf.getvalue())
