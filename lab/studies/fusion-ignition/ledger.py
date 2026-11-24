"""Unified, time-dependent energy and particle ledger of one Vertex engine pulse (owner brief 2026-11-23 13:11Z).

One bookkeeping for every stage of the Fusion Ignition page: fuel injected -> driver heat -> target burn (R2-B, with every joule and
every nucleus tracked over time) -> charged plasma left at disassembly -> magnetic nozzle (directed, side, on hardware) -> impulse and
thrust, plus the heat each loss puts into the engine. Standard library only; reads the project's models and never changes them.

Model states. The studies behind the page were made under different operating assumptions. They are kept, not tuned to agree, and
every number on the page names the state it belongs to:

  MISSION   operating_point (WORKING): the approved ship's requirement; prescribes exhaust speed, directed efficiency 0.8, burn-up 0.8.
  DESIGN    vertex_engine C-02/C-04 (SPECULATIVE): the drawn engine's pulse point, sized to a quarter of the V4 research drive; assumes
            the research jet share (jet_TW / fusion_TW = 0.78) of every yield leaves as directed jet.
  COUPLED   this ledger (CALCULATED where marked): the design target and rate, burned by R2-B, nozzle shares from the compact study.
  STEADY    compact study source V2 (IMPORTED): radiation shares of a steady, magnetically confined plasma (n_e 1e21 m^-3), not a target.

The R2-B loop below is the same arithmetic as src/wayfarer/vertex_radiation.burn (the tests require identical results); it only adds
the bookkeeping that burn() does not return.

    python3 lab/studies/fusion-ignition/ledger.py      # prints the reconciliation
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
import vertex_magnet as vm  # noqa: E402
import vertex_radiation as vr  # noqa: E402
import vertex_engine as ve  # noqa: E402

MEV, KEV, AMU = vr.MEV, vr.KEV, vr.AMU
C_LIGHT = 299792458.0
A_NUC = dict(D=2, He3=3, T=3, alpha=4, p=1)          # nucleons per species (neutrons counted apart)
DRIVER_WALLPLUG = 0.5                                # ignition-failures: driver 50 % efficient (IMPORTED assumption)
RHO = [3.0, 10.0, 30.0, 60.0, None, 200.0]           # None: the design areal density (rhoR_for_yield)
TI = [30.0, 50.0, 70.0, 100.0]
MIX = [0.5, 1.0, 2.0]                                # D per 3He (by nuclei)


# ---------- the burn, with the full ledger -------------------------------------------------------------------------------------------

def burn(s, case, mass_kg=None, steps_max=200000, rows=72):
    """R2-B of one target with the energy and particle ledger. Same physics and time stepping as vertex_radiation.burn."""
    pz = vm.plasma(s)
    M = mass_kg or pz['mass_kg']; r_DHe = case['D_per_He3']
    m_pair = r_DHe * vr.M_ION['D'] + vr.M_ION['He3']
    N_He = M / (m_pair * AMU); N = dict(D=r_DHe * N_He, He3=N_He, T=0.0, alpha=0.0, p=0.0)
    N0 = dict(N); nn = 0.0
    rhoR = case['rhoR_g_cm2'] * 10.0
    R = math.sqrt(3.0 * M / (4.0 * math.pi * rhoR)); R0 = R
    Ti = case['Ti_keV']; Te = Ti * case['Te_over_Ti']; dep = case['deposition']
    E = dict(DHe3=0.0, DDn=0.0, DDp=0.0, DT=0.0); Ebr = Eadiab = En = Ei_dep = Ee_dep = Eesc = Eei = Enum = 0.0
    react = dict(DHe3=0.0, DDn=0.0, DDp=0.0, DT=0.0)
    t = 0.0; nsteps = 0
    E0 = 1.5 * (sum(N[k] * vr.Z_ION[k] for k in N) * Te + sum(N.values()) * Ti) * KEV
    hist = []; tei0 = None
    while nsteps < steps_max:
        V = 4.0 / 3.0 * math.pi * R ** 3
        n = {k: v / V for k, v in N.items()}
        ions = [(n[k], vr.Z_ION[k], vr.M_ION[k]) for k in n if n[k] > 0]
        ne = sum(a * b for a, b, _ in ions); ni = sum(a for a, _, _ in ions)
        rate = dict(DHe3=n['D'] * n['He3'] * vr.sigma_v('DHe3', Ti), DDn=0.5 * n['D'] ** 2 * vr.sigma_v('DDn', Ti),
                    DDp=0.5 * n['D'] ** 2 * vr.sigma_v('DDp', Ti), DT=n['D'] * n['T'] * vr.sigma_v('DT', Ti))
        Pf = {k: rate[k] * vr.Q[k] * MEV * V for k in rate}
        zeff = sum(a * b * b for a, b, _ in ions) / ne
        Pbr = vr.brems_W_m3(ne, Te, zeff) * V
        Pi = Pe = Pesc = 0.0
        for k, prods in vr.PRODUCTS.items():
            for sp, e_mev in prods.items():
                if sp == 'n':
                    continue
                Pc = rate[k] * e_mev * MEV * V
                fi = vr.ion_share(e_mev * 1e3, Te, vr.M_ION[sp], ions)
                Pi += fi * Pc * dep; Pe += (1.0 - fi) * Pc * dep; Pesc += (1.0 - dep) * Pc
        Pn = (rate['DDn'] * vr.PRODUCTS['DDn']['n'] + rate['DT'] * vr.PRODUCTS['DT']['n']) * MEV * V
        nu = sum(3.2e-9 * Z * Z * (q * 1e-6) * vr.lnlambda(ne, Te) / (A * (Te * 1e3) ** 1.5) for q, Z, A in ions)
        Pei = 1.5 * ne * V * (Ti - Te) * KEV * nu
        mi = sum(a * A for a, _, A in ions) / ni * AMU
        cs = math.sqrt((ne * Te + ni * Ti) * KEV / (ni * mi))
        dR = case['expansion'] * cs
        Ui = 1.5 * ni * V * Ti * KEV; Ue = 1.5 * ne * V * Te * KEV
        if tei0 is None:
            tei0 = 1.0 / max(nu, 1e-300)
        if nsteps % max(1, 1) == 0 and (nsteps % 25 == 0):
            hist.append(snapshot(t, Ti, Te, R, R0, M, ne, N, nn, E, Ebr, En, Eadiab, Ei_dep, Ee_dep, Eei, Ui, Ue, E0, Pf, Pbr, Pei, nu))
        rates = [abs(Pi + Pei) / Ui if Ui else 0, abs(Pe - Pei - Pbr) / Ue if Ue else 0, dR / R, rate['DHe3'] * V / max(N['He3'], 1.0)]
        dt = 0.01 / max(max(rates), 1e-30)
        Ui += (Pi - Pei) * dt; Ue += (Pe + Pei - Pbr) * dt
        Ti = max(Ui / (1.5 * ni * V * KEV), 0.01); Te = max(Ue / (1.5 * ne * V * KEV), 0.01)
        Rn = R + dR * dt; cool = (R / Rn) ** 2
        Eadiab += 1.5 * (ni * Ti + ne * Te) * V * KEV * (1.0 - cool); Ti *= cool; Te *= cool; R = Rn
        for k in rate:
            E[k] += Pf[k] * dt
        Ebr += Pbr * dt; En += Pn * dt; Ei_dep += Pi * dt; Ee_dep += Pe * dt; Eesc += Pesc * dt; Eei += Pei * dt
        d = rate['DHe3'] * V * dt; dn = rate['DDn'] * V * dt; dp = rate['DDp'] * V * dt; dtt = rate['DT'] * V * dt
        react['DHe3'] += d; react['DDn'] += dn; react['DDp'] += dp; react['DT'] += dtt; nn += dn + dtt
        N['D'] -= d + 2 * dn + 2 * dp + dtt; N['He3'] += dn - d; N['T'] += dp - dtt; N['alpha'] += d + dtt; N['p'] += d + dp
        for k in N:
            N[k] = max(N[k], 0.0)
        # bookkeeping only: the thermal energy of ions created or lost at fixed temperature (D-D-n and D-T turn two ions into one)
        Enum -= 1.5 * KEV * (Ti * (sum(N.values()) - ni * V) + Te * (sum(N[k] * vr.Z_ION[k] for k in N) - ne * V))
        t += dt; nsteps += 1
        if Ti < 2.0 or (sum(Pf.values()) < 1e-6 * max(sum(E.values()) / max(t, 1e-30), 1e-30) and t > 0):
            break
    V = 4.0 / 3.0 * math.pi * R ** 3; ni = sum(N.values()); ne = sum(N[k] * vr.Z_ION[k] for k in N)
    Ui = 1.5 * ni * Ti * KEV; Ue = 1.5 * ne * Te * KEV
    hist.append(snapshot(t, Ti, Te, R, R0, M, ne / V, N, nn, E, Ebr, En, Eadiab, Ei_dep, Ee_dep, Eei, Ui, Ue, E0, {k: 0.0 for k in E}, 0.0, 0.0, 0.0))
    Ef = sum(E.values())
    plasma = Eadiab + Ui + Ue                             # thermal and expansion energy of the charged plasma at the end of the burn
    resid = E0 + Ef - En - Ebr - Eesc - plasma - Enum                # Enum: thermal energy that left with the vanished ions
    mass_left = sum(N[k] * vr.M_ION[k] for k in N) * AMU
    fuel_left = (N['D'] * vr.M_ION['D'] + N['He3'] * vr.M_ION['He3']) * AMU
    nuc0 = sum(N0[k] * A_NUC[k] for k in N0); nuc1 = sum(N[k] * A_NUC[k] for k in N) + nn
    z0 = sum(N0[k] * vr.Z_ION[k] for k in N0); z1 = sum(N[k] * vr.Z_ION[k] for k in N)
    step = max(1, len(hist) // rows)
    return dict(
        case=dict(rhoR_g_cm2=case['rhoR_g_cm2'], Ti_keV=case['Ti_keV'], D_per_He3=r_DHe, Te_over_Ti=case['Te_over_Ti'], deposition=dep),
        mass_kg=M, R0_m=R0, duration_s=t, steps=nsteps,
        energy=dict(heat_in_J=E0, fusion_J=Ef, by_reaction_J=E, charged_born_J=Ef - En, neutron_J=En, xray_J=Ebr, escaped_charged_J=Eesc,
                    to_ions_J=Ei_dep, to_electrons_J=Ee_dep, ion_to_electron_J=Eei, plasma_J=plasma, expansion_J=Eadiab, number_change_J=Enum,
                    residual_J=resid, residual_share=resid / (E0 + Ef)),
        shares=dict(xray=Ebr / Ef, neutron=En / Ef, plasma=plasma / Ef, heat=E0 / Ef, gain=Ef / E0,
                    xray_of_input=Ebr / (Ef + E0), plasma_of_input=plasma / (Ef + E0)),
        particles=dict(injected=dict(D=N0['D'], He3=N0['He3']), final=dict(N), neutrons=nn, reactions=react,
                       nucleons=[nuc0, nuc1], charge=[z0, z1],
                       burn_fraction_D=1.0 - N['D'] / N0['D'], burn_fraction_He3=1.0 - N['He3'] / N0['He3'],
                       burn_fraction_mass=1.0 - fuel_left / M, reacted_kg=M - fuel_left, mass_defect_kg=Ef / C_LIGHT ** 2,
                       final_ion_mass_kg=mass_left, mass_check=(M - Ef / C_LIGHT ** 2 - mass_left - nn * 1.00866 * AMU) / M),
        tei0_s=tei0, history=hist[::step] + ([hist[-1]] if (len(hist) - 1) % step else []),
        history_fields=HIST)


HIST = ['t_s', 'Ti_keV', 'Te_keV', 'R_over_R0', 'rho_g_cc', 'ne_m3', 'D', 'He3', 'alpha', 'p', 'T', 'n', 'fusion_J', 'xray_J', 'neutron_J',
        'expansion_J', 'ions_J', 'electrons_J', 'Px_over_Pf', 'tei_over_tburn']


def snapshot(t, Ti, Te, R, R0, M, ne, N, nn, E, Ebr, En, Eadiab, Ei, Ee, Eei, Ui, Ue, E0, Pf, Pbr, Pei, nu):
    V = 4.0 / 3.0 * math.pi * R ** 3
    pf = sum(Pf.values())
    r = lambda v: float(f'{v:.4g}')
    return [r(t), r(Ti), r(Te), r(R / R0), r(M / V * 1e-3), r(ne), r(N['D']), r(N['He3']), r(N['alpha']), r(N['p']), r(N['T']), r(nn),
            r(sum(E.values())), r(Ebr), r(En), r(Eadiab), r(Ui), r(Ue), r(Pbr / pf) if pf else 0.0, r(1.0 / max(nu, 1e-300) / max(t, 1e-15)) if nu else 0.0]


def base_case(s):
    return next(x for x in vr.config(s)['cases'] if x['id'] == 'CONSERVATIVE')


def design_rhoR(s):
    return round(vr.rhoR_for_yield(s, base_case(s)), 1)


def grid(s):
    """The burn over areal density x start temperature x fuel mix, for the design target mass. Ledger summaries only (no history)."""
    b = base_case(s); rr = design_rhoR(s); out = {}
    for r in [rr if x is None else x for x in RHO]:
        for T in TI:
            for mix in MIX:
                L = burn(s, dict(b, rhoR_g_cm2=r, Ti_keV=T, D_per_He3=mix), rows=2)
                e, p = L['energy'], L['particles']
                out[key(r, T, mix)] = dict(fusion_J=e['fusion_J'], heat_J=e['heat_in_J'], xray_J=e['xray_J'], neutron_J=e['neutron_J'],
                                           plasma_J=e['plasma_J'], residual_J=e['residual_J'], number_change_J=e['number_change_J'], burn_fraction=p['burn_fraction_mass'],
                                           reacted_kg=p['reacted_kg'], neutrons=p['neutrons'], duration_s=L['duration_s'],
                                           Ti_peak_keV=max(h[1] for h in L['history']) if L['history'] else T)
    return dict(rhoR=[rr if x is None else x for x in RHO], Ti=TI, mix=MIX, design=key(rr, b['Ti_keV'], b['D_per_He3']), cells=out)


def key(r, T, mix):
    return f'{r:g}|{T:g}|{mix:g}'


# ---------- one pulse through the engine ----------------------------------------------------------------------------------------------

def pulse(cell, mass_kg, Hz, noz, budget_W, mirror=0.0, h2_kg=0.0):
    """Energy and mass of one pulse from the burn cell to thrust, the same arithmetic as the page (web/engineering/fusion-ignition.js
    pulseLedger). noz: eta (directed share of the plasma energy), hit (share striking hardware), pickup (share of X-ray and neutron energy
    absorbed by the engine). mirror: share of the absorbed X-rays a grazing mirror sends back out. h2_kg: hydrogen added per pulse; how it
    takes energy from the plasma is not modelled anywhere, so a nonzero value returns no thrust and says so."""
    F, Q, X, N_, P = cell['fusion_J'], cell['heat_J'], cell['xray_J'], cell['neutron_J'], cell['plasma_J']
    # Momentum-consistent nozzle (vertex-extraction, 2026-11-24): eta is the mean axial cosine of the launched debris (hits count zero),
    # so the impulse is eta sqrt(2 m P) for equal-speed debris; the struck share stays in the engine (its mass deposited, its energy heat).
    # Until 2026-11-24 the ledger used jet = eta P carried by every ion, which overstated the impulse by 1 / sqrt(eta).
    m_deb = mass_kg - F / C_LIGHT ** 2                  # fuel left after the mass defect, all of it in the expanding plasma
    hit = noz['hit'] * P; m_exh = (1.0 - noz['hit']) * m_deb; dep = noz['hit'] * m_deb
    x_abs = noz['pickup'] * X * (1.0 - mirror); n_abs = noz['pickup'] * N_
    coupled = h2_kg == 0.0
    I = noz['eta'] * math.sqrt(2.0 * m_deb * P) if coupled else None
    jet = I * I / (2.0 * m_exh) if coupled and m_exh > 0 else noz['eta'] * P
    side = max(P - jet - hit, 0.0)
    v = I / m_exh if coupled and m_exh > 0 else None
    heat = x_abs + n_abs + hit
    return dict(fusion_J=F, heat_in_J=Q, xray_J=X, neutron_J=N_, plasma_J=P, jet_J=jet, side_J=side, hit_J=hit, x_abs_J=x_abs, n_abs_J=n_abs,
                residual_J=cell.get('residual_J', 0.0), number_change_J=cell.get('number_change_J', 0.0), engine_heat_J=heat, impulse_Ns=I, exhaust_m_s=v, mass_kg=mass_kg, exhaust_mass_kg=m_exh, debris_kg=m_deb, deposited_kg=dep, deposited_kg_s=dep * Hz,
                reacted_kg=cell['reacted_kg'], burn_fraction=cell['burn_fraction'], Hz=Hz, fusion_W=F * Hz, jet_W=jet * Hz,
                thrust_N=I * Hz if coupled else None, engine_heat_W=heat * Hz, heat_over=heat * Hz / budget_W,
                driver_abs_W=Q * Hz, driver_elec_W=Q * Hz / DRIVER_WALLPLUG, fuel_kg_s=mass_kg * Hz, reacted_kg_s=cell['reacted_kg'] * Hz,
                jet_share=jet / F, coupled=coupled, budget_W=budget_W,
                limit=None if coupled else 'Hydrogen added to the exhaust: how fusion energy reaches cold hydrogen is not modelled (SPECULATIVE), so '
                                           'no exhaust speed or thrust is computed.')


def nozzle_of(imp, variant, field='1', geo_sky=None):
    """eta, hit share and the engine's effective X-ray/neutron pickup for a compact variant (IMPORTED, lab/studies/vertex-compact-engine/vertex-compact aebbb0d).
    pickup_piped is the compact study's figure: the part of its piped heat that is not charged strikes, over its X-ray, synchrotron and
    neutron power (a residual of two large numbers, from the steady-plasma source; see the audit in lab/studies/vertex-compact-engine/vertex-source). With geo_sky (the
    thermal study's trace of every drawn part of the C1 engine, 63.1 %) the pickup is scaled so that C1 equals the geometric share and the
    other variants keep their ratio to C1 (audit decision 2026-11-24)."""
    src = imp['source']; v = imp['variants'][variant]
    base = 'C1' if variant in ('C1', 'C2') else 'C3'
    sc = imp['field_scan'].get(f'{base}|{field}')
    neutral = src['P_brems_W'] + src['P_sync_W'] + src['P_n_W']
    piped_share = lambda vv: (vv['piped_four_W'] / 4 - vv['hit_share'] * src['P_charged_W']) / neutral
    pickup_piped = piped_share(v)
    pickup = pickup_piped * (geo_sky / piped_share(imp['variants']['C1'])) if geo_sky else pickup_piped
    eta, hit = (sc['eta'], sc['hit']) if sc else (v['eta'], v['hit_share'])
    return dict(eta=eta, hit=hit, pickup=pickup, pickup_piped=pickup_piped, pickup_source='geometric trace (thermal study)' if geo_sky else
                'compact study piped share', variant=variant, field=field, budget_W=src['drive_W'] / 4)


# ---------- the four model states and their reconciliation ---------------------------------------------------------------------------

def states(s, nd, imp, L):
    """The four model states as rows of one ledger (per engine, per second), each with its source and what it assumes."""
    import vertex_plasma as vp
    p = vm.plasma(s); r = s['vertex_research']; sp = ve.config(s)['speculative']; src = imp['source']
    q = s['physics']['operating_point']
    need_e = nd['fusion_W'] / 4
    # MISSION: the prescribed ledger (no burn physics: only the directed share and the burn-up)
    reacted = need_e / q['dhe3_specific_energy_J_kg']
    mission = dict(id='MISSION', label='Mission requirement', cls='SPEC', fusion_W=need_e, jet_W=need_e * q['directed_efficiency'],
                   undirected_W=need_e * (1 - q['directed_efficiency']), thrust_N=nd['thrust_N'] / 4, exhaust_m_s=nd['exhaust_m_s'],
                   reacted_kg_s=reacted, injected_kg_s=reacted / q['burnup'], recovered_kg_s=reacted / q['burnup'] * (1 - q['burnup']) * q['recovery'],
                   lost_kg_s=reacted / q['burnup'] * (1 - q['burnup']) * (1 - q['recovery']), hydrogen_kg_s=nd['mass_flow_kg_s'] / 4 - reacted
                   - reacted / q['burnup'] * (1 - q['burnup']) * (1 - q['recovery']), burnup=q['burnup'], directed=q['directed_efficiency'],
                   assumes='operating_point (WORKING): exhaust 19,201 km/s, directed efficiency 0.8, burn-up 0.8 with 95 % of the unburned fuel '
                           'recovered, hydrogen makes up the rest of the jet. It prescribes the split; it does not model a burn or a nozzle.',
                   source='src/wayfarer/operating_point.py (physics.operating_point)')
    # DESIGN: the drawn engine's pulse point with the research jet share
    c4 = vr.audit_1_4(s)
    design = dict(id='DESIGN', label='Engine pulse design point', cls='SPECULATIVE', yield_J=p['yield_J'], Hz=p['pulse_Hz'],
                  fusion_W=p['yield_J'] * p['pulse_Hz'], jet_W=p['energy_J']['design'] * p['pulse_Hz'], jet_share=p['charged_share'],
                  xray_W=c4['xray_J'] * p['pulse_Hz'], neutron_W=c4['neutron_J'] * p['pulse_Hz'], mass_kg=p['mass_kg'],
                  exhaust_m_s=p['exhaust_m_s'], thrust_N=math.sqrt(2 * p['mass_kg'] * p['energy_J']['design']) * p['pulse_Hz'],
                  reacted_kg=vr.implied_target(s)['burned_kg'], implied_burn_fraction=vr.implied_target(s)['implied_burn_fraction'],
                  assumes=f'vertex_engine C-02 (yield held at the research armour fluence) and C-04 (rate for {sp["design_power_share"]:g} of the V4 '
                          f'research fusion power): the four engines together are one V4 research drive ({r["fusion_TW"]:.1f} TW, {r["thrust_MN"]:.2f} MN, '
                          f'converged for a {r["departure_t"]:,.0f} t ship). The jet share {p["charged_share"]:.2f} is the research drive\'s jet power '
                          'over its fusion power, applied to every yield; the target mass is chosen so that jet leaves at 19,201 km/s.',
                  source='src/wayfarer/vertex_engine.py calculations, vertex_magnet.plasma, vertex_radiation.audit_1_4')
    dp = L['pulse']
    coupled = dict(id='COUPLED', label='Coupled pulse (this ledger)', cls='CALCULATED', yield_J=dp['fusion_J'], Hz=dp['Hz'], fusion_W=dp['fusion_W'],
                   jet_W=dp['jet_W'], jet_share=dp['jet_share'], xray_W=dp['xray_J'] * dp['Hz'], neutron_W=dp['neutron_J'] * dp['Hz'],
                   mass_kg=dp['mass_kg'], exhaust_m_s=dp['exhaust_m_s'], thrust_N=dp['thrust_N'], reacted_kg=dp['reacted_kg'],
                   burn_fraction=dp['burn_fraction'],
                   assumes='The design target (mass, areal density, start temperature) and rate, burned by R2-B with every joule and nucleus booked; '
                           'the nozzle shares of the drawn cluster (C1) from the compact study. Compression and driver coupling are OPEN.',
                   source='lab/studies/fusion-ignition/ledger.py (R2-B as vertex_radiation.burn) + lab/studies/vertex-compact-engine/vertex-compact aebbb0d nozzle shares')
    steady_case = json_case()
    steady = dict(id='STEADY', label='Steady-plasma source (losses study)', cls='IMPORTED', fusion_W=src['fusion_per_engine_W'], Hz=5697.0,
                  yield_J=src['fusion_per_engine_W'] / 5697.0, xray_share=src['P_brems_W'] / src['fusion_per_engine_W'],
                  sync_share=src['P_sync_W'] / src['fusion_per_engine_W'], neutron_share=src['P_n_W'] / src['fusion_per_engine_W'],
                  charged_share=src['P_charged_W'] / src['fusion_per_engine_W'], regime=steady_case,
                  assumes=f'Vertex 1.6B case S5 optimistic bracket (fuel V2): a steady plasma at n_e {steady_case["ne_m3"]:.0e} m^-3 with '
                          f'Ti {steady_case["Ti_keV"]:.0f} keV, 3He {steady_case["THe_keV"]:.0f} keV, Te {steady_case["Te_keV"]:.0f} keV, '
                          f'{steady_case["channelled_share"]:.0%} of the product energy channelled to ions; it does not sustain itself '
                          f'(gain {steady_case["gain"]:.2f}, auxiliary heating {steady_case["aux_share"]:.0%} of fusion). The compact study applied '
                          'these shares at the mission power per engine and the design rate.',
                  source='lab/studies/vertex-compact-engine/vertex-ron/ron.py source() <- lab/studies/vertex-compact-engine/magneto-photonic-nozzle/mpn.py sources() <- references/evidence/vertex_source.json')
    return [mission, design, coupled, steady]


def json_case():
    import json
    vs = json.loads((ROOT / 'references/evidence/vertex_source.json').read_text())
    b = vs['cases']['S5']['brackets']['optimistic']['best']
    keep = ('Ti_keV', 'THe_keV', 'Te_keV', 'ne_m3', 'brems_share', 'sync_share', 'neutron_share', 'charged_share', 'channelled_share',
            'to_electrons_share', 'gain', 'aux_share', 'sustained')
    return {k: b[k] for k in keep}


def reconcile(s, nd, imp, L, st):
    """The three reported differences and the fuel masses: where each number comes from, why they differ, what the coupled ledger says."""
    S_ = {x['id']: x for x in st}
    mis, des, cou, ste = S_['MISSION'], S_['DESIGN'], S_['COUPLED'], S_['STEADY']
    r = s['vertex_research']; q = s['physics']['operating_point']
    b = L['design_burn']; e = b['energy']; pp = b['particles']
    # time scales at the design burn start: electron-ion exchange against the burn
    tei, tb = b['tei0_s'], b['duration_s']
    H = b['history']; te_pk = max(h[2] for h in H); ti_pk = max(h[1] for h in H); ratio_0 = H[0][18]
    pf = [(H[i + 1][12] - H[i][12]) / max(H[i + 1][0] - H[i][0], 1e-30) for i in range(len(H) - 1)]
    ratio_pk = H[max(range(len(pf)), key=lambda i: pf[i])][18]
    at = lambda f: next(h[18] for h in H if h[12] >= f * e['fusion_J'])
    ratio_50, ratio_90 = at(0.5), at(0.9)
    mission_F, cou_F = mis['thrust_N'], cou['thrust_N']
    need_Hz = mission_F / L['pulse']['impulse_Ns']
    items = [
        dict(id='R1', title='Power: 8.9 TW per engine at the pulse design point, 65.3 TW needed', verdict='EXPLAINED: different ships, kept apart',
             values=dict(design_W=des['fusion_W'], mission_W=mis['fusion_W'], ratio=mis['fusion_W'] / des['fusion_W'],
                         design_thrust_N=des['thrust_N'], mission_thrust_N=mis['thrust_N'], research_departure_t=r['departure_t'],
                         mission_departure_t=nd['departure_t']),
             why=f'The engine was sized (vertex_engine design_power_share 0.25) so that four engines equal one V4 research drive: '
                 f'{r["fusion_TW"]:.1f} TW and {r["thrust_MN"]:.2f} MN, converged for a {r["departure_t"]:,.0f} t research ship. The mission '
                 f'requirement is the approved {nd["departure_t"]:,.0f} t ship at {nd["thrust_N"] / 1e6:.1f} MN (0.5 g). Neither number is wrong; the '
                 'drawn engine was never sized for the approved ship. The gap stays OPEN; no coefficient is changed to close it.',
             coupled=f'With the burn physics coupled (R3) the design point gives {cou_F * 4 / 1e6:.2f} MN for four engines, not {des["thrust_N"] * 4 / 1e6:.2f} MN. '
                     f'To give the mission thrust with this target each engine would fire {need_Hz:,.0f} times a second '
                     f'({need_Hz * L["pulse"]["fusion_J"] / 1e12:,.0f} TW of fusion per engine) and the exhaust would leave at '
                     f'{L["pulse"]["exhaust_m_s"] / 1e3:,.0f} km/s instead of {nd["exhaust_m_s"] / 1e3:,.0f} km/s; the engine would take up '
                     f'{L["pulse"]["heat_over"] * need_Hz / L["pulse"]["Hz"]:,.0f} times its radiator share.',
             need_Hz=need_Hz, need_fusion_W=need_Hz * L['pulse']['fusion_J'], need_heat_over=L['pulse']['heat_over'] * need_Hz / L['pulse']['Hz']),
        dict(id='R2', title='X-rays: 85 % of the energy in the target burn, 6.3 % in the losses stage', verdict='EXPLAINED: different plasmas; the losses stage used the wrong regime for a pulsed target',
             values=dict(target=e['xray_J'] / e['fusion_J'], steady=ste['xray_share'] + ste['sync_share'], steady_brems=ste['xray_share'],
                         target_ne_m3=b['history'][0][5], steady_ne_m3=ste['regime']['ne_m3'], tei_s=tei, burn_s=tb,
                         instant_start=ratio_0, instant_at_peak=ratio_pk, instant_half=ratio_50, instant_90=ratio_90, Te_peak_keV=te_pk, Ti_peak_keV=ti_pk),
             why=f'The 6.3 % is the instantaneous bremsstrahlung of a steady plasma at n_e {ste["regime"]["ne_m3"]:.0e} m^-3 held at Te '
                 f'{ste["regime"]["Te_keV"]:.0f} keV while the ions run at {ste["regime"]["Ti_keV"]:.0f}-{ste["regime"]["THe_keV"]:.0f} keV, with '
                 f'{ste["regime"]["channelled_share"]:.0%} of the product energy channelled to ions and auxiliary heating of '
                 f'{ste["regime"]["aux_share"]:.0%} of the fusion power (not self-sustaining). In the target (n_e about {b["history"][0][5]:.0e} m^-3) '
                 f'nothing channels or removes the product energy: {e["to_electrons_J"] / max(e["to_electrons_J"] + e["to_ions_J"], 1e-30):.0%} of it goes '
                 f'straight to the electrons, which reach {te_pk:.0f} keV (ions {ti_pk:.0f} keV). At that temperature bremsstrahlung, with its '
                 f'relativistic terms, is {ratio_0:.0%} of the fusion power at the start, {ratio_50:.0%} when half the yield is made and '
                 f'{ratio_90:.0%} at 90 %: as the fuel burns out and the target expands, the heat the electrons hold radiates faster than new fusion '
                 'replaces it. '
                 'The 85 % is that energy integrated over the burn. The two are different regimes; neither '
                 'is tuned.',
             coupled='The coupled ledger uses the target burn for the pulsed engine. The losses stage now shows the coupled X-rays and keeps the '
                     'steady-plasma figure as a separate, labelled regime.'),
        dict(id='R3', title='Charged energy: 78 % assumed by the engine, 17 % left in the plasma', verdict='INCONSISTENT: the design point assumes more jet than its own burn leaves',
             values=dict(assumed=des['jet_share'], born_charged=e['charged_born_J'] / e['fusion_J'], left=e['plasma_J'] / e['fusion_J'],
                         jet_coupled=cou['jet_share'], design_exhaust=des['exhaust_m_s'], coupled_exhaust=cou['exhaust_m_s']),
             why=f'The 0.78 is not a charged-product share: it is the V4 research drive\'s jet power over its fusion power '
                 f'({r["jet_TW"]:.2f} / {r["fusion_TW"]:.2f} TW), applied to every pulse, and it sets the target mass (6.6 mg) and the 19,201 km/s exhaust. '
                 f'At birth {e["charged_born_J"] / e["fusion_J"]:.1%} of the fusion energy is charged (only D-D side reactions make neutrons). But the '
                 f'products cannot leave a target this dense: they heat it, the electrons radiate, and when the burn ends {e["plasma_J"] / e["fusion_J"]:.1%} '
                 'of the fusion energy is still plasma energy that a nozzle could use. The burn that makes the design yield cannot also deliver the '
                 'design jet.',
             coupled=f'Plasma {e["plasma_J"] / e["fusion_J"]:.1%} of fusion x nozzle {L["noz"]["eta"]:.2f} (C1) = {cou["jet_share"]:.1%} jet; the exhaust '
                     f'leaves at {cou["exhaust_m_s"] / 1e3:,.0f} km/s and the design pulse gives {cou["thrust_N"] / des["thrust_N"]:.0%} of the design thrust.'),
        dict(id='R4', title='Fuel masses: injected or reacted', verdict='MIXED: now booked separately',
             values=dict(target_injected_kg=b['mass_kg'], target_reacted_kg=pp['reacted_kg'], burn_fraction=pp['burn_fraction_mass'],
                         implied_burn_fraction=des['implied_burn_fraction'], design_reacted_kg=des['reacted_kg'],
                         mission_reacted_kg_s=mis['reacted_kg_s'], mission_injected_kg_s=mis['injected_kg_s'], mission_lost_kg_s=mis['lost_kg_s'],
                         mission_species_t=nd['species_t'], burnup=q['burnup'], recovery=q['recovery'], design_h2_note=True),
             why=f'Mission (operating_point.species): the D and 3He tonnes are REACTED fuel; the tanks feed {1 / q["burnup"]:.2f} times that '
                 f'(burn-up {q["burnup"]:g}) and get {q["recovery"]:.0%} of the unburned part back. The unrecovered feed, '
                 f'{mis["lost_kg_s"] / mis["reacted_kg_s"]:.2%} of the reacted mass, leaves in the jet but is counted in the hydrogen line, so the 3He and D lines understate the fuel the '
                 f'tanks lose by that much (a bookkeeping note for the owner, not changed here). Engine pulse: the old fuel stage showed the reacted '
                 f'D and 3He ({des["reacted_kg"] * 1e6:.2f} mg, from the yield and the D-3He energy alone) as "per pulse"; the injected target is '
                 f'{b["mass_kg"] * 1e6:.2f} mg. Its "burned share {des["implied_burn_fraction"]:.0%}" is that ratio, and the burn agrees: it consumes '
                 f'{pp["burn_fraction_mass"]:.0%} of the injected fuel by mass. The ignition stage\'s "burn fraction {pp["burn_fraction_D"]:.0%}" is the share '
                 'of the deuterium used (D-D side reactions use two deuterons and little energy), so it is now labelled as such. '
                 'A pulsed target has no recovery: its unburned fuel leaves with the exhaust. The fuel stage also divided the mission hydrogen flow '
                 'by the design pulse rate, mixing two states; the coupled ledger adds no hydrogen, because no model says how it would be heated.',
             coupled=f'The ledger books per pulse: injected {b["mass_kg"] * 1e6:.2f} mg, reacted {pp["reacted_kg"] * 1e6:.2f} mg '
                     f'({pp["burn_fraction_mass"]:.0%}), mass turned into energy {pp["mass_defect_kg"] * 1e6:.4f} mg, exhaust {L["pulse"]["exhaust_mass_kg"] * 1e6:.2f} mg.'),
    ]
    return items


def build(s, nd, imp, geo_sky=None):
    b = base_case(s); rr = design_rhoR(s); p = vm.plasma(s)
    design = burn(s, dict(b, rhoR_g_cm2=rr))
    G = grid(s)
    noz = nozzle_of(imp, 'C1', geo_sky=geo_sky)
    cell = G['cells'][G['design']]
    pl = pulse(cell, p['mass_kg'], p['pulse_Hz'], noz, noz['budget_W'])
    st_ = ve.stations(s)
    # the design point as a ledger: its own prescribed split (audit_1_4: jet share, 1 % neutrons, the rest X-rays), every jet joule directed,
    # driver heat at gain 100 (ignition-failures), so it reads in the same rows as the coupled pulse
    c4 = vr.audit_1_4(s); it = vr.implied_target(s)
    design_cell = dict(fusion_J=p['yield_J'], heat_J=p['yield_J'] / 100, xray_J=c4['xray_J'], neutron_J=c4['neutron_J'], plasma_J=p['energy_J']['design'],
                       residual_J=p['yield_J'] / 100, reacted_kg=it['burned_kg'], burn_fraction=it['implied_burn_fraction'])
    pd = pulse(design_cell, p['mass_kg'], p['pulse_Hz'], dict(noz, eta=1.0, hit=0.0), noz['budget_W'])
    L = dict(pulse=pl, noz=noz, design_burn=design)
    st = states(s, nd, imp, L)
    v_plasma = math.sqrt(2 * pl['plasma_J'] / pl['debris_kg'])
    timeline = [
        dict(id='inject', title='Target flight to the burn point', t0=-1.0 / p['pulse_Hz'], t1=0.0, cls='SPECULATIVE',
             note='One target in flight per period (vertex_engine C-08); launcher and tracking are VTX-S2.'),
        dict(id='compress', title='Compression and heating', t0=None, t1=0.0, cls='OPEN',
             note=f'Not modelled: the burn starts from a compressed sphere holding {pl["heat_in_J"] / 1e6:.0f} MJ of heat. The driver must put at least '
                  'that into the fuel; its coupling efficiency is OPEN.'),
        dict(id='burn', title='Burn', t0=0.0, t1=design['duration_s'], cls='CALCULATED', note='R2-B with the full ledger (history below).'),
        dict(id='expand', title='Plasma to the nozzle exit', t0=design['duration_s'], t1=abs(st_['exit'] - st_['burn']) / v_plasma, cls='CALCULATED',
             note=f'The plasma leaves at about {v_plasma / 1e3:,.0f} km/s (its energy over its mass) and crosses the {abs(st_["exit"] - st_["burn"]):.1f} m to the exit; '
                  'the nozzle shares are IMPORTED test-particle results, so how the energy turns inside the nozzle is not resolved in time.'),
        dict(id='next', title='Next target', t0=1.0 / p['pulse_Hz'], t1=1.0 / p['pulse_Hz'], cls='SPECULATIVE', note='Period of the design rate.'),
    ]
    rec = reconcile(s, nd, imp, L, st)
    checks = dict(energy_residual_share=design['energy']['residual_share'], nucleons=design['particles']['nucleons'],
                  charge=design['particles']['charge'], mass_check=design['particles']['mass_check'],
                  pulse_balance=(pl['fusion_J'] + pl['heat_in_J'] - pl['xray_J'] - pl['neutron_J'] - pl['plasma_J'] - pl['residual_J'] - pl['number_change_J']) / pl['fusion_J'],
                  nozzle_balance=(pl['plasma_J'] - pl['jet_J'] - pl['side_J'] - pl['hit_J']) / pl['plasma_J'])
    noz_all = {f'{v}|{f}': nozzle_of(imp, v, f, geo_sky=geo_sky) for v in imp['variants'] for f in ('1', '2', '4')}
    return dict(cls='CALCULATED', source='lab/studies/fusion-ignition/ledger.py', design=dict(
                    case=design['case'], mass_kg=design['mass_kg'], R0_m=design['R0_m'], duration_s=design['duration_s'], energy=design['energy'],
                    shares=design['shares'], particles={k: v for k, v in design['particles'].items()}, tei0_s=design['tei0_s'],
                    history=design['history'], history_fields=HIST),
                grid=G, pulse=pl, design_cell=design_cell, pulse_design=pd, nozzle=noz_all, states=st, reconcile=rec, timeline=timeline, checks=checks,
                need=dict(thrust_per_engine_N=nd['thrust_N'] / 4, exhaust_m_s=nd['exhaust_m_s'], fusion_per_engine_W=nd['fusion_W'] / 4),
                wallplug=DRIVER_WALLPLUG, target_mass_kg=p['mass_kg'], design_Hz=p['pulse_Hz'],
                limits=['Compression and driver coupling are not modelled (OPEN): the driver figures are lower bounds at full coupling and '
                        f'{DRIVER_WALLPLUG:.0%} wall-plug efficiency (ignition-failures assumption).',
                        'Nozzle shares are IMPORTED from test particles at birth energies and burn-debris speed in the vacuum field; the expanding '
                        'plasma\'s own response (detachment, collective effects) is not modelled.',
                        'Every fusion product deposits its energy inside the target (R2-B deposition 1.0); the reactivity is held at the '
                        'Bosch-Hale fit limit (190 keV) where the ions run hotter.',
                        'X-rays escape the target freely (R2-B: Compton depth 0.1-1 only downshifts them).',
                        'Hydrogen propellant coupling is not modelled; with hydrogen the ledger returns no thrust.',
                        'The steady-plasma levers (polarisation, hot-ion mode, 3He heating) belong to the steady regime and are not coupled to the '
                        'target burn.'])


if __name__ == '__main__':
    import json
    import spec as S
    import operating_point as op
    s = S.load()[0]
    sys.path.insert(0, str(HERE))
    import model
    nd = model.need(s); imp = json.loads(model.IMPORT.read_text())
    d = build(s, nd, imp)
    for r in d['reconcile']:
        print(r['id'], r['verdict']); print('  ', r['why']); print('  ', r['coupled'])
    print('checks', d['checks'])
    for x in d['states']:
        print(x['id'], {k: v for k, v in x.items() if isinstance(v, float)})
