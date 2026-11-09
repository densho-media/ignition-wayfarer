"""Revision 4 §3: closure-coil energy ledger for V4 (T00, research only, NON-CANON).

  python3 lab/variants/vertex-drive/studies/rev4/ledger.py      # writes results/ledger.json (about 1-2 min, 4 cores not needed)

What FDP-1 does (protected, unchanged): the hot loop takes plasma on hardware, the recovery conversion loss and the escaping radiation
caught by the solid angle Omega = nozzle loops + nozzle struts + shadow shield. The forward closure coils C1 and C2 (VTX-03D, T03 design
C_W15) are not in Omega, so their interception is booked as radiation to space.

What this postprocessor does:

1. Builds the closure-coil assembly bottom-up (winding, cryostat, neutron and thermal screen, armour, coolant, structural case, struts)
   at V4 scale and computes its projected solid angle from the burn point.
2. Splits the V4 ledger into the eight terms the brief names, moving the coil interception out of radiation to space and drawing the
   coil-cooling electricity out of the plasma through the recovery system. The sum stays the gross fusion power exactly.
3. Splits the coil heat once into hot (armour coolant), warm (neutron screen, back-face leak, cryoplant rejection) and cold (winding).
4. Books each case two ways:
   - POSTPROCESS: the V4 ship unchanged, the ledger relabelled. Mass and radiator consequences are reported, not solved.
   - COUPLED APPROXIMATION (labelled): FDP-1 re-solved with the coil heat through plume_to_hardware (same 1,800 K hot loop), the coil
     warm and electric loads through house_fraction (warm loop, drawn from recovery) and the coil hardware mass through the payload.
     This is a converged FDP-1 solution of an approximate model, not of the true geometry: FDP-1 still believes the heat is plasma and
     the mass is payload. The relabelling restores the categories afterwards. It is not a fully converged spacecraft design.
"""
import json
import math

from common import C, MU0, SIGMA_SB, YEAR, solve_full, v4_overrides, write_json, VX

T03 = json.loads((VX / 'studies/nozzle/results/nozzle_results.json').read_text())

