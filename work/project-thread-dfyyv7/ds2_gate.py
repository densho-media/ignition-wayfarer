"""Deadship Phase 2B engineering gate (2026-11-14): does ring A's compartment model (SYS-002, src/wayfarer/ring_air.py) produce a genuine
"you cannot save everything" decision on its own? A deterministic search over every door configuration and crew order, scored only on
quantities the model computes. Task study (work/), not part of the build; it calls the model's public functions and changes nothing.

    python3 work/project-thread-dfyyv7/ds2_gate.py            # prints the findings, writes ds2_gate.json next to this file

Variants (every value PROTOTYPE, as in the model):
  V0  the section 24 proposal: ring ventilation failed, fill 2's doors (A2P, AC2, A3N) held shut by procedure, the three two-person crews
      free to move to any sector, the other six doors free.
  V1  the refined candidate: ventilation failed, every door free, sector 2's crew held at their repair (the scenario rule that ends the
      fault), sector 1's off-shift crew may be sent to sector 3, sector 3's crew stays with the unit.
  V2  the revised-design probe (NOT the model, NOT implemented): V1 plus a second passive trace species released in sector 2 and removed
      only by the trace-contaminant unit in sector 3, transported by the same graph. It shows what one hazard species would add.
  V3  V1 with the unit at half duty (a limited resource without a new species).
  V4  twelve crew in ring A (four per sector) from the six-crew steady state, the unit at half duty, ventilation failed; sectors 1 and 2
      may each send their four to sector 3; every door free. Scored on the worst compartment and the crew-weighted mean.

Every strategy is applied at ACT_H after the fault (the trainee's reaction time), crew transit included (TRANSIT_S per compartment
passed), then the model runs to the planning horizon with no input.
"""
import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
import ring_air as ra   # noqa: E402

ACT_H = 0.5            # PROTOTYPE: the trainee's configuration is in place half an hour after the fault
TRANSIT_S = 40.0       # PROTOTYPE: a crew passes each compartment on its route in 40 s (doors cycled behind them)
HORIZONS_H = (6.0, 12.0)   # the repair's expected and worst-case completion (a scenario value)
DT = 300.0             # the search step; the model's step is exact for any length (checked below at 10 s and 60 s)
EPS_TREND = 1e-6       # %/h: a trend at or below this counts as settled
DEGRADED = 0.5         # V3/V4: one of the unit's two swing beds out, the other cycling alone (half the duty): PROTOTYPE

P = ra.params()
IDS = P['ids']
N = len(IDS)
DOORS = [e['id'] for e in P['edges'] if e['kind'] == 'door']
I = {k: i for i, k in enumerate(IDS)}
TARGET, LIMIT = P['co2_target'], P['co2_max']


def route(frm, to, shut=()):
    """The shortest door path between two compartments (BFS over the CIRC doors not held shut; crews open and re-close each door)."""
    adj = {k: [] for k in IDS}
    for e in P['edges']:
        if e['kind'] == 'door' and e['id'] not in shut:
            a, b = IDS[e['i']], IDS[e['j']]
            adj[a].append(b); adj[b].append(a)
    prev = {frm: None}; q = [frm]
    while q:
        c = q.pop(0)
        for n in adj[c]:
            if n not in prev:
                prev[n] = c; q.append(n)
    path = [to]
    while prev[path[-1]] is not None:
        path.append(prev[path[-1]])
    return path[::-1]


def simulate(open_doors, moves, horizon_h, dt=DT, params=None, removal_node=None, source=None, start_x=None, shut=(), team=2):
    """Run one strategy: the fault (ventilation off) at t = 0, the doors and crew moves at ACT_H (moves walk their route), then no input.
    Returns the occupied compartments' history summary and the end state."""
    p = dict(params or P)
    if removal_node is not None:
        p['removal'] = I[removal_node]
    st = ra.start(p, x0=start_x)
    occ = [team if k in ('A1', 'A2', 'A3') else 0 for k in IDS] if source is None else list(source)
    ra.set_occupants(st, occ)
    ra.set_vent(st, False)
    hist = []

    def record():
        x = [st['m'][i]/p['M_CO2']/ra.n_mol(p, i) for i in range(N)]
        hist.append((st['t_s'], x, list(st['occupants'])))

    def run_to(t, step):
        while st['t_s'] < t - 1e-9:
            ra.step(st, p, min(step, t - st['t_s']))
            record()
    record()
    run_to(ACT_H*3600.0, dt)
    for d in open_doors:
        ra.set_edge(st, d, True)
    if moves:
        legs = []
        for frm, to, n in moves:
            path = route(frm, to, shut)
            legs.append((path, n))
        longest = max(len(path) for path, _ in legs)
        for k in range(1, longest):              # every crew advances one compartment per TRANSIT_S, together
            o = list(st['occupants'])
            for path, n in legs:
                if k < len(path):
                    o[I[path[k-1]]] -= n; o[I[path[k]]] += n
            ra.set_occupants(st, o)
            run_to(st['t_s'] + TRANSIT_S, 10.0)
    run_to(horizon_h*3600.0, dt)
    return st, p, hist


