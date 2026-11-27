"""ISSA Phase V: thermal-network optimisation and engineering convergence (STUDY, NONCANON). Pure Python; reads the spec, the Phase III/IV
results and the Phase V OpenMC summary (results/phase5_rad3d.json, written by rad3d.py when it has run); writes
results/phase5_config.json and results/phase5.json.

    python3 work/ship-systems-architecture/phase4/study4.py      (Phase IV inputs)
    /opt/mf/envs/omc/bin/python work/ship-systems-architecture/phase5/rad3d.py   (optional, OpenMC 3-D)
    python3 work/ship-systems-architecture/phase5/study5.py

Every integrated result names the configuration it represents (CONFIG['id']); nothing mixes phases. Cases are correlated sensitivity
cases (opt / nom / cons: inputs moved together), not statistical bounds, unless a row says 'envelope'. Dual baseline (owner 2026-11-27):
RESEARCH = what today's engineering supports; FICTIONAL = the adopted hard-SF assumption, with the advance that bridges the gap.
"""
import hashlib
import json
import math
import random
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
ROOT = WORK.parents[1]
R = WORK/'results'
for p in (ROOT/'src/wayfarer', WORK/'phase2', WORK/'phase3', WORK/'phase4', HERE):
    sys.path.insert(0, str(p))
import spec  # noqa: E402
import operating_point as op  # noqa: E402
import mass_model  # noqa: E402
mm = mass_model
import fuel_storage as fs  # noqa: E402
import habitat_ring  # noqa: E402
import eps_b  # noqa: E402
import eps_g1  # noqa: E402
import mission as msn  # noqa: E402
import study as s3  # noqa: E402
import study4 as s4  # noqa: E402
import hot  # noqa: E402
from viewfactor import view_factor  # noqa: E402

SIG = s3.SIG; EPS = s3.EPS; G0 = 9.80665; C = 299792458.0; AU = 1.495978707e11; DAY = 86400.0; YR = 365.25*DAY
B = (0, 1, 2); CASES = hot.CASES
FACE_PER_M = s3.FACE_PER_M; MARGIN = 1.2
T_HOT = 1800.0; ABSORBED = 10.45e9; HOT_IDEAL = 14.40e9
PER_M_HOT = s3.cap(FACE_PER_M, T_HOT)
HOT_X0 = s4.BULKHEAD_X-162.0           # aft end of the hot length on the blade (-111.6)
CIRC = 40.2e3                          # CIRC-001 ring circulation (mass_model only), kg


def r3(x, n=3):
    return [round(v, n) for v in x]


# ============================================================================ V-A configuration ========================================
def config(s):
    m0 = op.mission(s); mc = mm.coupled_mission(s, CIRC)
    cfg = dict(
        id='N2-R4a-P5.0', label='N2-R4a initial research variant as fixed for Phase V reconciliation (owner DR4-01, 2026-11-27)',
        phase='V', status='STUDY / NONCANON', supersedes='every Phase IV integrated N2-R4a figure',
        generation=dict(L2=dict(units=3, rating_We=3.5e6, strategy_operating='C: all three at partial load (high-velocity coast, burns, critical phases)',
                                strategy_maintenance='B: two running + warm standby', BOL_factor=1.0, EOL_factor=0.90, aux_frac=0.03, pmad=0.95,
                                technology='closed Brayton, reactor-heated (PROVISIONAL; rating and technology provisional per DR4-02)',
                                rejection_T_K=700.0, placement='one unit per radiator sector (azimuth 90/210/330), x_aft ~ -89.5, r ~2.9'),
                        L1='drive-specific services in burns; derived from the chosen heat transport (V-D), no fixed 6 or 40 MW',
                        L3='refuge survival (independent)'),
        loads=dict(source='references/p1_power_loads.json (Phase II/III ledger)', planning_bands_W=[0.0, 1.0e6, 2.0e6],
                   demand_two_unit_basis_W='Phase IV l2.demand_W (proactive + planning + recharge + standby)'),
        radiators=dict(hot=dict(T_K=1800.0, ideal_W=HOT_IDEAL, absorbed_peak_W=ABSORBED, margin_rule=1.2, per_m_W=PER_M_HOT,
                                hot_length_m=162.0, x=(HOT_X0, s4.BULKHEAD_X)),
                       L2=dict(T_K=700.0, length_m=24.0, x=(s4.BULKHEAD_X-24.0, s4.BULKHEAD_X), on='hot-blade forward end, all three blades'),
                       bulkhead=dict(layers=3, eps=0.05, R_m=37.0, station_x=s4.BULKHEAD_X-24.0-0.2, origin='production graded bulkhead moved aft'),
                       WARM=dict(T_K=440.0, x=(50.4, 72.9), area_m2=s3.WARM['area']), LOW=dict(T_K=300.0, x=(73.4, 93.4), area_m2=s3.LOW['area'])),
        hot_loop=dict(reference='H5 (distributed redundancy reference only, DR4-03)', coolant='Li (study assumption)'),
        storage=dict(main_battery_kWh=2000, restart_pack='independent L2 restart pack (R1b), 2-6.5 t', defense_buffer='power-sized 21 MW class',
                     survival='refuge, independent', ride_through='per bus segment', pulse_bank='canon, unchanged'),
        failure_domains=['L2 unit (one per sector)', 'radiator sector (blade)', 'hot-loop zone (H5: 6 per blade)', 'ring A', 'ring B',
                         'stationary hub', 'bus segment', 'refuge'],
        mission_loading=dict(standard='12 months, 12 crew, modular extended provisioning (owner DR4-09)', velocity='per mission, 0.016 c reference max'),
        mass_base=dict(historical_departure_t=m0['departure_mass_kg']/1e3, coupled_departure_t=mc['departure_mass_kg']/1e3,
                       CIRC001_t=CIRC/1e3, note='coupled base = mass_model.coupled_mission(s, CIRC-001), development configuration'),
    )
    txt = json.dumps(cfg, sort_keys=True, default=str)
    cfg['hash'] = hashlib.sha256(txt.encode()).hexdigest()[:12]
    return cfg


# ============================================================================ V-A corrections ==========================================
def corrections(s, P4, H, L2c):
    T4 = {r['name'][:2]: r for r in P4['transport']['rows']}
    h5 = T4['H5']['mass_t']
    low_ideal = s3.cap(s3.LOW['area'], 300.0); warm_ideal = s3.cap(s3.WARM['area'], 440.0)
    lowF = next(r for r in P4['thermal']['view_factors'] if r['surface'].startswith('LOW, production'))
    m0 = op.mission(s); mc = mm.coupled_mission(s, CIRC)
    rows = [
        dict(id='C5-01', item='H5 mass interval', phase4=f'{h5[0]:.0f} / {h5[1]:.0f} / {h5[2]:.0f} t (nominal below both ends)',
             cause='each band moved trunk velocity (6/8/10 m/s): inventory fell while pumps and walls rose, so the "bands" were three design points, not bounds',
             phase5=f'velocity optimised per case on one objective; H5 now {H["H5"]["total_t"][0]:,.0f} / {H["H5"]["total_t"][1]:,.0f} / {H["H5"]["total_t"][2]:,.0f} t (correlated cases)'),
        dict(id='C5-02', item='fixed 3 mm pipe wall', phase4='3 mm on every trunk at any diameter and pressure',
             cause='no pressure or creep basis', phase5=f'hoop stress at the local pressure (vapour pressure + subcooling + acceleration head + loop loss) over a '
             f'creep-limited allowable of 30/15/8 MPa at ~1950 K: H6a trunk {H["H6a"]["net"][1]["t_trunk"]*1e3:.0f} mm at D {H["H6a"]["net"][1]["D_trunk"]:.2f} m, '
             f'{H["H6a"]["net"][1]["p_trunk_max"]/1e6:.1f} MPa'),
        dict(id='C5-03', item='drive-specific L1 0.1 vs 0.6 MW', phase4='0.1 MW in the L1 mass line, 0.6 MW in the L1 table',
             cause='two placeholders from Phase III (heat-pipe-blade case vs base)', phase5='L1 rebuilt item by item from the canon L1 rows and the derived pump work (V-D); no placeholder'),
        dict(id='C5-04', item='2 running + standby vs strategy C', phase4=f'700 K section {P4["convergence"]["candidates"][-1]["length_m"][1]:.0f} m sized for two units at full load + 3 % standby',
             cause='under C a trip leaves two survivors at full load on their OWN sector radiators: dedicated sections must each carry one full unit',
             phase5=f'dedicated sections {L2c["dedicated"]["length_m"]:.1f} m; cross-strapped dual-header sections {L2c["cross"]["length_m"]:.1f} m (V-C)'),
        dict(id='C5-05', item='LOW capacity figures', phase4='1.07 MW (Phase III usable), 1.26 MW (radiator_zones placed), 62.9 kW/m',
             cause='three definitions', phase5=f'ideal {low_ideal/1e6:.2f} MW; /1.2 margin {low_ideal/1.2/1e6:.2f} MW usable; in a burn the hot-blade '
             f'exchange debits {100*lowF["debit"]:.0f} % -> {low_ideal*(1-lowF["debit"])/1.2/1e6:.2f} MW. WARM: ideal {warm_ideal/1e6:.2f}, usable {warm_ideal/1.2/1e6:.2f} MW'),
        dict(id='C5-06', item='Phase III thermal states in the Phase IV closure table', phase4='closure rows reused Phase III loads (550 K section, 2.66 MWe)',
             cause='phase mixing', phase5='Phase V ledgers (V-C) are built from CONFIG only'),
        dict(id='C5-07', item='logistics gross mass', phase4='gross = payload + 1 t tare per container, dedicated and shared counts mixed',
             cause='container tare and the 60 t cargo line overlap', phase5='LOG-G1 (V-G): payload against the cargo/food lines once, tare as a separate new item'),
        dict(id='C5-08', item='existing allocations vs added equipment', phase4='increments listed without their owner line',
             cause='no classification', phase5='every V-F item is EXISTING (inside a budget line), OMITTED-EXISTING (CIRC-001) or NEW'),
        dict(id='C5-09', item='survival storage and ride-through', phase4='survival storage and ride-through cells counted inside the storage total',
             cause='independence not shown', phase5='V-D storage table: separate stores, separate converters, no shared energy'),
        dict(id='C5-10', item='CIRC-001', phase4=f'historical departure {m0["departure_mass_kg"]/1e3:,.0f} t',
             cause='operating_point omits the 40.2 t ring circulation that mass_model carries (an omitted EXISTING component, not a new requirement)',
             phase5=f'coupled base via mass_model.coupled_mission(extra_end_kg) = {mc["departure_mass_kg"]/1e3:,.1f} t; production default unchanged'),
    ]
    return rows


