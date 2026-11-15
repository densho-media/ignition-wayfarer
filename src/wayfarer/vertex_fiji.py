"""Vertex Engine 1.6: Fiji-assisted advanced fusion and nanoengineered materials (owner brief 2026-11-15 19:59Z, `[vertex_fiji]`).

Research only. The released Engine 1.5 (four independent Compact Vertex engines, M0-NOMINAL, 1.2 geometry) is the reference F0 and is
read, never changed. Order of work, as the brief asks:

  A  reproduce 1.5 from its evidence and list the canon reconciliation the four-engine direction needs;
  B  Fiji constitutive model M(T, H, S): one extraordinary property (magnetization rises with temperature over a finite range), bounded
     everywhere else; field from coil currents plus magnetization (exact dipole-kernel integral, optimal orientation), forces, energies,
     losses, collapse;
  C  the lattice assembly (Fiji liner, thermal isolation from REBCO, load path) and REBCO Jc(B, T, strain, fluence) margins;
  D  fusion levers: spin polarization, hot-ion operation and energy channeling, by the 1.5 burn models with the levers inside them;
  E  F0-F6 radiation and thermal closure on the 1.5 component map, with the SR-1 photon allowance recomputed per configuration.

Standard library only. Evidence per result: CANON_WORKING, LITERATURE_RANGE, THEORETICAL, PROTOTYPE, ANALYTIC, REDUCED_MODEL.

python3 src/wayfarer/vertex_fiji.py [--evidence]"""
import contextlib
import hashlib
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import material_physics as mp  # noqa: E402
import vertex_engine as ve  # noqa: E402
import vertex_magnet as vm  # noqa: E402
import vertex_radiation as vr  # noqa: E402
import vertex_structure as vs  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = ROOT/'references'/'evidence'/'vertex_fiji.json'
MU0 = vs.MU0
SIGMA_SB = vr.SIGMA_SB
MEV = vr.MEV
KEV = vr.KEV
# Optimal-orientation constant: (1/4 pi) times the solid-angle integral of sqrt(1 + 3 cos^2 theta) = int_0^1 sqrt(1 + 3 u^2) du
K_SPHERE = 0.5*(2.0+math.asinh(math.sqrt(3.0))/math.sqrt(3.0))
OPT, NOM, PES = 0, 1, 2


def config(s):
    return s['vertex_fiji']


def r15():
    return json.loads(vr.EVIDENCE_PATH.read_text())


# ---------- B: Fiji constitutive model -------------------------------------------------------------------------------------------------

def smoothstep(x):
    x = min(max(x, 0.0), 1.0)
    return 3*x*x-2*x**3


def lattice_law(c, T):
    """Canon A_B(T) (Fiji 05_LATTICE_LAW, WORKING): 1 below activation, smoothstep to A_max at saturation, A_max until quench."""
    return 1.0+(c['A_max']-1.0)*smoothstep((T-c['T_activation_K'])/(c['T_saturation_K']-c['T_activation_K']))


def state(c, T, branch='heating', strain=0.0, cycles=0, k=NOM):
    """Normalized saturation magnetization Ms(T, S)/Ms_max and the lattice state. Heating follows the activation smoothstep; cooling keeps the
    lattice ordered down to the release threshold (hysteresis). Above T_degrade it falls linearly to zero at quench (collapse); strain beyond
    the limit collapses it; every thermal cycle costs cycle_loss."""
    lo = 1.0/c['A_max']
    T0 = c['T_activation_K'] if branch == 'heating' else c['T_release_K']
    f = lo+(1.0-lo)*smoothstep((T-T0)/(c['T_saturation_K']-T0))
    st = 'LOW' if T < T0 else ('RISING' if T < c['T_saturation_K'] else 'SATURATED')
    if T >= c['T_degrade_K']:
        f *= max(0.0, (c['T_quench_K']-T)/(c['T_quench_K']-c['T_degrade_K'])); st = 'DEGRADING'
    if T >= c['T_quench_K']:
        f = 0.0; st = 'COLLAPSED'
    if abs(strain) > c['strain_limit']:
        f = 0.0; st = 'COLLAPSED'
    else:
        f *= max(0.0, 1.0+c['strain_sensitivity'][k]*abs(strain))
    f *= (1.0-c['cycle_loss'][k])**cycles
    return f, st


def magnetization(c, T, B_seed, branch='heating', strain=0.0, cycles=0, k=NOM):
    """M (A/m) = Ms(T, S) tanh(B_seed / B_align): bounded by mu0 Ms_max, zero without a seed field (SEED-LATTICE-02)."""
    f, st = state(c, T, branch, strain, cycles, k)
    return c['mu0_Ms_T'][k]/MU0*f*math.tanh(abs(B_seed)/c['B_align_T'][k]), st


def curve(c, k=NOM, B_seed=5.0):
    rows = []
    for T in range(300, int(c['T_quench_K'])+101, 25):
        h, sh = magnetization(c, float(T), B_seed, 'heating', k=k); co, sc = magnetization(c, float(T), B_seed, 'cooling', k=k)
        rows.append(dict(T_K=T, heating_mu0M_T=MU0*h, cooling_mu0M_T=MU0*co, state=sh, canon_A_B=lattice_law(c, T)))
    return rows


def thermodynamics(c, k=NOM, B_seed=5.0):
    """Per cubic metre of lattice at the operating point: the Maxwell relation (dS/dB)_T = (dM/dT)_B > 0 makes the magnetocaloric effect
    inverse (applying the seed field at constant temperature ABSORBS heat T dS); the magnetic work the seed circuit supplies when the lattice
    orders (M B); the energy released to the coils on collapse; hysteresis loss per ripple cycle. The lattice creates no energy."""
    T = c['T_operating_K']; dT = 1.0
    dM = (magnetization(c, T+dT, B_seed, k=k)[0]-magnetization(c, T-dT, B_seed, k=k)[0])/(2*dT)
    M, _ = magnetization(c, T, B_seed, k=k)
    ds = dM*B_seed                                    # J/(m3 K): integral of (dM/dT) dB at a saturated tanh (upper bound)
    return dict(M_A_m=M, mu0M_T=MU0*M, dM_dT_A_mK=dM, entropy_J_m3K=ds, isothermal_heat_J_m3=T*ds, seed_work_J_m3=M*B_seed,
                self_field_energy_J_m3=MU0*M*M/2, hysteresis_J_m3_cycle=c['hysteresis_share'][k]*M*c['ripple_T'][k],
                note='inverse magnetocaloric (heat absorbed on magnetizing, like FeRh); the seed circuit supplies M B per m3 when the lattice '
                     'orders and receives it back on collapse; the lattice is not a heat sink (ROOT-04, LOCKED)')


# ---------- B: field from currents plus magnetization -------------------------------------------------------------------------------------

def liners(s, t):
    """PROTOTYPE Fiji liner rings: square section t inboard of each coil's cryostat, a gap for the isolation stack."""
    c = config(s)
    return [dict(coil=q['name'], x=q['x'], R=q['r']-q['cryostat']-c['liner_gap_m']-t/2, t=t) for q in vs.coils(s)]


