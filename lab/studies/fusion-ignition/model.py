"""Fusion Ignition, From Nucleus to Nozzle: the data behind the flagship simulation (engineering/fusion-ignition/). Standard library only.

One file of generated physics for a page that only draws and looks values up. Every block names its class: CALCULATED (computed here or
by the shared Vertex modules), SAMPLED (test particles or a grid of model runs), IMPORTED (copied once from another study), SPEC (ship
parameters) or ILLUSTRATIVE (a display choice, no physics claim). Nothing here is canon and nothing writes to data/.

  need      the ship's propulsion requirement (src/wayfarer/operating_point.py, SPEC/WORKING)
  engine    the Vertex engine: stations, coils, vacuum field on the axis, stored energy, one pulse (vertex_engine, vertex_magnet)
  startup   the start sequence, step by step, with what is budgeted and what is not (ignition-failures constants, IMPORTED)
  fuel      one pulse's D-3He target and hydrogen reaction mass (vertex_magnet.plasma, docs/FUEL_SYSTEM.md flows)
  nuclear   one D-3He encounter: Coulomb barrier, Gamow factor, Bosch-Hale cross section, products (CALCULATED)
  plasma    reactivities, the thermal ignition (Lawson) curve, and the Vertex single-target burn (vertex_radiation.burn, R2-B) over
            areal density and start temperature: the engine's own ignition model, with its histories
  nozzle    representative charged-particle paths in the vacuum field (Boris push, the same field and obstacles as vertex_magnet)
  channels  where one engine's power goes in each compact variant C1-C4 (lab/studies/vertex-compact-engine/vertex-compact via imports/compact_*.json)
  lab       the experiment levers: fuel mix, temperature, polarisation (selective-fusion grid), field multiple (compact scan), coil armour,
            grazing-incidence mirrors, variants; each lever has its class
  problems  ENG-030..038 (compact study) and ENG-040..056 (thermal study) with the engine categories they point at
  thermal   per-component radiation and heat, mirror strategies A-D, hot and cryogenic circuits, energy flow and the WORK hardware
            geometry (lab/studies/vertex-compact-engine/vertex-thermal via imports/thermal_*.json, IMPORTED)

    python3 lab/studies/fusion-ignition/model.py      # writes results/fusion_ignition.json (about 20 s)
"""
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'src' / 'wayfarer'))
import spec as S  # noqa: E402
import operating_point as op  # noqa: E402
import vertex_engine as ve  # noqa: E402
import vertex_magnet as vm  # noqa: E402
import vertex_radiation as vr  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger as LG  # noqa: E402

IMPORT = sorted((HERE / 'imports').glob('compact_*.json'))[-1]
THERMAL = sorted((HERE / 'imports').glob('thermal_*.json'))[-1]
SOURCE = sorted((HERE / 'imports').glob('source_*.json'))[-1]
IGNITION = ROOT / 'lab/studies/ignition-failures/results/ignition.json'
FUSION = ROOT / 'lab/studies/selective-fusion/results/fusion.json'

MEV, KEV, AMU = vr.MEV, vr.KEV, vr.AMU
C_LIGHT = 299792458.0
E2_MEV_FM = 1.439964548                      # e^2 / (4 pi eps0) in MeV fm
ALPHA_FS = 1 / 137.035999084
AMU_MEV = 931.49410242
# Bosch-Hale 1992 cross-section fit for D(3He,p)4He: S(E) in keV mb, E centre-of-mass keV, valid 0.3-900 keV
BH_SIGMA = dict(BG=68.7508, A=(5.7501e6, 2.5226e3, 4.5566e1, 0.0, 0.0), B=(-3.1995e-3, -8.5530e-6, 5.9014e-8, 0.0))
H2_PER_ENGINE_KG_S = 0.385 / 4               # docs/FUEL_SYSTEM.md M3 flow table: 0.385 kg/s hydrogen at the operating point, four engines
CHARGE_POWER_W = 100e6                       # ILLUSTRATIVE coil charging power per engine (no owner number exists; the time scales with it)
NIF_RHOR = 1.0                               # g/cm2, order of the best compressed fuel areal density shown in laser-driven D-T (for scale)

# Measured on the built approved ship (lab/studies/vertex-compact-engine/vertex-compact, 2026-11-23, geometry diff 0): ship X of the parts the schematic ship draws.
SHIP = dict(burn_x=-153.4, cluster_front=-134.6, thrust_ring=(-136.4, 6.5), spine=(-136.4, -100.0, 6.5), tank=(-100.0, 90.0, 19.7),
            blades=dict(x0=-133.25, x1=48.9, r0=6.5, r1=37.0, az=(30.0, 150.0, 270.0)), shield=(94.0, 157.0, 45.0), habitat=(94.0, 105.0, 30.0))
CATEGORY_OF = dict(RING=['MAGNETIC_NOZZLE', 'MAGNETIC_COILS'], BLADES=[], HUB=['STRUCTURE'], SCREEN=[], SHIELD=['SHIELDING'], TRUSS=['STRUCTURE'])


def r3(v, n=4):
    return float(f'{v:.{n}g}') if isinstance(v, float) and math.isfinite(v) else v


