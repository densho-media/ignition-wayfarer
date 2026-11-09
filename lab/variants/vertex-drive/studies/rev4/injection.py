"""Revision 4 §4: target-injection feasibility for V4 (T00, research only, NON-CANON).

  python3 lab/variants/vertex-drive/studies/rev4/injection.py     # writes results/injection.json (about 3-4 min)

Question: can a target reach the V4 burn point intact, on time and in position, at the V4 pulse rate? Launcher B (T05 Rev 3) answers the
geometry: 45 m of open flight at one target per period needs 8.81 km/s, and a 289 m accelerator then needs 13,700 g. This study asks
whether a D/3He target survives that, compares B, B-long, B-modified and fewer, larger pulses, and books each candidate's mass and power.

Rules kept: V4 is never changed. Every changed pulse rate is a separately labelled FDP-1 case through the Vertex adapter (max_rep_Hz cap).
Survivability numbers are physics estimates with stated inputs, not test data; the evidence table separates the two.
"""
import math

import ledger as LG
from common import C, G0, MU0, core, solve_full, v4_overrides, write_json, VX
import json

T03 = json.loads((VX / 'studies/nozzle/results/nozzle_results.json').read_text())

# ---------------------------------------------------------------------------------------------------------------------------------
# evidence (published or demonstrated) and physics limits (computed here)
# ---------------------------------------------------------------------------------------------------------------------------------
EVIDENCE = [
    {'item': 'IFE gas-gun injector (GA)', 'kind': 'DEMONSTRATED / DESIGN', 'target': 'direct-drive DT capsule in sabot',
     'value': '400 m/s over an 8 m barrel at <= 10,000 m/s2 (1,020 g)',
     'source': 'Petzoldt, Goodin et al., Fusion Sci. Technol. 2003 (ANS article 323); ARIES meeting 2000 (aries.pppl.gov/MEETINGS/0009/Petzoldt.pdf)'},
    {'item': 'Frozen-DT strength in a capsule', 'kind': 'CALCULATED (literature)', 'target': 'layered DT ice below 17 K',
     'value': '> 10,000 m/s2 (1,020 g) allowed; dual-membrane hohlraum support about 2,000 m/s2 (204 g)',
     'source': 'Petzoldt and Moir 1996, as summarised in ARIES/GA injection papers'},
    {'item': 'IFE injector design ranges', 'kind': 'DESIGN STUDIES', 'target': 'layered IFE targets',
     'value': '1,000-10,000 m/s2; 100-400 m/s; the 400 m/s choice is set by chamber heating, not strength',
     'source': 'ARIES-IFE injection reviews (aries.pppl.gov/MEETINGS/0110/Petzoldt.pdf, IAEA IFE CRP Goodin 2001)'},
    {'item': 'Levitated / electromagnetic sabot mock-ups', 'kind': 'DEMONSTRATED (mock-up)', 'target': 'sabot only',
     'value': 'about 500 g', 'source': 'T05 Rev 3 rev3.json launcher_target.tolerance_evidence_g (T05 literature pass)'},
    {'item': 'Two-stage light-gas gun, D2 pellets with sabot', 'kind': 'DEMONSTRATED', 'target': 'solid D2 pellet (MFE fuelling)',
     'value': '3.8 km/s with a sabot (European group); ORNL bare D2 2.85 km/s, plastic 4.5 km/s; repetitive 2.5 km/s at 1 Hz',
     'source': 'ORNL pellet-injector papers (osti.gov/servlets/purl/7043184, /5588343); ORNL-ENEA repetitive two-stage gun'},
    {'item': 'Bare solid hydrogen pellet acceleration', 'kind': 'DEMONSTRATED', 'target': 'solid D2, no layer, no uniformity need',
     'value': 'about 5-6e6 m/s2 (510-610 kg-g) before fracture', 'source': 'T05 Rev 3 MFE_bare_pellet_fracture_g'},
    {'item': 'Sabot stripping at > 1 km/s and many Hz', 'kind': 'NOT DEMONSTRATED', 'target': 'any',
     'value': 'no reliable repetitive sabot separation reported at km/s speeds', 'source': 'ORNL papers note sabot use, not a repetitive separator'},
    {'item': '3He phase', 'kind': 'SOURCE (physical property)', 'target': 'fuel',
     'value': '3He is not solid below 2.93 MPa at any temperature (melting-curve minimum 2.93 MPa at 0.32 K); liquid below 3.3 K',
     'source': 'He-3 melting curve (PLTS-2000 scale)'},
    {'item': 'REBCO neutron tolerance', 'kind': 'SOURCE', 'target': 'closure coils (cross-check for §3)',
     'value': 'degradation already at about 3.3e18 n/cm2; in-situ 14 MeV irradiation at 40 K shows Ic loss far below ex-situ thresholds',
     'source': 'Oxford / UKAEA in-situ REBCO irradiation (ora.ox.ac.uk uuid:b463ec76...); review in sci-08-00178 (MDPI)'},
]

