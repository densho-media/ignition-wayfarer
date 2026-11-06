"""Fiji Drive v3: integrated energy, radiation, thermal and topology study (owner brief 2026-11-03 07:53Z). Study code only.

  python3 lab/variants/fiji-drive/v3/integrated.py            -> lab/variants/fiji-drive/v3/results/integrated.json and a printed summary

Everything here is a conceptual estimate: formulas and inputs are printed with the results. Canon is read, never changed.
Sources for the material numbers are listed in lab/variants/fiji-drive/v3/REPORT.md (section 12).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE.parent), str(ROOT/'src/wayfarer')]
import spec                      # noqa: E402
import operating_point as op     # noqa: E402
import fiji_budget as fb         # noqa: E402

SIGMA = 5.670374419e-8; MU0 = 4e-7*math.pi; G0 = 9.80665; MEV = 1.602176634e-13; C = 299792458.0
s = spec.load()[0]
B01 = op.burn(s); MIS = op.mission(s)
VE = B01['exhaust_velocity_m_s']; M0 = MIS['departure_mass_kg']; EXPELLED_1 = B01['expelled_kg']
P_TODAY = B01['peak_fusion_power_W']; HOT_BUDGET = B01['hot_budget_W']; IDEAL_REJ = B01['ideal_rejection_W']

# ---------------------------------------------------------------- Phase I: channels -------------------------------------------------
# Fiji canon (IGNITION Fiji / Lattice Drive Science Model): He3:D 2.5 WORKING (10_FUSION), tritium exhausted (04 Fuel cycle LOCKED),
# NASA NIAC 2019 1 MW DFD split (15_ENERGY_FLOW rows 11-15): thrust 0.52, brems 0.205, synchrotron 0.142, neutrons 0.00257, gas box 0.13.
DFD = dict(thrust=0.52, bremsstrahlung=0.205, synchrotron=0.142, neutron=0.00257, gas_box=0.13)


def channel_cases():
    out = {}
    for key, (Ti, ratio, Te_over_Ti, label) in dict(
            optimistic=(150.0, 0.5, 0.5, 'hot-ion mode (Te = Ti/2), D-rich 0.5:1; Te/Ti = 0.5 is unproven for D-3He (alpha and proton slowing heat electrons)'),
            central=(100.0, 1.0, 1.0, 'Ti = Te = 100 keV, 1:1 (the v2 baseline); matches the NASA DFD bremsstrahlung share (0.205)'),
            canon_ratio=(100.0, 2.5, 1.0, 'Ti = Te = 100 keV at the WORKING canon 2.5:1 He3:D: more He-3 means fewer reactions per electron')).items():
        p = fb.plasma_split(Ti_keV=Ti, Te_keV=Ti*Te_over_Ti, he3_to_d=ratio, synchrotron_fraction=0.0)
        out[key] = dict(label=label, Ti_keV=Ti, Te_keV=Ti*Te_over_Ti, he3_to_d=ratio, brems=p['bremsstrahlung_fraction'], neutron=p['neutron_fraction'],
                        neutral=p['bremsstrahlung_fraction']+p['neutron_fraction'], mean_photon_keV=Ti*Te_over_Ti)
    return out


CASES = channel_cases()
# synchrotron: far-infrared (cyclotron harmonics), absorbed in a micron of wall, reflected by polished metal (R ~0.98-0.99); it is the
# one fusion photon channel a mirror can handle. Emitted share 0.05-0.14 (DFD 0.142 at 5 T); with reflecting coil faces most returns
# to the plasma, and the open gaps let the rest escape to space. Kept as a range; it lowers the charged share, not the hardware heat.
SYNC = dict(emitted=(0.05, 0.10, 0.142), coil_face_reflectivity=0.98)
NOZZLE_EFF = 0.88   # magnetic-nozzle thrust efficiency (detachment, divergence): PROTOTYPE, 0.8-0.9 in nozzle literature


def eta_directed(case, sync=0.10):
    return (1-CASES[case]['neutral']-sync)*NOZZLE_EFF

# ---------------------------------------------------------------- Phase I: audit of the v2 numbers ------------------------------------
V2 = json.loads((HERE.parent/'results/budget.json').read_text()) if (HERE.parent/'results/budget.json').exists() else {}


def audit():
    f_r = CASES['central']['neutral']
    return dict(
        absorbed_45TW=dict(formula='P_fus x neutral fraction x intercepted share = 261.3 TW x 0.21 x 0.82', value_TW=P_TODAY*0.209*0.8193/1e12,
                           source='lab/variants/fiji-drive/fiji_budget.py intercept(): 60,000 isotropic rays from the v2 core plasma against the modelled coils, '
                                  'limiters, inserts, frames, lattice, HX, shield, blades and engines'),
        shield_645GW=dict(formula='P_fus x neutral x cone fraction; cone = (1 - cos 12.5 deg)/2 = 0.0118 (thermal bulkhead rim r 37 m at X 48.9 seen from the core at X -118)',
                          value_GW=P_TODAY*0.209*(1-math.cos(math.radians(12.5)))/2/1e9),
        radiator_10_8GW=dict(formula='hot_share 0.75 x ideal rejection; ideal = 26,882 m2 effective x 0.9 x sigma x 1800^4',
                             ideal_GW=IDEAL_REJ/1e9, drive_share_GW=HOT_BUDGET/1e9,
                             source='src/wayfarer/operating_point.py burn(); data/wayfarer_3d.toml [physics.operating_point] hot_share, [radiators.*]'),
        b01_absorbed_fraction=dict(note='B01 absorbed fraction 4e-5 is a requirement, not a mechanism (Fiji 15_ENERGY_FLOW: 1e-4 "DIAGNOSTIC / UNVALIDATED"; 04_ROOT_TRUTHS P1 "OPEN FUNDAMENTAL").'),
        canon_efficiency=dict(note='Canon directed efficiency 0.8 exceeds the charged share: with 0.21 neutral and 0.10 synchrotron the ceiling is '
                                   f'{(1-0.209-0.10):.2f} before nozzle losses, {eta_directed("central"):.2f} after.'),
        neutral_fraction_check=dict(central=f_r, dfd_published=DFD['bremsstrahlung']+DFD['neutron']))

# ---------------------------------------------------------------- Phase III/IV: why absorbers cannot carry X-rays into the exhaust ----
# NIST XCOM (rounded), cm2/g: total attenuation mu/rho and energy-absorption mu_en/rho
XCOM = {'H': {50: (0.336, 0.0271), 100: (0.294, 0.0406)}, 'Li': {50: (0.150, 0.0128), 100: (0.130, 0.0190)},
        'Sn': {50: (8.9, 6.8), 100: (1.68, 0.93)}, 'W': {50: (5.95, 4.55), 100: (4.44, 1.97)}, 'Pb': {50: (8.04, 6.0), 100: (5.55, 1.98)}}


def absorber_study(P_rad=P_TODAY*0.209, mdot=B01['peak_mass_flow_kg_s']):
    rows = []
    for el in ('H', 'Li', 'Sn', 'W'):
        mu_en = XCOM[el][100][1]; col = 1/mu_en*10            # kg/m2 for one e-fold of energy absorption at 100 keV
        area = 4*math.pi*3.0**2                                # a 3 m absorber shell round the plasma
        inventory = col*area; eps = 0.63*P_rad/mdot            # specific energy if all propellant flow carries the absorbed power
        dens = {'H': 71.0, 'Li': 512.0, 'Sn': 6990.0, 'W': 19300.0}[el]; thick = col/dens
        p_if_held = (2/3)*dens*eps                             # ideal-gas pressure if the absorber stayed in place at that energy
        rows.append(dict(material=el, mu_en_100keV_cm2_g=mu_en, efold_column_kg_m2=col, layer_thickness_m=thick, shell_inventory_t=inventory/1e3,
                         residence_s=inventory/mdot, specific_energy_J_kg=eps, pressure_if_held_Pa=p_if_held,
                         fiji_150T_magnetic_pressure_Pa=150.0**2/(2*MU0)))
    # vaporisation / ablation as the energy sink instead (expendable liquid metal)
    ablate = {el: dict(J_kg=h, kg_s_per_TW=1e12/h) for el, h in (('Li', 2.1e7+4.0e6), ('Sn', 2.5e6+0.6e6), ('H2_to_3000K', 4.5e7))}
    # propellant as regenerative coolant: everything the whole H2 flow can take before injection (LH2 -> 3000 K, partial dissociation)
    regen = dict(mdot_kg_s=mdot, enthalpy_J_kg=4.5e7, capacity_GW=mdot*4.5e7/1e9)
    # hydrogen as a neutron moderator: 2.45 MeV n-p scattering ~2.5 b, half the energy per collision
    n_mfp_LH2 = 1/(0.071e3/1.6735e-27*2.5e-28)
    return dict(xray_columns=rows, ablation=ablate, regenerative_cooling=regen, neutron_mean_free_path_LH2_m=n_mfp_LH2,
                verdict=('A column that absorbs 100 keV bremsstrahlung (25-500 kg/m2) cannot also reach exhaust-class specific energy while it stays '
                         'in place: the pressure is 10^5-10^7 times the 150 T Fiji magnetic pressure. Ablation needs 10^4-10^6 kg/s per TW. The '
                         'whole hydrogen flow as a coolant carries ~0.05 GW. X-ray energy cannot be routed into the exhaust at Wayfarer ve.'))


def xray_optics():
    out = []
    for el, rho in (('Ir', 22.56), ('Au', 19.3), ('W', 19.25)):
        for E in (10, 50, 100):
            th = math.sqrt(rho)/E                               # degrees, theta_c ~ sqrt(rho[g/cm3]) / E[keV]
            out.append(dict(coating=el, E_keV=E, critical_angle_deg=th, max_deflection_deg=2*th))
    Te = CASES['central']['Te_keV']
    return dict(table=out, brems_power_below_10keV=1-math.exp(-10/Te),
                verdict='Below the critical angle a mirror deflects rays by at most 2 theta_c (0.1-1 deg); it cannot turn isotropic emission away '
                        'from coils or the shield. Multilayers extend to ~80 keV only in narrow bands at a few theta_c. REJECTED.')

# ---------------------------------------------------------------- Phase II/V: the wall-flux limit -------------------------------------
Q_LIMITS = {'W_armour_Li_heat_pipe_1900K': 10e6, 'flowing_liquid_Sn_1300K': 20e6, 'flowing_liquid_Li_projection': 50e6}


def wall_limit(R_face, L, q, f_neutral):
    """Line source of length L on the axis of coil faces at radius R_face: q_face ~ P_rad/(2 pi R L). Max fusion power for flux q."""
    return 2*math.pi*R_face*L*q/f_neutral


def bfield_for(P, r_p, L):
    p = P/(math.pi*r_p**2*L)
    return 5.0*(p/5658842.421)**0.25, p          # Fiji 35_SCALING_LIMITS B^4 proxy, anchored to the 1 MW NASA DFD

# ---------------------------------------------------------------- Phase VI: topology geometry and Monte Carlo ---------------------------
BLADES = [math.radians(a) for a in (30, 150, 270)]
BLADE = dict(r0=6.5, r1=37.0, x_aft=-133.25, x_fwd=48.9, half_thick=0.15)
HULL = dict(r=7.2, x_aft=-134.0)
R_ENV = 6.5          # cluster outer radius: inside the blade roots (no silent enlargement in cross-section)
L_PLASMA = 30.0      # plasma zone length of the aft-extended drive section (PROTOTYPE)
X_FWD_PLASMA = -139.0  # plasma zone forward end: 5 m aft of the hull end, room for the shadow shield
SHIELD_GAP = 2.5
COVER = 0.25         # coil + armour coverage of each module's cylinder (sparse open-cage coils, PROTOTYPE)
T_COIL = 1.8         # radial build: armour 0.1 + coil-protecting neutron shield 1.4 (mission fluence, neutron_shield()) + winding/casing 0.3 (m)


def topologies():
    T = {}
    def ring(N, phase=90.0):
        s_ = math.sin(math.pi/N); Ro = R_ENV*s_/(1+s_); rc = R_ENV-Ro
        return Ro, [(rc*math.cos(math.radians(phase+360*k/N)), rc*math.sin(math.radians(phase+360*k/N))) for k in range(N)]
    T['F5_1x1'] = dict(reactors=1, nozzles=1, R_out=R_ENV-0.5, pos=[(0.0, 0.0)], manifold=False,
                       note='one on-axis core straight into one segmented nozzle (optional mapping)')
    T['F0_1x4_aft'] = dict(reactors=1, nozzles=4, R_out=R_ENV-0.5, pos=[(0.0, 0.0)], manifold=True,
                           note='canon topology moved aft: one core, four-way manifold, four nozzles')
    Ro, pos = ring(2, 90.0); T['F1_2x4'] = dict(reactors=2, nozzles=4, R_out=Ro, pos=pos, manifold=True, note='two cores on the Z axis, each splitting to two nozzles')
    Ro, pos = ring(4, 45.0); T['F2_4x4'] = dict(reactors=4, nozzles=4, R_out=Ro, pos=pos, manifold=False, note='one module per nozzle, the current N1-N4 corners')
    Ro, pos = ring(6, 90.0); T['F3_6x6'] = dict(reactors=6, nozzles=6, R_out=Ro, pos=pos, manifold=False, note='six modules on a ring')
    Ro, pos = ring(8, 90.0); T['F4_8x8'] = dict(reactors=8, nozzles=8, R_out=Ro, pos=pos, manifold=False, note='eight modules on a ring')
    for k, t in T.items():
        t['R_face'] = t['R_out']-T_COIL; t['r_plasma'] = max(0.0, t['R_face']-0.5)
    return T


def _hit_cyl(o, d, cy, cz, R, x0, x1):
    """Distance to the first crossing of an infinite cylinder (axis along X through (cy,cz)) from outside, within x0..x1, or inf."""
    oy = o[:, 1]-cy; oz = o[:, 2]-cz
    a = d[:, 1]**2+d[:, 2]**2; b = 2*(oy*d[:, 1]+oz*d[:, 2]); c = oy**2+oz**2-R**2
    disc = b*b-4*a*c; t = np.full(len(o), np.inf)
    ok = (disc > 0) & (a > 1e-12) & (c > 0)
    sq = np.sqrt(np.where(ok, disc, 0)); t1 = (-b-sq)/(2*np.where(a > 1e-12, a, 1))
    xh = o[:, 0]+t1*d[:, 0]; good = ok & (t1 > 0) & (xh >= x0) & (xh <= x1)
    t[good] = t1[good]; return t


def _hit_disk(o, d, x, R, cy=0.0, cz=0.0):
    t = np.where(np.abs(d[:, 0]) > 1e-12, (x-o[:, 0])/np.where(np.abs(d[:, 0]) > 1e-12, d[:, 0], 1), np.inf)
    y = o[:, 1]+t*d[:, 1]-cy; z = o[:, 2]+t*d[:, 2]-cz
    return np.where((t > 0) & (y*y+z*z <= R*R), t, np.inf)


def _hit_blade(o, d, phi):
    n = np.array([0.0, -math.sin(phi), math.cos(phi)]); u = np.array([0.0, math.cos(phi), math.sin(phi)])
    dn = d@n; on = o@n
    t = np.where(np.abs(dn) > 1e-12, -on/np.where(np.abs(dn) > 1e-12, dn, 1), np.inf)
    p = o+t[:, None]*d; r = p@u; x = p[:, 0]
    good = (t > 0) & (r >= BLADE['r0']) & (r <= BLADE['r1']) & (x >= BLADE['x_aft']) & (x <= BLADE['x_fwd'])
    # thickness: rays travelling nearly in-plane graze the blade edge-on; count a hit if they pass within half_thick of the plane
    tt = np.where(good, t, np.inf)
    # edge-on grazing: closest approach to the plane while inside the blade's r/x box
    return tt


def mc_topology(t, n=200_000, seed=7, L=None):
    rng = np.random.default_rng(seed); L = L or L_PLASMA
    x0, x1 = X_FWD_PLASMA-L, X_FWD_PLASMA
    pos = t['pos']; N = len(pos); Rf = t['R_face']; Ro = t['R_out']
    # shadow shield: one disk forward of the plasma, sized to block every line from the plasma line to the hull end disk (r 7.2 at X -134)
    xs = X_FWD_PLASMA+SHIELD_GAP; worst = max(math.hypot(y, z) for y, z in pos)
    # the aftmost source point sets the size: its lines to the hull rim cross the shield plane farthest out
    r_s = worst+(HULL['r']+worst)*((xs-x0)/(HULL['x_aft']-x0))+0.3
    res = []
    for k, (cy, cz) in enumerate(pos):
        o = np.zeros((n, 3)); o[:, 0] = rng.uniform(x0, x1, n); o[:, 1] = cy; o[:, 2] = cz
        d = rng.normal(size=(n, 3)); d /= np.linalg.norm(d, axis=1)[:, None]
        alive = rng.random(n) >= COVER                               # own coils take COVER (rays that leave the own cylinder through a gap survive)
        own = 1-alive.mean()
        # start the surviving rays at the own outer cylinder so they cannot hit their own module again
        tags = {}
        cand = {'shield': _hit_disk(o, d, xs, r_s), 'hull_end': _hit_disk(o, d, HULL['x_aft'], HULL['r']),
                'hull_side': _hit_cyl(o, d, 0.0, 0.0, HULL['r'], HULL['x_aft'], 48.9)}
        for j, phi in enumerate(BLADES):
            cand[f'blade_{j}'] = _hit_blade(o, d, phi)
        for m, (my, mz) in enumerate(pos):
            if m != k:
                tc = _hit_cyl(o, d, my, mz, Ro, x0-1.0, x1+1.0)
                # neighbour coils cover COVER of the cylinder; its gaps let the ray pass to the neighbour's far side, then out (count first wall only)
                cand[f'neighbour_{m}'] = np.where(rng.random(n) < COVER+(1-COVER)*COVER, tc, np.inf)   # near-side coils, or the far side after a gap
        names = list(cand); M = np.vstack([cand[q] for q in names]); first = np.argmin(M, axis=0); tmin = M[first, np.arange(n)]
        hit = alive & np.isfinite(tmin)
        frac = {q: float(np.mean(hit & (first == i))) for i, q in enumerate(names)}
        res.append(dict(own=own, **frac))
    agg = {}
    for r in res:
        for q, v in r.items():
            key = 'neighbour' if q.startswith('neighbour') else ('blades' if q.startswith('blade') else q)
            agg[key] = agg.get(key, 0.0)+v/N
    agg['escape'] = 1-sum(agg.values())
    return dict(shield_radius_m=r_s, shield_x=xs, fractions=agg)

# ---------------------------------------------------------------- Phase VI/VII: evaluate each topology --------------------------------
MAN_EXTRA = 0.10     # four-way manifold hardware in the radiation view (septa, guide coils, gates) as extra intercepted share (v2 geometry: ~0.05-0.15)
RHO_SIGMA = dict(steel=7900/1.0e9, nanocomposite=1800/3.0e9)


def evaluate(T, case='central', qkey='W_armour_Li_heat_pipe_1900K', hot_budget=HOT_BUDGET, mc=None):
    f_n = CASES[case]['neutral']; q = Q_LIMITS[qkey]; out = {}
    for k, t in T.items():
        N = t['reactors']; fr = mc[k]['fractions']
        own = fr['own']+(MAN_EXTRA if t['manifold'] else 0.0)
        hardware = own+fr.get('neighbour', 0.0)+fr['shield']+fr['blades']+fr['hull_end']+fr['hull_side']
        if t['r_plasma'] < 0.25:
            out[k] = dict(feasible=False, reason='plasma radius below the 0.25 m DFD scale after the 1.8 m coil, shield and armour build'); continue
        P_wall = N*wall_limit(t['R_face'], L_PLASMA, q, f_n)                       # own armour flux limit
        # neighbour outer faces: flux from an adjacent line source at the centre spacing
        if N > 1:
            dmin = min(math.dist(a, b) for i, a in enumerate(t['pos']) for b in t['pos'][i+1:])
            P_cross = N*2*math.pi*(dmin-t['R_out'])*L_PLASMA*q/f_n
        else:
            P_cross = math.inf
        P_heat = hot_budget/(f_n*hardware) if qkey == 'W_armour_Li_heat_pipe_1900K' else math.inf
        P = min(P_wall, P_cross, P_heat)
        binding = 'own armour flux' if P == P_wall else ('cross-irradiation flux' if P == P_cross else 'hot-loop budget')
        B, pden = bfield_for(P/N, t['r_plasma'], L_PLASMA)
        W = B**2/(2*MU0)*math.pi*t['R_face']**2*L_PLASMA*N
        coil_t = {m: 2*W*rs/1e3 for m, rs in RHO_SIGMA.items()}
        armour_t = COVER*2*math.pi*(t['R_face']+0.7)*L_PLASMA*1.4*3000*N/1e3
        shield_t = math.pi*mc[k]['shield_radius_m']**2*1.0*2500/1e3
        overhead_t = 25*N+(60 if t['manifold'] else 0)
        eta = eta_directed(case); F = 2*eta*P/VE
        heat = f_n*P*hardware
        T_loop = {'W_armour_Li_heat_pipe_1900K': 1800, 'flowing_liquid_Sn_1300K': 1300, 'flowing_liquid_Li_projection': 800}[qkey]
        armour_heat = f_n*P*own; other_heat = heat-armour_heat
        new_rad_area = 0.0 if T_loop == 1800 else armour_heat/(2*0.9*SIGMA*T_loop**4)
        out[k] = dict(armour_loop_K=T_loop, armour_heat_GW=armour_heat/1e9, other_hardware_heat_GW=other_heat/1e9,
                      new_armour_radiator_m2=new_rad_area, hot_loop_load_GW=(heat if T_loop == 1800 else other_heat)/1e9,
                  feasible=True, P_fus_max_TW=P/1e12, binding=binding, P_wall_TW=P_wall/1e12, P_cross_TW=P_cross/1e12 if P_cross != math.inf else None,
                      P_heat_TW=P_heat/1e12, per_module_TW=P/N/1e12, hardware_fraction_of_neutral=hardware, permanent_heat_GW=heat/1e9,
                      neutral_TW=f_n*P/1e12, escaping_neutral_TW=f_n*P*(1-hardware)/1e12, field_T=B, power_density_W_m3=pden,
                      peak_wall_MW_m2=f_n*P/N/(2*math.pi*t['R_face']*L_PLASMA)/1e6,
                      mass_t=dict(coils_nanocomposite=coil_t['nanocomposite'], coils_steel=coil_t['steel'], armour_and_coil_shields=armour_t,
                                  shadow_shield=shield_t, module_overhead=overhead_t,
                                  total_nanocomposite=coil_t['nanocomposite']+armour_t+shield_t+overhead_t),
                      eta_directed=eta, thrust_kN=F/1e3, accel_mg=F/M0/G0*1e3, burn1_days=EXPELLED_1/(F/VE)/86400,
                      burn1_vs_today=(EXPELLED_1/(F/VE))/(EXPELLED_1/(B01['peak_thrust_N']/VE)),
                      one_module_out=dict(thrust_left=(N-1)/N if N > 1 else 0.0,
                                          trim_deg_to_balance=(math.degrees(math.atan(max(math.hypot(*p_) for p_ in t['pos'])/((N-1)*150.0))) if N > 1 else None)))
    return out


def radiator_options(Q=10e9):
    rows = []
    for name, T_, eps, areal in (('existing hot blades 1800 K', 1800, 0.90, 10.0), ('nanostructured hot face 1800 K, eps 0.95', 1800, 0.95, 10.0),
                                 ('armour loop radiator 1300 K', 1300, 0.90, 8.0), ('liquid-Li armour loop 800 K', 800, 0.90, 8.0),
                                 ('liquid-droplet sheet 1300 K (tin, eps_sheet 0.5)', 1300, 0.50, 1.0)):
        q2 = 2*eps*SIGMA*T_**4
        rows.append(dict(option=name, T_K=T_, both_faces_W_m2=q2, area_m2_per_10GW=Q/q2, mass_t_per_10GW=Q/q2*areal/1e3))
    return rows


def neutron_shield(P=1e11, case='central', R=5.0, L=L_PLASMA, burn_s=None):
    f = CASES[case]['neutron']; En = 2.45*MEV
    rate = f*P/En; flux = rate/(2*math.pi*R*L)/1e4
    total = MIS['mass_ratio_per_burn']
    E_jet_4 = 4*B01['jet_energy_J']; t_burn = E_jet_4/(eta_directed(case)*P) if burn_s is None else burn_s
    fluence = flux*t_burn; lim = 3e18
    efolds = max(0.0, math.log(fluence/lim)); thick = efolds*0.10
    return dict(P_fus_TW=P/1e12, neutron_rate_s=rate, coil_flux_n_cm2_s=flux, mission_burn_s=t_burn, mission_fluence_n_cm2=fluence,
                rebco_limit_n_cm2=lim, efolds=efolds, shield_thickness_m=thick, note='~0.1 m per e-fold for W/B4C/hydride (2.45 MeV); in-situ REBCO data suggest a lower limit')


def design_point(R_face=8.0, L=60.0, case='central'):
    """IFD-1: one on-axis core, aft of the hull, open-cage coils, W armour on Li heat pipes into the existing 1800 K hot loop."""
    t = dict(reactors=1, nozzles=1, R_out=R_face+T_COIL, R_face=R_face, r_plasma=R_face-3.0, pos=[(0.0, 0.0)], manifold=False)
    mc = mc_topology(t, L=L); fr = mc['fractions']; f_n = CASES[case]['neutral']; f_b = CASES[case]['brems']; f_neu = CASES[case]['neutron']
    q = Q_LIMITS['W_armour_Li_heat_pipe_1900K']
    hw = fr['own']+fr['shield']+fr['blades']+fr['hull_end']+fr['hull_side']
    P_wall = wall_limit(R_face, L, q, f_n); P_heat = HOT_BUDGET/(f_n*hw); P = min(P_wall, P_heat)
    sync = 0.10; eta = eta_directed(case, sync); F = 2*eta*P/VE; mdot = F/VE
    B, pden = bfield_for(P, t['r_plasma'], L)
    W = B**2/(2*MU0)*math.pi*R_face**2*L
    # energy ledger (fractions of gross fusion power, no double counting)
    led = {
        'directed exhaust (charged products + H2 mass loading, after nozzle losses)': (1-f_n-sync)*NOZZLE_EFF,
        'nozzle divergence and detachment loss (charged, leaves aft as plume)': (1-f_n-sync)*(1-NOZZLE_EFF),
        'synchrotron escaping to space through the coil gaps (net after 0.98 coil-face reflection)': sync,
        'bremsstrahlung escaping to space': f_b*fr['escape'], 'neutrons escaping to space': f_neu*fr['escape'],
        'neutral radiation into coil armour (hot loop 1800 K, blades)': f_n*fr['own'],
        'neutral radiation into the shadow shield (hot loop)': f_n*fr['shield'],
        'neutral radiation into blades and hull (radiate directly)': f_n*(fr['blades']+fr['hull_end']+fr['hull_side']),
    }
    tot = sum(led.values())
    shield_t = math.pi*mc['shield_radius_m']**2*1.0*2500/1e3
    armour_t = COVER*2*math.pi*(R_face+0.7)*L*1.4*3000/1e3
    coil_t = 2*W*RHO_SIGMA['nanocomposite']/1e3
    return dict(R_face_m=R_face, R_out_m=R_face+T_COIL, L_m=L, r_plasma_m=t['r_plasma'], x_plasma=(X_FWD_PLASMA-L, X_FWD_PLASMA), shield_x=mc['shield_x'],
                shield_radius_m=mc['shield_radius_m'], fractions=fr, hardware_fraction=hw, P_wall_TW=P_wall/1e12, P_heat_TW=P_heat/1e12, P_fus_TW=P/1e12,
                ledger_fraction=led, ledger_sum=tot, ledger_GW={k: v*P/1e9 for k, v in led.items()},
                hot_loop_GW=f_n*P*hw/1e9, hot_budget_GW=HOT_BUDGET/1e9, wall_MW_m2=f_n*P/(2*math.pi*R_face*L)/1e6, field_T=B, power_density_MW_m3=pden/1e6,
                field_energy_J=W, eta_directed=eta, thrust_kN=F/1e3, mass_flow_g_s=mdot*1e3, accel_mg=F/M0/G0*1e3,
                burn1_years=EXPELLED_1/mdot/86400/365.25, mission_burn_years=4*EXPELLED_1/mdot/86400/365.25*1.0,
                masses_t=dict(coil_structure=coil_t, armour_and_coil_shields=armour_t, shadow_shield=shield_t, heat_pipes_and_manifolds=0.02*f_n*P*hw/1e6,
                              controls_power_startup=40.0),
                neutron=neutron_shield(P, case, R=R_face, L=L), gap_to_1_1g=739e12/P, gap_to_today=P_TODAY/P)


def sensitivity():
    rows = []
    for c in CASES:
        for qk, q in Q_LIMITS.items():
            for L in (30.0, 60.0, 120.0):
                for Rf in (4.2, 8.0, 15.0):
                    P = wall_limit(Rf, L, q, CASES[c]['neutral']); F = 2*eta_directed(c)*P/VE
                    rows.append(dict(case=c, armour=qk, L_m=L, R_face_m=Rf, P_fus_TW=P/1e12, accel_mg=F/M0/G0*1e3,
                                     field_energy_J_at_10T=100/(2*MU0)*math.pi*Rf**2*L))
    return rows


def main():
    T = topologies(); mc = {k: mc_topology(t) for k, t in T.items()}
    ev = {c: {qk: evaluate(T, c, qk, mc=mc) for qk in Q_LIMITS} for c in CASES}
    # same with a dedicated 1300 K armour radiator: hot budget no longer binding (report the wall-limited ceiling)
    ev_free = {c: evaluate(T, c, 'flowing_liquid_Sn_1300K', hot_budget=1e18, mc=mc) for c in CASES}
    # status quo (v2 core inside the hull): bore face 3.45 m, plasma 7 m, intercepted 0.82
    sq = {}
    for c in CASES:
        f = CASES[c]['neutral']
        sq[c] = dict(P_wall_TW=wall_limit(3.37, 7.0, 10e6, f)/1e12, P_heat_TW=HOT_BUDGET/(f*0.8193)/1e12)
    req = {}
    for g in (1.1, 1.5):
        F = M0*g*G0; req[g] = dict(thrust_MN=F/1e6, jet_TW=F*VE/2/1e12, fusion_TW=F*VE/2/eta_directed('central')/1e12)
    res = dict(audit=audit(), channels=CASES, synchrotron=SYNC, dfd_reference=DFD, eta_directed={c: eta_directed(c) for c in CASES},
               absorbers=absorber_study(), xray_optics=xray_optics(), wall_limits_W_m2=Q_LIMITS, radiators=radiator_options(),
               neutron_shield=[neutron_shield(P) for P in (5e10, 2e11, 1e12)],
               topologies={k: {kk: vv for kk, vv in t.items()} for k, t in T.items()}, monte_carlo=mc, evaluation=ev,
               evaluation_with_armour_radiator=ev_free, status_quo_v2=sq, required_for_g=req,
               design_point={c: design_point(case=c) for c in CASES}, sensitivity=sensitivity(), today=dict(P_fus_TW=P_TODAY/1e12, thrust_MN=B01['peak_thrust_N']/1e6, ve_km_s=VE/1e3, departure_t=M0/1e3, burn1_days=B01['duration_d']))
    (HERE/'results').mkdir(exist_ok=True)
    (HERE/'results/integrated.json').write_text(json.dumps(res, indent=1, default=float)+'\n')
    print('channels', {c: (round(v['brems'], 3), round(v['neutron'], 4)) for c, v in CASES.items()})
    print('audit', json.dumps(res['audit'], indent=0, default=float)[:900])
    for k, m in mc.items():
        print(k, 'shield r %.1f' % m['shield_radius_m'], {q: round(v, 4) for q, v in m['fractions'].items()})
    for c in CASES:
        for qk in Q_LIMITS:
            print('==', c, qk)
            for k, v in ev[c][qk].items():
                if not v.get('feasible'):
                    print('  ', k, 'INFEASIBLE', v['reason']); continue
                print('  %-11s P %.3f TW (%s) | heat %.1f GW (armour %.1f @%dK, new rad %.0f m2) hw %.3f | B %.1f T q %.0f MW/m2 | a %.3f mg burn1 %.0f y | mass %.0f t' % (
                    k, v['P_fus_max_TW'], v['binding'], v['permanent_heat_GW'], v['armour_heat_GW'], v['armour_loop_K'], v['new_armour_radiator_m2'],
                    v['hardware_fraction_of_neutral'], v['field_T'], v['peak_wall_MW_m2'], v['accel_mg'], v['burn1_days']/365.25, v['mass_t']['total_nanocomposite']))
    dp = res['design_point']['central']; print('DESIGN', json.dumps({k: v for k, v in dp.items() if k not in ('neutron',)}, indent=0, default=float)[:3000])
    print('status quo', sq); print('required', req)
    print('absorbers', [(r['material'], round(r['efold_column_kg_m2']), '%.1e' % r['pressure_if_held_Pa']) for r in res['absorbers']['xray_columns']], res['absorbers']['regenerative_cooling'])
    print('radiators', [(r['option'], round(r['area_m2_per_10GW'])) for r in res['radiators']])
    print('neutron', [(n['P_fus_TW'], '%.1e' % n['mission_fluence_n_cm2'], round(n['shield_thickness_m'], 2)) for n in res['neutron_shield']])


if __name__ == '__main__':
    main()
