#!/usr/bin/env python3
"""Spacecraft-level integration (research, not canon): what each stern protection option does to the B-today departure mass.

The AMPN trade (lab/studies/vertex-compact-engine/vertex-ampn/trade.py) counts the passive stern screen inside its dust mass. Here each HIMS option replaces that
screen: the difference in stern-stack mass (results/hims.json) is added to the dry mass through the same ship model (ron.ship), for both
dust cases. `python3 lab/studies/vertex-compact-engine/vertex-hims/integrate.py` writes results/integration.json and results/integration.md.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AMPN = HERE.parent / 'vertex-ampn'
sys.path.insert(0, str(HERE.parent / 'vertex-ron')); sys.path.insert(0, str(AMPN))
import ron  # noqa: E402
import dust  # noqa: E402

KEY = 'B_today'


def main():
    k = ron.canon()
    b = json.loads((AMPN / 'results' / 'optimize.json').read_text())[KEY]
    c = json.loads((AMPN / 'results' / 'coilpack.json').read_text())[KEY]
    h = json.loads((HERE / 'results' / 'hims.json').read_text())
    eng = c['engine_full_t'] - c['extra_t']['carriage_locks_actuators_t']
    R, kap, D, S = b['x'][:4]
    dn = b['add_t']['dust_protection_t'] * 4
    dj, _ = dust.dust_mass_t(R, b['plug_r_m'], S, D, case='JUSTIFIED')

    def ship(extra_t):
        return ron.ship(k, eng + extra_t / 4, 4 * b['piped_W'], max(0.05, b['eta']), cant_deg=b['cant_deg'])
    rows = []
    for case, base_extra in (('NOMINAL', 0.0), ('JUSTIFIED', dj - dn)):
        opts = h['cases'][case]['options']
        ref = next(o for o in opts if o['name'].startswith('PASSIVE'))
        ref_dep = ship(base_extra)['departure_t']
        for o in opts:
            if not o.get('closes'):
                rows.append(dict(case=case, option=o['name'], closes=False)); continue
            d = o['mass_t'] - ref['mass_t']
            s = ship(base_extra + d)
            rows.append(dict(case=case, option=o['name'], closes=True, standoff_m=o['standoff_m'], stack_t=o['mass_t'], delta_stack_t=d,
                             dry_t=s['dry_t'], departure_t=s['departure_t'], delta_departure_t=s['departure_t'] - ref_dep,
                             ratio_to_canon=s['departure_t'] / 4426.07))
    (HERE / 'results' / 'integration.json').write_text(json.dumps(rows, indent=1))
    L = ['| Case | Stern option | Stand-off m | Stack t | Delta stack t | Dry t | Departure t | Delta departure t | x canon |',
         '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for r in rows:
        if r['closes']:
            L.append(f"| {r['case']} | {r['option']} | {r['standoff_m']:.1f} | {r['stack_t']:.1f} | {r['delta_stack_t']:+.1f} | {r['dry_t']:,.0f} | "
                     f"{r['departure_t']:,.0f} | {r['delta_departure_t']:+,.0f} | {r['ratio_to_canon']:.2f} |")
        else:
            L.append(f"| {r['case']} | {r['option']} | n/a | | | | | | does not close |")
    (HERE / 'results' / 'integration.md').write_text('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
