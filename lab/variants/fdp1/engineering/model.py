"""The integrated FDP-1 solve. One record holds everything the reports print and Blender draws.

Loop (until the departure mass reproduces itself):
  four-burn closure (fixed masses, hardware solid angle)  ->  pulse record (stand-off R_s, power, rates)
  -> layout (module, shield, burn point, loops, galleries, wings)  ->  shield (cones, dose, thickness, mass)
  -> nozzle and strut solid angles  ->  structure, thermal, tanks  ->  new fixed mass and solid angle  -> closure ...
The four-burn engine stays the only place where thrust, power, propellant, radiator and drive masses are computed."""
import math

from . import config, propulsion, shielding, structure, thermal, tanks, mission
from .config import v

G0 = 9.80665


def payload(cfg, s, mods):
    """Non-propulsion dry mass and its parts (mass_model), excluding the items FDP-1 sizes itself."""
    mm = mods['mass_model']; parts = mm.dry_parts(s)
    sup = tuple(cfg['mission']['superseded_items'])
    keep = [p for p in parts if not p['name'].startswith(sup)]
    dropped = [p for p in parts if p['name'].startswith(sup)]
    src = cfg['mission']['payload'].get('source', 'mass_model')
    m = sum(p['m'] for p in keep) if src == 'mass_model' else cfg['mission']['payload']['reference_t']*1e3
    return m, keep, dropped


def nozzle(cfg, R_s, x_B, M_struct, M_armour):
    n = cfg['nozzle']; N = int(v(n['coil_count'])); p0 = math.radians(v(n['phi_min_deg'])); p1 = math.radians(v(n['phi_max_deg']))
    f = R_s*(1+math.cos(p0))/2                                  # paraboloid focal length: the forward loop sits at R_s
    loops = []
    for i in range(N):
        ph = p0+(p1-p0)*i/max(N-1, 1); d = 2*f/(1+math.cos(ph))
        loops.append({'name': f'Loop_{i+1}', 'phi_deg': math.degrees(ph), 'd': d, 'x': x_B+d*math.cos(ph), 'r': d*math.sin(ph)})
    lam = M_struct/(2*math.pi*sum(L['r'] for L in loops)); a = math.sqrt(lam/(math.pi*v(n['conductor_density_kg_m3'])))
    a_env = a*v(n['envelope_factor'])
    share = 0.0
    for L in loops:
        L['minor_radius_m'] = a; L['envelope_radius_m'] = a_env; L['mass_kg'] = lam*2*math.pi*L['r']
        L['armour_kg'] = M_armour*L['r']/sum(q['r'] for q in loops)
        L['solid_angle_share'] = math.sin(math.radians(L['phi_deg']))*a_env/L['d']
        share += L['solid_angle_share']
    vertex = {'x': x_B+f, 'opening_radius_m': 0.0}
    return {'focal_length_m': f, 'loops': loops, 'linear_density_kg_m': lam, 'solid_angle_share': share, 'vertex': vertex,
            'trim_sectors': int(v(n['trim_sectors'])), 'plume_half_angle_deg': v(n['plume_half_angle_deg'])}


def strut_share(cfg, struts, x_B, samples=24):
    """Share of the burn's sky covered by the strut columns (lattice solidity applied)."""
    sol = v(cfg['nozzle'].get('strut_solidity', {'value': 1.0})); tot = 0.0
    for st in struts:
        (x0, r0), (x1, r1) = st['a'], st['b']
        ux, ur = (x1-x0), (r1-r0); un = math.hypot(ux, ur)
        for k in range(samples):
            t = (k+.5)/samples; x = x0+ux*t; rr = r0+ur*t
            d = math.hypot(x-x_B, rr); ds = un/samples; lx, lr = (x-x_B)/d, rr/d
            sin_a = abs(ux/un*lr-ur/un*lx)
            tot += st['count']*sol*2*st['radius_m']*ds*sin_a/(4*math.pi*d*d)
    return tot


def gallery_azimuths(n, planes, min_sep=15.0):
    """n gallery azimuths in the widest gaps between the radiator planes (greedy, 1 deg grid)."""
    taken = list(planes); out = []
    for _ in range(n):
        best = max(range(360), key=lambda a: min(abs(((a-b)+180) % 360-180) for b in taken))
        out.append(float(best)); taken.append(best)
    return sorted(out)


