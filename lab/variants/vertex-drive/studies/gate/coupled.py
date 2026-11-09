"""Feasibility gate Phase 2 (ISS-024): a self-consistent coupled Vertex ship (T00, research only, NON-CANON).

  python3 lab/variants/vertex-drive/studies/gate/coupled.py      # writes results/coupled.json (minutes)

Revision 4 coupled the coil hardware once: it sized the coils on V4, then re-solved FDP-1 with that hardware as payload (68.5-71.9 kt).
Here every added item is re-sized on each new solution until the departure mass stops changing (fixed-point iteration), so the coil
geometry and mass follow the pulse energy and the stand-off, the spine follows the propellant, and the launcher follows the pulse rate:

  closure coils C1, C2      LG.coils_v4(R): stand-off scale and field-limited current from this solve's nozzle field energy; then the
                            Rev 4 bottom-up assembly (winding pack at J_e, TARGET-composite case in its own shadow, LiH neutron screen
                            for the REBCO fluence over this solve's burn time, cryostat, CFC armour, struts), its heat, cooling and
                            cryoplant (injection.coil_hw)
  FDP-1 loop conductor      adapter term (FDP-1 code is protected and books only the virial structure): winding packs of L1-L3 at
                            the same J_e, current from FDP-1's own minor radius at 25 T (labelled; on in the 'full' cases)
  spine                     N9 longerons in the inter-tank gaps (R 31 m), sized for a 0.2 Hz cantilever f1 on a stretch that grows
                            with this solve's propellant at the same section (spine.size_for); booked over the S2 keels
  launcher                  B-ray (B-modified gas capsule on a 12 deg burn ray, 30,000 g), tip at 1.3x the stopping radius at 12 deg
                            scaled with the stand-off, coilgun mass and electric power at this solve's rate (injection.kin)
  axis protection           the Phase 1 concept's hardware (results/concepts.json), booked as payload
  propellant, radiators, drivers, shield, tanks, fusion yield, rate: FDP-1's own sizing on each solve (four-burn engine untouched)

Heat from the coils goes into FDP-1 through plume_to_hardware, warm/electric loads through house_fraction, hardware through the payload
(the adapter used in Rev 4). Pulse rate: FDP-1's own choice, or capped (max_rep_Hz), which forces larger pulses and a longer stand-off.
A case that does not converge in 40 iterations, or whose departure passes 400 kt, is recorded as NON-CONVERGING with its trajectory.
"""
import copy
import math
import time

import gate_common as G
import injection as IN
import spine as SP
from common import C

MAX_IT = 40
TOL_T = 1.0
BLOWUP_T = 400e3           # t
B_SURF = 25.0
WALL_G_V4 = 0.59           # Rev 4 B-modified HDC wall for 0.772 g of fuel


def fdp1_loop_conductor(R, J_e):
    kg = 0.0; rows = []
    for L in R['nozzle']['loops']:
        I = 2 * math.pi * L['minor_radius_m'] * B_SURF / G.MU0
        m = I / J_e * 2 * math.pi * L['r'] * G.LG.a('winding_density')
        rows.append({'loop': L['name'], 'current_MA': I / 1e6, 'radius_m': L['r'], 'winding_t': m / 1e3}); kg += m
    return kg, rows


FARM_R_V4 = 34.5          # existing tank farm radius (FDP-1 shield envelope 'existing_tank_farm')
FARM_X_NEAR = 109.25      # its nearest X (ship frame)


def shield_growth(R, R4, lam, farm):
    """Wide farm: the tank farm radius grows as sqrt(lam) at the same length; the shadow shield must still cover it."""
    if farm != 'wide':
        return {'farm_radius_m': FARM_R_V4, 'added_kg': 0.0}
    Rf = FARM_R_V4 * math.sqrt(max(lam, 1.0))
    d = FARM_X_NEAR - R['layout']['x_burn']
    need = math.degrees(math.atan(Rf / d))
    have = R['shield']['hardware_half_angle_deg']
    m0 = R['mass']['items_kg']['shadow shield']
    k = (math.tan(math.radians(max(need + 0.5, have))) / math.tan(math.radians(have))) ** 2
    return {'farm_radius_m': Rf, 'needed_half_angle_deg': need + 0.5, 'fdp1_half_angle_deg': have, 'shield_area_factor': k,
            'added_kg': m0 * (k - 1), 'shield_radius_m': R['layout']['d_shield'] * math.tan(math.radians(max(need + 0.5, have)))}


