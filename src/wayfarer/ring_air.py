"""SYS-002 ring A atmospheric connectivity (Deadship Phase 2A): ring A's cabin CO2 as a graph of pressure compartments joined by doors
and ventilation, instead of one well-mixed volume (SYS-001, cabin_air). Standard library only.

A reusable engineering state: it knows nothing of games, scenarios, input or scores. Consumers set the state of its connections
(`set_edge`, `set_vent`), its removal (`set_removal`) and its occupants (`set_occupants`), and read it (`readout`); Godot repeats `step`
(godot/scripts/systems/ring_air.gd) and must reproduce `checkpoints()` within `TOLERANCE` before the state is shown.

Topology. The layout defines the volumes, doors and hatches the connections, ventilation the mechanical exchange:
- nodes: ring A's nine pressure compartments (ring_circulation.compartments): sectors A1, A2, A3 at their net free volume (pressure_volumes)
  and the six corridor halves AC1a ... AC3b at their gross cavity. They sum to SYS-001's 466.36 m3 exactly (no part counted twice).
- edges: the nine CIRC pressure doors (ring_circulation.doors, a single loop round the ring) and, through each of the nine bulkheads, one
  intermodule ventilation (IMV) pair (supply and return duct with a damper; PROTOTYPE, no ventilation is in canon).
- boundaries: each sector's crew-tube hatch (crew_transfer) is held CLOSED and the tubes and vestibule lie outside the model. The walk does
  not animate those hatches; the tubes are a second path between sectors and are named here rather than silently ignored.

Physics. CO2 is a trace gas; every exchange is balanced (equal volume each way: a doorway's two-way buoyant exchange, a duct pair's supply and
return), so each compartment's total gas stays n_i = P V_i / (R T) and no pressure state is needed. CO2 mass m_i obeys
    dm_i/dt = G_i - [i = r] k m_i / V_i + sum_j C_ij (m_j / V_j - m_i / V_i)
G_i the occupants' generation in i, k the unit's scrubbed flow drawn from compartment r, C_ij the exchange flow (m3/s) of every open edge
between i and j. Connectivity is not mixing: an open edge has a finite flow, so concentrations approach each other over V / C, never at once.
The system is linear with constant coefficients between changes, so a step is exact: y(t+dt) = exp(A dt) y(t) on y = [m_1..m_9, generated,
removed, 1], with generated and removed integrated inside the same exponential (the ledger initial + generated - removed = final is then a
real check of the step, not a definition). The exponential is scaling and squaring of a fixed-order Taylor series, written so that Godot can
repeat it operation for operation.

SYS-002 v2 (2026-11-14): a second, trace species, ammonia (NH3), rides the same compartments and the same exchange flows (a trace gas
in a balanced exchange is carried by the air, whatever the gas). Its own source and sink are separate from CO2's: a finite source that
empties into one compartment at a first-order rate (inventory S, dS/dt = -S / tau while LEAKING, 0 once ISOLATED or empty) and a
trace-contaminant control element (TCC) that draws from its compartment at its own flow and single-pass efficiency. NH3 mass c_i obeys
    dc_i/dt = [i = s] S / tau - [i = t] eta Q_t c_i / V_i + sum_j C_ij (c_j / V_j - c_i / V_i)
and is stepped exactly like CO2 on z = [c_1..c_N, S, released, removed, I_1..I_N], where I_i = integral of c_i dt (kg s) gives exact
exposures (a crew member's mean concentration over any stay). CO2's equations, its matrix and its checkpoints are untouched: the two species
share transport, not removal (the CO2 unit removes no NH3; the TCC removes no CO2). Exposure references (`NH3_SMAC`) are NASA JSC 20584
Rev D; every source and sink value is PROTOTYPE (`TRACE`). The release itself is scenario data (`set_source`), never a model default.

Statuses: pressure 80 kPa BASELINE; CO2 rate STUDY; compartment volumes PROTOTYPE (built rooms); the doorway exchange, the IMV flow, the
occupants' places, the removal compartment and the closed tube hatches PROTOTYPE (`PROTOTYPE`). Nothing here is written back to canon.

    python3 src/wayfarer/ring_air.py      # the topology, the exchange rates and the steady states of cases A-G
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

FILE = 'wf_ring_air.json'
SCHEMA = 'WF_RING_AIR'
VERSION = 2               # 2: the trace species NH3 (SYS-002 v2); the CO2 part and its proof are unchanged from 1
G0 = 9.80665              # m/s2 per g
TAYLOR_ORDER = 18         # terms of the series after scaling to a norm of at most 0.5: truncation below 1e-22
SCALE_NORM = 0.5
TOLERANCE = {'rel': 1e-9, 'abs_kg': 1e-12}

PROTOTYPE = {
    'door_cd': dict(value=0.6, unit='-', status='PROTOTYPE', note='Discharge coefficient of an open doorway (sharp-edged opening).'),
    'door_delta_T_K': dict(value=0.5, unit='K', status='PROTOTYPE',
                           note='Air temperature difference that drives the two-way buoyant exchange through an open doorway in spin gravity. '
                                'The exchange Q = (Cd / 3) W H sqrt(g H dT / T) (the standard doorway exchange-flow form) is the only door '
                                'transport; cabin fans and people walking through add to it, so this is a conservative floor.'),
    'imv_flow_m3_s': dict(value=0.066, unit='m3/s', status='PROTOTYPE',
                          note='Intermodule ventilation through each bulkhead: a balanced supply and return duct pair, about 240 m3/h, the order '
                               'of a spacecraft intermodule-ventilation fan (about 140 cfm). It runs only while the ring\'s ventilation is ON and '
                               'the bulkhead\'s damper is OPEN. No ventilation is in canon.'),
    'occupants': dict(value={'A1': 2, 'A2': 2, 'A3': 2}, unit='persons', status='PROTOTYPE',
                      note='SYS-001\'s six occupants, two per sector; the corridors hold no one.'),
    'removal_node': dict(value='A3', status='PROTOTYPE', note='The CO2-removal unit sits in the sector 3 ECLSS bay (cabin_air.BINDING) and '
                                                              'draws its process air from sector 3 only.'),
    'tube_hatches': dict(value='CLOSED', status='PROTOTYPE',
                         note='The crew-tube hatches are held closed; the tubes (about 49 m3 each) and the vestibule are outside the model.'),
    'leakage': dict(value=0.0, unit='m3/s', status='PROTOTYPE', note='A closed door or damper seals: no leakage path is modelled.'),
}


# SYS-002 v2: the trace species. Values sourced outside the project carry their reference; every engineering choice is PROTOTYPE.
M_NH3 = 0.0170305         # kg/mol (standard atomic weights; JSC 20584 Rev D lists 17 g/mol)
NH3_SMAC = dict(
    value_ppm={'1h': 30.0, '24h': 20.0, '7d': 3.0, '30d': 3.0, '180d': 3.0, '1000d': 3.0},
    status='EXTERNAL REFERENCE', basis='mole fraction (ppm by volume), applied unchanged at Wayfarer\'s cabin pressure as Rev D directs',
    reference='NASA JSC 20584 Rev D, Spacecraft Maximum Allowable Concentrations for Airborne Contaminants (02/2026), p. 9, SMAC table, '
              'Ammonia (7664-41-7): 1 h 30, 24 h 20 (off-nominal), 7 d 3, 30 d 3, 180 d 3, 1000 d 3 ppm (nominal); effects eye '
              'irritation, CNS headache; citation NRC Vol. 5 (2008) pp. 48-61.',
    note='Exposure-duration guidelines, not instantaneous thresholds: the 1 h and 24 h values apply to off-nominal events and permit minor, '
         'reversible effects (mild mucosal irritation); the long-term values protect continuous occupancy. An exceedance means increased '
         'risk to be evaluated, not certain harm (Rev D p. 7). Wayfarer\'s own medical limits stay OPEN (12!G22).')
TRACE = {
    'tcc_node': dict(value='A3', status='PROTOTYPE', note='A trace-contaminant control element in the sector 3 ECLSS bay beside the CO2 unit, '
                                                          'with its own fan and bed: it shares the place, not the function.'),
    'tcc_flow_m3_s': dict(value=15.3/3600.0, unit='m3/s', status='PROTOTYPE',
                          note='Process air through the bed: 15.3 m3/h, the ISS trace-contaminant control charcoal bed\'s nominal flow '
                               '(NASA NTRS 20070019823; about 15 m3/h also in NTRS 20100039332), one element per ring.'),
    'tcc_efficiency': dict(value=0.95, unit='-', status='PROTOTYPE',
                           note='Single-pass NH3 capture of a phosphoric-acid-treated activated-carbon bed (the ISS TCCS bed chemistry, NTRS '
                                '20170006640): NH3 is held as an ammonium salt. Breakthrough and bed capacity are not modelled.'),
    'co2_unit_nh3': dict(value=0.0, status='PROTOTYPE', note='The CO2 unit is credited with no NH3 removal (independent sinks).'),
    'condensate_nh3': dict(value=0.0, status='PROTOTYPE',
                           note='Cabin condensing heat exchangers dissolve NH3 into condensate on real spacecraft; there is no humidity model, '
                                'so this sink is left out. Leaving it out over-predicts NH3 (conservative).'),
    'background_ppm': dict(value=0.0, unit='ppm', status='PROTOTYPE',
                           note='Metabolic and off-gassing NH3 in normal operation is neglected: the ring starts at 0 and exposures before '
                                'an event count as 0.'),
}

# Where each kind of node, edge and boundary comes from (given once, not per item)
SOURCES = dict(sector='pressure_volumes.rooms: net (deck to overhead less the modelled fit-out; subfloor not counted)',
               corridor='ring_circulation.compartments: gross clear cavity of the corridor half (CIRC-001)',
               door='ring_circulation.doors (CIRC-001)', imv='PROTOTYPE: one intermodule-ventilation duct pair through each bulkhead',
               hatch='crew_transfer TUBE_HATCH (sector overhead)')


# ---------- topology ----------------------------------------------------------------------------------------------------------------------------

def topology(s):
    """Ring A's compartments, connections and boundaries, each with its source and status."""
    import pressure_volumes
    import ring_circulation
    rooms = pressure_volumes.rooms(s)
    nodes = []
    for c in ring_circulation.compartments(s, 1):
        if c['kind'] == 'sector':
            room = rooms[f"Sector_1_{c['id'][1]}"]
            nodes.append(dict(id=c['id'], kind='sector', V_m3=room['net_m3'], gross_m3=room['gross_m3'], basis='net', status='PROTOTYPE'))
        else:
            nodes.append(dict(id=c['id'], kind='corridor', V_m3=c['gross_m3'], gross_m3=c['gross_m3'], basis='gross', status='PROTOTYPE'))
    edges = []
    for d in ring_circulation.doors(s, 1):
        edges.append(dict(id=d['id'], kind='door', between=list(d['between']), leaf=d['name'], width_m=d['width'], height_m=d['height'],
                          normally='CLOSED', status='PROTOTYPE'))
    for d in ring_circulation.doors(s, 1):
        edges.append(dict(id='IMV.' + d['id'].split('.', 1)[1], kind='imv', between=list(d['between']), normally='OPEN', door=d['id'],
                          status='PROTOTYPE'))
    boundaries = [dict(id=f'TUBE.A{k}', kind='hatch', compartment=f'A{k}', outside=f'Crew_Tube_1_{k}', outside_m3=rooms[f'Crew_Tube_1_{k}']['gross_m3'],
                       state='CLOSED', modelled=False, status='PROTOTYPE')
                  for k in (1, 2, 3)]
    return dict(nodes=nodes, edges=edges, boundaries=boundaries, sources=SOURCES)


