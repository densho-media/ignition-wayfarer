"""Vertex 2.8: high-cosine magnetic-nozzle candidates for the protected four-engine Vertex (research, not canon).

    python3 work/vertex-2-8/nozzle.py        writes work/vertex-2-8/nozzle.json and nozzle.log (numpy; about 15-25 min)

Every candidate is judged in two regimes, because a pulsed D-3He burn is neither purely collective nor purely single-particle:
  collective  the pulse as a diamagnetic cavity that pushes the field out (nozzle_core.shell, energy-conserving, calibrated to the
              published hybrid-PIC 65 % at a 50 deg coil angle and E_B = 5 E_p); c = 1.0 is credited, c = 1.5 is the optimistic bound;
  single-ion  relativistic Boris tracing of the exhaust species in the vacuum field (nozzle_core.trace), with the impulse on each coil
              and the forward escapes followed to the ship's stern face.
Credit rule (robust design): kappa_credit = min(kappa_coll(c = 1.0), kappa_TP); forward stream = the larger of the two regimes.

Candidates (one engine; metres, +z aft, main coil R 10 m at z = 0):
  A   2.7 reference: one coil, B0 0.96 T, burn 2 R aft, pulse 192 MJ (the 2.6/2.7 rule: field energy inside R/2).
  B1  near-burn single coil: burn 0.6 R aft, E_B/E_p 70.
  B2  plugged near-burn: forward plug coil R 3 m at z -6 m plus the main coil (three variants).
  B3  collar/bell: B2b plus a coaxial collar R 11 m aft of the burn (tests a shaped expansion).
  C   adaptive: B2b with the burn displaced (r, z) and the pulse energy off its set-point, fixed versus retuned currents.
  D   speculative: the plug field a mirror would need to reach the SR-26F forward share.
"""
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nozzle_core as N  # noqa: E402

MU0 = N.MU0; C = N.C
R = 10.0
VE_C = 0.080                    # operating exhaust speed of the 2.7 levers point region (0.080-0.084 c); species energies follow it
SPINE = 200.0                   # research spine (D2)
SHIP = dict(z_face=-(31.93+SPINE), offset=24.0, R=45.0)
EP_RULE = lambda B0: B0*B0/(2*MU0)*4/3*math.pi*(R/2)**3          # 2.6/2.7 pulse-energy rule


def Icoil(B, Rc):
    return 2*Rc*B/MU0


def main(B0):
    return dict(I=Icoil(B0, R), R=R, z=0.0, a=0.15, fin=1.0, name='main')


def plug(B, Rp=3.0, zp=-6.0):
    return dict(I=Icoil(B, Rp), R=Rp, z=zp, a=0.2, fin=0.5, name='plug')


def collar(B, Rc=11.0, zc=14.0):
    return dict(I=Icoil(B, Rc), R=Rc, z=zc, a=0.15, fin=1.0, name='collar')


def mu_grid(n_fwd=200, n_rest=150, split=-0.5):
    """Fine cells near mu = -1 (the forward loss cone) and coarser elsewhere; returns centres and widths (dmu)."""
    e1 = np.linspace(-1.0, split, n_fwd+1); e2 = np.linspace(split, 1.0, n_rest+1)
    edges = np.concatenate([e1, e2[1:]])
    return 0.5*(edges[1:]+edges[:-1]), np.diff(edges)


def tp(coils, zb, src_r=0.0, n_phi=1, species=None):
    sp = species or N.species_set(VE_C, 'thermal', 0.95)
    mu, dmu = mu_grid() if n_phi == 1 else mu_grid(60, 40)
    if n_phi == 1:
        mus = list(mu); wcell = list(dmu)
    else:
        phis = (np.arange(n_phi)+0.5)*2*math.pi/n_phi
        mus = [(float(m), float(p)) for m in mu for p in phis]; wcell = [float(w)/n_phi for w in dmu for _ in phis]
    tr = N.trace(coils, zb, sp, mus, src_r=src_r, box=150.0, ship=SHIP)
    w = np.array([s['n'] for s in sp for _ in wcell])*np.array(wcell*len(sp))
    S = N.summarize(tr, coils, weights=w)
    # where the forward escapes cross the plug plane (can a dump in the plug throat take them?)
    fw = tr['status'] == 'FORWARD'
    r_end = np.hypot(tr['xf'][fw, 0], tr['xf'][fw, 1])
    S['forward_r_at_exit_m'] = [float(np.percentile(r_end, q)) for q in (50, 90)] if fw.any() else None
    return S


