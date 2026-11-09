"""T04 target physics: pure, standard-library models used by ignition.py. Nothing here changes a calculator.

Every function returns numbers with the label the HANDOFF vocabulary needs (MODEL, EXTRAPOLATION, ASSUMPTION). Reactivities, the
bremsstrahlung formula and the burn parameter come from the four-burn calculator (fourburn.plasma, read-only); the rest is written here:

  fermi_*            Fermi-degenerate compression energy (the minimum work to compress cold fuel to density rho)
  gain_ceiling       highest target gain a compression-driven target can have: G <= eta_c b eps / (alpha eps_F(rho))
  hotspot_*          0-D self-heating boundary of a hot spot (charged-product heating >= bremsstrahlung + electron conduction),
                     validated against the published D-T ignition region, then applied to D-3He with and without magnetisation
  spark_*            a D-T core inside D-3He fuel: energy share, 14.1 MeV neutrons, tritium per pulse and per mission
  tamped_*           tamper inertial confinement on the burn fraction (the case the Atlas liner study did not model)
  in_flight_*        exposure of the next target in flight to the previous pulse
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
FB = ROOT / 'lab/studies/four-burn-mission'
if str(FB) not in sys.path:
    sys.path.insert(0, str(FB))
from fourburn import plasma                      # noqa: E402
from fourburn.const import U, MEV, KEV, M_D, M_HE3, EPS_DHE3, Q_MEV   # noqa: E402

HBAR = 1.054571817e-34
M_E = 9.1093837015e-31
E_CH = 1.602176634e-19
K_B = 1.380649e-23
GAMMA = 5.0 / 3.0

# fuel composition: mass per ion pair (kg), electrons per pair, ions per pair, charged energy per reaction (J)
FUELS = {
    'DT':   {'pair_kg': (2.01410178 + 3.01604928) * U, 'electrons': 2, 'ions': 2, 'Z2': 1.0, 'Zeff': 1.0,
             'Q_c_J': 3.52 * MEV, 'Q_J': Q_MEV['DT'] * MEV, 'products': [('alpha', 3.52, 4.0, 2.0)]},
    'DHe3': {'pair_kg': (M_D + M_HE3) * U, 'electrons': 3, 'ions': 2, 'Z2': 5.0 / 2.0, 'Zeff': 5.0 / 3.0,
             'Q_c_J': Q_MEV['DHe3'] * MEV, 'Q_J': Q_MEV['DHe3'] * MEV, 'products': [('alpha', 3.67, 4.0, 2.0), ('proton', 14.68, 1.0, 1.0)]},
}


# ----------------------------------------------------------------------------------------------------------------------------------
# compression energy and the gain ceiling
# ----------------------------------------------------------------------------------------------------------------------------------

def electron_density(fuel, rho_kg_m3):
    f = FUELS[fuel]
    return rho_kg_m3 / f['pair_kg'] * f['electrons']


def fermi_pressure_Pa(fuel, rho_kg_m3):
    """Degenerate electron pressure P_F = (2/5) n_e E_F (ideal, T = 0). For D-T this is the textbook ~2.2 rho^(5/3) Mbar."""
    n = electron_density(fuel, rho_kg_m3)
    E_F = HBAR ** 2 / (2 * M_E) * (3 * math.pi ** 2 * n) ** (2 / 3)
    return 0.4 * n * E_F


def fermi_energy_J_kg(fuel, rho_kg_m3):
    """Minimum (alpha = 1) internal energy per kg of cold fuel compressed to rho: (3/2) P_F / rho."""
    return 1.5 * fermi_pressure_Pa(fuel, rho_kg_m3) / rho_kg_m3


def gain_ceiling(b, rho_kg_m3, eta_c, alpha=1.0, fuel='DHe3', eps=EPS_DHE3, ignitor_J_per_kg=0.0):
    """Upper bound on target gain of a compression-driven target: yield b eps per kg of fuel over the driver energy that must at least
    supply alpha eps_F (plus any ignitor energy per kg) at coupling eta_c (driver energy -> fuel internal energy). MODEL: a bound, not a
    design; real targets also lose energy to the ablator, the hot spot, instabilities and preheat."""
    return eta_c * b * eps / (alpha * fermi_energy_J_kg(fuel, rho_kg_m3) + ignitor_J_per_kg)


def pellet_at(b, H_B_kg_m2, rho_kg_m3, P_fus_W, eps=EPS_DHE3):
    """Fuel-only sphere that reaches burn fraction b at density rho: rhoR, radius, mass, yield, rate at fusion power P_fus."""
    rhoR = plasma.rhoR_needed(b, H_B_kg_m2)
    R = rhoR / rho_kg_m3
    m = 4 / 3 * math.pi * R ** 3 * rho_kg_m3
    E = b * m * eps
    return {'rhoR_g_cm2': rhoR / 10, 'radius_mm': R * 1e3, 'fuel_mass_g': m * 1e3, 'yield_J': E, 'yield_t_TNT': E / 4.184e9,
            'rate_Hz': P_fus_W / E, 'compression_J_alpha1': m * fermi_energy_J_kg('DHe3', rho_kg_m3)}


# ----------------------------------------------------------------------------------------------------------------------------------
# hot-spot self-heating boundary (0-D)
# ----------------------------------------------------------------------------------------------------------------------------------

def sigv(fuel, T_keV):
    return plasma.sigv('DT' if fuel == 'DT' else 'DHe3', T_keV)


def range_g_cm2(fuel, product, T_keV, scale=1.0):
    """Areal range of a fusion product slowing in the fuel. D-T alphas: the Atzeni & Meyer-ter-Vehn fit
    rho*lambda = 0.025 T^1.25 / (1 + 0.0082 T^1.25) g/cm2 (TRANSCRIBED). Other products: electron-drag scaling from it,
    rho*lambda ~ sqrt(E A) T^1.5 / (Z^2 n_e/rho), i.e. x (sqrt(E A)/sqrt(3.52*4)) (4/Z^2) ((n_e/rho)_DT / (n_e/rho)_fuel).
    EXTRAPOLATION: the saturation term is kept as for alphas; `scale` is the sensitivity band."""
    base = 0.025 * T_keV ** 1.25 / (1 + 0.0082 * T_keV ** 1.25)
    if fuel == 'DT' and product == 'alpha':
        return base * scale
    p = {x[0]: x for x in FUELS[fuel]['products']}[product]
    _, E, A, Z = p
    ne_dt = FUELS['DT']['electrons'] / FUELS['DT']['pair_kg']
    ne_f = FUELS[fuel]['electrons'] / FUELS[fuel]['pair_kg']
    return base * math.sqrt(E * A) / math.sqrt(3.52 * 4) * (4 / Z ** 2) * (ne_dt / ne_f) * scale


def deposition(tau):
    """Krokhin-Rozanov fraction of fast-particle energy deposited in a uniform sphere of areal range ratio tau = rhoR / rho*lambda."""
    if tau <= 0:
        return 0.0
    if tau < 0.5:
        return 1.5 * tau - 0.8 * tau ** 2
    return 1 - 1 / (4 * tau) + 1 / (160 * tau ** 3)


def hotspot_rates(fuel, rhoR_g_cm2, T_keV, magnetised=False, range_scale=1.0, lnL=7.0, conduction_factor=1.0, brems_escape=True):
    """Per-kg heating and loss rates divided by rho (W m3 / kg2): all terms scale with rho, so the boundary depends on rhoR and T only."""
    f = FUELS[fuel]; m = f['pair_kg']
    sv = sigv(fuel, T_keV)
    heat_full = (1 / m) ** 2 * sv * f['Q_c_J']                 # equimolar: n_D = n_partner = rho / m (m = pair mass)
    if magnetised:
        dep = 1.0
    else:
        tot = sum(p[1] for p in f['products'])
        dep = sum(p[1] / tot * deposition(rhoR_g_cm2 / range_g_cm2(fuel, p[0], T_keV, range_scale)) for p in f['products'])
    ne_per_rho = f['electrons'] / m
    x = T_keV / 511.0
    Zeff = f['Zeff']
    ei = Zeff * (1 + 0.7936 * x + 1.874 * x ** 2)
    ee = 3 / math.sqrt(2) * x * (1 + 1.1 * x + x ** 2 - 1.25 * x ** 2.5)
    brems = 5.35e-37 * ne_per_rho ** 2 * math.sqrt(T_keV) * (ei + ee)
    if brems_escape:
        kappa_x = 0.40 * f['electrons'] / (m / U)               # Compton opacity per gram scales with electrons per nucleon (0.24 for D-3He)
        brems *= plasma.escape_probability(kappa_x * rhoR_g_cm2)
    # Spitzer electron conduction from a sphere: W/kg = 3 kappa T / (rho R^2) = 3 kappa T rho / (rhoR)^2 -> /rho^2 below
    T_K = T_keV * KEV / K_B
    kappa = 1.84e-10 * T_K ** 2.5 / lnL * (1.0 if fuel == 'DT' else 0.6)   # Z_eff 5/3: Spitzer reduction about 0.6
    if magnetised:
        kappa = 0.0
    cond = 3 * kappa * T_K / (rhoR_g_cm2 * 10) ** 2 * conduction_factor
    return {'heating': dep * heat_full, 'deposition': dep, 'brems': brems, 'conduction': cond, 'net': dep * heat_full - brems - cond}


def hotspot_boundary(fuel, T_grid, magnetised=False, range_scale=1.0, rhoR_max=500.0):
    """Lowest hot-spot rhoR (g/cm2) at which heating >= losses, per temperature; None where no rhoR works."""
    out = []
    for T in T_grid:
        lo, hi = 1e-3, rhoR_max
        if hotspot_rates(fuel, hi, T, magnetised, range_scale)['net'] <= 0:
            out.append({'T_keV': T, 'rhoR_g_cm2': None})
            continue
        if hotspot_rates(fuel, lo, T, magnetised, range_scale)['net'] > 0:
            out.append({'T_keV': T, 'rhoR_g_cm2': lo})
            continue
        for _ in range(80):
            mid = math.sqrt(lo * hi)
            if hotspot_rates(fuel, mid, T, magnetised, range_scale)['net'] > 0:
                hi = mid
            else:
                lo = mid
        out.append({'T_keV': T, 'rhoR_g_cm2': hi})
    return out


def ideal_ignition_window(fuel='DHe3', T_grid=None):
    """Temperatures where charged fusion power exceeds optically thin bremsstrahlung (no conduction, full deposition)."""
    T_grid = T_grid or [float(t) for t in range(5, 501, 1)]
    ok = [T for T in T_grid if hotspot_rates(fuel, 1e6, T, magnetised=True, brems_escape=False)['net'] > 0]
    best = max(T_grid, key=lambda T: (lambda r: r['heating'] / r['brems'])(hotspot_rates(fuel, 1e6, T, magnetised=True, brems_escape=False)))
    r = hotspot_rates(fuel, 1e6, best, magnetised=True, brems_escape=False)
    return {'fuel': fuel, 'T_min_keV': min(ok) if ok else None, 'T_max_keV': max(ok) if ok else None, 'T_best_keV': best,
            'best_heating_over_brems': r['heating'] / r['brems']}


def isochoric_hotspot_J(fuel, rhoR_g_cm2, T_keV, rho_kg_m3):
    """Thermal energy of an isochoric hot spot (fast-ignition style) of areal density rhoR at the fuel density: (3/2) n_tot T V."""
    f = FUELS[fuel]
    R = rhoR_g_cm2 * 10 / rho_kg_m3
    n_tot = rho_kg_m3 / f['pair_kg'] * (f['ions'] + f['electrons'])
    return 1.5 * n_tot * T_keV * KEV * 4 / 3 * math.pi * R ** 3


def isobaric_hotspot(fuel, rhoR_g_cm2, T_keV, P_Pa):
    """Hot spot in pressure balance with cold fuel at pressure P: density, radius and energy (3/2) P V."""
    f = FUELS[fuel]
    n_tot = P_Pa / (T_keV * KEV)
    rho = n_tot / (f['ions'] + f['electrons']) * f['pair_kg']
    R = rhoR_g_cm2 * 10 / rho
    return {'rho_g_cc': rho / 1e3, 'radius_mm': R * 1e3, 'energy_J': 1.5 * P_Pa * 4 / 3 * math.pi * R ** 3}


def larmor_BR_T_m(product='proton', E_MeV=14.68, A=1.0, Z=1.0):
    """Field x radius at which the Larmor radius equals the hot-spot radius (B R = p / (Z e))."""
    p = math.sqrt(2 * A * 1.67262192e-27 * E_MeV * MEV)
    return p / (Z * E_CH)


# ----------------------------------------------------------------------------------------------------------------------------------
# D-T core (spark / booster) inside D-3He fuel
# ----------------------------------------------------------------------------------------------------------------------------------

def spark(rhoR_DT_g_cm2, rhoR_total_g_cm2, fuel_mass_g, yield_J, rate_Hz, burn_s, H_B_DT_g_cm2=7.0, kappa_n14_cm2_g=0.05,
          tritium_half_life_y=12.32):
    """A central D-T sphere of areal density rhoR_DT inside fuel of total rhoR at the same density. Its mass share is
    (rhoR_DT/rhoR_total)^3. Burn fraction from the D-T burn parameter; 80 % of D-T energy in 14.1 MeV neutrons, removed by the
    surrounding D-3He with removal opacity kappa_n14 (ASSUMPTION, about half the 2.45 MeV value)."""
    share_m = (rhoR_DT_g_cm2 / rhoR_total_g_cm2) ** 3
    m_dt = share_m * fuel_mass_g * 1e-3
    b_dt = rhoR_DT_g_cm2 / (rhoR_DT_g_cm2 + H_B_DT_g_cm2)
    eps_dt = Q_MEV['DT'] * MEV / ((2.01410178 + 3.01604928) * U)
    E_dt = b_dt * m_dt * eps_dt
    t_per_pulse = m_dt * 3.01604928 / (2.01410178 + 3.01604928)
    n14_share = 14.07 / 17.589 * E_dt / yield_J
    esc14 = math.exp(-kappa_n14_cm2_g * (rhoR_total_g_cm2 - rhoR_DT_g_cm2))
    loaded = t_per_pulse * rate_Hz * burn_s
    return {'rhoR_DT_g_cm2': rhoR_DT_g_cm2, 'dt_mass_ug': m_dt * 1e9, 'dt_burn_fraction': b_dt, 'dt_yield_J': E_dt,
            'dt_share_of_yield': E_dt / yield_J, 'n14_share_of_yield': n14_share, 'n14_escape_probability': esc14,
            'n14_escaping_share': n14_share * esc14, 'tritium_per_pulse_ug': t_per_pulse * 1e9,
            'tritium_loaded_mission_kg': loaded, 'tritium_burned_mission_kg': loaded * b_dt,
            'tritium_decay_over_burn': 1 - 0.5 ** (burn_s / (tritium_half_life_y * 365.25 * 86400))}


# ----------------------------------------------------------------------------------------------------------------------------------
# tamper inertial confinement (not modelled by the Atlas liner study)
# ----------------------------------------------------------------------------------------------------------------------------------

def tamper_time_factor(mu, k):
    """Confinement-time multiplier of fuel pushing a thin tamper shell of mass mu (per kg fuel): the shell needs
    t ~ sqrt(M_t / (2 pi R P)) to move one radius, against R / c_s untamped; their ratio is sqrt(2 gamma mu / 3). k (0-1) is the share of
    that inertia that actually confines (tamper preheat, rarefaction, mix lower it). EXTRAPOLATION: thin-shell, constant-pressure push."""
    return 1 + k * math.sqrt(2 * GAMMA * mu / 3)


def tamped_burn_fraction(rhoR_kg_m2, H_B, mu, k):
    """b with the confinement time stretched by tamper_time_factor: equivalent to an effective rhoR x factor in b = rhoR/(rhoR + H_B)."""
    r = rhoR_kg_m2 * tamper_time_factor(mu, k)
    return r / (r + H_B)


# ----------------------------------------------------------------------------------------------------------------------------------
# the next target in flight
# ----------------------------------------------------------------------------------------------------------------------------------

def in_flight(yield_J, xray_escape, rate_Hz, standoff_m, v_inj_m_s, target_radius_m, plasma_share=0.98,
              he3_latent_J_kg=8.5e3, he3_mass_kg=None):
    """Targets travel from the shield muzzle (standoff_m forward of the burn) to the burn point at v_inj. The next target is
    d = v_inj / rate from the burn when a pulse fires. Fluence of escaping X-rays and of the expanding plasma at d, energy intercepted
    by the target's cross-section, and how many targets are in the burn's sky at once. He-3 latent heat about 8.5 kJ/kg near 1.5 K."""
    d = v_inj_m_s / rate_Hz
    in_sky = standoff_m / d
    area = math.pi * target_radius_m ** 2
    flu_x = yield_J * xray_escape / (4 * math.pi * d ** 2)
    flu_p = yield_J * plasma_share / (4 * math.pi * d ** 2)
    out = {'next_target_distance_m': d, 'targets_in_burn_sky': in_sky, 'xray_fluence_J_cm2': flu_x / 1e4, 'plasma_fluence_J_cm2': flu_p / 1e4,
           'xray_on_target_J': flu_x * area, 'plasma_on_target_J': flu_p * area,
           'v_needed_one_in_sky_km_s': standoff_m * rate_Hz / 1e3}
    if he3_mass_kg:
        out['he3_boil_off_J'] = he3_latent_J_kg * he3_mass_kg
    return out
