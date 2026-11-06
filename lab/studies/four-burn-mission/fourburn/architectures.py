"""Drive architectures as functions of fusion power and exhaust velocity.

Each model returns, per W of gross fusion power, an energy ledger that closes to 1 (+ the driver's beam energy for pulsed), the heat
per radiator class, the hardware and radiator specific masses (kg/W), the reachable exhaust velocity and the burn fraction, plus the
fixed masses (shadow shields) and geometry. Mass closure (closure.py) multiplies these by the power the ship needs.

  CANON   the working operating point (physics.operating_point), audited: eta 0.8, burnup 0.8, recovery 0.95, absorbed 4e-5.
  IFD-C   continuous open-cage linear D-3He core, Fiji-amplified sparse coils, steady magnetic nozzle, 1800 K heat-pipe radiators.
  IFD-CH  IFD-C with flowing liquid-lithium armour films, hydrogen mass augmentation and the lighter hot radiator.
  IFD-P   pulsed point burn of magnetised fuel-only targets (v4 IFD-P), stand-off heavy-ion driver, Fiji nozzle loops.
  IFD-PH  IFD-P with a hydrogen propellant tamper (captures X-rays and neutrons, sets ve), free pulse rate, lighter radiators.
"""
import math

from .const import EPS_DHE3, MU0, KEV, he3_mass_share
from .canon import val
from . import plasma, thermal

ARCHS = ('CANON', 'IFD-C', 'IFD-CH', 'IFD-P', 'IFD-PH')
CLASS = {'CANON': 'unsupported (no mechanism for eta 0.8 with 0.26 neutral share, recovery 0.95 or absorbed 4e-5)',
         'IFD-C': 'credible extrapolation (open-cage D-3He core, tau_p above 1 s needs Fiji stabilisation)',
         'IFD-CH': 'highly speculative engineering (flowing Li armour at 30 MW/m2)',
         'IFD-P': 'highly speculative engineering (D-3He ignition, rhoR >= 40 g/cm2, target gain 300 central / 3,000 optimistic tier)',
         'IFD-PH': 'highly speculative engineering (D-3He ignition, target gain 300 central / 3,000 optimistic tier, tamper-captured X-rays)'}


def _ledger_check(L, total):
    s = sum(L.values())
    if abs(s-total) > 1e-9:
        raise AssertionError(f'energy ledger sums to {s}, expected {total}: {L}')


def canon_ref(sc, ref, tier, P_fus, ve):
    th = thermal.classes(sc, tier)
    eta = ref['eta']; f = ref['absorbed_fraction']; b = ref['burnup']; r = ref['recovery']
    L = {'jet': eta, 'hot_heat': f, 'to_space': 1-eta-f}
    _ledger_check(L, 1.0)
    from .rocket import ve_max
    alpha_hw = ref['mass_budget']['drive_package']/2.6126510418e14
    return {'arch': 'CANON', 'tier': tier, 'eta_jet': eta, 'burn_fraction': b, 'recovery': r, 'ledger': L,
            've_max': ve_max(eta, b, r, eps=ref['eps_J_kg']), 'eps': ref['eps_J_kg'], 'he3_share': ref['he3_share'],
            'heat': {'hot': f, 'warm': 0.0}, 'alpha_hw': alpha_hw, 'alpha_rad': f*th['hot']['kg_per_W'], 'radiators': th,
            'fixed_kg': 0.0, 'geometry': {'note': 'canon allowance 250 t drive at 261 TW'}, 'feasible': True, 'reason': ''}