def coll(coils, zb, Ep, src_r=0.0, n=121):
    a = N.shell(coils, zb, Ep, n=n, compress=1.0, src_r=src_r)
    b = N.shell(coils, zb, Ep, n=n, compress=1.5, src_r=src_r)
    return a, b


def burn_field(coils, zb):
    Br, Bz, _ = N.field(coils, np.array([0.0]), np.array([float(zb)]))
    return float(math.hypot(Br[0], Bz[0]))


def axis_max(coils, z0, z1, n=400):
    zz = np.linspace(z0, z1, n); Br, Bz, _ = N.field(coils, np.zeros(n), zz)
    B = np.hypot(Br, Bz); i = int(np.argmax(B)); return float(B[i]), float(zz[i])


def evaluate(key, label, coils, zb, Ep=None, ratio=None, src_r=0.0, cls='future engineering', note='', tp_src=None):
    t0 = time.time()
    EB = N.stored_energy(coils)
    Ep = Ep if Ep is not None else EB/ratio
    a, b = coll(coils, zb, Ep, src_r=src_r)
    S = tp(coils, zb, src_r=tp_src or 0.0, n_phi=1 if not tp_src else 8)
    dmin = min(math.hypot(c['R'], c['z']-zb) for c in coils)
    Bb = burn_field(coils, zb); Bmax, zmax = axis_max(coils, zb-60.0, zb)
    k_credit = min(a['kappa'], S['kappa']) if a['fractions']['TRAPPED'] < 0.5 else 0.0
    fwd_coll = a['fractions']['FORWARD']
    fwd_credit = max(S['forward_on_ship'], fwd_coll)
    row = dict(key=key, label=label, cls=cls, note=note, zb_m=zb, coils=[dict(name=c['name'], R_m=c['R'], z_m=c['z'], I_MA=c['I']/1e6,
               B_centre_T=MU0*c['I']/(2*c['R'])) for c in coils], E_B_GJ=EB/1e9, E_p_MJ=Ep/1e6, EB_over_Ep=EB/Ep, d_min_m=dmin,
               coil_flux_vs_A=(22.36/dmin)**2, B_burn_T=Bb, B_plug_axis_T=Bmax, mirror_ratio=Bmax/Bb,
               loss_cone_forward=(1-math.sqrt(max(1-Bb/Bmax, 0.0)))/2,
               collective=dict(c1=dict(kappa=a['kappa'], fractions=a['fractions'], aft_cos=a['aft_cos'], field_impulse=a['field_impulse'],
                                       energy_check=a['energy_check']),
                               c15=dict(kappa=b['kappa'], fractions=b['fractions'], aft_cos=b['aft_cos'])),
               test_particle=S, kappa_credit=k_credit, forward_credit=fwd_credit, seconds=time.time()-t0)
    print(f"{key:5s} {label:44s} EB {EB/1e9:6.2f} GJ Ep {Ep/1e6:6.0f} MJ r {EB/Ep:5.0f} dmin {dmin:5.1f} Bb {Bb:5.2f} Rm {Bmax/Bb:6.1f} | "
          f"coll {a['kappa']:.3f}/{b['kappa']:.3f} trap {a['fractions']['TRAPPED']:.2f} | TP {S['kappa']:.3f} fwd {S['fractions']['FORWARD']:.4f} "
          f"ship {S['forward_on_ship']:.4f} coil {S['fractions']['COIL']:.4f} shares {[round(x, 2) for x in S['coil_impulse_share']]} "
          f"closure {S['closure']:+.3f} | credit k {k_credit:.3f} fwd {fwd_credit:.4f} ({time.time()-t0:.0f}s)", flush=True)
    return row


