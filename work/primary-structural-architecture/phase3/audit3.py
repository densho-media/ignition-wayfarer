"""PSA Phase III.0 stability audit items (owner 3.4) on a sized variant: depletion states, actual thrust points, partial follower,
damping threshold, mass uncertainty, puller (tension) sensitivity, rigid-elastic coupling (via dyn3).

  python3 audit3.py <closure json> [n_states]
Each item changes one thing against the reference sweep (thrust at the 12 thrust-ring nodes, zeta 0.005, nominal masses).
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H)); sys.path.insert(0, str(H.parent / 'phase2'))
import analysis as an  # noqa: E402
import model3 as m3  # noqa: E402
import run3  # noqa: E402

OUT = H.parent / 'results' / 'p3_audit'; OUT.mkdir(parents=True, exist_ok=True)


def lam(b, nodes, partial, zeta=0.005, sign=1.0):
    T = b.cfg['thrust']; b.m.loads = {}; b.m.follow = {}
    for n in nodes:
        b.m.thrust(n, (sign*T/len(nodes), 0.0, 0.0), follower=True)
    r = b.m.solve_static(inertia_relief=True); fs = b.m.element_forces(r['u']); N = [f['N'] if f else 0.0 for f in fs]
    out = an.reduced_stability(b, N, lam_hi=12.0, nbasis=60, partial=partial, zeta=zeta); out.pop('mode', None)
    b.apply_thrust(T)
    return out.get('lam') or 12.0, out.get('kind')


def scaled(bodies, f):
    out = []
    for q in bodies:
        q = dict(q); q['m'] *= f; q['I'] = q['I']*f; out.append(q)
    return out


def main(path, n=3):
    t0 = time.time(); d = json.loads(Path(path).read_text()); hs = run3.hist(n, 'wsi')
    b = m3.Build3(d['concept'], hs[0]['cfg'], deck=d['deck'], rotor=d['rotor'], guide_ring=d['guide_ring'], mats=d['mats'])
    for g, s in d['sections'].items():
        if g in b.sec:
            b.sec[g].update(s)
    b.update_sections()
    ring = list(b.station_nodes[b.xs[0]].values()); rows = []
    for s in hs:
        bodies = s['cfg']['bodies']; b.attach(bodies)
        ref = {p: lam(b, ring, p) for p in (0.0, 0.5, 1.0)}
        row = dict(left=s['left'], ref_static=ref[0.0], ref_partial05=ref[0.5], ref_follower=ref[1.0])
        row['nozzle_static'] = lam(b, b.noz, 0.0); row['nozzle_follower'] = lam(b, b.noz, 1.0)
        row['zeta0.002_follower'] = lam(b, ring, 1.0, zeta=0.002); row['zeta0.01_follower'] = lam(b, ring, 1.0, zeta=0.01)
        for f in (0.9, 1.1):
            b.attach(scaled(bodies, f)); row[f'mass{f}_static'] = lam(b, ring, 0.0); row[f'mass{f}_follower'] = lam(b, ring, 1.0)
        b.attach(bodies)
        # puller sensitivity: the same thrust applied at the Brow interface ring pulling the ship (+x): the farm and cage hang in
        # tension behind it. Not a design (the plume would hit the ship); it measures how much of the problem is compression.
        row['puller_static'] = lam(b, b.brow_nodes, 0.0); row['puller_follower'] = lam(b, b.brow_nodes, 1.0)
        rows.append(row); print(json.dumps({k: (v if not isinstance(v, tuple) else [round(v[0], 3), v[1]]) for k, v in row.items()}), flush=True)
    out = dict(source=path, tag=d['tag'], rows=rows, seconds=time.time()-t0)
    (OUT / f"{d['tag']}.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3)