def cells(ring, n=8):
    for i in range(n):
        for j in range(n):
            x = ring['x']-ring['t']/2+(i+0.5)*ring['t']/n; r = ring['R']-ring['t']/2+(j+0.5)*ring['t']/n
            yield x, r, 2*math.pi*r*(ring['t']/n)**2


def kernel(x, r, xt):
    """Axisymmetric dipole kernel for an on-axis target at xt: the optimal moment direction in the meridional plane (unit, (x, r)) and
    the axial field per unit moment, mu0/(4 pi) sqrt(1 + 3 cos^2 theta)/d^3. Also the axial field of a uniformly axial moment."""
    dx, dr = x-xt, r; d = math.hypot(dx, dr); cx, cr = dx/d, dr/d
    vx, vr_ = 3*cx*cx-1.0, 3*cx*cr; n = math.hypot(vx, vr_)
    return (vx/n, vr_/n), MU0/(4*math.pi)*n/d**3, MU0/(4*math.pi)*vx/d**3


def geometry_factor(rings, xt, n=8):
    """G with B_target = mu0 Ms G for a magnetized volume (exact for a target outside the material): optimal orientation (every cell along
    its kernel; the ceiling nanofabricated orientation can approach) and uniform axial magnetization (no orientation engineering)."""
    g = ga = 0.0
    for ring in rings:
        for x, r, dV in cells(ring, n):
            _, kz, kax = kernel(x, r, xt)
            g += kz*dV/MU0; ga += kax*dV/MU0
    return g, ga


def shell_factor(ri, ro):
    """Spherical-shell bound, optimal orientation: G = K ln(ro/ri), K = 1.380 (a Halbach sphere's uniform field has 4/3)."""
    return K_SPHERE*math.log(ro/ri)


def coil_B(cs, I, x, r):
    br = bz = 0.0
    for q, i in zip(cs, I):
        a, b = vs.loop_field(q['r'], i, r, x-q['x']); br += a; bz += b
    return bz, br


def segment_factor(N):
    """Halbach N-segment discretization efficiency sin(2 pi/N)/(2 pi/N)."""
    return math.sin(2*math.pi/N)/(2*math.pi/N)


def fiji_field(s, k=NOM):
    """Field at the burn point and the C1 throat: coils (M0-NOMINAL) plus Fiji liners at the operating point; the mu0 Ms the canon lattice
    law (B_eff = B_seed A_B, 26.3 at 1000 K) would need there; per-liner forces from the coil field gradient; energies."""
    c = config(s); cs = vs.coils(s); I = vs.currents(s, 'NOMINAL'); st = ve.stations(s)
    eff = c['texture'][k]*segment_factor(c['orientation_segments']); A = lattice_law(c, c['T_operating_K'])
    targets = dict(burn=st['burn'], throat=next(q['x'] for q in cs if q['name'] == 'C1'))
    out = dict(efficiency=eff, canon_A_B=A, atomic_bound_T=c['mu0_Ms_T'][OPT], liners={}, targets={})
    for name, xt in targets.items():
        Bc = vs.axis_field(cs, I, xt); row = dict(x_m=xt, B_coil_T=Bc, cases={})
        for t in c['liner_section_m']:
            g, ga = geometry_factor(liners(s, t), xt)
            row['cases'][f'{t:g}'] = dict(G_optimal=g, G_axial=ga, B_fiji_T=[c['mu0_Ms_T'][j]*g*eff for j in range(3)],
                                         B_fiji_axial_T=[c['mu0_Ms_T'][j]*ga for j in range(3)],
                                         mu0Ms_for_canon_T=(A*c['canon_seed_T']-abs(Bc))/(g*eff), mu0Ms_for_local_T=(A-1.0)*abs(Bc)/(g*eff))
        row['shell'] = {f'{ro:g}': dict(G=shell_factor(c['bound_inner_m'], ro), B_fiji_T=c['mu0_Ms_T'][OPT]*shell_factor(c['bound_inner_m'], ro),
                                        mu0Ms_for_canon_T=(A*c['canon_seed_T']-abs(Bc))/shell_factor(c['bound_inner_m'], ro),
                                        mu0Ms_for_local_T=(A-1.0)*abs(Bc)/shell_factor(c['bound_inner_m'], ro)) for ro in c['bound_outer_m']}
        out['targets'][name] = row
    # forces and energies of the nominal liner, oriented for the burn point, at the optimistic (atomic-bound) magnetization
    t = c['liner_section_m'][NOM]; M = c['mu0_Ms_T'][OPT]/MU0*eff; h = 1e-3
    for ring in liners(s, t):
        Fx = Fr = W = V = 0.0
        for x, r, dV in cells(ring, 6):
            (ux, ur), _, _ = kernel(x, r, targets['burn'])
            mB = lambda xx, rr: (lambda b: M*(ux*b[0]+ur*b[1]))(coil_B(cs, I, xx, rr))
            Fx += (mB(x+h, r)-mB(x-h, r))/(2*h)*dV; Fr += (mB(x, r+h)-mB(x, r-h))/(2*h)*dV
            W += mB(x, r)*dV; V += dV
        out['liners'][ring['coil']] = dict(R_m=ring['R'], volume_m3=V, mass_kg=V*c['density_kg_m3'], force_x_N=Fx, force_r_N=Fr,
                                           hoop_stress_Pa=abs(Fr)/(2*math.pi*t*t), interaction_J=-W, self_energy_J=MU0*M*M/2*V)
    Bt = A*c['canon_seed_T']
    rho = mp.require(mp.get_property('MAT-TI6AL4V', 'density')); sy = mp.require(mp.get_property('MAT-TI6AL4V', 'yield_strength', 293.0), 'low')
    Wc = Bt**2/(2*MU0)*4/3*math.pi*cs[0]['r']**3
    out['canon_field'] = dict(B_T=Bt, pressure_Pa=Bt**2/(2*MU0), energy_J=Wc, virial_mass_kg=rho*Wc/sy, stress_ratio=Bt**2/(2*MU0)/sy,
                              note='the canon lattice law (5 T seed x A_B at 1000 K) applied at the Vertex burn region: field energy in a sphere of the C1 radius; virial bound '
                                   'M >= rho W / sigma at the Ti-6Al-4V room-temperature yield (PMDS)')
    return out


# ---------- C: lattice assembly ------------------------------------------------------------------------------------------------------------

