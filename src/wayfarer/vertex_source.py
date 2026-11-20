"""Vertex Engine 1.6B: fusion radiation source and plasma-hardware interface feasibility (owner brief 2026-11-16 07:16Z, `[vertex_source]`).

Research only. The released engine (four independent Compact Vertex engines, M0-NOMINAL, 1.2 geometry) is the reference; Engines 1.5
(`vertex_radiation`), 1.6 (`vertex_fiji`) and 1.6A (`vertex_fiji_a`), their tables and their evidence are read, never changed. EXT-01
(lab/studies/external-pulse) is a comparison only: src never reads lab/, so its numbers are quoted in `[vertex_source].ext01_quote`.

  A  ledger: 1.5 F0 (854x), 1.6 F6 / W liner and 1.6A ratios put side by side with the configuration, source model, geometry and thermal
     assumptions behind each, so they are not read as consecutive measurements; F0 is recomputed from the 1.5 component map.
  B  source physics: Bosch-Hale reactivities, extended beyond their fit limits for D-D and D-T by Maxwellian integration of the
     Bosch-Hale cross sections (validated against the fit inside its range); D-3He held above 190 keV with a literature bracket;
     a two-temperature (three-species) power balance with every channel separated: fusion by reaction, charged products to ions, to
     electrons, channelled or escaping promptly, bremsstrahlung (electron-ion and electron-electron, impurities), cyclotron emission,
     prompt gammas, D-D and bred D-T neutrons, Spitzer exchange (e-i and i-i), auxiliary heating and the confinement it implies.
  C  cases S0-S6 (1.5 reference, self-consistent, spin-polarized, hot ions, selective He-3 heating, channeling, combined, prompt product
     escape) in three brackets over a Ti scan; the lowest defensible photon share per model, never a prescribed floor.
  D  non-equilibrium: equilibration against burn and confinement times, which states are instantaneous, transient or sustained; the
     dense target's Compton trapping as a two-sided bound.
  E  interface: Engine 1.4 capture and leakage, the irreducible magnet sky, the allowable charged leakage per hardware class worked
     backwards from the drive's share of the radiator, and the photon sky each source would need.
  F  combined budget per case at the demonstrator and the mission operating point (energy conserved, radiator allocated as canon does:
     hot_share for the drive, the rest for the ship), SR-1 recomputed per case, a seven-axis feasibility map with evidence classes.
  G  neutrons (a separate gate), propulsion and mission, sensitivity, a limited fuel comparison, gates R16B-0..9 and the verdict.

Standard library only. python3 src/wayfarer/vertex_source.py [--evidence]"""
import hashlib
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import operating_point as op  # noqa: E402
import vertex_engine as ve  # noqa: E402
import vertex_fiji as vf  # noqa: E402
import vertex_fiji_a as va  # noqa: E402
import vertex_plasma as vp  # noqa: E402
import vertex_radiation as vr  # noqa: E402
import vertex_structure as vs  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = ROOT/'references'/'evidence'/'vertex_source.json'
MEV = vr.MEV; KEV = vr.KEV; AMU = vr.AMU
E_CH = 1.602176634e-19; EPS0 = 8.8541878128e-12; ME = 9.1093837015e-31; MU0 = 4e-7*math.pi
OPT, NOM, PES = 0, 1, 2
NEUTRON_ABSORBED = 0.87               # Engine 1.4: share of the neutron power absorbed by the engine hardware (0.869)
SPITZER_NRL = 1.5                    # textbook Spitzer / NRL e-i relaxation (validation row); the NRL convention is used
BRACKETS = ('optimistic', 'nominal', 'pessimistic')
CLASSES = ('SUPPORTED', 'PLAUSIBLE_EXTRAPOLATION', 'SPECULATIVE_MOTIVATED', 'UNSUPPORTED', 'INCONSISTENT')

# Bosch-Hale (1992) cross-section fits, sigma(E) = S(E) / (E exp(BG / sqrt(E))) mb, E centre-of-mass keV, S = A / (1 + E B) polynomials.
# Only D-D and D-T are used; they reproduce the reactivity fit inside its range to about 1 % (validation rows).
BH_XS = {'DT': (34.3827, (6.927e4, 7.454e8, 2.050e6, 5.2002e4, 0.0), (6.38e1, -9.95e-1, 6.981e-5, 1.728e-4)),
         'DDp': (31.3970, (5.5576e4, 2.1054e2, -3.2638e-2, 1.4987e-6, 1.8181e-10), (0.0, 0.0, 0.0, 0.0)),
         'DDn': (31.3970, (5.3701e4, 3.3027e2, -1.2706e-1, 2.9327e-5, -2.5151e-9), (0.0, 0.0, 0.0, 0.0))}
PAIR = {'DT': ('D', 'T'), 'DHe3': ('D', 'He3'), 'DDp': ('D', 'D'), 'DDn': ('D', 'D')}


def config(s):
    return s['vertex_source']


def cop(s, T):
    return vf.cop(s['vertex_radiation'], T, s['radiators']['temperature']['value'])


def cost(s, T):
    """Radiator watts per watt deposited at temperature T: 1 at or above the radiator, 1 + 1/COP below it (the heat plus the pump work)."""
    Th = s['radiators']['temperature']['value']
    return 1.0 if T >= Th else 1.0+1.0/cop(s, T)


# ---------- B: reactivity -------------------------------------------------------------------------------------------------------------

def sigma_xs(r, E):
    BG, A, B = BH_XS[r]
    S = (A[0]+E*(A[1]+E*(A[2]+E*(A[3]+E*A[4]))))/(1.0+E*(B[0]+E*(B[1]+E*(B[2]+E*B[3]))))
    return S/(E*math.exp(BG/math.sqrt(E)))*1e-31


_SV = {}


def sv_xs(r, T, n=4000):
    """Maxwellian reactivity from the cross section (m^3/s): sqrt(8 / (pi mu)) (kT)^-3/2 integral sigma E exp(-E/kT) dE."""
    key = (r, round(T, 6), n)
    if key not in _SV:
        a, b = PAIR[r]; mu = vr.M_ION[a]*vr.M_ION[b]/(vr.M_ION[a]+vr.M_ION[b])*AMU
        Emax = max(60.0*T, 2000.0); h = Emax/n
        tot = sum(sigma_xs(r, (i+0.5)*h)*(i+0.5)*h*math.exp(-(i+0.5)*h/T) for i in range(n))*h*KEV*KEV
        _SV[key] = math.sqrt(8.0/(math.pi*mu))*(T*KEV)**-1.5*tot
    return _SV[key]


def sv(s, r, T, mode='corrected', k=NOM):
    """Reactivity. legacy: the 1.5 function (held at the fit's upper limit beyond it). corrected: D-D and D-T from the cross sections above
    the fit limit; D-3He held at 190 keV times the literature bracket."""
    if mode == 'legacy' or T <= vr.BH_VALID_KEV[r]:
        return vr.sigma_v(r, T)
    if r == 'DHe3':
        return vr.sigma_v(r, T)*config(s)['dhe3_hold'][k]
    return sv_xs(r, T, config(s)['xs_points'])


def t_eff(a, Ta, b, Tb):
    """Two Maxwellians at different temperatures react as one at the reduced-mass temperature (m_b Ta + m_a Tb) / (m_a + m_b) (exact)."""
    ma, mb = vr.M_ION[a], vr.M_ION[b]
    return (mb*Ta+ma*Tb)/(ma+mb)


def tau_ex(na, Za, ma, Ta, nb, Zb, mb, Tb, lnL):
    """Spitzer two-species energy relaxation: dT_a/dt = (T_b - T_a) / tau_ab with
    tau_ab = 3 (2 pi)^3/2 eps0^2 m_a m_b (kT_a/m_a + kT_b/m_b)^3/2 / (n_b Z_a^2 Z_b^2 e^4 lnL); masses in kg, T in keV."""
    return 3.0*(2*math.pi)**1.5*EPS0**2*ma*mb*(Ta*KEV/ma+Tb*KEV/mb)**1.5/(nb*Za*Za*Zb*Zb*E_CH**4*lnL)


def validation(s):
    rows = []
    for r, Ts in (('DT', (20.0, 50.0, 100.0)), ('DDn', (20.0, 50.0, 100.0)), ('DDp', (20.0, 50.0, 100.0))):
        for T in Ts:
            a, b = sv_xs(r, T, config(s)['xs_points']), vr.sigma_v(r, T)
            rows.append(dict(case=f'{r} cross-section integral vs Bosch-Hale reactivity at {T:g} keV', rel_error=abs(a/b-1), passes=abs(a/b-1) < 0.02,
                             note='validates the cross-section coefficients inside the fit range'))
    pk = max(sigma_xs('DT', E) for E in range(30, 150))*1e28
    rows.append(dict(case='D-T cross-section peak (barn)', rel_error=abs(pk/5.0-1), passes=abs(pk/5.0-1) < 0.05, note='about 5 b near 64 keV (textbook)'))
    # Spitzer two-species exchange against the 1.5 / NRL electron-ion rate (D plasma, Te 50 keV, Ti 100 keV)
    n = 1e21; lnL = vr.lnlambda(n, 50.0)
    nu = 3.2e-9*(n*1e-6)*lnL/(vr.M_ION['D']*(50e3)**1.5)
    tau = tau_ex(n, 1, ME, 50.0, n, 1, vr.M_ION['D']*AMU, 100.0, lnL)
    rows.append(dict(case='Spitzer e-i relaxation / the NRL rate used by 1.5', rel_error=1/tau/nu-1, passes=None,
                     note='INFO: the textbook Spitzer form is 1.5x the NRL rate; the NRL convention is kept throughout (continuity with 1.5 and 1.6) '
                          'and the ion-ion exchange is normalised to it; the factor is an exchange uncertainty carried in the brackets'))
    lo = sv(s, 'DDn', 200.0)/vr.sigma_v('DDn', 200.0)
    rows.append(dict(case='D-D reactivity at 200 keV, corrected / held (1.5, 1.6)', rel_error=lo-1, passes=lo > 1.0,
                     note='the held fit undercounts D-D neutrons above 100 keV (fidelity finding, not a pass criterion)'))
    return dict(rows=rows, all_pass=all(r['passes'] for r in rows if r['passes'] is not None))


