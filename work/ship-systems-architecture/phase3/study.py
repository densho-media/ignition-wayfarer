"""ISSA Phase III-A/B/D/E: corrections, coupled optimisation, missions and convergence. STUDY (NONCANON). Pure Python.
Reads references/p1_power_loads.json (EPS-A), results/phase2_*.json, results/phase3_eps_g1.json and the spec; writes results/phase3.json.

    python3 src/wayfarer/power_loads.py
    python3 work/ship-systems-architecture/phase2/{eps_b,eclss_mass,placement,mission,fmea}.py   (Phase II, corrected inputs)
    python3 work/ship-systems-architecture/phase3/eps_g1.py
    python3 work/ship-systems-architecture/phase3/study.py

Every band is (low, nominal, high) demand or technology. Class labels: MODEL-DERIVED (read from the spec or EPS-A), STUDY (computed here
from stated assumptions), PROTOTYPE (an unsourced choice), SPECULATIVE (beyond demonstrated technology), OPEN (unknown, kept unknown).
"""
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
sys.path.insert(0, str(ROOT/'src/wayfarer'))
import spec  # noqa: E402
import operating_point as op  # noqa: E402
import mass_model  # noqa: E402
sys.path.insert(0, str(WORK/'phase2'))
import eps_b  # noqa: E402
import placement as plc  # noqa: E402
import mission as msn  # noqa: E402

SIG = 5.670374419e-8; EPS = 0.91; G0 = 9.80665; C = 299792458.0; AU = 1.495978707e11; DAY = 86400.0; YR = 365.25*DAY
B = (0, 1, 2); BANDS = ('low', 'nominal', 'high')
# radiator sections (MODEL-DERIVED: thermal_geometry zones as summarised in Phase II eps_b; net face areas include both faces)
WARM = dict(T=440.0, area=3702.0, length=22.5, design_W=5e6)
LOW = dict(T=300.0, area=3060.0, length=20.0, design_W=1e6)
CHANNELS_W_440 = 51.4e6         # coast: drained hot-blade warm channels at 440 K (Phase II thermal ledger)
RING_COLD = dict(coast=1.38e6, burn=0.15e6)
MARGIN = 1.2                    # 20 % rejection margin (Phase I rule)
FACE_PER_M = WARM['area']/WARM['length']     # m2 of net face area per metre of RAD-ZONE / blade length (three blades, two faces)
HOT_T = 1800.0; HOT_ALLOWANCE_W = 3.6e9


def q_area(Q, T):
    return Q/(EPS*SIG*T**4)


def cap(area, T):
    return area*EPS*SIG*T**4


def st(pl, sid, key='generation_W'):
    return pl['states'][sid][key]


def heat(pl, sid, c):
    return pl['states'][sid]['heat_W'].get(c, [0.0, 0.0, 0.0])


# ------------------------------------------------------------------ III-A 3.1 battery ----------------------------------------------
def battery(pl):
    S = pl['storage']; kwh = S['kWh']; J2k = 1/3.6e6
    eol = sorted(x*J2k for x in S['end_of_life_usable_J'])
    pack_kg = S['pack_mass_kg']
    c_rate = (0.7, 1.0, 2.0)                                  # continuous discharge C-rate of an 800 Wh/kg pack (OPEN; high-energy cells)
    p_max = [kwh['main_usable']*c/1e3 for c in c_rate]        # MW
    coast = st(pl, 'COAST_HV_PROACTIVE')
    crew = st(pl, 'SURVIVAL_CREW'); bs = S['black_start_services_W']
    # budgets (kWh, low / nominal / high), each with its basis; restart uncertainty x1.5 on the high end only
    L2_restart = (60.0, 300.0, 750.0*1.5)        # warm start: TAC motoring ~5 % Pe for 15 min (~25 kWh) + controls; cold start: primary-loop trace
    #                                               heating 100-250 kW for 1-3 h plus motoring (PROTOTYPE, no L2 design)
    crew_bridge = tuple(crew[i]/1e3*h for i, h in zip(B, (4.0, 8.0, 12.0)))        # crew-only loads until L3 runs (fission-Stirling start)
    pulse = kwh['pulse_bank_recharge']
    drive_restart = (20.0, 100.0, 400.0)          # PROP.DRIVE_STANDBY 20-400 kW for ~1 h before re-ignition (OPEN) - only if the drive
    #                                               restarts before L2 (it should not: L2 first)
    eol_unit = (0.95, 0.90, 0.85)                 # L2 unit output at end of service life (Brayton degradation, OPEN)
    after_trip = [2*1.75*eol_unit[i] for i in B]
    gap_MW = [max(0.0, coast[i]/1e6-after_trip[i]) for i in B]
    buffering = [gap_MW[i]*1e3*h for i, h in zip(B, (1.0, 2.0, 4.0))]    # bridge a unit trip until the standby unit runs (hours, warm start)
    budgets = dict(
        aux_plant_restart=dict(kWh=L2_restart, basis='L2 unit warm or cold restart (motoring + trace heating), x1.5 restart uncertainty on the high end', cls='PROTOTYPE'),
        propulsion_restart=dict(kWh=drive_restart, basis='PROP.DRIVE_STANDBY before re-ignition; not needed if L2 restarts first', cls='OPEN'),
        pulse_bank_recharge=dict(kWh=(pulse, pulse, pulse), basis='canon black-start step 2 (BASELINE): battery charges the pulse bank, 720 MJ / 0.9', cls='MODEL-DERIVED'),
        emergency_buffering=dict(kWh=tuple(buffering), basis='C-lean unit trip at end of life: coast proactive load minus two degraded units, until the standby unit runs', cls='STUDY'),
        protected_survival=dict(kWh=crew_bridge, basis='crew-only loads until the L3 source runs (4-12 h); cryo is paused inside the sealed hold, never battery-fed', cls='STUDY'),
    )
    cryo_on_battery_kWh = [st(pl, 'SURVIVAL_MISSION')[i]/1e3*58 for i in B]
    opts = {}
    def opt(name, keep, note, separate_pack_t=0.0):
        res = [sum(budgets[k]['kWh'][i] for k in keep) for i in B]
        opts[name] = dict(protected_kWh=res, fraction_BOL=[r/kwh['main_usable'] for r in res] if not separate_pack_t else [0.0]*3,
                          ride_through_BOL_kWh=[kwh['main_usable']-(0 if separate_pack_t else r) for r in res],
                          ride_through_EOL_kWh=[eol[0 if i == 2 else (1 if i == 1 else 2)]-(0 if separate_pack_t else res[i]) for i in B],
                          keeps=keep, separate_pack_t=separate_pack_t, note=note)
    opts['R0 canon'] = dict(protected_kWh=[kwh['black_start_reserve']]*3, fraction_BOL=[S['reserve_fraction']]*3,
                            ride_through_BOL_kWh=[kwh['ride_through']]*3, ride_through_EOL_kWh=[x*J2k for x in S['ride_through_at_end_of_life_J']],
                            keeps=['1 h of black-start services at the high band', 'pulse_bank_recharge'],
                            note='EPS-A: protects 1 h of the full black-start service load plus the pulse step (BASELINE sequence)')
    opt('R1 L2-first restart', ['aux_plant_restart', 'protected_survival', 'pulse_bank_recharge'],
        'Restart one L2 unit first, pause cryo inside the 58-77 h sealed hold, keep the canon pulse step (PROPOSED sequence change, not canon)')
    opt('R1b without the pulse step', ['aux_plant_restart', 'protected_survival'],
        'As R1 but the drive restarts only after L2 runs, so the pulse bank is charged from L2 (would change BASELINE step 2: owner decision)')
    pk_t = round((max(budgets['aux_plant_restart']['kWh'])+max(crew_bridge)+pulse)/0.8/1e3, 2)
    opt('R2 separate restart pack', ['aux_plant_restart', 'protected_survival', 'pulse_bank_recharge'],
        f'A {pk_t:.2f} t restart pack (800 Wh/kg) on bus E carries R1; the whole main pack becomes ride-through and a main-pack fault no longer '
        'takes the restart energy (FMEA F11 common mode removed)', separate_pack_t=pk_t)
    o = opts
    finding = (f"72 % is set by protecting a full hour of the high-band black-start service load. Restarting one L2 unit first and pausing cryo "
               f"inside the sealed hold (R1) protects {o['R1 L2-first restart']['protected_kWh'][1]:,.0f} kWh nominal "
               f"({100*o['R1 L2-first restart']['fraction_BOL'][1]:.0f} %; {100*o['R1 L2-first restart']['fraction_BOL'][0]:.0f}-"
               f"{100*o['R1 L2-first restart']['fraction_BOL'][2]:.0f} % across the bands, the high end being a cold restart with 1.5x uncertainty and a "
               f"12 h L3 start). Keeping one unit in warm standby cuts the restart to ~25 kWh. A separate {pk_t:.1f} t restart pack (R2) frees the whole "
               f"main pack for ride-through and removes the single-pack common mode. At 1C an 800 Wh/kg pack delivers 2 MW, below the 3.4 MW coast load: "
               f"the ride-through is power-limited, loads must shed to the discharge limit within seconds, and ride-through hours are an energy bound only.")
    return dict(kWh=kwh, corrected_note='Phase II report printed MWh values with a kWh label (J/3.6e9). Corrected: 2,000 kWh usable, 1,442 kWh protected, '
                                        '558 kWh ride-through, protected fraction 72 %.',
                eol_usable_kWh=eol, pack_kg=pack_kg, c_rate=c_rate, discharge_limit_MW=p_max,
                coast_load_MW=[x/1e6 for x in coast], power_limited=[coast[i]/1e6 > p_max[i] for i in B],
                black_start_services_MW=[x/1e6 for x in bs], budgets=budgets, options=opts, cryo_on_battery_kWh=cryo_on_battery_kWh,
                finding=finding)


# ------------------------------------------------------------------ III-A 3.2 coupled buffer ---------------------------------------
CHEM = {  # pack-level specific energy Wh/kg, specific power kW/kg, round-trip one-way efficiencies (PROTOTYPE bands)
    'Li-ion high-power cells': dict(e=150.0, p=1.5, eta=0.96, cls='PROTOTYPE'),
    'supercapacitor bank': dict(e=6.0, p=6.0, eta=0.98, cls='PROTOTYPE'),
    'flywheel (composite rotor)': dict(e=30.0, p=1.0, eta=0.95, cls='PROTOTYPE'),
    'main battery (800 Wh/kg, 1C)': dict(e=800.0, p=0.8, eta=0.95, cls='PROTOTYPE'),
}


