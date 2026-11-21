"""Accelerator-driven selective D-3He fusion (ASF): first-order analytical study.

Research only (owner brief 2026-11-21). Reads the canon numbers it compares against from data/wayfarer_3d.toml and the shared physics in
src/wayfarer/vertex_radiation.py; writes results/asf.json. Changes no canon. Standard library only:

    python3 work/accelerator-fusion/asf.py

Every efficiency below is a declared HYPOTHESIS per maturity level, never a result. The physics (cross sections, Coulomb logarithm,
slowing down, bremsstrahlung) is textbook; the outputs are screening numbers, not a design.
"""
import json
import math
import random
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'/'wayfarer'))
import vertex_radiation as vr  # noqa: E402
import vertex_source as vs  # noqa: E402

OUT = Path(__file__).resolve().parent/'results'/'asf.json'
KEV = vr.KEV; MEV = vr.MEV; AMU = vr.AMU
E_CH = 1.602176634e-19; EPS0 = 8.8541878128e-12; ME = 9.1093837015e-31; KB = 1.380649e-23; HBAR = 1.054571817e-34; C = 2.99792458e8
mD, mHe3 = vr.M_ION['D']*AMU, vr.M_ION['He3']*AMU
MU_DHE3 = mD*mHe3/(mD+mHe3)
Y = vr.Q['DHe3']*MEV                      # 18.353 MeV per D-3He reaction, all charged (p 14.68, alpha 3.67)
COULOMB_MEV_FM = 1.439964                # e^2 / (4 pi eps0)

# ---------- canon -------------------------------------------------------------------------------------------------------------------

def canon():
    s = tomllib.loads((ROOT/'data'/'wayfarer_3d.toml').read_text())
    op = s['physics']['operating_point']
    body = s['ship']['length']['value']
    lance = s['forward_defense']['dust_lance']['length']['value'] if isinstance(s['forward_defense']['dust_lance'].get('length'), dict) else 12.0
    return dict(
        ship_body_m=body, ship_overall_m=body+lance, cluster_hardware_length_m=323.2, ship_max_m=s['ship']['length']['max'],
        engine_envelope=dict(length_m=31.9, radius_m=11.44, volume_m3=math.pi*11.44**2*31.9),
        engines=4,
        fusion_per_engine_W=65.3e12, fusion_total_W=4*65.3e12,          # docs/FUEL_SYSTEM.md 10.3 (ship operating point)
        jet_total_W=209e12, thrust_total_N=4*21.8e6,                      # docs/FUEL_SYSTEM.md 3
        exhaust_velocity_m_s=op['exhaust_velocity_m_s'], directed_efficiency=op['directed_efficiency'],
        absorbed_fraction=op['absorbed_fraction'], hot_share=op['hot_share'], burnup=op['burnup'], recovery=op['recovery'],
        hot_radiator_W=14.4e9,                                             # 1800 K hot blades (MODEL.md, B01 note)
        exhaust_per_reacted=1.53,                                          # FUEL_SYSTEM.md 10.3
        fuel_t=dict(D=731, He3=1094, H2=972),
        vertex_reference=dict(photon_share_best=0.10, photon_share_floor_1_6=0.126, real_mesh_intercept=0.62,
                              coil_sky_share=0.37, neutron_share_canon=0.01,
                              note='Vertex 1.5/1.6B (lab and references/evidence): best defensible photon share 10 %, 62 % intercepted; '
                                   'B01 absorbed 4e-5 is a requirement, not a property'))

# ---------- cross sections ----------------------------------------------------------------------------------------------------------
# Bosch & Hale (1992) Table IV, D-3He: B_G 68.7508, S = (A1 + E(A2 + E(A3 + E(A4 + E A5)))) / (1 + E(B1 + E(B2 + E(B3 + E B4)))) keV mb,
# valid 0.3-900 keV centre-of-mass. D-D branches from vertex_source.BH_XS (validated there).
BH_DHE3 = (68.7508, (5.7501e6, 2.5226e3, 4.5566e1, 0.0, 0.0), (-3.1995e-3, -8.5530e-6, 5.9014e-8, 0.0))


