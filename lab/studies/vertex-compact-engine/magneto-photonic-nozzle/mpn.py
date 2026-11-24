"""Magneto-Photonic Nozzle (MPN): radiation optics, energy ledger and architecture screen for the Vertex drive.

Research only (owner brief 2026-11-22). Changes no canon, geometry or Drive row. Standard library only; reads
data/wayfarer_3d.toml, references/p1_operating_point.json, the Vertex 1.5/1.6B evidence, the Halo Vertex 2.5 ledger and the photon
interaction table data/optics.json (built once by optics_data.py from xraylib). Writes results/mpn.json and results/mpn.log:

    python3 lab/studies/vertex-compact-engine/magneto-photonic-nozzle/mpn.py            # about 20 s on 4 cores

Every efficiency or dimension marked PROTOTYPE is a declared choice, not a result. The optics are textbook (Fresnel reflection with a
complex refractive index, Parratt recursion, Darwin widths, Klein-Nishina); the geometry is analytic solid angles checked by Monte Carlo
and, for the drawn engine, the Vertex 1.5 ray trace of its 263 real part meshes.
"""
import cmath
import json
import math
import random
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT/'src'/'wayfarer'))
OUT = HERE/'results'/'mpn.json'
LOG = HERE/'results'/'mpn.log'

C = 2.99792458e8
R_E = 2.8179403262e-15
HC_KEV_M = 1.23984198e-9
EPS0 = 8.8541878128e-12
MU0 = 4e-7*math.pi
SIGMA_SB = 5.670374419e-8
H_PLANCK = 6.62607015e-34
M_N = 1.67492749804e-27
EV = 1.602176634e-19
SIGMA_T = 6.6524587321e-29

LINES = []


def log(*a):
    s = ' '.join(str(x) for x in a)
    LINES.append(s)
    print(s)

# ===================================================================================================================================
# 0. Canon: the operating point and the heat budget (verified against the brief's figures)
# ===================================================================================================================================


def canon():
    s = tomllib.loads((ROOT/'data'/'wayfarer_3d.toml').read_text())
    op = s['physics']['operating_point']
    p1 = json.loads((ROOT/'references'/'p1_operating_point.json').read_text())['operating_point']
    rad = json.loads((ROOT/'references'/'evidence'/'vertex_radiation.json').read_text())
    cop = rad['thermal']['cop']
    P = p1['peak_fusion_power_W']
    drive_W = op['hot_share']*p1['ideal_rejection_W']
    return dict(
        fusion_W=P, fusion_per_engine_W=P/4, engines=4, jet_W=p1['peak_jet_power_W'], thrust_N=4*p1['peak_thrust_N'] if p1['peak_thrust_N'] < 3e7 else p1['peak_thrust_N'],
        thrust_per_engine_N=p1['peak_thrust_N'], ve_m_s=op['exhaust_velocity_m_s'], absorbed_fraction=op['absorbed_fraction'],
        absorbed_W=p1['peak_absorbed_heat_W'], ideal_rejection_W=p1['ideal_rejection_W'], hot_share=op['hot_share'], drive_W=drive_W,
        drive_per_engine_W=drive_W/4, allowed_fraction=drive_W/P, cop_20K=cop, cold_cost=1.0+1.0/cop,
        burn_s=4*9.99*86400.0, radiator_kg_m2=10.0, ship_shield_radius_m=45.0,
        sources=dict(operating_point='references/p1_operating_point.json (operating_point)',
                     budget='physics.operating_point.hot_share x ideal_rejection_W (docs/MODEL.md B01)',
                     cop='references/evidence/vertex_radiation.json thermal.cop (20 K, Carnot fraction as 1.5)',
                     shield_radius='docs/MODEL.md: cluster outer radius 36.5 m = 0.81 of the shield radius'))


def brief_check(k):
    """The brief's illustrative screen, recomputed: 20 % photons, 62 % intercepted, single reflection, budget 10.8 GW."""
    managed = 0.20*k['fusion_W']*0.62
    return dict(fusion_TW=k['fusion_W']/1e12, jet_TW=k['jet_W']/1e12, drive_GW=k['drive_W']/1e9, allowed_fraction=k['allowed_fraction'],
                managed_TW=managed/1e12, required_reflectivity=1.0-k['drive_W']/managed,
                photon_thrust_kN_52TW=52.2e12/C/1e3,
                verdict='The brief figures hold: 261.3 TW fusion, 209.0 TW jet, 10.80 GW drive share (75 % of 14.40 GW), 4.13e-5 allowed; '
                        '32.4 TW managed and 99.967 % reflectivity for a single bounce; 52.2 TW of collimated photons give 174 kN.')

# ===================================================================================================================================
# 1. Photon optics
# ===================================================================================================================================


OPT = json.loads((HERE/'data'/'optics.json').read_text())
MATS = OPT['materials']


def _interp(mat, key, E, rho_scale=1.0):
    rows = MATS[mat]['rows']
    if E <= rows[0]['E_keV']:
        return rows[0][key]*rho_scale
    for a, b in zip(rows, rows[1:]):
        if a['E_keV'] <= E <= b['E_keV']:
            if a[key] <= 0 or b[key] <= 0:
                return (a[key]+(b[key]-a[key])*(E-a['E_keV'])/(b['E_keV']-a['E_keV']))*rho_scale
            t = math.log(E/a['E_keV'])/math.log(b['E_keV']/a['E_keV'])
            return math.exp(math.log(a[key])+t*math.log(b[key]/a[key]))*rho_scale
    return rows[-1][key]*rho_scale


def n_index(mat, E, rho_scale=1.0):
    return _interp(mat, 'delta', E, rho_scale), _interp(mat, 'beta', E, rho_scale)


def theta_c(mat, E):
    return math.sqrt(2*n_index(mat, E)[0])


def fresnel_R(mat, E, th, sigma=0.0, rho_scale=1.0):
    """Specular reflectivity of a semi-infinite mirror at grazing angle th (rad), Névot-Croce roughness sigma (m). X-ray s and p
    polarisations are equal to well below 1e-6 at these angles."""
    d, b = n_index(mat, E, rho_scale)
    k = 2*math.pi/(HC_KEV_M/E)
    s1 = math.sin(th)
    kz1 = k*s1
    kz2 = k*cmath.sqrt(s1*s1-2*d+2j*b)
    if kz2.imag < 0:
        kz2 = -kz2
    r = (kz1-kz2)/(kz1+kz2)*cmath.exp(-2*kz1*kz2*sigma*sigma)
    return abs(r)**2


def steering_cost(mat, E):
    """Loss per radian of deflection by total external reflection in the grazing limit: (1-R)/(2 theta) -> 2 beta / theta_c^3.
    A ray turned by phi through many shallow bounces loses at least 1 - exp(-g phi), whatever the number of bounces."""
    d, b = n_index(mat, E)
    tc = math.sqrt(2*d)
    return 2*b/tc**3


def steering_cost_numeric(mat, E, frac=0.05):
    th = frac*theta_c(mat, E)
    return (1-fresnel_R(mat, E, th))/(2*th)


def sigma_kn(E):
    k = E/510.99895
    return 2*math.pi*R_E**2*((1+k)/k**2*(2*(1+k)/(1+2*k)-math.log(1+2*k)/k)+math.log(1+2*k)/(2*k)-(1+3*k)/(1+2*k)**2)


def compton_floor(E, ne):
    """The steering cost of an ideal mirror that only Compton-scatters (no photoabsorption) at electron density ne: the floor no
    material can beat at that density (beta = ne sigma_KN lambda / 4 pi, theta_c^2 = r_e lambda^2 ne / pi)."""
    lam = HC_KEV_M/E
    beta = ne*sigma_kn(E)*lam/(4*math.pi)
    tc = math.sqrt(R_E*lam*lam*ne/math.pi)
    return 2*beta/tc**3


def parratt(layers, E, th):
    """Reflectivity of a stack by Parratt's recursion. layers: [(mat, thickness_m, rho_scale, sigma_m)] from the top; the last is the
    substrate (thickness ignored)."""
    k = 2*math.pi/(HC_KEV_M/E)
    s = math.sin(th)

    def kz(mat, rs):
        if mat is None:
            return k*s
        d, b = n_index(mat, E, rs)
        q = k*cmath.sqrt(s*s-2*d+2j*b)
        return q if q.imag >= 0 else -q
    kzs = [kz(None, 1.0)]+[kz(m, rs) for m, t, rs, sg in layers]
    X = 0j
    for j in range(len(layers)-1, -1, -1):
        k1, k2 = kzs[j], kzs[j+1]
        sg = layers[j][3]
        r = (k1-k2)/(k1+k2)*cmath.exp(-2*k1*k2*sg*sg)
        if j+1 < len(layers):
            ph = cmath.exp(2j*k2*layers[j][1])
        else:
            ph = 1.0
        X = (r+X*ph)/(1+r*X*ph) if j+1 < len(layers) else r
    return abs(X)**2