def buffer(pl, planning):
    pro0 = st(pl, 'COAST_HV_PROACTIVE'); act0 = st(pl, 'COAST_HV_TRIGGERED')
    pro_w = heat(pl, 'COAST_HV_PROACTIVE', 'WARM'); act_w = heat(pl, 'COAST_HV_TRIGGERED', 'WARM')
    warm_use = cap(WARM['area'], WARM['T'])/MARGIN
    eol = (0.95, 0.90, 0.85)
    cases = [('C-lean 3 running + 1 standby', 3, 1.75e6), ('C-lean all 4 running (no hot standby)', 4, 1.75e6),
             ('C-lean after one unit trip (2 running)', 2, 1.75e6), ('2+1 x 2.66 MWe, 2 running', 2, 2.66e6),
             ('4+1 x 1.33 MWe, 4 running', 4, 1.33e6)]
    rows = []
    for dem in ('known loads', 'known + OPEN planning loads'):
      pro = [pro0[i]+(planning[i] if dem != 'known loads' else 0.0) for i in B]; act = [act0[i]+pro[i]-pro0[i] for i in B]
      for name, n, Pe in cases:
        for life, f in (('BOL', (1.0, 1.0, 1.0)), ('EOL', eol)):
            for i in B:
                gen = n*Pe*f[i]; surplus = gen-pro[i]; excess = act[i]-pro[i]
                heat_excess = max(0.0, act_w[i]-max(pro_w[i], 0.0)-max(0.0, warm_use-pro_w[i]))
                for t_eng in (1.0, 10.0, 60.0):
                    for interval in (600.0, 3600.0):
                        eta = CHEM['Li-ion high-power cells']['eta']
                        draw = excess*t_eng/eta
                        rech = draw/(surplus*eta) if surplus > 0 else math.inf
                        ok = surplus > 0 and rech <= interval-t_eng
                        sizes = {c: max(draw*1.25/3600/v['e'], excess/1e3/v['p']) for c, v in CHEM.items()}
                        rows.append(dict(demand=dem, case=name, life=life, band=BANDS[i], units_running=n, unit_W=Pe, generation_W=gen, surplus_W=surplus,
                                         excess_W=excess, t_eng_s=t_eng, interval_s=interval, draw_J=draw, recharge_s=rech, sustainable=ok,
                                         max_duty=(surplus*eta*eta/(excess+surplus*eta*eta)) if surplus > 0 else 0.0,
                                         buffer_kg=sizes, power_sets_mass={c: excess/1e3/v['p'] >= draw*1.25/3600/v['e'] for c, v in CHEM.items()},
                                         loss_heat_J=draw*(1-eta*eta), thermal_buffer_J=heat_excess*t_eng))
    def pick(name, life, i, t, iv, dem):
        return next(r for r in rows if r['demand'] == dem and r['case'] == name and r['life'] == life and r['band'] == BANDS[i] and r['t_eng_s'] == t and r['interval_s'] == iv)
    summary = []
    for dem in ('known loads', 'known + OPEN planning loads'):
     for name, _, _ in cases:
        for life in ('BOL', 'EOL'):
            r = [pick(name, life, i, 10.0, 600.0, dem) for i in B]
            summary.append(dict(demand=dem, case=name, life=life, surplus_MW=[x['surplus_W']/1e6 for x in r], sustainable=[x['sustainable'] for x in r],
                                max_duty=[x['max_duty'] for x in r], recharge_s=[x['recharge_s'] for x in r],
                                buffer_t_li=[x['buffer_kg']['Li-ion high-power cells']/1e3 for x in r],
                                buffer_t_sc=[x['buffer_kg']['supercapacitor bank']/1e3 for x in r],
                                thermal_buffer_GJ=[x['thermal_buffer_J']/1e9 for x in r]))
    return dict(rows=rows, summary=summary, chemistries=CHEM, warm_usable_W=warm_use,
                engagement_excess_W=[act0[i]-pro0[i] for i in B], planning_W=list(planning),
                finding=('With the OPEN planning loads (the owner\'s 4.8 MW case) C-lean has 0.53 MW of surplus at BOL nominal and none at EOL '
                         '(0.01 MW): a 10 s engagement every 10 min recharges in ~7 min at BOL and never at EOL, at the high band or after a unit trip. '
                         'On known loads alone the surplus is 1.9 MW BOL / 1.4 MW EOL nominal. Running all four units adds 1.75 MW but removes the hot '
                         'standby. The buffer is sized by ~21 MW of discharge power and 10 s of energy: ~14 t of high-power Li cells or ~13 t of '
                         'supercapacitors (supercapacitors win only below ~3 s), not 2.4 t. Engagement heat beyond the WARM spare needs a '
                         '~0.1-1 GJ thermal buffer.'))


# ------------------------------------------------------------------ III-A 3.3 thermal closure per circuit --------------------------
def thermal_closure(pl, U, planning):
    warm_use = cap(WARM['area'], WARM['T'])/MARGIN; low_use = cap(LOW['area'], LOW['T'])/MARGIN
    eta = [eps_b.brayton_eff(550.0, i) for i in B]
    standby_W = 0.01*U['Pt_W']                                  # warm standby: ~1 % thermal to keep the loop hot (PROTOTYPE)
    buf_loss = [0.04*21e6*10/600, 0.04*21e6*10/600, 0.04*28e6*60/600]   # averaged buffer losses on LOW (STUDY, 10-60 s / 10 min)
    states = [('COAST_HV_PROACTIVE', 'coast'), ('COAST_HV_TRIGGERED', 'coast (engagement, peak)'), ('HIGH_THRUST_PROACTIVE', 'burn'),
              ('HIGH_THRUST', 'burn (continuous active bound)'), ('SURVIVAL_MISSION', 'coast'), ('BLACK_START', 'coast'),
              ('POST_BURN_COOLDOWN', 'transition (channels refilling)')]
    rows = []
    for sid, mode in states:
        burn = mode.startswith('burn'); trans = mode.startswith('transition')
        for deg in ('intact', 'one blade circuit lost'):
            fk = 2/3 if deg != 'intact' else 1.0
            for i in B:
                plan = planning[i] if sid not in ('SURVIVAL_MISSION', 'BLACK_START', 'SURVIVAL_CREW') else 0.0
                gen = st(pl, sid)[i]+plan
                if 'TRIGGERED' in sid:
                    gen = min(gen, 3*1.75e6)                   # L2 carries at most its running capacity; the buffer supplies the rest
                L2_on = pl['states'][sid]['by_supply_W'].get('L2') is not None
                l2_waste = gen*(1/eta[i]-1) if L2_on else 0.0
                L1_on = pl['states'][sid]['by_supply_W'].get('L1') is not None
                l1_waste = gen*(1/0.30-1) if L1_on else 0.0              # L1 thermal conversion at ~30 % rejects at ~900 K
                circ = []
                circ.append(('HOT (drive blades, 1800 K)', heat(pl, sid, 'HOT')[i], HOT_ALLOWANCE_W if burn else 0.0, burn))
                circ.append(('L1 conversion reject (~900 K)', l1_waste, 0.0, L1_on))
                ch_cap = 0.0 if (burn or trans) else CHANNELS_W_440*fk
                circ.append(('Blade warm channels (L2 waste, CONDITIONAL)', l2_waste+(standby_W if L2_on else 0.0), ch_cap, L2_on))
                circ.append(('WARM section (440 K)', heat(pl, sid, 'WARM')[i]+plan, warm_use*fk, True))
                circ.append(('LOW section (300 K)', heat(pl, sid, 'LOW')[i]+(buf_loss[i] if 'TRIGGERED' in sid else 0.0), low_use*fk, True))
                circ.append(('Ring cold loops', heat(pl, sid, 'RING_COLD')[i], RING_COLD['burn' if burn else 'coast']*fk, True))
                out = []
                for nm, load, capW, active in circ:
                    if not active and load <= 0:
                        continue
                    out.append(dict(circuit=nm, load_W=load, capacity_W=capW, ok=load <= capW, margin_W=capW-load))
                rows.append(dict(state=sid, mode=mode, condition=deg, band=BANDS[i], circuits=out, closes=all(c['ok'] for c in out),
                                 fails=[c['circuit'] for c in out if not c['ok']]))
    return dict(rows=rows, warm_usable_W=warm_use, low_usable_W=low_use, standby_W=standby_W,
                rule='A state closes only if every active circuit passes at the band; unused area elsewhere gets no credit without a temperature and transport path.',
                finding=('No state closes at every band. In coast LOW fails at the high band (1.10 MW against 1.07 MW usable) and in every band once '
                         'a blade circuit is lost; WARM fails at the high band once the OPEN planning loads land on it, and an engagement fails WARM '
                         'without a thermal buffer. In burns the working doctrine fits WARM at the nominal band (5.0 MW with planning), but L1\'s own '
                         'conversion waste (~900 K) has no radiator in the production geometry at all: a gap Phase II did not count. L2 has no sink '
                         'in burns or while the channels refill.'))