# ---------------------------------------------------------------------------------------------------------------------------------
# assumptions (each one labelled)
# ---------------------------------------------------------------------------------------------------------------------------------
A = {
    'B_surface_T': (25.0, 'T03 design basis (conductor surface field)'),
    'dynamic_factor': (1.25, 'PROTOTYPE: pulse field compression on top of the static hoop and inter-coil loads (D-21 would set it)'),
    'layers_m': ({'ground_insulation': 0.02, 'cryostat_wall': 0.03, 'vacuum_mli_80K_screen': 0.15, 'shadow_margin': 0.05},
                 'PROTOTYPE radial build between the winding and the burn-facing screen'),
    'armour_W_m': (0.005, 'CFC monoblock armour on Mo-TZM lithium tubes (durability.py: carbon is the only solid that survives every '
                          'spectrum band at 4 J/cm2; conduction limits it to 5.7 mm at 7.8 MW/m2)'),
    'armour_density': (1850.0, 'CFC'),
    'coolant_channel_m': (0.030, 'PROTOTYPE lithium channel behind the armour'),
    'screens': ({'LiH': (780.0, 0.12, 'lithium hydride, the SNAP-era space shadow-shield material (T02 LiH loop shoes); '
                         'fast-neutron e-fold 0.12 m, band 0.08-0.18 (EXTRAPOLATION from removal cross sections); 600-700 K'),
                 'WC_steel': (9000.0, 0.10, 'tungsten carbide / B4C / steel; e-fold 0.10 m, band 0.07-0.15 (EXTRAPOLATION)')},
                'burn-facing neutron screen, warm loop; (density kg/m3, fast-neutron e-folding length m)'),
    'rebco_fluence_n_cm2': (3e18, 'SOURCE (order): REBCO critical current degrades above ~3e18 n/cm2 fast fluence (Prokopec et al. 2015, '
                            'Fischer et al. 2018)'),
    'fluence_safety': (3.0, 'PROTOTYPE safety factor on the fluence limit'),
    'neutron_mean_MeV': (4.0, 'EXTRAPOLATION: mix of 2.45 MeV D-D and 14.1 MeV D-T neutrons'),
    'neutron_escape_factor': (1.0, 'FDP-1 uncollided escape exp(-tau_n); x10 sensitivity for scattered neutrons that leave the fuel'),
    'winding_deposit': (0.5, 'PROTOTYPE share of the neutron energy reaching the winding that deposits there'),
    'J_e_A_m2': (150e6, 'TARGET engineering current density of a REBCO winding pack (25 T class magnets 100-300 A/mm2)'),
    'winding_density': (7000.0, 'PROTOTYPE winding pack density (REBCO tape, Cu stabiliser, steel, insulation), kg/m3'),
    'case_options': ({'TARGET_composite': (1600.0, None, 'FDP-1 nozzle_kg_per_J 5.35e-7 kg/J (2x CFRP specific strength)'),
                      'CFRP_1.2GPa': (1600.0, 1.2e9, 'unidirectional CFRP hoop band, 1.2 GPa working stress at 20 K'),
                      'cryo_steel_0.66GPa': (7900.0, 0.66e9, 'ITER-class 316LN case, 660 MPa allowable')},
                     'hoop structure options; mass = rho / sigma x 2 pi R T'),
    'strut_sigma': (1.2e9, 'CFRP strut working stress (axial coil loads)'),
    'struts_per_coil': (6, 'PROTOTYPE'),
    'strut_armour_m': (0.06, 'PROTOTYPE armour and screen on each strut face'),
    'armour_T_K': (1800.0, 'hot-loop temperature (FDP-1 hot radiator)'),
    'warm_T_K': (628.0, 'V4 warm-loop temperature'),
    'foils': (10, 'PROTOTYPE reflective foils between armour back face and the warm screen (emissivity 0.1 each)'),
    'mli_80K_W_m2': (30.0, 'EXTRAPOLATION: MLI from a 628 K screen to an 80 K shield (1.5 W/m2 from 300 K scaled with T^4)'),
    'mli_20K_W_m2': (0.1, 'SOURCE (order): MLI from 80 K to 20 K'),
    'cryo_W_per_W_20K': ((628 - 20) / 20 / 0.30, 'Carnot from 20 K to the 628 K warm loop at 30 % of Carnot'),
    'cryo_W_per_W_80K': ((628 - 80) / 80 / 0.30, 'Carnot from 80 K to 628 K at 30 % of Carnot'),
    'li_cp_J_kgK': (4200.0, 'SOURCE: liquid lithium heat capacity'),
    'li_density': (480.0, 'SOURCE: liquid lithium at 1,600-1,800 K'),
    'li_dT_K': (300.0, 'PROTOTYPE coolant rise across the armour (1,500 to 1,800 K)'),
    'li_velocity_m_s': (10.0, 'PROTOTYPE'),
    'li_dp_Pa': (1.0e6, 'T05 Rev 3 loop pressure drop'),
    'pump_efficiency': (0.6, 'EXTRAPOLATION: liquid-metal EM pump'),
    'pump_kg_per_W': (1e-3, 'EXTRAPOLATION: 1 kg/kW electric for large EM pumps'),
    'pipe_kg_per_m3_flow': (None, 'Mo-TZM tubes of 0.15 m radius, wall r/50 (1 MPa, 50 MPa creep allowable at 1,800 K), min 2 mm'),
    'loop_length_m': ({'main_radiator': 170.0, 'shadow_cone': 40.0}, 'PROTOTYPE out-and-back coolant path'),
    'cryo_kg_per_W_in': ((2e-3, 1e-2), 'EXTRAPOLATION: cryoplant mass per watt of input, turbo-Brayton TARGET and conservative'),
    'shadow_cone_T_K': ((1800.0, 1400.0, 1000.0), 'alternative coil radiators in the coils own shadow cone'),
    'emissivity': (0.85, 'radiator emissivity, two faces'),
}


def a(k):
    return A[k][0]


# ---------------------------------------------------------------------------------------------------------------------------------
# coil assembly
# ---------------------------------------------------------------------------------------------------------------------------------

def self_tension(I, R, a_w):
    """Hoop tension of a thin ring carrying I: T = mu0 I^2 (ln(8R/a) - 3/4) / (4 pi) (from dL/dR, L = mu0 R (ln(8R/a) - 7/4))."""
    return MU0 * I * I * (math.log(8 * R / a_w) - 0.75) / (4 * math.pi)


def stored(I, R, a_w):
    return 0.5 * MU0 * R * (math.log(8 * R / a_w) - 1.75) * I * I


