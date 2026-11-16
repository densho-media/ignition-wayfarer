"""Deadship Phases 2C/3 closeout (owner brief 2026-11-15 18:47Z, section 3 and 4): sensitivity of the reference strategies to the
PROTOTYPE electrical values and to an omitted passive hull heat path. Task study (work/), not part of the build.

    python3 lab/studies/deadship/ds3_sensitivity.py      # about 2 min; prints the matrix, writes ds3_sensitivity.json

Each row changes ONE value of the ring services parameters (ring_services.params, via ship_ops.params) and replays the packaged
reference scripts (ship_ops.cases) unchanged, so a strategy is tested as the player would execute it, not re-optimized. The baseline
values are never edited; the variations are exploratory (EXPLORATORY: no source gives an uncertainty band for an OPEN value), except
where a physical bound is named in the row.

Measured per run: the family and verdict, whether a bus tripped (and when), the battery at the restart window against the restart
demand (the margin), the tightest bus-group margin (sources minus demand, kW, during the watch), and the peaks where people live.

The hull row adds a study-only passive term UA (T - T_env) to each cabin's heat balance (monkeypatched derivative; the ledgers are not
closed for it, it is a what-if, not a model change).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
import ring_services as rs  # noqa: E402
import ship_ops as so  # noqa: E402

H = 3600.0
STRAT = {
    'ds3': ['nothing', 'tie_only', 'shed_garden', 'shed_dark_b', 'shed_economy', 'short_reserve', 'keep_garden'],
    'ds2c': ['borrow_fan', 'borrow_fan_shed', 'borrow_fan_pump', 'relocate', 'relocate_cold', 'cannibalize', 'late_fetch'],
}
VIABLE = {'ds3': ['shed_garden', 'shed_dark_b', 'shed_economy'], 'ds2c': ['borrow_fan_shed', 'borrow_fan_pump', 'relocate']}

# one value at a time: (label, key, values, scenarios, basis)
ROWS = [
    ('Survival packs per ring (kWh)', 'pack_Wh', [2000.0, 4000.0, 8000.0, 16000.0, 32000.0], ['ds3'],
     'EXPLORATORY; survival_reserve.capacity OPEN. 0.95 kW of bus-B survival loads per ring: 8 kWh = 8.4 h.'),
    ('Battery converter rating (kW)', 'conv_W', [25000.0, 30000.0, 35000.0, 40000.0, 50000.0, 60000.0], ['ds3'],
     'EXPLORATORY; no owner row. Both buses on one converter need 15+15 kW ship load plus the rings\' loads.'),
    ('Unmodelled ship load per bus (kW)', 'ship_W', [5000.0, 10000.0, 15000.0, 20000.0, 25000.0], ['ds3', 'ds2c'],
     'EXPLORATORY; power.rating OPEN. Flight computers, comms, propellant conditioning, drive standby, lumped.'),
    ('Generator rating (kW)', 'gen_W', [20000.0, 30000.0, 40000.0, 60000.0, 80000.0, 120000.0], ['ds3', 'ds2c'],
     'EXPLORATORY; power.rating OPEN. Matters after the DS-3 restart and throughout DS-2C (plant on).'),
    ('Restart energy demand (kWh)', 'pulse_Wh', [50000.0, 100000.0, 150000.0, 200000.0, 250000.0], ['ds3'],
     'Bank capacity 200 kWh WORKING; the ignition energy is OPEN, so the demand may be less than the full bank (never more than the '
     'bank holds: 250 kWh is shown only as a stress case).'),
    ('Main battery usable (MWh)', 'battery_Wh', [1.6e6, 1.8e6, 2.0e6, 2.2e6], ['ds3'],
     'WORKING 2 MWh (not changed); EXPLORATORY derating for age, temperature or depth-of-discharge policy.'),
]
SCENARIO_ROWS = [
    ('Restart window (h)', ('premise', 'restart_h'), [36.0, 42.0, 48.0, 54.0, 60.0], ['ds3'],
     'Scenario value (PROTOTYPE): the planned service length.'),
]
HULL = [0.0, 50.0, 150.0, 300.0]   # W/K per ring, to T_ENV
T_ENV = 278.15                     # EXPLORATORY inner-structure temperature behind the cabin lining


def run(name, p, sc, actions):
    """Play one script; also record the tightest bus-group margin (W) while the watch and projection hold the declared state."""
    tight = {'W': None, 't': None}
    orig = rs.settle

    def settle(pp, st):
        plan = orig(pp, st)
        if r_ref[0] is not None and r_ref[0].phase in ('WATCH', 'PROJECTION'):
            coils = {}
            for ring in rs.RINGS:
                rr = st['ring'][ring]
                pumps = sum(1 for e in pp['equipment'] if e['id'] in ('P1', 'P2') and rs.equipment_ready(pp, st, ring, e))
                coils[ring] = rs.coil(pp, rr['T'], rr['m_w'], rs.equipment_ready(pp, st, ring, rs.eq(pp, 'CHX')), pumps,
                                      rs.equipment_ready(pp, st, ring, rs.eq(pp, 'HP')), rs.supply(pp, st, ring))
            src = rs.sources(pp, st); dem = rs.demand(pp, st, coils)
            for g in plan['groups']:
                if all(plan['live'][b] for b in g):
                    m = sum(src[b]['gen'] + src[b]['conv'] for b in g) - sum(dem[b] for b in g)
                    if tight['W'] is None or m < tight['W']:
                        tight['W'] = m; tight['t'] = st['t_s']
        return plan
    r_ref = [None]
    RunCls = so.Run

    class Tracked(RunCls):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            r_ref[0] = self
    rs.settle = settle
    so.Run = Tracked
    try:
        r, _ = so.play(sc, p, actions)
    finally:
        rs.settle = orig
        so.Run = RunCls
    d = r.debrief()
    v = d['watch']['verdict']; m = d['metrics']
    rst = m['restart']
    return dict(family=d['watch']['family'], verdict=v['result'], degraded=v['degraded'],
                trips=[[round(t, 2), b] for t, b in m['trips']],
                restart=None if rst is None else dict(ok=rst['ok'], battery_kWh=round(rst['battery_kWh'], 1),
                                                         margin_kWh=round(rst['battery_kWh'] - p['pulse_Wh']/1000.0, 1)),
                bus_margin_kW=None if tight['W'] is None else round(tight['W']/1000.0, 2),
                bus_margin_at_h=None if tight['t'] is None else round(tight['t']/H, 2),
                peak_T_C=round(v['peak']['T_C'], 1), beyond_validity=v['peak']['beyond_validity'], peak_co2_pct=round(v['peak']['co2_pct'], 3),
                peak_rh=round(v['peak']['rh'], 3), first_cross_h={k: round(x, 2) for k, x in v['first_cross_h'].items() if x is not None},
                battery_end_kWh=round(m['battery_kWh'], 1), packs_end_kWh={k: round(x, 2) for k, x in m['packs_kWh'].items()},
                shed_kWh=round(m['shed_kWh'], 0))


def ok(res):
    return res['verdict'] == 'STABLE'


def table(name, label, values, results, fmt):
    print(f'\n[{name}] {label}')
    head = ' '*16 + ''.join(f'{fmt(x):>14s}' for x in values)
    print(head)
    for s in STRAT[name]:
        cells = []
        for x in values:
            r = results[str(x)][s]
            c = r['verdict'][:9] + ('*' if r['degraded'] else '')
            if r['restart'] is not None:
                c += f" {r['restart']['margin_kWh']:+.0f}"
            if r['trips']:
                c += ' T'
            cells.append(f'{c:>14s}')
        print(f'{s:16s}' + ''.join(cells))


def hull_derivs(UA):
    orig = rs.derivs

    def d(p, st, plan, y):
        dy = orig(p, st, plan, y)
        for k, _ in enumerate(rs.RINGS):
            o = k*rs.Y_RING
            dy[o] -= UA*(y[o] - T_ENV)/p['C']
        return dy
    return orig, d


def main():
    base = so.params()
    out = dict(note=__doc__.split('\n\n')[0], baseline={k: base[k] for k in ('pack_Wh', 'conv_W', 'ship_W', 'gen_W', 'pulse_Wh', 'battery_Wh')},
               rows=[], hull=dict(T_env_K=T_ENV, rows={}))
    for name in ('ds3', 'ds2c'):
        sc = so.load(name)
        cases = {n: a for n, _, a in so.cases(name)}
        for label, key, values, scen, basis in ROWS + SCENARIO_ROWS:
            if name not in scen:
                continue
            results = {}
            for x in values:
                p = dict(base); s2 = json.loads(json.dumps({k: v for k, v in sc.items() if not k.startswith('_')}))
                s2.update({k: v for k, v in sc.items() if k.startswith('_')})
                if isinstance(key, tuple):
                    s2[key[0]][key[1]] = x
                elif key == 'ship_W':
                    p['ship_W'] = {b: x for b in rs.BUSES}
                else:
                    p[key] = x
                results[str(x)] = {s: run(name, p, s2, cases[s]) for s in STRAT[name]}
            viable = {str(x): [s for s in VIABLE[name] if ok(results[str(x)][s])] for x in values}
            out['rows'].append(dict(scenario=name, label=label, key=key if isinstance(key, str) else '.'.join(key), values=values,
                                    basis=basis, results=results, viable=viable))
            div = 1000.0 if key not in ('battery_Wh',) else 1e6
            table(name, label, values, results, (lambda x: f'{x:g}') if isinstance(key, tuple) else (lambda x, d=div: f'{x/d:g}'))
        # the omitted passive hull path
        res = {}
        for UA in HULL:
            orig, d = hull_derivs(UA)
            rs.derivs = d
            try:
                res[str(UA)] = {s: run(name, base, sc, cases[s]) for s in STRAT[name]}
            finally:
                rs.derivs = orig
        out['hull']['rows'][name] = res
        table(name, f'Passive hull UA per ring (W/K) to {T_ENV - 273.15:.0f} C (study-only, EXPLORATORY)', HULL, res, lambda x: f'{x:g}')
    (HERE / 'ds3_sensitivity.json').write_text(json.dumps(out, indent=1) + '\n')


if __name__ == '__main__':
    main()
