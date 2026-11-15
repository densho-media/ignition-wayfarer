"""SYS-003 ring services (Deadship Phases 2C and 3): both habitat rings' cabin heat, water vapour and CO2, the cold-loop chain that cools
them, the electrical buses and stores that power it, and the line-replaceable parts it is made of. Standard library only.

A reusable engineering state: it knows nothing of games, scenarios, input or scores. Consumers switch equipment, isolate it, move parts
between slots, stores and carriers, set the crew in each ring and operate the electrical switchboard; they read the readouts. Godot repeats
`step` (godot/scripts/systems/ring_services.gd) and must reproduce `checkpoints()` within TOLERANCE before anything is shown.

Scope. One well-mixed air volume per ring: ring A's nine compartments (ring_air) summed, 466.36 m3, and ring B its mirror. That is
SYS-001's resolution (cabin_air), right while every door stands at its normal state with the ventilation running (ring_air.well_mixed_gap);
compartment-level transport stays SYS-002's job. The rings share no air: the crew-tube hatches and the despun vestibule are closed
between them, and only people and carried parts cross (through the trunk, in a stated transfer time).

Physics per ring (state: cabin temperature T, vapour mass m_w, CO2 mass m_c):
    C dT/dt   = n q_sens + P_ring - Q_s
    dm_w/dt   = n g_w - mdot_cond
    dm_c/dt   = n g_c - k m_c / V            (k only while the CO2 unit runs: powered, not isolated, its fan installed and working)
C the cabin's participating heat capacity (air plus the furnishings and inner structure that follow the air over hours, PROTOTYPE),
n the crew in the ring, q_sens, g_w, g_c the sensible heat, water vapour and CO2 per person (NASA BVAD 2022; the CO2 rate is the
owner's 1.0 kg/day, as SYS-001 and SYS-002), P_ring the electrical power of the ring's running loads (all of it ends as heat in the
cabin), Q_s the sensible heat the cabin heat exchanger (CHX) removes and mdot_cond the water it condenses.

The cooling chain. The CHX fan draws cabin air over a coil carrying the ring's internal coolant, which the ring's pumps P1 and P2 move
(each a part). The coolant is chilled by a heat pump that rejects the heat and its own work into the ring's cold loop at 320 K
(thermal.loops.cold, WORKING): cabin heat at about 297 K cannot reach a 320 K radiator without work (thermal.loops.separation_rule,
BASELINE). The heat pump runs at the spec's second-law efficiency (thermal.loops.architecture, 0.5 of Carnot):
    COP = eta_II T_s / (T_rad - T_s)       its electrical draw W = Q_coolant / COP, rejected heat Q_coolant + W
The coil is a counterflow exchanger, effectiveness by epsilon-NTU with a fixed UA: Q_s = eps C_min (T - T_s), C_air = rho cp Q_air,
C_cool = mdot cp_w (pumps running x each pump's flow). One pump halves C_cool: less heat leaves the cabin and the coolant returns warmer,
so the coil's mean surface temperature rises toward the cabin's dew point and condensation falls. Condensation:
    mdot_cond = Q_air eps max(0, rho_v - rho_v,sat(T_coil)),   T_coil = T_s + (Q_s + h_fg mdot_cond) / (2 C_cool)
solved by a fixed number of substitutions (Godot repeats them). The heat pump's capacity is finite: past it, the supply temperature
rises until the heat it takes equals its capacity. Without its power the coil carries no heat at all.

Electricity (PROTOTYPE architecture on the spec's two generators and buses A and B, BASELINE): generator G1 feeds bus A and G2 bus B
while the fusion plant runs; the main battery (2 MWh usable, WORKING) feeds each bus through its own converter (BC-A, BC-B, each a part
with a power rating); a tie breaker joins the buses; each ring's survival packs (survival_reserve, capacity OPEN: PROTOTYPE) carry only
that ring's survival loads (the spec's LIFE_SUPPORT, FLIGHT_COMPUTER, COMMS, EMERGENCY_LIGHTING, CRITICAL_PUMPS_VALVES) when their bus
is dead. A bus whose demand exceeds its sources' rating trips (its breaker opens) and stays dead until it is reset. Every load draws
its power while it runs; every watt drawn in a ring is heat in that ring. A load without power does not run, whatever its parts.

Steps. Switch states, which loads run and where their power comes from are settled at each step's start and held over the step; the
continuous state (temperatures, vapour, CO2, the stores and every ledger total) advances by one classical Runge-Kutta step, so the
heat pump's draw follows the cabin through the step. Ledgers (each integrated by the same step, so closing them checks the step):
    water   m_w + condensed            = m_w0 + generated              (per ring)
    CO2     m_c + removed              = m_c0 + generated              (per ring)
    heat    C (T - T0) + removed       = crew sensible + electrical    (per ring, the cabin)
    coolant rejected                   = removed + latent + heat-pump work
    energy  battery drawn + packs drawn + generated = loads served;  battery E0 - E = battery drawn
    parts   every part is in exactly one place (a slot, a store, a carrier); none is made or lost

    python3 src/wayfarer/ring_services.py      # the parameters, the normal steady state and the single-fault cases
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

FILE = 'wf_ring_services.json'
SCHEMA = 'WF_RING_SERVICES'
VERSION = 1
TOLERANCE = {'rel': 1e-9, 'abs': 1e-9}
RINGS = ('A', 'B')
BUSES = ('A', 'B')
R = 8.314462618           # J/(mol K)
R_V = 461.5               # J/(kg K), water vapour
M_CO2 = 0.04401           # kg/mol
H_FG = 2.454e6            # J/kg, latent heat of vaporization of water at 20 C
CP_AIR = 1005.0           # J/(kg K)
CP_W = 4186.0             # J/(kg K), the coolant (water)
M_AIR = 0.02897           # kg/mol
ITERATIONS = 4            # substitutions of the coil temperature, condensation and the heat pump's capacity
DAY = 86400.0

# External references (not Wayfarer canon; applied as published)
BVAD = dict(
    sensible_W=6.308e6/DAY, latent_W=6.118e6/DAY, vapour_kg_s=2.27/DAY,
    reference='NASA/TP-2015-218570/REV2 Life Support Baseline Values and Assumptions Document (2022), Table 3-21 (sensible 6.308, '
              'latent 6.118 MJ/CM-d), Table 4-21 (crew latent humidity condensate 2.27 kg/CM-d nominal), Table 4-1 (cabin 291-300 K, '
              'relative humidity 25-75 %, dew point 271-295 K, NASA HIDH 2014).',
    note='The vapour the crew give off is taken as the condensate load the humidity system must remove; its latent heat is carried by the '
         'vapour and released in the coil, not in the cabin.')
LIMITS = dict(T_max_K=300.15, T_min_K=291.15, rh_limit=0.75, status='EXTERNAL REFERENCE',
              reference='NASA HIDH (2014) via BVAD Table 4-1: air temperature 291.15-300.15 K, relative humidity 25-75 %',
              note='Habitability limits for planning, not injury thresholds. The relative-humidity control band 0.40-0.50 is the spec\'s '
                   '(habitat.atmosphere.control, WORKING).')

PROTOTYPE = {
    'heat_capacity_J_K': dict(value=4.4e6, unit='J/K', status='PROTOTYPE',
                              note='Cabin air (about 0.44 MJ/K) plus about 4.4 t of aluminium-equivalent furnishings, panels and inner '
                                   'structure in good contact with the air over hours.'),
    'T0_K': dict(value=296.0, unit='K', status='PROTOTYPE', note='Cabin start temperature (BVAD nominal 296 K).'),
    'rh0': dict(value=0.42, unit='-', status='PROTOTYPE', note='Start relative humidity, inside the spec\'s 0.40-0.50 band.'),
    'chx_air_m3_s': dict(value=1.0, unit='m3/s', status='PROTOTYPE',
                         note='Air through the cabin heat exchanger, about 2,100 cfm: the order of several ISS common cabin air assemblies.'),
    'chx_UA_W_K': dict(value=1500.0, unit='W/K', status='PROTOTYPE', note='The coil\'s conductance (counterflow).'),
    'pump_kg_s': dict(value=0.2, unit='kg/s', status='PROTOTYPE', note='Coolant flow of one pump; two pumps per ring, each a part.'),
    'T_supply_K': dict(value=277.15, unit='K', status='PROTOTYPE', note='Chilled coolant supply (4 C, the ISS low-temperature loop).'),
    'T_supply_economy_K': dict(value=285.15, unit='K', status='PROTOTYPE',
                               note='The heat pump\'s economy setpoint (12 C supply): a better COP and less work, but a warmer coil that '
                                    'condenses less, so the cabin dries less. The two setpoints are the only ones the controller offers.'),
    'T_set_K': dict(value=296.15, unit='K', status='PROTOTYPE', note='Cabin temperature setpoint (23 C; BVAD nominal 296 K).'),
    'control_band_K': dict(value=2.0, unit='K', status='PROTOTYPE',
                           note='The temperature control valve sends a share f = 0.5 + (T - T_set) / band of the fan\'s air over the coil '
                                '(the rest bypasses it), between f_min and 1: a proportional controller, as the ISS cabin air assembly\'s '
                                'temperature control valve.'),
    'coil_min_fraction': dict(value=0.15, unit='-', status='PROTOTYPE',
                              note='The share of air the valve always sends over the coil, so the coil keeps condensing when little cooling '
                                   'is needed.'),
    'heat_pump_W': dict(value=16000.0, unit='W', status='PROTOTYPE', note='The ring heat pump\'s capacity (heat taken from the coolant).'),
    'cold_loop_K': dict(value=320.0, unit='K', status='WORKING', note='thermal.loops.cold.temperature_K'),
    'heat_pump_eta': dict(value=0.5, unit='-', status='WORKING', note='thermal.loops.architecture.heat_pump_second_law_efficiency'),
    'battery_converter_W': dict(value=40000.0, unit='W', status='PROTOTYPE',
                                note='Each battery converter (BC-A, BC-B) carries its bus up to this power.'),
    'generator_W': dict(value=80000.0, unit='W', status='PROTOTYPE',
                        note='Each generator\'s hotel-mode output to its bus while the fusion plant runs (power.rating OPEN).'),
    'pack_Wh': dict(value=8000.0, unit='Wh', status='PROTOTYPE',
                    note='Each ring\'s survival packs together (survival_reserve.capacity OPEN): they carry only the ring\'s survival loads.'),
    'ship_load_W': dict(value={'A': 15000.0, 'B': 15000.0}, unit='W', status='PROTOTYPE',
                        note='Each bus\'s non-habitat ship services (flight computers, communications, propellant conditioning, drive '
                             'standby), lumped. The whole-ship load is OPEN (power.rating); these are scenario-scale placeholders.'),
}

# The equipment of each ring: (id, title, watts, bus, survival, nonessential, parts needed by slot). PROTOTYPE values with an ISS basis.
EQUIPMENT = [
    dict(id='CO2', title='CO2 removal unit', W=700.0, bus='A', survival=True, shed=False, slots=['CO2.FAN'],
         note='A regenerable sorbent unit with its process-air fan (ISS CDRA class, about 700 W with bed heaters).'),
    dict(id='CHX', title='Cabin heat exchanger fan', W=150.0, bus='B', survival=True, shed=False, slots=['CHX.FAN'],
         note='The fan that draws cabin air over the coil (ISS CCAA class).'),
    dict(id='P1', title='Coolant pump 1', W=150.0, bus='A', survival=True, shed=False, slots=['P1.PUMP'], note='Internal coolant loop.'),
    dict(id='P2', title='Coolant pump 2', W=150.0, bus='B', survival=True, shed=False, slots=['P2.PUMP'], note='Internal coolant loop.'),
    dict(id='HP', title='Heat pump (to the 320 K cold loop)', W=0.0, bus='A', survival=False, shed=False, slots=[],
         note='Its draw is computed: heat taken over its COP.'),
    dict(id='TCC', title='Trace-contaminant control', W=150.0, bus='B', survival=True, shed=False, slots=[], note='ISS TCCS class.'),
    dict(id='VENT', title='Intermodule ventilation fans', W=120.0, bus='A', survival=True, shed=False, slots=[], note='Four duct fans.'),
    dict(id='AV', title='Ring avionics and comms', W=500.0, bus='B', survival=True, shed=False, slots=[], note='Displays, network, intercom.'),
    dict(id='LIGHT', title='Cabin lighting', W=1200.0, bus='A', survival=False, shed=True, slots=[], note='Emergency lighting is in AV.'),
    dict(id='GALLEY', title='Galley', W=1500.0, bus='B', survival=False, shed=True, slots=[], note='Averaged over the day.'),
    dict(id='LAB', title='Laboratory and workshop', W=2000.0, bus='A', survival=False, shed=True, slots=[], note=''),
    dict(id='GARDEN', title='Garden lights', W=6000.0, bus='B', survival=False, shed=True, slots=[],
         note='Plant lighting: the largest discretionary load.'),
]
# Line-replaceable unit families: a part fits a slot only with the same interface.
LRU = {
    'FAN_ECLSS': dict(title='ECLSS process fan (common to the CO2 unit and the cabin heat exchanger)',
                      note='One fan family for both machines (commonality cuts the spares a ship must carry): PROTOTYPE.'),
    'PUMP_ITCS': dict(title='Internal coolant pump', note='Both pumps of either ring.'),
    'CONVERTER': dict(title='Battery converter', note='BC-A and BC-B are the same unit.'),
}
SLOTS = {'CO2.FAN': 'FAN_ECLSS', 'CHX.FAN': 'FAN_ECLSS', 'P1.PUMP': 'PUMP_ITCS', 'P2.PUMP': 'PUMP_ITCS'}
CONVERTER_SLOTS = {'BC-A': 'CONVERTER', 'BC-B': 'CONVERTER'}


def params(s=None, reg=None):
    """Everything step() needs, from the spec and the life-support registry; the rest is PROTOTYPE above."""
    import cabin_air
    import ring_air
    if s is None:
        import spec
        s = spec.load()[0]
    if reg is None:
        import life_support
        reg = life_support.load()
    a = s['habitat']['atmosphere']; L = s['thermal']['loops']; st = s['power']['storage']
    V = sum(n['V_m3'] for n in ring_air.topology(s)['nodes'])
    base = cabin_air.params(s, reg)
    pv = {k: v['value'] for k, v in PROTOTYPE.items()}
    return dict(V_m3=V, P_Pa=float(a['cabin_pressure_kpa'])*1000.0, co2_target=float(a['control']['co2_target_fraction']),
                co2_max=float(a['control']['co2_max_fraction']), rh_min=float(a['control']['rh_min']), rh_max=float(a['control']['rh_max']),
                g_c=base['per_person_kg_s'], k_m3_s=base['k_m3_s'], q_sens=BVAD['sensible_W'], g_w=BVAD['vapour_kg_s'],
                T_rad=float(L['cold']['temperature_K']), eta_hp=float(L['architecture']['heat_pump_second_law_efficiency']),
                battery_Wh=float(st['main_battery']['usable_energy_Wh']), pulse_Wh=float(st['pulse_bank']['energy_Wh']),
                survival_loads=list(st['survival_reserve']['loads']),
                C=pv['heat_capacity_J_K'], T0=pv['T0_K'], rh0=pv['rh0'], Q_air=pv['chx_air_m3_s'], UA=pv['chx_UA_W_K'],
                pump=pv['pump_kg_s'], T_s=pv['T_supply_K'], T_s_economy=pv['T_supply_economy_K'], T_set=pv['T_set_K'], band=pv['control_band_K'], f_min=pv['coil_min_fraction'], hp_max=pv['heat_pump_W'], conv_W=pv['battery_converter_W'],
                gen_W=pv['generator_W'], pack_Wh=pv['pack_Wh'], ship_W=dict(pv['ship_load_W']), T_max=LIMITS['T_max_K'],
                T_min=LIMITS['T_min_K'], rh_limit=LIMITS['rh_limit'],
                equipment=[dict(id=e['id'], W=e['W'], bus=e['bus'], survival=e['survival'], shed=e['shed'], slots=list(e['slots']))
                           for e in EQUIPMENT])


# ---------- thermodynamics -----------------------------------------------------------------------------------------------------------

def p_sat(T):
    """Saturation vapour pressure over water (Pa), Magnus form with Alduchov and Eskridge (1996) coefficients."""
    t = T - 273.15
    return 610.94*math.exp(17.625*t/(t + 243.04))


def rho_sat(T):
    return p_sat(T)/(R_V*T)


def rho_air(p, T):
    return p['P_Pa']*M_AIR/(R*T)


def rh(p, T, m_w):
    return m_w/p['V_m3']*R_V*T/p_sat(T)


def x_co2(p, T, m_c):
    return m_c/M_CO2/(p['P_Pa']*p['V_m3']/(R*T))


def m_w_at(p, T, rh_):
    return rh_*p_sat(T)/(R_V*T)*p['V_m3']


def m_c_at(p, T, x):
    return x*p['P_Pa']*p['V_m3']/(R*T)*M_CO2


def eps_counterflow(ntu, cr):
    if cr > 0.999999:
        return ntu/(1.0 + ntu)
    e = math.exp(-ntu*(1.0 - cr))
    return (1.0 - e)/(1.0 - cr*e)


def coil(p, T, m_w, fan, pumps, hp_on, T_s0=None):
    """The cabin heat exchanger now: sensible heat removed Q_s (W), water condensed (kg/s), heat taken by the heat pump (W), its work (W),
    the supply and mean coil temperatures (K)."""
    zero = dict(Q_s=0.0, cond=0.0, Q_hp=0.0, W_hp=0.0, T_s=T, T_coil=T, f=0.0)
    if not fan or pumps <= 0 or not hp_on:
        return zero
    f = min(max(0.5 + (T - p['T_set'])/p['band'], p['f_min']), 1.0)       # the temperature control valve
    Qa = f*p['Q_air']
    Ca = rho_air(p, T)*CP_AIR*Qa
    Cc = pumps*p['pump']*CP_W
    cmin = min(Ca, Cc); cmax = max(Ca, Cc)
    eps = eps_counterflow(p['UA']/cmin, cmin/cmax)
    rho_v = m_w/p['V_m3']
    T_s0 = p['T_s'] if T_s0 is None else T_s0
    T_s = T_s0; cond = 0.0; Q_s = 0.0; T_coil = T_s
    for _ in range(ITERATIONS):
        Q_s = eps*cmin*max(T - T_s, 0.0)
        latent = H_FG*cond
        if Q_s + latent > p['hp_max']:
            # past the heat pump's capacity the supply warms until it takes no more than its capacity
            T_s = max(T_s0, T - max(p['hp_max'] - latent, 0.0)/(eps*cmin))
            Q_s = eps*cmin*max(T - T_s, 0.0)
        T_coil = T_s + (Q_s + latent)/(2.0*Cc)
        cond = Qa*eps*max(rho_v - rho_sat(T_coil), 0.0)
    Q_hp = Q_s + H_FG*cond
    cop = p['eta_hp']*T_s/(p['T_rad'] - T_s)
    return dict(Q_s=Q_s, cond=cond, Q_hp=Q_hp, W_hp=Q_hp/cop, T_s=T_s, T_coil=T_coil, f=f)


# ---------- state -------------------------------------------------------------------------------------------------------------------------

def start(p, occupants=None, fusion=True):
    """Both rings at the start temperature and humidity, CO2 at the running unit's steady state for their crew; every machine on and
    whole; the fusion plant running; the battery full; every switch closed but the bus tie."""
    occ = dict(occupants or {'A': 6, 'B': 0})
    ring = {}
    for r in RINGS:
        T = p['T0']
        x = occ[r]*p['g_c']/p['k_m3_s']*R*T/(p['P_Pa']*M_CO2) if occ[r] else 0.0004
        ring[r] = dict(T=T, m_w=m_w_at(p, T, p['rh0']), m_c=m_c_at(p, T, x), economy=False, on={e['id']: True for e in p['equipment']},
                       isolated={e['id']: False for e in p['equipment']})
    parts = {}
    for r in RINGS:
        for slot, lru in SLOTS.items():
            parts[f'{r}.{slot}'] = dict(lru=lru, at=f'{r}.{slot}', ok=True)
    for slot, lru in CONVERTER_SLOTS.items():
        parts[slot] = dict(lru=lru, at=slot, ok=True)
    st = dict(t_s=0.0, ring=ring, occ=occ, parts=parts, fusion=bool(fusion), gen={'A': True, 'B': True}, tie=False,
              breaker={'A': True, 'B': True}, conv_on={'A': True, 'B': True}, E=p['battery_Wh']*3600.0,
              pack={r: p['pack_Wh']*3600.0 for r in RINGS}, log=[], trips=[])
    st['E0'] = st['E']; st['pack0'] = dict(st['pack']); st['pulse_J'] = 0.0
    st['acc'] = {k: 0.0 for k in ACC_KEYS}
    st['init'] = {r: dict(T=ring[r]['T'], m_w=ring[r]['m_w'], m_c=ring[r]['m_c']) for r in RINGS}
    return st


ACC_KEYS = ([f'{r}.{k}' for r in RINGS for k in ('w_gen', 'w_cond', 'c_gen', 'c_rem', 'q_crew', 'q_elec', 'q_rem', 'q_lat', 'w_hp',
                                                   'rejected', 't_hot', 't_rh', 't_co2', 't_wet')]
            + ['E_batt', 'E_gen', 'E_pack.A', 'E_pack.B', 'E_served', 'E_unserved'])


def slot_ok(st, slot):
    """A slot works when a part of its own family is installed there and that part is whole."""
    for part in st['parts'].values():
        if part['at'] == slot:
            return part['ok'] and part['lru'] == (SLOTS.get(slot.split('.', 1)[1]) if slot[:2] in ('A.', 'B.') else CONVERTER_SLOTS.get(slot))
    return False


def where(st, part_id):
    return st['parts'][part_id]['at']


def move_part(st, part_id, to):
    """Move a part: remove it from a slot, take it to a store or a carrier, or install it in a slot. Refusals return the reason."""
    part = st['parts'].get(part_id)
    if part is None:
        return 'no such part'
    if to in SLOTS_ALL():
        fam = SLOTS_ALL()[to]
        if fam != part['lru']:
            return f'{part_id} does not fit {to}: {LRU[part["lru"]]["title"]} against {LRU[fam]["title"]}'
        if any(q['at'] == to for q in st['parts'].values()):
            return f'{to} already holds a part'
    part['at'] = to
    st['log'].append((st['t_s'], 'part', part_id, to))
    return ''


def SLOTS_ALL():
    out = {f'{r}.{s}': f for r in RINGS for s, f in SLOTS.items()}
    out.update(CONVERTER_SLOTS)
    return out


def fail_part(st, part_id):
    st['parts'][part_id]['ok'] = False
    st['log'].append((st['t_s'], 'fail', part_id, ''))


def set_on(st, ring, eq, on):
    st['ring'][ring]['on'][eq] = bool(on)
    st['log'].append((st['t_s'], 'switch', f'{ring}.{eq}', bool(on)))


def set_isolated(st, ring, eq, isolated):
    st['ring'][ring]['isolated'][eq] = bool(isolated)
    st['log'].append((st['t_s'], 'isolate', f'{ring}.{eq}', bool(isolated)))


def set_occupants(st, occ):
    st['occ'] = dict(occ)
    st['log'].append((st['t_s'], 'occupants', '', dict(occ)))


def set_tie(st, closed):
    st['tie'] = bool(closed)
    st['log'].append((st['t_s'], 'tie', '', bool(closed)))


def reset_breaker(st, bus):
    st['breaker'][bus] = True
    st['log'].append((st['t_s'], 'breaker', bus, True))


def set_converter(st, bus, on):
    st['conv_on'][bus] = bool(on)
    st['log'].append((st['t_s'], 'converter', bus, bool(on)))


def set_economy(st, ring, on):
    """The ring heat pump's supply setpoint: normal or economy (T_supply_economy_K)."""
    st['ring'][ring]['economy'] = bool(on)
    st['log'].append((st['t_s'], 'economy', ring, bool(on)))