def sigma(r, E_keV):
    """Cross section (m^2) at centre-of-mass energy E (keV). Above 900 keV D-3He is held (documented extrapolation)."""
    if E_keV <= 0.3:
        return 0.0
    if r == 'DHe3':
        BG, A, B = BH_DHE3; E = min(E_keV, 900.0)
        S = (A[0]+E*(A[1]+E*(A[2]+E*(A[3]+E*A[4]))))/(1.0+E*(B[0]+E*(B[1]+E*(B[2]+E*B[3]))))
        return S/(E*math.exp(BG/math.sqrt(E)))*1e-31
    if r == 'DD':
        return vs.sigma_xs('DDn', min(E_keV, 3000.0))+vs.sigma_xs('DDp', min(E_keV, 3000.0))
    return vs.sigma_xs(r, E_keV)


def maxwell_sv(r, T, n=3000):
    mu = MU_DHE3 if r == 'DHe3' else mD/2
    Emax = max(60*T, 2000.0); h = Emax/n
    tot = sum(sigma(r, (i+0.5)*h)*(i+0.5)*h*math.exp(-(i+0.5)*h/T) for i in range(n))*h*KEV*KEV
    return math.sqrt(8/(math.pi*mu))*(T*KEV)**-1.5*tot


def validation():
    rows = []
    for T in (10.0, 30.0, 50.0, 100.0):
        a, b = maxwell_sv('DHe3', T), vr.sigma_v('DHe3', T)
        rows.append(dict(case=f'D-3He cross-section integral vs Bosch-Hale reactivity, {T:g} keV', ratio=a/b, passes=abs(a/b-1) < 0.03))
    Es = [5*i for i in range(1, 181)]
    pk = max(Es, key=lambda E: sigma('DHe3', E))
    rows.append(dict(case='D-3He peak (textbook ~0.7-0.9 b near 250-450 keV c.m.)', E_keV=pk, barn=sigma('DHe3', pk)*1e28))
    return rows

# ---------- 1. kinematics: what makes a collision energetic --------------------------------------------------------------------------

def kinematics(Ecm_keV):
    """Lab energy a D and a 3He beam must carry to meet at Ecm, by geometry. Ecm = 1/2 mu v_rel^2."""
    vrel = math.sqrt(2*Ecm_keV*KEV/MU_DHE3)
    rows = []
    # head-on at zero total momentum (lab = c.m.): the cheapest possible
    vD = vrel*mHe3/(mD+mHe3); vH = vrel*mD/(mD+mHe3)
    E0 = 0.5*mD*vD**2+0.5*mHe3*vH**2
    rows.append(dict(arrangement='head-on, zero net momentum (lab = c.m.)', E_lab_keV=E0/KEV, cm_drift_m_s=0.0, ratio_to_min=1.0))
    # beam into a stationary target: D moving
    E1 = 0.5*mD*vrel**2
    rows.append(dict(arrangement='D beam into resting 3He (beam-target)', E_lab_keV=E1/KEV, cm_drift_m_s=vrel*mD/(mD+mHe3), ratio_to_min=E1/E0))
    # angled beams of equal speed, crossing angle theta
    for th in (90.0, 30.0, 10.0):
        t = math.radians(th)
        # equal speeds v: v_rel = 2 v sin(t/2)
        v = vrel/(2*math.sin(t/2)); E = 0.5*(mD+mHe3)*v*v
        rows.append(dict(arrangement=f'crossing at {th:g} deg, equal speeds', E_lab_keV=E/KEV, cm_drift_m_s=v*math.cos(t/2), ratio_to_min=E/E0))
    # co-propagating: both forward, relative speed vrel, slower one at u
    for u in (1e6, 5e6, 2e7):
        E = 0.5*mD*(u+vrel)**2+0.5*mHe3*u**2
        rows.append(dict(arrangement=f'co-propagating, 3He at {u/1e6:g} Mm/s, D faster by v_rel', E_lab_keV=E/KEV,
                         cm_drift_m_s=(mD*(u+vrel)+mHe3*u)/(mD+mHe3), ratio_to_min=E/E0))
    return dict(Ecm_keV=Ecm_keV, v_rel_m_s=vrel, rows=rows,
                note='Only the relative velocity fuses; a common drift is kinetic energy carried by both beams that the collision cannot use '
                     '(it must be recovered). Co-propagating beams pay the drift twice: in the accelerator and in the recovery.')

# ---------- 2. fusion versus Coulomb scattering -------------------------------------------------------------------------------------