def continuous(sc, tier, P_fus, ve, liquid_wall=False, he3_to_d=None):
    c = sc['continuous']; pl = sc['plasma']
    Ti = val(pl['Ti_keV'], tier); Te = Ti*val(pl['Te_over_Ti'], tier); rr = val(pl['he3_to_d']) if he3_to_d is None else he3_to_d
    part = plasma.partition(Ti, Te, rr, val(pl['tritium_burn']), val(pl['sync_fraction'], tier))
    f_rad = part['neutron']+part['brems']+part['sync']; f_c = part['charged_to_exhaust']
    B_max = val(c['field_T'], tier); beta = val(c['beta']); k = val(c['wall_to_plasma_radius'])
    q = val((sc['liquid_wall'] if liquid_wall else c)['wall_flux_MW_m2'], tier)*1e6
    sig_s = val((sc['liquid_wall'] if liquid_wall else c)['armour_shield_kg_m2'], tier)
    cov = val(c['coil_coverage'], tier); L_max = val(c['core_length_max_m'], tier); sig_sh = val(c['shadow_shield_kg_m2'], tier)
    tau_p = val(c['tau_p_s'], tier)
    th = thermal.best_hot(sc, tier) if liquid_wall else thermal.classes(sc, tier)
    P_int = cov*f_rad; lift = val(c['neutron_leak_to_cryo'])*P_int; cryo_in = lift*th['cryo_W_per_W']
    house = val(c['house_fraction']); P_e = house+cryo_in; eta_dc = val(c['direct_conversion_efficiency'], tier)
    P_ext = P_e/eta_dc; eta_n = val(c['nozzle_efficiency'], tier); ptw = val(c['plume_to_hardware'])
    stream = f_c-P_ext
    jet = eta_n*stream; plume = (1-eta_n)*stream
    L = {'jet': jet, 'plume_to_space': plume*(1-ptw), 'plume_to_hardware': plume*ptw, 'direct_conversion_loss': P_ext-P_e,
         'electric_house': house, 'cryo_input': cryo_in, 'radiation_on_armour': P_int-lift, 'radiation_on_conductor': lift,
         'radiation_to_space': (1-cov)*f_rad}
    _ledger_check(L, 1.0)
    hot = L['plume_to_hardware']+L['direct_conversion_loss']+L['radiation_on_armour']
    warm = house+cryo_in+lift
    alpha_shield = cov*f_rad*sig_s/q
    alpha_other = val(c['other_kg_per_W'], tier)
    alpha_rad = hot*th['hot']['kg_per_W']+warm*th['warm']['kg_per_W']
    from .rocket import ve_max

    def at_field(B):
        """Core at field B (<= the Fiji limit) at the beta limit and the wall-flux limit; cores of at most L_max."""
        p_mag = B**2/(2*MU0); ni_per_ne = (1+rr)/(1+2*rr)
        n_e = beta*p_mag/((Te+ni_per_ne*Ti)*KEV)
        p_f = plasma.fusion_power_density(n_e, Ti, rr); tau_f = plasma.fuel_burn_time_s(n_e, Ti, rr)
        b = plasma.continuous_burn_fraction(tau_p, tau_f)
        a_p = 2*k*q/(f_rad*p_f); per_m = p_f*math.pi*a_p**2
        cores = max(1, math.ceil(P_fus/(per_m*L_max))); P_core = P_fus/cores
        alpha_coil = val(c['coil_structure_kg_per_J'], tier)*p_mag*k**2/p_f
        shadow = cores*sig_sh*math.pi*(k*a_p+1.0)**2
        vmax = ve_max(jet, b, 0.0)
        return {'B': B, 'n_e': n_e, 'p_f': p_f, 'tau_f': tau_f, 'b': b, 'a_p': a_p, 'cores': cores, 'P_core': P_core,
                'length': P_core/per_m, 'alpha_coil': alpha_coil, 'shadow_kg': shadow, 'vmax': vmax,
                'total': (alpha_coil+alpha_shield+alpha_other+alpha_rad+shadow/P_fus)/jet}

    grid = [at_field(B_max*(i/24)) for i in range(4, 25)]
    ok = [g for g in grid if g['vmax'] >= ve*(1-1e-12)]
    g = min(ok, key=lambda x: x['total']) if ok else max(grid, key=lambda x: x['vmax'])
    B, n_e, p_f, tau_f, b, a_p, cores = g['B'], g['n_e'], g['p_f'], g['tau_f'], g['b'], g['a_p'], g['cores']
    alpha_coil = g['alpha_coil']; length = g['length']
    vmax = g['vmax']
    feasible = ve <= vmax*(1+1e-12) and jet > 0
    return {'arch': 'IFD-CH' if liquid_wall else 'IFD-C', 'tier': tier, 'eta_jet': jet, 'burn_fraction': b, 'recovery': 0.0,
            'partition': part, 'ledger': L, 've_max': vmax, 'eps': EPS_DHE3, 'he3_share': he3_mass_share(rr),
            'heat': {'hot': hot, 'warm': warm, 'cryo_lift': lift}, 'alpha_hw': alpha_coil+alpha_shield+alpha_other,
            'alpha_parts': {'coil_structure': alpha_coil, 'armour_shield': alpha_shield, 'other': alpha_other},
            'alpha_rad': alpha_rad, 'radiators': th, 'fixed_kg': g['shadow_kg'],
            'geometry': {'field_T': B, 'n_e_m3': n_e, 'power_density_W_m3': p_f, 'tau_burn_s': tau_f, 'tau_p_s': tau_p,
                         'tau_p_needed_for_ve_s': plasma.tau_p_needed(min(0.999, ve**2/(2*jet*EPS_DHE3)), tau_f), 'plasma_radius_m': a_p, 'wall_radius_m': k*a_p, 'cores': cores,
                         'core_length_m': length, 'wall_flux_MW_m2': q/1e6, 'armour_area_m2': cov*f_rad*P_fus/q},
            'feasible': feasible, 'reason': '' if feasible else f've {ve/1e3:.0f} km/s above the reachable {vmax/1e3:.0f} km/s'}