# ============================================================================ V-B heat transport =======================================
def transport(s, accel_g=1.362):
    L_hdr = 162.0-24.0         # hot length on the blade under N2-R4a (700 K section on the forward 24 m)
    Q = ABSORBED/3; a = accel_g*G0; cap_blade = PER_M_HOT*L_hdr/3
    topo = hot.TOPOLOGIES+[dict(hot.TOPOLOGIES[4], key='H6f', name='H6f = H6a with dT 400 K', dT=400.0)]
    out = {}
    for t in topo:
        nets = [hot.network(t, Q, L_hdr, a, i=i) for i in B]
        out[t['key']] = dict(name=t['name'], maturity=t['maturity'], net=nets,
                             total_t=[3*n['hardware_kg']/1e3 for n in nets], pump_MW=[3*n['pump_W']/1e6 for n in nets],
                             inventory_t=[3*n['inventory_kg']/1e3 for n in nets],
                             by_item_t={k: [3*n['mass_kg'][k]/1e3 for n in nets] for k in nets[1]['mass_kg']},
                             objective_t=[3*n['objective_kg']/1e3 for n in nets], faults=hot.faults(t, nets[1], Q, cap_blade),
                             startup=hot.startup(nets[1], L_hdr), wall_limit=[n['wall_over_T_limit'] for n in nets],
                             sections=t['n_sec'], paths=t['n_paths'], independent=t['indep'])
    # coolants on the H6a network
    cool = []
    for f in ('Li', 'Na', 'K', 'Sn', 'HeXe'):
        n = hot.network(hot.TOPOLOGIES[4], Q, L_hdr, a, fluid=f, i=1); F = hot.FLUIDS[f]
        cool.append(dict(fluid=f, T_in=n['T_in'], p_sat_MPa=n['p_sat']/1e6, p_max_MPa=n['p_trunk_max']/1e6, inventory_t=3*n['inventory_kg']/1e3,
                         pump_MW=3*n['pump_W']/1e6, hardware_t=3*n['hardware_kg']/1e3, freeze_K=F.get('T_m'), compat=F['compat'], failure=F['failure'],
                         trl=F['trl'], near_critical=(F.get('T_crit') or 1e9) < n['T_in']+300))
    # material / pressure sensitivity on H6a (the dominant lever): allowable stress and wall density
    sens = []
    for sig, rho_w, label in ((8e6, 10.2e3, 'Mo-TZM, conservative creep'), (15e6, 10.2e3, 'Mo-Re class, nominal'), (30e6, 10.2e3, 'W-Re / ODS, optimistic'),
                              (60e6, 10.2e3, 'advanced refractory (not demonstrated)'), (100e6, 3.0e3, 'C/C-SiC structural tube with refractory liner (not demonstrated)')):
        keep = (hot.SIGMA_ALLOW, hot.WALL['rho'])
        hot.SIGMA_ALLOW = (sig, sig, sig); hot.WALL['rho'] = rho_w
        n = hot.network(hot.TOPOLOGIES[4], Q, L_hdr, a, i=1); n0 = hot.network(hot.TOPOLOGIES[4], Q, L_hdr, a, i=1, accel=False)
        hot.SIGMA_ALLOW, hot.WALL['rho'] = keep
        sens.append(dict(material=label, sigma_MPa=sig/1e6, wall_rho=rho_w, total_t=3*n['hardware_kg']/1e3, coast_only_head_t=3*n0['hardware_kg']/1e3))
    prof = {f'dT {dT:.0f} K, theta {th:.0f} K': hot.spatial_profile(dT, th) for dT, th in ((200.0, 10.0), (300.0, 30.0), (400.0, 30.0))}
    T_in = {f'{dT:.0f}': hot.inlet_temperature(dT, 30.0) for dT in (100.0, 200.0, 300.0, 400.0, 500.0)}
    rec = 'H6a'
    return dict(L_hot_m=L_hdr, Q_blade_W=Q, accel_m_s2=a, topologies=out, coolants=cool, material_sensitivity=sens, profiles=prof,
                inlet_T=T_in, recommended=rec, finding=None)


# ============================================================================ V-C radiators ============================================
def l2_sections(T=700.0, Pe=3.5e6, i=1):
    """Strategy C: after a trip two survivors run at full rating. Dedicated sections: each sector's section carries one full unit (3 x).
    Cross-strapped dual-header sections: every section has two independent headers from two neighbouring units, so the total is two full
    units while each unit stays in its own failure domain."""
    eta = eps_b.brayton_eff(T, i)
    def L(units):
        x = s4.section(units, Pe, T_rej=T, band=i, standby_units=0, F_hot=3e-4)
        return x
    ded = L(3); cr = L(2)
    return dict(T_K=T, eta=eta, waste_per_unit_W=Pe*(1/eta-1), dedicated=dict(length_m=ded['length_m'], area_m2=ded['geometric_area_m2'],
                hot_capacity_W=ded['hot_capacity_W']), cross=dict(length_m=cr['length_m'], area_m2=cr['geometric_area_m2'], hot_capacity_W=cr['hot_capacity_W'],
                header_t=cr['length_m']*3*2*0.15))


def emitter_mc(x_e, beta_deg, T_e, n=30000, seed=11, r0=6.1, r1=37.0):
    """Monte Carlo from an annular emitter at station x_e (normal tilted beta from +x toward radial-outward) to the forward blades,
    ring A, ring B, the He-3 tank zone, the aft (hot) blades, and space. Straight rays; blades as radial half-planes at 90/210/330."""
    rnd = random.Random(seed); b = math.radians(beta_deg)
    hits = dict(fwd_blades=0, hot_blades=0, ring_A=0, ring_B=0, tanks=0, casing=0, space=0)
    AZ = [math.radians(a) for a in (90.0, 210.0, 330.0)]
    xa, xb = 97.3, 103.3
    for _ in range(n):
        r = math.sqrt(rnd.uniform(r0*r0, r1*r1)); ph = rnd.uniform(0, 2*math.pi)
        P = (x_e, r*math.cos(ph), r*math.sin(ph)); er = (0.0, math.cos(ph), math.sin(ph))
        nrm = (math.cos(b), math.sin(b)*er[1], math.sin(b)*er[2])
        # cosine-weighted direction about nrm
        u1, u2 = rnd.random(), rnd.random(); st = math.sqrt(u1); ct = math.sqrt(1-u1); pp = 2*math.pi*u2
        t1 = (0.0, -math.sin(ph), math.cos(ph)); t2 = (nrm[1]*t1[2]-nrm[2]*t1[1], nrm[2]*t1[0]-nrm[0]*t1[2], nrm[0]*t1[1]-nrm[1]*t1[0])
        d = tuple(ct*nrm[k]+st*(math.cos(pp)*t1[k]+math.sin(pp)*t2[k]) for k in range(3))
        best = (1e9, 'space')
        for a in AZ:                                   # blade half-planes: n_plane = (-sin a, cos a) in yz
            ny, nz = -math.sin(a), math.cos(a); den = d[1]*ny+d[2]*nz
            if abs(den) < 1e-12: continue
            t = -(P[1]*ny+P[2]*nz)/den
            if t <= 1e-6: continue
            X = P[0]+t*d[0]; Y = P[1]+t*d[1]; Z = P[2]+t*d[2]; rr = Y*math.cos(a)+Z*math.sin(a)
            if 6.1 <= rr <= 36.1:
                if 50.4 <= X <= 93.4 and t < best[0]: best = (t, 'fwd_blades')
                if HOT_X0 <= X < x_e-0.5 and t < best[0]: best = (t, 'hot_blades')
        # casing cylinder r 5.6
        A = d[1]**2+d[2]**2; Bq = 2*(P[1]*d[1]+P[2]*d[2]); Cq = P[1]**2+P[2]**2-5.6**2
        if A > 1e-12 and Bq*Bq-4*A*Cq > 0:
            t = (-Bq-math.sqrt(Bq*Bq-4*A*Cq))/(2*A)
            if t > 0 and t < best[0]: best = (t, 'casing')
        # ring bands (x +-2 m, r 22-30) and the tank zone (x 109-138, r 21-34.5): sample along the ray
        for name, (xlo, xhi, rlo, rhi) in (('ring_A', (xa-2, xa+2, 22.0, 30.0)), ('ring_B', (xb-2, xb+2, 22.0, 30.0)),
                                            ('tanks', (109.25, 137.85, 21.0, 34.5))):
            if abs(d[0]) < 1e-9: continue
            for xs in (xlo, 0.5*(xlo+xhi), xhi):
                t = (xs-P[0])/d[0]
                if t <= 0: continue
                rr = math.hypot(P[1]+t*d[1], P[2]+t*d[2])
                if rlo <= rr <= rhi and t < best[0]: best = (t, name); break
        hits[best[1]] += 1
    return {k: v/n for k, v in hits.items()}


