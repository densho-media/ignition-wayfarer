"""Gate 2 Task B: fusion-target feasibility, independent check and operating map (T00, research only, NON-CANON).

  python3 lab/variants/vertex-drive/studies/gate2/target2.py      # writes results/target2.json (about a minute)

Closed-form physics only (no hydro code). Each block states its approximation; constants are CODATA, reactivities Bosch-Hale 1992
(re-implemented here and compared with the four-burn engine's copy), stopping on electrons from the Spitzer slowing-down time.
  1. compression energy: the gate's Lindl scaling against a first-principles degenerate electron gas (with the relativistic,
     exchange and ion-lattice corrections), and E(rho, alpha) maps
  2. the density the ship asks for: rho follows from FDP-1's fuel mass and rhoR, rhoR from its burn fraction and H_B (checked)
  3. ignition: ideal ignition temperature (charged heating = bremsstrahlung), product ranges, and a 0D hot-spot power balance
     (charged deposition >= bremsstrahlung + expansion work) giving the minimum hot-spot rhoR, validated on D-T
  4. hot-spot energy for central (isobaric) and fast (isochoric) ignition; D-T-assisted ignition and its tritium bill
  5. operating map: driver energy = compression / eta_c + ignition / eta_ig for the ship's yield, over rhoR, alpha and eta_c, with
     the gain each gives against FDP-1's gain input (1,084 in V4), and what lower gains do to FDP-1's departure mass
  6. inert target mass and exhaust velocity
"""
import math
import time

import g2
G = g2.G

KB_KEV = 1.602176634e-16    # J per keV
AMU = 1.66053906660e-27
ME = 9.1093837015e-31
HBAR = 1.054571817e-34
C0 = 2.99792458e8
EPS0 = 8.8541878128e-12
QE = 1.602176634e-19
MEV = 1.602176634e-13

BH = {'DT': (34.3827, 1124656, 1.17302e-9, 1.51361e-2, 7.51886e-2, 4.60643e-3, 1.35e-2, -1.0675e-4, 1.366e-5),
      'DHe3': (68.7508, 1124572, 5.51036e-10, 6.41918e-3, -2.02896e-3, -1.91080e-5, 1.35776e-4, 0.0, 0.0)}

# fuels: per amu of fuel: electrons, ions, mean Z^2 per ion; products
FUEL = {'DHe3': {'m_ion_amu': (2.01410 + 3.01603) / 2, 'Z': (1, 2), 'Q_MeV': 18.35, 'charged': [('alpha', 4.0026, 2, 3.6), ('proton', 1.00728, 1, 14.7)],
                 'neutral_MeV': 0.0},
        'DT': {'m_ion_amu': (2.01410 + 3.01605) / 2, 'Z': (1, 1), 'Q_MeV': 17.59, 'charged': [('alpha', 4.0026, 2, 3.5)], 'neutral_MeV': 14.1}}


def sigv(r, T):
    BG, mrc2, c1, c2, c3, c4, c5, c6, c7 = BH[r]
    th = T / (1 - T * (c2 + T * (c4 + T * c6)) / (1 + T * (c3 + T * (c5 + T * c7))))
    xi = (BG ** 2 / (4 * th)) ** (1 / 3)
    return c1 * th * math.sqrt(xi / (mrc2 * T ** 3)) * math.exp(-3 * xi) * 1e-6        # m3/s


def per_amu(f):
    F = FUEL[f]; z1, z2 = F['Z']; m = F['m_ion_amu']
    ions = 1 / m; ne = ions * (z1 + z2) / 2; z2m = (z1 ** 2 + z2 ** 2) / 2
    return {'ions': ions, 'electrons': ne, 'Z2_mean': z2m, 'Zbar': (z1 + z2) / 2}