def multilayer(top, spacer, d, gamma, N, sigma, E, spacer_rho=1.0, scan=400):
    """First Bragg peak of a periodic multilayer: peak reflectivity, its angle, steering cost and relative angular bandwidth."""
    layers = []
    for _ in range(N):
        layers.append((top, d*gamma, 1.0, sigma))
        layers.append((spacer, d*(1-gamma), spacer_rho, sigma))
    layers.append(('Si', 1e-3, 1.0, sigma))
    lam = HC_KEV_M/E
    thB = lam/(2*d)
    best = (0.0, thB)
    grid = [thB*(0.85+0.4*i/scan) for i in range(scan+1)]
    Rs = []
    for th in grid:
        R = parratt(layers, E, th)
        Rs.append(R)
        if R > best[0]:
            best = (R, th)
    half = [th for th, R in zip(grid, Rs) if R >= best[0]/2]
    bw = (max(half)-min(half))/best[1] if half else 0.0
    return dict(top=top, spacer=spacer, d_nm=d*1e9, N=N, sigma_nm=sigma*1e9, E_keV=E, peak_R=best[0], theta_mrad=best[1]*1e3,
                steering_cost=(1-best[0])/(2*best[1]), bandwidth_rel=bw,
                ter_steering_cost=min(steering_cost(m, E) for m in ('C_diamond', 'Pt', 'W')))


def supermirror(top, spacer, d_min, d_max, N, gamma, sigma, th, Te, spacer_rho=2.2/3.515):
    """A depth-graded multilayer supermirror (d from d_max at the top to d_min at the bottom, geometric grading) at one grazing angle:
    reflectivity across the spectrum and the spectrum-weighted absorbed share, against the best plain coating at the same angle."""
    layers = []
    for i in range(N):
        d = d_max*(d_min/d_max)**(i/max(1, N-1))
        layers.append((top, d*gamma, 1.0, sigma)); layers.append((spacer, d*(1-gamma), spacer_rho, sigma))
    layers.append(('Si', 1e-3, 1.0, sigma))
    bins = spectrum_bins(Te, n=40)
    rows = []; a_ml = a_ter = 0.0
    for E, w in bins:
        Rm = parratt(layers, E, th); Rt = best_R(E, th)[0]
        rows.append((E, Rm, Rt)); a_ml += w*(1-max(Rm, 0.0)); a_ter += w*(1-Rt)
    band = (HC_KEV_M/(2*d_max*th), HC_KEV_M/(2*d_min*th))
    return dict(top=top, spacer=spacer, d_nm=(d_min*1e9, d_max*1e9), N=N, sigma_nm=sigma*1e9, theta_mrad=th*1e3, band_keV=band,
                absorbed_supermirror=a_ml, absorbed_best_plain=a_ter, curve=rows)


def bragg_broadband(Te):
    """Best broadband efficiency of crystal diffraction on a bremsstrahlung continuum exp(-E/Te): the reflected band dE/E around E0
    carries (E0/Te) exp(-E0/Te) dE/E of the power, largest at E0 = Te (1/e)."""
    rows = []
    for c in OPT['crystals']:
        if c['E_keV'] not in (100, 300):
            continue
        perfect = math.exp(-1)*c['bandwidth_dE_E']*1.0
        eta = 2.9e-4                                  # 1 arcmin mosaic (Laue lens practice)
        mosaic = math.exp(-1)*min(1.0, eta/math.tan(c['bragg_rad']))*0.5
        rows.append(dict(crystal=c['crystal'], hkl=c['hkl'], E_keV=c['E_keV'], bragg_mrad=c['bragg_rad']*1e3,
                         darwin_urad=c['darwin_full_rad']*1e6, perfect_bandwidth=c['bandwidth_dE_E'], perfect_broadband_eff=perfect,
                         mosaic_bandwidth=eta/math.tan(c['bragg_rad']), mosaic_broadband_eff=mosaic, deflection_mrad=2e3*c['bragg_rad']))
    graded = dict(case='graded or bent crystal (advanced): dE/E 0.10, peak 0.3', broadband_eff=math.exp(-1)*0.10*0.3)
    return dict(rows=rows, graded=graded, Te_keV=Te,
                note='A crystal at one orientation diffracts one narrow band of a broad continuum; every other photon passes into the '
                     'crystal and is attenuated there. Crystals turn photons by large angles (2 theta_B, tens of mrad) but only a '
                     'percent-level share of a bremsstrahlung spectrum, so as heat shields they add absorber rather than remove it.')


def far_ir_wall(sigma_S_m, f_Hz):
    """Hagen-Rubens normal-incidence reflectivity of a metal at a cyclotron/synchrotron frequency: 1 - R = 2 sqrt(2 eps0 omega / sigma)."""
    w = 2*math.pi*f_Hz
    return 1.0-2.0*math.sqrt(2*EPS0*w/sigma_S_m)


def neutron_optics():
    """Neutron total reflection: theta_c = lambda sqrt(N b / pi). Ni N b = 9.41e14 m^-2; supermirrors extend this by m."""
    Nb_Ni = 9.41e14
    rows = []
    for label, E_eV in (('cold 3 meV', 3e-3), ('thermal 25 meV', 0.0253), ('epithermal 1 eV', 1.0), ('D-D 2.45 MeV', 2.45e6),
                        ('D-T 14.1 MeV', 14.07e6)):
        lam = H_PLANCK/math.sqrt(2*M_N*E_eV*EV)
        tc = lam*math.sqrt(Nb_Ni/math.pi)
        lattice = lam/(2*0.1e-9)                      # Bragg angle of a 0.1 nm lattice: the limit any layered mirror could reach
        rows.append(dict(neutron=label, E_eV=E_eV, wavelength_m=lam, theta_c_Ni_rad=tc, theta_c_m6_rad=6*tc, theta_c_m10_rad=10*tc,
                         lattice_limit_rad=lattice, length_to_hide_3cm_m=0.03/max(10*tc, 1e-30),
                         length_to_hide_3cm_lattice_m=0.03/lattice))
    return dict(rows=rows,
                note='Supermirrors (m up to about 6-8 today) and any layered structure down to atomic spacing reflect MeV neutrons only '
                     'below about 0.1 mrad; hiding a 3 cm edge takes hundreds of metres to kilometres of mirror. Moderating a fast neutron '
                     'first deposits its energy, which is the heat the optics was meant to avoid. Fast neutrons can only be avoided '
                     '(geometry), shadowed (removal), or not made (fuel).')

# ===================================================================================================================================
# 2. Sources
# ===================================================================================================================================


