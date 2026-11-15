"""Deadship ship operations (Phases 2C and 3): the scenario layer over the ring services model (ring_services, SYS-003). Standard
library only.

One machine plays every multi-system Deadship scenario: DS-2C "Borrowed Air" (data/deadship/ds2c_borrowed_air.toml) and DS-3 "Dark Bus"
(data/deadship/ds3_dark_bus.toml). A scenario owns its premise (what failed, the fusion plant, who is where, the spares), its crew and
their times, the places its actions are done, its clocks, texts and stages; it calls only the model's public operations (start,
fail_part, move_part, set_on, set_isolated, set_occupants, set_tie, reset_breaker, set_converter, set_fusion, step, readout, ledgers).
It owns no physical law: every temperature, humidity, CO2, flow, draw and store is the model's.

A run is a deterministic machine on a fixed step. Actions apply at step boundaries in the order they arrive:

    trainee <node>               the trainee's compartment in ring A (the walk reports it; a reference script states it)
    inspect <equipment>          at the bay: read a machine's local indicators (logged: the diagnosis time)
    isolate <equipment> <bool>   at the bay: lock a ring A machine out (it stops) or return it to service
    remove <slot>                at the bay: start removing the part in a ring A slot (the machine isolated, the trainee's hands free)
    install <slot>               at the bay: start installing the part in hand (the machine isolated, the part's family fits the slot)
    take <part> / stow           at the bay: a part from the shelf into the hands, or the hands' part onto the shelf
    switch <ring> <load> <bool>  at the console: a load's remote power controller in either ring
    tie <bool> / reset <bus> / converter <bus> <bool>   at the console: the bus tie, a tripped bus breaker, a battery converter
    order <pair> fetch <part>    a pair crosses to ring B, isolates the machine there, removes the part, crosses back and leaves it on the
                                 ring A shelf
    order <pair> swap <part> <into>   a pair crosses to where `into` is, isolates, swaps the part in, and returns (Phase 3: the power bay)
    order <pair> move <ring>     a pair crosses to the other ring and stays
    watch                        the stability watch from the exact present state to `ship_h`, then the projection to `projection_h`

At each boundary: the due actions, then the trainee's work and the pairs' tasks advance, then the occupants are counted in each ring;
the model steps; each person's limit-hours add their ring's state over the step.

    python3 src/wayfarer/ship_ops.py [ds2c|ds3]      # check the scenario, run its reference cases, print their outcomes
"""
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ring_services as rs   # noqa: E402

SCENARIOS = {'ds2c': 'data/deadship/ds2c_borrowed_air.toml', 'ds3': 'data/deadship/ds3_dark_bus.toml'}
FILES = {'ds2c': 'wf_deadship_ds2c.json', 'ds3': 'wf_deadship_ds3.json'}
SCHEMA = 'WF_DEADSHIP_SCENARIO'
VERSION = 1
H = 3600.0
EPS = 1e-6
ENGINEERING_KEYS = {'C', 'V_m3', 'Q_air', 'UA', 'pump', 'T_s', 'hp_max', 'conv_W', 'gen_W', 'pack_Wh', 'ship_W', 'g_c', 'g_w', 'q_sens',
                    'k_m3_s', 'co2_max', 'co2_target', 'T_max', 'rh_max', 'rh_limit', 'battery_Wh'}
VALID_ABOVE_LIMIT_K = 8.0   # past T_max + this the model's cabin has left its range: no equipment over-temperature trips, no passive loss
BAY_SLOTS = ('CO2.FAN', 'CHX.FAN', 'P1.PUMP', 'P2.PUMP')


def _keys(d, path=''):
    out = []
    for k, v in d.items():
        out.append(k)
        if isinstance(v, dict):
            out += _keys(v, path + k + '.')
    return out


def load(name='ds2c', root=ROOT):
    path = SCENARIOS[name]
    sc = tomllib.loads((Path(root)/path).read_text())
    bad = sorted(ENGINEERING_KEYS & set(_keys(sc)))
    if bad:
        raise ValueError(f'{path}: a scenario must not set engineering values: {bad}')
    if sc['scenario'].get('scored'):
        raise ValueError(f'{path}: Deadship challenges are unscored')
    dt = sc['time']['dt_s']
    for k, v in (('transfer', sc['crew']['transfer_s']), ('fetch', sc['crew']['fetch_work_s']), ('remove', sc['work']['remove_s']),
                 ('install', sc['work']['install_s']), ('alert', sc['time']['alert_s']), ('watch step', sc['time']['watch_dt_s'])):
        if abs(v/dt - round(v/dt)) > 1e-9:
            raise ValueError(f'{path}: {k} {v} s is not a whole number of {dt} s steps')
    for k in ('watch_dt_s', 'projection_dt_s'):
        if abs(H/sc['time'][k] - round(H/sc['time'][k])) > 1e-9:
            raise ValueError(f'{path}: {k} must divide an hour')
    sc['_name'] = name
    return sc