def _pulse(sc, tier, rhoR, mu_t):
    """Energy ledger per W fusion for one pulse geometry (fuel rhoR kg/m2, hydrogen tamper mu_t kg per kg fuel)."""
    p = sc['pulsed']; c = sc['continuous']
    G = val(p['gain'], tier); eta_d = val(p['driver_efficiency'], tier); eta_r = val(p['recovery_efficiency'], tier)
    eta_n = val(p['nozzle_efficiency'], tier); Om = val(p['hardware_solid_angle'], tier); ptw = val(c['plume_to_hardware'])
    T = val(p['burn_T_keV']); part = plasma.partition(T, T, 1.0, val(p['dense_tritium_burn']))
    f_n = part['neutron']; f_x = val(p['brems_dense'], tier)
    rhoR_g = rhoR/10.0; rhoR_H_g = mu_t*rhoR_g/3.0
    tau_x = p['xray_kappa_cm2_g']['fuel']*rhoR_g+p['xray_kappa_cm2_g']['hydrogen']*rhoR_H_g
    tau_n = p['neutron_kappa_cm2_g']['fuel']*rhoR_g+p['neutron_kappa_cm2_g']['hydrogen']*rhoR_H_g
    esc_x = f_x*plasma.escape_probability(tau_x); esc_n = f_n*math.exp(-tau_n)
    th_best = thermal.best_hot(sc, tier)
    leak = val(p['neutron_leak_to_cryo']); caught = Om*(esc_x+esc_n); lift = leak*caught
    cryo_in = lift*th_best['cryo_W_per_W']; house = val(p['house_fraction'])
    P_drv = 1/(G*eta_d); P_e = P_drv+house+cryo_in; P_ext = P_e/eta_r
    plasma_E = 1+1/G-esc_x-esc_n
    stream = plasma_E-P_ext
    jet = eta_n*stream; plume = (1-eta_n)*stream
    L = {'jet': jet, 'plume_to_space': plume*(1-ptw), 'plume_to_hardware': plume*ptw, 'recovery_loss': P_ext-P_e,
         'driver_loss': P_drv-1/G, 'electric_house': house, 'cryo_input': cryo_in, 'radiation_on_hardware': caught-lift,
         'radiation_on_conductor': lift, 'radiation_to_space': (1-Om)*(esc_x+esc_n)}
    _ledger_check(L, 1.0)      # the driver's beam energy (1/G) is recirculated from the recovered expansion energy
    hot = L['plume_to_hardware']+L['recovery_loss']+L['radiation_on_hardware']
    warm = L['driver_loss']+house+cryo_in+lift
    return {'ledger': L, 'eta_jet': jet, 'heat': {'hot': hot, 'warm': warm, 'cryo_lift': lift}, 'esc_x': esc_x, 'esc_n': esc_n,
            'P_driver_e': P_drv, 'gain': G, 'radiators': th_best, 'part': part}