def coulomb_ratio(Ecm_keV, lnL=20.0):
    """Momentum-transfer (thermalising) Coulomb cross section 4 pi b0^2 lnL with b0 = Z1 Z2 e^2 / (4 pi eps0 * 2 Ecm), against fusion."""
    b0 = 2*COULOMB_MEV_FM/(2*Ecm_keV/1e3)*1e-15
    s_c = 4*math.pi*b0*b0*lnL
    s_f = sigma('DHe3', Ecm_keV)
    return dict(Ecm_keV=Ecm_keV, b0_fm=b0*1e15, sigma_coulomb_b=s_c*1e28, sigma_fusion_b=s_f*1e28, ratio=s_c/s_f,
                recirc_per_fusion=(s_c/s_f)*Ecm_keV*KEV/Y)

# ---------- 3. non-neutral colliding beams (no electrons in the burn) ----------------------------------------------------------------

def non_neutral(B_T=(10.0, 20.0, 40.0), Ecm_keV=400.0, P_W=65.3e12, V_engine=13115.0):
    rows = []
    vrel = math.sqrt(2*Ecm_keV*KEV/MU_DHE3)
    for B in B_T:
        # Brillouin limit for the combined beam column, mass density rho <= eps0 B^2 / 2 per unit (q/m)... per species: n <= eps0 B^2 / (2 m)
        nD = EPS0*B*B/(2*mD); nH = EPS0*B*B/(2*mHe3)*0.25      # 3He2+: q^2 enters, so n_He3 <= eps0 B^2 / (2 m) / Z^2 for equal space charge share
        n1, n2 = nD/2, nH/2                                    # share the column's space charge between the two species
        p = n1*n2*sigma('DHe3', Ecm_keV)*vrel*Y
        rows.append(dict(B_T=B, n_D_m3=n1, n_He3_m3=n2, power_density_W_m3=p, volume_per_engine_m3=P_W/p, engine_volumes=P_W/p/V_engine))
    return dict(Ecm_keV=Ecm_keV, rows=rows,
                note='Pure-ion beams are limited by their own space charge (Brillouin density). Neutralising them admits electrons, which bring '
                     'bremsstrahlung and electron drag: the burn becomes a beam-plasma system (section 4).')

# ---------- 4. beam-target: D beam slowing in a 3He-rich plasma -------------------------------------------------------------------

def slowing(E0_keV, Te_keV, ne=1e21, Ti_keV=None, nfD_frac=0.0, steps=1500):
    """D beam slowing on electrons and ions of a 3He plasma (Stix): dE/dt = -(2E/tau_s)(1 + (Ec/E)^1.5).
    Returns burn-up probability P, energy gain F = Y P / E0, slowing time, the energy-weighted residence density f(E) and <sigma v>_sd."""
    if Ti_keV is None:
        Ti_keV = Te_keV
    nHe = ne/(2+nfD_frac); nfD = nfD_frac*nHe
    lnL = vr.lnlambda(ne, Te_keV)
    tau_s = 6.27e8*2.0*(Te_keV*1e3)**1.5/(ne*1e-6*lnL)     # s; A_b = 2, Z_b = 1
    ions = [(nHe, 2, 3.016)]+([(nfD, 1, 2.014)] if nfD > 0 else [])
    Ec = 14.8*2.0*Te_keV*(sum(n*Z*Z/A for n, Z, A in ions)/ne)**(2/3)
    Eend = max(1.5*Ti_keV, 1.0)
    if E0_keV <= Eend:
        return None
    # log grid in energy
    P = 0.0; T = 0.0; shells = []
    lo, hi = math.log(Eend), math.log(E0_keV); h = (hi-lo)/steps
    for i in range(steps):
        E = math.exp(lo+(i+0.5)*h); dE = E*h
        rate = (2*E/tau_s)*(1+(Ec/E)**1.5)              # keV/s
        dt = dE/rate
        v = math.sqrt(2*E*KEV/mD)
        Ecm = E*mHe3/(mD+mHe3)
        dP = nHe*sigma('DHe3', Ecm)*v*dt
        P += dP; T += dt; shells.append((E, dt))
    P = 1-math.exp(-P)
    F = Y*P/(E0_keV*KEV)
    sv_sd = P/(nHe*T)          # mean D-3He reactivity of a fast D over its life
    ion_share = vr.ion_share(E0_keV, Te_keV, 2.014, ions)
    return dict(E0_keV=E0_keV, Te_keV=Te_keV, Ti_keV=Ti_keV, Ec_keV=Ec, tau_s_s=tau_s, life_s=T, P=P, F=F, sv_sd=sv_sd, ne=ne, nHe=nHe,
                nfD=nfD, ion_share=ion_share, shells=shells)