def rt(v):
    """Blender engine frame (x, y, z) -> runtime (x, z, -y), as the exported GLB and vertex_inspect."""
    return (v[0], v[2], -v[1])


# ---------- need ---------------------------------------------------------------------------------------------------------------------

def need(s):
    r = op.report(s); o = r['operating_point']; m = r['mission']
    return dict(cls='SPEC', source='src/wayfarer/operating_point.py report() (physics.operating_point, WORKING)',
                departure_t=o['departure_mass_kg'] / 1e3, delta_v_m_s=o['delta_v_m_s'], cruise_c=o['delta_v_m_s'] / C_LIGHT,
                exhaust_m_s=o['exhaust_velocity_m_s'], exhaust_c=o['exhaust_velocity_c'], thrust_N=o['peak_thrust_N'],
                jet_W=o['peak_jet_power_W'], fusion_W=o['peak_fusion_power_W'], burn_d=o['duration_d'], burns=m['burns'],
                accel_g=o['accel_g'], propellant_t=m['propellant_kg'] / 1e3, species_t={k: v / 1e3 for k, v in r['species_kg'].items()},
                absorbed_fraction=o['absorbed_fraction'], hot_budget_W=o['hot_budget_W'], mass_flow_kg_s=o['peak_mass_flow_kg_s'],
                engines=4)


# ---------- engine --------------------------------------------------------------------------------------------------------------------

def engine(s):
    st = ve.stations(s); pz = vm.plasma(s); nom = vm.candidate(s, 'NOMINAL'); cs, I = nom['cs'], nom['I']
    W = vm.stored_energy(cs, I)
    prof = [(x, abs(vm.field(cs, I, x, 0.0)[1])) for x in [st['shield_aft'] + 0.5 - k * (st['shield_aft'] + 0.5 - st['exit'] + 8) / 59 for k in range(60)]]
    coils = [dict(name=c['name'], x=c['x'], r=c['r'], MAt=i / 1e6) for c, i in zip(cs, I)]
    burned = vr.implied_target(s)
    return dict(cls='CALCULATED', source='vertex_engine.stations, vertex_magnet (NOMINAL coil set, exact loop fields), vertex_radiation.implied_target',
                stations={k: v for k, v in st.items() if isinstance(v, float)}, coils=coils, B_burn_T=abs(vm.field(cs, I, st['burn'], 0.0)[1]),
                stored_J=W, axis_B=[[r3(x), r3(b)] for x, b in prof],
                pulse=dict(yield_J=pz['yield_J'], Hz=pz['pulse_Hz'], period_s=pz['period_s'], charged_share=pz['charged_share'],
                           exhaust_m_s=pz['exhaust_m_s'], jet_mass_kg=pz['mass_kg'], burned_kg=burned['burned_kg'],
                           burn_fraction=burned['implied_burn_fraction'], power_W=pz['yield_J'] * pz['pulse_Hz']),
                cold_K=vr.config(s)['cold_K'])


# ---------- accounting ----------------------------------------------------------------------------------------------------------------

def accounting(s, nd, eng, pl, ch, nu):
    """Energy per pulse, pulse rate and power in the three model states the page uses, and how they relate. Nothing is reconciled by
    changing a number: the states come from different models (mission requirement, engine pulse design point, imported compact study)
    and the page names which one each stage shows."""
    p = eng['pulse']; r = s['vertex_research']; sp = ve.config(s)['speculative']
    b = pl['burn']; g = b['grid'][f'{b["rhoR_design"]:g}|{b["Ti_design"]:g}']; src = ch['powers']
    need_e = nd['fusion_W'] / nd['engines']; pulse_e = p['yield_J'] * p['Hz']
    left = (g['fusion_J'] + g['heat_J'] - g['photon_share'] * g['fusion_J'] - g['neutron_share'] * g['fusion_J']) / g['fusion_J']
    pts = {q['E_keV']: q for q in nu['points']}; q100 = min(nu['points'], key=lambda q: abs(q['E_keV'] - 100.0))
    qpk = max(nu['points'], key=lambda q: q['E_keV'])
    return dict(
        cls='CALCULATED', source='need (operating_point), engine.pulse (vertex_engine C-02/C-04), plasma.burn (R2-B), channels (compact aebbb0d)',
        states=[
            dict(id='need', label='Mission requirement', cls='SPEC', per_engine_W=need_e, cluster_W=nd['fusion_W'], thrust_N=nd['thrust_N'],
                 source='operating_point.report: 0.5 g departure burn, 4,426 t ship, exhaust 19,201 km/s'),
            dict(id='pulse', label='Engine pulse design point', cls='SPECULATIVE', yield_J=p['yield_J'], Hz=p['Hz'], per_engine_W=pulse_e,
                 cluster_W=4 * pulse_e, thrust_N=r['thrust_MN'] * 1e6 * sp['design_power_share'] * 4,
                 source=f'vertex_engine C-02 (yield at the research armour fluence) and C-04 (rate for {sp["design_power_share"]:g} of the V4 '
                        f'research power per engine): the cluster equals one V4 research drive ({r["fusion_TW"]:.1f} TW, {r["thrust_MN"]:.2f} MN)'),
            dict(id='channels', label='Compact study (losses stage)', cls='IMPORTED', per_engine_W=src['fusion_per_engine_W'], Hz=5697.0,
                 yield_J=src['fusion_per_engine_W'] / 5697.0,
                 shares=dict(xray=src['P_brems_W'] / src['fusion_per_engine_W'], sync=src['P_sync_W'] / src['fusion_per_engine_W'],
                             neutron=src['P_n_W'] / src['fusion_per_engine_W'], charged=src['P_charged_W'] / src['fusion_per_engine_W']),
                 source=f'lab/studies/vertex-compact-engine/vertex-compact at aebbb0d: mission power per engine, fuel source {src["fuel"]} (steady-plasma radiation shares), '
                        'pulse rate 5,697 Hz taken from the design point, so its implied energy per pulse is not the 1.57 GJ target'),
        ],
        gap=dict(power_ratio=need_e / pulse_e, Hz_at_design_yield=need_e / p['yield_J'], yield_at_design_Hz_J=need_e / p['Hz']),
        burn=dict(fusion_J=g['fusion_J'], heat_J=g['heat_J'], xray=g['photon_share'], neutron=g['neutron_share'], left_in_plasma=left,
                  note='Shares of the fusion energy from one R2-B target burn. "Left in the plasma" is the energy balance fusion + driver heat - '
                       'X-rays - neutrons: the thermal and kinetic energy of the expanding charged plasma, the part a nozzle could steer.'),
        charged_assumed=p['charged_share'],
        encounter=dict(T_keV=q100['E_keV'], per_close_90=q100['sigma_fus_b'] / q100['sigma_90_b'], per_deflection=q100['fuse_per_scatter'],
                       peak_keV=qpk['E_keV'], peak_per_close_90=qpk['sigma_fus_b'] / qpk['sigma_90_b'], peak_per_deflection=qpk['fuse_per_scatter'],
                       note='per_close_90: fusion against one single hard (90 degree) Coulomb encounter; per_deflection: against the momentum-transfer '
                            'cross section (many distant small-angle passes, ln Lambda = 20). Both at a fixed pair energy, not a thermal average.'),
    )