def bulkhead_radiosity(T_hot_side, T_cold_side, n_layers=3, eps=0.05, F_hot=1.0, damaged=0.0):
    """Layer temperatures through n parallel low-emissivity layers (multiple reflections, grey diffuse): flux q between outer boundaries;
    damaged = fraction of layer area holed/lost (direct leak through holes at the outer-boundary exchange)."""
    Rl = 2/eps-1; q_stack = SIG*(T_hot_side**4-T_cold_side**4)/((n_layers+1)*Rl)
    q_hole = SIG*(T_hot_side**4-T_cold_side**4)*0.9
    q = (1-damaged)*q_stack+damaged*q_hole
    Ts = []
    for k in range(1, n_layers+1):
        Ts.append(((T_hot_side**4)-(k)*(T_hot_side**4-T_cold_side**4)/(n_layers+1))**0.25)
    return dict(q_W_m2=q, layer_T_K=Ts, q_intact_W_m2=q_stack)


def radiators(s, P4, H):
    sc = [l2_sections(T) for T in (550.0, 600.0, 650.0, 700.0, 750.0, 800.0, 850.0)]
    hot_free_m = (HOT_IDEAL-ABSORBED*MARGIN)/PER_M_HOT       # hot length the 20 % rule leaves for non-hot use
    scan = []
    for x in sc:
        T = x['T_K']
        p = eps_b.fission_plant(3.5e6, T, 80.0, 1, 2.69e4, EPS); U = eps_g1.unit(Pe_W=3.5e6, eta=p['eta'], T_rej=T, n_running=3, i=1)
        unit_t = (sum(v for k, v in p['parts_kg'].items() if k not in ('shield', 'rejection'))+U['shadow_kg']+U['slab_kg'])/1e3
        scan.append(dict(T_K=T, eta=x['eta'], reactor_MWt=3.5/x['eta'], unit_t=unit_t, L_dedicated_m=x['dedicated']['length_m'],
                         L_cross_m=x['cross']['length_m'], fits_hot_rule_cross=x['cross']['length_m'] <= hot_free_m,
                         fits_hot_rule_dedicated=x['dedicated']['length_m'] <= hot_free_m,
                         displaced_hot_W_cross=x['cross']['length_m']*PER_M_HOT, area_cross_m2=x['cross']['area_m2']))
    # advanced turbine inlet (bridging advance): 1500 K inlet at the same Carnot fraction
    adv = []
    for T in (700.0, 800.0, 900.0):
        eta = 0.42*(1-T/1500.0); waste = 2*3.5e6*(1/eta-1)*MARGIN; A = waste/(EPS*SIG*T**4*0.9)
        adv.append(dict(T_K=T, eta=eta, L_cross_m=A/FACE_PER_M))
    # R5-C: L2 emitter on the forward face of the graded bulkhead (normal tilt beta)
    mc = {b: emitter_mc(50.6, b, 700.0) for b in (0.0, 45.0, 70.0)}
    A_bulk = math.pi*(37.0**2-6.1**2)
    lift = json.loads((R/'phase3.json').read_text())['shielding']['he3_stage_lift_W']
    def tank_leak(Fq, T, A):
        E = A*EPS*SIG*T**4*Fq/(13*2*math.pi*6.45*28.6)      # mean irradiance on the 13 tank shells
        To = ((E*0.1+0.05*SIG*150.0**4)/(0.05*SIG))**0.25
        return dict(irradiance_W_m2=E, mli_outer_K=To, leak_W_total=13*2*math.pi*6.45*28.6*0.3*(To**4)/(150.0**4))
    rc = {}
    for b, h in mc.items():
        A_eff = A_bulk/math.cos(math.radians(b)) if b < 80 else A_bulk
        cap = A_eff*EPS*SIG*700.0**4*h['space']
        rc[b] = dict(F=h, area_m2=A_eff, capacity_W=cap, need_W=l2_sections(700.0)['waste_per_unit_W']*2*MARGIN,
                     to_fwd_blades_W=A_eff*EPS*SIG*700.0**4*h['fwd_blades'], tanks=tank_leak(h['tanks'], 700.0, A_eff), lift_W=lift)
    # bulkhead radiosity, relocated (behind the 700 K section) and degraded
    bk = dict(intact=bulkhead_radiosity(1000.0, 700.0), one_layer_lost=bulkhead_radiosity(1000.0, 700.0, n_layers=2),
              holed_1pct=bulkhead_radiosity(1000.0, 700.0, damaged=0.01), holed_5pct=bulkhead_radiosity(1000.0, 700.0, damaged=0.05),
              note='hot side: the bulkhead aft face sees the 1800 K blades at F ~0.1-0.2 -> effective ~1000 K boundary (STUDY); cold side the 700 K section')
    # header penetrations and the blade spar crossing the bulkhead plane (conduction 1800 -> 700 K through a thermal break)
    pen = dict(spar_W=3*(20.0*0.05*(1800-700)/1.0), header_W=0.0, note='C-C spar 20 W/m K, 0.05 m2 per blade over a 1 m break: ~3 kW total; L2 headers '
               'run inside the casing (no crossing); the hot trunk does not cross the plane')
    exp_ = dict(mo_1500K_mm_per_m=hot.WALL['alpha']*1500*1e3, bulkhead_r37_mm=37.0*8e-6*400*1e3,
                note='bulkhead layers at 700-1000 K grow ~0.1-0.12 m in radius: sliding supports at the casing, slotted V-grooves')
    variants = []
    def var(key, name, L2_where, L2_len, hot_len, geometry, wl, issues, cls):
        cap = hot_len*PER_M_HOT
        variants.append(dict(key=key, name=name, L2=L2_where, L2_length_m=L2_len, hot_length_m=hot_len, hot_ideal_W=cap,
                             hot_margin=cap/ABSORBED-1, meets_20pct=cap >= MARGIN*ABSORBED, geometry=geometry, warm_low=wl, issues=issues, cls=cls))
    s700 = l2_sections(700.0); s750 = l2_sections(750.0)
    var('R5-A', 'Existing silhouette, relocated bulkhead, optimised 750 K cross-strapped section', 'hot-blade forward end', s750['cross']['length_m'],
        162.0-s750['cross']['length_m'], 'bulkhead moves aft %.1f m; no envelope change' % s750['cross']['length_m'], 'unchanged (shadowed)',
        ['L2 at 750 K: Brayton eta %.3f (unit mass +%.0f %%)' % (s750['eta'], 100*(scan[4]['unit_t']/scan[3]['unit_t']-1)), 'dual headers'], 'PROTOTYPE')
    ext = s700['dedicated']['length_m']-hot_free_m
    var('R5-B', 'Extended hot blades: 700 K dedicated sections, blades lengthened aft to keep the hot area', 'hot-blade forward end',
        s700['dedicated']['length_m'], 162.0-s700['dedicated']['length_m']+ext, f'blades +{ext:.1f} m aft of the fixed aft edge', 'unchanged',
        ['conflicts with Q52 option D (fixed aft edge) and the engine exclusion rule (OPEN)'], 'PROTOTYPE (canon conflict)')
    best_b = min(rc, key=lambda b: rc[b]['tanks']['leak_W_total'])
    var('R5-C', f'Separate shielded L2 emitter: forward face of the graded bulkhead, normal tilted {best_b:.0f} deg outward', 'bulkhead forward face',
        0.0, 162.0, 'adds an emitting face to an existing element', 'WARM absorbs %.1f MW from the emitter' % (rc[best_b]['to_fwd_blades_W']/1e6),
        ['tank IR leak %.0f W vs %.0f W He-3 lift' % (rc[best_b]['tanks']['leak_W_total'], lift),
         'capacity %.0f MW vs %.0f MW needed' % (rc[best_b]['capacity_W']/1e6, rc[best_b]['need_W']/1e6)], 'PROTOTYPE')
    var('R5-D', 'Integrated: R5-A L2 + WARM split (hot end of WARM to 480 K) + LOW +4 m from WARM', 'hot-blade forward end', s750['cross']['length_m'],
        162.0-s750['cross']['length_m'], 'internal re-zoning of WARM/LOW only', 'WARM %.2f MW, LOW %.2f MW usable' % (
            (s3.cap(s3.WARM['area']*14.5/22.5, 440.0)+s3.cap(s3.WARM['area']*4.0/22.5, 480.0))/MARGIN/1e6, s3.cap(s3.LOW['area']*24.0/20.0, 300.0)/MARGIN/1e6),
        ['480 K needs heat-pump lift for loads specified at 440 K'], 'PROTOTYPE')
    var('R5-E', 'Hybrid: half of L2 on the bulkhead face (R5-C, 70 deg) and half on a 750 K cross-strapped hot-end section', 'split',
        s750['cross']['length_m']/2, 162.0-s750['cross']['length_m']/2, 'bulkhead aft by half the length', 'unchanged',
        ['two different L2 sinks: more headers; tank leak halved'], 'PROTOTYPE')
    return dict(l2_scan=scan, advanced_turbine=adv, hot_free_m=hot_free_m, l2_700=s700, l2_750=s750, emitter=rc, bulkhead=bk, penetrations=pen,
                expansion=exp_, variants=variants)


