"""Revision 4 §6: S5 tank-stretch spine, beam finite-element check (T00, research only, NON-CANON).

  python3 lab/variants/vertex-drive/studies/rev4/spine.py      # writes results/spine.json (seconds; numpy)

This is a 1D Timoshenko BEAM model (bending, shear through the lacing, axial), not a shell or solid FEA. Members are smeared into section
properties; frames, saddles and longeron bays are checked with closed-form local models. The stretch runs from J1 (X 140.75 m) to J3
(X 416.15 m), 275.4 m in 9 bays, element length 7.65 m (one frame pitch). Masses are T05 Rev 3 bay masses (stretch key of rev3.json, read
from the T05 branch at the commit named below), lumped at frame nodes; the aft ship is a lumped mass at J1 and the bow at J3.

Geometries (T05):
  N6_drawn   six longerons, tube r 0.29 m, at R 34.8 m (Rev 3 as drawn; T05 found its own stiffness was undercounted 6x)
  N6_fixed   six longerons, r 0.76 m, at R 34.8 m (T05 corrected for 0.2 Hz)
  N9_gaps    nine longerons in the inter-tank gaps, r 0.52 m, at R 31 m (T05 Rev 4 proposal)
  S2         canon sectors only (spine + three keels), for reference
Each has the S2 spine and keels, ring frames every 7.65 m and diagonal lacing (PROTOTYPE, area 0.25 of a longeron) in every bay panel.
"""
import json
import math
import subprocess

import numpy as np

from common import G0, write_json, VX

T05_REF = 'origin/claude/project-thread-ctwplp:work/vertex-blender/rev3.json'
E = 120e9; RHO = 1700.0; SIG = 600e6; SF = 2.0; SPLICE = 0.8; ALLOW = SIG / SF * SPLICE
G_LAT = (0.002, 0.01)
F_TARGET = 0.2
PULSE = 195.73784854631526


def t05():
    raw = subprocess.run(['git', 'show', T05_REF], capture_output=True, text=True, cwd=VX, check=True).stdout
    return json.loads(raw)


def tube(r, t_over_r=0.1):
    t = r * t_over_r
    A = math.pi * (r ** 2 - (r - t) ** 2); I = math.pi / 4 * (r ** 4 - (r - t) ** 4)
    return A, I


GEOMS = {'S2': (0, 0.0, 0.0), 'N6_drawn': (6, 34.8, 0.29), 'N6_fixed': (6, 34.8, 0.76), 'N9_gaps': (9, 31.0, 0.52)}
KEEL = (3, 5.0, 0.3914157237254803, 0.019570786186274017)      # n, R, r, t (S2 keels, rev3.json)
SPINE = (0.95, 0.006)


def section(n, R, r):
    """EI, GA (lacing), EA, mass per metre (structure) of one geometry."""
    A_sp = math.pi * (SPINE[0] ** 2 - (SPINE[0] - SPINE[1]) ** 2); I_sp = math.pi / 4 * (SPINE[0] ** 4 - (SPINE[0] - SPINE[1]) ** 4)
    nk, Rk, rk, tk = KEEL
    A_k = math.pi * (rk ** 2 - (rk - tk) ** 2)
    EI = E * (I_sp + nk * A_k * Rk ** 2 / 2)
    EA = E * (A_sp + nk * A_k)
    m = RHO * (A_sp + nk * A_k)
    GA = 0.0
    if n:
        A_l, I_l = tube(r)
        EI += E * n * (A_l * R ** 2 / 2 + I_l)
        EA += E * n * A_l
        b = 2 * R * math.sin(math.pi / n); a = 7.65; Ld = math.hypot(a, b)
        A_d = 0.25 * A_l
        GA = n / 2 * E * A_d * b * b * a / Ld ** 3
        m += RHO * n * (A_l + A_d * Ld / a)
        m += RHO * 2 * math.pi * R * tube(0.15)[0] / 7.65 * 1.0            # ring frame r 0.15 m every 7.65 m (PROTOTYPE)
    else:
        GA = 1e30                                                          # S2: shear through the closed spine / keel webs, rigid here
    return {'EI': EI, 'GA': GA, 'EA': EA, 'kg_per_m': m * 1.10}           # +10 % joints