# ---------- startup -------------------------------------------------------------------------------------------------------------------

def startup(eng, ign):
    K = ign['constants']; r = ign['reference']
    W = eng['stored_J']; t_charge = W / CHARGE_POWER_W
    steps = [
        dict(id='POWER', title='Electrical power to the engine bay', cls='OPEN',
             text='The cluster takes power through its power bay. Which source carries the driver is not budgeted: the only budgeted store is '
                  f'the {K["bank_J"] / 1e6:,.0f} MJ pulse bank, charged at {K["bank_W"] / 1e6:,.0f} MW.', value=dict(bank_J=K['bank_J'], bank_W=K['bank_W'])),
        dict(id='COOL', title='Coils cold', cls='CALCULATED', text=f'The superconducting windings are held near {eng["cold_K"]:.0f} K by the cryogenic '
             'circuit before any current flows. A warm spot in a winding would end superconductivity there.', value=dict(cold_K=eng['cold_K'])),
        dict(id='CHARGE', title='Current ramps up in the coils', cls='CALCULATED',
             text=f'Six coils per engine take {min(c["MAt"] for c in eng["coils"]):.1f} to {max(abs(c["MAt"]) for c in eng["coils"]):.1f} '
                  f'mega-ampere-turns. The field stores {W / 1e9:.1f} GJ per engine. At an illustrative {CHARGE_POWER_W / 1e6:.0f} MW the ramp takes '
                  f'{t_charge:.0f} s.', value=dict(stored_J=W, charge_W=CHARGE_POWER_W, charge_s=t_charge, charge_cls='ILLUSTRATIVE')),
        dict(id='FIELD', title='The magnetic nozzle forms', cls='CALCULATED',
             text=f'The field lines form a closed cusp ahead of the burn point and open aft into the nozzle. {eng["B_burn_T"]:.2f} T at the burn '
                  'point (vacuum field: no plasma yet, and a field alone makes no plasma and no fusion).', value=dict(B_burn_T=eng['B_burn_T'])),
        dict(id='CHECK', title='Readiness checks', cls='OPEN',
             text='Field map, coil temperatures, quench detection, bore shutter, target magazine and driver alignment. The quench protection '
                  f'must absorb {K["quench_J"] / 1e9:.1f} GJ if a coil goes normal; no dump system is sized yet.', value=dict(quench_J=K['quench_J'])),
        dict(id='DRIVER', title='Driver power for the targets', cls='OPEN',
             text=f'At the mission rate the target drivers need {r["driver_W"] / 1e12:.2f} TW (gain 100, 50 % efficient): '
                  f'{r["bank_ratio"]:,.0f} times the pulse bank\'s power. This is the first thing that fails, after '
                  f'{K["bank_J"] / r["driver_W"] * 1e3:.2f} ms.', value=dict(driver_W=r['driver_W'], bank_empty_s=K['bank_J'] / r['driver_W'])),
    ]
    return dict(cls='CALCULATED', source='lab/studies/ignition-failures results (constants, reference); vertex_magnet stored energy', steps=steps)