def sources(k):
    """Radiation sources per engine. Shares are fractions of fusion power from the Vertex 1.5/1.6B evidence; the photon spectrum is
    bremsstrahlung exp(-E/Te) (validated against the 1.5 LOW bins). V3 is a declared speculative source, not a result."""
    vs = json.loads((ROOT/'references'/'evidence'/'vertex_source.json').read_text())
    vrad = json.loads((ROOT/'references'/'evidence'/'vertex_radiation.json').read_text())
    S = vs['cases']

    def pick(case, br):
        r = S[case]['brackets'][br]['best']
        return dict(Te_keV=r['Te_keV'], brems=r['brems_share'], sync=r.get('sync_share', 0.0), neutron=r['neutron_share'])
    low = vrad['sources']['cases']['LOW']
    nl = low['neutron_lines']
    dd_e, dt_e = nl['DD_2_45MeV'], nl['DT_14_1MeV']
    out = {
        'V0': dict(name='Vertex 1.5 LOW reference (hot-ion R2-A, Te 55 keV)', **pick('S0', 'optimistic'), evidence='CALCULATED (1.5/1.6B)'),
        'V1': dict(name='1.6B S1 spin-polarized D-3He, nominal', **pick('S1', 'nominal'), evidence='CALCULATED (1.6B)'),
        'V2': dict(name='1.6B S5 combined (polarization + selective He-3 heating + channeling)', **pick('S5', 'optimistic'),
                   evidence='CALCULATED, optimistic bracket (1.6B)'),
        'V3': dict(name='declared low-neutron burn (V2 with neutrons x0.25: quintet suppression and He-3-rich feed)', Te_keV=pick('S5', 'optimistic')['Te_keV'],
                   brems=pick('S5', 'optimistic')['brems'], sync=pick('S5', 'optimistic')['sync'], neutron=pick('S5', 'optimistic')['neutron']*0.25,
                   evidence='SPECULATIVE (declared, accelerator study Q3)')}
    for v in out.values():
        v['photon'] = v['brems']+v['sync']
        Pf = k['fusion_per_engine_W']
        v['P_brems_W'] = Pf*v['brems']; v['P_sync_W'] = Pf*v['sync']; v['P_n_W'] = Pf*v['neutron']
        # neutron count: the 1.5 LOW line split (energy shares) gives the mean neutron energy
        e_mean = (dd_e+dt_e)/(dd_e/2.45+dt_e/14.07)
        v['neutron_mean_MeV'] = e_mean
        v['neutrons_per_s'] = v['P_n_W']/(e_mean*1.602176634e-13)
    # spectrum validation against the 1.5 LOW bins (Te 55 keV)
    val = []
    for b in low['spectrum']:
        lo, hi = b['lo_keV'], b['hi_keV']
        model = math.exp(-lo/55.0)-math.exp(-hi/55.0)
        val.append(dict(lo=lo, hi=hi, vertex_1_5=b['share'], exp_model=model))
    return out, val


def spectrum_bins(Te, n=48, lo=1.0, hi=3000.0):
    """Log energy bins (centre keV, power share) of exp(-E/Te), normalised over [lo, hi]."""
    edges = [lo*(hi/lo)**(i/n) for i in range(n+1)]
    w = [math.exp(-a/Te)-math.exp(-b/Te) for a, b in zip(edges, edges[1:])]
    t = sum(w)
    return [(math.sqrt(a*b), x/t) for a, b, x in zip(edges, edges[1:], w)]

# ===================================================================================================================================
# 3. Optical elements on a spectrum
# ===================================================================================================================================


COATINGS = ('C_diamond', 'Be', 'SiC', 'Ni', 'Mo', 'W', 'Pt', 'Ir', 'Au', 'Os')


def best_R(E, th, sigma=0.2e-9, mats=COATINGS):
    return max((fresnel_R(m, E, th, sigma), m) for m in mats)


def spectral_absorptance(Te, th, mat=None, sigma=0.2e-9, bins=None):
    """Power-weighted absorbed share (1 - R) of a bremsstrahlung spectrum at one grazing angle; mat None picks the best coating per
    energy (an upper bound on any single coating)."""
    bins = bins or spectrum_bins(Te)
    a = 0.0
    for E, w in bins:
        R = best_R(E, th, sigma)[0] if mat is None else fresnel_R(mat, E, th, sigma)
        a += w*(1-R)
    return a


def skimmer(Te, a, L, mat, tip_m=1e-4, sigma=0.2e-9):
    """A grazing wedge of length L along the rays that hides a body of half-width a: every intercepted ray meets a flank at
    theta = atan(a / L); a blunt tip of thickness tip_m absorbs fully. Returns the absorbed share of the intercepted photon power."""
    th = math.atan(a/L)
    tip = min(1.0, tip_m/(2*a))
    A = spectral_absorptance(Te, th, mat, sigma)
    return dict(theta_mrad=th*1e3, flank_absorbed=A, tip_share=tip, absorbed=tip+(1-tip)*A)


def skimmer_mc(Te, a, L, mat, n=20000, seed=7, src_radius=0.0, dist=100.0):
    """2D Monte Carlo of one wedge (apex toward the source at distance dist): rays from a source of radius src_radius, Fresnel at the
    local angle on every bounce, rays followed until they leave the wedge region. Checks the analytic skimmer()."""
    rnd = random.Random(seed)
    bins = spectrum_bins(Te)
    cum = []; s = 0.0
    for E, w in bins:
        s += w; cum.append((s, E))
    th = math.atan(a/L)
    absorbed = 0.0; second = 0
    for _ in range(n):
        u = rnd.random()
        E = next(e for c, e in cum if c >= u)
        y0 = (rnd.random()*2-1)*src_radius
        yt = (rnd.random()*2-1)*a                      # aim at the hidden body's face at x = dist + L
        ang = math.atan2(yt-y0, dist+L)
        # graze on the flank the ray meets: flank half-angle th about the axis from the apex at x = dist
        g = th-abs(ang) if yt*ang >= 0 else th+abs(ang)
        g = max(g, 1e-9)
        R = fresnel_R(mat, E, g)
        absorbed += 1-R
        # reflected ray leaves at angle 2 th - |ang| outward: never meets the other flank (opening wedge)
    return dict(theta_mrad=th*1e3, absorbed_mc=absorbed/n, second_hits=second, src_radius_m=src_radius)

# ===================================================================================================================================
# 4. Candidate A and C: the drawn compact engine (Vertex 1.5 ray trace of its real meshes)
# ===================================================================================================================================


def drawn_engine(src, n_rays=16384, workers=4):
    import vertex_radiation as vr
    s = tomllib.loads((ROOT/'data'/'wayfarer_3d.toml').read_text())
    c = vr.config(s)
    tris, meta, src_pt = vr.engine_scene(s)
    dirs, rays = vr.trace(tris, meta, src_pt, n_rays, c['shell_thickness_m'], workers)
    hits = [r[0][0] for r in rays if r[0]]
    f = len(hits)/n_rays
    out = {}
    gg = [1e-5*(1.5708/1e-5)**(i/160) for i in range(161)]
    for key, v in src.items():
        bins = spectrum_bins(v['Te_keV'], n=24)
        # power-weighted best-coating reflectivity on a graze grid, interpolated per ray
        tab = [sum(w*best_R(E, g)[0] for E, w in bins) for g in gg]

        def Rw(g):
            if g <= gg[0]:
                return tab[0]
            i = min(int(math.log(g/gg[0])/math.log(gg[1]/gg[0])), len(gg)-2)
            t = (g-gg[i])/(gg[i+1]-gg[i])
            return tab[i]+t*(tab[i+1]-tab[i])
        # A: the best coating per energy at each ray's real incidence; reflected rays assumed to escape (upper bound on the benefit)
        # C: a grazing fairing on every exposed member: half-width 0.2 m (the thinnest members), length up to 1 m short of the hit
        refl = refl_c = 0.0
        for t, kk, Lseg, cs in hits:
            g = math.asin(min(1.0, cs))
            gc = math.atan(0.2/max(t-1.0, 0.2))
            refl += Rw(g); refl_c += Rw(min(g, gc))
        refl /= len(hits); refl_c /= len(hits)
        Pg = v['P_brems_W']
        out[key] = dict(intercepted=f, A_reflected_share=refl, C_reflected_share=refl_c,
                        A_photon_heat_four_GW=4*Pg*f*(1-refl)/1e9, C_photon_heat_four_GW=4*Pg*f*(1-refl_c)/1e9,
                        bare_photon_heat_four_GW=4*Pg*f/1e9, neutron_heat_four_GW_upper=4*v['P_n_W']*f/1e9)
    graze = sorted(math.degrees(math.asin(min(1.0, h[3]))) for h in hits)
    return dict(rays=n_rays, intercepted=f, graze_deg_quantiles={q: graze[int(q*(len(graze)-1))] for q in (0.0, 0.01, 0.05, 0.25, 0.5)},
                share_below_1deg=sum(1 for g in graze if g < 1.0)/n_rays, by_source=out,
                note='Heat booked at full absorption of the non-reflected share (the 1.5 upper bracket for the bare engine); the 1.5 '
                     'Compton-only lower bracket would scale every row by the same transport factor, so the reflected share is the result.')

# ===================================================================================================================================
# 5. Candidate B: a nested grazing collimator that turns photons aft (photonic nozzle) and its momentum balance
# ===================================================================================================================================