def drivers(cfg, rec, M_driver, x_attach):
    dr = cfg['drivers']; T = v(dr['ion_energy_GeV']); q = v(dr['charge_state']); Gm = v(dr['gradient_MV_m'])
    L_lin = T*1e3/(q*Gm)                                         # m (GeV -> MV / (q MV/m))
    folds = int(v(dr['folds'])); L_pass = L_lin/folds
    mc2 = v(dr['ion_mass_u'])*0.93149410242; pc = math.sqrt(T*T+2*T*mc2)
    Brho = pc*3.33564/q; r_arc = Brho/v(dr['bend_field_T'])
    E_e = rec['driver_wall_plug_power_W']/rec['pellet_rate_Hz']
    m_store = v(dr['storage_pulses'])*E_e/(v(dr['storage_kJ_per_kg'])*1e3)
    m_cores = M_driver-m_store
    beams = int(v(dr['beams']))
    area = max(m_cores, 0.0)/(v(dr['core_density_kg_m3'])*beams*L_lin)
    ions = rec['driver_energy_per_pulse_J']/(T*1e9*1.602176634e-19)
    return {'type': dr['type'], 'beams': beams, 'galleries': int(v(dr['galleries'])), 'azimuths_deg': [],
            'radius_m': v(dr['gallery_radius_m']), 'linac_length_m': L_lin, 'folds': folds, 'pass_length_m': L_pass,
            'magnetic_rigidity_Tm': Brho, 'arc_radius_m': r_arc, 'beam_energy_per_pulse_J': rec['driver_energy_per_pulse_J'],
            'electric_energy_per_pulse_J': E_e, 'ions_per_pulse': ions, 'mass_kg': M_driver, 'storage_mass_kg': m_store,
            'core_mass_kg': m_cores, 'core_cross_section_m2': area, 'core_radius_m': math.sqrt(area/math.pi) if area > 0 else 0.0,
            'storage_exceeds_budget': m_store > M_driver, 'x_aft': x_attach, 'x_fwd': x_attach+L_pass+r_arc}


def layout(cfg, s, mods, rec, t_shield, tank_opt, bays_aft_len):
    lay_mod = mods['layout']; L = cfg['layout']
    x_attach = lay_mod.x(s, L['hull_attach']['datum'], L['hull_attach']['offset_m'])
    R_s = rec['xray_standoff_m']; d_sh = R_s*v(L['shield_standoff_factor'])
    x_mod_fwd = x_attach-bays_aft_len
    x_sf = x_mod_fwd-v(L['module_length_m']); x_sa = x_sf-t_shield; x_B = x_sa-d_sh
    dr = cfg['drivers']
    fwd_shield_aft = 138.2
    if tank_opt == 'T-B':
        pass
    return {'x_attach': x_attach, 'x_module_fwd': x_mod_fwd, 'x_shield_fwd': x_sf, 'x_shield_aft': x_sa, 'x_burn': x_B, 'd_shield': d_sh,
            'R_s': R_s, 'module_length': v(L['module_length_m']), 'module_radius': v(L['module_radius_m']), 'added_bay_length': bays_aft_len,
            'gallery_outer_r': v(dr['gallery_radius_m'])+2.0, 'x_gallery_aft': x_attach, 'x_forward_shield_aft': fwd_shield_aft,
            'wing_aft_x': x_sf+2.0, 'wing_forward_x': v(cfg['radiators']['wing_forward_x'])}


