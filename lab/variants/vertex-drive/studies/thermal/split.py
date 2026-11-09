"""T01 thermal study: component-level warm heat ledger and split radiator circuits for the Vertex generations.

  python3 lab/variants/vertex-drive/studies/thermal/split.py          # writes ledger.json and RESULTS.md here (about 10-15 min, 4 cores)
  python3 lab/variants/vertex-drive/studies/thermal/split.py --quick  # no gain-cliff bisections (about 2 min)

Adapter, not a new physics model. Every ship number is an FDP-1 calculator result (lab/variants/fdp1, run.solve with overrides), called
through convergence.py's helpers exactly as the Atlas does. Nothing in FDP-1, the four-burn engine, convergence.py or the registry is
changed.

The calculator has ONE warm radiator (one temperature, one areal mass, one transport mass per W). This script books the warm heat by
component, gives every component a circuit (coolant temperature, radiator technology), and collapses the circuits into the single
equivalent warm radiator that has exactly the same total planform area and the same total mass:

  A_i = Q_i / (2 eps_i sigma T_i^4)           area per circuit
  T_eq  from 2 eps_calc sigma T_eq^4 = sum Q_i / sum A_i      (eps_calc = 0.9, the scenario's warm emissivity)
  a_eq  = sum A_i a_i / sum A_i              areal mass, area-weighted
  t_eq  = sum Q_i t_i / sum Q_i              transport mass per W, heat-weighted

The equivalent radiator is then fed back to the calculator (warm T, areal, transport) and the house load (built bottom-up per pellet) is
fed back as house_fraction, until the circuit shares stop moving. Area and mass are reproduced exactly; what the calculator cannot see is
the number of separate loops (pumps, manifolds), which is booked as transport mass per W and pumping power.

Value labels (planning/HANDOFF.md): every scenario number below carries one of PUBLISHED / EXTRAPOLATION / ASSUMPTION / TARGET.
"""
import copy
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
VD = HERE.parents[1]
sys.path.insert(0, str(VD))
import convergence as C                      # noqa: E402  (read-only: generations, put, solve, bisect)

SIGMA = 5.670374419e-8
EPS_CALC = 0.9                               # scenario v1 warm emissivity; the equivalent temperature is defined against it
WARM_T = C.WARM
HOUSE = C.HOUSE
DRIVER = C.DRIVER
GAIN = C.GAIN
H2 = C.H2
AREAL = 'base.overrides.radiators.warm.areal_kg_m2.optimistic'
TRANSPORT = 'base.overrides.radiators.warm.transport_kg_per_W.optimistic'
CRYO = 'base.overrides.radiators.cryo.W_per_W.optimistic'
MAXREP = 'base.overrides.pulsed.max_rep_Hz.optimistic'
DRV_KG = 'base.overrides.pulsed.driver_kg_per_W.optimistic'

# ----------------------------------------------------------------------------------------------------------------------------------
# radiator technologies by temperature band (planform, two-sided; areal includes panel, fins/heat pipes or sheet, generator/collector)
# ----------------------------------------------------------------------------------------------------------------------------------
RADIATORS = {
    # name: areal kg/m2, transport kg/W, emissivity, valid band K, label, basis
    'TiH2O_HP':   {'areal': 3.0, 'transport': 5.0e-6, 'eps': 0.90, 'band': (300, 520), 'label': 'EXTRAPOLATION',
                   'basis': 'Ti-water heat pipes with C-C fins; water usable to about 500-550 K; NASA goal 2-3 kg/m2 (S-T01-NASA-ITHP, S-T01-TFAWS-2024)'},
    'HALIDE_HP':  {'areal': 5.0, 'transport': 5.0e-6, 'eps': 0.90, 'band': (450, 700), 'label': 'EXTRAPOLATION',
                   'basis': 'the 450-700 K heat-pipe gap: halide fluids in ceramic shells, AlN/AlBr3 radiator estimated 5.2 kg/m2 (S-T01-TFAWS-2024); life tests to about 673 K only'},
    'ALKALI_HP':  {'areal': 6.0, 'transport': 5.0e-6, 'eps': 0.85, 'band': (700, 1400), 'label': 'EXTRAPOLATION',
                   'basis': 'K/Na heat pipes, refractory or superalloy envelopes; tube-and-fin heat-pipe radiators 5-10 kg/m2 (S-T01-LDR-PATENT)'},
    'CALC_OPT':   {'areal': 1.0, 'transport': 2.0e-6, 'eps': 0.90, 'band': (300, 900), 'label': 'TARGET',
                   'basis': 'scenario v1 optimistic warm radiator, used by the Atlas at 600-800 K; no solid panel technology at 600-800 K reaches it'},
    'ADV_PANEL':  {'areal': 1.5, 'transport': 2.0e-6, 'eps': 0.90, 'band': (300, 750), 'label': 'TARGET',
                   'basis': 'a heat-pipe or pumped panel at about half of the NASA 2-3 kg/m2 goal, valid to 750 K: needs a working fluid for the gap'},
    'SN_DROPLET': {'areal': 0.6, 'transport': 2.0e-6, 'eps': 0.50, 'band': (520, 1000), 'label': 'TARGET',
                   'basis': 'tin droplet sheet (Sn 505-1000 K); sheet 0.1 kg/m2 estimated, generator/collector/pump dominate (S-MATTICK-LDR, S-T01-LDR-PATENT); '
                            'sheet emissivity 0.5 assumes an optically thick sheet of 0.1-0.2 droplets'},
}