P = {
    'fuel_g': None,                                     # from the solve
    'D_mass_fraction': (0.4, 'equimolar D:3He by atoms (FDP-1 fuel D/3He); mass fraction of D'),
    'rho_D2_solid': (200.0, 'SOURCE: solid D2 kg/m3'), 'rho_He3_liquid': (82.0, 'SOURCE: liquid 3He at 1-2 K, kg/m3'),
    'gamma_He3': (1.5e-4, 'SOURCE: 3He surface tension near 1 K, N/m'), 'mu_He3': (2.0e-6, 'SOURCE (order): liquid 3He viscosity, Pa s'),
    'D2_ice_yield_Pa': ((0.3e6, 1.0e6), 'EXTRAPOLATION: solid D2 yield / creep threshold near 10-17 K'),
    'HDC_allow_Pa': (1.0e9, 'PROTOTYPE: high-density-carbon shell allowable membrane stress (strength several GPa)'),
    'rho_HDC': (3500.0, 'SOURCE'), 'rho_GDP': (1050.0, 'SOURCE'), 'GDP_allow_Pa': (60e6, 'PROTOTYPE polymer shell allowable'),
    'capsule_r_m': (0.02, 'PROTOTYPE capsule outer radius for 0.77 g of D/3He (liquid / solid fuel needs about 1.2 cm radius)'),
    'sabot_to_target': (3.0, 'PROTOTYPE sabot mass per target mass (EM armature + carrier)'),
    'launcher_efficiency': (0.4, 'EXTRAPOLATION: coilgun electrical-to-kinetic'),
    'launcher_kg_per_m': (250.0, 'PROTOTYPE coilgun stages, structure and cooling per metre'),
    'store_J_per_kg': (1000.0, 'EXTRAPOLATION: pulsed capacitor bank energy density'),
    'tip_fluence_J_cm2': (8.3, 'T05 Rev 3 snout-tip X-ray fluence per pulse (launcher B)'),
    'accel_cases_g': ((500.0, 1000.0, 3000.0, 6400.0, 13700.0), 'acceleration levels compared'),
    'placement_mm': (0.1, 'PROTOTYPE: target position tolerance at the burn point after tracking'),
    'steering_mm': (5.0, 'PROTOTYPE: driver beam steering range'),
}


def p(k):
    return P[k][0]


def available_straight(R):
    lay = R['layout']
    return lay['x_forward_shield_aft'] - lay['x_shield_fwd']


# ---------------------------------------------------------------------------------------------------------------------------------
# target classes
# ---------------------------------------------------------------------------------------------------------------------------------

