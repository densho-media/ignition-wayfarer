"""Revision 4 §5: pulsed-radiation durability of the shield face, snout tip and coil armour (ISS-016/017; T00, research only, NON-CANON).

  python3 lab/variants/vertex-drive/studies/rev4/durability.py      # writes results/durability.json (seconds)

Inputs: per-pulse X-ray fluence 4.0 J/cm2 (shield face and closure-coil armour, both about 64.7 m from the burn), 8.3 J/cm2 (launcher B
snout tip, 45 m); 196 Hz, so 7.8 and 16.2 MW/m2 steady. The plasma temperature does not set the escaping spectrum: the V4 fuel is Compton-
thick (tau about 20 at rho R 90 g/cm2, Z/A 0.6), so photons random-walk out, down-scattered and re-emitted near the surface. The spectrum
is therefore carried as bands from soft (Planck 1 keV, a disassembling surface) to hard (unfiltered 50 keV bremsstrahlung, an upper bound
on hardness). Deposition uses xraylib mass energy-absorption coefficients (data/xray_attenuation.json); the surface temperature rise is
averaged over the thermal diffusion length of a 1 ns pulse. Material properties are handbook values at the stated base temperature.
"""
import math

from common import attenuation, solve_full, v4_overrides, write_json, YEAR, C

TAU_PULSE = 1e-9                       # PROTOTYPE X-ray pulse length (burn plus disassembly, 0.1-1 ns)
ALLOW_EROSION_M = 1e-3                 # PROTOTYPE erosion allowance of a cartridge face
COND_DT = 300.0                        # PROTOTYPE allowed conduction drop through the armour at the steady flux

# rho kg/m3, c J/kgK, k W/mK, alpha 1/K, E Pa, nu, strength Pa, ductile?, T_base K, T_limit K (melt / sublimation / decomposition),
# h_loss J/kg (latent heats from the base state to vapour), mixture by mass (xraylib elements)
MAT = {
    'W': dict(rho=19300, c=160, k=100, a=4.6e-6, E=380e9, nu=0.28, s=0.2e9, ductile=True, Tb=1500, Tl=3695, L=0.19e6 + 4.48e6, mix={'W': 1.0}),
    'C (CFC)': dict(rho=1850, c=1900, k=150, a=1.0e-6, E=50e9, nu=0.2, s=0.15e9, ductile=False, Tb=1500, Tl=3900, L=59.6e6, mix={'C': 1.0}),
    'Be': dict(rho=1850, c=2600, k=120, a=15e-6, E=287e9, nu=0.1, s=0.15e9, ductile=True, Tb=700, Tl=1560, L=1.36e6 + 32.6e6, mix={'Be': 1.0}),
    'SiC': dict(rho=3210, c=1200, k=60, a=4.5e-6, E=400e9, nu=0.2, s=0.35e9, ductile=False, Tb=1300, Tl=2800, L=18e6, mix={'Si': 0.7, 'C': 0.3}),
    'Mo': dict(rho=10220, c=300, k=100, a=5.5e-6, E=300e9, nu=0.3, s=0.2e9, ductile=True, Tb=1500, Tl=2896, L=0.39e6 + 6.2e6, mix={'Mo': 1.0}),
    'Sn film (liquid, renewable)': dict(rho=6400, c=250, k=60, a=0, E=0, nu=0, s=0, ductile=None, Tb=1200, Tl=2875, L=2.5e6, mix={'Sn': 1.0}),
    'Li film (liquid, renewable)': dict(rho=480, c=4200, k=50, a=0, E=0, nu=0, s=0, ductile=None, Tb=800, Tl=1615, L=19.6e6, mix={'Li': 1.0}),
}
BANDS = {'Planck 1 keV (soft surface)': ('planck', 1.0), 'Planck 3 keV': ('planck', 3.0), 'Wien 10 keV (Comptonised)': ('wien', 10.0),
         'Wien 30 keV': ('wien', 30.0), 'bremsstrahlung 50 keV with its soft tail (unfiltered)': ('brems', 50.0),
         'bremsstrahlung 50 keV above 5 keV (hard bound)': ('brems_f', 50.0)}
SURFACES = {'shield face and coil armour': 4.0, 'snout tip (launcher B)': 8.3}


