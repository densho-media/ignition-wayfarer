"""ISSA Phase 1 study: preliminary electrical load model and drive-off generation screen (NONCANON, study only).

Reads the spec (data/wayfarer_3d.toml) and the derived reports it already has; writes nothing outside this folder's results/.
Every load carries an evidence class:
    SPEC      a value in data/wayfarer_3d.toml (its canon_status is printed with it)
    DERIVED   computed here or in an existing report from SPEC values
    PROTO     an existing PROTOTYPE value in the repository (ring_services, life_support study)
    STUDY     an ISSA working assumption with a stated basis (ISS / NASA comparable); a band, never canon
Nothing here changes a parameter. Bands are (low, nominal, high) in watts.

    python3 work/ship-systems-architecture/eps_study.py          # prints the tables, writes results/eps_study.json
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src' / 'wayfarer'))
import spec  # noqa: E402

OUT = Path(__file__).resolve().parent / 'results'
SIGMA = 5.670374419e-8


def band(lo, nom, hi):
    return (float(lo), float(nom), float(hi))


def loads(s):
    """Electrical load items. role: CONT (continuous), INTER (duty-averaged intermittent), PEAK (short peak, store-fed), START."""
    eye = s['eye']; fd = s['forward_defense']['power']; ed = eye['electrical_demand']
    fl = json.loads((ROOT / 'references' / 'p1_fuel_loads.json').read_text())
    cryo_W = fl['cooling']['rejected_W']               # rejected ~= input work for a cryocooler far below Carnot
    crew = s['crew']['rated_occupancy']['value']
    import ring_services as rs
    per_ring_eq = {e['id']: e['W'] for e in rs.EQUIPMENT}
    ring_cont = sum(per_ring_eq[k] for k in ('CO2', 'CHX', 'P1', 'P2', 'TCC', 'VENT', 'AV'))
    ring_hotel = sum(per_ring_eq[k] for k in ('LIGHT', 'GALLEY', 'LAB'))
    o2_kg_day = 0.84 * crew
    L = [
        # id, family, title, band W, role, class, basis
        ('HAB.ECLSS', 'ECLSS', 'Ring air trains (CO2, cabin HX fan, pumps, TCC, ventilation, ring avionics), both rings',
         band(2*ring_cont*0.9, 2*ring_cont, 2*ring_cont*1.5), 'CONT', 'PROTO', 'ring_services.EQUIPMENT (ISS CDRA/CCAA class), x2 rings'),
        ('HAB.O2GEN', 'ECLSS', f'O2 generation by water electrolysis for {crew} ({o2_kg_day:.1f} kg O2/day)',
         band(o2_kg_day*5.5e3/24, o2_kg_day*7.0e3/24, o2_kg_day*9.0e3/24), 'CONT', 'STUDY', '5.5-9 kWh per kg O2 (ISS OGA class); G01 lists 1.7 kW per string'),
        ('HAB.WATER', 'ECLSS', 'Water recovery (urine, condensate, brine) and potable treatment, both rings',
         band(1.5e3, 3.0e3, 5.0e3), 'CONT', 'STUDY', 'ISS UPA+WPA+BPA order, scaled to 12'),
        ('HAB.CO2RED', 'ECLSS', 'CO2 reduction (Sabatier) and trace-gas polishing', band(0.3e3, 0.8e3, 1.5e3), 'CONT', 'STUDY', 'ISS Sabatier order'),
        ('HAB.HEATPUMP', 'TMS', 'Ring heat pumps lifting cabin heat to the 320 K cold loop', band(8e3, 12e3, 20e3), 'CONT', 'DERIVED',
         'ring_services COP 0.5 Carnot, ~25-35 kW cabin heat per ring'),
        ('HAB.HOTEL', 'HAB', 'Lighting, galley, laboratory and workshop benches', band(0.7*2*ring_hotel, 2*ring_hotel, 2*ring_hotel*1.8), 'INTER', 'PROTO',
         'ring_services LIGHT/GALLEY/LAB, x2'),
        ('HAB.GARDEN', 'ECLSS', 'Garden plant lighting and nutrient circuits (6 kW/ring today; 25 % caloric closure for 12 needs ~120 m2 of crop)',
         band(12e3, 40e3, 90e3), 'CONT', 'STUDY', 'ring_services GARDEN 6 kW x2 (low); 120-250 m2 at 250-400 W/m2 LED (nominal/high)'),
        ('HAB.MED', 'SAFETY', 'Medical diagnostics, sterilisation, cold storage', band(0.3e3, 1.0e3, 3.0e3), 'INTER', 'STUDY', 'clinic order'),
        ('HAB.ROTOR', 'STRUCT', 'Ring hub motors (spin hold), magnetic bearings, contactless transfer losses', band(2e3, 8e3, 20e3), 'CONT', 'STUDY',
         'bearing/seal drag; spin-up of a ring is ~11 MJ (3 kWh), so spin-up is not a power driver'),
        ('SHIP.CDH', 'CDH', 'Flight, engineering and habitat computers, networks, recorders', band(10e3, 30e3, 80e3), 'CONT', 'STUDY',
         'ISS C&DH order x3 for full autonomy; the LOW section carries a 300 kW avionics heat allowance (fuel_loads.cooling)'),
        ('SHIP.GNC', 'GNC', 'Star trackers, IMUs, CMG spin and gimbal power, RCS heaters and valves', band(3e3, 8e3, 20e3), 'CONT', 'STUDY', 'six CMGs + sensors'),
        ('SHIP.COMMS', 'COMMS', 'Two 4 m Ka dishes + optical terminal at 30-300 AU (duty-averaged)', band(1e3, 4e3, 12e3), 'INTER', 'STUDY',
         'kW-class RF/optical transmitter for a deep-space link'),
        ('SHIP.CRYO', 'TMS', 'Zero-boil-off cryocoolers of the tank farm (20 K shield + 3 K He-3 stage)', band(cryo_W*0.8, cryo_W, cryo_W*1.5), 'CONT', 'DERIVED',
         'p1_fuel_loads.json cooling.rejected_W (input work ~= rejection)'),
        ('SHIP.EYE', 'PROT', 'EYE Quiet Watch (drive-off coast)', band(eye['power_inputs']['quiet_W'], eye['power_inputs']['quiet_W'], ed['survey_W']), 'CONT', 'SPEC',
         f"eye.power_inputs.quiet_W ({eye['power_inputs'].get('canon_status', eye.get('canon_status','?'))}); survey {ed['survey_W']/1e3:.0f} kW as high"),
        ('SHIP.TMS_PUMPS', 'TMS', 'Warm-loop and LOW-section circulation pumps (5 MW warm + 1 MW LOW base)', band(30e3, 80e3, 200e3), 'CONT', 'STUDY',
         '0.5-3 % of heat moved, pumped-loop order'),
        ('SHIP.DRONES', 'MRO', 'Maintenance drones charging, workshop machines (duty-averaged)', band(2e3, 10e3, 40e3), 'INTER', 'STUDY', 'drone fleet + fabrication cell'),
        ('SHIP.DRIVE_STBY', 'PROP', 'Drive standby: magnet cryostat keep-cold, plasma-facing heaters, feed conditioning (coast)', band(20e3, 100e3, 400e3), 'CONT', 'STUDY',
         'OPEN in canon; superconducting coil keep-cold order'),
        ('DEF.PROACTIVE', 'PROT', 'Forward defense proactive field band', band(*[fd['bands_W']['proactive'][0]]*2, fd['bands_W']['proactive'][1]), 'CONT', 'SPEC',
         f"forward_defense.power.bands_W.proactive ({fd['bands_W']['canon_status']})"),
        ('DEF.FIELD_SVC', 'PROT', 'Defense field services', band(fd['field_services_W']['range'][0], sum(fd['field_services_W']['range'])/2, fd['field_services_W']['range'][1]),
         'CONT', 'SPEC', f"forward_defense.power.field_services_W ({fd['field_services_W']['canon_status']}, planning allowance)"),
        ('DEF.NORMAL', 'PROT', 'Forward defense normal active band', band(fd['bands_W']['normal_active'][0], sum(fd['bands_W']['normal_active'])/2, fd['bands_W']['normal_active'][1]),
         'MODE', 'SPEC', f"forward_defense.power.bands_W.normal_active ({fd['bands_W']['canon_status']}); steady duty OPEN (40!B66)"),
        ('DEF.SEVERE', 'PROT', 'Forward defense severe band', band(*fd['bands_W']['severe'][:1]*2, fd['bands_W']['severe'][1]), 'MODE', 'SPEC', 'bands_W.severe'),
        ('DEF.BURST', 'PROT', 'Forward defense extreme burst (store-fed, Heat Debt)', band(fd['bands_W']['extreme_burst'][0], sum(fd['bands_W']['extreme_burst'])/2, fd['bands_W']['extreme_burst'][1]),
         'PEAK', 'SPEC', 'bands_W.extreme_burst; Crown local stores 20 MJ (forward_defense.crown_inputs)'),
        ('EYE.BURN', 'PROT', 'EYE Burn Watch', band(ed['burn_watch_W'], ed['burn_watch_W'], ed['burn_watch_W']), 'MODE', 'SPEC', 'eye.electrical_demand.burn_watch_W (DERIVED)'),
        ('EYE.ABLATE', 'PROT', 'EYE Emergency Ablation', band(ed['ablation_W'], ed['ablation_W'], ed['ablation_W']), 'PEAK', 'SPEC', 'eye.electrical_demand.ablation_W (DERIVED)'),
        ('BURN.HEATPUMP', 'TMS', 'Burn heat pumps lifting the warm loop into the hot loop (at burnout)', band(150e6, 210e6, 260e6), 'MODE', 'DERIVED',
         'p1_heat_rejection.json, F02 (drive electric tap)'),
        ('BURN.HOTLOOP', 'TMS', 'Hot-loop circulation during a burn (GW-class heat transport)', band(10e6, 40e6, 100e6), 'MODE', 'STUDY',
         '0.5-3 % of ~3.6 GW other-loads + drive absorbed heat; OPEN coolant'),
        ('START.PULSE', 'EPS', 'Pulse bank discharge into seed field / startup heating', band(50e6, 50e6, 50e6), 'START', 'SPEC',
         'power.storage.pulse_bank.power_W, 200 kWh'),
        ('EVA.SUPPORT', 'EVA', 'Airlock pumps, suit charging and O2 top-up, floodlights', band(3e3, 8e3, 15e3), 'INTER', 'STUDY', 'ISS airlock depress pump ~1-2 kW'),
        ('DOCK.XFER', 'DOCK', 'Docking mechanisms, umbilical, propellant-transfer pumps', band(5e3, 30e3, 200e3), 'INTER', 'STUDY', 'transfer pump order'),
    ]
    return [dict(id=a, family=b, title=c, W=d, role=e, cls=f, basis=g) for a, b, c, d, e, f, g in L]


# Operating conditions: which loads run (multiplier per load id; absent = 0). 'HAB_SURV' scales habitat loads to survival.
BASE_COAST = {'HAB.ECLSS': 1, 'HAB.O2GEN': 1, 'HAB.WATER': 1, 'HAB.CO2RED': 1, 'HAB.HEATPUMP': 1, 'HAB.HOTEL': 1, 'HAB.GARDEN': 1,
              'HAB.MED': 1, 'HAB.ROTOR': 1, 'SHIP.CDH': 1, 'SHIP.GNC': 1, 'SHIP.COMMS': 1, 'SHIP.CRYO': 1, 'SHIP.EYE': 1,
              'SHIP.TMS_PUMPS': 1, 'SHIP.DRONES': 1, 'SHIP.DRIVE_STBY': 1}
MODES = {
    'NORMAL_COAST': dict(BASE_COAST, **{'DEF.PROACTIVE': 1, 'DEF.FIELD_SVC': 1}),
    'HIGH_VELOCITY_COAST': dict(BASE_COAST, **{'DEF.PROACTIVE': 1, 'DEF.FIELD_SVC': 1, 'DEF.NORMAL': 1}),
    'LOW_THRUST': dict(BASE_COAST, **{'DEF.PROACTIVE': 1, 'DEF.FIELD_SVC': 1, 'EYE.BURN': 1, 'BURN.HOTLOOP': 0.3, 'BURN.HEATPUMP': 0.2, 'SHIP.EYE': 0}),
    'HIGH_THRUST': dict(BASE_COAST, **{'HAB.ROTOR': 0.2, 'HAB.GARDEN': 0.5, 'DEF.PROACTIVE': 1, 'DEF.FIELD_SVC': 1, 'DEF.NORMAL': 1,
                                       'EYE.BURN': 1, 'SHIP.EYE': 0, 'BURN.HOTLOOP': 1, 'BURN.HEATPUMP': 1}),
    'FIRST_IGNITION': dict(BASE_COAST, **{'HAB.ROTOR': 0.2, 'HAB.GARDEN': 0.3, 'HAB.HOTEL': 0.5, 'DEF.PROACTIVE': 1, 'EYE.BURN': 1, 'SHIP.EYE': 0,
                                          'START.PULSE': 1, 'BURN.HOTLOOP': 0.2}),
    'BLACK_START': {'HAB.ECLSS': 1, 'HAB.HEATPUMP': 0.5, 'SHIP.CDH': 0.6, 'SHIP.GNC': 1, 'SHIP.COMMS': 0.3, 'SHIP.CRYO': 1, 'SHIP.EYE': 1,
                    'SHIP.TMS_PUMPS': 0.5, 'SHIP.DRIVE_STBY': 1, 'START.PULSE': 1},
    'PROPULSION_SHUTDOWN': dict(BASE_COAST, **{'DEF.PROACTIVE': 1, 'BURN.HOTLOOP': 0.3, 'HAB.ROTOR': 0.5}),
    'POST_BURN_COOLDOWN': dict(BASE_COAST, **{'DEF.PROACTIVE': 1, 'DEF.FIELD_SVC': 1, 'BURN.HOTLOOP': 0.15}),
    'DOCKED': dict(BASE_COAST, **{'DOCK.XFER': 1, 'SHIP.EYE': 0.5, 'HAB.ROTOR': 0.2}),
    'EVA_OPERATIONS': dict(BASE_COAST, **{'DEF.PROACTIVE': 1, 'EVA.SUPPORT': 1}),
    'MAINTENANCE': dict(BASE_COAST, **{'DEF.PROACTIVE': 1, 'SHIP.DRONES': 3, 'EVA.SUPPORT': 0.5}),
    'EMERGENCY_SURVIVAL': {'HAB.ECLSS': 0.6, 'HAB.O2GEN': 0.0, 'HAB.HEATPUMP': 0.4, 'HAB.MED': 0.3, 'SHIP.CDH': 0.2, 'SHIP.GNC': 0.3,
                           'SHIP.COMMS': 0.3},
    'SURVIVAL_WITH_CRYO': {'HAB.ECLSS': 0.6, 'HAB.HEATPUMP': 0.4, 'HAB.MED': 0.3, 'SHIP.CDH': 0.2, 'SHIP.GNC': 0.3, 'SHIP.COMMS': 0.3,
                           'SHIP.CRYO': 1.0},
    'PARTIAL_FAILURE_ONE_PLANT': dict(BASE_COAST, **{'HAB.GARDEN': 0.5, 'HAB.HOTEL': 0.5, 'SHIP.DRONES': 0.3, 'DEF.PROACTIVE': 1}),
    'EXTENDED_DRIVE_OFF': dict(BASE_COAST, **{'DEF.PROACTIVE': 1, 'DEF.FIELD_SVC': 1}),
}
MODE_NOTES = {
    'NORMAL_COAST': 'drive off, rings spinning, proactive defense field only (inner system or low speed)',
    'HIGH_VELOCITY_COAST': 'the multi-year cruise at up to 0.016 c with the normal active defense band ON (its steady duty is OPEN)',
    'LOW_THRUST': 'drive on at low power, rings spinning; drive generators carry burn loads',
    'HIGH_THRUST': 'drive at peak; rings stopped and locked; burn heat pumps at burnout',
    'FIRST_IGNITION': 'pulse bank startup transient (seconds) on top of a reduced ship load',
    'BLACK_START': 'every plant cold; stores wake the ship, battery charges the pulse bank',
    'PROPULSION_SHUTDOWN': 'drive off, hot loop still circulating',
    'POST_BURN_COOLDOWN': 'blades cooling, hot loop at part flow, rings spun up again',
    'DOCKED': 'at a station; rings stopped; propellant transfer',
    'EVA_OPERATIONS': 'coast plus airlock cycling and suit servicing',
    'MAINTENANCE': 'coast plus heavy drone/workshop duty',
    'EMERGENCY_SURVIVAL': 'crew survival loads only (refuge or one ring); tank farm abandoned to boil-off',
    'SURVIVAL_WITH_CRYO': 'crew survival plus the tank-farm cryocoolers (keeps the mission alive)',
    'PARTIAL_FAILURE_ONE_PLANT': 'one ship-service plant lost: discretionary loads shed, defense proactive only',
    'EXTENDED_DRIVE_OFF': 'years of coast; same load as normal coast, the question is endurance and maintenance',
}


def mode_totals(L):
    ids = {x['id']: x for x in L}
    out = {}
    for m, mult in MODES.items():
        tot = [0.0, 0.0, 0.0]; peak = [0.0, 0.0, 0.0]; byfam = {}
        for k, f in mult.items():
            x = ids[k]
            for i in range(3):
                v = x['W'][i]*f
                (peak if x['role'] in ('PEAK', 'START') else tot)[i] += v
            byfam[x['family']] = byfam.get(x['family'], 0.0) + x['W'][1]*f*(x['role'] not in ('PEAK', 'START'))
        out[m] = dict(continuous_W=tot, peak_add_W=peak, by_family_nominal_W=byfam, note=MODE_NOTES[m])
    return out


def storage(s, totals):
    st = s['power']['storage']
    E = st['main_battery']['usable_energy_Wh']*3600.0
    rows = {}
    for m in ('NORMAL_COAST', 'HIGH_VELOCITY_COAST', 'SURVIVAL_WITH_CRYO', 'EMERGENCY_SURVIVAL'):
        lo, nom, hi = totals[m]['continuous_W']
        rows[m] = dict(main_battery_hours=[E/hi/3600, E/nom/3600, E/lo/3600])
    # survival reserve: Deadship PROTOTYPE 8 kWh per ring
    surv_J = 2*8000.0*3600
    lo, nom, hi = totals['EMERGENCY_SURVIVAL']['continuous_W']
    rows['survival_packs_2x8kWh_hours'] = [surv_J/hi/3600, surv_J/nom/3600, surv_J/lo/3600]
    # what a 30-day independent survival endurance would cost in batteries
    rows['battery_mass_for_30d_survival_t'] = [lo*30*86400/3600/800/1000, nom*30*86400/3600/800/1000, hi*30*86400/3600/800/1000]
    fl = json.loads((ROOT / 'references' / 'p1_fuel_loads.json').read_text())
    rows['he3_boiloff_uncooled_t_per_day'] = fl['heat']['helium_3']['uncooled_boiloff_kg_day']/1000
    return rows


# Generation candidates: specific mass of a complete plant (reactor/source, shield, conversion, PMAD; radiator separately) in kg/kWe.
# Literature anchors (results/sources in NOTES.md): SP-100 100 kWe < 3,000-4,600 kg (~30-46 kg/kWe incl. radiator, thermoelectric);
# FSP 40 kWe < 6 t (~150 kg/kWe surface); Kilopower 10 kWe ~1.5 t projected; INL 2002 multi-MWe Brayton 3.5 kg/kWe (goal 3-5, 'substantial
# development'); NASA MW-class NEP studies treat < 10 kg/kWe propulsion-system alpha as the threshold of attractiveness.
CANDIDATES = {
    'A_MAIN_FUSION_HOTEL': dict(title='Main propulsion reactor in low-power hotel mode', alpha=None, eff=None, independent=False,
                                maturity='SPECULATIVE (canon drive); turndown OPEN',
                                verdict='Not credible as the continuous source: a reactor sized for ~200 GW of jet power would have to hold a burning '
                                        'plasma at 1e-4 to 1e-5 of rating for six years; confinement and power balance do not scale down that far '
                                        'in one fixed machine, and every drive fault becomes a ship-power fault (power.hotel_source OPEN, OD-009).'),
    'B_FISSION_BRAYTON': dict(title='Independent fission reactor + closed Brayton', alpha=(8.0, 15.0, 30.0), eff=(0.20, 0.25, 0.30), independent=True,
                              maturity='ESTABLISHED PHYSICS; MWe class not flown (SP-100/JIMO/NEP studies)',
                              verdict='Credible for ship service and the proactive defense band; mass grows linearly with the defense duty.'),
    'B2_FISSION_STIRLING': dict(title='Fission + free-piston Stirling (Kilopower family)', alpha=(25.0, 40.0, 80.0), eff=(0.22, 0.27, 0.32), independent=True,
                                maturity='ESTABLISHED (KRUSTY 2018 at 1 kWe class)', verdict='Good for 10-100 kWe survival or refuge power; too heavy per kWe for MW.'),
    'C_AUX_FUSION': dict(title='Dedicated small fusion plant (D-He3)', alpha=(5.0, 20.0, 60.0), eff=(0.30, 0.40, 0.55), independent=True,
                         maturity='SPECULATIVE (no fusion plant has produced net electricity)',
                         verdict='Inside the IGNITION technology frame and fuel-free in practice (grams/day of D-He3); its mass and minimum size are not '
                                 'sourced; a second fusion machine doubles the speculative content.'),
    'E1_RPS': dict(title='Radioisotope power (Pu-238 / Am-241, Stirling or TE)', alpha=(150.0, 300.0, 450.0), eff=(0.06, 0.15, 0.25), independent=True,
                   maturity='ESTABLISHED (MMRTG 110 We / 45 kg)', verdict='Only for isolated kWe-class survival loads (beacon, recorder, refuge core); '
                   'decays ~0.8 %/yr (Pu-238).'),
    'E2_SOLAR': dict(title='Photovoltaic', alpha=(5.0, 8.0, 12.0), eff=None, independent=True, maturity='ESTABLISHED',
                     verdict='Useful only docked or inside ~2 AU: flux falls as 1/r2 (1/900 at 30 AU, 1/100,000 at 324 AU).'),
    'E3_FUELCELL': dict(title='H2/O2 fuel cell on stored reactants', alpha=None, eff=(0.5, 0.6, 0.65), independent=True, maturity='ESTABLISHED',
                        verdict='Emergency bridge only: about 0.06 kg H2 and 0.5 kg O2 per kWh; O2 competes with breathing.'),
}


def plant_screen(totals):
    rows = {}
    cases = {
        'ship_service_no_defense': [x - p for x, p in zip(totals['NORMAL_COAST']['continuous_W'], [0, 0, 0])],
    }
    ids = {x['id']: x for x in loads(spec.load()[0])}
    defense = [ids['DEF.PROACTIVE']['W'][i] + ids['DEF.FIELD_SVC']['W'][i] for i in range(3)]
    cases['ship_service_no_defense'] = [a - b for a, b in zip(totals['NORMAL_COAST']['continuous_W'], defense)]
    cases['ship_service_plus_proactive'] = totals['NORMAL_COAST']['continuous_W']
    cases['ship_service_plus_normal_active'] = totals['HIGH_VELOCITY_COAST']['continuous_W']
    for cname, P in cases.items():
        r = {}
        for k, c in CANDIDATES.items():
            if c['alpha'] is None:
                continue
            # 2 x 100 % of the case (two independent plants), mass at nominal power, band over alpha
            r[k] = dict(single_plant_t=[P[1]/1e3*c['alpha'][0]/1e3, P[1]/1e3*c['alpha'][1]/1e3, P[1]/1e3*c['alpha'][2]/1e3],
                        two_plants_100pct_t=[2*P[1]/1e3*c['alpha'][0]/1e3, 2*P[1]/1e3*c['alpha'][1]/1e3, 2*P[1]/1e3*c['alpha'][2]/1e3])
        rows[cname] = dict(P_W=P, candidates=r)
    return rows


def rejection(s, totals):
    """Coast heat rejection of a fission-Brayton ship-service plant on the dark hot blades vs the defense warm channels."""
    A = s['radiators']['effective_area']['value']
    eps = 0.85
    out = {}
    for T in (550.0, 650.0, 800.0):
        out[f'blades_capacity_at_{int(T)}K_MW'] = A*eps*SIGMA*T**4/1e6
    warm = A*0.91*SIGMA*s['thermal']['loops']['architecture']['blade_warm_T_K']**4/1e6
    out['blades_warm_channels_at_440K_MW'] = warm
    shares = []
    for Pe in (1e6, 5e6, 15e6, 35e6):
        waste = Pe*(1/0.25 - 1)
        for d in (0.0, 15e6, 30e6):
            share = waste/(A*eps*SIGMA*650.0**4) + d/(warm*1e6)
            shares.append(dict(plant_MWe=Pe/1e6, plant_waste_MW=waste/1e6, defense_heat_MW=d/1e6, blade_area_fraction=share))
    out['shared_blade_area'] = shares
    return out


# The 50 t power / computers / steering / communications item: what it already has to hold before any drive-off plant (t, lo/nom/hi).
PCSC_LEDGER = [
    ('Main battery 2 MWh: cells at 800 Wh/kg x packaging 1.4-2.0', (3.5, 4.0, 5.0)),
    ('Pulse bank 200 kWh supercapacitors (20-60 Wh/kg pack)', (3.3, 6.0, 10.0)),
    ('Survival packs, converters BC-A/BC-B, ride-through cells', (1.0, 2.0, 4.0)),
    ('Primary distribution A/B/E: HV DC trunks ~2 x 230 m, switchboards, breakers', (3.0, 6.0, 10.0)),
    ('Computers, networks, recorders (CDH)', (1.5, 3.0, 6.0)),
    ('Six CMGs (rotor rim 182 kg each + gimbals, motors, housing)', (3.0, 4.5, 6.0)),
    ('RCS pods, valves and lines (propellant excluded)', (1.5, 2.5, 4.0)),
    ('Comms: two 4 m Ka dishes, optical terminal, booms, transmitters', (1.5, 2.5, 4.0)),
    ('Star trackers, IMUs, sensors, cabling to the Brow', (0.5, 1.0, 2.0)),
]


def pcsc_ledger(plants):
    used = [sum(v[i] for _, v in PCSC_LEDGER) for i in range(3)]
    left = [50.0 - u for u in used]
    b = plants['ship_service_no_defense']['candidates']['B_FISSION_BRAYTON']['single_plant_t']
    return dict(items=[dict(item=k, t=v) for k, v in PCSC_LEDGER], used_t=used, left_for_generation_t=left,
                one_ship_service_plant_t=b, two_ship_service_plants_t=[2*x for x in b],
                note='Plant mass excludes radiators (blades reused in coast) and the reactor shadow shield; both would add.')


def main():
    s = spec.load()[0]
    L = loads(s)
    T = mode_totals(L)
    res = dict(status='ISSA STUDY (NONCANON): bands, not ratings', loads=L, modes=T, storage=storage(s, T), plants=plant_screen(T),
               candidates=CANDIDATES, rejection=rejection(s, T),
               pcsc=None, budget=dict(power_computers_steering_comms_t=50.0,
                           note='Holds batteries, pulse bank, survival packs, computers, CMGs, RCS hardware, comms and any drive-off plant'))
    res['pcsc'] = pcsc_ledger(res['plants'])
    OUT.mkdir(exist_ok=True)
    (OUT / 'eps_study.json').write_text(json.dumps(res, indent=1))
    MW = lambda b: '/'.join(f'{v/1e6:.2f}' for b_ in [b] for v in b_)
    print('MODE                         continuous MW (lo/nom/hi)    peak add MW')
    for m, r in T.items():
        print(f'{m:28s} {MW(r["continuous_W"]):28s} {MW(r["peak_add_W"])}')
    print('\nstorage', json.dumps(res['storage'], indent=1))
    for c, r in res['plants'].items():
        print('\n', c, MW(r['P_W']))
        for k, v in r['candidates'].items():
            print(f'  {k:22s} one {"/".join(f"{x:.0f}" for x in v["single_plant_t"])} t   two {"/".join(f"{x:.0f}" for x in v["two_plants_100pct_t"])} t')
    print('\n', json.dumps({k: v for k, v in res['rejection'].items() if k != 'shared_blade_area'}, indent=1))
    for r in res['rejection']['shared_blade_area']:
        print(r)
    print('\n50 t item', json.dumps(res['pcsc'], indent=1))


if __name__ == '__main__':
    main()
