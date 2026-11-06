"""Run one concept config: trace receivers and adiabatic sheets, solve sheet temperatures, report net rejection."""
import json, sys, time
from multiprocessing import Pool
import concepts, radmc as m

N = 20000


def _trace(args):
    cfg, name, n, seed = args
    sc, *_ = (concepts.build_v if 'layers' in cfg else concepts.build)(cfg)
    return name, sc.trace(name, n=n, seed=seed)


def run(cfg, n=N, extra=('RING_A', 'RING_B', 'TANKS'), pool=None):
    sc, loads, sheets, span = (concepts.build_v if 'layers' in cfg else concepts.build)(cfg)
    names = ['WARM', 'LOW']+list(sheets)+list(extra)
    jobs = [(cfg, nm, n, 11+i) for i, nm in enumerate(names)]
    res = dict((pool or Pool(4)).map(_trace, jobs))
    Ts = m.solve_adiabatic(sc, res, list(sheets)) if sheets else {}
    out = dict(cfg={k: (v if not isinstance(v, dict) else v['note']) for k, v in cfg.items()}, span=span, sheets={k: round(v, 1) for k, v in Ts.items()})
    for sec in ('WARM', 'LOW'):
        a = sc.absorbed_from(sec, res[sec]); e = sc.emitted(sec); self_ = a.pop(sec, 0.0)
        absorbed = sum(a.values()); net = e-self_-absorbed
        out[sec] = dict(area_m2=round(sc.groups[sec]['area']), emitted_MW=round(e/1e6, 3), self_MW=round(self_/1e6, 3),
                        absorbed_MW={k: round(v/1e6, 4) for k, v in a.items() if v > 1}, net_MW=round(net/1e6, 3),
                        load_MW=loads[sec]/1e6, margin=round(net/loads[sec]-1, 3), interference=round(absorbed/max(e-self_, 1), 3))
    for rec in extra:
        a = sc.absorbed_from(rec, res[rec]); out[rec] = {k: round(v/1e6, 3) for k, v in a.items() if v > 1e3}
    for sh in sheets:
        a = sc.absorbed_from(sh, res[sh]); out[sh+'_absorbed_MW'] = round(sum(v for k, v in a.items() if k != sh)/1e6, 2)
        out[sh+'_area_m2'] = round(sc.groups[sh]['area']/2)
    return out


if __name__ == '__main__':
    cfg = json.loads(sys.argv[1]); t = time.time()
    print(json.dumps(run(cfg), indent=1)); print('s', round(time.time()-t))
