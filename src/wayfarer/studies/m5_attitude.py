"""M5 slice 2: the comms / attitude / RCS CAD readback that S&E 63_COMMS_ATTITUDE_STUDY asks for ("Ask Claude for per-axis mass/inertia
tensor, torque vectors, jet plumes, shadow margins, LOS plots and power constraints"). NONCANON; nothing in the vehicle changes.

Function: give the owner's screen measured inputs from the built model in place of its HYPOTHESIS values (inertia 3e9 kg m2, 35 m arm,
4 effective jets, 2.29 deg shadow). Fixed: the built geometry (saved COAST vehicle), the S02 nozzles and antennas (exterior_hardware.py),
the 1,100 t protected-burnout mass budget items (S&E 02, PROVISIONAL), the ring residual momentum (08). Unknown (OPEN, never chosen):
physics.inertia (OPEN: this is a distribution screen, not a mass model), propellant load and placement (BODY-Q1/Q2), RCS thrust, Isp and
technology (S02-Q3), slew and flip requirement (S02-Q2), power and thermal budgets for an arcjet. Design freedom (PROTOTYPE, this file):
how each mass item spreads over its built meshes (area for shells and structure, volume for water and zones), the jet-selection rule.

    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/m5_attitude.py -- --masses   # mass-region dump (runs/m5_mass_regions.json)
    python3 src/wayfarer/studies/m5_attitude.py --out runs/<stamp>-m5-attitude                         # tensor, jets, modes, shadow, LOS maps, report json
"""
from pathlib import Path
import argparse
import itertools
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/studies'), str(ROOT/'src/wayfarer/shots')]

DUMP = ROOT/'runs/m5_mass_regions.json'
OUT_JSON = ROOT/'references/m5_attitude.json'
G0 = 9.80665
# S&E 63 (read 2026-10-18): its screen values, for comparison only.
S63 = dict(I_pitch_yaw=3.0e9, torque_N_m=14000.0, arm_m=35.0, jets=4, flip_min=27.35, isp_cold_s=200.0, isp_arcjet_s=1000.0, arcjet_eff=0.5,
           shadow_half_angle_deg=2.29, shadow_margin_m=8.0, lever_m=200.0)
ISP_S02 = 800.0
F_JET = 100.0   # S02 PROTOTYPE nozzle force (S02-Q3 OPEN)


# ---------------------------------------------------------------- mass regions (which built meshes carry which mass-budget item)

def mass_item(it):
    """(mass-budget item id, weighting) for a gathered shot item, or None when it carries no budget mass (envelopes, display, scale)."""
    g = it['group'].split('/')[0]; k = it['kind']; n = it['name']
    if k in ('scale_reference', 'hull_envelope', 'plasma', 'magnetic_field', 'optical_beam', 'shortfall_scale', 'service_lane', 'spine_tunnel',
             'insulation_envelope', 'he3_cryostat', 'd2_cryostat', 'h2_tank', 'refrigeration_frame', 'transfer_pump_frame', 'vent_frame',
             'transfer_manifold', 'tank_support') or n.startswith(('Engineering_Envelope', 'Tank_Volume')):
        return None
    if g == '':   # BODY-C study zones that stand for budget items placed there by 13_MASS_POSITIONS (inertia_items spans)
        return {'service_workshop': ('workshop_spares_cargo', 'volume'), 'equipment_envelope': ('power_computers_steering_comms', 'volume')}.get(k)
    if g == 'Assembly_HABITAT':
        if k == 'ring_fill':
            return 'water_radiation_shielding:rot', 'volume'
        if k.startswith('sector_interior') or k == 'crew_vestibule':
            return 'life_support+food', 'area'
        if k == 'sector_pressure':
            return 'habitat_pressure_structure', 'area'
        return 'main_structure:rot', 'area'
    if g == 'Assembly_ROTOR_INTERFACE':
        return 'main_structure:rot', 'area'
    if g == 'Assembly_FORWARD_SHIELD':
        return ('power_computers_steering_comms', 'area') if k in ('rcs_thruster', 'nav_light') else ('forward_impact_shielding', 'area')
    if g == 'Assembly_EYE':
        return 'eye_sensors', 'area'
    if g == 'Assembly_STRUCTURE':
        return ('power_computers_steering_comms', 'area') if k == 'generator_proxy' else ('main_structure+margin', 'area')
    if g in ('Assembly_HULL', 'Assembly_CREW_TRANSFER', 'Assembly_STORAGE'):
        return 'main_structure+margin', 'area'
    if g == 'Assembly_SERVICE':
        if k in ('crew_refuge', 'refuge_wall'):
            return 'water_radiation_shielding:refuge', 'volume'
        if k.startswith('storeroom') or k == 'survival_envelope':
            return 'workshop_spares_cargo', 'volume'
        if k in ('comms_antenna', 'exterior_hardware'):
            return 'power_computers_steering_comms', 'area'
        return 'main_structure+margin', 'area'
    if g in ('Assembly_PROPULSION', 'Assembly_SHIELDING'):
        return 'drive_package', 'area'
    if g == 'Assembly_THERMAL':
        return 'radiators_thermal', 'area'
    if g == 'Assembly_POWER_STORAGE':
        return 'power_computers_steering_comms', 'volume'
    if g == 'Assembly_DRONES':
        return 'workshop_spares_cargo', 'area'
    return None


