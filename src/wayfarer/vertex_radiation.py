"""Vertex Engine 1.5: radiation physics, 3D exposure geometry and thermal feasibility (owner brief 2026-11-15, `[vertex_radiation]`).

Order of work, as the brief asks: audit the 1.4 energy budget (R-01), bound the photon and neutron sources (R-02, R-03), trace the real
engine meshes from the burn point in 3D (G-01, G-02), bracket the energy each part absorbs (R-04, R-05), close or fail the heat balance
against Wayfarer's radiators (T-01, T-02), then screen radiation-aware candidates (A-01..A-03) and decide (R15-0..6).

Standard library only. The engine, cluster, plasma and radiator inputs are read, never changed. Evidence per result:
ANALYTIC (closed form), REDUCED_MODEL (R2-B burn), RAY_TRACED (real part meshes), BRACKETED (transport bounds), NOT_EXECUTED.

python3 src/wayfarer/vertex_radiation.py [--quick] [--evidence]"""
import hashlib
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vertex_cluster as vc  # noqa: E402
import vertex_engine as ve  # noqa: E402
import vertex_magnet as vm  # noqa: E402
import vertex_plasma as vp  # noqa: E402

EVIDENCE_PATH = Path(__file__).resolve().parents[2]/'references'/'evidence'/'vertex_radiation.json'
MEV = 1.602176634e-13            # J
KEV = 1.602176634e-16            # J
AMU = 1.66053906660e-27
ME_C2_KEV = 510.99895
SIGMA_SB = 5.670374419e-8
R_E = 2.8179403262e-15           # classical electron radius (m)
N_A = 6.02214076e23

# Reaction energies (MeV) and products.
Q = dict(DHe3=18.353, DDn=3.269, DDp=4.033, DT=17.589)
PRODUCTS = dict(DHe3=dict(p=14.68, alpha=3.67), DDn=dict(n=2.45, He3=0.82), DDp=dict(p=3.02, T=1.01), DT=dict(n=14.07, alpha=3.52))
M_ION = dict(D=2.01410, He3=3.01603, T=3.01605, alpha=4.00260, p=1.00728)
Z_ION = dict(D=1, He3=2, T=1, alpha=2, p=1)

# Bosch & Hale, Nucl. Fusion 32 (1992) 611, Table VII: B_G (keV^1/2), m_r c^2 (keV), C1..C7; <sigma v> in cm^3/s, T in keV (0.2-100+).
BOSCH_HALE = {
    'DT': (34.3827, 1124656.0, (1.17302e-9, 1.51361e-2, 7.51886e-2, 4.60643e-3, 1.35000e-2, -1.06750e-4, 1.36600e-5)),
    'DHe3': (68.7508, 1124572.0, (5.51036e-10, 6.41918e-3, -2.02896e-3, -1.91080e-5, 1.35776e-4, 0.0, 0.0)),
    'DDp': (31.3970, 937814.0, (5.65718e-12, 3.41267e-3, 1.99167e-3, 0.0, 1.05060e-5, 0.0, 0.0)),
    'DDn': (31.3970, 937814.0, (5.43360e-12, 5.85778e-3, 7.68222e-3, 0.0, -2.96400e-6, 0.0, 0.0)),
}

BH_VALID_KEV = dict(DT=100.0, DHe3=190.0, DDp=100.0, DDn=100.0)


def config(s):
    return s['vertex_radiation']


# ---------- R-01: the 1.4 energy budget ------------------------------------------------------------------------------------------------

def audit_1_4(s):
    """What Engine 1.4 assumed (vertex_plasma.thermal): everything that is not the research jet (1 - jet_TW / fusion_TW of the yield) is
    neutral radiation, of it 1 % of the yield neutrons and the rest X-rays; X-ray and neutron power hitting hardware = emitted power x the
    axisymmetric sky fraction (87 %); every intercepted photon deposits all its energy."""
    pz = vm.plasma(s); c = vp.config(s); Y = pz['yield_J']; f = pz['pulse_Hz']
    Ech = pz['energy_J']['design']; Enc = Y-Ech; neu = c['neutron_share_of_fusion'][1]*Y; xr = Enc-neu
    sky = vp.sky_fractions(s, 'NOMINAL'); hw = sum(v for k, v in sky.items() if k != 'SPACE')
    return dict(yield_J=Y, pulse_Hz=f, fusion_W=Y*f, jet_share=pz['charged_share'], jet_J=Ech, nonjet_J=Enc, neutron_J=neu, xray_J=xr,
                xray_share=xr/Y, hardware_sky=hw, sky=sky, xray_absorbed_W=xr*f*hw, neutron_absorbed_W=neu*f*hw,
                findings=['The photon energy is the remainder of the jet share, not a radiation calculation: any charged energy the nozzle does '
                          'not direct (plasma heat, undirected debris, the driver energy) is booked as X-rays.',
                          'Neutron heating is the neutron energy times the photon sky fraction: neutrons were given the photon geometry and '
                          'full absorption.',
                          'The sky fraction is an axisymmetric (x, rho) screen: the eight cage longerons count as a solid surface of revolution, '
                          'and parts that are not coils, shield or cage are missing.',
                          'Every intercepted photon deposits all its energy where it lands (no transmission, scattering or depth).'])


# ---------- R-02 / R-03: source physics ------------------------------------------------------------------------------------------------

def sigma_v(reaction, T_keV):
    """Bosch-Hale Maxwellian reactivity (m^3/s)."""
    if T_keV <= 0.0:
        return 0.0
    BG, mrc2, C = BOSCH_HALE[reaction]; T = min(T_keV, BH_VALID_KEV[reaction])     # held at the fit's upper limit beyond it
    theta = T/(1.0-T*(C[1]+T*(C[3]+T*C[5]))/(1.0+T*(C[2]+T*(C[4]+T*C[6]))))
    xi = (BG*BG/(4.0*theta))**(1.0/3.0)
    return C[0]*theta*math.sqrt(xi/(mrc2*T**3))*math.exp(-3.0*xi)*1e-6


def brems_W_m3(ne, Te_keV, zeff):
    """Bremsstrahlung power density (W/m^3) with the relativistic electron-ion and electron-electron terms (theta = Te / m_e c^2):
    P = 5.34e-37 ne^2 sqrt(Te) [Zeff (1 + 0.7936 theta + 1.874 theta^2) + 3/sqrt(2) theta] (Rider 1995 form; Stott 2005)."""
    th = Te_keV/ME_C2_KEV
    return 5.34e-37*ne*ne*math.sqrt(max(Te_keV, 0.0))*(zeff*(1.0+0.7936*th+1.874*th*th)+(3.0/math.sqrt(2.0))*th)


def ion_share(E0_keV, Te_keV, A_fast, ions):
    """Share of a fast ion's energy given to the bulk ions while it slows down (Sivukhin): critical energy
    E_c = 14.8 A_f Te [sum n_j Z_j^2 / A_j / n_e]^(2/3); ions = [(n, Z, A)], n_e from them."""
    ne = sum(n*Z for n, Z, A in ions)
    Ec = 14.8*A_fast*Te_keV*(sum(n*Z*Z/A for n, Z, A in ions)/ne)**(2.0/3.0)
    x = E0_keV/max(Ec, 1e-9)
    if x < 1e-6:
        return 1.0
    r = math.sqrt(x)
    return (1.0/x)*((1.0/3.0)*math.log((1.0-r+x)/(1.0+r)**2)+(2.0/math.sqrt(3.0))*(math.atan((2.0*r-1.0)/math.sqrt(3.0))+math.pi/6.0))


def lnlambda(ne, Te_keV):
    return max(5.0, 24.0-math.log(math.sqrt(ne*1e-6)/(Te_keV*1e3)))


