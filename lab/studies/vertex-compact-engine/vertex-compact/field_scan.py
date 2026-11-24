#!/usr/bin/env python3
"""Field-multiple scan for the Fusion Ignition page's experiment mode (research, not canon). For each compact variant geometry (C1, C3)
and closure-field multiple x1, x2, x4: axial efficiency, charged hit share, sky and piped heat (ron.evaluate, the same call compact.py
makes, quick 48 directions). Writes results/field_scan.json; the lab study fusion-ignition copies it once into its imports."""
import json
import math
import sys
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.argv.append('--quick')
import compact as C  # noqa: E402

def main():
    k = C.ron.canon(); xb1 = C.SHIP['x_burn']; xb3 = xb1 - 36.0
    D1, D3 = C.SHIP['tank'][0] - xb1, C.SHIP['tank'][0] - xb3
    tan3 = math.tan(math.atan((C.PITCH + C.SHIP['tank'][2]) / D3) + math.radians(C.CANT)) * 1.05
    V = dict(C1=C.variant('C1', D1, 6.0, 0.62), C3=C.variant('C3', D3, 12.0, 0.013, shield_tan=tan3))
    out = {}
    with Pool(4) as pool:
        for key, (p, sh) in V.items():
            v, src, E, cap = C.ron.configure(p, k)
            for m in (1.0, 2.0, 4.0):
                r = C.ron.evaluate(v, k, src, E, cap, m, pool, C.N)
                led = r['ledger']
                out[f'{key}|{m:g}'] = dict(eta=r['particles']['axial_efficiency'], hit=r['particles']['hit_energy_share'],
                                           sky=led['sky_total'], piped_four_W=4 * led['B01_W'], over=4 * led['B01_W'] / k['drive_W'])
                print(key, m, out[f'{key}|{m:g}'], flush=True)
    (HERE / 'results' / 'field_scan.json').write_text(json.dumps(out, indent=1))

if __name__ == '__main__':
    main()
