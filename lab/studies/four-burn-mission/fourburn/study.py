"""The study: canon audit, matrices A-E, mass cases, the 1 g check, mass-capped optimisation (Pareto), tank comparison, sensitivity,
fuel-ratio and dose estimates. Everything is deterministic; run.py writes the results."""
import math

from .const import C, G0, YEAR, DAY, AU, EPS_DHE3, MEV, he3_mass_share
from .canon import val, TIERS
from . import architectures, closure, kinematics, plasma, rocket, tanks, thermal

ARCH_TIERS = [(a, t) for a in ('IFD-C', 'IFD-CH', 'IFD-P', 'IFD-PH') for t in TIERS]
VE_GRID = [x*1e6 for x in (9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19.2011720, 20, 21, 22, 23)]


def dv(sc):
    return val(sc['mission']['target_speed_c'])*C


# ------------------------------------------------------------------ canon audit and the 147 t reconciliation
def canon_audit(sc, ref):
    op = ref['op']; ve = ref['ve_m_s']; d = dv(sc); R = rocket.mass_ratio(d, ve)
    led = rocket.ledger(op['mission']['end_mass_kg'], ve, d)
    sp = rocket.split(led['propellant_kg'], ve, ref['eta'], ref['burnup'], ref['recovery'], eps=ref['eps_J_kg'], he3_share=ref['he3_share'])
    # the 147 t: pass-5 one-way ship (case E: 1,900 t departure, 1,480 t at burnout, 180 t reserve) braking from cruise
    m_bo = op['design_ramp_1_5g']['burnout_mass_kg']; reserve = op['design_ramp_1_5g']['reserve_kg']
    brake_need = m_bo*(1-1/R)
    # tank-law check: operating_point.mission uses 0.15 kg per kg of capacity; the as-built farm is 11.4 kg/m3 by volume
    tank_model = ref['tank_dry_fraction']*led['propellant_kg']
    tank_built = ref['tanks']['dry_mass']['total_kg']
    end_built = op['mission']['end_mass_kg']-tank_model+tank_built
    led_built = rocket.ledger(end_built, ve, d)
    loaded = {k: v*1.0 for k, v in op['species_kg'].items()}
    cmp_canon = tanks.compare(loaded, sc, ref['density_kg_m3'])
    sp_b = rocket.split(led_built['propellant_kg'], ve, ref['eta'], ref['burnup'], ref['recovery'], eps=ref['eps_J_kg'], he3_share=ref['he3_share'])
    cmp_built = tanks.compare({'helium_3': sp_b['helium_3_kg'], 'deuterium': sp_b['deuterium_kg'], 'hydrogen': sp_b['hydrogen_kg']},
                              sc, ref['density_kg_m3'])
    # physics checks of the canon drive numbers
    part = plasma.partition(100.0, 100.0, 1.0, 0.5, 0.0)
    sp_phys = rocket.split(led['propellant_kg'], ve, 0.57, 1.0, 0.0)
    b_needed_phys = None if sp_phys is None else sp_phys['fused_share']
    return {'reproduced': {'departure_t': led['departure_kg']/1e3, 'end_t': led['end_kg']/1e3, 'propellant_t': led['propellant_kg']/1e3,
                           'burn_propellant_t': [x/1e3 for x in led['burn_propellant_kg']],
                           'species_t': {'helium_3': sp['helium_3_kg']/1e3, 'deuterium': sp['deuterium_kg']/1e3, 'hydrogen': sp['hydrogen_kg']/1e3},
                           'canon_species_t': {k: v/1e3 for k, v in op['species_kg'].items()},
                           'fused_t': sp['fused_kg']/1e3, 'recovered_t': sp['recovered_kg']/1e3, 'lost_t': sp['lost_unburned_kg']/1e3,
                           'mass_ratio_total': led['mass_ratio_total']},
            'shortfall_147t': {'burnout_t': m_bo/1e3, 'reserve_t': reserve/1e3, 'braking_need_t': brake_need/1e3,
                               'shortfall_t': (brake_need-reserve)/1e3,
                               'status': 'pass-5 one-way ship; superseded by pass 7 (four-burn propellant carried). The text '
                                         '"return braking short by 147 t (S&E 69)" in data/wayfarer_3d.toml [fuel_storage].open is stale.',
                               'stale_text_present': '147' in ref['fuel_storage_open_text']},
            'tank_law': {'model_tank_t': tank_model/1e3, 'as_built_tank_t': tank_built/1e3, 'difference_t': (tank_built-tank_model)/1e3,
                         'end_t_as_built': end_built/1e3, 'departure_t_as_built': led_built['departure_kg']/1e3,
                         'propellant_t_as_built': led_built['propellant_kg']/1e3,
                         'extra_propellant_t': (led_built['propellant_kg']-led['propellant_kg'])/1e3},
            'tanks_canon_split': cmp_canon, 'tanks_as_built_closure': cmp_built,
            'physics': {'computed_partition_100keV_1to1': part, 'canon_eta': ref['eta'],
                        'eta_upper_bound': part['charged_to_exhaust'],
                        'canon_burnup_x_recovery': {'burnup': ref['burnup'], 'recovery': ref['recovery']},
                        'fused_share_needed_at_eta_0.57_no_recovery': b_needed_phys,
                        'canon_absorbed_fraction': ref['absorbed_fraction']}}


