"""Gate 2 Task A: the shield-cone feasibility matrix, every variant through the coupled ship (T00, research only, NON-CANON).

  python3 lab/variants/vertex-drive/studies/gate2/coupled2.py          # writes results/matrix.json (tens of minutes)
  python3 lab/variants/vertex-drive/studies/gate2/coupled2.py NAME...  # selected variants only (merged into matrix.json)

Same fixed-point method as the gate (studies/gate/coupled.py, unchanged): each added item is re-sized on every FDP-1 solution until
the departure mass changes by less than 1 t; FDP-1 and the four-burn engine are untouched (adapter terms through payload, plume heat
and house power). What Gate 2 adds is the geometry of the shadow cone, so that the A1 limit is a computed constraint:

  shield rim     FDP-1's own rule: rim = atan(tan(theta_hw) + m / d_shield), m = 1 m shadow margin, theta_hw = the widest protected
                 hardware envelope seen from the burn point (FDP-1 envelopes; the tank-farm envelopes replaced by the variant's farm)
  shield mass    FDP-1's layered-shield formulas re-evaluated at the variant's cones and distance (the crew core follows the crew cone,
                 the hardware annulus and W face the hardware cone); booked as the difference to FDP-1's own shield. (The gate scaled
                 the whole shield with the hardware cone; that over-counted, because the crew core does not grow.)
  tank farm      radius Rf at its V4 near end (X 109.25 m): 'wide' Rf = 34.5 sqrt(lam) (the gate), 'cone' Rf = the largest radius that
                 keeps the rim at the A1 limit, capped by the forward dust shield (canon r 45, 1 m clearance: Rf <= 44 m); the rest of
                 the propellant goes into more bays (the stretch grows). lam = propellant / V4 propellant.
  spine          N9 longerons on a ring 31 Rf/34.5 m, sized on a stated basis (beam model, Rev 4 spine.py); the result is also given
                 as an FE-calibrated estimate f_FE = k_FE f_beam_cantilever with T05's S5N frame FE ratio (0.110 / 0.200 on V4)
  aft stand-off  dx: the drive (shield, module, nozzle, coils) moves aft by dx on a new truss from the hull (six longerons at r 6.5 m,
                 sized for the same frequency basis with the drive as a tip mass and for the thrust); nine beam lines lengthen by dx
  A1             tilt chi from results/cone.json: thrust-efficiency factor (momentum factor squared; the gate applied the momentum
                 factor, which under-counted), the static pair torque booked as strut mass 1.25 x 2 rho tau / sigma_a (scaled with the
                 coils' stored energy), the residual thrust torque trimmed by a small nozzle turn (reported)
  launcher       B-ray as in the gate (one target in flight per period, 30,000 g)
"""
import copy
import math
import sys
import time

import g2
import coupled as CP
import injection as IN
import spine as SP
from common import C
G = g2.G

K_FE = 0.110 / 0.200            # T05 fe_s5n.json: frame FE / beam cantilever on V4 S5N (full tanks)
DUST_R = 44.0                   # canon forward shield r 45 m (forward_shield rationale), 1 m clearance (T05)
FARM_X = 109.25
M_SHADOW = 1.0                  # FDP-1 shadow_margin_m
RHO_CFRP, SIG_A = 1700.0, 300e6
SPIN_HZ = 4.0 / 60.0
SLOSH_HZ = (0.022, 0.040)
CONE = g2.read('cone.json')


def a1(chi):
    r = next(x for x in CONE['rows'] if abs(x['tilt_deg'] - chi) < 1e-6)
    return r