# ----------------------------------------------------------------------------------------------------------------------------------
# driver loss by component (shares of the driver's wall-plug loss, P_drv - beam). EXTRAPOLATION from the HIF literature: core loss is the
# primary loss of an induction linac, pulser (modulator) efficiency 50-75 % (S-T01-HIF-EFF); the rest are engineering allocations.
# ----------------------------------------------------------------------------------------------------------------------------------
DRIVER_SPLIT = {
    'driver_induction_cores':    0.45,   # core loss and magnetising current (the primary loss, S-T01-HIF-EFF)
    'driver_modulators':         0.30,   # pulse-forming switches, SiC/GaN power stages, gate drives
    'driver_pulse_storage':      0.05,   # capacitor/inductive store dissipation (FDP-1 holds 5 pulses)
    'driver_ion_source':         0.04,   # sources, injector, low-energy front end
    'driver_busbars':            0.05,   # transmission and conversion between recovery, storage and cells
    'driver_magnet_cryoplant':   0.03,   # input power of the superconducting transport, arc and final-focus magnet cryoplant
    'driver_beam_loss_dumps':    0.08,   # halo scraping, dumps behind the dog-leg, final-focus heating
}

# the target factory, per pellet, built bottom-up (J per pellet unless marked); see REPORT.md section 3.1 for the derivation
FACTORY = {
    'conservative': {'cold_J': 100.0, 'cold_W_per_W_300K': 1000.0, 'fab_J': 8.0e6, 'inject_mass_kg': 1.34e-3, 'inject_eff': 0.10,
                     'magnetise_J': 2.0e5, 'controls_W': 20.0e6, 'trim_supplies_W': 10.0e6, 'pump_share': 0.015},
    'advanced':     {'cold_J': 100.0, 'cold_W_per_W_300K': 600.0, 'fab_J': 0.3e6, 'inject_mass_kg': 1.34e-3, 'inject_eff': 0.30,
                     'magnetise_J': 0.0, 'controls_W': 5.0e6, 'trim_supplies_W': 5.0e6, 'pump_share': 0.005},
}

