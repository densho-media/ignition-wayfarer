"""Energy at the source: how the D-3He products give their energy to ions and electrons, and what each target lever does to the yield,
burn-up, radiation, extractable energy and thrust (owner brief 2026-11-24 06:43Z, Q-TH-3). WORK, not canon.

Every burn is lab/studies/fusion-ignition/ledger.burn (the R2-B model of the page, every joule and nucleus booked). The study changes only
the case it is given, or, for spin polarisation, multiplies the D-3He reactivity it reads. Nothing here changes the spec or the models.

    python3 lab/studies/vertex-compact-engine/vertex-source/source.py        # about 3 minutes; writes results/source.json

Classes: CALCULATED (the burn model), ANALYTIC (closed forms), PROTOTYPE (choices marked P[...]), SPECULATIVE (polarisation survival,
hot-tamper opacity, advanced-technology levers).
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
sys.path.insert(0, str(ROOT / 'lab/studies/fusion-ignition'))
sys.path.insert(0, str(ROOT / 'lab/studies/vertex-compact-engine/magneto-photonic-nozzle'))
import spec as S  # noqa: E402
import vertex_radiation as vr  # noqa: E402
import ledger as lg  # noqa: E402
import mpn  # noqa: E402

MEV, KEV, AMU = vr.MEV, vr.KEV, vr.AMU
E_CHARGE = 1.602176634e-19
FI = ROOT / 'lab/studies/fusion-ignition/results/fusion_ignition.json'
TH = ROOT / 'lab/studies/vertex-compact-engine/vertex-thermal/results/thermal.json'

P = dict(
    pol_gain=1.5,              # D-3He reactivity with both nuclei spin-polarised parallel (Kulsrud et al. 1982: x1.5); SPECULATIVE survival
    pol_DD=1.0,                # D-D left unchanged (its suppression is disputed); PROTOTYPE
    refire=0.3,                # share of the energy a hot, optically thick tamper re-radiates before it expands; PROTOTYPE (0.1-0.6 shown)
    tamper_mats=('LiH', 'C_diamond', 'W'),
    tamper_sigma=(0.01, 0.1, 0.3, 1.0, 3.0),     # g/cm2
)


# ---------- 1. where the products' energy goes ---------------------------------------------------------------------------------------

def slowing(ne, ions):
    """Critical energy, the share each product gives the ions, and its slowing time and range against electrons (ANALYTIC)."""
    rows = []
    for Te in (5, 10, 20, 30, 50, 70, 100, 150, 200, 300, 500):
        row = dict(Te_keV=Te)
        for sp, E in (('p', 14.68), ('alpha', 3.67)):
            A = vr.M_ION[sp]; Z = vr.Z_ION[sp]
            Ec = 14.8 * A * Te * (sum(n * z * z / a for n, z, a in ions) / sum(n * z for n, z, a in ions)) ** (2.0 / 3.0)
            fi = vr.ion_share(E * 1e3, Te, A, ions)
            lnL = vr.lnlambda(ne, Te)
            tau = 6.27e8 * A * (Te * 1e3) ** 1.5 / (Z * Z * ne * 1e-6 * lnL)     # Spitzer electron drag time (s; Te in eV, ne in cm^-3)
            v = math.sqrt(2 * E * MEV / (A * AMU))
            row[sp] = dict(E_MeV=E, Ec_keV=Ec, to_ions=fi, tau_s=tau, range_m=v * tau / 2)
        rows.append(row)
    return rows


def brems_ratio():
    """Bremsstrahlung over fusion power for a burning D-3He mix (ANALYTIC, density cancels), at Te = Ti and in a hot-ion plasma."""
    out = []
    for T in (30, 50, 70, 100, 150, 200, 300):
        a = vr.ratio_at(T, 1.0, 1.0); b = vr.ratio_at(T, 0.5, 1.0); c = vr.ratio_at(T, 1.0, 0.33)
        out.append(dict(Ti_keV=T, equal=a['photon'], hot_ion=b['photon'], he3_rich=c['photon'], dd_neutron=a['neutron_DD']))
    return out


# ---------- 2. target levers ---------------------------------------------------------------------------------------------------------

def run(s, label, lever, case, mass=None, pol=1.0, cls='CALCULATED', tech='', note=''):
    orig = vr.sigma_v
    if pol != 1.0:
        vr.sigma_v = lambda r, T: orig(r, T) * (pol if r == 'DHe3' else P['pol_DD'] if r.startswith('DD') else 1.0)
    try:
        L = lg.burn(s, case, mass_kg=mass, rows=4)
    finally:
        vr.sigma_v = orig
    e = L['energy']; p = L['particles']; Ef = e['fusion_J']
    extract = e['plasma_J'] + e['escaped_charged_J']
    return dict(label=label, lever=lever, cls=cls, tech=tech, note=note, case=L['case'], mass_kg=L['mass_kg'], R0_um=L['R0_m'] * 1e6,
                duration_ps=L['duration_s'] * 1e12, fusion_J=Ef, gain=Ef / e['heat_in_J'], burn_up=p['burn_fraction_mass'],
                xray_share=e['xray_J'] / Ef, neutron_share=e['neutron_J'] / Ef, plasma_share=e['plasma_J'] / Ef,
                escaped_share=e['escaped_charged_J'] / Ef, extract_share=extract / Ef, extract_J=extract,
                self_heat_share=(e['to_ions_J'] + e['to_electrons_J']) / max(e['charged_born_J'], 1e-30),
                to_ions_share=e['to_ions_J'] / max(e['to_ions_J'] + e['to_electrons_J'], 1e-30),
                residual_share=e['residual_share'], number_change_share=e.get('number_change_J', 0.0) / (Ef + e['heat_in_J']))


def engine(row, fi, pickup, extra_plasma_J=0.0, xray_J=None, extra_mass=0.0):
    """One pulse of this burn through the compact engine at the design rate (ledger.pulse arithmetic): the extractable plasma (thermal,
    expansion and escaped products) is directed with the nozzle's eta, the hit share strikes hardware, X-rays and neutrons are picked up
    at the geometric share of the drawn engine."""
    L = fi['ledger']; nz = L['nozzle']['C1|1']; Hz = L['pulse']['Hz']; budget = nz['budget_W']
    Pp = row['extract_J'] + extra_plasma_J; X = row['fusion_J'] * row['xray_share'] if xray_J is None else xray_J
    N_ = row['fusion_J'] * row['neutron_share']
    jet = nz['eta'] * Pp; hit = nz['hit'] * Pp; heat = pickup * (X + N_) + hit
    m = row['mass_kg'] - row['fusion_J'] / lg.C_LIGHT ** 2 + extra_mass
    I = math.sqrt(2 * m * jet); v = math.sqrt(2 * jet / m)
    return dict(jet_share=jet / row['fusion_J'], exhaust_m_s=v, thrust_N=I * Hz, heat_W=heat * Hz, heat_over=heat * Hz / budget,
                xray_heat_share=pickup * X / heat, hit_heat_share=hit / heat)


def levers(s):
    b = lg.base_case(s); r0 = lg.design_rhoR(s); M0 = None
    base = dict(b, rhoR_g_cm2=r0)
    R = [run(s, 'Design target (R2-B, 70 keV, D:3He 1:1)', 'base', base)]
    for f in (0.3, 3.0):
        R.append(run(s, f'Areal density x{f:g}', 'density', dict(base, rhoR_g_cm2=r0 * f),
                     tech='x3: precision shells and pulse shaping (advanced manufacturing, AI-controlled drivers)' if f > 1 else ''))
    for m in (0.25, 4.0):
        R.append(run(s, f'Target mass x{m:g} at the design areal density', 'geometry', base, mass=lg.vm.plasma(s)['mass_kg'] * m))
    for x in (0.5, 0.25, 2.0):
        R.append(run(s, f'Disassembly {1 / x:g}x {"slower (tamped)" if x < 1 else "faster"}', 'duration', dict(base, expansion=x),
                     tech='a heavy tamper or a magnetised liner holds the fuel longer' if x < 1 else ''))
    for mix in (0.33, 3.0):
        R.append(run(s, f'Selective fuelling D:3He {mix:g}:1', 'fuelling', dict(base, D_per_He3=mix)))
    R.append(run(s, 'Spin-polarised D and 3He (sigma-v x1.5)', 'polarisation', base, pol=P['pol_gain'], cls='SPECULATIVE',
                 tech='polarised fuel made, stored and compressed without depolarising (cryogenic handling, nanoscale target shells)'))
    R.append(run(s, 'Hot ions at the start (Te = 0.5 Ti)', 'hot-ion', dict(base, Te_over_Ti=0.5)))
    for d in (0.8, 0.5, 0.2):
        R.append(run(s, f'Early extraction: {1 - d:.0%} of the product energy leaves the target', 'extraction', dict(base, deposition=d),
                     cls='MODEL-BASED', tech='a lower-density burn edge or a strong field that lets the fast protons out'))
    worst = dict(base, D_per_He3=0.33, expansion=0.5, rhoR_g_cm2=r0 * 3.0)
    R.append(run(s, 'Fuel-side levers together: polarised, 3He-rich, tamped, x3 areal density', 'fuel-combined', worst, pol=P['pol_gain'],
                 cls='SPECULATIVE', tech='every fuel-side lever at once'))
    best = dict(base, rhoR_g_cm2=r0 * 0.3, deposition=0.8)
    R.append(run(s, 'Source-side levers together: polarised, x0.3 areal density, 20% early extraction', 'combined', best, pol=P['pol_gain'],
                 cls='SPECULATIVE', tech='polarised fuel, a lower-density burn and a strong extraction field'))
    return R


# ---------- 3. trapping the X-rays in the target's own tamper ------------------------------------------------------------------------

def mu_abs(mat, E):
    """Energy-absorption coefficient (cm2/g): photoabsorption plus the energy Compton scattering leaves behind (cold matter)."""
    ph = mpn._interp(mat, 'photo_cm2_g', E); co = mpn._interp(mat, 'compton_cm2_g', E)
    return ph + co * vr.sigma_kn_transfer(E) / max(vr.sigma_kn(E), 1e-60)


def tamper(base_row, spec, pulse, need_ve):
    """A shell of areal density sigma round the fuel absorbs the burn's X-rays; a share P['refire'] is re-radiated, the rest becomes
    plasma the nozzle can direct. The shell joins the exhaust mass (ANALYTIC; cold opacities, so the absorption is an upper bound)."""
    R0 = base_row['R0_um'] * 1e-6; X = pulse['xray_J']; eta = pulse['jet_J'] / pulse['plasma_J']
    rows = []
    for mat in P['tamper_mats']:
        for sg in P['tamper_sigma']:
            f = sum(w * (1 - math.exp(-mu_abs(mat, E) * sg)) for E, w in spec)
            m = 4 * math.pi * R0 * R0 * sg * 10.0
            gain_J = f * (1 - P['refire']) * X
            jet = pulse['jet_J'] + eta * gain_J; mex = pulse['exhaust_mass_kg'] + m
            ve = math.sqrt(2 * jet / mex); I = mex * ve
            rows.append(dict(material=mat, sigma_g_cm2=sg, absorbed=f, tamper_kg=m, tamper_over_fuel=m / pulse['mass_kg'],
                             xray_left_share=(X - f * X + P['refire'] * f * X) / pulse['fusion_J'], jet_J=jet, exhaust_m_s=ve,
                             impulse_ratio=I / pulse['impulse_Ns'], ve_over_need=ve / need_ve,
                             refire_band=[sum(w * (1 - math.exp(-mu_abs(mat, E) * sg)) for E, w in spec) * (1 - q) for q in (0.1, 0.6)]))
    return rows


# ---------- 4. the audit ------------------------------------------------------------------------------------------------------------

def audit(fi, th):
    nz = fi['ledger']['nozzle']['C1|1']
    imp = json.loads(sorted((ROOT / 'lab/studies/fusion-ignition/imports').glob('compact_*.json'))[-1].read_text())
    src = imp['source']; v = imp['variants']['C1']
    piped = v['piped_four_W'] / 4; neutral = src['P_brems_W'] + src['P_sync_W'] + src['P_n_W']; hits = v['hit_share'] * src['P_charged_W']
    dp = 0.01 * src['P_charged_W'] / neutral                         # pickup moved by one point of hit share
    comp = {c['id']: c['sky'] for c in th['components']}
    coils = sum(comp[k] for k in ('C1', 'C2', 'L1', 'L2', 'L3', 'L4')); cage = comp['CAGE'] + comp['LINES'] + comp['OPTICS']
    L = fi['ledger']; e_res = L['checks']['energy_residual_share']
    return dict(
        geometry_sky=th['reconcile']['geometry_sky'], ledger_pickup=nz['pickup'],
        pickup_terms=dict(piped_W=piped, charged_hits_W=hits, neutral_W=neutral, sky_total_compact=v['sky'], per_point_hit_share=dp),
        geometry_terms=dict(shield=comp['SHIELD'], coils_and_loops=coils, cage_lines_optics=cage),
        findings=[
            f'The 54.6 % is not a geometric quantity. The ledger derives it as (piped heat - hit share x charged power) / neutral power from the '
            f'compact study: ({piped / 1e12:.1f} TW - {hits / 1e12:.1f} TW) / {neutral / 1e12:.2f} TW. It is the small difference of two large '
            f'numbers: one point of hit share moves it by {dp:.2f}.',
            f'It also comes from a different source state: the steady-plasma spectrum (STEADY, with synchrotron), not the target burn (COUPLED).',
            f'The compact study\'s own sky ledger covered {v["sky"]:.1%} of the burn (with the radiator blades and the neighbour engines), and its '
            f'piped heat leaves out what edge-on fins and the plug re-radiate themselves.',
            f'The geometric trace of every drawn part gives {th["reconcile"]["geometry_sky"]:.1%}: shield {comp["SHIELD"]:.1%}, coils and loops '
            f'{coils:.1%}, cage, lines and optics {cage:.1%}. The coils, loops and shield alone give {comp["SHIELD"] + coils:.1%}, '
            f'close to the ledger figure, which is why the two looked related.',
            'Decision: the COUPLED ledger now uses the geometric trace (63.1 %) for the X-ray and neutron pickup of the compact engine; '
            'the old figure is kept and labelled as the compact study\'s piped share.'],
        residual=dict(share=e_res,
                      finding='The 0.25 % energy residual of the burn was the thermal energy of ions created or lost at fixed temperature '
                              '(D-D-n and D-T turn two ions into one). The ledger now books it as its own term (number change); about '
                              '0.02 % remains, the time-step error of the integration.'))


# ---------- 5. advanced-technology levers --------------------------------------------------------------------------------------------

TECH = [
    dict(lever='Spin-polarised fuel', physics='x1.5 D-3He reactivity (established); survival through compression is unknown',
         enabler='cryogenic polarised fuel, nanoscale shells that keep spins aligned, AI-shaped compression', status='SPECULATIVE'),
    dict(lever='Higher areal density', physics='more burn-up, but the burning electrons radiate more: the X-ray share grows',
         enabler='precision target manufacture, pulse shaping by learned controllers', status='ESTABLISHED physics, ADVANCED manufacture'),
    dict(lever='Tamped, longer burn', physics='more burn-up at the same yield; a heavy tamper mixes and raises Zeff',
         enabler='graded nanostructured tampers, magnetised liners (superconducting drivers)', status='ESTABLISHED'),
    dict(lever='X-ray trapping tamper', physics='an opaque shell turns X-rays into plasma the nozzle can direct; adds exhaust mass',
         enabler='graded high-Z/low-Z shells made atom by atom', status='ESTABLISHED (cold opacity upper bound)'),
    dict(lever='Early extraction of protons', physics='directed 14.7 MeV protons, but the burn loses its self-heating',
         enabler='stronger fields from advanced superconductors at the target', status='MODEL-BASED'),
    dict(lever='Hot-ion burn', physics='the products heat electrons first above Ec; Te follows Ti within picoseconds at target density',
         enabler='none known: the coupling is collisional, not a technology limit', status='LIMITED BY PHYSICS'),
]


def main():
    s = S.load()[0]; fi = json.loads(FI.read_text()); th = json.loads(TH.read_text())
    pz = lg.vm.plasma(s); r0 = lg.design_rhoR(s)
    M = pz['mass_kg']; R0 = math.sqrt(3 * M / (4 * math.pi * r0 * 10)); rho = M / (4 / 3 * math.pi * R0 ** 3)
    m_pair = vr.M_ION['D'] + vr.M_ION['He3']; ni = rho / (m_pair * AMU); ne = 3 * ni
    ions = [(ni, 1, vr.M_ION['D']), (ni, 2, vr.M_ION['He3'])]
    sl = slowing(ne, ions)
    print('slowing (design density, ne %.2e m^-3):' % ne)
    for r in sl:
        print(f"  Te {r['Te_keV']:4d} keV  p: Ec {r['p']['Ec_keV']:7.0f} keV ions {r['p']['to_ions']:.2f} range {r['p']['range_m'] * 1e6:6.2f} um"
              f"  alpha: Ec {r['alpha']['Ec_keV']:7.0f} ions {r['alpha']['to_ions']:.2f} range {r['alpha']['range_m'] * 1e6:6.2f} um")
    lv = levers(s)
    for r in lv:
        print(f"  {r['label'][:58]:58s} Y {r['fusion_J'] / 1e9:6.2f} GJ burn-up {r['burn_up']:.2f} X {r['xray_share']:.2f} "
              f"n {r['neutron_share']:.3f} extract {r['extract_share']:.2f} ions {r['to_ions_share']:.2f} {r['duration_ps']:.1f} ps")
    pulse = fi['ledger']['pulse']; spec = [(x['E_keV'], x['share']) for x in th['spectrum']]
    pk = th['reconcile']['geometry_sky']
    for r in lv:
        r['engine'] = engine(r, fi, pk)
    tp = tamper(lv[0], spec, pulse, fi['need']['exhaust_m_s'])
    for r in tp:
        X = lv[0]['fusion_J'] * r['xray_left_share']
        r['engine'] = engine(lv[0], fi, pk, extra_plasma_J=r['absorbed'] * (1 - P['refire']) * lv[0]['fusion_J'] * lv[0]['xray_share'],
                             xray_J=X, extra_mass=r['tamper_kg'])
    comb = next(r for r in lv if r['lever'] == 'combined')
    tW = next(r for r in tp if r['material'] == 'W' and r['sigma_g_cm2'] == 1.0)
    f = tW['absorbed'] * (1 - P['refire'])
    best = dict(label='Source-side levers + 1 g/cm2 tungsten tamper', engine=engine(
        comb, fi, pk, extra_plasma_J=f * comb['fusion_J'] * comb['xray_share'], xray_J=comb['fusion_J'] * comb['xray_share'] * (1 - f),
        extra_mass=tW['tamper_kg']), xray_left_share=comb['xray_share'] * (1 - f), cls='SPECULATIVE')
    for r in [*lv, best]:
        e = r['engine']; print(f"  {r['label'][:58]:58s} jet {e['jet_share']:.3f} ve {e['exhaust_m_s'] / 1e3:6.0f} km/s F {e['thrust_N'] / 1e3:6.0f} kN heat x{e['heat_over']:6.0f}")
    for r in tp:
        print(f"  tamper {r['material']:9s} {r['sigma_g_cm2']:5.2f} g/cm2 absorbs {r['absorbed']:.2f} mass/fuel {r['tamper_over_fuel']:.3f} "
              f"X left {r['xray_left_share']:.2f} ve {r['exhaust_m_s'] / 1e3:6.0f} km/s impulse x{r['impulse_ratio']:.2f}")
    au = audit(fi, th)
    base = lv[0]
    # the trade summary: each lever against the design target
    trade = []
    for r in lv[1:]:
        trade.append(dict(label=r['label'], lever=r['lever'], cls=r['cls'], yield_x=r['fusion_J'] / base['fusion_J'],
                          burn_up=r['burn_up'], xray_share=r['xray_share'], extract_share=r['extract_share'],
                          extract_x=r['extract_J'] / base['extract_J'], neutron_share=r['neutron_share'], self_heat=r['self_heat_share'],
                          thrust_x=r['engine']['thrust_N'] / base['engine']['thrust_N'], heat_over=r['engine']['heat_over'],
                          exhaust_m_s=r['engine']['exhaust_m_s']))
    out = dict(cls='WORK', source='lab/studies/vertex-compact-engine/vertex-source/source.py (owner brief 2026-11-24 06:43Z)', params=P,
               design=dict(rhoR_g_cm2=r0, mass_kg=M, R0_um=R0 * 1e6, rho_g_cc=rho / 1e3, ne_m3=ne),
               slowing=sl, brems=brems_ratio(), levers=lv, best=best, pickup=pk, trade=trade, tamper=tp, audit=au, tech=TECH,
               findings=findings(sl, lv, tp, base, best))
    (HERE / 'results').mkdir(exist_ok=True)
    (HERE / 'results/source.json').write_text(json.dumps(out, indent=1))
    for f in out['findings']:
        print('-', f)


def findings(sl, lv, tp, base, best):
    L = {r['lever'] + r['label']: r for r in lv}
    at = next(r for r in sl if r['Te_keV'] == 70)
    fc = next(r for r in lv if r['lever'] == 'fuel-combined'); lo = next(r for r in lv if r['label'] == 'Areal density x0.3')
    fast = next(r for r in lv if r['label'].startswith('Disassembly 0.5'))
    pol = next(r for r in lv if r['lever'] == 'polarisation'); hot = next(r for r in lv if r['lever'] == 'hot-ion')
    ex = [r for r in lv if r['lever'] == 'extraction']; comb = next(r for r in lv if r['lever'] == 'combined')
    he3 = next(r for r in lv if r['lever'] == 'fuelling' and r['case']['D_per_He3'] < 1)
    tW = max((r for r in tp if r['material'] == 'W'), key=lambda r: r['absorbed'] if r['sigma_g_cm2'] <= 1 else 0)
    return [
        f'At 70 keV the 14.7 MeV protons give {at["p"]["to_ions"]:.0%} of their energy to ions and the 3.6 MeV alphas {at["alpha"]["to_ions"]:.0%} '
        f'(critical energies {at["p"]["Ec_keV"] / 1e3:.1f} and {at["alpha"]["Ec_keV"] / 1e3:.1f} MeV); the rest heats electrons, which radiate. '
        f'At the design density the products stop within {at["p"]["range_m"] * 1e6:.1f} um (protons) of a {base["R0_um"]:.0f} um target, so they '
        f'all deposit: the target is its own X-ray lamp.',
        f'The design burn sends {base["xray_share"]:.0%} of its fusion energy out as X-rays and leaves {base["extract_share"]:.0%} as plasma the nozzle can use.',
        f'Hot ions at the start change almost nothing (X-ray share {hot["xray_share"]:.0%}): ions and electrons equilibrate in picoseconds at '
        f'this density. This is a physics limit, not a technology one.',
        f'Spin polarisation raises the yield x{pol["fusion_J"] / base["fusion_J"]:.2f} and burn-up to {pol["burn_up"]:.0%}, but the X-ray share stays '
        f'{pol["xray_share"]:.0%}: it helps the fuel, not the radiation.',
        f'3He-rich fuel (D:3He 1:3) cuts the neutron share to {he3["neutron_share"]:.1%} (from {base["neutron_share"]:.1%}) at X-ray share '
        f'{he3["xray_share"]:.0%}.',
        'Early extraction is the only lever that lowers the X-ray share at the source: ' + '; '.join(
            f'{1 - r["case"]["deposition"]:.0%} out gives X-rays {r["xray_share"]:.0%}, extractable {r["extract_share"]:.0%}, yield x{r["fusion_J"] / base["fusion_J"]:.2f}'
            for r in ex) + '. The burn loses its self-heating, so the yield falls.',
        f'A tungsten tamper of {tW["sigma_g_cm2"]:g} g/cm2 round the fuel ({tW["tamper_over_fuel"]:.1%} of its mass) would absorb {tW["absorbed"]:.0%} '
        f'of the X-rays (cold opacity, an upper bound) and leave {tW["xray_left_share"]:.0%} of the fusion energy as X-rays. The absorbed energy '
        f'becomes plasma the nozzle can direct, so the exhaust speeds up to {tW["exhaust_m_s"] / 1e3:,.0f} km/s ({tW["ve_over_need"]:.2f} of the '
        f'mission\'s) and the impulse per pulse grows x{tW["impulse_ratio"]:.2f}. Light tampers (LiH, carbon) absorb too little.',
        f'Density and burn time decide the split: x0.3 areal density gives X-rays {lo["xray_share"]:.0%} and extractable {lo["extract_share"]:.0%} '
        f'(yield x{lo["fusion_J"] / base["fusion_J"]:.2f}); a faster disassembly gives {fast["xray_share"]:.0%} and {fast["extract_share"]:.0%}. A denser '
        f'or longer burn raises burn-up a little and sends almost everything out as X-rays.',
        f'The fuel-side levers together (polarised, 3He-rich, tamped, x3 areal density) are the worst case: yield x{fc["fusion_J"] / base["fusion_J"]:.2f}, '
        f'X-rays {fc["xray_share"]:.0%} of the fusion energy (the driver heat radiates too).',
        f'The source-side levers together (polarised, x0.3 areal density, 20 % early extraction): yield x{comb["fusion_J"] / base["fusion_J"]:.2f}, '
        f'burn-up {comb["burn_up"]:.0%}, X-rays {comb["xray_share"]:.0%}, extractable {comb["extract_share"]:.0%}. With a tungsten tamper on top, '
        f'the X-rays leaving the target fall to {best["xray_left_share"]:.0%} of the fusion energy and the thrust grows x'
        f'{best["engine"]["thrust_N"] / base["engine"]["thrust_N"]:.1f}, but the engine heat stays x{best["engine"]["heat_over"]:,.0f} its radiator share '
        f'(design x{base["engine"]["heat_over"]:,.0f}): the plasma that no longer radiates strikes the hardware instead '
        f'({best["engine"]["hit_heat_share"]:.0%} of the heat). The next lever is the nozzle\'s hit share, not the fuel.',
        'Adding cold propellant lowers the exhaust speed: the design is short of energy per kilogram (coupled exhaust '
        f'{base["engine"]["exhaust_m_s"] / 1e3:,.0f} km/s against the mission\'s 19,201 km/s), not short of mass.',
    ]


if __name__ == '__main__':
    main()