def door_flow(s, door):
    """Two-way buoyant exchange through an open doorway at ring A's floor gravity (m3/s, PROTOTYPE inputs)."""
    import habitat_ring
    g = habitat_ring.floor_gravity_g(s)*G0
    T = cabin_T()
    return PROTOTYPE['door_cd']['value']/3.0*door['width_m']*door['height_m']*math.sqrt(g*door['height_m']*PROTOTYPE['door_delta_T_K']['value']/T)


def cabin_T():
    import cabin_air
    return cabin_air.PROTOTYPE['temperature_K']['value']


def params(s=None, reg=None):
    """Everything step() needs: the compartments in order, the edges with their flows, the generation rate and the unit."""
    import cabin_air
    if s is None:
        import spec
        s = spec.load()[0]
    if reg is None:
        import life_support
        reg = life_support.load()
    base = cabin_air.params(s, reg)
    topo = topology(s)
    ids = [n['id'] for n in topo['nodes']]
    edges = []
    for e in topo['edges']:
        q = door_flow(s, e) if e['kind'] == 'door' else PROTOTYPE['imv_flow_m3_s']['value']
        edges.append(dict(id=e['id'], kind=e['kind'], i=ids.index(e['between'][0]), j=ids.index(e['between'][1]), Q_m3_s=q,
                          door=e.get('door', e['id'])))
    occ = PROTOTYPE['occupants']['value']
    return dict(P_Pa=base['P_Pa'], T_K=base['T_K'], R=cabin_air.R, M_CO2=cabin_air.M_CO2, ids=ids, V_m3=[n['V_m3'] for n in topo['nodes']],
                edges=edges, occupants=[occ.get(i, 0) for i in ids], per_person_kg_s=base['per_person_kg_s'], k_m3_s=base['k_m3_s'],
                removal=ids.index(PROTOTYPE['removal_node']['value']), co2_target=base['co2_target'], co2_max=base['co2_max'],
                well_mixed_x=cabin_air.steady_x(base), M_NH3=M_NH3, tcc_node=ids.index(TRACE['tcc_node']['value']),
                tcc_k_m3_s=TRACE['tcc_flow_m3_s']['value']*TRACE['tcc_efficiency']['value'], nh3_smac_ppm=NH3_SMAC['value_ppm'])


