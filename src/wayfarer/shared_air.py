"""Deadship DS-2B "Shared Air" (Phase 2B): the scenario layer over ring A's two-gas air model (ring_air, SYS-002 v2). Standard library only.

The scenario owns its training values (data/deadship/ds2_shared_air.toml: the source it starts, the crew and their orders, the alert,
the containment work, the time scales, the watch and its recovery plans, the reuse criterion, texts) and calls only the model's public
operations (start, set_source, isolate_source, set_edge, set_vent, set_tcc, set_removal, set_occupants, step, ppm, exposure_ppm_s,
components, readout). It owns no gas equation: every concentration, exposure and removal is the model's.

One run is a deterministic machine on a fixed 10 s step. Actions apply at step boundaries in the order they arrive:

    trainee <node>          the trainee's compartment (the walk reports it from the body; a reference script states it)
    door <CIRC id> <bool>   a CIRC door (the walk's leaf); a close is refused while an ordered pair stands in that doorway
    damper <suffix> <bool>  one bulkhead's IMV damper pair      vent <bool>  every IMV fan
    tcc <bool>  removal <bool>   the trace-contaminant control and the CO2 unit (at the ECLSS bay: the caller checks the place)
    order <pair> <sector>   a pair walks to a sector (pair A: the trainee's partner)      hold <pair>   stop where they are
    contain_start / contain_stop   the trainee's work at hygiene A (refused away from the source's compartment)
    schedule <t_s|None>     at the ECLSS bay: the ducts' reconnection (every IMV damper pair open, the fans on) at ship time t_s, or
                            cancel it. Remote equipment only; doors are never operated remotely. Refused in the past, off the step grid
                            or after the watch's end; it runs when due in any phase, logged, and it is part of what the watch tests
    watch <plan>            the stability watch from the exact present state (NONE or RESTORE), then the 7-day projection

At each boundary: the due actions, then a due scheduled reconnection, then the pairs' walks, then a completed containment isolates the source, then the occupants are
counted where everybody is; the model steps; each person's exposure adds their compartment's exact integral over the step.

    python3 src/wayfarer/shared_air.py      # check the scenario, run the reference cases, print their outcomes
"""
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ring_air   # noqa: E402

SCENARIO = 'data/deadship/ds2_shared_air.toml'
FILE = 'wf_deadship_ds2.json'
SCHEMA = 'WF_DEADSHIP_SCENARIO'
VERSION = 1
SECTORS = ('A1', 'A2', 'A3')
ENGINEERING_KEYS = {'co2_target', 'co2_max', 'P_Pa', 'T_K', 'V_m3', 'occupants', 'per_person_kg_s', 'k_m3_s', 'Q_m3_s', 'tcc_flow_m3_s',
                    'tcc_efficiency', 'tcc_k_m3_s', 'smac', 'value_ppm', 'M_NH3', 'M_CO2'}
EPS = 1e-6
H = 3600.0


def _keys(d, path=''):
    if isinstance(d, dict):
        for k, v in d.items():
            yield f'{path}{k}', k
            yield from _keys(v, f'{path}{k}.')
    elif isinstance(d, list):
        for i, v in enumerate(d):
            yield from _keys(v, f'{path}{i}.')


def load(root=ROOT, path=SCENARIO):
    sc = tomllib.loads((Path(root) / path).read_text())
    bad = sorted(p for p, k in _keys(sc) if k in ENGINEERING_KEYS)
    if bad:
        raise ValueError(f'{path}: a scenario must not set engineering values: {bad}')
    if sc['scenario'].get('scored'):
        raise ValueError(f'{path}: Phase 2B is unscored')
    if sc['source']['compartment'] not in SECTORS:
        raise ValueError(f'{path}: the source must be in a sector')
    dt, pdt = sc['time']['dt_s'], sc['time']['projection_dt_s']
    for k, v in (('alert', sc['time']['alert_s']), ('transit', sc['crew']['transit_s']), ('doorway', sc['crew']['doorway_s']),
                 ('work', sc['containment']['work_s']), ('projection step', pdt), ('hour', H)):
        if abs(v/dt - round(v/dt)) > 1e-9:
            raise ValueError(f'{path}: {k} {v} s is not a whole number of {dt} s steps')
    if abs(H/pdt - round(H/pdt)) > 1e-9:
        raise ValueError(f'{path}: the projection step must divide an hour')
    return sc


def params(root=ROOT):
    import life_support
    import spec
    return ring_air.params(spec.load(Path(root))[0], life_support.load(Path(root)))