def score(st, p, hist, crew_ids=None, limit=LIMIT, target=TARGET):
    """Only computed quantities: per occupied compartment the peak, the hours above the target and the control limit, the first crossing;
    at the end the trend, whether every crew compartment shares air with the unit (bounded), the crew air groups, the CO2 outside the
    unit's group (what the unit must clean after the repair) and the ledger."""
    peak = 0.0; above_t = 0.0; above_l = 0.0; first = None; worst_id = None; ph_t = 0.0; peak_after = 0.0; exp_sum = 0.0; exp_w = 0.0
    for k in range(1, len(hist)):
        t0, _, _ = hist[k-1]; t1, x, o = hist[k]
        ph_t += sum(o[i] for i in range(N) if x[i] > target)*(t1 - t0)/3600.0
        exp_sum += sum(o[i]*x[i] for i in range(N))*(t1 - t0); exp_w += sum(o)*(t1 - t0)
        if t1 > ACT_H*3600.0 + 1e-6:
            peak_after = max([peak_after] + [x[i] for i in range(N) if o[i] > 0])
        for i in range(N):
            if o[i] > 0:
                if x[i] > peak:
                    peak, worst_id = x[i], IDS[i]
        top = max((x[i] for i in range(N) if o[i] > 0), default=0.0)
        if top > target:
            above_t += (t1 - t0)/3600.0
        if top > limit:
            above_l += (t1 - t0)/3600.0
            first = first if first is not None else t1/3600.0
    r = ra.readout(st, p)
    groups = ra.components(st, p)
    occ = st['occupants']
    crew_groups = [g for g in groups if sum(occ[i] for i in g) > 0]
    removal_group = next(g for g in groups if p['removal'] in g)
    bounded = all(p['removal'] in g for g in crew_groups)
    outside_kg = sum(st['m'][i] for i in range(N) if i not in removal_group) - \
        sum(hist[0][1][i]*ra.n_mol(p, i)*p['M_CO2'] for i in range(N) if i not in removal_group)
    trend = max((q['dxdt_per_h']*100 for q in r['nodes'] if q['occupants'] > 0), default=0.0)
    end = {q['id']: round(q['x']*100, 4) for q in r['nodes'] if q['occupants'] > 0}
    return dict(mean_pct=round(exp_sum/exp_w*100, 4) if exp_w else 0.0, peak_pct=round(peak*100, 4), peak_after_pct=round(peak_after*100, 4), crew_h_above_target=round(ph_t, 3), worst=worst_id, h_above_target=round(above_t, 3), h_above_limit=round(above_l, 3),
                first_limit_h=first, end_pct=end, trend_pct_h=round(trend, 6), bounded=bounded, viable=above_l == 0.0,
                crew_groups=len(crew_groups), largest_crew_group=max(sum(occ[i] for i in g) for g in crew_groups),
                doors_open=sum(1 for d in DOORS if st['open'][d]), excess_outside_unit_kg=round(max(outside_kg, 0.0), 4),
                ledger_kg=ra.ledger_error(st))


def dominates(a, b, keys):
    """a is at least as good as b on every key (all minimised) and better on one."""
    return all(a[k] <= b[k] for k in keys) and any(a[k] < b[k] for k in keys)


def pareto(rows, keys):
    return [r for r in rows if not any(dominates(o, r, keys) for o in rows if o is not r)]


# The computed objectives (all minimised). Door count is reported but is not an objective: no computed consequence follows from a door
# standing open in this model (that is the point under test).
KEYS = ('peak_after_pct', 'crew_h_above_target', 'unbounded', 'excess_outside_unit_kg')


def flat(sc):
    return dict(sc, unbounded=0 if sc['bounded'] else 1)


