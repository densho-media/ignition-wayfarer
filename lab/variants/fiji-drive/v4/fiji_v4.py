"""Fiji Drive v4: an independent recheck of IFD-1 (continuous D-3He) and a pulsed direct-fusion alternative, judged against the same
Wayfarer mission. Research study (PROTOTYPE); it reads data/wayfarer_3d.toml for mission and mass numbers and the v3 results only to
compare against them. No canon, data or generator is changed.

  python3 lab/variants/fiji-drive/v4/fiji_v4.py        -> results/v4.json and a printed summary

Independence: the reactivities (Bosch-Hale 1992), bremsstrahlung (relativistic Rider/Wesson form), the coil Monte Carlo (thick coils
with real slot depth) and the mass budget are written here from scratch, not imported from v3.
"""
import json
import math
import tomllib
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TOML = tomllib.loads((ROOT/'data/wayfarer_3d.toml').read_text())
V3 = json.loads((HERE.parent/'v3/results/integrated.json').read_text())

MEV = 1.602176634e-13; U = 1.66053907e-27; KEV = 1.602176634e-16; MU0 = 4e-7*math.pi; SIGMA = 5.670374419e-8; C = 299792458.0
G0 = 9.80665

# ---------------------------------------------------------------- reactivities (Bosch & Hale, Nucl. Fusion 32 (1992) 611), cm^3/s
BH = {'DT': (34.3827, 1124656, 1.17302e-9, 1.51361e-2, 7.51886e-2, 4.60643e-3, 1.35e-2, -1.0675e-4, 1.366e-5),
      'DHe3': (68.7508, 1124572, 5.51036e-10, 6.41918e-3, -2.02896e-3, -1.91080e-5, 1.35776e-4, 0.0, 0.0),
      'DDn': (31.3970, 937814, 5.43360e-12, 5.85778e-3, 7.68222e-3, 0.0, -2.964e-6, 0.0, 0.0),
      'DDp': (31.3970, 937814, 5.65718e-12, 3.41267e-3, 1.99167e-3, 0.0, 1.05060e-5, 0.0, 0.0)}


def sigv(r, T):
    """<sigma v> in m^3/s at ion temperature T keV."""
    BG, mrc2, C1, C2, C3, C4, C5, C6, C7 = BH[r]
    th = T/(1-T*(C2+T*(C4+T*C6))/(1+T*(C3+T*(C5+T*C7))))
    xi = (BG**2/(4*th))**(1/3)
    return C1*th*math.sqrt(xi/(mrc2*T**3))*math.exp(-3*xi)*1e-6


Q = {'DHe3': 18.353, 'DDn': 3.269, 'DDp': 4.033, 'DT': 17.589}       # MeV
EPS_DHE3 = 18.353*MEV/((2.01410178+3.01602932)*U)                   # J/kg of reacted D+He3


def brems_W_m3(ne, Te, Zeff):
    """Bremsstrahlung (e-i + e-e, relativistic corrections; Rider 1995 / Wesson) in W/m^3, ne in m^-3, Te in keV."""
    x = Te/511.0
    return 5.35e-37*ne**2*math.sqrt(Te)*(Zeff*(1+0.7936*x+1.874*x**2) + 3/math.sqrt(2)*x*(1+1.1*x+x**2-1.25*x**2.5))


def channels(Ti, Te, he3_to_d, tritium_burn=0.0):
    """Fractions of gross fusion power: charged, bremsstrahlung, neutron (D-D, plus D-T from bred tritium when tritium_burn > 0)."""
    nD = 1.0; nHe = he3_to_d; ne = nD+2*nHe; Zeff = (nD+4*nHe)/ne
    n0 = 1e20  # cancels
    rDHe = nD*nHe*n0**2*sigv('DHe3', Ti); rDDn = 0.5*(nD*n0)**2*sigv('DDn', Ti); rDDp = 0.5*(nD*n0)**2*sigv('DDp', Ti)
    rDT = rDDp*tritium_burn
    Pf = (rDHe*Q['DHe3']+rDDn*Q['DDn']+rDDp*Q['DDp']+rDT*Q['DT'])*MEV
    Pn = (rDDn*2.449+rDT*14.07)*MEV
    Pb = brems_W_m3(ne*n0, Te, Zeff)
    return {'Ti_keV': Ti, 'Te_keV': Te, 'he3_to_d': he3_to_d, 'brems': Pb/Pf, 'neutron': Pn/Pf, 'neutral': (Pb+Pn)/Pf,
            'charged': 1-(Pn/Pf), 'Zeff': Zeff}