# ---------- fuel ----------------------------------------------------------------------------------------------------------------------

def fuel(eng):
    p = eng['pulse']; mb = p['burned_kg']
    m_pair = vr.M_ION['D'] + vr.M_ION['He3']
    pairs = mb / (m_pair * AMU)
    h2 = H2_PER_ENGINE_KG_S / p['Hz']
    return dict(cls='CALCULATED', source='vertex_radiation.implied_target (burned mass), docs/FUEL_SYSTEM.md (H2 flow)',
                target_injected_kg=p['jet_mass_kg'], target_burned_kg=mb, D_kg=pairs * vr.M_ION['D'] * AMU, He3_kg=pairs * vr.M_ION['He3'] * AMU, nuclei_pairs=pairs,
                electrons=pairs * 3, ionise_eV=dict(D=13.6, He3=24.6 + 54.4), h2_per_pulse_kg=h2, h2_kg_s=H2_PER_ENGINE_KG_S,
                h2_state='MISSION', h2_cls='SPECULATIVE', h2_note='The hydrogen flow is the mission state (operating_point); divided by the design '
                'pulse rate it mixes two states and is shown only for scale. '
                'How MeV fusion products give their energy to cold hydrogen is SPECULATIVE and belongs to the engine '
                'workstream; the hydrogen opens only after ignition (FPS states IGNITION, then PROPELLANT FEED).')


# ---------- nuclear -------------------------------------------------------------------------------------------------------------------

def sigma_dhe3_b(E_keV):
    """Bosch-Hale D-3He fusion cross section, barn, E in keV (centre of mass)."""
    A, B = BH_SIGMA['A'], BH_SIGMA['B']
    Sv = (A[0] + E_keV * (A[1] + E_keV * (A[2] + E_keV * (A[3] + E_keV * A[4])))) / (1 + E_keV * (B[0] + E_keV * (B[1] + E_keV * (B[2] + E_keV * B[3]))))
    return Sv / (E_keV * math.exp(BH_SIGMA['BG'] / math.sqrt(E_keV))) * 1e-3


def nuclear():
    mD, mH = vr.M_ION['D'], vr.M_ION['He3']
    mu = mD * mH / (mD + mH) * AMU_MEV
    R = 1.2 * (2 ** (1 / 3)) + 1.2 * (3 ** (1 / 3))          # touching radii, fm (R = 1.2 A^1/3)
    Vb = 2 * E2_MEV_FM / R                                   # MeV
    EG = 2 * mu * (math.pi * ALPHA_FS * 2) ** 2 * 1e3        # keV
    T = 100.0
    E0 = (EG * T * T / 4) ** (1 / 3)
    lnL = 20.0
    def b90(E):
        return 2 * E2_MEV_FM / (2 * E / 1e3)                 # fm, 90-degree impact parameter at centre-of-mass energy E keV
    rows = []
    for k in range(61):
        E = 10 ** (1 + 2.3 * k / 60)                          # 10 keV .. 2 MeV
        sf = sigma_dhe3_b(min(E, 900.0)) if E <= 900 else None
        s90 = math.pi * (b90(E) * 1e-15) ** 2 / 1e-28
        rows.append([r3(E), r3(sf) if sf else None, r3(math.exp(-math.sqrt(EG / E))), r3(s90), r3(s90 * 8 * lnL)])
    gp = [[r3(E), r3(math.exp(-E / T - math.sqrt(EG / E)) / math.exp(-E0 / T - math.sqrt(EG / E0)))] for E in [5 + 5 * k for k in range(120)]]
    prods = {}
    for name, e, m in (('p', 14.68, vr.M_ION['p']), ('alpha', 3.67, vr.M_ION['alpha'])):
        g = 1 + e / (m * AMU_MEV)
        prods[name] = dict(MeV=e, v_c=math.sqrt(1 - 1 / g ** 2), charge=1 if name == 'p' else 2, mass_amu=m)
    at = lambda E: dict(E_keV=E, sigma_fus_b=sigma_dhe3_b(E), sigma_90_b=math.pi * (b90(E) * 1e-15) ** 2 / 1e-28, sigma_scatter_b=math.pi * (b90(E) * 1e-15) ** 2 / 1e-28 * 8 * lnL)
    pts = [at(E0), at(100.0)]
    for p_ in pts:
        p_['fuse_per_scatter'] = p_['sigma_fus_b'] / p_['sigma_scatter_b']
    return dict(cls='CALCULATED', source='Coulomb barrier at touching radii (R = 1.2 A^1/3 fm), Gamow energy, Bosch-Hale 1992 cross-section fit; '
                'momentum-transfer Coulomb cross section 8 ln(Lambda) x pi b90^2 with ln(Lambda) = 20',
                Q_MeV=vr.Q['DHe3'], products=prods, barrier_MeV=Vb, touch_fm=R, gamow_keV=EG, T_keV=T, gamow_peak_keV=E0,
                curve_fields=['E_keV', 'sigma_fus_b', 'tunnel_P', 'sigma_90_b', 'sigma_scatter_b'], curve=rows, gamow_window=gp, points=pts,
                peak=max(((E, sigma_dhe3_b(E)) for E in range(50, 900, 5)), key=lambda a: a[1]))