def spectrum(kind, kT, E):
    x = E / kT
    if kind == 'planck':
        return E ** 3 / math.expm1(x) if x < 700 else 0.0
    if kind == 'wien':
        return E ** 3 * math.exp(-x)
    if kind == 'brems_f' and E < 5.0:
        return 0.0
    return math.exp(-x)


def mu(table, key, el, E):
    """log-log interpolation of a mass coefficient (cm2/g) at E keV; below 1 keV the 1 keV value (underestimates deposition)."""
    pts = [(e, y) for e, y in zip(table['energies_keV'], table[key][el]) if y]
    Es = [e for e, _ in pts]; ys = [y for _, y in pts]
    if E <= Es[0]:
        return ys[0]
    for i in range(len(Es) - 1):
        if Es[i] <= E <= Es[i + 1]:
            f = math.log(E / Es[i]) / math.log(Es[i + 1] / Es[i])
            return math.exp(math.log(ys[i]) + f * (math.log(ys[i + 1]) - math.log(ys[i])))
    return ys[-1]


def deposition(table, m, kind, kT, F_J_cm2):
    """Energy (J/m3) deposited at depths x, and the cumulative energy (J/m2) above x."""
    Es = [0.25 * 1.03 ** i for i in range(260) if 0.25 * 1.03 ** i <= 1000.0]
    w = [spectrum(kind, kT, E) * E * 0.03 for E in Es]           # energy per log bin
    W = sum(w); w = [x / W for x in w]
    F = F_J_cm2 * 1e4
    coef = []
    for E, wi in zip(Es, w):
        mt = sum(fr * mu(table, 'mu_rho', el, E) for el, fr in m['mix'].items()) * 0.1        # m2/kg
        me = sum(fr * mu(table, 'mu_en_rho', el, E) for el, fr in m['mix'].items()) * 0.1
        coef.append((wi, mt * m['rho'], me * m['rho']))

    def q(x):
        return F * sum(wi * me * math.exp(-mt * x) for wi, mt, me in coef)

    def cum(x):                                                  # energy deposited between 0 and x (J/m2), en-weighted
        return F * sum(wi * (me / mt) * (1 - math.exp(-mt * x)) for wi, mt, me in coef)
    mean_depth = sum(wi / mt for wi, mt, _ in coef)
    return q, cum, mean_depth


def assess(table, name, m, band, F):
    kind, kT = BANDS[band]
    q, cum, depth = deposition(table, m, kind, kT, F)
    alpha = m['k'] / (m['rho'] * m['c'])
    Ld = math.sqrt(alpha * TAU_PULSE)
    dT = cum(Ld) / (m['rho'] * m['c'] * Ld)                      # surface rise averaged over the diffusion length
    peak = m['Tb'] + dT
    h_v = m['c'] * (m['Tl'] - m['Tb']) + m['L']                  # J/kg to remove the surface as vapour (melt + vaporise)
    # eroded depth per pulse: where the local deposit exceeds the vaporisation enthalpy (bisection on depth)
    lo, hi = 0.0, 1e-2
    if q(0.0) / m['rho'] <= h_v:
        eroded = 0.0
    else:
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            lo, hi = (mid, hi) if q(mid) / m['rho'] > h_v else (lo, mid)
        eroded = lo
    melt = peak >= m['Tl'] if not m['ductile'] is None else False
    out = {'material': name, 'band': band, 'fluence_J_cm2': F, 'mean_absorption_depth_um': depth * 1e6, 'diffusion_um': Ld * 1e6,
           'surface_dT_K': dT, 'peak_K': peak, 'limit_K': m['Tl'], 'eroded_nm_per_pulse': eroded * 1e9}
    if m['ductile'] is None:                                     # liquid film: vaporisation loss only
        out['verdict'] = 'OK (film below boiling)' if peak < m['Tl'] else 'VAPOUR LOSS (renew)'
        out['film_loss_m_per_s_at_196Hz'] = eroded * 196.0
        return out
    stress = m['E'] * m['a'] * dT / (1 - m['nu'])
    lim_dT = (2 if m['ductile'] else 1) * m['s'] * (1 - m['nu']) / (m['E'] * m['a'])
    out.update({'thermal_stress_MPa': stress / 1e6, 'elastic_dT_limit_K': lim_dT})
    if eroded > 0 or peak >= m['Tl']:
        out['verdict'] = 'ABLATES / MELTS'
        rate = eroded * 196.0
        out['mission_erosion_m'] = eroded * 196.0 * 5.685 * YEAR
        out['replace_interval_s'] = ALLOW_EROSION_M / rate if rate else 0.0
    elif dT <= lim_dT:
        out['verdict'] = 'OK (elastic, below shakedown)' if m['ductile'] else 'OK (below fracture)'
    else:
        if m['ductile']:
            de = (stress - 2 * m['s']) / m['E']                 # plastic strain range per cycle
            N = 0.5 * (de / 0.3) ** (-1 / 0.6)                  # Coffin-Manson, eps_f' 0.3, c -0.6 (EXTRAPOLATION)
            out['verdict'] = 'FATIGUE (cartridge)'
            out['cycles_to_crack'] = N; out['replace_interval_s'] = N / 196.0
        else:
            out['verdict'] = 'CRACKS (brittle)'
            out['replace_interval_s'] = 0.0
    return out