# ---------- B: two-temperature power balance -----------------------------------------------------------------------------------------

def opts(s, case, k):
    """The physics settings of one case in bracket k."""
    c = config(s); f = vf.config(s)
    pol = vf.pol_factor(f, k) if case['pol'] else 1.0
    return dict(mode=case['reactivity'], k=k, pol=pol, dd=f['dd_factor'][k] if case['dd'] else 1.0,
                channel=c['channel_share'][k] if case['channel'] else 0.0, dep=case['deposition'],
                he_ratio=c['he3_hot_ratio'][k] if case['he3_hot'] else 1.0, dzeff=c['impurity_dzeff'][k],
                beta=c['sync_beta'][k] if case['magnetized'] else None, sync_escape=c['sync_escape'][k] if case['magnetized'] else 0.0,
                ne=c['densities_m3'][case['density']], aux=case['aux'])


def powers(s, Ti, Te, o, burnup):
    """All power densities (W/m3) of a D-3He (1:1) burn with ions D at Ti and He-3 at he_ratio Ti, electrons at Te; quasineutral."""
    ne = o['ne']; nD = ne/3.0; nHe = ne/3.0; TD = Ti; THe = Ti*o['he_ratio']; m = o['mode']; k = o['k']
    zeff = (nD+4*nHe)/ne+o['dzeff']
    rD = nD*nHe*sv(s, 'DHe3', t_eff('D', TD, 'He3', THe), m, k)*o['pol']
    rn = 0.5*nD*nD*sv(s, 'DDn', TD, m, k)*o['dd']; rp = 0.5*nD*nD*sv(s, 'DDp', TD, m, k)*o['dd']; rT = rp*burnup
    # energy per reaction = the sum of its product energies (equal to Q within 0.03 %: the tabulated splits are rounded), so the ledger closes
    Pf = {rx: rate*sum(vr.PRODUCTS[rx].values())*MEV for rx, rate in (('DHe3', rD), ('DDn', rn), ('DDp', rp), ('DT', rT))}
    g = s['vertex_radiation']['gamma_branch'][k]*s['vertex_radiation']['gamma_MeV']*MEV*rD
    ions = [(nD, 1, vr.M_ION['D']), (nHe, 2, vr.M_ION['He3'])]
    wD = nD*1/vr.M_ION['D']; wHe = nHe*4/vr.M_ION['He3']                         # Sivukhin ion partition ~ n Z^2 / A
    ch = dict(to_i=0.0, to_e=0.0, channelled=0.0, escaped=0.0, total=0.0)
    for rate, rx in ((rD, 'DHe3'), (rn, 'DDn'), (rp, 'DDp'), (rT, 'DT')):
        for sp, e in vr.PRODUCTS[rx].items():
            if sp == 'n':
                continue
            P = rate*e*MEV; ch['total'] += P; dep = P*o['dep']; ch['escaped'] += P-dep
            fi = vr.ion_share(e*1e3, Te, vr.M_ION[sp], ions); pe = dep*(1-fi)
            ch['to_i'] += dep*fi; ch['channelled'] += o['channel']*pe; ch['to_e'] += (1-o['channel'])*pe
    f = (ch['total']-g)/ch['total'] if ch['total'] > 0 else 1.0               # the prompt gamma branch takes its energy from the products
    ch = {x: v*f for x, v in ch.items()}
    neutron = (rn*vr.PRODUCTS['DDn']['n']+rT*vr.PRODUCTS['DT']['n'])*MEV
    lnL = vr.lnlambda(ne, Te)
    ex_eD = sum(3.2e-9*Z*Z*(n*1e-6)*lnL/(A*(Te*1e3)**1.5) for n, Z, A in ions[:1])*1.5*ne*(TD-Te)*KEV
    ex_eHe = 3.2e-9*4*(nHe*1e-6)*lnL/(vr.M_ION['He3']*(Te*1e3)**1.5)*1.5*ne*(THe-Te)*KEV
    tau = tau_ex(nD, 1, vr.M_ION['D']*AMU, TD, nHe, 2, vr.M_ION['He3']*AMU, THe, lnL)
    ex_HeD = 1.5*nD*(THe-TD)*KEV/tau/SPITZER_NRL
    brems = vr.brems_W_m3(ne, Te, zeff)
    if o['beta']:
        p = (ne*Te+nD*TD+nHe*THe)*KEV; B2 = 2*MU0*p/o['beta']
        sync_thin = 6.21e-17*B2*ne*Te*(1+Te/204.0); sync = sync_thin*o['sync_escape']
    else:
        sync_thin = sync = 0.0
    return dict(Pf=Pf, fusion=sum(Pf.values()), charged=ch, gamma=g, neutron=neutron, brems=brems, sync=sync, sync_thin=sync_thin,
                ex_e=ex_eD+ex_eHe, ex_eD=ex_eD, ex_eHe=ex_eHe, ex_HeD=ex_HeD, wD=wD/(wD+wHe), zeff=zeff, ne=ne, TD=TD, THe=THe, Te=Te,
                ion_split_D=wD/(wD+wHe))


def electron_net(P):
    """Electron gain minus loss: product share + exchange - bremsstrahlung - escaping cyclotron emission."""
    return P['charged']['to_e']+P['ex_e']-P['brems']-P['sync']


def solve(s, Ti, o, burnup, Te_fixed=None):
    """Te from the electron balance (or prescribed), then the ion balance: each ion species gains its product share (channelled energy to
    ions too) and the ion-ion and electron exchange; a deficit is auxiliary heating (only if the case allows it); a surplus leaves as plasma
    (the transport loss that sets the implied confinement). Returns every channel as a share of fusion power and the conservation check."""
    if Te_fixed is not None:
        Te = Te_fixed
    else:
        lo, hi = 0.05, 5.0*Ti*max(o['he_ratio'], 1.0)
        if electron_net(powers(s, Ti, hi, o, burnup)) > 0:
            Te = hi
        else:
            for _ in range(80):
                mid = math.sqrt(lo*hi)
                lo, hi = (mid, hi) if electron_net(powers(s, Ti, mid, o, burnup)) > 0 else (lo, mid)
            Te = math.sqrt(lo*hi)
    P = powers(s, Ti, Te, o, burnup); ch = P['charged']; Pf = P['fusion']
    to_ions = ch['to_i']+ch['channelled']
    netD = to_ions*P['ion_split_D']+P['ex_HeD']-P['ex_eD']
    netHe = to_ions*(1-P['ion_split_D'])-P['ex_HeD']-P['ex_eHe']
    aux = max(0.0, -netD)+max(0.0, -netHe)
    e_net = electron_net(P)                                                    # zero when balanced; != 0 for a prescribed Te
    photons = P['brems']+P['sync']
    exhaust = ch['total']+aux-photons                                          # all charged / plasma energy that is not radiated
    balance = Pf+aux-(photons+P['neutron']+P['gamma']+exhaust)
    partition = ch['to_i']+ch['to_e']+ch['channelled']+ch['escaped']-ch['total']
    surplus = max(netD, 0.0)+max(netHe, 0.0)+max(e_net, 0.0)
    nD = P['ne']/3.0
    stored = 1.5*(P['ne']*Te+nD*P['TD']+nD*P['THe'])*KEV
    ntau = stored/surplus*P['ne'] if surplus > 0 else math.inf
    sustained = aux <= 1e-12*Pf
    return dict(Ti_keV=Ti, THe_keV=P['THe'], Te_keV=Te, Te_over_Ti=Te/Ti, zeff=P['zeff'], fusion_W_m3=Pf,
                photon_share=photons/Pf, brems_share=P['brems']/Pf, sync_share=P['sync']/Pf, sync_thin_share=P['sync_thin']/Pf,
                neutron_share=P['neutron']/Pf, gamma_share=P['gamma']/Pf, charged_share=ch['total']/Pf,
                to_electrons_share=ch['to_e']/Pf, to_ions_share=ch['to_i']/Pf, channelled_share=ch['channelled']/Pf, escaped_share=ch['escaped']/Pf,
                exchange_share=P['ex_e']/Pf, ion_ion_share=P['ex_HeD']/Pf, aux_share=aux/Pf, gain=Pf/aux if aux > 0 else math.inf,
                exhaust_share=exhaust/Pf, electron_imbalance_share=e_net/Pf, energy_error=balance/Pf, partition_error=partition/Pf, sustained=sustained,
                ntau_m3s=ntau, DD_share=(P['Pf']['DDn']+P['Pf']['DDp'])/Pf, DT_share=P['Pf']['DT']/Pf, ne_m3=P['ne'])


def useful(s, row, o, k):
    """Net useful directed energy per unit fusion: the captured exhaust less the charged energy spent on recirculating power (auxiliary
    heating at its wall-plug efficiency, spin preparation), drawn from the stream by direct conversion."""
    c = config(s); f = vf.config(s)
    prep = f['polarization_J_kg']/s['physics']['operating_point']['dhe3_specific_energy_J_kg']/s['physics']['operating_point']['burnup'] if o['pol'] > 1 else 0.0
    wall = row['aux_share']/c['aux_coupling'][k]+prep
    drawn = wall/c['conversion'][k]
    U = c['capture'][k]*(row['exhaust_share']-drawn)
    losses = (wall-row['aux_share'])+(drawn-wall)
    return dict(wall_share=wall, drawn_share=drawn, prep_share=prep, loss_share=losses, useful_share=U)