def coils_v4(R4):
    """T03 C_W15 closure coils scaled to the V4 pulse: geometry with the X-ray stand-off, current field-limited (W ~ L I^2 ~ R I^2)."""
    c = T03['designs']['C_W15']; d1 = T03['pulse']['R_s_m']
    s = R4['fusion']['xray_standoff_m'] / d1
    k = C.generations()['V4']['overrides']['base']['overrides']['pulsed']['nozzle_kg_per_J']['optimistic']
    W4 = R4['mass']['items_kg']['nozzle loops (virial structure)'] / k
    W1 = c['ledger']['stored_J']
    fI = math.sqrt((W4 / W1) / s)
    out = []
    for loop, st in zip(c['loops'][:2], c['stresses'][:2]):
        I = loop['current_MA'] * 1e6 * fI; R = loop['radius_m'] * s; d = loop['distance_m'] * s; z = loop['z_m'] * s
        a_w = MU0 * I / (2 * math.pi * a('B_surface_T'))
        T_self = self_tension(I, R, a_w)
        F_rad = st['net_radial_from_others_MN'] * 1e6 * fI ** 2; F_ax = st['net_axial_from_others_MN'] * 1e6 * fI ** 2
        T = (T_self + max(F_rad, 0.0) / (2 * math.pi)) * a('dynamic_factor')
        out.append({'name': loop['name'].split('@')[0], 'polar_deg': loop['polar_deg'], 'distance_m': d, 'radius_m': R, 'z_from_burn_m': z,
                    'current_A': I, 'winding_minor_m': a_w, 'stored_J': stored(I, R, a_w), 'tension_self_N': T_self,
                    'radial_from_others_N': F_rad, 'axial_from_others_N': F_ax, 'design_tension_N': T,
                    'T03_envelope_share_x3': st['solid_angle_share_envelope_x3']})
    return {'scale': s, 'current_factor': fI, 'W_V4_J': W4, 'W_V1_J': W1, 'coils': out}


def strut_share(p0, p1, width, n=400):
    """Solid-angle share (of 4 pi) of a flat strip of `width` along segment p0-p1 (r, z from the burn), seen from the burn, per strut."""
    tot = 0.0
    (r0, z0), (r1, z1) = p0, p1
    L = math.hypot(r1 - r0, z1 - z0); ux, uz = (r1 - r0) / L, (z1 - z0) / L
    for i in range(n):
        t = (i + 0.5) / n; r = r0 + t * (r1 - r0); z = z0 + t * (z1 - z0); d = math.hypot(r, z)
        cos_view = abs(r * ux + z * uz) / d                     # component of the strut along the line of sight
        tot += width * (L / n) * math.sqrt(max(0.0, 1 - cos_view ** 2)) / d ** 2
    return tot / (4 * math.pi)