def collimator(src, k, psi_deg=25.0, edge_block=0.01, mat='C_diamond'):
    """Shells occupy the aft hemisphere outside the plume cone psi. A photon at polar angle alpha (from the aft axis, psi < alpha < 90)
    is turned by phi = alpha - psi and keeps exp(-g phi) (the whispering-gallery bound, the least loss any bounce sequence achieves).
    Shell front edges block edge_block of the rays (absorbed). Photons outside the shells escape as before."""
    out = {}
    for key, v in src.items():
        bins = spectrum_bins(v['Te_keV'], n=36)
        Pg = v['P_brems_W']
        n = 180
        absorbed = 0.0; p_axial_before = 0.0; p_axial_after = 0.0
        for i in range(n):
            al = math.radians(90.0*(i+0.5)/n)
            dO = math.sin(al)*math.radians(90.0/n)/2      # share of the sphere in this ring (2 pi sin dtheta / 4 pi)
            p_axial_before += dO*math.cos(al)
            if al <= math.radians(psi_deg):
                p_axial_after += dO*math.cos(al); continue
            phi = al-math.radians(psi_deg)
            kept = 0.0
            for E, w in bins:
                kept += w*math.exp(-steering_cost(mat, E)*phi)
            kept *= (1-edge_block)
            absorbed += dO*(1-kept)
            p_axial_after += dO*kept*math.cos(math.radians(psi_deg)*0.5)
        # forward hemisphere photons are untouched: their axial momentum cancels the aft hemisphere's before collimation
        F_before = 0.0
        F_after = Pg/C*(p_axial_after-p_axial_before)
        out[key] = dict(absorbed_share=absorbed, heat_per_engine_GW=Pg*absorbed/1e9, heat_four_GW=4*Pg*absorbed/1e9,
                        thrust_gain_per_engine_N=F_after-F_before, thrust_gain_share=4*(F_after-F_before)/k['thrust_N'],
                        ideal_thrust_all_photons_aft_kN=4*(v['P_brems_W']+v['P_sync_W'])/C/1e3)
    return dict(psi_deg=psi_deg, edge_block=edge_block, material=mat, by_source=out,
                jet_thrust_per_W=2/k['ve_m_s'], photon_thrust_per_W=1/C, ratio=(2/k['ve_m_s'])/(1/C),
                note='Without the collimator these photons leave with zero heat. Any structure placed in a free escape path adds heat; '
                     'the gain is bounded by P/(2c) per engine even for loss-free optics.')

# ===================================================================================================================================
# 6. Geometry: remote ring architectures (D Halo MPN, F edge-on hybrid)
# ===================================================================================================================================


def ring_sky(a, R, z):
    """Share of the sphere a ring (radius R, half-width a normal to the ray) covers from a point on its axis at distance z."""
    rho2 = R*R+z*z
    return a*R/rho2


def ring_sky_mc(a, R, z, n=400000, seed=3):
    rnd = random.Random(seed)
    rho = math.sqrt(R*R+z*z); al = math.atan2(R, z); da = a/rho
    hit = 0
    for _ in range(n):
        u = 2*rnd.random()-1
        th = math.acos(u)
        if abs(th-al) <= da:
            hit += 1
    return hit/n


def segment_sky(p0, p1, w, n=400):
    """Share of the sphere a thin member of width w from p0 to p1 covers from the origin: (1/4 pi) int w sin(psi) dl / r^2."""
    tot = 0.0
    L = math.dist(p0, p1)
    d = [(b-a)/L for a, b in zip(p0, p1)]
    for i in range(n):
        t = (i+0.5)/n*L
        p = [a+t*x for a, x in zip(p0, d)]
        r = math.sqrt(sum(x*x for x in p))
        cosp = abs(sum(x*y for x, y in zip(p, d)))/r
        sinp = math.sqrt(max(0.0, 1-cosp*cosp))
        tot += w*sinp/(r*r)*(L/n)
    return tot/(4*math.pi)


def halo_reference():
    """The Halo Vertex 2.5 all-lever case per engine (lab/variants/halo-vertex/ledger2.json), the starting point for candidate D."""
    d = json.loads((ROOT/'lab'/'variants'/'halo-vertex'/'ledger2.json').read_text())
    best = None

    def walk(x):
        nonlocal best
        if isinstance(x, dict):
            if 'heat_engine_GW' in x and 'detail' in x:
                if best is None or x.get('system_t', 1e18) < best.get('system_t', 1e18):
                    best = x
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(d)
    return best