def burnup():
    return vf.r15()['sources']['cases']['CONSERVATIVE']['burn']['tritium_burnup']


def cases(s):
    """S0-S6 in three brackets over the Ti grid and, below the radiative electron balance, a scan of colder electrons that lose the difference
    by transport (the plasma carries it into the exhaust; it implies an electron energy confinement n tau_Ee). A state is valid when it is
    sustained by the products, or uses the auxiliary heating its case allows, and still delivers useful_floor of fusion as useful energy;
    the best is the valid state with the least photon share. S0 is the prescribed 1.5 state, reproduced from vertex_radiation.analytic_case."""
    c = config(s); Tb = burnup(); out = {}
    low = next(x for x in s['vertex_radiation']['cases'] if x['id'] == 'LOW')
    ref = vr.analytic_case(s, low, Tb)
    keep = ('Ti_keV', 'Te_keV', 'photon_share', 'neutron_share', 'aux_share', 'useful_share', 'valid', 'mode', 'sustained')
    for case in c['cases']:
        res = dict(id=case['id'], name=case['name'], brackets={})
        for k in (OPT, NOM, PES):
            o = opts(s, case, k); scan = []
            if case['Te'] == 'prescribed':
                r = solve(s, case['Ti_keV'], o, Tb, Te_fixed=case['Ti_keV']*case['Te_over_Ti']); r.update(useful(s, r, o, k))
                r['valid'] = True; r['mode'] = 'PRESCRIBED'; scan.append(r)
            else:
                for Ti in c['Ti_grid_keV']:
                    rad = solve(s, Ti, o, Tb); Te_rad = rad['Te_keV']
                    for f in c['Te_fractions']:
                        r = rad if f == 1.0 else solve(s, Ti, o, Tb, Te_fixed=Te_rad*f)
                        r = dict(r); r.update(useful(s, r, o, k)); r['mode'] = 'RADIATIVE' if f == 1.0 else 'TRANSPORT'
                        r['ntau_Ee_m3s'] = 1.5*r['ne_m3']*r['Te_keV']*KEV/(r['electron_imbalance_share']*r['fusion_W_m3'])*r['ne_m3'] if r['electron_imbalance_share'] > 1e-12 else math.inf
                        r['valid'] = (r['sustained'] or o['aux']) and r['useful_share'] >= c['useful_floor']
                        scan.append(r)
            ok = [r for r in scan if r['valid']]
            best = min(ok, key=lambda r: r['photon_share']) if ok else None
            okr = [r for r in ok if r['mode'] != 'TRANSPORT']
            radiative = min(okr, key=lambda r: r['photon_share']) if okr else None
            res['brackets'][BRACKETS[k]] = dict(radiative=radiative, settings={x: o[x] for x in ('pol', 'dd', 'channel', 'dep', 'he_ratio', 'dzeff', 'beta', 'sync_escape', 'ne')},
                                                scan=[{x: r[x] for x in keep} for r in scan], best=best, n_valid=len(ok))
        if case['id'] == 'S0':
            b = res['brackets']['optimistic']['best']
            res['reproduction'] = dict(analytic_photon=ref['photon_share'], engine_photon=b['photon_share'], released=vf.r15()['sources']['cases']['LOW']['photon_share'],
                                       matches=abs(ref['photon_share']/vf.r15()['sources']['cases']['LOW']['photon_share']-1) < 1e-9 and abs(b['photon_share']/ref['photon_share']-1) < 1e-3,
                                       electron_imbalance_share=b['electron_imbalance_share'],
                                       note='at the prescribed Te/Ti 0.5 the electrons gain this share of fusion power more than they radiate; 1.5 removed it '
                                            'implicitly. In the dense target nothing removes it within the burn, so S0 is an instantaneous state only')
        out[case['id']] = res
    return out


def floor_audit(s, C):
    """The 1.6 floor (16.4 %, polarized, 90 % channel, 150 keV) re-derived: 1.6 set n_He = n_D = n_e / 4 (three electrons per pair counted as
    four), which inflates bremsstrahlung against fusion by 4/3, and held D-D at 100 keV. Same levers, corrected composition and reactivity."""
    f = vf.config(s); Tb = burnup(); pol = vf.pol_factor(f, OPT)
    with vf.levers():
        old = vf.floor(f, 150.0, channel=0.9, pol=pol, dd=f['dd_factor'][OPT])
    o = dict(mode='legacy', k=NOM, pol=pol, dd=f['dd_factor'][OPT], channel=0.9, dep=1.0, he_ratio=1.0, dzeff=0.0, beta=None, sync_escape=0.0, ne=1e31, aux=False)
    leg = solve(s, 150.0, o, 0.0)
    cor = solve(s, 150.0, dict(o, mode='corrected'), Tb)
    return dict(released_1_6=old['photon_share'], composition_fixed=leg['photon_share'], composition_and_reactivity_and_tritium=cor['photon_share'],
                Te_1_6=old['Te_keV'], Te_fixed=leg['Te_keV'], factor=old['photon_share']/leg['photon_share'],
                note='1.6 floor() counted n_e = 4 n_He with n_D = n_He (quasineutrality gives 3); the 16.4 % falls to the composition-fixed value. '
                     'The 1.6 evidence is not changed; this is the 1.6B reading of it.')


# ---------- D: non-equilibrium and transient states -----------------------------------------------------------------------------------

def nonequilibrium(s, C):
    """Equilibration against the burn: in the dense target (1.5 R2-B) and per sustained case (n tau_ei against the implied n tau_E, both
    density-independent). Classifies: INSTANTANEOUS (prescribed, electron balance not met), TRANSIENT (Ti > Te only for less than one
    exchange time), SELF_CONSISTENT_TRANSIENT (the coupled 1.6 burns, which include it), SUSTAINED (balance met, aux within the case)."""
    R = vf.r15(); b = R['sources']['cases']['CONSERVATIVE']['burn']; F = json.loads(vf.EVIDENCE_PATH.read_text())
    M = b['mass_kg']; R0 = b['R0_m']; rho = M/(4/3*math.pi*R0**3)
    ne = rho/((vr.M_ION['D']+vr.M_ION['He3'])*AMU)*3.0
    Te = 50.0; lnL = vr.lnlambda(ne, Te)
    tei = 1/(3.2e-9*(ne/3*1e-6)*lnL/(vr.M_ION['D']*(Te*1e3)**1.5)+3.2e-9*4*(ne/3*1e-6)*lnL/(vr.M_ION['He3']*(Te*1e3)**1.5))
    target = dict(ne_m3=ne, rho_kg_m3=rho, R0_m=R0, burn_s=b['duration_s'], tau_ei_s=tei, ratio=tei/b['duration_s'],
                  verdict='Ti > Te cannot be held in the dense target: electrons and ions exchange energy within about '
                          f'{tei/b["duration_s"]:.1%} of the burn time, so a hot-ion start relaxes almost at once (1.5 R2-B already follows this)')
    rows = []
    for cid, cs in C.items():
        bb = cs['brackets']['nominal']['best']
        if not bb:
            continue
        ntei = None
        if bb['Te_keV'] < bb['Ti_keV']:
            n = bb['ne_m3']; T = bb['Te_keV']; l = vr.lnlambda(n, T)
            nu = 3.2e-9*(n/3*1e-6)*l/(vr.M_ION['D']*(T*1e3)**1.5)+3.2e-9*4*(n/3*1e-6)*l/(vr.M_ION['He3']*(T*1e3)**1.5)
            ntei = n/nu
        state = ('INSTANTANEOUS' if cid == 'S0' else 'SUSTAINED' if bb['sustained'] else 'SUSTAINED_WITH_AUX')
        rows.append(dict(case=cid, state=state, Te_over_Ti=bb['Te_over_Ti'], ntau_ei_m3s=ntei, ntau_E_m3s=bb['ntau_m3s'], aux_share=bb['aux_share'],
                         electron_imbalance_share=bb['electron_imbalance_share'],
                         maintained=bb['sustained'] or bb['aux_share'] > 0, note='Ti > Te is held by the auxiliary heating it costs' if bb['aux_share'] > 0 else
                         ('Ti > Te is held by the products alone' if bb['Te_over_Ti'] < 0.999 else 'Te = Ti')))
    coupled = [dict(r, state='SELF_CONSISTENT_TRANSIENT') for r in F['fusion']['coupled']]
    return dict(target=target, rows=rows, coupled=coupled, coupled_min=min(r['photon_share'] for r in coupled), trapping=trapping(s),
                rule='Ti/Te is set by the balance of exchange (n^2) against heating (n^2): density cancels except in ln Lambda, so the '
                     'sustained cases hold at any density; only finite confinement (n tau_E) adds loss, and n tau_ei ~ n tau_E means the '
                     'two-temperature state is marginal wherever the burn is confined long enough to burn')