# circuits: component -> (coolant/radiator temperature K, radiator technology, label, why)
CIRCUITS = {
    'demonstrated': {
        'driver_induction_cores':  (420, 'TiH2O_HP', 'PUBLISHED', 'FINEMET rated 150 C continuous (S-CORE-CURIE)'),
        'driver_modulators':       (420, 'TiH2O_HP', 'PUBLISHED', 'commercial SiC power modules Tj 175-200 C'),
        'driver_pulse_storage':    (400, 'TiH2O_HP', 'PUBLISHED', 'film/C0G pulse capacitors rated to about 200 C (S-T01-CAP-200C)'),
        'driver_ion_source':       (420, 'TiH2O_HP', 'PUBLISHED', 'as modulators'),
        'driver_busbars':          (420, 'TiH2O_HP', 'PUBLISHED', 'insulation class'),
        'driver_magnet_cryoplant': (320, 'TiH2O_HP', 'PUBLISHED', 'cryoplant compressors reject near ambient'),
        'driver_beam_loss_dumps':  (420, 'TiH2O_HP', 'PUBLISHED', 'dumps in the same loop'),
        'factory_cryoplant':       (320, 'TiH2O_HP', 'PUBLISHED', 'helium plants reject near ambient'),
        'factory_process':         (420, 'TiH2O_HP', 'PUBLISHED', 'electronics'),
        'injection':               (420, 'TiH2O_HP', 'PUBLISHED', 'electronics'),
        'magnetisation':           (420, 'TiH2O_HP', 'PUBLISHED', 'electronics'),
        'controls_and_trim':       (420, 'TiH2O_HP', 'PUBLISHED', 'electronics'),
        'radiator_pumps':          (420, 'TiH2O_HP', 'PUBLISHED', 'motor drives'),
        'nozzle_coil_cryo':        (320, 'TiH2O_HP', 'PUBLISHED', 'cryoplant'),
    },
    'conservative': {
        'driver_induction_cores':  (470, 'TiH2O_HP', 'EXTRAPOLATION', 'nanocrystalline cores 50 K above their 150 C rating, far below Curie 823-843 K'),
        'driver_modulators':       (500, 'TiH2O_HP', 'EXTRAPOLATION', 'SiC power modules with 250 C packaging (research modules), coolant 25 K below'),
        'driver_pulse_storage':    (440, 'TiH2O_HP', 'PUBLISHED', 'PEI film / C0G ceramic pulse capacitors rated 200 C (S-T01-CAP-200C)'),
        'driver_ion_source':       (500, 'TiH2O_HP', 'EXTRAPOLATION', 'as modulators'),
        'driver_busbars':          (500, 'TiH2O_HP', 'EXTRAPOLATION', 'polyimide/ceramic insulation'),
        'driver_magnet_cryoplant': (450, 'TiH2O_HP', 'EXTRAPOLATION', 'cryoplant hot side moved up into the electronics loop; input scaled to 450 K'),
        'driver_beam_loss_dumps':  (900, 'ALKALI_HP', 'EXTRAPOLATION', 'refractory dumps and final-focus shields on a potassium heat-pipe circuit'),
        'factory_cryoplant':       (450, 'TiH2O_HP', 'EXTRAPOLATION', 'as driver cryoplant'),
        'factory_process':         (500, 'TiH2O_HP', 'EXTRAPOLATION', 'electronics'),
        'injection':               (500, 'TiH2O_HP', 'EXTRAPOLATION', 'electronics'),
        'magnetisation':           (500, 'TiH2O_HP', 'EXTRAPOLATION', 'electronics'),
        'controls_and_trim':       (470, 'TiH2O_HP', 'EXTRAPOLATION', 'computing and control electronics'),
        'radiator_pumps':          (500, 'TiH2O_HP', 'EXTRAPOLATION', 'motor drives'),
        'nozzle_coil_cryo':        (450, 'TiH2O_HP', 'EXTRAPOLATION', 'cryoplant'),
    },
    'advanced': {
        'driver_induction_cores':  (640, 'ADV_PANEL', 'TARGET', 'HITPERM-class FeCo nanocrystalline cores at 673 K (Curie about 1,250 K; core loss at temperature unmeasured, S-T01-HITPERM)'),
        'driver_modulators':       (740, 'SN_DROPLET', 'TARGET', 'MW-class SiC/GaN power stages at 773 K (only 200-transistor logic ICs shown, S-NASA-SIC-500C)'),
        'driver_pulse_storage':    (550, 'SN_DROPLET', 'TARGET', 'mica/glass or ceramic pulse capacitors at 300 C (no rated part found)'),
        'driver_ion_source':       (740, 'SN_DROPLET', 'TARGET', 'as modulators'),
        'driver_busbars':          (740, 'SN_DROPLET', 'TARGET', 'ceramic insulation'),
        'driver_magnet_cryoplant': (700, 'SN_DROPLET', 'TARGET', 'cryoplant rejecting at 700 K; input scaled by Carnot'),
        'driver_beam_loss_dumps':  (1000, 'SN_DROPLET', 'TARGET', 'refractory dumps on the tin droplet sheet'),
        'factory_cryoplant':       (700, 'SN_DROPLET', 'TARGET', 'as driver cryoplant'),
        'factory_process':         (740, 'SN_DROPLET', 'TARGET', 'electronics at 773 K'),
        'injection':               (740, 'SN_DROPLET', 'TARGET', 'electronics at 773 K'),
        'magnetisation':           (740, 'SN_DROPLET', 'TARGET', 'electronics at 773 K'),
        'controls_and_trim':       (600, 'ADV_PANEL', 'TARGET', 'computing at 600 K'),
        'radiator_pumps':          (740, 'SN_DROPLET', 'TARGET', 'motor drives'),
        'nozzle_coil_cryo':        (700, 'SN_DROPLET', 'TARGET', 'cryoplant'),
    },
}
# the circuit set each scenario uses and its factory set
SCENARIO = {'demonstrated': 'conservative', 'conservative': 'conservative', 'advanced': 'advanced'}


def _variant(name, base, factory, tech=None, areal=None, eps=None):
    """A scenario that keeps `base`'s circuit temperatures but swaps the radiator technology (all circuits), its areal mass or the
    droplet sheet's emissivity. Registered at import so worker processes see it."""
    rows = {}
    for k, (T, t, label, why) in CIRCUITS[base].items():
        t2 = tech or t
        if areal is not None or eps is not None:
            r = dict(RADIATORS[t2]); key = f'{t2}_{name}'
            if areal is not None:
                r['areal'] = areal; r['label'] = 'TARGET'
            if eps is not None and t2.startswith('SN_DROPLET'):
                r['eps'] = eps
            RADIATORS[key] = r; t2 = key
        rows[k] = (T, t2, label, why)
    CIRCUITS[name] = rows; SCENARIO[name] = factory


