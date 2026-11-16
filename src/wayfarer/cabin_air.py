"""SYS-001 ring cabin CO2 balance: one well-mixed ring air volume, its occupants and one CO2-removal unit. Standard library only.

A reusable engineering state (the first one the walk can change): it knows nothing of games, scenarios or scores. Consumers apply the
unit's operations (`operate`) and read the state (`readout`); Godot repeats `step` exactly (godot/scripts/systems/cabin_air.gd) and must
reproduce `checkpoints()` within `TOLERANCE` before the state is shown.

Physics. CO2 is a trace gas in the cabin (mole fraction below 1 %), so the total gas amount n = P V / (R T) is held fixed and the CO2
mass m carries the state:
    dm/dt = G - k m / V        G = occupants x per-person CO2 rate; k = the unit's effective scrubbed flow (0 unless RUNNING)
For a step dt with G and k constant this has the exact solution
    m(t+dt) = m_ss + (m(t) - m_ss) exp(-k dt / V),   m_ss = G V / k      (k > 0)
    m(t+dt) = m(t) + G dt                                               (k = 0)
so the stepped result does not depend on dt, and the ledger generated - removed = m - m0 closes exactly. Mole fraction x = (m / M) / n and
partial pressure p = x P.

Sources and statuses (every value travels with its status into the package):
- cabin pressure 80 kPa (BASELINE), CO2 target 0.3 % and control maximum 0.5 % (WORKING, "not final medical/ECLSS limits"): the spec;
- CO2 1.0 kg per human-day (41!B15, STUDY HYPOTHESIS): data/life_support.toml;
- the free gas volume: PROTOTYPE, from the built rooms (pressure_volumes, ring_circulation), see `volume()`;
- occupants, cabin temperature, the unit's rating and the habitability bands: PROTOTYPE, see `PROTOTYPE`.
Nothing here is written back to canon.

    python3 src/wayfarer/cabin_air.py      # print the state, the bands and the checkpoint run
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

FILE = 'wf_cabin_air.json'
SCHEMA = 'WF_CABIN_AIR'
VERSION = 2
R = 8.314462618          # J/(mol K), CODATA (exact since 2019)
M_CO2 = 0.0440095        # kg/mol
DAY_S = 86400.0

# The unit's state has three independent parts (one enum could not hold a failed fan inside an isolated unit):
#   mode   RUNNING (energized, process air flowing through the bed) or ISOLATED (de-energized, its valves shut: safe to open)
#   fan    the process-air fan's condition: OK or FAILED (a FAILED fan moves no air, so the bed removes nothing)
#   spare  where the ring's replacement fan is: NONE (no spare), BENCH (at the sector 2 workbench), CARRIED (by a crew member),
#          INSTALLED (fitted in the unit)
# The unit removes CO2 only when RUNNING with its fan OK. "Repaired but not yet restored" is ISOLATED with the fan OK.
FIELDS = dict(mode=('RUNNING', 'ISOLATED'), fan=('OK', 'FAILED'), spare=('NONE', 'BENCH', 'CARRIED', 'INSTALLED'))
# operation -> the field values it requires (checked in this order) and the values it sets. Nothing else changes a field. Where the
# crew member stands (at the bay, at the workbench) is the consumer's business; this model knows only where the part is.
OPERATIONS = {
    'isolate': dict(requires=dict(mode=['RUNNING']), sets=dict(mode='ISOLATED')),
    'restore': dict(requires=dict(mode=['ISOLATED'], fan=['OK']), sets=dict(mode='RUNNING')),
    'take_spare': dict(requires=dict(spare=['BENCH']), sets=dict(spare='CARRIED')),
    'install_spare': dict(requires=dict(mode=['ISOLATED'], fan=['FAILED'], spare=['CARRIED']), sets=dict(fan='OK', spare='INSTALLED')),
    'fault_fan': dict(requires=dict(fan=['OK']), sets=dict(fan='FAILED'), kind='FAULT'),
}
# Why an operation is refused: operation -> field -> the value that blocks it -> the engineering reason. A refusal changes nothing.
REFUSALS = {
    'isolate': dict(mode=dict(ISOLATED='The unit is already isolated.')),
    'restore': dict(mode=dict(RUNNING='The unit is already running.'),
                    fan=dict(FAILED='The process-air fan has failed: energizing the unit would move no air through the bed and remove no '
                                    'CO2. Replace the fan first.')),
    'take_spare': dict(spare=dict(NONE='There is no spare fan.', CARRIED='The spare fan is already being carried.',
                                  INSTALLED='The spare fan is already installed.')),
    'install_spare': dict(mode=dict(RUNNING='The unit is energized and its process duct is live: isolate it before opening it.'),
                          fan=dict(OK='The fan is working: there is nothing to replace.'),
                          spare=dict(NONE='There is no spare fan.', BENCH='The spare fan is still at the sector 2 workbench.',
                                     INSTALLED='The spare fan is already installed.')),
    'fault_fan': dict(fan=dict(FAILED='The fan has already failed.')),
}

# Godot must reproduce the checkpoints to this tolerance (|got - want| <= abs + rel |want|). Both sides evaluate the same closed-form
# step in IEEE 754 doubles (GDScript float is 64-bit); the only differences are the last-place rounding of exp() between the two math
# libraries, compounded over at most 28,800 steps: about 1e-13 relative. 1e-9 relative leaves four orders of margin and is still
# a million times finer than any display or physical decision (the readout shows 0.001 % of CO2, a 3e-3 relative step at 0.3 %).
TOLERANCE = {'rel': 1e-9, 'abs_kg': 1e-9}

PROTOTYPE = {
    'occupants': dict(value=6, unit='persons', status='PROTOTYPE',
                      note='Half the rated occupancy of 12 (LOCKED, 02!A42) in ring A; the six-person story crew never sizes a system.'),
    'temperature_K': dict(value=295.0, unit='K', status='PROTOTYPE',
                          note='Cabin air temperature; no cabin temperature setpoint is in the spec.'),
    'unit_rated_occupants': dict(value=12, unit='persons', status='PROTOTYPE',
                                 note='The ring\'s CO2-removal unit is rated to hold the target with the whole rated crew in one ring, so '
                                      'either ring can carry everyone. Technology (a regenerable sorbent bed with a process-air fan) '
                                      'and its parts stay OPEN (12!G26:G27).'),
    'mixing': dict(value='WELL_MIXED_RING', status='PROTOTYPE',
                   note='The ring\'s sectors and corridor compartments are one well-mixed volume. The CIRC pressure doors are normally '
                        'closed (ring_circulation.doors), so the connection is the ring\'s ventilation (an intermodule-ventilation duct '
                        'loop with dampers, assumed open; ventilation is not in canon): a door neither joins nor splits the gas here. '
                        'Local excess near the occupants is of order G / Q_vent, about 0.05-0.1 % CO2 at a few hundred m3/h.'),
}

# Habitability bands by CO2 partial pressure (the body responds to partial pressure, not to the fraction). The first is the spec's
# control band; the other two are PROTOTYPE reference levels from public practice, labelled, never canon (medical limits OPEN, 12!G22).
BANDS = [
    dict(id='CONTROL', kind='operational control limit', source='spec habitat.atmosphere.control.co2_max_fraction (WORKING)',
         meaning='Outside the normal operating range: corrective action required. Not a medical limit.'),
    dict(id='DEGRADED', kind='degraded habitability', kpa=0.8, status='PROTOTYPE',
         source='order of the long-duration submarine limit (about 0.8 % at one atmosphere)',
         meaning='Safety margin reduced; headaches and lower performance become likely over hours. Not an immediate emergency.'),
    dict(id='DANGER', kind='physiological danger', kpa=3.0, status='PROTOTYPE',
         source='order of the 15-minute occupational exposure limit (3 % at one atmosphere)',
         meaning='Clinically meaningful risk: breathlessness, impaired judgement; leave or restore removal now.'),
]

BINDING = dict(component='RA_ECLSS_CO2', ring='RING_A', node='Prod_RA3_GDN_ECLSS', reach_m=2.4, status='PROTOTYPE',
               note='The ring A sector 3 ECLSS bay (route_fitout ECLSS_Bay, the UJ-004 learning station) houses the unit.')


def spec_values(s):
    a = s['habitat']['atmosphere']
    return dict(pressure_kpa=float(a['cabin_pressure_kpa']), pressure_status=a['canon_status'],
                co2_target=float(a['control']['co2_target_fraction']), co2_max=float(a['control']['co2_max_fraction']),
                control_status=a['control']['canon_status'])


def co2_rate(reg):
    r = next(q for q in reg['rate'] if q['id'] == 'CO2_REMOVED')
    return dict(value=float(r['value']), unit=r['unit'], source=r['source'], status='STUDY')


def volume(s):
    """Ring A's free gas volume, PROTOTYPE: the three sectors' net volume (deck to overhead less the modelled fit-out; the subfloor is
    not counted) plus ring A's circulation corridor (gross clear cavity, CIRC-001), crew tubes excluded. Bounds: the sectors alone
    with every door shut, and all gross."""
    import pressure_volumes
    import ring_circulation
    rooms = pressure_volumes.rooms(s)
    sectors = {k: q for k, q in rooms.items() if k.startswith('Sector_1_')}
    corridor = ring_circulation.budget(s)['corridor_gross_per_ring_m3']
    net = sum(q['net_m3'] for q in sectors.values())
    gross = sum(q['gross_m3'] for q in sectors.values())
    sector3 = sectors['Sector_1_3']
    return dict(value=net+corridor, unit='m3', status='PROTOTYPE',
                parts={**{k: round(q['net_m3'], 3) for k, q in sectors.items()}, 'RING_A_CORRIDOR_gross': round(corridor, 3)},
                bounds=dict(sector3_alone_net=sector3['net_m3'], sector3_alone_gross=sector3['gross_m3'], ring_all_gross=gross+corridor),
                note='Sectors net + corridor gross; crew tubes (about 49 m3 each) excluded. The canon allocation is 120 m3 usable per ring '
                     '(12!A2:A4, WORKING): a usable-space figure, not the connected gas volume.')


def params(s=None, reg=None):
    """The model's parameters with their statuses: everything step() needs."""
    if s is None:
        import spec
        s = spec.load()[0]
    if reg is None:
        import life_support
        reg = life_support.load()
    sv = spec_values(s); rate = co2_rate(reg); vol = volume(s)
    P = sv['pressure_kpa']*1000.0; T = PROTOTYPE['temperature_K']['value']; V = vol['value']
    per_person = rate['value']/DAY_S                                   # kg/s
    # k so that the rated crew's generation is held exactly at the target: m_ss/V = G_rated/k and x_ss = target
    k = PROTOTYPE['unit_rated_occupants']['value']*per_person*R*T/(P*M_CO2*sv['co2_target'])
    return dict(P_Pa=P, T_K=T, V_m3=V, n_mol=P*V/(R*T), occupants=PROTOTYPE['occupants']['value'], per_person_kg_s=per_person,
                k_m3_s=k, co2_target=sv['co2_target'], co2_max=sv['co2_max'])