def beam(nodes_x, sec, masses, fix_root=False):
    """Timoshenko beam (2 DOF per node: w, theta), consistent stiffness, lumped mass (translational + small rotary)."""
    n = len(nodes_x); K = np.zeros((2 * n, 2 * n)); M = np.zeros(2 * n)
    for e in range(n - 1):
        L = nodes_x[e + 1] - nodes_x[e]
        EI, GA = sec['EI'], sec['GA']
        phi = 12 * EI / (GA * L * L)
        k = EI / ((1 + phi) * L ** 3) * np.array([[12, 6 * L, -12, 6 * L], [6 * L, (4 + phi) * L * L, -6 * L, (2 - phi) * L * L],
                                                   [-12, -6 * L, 12, -6 * L], [6 * L, (2 - phi) * L * L, -6 * L, (4 + phi) * L * L]])
        idx = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        for i in range(4):
            for j in range(4):
                K[idx[i], idx[j]] += k[i, j]
    for i, m in enumerate(masses):
        M[2 * i] = m; M[2 * i + 1] = m * 1.0 + 1e-6                     # rotary inertia: 1 m2 radius of gyration (small)
    free = list(range(2, 2 * n)) if fix_root else list(range(2 * n))
    return K, M, free


def modes(K, M, free, k=4):
    """Natural frequencies with the rotations condensed out (Guyan): translational lumped masses only, so the rotary inertia of the tank
    rings is neglected (a few per cent high for this slenderness). Avoids the ill-conditioning of tiny rotary masses."""
    t = [i for i in free if i % 2 == 0]; r = [i for i in free if i % 2 == 1]
    Ktt = K[np.ix_(t, t)]; Ktr = K[np.ix_(t, r)]; Krr = K[np.ix_(r, r)]
    Kc = Ktt - Ktr @ np.linalg.solve(Krr, Ktr.T)
    Mi = 1 / np.sqrt(M[t])
    w2 = np.linalg.eigvalsh((Kc + Kc.T) / 2 * Mi[:, None] * Mi[None, :])
    f = np.sqrt(np.clip(w2, 0, None)) / (2 * math.pi)
    flex = sorted(x for x in f if x > 1e-4 * max(1.0, f.max() * 1e-6))
    return flex[:k]


def geometric(nodes_x, N):
    """Geometric stiffness (consistent, Euler) for compressive axial force N per element (positive = compression)."""
    n = len(nodes_x); KG = np.zeros((2 * n, 2 * n))
    for e in range(n - 1):
        L = nodes_x[e + 1] - nodes_x[e]
        g = N[e] / (30 * L) * np.array([[36, 3 * L, -36, 3 * L], [3 * L, 4 * L * L, -3 * L, -L * L],
                                        [-36, -3 * L, 36, -3 * L], [3 * L, -L * L, -3 * L, 4 * L * L]])
        idx = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        for i in range(4):
            for j in range(4):
                KG[idx[i], idx[j]] += g[i, j]
    return KG


def build(d, bow_kg, fill=1.0):
    st = d['stretch']; x0, x1 = st['x_m']
    nodes = np.arange(x0, x1 + 1e-6, 7.65)
    if nodes[-1] < x1 - 1e-6:
        nodes = np.append(nodes, x1)
    m = np.zeros(len(nodes))
    for b in st['bay_masses']:
        mb = b['propellant_kg'] * fill + b['tank_kg']
        lo, hi = b['x_m'] - st['bay_pitch_m'] / 2, b['x_m'] + st['bay_pitch_m'] / 2
        inside = [i for i, x in enumerate(nodes) if lo - 1e-6 <= x <= hi + 1e-6]
        for i in inside:
            m[i] += mb / len(inside)
    m[-1] += bow_kg
    return nodes, m