def size_spine(d, R_long, bow_kg, basis):
    """Smallest N9 tube radius meeting the f1 basis: ('cantilever', f) is T05's lower bound, ('free_free', f) the upper bound."""
    kind, f_t = basis
    if kind == 'cantilever':
        return SP.size_for(d, 9, R_long, bow_kg, target=f_t)
    lo, hi = 0.02, 2.5
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        SP.GEOMS['_tmp'] = (9, R_long, mid)
        ok = SP.analyse(d, '_tmp', bow_kg)['f1_Hz'] >= f_t
        lo, hi = (lo, mid) if ok else (mid, hi)
    SP.GEOMS['_tmp'] = (9, R_long, hi)
    res = SP.analyse(d, '_tmp', bow_kg)
    del SP.GEOMS['_tmp']
    return hi, res


def spine_mass(R, R4, d0, bow_kg=300e3, farm='wide', basis=('cantilever', 0.2), fixed=None):
    """N9 sized for a 0.2 Hz cantilever f1 (T05 basis). farm 'wide': the drawn bays carry lam x the loading on a ring of longerons
    at 31 sqrt(lam) m (same length); farm 'long': the same section with more full bays (the stretch grows)."""
    lam = R['mass']['items_kg']['propellant (four burns)'] / R4['mass']['items_kg']['propellant (four burns)']
    d = copy.deepcopy(d0)
    st = d['stretch']; bays = st['bay_masses']
    full = max(b['propellant_kg'] for b in bays); tk = max(b['tank_kg'] for b in bays)
    total = lam * sum(b['propellant_kg'] for b in bays)
    x0 = st['x_m'][0]; pitch = st['bay_pitch_m']
    if lam <= 1.0 or farm == 'wide':
        new = [dict(b, propellant_kg=b['propellant_kg'] * lam, tank_kg=b['tank_kg'] * lam) for b in bays]
    else:                                                # same section and bay loading: the drawn bays, then more full bays aft-to-bow
        new = [dict(b) for b in bays]
        extra = total - sum(b['propellant_kg'] for b in bays)
        i = 0
        while extra > 1e-6:
            q = min(full, extra)
            new.append(dict(bays[0], x_m=bays[-1]['x_m'] + pitch * (i + 1), propellant_kg=q, tank_kg=tk * q / full))
            extra -= q; i += 1
    n_new = len(new)
    st['bay_masses'] = new
    st['x_m'] = [x0, st['x_m'][1] + pitch * (n_new - len(bays))]
    a_ratio = C.fdp1.summary(R)['a0_g'] / C.fdp1.summary(R4)['a0_g']
    fwd = sum(b['propellant_kg'] + b['tank_kg'] for b in new) + bow_kg
    for b in d['loads']['root_axial_by_burn']:
        b['ship_kg'] = b['ship_kg'] + (C.fdp1.summary(R)['departure_t'] - C.fdp1.summary(R4)['departure_t']) * 1e3
        b['root_axial_N'] = b['root_axial_N'] * fwd / d0['loads']['root_axial_by_burn'][0]['forward_kg'] * a_ratio
        b['accel_g'] = b['accel_g'] * R['structure']['peak_accel_g'] / R4['structure']['peak_accel_g']
    R_long = 31.0 * math.sqrt(max(lam, 1.0)) if farm == 'wide' else 31.0
    dep = C.fdp1.summary(R)['departure_t'] * 1e3
    for q in d['loads']['root_axial_by_burn']:
        q['ship_kg'] = 3 * dep                     # sizing uses the cantilever bound only; keeps the free-free aft mass positive
    if fixed:                                       # (ring radius, tube radius): analyse a drawn section instead of sizing one
        R_long, r = fixed
    else:
        r, res = size_spine(d, R_long, bow_kg, basis)
    SP.PULSE = R['fusion']['pellet_rate_Hz']
    if fixed:
        SP.GEOMS['_fix'] = (9, R_long, r)
        try:
            res = SP.analyse(d, '_fix', bow_kg)
        finally:
            del SP.GEOMS['_fix']
    for q in d['loads']['root_axial_by_burn']:
        q['ship_kg'] = dep + res['structure_t'] * 1e3
    GEOM = ('_fin', (9, R_long, r))
    SP.GEOMS[GEOM[0]] = GEOM[1]
    try:
        res = SP.analyse(d, GEOM[0], bow_kg)
        sec = SP.section(9, R_long, r)
    finally:
        del SP.GEOMS[GEOM[0]]
    return {'farm': farm, 'basis': list(basis), 'longeron_ring_m': R_long, 'stretch_scale': lam, 'bays': n_new, 'length_m': st['x_m'][1] - st['x_m'][0], 'tube_r_m': r,
            'added_t': res['added_structure_t'], 'structure_t': res['structure_t'], 'f1_cantilever_Hz': res['f_cantilever_Hz'][0],
            'f1_free_free_Hz': res['f1_Hz'], 'buckling_factor_SF2': res['buckling_factor_SF2'], 'J1': res['J1'], 'J3': res['J3'],
            'lateral': res['lateral'], 'local': res['local'], 'EI_N_m2': sec['EI'], 'EA_N': sec['EA'], 'pulse_Hz': SP.PULSE,
            'bow_kg': bow_kg}