# ---------------------------------------------------------------- mission and mass (data/wayfarer_3d.toml, operating_point.py logic)
OP = TOML['physics']['operating_point']
VE = OP['exhaust_velocity_m_s']; DV = 0.016*C                        # 0.016 c per burn (first_ignition), four burns
TANK = TOML['physics']['fuel_loads']['tank_dry_fraction']
BUDGET = {i['id']: i['mass_kg'] for i in TOML['physics']['mass_budget']['items']}
END0 = OP['protected_and_operational_kg']; INV0 = OP['legacy_inventory_kg']


def mission(end0, ve=VE, burns=4):
    """Four equal 0.016 c burns ending at end0, with tank dry mass growing with capacity (same law as operating_point.mission)."""
    R = math.exp(DV/ve)
    P = (R**burns-1)*(end0-TANK*INV0)/(1-(R**burns-1)*TANK)
    if P < 0 or (1-(R**burns-1)*TANK) <= 0:
        return None
    end = end0+TANK*(P-INV0)
    return {'ve_km_s': ve/1e3, 'mass_ratio_total': R**burns, 'propellant_t': P/1e3, 'end_t': end/1e3, 'departure_t': (end+P)/1e3}


def burn_times(m0, P_jet, ve):
    """Power-limited constant-thrust burn sequence: mdot = 2 P / ve^2. Returns first-burn time, initial acceleration, total time."""
    mdot = 2*P_jet/ve**2; R = math.exp(DV/ve); t1 = m0*(1-1/R)/mdot; t_all = m0*(1-1/R**4)/mdot
    return {'mdot_kg_s': mdot, 'thrust_N': mdot*ve, 'a0_g': mdot*ve/m0/G0, 'burn1_days': t1/86400, 'mission_burn_years': t_all/3.156e7}


def ve_gate(eta, burnup, inert_ratio=0.0, recovery=0.0):
    """Highest exhaust velocity a D-3He drive can reach: jet KE = eta * reacted * eps; exhaust mass = reacted/burnup minus recovered
    unburned fuel, plus inert mass (H2, liner, ablator) per kg of fuel fed."""
    fed = 1/burnup; ex = 1+(fed-1)*(1-recovery)+inert_ratio*fed
    return math.sqrt(2*eta*EPS_DHE3/ex)


