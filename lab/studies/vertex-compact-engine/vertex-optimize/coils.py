#!/usr/bin/env python3
"""ENG-067/068: closure-coil engineering and the 3D consequences of the moved burn (research, not canon).

Reads results/optimize.json (the chosen geometry) and writes results/coils.json:
  - four coil cases with optimize.coil_engineering(): the drawn engine as built (k = 1, the field the 3D engine carries), the drawn engine
    at its capture current, the optimised geometry at its capture current and the optimised geometry at the as-built current scale (the
    research geometry drawn in Blender: closure ampere-turns x fc, loops as built);
  - the drawn research geometry in the engine frame: burn x, each coil's winding and cryostat minor radius at the as-built current density
    (winding area scales with ampere-turns), the hoop band each needs, and clearances between neighbouring cryostats and to the shield;
  - the re-aim of the thermal study's source-aligned blades (strategy B) to the moved burn: the angle each blade turns.

    python3 lab/studies/vertex-compact-engine/vertex-optimize/coils.py
"""
import json
import math
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
import optimize as O  # noqa: E402
import vertex_engine as ve  # noqa: E402

ron = O.ron


def main():
    R = json.loads((HERE / 'results' / 'optimize.json').read_text())
    best = next(g for g in R['geometries'] if g['key'] == R['best'])
    k = ron.canon()
    vd, _, _, capd = ron.configure(O.geometry('drawn|0', 0.0, 1.0), k)
    vb, _, _, capb = ron.configure(O.geometry(best['key'], best['dz'], best['fc'], best['grade'], best['aft_space']), k)
    s = tomllib.loads((ROOT / 'data/wayfarer_3d.toml').read_text())
    st = ve.stations(s)
    names = ['C1', 'C2', 'L1', 'L2', 'L3', 'L4']; ring = {n: f'RING_{i + 1}' for i, n in enumerate(names)}
    wm0 = {c['name']: c['winding_minor_m'] for c in st['coils'] + st['loops']}
    grade = best['grade'] or [best['fc']] * 3
    fac = dict(zip(names[:3], grade))

    def minor(kk, opt):                       # round windings at the drawn engine's current density: area scales with ampere-turns
        return {ring[n]: wm0[n] * math.sqrt(kk * (fac.get(n, 1.0) if opt else 1.0)) for n in names}
    cases = [O.coil_engineering(vd, 1.0, 'Drawn engine as built (the field the 3D engine carries)', minor(1.0, False)),
             O.coil_engineering(vd, capd['k'], 'Drawn engine at its capture current', minor(capd['k'], False)),
             O.coil_engineering(vb, capb['k'], f'Optimised ({best["label"]}) at its capture current', minor(capb['k'], True)),
             O.coil_engineering(vb, 1.0, f'Optimised ({best["label"]}) at the as-built current scale (the drawn research geometry)', minor(1.0, True))]
    for c in cases:
        c['id'] = ('built', 'drawn_capture', 'opt_capture', 'opt_built')[cases.index(c)]
    # engine frame research geometry
    bx0 = st['burn']; bx1 = bx0 - best['dz']
    eng = []
    cb = {r['name']: r for r in cases[3]['coils']}
    ringmap = dict(zip(['C1', 'C2', 'L1', 'L2', 'L3', 'L4'], ['RING_1', 'RING_2', 'RING_3', 'RING_4', 'RING_5', 'RING_6']))
    for c in st['coils'] + st['loops']:
        f = fac.get(c['name'], 1.0)
        wm = c['winding_minor_m'] * math.sqrt(f)
        gap = c['cryostat_minor_m'] - c['winding_minor_m']
        ce = cb[ringmap[c['name']]]
        A = ce['structure_m2']                                  # hoop structure cross-section, m2 (1.5 GPa allowable)
        width = 1.6 * wm; band_t = A / width
        eng.append(dict(name=c['name'], x=c['x'], r=c['r'], factor=f, winding_minor_m=wm, cryostat_minor_m=wm + gap + band_t,
                        band_width_m=width, band_t_m=band_t, hoop_MN=ce['hoop_MN'], B_peak_T=ce['B_peak_T'], Fx_MN=ce['Fx_MN'],
                        drawn_winding_minor_m=c['winding_minor_m'], drawn_cryostat_minor_m=c['cryostat_minor_m']))
    clear = []
    for a, b in zip(eng, eng[1:]):
        d = math.hypot(a['x'] - b['x'], a['r'] - b['r'])
        clear.append(dict(pair=f'{a["name"]}-{b["name"]}', gap_m=d - a['cryostat_minor_m'] - b['cryostat_minor_m'],
                          drawn_gap_m=d - a['drawn_cryostat_minor_m'] - b['drawn_cryostat_minor_m']))
    c1 = eng[0]
    clear.append(dict(pair='C1-shield', gap_m=(st['shield_aft'] - c1['x']) - c1['cryostat_minor_m'],
                      drawn_gap_m=(st['shield_aft'] - c1['x']) - c1['drawn_cryostat_minor_m']))
    # blades: re-aim each strategy-B blade edge at the moved burn
    T = json.loads((HERE.parent / 'vertex-thermal' / 'results' / 'thermal.json').read_text())
    turn = []
    for g in T['geometry']:
        if g['layer'] in ('mirror_B', 'blades') and g['kind'] == 'ribbon':
            for a, b in zip(g['a'], g['b']):
                u0 = [b[i] - a[i] for i in range(3)]; L = math.sqrt(sum(q * q for q in u0))
                t = [(bx1 if i == 0 else 0.0) - a[i] for i in range(3)]; Lt = math.sqrt(sum(q * q for q in t))
                cs = sum(u0[i] * t[i] for i in range(3)) / (L * Lt)
                turn.append(math.degrees(math.acos(max(-1, min(1, cs)))))
    out = dict(cls='CALCULATED', source='lab/studies/vertex-compact-engine/vertex-optimize/coils.py', best=best['key'], burn_x_drawn=bx0,
               burn_x_moved=bx1, cases=cases, research_geometry=eng, clearances=clear,
               blades=dict(n_edges=len(turn), max_turn_deg=max(turn) if turn else 0.0, mean_turn_deg=sum(turn) / len(turn) if turn else 0.0))
    (HERE / 'results' / 'coils.json').write_text(json.dumps(out, indent=1))
    for c in cases:
        print(f"{c['id']:14s} W {c['stored_J'] / 1e9:8.1f} GJ  B_burn {c['B_burn_T']:5.2f} T  B_wind {c['B_peak_max_T']:6.1f} T  hoop {c['hoop_total_MN'] / 1e3:7.1f} GN "
              f"struct {c['structure_t']:7.0f} t  cond {c['conductor_t']:6.0f} t  Fx max {c['Fx_max_MN']:8.0f} MN  dump {c['quench_dump_s']:7.0f} s  Cu {c['quench_copper_t']:6.0f} t")
    for e in eng:
        print(e['name'], round(e['winding_minor_m'], 2), round(e['cryostat_minor_m'], 2), 'band', round(e['band_t_m'], 3))
    print(clear); print(out['blades'])


if __name__ == '__main__':
    main()
