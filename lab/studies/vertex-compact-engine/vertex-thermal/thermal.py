"""Vertex thermal engineering: supermirrors, cooling mesh and the per-component radiation and heat ledger (owner brief 2026-11-23 14:18Z).
Work, noncanonical. Standard library only (reads the shared Vertex modules, the Fusion Ignition ledger results and the MPN optics data).

    python3 lab/studies/vertex-compact-engine/vertex-thermal/thermal.py        # writes results/thermal.json and prints the summary (about 10 s)

What it does, for one engine of the drawn compact cluster (C1 geometry, vertex_engine.parts) at the COUPLED pulse of the Fusion Ignition
ledger (lab/studies/fusion-ignition/results/fusion_ignition.json, ledger.pulse):

1. Sky ledger. From the burn point, every polar direction (0.02 deg bands, full azimuth) is traced to the nearest drawn part: tori
   (armour shoes, cryostat segments, joints, headers, hoops, LiH noses, the reaction ring), the shield burn face, and the thin members
   (longerons, seats, struts, tie rods, lines) as azimuthal fill fractions. Each strike keeps its distance and its grazing angle psi.
2. Radiation per component: incident, reflected (strategy A-D optics), transmitted, absorbed, secondary (fluorescence and Compton
   albedo) and final deposition, for the R2-B X-ray spectrum, the neutrons and the charged strikes.
3. Heat per component and per thermal regime: HOT (lithium-cooled armour and shield face, 1500 -> 1800 K), WARM (vessels, cage, lines,
   driver optics: drawn without a coolant), CRYO (20 K windings, 80 K screens). Coolant flow, channel and line capacity, MHD pressure
   loss, pumping, refrigeration, radiator area and mass, Brayton recovery without double counting.
4. Mirror strategies A (coated coil and shield faces), B (edge-on structure), C (layered full-silhouette blankets), D (integrated
   grazing nozzle photonics): heat moved or removed, mass added, and where each fails.
5. Geometry of the WORK hardware (mirror assemblies, blanket layers, cooling mesh) in the engine frame, for blender_thermal.py and the
   Fusion Ignition page.

Classes: CALCULATED (computed here), MODEL-BASED (textbook relation, not demonstrated for this hardware), PROTOTYPE (a declared design
choice), IMPORTED (another study), OPEN. Nothing here is canon; nothing writes to data/.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
sys.path.insert(0, str(ROOT / 'lab/studies/vertex-compact-engine/magneto-photonic-nozzle'))
sys.path.insert(0, str(ROOT / 'lab/studies/fusion-ignition'))
import spec as S  # noqa: E402
import vertex_engine as ve  # noqa: E402
import vertex_magnet as vm  # noqa: E402
import vertex_radiation as vr  # noqa: E402
import vertex_plasma as vp  # noqa: E402
import mpn  # noqa: E402
import ledger as LG  # noqa: E402

OUT = HERE / 'results' / 'thermal.json'
FI = ROOT / 'lab/studies/fusion-ignition/results/fusion_ignition.json'
SIGMA_SB = 5.670374419e-8
MU0 = 4e-7 * math.pi

# ---------- declared choices (PROTOTYPE unless marked) ---------------------------------------------------------------------------------
P = dict(
    dtheta_deg=0.02,               # polar band of the sky trace
    q_limit_W_m2=20e6,             # steady heat-flux limit of a lithium-cooled tungsten face (order of ITER divertor targets, 10-20 MW/m2)
    li_in_K=1500.0, li_out_K=1800.0,
    li_sigma_S_m=2.5e6,            # liquid lithium electrical conductivity near 1600 K (MODEL-BASED, about 0.4 uOhm m)
    c_wall_bare=0.05, c_wall_fci=0.002,   # MHD wall conductance ratio: bare refractory wall / SiC flow-channel insert
    pump_eff=0.8,
    channel_depth_m=0.010, channel_open=0.5,   # coolant layer under each armour face (depth, open fraction)
    lam_armour_m=0.08, floor=1e-4,  # W/B4C neutron attenuation length and scattered floor (MPN rule, lab/studies/vertex-compact-engine/vertex-compact problems.py)
    lam_lih_m=0.12,                 # LiH fast-neutron removal length
    winding_dep=0.5,                # share of the neutron energy reaching a winding pack that it deposits there
    albedo=0.03,                    # X-ray energy re-emitted by fluorescence and Compton backscatter from high-Z faces (MODEL-BASED)
    sigma_rough_m=0.5e-9,           # mirror roughness (polished, as-new)
    miss_m=None,                    # source wander: vertex_engine.structure.target_miss_tolerance_m (set in main)
    rhoc_W=19300 * 150.0,           # tungsten volumetric heat capacity near 1500 K, J/m3/K
    W_melt_K=3695.0, steel_melt_K=1700.0,
    cop80_W_per_W=14.0,             # 80 K screen refrigeration, about 20 % of Carnot rejecting at 300 K
    support_W_80=1000.0, support_W_20=50.0,   # per coil: cold-mass supports and leads to the 80 K and 20 K stages
    mli_W_m2_293=1.0, mli_W_m2_80=0.05,
    eps_gap=0.05,                   # effective emissivity between a hot face and the warm vessel behind its gap (polished screen)
    low_T_K=300.0, low_eps=0.91,    # LOW radiator (cryocooler rejection), radiator_zones LOW circuit
    radiator_kg_m2=10.0,            # deployed radiator mass per effective m2 (MPN, the study figure)
    farir_f_Hz=1e12,                # synchrotron harmonics of a hot steady plasma (far infrared)
    sigma_W_hot=1.5e6, sigma_B4C=1e3,  # electrical conductivity of a tungsten face near 1500 K and of a B4C face
    edge_m=0.03,                    # strategy B: leading-edge thickness of a source-aligned member
    B_mass_factor=1.3,              # strategy B: a deep thin blade carries the member's load with about 30 % more mass (buckling)
    D_eff=0.7,                      # strategy D: usable grazing angle as a share of the critical angle (reflectivity about 0.5)
)
# strategy C blanket stack (outside -> inside): thickness m, density kg/m3, role
STACK = [('CFC sacrificial face', 0.010, 1900, 'Low-Z face: spreads each X-ray pulse over centimetres; ablates and is renewed'),
         ('W/CFC heat sink with lithium channels', 0.012, 9000, 'Lithium 1500 -> 1800 K, 10 mm channels at 50 % open area'),
         ('W/B4C shield', 0.22, 12000, 'Neutron and gamma attenuation (drawn armour thickness)'),
         ('LiH moderator', 0.10, 780, 'Slows the neutrons the shield passes; Li-6 capture'),
         ('Vacuum gap and polished screen', 0.05, 2700 * 0.04, 'Thermal isolation: radiation only, eps about 0.05'),
         ('80 K screen (Cu, cooled)', 0.002, 8960, 'Intercepts the warm-side heat before the 20 K stage'),
         ('MLI', 0.02, 90, 'About 40 layers'),
         ('Cryostat vessel wall', 0.02, 7900, 'Vacuum boundary (drawn)')]


def r(v, n=4):
    return float(f'{v:.{n}g}') if isinstance(v, (int, float)) and v not in (0,) and math.isfinite(v) else v


# ---------- inputs ---------------------------------------------------------------------------------------------------------------------

def inputs(s):
    fi = json.loads(FI.read_text()); L = fi['ledger']; pl = L['pulse']
    b = LG.base_case(s); rr = LG.design_rhoR(s)
    br = vr.burn(s, dict(b, rhoR_g_cm2=rr), spectrum=True)
    edges = vr.config(s)['spectrum_edges_keV']
    spec = [(math.sqrt(a * c), w) for a, c, w in zip(edges, edges[1:], br['spectrum_share']) if w > 0]
    steady = next(x for x in L['states'] if x['id'] == 'STEADY')
    return dict(pulse=pl, Hz=pl['Hz'], spec=spec, edges=edges, steady=steady, R0_m=br['R0_m'], budget_W=pl['budget_W'],
                fi_hash=fi['inputs_hash'], design_fusion_W=pl['fusion_W'])


# ---------- the drawn engine as sky occluders ----------------------------------------------------------------------------------------

def comp_of(name):
    """Component and surface of a drawn part: (component, surface, regime)."""
    n = name[4:]
    for k in ('C1', 'C2', 'L1', 'L2', 'L3', 'L4'):
        if n.startswith(k + '_Armour_Header'):
            return k, 'HEADER', 'HOT'
        if n.startswith(k + '_Armour'):
            return k, 'ARMOUR', 'HOT'
        if n.startswith(k + '_LiH'):
            return k, 'NOSE', 'HOT'
        if n.startswith(k + '_Segment') or n == k + '_Cryostat':
            return k, 'VESSEL', 'WARM'
        if n.startswith(k + '_Joint'):
            return k, 'JOINT', 'WARM'
        if n.startswith(k + '_Winding'):
            return k, 'WINDING', 'CRYO'
        if n.startswith(k + '_Lithium') or n.startswith(k + '_Cryo') or n.startswith(k + '_Lead'):
            return 'LINES', k, 'WARM'
    if n.startswith('Shield_Burn_Face'):
        return 'SHIELD', 'FACE', 'HOT'
    if n.startswith('Driver_Optic'):
        return 'OPTICS', 'OPTIC', 'WARM'
    if n.startswith(('Cage', 'Loop_Seat', 'C1_Strut', 'C2_Strut', 'Shield_Tie', 'Coil_Reaction')):
        return 'CAGE', n.split('_')[0] if not n.startswith('Loop_Seat') else 'Seat', 'WARM'
    if n.startswith(('Lithium', 'Cryo', 'Coil_Current', 'Exchange')):
        return 'LINES', n.split('_')[0], 'WARM'
    return None


def occluders(s):
    """Axisymmetric rings (x, R, a, fill), the face disc, and the thin members (tube segments) of the drawn engine."""
    rings, members = {}, []
    face = None
    for p in ve.parts(s):
        c = comp_of(p['name'])
        if not c:
            continue
        key = (c[0], c[1])
        if p['shape'] == 'torus':
            fill = (p['arc'][1] - p['arc'][0]) / 360.0 if p.get('arc') else 1.0
            k = (key, round(p['x'], 4), round(p['R'], 4), round(p['a'], 4))
            rings[k] = rings.get(k, 0.0) + fill
        elif p['shape'] == 'torus_section':
            k = (key, round(p['x'], 4), round(p['R'], 4), round(p['a'], 4))
            rings[k] = rings.get(k, 0.0) + p['width'] / (2 * math.pi * p['R'])
        elif p['shape'] == 'revolve' and c[0] == 'SHIELD':
            face = dict(x=max(x for x, _ in p['profile']), R=max(rr for _, rr in p['profile']))
        elif p['shape'] == 'tube':
            for a, b in zip(p['points'], p['points'][1:]):
                members.append(dict(comp=c[0], surf=c[1], p0=a, p1=b, w=2 * p['radius']))
        elif p['shape'] == 'disc' and c[0] == 'OPTICS':
            members.append(dict(comp='OPTICS', surf='OPTIC', disc=p['center'], rad=p['radius']))
    ring_list = [dict(comp=k[0][0], surf=k[0][1], x=k[1], R=k[2], a=k[3], fill=min(1.0, f)) for k, f in rings.items()]
    return ring_list, members, face


def trace(s, bx, rings, face, dth):
    """Polar bands from the burn point: nearest axisymmetric strikes with their fill, distance and grazing angle."""
    n = int(round(180.0 / dth)); out = []
    for i in range(n):
        t0, t1 = math.radians(i * dth), math.radians((i + 1) * dth); th = 0.5 * (t0 + t1)
        share = 0.5 * (math.cos(t0) - math.cos(t1)); c, sn = math.cos(th), math.sin(th)
        hits = []
        for g in rings:
            dx, dr = g['x'] - bx, g['R']
            t = dx * c + dr * sn; b = abs(dx * sn - dr * c)
            if t > 0 and b < g['a']:
                hits.append((t - math.sqrt(g['a'] ** 2 - b * b), g, math.acos(min(1.0, b / g['a']))))
        if face and c > 0:
            t = (face['x'] - bx) / c
            if t * sn <= face['R']:
                hits.append((t, dict(comp='SHIELD', surf='FACE', fill=1.0), math.pi / 2 - th))
        hits.sort(key=lambda h: h[0])
        out.append((th, share, hits))
    return out


def ledger_sky(s, inp):
    st = ve.stations(s); bx = st['burn']
    rings, members, face = occluders(s)
    bands = trace(s, bx, rings, face, P['dtheta_deg'])
    comp = {}
    def add(key, share, rho, psi, kind='axi'):
        d = comp.setdefault(key, dict(share=0.0, area=0.0, peak=0.0, psi=[], rho_min=1e9))
        d['share'] += share
        sp = max(math.sin(psi), 1e-3)
        d['area'] += share * 4 * math.pi * rho * rho / sp
        d['peak'] = max(d['peak'], math.sin(psi) / (4 * math.pi * rho * rho))
        d['rho_min'] = min(d['rho_min'], rho)
        d['psi'].append((psi, share))
    escape = 0.0
    nearest = []
    for th, share, hits in bands:
        rem = 1.0
        for t, g, psi in hits:
            take = rem * g['fill']
            if take > 0:
                add((g['comp'], g['surf']), share * take, t, psi)
            rem -= take
            if rem <= 1e-12:
                break
        escape += share * rem
        nearest.append(hits[0][0] if hits else None)
    # thin members: sample along each segment, occluded by any nearer axisymmetric strike in its band
    n = len(bands); dth = math.radians(P['dtheta_deg'])
    for m in members:
        if 'disc' in m:
            cx, cy, cz = m['disc']; rho_r = math.hypot(cy, cz); dx = cx - bx; rho = math.hypot(dx, rho_r)
            cosi = abs(dx) / rho
            sh = math.pi * m['rad'] ** 2 * cosi / (4 * math.pi * rho * rho)
            add((m['comp'], m['surf']), sh, rho, math.pi / 2 - math.acos(cosi))
            continue
        a, b = m['p0'], m['p1']; Lm = math.dist(a, b); k = 24
        dirv = [(q - p_) / Lm for p_, q in zip(a, b)]
        for j in range(k):
            f = (j + 0.5) / k; p_ = [u + f * (v - u) for u, v in zip(a, b)]
            v = (p_[0] - bx, p_[1], p_[2]); rho = math.sqrt(sum(x * x for x in v))
            th = math.acos(max(-1.0, min(1.0, v[0] / rho))); ib = min(n - 1, int(th / dth))
            near = nearest[ib]
            if near is not None and near < rho:
                continue
            cosp = abs(sum(x * y for x, y in zip(v, dirv))) / rho; sinp = math.sqrt(max(0.0, 1 - cosp * cosp))
            sh = m['w'] * sinp * (Lm / k) / (4 * math.pi * rho * rho)
            add((m['comp'], m['surf']), sh, rho, math.pi / 4)        # a round member: mean grazing angle 45 deg (A does not coat members)
            escape -= sh
    return comp, escape, rings, members, face


# ---------- optics --------------------------------------------------------------------------------------------------------------------

def R_spec(spec, psi, mat=None):
    """Power-weighted reflectivity of the R2-B spectrum at grazing angle psi: best coating per energy (mat None) or one coating."""
    tot = 0.0
    for E, w in spec:
        Rv = mpn.best_R(E, psi, P['sigma_rough_m'])[0] if mat is None else mpn.fresnel_R(mat, E, psi, P['sigma_rough_m'])
        tot += w * Rv
    return tot


def mu_spec(spec, mat):
    return [(E, w, mpn._interp(mat, 'mu_loss_m', E)) for E, w in spec]


# ---------- main model ---------------------------------------------------------------------------------------------------------------

def coil_field(eng_coils, name, dist):
    I = next(abs(c['MAt']) for c in eng_coils if c['name'] == name) * 1e6
    return MU0 * I / (2 * math.pi * dist)


def build():
    s = S.load()[0]; inp = inputs(s); pl = inp['pulse']; Hz = inp['Hz']; spec = inp['spec']
    stc = s['vertex_engine']['structure']; P['miss_m'] = stc['target_miss_tolerance_m']
    st = ve.stations(s); bx = st['burn']
    comp, escape, rings, members, face = ledger_sky(s, inp)
    fi = json.loads(FI.read_text()); eng_coils = fi['engine']['coils']
    XW = pl['xray_J'] * Hz; NW = pl['neutron_J'] * Hz; HW = pl['hit_J'] * Hz
    geo_share = sum(d['share'] for d in comp.values())
    pickup = json.loads(FI.read_text())['ledger']['nozzle']['C1|1'].get('pickup_piped', pl['x_abs_J'] / pl['xray_J'])
    # psi lookup for the reflection integral (grazing angles are binned on a log grid)
    grid = [10 ** (-6 + 6.2 * i / 160) for i in range(161)]
    Rg = {i: R_spec(spec, min(g, math.pi / 2)) for i, g in enumerate(grid)}
    def Rof(psi):
        if psi <= grid[0]:
            return Rg[0]
        i = min(160, int((math.log10(psi) + 6) / 6.2 * 160)); return Rg[i]
    hw_share = {k: d['share'] for k, d in comp.items()}
    tot_hw = sum(hw_share.values())
    # ---------- per surface radiation ledger (baseline: the drawn engine, no mirrors) ----------
    surf = []
    T_arm = math.exp(-ve.config(s)['geometry']['armour_minor_m'] * 2 / P['lam_armour_m']) + P['floor']   # shoe section 0.44 m deep on the burn line
    T_nose = math.exp(-0.32 / P['lam_lih_m']) + P['floor']
    for (c, sf), d in sorted(comp.items(), key=lambda kv: -kv[1]['share']):
        X_in = XW * d['share']; N_in = NW * d['share']; H_in = HW * d['share'] / tot_hw
        refl_A = XW * sum(sh * Rof(psi) for psi, sh in d['psi']) if sf in ('ARMOUR', 'NOSE', 'FACE', 'VESSEL') else 0.0
        X_abs = X_in; sec = P['albedo'] * X_abs if sf in ('ARMOUR', 'FACE', 'NOSE', 'VESSEL', 'JOINT') else 0.0
        if sf in ('ARMOUR',):
            Ntr = N_in * T_arm
        elif sf == 'NOSE':
            Ntr = N_in * T_nose
        elif sf == 'VESSEL':
            Ntr = N_in
        else:
            Ntr = 0.0
        to_wind = Ntr * P['winding_dep']
        regime = 'HOT' if sf in ('ARMOUR', 'NOSE', 'FACE', 'HEADER') else 'WARM'
        hot = (X_abs - sec + N_in - Ntr + H_in) if regime == 'HOT' else 0.0
        warm = (X_abs - sec + N_in - Ntr + H_in + Ntr - to_wind) if regime == 'WARM' else (Ntr - to_wind)
        surf.append(dict(comp=c, surface=sf, regime=regime, sky=d['share'], area_m2=d['area'], rho_min_m=d['rho_min'],
                         peak_W_m2=d['peak'] * (XW + NW) + (HW / tot_hw) * d['peak'] * 1.0,
                         xray=dict(incident_W=X_in, reflected_W=0.0, transmitted_W=0.0, absorbed_W=X_abs, secondary_W=sec, final_W=X_abs - sec,
                                   reflectable_A_W=refl_A),
                         neutron=dict(incident_W=N_in, transmitted_W=Ntr, absorbed_W=N_in - Ntr, winding_W=to_wind),
                         charged=dict(incident_W=H_in, absorbed_W=H_in),
                         hot_W=hot, warm_W=warm, cryo_W=to_wind, total_W=X_abs - sec + N_in + H_in))
    sec_total = sum(x['xray']['secondary_W'] for x in surf)
    # ---------- components (assemblies) ----------
    order = ['SHIELD', 'C1', 'C2', 'L1', 'L2', 'L3', 'L4', 'CAGE', 'LINES', 'OPTICS']
    comps = []
    for c in order:
        ss = [x for x in surf if x['comp'] == c]
        if not ss:
            continue
        agg = lambda f: sum(f(x) for x in ss)
        comps.append(dict(id=c, surfaces=[x['surface'] for x in ss], sky=agg(lambda x: x['sky']), area_m2=agg(lambda x: x['area_m2']),
                          xray_W=agg(lambda x: x['xray']['incident_W']), neutron_W=agg(lambda x: x['neutron']['incident_W']),
                          charged_W=agg(lambda x: x['charged']['incident_W']), hot_W=agg(lambda x: x['hot_W']), warm_W=agg(lambda x: x['warm_W']),
                          cryo_W=agg(lambda x: x['cryo_W']), total_W=agg(lambda x: x['total_W']),
                          armoured_share=sum(x['sky'] for x in ss if x['surface'] in ('ARMOUR', 'NOSE', 'FACE')) / max(1e-30, agg(lambda x: x['sky']))))
    # ---------- reconciliation with the ledger pickup ----------
    other = pickup - geo_share
    recon = dict(geometry_sky=geo_share, ledger_pickup=pickup, escape=escape, other=other, ratio=geo_share / pickup,
                 note=f'This trace of every drawn part finds the hardware covering {geo_share:.1%} of the burn\'s sky. The compact study\'s '
                      f'piped share ({pickup:.1%}) is not a geometric figure: it is its piped heat minus the charged strikes, over the steady-plasma '
                      f'neutral power, and it leaves out the cage hoops, seats, struts and lines and what edge-on parts re-radiate. Since the '
                      f'2026-11-24 audit (lab/studies/vertex-compact-engine/vertex-source) the coupled ledger uses this trace for its X-ray and neutron pickup.')
    other_W = max(0.0, other) * (XW + NW)
    # ---------- pulsed surface heating at the hottest armour point ----------
    pk = []
    for x in surf:
        if x['surface'] in ('ARMOUR', 'FACE', 'NOSE', 'VESSEL'):
            d = comp[(x['comp'], x['surface'])]
            F = pl['xray_J'] * d['peak']                                             # J/m2 per pulse at normal-ish incidence
            mat = 'W' if x['surface'] in ('ARMOUR', 'FACE') else ('LiH' if x['surface'] == 'NOSE' else 'Ni')
            rc = P['rhoc_W'] if mat == 'W' else (780 * 4200.0 if mat == 'LiH' else 7900 * 600.0)
            dT = sum(F * w * mu for _, w, mu in mu_spec(spec, mat)) / rc
            depth = sum(w / mu for _, w, mu in mu_spec(spec, mat))
            pk.append(dict(comp=x['comp'], surface=x['surface'], material=mat, fluence_J_m2=F, dT_surface_K=dT, mean_depth_m=depth,
                           mean_flux_W_m2=(x['total_W']) / max(x['area_m2'], 1e-9), peak_flux_W_m2=F * Hz))
    hottest = max((x for x in pk if x['surface'] in ('ARMOUR', 'FACE')), key=lambda x: x['fluence_J_m2'])
    rhoc = dict(W=19300 * 150.0, Mo=10200 * 330.0, SiC=3210 * 1200.0, C_diamond=1900 * 1800.0, Be=1850 * 2800.0, LiH=780 * 4200.0)
    melt = dict(W=3695.0, Mo=2896.0, SiC=3003.0, C_diamond=3900.0, Be=1560.0, LiH=961.0)
    pulse_mats = []
    for m_, rc_ in rhoc.items():
        dT_ = sum(hottest['fluence_J_m2'] * w * mu for _, w, mu in mu_spec(spec, m_)) / rc_
        pulse_mats.append(dict(material=m_, rho_c=rc_, dT_surface_K=dT_, melt_K=melt[m_], margin_K=melt[m_] - P['li_out_K'] - dT_,
                               mean_depth_m=sum(w / mu for _, w, mu in mu_spec(spec, m_)), survives=melt[m_] - P['li_out_K'] - dT_ > 0))
    pulsed = dict(points=pk, hottest=hottest, materials=pulse_mats, Hz=Hz, cycles_per_hour=Hz * 3600,
                  note='Surface temperature jump of one pulse at the hottest armour point (fluence per pulse times the spectrum-weighted absorption '
                       'at the surface, over the volumetric heat capacity; the pulse is far shorter than heat conduction). C_diamond stands for '
                       'carbon (CFC density). A low-Z face spreads the same X-rays over centimetres; tungsten takes them in the first micrometres.')
    # ---------- hot circuit ----------
    cp = stc['lithium_cp_J_kgK']; dT = P['li_out_K'] - P['li_in_K']; rho_li = stc['lithium_density_kg_m3']; vmax = stc['lithium_max_velocity_m_s']
    Q_hot = sum(x['hot_W'] for x in surf); Q_warm = sum(x['warm_W'] for x in surf); Q_cryo_n = sum(x['cryo_W'] for x in surf)
    flow_cap = lambda A: rho_li * vmax * A * cp * dT
    lines = dict(feeder=math.pi * 0.11 ** 2, panel=math.pi * 0.12 ** 2, manifold=math.pi * 0.20 ** 2, header=math.pi * 0.08 ** 2, jumper=math.pi * 0.07 ** 2)
    net_cap = min(flow_cap(lines['feeder']), flow_cap(lines['panel']))
    hot_rows = []
    g = ve.config(s)['geometry']
    for c in comps:
        hs = [x for x in surf if x['comp'] == c['id'] and x['regime'] == 'HOT']
        if not hs:
            continue
        A = sum(x['area_m2'] for x in hs); Q = sum(x['hot_W'] for x in hs)
        q_cap = P['q_limit_W_m2'] * A
        if c['id'] in ('C1', 'C2', 'L1', 'L2', 'L3', 'L4'):
            ring = next(rr for rr in rings if rr['comp'] == c['id'] and rr['surf'] in ('ARMOUR', 'NOSE'))
            seg_L = 2 * math.pi * ring['R'] / g['segments_per_loop']
            A_flow = g['segments_per_loop'] * math.pi * ring['a'] * P['channel_depth_m'] * P['channel_open']
            coil = next(cc for cc in st['coils'] + st['loops'] if cc['name'] == c['id'])
            Bmag = coil_field(eng_coils, c['id'], math.hypot(ring['x'] - coil['x'], ring['R'] - coil['r']))
            hdr = lines['header'] if c['id'].startswith('L') else lines['jumper']
        else:
            seg_L = 2 * math.pi * 2.7; A_flow = 2 * math.pi * 2.7 * P['channel_depth_m'] * P['channel_open'] * 0.5; Bmag = 1.5; hdr = lines['panel']
        cap_flow = flow_cap(min(A_flow, hdr))
        mdot = Q / (cp * dT); Vd = mdot / rho_li; v_need = Vd / A_flow
        dp_mhd = lambda c_, v: P['li_sigma_S_m'] * v * Bmag ** 2 * seg_L * c_ / (1 + c_)
        removed = min(Q, q_cap, cap_flow)
        hot_rows.append(dict(id=c['id'], heat_W=Q, area_m2=A, flux_W_m2=Q / A, q_limit_W_m2=P['q_limit_W_m2'], flux_cap_W=q_cap, flow_cap_W=cap_flow,
                             removed_W=removed, deficit_W=Q - removed, over=Q / removed if removed else None, mdot_kg_s=mdot, flow_m3_s=Vd,
                             flow_area_m2=A_flow, v_needed_m_s=v_need, B_T=Bmag, run_m=seg_L,
                             dp_mhd_bare_Pa=dp_mhd(P['c_wall_bare'], vmax), dp_mhd_fci_Pa=dp_mhd(P['c_wall_fci'], vmax),
                             dp_needed_flow_fci_Pa=dp_mhd(P['c_wall_fci'], v_need),
                             pump_at_cap_W=(cap_flow / (cp * dT) / rho_li) * (stc['lithium_design_pressure_Pa'] + dp_mhd(P['c_wall_fci'], vmax)) / P['pump_eff']))
    removed_hot = min(sum(h['removed_W'] for h in hot_rows), net_cap)
    rad = s['radiators']; T = rad['temperature']['value']; eps = rad['emissivity']['value']
    q_area = SIGMA_SB * eps * T ** 4
    tr = vp.config(s); eta_b = tr['treg_brayton_efficiency']; Tc = 0.5 * T
    need_all = Q_hot + Q_warm
    hot = dict(inlet_K=P['li_in_K'], outlet_K=P['li_out_K'], heat_W=Q_hot, warm_uncooled_W=Q_warm, cp=cp, dT=dT,
               mdot_kg_s=need_all / (cp * dT), flow_m3_s=need_all / (cp * dT) / rho_li, flow_area_10ms_m2=need_all / (cp * dT) / rho_li / vmax,
               pipe_radius_10ms_m=math.sqrt(need_all / (cp * dT) / rho_li / vmax / math.pi),
               drawn_line_cap_W=net_cap, drawn_line_over=need_all / net_cap, budget_W=inp['budget_W'],
               budget_line_area_m2=inp['budget_W'] / (cp * dT) / rho_li / vmax,
               pump_W=need_all / (cp * dT) / rho_li * stc['lithium_design_pressure_Pa'] / P['pump_eff'],
               removed_W=removed_hot, deficit_W=need_all - removed_hot,
               radiator_m2=need_all / q_area, radiator_t=need_all / q_area * P['radiator_kg_m2'] / 1000, ship_radiator_m2=rad['effective_area']['value'],
               radiator_over_ship=need_all / q_area / rad['effective_area']['value'], radiator_budget_m2=inp['budget_W'] / q_area,
               rows=hot_rows,
               brayton=dict(eff=eta_b, cold_K=Tc, electric_W=eta_b * need_all, rejected_W=(1 - eta_b) * need_all,
                            radiator_m2=(1 - eta_b) * need_all / (SIGMA_SB * eps * Tc ** 4),
                            radiator_over_direct=((1 - eta_b) / Tc ** 4) / (1 / T ** 4),
                            driver_elec_W=pl['driver_elec_W'], driver_covered=eta_b * need_all / pl['driver_elec_W'],
                            note='Recovered electricity can run the driver, whose heat is already the ledger\'s heat_in: it replaces external power '
                                 'and adds no energy or thrust. The rest leaves at the cold side, so the radiator grows.'),
               capacity_fusion_W=inp['design_fusion_W'] * removed_hot / need_all)
    # ---------- cryogenic circuit ----------
    cop20 = 1.0 / json.loads((ROOT / 'references/evidence/vertex_radiation.json').read_text())['thermal']['cop']
    cryo_rows = []
    for c in ('C1', 'C2', 'L1', 'L2', 'L3', 'L4'):
        coil = next(cc for cc in st['coils'] + st['loops'] if cc['name'] == c)
        a_c = coil['cryostat_minor_m']; A_vessel = 4 * math.pi ** 2 * coil['r'] * a_c
        n_w = sum(x['cryo_W'] for x in surf if x['comp'] == c)
        hot_face = sum(x['area_m2'] for x in surf if x['comp'] == c and x['surface'] in ('ARMOUR', 'NOSE'))
        rad_gap = P['eps_gap'] * SIGMA_SB * (P['li_out_K'] ** 4 - 293.0 ** 4) * hot_face        # hot shoe -> warm vessel (warm stage)
        q80 = P['mli_W_m2_293'] * A_vessel + P['support_W_80']
        q20 = P['mli_W_m2_80'] * A_vessel + P['support_W_20'] + n_w
        cryo_rows.append(dict(id=c, vessel_m2=A_vessel, neutron_winding_W=n_w, gap_radiation_to_vessel_W=rad_gap, stage80_W=q80, stage20_W=q20,
                              refrig_W=q80 * P['cop80_W_per_W'] + q20 * cop20, field_T=coil_field(eng_coils, c, coil['winding_minor_m'])))
    refr = sum(x['refrig_W'] for x in cryo_rows)
    q_low = SIGMA_SB * P['low_eps'] * P['low_T_K'] ** 4
    W_st = fi['engine']['stored_J']
    cryo = dict(T_winding_K=stc['cold_mass_temperature_K'], T_screen_K=80.0, cop20_W_per_W=cop20, cop80_W_per_W=P['cop80_W_per_W'], rows=cryo_rows,
                stage20_W=sum(x['stage20_W'] for x in cryo_rows), stage80_W=sum(x['stage80_W'] for x in cryo_rows), refrig_W=refr,
                low_radiator_m2=(refr + sum(x['stage20_W'] + x['stage80_W'] for x in cryo_rows)) / q_low, low_radiator_t=(refr) / q_low * P['radiator_kg_m2'] / 1000,
                quench=dict(stored_J=W_st, dump_s=stc['quench_dump_time_s'], dump_W=W_st / stc['quench_dump_time_s'],
                            note='Stored field energy of the engine coil set (NOMINAL); dumped into warm resistor banks on the pulse pods over the dump time, '
                                 'never into the hot lithium loop.'),
                separation='The cryogenic circuit (20 K windings, 80 K screens, cold supports, leads, quench lines) shares no fluid, header or wall with '
                           'the lithium circuit; the only coupling is radiation across the vacuum gap and conduction through the cold-mass supports.')
    # ---------- mirror strategies ----------
    XW_hot_faces = sum(x['xray']['incident_W'] for x in surf if x['surface'] in ('ARMOUR', 'NOSE', 'FACE', 'VESSEL'))
    A_refl = sum(x['xray']['reflectable_A_W'] for x in surf)
    psi_hist = {}
    for (c, sf), d in comp.items():
        if sf in ('ARMOUR', 'NOSE', 'FACE', 'VESSEL'):
            for psi, sh in d['psi']:
                k = 'below 1 mrad' if psi < 1e-3 else 'below 10 mrad' if psi < 1e-2 else 'below 10 deg' if psi < math.radians(10) else 'above 10 deg'
                psi_hist[k] = psi_hist.get(k, 0.0) + sh * XW
    med = sorted(((psi, sh) for (c, sf), d in comp.items() if sf in ('ARMOUR', 'NOSE', 'FACE', 'VESSEL') for psi, sh in d['psi']))
    acc = 0.0; tot = sum(sh for _, sh in med); psi_med = None
    for psi, sh in med:
        acc += sh
        if acc >= tot / 2:
            psi_med = psi; break
    A_area = sum(x['area_m2'] for x in surf if x['surface'] in ('ARMOUR', 'NOSE', 'FACE'))
    sync_W = inp['steady']['shares']['sync'] * inp['design_fusion_W'] if 'shares' in inp['steady'] else 0.022 * inp['design_fusion_W']
    Rf_W = mpn.far_ir_wall(P['sigma_W_hot'], P['farir_f_Hz']); Rf_B = max(0.0, mpn.far_ir_wall(P['sigma_B4C'], P['farir_f_Hz']))
    esc = 1 - pickup
    absorbed_farir = lambda R_: (1 - R_) / (1 - R_ * (1 - esc))
    A = dict(id='A', title='Coated coil and shield faces (grazing X-ray and far-IR mirrors)',
             surfaces='Burn-facing armour shoes, LiH noses, shield burn face, bare cryostat areas', area_m2=A_area,
             coupled_xray_on_faces_W=XW_hot_faces, coupled_reflected_W=A_refl, coupled_reflected_share=A_refl / XW_hot_faces,
             median_psi_deg=math.degrees(psi_med) if psi_med else None, psi_hist_W=psi_hist,
             steady_sync_on_hw_W=sync_W * pickup, farir_R_W=Rf_W, farir_R_B4C=Rf_B,
             steady_absorbed_W_face=sync_W * pickup * absorbed_farir(Rf_W), steady_absorbed_B4C_face=sync_W * pickup * absorbed_farir(Rf_B),
             mass_t=A_area * 1e-6 * 21450 / 1000,
             verdict='NO BENEFIT (COUPLED)',
             why=f'The faces meet the burn\'s rays at a median grazing angle of {math.degrees(psi_med):.0f} deg; X-ray mirrors reflect only below a few mrad, '
                 f'so a coating returns {A_refl / XW_hot_faces:.1e} of the X-rays that strike. In the STEADY regime a metal face already reflects '
                 f'{Rf_W:.1%} of far-IR synchrotron light; the coating adds nothing over a tungsten face, and helps only where the face would be B4C.')
    # B: edge-on structure
    Bm = [x for x in surf if x['comp'] in ('CAGE', 'LINES')]
    B_heat = sum(x['total_W'] for x in Bm)
    widths = {}
    for m in members:
        if m['comp'] in ('CAGE', 'LINES') and 'w' in m:
            widths.setdefault(m['comp'], []).append(m['w'])
    D_mean = sum(sum(v) for v in widths.values()) / sum(len(v) for v in widths.values())
    rho_c = 9.0; psi_B = P['miss_m'] / rho_c
    face_abs = 1 - R_spec(spec, psi_B)
    depth = 1.0
    keep = (P['edge_m'] + depth * psi_B * face_abs) / D_mean
    mass_members = 0.0
    for p in ve.parts(s):
        c = comp_of(p['name'])
        if c and c[0] == 'CAGE':
            mt = ve.config(s)['materials']
            mass_members += ve._volume(p) * mt['density_kg_m3'][p['material']] * mt['solid_fraction'][p['material']]
    B = dict(id='B', title='Edge-on structure: source-aligned blades and cones for the cage, seats, struts and lines',
             heat_before_W=B_heat, keep_share=keep, heat_after_W=B_heat * keep, removed_W=B_heat * (1 - keep), psi_mrad=psi_B * 1e3,
             face_absorptance=face_abs, member_width_m=D_mean, edge_m=P['edge_m'], members_t=mass_members / 1000,
             mass_t=mass_members / 1000 * (P['B_mass_factor'] - 1),
             verdict='HELPS: LARGEST CUT, FAR FROM ENOUGH',
             why=f'A blade whose plane contains the burn point shows the burn only its {P["edge_m"] * 1000:.0f} mm edge; its faces meet the rays at the '
                 f'source wander over distance (about {psi_B * 1e3:.2f} mrad), where a polished face reflects {1 - face_abs:.0%} of the spectrum. '
                 f'The members\' heat falls to {keep:.1%}; the hoops and the reaction ring become cones with their apex at the burn point. '
                 'The photons that pass the blades go on to space or to the neighbour engines; nothing is stored.')
    # C: layered full-silhouette blankets
    C_rows = []; C_mass = 0.0; C_moved = 0.0; C_cryo_before = 0.0; C_cryo_after = 0.0
    areal = sum(t * rho_ for _, t, rho_, _ in STACK)
    T_C = math.exp(-0.22 / P['lam_armour_m'] - 0.10 / P['lam_lih_m']) + P['floor']
    for c in ('C1', 'C2', 'L1', 'L2', 'L3', 'L4'):
        coil = next(cc for cc in st['coils'] + st['loops'] if cc['name'] == c)
        a_out = coil['cryostat_minor_m'] + sum(t for _, t, _, _ in STACK[:-1])
        A_bl = 2 * math.pi * coil['r'] * math.pi * a_out                                   # burn-facing half of the blanket torus
        bare = [x for x in surf if x['comp'] == c and x['surface'] in ('VESSEL', 'JOINT')]
        moved = sum(x['warm_W'] for x in bare)
        n_in = sum(x['neutron']['incident_W'] for x in surf if x['comp'] == c)
        cb = sum(x['cryo_W'] for x in surf if x['comp'] == c); ca = n_in * T_C * P['winding_dep']
        drawn = sum(ve._volume(p) * 12000 * 0.85 for p in ve.parts(s) if p['name'].startswith(f'VTX_{c}_Armour_') and 'Header' not in p['name'])
        m = A_bl * areal - drawn
        C_rows.append(dict(id=c, blanket_m2=A_bl, areal_kg_m2=areal, mass_t=m / 1000, moved_to_hot_W=moved, cryo_before_W=cb, cryo_after_W=ca))
        C_mass += m; C_moved += moved; C_cryo_before += cb; C_cryo_after += ca
    thin = [x for x in STACK if x[0] not in ('W/B4C shield', 'LiH moderator')]
    areal_thin = sum(t * rho_ for _, t, rho_, _ in thin)
    C_thin_mass = sum(rw['blanket_m2'] for rw in C_rows) * areal_thin / 1000
    C = dict(id='C', title='Layered full-silhouette blankets on every coil',
             thin=dict(areal_kg_m2=areal_thin, mass_t=C_thin_mass, moved_to_hot_W=C_moved,
                       note='Without the W/B4C and LiH layers: the X-rays and strikes on the bare cryostats go to lithium, but the neutrons still reach the windings.'), stack=[dict(layer=a, t_m=t, rho=rho_, role=ro) for a, t, rho_, ro in STACK],
             areal_kg_m2=areal, transmission=T_C, rows=C_rows, mass_t=C_mass / 1000, moved_to_hot_W=C_moved,
             cryo_before_W=C_cryo_before, cryo_after_W=C_cryo_after, refrig_saved_W=(C_cryo_before - C_cryo_after) * cop20,
             verdict='MOVES HEAT, ADDS MASS',
             why='Absorbs instead of reflecting. It covers the cryostat silhouette the drawn shoes leave bare and cuts the neutron heat in the '
                 'windings, so the cryogenic load falls; every joule it stops still goes into the lithium loop, so the hot load does not fall.')
    # C-thin (owner Q-TH-2, 2026-11-24): the optional experimental blanket without the W/B4C and LiH layers; the full blanket is archived
    T_thin = math.exp(-sum(t for a, t, _, _ in thin if a.startswith(('CFC', 'W/CFC'))) / P['lam_armour_m']) + P['floor']
    thin_after = sum(sum(x['neutron']['incident_W'] for x in surf if x['comp'] == c) * T_thin * P['winding_dep'] for c in ('C1', 'C2', 'L1', 'L2', 'L3', 'L4'))
    thin_after = min(thin_after, C_cryo_before)
    C['thin'].update(transmission=T_thin, cryo_after_W=thin_after, cryo_saved_W=C_cryo_before - thin_after,
                     refrig_saved_W=(C_cryo_before - thin_after) * cop20, status='OPTIONAL EXPERIMENTAL CONFIGURATION (owner 2026-11-24)')
    C['status'] = 'ARCHIVED (owner 2026-11-24): kept for its research; the thin blanket is the optional configuration'
    # B in detail (owner Q-TH-1, 2026-11-24): alignment budget, thermal bow, vibration, edge loading, integration
    CFC = dict(E=1.0e11, rho=1900.0, alpha=2.0e-6, k=300.0, strength=350e6)        # PROTOTYPE carbon-fibre composite, in-plane
    t_bl = P['edge_m']; Lr = depth                                                   # blade thickness and radial span (cantilever)
    f1 = 1.875 ** 2 / (2 * math.pi * Lr ** 2) * math.sqrt(CFC['E'] * t_bl ** 2 / (12 * CFC['rho']))
    q_edge = inp['pulse']['xray_J'] * Hz / (4 * math.pi * rho_c ** 2)              # steady X-ray flux on a blade edge at the cage radius
    F_edge = inp['pulse']['xray_J'] / (4 * math.pi * rho_c ** 2)                    # per pulse
    dT_edge = sum(F_edge * w * mu for _, w, mu in mu_spec(spec, 'C_diamond')) / (1900 * 1800.0)
    budget = [dict(term='Target miss at the burn point', mrad=psi_B * 1e3, source='vertex_engine.structure.target_miss_tolerance_m over 9 m'),
              dict(term='Mount and assembly tolerance', mrad=0.05, source='PROTOTYPE (survey-grade alignment)'),
              dict(term='Thermal bow, 1 K face-to-face difference', mrad=CFC['alpha'] * 1.0 / t_bl * Lr * 1e3 / 2, source='alpha dT / t over the span'),
              dict(term='Vibration (first mode, 1 um tip amplitude)', mrad=1e-6 / Lr * 1e3, source='PROTOTYPE amplitude')]
    psi_tot = math.sqrt(sum(b_['mrad'] ** 2 for b_ in budget)) * 1e-3
    dT_allow = (P['miss_m'] / rho_c) * 2 * t_bl / (CFC['alpha'] * Lr)
    keep_tot = (P['edge_m'] + depth * psi_tot * (1 - R_spec(spec, psi_tot))) / D_mean
    B['detail'] = dict(
        blade=dict(material='CFC with a replaceable tungsten-carbon edge strip (PROTOTYPE)', thickness_m=t_bl, span_m=Lr, width_m=D_mean,
                   f1_Hz=f1, pulse_Hz=Hz, f1_over_pulse=f1 / Hz),
        alignment=dict(budget=budget, psi_total_mrad=psi_tot * 1e3, keep_share_at_budget=keep_tot, removed_at_budget_W=B_heat * (1 - keep_tot),
                       face_dT_allowed_K=dT_allow,
                       note=f'The blade must hold its plane on the burn point to about {psi_B * 1e3:.2f} mrad. Thermal bow dominates: a face-to-face '
                            f'difference of only {dT_allow:.2f} K bends a {Lr:.1f} m blade that far, so both faces are cooled together and an active '
                            f'root actuator (sensed by the engine controller from the edge temperature map) trims the plane between pulses.'),
        vibration=dict(f1_Hz=f1, note=f'The first bending mode ({f1:.0f} Hz) is far below the {Hz:,.0f} Hz pulse rate, so each pulse is a quasi-static '
                                      'load on the low modes; the risk is the dense high-order modes near the pulse rate and its harmonics, which '
                                      'need damping in the root joint (PROTOTYPE: constrained-layer dampers at every root).'),
        edge=dict(steady_W_m2=q_edge, per_pulse_J_m2=F_edge, dT_per_pulse_K=dT_edge, over_limit=q_edge / P['q_limit_W_m2'],
                  thermal_stress_Pa=CFC['E'] * CFC['alpha'] * dT_edge, stress_over_strength=CFC['E'] * CFC['alpha'] * dT_edge / CFC['strength'],
                  note=f'Edge-on concentrates what is left on the edge: {q_edge / 1e9:.1f} GW/m2 steady, {q_edge / P["q_limit_W_m2"]:,.0f} times a lithium-cooled '
                       f'face can take, and a {dT_edge:,.0f} K jump each pulse. The edge is a sacrificial, replaceable strip on lithium-cooled roots.'),
        integration=dict(actuator_t=0.1 * B['mass_t'], note='Blades bolt to the cage hoops, which become cones with their apex at the burn point; '
                         'every blade root carries a lithium manifold tap, an actuator and a damper; edge strips change on the service rail.'))
    # warm (intermediate) circuit: NaK at 650 -> 850 K for the parts the hot loop does not reach (vessel outer walls, blade roots,
    # manifold supports, driver-optic housings); what it takes after B and the thin blanket is booked here
    T_w_in, T_w_out = 650.0, 850.0; cp_nak = 880.0
    warm_load = B['heat_after_W'] * 0.2 + sum(c_['total_W'] for c_ in comps if c_['id'] == 'OPTICS')
    q_w = SIGMA_SB * 0.85 * T_w_out ** 4
    warm = dict(fluid='NaK-78 (PROTOTYPE)', inlet_K=T_w_in, outlet_K=T_w_out, load_W=warm_load, mdot_kg_s=warm_load / (cp_nak * (T_w_out - T_w_in)),
                radiator_m2=warm_load / q_w, radiator_t=warm_load / q_w * P['radiator_kg_m2'] / 1000,
                note='Intermediate circuit between the hot lithium and the cryostats: blade roots (a fifth of what B leaves), driver-optic housings, '
                     'vessel outer walls and manifold supports. Its radiator runs at 850 K, so every watt it takes costs about 20 times the area '
                     'of the hot radiator; it is sized small on purpose.')
    # D: integrated grazing nozzle photonics
    D_rows = []
    for c in ('C1', 'C2', 'L1', 'L2', 'L3', 'L4'):
        coil = next(cc for cc in st['coils'] + st['loops'] if cc['name'] == c)
        d = math.hypot(coil['x'] - bx, coil['r']); a = coil['cryostat_minor_m'] + 0.38
        need_psi = a / d / P['D_eff']                                  # deflect the band clear (2 psi d >= 2 a) with psi = D_eff theta_c
        share = sum(w for E, w in spec if mpn.theta_c('Pt', E) >= need_psi)
        Emax = None
        for k in range(400):
            E = 0.01 * 1.03 ** k
            if mpn.MATS['Pt']['rows'][0]['E_keV'] > E:
                continue
            if mpn.theta_c('Pt', E) < need_psi:
                Emax = E; break
        lowest = mpn.MATS['Pt']['rows'][0]['E_keV']
        D_rows.append(dict(id=c, distance_m=d, half_width_m=a, psi_needed_mrad=need_psi * 1e3, theta_c_1keV_mrad=mpn.theta_c('Pt', 1.0) * 1e3,
                           E_max_keV=Emax, below_data=Emax is None or Emax <= lowest, spectrum_share=share))
    D = dict(id='D', title='Integrated grazing photonics in the nozzle (deflector collars, source-pointing liners)', rows=D_rows,
             reflected_W=sum(x['spectrum_share'] for x in D_rows) * XW / len(D_rows) * pickup,
             liner_far_ir='Metal bore liners return far-IR synchrotron light in the STEADY regime (as A); in the coupled target pulse the '
                          'synchrotron share is not modelled (OPEN).',
             mass_t=0.0, verdict='NO BENEFIT (HARD SPECTRUM)',
             why='To steer a ray clear of a coil, a grazing mirror must turn it by about the coil\'s angular width (0.1-0.2 rad here); X-ray '
                 f'mirrors turn rays by at most twice the critical angle (Pt: {D_rows[0]["theta_c_1keV_mrad"]:.0f} mrad at 1 keV, falling as 1/E), which never reaches it inside the R2-B spectrum. '
                 'No deflector inside the engine envelope removes measurable heat.')
    cop20_ = cop20
    comparison = [
        dict(id='BASE', title='Drawn engine, no mirrors', acts='Reference', hot_W=Q_hot, warm_W=Q_warm, cryo_W=Q_cryo_n, removed_W=0.0, moved_W=0.0,
             cryo_saved_W=0.0, refrig_saved_W=0.0, mass_t=0.0, verdict='Reference', why='Heat on this engine at the coupled pulse.'),
        dict(id='A', title=A['title'], acts='X-rays at grazing angles below a few mrad; far-IR (steady regime)', removed_W=A_refl, moved_W=0.0,
             cryo_saved_W=0.0, refrig_saved_W=0.0, steady_removed_W=A['steady_absorbed_B4C_face'] - A['steady_absorbed_W_face'], mass_t=A['mass_t'],
             verdict=A['verdict'], why=A['why']),
        dict(id='B', title=B['title'], acts='Structure the burn sees edge-on', removed_W=B['removed_W'], moved_W=0.0, cryo_saved_W=0.0,
             refrig_saved_W=0.0, mass_t=B['mass_t'], verdict=B['verdict'], why=B['why']),
        dict(id='C', title=C['title'] + ' (archived)', acts='X-rays, neutrons and strikes on the coils', removed_W=0.0, moved_W=C_moved,
             cryo_saved_W=C_cryo_before - C_cryo_after, refrig_saved_W=(C_cryo_before - C_cryo_after) * cop20_, mass_t=C['mass_t'],
             thin_mass_t=C['thin']['mass_t'], verdict=C['verdict'] + ' (ARCHIVED)', why=C['why']),
        dict(id='Ct', title='Thin blanket on every coil (optional experimental configuration)', acts='X-rays and strikes on the bare cryostats',
             removed_W=0.0, moved_W=C_moved, cryo_saved_W=C['thin']['cryo_saved_W'], refrig_saved_W=C['thin']['refrig_saved_W'],
             mass_t=C['thin']['mass_t'], verdict='OPTION: MOVES HEAT, NEUTRONS PASS',
             why=C['thin']['note'] + f' It cools the bare cryostat walls ({C_moved / 1e12:.2f} TW into lithium instead of into uncooled parts), but the 20 K '
                 f'load stays at {C["thin"]["cryo_after_W"] / 1e9:.1f} GW because the neutrons pass (the full blanket: {C_cryo_after / 1e9:.1f} GW).'),
        dict(id='D', title=D['title'], acts='Soft X-rays below about 0.1 keV; far-IR (steady regime)', removed_W=D['reflected_W'], moved_W=0.0,
             cryo_saved_W=0.0, refrig_saved_W=0.0, mass_t=D['mass_t'], verdict=D['verdict'], why=D['why']),
    ]
    after = Q_hot + Q_warm - B['removed_W']
    comparison.append(dict(id='B+Ct', title='Edge-on structure and the thin blanket (current direction)', acts='Structure and bare cryostats',
                           removed_W=B['removed_W'], moved_W=C_moved, cryo_saved_W=C['thin']['cryo_saved_W'], refrig_saved_W=C['thin']['refrig_saved_W'],
                           mass_t=B['mass_t'] + C['thin']['mass_t'], heat_after_W=after, cryo_after_W=C['thin']['cryo_after_W'],
                           refrig_after_W=C['thin']['cryo_after_W'] * cop20_, over_budget_after=after / inp['budget_W'],
                           over_budget_before=(Q_hot + Q_warm) / inp['budget_W'], verdict='CURRENT DIRECTION, NOT CLOSED',
                           why=f'The owner\'s current direction (2026-11-24): B on the cage and the 248 t blanket as an option. The engine still takes '
                               f'{after / inp["budget_W"]:,.0f} times its radiator share; the next lever is the source (Q-TH-3).'))
    comparison.append(dict(id='B+C', title='Edge-on structure and layered blankets together', acts='Everything the trace finds',
                           removed_W=B['removed_W'], moved_W=C_moved, cryo_saved_W=C_cryo_before - C_cryo_after,
                           refrig_saved_W=(C_cryo_before - C_cryo_after) * cop20_, mass_t=B['mass_t'] + C['mass_t'], heat_after_W=after,
                           cryo_after_W=C_cryo_after, refrig_after_W=C_cryo_after * cop20_, over_budget_after=after / inp['budget_W'],
                           over_budget_before=(Q_hot + Q_warm) / inp['budget_W'], verdict='NOT CLOSED',
                           why=f'Together they take {B["removed_W"] / (Q_hot + Q_warm):.0%} of the heat off this engine and cut the 20 K load '
                               f'{C_cryo_before / max(C_cryo_after, 1):.0f}-fold, for {B["mass_t"] + C["mass_t"]:,.0f} t per engine. The engine still takes '
                               f'{after / inp["budget_W"]:,.0f} times its radiator share, and its windings still need {C_cryo_after * cop20_ / 1e9:,.0f} GW of refrigeration.'))
    flow = energy_flow(pl, Hz, Q_hot, Q_warm, Q_cryo_n, other_W, sec_total, hot, cryo)
    # optics curves for the inspector: best-coating reflectivity against grazing angle, per energy and for the whole spectrum
    psis = [10 ** (-2 + 5 * i / 40) * 1e-3 for i in range(41)]          # 0.01 mrad .. 1 rad
    Es = [3.0, 10.0, 30.0, 100.0, 300.0]
    optics = dict(psi_mrad=[x * 1e3 for x in psis], E_keV=Es, R=[[mpn.best_R(E, x, P['sigma_rough_m'])[0] for x in psis] for E in Es],
                  R_spectrum=[R_spec(spec, x) for x in psis], theta_c_mrad={str(E): mpn.theta_c('Pt', E) * 1e3 for E in Es},
                  note='Best of ten coatings per energy, 0.5 nm roughness, single reflection (Fresnel, mpn.py). Neutrons are not reflected at any '
                       'angle that matters; charged particles are not reflected by mirrors.')
    for c in comps:
        ps = sorted(x for (cc, sf), dd in comp.items() if cc == c['id'] for x in dd['psi'])
        tot_ = sum(sh for _, sh in ps); acc_ = 0.0; c['psi_median_deg'] = None
        for psi_, sh in ps:
            acc_ += sh
            if acc_ >= tot_ / 2:
                c['psi_median_deg'] = math.degrees(psi_); break
        c['psi_min_deg'] = math.degrees(ps[0][0]) if ps else None
    geo = geometry(s, comps, surf, hot, cryo)
    return dict(study='lab/studies/vertex-compact-engine/vertex-thermal', cls='CALCULATED', fi_inputs_hash=inp['fi_hash'], params=P, state='COUPLED',
                state_note='The COUPLED pulse of the Fusion Ignition ledger (R2-B design target at the design rate, C1 nozzle shares).',
                powers=dict(fusion_W=pl['fusion_W'], xray_W=XW, neutron_W=NW, charged_hit_W=HW, jet_W=pl['jet_W'], budget_W=inp['budget_W'], Hz=Hz),
                spectrum=[dict(E_keV=E, share=w) for E, w in spec], reconcile=recon, surfaces=surf, components=comps, other_W=other_W,
                secondary_W=sec_total, pulsed=pulsed, hot=hot, cryo=cryo, strategies=dict(A=A, B=B, C=C, D=D), comparison=comparison, warm=warm,
                flow=flow, geometry=geo, paths=flow_paths(s) + getattr(network, 'paths', []), optics=optics)


def energy_flow(pl, Hz, Q_hot, Q_warm, Q_cryo, other_W, sec, hot, cryo):
    """fusion -> particles and radiation -> hardware -> heat -> cooling -> space, and the exhaust path (W per engine)."""
    F = pl['fusion_W']; Hin = pl['heat_in_J'] * Hz; X = pl['xray_J'] * Hz; N = pl['neutron_J'] * Hz; Pp = pl['plasma_J'] * Hz
    jet = pl['jet_W']; hit = pl['hit_J'] * Hz; side = pl['side_J'] * Hz
    hw = Q_hot + Q_warm + Q_cryo
    nodes = [dict(id='fusion', label='Fusion', W=F), dict(id='driver', label='Driver heat into the fuel', W=Hin),
             dict(id='xray', label='X-rays', W=X), dict(id='neutron', label='Neutrons', W=N), dict(id='plasma', label='Charged plasma', W=Pp),
             dict(id='jet', label='Directed jet (thrust)', W=jet), dict(id='side', label='Side exhaust', W=side), dict(id='hit', label='Charged strikes on hardware', W=hit),
             dict(id='space_direct', label='Radiation past the engine (space and neighbour engines)', W=X + N - (hw - hit)),
             dict(id='absorbed', label='X-rays and neutrons absorbed by this engine', W=hw - hit),
             dict(id='other', label='Neighbour engines and cluster (ledger pickup minus this engine)', W=other_W),
             dict(id='hot', label='Hot circuit (lithium)', W=Q_hot), dict(id='warm', label='Warm parts with no coolant drawn', W=Q_warm),
             dict(id='cryo', label='20 K windings (refrigerator)', W=Q_cryo),
             dict(id='removed', label='Removed by the drawn lithium lines', W=hot['removed_W']),
             dict(id='deficit', label='Heat the network cannot carry', W=hot['deficit_W']),
             dict(id='radiator', label='Rejected by radiators to space', W=hot['removed_W']),
             dict(id='refrig', label='Refrigerator input power', W=cryo['refrig_W'])]
    absorbed_rad = hw - hit
    links = [('fusion', 'xray', X), ('fusion', 'neutron', N), ('fusion', 'plasma', Pp - Hin), ('driver', 'plasma', Hin),
             ('plasma', 'jet', jet), ('plasma', 'side', side), ('plasma', 'hit', hit),
             ('xray', 'space_direct', X + N - absorbed_rad), ('xray', 'hot', None), ('hit', 'hot', None), ('hot', 'removed', hot['removed_W']), ('hot', 'deficit', Q_hot - min(Q_hot, hot['removed_W'])),
             ('warm', 'deficit', Q_warm), ('removed', 'radiator', hot['removed_W']), ('cryo', 'refrig', Q_cryo)]
    return dict(nodes=nodes, links=[dict(a=a, b=b, W=w) for a, b, w in links],
                note='Watts per engine at the coupled pulse rate. The bars of one row add to its parent; the residual of the burn (0.25 %) is not drawn.')


def flow_paths(s):
    """Coolant paths of the drawn engine and the study's additions, ordered in the flow direction (for the page's flow animation)."""
    out = []
    for p in ve.parts(s):
        n = p['name']
        if p['shape'] != 'tube':
            continue
        if n.startswith('VTX_Lithium') or ('_Lithium_' in n):
            circ, rev = 'hot', ('Return' in n)
        elif 'Cryo' in n:
            circ, rev = 'cryo', False
        else:
            continue
        pts = [[round(v, 3) for v in q] for q in p['points']]
        out.append(dict(circuit=circ, name=n, points=pts[::-1] if rev else pts))
    return out


# ---------- WORK geometry (engine frame) ---------------------------------------------------------------------------------------------

def geometry(s, comps, surf, hot, cryo):
    """Primitives for the WORK hardware: torus (x, R, a, arc), tube (points, radius), revolve (profile, arc, closed), box, ribbon."""
    g = ve.config(s)['geometry']; st = ve.stations(s); bx = st['burn']; out = []
    pol = ve.pol
    def add(layer, comp, kind, **k):
        out.append(dict(layer=layer, comp=comp, kind=kind, **{a: (round(b, 4) if isinstance(b, float) else b) for a, b in k.items()}))
    coils = st['coils'] + st['loops']
    for c in coils:
        cm = c['cryostat_minor_m']; phi = math.atan2(c['r'], c['x'] - bx)
        off = cm + g['armour_offset_m'] + g['armour_minor_m']; sx, sr = c['x'] - off * math.cos(phi), c['r'] - off * math.sin(phi)
        # A: coating band on the shoe (loops) or LiH nose (closure coils)
        aa = g['armour_minor_m'] if c['name'].startswith('L') else 0.16
        if c['name'].startswith('C'):
            sx, sr = c['x'] - (cm + 0.055) * math.cos(phi), c['r'] - (cm + 0.055) * math.sin(phi)
        add('mirror_A', c['name'], 'torus', x=sx, R=sr, a=aa + 0.012, note='Strategy A: Pt-coated burn face (X-ray grazing and far-IR mirror)')
        # C: layered blanket, burn-facing half section, revolved; layers as nested half annuli
        r0 = cm; prof_layers = []
        for name, t, rho_, role in reversed(STACK[:-1]):
            pass
        rad = cm
        for name, t, rho_, role in reversed(STACK):
            if name == 'Cryostat vessel wall':
                continue
        acc = cm
        for name, t, rho_, role in list(reversed(STACK))[1:]:
            r_in, r_out = acc, acc + t
            n = 14; ang = [phi + math.pi - math.pi / 2 + math.pi * k / n for k in range(n + 1)]   # half facing the burn (centred on -phi dir)
            outer = [(c['x'] + r_out * math.cos(a_), c['r'] + r_out * math.sin(a_)) for a_ in ang]
            inner = [(c['x'] + r_in * math.cos(a_), c['r'] + r_in * math.sin(a_)) for a_ in reversed(ang)]
            add('blanket_C', c['name'], 'revolve', profile=[(round(x, 4), round(y, 4)) for x, y in outer + inner], closed=True, arc=[20.0, 340.0],
                layer_name=name, t_m=t)
            acc = r_out
        # cryo: 80 K screen inside the vacuum space, quench line to the dump banks
        add('cryo', c['name'], 'torus', x=c['x'], R=c['r'], a=cm * 0.82, arc=[30.0, 330.0], note='80 K thermal screen (cooled, inside the cryostat vacuum)')
        rt = c['r'] + cm
        add('cryo_quench', c['name'], 'tube', points=[pol(c['x'], rt + 0.45, 270 if c['name'].startswith('C') else 90),
                                                       pol(c['x'] + 1.0, rt + 0.9, 250), pol(-6.5, 4.7, 200), pol(-5.9, 4.05 + 0.65, 180)], radius=0.05,
            note='Quench dump line: coil current to the warm resistor bank on the pulse pod (never the lithium loop)')
    # B: source-aligned blades on the cage longerons (ribbons toward the burn point)
    for j in range(g['cage_longerons']):
        az = 22.5 + j * 360 / g['cage_longerons']
        pts = [pol(x, rr, az) for x, rr in ve.cage_points(s)]
        inner = []
        for p_ in pts:
            v = (p_[0] - bx, p_[1], p_[2]); L = math.sqrt(sum(x * x for x in v)); d = 0.9
            inner.append(tuple(p_[i] - d * v[i] / L for i in range(3)))
        add('mirror_B', 'CAGE', 'ribbon', a=[list(map(lambda q: round(q, 4), p_)) for p_ in pts], b=[list(map(lambda q: round(q, 4), p_)) for p_ in inner],
            note='Strategy B: source-aligned blade fairing on a longeron (plane through the burn point, 30 mm edge)')
    # D: deflector collar and source-pointing liners (drawn to show where they would sit, shown as ineffective)
    for c in st['loops'][2:]:
        th = math.atan2(c['r'] - c['cryostat_minor_m'] - 0.6, c['x'] - bx)
        r1, r2 = 4.0, math.hypot(c['x'] - bx, c['r']) - c['cryostat_minor_m'] - 0.8
        add('mirror_D', c['name'], 'revolve', profile=[(round(bx + r1 * math.cos(th), 4), round(r1 * math.sin(th), 4)), (round(bx + r2 * math.cos(th), 4), round(r2 * math.sin(th), 4))],
            closed=False, arc=[0.0, 360.0], note='Strategy D: source-pointing grazing liner (soft X-ray and far-IR), in front of ' + c['name'])
    # hot circuit additions: armour channel jackets, heat exchanger, pumps, link to the ship's HOT radiator
    sp = ve.service_panel(s)
    add('hot', 'HX', 'box', center=pol(sp['x'] + 0.2, sp['r_out'] + 0.9, 180), size=[1.6, 1.2, 2.4], az=180,
        note='Lithium-to-cluster heat exchanger (intermediate loop, keeps the engine lithium in the engine)')
    for j, az in enumerate((160, 200)):
        add('hot', 'PUMP', 'box', center=pol(-8.9, 4.6 + 0.45, az), size=[0.7, 0.6, 0.7], az=az, note='Electromagnetic lithium pump (one per feeder)')
    add('hot', 'LINK', 'tube', points=[pol(sp['x'] + 0.2, sp['r_out'] + 1.5, 180), pol(-4.0, 7.2, 180), pol(2.0, 7.2, 180), pol(6.0, 9.0, 180)], radius=0.18,
        note='Intermediate loop to the ship HOT radiator (the cluster thrust ring service lines)')
    add('hot', 'SHIELD', 'torus', x=st['shield_aft'] + 0.25, R=5.2, a=0.09, note='Shield face lithium ring header')
    for c in st['loops']:
        phi = math.atan2(c['r'], c['x'] - bx); cm = c['cryostat_minor_m']; off = cm + g['armour_offset_m'] + g['armour_minor_m']
        add('hot', c['name'], 'torus', x=c['x'] - off * math.cos(phi), R=c['r'] - off * math.sin(phi), a=g['armour_minor_m'] - 0.02,
            note=f'{c["name"]} armour channel jacket (lithium 1500 -> 1800 K under the shoe face)')
    # cryo additions: refrigerator on the cartridge, its rejection line to the LOW radiator
    add('cryo', 'PLANT', 'box', center=pol(-4.6, 3.4 + 0.55, 270), size=[3.0, 1.1, 1.6], az=270, note='Cryogenic refrigerator (20 K and 80 K stages)')
    add('cryo', 'PLANT', 'tube', points=[pol(-4.6, 4.0, 270), pol(-8.6, 5.2, 270)], radius=0.08, note='Refrigerator to the coil cryogen header')
    add('cryo', 'LOWRAD', 'tube', points=[pol(-3.2, 4.1, 270), pol(-1.0, 4.6, 270), pol(4.0, 6.5, 270)], radius=0.1,
        note='Refrigerator rejection to the LOW radiator circuit (300 K)')
    network(s, add, out)
    return out


def network(s, add, out):
    """The integrated engine of 2026-11-24 (owner Q-TH-1/Q-TH-2): edge-on blades and cones on the whole cage, supermirror assemblies with
    their substrates, supports and cooling, the thin coil blanket (the full blanket stays as an archived layer), a coherent hot lithium
    network (supply and return rings, longeron feeders, hoop branches, nose jackets), a NaK warm circuit for blade roots and housings, an
    independent cryogenic network (supply and return headers, coil feeds), links to the ship's HOT, WARM and LOW radiators, and the
    service interfaces (rail, edge-strip ports, quick-disconnect couplings, blanket lugs). PROTOTYPE positions inside the drawn envelope."""
    g = ve.config(s)['geometry']; st = ve.stations(s); bx = st['burn']; pol = ve.pol
    cage = ve.cage_points(s); nl = g['cage_longerons']; azs = [22.5 + j * 360 / nl for j in range(nl)]
    loops = st['loops']; coils = st['coils']
    def ray(x, r, d):                                   # move a meridian point by d along the ray from the burn point
        vx, vr_ = x - bx, r; L = math.hypot(vx, vr_)
        return x + d * vx / L, r + d * vr_ / L
    def path(circuit, name, pts):
        out_paths.append(dict(circuit=circuit, name=name, points=[[round(v, 3) for v in q] for q in pts]))
    out_paths = network.paths = []
    # ---- edge-on blades and cones (strategy B, adopted) ----
    for j, az in enumerate(azs):
        pts = [pol(x, rr, az) for x, rr in cage]
        edge = [pol(*ray(x, rr, -0.9), az) for x, rr in cage]
        add('blades', 'EDGE', 'tube', points=edge, radius=0.018, note='Replaceable edge strip (W/C, lithium-cooled root): the only face the burn sees')
    for c in loops:
        hp = next(p for p in ve.parts(s) if p['name'] == f'VTX_Cage_Hoop_{c["name"]}')
        x1, r1 = ray(hp['x'], hp['R'], -0.55); x2, r2 = ray(hp['x'], hp['R'], 0.55)
        add('blades', 'CONE', 'revolve', profile=[(round(x1, 4), round(r1, 4)), (round(x2, 4), round(r2, 4))], closed=False, arc=[0.0, 360.0],
            note=f'Hoop {c["name"]} re-formed as a cone with its apex at the burn point (seen edge-on)')
        for k in range(8):
            sp_ = next(p for p in ve.parts(s) if p['name'] == f'VTX_Loop_Seat_{c["name"]}_{k + 1}')
            a_ = [list(q) for q in sp_['points']]
            b_ = []
            for q in a_:
                v = (q[0] - bx, q[1], q[2]); L = math.sqrt(sum(t * t for t in v)); b_.append([q[i] - 0.45 * v[i] / L for i in range(3)])
            add('blades', 'SEAT', 'ribbon', a=[[round(t, 4) for t in q] for q in a_], b=[[round(t, 4) for t in q] for q in b_],
                note=f'Seat blade {c["name"]}-{k + 1}: plane through the burn point')
        for j, az in enumerate(azs):
            add('blades', 'ROOT', 'box', center=pol(hp['x'], hp['R'] + 0.42, az), size=[0.5, 0.36, 0.5], az=az,
                note='Blade root: alignment actuator, constrained-layer damper and lithium tap')
    for c in coils:
        for k in range(6):
            sp_ = next(p for p in ve.parts(s) if p['name'] == f'VTX_{c["name"]}_Strut_{k + 1}')
            a_ = [list(q) for q in sp_['points']]; b_ = []
            for q in a_:
                v = (q[0] - bx, q[1], q[2]); L = math.sqrt(sum(t * t for t in v)); b_.append([q[i] - 0.35 * v[i] / L for i in range(3)])
            add('blades', 'STRUT', 'ribbon', a=[[round(t, 4) for t in q] for q in a_], b=[[round(t, 4) for t in q] for q in b_],
                note=f'{c["name"]} strut blade: plane through the burn point')
    # ---- supermirror assemblies: substrate behind each coating, liner panels with supports and cooling ----
    for gg in [q for q in out if q['layer'] == 'mirror_A']:
        add('mirror_A', gg['comp'] + '_SUB', 'torus', x=gg['x'], R=gg['R'], a=gg['a'] + 0.03,
            note='Mirror substrate: W/CFC backing with lithium micro-channels under the Pt multilayer')
    for c in loops[2:]:
        th = math.atan2(c['r'] - c['cryostat_minor_m'] - 0.6, c['x'] - bx)
        r2 = math.hypot(c['x'] - bx, c['r']) - c['cryostat_minor_m'] - 0.8; rm = 0.5 * (4.0 + r2)
        xm, rr = bx + rm * math.cos(th), rm * math.sin(th)
        for k in range(12):
            azk = [15 + 30 * k - 13 + 26 * q / 4 for q in range(5)]
            ia = [[round(t, 4) for t in pol(bx + 4.2 * math.cos(th), 4.2 * math.sin(th), a_)] for a_ in azk]
            ob = [[round(t, 4) for t in pol(bx + (r2 - 0.2) * math.cos(th), (r2 - 0.2) * math.sin(th), a_)] for a_ in azk]
            add('mirror_D', 'PANEL', 'ribbon', a=ia, b=ob,
                note=f'Grazing liner panel {c["name"]}-{k + 1}: Pt/C multilayer on a cooled SiC plate, faces along the rays')
        xe, re_ = bx + r2 * math.cos(th), r2 * math.sin(th)
        add('mirror_D', 'PANEL', 'torus', x=xe, R=re_ + 0.12, a=0.07, note='Liner cooling ring (lithium, on the hot network)')
        for az in azs[::2]:
            add('mirror_D', 'SUPPORT', 'tube', points=[pol(xe, re_ + 0.12, az), pol(c['x'], c['r'] + c['cryostat_minor_m'] + 0.5, az)], radius=0.05,
                note='Liner support spoke to the loop seat ring')
    # ---- thin blanket (optional configuration) ----
    thin = [x for x in STACK if x[0] not in ('W/B4C shield', 'LiH moderator', 'Cryostat vessel wall')]
    for c in coils + loops:
        cm = c['cryostat_minor_m']; phi = math.atan2(c['r'], c['x'] - bx); acc = cm
        for name, t, rho_, role in reversed(thin):
            n = 14; ang = [phi + math.pi / 2 + math.pi * k / n for k in range(n + 1)]
            o_ = [(c['x'] + (acc + t + 0.004) * math.cos(a_), c['r'] + (acc + t + 0.004) * math.sin(a_)) for a_ in ang]
            i_ = [(c['x'] + acc * math.cos(a_), c['r'] + acc * math.sin(a_)) for a_ in reversed(ang)]
            add('blanket_thin', c['name'], 'revolve', profile=[(round(x, 4), round(y, 4)) for x, y in o_ + i_], closed=True, arc=[20.0, 340.0],
                layer_name=name, t_m=t)
            acc += t + 0.004
    # ---- hot lithium network ----
    xs, Rs = -11.0, 5.55; xr, Rr = -11.6, 6.05
    add('hot', 'HOT_RING', 'torus', x=xs, R=Rs, a=0.17, note='Hot supply ring manifold (lithium 1500 K)')
    add('hot', 'HOT_RING_R', 'torus', x=xr, R=Rr, a=0.17, note='Hot return ring manifold (lithium 1800 K)')
    sp = ve.service_panel(s)
    add('hot', 'HOT_RING', 'tube', points=[pol(sp['x'], sp['r_out'] + 0.9, 180), pol(xs, Rs, 180)], radius=0.16, note='Heat exchanger to supply ring')
    add('hot', 'HOT_RING_R', 'tube', points=[pol(xr, Rr, 188), pol(sp['x'] + 0.3, sp['r_out'] + 1.1, 188)], radius=0.16, note='Return ring to heat exchanger')
    path('hot', 'hx_to_ring', [pol(sp['x'], sp['r_out'] + 0.9, 180), pol(xs, Rs, 180)])
    for j, az in enumerate(azs):
        sup = [pol(xs, Rs, az)] + [pol(x, rr - 0.55, az + 4) for x, rr in cage[1:]]
        ret = [pol(x, rr + 0.62, az - 4) for x, rr in cage[1:]][::-1] + [pol(xr, Rr, az)]
        add('hot', 'HOT_FEED', 'tube', points=sup, radius=0.09, note='Longeron supply feeder (lithium 1500 K)')
        add('hot', 'HOT_FEED_R', 'tube', points=ret, radius=0.09, note='Longeron return feeder (lithium 1800 K)')
        path('hot', f'feed_{j}', sup); path('hot', f'return_{j}', ret)
        for c in loops:
            phi = math.atan2(c['r'], c['x'] - bx); off = c['cryostat_minor_m'] + g['armour_offset_m'] + g['armour_minor_m']
            jx, jr = c['x'] - off * math.cos(phi), c['r'] - off * math.sin(phi) - g['armour_minor_m']
            hp = next(p for p in ve.parts(s) if p['name'] == f'VTX_Cage_Hoop_{c["name"]}')
            br = [pol(hp['x'], hp['R'] - 0.55, az + 4), pol(jx, jr, az + 4)]
            add('hot', 'HOT_BRANCH', 'tube', points=br, radius=0.05, note=f'{c["name"]} jacket branch (supply)')
            path('hot', f'br_{c["name"]}_{j}', br)
    for c in coils:
        cm = c['cryostat_minor_m']; phi = math.atan2(c['r'], c['x'] - bx)
        jx, jr = c['x'] - (cm + 0.09) * math.cos(phi), c['r'] - (cm + 0.09) * math.sin(phi)
        add('hot', c['name'] + '_JACKET', 'torus', x=jx, R=jr, a=0.06, note=f'{c["name"]} nose jacket (lithium under the LiH nose and blanket face)')
        for k in range(6):
            az = 30 + 60 * k
            br = [pol(xs, Rs, az), pol(jx, jr, az)]
            add('hot', 'HOT_BRANCH', 'tube', points=br, radius=0.045, note=f'{c["name"]} nose branch from the supply ring')
            path('hot', f'br_{c["name"]}_{k}', br)
    # ---- warm NaK circuit ----
    xw, Rw = -10.9, 6.5
    add('warm', 'WARM_RING', 'torus', x=xw, R=Rw, a=0.11, note='Warm ring manifold (NaK 650 -> 850 K)')
    for c in loops:
        hp = next(p for p in ve.parts(s) if p['name'] == f'VTX_Cage_Hoop_{c["name"]}')
        add('warm', 'WARM_HOOP', 'torus', x=hp['x'] + 0.3, R=hp['R'] + 0.55, a=0.05, note=f'Hoop {c["name"]} warm line: blade roots and dampers')
    for j, az in enumerate(azs):
        rs = [pol(xw, Rw, az - 9)] + [pol(x + 0.3, rr + 0.55, az - 9) for x, rr in cage[1:]]
        add('warm', 'WARM_RISER', 'tube', points=rs, radius=0.05, note='Warm riser along the longeron')
        path('warm', f'warm_{j}', rs)
    lk = [pol(xw, Rw, 90), pol(-6.0, 8.0, 90), pol(2.0, 8.6, 90), pol(6.0, 9.6, 90)]
    add('warm', 'WARM_LINK', 'tube', points=lk, radius=0.12, note="Warm loop to the ship's WARM radiator zone")
    path('warm', 'warm_link', lk[::-1])
    # ---- independent cryogenic network ----
    xc, Rc = -9.6, 3.7; xcr, Rcr = -9.95, 3.95
    add('cryo', 'CRYO_NET', 'torus', x=xc, R=Rc, a=0.07, note='Cryogen supply header (20 K helium)')
    add('cryo', 'CRYO_NET', 'torus', x=xcr, R=Rcr, a=0.07, note='Cryogen return header')
    for c in coils + loops:
        cm = c['cryostat_minor_m']
        for side, (xh, Rh, dz) in enumerate(((xc, Rc, -6), (xcr, Rcr, 6))):
            for az0 in (90, 270):
                az = az0 + dz
                if c['name'].startswith('C'):
                    pts = [pol(xh, Rh, az), pol(c['x'] + 0.2, c['r'] + cm + 0.12, az)]
                else:
                    pts = [pol(xh, Rh, az), pol(-12.0, 6.2, az)] + [pol(x, rr - 0.3, az) for x, rr in cage[1:] if x >= c['x'] - 1.0] +                           [pol(c['x'], c['r'] + cm + 0.12, az)]
                add('cryo', 'CRYO_NET', 'tube', points=pts, radius=0.035, note=f'{c["name"]} cryogen {"supply" if side == 0 else "return"} line')
                path('cryo', f'cryo_{c["name"]}_{side}_{az0}', pts if side == 0 else pts[::-1])
    # ---- service interfaces ----
    add('service', 'RAIL', 'torus', x=-10.9, R=7.3, a=0.06, note='Service rail: the exchange carriage runs here to reach every blade root and coupling')
    for j, az in enumerate(azs):
        add('service', 'PORT', 'box', center=pol(cage[-1][0] + 0.4, cage[-1][1] - 0.2, az), size=[0.45, 0.4, 0.6], az=az,
            note='Edge-strip exchange port (the strip slides out along the longeron)')
        for k, (x_, R_) in enumerate(((xs, Rs), (xr, Rr))):
            add('service', 'COUPLING', 'box', center=pol(x_ - 0.3, R_, az + (4 if k == 0 else -4)), size=[0.3, 0.3, 0.3], az=az,
                note='Quick-disconnect coupling (remote handling) between ring and feeder')
    for c in coils + loops:
        cm = c['cryostat_minor_m']
        for k in range(4):
            add('service', 'LUG', 'box', center=pol(c['x'], c['r'] + cm + 0.25, 45 + 90 * k), size=[0.22, 0.22, 0.22], az=45 + 90 * k,
                note=f'{c["name"]} blanket segment lift lug')


def main():
    d = build()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(d, separators=(',', ':'), default=float))
    pw = d['powers']; h = d['hot']; cr = d['cryo']; rc = d['reconcile']
    print(f"X {pw['xray_W'] / 1e12:.2f} TW, n {pw['neutron_W'] / 1e9:.0f} GW, hits {pw['charged_hit_W'] / 1e12:.2f} TW per engine")
    print(f"sky: geometry {rc['geometry_sky']:.3f}, ledger pickup {rc['ledger_pickup']:.3f}, escape {rc['escape']:.3f}")
    for c in d['components']:
        print(f"  {c['id']:7s} sky {c['sky']:.4f} area {c['area_m2']:7.1f} m2  hot {c['hot_W'] / 1e9:9.1f} GW warm {c['warm_W'] / 1e9:8.1f} GW cryo {c['cryo_W'] / 1e6:8.1f} MW  armoured {c['armoured_share']:.2f}")
    print(f"hot {h['heat_W'] / 1e12:.2f} TW, warm uncooled {h['warm_uncooled_W'] / 1e12:.2f} TW; drawn lines carry {h['drawn_line_cap_W'] / 1e9:.2f} GW ({h['drawn_line_over']:.0f}x); "
          f"pipe r at 10 m/s {h['pipe_radius_10ms_m']:.1f} m; radiator {h['radiator_m2']:.3g} m2 ({h['radiator_over_ship']:.0f}x ship), pump {h['pump_W'] / 1e9:.1f} GW")
    for x in h['rows']:
        print(f"  {x['id']:6s} flux {x['flux_W_m2'] / 1e6:9.0f} MW/m2 ({x['flux_W_m2'] / x['q_limit_W_m2']:.0f}x)  v needed {x['v_needed_m_s']:.3g} m/s  B {x['B_T']:.1f} T  dp MHD bare {x['dp_mhd_bare_Pa'] / 1e6:.1f} MPa fci {x['dp_mhd_fci_Pa'] / 1e6:.2f} MPa")
    print(f"cryo 20 K {cr['stage20_W'] / 1e6:.2f} MW, 80 K {cr['stage80_W'] / 1e3:.0f} kW, refrigeration {cr['refrig_W'] / 1e9:.2f} GW")
    for p in d['pulsed']['materials']:
        print(f"  pulse {p['material']:9s} dT {p['dT_surface_K']:.3g} K depth {p['mean_depth_m'] * 1e6:.0f} um survives {p['survives']}")
    for p in d['pulsed']['points'][:3]:
        print(f"  pulse {p['comp']:6s} {p['surface']:7s} F {p['fluence_J_m2'] / 1e6:.2f} MJ/m2  dT {p['dT_surface_K']:.3g} K  depth {p['mean_depth_m'] * 1e6:.0f} um")
    for k, v in d['strategies'].items():
        print(f"  {k}: {v['verdict']}  mass {v['mass_t']:.1f} t  " + v['why'][:160])
    print(f"Brayton: {h['brayton']['electric_W'] / 1e12:.2f} TW electric, driver covered {h['brayton']['driver_covered']:.1f}x, radiator x{h['brayton']['radiator_over_direct']:.1f}")


if __name__ == '__main__':
    main()