# ---------------------------------------------------------------- part 1: independent recheck of IFD-1
def recheck_ifd1():
    dp = V3['design_point']['central']
    out = {}
    # 1a channels
    out['channels'] = {k: channels(*a) for k, a in {'hot_ion_0.5:1': (150, 75, 0.5), 'central_1:1': (100, 100, 1.0),
                                                    'canon_2.5:1': (100, 100, 2.5), 'cool_70keV_1:1': (70, 70, 1.0)}.items()}
    # 1b energy-ledger closure and the exhaust-mass consistency (the ledger must also close in mass)
    P = dp['P_fus_TW']*1e12; L = dp['ledger_GW']; out['ledger_sum'] = sum(dp['ledger_fraction'].values())
    P_jet = [v for k, v in L.items() if k.startswith('directed')][0]*1e9
    mdot = 2*P_jet/VE**2; reacted = P/EPS_DHE3
    out['mass_closure'] = {'exhaust_kg_s': mdot, 'reacted_kg_s': reacted, 'inert_allowed_kg_s': mdot-reacted,
                           'v3_label': 'v3 labelled the whole 0.52 g/s as H2 mass loading; 84 % of it is reacted fuel (ash), so only '
                                       f'{(mdot-reacted)*1e3:.3f} g/s is left for unburned fuel plus H2',
                           'burnup_needed_without_recovery': reacted/mdot}
    # burn time and particle confinement needed for that burnup
    ch = out['channels']['central_1:1']; n_i = None
    pd = P/(math.pi*dp['r_plasma_m']**2*dp['L_m'])
    sv = sigv('DHe3', 100)
    # P/V = nD nHe sv Q with nD = nHe = n/2  ->  n
    n = math.sqrt(4*pd/(sv*Q['DHe3']*MEV)); tau_burn = 2/(n*sv)
    b_need = reacted/mdot
    out['confinement'] = {'ion_density_m3': n, 'tau_burn_s': tau_burn,
                          'tau_particle_needed_s_without_recovery': tau_burn*b_need/(1-b_need),
                          'tau_particle_needed_s_canon_burnup_0.8': tau_burn*0.8/0.2,
                          'beta_at_field': 2*MU0*n*2.5*100*KEV/dp['field_T']**2,
                          'note': 'burnup = tau_p/(tau_p+tau_burn) for continuous feed; open and FRC devices hold particles for ms-s'}
    out['ve_gate_continuous'] = {f'tau_p_{t}s': {'burnup': t/(t+tau_burn), 've_km_s': ve_gate(0.62, t/(t+tau_burn))/1e3}
                                 for t in (0.1, 1, 10, 100)}
    out['ve_gate_continuous']['canon_assumption'] = {'burnup': 0.8, 'recovery': 0.95, 'eta': 0.62,
                                                     've_km_s': ve_gate(0.62, 0.8, recovery=0.95)/1e3}
    # 1c wall flux: analytic finite line source vs the v3 design point
    R, Lp = dp['R_face_m'], dp['L_m']; f_n = ch['neutral']
    q_inf = f_n*P/(2*math.pi*R*Lp)
    q_mid = q_inf*(Lp/2)/math.sqrt(R**2+(Lp/2)**2)
    out['wall_flux_analytic'] = {'q_infinite_MW_m2': q_inf/1e6, 'q_midplane_finite_MW_m2': q_mid/1e6, 'v3_peak_MW_m2': dp['wall_MW_m2']}
    # 1d thick-coil Monte Carlo (real coil depth, faces and sides), 16 coils over L at coverage 0.25
    out['coil_mc'] = coil_mc(R_face=R, R_out=dp['R_out_m'], L=Lp, r_p=dp['r_plasma_m'], n_coils=16, cover=0.25,
                             shield_r=dp['shield_radius_m'], shield_gap=2.5)
    mc = out['coil_mc']
    P_wall = 10e6/(mc['peak_face_W_m2_per_W_neutral']*f_n)
    P_heat = 10.8e9/((mc['own']+mc['shield'])*f_n)
    P_corr = min(P_wall, P_heat)
    out['corrected_power'] = {'P_fus_TW_at_10MW_m2_peak': P_wall/1e12, 'P_fus_TW_heat_limited': P_heat/1e12,
                              'P_fus_TW': P_corr/1e12, 'binding': 'hot loop' if P_heat < P_wall else 'wall flux',
                              'v3_P_fus_TW': dp['P_fus_TW'], 'neutral_share_v4': f_n, 'neutral_share_v3': 0.1955,
                              'hardware_fraction_v3': dp['hardware_fraction'], 'hardware_fraction_v4': mc['own']+mc['shield'],
                              'hot_loop_GW_at_P_corr': (mc['own']+mc['shield'])*f_n*P_corr/1e9}
    # 1e sparse-coil confinement checks
    pitch = Lp/16; w = 0.25*pitch; a = (R+dp['R_out_m'])/2; B = dp['field_T']
    ripple = 2*math.exp(-2*math.pi*(a-dp['r_plasma_m'])/pitch)
    NI = B/MU0*pitch; J = NI/(w*0.6)
    W = B**2/(2*MU0)*math.pi*a**2*Lp
    out['sparse_coils'] = {'pitch_m': pitch, 'coil_width_m': w, 'ripple_at_plasma_edge': ripple, 'NI_per_coil_MA': NI/1e6,
                           'J_winding_MA_m2_0.6m_deep': J/1e6, 'magnetic_pressure_MPa': B**2/(2*MU0)/1e6,
                           'field_energy_J': W, 'virial_structure_t': {
                               'carbon_composite_SF1': 2*W/1.9e6/1e3, 'carbon_composite_SF2.5': 2*W/(1.9e6/2.5)/1e3,
                               'maraging_steel_SF1.5': 2*W/(2.0e9/1.5/8000)/1e3, 'v3_used': dp['masses_t']['coil_structure']},
                           'note': 'v3 sized the coil structure at ultimate composite strength with no safety factor; Fiji amplification '
                                   'does not lower the field energy the structure must hold (virial theorem)'}
    # 1f complete spacecraft mass budget with IFD-1
    m = dp['masses_t']; drive_v3 = sum(m.values())
    drive_v4 = drive_v3-m['coil_structure']+out['sparse_coils']['virial_structure_t']['carbon_composite_SF2.5']
    end0 = END0-BUDGET['drive_package']+drive_v4*1e3
    mi = mission(end0); bt = burn_times(mi['departure_t']*1e3, 0.62*P_corr, VE)
    out['mass_budget'] = {'canon_drive_package_t': BUDGET['drive_package']/1e3, 'ifd1_drive_v3_t': drive_v3, 'ifd1_drive_v4_t': drive_v4,
                          'protected_operational_t': end0/1e3, 'mission': mi, 'burns': bt,
                          'today': mission(END0)}
    return out