def launcher(R, R4):
    s = R['fusion']['xray_standoff_m'] / R4['fusion']['xray_standoff_m']
    tip = 1.3 * 43.5 * s
    fuel = R['fusion']['pellet_fuel_mass_g']
    m_t = (fuel + WALL_G_V4 * (fuel / 0.7721569150877443) ** (2 / 3)) / 1e3 * 1.15
    k = IN.kin(R, tip, 30000.0, m_target_kg=m_t)
    return {'tip_m': tip, 'target_g': m_t * 1e3, **{x: k[x] for x in ('muzzle_m_s', 'accelerator_m', 'launcher_kg', 'electric_W', 'sabot_catcher_W',
                                                                       'tip_xray_J_cm2', 'rate_Hz')}}


def solve(ov, kv, cap):
    o = C.P(ov, **kv)
    if cap:
        o = C.P(o, **{C.MAXREP: cap})
    return C.fdp1.solve('baseline', G.core(o))


NOZ = 'base.overrides.pulsed.nozzle_efficiency.optimistic'


def run(label, ov, R4, d0, cap=None, items=('coils',), J_e=None, axis_kg=0.0, axis_house_W=0.0, noz_factor=1.0):
    """Fixed-point iteration of the coupled ship."""
    J_e = J_e or G.LG.a('J_e_A_m2')
    saved = G.LG.A['J_e_A_m2']
    G.LG.A['J_e_A_m2'] = (J_e, saved[1])
    try:
        R = solve(ov, {}, cap)
        traj = [C.fdp1.summary(R)['departure_t']]
        pay0 = ov['mission']['payload']['reference_t']
        ptw0 = ov['base']['overrides']['continuous']['plume_to_hardware']['value']
        house0 = ov['base']['overrides']['pulsed']['house_fraction']['value']
        status = 'NON-CONVERGING' if MAX_IT > 1 else 'SINGLE PASS (Rev 4 method)'
        last = None
        hist = []
        for it in range(MAX_IT):
            if not R.get('converged'):
                status = 'FDP-1 DID NOT CLOSE'; break
            Pf = R['fusion']['gross_fusion_power_W']; L = R['fusion']['ledger_W']
            plume = (L['plume_to_space'] + L['plume_to_hardware']) / Pf
            add = {}; hot = 0.0; house = 0.0
            if 'coils' in items:
                c = IN.coil_hw(ov, R)
                add['closure coils C1, C2 (winding, case, LiH screen, cryostat, armour, struts, cooling)'] = c['coil_hw_kg']
                hot += c['ch']['hot_W'] + c['ch']['pump_hydraulic_W']; house += c['circ']['warm_added_W']
                last_c = c
            if 'loops' in items:
                kg, rows = fdp1_loop_conductor(R, J_e)
                add['FDP-1 loop conductor (adapter term)'] = kg
            if 'spine' in items:
                farm = 'long' if 'long' in items else 'wide'
                basis = next((b for b in items if isinstance(b, tuple)), ('cantilever', 0.2))
                sp = spine_mass(R, R4, d0, farm=farm, basis=basis)
                add['spine N9 over S2 keels'] = sp['added_t'] * 1e3
                sg = shield_growth(R, R4, sp['stretch_scale'], farm)
                add['shadow shield growth (wide farm)'] = sg['added_kg']
                sp['shield'] = sg
            if 'launcher' in items:
                ln = launcher(R, R4)
                add['launcher B-ray'] = ln['launcher_kg']
                house += ln['electric_W'] + ln['sabot_catcher_W']
            if axis_kg:
                add['axis protection (Phase 1 concept)'] = axis_kg
                house += axis_house_W
            extra = sum(add.values())
            kv = {C.PTW: ptw0 + hot / Pf / plume, C.HOUSE: house0 + house / Pf, 'mission.payload.reference_t': pay0 + extra / 1e3}
            if noz_factor != 1.0:
                kv[NOZ] = ov['base']['overrides']['pulsed']['nozzle_efficiency']['optimistic'] * noz_factor
            Rn = solve(ov, kv, cap)
            s = C.fdp1.summary(Rn) if Rn.get('converged') else {'departure_t': float('nan')}
            traj.append(s['departure_t'])
            hist.append({'departure_t': s['departure_t'], 'rate_Hz': Rn['fusion']['pellet_rate_Hz'] if Rn.get('converged') else None,
                         'stand_off_m': Rn['fusion']['xray_standoff_m'] if Rn.get('converged') else None,
                         'added_t': {k: x / 1e3 for k, x in add.items()}})
            R = Rn
            last = {'added_kg': add, 'kv': kv}
            if not Rn.get('converged'):
                status = 'FDP-1 DID NOT CLOSE'; break
            if s['departure_t'] > BLOWUP_T:
                status = 'NON-CONVERGING (diverges past 400 kt)'; break
            if abs(traj[-1] - traj[-2]) < TOL_T:
                status = 'CONVERGED'; break
        out = {'label': label, 'rate_cap_Hz': cap, 'items': list(items), 'J_e_A_mm2': J_e / 1e6, 'status': status, 'iterations': len(traj) - 1,
               'departure_trajectory_t': traj, 'history': hist}
        if len(traj) >= 3 and all(math.isfinite(x) for x in traj[-3:]):
            d1, d2 = traj[-2] - traj[-3], traj[-1] - traj[-2]
            out['loop_gain'] = d2 / d1 if abs(d1) > 1e-9 else 0.0
        if R.get('converged') and last:
            s = G.LG.summary(R)
            f = R['fusion']
            out['added_kg'] = last['added_kg']
            out['final_set'] = last['kv']
            out['summary'] = s
            out['fusion'] = {'yield_per_pulse_GJ': f['yield_per_pulse_J'] / 1e9, 'pellet_rate_Hz': f['pellet_rate_Hz'], 'fuel_g': f['pellet_fuel_mass_g'],
                             'target_gain': f['target_gain'], 'driver_MJ': f['driver_energy_per_pulse_J'] / 1e6, 'stand_off_m': f['xray_standoff_m'],
                             'thrust_MN': R['structure']['thrust_N'] / 1e6, 'peak_accel_g': R['structure']['peak_accel_g'],
                             'jet_TW': f['jet_power_W'] / 1e12, 'mass_flow_kg_s': f['mass_flow_kg_s']}
            out['heat_rejection'] = {'hot_km2': s['hot_km2'], 'warm_km2': s['warm_km2'], 'radiator_t': s['radiator_t'],
                                     'coil_hot_GW': last_c['ch']['hot_W'] / 1e9 if 'coils' in items else 0.0,
                                     'coil_warm_GW': last_c['circ']['warm_added_W'] / 1e9 if 'coils' in items else 0.0}
            if 'coils' in items:
                cg = G.LG.coils_v4(R)
                out['coils'] = [{k: c[k] for k in ('name', 'radius_m', 'distance_m', 'z_from_burn_m', 'current_A', 'winding_minor_m', 'stored_J')}
                                for c in cg['coils']]
                out['coil_scale_from_V4'] = cg['scale'] / G.LG.coils_v4(R4)['scale']
            if 'spine' in items:
                out['spine'] = sp
            if 'launcher' in items:
                ln = launcher(R, R4); ln['fits_gas_capsule'] = 30000.0 <= 102282.0
                out['launcher'] = ln
            out['propellant_t'] = s['propellant_t']
        return out
    finally:
        G.LG.A['J_e_A_m2'] = saved


