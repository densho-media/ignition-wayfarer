"""Layered shadow shield for the aft point burn.

The burn point sits on the ship axis aft of the shield. Everything that is not edge-on to the burn must lie inside a shadow cone:
  crew cone      habitat rings, refuge and crew trunk (thick LiH core sized by the crew dose budget)
  hardware cone  hull, equipment module, driver galleries, tank farm(s), forward shield and EYE (thinner LiH annulus, placeholder decades)
Radiator planes containing the axis (the existing blades and the FDP-1 wings) are edge-on and exempt; their edge exposure is flagged.
A tungsten face stops the escaping X-rays. Beam ports and the pellet bore are the streaming corridors through the shield.
First-order attenuation only (exponential removal, no build-up, no secondary gammas): a transport calculation must replace it."""
import math

from .config import v

YEAR = 365.25*86400.0
MEV = 1.602176634e-13


def protected(s, mods, lay, proposed_vessels):
    """Envelopes that must be shadowed: (name, kind, radius m, nearest x m). Read from canon geometry and the FDP-1 layout."""
    hr = mods['habitat_ring']; fs = mods['fuel_storage']
    out = []
    xa, xb = hr.centers(s); sw = hr.sweep_half(s)
    out.append(('habitat_rings', 'crew', hr.outer(s), min(xa, xb)-sw))
    out.append(('crew_trunk_and_refuge', 'crew', s['ship']['body_diameter']['value']/2, min(xa, xb)-sw))
    out.append(('hull_and_spine', 'hardware', s['ship']['body_diameter']['value']/2+1.0, lay['x_attach']))
    out.append(('equipment_module', 'hardware', lay['module_radius'], lay['x_shield_fwd']))
    out.append(('driver_galleries', 'hardware', lay['gallery_outer_r'], lay['x_gallery_aft']))
    ts = fs.tanks(s)
    out.append(('existing_tank_farm', 'hardware', max(t['R']+t['a_env'] for t in ts), min(t['x0'] for t in ts)))
    out.append(('forward_shield_and_eye', 'hardware', s['forward_shield']['diameter']['value']/2, lay['x_forward_shield_aft']))
    if proposed_vessels:
        out.append(('proposed_tanks', 'hardware', max(t['R']+t['a_env'] for t in proposed_vessels), min(t['x0'] for t in proposed_vessels)))
    return out


def frustum(R0, R1, t):
    return math.pi*t/3*(R0*R0+R0*R1+R1*R1)