def trapping(s):
    """Compton trapping in the dense target (optical depth about 18 at ignition, 1.5): photons emitted while tau > 1 diffuse out over
    tau^2 R / c, longer than the burn. Lower bound: radiation coupled to the expanding plasma loses energy as 1/R until it escapes at
    R_esc = R0 sqrt(tau0), and the work returns to the plasma (charged exhaust). Upper bound: with Kompaneets y >> 1 the photons are
    Comptonized up by the hot electrons, which raises the electrons' losses. REDUCED_MODEL bracket; only radiation hydrodynamics settles it."""
    R = vf.r15(); b0 = R['sources']['cases']['CONSERVATIVE']['burn']
    case = dict(next(x for x in s['vertex_radiation']['cases'] if x['id'] == 'CONSERVATIVE'), rhoR_g_cm2=b0['rhoR_g_cm2'])
    b = vr.burn(s, case, spectrum=False); h = b['history']; tau0 = b['compton_depth0']; R0 = b['R0_m']; Resc = R0*math.sqrt(tau0)
    w = ws = 0.0
    for (t0, _, Te0, R_0, _), (t1, _, Te1, R_1, _) in zip(h, h[1:]):
        Te = 0.5*(Te0+Te1); Rm = 0.5*(R_0+R_1); x = math.sqrt(max(Te, 0.0))/Rm**3*(t1-t0)
        w += x; ws += x*min(1.0, Rm/Resc)
    keep = ws/w if w else 1.0
    th = 4*50.0/511.0*tau0**2
    return dict(compton_depth0=tau0, R0_m=R0, R_escape_m=Resc, diffusion_s=tau0**2*R0/2.998e8, burn_s=b['duration_s'],
                photon_kept_lower=keep, photon_share_lower=b['photon_share']*keep, photon_share_released=b['photon_share'], kompaneets_y=th,
                evidence='REDUCED_MODEL', note='a two-sided bound: adiabatic recovery can lower the photon share by at most about '
                f'{1/keep:.1f}x; Comptonization (y about {th:,.0f}) pushes the other way. The sign is unresolved without radiation-hydrodynamic transport.')


# ---------- E: interface ----------------------------------------------------------------------------------------------------------------

def band(z, r, a):
    """Sky share of a torus (major radius r, minor a, axial distance z) seen from the burn."""
    d = math.hypot(z, r); th = math.atan2(r, z); dl = math.asin(min(1.0, a/d))
    return 0.5*(math.cos(max(th-dl, 0.0))-math.cos(min(th+dl, math.pi)))


def geometry(s):
    """6.2 analytical escape geometry (no model change): the sky the magnets themselves take (cryostat tori, irreducible while they surround
    the burn), against the 1.5 real-mesh hardware sky, and how both change if the burn sits farther aft (the coil current for the same
    field at the burn rises as (r^2 + z^2)^1.5 / r^2)."""
    st = ve.stations(s); cs = vs.coils(s); R = vf.r15(); fh = R['cluster']['first_hit']; rows = []
    for dx in s['vertex_radiation']['burn_shifts_m']+[5.0, 10.0, 20.0]:
        b = st['burn']-dx
        sky = sum(band(q['x']-b, q['r'], q['cryostat']) for q in cs)
        L2 = next(q for q in cs if q['name'] == 'L2'); z0 = L2['x']-st['burn']; z1 = L2['x']-b
        kI = ((L2['r']**2+z1**2)**1.5)/((L2['r']**2+z0**2)**1.5)
        rows.append(dict(shift_m=dx, coil_sky=sky, current_factor_L2=kI))
    rows = sorted({r['shift_m']: r for r in rows}.values(), key=lambda r: r['shift_m'])
    th = R['thermal']['cases']['LOW']['RADIATION_low']; P = R['sources']['cases']['LOW']['power_W']['photon']
    comp = R['components']; dep_lo = sum(v['photon']['LOW']['low'] for v in comp.values())/P; dep_hi = sum(v['photon']['LOW']['high'] for v in comp.values())/P
    cold_lo = th['cold_W']/(th['hot_W']+th['cold_W'])
    return dict(hardware_sky_mesh=fh['OWN_ENGINE']+fh['CLUSTER_FRAME']+fh['NEIGHBOUR_ENGINES']+fh['RADIATORS']+fh['DISTRIBUTION'],
                space_sky=fh['SPACE'], absorbed_low=dep_lo, absorbed_high=dep_hi, cold_share_low=cold_lo, coil_sky=rows[0]['coil_sky'], shifts=rows,
                note='absorbed_low / high: the 1.5 deposited share of the photon power (Compton-only / full absorption); the coil sky is a floor on '
                     'interception for any engine whose magnets surround the burn: shading a coil puts the shade in the same sky')


def interface(s, C, G):
    """6.1 capture (Engine 1.4 ledger, unchanged) and 6.3 allowable leakage worked backwards from the drive's radiator share per class."""
    Pz = json.loads(vp.EVIDENCE_PATH.read_text()); m0 = Pz['thermal']['M0-NOMINAL']; c = config(s)
    cap = vf.r15()['thermal']['capacity_W']; hs = s['physics']['operating_point']['hot_share']; Be = hs*cap/4
    classes = [('HOT_STRUCTURE', s['radiators']['temperature']['value']), ('RADIATION_FACING_ARMOUR', c['armour_K']),
               ('WARM_MACHINERY', c['warm_K']), ('CRYOGENIC_SUPERCONDUCTOR', s['vertex_radiation']['cold_K'])]
    pw = power_points(s)
    allow = []
    for name, T in classes:
        k = cost(s, T)
        row = dict(cls=name, T_K=T, cost=k)
        for pname, Pf in pw.items():
            ch = Pf*C['S0-SC']['brackets']['nominal']['best']['exhaust_share']
            row[pname] = dict(allowed_W=Be/k, allowed_share=Be/k/ch)
        allow.append(row)
    led = {cl: dict(aft=v['aft'], hardware=v['hardware'], shield=v['shield'], impulse_Ns=v['impulse_Ns']) for cl, v in m0['ledger'].items()}
    det = Pz['detachment']['M0-NOMINAL']['domain_extension'][-1]
    return dict(capture=led, detachment=dict(aft_first_pass=det['aft_first_pass'], stopped=det['stopped'], downstream_m=det['downstream_m']),
                drive_budget_W=hs*cap, per_engine_W=Be, allowable=allow, best_computed_leak=min(v['hardware'] for v in led.values()),
                literature=[dict(item='Laboratory magnetic-nozzle detachment', value='VX-200: detachment within a few metres of the throat; '
                                 'low-power nozzles below 10 % efficiency (Collard & Jorns 2019)', evidence='LITERATURE'),
                            dict(item='Leakage at 1e-4 to 1e-7 of a fusion-product stream', value='no published experiment or model', evidence='UNRESOLVED')],
                note='the allowed shares assume photons and neutrons put nothing in the budget (upper bound on the leakage allowance)')


def power_points(s):
    """Per-engine fusion power: the 1.5 demonstrator (vm.plasma yield x rate) and the mission operating point at the canon directed
    efficiency (peak jet power / 4 / 0.8)."""
    b = op.burn(s); q = s['physics']['operating_point']
    return dict(demonstrator=vf.r15()['sources']['cases']['LOW']['power_W']['fusion'], mission=b['peak_jet_power_W']/4/q['directed_efficiency'])


# ---------- F: combined budget --------------------------------------------------------------------------------------------------------

def budget(s, row, U, Pf, k, shield=False, leak=None):
    """One engine at fusion power Pf: every channel to its destination and the radiator watts, energy conserved. Photon and neutron heat
    from the 1.5 component map scaled to this source (vf.closure; low and high transport brackets; shield=True moves the cold parts behind a
    1300 K tungsten liner as 1.6 did); charged leakage at the Engine 1.4 hardware share (or `leak`), split shield (armour) / coils
    (cryostat: hot in the low bracket, 20 K in the high, as 1.5 counted); recirculating losses at loss_K."""
    c = config(s); L = vf.r15()['sources']['cases']['LOW']['power_W']; Pz = json.loads(vp.EVIDENCE_PATH.read_text())['thermal']['M0-NOMINAL']['ledger']
    ph = row['photon_share']*Pf; nn = row['neutron_share']*Pf; g = row['gamma_share']*Pf; aux = row['aux_share']*Pf
    cl = ('aft', 'channelled', 'isotropic')[k]; hw = Pz[cl]['hardware'] if leak is None else leak; sh = Pz[cl]['shield']/Pz[cl]['hardware'] if Pz[cl]['hardware'] else 0.5
    ex = row['exhaust_share']*Pf; drawn = U['drawn_share']*Pf; loss = U['loss_share']*Pf
    stream = ex-drawn; leak_W = stream*hw; jet = stream-leak_W
    rad = vf.closure(s, 'case', ph/L['photon'], nn/L['neutron'], liner=dict(T_K=c['armour_K'], n_share=1.0) if shield else None)
    k20 = cost(s, s['vertex_radiation']['cold_K']); ka = cost(s, c['armour_K']); kl = cost(s, c['loss_K'])
    out = {}
    for b in ('low', 'high'):
        r = rad['brackets'][b]
        lk = leak_W*sh*ka+leak_W*(1-sh)*(1.0 if b == 'low' else k20)
        rej = r['four_W']/4+lk+loss*kl                                         # photon/neutron map (incl. blades) + leakage + losses
        out[b] = dict(photon_neutron_W=r['four_W']/4, leak_W=leak_W, leak_reject_W=lk, loss_W=loss, loss_reject_W=loss*kl, reject_W=rej,
                      cryo_W=r['cold_W'], refrigeration_W=r['refrigeration_W'], hot_W=r['hot_W'])
    # destinations (energy): jet, escaping photons + neutrons + gamma (not deposited), deposited radiation, leakage, losses
    dep_ph = rad['brackets']['low']['hot_W']+rad['brackets']['low']['cold_W']+rad['brackets']['low']['warm_W']
    dest = dict(jet_W=jet, leak_W=leak_W, losses_W=loss, radiation_W=ph+nn+g, deposited_radiation_low_W=dep_ph)
    err = Pf-(jet+leak_W+loss+ph+nn+g)                                       # the auxiliary power recirculates: drawn = aux + losses
    mom = dict(jet_thrust_N=2*jet/op.burn(s)['exhaust_velocity_m_s'], photon_recoil_N_max=ph/2.998e8)
    return dict(Pf_W=Pf, aux_W=aux, destinations=dest, brackets=out, energy_error=err/Pf, momentum=mom, shield=shield)


