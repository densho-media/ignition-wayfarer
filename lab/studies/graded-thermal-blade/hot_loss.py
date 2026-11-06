"""Hot-blade rejection lost to each blocker: trace the HOT group (band 0..2, gray 0.9) with and without the blocker."""
import json
from multiprocessing import Pool
import concepts, radmc as m, study, numpy as np
CASES = ['base_open', 'base_baffled', 'F_final']
def tr(name):
    cfg = study.CONFIGS[name]; b = concepts.build_v if 'layers' in cfg else concepts.build
    sc, *_ = b(cfg); G = sc.trace('HOT', n=60000, seed=3, bands=[0])
    return name, dict(space=float(G[0, -1]), self=float(G[0, sc.names.index('HOT')]), other={k: float(G[0, i]) for i, k in enumerate(sc.names) if G[0, i] > 1e-4 and k != 'HOT'})
if __name__ == '__main__':
    r = dict(Pool(3).map(tr, CASES)); json.dump(r, open('results/hot_loss.json', 'w'), indent=1); print(json.dumps(r, indent=1))
