"""Correction 3.6: radiator backbone alternatives, one-dimensional sizing per metre of blade root (coordinate with ISSA thermal).

Load: the F1 hot-loop radiator line mass (ISSA H6a 565.2 t over 152.6 m, three blade planes) under the end-of-burn limit
acceleration x DLF, ultimate 1.4, carried between frames (4 m span) and accumulated to one axial anchor per 25.4 m section.
Options:
  A refractory backbone in the blade root (Nb-1Zr or C/C) at blade temperature: no thermal break, no heat leak, weak and heavy hot
  B isolated cool backbone (Al 6061 at 350 K) beside the hot root: MLI + standoffs; the radiative leak through MLI must be
    rejected by the cool loop (radiator area penalty)
  C segmented hot cells (4 m, the bay) on kinematic three-point mounts on a cool support: the hot cell shields the support; leak
    only through the mounts and the gaps
  D hybrid: SiC/SiC hot root ribs every 4 m carrying the cells to a cool Al backbone (C with stronger hot ribs, fewer mounts)
Every number is STUDY / PROTOTYPE; the formulas are in each function.
"""
import json
import math
from pathlib import Path

H = Path(__file__).resolve().parent
SIG = 5.670374e-8
LINE_T_PER_M = 565.2/152.6/3          # t/m per blade plane (F1, ISSA CP4 H6a incl. supports)
A_LIMIT = 21.770763e6/3.3e6*1.09      # end-of-burn limit acceleration (F1 end ~3.3 kt with PSA structure) x DLF
SPAN, SECTION = 4.0, 25.4
T_HOT, T_COOL, T_SINK = 1800.0, 350.0, 4.0


def tube_for(M, N, F, rho, rmax=0.35):
    """Lightest thin tube (r/t <= 40) carrying bending M and axial N at design stress F: returns kg/m and r."""
    best = None
    for i in range(1, 200):
        r = rmax*i/200; t = max(r/40, 0.002); A = 2*math.pi*r*t; S = math.pi*r*r*t
        if N/A + M/S <= F:
            m = rho*A
            if best is None or m < best[0]:
                best = (m, r, t)
    return best or (float('inf'), rmax, rmax/40)


def option(name, F, rho, hot, mounts_per_m, leak_area_m2_per_m, eps_eff, conduct_W_per_mount, note, alpha=None):
    w = LINE_T_PER_M*1e3*A_LIMIT*1.4          # N/m ultimate
    M = w*SPAN**2/8; N = w*SECTION
    kgm, r, t = tube_for(M, N, F*1e6, rho)
    leak = leak_area_m2_per_m*eps_eff*SIG*(T_HOT**4-T_COOL**4) + mounts_per_m*conduct_W_per_mount
    # cool-loop radiator to reject the leak at 350 K (two-sided panel, emissivity 0.85): area and mass at 5 kg/m2
    area = leak/(2*0.85*SIG*(T_COOL**4-T_SINK**4)); rad_kg = area*5.0
    growth = (alpha if alpha else (7.0e-6 if hot else 23.6e-6))*((T_HOT if hot else T_COOL)-290.0)*SECTION*1e3
    return dict(option=name, backbone_kg_per_m=kgm, r_m=r, t_mm=t*1e3, leak_W_per_m=leak, cool_radiator_m2_per_m=area, cool_radiator_kg_per_m=rad_kg,
                total_kg_per_m=kgm+rad_kg+mounts_per_m*1.5, growth_mm_per_section=growth, hot_structure=hot, note=note)


def main():
    out = [
        option('A refractory backbone (Nb-1Zr, 1800 K)', 60.0, 8570, True, 0.0, 0.0, 0.0, 0.0,
               'Nb-1Zr creep-limited ~60 MPa at 1800 K for 10^5 h (LIT order); growth absorbed by axial slides at the frames'),
        option('A2 refractory backbone (C/C, 1800 K)', 120.0, 1750, True, 0.0, 0.0, 0.0, 0.0,
               'C/C keeps strength hot; joints to the metallic frames need a thermal break anyway (at the frame, not along the length)', alpha=1.0e-6),
        option('B isolated cool backbone (Al, MLI)', 229.0, 2700, False, 1.0, 1.0, 0.01, 6.0,
               'MLI effective emittance 0.01 at 1800 K is optimistic (high-T MLI is refractory foil, e* 0.02-0.05); 1 zirconia standoff per metre'),
        option('C segmented hot cells on cool support', 229.0, 2700, False, 0.75, 0.08, 0.05, 6.0,
               'three mounts per 4 m cell; only the gaps (2 cm per side) and mount pads see the hot root; growth per cell 4 m only'),
        option('D hybrid: SiC/SiC ribs + cool Al backbone', 229.0, 2700, False, 0.25, 0.05, 0.05, 15.0,
               'one SiC/SiC rib per 4 m carries the cell; rib conduction larger but fewer paths'),
    ]
    for o in out:
        o['per_blade_plane_152m_t'] = o['total_kg_per_m']*152.6/1e3
        o['three_planes_t'] = 3*o['per_blade_plane_152m_t']
    (H.parent / 'results' / 'p2_backbone.json').write_text(json.dumps(dict(line_t_per_m=LINE_T_PER_M, a_limit=A_LIMIT, options=out), indent=1))
    for o in out:
        print(f"{o['option']:<44} backbone {o['backbone_kg_per_m']:6.1f} kg/m leak {o['leak_W_per_m']:7.0f} W/m cool rad {o['cool_radiator_m2_per_m']:6.2f} m2/m total {o['three_planes_t']:6.1f} t growth {o['growth_mm_per_section']:5.0f} mm")


if __name__ == '__main__':
    main()