def analyse(d, name, bow_kg=300e3, fill=1.0, aft_kg=None):
    n, R, r = GEOMS[name]
    sec = section(n, R, r)
    nodes, m = build(d, bow_kg, fill)
    m_struct = sec['kg_per_m'] * (nodes[-1] - nodes[0])
    m = m + sec['kg_per_m'] * 7.65 * np.r_[0.5, np.ones(len(nodes) - 2), 0.5]
    loads = d['loads']; ship = loads['root_axial_by_burn'][0]['ship_kg']
    aft = aft_kg if aft_kg is not None else ship - (sum(m) - 0)       # everything not on the stretch sits at J1
    m_ff = m.copy(); m_ff[0] += aft
    K, M, free = beam(nodes, sec, m_ff)
    f_free = modes(K, M, free)
    Kc, Mc, freec = beam(nodes, sec, m, fix_root=True)
    f_cant = modes(Kc, Mc, freec)
    # buckling under the inertial axial load at the peak acceleration (cantilever from J1, load = mass forward of each element x a)
    a_peak = max(b['accel_g'] for b in loads['root_axial_by_burn']) * G0
    fwd = np.cumsum(m[::-1])[::-1]
    N = np.array([fwd[e + 1] * a_peak for e in range(len(nodes) - 1)]) * SF
    KG = geometric(nodes, N)
    Kf = Kc[np.ix_(freec, freec)]; Gf = KG[np.ix_(freec, freec)]
    lam = np.linalg.eigvals(np.linalg.solve(Kf, Gf))
    lam = max(x.real for x in lam if abs(x.imag) < 1e-9 and x.real > 0)
    buckling_factor = 1 / lam
    # lateral manoeuvre: distributed inertia load, root moment and longeron stress
    xs = nodes - nodes[0]
    out_lat = {}
    for g in G_LAT:
        M_root = float(sum(m[i] * g * G0 * xs[i] for i in range(len(nodes))))
        V_root = float(sum(m) * g * G0)
        sigma_b = M_root * (R if n else KEEL[1]) * E / sec['EI']
        sigma_ax = loads['root_axial_by_burn'][0]['root_axial_N'] * SF * E / sec['EA']
        out_lat[f'{g:g}g'] = {'root_moment_MN_m': M_root / 1e6, 'root_shear_MN': V_root / 1e6, 'stress_MPa': (sigma_b * SF + sigma_ax) / 1e6,
                              'allowable_MPa': ALLOW / 1e6, 'ok': (sigma_b * SF + sigma_ax) <= ALLOW}
    loc = {}
    if n:
        A_l, I_l = tube(r)
        # longeron bay between frames, pinned-pinned
        mpl = RHO * A_l
        f_bay = math.pi / (2 * 7.65 ** 2) * math.sqrt(E * I_l / mpl)
        P_long = (loads['root_axial_by_burn'][0]['root_axial_N'] * SF * E * A_l / sec['EA']
                  + out_lat['0.01g']['root_moment_MN_m'] * 1e6 * SF * R * E * A_l / sec['EI'])
        P_cr = math.pi ** 2 * E * I_l / 7.65 ** 2
        # ring frame ovalling n = 2 (frame r 0.15 m tube on R, frame mass + tributary longeron mass)
        A_f, I_f = tube(0.15)
        m_ring = RHO * A_f + n * RHO * A_l * 7.65 / (2 * math.pi * R)
        f_oval = 1 / (2 * math.pi) * math.sqrt(E * I_f / (m_ring * R ** 4)) * 2 * 3 / math.sqrt(5)
        loc = {'longeron_bay_Hz': f_bay, 'longeron_load_MN': P_long / 1e6, 'longeron_Pcr_MN': P_cr / 1e6, 'longeron_buckling_margin': P_cr / P_long,
               'frame_ovalling_n2_Hz': f_oval,
               'pulse_clear': {k: min(abs(v / (PULSE * h) - 1) for h in (1, 2, 3)) > 0.1 for k, v in (('longeron_bay', f_bay), ('frame_n2', f_oval))}}
    return {'geometry': name, 'n': n, 'R_m': R, 'tube_r_m': r, 'bow_t': bow_kg / 1e3, 'fill': fill, 'EI_N_m2': sec['EI'], 'GA_N': sec['GA'],
            'EA_N': sec['EA'], 'added_structure_t': (sec['kg_per_m'] - section(0, 0, 0)['kg_per_m']) * (nodes[-1] - nodes[0]) / 1e3,
            'structure_t': m_struct / 1e3, 'f_free_free_Hz': f_free[:3], 'f_cantilever_Hz': f_cant[:3], 'f1_Hz': f_free[0],
            'f1_bound_note': 'free-free with a rigid aft ship at J1 is the upper bound; cantilever at J1 (T05 basis) is the lower bound',
            'meets_0.2Hz_cantilever': f_cant[0] >= F_TARGET, 'meets_0.2Hz_free_free': f_free[0] >= F_TARGET, 'buckling_factor_SF2': buckling_factor, 'lateral': out_lat, 'local': loc,
            'J1': {'axial_design_MN': loads['root_axial_by_burn'][0]['root_axial_N'] * SF / 1e6, 'moment_0.01g_MN_m': out_lat['0.01g']['root_moment_MN_m'],
                   'shear_0.01g_MN': out_lat['0.01g']['root_shear_MN']},
            'J3': {'axial_design_MN': bow_kg * a_peak * SF / 1e6, 'lateral_0.01g_MN': bow_kg * 0.01 * G0 / 1e6}}