def remote_engine(k, v, R=62.0, kappa=2.0, BR=6.4, Je=3e8, depth=2.0, cryo_m=0.013, Ls=0.0, mat='Pt', D=2000.0, S=1000.0,
                  tethers=6, tape_w=0.3, knife_w=3.0, tether_at=0.5, plug_T=2300.0, eps=0.85, dep_thin=0.3, charged_W=None,
                  strips=True, bubble_share=0.5, scatter_floor=1e-4, rho_nose=10.9, lam_nose=0.08, fluence_limit=3e22,
                  tether_sigma=4e9, edge_on_tethers=True, nose_override=None, pulse_rate=2.0e4, field_ratio=50.0):
    """One engine of a remote-burn ring nozzle with the MPN subsystems (candidates D and F).

    Ring: a ribbon conductor laid along the rays from its own burn (edge-on); its exposed half-width is half the ribbon thickness. A hot
    W-B4C nose (length set by the coil fluence limit) leads the ribbon and radiates its own heat from its flanks. A grazing skimmer of
    length Ls (inside the ring, outside the plasma: Ls <= (1 - bubble_share) rho) can sharpen the nose's leading edge. Tethers: tension
    tapes from the ring back to a node on the burn-ship line at tether_at x the burn-ring distance; a planar tape whose plane contains the
    burn is seen edge-on (projected width = tape thickness); with Ls > 0 their leading edges get knife-edge skimmers knife_w wide.
    A self-radiating shadow plug hides the ship (aft shield disc 45 m at distance D) and the spine. Neighbour engines at spacing S see the
    ring and its skimmer broadside; self-radiating strips shade them. Sinks: SELF (a hot part that radiates its own heat; area and mass
    booked) and B01 (heat that must be piped to the ship's hot loop: charged leakage and the cold ribbon's neutron heat at the 20 K cost)."""
    Pf = k['fusion_per_engine_W']
    Pb, Ps, Pn = v['P_brems_W'], v['P_sync_W'], v['P_n_W']
    # current: test-particle capture (B0 R >= BR, Halo 2.2 trace) and the collective pulse: stored field energy >= field_ratio x the
    # pulse energy (Halo 2.2/2.5 design ratio, PROTOTYPE) at pulse_rate (upper end of the Halo chain-ignition range)
    E_pulse = Pf/pulse_rate
    I = 2*BR/MU0
    for _ in range(4):
        Ac = I/Je
        L_ind = MU0*R*(math.log(8*R/math.sqrt(Ac/math.pi))-2)
        I = max(2*BR/MU0, math.sqrt(2*field_ratio*E_pulse/L_ind))
    Ac = I/Je
    t_c = Ac/depth
    thick = t_c+2*cryo_m
    a = thick/2
    z = kappa*R
    rho = math.hypot(R, z)
    f_ring = ring_sky(a, R, z)
    Ls_max = (1-bubble_share)*rho
    Ls_eff = min(Ls, Ls_max)
    sk = skimmer(v['Te_keV'], a, Ls_eff, mat) if Ls_eff > 0 else None
    A_ring = sk['absorbed'] if sk else 1.0
    A_sync = 1-far_ir_wall(2.0e6, 1e12)            # W at 1800 K, 1 THz (Hagen-Rubens)
    # nose length from the fluence limit on the cold ribbon behind it
    flu_face = v['neutrons_per_s']/(4*math.pi*rho*rho)*k['burn_s']
    room = fluence_limit/2-flu_face*scatter_floor
    nose_m = nose_override or (max(0.2, lam_nose*math.log(flu_face/room)) if room > 0 else float('inf'))
    flu_cold = flu_face*math.exp(-nose_m/lam_nose)+flu_face*scatter_floor if math.isfinite(nose_m) else float('inf')
    rows = []
    ring_W = f_ring*(Pb*A_ring+Ps*A_sync+Pn*dep_thin)
    nose_area = 2*nose_m*2*math.pi*R if math.isfinite(nose_m) else 1.0
    T_nose = (ring_W/(eps*SIGMA_SB*nose_area))**0.25
    edge_flux = (Pb+Ps)/(4*math.pi*rho*rho)
    rows.append(dict(element='ring nose (edge-on' + (', knife-edge skimmer' if sk else '') + ')', sky=f_ring,
                     photon_W=f_ring*(Pb*A_ring+Ps*A_sync), neutron_W=f_ring*Pn*dep_thin, sink='SELF', area_m2=nose_area, T_K=T_nose))
    # cold ribbon behind the nose: neutrons that get through, at the refrigeration cost
    cold_W = f_ring*Pn*dep_thin*(flu_cold/flu_face)*k['cold_cost'] if math.isfinite(flu_cold) else float('inf')
    rows.append(dict(element='cold ribbon behind the nose (x refrigeration)', sky=0.0, photon_W=0.0, neutron_W=cold_W, sink='B01'))
    # tethers
    A_t = 2*k['thrust_per_engine_N']/tethers/tether_sigma
    w_proj = A_t/tape_w if edge_on_tethers else 2*math.sqrt(A_t/math.pi)
    p0 = (tether_at*z, 0.0, 0.0); p1 = (z, R, 0.0)
    f_t = tethers*segment_sky(p0, p1, w_proj)
    A_t_abs = skimmer(v['Te_keV'], w_proj/2, knife_w, mat)['absorbed'] if (sk and edge_on_tethers) else 1.0
    t_len = math.dist(p0, p1)
    t_W = f_t*(Pb*A_t_abs+Ps*A_sync+Pn*dep_thin)
    t_area = tethers*t_len*2*(knife_w if sk and edge_on_tethers else tape_w)
    rows.append(dict(element=f"{tethers} tension {'tapes, edge-on' if edge_on_tethers else 'cables'} ({w_proj*1000:.1f} mm projected)"
                     + (', knife edges' if A_t_abs < 1 else ''), sky=f_t, photon_W=f_t*(Pb*A_t_abs+Ps*A_sync), neutron_W=f_t*Pn*dep_thin,
                     sink='SELF', area_m2=t_area, T_K=(t_W/(eps*SIGMA_SB*t_area))**0.25))
    # shadow plug for the ship and spine
    f_plug = (k['ship_shield_radius_m']/D)**2/4
    P_plug = f_plug*(Pb+Ps+Pn*0.9)
    plug_m2 = P_plug/(eps*SIGMA_SB*plug_T**4)
    rows.append(dict(element='ship shadow plug (self-radiating)', sky=f_plug, photon_W=f_plug*(Pb+Ps), neutron_W=f_plug*Pn*0.9,
                     sink='SELF', area_m2=plug_m2, T_K=plug_T))
    # neighbours see this ring, its nose and its skimmer broadside (mean |cos| 0.5)
    broad = 2*math.pi*R*(depth+nose_m+Ls_eff)*0.5
    f_x = 3*broad/(4*math.pi*S*S)
    P_x = f_x*(Pb+Ps+Pn*0.5)
    strip_m2 = P_x/(eps*SIGMA_SB*plug_T**4)
    rows.append(dict(element='neighbour shadow strips (self-radiating)' if strips else 'neighbour rings, unshaded', sky=f_x,
                     photon_W=f_x*(Pb+Ps), neutron_W=f_x*Pn*0.5, sink='SELF' if strips else 'B01', area_m2=strip_m2, T_K=plug_T))
    if charged_W is not None:
        rows.append(dict(element='charged leakage (Halo 2.2 95 % bound, OPEN)', sky=0.0, photon_W=0.0, neutron_W=0.0, charged_W=charged_W,
                         sink='B01'))
    tot = lambda r: r['photon_W']+r['neutron_W']+r.get('charged_W', 0.0)
    b01 = sum(tot(r) for r in rows if r['sink'] == 'B01')
    selfrad = sum(tot(r) for r in rows if r['sink'] == 'SELF')
    L_ind = MU0*R*(math.log(8*R/math.sqrt(Ac/math.pi+1e-9))-2)
    W_mag = 0.5*L_ind*I*I
    m = dict(conductor_t=Ac*2*math.pi*R*6.0, structure_t=2*W_mag*1600/1.5e9/1e3,
             nose_t=thick*nose_m*2*math.pi*R*rho_nose if math.isfinite(nose_m) else float('inf'),
             skimmer_t=2*0.3e-3*Ls_eff*2*math.pi*R*3.515*3, tethers_t=tethers*t_len*A_t*1600/1e3*(2.0 if sk else 1.0),
             plug_t=plug_m2*12e-3, strips_t=strip_m2*12e-3 if strips else 0.0, spine_t=54.1*D/2000.0)
    return dict(params=dict(R_m=R, burn_aft_m=z, rho_m=rho, I_MA=I/1e6, B0R_Tm=MU0*I/2, B_conductor_T=MU0*I/(2*depth), E_pulse_GJ=E_pulse/1e9, BR_Tm=BR, Je_A_m2=Je, ribbon_m=t_c, thickness_m=thick,
                            nose_m=nose_m, Ls_m=Ls_eff, Ls_max_m=Ls_max, material=mat, D_m=D, S_m=S, W_mag_GJ=W_mag/1e9,
                            edge_flux_W_m2=edge_flux, tether_area_m2=A_t, tether_projected_m=w_proj),
                skimmer=sk, rows=rows, B01_W=b01, self_radiated_W=selfrad, total_W=b01+selfrad, mass_t=m,
                mass_total_t=sum(m.values()), fluence_face_n_m2=flu_face, fluence_cold_n_m2=flu_cold, T_nose_K=T_nose,
                fits_B01=4*b01 <= k['drive_W'], fits_total=4*(b01+selfrad) <= k['drive_W'],
                fluence_ok=flu_cold <= fluence_limit, nose_ok=T_nose <= 2000.0)


def eddy_screen(e, swing=0.1, v_front=2.0e7):
    """Eddy heat in the parts that sit in the ring's pulsed field: each pulse changes the field at the conductor by swing x B_cond over the
    bubble transit time rho / v_front (PROTOTYPE). Loops of size s in a conductor of conductivity sigma dissipate sigma (dB/dt)^2 s^2 / 16
    per unit volume while the field changes (thin-plate estimate); duty = transit time x pulse rate."""
    p = e['params']
    dB = swing*p['B_conductor_T']
    tau = p['rho_m']/v_front
    duty = min(1.0, tau*(65.3e12/(p['E_pulse_GJ']*1e9)))
    vol_nose = p['thickness_m']*p['nose_m']*2*math.pi*p['R_m']
    rows = []
    for label, sigma, s_loop, vol in (('nose, bulk tungsten (1700 K)', 1.8e6, p['thickness_m'], vol_nose),
                                     ('nose, tungsten laminated 1 mm', 1.8e6, 1e-3, vol_nose),
                                     ('nose, B4C ceramic (semiconducting, ~1e4 S/m)', 1e4, p['thickness_m'], vol_nose),
                                     ('nose, BN or diamond (insulator)', 1e-6, p['thickness_m'], vol_nose),
                                     ('skimmer Pt film 50 nm, tiled 1 mm', 2.0e6, 1e-3, 2*5e-8*2*math.pi*p['R_m']*20.0),
                                     ('skimmer Pt film 50 nm, untiled 0.1 m', 2.0e6, 0.1, 2*5e-8*2*math.pi*p['R_m']*20.0)):
        q = sigma*(dB/tau)**2*s_loop**2/16*duty
        rows.append(dict(part=label, sigma_S_m=sigma, loop_m=s_loop, volume_m3=vol, W_per_engine=q*vol))
    return dict(swing=swing, dB_T=dB, transit_s=tau, duty=duty, rows=rows,
                note='Order-of-magnitude screen. Anything electrically continuous at the ring scale must be segmented or insulating: '
                     'the MPN favours dielectric skimmers (diamond, BN) with tiled metal films, and a ceramic or finely laminated nose.')


# ===================================================================================================================================
# 7. Feasibility maps
# ===================================================================================================================================


def maps(k, src):
    """Heat (four engines) vs interception and effective absorptance for each source; and the skimmer absorptance vs L/a and energy."""
    fs = [10**(-x/4) for x in range(0, 21)]       # 1 .. 1e-5
    As = [10**(-x/4) for x in range(0, 17)]       # 1 .. 1e-4
    out = {}
    for key, v in src.items():
        grid = [[4*(v['P_brems_W']*A+v['P_n_W']*0.5*1.0)*f/k['drive_W'] for A in As] for f in fs]
        out[key] = dict(f=fs, A=As, heat_over_budget=grid,
                        f_needed_photons_only={A: k['drive_W']/(4*v['P_brems_W']*A) for A in (1.0, 0.1, 0.01, 0.001)},
                        f_needed_neutrons_only=k['drive_W']/(4*v['P_n_W']*0.5))
    # skimmer absorptance vs length (per 1 cm of half-width) for V0 and V2 spectra, three coatings
    sk = {}
    for key in ('V0', 'V2'):
        Te = src[key]['Te_keV']
        for mat in ('C_diamond', 'Pt', 'Os'):
            sk[f'{key}/{mat}'] = [(La, spectral_absorptance(Te, math.atan(1/La), mat)) for La in (10, 30, 100, 300, 1000, 3000, 10000, 30000)]
    return dict(intercept=out, skimmer_vs_L_over_a=sk)