def target_classes(fuel_g):
    """Acceleration limit (g) of each target construction, with the mechanism that sets it."""
    m = fuel_g / 1e3; mD = m * p('D_mass_fraction'); mHe = m - mD
    vD = mD / p('rho_D2_solid'); vHe = mHe / p('rho_He3_liquid')
    r_fuel = (3 * (vD + vHe) / (4 * math.pi)) ** (1 / 3)
    rc = p('capsule_r_m')
    out = []
    # 1. bare solid pellet: D2 only (3He cannot be solid at a usable pressure)
    L = 2 * r_fuel
    out.append({'class': 'solid pellet (D2 only)', 'fits_DHe3': False,
                'limit_g': p('D2_ice_yield_Pa')[1] / (p('rho_D2_solid') * L) / G0,
                'mechanism': 'base stress rho a L below the D2 yield stress; but 3He cannot be carried as a solid (needs > 2.93 MPa), so a '
                             'D/3He target cannot be a bare solid pellet', 'evidence': 'MFE pellets: 5-6e6 m/s2 bare'})
    # 2. layered, liquid 3He in nanofoam (capillary retention against acceleration along the capsule diameter)
    for pore in (25e-9, 10e-9):
        Pc = 2 * p('gamma_He3') / pore
        out.append({'class': f'layered: liquid 3He in {pore * 1e9:.0f} nm foam', 'fits_DHe3': True,
                    'limit_g': Pc / (p('rho_He3_liquid') * 2 * rc) / G0, 'capillary_Pa': Pc,
                    'drain_mm_at_8.81km_s_k1e-13': 1e-13 * p('rho_He3_liquid') * 8810.0 / p('mu_He3') * 1e3,
                    'mechanism': 'liquid relocates once rho a (2 r) exceeds the capillary pressure; drained liquid cannot rewet in a '
                                 '5 ms flight (capillary refill takes seconds); displacement k rho v / mu is independent of a'})
    # 3. layered D2 ice on the wall of a shell (creep under its own inertia)
    for y in p('D2_ice_yield_Pa'):
        out.append({'class': f'layered: D2 ice on a shell wall (yield {y / 1e6:g} MPa)', 'fits_DHe3': True,
                    'limit_g': y / (p('rho_D2_solid') * rc) / G0,
                    'mechanism': 'shear in the ice layer about rho a r; above it the layer slumps (uniformity lost); 3He must still be '
                                 'carried as liquid or gas'})
    # 4. strong-shell gas-filled capsule (B-modified basis): D2 + 3He as gas at 30-77 K, HDC or polymer wall
    nD = mD / 4.028e-3; nHe = mHe / 3.016e-3
    V = 4 / 3 * math.pi * rc ** 3
    for T in (30.0, 77.0):
        Pgas = (nD + nHe) * 8.314 * T / V
        for wall, rho_w, allow in (('HDC', p('rho_HDC'), p('HDC_allow_Pa')), ('GDP polymer', p('rho_GDP'), p('GDP_allow_Pa'))):
            t = Pgas * rc / (2 * allow)
            m_w = 4 * math.pi * rc ** 2 * t * rho_w
            m_tot = m + m_w
            # inertial membrane stress when the sabot carries the rear hemisphere: sigma = m_tot a / (2 pi r t) <= allow - pressure stress
            margin = allow - Pgas * rc / (2 * t) * 0.5          # wall sized at 2x on pressure, so half the allowable is left
            a_lim = margin * 2 * math.pi * rc * t / m_tot
            rho0 = m / V
            out.append({'class': f'strong shell, gas fill {T:.0f} K, {wall}', 'fits_DHe3': True, 'fill_MPa': Pgas / 1e6, 'wall_um': t * 1e6,
                        'wall_g': m_w * 1e3, 'shell_to_fuel': m_w / m, 'limit_g': a_lim / G0,
                        'fuel_density_g_cc': rho0 / 1e3, 'convergence_to_2000': (2000.0 / (rho0 / 1e3)) ** (1 / 3),
                        'gas_scale_height_m': 1.380649e-23 * T / (3.3e-27 * 13700 * G0),
                        'mechanism': 'wall carries its fill pressure and the inertial load; fuel stays uniform because a gas re-equilibrates '
                                     'at sound speed in about 0.1 ms; penalties: wall mass, convergence about 2x the liquid case, a cold '
                                     'high-pressure fill at 196 Hz (fill tube or cold permeation), carbon mix'})
    # 5. indirect-drive capsule support in a hohlraum
    m_cap = m * 1.5
    out.append({'class': 'indirect drive: capsule on membranes / foam in a hohlraum', 'fits_DHe3': True,
                'limit_g': 2000.0 / G0, 'support_stress_kPa_at_13700g': m_cap * 13700 * G0 / (math.pi * rc ** 2) / 1e3,
                'mechanism': 'membrane tents give about 2,000 m/s2 (Petzoldt and Moir); a foam bed must carry m a / (pi r^2), about 160 kPa '
                             'at 13,700 g, i.e. a structural foam that disturbs the drive'})
    return {'fuel_radius_m': r_fuel, 'capsule_radius_m': rc, 'classes': out}