# ------------------------------------------------------------------ matrices A, B, C
def matrix_A(sc, ref):
    rows = kinematics.accel_matrix(dv(sc), sc['mission']['accel_cases_g'], G0)
    ve = ref['ve_m_s']
    for r in rows:
        a = r['accel_g']*G0
        r['jet_power_MW_per_t_at_canon_ve'] = a*ve/2*1e3/1e6
        r['const_thrust_from_departure_days'] = kinematics.const_thrust(dv(sc), ve, a)['t_s']/DAY
    return rows


def matrix_B(sc, ref):
    out = {}
    for name, m_end in (('existing_final_1629t', ref['op']['mission']['end_mass_kg']), ('dry_1000t', val(sc['payload']['illustrative_dry_kg']))):
        out[name] = rocket.ve_matrix(m_end, dv(sc), [v*1e3 for v in sc['mission']['ve_cases_km_s']], ref['tank_dry_fraction'])
    return out


def matrix_C(sc, ref, iterated):
    rows = []; ve_c = ref['ve_m_s']
    eta_c = architectures.continuous(sc, 'central', 1e12, 9e6)['eta_jet']
    pc = architectures.pulsed(sc, 'central', 1e13, ve_c, tamper=True)
    heat_c = architectures.continuous(sc, 'central', 1e12, 9e6)['heat']['hot']+architectures.continuous(sc, 'central', 1e12, 9e6)['heat']['warm']
    heat_p = pc['heat']['hot']+pc['heat']['warm']
    masses = [('current departure', ref['op']['mission']['departure_mass_kg'], ve_c),
              ('current final', ref['op']['mission']['end_mass_kg'], ve_c)]
    for it in iterated:
        masses.append((f"iterated {it['arch']} {it['tier']}", it['departure_t']*1e3, it['ve_km_s']*1e3))
    for label, m, ve in masses:
        for ag in (0.001, 0.01, 0.1, 0.5, 1.0, 1.5):
            F = m*ag*G0; P = F*ve/2
            rows.append({'case': label, 'mass_t': m/1e3, 've_km_s': ve/1e3, 'accel_g': ag, 'thrust_MN': F/1e6, 'mass_flow_kg_s': F/ve,
                         'jet_power_TW': P/1e12, 'fusion_TW_canon_eta0.8': P/0.8/1e12, 'fusion_TW_continuous': P/eta_c/1e12,
                         'fusion_TW_pulsed': P/pc['eta_jet']/1e12, 'heat_GW_canon_4e-5': P/0.8*4e-5/1e9,
                         'heat_GW_continuous': P/eta_c*heat_c/1e9, 'heat_GW_pulsed': P/pc['eta_jet']*heat_p/1e9})
    return {'eta': {'canon': 0.8, 'continuous_central': eta_c, 'pulsed_central': pc['eta_jet']},
            'heat_fraction': {'canon': 4e-5, 'continuous_central': heat_c, 'pulsed_central': heat_p}, 'rows': rows}


# ------------------------------------------------------------------ mass-capped optimisation
def _m0(arch, tier, sc, ref, ve, a0, pay):
    r = closure.close(arch, tier, sc, ref, ve, a0, pay)
    return r


