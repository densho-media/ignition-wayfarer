"""Coupled spacecraft mass closure for the four-burn mission.

Two loops are solved together by fixed-point iteration on the departure mass m0:
  power:      a0 m0 -> thrust -> jet power -> fusion power -> drive hardware + heat -> radiators -> dry mass -> m0
  propellant: ve -> mass ratio -> propellant (by species, with reserve and allowances) -> tank volume -> tank mass -> dry mass -> m0
The drive is sized for the departure acceleration a0 at full mass and then flies at constant thrust (constant power, constant ve),
throttled to hold the 1.5 g ceiling. The iteration reports divergence (the hardware needed to lift the ship outweighs what it lifts)
instead of forcing a number.
"""
import math

from .const import C, G0, DAY, YEAR, AU, EPS_DHE3
from .canon import val
from . import architectures, kinematics, rocket, tanks

SPECIES = tanks.SPECIES


def allowances(sc):
    t = sc['tanks']
    return {'reserve': val(sc['mission']['propellant_reserve']), 'residual': val(t['residual']), 'boiloff': val(t['boiloff_reserve'])}


def close(arch, tier, sc, ref, ve, a0_g, payload_kg, dv=None, burns=4, a_cap_g=None, tol=1e-10, max_iter=200, tank_tier=None, **kw):
    dv = dv or val(sc['mission']['target_speed_c'])*C
    a_cap = (a_cap_g or val(sc['mission']['max_accel_g']))*G0
    a0 = min(a0_g*G0, a_cap)
    R = rocket.mass_ratio(dv, ve); RN = R**burns
    al = allowances(sc); extra = al['reserve']+al['residual']+al['boiloff']
    dens = ref['density_kg_m3']; tank_tier = tank_tier or ('central' if arch == 'CANON' else tier)
    state = {}

    def step(m0):
        """One pass of both loops: m0 -> power -> drive, heat, radiators; m0 -> propellant -> tanks; -> new m0."""
        P_jet = a0*m0*ve/2; eta = state.get('eta', 0.6)
        for _ in range(4):                                   # efficiency depends (weakly) on the power level
            A = architectures.evaluate(arch, sc, tier, P_jet/eta, ve, ref, **kw)
            if not A['feasible'] or abs(A['eta_jet']-eta) < 1e-14:
                break
            eta = A['eta_jet']
        if not A['feasible']:
            return None, A, A['reason']
        eta = A['eta_jet']; P_fus = P_jet/eta
        sp = rocket.split(1.0, ve, eta, A['burn_fraction'], A['recovery'], eps=A['eps'], he3_share=A['he3_share'])
        if sp is None:
            return None, A, 've not reachable'
        share = {'helium_3': sp['helium_3_kg'], 'deuterium': sp['deuterium_kg'], 'hydrogen': sp['hydrogen_kg']}
        m_drive = A['alpha_hw']*P_fus+A['fixed_kg']; m_rad = A['alpha_rad']*P_fus
        D = m0*(1-1/RN)
        loaded = {k: D*(1+extra)*share[k] for k in SPECIES}
        cap = tanks.need(loaded, sc, dens); m_tank = tanks.mass_kg(cap, sc, tank_tier)
        m_dry = payload_kg+m_drive+m_rad+m_tank; m_end = m_dry+extra*D
        state.update(eta=eta, A=A, share=share, m_drive=m_drive, m_rad=m_rad, m_tank=m_tank, m_dry=m_dry, m_end=m_end)
        return m_end*RN, A, ''

    # fixed point m0 = step(m0), solved by secant steps on step(m) - m; the local slope of step() is the loop gain
    hist = []; m_a = payload_kg*RN*1.5; g_a, A, why = step(m_a)
    if g_a is None:
        return {'arch': arch, 'tier': tier, 've': ve, 'a0_g': a0/G0, 'converged': False, 'feasible': False, 'reason': why, 'architecture': A}
    m_b = g_a; it = 0
    for it in range(max_iter):
        g_b, A, why = step(m_b); hist.append(g_b)
        if g_b is None:
            return {'arch': arch, 'tier': tier, 've': ve, 'a0_g': a0/G0, 'converged': False, 'feasible': False, 'reason': why, 'architecture': A}
        if not math.isfinite(g_b) or g_b > 1e13:
            return _diverged(arch, tier, ve, a0, A, hist, 'departure mass exceeds 1e10 t')
        if abs(g_b-m_b) <= tol*g_b:
            break
        gain = (g_b-g_a)/(m_b-m_a) if m_b != m_a else 0.0
        if gain >= 1.0 and g_b > m_b:
            # confirm at twice the mass: still no fixed point above -> divergent closure
            g2, _, _ = step(2*m_b)
            if g2 is None or g2 > 2*m_b:
                return _diverged(arch, tier, ve, a0, A, hist, f'loop gain {gain:.3f} >= 1 (drive, radiators and tanks outweigh what they lift)')
            step(m_b)
        m_new = m_b+(g_b-m_b)/(1-gain) if gain < 0.98 else g_b
        if m_new <= 0:
            m_new = g_b
        m_a, g_a, m_b = m_b, g_b, m_new
    else:
        return _diverged(arch, tier, ve, a0, A, hist, 'no convergence in iteration limit')
    m0 = g_b; step(m0)
    eta = state['eta']; A = state['A']; share = state['share']; m_drive = state['m_drive']; m_rad = state['m_rad']
    m_tank = state['m_tank']; m_dry = state['m_dry']; m_end = state['m_end']; m0 = m_end*RN
    # final consistent state
    P_jet = a0*m0*ve/2; P_fus = P_jet/eta; F = 2*P_jet/ve
    D = m0-m_end
    led = rocket.ledger(m_end, ve, dv, burns)
    tot = rocket.split(D, ve, eta, A['burn_fraction'], A['recovery'], eps=A['eps'], he3_share=A['he3_share'])
    errs = rocket.check_split(tot)
    if abs(led['departure_kg']-m0) > 1e-6*m0 or abs(led['masses_kg'][-1]-m_end) > 1e-6*m_end:
        errs.append('ledger does not end at the end mass')
    if abs(sum(led['burn_propellant_kg'])-D) > 1e-6*D:
        errs.append('burn propellant does not sum to the mission draw')
    if errs:
        raise AssertionError(errs)
    burns_out = []; m = m0; t_total = 0.0
    for i in range(burns):
        b = kinematics.throttled_burn(dv, ve, F, m, a_cap)
        burns_out.append({'start_t': m/1e3, 'propellant_t': (m-b['m_end'])/1e3, 'days': b['t_s']/DAY, 'distance_AU': b['d_m']/AU,
                          'a_start_g': min(F/m, a_cap)/G0, 'a_end_g': b['a_peak']/G0})
        t_total += b['t_s']; m = b['m_end']
    heat = {k: A['heat'][k]*P_fus for k in ('hot', 'warm')}
    th = A['radiators']
    area = {k: heat[k]/th[k]['flux_W_m2'] for k in ('hot', 'warm')}
    loaded = {k: D*(1+al['reserve']+al['residual']+al['boiloff'])*share[k] for k in SPECIES}
    tk = tanks.compare(loaded, sc, dens, tier=tank_tier)
    return {'arch': arch, 'tier': tier, 've_km_s': ve/1e3, 'a0_g': a0/G0, 'converged': True, 'feasible': True, 'iterations': it+1,
            'departure_t': m0/1e3, 'end_t': m_end/1e3, 'dry_t': m_dry/1e3, 'payload_t': payload_kg/1e3, 'drive_t': m_drive/1e3,
            'radiator_t': m_rad/1e3, 'tank_t': m_tank/1e3, 'reserve_t': extra*D/1e3, 'propellant_t': D/1e3,
            'propellant_fraction': D/m0, 'mass_ratio_total': RN, 'burn_propellant_t': [x/1e3 for x in led['burn_propellant_kg']],
            'burn_start_t': [x/1e3 for x in led['masses_kg'][:-1]],
            'species_t': {'helium_3': tot['helium_3_kg']/1e3, 'deuterium': tot['deuterium_kg']/1e3, 'hydrogen': tot['hydrogen_kg']/1e3},
            'fused_t': tot['fused_kg']/1e3, 'lost_unburned_t': tot['lost_unburned_kg']/1e3, 'recovered_t': tot['recovered_kg']/1e3,
            'fusion_energy_J': tot['fusion_energy_J'], 'jet_energy_J': tot['jet_energy_J'],
            'thrust_MN': F/1e6, 'jet_power_TW': P_jet/1e12, 'fusion_power_TW': P_fus/1e12, 'mass_flow_kg_s': F/ve,
            'heat_GW': {k: v/1e9 for k, v in heat.items()}, 'radiator_area_km2': {k: v/1e6 for k, v in area.items()},
            'burns': burns_out, 'burn_time_years': t_total/YEAR, 'const_accel_years': burns*dv/a0/YEAR,
            'a_end_g': burns_out[-1]['a_end_g'], 'tanks': tk, 'architecture': A,
            'alpha_jet_kg_per_W': (A['alpha_hw']+A['alpha_rad'])/eta}


def _diverged(arch, tier, ve, a0, A, hist, why):
    return {'arch': arch, 'tier': tier, 've_km_s': ve/1e3, 'a0_g': a0/G0, 'converged': False, 'feasible': True, 'reason': why,
            'last_departure_t': hist[-1]/1e3 if hist else None, 'architecture': A}


def a0_limit_g(alpha_jet, ve, k_tank, extra, burns=4, dv=0.016*C):
    """Asymptotic departure acceleration as power -> infinity (payload negligible): the denominator of the linear closure,
    1 - RN (alpha a0 ve / 2) - (k (1+extra) + extra)(RN - 1) / ... = 0. k_tank in kg of tank per kg of propellant."""
    RN = math.exp(burns*dv/ve)
    lin = 1-(RN-1)*(k_tank*(1+extra)+extra)/1.0
    # m_end = m_pay + alpha a0 m0 ve/2 + (k(1+extra) + extra) D, D = m0 (1 - 1/RN), m0 = RN m_end
    # => m0 [1 - RN alpha a0 ve/2 - (k(1+extra)+extra)(RN-1)] = RN m_pay
    if lin <= 0:
        return 0.0
    return 2*lin/(RN*alpha_jet*ve)/G0