# ---------- plasma --------------------------------------------------------------------------------------------------------------------

def lawson(Te_over_Ti=1.0):
    """Thermal 1:1 D-3He: the n tau_E (m^-3 s) at which charged-product heating equals bremsstrahlung plus transport (W / tau_E).
    None where bremsstrahlung alone exceeds the fusion heating."""
    out = []
    for T in [20, 30, 40, 50, 60, 70, 80, 100, 120, 150, 200, 250, 300, 400, 500]:
        Te = T * Te_over_Ti; n = 1e20; nD = nH = n / 2; ne = nD + 2 * nH; zeff = (nD + 4 * nH) / ne
        Pf = nD * nH * vr.sigma_v('DHe3', min(T, vr.BH_VALID_KEV['DHe3'] * 2.5)) * vr.Q['DHe3'] * MEV
        Pb = vr.brems_W_m3(ne, Te, zeff)
        Wth = 1.5 * (ne * Te + n * T) * KEV
        net = Pf - Pb
        out.append([T, r3(Wth / net * n) if net > 0 else None, r3(Pb / Pf)])
    return out


def reactivities():
    out = []
    for k in range(50):
        T = 10 ** (0.7 + 1.9 * k / 49)
        row = [r3(T)]
        for rx in ('DHe3', 'DDn', 'DDp', 'DT'):
            row.append(r3(vr.sigma_v(rx, min(T, vr.BH_VALID_KEV[rx] * 2.5))))
        out.append(row)
    return out


def burns(s):
    """The Vertex single-target burn (vertex_radiation.burn, the R2-B CONSERVATIVE case: a uniform sphere of the implied target mass,
    fusion products heat the fuel, electrons radiate, the sphere expands) over areal density and start temperature."""
    c = vr.config(s); base = next(x for x in c['cases'] if x['id'] == 'CONSERVATIVE')
    rr = vr.rhoR_for_yield(s, base)
    grid = {}
    RHO = [3.0, 10.0, 30.0, 60.0, round(rr, 1), 200.0]
    TI = [30.0, 50.0, 70.0, 100.0]
    for r in RHO:
        for T in TI:
            b = vr.burn(s, dict(base, rhoR_g_cm2=r, Ti_keV=T), spectrum=False)
            grid[f'{r:g}|{T:g}'] = dict(gain=b['fusion_J'] / b['initial_heat_J'], fusion_J=b['fusion_J'], heat_J=b['initial_heat_J'],
                                        burn_fraction=b['burn_fraction'], photon_share=b['photon_share'], neutron_share=b['neutron_share'],
                                        Ti_peak_keV=b['Ti_peak_keV'], duration_s=b['duration_s'], R0_m=b['R0_m'],
                                        history=[[r3(t), r3(ti), r3(te), r3(R), r3(E)] for t, ti, te, R, E in b['history']])
    return dict(cls='CALCULATED', source='src/wayfarer/vertex_radiation.py burn() (R2-B, CONSERVATIVE case), rhoR_for_yield()',
                rhoR=RHO, Ti=TI, rhoR_design=round(rr, 1), Ti_design=base['Ti_keV'], grid=grid, history_fields=['t_s', 'Ti_keV', 'Te_keV', 'R_m', 'fusion_J'],
                yield_J=vm.plasma(s)['yield_J'], nif_rhoR=NIF_RHOR,
                open='How the target reaches its areal density (the driver and the implosion) is not modelled anywhere in the project: the burn starts '
                     'from an assumed compressed, heated sphere.')


def plasma(s):
    return dict(cls='CALCULATED', source='vertex_radiation.sigma_v (Bosch-Hale), brems_W_m3 (relativistic)',
                reactivity_fields=['T_keV', 'DHe3', 'DDn', 'DDp', 'DT'], reactivity=reactivities(),
                lawson_fields=['T_keV', 'n_tau_m3_s', 'brems_over_fusion'], lawson=dict(thermal=lawson(1.0), hot_ion=lawson(0.5)),
                dt_ref=dict(n_tau_min=1.5e20, note='D-T, for scale: about 1.5e20 m^-3 s near 25 keV (textbook ignition)'),
                burn=burns(s))


# ---------- nozzle: representative paths ---------------------------------------------------------------------------------------------

