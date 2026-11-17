"""Vertex 2.3: ring-strike (leakage) Monte Carlo at the chosen single-ring design, sized to test the 1e-4 requirement.

  python3 lab/variants/halo-vertex/leak.py [n]     writes lab/variants/halo-vertex/leak.json (default n = 30,000 per case; 3 processes)

Design: one ring, B0 = 0.2 T at the centre (B0 R = 12.8 T m), burn 2 R aft of the ring plane (trace.py scan). Source: uniform sphere of
radius r_src about the burn point, isotropic directions. With zero strikes in n samples the one-sided 95 % upper limit is 3/n
(n = 30,000 -> 1e-4). Also records the exit-direction cosines of the aft and forward streams (used by halo.py for plume geometry).
"""
import json
import math
import random
import sys
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import trace as tr  # noqa: E402  (the local trace.py, not the standard library module)

R = 64.0
B0 = 0.2
Z0 = 2.0
CASES = [('p 14.7 MeV (D-3He product)', 0.05), ('D exhaust 0.0677 c', 0.1), ('He-3 exhaust 0.0677 c', 0.1)]


def design():
    I = 2*R*B0/tr.MU0
    return [(I, R, 0.0)], tr.ring_body(R, 0.08, 1.4)


def chunk(args):
    sp, rs, n, seed = args
    coils, bodies = design(); rnd = random.Random(seed); out = []
    for _ in range(n):
        while True:
            x, y, z = (rnd.uniform(-1, 1) for _ in range(3))
            if x*x+y*y+z*z <= 1:
                break
        mu = rnd.uniform(-1, 1); ph = rnd.uniform(0, 2*math.pi)
        rr = math.hypot(x, y)*rs*R; zz = Z0+z*rs; ang = math.atan2(y, x)
        k, c = tr.push(coils, bodies, sp, math.acos(mu), zz, R, r_src=rr, phi=ph-ang)
        out.append((k, round(c, 4)))
    return out


def run(n=30000, procs=3):
    res = []
    with Pool(procs) as pool:
        for sp, rs in CASES:
            parts = pool.map(chunk, [(sp, rs, n//(procs*4), 100*i+7) for i in range(procs*4)])
            rows = [x for p in parts for x in p]; N = len(rows); cnt = {}
            for k, _ in rows:
                cnt[k] = cnt.get(k, 0)+1
            aft = sorted(c for k, c in rows if k == 'AFT'); fwd = sorted(c for k, c in rows if k == 'FORWARD')
            strikes = cnt.get('RING', 0)
            res.append(dict(species=sp, source_radius_R=rs, n=N, counts=cnt, ring_strike=strikes/N,
                            ring_strike_upper95=(3.0 if strikes == 0 else strikes+2*math.sqrt(strikes))/N,
                            thrust_cos=(sum(aft)+sum(fwd))/N, aft_cos_deciles=[aft[int(i*len(aft)/10)] for i in range(10)] if aft else [],
                            forward_cos_deciles=[fwd[int(i*len(fwd)/10)] for i in range(10)] if fwd else [],
                            forward_cos_min_abs=min((abs(c) for c in fwd), default=None)))
            print(res[-1], flush=True)
    return dict(design=dict(R_m=R, B0_T=B0, I_MA=2*R*B0/tr.MU0/1e6, burn_R=Z0, conductor_face_m=0.08, conductor_depth_m=1.4), cases=res)


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30000
    out = run(n)
    (HERE/'leak.json').write_text(json.dumps(out, indent=1)+'\n')
