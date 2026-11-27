"""District volume table from results/survey.json (pure; run after survey_blender.py)."""
import json
from pathlib import Path
R = Path(__file__).resolve().parent / 'results'
DISTRICTS = [('D1', 'Drive and thrust ring', -136.75, -133.25), ('D2', 'Aft engineering bay (feed, fab, Brayton A/B, stores)', -133.25, -89.5),
             ('D3', 'Mid-body dry store (BODY-C3 modules, CMG frames)', -89.5, 21.0), ('D4', 'Forward body under the hot blades', 21.0, 48.9),
             ('D5', 'RAD-ZONE casing (LOW/WARM sections, bulkhead)', 48.9, 93.4), ('D6', 'Rotor bay (rings A, B hubs)', 93.4, 108.8),
             ('D7', 'Forward collar / service zone (refuge, storeroom, airlock, docks)', 108.8, 141.75)]


def table():
    d = json.loads((R / 'survey.json').read_text()); cell = d['cell_m3']; out = []
    for i, n, a, b in DISTRICTS:
        t = {c: 0 for c in 'OFRUD'}
        for s in d['sections']:
            if a <= s['x'] < b:
                for c in t:
                    t[c] += s['counts'].get(c, 0)
        v = {c: round(t[c]*cell) for c in t}
        out.append(dict(id=i, name=n, x=[a, b], inside_casing_m3=sum(v.values()), occupied_m3=v['O'], reserved_m3=v['R'],
                        dry_store_m3=v['D'], free_m3=v['F']+v['U'], usable_m3=v['U']))
    return out


if __name__ == '__main__':
    t = table(); (R / 'districts.json').write_text(json.dumps(t, indent=1))
    for r in t:
        print(f"{r['id']} {r['name'][:44]:44s} {r['x'][0]:7.1f}..{r['x'][1]:6.1f}  in {r['inside_casing_m3']:6d}  occ {r['occupied_m3']:5d}  res {r['reserved_m3']:5d}  dry {r['dry_store_m3']:5d}  free {r['free_m3']:5d}  usable {r['usable_m3']:4d}")
    print('total', {k: sum(r[k] for r in t) for k in ('inside_casing_m3', 'occupied_m3', 'reserved_m3', 'dry_store_m3', 'free_m3', 'usable_m3')})