def solve(cfg, verbose=False):
    fb = config.fourburn(cfg); sc = config.scenario(cfg, fb); ref = fb['canon'].reference(); s = config.spec(); mods = config.wayfarer_modules()
    pay_kg, pay_parts, dropped = payload(cfg, s, mods)
    integ = cfg['integration']; feedback = integ.get('feedback', True)
    fixed = fb['canon'].val(sc['pulsed']['shadow_shield_kg']); Om = None
    sel = v(cfg['tanks']['selected'])
    t_shield = 4.0; hist = []
    rec = None
    for it in range(int(integ['max_iterations'])):
        r, sc_used = propulsion.close(cfg, fb, sc, ref, pay_kg, fixed, Om)
        if not r.get('converged'):
            return deficit_record(cfg, fb, sc, ref, pay_kg, fixed, Om, r, hist)
        rec = propulsion.fusion_record(r)
        A = r['architecture']; P = rec['gross_fusion_power_W']; ap = A['alpha_parts']
        M_noz = ap['nozzle_structure']*P; M_arm = ap['loop_armour']*P; M_drv = ap['driver']*P; M_other = ap['other']*P
        for _ in range(6):                                  # shield thickness <-> burn position
            bays_aft = 0.0
            lay = layout(cfg, s, mods, rec, t_shield, sel, bays_aft)
            topt = tanks.options(cfg, s, mods, r, lay)
            if sel == 'T-A':
                bays_aft = topt['options']['T-A']['added_length_m']; lay = layout(cfg, s, mods, rec, t_shield, sel, bays_aft)
                topt = tanks.options(cfg, s, mods, r, lay)
            prop_v = topt['options'][sel]['vessels']
            if sel == 'T-B':
                lay['x_forward_shield_aft'] += topt['options']['T-B']['added_length_m']
            sh = shielding.solve(cfg, s, mods, r, rec, lay, prop_v)
            if abs(sh['thickness_m']-t_shield) < 1e-6:
                break
            t_shield = sh['thickness_m']
        noz = nozzle(cfg, rec['xray_standoff_m'], lay['x_burn'], M_noz, M_arm)
        drv = drivers(cfg, rec, M_drv, lay['x_attach'])
        lay['wing_length'] = lay['wing_forward_x']-lay['wing_aft_x']
        circ0 = thermal.circuits(r, rec, {'loops': 1.0})
        rad = thermal.radiators(cfg, s, r, circ0)
        spar = v(cfg['structure']['wing_spar_kg_per_m'])
        wl = thermal.layouts(cfg, rad, lay, mods['habitat_ring'].outer(s), spar); wkey = thermal.pick(cfg, wl); wsel = wl[wkey]
        drv['azimuths_deg'] = gallery_azimuths(drv['galleries'], [30.0, 150.0, 270.0]+wsel['azimuths_deg'])
        st = structure.solve(cfg, r, rec, lay, noz, sh, {'span_m': wsel['span_m']+wsel['hot_band_m'], 'count': wsel['wings']},
                             {'length_m': drv['pass_length_m']+drv['arc_radius_m'], 'count': drv['galleries']})
        s_struts = strut_share(cfg, st['struts'], lay['x_burn'])
        shares = {'nozzle_loops': noz['solid_angle_share'], 'nozzle_struts': s_struts, 'shadow_shield': sh['solid_angle_share']}
        Om_geo = sum(shares.values())
        circ = thermal.circuits(r, rec, shares)
        rad = thermal.radiators(cfg, s, r, circ)
        wl = thermal.layouts(cfg, rad, lay, mods['habitat_ring'].outer(s), spar); wkey = thermal.pick(cfg, wl); wsel = wl[wkey]
        # masses FDP-1 adds on top of the closure's drive/radiator/tank terms
        idle_m3 = sum(t['liquid_m3'] for t in topt['existing'] if t['key'] == 'hydrogen')
        k_tank = fb['canon'].val(sc['tanks']['mass_per_m3'], cfg['base']['tier'])
        idle_kg = idle_m3*k_tank if v(integ['keep_idle_hydrogen_vessels']) else 0.0
        cool_added = max(0.0, r['tanks']['cooling_W']-sc['tanks']['cooling_W_per_m3']['value']*(topt['existing_capacity_m3']['helium_3']+topt['existing_capacity_m3']['deuterium']))
        low_area = cool_added/(2*0.9*5.670374419e-8*300.0**4); low_kg = low_area*v(integ['low_loop_radiator_kg_m2'])
        vf_kg = (wsel.get('area_penalty', 1.0)-1.0)*rad['warm']['planform_m2']*rad['warm']['areal_kg_m2']
        added = {'shadow_shield': sh['mass_kg']['total'], 'fdp1_structure': st['mass_kg']['total'], 'idle_hydrogen_vessels': idle_kg,
                 'low_loop_radiator': low_kg, 'wing_view_factor_area': vf_kg}
        fixed_new = sum(added.values())
        hist.append({'iteration': it+1, 'departure_t': r['departure_t'], 'fixed_t': fixed/1e3, 'solid_angle': Om if Om is not None else fb['canon'].val(sc['pulsed']['hardware_solid_angle'], cfg['base']['tier'])})
        if verbose:
            print(hist[-1], Om_geo, fixed_new/1e3)
        if not feedback:
            break
        done = abs(fixed_new-fixed) <= integ['tolerance']*max(fixed, 1.0) and Om is not None and abs(Om_geo-Om) <= integ['tolerance']*Om_geo
        fixed, Om = fixed_new, Om_geo
        if done:
            break
    else:
        raise RuntimeError('FDP-1 integration did not converge')
    mis = mission.solve(cfg, r, cfg['mission']['destination_distances_AU'])
    added = {k: x*fixed/sum(added.values()) for k, x in added.items()} if feedback else added
    mass = mass_breakdown(r, rec, A, added, pay_kg, M_noz, M_arm, M_drv, M_other, rad, st, sh)
    com = centre_of_mass(cfg, s, mods, pay_parts, r, lay, noz, drv, sh, topt, sel, rad, mass)
    rec_out = {
        'version': cfg['version'], 'variant': cfg['variant'], 'architecture': cfg['base']['architecture'], 'tier': cfg['base']['tier'],
        'converged': True, 'iterations': hist, 'payload_kg': pay_kg, 'payload_reference_kg': cfg['mission']['payload']['reference_t']*1e3,
        'payload_dropped': [{'id': p['name'], 'kg': p['m']} for p in dropped],
        'closure': strip(r), 'fusion': rec, 'pellet': propulsion.pellet(cfg, rec), 'layout': lay, 'nozzle': noz, 'drivers': drv,
        'shield': sh, 'structure': st, 'solid_angle': {'shares': shares, 'total': Om_geo, 'used_in_closure': Om,
                                                       'scenario_value': fb['canon'].val(fb['canon'].scenario(cfg['base']['scenario'])['pulsed']['hardware_solid_angle'], cfg['base']['tier'])},
        'thermal': {'circuits': circ, 'radiators': rad, 'layouts': wl, 'selected_layout': wkey,
                    'low_loop': {'added_cooling_W': cool_added, 'area_m2': low_area, 'mass_kg': low_kg}},
        'tanks': {'summary': tanks.summary(cfg, r, topt, s), 'options': {k: {kk: vv for kk, vv in o.items()} for k, o in topt['options'].items()},
                  'existing': topt['existing'], 'selected': sel, 'idle_hydrogen_kg': idle_kg, 'bay_length_m': topt['bay_length_m']},
        'added_fixed_kg': added, 'mass': mass, 'mission': mis, 'com': com,
    }
    rec_out['injection'] = injection(cfg, rec, lay, r)
    rec_out['checks'] = checks(cfg, rec_out)
    rec_out['clearances'] = clearances(cfg, s, mods, rec_out)
    return rec_out


