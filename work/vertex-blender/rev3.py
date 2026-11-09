"""T05 Stage B revision 3 screening: structure and access across the T-B stretch, target survival and snout durability, closure-coil
cooling. Standard library only; run from the project root: python3 work/vertex-blender/rev3.py  -> work/vertex-blender/rev3.json

NON-CANON. Every structural choice here is PROTOTYPE (member layout, design accelerations, joint knock-downs, frame pitch); material
values reuse the FDP-1 structure assumptions (lab/variants/fdp1/config/fdp1.toml [structure]). Masses are lower bounds of a beam
model, not a finite-element result. Nothing here feeds the propulsion calculator."""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import screen  # noqa: E402

G0 = 9.80665
REV2 = json.loads((HERE/'rev2.json').read_text())
CAN = REV2['canon']

# FDP-1 structure assumptions (CFRP/Ti members)
SIG, SF, E, RHO, TR = 6.0e8, 2.0, 1.2e11, 1700.0, 0.05
# PROTOTYPE choices for this screening
DAF = 2.0                    # dynamic amplification on the pulsed thrust (195.7 Hz pulse train through the thrust ring)
A_LAT_G = 0.002              # lateral envelope: 2x the canon 0.1 deg/s slew started in 60 s at the bow (about 0.001 g); 1 deg thrust misalignment gives 4e-4 g
A_LAT_SENS_G = 0.01          # sensitivity case
F_TARGET_HZ = 0.2            # first bending mode target, full tanks: 3x ring spin (4 rpm) and 5x the highest propellant slosh mode
M_BOW_KG = 300e3             # forward shield, Lance, Crown, EYE, hub and keels (Brow 100 t PROVISIONAL + equipment); sensitivity 100-1,000 t
JOINT_KD = 0.8               # splice efficiency on member strength
LACING = 0.30                # diagonals and shear panels as a fraction of keel mass
MIN_T = 0.003                # minimum CFRP gauge
CABIN_PA = 80e3              # canon cabin pressure (data/wayfarer_3d.toml cabin_pressure_kpa)


def tube_for(force_N, length_m, r_fixed=None):
    """Thin tube for an axial (compressive) force: stress or Euler buckling over length_m, whichever governs (FDP-1 rule, SF on both)."""
    P = force_N*SF/JOINT_KD
    if r_fixed:
        t_s = P/(2*math.pi*r_fixed*SIG)
        t_b = P*length_m**2/(math.pi**3*E*r_fixed**3)
        t = max(t_s, t_b, MIN_T); A = 2*math.pi*r_fixed*t
        return {'r_m': r_fixed, 't_m': t, 'area_m2': A, 'governs': 'buckling' if t_b > t_s else 'stress', 'kg_per_m': RHO*A}
    r_b = (P*length_m**2/(math.pi**3*E*TR))**0.25
    A_s = P/SIG; A_b = 2*math.pi*TR*r_b*r_b
    A = max(A_s, A_b); r = max(r_b, math.sqrt(A/(2*math.pi*TR)), 0.05)
    return {'r_m': r, 't_m': TR*r, 'area_m2': A, 'governs': 'buckling' if A_b >= A_s else 'stress', 'kg_per_m': RHO*A}


def stretch_masses(R):
    tb = R['tanks']['options']['T-B']; summ = R['tanks']['summary']
    dens = summ['density_kg_m3']; req = sum(summ['required_m3'].values())
    tank_kg_m3 = summ['tank_mass_kg']/req
    bays = {}
    for v in tb['vessels']:
        xm = round((v['x0']+v['x1'])/2, 2)
        b = bays.setdefault(xm, {'x_m': xm, 'propellant_kg': 0.0, 'tank_kg': 0.0, 'vessels': 0, 'outer_kg': 0.0, 'inner_kg': 0.0})
        mp = v['liquid_m3']*dens[v['species']]; mt = v['liquid_m3']*tank_kg_m3
        b['propellant_kg'] += mp; b['tank_kg'] += mt; b['vessels'] += 1
        b['outer_kg' if v['R'] > 20 else 'inner_kg'] += mp+mt
        b.setdefault('vessel_max_kg', 0.0); b['vessel_max_kg'] = max(b['vessel_max_kg'], mp+mt)
    out = [bays[k] for k in sorted(bays)]
    existing = sum(summ['existing_m3'][k]*dens[k] for k in ('helium_3', 'deuterium'))
    fill = (R['closure']['propellant_t']*1e3-existing)/sum(b['propellant_kg'] for b in out)
    for b in out:                                       # canon farm vessels are filled first; the T-B vessels hold the rest (spare volume)
        b['propellant_kg'] *= fill; b['vessel_max_kg'] = b['vessel_max_kg']*fill+b['tank_kg']/b['vessels']*(1-fill)
    return out, tb