def best_at_cap(arch, tier, sc, ref, cap_t, pay, ves=VE_GRID, a_min=1e-6):
    """Shortest four-burn time with departure mass <= cap: for each ve the departure acceleration that just reaches the cap
    (bisection in log a0), then the best ve."""
    best = None
    a_max = val(sc['mission']['max_accel_g'])
    for ve in ves:
        lo = _m0(arch, tier, sc, ref, ve, a_min, pay)
        if not lo['converged'] or lo['departure_t'] > cap_t:
            continue
        hi = _m0(arch, tier, sc, ref, ve, a_max, pay)
        if hi['converged'] and hi['departure_t'] <= cap_t:
            r = hi
        else:
            la, lb = math.log(a_min), math.log(a_max); r = lo
            for _ in range(30):
                mid = (la+lb)/2; x = _m0(arch, tier, sc, ref, ve, math.exp(mid), pay)
                if x['converged'] and x['departure_t'] <= cap_t:
                    la = mid; r = x
                else:
                    lb = mid
                if lb-la < 1e-3:
                    break
        if best is None or r['burn_time_years'] < best['burn_time_years']:
            best = r
    return best


def min_mass(arch, tier, sc, ref, pay, ves=VE_GRID, a0=1e-6):
    best = None
    for ve in ves:
        r = _m0(arch, tier, sc, ref, ve, a0, pay)
        if r['converged'] and (best is None or r['departure_t'] < best['departure_t']):
            best = r
    return best


def pareto(sc, ref, pay, caps_t):
    out = {}
    for arch, tier in ARCH_TIERS:
        mm = min_mass(arch, tier, sc, ref, pay)
        pts = []
        if mm is not None:
            for cap in caps_t:
                if cap < mm['departure_t']*1.001:
                    continue
                b = best_at_cap(arch, tier, sc, ref, cap, pay)
                if b is not None:
                    pts.append(_summ(b))
        out[f'{arch}/{tier}'] = {'min_mass': None if mm is None else _summ(mm), 'front': _nondominated(pts),
                                 'reason': None if mm is not None else _why(arch, tier, sc, ref, pay)}
    return out


def _why(arch, tier, sc, ref, pay):
    reasons = set()
    for ve in VE_GRID:
        r = _m0(arch, tier, sc, ref, ve, 1e-6, pay)
        reasons.add(r.get('reason', ''))
    return sorted(reasons)


def _nondominated(pts):
    pts = sorted(pts, key=lambda p: (p['departure_t'], p['burn_time_years']))
    out = []; best_t = float('inf')
    for p in pts:
        if p['burn_time_years'] < best_t-1e-9:
            out.append(p); best_t = p['burn_time_years']
    return out


def _summ(r):
    A = r['architecture']
    return {'arch': r['arch'], 'tier': r['tier'], 've_km_s': r['ve_km_s'], 'a0_g': r['a0_g'], 'a_end_g': r['a_end_g'],
            'departure_t': r['departure_t'], 'end_t': r['end_t'], 'dry_t': r['dry_t'], 'drive_t': r['drive_t'], 'radiator_t': r['radiator_t'],
            'tank_t': r['tank_t'], 'reserve_t': r['reserve_t'], 'propellant_t': r['propellant_t'], 'species_t': r['species_t'],
            'fusion_power_TW': r['fusion_power_TW'], 'jet_power_TW': r['jet_power_TW'], 'thrust_MN': r['thrust_MN'],
            'eta_jet': A['eta_jet'], 'burn_fraction': A['burn_fraction'], 'heat_GW': r['heat_GW'],
            'radiator_area_km2': r['radiator_area_km2'], 'burn_time_years': r['burn_time_years'],
            'burn_days': [b['days'] for b in r['burns']], 'alpha_jet_kg_per_W': r['alpha_jet_kg_per_W'],
            'geometry': A.get('geometry', {}), 'tank_outcome': r['tanks']['outcome'], 'burn_propellant_t': r['burn_propellant_t'],
            'burn_start_t': r['burn_start_t'], 'fused_t': r['fused_t'], 'lost_unburned_t': r['lost_unburned_t']}