def allocation(s):
    cap = vf.r15()['thermal']['capacity_W']; q = s['physics']['operating_point']; rad = s['radiators']
    return dict(installed_W=cap, drive_W=q['hot_share']*cap, ship_W=(1-q['hot_share'])*cap, per_engine_W=q['hot_share']*cap/4,
                warm_sections=vf.r15()['thermal']['warm_low_W'], refrigeration_in_drive=True, temperature_K=rad['temperature']['value'],
                note='Canon (physics.operating_point.hot_share): the drive may use 75 % of the ideal 1800 K rejection; the rest (about 3.6 GW) '
                     'carries EYE, Crown, machinery and margin. Cryogenic heat and its pump work are rejected inside the drive share. The WARM and '
                     'LOW sections carry the ship\'s own loads (MW) and take no engine heat.')


def combined(s, C):
    """7.1-7.2 per case and bracket at both power points: the budget, its ratio to the drive allocation and SR-1 recomputed: the photon share
    that would fit once this case's neutrons, leakage and losses are paid; FAIL when they alone exceed the allocation."""
    A = allocation(s); pw = power_points(s); jet = op.burn(s)['peak_jet_power_W']/4; rows = []
    for cid, cs in C.items():
        for bn, bk in cs['brackets'].items():
            r = bk['best']
            if not r:
                continue
            k = BRACKETS.index(bn); o = opts(s, next(x for x in config(s)['cases'] if x['id'] == cid), k); U = useful(s, r, o, k)
            Pfs = dict(demonstrator=pw['demonstrator'], mission=jet/U['useful_share'] if U['useful_share'] > 0 else None)
            for pname, Pf in Pfs.items():
                if not Pf:
                    rows.append(dict(case=cid, bracket=bn, point=pname, status='INCONSISTENT', note='no useful energy')); continue
                for shield in (False, True):
                    B = budget(s, r, U, Pf, k, shield)
                    lo = B['brackets']['low']; ratio = 4*lo['reject_W']/A['drive_W']; ratio_hi = 4*B['brackets']['high']['reject_W']/A['drive_W']
                    zero = dict(r, photon_share=0.0); Bz = budget(s, zero, U, Pf, k, shield); non = Bz['brackets']['low']['reject_W']
                    per_ph = (lo['reject_W']-non)/(r['photon_share']*Pf) if r['photon_share'] > 0 else None
                    room = A['per_engine_W']-non
                    sr1 = room/(per_ph*Pf) if (per_ph and room > 0) else None
                    room_r = A['per_engine_W']-r['neutron_share']*Pf*NEUTRON_ABSORBED
                    sr1_r = room_r/(per_ph*Pf) if (per_ph and room_r > 0) else None
                    rows.append(dict(case=cid, bracket=bn, point=pname, shield=shield, Pf_W=Pf, ratio=ratio, ratio_high=ratio_hi,
                                     nonphoton_reject_W=non, nonphoton_ratio=4*non/A['drive_W'], heat_per_photon=per_ph, sr1_photon_share=sr1, sr1_radiation_only=sr1_r, gap_radiation_only=r['photon_share']/sr1_r if sr1_r else None,
                                     sr1_photon_only=A['per_engine_W']/(per_ph*Pf) if per_ph else None, neutron_alone_ratio=4*r['neutron_share']*Pf*NEUTRON_ABSORBED/A['drive_W'],
                                     sr1_status='FAIL_NONPHOTON' if room <= 0 else 'COMPUTED', photon_share=r['photon_share'],
                                     gap=r['photon_share']/sr1 if sr1 else None, energy_error=B['energy_error'], budget=B,
                                     status='CLOSES' if ratio <= 1 else 'FAIL'))
    return dict(allocation=A, power=pw, rows=rows, closing=[x for x in rows if x.get('status') == 'CLOSES'])


def classify(axis, v, T):
    for cls, test in T[axis]:
        if test(v):
            return cls
    return 'UNSUPPORTED'


def feasibility(s, C, G, I, tr=1.0):
    """7.3: closure over photon share x neutron share x photon deposition x charged leakage x cryogenic share x radiator capacity x power,
    each axis value classed by the evidence behind it; a combination takes its worst class, INCONSISTENT if it cannot deliver the canon
    directed efficiency at the mission point. Hot heat costs 1 W per W (the 1.5 convention, favourable), cryogenic heat cost(20 K)."""
    A = allocation(s); pw = power_points(s); k20 = cost(s, s['vertex_radiation']['cold_K']); eta = s['physics']['operating_point']['directed_efficiency']
    best = {bn: min((cs['brackets'][bn]['best']['photon_share'] for cid, cs in C.items() if cid != 'S0' and cs['brackets'][bn]['best']), default=1.0)
            for bn in BRACKETS}
    bestn = {bn: min((cs['brackets'][bn]['best']['neutron_share'] for cid, cs in C.items() if cid != 'S0' and cs['brackets'][bn]['best']), default=1.0)
             for bn in BRACKETS}
    rad = min((r['photon_share'] for cid, cs in C.items() if cid != 'S0' for r in cs['brackets']['nominal']['scan'] if r['mode'] == 'RADIATIVE' and r['sustained']), default=1.0)
    T = dict(photon=[('SUPPORTED', lambda v: v >= rad), ('PLAUSIBLE_EXTRAPOLATION', lambda v: v >= best['nominal']), ('SPECULATIVE_MOTIVATED', lambda v: v >= best['optimistic']*tr)],
             neutron=[('SUPPORTED', lambda v: v >= bestn['nominal']), ('PLAUSIBLE_EXTRAPOLATION', lambda v: v >= bestn['optimistic']),
                      ('SPECULATIVE_MOTIVATED', lambda v: v >= 0.5*bestn['optimistic'])],
             deposition=[('SUPPORTED', lambda v: v >= G['absorbed_low']), ('PLAUSIBLE_EXTRAPOLATION', lambda v: v >= G['coil_sky']*G['absorbed_low']/G['hardware_sky_mesh'])],
             leak=[('SUPPORTED', lambda v: v >= I['best_computed_leak']), ('SPECULATIVE_MOTIVATED', lambda v: v >= 0.01)],
             cryo=[('SUPPORTED', lambda v: v >= G['cold_share_low']), ('PLAUSIBLE_EXTRAPOLATION', lambda v: True)],
             capacity=[('SUPPORTED', lambda v: v <= 1.0), ('SPECULATIVE_MOTIVATED', lambda v: v <= 2.0)])
    ax = dict(photon=[0.3, 0.15, 0.1, 0.05, 0.02, 1e-2, 3e-3, 1e-3, 3e-4, 1e-4, 3e-5], neutron=[0.05, 0.02, 1e-2, 3e-3, 1e-3, 1e-4],
              deposition=[0.62, 0.2, 0.046, 0.01, 3e-3, 1e-3], leak=[0.5, 0.183, 0.05, 1e-2, 1e-3, 1e-4, 1e-5, 1e-6], cryo=[0.2, 0.05, 0.01, 0.0],
              capacity=[1.0, 2.0, 10.0])
    counts = {p: {cl: [0, 0] for cl in CLASSES} for p in pw}; slices = []; best_closing = {}
    order = {cl: i for i, cl in enumerate(CLASSES)}
    for pname, Pf in pw.items():
        for ph in ax['photon']:
            for nf in ax['neutron']:
                for dp in ax['deposition']:
                    for lk in ax['leak']:
                        for cr in ax['cryo']:
                            for cp in ax['capacity']:
                                heat = Pf*(ph*dp*(1-cr+cr*k20)+nf*0.87+(1-ph-nf)*lk)
                                ratio = 4*heat/(A['drive_W']*cp)
                                cls = max((classify('photon', ph, T), classify('neutron', nf, T), classify('deposition', dp, T), classify('leak', lk, T),
                                           classify('cryo', cr, T), classify('capacity', cp, T)), key=lambda x: order[x])
                                if pname == 'mission' and (1-ph-nf)*(1-lk) < eta:
                                    cls = 'INCONSISTENT'
                                counts[pname][cls][0] += 1
                                if ratio <= 1:
                                    counts[pname][cls][1] += 1
                                    if pname not in best_closing or order[cls] < order[best_closing[pname]['cls']]:
                                        best_closing[pname] = dict(cls=cls, photon=ph, neutron=nf, deposition=dp, leak=lk, cryo=cr, capacity=cp, ratio=ratio)
                                if nf in (1e-2, 1e-4) and lk in (0.183, 1e-2, 1e-4, 1e-6) and cr in (0.2, 0.0) and cp in (1.0, 10.0):
                                    slices.append([pname, ph, nf, dp, lk, cr, cp, ratio, cls])
    return dict(axes=ax, thresholds=dict(photon=best, photon_radiative=rad, neutron=bestn, deposition_supported=G['absorbed_low'],
                                         deposition_min=G['coil_sky']*G['absorbed_low']/G['hardware_sky_mesh'], leak_supported=I['best_computed_leak']),
                counts=counts, best_closing=best_closing, slices=slices, power=pw,
                note='closing counts per class: [combinations, closing]; a closing combination outside SUPPORTED / PLAUSIBLE_EXTRAPOLATION is a '
                     'requirement, not a design')


# ---------- G: neutrons, mission, sensitivity, fuels ------------------------------------------------------------------------------------