def burn_loads(R, bays, m_bow):
    """Axial force at the stretch root (X 140.75 m) through each burn: N = thrust x m_forward / m_total. T-B tanks drain in proportion
    to the whole propellant load (draining order UNKNOWN)."""
    c = R['closure']; F = c['thrust_MN']*1e6
    prop_TB = sum(b['propellant_kg'] for b in bays); tank_TB = sum(b['tank_kg'] for b in bays)
    p_total = c['propellant_t']*1e3
    rows = []; left = p_total
    for b in c['burns']:
        for when, m_ship in (('start', b['start_t']*1e3), ('end', (b['start_t']-b['propellant_t'])*1e3)):
            if when == 'end':
                left_now = left-b['propellant_t']*1e3
            else:
                left_now = left
            f_left = left_now/p_total
            m_fwd = m_bow+tank_TB+prop_TB*f_left
            rows.append({'burn_start_t': b['start_t'], 'when': when, 'ship_kg': m_ship, 'forward_kg': m_fwd, 'accel_g': F/m_ship/G0,
                         'root_axial_N': F*m_fwd/m_ship})
        left -= b['propellant_t']*1e3
    return F, rows, prop_TB, tank_TB


def lateral(bays, m_bow, x_root, x_bow, a_g):
    a = a_g*G0
    V = (sum(b['propellant_kg']+b['tank_kg'] for b in bays)+m_bow)*a
    M = sum((b['propellant_kg']+b['tank_kg'])*a*(b['x_m']-x_root) for b in bays)+m_bow*a*(x_bow-x_root)
    return V, M