def size_for(d, n, R, bow_kg, target=F_TARGET):
    """Smallest longeron tube radius (t/r 0.1) that gives f1 >= target with full tanks; returns (r, added structure t)."""
    lo, hi = 0.05, 2.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        GEOMS['_tmp'] = (n, R, mid)
        ok = analyse(d, '_tmp', bow_kg)['f_cantilever_Hz'][0] >= target
        lo, hi = (lo, mid) if ok else (mid, hi)
    GEOMS['_tmp'] = (n, R, hi)
    res = analyse(d, '_tmp', bow_kg)
    del GEOMS['_tmp']
    return hi, res


def thermal(R):
    """Thermal bow of the stretch from a side-to-side temperature difference (CFRP, quasi-isotropic alpha 2e-6)."""
    out = {}
    for dT in (10.0, 50.0):
        k = 2e-6 * dT / (2 * R)
        out[f'{dT:g}K'] = {'curvature_per_m': k, 'tip_deflection_m': k * 275.4 ** 2 / 2, 'angle_urad': k * 275.4 * 1e6}
    return out


def main():
    d = t05()
    rows = []
    for g in ('S2', 'N6_drawn', 'N6_fixed', 'N9_gaps'):
        for bow in (100e3, 300e3, 1000e3):
            for fill in (1.0, 0.0):
                rows.append(analyse(d, g, bow, fill))
    sizing = []
    for (n, R, lab) in ((6, 34.8, 'N6 at R 34.8 m'), (9, 31.0, 'N9 at R 31 m')):
        for bow in (100e3, 300e3, 1000e3):
            r, res = size_for(d, n, R, bow)
            sizing.append({'layout': lab, 'bow_t': bow / 1e3, 'tube_r_m': r, 'added_structure_t': res['added_structure_t'],
                           'structure_t': res['structure_t'], 'f1_cantilever_Hz': res['f_cantilever_Hz'][0], 'f1_free_free_Hz': res['f1_Hz'], 'buckling_factor_SF2': res['buckling_factor_SF2'],
                           'longeron_buckling_margin': res['local'].get('longeron_buckling_margin'), 'local': res['local']})
    dyn = d['dynamics']
    req = {'f1_min_Hz': F_TARGET, 'basis': '3x the highest slosh (0.040 Hz) and 3x ring spin (0.0667 Hz); below the pulse rate by > 100x',
           'slosh_Hz': dyn['slosh_Hz'], 'ring_spin_Hz': dyn['ring_spin_Hz'], 'pulse_Hz': PULSE,
           'tank_saddle': {'recommend_Hz': [10.0, 30.0], 'max_vessel_t': max(b['vessel_max_kg'] for b in d['stretch']['bay_masses']) / 1e3,
                           'k_N_m_at_10Hz': max(b['vessel_max_kg'] for b in d['stretch']['bay_masses']) * (2 * math.pi * 10) ** 2,
                           'transmissibility_at_pulse': (10.0 / PULSE) ** 2,
                           'note': 'isolate the vessels: a saddle mode at 10-30 Hz passes (f/f_p)^2 = 0.3-2.3 % of the pulse ripple and stays '
                                   'well above f1 and the slosh band; a stiff saddle above 196 Hz would need about 7e11 N/m per vessel'}}
    out = {'study': 'Revision 4 section 6, S5 spine beam FE (T00)', 'status': 'MODEL, research only, NON-CANON; 1D Timoshenko beam, not FEA',
           'inputs': {'t05_ref': T05_REF, 'material': {'E': E, 'rho': RHO, 'sigma': SIG, 'SF': SF, 'splice': SPLICE, 'allowable_Pa': ALLOW},
                      'geometries': GEOMS, 'keel': KEEL, 'spine': SPINE, 'lacing': '0.25 x longeron area, every bay panel (PROTOTYPE)',
                      'frames': 'tube r 0.15 m, t/r 0.1, every 7.65 m (PROTOTYPE)'},
           'rows': rows, 'sizing_for_0.2Hz': sizing, 'requirements': req, 'thermal_bow': {k: thermal(v[1]) for k, v in GEOMS.items() if v[0]},
           'independence': {'K2': 'pressure tube r 3 m az 90 deg, between keels 30 and 150; carries no primary load; its own 2.2 m tube',
                            'launcher': 'in the spine bore or on its own kinematic rail; must not be a primary member (thermal bow of the '
                                        'stretch is 0.4-2 mrad, far above the 22 urad untracked pointing need)',
                            'services': 'two independent runs on keels 150 and 270 (K2 on the 90 side), cross-tied at J1 and J3',
                            'checks': ['K2 and the launcher share no member', 'loss of one keel: cantilever f1 in keel_loss']}}
    # keel loss: N9 with one keel removed is dominated by the longerons; recompute with keel area 2/3
    k0 = KEEL
    globals()['KEEL'] = (2, k0[1], k0[2], k0[3])
    out['keel_loss'] = {g: analyse(d, g)['f_cantilever_Hz'][0] for g in ('N6_fixed', 'N9_gaps')}
    globals()['KEEL'] = k0
    write_json('spine.json', out)
    for r_ in rows:
        print(f"{r_['geometry']:9s} bow {r_['bow_t']:5.0f} t fill {r_['fill']:.0f}: f1 {r_['f1_Hz']:.3f} Hz (cant {r_['f_cantilever_Hz'][0]:.3f}) "
              f"buckle x{r_['buckling_factor_SF2']:8.1f} added {r_['added_structure_t']:6.0f} t  0.01g stress {r_['lateral']['0.01g']['stress_MPa']:.0f} MPa "
              + (f"bay {r_['local']['longeron_bay_Hz']:.1f} Hz oval {r_['local']['frame_ovalling_n2_Hz']:.2f} Hz" if r_['local'] else ''))
    for s in sizing:
        print(s['layout'], s['bow_t'], round(s['tube_r_m'], 3), round(s['added_structure_t']), round(s['structure_t']), round(s['f1_free_free_Hz'], 3),
              s['local']['longeron_bay_Hz'], s['local']['frame_ovalling_n2_Hz'])
    print(out['keel_loss'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