def main():
    global MAX_IT
    t0 = time.time()
    ov = G.v4_overrides(); R4 = G.solve_full(ov)
    d0 = SP.t05()
    ax = {}
    try:
        cc = G.read('concepts.json'); ax = cc.get('chosen', {})
    except FileNotFoundError:
        pass
    axis_kg = ax.get('booked_kg', 0.0); axis_W = ax.get('house_W', 0.0); noz = ax.get('nozzle_efficiency_factor', 1.0)
    full = ('coils', 'spine', 'launcher')
    A = ('coils', 'launcher')
    S = lambda kind, f: ('spine', (kind, f))
    cases = [
        # label, rate cap, items, J_e, axis kg, iterations, nozzle factor applies
        ('Rev 4 method: coils only, rate free, one pass', None, ('coils',), None, 0.0, 1, False),
        ('coils only, rate free', None, ('coils',), None, 0.0, MAX_IT, False),
        ('coils + launcher, rate free', None, A, None, 0.0, MAX_IT, False),
        ('coils + launcher + axis A1, rate free', None, A, None, axis_kg, MAX_IT, True),
        ('full: + spine cantilever 0.2 Hz (T05 basis), rate free', None, A + S('cantilever', 0.2), None, axis_kg, MAX_IT, True),
        ('full: + spine cantilever 0.1 Hz, rate free', None, A + S('cantilever', 0.1), None, axis_kg, MAX_IT, True),
        ('full: + spine free-free 0.2 Hz (upper bound), rate free', None, A + S('free_free', 0.2), None, axis_kg, MAX_IT, True),
        ('full: spine free-free 0.2 Hz, cap 250 Hz', 250.0, A + S('free_free', 0.2), None, axis_kg, MAX_IT, True),
        ('full: spine free-free 0.2 Hz, cap 196 Hz', 196.0, A + S('free_free', 0.2), None, axis_kg, MAX_IT, True),
        ('full: spine cantilever 0.2 Hz, long farm (same section)', None, A + S('cantilever', 0.2) + ('long',), None, axis_kg, MAX_IT, True),
        ('full (free-free 0.2 Hz) + FDP-1 loop conductor, rate free', None, A + S('free_free', 0.2) + ('loops',), None, axis_kg, MAX_IT, True),
        ('full (free-free 0.2 Hz) + loop conductor at J_e 300 A/mm2', None, A + S('free_free', 0.2) + ('loops',), 300e6, axis_kg, MAX_IT, True),
    ]
    rows = []
    for lab, cap, items, J, akg, nit, use_noz in cases:
        m0 = MAX_IT; MAX_IT = nit
        r = run(lab, ov, R4, d0, cap, items, J, akg, axis_W if akg else 0.0, noz if use_noz else 1.0)
        MAX_IT = m0
        rows.append(r)
        s = r.get('summary', {})
        print(f"{lab:62s} {r['status']:28s} it {r['iterations']:2d} dep {s.get('departure_t', float('nan')):9.0f} t rate "
              f"{r.get('fusion', {}).get('pellet_rate_Hz', float('nan')):6.1f} Hz traj {[round(x) for x in r['departure_trajectory_t'][:6]]} "
              f"gain {r.get('loop_gain', float('nan')):.3f} [{time.time() - t0:.0f} s]", flush=True)
    out = {'study': 'Feasibility gate Phase 2: self-consistent coupled ship (T00)', 'status': 'MODEL, research only, NON-CANON',
           'v4_reference': G.LG.summary(R4), 'axis_concept_booked': ax, 'cases': rows,
           'method': __doc__.split('\n\n', 1)[1], 'runtime_s': time.time() - t0}
    G.write('coupled.json', out)


if __name__ == '__main__':
    main()