# ----------------------------------------------------------------------------------------------------------------- shadow geometry
def shield_eval(R, d_sh, th_hw, th_crew):
    """FDP-1 shielding.solve mass formulas at given cones and distance (layer thicknesses and densities from FDP-1's own result)."""
    sh = R['shield']; mk = sh['mass_kg']
    t_c, t_h, w = sh['lih_core_m'], sh['lih_annulus_m'], sh['w_face_m']
    fr = lambda R0, R1, t: math.pi * t / 3 * (R0 * R0 + R0 * R1 + R1 * R1)
    d0 = sh['distance_from_burn_m']
    tc0, th0 = math.tan(math.radians(sh['crew_half_angle_deg'])), math.tan(math.radians(sh['hardware_half_angle_deg']))
    rho = mk['lih_core'] / fr(d0 * tc0 + M_SHADOW, (d0 + w + t_c) * tc0 + M_SHADOW, t_c)
    rho_w = mk['w_face'] / (math.pi * (d0 * th0 + M_SHADOW) ** 2 * w)
    ff = mk['frame'] / (mk['lih_core'] + mk['lih_annulus'] + mk['w_face'] + mk['axial_plug'])
    tc, th = math.tan(math.radians(th_crew)), math.tan(math.radians(th_hw))
    Rc0, Rc1 = d_sh * tc + M_SHADOW, (d_sh + w + t_c) * tc + M_SHADOW
    Rh0, Rh1 = d_sh * th + M_SHADOW, (d_sh + w + t_h) * th + M_SHADOW
    core = rho * fr(Rc0, Rc1, t_c)
    ann = max(0.0, rho * (fr(Rh0, Rh1, t_h) - fr(Rc0, min(Rc1, Rc0 + (Rc1 - Rc0) * t_h / max(t_c, 1e-9)), min(t_h, t_c))))
    wf = rho_w * math.pi * Rh0 ** 2 * w
    tot = (core + ann + wf + mk['axial_plug']) * (1 + ff)
    return {'total_kg': tot, 'radius_hw_aft_m': Rh0, 'rim_polar_deg': math.degrees(math.atan2(Rh0, d_sh)), 'core_kg': core, 'annulus_kg': ann,
            'w_face_kg': wf}


def cones(R, Rf, dx, dz):
    """Protected envelopes seen from the (moved) burn point; the tank envelopes replaced by the variant farm."""
    xb = R['layout']['x_burn'] - dx
    env = []
    for e in R['shield']['envelopes']:
        if e['name'] in ('existing_tank_farm', 'proposed_tanks'):
            continue
        x = e['nearest_x_m']
        if e['name'] == 'equipment_module':
            x = x - dx + dz                                  # the module moves with the drive (and is shortened by a forward shield move)
        env.append((e['name'], e['kind'], e['radius_m'], x))
    env.append(('tank_farm', 'hardware', Rf, FARM_X))
    ang = [{'name': n, 'kind': k, 'radius_m': r, 'x_m': x, 'distance_m': x - xb, 'half_angle_deg': math.degrees(math.atan2(r, x - xb))}
           for n, k, r, x in env]
    th_hw = max(a['half_angle_deg'] for a in ang)
    th_c = max(a['half_angle_deg'] for a in ang if a['kind'] == 'crew')
    d_sh = R['shield']['distance_from_burn_m'] + dz
    rim = math.degrees(math.atan(math.tan(math.radians(th_hw)) + M_SHADOW / d_sh))
    return {'envelopes': ang, 'theta_hw_deg': th_hw, 'set_by': max(ang, key=lambda a: a['half_angle_deg'])['name'], 'theta_crew_deg': th_c,
            'd_shield_m': d_sh, 'rim_deg': rim, 'farm_distance_m': FARM_X - xb}


def farm_radius_for_rim(R, rim_lim, dx, dz):
    d_sh = R['shield']['distance_from_burn_m'] + dz
    t = math.tan(math.radians(rim_lim)) - M_SHADOW / d_sh
    return (FARM_X - (R['layout']['x_burn'] - dx)) * t


