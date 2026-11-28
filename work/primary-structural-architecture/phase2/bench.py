"""Verification of fe.py against closed forms, with discretisation convergence. Writes results/p2_bench.json.

    python3 work/primary-structural-architecture/phase2/bench.py
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import fe  # noqa: E402

MAT = dict(E=70e9, G=26e9, rho=2700.0, alpha=23e-6)
L = 10.0
SEC = fe.tube(0.1, 0.005)
EI = MAT['E']*SEC['Iy']
mL = MAT['rho']*SEC['A']


def line(n, L=L, sec=SEC, mat=MAT):
    m = fe.Model(); ns = [m.node((L*i/n, 0, 0)) for i in range(n+1)]
    for i in range(n):
        m.beam(ns[i], ns[i+1], sec, mat)
    return m, ns


def rel(a, b):
    return abs(a-b)/abs(b)


def cantilever(n):
    m, ns = line(n); m.fix(ns[0]); P = 1000.0; m.load(ns[-1], (0, 0, -P))
    r = m.solve_static(); w = -r['u'][6*ns[-1]+2]
    return w, P*L**3/(3*EI)


def euler_pp(n):
    m, ns = line(n); m.fix(ns[0], [0, 1, 2, 3]); m.fix(ns[-1], [1, 2]); P = 1.0; m.load(ns[-1], (-P, 0, 0))
    r = m.solve_static(); N = [f['N'] if f else 0 for f in m.element_forces(r['u'])]
    lam = m.buckling(N)[0]
    return lam, math.pi**2*EI/L**2


def cantilever_freq(n):
    m, ns = line(n); m.fix(ns[0]); f, V, w2 = m.modes(k=2)
    return f[0], 1.875104**2/(2*math.pi)*math.sqrt(EI/(mL*L**4))


def freefree_freq(n):
    m, ns = line(n); f, V, w2 = m.modes(k=8)
    el = [x for x in f if x > 1e-3*max(f)]
    return el[0], 4.730041**2/(2*math.pi)*math.sqrt(EI/(mL*L**4)), int(sum(1 for x in f if x <= 1e-3*max(f)))


def beck(n):
    """Cantilever with a tangential (follower) end load: flutter at 20.05 EI/L^2 (Beck 1952)."""
    m, ns = line(n); m.fix(ns[0]); P = 1.0; m.thrust(ns[-1], (-P, 0, 0), follower=True)
    r = m.solve_static(); N = [f['N'] if f else 0 for f in m.element_forces(r['u'])]
    c = fe.critical(m, N, 1*EI/L**2, 40*EI/L**2, follower=True)
    return (c['lam']/(EI/L**2) if c['lam'] else None), 20.05, c['kind']


def beal(n):
    """Free-free uniform beam pushed by an end follower thrust (Beal 1965): instability at ~109.9 EI/L^2. The axial force comes
    from inertia relief, N(x) = -P (1 - x/L); the uniform mass carries the d'Alembert load."""
    m, ns = line(n); P = 1.0; m.thrust(ns[0], (P, 0, 0), follower=True)
    r = m.solve_static(inertia_relief=True)
    N = [f['N'] if f else 0 for f in m.element_forces(r['u'])]
    c = fe.critical(m, N, 1*EI/L**2, 200*EI/L**2, follower=True)
    return (c['lam']/(EI/L**2) if c['lam'] else None), 109.9, c['kind']


def inertia_relief(n):
    m, ns = line(n); P = 1000.0; m.load(ns[0], (P, 0, 0))
    r = m.solve_static(inertia_relief=True); fs = m.element_forces(r['u'])
    xm = [(i+0.5)/n*L for i in range(n)]; Nm = [f['N'] for f in fs]
    exact = [-P*(1-x/L) for x in xm]
    err = max(abs(a-b) for a, b in zip(Nm, exact))/P
    return err, float(r['accel']['lin'][0]), P/(mL*L)