# --------------------------------------------------------------------------------------------------------------- 1. compression
def fermi_first_principles(rho_g_cc, ne_amu, Z=1.5):
    """Specific energy (MJ/g) of the T = 0 electron gas: kinetic (exact relativistic Fermi gas), exchange and the ion lattice
    (Wigner-Seitz -0.9 Z^2 e^2/a per ion), all from first principles. Also returns the non-relativistic kinetic term alone."""
    n = rho_g_cc * 1e3 / AMU * ne_amu                         # electrons per m3
    kF = (3 * math.pi ** 2 * n) ** (1 / 3); x = HBAR * kF / (ME * C0)
    # exact T=0 relativistic kinetic energy density
    eps = ME ** 4 * C0 ** 5 / (8 * math.pi ** 2 * HBAR ** 3) * (x * (2 * x * x + 1) * math.sqrt(1 + x * x) - math.asinh(x)) - n * ME * C0 ** 2
    ekin_nr = 0.6 * (HBAR * kF) ** 2 / (2 * ME) * n
    exch = -0.75 * (3 / math.pi) ** (1 / 3) * QE ** 2 / (4 * math.pi * EPS0) * n ** (4 / 3)
    ni = n / Z; a = (3 / (4 * math.pi * ni)) ** (1 / 3)
    latt = -0.9 * Z ** 2 * QE ** 2 / (4 * math.pi * EPS0 * a) * ni
    per_g = lambda e: e / (rho_g_cc * 1e6) / 1e6               # J/m3 -> MJ/g
    return {'x_rel': x, 'E_F_keV': (math.sqrt(1 + x * x) - 1) * ME * C0 ** 2 / KB_KEV, 'kinetic_MJ_g': per_g(eps), 'kinetic_nonrel_MJ_g': per_g(ekin_nr),
            'exchange_MJ_g': per_g(exch), 'lattice_MJ_g': per_g(latt), 'total_MJ_g': per_g(eps + exch + latt),
            'P_F_Pa': 2 / 3 * ekin_nr}


def lindl(rho, ne_amu):
    P = 2.17e11 * rho ** (5 / 3) * (ne_amu / 0.3975) ** (5 / 3)
    return 1.5 * P / (rho * 1e3) / 1e9


# --------------------------------------------------------------------------------------------------------------- 3. ignition
def coulomb_log(ne, T):
    return max(5.0, 24.0 - math.log(math.sqrt(ne * 1e-6) / (T * 1e3)))     # electron, NRL (T in keV)


def range_g_cm2(f, prod, T, rho_g_cc):
    """CSDA range (g/cm2) of a fusion product slowing on electrons (v << v_te): R = v0 tau_s (Spitzer), plus the ion drag as a
    harmonic correction (energy share to ions ~ (E_crit / E)^(3/2), approximate)."""
    _, A, Zp, E = prod
    pa = per_amu(f)
    ne = rho_g_cc * 1e3 / AMU * pa['electrons']
    lnL = coulomb_log(ne, T)
    tau_s = 6.27e8 * A * (T * 1e3) ** 1.5 / (Zp ** 2 * (ne * 1e-6) * lnL)            # s (NRL, ne in cm^-3, T in eV)
    v0 = math.sqrt(2 * E * MEV / (A * AMU))
    R_e = v0 * tau_s * 100 * rho_g_cc                                               # g/cm2
    Ec = 14.8 * A * T * (pa['Z2_mean'] / FUEL[f]['m_ion_amu']) ** (2 / 3) / 1e3      # MeV (critical energy, ion share 50 % at E_c)
    return R_e / (1 + (Ec / E) ** 1.5), Ec


def deposit(f, rhoR, T, rho):
    tot = 0.0; Qc = sum(p[3] for p in FUEL[f]['charged'])
    for p in FUEL[f]['charged']:
        Rr, _ = range_g_cm2(f, p, T, rho)
        x = rhoR / Rr
        tot += p[3] * (1.0 if x >= 1 else x * (1 - 0.25 * x))          # uniform sphere, straight paths (approximate escape fraction)
    return tot / Qc