# ---------------------------------------------------------------------------------------------------------------------------------
# field and plasma on the injection axis
# ---------------------------------------------------------------------------------------------------------------------------------

def axis_field(R4, n=66):
    """Vacuum B_z on the axis from the burn point to the shield face, from T03's C_W15 coil set scaled to V4 (all currents as signed by T03)."""
    cg = LG.coils_v4(R4)
    s, fI = cg['scale'], cg['current_factor']
    loops = T03['designs']['C_W15']['loops']
    d = R4['fusion']['xray_standoff_m']
    out = []
    for i in range(n + 1):
        z = d * i / n
        B = 0.0
        for l in loops:
            I = l['current_MA'] * 1e6 * fI; Rr = l['radius_m'] * s; zz = l['z_m'] * s
            B += MU0 * I * Rr ** 2 / (2 * (Rr ** 2 + (z - zz) ** 2) ** 1.5)
        out.append((z, B))
    return out


def axis_plasma(R4):
    """T03's thin-shell rays: plasma that is not stopped near the axis flies to the shield face (strike_by shield)."""
    ts = T03['designs']['C_W15']['thin_shell']
    f = R4['fusion']; Pf = f['gross_fusion_power_W']; rate = f['pellet_rate_Hz']
    plasma_J = f['yield_per_pulse_J'] * (1 - f['xray_escape_fraction'] - f['neutron_escape_fraction'])
    sh = ts['strike_by']['shield']
    r_sh = f['xray_standoff_m'] * math.tan(math.radians(R4['shield']['hardware_half_angle_deg']))
    A = math.pi * r_sh ** 2
    return {'shield_strike_share_of_plasma': sh, 'unstopped_forward_share': ts['unstopped_forward_share'],
            'stopping_radius_by_polar_deg': ts['stopping_radius_m_by_polar_deg'],
            'shield_plasma_J_per_pulse': sh * plasma_J, 'shield_plasma_W': sh * plasma_J * rate,
            'shield_face_m2': A, 'shield_mean_J_cm2_per_pulse': sh * plasma_J / A / 1e4,
            'shield_mean_MW_m2': sh * plasma_J * rate / A / 1e6,
            'note': 'T03 thin-shell MODEL: on the axis (polar 0) no stopping radius exists, so near-axis plasma reaches the shield face '
                    'and any snout on the axis. FDP-1 books this heat in plume_to_hardware (hot loop) but no surface check uses it.'}


# ---------------------------------------------------------------------------------------------------------------------------------
# launcher kinematics and the candidates
# ---------------------------------------------------------------------------------------------------------------------------------