def n_mol(p, i):
    return p['P_Pa']*p['V_m3'][i]/(p['R']*p['T_K'])


# ---------- state -------------------------------------------------------------------------------------------------------------------------------

def start(p, x0=None, doors='CLOSED', vent='ON', removal='ON'):
    """Every compartment at x0 (default: the well-mixed steady state SYS-001's running unit holds); doors normally closed, ventilation and
    dampers open, the unit removing."""
    if x0 is None:
        x0 = p['well_mixed_x']
    xs = x0 if isinstance(x0, list) else [x0]*len(p['ids'])
    m = [xs[i]*n_mol(p, i)*p['M_CO2'] for i in range(len(p['ids']))]
    st = dict(t_s=0.0, m=m, m0=sum(m), generated=0.0, removed=0.0, vent=vent, removal=removal, occupants=list(p['occupants']),
              open={e['id']: (doors == 'OPEN') if e['kind'] == 'door' else True for e in p['edges']}, log=[], _cache={})
    st.update(trace_start(p))
    return st


def trace_start(p):
    """The trace species' state: no NH3, no source, the TCC on."""
    N = len(p['ids'])
    return dict(c=[0.0]*N, S=0.0, c0=0.0, S0=0.0, released=0.0, nh3_removed=0.0, I=[0.0]*N, source=dict(node=None, tau_s=None, state='NONE'),
                tcc='ON', _tcache={})