def power_terms(f, T, rho_g_cc):
    """Per unit mass (W/kg) at T (keV), density rho: fusion charged heating (fully deposited), bremsstrahlung, and the pressure p/rho."""
    pa = per_amu(f); rho = rho_g_cc * 1e3
    ni = rho / AMU * pa['ions']; ne = rho / AMU * pa['electrons']
    sv = sigv(f, T)
    nr = (ni / 2) * (ni / 2) * sv                                                  # equimolar: n_1 n_2 <sv>
    Pch = nr * sum(p[3] for p in FUEL[f]['charged']) * MEV
    Zeff = pa['Z2_mean'] / pa['Zbar']
    x = T / 511.0
    Pb = 5.35e-37 * ne * ne * Zeff * math.sqrt(T) * (1 + 0.7936 * x + 1.874 * x * x) + 5.35e-37 * ne * ne * math.sqrt(T) * 3 / math.sqrt(2) * x
    p = (ni + ne) * T * KB_KEV
    return Pch / rho, Pb / rho, p / rho


def ideal_ignition_T(f):
    lo = None
    for i in range(1, 4000):
        T = 0.1 * i
        a, b, _ = power_terms(f, T, 100.0)
        if a > b:
            lo = T; break
    return lo


def hotspot_min_rhoR(f, rho_hs):
    """Smallest hot-spot rhoR (g/cm2) for which charged deposition exceeds bremsstrahlung + expansion work (3 p c_s / R) at the best T."""
    best = (math.inf, None)
    for T in [1.0 * 1.03 ** k for k in range(0, 200) if 1.0 * 1.03 ** k < 400]:
        a, b, pr = power_terms(f, T, rho_hs)
        pa = per_amu(f)
        cs = math.sqrt((1 + pa['Zbar']) * T * KB_KEV / (FUEL[f]['m_ion_amu'] * AMU))
        for k in range(0, 400):
            rR = 0.01 * 1.04 ** k                                  # g/cm2
            dep = deposit(f, rR, T, rho_hs)
            R_m = rR / rho_hs / 100
            if a * dep > b + 3 * pr * cs / R_m:
                if rR < best[0]:
                    best = (rR, T)
                break
    return {'rhoR_g_cm2': best[0], 'T_keV': best[1], 'rho_hs_g_cc': rho_hs}


def spec_energy_MJ_g(f, T):
    pa = per_amu(f)
    return 1.5 * (pa['ions'] + pa['electrons']) / AMU * T * KB_KEV / 1e9