def strip(r):
    out = {k: x for k, x in r.items() if k != 'architecture'}
    A = r['architecture']
    out['architecture'] = {k: A[k] for k in ('arch', 'tier', 'eta_jet', 'burn_fraction', 'alpha_hw', 'alpha_parts', 'alpha_rad', 'fixed_kg', 'geometry', 'heat', 'ledger', 'radiators', 'feasible', 'reason')}
    return out


def mass_breakdown(r, rec, A, added, pay, M_noz, M_arm, M_drv, M_other, rad, st, sh):
    P = rec['gross_fusion_power_W']
    m = {'payload (non-propulsion ship)': pay,
         'drivers (heavy-ion linacs, storage)': M_drv, 'nozzle loops (virial structure)': M_noz, 'loop armour': M_arm,
         'target factory, injectors, cryo-targets, misc': M_other,
         'shadow shield': added['shadow_shield'], 'FDP-1 structure': added['fdp1_structure'],
         'hot radiators': rad['hot']['mass_kg'], 'warm radiators': rad['warm']['mass_kg'],
         'warm-wing view-factor area': added['wing_view_factor_area'], 'low loop radiator': added['low_loop_radiator'],
         'tankage (required volume)': r['tank_t']*1e3, 'idle hydrogen vessels': added['idle_hydrogen_vessels'],
         'propellant reserve and allowances': r['reserve_t']*1e3}
    dry = sum(m.values())
    m['propellant (four burns)'] = r['propellant_t']*1e3
    prop_sys = M_drv+M_noz+M_arm+M_other+added['shadow_shield']+added['fdp1_structure']+rad['hot']['mass_kg']+rad['warm']['mass_kg']+added['wing_view_factor_area']+added['low_loop_radiator']
    return {'items_kg': m, 'end_mass_kg': r['end_t']*1e3, 'dry_kg_check': dry, 'departure_kg': r['departure_t']*1e3,
            'propulsion_system_kg': prop_sys, 'closure_drive_kg': r['drive_t']*1e3, 'closure_radiator_kg': r['radiator_t']*1e3,
            'closure_tank_kg': r['tank_t']*1e3, 'balance_error_kg': (r['end_t']*1e3)-dry}