def params(root=ROOT):
    import life_support
    import spec
    return rs.params(spec.load(Path(root))[0], life_support.load(Path(root)))


def equipment_of(slot):
    return slot.split('.')[0]


class Run:
    """One play of a scenario (or one reference script) on the model."""

    def __init__(self, sc, p):
        self.sc, self.p = sc, p
        pr = sc['premise']
        self.dt = float(sc['time']['dt_s']); self.wdt = float(sc['time']['watch_dt_s']); self.pdt = float(sc['time']['projection_dt_s'])
        self.people = []
        for pair, home in sc['crew']['pairs']:
            for k in (1, 2):
                self.people.append(dict(id=f'{pair}-{k}', pair=pair, ring='A', node=home, task=None, crossings=0,
                                        co2_s=0.0, hot_s=0.0, wet_s=0.0, cold_s=0.0, band_s=0.0, target_s=0.0))
        occ = dict(pr['occupants'])
        self.st = rs.start(p, occupants=occ, fusion=bool(pr['fusion']))
        self.extra_people = {r: int(occ[r]) - sum(1 for q in self.people if q['ring'] == r) for r in rs.RINGS}
        sb = pr.get('setback')
        if sb:
            r = sb['ring']; rr = self.st['ring'][r]
            rr['T'] = float(sb['T_K']); rr['m_w'] = rs.m_w_at(p, rr['T'], float(sb['rh'])); rr['m_c'] = rs.m_c_at(p, rr['T'], 0.0004)
            self.st['init'][r] = dict(T=rr['T'], m_w=rr['m_w'], m_c=rr['m_c'])
            for e in sb['off']:
                rr['on'][e] = False
        for part, t in pr['faults']:
            if float(t) <= 0.0:
                rs.fail_part(self.st, part)
        self.later_faults = sorted([[float(t), part] for part, t in pr['faults'] if float(t) > 0.0])
        for e in pr.get('switched_off', []):
            rs.set_on(self.st, e[0], e[1], False)
        for part, place in pr.get('spares', []):
            self.st['parts'][part] = dict(lru=place[0], at=place[1], ok=True)
        self.trainee = self.people[0]
        self.job = None                           # the trainee's work: dict(kind, slot, part, done_s, need_s)
        self.hands = None                         # the part in the trainee's hands
        self.phase = 'LIVE'                       # LIVE, WATCH, PROJECTION, DONE
        self.watch = {}
        self.log = []
        self.inspected = {}
        self.alerted = False
        self.first_cross = dict(co2=None, hot=None, wet=None, cold=None)
        self.after24 = dict(co2=None, hot=None, wet=None, cold=None)
        self.peak = dict(co2=0.0, T=0.0, rh=0.0)
        self.shed_J = 0.0                         # discretionary service not delivered (switched off), J
        self.samples = []
        self.start_parts = {k: v['at'] for k, v in self.st['parts'].items()}
        self._occupy()

    # ---- state ---------------------------------------------------------------------------------------------------------------------------
    @property
    def t(self):
        return self.st['t_s']

    def _occupy(self):
        occ = {r: self.extra_people[r] + sum(1 for q in self.people if q['ring'] == r) for r in rs.RINGS}
        if occ != self.st['occ']:
            rs.set_occupants(self.st, occ)

    def living(self, r):
        """People living in a ring now: there and not on an errand or in a crossing."""
        return self.extra_people[r] + sum(1 for q in self.people if q['ring'] == r and q['task'] is None)

    def at(self, place):
        pl = self.sc['places'].get(place)
        return pl is not None and self.trainee['ring'] == 'A' and self.trainee['node'] == pl['compartment']

    def pair_members(self, pair, what=''):
        """The members an order goes to. The trainee (A-1) does the work at ring A's machines, so an order to pair A sends only A-2,
        except a move: then the trainee goes with them (the whole crew can leave ring A)."""
        ms = [q for q in self.people if q['pair'] == pair]
        return ms if (pair != 'A' or what == 'move') else ms[1:]

    def idle(self, pair):
        return all(q['task'] is None for q in self.pair_members(pair))

    # ---- actions -------------------------------------------------------------------------------------------------------------------------
    def act(self, kind, *a):
        why = self._act(kind, *a)
        self.log.append([self.t, kind, list(a), why])
        return why

    def _act(self, kind, *a):
        st = self.st
        if self.phase != 'LIVE' and kind != 'trainee':
            return 'the watch is running: nothing can be changed now'
        if kind == 'trainee':
            self.trainee['node'] = a[0]; return ''
        if kind == 'inspect':
            if not self.at('bay'):
                return 'the machines are in the ECLSS bay in sector 3: you have to be there'
            self.inspected.setdefault(a[0], self.t); return ''
        if kind == 'isolate':
            if not self.at('bay'):
                return 'isolation is done at the machine, in the ECLSS bay in sector 3'
            if a[0] not in self.sc['places']['bay']['holds']:
                return f'{a[0]} is not in the bay'
            if self.job is not None and equipment_of(self.job['slot']) == a[0] and not a[1]:
                return 'you are working on it: finish or put the part down first'
            rs.set_isolated(st, 'A', a[0], bool(a[1])); return ''
        if kind in ('remove', 'install'):
            if not self.at('bay'):
                return 'parts are changed at the machine, in the ECLSS bay in sector 3'
            slot = a[0]; full = f'A.{slot}'; e = equipment_of(slot)
            if slot not in BAY_SLOTS:
                return f'{slot} is not a slot in the bay'
            if not st['ring']['A']['isolated'][e]:
                return f'the {e} is not isolated: isolate it before you work on it'
            if self.job is not None:
                return 'you are already working on a part'
            here = next((k for k, q in st['parts'].items() if q['at'] == full), None)
            if kind == 'remove':
                if self.hands is not None:
                    return 'your hands are full: stow the part first'
                if here is None:
                    return f'{slot} is empty'
                self.job = dict(kind='remove', slot=full, part=here, done_s=0.0, need_s=float(self.sc['work']['remove_s']))
                return ''
            if self.hands is None:
                return 'you have no part in hand'
            if here is not None:
                return f'{slot} already holds a part: remove it first'
            fam = rs.SLOTS[slot]
            if st['parts'][self.hands]['lru'] != fam:
                return f"that part does not fit: {rs.LRU[st['parts'][self.hands]['lru']]['title']} against {rs.LRU[fam]['title']}"
            self.job = dict(kind='install', slot=full, part=self.hands, done_s=0.0, need_s=float(self.sc['work']['install_s']))
            return ''
        if kind == 'take':
            if not self.at('bay'):
                return 'the parts shelf is in the ECLSS bay'
            if self.hands is not None:
                return 'your hands are full'
            if st['parts'].get(a[0], {}).get('at') != 'A.SHELF':
                return f'{a[0]} is not on the shelf'
            rs.move_part(st, a[0], 'CARRY.T'); self.hands = a[0]; return ''
        if kind == 'stow':
            if not self.at('bay'):
                return 'the parts shelf is in the ECLSS bay'
            if self.hands is None:
                return 'your hands are empty'
            if self.job is not None and self.job['part'] == self.hands:
                return 'you are installing it'
            rs.move_part(st, self.hands, 'A.SHELF'); self.hands = None; return ''
        if kind in ('switch', 'tie', 'reset', 'converter'):
            if not self.at('console'):
                return 'switching is done at the ops console in sector 2'
            if kind == 'switch':
                ring, load, on = a
                if load not in st['ring'][ring]['on']:
                    return f'no load {load}'
                rs.set_on(st, ring, load, bool(on)); return ''
            if kind == 'tie':
                rs.set_tie(st, bool(a[0])); return ''
            if kind == 'reset':
                rs.reset_breaker(st, a[0]); return ''
            rs.set_converter(st, a[0], bool(a[1])); return ''
        if kind == 'order':
            pair, what = a[0], a[1]
            if pair not in [x[0] for x in self.sc['crew']['pairs']]:
                return f'no pair {pair}'
            if not self.idle(pair):
                return f'pair {pair} is busy'
            ms = self.pair_members(pair, what)
            if what == 'move' and pair == 'A' and (self.job is not None or self.hands is not None):
                return 'finish the work in hand and stow the part before you leave'
            T = float(self.sc['crew']['transfer_s']); W = float(self.sc['crew']['fetch_work_s'])
            ring = ms[0]['ring']
            if what == 'fetch':
                part = a[2]
                q = st['parts'].get(part)
                if q is None or not q['at'].startswith('B.'):
                    return f'{part} is not installed in ring B'
                if ring != 'A':
                    return f'pair {pair} is not in ring A'
                plan = [('cross', T, 'B'), ('isolate', W, part), ('cross', T, 'A'), ('deliver', 0.0, part)]
            elif what == 'move':
                to = a[2]
                if to == ring:
                    return f'pair {pair} is already in ring {to}'
                plan = [('cross', T, to)]
            elif what == 'swap':
                part, into = a[2], a[3]
                q = st['parts'].get(part)
                if q is None or q['at'] != self.sc['crew'].get('swap_store', ''):
                    return f'{part} is not where the crew keep spares'
                if st['parts'][part]['lru'] != rs.SLOTS_ALL().get(into):
                    return f'{part} does not fit {into}'
                plan = [('go', float(self.sc['crew']['swap_go_s']), ''), ('swap', float(self.sc['crew']['swap_work_s']), [part, into]),
                        ('return', float(self.sc['crew']['swap_go_s']), '')]
            else:
                return f'no order {what}'
            for i, m in enumerate(ms):
                m['task'] = dict(plan=[list(x) for x in plan], k=0, left=plan[0][1], lead=(i == 0))
                self._begin(m)
            return ''
        if kind == 'watch':
            if self.job is not None:
                return 'finish the work in hand first'
            self._start_watch(); return ''
        return f'unknown action {kind}'

    # ---- the crew's tasks ------------------------------------------------------------------------------------------------------------
    def _begin(self, q):
        """A task phase starts: a crossing takes the person out of the rings' air; an isolation at ring B locks that machine out."""
        k, _, arg = q['task']['plan'][q['task']['k']]
        if k == 'cross':
            q['ring'] = 'X'; q['crossings'] += 1
        elif k == 'isolate' and q['task']['lead']:
            rs.set_isolated(self.st, 'B', arg.split('.')[1], True)
        elif k == 'go':
            q['ring'] = 'X'

    def _finish(self, q):
        k, _, arg = q['task']['plan'][q['task']['k']]
        lead = q['task']['lead']
        if k == 'cross':
            q['ring'] = arg; q['node'] = 'A3' if arg == 'A' else 'B2'
        elif k == 'isolate' and lead:
            rs.move_part(self.st, arg, f"CARRY.{q['pair']}")
        elif k == 'deliver' and lead:
            rs.move_part(self.st, arg, self.sc['crew']['deliver_to'])
        elif k == 'swap' and lead:
            part, into = arg
            old = next((kk for kk, v in self.st['parts'].items() if v['at'] == into), None)
            if old is not None:
                rs.move_part(self.st, old, self.sc['crew']['swap_store'])
            rs.move_part(self.st, part, into)
        elif k == 'return':
            q['ring'] = 'A'; q['node'] = 'A2'

    def _tasks(self, dt):
        for q in self.people:
            t = q['task']
            while t is not None:
                if t['left'] > dt - EPS and t['left'] > EPS:
                    t['left'] -= dt
                    if t['left'] > EPS:
                        break
                self._finish(q)
                t['k'] += 1
                if t['k'] >= len(t['plan']):
                    q['task'] = None
                    self.log.append([self.t, 'arrived', [q['id'], q['ring']], ''])
                    break
                t['left'] = t['plan'][t['k']][1]
                self._begin(q)
                if t['left'] > EPS:
                    break
                dt = 0.0
            self._occupy()

    def _work(self, dt):
        j = self.job
        if j is None or not self.at('bay'):
            return
        j['done_s'] += dt
        if j['done_s'] < j['need_s'] - EPS:
            return
        if j['kind'] == 'remove':
            rs.move_part(self.st, j['part'], 'CARRY.T'); self.hands = j['part']
        else:
            rs.move_part(self.st, j['part'], j['slot']); self.hands = None
        self.log.append([self.t, j['kind'] + 'd', [j['slot'], j['part']], ''])
        self.job = None

    # ---- the step ------------------------------------------------------------------------------------------------------------------------
    def tick(self, dt=None):
        dt = self.dt if dt is None else dt
        while self.later_faults and self.later_faults[0][0] <= self.t + EPS:
            rs.fail_part(self.st, self.later_faults.pop(0)[1])
        self._work(dt)
        self._tasks(dt)
        self._occupy()
        before = dict(self.st['ring']['A']['on']), dict(self.st['ring']['B']['on'])
        rs.step(self.st, self.p, dt)
        if not self.alerted and self.t >= float(self.sc['time']['alert_s']) - EPS:
            self.alerted = True
        for r, on in zip(rs.RINGS, before):
            if not self.living(r):
                continue                          # a discretionary load off where nobody lives denies no one its service
            for e in self.p['equipment']:
                if e['shed'] and not on[e['id']]:
                    self.shed_J += e['W']*dt
        self._account(dt)

    def _account(self, dt):
        p = self.p
        for r in rs.RINGS:
            rr = self.st['ring'][r]
            x = rs.x_co2(p, rr['T'], rr['m_c']); h = rs.rh(p, rr['T'], rr['m_w']); T = rr['T']
            # the habitability limits are for the people living in a ring; a pair on an errand there (dressed and working for minutes) is
            # not counted, nor is anyone in a crossing
            people = [q for q in self.people if q['ring'] == r and q['task'] is None]
            if not people and not self.extra_people[r]:
                continue
            flags = dict(co2=x > p['co2_max'], hot=T > p['T_max'], wet=h > p['rh_limit'], cold=T < p['T_min'])
            for q in people:
                q['co2_s'] += dt if flags['co2'] else 0.0
                q['hot_s'] += dt if flags['hot'] else 0.0
                q['wet_s'] += dt if flags['wet'] else 0.0
                q['cold_s'] += dt if flags['cold'] else 0.0
                q['band_s'] += dt if h > p['rh_max'] else 0.0
                q['target_s'] += dt if x > p['co2_target'] else 0.0
            if people and self.phase in ('LIVE', 'WATCH', 'PROJECTION'):
                for k, v in flags.items():
                    if v:
                        if self.phase != 'PROJECTION' and self.first_cross[k] is None:
                            self.first_cross[k] = self.t
                        if self.phase == 'PROJECTION' and self.after24[k] is None:
                            self.after24[k] = self.t
                if self.phase != 'PROJECTION':
                    self.peak['co2'] = max(self.peak['co2'], x); self.peak['T'] = max(self.peak['T'], T)
                    self.peak['rh'] = max(self.peak['rh'], h)
        self.samples.append((self.t, {r: (self.st['ring'][r]['T'], rs.rh(p, self.st['ring'][r]['T'], self.st['ring'][r]['m_w']),
                                          rs.x_co2(p, self.st['ring'][r]['T'], self.st['ring'][r]['m_c'])) for r in rs.RINGS},
                             self.st['E']))

    # ---- the watch -------------------------------------------------------------------------------------------------------------------
    def _start_watch(self):
        self.phase = 'WATCH'
        self.watch = dict(t0=self.t, config=self.config())
        self.log.append([self.t, 'watch_start', [], ''])

    def watch_end_s(self):
        return max(float(self.sc['watch']['ship_h'])*H, self.watch['t0'] + float(self.sc['watch']['min_h'])*H)

    def run_watch(self):
        end = self.watch_end_s()
        while self.t < end - EPS:
            self.tick(min(self.wdt, end - self.t) if abs((end - self.t) % self.wdt) > EPS and end - self.t < self.wdt else self.wdt)
        self.finish_watch()

    def finish_watch(self):
        self.watch['end_config'] = self.config()
        self.watch['verdict24'] = self.verdict(limit_only=True)
        self.phase = 'PROJECTION'
        end = float(self.sc['watch']['projection_h'])*H
        while self.t < end - EPS:
            self.tick(self.pdt)
        self.phase = 'DONE'
        self.watch['verdict'] = self.verdict()

    # ---- results -------------------------------------------------------------------------------------------------------------------------
    def config(self):
        st = self.st
        return dict(occ=dict(st['occ']), parts={k: v['at'] for k, v in st['parts'].items()},
                    isolated={r: sorted(k for k, v in st['ring'][r]['isolated'].items() if v) for r in rs.RINGS},
                    off={r: sorted(k for k, v in st['ring'][r]['on'].items() if not v) for r in rs.RINGS},
                    tie=st['tie'], breaker=dict(st['breaker']), fusion=st['fusion'])

    def hostable(self, r):
        """A ring can host the crew when its CO2 unit, its heat exchanger fan, a pump and its heat pump could all run (parts whole and
        installed, not isolated, switched on)."""
        st = self.st; p = self.p
        ok = lambda e: rs.equipment_ready(p, st, r, rs.eq(p, e))
        return ok('CO2') and ok('CHX') and (ok('P1') or ok('P2')) and ok('HP')

    def family(self):
        parts = self.st['parts']
        borrowed = [k for k, v in parts.items() if k.startswith('B.') and v['at'].startswith('A.')]
        in_co2 = next((k for k, v in parts.items() if v['at'] == 'A.CO2.FAN'), None)
        crew_b = self.st['occ']['B']
        if crew_b >= max(1, self.st['occ']['A'] + 1):
            return 'RELOCATE'
        if in_co2 == 'A.CHX.FAN':
            return 'CANNIBALIZE'
        if 'B.CO2.FAN' in borrowed and any(k.endswith('PUMP') for k in borrowed):
            return 'BORROW_FAN_PUMP'
        if 'B.CO2.FAN' in borrowed:
            return 'BORROW_FAN'
        return 'NO_REPAIR'

    def verdict(self, limit_only=False):
        fc = self.first_cross; late = self.after24
        if fc['co2'] is not None:
            res = 'CO2_LIMIT'
        elif fc['hot'] is not None:
            res = 'HEAT_LIMIT'
        elif fc['wet'] is not None:
            res = 'HUMIDITY_LIMIT'
        elif fc['cold'] is not None:
            res = 'COLD_LIMIT'
        elif not limit_only and any(v is not None for v in late.values()):
            res = 'TEMPORARY'
        else:
            res = 'STABLE'
        crew = self.people
        ch = lambda k: sum(q[k] for q in crew)/H
        degraded = res == 'STABLE' and (ch('band_s') > 0.0 or ch('target_s') > 0.0)
        return dict(result=res, degraded=degraded,
                    first_cross_h={k: (None if v is None else v/H) for k, v in fc.items()},
                    after_watch_h={k: (None if v is None else v/H) for k, v in late.items()},
                    crew_h=dict(co2_limit=ch('co2_s'), heat_limit=ch('hot_s'), humidity_limit=ch('wet_s'), cold_limit=ch('cold_s'),
                                humidity_band=ch('band_s'), co2_target=ch('target_s')),
                    peak=dict(co2_pct=100.0*self.peak['co2'], T_C=self.peak['T'] - 273.15, rh=self.peak['rh'],
                              beyond_validity=self.peak['T'] > self.p['T_max'] + VALID_ABOVE_LIMIT_K))

    def metrics(self):
        st = self.st
        moved = [k for k, v in st['parts'].items() if v['at'] != self.start_parts.get(k)]
        from_b = [k for k in moved if k.startswith('B.')]
        unresolved = sorted(f'{r}.{e["id"]}' for r in rs.RINGS for e in self.p['equipment'] if e['slots']
                            and not rs.equipment_ready(self.p, st, r, e))
        first_inspect = min(self.inspected.values()) if self.inspected else None
        acts = [e for e in self.log if not e[3] and e[1] not in ('trainee', 'arrived', 'watch_start', 'inspect')]
        return dict(parts_moved=sorted(moved), parts_from_ring_b=sorted(from_b), hostable={r: self.hostable(r) for r in rs.RINGS},
                    unresolved=unresolved, crossings=sum(q['crossings'] for q in self.people), shed_kWh=self.shed_J/3.6e6,
                    battery_kWh=st['E']/3.6e6, battery_used_kWh=(st['E0'] - st['E'])/3.6e6,
                    packs_kWh={r: st['pack'][r]/3.6e6 for r in rs.RINGS}, first_inspect_h=None if first_inspect is None else first_inspect/H,
                    last_action_h=(acts[-1][0]/H if acts else None), watch_declared_h=(self.watch['t0']/H if self.watch else None),
                    refusals=sum(1 for e in self.log if e[3]))

    def debrief(self):
        return dict(watch=dict(family=self.family(), verdict=self.watch.get('verdict') or self.verdict(),
                               verdict24=self.watch.get('verdict24')), metrics=self.metrics(), decisions=self.decisions(),
                    rings={r: dict(T_C=self.st['ring'][r]['T'] - 273.15, rh=rs.rh(self.p, self.st['ring'][r]['T'], self.st['ring'][r]['m_w']),
                                   co2_pct=100.0*rs.x_co2(self.p, self.st['ring'][r]['T'], self.st['ring'][r]['m_c']),
                                   occupants=self.st['occ'][r]) for r in rs.RINGS},
                    ledgers=rs.ledgers(self.st, self.p))

    def decisions(self):
        keep = ('isolate', 'removed', 'installed', 'take', 'stow', 'switch', 'tie', 'reset', 'converter', 'order', 'watch')
        return [[e[0]/H, e[1], e[2]] for e in self.log if e[1] in keep and not e[3]]

    def checkpoint(self):
        st = self.st
        return dict(t_s=self.t, phase=self.phase, T={r: st['ring'][r]['T'] for r in rs.RINGS}, m_w={r: st['ring'][r]['m_w'] for r in rs.RINGS},
                    m_c={r: st['ring'][r]['m_c'] for r in rs.RINGS}, E=st['E'], pack=dict(st['pack']), occ=dict(st['occ']),
                    parts={k: v['at'] for k, v in st['parts'].items()})