def removing(st):
    """The unit removes CO2 only when it is energized and its fan moves air."""
    return st['mode'] == 'RUNNING' and st['fan'] == 'OK'


def steady_x(p):
    """The fraction a removing unit holds the ring at with the present occupants."""
    G = p['occupants']*p['per_person_kg_s']
    return G*p['V_m3']/p['k_m3_s']/(p['n_mol']*M_CO2)


def start(p, mode='RUNNING', fan='OK', spare='NONE', x0=None):
    """A ring at x0, or at the steady state when the unit is removing (else at the target)."""
    st = dict(t_s=0.0, mode=mode, fan=fan, spare=spare, log=[])
    for f, v in (('mode', mode), ('fan', fan), ('spare', spare)):
        assert v in FIELDS[f], (f, v)
    if x0 is None:
        x0 = steady_x(p) if removing(st) else p['co2_target']
    m0 = x0*p['n_mol']*M_CO2
    st.update(m_kg=m0, m0_kg=m0, generated_kg=0.0, removed_kg=0.0)
    return st


def blocked(st, op):
    """'' if op is allowed now, else the field that blocks it ('op' for an unknown operation)."""
    if op not in OPERATIONS:
        return 'op'
    for f, allowed in OPERATIONS[op]['requires'].items():
        if st[f] not in allowed:
            return f
    return ''