# ------------------------------------------------------------------ III-A 3.4 shielding --------------------------------------------
def shielding(pl, G, cryo):
    U = G['reference_unit']; Pt = U['Pt_W']
    lam = 0.12; ef_shadow = U['shadow_t_m']/lam
    # Phase II consistency: 27.9 t per unit at 1.6 t/m3 against the 2.8 m3 envelope in the Phase II placement model
    p2 = dict(mass_t=27.9, rho=1.6, implied_m3=27.9/1.6, envelope_m3=2.8, consistent=False)
    g1 = dict(shadow_t=U['shadow_kg']/1e3, slab_t=U['slab_kg']/1e3, rho=G['rho_shield']/1e3,
              shadow_m3=U['envelopes'][2]['volume_m3'], slab_m3=next(e for e in U['envelopes'] if e['name'].startswith('Blade-facing'))['volume_m3'])
    g1['per_unit_t'] = g1['shadow_t']+g1['slab_t']
    # tanks: off-axis angle from a unit at the district (x -84, r 2.9) to each tank's aft end
    s = spec.load()[0]
    import fuel_storage as fs
    import layout
    tank_rows = []
    leak = 0.025                                                    # fraction of thermal power leaving a reflected core as n + gamma (bare)
    for t in fs.tanks(s):
        x_aft = layout.at(s, s['fuel_storage']['body']['bay_aft_x']) - 55.0 + t['x0'] if False else None
        tank_rows.append(t)
    x_unit = -84.0; r_unit = 2.9
    x0_ship = -144.75+109.25                                         # tank aft ends (ship x) from fuel_storage span (AFT + span[0])
    rows = []
    for t in tank_rows:
        dy = t['R']-r_unit; dx = x0_ship-x_unit; d = math.hypot(dx, dy); ang = math.degrees(math.atan2(dy, dx))
        flux = leak*Pt/(4*math.pi*d*d); area = math.pi*t['a_env']**2 + 2*t['a_env']*min(28.6, 10.0)*0.2
        dep_bare = flux*area
        in_cone = ang <= 12.5
        dep = dep_bare*(math.exp(-ef_shadow) if in_cone else 1.0)
        rows.append(dict(tank=t['name'], species=t['species'], R_m=t['R'], d_m=d, off_axis_deg=ang, in_shadow=in_cone,
                         bare_deposit_W=dep_bare*3, deposit_W=dep*3))           # three running units
    he3_rows = [r for r in rows if r['species'] == 'helium-3']
    he3_dep = sum(r['deposit_W'] for r in he3_rows)
    need_angle = max(r['off_axis_deg'] for r in rows)+1.0
    t_sh = U['shadow_t_m']; r0 = U['core_r_m']+0.05
    def frustum_kg(deg):
        r1 = r0+t_sh*math.tan(math.radians(deg)); return math.pi*t_sh/3*(r0*r0+r0*r1+r1*r1)*G['rho_shield']
    wide = dict(half_angle_deg=need_angle, shadow_t=frustum_kg(need_angle)/1e3, reference_shadow_t=frustum_kg(12.5)/1e3,
                outer_radius_m=r0+t_sh*math.tan(math.radians(need_angle)))
    wide['fits_bay'] = 2*wide['outer_radius_m'] <= 2.8
    # combined exposure, shutdown, electronics
    comb = {n: math.log(n) for n in (1, 2, 3, 4, 5)}
    T_op = 365*DAY
    shut = {}
    for days in (1, 7, 30):
        P_d = eps_b.decay_heat(Pt, days*DAY, T_op)
        g = plc.bare(P_d*0.4, 5.0)                           # decay gamma ~40 % of decay heat (order of magnitude), at 5 m, unshielded side
        shut[f'{days} d'] = dict(decay_W=P_d, bare_Sv_h_at_5m=g, crew_minutes_to_50mSv=0.05/g*60 if g > 0 else None)
    elec = {}
    for nm, d, ef in (('own plant PCU, in the shadow 3 m from the core', 3.0, ef_shadow), ('neighbour unit PCU across the bay, 3.4 m, behind the slab', 3.4, 13.3),
                      ('next module (M3) electronics, 14 m, off-axis', 14.0, 0.0)):
        Svh = plc.bare(Pt, d)*math.exp(-ef)*(0.3 if 'M3' in nm else 1.0)
        elec[nm] = dict(Gy_20yr=Svh*20*8766*0.6, limit_Gy=1e3, ok=Svh*20*8766*0.6 <= 1e3)
    return dict(phase2=p2, eps_g1=g1, tanks=rows, he3_deposit_W=he3_dep, he3_stage_lift_W=cryo['he3_stage_lift_W'],
                he3_ok=he3_dep <= 0.1*cryo['he3_stage_lift_W'], wide_cone=wide, combined_efolds=comb, shutdown=shut, electronics=elec,
                blocker=('BLOCKER: no validated radiation-transport tool (MCNP/OpenMC with evaluated nuclear data, coupled n-gamma, the real '
                         'geometry incl. blade scatter and streaming through the riser and hatch penetrations) is available in this environment. '
                         'Every shield mass here is a simplified exponential-attenuation estimate. Shielding stays OPEN; nothing here '
                         'establishes crew safety.'),
                finding=('Shield mass and volume now agree by construction (rho 1.9 t/m3 for LiH + 6 % W; Phase II used 1.6 and a 2.8 m3 envelope that '
                         'cannot hold 27.9 t). The nominal unit needs ~15 t shadow + ~22 t blade slab = ~37 t, more than Phase II. The He-3 tanks on the '
                         'outer ring sit ~25-30 deg off the district axis, outside a 12.5 deg shadow cone; three units would deposit up to ~16 kW '
                         '(upper bound, all of it absorbed) into tanks whose 3 K stage lifts ~118 W in total; even 1 % reaching the 3 K stage exceeds it. Either the shadow widens to ~30 deg (doesn\'t fit a '
                         '3.2 m bay) or the tanks get their own shadow: a coupling the district must solve. Shutdown gamma keeps crew out of line of '
                         'sight for weeks; servicing is robotic.'))


# ------------------------------------------------------------------ III-A 3.5 redundancy -------------------------------------------
def redundancy(configs, need_W, years=(1.0, 3.0, 5.0), trials=3000, seed=20261127):
    """Event Monte Carlo with shared dependencies. Rates per year (PROTOTYPE): unit lam_u (60 % conversion-side, repairable by ORU in
    repair_d; 40 % reactor-side, permanent for the mission), blade header per blade (repairable), blade sector damage (permanent for the units on
    it until rerouted 14 d), bus A/B (1 h cross-tie), software common cause (all units, 1 d), design common cause beta x lam_u (all, permanent),
    module damage zone (permanent for units in that module), maintenance equipment unavailable (repair times x2). Returns, per config and
    unit rate: events/yr causing a shortfall, unavailability, P(any shortfall by T), P(permanent shortfall by T), with and without repair."""
    rng = random.Random(seed); out = {}
    for cname, c in configs.items():
        out[cname] = {}
        for lam_u in (0.02, 0.05, 0.10):
            for repair in (True, False):
                T = max(years)*YR; res = {y: dict(short=0, perm=0) for y in years}; unavail = {y: 0.0 for y in years}; nshort = {y: 0 for y in years}
                for _ in range(trials):
                    ev = []          # (t0, t1, units)
                    def poisson(rate):
                        t = 0.0; ts = []
                        while True:
                            t += rng.expovariate(rate) if rate > 0 else math.inf
                            if t > T: return ts
                            ts.append(t)
                    maint_out = [(t, t+10*DAY) for t in poisson(0.2/YR)]
                    def rep(t, d):
                        if not repair: return math.inf
                        k = 2.0 if any(a <= t <= b for a, b in maint_out) else 1.0
                        return t+d*DAY*k
                    for k in range(c['n']):
                        for t in poisson(lam_u/YR):
                            ev.append((t, rep(t, 7.0) if rng.random() < 0.6 else math.inf, {k}))
                    for blade in set(c['blades']):
                        us = {k for k, b in enumerate(c['blades']) if b == blade}
                        for t in poisson(0.01/YR): ev.append((t, rep(t, 3.0), us))
                        for t in poisson(0.005/YR): ev.append((t, rep(t, 14.0), us))
                    for bus in set(c['buses']):
                        us = {k for k, b in enumerate(c['buses']) if b == bus}
                        for t in poisson(0.01/YR): ev.append((t, t+3600.0, us))
                    for t in poisson(0.01/YR): ev.append((t, t+DAY, set(range(c['n']))))
                    for t in poisson(0.05*lam_u/YR): ev.append((t, math.inf, set(range(c['n']))))
                    for mod in set(c['modules']):
                        us = {k for k, m in enumerate(c['modules']) if m == mod}
                        for t in poisson(0.002/YR): ev.append((t, math.inf, us))
                    pts = sorted({0.0, T} | {e[0] for e in ev} | {e[1] for e in ev if e[1] < T})
                    first = None; perm_t = None; dur = {y: 0.0 for y in years}; cnt = {y: 0 for y in years}; was = False
                    for a, b in zip(pts, pts[1:]):
                        m = (a+b)/2; down = set()
                        for e in ev:
                            if e[0] <= m < e[1]: down |= e[2]
                        capW = (c['n']-len(down))*c['unit_W']
                        short = capW < need_W
                        if short:
                            if first is None: first = a
                            for y in years:
                                lo, hi = a, min(b, y*YR)
                                if hi > lo: dur[y] += hi-lo
                            if not was:
                                for y in years:
                                    if a < y*YR: cnt[y] += 1
                            permdown = set()
                            for e in ev:
                                if e[0] <= m and e[1] == math.inf: permdown |= e[2]
                            if (c['n']-len(permdown))*c['unit_W'] < need_W and perm_t is None: perm_t = a
                        was = short
                    for y in years:
                        if first is not None and first < y*YR: res[y]['short'] += 1
                        if perm_t is not None and perm_t < y*YR: res[y]['perm'] += 1
                        unavail[y] += dur[y]/(y*YR); nshort[y] += cnt[y]
                out[cname][f'u={lam_u}{"" if repair else ", no repair"}'] = {
                    f'{y:g} yr': dict(P_any_shortfall=res[y]['short']/trials, P_permanent_shortfall=res[y]['perm']/trials,
                                      unavailability=unavail[y]/trials, shortfall_events_per_yr=nshort[y]/trials/y) for y in years}
    return out