def ledgers(s, Rd, H, D):
    """Thermal ledgers for the preferred configuration (R5-A geometry, H6a, 3 x 3.5 MWe C). Loads in W (nominal case) with the capacity of
    each zone in that state. HOT capacity is the ideal hot area; WARM/LOW capacities are usable (/1.2) with the burn exchange debit."""
    P4 = json.loads((R/'phase4.json').read_text())
    vf = {r['surface'][:4]: r for r in P4['thermal']['view_factors'] if 'production bulkhead in place' in r['surface']}
    warm_u = s3.cap(s3.WARM['area'], 440.0)/MARGIN; low_u = s3.cap(s3.LOW['area'], 300.0)/MARGIN
    hot_cap = (162.0-Rd['l2_750']['cross']['length_m'])*PER_M_HOT
    l2_cap = Rd['l2_750']['cross']['area_m2']*EPS*SIG*750.0**4*0.9/MARGIN*MARGIN    # area already includes the margin
    pump = H['topologies']['H6a']['pump_MW'][1]*1e6
    Pt = 3.5e6/Rd['l2_750']['eta']; w_full = Pt-3.5e6
    P3 = json.loads((R/'phase3.json').read_text())['thermal_closure']['rows']
    def p3(state, band='nominal'):
        r = next(x for x in P3 if x['state'] == state and x['band'] == band and x['condition'] == 'intact')
        return {c['circuit'][:4]: c['load_W'] for c in r['circuits']}
    coast = p3('COAST_HV_PROACTIVE'); trig = p3('COAST_HV_TRIGGERED'); burn = p3('HIGH_THRUST_PROACTIVE')
    L1r = D['L1']['rows']
    l1_drive = sum(r['W'][1] for r in L1r if r['cls'] not in ('EXISTING-ALLOCATION', 'STARTUP')); l1_reject = l1_drive*(1/0.27-1)
    l1_exist = sum(r['W'][1] for r in L1r if r['cls'] == 'EXISTING-ALLOCATION' and r['id'] == 'TMS.BURN_HEAT_PUMPS')*(1/0.27-1)
    warm_d = (s3.cap(s3.WARM['area']*14.5/22.5, 440.0)+s3.cap(s3.WARM['area']*4.0/22.5, 480.0))/MARGIN    # R5-D re-zoned WARM
    low_d = s3.cap(s3.LOW['area']*24.0/20.0, 300.0)/MARGIN
    states = [
        ('coast (high-velocity, proactive)', 0.0, 0.0, 2/3, coast['WARM'], coast['LOW ']),
        ('propulsion startup (preheat, 10 % power)', 0.1*ABSORBED, 0.1*l1_reject, 2/3, burn['WARM'], burn['LOW ']),
        ('high-power burn', ABSORBED, l1_reject, 2/3, burn['WARM']*(1+vf['WARM']['debit']), burn['LOW ']*(1+vf['LOW,']['debit'])),
        ('braking burn', ABSORBED, l1_reject, 2/3, burn['WARM']*(1+vf['WARM']['debit']), burn['LOW ']*(1+vf['LOW,']['debit'])),
        ('drive trip (first 60 s)', 0.15*ABSORBED, 0.0, 2/3, burn['WARM'], burn['LOW ']),
        ('post-burn cooldown', 0.02*ABSORBED, 0.0, 2/3, coast['WARM'], coast['LOW ']),
        ('defense engagement (coast)', 0.0, 0.0, 2/3, trig['WARM'], trig['LOW ']),
        ('black start (one unit, R1b)', 0.0, 0.0, 0.3, 0.3*coast['WARM'], 0.5*coast['LOW ']),
        ('generator failure (two survivors at 100 %)', 0.0, 0.0, 1.0, coast['WARM'], coast['LOW ']),
        ('coolant-sector failure in a burn (one H6a section)', ABSORBED, l1_reject, 2/3, burn['WARM'], burn['LOW ']),
        ('emergency (refuge, L3)', 0.0, 0.0, 0.0, 0.2*coast['WARM'], 0.3*coast['LOW ']),
    ]
    rows = []
    for name, qh, ql1, lf, qw, ql in states:
        units = 2 if 'generator' in name else (1 if 'black' in name else 3)
        l2w = (units*lf if units == 3 else min(units, units*1.0 if 'generator' in name else 0.3))*w_full if lf else 0.0
        hc = hot_cap*(1-1/(3*6)) if 'coolant-sector' in name else hot_cap
        z = dict(HOT=(qh+(pump if qh else 0.0), hc), L1_reject_drive=(ql1, 0.0), L1_reject_burn_heat_pumps=(l1_exist if qh >= ABSORBED else 0.0, 0.0),
                 L2=(l2w, l2_cap), WARM_R5A=(qw, warm_u), WARM_R5D=(qw, warm_d), LOW_R5A=(ql, low_u), LOW_R5D=(ql, low_d))
        zones = {k: dict(load_W=a, capacity_W=b, ok=a <= b+1e-6) for k, (a, b) in z.items()}
        buf = sum(max(0.0, zones[k]['load_W']-zones[k]['capacity_W'])*60.0 for k in ('WARM_R5D', 'LOW_R5D'))
        core = [k for k in zones if k not in ('WARM_R5A', 'LOW_R5A')]
        rows.append(dict(state=name, zones=zones, closes_R5D=all(zones[k]['ok'] for k in core),
                         closes_R5D_except_L1=all(zones[k]['ok'] for k in core if not k.startswith('L1')),
                         thermal_buffer_MJ_per_min=buf/1e6, pcm_t_per_min=buf/288e3/1e3))
    return dict(rows=rows, basis=dict(hot_capacity_W=hot_cap, l2_capacity_W=l2_cap, warm_usable_W=warm_u, low_usable_W=low_u, l1_reject_W=l1_reject, l1_reject_burn_heat_pumps_W=l1_exist, warm_R5D_W=warm_d, low_R5D_W=low_d,
                                      config='N2-R4a-P5.0 + R5-A + H6a'), finding=None)