def path(s, cs, I, sp, v, d, hw, every=6, dt_gyro=40, max_pts=48):
    """vertex_magnet.push with the path kept (same Boris step, field, obstacles and exits)."""
    st = ve.stations(s); c = vm.config(s)
    m = sp['mass_amu'] * AMU; q = sp['charge'] * vm.E_CHARGE
    x = [st['burn'], 0.0, 0.0]; u = [v * d[0], v * d[1], v * d[2]]
    Bref = max(abs(vm.field(cs, I, st['burn'], 0.0)[1]), 0.05)
    dt = min(2 * math.pi * m / (q * Bref) / dt_gyro, 0.02 / v)
    tmax = 6 * abs(st['exit'] - st['burn'] - c['exit_margin_m']) / v + 4 * c['radial_limit_m'] / v
    t = 0.0; pts = [rt(x)]; k = 0; out = 'TRAPPED'; hit = None
    while t < tmax:
        B = vm.field3(cs, I, x); b = math.sqrt(sum(a * a for a in B)); h = q * dt / (2 * m)
        tv = [h * a for a in B]; t2 = sum(a * a for a in tv); sv = [2 * a / (1 + t2) for a in tv]
        up = [u[0] + (u[1] * tv[2] - u[2] * tv[1]), u[1] + (u[2] * tv[0] - u[0] * tv[2]), u[2] + (u[0] * tv[1] - u[1] * tv[0])]
        u = [u[0] + (up[1] * sv[2] - up[2] * sv[1]), u[1] + (up[2] * sv[0] - up[0] * sv[2]), u[2] + (up[0] * sv[1] - up[1] * sv[0])]
        step = dt if b == 0 else min(dt, 2 * math.pi * m / (q * b) / dt_gyro)
        x = [x[i] + u[i] * step for i in range(3)]; t += step; k += 1
        if k % every == 0:
            pts.append(rt(x))
        rho = math.hypot(x[1], x[2]); n = vm.obstacle(hw, x[0], rho)
        if n:
            out, hit = 'HIT', n; break
        if x[0] < st['exit'] - c['exit_margin_m']:
            out = 'AFT'; break
        if rho > c['radial_limit_m'] or x[0] > st['front']:
            out = 'OUT'; break
    pts.append(rt(x))
    if len(pts) > max_pts:
        idx = [round(i * (len(pts) - 1) / (max_pts - 1)) for i in range(max_pts)]
        pts = [pts[i] for i in idx]
    return dict(outcome=out, obstacle=hit, t_s=t, axial=-u[0] / math.sqrt(sum(a * a for a in u)), pts=[round(c_, 1) for p in pts for c_ in p])


def nozzle(s, n=14):
    nom = vm.candidate(s, 'NOMINAL'); cs = nom['cs']; pz = vm.plasma(s); hw = vm.hardware(s, cs)
    out = {}
    for mult in (1.0, 4.0):
        I = [i * mult for i in nom['I']]
        per = {}
        for sp in pz['species']:
            v = vm.speed(sp, pz['exhaust_m_s'] * sp.get('bulk_speed_factor', 1.0))
            paths = [path(s, cs, I, sp, v, d, hw) for d in vm._dirs(n)]
            per[sp['id']] = dict(name=sp['name'], charge=sp['charge'], mass_amu=sp['mass_amu'], speed_m_s=v,
                                 larmor_burn_m=vm.larmor(sp, abs(vm.field(cs, I, ve.stations(s)['burn'], 0.0)[1]) or 1e-9, v),
                                 share=dict(aft=sum(p['outcome'] == 'AFT' for p in paths) / n, hit=sum(p['outcome'] == 'HIT' for p in paths) / n,
                                            out=sum(p['outcome'] == 'OUT' for p in paths) / n, trapped=sum(p['outcome'] == 'TRAPPED' for p in paths) / n),
                                 paths=paths)
        out[f'{mult:g}'] = per
    return dict(cls='SAMPLED', source='Boris push in the NOMINAL vacuum field (vertex_magnet.field3, hardware, obstacle); field x4 scales every '
                'coil current; no plasma response, no collisions, so detachment is not shown', directions=n, mult=out)


# ---------- channels ------------------------------------------------------------------------------------------------------------------

def channels(imp):
    src = imp['source']; Pc = src['P_charged_W']; budget = src['drive_W'] / 4
    out = {}
    for key, v in imp['variants'].items():
        hit = v['hit_share'] * Pc; useful = v['eta'] * Pc; side = max(Pc - hit - useful, 0.0)
        piped = v['piped_four_W'] / 4
        out[key] = dict(label=v['label'], fusion_W=src['fusion_per_engine_W'], charged_useful_W=useful, charged_side_W=side, charged_hit_W=hit,
                        brems_W=src['P_brems_W'], sync_W=src['P_sync_W'], neutron_W=src['P_n_W'], piped_W=piped, budget_W=budget,
                        over=piped / budget, eta=v['eta'], ship_lit_W=v['ship_lit_W'], ship_lit_over=v['ship_lit_over_limit'],
                        winding_over=v['winding_over_limit'], engine_t=v['engine_t'], dust_t=[v['dust_nominal_t'], v['dust_justified_t']],
                        x_burn=v['x_burn'], standoff_m=v['standoff_m'], shield=v['shield'], departure_t=v['departure_if_heat_closed_t'])
    return dict(cls='IMPORTED', source=f'{IMPORT.relative_to(ROOT)} (lab/studies/vertex-compact-engine/vertex-compact compact.py, quick run, 48 directions x 4 species)',
                provenance=imp['provenance'], ship_lit_limit_W=1e8, fuel=src['fuel'], powers=src, variants=out)


# ---------- lab -----------------------------------------------------------------------------------------------------------------------