def options(F_root, M_root, L, bays, m_bow, x_root):
    """S1 spine only, S2 canon topology continued (spine + three sector keels at r 5 m + bay frames), S3 outer cage at r 35.5 m."""
    m_tanks_full = sum(b['propellant_kg']+b['tank_kg'] for b in bays)
    m_tanks_dry = sum(b['tank_kg'] for b in bays)
    out = {}
    # --- S1: spine tube only (canon diameter 1.5-2.0 m, r 0.95 m used by the canon spine)
    r = CAN['spine_r_m']
    # bending + axial in one tube: needed wall from stress; global Euler as a cantilever from the root (tip-load idealisation)
    t_sb = SF/JOINT_KD*(F_root/(2*math.pi*r)+M_root/(math.pi*r*r))/SIG
    t_gb = SF*F_root*4*L*L/(math.pi**3*E*r**3)
    t1 = max(t_sb, t_gb, MIN_T); A1 = 2*math.pi*r*t1; I1 = math.pi*r**3*t1
    out['S1_SPINE_ONLY'] = {'members': f'one tube r {r:.2f} m, wall {t1*1e3:.0f} mm', 'governs': 'global buckling' if t_gb >= t_sb else 'stress',
                            'EI_N_m2': E*I1, 'EA_N': E*A1, 'structure_kg': RHO*A1*L*1.1,
                            'canon_rule': 'VIOLATES forward_defense.shield_load_path (hub alone forbidden; three primary sectors required)'}
    # --- S2: spine (min gauge 6 mm, shares load) + three keels r 5 m + bay frames every 30.4 m and intermediate frames
    rk = CAN.get('sector_radius_m', 5.0); frames_per_bay = 4; bay = L/9.0; Lf = bay/frames_per_bay
    # keel force: axial share + bending (three members at 120 deg: I = 1.5 A r^2, max member force M/(1.5 r) x 2/sqrt(3)... use M/(1.5 r) worst)
    Fk = F_root/3+M_root/(1.5*rk)*(2/math.sqrt(3))
    keel = tube_for(Fk, Lf)
    I2 = 1.5*keel['area_m2']*rk**2+math.pi*r**3*0.006
    A2 = 3*keel['area_m2']+2*math.pi*r*0.006
    Pcr2 = math.pi**2*E*I2/(4*L*L)
    # frames: each bay frame carries its bay's tank inertia; radial arms to the outer tanks (R 27.75) cantilever from the keel ring (r 5)
    frame = frame_mass(bays, rk, 22.75)
    m_keels = 3*keel['kg_per_m']*L*(1+LACING)
    m_frames = frame['per_bay_kg']*9+frame['intermediate_kg']*9*(frames_per_bay-1)
    m_spine = RHO*2*math.pi*r*0.006*L
    out['S2_CANON_SECTORS'] = {'members': f"spine r {r:.2f} m x 6 mm; three keels r {keel['r_m']:.2f} m x {keel['t_m']*1e3:.0f} mm at r {rk:.0f} m (az 30/150/270); "
                                          f"frames every {Lf:.1f} m; tank arms r {frame['arm_r_m']:.2f} m",
                               'keel': keel, 'keel_force_N': Fk, 'frame_pitch_m': Lf, 'global_buckling_N': Pcr2, 'global_margin': Pcr2/(SF*F_root),
                               'EI_N_m2': E*I2, 'EA_N': E*A2, 'structure_kg': (m_keels+m_frames+m_spine)*1.10,
                               'mass_split_kg': {'keels_and_lacing': m_keels, 'frames_and_tank_arms': m_frames, 'spine': m_spine, 'joints_10pct': 0.1*(m_keels+m_frames+m_spine)},
                               'canon_rule': 'MEETS forward_defense.shield_load_path (hub + three primary sectors carried to the Brow)'}
    # --- S3: six longerons at r 35.5 m outside the tanks + ring frames + spine
    rc = 34.8      # just outside the outer tank envelope (r 34.5 m); skirt B2 shadow r 36.0 m
    Fl = F_root/6+M_root/(3*rc)
    lon = tube_for(Fl, bay/2)
    LON_R = rc
    I3 = 3*lon['area_m2']*rc**2+math.pi*r**3*0.006
    A3 = 6*lon['area_m2']+2*math.pi*r*0.006
    ring = tube_for(sum(b['propellant_kg']+b['tank_kg'] for b in bays)/9*0.0375*G0*2, 2*math.pi*rc/12)
    m_ring = ring['kg_per_m']*2*math.pi*rc*18+12*18*ring['kg_per_m']*rc
    m_lon = 6*lon['kg_per_m']*L*(1+LACING)
    out['S3_OUTER_CAGE'] = {'members': f"six longerons r {lon['r_m']:.2f} m at r {rc} m; 18 ring frames with 12 spokes", 'longeron': lon,
                            'EI_N_m2': E*I3, 'EA_N': E*A3, 'global_buckling_N': math.pi**2*E*I3/(4*L*L),
                            'structure_kg': (m_lon+m_ring+RHO*2*math.pi*r*0.006*L)*1.10,
                            'conflicts': ['longerons (outer face r 35.05 m) 0.95 m inside the skirt B2 shadow (r 36.0 m): a 0.2 deg attitude error exposes them',
                                          'blocks radial tank exchange and EVA access between frames',
                                          'canon shield load path wants the sectors at r 5 m: needs a second transfer to the Brow keels'],
                            'canon_rule': 'PARTLY: carries the Brow rim, not the three r 5 m sectors'}
    # --- S4: canon r 5 m sectors + three belt keels at r 20.1 m in the gap between the inner (r 8.05-18.95) and outer (r 21.3-34.2) tank rings
    rb = 20.1
    Fb = F_root/6+M_root/(1.5*(rk**2+rb**2)/rb)*(2/math.sqrt(3))
    belt = tube_for(Fb, Lf)
    I4 = 1.5*keel['area_m2']*rk**2+1.5*belt['area_m2']*rb**2
    A4 = 3*keel['area_m2']+3*belt['area_m2']+2*math.pi*r*0.006
    m4 = (m_keels+3*belt['kg_per_m']*L*(1+LACING)+m_frames*1.25+m_spine)*1.10
    out['S4_SECTORS_PLUS_BELT'] = {'members': f"S2 plus three belt keels r {belt['r_m']:.2f} m at r {rb} m (az 90/210/330) between the tank rings, frames tie both",
                                   'belt_keel': belt, 'EI_N_m2': E*I4, 'EA_N': E*A4, 'global_buckling_N': math.pi**2*E*I4/(4*L*L),
                                   'structure_kg': m4, 'canon_rule': 'MEETS (keeps the three r 5 m sectors; the belt is added)',
                                   'conflicts': ['belt keels sit in a 1.75 m radial gap between the tank rings: tank exchange must be axial or outward']}
    # --- S5: S2 (canon sectors, strength and the Brow hub + sector path) plus six outer stiffening longerons at r 34.8 m (Q45-collar
    #         radius family) sized for stiffness only, tied by the same bay frames and carried into the Brow outer truss ring
    s2, s3 = out['S2_CANON_SECTORS'], out['S3_OUTER_CAGE']
    out['S5_SECTORS_PLUS_OUTER_STIFFENERS'] = {'members': 'S2 (spine + three r 5 m sector keels) plus the S3 ring frames and six outer longerons at r 34.8 m, '
                                                          'tied by the same bay frames and carried into the Brow outer truss ring',
                                               'EI_N_m2': s2['EI_N_m2']+s3['EI_N_m2']-E*math.pi*r**3*0.006, 'EA_N': s2['EA_N']+s3['EA_N']-E*2*math.pi*r*0.006,
                                               'structure_kg': s2['structure_kg']+s3['structure_kg']-RHO*2*math.pi*r*0.006*L*1.1,
                                               'canon_rule': 'MEETS (hub + three r 5 m sectors; the outer ring echoes the Q45 bypass collar radius)',
                                               'conflicts': ['as S3: outer longerons 0.95 m inside the skirt B2 shadow; tank access between frames only']}
    # stiffness sizing: area to add at each layout's outer member radius so the first bending mode (full tanks) reaches F_TARGET_HZ
    mL_full = m_tanks_full
    for k, o in out.items():
        need = (2*math.pi*F_TARGET_HZ)**2*L**3*(m_bow+0.2357*(mL_full+o['structure_kg']))/3
        o['EI_required_N_m2'] = need
        if o['EI_N_m2'] >= need:
            o['stiffness_add_kg'] = 0.0; continue
        lever = {'S1_SPINE_ONLY': None, 'S2_CANON_SECTORS': (3, rk, 1.5), 'S3_OUTER_CAGE': (6, rc, 3.0), 'S4_SECTORS_PLUS_BELT': (3, rb, 1.5),
                 'S5_SECTORS_PLUS_OUTER_STIFFENERS': (6, rc, 3.0)}[k]
        if lever is None:
            t_need = (need/E)/(math.pi*r**3)
            o['stiffness_add_kg'] = RHO*2*math.pi*r*t_need*L-o['structure_kg']/1.1
            o['stiffness_note'] = f'needs a {t_need:.1f} m wall on r {r} m: infeasible'
            continue
        n, rr, fac = lever
        dA = (need-o['EI_N_m2'])/(E*fac*rr**2)/n*n
        o['stiffness_add_kg'] = RHO*dA*L*(1+LACING)*1.1
        o['stiffness_member_area_m2_each'] = dA/n
        o['stiffness_member_r_m_each_at_t_over_r_0p05'] = math.sqrt(dA/n/(2*math.pi*TR))
    for k, o in out.items():
        o['structure_stiff_kg'] = o['structure_kg']+max(o.get('stiffness_add_kg', 0.0), 0.0)
    # vibration for each (cantilever from the root, distributed tank mass, bow tip mass)
    for k, o in out.items():
        for case, m_dist in (('full', m_tanks_full), ('dry', m_tanks_dry)):
            ms = o['structure_kg']
            mL = m_dist+ms
            o.setdefault('f_bending_Hz', {})[case] = math.sqrt(3*o['EI_N_m2']/(L**3*(m_bow+0.2357*mL)))/(2*math.pi)
            o.setdefault('f_axial_Hz', {})[case] = math.sqrt(o['EA_N']/L/(m_bow+mL/3))/(2*math.pi)
    return out


