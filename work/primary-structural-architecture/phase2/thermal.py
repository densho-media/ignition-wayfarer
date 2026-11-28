"""Correction 3.5: thermal compliance by degrees of freedom. Thermal load cases on the sized global model, with the spine either
fully coupled to the cage (every tie fixed) or on the proposed datum scheme (one axial datum, axial slides elsewhere).

Cases (free-free, no thrust, self-equilibrated): uniform soak, a hot sector, a through-section rail gradient, a warm spine.
Output: peak thermal utilisation (stress over the design allowable, factor 1.0 because thermal strain is a deformation-controlled
load; the combination with thrust uses the yield factor 1.25 in the report), axial growth, bow at the Brow, spine-to-cage slip.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import analysis as an  # noqa: E402
import configs  # noqa: E402
import model as mdl  # noqa: E402

OUT = H.parent / 'results'


def sized(key, coupled):
    V = json.loads((OUT / 'p2_variants.json').read_text())[key]
    cfg = configs.config(V['config'], 1.0)
    b = mdl.Build(V['concept'], cfg, rotor=V['rotor'], spine_coupled=coupled)
    for g, s in V['sizing'].items():
        if g in b.sec:
            b.sec[g]['r'], b.sec[g]['t'] = s['r'], s['t']
    b.update_sections(); b.attach(cfg['parts'])
    return b


def apply(b, case):
    for e, md in zip(b.m.el, b.meta):
        e['dT'] = e['dTy'] = e['dTz'] = 0.0
        if e['kind'] == 'spring' or md['fam'] == 'iface':
            continue
        xa, xb = b.m.X[e['a']], b.m.X[e['b']]; az = math.degrees(math.atan2((xa[2]+xb[2])/2, (xa[1]+xb[1])/2)) % 360
        if case == 'uniform soak +60 K':
            e['dT'] = 60.0
        elif case == 'hot sector +50 K (az 240-300)':
            if 240 <= az <= 300 and md['fam'] in ('rail', 'diag', 'frame', 'modframe', 'trans'):
                e['dT'] = 50.0
        elif case == 'rail through-section gradient 20 K':
            if md['fam'] == 'rail':
                e['dTz'] = 20.0
        elif case == 'warm spine +40 K':
            if md['fam'] in ('spine', 'hub'):
                e['dT'] = 40.0


def run(key):
    out = []
    for coupled, label in ((True, 'all ties fixed'), ('datum', 'one axial datum + slides')):
        b = sized(key, coupled)
        for case in ('uniform soak +60 K', 'hot sector +50 K (az 240-300)', 'rail through-section gradient 20 K', 'warm spine +40 K'):
            apply(b, case); b.m.loads = {}; b.m.follow = {}
            r = b.m.solve_static(inertia_relief=True, thermal=True); fs = b.m.element_forces(r['u'])
            u = []
            for e, md, f in zip(b.m.el, b.meta, fs):
                if f is None or md['fam'] == 'iface':
                    continue
                s = b.sec[md['group']]; mat = mdl.mat(s['mat']); A, I, S = an.tube_props(np.array(s['r']), np.array(s['t']))
                sig = abs(f['N'])/A + math.hypot(f['My'], f['Mz'])/S
                u.append((float(sig/min(mat['Fc'], mat['Ft'])), md['group']))
            u.sort(reverse=True)
            ux = r['u'][0::6]; uy = r['u'][1::6]; uz = r['u'][2::6]
            bn = b.brow_nodes[0]; noz = b.noz[0]
            sp = b.sp(60.0); rail = b.station_nodes[min(b.xs, key=lambda q: abs(q-60.0))][b.rail_az()[0]]
            out.append(dict(ties=label, case=case, max_util=u[0][0], at=u[0][1], top=[x[1] for x in u[:5]],
                            growth_mm=float((ux[bn]-ux[noz])*1e3), brow_bow_mm=float(math.hypot(uy[bn]-uy[noz], uz[bn]-uz[noz])*1e3),
                            spine_slip_mm_at_x60=float((ux[sp]-ux[rail])*1e3), residual=r['accel']['multiplier_residual']))
            print(f"{label:<26} {case:<36} util {u[0][0]:5.2f} at {u[0][1]:<14} growth {out[-1]['growth_mm']:7.1f} mm bow {out[-1]['brow_bow_mm']:7.1f} mm slip {out[-1]['spine_slip_mm_at_x60']:6.1f}")
    return out


if __name__ == '__main__':
    keys = sys.argv[1:] or ['H:hub:F1', 'HC:hub:F1']
    res = {k: run(k) for k in keys}
    (OUT / 'p2_thermal.json').write_text(json.dumps(res, indent=1))
