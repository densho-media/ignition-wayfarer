"""The reference lens on the second Phase 2B gate (ds2b_gate.py): an epsilon-Pareto front counts differences that stay far below every
reference as trades. This pass asks the sharper question a trainee faces: which strategies keep every person inside every reference
(CO2 under the 0.5 % control limit; NH3 1 h, 24 h and 7 d means under the SMACs), and among those, is there still a real choice?

    python3 work/project-thread-dfyyv7/ds2b_lens.py      # about 25 min on 4 cores; writes ds2b_lens.json

Same model, same strategies, same scenario values as ds2b_gate.py; nothing tuned.
"""
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ds2b_gate as g   # noqa: E402

KEYS24 = ('r1', 'r24', 'dose', 'co2_ch', 'r7d', 'restore_h')


def within(r):
    o = r['obj'][24]
    return r['viable'][24] and o['r1'] < 1.0 and o['r24'] < 1.0 and o['r7d'] < 1.0


def lens(rows):
    W = [r for r in rows if within(r)]
    out = dict(within=len(W), within_contain=sum(r['strat']['contain'] for r in W),
               within_families=sorted({g.family(r['strat']) for r in W}))
    if not W:
        # nothing keeps everyone inside every reference: what is the least bad, by the worst ratio?
        best = min(rows, key=lambda r: (not r['viable'][24], max(r['obj'][24][k] for k in ('r1', 'r24', 'r7d'))))
        out['least_exceedance'] = g.summarise(best, 24)
        return out
    obj = [r['obj'][24] for r in W]
    F = [r for r, o in zip(W, obj) if not any(g.dominates(q, o, KEYS24, g.EPS) for q in obj if q is not o)]
    fams = {}
    for r in F:
        f = g.family(r['strat'])
        # one representative per family: the member with the lowest worst ratio, then the shortest restoration
        if f not in fams or (max(r['obj'][24][k] for k in ('r1', 'r24', 'r7d')), r['obj'][24]['restore_h']) < \
                (max(fams[f]['obj'][24][k] for k in ('r1', 'r24', 'r7d')), fams[f]['obj'][24]['restore_h']):
            fams[f] = r
    out['front'] = len(F)
    out['front_families'] = {f: g.summarise(r, 24) for f, r in sorted(fams.items())}
    ideal = {k: min(o[k] for o in obj) for k in KEYS24}
    out['ideal'] = {k: round(v, 3) for k, v in ideal.items()}
    out['trivial'] = sum(1 for o in obj if all(o[k] <= ideal[k] + g.EPS[k] for k in KEYS24))
    # the two axes that separate the families: the 24 h burden (crew NH3 and CO2 above target) against how soon the ring is clean
    out['restore_range_h'] = (min(r['obj'][24]['restore_h'] for r in F), max(r['obj'][24]['restore_h'] for r in F))
    return out


def main():
    t0 = time.time()
    out = {}
    with mp.Pool(4) as pool:
        cases = {'base': {}}
        cases.update(g.sensitivities())
        for name, d in cases.items():
            sc = dict(g.BASE, **d)
            rows = g.search(sc, pool)
            out[name] = lens(rows)
            print(f"{name}: within {out[name]['within']} (contain {out[name]['within_contain']}), "
                  f"families {len(out[name].get('front_families', {}))}, trivial {out[name].get('trivial')}", flush=True)
            g._C1.clear(); g._C2.clear()
    out['elapsed_s'] = round(time.time() - t0)
    (HERE / 'ds2b_lens.json').write_text(json.dumps(out, indent=1, default=list) + '\n')


if __name__ == '__main__':
    main()