# --------------------------------------------------------------------------------------------------------------------------- spine
def spine2(R, R4, d0, Rf, basis, bow_kg=300e3):
    lam = R['mass']['items_kg']['propellant (four burns)'] / R4['mass']['items_kg']['propellant (four burns)']
    a = min((Rf / 34.5) ** 2, max(lam, 1.0))
    Rf_used = 34.5 * math.sqrt(a)
    d = copy.deepcopy(d0); st = d['stretch']; bays = st['bay_masses']
    full = max(b['propellant_kg'] for b in bays); tk = max(b['tank_kg'] for b in bays)
    total = lam * sum(b['propellant_kg'] for b in bays)
    new = [dict(b, propellant_kg=b['propellant_kg'] * min(a, lam), tank_kg=b['tank_kg'] * min(a, lam)) for b in bays]
    extra = total - sum(b['propellant_kg'] for b in new); i = 0; pitch = st['bay_pitch_m']
    while extra > 1e-6:
        q = min(full * a, extra)
        new.append(dict(bays[0], x_m=bays[-1]['x_m'] + pitch * (i + 1), propellant_kg=q, tank_kg=tk * q / full))
        extra -= q; i += 1
    st['bay_masses'] = new; st['x_m'] = [st['x_m'][0], st['x_m'][1] + pitch * (len(new) - len(bays))]
    a_ratio = C.fdp1.summary(R)['a0_g'] / C.fdp1.summary(R4)['a0_g']
    fwd = sum(b['propellant_kg'] + b['tank_kg'] for b in new) + bow_kg
    dep = C.fdp1.summary(R)['departure_t'] * 1e3
    for b in d['loads']['root_axial_by_burn']:
        b['root_axial_N'] = b['root_axial_N'] * fwd / d0['loads']['root_axial_by_burn'][0]['forward_kg'] * a_ratio
        b['accel_g'] = b['accel_g'] * R['structure']['peak_accel_g'] / R4['structure']['peak_accel_g']
        b['ship_kg'] = 3 * dep
    R_long = 31.0 * Rf_used / 34.5
    kind, f_t = basis
    r, res = CP.size_spine(d, R_long, bow_kg, ('free_free' if kind == 'free_free' else 'cantilever', f_t))
    for q in d['loads']['root_axial_by_burn']:
        q['ship_kg'] = dep + res['structure_t'] * 1e3
    SP.GEOMS['_g2'] = (9, R_long, r)
    try:
        res = SP.analyse(d, '_g2', bow_kg)
    finally:
        del SP.GEOMS['_g2']
    fc, ff = res['f_cantilever_Hz'][0], res['f1_Hz']
    fe = K_FE * fc
    return {'farm_radius_m': Rf_used, 'longeron_ring_m': R_long, 'stretch_scale': lam, 'area_scale': a, 'bays': len(new),
            'length_m': st['x_m'][1] - st['x_m'][0], 'tube_r_m': r, 'tube_at_cap': r > 1.99, 'added_t': res['added_structure_t'],
            'structure_t': res['structure_t'], 'f1_cantilever_beam_Hz': fc, 'f1_free_free_beam_Hz': ff, 'f1_FE_estimate_Hz': fe,
            'meets_basis': (fc if kind == 'cantilever' else ff) >= f_t * 0.999,
            'screen': {'above_3x_slosh_0.12Hz': fe >= 3 * SLOSH_HZ[1], 'clear_of_spin_1x_2x': all(abs(fe / (h * SPIN_HZ) - 1) > 0.1 for h in (1, 2)),
                       'note': 'FE estimate = k_FE x beam cantilever (T05 S5N ratio on V4); lowest (torsion-like) mode about 0.43 x that (T05)'},
            'buckling_factor_SF2': res['buckling_factor_SF2'], 'J1': res['J1'], 'lateral_0.01g': res['lateral']['0.01g']}