def budget(s):
    """Mass per region id from physics.mass_budget (kg), with the rotating / refuge allowances split out as the budget states them."""
    m = {i['id']: i for i in s['physics']['mass_budget']['items']}
    rot_struct = m['main_structure'].get('rotating_allowance_kg', 0.0); water = m['water_radiation_shielding']
    return {'main_structure+margin': m['main_structure']['mass_kg']-rot_struct+m['design_margin']['mass_kg'], 'main_structure:rot': rot_struct,
            'forward_impact_shielding': m['forward_impact_shielding']['mass_kg'], 'habitat_pressure_structure': m['habitat_pressure_structure']['mass_kg'],
            'eye_sensors': m['eye_sensors']['mass_kg'], 'life_support+food': m['life_support_garden_medical']['mass_kg']+m['food_consumables']['mass_kg'],
            'water_radiation_shielding:rot': water['rotating_allowance_kg'], 'water_radiation_shielding:refuge': water['refuge_allowance_kg'],
            'workshop_spares_cargo': m['workshop_spares_cargo']['mass_kg'], 'drive_package': m['drive_package']['mass_kg'],
            'radiators_thermal': m['radiators_thermal']['mass_kg'], 'power_computers_steering_comms': m['power_computers_steering_comms']['mass_kg']}


ROTATING = ('main_structure:rot', 'habitat_pressure_structure', 'life_support+food', 'water_radiation_shielding:rot')


# ---------------------------------------------------------------- Blender: per-object weight, first and second moments

def object_moments(it, mode):
    """(weight, first moment, second moment 3x3) of one gathered item in world space: area (triangles) or volume (signed tetrahedra to the
    origin; falls back to area for an open mesh); curves as bevelled polylines (length x circumference)."""
    ob = it['obj']; W = it['matrix']
    if ob.type == 'MESH':
        vs = [W@v.co for v in ob.data.vertices]; tris = []
        for p in ob.data.polygons:
            ids = list(p.vertices)
            tris += [(ids[0], ids[i], ids[i+1]) for i in range(1, len(ids)-1)]
        if not tris:
            return None
        def acc(kind):
            w = 0.0; f = [0.0]*3; S = [[0.0]*3 for _ in range(3)]
            for a, b, c in tris:
                A, B, C = vs[a], vs[b], vs[c]
                if kind == 'volume':
                    q = A.dot(B.cross(C))/6.0; pts = (A, B, C); n = 20.0; T = A+B+C; cen = T/4
                else:
                    q = (B-A).cross(C-A).length/2; pts = (A, B, C); n = 12.0; T = A+B+C; cen = T/3
                w += q
                for i in range(3):
                    f[i] += q*cen[i]
                    for j in range(3):
                        S[i][j] += q/n*(sum(P[i]*P[j] for P in pts)+T[i]*T[j])
            return w, f, S
        if mode == 'volume':
            r = acc('volume')
            if abs(r[0]) > 1e-6:
                return r if r[0] > 0 else (-r[0], [-v for v in r[1]], [[-v for v in row] for row in r[2]])
        return acc('area')
    if ob.type == 'CURVE':
        from mathutils import Vector
        rad = max(ob.data.bevel_depth, 0.02); w = 0.0; f = [0.0]*3; S = [[0.0]*3 for _ in range(3)]
        for sp in ob.data.splines:
            pts = [W@Vector(p.co[:3]) for p in sp.points]+[W@p.co for p in sp.bezier_points]
            for a, b in zip(pts, pts[1:]):
                q = (b-a).length*2*math.pi*rad; w += q
                for i in range(3):
                    f[i] += q*(a[i]+b[i])/2
                    for j in range(3):
                        S[i][j] += q*((a[i]*a[j]+b[i]*b[j])/3+(a[i]*b[j]+b[i]*a[j])/6)
        return (w, f, S) if w > 0 else None
    return None