def coil_mc(R_face, R_out, L, r_p, n_coils, cover, shield_r, shield_gap, n=400000, seed=11):
    """Rays from a uniform plasma cylinder against thick ring coils (face at R_face, back at R_out, axial width cover*pitch) and a
    forward shadow disk. A ray in a gap escapes only if it clears the coil sides before R_out."""
    rng = np.random.default_rng(seed)
    r = r_p*np.sqrt(rng.random(n)); ph = 2*np.pi*rng.random(n); z0 = L*rng.random(n)
    x0, y0 = r*np.cos(ph), r*np.sin(ph)
    mu = 2*rng.random(n)-1; az = 2*np.pi*rng.random(n); s = np.sqrt(1-mu**2)
    dx, dy, dz = s*np.cos(az), s*np.sin(az), mu
    def t_at(Rc):
        a = dx**2+dy**2; b = 2*(x0*dx+y0*dy); c = x0**2+y0**2-Rc**2
        return (-b+np.sqrt(np.maximum(b**2-4*a*c, 0)))/(2*np.maximum(a, 1e-30))
    t1 = t_at(R_face); z1 = z0+dz*t1; t2 = t_at(R_out); z2 = z0+dz*t2
    pitch = L/n_coils; w = cover*pitch
    def in_coil(z):
        k = np.floor(z/pitch); loc = z-k*pitch
        return (z >= 0) & (z <= L) & (np.abs(loc-pitch/2) <= w/2)
    inside = (z1 >= 0) & (z1 <= L)
    face = inside & in_coil(z1)
    # side hit: the ray moves from z1 to z2 inside the coil-annulus; it hits a side if a coil edge lies between them
    k1 = np.floor(z1/pitch); lo = k1*pitch+(pitch-w)/2; hi = lo+w
    zmin, zmax = np.minimum(z1, z2), np.maximum(z1, z2)
    gap_lo = np.where(z1 > hi, hi, lo-pitch+w); gap_hi = np.where(z1 > hi, lo+pitch, lo)
    side = inside & ~face & ((zmin < gap_lo) | (zmax > gap_hi)) & (zmax > 0) & (zmin < L)
    # forward shadow disk at z = -shield_gap
    fwd = ~inside & (dz < 0); tz = (-shield_gap-z0)/np.where(dz == 0, -1e-30, dz)
    rz = np.hypot(x0+dx*tz, y0+dy*tz); shield = fwd & (rz <= shield_r)
    escape = ~(face | side | shield)
    # peak face flux: energy per unit area on the face band nearest the midplane, per watt of neutral power
    mid = face & (np.abs(z1-L/2) < pitch/2)
    area_mid = 2*np.pi*R_face*w
    return {'face': face.mean(), 'side': side.mean(), 'own': (face | side).mean(), 'shield': shield.mean(), 'escape': escape.mean(),
            'v3_own': 0.25117, 'v3_shield': 0.02902,
            'peak_face_W_m2_per_W_neutral': mid.mean()/area_mid, 'mean_face_W_m2_per_W_neutral': face.mean()/(n_coils*area_mid)}


# ---------------------------------------------------------------- part 2: pulsed direct-fusion model
def burn_parameter(T, he3_to_d=1.0, calib=0.7):
    """H_B (kg/m^2) in the burn-fraction law b = rhoR/(rhoR + H_B): H_B = 8 c_s m/<sv> for an equimolar binary fuel, calibrated by
    `calib` so D-T at 20 keV gives ~7 g/cm^2 (textbook 6-7)."""
    m = (2.014+3.016*he3_to_d)/(1+he3_to_d)*U; Z = (1+2*he3_to_d)/(1+he3_to_d)
    cs = math.sqrt((1+Z)*T*KEV/m)
    return calib*8*cs*m/sigv('DHe3', T)