# conservative temperatures with lighter radiators: separates the temperature effect from the areal-mass effect
for _a in (0.5, 1.0, 1.5, 2.0):
    _variant(f'cons_T_areal{_a:g}', 'conservative', 'conservative', areal=_a)
_variant('cons_T_calcopt', 'conservative', 'conservative', tech='CALC_OPT')
# advanced temperatures without droplets (solid panels everywhere), and the droplet sheet's emissivity band
_variant('adv_T_panel', 'advanced', 'advanced', tech='ADV_PANEL')
for _e in (0.3, 0.8):
    _variant(f'adv_eps{_e:g}', 'advanced', 'advanced', eps=_e)

NOZZLE_COIL_CRYO_W_COLD = 10.0e3            # static heat leak of the three loop cryostats at 20-40 K (about 1 W/m2 on about 1e4 m2)
CRYO_REF_T = 300.0                          # cryoplant W/W figures are quoted rejecting at 300 K


def carnot_scale(T_hot, T_cold, ref=CRYO_REF_T):
    """Input power multiplier when a cryoplant rejects at T_hot instead of the reference: (T_hot - Tc) / (ref - Tc) at fixed % Carnot."""
    return (T_hot - T_cold) / (ref - T_cold)


# ----------------------------------------------------------------------------------------------------------------------------------
# ledger
# ----------------------------------------------------------------------------------------------------------------------------------

def injection_speed(R, rule):
    """'fdp1' keeps the 400 m/s gas gun; 'one_in_flight' sets the speed so that only one target is in the open at a time (it leaves the
    shielded muzzle after the previous pulse and reaches the burn point before the next): v = path x rate."""
    if rule == 'fdp1':
        return R['injection']['speed_m_s']
    return R['injection']['path_m'] * R['fusion']['pellet_rate_Hz']


def components(R, scen, inject_rule='one_in_flight'):
    """Warm-loop heat (W) by component for one solved ship, built from the calculator's own ledger plus the bottom-up house load."""
    fu = R['fusion']; L = fu['ledger_W']; f = fu['pellet_rate_Hz']
    fac = FACTORY[SCENARIO[scen]]; circ = CIRCUITS[scen]
    out = {}
    drv = L['driver_loss']
    for k, s in DRIVER_SPLIT.items():
        out[k] = drv * s
    # the driver magnet cryoplant input was quoted at 300 K reject; rescale to its circuit temperature (cold end 4.5-20 K: use 10 K)
    out['driver_magnet_cryoplant'] *= carnot_scale(circ['driver_magnet_cryoplant'][0], 10.0)
    v_inj = injection_speed(R, inject_rule)
    tf_cold = fac['cold_J'] * fac['cold_W_per_W_300K'] * carnot_scale(circ['factory_cryoplant'][0], 1.5) * f
    out['factory_cryoplant'] = tf_cold
    out['factory_process'] = fac['fab_J'] * f
    out['injection'] = 0.5 * fac['inject_mass_kg'] * v_inj ** 2 / fac['inject_eff'] * f
    out['magnetisation'] = fac['magnetise_J'] * f
    out['controls_and_trim'] = fac['controls_W'] + fac['trim_supplies_W']
    # nozzle coils: the calculator's radiation-driven lift (cryo_input + radiation_on_conductor) plus the static leak at 30 W/W (300 K)
    out['nozzle_coil_cryo'] = (L['cryo_input'] + L['radiation_on_conductor']
                               + NOZZLE_COIL_CRYO_W_COLD * 30.0 * carnot_scale(circ['nozzle_coil_cryo'][0], 30.0))
    # pumping: a share of all pumped warm heat (heat pipes need none, so the share is an average); set after the rest is known
    pumped = sum(out.values())
    out['radiator_pumps'] = fac['pump_share'] * pumped / (1 - fac['pump_share'])
    return out, v_inj


def house_W(comp, R):
    """Electric house load fed back to the calculator: every booked watt that the calculator's ledger does not already hold as driver
    loss or radiation-driven coil cryo. This includes the Carnot surcharge when the driver magnet cryoplant rejects above 300 K and the
    static coil cryostat leak, so the calculator's warm total equals the component total and every watt is booked once."""
    L = R['fusion']['ledger_W']
    return sum(comp.values()) - L['driver_loss'] - L['cryo_input'] - L['radiation_on_conductor']


