"""Vertex 2.11 Stern Mirror hold-off, transparency and grid-heat screen (research, not canon).

    python3 lab/studies/vertex-closure/vertex-2-11/screen.py       writes screen.json/.log (seconds)

Hold-off evidence used (engineering data, not Cranberg alone)
- H1 MeV negative-ion accelerators (JT-60 / ITER MAMuG, five 200 kV stages, 1 MV): 200 kV per stage was marginal at the 72 mm minimum gap
  and needed a longer gap and larger support-edge radii; large grids held below half of small uniform-field electrodes; sustainable
  voltage ~ sqrt(gap) (Hanada, Kashiwagi, Tobari et al., JAEA/IAEA FEC 2010-2014). Taken as E*V = 4e11 V^2/m at a stage with ~2 m^2 of
  grid area after long conditioning, with a beam.
- H2 area effect: E*V proportional to S^-0.33 for plane and coaxial electrodes up to 10 m^2 (QST 1 MV vacuum-insulation tests, clump
  model: breakdown when E*V reaches a constant; MeVArc 2019). Extrapolated here to the 100-6,000 m^2 of a stern-disk grid.
- H3 graded electrostatic-accelerator columns (Pelletron / tandem tubes): 1.5-2 MV/m average over tens of metres, but with small
  aperture electrodes (~0.1 m^2 each), so not an area-matched precedent.
- 2.10 used Cranberg V^2 = C d with C 1e13 V^2/m over the whole stack and no area effect.
Field on wires: inside the graded stack the grids sit at their natural potential (equal fields on both faces), so the wire surface field is
~2x the gap field (cylinder in a uniform field). A grid that terminates field lines (entrance, suppressor) carries a net line charge and
its wire surface field is (E_up + E_down)/(pi o) for opacity o = 2r/p; it is held below E_FE = 10 MV/m (design practice for conditioned
large-area electrodes; field emission and dark current rise steeply above it).
Grid heat: a radiatively cooled ribbon (emissivity eps, below 1,500 K so that thermionic emission from tungsten stays below ~1e-3 A/m^2)
has radiating area 2h/p per unit disk area and opacity o >= (h/p) tan(theta) for ions arriving at angle theta; its intercepted heat is
~o F with F the two-way kinetic-energy flux. Hence the condition F tan(theta) <= 2 eps sigma T^4, independent of the ribbon size.
"""
import json, math, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent

A_DISK = math.pi*45.0**2
EV_REF, S_REF, AREA_EXP = 4e11, 2.0, 0.33
BETA_INT = 2.0
E_FE = 10e6
SIGMA = 5.670374419e-8
F_PEN = 0.62          # energy-weighted share of the stack an ion of the thermal set penetrates (p 8.25/10, alpha 4.12/10)
K_E = 1.17            # secondary-electron heat per unit intercepted ion energy (PIC D210 thermal, f_esc 1: 0.088/0.075)


def ev_allow(o, frame_frac=0.01):
    S = math.pi*o*A_DISK+frame_frac*A_DISK
    return EV_REF*(S/S_REF)**-AREA_EXP, S


def stages_needed(V, L, o, law):
    if law == 'H1H2':
        EV, S = ev_allow(o)
        n = BETA_INT*V*V/(EV*L)
    elif law == 'cranberg_2.10':
        n = V*V/(1e13*L)                 # per stage V_s^2 = C d -> n L >= V^2/C
    elif law == 'column_H3':
        n = 0.0 if V/L <= 1.5e6 else math.inf
    return max(1, math.ceil(n)) if math.isfinite(n) else math.inf


def loss(n, o, o_term=0.01):
    ion = 1-(1-o)**(2*n*F_PEN)*(1-o_term)**4
    return ion, ion*(1+K_E)


def terminating_opacity(V_s, d_s, dV1, d1):
    return (V_s/d_s+(V_s+dV1)/d1)/(math.pi*E_FE)