# ---------- reference scripts ---------------------------------------------------------------------------------------------------------

def go_bay(t):
    return [[t, 'trainee', 'A3']]


def cases_ds2c():
    """The DS-2C reference scripts (name, description, actions): every strategy family, failures, refusals and a replay."""
    T0 = 120.0
    base = [[0.0, 'trainee', 'A1'], [T0, 'trainee', 'A2'], [T0 + 60.0, 'trainee', 'A3'], [T0 + 70.0, 'inspect', 'CO2'],
            [T0 + 80.0, 'inspect', 'P1'], [T0 + 90.0, 'inspect', 'CHX']]
    D = T0 + 100.0
    fetch_fan = [[D, 'order', 'B', 'fetch', 'B.CO2.FAN']]
    fit_b_fan = lambda t: [[t, 'isolate', 'CO2', True], [t, 'remove', 'CO2.FAN'], [t + 310.0, 'stow'], [t + 320.0, 'take', 'B.CO2.FAN'],
                           [t + 320.0, 'install', 'CO2.FAN'], [t + 630.0, 'isolate', 'CO2', False]]
    arrive = D + 900.0 + 600.0 + 900.0 + 10.0
    shed = lambda t: [[t, 'trainee', 'A2'], [t + 10.0, 'switch', 'A', 'GARDEN', False], [t + 10.0, 'switch', 'A', 'LAB', False],
                      [t + 20.0, 'trainee', 'A3']]
    S2 = base + fetch_fan + fit_b_fan(arrive)
    S2S4 = base + shed(D) + fetch_fan + fit_b_fan(arrive)
    pump = [[D, 'order', 'C', 'fetch', 'B.P1.PUMP']]
    fit_b_pump = lambda t: [[t, 'isolate', 'P1', True], [t, 'remove', 'P1.PUMP'], [t + 310.0, 'stow'], [t + 320.0, 'take', 'B.P1.PUMP'],
                            [t + 320.0, 'install', 'P1.PUMP'], [t + 630.0, 'isolate', 'P1', False]]
    S2P = base + fetch_fan + pump + fit_b_fan(arrive) + fit_b_pump(arrive + 640.0)
    move_all = lambda t: [[t, 'order', 'B', 'move', 'B'], [t, 'order', 'C', 'move', 'B'], [t + 10.0, 'order', 'A', 'move', 'B']]
    bring_up = [[D, 'trainee', 'A2'], [D + 10.0, 'switch', 'B', 'CO2', True], [D + 10.0, 'switch', 'B', 'GARDEN', True],
                [D + 10.0, 'switch', 'B', 'LIGHT', True], [D + 10.0, 'switch', 'B', 'HP', False]]
    WARM = 1.5*H
    S3 = base + bring_up + [[D + WARM, 'switch', 'B', 'HP', True], [D + WARM, 'switch', 'B', 'GALLEY', True],
                            [D + WARM, 'switch', 'B', 'LAB', True]] + move_all(D + WARM)
    S3_cold = base + [[D, 'trainee', 'A2'], [D + 10.0, 'switch', 'B', 'CO2', True]] + move_all(D + 20.0)
    S1 = base + [[D, 'isolate', 'CO2', True], [D, 'remove', 'CO2.FAN'], [D + 310.0, 'stow'], [D + 320.0, 'isolate', 'CHX', True],
                 [D + 320.0, 'remove', 'CHX.FAN'], [D + 630.0, 'install', 'CO2.FAN'], [D + 940.0, 'isolate', 'CO2', False]]
    S4 = base + shed(D)
    W = lambda t: [[t, 'watch']]
    late_fetch = base + shed(D) + [[D + 5*H, 'order', 'B', 'fetch', 'B.CO2.FAN']] + fit_b_fan(D + 5*H + 2410.0)
    refused = base + [[D, 'remove', 'CO2.FAN'], [D, 'switch', 'A', 'GARDEN', False], [D, 'install', 'P1.PUMP'],
                      [D + 10.0, 'isolate', 'P1', True], [D + 10.0, 'remove', 'P1.PUMP'], [D + 320.0, 'install', 'CO2.FAN'],
                      [D + 320.0, 'stow'], [D + 330.0, 'order', 'B', 'fetch', 'A.CO2.FAN']] + shed(D + 340.0) + fetch_fan[:0] + \
              [[D + 400.0, 'order', 'B', 'fetch', 'B.CO2.FAN'], [D + 410.0, 'order', 'B', 'move', 'B']] + fit_b_fan(D + 400.0 + 2410.0)
    return [
        ('nothing', 'No action: the watch is declared after the inspection.', base + W(D + 10.0)),
        ('borrow_fan', 'Fetch ring B\'s CO2 fan and fit it; no shedding (one pump carries the full heat load).', S2 + W(arrive + 700.0)),
        ('borrow_fan_shed', 'Shed the Garden lights and the lab, fetch ring B\'s CO2 fan and fit it.', S2S4 + W(arrive + 700.0)),
        ('borrow_fan_pump', 'Fetch ring B\'s CO2 fan and pump 1 and fit both.', S2P + W(arrive + 1300.0)),
        ('relocate', 'Bring ring B out of setback (its CO2 unit, lights and Garden on, its heat pump off for 90 minutes to warm it), then '
                     'move all three pairs there (the trainee too, as pair A), leaving ring A empty.', S3 + W(D + WARM + 1000.0)),
        ('relocate_cold', 'Start ring B\'s CO2 unit and move everyone at once into the cold ring.', S3_cold + W(D + 1000.0)),
        ('cannibalize', 'Move ring A\'s heat exchanger fan into its CO2 unit.', S1 + W(D + 950.0)),
        ('shed_only', 'Shed the Garden lights and the lab only.', S4 + W(D + 40.0)),
        ('late_fetch', 'Shed, then fetch ring B\'s CO2 fan five hours later.', late_fetch + W(D + 5*H + 2410.0 + 700.0)),
        ('refused', 'Refusals: work on a running unit, switching away from the console, installing with empty hands, fetching a ring A part, '
                    'a busy pair; then the shed-and-borrow repair.', refused + W(D + 400.0 + 2410.0 + 700.0)),
        ('replay_borrow_fan_shed', 'Replay of borrow_fan_shed from the same start.', 'borrow_fan_shed'),
    ]