def equivalent(comp, scen):
    circ = CIRCUITS[scen]; rows = {}; A = Q = M = Tr = 0.0
    for k, q in comp.items():
        T, tech, label, why = circ[k]; rad = RADIATORS[tech]
        lo, hi = rad['band']
        flux = 2 * rad['eps'] * SIGMA * T ** 4; a = q / flux
        rows[k] = {'W': q, 'T_K': T, 'radiator': tech, 'label': label, 'why': why, 'flux_W_m2': flux, 'area_m2': a,
                   'mass_kg': a * rad['areal'] + q * rad['transport'], 'in_band': lo <= T <= hi}
        A += a; Q += q; M += rows[k]['mass_kg']; Tr += q * rad['transport']
    flux_eq = Q / A
    T_eq = (flux_eq / (2 * EPS_CALC * SIGMA)) ** 0.25
    areal_eq = (M - Tr) / A
    return {'rows': rows, 'Q_W': Q, 'area_m2': A, 'mass_kg': M, 'T_eq_K': T_eq, 'areal_eq_kg_m2': areal_eq, 'transport_eq_kg_W': Tr / Q,
            'heat_weighted_T_K': sum(r['W'] * r['T_K'] for r in rows.values()) / Q,
            'area_weighted_T_K': sum(r['area_m2'] * r['T_K'] for r in rows.values()) / A}


def split_solve(base_ov, scen, inject_rule='one_in_flight', iters=6):
    """Fixed point: solve, book components, set the equivalent warm radiator and the house fraction, solve again."""
    ov = copy.deepcopy(base_ov)
    # start from the V1 single loop
    hist = []; eq = None; comp = None; R = None
    for i in range(iters):
        R = C.fdp1.solve('baseline', ov)
        if not R.get('converged'):
            return {'converged': False, 'hist': hist, 'summary': C.fdp1.summary(R)}
        comp, v_inj = components(R, scen, inject_rule)
        eq = equivalent(comp, scen)
        h = house_W(comp, R) / R['fusion']['gross_fusion_power_W']
        new = {WARM_T: eq['T_eq_K'], AREAL: eq['areal_eq_kg_m2'], TRANSPORT: eq['transport_eq_kg_W'], HOUSE: h}
        hist.append({'departure_t': R['closure']['departure_t'], **{k.split('.')[-2] if k != HOUSE else 'house': v for k, v in new.items()}})
        moved = max(abs(new[k] / _get(ov, k, new[k]) - 1) for k in new)
        for k, v in new.items():
            C.put(ov, k, v)
        if i > 0 and moved < 1e-4:
            break
    R = C.fdp1.solve('baseline', ov)
    if not R.get('converged'):
        return {'converged': False, 'hist': hist, 'summary': C.fdp1.summary(R)}
    comp, v_inj = components(R, scen, inject_rule); eq = equivalent(comp, scen)
    return {'converged': True, 'overrides': ov, 'R': R, 'components': comp, 'equivalent': eq, 'injection_speed_m_s': v_inj, 'hist': hist}


def _get(tree, path, default):
    node = tree
    for k in path.split('.'):
        if not isinstance(node, dict) or k not in node:
            return default
        node = node[k]
    return node


def digest(R):
    """The numbers every table needs from one solved ship."""
    s = C.fdp1.summary(R)
    th = R['thermal']; rad = th['radiators']; lay = th['layouts'][th['selected_layout']]
    fu = R['fusion']; L = fu['ledger_W']; P = fu['gross_fusion_power_W']
    return {'departure_t': R['closure']['departure_t'], 'fusion_TW': P / 1e12, 'pellet_rate_Hz': fu['pellet_rate_Hz'],
            'yield_GJ': fu['yield_per_pulse_J'] / 1e9, 'warm_GW': th['circuits']['warm_total_W'] / 1e9, 'hot_GW': th['circuits']['hot_total_W'] / 1e9,
            'warm_km2': rad['warm']['planform_m2'] / 1e6, 'hot_km2': rad['hot']['planform_m2'] / 1e6, 'hot_extension_m2': rad['hot']['extension_m2'],
            'low_m2': th['low_loop']['area_m2'], 'warm_T_K': rad['warm']['T_K'], 'warm_areal': rad['warm']['areal_kg_m2'],
            'warm_radiator_t': rad['warm']['mass_kg'] / 1e3, 'hot_radiator_t': rad['hot']['mass_kg'] / 1e3,
            'layout': th['selected_layout'], 'wing_tip_m': lay['tip_radius_m'], 'wing_span_m': lay['span_m'], 'wing_root_m': lay.get('warm_root_radius_m'),
            'wing_length_m': R['layout']['wing_length'], 'spar_t': lay['extra_mass_kg'] / 1e3,
            'driver_t': R['drivers']['mass_kg'] / 1e3, 'house_fraction': L['electric_house'] / P, 'driver_loss_fraction': L['driver_loss'] / P,
            'ledger_sum': sum(L.values()) / P, 'injection_path_m': R['injection']['path_m'], 'pellets_in_flight_400': R['injection']['pellets_in_flight'],
            'xray_standoff_m': fu['xray_standoff_m'], 'checks_ok': all(c['ok'] for c in R['checks']), 'burn_years': s.get('burn_years'),
            'min_round_trip_years': s.get('min_round_trip_years')}