def pulsed(sc, tier, P_fus, ve, tamper=False):
    p = sc['pulsed']; rho = val(p['rho_g_cc'], tier)*1000.0; H_B = plasma.burn_parameter_kg_m2(val(p['burn_T_keV']),
                                                                                              calib_DT_g_cm2=p['HB_calibration']['DT_20keV_g_cm2'])
    fmax = val(p['max_rep_Hz'], tier); eps = EPS_DHE3

    def design(f):
        """Pulse at rate f: yield E = P/f, then the fuel rhoR that yields it with its own burn fraction, then the tamper for ve."""
        E = P_fus/f; b = 0.5
        for _ in range(200):
            m_f = E/(b*eps); rhoR = (3*m_f*rho**2/(4*math.pi))**(1/3); b_new = plasma.pulsed_burn_fraction(rhoR, H_B)
            if abs(b_new-b) < 1e-12:
                break
            b = b_new
        mu = 0.0
        for _ in range(200):
            q = _pulse(sc, tier, rhoR, mu); mu_new = 2*q['eta_jet']*b*eps/ve**2-1
            if not tamper or mu_new <= 0:
                mu_new = 0.0
            if abs(mu_new-mu) < 1e-10:
                break
            mu = mu_new
        q = _pulse(sc, tier, rhoR, mu)
        v_reach = math.sqrt(2*q['eta_jet']*b*eps/(1+mu))
        return E, b, rhoR, m_f, mu, q, v_reach

    if tamper:
        seen = []

        def cost(lf):
            f = 10**lf; E, b, rhoR, m_f, mu, q, vr = design(f)
            a = _alpha_pulsed(sc, tier, q, E, f, P_fus)
            tot = (a['alpha_hw']+a['alpha_rad'])/q['eta_jet']
            short = max(0.0, 1-vr/ve)
            out = ((tot if short == 0 else math.inf), (f, E, b, rhoR, m_f, mu, q, vr, a, short))
            seen.append(out)
            return out
        lmax = math.log10(fmax); grid = [lmax-i/4 for i in range(29)]
        vals = [cost(lf) for lf in grid]
        i = min(range(len(grid)), key=lambda j: vals[j][0])
        lo, hi = grid[min(i+1, len(grid)-1)], grid[max(i-1, 0)]
        g = (math.sqrt(5)-1)/2
        x1, x2 = hi-g*(hi-lo), lo+g*(hi-lo); c1, c2 = cost(x1)[0], cost(x2)[0]
        for _ in range(60):                        # golden section: the optimum rate is a continuous function of power
            if c1 < c2 or (math.isinf(c1) and math.isinf(c2)):     # unreachable ve lies at high rates (small pulses)
                hi, x2, c2 = x2, x1, c1; x1 = hi-g*(hi-lo); c1 = cost(x1)[0]
            else:
                lo, x1, c1 = x1, x2, c2; x2 = lo+g*(hi-lo); c2 = cost(x2)[0]
            if hi-lo < 1e-7:
                break
        cost((lo+hi)/2)
        _, (f, E, b, rhoR, m_f, mu, q, vr, a, short) = min(seen, key=lambda c: c[0])
        ok = short == 0
        return _pack('IFD-PH', tier, q, a, b, rhoR, m_f, mu, E, f, vr, ok, '' if ok else f've {ve/1e3:.0f} km/s not reachable at any rate', sc)
    # fuel-only: the burn fraction that gives exactly ve (fixed point through the X-ray escape), then the pulse size and rate
    b = 0.7
    for _ in range(300):
        rhoR = plasma.rhoR_needed(min(b, 0.999), H_B); q = _pulse(sc, tier, rhoR, 0.0)
        b_new = ve**2/(2*q['eta_jet']*eps)
        if b_new >= 0.999:
            return _pack('IFD-P', tier, q, _alpha_pulsed(sc, tier, q, 1.0, 1.0, P_fus), b_new, rhoR, 0, 0, 0, 0,
                         math.sqrt(2*q['eta_jet']*0.999*eps), False, f've {ve/1e3:.0f} km/s needs burn fraction {b_new:.2f}', sc)
        if abs(b_new-b) < 1e-12:
            break
        b = b_new
    rhoR = plasma.rhoR_needed(b, H_B); m_f = 4/3*math.pi*rhoR**3/rho**2; E = b*m_f*eps; f = P_fus/E
    q = _pulse(sc, tier, rhoR, 0.0); a = _alpha_pulsed(sc, tier, q, E, f, P_fus)
    ok = f <= fmax
    return _pack('IFD-P', tier, q, a, b, rhoR, m_f, 0.0, E, f, ve, ok, '' if ok else f'needs {f:.0f} Hz > {fmax:.0f} Hz', sc)