def dump_masses():
    import bpy
    import shot_tools
    bpy.ops.wm.read_factory_settings(use_empty=True)
    regions = {}; count = {}
    for src in ({'asset': 'WF_WAYFARER_001.blend', 'collection': 'WF_WAYFARER_001', 'group': 'assembly'},
                {'asset': 'studies/WF_STUDY_BODY_C.blend', 'collection': 'WF_STUDY_BODY_C', 'group': 'fixed'}):
        for it in shot_tools.gather(shot_tools.link_source(ROOT, src), src):
            if it['group'] == '' or src['group'] == 'fixed':
                it = dict(it, group='')
            mi = mass_item(it)
            if mi is None:
                continue
            r = object_moments(it, mi[1])
            if r is None or r[0] <= 0:
                continue
            e = regions.setdefault(mi[0], dict(w=0.0, f=[0.0]*3, S=[[0.0]*3 for _ in range(3)], objects=0))
            e['w'] += r[0]; e['objects'] += 1
            for i in range(3):
                e['f'][i] += r[1][i]
                for j in range(3):
                    e['S'][i][j] += r[2][i][j]
    # propellant regions: the BODY-C vessels by species (volume), for the housed-fuel case
    for src in ({'asset': 'studies/WF_STUDY_BODY_C.blend', 'collection': 'WF_STUDY_BODY_C', 'group': 'fixed'},):
        for it in shot_tools.gather(bpy.data.collections[src['collection']], src):
            if it['kind'] in ('he3_cryostat', 'd2_cryostat'):
                r = object_moments(it, 'volume'); key = 'prop:'+it['kind']
                e = regions.setdefault(key, dict(w=0.0, f=[0.0]*3, S=[[0.0]*3 for _ in range(3)], objects=0))
                e['w'] += r[0]; e['objects'] += 1
                for i in range(3):
                    e['f'][i] += r[1][i]
                    for j in range(3):
                        e['S'][i][j] += r[2][i][j]
    DUMP.parent.mkdir(exist_ok=True); DUMP.write_text(json.dumps(regions))
    print('WF_M5_MASS', {k: (v['objects'], round(v['w'], 1)) for k, v in regions.items()})


# ---------------------------------------------------------------- pure: tensor

def tensor(regions, masses):
    """Mass, centre of mass and the inertia tensor about it (kg m2) for {region: mass_kg}, each region's mass spread like its weight."""
    M = 0.0; f = [0.0]*3; S = [[0.0]*3 for _ in range(3)]
    for k, m in masses.items():
        r = regions[k]; s = m/r['w']; M += m
        for i in range(3):
            f[i] += s*r['f'][i]
            for j in range(3):
                S[i][j] += s*r['S'][i][j]
    c = [v/M for v in f]
    Sc = [[S[i][j]-M*c[i]*c[j] for j in range(3)] for i in range(3)]
    tr = Sc[0][0]+Sc[1][1]+Sc[2][2]
    I = [[(tr if i == j else 0.0)-Sc[i][j] for j in range(3)] for i in range(3)]
    return M, c, I


def eig_sym(I):
    """Principal moments of a symmetric 3x3 (Jacobi)."""
    A = [row[:] for row in I]; V = [[float(i == j) for j in range(3)] for i in range(3)]
    for _ in range(50):
        p, q = max(((0, 1), (0, 2), (1, 2)), key=lambda t: abs(A[t[0]][t[1]]))
        if abs(A[p][q]) < 1e-9*max(abs(A[i][i]) for i in range(3)):
            break
        th = 0.5*math.atan2(2*A[p][q], A[q][q]-A[p][p]); c, s = math.cos(th), math.sin(th)
        for k in range(3):
            akp, akq = A[k][p], A[k][q]; A[k][p], A[k][q] = c*akp-s*akq, s*akp+c*akq
        for k in range(3):
            apk, aqk = A[p][k], A[q][k]; A[p][k], A[q][k] = c*apk-s*aqk, s*apk+c*aqk
        for k in range(3):
            vkp, vkq = V[k][p], V[k][q]; V[k][p], V[k][q] = c*vkp-s*vkq, s*vkp+c*vkq
    return [A[i][i] for i in range(3)], [[V[k][i] for k in range(3)] for i in range(3)]