# ============================================================================ V-D electrical ==========================================
def electrical(s, H):
    Pe = 3.5e6; eol = 0.90; aux = 0.03; pmad = 0.95
    P4 = json.loads((R/'phase4.json').read_text()); dem = P4['l2']['demand_W']
    def eta_part(f, k):                     # closed Brayton with inventory control: flat to ~50 %, then falls (STUDY)
        return max(0.0, 1-k*(1-f)**2) if f >= 0.3 else 0.0
    part = []
    for k, label in ((0.15, 'inventory control (opt)'), (0.3, 'nom'), (0.6, 'temperature control (cons)')):
        for f in (0.3, 0.4, 0.5, 0.6, 2/3, 0.8, 1.0):
            e = 0.164*eta_part(f, k)
            part.append(dict(control=label, load_frac=f, eta=e, waste_W=f*Pe*(1/e-1) if e else None, fuel_rel=f/(e/0.164) if e else None))
    # trip transient: unit 1 trips at t = 0 from strategy C; survivors ramp at r (fraction of rating per s) after a delay
    trans = []
    for case, (delay, ramp, shed_t, store_W, store_kWh) in zip(CASES, ((1.0, 0.05, 2.0, 2.6e6, 2060.0), (3.0, 0.02, 5.0, 2.6e6, 2060.0),
                                                                      (10.0, 0.005, 10.0, 2.0e6, 2000.0))):
        for life, kf in (('BOL', 1.0), ('EOL', eol)):
            load = dem[1]; cap = Pe*kf*(1-aux)*pmad
            each0 = load/3; t = 0.0; dt = 0.1; E = 0.0; deficit_max = 0.0; shed = 0.0; out = []
            while t < 600.0:
                each = min(cap, each0+(ramp*cap*(t-delay) if t > delay else 0.0))
                supply = 2*each; lt = load-(0.25*load if t >= shed_t and supply < load else 0.0)
                d = max(0.0, lt-supply); E += d*dt; deficit_max = max(deficit_max, d)
                if int(t*10) % 50 == 0: out.append((round(t, 1), supply, lt))
                t += dt
            t_rest = delay+(cap-each0)/(ramp*cap) if 2*cap >= load else None
            trans.append(dict(case=case, life=life, load_W=load, survivor_cap_W=cap, delay_s=delay, ramp_per_s=ramp, t_restored_s=t_rest,
                              peak_deficit_W=deficit_max, storage_kWh_used=E/3.6e6, storage_power_ok=deficit_max <= store_W,
                              storage_energy_ok=E/3.6e6 <= store_kWh, steady_ok=2*cap >= load, trace=out[:40]))
    # radiator after the trip: survivors at 100 % on their own sections (dedicated) or cross-strapped
    stores = [
        dict(store='Main battery (EPS-A)', kWh=2000, MW=2.0, converter='bidirectional DC-DC on the main bus', charge='L2 surplus', heat_kW=60,
             independent='shared main bus', role='ride-through and black-start services', cls='EXISTING (canon)'),
        dict(store='Ride-through cells', kWh=60, MW=0.6, converter='per bus segment', charge='bus', heat_kW=10, independent='per segment',
             role='switching faults 5-15 min; first seconds of a unit trip', cls='NEW'),
        dict(store='Independent restart pack (R1b)', kWh=500, MW=0.5, converter='own converter to the L2 unit start bus', charge='L2 only',
             heat_kW=15, independent='yes: own cells, bus and converter; never connected to the refuge', role='restart one L2 unit', cls='NEW'),
        dict(store='Defense buffer', kWh=58, MW=21.0, converter='high-power DC link to the defense load only', charge='L2 surplus',
             heat_kW=400, independent='defense bus only', role='engagement bursts', cls='NEW'),
        dict(store='Pulse bank', kWh='canon', MW='canon', converter='drive ignition', charge='L1/L2', heat_kW='canon', independent='drive only',
             role='ignition', cls='EXISTING (canon)'),
        dict(store='Survival bridge (refuge)', kWh=250, MW=0.05, converter='refuge bus', charge='L3', heat_kW=2, independent='yes (owner rule)',
             role='crew survival to L3', cls='NEW'),
        dict(store='Thermal storage (PCM, hot-loop cooldown)', kWh=3000, MW='heat only', converter='none', charge='drive heat', heat_kW='-',
             independent='per section', role='absorbs drive-HX stored heat if pumps stop', cls='NEW (option)'),
    ]
    # L1 rebuilt from the canon L1 rows and the derived transport
    pl = json.loads((ROOT/'references/p1_power_loads.json').read_text())['items']
    rows = []
    for iid, it in pl.items():
        if it.get('bus') != 'L1': continue
        W = it.get('W')
        cls = 'EXISTING-ALLOCATION' if iid in ('TMS.BURN_HEAT_PUMPS', 'PROP.PULSE_DISCHARGE') else 'DRIVE-SPECIFIC'
        if iid == 'TMS.HOT_LOOP_PUMPS':
            W = H['topologies']['H6a']['pump_MW']; W = [w*1e6 for w in W]; cls = 'DERIVED (V-B H6a)'
        if iid == 'PROP.FEED_PUMPS' and W is None:
            W = [0.2e6, 0.5e6, 1.0e6]; cls = 'OPEN (estimate)'
        rows.append(dict(id=iid, title=it['title'], W=W or [0.0, 0.0, 0.0], cls=cls))
    pre = H['topologies']['H6a']['startup']
    extra = [dict(id='ISSA.PREHEAT', title='hot-loop thaw and blade preheat before ignition (energy)', W=[0, 0, 0], cls='STARTUP',
                  J=pre['thaw_J']+pre['blade_preheat_J']),
             dict(id='ISSA.COOLDOWN', title='cooldown circulation after a burn (25 % flow)', W=[w*0.016 for w in rows[[r['id'] for r in rows].index('TMS.HOT_LOOP_PUMPS')]['W']],
                  cls='DERIVED')]
    L1 = dict(rows=rows+extra, drive_specific_W=[sum(r['W'][i] for r in rows if r['cls'] != 'EXISTING-ALLOCATION') for i in B],
              existing_W=[sum(r['W'][i] for r in rows if r['cls'] == 'EXISTING-ALLOCATION') for i in B])
    return dict(part_load=part, transient=trans, stores=stores, L1=L1)


# ============================================================================ V-F mass and structure ==================================
def mass(s, add_items):
    """Coupled mass through mass_model.coupled_mission(extra_end_kg). add_items: {name: (t_case_list, x0, x1, class)}."""
    base = op.mission(s); corr = mm.coupled_mission(s, CIRC)
    out = []
    for i in B:
        dM = sum(v[0][i] for v in add_items.values())*1e3
        m = mm.coupled_mission(s, CIRC+dM)
        out.append(dict(case=CASES[i], dry_added_t=dM/1e3, propellant_t=m['propellant_kg']/1e3, tankage_t=m['added_tank_kg']/1e3,
                        end_t=m['end_mass_kg']/1e3, departure_t=m['departure_mass_kg']/1e3,
                        extra_departure_t=(m['departure_mass_kg']-corr['departure_mass_kg'])/1e3))
    # tank capacity: liquid volume per species (fuel_storage) vs the propellant the coupled case needs, split like today's inventory
    inv = fs.inventory(s); dens = s['fuel_storage']['density_kg_m3']; tot = sum(inv.values())
    cap = {}
    for t_ in fs.tanks(s):
        cap[t_['species']] = cap.get(t_['species'], 0.0)+t_['liquid_m3']
    key = {'helium_3': 'helium-3', 'deuterium': 'deuterium', 'hydrogen': 'hydrogen'}
    tank = []
    for r in [dict(case='corrected base', propellant_t=corr['propellant_kg']/1e3)]+out:
        need = {key[k]: r['propellant_t']*1e3*v/tot/dens[k] for k, v in inv.items()}
        tank.append(dict(case=r['case'], need_m3=need, capacity_m3={k: cap.get(k, 0.0) for k in need}, fill={k: need[k]/cap.get(k, 1e-9) for k in need}))
    # CoM / inertia with the added masses placed (nominal)
    parts = mass_model.dry_parts(s)
    t0 = mass_model.totals(parts)
    added = [mass_model._part(k, v[0][1]*1e3, v[1], v[2], ['cyl', 5.0]) for k, v in add_items.items() if v[0][1] > 0]
    t1 = mass_model.totals(parts+added)
    F = op.power_cap_N(s)
    acc = dict(end_mass_base_t=corr['end_mass_kg']/1e3, a_end_base_g=F/corr['end_mass_kg']/G0, a_end_nom_g=F/(out[1]['end_t']*1e3)/G0,
               burn_time_ratio=out[1]['propellant_t']/(corr['propellant_kg']/1e3), thrust_N=F)
    att = dict(cg_shift_m=t1['cg_m'][0]-t0['cg_m'][0], I_pitch_ratio=t1['I_pitch']/t0['I_pitch'], cg_base=t0['cg_m'][0], cg_new=t1['cg_m'][0])
    return dict(historical=dict(departure_t=base['departure_mass_kg']/1e3, propellant_t=base['propellant_kg']/1e3),
                corrected=dict(departure_t=corr['departure_mass_kg']/1e3, propellant_t=corr['propellant_kg']/1e3, end_t=corr['end_mass_kg']/1e3),
                cases=out, tanks=tank, accel=acc, attitude=att, items={k: dict(t=v[0], x=(v[1], v[2]), cls=v[3]) for k, v in add_items.items()})


# ============================================================================ V-G independent systems =================================
def eclss():
    unit = dict(crew=4, mass_t=1.2, power_kW=3.4, cooling_kW=3.4, envelope_m=(2.0, 1.4, 2.2), orus_max_width_m=0.70, maint_clear_m=1.0,
                air_flow_m3_s=0.24, functions=['air circulation', 'CO2 removal (amine swing)', 'O2 interface (from central electrolysis)',
                                               'water recovery (urine + condensate)', 'trace contaminant control', 'local control + sensing'],
                interfaces=['28/120 V DC from two bus segments', 'cooling loop to the ring cold loop', 'O2 / N2 supply lines', 'water in/out',
                            'data (two networks)'], cls='PROTOTYPE (ISS CDRA/CCAA/WRS class per crew)')
    layouts = {'7 (3 A + 3 B + 1 hub)': dict(A=3, B=3, hub=1), '8 (3 A + 3 B + 2 hub)': dict(A=3, B=3, hub=2), '8 (4 A + 4 B)': dict(A=4, B=4, hub=0)}
    cases = []
    for name, L in layouts.items():
        res = {}
        for case, (lostA, lostB, lostH, ringA_dead, crewA, crewB) in {
                'nominal 6 + 6': (0, 0, 0, False, 6, 6), 'one unit lost in A': (1, 0, 0, False, 6, 6),
                'ring A lost (12 in B)': (0, 0, 0, True, 0, 12), 'ring A lost + one B unit failed': (0, 1, 0, True, 0, 12),
                'ring A lost + hub unit failed': (0, 0, 1, True, 0, 12)}.items():
            capA = 0 if ringA_dead else 4*(L['A']-lostA); capB = 4*(L['B']-lostB); capH = 4*(L['hub']-lostH)
            # hub capacity can serve either ring through the spoke ducts (cross-ring)
            needA = max(0, crewA-capA); needB = max(0, crewB-capB)
            res[case] = needA+needB <= capH
        cases.append(dict(layout=name, units=sum(L.values()), mass_t=1.2*sum(L.values()), results=res))
    hubif = dict(duct_D_m=math.sqrt(4*0.24/4.0/math.pi), duct_velocity=4.0, rotary_seal='passes through the crew-transfer drum (r ~1.3-1.5 m): '
                 'needs rotating air seals or a ducted air exchange in the transfer vestibule', leak_kg_d=(0.05, 0.2, 1.0),
                 verdict='PRACTICAL IF the duct runs through the existing transfer drum; else use 8 units (4 + 4)')
    return dict(unit=unit, cases=cases, hub_interface=hubif)


