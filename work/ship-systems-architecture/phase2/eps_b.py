"""ISSA Phase II, EPS-B + TMS-A: generation architecture trade, defense duty cycle, survival power and the coupled thermal ledger.
STUDY (NONCANON). Reads the spec and power_loads (EPS-A); writes ../results/phase2_eps_b.json. Bands are (optimistic, nominal,
conservative). Every literature anchor and its scope is in ANCHORS; nothing here is a selection.

    python3 work/ship-systems-architecture/phase2/eps_b.py
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src/wayfarer'))
import spec  # noqa: E402
import power_loads as pl  # noqa: E402

OUT = Path(__file__).resolve().parents[1]/'results'
SIGMA = 5.670374419e-8
YEAR = 365.25*86400.0
CASES = ('OPT', 'NOM', 'CONS')

ANCHORS = {
    'SP-100': 'SP-100 GES (1980s-1990s): 100 kWe, ~2.4 MWt, thermoelectric, ~4.6 t total incl. radiator and an unmanned 25 m shadow shield; '
              '7-10 yr life. Scope: whole power system, unmanned dose limits. Used for reactor-core scaling only.',
    'JIMO': 'JIMO/Prometheus (2005): 100 kWe Brayton, ~500 kWt, 170 m2 radiator for ~360 kWt; reactor module ~ a few t. Scope: unmanned.',
    'INL2002': 'INL multi-MWe space Brayton study: ~3.5 kg/kWe system goal (3-5), called substantial development. Scope: optimistic total incl. '
               'radiator, unmanned shield. Not demonstrated.',
    'Mason2023': 'Mason, NASA GRC Brayton conversion: MW-class closed Brayton turbo-alternator-compressor + recuperator + gas cooler ~2-5 kg/kWe '
                 '(conversion only). Brayton component technology flown in none; terrestrial and lab heritage (BRU, 2 kWe-class).',
    'Kilopower': 'KRUSTY 2018: 1 kWe-class Stirling, demonstrated on the ground; Fission Surface Power 40 kWe under 6 t (incl. shield for '
                 'surface use). Scope: whole plant.',
    'MMRTG': 'MMRTG: 110 We BOL, 45 kg, ~4.8 kg Pu-238 dioxide, -4.8 %/yr output incl. thermocouple degradation (flight).',
    'ASRG': 'Advanced Stirling RG (cancelled 2013): ~130 We, ~32 kg, 4x less Pu-238 than an MMRTG (lab-tested).',
    'Fusion': 'No fusion plant has produced net electricity. Compact D-He3 power plant masses in studies span tens of t to hundreds of t; '
              'minimum machine size is the dominant unknown. SPECULATIVE within the IGNITION technology frame.',
    'Decay': 'Way-Wigner decay heat P/P0 = 0.0622 (t^-0.2 - (t+T)^-0.2), t and T in s (order of magnitude, +/-30 %).',
}

# ---------- component mass model (kg); unit = kWt or kWe as named ---------------------------------------------------------------------
COMP = {
    'reactor_fixed_kg': (300.0, 500.0, 900.0),            # vessel, reflectors, drives, controls
    'reactor_kg_per_kWt': (0.15, 0.30, 0.60),            # SP-100 core ~1 t at 2.4 MWt (anchor), fuel inventory inside
    'heat_transport_kg_per_kWt': (0.30, 0.60, 1.20),     # Li/NaK pumps, piping, intermediate HX
    'conversion_kg_per_kWe': (1.5, 3.0, 6.0),             # Brayton TAC + recuperator + gas cooler (Mason2023)
    'pmad_kg_per_kWe': (0.5, 1.0, 2.0),                   # rectifiers, switchgear, plant breakers
    'structure_frac': (0.08, 0.10, 0.15),
    'coolant_frac': (0.03, 0.05, 0.08),
    'spares_frac': (0.05, 0.10, 0.20),                    # dedicated spares and maintenance equipment for six years
    'rejection_kg_per_m2': (1.5, 3.0, 5.0),               # higher-temperature channels added to blade panels (no new surface)
    'headers_kg': (1000.0, 2000.0, 4000.0),               # per plant: headers from the district to the blade roots
}
# Shadow shield: crew-rated layered LiH/W disc behind the core. Anchor: a few MWt at ~150 m to ~0.05 Sv/yr needs ~1 m layered thickness;
# disc area grows with core size (Pt^2/3), thickness by e-folds of (Pt/d^2): lambda_eff ~0.1 m per e-fold (neutron+gamma, STUDY).
SHIELD = dict(ref_Pt_W=2.5e6, ref_d_m=150.0, ref_kg=(4000.0, 6000.0, 10000.0), ref_t_m=1.0, lam_m=0.10)
EFF = dict(T_hot_K=(1300.0, 1150.0, 1050.0), carnot_frac=(0.45, 0.42, 0.38))
UNAVAIL = (0.02, 0.05, 0.10)                              # per-unit unavailability (failure + repair + maintenance)


def brayton_eff(T_rej, i):
    return EFF['carnot_frac'][i]*(1.0-T_rej/EFF['T_hot_K'][i])


def shield_kg(Pt, d, i, cover='SHADOW'):
    t = SHIELD['ref_t_m']+SHIELD['lam_m']*math.log(max(1e-3, (Pt/SHIELD['ref_Pt_W'])*(SHIELD['ref_d_m']/d)**2))
    m = SHIELD['ref_kg'][i]*(Pt/SHIELD['ref_Pt_W'])**(2/3)*t/SHIELD['ref_t_m']
    # SHADOW protects the rings and refuge only; SECTOR adds shields toward the keel lanes and the EVA/drone stations in the casing;
    # FOUR_PI would allow work beside a running reactor (illustrative bound).
    return m*{'SHADOW': 1.0, 'SECTOR': 2.5, 'FOUR_PI': 12.0}[cover]


def fission_plant(Pe, T_rej, d, i, A_eff, eps, cover='SHADOW'):
    eta = brayton_eff(T_rej, i); Pt = Pe/eta; kWt = Pt/1e3; kWe = Pe/1e3
    waste = Pt-Pe
    area = waste/(eps*SIGMA*T_rej**4)
    c = {k: (v[i] if isinstance(v, tuple) else v) for k, v in COMP.items()}
    parts = dict(reactor=c['reactor_fixed_kg']+c['reactor_kg_per_kWt']*kWt, heat_transport=c['heat_transport_kg_per_kWt']*kWt,
                 conversion=c['conversion_kg_per_kWe']*kWe, pmad=c['pmad_kg_per_kWe']*kWe)
    sub = sum(parts.values())
    parts.update(structure=c['structure_frac']*sub, coolant=c['coolant_frac']*sub, spares=c['spares_frac']*sub,
                 rejection=c['rejection_kg_per_m2']*area+c['headers_kg'], shield=shield_kg(Pt, d, i, cover))
    return dict(Pe_W=Pe, eta=eta, Pt_W=Pt, waste_W=waste, T_rej_K=T_rej, blade_area_m2=area, blade_fraction=area/A_eff,
                parts_kg=parts, mass_kg=sum(parts.values()),
                volume_m3=8.0+2.0*Pt/1e6+4.0*Pe/1e6,   # reactor+shield ~8 m3, heat transport ~2 m3/MWt, conversion ~4 m3/MWe (STUDY)
                fuel_kg_6y=Pt*6*YEAR/(200e6*1.602e-19)*235*1.66054e-27/0.6)  # U-235 fissioned (200 MeV each) at 60 % of fissile burned


def fusion_plant(Pe, i, A_eff, eps, T_rej=900.0):
    eta = (0.55, 0.40, 0.30)[i]; Pt = Pe/eta; fixed = (20e3, 50e3, 120e3)[i]; spec_m = (5.0, 20.0, 60.0)[i]
    waste = Pt-Pe; area = waste/(eps*SIGMA*T_rej**4)
    parts = dict(machine=fixed, scaling=spec_m*Pe/1e3, shield=(2e3, 5e3, 12e3)[i], rejection=COMP['rejection_kg_per_m2'][i]*area)
    return dict(Pe_W=Pe, eta=eta, Pt_W=Pt, waste_W=waste, T_rej_K=T_rej, blade_area_m2=area, blade_fraction=area/A_eff,
                parts_kg=parts, mass_kg=sum(parts.values()), volume_m3=(60.0, 120.0, 300.0)[i],
                fuel_kg_6y=Pt*6*YEAR/3.5e14)


def p_short(units, unit_W, need_W, u):
    """Probability that the available units carry less than need_W (independent unit unavailability u)."""
    k = math.ceil(need_W/unit_W - 1e-9)
    return sum(math.comb(units, j)*(1-u)**j*u**(units-j) for j in range(0, min(k, units+1)) if j < k)


def decay_heat(P0, t_s, T_op_s):
    return P0*0.0622*(t_s**-0.2-(t_s+T_op_s)**-0.2)


def main():
    s = spec.load()[0]; I = pl.items(s); L = pl.ledgers(s, I=I)
    A_eff = s['radiators']['effective_area']['value']; eps = s['radiators']['zones']['emissivity']
    pm = s['power']['loads']['pmad_loss_fraction']
    pro = L['COAST_HV_PROACTIVE']; act = L['COAST_HV_CONTINUOUS_ACTIVE']
    planning = [sum((o['planning_W'] or (0, 0, 0))[j] for o in pro['open']) for j in range(3)]
    pri = pl.by_priority(pro)
    defense_pro = I['PROT.DEF_PROACTIVE']['W']
    ess = [pri['ESSENTIAL'][j]*(1+pm[j]) for j in range(3)]
    core = [(pri['ESSENTIAL'][j]+pri['MISSION'][j]-defense_pro[j])*(1+pm[j]) for j in range(3)]   # crew + mission core, no defense
    must = [(pri['ESSENTIAL'][j]+pri['MISSION'][j])*(1+pm[j]) for j in range(3)]                  # + proactive defense
    design = [pro['generation_W'][j]+planning[j]*(1+pm[j]) for j in range(3)]                     # known + OPEN planning bands
    design_active = [act['generation_W'][j]+planning[j]*(1+pm[j]) for j in range(3)]
    D = dict(essential_W=ess, mission_core_W=core, must_keep_with_proactive_W=must, design_proactive_W=design,
             design_continuous_active_W=design_active, planning_open_W=planning)

    # ---------- DR-01: defense duty cycle ------------------------------------------------------------------------------------------
    Pp, Pa = defense_pro[1], I['PROT.DEF_ACTIVE']['W'][1]; Pexp = I['PROT.DEF_ACTIVE']['exported_W']
    warm_cap = A_eff*eps*SIGMA*s['thermal']['loops']['architecture']['blade_warm_T_K']**4
    duty_rows = []
    for t_e in (1.0, 10.0, 60.0, 600.0, 3600.0, 6*3600.0, 86400.0):
        for interval in (600.0, 3600.0, 86400.0, 7*86400.0):
            if t_e >= interval:
                continue
            for surplus in (0.5e6, 2e6, 5e6):
                for E_buf in (0.1e9, 1e9, 5e9):
                    e = pl.engagement(Pp, Pa, t_e, interval, Pp+surplus, E_buf, P_export=Pexp, Q_reject_def=0.5*warm_cap)
                    duty_rows.append(dict(t_eng_s=t_e, interval_s=interval, surplus_W=surplus, buffer_J=E_buf, **e))
    # buffer technology masses for the engagement energy (pack-level, plus 30 % installed)
    buf_tech = {'supercapacitor (pulse-bank class, 30 Wh/kg)': 30.0, 'high-power Li cells (150 Wh/kg)': 150.0,
                'main-battery chemistry (800 Wh/kg, WORKING extrapolation)': 800.0}
    buffers = {name: {f'{E/1e9:g} GJ': E/3600.0/whkg*1.3 for E in (0.1e9, 1e9, 5e9, 20e9)} for name, whkg in buf_tech.items()}
    # dust context (lab/studies/dust-impacts NOMINAL/HIGH, Vertex research mission profile): grains that pass the 2 m disruptor
    dust = json.loads((ROOT/'lab/studies/dust-impacts/results/dust.json').read_text())
    h = dust['headline']; days = h['trip_days']
    dust_ctx = dict(note='Vertex research-mission profile (467 d), not the six-year canon mission: an order-of-magnitude context only.',
                    brow_breaches=dict(LOW=h['brow_breaches_low'], NOMINAL=h['brow_breaches'], HIGH=h['brow_breaches_high']),
                    mean_interval_s={k: days*86400.0/v for k, v in dict(LOW=h['brow_breaches_low'], NOMINAL=h['brow_breaches'],
                                                                         HIGH=h['brow_breaches_high']).items()},
                    warning='At 0.016 c a grain covers 4,800 km/s: warning times are milliseconds to seconds; neutral dust ignores fields.')

    # ---------- EPS-B: generation architectures -----------------------------------------------------------------------------------
    d_plant = 155.0                                          # M3/M4 (X -65..-41) to ring A (X 97.3): ~150-160 m
    T_rej = 550.0
    def arch(name, units, unit_W, running, tech='FISSION', T=T_rej, cover='SHADOW', note=''):
        rows = []
        for i in range(3):
            p = fission_plant(unit_W, T, d_plant, i, A_eff, eps, cover) if tech == 'FISSION' else fusion_plant(unit_W, i, A_eff, eps)
            rows.append(p)
        mass = [units*r['mass_kg'] for r in rows]
        # blade area while carrying the nominal design load (all running units share it)
        load_W = design[1]; frac = rows[1]['blade_fraction']*load_W/unit_W
        rel = {f'u={u}': dict(p_short_essential=p_short(units, unit_W, ess[2], u), p_short_mission=p_short(units, unit_W, must[2], u),
                              p_short_full=p_short(units, unit_W, design[2], u)) for u in UNAVAIL}
        return dict(name=name, tech=tech, units=units, unit_W=unit_W, installed_W=units*unit_W, running=running, mass_kg=mass,
                    unit=rows, waste_at_design_W=load_W*(1/rows[1]['eta']-1), blade_fraction_at_design=frac,
                    volume_m3=units*rows[1]['volume_m3'], reliability=rel, note=note)
    Pd = design[2]*1.1                                         # high band + 10 % growth
    A = arch('A: 2 x 100 %', 2, Pd, 'both at ~50 % (hot, load-sharing)', note='Each plant carries the whole design load alone.')
    B = arch('B: 2 x 60 %, essentials on either', 2, max(0.6*Pd, must[2]*1.1), 'both sharing',
             note='Either plant alone carries everything that must keep running (crew, cryo, nav, comms, proactive defense).')
    C = arch('C: 3+1 modular (N+1)', 4, Pd/3, 'three running, one warm standby', note='Four identical modules; any three carry the design load.')
    C2 = arch('C2: 5+1 modular', 6, Pd/5, 'five running, one warm standby', note='Smaller modules: more shield discs and controls, better availability.')
    Dg = arch('D: 3+1 modular + dedicated defense buffer', 4, (Pd+2e6)/3, 'three running', note='Modules sized for design plus 2 MW to recharge a '
              'defense buffer; engagements up to the buffer limit draw the active band from storage (buffer mass listed apart).')
    E = arch('E: 2 x 60 % auxiliary fusion (SPECULATIVE)', 2, max(0.6*Pd, must[2]*1.1), 'both sharing', tech='FUSION',
             note='D-He3 in the IGNITION frame; no fusion plant has made net electricity.')
    A_act = arch('A-bound: 2 x 100 % for continuous active defense', 2, design_active[2]*1.1, 'both at ~50 %',
                 note='Bounding: the normal active band all cruise.')
    C_act = arch('C-bound: 3+1 for continuous active defense', 4, design_active[2]*1.1/3, 'three running', note='Bounding.')
    Pn = design[1]*1.1                                         # nominal band + 10 %: the smallest credible sizing
    B_lean = arch('B-lean: 2 x 60 % at nominal demand', 2, max(0.6*Pn, must[1]*1.1), 'both sharing', note='Smallest credible two-plant sizing.')
    C_lean = arch('C-lean: 3+1 at nominal demand', 4, Pn/3, 'three running', note='Smallest credible modular sizing.')
    archs = [A, B, C, C2, Dg, E, B_lean, C_lean, A_act, C_act]
    for a in archs:
        a['buffer_kg'] = (1e9/3600.0/800.0*1.3, 1e9/3600.0/150.0*1.3, 1e9/3600.0/30.0*1.3) if a['name'].startswith('D') else (0.0, 0.0, 0.0)
    # rejection-temperature sensitivity of one 2 MWe module
    t_sens = [dict(**{k: v for k, v in fission_plant(2e6, T, d_plant, 1, A_eff, eps).items() if k != 'parts_kg'}) for T in (440.0, 500.0, 550.0, 600.0, 650.0)]
    shield_cover = {c: shield_kg(2e6/brayton_eff(550, 1), d_plant, 1, c) for c in ('SHADOW', 'SECTOR', 'FOUR_PI')}
    dist_sens = {f'{d:g} m': shield_kg(2e6/brayton_eff(550, 1), d, 1) for d in (40.0, 80.0, 155.0, 250.0)}
    operating = [
        dict(mode='All units at partial load (hot, sharing)', start='instant pickup (seconds)', min_stable='Brayton ~30-40 % of rating; reactor any',
             penalty='every unit accumulates turbomachinery hours and fuel burn; no dormant failures', benefit='a trip loses only its share'),
        dict(mode='Warm standby (reactor at low power, loop hot, TAC idling or stopped)', start='minutes (TAC restart, ramp)', min_stable='n/a',
             penalty='decay and idle heat still rejected; standby reactor still needs shielding', benefit='spare unit ready after a trip'),
        dict(mode='Cold standby (subcritical, loop frozen or drained)', start='hours to a day (thaw a Li loop: Li freezes at 454 K; NaK does not)',
             min_stable='n/a', penalty='dormant failures undetected; slow', benefit='no wear, no heat'),
    ]
    # ---------- L1 burn generation --------------------------------------------------------------------------------------------------
    ht = L['HIGH_THRUST']; l1 = ht['by_supply_W'].get('L1', (0, 0, 0))
    l1_need = [ht['generation_W'][j]+(ht['open'] and sum((o['planning_W'] or (0, 0, 0))[j] for o in ht['open'])) for j in range(3)]
    L1 = dict(high_thrust_generation_W=ht['generation_W'], with_open_planning_W=l1_need, rated_F02_pump_work_W=I['TMS.BURN_HEAT_PUMPS']['rated_W'],
              mass_kg=[l1_need[1]/1e3*k for k in (0.7, 1.5, 3.5)],
              note='Conversion from the drive hot loop at ~1800 K (Brayton/MHD/direct conversion OPEN); 0.7-3.5 kg/kWe (INL2002 total as the '
                   'conservative end). The hot-loop pumps (OPEN, 10-100 MW planning) dominate the uncertainty.')

    # ---------- L3 survival -----------------------------------------------------------------------------------------------------------
    surv = {'1 crew only': L['SURVIVAL_CREW']['generation_W'],
            '2 crew + cryo': L['SURVIVAL_MISSION']['generation_W'],
            '3 crew + nav/comms': tuple(L['SURVIVAL_CREW']['generation_W'][j]+20e3 for j in range(3)),
            '4 mission recovery (2 + protected black-start reserve)': L['SURVIVAL_MISSION']['generation_W'],
            '5 high-velocity protected': L['SURVIVAL_PROTECTED']['generation_W']}
    reserve_J = pl.storage(s, L, I)['black_start_reserve_J']
    opts = {
        'battery (conservative chemistry 250 Wh/kg pack, +30 % installed)': lambda P, t: P*t/3600.0/250.0*1.3,
        'battery (800 Wh/kg main-battery chemistry, +30 %)': lambda P, t: P*t/3600.0/800.0*1.3,
        'H2/O2 fuel cell on stored reactants (0.45 kg reactant/kWh, tanks x2, +stack 5 kg/kW)': lambda P, t: P*t/3.6e6*0.45*2.0+P/1e3*5.0,
        'RPS (advanced Stirling 4 We/kg, Pu-238 decays 0.8 %/yr)': lambda P, t: P/4.0,
        'fission-Stirling (Kilopower family: 10 kWe 1.5 t, 40 kWe 6 t incl. shield; 130 kg/kWe + 1 t)': lambda P, t: 1000.0+P/1e3*130.0,
    }
    l3 = {}
    for sc, P in surv.items():
        extra = reserve_J if sc.startswith('4') else 0.0
        l3[sc] = dict(P_W=P, rows={})
        for name, f in opts.items():
            l3[sc]['rows'][name] = {lab: f(P[2], t)+(extra/3600.0/800.0*1.3 if 'battery' in name or 'cell' in name else 0.0)
                                    for lab, t in (('72 h', 72*3600.0), ('7 d', 7*86400.0), ('30 d', 30*86400.0))}
    rps_radiation = dict(
        RPS='Pu-238 alpha source: gamma and spontaneous-fission neutrons are weak; ~0.1-1 mSv/h at 1 m unshielded for a kWt-class unit; a few cm '
            'of shielding or a few metres of distance suffice beside a refuge.',
        fission='A 10-40 kWe fission-Stirling (40-150 kWt) next to the refuge needs a shadow shield of ~1-3 t and tens of metres, or the refuge '
                'itself as shield: placing it beside the refuge is not acceptable without it; 20-40 m away on the forward collar is.',
        recommendation='Local batteries/fuel cells per ring and refuge for crew-only (no single point), plus one isolated kWe-class RPS or '
                       'fission-Stirling for mission preservation; cryo at 0.4 MW is beyond any isolated survival source short of L2.')

    # ---------- TMS-A: coupled thermal ledger ------------------------------------------------------------------------------------------
    sections = {x['id']: x for x in s['radiators']['zones']['sections']}
    warm_T = s['thermal']['loops']['architecture']['blade_warm_T_K']
    def frac(Q, T):
        return Q/(A_eff*eps*SIGMA*T**4)
    thermal = []
    for a in (A, B, C, Dg, E, A_act):
        u = a['unit'][1]; Pe = design[1] if 'bound' not in a['name'] else design_active[1]
        waste = Pe*(1/u['eta']-1)
        def_heat = (pro if 'bound' not in a['name'] else act)['heat_W']['WARM'][1]
        f_plant = frac(waste, u['T_rej_K']); f_def = frac(max(0.0, def_heat-sections['WARM']['load_W']), warm_T)
        low = (pro if 'bound' not in a['name'] else act)['heat_W']['LOW'][1]
        thermal.append(dict(arch=a['name'], Pe_W=Pe, eta=u['eta'], primary_W=Pe/u['eta'], conversion_waste_W=waste, consumer_heat_W=Pe,
                            exported_W=(pro if 'bound' not in a['name'] else act)['exported_W'][1], T_rej_K=u['T_rej_K'],
                            blade_fraction_plant=f_plant, blade_fraction_defense_warm=f_def, blade_fraction_total=f_plant+f_def,
                            closes_in_coast=f_plant+f_def <= 0.8,
                            low_section_heat_W=low, low_section_W=sections['LOW']['load_W'], low_ok=low <= sections['LOW']['load_W'],
                            coolant='Li or NaK primary, He-Xe Brayton working gas, NaK/organic to the blade channels (OPEN)',
                            heat_storage='none needed in steady coast; a defense heat buffer only for engagements beyond the channels'))
    P0 = design[1]/brayton_eff(T_rej, 1)
    transitions = dict(
        coast_to_burn='Warm channels drained and purged before the blades heat: L2 loses its coast sink. L2 steps down to hot standby and L1 '
                      'takes the ship load; L2 decay heat goes to the WARM section margin.',
        burn_decay_heat_W={f'{t}': decay_heat(P0, t, 6*YEAR) for t in (60, 3600, 86400, 10*86400)},
        warm_section_in_burn=dict(capacity_W=sections['WARM']['load_W'], high_thrust_warm_after_pumps_W=L['HIGH_THRUST']['heat_W']['WARM'],
                                  note='The WARM section rejects its 5 MW in every mode; plant decay heat (~0.05-0.1 MW after an hour) must fit '
                                       'beside the machinery base load or be heat-pumped (6 W of L1 work per W).'),
        l2_running_through_burn_extra_L1_W=design[1]*(1/brayton_eff(T_rej, 1)-1)*pl.pump_factor(s),
        burn_to_coast='Blades cool radiatively from 1800 K to below ~500 K in minutes (thin C/C sheets); hot-loop decay heat sets hours. '
                      'Channels refill and L2 restarts from hot standby; battery bridges minutes only.',
        drive_trip_in_burn='L1 lost with hot blades and drained channels: heat pumps stop, so the WARM section (5 MW) is free for L2 at reduced '
                           'power (~1.0-1.3 MWe at 25 % efficiency) until the channels refill: crew, cryo, nav keep running; proactive '
                           'defense (2.5 MW) cannot.',
        generator_trip='One unit lost: architecture-dependent (see reliability); the blade channels of the lost unit stay available.',
        heat_pump_trip='In a burn: warm heat beyond the WARM section has no sink; defense heat goes to Heat Debt (buffer OPEN) or the active '
                       'band is shed to proactive within the buffer time.',
        radiator_circuit_loss='Plants on separate blades (A on blade 1, B on blade 2) keep independent rejection paths; one shared manifold '
                              'would be a common mode that defeats plant redundancy.',
        emergency_rejection='LOW and WARM sections (1 + 5 MW) are the only surfaces that work in every mode; with blades hot and channels '
                            'drained they are the ship\'s whole emergency sink.')

    import mass_model, fuel_loads
    he3 = mass_model.stores_at(s, 1.0)['he3']; hl = fuel_loads.heat(s); cl = fuel_loads.cooling(s); lat = s['physics']['fuel_loads']['latent_J_kg']
    cp_he3 = (2.0e3, 3.0e3, 4.5e3); dT = (0.3, 0.2, 0.1)    # liquid He-3 near 3 K (STUDY), sealed hold until the vessel reaches its relief point
    cryo = dict(he3_inventory_kg=he3, he3_leak_uncooled_W=hl['helium_3']['total_W'], he3_stage_lift_W=cl['he3_stage_lift_W'],
                sealed_hold_h=[he3*cp_he3[i]*dT[i]/hl['helium_3']['total_W']/3600.0 for i in range(3)],
                loss_after_hold_t_per_day={k: v['uncooled_boiloff_kg_day']/1e3 for k, v in hl.items()},
                lose_3K_stage_only_t_per_day=cl['he3_stage_lift_W']*86400.0/lat['helium_3']/1e3,
                lose_20K_shield_keep_3K='the 3 K stage would have to lift the full 2.4 kW at 1500 W/W (3.5 MW): it cannot; He-3 warms as in a total loss',
                n_plus_1='Cryocooler trains as N+1 units split over buses A and B; the 3 K He-3 stage is the critical one (1.2 t/day if it alone fails, '
                         '24 t/day after the sealed hold if everything fails).',
                recovery='Re-cooling after a hold: a warmed vessel must be brought back below its relief point; with the 20 K shield back, the 3 K '
                         'stage recovers ~0.1 K a day per 100 W of spare lift (slow): spare lift capacity sets recovery.')
    res = dict(cryo=cryo, status='ISSA Phase II STUDY (NONCANON)', anchors=ANCHORS, components=COMP, shield_model=SHIELD, efficiency=EFF,
               demand=D, duty=dict(rows=duty_rows, buffers_kg=buffers, dust=dust_ctx, warm_channel_capacity_W=warm_cap,
                                   active_W=Pa, proactive_W=Pp, active_exported_W=Pexp),
               architectures=archs, rejection_temperature=t_sens, shield_cover_kg=shield_cover, shield_distance_kg=dist_sens,
               operating_modes=operating, L1=L1, L3=dict(scenarios=l3, radiation=rps_radiation), thermal=thermal, transitions=transitions)
    OUT.mkdir(exist_ok=True)
    (OUT/'phase2_eps_b.json').write_text(json.dumps(res, indent=1, default=lambda x: None if isinstance(x, float) and not math.isfinite(x) else str(x)))
    MW = lambda b: '/'.join(f'{x/1e6:.2f}' for x in b)
    print('demand MW', {k: MW(v) for k, v in D.items()})
    for a in archs:
        print(f"{a['name'][:44]:44s} units {a['units']} x {a['unit_W']/1e6:5.2f} MWe  mass t {'/'.join(f'{m/1e3:.0f}' for m in a['mass_kg'])}"
              f"  blade {a['blade_fraction_at_design']:.3f}  Pshort(mission,u=.05) {a['reliability']['u=0.05']['p_short_mission']:.4f}")
    print('shield cover kg', {k: round(v) for k, v in shield_cover.items()}, 'distance', {k: round(v) for k, v in dist_sens.items()})
    print('L1', MW(L1['with_open_planning_W']), 't', [round(x/1e3) for x in L1['mass_kg']])
    for sc, r in l3.items():
        print(sc, MW(r['P_W']), {n[:22]: {k: round(v/1e3, 1) for k, v in x.items()} for n, x in r['rows'].items()})
    for t in thermal:
        print(t['arch'][:30], f"eta {t['eta']:.3f} waste {t['conversion_waste_W']/1e6:.1f} MW f_plant {t['blade_fraction_plant']:.3f} f_def {t['blade_fraction_defense_warm']:.3f} LOW {t['low_section_heat_W']/1e6:.2f}/{t['low_section_W']/1e6:.1f}")
    print('decay', {k: round(v/1e3) for k, v in transitions['burn_decay_heat_W'].items()}, 'kW')


if __name__ == '__main__':
    main()