def mirrors(Te=100.0):
    """Grazing-incidence X-ray mirrors (multilayer supermirrors) in front of hardware: what share of the bremsstrahlung landing on a
    mirrored surface leaves again, at grazing angle theta. Reflection only below E_max(theta) = K / theta (K about 16 keV deg, the order
    of hard X-ray telescope supermirrors), with reflectivity 0.5 there; the brems power spectrum is about exp(-E / Te)."""
    K, R = 16.0, 0.5
    rows = []
    for th in (0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.0, 5.0):
        Em = K / th
        below = 1 - math.exp(-Em / Te)
        rows.append(dict(theta_deg=th, E_max_keV=Em, reflectable=below, reflected=R * below, length_factor=1 / math.sin(math.radians(th))))
    return dict(cls='MODEL-BASED', source='Thermal bremsstrahlung spectrum at Te; supermirror cut-off K / theta with K = 16 keV deg and R = 0.5 '
                '(order of hard X-ray telescope optics); neutrons and charged products are not reflected', Te_keV=Te, K_keV_deg=K, R=R, rows=rows,
                note='A mirror only helps where the photons meet it at a grazing angle. To intercept the same share of the sky at angle theta, a '
                     'surface must be about 1 / sin(theta) times longer, and half the photons it accepts are still absorbed in it.')


def lab(imp, eng):
    f = json.loads(FUSION.read_text())
    keep = ('charged', 'neutron', 'photon', 'rel_power')
    ix = [f['fields'].index(k) for k in keep]
    grid = {k: [v[i] for i in ix] for k, v in f['grid'].items()}
    fs = imp['field_scan']
    V = imp['variants']
    over0 = V['C1']['winding_over_limit']
    return dict(
        fuel=dict(cls='CALCULATED', source='lab/studies/selective-fusion/results/fusion.json (Bosch-Hale, relativistic brems)', axes=f['axes'], fields=list(keep), grid=grid,
                  reference=f['reference']),
        field=dict(cls='SAMPLED', source=f'{IMPORT.relative_to(ROOT)} field_scan (ron.evaluate, 48 directions)', scan=fs,
                   note='The closure field times 1, 2 or 4. In the drawn cluster (C1) more field changes almost nothing: the products that miss '
                        'the nozzle hit the shield and loops before the field turns them. In C3 the burn sits farther from the shield, which helps more.'),
        armour=dict(cls='CALCULATED', source='MPN rule used in lab/studies/vertex-compact-engine/vertex-compact/problems.py: W-B4C attenuation length 0.08 m, scattered floor 1e-4',
                    over_at_t0=over0, t0_m=0.22, lam_m=0.08, floor=1e-4, density_kg_m3=12000.0, area_m2_per_engine=989.0 / 4,
                    note='Thicker armour helps until the neutrons scattered round it dominate; that floor alone is about '
                         f'{over0 * 1e-4 / (math.exp(-0.22 / 0.08) + 1e-4):.0f} times the winding limit.'),
        mirrors=mirrors(),
        spin=dict(cls='MODEL-BASED', note='Polarised D and 3He: D-3He rate up to x1.5 in theory, never shown in a burning plasma. The D-D suppression '
                  'option is SPECULATIVE.'),
        variants=dict(cls='IMPORTED', order=['C1', 'C2', 'C3', 'C4'], note='C1 is the approved cluster; C2-C4 move it 30-36 m aft and are research, '
                      'not canon. C4 is the recommended compact research direction, not a validated design.'),
        supported=['fuel', 'temperature', 'mode', 'pol', 'variant', 'field', 'armour', 'mirror', 'rhoR', 'Ti0'],
        speculative=['spin D-D suppression', 'advanced materials', 'hydrogen coupling'],
        engine_mass_t=eng.get('mass_t'))


def rnd(v):
    if isinstance(v, float):
        return float(f'{v:.4g}') if math.isfinite(v) else None
    if isinstance(v, dict):
        return {k: rnd(x) for k, x in v.items()}
    if isinstance(v, list):
        return [rnd(x) for x in v]
    return v


def thermal(th):
    keep = ('state', 'state_note', 'powers', 'spectrum', 'reconcile', 'surfaces', 'components', 'secondary_W', 'pulsed', 'hot', 'cryo', 'strategies',
            'comparison', 'flow', 'geometry', 'paths', 'optics', 'params', 'warm')
    out = {k: th[k] for k in keep}
    out['strategies'] = {k: {a: b for a, b in v.items() if a != 'psi_hist_W'} for k, v in th['strategies'].items()}
    return dict(cls='IMPORTED', source=f'{THERMAL.relative_to(ROOT)} (lab/studies/vertex-compact-engine/vertex-thermal thermal.py at {th["provenance"]["branch_head"]})', **rnd(out))


def source(sr):
    """Energy at the source (lab/studies/vertex-compact-engine/vertex-source, owner brief 2026-11-24): product slowing-down, bremsstrahlung, the target levers, the X-ray
    trapping tamper, the audit and the advanced-technology levers (IMPORTED; each row names its class)."""
    keep = ('design', 'slowing', 'brems', 'trade', 'tamper', 'audit', 'tech', 'findings', 'best', 'pickup', 'params')
    out = {k: sr[k] for k in keep}
    out['levers'] = [{k: v for k, v in r.items() if k != 'case'} | dict(case=r['case']) for r in sr['levers']]
    return dict(cls='IMPORTED', source=f'{SOURCE.relative_to(ROOT)} (lab/studies/vertex-compact-engine/vertex-source source.py at {sr["provenance"]["branch_head"]})', **rnd(out))