def supply(p, st, ring):
    return p['T_s_economy'] if st['ring'][ring]['economy'] else p['T_s']


def charge_pulse(st, p):
    """Charge the drive's pulse bank from the main battery for a plant restart (pulse_bank.energy_Wh). Refused (False) when the battery
    holds less."""
    need = p['pulse_Wh']*3600.0
    if st['E'] < need:
        return False
    st['E'] -= need; st['pulse_J'] += need
    st['log'].append((st['t_s'], 'pulse', '', need))
    return True


def set_fusion(st, on):
    st['fusion'] = bool(on)
    st['log'].append((st['t_s'], 'fusion', '', bool(on)))


# ---------- the switchboard ------------------------------------------------------------------------------------------------------------

def equipment_ready(p, st, ring, e):
    """A machine can run (given power) when it is switched on, not isolated and every slot it needs works."""
    rr = st['ring'][ring]
    return rr['on'][e['id']] and not rr['isolated'][e['id']] and all(slot_ok(st, f'{ring}.{s}') for s in e['slots'])


def sources(p, st):
    """What can feed each bus now: generator and battery converter ratings (W). The battery feeds only while it holds energy."""
    out = {}
    for b in BUSES:
        g = p['gen_W'] if st['fusion'] and st['gen'][b] else 0.0
        c = p['conv_W'] if st['conv_on'][b] and slot_ok(st, f'BC-{b}') and st['E'] > 0.0 else 0.0
        out[b] = dict(gen=g, conv=c)
    return out