# ------------------------------------------------------------------ III-A 3.6 mass ledgers -----------------------------------------
def ledgers(pl, G, bat, buf, s):
    reg = tomllib.loads((ROOT/'data/systems.toml').read_text())
    reg_by = {}
    for r in reg['system']:
        if r.get('mass_open'): continue
        reg_by.setdefault(r['budget_item'], [0.0, 0.0, 0.0])
        for j in B: reg_by[r['budget_item']][j] += r['mass_kg'][j]/1e3
    pcsc_other = (8.0, 13.5, 22.0)
    alloc = {'power_computers_steering_comms': 50.0, 'radiators_thermal': None, 'food_consumables': 10.0}
    E = json.loads((R/'phase2_eps_b.json').read_text())
    lean = next(a for a in E['architectures'] if a['name'].startswith('C-lean'))
    non_shield = [sum(v for k, v in lean['unit'][i]['parts_kg'].items() if k != 'shield')/1e3 for i in B]
    g1_shield = [G['bands'][b]['shadow_kg']/1e3+G['bands'][b]['slab_kg']/1e3 for b in BANDS]
    L2 = [4*(non_shield[i]+g1_shield[i]) for i in B]
    l3 = (9.0, 12.0, 16.0)
    buf_t = (9.3, 14.0, 19.1)         # power- and energy-sized for a 10 s engagement: high-power Li cells, from buffer()
    inst = [
        dict(item='L2 ship-service generation: 4 x 1.75 MWe fission-Brayton, EPS-G1 shields (rho V)', line='PROPOSED.ship_service_generation', t=L2, cls='STUDY'),
        dict(item='L1 burn generation (working doctrine, OPEN hot-loop pumps nominal 40 MW)', line='PROPOSED.burn_generation', t=[x*45/111.3 for x in [m/1e3 for m in E['L1']['mass_kg']]], cls='STUDY'),
        dict(item='L1 conversion reject radiator ~900 K (new, research variant)', line='PROPOSED.power_thermal_machinery', t=[q_area(45e6*(1/0.3-1), 900.0)*k/1e3/2 for k in (6, 10, 15)], cls='STUDY'),
        dict(item='Burn heat pumps: backup only under DR-01 (7 MW)', line='PROPOSED.power_thermal_machinery', t=[7e3*k/1e3 for k in (0.5, 1.5, 5.0)], cls='STUDY'),
        dict(item='Engagement thermal buffer (1 GJ PCM)', line='PROPOSED.power_thermal_machinery', t=[3.0, 4.0, 6.0], cls='STUDY'),
        dict(item='L3 survival source (30 d crew + nav)', line='power_computers_steering_comms', t=list(l3), cls='STUDY'),
        dict(item='Defense buffer, power-sized (~21 MW)', line='power_computers_steering_comms', t=list(buf_t), cls='STUDY'),
        dict(item='Cryocoolers (TMS-07): already in the registry, radiators_thermal', line='radiators_thermal', t=[0.0, 0.0, 0.0], cls='MODEL-DERIVED',
             note='Phase II added 3/6/12 t a second time; the registry row already carries it'),
        dict(item='Distribution: buses A/B/E trunks and switchgear for ~10 MW', line='PROPOSED.ship_service_generation', t=[4.0, 8.0, 15.0], cls='PROTOTYPE'),
    ]
    by = {}
    for r in inst:
        by.setdefault(r['line'], [0.0, 0.0, 0.0])
        for j in B: by[r['line']][j] += r['t'][j]
    inc = []
    for line, t in by.items():
        if line == 'power_computers_steering_comms':
            com = [reg_by.get(line, [0, 0, 0])[j]+pcsc_other[j] for j in B]
            head = [50.0-com[j] for j in B]
            inc.append(dict(line=line, allocation_t=50.0, committed_t=com, new_t=t, increment_t=[max(0.0, t[j]-head[j]) for j in B],
                            headroom_after_t=[head[j]-t[j] for j in B]))
        elif line.startswith('PROPOSED'):
            inc.append(dict(line=line, allocation_t=0.0, committed_t=[0, 0, 0], new_t=t, increment_t=t, headroom_after_t=[-x for x in t]))
        else:
            inc.append(dict(line=line, allocation_t=None, committed_t=reg_by.get(line, [0, 0, 0]), new_t=t, increment_t=[0, 0, 0], headroom_after_t=None))
    inc_tot = [sum(r['increment_t'][j] for r in inc) for j in B]
    life = tomllib.loads((ROOT/'data/life_support.toml').read_text())
    dep = []
    for months in (12, 24, 36):
        p = msn.provisioning(12, months*30.44, 'mixed', life=life)
        rcs = (9.3, 10.6, 16.1)
        dep.append(dict(mission=f'12 crew, {months} months', crew_consumables_t=p['crew_consumables_kg']/1e3, spares_t=p['items_kg']['spares']/1e3,
                        total_t=p['total_kg']/1e3, beyond_10t_line_t=p['total_kg']/1e3-10.0, rcs_propellant_t=list(rcs), containers=p['containers'],
                        volume_m3=p['volume_m3']))
    return dict(installed=inst, by_line=by, increment=inc, increment_total_t=inc_tot, departure=dep, reconciliation=[
        'Cryocoolers were counted twice in Phase II (registry radiators_thermal row and a new 3/6/12 t line): removed.',
        'L3 (12 t) and the defense buffer sit in the 50 t power/computers/steering/comms line; with the power-sized buffer they exceed its '
        f'{50-(reg_by.get("power_computers_steering_comms",[0,0,0])[1]+pcsc_other[1]):.1f} t nominal headroom by the amount shown, so only the excess is an increment.',
        'The defense buffer was labelled "D-variant only" but carried in the C-lean ledger; it is now one power-sized line counted once.',
        'Provisions: a 12-month load for 12 is ~20 t at departure (crew consumables plus 4 t spares); Phase II added only the crew consumables beyond '
        'the 10 t line (4.1 t). Departure loading is now its own ledger and is not dry mass.',
        'Phase II shield masses (1.6 t/m3, 2.8 m3) replaced by EPS-G1 envelopes (1.9 t/m3, volume x density).'])


# ------------------------------------------------------------------ III-B 4.1 thermal architectures --------------------------------
def thermal_archs(pl):
    warm_use = cap(WARM['area'], WARM['T'])/MARGIN
    base_burn = st(pl, 'HIGH_THRUST_PROACTIVE'); warm_burn = heat(pl, 'HIGH_THRUST_PROACTIVE', 'WARM')
    cont_burn = st(pl, 'HIGH_THRUST'); warm_cont = [17.7e6*k for k in (0.67, 1.0, 1.35)]   # continuous-active consumer heat at 440 K (TRIGGERED WARM)
    warm_cont = heat(pl, 'COAST_HV_TRIGGERED', 'WARM')
    eta2 = eps_b.brayton_eff(550.0, 1); pcs = (6.0, 10.0, 15.0)    # kg per m2 of panel (two faces) incl. channels
    hp_kg_kW = (0.5, 1.5, 5.0); l1_kg_kWe = (1.5, 3.0, 5.0)
    hot_per_m = cap(FACE_PER_M, HOT_T)
    def l1_mass(Pe, i):  # thermal conversion incl. its 900 K radiator panel
        waste = Pe*(1/0.30-1); return Pe/1e3*l1_kg_kWe[i]/1e3+q_area(waste, 900.0)/2*pcs[i]/1e3, waste
    out = []
    for doc, need_warm, gen_burn in (('DR-01 working', warm_burn, base_burn), ('continuous active bound', warm_cont, cont_burn)):
        for key, name in (('A', 'Existing graded blade + heat pumps'), ('B', 'Independent warm radiator, burns and coast'),
                          ('C', 'Expanded warm/intermediate section (550 K) in the RAD-ZONE'), ('D', 'Two circuits inside the existing WARM blades (440/550 K)'),
                          ('E', 'Thermal storage'), ('F', 'Hybrid: DR-01 + small 550 K section + engagement buffer')):
            r = dict(doctrine=doc, key=key, name=name)
            n = 1
            over = max(0.0, need_warm[n]-warm_use)
            l2_waste = gen_burn[n]*(1/eta2-1)
            hotloop = 40e6
            if key == 'A':
                lift = over; COP = 440/(600-440)*0.5          # lift to a 600 K reject point on the hot blade root (Phase II)
                pump = lift/COP if lift > 0 else 0.0
                l1 = gen_burn[n]+pump+(hotloop if doc.startswith('DR') else 0.0)
                m_l1, w1 = l1_mass(l1, n)
                r.update(pump_work_W=pump, L1_W=l1, L1_waste_W=w1, added_area_m2=q_area(w1, 900.0), transport_t=0.02*pump/1e3, structure_t=0.0,
                         added_t=m_l1+pump/1e3*hp_kg_kW[n]/1e3, interference='heat-pump rejection at the hot blade root; 900 K L1 panel is new',
                         shield='none', transitions='burn-to-coast gap remains (L2 has no sink in burns)', L2_in_burn=False)
            elif key == 'B':
                Q = need_warm[n]+l2_waste; area = q_area(Q*MARGIN, 440.0)
                l1 = gen_burn[n]*0.1+(hotloop if doc.startswith('DR') else 0.0)
                m_l1, w1 = l1_mass(l1, n)
                r.update(pump_work_W=0.0, L1_W=l1, L1_waste_W=w1, added_area_m2=area+q_area(w1, 900.0), transport_t=area*0.5/1e3, structure_t=area/2*4/1e3,
                         added_t=area/2*pcs[n]/1e3+area/2*4/1e3+m_l1, interference='a new radiator outside the RAD-ZONE: sight lines to the hot blades (view '
                         'factor) and the dust shadow; research variant only', shield='blade scatter from a new surface', transitions='L2 runs through burns: no gap',
                         L2_in_burn=True)
            elif key == 'C':
                Q = l2_waste; area = q_area(Q*MARGIN, 550.0); L = area/FACE_PER_M
                l1 = (hotloop if doc.startswith('DR') else 0.0)+0.6e6+(cont_burn[n]-base_burn[n] if not doc.startswith('DR') else 0.0)
                m_l1, w1 = l1_mass(l1, n)
                r.update(pump_work_W=max(0.0, over)/(440/(600-440)*0.5), L1_W=l1, L1_waste_W=w1, added_area_m2=area+q_area(w1, 900.0), length_m=L,
                         hot_allowance_used_W=L*hot_per_m if True else 0.0, transport_t=area*0.3/1e3, structure_t=0.0,
                         added_t=area/2*pcs[n]/1e3*0.5+area*0.3/1e3+m_l1, interference=f'~{L:.0f} m taken from the hot blade forward end, costs '
                         f'{L*hot_per_m/1e9:.1f} of the 3.6 GW hot allowance; graded bulkhead moves', shield='none new', transitions='L2 runs through burns: no gap',
                         L2_in_burn=True)
            elif key == 'D':
                f550 = 10.5/22.5; cap440 = warm_use*(1-f550); cap550 = cap(WARM['area']*f550, 550.0)/MARGIN
                units = int(cap550/(1.75e6*(1/eta2-1)))
                l1 = gen_burn[n]-units*1.75e6+(hotloop if doc.startswith('DR') else 0.0)
                m_l1, w1 = l1_mass(max(l1, 0.0), n)
                r.update(pump_work_W=max(0.0, need_warm[n]-cap440)/(440/(600-440)*0.5), L1_W=l1, L1_waste_W=w1, added_area_m2=q_area(w1, 900.0),
                         transport_t=3.0, structure_t=0.0, added_t=m_l1+3.0+max(0.0, need_warm[n]-cap440)/(440/(600-440)*0.5)/1e3*hp_kg_kW[n]/1e3,
                         interference='none outside the blades; the 440 K part shrinks to '+f'{cap440/1e6:.1f} MW usable', shield='none new',
                         transitions=f'{units} L2 unit(s) keep running in burns ({units*1.75:.2f} MWe)', L2_in_burn=units > 0, warm440_usable_W=cap440,
                         warm550_usable_W=cap550, closes_warm=need_warm[n] <= cap440)
            elif key == 'E':
                whole = (need_warm[n]+l2_waste)*10*DAY; pcm = 300e3
                r.update(pump_work_W=0.0, L1_W=gen_burn[n], L1_waste_W=None, added_area_m2=0.0, transport_t=0.0, structure_t=0.0,
                         added_t=whole/pcm/1e3, interference='none', shield='none', transitions='buffer must be rejected in coast',
                         L2_in_burn=False, note=f'whole 10-day burn: {whole/1e12:.0f} TJ = {whole/pcm/1e6:.0f} kt of PCM (infeasible); one engagement '
                         '(~1 GJ): 3-5 t (viable)')
            else:
                Q = l2_waste*0.4; area = q_area(Q*MARGIN, 550.0); L = area/FACE_PER_M
                l1 = hotloop*(1 if doc.startswith('DR') else 1)+0.6e6+(cont_burn[n]-base_burn[n] if not doc.startswith('DR') else 0.0)-0.0
                m_l1, w1 = l1_mass(l1, n)
                r.update(pump_work_W=0.0 if doc.startswith('DR') else max(0.0, over)/(440/(600-440)*0.5), L1_W=l1, L1_waste_W=w1,
                         added_area_m2=area+q_area(w1, 900.0), length_m=L, hot_allowance_used_W=L*hot_per_m, transport_t=area*0.3/1e3, structure_t=0.0,
                         added_t=area/2*pcs[n]/1e3*0.5+area*0.3/1e3+m_l1+4.0, interference=f'~{L:.0f} m of the hot blade at 550 K for two units (3.5 MWe)',
                         shield='none new', transitions='two L2 units run through burns; ship base load on L2, L1 only drive-specific', L2_in_burn=True)
            out.append(r)
    return dict(rows=out, warm_usable_W=warm_use, hot_W_per_m=hot_per_m,
                finding=('Under the working doctrine the burn heat pumps vanish in every architecture (WARM 3.6 MW fits 6.0 MW usable). What remains is '
                         'L1\'s own 900 K rejection and L2\'s missing sink in burns. C and F give L2 a 550 K sink by taking ~23-37 m from the forward end of '
                         'the hot blades (2.1-3.3 GW of the 3.6 GW hot allowance, to be confirmed against the drive\'s hot budget): L2 then runs through burns and the burn-to-coast gap disappears. D does the same '
                         'inside today\'s WARM blades for one unit but leaves the 440 K part too small at the high band. Thermal storage only works per '
                         'engagement.'))


