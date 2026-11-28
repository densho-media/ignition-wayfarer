"""Phase III.0 rerun: size a variant on the corrected C1.1 representation (TD-A or another deck), then stability over the depletion
states. Writes results/p3_runs/<key>.json.   python3 run3.py H A hub [n_states]"""
import json, sys, time
from pathlib import Path
import numpy as np
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H)); sys.path.insert(0, str(H.parent / 'phase2'))
import analysis as an, analysis3 as a3, c11, model3 as m3, wsi_bodies
OUT = H.parent / 'results' / 'p3_runs'; OUT.mkdir(parents=True, exist_ok=True)

def hist(n, src='c11'):
    if src == 'wsi':
        return wsi_bodies.history(n)
    h = c11.history(n)
    for s in h:
        s['cfg']['parts'] = s['cfg']['bodies']
    return h

def evaluate(hs, concept='H', deck='A', rotor='hub', iters=4, stability=('static', 'follower'), log=print, check='full', K=1.0, **kw):
    """Public entry point (WSI coupled loop): hs = depletion history, a list of dict(left, M_kg, a, cfg) where cfg carries
    bodies (c11.body records), farm, brow and thrust; hs[0] is departure. Builds the structure on the departure bodies, sizes it
    over every state (strength, 4 passes) and returns structure mass and static / follower lambda per state (x operating thrust)."""
    t0 = time.time(); key = f'{concept}:{rotor}:TD-{deck}:{check}'
    for s in hs:
        s['cfg'].setdefault('parts', s['cfg']['bodies'])
    b = m3.Build3(concept, hs[0]['cfg'], deck=deck, rotor=rotor, **kw)
    b.attach(hs[0]['cfg']['bodies']); mc = b.mass_check(hs[0]['cfg']['bodies'])
    res = an.run(b, hs, iters=iters, log=log) if check == 'p2' else a3.run3(b, hs, iters=iters, K=K, log=log)
    sm, by = b.structure_mass()
    out = dict(key=key, mass_check=mc, members_t=sm/1e3, joints_t=res['joints_t'], structure_t=sm/1e3+res['joints_t'],
               by_family_t={k: v/1e3 for k, v in by.items()}, failing=[g for g, s in res['sizing'].items() if not s['passes']],
               sizing=res['sizing'], dlf=res['cases'][0]['dlf'], f_axial=res['cases'][0]['f_axial'])
    # deck groups mass
    out['deck_t'] = sum(v for k, v in out['by_family_t'].items() if k in ('deck',))
    out['tankwall_credit_t'] = b.tank_credit_t()
    out['psa_increment_t'] = out['structure_t'] - out['tankwall_credit_t']   # TD-E: credited shell already in the tankage ledger
    st = []
    for s in hs:
        b.attach(s['cfg']['bodies'])
        for nm, part in [c for c in (('static', 0.0), ('follower', 1.0)) if c[0] in stability]:
            g = an.global_stability(b, partial=part)
            st.append(dict(left=s['left'], case=nm, lam=g.get('lam'), kind=g.get('kind'), f1=g.get('f1'), groups=g.get('mode_groups', {})))
            log(f"  left {s['left']:.2f} {nm}: lambda {g.get('lam')} {g.get('kind')} f1 {g.get('f1')}")
    out['stability'] = st; out['seconds'] = time.time()-t0
    return out, b


def main(concept, deck, rotor, n=3, check='full', src='c11'):
    hs = hist(n, src); out, b = evaluate(hs, concept, deck, rotor, check=check); key = out['key'] + ('' if src == 'c11' else ':'+src)
    out['key'] = key; out['source'] = hs[0]['cfg']['id']
    (OUT / (key.replace(':', '_')+'.json')).write_text(json.dumps(out, indent=1, default=float))
    print(key, f"members {out['members_t']:.1f} t joints {out['joints_t']:.1f} deck {out['deck_t']:.1f} failing {out['failing']} {out['seconds']:.0f} s")

if __name__ == '__main__':
    a = sys.argv[1:]; main(a[0], a[1], a[2], int(a[3]) if len(a) > 3 else 3, a[4] if len(a) > 4 else 'full', a[5] if len(a) > 5 else 'c11')