def aft_truss(R, dx, f_t, extra_tip_kg):
    """New truss between the hull (x_attach) and the moved drive: six CFRP longerons at r 6.5 m, lacing 0.25, rings, +10 % joints."""
    if dx <= 0:
        return {'dx_m': 0.0, 'kg': 0.0}
    it = R['mass']['items_kg']
    tip = sum(it[k] for k in ('shadow shield', 'nozzle loops (virial structure)', 'loop armour', 'target factory, injectors, cryo-targets, misc')) + extra_tip_kg
    E = SP.E; n, Rt = 6, 6.5
    EI = (2 * math.pi * f_t) ** 2 * tip * dx ** 3 / 3
    A_stiff = 2 * EI / (E * n * Rt ** 2)
    T = R['structure']['thrust_N'] * max(1.0, R['structure']['peak_accel_g'] / max(C.fdp1.summary(R)['a0_g'], 1e-9))
    A_str = T * 2.0 / (SIG_A * 0.8) / n
    A = max(A_stiff, A_str)
    kg = RHO_CFRP * n * A * dx * (1 + 0.25 * 1.4) * 1.10 + RHO_CFRP * 2 * math.pi * Rt * SP.tube(0.15)[0] * dx / 7.65
    beams = 9 * 500.0 * dx                                  # beam transport lines, 0.5 t/m each (PROTOTYPE)
    return {'dx_m': dx, 'tip_t': tip / 1e3, 'governed_by': 'stiffness' if A_stiff > A_str else 'thrust', 'truss_t': kg / 1e3,
            'beamlines_t': beams / 1e3, 'kg': kg + beams, 'f_target_Hz': f_t}