def kin(R, L_open, a_g, rate=None, m_target_kg=None):
    f = R['fusion']; rate = rate or f['pellet_rate_Hz']
    v = L_open * rate                                         # one target in the open per period (minimum)
    a = a_g * G0; L_a = v * v / (2 * a); t_a = v / a
    m_t = m_target_kg or f['pellet_fuel_mass_g'] / 1e3 * 1.5
    m_s = m_t * p('sabot_to_target')
    E_shot = 0.5 * (m_t + m_s) * v * v
    P_kin = E_shot * rate; P_e = P_kin / p('launcher_efficiency')
    E_x = f['xray_escape_fraction'] * f['yield_per_pulse_J']
    F_tip = E_x / (4 * math.pi * (L_open * 100) ** 2)
    return {'rate_Hz': rate, 'open_flight_m': L_open, 'muzzle_m_s': v, 'accel_g': a_g, 'accelerator_m': L_a, 'launch_ms': t_a * 1e3,
            'target_kg': m_t, 'sabot_kg': m_s, 'shot_J': E_shot, 'kinetic_W': P_kin, 'electric_W': P_e,
            'sabot_catcher_W': 0.5 * m_s * v * v * rate, 'tip_xray_J_cm2': F_tip,
            'tip_xray_MW_m2': F_tip * 1e4 * rate / 1e6,
            'launcher_kg': L_a * p('launcher_kg_per_m') + 2 * E_shot / p('launcher_efficiency') / p('store_J_per_kg'),
            'shots_per_mission': rate * C.fdp1.summary(R)['burn_years'] * 3.15576e7}


def open_for_tip(R, F_J_cm2):
    E_x = R['fusion']['xray_escape_fraction'] * R['fusion']['yield_per_pulse_J']
    return math.sqrt(E_x / (4 * math.pi * F_J_cm2 * 1e4))


def coil_hw(ov, R):
    """§3 bottom-up coil hardware (shadowed, TARGET case structure, LiH screen) at this pulse size."""
    cg = LG.coils_v4(R)
    ass = LG.assembly(cg, R, 'shadowed', 'TARGET_composite')
    share = sum(x['share'] + x['strut_share'] for x in ass)
    ch = LG.coil_heat(R, share, ass)
    E, eta = LG.eight(R, ch); circ = LG.circuits(R, ch, eta)
    cm = LG.cooling_mass(ch, ass, 'main_radiator')
    return {'share': share, 'coil_hw_kg': cm['total_kg'], 'C1_winding_minor_m': cg['coils'][0]['winding_minor_m'],
            'C1_radius_m': cg['coils'][0]['radius_m'], 'ch': ch, 'circ': circ}


def coupled_total(ov, R, extra_kg, extra_house_W, coil):
    """Labelled coupled approximation: coil heat via plume_to_hardware, coil + launcher electric via house, hardware via payload."""
    Pf = R['fusion']['gross_fusion_power_W']; L = R['fusion']['ledger_W']
    plume = (L['plume_to_space'] + L['plume_to_hardware']) / Pf
    ptw0 = ov['base']['overrides']['continuous']['plume_to_hardware']['value']
    house0 = ov['base']['overrides']['pulsed']['house_fraction']['value']
    ch = coil['ch']
    kv = {C.PTW: ptw0 + (ch['hot_W'] + ch['pump_hydraulic_W']) / Pf / plume,
          C.HOUSE: house0 + (coil['circ']['warm_added_W'] + extra_house_W) / Pf,
          'mission.payload.reference_t': ov['mission']['payload']['reference_t'] + extra_kg / 1e3}
    Rc = C.fdp1.solve('baseline', core(C.P(ov, **kv)))
    return kv, LG.summary(Rc)


def rate_case(ov, cap):
    o = C.P(ov, **{C.MAXREP: cap}) if cap else ov
    R = C.fdp1.solve('baseline', core(o))
    return o, R


