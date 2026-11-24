"""R scan below the optimiser's 15 m bound at the B today optimum (other variables fixed). Writes results/rscan.json."""
import json, sys
from multiprocessing import Pool
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'vertex-ron')); sys.path.insert(0, str(HERE))
import ron, optimize as O
k = ron.canon(); rows = []
with Pool(2) as pool:
    for R in (6.0, 8.0, 10.0, 12.0, 15.0, 20.0):
        r = O.evaluate('B', [R, 2.28, 1910.0, 767.0, 1.19], k, pool, n=320)
        if 'error' in r:
            print(R, r['error']); continue
        rows.append(dict(R=R, departure_t=r['departure_t'], engine_t=r['engine_t'], eta=r['eta'], cant=r['cant_deg'], self_W=r['self_W'],
                         nose_t=r['mass_t'].get('nose_t'), fins_t=r['mass_t'].get('fins_t'), dust_t=r['add_t']['dust_protection_t'],
                         eddy_W=r['heat_W'].get('eddy_shield_W'), field_ratio=r['field_ratio']))
        print({kk: (round(v, 3) if isinstance(v, float) else v) for kk, v in rows[-1].items()}, flush=True)
(HERE/'results'/'rscan.json').write_text(json.dumps(rows, indent=1))