# ------------------------------------------------------------------------------------------------------------------------- the run
def run(V, ov, R4, d0, ref_coils_J):
    chi = V.get('tilt', 14.0); A1 = a1(chi)
    eta_base = V.get('eta_T', ov['base']['overrides']['pulsed']['nozzle_efficiency']['optimistic'])
    eta = eta_base * (A1['momentum_factor'] ** 2 if V.get('a1', True) else 1.0)
    dx, dz = V.get('dx', 0.0), V.get('dz', 0.0)
    basis = V.get('basis', ('free_free', 0.2))
    cap = V.get('cap')
    pay0 = ov['mission']['payload']['reference_t']
    ptw0 = ov['base']['overrides']['continuous']['plume_to_hardware']['value']
    house0 = ov['base']['overrides']['pulsed']['house_fraction']['value']
    kv0 = {CP.NOZ: eta}
    R = CP.solve(ov, kv0, cap)
    traj = [C.fdp1.summary(R)['departure_t']]; hist = []; status = 'NON-CONVERGING'; last = None
    for it in range(CP.MAX_IT):
        if not R.get('converged'):
            status = 'FDP-1 DID NOT CLOSE'; break
        Pf = R['fusion']['gross_fusion_power_W']; L = R['fusion']['ledger_W']
        plume = (L['plume_to_space'] + L['plume_to_hardware']) / Pf
        add = {}; hot = house = 0.0
        c = IN.coil_hw(ov, R)
        add['closure coils C1, C2'] = c['coil_hw_kg']; hot += c['ch']['hot_W'] + c['ch']['pump_hydraulic_W']; house += c['circ']['warm_added_W']
        cg = G.LG.coils_v4(R); Wc = sum(q['stored_J'] for q in cg['coils'])
        tau = A1['static_pair_load']['torque_mag_MN_m'] * 1e6 * Wc / ref_coils_J if V.get('a1', True) else 0.0
        add['A1 pair-torque struts'] = 1.25 * 2 * RHO_CFRP * tau / SIG_A
        ln = CP.launcher(R, R4); add['launcher B-ray'] = ln['launcher_kg']; house += ln['electric_W'] + ln['sabot_catcher_W']
        lam = R['mass']['items_kg']['propellant (four burns)'] / R4['mass']['items_kg']['propellant (four burns)']
        s_geo = R['shield']['distance_from_burn_m'] / R4['shield']['distance_from_burn_m']      # nozzle geometry scales with the stand-off
        dz_e = dz * s_geo
        if V['farm'] == 'wide':
            Rf = 34.5 * math.sqrt(max(lam, 1.0))
        elif V['farm'] == 'cone':
            Rf = min(farm_radius_for_rim(R, V['rim_limit'], dx, dz_e), DUST_R, 34.5 * math.sqrt(max(lam, 1.0)))
            Rf = max(Rf, 34.5) if V.get('keep_v4_radius', True) else Rf
        else:
            Rf = V['farm_r']
        sp = spine2(R, R4, d0, Rf, basis)
        add['spine N9 over S2 keels'] = sp['added_t'] * 1e3
        cn = cones(R, sp['farm_radius_m'], dx, dz_e)
        she = shield_eval(R, cn['d_shield_m'], cn['theta_hw_deg'], cn['theta_crew_deg'])
        add['shadow shield change (variant cones)'] = she['total_kg'] - R['shield']['mass_kg']['total']
        at = aft_truss(R, dx, basis[1] if basis[0] == 'cantilever' else basis[1] / 3, add['closure coils C1, C2'])
        add['aft stand-off truss and beam lines'] = at['kg']
        extra = sum(add.values())
        kv = dict(kv0); kv.update({C.PTW: ptw0 + hot / Pf / plume, C.HOUSE: house0 + house / Pf, 'mission.payload.reference_t': pay0 + extra / 1e3})
        Rn = CP.solve(ov, kv, cap)
        s = C.fdp1.summary(Rn) if Rn.get('converged') else {'departure_t': float('nan')}
        traj.append(s['departure_t'])
        hist.append({'departure_t': s['departure_t'], 'farm_r_m': sp['farm_radius_m'], 'stretch_m': sp['length_m'], 'rim_deg': cn['rim_deg'],
                     'added_t': {k: x / 1e3 for k, x in add.items()}})
        R = Rn; last = {'s_geo': s_geo, 'add': add, 'kv': kv, 'sp': sp, 'cn': cn, 'she': she, 'at': at, 'ln': ln, 'tau': tau, 'c': c}
        if not Rn.get('converged'):
            status = 'FDP-1 DID NOT CLOSE'; break
        if s['departure_t'] > CP.BLOWUP_T:
            status = 'NON-CONVERGING (diverges past 400 kt)'; break
        if abs(traj[-1] - traj[-2]) < CP.TOL_T:
            status = 'CONVERGED'; break
    out = {'name': V['name'], 'what': V['what'], 'variant': {k: (list(x) if isinstance(x, tuple) else x) for k, x in V.items()},
           'status': status, 'iterations': len(traj) - 1, 'departure_trajectory_t': traj, 'history': hist, 'eta_T_booked': eta}
    if len(traj) >= 3 and all(math.isfinite(x) for x in traj[-3:]) and abs(traj[-2] - traj[-3]) > 1e-9:
        out['loop_gain'] = (traj[-1] - traj[-2]) / (traj[-2] - traj[-3])
    if last:
        sp, cn, she, at, ln = last['sp'], last['cn'], last['she'], last['at'], last['ln']
        f = R['fusion'] if R.get('converged') else {}
        T = R['structure']['thrust_N'] if R.get('converged') else float('nan')
        lever = A1['momentum']['lever_arm_m'] if V.get('a1', True) else 0.0
        rim_lim_leak = A1['rim_limit_deg']
        c1 = dict(A1['C1_near_side']); sg = last['s_geo']
        c1.update({'z_m': c1['z_m'] * sg, 'r_m': c1['r_m'] * sg, 'envelope_z_m': [z * sg for z in c1['envelope_z_m']],
                   'envelope_r_min_m': c1['envelope_r_min_m'] * sg})
        z0 = cn['d_shield_m']; z1 = z0 + R['shield']['thickness_m'] if R.get('converged') else z0
        c1_clash_z = not (c1['envelope_z_m'][1] < z0 or c1['envelope_z_m'][0] > z1)
        c1_ok = (cn['rim_deg'] <= c1['envelope_polar_deg']) if c1_clash_z else (c1['envelope_r_min_m'] > 6.5)
        out['report'] = {
            '1_shield': {'rim_deg': cn['rim_deg'], 'A1_limit_from_leak_deg': rim_lim_leak, 'theta_hw_deg': cn['theta_hw_deg'], 'set_by': cn['set_by'],
                         'theta_crew_deg': cn['theta_crew_deg'], 'd_shield_m': cn['d_shield_m'], 'shield_radius_m': she['radius_hw_aft_m'],
                         'shield_t': she['total_kg'] / 1e3, 'fdp1_shield_t': R['shield']['mass_kg']['total'] / 1e3 if R.get('converged') else None,
                         'envelope_margins_deg': {e['name']: cn['rim_deg'] - e['half_angle_deg'] for e in cn['envelopes']},
                         'hardware_decades': R['shield']['hardware_decades'] if R.get('converged') else None,
                         'crew_decades_n': R['shield']['neutron_decades'] if R.get('converged') else None,
                         'dust_farm_inside_r44': sp['farm_radius_m'] <= DUST_R + 1e-6,
                         'W_face_fluence_factor_vs_d_shield': (R['shield']['distance_from_burn_m'] / cn['d_shield_m']) ** 2 if R.get('converged') else None},
            '2_mass': {'departure_t': traj[-1], 'status': status},
            '3_rate_Hz': f.get('pellet_rate_Hz'),
            '4_launcher': {k: ln[k] for k in ('muzzle_m_s', 'accelerator_m', 'launcher_kg', 'electric_W')},
            '5_structure': {**{k: sp[k] for k in ('farm_radius_m', 'length_m', 'longeron_ring_m', 'tube_r_m', 'tube_at_cap', 'added_t',
                                                  'f1_cantilever_beam_Hz', 'f1_free_free_beam_Hz', 'f1_FE_estimate_Hz', 'meets_basis', 'screen')},
                            'aft_truss': at},
            '6_coil_and_leak': {'tilt_deg': chi, 'leak_centre_polar_deg': A1['leak_centre_polar_deg'], 'leak_inner_edge_deg': A1['leak_inner_edge_deg'],
                                'rim_below_leak_limit': cn['rim_deg'] <= rim_lim_leak, 'C1_near_side': c1, 'C1_shield_same_z': c1_clash_z,
                                'C1_clear': c1_ok, 'pair_torque_GN_m': last['tau'] / 1e9},
            '7_thrust': {'thrust_MN': T / 1e6, 'residual_lever_m': lever, 'untrimmed_torque_MN_m': T * lever / 1e6,
                         'trim_turn_deg_full_to_dry': [math.degrees(lever / 410.0), math.degrees(lever / 208.0)],
                         'eta_T': eta, 'side_over_axial': A1['momentum']['side_over_axial']},
            'added_t': {k: x / 1e3 for k, x in last['add'].items()}}
        if R.get('converged'):
            out['summary'] = G.LG.summary(R)
    return out