# ----------------------------------------------------------------------------------------------------------------------------------
# cases
# ----------------------------------------------------------------------------------------------------------------------------------

def base_overrides():
    G = C.generations()
    return {g: G[g]['overrides'] for g in ('V0', 'V1', 'V2')}


def case_list():
    B = base_overrides(); V1, V2 = B['V1'], B['V2']
    cases = [('V0', 'atlas', B['V0'], {}), ('V1', 'atlas', V1, {}), ('V2', 'atlas', V2, {})]
    for eta in (0.25, 0.30, 0.45):
        e = {DRIVER: eta}
        if eta != 0.45:
            cases += [(f'V1_eta{eta:.2f}', 'atlas', C.P(V1, **e), {}), (f'V2_eta{eta:.2f}', 'atlas', C.P(V2, **e), {})]
        for scen in ('conservative', 'advanced'):
            cases.append((f'S1_{scen}_eta{eta:.2f}', scen, C.P(V1, **e), {}))
        cases.append((f'S2_advanced_eta{eta:.2f}', 'advanced', C.P(V2, **e), {}))
    cases.append(('S1_demonstrated_eta0.30', 'demonstrated', C.P(V1, **{DRIVER: 0.30}), {}))
    for scen in [f'cons_T_areal{a:g}' for a in (0.5, 1.0, 1.5, 2.0)] + ['cons_T_calcopt', 'adv_T_panel', 'adv_eps0.3', 'adv_eps0.8']:
        cases.append((f'S1_{scen}_eta0.30', scen, C.P(V1, **{DRIVER: 0.30}), {}))
        cases.append((f'S1_{scen}_eta0.45', scen, V1, {}))
    # what FDP-1 itself needs: V0 with the warm radiator at the scenario's central areal mass, and at its central temperature
    cases += [('V0_areal2.5', 'atlas', C.P(B['V0'], **{AREAL: 2.5}), {}), ('V0_500K', 'atlas', C.P(B['V0'], **{WARM_T: 500.0}), {})]
    # the V0 -> V1 path one change at a time (Atlas single loop), then with the T01 house load in place of the 0.05 % target
    G0 = B['V0']
    step1 = C.P(G0, **{C.GALLERY: 4.5}); step2 = C.P(step1, **{H2: False}); step3 = C.P(step2, **{HOUSE: 5e-4})
    cases += [('step1_galleries', 'atlas', step1, {}), ('step2_noH2', 'atlas', step2, {}), ('step3_house0.05', 'atlas', step3, {}),
              ('step3b_house_bottomup_cons', 'atlas', step2, {'house_from': 'conservative'})]
    # D-04: idle hydrogen vessels kept
    for name, scen, ov in (('V1_keepH2', 'atlas', V1), ('S1_conservative_eta0.30_keepH2', 'conservative', C.P(V1, **{DRIVER: 0.30})),
                           ('S1_advanced_eta0.30_keepH2', 'advanced', C.P(V1, **{DRIVER: 0.30}))):
        cases.append((name, scen, C.P(ov, **{H2: True}), {}))
    # attribution of the V1 saving: house and temperature separately (Atlas single loop)
    cases += [('V1_house_bottomup_cons', 'atlas', C.P(V1, **{HOUSE: None}), {'house_from': 'conservative'}),
              ('V1_house_bottomup_adv', 'atlas', C.P(V1, **{HOUSE: None}), {'house_from': 'advanced'}),
              ('V1_areal_by_band_700K', 'atlas', C.P(V1, **{AREAL: 5.0, TRANSPORT: 5.0e-6}), {}),
              ('V2_areal_by_band_800K', 'atlas', C.P(V2, **{AREAL: 6.0, TRANSPORT: 5.0e-6}), {})]
    # driver mass per W (VTX-01B): the calculator's central and pessimistic tiers on the advanced case
    for kg in (0.075e-3, 0.1e-3, 0.15e-3, 0.2e-3):
        cases.append((f'S1_advanced_eta0.30_drvkg{kg*1e3:g}', 'advanced', C.P(V1, **{DRIVER: 0.30, DRV_KG: kg}), {}))
        cases.append((f'S1_advanced_eta0.45_drvkg{kg*1e3:g}', 'advanced', C.P(V1, **{DRV_KG: kg}), {}))
        cases.append((f'V1_drvkg{kg*1e3:g}', 'atlas', C.P(V1, **{DRV_KG: kg}), {}))
    # target injection: FDP-1's 400 m/s gas gun with the one-target-in-flight rule caps the pulse rate (sensitivity, see REPORT 3.1)
    for v in (400.0, 1000.0, 1500.0, 2500.0, 4000.0):
        cases.append((f'S1_advanced_eta0.30_vinj{v:g}', 'advanced', C.P(V1, **{DRIVER: 0.30}), {'v_inj_cap': v}))
    return cases