def problems(imp, th=None):
    out = []
    for p in imp['problems']:
        cats = sorted({c for comp in p.get('components', []) for c in CATEGORY_OF.get(comp, [])})
        out.append(dict(id=p['id'], title=p['title'], status=p['status'], severity=p['severity'], subsystem=p['subsystem'], variants=p['variants'],
                        mechanism=p['mechanism'], required=p['required'], achieved=p['achieved'], solutions=p['solutions'], advances=p['advances'],
                        next=p['next'], evidence=p['evidence'], assumptions=p['assumptions'], components=p.get('components', []), categories=cats))
    for p in (th or {}).get('problems', []):
        out.append({k: p.get(k) for k in ('id', 'title', 'status', 'severity', 'subsystem', 'variants', 'mechanism', 'required', 'achieved', 'solutions',
                                          'advances', 'next', 'evidence', 'assumptions', 'components', 'categories', 'stages')})
    return dict(cls='IMPORTED', source=f'{IMPORT.relative_to(ROOT)} problems (lab/studies/vertex-compact-engine/vertex-compact/problems.py) and {THERMAL.relative_to(ROOT)} (lab/studies/vertex-compact-engine/vertex-thermal/problems.py)',
                register='lab/studies/vertex-compact-engine/vertex-compact/PROBLEMS.md, lab/studies/vertex-compact-engine/vertex-thermal/PROBLEMS.md', items=out)


def inputs_hash():
    h = hashlib.sha256()
    for p in [HERE / 'model.py', HERE / 'ledger.py', ROOT / 'references/evidence/vertex_source.json', IMPORT, THERMAL, SOURCE, IGNITION, FUSION, ROOT / 'data/wayfarer_3d.toml', ROOT / 'src/wayfarer/vertex_radiation.py',
              ROOT / 'src/wayfarer/vertex_magnet.py', ROOT / 'src/wayfarer/vertex_engine.py', ROOT / 'src/wayfarer/operating_point.py']:
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def build():
    s = S.load()[0]
    imp = json.loads(IMPORT.read_text()); ign = json.loads(IGNITION.read_text()); th = json.loads(THERMAL.read_text())
    sr = json.loads(SOURCE.read_text())
    eng = engine(s); nd = need(s); pl = plasma(s); ch = channels(imp); nu = nuclear()
    d = dict(study='lab/studies/fusion-ignition', inputs_hash=inputs_hash(), ship=SHIP, need=nd, engine=eng, startup=startup(eng, ign),
             fuel=fuel(eng), nuclear=nu, plasma=pl, nozzle=nozzle(s), channels=ch, lab=lab(imp, eng), problems=problems(imp, th), thermal=thermal(th), source=source(sr),
             accounting=accounting(s, nd, eng, pl, ch, nu), ledger=LG.build(s, nd, imp, geo_sky=th['reconcile']['geometry_sky']),
             modeled=dict(cls='IMPORTED', source='lab/studies/ignition-failures results reference (Vertex 1.5-1.8 ledger)',
                          heat_over=ign['reference']['ratio'], burn_heat_over=ign['reference']['burn_ratio'], melt_s=ign['reference']['melt_s'],
                          coil=ign['reference']['coil'], coil_life_s=ign['reference']['coil_life_s'], driver_W=ign['reference']['driver_W'],
                          bank_empty_s=ign['constants']['bank_J'] / ign['reference']['driver_W']),
             classes=dict(SPEC='ship parameter', CALCULATED='computed by a model', SAMPLED='test particles or a grid of model runs',
                          IMPORTED='copied once from another study', **{'MODEL-BASED': 'expected from theory, not demonstrated'},
                          ILLUSTRATIVE='picture or display choice, no physics claim', OPEN='not modelled or not budgeted', SPECULATIVE='beyond '
                          'established physics or engineering'))
    A = d['thermal']['strategies']['A']
    d['lab']['mirrors']['drawn'] = dict(median_psi_deg=A['median_psi_deg'], reflected_share=A['coupled_reflected_share'])
    d['lab']['mirrors']['note'] += (f' On the drawn engine the faces meet the rays at a median {A["median_psi_deg"]:.0f} deg, where a coating returns '
                                    f'{A["coupled_reflected_share"]:.1e} of what strikes (thermal study, strategy A): this lever asks what if the faces were grazing.')
    return d


def main():
    d = build()
    (HERE / 'results' / 'fusion_ignition.json').write_text(json.dumps(d, separators=(',', ':')))
    n = d['nuclear']; b = d['plasma']['burn']; g = b['grid'][f'{b["rhoR_design"]:g}|{b["Ti_design"]:g}']
    print(f"barrier {n['barrier_MeV']:.3f} MeV, Gamow {n['gamow_keV']:.0f} keV, peak {n['gamow_peak_keV']:.0f} keV at 100 keV; "
          f"burn at rhoR {b['rhoR_design']} gain {g['gain']:.1f}, photons {g['photon_share']:.2f}; "
          f"nozzle p aft {d['nozzle']['mult']['1']['p_14.7MeV']['share']['aft']:.2f}")


if __name__ == '__main__':
    main()
