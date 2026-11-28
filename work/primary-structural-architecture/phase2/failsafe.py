"""D03 redundancy penalty: resize a strength-sized variant so that it survives the loss of any one rail bay (and, as a second
target, one rail joint) and keeps carrying thrust. Two targets:
  EMERGENCY  damaged structure at 50 % thrust, accidental factor 1.0 on design allowables (survive and limp home)
  NOMINAL    damaged structure at 100 % thrust with the full ultimate factor 1.4 (keep operating after damage)
The intact limit envelope is always kept. The added mass is the redundancy penalty of that topology.

    python3 work/primary-structural-architecture/phase2/failsafe.py H:hub:F1 H3:hub:F1
"""
import json
import sys
from pathlib import Path

import numpy as np

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import analysis as an  # noqa: E402
import configs  # noqa: E402
import failure  # noqa: E402
import model as mdl  # noqa: E402

OUT = H.parent / 'results'
XS = [-111.25, -55.25, 0.75, 56.75, 84.75]


def sized(key):
    V = json.loads((OUT / 'p2_var' / (key.replace(':', '_')+'.json')).read_text())
    cfg = configs.config(V['config'], 1.0)
    b = mdl.Build(V['concept'], cfg, rotor=V['rotor'])
    for g, s in V['sizing'].items():
        if g in b.sec:
            b.sec[g]['r'], b.sec[g]['t'] = s['r'], s['t']
    b.update_sections(); b.attach(cfg['parts'])
    return V, b, configs.history(V['config'], 3)


def damage_sets(b, joints=False):
    rails = b.rail_az(); out = []
    for x in XS:
        out.append((f'rail bay X {x:+.0f}', failure.rail_members_at(b, x, rails[0])))
        if joints:
            k = min(range(len(b.xs)), key=lambda i: abs(b.xs[i]-x)); out.append((f'rail joint X {b.xs[k]:+.0f}', failure.node_members(b, b.station_nodes[b.xs[k]][rails[0]])))
    return out


def run(key, target, joints=False, iters=3):
    V, b, hist = sized(key); dlf = V['dlf']
    f_thr, fac = (0.5, 1.0) if target == 'EMERGENCY' else (1.0, an.LF_ULT)
    m0 = b.structure_mass()[0]/1e3; log = []
    for it in range(iters):
        cs = an.cases(b, hist); env = an.envelope(b, cs)
        worst = []
        for name, off in damage_sets(b, joints):
            for i in off:
                b.m.el[i]['on'] = False
            b.attach(hist[0]['cfg']['parts']); r, fs = an.solve(b, T=hist[0]['cfg']['thrust']*f_thr)
            for i, fx in enumerate(fs):
                if fx is None:
                    continue
                sc = dlf*fac/an.LF_ULT                 # check() applies 1.4; the accidental target needs fac
                N = sc*fx['N']; M = abs(sc)*np.hypot(fx['My'], fx['Mz'])
                env['Nc'][i] = max(env['Nc'][i], -N); env['Nt'][i] = max(env['Nt'][i], N); env['M'][i] = max(env['M'][i], M)
            for i in off:
                b.m.el[i]['on'] = True
        rep = an.size(b, env); m = b.structure_mass()[0]/1e3
        log.append(dict(iter=it+1, members_t=m, at_max=[g for g, v in rep.items() if not v['passes']]))
        print(f'{key} {target} pass {it+1}: members {m:.1f} t (intact {m0:.1f} t)')
    # verify: rerun every damage case and classify
    b.attach(hist[0]['cfg']['parts'])
    checks = [dict(name=n, **{k: v for k, v in failure.damaged(b, off, dlf).items() if k in ('u_nom', 'f_emer', 'class', 'collapse_chain')}) for n, off in damage_sets(b, True)]
    by = {k: v/1e3 for k, v in b.structure_mass()[1].items()}
    return dict(key=key, target=target, intact_members_t=m0, failsafe_members_t=m, penalty_t=m-m0, passes=log, verify=checks, by_family_t=by)


if __name__ == '__main__':
    keys = sys.argv[1:] or ['H:hub:F1', 'H3:hub:F1']
    p = OUT / 'p2_failsafe.json'; res = json.loads(p.read_text()) if p.exists() else {}
    for k in keys:
        for tgt in ('EMERGENCY', 'NOMINAL'):
            r = run(k, tgt); res[f'{k}|{tgt}'] = r
            p.write_text(json.dumps(res, indent=1, default=float))
            print(k, tgt, 'penalty', round(r['penalty_t'], 1), 't;', [(c['name'], c['class']) for c in r['verify']])