def dd_fast_fast(sd, collimated, n=4000, seed=7):
    """<sigma v> for D-D between two fast D drawn from the slowing-down residence distribution (weight dt per shell).
    collimated: same direction (relative speed from the energy spread only); else isotropic directions (pitch-angle scattered)."""
    rnd = random.Random(seed)
    Es = [e for e, _ in sd['shells']]; ws = [w for _, w in sd['shells']]
    cum = []; t = 0.0
    for w in ws:
        t += w; cum.append(t)
    def draw():
        x = rnd.random()*t
        lo, hi = 0, len(cum)-1
        while lo < hi:
            m = (lo+hi)//2
            if cum[m] < x: lo = m+1
            else: hi = m
        return Es[lo]
    acc = 0.0
    for _ in range(n):
        E1, E2 = draw(), draw()
        v1, v2 = math.sqrt(2*E1*KEV/mD), math.sqrt(2*E2*KEV/mD)
        c = 1.0 if collimated else rnd.uniform(-1, 1)
        vr2 = v1*v1+v2*v2-2*v1*v2*c
        Ecm = 0.25*mD*vr2/KEV
        acc += sigma('DD', Ecm)*math.sqrt(vr2)
    return acc/n


def selectivity(sd, nfD_frac, thermal_res_ratio):
    """Reaction shares in a beam-target burn: fast D on 3He (wanted), fast-fast D-D (collimated / isotropic), and thermalised D
    (residence thermal_res_ratio x the fast life) reacting with D and 3He at Ti. Neutron power share counts the D-D n branch (2.45 MeV)
    and burns 1.01 MeV tritons at the same beam-target probability bracket (secondary D-T, 14.07 MeV)."""
    nHe = sd['nHe']; nfD = nfD_frac*nHe
    Ti = sd['Ti_keV']
    nth = nfD*thermal_res_ratio
    r_dhe = nfD*nHe*sd['sv_sd']+nth*nHe*vr.sigma_v('DHe3', Ti)
    out = {}
    for tag, col in (('collimated', True), ('isotropic', False)):
        svff = dd_fast_fast(sd, col)
        r_dd = 0.5*nfD*nfD*svff+nfD*nth*vs.sv_xs('DDn', max(Ti, 1.0))*2+0.5*nth*nth*(vr.sigma_v('DDn', Ti)+vr.sigma_v('DDp', Ti))
        # neutron power: half of D-D are n-branch (2.45 MeV); tritons (half) burn with probability ~1e-2..5e-2 (bracket 3e-2) into 14.07 MeV n
        pt = 0.03
        Pn = r_dd*0.5*2.45*MEV+r_dd*0.5*pt*14.07*MEV
        Pf = r_dhe*Y+r_dd*(0.5*3.27+0.5*4.03)*MEV
        out[tag] = dict(dd_per_dhe3=r_dd/r_dhe, neutron_power_share=Pn/Pf)
    return out


def brems_share(sd, nfD_frac):
    """Bremsstrahlung / fusion power in a steady beam-target burn: both scale as n^2, so the ratio depends only on Te, the beam fraction
    and the beam's lifetime reactivity."""
    nHe = sd['nHe']; nfD = nfD_frac*nHe; ne = 2*nHe+nfD
    zeff = (4*nHe+nfD)/ne
    Pb = vr.brems_W_m3(ne, sd['Te_keV'], zeff)
    Pf = nfD*nHe*sd['sv_sd']*Y
    return Pb/Pf


def thermal_reference(T, d_frac):
    """Thermal D-3He at Ti = Te = T with D:3He = d_frac:(1-d_frac) by ions: brems and neutron shares (no secondaries, no synchrotron)."""
    nD, nH = d_frac, 1-d_frac
    ne = nD+2*nH; zeff = (nD+4*nH)/ne
    n0 = 1e21
    rD, rH, rE = nD*n0, nH*n0, ne*n0
    p_dhe = rD*rH*vr.sigma_v('DHe3', T)*Y
    r_dd = 0.5*rD*rD*(vr.sigma_v('DDn', T)+vr.sigma_v('DDp', T))
    p_dd = r_dd*(0.5*3.27+0.5*4.03)*MEV
    pn = r_dd*0.5*2.45*MEV+r_dd*0.5*0.5*14.07*MEV           # tritons burn ~50 % in a confined thermal plasma (bracket)
    pb = vr.brems_W_m3(rE, T, zeff)
    return dict(T_keV=T, D_fraction=d_frac, brems_share=pb/(p_dhe+p_dd), neutron_share=pn/(p_dhe+p_dd))