def neutrons(s, C):
    """Separate gate: per case at the mission point, neutron rate, nearest REBCO fluence over the four burns, the attenuation and wrap-shield
    thickness, mass and heat that a credible lifetime needs, the capture gammas, and the D-D suppression that alone would do it."""
    a = va.config(s); c = config(s); st = ve.stations(s); cs = vs.coils(s); b = op.burn(s); t_life = b['duration_s']*s['physics']['operating_point']['mission_burns']
    jet = b['peak_jet_power_W']/4; margin = s['physics']['departure_mass']['upper_kg']-op.mission(s)['departure_mass_kg']
    kn = cost(s, c['neutron_shield_K']); A = allocation(s); rows = []
    for cid, csr in C.items():
        r = csr['brackets']['nominal']['best']
        if not r or cid == 'S0':
            continue
        k = NOM; o = opts(s, next(x for x in c['cases'] if x['id'] == cid), k); U = useful(s, r, o, k)
        if U['useful_share'] <= 0:
            continue
        Pf = jet/U['useful_share']
        e_n = (r['neutron_share']*Pf)/MEV                                       # MeV/s
        dd = r['DD_share']*Pf/((vr.Q['DDn']+vr.Q['DDp'])/2*MEV)/2; dt = r['DT_share']*Pf/(vr.Q['DT']*MEV)
        nps = dd+dt
        coils = []; mass = 0.0; heat = 0.0
        for q in cs:
            d = math.hypot(q['x']-st['burn'], q['r'])-q['cryostat']; phi = nps/(4*math.pi*d*d)*math.exp(-a['intervening_m'][1]/a['removal_length_m'][1])
            need = phi*t_life/a['fluence_limit_n_m2'][1]
            t = a['shield_removal_length_m'][1]*math.log(max(need, 1.0))
            vol = 2*math.pi*q['r']*math.pi*((q['cryostat']+t)**2-q['cryostat']**2); m = vol*a['shield_density_kg_m3']
            sky = band(q['x']-st['burn'], q['r'], q['cryostat']+t)
            coils.append(dict(coil=q['name'], distance_m=d, flux_n_m2s=phi, life_unshielded_s=a['fluence_limit_n_m2'][1]/phi, attenuation_needed=need,
                              shield_m=t, shield_kg=m, shield_sky=sky))
            mass += m; heat += r['neutron_share']*Pf*sky+nps*sky*c['capture_gamma_MeV'][NOM]*MEV
        dd_need = min(1.0, min(x['life_unshielded_s'] for x in coils)/t_life)
        rows.append(dict(case=cid, Pf_W=Pf, neutrons_per_s=nps, dd_per_s=dd, dt_per_s=dt, neutron_W=e_n*MEV, mission_s=t_life, coils=coils,
                         shield_mass_four_kg=4*mass, shield_heat_W=heat, shield_reject_four_W=4*heat*kn, shield_ratio=4*heat*kn/A['drive_W'],
                         mass_margin_kg=margin, mass_ok=4*mass <= margin, source_factor_needed_unshielded=dd_need,
                         status='FAIL' if (4*mass > margin or 4*heat*kn > A['drive_W']) else 'BOUNDED'))
    return dict(rows=rows, limits=dict(fluence_n_m2=a['fluence_limit_n_m2'], evidence='LITERATURE_RANGE'), status='FAIL' if all(r['status'] == 'FAIL' for r in rows) else 'OPEN',
                note='Fluence limits, removal lengths and shield density are the 1.6A brackets (nominal used); no asserted conductor lifetime, '
                     'no nanomaterial immunity. Shield heat lands at 700 K and is lifted to the radiator.')


def mission(s, C, CB):
    """9: per promising case (nominal), at the mission's peak thrust (no pass by less thrust): fusion power, auxiliary and recirculating
    power, power-conditioning mass, fuel, and the added radiator that closing by area alone would need."""
    c = config(s); b = op.burn(s); q = s['physics']['operating_point']; jet = b['peak_jet_power_W']; A = allocation(s)
    per_m2 = A['installed_W']/s['radiators']['effective_area']['value'] if 'effective_area' in s['radiators'] else None
    margin = s['physics']['departure_mass']['upper_kg']-op.mission(s)['departure_mass_kg']; rows = []
    comb = {(r['case'], r['bracket'], r['point'], r.get('shield')): r for r in CB['rows']}
    for cid, csr in C.items():
        r = csr['brackets']['nominal']['best']
        if not r:
            continue
        o = opts(s, next(x for x in c['cases'] if x['id'] == cid), NOM); U = useful(s, r, o, NOM)
        if U['useful_share'] <= 0:
            rows.append(dict(case=cid, status='INCONSISTENT', note='no useful energy')); continue
        Pf = jet/U['useful_share']; fuel = Pf*b['duration_s']*q['mission_burns']/q['dhe3_specific_energy_J_kg']
        fuel_canon = b['reacted_dhe3_kg']*q['mission_burns']
        cb = comb.get((cid, 'nominal', 'mission', True)) or comb.get((cid, 'nominal', 'mission', False))
        excess = max(0.0, 4*cb['budget']['brackets']['low']['reject_W']-A['drive_W']) if cb else None
        area = excess/per_m2 if (excess is not None and per_m2) else None
        rows.append(dict(case=cid, useful_share=U['useful_share'], fusion_four_W=Pf, jet_W=jet, thrust_N=b['peak_thrust_N'], ve_m_s=b['exhaust_velocity_m_s'],
                         isp_s=b['exhaust_velocity_m_s']/9.80665, mdot_kg_s=b['peak_mass_flow_kg_s'], aux_W=r['aux_share']*Pf, wall_W=U['wall_share']*Pf,
                         power_mass_kg=U['wall_share']*Pf*c['power_specific_kg_W'][NOM], fuel_dhe3_kg=fuel, fuel_canon_kg=fuel_canon, burn_d=b['duration_d'],
                         radiator_added_m2=area, radiator_added_kg=area*c['radiator_kg_m2'][NOM] if area is not None else None, mass_margin_kg=margin,
                         status='FAIL' if (area and area > 0) or fuel-fuel_canon > margin or U['wall_share']*Pf*c['power_specific_kg_W'][NOM] > margin else 'PASS'))
    return dict(rows=rows, operating_point=dict(thrust_N=b['peak_thrust_N'], jet_W=jet, ve_m_s=b['exhaust_velocity_m_s'], duration_d=b['duration_d'],
                burns=q['mission_burns'], directed_efficiency=q['directed_efficiency'], max_absorbed_fraction=b['max_absorbed_fraction'], speed_c=0.016),
                note='Thrust, exhaust speed and burn time are held at the B01 operating point (0.016 c reference); a case with less useful energy '
                     'needs more fusion power for the same jet, and so more heat and fuel.')


def sensitivity(s, C, G, I, FE):
    """10: per parameter, current value, literature range, the value closure needs with every other axis at its most favourable class-
    PLAUSIBLE value at the mission point, the gap and the confidence."""
    A = allocation(s); Pf = power_points(s)['mission']; k20 = cost(s, s['vertex_radiation']['cold_K']); th = FE['thresholds']
    fav = dict(photon=th['photon']['optimistic'], neutron=th['neutron']['optimistic'], deposition=th['deposition_min'], leak=th['leak_supported'], cryo=0.0)
    def heat(ph, nf, dp, lk, cr):
        return Pf*(ph*dp*(1-cr+cr*k20)+nf*0.87+(1-ph-nf)*lk)
    Be = A['per_engine_W']
    def alone(axis):
        if axis == 'photon':
            return Be/(Pf*fav['deposition'])
        if axis == 'neutron':
            return Be/(Pf*0.87)
        if axis == 'deposition':
            return Be/(Pf*fav['photon'])
        if axis == 'leak':
            return Be/(Pf*(1-fav['photon']-fav['neutron']))
        return None
    def need(axis):
        v = dict(fav); v[axis] = 0.0; rest = heat(v['photon'], v['neutron'], v['deposition'], v['leak'], v['cryo'])
        if rest >= Be:
            return None
        if axis == 'photon':
            return (Be-rest)/(Pf*v['deposition']*(1-v['cryo']+v['cryo']*k20))
        if axis == 'neutron':
            return (Be-rest)/(Pf*0.87)
        if axis == 'deposition':
            return (Be-rest)/(Pf*v['photon']*(1-v['cryo']+v['cryo']*k20))
        if axis == 'leak':
            return (Be-rest)/(Pf*(1-v['photon']-v['neutron']))
        return None
    f = vf.config(s); c = config(s)
    rows = [dict(param='photon share', current=C['S0']['brackets']['nominal']['best']['photon_share'], best_defensible=th['photon']['nominal'],
                 literature='Maxwellian D-3He at 70-200 keV: tens of percent (Rider 1995; 1.5)', required=need('photon'),
                 mechanisms='hot ions, polarization, channeling, prompt escape (all below)', confidence='HIGH (physics of bremsstrahlung)'),
            dict(param='D-D (neutron) share', current=C['S0']['brackets']['nominal']['best']['neutron_share'], best_defensible=th['neutron']['nominal'],
                 literature=f'spin suppression of D-D disputed; factor {f["dd_factor"]}', required=need('neutron'),
                 mechanisms='D-lean mix, polarization (disputed), lower Ti', confidence='MEDIUM'),
            dict(param='photon deposition in hardware', current=G['absorbed_low'], best_defensible=th['deposition_min'],
                 literature='1.5 mesh: 62 % of the sky is hardware; the coils alone take ' f'{G["coil_sky"]:.1%}', required=need('deposition'),
                 mechanisms='open coils, standoff (field cost grows), thin low-Z structure', confidence='HIGH (geometry)'),
            dict(param='charged leakage to hardware', current=I['best_computed_leak'], best_defensible=I['best_computed_leak'],
                 literature='no fusion-product nozzle data; lab nozzles detach within metres', required=need('leak'),
                 mechanisms='closure topology, detachment', confidence='LOW (no model below 1e-2)'),
            dict(param='polarization P_D P_He survival', current=0.0, best_defensible=f['polarization'][NOM]*f['polarization_survival'][NOM],
                 literature='enhancement 1 + P^2/2 (Kulsrud 1982); more under optimistic 2025 analyses', required=None,
                 mechanisms='raises fusion at the same electron heating; at most x1.5', confidence='MEDIUM'),
            dict(param='channeling share', current=0.0, best_defensible=c['channel_share'][NOM], literature='17-66 % theory, no burning-plasma test',
                 required=None, mechanisms='waves need a magnetized, low-density plasma', confidence='LOW'),
            dict(param='radiator capacity', current=1.0, best_defensible=1.0, literature='canon 14.4 GW installed, 75 % to the drive',
                 required=None, mechanisms='only by changing the ship (not permitted)', confidence='HIGH')]
    for r, ax in zip(rows, ('photon', 'neutron', 'deposition', 'leak', None, None, None)):
        r['required_alone'] = alone(ax) if ax else None
        r['gap_alone'] = r['best_defensible']/r['required_alone'] if r['required_alone'] else None
        if r['required'] is not None and r['best_defensible']:
            r['gap'] = r['best_defensible']/r['required'] if r['required'] > 0 else math.inf
        else:
            r['gap'] = None
    return dict(favourable=fav, rows=rows, Pf_W=Pf,
                note='required: the value that closes the drive allocation at the mission point with every other axis at its most favourable value '
                     'that is still PLAUSIBLE_EXTRAPOLATION or better; None when the other axes alone already exceed the allocation')