def search_v1(horizon_h, params=None):
    rows = []
    for mask in range(1 << len(DOORS)):
        doors = [d for k, d in enumerate(DOORS) if mask >> k & 1]
        for a1 in ('A1', 'A3'):
            moves = [] if a1 == 'A1' else [('A1', 'A3', 2)]
            st, p, hist = simulate(doors, moves, horizon_h, params=params)
            sc = flat(score(st, p, hist))
            sc.update(doors=doors, a1_crew=a1)
            rows.append(sc)
    return rows


FILL2 = ('CIRC.A2P', 'CIRC.AC2', 'CIRC.A3N')


def search_v0(horizon_h):
    """Section 24: A2P, AC2, A3N held shut; each two-person crew may go to any sector."""
    free = [d for d in DOORS if d not in FILL2]
    rows = []
    for mask in range(1 << len(free)):
        doors = [d for k, d in enumerate(free) if mask >> k & 1]
        for dest in itertools.product(('A1', 'A2', 'A3'), repeat=3):
            moves = [(f'A{k+1}', dest[k], 2) for k in range(3) if dest[k] != f'A{k+1}']
            # a crew can only walk through doors; with fill 2 held shut, a route through it is refused (the long way round is allowed)
            ok = True
            for frm, to, _ in moves:
                ok = ok and to in route(frm, to, FILL2)
            if not ok:
                continue
            st, p, hist = simulate(doors, moves, horizon_h, shut=FILL2)
            sc = flat(score(st, p, hist))
            sc.update(doors=doors, crews=dict(zip(('A1', 'A2', 'A3'), dest)))
            rows.append(sc)
    return rows


NAMED = {
    'seal': ([], []),
    'buffer sector 2 (2 doors)': (['CIRC.A2N', 'CIRC.A2P'], [('A1', 'A3', 2)]),
    'buffer sector 2 (4 doors, all its corridors)': (['CIRC.A2N', 'CIRC.AC1', 'CIRC.A2P', 'CIRC.AC2'], [('A1', 'A3', 2)]),
    'join sector 2 to the unit (3 doors), sector 1 crew to 3': (['CIRC.A2P', 'CIRC.AC2', 'CIRC.A3N'], [('A1', 'A3', 2)]),
    'join both sectors (6 doors), nobody moves': (['CIRC.A2P', 'CIRC.AC2', 'CIRC.A3N', 'CIRC.A1N', 'CIRC.AC3', 'CIRC.A3P'], []),
    'open the whole loop (9 doors)': (DOORS, []),
}


def step_independence():
    """The exact step: one strategy at 10 s, 60 s and 300 s steps ends in the same state (the transit legs always run at 10 s)."""
    doors, moves = NAMED['join sector 2 to the unit (3 doors), sector 1 crew to 3']
    ends = []
    for dt in (10.0, 60.0, 300.0):
        st, p, hist = simulate(doors, moves, 12.0, dt=dt)
        ends.append(st['m'])
    worst = max(abs(a - b)/max(abs(b), 1e-30) for e in ends[1:] for a, b in zip(e, ends[0]))
    return worst


def contaminant_probe():
    """V2 (revised-design probe, not the model): a generic trace species in units of its own limit. Source in sector 2 at a rate that
    takes an isolated sector 2 to its limit in SRC_TO_LIMIT_H; removal by the trace-contaminant unit in sector 3 at TCC_M3_H. The same
    transport (ring_air) with the species' own source and removal. All values PROTOTYPE, chosen only to show the shape of the trade."""
    SRC_TO_LIMIT_H, TCC_M3_H = 4.0, 15.0
    q = dict(P)
    nA2 = ra.n_mol(q, I['A2'])
    limit_mass = 1.0*nA2*q['M_CO2']*1e-5        # a nominal limit fraction of 1e-5 (10 ppm), expressed through the CO2 machinery
    q['per_person_kg_s'] = limit_mass/(SRC_TO_LIMIT_H*3600.0)
    q['k_m3_s'] = TCC_M3_H/3600.0
    q['co2_target'] = q['co2_max'] = 1e-5
    src = [1 if k == 'A2' else 0 for k in IDS]
    out = {}
    for name, (doors, moves) in NAMED.items():
        # crews move but the source stays: the species follows the air, not the people
        st, p, hist = simulate(doors, [], 12.0, params=q, source=src, start_x=0.0)
        x = {k: st['m'][I[k]]/q['M_CO2']/ra.n_mol(q, I[k])/1e-5 for k in ('A1', 'A2', 'A3')}
        crew_at = {'A1': 'A3' if moves else 'A1', 'A2': 'A2', 'A3': 'A3'}
        out[name] = {f'crew of {k} (in {v})': round(x[v], 3) for k, v in crew_at.items()}
    return dict(note='multiples of the species limit at 12 h for each crew; PROTOTYPE probe, not implemented',
                source_to_limit_h=SRC_TO_LIMIT_H, tcc_m3_h=TCC_M3_H, results=out)