def assembly(s, F, k=NOM):
    """Thermal isolation, load path and heat of the nominal liner set (per engine): refractory foils to an intermediate shield, MLI to 20 K,
    struts carrying the liner force at the allowable share of Ti-6Al-4V yield; hysteresis and eddy loss at the pulse rate; the photon flux
    on the inboard face and the temperature rise through the liner against the collapse margin."""
    c = config(s); R = r15(); pz = vm.plasma(s); f = pz['pulse_Hz']; t = c['liner_section_m'][k]; Tf = c['T_operating_K']; Ti = c['intermediate_K']
    area = sum(2*math.pi*v['R_m']*2*t for v in F['liners'].values())        # outboard and side faces toward the cryostat
    face = sum(2*math.pi*v['R_m']*t for v in F['liners'].values())          # inboard face toward the burn
    V = sum(v['volume_m3'] for v in F['liners'].values())
    q_rad = SIGMA_SB*(Tf**4-Ti**4)/((c['foil_layers']+1)*(2.0/c['foil_emissivity']-1.0))
    force = sum(math.hypot(v['force_x_N'], v['force_r_N']) for v in F['liners'].values())
    sy = mp.require(mp.get_property(c['strut_material'], 'yield_strength', 293.0), 'low')
    As = force/(c['strut_allowable_share']*sy)
    try:
        kint = mp.conductivity_integral(c['strut_material'], Ti, Tf); strut_W = As/c['strut_length_m']*kint; strut_note = 'PMDS table'
    except mp.UnknownProperty as e:
        q = mp.get_property(c['strut_material'], 'thermal_conductivity')
        if q['known']:
            kint = q['value']*(Tf-Ti); strut_W = As/c['strut_length_m']*kint
            strut_note = f"PMDS single-temperature conductivity ({q['value']:g} W/(m K) at {q['temperature_K']:g} K) held constant: no table ({e})"
        else:
            kint = None; strut_W = None; strut_note = f'OPEN: {e}'
    M = c['mu0_Ms_T'][OPT]/MU0; dB = c['ripple_T'][k]
    hyst = f*V*c['hysteresis_share'][k]*M*dB
    eddy = math.pi**2*f*f*dB*dB*c['lamination_m']**2/(6*c['resistivity_ohm_m'][k])*V
    comp = R['components']; P = R['sources']['cases']['LOW']['power_W']
    tm = thermal_map(s); caught = [tm['low']['cold_ph'], tm['high']['cold_ph']]
    flux = [x/face for x in caught]; kF = c['thermal_conductivity_W_mK'][k]; qa = armour(s)['q_max_W_m2']
    dT = [q*c['armour_thickness_m']/kF for q in flux]
    return dict(liner_section_m=t, volume_m3=V, mass_kg=V*c['density_kg_m3'], isolation_area_m2=area, inboard_area_m2=face,
                radiative_W_m2=q_rad, radiative_W=q_rad*area, mli_W=c['mli_W_m2']*area, struts=dict(force_N=force, area_m2=As, conduction_W=strut_W,
                k_integral_W_m=kint, note=strut_note), hysteresis_W=hyst, eddy_W=eddy, caught_photon_W=caught, inboard_flux_W_m2=flux,
                skin_m=c['armour_thickness_m'], vs_armour=[q/qa for q in flux], temperature_rise_K=dT, collapse_margin_K=c['T_quench_K']-Tf, survives=[Tf+x < c['T_degrade_K'] for x in dT],
                neutron_caught_share=1.0-math.exp(-t/0.15), photon_W=P['photon'])


def rebco(s, F, k=NOM):
    """Jc(B, T, strain, fluence) margin per coil about the demonstrated SPARC TFMC point (20 T, 20 K, 153 A/mm2 winding pack): field
    scaling ((B_ref + B0)/(B + B0))^beta, strain factor; APC gain (MAT-REBCO-APC01, Level B) as a bracket; the Fiji liner's added field at the
    winding; fast-neutron fluence lifetime from a point source with no shield. Jc is never unlimited."""
    c = config(s); m = s['vertex_engine']['magnet']; R = r15(); cs = vs.coils(s); I = vs.currents(s, 'NOMINAL'); st = ve.stations(s)
    Bpk = vm.conductor_field(cs, I); Bref = m['conductor_field_limit_T']; Jdemo = m['winding_current_density_A_m2']
    P = R['sources']['cases']['LOW']; lines = P['neutron_lines']; Pf = P['power_W']['fusion']
    nps = Pf*(lines['DD_2_45MeV']/(2.45*MEV)+lines['DT_14_1MeV']/(14.07*MEV))
    eff = F['efficiency']; Ms = c['mu0_Ms_T'][OPT]; rows = []
    for q, i, B in zip(cs, I, Bpk):
        J = abs(i)/(math.pi*q['a']**2)
        # liner field at the winding centre (radial distance gap + cryostat - winding); thin-ring estimate mu0 M t^2/(2 pi d^2) x pi
        d = q['cryostat']+c['liner_gap_m']+c['liner_section_m'][NOM]/2; dB = Ms*eff*c['liner_section_m'][NOM]**2/(2*d*d)
        Bw = B+dB
        scale = lambda BB, beta: ((Bref+c['jc_B0_T'])/(BB+c['jc_B0_T']))**beta
        Jc = [Jdemo*scale(B, c['jc_field_exponent'][j])*c['jc_strain_factor'][j] for j in range(3)]
        JcF = [Jdemo*scale(Bw, c['jc_field_exponent'][j])*c['jc_strain_factor'][j] for j in range(3)]
        dist = math.hypot(q['x']-st['burn'], q['r'])-q['cryostat']
        phi = nps/(4*math.pi*dist*dist)
        rows.append(dict(coil=q['name'], B_peak_T=B, J_op_A_m2=J, Jc_A_m2=Jc, margin=[x/J for x in Jc], margin_with_fiji=[x/J for x in JcF],
                         fiji_dB_T=dB, apc_margin=[Jc[j]*c['apc_gain'][j]/J for j in range(3)], distance_m=dist, fluence_rate_n_m2s=phi,
                         lifetime_s=[x/phi for x in c['fluence_limit_n_m2']], burn_fluence_n_m2=phi*c['burn_time_s']))
    worst = max(rows, key=lambda r: r['fluence_rate_n_m2s'])
    need = worst['burn_fluence_n_m2']/c['fluence_limit_n_m2'][OPT]
    W = vm.stored_energy(cs, I)
    return dict(rows=rows, neutrons_per_s=nps, worst=worst['coil'], attenuation_needed=need, shield_m=0.15*math.log(max(need, 1.0)),
                stored_J=W, dump_s=s['vertex_engine']['structure'].get('quench_dump_s', 10.0),
                cold_W=[R['thermal']['cases']['LOW']['RADIATION_low']['cold_W'], R['thermal']['cases']['LOW']['RADIATION_high']['cold_W']],
                note='margins against the demonstrated envelope scaled to the coil field: LITERATURE_RANGE scaling, not a measured critical surface '
                     '(PMDS MAT-REBCO Jc OPEN, OD-024); fluence from the LOW source with no shielding beyond the drawn cryostat, D-D and bred D-T '
                     'neutrons, against literature cryogenic-irradiation limits')


# ---------- D: fusion levers -------------------------------------------------------------------------------------------------------------