def hot_ion(Ti, Te, d_frac, n0=1e21):
    """Hybrid: a thermal D-3He burn held at Ti > Te by ion-heating beam injection. The beam must replace the ion-to-electron transfer
    P_ei = sum_b 1.5 ne k (Ti - Te) / tau_eb (NRL convention, vertex_source.tau_ex). All shares are density independent (n^2)."""
    nD, nH = d_frac*n0, (1-d_frac)*n0
    ne = nD+2*nH; zeff = (nD+4*nH)/ne
    lnL = vr.lnlambda(ne, Te)
    p_dhe = nD*nH*vr.sigma_v('DHe3', Ti)*Y
    r_dd = 0.5*nD*nD*(vr.sigma_v('DDn', Ti)+vr.sigma_v('DDp', Ti))
    p_f = p_dhe+r_dd*(0.5*3.27+0.5*4.03)*MEV
    pn = r_dd*0.5*2.45*MEV+r_dd*0.5*0.5*14.07*MEV
    pb = vr.brems_W_m3(ne, Te, zeff)
    pei = 0.0
    if Ti > Te:
        for nb, Zb, mb in ((nD, 1, mD), (nH, 2, mHe3)):
            tau = vs.tau_ex(ne, 1, ME, Te, nb, Zb, mb, Ti, lnL)
            pei += 1.5*ne*(Ti-Te)*KEV/tau
    return dict(Ti_keV=Ti, Te_keV=Te, D_fraction=d_frac, brems_share=pb/p_f, neutron_share=pn/p_f, ei_share=pei/p_f)


def ledger_hot_ion(h, m, cn):
    loop = h['ei_share']*(1-m['eta_acc']*m['eta_dec'])/(m['eta_acc']*m['eta_dec'])
    heat = loop+h['brems_share']*m['i_ph']+h['neutron_share']*m['a_n']
    tap = h['ei_share']/(m['eta_acc']*m['eta_dec'])
    jet = m['eta_noz']*(1-h['brems_share']-h['neutron_share']-tap+h['ei_share'])
    P_fus = cn['jet_total_W']/jet if jet > 0 else float('inf')
    return dict(recirc_heat_frac=loop, heat_frac=heat, tap_frac=tap, jet_frac=jet, P_fus_TW=P_fus/1e12, heat_GW=heat*P_fus/1e9,
                radiator_multiple=heat*P_fus/(cn['hot_radiator_W']*cn['hot_share']))

# ---------- 5. recirculating collider (storage ring / ERL): the Rider-Nevins bound -------------------------------------------------

def recirculation(Ecm_keV=400.0, lnL=20.0, budget=4e-5):
    cr = coulomb_ratio(Ecm_keV, lnL)
    k = cr['recirc_per_fusion']             # beam energy that must be restored per fusion (ion-ion only, no electrons)
    eta_req = 1-budget/k
    # thermodynamic floor: entropy per scattering event ~ k_B * ln(phase-space growth); take ln-growth 3 (bracket 1-10) at the 1800 K sink
    floor = cr['ratio']*3*KB*1800.0/Y
    return dict(Ecm_keV=Ecm_keV, coulomb_events_per_fusion=cr['ratio'], restored_energy_per_fusion=k,
                eta_required_for_absorbed_budget=eta_req, budget=budget,
                entropy_floor_fraction=floor,
                note='Even with no electrons in the burn, every fusion costs ~ratio Coulomb events that each degrade beam energy and emittance. '
                     'The heat left in hardware is (1 - eta) x restored power. The thermodynamic floor (k T ln growth per event at 1800 K) '
                     'is ~1e-6 of the fusion energy: the bound is engineering, not the second law, but it needs near-reversible beam cooling.')


def control_limits(ne=1e22, Te_keV=30.0, events_per_s=None):
    lam_d = math.sqrt(EPS0*Te_keV*KEV/(ne*E_CH*E_CH))
    nd = ne*4/3*math.pi*lam_d**3
    spacing = ne**(-1/3)
    vth = math.sqrt(2*400*KEV/mD)
    return dict(ne_m3=ne, Te_keV=Te_keV, debye_length_m=lam_d, particles_per_debye_sphere=nd, interparticle_spacing_m=spacing,
                rutherford_event_time_s=spacing/vth, events_per_s_per_engine=events_per_s,
                note='Beyond a Debye length a single ion is screened: sensors and fields act on collective modes of ~N_D ions, never on one ion. '
                     'Rutherford outcomes are random (impact parameter below the inter-particle spacing, femtometre-scale b0), so control can '
                     'only correct after the fact, at the rate the scattering happens.')