def demand(p, st, coils):
    """Each bus's demand now (W) if every ready machine runs: the ship services plus the rings' loads on that bus; the heat pump's draw
    from the coil state at the step's start."""
    d = {b: p['ship_W'][b] for b in BUSES}
    for r in RINGS:
        for e in p['equipment']:
            if equipment_ready(p, st, r, e):
                d[e['bus']] += coils[r]['W_hp'] if e['id'] == 'HP' else e['W']
    return d


def settle(p, st):
    """The switchboard at a step's start: which buses are live (and from what), which loads run and from which supply. A live bus whose
    demand exceeds its sources trips. Returns the plan the step holds."""
    coils = {}
    for r in RINGS:
        rr = st['ring'][r]
        pumps = sum(1 for e in p['equipment'] if e['id'] in ('P1', 'P2') and equipment_ready(p, st, r, e))
        fan = equipment_ready(p, st, r, eq(p, 'CHX'))
        hp = equipment_ready(p, st, r, eq(p, 'HP'))
        coils[r] = coil(p, rr['T'], rr['m_w'], fan, pumps, hp, supply(p, st, r))
    src = sources(p, st)
    dem = demand(p, st, coils)
    live = {}
    groups = [('A', 'B')] if st['tie'] else [('A',), ('B',)]
    for g in groups:
        cap = sum(src[b]['gen'] + src[b]['conv'] for b in g if st['breaker'][b])
        need = sum(dem[b] for b in g)
        closed = [b for b in g if st['breaker'][b]]
        if not closed or cap <= 0.0:
            for b in g:
                live[b] = False
            continue
        if need > cap + 1e-9:
            for b in closed:
                st['breaker'][b] = False
                st['trips'].append((st['t_s'], b, need, cap))
                st['log'].append((st['t_s'], 'trip', b, [need, cap]))
            for b in g:
                live[b] = False
            continue
        for b in g:
            live[b] = st['breaker'][b] and (st['tie'] or src[b]['gen'] + src[b]['conv'] > 0.0)
        if st['tie']:
            for b in g:
                live[b] = True
    run = {}
    for r in RINGS:
        run[r] = {}
        for e in p['equipment']:
            if not equipment_ready(p, st, r, e):
                run[r][e['id']] = None
            elif live[e['bus']]:
                run[r][e['id']] = 'BUS'
            elif e['survival'] and st['pack'][r] > 0.0:
                run[r][e['id']] = 'PACK'
            else:
                run[r][e['id']] = 'DARK'                  # wanted but unpowered: unserved
    gen_share = {}
    for g in groups:
        gsum = sum(src[b]['gen'] for b in g if live.get(b))
        gen_share[g] = gsum
    return dict(live=live, run=run, src=src, groups=groups, gen=gen_share)