def candidates(ov, R4, cls):
    """B, B-long, B-modified and fewer larger pulses. Every case states the target class it needs."""
    # a layered D/3He target needs both its liquid 3He retained and its D2 ice in place: the weaker of the best 3He option and the
    # conservative D2 ice limit sets it
    he3 = max(c['limit_g'] for c in cls['classes'] if c['class'].startswith('layered: liquid'))
    d2 = min(c['limit_g'] for c in cls['classes'] if c['class'].startswith('layered: D2'))
    best_layered = min(he3, d2)
    gas = [c for c in cls['classes'] if c['class'].startswith('strong shell')]
    gas_pref = next(c for c in gas if '30 K, HDC' in c['class'])
    L_max = available_straight(R4)
    out = []
    coil0 = coil_hw(ov, R4)

    def book(lab, o, R, k, target_class, needs_g, notes, basis):
        coil = coil_hw(o, R) if R is not R4 else coil0
        extra = coil['coil_hw_kg'] + k['launcher_kg']
        kv, cs = coupled_total(o, R, extra, k['electric_W'], coil)
        survives = needs_g >= k['accel_g']
        fits = k['accelerator_m'] <= L_max
        out.append({'label': lab, 'basis': basis, 'kinematics': k, 'target_class': target_class, 'class_limit_g': needs_g,
                    'survives': survives, 'fits_ship': fits, 'available_straight_m': L_max,
                    'uncoupled': LG.summary(R), 'coil_hw_kg': coil['coil_hw_kg'], 'coil_share': coil['share'],
                    'C1_radius_m': coil['C1_radius_m'], 'stand_off_m': R['fusion']['xray_standoff_m'],
                    'yield_GJ': R['fusion']['yield_per_pulse_J'] / 1e9, 'coupled_set': kv, 'coupled': cs, 'notes': notes,
                    'verdict': ('NOT DEFENSIBLE' if not survives else ('DOES NOT FIT' if not fits else
                                ('CANDIDATE, TARGET PHYSICS UNPROVEN' if 'gas' in target_class else 'CANDIDATE')))})

    # B: T05 Rev 3
    kB = kin(R4, 45.0, 13700.0)
    book('B (T05 Rev 3): 45 m open, 13,700 g', ov, R4, kB, f'best layered liquid / ice target (<= {best_layered:,.0f} g)', best_layered,
         '13.7x the strongest layered-target evidence; no D/3He layered construction survives', 'T05 Rev 3 geometry, V4 rate')
    # B-long: same speed, lower acceleration in the longest straight run the ship has
    a_long = kB['muzzle_m_s'] ** 2 / (2 * L_max) / G0
    kBL = kin(R4, 45.0, a_long)
    book(f'B-long: 45 m open, {L_max:.0f} m accelerator ({a_long:,.0f} g)', ov, R4, kBL,
         f'best layered target (<= {best_layered:,.0f} g)', best_layered,
         'the whole ship length still leaves the target above every layered limit', 'longest straight run (shield to forward shield)')
    # B-modified: B kinematics, strong-shell gas-filled capsule
    kBM = kin(R4, 45.0, 13700.0, m_target_kg=(R4['fusion']['pellet_fuel_mass_g'] + gas_pref['wall_g']) / 1e3 * 1.15)
    book('B-modified: B kinematics, 30 K gas-filled HDC capsule', ov, R4, kBM, gas_pref['class'], gas_pref['limit_g'],
         f"wall {gas_pref['wall_um']:.0f} um, {gas_pref['wall_g']:.2f} g; convergence {gas_pref['convergence_to_2000']:.0f} (liquid fuel about 24); "
         'compression at this convergence is unproven (T04 basis assumed liquid/solid density); FDP-1 gain unchanged (not re-derived)',
         'physical basis: gas fill is uniform by construction; strength margin from the HDC wall')
    # fewer, larger pulses: rate caps, tip fluence held at 8.3 J/cm2, layered-target acceleration
    for cap in (150.0, 100.0, 60.0, 30.0, 15.0):
        o, R = rate_case(ov, cap)
        if not R.get('converged'):
            out.append({'label': f'fewer, larger pulses: {cap:g} Hz', 'verdict': 'DOES NOT CLOSE', 'uncoupled': LG.summary(R)}); continue
        Lo = open_for_tip(R, p('tip_fluence_J_cm2'))
        for a_g in (1000.0, 3000.0):
            k = kin(R, Lo, a_g)
            lim = best_layered if a_g <= best_layered else gas_pref['limit_g']
            cls_name = f'layered target (<= {best_layered:,.0f} g)' if a_g <= best_layered else gas_pref['class']
            book(f'fewer, larger pulses: {cap:g} Hz, {a_g:,.0f} g', o, R, k, cls_name, lim,
                 'pulse energy grows as 1/rate; stand-off and coils grow as sqrt(E_p); tip fluence held at B value', 'labelled rate cap (MAXREP)')
    return out