def logistics():
    rows = []
    for gross in (1.5, 3.0, 6.0):
        rho = 400.0; tare_frac_guess = 0.15
        for _ in range(5):
            pay = gross*(1-tare_frac_guess); V = pay*1e3/rho/0.7
            a = V**(1/3); Aw = 6*a*a
            tare = (Aw*8.0+0.12*gross*1e3+40.0)/1e3                  # honeycomb shell 8 kg/m2 + frame/restraints 12 % gross + fittings
            tare_frac_guess = tare/gross
        rows.append(dict(gross_t=gross, tare_t=tare, payload_t=gross-tare, tare_frac=tare/gross, edge_m=a, volume_m3=V,
                         fits_2p5m_hatch=a < 2.3, handling='manipulator %s' % ('single-arm' if gross <= 3 else 'dual-arm / rail')))
    racks = dict(fixed_rack_t=6.0, bag_tare_frac=0.05, note='permanent racks in the hub store: 6 t of structure counted once (structure line), bags 5 % tare')
    miss = []
    for months, payload in ((12, 18.9), (24, 35.8), (36, 52.7)):
        r = {}
        for c in rows:
            n = math.ceil(payload/c['payload_t']); r[f'{c["gross_t"]:.1f} t'] = dict(n=n, tare_t=n*c['tare_t'], gross_t=n*c['tare_t']+payload)
        r['racks + bags'] = dict(n=None, tare_t=racks['fixed_rack_t']+payload*racks['bag_tare_frac'], gross_t=racks['fixed_rack_t']+payload*1.05)
        miss.append(dict(months=months, payload_t=payload, options=r))
    return dict(containers=rows, racks=racks, missions=miss, accounting='payload counts against the food/consumables lines once; tare is a NEW item; '
                'the 60 t workshop/spares/cargo line holds the spares themselves, not their containers')


def allocation():
    zones = {'stationary hub (x 95-106, r < 5)': 180.0, 'casing service bays (x 0-50)': 900.0, 'district (x -92 to -80)': 260.0,
             'ring A deck': 1200.0, 'ring B deck': 1200.0, 'refuge': 90.0}
    items = [('flight computers (3 x triplex)', 'stationary hub', 3.0, 0.6, 4.5), ('data distribution / switches', 'casing service bays', 6.0, 0.8, 2.0),
             ('main switchgear (3 sectors)', 'casing service bays', 18.0, 6.0, 1.0), ('L2 unit switchgear + restart pack', 'district', 15.0, 4.5, 0.6),
             ('medical bay equipment', 'ring A deck', 20.0, 2.0, 3.0), ('gas reserves (O2/N2, 90 d)', 'casing service bays', 30.0, 5.0, 0.0),
             ('water processing (central)', 'ring B deck', 12.0, 2.5, 4.0), ('workshop + fab cell', 'stationary hub', 40.0, 6.0, 8.0),
             ('refuge equipment (L3, survival bridge)', 'refuge', 25.0, 5.0, 2.0), ('ECLSS-G1 x 3 (ring A)', 'ring A deck', 18.5, 3.6, 10.2),
             ('ECLSS-G1 x 3 (ring B)', 'ring B deck', 18.5, 3.6, 10.2), ('ECLSS-G1 hub unit', 'stationary hub', 6.2, 1.2, 3.4),
             ('defense buffer', 'casing service bays', 20.0, 14.0, 0.0), ('LOG-G1 store (12 months)', 'stationary hub', 70.0, 0.0, 0.0)]
    use = {}
    rows = []
    for name, z, V, m, kW in items:
        zk = next(k for k in zones if k.startswith(z)); use[zk] = use.get(zk, 0.0)+V
        rows.append(dict(item=name, zone=zk, volume_m3=V, mass_t=m, power_kW=kW))
    return dict(rows=rows, zones=[dict(zone=k, free_m3=v, used_m3=use.get(k, 0.0), ok=use.get(k, 0.0) <= v) for k, v in zones.items()],
                note='zone free volumes are PROTOTYPE estimates (layout envelopes), not measured from the generated model')


# ============================================================================ V-H missions ============================================
def missions(s, dM_t, life):
    ve = op.p(s)['exhaust_velocity_m_s']; F = op.power_cap_N(s)
    end0 = mm.coupled_mission(s, CIRC+dM_t*1e3)['end_mass_kg']        # tankage sized once for 0.016 c (one hardware set)
    rows = []
    for D in (45.0, 120.0, 200.0, 500.0, 1000.0):
        for vf in (0.002, 0.004, 0.006, 0.008, 0.010, 0.012, 0.014, 0.016):
            Rr = math.exp(vf*C/ve); prov = 0.0
            for _ in range(3):
                end = end0+prov; P = (Rr**4-1)*end
                ms = [end*Rr**(4-i) for i in range(5)]; Tb = sum((a-b)*ve/F for a, b in zip(ms, ms[1:]))
                dist = sum(ve*(a-b)/F*ve*0.5*vf*C/ve for a, b in zip(ms, ms[1:]))*0 + sum(0.5*vf*C*(a-b)*ve/F for a, b in zip(ms, ms[1:]))
                cruise = max(0.0, 2*D*AU-dist)/(vf*C); tot = cruise/DAY+Tb/DAY+30
                prov = max(0.0, msn.provisioning(12, max(365.0, tot), 'mixed', life=life)['total_kg']-10e3)
            rows.append(dict(D_AU=D, v_c=vf, round_trip_d=tot, burn_d=Tb/DAY, propellant_t=P/1e3, departure_t=(end+P)/1e3,
                             consumables_t=prov/1e3, equipment_h=tot*24, burn_h=Tb/3600, defense_rel=[(vf/0.016)**k for k in (1, 2, 3)],
                             dust_rel=(vf/0.016)*cruise/YR, reliability=math.exp(-tot*24/2.0e5)))
    par = []
    for D in (45.0, 120.0, 200.0, 500.0, 1000.0):
        rs = [r for r in rows if r['D_AU'] == D]
        for k in (0, 1, 2):
            front = [r for r in rs if not any((o['round_trip_d'] <= r['round_trip_d'] and o['departure_t'] <= r['departure_t'] and
                                               o['defense_rel'][k] <= r['defense_rel'][k]) and
                                              (o['round_trip_d'] < r['round_trip_d'] or o['departure_t'] < r['departure_t'] or o['defense_rel'][k] < r['defense_rel'][k])
                                              for o in rs)]
            par.append(dict(D_AU=D, defense_law=('v1', 'v2', 'v3')[k], pareto_v=[r['v_c'] for r in front]))
    return dict(rows=rows, pareto=par, note='one hardware set; no value is assigned to a day; v^3 defense scaling is a sensitivity case')


def rad_summary(rad, Rd, lift_W):
    """Physical scaling of the 3-D tallies: per fission in each unit x fission rate of one unit at full load (750 K, R5-A)."""
    if not rad.get('runs'): return dict(status='not run')
    Pt = 3.5e6/Rd['l2_750']['eta']; f_rate = Pt/(200e6*1.602e-19)
    V = [r['ratio'] for r in rad['runs']['V']['rows']]
    B_, S_ = rad['runs']['B']['cells'], rad['runs']['S']['cells']
    tk = [k for k in B_ if k.startswith('tank_')]
    def heat(c, ks):
        tot = sum(c[k]['heat_eV'] for k in ks); err = math.sqrt(sum((c[k]['heat_eV']*c[k]['heat_rel'])**2 for k in ks))/max(tot, 1e-30)
        return tot*1.602e-19*f_rate, err
    hb, eb = heat(B_, tk); hs, es = heat(S_, tk)
    vol = {'ring_A': math.pi*(30**2-22**2)*4*1e6, 'ring_B': math.pi*(30**2-22**2)*4*1e6, 'refuge': math.pi*4.5**2*6*1e6,
           'keel_lane': math.pi*5.59**2*35*1e6, 'district_electronics': math.pi*(5.59**2-3.6**2)*15*1e6}
    reg = {k: dict(bare_n_cm2_s=B_[k]['flux_n']/vol[k]*f_rate, shadowed_n_cm2_s=S_[k]['flux_n']/vol[k]*f_rate, rel=S_[k]['flux_n_rel'],
                   shadowed_over_bare=S_[k]['flux_n']/max(B_[k]['flux_n'], 1e-30),
                   g_shadowed_over_bare=S_[k]['flux_g']/max(B_[k]['flux_g'], 1e-30)) for k in vol}
    return dict(verification=dict(min=min(V), max=max(V), mean=sum(V)/len(V), passes=0.9 < sum(V)/len(V) < 1.1),
                fission_rate_per_unit=f_rate, Pt_per_unit_W=Pt, tank_heat_bare_W=hb, tank_heat_bare_rel=eb, tank_heat_scatter_W=hs,
                tank_heat_scatter_rel=es, scatter_over_bare=hs/hb, lift_W=lift_W, scatter_share_of_lift_full=3*hs/lift_W,
                scatter_share_of_lift_C=3*hs*2/3/lift_W, regions=reg,
                finding=(f'Verification passes: in a void model OpenMC reproduces the point kernel in every tank volume (ratio {min(V):.2f}-{max(V):.2f}, '
                         f'mean {sum(V)/len(V):.3f}), so the ship frame, the CSG placement and the normalisation agree with the generated model. With the '
                         f'shadow cone removed from the source, radiation scattered by the casing, blades and bulkhead still delivers '
                         f'{100*hs/hb:.0f} % (±{100*es:.0f} % statistical) of the unshielded tank heating: ~{hs:.0f} W per unit at full power over the 13 '
                         f'tanks, {3*hs:.0f} W for three units against a {lift_W:.0f} W He-3 stage lift. Ring A sees {100*reg["ring_A"]["shadowed_over_bare"]:.0f} % '
                         f'of its unshielded neutron flux the same way. A shadow shield alone does not protect the tanks or the rings: side and '
                         'structure shielding (or a longer standoff) is required. Scatter fractions only; no dose or safety claim.'))