def eq(p, i):
    return next(e for e in p['equipment'] if e['id'] == i)


# ---------- the step ----------------------------------------------------------------------------------------------------------------------

def derivs(p, st, plan, y):
    """d/dt of the continuous state y (see pack_y) with the plan held."""
    dy = [0.0]*len(y)
    bus_load = {b: p['ship_W'][b] if plan['live'][b] else 0.0 for b in BUSES}
    pack_load = {r: 0.0 for r in RINGS}
    unserved = 0.0 if all(plan['live'][b] for b in BUSES) else sum(p['ship_W'][b] for b in BUSES if not plan['live'][b])
    for k, r in enumerate(RINGS):
        o = k*Y_RING
        T, m_w, m_c = y[o], y[o + 1], y[o + 2]
        run = plan['run'][r]
        powered = lambda i: run[i] in ('BUS', 'PACK')
        pumps = (1 if powered('P1') else 0) + (1 if powered('P2') else 0)
        c = coil(p, T, m_w, powered('CHX'), pumps, powered('HP'), supply(p, st, r))
        elec = 0.0
        for e in p['equipment']:
            s = run[e['id']]
            w = c['W_hp'] if e['id'] == 'HP' else e['W']
            if s == 'BUS':
                bus_load[e['bus']] += w
                if e['id'] != 'HP':
                    elec += w
            elif s == 'PACK':
                pack_load[r] += w
                if e['id'] != 'HP':
                    elec += w
            elif s == 'DARK':
                unserved += w
        n = st['occ'][r]
        qc = n*p['q_sens']
        k_rem = p['k_m3_s'] if powered('CO2') else 0.0
        dy[o] = (qc + elec - c['Q_s'])/p['C']
        dy[o + 1] = n*p['g_w'] - c['cond']
        dy[o + 2] = n*p['g_c'] - k_rem*m_c/p['V_m3']
        dy[o + 3] = n*p['g_w']                         # water generated
        dy[o + 4] = c['cond']                          # water condensed
        dy[o + 5] = n*p['g_c']                         # CO2 generated
        dy[o + 6] = k_rem*m_c/p['V_m3']                # CO2 removed
        dy[o + 7] = qc                                 # crew sensible heat
        dy[o + 8] = elec                               # electrical heat in the cabin
        dy[o + 9] = c['Q_s']                           # sensible heat removed
        dy[o + 10] = H_FG*c['cond']                    # latent heat into the coolant
        dy[o + 11] = c['W_hp'] if powered('HP') else 0.0
        dy[o + 12] = c['Q_hp'] + (c['W_hp'] if powered('HP') else 0.0)   # rejected to the cold loop
        x = x_co2(p, T, m_c)
        dy[o + 13] = 1.0 if T > p['T_max'] else 0.0                   # time above the temperature limit
        dy[o + 14] = 1.0 if rh(p, T, m_w) > p['rh_max'] else 0.0      # time above the humidity band
        dy[o + 15] = 1.0 if x > p['co2_max'] else 0.0                 # time above the CO2 control limit
        dy[o + 16] = 1.0 if rh(p, T, m_w) > p['rh_limit'] else 0.0    # time above the humidity limit
    # electrical: generators first, the battery for the rest of each live group, the packs for their rings
    E_gen = 0.0; E_batt = 0.0
    for g in plan['groups']:
        if not all(plan['live'][b] for b in g):
            continue
        load = sum(bus_load[b] for b in g)
        gen = min(load, plan['gen'][g])
        E_gen += gen
        E_batt += load - gen
    o = Y_RING*len(RINGS)
    dy[o] = -E_batt                                    # battery energy (J)
    dy[o + 1] = -pack_load['A']
    dy[o + 2] = -pack_load['B']
    dy[o + 3] = E_batt
    dy[o + 4] = E_gen
    dy[o + 5] = pack_load['A']
    dy[o + 6] = pack_load['B']
    dy[o + 7] = E_gen + E_batt + pack_load['A'] + pack_load['B']   # served
    dy[o + 8] = unserved
    return dy