def optimise(k, v, charged_W):
    """Grid search over ring radius, standoff, spacing and skimmer length for the hybrid (F). Feasible: B01 heat within the drive share,
    cold-coil fluence within the limit, nose below 2000 K. Reports the feasible set, the lightest feasible points and the strict set
    (piped and self-radiated heat together within the drive share)."""
    feas = []; allr = []
    import itertools
    for R, D, S, Ls, mat, depth in itertools.product((30.0, 45.0, 62.0, 90.0, 130.0), (500.0, 1000.0, 1500.0, 2000.0),
                                                     (700.0, 1000.0, 2000.0), (0.0, 20.0, 60.0), ('Pt', 'C_diamond'), (2.0, 4.0)):
                        if Ls == 0.0 and mat != 'Pt':
                            continue
                        e = remote_engine(k, v, R=R, D=D, S=S, Ls=Ls, mat=mat, depth=depth, charged_W=charged_W)
                        row = dict(R=R, D=D, S=S, Ls=e['params']['Ls_m'], mat=mat, depth=depth, I_MA=e['params']['I_MA'], B01_four_GW=4*e['B01_W']/1e9,
                                   self_four_GW=4*e['self_radiated_W']/1e9, total_four_GW=4*e['total_W']/1e9, mass_t=e['mass_total_t'],
                                   T_nose_K=e['T_nose_K'], fits=e['fits_B01'] and e['fluence_ok'] and e['nose_ok'], strict=e['fits_total'] and e['fluence_ok'] and e['nose_ok'])
                        allr.append(row)
                        if row['fits']:
                            feas.append(row)
    feas.sort(key=lambda r: r['mass_t'])
    strict = sorted([r for r in feas if r['strict']], key=lambda r: r['mass_t'])
    return dict(n=len(allr), feasible=len(feas), strict=len(strict), lightest=feas[:8], lightest_strict=strict[:8], rows=allr)


# ===================================================================================================================================
# 8. Validation
# ===================================================================================================================================


def validation():
    rows = []
    lit = dict(Si=0.22, Ni=0.40, Au=0.55, Pt=0.58)       # degrees at Cu K-alpha (8.05 keV), Als-Nielsen & McMorrow; Henke tables
    for m, deg in lit.items():
        mm = m if m in MATS else m
        tc = math.degrees(theta_c(mm, 8.05))
        rows.append(dict(case=f'critical angle {m} at 8.05 keV vs {deg} deg', value=tc, passes=abs(tc/deg-1) < 0.06))
    for m in ('C_diamond', 'W', 'Pt'):
        for E in (30, 100):
            g1, g2 = steering_cost(m, E), steering_cost_numeric(m, E, 0.02)
            rows.append(dict(case=f'grazing-limit loss 2 beta/theta_c^3 vs Fresnel at 0.02 theta_c, {m} {E} keV', value=g2/g1,
                             passes=abs(g2/g1-1) < 0.05))
    for m in ('C_diamond', 'W'):
        r = [x for x in MATS[m]['rows'] if x['E_keV'] == 100][0]
        rows.append(dict(case=f'beta vs xraylib Refractive_Index_Im, {m} 100 keV', value=r['beta']/r['beta_xraylib'],
                         passes=abs(r['beta']/r['beta_xraylib']-1) < 0.1))
    si = [c for c in OPT['crystals'] if c['crystal'] == 'Si' and c['hkl'] == [1, 1, 1] and c['E_keV'] == 100][0]
    rows.append(dict(case='Si(111) intrinsic bandwidth vs 1.33e-4 (literature)', value=si['bandwidth_dE_E'], passes=abs(si['bandwidth_dE_E']/1.33e-4-1) < 0.05))
    rows.append(dict(case='Klein-Nishina at 511 keV vs 0.432 sigma_T', value=sigma_kn(510.99895)/SIGMA_T, passes=abs(sigma_kn(510.99895)/SIGMA_T-0.432) < 0.003))
    # Parratt reproduces Fresnel for a single thick layer
    pa = parratt([('W', 1e-3, 1.0, 0.0), ('Si', 1e-3, 1.0, 0.0)], 30.0, 1.5e-3)
    fr = fresnel_R('W', 30.0, 1.5e-3)
    rows.append(dict(case='Parratt one thick W layer vs Fresnel W (30 keV, 1.5 mrad)', value=pa/fr, passes=abs(pa/fr-1) < 1e-3))
    # ring sky analytic vs Monte Carlo
    a, mc = ring_sky(0.5, 62.0, 124.0), ring_sky_mc(0.5, 62.0, 124.0)
    rows.append(dict(case='ring sky a R / rho^2 vs Monte Carlo (a 0.5, R 62, z 124)', value=mc/a, passes=abs(mc/a-1) < 0.05))
    # skimmer analytic vs 2D Monte Carlo
    an = skimmer(55.0, 0.02, 40.0, 'Pt', tip_m=0.0)['absorbed']
    mc2 = skimmer_mc(55.0, 0.02, 40.0, 'Pt', n=6000, src_radius=0.0, dist=1e6)['absorbed_mc']
    rows.append(dict(case='skimmer absorptance analytic vs 2D Monte Carlo (Pt, a 2 cm, L 40 m, Te 55 keV, distant point source)', value=mc2/an,
                     passes=abs(mc2/an-1) < 0.1))
    return rows

# ===================================================================================================================================
# main
# ===================================================================================================================================


