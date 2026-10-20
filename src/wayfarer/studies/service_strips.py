"""SERV-STRIPS-2026-10-10 (15!A119, 98!A86): inventory of the sector faces served only by a shirt-sleeve strip.

The owner treats the 0.60 m strips as SHIRT-SLEEVE-ONLY maintenance access (suited_access = false), and asks Claude to catalogue the units
behind them and flag those that would need suited access with no alternative. This lists, per sector function, every clear volume whose
narrow side is under the 0.70 m suited envelope (sector_whitebox.clear_volumes), the block it serves, its zone and the 12A spaces the program
places in that zone. The service assessment is in references/SERVICE_STRIPS.md. Pure standard library.

    python3 src/wayfarer/studies/service_strips.py
"""
from pathlib import Path
import json
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer')]
from spec import load
import habitat_interior
import sector_whitebox


def inventory(s):
    out = []; program = s['sector_whitebox']['program']
    for fn in s['habitat']['layout']['functions']:
        blocks = {b['name']: b for b in habitat_interior.zones(s, fn)}
        for q in sector_whitebox.clear_volumes(s, fn):
            if q['suited_access'] or q['kind'] not in ('access strip', 'couch strip'):
                continue
            b = blocks.get(q['name'].removesuffix('_Strip').removesuffix('_Free'))
            zone = b['zone'] if b else None
            sps = [p['sp'] for p in program.get(fn, []) if zone in p.get('zones', [])]
            out.append(dict(function=fn, strip=q['name'], kind=q['kind'], block=b['name'] if b else None, zone=zone, spaces=sps,
                            width_m=round(min(q['max'][k]-q['min'][k] for k in (0, 2)), 3), suited_access=False))
    return out


if __name__ == '__main__':
    print(json.dumps(inventory(load(ROOT)[0]), indent=1))
