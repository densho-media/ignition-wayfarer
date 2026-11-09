"""T05 Stage B Revision 2: screening numbers for the launcher, thermal, closure-coil, dust and scale questions (NON-CANON study).

  python3 work/vertex-blender/rev2.py          (about 15 s; writes rev2.json, read by build_vertex.py)

Inputs: the live FDP-1 solve with the V4 registry overrides (screen.solve), screen.json (Stage A envelope), axis_survey.json and the
canonical positions read from the built asset (constants below, with the object they came from). No calculator value is changed.
Labels: MODEL = arithmetic on solved values; EXTRAPOLATION = a published figure scaled to this case; PROTOTYPE = a T05 choice;
UNKNOWN = no basis. Literature anchors are cited in REV2_REPORT.md §6.
"""
import json
import math
from pathlib import Path

import screen

HERE = Path(__file__).resolve().parent
G0 = 9.80665
SIGMA = 5.670374e-8

# canonical positions measured on assets/wayfarer/WF_WAYFARER_001.blend (axis_survey.py, bounding boxes)
CANON = {'spine_x_m': (-112.05, 140.75), 'spine_r_m': 0.95, 'crew_trunk_x_m': (93.85, 134.7), 'dock_x_m': 131.65, 'airlock_x_m': 134.10,
         'dock_corridor_halfwidth_m': 3.0, 'ring_a_aft_face_x_m': 95.15, 'ring_r_m': 30.0, 'ring_inner_hoop_r_m': 25.0,
         'bypass_collar': {'x_m': (72.02, 116.5), 'r_m': (33.0, 35.0)}, 'farm_r_m': (7.75, 34.5), 'forward_shield_r_m': 45.0,
         'thrust_ring_r_m': (5.0, 6.0), 'blade_front_x_m': 48.9}

# T05 PROTOTYPE / literature-anchored constants
TARGET_D_M = 0.0239                    # FDP-1 pellet.diameter_mm
SABOT_KG = 1.7e-3                      # PROTOTYPE sabot mass per target
LAUNCHER_EFF = 0.4                     # PROTOTYPE electrical-to-kinetic efficiency (coilgun class, UNKNOWN)
LAUNCHER_KG_PER_M = 500.0              # PROTOTYPE barrel + coils + supports per metre (UNKNOWN)
IFE_DESIGN_G = (100.0, 1000.0)         # published IFE target-injection design range (EXTRAPOLATION anchor, REV2_REPORT §6)
PELLET_FRACTURE_M_S2 = (5.0e6, 6.0e6)  # bare 2.7-4 mm D2 pellet fracture acceleration (published, REV2_REPORT §6)
PELLET_D_M = 0.003                     # size of those pellets
RHO_D2 = 200.0                         # kg/m3 solid D2
RHO_HE3 = 82.0                         # kg/m3 liquid He-3 near 1.5 K
HE3_LATENT_J_KG = 1.0e4                # about 10 kJ/kg (approximate; UNVERIFIED)
BREECH_X = 85.0                        # PROTOTYPE: breech plug 85-89 m, 4.85 m aft of the crew trunk (93.85)
SNOUT_TIP_D_M = 45.0                   # PROTOTYPE preferred snout tip distance from the burn point
OFFSET_R_M = 3.0                       # option C exit radius on the shield aft face
MODULE_CLEAR_R_M = 6.0                 # module skin 6.5 m less 0.5 m