def assembly(cg, R4, layout='shadowed', case='TARGET_composite', t_screen=None, lam=None, n_factor=1.0, screen='LiH', J_e=None):
    """Radial build, projected shares, cold loads and masses of C1 + C2 for one layout and structure option."""
    rho_sc, lam0, _ = a('screens')[screen]
    lam = lam or lam0
    J_e = J_e or a('J_e_A_m2')
    f = R4['fusion']; Pf = f['gross_fusion_power_W']
    P_n = f['neutron_escape_fraction'] * Pf * n_factor
    burn_s = C.fdp1.summary(R4)['burn_years'] * YEAR
    lay = a('layers_m'); inner = sum(lay.values())
    rho_case, sig_case, _ = a('case_options')[case]
    k_target = 5.35e-7
    shield_r = R4['fusion']['xray_standoff_m'] * math.tan(math.radians(R4['shield']['hardware_half_angle_deg']))
    out = []
    for c in cg['coils']:
        I, R, d, aw, T = c['current_A'], c['radius_m'], c['distance_m'], c['winding_minor_m'], c['design_tension_N']
        # neutron screen: thick enough for the REBCO fluence limit with a safety factor
        flux = P_n / (a('neutron_mean_MeV') * 1.602e-13) / (4 * math.pi * (d * 100) ** 2)        # n/cm2/s at the coil
        fluence = flux * burn_s
        need = fluence * a('fluence_safety') / a('rebco_fluence_n_cm2')
        t_sc = t_screen if t_screen is not None else max(0.0, lam * math.log(max(need, 1.0)))
        # structure
        k_case = rho_case / sig_case if sig_case else k_target
        case_mass = k_case * 2 * math.pi * R * T
        case_area = case_mass / (rho_case * 2 * math.pi * R)
        delta_case = case_mass - k_target * 2 * math.pi * R * T      # FDP-1 books the field energy's structure at k_target
        w_area = I / J_e; w_mass = w_area * 2 * math.pi * R * a('winding_density')
        if layout == 'wrapped':
            core_r = math.sqrt(aw ** 2 + case_area / math.pi)
        else:                                                       # case behind the winding, in its own shadow
            core_r = aw
        h = core_r + inner + a('coolant_channel_m') + a('armour_W_m')   # the slab screen sits in front, inside this width
        share = math.sin(math.radians(c['polar_deg'])) * h / d
        # struts: carry the axial load to the next structure inward (C1 -> shield rim, C2 -> C1)
        F_ax = abs(c['axial_from_others_N']) * a('dynamic_factor')
        A_strut = F_ax / a('strut_sigma') / a('struts_per_coil')
        w_strut = math.sqrt(A_strut) + 2 * a('strut_armour_m')
        p0 = (R, c['z_from_burn_m'])
        if c['name'] == 'C1':
            p1 = (shield_r, R4['fusion']['xray_standoff_m'])
        else:
            c1 = cg['coils'][0]; p1 = (c1['radius_m'], c1['z_from_burn_m'])
        s_strut = strut_share(p0, p1, w_strut) * a('struts_per_coil')
        L_strut = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        strut_mass = F_ax / a('strut_sigma') * L_strut * 1600.0 * 2      # x2 for joints, armour attachment (PROTOTYPE)
        # screen and armour masses (burn-facing slab of width 2h)
        face = 2 * h * 2 * math.pi * R
        screen_mass = face * t_sc * rho_sc
        armour_mass = face * a('armour_W_m') * a('armour_density')
        cryostat_mass = 2 * math.pi * (aw + inner) * 2 * math.pi * R * 0.03 * 2700.0     # aluminium-alloy wall, 30 mm
        out.append({'name': c['name'], 'layout': layout, 'case': case, 'screen': screen, 'lambda_m': lam, 'projected_half_width_m': h, 'share': share, 'strut_share': s_strut,
                    'strut_width_m': w_strut, 'strut_length_m': L_strut, 'neutron_flux_n_cm2_s': flux, 'mission_fluence_n_cm2': fluence,
                    'screen_attenuation_needed': need, 'screen_m': t_sc, 'case_area_m2': case_area,
                    'masses_t': {'case': case_mass / 1e3, 'case_minus_FDP1_booking': delta_case / 1e3, 'winding_pack': w_mass / 1e3,
                                 'neutron_screen': screen_mass / 1e3, 'armour': armour_mass / 1e3, 'cryostat': cryostat_mass / 1e3,
                                 'struts': strut_mass / 1e3},
                    'faces_m2': {'burn_face': face, 'armour_back': math.pi * h * 2 * math.pi * R,
                                 'cryostat': 2 * math.pi * (aw + inner) * 2 * math.pi * R}})
    return out


# ---------------------------------------------------------------------------------------------------------------------------------
# eight-term ledger
# ---------------------------------------------------------------------------------------------------------------------------------

TERMS = ('radiation_to_space', 'radiation_on_closure_coils', 'radiation_on_other_hardware', 'plasma_on_hardware',
         'plasma_through_nozzle', 'useful_jet', 'conversion_losses', 'coil_cooling_loads')