def mass_cases(s, regions):
    b = budget(s); tagged = dict(b)
    he3 = 164.8e3; d2_housed = 452.0*175.2   # BODY-C housed (m5_body_c.json): He-3 ideal minimum in full, D2 to the one module's net 452 m3
    out = {}
    for name, extra in (('burnout_1100t', {}), ('burnout_plus_housed_fusion_fuel_C', {'prop:he3_cryostat': he3, 'prop:d2_cryostat': d2_housed})):
        masses = dict(tagged, **extra)
        M, c, I = tensor(regions, masses); ev, vec = eig_sym(I)
        stat = {k: v for k, v in masses.items() if k not in ROTATING}
        Ms, cs, Is = tensor(regions, stat)
        out[name] = dict(mass_t=round(M/1e3, 1), com_m=[round(v, 2) for v in c], I_kg_m2=[[float(f'{v:.4e}') for v in row] for row in I],
                         principal_kg_m2=[float(f'{v:.4e}') for v in sorted(ev)], products_over_transverse=round(max(abs(I[0][1]), abs(I[0][2]), abs(I[1][2]))/I[1][1], 5),
                         roll_stationary_only_kg_m2=float(f'{Is[0][0]:.4e}'), stationary_mass_t=round(Ms/1e3, 1),
                         note='roll: rings on bearings do not follow a roll torque on the stationary body, so the RCS sees the stationary roll inertia'
                              if name.startswith('burnout_1100') else 'He-3 164.8 t + D2 79.2 t in the BODY-C vessels (housed part only)')
    return out


# ---------------------------------------------------------------- pure: jets, torques and modes

def jets(s):
    import exterior_hardware as eh
    out = []
    for p in eh.rcs_aft(s)+eh.rcs_rim(s):
        if 'jet' in p:
            out.append(dict(name=p['name'], at=p['exit'], exhaust=p['jet'], force=tuple(-F_JET*v for v in p['jet'])))
    return out


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def torque_table(s, cm):
    rows = []
    for j in jets(s):
        r = tuple(j['at'][i]-cm[i] for i in range(3)); t = cross(r, j['force'])
        rows.append(dict(j, r=r, torque=t))
    return rows


def lp_max(c, A, n, big=1e7):
    """max c.u subject to A u = 0 and 0 <= u <= 1 (dense Big-M simplex, Bland's rule). Variables: u (n), slacks s (u + s = 1), artificials
    for the A rows (start basic at 0, penalised). Returns u."""
    m1 = len(A); rows = []; rhs = []
    for i in range(m1):
        rows.append([float(v) for v in A[i]]+[0.0]*n+[1.0 if k == i else 0.0 for k in range(m1)]); rhs.append(0.0)
    for j in range(n):
        rows.append([1.0 if k == j else 0.0 for k in range(n)]+[1.0 if k == j else 0.0 for k in range(n)]+[0.0]*m1); rhs.append(1.0)
    cost = [float(v) for v in c]+[0.0]*n+[-big]*m1; N = 2*n+m1
    basis = [2*n+i for i in range(m1)]+[n+j for j in range(n)]
    for _ in range(2000):
        cb = [cost[b] for b in basis]
        red = [cost[k]-sum(cb[i]*rows[i][k] for i in range(len(rows))) for k in range(N)]
        enter = next((k for k in range(N) if red[k] > 1e-9 and k not in basis), None)
        if enter is None:
            break
        ratios = [(rhs[i]/rows[i][enter], basis[i], i) for i in range(len(rows)) if rows[i][enter] > 1e-12]
        if not ratios:
            raise ValueError('unbounded')
        _, _, r = min(ratios)
        pv = rows[r][enter]; rows[r] = [v/pv for v in rows[r]]; rhs[r] /= pv
        for i in range(len(rows)):
            if i != r and abs(rows[i][enter]) > 1e-15:
                f = rows[i][enter]; rows[i] = [a-f*b for a, b in zip(rows[i], rows[r])]; rhs[i] -= f*rhs[r]
        basis[r] = enter
    u = [0.0]*n
    for i, b in enumerate(basis):
        if b < n:
            u[b] = rhs[i]
    return u