def frame_mass(bays, rk, arm_len):
    """One bay frame: a ring at the keel radius plus a radial two-chord truss girder to each tank saddle, set in the 2 m gap between
    bays (girder depth 1.8 m). The girder takes the tank's axial inertia at the design acceleration as bending (chord force M / depth)
    and the lateral envelope as shear."""
    a_ax = 0.0375*G0  # peak 0.0187 g x DAF 2
    worst = max(bays, key=lambda b: b['vessel_max_kg'])
    m_v = worst['vessel_max_kg']; depth = 1.8
    Mb = m_v*a_ax*arm_len
    chord = tube_for(Mb/depth, 2.0)
    kg_m = 2*chord['kg_per_m']*(1+0.4)              # two chords + diagonals
    n_outer, n_inner = 12, 8
    arms_kg = n_outer*kg_m*arm_len+n_inner*kg_m*8.5
    ring = tube_for(m_v*a_ax*4, 2*math.pi*rk/12)
    ring_kg = ring['kg_per_m']*2*math.pi*rk
    return {'arm_r_m': chord['r_m'], 'girder_kg_per_m': kg_m, 'per_bay_kg': arms_kg+ring_kg+n_outer*2*150.0+n_inner*2*120.0,
            'intermediate_kg': ring_kg+3*kg_m*rk, 'design_vessel_kg': m_v, 'saddle_note': 'two isolating saddles per tank, 120-150 kg each (PROTOTYPE)'}