def solve(cfg, s, mods, r, rec, lay, proposed_vessels):
    sh = cfg['shielding']; xB = lay['x_burn']; d_sh = lay['d_shield']
    env = protected(s, mods, lay, proposed_vessels)
    ang = [(n, k, R, x, math.atan2(R, x-xB)) for n, k, R, x in env]
    th_crew = max(a for n, k, R, x, a in ang if k == 'crew'); th_hw = max(a for n, k, R, x, a in ang)
    driving_hw = max(ang, key=lambda e: e[4])[0]
    P = rec['gross_fusion_power_W']
    # crew dose without the shield, at the nearest crew envelope
    x_crew = min(x for n, k, R, x, a in ang if k == 'crew'); d_crew = x_crew-xB
    P_n = rec['neutron_escape_fraction']*P; P_x = rec['xray_escape_fraction']*P
    flux_n = P_n/(v(sh['neutron_energy_MeV'])*MEV)/(4*math.pi*d_crew**2)
    H_n = flux_n*v(sh['fluence_to_dose_Sv_m2'])                                  # Sv/s
    K_x = P_x/(4*math.pi*d_crew**2)*v(sh['tissue_mu_en_m2_kg'])                    # Gy/s (Sv/s for photons)
    allowed = v(cfg['mission']['crew_dose_limit_Sv_per_year'])*v(cfg['mission']['dose_budget_share'])/YEAR
    dec_n = max(0.0, math.log10(H_n/allowed)); dec_x = max(0.0, math.log10(K_x/allowed))
    lam = v(sh['lambda_LiH_m']); t_crew = dec_n*math.log(10)*lam
    dec_hw = v(sh['hardware_decades']); t_hw = dec_hw*math.log(10)*lam
    w = v(sh['w_face_m']); w_need = dec_x*math.log(10)/v(sh['w_mu_per_m'])
    m = v(sh['shadow_margin_m'], 1.0) if 'shadow_margin_m' in sh else v(cfg['layout']['shadow_margin_m'])
    tan_c, tan_h = math.tan(th_crew), math.tan(th_hw)
    # radii at the aft (burn-facing) face and at the forward face of each layer
    Rc0 = d_sh*tan_c+m; Rc1 = (d_sh+w+t_crew)*tan_c+m
    Rh0 = d_sh*tan_h+m; Rh1 = (d_sh+w+t_hw)*tan_h+m
    rho = v(sh['rho_LiH_kg_m3'])
    V_core = frustum(Rc0, Rc1, t_crew)
    V_ann = max(0.0, frustum(Rh0, Rh1, t_hw)-frustum(Rc0, min(Rc1, Rc0+(Rc1-Rc0)*t_hw/max(t_crew, 1e-9)), min(t_hw, t_crew)))
    m_core = rho*V_core; m_ann = rho*V_ann; m_w = v(sh['rho_W_kg_m3'])*math.pi*Rh0**2*w
    fu = cfg['fuel']
    plug_len = t_crew+v(fu['plug_margin_m'])                                           # the on-axis plug is as thick as the crew core + margin
    m_plug = rho*math.pi*v(fu['plug_radius_m'])**2*plug_len
    m_frame = v(sh['frame_fraction'])*(m_core+m_ann+m_w+m_plug)
    total = m_core+m_ann+m_w+m_plug+m_frame
    share = (1-math.cos(math.atan2(Rh0, d_sh)))/2
    # streaming corridors: beam ports (dog-legged to dumps) and the on-axis pellet bore (plugged)
    dr = cfg['drivers']
    port_share = dr['beams']['value']*(math.pi*(v(dr['port_diameter_m'])/2)**2)/(4*math.pi*d_sh**2)
    bore_share = (math.pi*(v(fu['bore_diameter_m'])/2)**2)/(4*math.pi*d_sh**2)
    plug_dec = plug_len/(lam*math.log(10))
    H_axis = H_n*10**(-plug_dec)                                                       # on-axis dose rate behind the plug at the crew plane
    return {
        'envelopes': [{'name': n, 'kind': k, 'radius_m': R, 'nearest_x_m': x, 'half_angle_deg': math.degrees(a)} for n, k, R, x, a in ang],
        'crew_half_angle_deg': math.degrees(th_crew), 'hardware_half_angle_deg': math.degrees(th_hw), 'hardware_cone_set_by': driving_hw,
        'distance_from_burn_m': d_sh, 'crew_distance_m': d_crew,
        'neutron_escape_W': P_n, 'xray_escape_W': P_x,
        'unshielded_crew_dose_Sv_h': {'neutron': H_n*3600, 'xray': K_x*3600},
        'allowed_dose_rate_Sv_h': allowed*3600, 'neutron_decades': dec_n, 'xray_decades': dec_x, 'hardware_decades': dec_hw,
        'lih_core_m': t_crew, 'lih_annulus_m': t_hw, 'w_face_m': w, 'w_needed_m': w_need,
        'radius_crew_aft_m': Rc0, 'radius_crew_fwd_m': Rc1, 'radius_hw_aft_m': Rh0, 'radius_hw_fwd_m': Rh1,
        'thickness_m': w+max(t_crew, t_hw),
        'mass_kg': {'lih_core': m_core, 'lih_annulus': m_ann, 'w_face': m_w, 'axial_plug': m_plug, 'frame': m_frame, 'total': total},
        'placeholder_kg': 100000.0, 'solid_angle_share': share,
        'streaming': {'beam_ports': {'count': dr['beams']['value'], 'share': port_share, 'power_W': port_share*P_n,
                                     'mitigation': 'final-focus dog-leg: the line of sight ends in a LiH beam dump as thick as the crew core'},
                      'pellet_bore': {'share': bore_share, 'plug_length_m': plug_len, 'plug_radius_m': v(fu['plug_radius_m']), 'power_W': bore_share*P_n, 'plug_decades': plug_dec, 'axis_dose_Sv_h': H_axis*3600,
                                      'ok': H_axis <= allowed,
                                      'mitigation': 'on-axis LiH plug behind the injector breech; the crew trunk lies on this axis'}},
        'limits': ['first-order exponential removal; no build-up factor, no secondary (n,gamma) photons, no scatter around the rim',
                   'neutron spectrum taken as D-D 2.45 MeV; the 14.1 MeV D-T share needs a longer relaxation length',
                   'hardware decades are a placeholder (cryogenic heating, activation, electronics) until a transport calculation',
                   'edge-on radiator planes are exempt from the shadow; their edge and rim-scatter exposure is not computed'],
    }