def variants():
    FF, CA2, CA1 = ('free_free', 0.2), ('cantilever', 0.2), ('cantilever', 0.1)
    FE15 = ('cantilever', 0.15 / K_FE)
    P = ('cantilever', 0.1)        # beam cantilever 0.1 Hz ~ T05's practical FE target (free-free 0.087 Hz, between 1x and 2x ring spin)
    V = [
        dict(name='G0', what='gate reference: wide farm, spine free-free 0.2 Hz (beam), A1 14 deg, corrected shield and eta_T', farm='wide', basis=FF),
        dict(name='G0-noA1', what='as G0 without A1 (axisymmetric closure, leak on the shield centre)', farm='wide', basis=FF, a1=False),
        dict(name='G0-P', what='wide farm, spine beam cantilever 0.1 Hz (T05 practical basis)', farm='wide', basis=P),
        dict(name='K1', what='cone farm: rim <= 7.5 deg, Rf <= 44, stretch grows; spine free-free 0.2 Hz', farm='cone', rim_limit=7.5, basis=FF),
        dict(name='K2', what='K1 with spine beam cantilever 0.1 Hz (T05 practical basis)', farm='cone', rim_limit=7.5, basis=P),
        dict(name='K3', what='K1 with spine beam cantilever 0.2 Hz (Rev 4 / T05 gate basis)', farm='cone', rim_limit=7.5, basis=CA2),
        dict(name='S1', what='aft stand-off +100 m, cone farm rim 7.5, spine practical', farm='cone', rim_limit=7.5, basis=P, dx=100.0),
        dict(name='S2', what='aft stand-off +200 m, cone farm rim 7.5, spine practical', farm='cone', rim_limit=7.5, basis=P, dx=200.0),
        dict(name='S3', what='aft stand-off +200 m, cone farm rim 7.5, spine cantilever 0.2 Hz', farm='cone', rim_limit=7.5, basis=CA2, dx=200.0),
        dict(name='T15', what='A1 at 15 deg, shield moved 3.5 m forward clear of C1 (rim limit from the leak), cone farm, spine practical',
             farm='cone', rim_limit=None, tilt=15.0, dz=3.5, basis=P),
        dict(name='T15-S2', what='T15 with aft stand-off +200 m', farm='cone', rim_limit=None, tilt=15.0, dz=3.5, basis=P, dx=200.0),
        dict(name='N-V4', what='narrowest: farm kept at V4 r 34.5 (long farm), spine practical', farm='fixed', farm_r=34.5, basis=P),
        # Task D: nozzle performance on the converged cases (eta_T before the A1 factor)
        dict(name='D-G0-0.80', what='G0 at the G1-regularised eta_T 0.80', farm='wide', basis=FF, eta_T=0.80),
        dict(name='D-G0-0.72', what='G0 at eta_T 0.72', farm='wide', basis=FF, eta_T=0.72),
        dict(name='D-noA1-0.80', what='G0-noA1 at eta_T 0.80', farm='wide', basis=FF, a1=False, eta_T=0.80),
        dict(name='D-noA1-0.72', what='G0-noA1 at eta_T 0.72', farm='wide', basis=FF, a1=False, eta_T=0.72),
        dict(name='D-noA1-0.67', what='G0-noA1 at the fine-grid eta_T 0.67', farm='wide', basis=FF, a1=False, eta_T=0.67),
    ]
    for v in V:
        if v.get('rim_limit', 0) is None:
            v['rim_limit'] = a1(v['tilt'])['rim_limit_deg']
    return V