def pulse(rhoR_g_cm2, T=100.0, rho_g_cc=1000.0, eta_noz=0.79, inert=0.0, mu_en=0.024, lam_n=(6.0, 15.0), post_brems=0.02):
    """One D-3He pulse. Self-absorption: neutral radiation emitted inside the fuel escapes with (1 - e^-tau)/tau for X-rays
    (tau = mu_en rhoR, mu_en ~ 0.024 cm^2/g Compton energy absorption at ~100 keV) and e^(-rhoR/lambda) for neutrons; absorbed
    radiation stays in the plasma and becomes exhaust energy. Bred tritium burns in situ in proportion to the burn fraction."""
    rr = rhoR_g_cm2*10.0
    b = rr/(rr+burn_parameter(T))
    ch = channels(T, T, 1.0, tritium_burn=b)
    tau = mu_en*rhoR_g_cm2
    x_esc = (ch['brems']+post_brems)*(1-math.exp(-tau))/tau
    nDD = channels(T, T, 1.0)['neutron']; nDT = ch['neutron']-nDD
    n_esc = nDD*math.exp(-rhoR_g_cm2/lam_n[0])+nDT*math.exp(-rhoR_g_cm2/lam_n[1])
    eta = eta_noz*(1-x_esc-n_esc)
    rho = rho_g_cc*1e3; R = rr/rho; m = 4/3*math.pi*R**3*rho
    E = b*m*EPS_DHE3
    return {'rhoR_g_cm2': rhoR_g_cm2, 'T_keV': T, 'rho_g_cc': rho_g_cc, 'burnup': b, 'fuel_g': m*1e3, 'radius_mm': R*1e3,
            'yield_J': E, 'yield_t_TNT': E/4.184e9, 'xray_escape': x_esc, 'neutron_escape': n_esc, 'eta_jet': eta,
            've_km_s': math.sqrt(2*eta*b*EPS_DHE3/(1+inert))/1e3, 'inert_ratio': inert}


DRIVERS = {
    # name: (electrical->target efficiency, specific mass kg per W of average electrical draw, waste-heat temperature K, inert kg/pulse)
    'standoff_laser': (0.15, 1e-4, 350.0, 0.0),        # diode-pumped solid-state laser, projected 10-20 % (NIF wall-plug ~1 %)
    'heavy_ion_beam': (0.30, 2e-4, 400.0, 0.0),        # induction/RF linac, projected 25-35 %
    'magnetic_liner': (0.40, 5e-5, 600.0, 0.35),       # FDR-class: coil-driven metal liner, 0.28-0.41 kg per pulse becomes exhaust
}
CASES = {'optimistic': dict(gain=3000, rho=3000.0, fluence=4e4, amp=30.0, spec_scale=0.3),
         'central': dict(gain=300, rho=1000.0, fluence=1e4, amp=10.0, spec_scale=1.0),
         'pessimistic': dict(gain=50, rho=300.0, fluence=1e4, amp=3.0, spec_scale=3.0)}