def set_edge(st, eid, is_open):
    """Open or close a door (the walk's leaf moved off or back onto its seat) or an IMV damper."""
    if st['open'][eid] != bool(is_open):
        st['open'][eid] = bool(is_open)
        st['log'].append((st['t_s'], 'edge', eid, bool(is_open)))
        st['_cache'] = {}; st['_tcache'] = {}


def set_vent(st, on):
    v = 'ON' if on else 'OFF'
    if st['vent'] != v:
        st['vent'] = v
        st['log'].append((st['t_s'], 'vent', '', v))
        st['_cache'] = {}; st['_tcache'] = {}


def set_removal(st, on):
    v = 'ON' if on else 'OFF'
    if st['removal'] != v:
        st['removal'] = v
        st['log'].append((st['t_s'], 'removal', '', v))
        st['_cache'] = {}


def set_occupants(st, occupants):
    if list(occupants) != st['occupants']:
        st['occupants'] = list(occupants)
        st['log'].append((st['t_s'], 'occupants', '', list(occupants)))
        st['_cache'] = {}


def set_source(st, p, node, inventory_kg, tau_s):
    """A finite NH3 source starts releasing into `node`: inventory_kg (all of it releasable) emptying at the first-order rate 1 / tau_s.
    Scenario data: the model has no default source."""
    if inventory_kg < 0.0 or tau_s <= 0.0:
        raise ValueError('a source needs a nonnegative inventory and a positive time constant')
    st['S'] += inventory_kg; st['S0'] += inventory_kg
    st['source'] = dict(node=p['ids'].index(node), tau_s=float(tau_s), state='LEAKING' if inventory_kg > 0.0 else 'NONE')
    st['log'].append((st['t_s'], 'source', node, [inventory_kg, tau_s]))
    st['_tcache'] = {}


def isolate_source(st):
    """Contain the source (the spill bagged, the container sealed): it releases nothing more; what it still holds stays in it, accounted."""
    if st['source']['state'] == 'LEAKING':
        st['source']['state'] = 'ISOLATED'
        st['log'].append((st['t_s'], 'source', '', 'ISOLATED'))
        st['_tcache'] = {}