@contextlib.contextmanager
def levers(pol=1.0, dd=1.0, channel=0.0):
    """Run the 1.5 burn models with the levers inside them: sigma(D-3He) x pol, sigma(D-D) x dd, and a share `channel` of the electron part of
    every fast product's slowing sent to ions. With all levers off the functions are the released ones."""
    sv, isf = vr.sigma_v, vr.ion_share
    def sigma(reaction, T):
        return sv(reaction, T)*(pol if reaction == 'DHe3' else dd if reaction in ('DDn', 'DDp') else 1.0)
    def share(E0, Te, A, ions):
        fi = isf(E0, Te, A, ions); return fi+channel*(1.0-fi)
    vr.sigma_v, vr.ion_share = sigma, share
    try:
        yield
    finally:
        vr.sigma_v, vr.ion_share = sv, isf


def pol_factor(c, k):
    P = c['polarization'][k]*c['polarization_survival'][k]
    return 1.0+0.5*P*P


def floor(c, Ti, channel=0.0, pol=1.0, dd=1.0, ne=1e31):
    """Electron energy balance of a burn held at Ti (coupled steady state): electrons are heated by e-i exchange from the hotter ions and by
    the products' electron share not channelled; they lose bremsstrahlung. The Te at balance gives the least photon share any sustained burn
    at that Ti can have. ne cancels except in the Coulomb logarithm. Ion balance: the ions' product share must pay the exchange."""
    nHe = ne/4.0; nD = nHe; ions = [(nD, 1, vr.M_ION['D']), (nHe, 2, vr.M_ION['He3'])]; zeff = (nD+4*nHe)/ne
    rD = nD*nHe*vr.sigma_v('DHe3', Ti)*pol; rn = 0.5*nD*nD*vr.sigma_v('DDn', Ti)*dd; rp = 0.5*nD*nD*vr.sigma_v('DDp', Ti)*dd
    Pf = (rD*vr.Q['DHe3']+rn*vr.Q['DDn']+rp*vr.Q['DDp'])*MEV
    def bal(Te):
        pe = pi = 0.0
        for rate, prods in ((rD, vr.PRODUCTS['DHe3']), (rn, vr.PRODUCTS['DDn']), (rp, vr.PRODUCTS['DDp'])):
            for sp, e in prods.items():
                if sp == 'n':
                    continue
                fi = vr.ion_share(e*1e3, Te, vr.M_ION[sp], ions); fi = fi+channel*(1-fi)
                pi += rate*e*MEV*fi; pe += rate*e*MEV*(1-fi)
        nu = sum(3.2e-9*Z*Z*(n*1e-6)*vr.lnlambda(ne, Te)/(A*(Te*1e3)**1.5) for n, Z, A in ions)
        pei = 1.5*ne*(Ti-Te)*KEV*nu
        return pe+pei-vr.brems_W_m3(ne, Te, zeff), pe, pi, pei
    lo, hi = 0.05, Ti
    if bal(hi)[0] > 0:
        Te = Ti
    else:
        for _ in range(100):
            mid = math.sqrt(lo*hi); lo, hi = (mid, hi) if bal(mid)[0] > 0 else (lo, mid)
        Te = math.sqrt(lo*hi)
    _, pe, pi, pei = bal(Te); Pb = vr.brems_W_m3(ne, Te, zeff)
    return dict(Ti_keV=Ti, Te_keV=Te, Te_over_Ti=Te/Ti, photon_share=Pb/Pf, exchange_share=pei/Pf, ion_heating_share=pi/Pf,
                sustained=pi >= pei, channel=channel, pol=pol)


def analytic(s, case, Tburn, pol=1.0, dd=1.0):
    with levers(pol, dd):
        return vr.analytic_case(s, case, Tburn)


def coupled(s, Ti, Te_over_Ti, pol=1.0, dd=1.0, channel=0.0):
    """R2-B self-consistent burn of the implied target (1.5's model) with the levers inside, its areal density solved for the demonstrator
    yield: the time-integrated photon share and the electron temperature the burn actually reaches."""
    case = dict(id=f'R2B-{Ti:g}-{Te_over_Ti:g}', Ti_keV=Ti, Te_over_Ti=Te_over_Ti, D_per_He3=1.0, deposition=1.0, expansion=1.0)
    with levers(pol, dd, channel):
        rr = vr.rhoR_for_yield(s, case)
        b = vr.burn(s, dict(case, rhoR_g_cm2=rr if rr else 30.0), spectrum=False)
    Te_end = b['history'][-1][2] if b['history'] else None
    Te_max = max(h[2] for h in b['history']) if b['history'] else None
    return dict(case=case['id'], rhoR_g_cm2=rr, photon_share=b['photon_share'], neutron_share=b['neutron_share'], burn_fraction=b['burn_fraction'],
                Te_peak_keV=Te_max, Te_end_keV=Te_end, Ti_peak_keV=b['Ti_peak_keV'], pol=pol, dd=dd, channel=channel)


def fusion(s):
    c = config(s); R = r15(); Tburn = R['sources']['cases']['CONSERVATIVE']['burn']['tritium_burnup']
    low = next(x for x in s['vertex_radiation']['cases'] if x['id'] == 'LOW')
    base = analytic(s, low, Tburn)
    pol = [dict(k=k, factor=pol_factor(c, k), dd=c['dd_factor'][k], **{x: analytic(s, low, Tburn, pol_factor(c, k), c['dd_factor'][k])[x]
               for x in ('photon_share', 'neutron_share')}) for k in (OPT, NOM, PES)]
    pz = vm.plasma(s); prep = c['polarization_J_kg']*pz['mass_kg']*pz['pulse_Hz']
    fl = {f'{eta:g}': [floor(c, T, eta) for T in c['floor_Ti_keV']] for eta in [0.0]+c['channel_share']}
    fl_pol = [floor(c, T, c['channel_share'][OPT], pol_factor(c, OPT), c['dd_factor'][OPT]) for T in c['floor_Ti_keV']]
    best = min((r for rows in fl.values() for r in rows if r['sustained']), key=lambda r: r['photon_share'])
    best_pol = min((r for r in fl_pol if r['sustained']), key=lambda r: r['photon_share'])
    runs = [coupled(s, 110.0, 0.5), coupled(s, 110.0, 0.5, channel=c['channel_share'][NOM]),
            coupled(s, 150.0, 0.3, pol_factor(c, OPT), c['dd_factor'][OPT], c['channel_share'][OPT])]
    return dict(reference=dict(photon_share=base['photon_share'], neutron_share=base['neutron_share'], released=R['sources']['cases']['LOW']['photon_share']),
                polarization=pol, polarization_power_W=prep, polarization_note='THEORETICAL: sigma x (1 + P_D P_He / 2) for parallel spins '
                '(Kulsrud et al. 1982); depolarization in a dense hot burn (spin-flip collisions, field gradients) is not modelled, it enters as '
                'survival; D-D suppression disputed (dd_factor 1 nominal). Fiji does not preserve polarization.',
                floor=fl, floor_polarized=fl_pol, best_floor=best, best_floor_polarized=best_pol, coupled=runs,
                channel_cost_W=[c['channel_cost'][k]*c['channel_share'][k]*R['sources']['cases']['LOW']['ledger']['charged_J']*pz['pulse_Hz'] for k in (OPT, NOM, PES)])