# ------------------------------------------------------------------ the 1 g question
def one_g(sc, ref, pay):
    """For each architecture/tier and exhaust velocity: does a ship sized for 1 g at departure close, and how much lighter per W
    would the drive have to be?"""
    RN = lambda ve: math.exp(4*dv(sc)/ve)
    al = closure.allowances(sc); extra = al['reserve']+al['residual']+al['boiloff']
    rows = []
    for arch, tier in [('CANON', 'central')]+ARCH_TIERS:
        for ve in (10e6, 13e6, 16e6, 19.2011720e6, 23e6):
            r = closure.close(arch, tier, sc, ref, ve, 1.0, pay)
            A = r['architecture']
            k = _tank_k(sc, ref, A, ve, tier)
            lin = 1-(k*(1+extra)+extra)*(RN(ve)-1)
            alpha_crit = 2*lin/(RN(ve)*G0*ve) if lin > 0 else 0.0
            a_jet = (A['alpha_hw']+A['alpha_rad'])/A['eta_jet'] if A.get('eta_jet') else None
            rows.append({'arch': arch, 'tier': tier, 've_km_s': ve/1e3, 'closes': r['converged'],
                         'departure_t': r.get('departure_t'), 'fusion_TW': r.get('fusion_power_TW'),
                         'reason': r.get('reason', ''), 'alpha_jet_kg_per_W': a_jet,
                         'alpha_needed_zero_payload_kg_per_W': alpha_crit,
                         'gap_factor': (a_jet/alpha_crit) if (a_jet and alpha_crit > 0) else None, 've_reachable': A.get('feasible', True)})
    return rows


def _tank_k(sc, ref, A, ve, tier):
    sp = rocket.split(1.0, ve, A['eta_jet'], A['burn_fraction'], A['recovery'], eps=A['eps'], he3_share=A['he3_share'])
    if sp is None:
        return float('inf')
    d = ref['density_kg_m3']; u = val(sc['tanks']['ullage']); m = val(sc['tanks']['mass_per_m3'], tier if A['arch'] != 'CANON' else 'central')
    return m*(1+u)*(sp['helium_3_kg']/d['helium_3']+sp['deuterium_kg']/d['deuterium']+sp['hydrogen_kg']/d['hydrogen'])


def accel_limit(arch, tier, sc, ref, pay, ves=VE_GRID):
    """Highest departure acceleration that still closes (any mass), per ve, by bisection on convergence."""
    best = None
    for ve in ves:
        lo = closure.close(arch, tier, sc, ref, ve, 1e-8, pay)
        if not lo['converged']:
            continue
        la, lb = math.log(1e-8), math.log(val(sc['mission']['max_accel_g']))
        top = closure.close(arch, tier, sc, ref, ve, math.exp(lb), pay)
        if top['converged']:
            a = math.exp(lb)
        else:
            for _ in range(50):
                mid = (la+lb)/2
                if closure.close(arch, tier, sc, ref, ve, math.exp(mid), pay)['converged']:
                    la = mid
                else:
                    lb = mid
            a = math.exp(la)
        if best is None or a > best[1]:
            best = (ve/1e3, a)
    return None if best is None else {'ve_km_s': best[0], 'a0_limit_g': best[1]}


# ------------------------------------------------------------------ matrix D (tanks) and E (architectures)
def matrix_D(configs):
    rows = []
    for c in configs:
        t = c['tanks']
        rows.append({'config': f"{c['arch']} {c['tier']} ve {c['ve_km_s']:.0f} km/s", 'species_t': c['species_t'],
                     'required_m3': t['required_m3'], 'existing_m3': t['existing_m3'], 'surplus_m3': t['surplus_m3'],
                     'ratio': t['ratio'], 'vessels_L_equivalent': t['vessels_L_equivalent'], 'farm_bays': t['farm_bays'],
                     'farm_length_m': t['farm_length_m'], 'axial_load_MN_1_5g': t['axial_load_N']/1e6,
                     'axial_vs_existing': t['axial_load_ratio'], 'cooling_MW': t['cooling_W']/1e6, 'tank_t': t['tank_mass_kg']/1e3,
                     'outcome': t['outcome']})
    return rows


def matrix_E(designs):
    rows = []
    for key, d in designs.items():
        if d is None:
            continue
        arch = d['arch']
        rows.append({'design': key, 'arch': arch, 'tier': d['tier'], 've_km_s': d['ve_km_s'], 'fusion_TW': d['fusion_power_TW'],
                     'eta_jet': d['eta_jet'], 'hot_heat_fraction': d['heat_GW']['hot']/d['fusion_power_TW']/1e3,
                     'warm_heat_fraction': d['heat_GW']['warm']/d['fusion_power_TW']/1e3, 'radiator_t': d['radiator_t'],
                     'radiator_km2': sum(d['radiator_area_km2'].values()), 'propellant_t': d['propellant_t'], 'dry_t': d['dry_t'],
                     'departure_t': d['departure_t'], 'a0_g': d['a0_g'], 'burn_time_years': d['burn_time_years'],
                     'helium_3_t': d['species_t']['helium_3'], 'classification': architectures.CLASS[arch]})
    return rows


