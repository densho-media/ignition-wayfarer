#!/usr/bin/env python3
"""The inverse problem: shape the fusion pulse so the magnetic nozzle needs less (owner brief 2026-11-25 08:55Z, item 2). WORK, not canon.

Every target is lab/studies/fusion-ignition/ledger.burn (R2-B, every joule and nucleus booked) through vertex-source.run. The engine is the
approved research geometry (vertex-optimize 'mirror4|4': burn 4 m aft, closure x4) with its momentum-consistent nozzle (eta, hit, pickup
from the page ledger 'R|1'). Each pulse runs at the frequency that holds the per-engine fusion power the mission needs (65.3 TW, the
ledger's need), so large/rare and small/frequent pulses are compared at equal power; a second table holds equal thrust.

Per pulse it books:
  - the burn: yield, gain, burn-up, X-ray / neutron / plasma / escaped shares, target mass, radius and density (compression), duration;
  - capture: the current scale k that stops the pulse's charged energy before the hardware (vertex-ron capture on the research
    geometry), stored field energy W, field at the burn and at the windings, hoop and axial loads (vertex-optimize coil_engineering), the
    diamagnetic cavity radius, and the same pulse in the coils as drawn (k = 1, 27 GJ) as a ripple and a fit;
  - the engine: thrust, exhaust speed, heat over the radiator share (vertex-source engine arithmetic, research nozzle);
  - operation: driver power (absorbed and at the wall plug), injector rate and the injection speed that brings the next target to the
    burn point after the cavity has collapsed, nozzle transit time, per-pulse X-ray fluence and surface temperature spike on the nearest
    cryostat (tungsten face), thermal-stress amplitude and cycles per year.

Two bases for the charged energy are carried and never mixed: BURN (the burn ledger: plasma + escaped products, the page's coupled state)
and OPERATING (the mission operating point's 90 % charged share, the basis of the 286 GJ capture of vertex-optimize).

    python3 lab/studies/vertex-compact-engine/vertex-pulse/pulse.py          # about 4 minutes; writes results/pulse.json

Classes: CALCULATED (burn model, field solver), ANALYTIC (closed forms), PROTOTYPE (choices marked P[...]), SPECULATIVE (polarisation).
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
for p in ('src/wayfarer', 'lab/studies/fusion-ignition', 'lab/studies/vertex-compact-engine/vertex-source',
          'lab/studies/vertex-compact-engine/vertex-optimize'):
    sys.path.insert(0, str(ROOT / p))
import spec as S  # noqa: E402
import ledger as lg  # noqa: E402
import source as src  # noqa: E402
import optimize as O  # noqa: E402

ron = O.ron
MU0 = 4e-7 * math.pi
YEAR = 3.15576e7
FI = ROOT / 'lab/studies/fusion-ignition/results/fusion_ignition.json'
OPT = ROOT / 'lab/studies/fusion-ignition/imports/optimize.json'
COILS = ROOT / 'lab/studies/vertex-compact-engine/vertex-optimize/results/coils.json'

P = dict(
    W_face=dict(rho=19300.0, c=134.0, k=173.0, E=411e9, alpha=4.5e-6, nu=0.28, mu_cm2_g=4.4),   # tungsten; mu at ~100 keV (NIST XCOM)
    sigma_fatigue=300e6,       # P[thermal-stress amplitude tungsten survives ~1e9+ cycles at temperature, order of magnitude]
    v_inj_max=20e3,            # P[injection speed of a fragile cryogenic target; gas guns reach ~1 km/s, electromagnetic ~10-20 km/s]
    transit_L=12.0,            # m, burn to nozzle exit in the research geometry (burn -22.8 to L4 -31.2 plus the exit flare)
    transit_margin=3.0,        # P[the nozzle must be clear for this many debris transits before the next pulse]
)


def burns(s):
    b = lg.base_case(s); r0 = lg.design_rhoR(s); m0 = lg.vm.plasma(s)['mass_kg']; base = dict(b, rhoR_g_cm2=r0)
    R = []
    for m in (1 / 64, 1 / 16, 1 / 4, 1.0, 4.0, 16.0):
        R.append(dict(src.run(s, f'Target mass x{m:g}', 'size', base, mass=m0 * m), mass_factor=m))
    for f in (0.5, 2.0):
        R.append(dict(src.run(s, f'Areal density x{f:g} (mass x1)', 'density', dict(base, rhoR_g_cm2=r0 * f)), mass_factor=1.0))
    R.append(dict(src.run(s, 'Small target x1/16 at areal density x2', 'size+density', dict(base, rhoR_g_cm2=r0 * 2), mass=m0 / 16),
                  mass_factor=1 / 16))
    R.append(dict(src.run(s, 'Tamped x2 (disassembly 2x slower)', 'duration', dict(base, expansion=0.5)), mass_factor=1.0))
    R.append(dict(src.run(s, '3He-rich D:3He 1:3', 'fuelling', dict(base, D_per_He3=0.33)), mass_factor=1.0))
    R.append(dict(src.run(s, 'Spin-polarised (sigma-v x1.5)', 'polarisation', base, pol=src.P['pol_gain'], cls='SPECULATIVE',
                          tech='polarised fuel survives manufacture, storage and compression'), mass_factor=1.0))
    R.append(dict(src.run(s, 'Early extraction 20 % (small target x1/16)', 'extraction', dict(base, deposition=0.8), mass=m0 / 16,
                          cls='MODEL-BASED'), mass_factor=1 / 16))
    return R


def engine(row, noz, Hz, budget):
    """vertex-source.engine with the research nozzle: thermal debris eta sqrt(2 m P), escaped products per particle, hits stay."""
    F = row['fusion_J']; X = F * row['xray_share']; N_ = F * row['neutron_share']
    Pd = F * row['plasma_share']; Pf = F * row['escaped_share']
    md = row['mass_kg'] - F / lg.C_LIGHT ** 2
    eta, hit, pick = noz['eta'], noz['hit'], noz['pickup']
    I_d = eta * math.sqrt(2 * md * Pd); I_f = 0.0; mf = 0.0
    for Ep, mp, share in ((14.68 * src.MEV, 1.00728 * src.AMU, 14.68 / 18.35), (3.67 * src.MEV, 4.00151 * src.AMU, 3.67 / 18.35)):
        Pi = Pf * share; mi = Pi / Ep * mp; I_f += eta * math.sqrt(2 * mi * Pi); mf += mi
    I = I_d + I_f; mx = (1 - hit) * (md + mf)
    heat = pick * (X + N_) + hit * (Pd + Pf)
    return dict(impulse_Ns=I, thrust_N=I * Hz, exhaust_m_s=I / mx, heat_W=heat * Hz, heat_over=heat * Hz / budget,
                jet_share=I * I / (2 * mx) / F, debris_m_s=math.sqrt(2 * Pd / md) if md > 0 else 0.0)


def main():
    s = S.load()[0]
    fi = json.loads(FI.read_text()); L = fi['ledger']
    o = json.loads(OPT.read_text()); noz = o['research']['nozzle']; budget = noz['budget_W']
    P_need = L['need']['fusion_per_engine_W']
    Hz0 = L['pulse']['Hz']
    coils = json.loads(COILS.read_text())
    k = ron.canon()
    v, srcp, E_op, cap_op = ron.configure(O.geometry(O.RESEARCH, 4.0, 4.0), k)
    ch_share_op = srcp['P_charged_W'] / P_need                  # the operating point's charged share of the mission fusion power
    built = O.coil_engineering(v, 1.0, 'Research coils as drawn (k = 1)')
    W_built = built['stored_J']; B_burn_built = built['B_burn_T']
    # nearest X-ray-facing surface: a cryostat skin, from the research geometry in the engine frame
    bx = coils['burn_x_moved']
    d_face = min(math.hypot(e['x'] - bx, e['r']) - e['cryostat_minor_m'] for e in coils['research_geometry'])
    wf = P['W_face']; depth = 1.0 / (wf['mu_cm2_g'] * wf['rho'] / 1000.0) / 100.0       # m, X-ray absorption length in tungsten
    alpha_th = wf['k'] / (wf['rho'] * wf['c'])
    stress_per_K = wf['E'] * wf['alpha'] / (1 - wf['nu'])

    rows = []
    for b in burns(s):
        F = b['fusion_J']; Hz = P_need / F
        E_burn = F * (b['plasma_share'] + b['escaped_share'])          # charged energy the field must stop, BURN basis
        E_opb = F * ch_share_op                                         # OPERATING basis (90 % charged)
        out = {}
        for basis, E in (('burn', E_burn), ('operating', E_opb)):
            c = ron.capture(v, E); kk = c['k']
            ce = O.coil_engineering(v, kk, basis)
            B = ce['B_burn_T']
            R_b = (3 * MU0 * E / (2 * math.pi * B * B)) ** (1 / 3) if B > 0 else None
            R_b_built = (3 * MU0 * E / (2 * math.pi * B_burn_built ** 2)) ** (1 / 3)
            out[basis] = dict(E_charged_J=E, k=kk, W_J=c['W_J'], W_over_E=c['W_J'] / E, B_burn_T=B, B_wind_T=ce['B_peak_max_T'],
                              hoop_GN=ce['hoop_total_MN'] / 1e3, Fx_max_GN=ce['Fx_max_MN'] / 1e3, structure_t=ce['structure_t'],
                              quench_dump_s=ce['quench_dump_s'], cavity_m=R_b, fits_built=c['W_J'] <= W_built,
                              ripple_built=E / W_built, cavity_built_m=R_b_built)
        e = engine(b, noz, Hz, budget)
        X = F * b['xray_share']
        fluence = X / (4 * math.pi * d_face ** 2)
        dT = fluence / (wf['rho'] * wf['c'] * depth)
        relax = depth ** 2 / alpha_th
        R_cav = out['burn']['cavity_built_m']
        t_transit = P['transit_L'] / e['debris_m_s'] if e['debris_m_s'] else None
        f_max = 1 / (P['transit_margin'] * t_transit) if t_transit else None
        v_inj = R_cav * Hz
        rho0 = b['mass_kg'] / (4 / 3 * math.pi * (b['R0_um'] * 1e-6) ** 3)
        rows.append(dict(label=b['label'], lever=b['lever'], cls=b['cls'], mass_factor=b['mass_factor'], mass_kg=b['mass_kg'],
                         R0_um=b['R0_um'], rho0_kg_m3=rho0, duration_ps=b['duration_ps'], fusion_J=F, gain=b['gain'],
                         burn_up=b['burn_up'], xray_share=b['xray_share'], neutron_share=b['neutron_share'],
                         plasma_share=b['plasma_share'], escaped_share=b['escaped_share'], Hz=Hz,
                         driver_abs_W=F / b['gain'] * Hz, driver_elec_W=F / b['gain'] * Hz / lg.DRIVER_WALLPLUG,
                         capture=out, thrust_N=e['thrust_N'], exhaust_m_s=e['exhaust_m_s'], heat_W=e['heat_W'],
                         heat_over=e['heat_over'], jet_share=e['jet_share'], debris_m_s=e['debris_m_s'],
                         transit_s=t_transit, f_max_Hz=f_max, rate_ok=f_max is None or Hz <= f_max,
                         v_inj_m_s=v_inj, inj_ok=v_inj <= P['v_inj_max'], fluence_J_m2=fluence, dT_K=dT,
                         stress_MPa=dT * stress_per_K / 1e6, fatigue_ok=dT * stress_per_K <= P['sigma_fatigue'],
                         ratchet=Hz * relax > 1.0, cycles_per_year=Hz * YEAR))
    base = next(r for r in rows if r['label'] == 'Target mass x1')
    for r in rows:
        r['heat_vs_base'] = r['heat_W'] / base['heat_W']; r['thrust_vs_base'] = r['thrust_N'] / base['thrust_N']
    # equal thrust: the frequency that gives the base thrust, and the heat that costs
    eq = [dict(label=r['label'], Hz=base['thrust_N'] / (r['thrust_N'] / r['Hz']),
               heat_over=r['heat_over'] * (base['thrust_N'] / r['thrust_N']),
               fusion_W=P_need * base['thrust_N'] / r['thrust_N'],
               W_burn_GJ=r['capture']['burn']['W_J'] / 1e9) for r in rows]
    # the coupled optimum under the constraints the drawn coils and the operation set
    ok = [r for r in rows if r['capture']['burn']['fits_built'] and r['inj_ok'] and r['fatigue_ok'] and r['rate_ok'] and r['cls'] != 'SPECULATIVE']
    pick = min(ok, key=lambda r: r['heat_W'] / r['thrust_N']) if ok else None
    for r in rows:
        r['fails'] = [n for n, good in (('capture field over the drawn coils', r['capture']['burn']['fits_built']),
                                         ('injection speed', r['inj_ok']), ('surface spike', r['fatigue_ok']),
                                         ('nozzle transit', r['rate_ok'])) if not good]
    # the window the per-pulse and the operating limits leave, on the size scan (mass x, everything else the design)
    size = [r for r in rows if r['lever'] == 'size']
    def interp(key, target):                     # mass factor at which a power law through the size scan meets the limit
        a, b = size[0], size[-1]
        ya, yb = a[key], b[key]
        n = math.log(yb / ya) / math.log(b['mass_factor'] / a['mass_factor'])
        return a['mass_factor'] * (target / ya) ** (1 / n)
    window = dict(mass_max_surface=interp('dT_K', P['sigma_fatigue'] / stress_per_K),
                  mass_min_injection=interp('v_inj_m_s', P['v_inj_max']),
                  dT_limit_K=P['sigma_fatigue'] / stress_per_K)
    window['gap'] = window['mass_min_injection'] / window['mass_max_surface']
    # what would open it: the face distance (fluence ~ 1/d^2) or a face that takes the spike (spread, renewed or reflected)
    base1 = next(r for r in rows if r['label'] == 'Target mass x1')
    window['face_m_for_x1'] = d_face * math.sqrt(base1['dT_K'] / window['dT_limit_K'])
    window['face_m_for_injection_size'] = d_face * math.sqrt(window['mass_min_injection'] * base1['dT_K'] / window['dT_limit_K'])
    compromise = min((r for r in rows if r['cls'] != 'SPECULATIVE'), key=lambda r: (len(r['fails']), r['heat_W'] / r['thrust_N']))
    # pulse energy each budget allows at the mission power
    lim = dict(
        E_max_fit_built_J=W_built / base['capture']['burn']['W_over_E'],
        E_max_fit_built_op_J=W_built / base['capture']['operating']['W_over_E'],
        fusion_max_fit_built_op_J=W_built / base['capture']['operating']['W_over_E'] / ch_share_op,
        Hz_min_fit_built_op=P_need / (W_built / base['capture']['operating']['W_over_E'] / ch_share_op))
    res = dict(cls='CALCULATED', source='lab/studies/vertex-compact-engine/vertex-pulse/pulse.py', P=P, P_need_W=P_need, Hz_design=Hz0,
               research=O.RESEARCH, nozzle=noz, charged_share_operating=ch_share_op, W_built_J=W_built, B_burn_built_T=B_burn_built,
               d_face_m=d_face, xray_depth_m=depth, relax_s=depth ** 2 / alpha_th, rows=rows, equal_thrust=eq, pick=pick and pick['label'], window=window,
               compromise=dict(label=compromise['label'], fails=compromise['fails']),
               limits=lim)
    (HERE / 'results').mkdir(exist_ok=True)
    (HERE / 'results' / 'pulse.json').write_text(json.dumps(res, indent=1))
    print(f"need {P_need / 1e12:.1f} TW/engine  built W {W_built / 1e9:.1f} GJ  B0 {B_burn_built:.2f} T  face {d_face:.2f} m  depth {depth * 1e6:.0f} um  op share {ch_share_op:.3f}")
    for r in rows:
        cb, co = r['capture']['burn'], r['capture']['operating']
        print(f"{r['label'][:42]:42s} F {r['fusion_J'] / 1e9:7.3f} GJ G {r['gain']:6.1f} X {r['xray_share']:.2f} f {r['Hz'] / 1e3:8.1f} kHz "
              f"W {cb['W_J'] / 1e9:7.2f}/{co['W_J'] / 1e9:7.1f} GJ  T {r['thrust_N'] / 1e6:5.2f} MN heat {r['heat_over']:7.0f}x "
              f"dT {r['dT_K']:7.1f} K vinj {r['v_inj_m_s'] / 1e3:6.1f} km/s fmax {r['f_max_Hz'] / 1e3 if r['f_max_Hz'] else 0:7.1f} rho {r['rho0_kg_m3']:.3g}")
    print('pick', res['pick'], 'compromise', res['compromise']); print(lim); print(window)
    for r in eq: print(r)


if __name__ == '__main__':
    main()