# ---------- 6. ship-level ledger -------------------------------------------------------------------------------------------------

MATURITY = {
    # eta_acc: electric -> beam; eta_dec: charged-product energy -> electric; eta_rec: beam energy recovered per pass in a collider;
    # i_ph: share of photons intercepted by hardware; a_n: share of neutron power absorbed; eta_noz: jet / plasma power
    'present': dict(eta_acc=0.5, eta_dec=0.6, eta_rec=0.999, i_ph=0.62, a_n=0.87, eta_noz=0.75,
                    basis='NBI/RFQ wall-plug 0.3-0.6; TWDEC 0.55-0.70 (ARTEMIS studies); ERL recovery 0.994-0.9996 (CBETA, cERL) for '
                          'unscattered beams; Vertex 1.5 real-mesh intercept 0.62, Engine 1.4 neutron absorption 0.87'),
    'advanced': dict(eta_acc=0.90, eta_dec=0.85, eta_rec=0.9999, i_ph=0.20, a_n=0.60, eta_noz=0.85,
                     basis='SRF + solid-state RF chains near 0.9; TWDEC projections 0.8-0.9; open aft geometry with coils out of the burn sky'),
    'speculative': dict(eta_acc=0.98, eta_dec=0.95, eta_rec=0.99999, i_ph=0.05, a_n=0.40, eta_noz=0.90,
                        basis='near-lossless superconducting conversion both ways; burn region seen by 5 % hardware; HYPOTHETICAL'),
}


def ledger_beam_target(sd, sel, f_br, m, cn):
    """Self-consistent beam-target engine at the canon jet power. The beam is regenerated from the fusion products (DEC), unburned D
    recovered and re-accelerated (required: exhaust mass per reacted fuel is fixed at 1.53 by the mission ve)."""
    F = sd['F']
    loop = (1/F)*((1-m['eta_acc'])/m['eta_acc']+(1-m['eta_dec'])/(m['eta_acc']*m['eta_dec']))   # hardware heat / fusion, recirculation
    f_n = sel['neutron_power_share']
    heat = loop+f_br*m['i_ph']+f_n*m['a_n']
    tap = 1/(F*m['eta_acc']*m['eta_dec'])                  # share of fusion power that must pass through the DEC to drive the beam
    plasma = (1-f_br-f_n)+1/F-tap                           # charged fusion + deposited beam - tapped
    jet = m['eta_noz']*plasma
    P_fus = cn['jet_total_W']/jet if jet > 0 else float('inf')
    return dict(F=F, recirc_heat_frac=loop, brems=f_br, neutron=f_n, heat_frac=heat, tap_frac=tap, jet_frac=jet,
                P_fus_TW=P_fus/1e12, heat_GW=heat*P_fus/1e9, radiator_multiple=heat*P_fus/(cn['hot_radiator_W']*cn['hot_share']),
                self_sustaining=tap < (1-f_br-f_n))


def ledger_collider(rc, m, cn, f_br=0.0, f_n=2e-4):
    k = rc['restored_energy_per_fusion']
    loop = k*(1-m['eta_rec'])+k*(1-m['eta_rec'])*((1-m['eta_acc'])/m['eta_acc'])
    heat = loop+f_br*m['i_ph']+f_n*m['a_n']
    jet = m['eta_noz']*(1-f_br-f_n)
    P_fus = cn['jet_total_W']/jet
    return dict(restored_per_fusion=k, recirc_heat_frac=loop, heat_frac=heat, P_fus_TW=P_fus/1e12, heat_GW=heat*P_fus/1e9,
                radiator_multiple=heat*P_fus/(cn['hot_radiator_W']*cn['hot_share']))


def ledger_thermal(th, m, cn):
    heat = th['brems_share']*m['i_ph']+th['neutron_share']*m['a_n']
    jet = m['eta_noz']*(1-th['brems_share']-th['neutron_share'])
    P_fus = cn['jet_total_W']/jet
    return dict(heat_frac=heat, P_fus_TW=P_fus/1e12, heat_GW=heat*P_fus/1e9,
                radiator_multiple=heat*P_fus/(cn['hot_radiator_W']*cn['hot_share']))