def launcher(R, e):
    f = R['fusion']['pellet_rate_Hz']; xB = e['x_burn_m']; xSA = e['x_shield_aft_m']; Rs = e['stand_off_m']
    Ex = R['fusion']['yield_per_pulse_J']*R['fusion']['xray_escape_fraction']
    p = R['pellet']; m_t = p['he3_kg']+p['d_kg']
    A_x = math.pi*(TARGET_D_M/2)**2
    he3_budget = p['he3_kg']*HE3_LATENT_J_KG
    sigma_f = [RHO_D2*a*PELLET_D_M for a in PELLET_FRACTURE_M_S2]        # implied D2 strength (EXTRAPOLATION)

    def shell_stress(a):
        # liquid He-3 column pushing on an unsupported D2 shell (conservative; a sabot carries part of it)
        pr = RHO_HE3*a*2*p['core_radius_mm']/1e3
        return pr*(p['core_radius_mm']/1e3)/(2*p['shell_mm']/1e3)

    def option(key, name, L_acc, L_los, extra):
        v = L_los*f
        a = v*v/(2*L_acc)
        s = shell_stress(a)
        kin = 0.5*(m_t+SABOT_KG)*v*v*f
        return {'key': key, 'name': name, 'accelerator_m': L_acc, 'line_of_sight_m': L_los, 'exit_speed_m_s': v, 'accel_m_s2': a,
                'accel_g': a/G0, 'times_ife_design_g': [a/G0/IFE_DESIGN_G[1], a/G0/IFE_DESIGN_G[0]],
                'shell_stress_MPa': s/1e6, 'implied_D2_strength_MPa': [x/1e6 for x in sigma_f], 'stress_margin': [x/s for x in sigma_f],
                'barrel_transit_s': 2*L_acc/v, 'targets_in_barrel': 2*L_acc/v*f, 'kinetic_W': kin, 'electric_W': kin/LAUNCHER_EFF,
                'launcher_mass_kg': L_acc*LAUNCHER_KG_PER_M, 'sabot_flow_kg_day': SABOT_KG*f*86400,
                'sabot_catch_W': 0.5*SABOT_KG*v*v*f, **extra}

    face_flux = Ex*f/(4*math.pi*Rs**2)
    tip_x = xB+SNOUT_TIP_D_M
    # option C: straight line through the burn point and (xSA, OFFSET_R); usable until it reaches the module clear radius
    slope = OFFSET_R_M/(xSA-xB)
    x_end = xB+MODULE_CLEAR_R_M/slope
    r_at_thrust_ring = (e['x_module_fwd_m']-xB)*slope
    opts = [
        option('REV1', 'Rev 1: 20 m barrel ahead of the shield (fails, kept for comparison)', 20.0, e['injection_path_m'],
               {'muzzle_x_m': xSA+3.7+0.2, 'breech_x_m': xSA+3.7+20.2, 'shutter': 'none', 'conflicts': ['FDP-1 magazine at xSF+14.5-16 m', 'LiH plug at xSF+16 m'],
                'status': 'FAILED'}),
        option('A', 'A: axial accelerator in the spine bore, X-ray chopper at the shield aft face', BREECH_X-xSA, Rs,
               {'muzzle_x_m': xSA, 'breech_x_m': BREECH_X, 'shutter': 'chopper at the shield aft face (shield-face flux)', 'shutter_flux_W_m2': face_flux,
                'conflicts': ['spine bore services (canon: distributed stationary services)', 'breech plug 4.85 m aft of the crew trunk',
                              'barrel passes the drive galleries region and the rotor bay approach'], 'status': 'CANDIDATE'}),
        option('B', 'B: spine accelerator + shielded snout, chopper at the snout tip 45 m from the burn', BREECH_X-tip_x, SNOUT_TIP_D_M,
               {'muzzle_x_m': tip_x, 'breech_x_m': BREECH_X, 'snout_m': xSA-tip_x, 'shutter': f'chopper cartridge at the snout tip ({SNOUT_TIP_D_M:.0f} m)',
                'shutter_flux_W_m2': Ex*f/(4*math.pi*SNOUT_TIP_D_M**2), 'tip_flux_vs_shield_face': (Rs/SNOUT_TIP_D_M)**2,
                'conflicts': ['as A', 'snout tip is a new plasma-facing component inside C1 (r 22 m) on the axis'], 'status': 'PREFERRED'}),
        option('C', 'C: offset launcher on a line through the burn point, own shield penetration and chopper', x_end-xSA, math.hypot(xSA-xB, OFFSET_R_M),
               {'muzzle_x_m': xSA, 'breech_x_m': x_end, 'exit_r_m': OFFSET_R_M, 'inclination_deg': math.degrees(math.atan(slope)),
                'r_at_thrust_ring_m': r_at_thrust_ring, 'shutter': 'second chopper at its own penetration', 'shutter_flux_W_m2': face_flux,
                'extra_streaming_paths': 1, 'conflicts': [f'line passes the canon 12 m thrust ring (r 5-6 m) at r {r_at_thrust_ring:.2f} m',
                                                          'second straight shield penetration (bore-sized streaming path)'], 'status': 'REJECTED'}),
    ]
    # B sweep over the snout tip distance
    sweep = []
    for d in (64.7, 55.0, 45.0, 35.0, 25.0):
        v = d*f; L = BREECH_X-(xB+d); a = v*v/(2*L)
        sweep.append({'tip_from_burn_m': d, 'snout_m': xSA-(xB+d), 'exit_speed_m_s': v, 'accel_g': a/G0, 'shell_stress_MPa': shell_stress(a)/1e6,
                      'tip_flux_MW_m2': Ex*f/(4*math.pi*d*d)/1e6})
    # several targets in the open path: exposure to the preceding pulse
    multi = []
    for N in (1, 2, 3, 5, 10):
        v = Rs*f/N
        d_near = Rs/N
        flu = Ex/(4*math.pi*d_near**2) if N > 1 else 0.0
        multi.append({'targets_in_open_path': N, 'speed_m_s': v, 'nearest_at_pulse_m': d_near if N > 1 else None,
                      'xray_fluence_J_m2': flu, 'absorbed_J': flu*A_x, 'he3_boil_off_budget_J': he3_budget,
                      'ratio_absorbed_to_budget': flu*A_x/he3_budget})
    # radiative heating in the last flight by a 1,800 K shield face filling about half the target's sky
    rad = SIGMA*1800.0**4*0.5*A_x*4*(Rs/(Rs*f))           # W on the target surface (4 x cross-section, half sky) x flight time
    safe_d = math.sqrt(Ex/(4*math.pi*0.01*he3_budget/A_x))
    return {'options': opts, 'snout_sweep': sweep, 'multi_target': multi, 'xray_per_pulse_J': Ex, 'pulse_Hz': f,
            'pulse_interval_s': 1/f, 'shield_face_flux_W_m2': face_flux, 'target_mass_kg': m_t, 'he3_boil_off_budget_J': he3_budget,
            'last_flight_radiant_J_black': rad, 'distance_for_1pct_budget_m': safe_d,
            'rule': 'a target on a straight line to the burn point at a pulse instant is destroyed; so v >= (shuttered line-of-sight length) x f, '
                    'and the accelerator must sit behind a shutter or out of line of sight'}