def main():
    out = dict(study='Deadship Phase 2B engineering gate', date='2026-11-14', model=dict(file='src/wayfarer/ring_air.py', version=ra.VERSION),
               act_h=ACT_H, transit_s=TRANSIT_S, horizons_h=list(HORIZONS_H), objectives=list(KEYS),
               target_pct=TARGET*100, limit_pct=LIMIT*100)
    out['step_independence_rel'] = step_independence()
    for H in HORIZONS_H:
        v1 = search_v1(H)
        viable = [r for r in v1 if r['viable']]
        front = pareto(viable, KEYS)
        out[f'v1_{int(H)}h'] = dict(configs=len(v1), viable=len(viable), bounded=sum(r['bounded'] for r in viable),
                                     pareto=[{k: r[k] for k in ('a1_crew', 'doors', 'peak_after_pct', 'crew_h_above_target', 'end_pct', 'bounded',
                                                               'excess_outside_unit_kg', 'crew_groups', 'largest_crew_group', 'doors_open')}
                                             for r in sorted(front, key=lambda r: (r['peak_pct'], r['doors_open']))][:12],
                                     pareto_size=len(front),
                                     split_and_bounded=sum(1 for r in viable if r['crew_groups'] > 1 and r['bounded']),
                                     split_and_viable=sum(1 for r in viable if r['crew_groups'] > 1),
                                     max_ledger_kg=max(abs(r['ledger_kg']) for r in v1))
        v0 = search_v0(H)
        v0v = [r for r in v0 if r['viable']]
        f0 = pareto(v0v, KEYS)
        out[f'v0_{int(H)}h'] = dict(configs=len(v0), viable=len(v0v), pareto_size=len(f0),
                                     pareto=[{k: r[k] for k in ('crews', 'doors', 'peak_after_pct', 'crew_h_above_target', 'bounded', 'doors_open',
                                                               'largest_crew_group')}
                                             for r in sorted(f0, key=lambda r: (r['doors_open'], r['peak_pct']))][:6])
    deg = dict(P, k_m3_s=P['k_m3_s']*DEGRADED)
    for H in HORIZONS_H:
        v3 = search_v1(H, params=deg)
        viable = [r for r in v3 if r['viable']]
        front = pareto(viable, KEYS)
        out[f'v3_{int(H)}h'] = dict(configs=len(v3), viable=len(viable), bounded=sum(r['bounded'] for r in viable), pareto_size=len(front),
                                     pareto=[{k: r[k] for k in ('a1_crew', 'doors_open', 'doors', 'peak_after_pct', 'crew_h_above_target', 'end_pct',
                                                               'bounded', 'trend_pct_h', 'crew_groups')}
                                             for r in sorted(front, key=lambda r: (r['unbounded'], r['peak_after_pct']))],
                                     all_good=sum(1 for r in viable if r['bounded'] and r['crew_h_above_target'] == 0.0))
    # V4: the full crew of twelve in ring A (ring B's six arrive at the fault, two through each sector's crew tube), the unit at half duty,
    # the fans stopped; orders send a sector's crew of four to the unit's sector 3. Start: the six-crew steady state with the fans on.
    deg = dict(P, k_m3_s=P['k_m3_s']*DEGRADED)
    s6 = ra.start(P); ra.step(s6, P, 400*3600.0)
    x6 = [s6['m'][i]/P['M_CO2']/ra.n_mol(P, i) for i in range(N)]
    s12 = ra.start(P, x0=list(x6)); ra.set_occupants(s12, [4 if k in ('A1', 'A2', 'A3') else 0 for k in IDS]); ra.step(s12, P, 400*3600.0)
    out['v4_note'] = dict(start_pct={k: round(v*100, 4) for k, v in zip(IDS, x6)},
                          twelve_crew_fans_on_steady_pct={k: round(s12['m'][i]/P['M_CO2']/ra.n_mol(P, i)*100, 4) for i, k in enumerate(IDS)})
    for H in HORIZONS_H:
        rows = []
        for mask in range(1 << len(DOORS)):
            doors = [d for k, d in enumerate(DOORS) if mask >> k & 1]
            for a1, a2 in itertools.product(('A1', 'A3'), ('A2', 'A3')):
                moves = [(f, 'A3', 4) for f, d in (('A1', a1), ('A2', a2)) if d == 'A3']
                st, p, hist = simulate(doors, moves, H, params=deg, start_x=list(x6), team=4)
                sc = flat(score(st, p, hist)); sc.update(doors=doors, orders=dict(A1=a1, A2=a2)); rows.append(sc)
        viable = [r for r in rows if r['viable']]
        front = pareto(viable, ('peak_after_pct', 'mean_pct'))
        out[f'v4_{int(H)}h'] = dict(configs=len(rows), viable=len(viable), pareto_size=len(front),
                                     pareto=[{k: r[k] for k in ('orders', 'doors_open', 'peak_after_pct', 'mean_pct', 'end_pct', 'bounded')}
                                             for r in sorted(front, key=lambda r: r['peak_after_pct'])])
    named = {}
    for name, (doors, moves) in NAMED.items():
        named[name] = {}
        for H in HORIZONS_H:
            st, p, hist = simulate(doors, moves, H)
            named[name][f'{int(H)}h'] = score(st, p, hist)
    out['named'] = named
    out['v2_probe'] = contaminant_probe()
    # determinism: the same strategy twice gives bit-identical end states
    a = simulate(*NAMED['open the whole loop (9 doors)'], 12.0)[0]['m']
    b = simulate(*NAMED['open the whole loop (9 doors)'], 12.0)[0]['m']
    out['deterministic'] = a == b
    (HERE / 'ds2_gate.json').write_text(json.dumps(out, indent=1) + '\n')
    return out