def coil_heat(R4, share, assy, n_factor=1.0, other_share=0.0):
    """Coil interception split once into hot / warm / cold, plus the coil cooling-system electric loads and masses."""
    f = R4['fusion']; Pf = f['gross_fusion_power_W']
    P_x = f['xray_escape_fraction'] * Pf; P_n = f['neutron_escape_fraction'] * Pf * n_factor
    Qx, Qn = share * P_x, share * P_n
    # geometric weights of each coil in the share (for per-coil loads); assy shares are per-coil incl. struts
    tot = sum(x['share'] + x['strut_share'] for x in assy) or 1.0
    per = []
    for x in assy:
        lam = x['lambda_m']
        w = (x['share'] + x['strut_share']) / tot
        qx, qn = Qx * w, Qn * w
        to_winding = qn * math.exp(-x['screen_m'] / lam) * a('winding_deposit')
        q_screen = qn - to_winding                                       # warm screen (rest assumed absorbed nearby, warm)
        Ta, Tw = a('armour_T_K'), a('warm_T_K'); eps = 0.1; nf = a('foils')
        q_leak = SIGMA_SB * (Ta ** 4 - Tw ** 4) / ((2 / eps - 1) * (nf + 1)) * x['faces_m2']['armour_back']
        q_leak = min(q_leak, qx)
        q80 = a('mli_80K_W_m2') * x['faces_m2']['cryostat']
        q20 = a('mli_20K_W_m2') * x['faces_m2']['cryostat'] + to_winding
        per.append({'name': x['name'], 'xray_W': qx, 'neutron_W': qn, 'armour_hot_W': qx - q_leak, 'back_face_leak_warm_W': q_leak,
                    'neutron_screen_warm_W': q_screen, 'shield_80K_W': q80, 'winding_20K_W': q20,
                    'cryo_input_W': q80 * a('cryo_W_per_W_80K') + q20 * a('cryo_W_per_W_20K')})
    hot = sum(p['armour_hot_W'] for p in per)
    # the 80 K and 20 K loads come out of the warm screen's heat (radiation through MLI) and the winding's neutron heat
    lifted = sum(p['shield_80K_W'] + p['winding_20K_W'] for p in per)
    warm_rad = sum(p['back_face_leak_warm_W'] + p['neutron_screen_warm_W'] for p in per)
    # MLI loads are taken from the warm screen's heat so nothing is counted twice; neutron winding heat is already removed from q_screen
    mli = sum(a('mli_80K_W_m2') * x['faces_m2']['cryostat'] + a('mli_20K_W_m2') * x['faces_m2']['cryostat'] for x in assy)
    warm_rad -= mli
    W_cryo = sum(p['cryo_input_W'] for p in per)
    li_flow = hot / (a('li_cp_J_kgK') * a('li_dT_K')) / a('li_density')                 # m3/s
    W_hyd = li_flow * a('li_dp_Pa'); W_pump = W_hyd / a('pump_efficiency')
    O = other_share * (P_x + P_n)          # escaping radiation on hardware FDP-1's Omega misses (T05 ray cast); armoured, hot loop
    return {'share': share, 'other_share': other_share, 'other_hw_W': O, 'xray_W': Qx, 'neutron_W': Qn, 'per_coil': per,
            'hot_W': hot, 'warm_radiation_W': warm_rad, 'lifted_cold_W': lifted, 'cryo_input_W': W_cryo,
            'pump_electric_W': W_pump, 'pump_hydraulic_W': W_hyd, 'li_flow_m3_s': li_flow, 'check_split_W': hot + warm_rad + lifted - Qx - Qn}


def eight(R4, ch):
    """Eight-term ledger (W) from an FDP-1 record and a coil-heat split. The coil electricity (pumps, cryoplant) is drawn from the plasma
    through the recovery system at FDP-1's recovery efficiency, so plume to space falls by W_e / eta_rec and the recovery loss rises."""
    L = R4['fusion']['ledger_W']
    P_e = R4['fusion']['electric_load_W']; P_ext = R4['fusion']['recovered_power_W']; eta = P_e / P_ext
    W_e = ch['cryo_input_W'] + ch['pump_electric_W']
    Q = ch['xray_W'] + ch['neutron_W']
    O = ch.get('other_hw_W', 0.0)
    out = {'radiation_to_space': L['radiation_to_space'] - Q - O,
           'radiation_on_closure_coils': Q,
           'radiation_on_other_hardware': L['radiation_on_hardware'] + L['radiation_on_conductor'] + O,
           'plasma_on_hardware': L['plume_to_hardware'],
           'plasma_through_nozzle': L['plume_to_space'] - W_e / eta,
           'useful_jet': L['jet'],
           'conversion_losses': L['recovery_loss'] + W_e * (1 / eta - 1) + L['driver_loss'] + L['electric_house'] + L['cryo_input'],
           'coil_cooling_loads': W_e}
    return out, eta


