"""Ship systems registry (DR-13, ISSA Phase II): data/systems.toml, starting with EPS and TMS. PROTOTYPE. Standard library only.

One row per physical assembly: one physical owner (family), one mass-budget owner (a physics.mass_budget id or a PROPOSED line), its
power.loads ids, heat loop, interfaces, failure domain, candidate districts, sources and maturity. Values owned elsewhere are referenced
(spec paths, power.loads ids, mass_ref); a mass band lives here only where no other owner exists, and an unsized assembly stays OPEN.

- load(): the registry; check(s, reg): consistency failures; rollup(s, reg): known mass per budget item against its allocation, with
  OPEN assemblies and their planning bands listed apart (never summed into a known total).

    python3 src/wayfarer/systems.py
"""
import json
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT/'data/systems.toml'


def load(root=ROOT):
    return tomllib.loads((Path(root)/'data/systems.toml').read_text())


def _spec_path(s, path):
    node = s
    for part in path.split('.'):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def mass_ref(s, r):
    kind, _, name = r.partition(':')
    if kind == 'calc' and name.startswith('power_storage.'):
        import power_storage
        return power_storage.quantities(s)[name.split('.', 1)[1]]
    raise KeyError(r)


def budget_items(s, reg):
    real = {i['id']: i['mass_kg'] for i in s['physics']['mass_budget']['items']}
    return real, {p['id'] for p in reg['registry']['proposed_budget_items']}


def check(s, reg=None):
    reg = reg or load(); fails = []
    real, proposed = budget_items(s, reg)
    loads = {i['id']: i for i in s['power']['loads']['items']}
    ids = [r['id'] for r in reg['system']]
    if len(ids) != len(set(ids)):
        fails.append('system ids must be unique')
    claimed = {}
    for r in reg['system']:
        k = r['id']
        if r['family'] not in reg['registry']['families'] or not k.startswith(r['family']+'-'):
            fails.append(f'{k}: family')
        if r['budget_item'] not in real and r['budget_item'] not in proposed:
            fails.append(f'{k}: budget item {r["budget_item"]} is neither a mass_budget line nor a proposed line')
        if r.get('mass_open'):
            if 'mass_kg' in r:
                fails.append(f'{k}: an OPEN mass carries no known value')
        else:
            m = r.get('mass_kg')
            if not (m and len(m) == 3 and 0 < m[0] <= m[1] <= m[2]):
                fails.append(f'{k}: mass band (low, nominal, high) or mass_open')
            if 'mass_ref' in r and not m[0] <= mass_ref(s, r['mass_ref']) <= m[2]:
                fails.append(f'{k}: mass band must contain its referenced owner value')
        for ld in r['loads']:
            if ld not in loads:
                fails.append(f'{k}: unknown load {ld}')
            elif ld in claimed:
                fails.append(f'{ld}: owned by both {claimed[ld]} and {k}')
            claimed[ld] = k
        if r['failure_domain'] not in reg['registry']['failure_domains']:
            fails.append(f'{k}: failure domain')
        if not 0 <= r['maturity'] <= 7:
            fails.append(f'{k}: maturity 0-7')
        for src in r['sources']:
            if src.startswith('spec:') and _spec_path(s, src[5:]) is None:
                fails.append(f'{k}: source {src} does not resolve')
        for i in r['interfaces']:
            if i['kind'] not in ('ELECTRIC', 'HEAT', 'FLUID', 'DATA'):
                fails.append(f'{k}: interface kind')
    for ld, it in loads.items():                       # every EPS/TMS-owned load has exactly one registry assembly
        if it['owner'] in reg['registry']['families'] and ld not in claimed:
            fails.append(f'{ld}: an {it["owner"]} load without a registry assembly')
    return fails


def rollup(s, reg=None):
    reg = reg or load(); real, proposed = budget_items(s, reg); out = {}
    for r in reg['system']:
        b = out.setdefault(r['budget_item'], dict(allocation_kg=real.get(r['budget_item']), known_kg=[0.0, 0.0, 0.0], rows=[], open=[]))
        if r.get('mass_open'):
            b['open'].append(dict(id=r['id'], planning_kg=r.get('planning_kg')))
        else:
            b['known_kg'] = [a+m for a, m in zip(b['known_kg'], r['mass_kg'])]; b['rows'].append(r['id'])
    return out


if __name__ == '__main__':
    from spec import load as spec_load
    s = spec_load()[0]; reg = load()
    print(json.dumps(rollup(s, reg), indent=1)); print('failures:', check(s, reg) or 'none')