def section550(units_running, Pe=1.75e6):
    """A 550 K section carved from the forward end of the hot blades for L2 in burns (thermal option C/F): area, length, mass, hot allowance."""
    out = dict(units=units_running, area_m2=[], length_m=[], mass_t=[], hot_allowance_W=[])
    for i in B:
        Q = units_running*Pe*(1/eps_b.brayton_eff(550.0, i)-1); a = q_area(Q*MARGIN, 550.0); L = a/FACE_PER_M
        out['area_m2'].append(a); out['length_m'].append(L); out['hot_allowance_W'].append(L*cap(FACE_PER_M, HOT_T))
        out['mass_t'].append(a*(0.3, 0.5, 0.8)[i]/1e3+(2.0, 4.0, 8.0)[i])     # 550 K channels + headers on the existing blade structure, plus a graded joint
    return out


# ------------------------------------------------------------------ III-B 4.2 L1 ----------------------------------------------------
def l1_options(pl):
    base = st(pl, 'HIGH_THRUST_PROACTIVE'); cont = st(pl, 'HIGH_THRUST')
    demand = {
        'continuous active (Phase II)': [cont[i]+(10e6, 40e6, 100e6)[i] for i in B],
        'DR-01, pumped hot loop (OPEN 10-100 MW)': [base[i]+(10e6, 40e6, 100e6)[i] for i in B],
        'DR-01, heat-pipe hot blades (no hot-loop pumps)': [base[i]+(0.1e6, 0.5e6, 2e6)[i] for i in B],
        'DR-01 + L2 carries the ship in burns (C/F)': [(0.1e6, 0.5e6, 2e6)[i]+(0.02e6, 0.1e6, 0.4e6)[i] for i in B],
    }
    conv = {
        'thermal (Brayton from the 1800 K hot loop, reject ~900 K)': dict(eta=0.30, kg_kWe=(1.5, 3.0, 5.0), T_rej=900.0, cls='STUDY',
                                                                         note='needs its own 900 K panel; uses hot-loop heat the drive already rejects'),
        'inductive (pickup coils on the pulsed nozzle field)': dict(eta=0.60, kg_kWe=(0.5, 1.5, 4.0), T_rej=450.0, cls='SPECULATIVE',
                                                                    note='interface only: energy tapped from the expanding plasma reduces thrust; losses at coil temperature'),
        'direct (charged-particle collectors in the exhaust)': dict(eta=0.70, kg_kWe=(1.0, 3.0, 8.0), T_rej=700.0, cls='SPECULATIVE',
                                                                    note='TRL 2-3; collector erosion and the jet-power debit belong to Vertex (not reopened)'),
    }
    rows = []
    for dn, d in demand.items():
        for cn, c in conv.items():
            for i in B:
                Pe = d[i]; waste = Pe*(1/c['eta']-1); area = q_area(waste, c['T_rej'])
                m = Pe/1e3*c['kg_kWe'][i]/1e3+area/2*(6, 10, 15)[i]/1e3
                rows.append(dict(demand=dn, conversion=cn, band=BANDS[i], Pe_W=Pe, waste_W=waste, area_m2=area, mass_t=m, cls=c['cls']))
    return dict(demand_W=demand, conversion=conv, rows=rows,
                finding=('Reduce demand first: the working doctrine takes L1 from ~150 MW to ~45 MW nominal, and the OPEN hot-loop pumps are 90 % of '
                         'what is left. Heat-pipe hot blades (a propulsion-interface choice) take L1 to ~5 MW; if L2 also carries the ship in burns '
                         '(thermal options C/F) L1 shrinks to ~0.6 MW of drive-specific loads. Thermal conversion from the hot loop is the only '
                         'non-speculative option; inductive and direct conversion stay SPECULATIVE and are not credited.'))


# ------------------------------------------------------------------ III-B 4.3 L2 ----------------------------------------------------
def l2_options(pl, G, mc):
    pro = st(pl, 'COAST_HV_PROACTIVE'); E = json.loads((R/'phase2_eps_b.json').read_text())
    rows = []
    for name, n, Pe, strat in (('2 x 100 % (5.3 MWe)', 2, 5.3e6, 'one running, one warm standby'),
                               ('2+1 x 2.66 MWe', 3, 2.66e6, 'two sharing, one warm standby'),
                               ('C-lean 3+1 x 1.75 MWe', 4, 1.75e6, 'three sharing, one warm standby'),
                               ('C-lean all four partial', 4, 1.75e6, 'all four at ~75 %, no standby (faster response, more wear)'),
                               ('4+1 x 1.33 MWe', 5, 1.33e6, 'four sharing, one warm standby'),
                               ('C-lean 3+1 + essential-only redundancy', 4, 1.75e6, 'N+1 only for essentials (0.45 MW): proactive defense sheds on a trip'),
                               ('Aux fusion 2 x 60 % (SPECULATIVE)', 2, 3.2e6, 'speculative, not credited')):
        m = []
        for i in B:
            p = eps_b.fission_plant(Pe, 550.0, 80.0, i, 2.69e4, EPS)
            ns = sum(v for k, v in p['parts_kg'].items() if k != 'shield')
            U = __import__('eps_g1').unit(Pe_W=Pe, eta=p['eta'], n_running=max(1, n-1), i=i)
            m.append(n*(ns+U['shadow_kg']+U['slab_kg'])/1e3)
        if 'fusion' in name:
            m = [n*eps_b.fusion_plant(Pe, i, 2.69e4, EPS)['mass_kg']/1e3 for i in B]
        run = n-1 if 'standby' in strat else n
        surplus = [run*Pe-pro[i] for i in B]
        plan = E['demand']['planning_open_W']
        rows.append(dict(name=name, units=n, unit_W=Pe, strategy=strat, mass_t=m, surplus_W=surplus,
                         surplus_with_planning_EOL_W=[run*Pe*(0.95, 0.9, 0.85)[i]-pro[i]-plan[i] for i in B],
                         after_one_loss_W=[(n-1)*Pe-pro[i] for i in B]))
    return dict(rows=rows, mc=mc, finding=('At end of life a 1.75 MWe unit gives ~1.58 MW, so C-lean needs three of four units for proactive defense: '
                                           'it is N+1 with no margin and the most likely to fall short (18 % over 3 years at u = 0.05 with repair, 3 % '
                                           'lasting). Fewer, larger units with one unit per blade do better (2+1 x 2.66: 9 % / 2 %; 2 x 100 %: 5 % / 1 %; '
                                           '4+1 x 1.33: 9 % / 1.5 %), at masses within 15 % (233-266 t nominal) because every unit carries its own shield. '
                                           'Moving C-lean unit 4 to another blade does not help: four units on three blades always share a header. '
                                           'Without ORU repair the lasting-shortfall probability rises about fivefold. Every option has ~0 surplus at EOL '
                                           'once the OPEN planning loads arrive: running capacity should be ~6 MWe, not 5.3. Service life (20 years) is '
                                           'not an unserviced mission: units are swapped between missions.'))