def throttled_couple(rows, axis, sign):
    """Pulse-width-modulated jets (duty 0..1 each): the largest pure torque about one axis with zero lateral force and zero cross-axis
    torque; the axial (forward) force is left free and reported, since every S02 jet is canted aft."""
    others = [i for i in range(3) if i != axis]
    A = [[r['force'][1] for r in rows], [r['force'][2] for r in rows]]+[[r['torque'][i] for r in rows] for i in others]
    u = lp_max([sign*r['torque'][axis] for r in rows], A, len(rows))
    T = [sum(u[k]*rows[k]['torque'][i] for k in range(len(rows))) for i in range(3)]; Fv = [sum(u[k]*rows[k]['force'][i] for k in range(len(rows))) for i in range(3)]
    used = [(rows[k]['name'], round(u[k], 3)) for k in range(len(rows)) if u[k] > 1e-4]
    return dict(torque_N_m=round(sign*T[axis]), duty=dict(used), n=len(used), sum_duty=round(sum(u), 2), axial_force_N=round(Fv[0], 1),
                lateral_force_N=round(math.hypot(Fv[1], Fv[2]), 2), cross_torque_N_m=round(math.hypot(*[T[i] for i in others]), 1))


AXES = {'roll+': (0, 1), 'roll-': (0, -1), 'pitch+': (1, 1), 'pitch-': (1, -1), 'yaw+': (2, 1), 'yaw-': (2, -1)}


def best_couple(rows, axis, sign, force_tol=0.15, cross_tol=0.10, axial_free=False):
    """On/off jet set giving the largest torque about one body axis (X roll, Y pitch, Z yaw) with the net force under force_tol x one jet's
    force (lateral only when axial_free: every S02 jet is canted aft, so no set cancels the forward force) and the cross-axis torque under
    cross_tol of the axis torque; brute force over the jets that help that axis."""
    cand = [r for r in rows if sign*r['torque'][axis] > 0.05*F_JET]
    cand = sorted(cand, key=lambda r: -sign*r['torque'][axis])[:14]
    best = None
    for n in range(1, len(cand)+1):
        for combo in itertools.combinations(cand, n):
            T = [sum(r['torque'][i] for r in combo) for i in range(3)]; Fv = [sum(r['force'][i] for r in combo) for i in range(3)]
            ax = sign*T[axis]; off = math.hypot(*[T[i] for i in range(3) if i != axis])
            fres = math.hypot(Fv[1], Fv[2]) if axial_free else math.hypot(*Fv)
            if fres <= force_tol*F_JET and off <= cross_tol*ax and (best is None or ax > best['torque_N_m']):
                best = dict(torque_N_m=round(ax), jets=[r['name'] for r in combo], n=len(combo), net_force_N=round(math.hypot(*Fv), 1),
                            axial_force_N=round(Fv[0], 1), lateral_force_N=round(math.hypot(Fv[1], Fv[2]), 1), cross_torque_N_m=round(off))
    return best