def thermal(R, e, S):
    th = R['thermal']; hot = th['radiators']['hot']; w = e['wing']
    calc_area = (w['hot_band_r_m'][1]-w['hot_band_r_m'][0])*(w['x_m'][1]-w['x_m'][0])*2
    g = S['V4_hot_band_mitigations']['hot_aft_of_RADIATOR_FRONT_and_20m_clear_of_C1']
    graded_area = (g['hot_r_m'][1]-g['hot_r_m'][0])*(g['hot_x_m'][1]-g['hot_x_m'][0])*2
    # canonical 1,800 K blades seen from the wing hot band: worst irradiance on a blade face
    best = 0.0
    for xb in (-120.0, -40.0, 40.0):
        for rb in (10.0, 20.0, 35.0):
            for nm, layout in (('calc', (w['x_m'][0], w['x_m'][1], w['hot_band_r_m'][0], w['hot_band_r_m'][1])),
                               ('graded', (g['hot_x_m'][0], g['hot_x_m'][1], g['hot_r_m'][0], g['hot_r_m'][1]))):
                a = math.radians(30.0)
                p = (xb, rb*math.cos(a), rb*math.sin(a))
                n = (0.0, math.sin(a), -math.cos(a))                 # blade face normal toward the wing plane
                E, F = screen.irradiance(layout, w['hot_T_K'], p, n, n=70)
                best = max(best, E) if nm == 'calc' else best
    emitted = 0.9*SIGMA*w['hot_T_K']**4
    # Rev 2 preferred: graded hot band with the canonical hot blades retired and their reused area moved into the wing
    chord_g = g['hot_x_m'][1]-g['hot_x_m'][0]
    r_hot_end = w['hot_band_r_m'][0]+hot['planform_m2']/(2*chord_g)
    corner = (w['x_m'][1]-g['hot_x_m'][1])*(r_hot_end-w['hot_band_r_m'][0])*2
    full_chord = w['x_m'][1]-w['x_m'][0]
    warm_area = th['radiators']['warm']['planform_m2']
    tip_pref = r_hot_end+(warm_area-corner)/(2*full_chord)
    xa = CANON['ring_a_aft_face_x_m']; best_ring = 0.0
    for azd in (5, 15, 30, 45, 60, 75, 85):
        aa = math.radians(azd)
        for rr in (28.0, 30.0):
            E, _ = screen.irradiance((g['hot_x_m'][0], g['hot_x_m'][1], w['hot_band_r_m'][0], r_hot_end), w['hot_T_K'],
                                     (xa, rr*math.cos(aa), rr*math.sin(aa)), (-1, 0, 0), n=90)
            best_ring = max(best_ring, E)
    pref = {'hot_x_m': g['hot_x_m'], 'hot_r_m': [w['hot_band_r_m'][0], r_hot_end], 'hot_area_m2': 2*chord_g*(r_hot_end-w['hot_band_r_m'][0]),
            'corner_warm_m2': corner, 'tip_r_m': tip_pref, 'span_m': 2*tip_pref, 'span_change_m': 2*(tip_pref-w['tip_r_m']),
            'ring_A_W_m2': best_ring, 'C1_W_m2_upper': g['C1_W_m2']}
    return {'preferred_rev2': pref,
        'hot_circuit_W': th['circuits']['hot_total_W'], 'hot_planform_m2': hot['planform_m2'], 'canon_blades_reused_m2': hot['reused_m2'],
        'wing_extension_m2': hot['extension_m2'], 'calc_wing_hot_band_m2': calc_area, 'graded_wing_hot_band_m2': graded_area,
        'calc_matches_extension': abs(calc_area-hot['extension_m2'])/hot['extension_m2'], 'graded_matches_extension': abs(graded_area-hot['extension_m2'])/hot['extension_m2'],
        'blades_share_of_hot_area': hot['reused_m2']/hot['planform_m2'],
        'hot_sources_W': th['circuits']['hot_W'], 'warm_total_W': th['circuits']['warm_total_W'], 'warm_planform_m2': th['radiators']['warm']['planform_m2'],
        'blade_irradiance_from_wing_W_m2': best, 'blade_emitted_W_m2': emitted, 'blade_net_loss_fraction': best/emitted,
        'ring_A_W_m2': {'calc': e['ring_A_irradiance']['hot_band']['aft_face']['W_m2'], 'graded': g['ring_A_aft_face_W_m2']},
        'C1_W_m2': {'calc': e['closure_coil_C1_irradiance']['facing_fwd_z4.8m']['W_m2'], 'graded': g['C1_W_m2']},
        'canon_blades_on_ring_A_W_m2': S['canon_blades_on_ring_A_W_m2'],
        'graded_geometry': {'hot_x_m': g['hot_x_m'], 'hot_r_m': g['hot_r_m'], 'chord_m': g['hot_x_m'][1]-g['hot_x_m'][0],
                            'tip_m': w['tip_r_m'], 'warm_starts_r_m': g['hot_r_m'][1], 'forward_root_corner': 'X 48.9-88.0 m, r 10-1,061 m: warm circuit (550 K capacitors) by the rings'},
        'graded_structural': 'hot band 1,061 m long instead of 847 m: the 1,800 K / 628 K thermal break becomes an L (spanwise at r 1,061 m aft of X 48.9 m, '
                             'chordwise at X 48.9 m from r 10 to 1,061 m), so the hot manifold no longer runs the whole chord and the break carries '
                             'a chordwise expansion joint; the spars see 1,800 K over 212 m of the 267 m root chord',
    }