# ============================================================================ dual baseline ===========================================
def dual_baseline(H, Rd, D, E):
    hm = H['topologies']['H6a']
    return [
        dict(subsystem='Propulsion heat transport (hot loop)',
             physics='radiation T^4; hoop stress p D / 2 sigma; hydrostatic head rho a L in a 1.36 g burn; Li vapour pressure',
             today='Li loops to ~1350 K (SP-100 components); refractory creep allowables ~8-30 MPa near 1950 K',
             unresolved=f'{hm["total_t"][1]:,.0f} t nominal (H6a): walls dominate at ~2 MPa; 1990 K coolant inlet for a 1800 K mean surface; frozen start',
             advance='pressure boundary at ~100 MPa allowable and ~3 t/m3 near 2000 K (C/C-SiC tube with refractory liner) or a low-head layout',
             fiction='Wayfarer uses a refractory-composite sectionalized network (H6a topology) at the C/C-SiC row of the material sensitivity',
             research_value=f'{hm["total_t"][1]:,.0f} t', fiction_value=f'{next(x for x in H["material_sensitivity"] if x["sigma_MPa"] == 100)["total_t"]:,.0f} t'),
        dict(subsystem='Hot radiator margin', physics='20 % rejection margin (working rule)', today='rule met only if L2 takes <= %.1f m of hot length' % Rd['hot_free_m'],
             unresolved='dedicated 700 K L2 sections need %.1f m' % Rd['l2_700']['dedicated']['length_m'], advance='cross-strapped dual-header L2 sections at 750 K',
             fiction='R5-A (750 K cross-strapped) keeps the rule', research_value='R5-A meets the rule', fiction_value='same'),
        dict(subsystem='L2 generation', physics='Brayton efficiency = Carnot fraction x (1 - T_rej/T_in)', today='~1150 K turbine inlet (Prometheus class)',
             unresolved='efficiency collapses above ~750 K rejection; trip transient depends on ramp rate (unknown)',
             advance='1500 K turbine inlet (ceramic / refractory turbomachinery)', fiction='3 x 3.5 MWe C at 750 K rejection; 1500 K inlet would cut the section by ~%.0f %%' % (
                 100*(1-Rd['advanced_turbine'][0]['L_cross_m']/Rd['l2_scan'][3]['L_cross_m'])),
             research_value='3 x 3.5 MWe, 750 K', fiction_value='same hardware'),
        dict(subsystem='Radiation protection', physics='neutron/photon transport (OpenMC, ENDF/B-VIII.0)', today='OpenMC 3-D ship-frame model, no core design',
             unresolved='shield mass, crew dose, tank scatter OPEN', advance='validated source term and shielding benchmarks',
             fiction='shadow shield + structural scatter limits as computed; crew safety not claimed', research_value=E.get('status', 'see V-E'), fiction_value='OPEN'),
        dict(subsystem='Storage and black start', physics='energy = power x time; converter limits', today='Li-ion 100-180 Wh/kg, supercaps, flywheels',
             unresolved='unit ramp rate after a trip', advance='none needed', fiction='independent restart pack R1b', research_value='closes', fiction_value='closes'),
        dict(subsystem='ECLSS', physics='mass balance per person', today='ISS-class per-crew hardware', unresolved='hub rotary interface for the cross-ring unit',
             advance='rotating air seals at r ~1.4 m', fiction='7 units with a hub unit', research_value='7 units pass all cases', fiction_value='same'),
    ]


# ============================================================================ convergence ============================================
def convergence(s, P4, H, Rd, D, M_items):
    c4 = P4['convergence']['candidates']
    def coupled(dM):
        m = mm.coupled_mission(s, CIRC+dM*1e3); b = mm.coupled_mission(s, CIRC)
        return dict(departure_t=m['departure_mass_kg']/1e3, extra_t=(m['departure_mass_kg']-b['departure_mass_kg'])/1e3, propellant_t=m['propellant_kg']/1e3)
    base_items = {k: v for k, v in c4[-1]['items_t'].items() if k not in ('heat_transport_H5', 'section_700K', 'bulkhead_relocation')}
    nonT = [sum(v[i] for v in base_items.values()) for i in B]
    cands = []
    def add(name, src, dry, thermal, elec, rad, fault, maturity, problems, geometry):
        cands.append(dict(name=name, source=src, dry_added_t=dry, coupled=[coupled(x) for x in dry], thermal=thermal, electrical=elec,
                          radiation=rad, fault_tolerance=fault, maturity=maturity, problems=problems, geometry=geometry))
    add('Corrected existing reference (CIRC-001 coupled)', 'Phase V', [0.0]*3, 'L2 has no burn sink; LOW fails at the high band', 'production EPS',
        'not assessed', 'canon', 'canon', ['hot loop OPEN', 'L1 900 K reject has no radiator'], 'production')
    for c in c4[:5]:
        if c['name'].startswith('Baseline'): continue
        add(c['name'], 'Phase II/III (recoupled)', c['dry_added_t'], 'does not close in burns', 'see Phase III', 'gate open', '-', 'study', ['superseded'], 'Phase III')
    add('Phase IV N2-R4a (as reported, H5)', 'Phase IV', c4[-1]['dry_added_t'], '700 K section breaks the 20 % rule', 'closes nominal after one loss',
        'TRANSPORT-INFORMED', 'H5 zones', 'TRL 3', ['H5 mass basis invalid (C5-01/02)'], '24 m 700 K section')
    for key in ('H3', 'H6a', 'H6e', 'H6f'):
        t = H['topologies'][key]['total_t']
        add(f'N2-R4a + {key} (Phase V transport)', 'Phase V', [nonT[i]+t[i] for i in B], 'R5-A geometry: 20 % rule kept', 'C, see V-D',
            'V-E', {'H3': 'blade loop single point', 'H6a': 'section isolation + redundant trunks', 'H6e': '4 sections', 'H6f': 'as H6a, hotter inlet'}[key],
            H['topologies'][key]['maturity'], ['wall mass at 2 MPa'], 'R5-A')
    adv = next(x for x in H['material_sensitivity'] if x['sigma_MPa'] == 100)['total_t']
    add('Preferred Phase V candidate, FICTIONAL baseline (R5-A + H6a in C/C-SiC + 3 x 3.5 MWe C)', 'Phase V', [nonT[i]+adv for i in B],
        'closes with the 20 % rule', 'closes nominal; high band needs shedding', 'OPEN', 'section + path redundancy', 'requires the bridging material',
        ['material not demonstrated', 'frozen start'], 'R5-A')
    return cands


def problems():
    return [
        dict(id='P5-01', sev='BLOCKER (research)', text='Hot-loop pressure boundary at ~2000 K and ~2 MPa: walls dominate the mass (V-B); no demonstrated material closes.'),
        dict(id='P5-02', sev='HIGH', text='Coolant inlet ~1990 K is needed for an 1800 K mean surface (dT 300 K, 30 K drop): beyond Mo-TZM, at the Mo-Re/W-Re limit.'),
        dict(id='P5-03', sev='HIGH', text='Dedicated L2 sections under strategy C break the 20 % HOT rule; only cross-strapped 750 K sections fit.'),
        dict(id='P5-04', sev='HIGH', text='A forward-facing bulkhead emitter (R5-C) irradiates the He-3 tank zone; tank IR leak vs the 118 W lift decides it.'),
        dict(id='P5-05', sev='HIGH', text='L1 conversion reject at ~900 K still has no radiator; the canon burn heat pumps dominate it (existing allocation).'),
        dict(id='P5-06', sev='MEDIUM', text='Unit ramp rate after a trip is unknown; the conservative case drains the battery in a high band.'),
        dict(id='P5-07', sev='MEDIUM', text='Frozen start: ~%s of thaw and preheat before the first ignition; L2 alone takes days.'),
        dict(id='P5-08', sev='MEDIUM', text='Hub ECLSS cross-ring duct through the rotating transfer drum not designed.'),
        dict(id='P5-09', sev='MEDIUM', text='R5-B conflicts with the fixed aft edge (Q52 option D) and the engine exclusion rule.'),
        dict(id='P5-10', sev='HIGH', text='3-D transport: structure scatter around the shadow cone reaches the He-3 tanks and ring A at a large fraction of the unshielded level; side/structure shielding needed; shield mass OPEN, no dose claim.'),
    ]


def decisions():
    return [
        dict(id='DR5-01', q='Adopt R5-A (750 K cross-strapped dual-header L2 sections, relocated bulkhead) as the radiator research baseline?', rec='yes'),
        dict(id='DR5-02', q='Adopt H6a (two 60 % trunk pairs, 6 isolatable sections, heat-pipe fins, cross-feed) as the hot-loop topology?', rec='yes'),
        dict(id='DR5-03', q='Accept a refractory-composite pressure boundary (~100 MPa, ~3 t/m3 at 2000 K) as a FICTIONAL-baseline assumption, with the research mass kept visible?', rec='owner'),
        dict(id='DR5-04', q='Keep Li as the coolant (Na, K near-critical; Sn too heavy under head; He-Xe pumping ~1 GW)?', rec='yes'),
        dict(id='DR5-05', q='Fictional L1: direct conversion of charged drive products with waste into the hot loop, closing the 900 K gap?', rec='owner'),
        dict(id='DR5-06', q='ECLSS: keep 7 units if the hub duct runs through the transfer drum; else 8 (4 + 4)?', rec='yes'),
        dict(id='DR5-07', q='LOG-G1: 3 t gross containers (single-arm handling) instead of 6 t?', rec='yes'),
        dict(id='DR5-08', q='Next: 3-D transport with weight windows to quote shield transmission (beyond the scatter split)?', rec='yes'),
    ]