def operate(st, op):
    """Apply an operation; returns '' or the reason it is refused (the state is then unchanged)."""
    f = blocked(st, op)
    if f == 'op':
        return f'unknown operation {op}'
    if f:
        return REFUSALS.get(op, {}).get(f, {}).get(st[f], f'{op} refused: {f} is {st[f]}')
    sets = OPERATIONS[op]['sets']
    st['log'].append((st['t_s'], op, {k: st[k] for k in sets}, dict(sets)))
    st.update(sets)
    return ''


def step(st, p, dt):
    """Advance dt seconds with the exact solution for constant generation and removal."""
    G = p['occupants']*p['per_person_kg_s']; V = p['V_m3']
    k = p['k_m3_s'] if removing(st) else 0.0
    m = st['m_kg']
    if k > 0.0:
        m_ss = G*V/k
        m_new = m_ss+(m-m_ss)*math.exp(-k*dt/V)
    else:
        m_new = m+G*dt
    st['generated_kg'] += G*dt
    st['removed_kg'] += G*dt-(m_new-m)
    st['m_kg'] = m_new
    st['t_s'] += dt
    return st


def ledger_error(st):
    return st['m_kg']-(st['m0_kg']+st['generated_kg']-st['removed_kg'])


def status(st):
    """One word for the unit's condition, from its fields."""
    if st['mode'] == 'RUNNING':
        return 'OPERATING' if st['fan'] == 'OK' else 'RUNNING_NOT_REMOVING'
    return 'ISOLATED_READY' if st['fan'] == 'OK' else 'ISOLATED_FAULT'


