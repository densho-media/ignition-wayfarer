"""Deadship Phase 2B engineering gate, second attempt (2026-11-14): with SYS-002 v2 (CO2 and NH3, src/wayfarer/ring_air.py) does ring A
produce a genuine decision? A deterministic search over the ring's connections, the crew's moves, containing the source and reconnecting
later, scored only on what the model computes for each person along the places they actually are. Task study (work/), not part of the
build; it calls the model's public functions and changes nothing.

    python3 work/project-thread-dfyyv7/ds2b_gate.py            # about 30 min on 4 cores; prints the findings, writes ds2b_gate.json

The event (every value PROTOTYPE unless it cites a source):
  t = 0   hygiene A in sector 1 (A1, the habitation sector): a urine store whose pretreatment dose failed. Urease hydrolyses the urea to
          ammonia (CO(NH2)2 + H2O -> 2 NH3 + CO2; ISS pretreats urine precisely to stop this). The store's bag splits and the liquid
          spreads on the compartment's surfaces; it gives off NH3 at a first-order rate, M0 = 7 g volatile NH3 (3 to 20 g), tau = 1 h
          (0.25 to 4 h). The ring is in its normal state: doors closed, ventilation and every damper open, the CO2 unit and the TCC on.
          Crew 2/2/2 in sectors 1/2/3 (sector 1's pair off shift in their berths).
  t = d   the crew notice (the smell or a sensor; d = 10 min) and act at once: the Ops panel sets every damper and door, the crews walk
          (40 s per compartment passed, doors cycled behind them), one person may contain the spill (10 min in A1: bag the liquid and the
          absorbent; the source is ISOLATED, what it still holds stays in the bag).
  t = T2  optionally the ring goes back to normal ventilation (every damper open, doors closed) with the crew where they are.
  t = 24 h the projection: the ring back to normal, everybody home, run to 7 d with no further input.

Objectives (all minimised, all computed): per person the largest 1 h mean NH3 / 30 ppm and 24 h mean / 20 ppm (JSC 20584 Rev D SMACs;
exceedances of a reference, never harm), the crew's mean NH3 dose, crew-hours above the CO2 target (0.3 %, PROTOTYPE control level), the
7 d mean / 3 ppm and the time until every compartment is back under 3 ppm. A strategy is viable while no occupied compartment exceeds
the CO2 control limit (0.5 %, PROTOTYPE) within the horizon.
"""
import itertools
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
import air_exposure as ax   # noqa: E402
import ring_air as ra   # noqa: E402

P0 = ra.params()
IDS = P0['ids']
N = len(IDS)
I = {k: i for i, k in enumerate(IDS)}
SMAC = ra.NH3_SMAC['value_ppm']
TARGET, LIMIT = P0['co2_target'], P0['co2_max']
H = 3600.0

# the ring is one loop of nine links; each link carries a door (139 m3/h open) and an IMV damper pair (238 m3/h with the fans on)
LINKS = ['A1P', 'AC1', 'A2N', 'A2P', 'AC2', 'A3N', 'A3P', 'AC3', 'A1N']
ARCS = (('12', LINKS[0:3]), ('23', LINKS[3:6]), ('31', LINKS[6:9]))
# per arc (sector to sector, through two corridor halves): D normal (dampers open, doors closed), S sealed (both shut on all three links),
# B dampers and doors open, O doors open with the dampers shut, Ha / Hb the corridor joined to the arc's first / second sector only
ARC_STATES = {'D': [(1, 0)]*3, 'S': [(0, 0)]*3, 'B': [(1, 1)]*3, 'O': [(0, 1)]*3,
              'Ha': [(1, 0), (1, 0), (0, 0)], 'Hb': [(0, 0), (1, 0), (1, 0)]}

BASE = dict(M0=0.007, tau_s=3600.0, src='A1', delay_s=600.0, contain_s=600.0, transit_s=40.0, crew=(2, 2, 2), imv=1.0, door=1.0,
            tcc_eff=0.95, t2_s=4*H, project_to_s=168*H)
HORIZONS = (6, 12, 24)
EPS = dict(r1=0.05, r24=0.05, dose=0.5, co2_ch=0.5, airborne_g=0.1, r7d=0.05, restore_h=2.0)   # what counts as a real difference