# ------------------------------------------------------------------ III-B 4.4 nuclear district -------------------------------------
def district_options(G):
    U = G['reference_unit']
    per = (U['shadow_kg']+U['slab_kg'])/1e3
    return dict(rows=[
        dict(option='Individual shields in M1-M2 (EPS-G1)', shield_t=4*per, notes='each unit its own shadow + blade slab; fits a 3.2 m bay; '
             'outer-ring He-3 tanks outside the cone (OPEN)', fits=True),
        dict(option='Clustered district wall (one shared shadow wall at M2 forward end, r 1.5-5.6)', shield_t=math.pi*(5.6**2-1.5**2)*U['shadow_t_m']*1.9,
             notes='one wall shadows all units and the tanks if extended to the casing; lanes and feed lines must pass through it', fits=True),
        dict(option='District sleeve (full 4 pi around M1-M2)', shield_t=1000.0, notes='~1 kt: not credible', fits=False),
        dict(option='Separated boom modules (units on a 30 m aft boom)', shield_t=4*per*0.6, notes='distance buys ~3 e-folds but the boom crosses '
             'the drive hot section and the plume envelope: rejected for the aft; possible forward of the Brow (crew side, rejected)', fits=False),
        dict(option='Alternative aft location: drive service bay (x -100)', shield_t=4*per, notes='closer to L1 and the hot loop; sits inside the '
             'drive district and its maintenance envelope: conflicts with DRIVE_AFT', fits=False)],
        finding=('Individual shields stay lightest and fit. A shared shadow wall across the M2 forward face is the only option that also shades the '
                 'tank farm and the keel-lane traffic; it weighs about as much as four slabs and turns M1-M2 into a closed district with '
                 'controlled penetrations. Recommended research direction: individual shields + a partial tank-facing wall, pending transport.'))


# ------------------------------------------------------------------ III-B 4.5 burn-to-coast transition -----------------------------
def transition(pl):
    pro = st(pl, 'COAST_HV_PROACTIVE'); bat = pl['storage']
    steps = [
        ('t = 0', 'Drive trip at high velocity in a burn', 'L1 lost; hot blades at 1800 K; warm channels drained; L2 off (no sink)'),
        ('0-80 s', 'Hot blades radiate down to ~600 K (2 mm C/C sheet)', 'decay heat ~0.5-1 % of hot-loop heat must keep circulating: hot-loop pumps on battery?'),
        ('0-0.2 h', 'Battery ride-through (energy bound 0.16 h, power-limited to ~2 MW)', 'proactive defense (2.5 MW) cannot be carried at 1C: protection lost'),
        ('0.1-4 h', 'Channel refill and re-prime (OPEN 0.5-4 h)', 'L2 waits for a sink'),
        ('+0.5-2 h', 'L2 restart (warm start) on the refilled channels', 'proactive defense back once 2 units run'),
    ]
    gap_h = (0.3, 1.5, 3.8)
    flux_per_h = (1e-3, 1e-2, 1e-1)    # probability of a damaging dust strike per hour unprotected at 0.016 c (OPEN; lab dust study)
    risk = [1-math.exp(-gap_h[i]*flux_per_h[i]) for i in B]
    return dict(steps=steps, gap_h=gap_h, strike_probability=risk, with_C_or_F='with a 550 K section L2 never stops: the gap closes to the '
                'L1-only loads (drive standby), and proactive defense continues on L2',
                finding=('A drive trip at velocity leaves the ship without proactive defense for ~0.3-4 h, set by the OPEN channel refill. That is not '
                         'SAFE even though the refuge carries the crew: it is a mission and hull risk proportional to dust flux x gap. Options C/F '
                         '(or D for one unit) remove it.'))


# ------------------------------------------------------------------ III-D missions --------------------------------------------------
def missions(s, pl):
    m = op.mission(s); burns = []
    for k, m0 in enumerate(m['burn_masses_kg'][:-1]):
        b = op.burn(s, profile='power_limited', m0=m0)
        burns.append(dict(burn=k+1, m0_t=m0/1e3, duration_d=b['duration_d'], distance_AU=b['distance_AU'], accel_g=b['accel_g'], dv=b['delta_v_m_s']))
    ramp = op.burn(s, profile='ramp')
    ve = op.p(s)['exhaust_velocity_m_s']; f = s['physics']['fuel_loads']['tank_dry_fraction']
    end0 = op.p(s)['protected_and_operational_kg']; p0 = op.p(s)['legacy_inventory_kg']; F = op.power_cap_N(s)
    def mission_at(v, dM=0.0, n=4):
        Rr = math.exp(v/ve); P = (Rr**n-1)*(end0+dM-f*p0)/(1-(Rr**n-1)*f); end = end0+dM+f*(P-p0); m0 = end+P
        ms = [m0/Rr**i for i in range(n+1)]
        T = sum((a-b)*ve/F for a, b in zip(ms, ms[1:]))
        dist = 0.0
        for a, b in zip(ms, ms[1:]):          # distance per burn at constant thrust
            Tb = (a-b)*ve/F; mdot = F/ve; N = 200
            for j in range(N):
                t = Tb*(j+.5)/N; dist += ve*math.log(a/(a-mdot*t))*Tb/N
        return dict(v=v, propellant_t=P/1e3, departure_t=m0/1e3, burn_days=T/DAY, burn_AU=dist/AU)
    def_item = next(x for x in pl['items'].values() if x.get('id', '') == 'PROT.DEF_PROACTIVE') if isinstance(pl['items'], dict) and False else None
    P_def = 2.5e6
    speeds = (0.004, 0.008, 0.012, 0.016)
    trade = []
    for D in (45.0, 120.0, 200.0, 500.0, 1000.0):
        for vf in speeds:
            mm = mission_at(vf*C)
            cruise = max(0.0, 2*D*AU-mm['burn_AU']*AU)/(vf*C)       # round trip: four burns cover burn_AU in total
            tot = cruise/DAY+mm['burn_days']+30
            pdef = P_def*(vf/0.016)**3
            life = tomllib.loads((ROOT/'data/life_support.toml').read_text())
            prov = msn.provisioning(12, tot, 'mixed', life=life)['total_kg']/1e3
            trade.append(dict(D_AU=D, v_c=vf, round_trip_d=tot, round_trip_months=tot/30.44, propellant_t=mm['propellant_t'], departure_t=mm['departure_t'],
                              defense_W=pdef, coast_L2_W=st(pl, 'COAST_HV_PROACTIVE')[1]-P_def+pdef, consumables_t=prov,
                              dust_fluence_rel=(vf/0.016)**3*cruise/YR, P_unit_loss2=1-sum(math.comb(4, j)*(math.exp(-0.05*tot/365.25))**j*(1-math.exp(-0.05*tot/365.25))**(4-j) for j in (3, 4))))
    m12 = mission_at(0.016*C)
    return dict(burns=burns, ramp_reference=dict(duration_d=ramp['duration_d'], distance_AU=ramp['distance_AU']),
                correction=('Phase II used the 7.55 d / 6.97 AU ramp; the flown profile is power-limited: the first burn takes '
                            f'{burns[0]["duration_d"]:.2f} d over {burns[0]["distance_AU"]:.2f} AU, later burns are shorter as the ship lightens.'),
                speed_trade=trade, design_point=m12, mission_at=None,
                coupled_dP_dM=(math.exp(4*0.016*C/ve)-1)/(1-(math.exp(4*0.016*C/ve)-1)*f),
                finding=('0.016 c is a capability. Inside ~200 AU a 0.008 c cruise costs months, not years, and saves ~60 % of the propellant, an '
                         '8x lower defense load and an 8x lower dust fluence per year. Beyond ~500 AU only 0.012-0.016 c keeps round trips inside 36 months.'))


def logistics(life):
    cats = [  # category, share of a 12-month load by mass, density t/m3 as packed, max gross t/container, handling, access
        ('FOOD_SHELF', 'Food, shelf-stable', 'food', 0.55, 'manual + drone', 'weekly'),
        ('FOOD_FROZEN', 'Food, frozen (LOW cold loop)', None, 0.45, 'manual', 'weekly; needs 1-3 kW per container on LOW'),
        ('WATER_O2', 'Water makeup and O2 water (bladders)', 'water', 1.0, 'manual pump-transfer', 'monthly'),
        ('ECLSS_EXP', 'ECLSS expendables (filters, sorbent, cartridges)', 'eclss', 0.25, 'manual', 'monthly'),
        ('MEDICAL', 'Medical stock (controlled temperature)', 'medical', 0.25, 'manual', 'on demand'),
        ('HYGIENE', 'Hygiene and clothing', 'hygiene', 0.25, 'manual', 'monthly'),
        ('SPARES_ORU', 'Spares and ORUs (robotic interface)', 'spares', 0.40, 'drone + keel-lane manipulator', 'on demand'),
        ('RESERVE', '30-day survival reserve (refuge-adjacent)', 'reserve', 0.70, 'manual, never drawn', 'never'),
        ('HAZMAT', 'Hazardous (batteries, propellant samples, chemicals)', None, 0.5, 'robotic only, separated', 'rare'),
        ('GARDEN', 'Garden inputs (nutrients, seeds, media)', None, 0.4, 'manual', 'monthly'),
    ]
    vol = 44.8; gross = (4.0, 6.0, 8.0)
    rows = []
    for months in (12, 24, 36):
        p = msn.provisioning(12, months*30.44, 'mixed', life=life)
        it = p['items_kg']; mapping = dict(food=it['food'], water=it['water_makeup']+it['o2_water'], eclss=it['eclss_expendables'],
                                             medical=it['medical'], hygiene=it['hygiene_clothing'], spares=it['spares'], reserve=it['reserve'])
        crow = []
        for cid, nm, key, rho, hand, acc in cats:
            kg = mapping.get(key, 0.0) if key else (0.2*it['food'] if cid == 'FOOD_FROZEN' else (0.5e3*months/12 if cid == 'GARDEN' else 0.3e3))
            if cid == 'FOOD_SHELF': kg *= 0.8
            n_mass = kg/1e3/gross[1]; n_vol = kg/1e3/rho/(vol*0.7)
            crow.append(dict(category=cid, name=nm, kg=kg, containers=max(1, math.ceil(max(n_mass, n_vol))) if kg > 0 else 0, set_by='mass' if n_mass > n_vol else 'volume',
                             handling=hand, access=acc))
        rows.append(dict(mission=f'12 crew, {months} months', categories=crow, containers=sum(c['containers'] for c in crow), total_t=sum(c['kg'] for c in crow)/1e3))
    return dict(container=dict(size_m=(5.0, 2.8, 3.2), volume_m3=vol, gross_t=gross, restraint='four-point twist-lock to the module frame + two '
                'tie-down straps; rated 1.5 g axial, 0.3 g lateral (PROTOTYPE)', load_path='container -> rack rails -> module ring frames -> keel girders',
                axial_kN_at_6t=6e3*1.5*G0/1e3, transfer='keel-lane trolley to the forward lock; robotic capture interface on two faces',
                count_total=54), rows=rows)