def slosh(R, bays):
    """First lateral slosh mode of a cylindrical tank (radius a) under axial acceleration g_eff: f = (1/2 pi) sqrt(1.841 g_eff / a tanh(1.841 h/a))."""
    a_min = min(b['a_start_g'] for b in R['closure']['burns'])*G0; a_max = max(b['a_end_g'] for b in R['closure']['burns'])*G0
    out = {}
    for nm, a in (('outer', 6.45), ('inner', 5.45)):
        out[nm] = [math.sqrt(1.841*g/a)/(2*math.pi) for g in (a_min, a_max)]
    return out


def corridor(L):
    """ISS-015 options. K1 crew trunk continued inside the spine bore; K2 separate 2.2 m pressurised tube beside the spine (r 3 m, az 90);
    K3 robot rail plus EVA only."""
    out = {}
    for key, d, note in (('K1_TRUNK_IN_SPINE', 1.9, 'continues the canon crew trunk (inside the spine bore, X 93.85-134.7 m); 1.65 m clear after service trays; spine becomes a pressure vessel'),
                         ('K2_TUBE_BESIDE_SPINE', 2.2, 'own 2.2 m pressure tube at r 3 m, az 90 deg, between the keels; spine bore stays free for services (or a longer launcher)')):
        R_ = d/2
        t = max(CABIN_PA*R_*SF/(4.5e8/1.0), 0.0025)          # Al-Li, 450 MPa, SF 2
        shell = 2780*2*math.pi*R_*t*1.5                       # stiffeners x1.5
        liner = 5.0*2*math.pi*R_                                # MLI, liner
        fit = 25.0                                              # floor/rail, air duct, lights, cabling
        kgm = shell+liner+fit
        out[key] = {'diameter_m': d, 'wall_mm': t*1e3, 'kg_per_m': kgm, 'mass_kg': kgm*(L+6.0)+9*350.0, 'hatches': 10,
                    'hatch_clear_m': 0.75, 'transit_min_at_1m_s': (L+6.0)/60.0, 'note': note}
    out['K3_ROBOT_RAIL_EVA'] = {'kg_per_m': 6.0, 'mass_kg': 6.0*(L+6.0), 'note': 'unpressurised rail on keel 270; crew only in suits; no shirt-sleeve access to the bow',
                                'transit_min_at_1m_s': (L+6.0)/60.0}
    out['K2_TUBE_BESIDE_SPINE']['clearances_m'] = {'to_keel_30': math.hypot(5*math.cos(math.radians(30))-0, 5*math.sin(math.radians(30))-3.0)-1.1-0.3,
                                                   'to_inner_tank_envelope': 7.75-(3.0+1.1)}
    return out