def pulsed_engine(P_fus, p, driver, gain, fluence, amp, spec_scale, loops=3, loop_w=2.0, Je=3e8, rho_c=6500.0, rec_eff=0.95):
    """Engine budgets and drive mass at gross fusion power P_fus (PROTOTYPE sizing, every assumption a parameter):
    - stand-off R: escaping X-ray fluence per pulse on the nearest hardware below `fluence` J/m^2 (W melts near 1 J/cm^2);
    - nozzle: `loops` superconducting loops at R; the field at the stopping radius (0.8 R) holds the plasma energy; conductor ampere-turns
      2 R B / mu0 shared by the loops, divided by the Fiji amplification `amp` (canon B_eff = B_seed A_B); structure by the virial
      bound on a stored field of 0.3 E (flux compression carries the rest inertially), carbon composite at safety factor 2.5;
    - hardware solid angle: the loops (loops w / 2R) + the ship and its shadow shield seen from the burn point (r 37 m at R + 150 m);
    - driver: electrical draw E / (gain eta); its loss heat leaves at the driver temperature through its own radiator; recovery of that
      energy from the exhaust (inductive pickup) loses (1 - rec_eff), rejected into the 1800 K loop."""
    eta_d, spec, T_d, inert = DRIVERS[driver]
    E = p['yield_J']; f = P_fus/E; esc = p['xray_escape']+p['neutron_escape']
    R = math.sqrt(p['xray_escape']*E/(4*math.pi*fluence)); r_stop = 0.8*R
    B = math.sqrt(2*MU0*E*(1-esc)/(4/3*math.pi*r_stop**3))
    NI = 2*R*B/MU0/amp
    conductor_t = NI/Je*2*math.pi*R*rho_c/1e3
    structure_t = 2*0.3*E/(1.9e6/2.5)/1e3
    om_loops = loops*loop_w/(2*R); om_ship = (math.pi*37.0**2)/(4*math.pi*(R+150.0)**2)
    rad_heat = P_fus*esc*(om_loops+om_ship)
    drawn = f*E/(gain*eta_d); drv_heat = drawn*(1-eta_d); rec_heat = drawn/rec_eff*(1-rec_eff)
    drv_rad_m2 = drv_heat/(2*0.9*SIGMA*T_d**4)
    driver_t = drawn*spec*spec_scale/1e3; drv_rad_t = drv_rad_m2*5.0/1e3
    # nozzle-loop neutron shield (mission fluence fixed by the mission energy, see pulsed_study)
    # loop neutron shield from the mission fluence (10x today's mission fusion energy, conservative for a heavier ship)
    F = 10*7.14e20*p['neutron_escape']/(5*MEV)/(4*math.pi*(R*100)**2)
    shield_m = max(0.0, math.log(F/3e18))*0.1 if F > 0 else 0.0
    shield_t = loops*2*math.pi*R*loop_w*shield_m*3.0+loops*2*math.pi*R*loop_w*0.001*19.3   # + 1 mm W X-ray armour band
    fixed_t = 100.0+100.0                                 # injector/target factory and the ship's shadow shield (PROTOTYPE)
    drive_t = conductor_t+structure_t+shield_t+driver_t+drv_rad_t+fixed_t
    return {'P_fus_TW': P_fus/1e12, 'rep_Hz': f, 'yield_J': E, 'P_jet_TW': p['eta_jet']*P_fus/1e12, 'standoff_m': R,
            'nozzle_field_T': B, 'NI_per_loop_MA': NI/loops/1e6, 'hardware_solid_angle': om_loops+om_ship,
            'radiation_heat_GW': rad_heat/1e9, 'recovery_heat_GW': rec_heat/1e9, 'hot_loop_GW': (rad_heat+rec_heat)/1e9,
            'driver_draw_GW': drawn/1e9, 'driver_heat_GW': drv_heat/1e9, 'driver_radiator_m2': drv_rad_m2, 'driver_T_K': T_d,
            'mass_t': {'nozzle_conductor': conductor_t, 'nozzle_structure': structure_t, 'nozzle_shield': shield_t,
                       'driver': driver_t, 'driver_radiator': drv_rad_t, 'injector_and_shadow_shield': fixed_t},
            'drive_t': drive_t, 'inert_kg_per_pulse': inert}


def design_point(p, driver, case):
    """Best fusion power for the mission: the hot-loop heat must fit the 10.8 GW share; above that, choose the power that minimises the
    total burn time with the drive mass (driver and its radiators grow with power) in the complete ship."""
    best = None
    for k in range(-30, 41):
        P = 10**(12+k/10)
        e = pulsed_engine(P, p, driver, **{x: case[x] for x in ('gain', 'fluence', 'amp', 'spec_scale')})
        if e['hot_loop_GW'] > 10.8:
            break
        end0 = END0-BUDGET['drive_package']+e['drive_t']*1e3
        ve = p['ve_km_s']*1e3
        mi = mission(end0, ve=ve)
        if not mi:
            return {'infeasible': True, 've_km_s': p['ve_km_s'], 'reason': 'at this ve the four-burn mass ratio makes the tank mass diverge'}
        bt = burn_times(mi['departure_t']*1e3, e['P_jet_TW']*1e12, ve)
        row = {**e, 'mission': mi, 'burns': bt}
        if best is None or bt['mission_burn_years'] < best['burns']['mission_burn_years']:
            best = row
    return best