def main(names):
    t0 = time.time()
    ov = G.v4_overrides(); R4 = G.solve_full(ov); d0 = SP.t05()
    ref = sum(q['stored_J'] for q in G.LG.coils_v4(R4)['coils'])
    try:
        old = {r['name']: r for r in g2.read('matrix.json')['rows']}
    except FileNotFoundError:
        old = {}
    Vs = [v for v in variants() if not names or v['name'] in names]
    for V in Vs:
        r = run(V, ov, R4, d0, ref)
        old[V['name']] = r
        rp = r.get('report', {})
        print(f"{V['name']:8s} {r['status']:38s} it {r['iterations']:2d} dep {r['departure_trajectory_t'][-1]:9.0f} t rim "
              f"{rp.get('1_shield', {}).get('rim_deg', float('nan')):.2f} farm {rp.get('5_structure', {}).get('farm_radius_m', float('nan')):.1f} m x "
              f"{rp.get('5_structure', {}).get('length_m', float('nan')):.0f} m rate {rp.get('3_rate_Hz') or float('nan'):.0f} Hz fFE "
              f"{rp.get('5_structure', {}).get('f1_FE_estimate_Hz', float('nan')):.3f} [{time.time() - t0:.0f} s]", flush=True)
    order = [v['name'] for v in variants()] + [k for k in old if k not in [v['name'] for v in variants()]]
    g2.write('matrix.json', {'study': 'Gate 2 Task A: shield-cone feasibility matrix (T00)', 'status': 'MODEL, research only, NON-CANON',
                             'method': __doc__.split('\n\n', 1)[1], 'k_FE': K_FE, 'dust_r_m': DUST_R,
                             'rows': [old[k] for k in order if k in old]})


if __name__ == '__main__':
    main(sys.argv[1:])
