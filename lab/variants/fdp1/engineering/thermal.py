"""Heat by loop and radiator sizing. Every watt comes from the four-burn ledger; this module only splits it by circuit and lays the
resulting area out. Radiator areas are the closure's (planform, two-sided, q = 2 eps sigma T^4); the layouts never shrink them."""
import math

from .config import v


def circuits(r, rec, shares):
    """Heat per circuit (W) and the radiation budget. shares: solid-angle shares of loops, struts and shield (sum = hardware share)."""
    L = rec['ledger_W']; tot = sum(shares.values()) or 1.0
    rad_hw = L['radiation_on_hardware']
    hot = {'plume_on_hardware': L['plume_to_hardware'], 'recovery_conversion_loss': L['recovery_loss']}
    for k, x in shares.items():
        hot[f'radiation_on_{k}'] = rad_hw*x/tot
    warm = {'driver_waste': L['driver_loss'], 'power_and_target_systems': L['electric_house'],
            'cryoplant_input': L['cryo_input'], 'coil_conductor_heating': L['radiation_on_conductor']}
    out = {'hot_W': hot, 'warm_W': warm, 'hot_total_W': sum(hot.values()), 'warm_total_W': sum(warm.values()),
           'to_space_W': {'jet': L['jet'], 'plume_to_space': L['plume_to_space'], 'radiation_to_space': L['radiation_to_space']},
           'closure_hot_W': r['heat_GW']['hot']*1e9, 'closure_warm_W': r['heat_GW']['warm']*1e9}
    out['unaccounted_W'] = rec['gross_fusion_power_W']-sum(L.values())
    return out


def radiators(cfg, s, r, circ):
    A = r['architecture']; th = A['radiators']; P = r['fusion_power_TW']*1e12
    hot_c, warm_c = th['hot'], th['warm']
    area_hot = circ['hot_total_W']/hot_c['flux_W_m2']; area_warm = circ['warm_total_W']/warm_c['flux_W_m2']
    m_hot = circ['hot_total_W']*hot_c['kg_per_W']; m_warm = circ['warm_total_W']*warm_c['kg_per_W']
    # the existing three 1800 K blades (canon effective area = one-face planform x 2 faces x view factor)
    rd = s['radiators']; blades_planform = rd['effective_area']['value']/(rd['emitting_faces']*rd['view_factor']['value'])
    reuse = v(cfg['radiators']['reuse_existing_hot_blades']) and hot_c['kind'] == 'hot'
    reused = min(area_hot, blades_planform) if reuse else 0.0
    return {'hot': {'kind': hot_c['kind'], 'T_K': hot_c['T_K'], 'flux_W_m2': hot_c['flux_W_m2'], 'areal_kg_m2': hot_c['areal_kg_m2'],
                    'planform_m2': area_hot, 'mass_kg': m_hot, 'existing_blades_planform_m2': blades_planform, 'reused_m2': reused,
                    'extension_m2': area_hot-reused},
            'warm': {'kind': 'warm', 'T_K': warm_c['T_K'], 'flux_W_m2': warm_c['flux_W_m2'], 'areal_kg_m2': warm_c['areal_kg_m2'],
                     'planform_m2': area_warm, 'mass_kg': m_warm},
            'closure_radiator_kg': r['radiator_t']*1e3, 'check_kg': m_hot+m_warm,
            'cryo_W_per_W': th['cryo_W_per_W']}


def layouts(cfg, rad, lay, ring_radius, spar_kg_per_m=0.0):
    hot_ext = rad['hot']['extension_m2']
    """Warm-wing packaging candidates. Half-planes through the axis are edge-on to the burn. n wings at equal spacing alpha see each
    other with F = 1 - sin(alpha/2) (infinite plates sharing an edge); at equal temperature that exchange is lost, so each wing must be
    larger by 1/sin(alpha/2). ENVELOPE keeps the span inside today's ship envelope (the ring radius)."""
    A = rad['warm']['planform_m2']; L = lay['wing_length']; root = v(cfg['radiators']['root_radius_m'])
    out = {}
    for name, n, az, note in (('W2', 2, [0.0, 180.0], 'one plane (port/starboard); no mutual view'),
                              ('W3', 3, [90.0, 210.0, 330.0], 'three wings between the existing blades (30/150/270 deg)'),
                              ('W6', 6, [0.0, 60.0, 120.0, 180.0, 240.0, 300.0], 'six wings; 30 deg from the blades'),
                              ('ENVELOPE', 3, [90.0, 210.0, 330.0], 'W3 limited to the habitat-ring radius')):
        alpha = 2*math.pi/n if n > 2 else math.pi
        factor = math.sin(alpha/2) if n > 2 else 1.0
        need_each = A/(n*factor)
        span = need_each/L
        band = hot_ext/(n*L)                                       # 1800 K root band of each wing
        root_w = root+band
        if name == 'ENVELOPE':
            span_max = max(0.0, ring_radius-root_w)
            fit = n*factor*L*span_max
            out[name] = {'wings': n, 'azimuths_deg': az, 'view_factor_loss': 1-factor, 'span_m': span_max, 'hot_band_m': band, 'tip_radius_m': ring_radius,
                         'planform_each_m2': L*span_max, 'rejects_share': fit/A, 'shortfall_m2': A-fit, 'note': note+f': rejects {100*fit/A:.1f} % of the warm heat'}
            continue
        pen = (1/factor-1)*A*rad['warm']['areal_kg_m2']; spars = spar_kg_per_m*(span+band)*n*2
        out[name] = {'wings': n, 'azimuths_deg': az, 'view_factor_loss': 1-factor, 'span_m': span, 'hot_band_m': band, 'warm_root_radius_m': root_w, 'tip_radius_m': root_w+span,
                     'planform_each_m2': need_each, 'total_planform_m2': need_each*n, 'area_penalty': 1/factor, 'note': note,
                     'view_factor_mass_kg': pen, 'spar_mass_kg': spars, 'extra_mass_kg': pen+spars}
    return out


def pick(cfg, wl):
    choice = cfg['radiators']['layout']['value']
    if choice == 'auto':
        return min((k for k in wl if k != 'ENVELOPE'), key=lambda k: wl[k]['extra_mass_kg'])
    return choice