def fuel_check(P, cn):
    """Exhaust mass per reacted fuel mass if unburned D left with the jet (no recovery). The mission fixes it at 1.53."""
    mD_share = 2.014/(2.014+3.016)
    ratio = 1+mD_share*(1-P)/P
    return dict(burnup=P, exhaust_per_reacted_if_D_vented=ratio, mission_value=cn['exhaust_per_reacted'],
                ve_if_vented_m_s=cn['exhaust_velocity_m_s']*math.sqrt(cn['exhaust_per_reacted']/ratio) if ratio > cn['exhaust_per_reacted'] else None)

# ---------- run -----------------------------------------------------------------------------------------------------------------

def main():
    cn = canon()
    out = dict(meta=dict(study='Accelerator-driven selective D-3He fusion (ASF)', status='RESEARCH, not canon', brief='owner 2026-11-21'),
               canon=cn, validation=validation())
    out['kinematics'] = kinematics(400.0)
    out['coulomb'] = [coulomb_ratio(E) for E in (50, 100, 200, 300, 400, 600, 900)]
    out['non_neutral'] = non_neutral(V_engine=cn['engine_envelope']['volume_m3'])
    # beam-target sweep
    sweep = []
    for Te in (2.0, 5.0, 10.0, 20.0, 30.0, 50.0, 80.0, 120.0, 200.0):
        for E0 in (200.0, 400.0, 700.0, 1000.0, 1500.0, 2000.0, 3000.0, 5000.0):
            sd = slowing(E0, Te, Ti_keV=min(Te, 20.0))
            if sd:
                sweep.append(dict(Te_keV=Te, E0_keV=E0, P=sd['P'], F=sd['F'], ion_share=sd['ion_share'], Ec_keV=sd['Ec_keV']))
    out['beam_target_sweep'] = sweep
    best = {}
    for Te in sorted({r['Te_keV'] for r in sweep}):
        b = max((r for r in sweep if r['Te_keV'] == Te), key=lambda r: r['F'])
        best[str(Te)] = b
    out['beam_target_best_by_Te'] = best
    # candidate operating points
    cands = {}
    for name, (E0, Te, Ti, fb, res) in dict(C_cold=(1000.0, 10.0, 10.0, 0.3, 0.3), C_warm=(2000.0, 50.0, 20.0, 0.3, 0.3),
                                            C_hot=(3000.0, 120.0, 20.0, 0.3, 0.3), C_hot_lean=(3000.0, 120.0, 20.0, 0.1, 0.1)).items():
        sd = slowing(E0, Te, Ti_keV=Ti, nfD_frac=fb)
        sel = selectivity(sd, fb, res)
        fbr = brems_share(sd, fb)
        c = dict(E0_keV=E0, Te_keV=Te, Ti_keV=Ti, beam_fraction=fb, thermal_residence=res, P=sd['P'], F=sd['F'], brems_share=fbr,
                 selectivity=sel, fuel=fuel_check(sd['P'], cn))
        c['ledger'] = {k: ledger_beam_target(sd, sel['isotropic'], fbr, m, cn) for k, m in MATURITY.items()}
        cands[name] = c
    out['beam_target_candidates'] = cands
    rc = recirculation(400.0)
    out['recirculation'] = rc
    out['collider_ledger'] = {k: ledger_collider(rc, m, cn) for k, m in MATURITY.items()}
    out['control'] = control_limits(events_per_s=rc['coulomb_events_per_fusion']*cn['fusion_per_engine_W']/Y)
    th = {f'{T:g}keV_{int(d*100)}D': thermal_reference(T, d) for T in (60.0, 100.0) for d in (0.5, 0.25, 0.1)}
    out['thermal_reference'] = th
    out['thermal_ledger'] = {k: {m_: ledger_thermal(v, MATURITY[m_], cn) for m_ in MATURITY} for k, v in th.items()}
    # scale: beam current and processed power per engine, and conversion-hardware mass at a declared specific power
    R = cn['fusion_per_engine_W']/Y
    sc = []
    for tag, P, E0, k in (('beam-target C_hot (P from the model)', cands['C_hot']['P'], 3000.0, None),
                          ('collider, ion-only (restored energy per fusion)', None, 400.0, rc['restored_energy_per_fusion'])):
        if P:
            I = R*E_CH/P; Pb = I*E0*1e3
        else:
            Pb = k*cn['fusion_per_engine_W']; I = Pb/(E0*1e3)
        row = dict(case=tag, reactions_per_s=R, beam_current_A=I, processed_power_W=Pb)
        for lvl, sp in (('present_1kW_kg', 1e3), ('advanced_100kW_kg', 1e5), ('speculative_10MW_kg', 1e7)):
            row[f'mass_t_{lvl}'] = Pb/sp/1e3
        sc.append(row)
    out['scale'] = dict(rows=sc, drive_allowance_t=250.0, vertex_engine_drawn_t=1244.0,
                        note='Specific powers are declared HYPOTHESES (kW of processed power per kg of converter, supply, RF and cooling).')
    hi = {}
    for Ti in (100.0, 150.0):
        for Te in (Ti, 0.7*Ti, 0.5*Ti, 0.35*Ti):
            for d in (0.5, 0.3, 0.2):
                h = hot_ion(Ti, Te, d)
                h['ledger'] = {k: ledger_hot_ion(h, m, cn) for k, m in MATURITY.items()}
                hi[f'Ti{Ti:g}_Te{Te:g}_D{int(d*100)}'] = h
    out['hot_ion_hybrid'] = hi
    out['required_intercept'] = {k: dict(brems_share=v['brems_share'], intercept_needed=cn['absorbed_fraction']/v['brems_share'])
                                 for k, v in (('thermal 100 keV 1:1', th['100keV_50D']), ('hybrid Ti150 Te105 D50', hi['Ti150_Te105_D50']),
                                              ('beam-target C_warm', dict(brems_share=cands['C_warm']['brems_share'])))}
    out['hot_ion_best'] = {k: min(hi.items(), key=lambda kv: kv[1]['ledger'][k]['radiator_multiple'] if kv[1]['ledger'][k]['jet_frac'] > 0 else 1e99)[0]
                           for k in MATURITY}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, default=float))
    return out