def centre_of_mass(cfg, s, mods, pay_parts, r, lay, noz, drv, sh, topt, sel, rad, mass):
    """Axial centre of mass, baseline ship (dry, canon) versus FDP-1 (end mass and departure)."""
    mm = mods['mass_model']; base = mm.totals(mm.dry_parts(s))
    pts = [(p['m'], p['c'][0]) for p in pay_parts]
    it = mass['items_kg']
    x_mod = (lay['x_shield_fwd']+lay['x_module_fwd'])/2
    pts += [(it['drivers (heavy-ion linacs, storage)'], (drv['x_aft']+drv['x_fwd'])/2),
            (it['nozzle loops (virial structure)']+it['loop armour'], sum(L['x'] for L in noz['loops'])/len(noz['loops'])),
            (it['target factory, injectors, cryo-targets, misc'], x_mod), (it['shadow shield'], lay['x_shield_aft']+sh['thickness_m']/2),
            (it['FDP-1 structure'], x_mod), (it['hot radiators'], -42.0), (it['warm radiators']+it['warm-wing view-factor area'], (lay['wing_aft_x']+lay['wing_forward_x'])/2),
            (it['low loop radiator'], x_mod)]
    ex = topt['existing']; pv = topt['options'][sel]['vessels']
    vessels = [t for t in ex]+pv; vol = sum(t['liquid_m3'] for t in vessels if t['key'] != 'hydrogen')
    x_tank = sum(t['liquid_m3']*(t['x0']+t['x1'])/2 for t in vessels if t['key'] != 'hydrogen')/vol
    x_h2 = sum(t['liquid_m3']*(t['x0']+t['x1'])/2 for t in ex if t['key'] == 'hydrogen')/max(1e-9, sum(t['liquid_m3'] for t in ex if t['key'] == 'hydrogen'))
    pts += [(it['tankage (required volume)'], x_tank), (it['idle hydrogen vessels'], x_h2), (it['propellant reserve and allowances'], x_tank)]
    M_end = sum(m for m, x in pts); x_end = sum(m*x for m, x in pts)/M_end
    P = r['propellant_t']*1e3-r['reserve_t']*1e3
    x_dep = (M_end*x_end+P*x_tank)/(M_end+P)
    return {'baseline_dry_x_m': base['cg_m'][0], 'baseline_dry_kg': base['mass_kg'], 'fdp1_end_x_m': x_end, 'fdp1_end_kg': M_end,
            'fdp1_departure_x_m': x_dep, 'propellant_centroid_x_m': x_tank, 'shift_end_vs_baseline_m': x_end-base['cg_m'][0]}


def injection(cfg, rec, lay, r):
    fu = cfg['fuel']; vi = v(fu['injection_speed_m_s']); dist = lay['x_shield_fwd']-lay['x_burn']
    t = dist/vi; a = max(b['a_end_g'] for b in r['burns'])*G0
    return {'speed_m_s': vi, 'path_m': dist, 'flight_time_s': t, 'pellets_in_flight': t*rec['pellet_rate_Hz'],
            'drift_under_peak_accel_m': 0.5*a*t*t, 'drift_note': 'the ship accelerates away from a pellet in free flight; tracking and beam steering absorb it',
            'injectors': int(v(fu['injectors'])), 'magazine_pulses': int(v(fu['magazine_pulses'])),
            'magazine_seconds': v(fu['magazine_pulses'])/rec['pellet_rate_Hz'], 'pellets_per_day': rec['pellet_rate_Hz']*86400}