def readout(st, p):
    """What a panel can show: fraction, partial pressure, trend, the band and the time to the control limit, counted from the present
    state at the present trend (no removal: the linear rise, exact; removing: the trend falls or holds, so no limit is approached)."""
    x = st['m_kg']/M_CO2/p['n_mol']; pp = x*p['P_Pa']/1000.0
    G = p['occupants']*p['per_person_kg_s']; k = p['k_m3_s'] if removing(st) else 0.0
    dmdt = G-k*st['m_kg']/p['V_m3']
    dxdt_h = dmdt/M_CO2/p['n_mol']*3600.0
    band = 'NOMINAL' if x <= p['co2_target'] else ('ABOVE_TARGET' if x <= p['co2_max'] else 'CONTROL')
    for b in BANDS[1:]:
        if pp >= b['kpa']:
            band = b['id']
    # with removal the approach to the steady state is monotonic, so the limit is reached only if the steady state lies beyond it
    to_max = None
    if x < p['co2_max'] and dxdt_h > 0:
        if k > 0.0:
            x_ss = steady_x(p)
            if x_ss > p['co2_max']:
                to_max = -p['V_m3']/k*math.log((x_ss-p['co2_max'])/(x_ss-x))/3600.0
        else:
            to_max = (p['co2_max']-x)/dxdt_h
    return dict(x=x, pp_kpa=pp, dxdt_per_h=dxdt_h, band=band, mode=st['mode'], fan=st['fan'], spare=st['spare'], status=status(st),
                removing=removing(st), hours_to_control_limit=to_max, t_s=st['t_s'])


def diagnostics(st, p):
    """The unit's component readings a technician compares (derived from the state; only the fan can fail in this model). Supply and
    controller are readings, not modelled faults: a supply loss would show every reading dark, a controller fault inconsistent or
    failed self-test readings, a spent bed full airflow with no CO2 taken out."""
    on = st['mode'] == 'RUNNING'
    flow = p['k_m3_s']*3600.0 if removing(st) else 0.0
    k = p['k_m3_s'] if removing(st) else 0.0
    return dict(supply='ENERGIZED' if on else 'ISOLATED', controller='SELF-TEST PASS' if on else 'OFF (isolated)',
                fan_command='ON' if on else 'OFF', fan_speed_pct=100.0 if removing(st) else 0.0, fan_condition=st['fan'],
                scrubbed_flow_m3_h=flow, bed='NORMAL' if on else 'NORMAL (cold)', removal_kg_h=k*st['m_kg']/p['V_m3']*3600.0,
                spare=st['spare'])


def hours_between(p, x_from, x_to):
    """Hours for the fraction to climb from x_from to x_to with no removal (the linear rise)."""
    return (x_to-x_from)*p['n_mol']*M_CO2/(p['occupants']*p['per_person_kg_s'])/3600.0


# The checkpoint run Godot must reproduce, at the runtime's 1 s step: steady state with the spare at the workbench; the fan fails; the
# unit is isolated; the spare is fetched and installed; the unit is restored; 10 h in all. Each event is (t, operation, expected
# outcome): '' accepted, or the field that must refuse it (the state then must not change). The refusals probe the safety rules.
PROOF_START = dict(mode='RUNNING', fan='OK', spare='BENCH')
PROOF_EVENTS = [(600.0, 'fault_fan', ''), (900.0, 'restore', 'mode'), (1200.0, 'install_spare', 'mode'), (1800.0, 'isolate', ''),
                (2100.0, 'restore', 'fan'), (2400.0, 'install_spare', 'spare'), (3600.0, 'take_spare', ''),
                (5400.0, 'install_spare', ''), (5700.0, 'install_spare', 'fan'), (7200.0, 'restore', ''), (7500.0, 'take_spare', 'spare')]
PROOF_END_S = 36000.0
PROOF_EVERY_S = 900.0
PROOF_DT_S = 1.0


def run_events(st, p, events):
    """Apply every event due now; asserts each has its expected outcome."""
    while events and st['t_s'] >= events[0][0]-1e-9:
        t, op, expect = events.pop(0)
        got = blocked(st, op)
        before = {f: st[f] for f in FIELDS}
        reason = operate(st, op)
        assert got == expect, (t, op, got, expect, reason)
        assert expect == '' or {f: st[f] for f in FIELDS} == before, (t, op)