def modes(s, cases):
    """Per axis: best pure couple, ideal bang-bang 180 deg time and propellant per Isp, arcjet power and waste heat; the 63 operating modes."""
    c = cases['burnout_1100t']; I = c['I_kg_m2']; rows = torque_table(s, c['com_m']); out = {}
    strict = {name: best_couple(rows, ax, sg) is not None for name, (ax, sg) in AXES.items()}
    for name, (ax, sg) in AXES.items():
        b = throttled_couple(rows, ax, sg); onoff = best_couple(rows, ax, sg, axial_free=True)
        if b['torque_N_m'] <= 0:
            out[name] = dict(couple=None, force_free_couple=strict[name], note='no pure couple from the S02 jets'); continue
        Iax = c['roll_stationary_only_kg_m2'] if ax == 0 else I[ax][ax]
        T = math.sqrt(4*math.pi*Iax/b['torque_N_m']); J = b['sum_duty']*F_JET*T
        prop = {f'isp_{int(i)}_kg': round(J/(i*G0), 1) for i in (S63['isp_cold_s'], ISP_S02, S63['isp_arcjet_s'])}
        p_jet = F_JET*S63['isp_arcjet_s']*G0/2/S63['arcjet_eff']
        out[name] = dict(couple=b, on_off_couple=onoff, force_free_couple=strict[name], I_axis_kg_m2=float(f'{Iax:.4e}'), flip_180_min=round(T/60, 1), propellant_per_flip=prop,
                         arcjet_power_MW=round(b['sum_duty']*p_jet/1e6, 2), arcjet_waste_heat_MW=round(b['sum_duty']*p_jet*(1-S63['arcjet_eff'])/1e6, 2),
                         forward_dv_per_flip_m_s=round(b['axial_force_N']*T/(c['mass_t']*1e3), 4),
                         alpha_deg_s2=float(f'{math.degrees(b["torque_N_m"]/Iax):.3e}'))
    H = s['physics']['rotor_dynamics']['allowed_residual_momentum_N_m_s']; pitch = out.get('pitch+') or {}
    wmax = math.pi/(pitch['flip_180_min']*60)*2 if pitch.get('flip_180_min') else 0.0
    return dict(axes=out, gyroscopic=dict(ring_residual_H_N_m_s=H, peak_slew_rate_deg_s=round(math.degrees(wmax), 4),
                                         gyro_torque_N_m=round(H*wmax, 1), note='omega x H_residual during a bang-bang flip; compare the couple'),
                operating_modes=[dict(mode='1 micro-slew + precision hold', rcs='minimum-impulse pulses of one couple; hold accuracy OPEN (S02-Q2)'),
                                 dict(mode='2 low-hazard maintenance orientation', rcs='slow slews at a fraction of the couple; only below the dust-speed limit'),
                                 dict(mode='3 high-speed forward-only protected flight', rcs='hold inside the shield-shadow tolerance below; NO 180 deg flip (63 HOLD)')])


# ---------------------------------------------------------------- pure: shield-shadow tolerance from the built parts

def shadow(s, fingerprint, n_phi=72, half=None):
    """For a velocity vector tilted by theta from +X toward azimuth phi, every built corner aft of the shield must stay within the shield
    disc's shadow cylinder along v (radius shield_r - margin). theta_max(phi) and the binding part per phi. Bounding-box corners, so the
    tolerance is conservative for round parts. Rings sweep: their corners stand in for the swept rim (axisymmetric)."""
    import forward_shield as fs
    import habitat_ring
    R = fs.stations(s)['shield_r']; xs = fs.stations(s)['rim'][0]; pts = []; r_ring = habitat_ring.outer(s)
    for f, v in fingerprint.items():
        if f.startswith('components/') or 'objects' not in v or f.endswith(('WF_FORWARD_SHIELD.blend', 'WF_EYE.blend')):
            continue                                           # the shield and its EYE cast the shadow
        swept = f.endswith(('WF_HABITAT.blend', 'WF_ROTOR_INTERFACE.blend'))   # rotating: the full swept circle
        for n, o in v['objects'].items():
            if 'min' not in o or o.get('kind') in ('scale_reference', 'debug_magnetics', 'debug_optics', 'debug_separatrix', 'magnetic_field', 'plasma',
                                                   'optical_beam', 'hull_envelope', 'sim_proxy') or o['max'][0] > xs-0.5:
                continue
            lo, hi = o['min'], o['max']
            if swept or (lo[1] < 0 < hi[1] and lo[2] < 0 < hi[2]):     # a hoop / disc straddling the axis, or a rotating part's sweep: a circle
                rr = max(abs(lo[1]), hi[1], abs(lo[2]), hi[2])
                if swept:
                    rr = min(r_ring, max(math.hypot(y, z) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])))
                for x in (lo[0], hi[0]):
                    for k in range(24):
                        a = 2*math.pi*k/24; pts.append(((x, rr*math.cos(a), rr*math.sin(a)), n))
            else:
                for c in itertools.product(*zip(lo, hi)):
                    pts.append((c, n))
    import exterior_hardware as eh
    o = eh.obstacles(s); d = o['blade']        # the blade sheets are component instances (no fingerprint box): add them analytically
    for j, a in enumerate(o['blades']):
        for x in (d['aft_x_m'], d['front_x_m']):
            for r in (d['root_radius_m'], d['outer_radius_m']):
                pts.append(((x, r*math.cos(a), r*math.sin(a)), f'Radiator blade {j+1} ({math.degrees(a):.0f} deg)'))
    out = []
    for k in range(n_phi):
        phi = 2*math.pi*k/n_phi; lo, hi = 0.0, math.radians(30)
        def ok(th):
            v = (math.cos(th), math.sin(th)*math.cos(phi), math.sin(th)*math.sin(phi))
            worst = None
            for (p, n) in pts:
                d = (p[0]-xs)*v[0]+p[1]*v[1]+p[2]*v[2]                        # along v from the shield plane centre
                perp = math.sqrt(max(0.0, (p[0]-xs)**2+p[1]**2+p[2]**2-d*d))
                if d < 0 and perp > R:
                    return False, n
            return True, None
        for _ in range(30):
            mid = (lo+hi)/2
            if ok(mid)[0]:
                lo = mid
            else:
                hi = mid
        out.append(dict(phi_deg=round(math.degrees(phi), 1), theta_max_deg=round(math.degrees(lo), 3), binding=ok(hi)[1]))
    worst = min(out, key=lambda r: r['theta_max_deg'])
    return dict(shield_r_m=R, shield_x_m=xs, per_azimuth=out, minimum=worst,
                note='geometric only: the velocity-vector misalignment at which a built corner leaves the shield shadow; margin for dust, '
                     'plasma and uncertainty not included (63: actual safe tolerance < geometric max)')


