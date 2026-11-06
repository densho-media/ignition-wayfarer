import json, sys
from multiprocessing import Pool
import concepts, radmc as m
CFG = dict(coat=m.GRAY90, beta=float(sys.argv[1]), chord=4.0, pitch=float(sys.argv[2]), lw=21, ll=19.5, gap=2, gap2=2)
def tr(nm):
    sc, *_ = concepts.build_gill(CFG); return nm, sc.trace(nm, n=20000, seed=5)
if __name__ == '__main__':
    sc, loads, _, sp = concepts.build_gill(CFG)
    names = ['WARM', 'WARM_BACK', 'LOW', 'LOW_BACK', 'RING_A', 'TANKS']
    res = dict(Pool(4).map(tr, names)); out = dict(cfg=dict(beta=CFG['beta'], pitch=CFG['pitch']), span=sp)
    for sec in ('WARM', 'LOW'):
        e = 0; ab = 0; selfx = 0
        for g in (sec, sec+'_BACK'):
            a = sc.absorbed_from(g, res[g]); e += sc.emitted(g)
            selfx += a.get(sec, 0)+a.get(sec+'_BACK', 0); ab += sum(v for k, v in a.items() if k not in (sec, sec+'_BACK'))
        out[sec] = dict(emitted_MW=e/1e6, net_MW=(e-selfx-ab)/1e6, absorbed_MW=ab/1e6, front_area=sc.groups[sec]['area'])
    for r in ('RING_A', 'TANKS'):
        out[r] = {k: round(v/1e6, 3) for k, v in sc.absorbed_from(r, res[r]).items() if v > 1e3}
    print(json.dumps(out, indent=1)); json.dump(out, open(f'results/A_gill_{int(CFG["beta"])}_{CFG["pitch"]}.json', 'w'), indent=1)