def report(o):
    print('validation'); [print('  ', r) for r in o['validation']]
    print('kinematics @400 keV cm'); [print(f"   {r['arrangement']:<55} {r['E_lab_keV']:10.0f} keV x{r['ratio_to_min']:.2f}") for r in o['kinematics']['rows']]
    print('coulomb'); [print(f"   {r['Ecm_keV']:5} keV  sig_f {r['sigma_fusion_b']:.3f} b  sig_C {r['sigma_coulomb_b']:.1f} b  ratio {r['ratio']:.0f}  restored/fusion {r['recirc_per_fusion']:.2f}") for r in o['coulomb']]
    print('non-neutral'); [print('  ', {k: f'{v:.3g}' for k, v in r.items()}) for r in o['non_neutral']['rows']]
    print('beam-target best F by Te'); [print(f"   Te {k:>6}: E0 {v['E0_keV']:.0f} P {v['P']:.4f} F {v['F']:.2f}") for k, v in o['beam_target_best_by_Te'].items()]
    for k, c in o['beam_target_candidates'].items():
        print(k, f"P {c['P']:.4f} F {c['F']:.2f} brems {c['brems_share']:.3f} sel {c['selectivity']} fuel {c['fuel']['exhaust_per_reacted_if_D_vented']:.1f}")
        for m, l in c['ledger'].items():
            print('    ', m, {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in l.items()})
    print('recirc', o['recirculation'])
    for m, l in o['collider_ledger'].items():
        print('   collider', m, {kk: round(vv, 5) for kk, vv in l.items()})
    print('control', o['control'])
    for k, v in o['thermal_reference'].items():
        print('thermal', k, {kk: round(vv, 4) for kk, vv in v.items()}, {m: round(l['radiator_multiple'], 1) for m, l in o['thermal_ledger'][k].items()})
    for k, h in o['hot_ion_hybrid'].items():
        print('hot-ion', k, f"br {h['brems_share']:.3f} n {h['neutron_share']:.4f} ei {h['ei_share']:.3f}",
              {m: (round(l['radiator_multiple'], 0), round(l['jet_frac'], 3)) for m, l in h['ledger'].items()})
    print('hot-ion best', o['hot_ion_best'])
    for r in o['scale']['rows']:
        print('scale', {k: (f'{v:.3g}' if isinstance(v, float) else v) for k, v in r.items()})
    print('intercept', o['required_intercept'])


if __name__ == '__main__':
    report(main())