# ---------- E: materials, radiators, shielding, insulation, hydrogen -------------------------------------------------------------------

QUAL = [('MAT-W', 'plasma-facing armour'), ('MAT-W-ADV01', 'armour (fibre-reinforced, Level B)'), ('MAT-W-FIJI01', 'armour (Fiji-stabilized, Level C)'),
        ('MAT-REBCO', 'coil conductor'), ('MAT-REBCO-APC01', 'coil conductor (APC, Level B)'), ('MAT-TI6AL4V', 'structure, liner struts'),
        ('MAT-NB1ZR', 'hot circuit'), ('MAT-SS-316LN', 'cryostat'), ('MAT-CU-OF', 'power'), ('MAT-LIH', 'neutron shield'), ('MAT-B4C', 'neutron absorber'),
        ('MAT-HDPE', 'polymer shield'), ('MAT-RAD-NPE01', 'nanophotonic radiator skin (Level B)')]
PROPS = [('max_service_temperature', None), ('melting_point', None), ('thermal_conductivity', 1000.0), ('specific_heat', None),
         ('thermal_expansion', None), ('yield_strength', 293.0), ('density', None)]


def qualify(s):
    rows = []
    for mid, use in QUAL:
        r = dict(material=mid, use=use)
        for p, T in PROPS:
            try:
                q = mp.get_property(mid, p, T)
            except KeyError:
                r[p] = 'OPEN'; continue
            if not q['known'] and q['status'] == 'OUT_OF_RANGE' and p == 'thermal_conductivity':
                q = mp.get_property(mid, p, q['valid_K'][1] if q['valid_K'] else None)
            r[p] = (q['value'] if q['value'] is not None else [q['low'], q['high']]) if q['known'] else q['status']
            r['level'] = q['level']
        rows.append(r)
    return rows


def armour(s):
    """Heat-removal capacity is not radiation tolerance: the most heat flux a W armour of the given thickness passes from its service limit to
    the coolant (PMDS conductivity integral), against the 1.5 peak incident flux."""
    c = config(s); R = r15(); Tmax = mp.require(mp.get_property('MAT-W', 'max_service_temperature'), 'low')
    q = mp.conductivity_integral('MAT-W', c['armour_coolant_K'], Tmax)/c['armour_thickness_m']
    peak = max(v['peak_irradiance_per_W'] for v in R['components'].values() if v.get('peak_irradiance_per_W'))*R['sources']['cases']['LOW']['power_W']['photon']
    return dict(T_limit_K=Tmax, coolant_K=c['armour_coolant_K'], thickness_m=c['armour_thickness_m'], q_max_W_m2=q, peak_W_m2=peak, shortfall=peak/q)


def cop(c, T, Th):
    return c['carnot_fraction']*T/(Th-T)


def thermal_map(s):
    """1.5 T-01 reproduced from its component map (LOW source): per engine hot, cold photon and neutron heat in each bracket."""
    R = r15(); c = s['vertex_radiation']; comp = R['components']; strict = [m for m in c['cold_materials'] if m != 'cryostat']; out = {}
    for b in ('low', 'high'):
        h = dict(hot_ph=0.0, cold_ph=0.0, hot_n=0.0, cold_n=0.0)
        for v in comp.values():
            cold = any(m in (strict if b == 'low' else c['cold_materials']) for m in (v.get('material') or []))
            h['cold_ph' if cold else 'hot_ph'] += v['photon']['LOW'][b]
            if b == 'high':
                h['cold_n' if cold else 'hot_n'] += v['neutron_upper']['LOW']
        h['blades'] = R['thermal']['cases']['LOW'][f'RADIATION_{b}']['radiator_direct_W']/4
        out[b] = h
    return out


def closure(s, label, ph_scale, n_scale, cap_scale=1.0, liner=None, cold_scale=1.0, extra_hot=0.0, extra_cold=0.0, extra_warm=0.0, extra_mid=(0.0, 300.0)):
    """Per-engine and four-engine heat for one configuration: photon heat scales with the photon power, neutron heat with the neutron power;
    a liner moves the cold parts' photons (all intercepted energy, high bracket; Compton share, low) and a share of their neutrons to its own
    temperature, lifted to the radiator by a heat pump; extra loads are added at hot, 20 K and warm (liner) temperature."""
    c = s['vertex_radiation']; R = r15(); th = R['thermal']; Th = s['radiators']['temperature']['value']; cap = th['capacity_W']*cap_scale
    k20 = cop(c, c['cold_K'], Th); tm = thermal_map(s); rows = {}
    for b, h in tm.items():
        hot = h['hot_ph']*ph_scale+h['hot_n']*n_scale+extra_hot; cold = (h['cold_ph']*ph_scale+h['cold_n']*n_scale)*cold_scale+extra_cold
        warm = extra_warm; kw = None
        if liner:
            moved_ph = h['cold_ph']*ph_scale*cold_scale; moved_n = h['cold_n']*n_scale*cold_scale*liner['n_share']
            cold -= moved_ph+moved_n; warm += moved_ph+moved_n
            kw = cop(c, liner['T_K'], Th)
        mid = extra_mid[0]; lift = cold/k20+(warm/kw if kw else 0.0)+(mid/cop(c, extra_mid[1], Th) if mid else 0.0)
        reject = hot+cold+warm+mid+lift; four = 4*reject+4*h['blades']*ph_scale
        rows[b] = dict(hot_W=hot, cold_W=cold, warm_W=warm+mid, refrigeration_W=lift, reject_W=reject, four_W=four, ratio=four/cap)
    per = rows['low']['reject_W']/(R['sources']['cases']['LOW']['power_W']['photon']*ph_scale) if ph_scale else None
    return dict(label=label, capacity_W=cap, brackets=rows, ratio=[rows['low']['ratio'], rows['high']['ratio']], heat_per_photon_W=per)


def hydrogen(s, excess_W):
    """Regenerative hydrogen: the mass flow that carries the excess heat out of the ship in the exhaust, its total over the four burns and its
    exhaust speed. The energy leaves only with the hydrogen; the hydrogen is reaction mass the mission must carry."""
    c = config(s); out = []
    for k in (OPT, NOM, PES):
        h = c['h2_enthalpy_J_kg'][k]; md = excess_W/h
        out.append(dict(enthalpy_J_kg=h, mdot_kg_s=md, mass_kg=md*c['burn_time_s'], v_exhaust_m_s=math.sqrt(2*c['h2_nozzle_efficiency']*h)))
    return out


def insulation(s):
    """Nanoporous / MLI tank insulation per m2 at 20 K (D, H2) and the work to lift it to the radiator; independent of the engine heat."""
    c = config(s); vrc = s['vertex_radiation']; Th = s['radiators']['temperature']['value']; k = cop(vrc, vrc['cold_K'], Th)
    return dict(mli_W_m2=c['tank_mli_W_m2'], aerogel_mli_W_m2=c['tank_aerogel_W_m2'], lift_W_per_W=1/k,
                lift_W_m2=[x/k for x in c['tank_aerogel_W_m2']], note='He-3 stored below its 3.2 K boiling point needs a sub-4 K stage (COP far below '
                'the 20 K value); kept separate from engine closure: tank leaks are watts per m2, the engines are terawatts')


