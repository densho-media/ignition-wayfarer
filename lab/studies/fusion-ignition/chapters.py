"""Chapter data for Fusion Engineering: From Nucleus to Engine (owner brief 2026-11-24 09:49Z). Standard library only.

model.build() calls build(s, d) after every other block exists, so each chapter reads the same component model and ledger the rest of
the page reads (one engine, one state). Nothing here changes a spacecraft parameter. Each block carries its class:

  matter      particles, charges, ionisation and gyroradii in the engine's own field (CALCULATED)
  unwanted    D-D branches, tritium and D-T secondaries: Bosch-Hale reactivities and rate ratios (CALCULATED), steady and pulsed kept apart
  mix         fuel ratio: the selective-fusion grid (steady), the pulse grid (target), the MPN V0-V3 sources (IMPORTED)
  accel       the accelerator-fusion study, PARKED negative (IMPORTED)
  spin        polarisation: cross-section factor, D-D suppression (disputed), steady grid and pulsed lever results kept apart
  radiation   each radiation type, whether a field or a mirror can steer it, where it is made and where it is absorbed
  optics      visible light on aluminium (Fresnel, CALCULATED) against X-rays (thermal study) and neutrons (critical angle)
  shapes      member shapes against the burn: intercepted heat per metre for the same structural section (CALCULATED, PROTOTYPE sizes)
  extraction  ENG-062 test-particle scan (vertex-extraction, IMPORTED copy) and the momentum-consistent frontier
  integration the cluster in the ship: attachment, feeds, cooling, radiators, thrust, braking, dust (SPEC and IMPORTED)
  compare     supported configurations against every metric, each with its problems and maturity
  concepts    rejected and archived concepts, kept visible
"""
import cmath
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'src' / 'wayfarer'))
sys.path.insert(0, str(HERE))
import vertex_radiation as vr  # noqa: E402
import ledger as LG  # noqa: E402

C = 299792458.0
QE = 1.602176634e-19
ME = 9.1093837015e-31
AMU = 1.66053906660e-27
MEV = 1e6 * QE
ASF = ROOT / 'lab/studies/accelerator-fusion/results/asf.json'
COMPACT = ROOT / 'lab/studies/vertex-compact-engine/vertex-compact/results/compact.json'
EXTRACT = sorted((HERE / 'imports').glob('extraction_*.json'))


