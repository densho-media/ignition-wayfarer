"""PSA Phase I screening study (STUDY / NONCANON, analytical, never structural proof).

Reads the PSA data libraries in work/primary-structural-architecture/data/, the production mass placement (src/wayfarer/mass_model.py,
unchanged) and the ISSA Phase VI results at the pinned commit ISSA_SHA (read through `git show`, never merged), and writes
results/psa_phase1.json.

What it calculates (first-order, every assumption named in the output):
  1. reference configurations P (production), F1 (ISSA Track F reference) and R (ISSA Track R), kept apart;
  2. the running axial compression N(x) along the ship from distributed inertial loads (thrust x mass ahead of the station / total mass)
     for every state of each configuration, against the canon 1.5 g design envelope;
  3. material design allowables (track R and F separately) and efficiency indices;
  4. longeron screening mass per material, configuration and rail topology (strength, local tube buckling, global stiffness bounds);
  5. thermal screens: structure temperature near the 1800 K blades and hot trunks, stand-off heat leak, ship-length thermal growth,
     CTE-mismatch strains;
  6. magnetic screens: ferromagnetic force density and eddy heating in pulsed fields;
  7. thrust-transfer outriggers for widely separated engines; ring spin-up and locking loads;
  8. resource energy of structure by material mix;
  9. coupled-mass sensitivity (departure tonnes per structure tonne) per configuration;
 10. concept evaluation: normalised criteria, three documented weight sets, Pareto front.

    python3 work/primary-structural-architecture/psa_study.py
"""
import json
import math
import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'src/wayfarer'))
from spec import load  # noqa: E402
import mass_model as mm  # noqa: E402
import habitat_ring  # noqa: E402
import layout  # noqa: E402

MAIN_SHA = '11f1e94f1c36a6e53835343c3ad645ff7da8f2d5'
ISSA_SHA = '5eae7016c1c31631c9437b2d7d06aa30b740a374'
G0 = 9.80665
OUT = HERE/'results/psa_phase1.json'


def toml(name):
    return tomllib.loads((HERE/'data'/name).read_text())


def git_json(sha, path):
    return json.loads(subprocess.check_output(['git', 'show', f'{sha}:{path}'], cwd=ROOT))


# ------------------------------------------------------------------------------------------------ 1. configurations and mass placement
def parts_state(s, left):
    st = mm.stores_at(s, left)
    return mm.dry_parts(s)+mm.propellant_parts(s, st['he3'], st['d2'], st['h2'], True)


def issa_configs():
    p6 = git_json(ISSA_SHA, 'work/ship-systems-architecture/results/phase6.json')
    out = {}
    for k in ('F1', 'R'):
        c = p6['configs'][k] if k in p6['configs'] else None
        if c is None:
            cf = git_json(ISSA_SHA, 'work/ship-systems-architecture/results/phase6_config_F.json')
            c = cf[k]
        i = 1  # nominal case
        out[k] = dict(id=c['id'], track=c['track'], departure_t=c['mass']['departure_t'][i], end_t=c['mass']['end_t'][i],
                      propellant_t=c['mass']['propellant_t'][i], dry_added_t=c['mass']['dry_added_t'][i],
                      items_t={n: v[i] for n, v in c['items_t'].items()}, hot_loop=c['hot_loop']['topology'],
                      L2=c['generation']['L2'], accel=[a for a in p6['accel'].get(k, []) if a['case'] == 'nom'])
    return out, p6


def config_parts(s, cfg, prod_dry_t, prop_P_kg, left):
    """ISSA configuration as placed parts: the production dry ship, ISSA dry additions at their districts, the remaining end-mass gap as
    tankage on the farm, and the production propellant pattern scaled to the configuration's propellant (PROTOTYPE placement)."""
    parts = mm.dry_parts(s)
    hot = sum(v for n, v in cfg['items_t'].items() if n.startswith('hot loop'))*1e3
    l2 = sum(v for n, v in cfg['items_t'].items() if n.startswith('L2 ('))*1e3
    other = sum(v for n, v in cfg['items_t'].items() if not n.startswith('hot loop') and not n.startswith('L2 ('))*1e3
    parts.append(mm._part('ISSA_hot_loop', hot, -140.0, 30.0, ['cyl', 5.5]))
    parts.append(mm._part('ISSA_L2_district', l2, -92.0, -80.0, ['cyl', 3.0]))
    parts.append(mm._part('ISSA_other_systems', other, -112.0, 48.0, ['cyl', 4.0]))
    gap = cfg['end_t']*1e3-prod_dry_t*1e3-hot-l2-other
    if gap > 0:
        parts.append(mm._part('ISSA_tankage_and_balance', gap, 109.25, 137.85, ['cyl', 5.0]))
    scale = cfg['propellant_t']*1e3/prop_P_kg
    st = mm.stores_at(s, left)
    for p in mm.propellant_parts(s, st['he3'], st['d2'], st['h2'], True):
        q = dict(p); q['m'] = p['m']*scale; parts.append(q)
    return parts, gap