def fuels(s, C):
    """11 (limited): D-T and D-3He from the same balance engine (Maxwellian, Te = Ti and the sustained floor), p-11B and 3He-3He from the
    literature. D-3He stays the working fuel."""
    rows = []
    for T in (20.0, 50.0, 100.0):
        nD = nT = 0.5e20; ne = 1e20
        pf = nD*nT*vr.sigma_v('DT', T)*vr.Q['DT']*MEV; pb = vr.brems_W_m3(ne, T, 1.0)
        rows.append(dict(T_keV=T, photon_over_fusion=pb/pf))
    dt = min(rows, key=lambda r: r['photon_over_fusion'])
    d3 = C['S0-SC']['brackets']['nominal']['best']
    return [dict(fuel='D-T', charged_share=3.52/17.59, neutron_share=14.07/17.59, photon_over_fusion=dt['photon_over_fusion'], T_keV=dt['T_keV'],
                 evidence='ANALYTIC (Bosch-Hale)', availability='tritium bred from lithium; no natural stock', shield='heaviest: 80 % of the energy in 14 MeV neutrons',
                 note='lowest temperature and highest reactivity; the neutron load fails the coil and shield gates at once'),
            dict(fuel='D-3He', charged_share=d3['charged_share'], neutron_share=d3['neutron_share'], photon_over_fusion=d3['photon_share'], T_keV=d3['Ti_keV'],
                 evidence='THIS STUDY (S0-SC)', availability='He-3 scarce (lunar regolith, gas giants)', shield='D-D side reactions and bred tritium',
                 note='the working fuel (canon)'),
            dict(fuel='p-11B', charged_share=0.998, neutron_share=0.002, photon_over_fusion=None, T_keV=None, evidence='LITERATURE',
                 availability='abundant', shield='light (side reactions)',
                 note='bremsstrahlung comparable to fusion at the 250-400 keV optimum; marginal even in updated analyses (Putvinski 2019; 2024-2026 '
                      're-assessments); no closed balance computed here'),
            dict(fuel='3He-3He', charged_share=1.0, neutron_share=0.0, photon_over_fusion=None, T_keV=None, evidence='LITERATURE',
                 availability='He-3 scarce', shield='none',
                 note='aneutronic but its reactivity is orders of magnitude below D-3He; not a burn candidate at any accessible temperature')]


# ---------- gates, verdict, answers ---------------------------------------------------------------------------------------------------

def gates(s, L, V, C, NE, I, CB, FE, N, MI):
    closing_ok = [x for x in CB['rows'] if x.get('status') == 'CLOSES' and x['point'] == 'mission']
    fe_m = FE['best_closing'].get('mission'); fe_cls = fe_m['cls'] if fe_m else None
    bestS = min((cs['brackets']['nominal']['best']['photon_share'] for cid, cs in C.items() if cid != 'S0' and cs['brackets']['nominal']['best']))
    bestO = min((cs['brackets']['optimistic']['best']['photon_share'] for cid, cs in C.items() if cid != 'S0' and cs['brackets']['optimistic']['best']))
    G = [dict(id='R16B-0', name='Baseline reproduction', status='PASS' if L['all_reproduced'] else 'FAIL', note='1.5 F0, 1.6, 1.6A and EXT-01 ledger'),
         dict(id='R16B-1', name='Source physics', status='PASS_WITH_LIMITS' if V['all_pass'] else 'FAIL',
              note='reactivity extension validated; D-3He above 190 keV bracketed; synchrotron and impurities added; trapping unresolved'),
         dict(id='R16B-2', name='Advanced mechanisms', status='FAIL', note=f'best defensible photon share {bestS:.1%}, optimistic {bestO:.1%}; SR-1 needs orders less'),
         dict(id='R16B-3', name='Interface', status='FAIL', note=f'computed leakage {I["best_computed_leak"]:.1%} vs allowed 1e-4..1e-7 per class'),
         dict(id='R16B-4', name='Transport', status='OPEN', note='photon transport (Compton trapping, Comptonization) and charged detachment need 2D / radiation-hydro models'),
         dict(id='R16B-5', name='Thermal closure', status='PASS' if closing_ok else 'FAIL', note=f'{len(closing_ok)} case rows close at the mission point; '
              f'feasibility map best closing class: {fe_cls}'),
         dict(id='R16B-6', name='Neutron survival', status=N['status'], note='shield mass / heat against the departure margin and the drive allocation'),
         dict(id='R16B-7', name='Propulsion and mission', status='PASS' if any(r.get('status') == 'PASS' for r in MI['rows']) else 'FAIL',
              note='held at the B01 thrust and exhaust speed'),
         dict(id='R16B-8', name='Architecture preservation', status='PASS' if (s['propulsion_cluster']['engine_count'] == 4 and
              s['propulsion_representation']['active'] == 'VERTEX_CLUSTER') else 'FAIL', note='four engines, D-3He, Fiji one property, no single core, no pusher plate'),
         dict(id='R16B-9', name='Verdict', status=verdict(C, I, CB, FE)['outcome'], note=verdict(C, I, CB, FE)['label'])]
    return G


def verdict(C, I, CB, FE):
    fe = FE['best_closing'].get('mission')
    good = fe and fe['cls'] in ('SUPPORTED', 'PLAUSIBLE_EXTRAPOLATION')
    spec = fe and fe['cls'] == 'SPECULATIVE_MOTIVATED'
    if good:
        return dict(outcome='A', label='PHYSICALLY_SUPPORTED_PATH')
    if spec:
        return dict(outcome='B', label='SPECULATIVE_BUT_BOUNDED')
    return dict(outcome='C', label='SOURCE_AND_INTERFACE_BLOCKED',
                next='radiation-hydrodynamic transport of the dense target (Compton trapping and Comptonization) is the single calculation that could '
                     'move the source by more than a factor of a few; it cannot close the interface gap, which needs a nozzle closure 4-6 orders tighter '
                     'than any computed or measured')


def ledger(s):
    """2: the four earlier results with the assumptions that make them different measurements; F0 recomputed from the 1.5 map."""
    R5 = vf.r15(); F = json.loads(vf.EVIDENCE_PATH.read_text()); A = json.loads(va.EVIDENCE_PATH.read_text()); x = config(s)['ext01_quote']
    F0 = vf.closure(s, 'F0', 1.0, 1.0)['ratio'][0]; v = {r['id']: r for r in F['variants']}
    exr = [e['brackets']['low']['ratio'] for e in A['exposure'].values()]
    rows = [dict(id='1.5 F0', ratio=R5['thermal']['cases']['LOW']['RADIATION_low']['ratio'], recomputed=F0,
                 configuration='four M0-NOMINAL engines as drawn', source='R2-A LOW: Ti 110 keV, Te/Ti 0.5 prescribed, photons 12.5 %',
                 geometry='real-mesh ray trace (hardware 62 % of the sky)', thermal='Compton-only deposition; coils and cryo lines at 20 K, the rest hot (1800 K, cost 1)',
                 capacity='whole 14.4 GW'),
            dict(id='1.6 F6', ratio=v['F6']['ratio'][0] if isinstance(v['F6'].get('ratio'), list) else v['F6'].get('ratio'), recomputed=None,
                 configuration='Fiji liner + every lever (polarization, channeling, nanomaterial radiator, liner hysteresis)', source='levers on the 1.5 LOW source',
                 geometry='1.5 map with a 1000 K Fiji liner moving cold heat', thermal='heat pump from the liner temperature', capacity='14.4 GW, emissivity raised'),
            dict(id='1.6 F1-REF (W liner)', ratio=v['F1-REF']['ratio'][0] if isinstance(v['F1-REF'].get('ratio'), list) else v['F1-REF'].get('ratio'), recomputed=None,
                 configuration='plain tungsten liner at 1300 K', source='1.5 LOW', geometry='1.5 map', thermal='liner to radiator by heat pump', capacity='14.4 GW'),
            dict(id='1.6A FG matrix', ratio=[min(exr), max(exr)], recomputed=None, configuration='Fiji geometries FG-0..FG-5 in sight of the burn',
                 source='1.5 LOW', geometry='ray screen of the Fiji volumes added to the hardware', thermal='Fiji at 1000 K absorbs its sky fully', capacity='14.4 GW'),
            dict(id='EXT-01', ratio=x['plate_min_ratio'], recomputed=None, configuration='external pulse (plate / magnetic / remote), comparison only',
                 source='isotropic bare pulse', geometry='analytic', thermal='plate ablation or magnetic reflection', capacity='14.4 GW',
                 note=f'{x["cases"]:,} cases, {x["verdict"]}; {x["magnetic_closing_cases"]} magnetic cases close only with a directed pulse and leak <= {x["tolerable_leak"]:.0e}')]
    ok = abs(F0/R5['thermal']['cases']['LOW']['RADIATION_low']['ratio']-1) < 1e-6 and F['input_hash'] == vf.input_hash(s) and A['input_hash'] == va.input_hash(s)
    return dict(rows=rows, all_reproduced=ok, hashes=dict(r15=R5['input_hash'], r16=F['input_hash'], r16a=A['input_hash']),
                note='The ratios answer different questions (source, geometry, thermal convention, capacity); they are not a sequence of improvements.')


