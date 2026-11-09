"""Feasibility gate Phase 3: can the gas-filled capsule (B-modified, B-ray) be the fusion target? (T00, research only, NON-CANON)

  python3 lab/variants/vertex-drive/studies/gate/target.py       # writes results/target.json (seconds)

Surviving the launch is not enough. This checks, with closed-form physics, what the capsule must do as a fusion target:
  1. compression: the energy to compress the fuel to FDP-1's density, against the driver energy and a hydrodynamic coupling
  2. ablator and beam: the range of FDP-1's 4 GeV heavy ions against the 34 um HDC wall (where the beam deposits)
  3. mix: how much wall carbon the D-3He burn tolerates (bremsstrahlung)
  4. exhaust mass: the wall leaves as exhaust, which FDP-1's optimiser does not carry
  5. fill and repetition: filling a cold diamond shell at the pulse rate
Each item gives the requirement, the value for the capsule and the unsupported assumption it rests on. No hydro or PIC code (D-21).
"""
import math

import gate_common as G

ME_C2 = 0.51099895e6       # eV
AMU_MEV = 931.494
K_BETHE = 0.307075         # MeV cm2 / mol
FUEL_D_MASS_FRACTION = 0.4 # equimolar D:3He by atoms (FDP-1 fuel)
WALL_G_V4 = 0.59           # Rev 4 B-modified HDC wall (34 um) for 0.772 g of fuel
RHO_GAS_30K = 0.0231       # g/cc, Rev 4 fill density (0.772 g in a 2 cm capsule)


def electrons_per_amu_fuel():
    w = FUEL_D_MASS_FRACTION
    return w / 2.0141 + (1 - w) * 2 / 3.0160


def fermi_specific_MJ_g(rho_g_cc, ne_per_amu):
    """Degenerate (alpha = 1) specific internal energy, scaled from DT: 2.17 Mbar rho^(5/3) at 0.3975 e/amu (Lindl 1995)."""
    P = 2.17e11 * rho_g_cc ** (5 / 3) * (ne_per_amu / 0.3975) ** (5 / 3)        # Pa
    return 1.5 * P / (rho_g_cc * 1e3) / 1e9                                       # MJ/g


def bethe_range_g_cm2(T_GeV, A=209, Z=83, Zt=6, At=12.011, I_eV=78.0, n=4000):
    """CSDA range of a heavy ion in a target (Bethe with the Barkas effective charge; no shell or density corrections).
    Default: Bi-209 (HIF reference; FDP-1 gives 4 GeV, not the species) in carbon."""
    E = T_GeV * 1e3            # MeV
    dE = E / n; R = 0.0
    for i in range(n):
        Ek = E - (i + 0.5) * dE
        g = 1 + Ek / (A * AMU_MEV); b2 = 1 - 1 / g ** 2; b = math.sqrt(b2)
        zeff = Z * (1 - math.exp(-125 * b * Z ** (-2 / 3)))
        L = math.log(2 * ME_C2 * b2 * g * g / I_eV) - b2
        S = K_BETHE * zeff ** 2 * Zt / At / b2 * max(L, 0.1)                      # MeV cm2/g
        R += dE / S
    return R


def brems_factor(f_C_per_fuel_ion):
    """Bremsstrahlung (n_e sum n_i Z_i^2) relative to clean equimolar D-3He, per carbon atom per fuel ion."""
    f = f_C_per_fuel_ion
    ne = 1.5 + 6 * f; z2 = 2.5 + 36 * f            # per fuel ion: D (Z 1) and 3He (Z 2) half each
    return ne * z2 / (1.5 * 2.5)