def target_and_snout():
    L2 = {o['key']: o for o in REV2['launcher']['options']}; f = REV2['launcher']['pulse_Hz']; xr = REV2['launcher']['xray_per_pulse_J']
    d_face = L2['A']['line_of_sight_m']
    tol = {'IFE_DT_ice_extrapolation_g': 1.0e4/G0, 'levitated_sabot_mockup_g': 500.0, 'MFE_bare_pellet_fracture_g': [5e6/G0, 6e6/G0]}
    rows = []
    for a_g in (500.0, 1000.0, 3000.0, 6378.0, 13681.0):
        for d in (25.0, 45.0):
            v = d*f
            rows.append({'tolerance_g': a_g, 'open_flight_m': d, 'exit_m_s': v, 'accelerator_m': v*v/(2*a_g*G0),
                         'tip_flux_MW_m2': xr*f/(4*math.pi*d*d)/1e6})
    # open flight that a 289 m accelerator allows at a given tolerance
    Lb = L2['B']['accelerator_m']
    d_for = {str(a): math.sqrt(2*a*G0*Lb)/f for a in (1000.0, 3000.0)}
    to_bow = (CAN['spine_x_m'][1]+REV2['scale']['spine_gap_m'][1]-CAN['spine_x_m'][1])-L2['B']['muzzle_x_m']
    v_b = L2['B']['exit_speed_m_s']
    long_b = {'accelerator_m': to_bow, 'accel_g': v_b*v_b/(2*to_bow*G0),
              'needs': 'crew trunk out of the spine bore (corridor K2) through X 93.85-134.7 m and the stretch; breech at the bow'}
    # per-pulse X-ray fluence and adiabatic surface temperature jump: dT = F mu_m / c (deposition depth 1/(mu rho) >> diffusion in ~ns)
    mu = {'W': {1: 3680, 3: 1900, 10: 92, 30: 22.7, 50: 5.95, 100: 4.44}, 'C': {1: 2211, 3: 89.8, 10: 2.37, 30: 0.256, 50: 0.187, 100: 0.151}}
    cp = {'W': 134.0, 'C': 1500.0}
    limit_K = {'W': 3695-600, 'C': 3800-600}
    surfaces = {'shield_face_64.7m': xr/(4*math.pi*d_face**2), 'snout_tip_45m': xr/(4*math.pi*45.0**2), 'snout_tip_25m': xr/(4*math.pi*25.0**2)}
    jump = {s: {m: {str(k): F*mu[m][k]*0.1/cp[m] for k in mu[m]} for m in mu} for s, F in surfaces.items()}
    return {'tolerance_evidence_g': tol, 'accelerator_vs_tolerance': rows, 'open_flight_for_289m_m': d_for, 'B_long_to_bow': long_b,
            'fluence_J_m2_per_pulse': surfaces, 'fluence_J_cm2_per_pulse': {k: v/1e4 for k, v in surfaces.items()},
            'published_W_single_pulse_J_cm2': {'damage_soft_xray': [0.15, 0.21], 'no_roughening': [0.5, 0.7], 'HAPL_design': [0.4, 1.2]},
            'surface_jump_K_by_keV': jump, 'jump_limit_K_from_600K': limit_K,
            'steady_flux_MW_m2': {k: v*f/1e6 for k, v in surfaces.items()},
            'conduction_dT_K_5mm_W_k100': {k: v*f*0.005/100.0 for k, v in surfaces.items()},
            'cycles_per_year': f*3.156e7, 'mu_source': 'approximate NIST XCOM mass attenuation (cm2/g); spectrum UNKNOWN (T04)'}