def params(sc):
    p = dict(P0)
    p['edges'] = [dict(e, Q_m3_s=e['Q_m3_s']*(sc['imv'] if e['kind'] == 'imv' else sc['door'])) for e in P0['edges']]
    p['tcc_k_m3_s'] = ra.TRACE['tcc_flow_m3_s']['value']*sc['tcc_eff']
    return p


def route(frm, to):
    """The shortest walk between two compartments (any door can be cycled to pass)."""
    if frm == to:
        return [frm]
    adj = {k: [] for k in IDS}
    for e in P0['edges']:
        if e['kind'] == 'door':
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


def config_edges(arcs):
    """{edge id: open} for an arc-state triple."""
    out = {}
    for (_, links), s in zip(ARCS, arcs):
        for lk, (dmp, door) in zip(links, ARC_STATES[s]):
            out['IMV.' + lk] = bool(dmp); out['CIRC.' + lk] = bool(door)
    return out


NORMAL = config_edges(('D', 'D', 'D'))

_C1, _C2 = {}, {}


def bind(st, pkey):
    """Share propagators between runs of the same parameters (the model's own per-state caches, keyed by everything they depend on)."""
    ok = tuple(st['open'][e['id']] for e in P0['edges'])
    st['_cache'] = _C1.setdefault((pkey, ok, st['vent'], st['removal'], tuple(st['occupants'])), {})
    s = st['source']
    st['_tcache'] = _C2.setdefault((pkey, ok, st['vent'], st['tcc'], s['state'], s['node'], s['tau_s']), {})


def itineraries(strat, sc):
    """Each person's places over time: a list of (t_s, node index) and the containment time if any."""
    homes = [k for k, n in zip(('A1', 'A2', 'A3'), sc['crew']) for _ in range(n)]
    starts = list(sc.get('starts') or homes)
    dest = dict(zip(('A1', 'A2', 'A3'), strat['dest']))
    d, T = sc['delay_s'], sc['transit_s']
    people = []
    contain_t = None
    helper = None
    if strat['contain']:
        helper = min(range(len(starts)), key=lambda k: (len(route(starts[k], sc['src'])), k))
    for k, (home, here) in enumerate(zip(homes, starts)):
        plan = [(0.0, I[here])]
        t = d; where = here
        if k == helper:
            path = route(where, sc['src'])
            for j, node in enumerate(path[1:]):
                plan.append((t + j*T, I[node]))
            t += (len(path) - 1)*T
            t = t if len(path) > 1 else d
            contain_t = t + sc['contain_s']
            t = contain_t; where = sc['src']
        path = route(where, dest[home])
        for j, node in enumerate(path[1:]):
            plan.append((t + j*T, I[node]))
        people.append(dict(name=f'{home}-{sum(1 for h in homes[:k] if h == home) + 1}', home=home, plan=plan))
    return people, contain_t


