"""WAYFARER Ship Navigator (SNAV-001; S&E 49_SHIP_NAVIGATOR NAV-001..029): the registry contract of the in-world orientation instrument.
Standard library only. data/ship_navigator.toml holds the modules, hotspots, status taxonomy and guidance modes; this module validates every
binding against the induction route and the crew nav graph built from the same spec and emits the rig's `navigator` block (sim_rig v33).

The navigator owns no fact (NAV-029). A hotspot number is resolved here from data/wayfarer_3d.toml with its source_map range; a section the
spec marks `known = false` stays OPEN with its items, never 0 (NAV-007). Modes carry guidance only, never a permission (NAV-003). The Godot
side is godot/scripts/navigator/; it plans routes with the rig's own gates and draws the map from the loaded GLB.
"""
from pathlib import Path
import json
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[2]
PERMISSION_KEYS = {'access', 'allow', 'allowed', 'unlock', 'permission', 'permissions', 'gate', 'closed', 'synced'}
OPEN_STATES = {'OPEN'}


def load(root=ROOT):
    return tomllib.loads((root / 'data/ship_navigator.toml').read_text())


def _walk(s, path):
    """The node at a dotted path of the spec and the nearest source/evidence ref on the way (a section's own ref wins)."""
    node, ref = s, None
    for key in path.split('.'):
        if isinstance(node, dict):
            ref = node.get('source_ref', node.get('evidence_ref', ref))
        assert isinstance(node, dict) and key in node, f'navigator fact {path}: not in data/wayfarer_3d.toml'
        node = node[key]
    if isinstance(node, dict):
        ref = node.get('source_ref', node.get('evidence_ref', ref))
    return node, ref


def fact(s, sources, item):
    """One hotspot fact: value, unit, status and the owner range behind it, or OPEN with the unresolved items."""
    node, ref = _walk(s, item['path'])
    assert ref is not None, f"navigator fact {item['path']}: no source_ref on its path"
    src = sources['sources'].get(ref)
    assert src is not None, f"navigator fact {item['path']}: source_ref {ref} is not in data/source_map.toml"
    owner = {'source_ref': ref, 'workbook': src['workbook'], 'sheet': src.get('sheet', ''), 'range': src.get('range', ''),
             'source_status': src.get('canon_status', '')}
    out = {'label': item['label'], 'path': item['path']} | owner
    if isinstance(node, dict) and node.get('known') is False:
        return out | {'known': False, 'status': node.get('canon_status', 'OPEN'), 'value': None, 'items': list(node.get('items', [])),
                      'reason': node.get('reason', '')}
    if isinstance(node, dict):
        assert 'value' in node, f"navigator fact {item['path']}: a section without a value or known = false"
        value, unit, status = node['value'], node.get('unit', item.get('unit', '')), node.get('canon_status', owner['source_status'])
    else:
        section, _ = _walk(s, item['path'].rsplit('.', 1)[0])
        value, unit = node, item.get('unit', '')
        status = section.get('canon_status', owner['source_status'])
    assert value is not None and value != '', f"navigator fact {item['path']}: empty value must be known = false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = float(value)
    return out | {'known': True, 'status': status, 'value': value, 'unit': unit}


def _sector_node(opening_id):
    m = re.match(r'WF\.OPENING\.A(\d)\.', opening_id)
    assert m, f'{opening_id}: no ring A sector in the id'
    return f'SECTOR_1_{m.group(1)}'


def rail_nodes(graph, reg):
    """The nav node of every rail waypoint: the zone's module node, or in ring A the sector of the nearest tube/sector opening."""
    zone_node = {'entry': 'DOCK_PRIMARY', 'trunk': 'TRUNK', 'vestibule': 'VESTIBULE_1'}
    ring_openings = [o for leg in graph['legs'] for o in leg['openings'] if o['kind'] in ('DRUM_DOOR_TUBE_HATCH', 'SECTOR_LEAF')]
    out = []
    for p in graph['rail']:
        if p['zone'] in zone_node:
            out.append(zone_node[p['zone']])
        else:
            near = min(ring_openings, key=lambda o: abs(o['rail_m'] - p['rail_m']))
            out.append(_sector_node(near['id']))
    return out


def openings(graph, reg):
    """Each rail opening with the nav edge it crosses (the edge's modes, actors and gate decide passage)."""
    out = []
    for leg in graph['legs']:
        for o in leg['openings']:
            a, b = reg['opening_edges'][o['kind']]
            b = _sector_node(o['id']) if b == 'SECTOR' else b
            out.append({'id': o['id'], 'kind': o['kind'], 'leg': leg['id'], 'rail_m': o['rail_m'], 'edge': [a, b]})
    return out


