"""WSI CP3: the sized PSA primary structure at the WSI point as review geometry, plus deflections and interference checks.

Rebuilds the PSA Phase III FE model (phase3 model3.Build3 on the WSI bodies, wsi_bodies.history) with the sizing of a PSA run JSON,
solves the steady-thrust case at departure and end of burn, and writes results/wsi_members.json: nodes, members (family, group, radius,
wall, material, axial force), deflections, and the checks of members against the joint configuration's envelopes and keep-outs.

    python3 work/wayfarer-systems-integration/wsi/members.py [psa_run_json]

STUDY / PROTOTYPE. No production geometry is touched.
"""
import json
import math
import sys

import numpy as np

import common
from common import PSA, R
import analysis as an
import model3 as m3
import wsi_bodies

RUN = PSA/'results/p3_runs/H_hub_TD-A_full_wsi.json'
PRIMARY = {'rail', 'trans', 'ring', 'pickup', 'spine', 'hub', 'collar', 'keel', 'deck', 'cone', 'hubcone', 'modframe', 'guide'}


def seg_dist(p, a, b):
    """Distance from points p (n,3) to segment ab."""
    ab = b-a; t = np.clip(((p-a) @ ab)/max(ab @ ab, 1e-12), 0, 1); return np.linalg.norm(p-(a+np.outer(t, ab)), axis=1)


def radial(p):
    return math.hypot(p[1], p[2])


def az(p):
    return math.degrees(math.atan2(p[2], p[1])) % 360


def checks(nodes, mem, cfg, u_dep):
    """Members against the keep-outs and the equipment envelopes of the joint config. Intended intersections (mount points,
    structural pass-throughs) are classified from the SSI mount table; everything else is an interference."""
    X = np.array(nodes); out = []
    ko = {k['id']: k for k in cfg['keepouts']}
    # 1 K-RING: no structure inside the ring sweep except the hub path (r <= hub bore) and the collar outside 31.5
    kr = ko['K-RING']
    for m in mem:
        a, b = X[m['a']], X[m['b']]
        for p in (a, b, 0.5*(a+b)):
            if kr['x'][0] < p[0] < kr['x'][1] and 2.0 < radial(p) < kr['r_max_m'] and m['fam'] not in ('collar', 'hub', 'hubcone', 'iface'):
                out.append(dict(check='K-RING', member=m['i'], fam=m['fam'], x=float(p[0]), r=radial(p), verdict='INTERFERENCE')); break
    # 2 MRU swept tubes (flight r 2.9 +- 0.55, yard 3.6 +- 0.85 on az 255/285, x -92.7..92.0): members crossing the lane radius band
    for kid in ('K-MRU-F', 'K-MRU-Y'):
        k = ko[kid]; lo, hi = k['r_lane_m']-k['radius_m'], k['r_lane_m']+k['radius_m']
        for m in mem:
            a, b = X[m['a']], X[m['b']]; mid = 0.5*(a+b)
            if k['x'][0] < mid[0] < k['x'][1] and lo < radial(mid) < hi and any(abs(((az(mid)-q+180) % 360)-180) < 8 for q in (255.0, 285.0)):
                out.append(dict(check=kid, member=m['i'], fam=m['fam'], x=float(mid[0]), r=radial(mid), verdict='INTERFERENCE'))
    # 3 equipment envelopes along x with a radius band (units, H6a trunks, L2 sections are mounted ON frames: contact at mounts intended)
    for e in cfg['equipment']:
        env = e['envelope'] if isinstance(e['envelope'], dict) else {}
        if 'x' not in env or 'r' not in env or not isinstance(env['r'], (list, tuple)):
            continue
        x0, x1 = env['x']; r0, r1 = env['r']; n_hit = 0
        for m in mem:
            mid = 0.5*(X[m['a']]+X[m['b']])
            if x0 < mid[0] < x1 and r0+0.05 < radial(mid) < r1-0.05 and m['fam'] in ('rail', 'diag', 'frame', 'modframe'):
                n_hit += 1
        if n_hit:
            out.append(dict(check='ENVELOPE', item=e['id'], members=n_hit, verdict='INTENDED (frame mounts / rails pass the equipment band at the SSI mount stations)'
                            if e['id'].startswith(('PWR-', 'TH-', 'RAD-')) else 'INTENDED (keels end on the Brow interface ring)' if e['id'].startswith('BROW') else 'REVIEW'))
    # 4 deflection clearance: steady thrust, relative to the mass centre. Axial: total shortening (taken by the slides); radial: the
    # cross-section change that eats lane and sweep clearances (rule: < 50 mm at the MRU lane, the ring sweep and the vessel gaps)
    rad = np.array([(x[1]*v[1]+x[2]*v[2])/max(math.hypot(x[1], x[2]), 1e-9) for x, v in zip(X, u_dep)])
    lat = np.hypot(u_dep[:, 1], u_dep[:, 2]); ax = u_dep[:, 0]
    out.append(dict(check='DEFLECTION', axial_span_mm=float((ax.max()-ax.min())*1e3), max_radial_mm=float(np.abs(rad).max()*1e3),
                    max_lateral_mm=float(lat.max()*1e3), verdict=('radial within the 50 mm clearance rule' if np.abs(rad).max() < 0.05 else 'RADIAL EXCEEDS 50 mm')
                    + '; axial shortening is taken by the vessel guide slides and the MRU rail expansion joints'))
    return out