def checks(cfg, R):
    """Physical consistency checks (also asserted by tests/test_fdp1.py). Each: (name, ok, detail)."""
    c = R['closure']; f = R['fusion']; out = []
    L = f['ledger_per_W_fusion']
    out.append(('energy ledger closes', abs(sum(L.values())-1) < 1e-9, f'sum {sum(L.values()):.12f} of gross fusion'))
    th = R['thermal']['circuits']
    out.append(('no unaccounted waste heat', abs(th['hot_total_W']-th['closure_hot_W']) < 1e-6*th['closure_hot_W'] and abs(th['warm_total_W']-th['closure_warm_W']) < 1e-6*th['closure_warm_W'],
                f"hot {th['hot_total_W']/1e9:.3f} GW, warm {th['warm_total_W']/1e9:.3f} GW match the closure"))
    rad = R['thermal']['radiators']
    out.append(('radiator sizing consistent', abs(rad['check_kg']-rad['closure_radiator_kg']) < 1e-6*rad['closure_radiator_kg'], f"{rad['check_kg']/1e3:.1f} t"))
    sb = R['shield']['streaming']['pellet_bore']
    out.append(('crew dose on the pellet-bore axis within budget', sb['ok'], f"{sb['axis_dose_Sv_h']:.3g} Sv/h behind a {sb['plug_length_m']:.2f} m plug, budget {R['shield']['allowed_dose_rate_Sv_h']:.3g}"))
    ms = R['mass']
    out.append(('mass balance (end mass = sum of dry items + reserve)', abs(ms['balance_error_kg']) < 1e-3*ms['end_mass_kg'], f"error {ms['balance_error_kg']:.3f} kg"))
    burns = R['mission']['burns']
    out.append(('four burns, each 0.016 c (rocket equation)', len(burns) == 4 and all(abs(b['delta_v_error']) < 1e-6 for b in burns),
                ', '.join(f"{b['delta_v_km_s']:.1f}" for b in burns)+' km/s'))
    out.append(('propellant drawn = sum of burns', abs(sum(b['propellant_t'] for b in burns)-c['propellant_t']) < 1e-6*c['propellant_t'], f"{c['propellant_t']:.1f} t"))
    out.append(('acceleration <= 1.5 g', max(b['accel_end_g'] for b in burns) <= 1.5+1e-9, f"peak {max(b['accel_end_g'] for b in burns):.4f} g"))
    out.append(('nonnegative propellant', all(x >= 0 for x in c['species_t'].values()), str({k: round(x, 3) for k, x in c['species_t'].items()})))
    fused = c['fused_t']; lost = c['lost_unburned_t']; feed = c['species_t']['helium_3']+c['species_t']['deuterium']
    out.append(('fused + unburned = fusion fuel fed', abs(fused+lost-feed) < 1e-6*feed, f'{fused:.1f} + {lost:.1f} = {feed:.1f} t'))
    out.append(('momentum: thrust = mass flow x ve', abs(c['thrust_MN']*1e6-c['mass_flow_kg_s']*c['ve_km_s']*1e3) < 1e-6*c['thrust_MN']*1e6, f"{c['thrust_MN']:.4f} MN"))
    out.append(('jet power = thrust x ve / 2', abs(c['jet_power_TW']-c['thrust_MN']*c['ve_km_s']/2*1e-3) < 1e-9*c['jet_power_TW'], f"{c['jet_power_TW']:.3f} TW"))
    tk = R['tanks']['summary']
    out.append(('tank capacity compared', all(k in tk['existing_m3'] for k in ('helium_3', 'deuterium', 'hydrogen')), tk['outcome']))
    sel = R['tanks']['options'][R['tanks']['selected']]
    out.append(('proposed tanks cover the deficit', all(sel['added_m3'][k] >= R['tanks']['summary']['deficit_m3'][k]-1e-6 for k in ('helium_3', 'deuterium')),
                str({k: round(x) for k, x in sel['added_m3'].items()})))
    sa = R['solid_angle']
    out.append(('geometric hardware solid angle fed back to the closure', sa['used_in_closure'] is not None and abs(sa['total']-sa['used_in_closure']) <= 1e-5*sa['total'], f"geometry {sa['total']:.5f}, closure {sa['used_in_closure']}"))
    out.append(('FDP-1 fixed masses fed back to the closure', abs(R['closure']['architecture']['fixed_kg']-sum(R['added_fixed_kg'].values())) <= 1e-5*sum(R['added_fixed_kg'].values()), f"{R['closure']['architecture']['fixed_kg']/1e3:.1f} t"))
    return [{'check': n, 'ok': bool(ok), 'detail': d} for n, ok, d in out]


