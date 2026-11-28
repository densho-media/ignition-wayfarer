"""PSA Phase III review export: results/p3_review/<tag>.json with nodes, members (family, group, material, radius, steady axial
force at departure, ultimate utilisation), the critical buckling mode and the first elastic mode at departure (node displacements,
normalised to 1 m peak), fail-safe joint classes (results/p3_failsafe/<tag>.json if present) and the WSI body envelopes.

  python3 post3.py <closure json> [failsafe json]
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

OUT = H.parent / 'results' / 'p3_review'; OUT.mkdir(parents=True, exist_ok=True)


def shape(b, u):
    U = np.asarray(u).reshape(-1, 6)[:, :3]; s = np.abs(U).max() or 1.0
    return (U/s).round(4).tolist()


def main(path, fpath=None):
    d, b, hs = fs3.load(path, 3); b.attach(hs[0]['cfg']['bodies'])
    cs = an.cases(b, hs); env = a3.envelope3(b, cs); u, mode = a3.utilisation(b, env)
    b.attach(hs[0]['cfg']['bodies']); r, f = an.solve(b)
    g = c3.crit(b, 0.0); f1, v1 = c3.first_mode(b)
    mem = []
    for i, (e, md) in enumerate(zip(b.m.el, b.meta)):
        if e['kind'] == 'spring' or not e['on']:
            continue
        s = b.sec.get(md['group']); mem.append(dict(a=e['a'], b=e['b'], fam=md['fam'], group=md['group'],
                                                   mat=(s['mat'] if s else 'IFACE'), r=(s['r'] if s else 0.05),
                                                   N=(f[i]['N']/1e6 if f[i] else 0.0), util=float(u[i]), umode=mode[i]))
    fsd = {}
    if fpath and Path(fpath).exists():
        for row in json.loads(Path(fpath).read_text())['rows']:
            if row.get('node') is not None:
                k = str(row['node']); prev = fsd.get(k)
                fsd.setdefault(k, {})[row['kind']] = row['cls']
    bodies = []
    for q in hs[0]['cfg']['bodies']:
        bb = dict(name=q['name'], m_t=q['m']/1e3, c=list(map(float, q['c'])), kind=q['kind'], cls=q['cls'])
        for k in ('a', 'R', 'az', 'x0', 'x1', 'x', 'r'):
            if k in q:
                bb[k] = q[k] if not isinstance(q[k], tuple) else list(q[k])
        bodies.append(bb)
    out = dict(tag=d['tag'], structure_t=d['structure_t'], lam=g.get('lam'), f1=f1, nodes=np.asarray(b.m.X).round(3).tolist(), members=mem,
               buckle=shape(b, g['mode']) if g.get('mode') is not None else None, mode1=shape(b, v1), failsafe=fsd, bodies=bodies,
               noz=list(b.noz), mru=dict(r=2.9, half=0.55, x=[-92.7, 92.0], az=270.0))
    (OUT / f"{d['tag']}.json").write_text(json.dumps(out, default=float))
    print('wrote', OUT / f"{d['tag']}.json", len(mem), 'members')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