def house_only(R, scen):
    comp, _ = components(R, scen)
    return house_W(comp, R) / R['fusion']['gross_fusion_power_W']


def run_case(case):
    name, scen, ov, opt = case
    t = time.time()
    ov = copy.deepcopy(ov)
    if opt.get('house_from'):
        # Atlas single loop, but the house load is the bottom-up value of that scenario (fixed point on the house fraction only)
        C.put(ov, HOUSE, 5e-4)
        for _ in range(6):
            R = C.fdp1.solve('baseline', ov); h = house_only(R, opt['house_from'])
            if abs(h / _get(ov, HOUSE, h) - 1) < 1e-4:
                break
            C.put(ov, HOUSE, h)
        R = C.fdp1.solve('baseline', ov)
        return name, {'scenario': 'atlas', 'house_from': opt['house_from'], 'converged': bool(R.get('converged')), 'digest': digest(R),
                      'overrides': ov, 'secs': round(time.time() - t, 1)}
    if opt.get('v_inj_cap'):
        # the rate at which one target in flight at a time is possible with this launcher: f <= v / path, path ~ R_s ~ f^-1/2
        v = opt['v_inj_cap']; f_cap = 1000.0
        for _ in range(12):
            C.put(ov, MAXREP, f_cap)
            S = split_solve(ov, scen)
            if not S['converged']:
                break
            R = S['R']; f_new = v / R['injection']['path_m']
            if R['fusion']['pellet_rate_Hz'] < f_new * 0.999:
                f_cap = f_new; break                     # the cap does not bind: the optimiser's own rate is slower
            if abs(f_new / f_cap - 1) < 1e-3:
                break
            f_cap = f_new
        return name, _pack(name, scen, S, t, extra={'v_inj_cap_m_s': v, 'max_rep_Hz': f_cap})
    if scen == 'atlas':
        R = C.fdp1.solve('baseline', ov)
        return name, {'scenario': 'atlas', 'converged': bool(R.get('converged')), 'digest': digest(R) if R.get('converged') else None,
                      'overrides': ov, 'secs': round(time.time() - t, 1)}
    S = split_solve(ov, scen)
    return name, _pack(name, scen, S, t)


def _pack(name, scen, S, t, extra=None):
    if not S['converged']:
        return {'scenario': scen, 'converged': False, 'hist': S['hist'], 'secs': round(time.time() - t, 1), **(extra or {})}
    eq = S['equivalent']
    return {'scenario': scen, 'converged': True, 'digest': digest(S['R']), 'overrides': S['overrides'],
            'equivalent': {k: v for k, v in eq.items() if k != 'rows'}, 'circuits': eq['rows'],
            'injection_speed_m_s': S['injection_speed_m_s'], 'iterations': S['hist'],
            'booking_error': eq['Q_W'] / S['R']['thermal']['circuits']['warm_total_W'] - 1, 'secs': round(time.time() - t, 1), **(extra or {})}


def gain_cliff(item):
    """Lowest target gain at which the ship still closes, with the circuits re-booked at every gain (driver loss changes with gain)."""
    name, scen, ov = item
    t = time.time()
    if scen == 'atlas':
        g, _, _ = C.bisect(ov, GAIN, 100.0, 3000.0, C.closes, n=9, log=True)
        return name, {'gain_cliff': g, 'secs': round(time.time() - t, 1)}
    lo, hi = math.log(100.0), math.log(3000.0)
    ok = lambda g: split_solve(C.P(ov, **{GAIN: g}), scen, iters=4)['converged']
    if not ok(3000.0):
        return name, {'gain_cliff': None, 'secs': round(time.time() - t, 1)}
    if ok(100.0):
        return name, {'gain_cliff': 100.0, 'note': 'closes at 100', 'secs': round(time.time() - t, 1)}
    for _ in range(9):
        m = (lo + hi) / 2
        if ok(math.exp(m)):
            hi = m
        else:
            lo = m
    return name, {'gain_cliff': math.exp(hi), 'secs': round(time.time() - t, 1)}


# ----------------------------------------------------------------------------------------------------------------------------------
# report
# ----------------------------------------------------------------------------------------------------------------------------------

def fmt(x, d=0):
    if x is None:
        return '-'
    return f'{x:,.{d}f}'