def main():
    s = spec.load()[0]
    P4 = json.loads((R/'phase4.json').read_text())
    life = tomllib.loads((ROOT/'data/life_support.toml').read_text())
    cfg = config(s)
    H = transport(s)
    Rd = radiators(s, P4, H)
    D = electrical(s, H)
    L = ledgers(s, Rd, H, D)
    L2c = Rd['l2_700']
    corr = corrections(s, P4, H['topologies'] | {}, L2c) if False else None
    Hs = {k: v for k, v in H['topologies'].items()}
    corr = corrections(s, P4, Hs, L2c)
    rad = json.loads((R/'phase5_rad3d.json').read_text()) if (R/'phase5_rad3d.json').exists() else dict(status='not run')
    c4 = P4['convergence']['candidates'][-1]['items_t']
    items = {
        'L2 (3 x 3.5 MWe, 750 K)': ([c4['L2'][i]*Rd['l2_scan'][4]['unit_t']/Rd['l2_scan'][3]['unit_t'] for i in B], -92.0, -80.0, 'NEW'),
        'L1 (derived)': (c4['L1'], -140.0, -120.0, 'NEW'), 'L3': (c4['L3'], 95.0, 106.0, 'NEW'),
        'storage (buffer + restart)': (c4['storage'], -92.0, 40.0, 'NEW'), 'distribution': (c4['distribution'], -92.0, 100.0, 'NEW'),
        'scatter allowance (OPEN)': (c4['scatter_allowance'], 105.0, 140.0, 'NEW (OPEN)'), 'ECLSS modular increment': (c4['ECLSS_modular'], 95.0, 106.0, 'NEW'),
        'hot loop H6a (research)': (Hs['H6a']['total_t'], -140.0, 26.0, 'NEW (canon OPEN line)'),
        'L2 sections 750 K cross-strapped + dual headers': ([Rd['l2_750']['cross']['area_m2']*k/1e3+Rd['l2_750']['cross']['header_t']*(0.7, 1.0, 1.5)[i]
                                                             for i, k in enumerate((0.3, 0.5, 0.8))], 26.0, 50.4, 'NEW'),
        'bulkhead relocation': ([0.0, 2.0, 5.0], 26.0, 27.0, 'EXISTING (moved)'),
        'LOG-G1 tare (3 t containers, 12 months)': ([7*0.55]*3, 95.0, 106.0, 'NEW'),
    }
    M = mass(s, items)
    # power-limited drive: the coupled end mass lowers the peak acceleration, so the head and the loop mass fall; iterate the H6a line
    coup = []
    for label, it in (('research', items), ('fictional', None)):
        g = 1.362
        for _ in range(4):
            Hc = transport(s, accel_g=g) if label == 'research' else None
            if label == 'research':
                it = dict(items); it['hot loop H6a (research)'] = (Hc['topologies']['H6a']['total_t'], -140.0, 26.0, 'NEW (canon OPEN line)')
                Mc = mass(s, it); g = Mc['accel']['a_end_nom_g']
        if label == 'research':
            coup.append(dict(case=label, a_end_g=g, H6a_t=Hc['topologies']['H6a']['total_t'], departure_t=[c['departure_t'] for c in Mc['cases']],
                             dry_added_t=[c['dry_added_t'] for c in Mc['cases']]))
    items_f = dict(items); items_f['hot loop H6a (research)'] = ([next(x for x in H['material_sensitivity'] if x['sigma_MPa'] == 100)['total_t']]*3, -140.0, 26.0, 'FICTIONAL')
    M_f = mass(s, items_f)
    EC = eclss(); LG = logistics(); AL = allocation()
    MS = missions(s, M['cases'][1]['dry_added_t'], life)
    CV = convergence(s, P4, H, Rd, D, items)
    lift = json.loads((R/'phase3.json').read_text())['shielding']['he3_stage_lift_W']
    RS = rad_summary(rad, Rd, lift)
    DB = dual_baseline(H, Rd, D, dict(status=(f"scatter {100*RS['scatter_over_bare']:.0f} % of bare; {3*RS['tank_heat_scatter_W']:.0f} W vs {lift:.0f} W lift") if RS.get('verification') else 'not run'))
    pr = problems(); pr[6]['text'] = pr[6]['text'] % ('%.0f GJ' % ((Hs['H6a']['startup']['thaw_J']+Hs['H6a']['startup']['blade_preheat_J'])/1e9))
    hm = Hs['H6a']
    H['finding'] = (f'With a pressure- and creep-based wall the hot loop is a structural problem, not a pumping one. A 1800 K mean surface needs a '
                    f'~{H["inlet_T"]["300"]:.0f} K coolant inlet at dT 300 K; Li then sits at ~{hm["net"][1]["p_trunk_max"]/1e6:.1f} MPa at the aft end '
                    f'of a 1.36 g burn (vapour pressure + subcooling + {hm["net"][1]["head_full"]/1e6:.2f} MPa head), and at a 15 MPa creep allowable the '
                    f'walls weigh several times the coolant. H6a (two 60 % trunk pairs, six isolatable sections, heat-pipe fins, cross-feed) is the '
                    f'best fault-tolerant network at {hm["total_t"][1]:,.0f} t nominal ({hm["total_t"][0]:,.0f}-{hm["total_t"][2]:,.0f} t correlated cases); '
                    f'H2 is lighter but a single puncture ends the burn. Material is the lever: the same network is '
                    f'{next(x for x in H["material_sensitivity"] if x["sigma_MPa"] == 100)["total_t"]:,.0f} t with a 100 MPa, 3 t/m3 composite boundary.')
    rb = next(r for r in L['rows'] if r['state'] == 'high-power burn'); rd = next(r for r in L['rows'] if r['state'].startswith('defense'))
    wz = rb['zones']['WARM_R5D']
    L['finding'] = (f'Closing (excluding L1): ' + ', '.join(r['state'] for r in L['rows'] if r['closes_R5D_except_L1']) + '. '
                    f'Burns miss WARM by {(wz["load_W"]-wz["capacity_W"])/1e6:.2f} MW even re-zoned (R5-D), because the hot-blade exchange debit '
                    f'({wz["load_W"]/1e6:.1f} MW load with debit vs {wz["capacity_W"]/1e6:.1f} MW usable); a defense engagement needs a thermal buffer of '
                    f'~{rd["pcm_t_per_min"]:.1f} t of PCM per minute of engagement. ')
    out = dict(status='STUDY / NONCANON (ISSA Phase V)', config_id=cfg['id'], config_hash=cfg['hash'], corrections=corr, transport=H, radiators=Rd,
               ledgers=L, electrical=D, mass=M, accel_coupled=coup, mass_fictional=M_f, eclss=EC, logistics=LG, allocation=AL, missions=MS, convergence=CV,
               dual_baseline=DB, radiation_summary=RS, problems=pr, decisions=decisions(), radiation=rad)
    (R/'phase5_config.json').write_text(json.dumps(cfg, indent=1, default=str))
    (R/'phase5.json').write_text(json.dumps(out, indent=1, default=lambda o: list(o) if isinstance(o, tuple) else str(o)))
    print('config', cfg['id'], cfg['hash'])
    for k in ('H1', 'H2', 'H3', 'H5', 'H6a', 'H6e', 'H6f'):
        print(k, r3(Hs[k]['total_t'], 0), r3(Hs[k]['pump_MW'], 1))
    print('L2 scan', [(x['T_K'], round(x['L_dedicated_m'], 1), round(x['L_cross_m'], 1), x['fits_hot_rule_cross']) for x in Rd['l2_scan']], round(Rd['hot_free_m'], 1))
    print('emitter', {b: (round(v['capacity_W']/1e6, 1), round(v['tanks']['leak_W_total'], 1), {k: round(x, 4) for k, x in v['F'].items()}) for b, v in Rd['emitter'].items()})
    print('ledger', [(r['state'][:22], r['closes_R5D_except_L1'], [k for k, z in r['zones'].items() if not z['ok']], round(r['pcm_t_per_min'], 2)) for r in L['rows']])
    print('coupled', [(c['a_end_g'], r3(c['H6a_t'], 0), r3(c['departure_t'], 0)) for c in coup])
    print('mass', [(r['dry_added_t'], round(r['departure_t'])) for r in M['cases']], 'fict', [round(r['departure_t']) for r in M_f['cases']])
    print('tanks', [{k: round(v, 2) for k, v in t['fill'].items()} for t in M['tanks']], M['accel'], M['attitude'])
    print('transient', [(t['case'], t['life'], t['t_restored_s'], round(t['peak_deficit_W']/1e6, 2), round(t['storage_kWh_used'], 1), t['steady_ok']) for t in D['transient']])
    print('sens', [(x['material'][:20], round(x['total_t']), round(x['coast_only_head_t'])) for x in H['material_sensitivity']])
    print('items', {k: r3(v[0], 0) for k, v in items.items()})
    print('rad', {k: v for k, v in RS.items() if k not in ('regions', 'finding')})
    print('L1', [round(x/1e6, 2) for x in D['L1']['drive_specific_W']], [round(x/1e6) for x in D['L1']['existing_W']])


if __name__ == '__main__':
    main()