def set_tcc(st, on):
    """The trace-contaminant control element, independent of the CO2 unit."""
    v = 'ON' if on else 'OFF'
    if st['tcc'] != v:
        st['tcc'] = v
        st['log'].append((st['t_s'], 'tcc', '', v))
        st['_tcache'] = {}


def flow(st, e):
    """The exchange flow an edge carries now (m3/s): a door when open; an IMV pair when the ventilation runs and its damper is open."""
    if not st['open'][e['id']]:
        return 0.0
    if e['kind'] == 'imv' and st['vent'] != 'ON':
        return 0.0
    return e['Q_m3_s']


# ---------- the exact step ----------------------------------------------------------------------------------------------------------------------

def rates(st, p):
    """The matrix A of dy/dt = A y on y = [m_1..m_N, generated, removed, 1]."""
    N = len(p['ids']); V = p['V_m3']; n = N+3
    A = [[0.0]*n for _ in range(n)]
    for e in p['edges']:
        q = flow(st, e)
        if q > 0.0:
            i, j = e['i'], e['j']
            A[i][j] += q/V[j]; A[i][i] -= q/V[i]
            A[j][i] += q/V[i]; A[j][j] -= q/V[j]
    if st['removal'] == 'ON':
        r = p['removal']; kr = p['k_m3_s']/V[r]
        A[r][r] -= kr
        A[N+1][r] += kr
    for i in range(N):
        g = st['occupants'][i]*p['per_person_kg_s']
        A[i][N+2] += g
        A[N][N+2] += g
    return A


def _mul(X, Y):
    n = len(X)
    out = [[0.0]*n for _ in range(n)]
    for i in range(n):
        Xi = X[i]; Oi = out[i]
        for k in range(n):
            a = Xi[k]
            if a != 0.0:
                Yk = Y[k]
                for j in range(n):
                    Oi[j] += a*Yk[j]
    return out


def expm(M):
    """exp(M) by scaling and squaring of a fixed-order Taylor series (Godot repeats it operation for operation)."""
    n = len(M)
    norm = max(sum(abs(M[i][j]) for i in range(n)) for j in range(n))
    s = 0; scale = 1.0
    while norm*scale > SCALE_NORM:
        scale *= 0.5; s += 1
    X = [[M[i][j]*scale for j in range(n)] for i in range(n)]
    E = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    T = [row[:] for row in E]
    for k in range(1, TAYLOR_ORDER+1):
        T = _mul(T, X)
        inv = 1.0/k
        for i in range(n):
            Ti = T[i]; Ei = E[i]
            for j in range(n):
                Ti[j] *= inv
                Ei[j] += Ti[j]
    for _ in range(s):
        E = _mul(E, E)
    return E


def propagator(st, p, dt):
    key = repr(dt)
    if key not in st['_cache']:
        A = rates(st, p)
        st['_cache'][key] = expm([[a*dt for a in row] for row in A])
    return st['_cache'][key]


def step(st, p, dt):
    """Advance dt seconds exactly (constant connections, occupants, removal and source state over the step)."""
    E = propagator(st, p, dt)
    N = len(p['ids'])
    y = st['m']+[st['generated'], st['removed'], 1.0]
    out = [sum(E[i][j]*y[j] for j in range(N+3)) for i in range(N+2)]
    st['m'] = out[:N]; st['generated'] = out[N]; st['removed'] = out[N+1]
    trace_step(st, p, dt)
    st['t_s'] += dt
    return st


# ---------- the trace species (SYS-002 v2) ------------------------------------------------------------------------------------------------------

def trace_active(st):
    return st['S'] > 0.0 or any(v != 0.0 for v in st['c'])


def trace_rates(st, p):
    """The matrix B of dz/dt = B z on z = [c_1..c_N, S, released, removed, I_1..I_N] (N + 3 + N)."""
    N = len(p['ids']); V = p['V_m3']; n = 2*N+3
    S, REL, REM = N, N+1, N+2
    B = [[0.0]*n for _ in range(n)]
    for e in p['edges']:
        q = flow(st, e)
        if q > 0.0:
            i, j = e['i'], e['j']
            B[i][j] += q/V[j]; B[i][i] -= q/V[i]
            B[j][i] += q/V[i]; B[j][j] -= q/V[j]
    src = st['source']
    if src['state'] == 'LEAKING':
        lam = 1.0/src['tau_s']
        B[S][S] -= lam; B[src['node']][S] += lam; B[REL][S] += lam
    if st['tcc'] == 'ON':
        t = p['tcc_node']; kt = p['tcc_k_m3_s']/V[t]
        B[t][t] -= kt; B[REM][t] += kt
    for i in range(N):
        B[N+3+i][i] = 1.0
    return B