def write_results(out):
    C_ = out['cases']; G = out.get('gain_cliffs', {})
    L = ['# T01 thermal study: results', '',
         '_Generated by `studies/thermal/split.py`; do not edit by hand. Every ship number is an FDP-1 calculator result (optimistic tier, '
         'four 0.016 c burns). "atlas" = the Atlas single warm loop; "conservative" / "advanced" / "demonstrated" = the split-circuit ledger '
         'collapsed into the equivalent warm radiator (same area, same mass) and fed back to the calculator._', '',
         '## Ships', '',
         '| Case | Scenario | Departure t | Fusion TW | Rate Hz | Warm GW | Warm T_eq K | Warm areal kg/m2 | Warm km2 | Wing tip m | Warm rad. t | House % fusion | Driver loss % | Gain cliff |',
         '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for n, r in C_.items():
        if not r.get('converged'):
            L.append(f'| {n} | {r["scenario"]} | does not close | | | | | | | | | | | {fmt(G.get(n, {}).get("gain_cliff"))} |')
            continue
        d = r['digest']
        L.append(f'| {n} | {r["scenario"]} | {fmt(d["departure_t"])} | {d["fusion_TW"]:.2f} | {d["pellet_rate_Hz"]:.1f} | {d["warm_GW"]:.2f} | '
                 f'{d["warm_T_K"]:.0f} | {d["warm_areal"]:.2f} | {d["warm_km2"]:.3f} | {fmt(d["wing_tip_m"])} | {fmt(d["warm_radiator_t"])} | '
                 f'{100*d["house_fraction"]:.4f} | {100*d["driver_loss_fraction"]:.4f} | {fmt(G.get(n, {}).get("gain_cliff"))} |')
    L += ['', '## Circuits (split cases)', '']
    for n, r in C_.items():
        if not r.get('circuits'):
            continue
        d = r['digest']; eq = r['equivalent']
        L += [f'### {n}', '',
              f'Warm {eq["Q_W"]/1e9:.2f} GW, {eq["area_m2"]/1e6:.3f} km2, {eq["mass_kg"]/1e3:,.0f} t; equivalent T {eq["T_eq_K"]:.0f} K, areal '
              f'{eq["areal_eq_kg_m2"]:.2f} kg/m2; heat-weighted T {eq["heat_weighted_T_K"]:.0f} K, area-weighted T {eq["area_weighted_T_K"]:.0f} K; '
              f'injection {r["injection_speed_m_s"]:,.0f} m/s; departure {d["departure_t"]:,.0f} t.', '',
              '| Component | MW | T K | Radiator | m2 | t | Label | In band |', '|---|---|---|---|---|---|---|---|']
        for k, c in sorted(r['circuits'].items(), key=lambda kv: -kv[1]['W']):
            L.append(f'| {k} | {c["W"]/1e6:,.1f} | {c["T_K"]} | {c["radiator"]} | {c["area_m2"]:,.0f} | {c["mass_kg"]/1e3:,.1f} | {c["label"]} | '
                     f'{"yes" if c["in_band"] else "NO"} |')
        L.append('')
    L += [f'Runtime {out["runtime_s"]:.0f} s.', '']
    (HERE / 'RESULTS.md').write_text('\n'.join(L))


def main(quick=False):
    t0 = time.time()
    cases = case_list()
    with ProcessPoolExecutor(max_workers=4) as ex:
        res = dict(ex.map(run_case, cases))
    out = {'version': 't01-v1', 'base_commit': '8de3ffa', 'cases': res}
    v0 = res['V0']['digest']['departure_t']
    out['v0_reproduces_fdp1'] = abs(v0 / 20760.0 - 1) < 0.01
    if not quick:
        names = ['V0', 'V1', 'V2', 'V1_eta0.30', 'V1_eta0.25', 'S1_conservative_eta0.45', 'S1_conservative_eta0.30', 'S1_conservative_eta0.25',
                 'S1_advanced_eta0.45', 'S1_advanced_eta0.30', 'S1_advanced_eta0.25', 'S2_advanced_eta0.30']
        lookup = {c[0]: c for c in cases}
        items = [(n, lookup[n][1], lookup[n][2]) for n in names if res[n].get('converged') or lookup[n][1] != 'atlas']
        with ProcessPoolExecutor(max_workers=4) as ex:
            out['gain_cliffs'] = dict(ex.map(gain_cliff, items))
    out['runtime_s'] = time.time() - t0
    (HERE / 'ledger.json').write_text(json.dumps(out, indent=1, default=float))
    write_results(out)
    print(f'V0 {v0:,.0f} t (reproduces FDP-1: {out["v0_reproduces_fdp1"]}); {len(res)} cases; {out["runtime_s"]:.0f} s')


if __name__ == '__main__':
    main(quick='--quick' in sys.argv)
