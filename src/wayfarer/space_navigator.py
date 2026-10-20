"""WAYFARER Space Navigator, Stage 2 (S&E 55 SPACE-015/017/019/030): the Solar System chart's reference registry for the rig.
Standard library only. data/space_navigator.toml holds the Sun, the eight planets and the Kuiper Belt's main region as published references
(NASA fact sheets) with their retrieval dates; this module validates them and emits the rig's `space_navigator` block (sim_rig v40).

The chart owns no fact and places nothing at a date. A body carries sizes and orbit shapes only; an epoch, longitude, anomaly or position
field is refused (SPACE-010/016: no planet arrangement before the owner releases an epoch and ephemerides). AU values are DERIVED from the
listed 10^6 km with the IAU 2012 exact astronomical unit. The display transforms are named and invertible (C-004, C-012).
"""
from pathlib import Path
import math
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[2]
PLACING_KEYS = {'epoch', 'longitude', 'mean_longitude', 'anomaly', 'mean_anomaly', 'true_anomaly', 'position', 'x', 'y', 'z',
                'argument_of_perihelion', 'ascending_node', 'phase', 'date', 'ra', 'dec'}
PLANET_KEYS = ('diameter_km', 'distance_1e6km', 'perihelion_1e6km', 'aphelion_1e6km', 'period_days', 'eccentricity', 'inclination_deg')


def load(root=ROOT):
    return tomllib.loads((root / 'data/space_navigator.toml').read_text())


def _au(km_1e6, au_km):
    return km_1e6 * 1e6 / au_km


def sqrt_distance(a_au, a_ref, r_px):
    """PRESENTATION distance transform and its inverse (C-004)."""
    return r_px * math.sqrt(a_au / a_ref)


def sqrt_distance_inverse(px, a_ref, r_px):
    return a_ref * (px / r_px) ** 2


def contract(reg):
    space, refs = reg['space'], reg['reference']
    au_km = float(space['au_km'])
    assert space['au_ref'] in refs, 'space navigator: the AU reference is missing'
    ids, bodies = set(), []
    for b in reg['body']:
        assert b['id'] not in ids, f"space navigator: duplicate body {b['id']}"
        ids.add(b['id'])
        bad = PLACING_KEYS & set(b)
        assert not bad, f"space navigator: {b['id']} carries {sorted(bad)}; the chart may not place a body at a date"
        assert b['ref'] in refs, f"space navigator: {b['id']} reference {b['ref']} is not listed"
        assert b.get('why', '').strip(), f"space navigator: {b['id']} has no card text"
        out = {'id': b['id'], 'name': b['name'], 'kind': b['kind'], 'ref': b['ref'], 'status': refs[b['ref']]['status'], 'why': b['why']}
        if b['kind'] == 'star':
            out['radius_km'] = float(b['radius_km'])
        else:
            for k in PLANET_KEYS:
                assert isinstance(b.get(k), (int, float)) and b[k] >= 0, f"space navigator: {b['id']}.{k} missing or negative"
                out[k] = float(b[k])
            assert b['perihelion_1e6km'] <= b['distance_1e6km'] <= b['aphelion_1e6km'], f"space navigator: {b['id']} distances out of order"
            assert 0 <= b['eccentricity'] < 1, f"space navigator: {b['id']} eccentricity"
            out['radius_km'] = out['diameter_km'] / 2.0
            out['a_au'] = _au(out['distance_1e6km'], au_km)
            out['perihelion_au'] = _au(out['perihelion_1e6km'], au_km)
            out['aphelion_au'] = _au(out['aphelion_1e6km'], au_km)
            out['derived'] = 'a_au, perihelion_au, aphelion_au = 10^6 km x 1e6 / au_km (IAU 2012 B2); radius_km = diameter_km / 2'
        bodies.append(out)
    planets = [b for b in bodies if b['kind'] == 'planet']
    assert [b['id'] for b in sorted(planets, key=lambda b: b['a_au'])] == [b['id'] for b in planets], 'space navigator: planets out of order'
    regions = []
    for r in reg.get('region', []):
        assert r['ref'] in refs and 0 < r['inner_au'] < r['outer_au'], f"space navigator: region {r['id']}"
        assert not PLACING_KEYS & set(r), f"space navigator: region {r['id']} carries a placing field"
        regions.append({k: r[k] for k in ('id', 'name', 'ref', 'inner_au', 'outer_au', 'note', 'why')} | {'status': refs[r['ref']]['status'],
                        'event_position': False})
    for mode in ('ANALYTICAL', 'PRESENTATION'):
        assert reg['transform'][mode]['disclosure'].startswith(mode), f'space navigator: {mode} disclosure must name the mode'
    return {'id': space['id'], 'version': space['version'], 'status': space['status'], 'schematic_notice': space['schematic_notice'],
            'au_km': au_km, 'references': refs, 'bodies': bodies, 'regions': regions, 'transforms': reg['transform'], 'zooms': reg['zoom'],
            'arrangement': 'SCHEMATIC', 'arrangement_note': 'bodies drawn on one layout ray, not at any date; positions need a released epoch '
            'and ephemerides (25!F14:F15 OPEN)'}


if __name__ == '__main__':
    c = contract(load(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT))
    print(c['schematic_notice'])
    for b in c['bodies']:
        print(f"{b['id']:8} r {b['radius_km']:>9,.1f} km" + (f"  a {b['a_au']:7.3f} AU  q {b['perihelion_au']:7.3f}  Q {b['aphelion_au']:7.3f}"
              f"  e {b['eccentricity']:.3f}  P {b['period_days']:,.1f} d" if 'a_au' in b else '') + f"  [{b['ref']}]")
    for r in c['regions']:
        print(f"{r['id']}: {r['inner_au']}-{r['outer_au']} AU [{r['ref']}], event position: {r['event_position']}")