def trace_step(st, p, dt):
    if not trace_active(st):
        return                          # nothing to carry: z stays 0 (integrals included), at no cost
    key = repr(dt)
    if key not in st['_tcache']:
        B = trace_rates(st, p)
        st['_tcache'][key] = expm([[b*dt for b in row] for row in B])
    E = st['_tcache'][key]
    N = len(p['ids']); n = 2*N+3
    z = st['c']+[st['S'], st['released'], st['nh3_removed']]+st['I']
    out = [sum(E[i][j]*z[j] for j in range(n)) for i in range(n)]
    st['c'] = out[:N]; st['S'] = out[N]; st['released'] = out[N+1]; st['nh3_removed'] = out[N+2]; st['I'] = out[N+3:]
    if st['source']['state'] == 'LEAKING' and st['S'] <= 0.0:
        st['S'] = 0.0


def trace_ledger_error(st):
    """NH3 is only moved, never made: the source's inventory plus the air plus the bed holds what was there at the start."""
    return (sum(st['c'])+st['S']+st['nh3_removed'])-(st['c0']+st['S0'])


def release_ledger_error(st):
    """What the source lost is what it released."""
    return (st['S0']-st['S'])-st['released']


def ppm(st, p, i):
    """NH3 mole fraction in compartment i, parts per million."""
    return st['c'][i]/M_NH3/n_mol(p, i)*1e6


def trace_units(st, p, i):
    """Every unit kept apart: mass, molar concentration, mole fraction, ppm and partial pressure."""
    x = st['c'][i]/M_NH3/n_mol(p, i)
    return dict(kg=st['c'][i], mol_m3=st['c'][i]/M_NH3/p['V_m3'][i], x=x, ppm=x*1e6, pp_Pa=x*p['P_Pa'])


def exposure_ppm_s(st, p, i):
    """The integral of compartment i's NH3 mole fraction over time so far, ppm s (exact: from the integral state)."""
    return st['I'][i]/M_NH3/n_mol(p, i)*1e6


def ledger_error(st):
    return sum(st['m'])-(st['m0']+st['generated']-st['removed'])


# ---------- readout -----------------------------------------------------------------------------------------------------------------------------

def components(st, p):
    """The groups of compartments joined by an open edge now (union-find); each group lists its members in node order."""
    N = len(p['ids']); root = list(range(N))

    def find(a):
        while root[a] != a:
            root[a] = root[root[a]]; a = root[a]
        return a
    for e in p['edges']:
        if flow(st, e) > 0.0:
            a, b = find(e['i']), find(e['j'])
            if a != b:
                root[max(a, b)] = min(a, b)
    groups = {}
    for i in range(N):
        groups.setdefault(find(i), []).append(i)
    return sorted(groups.values())


def readout(st, p):
    """Per compartment: fraction, partial pressure, trend, its group, whether it is isolated and whether removal reaches it."""
    N = len(p['ids']); A = rates(st, p)
    y = st['m']+[st['generated'], st['removed'], 1.0]
    groups = components(st, p)
    group_of = {i: g for g in groups for i in g}
    out = []
    for i in range(N):
        nm = n_mol(p, i)
        dm = sum(A[i][j]*y[j] for j in range(N+3))
        g = group_of[i]
        out.append(dict(id=p['ids'][i], x=st['m'][i]/p['M_CO2']/nm, pp_kpa=st['m'][i]/p['M_CO2']/nm*p['P_Pa']/1000.0,
                        dxdt_per_h=dm/p['M_CO2']/nm*3600.0, group=groups.index(g), isolated=len(g) == 1,
                        removal_reaches=st['removal'] == 'ON' and p['removal'] in g, occupants=st['occupants'][i],
                        nh3_ppm=ppm(st, p, i), tcc_reaches=st['tcc'] == 'ON' and p['tcc_node'] in g))
    total_n = sum(n_mol(p, i) for i in range(N))
    src = st['source']
    return dict(nodes=out, x_mean=sum(st['m'])/p['M_CO2']/total_n, groups=len(groups), vent=st['vent'], removal=st['removal'], tcc=st['tcc'],
                nh3_ppm_mean=sum(st['c'])/M_NH3/total_n*1e6, source=dict(state=src['state'], inventory_kg=st['S'],
                node=None if src['node'] is None else p['ids'][src['node']], released_kg=st['released']), nh3_removed_kg=st['nh3_removed'],
                open=sorted(k for k, v in st['open'].items() if v and k.startswith('CIRC.')), t_s=st['t_s'])