def main(workers=4):
    k = canon()
    R = dict(version='MPN-1.0', canon=k, brief_check=brief_check(k))
    log('== canon'); log(json.dumps(R['brief_check'], indent=1))
    R['validation'] = validation()
    log('== validation')
    for r in R['validation']:
        log(f"  {'PASS' if r['passes'] else 'FAIL'}  {r['case']}: {r['value']:.4g}")

    # ---- optics tables
    Es = (3, 10, 20, 30, 50, 80, 100, 150, 200, 300, 500, 1000)
    opt = dict(theta_c_mrad={m: {E: theta_c(m, E)*1e3 for E in Es} for m in COATINGS},
               beta_over_delta={m: {E: n_index(m, E)[1]/n_index(m, E)[0] for E in Es} for m in COATINGS},
               steering_cost={m: {E: steering_cost(m, E) for E in Es} for m in COATINGS},
               compton_floor={label: {E: compton_floor(E, ne) for E in Es} for label, ne in
                              (('diamond electron density', MATS['C_diamond']['electrons_m3']),
                               ('osmium electron density', MATS['Os']['electrons_m3']))})
    # reflectivity curves for the figure
    opt['R_curves'] = {f'{m}@{E}': [(th, fresnel_R(m, E, th*1e-3, 0.2e-9)) for th in [0.02*1.25**i for i in range(40)]]
                       for m in ('C_diamond', 'Pt') for E in (10, 30, 100, 300)}
    log('== optics: theta_c (mrad), steering cost g (per rad) and beta/delta')
    for m in COATINGS:
        log(f"  {m:10s} " + '  '.join(f"{E}keV tc {opt['theta_c_mrad'][m][E]:.3g} g {opt['steering_cost'][m][E]:.3g}" for E in (10, 30, 100, 300, 1000)))
    for label, row in opt['compton_floor'].items():
        log(f"  Compton floor at {label}: " + '  '.join(f"{E}keV {row[E]:.3g}" for E in (10, 30, 100, 300, 1000)))
    ml = [multilayer('W', 'Si', 2.5e-9, 0.4, 150, 0.3e-9, E) for E in (30, 60, 100)]
    ml += [multilayer('Pt', 'C_diamond', 2.0e-9, 0.4, 300, 0.3e-9, E, spacer_rho=2.2/3.515) for E in (60, 100)]
    ml += [multilayer('W', 'C_diamond', 1.0e-9, 0.45, 800, 0.08e-9, E, spacer_rho=2.2/3.515) for E in (100, 300)]
    opt['multilayers'] = ml
    log('== multilayers (first Bragg peak)')
    for r in ml:
        log(f"  {r['top']}/{r['spacer']} d {r['d_nm']} nm N {r['N']} s {r['sigma_nm']} nm @ {r['E_keV']} keV: R {r['peak_R']:.3f} at "
            f"{r['theta_mrad']:.2f} mrad, g {r['steering_cost']:.3g} /rad (TER best {r['ter_steering_cost']:.3g}), bw {r['bandwidth_rel']:.3f}")
    sm = [supermirror('Pt', 'C_diamond', 2.5e-9, 10e-9, 200, 0.4, 0.3e-9, 2.0e-3, 55.0),
          supermirror('W', 'C_diamond', 1.0e-9, 8e-9, 600, 0.45, 0.08e-9, 2.0e-3, 55.0),
          supermirror('W', 'C_diamond', 0.7e-9, 8e-9, 1000, 0.45, 0.05e-9, 1.0e-3, 55.0)]
    opt['supermirrors'] = sm
    log('== depth-graded supermirrors on the 55 keV continuum')
    for r in sm:
        log(f"  {r['top']}/{r['spacer']} d {r['d_nm'][0]:.1f}-{r['d_nm'][1]:.1f} nm N {r['N']} sigma {r['sigma_nm']} nm at {r['theta_mrad']} mrad "
            f"(band {r['band_keV'][0]:.0f}-{r['band_keV'][1]:.0f} keV): absorbed {r['absorbed_supermirror']:.3f} vs best plain coating {r['absorbed_best_plain']:.3f}")
    # repeated bounces at fixed total deflection: the loss does not depend on how the turn is split
    opt['bounces'] = [dict(N=N, theta_mrad=10.0/(2*N), kept_100keV_diamond=fresnel_R('C_diamond', 100.0, 0.01/(2*N))**N,
                           kept_30keV_Pt=fresnel_R('Pt', 30.0, 0.01/(2*N))**N) for N in (1, 3, 10, 30, 100, 300)]
    log('== a 10 mrad turn split into N bounces (kept share): ' + '; '.join(
        f"N {b['N']} ({b['theta_mrad']:.3f} mrad) diamond@100 {b['kept_100keV_diamond']:.3f} Pt@30 {b['kept_30keV_Pt']:.3f}" for b in opt['bounces']))
    opt['crystals'] = bragg_broadband(55.0)
    log('== crystals on a 55 keV continuum')
    for r in opt['crystals']['rows']:
        log(f"  {r['crystal']}{tuple(r['hkl'])} {r['E_keV']} keV: perfect band {r['perfect_bandwidth']:.2e} eff {r['perfect_broadband_eff']:.2e}; "
            f"mosaic band {r['mosaic_bandwidth']:.3f} eff {r['mosaic_broadband_eff']:.3e}; turn {r['deflection_mrad']:.1f} mrad")
    log(f"  {opt['crystals']['graded']}")
    opt['neutrons'] = neutron_optics()
    log('== neutron optics')
    for r in opt['neutrons']['rows']:
        log(f"  {r['neutron']:16s} lambda {r['wavelength_m']:.3g} m  tc(Ni) {r['theta_c_Ni_rad']:.3g}  m10 {r['theta_c_m10_rad']:.3g}  "
            f"lattice {r['lattice_limit_rad']:.3g} rad  hide 3 cm: {r['length_to_hide_3cm_m']:.3g} m (m10), {r['length_to_hide_3cm_lattice_m']:.3g} m (lattice)")
    opt['far_ir'] = {f'{lab} {f/1e12:g} THz': far_ir_wall(sg, f) for lab, sg in (('Cu 300 K', 5.96e7), ('W 1800 K', 2.0e6), ('W 300 K', 1.8e7))
                     for f in (0.3e12, 1e12, 3e12)}
    log('== far-IR (cyclotron/synchrotron) wall reflectivity'); log('  ' + json.dumps({a: round(b, 5) for a, b in opt['far_ir'].items()}))
    R['optics'] = opt

    # ---- sources
    src, sval = sources(k)
    R['sources'] = src; R['spectrum_validation'] = sval
    log('== sources (per engine)')
    for key, v in src.items():
        bins = spectrum_bins(v['Te_keV'])
        soft = sum(w for E, w in bins if E < 30); mid = sum(w for E, w in bins if 30 <= E < 100); hard = sum(w for E, w in bins if E >= 100)
        v['bands'] = dict(below_30keV=soft, keV30_100=mid, above_100keV=hard)
        log(f"  {key} {v['name']}: Te {v['Te_keV']:.1f} keV, brems {v['brems']:.4f} sync {v['sync']:.4f} neutrons {v['neutron']:.4f} | "
            f"brems {v['P_brems_W']/1e12:.2f} TW, n {v['P_n_W']/1e12:.3f} TW | <30 {soft:.2f} 30-100 {mid:.2f} >100 {hard:.2f}")
    log('  spectrum check (1.5 LOW vs exp model): ' + ', '.join(f"{r['lo']:g}-{r['hi']:g}: {r['vertex_1_5']:.3f}/{r['exp_model']:.3f}" for r in sval[:6]))

    # ---- candidate A and C (drawn engine)
    log('== A/C: drawn compact engine (1.5 ray trace)')
    A = drawn_engine(src, workers=workers)
    R['A_C_drawn_engine'] = A
    log(f"  intercepted {A['intercepted']:.3f}; graze quantiles {A['graze_deg_quantiles']}; share below 1 deg {A['share_below_1deg']:.4f}")
    for key, v in A['by_source'].items():
        log(f"  {key}: A reflects {v['A_reflected_share']:.4f}, C reflects {v['C_reflected_share']:.4f}; photon heat four engines bare "
            f"{v['bare_photon_heat_four_GW']:.0f} GW, A {v['A_photon_heat_four_GW']:.0f} GW, C {v['C_photon_heat_four_GW']:.0f} GW; neutrons <= {v['neutron_heat_four_GW_upper']:.0f} GW "
            f"(budget {k['drive_W']/1e9:.1f})")

    # ---- candidate B
    B = collimator(src, k)
    R['B_collimator'] = B
    log('== B: nested grazing collimator (aft cone 25 deg)')
    for key, v in B['by_source'].items():
        log(f"  {key}: absorbed {v['absorbed_share']:.3f} of the photons -> {v['heat_four_GW']:.0f} GW added (four), thrust gain "
            f"{v['thrust_gain_per_engine_N']/1e3:.2f} kN per engine = {v['thrust_gain_share']*100:.4f} % of thrust; all photons ideally aft: {v['ideal_thrust_all_photons_aft_kN']:.0f} kN")
    log(f"  jet thrust per watt / photon thrust per watt = {B['ratio']:.1f}")

    # ---- skimmer law
    law = []
    for key in ('V0', 'V2'):
        Te = src[key]['Te_keV']
        for a in (0.02, 0.12, 0.5):
            for L in (10.0, 30.0, 100.0, 300.0, 1000.0):
                for mat in ('C_diamond', 'Pt', 'Os'):
                    s_ = skimmer(Te, a, L, mat)
                    law.append(dict(source=key, a_m=a, L_m=L, material=mat, theta_mrad=s_['theta_mrad'], absorbed=s_['absorbed']))
    R['skimmer_law'] = law
    log('== skimmer absorbed share of intercepted photons (V0 spectrum)')
    for a in (0.02, 0.12, 0.5):
        log(f"  a {a} m: " + '  '.join(f"L {int(r['L_m'])} {r['material'][:2]} {r['absorbed']:.3f}" for r in law if r['source'] == 'V0' and r['a_m'] == a))
    R['skimmer_mc'] = [skimmer_mc(55.0, 0.02, 40.0, 'Pt', n=4000, src_radius=sr, dist=100.0) | dict(analytic=skimmer(55.0, 0.02, 40.0, 'Pt', tip_m=0.0)['absorbed'])
                       for sr in (0.0, 0.01, 0.05)]
    log('  finite source (Pt, a 2 cm, L 40 m, 100 m away): ' + ', '.join(f"r_src {r['src_radius_m']} m -> {r['absorbed_mc']:.3f} (analytic {r['analytic']:.3f})" for r in R['skimmer_mc']))

    # ---- candidate D: Halo Vertex 2.5 with MPN skimmers on the ring face
    H = halo_reference()
    d = H['detail']; heat = H['heat_engine_GW']
    log('== D: Halo Vertex 2.5 case (per engine) and its ring with skimmers')
    log(f"  Halo: R {d['R_m']:.1f} m, burn-ring {d['burn_to_ring_m']:.1f} m, sky {d['sky']:.2e}, face {d['face_m']:.3f} m, fin {d['fin_t_m']:.2f} m; heat {json.dumps({a: round(b, 3) for a, b in heat.items()})}")
    Dres = []
    hv = src['V2']
    for Ls in (0.0, 20.0, 40.0, 69.0):
        for mat in ('Pt', 'C_diamond', 'Os'):
            if Ls == 0 and mat != 'Pt':
                continue
            A_ = skimmer(hv['Te_keV'], d['face_m']/2, Ls, mat)['absorbed'] if Ls > 0 else 1.0
            ring_ph = heat['isotropic radiation on ring armour']*A_
            tot = sum(heat.values())-heat['isotropic radiation on ring armour']+ring_ph
            skim_t = 2*0.3e-3*Ls*2*math.pi*d['R_m']*3.515*3
            Dres.append(dict(Ls_m=Ls, material=mat, ring_absorbed=A_, ring_photon_GW=ring_ph, engine_heat_GW=tot,
                             radiator_saved_t=(heat['isotropic radiation on ring armour']-ring_ph)/sum(heat.values())*H['radiator_t_engine'],
                             skimmer_t=skim_t, broadside_added_m2=2*math.pi*d['R_m']*Ls*0.5))
    R['D_halo_mpn'] = dict(halo=dict(detail=d, heat_engine_GW=heat, engine_t=H['engine_t'], radiator_t=H['radiator_t_engine'], system_t=H['system_t']),
                           rows=Dres)
    for r in Dres:
        log(f"  Ls {r['Ls_m']:5.0f} {r['material']:9s}: ring absorbs {r['ring_absorbed']:.3f} -> {r['ring_photon_GW']:.2f} GW; engine {r['engine_heat_GW']:.2f} GW; "
            f"radiator saved {r['radiator_saved_t']:.1f} t vs skimmer {r['skimmer_t']:.1f} t; +{r['broadside_added_m2']:.0f} m2 broadside")

    # ---- candidate F: edge-on hybrid
    log('== F: edge-on remote ring hybrid (per engine, then x4)')
    charged = heat['charged leakage']*1e9
    F = {}
    for key in ('V0', 'V2', 'V3'):
        for label, kw in (('Halo-like thick face (0.24 m), round cables', dict(cryo_m=0.11, edge_on_tethers=False)),
                          ('edge-on ribbon + round cables', dict(edge_on_tethers=False)),
                          ('edge-on ribbon + edge-on tapes', dict()),
                          ('edge-on + Pt knife-edge skimmers 20 m', dict(Ls=20.0, mat='Pt')),
                          ('edge-on + Pt skimmers 60 m', dict(Ls=60.0, mat='Pt'))):
            e = remote_engine(k, src[key], charged_W=charged, **kw)
            F[f'{key} | {label}'] = e
            log(f"  {key} {label}: thick {e['params']['thickness_m']*100:.1f} cm, nose {e['params']['nose_m']:.2f} m at {e['T_nose_K']:.0f} K, "
                f"ring sky {e['rows'][0]['sky']:.2e}; B01 x4 {4*e['B01_W']/1e9:.2f} GW (budget {k['drive_W']/1e9:.1f}); self-radiated x4 "
                f"{4*e['self_radiated_W']/1e9:.2f} GW; total x4 {4*e['total_W']/1e9:.2f}; mass {e['mass_total_t']:.0f} t/engine "
                f"{json.dumps({a_: round(b_, 1) for a_, b_ in e['mass_t'].items()})}")
            for r in e['rows']:
                log(f"      {r['element']:48s} sky {r['sky']:.2e}  ph {r['photon_W']/1e9:7.3f} GW  n {r['neutron_W']/1e9:7.3f} GW  ch {r.get('charged_W', 0)/1e9:5.2f}  -> {r['sink']}")
    R['F_hybrid'] = F
    R['optimiser'] = {key: optimise(k, src[key], charged) for key in ('V0', 'V2', 'V3')}
    for key, o in R['optimiser'].items():
        fmt = lambda r: f"R{r['R']:.0f} D{r['D']:.0f} S{r['S']:.0f} Ls{r['Ls']:.0f} {r['mat'][:2]} h{r['depth']:.0f} {r['I_MA']:.0f} MA {r['B01_four_GW']:.1f}+{r['self_four_GW']:.1f} GW {r['mass_t']:.0f} t"
        log(f"  optimiser {key}: {o['feasible']}/{o['n']} feasible (B01), {o['strict']} strict (all heat); lightest: " + '; '.join(fmt(r) for r in o['lightest'][:3]))
        log(f"      lightest strict: " + '; '.join(fmt(r) for r in o['lightest_strict'][:3]))
        log(f"      skimmers among the feasible: {sum(1 for r in o['rows'] if r['fits'] and r['Ls'] > 0)} of {o['feasible']}; among the 8 lightest: {sum(1 for r in o['lightest'] if r['Ls'] > 0)}")
    # recommended point (lightest strict thermal closure, V2) and its sensitivities
    rec = dict(R=90.0, D=2000.0, S=2000.0, depth=4.0, Ls=0.0)
    sens = []
    for label, kw in (('recommended (V2)', {}), ('field ratio 10 instead of 50', dict(field_ratio=10.0)),
                      ('REBCO J_e x2 (6e8 A/m2, advanced)', dict(Je=6e8)), ('pulse rate 6.8 kHz (Halo 2.5)', dict(pulse_rate=6.8e3)),
                      ('scattered-in neutron floor 1e-3', dict(scatter_floor=1e-3)), ('charged leakage x0.1', dict(charged_W=charged*0.1)),
                      ('V3 source', dict(_src='V3')), ('V0 source', dict(_src='V0')), ('D 1000 m', dict(D=1000.0)), ('S 1000 m', dict(S=1000.0)),
                      ('Pt knife-edge skimmer 20 m', dict(Ls=20.0)), ('round cables instead of edge-on tapes', dict(edge_on_tethers=False))):
        kw = dict(kw); key = kw.pop('_src', 'V2')
        args = dict(rec); args.update(kw); args.setdefault('charged_W', charged)
        e = remote_engine(k, src[key], **args)
        sens.append(dict(case=label, B01_four_GW=4*e['B01_W']/1e9, self_four_GW=4*e['self_radiated_W']/1e9, total_four_GW=4*e['total_W']/1e9,
                         mass_t=e['mass_total_t'], T_nose_K=e['T_nose_K'], I_MA=e['params']['I_MA'], strict=e['fits_total'] and e['fluence_ok'] and e['nose_ok']))
    R['F_recommended'] = dict(point=rec, engine=remote_engine(k, src['V2'], charged_W=charged, **rec), sensitivity=sens)
    R['F_eddy'] = eddy_screen(R['F_recommended']['engine'])
    log(f"== F magnetic compatibility: eddy screen (swing {R['F_eddy']['swing']}, dB {R['F_eddy']['dB_T']:.2f} T, transit {R['F_eddy']['transit_s']*1e6:.1f} us, duty {R['F_eddy']['duty']:.2f})")
    for r in R['F_eddy']['rows']:
        log(f"  {r['part']:46s} {r['W_per_engine']/1e9:.3g} GW per engine")
    log('== F recommended point and sensitivities (four engines)')
    for r in sens:
        log(f"  {r['case']:42s} B01 {r['B01_four_GW']:.2f} + self {r['self_four_GW']:.2f} = {r['total_four_GW']:.2f} GW; {r['mass_t']:.0f} t/engine; "
            f"nose {r['T_nose_K']:.0f} K; {r['I_MA']:.1f} MA; strict {r['strict']}")
    R['maps'] = maps(k, src)
    for key, m in R['maps']['intercept'].items():
        log(f"  {key}: hardware sky needed (photons only) {json.dumps({str(a): round(b, 7) for a, b in m['f_needed_photons_only'].items()})}; "
            f"neutrons only {m['f_needed_neutrons_only']:.2e}")
    OUT.write_text(json.dumps(R, indent=1, default=str))
    LOG.write_text('\n'.join(LINES)+'\n')
    return R


if __name__ == '__main__':
    main()