def axial_profile(parts, thrust_N, x_thrust, grid):
    """Compression at station x: a * (mass ahead of x), a = T / M. Parts aft of the thrust ring hang on it (tension, not counted)."""
    M = sum(p['m'] for p in parts); a = thrust_N/M; out = []
    for x in grid:
        ahead = 0.0
        for p in parts:
            x0, x1 = p['x']
            if x1 <= x:
                continue
            ahead += p['m'] if x0 >= x else p['m']*(x1-x)/max(x1-x0, 1e-9)
        out.append(a*ahead)
    return dict(M_kg=M, a_g=a/G0, N=out)


# ------------------------------------------------------------------------------------------------ 3. materials
def kT(m, T):
    tab = m.get('k_T')
    if not tab:
        return 1.0
    tab = sorted(tab)
    if T <= tab[0][0]:
        return tab[0][1]
    for (t0, f0), (t1, f1) in zip(tab, tab[1:]):
        if T <= t1:
            return f0+(f1-f0)*(T-t0)/(t1-t0)
    return 0.0


def allowable(m, meta, T=293.0, joint='parent', process='wrought'):
    f = meta['factors']; jf = meta['joint_factors'][joint]; pf = meta['process_factors'][process]
    base = min(m['Fty']/f['FS_y'], m['Ftu']/f['FS_u']) if m.get('Fty') else m['Ftu']/f['FS_u']
    comp = min(m.get('Fcy', m['Fty'])/f['FS_y'], m['Ftu']/f['FS_u'])
    k = kT(m, T)
    return dict(tension_MPa=base*k*jf*pf, compression_MPa=comp*k*jf*pf, k_T=k)


def indices(m):
    r = m['rho']; E = m['E']*1e9
    return dict(E_rho=E/r/1e6, sigma_rho=m.get('Ftu', 0)*1e6/r/1e3, column=math.sqrt(E)/r, panel=E**(1/3)/r,
                thermal_distortion=m.get('alpha', 0)/m.get('k', 1))


# ------------------------------------------------------------------------------------------------ 4. longeron screening
def tube_area(P_N, F_allow_Pa, E_Pa, Lb, kd, FS_b=1.4, D_t=40.0):
    """Area of one thin tube (D/t fixed) carrying P: max of strength and local Euler buckling over the frame bay."""
    A_s = P_N/F_allow_Pa
    # I = A r^2 / 2 with A = pi D t = pi D^2 / D_t  ->  r^2 = D_t A / (4 pi);  P_cr = pi^2 E I / Lb^2
    A_b = Lb*math.sqrt(P_N*FS_b*8.0/(math.pi*E_Pa*kd*D_t))
    return max(A_s, A_b), ('strength' if A_s >= A_b else 'bay buckling')


def longeron_mass(N_profile, grid, mat, meta, n_rails, T_zone, joint, process, Lb=4.0, DLF=1.3):
    kd = meta['factors']['buckling_knockdown_tube']
    al = allowable(mat, meta, T_zone, joint, process)['compression_MPa']*1e6
    E = mat['E']*1e9*kT(mat, T_zone)
    m = 0.0; gov = {}
    for i in range(len(grid)-1):
        N = max(N_profile[i], N_profile[i+1])*DLF
        P = N/n_rails
        if P <= 0:
            continue
        A, g = tube_area(P, al, E, Lb, kd)
        dx = grid[i+1]-grid[i]; m += n_rails*A*mat['rho']*dx; gov[g] = gov.get(g, 0.0)+dx
    return m, gov


def global_bounds(EI_needed_coef, N, L):
    """EI for static Euler (pinned, pi^2) and follower-thrust free-free (Beal 1965, ~109.9) bounds, FS 3."""
    return dict(EI_euler=3*N*L*L/math.pi**2, EI_follower=3*N*L*L/109.9)


