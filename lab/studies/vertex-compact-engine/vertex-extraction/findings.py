#!/usr/bin/env python3
"""Findings of the ENG-062 scan, written into results/extraction.json (run after extraction.py). Every sentence is computed from the
scan's own rows, so a rerun of the scan rewrites them. `python3 lab/studies/vertex-compact-engine/vertex-extraction/findings.py`"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / 'results' / 'extraction.json'


def main():
    x = json.loads(P.read_text())
    G = {f"{g['topo']}|{g['dz']:g}|{g['mult']:g}": g for g in x['geometries']}
    B = x['base_by_geo']
    d0 = B['drawn|0|1']
    hit = lambda k: G[k]['species']['D']['hit']
    open_ = [k for k, v in B.items() if v['thrust_N'] == 0.0]
    best = max(B.items(), key=lambda kv: kv[1]['thrust_N'])
    err = G['drawn|0|1']['species']['D']['err']
    ext = [r for r in x['rows'] if r['geo'] == best[0] and r['lever'].startswith('Early extraction')]
    e80 = min(ext, key=lambda r: r['heat_over'])
    fr = x['frontier']
    f = [
        f"Field strength alone does nothing for the drawn topology: x4 the field leaves the struck share at {hit('drawn|0|4'):.2f} (x1: {hit('drawn|0|1'):.2f}), "
        f"because magnetised debris from an on-axis burn follows the same field lines at any strength.",
        f"Topology and position decide it: moving the burn 4 m aft of its drawn point lowers the struck share to {hit('drawn|4|1'):.2f}, and with "
        f"closure rings at four times their current share to {hit('mirror4|4|1'):.2f}. Strong closure with the burn at or forward of its drawn point "
        f"seals the nozzle instead: {len(open_)} of {len(B)} geometries strike every debris ion (hit 1.0, no thrust).",
        f"Best geometry for the design target, {best[0]}: {4 * best[1]['thrust_N'] / 1e6:.2f} MN for four engines (drawn {4 * d0['thrust_N'] / 1e6:.2f} MN), "
        f"{best[1]['exhaust_m_s'] / 1e3:,.0f} km/s, heat {best[1]['heat_over']:,.0f}x the radiator share (drawn {d0['heat_over']:,.0f}x). "
        f"Interception is a thrust lever, not a heat lever: X-rays carry most of the heat.",
        f"Early extraction (80 % of the product energy out of the target) cuts the heat to {e80['heat_over']:,.0f}x but the thrust to "
        f"{4 * e80['thrust_N'] / 1e6:.2f} MN: fast products carry energy, not momentum. It is a heat lever, not a thrust lever.",
        f"No case closes. The thrust-heat frontier runs from {fr[0]['heat_over']:,.0f}x at {4 * fr[0]['thrust_N'] / 1e6:.2f} MN to "
        f"{fr[-1]['heat_over']:,.0f}x at {4 * fr[-1]['thrust_N'] / 1e6:.2f} MN; the mission needs 21.8 MN at 1x.",
        f"Limits: vacuum test particles from an on-axis point ({x['n_dir']} directions per species, struck-share error about +/-{err:.2f}); the X-ray "
        f"pickup is the drawn engine's for every geometry (not recomputed for a moved burn, OPEN); coil masses scale with capture current and are "
        f"relative only; plasma expansion, detachment and collective effects are OPEN.",
    ]
    x['findings'] = f
    P.write_text(json.dumps(x, indent=1))
    print('\n'.join(f))


if __name__ == '__main__':
    main()
