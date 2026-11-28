"""Correction 3.2: audit of the drive pickup forces (Phase I 37.7 MN -> 1.9 MN) with a local FE model, one effect at a time.

Local model: the thrust ring (12 nodes, r 5.5 m, Ti-6Al-4V box-equivalent tube) supported axially by the rails (3 or 6 axial springs,
k = EA/L of a 16 m rail segment, lateral restraint by the frame), and one nozzle node at r 2.6 m, dx aft of the ring, joined by n
pickup struts. A unit axial thrust per nozzle (1 MN) is applied. Each line changes ONE thing from the production-like baseline.
The 37.7 MN Phase I figure was: canon design thrust 29.42 MN / 4 nozzles / one strut / cos(78.7 deg) - a single pin-ended strut
taking the whole nozzle at the production angle. The 1.9 MN figure was the same nozzle load shared by 4 struts at the axial
re-angled geometry. Both are bounds; the audit shows which effects move the number.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import fe  # noqa: E402
import model as mdl  # noqa: E402

TI = mdl.mat('TI64'); AL = mdl.mat('AL6061')
T_N = 1.0e6


def local(n_struts=3, dx=0.58, spread=30.0, kind='truss', rails=6, ring_r=0.35, ring_t=0.03, strut_r=0.2, strut_t=0.02, asym=1.0,
          joint_off=0.0, axial_post=False, ring_rail_offset=0.0):
    m = fe.Model(); R = 5.5
    ring = [m.node(mdl.Build.p(0.0, R, a)) for a in range(0, 360, 30)]
    rsec = fe.tube(ring_r, ring_t)
    for i in range(12):
        m.beam(ring[i], ring[(i+1) % 12], rsec, TI)
    raz = [30, 150, 270] if rails == 3 else [21.4, 38.6, 141.4, 158.6, 261.4, 278.6]
    k_ax = AL['E']*fe.tube(0.43, 0.026)['A']/16.0*(1.0 if rails == 3 else 0.5)
    for a in raz:
        # rail attachment on the ring (at the nearest ring node, or between nodes by ring_rail_offset)
        q = min(range(12), key=lambda i: abs(((i*30-a+180) % 360)-180))
        g = m.node(mdl.Build.p(16.0, R, a))
        m.beam(ring[q], g, dict(A=k_ax*16.0/AL['E'], Iy=1e-3, Iz=1e-3, J=1e-3, c=0.4), AL, kind='truss')
        m.fix(g)
    # lateral restraint of the ring (frame + diagonals): soft springs at every ring node in the ring plane
    for i, nd in enumerate(ring):
        g = m.node(m.X[nd]+np.array([0.0, 0.0, 0.0])); m.fix(g)
        m.spring(g, nd, [0.0, 2e7, 2e7, 0.0, 0.0, 0.0])
    nz = m.node(mdl.Build.p(-dx, 2.6, 0.0))
    ssec = fe.tube(strut_r, strut_t)
    struts = []
    angs = [0.0] if n_struts == 1 else list(np.linspace(-spread, spread, n_struts))
    for j, a in enumerate(angs):
        q = min(range(12), key=lambda i: abs(((i*30-a+180) % 360)-180))
        tgt = ring[q]
        if joint_off:
            # strut lands joint_off metres off the ring's shear centre (eccentric lug): a short stiff offset arm
            off = m.node(m.X[tgt]+np.array([-joint_off, 0.0, 0.0])); m.beam(tgt, off, fe.tube(0.3, 0.05), TI); tgt = off
        sec = ssec if (asym == 1.0 or j) else fe.tube(strut_r, strut_t*asym)
        struts.append(m.beam(nz, tgt, sec, TI, kind=kind))
    if axial_post:
        # direct axial transfer: an axial thrust post from the nozzle node forward to a node on a radial spoke of the ring plane
        hub = m.node((0.0, 2.6, 0.0)); m.beam(nz, hub, fe.tube(0.3, 0.03), TI)
        for i in (11, 0, 1):
            m.beam(hub, ring[i], fe.tube(0.25, 0.025), TI)
        struts.append(len(m.el)-4)
    # nozzle lateral restraint by the drive cage (the other nozzles): springs to ground in Y/Z, rotations
    g = m.node(m.X[nz]); m.fix(g); m.spring(g, nz, [0.0, 1e8, 1e8, 1e8, 1e8, 1e8])
    m.load(nz, (T_N, 0.0, 0.0))
    r = m.solve_static(); f = m.element_forces(r['u'])
    Ns = [abs(f[i]['N']) for i in struts]; Ms = [math.hypot(f[i]['My'], f[i]['Mz']) for i in struts]
    ringM = max(math.hypot(f[i]['My'], f[i]['Mz']) for i in range(12))
    return dict(strut_N_over_T=max(Ns)/T_N, strut_M_kNm_per_MN=max(Ms)/1e3, ring_M_kNm_per_MN=ringM/1e3,
                nozzle_dx_mm_per_MN=float(r['u'][6*nz]*1e3), angle_deg=math.degrees(math.atan2(5.5-2.6, dx)))


def main():
    base = dict()
    lines = [
        ('Phase I bound: 1 pin strut, production angle', dict(n_struts=1, kind='truss')),
        ('baseline: 3 pin struts, production angle (78.7 deg)', dict()),
        ('angle: dx 1.5 m (62.6 deg)', dict(dx=1.5)),
        ('angle: dx 2.9 m (45 deg)', dict(dx=2.9)),
        ('angle: dx 5.0 m (30.1 deg)', dict(dx=5.0)),
        ('strut count: 2', dict(n_struts=2)),
        ('strut count: 4', dict(n_struts=4, spread=45.0)),
        ('load sharing: 3 struts, soft ring (r 0.2, t 0.015)', dict(ring_r=0.2, ring_t=0.015)),
        ('load sharing: 3 struts, stiff ring (r 0.5, t 0.05)', dict(ring_r=0.5, ring_t=0.05)),
        ('joint position: 0.3 m eccentric lug', dict(joint_off=0.3)),
        ('local bending: fixed-end struts (beam), production angle', dict(kind='beam')),
        ('stiffness: struts 3x thicker', dict(strut_t=0.06)),
        ('asymmetry: one strut 50 % thinner', dict(asym=0.5)),
        ('rails: 3 single rails', dict(rails=3)),
        ('direct axial transfer: axial post + 3 spokes', dict(axial_post=True)),
        ('combined: 4 beam struts at 45 deg, stiff ring', dict(n_struts=4, spread=45.0, dx=2.9, kind='beam', ring_r=0.5, ring_t=0.05)),
    ]
    out = []
    for name, kw in lines:
        r = local(**kw); r['name'] = name; out.append(r)
    for r in out:
        r['strut_MN_at_canon_29.42MN'] = r['strut_N_over_T']*29.41995/4
        r['strut_MN_at_flight_21.77MN'] = r['strut_N_over_T']*21.770763/4
    (H.parent / 'results' / 'p2_pickup.json').write_text(json.dumps(out, indent=1))
    for r in out:
        print(f"{r['name']:<58} N/T {r['strut_N_over_T']:6.2f}  strut {r['strut_MN_at_canon_29.42MN']:6.2f} MN @29.42  ringM {r['ring_M_kNm_per_MN']:7.1f}  dx {r['nozzle_dx_mm_per_MN']:6.2f} mm/MN")


if __name__ == '__main__':
    main()