def pulsed_study():
    out = {'burn_parameter_g_cm2': {T: burn_parameter(T)/10 for T in (50, 70, 100, 150)}}
    m = 2.5*U; cs = math.sqrt(2*20*KEV/m); out['dt_check_g_cm2'] = 0.7*8*cs*m/sigv('DT', 20)/10
    out['rhoR_scan'] = [pulse(r) for r in (2, 8.5, 20, 50, 100, 150, 250)]
    need = {}
    for en in (0.79, 0.55):
        lo, hi = 1.0, 5000.0
        for _ in range(80):
            mid = math.sqrt(lo*hi)
            (lo, hi) = (mid, hi) if pulse(mid, eta_noz=en)['ve_km_s'] < VE/1e3 else (lo, mid)
        need[f'eta_noz_{en}'] = pulse(hi, eta_noz=en)
    out['rhoR_for_mission_ve'] = need
    ref = need['eta_noz_0.79']
    out['inert_mass_effect'] = [{'inert_per_fuel': mu, 've_km_s': pulse(ref['rhoR_g_cm2'], inert=mu)['ve_km_s']}
                                for mu in (0, 0.05, 0.2, 1, 10, 100)]
    out['fdr_class_liner'] = {'liner_kg': 0.35, 'fuel_g': ref['fuel_g'],
                              've_km_s': pulse(ref['rhoR_g_cm2'], inert=0.35/(ref['fuel_g']/1e3))['ve_km_s']}
    P_jet_need = 0.5*OP_THRUST*VE
    out['mission_power'] = {'P_jet_TW': P_jet_need/1e12, 'P_fus_TW': P_jet_need/ref['eta_jet']/1e12}
    # density sets the pulse size (rhoR fixed by ve): stand-off and rate
    out['density_scan'] = []
    for rho in (300.0, 1000.0, 3000.0, 10000.0):
        pp = pulse(ref['rhoR_g_cm2'], rho_g_cc=rho)
        out['density_scan'].append({'rho_g_cc': rho, 'fuel_g': pp['fuel_g'], 'yield_t_TNT': pp['yield_t_TNT'],
                                    'rate_at_mission_Hz': out['mission_power']['P_fus_TW']*1e12/pp['yield_J'],
                                    'standoff_m_1J_cm2': math.sqrt(pp['xray_escape']*pp['yield_J']/(4*math.pi*1e4))})
    # designs: each driver x case
    out['designs'] = {}
    for drv in DRIVERS:
        for cname, case in CASES.items():
            pp = pulse(ref['rhoR_g_cm2'], rho_g_cc=case['rho'], inert=DRIVERS[drv][3]/(pulse(ref['rhoR_g_cm2'], rho_g_cc=case['rho'])['fuel_g']/1e3))
            d = design_point(pp, drv, case)
            at_mission = pulsed_engine(out['mission_power']['P_fus_TW']*1e12, pp, drv, **{x: case[x] for x in ('gain', 'fluence', 'amp', 'spec_scale')})
            out['designs'][f'{drv}/{cname}'] = {'pulse': pp, 'best': d, 'at_mission_power': at_mission}
    # mission neutron fluence on the nozzle loops
    E_total = mission(END0)['propellant_t']*1e3*ref['burnup']*EPS_DHE3
    n_esc = E_total*ref['neutron_escape']/(5*MEV)
    out['nozzle_neutron_fluence'] = {'mission_fusion_J_today_mass': E_total, 'escaping_neutrons': n_esc,
                                     'fluence_n_cm2_at_1km': n_esc/(4*math.pi*1e5**2),
                                     'note': 'rhoR 110 g/cm^2 thermalises almost all neutrons in the fuel; bred tritium then burns, so the '
                                             'real escape depends on 14 MeV transport (lambda ~15 g/cm^2 assumed)'}
    return out


OP_THRUST = 21.77e6          # N, today's power-limited peak (operating_point.burn: 261.3 TW, 21.77 MN)


def topology(pulsed):
    """Chambers and nozzles. The pulse size is fixed by the rhoR the mission ve needs, so every chamber needs a full-size nozzle around
    its own burn point; more chambers only lower the rate per chamber."""
    d = pulsed['designs']['heavy_ion_beam/central']['best']; R = d['standoff_m']
    nozzle_t = sum(v for k, v in d['mass_t'].items() if k.startswith('nozzle'))
    rows = []
    for nc in (1, 2, 4):
        cross = 0.0 if nc == 1 else min(nc-1, 3)*(3*2.0*2*math.pi*R)/(4*math.pi*(2.2*R)**2)
        rows.append({'chambers': nc, 'nozzles': nc, 'rate_per_chamber_Hz': d['rep_Hz']/nc, 'cluster_span_km': 2.2*R*(nc-1)/1e3 if nc < 4 else 2.2*R*2**0.5/1e3,
                     'hardware_solid_angle': d['hardware_solid_angle']+cross, 'nozzle_mass_t': nc*nozzle_t,
                     'one_out_thrust_left': (nc-1)/nc})
    return {'standoff_m': R, 'rows': rows,
            'one_chamber_four_nozzles': {'feasible': False, 'reason': 'a pulse expands from a point within microseconds; a kiloton-class '
                                         'plasma sphere cannot be ducted into four nozzles, so one burn point means one nozzle; its four '
                                         'loop sectors keep the four-way vectoring role'}}