def clearances(cfg, s, mods, R):
    lay = R['layout']; hr = mods['habitat_ring']; xa, xb = hr.centers(s); sw = hr.sweep_half(s)
    w = R['thermal']['layouts'][R['thermal']['selected_layout']]
    out = []
    out.append(('radiator wings vs habitat ring A sweep', (xa-sw)-lay['wing_forward_x'], 'm axial gap', 5.0))
    out.append(('radiator wings vs docking corridor (Dock_Primary X 99.40 m, 3 m radius)', (99.40-3.0)-lay['wing_forward_x'], 'm axial gap', 2.0))
    az_blades = [30.0, 150.0, 270.0]
    sep = min(abs(((a-b)+180) % 360-180) for a in w['azimuths_deg'] for b in az_blades)
    out.append(('wing planes vs existing hot blades', sep, 'deg angular separation', 15.0))
    gaz = R['drivers']['azimuths_deg']
    sepg = min(abs(((a-b)+180) % 360-180) for a in gaz for b in w['azimuths_deg']+az_blades)
    out.append(('driver galleries vs radiator planes', sepg, 'deg angular separation', 15.0))
    out.append(('forward nozzle loop vs X-ray stand-off', R['nozzle']['loops'][0]['d']-lay['R_s'], 'm (>= 0)', 0.0))
    out.append(('shield aft face vs X-ray stand-off', lay['d_shield']-lay['R_s'], 'm (>= 0)', 0.0))
    out.append(('equipment module inside the hardware cone', R['shield']['radius_hw_fwd_m']-lay['module_radius'], 'm rim margin', 0.0))
    return [{'item': n, 'value': round(x, 3), 'unit': u, 'required': req, 'ok': x >= req-1e-9} for n, x, u, req in out]


def deficit_record(cfg, fb, sc, ref, pay_kg, fixed, Om, r, hist):
    """No closure: report the deficit (highest a0 the drive's specific mass allows at this ve) instead of a design."""
    import copy
    A = r.get('architecture') or {}
    ve = v(cfg['mission']['ve_km_s'])*1e3
    k = fb['canon'].val(sc['tanks']['mass_per_m3'], cfg['base']['tier'])/1.0
    rho_mix = 1/(0.6/58.61+0.4/175.2)
    k_tank = k/rho_mix*1.03
    al = fb['closure'].allowances(sc); extra = sum(al.values())
    alpha = (A.get('alpha_hw', 0)+A.get('alpha_rad', 0))/A['eta_jet'] if A.get('eta_jet') else None
    a_lim = fb['closure'].a0_limit_g(alpha, ve, k_tank, extra) if alpha else 0.0
    a0 = v(cfg['mission']['a0_g'])
    need_alpha = None
    if alpha and a_lim > 0:
        need_alpha = alpha*a_lim/a0
    return {'version': cfg['version'], 'variant': cfg['variant'], 'architecture': cfg['base']['architecture'], 'tier': cfg['base']['tier'],
            'converged': False, 'reason': r.get('reason'), 'requested_a0_g': a0, 've_km_s': ve/1e3,
            'drive_specific_mass_kg_per_W_jet': alpha, 'max_a0_g_any_size': a_lim, 'deficit_factor': (a0/a_lim) if a_lim else None,
            'required_specific_mass_kg_per_W_jet_zero_payload': need_alpha, 'iterations': hist,
            'note': 'No physical FDP-1 closes at this acceleration. The number is the factor by which drive-plus-radiator mass per watt of jet power must fall.'}
