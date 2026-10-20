"""MECH-003 six-year life-support stock/flow (S&E 58 MECH-003, 59 POL-009; Milestone C of references/SIM_INTEGRATION_PLAN_2026-10-17.md).
Standard library only. data/life_support.toml holds the owner's 41_SURVIVAL_RESOURCES study rates and results; this module integrates
them in mission days and writes generated/wf_life_support.json for the Godot simulator (godot/scripts/life_support.gd), which repeats the
same step and must reproduce the checkpoints here.

Accounting, per resource and step dt:
- food:  need = consumers x rate x dt = Garden (scenario fraction) + drawn from the store + deficit
- O2:    need = recovered from CO2 (scenario fraction) + drawn from the store + deficit
- water: turnover = recovered (scenario fraction) + makeup; makeup is drawn from the makeup store (+ deficit)
- CO2 removed and waste go to their sinks.
A store with known = false is OPEN: its draw is counted as required, never as a stock that runs out. A store that empties stops supplying
and the rest of the need is a deficit, with the exact depletion day. The Garden and O2 recovery are 0 by default (41!B20, 38 S02); a
non-zero value is a HYPOTHETICAL source whose own inputs (water, CO2, light power, plant mass) are not modelled, so it is flagged
UNCLOSED. Nothing is generated from nothing silently.
"""
from pathlib import Path
import argparse
import json
import math
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[2]
CHECKPOINTS = [0.0, 1.0, 3.0, 365.25, 1092.0, 1093.0, 2191.5]


def load(root=ROOT):
    return tomllib.loads((root / 'data/life_support.toml').read_text())


def rates(reg):
    return {r['id']: float(r['value']) for r in reg['rate']}


def stores(reg):
    return {s['id']: (float(s['value']) if s['known'] else None) for s in reg['store']}


def params(reg, consumers=None, water_recovery=None, o2_recovery=None, garden_food=None, extra=None):
    """A scenario: owner defaults unless given. `extra` = {store id: hypothetical kg} replaces an OPEN store or adds to a known one."""
    p = reg['process']
    out = {'consumers': int(consumers if consumers is not None else reg['consumers']['story']),
           'water_recovery': float(p['water_recovery']['default'] if water_recovery is None else water_recovery),
           'o2_recovery': float(p['o2_recovery']['default'] if o2_recovery is None else o2_recovery),
           'garden_food': float(p['garden_food']['default'] if garden_food is None else garden_food),
           'extra': {k: float(v) for k, v in (extra or {}).items()}}
    for k in ('water_recovery', 'o2_recovery', 'garden_food'):
        if not 0.0 <= out[k] <= 1.0:
            raise ValueError(f'{k} must lie in [0, 1]')
    return out


def start(reg, p):
    s = stores(reg)
    for k, v in p['extra'].items():
        s[k] = v if s.get(k) is None else s[k] + v
    z = {'FOOD': 0.0, 'O2': 0.0, 'WATER_MAKEUP': 0.0}
    return {'day': 0.0, 'initial': dict(s), 'store': dict(s), 'drawn': dict(z), 'required': dict(z), 'deficit': dict(z), 'depleted': {},
            'need': {'FOOD': 0.0, 'O2': 0.0, 'WATER': 0.0}, 'garden_food': 0.0, 'o2_recovered': 0.0, 'water_recovered': 0.0,
            'co2_removed': 0.0, 'waste': 0.0}


def _draw(st, key, amount, dt):
    if st['store'][key] is None:
        st['required'][key] += amount
        return
    have = st['store'][key]
    take = min(have, amount)
    st['store'][key] = have - take
    st['drawn'][key] += take
    st['deficit'][key] += amount - take
    if amount > take and key not in st['depleted']:
        st['depleted'][key] = st['day'] + (take / amount) * dt


def step(st, reg, p, dt):
    r = rates(reg)
    n = p['consumers']
    food = n * r['FOOD'] * dt
    o2 = n * r['O2'] * dt
    water = n * r['WATER_TURNOVER'] * dt
    st['need']['FOOD'] += food
    st['need']['O2'] += o2
    st['need']['WATER'] += water
    st['garden_food'] += food * p['garden_food']
    _draw(st, 'FOOD', food * (1.0 - p['garden_food']), dt)
    st['o2_recovered'] += o2 * p['o2_recovery']
    _draw(st, 'O2', o2 * (1.0 - p['o2_recovery']), dt)
    st['water_recovered'] += water * p['water_recovery']
    _draw(st, 'WATER_MAKEUP', water * (1.0 - p['water_recovery']), dt)
    st['co2_removed'] += n * r['CO2_REMOVED'] * dt
    st['waste'] += n * r['WASTE'] * dt
    st['day'] += dt


def run_to(st, reg, p, day):
    """Whole days, then the partial last step (the mission ends at day 2191.5)."""
    while st['day'] + 1.0 <= day + 1e-12:
        step(st, reg, p, 1.0)
    if day - st['day'] > 1e-12:
        step(st, reg, p, day - st['day'])
    return st