Y_RING = 17
ACC_RING = ('w_gen', 'w_cond', 'c_gen', 'c_rem', 'q_crew', 'q_elec', 'q_rem', 'q_lat', 'w_hp', 'rejected', 't_hot', 't_rh', 't_co2', 't_wet')
ACC_POWER = ('E_batt', 'E_gen', 'E_pack.A', 'E_pack.B', 'E_served', 'E_unserved')


def pack_y(st):
    y = []
    for r in RINGS:
        rr = st['ring'][r]
        y += [rr['T'], rr['m_w'], rr['m_c']] + [st['acc'][f'{r}.{k}'] for k in ACC_RING]
    y += [st['E'], st['pack']['A'], st['pack']['B']] + [st['acc'][k] for k in ACC_POWER]
    return y


def unpack_y(st, y):
    for k, r in enumerate(RINGS):
        o = k*Y_RING
        rr = st['ring'][r]
        rr['T'], rr['m_w'], rr['m_c'] = y[o], y[o + 1], y[o + 2]
        for j, a in enumerate(ACC_RING):
            st['acc'][f'{r}.{a}'] = y[o + 3 + j]
    o = Y_RING*len(RINGS)
    st['E'], st['pack']['A'], st['pack']['B'] = y[o], y[o + 1], y[o + 2]
    for j, a in enumerate(ACC_POWER):
        st['acc'][a] = y[o + 3 + j]