def coil_cooling():
    co = REV2['coils']; out = {}
    eps = 0.8; sigma = 5.670374e-8
    # basis (T00 note at 222dad1, lab/variants/vertex-drive/planning/ISS-014_COIL_RADIATION.md): T03 C_W15 geometry scaled 1.5007 to V4.
    # C1 envelope share 0.0252 (10.4 GW) matches Rev 2; C2 winding 0.085 m, 3x envelope 0.25 m, share 0.0038 (1.6 GW). Rev 2 had given
    # C2 C1's 4.8 m envelope (screen.py copied it): that 30.1 GW total is kept only as the upper case.
    T00_W = {'C1': 10.4e9, 'C2': 1.6e9}
    for c in co['coils']:
        q = c['flux_W_m2']; A = T00_W[c['name']]/q
        c = dict(c, xray_W=T00_W[c['name']], burn_face_m2=A)
        T_pass = (q/(eps*sigma))**0.25
        # pumped tin (T01 hot-radiator fluid) at 1,800 K, 300 K rise; lithium alternative
        mdot_sn = c['xray_W']/(240.0*300.0); mdot_li = c['xray_W']/(4200.0*300.0)
        back_leak = sigma*0.02*(2000.0**4)*A          # armour back face 2,000 K through a 0.02 effective emissivity foil stack
        out[c['name']] = {'xray_W': c['xray_W'], 'flux_MW_m2': q/1e6, 'passive_one_face_T_K': T_pass,
                          'tin_kg_s': mdot_sn, 'tin_m3_s': mdot_sn/6990.0, 'lithium_kg_s': mdot_li, 'lithium_m3_s': mdot_li/480.0,
                          'armour_dT_5mm_W_K': q*0.005/100.0, 'back_face_to_warm_screen_W': back_leak,
                          'warm_screen_to_cold_mass_W_at_1W_m2': A*2*1.0, 'cold_power_W_at_COP_1_over_60': A*2*1.0*60}
    hot_areal = 939730.5471811587/461618.93543012073; hot_flux = co['coil_xray_total_W']/co['extra_hot_area_m2']
    out['cases_W'] = {'T03_basis': 11.9e9, 'T00_extrapolated_C1_grows': 15.5e9, 'rev2_upper_case': co['coil_xray_total_W']}
    out['cases_hot_area_m2'] = {k: v/hot_flux for k, v in out['cases_W'].items()}
    tot = sum(T00_W.values())
    out['total'] = {'xray_W': tot, 'extra_hot_area_m2': tot/hot_flux, 'extra_hot_radiator_kg': tot/hot_flux*hot_areal,
                    'share_of_hot_circuit': tot/494.6042880719548e9, 'basis': 'T00 222dad1 (T03 geometry); upper case 30.1 GW kept', 'pump_W_at_1MPa_tin': sum(out[k]['tin_m3_s'] for k in ('C1', 'C2'))*1e6,
                    'neutron_note': 'T04 neutron escape 5.5e-6 of fusion power: coil nuclear heating ~ 14 kW total, but T02 puts loop neutron fluence at 3-62x REBCO tolerance and the coils share the per-area dose (lab/variants/vertex-drive/studies/futures/CONVERGENCE.md)',
                    'booking_T00': 'T00 222dad1: not booked. plume_on_hardware (478.5 GW) is plasma only; radiation_on_hardware (10.2 GW) covers loops + struts + shield (Omega 0.0248). Booking needs a closure_coils share in a Vertex adapter (X-T06-3).'}
    return out