# ------------------------------------------------------------------ sensitivity (one-at-a-time tier swaps)
SENS_KEYS = [('pulsed', 'gain'), ('pulsed', 'driver_efficiency'), ('pulsed', 'driver_kg_per_W'), ('pulsed', 'nozzle_efficiency'),
             ('pulsed', 'max_rep_Hz'), ('pulsed', 'rho_g_cc'), ('pulsed', 'fluence_J_m2'), ('pulsed', 'hardware_solid_angle'),
             ('pulsed', 'brems_dense'), ('pulsed', 'recovery_efficiency'), ('pulsed', 'nozzle_kg_per_J'), ('pulsed', 'loop_armor_kg_m2'),
             ('pulsed', 'other_kg_per_W'), ('radiators', 'warm'), ('radiators', 'hot'), ('radiators', 'droplet'), ('tanks', 'mass_per_m3')]


def _swap(sc, sec, key, tier, base):
    import copy
    s = copy.deepcopy(sc)
    node = s[sec][key]
    if sec == 'radiators':
        for kk in ('T_K', 'areal_kg_m2', 'transport_kg_per_W'):
            if isinstance(node.get(kk), dict) and base in node[kk]:
                node[kk][base] = node[kk][tier]
    elif isinstance(node, dict) and base in node:
        node[base] = node[tier]
    return s


def sensitivity(sc, ref, arch, base_tier, cap_t, pay):
    base = best_at_cap(arch, base_tier, sc, ref, cap_t, pay)
    out = {'base': _summ(base) if base else None, 'rows': []}
    for sec, key in SENS_KEYS:
        row = {'parameter': f'{sec}.{key}'}
        for t in ('optimistic', 'pessimistic'):
            if t == base_tier:
                continue
            s2 = _swap(sc, sec, key, t, base_tier)
            r = best_at_cap(arch, base_tier, s2, ref, cap_t, pay)
            row[t] = None if r is None else r['burn_time_years']
        out['rows'].append(row)
    return out


# ------------------------------------------------------------------ fuel ratio and plasma temperature
def fuel_ratio(sc):
    rows = []
    for r in (0.25, 0.5, 1.0, 1.5, 2.0, 3.0):
        for Ti, tet in ((80, 1.0), (100, 0.85), (120, 0.6)):
            p = plasma.partition(Ti, Ti*tet, r, 0.5, 0.0)
            rows.append({'he3_to_d': r, 'he3_mass_share': he3_mass_share(r), 'Ti_keV': Ti, 'Te_over_Ti': tet, 'brems': p['brems'],
                         'neutron': p['neutron'], 'charged': p['charged_to_exhaust'], 'Zeff': p['Zeff'],
                         'power_density_rel': plasma.fusion_power_density(1e20, Ti, r)/plasma.fusion_power_density(1e20, 100, 1.0)})
    return rows


# ------------------------------------------------------------------ crew dose from the drive (unshielded, for shield sizing)
def dose(design, distance_m=150.0):
    """Neutron and X-ray energy flux at the crew distance and the shadow-shield attenuation needed for 20 mSv/yr over the burns.
    H*(10) per fluence: 2.45 MeV ~ 4.2e-10 Sv cm2, 14 MeV ~ 5.2e-10 Sv cm2 (ICRP 74 order)."""
    A = design['architecture']; P = design['fusion_power_TW']*1e12
    if A['arch'] in ('IFD-C', 'IFD-CH'):
        n_W = P*A['partition']['neutron']; E = 3.5
    elif 'neutron_escape' in A.get('geometry', {}):
        n_W = P*A['geometry']['neutron_escape']; E = 10.0
    else:                                   # CANON states no neutron share: use the 100 keV 1:1 D-3He plasma value
        from . import plasma
        n_W = P*plasma.partition(100.0, 100.0, 1.0, 0.5)['neutron']; E = 3.5
    rate = n_W/(E*MEV); flux_cm2_s = rate/(4*math.pi*(distance_m*100)**2)
    sv_h = flux_cm2_s*4.6e-10*3600
    years = design['burn_time_years']; limit = 0.02
    need = sv_h*years*YEAR/3600/limit
    return {'distance_m': distance_m, 'neutron_W': n_W, 'unshielded_Sv_per_h': sv_h, 'attenuation_needed': need,
            'decades': math.log10(max(need, 1.0)), 'LiH_m': 0.3*math.log10(max(need, 1.0))}