def step(st, p, dt):
    """Advance dt seconds: settle the switchboard, then one Runge-Kutta step of the continuous state. A store that empties within the
    step is held at zero and what it could not give is counted as unserved; its loads drop at the next step."""
    plan = settle(p, st)
    y = pack_y(st)
    k1 = derivs(p, st, plan, y)
    k2 = derivs(p, st, plan, [y[i] + 0.5*dt*k1[i] for i in range(len(y))])
    k3 = derivs(p, st, plan, [y[i] + 0.5*dt*k2[i] for i in range(len(y))])
    k4 = derivs(p, st, plan, [y[i] + dt*k3[i] for i in range(len(y))])
    out = [y[i] + dt/6.0*(k1[i] + 2.0*k2[i] + 2.0*k3[i] + k4[i]) for i in range(len(y))]
    o = Y_RING*len(RINGS)
    for j in range(3):                                 # battery, pack A, pack B
        if out[o + j] < 0.0:
            short = -out[o + j]
            out[o + j] = 0.0
            out[o + 3 + (0 if j == 0 else 1 + j)] -= short      # it gave only what it held
            out[o + 7] -= short                                 # served less
            out[o + 8] += short                                 # unserved more
    unpack_y(st, out)
    st['t_s'] += dt
    st['plan'] = plan
    return st