def shielding(s):
    """Shield heat: a nanocomposite or hydride shield stops neutrons and photons but keeps their heat at its own temperature limit."""
    c = config(s); vrc = s['vertex_radiation']; Th = s['radiators']['temperature']['value']; R = r15(); P = R['sources']['cases']['LOW']['power_W']
    sh = R['components']['SHADOW_SHIELD']; heat = sh['photon']['LOW']['high']+sh['neutron_upper']['LOW']
    rows = []
    for name, T in (('LiH (melts 962 K) at the shield temperature', c['shield_K']), ('polymer / nanocomposite (B4C-HDPE class)', c['polymer_limit_K'])):
        k = cop(vrc, T, Th); rows.append(dict(name=name, T_K=T, cop=k, heat_W=heat, reject_W=heat*(1+1/k)))
    return dict(rows=rows, neutron_W=P['neutron'])


# ---------- E: F0-F6 ---------------------------------------------------------------------------------------------------------------------

def variants(s, F, A, Rb, Fu):
    c = config(s); R = r15(); L = R['sources']['cases']['LOW']; ph0 = L['photon_share']; n0 = L['neutron_share']
    eps = s['radiators']['emissivity']['value']; capn = c['radiator_emissivity_nano']/eps
    Pf = L['power_W']['fusion']; jet_eff = L['ledger']['jet_J']/L['ledger']['charged_J']; ve_ = vm.plasma(s)['exhaust_m_s']
    vrc = s['vertex_radiation']; Th = s['radiators']['temperature']['value']
    liner = dict(T_K=c['T_operating_K'], n_share=A['neutron_caught_share'])
    leak_cold = A['mli_W']; leak_warm = (A['radiative_W']+(A['struts']['conduction_W'] or 0.0))   # into the 300 K intermediate shield
    lin_hot = A['hysteresis_W']+A['eddy_W']                                     # in the liner (1000 K loop)
    a_scale = []
    for q in vs.coils(s):
        g = c['apc_gain'][NOM]; aw = q['a']/math.sqrt(g); a_scale.append((q['cryostat']-(q['a']-aw))/q['cryostat'])
    cold_apc = sum(a_scale)/len(a_scale)
    fl = Fu['best_floor']; flp = Fu['best_floor_polarized']; pol_nom = Fu['polarization'][NOM]
    coupled_ch = Fu['coupled'][1]; coupled_all = Fu['coupled'][2]
    defs = [
        ('F0', '1.5 baseline (LOW source, as drawn)', dict(ph=1.0, n=1.0), 'reproduces 1.5 T-01: 854x', []),
        ('F1', 'Fiji lattice liner at 1000 K (field + hot shield)', dict(ph=1.0, n=1.0, liner=True), 'the liner shields the cold parts but its heat is pumped from 1000 K', ['B', 'C']),
        ('F1-REF', 'conventional W liner at its 1300 K service limit (comparator, no Fiji)', dict(ph=1.0, n=1.0, liner='W'), 'what the same liner does without Fiji', ['C']),
        ('F2', 'advanced REBCO (APC) and nanofabricated coils', dict(ph=1.0, n=1.0, cold=cold_apc), 'thinner cryostats intercept less (optimistic: neutron shielding wants thicker)', ['D']),
        ('F3', 'spin-polarized D-3He (nominal polarization)', dict(ph=pol_nom['photon_share']/ph0, n=pol_nom['neutron_share']/n0), 'THEORETICAL cross-section gain', ['E']),
        ('F4', 'hot-ion burn with energy channeling (coupled R2-B, nominal channeling)', dict(ph=coupled_ch['photon_share']/ph0, n=coupled_ch['neutron_share']/n0, hot=Fu['channel_cost_W'][NOM]), 'the coupled burn, not a held Te', ['E']),
        ('F4-FLOOR', 'hot-ion electron-balance floor (best sustained Ti and channeling)', dict(ph=fl['photon_share']/ph0, n=1.0, hot=Fu['channel_cost_W'][OPT]), 'a lower bound on any sustained burn', ['E']),
        ('F5', 'refractory, shielding, insulation, nanophotonic radiator (emissivity 0.98)', dict(ph=1.0, n=1.0, cap=capn), 'capacity +8.9 %', ['F']),
        ('F6', 'integrated: F1 + F2 + polarized, channelled floor + F5 (one calculation, no double counting)',
         dict(ph=flp['photon_share']/ph0, n=Fu['polarization'][OPT]['neutron_share']/n0, liner=True, cold=cold_apc, cap=capn, hot=Fu['channel_cost_W'][OPT]), 'best case of every lever together', ['B', 'C', 'D', 'E', 'F']),
        ('F6-COUPLED', 'integrated with the coupled burn (polarized, channelled R2-B) instead of the floor',
         dict(ph=coupled_all['photon_share']/ph0, n=coupled_all['neutron_share']/n0, liner=True, cold=cold_apc, cap=capn, hot=Fu['channel_cost_W'][OPT]), 'the integrated case as a burn', ['B', 'C', 'D', 'E', 'F']),
    ]
    out = []
    for vid, name, d, note, deliv in defs:
        ln = None; xc = xw = 0.0; xm = (0.0, c['intermediate_K'])
        if d.get('liner') is True:
            ln = liner; xc = leak_cold; xw = lin_hot; xm = (leak_warm, c['intermediate_K'])
        elif d.get('liner') == 'W':
            ln = dict(T_K=mp.require(mp.get_property('MAT-W', 'max_service_temperature'), 'low'), n_share=A['neutron_caught_share'])
        cl = closure(s, name, d['ph'], d['n'], d.get('cap', 1.0), ln, d.get('cold', 1.0), extra_hot=d.get('hot', 0.0), extra_cold=xc, extra_warm=xw, extra_mid=xm)
        ph = ph0*d['ph']; nn = n0*d['n']; ch = 1.0-ph-nn
        Pjet = jet_eff*ch*Pf; thrust = 2*Pjet/ve_
        args = (d.get('cap', 1.0), ln, d.get('cold', 1.0)); kw = dict(extra_hot=d.get('hot', 0.0), extra_cold=xc, extra_warm=xw, extra_mid=xm)
        fixed = closure(s, name, 0.0, d['n'], *args, **kw)['brackets']['low']['reject_W']
        h_ph = (cl['brackets']['low']['reject_W']-fixed)/(ph0*d['ph']*Pf)
        need = (cl['capacity_W']/4-fixed)/(Pf*h_ph)
        cl['heat_per_photon_W'] = h_ph
        bare = closure(s, name, d['ph'], d['n'], *args)['ratio'][0]
        if need <= 0:
            need = None
        b = cl['brackets']['low']
        out.append(dict(id=vid, name=name, note=note, deliverables=deliv, photon_share=ph, neutron_share=nn, charged_share=ch,
                        per_engine=dict(fusion_W=Pf, charged_W=ch*Pf, photon_W=ph*Pf, neutron_W=nn*Pf, exhaust_W=Pjet,
                                        hardware_W=b['hot_W']+b['cold_W']+b['warm_W'], cryogenic_W=b['cold_W'], refrigeration_W=b['refrigeration_W'],
                                        hot_radiator_W=b['reject_W'], warm_W=b['warm_W'], reaction_mass_W=0.0, thrust_N=thrust,
                                        escaping_W=Pf-Pjet-(b['hot_W']+b['cold_W']+b['warm_W'])),
                        ratio=cl['ratio'], heat_per_photon_W=cl['heat_per_photon_W'], sr1_photon_share_needed=need,
                        sr1_factor=ph/need if need else None, fixed_heat_W=fixed, fixed_exceeds_radiator=need is None, ratio_without_overheads=bare, power_to_close=1.0/cl['ratio'][0], closes=cl['ratio'][0] <= 1.0))
    return out