def ledger_errors(st):
    """Conservation per resource, as absolute kg: every kg of need has exactly one origin; every store kg is either left or drawn."""
    e = {'FOOD': st['need']['FOOD'] - st['garden_food'] - st['drawn']['FOOD'] - st['required']['FOOD'] - st['deficit']['FOOD'],
         'O2': st['need']['O2'] - st['o2_recovered'] - st['drawn']['O2'] - st['required']['O2'] - st['deficit']['O2'],
         'WATER': st['need']['WATER'] - st['water_recovered'] - st['drawn']['WATER_MAKEUP'] - st['required']['WATER_MAKEUP'] - st['deficit']['WATER_MAKEUP']}
    for k, v in st['initial'].items():
        if v is not None:
            e['store_' + k] = v - st['store'][k] - st['drawn'][k]
    return e


def owner_results(reg):
    """The 41 result rows recomputed from the 41 rates through the simulator (not by a second formula)."""
    d = float(reg['duration']['value'])
    six = run_to(start(reg, params(reg)), reg, params(reg), d)
    six98 = run_to(start(reg, params(reg, water_recovery=0.98)), reg, params(reg, water_recovery=0.98), d)
    p12 = params(reg, consumers=reg['consumers']['stress'], water_recovery=0.0)
    h72 = run_to(start(reg, p12), reg, p12, 3.0)
    r = rates(reg)
    return {'FOOD_6Y_5': six['need']['FOOD'], 'FOOD_SHORTFALL': six['deficit']['FOOD'], 'O2_72H_12': h72['need']['O2'],
            'CO2_72H_12': h72['co2_removed'], 'WATER_LOOP_72H_12': h72['need']['WATER'],
            'POTABLE_72H_12': reg['consumers']['stress'] * r['POTABLE_REFUGE'] * 3.0, 'RATIONS_72H_12': h72['need']['FOOD'],
            'WASTE_6Y_5': six['waste'], 'WATER_RECOVERED_98': six98['water_recovered'],
            'MAKEUP_90': six['required']['WATER_MAKEUP'], 'MAKEUP_98': six98['required']['WATER_MAKEUP']}


def scenarios(reg):
    """Reference scenarios the Godot simulator must reproduce (owner defaults, owner alternatives and one labelled sandbox)."""
    return [{'id': 'STORY_90', 'label': 'five consumers, 90 % water recovery (41 scenario)', 'params': params(reg)},
            {'id': 'STORY_98', 'label': 'five consumers, 98 % water recovery (41 scenario, not achieved)', 'params': params(reg, water_recovery=0.98)},
            {'id': 'STRESS_12', 'label': 'twelve consumers, no recovery (41 72 h stress)', 'params': params(reg, consumers=12, water_recovery=0.0)},
            {'id': 'SANDBOX', 'label': 'HYPOTHETICAL: Garden 30 %, O2 recovery 50 %, 500 kg O2 and 2,000 kg water stores',
             'params': params(reg, garden_food=0.3, o2_recovery=0.5, extra={'O2': 500.0, 'WATER_MAKEUP': 2000.0})}]


def snapshot(st):
    keep = ('day', 'store', 'drawn', 'required', 'deficit', 'depleted', 'need', 'garden_food', 'o2_recovered', 'water_recovered', 'co2_removed', 'waste')
    return json.loads(json.dumps({k: st[k] for k in keep}))


def contract(reg):
    checks = owner_results(reg)
    for c in reg['check']:
        got = checks[c['id']]
        assert math.isclose(got, c['expected'], rel_tol=1e-9, abs_tol=1e-6), f"life support: {c['id']} {got} != owner {c['expected']}"
    refs = []
    for sc in scenarios(reg):
        st = start(reg, sc['params'])
        points = []
        for day in CHECKPOINTS:
            run_to(st, reg, sc['params'], day)
            assert all(abs(v) < 1e-6 for v in ledger_errors(st).values()), f"life support: {sc['id']} ledger at day {day}"
            points.append(snapshot(st))
        refs.append({**sc, 'checkpoints': points})
    return {'schema': 'WF_LIFE_SUPPORT', 'version': reg['life_support']['version'], 'meta': reg['life_support'], 'duration': reg['duration'],
            'consumers': reg['consumers'], 'rates': reg['rate'], 'stores': reg['store'], 'process': reg['process'],
            'owner_checks': [{**c, 'computed': checks[c['id']]} for c in reg['check']], 'scenarios': refs}


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--root', type=Path, default=ROOT)
    ap.add_argument('--out', type=Path, help='write wf_life_support.json into this directory')
    a = ap.parse_args(argv)
    data = contract(load(a.root))
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
        (a.out / 'wf_life_support.json').write_text(json.dumps(data, indent=1, sort_keys=True) + '\n')
        return 0
    for c in data['owner_checks']:
        print(f"{c['id']:<20} {c['computed']:>14.3f} {c['unit']:<3} owner {c['expected']}  ({c['source']})")
    for sc in data['scenarios']:
        end = sc['checkpoints'][-1]
        print(f"{sc['id']:<10} day {end['day']}: food deficit {end['deficit']['FOOD']:.1f} kg (empty day {end['depleted'].get('FOOD')}), "
              f"O2 required {end['required']['O2']:.1f} / drawn {end['drawn']['O2']:.1f}, makeup water required {end['required']['WATER_MAKEUP']:.1f} kg")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
