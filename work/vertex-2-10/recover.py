"""Vertex 2.10 candidates B (Stern Mirror) and C (collector, propellant coupling): physics checks (research, not canon).

    python3 work/vertex-2-10/recover.py        writes work/vertex-2-10/recover.json and .log (~1 min)

B1 return paths: the forward escapes of the B2d_z12 nozzle are traced to the stern plane (ship frame: own engine 24 m off the ship axis,
   stern face 200 m forward of the engine fronts), reflected by a flat or faceted mirror (each engine's quarter tilted outward by alpha),
   and followed back to the engines' front plane: the share that strikes an engine envelope (r 11.44 m around the four engine axes)
   instead of passing the cluster aft, and the aft cosine of the rest.
B2 space charge: Child-Langmuir gap for the decelerating stack at the beam's peak current density; vacuum-breakdown margin (Cranberg
   V^2 = C d, C 1e13 V^2/m, total-voltage effect, large electrodes).
B3 electrons: the stream's electrons must be stopped by a suppressor before the ion stack; their energy share at T_e.
C1 propellant coupling: the gas column that stops the forward ions, the gas mass each pulse throws away and the exhaust speed it gets.
C2 collector survival: alpha implantation dose, sputtering erosion, area at 10 MW/m^2.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'vertex-2-8')); sys.path.insert(0, str(HERE))
import nozzle as Z  # noqa: E402
import nozzle_core as N  # noqa: E402
import forward as F  # noqa: E402

QE = 1.602176634e-19; MP = 1.67262192e-27; EPS0 = 8.8541878128e-12; C = 2.99792458e8; MEV = 1e6*QE
ENG_OFF = 24.0; Z_FRONT = -31.93; Z_STERN = -(31.93+200.0); A_ENV = 11.44; R_SHIP = 45.0
ENGINES = [(24.0, 0.0), (-24.0, 0.0), (0.0, 24.0), (0.0, -24.0)]


def landing(coils, zb):
    sp = N.species_set(Z.VE_C, 'thermal', 0.95)
    mu, dmu = Z.mu_grid()
    tr = N.trace(coils, zb, sp, list(mu), box=150.0, ship=Z.SHIP)
    w = np.array([s['n'] for s in sp for _ in dmu])*np.array(list(dmu)*len(sp))
    fw = np.where(tr['status'] == 'FORWARD')[0]
    W0 = float(np.sum(w*tr['E0']))
    return tr, w, fw, W0


def returns(tr, w, fw, W0, alphas=(0.0, 3.0, 6.0, 10.0), nphi=72):
    out = {}
    for al in alphas:
        hit = 0.0; ok = 0.0; cosw = 0.0; land = 0.0
        ta = math.tan(math.radians(al))
        for i in fw:
            x = tr['xf'][i]; u = tr['pf'][i]/np.linalg.norm(tr['pf'][i])
            if u[2] >= 0:
                continue
            for k in range(nphi):
                ph = (k+0.5)*2*math.pi/nphi; c, s = math.cos(ph), math.sin(ph)
                # own engine frame -> ship frame (own engine at (24, 0)), the source is axisymmetric so rotate the escape by ph
                px, py = x[0]*c-x[1]*s, x[0]*s+x[1]*c; ux, uy = u[0]*c-u[1]*s, u[0]*s+u[1]*c
                t = (Z_STERN-x[2])/u[2]
                P = np.array([ENG_OFF+px+ux*t, py+uy*t])
                if math.hypot(*P) > R_SHIP:
                    continue
                wt = w[i]*tr['E0'][i]/nphi; land += wt
                # facet normal of the quarter that P lies in: tilted outward (toward the quarter's engine direction) by alpha
                q = max(ENGINES, key=lambda e: e[0]*P[0]+e[1]*P[1]); nq = np.array(q)/24.0
                n = np.array([nq[0]*ta, nq[1]*ta, -1.0]); n /= np.linalg.norm(n)      # normal pointing aft (toward the engines)
                v = np.array([ux, uy, u[2]]); vr = v-2*np.dot(v, n)*n
                if vr[2] <= 0:
                    continue
                tb = (Z_FRONT-Z_STERN)/vr[2]; R = P+vr[:2]*tb
                if any(math.hypot(R[0]-ex, R[1]-ey) < A_ENV for ex, ey in ENGINES):
                    hit += wt
                else:
                    ok += wt; cosw += wt*vr[2]
        out[f'{al:g}'] = dict(landed_share=land/W0, strike_engines=hit/max(land, 1e-30), pass_aft=ok/max(land, 1e-30),
                              aft_cos=cosw/max(ok, 1e-30))
    return out


def space_charge(P_fwd_W, Eq_V=8.25e6, duty=0.05, A=math.pi*45**2/4, m=MP, q=QE):
    I = P_fwd_W/Eq_V; J = I/A/duty
    d = math.sqrt(4*EPS0/9*math.sqrt(2*q/m)*Eq_V**1.5/J)
    Vbd = math.sqrt(1e13*d)
    return dict(I_avg_kA=I/1e3, J_peak_A_m2=J, gap_m=d, gradient_MV_m=Eq_V/d/1e6, V_breakdown_MV=Vbd/1e6, margin=Vbd/Eq_V)


def stopping_column():
    """Proton 8.25 MeV and alpha 8.25 MeV ranges in hydrogen (Bethe-Bloch integrated, I = 19.2 eV), g/cm^2."""
    def dEdx(E, m, z):            # MeV cm^2/g in H (Z/A = 1)
        g = 1+E/(m*931.494); b2 = 1-1/g**2
        K = 0.307075; I = 19.2e-6; me = 0.511
        Tm = 2*me*b2*g*g/(1+2*g*me/(m*931.494)+(me/(m*931.494))**2)
        return K*z*z*1.0/b2*(0.5*math.log(2*me*b2*g*g*Tm/I**2)-b2)
    out = {}
    for nm, m, z in (('p', 1.00728, 1), ('alpha', 4.00151, 2)):
        E = 8.25; R = 0.0; dE = 0.01
        while E > 0.05:
            R += dE/dEdx(E, m, z); E -= dE
        out[nm] = R
    return out


def main():
    co = [F.coil(5.0, 3.0, -6.0, 'plug'), F.M15]
    tr, w, fw, W0 = landing(co, 12.0)
    res = dict(B1_returns=returns(tr, w, fw, W0))
    for k, v in res['B1_returns'].items():
        print(f"B1 facet tilt {k:>3s} deg: landed {v['landed_share']:.4f} of pulse; of it strikes engines {v['strike_engines']:.3f}, "
              f"passes aft {v['pass_aft']:.3f} (aft cos {v['aft_cos']:.3f})")
    # per engine, ledger B_mirror tail 0.3 / 0.1: fusion ~30.9 / 30.1 TW, forward share 5.2e-3 / 1.7e-3 of the plasma (~0.99 of fusion)
    sc = {}
    for t, Pf, f in (('tail1', 30.0e12, 1.75e-2), ('tail0.3', 30.9e12, 5.25e-3), ('tail0.1', 30.1e12, 1.75e-3)):
        Pfwd = f*Pf/4
        sc[t] = dict(P_fwd_GW=Pfwd/1e9, proton=space_charge(Pfwd), alpha=space_charge(Pfwd, Eq_V=4.12e6, m=4*MP, q=2*QE))
        x = sc[t]['proton']
        print(f"B2 {t}: forward {Pfwd/1e9:.1f} GW/engine, I {x['I_avg_kA']:.1f} kA avg, J peak {x['J_peak_A_m2']:.0f} A/m2 (5 % duty), "
              f"CL gap {x['gap_m']:.2f} m, {x['gradient_MV_m']:.1f} MV/m, Cranberg breakdown {x['V_breakdown_MV']:.1f} MV (margin {x['margin']:.2f})")
    res['B2_space_charge'] = sc
    # electrons: quasi-neutral stream, one electron per charge; energy share kT_e / (E/q) per charge
    res['B3_electrons'] = {f'Te {Te:g} keV': Te*1e3/5.5e6 for Te in (10, 100, 300)}
    print('B3 electron energy share of the forward stream:', {k: round(v, 4) for k, v in res['B3_electrons'].items()},
          '-> suppressor at -(3-5) kT_e/e, i.e. -0.05 .. -1.5 MV')
    # C1 propellant coupling
    rng = stopping_column()
    Ep = 134e6; rate = 30e12/4/Ep
    c1 = {}
    for t, f in (('tail0.3', 5.25e-3), ('tail0.1', 1.75e-3), ('tail0.01', 1.75e-4)):
        Ef = f*Ep
        for A in (10.0, 100.0):
            m_pulse = rng['p']*10*A                    # g/cm^2 -> kg/m^2 x area
            v = math.sqrt(2*Ef/m_pulse)
            c1[f'{t}_A{A:g}'] = dict(E_fwd_kJ=Ef/1e3, gas_kg_per_pulse=m_pulse, gas_t_per_s=m_pulse*rate/1e3, gas_exhaust_km_s=v/1e3,
                                     gas_kt_per_burn=m_pulse*rate*467*86400/1e6)
    res['C1_propellant_coupling'] = dict(range_g_cm2=rng, pulse_rate_Hz=rate, cases=c1)
    print(f"C1 ranges in H: p {rng['p']:.3f}, alpha {rng['alpha']:.4f} g/cm2; pulse rate {rate:.0f} Hz/engine")
    for k, v in c1.items():
        print(f"   {k:14s} {v['E_fwd_kJ']:7.1f} kJ fwd/pulse -> {v['gas_kg_per_pulse']:.0f} kg gas/pulse ({v['gas_t_per_s']:.0f} t/s, "
              f"{v['gas_kt_per_burn']:.0e} kt/burn), gas exhaust {v['gas_exhaust_km_s']:.2f} km/s")
    # C2 collector survival (tail 0.1, collector at 10 MW/m^2): alpha implantation dose and sputter erosion over four 467 d burns
    Pfwd = 1.75e-3*30.1e12/4; A = Pfwd/10e6; alpha_rate = 0.475*Pfwd/(8.25*MEV)
    dose = alpha_rate*4*467*86400/A
    sput = alpha_rate*1e-4*183.84*1.6605e-27*4*467*86400   # yield ~1e-4 W atoms per MeV alpha (order of magnitude)
    res['C2_collector'] = dict(P_fwd_GW=Pfwd/1e9, area_m2=A, area_fits_stern_quarter=A <= math.pi*45**2/4, alpha_dose_m2=dose,
                               blister_threshold_m2=1e21, W_sputter_kg=sput)
    print(f"C2 tail 0.1: {Pfwd/1e9:.1f} GW/engine on {A:.0f} m2 (stern quarter {math.pi*45**2/4:.0f} m2); He dose {dose:.1e} /m2 vs blistering "
          f"~1e21 /m2 -> a solid face blisters unless hot (>2000 K) or liquid; W sputtering ~{sput:.1f} kg over the mission")
    (HERE/'recover.json').write_text(json.dumps(res, indent=1, default=float)+'\n')


if __name__ == '__main__':
    import contextlib, io
    buf = io.StringIO()

    class Tee(io.TextIOBase):
        def write(self, s):
            sys.__stdout__.write(s); buf.write(s); return len(s)
    with contextlib.redirect_stdout(Tee()):
        main()
    (HERE/'recover.log').write_text(buf.getvalue())