# ---------- ledgers and readouts ---------------------------------------------------------------------------------------------------------

def ledgers(st, p):
    """Every inventory's error (should be 0 to rounding)."""
    out = {}
    a = st['acc']
    for r in RINGS:
        rr = st['ring'][r]; i0 = st['init'][r]
        out[f'{r}.water_kg'] = (rr['m_w'] + a[f'{r}.w_cond']) - (i0['m_w'] + a[f'{r}.w_gen'])
        out[f'{r}.co2_kg'] = (rr['m_c'] + a[f'{r}.c_rem']) - (i0['m_c'] + a[f'{r}.c_gen'])
        out[f'{r}.heat_J'] = (p['C']*(rr['T'] - i0['T']) + a[f'{r}.q_rem']) - (a[f'{r}.q_crew'] + a[f'{r}.q_elec'])
        out[f'{r}.coolant_J'] = a[f'{r}.rejected'] - (a[f'{r}.q_rem'] + a[f'{r}.q_lat'] + a[f'{r}.w_hp'])
    out['battery_J'] = (st['E0'] - st['E']) - a['E_batt'] - st['pulse_J']
    out['packs_J'] = sum(st['pack0'][r] - st['pack'][r] for r in RINGS) - (a['E_pack.A'] + a['E_pack.B'])
    out['served_J'] = a['E_served'] - (a['E_gen'] + a['E_batt'] + a['E_pack.A'] + a['E_pack.B'])
    places = [q['at'] for q in st['parts'].values()]
    out['parts'] = 0 if len(places) == len(st['parts']) and all(isinstance(x, str) and x for x in places) else 1
    return out


def readout(st, p):
    """What a panel can show: per ring the cabin, its machines and their supply; the buses and stores."""
    plan = st.get('plan') or settle(p, dict(st, breaker=dict(st['breaker']), trips=list(st['trips']), log=list(st['log'])))
    out = dict(t_s=st['t_s'], rings={}, buses={}, battery_Wh=st['E']/3600.0, battery_frac=st['E']/st['E0'],
               packs_Wh={r: st['pack'][r]/3600.0 for r in RINGS}, tie=st['tie'], fusion=st['fusion'])
    for r in RINGS:
        rr = st['ring'][r]
        pumps = sum(1 for i in ('P1', 'P2') if plan['run'][r][i] in ('BUS', 'PACK'))
        c = coil(p, rr['T'], rr['m_w'], plan['run'][r]['CHX'] in ('BUS', 'PACK'), pumps, plan['run'][r]['HP'] in ('BUS', 'PACK'),
                 supply(p, st, r))
        out['rings'][r] = dict(T_C=rr['T'] - 273.15, rh=rh(p, rr['T'], rr['m_w']), dew_C=dew_point(p, rr['T'], rr['m_w']) - 273.15,
                               co2_pct=100.0*x_co2(p, rr['T'], rr['m_c']), occupants=st['occ'][r], Q_s_W=c['Q_s'],
                               cond_kg_h=c['cond']*3600.0, hp_W=c['W_hp'], T_coil_C=c['T_coil'] - 273.15,
                               run={e['id']: plan['run'][r][e['id']] for e in p['equipment']})
    for b in BUSES:
        out['buses'][b] = dict(live=plan['live'][b], breaker=st['breaker'][b], gen=plan['src'][b]['gen'] > 0.0,
                               converter=plan['src'][b]['conv'] > 0.0)
    return out