# ---------------------------------------------------------------- pure: LOS sky maps (PIL)

LOS_COLOR = {None: (40, 170, 90), 'blade': (225, 85, 85), 'ring': (90, 160, 210), 'shield': (90, 110, 200), 'hull': (150, 150, 150),
             'plume': (240, 170, 60)}


def los_maps(s, out, step=3.0, plume_deg=15.0):
    """Per antenna gimbal: an equirectangular map of the sky (longitude about +X from +Y, latitude from the X axis), first obstacle per
    direction, in COAST and with the 15 deg plume. Returns clear fractions; writes PNGs."""
    import exterior_hardware as eh
    from PIL import Image, ImageDraw
    o = eh.obstacles(s); ants = {}
    for p in eh.comms(s):
        ants.setdefault(p['antenna'], p['gimbal'])
    nx, ny = int(360/step), int(180/step); res = {}
    for name, c in ants.items():
        for state, plume in (('coast', None), ('burn15', math.radians(plume_deg))):
            im = Image.new('RGB', (nx, ny)); px = im.load(); clear = 0.0; wsum = 0.0
            for j in range(ny):
                pol = math.radians((j+.5)*step)            # angle from -X (aft boresight) 0 .. 180
                for i in range(nx):
                    az = math.radians((i+.5)*step)
                    r = (-math.cos(pol), math.sin(pol)*math.cos(az), math.sin(pol)*math.sin(az))
                    h = eh.ray_hit(o, c, r, plume=plume) if plume is None or r[0] < 0.2 else eh.ray_hit(o, c, r)
                    px[i, j] = LOS_COLOR.get(h, (200, 200, 200)); w = math.sin(pol); wsum += w; clear += w*(h is None)
            S = 6; big = im.resize((nx*S, ny*S), Image.NEAREST); canvas = Image.new('RGB', (nx*S, ny*S+56), (16, 18, 22))
            canvas.paste(big, (0, 28)); d = ImageDraw.Draw(canvas)
            for deg in (30, 60, 90, 120, 150):
                y = 28+deg/step*S; d.line((0, y, nx*S, y), fill=(20, 20, 20)); d.text((4, y-12), f'{deg} deg', fill=(0, 0, 0))
            for deg in (90, 180, 270):
                x = deg/step*S; d.line((x, 28, x, 28+ny*S), fill=(20, 20, 20))
            d.text((6, 8), f'{name} gimbal, {state.upper()}: sky seen from the gimbal; rows = angle from the aft axis (Earth in outbound coast) 0 top .. 180 bottom; '
                           f'columns = azimuth from +Y (0) through +Z (90). Clear (sin-weighted) {clear/wsum:.0%}', fill=(230, 230, 230))
            d.text((6, ny*S+36), 'green clear | red radiator blade | blue ring / shield | grey hull | orange main plume (15 deg study cone, burn only)',
                   fill=(200, 200, 200))
            canvas.save(out/f'los_{name}_{state}.png'); res[f'{name}_{state}'] = round(clear/wsum, 3)
    return res