def coils(R, e):
    Ex_W = R['shield']['xray_escape_W']; Rs = e['stand_off_m']
    L1 = R['nozzle']['loops'][0]
    areal = L1['armour_kg']/(2*math.pi*L1['r']*2*L1['envelope_radius_m'])
    out = []
    for c in e['closure_coils']:
        w = 2*c['envelope_r_m'][1]
        A = 2*math.pi*c['r_m']*w
        share = A/(4*math.pi*Rs**2)
        out.append({'name': c['name'], 'r_m': c['r_m'], 'x_m': c['x_m'], 'burn_face_m2': A, 'solid_angle_share': share,
                    'xray_W': share*Ex_W, 'flux_W_m2': Ex_W/(4*math.pi*Rs**2), 'armour_kg_at_loop_areal': A*areal,
                    'shadow_cone_r_at_coil_m': (c['x_m']-e['x_burn_m'])*math.tan(math.radians(e['hardware_cone_deg']))})
    # indicative C1 strut sizing (compression into the shield reaction ring), 6 struts
    c1 = e['closure_coils'][0]; ring_r = e['shield_r_hw_m']+1.0; xr = e['x_shield_aft_m']-0.8
    Ls = math.hypot(c1['x_m']-xr, c1['r_m']-ring_r)
    struts = []
    for F in (0.2e9, 1.9e9):
        A_tot = F/0.6e9
        r_t = 0.8; t_w = A_tot/6/(2*math.pi*r_t)
        I = math.pi*r_t**3*t_w
        Pcr = math.pi**2*150e9*I/Ls**2
        struts.append({'axial_force_N': F, 'allowable_Pa': 0.6e9, 'area_total_m2': A_tot, 'tube_r_m': r_t, 'wall_m': t_w,
                       'mass_kg': A_tot*Ls*1600.0, 'buckling_per_strut_N': Pcr, 'load_per_strut_N': F/6})
    strut_proj = 6*2*0.8*Ls
    return {'coils': out, 'loop_armour_areal_kg_m2': areal, 'loops_xray_booked_W': R['thermal']['circuits']['hot_W']['radiation_on_nozzle_loops'],
            'coil_xray_total_W': sum(c['xray_W'] for c in out), 'coil_armour_total_kg': sum(c['armour_kg_at_loop_areal'] for c in out),
            'hot_flux_W_m2': R['thermal']['radiators']['hot']['flux_W_m2'],
            'extra_hot_area_m2': sum(c['xray_W'] for c in out)/R['thermal']['radiators']['hot']['flux_W_m2'],
            'struts': {'length_m': Ls, 'cases': struts, 'xray_W': strut_proj/(4*math.pi*Rs**2)*Ex_W, 'note': 'CFRP 0.6 GPa, E 150 GPa, 1,600 kg/m3 (PROTOTYPE)'},
            'hoop': {'tension_N': [3e9, 7e9], 'structure_kg': [855e3, 1281e3], 'source': 'T03 HANDOFF E (unbooked)'}}


