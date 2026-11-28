"""Stability-only rerun of a sized variant: apply the sections saved in results/p3_runs/<key>.json and sweep static / follower
lambda over the depletion states.   python3 stab3.py <json> [n_states]"""
import json, sys, time
from pathlib import Path
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H)); sys.path.insert(0, str(H.parent / 'phase2'))
import analysis as an, model3 as m3, run3


def apply_sizing(b, sizing):
    for g, s in sizing.items():
        if g in b.sec:
            b.sec[g]['r'], b.sec[g]['t'], b.sec[g]['mat'] = s['r'], s['t'], s['mat']
    b.update_sections()


def stability(b, hs, cases=(('static', 0.0), ('follower', 1.0)), log=print):
    st = []
    for s in hs:
        b.attach(s['cfg']['bodies'])
        for nm, part in cases:
            g = an.global_stability(b, partial=part)
            st.append(dict(left=s['left'], case=nm, partial=part, lam=g.get('lam'), kind=g.get('kind'), f1=g.get('f1'),
                           groups=g.get('mode_groups', {})))
            log(f"  left {s['left']:.2f} {nm}: lambda {g.get('lam')} {g.get('kind')} f1 {g.get('f1')}")
    return st


if __name__ == '__main__':
    p = Path(sys.argv[1]); n = int(sys.argv[2]) if len(sys.argv) > 2 else 3; t0 = time.time()
    out = json.loads(p.read_text()); concept, rotor, deck = out['key'].split(':')[:3]
    hs = run3.hist(n, 'wsi' if out['key'].endswith(':wsi') else 'c11'); b = m3.Build3(concept, hs[0]['cfg'], deck=deck.replace('TD-', ''), rotor=rotor)
    apply_sizing(b, out['sizing']); out['stability'] = stability(b, hs); out['stability_seconds'] = time.time()-t0
    out['stability_note'] = 'rerun after the Phase III conditioning fix (near-coincident links as rigid springs, Cholesky standard form)'
    p.write_text(json.dumps(out, indent=1, default=float)); print(p.name, f'{time.time()-t0:.0f} s')