def _alpha_pulsed(sc, tier, q, E, f, P_fus):
    p = sc['pulsed']; th = q['radiators']
    fl = val(p['fluence_J_m2'], tier); R_s = math.sqrt(max(E*q['esc_x'], 1e-30)/(4*math.pi*fl))
    alpha_noz = val(p['nozzle_kg_per_J'], tier)*val(p['nozzle_field_energy_ratio'])*(1-q['esc_x']-q['esc_n'])/f
    armour = val(p['hardware_solid_angle'], tier)*4*math.pi*R_s**2*val(p['loop_armor_kg_m2'], tier)
    alpha_drv = val(p['driver_kg_per_W'], tier)*q['P_driver_e']
    alpha_other = val(p['other_kg_per_W'], tier)
    alpha_rad = q['heat']['hot']*th['hot']['kg_per_W']+q['heat']['warm']*th['warm']['kg_per_W']
    return {'alpha_hw': alpha_noz+alpha_drv+alpha_other+armour/P_fus, 'alpha_rad': alpha_rad, 'standoff_m': R_s,
            'alpha_parts': {'nozzle_structure': alpha_noz, 'driver': alpha_drv, 'loop_armour': armour/P_fus, 'other': alpha_other}}


def _pack(name, tier, q, a, b, rhoR, m_f, mu, E, f, vr, ok, reason, sc):
    return {'arch': name, 'tier': tier, 'eta_jet': q['eta_jet'], 'burn_fraction': b, 'recovery': 0.0, 'ledger': q['ledger'],
            've_max': vr, 'eps': EPS_DHE3, 'he3_share': he3_mass_share(1.0), 'heat': q['heat'], 'alpha_hw': a['alpha_hw'],
            'alpha_parts': a['alpha_parts'], 'alpha_rad': a['alpha_rad'], 'radiators': q['radiators'],
            'fixed_kg': val(sc['pulsed']['shadow_shield_kg']), 'tamper_per_fuel': mu,
            'geometry': {'fuel_rhoR_g_cm2': rhoR/10, 'fuel_mass_g': m_f*1e3, 'yield_J': E, 'yield_t_TNT': E/4.184e9, 'rep_Hz': f,
                         'standoff_m': a['standoff_m'], 'xray_escape': q['esc_x'], 'neutron_escape': q['esc_n'], 'gain': q['gain'],
                         'tamper_per_fuel': mu},
            'feasible': ok, 'reason': reason}


def evaluate(arch, sc, tier, P_fus, ve, ref=None, **kw):
    if arch == 'CANON':
        return canon_ref(sc, ref, tier, P_fus, ve)
    if arch == 'IFD-C':
        return continuous(sc, tier, P_fus, ve, **kw)
    if arch == 'IFD-CH':
        return continuous(sc, tier, P_fus, ve, liquid_wall=True, **kw)
    if arch == 'IFD-P':
        return pulsed(sc, tier, P_fus, ve)
    if arch == 'IFD-PH':
        return pulsed(sc, tier, P_fus, ve, tamper=True)
    raise KeyError(arch)