def circuits(R4, ch, eta):
    """Heat per circuit with the coil terms, each W booked once. Pump hydraulic work ends in the lithium (hot); pump motor loss and
    cryoplant input end in the warm loop together with the lifted cold heat; extra recovery loss goes hot like FDP-1's."""
    c = R4['thermal']['circuits']
    W_e = ch['cryo_input_W'] + ch['pump_electric_W']
    hot = dict(c['hot_W']); warm = dict(c['warm_W'])
    hot['coil_armour'] = ch['hot_W']; hot['coil_pump_work'] = ch['pump_hydraulic_W']; hot['coil_recovery_loss'] = W_e * (1 / eta - 1)
    hot['other_hardware_unbooked'] = ch.get('other_hw_W', 0.0)
    warm['coil_screens'] = ch['warm_radiation_W']; warm['coil_cold_lifted'] = ch['lifted_cold_W']
    warm['coil_cryoplant_input'] = ch['cryo_input_W']; warm['coil_pump_motor_loss'] = ch['pump_electric_W'] - ch['pump_hydraulic_W']
    return {'hot_W': hot, 'warm_W': warm, 'hot_total_W': sum(hot.values()), 'warm_total_W': sum(warm.values()),
            'hot_added_W': sum(hot.values()) - c['hot_total_W'], 'warm_added_W': sum(warm.values()) - c['warm_total_W']}


def cooling_mass(ch, assy, route):
    """Coil cooling-system hardware mass (kg), every term labelled."""
    flow = ch['li_flow_m3_s']; L = a('loop_length_m')[route]
    inv = flow * L / a('li_velocity_m_s') * a('li_density')
    r = 0.15; n = flow / a('li_velocity_m_s') / (math.pi * r * r); t = max(0.002, r / 50)
    pipes = n * 2 * math.pi * r * t * 10200.0 * L
    pumps = ch['pump_electric_W'] * a('pump_kg_per_W')
    cryo_lo, cryo_hi = (ch['cryo_input_W'] * k for k in a('cryo_kg_per_W_in'))
    hw = sum(sum(x['masses_t'][k] for k in ('neutron_screen', 'armour', 'cryostat', 'struts', 'winding_pack', 'case_minus_FDP1_booking'))
             for x in assy) * 1e3
    return {'route': route, 'lithium_inventory_kg': inv, 'pipes_kg': pipes, 'pumps_kg': pumps, 'cryoplant_kg': [cryo_lo, cryo_hi],
            'coil_hardware_unbooked_kg': hw, 'total_kg': inv + pipes + pumps + cryo_hi + hw,
            'note': 'coil_hardware_unbooked = screen + armour + cryostat + struts + winding pack + (case - FDP-1 booking at 5.35e-7 kg/J)'}


def radiators(R4, circ, ch):
    th = R4['thermal']['radiators']
    hot_flux = th['hot']['flux_W_m2']; warm_flux = th['warm']['flux_W_m2']
    out = {'main_hot_1800K': {'area_m2': circ['hot_added_W'] / hot_flux, 'mass_kg': circ['hot_added_W'] / hot_flux * th['hot']['areal_kg_m2']},
           'warm_628K': {'area_m2': circ['warm_added_W'] / warm_flux, 'mass_kg': circ['warm_added_W'] / warm_flux * th['warm']['areal_kg_m2']}}
    for T in a('shadow_cone_T_K'):
        q = 2 * a('emissivity') * SIGMA_SB * T ** 4
        out[f'shadow_cone_{T:.0f}K'] = {'area_m2': ch['hot_W'] / q, 'mass_kg': ch['hot_W'] / q * th['hot']['areal_kg_m2'],
                                       'flux_W_m2': q}
    return out


# ---------------------------------------------------------------------------------------------------------------------------------
# coupled approximation
# ---------------------------------------------------------------------------------------------------------------------------------
PTW = C.PTW; HOUSE = C.HOUSE


def coupled(ov, R4, ch, circ, mass_kg):
    """FDP-1 re-solved with the coil loads as per-fusion shares (labelled approximation)."""
    Pf = R4['fusion']['gross_fusion_power_W']; L = R4['fusion']['ledger_W']
    plume = (L['plume_to_space'] + L['plume_to_hardware']) / Pf
    ptw0 = ov['base']['overrides']['continuous']['plume_to_hardware']['value']
    house0 = ov['base']['overrides']['pulsed']['house_fraction']['value']
    hot_share = (ch['hot_W'] + ch['pump_hydraulic_W'] + ch.get('other_hw_W', 0.0)) / Pf
    warm_share = (circ['warm_added_W']) / Pf              # radiation-borne warm heat booked as house load (conservative: also draws recovery)
    pay = ov['mission']['payload']['reference_t']
    kv = {PTW: ptw0 + hot_share / plume, HOUSE: house0 + warm_share, 'mission.payload.reference_t': pay + mass_kg / 1e3}
    R = C.fdp1.solve('baseline', C.P(C.P(ov, **kv), vertex=None) if 'vertex' in ov else C.P(ov, **kv))
    return kv, R