def checkpoints(p, dt=PROOF_DT_S):
    st = start(p, **PROOF_START); out = []; events = list(PROOF_EVENTS)
    steps = int(round(PROOF_END_S/dt)); every = int(round(PROOF_EVERY_S/dt))
    for i in range(steps+1):
        run_events(st, p, events)
        if i % every == 0:
            r = readout(st, p)
            out.append(dict(t_s=st['t_s'], mode=st['mode'], fan=st['fan'], spare=st['spare'], m_kg=st['m_kg'], x=r['x'],
                            generated_kg=st['generated_kg'], removed_kg=st['removed_kg']))
        if i < steps:
            step(st, p, dt)
    return out


def analytic(p, t_s):
    """Closed-form m(t) of the proof run, for the reference check (independent of the stepping): steady until the fan fails, the
    linear rise until the unit is restored with a working fan, then the exponential approach to the steady state."""
    G = p['occupants']*p['per_person_kg_s']; V = p['V_m3']; k = p['k_m3_s']
    t_fail = next(t for t, op, e in PROOF_EVENTS if op == 'fault_fan' and not e)
    t_back = next(t for t, op, e in PROOF_EVENTS if op == 'restore' and not e)
    m0 = steady_x(p)*p['n_mol']*M_CO2
    if t_s <= t_fail:
        return m0
    m_up = m0+G*(min(t_s, t_back)-t_fail)
    if t_s <= t_back:
        return m_up
    m_ss = G*V/k
    return m_ss+(m_up-m_ss)*math.exp(-k*(t_s-t_back)/V)


def contract(s=None, reg=None):
    if s is None:
        import spec
        s = spec.load()[0]
    if reg is None:
        import life_support
        reg = life_support.load()
    p = params(s, reg); sv = spec_values(s); vol = volume(s)
    bands = [dict(b) for b in BANDS]
    bands[0]['fraction'] = p['co2_max']; bands[0]['kpa'] = p['co2_max']*p['P_Pa']/1000.0
    return dict(schema=SCHEMA, version=VERSION, system='RING_A_CABIN_CO2',
                notice='SIMULATION: an engineering model of ring A\'s cabin CO2. PROTOTYPE values are labelled; nothing here is canon.',
                params=p, binding=BINDING, fields={k: list(v) for k, v in FIELDS.items()}, operations=OPERATIONS, refusals=REFUSALS,
                bands=bands, tolerance=TOLERANCE,
                sources=dict(pressure=dict(value=sv['pressure_kpa'], unit='kPa', status=sv['pressure_status'], source_ref='cabin_atmosphere'),
                             control=dict(target=sv['co2_target'], max=sv['co2_max'], status=sv['control_status'], source_ref='cabin_atmosphere_control'),
                             co2_rate=co2_rate(reg), volume=vol, prototype=PROTOTYPE),
                proof=dict(events=[list(e) for e in PROOF_EVENTS], end_s=PROOF_END_S, every_s=PROOF_EVERY_S, dt_s=PROOF_DT_S,
                           start=PROOF_START, initial='steady state of the removing unit', checkpoints=checkpoints(p)))


def write(root, out):
    import life_support
    import spec
    Path(out).write_text(json.dumps(contract(spec.load(Path(root))[0], life_support.load(Path(root))), separators=(',', ':'))+'\n')    # compact: the play download has a byte budget


def main(argv):
    c = contract(); p = c['params']
    print(f"Ring A free gas volume {p['V_m3']:.1f} m3 (PROTOTYPE; {c['sources']['volume']['parts']}), n {p['n_mol']:.0f} mol")
    print(f"unit effective scrubbed flow k {p['k_m3_s']*3600:.1f} m3/h (rated for {PROTOTYPE['unit_rated_occupants']['value']} at the target)")
    st = start(p); r = readout(st, p)
    print(f"steady state with {p['occupants']} occupants: {100*r['x']:.3f} % ({r['pp_kpa']:.3f} kPa)")
    for name, x0, x1 in (('steady -> target', r['x'], p['co2_target']), ('target -> control max', p['co2_target'], p['co2_max'])):
        print(f"  unit off, {name}: {hours_between(p, x0, x1):.2f} h")
    for b in c['bands']:
        x = b['kpa']*1000.0/p['P_Pa']
        print(f"  {b['id']:8s} {b['kpa']:.2f} kPa = {100*x:.3f} % here; from the steady state {hours_between(p, r['x'], x):.1f} h with no removal")
    print(f"checkpoints: {len(c['proof']['checkpoints'])}, last x {100*c['proof']['checkpoints'][-1]['x']:.4f} %")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