class Run:
    """One play of the scenario (or one reference script) on the model."""

    def __init__(self, sc, p):
        self.sc, self.p = sc, p
        self.ids = p['ids']; self.N = len(self.ids); self.I = {k: i for i, k in enumerate(self.ids)}
        self.dt = float(sc['time']['dt_s']); self.pdt = float(sc['time']['projection_dt_s'])
        self.T = float(sc['crew']['transit_s']); self.doorway = float(sc['crew']['doorway_s'])
        self.st = ring_air.start(p)
        self.people = []
        for pair, home in sc['crew']['pairs']:
            for k in (1, 2):
                self.people.append(dict(id=f'{pair}-{k}', pair=pair, home=self.I[home], node=self.I[home], route=[], next_t=0.0,
                                        places=[[0.0, self.I[home]]], E=0.0, mark=0.0, peak=0.0, co2_s=0.0, t=[0.0], Es=[0.0],
                                        max1h=0.0, j=0, max24=0.0, j24=0))
        self.contain = dict(state='NONE', progress_s=0.0)
        self.phase = 'LIVE'                       # LIVE, WATCH, PROJECTION, DONE
        self.plan = 'NONE'
        self.schedule = None                      # the declared duct reconnection: dict(t_s, done)
        self.co2_peak = 0.0                       # the highest CO2 mole fraction where anybody was (live and watch) and when
        self.co2_peak_t = 0.0
        self.watch = {}
        self.log = []
        self.alerted = False
        self.co2_limit_crossed_at = None
        self.samples = []                         # (t, max ppm anywhere, airborne kg) at every step
        self.over_last = {k: None for k in self.ids}   # the last step each compartment was above the reuse criterion
        self._occupy()
        ring_air.set_source(self.st, p, sc['source']['compartment'], float(sc['source']['inventory_kg']), float(sc['source']['tau_s']))

    # ---- state ---------------------------------------------------------------------------------------------------------------------------
    @property
    def t(self):
        return self.st['t_s']

    def X(self):
        return [ring_air.exposure_ppm_s(self.st, self.p, i) for i in range(self.N)]

    def ppms(self):
        return [ring_air.ppm(self.st, self.p, i) for i in range(self.N)]

    def x(self, i):
        return self.st['m'][i]/self.p['M_CO2']/ring_air.n_mol(self.p, i)

    def _occupy(self):
        occ = [0]*self.N
        for q in self.people:
            occ[q['node']] += 1
        ring_air.set_occupants(self.st, occ)

    def _place(self, q, node):
        if node != q['node']:
            q['node'] = node
            q['places'].append([self.t, node])
            q['mark'] = ring_air.exposure_ppm_s(self.st, self.p, node)

    def sealed(self, door):
        """A bulkhead the trainee has sealed: its door shut and its IMV damper pair shut. Pairs cycle a shut door, never a sealed one."""
        imv = 'IMV.' + door.split('.', 1)[1]
        return not self.st['open'][door] and not self.st['open'].get(imv, True)

    def route(self, frm, to):
        """The shortest CIRC door route that crosses no sealed bulkhead (breadth first, the edges' own order): node indices from frm to
        to, or None when every way is sealed."""
        if frm == to:
            return [frm]
        adj = [[] for _ in range(self.N)]
        for e in self.p['edges']:
            if e['kind'] == 'door' and not self.sealed(e['id']):
                adj[e['i']].append(e['j']); adj[e['j']].append(e['i'])
        prev = {frm: None}; q = [frm]
        while q:
            c = q.pop(0)
            for n in adj[c]:
                if n not in prev:
                    prev[n] = c; q.append(n)
        if to not in prev:
            return None
        path = [to]
        while prev[path[-1]] is not None:
            path.append(prev[path[-1]])
        return path[::-1]

    def door_between(self, a, b):
        for e in self.p['edges']:
            if e['kind'] == 'door' and {e['i'], e['j']} == {a, b}:
                return e['id']
        return ''

    def in_doorway(self, door):
        """Who stands in a doorway now: an ordered person in the last `doorway` seconds before entering the next compartment."""
        return [q['id'] for q in self.people if q['route'] and self.t >= q['next_t'] - self.doorway - EPS
                and self.door_between(q['node'], q['route'][0]) == door]

    def members(self, pair):
        return [q for q in self.people if q['pair'] == pair and q['id'] != 'A-1']

    # ---- actions -------------------------------------------------------------------------------------------------------------------------
    def act(self, kind, *a):
        """One action now. Returns '' when done, else the refusal (the state is then unchanged)."""
        r = self._act(kind, *a)
        self.log.append([self.t, kind, list(a), r])
        return r

    def _act(self, kind, *a):
        st = self.st
        if self.phase != 'LIVE' and kind not in ('report',):
            return 'the watch is running: nothing can be changed now'
        if kind == 'trainee':
            self._place(self.people[0], self.I[a[0]]); self._occupy()
            if self.contain['state'] == 'WORKING' and self.people[0]['node'] != self.I[self.sc['source']['compartment']]:
                self.contain['state'] = 'PAUSED'
            return ''
        if kind == 'door':
            eid, op = a
            if not op and st['open'][eid] and self.in_doorway(eid):
                return f'the doorway is occupied by {", ".join(self.in_doorway(eid))}'
            ring_air.set_edge(st, eid, bool(op)); return ''
        if kind == 'damper':
            ring_air.set_edge(st, 'IMV.' + a[0], bool(a[1])); return ''
        if kind == 'vent':
            ring_air.set_vent(st, bool(a[0])); return ''
        if kind == 'tcc':
            ring_air.set_tcc(st, bool(a[0])); return ''
        if kind == 'removal':
            ring_air.set_removal(st, bool(a[0])); return ''
        if kind in ('order', 'hold'):
            pair = a[0]
            ms = self.members(pair)
            if not ms:
                return f'no pair {pair}'
            if kind == 'hold':
                for q in ms:
                    q['route'] = []
                return ''
            dest = a[1]
            if dest not in SECTORS:
                return f'{dest} is not a sector a pair can be sent to'
            d = self.I[dest]
            if all(q['node'] == d and not q['route'] for q in ms):
                return f'pair {pair} is already in {dest}'
            paths = [self.route(q['node'], d) for q in ms]
            if any(path is None for path in paths):
                return f'pair {pair} cannot reach {dest}: every way crosses a sealed bulkhead (door and dampers shut)'
            for q, path in zip(ms, paths):
                q['route'] = path[1:]; q['next_t'] = self.t + self.T
            return ''
        if kind == 'contain_start':
            if st['source']['state'] != 'LEAKING':
                return 'there is nothing left to contain' if st['source']['state'] == 'ISOLATED' else 'no leak here'
            if self.people[0]['node'] != self.I[self.sc['source']['compartment']]:
                return 'the store is in hygiene A: you have to be there'
            self.contain['state'] = 'WORKING'; return ''
        if kind == 'contain_stop':
            if self.contain['state'] == 'WORKING':
                self.contain['state'] = 'PAUSED'
            return ''
        if kind == 'schedule':
            if a[0] is None:
                self.schedule = None; return ''
            ts = float(a[0])
            if ts <= self.t + EPS:
                return 'that time has passed: a reconnection is scheduled ahead of the ship clock'
            if abs(ts/self.dt - round(ts/self.dt)) > 1e-9:
                return f'a reconnection is scheduled on the {self.dt:.0f} s step'
            if ts > float(self.sc['watch']['ship_h'])*H + EPS:
                return f'a reconnection is scheduled before the watch ends ({float(self.sc["watch"]["ship_h"]):.0f} h)'
            self.schedule = dict(t_s=ts, done=None); return ''
        if kind == 'watch':
            if a[0] not in self.sc['watch']['plans']:
                return f'no plan {a[0]}'
            self._start_watch(a[0]); return ''
        if kind == 'report':
            return ''
        raise ValueError(kind)

    # ---- time ----------------------------------------------------------------------------------------------------------------------------
    def _walks(self):
        for q in self.people:
            while q['route'] and self.t >= q['next_t'] - EPS:
                door = self.door_between(q['node'], q['route'][0])
                if self.sealed(door):                              # sealed after the order: they stop and wait where they are
                    q['route'] = []
                    self.log.append([self.t, 'stopped', [q['id'], door], ''])
                    break
                self._place(q, q['route'].pop(0))
                q['next_t'] += self.T

    def tick(self, dt=None):
        """One step: the walks, a completed containment, the occupants, the model, the exposures."""
        dt = self.dt if dt is None else dt
        self._scheduled()
        self._walks()
        if self.contain['state'] in ('WORKING', 'PAUSED') and self.contain['progress_s'] >= float(self.sc['containment']['work_s']) - EPS:
            ring_air.isolate_source(self.st)
            self.contain['state'] = 'DONE'
            self.log.append([self.t, 'contained', [], ''])
        self._occupy()
        ring_air.step(self.st, self.p, dt)
        if self.contain['state'] == 'WORKING':
            self.contain['progress_s'] += dt
        if not self.alerted and self.t >= float(self.sc['time']['alert_s']) - EPS:
            self.alerted = True
        X = self.X(); pp = self.ppms()
        target, limit = self.p['co2_target'], self.p['co2_max']
        for q in self.people:
            n = q['node']
            q['E'] += X[n] - q['mark']; q['mark'] = X[n]
            q['peak'] = max(q['peak'], pp[n])
            if self.x(n) > target:
                q['co2_s'] += dt
            q['t'].append(self.t); q['Es'].append(q['E'])
            q['max1h'], q['j'] = _roll(q['t'], q['Es'], H, q['max1h'], q['j'])
            q['max24'], q['j24'] = _roll(q['t'], q['Es'], 24*H, q['max24'], q['j24'])
        if self.phase in ('LIVE', 'WATCH'):
            xo = max(self.x(q['node']) for q in self.people)
            if xo > self.co2_peak:
                self.co2_peak, self.co2_peak_t = xo, self.t
            if self.co2_limit_crossed_at is None and xo > limit:
                self.co2_limit_crossed_at = self.t
        self.samples.append((self.t, max(pp), sum(self.st['c'])))
        reuse = float(self.sc['reuse']['ppm'])
        for i, v in enumerate(pp):
            if v > reuse:
                self.over_last[self.ids[i]] = self.t

    def _scheduled(self):
        """The declared duct reconnection, when due: the ECLSS controller opens every IMV damper pair and runs the fans. Doors stay as
        they are. It runs at the first step boundary at or after its time, before the walks."""
        s = self.schedule
        if s is None or s['done'] is not None or self.t < s['t_s'] - EPS:
            return
        st = self.st
        opened = [e['id'] for e in self.p['edges'] if e['kind'] == 'imv' and not st['open'][e['id']]]
        for eid in opened:
            ring_air.set_edge(st, eid, True)
        fans = st['vent'] != 'ON'
        ring_air.set_vent(st, True)
        s['done'] = self.t
        self.log.append([self.t, 'reconnect', [opened, fans], ''])

    def _start_watch(self, plan):
        self.plan = plan
        self.phase = 'WATCH'
        if self.contain['state'] == 'WORKING':
            self.contain['state'] = 'PAUSED'
        end = max(float(self.sc['watch']['ship_h'])*H, self.t + float(self.sc['watch']['min_h'])*H)
        end = -(-end // self.pdt)*self.pdt                          # on the projection grid
        self.watch = dict(plan=plan, t0=self.t, end_s=end, config=self.config(), limit_crossed_at=None, family=self.family(),
                          schedule=None if self.schedule is None else dict(self.schedule))

    def run_watch(self):
        """The watch at the live step to its end, then the verdict, the plan and the projection (the caller may instead tick the watch
        itself at watch_scale and call finish_watch)."""
        while self.t < self.watch['end_s'] - EPS:
            self.tick()
        self.finish_watch()

    def finish_watch(self):
        self.watch['verdict'] = self.verdict()
        if self.plan == 'RESTORE':
            st = self.st
            ring_air.set_vent(st, True)
            for e in self.p['edges']:
                if e['kind'] == 'imv':
                    ring_air.set_edge(st, e['id'], True)          # remote equipment only: the doors stay as the trainee left them
            ring_air.set_tcc(st, True); ring_air.set_removal(st, True)
            self.log.append([self.t, 'restore', [], ''])
        self.phase = 'PROJECTION'
        end = float(self.sc['watch']['projection_h'])*H
        while self.t < end - EPS:
            if self.plan == 'RESTORE' and abs(self.t/H - round(self.t/H)) < 1e-9:
                self._go_home()
            walking = any(q['route'] for q in self.people)
            on_grid = abs(self.t/self.pdt - round(self.t/self.pdt)) < 1e-9
            self.tick(self.dt if walking or not on_grid else self.pdt)
        self.phase = 'DONE'

    def _go_home(self):
        reuse = float(self.sc['reuse']['ppm'])
        for q in self.people:
            path = self.route(q['node'], q['home'])
            if path is not None and q['node'] != q['home'] and not q['route'] and all(ring_air.ppm(self.st, self.p, n) <= reuse for n in path):
                q['route'] = path[1:]; q['next_t'] = self.t + self.T
                self.log.append([self.t, 'home', [q['id']], ''])

    # ---- reading -------------------------------------------------------------------------------------------------------------------------
    def groups(self):
        return ring_air.components(self.st, self.p)

    def config(self):
        st = self.st
        return dict(doors_open=sorted(e['id'] for e in self.p['edges'] if e['kind'] == 'door' and st['open'][e['id']]),
                    dampers_closed=sorted(e['id'] for e in self.p['edges'] if e['kind'] == 'imv' and not st['open'][e['id']]),
                    vent=st['vent'], tcc=st['tcc'], removal=st['removal'], source=st['source']['state'],
                    places={q['id']: self.ids[q['node']] for q in self.people},
                    reconnect_at_s=None if self.schedule is None or self.schedule['done'] is not None else self.schedule['t_s'],
                    walking={q['id']: self.ids[q['route'][-1]] for q in self.people if q['route']})

    def family(self):
        """Which of the gate's families the present configuration belongs to (a description, never a grade)."""
        if self.st['source']['state'] == 'LEAKING':
            return 'UNCONTAINED'
        src = self.I[self.sc['source']['compartment']]; tcc = self.p['tcc_node']
        gs = self.groups()
        g_src = next(g for g in gs if src in g)
        if tcc not in g_src or self.st['tcc'] != 'ON':
            return 'ISOLATE'
        dest = {q['id']: (q['route'][-1] if q['route'] else q['node']) for q in self.people}
        if any(tcc not in next(g for g in gs if n in g) for n in dest.values()):
            return 'SEPARATE'
        return 'ROUTE'

    def verdict(self):
        st, p = self.st, self.p
        gs = self.groups()
        occ = [g for g in gs if any(q['node'] in g for q in self.people)]
        unbounded = [[self.ids[i] for i in g] for g in occ if p['removal'] not in g or st['removal'] != 'ON']
        tcc = p['tcc_node']
        away = sum(st['c'][i] for g in gs if tcc not in g or st['tcc'] != 'ON' for i in g)
        reuse = float(self.sc['reuse']['ppm'])
        residue = [self.ids[i] for g in gs if tcc not in g or st['tcc'] != 'ON' for i in g if ring_air.ppm(st, p, i) > reuse]
        crossed = self.co2_limit_crossed_at is not None              # where anybody was, before or during the watch
        if st['source']['state'] == 'LEAKING':
            result = 'NOT_CONTAINED'
        elif crossed:
            result = 'CO2_LIMIT'
        elif unbounded:
            result = 'TEMPORARY'
        elif residue:
            result = 'STABLE_RESIDUE'               # CO2 held, but NH3 above the reuse criterion where nothing removes it
        else:
            result = 'STABLE'
        return dict(result=result, co2_limit_crossed_at_h=None if self.co2_limit_crossed_at is None else self.co2_limit_crossed_at/H,
                    co2_unremoved_groups=unbounded, nh3_residue=residue, nh3_airborne_g=sum(st['c'])*1000.0, nh3_away_from_tcc_g=away*1000.0,
                    source=st['source']['state'], t_h=self.t/H,
                    max_occupied_co2_pct=100.0*max(self.x(q['node']) for q in self.people),
                    co2_peak_pct=100.0*self.co2_peak, co2_peak_h=self.co2_peak_t/H,
                    co2_above_target_crew_h=sum(q['co2_s'] for q in self.people)/H,
                    degraded=crossed is False and sum(q['co2_s'] for q in self.people) > 0.0)

    def debrief(self):
        """What was saved and what it cost: every number from the run's own model state and exposure records."""
        st, p, smac = self.st, self.p, ring_air.NH3_SMAC['value_ppm']
        span = self.t
        people = []
        for q in self.people:
            m24 = q['max24'] if span >= 24*H - EPS else None
            i24 = max(k for k in range(len(q['t'])) if q['t'][k] <= 24*H + EPS)
            people.append(dict(id=q['id'], pair=q['pair'], route=[[round(t/H, 4), self.ids[n]] for t, n in q['places']],
                               peak_ppm=q['peak'], max_1h_ppm=q['max1h'], max_24h_ppm=m24, mean_7d_ppm=q['E']/span if span >= 7*24*H - EPS else None,
                               dose_24h_ppm_h=q['Es'][i24]/H, dose_ppm_h=q['E']/H, co2_above_target_h=q['co2_s']/H,
                               over=[k for k, v, ref in (('1h', q['max1h'], smac['1h']), ('24h', m24, smac['24h']),
                                                         ('7d', q['E']/span if span >= 7*24*H - EPS else None, smac['7d']))
                                     if v is not None and v > ref]))
        reuse = float(self.sc['reuse']['ppm'])
        clear = {}
        over_last = self.over_last
        end = self.samples[-1][0] if self.samples else 0.0
        for k, t in over_last.items():
            clear[k] = 0.0 if t is None else (None if t >= end - EPS else t/H)
        x = [self.x(i) for i in range(self.N)]
        return dict(people=people, released_g=st['released']*1000.0, retained_g=st['S']*1000.0, removed_g=st['nh3_removed']*1000.0,
                    airborne_g=sum(st['c'])*1000.0, inventory_g=st['S0']*1000.0, co2_mean_pct=100.0*sum(st['m'])/p['M_CO2']/sum(ring_air.n_mol(p, i) for i in range(self.N)),
                    co2_max_pct=100.0*max(x), clear_h=clear, watch=self.watch, plan=self.plan, contained_at_h=next((e[0]/H for e in self.log if e[1] == 'contained'), None),
                    co2_peak_pct=100.0*self.co2_peak, co2_peak_h=self.co2_peak_t/H, schedule=self.schedule, decisions=self.decisions(),
                    ledgers=self.ledgers())

    def decisions(self):
        """What the trainee decided and what the ship did on its own account, in order: [t_h, kind, args] (refused actions and the
        trainee's own steps left out; the debrief counts refusals separately). A reconnection time stepped through several values in a
        row counts once, as its last value."""
        keep = ('contain_start', 'contained', 'door', 'damper', 'vent', 'tcc', 'removal', 'order', 'hold', 'schedule', 'watch', 'reconnect',
                'restore', 'stopped')
        out = []
        for e in self.log:
            if e[1] in keep and not e[3]:
                if e[1] == 'schedule' and out and out[-1][1] == 'schedule':
                    out.pop()
                out.append([e[0]/H, e[1], e[2]])
        return out

    def ledgers(self):
        return dict(co2_kg=ring_air.ledger_error(self.st), nh3_kg=ring_air.trace_ledger_error(self.st), release_kg=ring_air.release_ledger_error(self.st))

    def checkpoint(self):
        st = self.st
        return dict(t_s=self.t, phase=self.phase, m=list(st['m']), c=list(st['c']), S=st['S'], released=st['released'], removed=st['nh3_removed'],
                    E=[q['E'] for q in self.people], max1h=[q['max1h'] for q in self.people], max24=[q['max24'] for q in self.people], nodes=[self.ids[q['node']] for q in self.people],
                    co2_s=[q['co2_s'] for q in self.people], contain=dict(self.contain))


def _roll(t, E, w, best, j):
    """The running largest mean over a window w ending at the newest sample (E = 0 before the release); the pointer j moves forward only.
    The same rule as air_exposure.window_max, one sample at a time (tests/test_shared_air.py compares them)."""
    k = len(t) - 1
    start = t[k] - w
    if start <= 0.0:
        e0 = 0.0
    else:
        while t[j + 1] <= start + 1e-9:
            j += 1
        if abs(t[j] - start) < 1e-9:
            e0 = E[j]
        else:
            f = (start - t[j])/(t[j + 1] - t[j]); e0 = E[j] + f*(E[j + 1] - E[j])
    m = (E[k] - e0)/w
    return (m if m > best else best), j


# ---- the reference scripts ----------------------------------------------------------------------------------------------------------------------

LOOP = ['A1', 'AC1a', 'AC1b', 'A2', 'AC2a', 'AC2b', 'A3', 'AC3a', 'AC3b']
LOOP_DOORS = ['CIRC.A1P', 'CIRC.AC1', 'CIRC.A2N', 'CIRC.A2P', 'CIRC.AC2', 'CIRC.A3N', 'CIRC.A3P', 'CIRC.AC3', 'CIRC.A1N']


def _door(a, b):
    i, j = LOOP.index(a), LOOP.index(b)
    return LOOP_DOORS[i] if (i + 1) % 9 == j else LOOP_DOORS[j]


def walk(path, t0, leave_open=False):
    """The trainee walking a compartment path in a reference script, 40 ship seconds a compartment, as the walk does it: open the door,
    step through 20 s later, close it behind 10 s after that (or leave it open)."""
    out = []
    for k, (a, b) in enumerate(zip(path, path[1:])):
        t = t0 + 40.0*k
        out += [[t, 'door', _door(a, b), True], [t + 20.0, 'trainee', b]]
        if not leave_open:
            out.append([t + 30.0, 'door', _door(a, b), False])
    return out


A1_TO_A3 = ['A1', 'AC3b', 'AC3a', 'A3']          # the short way round (A1N, AC3, A3P): 120 s
A3_TO_A1 = A1_TO_A3[::-1]
A3_TO_A2 = ['A3', 'AC2b', 'AC2a', 'A2']
A1_TO_A2 = ['A1', 'AC1a', 'AC1b', 'A2']
A1_A2_A3 = A1_TO_A2 + A3_TO_A2[::-1][1:]
LOOP_WALK = LOOP + ['A1']


def seal(t, *sfx):
    return [[t, 'damper', x, False] for x in sfx]


def cases():
    """The reference scripts: (name, what it shows, actions [[t_s, kind, *args]]). Ship seconds after the release. The alert comes at
    10 min; unless a case says otherwise the trainee, already in sector 1, contains the spill from 15 min (10 min of work), then acts.
    The trainee operates doors only where they stand and the ECLSS bay only in sector 3 (the walk checks the same)."""
    C0 = 900.0                                    # contain_start
    D = C0 + 610.0                                # the work completes at the boundary after 600 s of it
    at_bay = D + 140.0                            # the trainee, walking from hygiene A by A1N, is at the bay
    separate = ([[C0, 'contain_start'], [D, 'order', 'A', 'A2'], [D, 'order', 'C', 'A2']] + walk(A1_TO_A3, D) + seal(D + 300.0, 'A1P', 'A3N')
                + walk(A3_TO_A2, D + 310.0) + [[D + 1200.0, 'watch', 'RESTORE']])
    # the gate's separation (report section 30.5): the short way A1-A3 left open by the trainee (doors and ducts: the purge path), sector 2
    # sealed with the crew, the ducts reconnected later; the schedule is set at the bay after the seal, before the walk to sector 2
    sep_open = ([[C0, 'contain_start'], [D, 'order', 'A', 'A2'], [D, 'order', 'C', 'A2']] + walk(A1_TO_A3, D, leave_open=True)
                + seal(D + 300.0, 'A1P', 'A3N') + walk(A3_TO_A2, D + 310.0) + [[D + 1200.0, 'watch', 'RESTORE']])
    k_sep = next(k for k, a in enumerate(sep_open) if a[0] > D + 300.0)
    return [
        ('isolate', '1. Containment, then isolation: the trainee walks to the bay and calls the partner over, then shuts sector 1\'s two damper pairs',
         [[C0, 'contain_start']] + walk(A1_TO_A3, D) + [[at_bay, 'order', 'A', 'A3']] + seal(at_bay + 130.0, 'A1P', 'A1N') + [[D + 1200.0, 'watch', 'NONE']]),
        ('purge', '2. Containment, then a controlled purge: the trainee leaves every door from A1 to A3 by sector 2 open; pair A and B to sector 3',
         [[C0, 'contain_start'], [D, 'order', 'A', 'A3'], [D, 'order', 'B', 'A3']] + walk(A1_A2_A3, D, leave_open=True) + [[D + 1200.0, 'watch', 'NONE']]),
        ('separate', '3. Containment, then crew separation with no reconnection before the watch\'s end: A1 joined to the TCC by the ducts, '
         'sector 2 sealed off (A1P, A3N) with partner, B and C in it; restore plan',
         separate),
        ('no_containment', '4. No containment: the trainee goes straight to the bay, calls the partner over and shuts sector 1\'s dampers',
         walk(A1_TO_A3, 700.0) + [[840.0, 'order', 'A', 'A3']] + seal(970.0, 'A1P', 'A1N') + [[3600.0, 'watch', 'NONE']]),
        ('late_containment', '5. Delayed containment: started 1 h after the release, ventilation untouched',
         [[3600.0, 'contain_start'], [7200.0, 'watch', 'NONE']]),
        ('invalid_containment', '6. Containment asked at the bay (refused: the store is in hygiene A), then done there',
         walk(A1_TO_A3, 700.0) + [[900.0, 'contain_start']] + walk(A3_TO_A1, 1000.0) + [[1200.0, 'contain_start'], [3600.0, 'watch', 'NONE']]),
        ('invalid_order', '7. Invalid orders refused and changing nothing: a corridor, the pair\'s own sector, an unknown pair, and the partner across sector 1\'s seal',
         [[C0, 'contain_start'], [C0 + 10.0, 'order', 'B', 'AC1a'], [C0 + 10.0, 'order', 'B', 'A2'], [C0 + 10.0, 'order', 'D', 'A1']]
         + walk(A1_TO_A3, D) + seal(at_bay + 10.0, 'A1P', 'A1N') + [[at_bay + 20.0, 'order', 'A', 'A3'], [3600.0, 'watch', 'NONE']]),
        ('doorway', '8. The trainee opens A1P for pair B and tries to close it while they are in its doorway (refused), then after they are through',
         [[C0, 'contain_start'], [D, 'door', 'CIRC.A1P', True], [D + 10.0, 'order', 'B', 'A1'], [D + 120.0, 'door', 'CIRC.A1P', False],
          [D + 140.0, 'door', 'CIRC.A1P', False], [3600.0, 'watch', 'NONE']]),
        ('vent_off', '9. Ventilation off at the bay after containment; nobody else moves',
         [[C0, 'contain_start']] + walk(A1_TO_A3, D) + [[at_bay + 10.0, 'vent', False], [3600.0, 'watch', 'NONE']]),
        ('tcc_off', '10. NH3 removal (the TCC) off at the bay after containment; ventilation on',
         [[C0, 'contain_start']] + walk(A1_TO_A3, D) + [[at_bay + 10.0, 'tcc', False], [3600.0, 'watch', 'NONE']]),
        ('co2_ok_nh3_up', '11. CO2 held but NH3 spread: no containment, the trainee opens the whole loop, pairs A and B to sector 3',
         [[700.0, 'order', 'A', 'A3'], [700.0, 'order', 'B', 'A3']] + walk(LOOP_WALK, 700.0, leave_open=True)
         + walk(A1_TO_A3, 700.0 + 40.0*9 + 10.0, leave_open=True) + [[3600.0, 'watch', 'NONE']]),
        ('clean_but_slow', '12. Clean air protected, recovery delayed: containment, the partner to sector 2, sector 1 sealed empty, no recovery plan',
         [[C0, 'contain_start'], [D, 'order', 'A', 'A2']] + walk(A1_TO_A3, D) + seal(at_bay + 10.0, 'A1P', 'A1N') + [[D + 1200.0, 'watch', 'NONE']]),
        ('interrupted', '13. Containment interrupted (the trainee steps out of A1 and back), a refused restart outside, progress kept',
         [[C0, 'contain_start']] + walk(['A1', 'AC1a'], C0 + 280.0) + [[C0 + 310.0, 'contain_start']] + walk(['AC1a', 'A1'], C0 + 380.0)
         + [[C0 + 410.0, 'contain_start'], [C0 + 420.0, 'contain_start'], [3600.0, 'watch', 'NONE']]),
        ('watch_none', '14. Watch with no further intervention (containment, then nothing)',
         [[C0, 'contain_start'], [D + 10.0, 'watch', 'NONE']]),
        ('watch_restore', '15. Watch with the declared restore plan: as case 12, then the ring returned to normal and everyone home once their way is under the reuse criterion',
         [[C0, 'contain_start'], [D, 'order', 'A', 'A2']] + walk(A1_TO_A3, D) + seal(at_bay + 10.0, 'A1P', 'A1N') + [[D + 1200.0, 'watch', 'RESTORE']]),
        ('replay', '16. Replay: case 1 again from the exact initial state', 'isolate'),
        ('separate_reconnect', '17. Crew separation with a scheduled reconnection: the short way A1-A3 left open (the purge path), sector 2 sealed with partner, B and C (as case 3); at the bay the trainee schedules the ducts\' '
         'reconnection at 4 h (every damper pair open, the fans on; doors untouched), as the gate\'s reconnect at T2',
         sep_open[:k_sep] + [[D + 305.0, 'schedule', 4*H]] + sep_open[k_sep:]),
        ('separate_late', '18. Crew separation reconnected too late: the reconnection scheduled at 6 h, after the sealed sector passes the CO2 control limit',
         sep_open[:k_sep] + [[D + 305.0, 'schedule', 6*H]] + sep_open[k_sep:]),
        ('reconnect_refused', '19. Reconnections refused and changing nothing: a time already past, a time off the step grid, a time after the '
         'watch, then the 4 h reconnection; during the watch a cancellation is refused',
         sep_open[:k_sep] + [[D + 301.0, 'schedule', 1800.0], [D + 302.0, 'schedule', 4*H + 5.0], [D + 303.0, 'schedule', 30*H],
                             [D + 305.0, 'schedule', 4*H]] + sep_open[k_sep:] + [[D + 1300.0, 'schedule', None]]),
        ('reconnect_cancelled', '20. A scheduled reconnection cancelled before the watch: the sealed sector keeps its crew without CO2 removal',
         sep_open[:k_sep] + [[D + 305.0, 'schedule', 4*H], [D + 600.0, 'schedule', None]] + sep_open[k_sep:]),
        ('replay_reconnect', '21. Replay: case 17 again from the exact initial state', 'separate_reconnect'),
    ]


def play(sc, p, actions):
    """Run a reference script to the end of the projection."""
    r = Run(sc, p)
    todo = sorted(([float(a[0])] + list(a[1:]) for a in actions), key=lambda a: a[0])
    cps = [r.checkpoint()]
    k = 0
    while r.phase == 'LIVE':
        while k < len(todo) and todo[k][0] <= r.t + EPS:
            a = todo[k]; k += 1
            r.act(a[1], *a[2:])
        if r.phase != 'LIVE':
            break
        r.tick()
        if abs(r.t/H - round(r.t/H)) < 1e-9:
            cps.append(r.checkpoint())
        if r.t > 48*H:
            raise ValueError('a reference script must start the watch')
    w0 = r.t
    while r.t < r.watch['end_s'] - EPS:
        while k < len(todo) and todo[k][0] <= r.t + EPS:     # during the watch every action is refused and logged
            a = todo[k]; k += 1
            r.act(a[1], *a[2:])
        r.tick()
        if abs(r.t/H - round(r.t/H)) < 1e-9:
            cps.append(r.checkpoint())
    cps.append(r.checkpoint())
    r.finish_watch()
    cps.append(r.checkpoint())
    return r, cps, w0


def reference(sc, p):
    out = []
    scripts = {}
    for name, what, actions in cases():
        if isinstance(actions, str):
            actions = scripts[actions]
        scripts[name] = actions
        r, cps, w0 = play(sc, p, actions)
        d = r.debrief()
        out.append(dict(name=name, what=what, actions=actions, log=r.log, checkpoints=cps, watch_start_s=w0, debrief=_light(d)))
    return out


def _light(d):
    """The debrief without the watch's bulky copy (kept: verdict, family, config)."""
    w = d['watch']
    return dict(d, watch=dict(plan=w['plan'], t0=w['t0'], end_s=w['end_s'], verdict=w['verdict'], family=w['family'], config=w['config']))


def contract(root=ROOT):
    sc = load(root)
    p = params(root)
    ref = reference(sc, p)
    return dict(schema=SCHEMA, version=VERSION, notice='SIMULATION: a Deadship training scenario (PROTOTYPE, unscored). It sets no '
                'engineering value; the ring A air model (wf_ring_air.json, SYS-002 v2) owns them.', source=SCENARIO, scenario=sc,
                model=dict(file=ring_air.FILE, schema=ring_air.SCHEMA, version=ring_air.VERSION), smac=ring_air.NH3_SMAC['value_ppm'],
                reference=ref, verify_at_load='isolate', tolerance=dict(rel=1e-9, abs_kg=1e-15, abs_ppm_s=1e-6))


def write(root, out):
    Path(out).write_text(json.dumps(contract(root), separators=(',', ':'))+'\n')


def main(argv):
    c = contract()
    for case in c['reference']:
        d = case['debrief']; v = d['watch']['verdict']
        worst = max(case['debrief']['people'], key=lambda q: q['max_1h_ppm'])
        refused = [e for e in case['log'] if e[3]]
        print(f"{case['name']:20s} {d['watch']['family']:11s} {v['result']:13s} released {d['released_g']:.2f} g retained {d['retained_g']:.2f} "
              f"removed {d['removed_g']:.2f} airborne {d['airborne_g']:.2f} | worst 1h {worst['max_1h_ppm']:.1f} ppm ({worst['id']}) "
              f"max24 {max((q['max_24h_ppm'] or 0) for q in d['people']):.1f} 7d {max((q['mean_7d_ppm'] or 0) for q in d['people']):.2f} "
              f"co2>t {sum(q['co2_above_target_h'] for q in d['people']):.1f} crew-h | A1 clear {d['clear_h']['A1']} h | refused {len(refused)}")
    print(f"package {len(json.dumps(c, separators=(',', ':')))} bytes")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