def run():
    out = dict(meta=dict(title='Vertex 2.8 nozzle candidates (research, not canon)', ve_c=VE_C, spine_m=SPINE, ship=SHIP,
                         credit_rule='kappa_credit = min(collective c=1.0, test-particle); forward = max of the two regimes',
                         calibration='single coil, 50 deg, E_B = 5 E_p: collective 0.633 vs hybrid PIC ~0.65 (Nagamine & Nakashima 1999)'),
               rows=[])
    rows = out['rows']
    add = lambda r: rows.append(r) or r
    # A: the 2.7 reference
    A = add(evaluate('A', '2.7 reference: one coil 0.96 T, burn 2R, 192 MJ', [main(0.96)], 2*R, Ep=EP_RULE(0.96), cls='established',
                     note='the 2.7 traced cosine 0.883 is the single-ion number'))
    # B1: near-burn single coil
    add(evaluate('B1', 'near-burn single coil 0.96 T, burn 0.6R, r70', [main(0.96)], 0.6*R, ratio=70))
    # B2: plugged near-burn
    add(evaluate('B2a', 'plug 5 T + main 0.96 T, burn 0.6R, r70', [plug(5.0), main(0.96)], 0.6*R, ratio=70))
    B2b = add(evaluate('B2b', 'plug 5 T + main 1.5 T, burn 0.9R, r70', [plug(5.0), main(1.5)], 0.9*R, ratio=70))
    add(evaluate('B2c', 'plug 12 T + main 0.96 T, burn 0.6R, r70', [plug(12.0), main(0.96)], 0.6*R, ratio=70))
    add(evaluate('B2d', 'plug 5 T + main 1.5 T, burn 0.9R, r150', [plug(5.0), main(1.5)], 0.9*R, ratio=150))
    # B3: collar / bell aft of the burn
    add(evaluate('B3a', 'B2b + collar R11 z14 0.5 T, r70', [plug(5.0), main(1.5), collar(0.5)], 0.9*R, ratio=70))
    add(evaluate('B3b', 'B2b + collar R11 z9 0.5 T, r35', [plug(5.0), main(1.5), collar(0.5, zc=9.0)], 0.9*R, ratio=35))
    # C: adaptive tolerance of B2b (fixed currents, the burn or the pulse off its set-point)
    co = [plug(5.0), main(1.5)]; EB = N.stored_energy(co); Ep0 = EB/70
    sens = []
    for lab, kw in (('pulse -30 % (r100), fixed currents', dict(Ep=0.7*Ep0)), ('pulse +30 % (r54), fixed currents', dict(Ep=1.3*Ep0)),
                    ('burn 1 m forward', dict(Ep=Ep0, zb=8.0)), ('burn 1 m aft', dict(Ep=Ep0, zb=10.0)),
                    ('burn 0.5 m off axis', dict(Ep=Ep0, src_r=0.5, tp_src=0.5)), ('burn 1.0 m off axis', dict(Ep=Ep0, src_r=1.0, tp_src=1.0))):
        zb = kw.pop('zb', 9.0)
        sens.append(evaluate('C', 'B2b ' + lab, co, zb, cls='future engineering (adaptive)', **kw))
    # retuned: currents scaled so E_B/E_p returns to 70 after a +30 % pulse (B ~ sqrt(E))
    s = math.sqrt(1.3)
    sens.append(evaluate('C', 'B2b pulse +30 %, currents retuned x1.14', [plug(5.0*s), main(1.5*s)], 9.0, Ep=1.3*Ep0, cls='future engineering (adaptive)'))
    out['adaptive'] = sens
    # D: what SR-26F (forward 2.4e-5 .. 2.4e-4) asks of a pure mirror plug
    Bb = B2b['B_burn_T']; need = {}
    for f in (2.4e-4, 2.4e-5):
        x = 1-2*f; Rm = 1/(1-x*x)
        need[f'{f:.1e}'] = dict(mirror_ratio=Rm, B_plug_T=Rm*Bb, note='single-ion loss cone; conductor practice ~20-45 T')
    out['speculative_plug'] = dict(B_burn_T=Bb, need=need)
    print('D     SR-26F by mirror alone:', {k: f"Rm {v['mirror_ratio']:.0f}, B_plug {v['B_plug_T']:.0f} T" for k, v in need.items()})
    return out


if __name__ == '__main__':
    import contextlib, io
    buf = io.StringIO()

    class Tee(io.TextIOBase):
        def write(self, s):
            sys.__stdout__.write(s); buf.write(s); return len(s)
    with contextlib.redirect_stdout(Tee()):
        o = run()
    (HERE/'nozzle.json').write_text(json.dumps(o, indent=1, default=float)+'\n')
    (HERE/'nozzle.log').write_text(buf.getvalue())