def reconciliation():
    """Phase A: where the 1.6 direction meets LOCKED canon. Proposals for owner approval; nothing is edited."""
    return [
        dict(id='REC-1', canon='Fiji 04_ROOT_TRUTHS drive topology (LOCKED): 1 core -> common plasma -> 1 manifold -> 4 channels -> 4 magnetic nozzles; '
             'fusion_core_count 1 (LOCKED)', direction='four independent Compact Vertex engines, each with one fusion region and one magnetic nozzle',
             proposal='Record the four-engine Vertex cluster as a separate research architecture beside the LOCKED single-core Fiji drive, not as a '
             'replacement: add a row "VERTEX_CLUSTER research architecture (fusion_core_count 4, nozzle_count 4), status RESEARCH" to the Fiji '
             'workbook interface table and leave the LOCKED rows as they are', destination='Fiji / Lattice Drive Science Model, 04_ROOT_TRUTHS interface rows; '
             'Wayfarer S&E 15_MODEL_INTERFACES (propulsion_representation)'),
        dict(id='REC-2', canon='Fiji 05_LATTICE_LAW (LOCKED law, WORKING calibration): B_eff = B_seed x A_B(T), A_max 30, 150 T derived',
             direction='the 1.6 brief: M = M(T, H, S), no constant amplification factor', proposal='Keep the law\'s temperature shape (activation, '
             'saturation, release, quench) and reinterpret A_B as the ratio of high- to low-temperature magnetization of the lattice; state that the '
             'field a structure reaches is mu0 Ms times a geometry factor, so 150 T is not a material property. Mark B_sat 150 T as '
             '"SINGLE_CORE_CALIBRATION only"', destination='Fiji 05_LATTICE_LAW rows B_sat and A_max notes; 35_SCALING_LIMITS'),
        dict(id='REC-3', canon='Fiji 04_ROOT_TRUTHS: no free field or energy (LOCKED); lattice is not a bulk heat sink (LOCKED)', direction='unchanged',
             proposal='No change: the 1.6 model obeys both (seed-circuit work M B, collapse returns it; inverse magnetocaloric heat)', destination='none'),
        dict(id='REC-4', canon='Technology 41_MATERIALS_MANUFACTURING: Fiji harvested, not synthesized; nanotech orients and engineers it', direction='unchanged',
             proposal='Add the orientation pattern (segmented optimal orientation, texture) as the nanofabrication step that sets the geometry factor',
             destination='IGNITION Technology 41_MATERIALS_MANUFACTURING, Fiji lattice processing row'),
        dict(id='REC-5', canon='S&E OD-024 (5 T seed separate from amplification; conductor OPEN)', direction='REBCO Jc margins and the neutron fluence finding',
             proposal='Append to OD-024: coil Jc margin is not limiting at <= 8 T; REBCO fast-neutron fluence at the closure coils is limiting (see R16-4)',
             destination='Wayfarer S&E open decisions OD-024 (request Doc queue item)'),
    ]


def proposals(s, R16):
    """Section 16: proposed workbook rows with exact destinations, for owner review. None is written."""
    g = {x['id']: x for x in R16['gates']}
    return [
        dict(workbook='Fiji / Lattice Drive Science Model', tab='05_LATTICE_LAW', anchor='after the B_sat row', change='add row "Ms_ceiling: mu0 Ms <= about 3.5 T '
             '(atomic-moment bound) unless the owner authorizes a second extraordinary property; status RESEARCH (Vertex 1.6)"'),
        dict(workbook='Fiji / Lattice Drive Science Model', tab='04_ROOT_TRUTHS', anchor='interface rows (fusion_core_count)', change='add the VERTEX_CLUSTER research row (REC-1)'),
        dict(workbook='Fiji / Lattice Drive Science Model', tab='35_SCALING_LIMITS', anchor='150 T / 9 GPa row', change='note "single-core calibration; not a material constant (Vertex 1.6 REC-2)"'),
        dict(workbook='IGNITION Technology', tab='41_MATERIALS_MANUFACTURING', anchor='Fiji lattice processing', change='add "orientation pattern sets the geometry factor; '
             'texture <= 0.98, N-segment efficiency" (REC-4)'),
        dict(workbook='IGNITION Technology', tab='41_MATERIALS_MANUFACTURING', anchor='Nanophotonic radiator surfaces', change='add "emissivity 0.98 vs 0.90 is +8.9 % capacity; '
             'not a remedy for a hundredfold thermal gap (Vertex 1.6 F5)"'),
        dict(workbook='Wayfarer S&E', tab='open decisions OD-024..027 (request Doc)', anchor='OD-024', change=f"REBCO neutron fluence: {g['R16-4']['value']}"),
        dict(workbook='Wayfarer S&E', tab='open decisions OD-025', anchor='plasma-facing heat flux', change='W armour carries about 1e7 W/m2 at 5 mm; the 1.5 peak flux is several hundred times that'),
    ]