def resolve(cases):
    named = {n: a for n, _, a in cases}
    return [(n, d, named[a] if isinstance(a, str) else a) for n, d, a in cases]


def play(sc, p, actions):
    """Run a script to the end of the projection. A relocated trainee (pair A moved) is the trainee too: the walk ends the live part."""
    r = Run(sc, p)
    acts = sorted(([float(a[0])] + list(a[1:]) for a in actions), key=lambda a: a[0])
    i = 0
    cps = []
    while r.phase == 'LIVE':
        while i < len(acts) and acts[i][0] <= r.t + EPS:
            r.act(acts[i][1], *acts[i][2:]); i += 1
            if r.phase != 'LIVE':
                break
        if r.phase != 'LIVE':
            break
        if abs(r.t % 1800.0) < EPS:
            cps.append(r.checkpoint())
        r.tick()
        if r.t > 30*H:
            raise RuntimeError('script never declared the watch')
    # actions after the watch began are refused and logged, as the runtime does
    for a in acts[i:]:
        r.act(a[1], *a[2:])
    end = r.watch_end_s()
    while r.t < end - EPS:
        if abs(r.t % 1800.0) < EPS:
            cps.append(r.checkpoint())
        r.tick(r.wdt if end - r.t >= r.wdt - EPS else end - r.t)
    r.finish_watch()
    cps.append(r.checkpoint())
    return r, cps


