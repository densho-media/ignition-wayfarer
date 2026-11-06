"""Concept comparison driver: python3 study.py <name> [<name> ...]; writes results/<name>.json."""
import json, os, sys, time
from multiprocessing import Pool
import radmc as m, run_concept

CUR = dict(lw=21.0, ll=19.5, gap=2.0, gap2=2.0)
CONFIGS = {
    'base_baffled': dict(CUR, coat=m.GRAY90, blocker='annulus2x2'),
    'base_open': dict(CUR, coat=m.GRAY90, blocker='none'),
    'osr_open': dict(CUR, coat=m.OSR, blocker='none'),
    'B_wedge2_gray': dict(CUR, coat=m.GRAY90, blocker='wedge2'),
    'B_wedge1_gray': dict(CUR, coat=m.GRAY90, blocker='wedge1'),
    'C_wedge2_osr': dict(CUR, coat=m.OSR, blocker='wedge2'),
    'C_wedge1_osr': dict(CUR, coat=m.OSR, blocker='wedge1'),
    'C_wedge2outer_osr': dict(CUR, coat=m.OSR, blocker='wedge2', frac0=0.35),
    'C_annulus1_osr': dict(CUR, coat=m.OSR, blocker='annulus2'),
    'V3_gray': dict(lw=21.0, ll=19.5, gap2=0.5, coat=m.GRAY90, layers=[(0.5, 0), (0.8, 5), (1.1, 10)]),
    'V3_osr': dict(lw=21.0, ll=19.5, gap2=0.5, coat=m.OSR, layers=[(0.5, 0), (0.8, 5), (1.1, 10)]),
    'F3_gray': dict(lw=21.0, ll=19.5, gap2=0.5, coat=m.GRAY90, layers=[(0.5, 0), (0.8, 0), (1.1, 0)], diagonal=False),
    'V2_gray': dict(lw=21.0, ll=19.5, gap2=0.5, coat=m.GRAY90, layers=[(0.5, 0), (0.8, 8)]),
    'V3w_gray': dict(lw=21.0, ll=19.5, gap2=0.5, coat=m.GRAY90, layers=[(0.5, 0), (0.8, 8), (1.1, 16)]),
}
VG = [(0.5, 0), (0.8, 5), (1.1, 10)]
LAY = [m.REFRACTORY_HOTLAYER, m.MID_LAYER, m.GOLD_LAYER]
LAY_EOL = [m.REFRACTORY_EOL, m.MID_EOL, m.GOLD_EOL]
def cand(lw, ll, **k):
    d = dict(lw=lw, ll=ll, gap2=0.5, coat=m.WHITE, layers=VG, coats_b=LAY, root_strip=0.5); d.update(k); return d
CONFIGS.update({
    'S_21_195': cand(21.0, 19.5),
    'S_24_21': cand(24.0, 21.0),
    'S_26_22': cand(26.0, 22.0),
    'S_24_21_osrlow': cand(24.0, 21.0, coat_l=m.OSR),
    'F_final': cand(22.5, 20.0, clear=0.4),
    'F_eol': cand(22.5, 20.0, clear=0.4, coat=m.WHITE_EOL, coats_b=LAY_EOL),
    'F_postburn': cand(22.5, 20.0, clear=0.4, hot_T=1300.0),
    'F_coast': cand(22.5, 20.0, clear=0.4, hot_T=440.0),
    'G_final': cand(22.34, 20.0, clear=0.4),
    'G_eol': cand(22.34, 20.0, clear=0.4, coat=m.WHITE_EOL, coats_b=LAY_EOL),
})

if __name__ == '__main__':
    os.makedirs('results', exist_ok=True); pool = Pool(4)
    for name in sys.argv[1:]:
        t = time.time(); r = run_concept.run(CONFIGS[name], pool=pool); r['seconds'] = round(time.time()-t)
        json.dump(r, open(f'results/{name}.json', 'w'), indent=1)
        print(name, r['seconds'], 's | WARM net', r['WARM']['net_MW'], 'margin', r['WARM']['margin'], '| LOW net', r['LOW']['net_MW'],
              'margin', r['LOW']['margin'], '| sheets', r['sheets'], '| ringA', r.get('RING_A'), 'tanks', r.get('TANKS'), flush=True)