def simulate(strat, sc, dt_main=300.0, fine=10.0, pkey=None, p=None):
    p = p or params(sc)
    pkey = pkey or repr(sorted((k, v) for k, v in sc.items() if k not in ('x0',)))
    st = ra.start(p, x0=sc.get('x0'))
    people, contain_t = itineraries(strat, sc)
    events = []                                   # (t, order, kind, value)
    for k, who in enumerate(people):
        for t, node in who['plan'][1:]:
            events.append((t, 1, 'move', (k, node)))
    events.append((sc['delay_s'], 0, 'config', config_edges(strat['arcs'])))
    if contain_t is not None:
        events.append((contain_t, 2, 'isolate', None))
    if strat['t2']:
        events.append((sc['t2_s'], 0, 'config', NORMAL))
    events.append((24*H, 0, 'config', NORMAL))
    events.append((24*H, 1, 'home', None))
    events.sort(key=lambda e: (e[0], e[1]))
    last_fine = max([sc['delay_s']] + [t for t, _, k, _ in events if k in ('move', 'isolate')])
    fine_end = (int(last_fine // dt_main) + 1)*dt_main
    where = [who['plan'][0][1] for who in people]

    def occ():
        o = [0]*N
        for n in where:
            o[n] += 1
        return o
    ra.set_occupants(st, occ())
    ra.set_source(st, p, sc['src'], sc['M0'], sc['tau_s'])
    bind(st, pkey)
    X = [0.0]*N; ppm = [0.0]*N
    tracks = [ax.Track(who['name'], where[k], 0.0) for k, who in enumerate(people)]
    for tr in tracks:
        tr.begin(X, ppm)
    co2_ch = {h: 0.0 for h in HORIZONS}; viable = {h: True for h in HORIZONS}; co2_peak = 0.0
    samples = []                                  # (t, max compartment ppm, airborne kg)
    ei = 0
    t_now = 0.0
    while t_now < sc['project_to_s'] - 1e-6:
        changed = False
        while ei < len(events) and events[ei][0] <= t_now + 1e-6:
            _, _, kind, v = events[ei]; ei += 1
            if kind == 'config':
                for eid, op in v.items():
                    ra.set_edge(st, eid, op)
            elif kind == 'move':
                k, node = v; where[k] = node; tracks[k].move(t_now, node, X, ppm)
            elif kind == 'isolate':
                ra.isolate_source(st)
            elif kind == 'home':
                for k, who in enumerate(people):
                    where[k] = I[who['home']]; tracks[k].move(t_now, where[k], X, ppm)
            changed = True
        if changed:
            ra.set_occupants(st, occ()); bind(st, pkey)
        dt = fine if t_now < fine_end - 1e-6 else (dt_main if t_now < 24*H - 1e-6 else 3600.0)
        nxt = events[ei][0] if ei < len(events) else sc['project_to_s']
        dt = min(dt, nxt - t_now) if nxt > t_now + 1e-6 else dt
        ra.step(st, p, dt)
        t_now = st['t_s']
        X = [ra.exposure_ppm_s(st, p, i) for i in range(N)]
        ppm = [ra.ppm(st, p, i) for i in range(N)]
        for tr in tracks:
            tr.sample(t_now, X, ppm)
        samples.append((t_now, max(ppm), sum(st['c'])))
        if t_now <= 24*H + 1e-6:
            xs = [st['m'][i]/p['M_CO2']/ra.n_mol(p, i) for i in range(N)]
            occupied = [xs[n] for n in set(where)]
            if t_now > sc['delay_s']:
                co2_peak = max(co2_peak, max(occupied))
            for h in HORIZONS:
                if t_now <= h*H + 1e-6:
                    co2_ch[h] += sum(dt/H for n in where if xs[n] > TARGET)
                    if max(occupied) > LIMIT:
                        viable[h] = False
    return st, p, tracks, samples, dict(co2_ch=co2_ch, viable=viable, co2_peak=co2_peak, contain_t=contain_t, people=people)


def score(st, p, tracks, samples, extra):
    out = dict(viable={}, obj={})
    for h in HORIZONS:
        hs = h*H
        r1 = r24 = 0.0; doses = []
        for tr in tracks:
            k = max(j for j in range(len(tr.t)) if tr.t[j] <= hs + 1e-6) + 1
            m1, _ = ax.window_max(tr.t[:k], tr.E[:k], H)
            m24 = ax.window_max(tr.t[:k], tr.E[:k], 24*H)[0] if h >= 24 else tr.E[k-1]/(24*H)   # below 24 h: the share of a 24 h mean so far
            r1 = max(r1, m1/SMAC['1h']); r24 = max(r24, m24/SMAC['24h']); doses.append(tr.E[k-1]/H)
        air = [a for t, _, a in samples if t <= hs + 1e-6][-1]
        o = dict(r1=r1, r24=r24, dose=sum(doses)/len(doses), co2_ch=extra['co2_ch'][h])
        if h < 24:
            o['airborne_g'] = air*1000.0
        else:
            r7 = max(tr.E[-1]/(tr.t[-1]) for tr in tracks)/SMAC['7d']
            over = [t for t, mx, _ in samples if mx > SMAC['7d']]
            o['r7d'] = r7
            # the last sample with any compartment over the long-term value; 999 when the ring is still over it at the end of the projection
            o['restore_h'] = 0.0 if not over else (999.0 if over[-1] >= samples[-1][0] - 1e-6 else over[-1]/H)
        out['obj'][h] = o
        out['viable'][h] = extra['viable'][h]
    out['co2_peak_pct'] = extra['co2_peak']*100
    out['person'] = {}
    for tr in tracks:
        k = sum(1 for t in tr.t if t <= 24*H + 1e-6)
        out['person'][tr.name] = dict(peak_ppm=max(tr.ppm[:k]), dose24_ppm_h=tr.E[k-1]/H, max_1h_ppm=ax.window_max(tr.t[:k], tr.E[:k], H)[0],
                                      mean24_ppm=tr.E[k-1]/(24*H), transit_ppm_h=transit_dose(tr), mean7d_ppm=tr.E[-1]/tr.t[-1])
    out['ledger'] = dict(co2_kg=ra.ledger_error(st), nh3_kg=ra.trace_ledger_error(st), release_kg=ra.release_ledger_error(st))
    out['released_g'] = st['released']*1000.0; out['removed_g'] = st['nh3_removed']*1000.0; out['contain_t_min'] = (extra['contain_t'] or 0)/60.0
    return out


def transit_dose(tr):
    """ppm h received while walking: every stay after the start shorter than 15 min is a compartment passed on the way."""
    dose = 0.0
    for (t0, _), (t1, _) in zip(tr.places[1:], tr.places[2:]):
        if t1 - t0 <= 900.0:
            ia = next(j for j in range(len(tr.t)) if tr.t[j] >= t0 - 1e-6)
            ib = next(j for j in range(len(tr.t)) if tr.t[j] >= t1 - 1e-6)
            dose += tr.E[ib] - tr.E[ia]
    return dose/H


def family(strat):
    """A coarse label for what a strategy does: containment, what becomes of the source's compartment, where sector 1's pair goes."""
    st = dict(open={e['id']: False for e in P0['edges']})
    st['open'].update(config_edges(strat['arcs']))
    conn = {k: set() for k in IDS}
    for e in P0['edges']:
        if st['open'][e['id']]:
            a, b = IDS[e['i']], IDS[e['j']]; conn[a].add(b); conn[b].add(a)
    seen = {'A1'}; q = ['A1']
    while q:
        c = q.pop()
        for n in conn[c]:
            if n not in seen:
                seen.add(n); q.append(n)
    a1 = 'sealed' if seen == {'A1'} else ('to TCC' if 'A3' in seen else ('to A2' if 'A2' in seen else 'own corridor'))
    return f"{'contain' if strat['contain'] else 'no contain'} / A1 {a1} / S1 crew to {strat['dest'][0]}{' / reconnect' if strat['t2'] else ''}"


def strategies():
    for arcs in itertools.product(ARC_STATES, repeat=3):
        for dest in itertools.product(('A1', 'A2', 'A3'), ('A2', 'A3'), ('A3', 'A2')):
            for contain in (0, 1):
                for t2 in (0, 1):
                    if t2 and arcs == ('D', 'D', 'D'):
                        continue                         # reconnecting the normal state changes nothing
                    yield dict(arcs=arcs, dest=dest, contain=contain, t2=t2)


def run_one(args):
    strat, sc = args
    st, p, tracks, samples, extra = simulate(strat, sc)
    s = score(st, p, tracks, samples, extra)
    s['strat'] = strat
    return s


def dominates(a, b, keys, eps):
    return all(a[k] <= b[k] + eps[k] for k in keys) and any(a[k] < b[k] - eps[k] for k in keys)


def front(rows, h):
    v = [r for r in rows if r['viable'][h]]
    keys = list(v[0]['obj'][h]) if v else []
    obj = [r['obj'][h] for r in v]
    f = [r for r, o in zip(v, obj) if not any(dominates(q, o, keys, EPS) for q in obj if q is not o)]
    return v, f, keys


def judge(rows, h):
    """Criteria A, B and D for one horizon: viable count, the epsilon-non-dominated set, its families, and whether one strategy sits within
    epsilon of the best value on every objective (a trivial optimum)."""
    v, f, keys = front(rows, h)
    if not v:
        return dict(viable=0, front=0, families=[], trivial=None)
    ideal = {k: min(r['obj'][h][k] for r in v) for k in keys}
    trivial = [r for r in v if all(r['obj'][h][k] <= ideal[k] + EPS[k] for k in keys)]
    fams = sorted({family(r['strat']) for r in f})
    # the spread on the front: for each objective, best and worst on the front
    spread = {k: (round(min(r['obj'][h][k] for r in f), 4), round(max(r['obj'][h][k] for r in f), 4)) for k in keys}
    return dict(viable=len(v), front=len(f), families=fams, n_families=len(fams), trivial=len(trivial),
                trivial_example=family(trivial[0]['strat']) if trivial else None, ideal={k: round(x, 4) for k, x in ideal.items()},
                spread=spread)


def summarise(r, h):
    o = r['obj'][h]
    return dict(family=family(r['strat']), arcs=''.join(f"{n}:{s} " for (n, _), s in zip(ARCS, r['strat']['arcs'])).strip(),
                dest=r['strat']['dest'], contain=r['strat']['contain'], t2=r['strat']['t2'], **{k: round(x, 3) for k, x in o.items()},
                co2_peak_pct=round(r['co2_peak_pct'], 3))


def search(sc, pool):
    todo = [(s, sc) for s in strategies()]
    return pool.map(run_one, todo, chunksize=64)


# The strategies the brief names, in the search's terms (sector 1's pair, sector 2's pair, sector 3's pair destinations)
NAMED = {
    'do nothing (ventilation on, nobody moves)': dict(arcs=('D', 'D', 'D'), dest=('A1', 'A2', 'A3'), contain=0, t2=0),
    'seal and stay (every sector sealed)': dict(arcs=('S', 'S', 'S'), dest=('A1', 'A2', 'A3'), contain=0, t2=0),
    'seal A1, its crew to sector 2': dict(arcs=('Hb', 'D', 'Ha'), dest=('A2', 'A2', 'A3'), contain=0, t2=0),
    'seal A1, its crew to sector 3': dict(arcs=('Hb', 'D', 'Ha'), dest=('A3', 'A2', 'A3'), contain=0, t2=0),
    'seal A1 4 h, then reconnect': dict(arcs=('Hb', 'D', 'Ha'), dest=('A2', 'A2', 'A3'), contain=0, t2=1),
    'ventilation off (dampers shut), crew stay': dict(arcs=('O', 'S', 'S'), dest=('A1', 'A2', 'A3'), contain=0, t2=0),
    'limited doors: A1 to the TCC the short way': dict(arcs=('S', 'S', 'B'), dest=('A2', 'A2', 'A2'), contain=0, t2=0),
    'full loop open (dampers and doors)': dict(arcs=('B', 'B', 'B'), dest=('A1', 'A2', 'A3'), contain=0, t2=0),
    'everyone to the scrubber (sector 3)': dict(arcs=('D', 'D', 'D'), dest=('A3', 'A3', 'A3'), contain=0, t2=0),
    'preserve the clean sectors (A1 sealed, 2-3 joined)': dict(arcs=('Hb', 'B', 'Ha'), dest=('A3', 'A2', 'A3'), contain=0, t2=0),
    'contain the spill, ventilation on': dict(arcs=('D', 'D', 'D'), dest=('A1', 'A2', 'A3'), contain=1, t2=0),
    'contain the spill, A1 sealed after': dict(arcs=('Hb', 'D', 'Ha'), dest=('A2', 'A2', 'A3'), contain=1, t2=1),
}


def sensitivities():
    """One value at a time around the base (criterion F). x0 for twelve crew: their steady state with the fans on."""
    s12 = ra.start(P0); ra.set_occupants(s12, [4, 4, 4] + [0]*6); ra.step(s12, P0, 400*H)
    x12 = [s12['m'][i]/P0['M_CO2']/ra.n_mol(P0, i) for i in range(N)]
    return {
        'inventory 3 g': dict(M0=0.003), 'inventory 20 g': dict(M0=0.020),
        'release tau 15 min': dict(tau_s=900.0), 'release tau 4 h': dict(tau_s=4*H),
        'ventilation x0.5': dict(imv=0.5), 'ventilation x1.5': dict(imv=1.5),
        'door flow x0.5': dict(door=0.5), 'door flow x2': dict(door=2.0),
        'TCC efficiency 0.5': dict(tcc_eff=0.5), 'TCC efficiency 1.0 at 2x flow': dict(tcc_eff=1.9),
        'sector 1 pair awake in sector 2': dict(starts=('A2', 'A2', 'A2', 'A2', 'A3', 'A3')),
        'twelve crew (4/4/4)': dict(crew=(4, 4, 4), x0=x12),
        'reaction 5 min': dict(delay_s=300.0), 'reaction 30 min': dict(delay_s=1800.0),
        'containment 20 min': dict(contain_s=1200.0), 'transit 80 s per compartment': dict(transit_s=80.0),
        'reconnect at 8 h': dict(t2_s=8*H),
    }


def step_check(pool):
    """Time-step independence and repeatability on the named strategies: 300 s against 60 s main steps (the fine phase stays at 10 s, so
    every event time is a step boundary), and the same run twice."""
    worst = 0.0; same = True
    for name, s in NAMED.items():
        a = simulate(s, BASE, dt_main=300.0); b = simulate(s, BASE, dt_main=60.0); c = simulate(s, BASE, dt_main=300.0)
        for ta, tb in zip(a[2], b[2]):
            worst = max(worst, abs(ta.E[-1] - tb.E[-1])/max(abs(tb.E[-1]), 1e-30))
        worst = max(worst, max(abs(x - y)/max(abs(y), 1e-30) for x, y in zip(a[0]['c'] + a[0]['m'], b[0]['c'] + b[0]['m'])))
        same = same and a[0]['c'] == c[0]['c'] and a[0]['m'] == c[0]['m'] and all(x.E == y.E for x, y in zip(a[2], c[2]))
    return dict(worst_rel_300_vs_60=worst, repeat_identical=same)


def main():
    t0 = time.time()
    out = dict(study='Deadship Phase 2B engineering gate, second attempt (SYS-002 v2)', date='2026-11-14',
               model=dict(file='src/wayfarer/ring_air.py', version=ra.VERSION), base={k: v for k, v in BASE.items()}, eps=EPS,
               smac_ppm=SMAC, co2_target_pct=TARGET*100, co2_limit_pct=LIMIT*100, horizons_h=list(HORIZONS),
               arc_states={k: v for k, v in ARC_STATES.items()})
    with mp.Pool(4) as pool:
        rows = search(BASE, pool)
        out['configurations'] = len(rows)
        out['max_ledger_kg'] = {k: max(abs(r['ledger'][k]) for r in rows) for k in ('co2_kg', 'nh3_kg', 'release_kg')}
        out['base'] = {}
        for h in HORIZONS:
            j = judge(rows, h)
            v, f, keys = front(rows, h)
            j['front_members'] = [summarise(r, h) for r in sorted(f, key=lambda r: (family(r['strat']), r['obj'][h]['r24']))]
            out['base'][f'{h}h'] = j
        # the named strategies (rerun; the search holds the same rows)
        out['named'] = {}
        for name, s in NAMED.items():
            r = run_one((s, BASE))
            onfront = {f'{h}h': any(x['strat'] == r['strat'] for x in front(rows, h)[1]) for h in HORIZONS}
            out['named'][name] = dict(family=family(s), on_front=onfront, viable=r['viable'], co2_peak_pct=round(r['co2_peak_pct'], 3),
                                      obj={f'{h}h': {k: round(x, 3) for k, x in r['obj'][h].items()} for h in HORIZONS},
                                      person={k: {a: round(b, 2) for a, b in v.items()} for k, v in r['person'].items()},
                                      released_g=round(r['released_g'], 3), removed_g=round(r['removed_g'], 3))
        print(f'base search: {len(rows)} runs in {time.time() - t0:.0f} s', flush=True)
        out['sensitivity'] = {}
        for name, d in sensitivities().items():
            sc = dict(BASE, **d)
            t1 = time.time()
            rs = search(sc, pool)
            out['sensitivity'][name] = {f'{h}h': {k: v for k, v in judge(rs, h).items() if k in ('viable', 'front', 'n_families', 'families', 'trivial',
                                                                                             'trivial_example', 'spread')}
                                        for h in HORIZONS}
            print(f'  {name}: {time.time() - t1:.0f} s, families at 24 h {out["sensitivity"][name]["24h"]["n_families"]}, '
                  f'trivial {out["sensitivity"][name]["24h"]["trivial"]}', flush=True)
            _C1.clear(); _C2.clear()
        out['step_check'] = step_check(pool)
    out['elapsed_s'] = round(time.time() - t0)
    (HERE / 'ds2b_gate.json').write_text(json.dumps(out, indent=1, default=list) + '\n')
    return out


if __name__ == '__main__':
    o = main()
    for h in HORIZONS:
        b = o['base'][f'{h}h']
        print(f"\n== {h} h: {b['viable']} viable, front {b['front']}, families {b['n_families']}, trivial {b['trivial']} ({b['trivial_example']})")
        print('   ideal', b['ideal']); print('   spread', b['spread'])
        for fam in b['families']:
            print('   ', fam)
    print('\nnamed')
    for k, v in o['named'].items():
        print(f"  {k:52s} front {v['on_front']} viable {v['viable']} 24h {v['obj']['24h']}")
    print('\nstep check', o['step_check'], 'ledgers', o['max_ledger_kg'], 'elapsed', o['elapsed_s'], 's')