def dew_point(p, T, m_w):
    """Dew point (K) of the cabin's vapour, inverse Magnus."""
    e = max(m_w/p['V_m3']*R_V*T, 1e-6)
    lg = math.log(e/610.94)
    return 273.15 + 243.04*lg/(17.625 - lg)


# ---------- proof ------------------------------------------------------------------------------------------------------------------------

PROOF_DT_S = 10.0
PROOF_END_S = 6*3600.0
PROOF_EVERY_S = 1800.0
# The proof run: ring A with six, ring B empty; at 30 min ring A's pump 1 fails, at 1 h its CO2 fan; at 2 h the fusion plant trips (the
# battery carries both buses); at 3 h converter B fails (bus B dead: the survival packs take its survival loads); at 4 h the tie closes
# with the Garden lights, galley, lab shed in both rings; at 5 h ring A's CHX fan moves into its CO2 unit.
PROOF_EVENTS = [
    (1800.0, 'fail', 'A.P1.PUMP'), (3600.0, 'fail', 'A.CO2.FAN'), (7200.0, 'fusion', False), (10800.0, 'fail', 'BC-B'),
    (14400.0, 'shed', 'A'), (14400.0, 'shed', 'B'), (14400.0, 'tie', True), (14400.0, 'reset', 'B'),
    (18000.0, 'move', 'A.CO2.FAN', 'STORE.A'), (18000.0, 'move', 'A.CHX.FAN', 'A.CO2.FAN'),
]


def apply(st, ev):
    k = ev[1]
    if k == 'fail':
        fail_part(st, ev[2])
    elif k == 'fusion':
        set_fusion(st, ev[2])
    elif k == 'shed':
        for e in ('GARDEN', 'GALLEY', 'LAB'):
            set_on(st, ev[2], e, False)
    elif k == 'tie':
        set_tie(st, ev[2])
    elif k == 'reset':
        reset_breaker(st, ev[2])
    elif k == 'move':
        move_part(st, ev[2], ev[3])
    elif k == 'occupants':
        set_occupants(st, ev[2])
    elif k == 'switch':
        set_on(st, ev[2], ev[3], ev[4])
    else:
        raise ValueError(k)


def snapshot(st):
    return dict(t_s=st['t_s'], T={r: st['ring'][r]['T'] for r in RINGS}, m_w={r: st['ring'][r]['m_w'] for r in RINGS},
                m_c={r: st['ring'][r]['m_c'] for r in RINGS}, E=st['E'], pack=dict(st['pack']), acc=dict(st['acc']),
                breaker=dict(st['breaker']))


def checkpoints(p, dt=PROOF_DT_S, events=None):
    st = start(p)
    evs = sorted(PROOF_EVENTS if events is None else events, key=lambda e: e[0])
    out = [snapshot(st)]
    j = 0
    while st['t_s'] < PROOF_END_S - 1e-9:
        while j < len(evs) and evs[j][0] <= st['t_s'] + 1e-9:
            apply(st, evs[j]); j += 1
        step(st, p, dt)
        if abs(st['t_s']/PROOF_EVERY_S - round(st['t_s']/PROOF_EVERY_S)) < 1e-9:
            out.append(snapshot(st))
    return out


def contract(s=None, reg=None):
    p = params(s, reg)
    return dict(schema=SCHEMA, version=VERSION, system='RING_SERVICES',
                notice='SIMULATION: both rings\' cabin heat, humidity and CO2, their cooling chain, the buses and stores, and their parts. '
                       'Architecture and values are PROTOTYPE unless stated; nothing here is canon.',
                params=p, prototype=PROTOTYPE, bvad=BVAD, limits=LIMITS, equipment=EQUIPMENT, lru=LRU, slots=SLOTS,
                converter_slots=CONVERTER_SLOTS, tolerance=TOLERANCE, iterations=ITERATIONS,
                constants=dict(R=R, R_V=R_V, M_CO2=M_CO2, H_FG=H_FG, CP_AIR=CP_AIR, CP_W=CP_W, M_AIR=M_AIR),
                proof=dict(events=[list(e) for e in PROOF_EVENTS], end_s=PROOF_END_S, every_s=PROOF_EVERY_S, dt_s=PROOF_DT_S,
                           checkpoints=checkpoints(p)))


def write(root, out):
    Path(out).write_text(json.dumps(contract(), separators=(',', ':')) + '\n')


def main(argv):
    p = params()
    st = start(p)
    for _ in range(int(6*3600/10)):
        step(st, p, 10.0)
    ro = readout(st, p)
    print(f"V {p['V_m3']:.1f} m3 per ring; C {p['C']/1e6:.2f} MJ/K; per person sensible {p['q_sens']:.1f} W, vapour {p['g_w']*DAY:.2f} kg/d")
    for r in RINGS:
        q = ro['rings'][r]
        print(f"ring {r} after 6 h normal: T {q['T_C']:.2f} C, RH {q['rh']:.3f}, dew {q['dew_C']:.1f} C, CO2 {q['co2_pct']:.3f} %, "
              f"Q_s {q['Q_s_W']:.0f} W, cond {q['cond_kg_h']:.3f} kg/h, heat pump {q['hp_W']:.0f} W, coil {q['T_coil_C']:.1f} C")
    print('ledgers', {k: f'{v:.2e}' for k, v in ledgers(st, p).items()})
    cps = checkpoints(p)
    last = cps[-1]
    print('proof end:', {r: round(last['T'][r] - 273.15, 2) for r in RINGS}, 'battery kWh', round(last['E']/3.6e6, 1), last['breaker'])


if __name__ == '__main__':
    main(sys.argv[1:])