def dust(e):
    xB = e['x_burn_m']; t = math.tan(math.radians(e['hardware_cone_deg'])); xs = e['x_shield_aft_m']
    r0 = (xs-xB)*t
    tb_front = 137.9+e['tanks_TB']['added_length_m']
    corridor_aft = CANON['dock_x_m']-CANON['dock_corridor_halfwidth_m']
    opts = {}
    for key, x_end in (('A_FULL', xB+45.0/t), ('B_SHORT', CANON['ring_a_aft_face_x_m']-10.0), ('B2_DOCK_CLEAR', corridor_aft-3.6), ('C_BUMPERS_ONLY', None)):
        if x_end is None:
            opts[key] = {'edge_x_m': None, 'shadow_r_m': e['shield_r_hw_m'], 'cone_area_m2': 0.0, 'mass_t': [0.0, 0.0], 'penetrations': 0}
            continue
        r1 = (x_end-xB)*t
        slant = math.hypot(x_end-xs, r1-r0)
        area = math.pi*(r0+r1)*slant
        pen = sum(1 for x in (CANON['dock_x_m'], CANON['airlock_x_m']) if x_end > x-3.0)*(1 if x_end < CANON['dock_x_m']-3 else 1)
        pen = (2 if x_end > corridor_aft else 0)+(1 if x_end > CANON['airlock_x_m']-1.5 else 0)
        drift_1deg = (tb_front-x_end)*math.tan(math.radians(1.0))
        collar = x_end > 93.0
        opts[key] = {'edge_x_m': x_end, 'shadow_r_m': r1, 'cone_area_m2': area, 'mass_t': [22*area/65100.0, 90*area/65100.0],
                     'penetrations': pen, 'shadow_loss_at_TB_front_1deg_m': drift_1deg, 'meets_bypass_collar': collar}
    A_area = opts['A_FULL']['cone_area_m2']
    for k, o in opts.items():
        rs = o['shadow_r_m']
        o['exposed_annuli_m2'] = {
            'ring_A_face (r 25-30)': 0.0 if rs >= 30 else math.pi*(30**2-max(rs, 25)**2),
            'farm and T-B tanks (r 7.75-34.5)': 0.0 if rs >= 34.5 else math.pi*(34.5**2-max(rs, 7.75)**2),
            'forward shield aft face (r 34.5-45)': 0.0 if rs >= 45 else math.pi*(45**2-max(rs, 34.5)**2)}
        o['mass_t'] = [22*o['cone_area_m2']/A_area, 90*o['cone_area_m2']/A_area]
    return {'options': opts, 'cone_deg': e['hardware_cone_deg'], 'TB_front_x_m': tb_front,
            'leading_edge_m2_per_cm': 202.0, 'note': 'axial dust from -X (braking, engine first); shadow = cylinder of the skirt edge radius; '
                                                    'mass scaled from T02 22-90 t for the full skirt by cone area'}