def burn(s, case, mass_kg=None, steps_max=200000, spectrum=True):
    """R2-B: one target's burn as a uniform sphere. Returns the time-integrated fusion energy by reaction, bremsstrahlung (all escaping:
    the hard spectrum's Compton depth at these areal densities is about 0.1-1 and Compton scattering only downshifts), neutron energy,
    burn fraction, the photon spectrum and histories. The photon-to-fusion ratio is the decision quantity: both scale with density
    squared, so it depends on the temperatures and the mix, not on the target size."""
    c = config(s); pz = vm.plasma(s)
    M = mass_kg or pz['mass_kg']; r_DHe = case['D_per_He3']
    m_pair = r_DHe*M_ION['D']+M_ION['He3']
    N_He = M/(m_pair*AMU); N = dict(D=r_DHe*N_He, He3=N_He, T=0.0, alpha=0.0, p=0.0)
    rhoR = case['rhoR_g_cm2']*10.0                                    # kg/m^2
    R = 3.0*M/(4.0*math.pi*rhoR)
    R = math.sqrt(R)
    Ti = case['Ti_keV']; Te = Ti*case['Te_over_Ti']; dep = case['deposition']
    E = dict(DHe3=0.0, DDn=0.0, DDp=0.0, DT=0.0); Ebr = 0.0; Eadiab = 0.0; t = 0.0; nsteps = 0
    edges = c['spectrum_edges_keV']; spec_J = [0.0]*(len(edges)-1)
    hist = []; N0_D = N['D']
    E0 = 1.5*(sum(N[k]*Z_ION[k] for k in N)*Te+sum(N.values())*Ti)*KEV        # initial plasma heat (from the driver, not fusion)
    tau0 = None; Tpk = Ti; Tmade = Tburnt = 0.0
    while nsteps < steps_max:
        V = 4.0/3.0*math.pi*R**3
        n = {k: v/V for k, v in N.items()}
        ions = [(n[k], Z_ION[k], M_ION[k]) for k in n if n[k] > 0]
        ne = sum(a*b for a, b, _ in ions); ni = sum(a for a, _, _ in ions)
        zeff = sum(a*b*b for a, b, _ in ions)/ne
        rate = dict(DHe3=n['D']*n['He3']*sigma_v('DHe3', Ti), DDn=0.5*n['D']**2*sigma_v('DDn', Ti), DDp=0.5*n['D']**2*sigma_v('DDp', Ti),
                    DT=n['D']*n['T']*sigma_v('DT', Ti))
        Pf = {k: rate[k]*Q[k]*MEV*V for k in rate}
        Pem = brems_W_m3(ne, Te, zeff)*V
        # Compton depth at the mean photon energy (about Te): scattering delays the photons (diffusion time about tau^2 R / c, shorter
        # than the burn) and, with electrons this hot, gives them energy rather than taking it; free-free absorption is negligible
        tau = ne*sigma_kn(max(Te, 1.0))*R
        Pbr = Pem
        # charged products slowing in the fuel: the deposited share heats ions and electrons by the critical-energy split
        Pi = Pe = 0.0
        for k, prods in PRODUCTS.items():
            for sp, e_mev in prods.items():
                if sp == 'n':
                    continue
                Pdep = rate[k]*e_mev*MEV*V*dep
                fi = ion_share(e_mev*1e3, Te, M_ION[sp], ions)
                Pi += fi*Pdep; Pe += (1.0-fi)*Pdep
        # Spitzer electron-ion exchange (NRL: nu = 3.2e-9 Z^2 n_i lnL / (mu Te^1.5), cgs, Te in eV)
        nu = sum(3.2e-9*Z*Z*(nn*1e-6)*lnlambda(ne, Te)/(A*(Te*1e3)**1.5) for nn, Z, A in ions)
        Pei = 1.5*ne*V*(Ti-Te)*KEV*nu
        mi = sum(a*A for a, _, A in ions)/ni*AMU
        cs = math.sqrt((ne*Te+ni*Ti)*KEV/(ni*mi))
        dR = case['expansion']*cs
        # time step: 1 % change of the fastest quantity
        Ui = 1.5*ni*V*Ti*KEV; Ue = 1.5*ne*V*Te*KEV
        rates = [abs(Pi+Pei)/Ui if Ui else 0, abs(Pe-Pei-Pbr)/Ue if Ue else 0, dR/R, rate['DHe3']*V/max(N['He3'], 1.0)]
        dt = 0.01/max(max(rates), 1e-30)
        Ui += (Pi-Pei)*dt; Ue += (Pe+Pei-Pbr)*dt
        Ti = max(Ui/(1.5*ni*V*KEV), 0.01); Te = max(Ue/(1.5*ne*V*KEV), 0.01)
        Rn = R+dR*dt; cool = (R/Rn)**2                          # adiabatic gamma 5/3: T ~ R^-2; the lost heat becomes expansion energy
        Eadiab += 1.5*(ni*Ti+ne*Te)*V*KEV*(1.0-cool); Ti *= cool; Te *= cool; R = Rn
        for k in rate:
            E[k] += Pf[k]*dt
        Ebr += Pbr*dt
        if spectrum and Pbr > 0:
            # thermal bremsstrahlung energy spectrum ~ exp(-E/Te) (Gaunt factor 1): bin share exp(-a/Te) - exp(-b/Te)
            for b in range(len(spec_J)):
                spec_J[b] += Pbr*dt*(math.exp(-edges[b]/Te)-math.exp(-edges[b+1]/Te))
        d = rate['DHe3']*V*dt; dn = rate['DDn']*V*dt; dp = rate['DDp']*V*dt; dtt = rate['DT']*V*dt; Tmade += dp; Tburnt += dtt
        N['D'] -= d+2*dn+2*dp+dtt; N['He3'] += dn-d; N['T'] += dp-dtt; N['alpha'] += d+dtt; N['p'] += d+dp
        for k in N:
            N[k] = max(N[k], 0.0)
        t += dt; nsteps += 1; Tpk = max(Tpk, Ti)
        if tau0 is None:
            tau0 = tau
        if nsteps % 50 == 0:
            hist.append((t, Ti, Te, R, sum(E.values())))
        if Ti < 2.0 or (sum(Pf.values()) < 1e-6*max(sum(E.values())/max(t, 1e-30), 1e-30) and t > 0):
            break
    Ef = sum(E.values())
    En = E['DDn']/Q['DDn']*PRODUCTS['DDn']['n']+E['DT']/Q['DT']*PRODUCTS['DT']['n']
    sp_tot = sum(spec_J) or 1.0
    return dict(case=case['id'], mass_kg=M, R0_m=math.sqrt(3.0*M/(4.0*math.pi*rhoR)), fusion_J=Ef, by_reaction_J=E, brems_J=Ebr, neutron_J=En,
                photon_share=Ebr/Ef if Ef else 0.0, neutron_share=En/Ef if Ef else 0.0, burn_fraction=1.0-N['D']/N0_D if N0_D else 0.0,
                adiabatic_J=Eadiab, initial_heat_J=E0, compton_depth0=tau0, Ti_peak_keV=Tpk, tritium_burnup=Tburnt/Tmade if Tmade else 0.0, rhoR_g_cm2=case['rhoR_g_cm2'],
                photon_share_of_input=Ebr/(Ef+E0) if Ef+E0 else 0.0, duration_s=t, steps=nsteps, spectrum_share=[x/sp_tot for x in spec_J], history=hist[::max(1, len(hist)//60)])


def sigma_kn(E_keV):
    """Klein-Nishina total cross section per electron (m^2)."""
    k = E_keV/ME_C2_KEV
    if k < 1e-4:
        return 8.0*math.pi/3.0*R_E**2*(1.0-2.0*k)
    a = (1+k)/k**2*(2*(1+k)/(1+2*k)-math.log(1+2*k)/k)
    b = math.log(1+2*k)/(2*k)-(1+3*k)/(1+2*k)**2
    return 2.0*math.pi*R_E**2*(a+b)


def sigma_kn_transfer(E_keV):
    """Klein-Nishina energy-transfer cross section per electron (m^2): the part of sigma whose energy stays with the recoil electron."""
    k = E_keV/ME_C2_KEV
    if k < 1e-3:
        return sigma_kn(E_keV)*k                    # transfer fraction ~ k at low energy
    # numerical: integrate d sigma/d Omega x (1 - E'/E) over angle
    n = 200; tot = 0.0
    for i in range(n):
        mu = -1.0+(i+0.5)*2.0/n
        P = 1.0/(1.0+k*(1.0-mu))
        ds = 0.5*R_E**2*P*P*(P+1.0/P-(1.0-mu*mu))
        tot += ds*(1.0-P)*2.0*math.pi*2.0/n
    return tot


def rhoR_for_yield(s, case, lo=0.5, hi=3000.0):
    """Areal density (g/cm2) at which the R2-B burn of the implied target mass gives the demonstrator yield (bisection in log)."""
    Y = vm.plasma(s)['yield_J']
    f = lambda r: burn(s, dict(case, rhoR_g_cm2=r), spectrum=False)['fusion_J']-Y
    if f(hi) < 0:
        return None
    for _ in range(40):
        mid = math.sqrt(lo*hi)
        if f(mid) > 0:
            hi = mid
        else:
            lo = mid
    return math.sqrt(lo*hi)


def ratio_at(T_i, Te_over_Ti=1.0, D_per_He3=1.0):
    """Instantaneous bremsstrahlung / fusion power of a D-3He mix (R2-A, ANALYTIC): density cancels."""
    nHe = 1.0; nD = D_per_He3; ne = nD+2*nHe; zeff = (nD+4*nHe)/ne; Te = T_i*Te_over_Ti
    pf = nD*nHe*sigma_v('DHe3', T_i)*Q['DHe3']+0.5*nD*nD*(sigma_v('DDn', T_i)*Q['DDn']+sigma_v('DDp', T_i)*Q['DDp'])
    pb = brems_W_m3(ne, Te, zeff)/MEV
    pn = 0.5*nD*nD*sigma_v('DDn', T_i)*PRODUCTS['DDn']['n']
    return dict(T_keV=T_i, photon=pb/pf if pf else math.inf, neutron_DD=pn/pf if pf else 0.0, zeff=zeff)


def analytic_case(s, case, Tburn):
    """R2-A case: photon and neutron shares of a burn held at Ti (electrons at Te_over_Ti); bred tritium burns at the R2-B burnup."""
    c = config(s); Ti = case['Ti_keV']; Te = Ti*case['Te_over_Ti']; nD = case['D_per_He3']; nHe = 1.0
    ne = nD+2*nHe; zeff = (nD+4*nHe)/ne
    rD = nD*nHe*sigma_v('DHe3', Ti); rn = 0.5*nD*nD*sigma_v('DDn', Ti); rp = 0.5*nD*nD*sigma_v('DDp', Ti); rT = rp*Tburn
    pf = (rD*Q['DHe3']+rn*Q['DDn']+rp*Q['DDp']+rT*Q['DT'])*MEV
    pb = brems_W_m3(ne, Te, zeff)
    pn = (rn*PRODUCTS['DDn']['n']+rT*PRODUCTS['DT']['n'])*MEV
    edges = c['spectrum_edges_keV']; sp = [math.exp(-edges[i]/Te)-math.exp(-edges[i+1]/Te) for i in range(len(edges)-1)]; tot = sum(sp)
    return dict(photon_share=pb/pf, neutron_share=pn/pf, DHe3_share=rD*Q['DHe3']*MEV/pf, zeff=zeff, Te_keV=Te, spectrum_share=[x/tot for x in sp],
                neutron_lines=dict(DD_2_45MeV=rn*PRODUCTS['DDn']['n']*MEV/pf, DT_14_1MeV=rT*PRODUCTS['DT']['n']*MEV/pf))


def sources(s):
    """R-02/R-03 per case: photon and neutron shares, the per-pulse ledger E = charged + photons + gamma + neutrons (charged split into
    the directed jet and the rest), power, spectrum, and the verdict on the 1.4 assumption."""
    c = config(s); pz = vm.plasma(s); Y = pz['yield_J']; f = pz['pulse_Hz']; jet = pz['energy_J']['design']
    old = audit_1_4(s); ref = None; out = {}
    for case in c['cases']:
        if case['model'] == 'R2-B':
            rr = rhoR_for_yield(s, case); b = burn(s, dict(case, rhoR_g_cm2=rr if rr else 30.0)); ref = b
    for i, case in enumerate(c['cases']):
        if case['model'] == 'R2-B':
            b = ref; E_ = b['by_reaction_J']
            r = dict(photon_share=b['photon_share'], neutron_share=b['neutron_share'], DHe3_share=E_['DHe3']/b['fusion_J'],
                     neutron_lines=dict(DD_2_45MeV=E_['DDn']*PRODUCTS['DDn']['n']/Q['DDn']/b['fusion_J'],
                                        DT_14_1MeV=E_['DT']*PRODUCTS['DT']['n']/Q['DT']/b['fusion_J']),
                              spectrum_share=b['spectrum_share'], burn={k: v for k, v in b.items() if k not in ('history', 'spectrum_share')}, history=b['history'])
        else:
            r = analytic_case(s, case, ref['tritium_burnup'] if ref else 0.0)
        g = c['gamma_branch'][min(i, 2)]
        gshare = g*c['gamma_MeV']/Q['DHe3']*r['DHe3_share']
        Eph = min(r['photon_share'], 1.0)*Y; En = r['neutron_share']*Y; Eg = gshare*Y
        Ech = Y-En-Eg-Eph
        r.update(ledger=dict(total_J=Y, charged_J=Ech, photon_J=Eph, gamma_J=Eg, neutron_J=En, jet_J=jet, charged_not_jet_J=Ech-jet,
                             closes=abs(Ech+Eph+Eg+En-Y) < 1e-6*Y, jet_fits=Ech >= jet),
                 power_W=dict(fusion=Y*f, photon=Eph*f, neutron=En*f, gamma=Eg*f),
                 spectrum=[dict(lo_keV=c['spectrum_edges_keV'][k], hi_keV=c['spectrum_edges_keV'][k+1], share=x) for k, x in enumerate(r['spectrum_share'])],
                 model=case['model'], note=case['note'])
        out[case['id']] = r
    lo = min(x['photon_share'] for x in out.values()); hi = max(x['photon_share'] for x in out.values())
    verdict = 'UNDERESTIMATED' if lo > old['xray_share'] else ('OVERESTIMATED' if hi < old['xray_share'] else 'UNDETERMINED')
    room = 1.0-old['jet_share']-min(x['neutron_share'] for x in out.values())
    return dict(cases=out, photon_share_range=[lo, hi], old_xray_share=old['xray_share'], verdict_1_4=verdict, photon_room_for_jet=room,
                implied=implied_target(s), rhoR_solved=(ref or {}).get('rhoR_g_cm2'))


def sensitivity(s):
    """R2-B rows: the reduced burn (CONSERVATIVE case, rhoR solved for the yield) with one input changed at a time (initial Ti and Te/Ti,
    rhoR, fuel mix, expansion speed). R2-A rows: the analytic photon/fusion ratio over Ti and Te/Ti."""
    c = config(s); base = next(x for x in c['cases'] if x['model'] == 'R2-B'); rows = []
    base = dict(base, rhoR_g_cm2=rhoR_for_yield(s, base) or 30.0)
    for key, vals in (('Ti_keV', c['sens_Ti_keV']), ('Te_over_Ti', c['sens_Te_over_Ti']), ('rhoR_g_cm2', c['sens_rhoR_g_cm2']),
                      ('D_per_He3', c['sens_D_per_He3']), ('expansion', c['sens_expansion'])):
        for v in vals:
            b = burn(s, dict(base, id=f'{key}={v}', **{key: v}), spectrum=False)
            rows.append(dict(model='R2-B', param=key, value=v, photon_share=b['photon_share'], neutron_share=b['neutron_share'],
                             burn_fraction=b['burn_fraction'], fusion_J=b['fusion_J'], Ti_peak_keV=b['Ti_peak_keV'], duration_ns=b['duration_s']*1e9))
    for Ti in c['sens_Ti_keV']:
        for r in c['sens_Te_over_Ti']:
            rows.append(dict(model='R2-A', param='Ti_keV,Te_over_Ti', value=[Ti, r], photon_share=ratio_at(Ti, r, 1.0)['photon']))
    return rows


def implied_target(s):
    """What the demonstrator's yield and jet imply: burned mass from the yield, target mass from the jet (6.6 mg at 19,200 km/s)."""
    pz = vm.plasma(s); e_per_kg = Q['DHe3']*MEV/((M_ION['D']+M_ION['He3'])*AMU)
    burned = pz['yield_J']/e_per_kg
    return dict(burned_kg=burned, jet_mass_kg=pz['mass_kg'], implied_burn_fraction=burned/pz['mass_kg'], exhaust_m_s=pz['exhaust_m_s'],
                fusion_product_speed_m_s=math.sqrt(2*Q['DHe3']*MEV/((M_ION['p']+M_ION['alpha'])*AMU)))


# ---------- G-01 / G-02: 3D ray tracing of the real part meshes ----------------------------------------------------------------------

def fibonacci(n):
    """n deterministic, near-uniform unit directions (Fibonacci sphere); each stands for 4 pi / n steradians."""
    ga = math.pi*(3.0-math.sqrt(5.0)); out = []
    for i in range(n):
        x = 1.0-(2.0*i+1.0)/n; r = math.sqrt(max(0.0, 1.0-x*x)); a = i*ga
        out.append((x, r*math.cos(a), r*math.sin(a)))
    return out


def triangles(parts, transform=None, exclude=()):
    """Triangles (a, b, c, part index) of the parts' own meshes (vertex_engine.mesh_of, as Blender builds them)."""
    tris = []; meta = []
    for p in parts:
        if p['name'] in exclude:
            continue
        vs, fs = ve.mesh_of(p)
        if transform:
            vs = [transform(v) for v in vs]
        k = len(meta); meta.append(dict(name=p['name'], category=p['category'], material=p['material'], shape=p['shape'],
                                        closed=not (p['shape'] == 'revolve' and not p.get('closed', False))))
        for f in fs:
            for j in range(1, len(f)-1):
                tris.append((vs[f[0]], vs[f[j]], vs[f[j+1]], k))
    return tris, meta


class BVH:
    """Bounding-volume hierarchy over triangles (median split on the longest axis, leaves of up to 6). all_hits returns every crossing
    of a ray from its origin: (t, part, |cos incidence|)."""

    def __init__(self, tris):
        self.tris = tris
        self.nodes = []                                   # (lo, hi, left, right, start, end)
        idx = list(range(len(tris)))
        cen = [tuple((a[i]+b[i]+c[i])/3.0 for i in range(3)) for a, b, c, _ in tris]
        self.order = []
        self._build(idx, cen)

    def _build(self, idx, cen):
        lo = [min(min(self.tris[i][0][k], self.tris[i][1][k], self.tris[i][2][k]) for i in idx) for k in range(3)]
        hi = [max(max(self.tris[i][0][k], self.tris[i][1][k], self.tris[i][2][k]) for i in idx) for k in range(3)]
        me = len(self.nodes); self.nodes.append(None)
        if len(idx) <= 6:
            s0 = len(self.order); self.order.extend(idx); self.nodes[me] = (lo, hi, -1, -1, s0, len(self.order)); return me
        ax = max(range(3), key=lambda k: hi[k]-lo[k])
        idx.sort(key=lambda i: cen[i][ax]); m = len(idx)//2
        left = self._build(idx[:m], cen); right = self._build(idx[m:], cen)
        self.nodes[me] = (lo, hi, left, right, 0, 0); return me

    def all_hits(self, o, d, tmin=1e-7):
        inv = tuple(1.0/x if abs(x) > 1e-15 else 1e15 for x in d)
        out = []; stack = [0]; tris = self.tris; nodes = self.nodes; order = self.order
        while stack:
            lo, hi, l, r, s0, s1 = nodes[stack.pop()]
            t0 = -1e30; t1 = 1e30
            for k in range(3):
                a = (lo[k]-o[k])*inv[k]; b = (hi[k]-o[k])*inv[k]
                if a > b:
                    a, b = b, a
                if a > t0:
                    t0 = a
                if b < t1:
                    t1 = b
                if t0 > t1:
                    break
            if t0 > t1 or t1 < tmin:
                continue
            if l >= 0:
                stack.append(l); stack.append(r); continue
            for i in order[s0:s1]:
                a, b, c, part = tris[i]
                e1 = (b[0]-a[0], b[1]-a[1], b[2]-a[2]); e2 = (c[0]-a[0], c[1]-a[1], c[2]-a[2])
                pv = (d[1]*e2[2]-d[2]*e2[1], d[2]*e2[0]-d[0]*e2[2], d[0]*e2[1]-d[1]*e2[0])
                det = e1[0]*pv[0]+e1[1]*pv[1]+e1[2]*pv[2]
                if abs(det) < 1e-14:
                    continue
                f = 1.0/det; tv = (o[0]-a[0], o[1]-a[1], o[2]-a[2])
                u = (tv[0]*pv[0]+tv[1]*pv[1]+tv[2]*pv[2])*f
                if u < 0.0 or u > 1.0:
                    continue
                qv = (tv[1]*e1[2]-tv[2]*e1[1], tv[2]*e1[0]-tv[0]*e1[2], tv[0]*e1[1]-tv[1]*e1[0])
                v = (d[0]*qv[0]+d[1]*qv[1]+d[2]*qv[2])*f
                if v < 0.0 or u+v > 1.0:
                    continue
                tt = (e2[0]*qv[0]+e2[1]*qv[1]+e2[2]*qv[2])*f
                if tt > tmin:
                    nx = e1[1]*e2[2]-e1[2]*e2[1]; ny = e1[2]*e2[0]-e1[0]*e2[2]; nz = e1[0]*e2[1]-e1[1]*e2[0]
                    nn = math.sqrt(nx*nx+ny*ny+nz*nz) or 1.0
                    out.append((tt, part, abs(nx*d[0]+ny*d[1]+nz*d[2])/nn))
        out.sort()
        return out


def segments(hits, meta, shell):
    """Ordered material segments along a ray from its crossings: a closed part's crossings pair into entry/exit (dedupe crossings closer
    than 1 micron: shared edges); an open shell is one crossing of thickness shell / |cos|. Returns [(t_in, part, length, cos)] and
    whether every closed part paired."""
    seg = []; open_ = {}; ok = True; last = {}
    for t, k, cs in hits:
        if k in last and t-last[k] < 1e-6:
            continue
        last[k] = t
        if not meta[k]['closed']:
            seg.append((t, k, shell/max(cs, 0.05), cs)); continue
        if k in open_:
            t0, c0 = open_.pop(k); seg.append((t0, k, t-t0, c0))
        else:
            open_[k] = (t, cs)
    if open_:
        ok = False
        for k, (t0, c0) in open_.items():
            seg.append((t0, k, 0.0, c0))
    seg.sort()
    return seg, ok


_G = {}


def _trace_chunk(args):
    lo, hi = args; bvh = _G['bvh']; meta = _G['meta']; src = _G['src']; dirs = _G['dirs']; shell = _G['shell']
    out = []
    for i in range(lo, hi):
        hits = bvh.all_hits(src, dirs[i])
        seg, ok = segments(hits, meta, shell)
        out.append((i, seg, ok))
    return out


def trace(tris, meta, src, n, shell, workers=4):
    """Trace n Fibonacci directions from src through the triangles; returns per ray its ordered segments."""
    _G.update(bvh=BVH(tris), meta=meta, src=src, dirs=fibonacci(n), shell=shell)
    chunks = [(k*n//64, (k+1)*n//64) for k in range(64)]
    if workers > 1:
        import multiprocessing as mp_
        with mp_.get_context('fork').Pool(workers) as pool:
            res = pool.map(_trace_chunk, chunks)
    else:
        res = [_trace_chunk(c) for c in chunks]
    rays = [None]*n
    for part in res:
        for i, seg, ok in part:
            rays[i] = (seg, ok)
    return _G['dirs'], rays


GROUPS = (('SHADOW_SHIELD', ('Shadow_Shield', 'Shield_Burn_Face', 'Bore_Shutter', 'Shield_Tie_Rod')),
          ('BURN_ARMOUR', ('_Armour', 'LiH_Nose')),
          ('CLOSURE_COILS', ('C1_Winding', 'C1_Cryostat', 'C2_Winding', 'C2_Cryostat')),
          ('NOZZLE_LOOPS', ('L1_Winding', 'L2_Winding', 'L3_Winding', 'L4_Winding', '_Segment', '_Joint')),
          ('COIL_SUPPORTS', ('_Strut', 'Loop_Seat', 'Reaction_Ring')),
          ('CAGE', ('Cage_',)),
          ('TARGET_INJECTOR', ('Target_', 'Launcher', 'Sabot', 'Bore')),
          ('DRIVER_OPTICS', ('Driver_',)),
          ('THERMAL_PLUMBING', ('Lithium', 'Cryo')),
          ('ELECTRICAL', ('Pulse_Pod', 'Power_Bus', 'Lead', 'Current_Leads')))


def group_of(name):
    for g, keys in GROUPS:
        if any(k in name for k in keys):
            return g
    return 'OTHER_ENGINE'


def legacy_of(name):
    """The 1.4 axisymmetric obstacle a part belongs to (vertex_magnet.hardware: coil cryostats, shield disc, cage line)."""
    for k in ('C1', 'C2', 'L1', 'L2', 'L3', 'L4'):
        if f'_{k}_' in name and ('Winding' in name or 'Cryostat' in name or 'Segment' in name or 'Joint' in name):
            return k
    if 'Shadow_Shield' in name or 'Burn_Face' in name:
        return 'SHIELD'
    if 'Cage_Longeron' in name:
        return 'CAGE'
    return 'NOT_IN_1_4'


def refined(parts, k):
    """The parts with k times the facets of every curved mesh (G-02 mesh convergence)."""
    out = []
    for p in parts:
        q = dict(p)
        for key, d in (('n', {'revolve': 32, 'tube': 8, 'sphere': 12, 'disc': 24}.get(p['shape'])), ('nu', 48 if p['shape'] == 'torus' else None),
                       ('nv', 8 if p['shape'] in ('torus', 'torus_section') else None)):
            if d is not None:
                q[key] = int(p.get(key, d)*k)
        out.append(q)
    return out


def engine_scene(s, burn_shift=0.0, loop_scale=1.0, refine=1):
    """The engine's parts as triangles (engine frame) and the burn point; research variants scale the loop radii (A2) or move the source;
    refine multiplies the facet counts (G-02)."""
    c = config(s); st = ve.stations(s)
    if loop_scale != 1.0:
        s = json.loads(json.dumps(s, default=str))
        for l in s['vertex_engine']['geometry']['loops']:
            l['r_m'] *= loop_scale
        st = ve.stations(s)
    parts = ve.parts(s) if refine == 1 else refined(ve.parts(s), refine)
    tris, meta = triangles(parts, exclude=tuple(c['exclude_parts']))
    return tris, meta, (st['burn']+burn_shift, 0.0, 0.0)


def exposure(dirs, rays, meta):
    """First-hit solid-angle shares by part, group, material and 1.4 obstacle; distance and incidence of the first hit; open sky."""
    n = len(rays); w = 1.0/n
    part = {}; grp = {}; mat = {}; leg = {}; esc = 0.0; unpaired = 0; dist = {}
    for seg, ok in rays:
        unpaired += (not ok)
        if not seg:
            esc += w; continue
        t, k, L, cs = seg[0]; m = meta[k]
        part[m['name']] = part.get(m['name'], 0.0)+w
        g = group_of(m['name']); grp[g] = grp.get(g, 0.0)+w
        mat[m['material']] = mat.get(m['material'], 0.0)+w
        lg = legacy_of(m['name']); leg[lg] = leg.get(lg, 0.0)+w
        d = dist.setdefault(g, [1e9, 0.0, 0.0, 0.0])
        d[0] = min(d[0], t); d[1] += t*w; d[2] += cs*w; d[3] += w
    return dict(rays=n, intercepted=1.0-esc, open_sky=esc, by_group=dict(sorted(grp.items(), key=lambda x: -x[1])), by_material=mat,
                by_legacy=leg, by_part=dict(sorted(part.items(), key=lambda x: -x[1])[:40]), unpaired_rays=unpaired,
                first_hit=({g: dict(min_distance_m=v[0], mean_distance_m=v[1]/v[3], mean_cos=v[2]/v[3]) for g, v in dist.items()}),
                stat_error=math.sqrt(max((1.0-esc)*esc, 1e-12)/n))


def geometry(s, quick=False, workers=4):
    """G-01/G-02: the single engine traced at the convergence ladder; the axisymmetric 1.4 screen beside it."""
    c = config(s); tris, meta, src = engine_scene(s); t0 = time.process_time(); out = {}
    ladder = c['ray_convergence'][:2] if quick else c['ray_convergence']
    for n in ladder:
        tw = time.time(); dirs, rays = trace(tris, meta, src, n, c['shell_thickness_m'], workers)
        e = exposure(dirs, rays, meta); e['wall_s'] = time.time()-tw; out[n] = e
    old = vp.sky_fractions(s, 'NOMINAL'); hw_old = sum(v for k, v in old.items() if k != 'SPACE')
    best = out[max(out)]
    diff = []
    for k in sorted(set(old) | set(best['by_legacy'])):
        if k == 'SPACE':
            continue
        diff.append(dict(obstacle=k, axisymmetric_1_4=old.get(k, 0.0), traced_3d=best['by_legacy'].get(k, 0.0)))
    t2, m2, _ = engine_scene(s, refine=2); n2 = c['rays']
    d2, r2 = trace(t2, m2, src, n2, c['shell_thickness_m'], workers); e2 = exposure(d2, r2, m2)
    mesh = dict(triangles=len(t2), rays=n2, intercepted=e2['intercepted'], base=out.get(n2, best)['intercepted'],
                difference=e2['intercepted']-out.get(n2, best)['intercepted'], by_group=e2['by_group'])
    return dict(triangles=len(tris), parts=len(meta), source=src, ladder=out, legacy_sky=old, legacy_hardware=hw_old, difference=diff,
                mesh_refinement=mesh, cpu_s=time.process_time()-t0, closed_parts=sum(1 for m in meta if m['closed']))


# ---------- R-04 / R-05: transport brackets and the component map ----------------------------------------------------------------------

def smeared(s, material):
    m = ve.config(s)['materials']; key = material if material in m['density_kg_m3'] else 'sensor'
    return m['density_kg_m3'][key]*m['solid_fraction'][key]


def mu_compton(s, material, E_keV):
    """Compton attenuation and energy-transfer coefficients (m^2/kg) of a material class: Klein-Nishina per electron x electrons per kg."""
    za = config(s)['z_over_a'].get(material, 0.48); epk = za*N_A*1000.0
    return sigma_kn(E_keV)*epk, sigma_kn_transfer(E_keV)*epk


def bins(s):
    e = config(s)['spectrum_edges_keV']
    return [math.sqrt(e[i]*e[i+1]) for i in range(len(e)-1)]


def transport(s, rays, meta, spectrum):
    """R-04 Level A/B brackets per part (energy shares of the emitted photon energy, summed over rays and bins):
    low  = Compton only (Klein-Nishina): transferred energy deposits where the photon interacts, scattered energy leaves (to space);
    high = every photon that meets hardware deposits all its energy in the first part (photoelectric-dominated limit, 1.4's rule).
    Conservation per ray: incident = absorbed + scattered + transmitted. Returns per part {low, high, scattered_low, transmitted}."""
    E = bins(s); w_ray = 1.0/len(rays); mus = {}
    out = {}
    for seg, ok in rays:
        if not seg:
            continue
        first = meta[seg[0][1]]['name']
        out.setdefault(first, dict(low=0.0, high=0.0, scattered=0.0, transmitted=0.0))['high'] += w_ray
        for b, share in enumerate(spectrum):
            if share <= 0:
                continue
            I = w_ray*share
            for t, k, L, cs in seg:
                m = meta[k]; key = (m['material'], b)
                if key not in mus:
                    mu, mtr = mu_compton(s, m['material'], E[b]); mus[key] = (mu, mtr/mu)
                mu, ftr = mus[key]
                a = 1.0-math.exp(-mu*smeared(s, m['material'])*L)
                r = out.setdefault(m['name'], dict(low=0.0, high=0.0, scattered=0.0, transmitted=0.0))
                r['low'] += I*a*ftr; r['scattered'] += I*a*(1.0-ftr); I *= (1.0-a)
            out[first]['transmitted'] += I
    return out


def peak_flux(dirs, rays, meta):
    """Largest first-hit irradiance factor cos / (4 pi r^2) (1/m^2) per group: times emitted power gives W/m^2, times pulse energy J/m^2."""
    out = {}
    for seg, ok in rays:
        if not seg:
            continue
        t, k, L, cs = seg[0]; g = group_of(meta[k]['name'])
        out[g] = max(out.get(g, 0.0), cs/(4.0*math.pi*t*t))
    return out


def component_map(s, src_cases, dirs, rays, meta, charged=None):
    """R-05 per group and channel (W per engine): photons low/high for each source case, neutron upper bound (all intercepted neutron
    energy stays in the first part), charged plasma (1.4 coupled closures) and induced eddy heat (1.4) where they apply."""
    c = config(s); pz = vm.plasma(s); f = pz['pulse_Hz']
    tr = {cid: transport(s, rays, meta, x['spectrum_share']) for cid, x in src_cases.items()}
    pf = peak_flux(dirs, rays, meta)
    grp = {}
    for cid, x in src_cases.items():
        P = x['power_W']['photon']+x['power_W']['gamma']
        for name, r in tr[cid].items():
            g = grp.setdefault(group_of(name), dict(photon={}, neutron_upper={}, material=set()))
            v = g['photon'].setdefault(cid, dict(low=0.0, high=0.0, scattered=0.0))
            v['low'] += r['low']*P; v['high'] += r['high']*P; v['scattered'] += r['scattered']*P
    n_first = {}
    for seg, ok in rays:
        if seg:
            g = group_of(meta[seg[0][1]]['name']); n_first[g] = n_first.get(g, 0.0)+1.0/len(rays)
            grp.setdefault(g, dict(photon={}, neutron_upper={}, material=set()))['material'].add(meta[seg[0][1]]['material'])
    for g, v in grp.items():
        for cid, x in src_cases.items():
            v['neutron_upper'][cid] = n_first.get(g, 0.0)*x['power_W']['neutron']
        v['sky'] = n_first.get(g, 0.0); v['peak_irradiance_per_W'] = pf.get(g, 0.0); v['material'] = sorted(v['material'])
        v['cold'] = any(m in c['cold_materials'] for m in v['material'])
    if charged:
        for g, W in charged.items():
            grp.setdefault(g, dict(photon={}, neutron_upper={}, material=[], sky=0.0, peak_irradiance_per_W=0.0, cold=False))['charged_W'] = W
    return grp


def charged_loads(s):
    """CHARGED_PLASMA_LOAD and INDUCED_ELECTROMAGNETIC_HEATING per engine for the active M0-NOMINAL engine, from the 1.4 evidence (closures
    span aft .. isotropic; eddy heat is the cryostat-wall range)."""
    R = json.loads(vp.EVIDENCE_PATH.read_text()); m0 = R['thermal']['M0-NOMINAL']; out = {}
    for closure, part in m0['deposition'].items():
        for obst, v in part.items():
            g = 'SHADOW_SHIELD' if obst == 'SHIELD' else ('CLOSURE_COILS' if obst in ('C1', 'C2') else ('CAGE' if obst == 'CAGE' else 'NOZZLE_LOOPS'))
            out.setdefault(g, {}).setdefault(closure, 0.0)
            out[g][closure] += v['W']
    eddy = m0['eddy']['power_W']
    return dict(charged={g: dict(low=min(v.values()), high=max(v.values()), by_closure=v) for g, v in out.items()}, eddy_W=eddy,
                source='references/evidence/vertex_plasma.json (Engine 1.4, M0-NOMINAL)')


# ---------- G-01 (4 engines) -----------------------------------------------------------------------------------------------------------

def cluster_scene(s):
    """Ship-frame triangles of the four engines, the cluster frame and distribution, and the three radiator blades (thin boxes on their
    planes); the source is engine N1's burn point."""
    c = config(s); est = ve.stations(s); pls = vc.placements(s); tris = []; meta = []
    for j, pl in enumerate(pls):
        t, m = triangles(ve.parts(s), transform=lambda v, pl=pl: vc.to_ship(pl, v), exclude=tuple(c['exclude_parts']))
        off = len(meta)
        for mm in m:
            mm['owner'] = 'OWN_ENGINE' if j == 0 else 'NEIGHBOUR_ENGINES'
        tris += [(a, b, cc, k+off) for a, b, cc, k in t]; meta += m
    extra = list(vc.frame(s))+list(vc.distribution(s)); frame_names = {p['name'] for p in vc.frame(s)}
    import thermal_geometry as tg
    d = tg.blade_of(s)
    for j in range(s['radiators']['count']):
        a = s['prototype']['radiator_phase_deg']+j*s['radiators']['separation_deg']; r = (d['root_radius_m']+d['outer_radius_m'])/2
        extra.append(ve.part(f'RAD_Blade_{j+1}', 'HOT_THERMAL', 'box', 'hot', note='Radiator blade (planform)',
                             center=((d['aft_x_m']+d['front_x_m'])/2, r*math.cos(math.radians(a)), r*math.sin(math.radians(a))),
                             size=(d['front_x_m']-d['aft_x_m'], d['outer_radius_m']-d['root_radius_m'], 0.05), az=a))
    t, m = triangles(extra)
    for mm in m:
        mm['owner'] = 'RADIATORS' if mm['name'].startswith('RAD_') else ('CLUSTER_FRAME' if mm['name'] in frame_names else 'DISTRIBUTION')
    off = len(meta); tris += [(a, b, cc, k+off) for a, b, cc, k in t]; meta += m
    return tris, meta, vc.to_ship(pls[0], (est['burn'], 0.0, 0.0)), d


def cluster(s, n=None, workers=4):
    c = config(s); tris, meta, src, d = cluster_scene(s); n = n or c['cluster_rays']; tw = time.time()
    dirs, rays = trace(tris, meta, src, n, c['shell_thickness_m'], workers)
    first = {}; through = {}; w = 1.0/n
    for seg, ok in rays:
        if not seg:
            first['SPACE'] = first.get('SPACE', 0.0)+w; continue
        o = meta[seg[0][1]]['owner']; first[o] = first.get(o, 0.0)+w
        for t, k, L, cs in seg:
            o2 = meta[k]['owner']
            if o2 != meta[seg[0][1]]['owner']:
                through[o2] = through.get(o2, 0.0)+w
                break
    return dict(rays=n, triangles=len(tris), source=src, first_hit=dict(sorted(first.items(), key=lambda x: -x[1])), behind_first=through,
                wall_s=time.time()-tw, note='First hit from engine N1 (the four engines are symmetric); behind_first: the next owner a ray meets '
                'after leaving its first one (what transmitted photons and neutrons can reach). Hull and habitat beyond the radiator roots are not '
                'in the scene.')


# ---------- material limits, thermal closure, T-REG -------------------------------------------------------------------------------------

def pmds(mid, prop):
    import material_physics as mp
    for T in (None, 298.0, 293.0):
        try:
            q = mp.get_property(mid, prop, T)
        except Exception:
            return None
        if q.get('known', True) and (q.get('value') is not None or q.get('low') is not None):
            return q.get('value') if q.get('value') is not None else q.get('low')
    return None


def materials_screen(s, comp, src_cases):
    """R-05 8.3/8.4 per group: average incident flux and per-pulse fluence at the hottest first-hit point, the shallowest depth the pulse
    may be absorbed in without lifting the surface past its limit (fluence / (rho cp dT_allow)), against the Compton mean free path (the
    deepest photons can reach without photoelectric absorption); PMDS limits or MATERIAL_LIMIT_OPEN."""
    c = config(s); f = vm.plasma(s)['pulse_Hz']; T_op = s['radiators']['temperature']['value']; out = {}
    for g, v in comp.items():
        mats_ = v.get('material') or []
        main = next((m for m in mats_ if m in c['pmds']), None); mid = c['pmds'].get(main) if main else None
        rho = pmds(mid, 'density') if mid else None; cp = pmds(mid, 'specific_heat') if mid else None
        lim = (pmds(mid, 'melting_point') or pmds(mid, 'max_service_temperature')) if mid else None
        Top = c['cold_K'] if main in c['cold_materials'] else T_op
        rows = {}
        for cid, x in src_cases.items():
            P = x['power_W']['photon']+x['power_W']['gamma']; Ep = P/f
            q = v['peak_irradiance_per_W']*P; F = v['peak_irradiance_per_W']*Ep
            dT = (lim-Top) if (lim and lim > Top) else None
            dmin = F/(rho*cp*dT) if (rho and cp and dT) else None
            mu, _ = mu_compton(s, main or 'structure', 100.0)
            lam = 1.0/(mu*rho) if rho else None
            rows[cid] = dict(avg_flux_W_m2=q, pulse_fluence_J_m2=F, min_absorption_depth_m=dmin, compton_mfp_100keV_m=lam,
                             vs_pfc=q/c_pfc(s) if q else 0.0)
        out[g] = dict(material=main, pmds=mid, density=rho, cp=cp, limit_K=lim, operating_K=Top,
                      status='OK' if (rho and cp and lim) else 'MATERIAL_LIMIT_OPEN', cases=rows)
    return out


def c_pfc(s):
    return vp.config(s)['pfc_heat_flux_W_m2'][0]


def thermal(s, comp, charged, src_cases, cl):
    """T-01 per engine and for the four, per source case, low and high brackets, two scopes:
    RADIATION (photons, gammas, neutrons: the 1.5 question) and ALL (plus 1.4's charged-plasma closures and induced eddy heat).
    Hot heat is rejected at the 1800 K radiators; cold heat (20 K) is lifted at carnot_fraction of Carnot to the radiator temperature.
    Low bracket: only coil and cryogenic-line material is at 20 K (cryostat walls assumed to run warm, behind a thermal shield);
    high bracket: everything in a cold group (coil, cryostat, cryo lines) is at 20 K. The photons that reach the radiator blades directly
    (cluster trace) are added to the high bracket."""
    c = config(s); rad = s['radiators']; Th = rad['temperature']['value']; eps = rad['emissivity']['value']
    cap = SIGMA_SB*eps*Th**4*rad['effective_area']['value']; per_m2 = cap/rad['effective_area']['value']
    cop = c['carnot_fraction']*c['cold_K']/(Th-c['cold_K'])
    eddy_lo, eddy_hi = charged['eddy_W']
    strict_cold = [m for m in c['cold_materials'] if m != 'cryostat']
    out = {}
    for cid, x in src_cases.items():
        row = {}
        for scope in ('RADIATION', 'ALL'):
            for b in ('low', 'high'):
                hot = cold = 0.0
                for g, v in comp.items():
                    ph = v['photon'].get(cid, {}).get(b, 0.0); nu = v['neutron_upper'].get(cid, 0.0) if b == 'high' else 0.0
                    ch = v.get('charged_W', {}).get(b, 0.0) if scope == 'ALL' else 0.0
                    mats_ = v.get('material') or []
                    is_cold = any(m in (strict_cold if b == 'low' else c['cold_materials']) for m in mats_)
                    if is_cold:
                        cold += ph+nu+ch
                    else:
                        hot += ph+nu+ch
                if scope == 'ALL':
                    cold += eddy_lo if b == 'low' else eddy_hi
                lift = cold/cop
                total = hot+cold+lift
                blades = (x['power_W']['photon']+x['power_W']['gamma'])*cl['first_hit'].get('RADIATORS', 0.0)*(0.0 if b == 'low' else 1.0)
                four = 4*total+4*blades
                row[f'{scope}_{b}'] = dict(hot_W=hot, cold_W=cold, refrigeration_W=lift, reject_W=total, four_W=four, radiator_direct_W=4*blades,
                                           radiator_m2=four/per_m2, ratio=four/cap)
        out[cid] = row
    return dict(capacity_W=cap, per_m2_W=per_m2, cop=cop, cases=out,
                warm_low_W={sec['id']: dict(T_K=sec['T_K'], load_W=sec['load_W']) for sec in rad['zones']['sections']},
                note='Capacity: radiators.effective_area (both faces, view factor 0.9) at 1800 K and emissivity 0.9, the whole hot radiator, '
                     'with nothing reserved for the ship\'s other hot loads (a favourable assumption). The WARM and LOW sections carry the ship\'s '
                     'own loads and cannot take engine heat at these powers. Storage is not closure (T3).')


def storage(s, reject_W):
    """T3 thermal buffering: seconds of full-power running the engine's own mass can absorb from its design temperature to its limit."""
    m = ve.mass_estimate(s)['total_kg']; cp = 500.0; dT = 1000.0
    return dict(mass_kg=m, cp_J_kgK=cp, dT_K=dT, energy_J=m*cp*dT, seconds=m*cp*dT/reject_W if reject_W else math.inf,
                note='ESTIMATE: the engine mass estimate (vertex_engine.mass_estimate), cp 500 J/(kg K), 1000 K swing. Buffering delays the heat; it never removes it.')


def treg(s, heat_W):
    """T-02: Engine 1.4's T0-T2 with the corrected heat, and T3 buffering."""
    t = vp.treg(s, {'deposition': {'isotropic': {}}, 'xray_absorbed_W': heat_W, 'neutron_absorbed_W': [0.0, 0.0, 0.0]})
    t['T3'] = storage(s, heat_W)
    return t


# ---------- A-01 .. A-03: candidates and the speculative gap ---------------------------------------------------------------------------

def absorbed_share(s, rays, meta, spectrum):
    """Absorbed photon energy share (low, high) of a traced scene and its cold part: low bracket with coil and cryo-line material cold,
    high bracket with cryostat walls also cold (as thermal())."""
    tr = transport(s, rays, meta, spectrum); c = config(s); mat = {m['name']: m['material'] for m in meta}
    strict = [m for m in c['cold_materials'] if m != 'cryostat']
    lo = sum(v['low'] for v in tr.values()); hi = sum(v['high'] for v in tr.values())
    clo = sum(v['low'] for k, v in tr.items() if mat.get(k) in strict); chi = sum(v['high'] for k, v in tr.items() if mat.get(k) in c['cold_materials'])
    return dict(low=lo, high=hi, cold_low=clo, cold_high=chi)


def candidates(s, src, workers=4, n=None):
    """A-01: research configurations traced like the engine, NOMINAL photons only (neutrons and charged heat excluded, which favours
    every row). vs_capacity: four engines' photon heat over the installed hot radiator capacity (low, high bracket); a4_*: the same with
    every cold part behind a perfect warm shield (A4 upper bound: the cold heat moves to the hot circuit, the shield mass is OPEN). Magnetic and structural consequences are reused where a computed run exists
    (1.4 burn_aft_2m) and OPEN otherwise; nothing here changes the active engine."""
    c = config(s); n = n or 4096; nom = src['cases']['NOMINAL']; spec_ = nom['spectrum_share']
    th_cap = SIGMA_SB*s['radiators']['emissivity']['value']*s['radiators']['temperature']['value']**4*s['radiators']['effective_area']['value']
    P = nom['power_W']['photon']; cop = c['carnot_fraction']*c['cold_K']/(s['radiators']['temperature']['value']-c['cold_K'])
    R14 = json.loads(vp.EVIDENCE_PATH.read_text())
    def row(name, tris, meta, srcp, magnetic, structural):
        dirs, rays = trace(tris, meta, srcp, n, c['shell_thickness_m'], workers)
        e = exposure(dirs, rays, meta); a = absorbed_share(s, rays, meta, spec_)
        heat = lambda b: 4*P*((a[b]-a['cold_'+b])+a['cold_'+b]*(1+1/cop))
        warm = lambda b: 4*P*a[b]
        return dict(name=name, intercepted=e['intercepted'], by_group=e['by_group'], absorbed_low=a['low'], absorbed_high=a['high'],
                    cold_low=a['cold_low'], cold_high=a['cold_high'], photon_heat_four_W=[heat('low'), heat('high')],
                    vs_capacity=[heat('low')/th_cap, heat('high')/th_cap],
                    a4_heat_four_W=[warm('low'), warm('high')], a4_vs_capacity=[warm('low')/th_cap, warm('high')/th_cap],
                    magnetic=magnetic, structural=structural)
    rows = []
    tris, meta, s0 = engine_scene(s)
    rows.append(row('A0 current engine (1.2 geometry, M0-NOMINAL)', tris, meta, s0, 'M0-NOMINAL as released (1.3/1.4)', 'Engine 1.2 sizing'))
    t1, m1 = triangles(ve.parts(s), exclude=tuple(c['exclude_parts'])+tuple(p['name'] for p in ve.parts(s) if group_of(p['name']) in ('CAGE', 'COIL_SUPPORTS')))
    rows.append(row('A1 open structure bound (cage and coil supports removed)', t1, m1, s0, 'unchanged', 'NOT ALLOWED: the bound on what any opener structure can gain; the loads still need a path'))
    for k in c['loop_radius_scale']:
        t2, m2, s2 = engine_scene(s, loop_scale=k)
        rows.append(row(f'A2 nozzle loops at {k:g} x radius', t2, m2, s2, 'OPEN: field, capture and forces not recomputed for this geometry', 'OPEN: cage and seats not resized'))
    for dx in c['burn_shifts_m']:
        if dx == 0.0:
            continue
        mag = 'OPEN'
        if dx == -2.0:
            a = R14['alternatives']['A2']['runs']['burn_aft_2m']['shield']; mag = f'1.4 coupled run (M2 field): shield share {min(a.values()):.1%}-{max(a.values()):.1%}'
        rows.append(row(f'A3 burn point {dx:+g} m', tris, meta, (s0[0]+dx, 0.0, 0.0), mag, 'unchanged (target flight longer by the shift)'))
    return rows


def pulse_loading(s, src, th):
    """A5: the fusion power at which the four engines' heat fits the radiators (the rest unchanged), and what it does to the mission:
    thrust and acceleration scale with power at fixed exhaust speed, burn time with its inverse."""
    out = {}
    for cid, v in th['cases'].items():
        for scope in ('RADIATION', 'ALL'):
            k = [th['capacity_W']/v[f'{scope}_{b}']['four_W'] for b in ('high', 'low')]
            out.setdefault(cid, {})[scope] = dict(power_factor=k, thrust_factor=k, burn_time_factor=[1/x for x in k])
    return out


def standoff(s, src, th):
    """A-02: a pusher geometry in which only a shadow shield meets the radiation (the nozzle hardware intercepting nothing, an ideal):
    the shield must cover the ship's disc of radius R at distance D, so it takes (1 - cos atan(R/D)) / 2 of photons and neutrons and must
    reject them at the radiator temperature; the D at which four such shields fit the radiators."""
    c = config(s); cap = th['capacity_W']; out = {}
    for cid, x in src['cases'].items():
        P = x['power_W']['photon']+x['power_W']['neutron']+x['power_W']['gamma']
        fmax = cap/(4*P); fmax = min(fmax, 0.5)
        half = math.acos(1-2*fmax)
        out[cid] = dict(max_shield_fraction=fmax, max_half_angle_deg=math.degrees(half),
                        standoff_m={str(R): R/math.tan(half) for R in (c['ship_shadow_radius_m'], s['radiators']['root_radius']['value'])})
    return out


def gap(s, src, a0, th):
    """A-03: the missing capability, stated as numbers. For the engine as drawn (a0, low transport bracket) the photon share of the yield
    at which four engines' photon heat alone fits the installed hot radiator capacity, with the cold parts as drawn and with them behind
    a perfect warm shield (A4 bound); and the factor by which the bracketed source exceeds it."""
    cap = th['capacity_W']; pz = vm.plasma(s); Pf = pz['yield_J']*pz['pulse_Hz']; cop = th['cop']
    out = dict(fusion_W_per_engine=Pf, photon_share_bracket=src['photon_share_range'])
    for k, per in (('as_drawn', (a0['absorbed_low']-a0['cold_low'])+a0['cold_low']*(1+1/cop)), ('cold_shielded', a0['absorbed_low'])):
        need = cap/(4*Pf*per)
        out[k] = dict(radiator_heat_per_photon_W=per, photon_share_needed=need, factor_low=src['photon_share_range'][0]/need,
                      factor_high=src['photon_share_range'][1]/need)
    out['text'] = ('The photons may be at most this share of the fusion yield for four engines to fit the radiators, even with neutrons and '
                   'charged heat at zero and the most favourable transport bracket.')
    return out


def combined(s, src, workers=4, n=None):
    """The best conventional combination screened: open-structure bound (A1), burn point 6 m aft (A3) and cold parts behind a perfect warm
    shield (A4). Every element is an upper bound on what it can gain."""
    c = config(s); n = n or 4096; nom = src['cases']['NOMINAL']; P = nom['power_W']['photon']
    th_cap = SIGMA_SB*s['radiators']['emissivity']['value']*s['radiators']['temperature']['value']**4*s['radiators']['effective_area']['value']
    ex = tuple(c['exclude_parts'])+tuple(p['name'] for p in ve.parts(s) if group_of(p['name']) in ('CAGE', 'COIL_SUPPORTS'))
    t1, m1 = triangles(ve.parts(s), exclude=ex); x = ve.stations(s)['burn']+min(c['burn_shifts_m'])
    dirs, rays = trace(t1, m1, (x, 0.0, 0.0), n, c['shell_thickness_m'], workers)
    e = exposure(dirs, rays, m1); a = absorbed_share(s, rays, m1, nom['spectrum_share'])
    lo = 4*P*a['low']; hi = 4*P*a['high']
    return dict(name='A1+A3+A4 best conventional bound', intercepted=e['intercepted'], absorbed_low=a['low'], absorbed_high=a['high'],
                heat_four_W=[lo, hi], vs_capacity=[lo/th_cap, hi/th_cap],
                photon_share_needed=th_cap/(4*nom['power_W']['fusion']*a['low']),
                magnetic='OPEN (no structure, burn point moved)', structural='NOT A DESIGN: cage and seats removed')


def alternatives(s, src, th, std):
    """A-02: architectural alternatives, each with the physics that limits it. Numbers come from the source and standoff models."""
    lo = src['cases']['LOW']; nom = src['cases']['NOMINAL']
    return [
        dict(id='ALT-1', name='Hotter ions, cooler electrons (hot-ion mode)', changes='photon generation', value=lo['photon_share'],
             physics='Bremsstrahlung falls with Te; D-He3 at Ti 110 keV with Te/Ti 0.5 gives the LOW case. Electron-ion equilibration in a '
                     'dense burn makes Te/Ti < 1 hard to hold (R2-B runs to Te = Ti).', maturity='OPEN plasma physics', verdict='REDUCES 1.7x, NOT ENOUGH'),
        dict(id='ALT-2', name='Target composition (pure fuel, D-rich mix)', changes='photon generation', value=nom['photon_share'],
             physics='The fuel is already Z_eff-minimal; any high-Z tamper raises bremsstrahlung as Z^2; a D-rich mix adds D-D neutrons and '
                     'tritium (sensitivity rows).', maturity='KNOWN', verdict='NO GAIN'),
        dict(id='ALT-3', name='Optically thick target (photon trapping)', changes='photon escape', value=src['rhoR_solved'],
             physics='Hard bremsstrahlung (30-1000 keV) is not reabsorbed: free-free absorption is negligible and hot-electron Compton gives '
                     'energy to photons. Trapping needs high-Z (raising emission) or rhoR far beyond the 97 g/cm2 the yield already implies.',
             maturity='NOT SUPPORTED', verdict='NO GAIN'),
        dict(id='ALT-4', name='Pusher standoff (open nozzle, only a distant shadow shield)', changes='photon escape',
             value=std['NOMINAL']['standoff_m'],
             physics='A shield at distance D covering a disc of radius R takes (1-cos atan(R/D))/2 of the sky. The magnetic nozzle at that '
                     'distance cannot capture the charged products: thrust is then the shield\'s own ablation and momentum (pulse unit), a '
                     'different engine.', maturity='KNOWN PHYSICS, NEW ENGINE', verdict='CLOSES THERMALLY ONLY AS A DIFFERENT ENGINE'),
        dict(id='ALT-5', name='Magnetic redirection or mirrors for X-rays', changes='photon direction', value=None,
             physics='Photons carry no charge; grazing-incidence optics reflect keV X-rays below about 1 degree and nothing above about 100 keV.',
             maturity='NOT PHYSICAL at these energies', verdict='EXCLUDED'),
        dict(id='ALT-6', name='Direct X-ray conversion (photoelectric / thermionic blanket)', changes='energy conversion', value=None,
             physics='Converts part of the absorbed heat to electricity but rejects the rest at a lower temperature (T-REG T2): more radiator, '
                     'not less, unless the electricity is exported (it has nowhere to go but the driver).', maturity='LOW TRL', verdict='WORSENS'),
    ]


def speculative(s, src, gap_, comb, pulse, th):
    """A-03: the bounded speculative requirements, answered in the brief's eight points. Recorded for the Breakthrough Lab; not canon."""
    g = gap_['cold_shielded']
    return [
        dict(id='SR-1', quantity='photon share of the fusion yield', required=f"<= {g['photon_share_needed']:.2%} (cold parts shielded); "
             f"<= {gap_['as_drawn']['photon_share_needed']:.3%} as drawn", current=f"{gap_['photon_share_bracket'][0]:.1%}-{gap_['photon_share_bracket'][1]:.1%}",
             factor=[g['factor_low'], g['factor_high']], energy='not produced (stays in the charged products)', momentum='adds to the jet',
             machinery='a burn regime below the bremsstrahlung floor: Te far below Ti with no equilibration, which no known plasma state holds',
             harder='every other gate becomes easier', lore='NONE (Fiji is not assigned this capability)'),
        dict(id='SR-2', quantity='engine hardware heat per watt of photons', required=f"<= {th['capacity_W']/(4*src['cases']['LOW']['power_W']['photon']):.4f} W/W at the LOW source",
             current=f"{g['radiator_heat_per_photon_W']:.3f} W/W (Compton-only, the most favourable bracket)", factor=[g['factor_low']],
             energy='transmitted to space through the hardware', momentum='none', machinery='hardware transparent to 30-1000 keV photons yet '
             'structural and superconducting: no known material', harder='magnet shielding, structure', lore='NONE'),
        dict(id='SR-3', quantity='hot radiator capacity at 1800 K', required=f"{comb['vs_capacity'][0]:.0f} x the installed 14.4 GW "
             '(best conventional bound)', current='14.4 GW', factor=[comb['vs_capacity'][0], comb['vs_capacity'][1]],
             energy='rejected as heat', momentum='none', machinery='radiators at the same temperature with that many times the area and mass',
             harder='ship mass, the mission mass budget', lore='NONE'),
        dict(id='SR-4', quantity='fusion power at the installed radiator', required=f"{pulse['NOMINAL']['RADIATION']['power_factor'][1]:.2%} of design "
             '(radiation only, low bracket)', current='100 %', factor=[1/pulse['NOMINAL']['RADIATION']['power_factor'][1]],
             energy='not produced', momentum='thrust falls in proportion', machinery='the same engine run slower', harder='burn time and mission '
             'duration rise in proportion', lore='n/a (conventional)'),
    ]


def gates(s, src, geo, th, comp, ms, cand, comb, gap_):
    G = []
    cl = all(x['ledger']['closes'] for x in src['cases'].values())
    G.append(dict(id='R15-0', name='Source-model validity', status='PASS_BOUNDED', value=f"ledger closes {cl}; photons "
             f"{src['photon_share_range'][0]:.3f}-{src['photon_share_range'][1]:.3f} of the yield (1.4: {src['old_xray_share']:.3f}, "
             f"{src['verdict_1_4']}); no UNKNOWN channel needed; the design jet fits the yield only in "
             f"{', '.join(k for k, v in src['cases'].items() if v['ledger']['jet_fits']) or 'no case'}"))
    lad = geo['ladder']; ns = sorted(lad, key=int); conv = abs(lad[ns[-1]]['intercepted']-lad[ns[-2]]['intercepted'])
    G.append(dict(id='R15-1', name='3D geometry validity', status='PASS', value=f"{geo['parts']} real part meshes, {geo['triangles']} triangles; "
             f"intercept {lad[ns[-1]]['intercepted']:.3f} (1.4: {geo['legacy_hardware']:.3f}); ray ladder change {conv:.4f}, mesh x2 change "
             f"{geo['mesh_refinement']['difference']:+.4f}"))
    G.append(dict(id='R15-2', name='Transport validity', status='BRACKETED', value='interception, attenuation and deposition separated; '
             'Compton (Klein-Nishina) lower bound and full-absorption upper bound; photoelectric and pair cross sections OPEN (no reference data in '
             'the container: xraylib not installed, NIST XCOM unreachable); Geant4 / OpenMC not run'))
    worst = max(ms.items(), key=lambda kv: kv[1]['cases']['LOW']['avg_flux_W_m2'])
    G.append(dict(id='R15-3', name='Component survival', status='FAIL', value=f"peak incident photon flux {worst[1]['cases']['LOW']['avg_flux_W_m2']:.1e} W/m2 "
             f"on {worst[0]} at the LOW source, {worst[1]['cases']['LOW']['vs_pfc']:.0f} x a 10 MW/m2 plasma-facing limit; coils absorb "
             f"{sum(v['photon']['LOW']['low'] for v in comp.values() if v['cold'])/1e9:.0f}-{sum(v['photon']['LOW']['high'] for v in comp.values() if v['cold'])/1e9:.0f} GW "
             'per engine at 20 K'))
    r = th['cases']['LOW']['RADIATION_low']['ratio']
    G.append(dict(id='R15-4', name='System thermal closure', status='FAIL', value=f"four engines need {r:.0f} x the installed hot radiator "
             f"(LOW source, Compton-only, radiation only); best conventional bound {comb['vs_capacity'][0]:.0f} x"))
    G.append(dict(id='R15-5', name='Propulsion compatibility', status='OPEN', value='no candidate closes; A2 loop growth and A3 burn shifts '
             'change the field (only burn_aft_2m has a 1.4 coupled run); A1 removes the load path; A5 keeps the magnets but divides thrust'))
    G.append(dict(id='R15-6', name='Architecture decision', status='OUTCOME_C', value=f"conventional architecture insufficient; the gap is "
             f"{gap_['cold_shielded']['factor_low']:.0f}-{gap_['cold_shielded']['factor_high']:.0f} x in photon share (SR-1)"))
    return G


def pareto(cand, comb, comp):
    """Candidate table for the brief's section 14: the radiation-relevant metrics per row; no single score."""
    rows = []
    for r in cand+[comb]:
        rows.append(dict(name=r['name'], intercepted=r['intercepted'], absorbed=[r['absorbed_low'], r['absorbed_high']],
                         vs_capacity=r['vs_capacity'], cold_shielded_vs_capacity=r.get('a4_vs_capacity', r['vs_capacity']),
                         magnetic=r['magnetic'], structural=r['structural'], verdict='FAILS THERMAL CLOSURE'))
    return rows


def input_hash(s):
    blob = json.dumps([s['vertex_radiation'], s['vertex_engine'], s['vertex_research'], s['radiators']['temperature'], s['radiators']['emissivity'],
                       s['radiators']['effective_area'], s['radiators']['zones']['sections']], sort_keys=True, default=str)
    here = Path(__file__).resolve().parent
    src = b''.join((here/f).read_bytes() for f in ('vertex_radiation.py', 'vertex_engine.py', 'vertex_cluster.py', 'vertex_plasma.py'))
    ev = vp.EVIDENCE_PATH.read_bytes()
    return hashlib.sha256(blob.encode()+src+ev).hexdigest()[:16]


def report(s, quick=False, workers=4):
    import resource
    c = config(s); t0 = time.time(); c0 = time.process_time(); R = dict(version=c['version'], input_hash=input_hash(s))
    R['audit'] = audit_1_4(s)
    src = sources(s); R['sources'] = {k: v for k, v in src.items() if k != 'cases'}
    R['sources']['cases'] = {k: {kk: vv for kk, vv in v.items() if kk != 'history'} for k, v in src['cases'].items()}
    R['sources']['history'] = src['cases']['CONSERVATIVE'].get('history', [])[::max(1, len(src['cases']['CONSERVATIVE'].get('history', []))//60)]
    R['sensitivity'] = sensitivity(s) if not quick else []
    geo = geometry(s, quick=quick, workers=workers); R['geometry'] = geo
    tris, meta, s0 = engine_scene(s); dirs, rays = trace(tris, meta, s0, c['rays'], c['shell_thickness_m'], workers)
    tr = transport(s, rays, meta, src['cases']['NOMINAL']['spectrum_share'])
    R['transport'] = dict(nominal=dict(low=sum(v['low'] for v in tr.values()), high=sum(v['high'] for v in tr.values()),
                                       scattered=sum(v['scattered'] for v in tr.values()), transmitted=sum(v['transmitted'] for v in tr.values())),
                          kn=[dict(E_keV=E, sigma_over_thomson=sigma_kn(E)/(8*math.pi/3*R_E**2), transfer=sigma_kn_transfer(E)/sigma_kn(E))
                              for E in (10.0, 100.0, 511.0, 1000.0, 10000.0)],
                          codes=dict(Geant4='Apache-2.0-like Geant4 licence, free; C++ toolkit, needs a GDML export of the meshes and a physics list '
                                     '(Livermore/Penelope EM); about a day of setup, minutes of CPU at 1e6 photons for this scene',
                                     OpenMC='MIT, free; photon transport since 0.12 with CAD via DAGMC; needs nuclear and photon data libraries '
                                     '(several GB); best for the neutron channel', xraylib='BSD; photoelectric/Compton/pair cross sections; '
                                     'install was not permitted in this session', run='NONE: neither is installed; the brackets are the result'))
    ch = charged_loads(s); R['charged'] = ch
    comp = component_map(s, src['cases'], dirs, rays, meta, charged=ch['charged']); R['components'] = comp
    ms = materials_screen(s, comp, src['cases']); R['materials'] = ms
    cl = cluster(s, workers=workers); R['cluster'] = cl
    th = thermal(s, comp, ch, src['cases'], cl); R['thermal'] = th
    R['treg'] = treg(s, th['cases']['LOW']['RADIATION_low']['reject_W'])
    cand = candidates(s, src, workers=workers, n=4096 if not quick else 1024); R['candidates'] = cand
    comb = combined(s, src, workers=workers, n=4096 if not quick else 1024); R['combined'] = comb
    pulse = pulse_loading(s, src, th); R['pulse_loading'] = pulse
    std = standoff(s, src, th); R['standoff'] = std
    gp = gap(s, src, cand[0], th); R['gap'] = gp
    scan = [r for r in (R['sensitivity'] or sensitivity(s)) if r['model'] == 'R2-A']
    m = min(scan, key=lambda r: r['photon_share'])
    gp['scan_min'] = dict(Ti_keV=m['value'][0], Te_over_Ti=m['value'][1], photon_share=m['photon_share'],
                          factor=m['photon_share']/gp['cold_shielded']['photon_share_needed'],
                          text='The lowest photon share in the R2-A plasma scan (Te/Ti down to 0.1, which no dense burn holds) still exceeds the requirement.')
    R['alternatives'] = alternatives(s, src, th, std)
    R['speculative'] = speculative(s, src, gp, comb, pulse, th)
    R['pareto'] = pareto(cand, comb, comp)
    R['gates'] = gates(s, src, geo, th, comp, ms, cand, comb, gp)
    R['outcome'] = 'C'; R['verdict'] = c['verdict']; R['thermal_verdict'] = c['thermal']
    R['cost'] = dict(wall_s=time.time()-t0, cpu_s_main=time.process_time()-c0, workers=workers,
                     peak_rss_MB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024.0,
                     python=sys.version.split()[0], commands=['python3 src/wayfarer/vertex_radiation.py --evidence',
                                                              'python3 -m unittest discover -s tests -k vertex_radiation'])
    R['wall_s'] = R['cost']['wall_s']
    return R


def evidence(s, path=EVIDENCE_PATH, quick=False):
    R = report(s, quick=quick)
    Path(path).write_text(json.dumps(R, indent=1, default=str)+'\n')
    return R


def summary(R):
    sr = R['sources']; g = R['geometry']; th = R['thermal']
    print(f"Vertex 1.5 radiation  ({R['wall_s']:.0f} s)  hash {R['input_hash']}")
    print(f"  1.4 X-ray share {sr['old_xray_share']:.3f}  ->  photons {sr['photon_share_range'][0]:.3f}-{sr['photon_share_range'][1]:.3f} ({sr['verdict_1_4']})")
    for k, v in sr['cases'].items():
        print(f"    {k:<12} photon {v['photon_share']:.3f} neutron {v['neutron_share']:.4f} jet fits {v['ledger']['jet_fits']}")
    lad = g['ladder']; n = max(lad, key=int)
    print(f"  intercept 3D {lad[n]['intercepted']:.3f} (1.4 {g['legacy_hardware']:.3f}), mesh x2 {g['mesh_refinement']['difference']:+.4f}")
    for cid, r in th['cases'].items():
        print(f"  {cid:<12} radiation x{r['RADIATION_low']['ratio']:.0f}-{r['RADIATION_high']['ratio']:.0f}  all x{r['ALL_low']['ratio']:.0f}-{r['ALL_high']['ratio']:.0f}")
    print(f"  best conventional x{R['combined']['vs_capacity'][0]:.1f}; photon share needed {R['gap']['cold_shielded']['photon_share_needed']:.4f}")
    for x in R['gates']:
        print(f"  {x['id']} {x['status']}: {x['value']}")


if __name__ == '__main__':
    from spec import load
    S = load(Path(__file__).resolve().parents[2])[0]
    if '--evidence' in sys.argv:
        summary(evidence(S, quick='--quick' in sys.argv))
    else:
        summary(report(S, quick='--quick' in sys.argv))