def thermal(n):
    m, ns = line(n); m.fix(ns[0]); m.fix(ns[-1])
    for e in m.el:
        e['dT'] = 100.0
    r = m.solve_static(thermal=True); fs = m.element_forces(r['u'])
    sig = fs[0]['N']/SEC['A']; exact = -MAT['E']*MAT['alpha']*100
    m2, ns2 = line(n); m2.fix(ns2[0])
    for e in m2.el:
        e['dT'] = 100.0
    r2 = m2.solve_static(thermal=True); grow = r2['u'][6*ns2[-1]]
    m3, ns3 = line(n); m3.fix(ns3[0])
    for e in m3.el:
        e['dTz'] = 50.0
    r3 = m3.solve_static(thermal=True); tip = r3['u'][6*ns3[-1]+2]
    kappa = MAT['alpha']*50/(2*SEC['c']); tip_exact = kappa*L**2/2
    return dict(clamped_sigma=sig, clamped_exact=exact, free_growth=grow, growth_exact=MAT['alpha']*100*L, grad_tip=abs(tip), grad_exact=tip_exact)


def legacy_compare():
    """Same frame in src/wayfarer/fe_frame.py (Vertex 1.2 solver): a 3D portal with a lateral load."""
    sys.path.insert(0, str(H.parents[2] / 'src' / 'wayfarer'))
    import fe_frame
    pts = [(0, 0, 0), (0, 0, 5), (4, 0, 5), (4, 0, 0), (4, 3, 5)]
    old = fe_frame.Frame(); new = fe.Model()
    for p in pts:
        old.node(p); new.node(p)
    sec_o = fe_frame.tube(0.1, 0.1); sec_n = dict(A=sec_o['A'], Iy=sec_o['Iy'], Iz=sec_o['Iz'], J=sec_o['J'], c=sec_o['c'])
    for a, b in ((0, 1), (1, 2), (2, 3), (2, 4)):
        old.beam(a, b, sec_o, MAT['E'], MAT['G']); new.beam(a, b, sec_n, MAT)
    for n in (0, 3):
        old.fix(n); new.fix(n)
    old.load(4, F=(1000, 2000, -500)); new.load(4, (1000, 2000, -500))
    uo = old.solve()['u'][4][:3]; un = new.solve_static()['u'][24:27]
    return float(max(abs(a-b) for a, b in zip(uo, un))/max(abs(v) for v in uo))


def main():
    out = {}
    out['cantilever'] = [dict(n=n, value=w, exact=ex, err=rel(w, ex)) for n in (1, 2, 8) for w, ex in [cantilever(n)]]
    out['euler_pinned'] = [dict(n=n, value=v, exact=ex, err=rel(v, ex)) for n in (2, 4, 8, 16) for v, ex in [euler_pp(n)]]
    out['cantilever_f1'] = [dict(n=n, value=v, exact=ex, err=rel(v, ex)) for n in (2, 4, 8, 16) for v, ex in [cantilever_freq(n)]]
    out['freefree_f1'] = [dict(n=n, value=v, exact=ex, err=rel(v, ex), rigid_modes=k) for n in (4, 8, 16) for v, ex, k in [freefree_freq(n)]]
    out['beck_follower'] = [dict(n=n, value=v, exact=ex, err=rel(v, ex) if v else None, kind=k) for n in (4, 8, 16) for v, ex, k in [beck(n)]]
    out['beal_free_free_follower'] = [dict(n=n, value=v, exact=ex, err=rel(v, ex) if v else None, kind=c) for n in (8, 16, 24) for v, ex, c in [beal(n)]]
    out['inertia_relief'] = [dict(n=n, max_err_over_P=e, accel=a, accel_exact=ax) for n in (4, 16) for e, a, ax in [inertia_relief(n)]]
    out['thermal'] = thermal(8)
    out['legacy_fe_frame_rel_diff'] = legacy_compare()
    (H.parent / 'results').mkdir(exist_ok=True)
    (H.parent / 'results' / 'p2_bench.json').write_text(json.dumps(out, indent=1, default=float))
    for k, v in out.items():
        print(k, json.dumps(v, default=lambda x: round(float(x), 5))[:400])


if __name__ == '__main__':
    main()