def plasma_on_axis(R4):
    """Plasma flux on anything inside the unstopped axis channel: the raw isotropic pulse, not reduced by the field."""
    f = R4['fusion']; d = f['xray_standoff_m']
    Ep = f['yield_per_pulse_J'] * (1 - f['xray_escape_fraction'] - f['neutron_escape_fraction'])
    J_cm2 = Ep / (4 * math.pi * (d * 100) ** 2)
    cone = (1 - math.cos(math.radians(R4['shield']['hardware_half_angle_deg']))) / 2
    v = 21.6e6 * math.sqrt(f['yield_per_pulse_J'] / 80.99e9) ** 0                # rms speed (T03 V1 pulse; V4 same specific energy)
    return {'raw_pulse_J_cm2_at_shield': J_cm2, 'raw_MW_m2': J_cm2 * 1e4 * f['pellet_rate_Hz'] / 1e6,
            'geometric_share_in_shield_cone': cone, 'T03_shield_strike_share': 0.003195,
            'ion_energy_MeV_per_u': 0.5 * 1.6605e-27 * v ** 2 / 1.602e-13,
            'W_range_um_order': 10.0,
            'dT_in_10um_W_K': J_cm2 * 1e4 / (19300 * 160 * 1e-5),
            'finding': 'An axisymmetric field is purely axial on the axis, so plasma moving along the axis forward is not reflected (T03 has no '
                       'stopping radius at polar 0). Anything inside that channel (shield face centre, snout tip, shutter) receives the raw '
                       'pulse: about 350 J/cm2 of MeV/u ions per pulse. No solid survives this; it needs an axis plug (a sacrificial or '
                       'renewable stagnation target, or a non-axisymmetric field), and the 0.23-0.32 % of plasma it stops must be booked as '
                       'hardware heat (FDP-1 already books it in plume_to_hardware).'}


def main():
    table = attenuation()
    R4 = solve_full(v4_overrides())
    rows = [assess(table, n, m, b, F) for sname, F in SURFACES.items() for n, m in MAT.items() for b in BANDS]
    for r in rows:
        r['surface'] = next(s for s, F in SURFACES.items() if F == r['fluence_J_cm2'])
    rate = R4['fusion']['pellet_rate_Hz']
    cool = {}
    for sname, F in SURFACES.items():
        q = F * 1e4 * rate
        cool[sname] = {'steady_MW_m2': q / 1e6, **{f'max_armour_mm_{n}': MAT[n]['k'] * COND_DT / q * 1e3 for n in ('W', 'C (CFC)', 'Mo', 'SiC')}}
    out = {'study': 'Revision 4 section 5, pulsed-radiation durability (T00)', 'status': 'MODEL, research only, NON-CANON',
           'assumptions': {'pulse_s': TAU_PULSE, 'erosion_allowance_m': ALLOW_EROSION_M, 'conduction_dT_K': COND_DT, 'materials': MAT,
                           'bands': BANDS, 'transport': 'Compton-thick fuel (tau ~20); bands bound the escaping spectrum, no transport code'},
           'rows': rows, 'cooling': cool, 'plasma_on_axis': plasma_on_axis(R4), 'cycles_per_mission': rate * 5.685 * YEAR}
    write_json('durability.json', out)
    for r in rows:
        print(f"{r['surface'][:14]:14s} {r['material'][:18]:18s} {r['band'][:22]:22s} dT {r['surface_dT_K']:9.0f} K  {r['verdict']}"
              + (f"  {r.get('replace_interval_s', 0):.3g} s" if 'replace_interval_s' in r else ''))
    print(cool); print(out['plasma_on_axis'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