def comparison(v1, pulsed):
    rows = {}
    ifd = v1['mass_budget']; P_ifd = v1['corrected_power']['P_fus_TW']*1e12
    rows['IFD-1 continuous (v4 recheck)'] = {
        'P_fus_TW': P_ifd/1e12, 've_km_s_tau_p_1s': v1['ve_gate_continuous']['tau_p_1s']['ve_km_s'],
        've_km_s_canon_recovery': v1['ve_gate_continuous']['canon_assumption']['ve_km_s'],
        'hot_loop_GW': v1['corrected_power']['hot_loop_GW_at_P_corr'], 'drive_t': ifd['ifd1_drive_v4_t'],
        'departure_t': ifd['mission']['departure_t'], **ifd['burns']}
    for k, v in pulsed['designs'].items():
        b = v['best']
        if not b or b.get('infeasible'):
            rows[f'pulsed {k}'] = {'infeasible': True, 've_km_s': v['pulse']['ve_km_s']}
            continue
        rows[f'pulsed {k}'] = {'P_fus_TW': b['P_fus_TW'], 've_km_s': v['pulse']['ve_km_s'], 'hot_loop_GW': b['hot_loop_GW'],
                               'driver_heat_GW': b['driver_heat_GW'], 'driver_radiator_m2': b['driver_radiator_m2'],
                               'standoff_m': b['standoff_m'], 'rep_Hz': b['rep_Hz'], 'drive_t': b['drive_t'],
                               'departure_t': b['mission']['departure_t'], **b['burns']}
    rows['today (canon WORKING, eta 0.8, burnup 0.8, recovery 0.95)'] = {
        'P_fus_TW': 261.3, 've_km_s': VE/1e3, 'hot_loop_GW': 10.45, 'drive_t': 250, 'departure_t': mission(END0)['departure_t'],
        **burn_times(mission(END0)['departure_t']*1e3, 0.5*OP_THRUST*VE, VE)}
    trade = []
    for ve in (19201e3, 15000e3, 10000e3, 6000e3):
        mi = mission(END0, ve=ve)
        trade.append({'ve_km_s': ve/1e3, **(mi or {'infeasible': 'tank mass diverges'}),
                      'jet_TW_at_today_thrust': 0.5*OP_THRUST*ve/1e12})
    return {'rows': rows, 've_trade_not_adopted': trade}


def main():
    v1 = recheck_ifd1(); pu = pulsed_study(); topo = topology(pu); comp = comparison(v1, pu)
    res = {'recheck_ifd1': v1, 'pulsed': pu, 'topology': topo, 'comparison': comp,
           'constants': {'eps_DHe3_J_kg': EPS_DHE3, 've_m_s': VE, 'dv_per_burn_m_s': DV}}
    (HERE/'results').mkdir(exist_ok=True)
    (HERE/'results/v4.json').write_text(json.dumps(res, indent=1, default=float))
    c = v1['channels']
    print('channels', {k: (round(v['brems'], 3), round(v['neutron'], 4)) for k, v in c.items()})
    print('mass closure', v1['mass_closure']); print('confinement', v1['confinement'])
    print('ve gate cont', v1['ve_gate_continuous'])
    print('wall', v1['wall_flux_analytic']); print('coil mc', v1['coil_mc']); print('corr', v1['corrected_power'])
    print('coils', v1['sparse_coils']); print('mass', v1['mass_budget'])
    print('H_B', pu['burn_parameter_g_cm2'], 'DT check', pu['dt_check_g_cm2'])
    print('need', {k: (round(v['rhoR_g_cm2'],1), round(v['burnup'],3), round(v['yield_t_TNT'],1), round(v['xray_escape'],3), round(v['eta_jet'],3)) for k, v in pu['rhoR_for_mission_ve'].items()})
    print('inert', pu['inert_mass_effect'], pu['fdr_class_liner']); print('mission power', pu['mission_power'])
    print('density', pu['density_scan'])
    for k, v in comp['rows'].items():
        print(k, {a: (round(b, 4) if isinstance(b, float) else b) for a, b in v.items()})
    for k, v in pu['designs'].items():
        if v['best'] and not v['best'].get('infeasible'): print(k, {a: round(b, 1) for a, b in v['best']['mass_t'].items()}, 'mission-power hot loop GW', round(v['at_mission_power']['hot_loop_GW']), 'drv heat GW', round(v['at_mission_power']['driver_heat_GW']))
    print('topo', topo); print('trade', comp['ve_trade_not_adopted']); print('fluence', pu['nozzle_neutron_fluence'])


if __name__ == '__main__':
    main()