def eclss_options():
    t_per_person = (0.9, 1.2, 1.6); kW_per_person = (0.9, 1.2, 1.6)
    base = 2*6  # two strings x 6-person capacity (one per ring)
    opts = [
        ('Surge: each string rated for 12 (2 x 12)', 24, 'one ring hosts 12 indefinitely; heaviest, simplest'),
        ('Third string (2 x 6 + 1 x 6 cross-ring spare in the hub)', 18, 'spare string can serve either ring via spoke ducts'),
        ('Modular 4-person units (5 x 4)', 20, 'units move between rings; 8 units would carry 12 in one ring with 4+4+4 and spares'),
        ('Refuge equipment only (2 x 6 + 30-day LiOH/O2 candles for 6)', 12, 'one ring carries 12 for 30 days on consumables; then degraded'),
        ('Cross-ring sharing (2 x 6 + air/water ducts through the spokes)', 12, 'needs the other ring\'s string alive; covers a habitat loss, not a string loss'),
    ]
    rows = []
    for nm, cap_p, note in opts:
        rows.append(dict(option=nm, capacity_persons=cap_p, added_t=[max(0, cap_p-base)*k for k in t_per_person],
                         added_kW=[max(0, cap_p-base)*k*0.3 for k in kW_per_person], note=note))
    rows[3]['added_t'] = [12*30*k/1e3 for k in (1.0, 1.5, 2.0)]
    return dict(rows=rows, recommendation='modular 4-person units: 12 people in one ring after a string or ring loss with a 2-3 t premium, and the units '
                'are mission-swappable logistics items')


def narrative(life, mc_lean):
    load36 = msn.provisioning(12, 36*30.44, 'mixed', life=life)['crew_consumables_kg']
    rows = []
    for nm, kw in (('nominal (100 % rations, 98 % recovery)', dict()), ('80 % rations, 99 % recovery', dict(ration=0.8, recovery=0.99)),
                   ('water recovery degrades to 95 %', dict(recovery=0.95)), ('spoilage 3 %/yr (applied as load loss)', dict()),
                   ('one ECLSS string lost at year 3 (recovery 90 % after)', dict(recovery=0.94))):
        d = msn.endurance(6, load36*(0.91 if 'spoilage' in nm else 1.0), food='mixed', life=life, **kw)
        rows.append(dict(case=nm, years=d/365.25))
    return dict(load_t=load36/1e3, rows=rows, l2=mc_lean, note='Six people on a 36-month load for twelve: endurance, not a design requirement (owner '
                '2026-11-27). Power reliability over 6 years without unit swap is the limiting item, not food.')


# ------------------------------------------------------------------ III-E convergence ---------------------------------------------
def convergence(s, pl, L, TA, L1o, L2o, mc, G, M):
    end0 = op.p(s)['protected_and_operational_kg']; f = s['physics']['fuel_loads']['tank_dry_fraction']; p0 = op.p(s)['legacy_inventory_kg']
    ve = op.p(s)['exhaust_velocity_m_s']; Rn = op.mission(s)['mass_ratio_per_burn']**4; F = op.power_cap_N(s)
    base = op.mission(s)
    def coupled(dM_t):
        dM = dM_t*1e3; P = (Rn-1)*(end0+dM-f*p0)/(1-(Rn-1)*f); end = end0+dM+f*(P-p0); m0 = end+P
        return dict(propellant_t=P/1e3, tankage_t=f*(P-p0)/1e3, departure_t=m0/1e3, first_burn_d=(m0-m0/op.mission(s)['mass_ratio_per_burn'])*ve/F/DAY,
                    accel_g=[F/m0/G0, F/(m0/op.mission(s)['mass_ratio_per_burn'])/G0])
    dry = mass_model.report(s)['dry_ship']; dcg = dry['cg_m'][0]; dm = dry['mass_kg']/1e3
    cand = []
    def add(name, items, cls, open_, redund, notes):
        tot = [sum(v[j] for v in items.values()) for j in B]
        xs = dict(L1=-100.0, L2=-78.0, L3=113.0, thermal=-40.0, shield=-80.0, storage=110.0, distribution=0.0, radiator_structure=40.0, cargo=100.0)
        mx = sum(items[k][1]*xs.get(k, 0.0) for k in items)
        c = [coupled(t) for t in tot]
        cand.append(dict(name=name, items_t=items, dry_added_t=tot, cls=cls, coupled=c,
                         extra_propellant_t=[x['propellant_t']-base['propellant_kg']/1e3 for x in c],
                         extra_departure_t=[x['departure_t']-base['departure_mass_kg']/1e3 for x in c],
                         cg_x_m=(dcg*dm+mx)/(dm+tot[1]), redundancy=redund, open=open_, notes=notes))
    lean = L2o['rows'][2]['mass_t']
    zero = [0.0, 0.0, 0.0]
    add('Baseline (today\'s lines, no ISSA additions)', dict(L1=zero, L2=zero, L3=zero, thermal=zero, shield=zero, storage=zero, distribution=zero,
                                                            radiator_structure=zero, cargo=zero), 'MODEL-DERIVED',
        ['no L1/L2 generation exists in the model; proactive defense and cryo unpowered'], 'n/a', 'reference')
    E = json.loads((R/'phase2_eclss_mass.json').read_text())['mass']
    p2 = {r['item']: r['t'] for r in E['adds']}
    g = lambda k: next(v for n, v in p2.items() if n.startswith(k))
    add('Phase II as reported (corrected ledger categories)', dict(L1=g('L1'), L2=g('L2'), L3=g('L3'), thermal=g('Burn heat pumps'), shield=zero,
                                                                    storage=g('Defense'), distribution=zero, radiator_structure=zero,
                                                                    cargo=[x+10.0*0 for x in g('Standard')]), 'STUDY',
        ['continuous-active burn bound', 'heat pumps 123 t', 'shield 1.6 t/m3', 'cryocoolers double counted (removed here)'], 'C-lean 3+1', 'Phase II reference')
    rowA = next(r for r in TA['rows'] if r['doctrine'].startswith('DR') and r['key'] == 'A')
    rowF = next(r for r in TA['rows'] if r['doctrine'].startswith('DR') and r['key'] == 'F')
    l1_pumped = [r['mass_t'] for r in L1o['rows'] if r['demand'].startswith('DR-01, pumped') and r['conversion'].startswith('thermal')]
    l1_hp = [r['mass_t'] for r in L1o['rows'] if r['demand'].startswith('DR-01, heat-pipe') and r['conversion'].startswith('thermal')]
    l1_min = [r['mass_t'] for r in L1o['rows'] if r['demand'].startswith('DR-01 + L2') and r['conversion'].startswith('thermal')]
    dist = [4.0, 8.0, 15.0]; l3 = [9.0, 12.0, 16.0]; buf = [9.3+3.0, 14.0+4.0, 19.1+6.0]
    pc_head = [50-(L['increment'][0]['committed_t'][j] if L['increment'][0]['line'] == 'power_computers_steering_comms' else 31.3) for j in B]
    add('N1: working doctrine, existing radiators, pumped hot loop', dict(L1=l1_pumped, L2=lean, L3=l3, thermal=[3.5, 10.5, 35.0], shield=zero, storage=buf,
                                                                         distribution=dist, radiator_structure=zero, cargo=zero), 'STUDY',
        ['L1 900 K reject has no production radiator (new panel)', 'hot-loop pumps OPEN', 'L2 gap in burn-to-coast', 'He-3 tank shadow', 'transport BLOCKER'],
        'C-lean 3+1', 'production radiators unchanged; L2 shields inside L2 mass')
    S3 = section550(2, 2.66e6); two = L2o['rows'][1]['mass_t']
    add('N2: hybrid F with 2+1 x 2.66 MWe (DR-01, 550 K section, buffer, heat-pipe hot blades)', dict(L1=l1_min, L2=two, L3=l3,
                                                                                    thermal=[2.0, 4.0, 8.0], shield=zero, storage=buf, distribution=dist,
                                                                                    radiator_structure=S3['mass_t']), 'STUDY / PROTOTYPE',
        ['radiator research variant (DR-03): 550 K section', 'heat-pipe hot blades are a propulsion-interface change (OPEN)', 'He-3 tank shadow',
         'transport BLOCKER'], '2+1, one unit per blade, runs through burns', 'closes the burn-to-coast gap; smallest L1; recommended research direction')
    four = L2o['rows'][4]['mass_t']
    S4 = section550(4, 1.33e6)
    add('N3: hybrid F with 4+1 x 1.33 MWe', dict(L1=l1_min, L2=four, L3=l3, thermal=[2.0, 4.0, 8.0], shield=zero, storage=buf, distribution=dist,
                                                 radiator_structure=S4['mass_t']), 'STUDY / PROTOTYPE',
        ['as N2', 'five units, two per blade on two blades (shared headers)'], '4+1, keeps proactive defense after a loss at the high band', 'most robust')
    for c in cand:
        c['pcsc_headroom_t'] = pc_head
    return dict(candidates=cand, section550=dict(N2=S3, N3=S4), base=dict(propellant_t=base['propellant_kg']/1e3, departure_t=base['departure_mass_kg']/1e3,
                                          dry_t=dm, dry_cg_x_m=dcg), dP_dM=(Rn-1)/(1-(Rn-1)*f),
                note='Coupled: added dry mass raises the protected + operational end mass in operating_point.mission(); propellant and its tankage '
                     'follow from the closed form (not a fixed multiplier). The drive power is fixed, so the burns get longer and the acceleration falls.')