# ---------- reference run -----------------------------------------------------------------------------------------------------------------------

# The checkpoint run Godot must reproduce (cases C, D, E, B and F in one 10 h run at the runtime's step): doors closed and ventilation on
# from the well-mixed state; ventilation off (every compartment isolated); a sector door reopens (two compartments join, not at once); the
# ring loop is opened all round but one node door (the other way round joins everything); the occupants move to A1; ventilation back on.
PROOF_EVENTS = [(1800.0, 'vent', '', 'OFF'), (7200.0, 'edge', 'CIRC.A2N', True), (14400.0, 'edge', 'CIRC.A1P', True),
                (14400.0, 'edge', 'CIRC.A2P', True), (14400.0, 'edge', 'CIRC.AC2', True), (14400.0, 'edge', 'CIRC.A3N', True),
                (14400.0, 'edge', 'CIRC.A3P', True), (14400.0, 'edge', 'CIRC.AC3', True), (14400.0, 'edge', 'CIRC.A1N', True),
                (21600.0, 'occupants', '', [6, 0, 0, 0, 0, 0, 0, 0, 0]), (28800.0, 'vent', '', 'ON')]
PROOF_END_S = 36000.0
PROOF_EVERY_S = 3600.0     # hourly: every event of the run falls between two checkpoints
PROOF_DT_S = 10.0


def apply(st, ev, p=None):
    _, kind, eid, v = ev
    if kind == 'vent':
        set_vent(st, v == 'ON')
    elif kind == 'removal':
        set_removal(st, v == 'ON')
    elif kind == 'edge':
        set_edge(st, eid, v)
    elif kind == 'occupants':
        set_occupants(st, v)
    elif kind == 'tcc':
        set_tcc(st, v == 'ON')
    elif kind == 'source':
        if v == 'ISOLATED':
            isolate_source(st)
        else:
            set_source(st, p, eid, v[0], v[1])
    else:
        raise ValueError(kind)


def checkpoints(p, dt=PROOF_DT_S, events=None):
    st = start(p); out = []; events = list(PROOF_EVENTS if events is None else events)
    steps = int(round(PROOF_END_S/dt)); every = int(round(PROOF_EVERY_S/dt))
    for i in range(steps+1):
        while events and st['t_s'] >= events[0][0]-1e-9:
            apply(st, events.pop(0), p)
        if i % every == 0:
            out.append(dict(t_s=st['t_s'], m=list(st['m']), generated=st['generated'], removed=st['removed'],
                            groups=len(components(st, p))))
        if i < steps:
            step(st, p, dt)
    return out


# SYS-002 v2: the trace reference run (a release in A1 with the ventilation running; the fans stopped; a door path to the TCC opened; the
# source contained; the TCC off and on again; the whole loop opened). PROTOTYPE numbers chosen to exercise every term, not a scenario.
TRACE_PROOF_EVENTS = [(0.0, 'source', 'A1', [0.007, 3600.0]), (900.0, 'vent', '', 'OFF'), (3600.0, 'edge', 'CIRC.A1N', True),
                      (3600.0, 'edge', 'CIRC.AC3', True), (3600.0, 'edge', 'CIRC.A3P', True), (7200.0, 'source', '', 'ISOLATED'),
                      (14400.0, 'tcc', '', 'OFF'), (21600.0, 'tcc', '', 'ON'), (21600.0, 'edge', 'CIRC.A1P', True),
                      (21600.0, 'edge', 'CIRC.AC1', True), (21600.0, 'edge', 'CIRC.A2N', True), (28800.0, 'vent', '', 'ON')]


def trace_checkpoints(p, dt=PROOF_DT_S, events=None):
    st = start(p); out = []; events = list(TRACE_PROOF_EVENTS if events is None else events)
    steps = int(round(PROOF_END_S/dt)); every = int(round(PROOF_EVERY_S/dt))
    for i in range(steps+1):
        while events and st['t_s'] >= events[0][0]-1e-9:
            apply(st, events.pop(0), p)
        if i % every == 0:
            out.append(dict(t_s=st['t_s'], c=list(st['c']), S=st['S'], released=st['released'], removed=st['nh3_removed'], I=list(st['I']),
                            m=list(st['m'])))
        if i < steps:
            step(st, p, dt)
    return out