def scale(R, e):
    tb = e['tanks_TB']; bow = 144.75+tb['bow_shift_m']
    return {'length_m': bow-e['loops'][-1]['x_m'], 'x_m': [e['loops'][-1]['x_m'], bow], 'span_m': 2*e['wing']['tip_r_m'],
            'spine_gap_m': [140.75, 140.75+tb['bow_shift_m']], 'TB_x_m': [139.85, 413.25], 'TB_inner_r_m': 7.75,
            'bow_parts_shifted': 549, 'crew_trunk_end_x_m': 134.7, 'bow_access_gap_m': bow-4.0-134.7,
            'drive_galleries_x_m': [R['drivers']['x_aft'], R['drivers']['x_fwd']], 'module_x_m': [e['x_shield_fwd_m'], e['x_module_fwd_m']]}


def main():
    S = json.loads((HERE/'screen.json').read_text())
    R = screen.solve('V4'); e = S['generations']['V4']
    out = {'canon': CANON, 'launcher': launcher(R, e), 'thermal': thermal(R, e, S), 'coils': coils(R, e), 'dust': dust(e), 'scale': scale(R, e)}
    (HERE/'rev2.json').write_text(json.dumps(out, indent=1, default=float))
    L = out['launcher']
    for o in L['options']:
        print(o['key'], f"L {o['accelerator_m']:.1f} m  los {o['line_of_sight_m']:.1f} m  v {o['exit_speed_m_s']/1e3:.2f} km/s  "
              f"{o['accel_g']:,.0f} g  shell {o['shell_stress_MPa']:.2f} MPa (margin {o['stress_margin'][0]:.2f}-{o['stress_margin'][1]:.2f})  "
              f"{o['targets_in_barrel']:.1f} in barrel  {o['electric_W']/1e6:.0f} MWe")
    for s in L['snout_sweep']:
        print('  snout', {k: round(v, 2) for k, v in s.items()})
    for m in L['multi_target']:
        print('  multi', {k: (round(v, 1) if isinstance(v, float) else v) for k, v in m.items()})
    print('  he3 budget J', round(L['he3_boil_off_budget_J'], 2), 'last flight radiant J (black)', round(L['last_flight_radiant_J_black'], 2),
          '1% budget distance m', round(L['distance_for_1pct_budget_m']))
    T = out['thermal']
    print('thermal', {k: (round(v, 3) if isinstance(v, float) else v) for k, v in T.items() if not isinstance(v, (dict, str))})
    C = out['coils']
    for c in C['coils']:
        print('coil', {k: (round(v, 4) if isinstance(v, float) else v) for k, v in c.items()})
    print('coils total xray GW', round(C['coil_xray_total_W']/1e9, 1), 'armour t', round(C['coil_armour_total_kg']/1e3), 'extra hot m2',
          round(C['extra_hot_area_m2']), 'loops booked GW', round(C['loops_xray_booked_W']/1e9, 1), 'areal', round(C['loop_armour_areal_kg_m2'], 1))
    for s in C['struts']['cases']:
        print('strut', {k: round(v, 3) for k, v in s.items()})
    for k, o in out['dust']['options'].items():
        print('dust', k, {q: (round(v, 1) if isinstance(v, float) else v) for q, v in o.items() if not isinstance(v, dict)}, {q: round(v) for q, v in o['exposed_annuli_m2'].items()})
    print('scale', out['scale'])


if __name__ == '__main__':
    main()
