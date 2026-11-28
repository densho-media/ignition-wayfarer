"""Review fields for the Blender file and the report: rebuilds a sized variant from results/p2_variants.json and writes
results/p2_review/<key>.json with nodes, members (family, primary/secondary, material, section, steady N, bending, torsion, group
utilisation, L3 module, thermal zone, mount zone), displacements for steady thrust and engine-out, and the members lost or
overloaded in the worst damage case.
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
import failure  # noqa: E402
import model as mdl  # noqa: E402

OUT = H.parent / 'results'
PRIMARY = {'rail', 'trans', 'ring', 'pickup', 'spine', 'hub', 'collar', 'keel', 'deck', 'cone', 'hubcone', 'modframe'}
THERMAL = [(-145.0, -113.0, 'DRIVE 350-500 K'), (-113.0, 41.0, 'HOT-LOOP SIDE 300-400 K'), (41.0, 93.6, 'WARM 300 K'), (93.6, 300.0, 'CRYO-SIDE 100-300 K')]


def zone(x):
    return next(n for a, b, n in THERMAL if a <= x < b)


def rebuild(key):
    V = json.loads((OUT / 'p2_variants.json').read_text())[key]
    cfg = configs.config(V['config'], 1.0)
    b = mdl.Build(V['concept'], cfg, rotor=V['rotor'])
    for g, s in V['sizing'].items():
        if g in b.sec:
            b.sec[g]['r'], b.sec[g]['t'] = s['r'], s['t']
    b.update_sections(); b.attach(cfg['parts'])
    return V, b


def main(keys):
    (OUT / 'p2_review').mkdir(parents=True, exist_ok=True)
    for key in keys:
        V, b = rebuild(key); dlf = V['dlf']
        r1, f1 = an.solve(b); r2, f2 = an.solve(b, out=0)
        # worst damage case from the study (lowest emergency thrust), re-run to list overloaded members
        dmg = sorted(V.get('damage', []), key=lambda d: d.get('f_emer', 1.0))
        worst = dmg[0] if dmg else None
        over = []
        if worst:
            for i in worst['off']:
                b.m.el[i]['on'] = False
            rd, fd = an.solve(b); ua = failure.utils(b, fd, dlf, 1.0); over = [int(i) for i in np.where(ua > 1.0)[0]]
            for i in worst['off']:
                b.m.el[i]['on'] = True
        mods = {}
        mem = []
        for i, (e, md) in enumerate(zip(b.m.el, b.meta)):
            if e['kind'] == 'spring':
                continue
            xa, xb = b.m.X[e['a']], b.m.X[e['b']]; xm = 0.5*(xa[0]+xb[0])
            s = b.sec.get(md['group'], dict(r=0.6, t=0.06, mat='IFACE'))
            f = f1[i]; g2 = f2[i]
            mod = int(math.floor((xm-mdl.X_TRANS)/(4.0*max(b.module_bays, 2)))) if mdl.X_TRANS <= xm <= mdl.X_CAGE_END else (-1 if xm < mdl.X_TRANS else 99)
            mem.append(dict(i=i, a=e['a'], b=e['b'], fam=md['fam'], primary=md['fam'] in PRIMARY, group=md['group'], r=s['r'], t=s['t'], mat=s['mat'],
                            N=f['N']*dlf/1e6 if f else 0.0, M=math.hypot(f['My'], f['Mz'])*dlf/1e6 if f else 0.0, T=abs(g2['T'])/1e6 if g2 else 0.0,
                            Meo=math.hypot(g2['My'], g2['Mz'])*dlf/1e6 if g2 else 0.0, util=V['sizing'].get(md['group'], {}).get('util', 0.0),
                            module=mod, thermal=zone(xm), lost=bool(worst and i in worst['off']), overloaded=i in over))
        u1 = r1['u'].reshape(-1, 6)[:, :3]*dlf; u2 = r2['u'].reshape(-1, 6)[:, :3]*dlf
        # remove the mean rigid translation for display (the free-free solution is relative to the mass centre)
        out = dict(key=key, concept=V['concept'], rotor=V['rotor'], config=V['config'], nodes=[list(map(float, x)) for x in b.m.X],
                   u_steady=u1.tolist(), u_engine_out=u2.tolist(), members=mem, worst_damage=worst['name'] if worst else None,
                   mounts=dict(rail_hardpoints=[n for x in b.xs for a, n in b.station_nodes[x].items() if a in b.rail_az()], deck=b.deck_nodes, brow=b.brow_nodes))
        (OUT / 'p2_review' / (key.replace(':', '_')+'.json')).write_text(json.dumps(out))
        print(key, len(mem), 'members; worst damage', out['worst_damage'], 'overloaded', len(over))


if __name__ == '__main__':
    main(sys.argv[1:] or ['H:hub:F1', 'HC:hub:F1'])
