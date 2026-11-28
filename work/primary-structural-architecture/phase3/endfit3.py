"""PSA Phase III forward end fitting (X 92.8, r 4.8): frame:14 and diag:14 are strength-short at their family radius limit (0.35 /
0.25 m) after closure. The forward end frame is a local load-introduction ring (farm tie ring, keels, hub-front): it is given a
larger section limit (RMAX_END, PROTO) and the cheapest passing section, then lambda and f1 are re-checked.

  python3 endfit3.py <closure json> <out tag>
"""
import json
import sys
from pathlib import Path

import numpy as np

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H)); sys.path.insert(0, str(H.parent / 'phase2'))
import analysis as an  # noqa: E402
import analysis3 as a3  # noqa: E402
import closure3 as c3  # noqa: E402
import failsafe3 as fs3  # noqa: E402

RMAX_END = 0.60


def main(path, tag):
    d, b, hs = fs3.load(path, 3); b.attach(hs[0]['cfg']['bodies'])
    m0 = b.structure_mass()[0]/1e3
    groups = list(d['strength_failing'])
    for g in groups:
        b.sec[g]['rmax'] = RMAX_END
    cs = an.cases(b, hs); env = a3.envelope3(b, cs)
    for it in range(3):
        rep = a3.size3(b, env)          # resizes every group to its cheapest passing section; keep the closure's stiffening elsewhere
        for g, s in d['sections'].items():
            if g in b.sec and g not in groups:
                b.sec[g].update(s)
        b.update_sections(); cs = an.cases(b, hs); env = a3.envelope3(b, cs)
    u, _ = a3.utilisation(b, env)
    fail = sorted({b.meta[i]['group'] for i in range(len(u)) if u[i] > 1.0})
    st = c3.sweep(b, hs, print); f1 = {}
    for s in hs:
        b.attach(s['cfg']['bodies']); f1[f"{s['left']:.1f}"] = c3.first_mode(b)[0]
    jt, _ = an.joints(b, env); m1 = b.structure_mass()[0]/1e3
    out = dict(d); out.update(tag=tag, members_t=m1, joints_t=jt/1e3, structure_t=m1+jt/1e3, end_fitting_t=m1-m0, end_groups={g: dict(r=b.sec[g]['r'], t=b.sec[g]['t']) for g in groups},
                              strength_failing=fail, stability=[{k: v for k, v in r.items() if k != 'mode'} for r in st], f1_Hz=f1,
                              closed=bool(min(r['lam'] for r in st) >= c3.LAM_TARGET-2e-3 and min(f1.values()) >= 0.0949 and not fail),
                              sections={g: dict(r=s['r'], t=s['t'], mat=s['mat']) for g, s in b.sec.items()})
    (c3.OUT / f'{tag}.json').write_text(json.dumps(out, indent=1, default=float))
    print(tag, 'structure', round(out['structure_t'], 1), 'end fitting +', round(out['end_fitting_t'], 2), 't; failing', fail, 'f1', f1, 'closed', out['closed'])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