def requirements(R4, k):
    """Alignment, timing and shielding requirements for the recommended configuration."""
    f = R4['fusion']; tf = k['open_flight_m'] / k['muzzle_m_s']
    a_ship = C.fdp1.summary(R4)['peak_g'] * G0
    return {'flight_open_ms': tf * 1e3,
            'lateral_velocity_error_m_s': p('placement_mm') / 1e3 / tf, 'pointing_urad_untracked': p('placement_mm') / 1e3 / k['open_flight_m'] * 1e6,
            'pointing_urad_with_steering': p('steering_mm') / 1e3 / k['open_flight_m'] * 1e6,
            'ship_drift_um_peak_accel': 0.5 * a_ship * tf ** 2 * 1e6,
            'arrival_jitter_ns_for_0.1mm_axial': p('placement_mm') / 1e3 / k['muzzle_m_s'] * 1e9,
            'driver_timing': 'fire on tracked arrival (axial error is absorbed by timing; lateral by beam steering)',
            'shutter': {'closed_before_flash': True, 'opens_after_flash_us': 100.0, 'cycle_Hz': k['rate_Hz'],
                        'note': 'rotating chopper disc at the snout tip, rim at about 500 m/s, slot open about 10 us per shot; '
                                'its rim is in the axis plasma channel (see axis_plasma)'},
            'shielded_transport': 'the accelerator runs inside the shadow-shield cone; the target is behind the shield until the snout; '
                                  'the open flight is one period, so a target never sees an earlier flash',
            'shots_per_mission': k['shots_per_mission'],
            'contact_life': 'a railgun cannot run 1e10 shots; a contactless coilgun (or linear induction) is the only EM class with a credible life'}


def coupled_launcher(ov):
    """Launcher B-modified on the §3 coupled ship (coil hardware booked). The heavier ship needs more fusion power; FDP-1 raises the pulse
    rate (312 Hz) unless it is capped, and a capped rate means larger pulses and a longer stand-off. Tip fluence held at 8.3 J/cm2."""
    from common import read_json
    lg = read_json('ledger.json')
    c = next(x for x in lg['cases'] if x['label'] == lg['preferred'])
    kv = c['coupled']['set']
    out = []
    for cap in (None, 250.0, 196.0):
        o = C.P(ov, **kv); o = C.P(o, **{C.MAXREP: cap}) if cap else o
        R = C.fdp1.solve('baseline', core(o))
        if not R.get('converged'):
            out.append({'rate_cap_Hz': cap, 'converged': False}); continue
        Lo = open_for_tip(R, p('tip_fluence_J_cm2'))
        k = kin(R, Lo, 13700.0)
        a_fit = k['muzzle_m_s'] ** 2 / (2 * available_straight(R)) / G0
        out.append({'rate_cap_Hz': cap, 'converged': True, 'summary': LG.summary(R), 'stand_off_m': R['fusion']['xray_standoff_m'],
                    'open_flight_m': Lo, 'muzzle_m_s': k['muzzle_m_s'], 'accelerator_m_at_13700g': k['accelerator_m'],
                    'fits_at_13700g': k['accelerator_m'] <= available_straight(R), 'accel_g_to_fit': a_fit,
                    'gas_capsule_survives': a_fit <= 102000})
    return {'label': 'B-modified on the coupled ship (coil hardware booked, labelled approximation)', 'rows': out,
            'adapter_one_target_rule_8.81km_s': 'does not close (convergence.py launcher iteration on the full path, cap falls to 78 Hz)'}


