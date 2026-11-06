"""Propulsion: the four-burn closure is the authoritative calculation. This module only sets the FDP-1 inputs it does not own (fixed
masses and the hardware solid angle the geometry presents), runs it, and unpacks the per-pulse fusion record from its energy ledger."""
import copy

from .config import v


def close(cfg, fb, sc, ref, payload_kg, fixed_kg, solid_angle, a0_g=None, ve_km_s=None, tier=None):
    """Run the four-burn closure with FDP-1's fixed masses and geometric hardware solid angle fed in."""
    s = copy.deepcopy(sc)
    s['pulsed']['shadow_shield_kg'] = {'value': fixed_kg, 'status': 'FDP-1', 'note': 'shield + FDP-1 structure + idle vessels + low loop'}
    if solid_angle is not None:
        s['pulsed']['hardware_solid_angle'] = solid_angle
    ve = (ve_km_s or v(cfg['mission']['ve_km_s']))*1e3
    a0 = a0_g if a0_g is not None else v(cfg['mission']['a0_g'])
    args = (cfg['base']['architecture'], tier or cfg['base']['tier'], s, ref, ve, a0, payload_kg)
    r = fb['closure'].close(*args)
    if not r.get('converged') and 'iteration limit' in str(r.get('reason', '')):
        # the IFD-PH pulse-rate optimiser (golden section) makes the fixed-point map slightly noisy; 1e-10 can be unreachable
        r = fb['closure'].close(*args, tol=1e-8, max_iter=1000)
    return r, s


def fusion_record(r):
    """Per-pulse and per-second fusion quantities of a converged closure (all from its ledger and pulse geometry)."""
    A = r['architecture']; g = A['geometry']; L = A['ledger']; P = r['fusion_power_TW']*1e12
    G = g['gain']; f = g['rep_Hz']; E = g['yield_J']
    P_drv_e = (L['driver_loss']+1/G)*P                      # driver wall-plug power
    P_beam = P/G                                            # beam power on target
    P_e = P_drv_e+(L['electric_house']+L['cryo_input'])*P  # electric load on the recovery system
    P_ext = P_e+L['recovery_loss']*P                        # power drawn from the expanding plasma by inductive recovery
    mdot = r['mass_flow_kg_s']; sp = r['species_t']; tot = sum(sp.values())
    return {
        'pellet_fuel_mass_g': g['fuel_mass_g'], 'pellet_rate_Hz': f, 'pulse_period_ms': 1e3/f, 'yield_per_pulse_J': E,
        'yield_per_pulse_t_TNT': g['yield_t_TNT'], 'driver_energy_per_pulse_J': E/G, 'target_gain': G, 'burn_fraction': A['burn_fraction'],
        'fuel_rhoR_g_cm2': g['fuel_rhoR_g_cm2'], 'gross_fusion_power_W': P, 'driver_wall_plug_power_W': P_drv_e, 'driver_beam_power_W': P_beam,
        'electric_load_W': P_e, 'recovered_power_W': P_ext, 'recovery_fraction_of_fusion': P_ext/P,
        'directed_exhaust_efficiency': A['eta_jet'], 'jet_power_W': r['jet_power_TW']*1e12, 'mass_flow_kg_s': mdot,
        'species_flow_kg_s': {k: mdot*sp[k]/tot for k in sp}, 'xray_escape_fraction': g['xray_escape'], 'neutron_escape_fraction': g['neutron_escape'],
        'tamper_per_fuel': g.get('tamper_per_fuel', 0.0), 'xray_standoff_m': g['standoff_m'],
        'ledger_per_W_fusion': dict(L), 'ledger_W': {k: x*P for k, x in L.items()},
    }


def pellet(cfg, rec):
    """Target geometry: a frozen D2 shell holding liquid He-3 (He-3 cannot be frozen at practical pressure)."""
    import math
    fu = cfg['fuel']; m = rec['pellet_fuel_mass_g']*1e-3
    sp = rec['species_flow_kg_s']; tot = sp['helium_3']+sp['deuterium']
    m_he = m*sp['helium_3']/tot; m_d = m*sp['deuterium']/tot
    V_he = m_he/v(fu['he3_liquid_density_kg_m3']); V_d = m_d/v(fu['d2_ice_density_kg_m3'])
    r_in = (3*V_he/(4*math.pi))**(1/3); r_out = (3*(V_he+V_d)/(4*math.pi))**(1/3)
    return {'he3_kg': m_he, 'd_kg': m_d, 'core_radius_mm': r_in*1e3, 'outer_radius_mm': r_out*1e3, 'shell_mm': (r_out-r_in)*1e3,
            'diameter_mm': 2*r_out*1e3, 'concept': fu['target_concept']}