def summary(R):
    s = C.fdp1.summary(R)
    return {k: s.get(k) for k in ('converged', 'departure_t', 'a0_g', 'fusion_TW', 'radiator_t', 'hot_km2', 'warm_km2', 'drive_t', 'propellant_t', 'tank_t', 'end_t', 'xray_standoff_m',
                                  'payload_t', 'wing_tip_radius_m', 'pellet_rate_Hz')}


def case_set(R4, cg):
    """The kept proxy shares plus the bottom-up assemblies."""
    sets = []
    for sh, lab in ((0.029, 'T03 geometry, 11.9 GW (kept case)'), (0.0377, 'C1 grown with the V4 pulse, 15.5 GW (kept case)'),
                    (0.073, 'T05 Rev 2 upper case, 30.1 GW (kept case)')):
        sets.append({'label': lab, 'share': sh, 'assembly': assembly(cg, R4, 'shadowed', 'TARGET_composite')})
    # T05 Rev 4 ray cast (ctwplp f6f527d, rev4_geometry.json): C1 0.0151, C2 0.0082, coil struts and C2 ties 0.0040; beyond FDP-1's
    # Omega it also finds loops + nozzle struts + shield 0.033 (FDP-1 0.0248), wing aft-edge spars 0.0030 and dust guards 0.0007
    ass = assembly(cg, R4, 'wrapped', 'TARGET_composite')
    sets.append({'label': 'T05 Rev 4 ray cast (coils + struts 0.0273; other hardware +0.0118)', 'share': 0.0151 + 0.0082 + 0.0040,
                 'other_share': (0.0199 + 0.0106 + 0.0029 - R4['solid_angle']['total']) + 0.0030 + 0.0007, 'assembly': ass})
    for layout in ('shadowed', 'wrapped'):
        for case in ('TARGET_composite', 'CFRP_1.2GPa', 'cryo_steel_0.66GPa'):
            ass = assembly(cg, R4, layout, case)
            sets.append({'label': f'bottom-up, {layout}, {case}', 'share': sum(x['share'] + x['strut_share'] for x in ass), 'assembly': ass})
    return sets


def run_case(ov, R4, cs, couple=True, n_factor=1.0, route='main_radiator'):
    ass = cs['assembly']
    ch = coil_heat(R4, cs['share'], ass, n_factor, cs.get('other_share', 0.0))
    E, eta = eight(R4, ch)
    circ = circuits(R4, ch, eta)
    cm = cooling_mass(ch, ass, route)
    rad = radiators(R4, circ, ch)
    out = {'label': cs['label'], 'share': cs['share'], 'other_share': cs.get('other_share', 0.0), 'assembly': ass, 'coil_heat': ch, 'eight_W': E, 'eta_recovery': eta,
           'circuits': circ, 'cooling_mass': cm, 'radiators': rad,
           'postprocess_mass_kg': cm['total_kg'] + rad['main_hot_1800K']['mass_kg'] + rad['warm_628K']['mass_kg']}
    if couple:
        kv, Rc = coupled(ov, R4, ch, circ, cm['total_kg'])
        Pf0 = R4['fusion']['gross_fusion_power_W']
        if Rc.get('converged'):
            Q_share = (ch['xray_W'] + ch['neutron_W']) / Pf0; O_share = ch['other_hw_W'] / Pf0
            hot_share = (ch['hot_W'] + ch['pump_hydraulic_W'] + ch['other_hw_W']) / Pf0
            house_share = circ['warm_added_W'] / Pf0
            Lc = Rc['fusion']['ledger_W']; Pfc = Rc['fusion']['gross_fusion_power_W']
            E2 = {'radiation_to_space': Lc['radiation_to_space'] - (Q_share + O_share) * Pfc,
                  'radiation_on_closure_coils': Q_share * Pfc,
                  'radiation_on_other_hardware': Lc['radiation_on_hardware'] + Lc['radiation_on_conductor'] + O_share * Pfc,
                  'plasma_on_hardware': Lc['plume_to_hardware'] - hot_share * Pfc,
                  'plasma_through_nozzle': Lc['plume_to_space'] + hot_share * Pfc,
                  'useful_jet': Lc['jet'],
                  'conversion_losses': Lc['recovery_loss'] + Lc['driver_loss'] + Lc['electric_house'] - house_share * Pfc + Lc['cryo_input'],
                  'coil_cooling_loads': house_share * Pfc}
            # relabelling: FDP-1 still books the coil X-rays as radiation to space and the armour heat as plasma on hardware (taken
            # from plume to space); both go back. The house increment goes to coil loads. The sum stays FDP-1's own (= fusion).
            # Over-count of the approximation: the radiation-borne warm heat is also drawn as electricity from the plasma, adding
            # (warm screens + lifted cold) x (1/eta_rec - 1) of recovery loss to the hot loop (about 5 % of those terms).
            out['coupled'] = {'label': 'COUPLED APPROXIMATION (heat via plume_to_hardware, warm and electric via house_fraction, '
                                       'hardware via payload); not a converged spacecraft design',
                              'set': kv, 'summary': summary(Rc), 'eight_W': E2, 'fusion_W': Pfc}
        else:
            out['coupled'] = {'set': kv, 'summary': summary(Rc), 'converged': False}
    return out