def shadow_plot(sh, path):
    """Polar plot of the geometric shield-shadow tolerance theta_max(phi), with the S&E 63 2.29 deg screen."""
    from PIL import Image, ImageDraw
    W = 720; c = W//2; k = 70.0; im = Image.new('RGB', (W, W+60), (16, 18, 22)); d = ImageDraw.Draw(im)
    for deg in (1, 2, 3, 4):
        d.ellipse((c-deg*k, c-deg*k, c+deg*k, c+deg*k), outline=(70, 70, 70)); d.text((c+deg*k+3, c-12), f'{deg} deg', fill=(150, 150, 150))
    r63 = S63['shadow_half_angle_deg']*k; d.ellipse((c-r63, c-r63, c+r63, c+r63), outline=(240, 170, 60))
    pts = [(c+r['theta_max_deg']*k*math.cos(math.radians(r['phi_deg'])), c-r['theta_max_deg']*k*math.sin(math.radians(r['phi_deg']))) for r in sh['per_azimuth']]
    d.polygon(pts, outline=(40, 200, 110))
    d.text((10, 10), 'Velocity-vector tilt from +X before a built part leaves the shield shadow (geometric, no margin)', fill=(230, 230, 230))
    d.text((10, 28), 'right = +Y, up = +Z (looking aft from ahead of the ship); green: built model; orange: S&E 63 screen 2.29 deg', fill=(190, 190, 190))
    m = sh['minimum']; d.text((10, W+20), f"minimum {m['theta_max_deg']:.2f} deg toward {m['phi_deg']:.0f} deg, bound by {m['binding']}", fill=(230, 230, 230))
    im.save(path)


def main(out=None):
    from spec import load
    s = load(ROOT)[0]
    regions = json.loads(DUMP.read_text())
    fp_path = sorted(ROOT.glob('runs/*-pipeline/fingerprint.json'))[-1]
    cases = mass_cases(s, regions); md = modes(s, cases)
    sh = shadow(s, json.loads(fp_path.read_text()))
    res = dict(study='M5 slice 2: comms / attitude / RCS CAD readback for S&E 63 (NONCANON; physics.inertia stays OPEN)',
               mass_model='1,100 t burnout budget (02, PROVISIONAL) spread over the built meshes per region; area-weighted shells and structure, '
                          'volume-weighted water, stores and study zones', fingerprint=str(fp_path.relative_to(ROOT)),
               regions={k: dict(objects=v['objects']) for k, v in regions.items()}, budget_kg=budget(s), cases=cases, modes=md, shadow=sh,
               s63=S63, jets=[dict(name=r['name'], at=[round(v, 2) for v in r['at']], force_N=[round(v, 1) for v in r['force']],
                                   torque_N_m=[round(v) for v in r['torque']]) for r in torque_table(s, cases['burnout_1100t']['com_m'])])
    if out is not None:
        out.mkdir(parents=True, exist_ok=True); res['los_clear_fraction_full_sky'] = los_maps(s, out); shadow_plot(sh, out/'shadow_tolerance.png')
        (out/'m5_attitude.json').write_text(json.dumps(res, indent=1)+'\n')
    elif OUT_JSON.exists():
        res['los_clear_fraction_full_sky'] = json.loads(OUT_JSON.read_text()).get('los_clear_fraction_full_sky')
    OUT_JSON.write_text(json.dumps(res, indent=1)+'\n')
    for k, c in cases.items():
        print(k, c['mass_t'], 't com', c['com_m'], 'principal', c['principal_kg_m2'], 'roll stat', c['roll_stationary_only_kg_m2'], 'prod/trans', c['products_over_transverse'])
    for k, v in md['axes'].items():
        print(k, v.get('couple', {}) and (v['couple']['torque_N_m'], v['couple']['n'], v['couple']['sum_duty'], v['couple']['axial_force_N'], v['couple']['lateral_force_N'], v['couple']['cross_torque_N_m']),
              v.get('flip_180_min'), v.get('propellant_per_flip'), v.get('arcjet_power_MW'))
    print('gyro', md['gyroscopic']); print('shadow min', sh['minimum'])
    print('los', res.get('los_clear_fraction_full_sky'))
    return res


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser(); ap.add_argument('--masses', action='store_true'); ap.add_argument('--out', type=Path)
    a = ap.parse_args(argv)
    if a.masses:
        dump_masses()
    else:
        main(None if a.out is None else (a.out if a.out.is_absolute() else ROOT/a.out))