def main():
    ov = G.v4_overrides(); R = G.solve_full(ov)
    try:
        cp = G.read('coupled.json')
        ships = [('V4', R['fusion'])] + [(c['label'], c['fusion']) for c in cp['cases'] if c.get('fusion')]
    except FileNotFoundError:
        ships = [('V4', R['fusion'])]
    f = R['fusion']
    m_g = f['pellet_fuel_mass_g']; rhoR = f['fuel_rhoR_g_cm2']
    rho_c = ov['base']['overrides']['pulsed']['rho_g_cc']['optimistic']        # FDP-1 compressed fuel density, g/cc
    ne = electrons_per_amu_fuel()
    eps = fermi_specific_MJ_g(rho_c, ne)
    E_drv = f['driver_energy_per_pulse_J'] / 1e6
    comp = []
    for alpha in (1.0, 1.5, 2.0, 3.0):
        E_fuel = alpha * eps * m_g
        comp.append({'adiabat_alpha': alpha, 'fuel_energy_MJ': E_fuel, 'coupling_needed': E_fuel / E_drv,
                     'driver_needed_MJ_at_10pc': E_fuel / 0.10, 'driver_needed_MJ_at_20pc': E_fuel / 0.20})
    # what a consistent target would look like at 10-20 % coupling and alpha 1.5 (gas fill, optimistic)
    cons = []
    for eta in (0.10, 0.20):
        eps_ok = E_drv * eta / (1.5 * m_g)
        rho_ok = (eps_ok / fermi_specific_MJ_g(1.0, ne)) ** 1.5
        m_for_rhoR = 4 * math.pi / 3 * rhoR ** 3 / rho_ok ** 2
        cons.append({'coupling': eta, 'reachable_density_g_cc': rho_ok, 'fuel_g_for_FDP1_rhoR': m_for_rhoR,
                     'yield_GJ_at_FDP1_burn_fraction': m_for_rhoR / m_g * f['yield_per_pulse_J'] / 1e9})
    # 2. beam range against the wall
    rng = bethe_range_g_cm2(4.0)
    rng_fuel = bethe_range_g_cm2(4.0, Zt=ne, At=1.0, I_eV=30.0)
    wall_um = 34.0; rho_hdc = 3.5
    wall_areal = wall_um * 1e-4 * rho_hdc
    r_c = 2.0
    gas_areal = RHO_GAS_30K * 2 * r_c
    t_needed_um = rng / rho_hdc * 1e4
    m_abl = 4 * math.pi * r_c ** 2 * t_needed_um * 1e-4 * rho_hdc
    beam = {'ion': 'Bi-209 1+ at 4 GeV (FDP-1 energy; species ASSUMPTION)', 'range_in_carbon_g_cm2': rng,
            'range_in_D3He_g_cm2_approx': rng_fuel, 'wall_areal_g_cm2': wall_areal, 'wall_over_range': wall_areal / rng,
            'gas_areal_diameter_g_cm2': gas_areal, 'range_matched_HDC_um': t_needed_um, 'range_matched_ablator_g': m_abl,
            'finding': 'the 34 um wall is about a third of the ion range: two thirds of the beam energy deposits in the gas fuel itself, '
                       'preheating it (high adiabat). A range-matched direct-drive ablator is about 0.1 mm of HDC, several grams, '
                       'several times the fuel mass. Indirect drive (hohlraum) avoids this but its capsule supports hold about 200 g, not 30,000 g.'}
    # 3. mix tolerance
    mix = []
    for w in (0.005, 0.01, 0.02, 0.05, 0.10):
        fC = (w / 12.011) / ((1 - w) / 2.515)          # mean fuel-ion mass 2.515 amu
        mix.append({'carbon_mass_fraction_in_burn': w, 'C_atoms_per_fuel_ion': fC, 'bremsstrahlung_x': brems_factor(fC)})
    wall_over_fuel = WALL_G_V4 / 0.7721569150877443
    # 4. exhaust mass
    exh = {'wall_over_fuel': wall_over_fuel, 'fdp1_tamper_per_fuel': f['tamper_per_fuel'],
           've_factor_at_fixed_pulse_energy': 1 / math.sqrt(1 + wall_over_fuel),
           've_factor_range_matched_ablator': 1 / math.sqrt(1 + m_abl / m_g),
           'mass_ratio_V4_ln': math.log(G.C.fdp1.summary(R)['departure_t'] / G.C.fdp1.summary(R)['end_t']),
           'note': 'FDP-1 (IFD-PH) chooses a hydrogen tamper to set ve and picks about zero; an HDC wall is inert exhaust it does not carry. '
                   'At fixed pulse energy ve falls as 1/sqrt(1 + wall/fuel); the coupled solve here does not include it (it would need a '
                   'change to protected code or a ve adapter).'}
    exh['ln_mass_ratio_with_wall'] = exh['mass_ratio_V4_ln'] / exh['ve_factor_at_fixed_pulse_energy']
    exh['mass_ratio_with_wall'] = math.exp(exh['ln_mass_ratio_with_wall'])
    exh['departure_t_at_V4_end_mass_before_regearing'] = G.C.fdp1.summary(R)['end_t'] * exh['mass_ratio_with_wall']
    # 5. fill and repetition
    rates = sorted({round(s[1]['pellet_rate_Hz'], 1) for s in ships})
    fill = {'rates_Hz': rates, 'targets_per_mission_V4': f['pellet_rate_Hz'] * 5.685 * G.YEAR,
            'fill': 'HDC (diamond) is effectively impermeable to hydrogen isotopes and helium at 30 K and slow even at 300 K: NIF fills HDC '
                    'capsules through a fill tube. A cold gas capsule therefore needs a fill tube and a seal per target, at 196-330 per '
                    'second for 3.5e10 targets, kept below 30 K from fill to shot (the fill pressure scales with temperature and the wall is '
                    'sized for 30 K). No such process exists; it is an unsupported assumption.'}
    verdict = ('NOT DEFENSIBLE as a fusion target on FDP-1\'s numbers. Mechanically it survives (Rev 4), but: (1) compressing 0.77 g of '
               f'D-3He to {rho_c:.0f} g/cc costs {comp[0]["fuel_energy_MJ"]:.0f} MJ even at alpha 1, {comp[0]["coupling_needed"]:.0%} of the '
               f'{E_drv:.0f} MJ driver, and a gas start raises alpha; (2) the 4 GeV ions pass through the 34 um wall and preheat the gas; '
               '(3) the carbon wall is 0.76x the fuel mass while the burn tolerates about 1-2 % carbon by mass; (4) the wall is exhaust mass '
               'FDP-1 does not carry (ve x0.75); (5) there is no fill process at the pulse rate.')
    out = {'study': 'Feasibility gate Phase 3: gas-filled capsule as a fusion target (T00)', 'status': 'MODEL, research only, NON-CANON',
           'fdp1_target': {'fuel_g': m_g, 'rhoR_g_cm2': rhoR, 'compressed_density_g_cc': rho_c, 'driver_MJ': E_drv, 'gain': f['target_gain'],
                           'burn_fraction': f['burn_fraction'], 'electrons_per_amu': ne,
                           'radius_compressed_cm': rhoR / rho_c, 'fill_density_30K_g_cc': RHO_GAS_30K,
                           'convergence_gas': (rho_c / RHO_GAS_30K) ** (1 / 3), 'convergence_liquid_0.18': (rho_c / 0.18) ** (1 / 3)},
           'compression': {'specific_MJ_g_alpha1': eps, 'rows': comp, 'consistent_targets': cons,
                           'finding': 'the compression energy alone exceeds what a heavy-ion driver of this size can couple (10-20 %) even for '
                                      'liquid or solid fuel at alpha 1: this is a V4/FDP-1 target assumption (gain 1,084 at 168 MJ), upstream '
                                      'of the launcher; the gas fill makes it worse.'},
           'beam': beam, 'mix': {'rows': mix, 'wall_over_fuel': wall_over_fuel,
                                 'finding': 'D-3He burns near its bremsstrahlung limit: 2 % carbon by mass raises the radiation loss by about '
                                            f'{(brems_factor(mix[2]["C_atoms_per_fuel_ion"]) - 1) * 100:.0f} %, 5 % by about '
                                            f'{(brems_factor(mix[3]["C_atoms_per_fuel_ion"]) - 1) * 100:.0f} %. The wall must leave the burn region '
                                            'almost completely.'},
           'exhaust': exh, 'fill_and_rate': fill,
           'unsupported_assumptions': ['compression of a gas-start D-3He fuel to 2,000 g/cc at alpha near 1 (convergence 44)',
                                       'hydrodynamic coupling near 50 % (FDP-1 gain at 168 MJ)',
                                       'beam deposition in a wall thinner than the ion range without fuel preheat',
                                       'wall/fuel mix below about 2 % by mass with a 0.76 wall/fuel ratio',
                                       'a cold fill-and-seal process at 196-330 Hz for 3.5e10 targets',
                                       'inert wall mass leaving as exhaust without the ve penalty'],
           'verdict': verdict,
           'B_ray': 'same target, same verdict; B-ray changes only where the launcher sits (off the axis channel), not the target physics'}
    G.write('target.json', out)
    print(verdict)
    print('compression', [(r['adiabat_alpha'], round(r['fuel_energy_MJ']), round(r['coupling_needed'], 2)) for r in comp])
    print('consistent', cons)
    print('beam', {k: v for k, v in beam.items() if k != 'finding'})
    print('mix', [(r['carbon_mass_fraction_in_burn'], round(r['bremsstrahlung_x'], 3)) for r in mix])
    print('exhaust', exh)


if __name__ == '__main__':
    main()