def answers(s, C, FA, NE, G, I, CB, FE, N, MI, SE):
    nm = lambda cid: C[cid]['brackets']['nominal']['best']
    bestS = min(((cid, nm(cid)['photon_share']) for cid in C if cid != 'S0' and nm(cid)), key=lambda x: x[1])
    bestO = min(((cid, C[cid]['brackets']['optimistic']['best']['photon_share']) for cid in C if cid != 'S0' and C[cid]['brackets']['optimistic']['best']), key=lambda x: x[1])
    sr = [r for r in CB['rows'] if r.get('point') == 'mission' and r.get('bracket') == 'optimistic' and r.get('shield')]
    sr_best = max((r['sr1_photon_only'] or 0.0 for r in sr), default=0.0); n_alone = min((r['neutron_alone_ratio'] for r in sr), default=0.0)
    allow = {a['cls']: a['mission']['allowed_share'] for a in I['allowable']}
    v = verdict(C, I, CB, FE)
    return [dict(q=1, question='Photon radiation under the best defensible models', answer=f'{bestS[1]:.1%} of fusion power ({bestS[0]}, nominal); optimistic bound '
                 f'{bestO[1]:.1%} ({bestO[0]}). 1.6\'s 16.4 % floor was {FA["factor"]:.2f}x too high (electron count); the corrected same-lever floor is '
                 f'{FA["composition_fixed"]:.1%}. Compton trapping could lower the dense target by at most {1/NE["trapping"]["photon_kept_lower"]:.1f}x (unresolved sign).'),
            dict(q=2, question='How much may strike the ship', answer=f'With every other load at zero, the drive share ({allocation(s)["drive_W"]/1e9:.1f} GW, 2.7 GW per engine) '
                 f'allows {I["allowable"][0]["mission"]["allowed_W"]/1e9:.1f} GW per engine at hot structure; at the mission point that is '
                 f'{allow["HOT_STRUCTURE"]:.1e} of the charged stream, Neutrons alone already put {n_alone:,.0f}x the drive share into the hardware in the best case, so no photon share fits; with neutrons, leakage and '
                 f'losses all at zero, photons could be at most {sr_best:.1e} of fusion power (SR-1, mission point, cold parts shaded).'),
            dict(q=3, question='Tolerable charged leakage', answer=f'hot structure {allow["HOT_STRUCTURE"]:.1e}, armour {allow["RADIATION_FACING_ARMOUR"]:.1e}, warm machinery '
                 f'{allow["WARM_MACHINERY"]:.1e}, cryogenic {allow["CRYOGENIC_SUPERCONDUCTOR"]:.1e} of the charged power (mission point); Engine 1.4 computed '
                 f'{I["best_computed_leak"]:.1%} at best.'),
            dict(q=4, question='Can polarization and non-equilibrium close the gap', answer='No. Polarization gives at most 1.5x fusion at the same electron heating; '
                 'hot-ion and prompt-escape states trade photons for auxiliary heating (Rider); together they move the photon share by a factor of a few '
                 'against a gap of orders of magnitude.'),
            dict(q=5, question='What limits directed exhaust energy', answer='Photons (10-60 % of fusion) and capture: Engine 1.4\'s best closure sends 82 % of the '
                 'charged energy aft; the canon 0.8 directed efficiency needs photons + neutrons + leakage below 20 % together.'),
            dict(q=6, question='Are the coils survivable', answer=N['note'] + ' ' + '; '.join(f'{r["case"]}: shield {r["shield_mass_four_kg"]/1e3:,.0f} t vs margin '
                 f'{r["mass_margin_kg"]/1e3:,.0f} t, {r["status"]}' for r in N['rows'][:3])),
            dict(q=7, question='What closes the radiator budget', answer='Nothing defensible. The feasibility map\'s best mission closure needs '
                 + (f'photons {FE["best_closing"]["mission"]["photon"]:.0e}, deposition {FE["best_closing"]["mission"]["deposition"]:.0e}, leakage '
                    f'{FE["best_closing"]["mission"]["leak"]:.0e} ({FE["best_closing"]["mission"]["cls"]})' if FE['best_closing'].get('mission') else 'values outside every grid point')),
            dict(q=8, question='Fundamental constraints vs engineering challenges', answer='Fundamental: bremsstrahlung of a D-3He burn hot enough to burn '
                 '(tens of percent), the magnet sky, D-D neutrons. Engineering: leakage, shielding mass, cold-part shading, power conversion.'),
            dict(q=9, question='Is the four-engine architecture worth developing', answer='As a representation, yes (it is canon and unchanged); as a radiation '
                 'and thermal design, not with this source: the gap is in the source and the interface, not in the number of engines.'),
            dict(q=10, question='The next milestone', answer=v.get('next', '') or 'a mission-level review of the power level (the photon budget scales with fusion power)')]


def input_hash(s):
    blob = json.dumps([s['vertex_source'], s['vertex_fiji_a'], s['vertex_fiji'], s['vertex_radiation'], s['physics']['operating_point'],
                       s['radiators']['temperature']], sort_keys=True, default=str)
    here = Path(__file__).resolve().parent
    src = b''.join((here/f).read_bytes() for f in ('vertex_source.py', 'vertex_radiation.py', 'vertex_fiji.py', 'operating_point.py'))
    return hashlib.sha256(blob.encode()+src+vf.EVIDENCE_PATH.read_bytes()+vr.EVIDENCE_PATH.read_bytes()+va.EVIDENCE_PATH.read_bytes()
                          +vp.EVIDENCE_PATH.read_bytes()).hexdigest()[:16]


def report(s):
    t0 = time.time(); c = config(s)
    L = ledger(s); V = validation(s); C = cases(s); FA = floor_audit(s, C); NE = nonequilibrium(s, C); G = geometry(s); I = interface(s, C, G)
    CB = combined(s, C)
    FE = feasibility(s, C, G, I, NE['trapping']['photon_kept_lower'])
    N = neutrons(s, C); MI = mission(s, C, CB); SE = sensitivity(s, C, G, I, FE); FU = fuels(s, C)
    GT = gates(s, L, V, C, NE, I, CB, FE, N, MI); VD = verdict(C, I, CB, FE)
    for r in CB['rows']:
        r.pop('budget', None) if r.get('point') == 'demonstrator' else None
    return dict(version=c['version'], input_hash=input_hash(s), evidence=c['evidence'], baseline_commit=c['baseline_commit'], ledger=L, validation=V,
                cases=C, floor_audit=FA, nonequilibrium=NE, geometry=G, interface=I, allocation=allocation(s), combined=CB, feasibility=FE, neutrons=N,
                mission=MI, sensitivity=SE, fuels=FU, gates=GT, verdict=VD, answers=answers(s, C, FA, NE, G, I, CB, FE, N, MI, SE),
                rec=[dict(id='REC-1', decision='APPROVED FOR VERTEX RESEARCH', action='research direction only; Drive rows not applied'),
                     dict(id='REC-2', decision='HOLD', action='unchanged'), dict(id='REC-3', decision='PRESERVE UNCHANGED', action='unchanged'),
                     dict(id='REC-4', decision='APPROVED AS A RESEARCH PRINCIPLE', action='research direction only; Drive rows not applied'),
                     dict(id='REC-5', decision='RECORD AS OPEN ENGINEERING FINDING', action='open finding')],
                outcome=VD['outcome'], cost=dict(seconds=time.time()-t0))


def compact(x):
    """Six significant digits in the evidence file (the values are reduced-model results, not measurements)."""
    if isinstance(x, float):
        return x if not math.isfinite(x) or x == 0 else float(f'{x:.6g}')
    if isinstance(x, dict):
        return {k: compact(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [compact(v) for v in x]
    return x


def evidence(s, path=EVIDENCE_PATH):
    R = report(s)
    path.write_text(json.dumps(compact(R), indent=None, separators=(',', ':'), default=lambda x: None if x is None else float(x))+'\n')
    return R


if __name__ == '__main__':
    import spec
    S = spec.load(ROOT)[0]
    R = evidence(S) if '--evidence' in sys.argv else report(S)
    for v in R['validation']['rows']:
        print(f"{'ok ' if v['passes'] else 'inf' if v['passes'] is None else 'BAD'} {v['rel_error']:+.2e}  {v['case']}")
    for cid, cs in R['cases'].items():
        print(cid, '  '.join(f"{bn[:3]} {b['best']['photon_share']:.2%} n {b['best']['neutron_share']:.2%} Ti {b['best']['Ti_keV']:g} Te {b['best']['Te_keV']:.0f} "
                             f"aux {b['best']['aux_share']:.2f} U {b['best']['useful_share']:.2f} {b['best']['mode'][:3]}" if b['best'] else f'{bn[:3]} none' for bn, b in cs['brackets'].items()))
    print('floor audit', R['floor_audit'])
    for g in R['gates']:
        print(f"{g['id']:8} {g['status']:18} {g['name']}: {g['note']}")
    print(R['feasibility']['counts']['mission'], R['feasibility']['best_closing'])
    print(f"{R['cost']['seconds']:.1f} s")