def main():
    R = screen.solve('V4')
    bays, tb = stretch_masses(R)
    x_root = CAN['spine_x_m'][1]; x_bow = x_root+REV2['scale']['spine_gap_m'][1]-x_root; L = x_bow-x_root
    F, rows, prop_TB, tank_TB = burn_loads(R, bays, M_BOW_KG)
    N_peak = max(r['root_axial_N'] for r in rows)
    N_design = N_peak*DAF
    V_lat, M_lat = lateral(bays, M_BOW_KG, x_root, x_bow+4.0, A_LAT_G)
    m_fwd_full = M_BOW_KG+tank_TB+prop_TB
    N_15g = m_fwd_full*1.5*G0
    opts = options(N_design, M_lat, L, bays, M_BOW_KG, x_root)
    opts15 = options(N_15g, M_lat, L, bays, M_BOW_KG, x_root)
    V_s, M_s = lateral(bays, M_BOW_KG, x_root, x_bow+4.0, A_LAT_SENS_G)
    optsS = options(N_design, M_s, L, bays, M_BOW_KG, x_root)
    sl = slosh(R, bays)
    out = {
        'stretch': {'x_m': [x_root, x_bow], 'length_m': L, 'bays': 9, 'bay_pitch_m': L/9, 'vessels': len(tb['vessels']),
                    'propellant_kg': prop_TB, 'tank_kg': tank_TB, 'bow_kg_PROTOTYPE': M_BOW_KG, 'forward_kg_full': m_fwd_full,
                    'bay_masses': bays},
        'loads': {'thrust_N': F, 'root_axial_by_burn': rows, 'root_axial_peak_N': N_peak, 'DAF': DAF, 'root_axial_design_N': N_design,
                  'lateral_g': A_LAT_G, 'root_shear_N': V_lat, 'root_moment_N_m': M_lat,
                  'canon_1p5g_ceiling_root_axial_N': N_15g, 'slew_0p1deg_s_bow_g': (0.1*math.pi/180)**2*400/G0+0.1*math.pi/180/60*400/G0},
        'options_operational': opts, 'options_canon_1p5g': {k: {'structure_kg': v['structure_kg'], 'members': v['members']} for k, v in opts15.items()},
        'options_lateral_0p01g': {k: {'structure_kg': v['structure_kg'], 'members': v['members']} for k, v in optsS.items()},
        'f_target_Hz': F_TARGET_HZ, 'lateral_sensitivity_g': A_LAT_SENS_G,
        'dynamics': {'pulse_Hz': REV2['launcher']['pulse_Hz'], 'ring_spin_Hz': 4/60, 'slosh_Hz': sl,
                     'requirement': 'bending mode above 3x the highest slosh and ring-spin frequency, below the pulse rate by >100x (quasi-static); local frame and tank-saddle modes must avoid 195.7 Hz and its harmonics',
                     'pulse_ripple_transmissibility_at_f1': None},
        'joints': [
            {'id': 'J1', 'x_m': [137.9, 140.75], 'what': 'canon spine end and farm-front frame: splice sleeve on the spine, keel shoes on the canon sector rails, a new transfer frame'},
            {'id': 'J2', 'x_m': 'every 30.6 m', 'what': 'bay splices on keels and spine (keels in 30.6 m segments for assembly); joint efficiency 0.8 used'},
            {'id': 'J3', 'x_m': [413.25, 416.15], 'what': 'bow interface: spine to the canon shield spine column, keels to the Brow-side sector keels (hub + three sectors)'},
            {'id': 'J4', 'x_m': 'each tank', 'what': 'tank saddles: G10/CFRP isolating struts (1.5-20 K tanks on a warm frame), one fixed and one sliding saddle per tank for 0.1 m axial contraction'}],
        'corridor': corridor(L),
        'launcher_target': target_and_snout(),
        'coil_cooling': coil_cooling(),
    }
    S2 = opts['S2_CANON_SECTORS']
    T = 1/(1-(REV2['launcher']['pulse_Hz']/S2['f_axial_Hz']['full'])**2)
    out['dynamics']['pulse_ripple_transmissibility_at_f1'] = abs(T)
    (HERE/'rev3.json').write_text(json.dumps(out, indent=1, default=float))
    print('stretch', round(L, 1), 'm  prop', round(prop_TB/1e3), 't  tanks', round(tank_TB/1e3), 't')
    print('root axial peak', round(N_peak/1e6, 2), 'MN design', round(N_design/1e6, 2), 'MN  1.5 g', round(N_15g/1e6), 'MN  lateral moment', round(M_lat/1e6), 'MN m')
    for k, o in opts.items():
        print(k, o['members'], '| mass', round(o['structure_kg']/1e3, 1), 't | f_bend', {c: round(v, 3) for c, v in o['f_bending_Hz'].items()},
              '| f_ax', {c: round(v, 2) for c, v in o['f_axial_Hz'].items()}, '| stiff', round(o['structure_stiff_kg']/1e3), 't | 1.5g', round(opts15[k]['structure_kg']/1e3), 't | lat0.01', round(optsS[k]['structure_kg']/1e3), 't')
    print('S2 global margin', round(S2['global_margin'], 2), 'slosh', sl)
    for k, v in out['corridor'].items():
        print(k, round(v['mass_kg']/1e3, 1), 't', round(v['kg_per_m']), 'kg/m')
    print(json.dumps(out['launcher_target']['B_long_to_bow']), json.dumps(out['launcher_target']['open_flight_for_289m_m']))
    print(json.dumps(out['launcher_target']['surface_jump_K_by_keV']['snout_tip_45m']))
    print(json.dumps({k: {kk: (round(vv, 1) if isinstance(vv, float) else vv) for kk, vv in v.items() if kk != 'neutron_note'} for k, v in out['coil_cooling'].items()})[:1500])


if __name__ == '__main__':
    main()