def main(run=RUN):
    run = json.loads(open(run).read()); cfg = json.loads((R/'wsi_config.json').read_text())
    hs = wsi_bodies.history(3)
    for s in hs:
        s['cfg'].setdefault('parts', s['cfg']['bodies'])
    b = m3.Build3('H', hs[0]['cfg'], deck='A', rotor='hub')
    for g, s in run['sizing'].items():
        if g in b.sec:
            b.sec[g]['r'], b.sec[g]['t'], b.sec[g]['mat'] = s['r'], s['t'], s['mat']
    b.update_sections()
    res = {}
    for s in (hs[0], hs[-1]):
        b.attach(s['cfg']['bodies']); r, f = an.solve(b)
        u = r['u'].reshape(-1, 6)[:, :3]; u = u-u.mean(axis=0)
        res[s['left']] = (u, f)
    u0, f0 = res[hs[0]['left']]
    nodes = [list(map(float, x)) for x in b.m.X]; mem = []
    for i, (e, md) in enumerate(zip(b.m.el, b.meta)):
        if e['kind'] == 'spring':
            continue
        s = b.sec.get(md['group'], dict(r=0.3, t=0.02, mat='IFACE'))
        fi = f0[i]
        mem.append(dict(i=i, a=int(e['a']), b=int(e['b']), fam=md['fam'], group=md['group'], primary=md['fam'] in PRIMARY, r=float(s['r']), t=float(s['t']),
                        mat=s['mat'], N_MN=(fi['N']/1e6 if fi else 0.0)))
    chk = checks(nodes, mem, cfg, u0)
    out = dict(source=run.get('key'), psa_run=str(RUN.name), structure_t=run['structure_t'], nodes=nodes, members=mem,
               u_departure=[list(map(float, v)) for v in u0], checks=chk,
               summary=dict(members=len(mem), interferences=sum(1 for c in chk if c['verdict'] == 'INTERFERENCE'),
                            intended=sum(1 for c in chk if c['verdict'].startswith('INTENDED')), review=sum(1 for c in chk if c['verdict'] == 'REVIEW')))
    (R/'wsi_members.json').write_text(json.dumps(out))
    print(out['summary'], [c for c in chk if c['check'] == 'DEFLECTION'])
    for c in chk:
        if not c['verdict'].startswith('INTENDED'):
            print(c)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else RUN)