def contract(s, sources, graph, nav, ring_count=2):
    reg = load()
    nodes = set(nav['nodes'])
    edges = {frozenset((e['from'], e['to'])) for e in nav['edges']}
    frames = {'STATIONARY'} | {f'WF.ROTOR.{j}' for j in range(1, ring_count + 1)} | {f'WF.CREW.{j}.DRUM' for j in range(1, ring_count + 1)}
    zones = set(graph['frames']['zones'])
    ids = [m['id'] for m in reg['module']] + [h['id'] for h in reg['hotspot']] + [m['id'] for m in reg['mode']]
    assert len(ids) == len(set(ids)), 'navigator: duplicate ids'
    owned = {}
    for m in reg['module']:
        assert m['frame'] in frames, f"{m['id']}: frame {m['frame']} is not a ship frame"
        for z in m['zones']:
            assert z in zones and z not in owned, f"{m['id']}: zone {z} unknown or owned twice"
            owned[z] = m['id']
            kind = graph['frames']['zones'][z]
            want = 'STATIONARY' if kind == 'STATIONARY' else graph['frames'][kind]
            assert m['frame'] == want, f"{m['id']}: zone {z} turns with {want}, not {m['frame']}"
        for n in m['nav']:
            assert n in nodes, f"{m['id']}: nav node {n} not in dynamics.nav"
    assert set(owned) == zones, f'navigator: rail zones without a module: {sorted(zones - set(owned))}'
    stops = {st['key'] for st in graph['stops']}
    assert set(reg['stop_nodes']) == stops, 'navigator: stop_nodes must name every induction stop'
    assert all(n in nodes for n in reg['stop_nodes'].values())
    ops = openings(graph, reg)
    for o in ops:
        assert frozenset(o['edge']) in edges or o['edge'][1].startswith('SECTOR_1_'), f"{o['id']}: no nav edge {o['edge']}"
    modules = {m['id'] for m in reg['module']}
    hotspots = []
    assert len({h['module'] for h in reg['hotspot']}) == len(reg['hotspot']), 'navigator: one hotspot per module'
    for h in reg['hotspot']:
        assert h['module'] in modules and all(x in modules for x in h['show_modules']), h['id']
        assert all(h[k] for k in ('what', 'why', 'show', 'facts')), f"{h['id']}: WHAT / WHY / SHOW ME and facts are required"
        assert all(k in reg['opening_edges'] for k in h['show_openings']), h['id']
        hotspots.append({k: h[k] for k in ('id', 'module', 'title', 'wording', 'what', 'why', 'show', 'show_modules', 'show_openings')}
                        | {'facts': [fact(s, sources, f) for f in h['facts']]})
    for m in reg['mode']:
        assert not (PERMISSION_KEYS & set(m)), f"mode {m['id']}: a mode carries guidance only, never a permission (NAV-003)"
    assert sum(1 for m in reg['mode'] if m.get('default')) == 1 and next(m for m in reg['mode'] if m.get('default'))['id'] == 'ASSISTED'
    return {'id': reg['navigator']['id'], 'version': reg['navigator']['version'], 'status': reg['navigator']['status'],
            'scope': reg['navigator']['scope'], 'source_ref': reg['navigator']['source_ref'], 'read_on': reg['navigator']['read_on'],
            'statuses': reg['status'], 'palette': reg['palette'], 'silhouette': reg['silhouette'],
            'modules': reg['module'], 'stop_nodes': reg['stop_nodes'], 'openings': ops, 'rail_nodes': rail_nodes(graph, reg),
            'hotspots': hotspots, 'modes': reg['mode']}


if __name__ == '__main__':
    # Fit screen: the hotspot facts as the card shows them, and the rail's nav nodes per zone.
    sys.path.insert(0, str(ROOT / 'src/wayfarer'))
    import spec, human_entry, crew_dynamics
    s, sources, _, _ = spec.load()
    c = contract(s, sources, human_entry.induction_graph(s), crew_dynamics.nav(s))
    for h in c['hotspots']:
        print(h['id'], h['title'])
        for f in h['facts']:
            v = f"{f['value']} {f['unit']}".strip() if f['known'] else f"OPEN ({', '.join(f['items'])})"
            print(f"  {f['label']}: {v}  [{f['status']}; {f['sheet']}!{f['range']}]")
    runs = []
    for n in c['rail_nodes']:
        if not runs or runs[-1][0] != n:
            runs.append([n, 0])
        runs[-1][1] += 1
    print('rail nodes:', ' -> '.join(f'{n} x{k}' for n, k in runs))
    print(json.dumps({o['id']: o['edge'] for o in c['openings']}, indent=1))