if __name__ == '__main__':
    o = main()
    print('step independence (10/60/300 s), worst relative difference:', o['step_independence_rel'], ' deterministic:', o['deterministic'])
    for H in HORIZONS_H:
        v1 = o[f'v1_{int(H)}h']; v0 = o[f'v0_{int(H)}h']
        print(f'\n== horizon {H:g} h')
        print(f"V0 (section 24): {v0['configs']} configurations, {v0['viable']} viable, Pareto set {v0['pareto_size']}")
        for r in v0['pareto']:
            print('   ', r)
        print(f"V1 (refined): {v1['configs']} configurations, {v1['viable']} viable ({v1['bounded']} bounded), Pareto set {v1['pareto_size']}, "
              f"split-and-bounded {v1['split_and_bounded']}, split-and-viable {v1['split_and_viable']}, max ledger {v1['max_ledger_kg']:.2e} kg")
        for r in v1['pareto']:
            print('   ', r)
    for H in HORIZONS_H:
        v3 = o[f'v3_{int(H)}h']
        print(f"\nV3 (degraded unit x{DEGRADED}) horizon {H:g} h: {v3['configs']} configurations, {v3['viable']} viable ({v3['bounded']} bounded), "
              f"Pareto set {v3['pareto_size']}, all-good {v3['all_good']}")
        for r in v3['pareto'][:14]:
            print('   ', {k: v for k, v in r.items() if k != 'doors'})
    print('\nV4 note', o['v4_note'])
    for H in HORIZONS_H:
        v4 = o[f'v4_{int(H)}h']
        print(f"V4 (12 crew, unit x{DEGRADED}) horizon {H:g} h: {v4['configs']} configurations, {v4['viable']} viable, Pareto set {v4['pareto_size']}")
        for r in v4['pareto']:
            print('   ', r)
    print('\nnamed strategies')
    for k, v in o['named'].items():
        for h, s in v.items():
            print(f"  {k:55s} {h:>4s} viable {s['viable']!s:5s} bounded {s['bounded']!s:5s} peak {s['peak_pct']:.3f} % "
                  f"above target {s['h_above_target']:.2f} h first limit {s['first_limit_h']} groups {s['crew_groups']} "
                  f"largest {s['largest_crew_group']} doors {s['doors_open']} excess {s['excess_outside_unit_kg']} kg")
    print('\nV2 probe:', json.dumps(o['v2_probe'], indent=1))