def main():
    out = dict(meta=dict(EV_ref=EV_REF, S_ref=S_REF, area_exp=AREA_EXP, beta_int=BETA_INT, E_FE=E_FE, F_pen=F_PEN, K_e=K_E), rows=[])
    print('Hold-off screen, V_top 10 MV (thermal set) and 17 MV (unthermalized 14.7 MeV protons)')
    for V in (10e6, 17e6):
        for law in ('cranberg_2.10', 'H1H2'):
            for o in (0.001, 0.002, 0.005):
                for L in (8.0, 20.0, 40.0, 100.0):
                    n = stages_needed(V, L, o, law)
                    if not math.isfinite(n):
                        row = dict(V_MV=V/1e6, law=law, o=o, L=L, n=None)
                        out['rows'].append(row); continue
                    d = L/n; dV = V/n
                    # field-terminating grids (entrance, suppressor 0.75 MV) at opacity 0.005 get their own gaps d_t on both sides
                    o_t = 0.005
                    d_t = (2*0.75e6+dV)/(math.pi*E_FE*o_t)
                    li, lt = loss(n, o, o_t)
                    EV, S = ev_allow(o)
                    row = dict(V_MV=V/1e6, law=law, o=o, L=L, n=n, dV_kV=dV/1e3, d_m=d, grad_MV_m=V/L/1e6, o_terminating=o_t,
                               d_terminating_m=d_t, L_total_m=L+2*d_t, ion_loss=li, loss_with_secondaries=lt, S_m2=S, EV_allow=EV)
                    out['rows'].append(row)
                    print(f"V {V/1e6:4.0f} MV {law:14s} o {o:.3f} L {L:5.0f} m: n {n:4d} stages of {dV/1e3:6.0f} kV / {d:5.2f} m, "
                          f"+2 x {d_t:4.1f} m terminating gaps (total {L+2*d_t:5.1f} m), ion loss {li:.3f}, with secondaries {lt:.3f}")
    # hold-off factor by which the 2.10 design (10 stages x 0.8 m, o 0.005) exceeds H1+H2
    EV, S = ev_allow(0.005)
    stage = BETA_INT*(1.075e6)**2/0.8
    out['D210_overstress'] = dict(EV_stage=stage, EV_allow=EV, factor=stage/EV, S_m2=S)
    print(f"D210 (1.075 MV per 0.8 m stage, o 0.005): E*V on the wires {stage:.2e} vs allowed {EV:.2e} V^2/m (S {S:.0f} m^2): "
          f"x{stage/EV:.0f} beyond the large-area MeV-accelerator data (voltage per stage x{math.sqrt(stage/EV):.1f})")
    # suppressor of D210: wire surface field
    for o in (0.005, 0.01, 0.02):
        Es = (0.75e6/0.5+(0.75e6+1.075e6)/0.8)/(math.pi*o)
        out.setdefault('D210_suppressor', {})[o] = Es
        print(f"D210 suppressor wires o {o}: surface field {Es/1e6:.0f} MV/m (limit ~{E_FE/1e6:.0f})")
    # thermal condition for radiatively cooled entrance-region grids: F tan(theta) <= 2 eps sigma T^4
    th = {}
    for S_avg, tag in ((8.3e6, '10 %'), (25.5e6, '30 %')):
        for eps in (0.3, 0.8):
            for T in (1500.0, 2000.0):
                cap = 2*eps*SIGMA*T**4
                tmax = cap/(2*S_avg*1.1)
                th[f'{tag} eps{eps} T{T:g}'] = math.degrees(math.atan(tmax))
                print(f"grid heat {tag} ({S_avg/1e6:.1f} MW/m2 average, two-way {2.2*S_avg/1e6:.0f} MW/m2): eps {eps}, T {T:.0f} K -> "
                      f"radiative cooling works only for incidence spread below {math.degrees(math.atan(tmax)):.2f} deg")
    out['thermal_theta_max_deg'] = th
    # thermionic current from a tungsten ribbon (Richardson, A 6e5 A/m^2K^2, W 4.5 eV) times the stack voltage it falls through
    for T in (1500.0, 1800.0, 2000.0):
        J = 6e5*T*T*math.exp(-4.5/(8.617e-5*T))
        out.setdefault('thermionic_A_m2', {})[T] = J
        print(f"W thermionic emission at {T:.0f} K: {J:.2e} A/m2 of ribbon surface")
    return out


if __name__ == '__main__':
    import contextlib, io
    buf = io.StringIO()
    class Tee(io.TextIOBase):
        def write(self, s):
            sys.__stdout__.write(s); buf.write(s); return len(s)
    with contextlib.redirect_stdout(Tee()):
        o = main()
    (HERE/'screen.json').write_text(json.dumps(o, indent=1, default=str)+'\n'); (HERE/'screen.log').write_text(buf.getvalue())