# --------------------------------------------------------------------------------------------------------------------- main
def main():
    t0 = time.time()
    ov = G.v4_overrides(); R = G.solve_full(ov); f = R['fusion']
    p = ov['base']['overrides']['pulsed']
    m_g, rhoR, b = f['pellet_fuel_mass_g'], f['fuel_rhoR_g_cm2'], f['burn_fraction']
    Y = f['yield_per_pulse_J']; E_drv = f['driver_energy_per_pulse_J']; rho_c = p['rho_g_cc']['optimistic']
    pa = per_amu('DHe3')
    out = {'study': 'Gate 2 Task B: fusion-target feasibility (T00)', 'status': 'MODEL, research only, NON-CANON (closed-form physics)'}
    # cross-check reactivities against the four-burn engine copy and Bosch-Hale table values
    import importlib.util, sys
    sys.path.insert(0, str(G.HERE.parents[3] / 'studies' / 'four-burn-mission'))
    from fourburn import plasma as PL
    out['reactivity_check'] = {'DT_10keV_m3_s': sigv('DT', 10.0), 'DT_10keV_BoschHale_table': 1.136e-22, 'DT_20keV': sigv('DT', 20.0),
                               'DT_20keV_table': 4.330e-22, 'DHe3_vs_fourburn_max_rel_diff': max(abs(sigv('DHe3', T) / PL.sigv('DHe3', T) - 1)
                                                                                                 for T in (10, 30, 60, 100, 150))}
    # 1. compression
    fp = fermi_first_principles(rho_c, pa['electrons'])
    E_l = lindl(rho_c, pa['electrons'])
    out['compression'] = {
        'fdp1': {'fuel_g': m_g, 'rhoR_g_cm2': rhoR, 'rho_g_cc': rho_c, 'burn_fraction': b, 'yield_GJ': Y / 1e9, 'driver_MJ': E_drv / 1e6,
                 'gain': f['target_gain'], 'electrons_per_amu': pa['electrons']},
        'first_principles_at_fdp1_density': fp, 'gate_lindl_MJ_g': E_l, 'lindl_over_first_principles_kinetic': E_l / fp['kinetic_MJ_g'],
        'ideal_E_MJ_alpha1': fp['kinetic_MJ_g'] * m_g, 'ideal_E_MJ_alpha1_with_corrections': fp['total_MJ_g'] * m_g,
        'map_MJ': {f'{r:g} g/cc': {f'alpha {a:g}': a * fermi_first_principles(r, pa['electrons'])['kinetic_MJ_g'] * m_g for a in (1, 1.5, 2, 3)}
                   for r in (100, 300, 1000, 2000, 3000)},
        'notes': ['alpha = pressure / Fermi pressure at the same density (cold-fuel adiabat); NIF-class implosions run alpha 1.5-3',
                  'a finite temperature adds 3/2 n_i kT for the ions (ions are not degenerate) and raises the electron term; '
                  'both are inside alpha here',
                  'the gate value (Lindl DT scaling by electrons per amu^(5/3)) agrees with the first-principles electron gas within the '
                  'percentage given; exchange and lattice terms lower it by a few per cent']}
    # 2. why 2,000 g/cc: rho from m and rhoR; rhoR from b and H_B
    H_B = rhoR * (1 - b) / b
    out['density_chain'] = {'H_B_implied_g_cm2': H_B, 'rho_from_m_and_rhoR': (rhoR ** 1.5) / math.sqrt(3 * m_g / (4 * math.pi)),
                            'burn_T_keV_fdp1': p.get('burn_T_keV', {}).get('value') if isinstance(p.get('burn_T_keV'), dict) else None,
                            'H_B_fourburn_at_T': {f'{T}': PL.burn_parameter_kg_m2(T) / 10 for T in (40, 60, 80, 100, 150)},
                            'note': 'E_comp = alpha K rho^(2/3) m and rho^(2/3) = rhoR (4 pi / 3 m)^(1/3): at fixed rhoR the compression energy '
                                    'grows as m^(2/3) while the yield grows as m, so gain rises only as m^(1/3)'}
    # 3. ignition
    ign = {}
    for fu in ('DT', 'DHe3'):
        Ti = ideal_ignition_T(fu)
        ign[fu] = {'ideal_ignition_T_keV': Ti,
                   'ranges_g_cm2_at': {f'{T} keV, {r} g/cc': {pr[0]: range_g_cm2(fu, pr, T, r)[0] for pr in FUEL[fu]['charged']}
                                       for T, r in ((10, 100), (30, 100), (60, 30), (60, 2000), (100, 2000))},
                   'hotspot_min': {f'{r} g/cc': hotspot_min_rhoR(fu, r) for r in (30.0, 100.0, 300.0, 2000.0)}}
        print(fu, Ti, ign[fu]['hotspot_min'], f'[{time.time() - t0:.0f} s]', flush=True)
    out['ignition'] = ign
    # 4. hot-spot energy
    P_cold = lambda r, a: a * fermi_first_principles(r, pa['electrons'])['P_F_Pa']
    hs = []
    for fu, H, T in (('DHe3', ign['DHe3']['hotspot_min']['2000.0 g/cc']['rhoR_g_cm2'], ign['DHe3']['hotspot_min']['2000.0 g/cc']['T_keV']),):
        for rho_f in (300.0, 1000.0, 2000.0):
            for a in (1.0, 2.0):
                pf = P_cold(rho_f, a); pp = per_amu(fu)
                rho_hs = pf / ((pp['ions'] + pp['electrons']) / AMU * T * KB_KEV) / 1e3      # isobaric
                Hn = hotspot_min_rhoR(fu, rho_hs)['rhoR_g_cm2']
                m_iso = 4 * math.pi / 3 * Hn ** 3 / rho_hs ** 2
                m_fi = 4 * math.pi / 3 * H ** 3 / rho_f ** 2
                cs = math.sqrt((1 + pp['Zbar']) * T * KB_KEV / (FUEL[fu]['m_ion_amu'] * AMU))
                R_fi = H / rho_f / 100
                hs.append({'fuel_density_g_cc': rho_f, 'alpha': a, 'T_keV': T,
                           'central_isobaric': {'hotspot_density_g_cc': rho_hs, 'hotspot_rhoR_g_cm2': Hn, 'hotspot_g': m_iso,
                                                'hotspot_MJ': m_iso * spec_energy_MJ_g(fu, T), 'hotspot_radius_cm': Hn / rho_hs,
                                                'fuel_radius_cm_at_fdp1_mass': (3 * m_g / (4 * math.pi * rho_f)) ** (1 / 3)},
                           'fast_isochoric': {'hotspot_rhoR_g_cm2': H, 'hotspot_g': m_fi, 'ignitor_MJ_deposited': m_fi * spec_energy_MJ_g(fu, T),
                                              'radius_um': R_fi * 1e6, 'confinement_ps': R_fi / cs * 1e12,
                                              'ignitor_power_W': m_fi * spec_energy_MJ_g(fu, T) * 1e6 / (R_fi / cs)}})
    # D-T assisted: a D-T spark (fast) whose burn must heat a D-3He hot spot of the size above
    dt = ign['DT']['hotspot_min']['2000.0 g/cc']
    E_he_hs = next(h for h in hs if h['fuel_density_g_cc'] == 2000.0 and h['alpha'] == 1.0)['fast_isochoric']['ignitor_MJ_deposited']
    Y_dt = E_he_hs * 1e6 / (3.5 / 17.59)               # J; only the alpha share of D-T deposits, the 14.1 MeV neutrons leave
    m_T = Y_dt / (17.59 * MEV) * 3.016 * AMU / 0.3     # kg tritium, 30 % burn-up of the D-T seed
    pulses = f['pellet_rate_Hz'] * 5.685 * G.YEAR
    out['hotspot'] = {'rows': hs, 'DT_assisted': {'DT_spark_min': dt, 'DHe3_hotspot_MJ_to_heat': E_he_hs, 'DT_yield_needed_MJ': Y_dt / 1e6,
                                                  'tritium_mg_per_pulse': m_T * 1e6, 'tritium_t_per_mission': m_T * pulses / 1e3,
                                                  'neutron_W_added': Y_dt * 14.1 / 17.59 * f['pellet_rate_Hz'],
                                                  'neutron_W_V4': f['neutron_escape_fraction'] * f['gross_fusion_power_W'],
                                                  'note': 'tritium decays (12.3 y) and the world inventory is tens of kg; on-board breeding needs a lithium '
                                                          'blanket in a 14 MeV neutron flux, which is the opposite of the D-3He premise'}}
    # 5. operating map
    Qsp = FUEL['DHe3']['Q_MeV'] * MEV / (5.03013 * AMU) * 1e-3          # J/g at full burn
    E_fi = lambda rho: 4 * math.pi / 3 * ign['DHe3']['hotspot_min']['2000.0 g/cc']['rhoR_g_cm2'] ** 3 / rho ** 2 * spec_energy_MJ_g('DHe3', ign['DHe3']['hotspot_min']['2000.0 g/cc']['T_keV'])
    rows = []
    for rr in (10.0, 20.0, 40.0, 90.34):
        bf = rr / (rr + H_B)
        m = Y / (bf * Qsp)
        rho = rr ** 1.5 / math.sqrt(3 * m / (4 * math.pi))
        e = fermi_first_principles(rho, pa['electrons'])['kinetic_MJ_g']
        for a in (1.0, 1.5, 2.0):
            for ec in (0.05, 0.10, 0.15, 0.20):
                Ec = a * e * m
                for eig in (0.1, 0.3):
                    Ed = Ec / ec + E_fi(rho) / eig
                    rows.append({'rhoR_g_cm2': rr, 'burn_fraction': bf, 'fuel_g': m, 'rho_g_cc': rho, 'alpha': a, 'eta_c': ec, 'eta_ig': eig,
                                 'compression_MJ': Ec, 'ignitor_MJ_deposited': E_fi(rho), 'driver_MJ': Ed, 'gain': Y / (Ed * 1e6),
                                 'meets_fdp1_gain': Y / (Ed * 1e6) >= f['target_gain'], 'unburned_He3_g': m * (1 - bf) * 0.6})
    best = max(rows, key=lambda r: r['gain'])
    plaus = [r for r in rows if r['eta_c'] <= 0.15 and r['alpha'] >= 1.5]
    out['operating_map'] = {'yield_GJ': Y / 1e9, 'fdp1_gain': f['target_gain'], 'rows': rows, 'best_any': best,
                            'best_plausible_eta_c_le_0.15_alpha_ge_1.5': max(plaus, key=lambda r: r['gain']),
                            'eta_c_literature_note': 'driver-to-fuel coupling: NIF indirect drive is about 1 % laser-to-fuel; direct-drive '
                                                     'rocket (hydrodynamic) efficiency 5-15 %; heavy-ion direct-drive designs quote 10-20 %. '
                                                     'These are literature ranges, not computed here.'}
    # gain sensitivity of FDP-1 (V4, no coupled extras): the ship the target physics would actually support
    gs = []
    for Gn in (1084.33, 600.0, 300.0, 150.0, 75.0):
        Rg = G.C.fdp1.solve('baseline', G.core(G.C.P(ov, **{'base.overrides.pulsed.gain.optimistic': Gn})))
        s = G.C.fdp1.summary(Rg) if Rg.get('converged') else None
        gs.append({'gain': Gn, 'converged': bool(Rg.get('converged')), 'departure_t': s['departure_t'] if s else None,
                   'driver_MJ': Rg['fusion']['driver_energy_per_pulse_J'] / 1e6 if s else None,
                   'rate_Hz': Rg['fusion']['pellet_rate_Hz'] if s else None, 'reason': None if s else str(Rg.get('reason'))[:200]})
        print('gain', Gn, gs[-1], flush=True)
    lo, hi = 600.0, 1084.33
    for _ in range(10):
        mid = 0.5 * (lo + hi)
        Rg = G.C.fdp1.solve('baseline', G.core(G.C.P(ov, **{'base.overrides.pulsed.gain.optimistic': mid})))
        lo, hi = (lo, mid) if Rg.get('converged') else (mid, hi)
    out['gain_sensitivity_fdp1_V4'] = {'rows': gs, 'closure_threshold_gain': hi,
                                       'note': 'FDP-1 V4 alone (no coupled extras); departure mass rises steeply toward the threshold (83 kt at 842, '
                                               '1.4 Mt at 703); the coupled extras raise the threshold'}
    Ec1 = out['compression']['ideal_E_MJ_alpha1'] * 1e6
    out['coupling_needed_for_closure'] = {f'alpha {a:g}': hi * a * Ec1 / Y for a in (1.0, 1.5, 2.0)}
    out['coupling_needed_for_closure']['note'] = ('eta_c = G_threshold x alpha x E_comp / yield with a free ignitor: the smallest driver-to-fuel '
                                                  'coupling at which this target could close the V4 ship at all')
    # 6. inert mass
    out['inert_mass'] = {'ve_factor': {f'{x:g}': 1 / math.sqrt(1 + x) for x in (0.0, 0.1, 0.3, 0.76, 2.6)},
                         'ln_MR_V4': math.log(G.C.fdp1.summary(R)['departure_t'] / G.C.fdp1.summary(R)['end_t']),
                         'note': 'at fixed pulse energy an inert mass x times the fuel lowers ve by 1/sqrt(1+x); ln(mass ratio) grows by the inverse. '
                                 'x 0.76 is the Rev 4 HDC wall, x 2.6 a range-matched 0.12 mm HDC ablator (gate target.py)'}
    out['runtime_s'] = time.time() - t0
    g2.write('target2.json', out)
    c = out['compression']
    print('compression', round(c['ideal_E_MJ_alpha1'], 1), round(c['ideal_E_MJ_alpha1_with_corrections'], 1), 'lindl/fp', round(c['lindl_over_first_principles_kinetic'], 4))
    print('best', {k: best[k] for k in ('rhoR_g_cm2', 'alpha', 'eta_c', 'eta_ig', 'driver_MJ', 'gain')})


if __name__ == '__main__':
    main()