def main():
    ov = v4_overrides()
    R4 = solve_full(ov)
    cg = coils_v4(R4)
    base = summary(R4)
    cases = [run_case(ov, R4, cs) for cs in case_set(R4, cg)]
    # sensitivities on the preferred bottom-up case (shadowed, TARGET case structure)
    pref = next(c for c in case_set(R4, cg) if c['label'] == 'bottom-up, shadowed, TARGET_composite')
    sens = []
    for lab, kw in (('LiH e-fold 0.08 m', {'lam': 0.08}), ('LiH e-fold 0.18 m', {'lam': 0.18}),
                    ('WC / steel screen instead of LiH', {'screen': 'WC_steel'}),
                    ('screen 0.20 m (REBCO fluence limit exceeded 10x)', {'t_screen': 0.20}), ('neutron escape x10', {'n_factor': 10.0}),
                    ('winding J_e 300 A/mm2', {'J_e': 300e6}), ('winding J_e 75 A/mm2', {'J_e': 75e6})):
        nf = kw.pop('n_factor', 1.0)
        ass = assembly(cg, R4, 'shadowed', 'TARGET_composite', n_factor=nf, **kw)
        cs = {'label': lab, 'share': sum(x['share'] + x['strut_share'] for x in ass), 'assembly': ass}
        sens.append(run_case(ov, R4, cs, couple=True, n_factor=nf))
    zero = run_case(ov, R4, {'label': 'zero coil terms (adapter check: must reproduce V4)', 'share': 0.0,
                             'assembly': [dict(x, share=0.0, strut_share=0.0) for x in pref['assembly']]}, couple=False)
    sens.append(run_case(ov, R4, {**pref, 'label': 'shadow-cone coil radiators (local loop)'}, couple=False, route='shadow_cone'))
    out = {'study': 'Revision 4 section 3, closure-coil energy ledger (T00)', 'status': 'MODEL, research only, NON-CANON',
           'assumptions': {k: {'value': v[0], 'basis': v[1]} for k, v in A.items()},
           'v4': {'summary': base, 'ledger_W': R4['fusion']['ledger_W'], 'fusion_W': R4['fusion']['gross_fusion_power_W'],
                  'xray_escape_W': R4['fusion']['xray_escape_fraction'] * R4['fusion']['gross_fusion_power_W'],
                  'neutron_escape_W': R4['fusion']['neutron_escape_fraction'] * R4['fusion']['gross_fusion_power_W'],
                  'omega_fdp1': R4['solid_angle']['shares']},
           'coils_v4': cg, 'cases': cases, 'sensitivities': sens, 'preferred': 'bottom-up, shadowed, TARGET_composite'}
    write_json('ledger.json', out)
    for c in cases + sens:
        cp = c.get('coupled', {}).get('summary', {})
        print(f"{c['label'][:52]:52s} share {c['share']:.4f} Q {(c['coil_heat']['xray_W'] + c['coil_heat']['neutron_W']) / 1e9:6.2f} GW "
              f"cryo {c['coil_heat']['cryo_input_W'] / 1e6:7.1f} MW  hw {c['cooling_mass']['total_kg'] / 1e3:7.0f} t  "
              f"coupled {cp.get('departure_t') or 0:9,.0f} t")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