def r3(x):
    if isinstance(x, float):
        return float(f'{x:.4g}')
    if isinstance(x, dict):
        return {k: r3(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [r3(v) for v in x]
    return x


def gyro(m, q, B, E_J=None, v=None):
    """Larmor radius of a particle moving perpendicular to B (relativistic), m; the speed as a fraction of c."""
    if E_J is not None:
        g = 1 + E_J / (m * C * C); v = C * math.sqrt(1 - 1 / g ** 2)
    else:
        g = 1 / math.sqrt(1 - (v / C) ** 2)
    return g * m * v / (abs(q) * B), v / C


def matter(d):
    B = d['engine']['B_burn_T']; pl = d['ledger']['pulse']
    v_deb = math.sqrt(2 * pl['plasma_J'] / pl['debris_kg'])
    parts = [dict(id='p', label='proton', Z=1, A=1, m_MeV=938.272, charge='+1'), dict(id='n', label='neutron', Z=0, A=1, m_MeV=939.565, charge='0'),
             dict(id='e', label='electron', Z=-1, A=0, m_MeV=0.511, charge='-1'), dict(id='D', label='deuteron (D)', Z=1, A=2, m_MeV=1875.613, charge='+1'),
             dict(id='He3', label='helium-3', Z=2, A=3, m_MeV=2808.391, charge='+2'), dict(id='He4', label='helium-4 (alpha)', Z=2, A=4, m_MeV=3727.379, charge='+2')]
    rows = []
    for lab, m, q, kw in (('14.7 MeV proton (product)', 1.00728 * AMU, QE, dict(E_J=14.68 * MEV)), ('3.67 MeV alpha (product)', 4.00151 * AMU, 2 * QE, dict(E_J=3.67 * MEV)),
                          (f'D in the expanding plasma ({v_deb / 1e3:,.0f} km/s)', 2.0141 * AMU, QE, dict(v=v_deb)), ('D at 70 keV (burning fuel)', 2.0141 * AMU, QE, dict(E_J=70e3 * QE)),
                          ('electron at 70 keV', ME, QE, dict(E_J=70e3 * QE))):
        r, beta = gyro(m, q, B, **kw); r1, _ = gyro(m, q, 1.0, **kw)
        rows.append(dict(particle=lab, r_m=r, r_1T_m=r1, beta=beta))
    return dict(cls='CALCULATED', B_T=B, particles=parts, ionise_eV=dict(D=13.6, He3=[24.59, 54.42]), gyro=rows,
                neutron='No charge: a field cannot turn it. It leaves in a straight line until it strikes a nucleus.',
                note=f'Gyroradii perpendicular to the {B:.2f} T field at the burn point (vacuum field, CALCULATED). Charged particles circle field lines; a field this strong '
                     'holds even the 14.7 MeV protons to circles well under a metre, which is why a magnetic nozzle can steer charged products at all.')


def unwanted(d, fusion):
    Ts = [10, 20, 30, 50, 70, 100, 150, 190]
    sv = {r: [vr.sigma_v(r, T) for T in Ts] for r in ('DHe3', 'DDn', 'DDp', 'DT')}
    ratio = [0.5 * (sv['DDn'][i] + sv['DDp'][i]) / sv['DHe3'][i] for i in range(len(Ts))]     # 1:1 by nuclei: n_D = n_He3
    g = fusion['grid']; f = fusion['fields']
    pick = lambda T, ds, pol='none': dict(zip(f, g[f'{pol}|thermal|{T:g}|{ds:.2f}']))
    st = pick(100, 0.5)
    L = d['ledger']; cell = L['grid']['cells'][L['grid']['design']]; pp = L['design']['particles']
    reactions = [
        dict(id='DHe3', eq='D + ³He → ⁴He (3.67 MeV) + p (14.68 MeV)', Q_MeV=18.35, neutrons=0, role='wanted: both products charged'),
        dict(id='DDp', eq='D + D → T (1.01 MeV) + p (3.02 MeV)', Q_MeV=4.03, neutrons=0, role='unwanted: makes tritium'),
        dict(id='DDn', eq='D + D → ³He (0.82 MeV) + n (2.45 MeV)', Q_MeV=3.27, neutrons=1, role='unwanted: a 2.45 MeV neutron'),
        dict(id='DT', eq='D + T → ⁴He (3.5 MeV) + n (14.1 MeV)', Q_MeV=17.59, neutrons=1, role='secondary: the bred tritium burns and gives a 14.1 MeV neutron'),
        dict(id='He3He3', eq='³He + ³He → ⁴He + 2 p', Q_MeV=12.86, neutrons=0, role='negligible at these temperatures (not computed)'),
    ]
    return dict(cls='CALCULATED', T_keV=Ts, sigma_v=sv, dd_per_dhe3=ratio, reactions=reactions,
                steady=dict(cls='CALCULATED', label='steady plasma, 100 keV, 1:1 (selective-fusion grid)', share_dd=st['share_dd'], share_dt=st['share_dt'],
                            neutron=st['neutron'], photon=st['photon']),
                pulse=dict(cls='CALCULATED', label='coupled target burn (R2-B), 70 keV start, 1:1', neutron_share=cell['neutron_J'] / cell['fusion_J'],
                           neutrons=cell.get('neutrons'), xray_share=cell['xray_J'] / cell['fusion_J'],
                           reactions={k: v for k, v in pp.items() if k in ('reactions', 'DHe3', 'DDn', 'DDp', 'DT')}),
                note='Two regimes kept apart: a steady plasma burns for seconds and its bred tritium has time to burn; the target burns for about '
                     f'{L["design"]["duration_s"] * 1e12:.0f} ps. Their shares are never combined.')


def mix(d, fusion, mpn_src):
    g = fusion['grid']; f = fusion['fields']; ax = fusion['axes']
    rows = []
    for T in (70.0, 100.0):
        Tn = min(ax['Ti'], key=lambda x: abs(x - T))
        for ds in ax['d_share']:
            v = dict(zip(f, g[f'none|thermal|{Tn:g}|{ds:.2f}']))
            rows.append(dict(T=Tn, d=ds, neutron=v['neutron'], photon=v['photon'], power=v['rel_power'], dd=v['share_dd']))
    L = d['ledger']; G = L['grid']
    pulse = []
    for mx in G['mix']:
        c = G['cells'].get(f'{G["design"].split("|")[0]}|{G["design"].split("|")[1]}|{mx:g}')
        if c:
            pulse.append(dict(mix=mx, fusion_J=c['fusion_J'], xray=c['xray_J'] / c['fusion_J'], neutron=c['neutron_J'] / c['fusion_J'],
                              plasma=c['plasma_J'] / c['fusion_J'], burn=c['burn_fraction']))
    V = {k: dict(name=v['name'], photon=v['photon'], neutron=v['neutron'], charged=1 - v['photon'] - v['neutron'], Te_keV=v['Te_keV'], evidence=v['evidence'])
         for k, v in mpn_src.items() if k in ('V0', 'V2', 'V3')}
    return dict(cls='CALCULATED', steady=rows, pulse=pulse, sources=V,
                lesson='Fewer deuterium nuclei mean fewer D-D neutrons, but also fewer D-3He reactions per cubic metre, a hotter-running mix for the '
                       'same power and, in the pulsed target, a larger X-ray share (helium carries two electrons per nucleus, deuterium one). '
                       'The neutron minimum is not the engine optimum.')


def accel():
    a = json.loads(ASF.read_text())
    co = [r for r in a['coulomb'] if r['Ecm_keV'] in (50, 100, 200, 400, 800)]
    rc = a['recirculation']; cl = a['collider_ledger']['present']; sc = a['scale']['rows'][0]
    return dict(cls='IMPORTED', source='lab/studies/accelerator-fusion/results/asf.json (PARKED, negative result accepted 2026-11-22)',
                coulomb=[dict(E_keV=r['Ecm_keV'], ratio=r['ratio'], recirc=r['recirc_per_fusion']) for r in co],
                recirc=dict(events=rc['coulomb_events_per_fusion'], restored=rc['restored_energy_per_fusion'], eta_needed=rc['eta_required_for_absorbed_budget']),
                collider=dict(heat_frac=cl['heat_frac'], radiator_multiple=cl['radiator_multiple']),
                scale=dict(case=sc['case'], current_A=sc['beam_current_A'], power_W=sc['processed_power_W']),
                kept='Selectivity: a fusion system can choose which nuclei meet and at what energy. The engine keeps that idea in its fuel mix, '
                     'polarisation and hot-ion start, not in beams.',
                why='At 400 keV a D and a 3He nucleus scatter about 60 times by Coulomb collisions for each fusion. Every scattering spreads the beams; '
                    'restoring them must recover about 99.997 % of the energy for the heat to fit the drive budget. No accelerator recovers energy that well.')


def spin(d, fusion):
    g = fusion['grid']; f = fusion['fields']
    pick = lambda pol: dict(zip(f, g[f'{pol}|thermal|100|0.50']))
    states = [dict(id='none', label='unpolarised', PD=0.0, PHe=0.0), dict(id='partial', label='partly polarised', PD=0.5, PHe=0.5),
              dict(id='high', label='highly polarised', PD=0.9, PHe=0.9), dict(id='ideal', label='fully aligned (ideal)', PD=1.0, PHe=1.0)]
    for s_ in states:
        s_['dhe3_x'] = 1 + 0.5 * s_['PD'] * s_['PHe']            # D (spin 1, vector) and 3He (spin 1/2) parallel: the J = 3/2 channel
    lv = {r['lever']: r for r in d['source']['levers']}
    pol = next((r for r in d['source']['levers'] if r['lever'] == 'polarisation'), None)
    base = d['source']['levers'][0]
    return dict(cls='MODEL-BASED', states=states,
                steady={k: dict(neutron=pick(k)['neutron'], photon=pick(k)['photon'], power=pick(k)['rel_power']) for k in ('none', 'polarised', 'polarised-dd')},
                pulsed=dict(label=pol['label'] if pol else 'not run', cls=pol['cls'] if pol else 'OPEN',
                            yield_x=pol['fusion_J'] / base['fusion_J'] if pol else None, xray=pol['xray_share'] if pol else None,
                            thrust_x=pol['engine']['thrust_N'] / base['engine']['thrust_N'] if pol else None,
                            heat_over=pol['engine']['heat_over'] if pol else None),
                dd=dict(range=[0.1, 1.0], cls='SPECULATIVE', note='Whether aligned deuterons suppress D-D fusion (the quintet state) is disputed in theory and '
                                                                   'unmeasured in a plasma; the page shows it as a range, never as a result.'),
                angular='Aligned spins also change where the products go: for full alignment they leave mostly at right angles to the spin axis '
                        '(about sin²θ), which a nozzle field along the same axis could use. MODEL-BASED.',
                survival='Preparation is established in the laboratory (optically pumped 3He, polarised HD ice held for days). Survival through '
                         'compression and a 10 ps burn is predicted, not shown (OPEN); in a steady plasma, wall recycling and field '
                         'fluctuations depolarise the fuel over seconds.')


def radiation(d):
    pl = d['ledger']['pulse']; F = pl['fusion_J']; nz = d['ledger']['nozzle']['C1|1']
    rows = [
        dict(id='charged', label='Charged products and plasma (p, α, D, ³He, electrons)', share=pl['plasma_J'] / F, field='yes: they circle field lines',
             mirror='no', made='in the target', absorbed=f'{nz["hit"]:.0%} strikes the nozzle hardware (C1)'),
        dict(id='xray', label='X-rays (bremsstrahlung from hot electrons)', share=pl['xray_J'] / F, field='no: no charge', mirror='only at grazing angles below a few mrad',
             made='in the target, by its own electrons', absorbed=f'{nz["pickup"]:.0%} of what leaves strikes this engine'),
        dict(id='neutron', label='Neutrons (D-D 2.45 MeV, D-T 14.1 MeV)', share=pl['neutron_J'] / F, field='no: no charge', mirror='no: MeV neutrons are not reflected',
             made='in the target', absorbed='through the hardware into the windings; only mass stops them'),
        dict(id='gamma', label='Gamma rays (from neutron capture)', share=None, field='no', mirror='no', made='in the hardware, after neutrons are captured',
             absorbed='in the hardware that made them (not computed)'),
        dict(id='ir', label='Infrared (hot hardware glowing)', share=None, field='no', mirror='yes: ordinary metal mirrors', made='in the hardware',
             absorbed='to space by radiators: this is how the heat leaves'),
    ]
    return dict(cls='CALCULATED', rows=rows, note='Fields steer only charges. Mirrors work for light and soft X-rays at grazing incidence, never for MeV neutrons.')


def optics(d):
    """Visible light (550 nm) on aluminium, Fresnel with n = 0.958 + 6.69i (CALCULATED), against the thermal study's X-ray curves; neutron
    critical angles for nickel and an m = 6 supermirror."""
    n = complex(0.958, 6.69); out = []
    for psi_deg in (0.05, 0.1, 0.3, 1, 3, 10, 30, 60, 90):
        th = math.radians(90 - psi_deg); ci = math.cos(th); st = math.sin(th)
        ct = cmath.sqrt(1 - (st / n) ** 2)
        rs = abs((ci - n * ct) / (ci + n * ct)) ** 2; rp = abs((ct - n * ci) / (ct + n * ci)) ** 2
        out.append(dict(psi_deg=psi_deg, R=(rs + rp) / 2))
    def lam(E_eV, m=1.67493e-27):
        return 6.62607015e-34 / math.sqrt(2 * m * E_eV * QE)
    # nickel: theta_c = lambda sqrt(N b / pi), N b = 9.41e14 m^-2 (Ni scattering-length density)
    nb = 9.41e14
    neut = [dict(label=l, E_eV=E, theta_c_mrad=lam(E) * math.sqrt(nb / math.pi) * 1e3, theta_c_m6_mrad=6 * lam(E) * math.sqrt(nb / math.pi) * 1e3)
            for l, E in (('cold neutron, 5 meV', 5e-3), ('thermal neutron, 25 meV', 0.025), ('D-D neutron, 2.45 MeV', 2.45e6), ('D-T neutron, 14.1 MeV', 14.1e6))]
    return dict(cls='CALCULATED', visible=out, neutrons=neut,
                note='A mirror reflects when the wave meets it below its critical angle. For visible light on metal that is every angle; for X-rays it '
                     'shrinks as 1/E (a few mrad at 10 keV, tenths at 100 keV); for MeV neutrons it is a ten-millionth of a radian.')


def shapes(d):
    """Heat a structural member intercepts per metre of length at 6 m from the burn, for the same load-carrying section (PROTOTYPE sizes):
    round tube 0.10 m, broad plate 0.34 x 0.03 m face-on, the same plate edge-on (faces at the alignment grazing angle), a cone member
    (grazing 2 mrad, the hoops), a truss of three 0.03 m rods, a member in the shield's shadow corridor (scattered only)."""
    T = d['thermal']; B = T['strategies']['B']; Bd = B['detail']; pl = d['ledger']['pulse']
    Px = pl['xray_J'] * pl['Hz']; r = 6.0; q = Px / (4 * math.pi * r * r)
    a_face = B['face_absorptance']; psi = Bd['alignment']['psi_total_mrad'] * 1e-3; w, t = B['member_width_m'], B['edge_m']
    rows = [dict(id='round', label='Round tube (0.10 m)', width_m=0.10, absorb=1.0),
            dict(id='broad', label='Broad plate, face-on', width_m=w, absorb=1.0),
            dict(id='edge', label='Same plate edge-on (adopted, B)', width_m=t + 2 * w * math.sin(psi), absorb=(t + 2 * w * math.sin(psi) * a_face) / (t + 2 * w * math.sin(psi))),
            dict(id='cone', label='Cone with its apex at the burn', width_m=w * math.sin(2e-3), absorb=a_face),
            dict(id='skeletal', label='Truss of three thin rods', width_m=3 * 0.03, absorb=1.0),
            dict(id='corridor', label='Member in the shield shadow corridor', width_m=0.10, absorb=0.0)]
    for x in rows:
        x['W_per_m'] = q * x['width_m'] * x['absorb']
    base = rows[0]['W_per_m']
    for x in rows:
        x['rel'] = x['W_per_m'] / base
    return dict(cls='CALCULATED', flux_W_m2=q, r_m=r, rows=rows, alignment=Bd['alignment'], vibration=Bd['vibration'], edge=Bd['edge'], blade=Bd['blade'],
                note='Per metre of member at 6 m from the burn; sizes PROTOTYPE. Edge-on and cone members pay only their edge and a grazing face; '
                     'a member in the shadow corridor sees only scattered light (not computed here).')


def extraction(d):
    if not EXTRACT:
        return dict(cls='OPEN', note='vertex-extraction has not been imported yet')
    x = json.loads(EXTRACT[-1].read_text())
    geo = {f"{g['topo']}|{g['dz']:g}|{g['mult']:g}": dict(topo=g['topo'], dz=g['dz'], mult=g['mult'], coil_t=g['coil_t'], stored_J=g['stored_J'], B_burn_T=g['B_burn_T'],
                                                         species={k: dict(hit=v['hit'], cos=v['cos'], err=v['err']) for k, v in g['species'].items()}) for g in x['geometries']}
    base_label = d['source']['levers'][0]['label']
    rows = [dict(geo=r['geo'], lever=r['lever'], cls=r['cls'], thrust_N=r['thrust_N'], exhaust_m_s=r['exhaust_m_s'], heat_over=r['heat_over'],
                 deposited_kg_s=r['deposited_kg_s'], hit=r['hit_share_plasma'], xray=r['xray_share'], fast=r['fast_impulse_share']) for r in x['rows']]
    T = x['topologies']
    geos = [dict(key=k, label=T[g['topo']], dz=g['dz'], mult=g['mult'], hit=g['species']['D']['hit'], eta=g['species']['D']['cos'], coil_t=g['coil_t'])
            for k, g in geo.items()]
    glab = {g['key']: f"{g['label']}, burn {g['dz']:+g} m, field x{g['mult']:g}" for g in geos}
    frontier = [dict(case=r['lever'], geo=glab.get(r['geo'], r['geo']), cls=r['cls'], thrust_N=r['thrust_N'], exhaust_m_s=r['exhaust_m_s'], heat_over=r['heat_over'],
                     deposited_kg_s=r['deposited_kg_s']) for r in x.get('frontier', [])]
    fnd = x.get('findings', [])
    return dict(cls='SAMPLED', geos=geos, frontier=frontier, finding=fnd[0] if fnd else '', source=f'{EXTRACT[-1].relative_to(ROOT)} (lab/studies/vertex-compact-engine/vertex-extraction extraction.py, {x["n_dir"]} directions per species)',
                topologies=x['topologies'], dz=x['dz'], mults=x['mults'], debris_speed_m_s=x['debris_speed_m_s'], geometries=geo, rows=rows,
                base_lever=base_label, old_vs_new=x['old_vs_new'], reconcile=x['reconcile'], findings=x.get('findings', []))


def integration(d, compact):
    n = d['need']; T = d['thermal']; c1 = compact['variants']['C1']; c4 = compact['variants']['C4']
    return dict(cls='SPEC', rows=[
        dict(id='attach', label='Attachment', value=f'four engines on a {24:.0f} m pitch, thrust ring at x {d["ship"]["thrust_ring"][0]:.1f} m', cls='SPEC'),
        dict(id='fuel', label='Fuel and propellant feed', value=f'{n["mass_flow_kg_s"]:.2f} kg/s at full thrust (D, ³He and hydrogen)', cls='SPEC'),
        dict(id='cool', label='Cooling', value=f'hot lithium to the ship radiators; the engine needs {T["hot"]["radiator_over_ship"]:,.0f}× their area', cls='IMPORTED'),
        dict(id='rad', label='Radiators', value='three blades at 30, 150 and 270°, edge-on to the burns', cls='SPEC'),
        dict(id='thrust', label='Thrust', value=f'{n["thrust_N"] / 1e6:.1f} MN needed; {4 * d["ledger"]["pulse"]["thrust_N"] / 1e6:.2f} MN modeled', cls='CALCULATED'),
        dict(id='brake', label='Braking', value=f'{n["burns"]} burns of {n["burn_d"]:.0f} days; the ship turns round, the engines face the destination', cls='SPEC'),
        dict(id='dust', label='Dust protection', value=f'passive screens and armour: {c1["dust_nominal_t"]:,.0f} t (C1 nominal), {c4["dust_nominal_t"]:,.0f} t (C4)', cls='IMPORTED'),
    ], ship_lit_W=c1['ship_lit_W'], rejected='The broad plasma shield (AMPN) was rejected; HIMS stays a later option for the forward stream.')


def compare(d, x):
    """Supported configurations against every metric. Every row comes from one model state; regimes are not mixed."""
    L = d['ledger']; S_ = d['source']; T = d['thermal']; cmpB = {r['id']: r for r in T['comparison']}
    cell = L['grid']['cells'][L['grid']['design']]
    def pulse_row(var, f):
        nz = L['nozzle'][f'{var}|{f}']; p = LG.pulse(cell, L['target_mass_kg'], L['design_Hz'], nz, nz['budget_W'])
        return dict(thrust_N=4 * p['thrust_N'], exhaust_m_s=p['exhaust_m_s'], heat_over=p['heat_over'], deposited_g_s=1e3 * p['deposited_kg_s'], xray=p['xray_J'] / p['fusion_J'])
    rows = [dict(id='C1', label='C1 as drawn, coupled pulse', cls='CALCULATED', maturity='L2', **pulse_row('C1', '1'), added_t=0, problems=['ENG-030', 'ENG-061', 'ENG-062', 'ENG-063'])]
    c4 = pulse_row('C4', '4'); rows.append(dict(id='C4', label='C4 compact package, field ×4', cls='SAMPLED', maturity='L2', **c4, added_t=None, problems=['ENG-030', 'ENG-033', 'ENG-036']))
    bc = cmpB.get('B+Ct')
    if bc:
        r0 = rows[0]; rows.append(dict(id='B+Ct', label='C1 with edge-on blades and the thin blanket', cls='IMPORTED', maturity='L2', thrust_N=r0['thrust_N'], exhaust_m_s=r0['exhaust_m_s'],
                                       heat_over=bc['over_budget_after'], deposited_g_s=r0['deposited_g_s'], xray=r0['xray'], added_t=bc['mass_t'], problems=['ENG-057', 'ENG-059']))
    be = S_['best']['engine']
    rows.append(dict(id='BEST', label='Best source case + tungsten tamper (C1)', cls='SPECULATIVE', maturity='L1', thrust_N=4 * be['thrust_N'], exhaust_m_s=be['exhaust_m_s'],
                     heat_over=be['heat_over'], deposited_g_s=1e3 * be.get('deposited_kg_s', 0.0), xray=S_['best']['xray_left_share'], added_t=None, problems=['ENG-061', 'ENG-062']))
    if x.get('rows'):
        bl = x['base_lever']; cand = [r for r in x['rows'] if r['lever'] == bl]
        b = min(cand, key=lambda r: r['heat_over'])
        rows.append(dict(id='TOPO', label=f'Design target, best nozzle topology ({b["geo"].replace("|", ", ")})', cls='SAMPLED', maturity='L2', thrust_N=4 * b['thrust_N'],
                         exhaust_m_s=b['exhaust_m_s'], heat_over=b['heat_over'], deposited_g_s=1e3 * b['deposited_kg_s'], xray=b['xray'], added_t=None, problems=['ENG-062', 'ENG-064']))
        allb = min(x['rows'], key=lambda r: r['heat_over'])
        rows.append(dict(id='FRONT', label=f'Lowest heat found: {allb["lever"]} ({allb["geo"].replace("|", ", ")})', cls=allb['cls'], maturity='L1', thrust_N=4 * allb['thrust_N'],
                         exhaust_m_s=allb['exhaust_m_s'], heat_over=allb['heat_over'], deposited_g_s=1e3 * allb['deposited_kg_s'], xray=allb['xray'], added_t=None,
                         problems=['ENG-062', 'ENG-065']))
    pd = L['pulse_design']
    rows.append(dict(id='DESIGN', label='Intended design point (78 % jet assumed)', cls='SPECULATIVE', maturity='L0', thrust_N=4 * pd['thrust_N'], exhaust_m_s=pd['exhaust_m_s'],
                     heat_over=pd['heat_over'], deposited_g_s=0.0, xray=pd['xray_J'] / pd['fusion_J'], added_t=0, problems=['ENG-063']))
    need = L['need']
    return dict(cls='CALCULATED', need=dict(thrust_N=4 * need['thrust_per_engine_N'], exhaust_m_s=need['exhaust_m_s'], heat_over=1.0), rows=rows,
                maturity=dict(L0='assumed (design point)', L1='0-D or analytic model with speculative levers', L2='calculated: vacuum test particles, 0-D burn, parametric geometry',
                              L3='coupled plasma simulation (none yet)', L4='experiment (none)'),
                note='Thrust for four engines; heat is the hardware heat over its radiator share (1 = closes). No row closes.')


CONCEPTS = [
    dict(id='X-ACC', title='Accelerator-driven selective fusion', status='REJECTED', why='Coulomb scattering outnumbers fusion about 60 to 1; recovery would need 99.997 %.', kept='selectivity'),
    dict(id='X-AMPN', title='Broad plasma dust shield (AMPN)', status='REJECTED', why='Its power and mass exceed what it protects; passive screens are lighter.', kept='passive shielding'),
    dict(id='X-REMOTE', title='Kilometre-scale remote engines (MPN F, RON B-E, Halo)', status='ARCHIVED', why='They fit the heat but not the compact silhouette or the mass.', kept='edge-on members'),
    dict(id='X-FULLC', title='Full coil blanket (2,147 t per engine)', status='ARCHIVED', why='Moves heat into lithium but does not remove it; far too heavy.', kept='the thin blanket option'),
    dict(id='X-A', title='Reflective coatings on the drawn faces (A)', status='NO BENEFIT', why='The faces meet the burn at about 60°; a coating returns 1e-5 of the X-rays.', kept='grazing geometry'),
    dict(id='X-D', title='Deflector liners inside the engine (D)', status='NO BENEFIT', why='The turn needed is far beyond any critical angle.', kept='-'),
    dict(id='X-EXTR', title='Early extraction as a thrust lever', status='CORRECTED 2026-11-24', why='Escaped protons carry energy but almost no momentum; it lowers X-rays and heat, not thrust.', kept='X-ray reduction'),
]

MATURITY = {'compact': 'L2 vacuum test particles + sky ledger', 'thermal': 'L2 parametric geometry, radiative ledger', 'source': 'L2 0-D burn (R2-B)',
            'extraction': 'L2 vacuum test particles, species-resolved'}


def problems(d, x):
    """Every register entry with cause, component, intended solution, achieved value, deficit, future improvements and maturity; plus the
    new ENG-064/065 from vertex-extraction and the ledger correction."""
    items = d['problems']['items']
    pl = d['ledger']['pulse']
    if not any(p['id'] == 'ENG-064' for p in items):
        items.append(dict(id='ENG-064', title='Struck plasma stays in the engine', status='OPEN', severity='HIGH', subsystem='Vertex nozzle', variants=['C1'],
                          mechanism='The ions that strike the nozzle do not leave: their energy is heat and their mass is deposited (implanted or condensed) on the hardware',
                          required='Deposition low enough for the strip and coil faces to survive between services', achieved=f'{1e3 * pl["deposited_kg_s"]:.0f} g/s per engine '
                          f'({pl["deposited_kg_s"] * 3600:.0f} kg per hour)', solutions='A nozzle topology that turns the forward-going plasma aft before it reaches hardware',
                          advances='Erosion-tolerant faces, renewable liners', next='vertex-extraction scan; a deposition and sputtering model (OPEN)',
                          evidence='lab/studies/fusion-ignition/ledger.py (pulse)', assumptions='Coupled pulse, C1 hit share', components=['CAGE', 'SHIELD'], categories=['MAGNETIC_NOZZLE', 'SHIELDING'],
                          stages=['nozzle', 'operate']))
    if x.get('rows') and not any(p['id'] == 'ENG-065' for p in items):
        G = x['geometries']; drawn = G.get('drawn|0|1'); best = min(G.values(), key=lambda g: 0.4 * g['species']['D']['hit'] + 0.6 * g['species']['He3']['hit'])
        items.append(dict(id='ENG-065', title='Topology, not field strength, sets the interception', status='OPEN', severity='CRITICAL', subsystem='Vertex nozzle', variants=['C1'],
                          mechanism='Magnetised products follow the field lines that leave the burn; forward-going lines end on the shield and closure coils at every field strength',
                          required='Hit share well below 0.1', achieved=f'drawn {drawn["species"]["D"]["hit"]:.2f}; best of {len(G)} configurations {best["species"]["D"]["hit"]:.2f} '
                          f'({best["topo"]}, burn {best["dz"]:+g} m, field ×{best["mult"]:g}); field ×4 alone changes nothing' if drawn else 'see the scan',
                          solutions='A closed forward mirror that reflects the forward-going field lines aft; a burn further from the closure hardware',
                          advances='Magnets carrying several times today\'s current density, or a plasma that expands across the field (not modelled)',
                          next='Coupled plasma expansion (diamagnetic cavity) in the best topology', evidence='lab/studies/vertex-compact-engine/vertex-extraction/results/extraction.json',
                          assumptions='Vacuum field, on-axis point source, equal-speed debris', components=['C1', 'C2', 'L1', 'L2', 'SHIELD'], categories=['MAGNETIC_COILS', 'MAGNETIC_NOZZLE'],
                          stages=['magnets', 'nozzle']))
    for p in items:
        ev = p.get('evidence') or ''
        kind = 'extraction' if 'extraction' in ev else 'source' if 'vertex-source' in ev else 'thermal' if 'thermal' in ev else 'compact'
        p.setdefault('cause', p.get('mechanism'))
        p.setdefault('component', ', '.join(p.get('components') or []) or p.get('subsystem'))
        p.setdefault('intended', p.get('solutions'))
        p.setdefault('deficit', p.get('severity'))
        p.setdefault('future', p.get('advances'))
        p.setdefault('maturity', 'L2 momentum-consistent pulse ledger' if p['id'] == 'ENG-064' else MATURITY[kind])
    d['problems']['concepts'] = CONCEPTS
    return d['problems']


def startup(d):
    st = {s_['id']: s_ for s_ in d['startup']['steps']}; tl = {t['id']: t for t in d['ledger']['timeline']}; pl = d['ledger']['pulse']
    seq = [('POWER', 'Power', 'CALCULATED'), ('COOL', 'Cryogenics', 'CALCULATED'), ('CHARGE', 'Field ramps up', 'ILLUSTRATIVE'), ('FIELD', 'Field ready', 'CALCULATED'),
           ('inject', 'Injection', 'SPECULATIVE'), ('TARGET', 'Target at the burn point', 'SPECULATIVE'), ('compress', 'Compression', 'OPEN'),
           ('burn', 'Fusion', 'CALCULATED'), ('expand', 'Expansion', 'CALCULATED'), ('GUIDE', 'Magnetic guidance', 'SAMPLED'), ('PROP', 'Propellant', 'SPECULATIVE'),
           ('EXHAUST', 'Exhaust', 'CALCULATED'), ('HEAT', 'Heat', 'CALCULATED'), ('RAD', 'Radiation', 'CALCULATED')]
    out = []
    for k, label, cls in seq:
        s_ = st.get(k) or tl.get(k)
        txt = s_.get('text') if s_ and 'text' in s_ else s_.get('note') if s_ else None
        if k == 'TARGET':
            txt = 'A target of {:.2f} mg of D and ³He reaches the burn point, {:,.0f} times a second.'.format(d['ledger']['target_mass_kg'] * 1e6, pl['Hz'])
        if k == 'GUIDE':
            txt = f'The field turns the expanding plasma: {d["ledger"]["nozzle"]["C1|1"]["hit"]:.0%} of it strikes hardware in C1 (test particles).'
        if k == 'PROP':
            txt = 'Hydrogen reaction mass would join here; how the plasma would heat it is not modelled (SPECULATIVE).'
        if k == 'EXHAUST':
            txt = f'{(1 - d["ledger"]["nozzle"]["C1|1"]["hit"]):.0%} of the plasma leaves at {pl["exhaust_m_s"] / 1e3:,.0f} km/s: {4 * pl["thrust_N"] / 1e6:.2f} MN for four engines.'
        if k == 'HEAT':
            txt = f'{pl["engine_heat_W"] / 1e12:.1f} TW per engine into the hardware, {pl["heat_over"]:,.0f}× its radiator share.'
        if k == 'RAD':
            txt = f'X-rays {pl["xray_J"] / pl["fusion_J"]:.0%} and neutrons {pl["neutron_J"] / pl["fusion_J"]:.1%} of the fusion energy leave in straight lines.'
        if k == 'compress':
            txt = 'Not modelled: how the drivers crush the target to the burn density is OPEN.'
        if k == 'DRIVER':
            continue
        out.append(dict(id=k, label=label, cls=cls, text=txt or ''))
    return out


def build(s, d):
    fusion = json.loads((ROOT / 'lab/studies/selective-fusion/results/fusion.json').read_text())
    sys.path.insert(0, str(ROOT / 'lab/studies/vertex-compact-engine/magneto-photonic-nozzle'))
    import mpn  # noqa: E402
    src, _ = mpn.sources(mpn.canon())
    compact = json.loads(COMPACT.read_text())
    x = extraction(d)
    out = dict(matter=matter(d), unwanted=unwanted(d, fusion), mix=mix(d, fusion, src), accel=accel(), spin=spin(d, fusion), radiation=radiation(d),
               optics=optics(d), shapes=shapes(d), extraction=x, integration=integration(d, compact), compare=compare(d, x), startup=startup(d))
    problems(d, x)
    out['extraction'].pop('rows', None)                 # 544 rows stay in the import; the page reads the geometries, frontier and findings
    return r3(out)
