"""Section 2: ISSA interface refresh (CP3/CP4 values, parametric). Hot-loop support reactions per load class, structure-induced
support travel, and interference checks of the ISSA envelopes against the generated PSA members.

Reads results/p2_variants.json and results/p2_geom/*.json; writes results/p2_interface.json. Operating values from ISSA are not
ultimate; this file derives limit and ultimate values from the PSA load cases (D01, one factor).
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

OUT = H.parent / 'results'
G0 = 9.80665
CP3 = dict(pitch_m=6.4, supports_per_section=4, section_m=25.4, trunk_t_per_m=0.211, saddle_t=5.4, anchor_kN=155.0, anchor_g=0.736,
           travel_mm=(38, 127), x_hot0=-111.6, hot_len=152.6, r_trunk=6.52)


def rigid(cfgname, struct_t, left):
    c = configs.config(cfgname, left); parts = c['parts']
    M = sum(p['m'] for p in parts)+struct_t*1e3
    xs = [(p['m'], 0.5*(p['x'][0]+p['x'][1]), p['x'][1]-p['x'][0]) for p in parts]
    xs.append((struct_t*1e3, -20.0, 280.0))
    xc = sum(m*x for m, x, _ in xs)/M; I = sum(m*((x-xc)**2+L*L/12) for m, x, L in xs)
    return M, xc, I


def reactions(v):
    out = []
    T = configs.THRUST_N; s_t = v['structure_t']
    for left in (1.0, 0.0):
        M, xc, I = rigid(v['config'], s_t, left)
        a = T/M; dlf = v['dlf']
        alpha = (T/4*2.6)/I                                                     # engine-out pitch acceleration (rigid)
        xs = [CP3['x_hot0']+i*CP3['section_m'] for i in range(int(CP3['hot_len']//CP3['section_m'])+1)]
        lat = max(abs(alpha*(x-xc)) for x in xs) + 0.02*T/M                   # + TVC 2 %
        m_sec = CP3['supports_per_section']*CP3['saddle_t']*1e3
        for cls, f in (('operating', 1.0), ('limit', dlf), ('ultimate', dlf*an.LF_ULT), ('proof', dlf*an.LF_PROOF)):
            out.append(dict(left=left, cls=cls, a_axial_g=a*f/G0, anchor_axial_kN=m_sec*a*f/1e3, slide_lateral_kN=CP3['saddle_t']*1e3*lat*(f if cls != 'operating' else 1)/1e3,
                            shutdown_reversal_anchor_kN=-m_sec*a*(dlf-1)*(f/dlf)/1e3 if cls != 'operating' else 0.0))
    return out


def support_travel(geom):
    """Structure-induced change of the anchor-to-slide spacing along the hot loop (steady thrust x DLF): rail ux between section
    ends, read from the FE displacement field at r 5 (rail nodes)."""
    X = np.array(geom['nodes']); ux = np.array(geom['ux_mm'])
    r = np.hypot(X[:, 1], X[:, 2]); sel = (np.abs(r-5.0) < 0.2)
    out = []
    for i in range(6):
        x0 = CP3['x_hot0']+i*CP3['section_m']; x1 = x0+CP3['section_m']
        a = sel & (np.abs(X[:, 0]-x0) < 2.1); b = sel & (np.abs(X[:, 0]-x1) < 2.1)
        if a.any() and b.any():
            out.append(dict(section=i+1, x0=x0, x1=x1, shortening_mm=float(ux[b].mean()-ux[a].mean())))
    return out


def dist_seg(p, a, b):
    ab = b-a; t = np.clip(np.dot(p-a, ab)/max(np.dot(ab, ab), 1e-12), 0, 1); return float(np.linalg.norm(p-(a+t*ab)))


def lane_clear(geom, lane):
    """Minimum surface clearance between members and a lane (a line along X at r, az over X range, with half-size) sampled every 1 m."""
    X = np.array(geom['nodes']); worst = (1e9, None)
    x0, x1 = lane['x']; th = math.radians(lane['az']); pts = [np.array([x, lane['r']*math.cos(th), lane['r']*math.sin(th)]) for x in np.arange(x0, x1, 1.0)]
    for m in geom['members']:
        a, b = X[m['a']], X[m['b']]
        if max(a[0], b[0]) < x0-2 or min(a[0], b[0]) > x1+2:
            continue
        for p in pts:
            d = dist_seg(p, a, b)-m['r']-lane['half']
            if d < worst[0]:
                worst = (d, m['group'], float(p[0]))
    return dict(lane=lane['name'], min_clear_m=worst[0], member=worst[1], at_x=worst[2] if len(worst) > 2 else None, ok=worst[0] > lane.get('need', 0.05))


LANES = [dict(name=f'NaK pipe az {a}', r=5.8, az=a, x=(-81.6, 40.4), half=0.1115, need=0.05) for a in (10, 50, 130, 170, 250, 290)] + [
    dict(name='MRU carriage lane (az 270, r 3.6, envelope 1.2 m PROTOTYPE)', r=3.6, az=270, x=(-88.0, 98.0), half=0.6, need=0.10),
    dict(name='ECLSS duct (X 99.2, r 1.4)', r=1.4, az=90, x=(98.9, 99.5), half=0.14, need=0.05),
    dict(name='ECLSS duct (X 101.4, r 1.4)', r=1.4, az=90, x=(101.1, 101.7), half=0.14, need=0.05),
    dict(name='hot-loop trunk axis (r 6.52, az 90)', r=6.52, az=90, x=(-111.6, 41.0), half=0.35, need=0.10),
]


def main():
    V = json.loads((OUT / 'p2_variants.json').read_text())
    res = dict(cp3=CP3, variants={})
    for k, v in V.items():
        if v['config'] != 'F1':
            continue
        g = OUT / 'p2_geom' / (k.replace(':', '_')+'.json')
        geom = json.loads(g.read_text()) if g.exists() else None
        e = dict(reactions=reactions(v))
        if geom:
            e['support_travel'] = support_travel(geom) if geom.get('ux_mm') else None
            e['lanes'] = [lane_clear(geom, L) for L in LANES]
        res['variants'][k] = e
    (OUT / 'p2_interface.json').write_text(json.dumps(res, indent=1, default=float))
    for k, e in res['variants'].items():
        r = [x for x in e['reactions'] if x['cls'] == 'ultimate']
        print(k, 'ultimate anchor kN', [round(x['anchor_axial_kN']) for x in r], 'slide kN', [round(x['slide_lateral_kN'], 1) for x in r])
        for L in e.get('lanes', []):
            if not L['ok']:
                print('   CLASH', L)
        if e.get('support_travel'):
            print('   travel', [round(s['shortening_mm'], 1) for s in e['support_travel']])


if __name__ == '__main__':
    main()