def cases(name):
    return resolve(cases_ds2c()) if name == 'ds2c' else resolve(cases_ds3())


def cases_ds3():
    return []


def contract(name='ds2c', root=ROOT):
    sc = load(name, root); p = params(root)
    refs = []
    for n, d, a in cases(name):
        r, cps = play(sc, p, a)
        refs.append(dict(name=n, description=d, actions=a, checkpoints=cps, debrief=r.debrief()))
    return dict(schema=SCHEMA, version=VERSION, scenario={k: v for k, v in sc.items() if not k.startswith('_')}, references=refs,
                notice='SIMULATION: a station-run Deadship training on the ring services model (SYS-003). Unscored; PROTOTYPE values.')


def write(root, out, name='ds2c'):
    Path(out).write_text(json.dumps(contract(name, root), separators=(',', ':')) + '\n')


def main(argv):
    name = argv[0] if argv else 'ds2c'
    sc = load(name); p = params()
    for n, d, a in cases(name):
        r, _ = play(sc, p, a)
        db = r.debrief(); v = db['watch']['verdict']; m = db['metrics']
        led = max(abs(x) for x in db['ledgers'].values())
        print(f"{n:24s} {db['watch']['family']:16s} {v['result']:15s}{' degraded' if v['degraded'] else '':9s} "
              f"peak CO2 {v['peak']['co2_pct']:.3f} % T {v['peak']['T_C']:.1f} C RH {v['peak']['rh']:.2f} | "
              f"limit crew-h co2 {v['crew_h']['co2_limit']:.1f} heat {v['crew_h']['heat_limit']:.1f} | from B {m['parts_from_ring_b']} "
              f"hostable {m['hostable']} shed {m['shed_kWh']:.0f} kWh crossings {m['crossings']} refusals {m['refusals']} | ledger {led:.1e}")


if __name__ == '__main__':
    main(sys.argv[1:])