def gates(s, F, A, Rb, Fu, V):
    R = r15(); G = []; c = config(s)
    f0 = next(v for v in V if v['id'] == 'F0'); f6 = next(v for v in V if v['id'] == 'F6'); f6c = next(v for v in V if v['id'] == 'F6-COUPLED')
    G.append(dict(id='R16-0', name='Engine 1.5 reproduced', status='PASS', value=f"intercept {R['geometry']['ladder'][max(R['geometry']['ladder'], key=int)]['intercepted']:.3f}; "
             f"photons {R['sources']['photon_share_range'][0]:.3f}-{R['sources']['photon_share_range'][1]:.3f}; F0 {f0['ratio'][0]:.0f}x (1.5: "
             f"{R['thermal']['cases']['LOW']['RADIATION_low']['ratio']:.0f}x); best conventional {R['combined']['vs_capacity'][0]:.0f}x; SR-1 "
             f"{R['gap']['cold_shielded']['photon_share_needed']:.2%}"))
    th = F['targets']['throat']; nom = th['cases'][f"{c['liner_section_m'][NOM]:g}"]
    G.append(dict(id='R16-1', name='Fiji constitutive model', status='PASS_BOUNDED', value='M(T, H, S) bounded by mu0 Ms_max, zero without seed, '
             'hysteretic, collapses at quench and beyond the strain limit; inverse magnetocaloric; no energy created'))
    bn = F['targets']['burn']; bc = bn['cases'][f"{c['liner_section_m'][NOM]:g}"]; sh = bn['shell'][f"{max(c['bound_outer_m']):g}"]
    G.append(dict(id='R16-2', name='Fiji field', status='CANON_CONFLICT', value=f"liners add {bc['B_fiji_T'][OPT]*1e3:.0f} mT at the burn point (coils "
             f"{abs(bn['B_coil_T']):.2f} T) at the atomic-moment bound (mu0 Ms {c['mu0_Ms_T'][OPT]} T); the canon law ({c['canon_seed_T']:g} T x {F['canon_A_B']:.1f} = "
             f"{F['canon_field']['B_T']:.0f} T) needs mu0 Ms {bc['mu0Ms_for_canon_T']:.0e} T in these liners, and {sh['mu0Ms_for_canon_T']:.0f} T "
             f"({sh['mu0Ms_for_canon_T']/c['mu0_Ms_T'][OPT]:.0f}x the bound) even in a solid 2-{max(c['bound_outer_m']):g} m shell around the burn"))
    G.append(dict(id='R16-3', name='Lattice survival', status='FAIL', value=f"inboard photon flux {A['inboard_flux_W_m2'][0]:.1e}-{A['inboard_flux_W_m2'][1]:.1e} W/m2, "
             f"{A['vs_armour'][0]:.0f}-{A['vs_armour'][1]:.0f}x what a cooled 5 mm W face passes; a cooled 5 mm Fiji skin would rise "
             f"{A['temperature_rise_K'][0]:.1e}-{A['temperature_rise_K'][1]:.1e} K against a {A['collapse_margin_K']:.0f} K margin to quench: the lattice collapses in line of sight of the burn"))
    worst = next(r for r in Rb['rows'] if r['coil'] == Rb['worst'])
    G.append(dict(id='R16-4', name='REBCO margin and fluence', status='FAIL', value=f"Jc margin {min(min(r['margin']) for r in Rb['rows']):.1f}x or more at <= "
             f"{max(r['B_peak_T'] for r in Rb['rows']):.1f} T (not limiting); fast-neutron fluence at {Rb['worst']} reaches the limit in "
             f"{worst['lifetime_s'][PES]:.0f}-{worst['lifetime_s'][OPT]:.0f} s against a {c['burn_time_s']/86400:.1f} d burn: attenuation {Rb['attenuation_needed']:.0e} "
             f"(about {Rb['shield_m']:.1f} m of shield) needed"))
    bf = Fu['best_floor_polarized']; best = max((v for v in V if v['sr1_photon_share_needed']), key=lambda v: v['sr1_photon_share_needed'])
    G.append(dict(id='R16-5', name='Advanced fusion photon share', status='FAIL', value=f"floor {bf['photon_share']:.1%} at Ti {bf['Ti_keV']:.0f} keV "
             f"(polarized, channelled, Te/Ti {bf['Te_over_Ti']:.2f}); coupled burn {Fu['coupled'][2]['photon_share']:.1%}; the most any configuration allows is "
             f"{best['sr1_photon_share_needed']:.2%} ({best['id']}); with channeling or a Fiji liner the fixed loads alone exceed the radiator"))
    G.append(dict(id='R16-6', name='Radiation and thermal closure', status='FAIL', value=f"F6 needs {f6['ratio'][0]:.0f}x the radiator ({f6['ratio_without_overheads']:.0f}x without the channeling drive and liner losses; coupled burn {f6c['ratio'][0]:.0f}x); "
             f"F0 {f0['ratio'][0]:.0f}x; no candidate closes"))
    G.append(dict(id='R16-7', name='Architecture', status='KEPT', value='four independent engines, one reusable engine asset; no canon, geometry or deployed-engine change'))
    return G


def input_hash(s):
    blob = json.dumps([s['vertex_fiji'], s['vertex_radiation'], s['vertex_engine'], s['radiators']['temperature'], s['radiators']['emissivity'],
                       s['radiators']['effective_area']], sort_keys=True, default=str)
    here = Path(__file__).resolve().parent
    src = b''.join((here/f).read_bytes() for f in ('vertex_fiji.py', 'vertex_radiation.py', 'vertex_magnet.py', 'vertex_structure.py', 'material_physics.py'))
    mats = (ROOT/'data'/'materials'/'catalogue.toml').read_bytes()
    return hashlib.sha256(blob.encode()+src+mats+vr.EVIDENCE_PATH.read_bytes()).hexdigest()[:16]


def report(s):
    t0 = time.time(); c = config(s)
    F = fiji_field(s); A = assembly(s, F); Rb = rebco(s, F); Fu = fusion(s)
    V = variants(s, F, A, Rb, Fu)
    excess = max(0.0, next(v for v in V if v['id'] == 'F6')['ratio'][0]-1.0)*r15()['thermal']['capacity_W']*c['radiator_emissivity_nano']/s['radiators']['emissivity']['value']
    out = dict(version=c['version'], input_hash=input_hash(s), evidence=c['evidence'],
               model=dict(curve=curve(c), thermodynamics=[thermodynamics(c, k) for k in (OPT, NOM, PES)], canon_A_B_1000K=lattice_law(c, c['T_operating_K'])),
               field=F, assembly=A, rebco=Rb, fusion=Fu, materials=qualify(s), armour=armour(s), shielding=shielding(s), insulation=insulation(s),
               radiator=dict(emissivity=[s['radiators']['emissivity']['value'], c['radiator_emissivity_nano']],
                             capacity_gain=c['radiator_emissivity_nano']/s['radiators']['emissivity']['value']-1.0),
               hydrogen=dict(excess_W=excess, cases=hydrogen(s, excess)), variants=V, reconciliation=reconciliation())
    out['gates'] = gates(s, F, A, Rb, Fu, V)
    out['proposals'] = proposals(s, out)
    out['outcome'] = c['outcome']
    out['cost'] = dict(wall_s=time.time()-t0)
    return out


def evidence(s, path=EVIDENCE_PATH):
    R = report(s)
    path.write_text(json.dumps(R, indent=1, default=float)+'\n')
    return R


if __name__ == '__main__':
    import spec
    S = spec.load(ROOT)[0]
    R = evidence(S) if '--evidence' in sys.argv else report(S)
    for g in R['gates']:
        print(f"{g['id']:6} {g['status']:14} {g['name']}: {g['value']}")
    for v in R['variants']:
        print(f"{v['id']:10} photons {v['photon_share']:.4f}  ratio {v['ratio'][0]:10.1f} {v['ratio'][1]:12.1f}  SR-1 {v['sr1_photon_share_needed'] or 0:.2e}  {v['name']}")