def f1_free_free(EI, mu, L):
    return 4.730**2/(2*math.pi*L*L)*math.sqrt(EI/mu)


# ------------------------------------------------------------------------------------------------ 5. thermal
SIGMA = 5.670374e-8


def member_T(T_src, F, alpha_hot, eps_emit, T_sink=3.0):
    return ((alpha_hot*F*T_src**4+eps_emit*T_sink**4)/eps_emit)**0.25


def standoff_leak(k, A, L, Th, Tc):
    return k*A*(Th-Tc)/L


def main():
    s = load(ROOT)[0]
    mats = toml('materials.toml'); procs = toml('processes.toml'); joints = toml('joints.toml'); res = toml('resources.toml')
    meta = mats['meta']; M = {m['id']: m for m in mats['material']}
    concepts = toml('concepts.toml'); lcs = toml('load_cases.toml'); iface = toml('interface.toml'); own = toml('mass_ownership.toml')
    probs = toml('problems.toml'); road = toml('roadmap.toml')

    # ---------------- configurations
    rep = mm.report(s)
    dep, burn, dry = rep['departure'], rep['burnout'], rep['dry_ship']
    T_flight = dep['thrust_N']; T_design = s['propulsion']['design_thrust']['value']*1e6
    x_ring = layout.at(s, s['prototype']['thrust_ring_x'])
    x_fwd = layout.at(s, {'datum': 'FWD', 'offset_m': 0.0})
    prop_P = dep['propellant_kg']
    issa, p6 = issa_configs()
    grid = [x_ring+i*2.0 for i in range(int((x_fwd-x_ring)/2.0)+1)]

    states = {}
    states['P_departure'] = axial_profile(parts_state(s, 1.0), T_flight, x_ring, grid)
    states['P_burnout'] = axial_profile(parts_state(s, rep['burnout']['mission_left']), T_flight, x_ring, grid)
    states['P_dry_end'] = axial_profile(parts_state(s, 0.0), T_flight, x_ring, grid)
    # Canon structural design envelope (07!A2: 1.5 g at 2,000 t) applied the way the tank deck study applied it: 1.5 g on the full ship.
    full = parts_state(s, 1.0); Mf = sum(p['m'] for p in full)
    states['P_canon_1p5g_full'] = axial_profile(full, 1.5*G0*Mf, x_ring, grid)
    gaps = {}
    for k, c in issa.items():
        for tag, left in (('departure', 1.0), ('end', 0.0)):
            parts, gap = config_parts(s, c, dry['mass_kg']/1e3, prop_P, left)
            states[f'{k}_{tag}'] = axial_profile(parts, T_flight, x_ring, grid); gaps[k] = gap
    env = {}
    for cfg in ('P', 'F1', 'R'):
        keys = [k for k in states if k.startswith(cfg+'_') and 'canon' not in k]
        env[cfg] = [max(states[k]['N'][i] for k in keys) for i in range(len(grid))]

    def at(profile, x):
        i = min(range(len(grid)), key=lambda j: abs(grid[j]-x)); return profile[i]
    x_ringA = habitat_ring.centers(s)[0]
    stations = {'thrust ring +8 m (transition)': x_ring+8.0, 'midbody X 0': 0.0, 'radiator front X 48.9': 48.9,
                'aft of ring A X 90': 90.0, 'tank farm aft face X 109': 109.0, 'shield root X 138': 138.0}
    station_table = {name: {k: at(v['N'], x)/1e6 for k, v in states.items()} for name, x in stations.items()}

    # ---------------- materials
    mat_table = {}
    for m in mats['material']:
        if m['track'] not in ('R', 'F') or 'E' not in m or 'Ftu' not in m:
            continue
        mat_table[m['id']] = dict(track=m['track'], name=m['name'], family=m['family'], lunar=m.get('lunar'),
                                  magnetic=m.get('magnetic', 'NON'), T_max=m.get('T_max'),
                                  allow_293=allowable(m, meta), allow_150=allowable(m, meta, 150.0),
                                  allow_400=allowable(m, meta, 400.0), indices=indices(m))

    # ---------------- longeron screening (production envelope, F1, R; zone temperature 150-350 K inside the casing: use 350 K)
    screen_mats = ['R-AL6061', 'R-AL5083', 'R-ALLI2195', 'R-ALSC', 'R-TI64', 'R-STHSLA', 'R-ST316LN', 'R-CFRP-IM', 'R-CFRP-TP',
                   'R-ALAL2O3F', 'R-BFRP', 'F-ALSC-NANO', 'F-CNT-CFRP']
    # member bodies are wrought/extruded parent material; joints are carried by the node and splice factors (concepts), not here
    jp = {'AL': ('parent', 'wrought'), 'TI': ('parent', 'wrought'), 'STEEL_F': ('parent', 'wrought'),
          'STEEL_A': ('parent', 'wrought'), 'CFRP_TS': ('parent', 'afp_thermoset_autoclave'),
          'CFRP_TP': ('parent', 'afp_thermoplastic_in_situ'), 'MMC_AL': ('parent', 'wrought'),
          'BFRP': ('parent', 'afp_thermoset_autoclave')}
    jp_override = {'F-ALSC-NANO': ('parent', 'dED_hip_machined')}
    screening = {}
    envelopes = dict(P_flight=env['P'], P_canon_1p5g=states['P_canon_1p5g_full']['N'], F1_flight=env['F1'], R_flight=env['R'])
    for mid in screen_mats:
        m = M[mid]
        mm_ = dict(m)
        if m['family'] in ('CFRP_TS', 'CFRP_TP') and 'laminates' in m:
            lam = m['laminates']['tube_0_45']; mm_.update(E=lam['E'], Ftu=lam['Ftu'], Fty=lam['Ftu'], Fcy=lam['Fcu'])
        if mid == 'F-CNT-CFRP':
            mm_.update(E=105.0, Ftu=1450, Fty=1450, Fcy=1000)
        j, pr = jp_override.get(mid, jp.get(m['family'], ('parent', 'wrought')))
        row = {}
        for ename, prof in envelopes.items():
            for n in (3, 6):
                mass, gov = longeron_mass(prof, grid, mm_, meta, n, 350.0, j, pr)
                row[f'{ename}_{n}rail_t'] = mass/1e3
                row[f'{ename}_{n}rail_governs'] = max(gov, key=gov.get) if gov else None
        screening[mid] = dict(track=m['track'], name=m['name'], joint=j, process=pr, **row)

    # global stiffness: production departure, 3 rails at r 5 m, aluminium sized by P_flight
    L_c = 109.0-x_ring
    N_peak = max(env['P']); gb = global_bounds(None, N_peak*1.3, L_c)
    r_rail = s['structure']['sector_radius_m']; sum_y2 = 1.5*r_rail**2
    mu = dep['mass_kg']/(x_fwd-(-144.75))
    stiff = {}
    for mid in ('R-AL6061', 'R-TI64', 'R-CFRP-IM', 'R-ALAL2O3F'):
        m = M[mid]; E = (m['laminates']['tube_0_45']['E'] if 'laminates' in m else m['E'])*1e9
        A_each_euler = gb['EI_euler']/(E*sum_y2); A_each_foll = gb['EI_follower']/(E*sum_y2)
        A_strength = N_peak*1.3/(allowable(m, meta, 350.0)['compression_MPa']*1e6)/3
        f1 = f1_free_free(E*3*A_strength*sum_y2/3*1.0, mu, 289.5) if False else f1_free_free(E*A_strength*sum_y2, mu, 289.5)
        stiff[mid] = dict(A_each_strength_m2=A_strength, A_each_euler_bound_m2=A_each_euler, A_each_follower_bound_m2=A_each_foll,
                          mass_euler_bound_t=3*A_each_euler*m['rho']*L_c/1e3, mass_strength_t=3*A_strength*m['rho']*L_c/1e3,
                          f1_strength_sized_Hz=f1)
    # how much does a wider structural radius help (bypass collar r 33-35 m, radiator root r 6.5, Q45)
    radius_trade = {f'r_{r}m': dict(A_each_euler_Al_m2=gb['EI_euler']/(M['R-AL6061']['E']*1e9*1.5*r*r)) for r in (5.0, 6.5, 10.0, 20.0, 35.0)}

    # ---------------- thermal screens
    thermal = {}
    thermal['frame_near_blade_K'] = {f'F={F}': dict(black=member_T(1800, F, 0.9, 0.9), low_alpha_coating=member_T(1800, F, 0.15, 0.85),
                                                    with_single_shield=member_T(member_T(1800, F, 0.9, 0.9), 0.5, 0.15, 0.85))
                                     for F in (0.01, 0.05, 0.1, 0.25, 0.5)}
    thermal['blade_backbone_K'] = 'inside a two-faced 1800 K emitting blade the backbone sees hot sheet on both sides: ~1650-1800 K unless it is moved to the root band or wrapped in refractory multifoil'
    thermal['hot_trunk_bare_flux_W_m2'] = 0.85*SIGMA*1990**4
    sup = dict(Inconel_flexure=standoff_leak(20.0, 3e-4, 0.25, 1990-900, 350)*0 + standoff_leak(20.0, 3e-4, 0.25, 900, 350),
               YSZ_pad=standoff_leak(2.2, 2e-3, 0.04, 1990, 900), )
    thermal['standoff_W'] = dict(note='two-stage stand-off: YSZ pad 1990->900 K (k 2.2, 20 cm2, 40 mm) then Inconel flexure 900->350 K (k 20, 3 cm2, 250 mm)',
                                 YSZ_stage_W=sup['YSZ_pad'], Inconel_stage_W=sup['Inconel_flexure'],
                                 n_supports_issa_h6a=sum(1 for e in p6['layout'] if e['name'].startswith('Support_')))
    L_ship = x_fwd-x_ring
    thermal['ship_growth_m'] = {mid: M[mid]['alpha']*1e-6*L_ship*150.0 for mid in ('R-AL6061', 'R-TI64', 'R-STHSLA', 'R-CFRP-IM', 'R-ALAL2O3F', 'R-CC')}
    thermal['ship_growth_note'] = f'free growth over the {L_ship:.0f} m thrust ring to shield span for a 150 K change (yard ~293 K to shadowed ~150 K)'
    fam_alpha = {'Al': 23.6, 'Ti': 8.6, 'Steel': 12.0, 'Stainless': 16.0, 'CFRP(0)': -0.4, 'CFRP(QI)': 2.0, 'Al2O3f/Al': 6.5, 'SiC/SiC': 4.5, 'C/C': 1.0, 'Mo': 5.3}
    thermal['cte_mismatch_mm_per_4m_per_100K'] = {f'{a}|{b}': abs(fam_alpha[a]-fam_alpha[b])*1e-6*4.0*100*1e3
                                                   for a in fam_alpha for b in fam_alpha if a < b}

    # ---------------- magnetic screens
    mu0 = 4e-7*math.pi
    magnetic = dict(ferro_force_density_N_m3={f'gradB={g} T/m': 1.7/mu0*g for g in (1e-3, 1e-2, 0.1, 1.0)},
                    eddy_W_m3={f'dB/dt={d} T/s, t={t*1e3:.0f} mm, Al': 2.5e7*d*d*t*t/12 for d in (0.1, 1.0, 10.0, 100.0) for t in (0.005, 0.02)},
                    rule='No ferromagnetic structure where |grad B| > ~1e-3 T/m (force density > 1.35 kN/m3, ~170 N per 100 kg of steel); break conductive loops with insulating joints (CN-12) where dB/dt > ~1 T/s.')

    # ---------------- thrust-transfer outriggers for separated engines (design thrust split over 4 engines)
    outr = {}
    Te = T_design/4
    for r_e in (2.6, 12.0, 15.0, 20.0, 30.0):
        lever = max(r_e-s['structure']['ring_node_radius_m'], 0.0)
        Mb = Te*lever
        for h in (3.0, 6.0):
            chord = Mb/h; A = chord/(allowable(M['R-TI64'], meta, 400.0)['tension_MPa']*1e6)
            outr[f'r{r_e}_h{h}'] = dict(moment_MN_m=Mb/1e6, chord_MN=chord/1e6, chord_mass_per_engine_t=2*A*lever*M['R-TI64']['rho']/1e3,
                                        engine_out_moment_MN_m=Te*r_e/1e6)

    # ---------------- rings
    d = habitat_ring.dynamics(s)
    rings = dict(mass_each_t=d['mass_each_kg']/1e3, H_each_N_m_s=d['angular_momentum_each_N_m_s'],
                 spin_torque_each_N_m=d['spin_torque_each_N_m'], spinup_1h_torque_N_m=d['angular_momentum_each_N_m_s']/3600,
                 locked_axial_each_MN_at_flight_peak=d['mass_each_kg']*max(T_flight/(rep['dry_ship']['mass_kg']), 0)/1e6,
                 high_thrust_axial_each_MN_canon=d['high_thrust_axial_load_each_N']/1e6,
                 centripetal_each_MN=d['centripetal_force_per_ring_N']/1e6,
                 latch_note='Spin-down/lock happens before thrust (operating_rules.habitat): latch loads are the axial inertial share plus residual-momentum capture (0.1 % H in 10 s: ~5 kN m), not the spin torque.')

    # ---------------- coupled mass sensitivity
    def coupling(dep_t, end_t, f_t=0.15):
        R = dep_t/end_t; return R/(1-f_t*(R-1)), R
    cfgs = {'P': (dep['mass_kg']/1e3, dry['mass_kg']/1e3), 'F1': (issa['F1']['departure_t'], issa['F1']['end_t']),
            'R': (issa['R']['departure_t'], issa['R']['end_t'])}
    f1 = issa['F1']; ratio_issa = (f1['departure_t']-4573.1)/(f1['end_t']-1683.6)
    sens = {k: dict(zip(('ddep_per_tonne', 'mass_ratio'), coupling(*v))) for k, v in cfgs.items()}
    sens['calibration'] = dict(issa_F1_extra_dep_per_extra_end=ratio_issa, f_t_assumed=0.15,
                               note='tankage grows with propellant (0.15 of propellant mass, calibrated against ISSA F1 nominal); mission delta-v fixed')

    # ---------------- resource energy for a 150 t, 300 t structure by mix
    energy = {}
    mixes = concepts['mix']
    for mx in mixes:
        e_lo = e_hi = imp = 0.0
        for mid, frac in mx['fractions'].items():
            m = M[mid]; btf = mx.get('buy_to_fly', {}).get(mid, 1.3)
            e_lo += frac*m['energy_kWh_kg'][0]*btf; e_hi += frac*m['energy_kWh_kg'][1]*btf
            imp += frac*{'LOCAL': 0.0, 'PARTIAL': 0.3, 'IMPORT': 1.0}[m.get('lunar', 'IMPORT')]
        energy[mx['id']] = dict(kWh_kg=[e_lo, e_hi], GWh_per_150t=[e_lo*150e3/1e6, e_hi*150e3/1e6], import_mass_fraction=imp, name=mx['name'])

    # ---------------- concept primary-structure mass build-up (first order)
    FIXED = dict(thrust_ring_and_transition=10.0, bypass_collar_Q45=25.0, brow_keels_and_hub_path=5.0, protective_casing=30.0)
    fixed_note = ('PROTOTYPE first-order items: 12-node ring + 8 m transition (~4-fold to 3-fold out-of-plane ring bending ~10 MN m at the '
                  'design thrust, Ti chords), bypass collar (3 girders r 33-35 m, X 72-116, ~16 MN of tank-farm and Brow load at flight), '
                  'Brow keels (125 t of shield + Eye), casing (~10,000 m2 at ~3 kg/m2 panels + straps). Ranges +-50 %.')
    al_ref = {}
    def lmass(prof, mix, rails, process=None, path=1.0):
        tot = 0.0
        for mid, frac in mix.items():
            m = dict(M[mid])
            if 'laminates' in m:
                lam = m['laminates']['tube_0_45']; m.update(E=lam['E'], Ftu=lam['Ftu'], Fty=lam['Ftu'], Fcy=lam['Fcu'])
            pr = process or {'CFRP_TP': 'afp_thermoplastic_in_situ', 'CFRP_TS': 'afp_thermoset_autoclave'}.get(m['family'], 'wrought')
            mass, _ = longeron_mass(prof, grid, m, meta, rails, 350.0, 'parent', pr)
            tot += frac*mass*path
        return tot/1e3

    def shell_mass(prof, mat, r, sandwich):
        m = M[mat]; E = m['E']*1e9; al = allowable(m, meta, 350.0)['compression_MPa']*1e6; tot = 0.0
        for i in range(len(grid)-1):
            N = max(prof[i], prof[i+1])*1.3
            t = max(N/(2*math.pi*r*al), math.sqrt(N/(2*math.pi*0.6*0.3*E)*1.4))
            tot += 2*math.pi*r*t*m['rho']*(grid[i+1]-grid[i])
        return tot*sandwich/1e3

    # concept G: propellant moved aft next to the shadow shield
    def shifted_profile(x0):
        out = {}
        for tag, left in (('dep', 1.0), ('end', rep['burnout']['mission_left'])):
            ps = []
            for p in parts_state(s, left):
                q = dict(p)
                if p['name'].startswith('tankage_') or p['name'].startswith('prop') or 'Fuel_Tank' in p['name'] or p['name'].startswith('he3') or p['name'].startswith('d2') or p['name'].startswith('h2'):
                    dx = x0-109.25; q['x'] = (p['x'][0]+dx, p['x'][1]+dx); q['c'] = (p['c'][0]+dx, p['c'][1], p['c'][2])
                ps.append(q)
            out[tag] = axial_profile(ps, T_flight, x_ring, grid)['N']
        return [max(a, b) for a, b in zip(out['dep'], out['end'])]
    prop_names = sorted({p['name'] for p in parts_state(s, 1.0)} - {p['name'] for p in mm.dry_parts(s)})
    concept_mass = {}
    for c in concepts['concept']:
        b = c['build']; row = {}
        for ename, prof in (('P_flight', env['P']), ('P_canon_1p5g', states['P_canon_1p5g_full']['N']), ('F1_flight', env['F1'])):
            if c['id'] == 'G':
                prof = shifted_profile(b['tanks_aft_x0']) if ename != 'P_canon_1p5g' else [n*3.0 for n in shifted_profile(b['tanks_aft_x0'])]
            ref = lmass(prof, {'R-AL6061': 1.0}, 3)
            if b.get('shell'):
                core = shell_mass(prof, b['material'], b['radius_m'], b['sandwich_factor'])
                fr = core*b['frames']; br = 0.0
            else:
                core = lmass(prof, b['longeron'], b['rails'], {'dED_hip_machined': 'dED_hip_machined'}.get(b.get('process')), b.get('path_factor', 1.0))
                fr = b['frames']*ref*b['frame_material']; br = b['bracing']*ref*b['frame_material']
            nodes = b['nodes']*(core+fr+br); asm = b['assembly']*(core+fr+br+nodes)
            fixed = dict(FIXED)
            if b.get('casing_credit'):
                fixed['protective_casing'] = 0.0
            if b.get('outriggers_r_m'):
                fixed['outriggers'] = 4*outr[f"r{b['outriggers_r_m']}_h6.0"]['chord_mass_per_engine_t']*2.5
            if c['id'] == 'G':
                fixed['bypass_collar_Q45'] = 10.0
            scale = 1.0 if ename != 'P_canon_1p5g' else 3.0
            fx = sum(v*(scale if k in ('thrust_ring_and_transition', 'bypass_collar_Q45') else 1.0) for k, v in fixed.items())
            row[ename] = dict(core_t=core, frames_t=fr, bracing_t=br, nodes_t=nodes, assembly_t=asm, fixed_t=fx, total_t=core+fr+br+nodes+asm+fx)
        concept_mass[c['id']] = row
    A_tot = concept_mass['A']['P_flight']['total_t']
    for c in concepts['concept']:
        c['scores']['mass'] = concept_mass[c['id']]['P_flight']['total_t']/A_tot
        c['mass_factor_computed'] = c['scores']['mass']

    # ---------------- concept evaluation
    crit = concepts['criteria']; cids = [c['id'] for c in concepts['concept']]
    def norm(cname, v):
        c = next(x for x in crit if x['id'] == cname); lo, hi = c['scale']
        z = (v-lo)/(hi-lo); return z if c['better'] == 'high' else 1-z
    scores = {}
    for c in concepts['concept']:
        scores[c['id']] = {k: norm(k, v) for k, v in c['scores'].items()}
    ranking = {}
    for ws in concepts['weights']:
        w = ws['w']; tot = sum(w.values())
        ranking[ws['id']] = sorted(((sum(w[k]*scores[cid][k] for k in w)/tot, cid) for cid in cids), reverse=True)
    # Pareto on (structural mass factor low, manufacturability high, repairability high)
    pts = {c['id']: (c['scores']['mass'], c['scores']['manufacturability'], c['scores']['repairability']) for c in concepts['concept']}
    def dominates(a, b):
        return a[0] <= b[0] and a[1] >= b[1] and a[2] >= b[2] and a != b
    pareto = [cid for cid in cids if not any(dominates(pts[o], pts[cid]) for o in cids if o != cid)]
    # weight sensitivity: sweep the mass weight in the lifecycle set
    sweep = []
    base = next(ws for ws in concepts['weights'] if ws['id'] == 'W-LIFECYCLE')['w']
    for wm in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5):
        w = dict(base); w['mass'] = wm; tot = sum(w.values())
        best = max(cids, key=lambda cid: sum(w[k]*scores[cid][k] for k in w)/tot)
        sweep.append(dict(mass_weight=wm, best=best))

    # ---------------- register checks (consistency, no silent zeros)
    checks = []
    ids = [m['id'] for m in mats['material']]
    if len(ids) != len(set(ids)):
        checks.append('duplicate material id')
    pids = {p['id'] for p in procs['process']}
    for m in mats['material']:
        for p in m.get('processes', []):
            if p not in pids:
                checks.append(f'{m["id"]} names unknown process {p}')
    for e in iface['equipment']:
        for k in ('mass_t', 'cg_m'):
            if k in e and e[k] == 0:
                checks.append(f'{e["id"]} {k} is zero (must be OPEN)')
    lc_ids = {l['id'] for l in lcs['case']}
    for c in concepts['concept']:
        for l in c.get('governing_cases', []):
            if l not in lc_ids:
                checks.append(f'{c["id"]} names unknown load case {l}')

    out = dict(status='STUDY / NONCANON (PSA Phase I analytical screening; not structural proof)',
               consulted=dict(main=MAIN_SHA, issa=ISSA_SHA, issa_branch='claude/cloud/ship-systems-architecture',
                              drive=['S&E 07_PRIMARY_STRUCTURE A1:H70', 'S&E 10_WAYFARER_MASS A1:H25', 'Technology 41_MATERIALS_MANUFACTURING',
                                     'Technology 43_SPACE_MANUFACTURING ISM-01..37', 'Culture 31_ARCHITECTURE', 'Economy 42_SPACE_ECONOMY'],
                              drive_read_utc='2026-11-28T08:05Z'),
               configs=dict(P=dict(id='PRODUCTION (main)', departure_t=dep['mass_kg']/1e3, burnout_t=burn['mass_kg']/1e3, dry_t=dry['mass_kg']/1e3,
                                   thrust_MN=T_flight/1e6, a_departure_g=T_flight/dep['mass_kg']/G0, a_dry_g=T_flight/dry['mass_kg']/G0,
                                   design_thrust_MN=T_design/1e6, canon_design_rule='1.5 g at 2,000 t (07!A2, DERIVED)',
                                   main_structure_t=150.0, rotating_allowance_t=25.0),
                            **{k: dict(v, tankage_gap_t=gaps[k]/1e3) for k, v in issa.items()}),
               axial=dict(grid_m=grid, x_thrust_ring=x_ring, states={k: dict(M_t=v['M_kg']/1e3, a_g=v['a_g'], N_MN=[n/1e6 for n in v['N']]) for k, v in states.items()},
                          envelope_MN={k: [n/1e6 for n in v] for k, v in env.items()}, stations_MN=station_table,
                          note='compression from inertial loads only (thrust x mass ahead / total mass); dynamic load factor 1.3 applied in sizing, not here'),
               materials=mat_table, longeron_screening=screening,
               global_stiffness=dict(column_length_m=L_c, N_design_MN=N_peak*1.3/1e6, bounds=gb, per_material=stiff, radius_trade=radius_trade,
                                     note='Static Euler (pinned) is a conservative lower bound on capacity; Beal follower-thrust free-free ~109.9 EI/L^2 an optimistic reference. The true limit couples thrust-vector control and elastic modes (Phase III).'),
               thermal=thermal, magnetic=magnetic, outriggers=outr, rings=rings, coupling=sens, resource_energy=energy,
               concept_mass=dict(fixed_items_t=FIXED, note=fixed_note, by_concept=concept_mass, propellant_part_names=prop_names),
               concepts=dict(scores=scores, ranking={k: [[round(a, 3), b] for a, b in v] for k, v in ranking.items()}, pareto=pareto, mass_weight_sweep=sweep),
               counts=dict(materials=len(mats['material']), processes=len(procs['process']), joint_pairs=len(joints['pair']),
                           connections=len(joints['connection']), deposits=len(res['deposit']), chains=len(res['chain']),
                           equipment=len(iface['equipment']), zones=len(iface['zone']), load_cases=len(lcs['case']),
                           ownership_rows=len(own['item']), concepts=len(concepts['concept']), problems=len(probs['problem']),
                           roadmap_phases=len(road['phase'])),
               checks=checks)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, default=float)+'\n')
    print(json.dumps(dict(stations=station_table, screening={k: {kk: (round(vv, 1) if isinstance(vv, float) else vv) for kk, vv in v.items() if kk.startswith('P_flight') or kk.startswith('F1') or kk.startswith('P_canon')} for k, v in screening.items()},
                          stiffness=stiff, coupling=sens, checks=checks), indent=1, default=lambda v: round(v, 3)))


if __name__ == '__main__':
    main()