def steady(st, p, hours=200.0):
    """The state after a long settle (a 1 h exact step repeated): for reports and tests."""
    for _ in range(int(hours)):
        step(st, p, 3600.0)
    return st


def well_mixed_gap(p):
    """How far the compartments of the DS-1 configuration (doors closed, ventilation on, two per sector, removal in A3) sit from the one
    well-mixed volume DS-1 assumes, at the steady state."""
    st = steady(start(p), p)
    r = readout(st, p)
    xs = [q['x'] for q in r['nodes']]
    return dict(well_mixed_x=p['well_mixed_x'], mean_x=r['x_mean'], min_x=min(xs), max_x=max(xs),
                min_id=r['nodes'][xs.index(min(xs))]['id'], max_id=r['nodes'][xs.index(max(xs))]['id'])


def contract(s=None, reg=None):
    if s is None:
        import spec
        s = spec.load()[0]
    if reg is None:
        import life_support
        reg = life_support.load()
    p = params(s, reg); topo = topology(s)
    return dict(schema=SCHEMA, version=VERSION, system='RING_A_AIR_CONNECTIVITY',
                notice='SIMULATION: ring A\'s cabin CO2 by compartment. Exchange rates, occupants\' places and the ventilation are PROTOTYPE; '
                       'nothing here is canon.',
                params=p, topology={k: v for k, v in topo.items() if k != 'edges'},   # the edges travel in params
                prototype=PROTOTYPE, tolerance=TOLERANCE, taylor_order=TAYLOR_ORDER, scale_norm=SCALE_NORM,
                proof=dict(events=[list(e) for e in PROOF_EVENTS], end_s=PROOF_END_S, every_s=PROOF_EVERY_S, dt_s=PROOF_DT_S,
                           initial='every compartment at the well-mixed steady state, doors closed, ventilation on, removal on',
                           checkpoints=checkpoints(p)),
                trace=dict(species='NH3', smac=NH3_SMAC, prototype=TRACE,
                           proof=dict(events=[list(e) for e in TRACE_PROOF_EVENTS], end_s=PROOF_END_S, every_s=PROOF_EVERY_S, dt_s=PROOF_DT_S,
                                      initial='as the CO2 proof; no NH3; the TCC on', checkpoints=trace_checkpoints(p))),
                ds1=dict(model='cabin_air (one well-mixed volume, unchanged)', gap=well_mixed_gap(p)))


def write(root, out):
    import life_support
    import spec
    Path(out).write_text(json.dumps(contract(spec.load(Path(root))[0], life_support.load(Path(root))), separators=(',', ':'))+'\n')    # compact: the play download has a byte budget


def main(argv):
    import spec
    s = spec.load()[0]
    p = params(s); topo = topology(s)
    print(f"ring A: {len(p['ids'])} compartments, {sum(p['V_m3']):.2f} m3")
    for n in topo['nodes']:
        print(f"  {n['id']:5s} {n['kind']:8s} {n['V_m3']:7.2f} m3 ({n['basis']}, gross {n['gross_m3']:.2f})")
    for e in p['edges'][:1]+p['edges'][9:10]:
        print(f"  {e['kind']} exchange {e['Q_m3_s']*3600:.0f} m3/h")
    gap = well_mixed_gap(p)
    print(f"DS-1 configuration steady: well-mixed {100*gap['well_mixed_x']:.3f} %, compartments {100*gap['min_x']:.3f} % ({gap['min_id']}) "
          f"to {100*gap['max_x']:.3f} % ({gap['max_id']}), mean {100*gap['mean_x']:.3f} %")
    cp = checkpoints(p)
    print(f"proof: {len(cp)} checkpoints, groups {[c['groups'] for c in cp]}")
    print(f"NH3: TCC in {p['ids'][p['tcc_node']]} at {p['tcc_k_m3_s']*3600:.2f} m3/h effective; SMAC (JSC 20584 Rev D) {NH3_SMAC['value_ppm']}")
    tc = trace_checkpoints(p)
    print("trace proof ppm A1/A3 by hour: " + ', '.join(f"{c['c'][0]/M_NH3/n_mol(p, 0)*1e6:.1f}/{c['c'][2]/M_NH3/n_mol(p, 2)*1e6:.1f}" for c in tc))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