def problems():
    P = [
        ('P3-01', 'BLOCKER', 'No validated radiation transport (MCNP/OpenMC + nuclear data): every shield mass is a simplified estimate', 'shielding OPEN; crew safety not established'),
        ('P3-02', 'BLOCKER', 'L1 conversion waste (~900 K) has no radiator in the production geometry', 'L1 does not close thermally'),
        ('P3-03', 'BLOCKER', 'LOW section fails at the high band and after any blade-circuit loss', 'no state closes at every band'),
        ('P3-04', 'MAJOR', 'L2 has no sink in burns or during channel refill: 0.3-4 h protection gap after a drive trip at velocity', 'not SAFE'),
        ('P3-05', 'MAJOR', 'Outer-ring He-3 tanks sit outside the district shadow cone; unshielded deposit exceeds the 3 K stage lift', 'cryo preservation'),
        ('P3-06', 'MAJOR', 'Hot-loop pumps (OPEN 10-100 MW) dominate L1', 'L1 mass and its 900 K rejection'),
        ('P3-07', 'MAJOR', 'Battery ride-through is discharge-power-limited (1C = 2 MW < 3.4 MW coast)', 'ride-through hours overstated'),
        ('P3-08', 'MAJOR', 'Defense buffer is power-sized (~21 MW), not energy-sized', 'buffer 3.5-14 t, not 2.4 t'),
        ('P3-09', 'MAJOR', 'C-lean surplus is negative at the high band and after one unit trip', 'triggered active not sustainable there'),
        ('P3-10', 'MAJOR', 'Coupled propellant growth 2.31 t per dry tonne (3.66 t of departure mass)', 'every ISSA tonne costs ~3.7 t at departure'),
        ('P3-11', 'MINOR', 'Blade-sharing: in C-lean units 2 and 4 share blade 210 and its header', 'common mode in redundancy'),
        ('P3-12', 'MINOR', 'Registry double count of cryocoolers; buffer mislabelled; provisions partly counted', 'fixed in the Phase III ledgers'),
        ('P3-13', 'OPEN', 'Channel refill time, unit restart energy, Brayton degradation, engagement frequency', 'bands only'),
        ('P3-14', 'OPEN', 'Coolant riser and removal hatch penetrate the casing next to the district', 'pressure/thermal/streaming interface'),
    ]
    return [dict(id=a, severity=b, problem=c, consequence=d) for a, b, c, d in P]


def decisions():
    D = [
        ('DR3-01', 'Adopt R1 (L2-first restart, cryo paused in the sealed hold) as the black-start study basis; keep canon step 2 until decided', 'R1'),
        ('DR3-02', 'Size the defense buffer by discharge power (supercapacitors) and adopt a 10 s / 10 min engagement duty as the planning case', 'yes'),
        ('DR3-03', 'Open a radiator research variant for a 550 K section (thermal option F); production stays unchanged (DR-03)', 'F'),
        ('DR3-04', 'Ask propulsion for heat-pipe hot blades (removes the OPEN hot-loop pumps from L1)', 'ask'),
        ('DR3-05', 'Move the L2 study reference from C-lean 3+1 x 1.75 to 2+1 x 2.66-3.0 MWe (one unit per blade); keep 4+1 x 1.33 as the alternative', '2+1'),
        ('DR3-06', 'Commission a radiation-transport assessment before any shield or district decision', 'yes'),
        ('DR3-07', 'Treat the He-3 tank shadow as a district requirement (tank-facing wall or tank shields)', 'yes'),
        ('DR3-08', 'Use modular 4-person ECLSS units for the one-ring case', 'modular'),
        ('DR3-09', 'Make cruise speed a per-mission choice (0.008 c inside 200 AU)', 'per mission'),
    ]
    return [dict(id=a, question=b, recommended=c) for a, b, c in D]


def main():
    s = spec.load()[0]
    pl = json.loads((ROOT/'references/p1_power_loads.json').read_text())
    G = json.loads((R/'phase3_eps_g1.json').read_text())
    E = json.loads((R/'phase2_eps_b.json').read_text())
    life = tomllib.loads((ROOT/'data/life_support.toml').read_text())
    U = G['reference_unit']
    need = st(pl, 'COAST_HV_PROACTIVE')[1]
    eol = 0.9
    cfgs = {
        'C-lean 3+1 x 1.75 (blades 90/210/330/210)': dict(n=4, unit_W=1.75e6*eol, blades=[90, 210, 330, 210], buses=['A', 'B', 'A', 'B'], modules=['M1', 'M1', 'M1', 'M2']),
        'C-lean 3+1, units 2/4 on different blades (fix)': dict(n=4, unit_W=1.75e6*eol, blades=[90, 210, 330, 90], buses=['A', 'B', 'A', 'B'], modules=['M1', 'M1', 'M1', 'M2']),
        '2+1 x 2.66 (one per blade)': dict(n=3, unit_W=2.66e6*eol, blades=[90, 210, 330], buses=['A', 'B', 'A'], modules=['M1', 'M1', 'M1']),
        '2 x 100 % x 5.3': dict(n=2, unit_W=5.3e6*eol, blades=[90, 330], buses=['A', 'B'], modules=['M1', 'M2']),
        '4+1 x 1.33': dict(n=5, unit_W=1.33e6*eol, blades=[90, 210, 330, 90, 330], buses=['A', 'B', 'A', 'B', 'A'], modules=['M1', 'M1', 'M1', 'M2', 'M2']),
    }
    mc = redundancy(cfgs, need)
    mc_ess = redundancy({k: v for k, v in cfgs.items() if k.startswith('C-lean 3+1 x')}, st(pl, 'SURVIVAL_MISSION')[1], trials=1500)
    planning = E['demand']['planning_open_W']
    bat = battery(pl); buf = buffer(pl, planning); th = thermal_closure(pl, U, planning); sh = shielding(pl, G, E['cryo'])
    L = ledgers(pl, G, bat, buf, s)
    TA = thermal_archs(pl); L1o = l1_options(pl); L2o = l2_options(pl, G, mc); DI = district_options(G); TR = transition(pl)
    M = missions(s, pl); LG = logistics(life); EC = eclss_options()
    NA = narrative(life, {k: v for k, v in mc['C-lean 3+1 x 1.75 (blades 90/210/330/210)'].items()})
    CV = convergence(s, pl, L, TA, L1o, L2o, mc, G, M)
    out = dict(status='ISSA Phase III STUDY (NONCANON)', battery=bat, buffer=buf, thermal_closure=th, shielding=sh,
               redundancy=dict(configs=cfgs, need_W=need, mc=mc, essential=mc_ess,
                               model='event Monte Carlo, 3,000 trials; shared blade headers, blade sectors, buses, software and design common cause, module damage '
                                     'zones and maintenance-equipment outages; conversion-side failures repairable by ORU, reactor-side permanent'),
               ledgers=L, thermal_architectures=TA, l1=L1o, l2=L2o, district=DI, transition=TR, missions=M, logistics=LG, eclss=EC,
               narrative=NA, convergence=CV, problems=problems(), decisions=decisions())
    (R/'phase3.json').write_text(json.dumps(out, indent=1, default=lambda o: None if o == math.inf else o).replace('Infinity', 'null'))
    # console summary
    print('battery', {k: [round(x) for x in v['protected_kWh']] for k, v in bat['options'].items()}, 'power-limited', bat['power_limited'])
    for r in buf['summary']: print('buffer', r['case'][:34].ljust(34), r['life'], [round(x, 2) for x in r['surplus_MW']], r['sustainable'], [round(x, 1) for x in r['buffer_t_li']], [round(x, 1) for x in r['buffer_t_sc']])
    for r in th['rows']:
        if r['band'] in ('nominal', 'high') and r['condition'] == 'intact': print('thermal', r['state'], r['band'], r['closes'], r['fails'])
    print('shield', round(sh['eps_g1']['per_unit_t'], 1), 'He3 dep W', round(sh['he3_deposit_W']), 'lift', round(sh['he3_stage_lift_W']), sh['wide_cone'])
    for k, v in mc.items(): print('mc', k[:44].ljust(44), {kk: (vv['3 yr']['P_any_shortfall'], vv['3 yr']['P_permanent_shortfall'], round(vv['3 yr']['unavailability'], 5)) for kk, vv in v.items() if kk in ('u=0.05', 'u=0.05, no repair')})
    print('ledger increment', [round(x, 1) for x in L['increment_total_t']], [(r['line'], [round(x, 1) for x in r['increment_t']]) for r in L['increment']])
    for r in TA['rows']: print('TA', r['doctrine'][:8], r['key'], round(r['added_t'], 1), 'L1', round(r['L1_W']/1e6, 1), 'pump', round(r['pump_work_W']/1e6, 1), r['L2_in_burn'])
    for r in L2o['rows']: print('L2', r['name'][:30].ljust(30), [round(x) for x in r['mass_t']], [round(x/1e6, 2) for x in r['after_one_loss_W']], [round(x/1e6, 2) for x in r['surplus_with_planning_EOL_W']])
    print('sec550', {k: ([round(x) for x in v['area_m2']], [round(x, 1) for x in v['length_m']], [round(x/1e9, 2) for x in v['hot_allowance_W']]) for k, v in CV['section550'].items()})
    print('burns', [(b['burn'], round(b['duration_d'], 2), round(b['distance_AU'], 2)) for b in M['burns']], 'dPdM', round(M['coupled_dP_dM'], 3))
    for c in CV['candidates']: print('CV', c['name'][:50].ljust(50), [round(x) for x in c['dry_added_t']], 'dep+', [round(x) for x in c['extra_departure_t']], 'cg', round(c['cg_x_m'], 1))
    for r in NA['rows']: print('narr', r['case'], round(r['years'], 2))


if __name__ == '__main__':
    main()