def main():
    ov = v4_overrides()
    R4 = solve_full(ov)
    cls = target_classes(R4['fusion']['pellet_fuel_mass_g'])
    ax = axis_field(R4)
    pl = axis_plasma(R4)
    cand = candidates(ov, R4, cls)
    trade = []
    for L_o in (25.0, 45.0, 64.7):
        for a_g in p('accel_cases_g'):
            k = kin(R4, L_o, a_g)
            trade.append({k2: k[k2] for k2 in ('open_flight_m', 'accel_g', 'muzzle_m_s', 'accelerator_m', 'launch_ms', 'tip_xray_J_cm2',
                                                'tip_xray_MW_m2')})
    viable = [c for c in cand if str(c.get('verdict', '')).startswith('CANDIDATE')]
    rec = min(viable, key=lambda c: c['coupled']['departure_t']) if viable else None
    kB = kin(R4, 45.0, 13700.0)
    ax_open = [b for z, b in ax if z <= kB['open_flight_m'] + 1e-9]
    ax_sum = {'burn_point_T': ax[0][1], 'snout_tip_T': min(ax, key=lambda q: abs(q[0] - 45.0))[1], 'max_open_path_T': max(map(abs, ax_open)),
              'max_to_shield_T': max(abs(b) for _, b in ax),
              'note': 'vacuum field of the T03 C_W15 set at V4 scale; the last 20 m of barrel (snout) and the open path cross it. A metal '
                      'hohlraum at 8.8 km/s through this field takes eddy heating and drag; a non-conducting direct-drive capsule does not. '
                      'The coilgun stages in the snout run in this background field.'}
    out = {'study': 'Revision 4 section 4, target injection (T00)', 'axis_field_summary': ax_sum, 'status': 'MODEL, research only, NON-CANON',
           'parameters': {k: {'value': v[0], 'basis': v[1]} for k, v in P.items() if v},
           'evidence': EVIDENCE, 'target_classes': cls, 'axis_field_T': ax, 'axis_plasma': pl,
           'accel_vs_length': trade, 'candidates': cand,
           'recommended': rec and {'label': rec['label'], 'requirements': requirements(R4, rec['kinematics'])},
           'b_requirements': requirements(R4, kin(R4, 45.0, 13700.0))}
    out['coupled_launcher'] = coupled_launcher(ov)
    write_json('injection.json', out)
    for r in out['coupled_launcher']['rows']:
        print('coupled', r.get('rate_cap_Hz'), r.get('summary', {}).get('departure_t'), r.get('open_flight_m'), r.get('muzzle_m_s'),
              r.get('accelerator_m_at_13700g'), r.get('accel_g_to_fit'))
    for c in cls['classes']:
        print(f"{c['class'][:58]:58s} limit {c['limit_g']:>12,.0f} g")
    print(ax_sum)
    print(f"axis field: burn {ax[0][1]:.2f} T, max {max(abs(b) for _, b in ax):.2f} T; shield plasma {pl['shield_plasma_W'] / 1e9:.0f} GW, "
          f"{pl['shield_mean_J_cm2_per_pulse']:.0f} J/cm2 per pulse")
    for c in cand:
        k = c.get('kinematics', {})
        print(f"{c['label'][:58]:58s} {c['verdict']:15s} v {k.get('muzzle_m_s', 0):6.0f} L_a {k.get('accelerator_m', 0):7.0f} m "
              f"dep {c['uncoupled'].get('departure_t') or 0:8,.0f} coupled {c.get('coupled', {}).get('departure_t') or 0:9,.0f} t")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
