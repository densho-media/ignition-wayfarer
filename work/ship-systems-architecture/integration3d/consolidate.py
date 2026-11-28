"""ISSA consolidation and structural handover (owner brief 2026-11-28 09:15Z). STUDY, PROTOTYPE, noncanon, Track F1 working configuration.

Implements the owner decisions DR-3D-01..04 and the CP4 approvals (WARM/LOW closure, heavy MRU transport, body-bay module 10), reconciles the
electrical, L2-cooling, ECLSS, cryogenic and mass accounts, and writes one versioned systems-to-structure interface (SSI) for the PSA
workstream. It supersedes the Checkpoint 4 ledger with WF-F1-C1.0.

Reads the Checkpoint 1-4 results; writes ../results/i3d_consolidated.json, i3d_structure_interface.json (SSI-1.0) and SVG sections.
Pure Python (repo modules only). Run after systems3d.py: consolidate.py, then make_review_i3d.py, then build_report.py.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent; W = HERE.parent; ROOT = W.parents[1]; R = W/'results'
sys.path.insert(0, str(ROOT/'src/wayfarer')); sys.path.insert(0, str(HERE))
import spec  # noqa: E402
import fuel_storage as fs  # noqa: E402
import fuel_loads  # noqa: E402
import mass_model as mm  # noqa: E402
import tanks3d  # noqa: E402

J = lambda n: json.loads((R/n).read_text())
P5, P6, PW, H6, RD, EL, EC, LG4, RM, TK, LD = (J(n) for n in ('phase5.json', 'phase6.json', 'i3d_power.json', 'i3d_h6a.json', 'i3d_radiators.json',
                                                           'i3d_electrical.json', 'i3d_eclss.json', 'i3d_logistics.json', 'i3d_remaining.json',
                                                           'i3d_tanks.json', 'i3d_ledger.json'))
CIRC = 40.2e3
CONFIG = 'WF-F1-C1.0'
SSI_VERSION = 'SSI-1.0'
G0 = 9.80665
A_PEAK_G = H6['supports']['a_peak_g']                     # 0.736 g, peak burn acceleration (end of the last burn)
LAY = {x['name']: x for x in P6['layout']}


def az_of(y, z):
    return math.degrees(math.atan2(z, y)) % 360.0


def pz(az, r):
    a = math.radians(az); return r*math.cos(a), r*math.sin(a)


# ============================================================================================================ radiators (DR-3D-04, WARM/LOW)
def radiators(C, l1_reactive_W):
    cryo_reject_W = C['reject_operating_W']
    B = RD['hot_budget']; HF = RD['hot_fins']; hp = P6['reconciliation']['electrical']['heat_pump']
    hot_len = P6['radiators']['F1']['hot_length_m']-RD['section']['delta_m']           # HOT length after the 9.38 m L2 section
    n_man = math.ceil(hot_len/HF['fin_half_m'])+1
    fins = dict(decision='DR-3D-04 APPROVED', pitch_m=HF['fin_half_m'], hot_length_m=hot_len, manifolds_per_blade=n_man, manifolds_total=3*n_man,
                phase6_manifolds_per_blade=math.ceil(hot_len/(2*HF['fin_half_m']))+1, extra_t=HF['manifold_walls_extra_t'],
                layout='manifold at the AFT end of every fin; Li heat-pipe fin points forward 1.47 m to the next manifold',
                modes=[dict(mode='acceleration burn (+x, up to 0.74 g)', condensate='driven aft to the manifold (evaporator) by the acceleration: assists the wick',
                            ok=True),
                       dict(mode='braking burn', condensate='Wayfarer brakes after the turnover with the drive still aft, so the acceleration is +x in ship axes: same as '
                            'acceleration', ok=True),
                       dict(mode='coast (0 g)', condensate='capillary return only over 1.47 m (one fin length, half the Phase V 2.94 m): margin rises', ok=True),
                       dict(mode='startup (frozen Li)', condensate='the manifold thaws first and the melt front runs forward along each fin; the residual acceleration of the '
                            'first seconds holds the melt at the evaporator, which is the safe direction', ok=True),
                       dict(mode='shutdown', condensate='the tail-off acceleration parks the liquid at the manifold before it freezes, so the next start finds it at the '
                            'evaporator; a coast freeze (no acceleration) is the Phase V frozen-start case and stays an FT-06 assumption', ok=True)])
    # complete propulsion heat budget at peak burn and at the reactive-defense peak (burnout)
    hp_pro = hp['proactive_W']+hp['proactive_lift_W']                                     # retired once WARM absorbs the burn shortfall
    eta_pick = 0.65                                                                       # FT-04 nominal pickup efficiency
    pick_loss = l1_reactive_W*(1/eta_pick-1); hp_react = hp['reactive_peak_W']+hp['reactive_lift_W']
    reserve_nominal = B['remaining_mitigated_W']+hp_pro
    reserve_reactive = reserve_nominal-hp_react-pick_loss
    budget = dict(items=[('HOT headroom (Phase VI, 20 % rule)', B['hot_headroom_W']), ('L2 section growth to 9.38 m (DR-3D-02)', B['l2_growth_W']),
                         ('H6a trunk shading (bound)', B['trunk_shading_W']), ('forward-pointing fins (DR-3D-04): fin loss removed', 0.0),
                         ('burn heat pumps proactive duty retired (WARM closure)', hp_pro)],
                  reserve_nominal_W=reserve_nominal, reactive=[('burn heat pumps at the reactive peak (work + lift)', -hp_react),
                                                               (f'L1 pickup loss at eta {eta_pick} on {l1_reactive_W/1e6:.1f} MW', -pick_loss)],
                  reserve_reactive_W=reserve_reactive)
    # requirements
    W0 = RD['warm']; L0 = RD['low']; adds = RM['warm']['adds']
    warm_need = adds['phase6_shortfall_W']+adds['nak_insulation_leak_W']+adds['bus_loss_W']
    avionics = 1.0e6-fuel_loads.cooling(spec.load()[0])['low_section_margin_W']-fuel_loads.cooling(spec.load()[0])['rejected_W']
    low_need_cap = 1.2*(avionics+cryo_reject_W)                                            # min_margin 0.2 rule of the zoning
    low_short = max(0.0, low_need_cap-L0['design_W'])
    per_m_hot = RD['section']['per_m_hot_W']; per_m_warm = W0['design_W']/22.5; per_m_low = L0['design_W']/20.0
    q_low = L0['design_W']/(20.0*6*30.5)                                                   # effective design flux of the LOW section, W/m2
    warm_ext = warm_need*1.2/per_m_warm; low_ext = low_short/per_m_low
    opts = []
    # O1: shift L2 and the WARM/LOW sections aft into HOT
    d1 = warm_ext+low_ext
    opts.append(dict(id='O1', name='Longitudinal: shift L2, WARM and LOW aft into HOT', area_m2=d1*6*30.5, hot_cost_W=d1*per_m_hot,
                     reserve_reactive_after_W=reserve_reactive-d1*per_m_hot, geometry=f'L2/WARM/LOW boundaries move {d1:.1f} m aft; envelope and blades unchanged',
                     verdict='REJECTED: consumes HOT that the reactive-defense peak needs (reserve goes negative)' if reserve_reactive-d1*per_m_hot < 0 else 'possible'))
    opts.append(dict(id='O2', name='Radial: wider WARM/LOW span beyond r 37 m', area_m2=None, hot_cost_W=0.0,
                     geometry='tip radius > 37 m', verdict='REJECTED: breaks the Brow shadow rule (radiators inside r 45 - 8 m)'))
    opts.append(dict(id='O3', name='Longitudinal forward: WARM/LOW past x 93.4', area_m2=None, hot_cost_W=0.0,
                     geometry='forward of LOW is the ring sweep keep-out (x 93.65-106.95, r < 31.5)', verdict='REJECTED at full span: collides with the ring sweep'))
    T_w = W0['T_K']*((W0['design_W']*1.2+warm_need*1.2)/(W0['design_W']*1.2))**0.25
    T_l = L0['T_K']*((L0['design_W']+low_short)/L0['design_W'])**0.25
    opts.append(dict(id='O4', name='Temperature redistribution only', area_m2=0.0, hot_cost_W=0.0, geometry='none',
                     T_warm_K=T_w, T_low_K=T_l,
                     verdict=f'possible: WARM {W0["T_K"]:.0f} -> {T_w:.1f} K, LOW {L0["T_K"]:.0f} -> {T_l:.1f} K; the LOW rise costs cryocooler input '
                             f'(Carnot work rises with the reject temperature) and avionics margin'))
    # O5 preferred: WARM by temperature (no new area); LOW by forward tip extensions outside the ring sweep (r 31.5-37 m, inside the Brow shadow), as long
    # as the ring keep-out allows (x 93.4-106.45, 0.5 m short of its forward end), and the remainder by a small LOW temperature rise that is iterated with
    # the cryocooler work (Carnot input grows with the reject temperature)
    tab_r = (31.5, 37.0); tab_view = 0.90                                                    # 10 % view penalty: the tab faces see part of the rings' rim
    per_m_tab = 3*2*(tab_r[1]-tab_r[0])*q_low*tab_view
    Lt = min(low_short/per_m_tab, 106.95-0.5-93.4); tab_x = (93.4, 93.4+Lt); tab_cap = Lt*per_m_tab
    def reject_at(T):
        return sum(st['lift_W']*(1+st['W_per_W']*(T-st['T_cold'])/(300.0-st['T_cold'])) for st in C['stages'])
    T_lo = L0['T_K']
    for _ in range(200):
        need_T = 1.2*(avionics+reject_at(T_lo)); have_T = (L0['design_W']+tab_cap)*(T_lo/L0['T_K'])**4
        if have_T >= need_T: break
        T_lo += 0.1
    tab_t = 3*(tab_r[1]-tab_r[0])*Lt*6.0e-3+3*Lt*0.15                                        # 6 kg/m2 planform two-face ammonia panel + 0.15 t/m spar
    pref = dict(id='O5', name='PREFERRED: WARM at 451 K (no new area) + LOW forward tip extensions beside the rings + LOW at ' f'{T_lo:.0f} K',
                T_warm_K=T_w, warm_area_m2=0.0, low_tab_length_m=Lt, low_tab_x=tab_x, low_tab_r=tab_r, low_tab_area_m2=3*2*(tab_r[1]-tab_r[0])*Lt,
                low_tab_capacity_W=tab_cap, low_tab_mass_t=tab_t, hot_cost_W=0.0, T_low_K=T_lo, cryo_reject_at_T_W=reject_at(T_lo),
                cryo_input_at_T_W=reject_at(T_lo)-sum(st['lift_W'] for st in C['stages']),
                low_need_at_T_W=1.2*(avionics+reject_at(T_lo)), low_have_at_T_W=(L0['design_W']+tab_cap)*(T_lo/L0['T_K'])**4,
                tabs_limited=low_short/per_m_tab > Lt, tabs_needed_alone_m=low_short/per_m_tab,
                view_factor_note=f'tab faces lose {100*(1-tab_view):.0f} % to the rings\' rim (PROTOTYPE)',
                clear_to_ring_m=tab_r[0]-30.0, brow_shadow_margin_m=45.0-tab_r[1],
                verdict='keeps the radial envelope, the three blades and all HOT; WARM machinery runs 11 K warmer; LOW gains physical area where the rings leave room '
                        'and runs slightly warmer for the rest')
    opts.append(dict(id='O5', name=pref['name'], area_m2=pref['low_tab_area_m2'], hot_cost_W=0.0, geometry=f'LOW tabs x {tab_x[0]:.1f}-{tab_x[1]:.1f}, r 31.5-37; '
                     f'WARM {T_w:.0f} K, LOW {T_lo:.0f} K', verdict='PREFERRED'))
    # consequences of the preferred configuration
    mdot_w = W0['mdot_kg_s']*(W0['design_W']+warm_need)/W0['design_W']; dp_w = 2.0e5*(mdot_w/W0['mdot_kg_s'])**2
    pump_w0 = W0['mdot_kg_s']*2.0e5/950.0/0.6; pump_w = mdot_w*dp_w/950.0/0.6
    mdot_l = L0['mdot_kg_s']*(L0['design_W']+low_short)/L0['design_W']; pump_l0 = L0['mdot_kg_s']*1.5e5/600.0/0.6; pump_l = mdot_l*1.5e5*(mdot_l/L0['mdot_kg_s'])**2/600.0/0.6
    joint = dict(dT_before_K=W0['T_K']-L0['T_K'], dT_after_K=T_w-L0['T_K'], leak_increase=(T_w-L0['T_K'])/(W0['T_K']-L0['T_K'])-1)
    expansion = dict(warm_extra_mm=22.5*1.5e-6*(T_w-W0['T_K'])*1e3, tab_growth_mm=Lt*25e-6*0.0*1e3,
                     note='WARM grows 0.4 mm more over 22.5 m (C-C, ~1.5e-6/K); the LOW tabs stay at the LOW temperature (no new growth); the tab spar slides at its '
                          'forward clevis')
    degraded = dict(warm_one_loop=W0['capacity_after_loop_loss'], low_one_loop=L0['capacity_after_loop_loss'],
                    tabs='own A/B interleave on each tab (same 86 % rule)',
                    warm_after_loop_loss_W=(W0['design_W']*1.2+warm_need*1.2)*W0['capacity_after_loop_loss'],
                    warm_load_W=W0['design_W']+warm_need)
    heat_pump = dict(before=f'Phase VI: the {adds["phase6_shortfall_W"]/1e3:.0f} kW WARM burn shortfall was lifted into HOT by the burn heat pumps '
                            f'({hp["proactive_W"]/1e6:.2f} MW of L1 work, {hp_pro/1e6:.2f} MW into HOT)',
                     after='WARM at 451 K absorbs it directly: the proactive heat-pump duty is retired, L1 continuous falls by that work, HOT gains it back; '
                           'the 210 MW heat-pump rating stays installed for the reactive defense', retired_W=hp['proactive_W'], hot_returned_W=hp_pro,
                     counted_once=True)
    return dict(fins=fins, budget=budget, need=dict(warm_W=warm_need, low_capacity_W=low_need_cap, low_short_W=low_short, avionics_W=avionics,
                                                   cryo_reject_W=cryo_reject_W, warm_ext_equiv_m=warm_ext, low_ext_equiv_m=low_ext),
                options=opts, preferred=pref, pumps=dict(warm_W=(pump_w0, pump_w), low_W=(pump_l0, pump_l), mdot_warm=mdot_w, mdot_low=mdot_l),
                joint=joint, expansion=expansion, degraded=degraded, heat_pump=heat_pump,
                supports=dict(tab='LOW forward spar extended by the tab length; tab cantilevered from the LOW forward spar at r 31.5-37 with two hinge-clevis lugs '
                                   'per blade (ISSA bracket) onto the PSA radiator root frame at x 93.4; burn load ' f'{tab_t/3*1e3*A_PEAK_G*G0/1e3:.1f} kN per blade'),
                mass_t=dict(fins=HF['manifold_walls_extra_t'], low_tabs=tab_t, warm_pump_upgrade=0.15))


# ============================================================================================================ tanks (DR-3D-01)
def tanks(s, prop_t):
    ts = fs.tanks(s); f = fs.farm_cfg(s); w, hr = f['wall_m'], f['head_ratio']
    need6, _ = tanks3d.need_F1(s); base_prop = next(c for c in P6['mass']['F1']['cases'] if c['case'] == 'nom')['propellant_t']
    k = prop_t/base_prop; need = {sp: v*k for sp, v in need6.items()}
    dL, caps = tanks3d.stretch(s, ts, need); cap = caps(dL)
    area = sum(tanks3d.area_at(t, dL) for t in ts); x0, x1 = fs.span(s)
    fill = {sp: need[sp]/cap[sp] for sp in need}
    per_vessel = []
    for t in ts:
        v = fs.vessel_volume(t['a_env'], t['length']+dL, w, hr); rho = {'helium-3': 59.0, 'hydrogen': 70.8, 'deuterium': 162.4}[t['species']]
        m_prop = v*fill[t['species']]*rho/1e3
        per_vessel.append(dict(id=t['id'], species=t['species'], cls=t['tank_class'], az=t['azimuth_deg'], R=t['R'], a=t['a'], x0=t['x0'], x1=t['x1']+dL,
                               volume_m3=v, prop_t=m_prop, axial_kN=m_prop*1e3*A_PEAK_G*G0/1e3))
    return dict(decision='DR-3D-01 APPROVED: T-A reference; T-B kept as mission-modular alternative; T-C research option (no densification adopted)',
                propellant_t=prop_t, cp1_propellant_t=base_prop, scale=k, need_m3=need, added_length_m=dL, cp1_added_length_m=TK['alternatives'][0]['added_length_m'],
                vessel_length_m=(x1-x0)+dL, farm_x=(x0, x1+dL), brow_x=(141.75+dL, 144.75+dL), ship_length_m=289.5+dL, capacity_m3=cap, fill=fill,
                shell_area_m2=area, cp1_shell_area_m2=TK['alternatives'][0]['shell_area_m2'], vessels=per_vessel,
                supports=dict(aft='each vessel on its aft skirt at the thrust deck (axial burn load, anchor)', forward='forward guide ring on the forward hoop (radial only, axial '
                              'slide for contraction: ' f'{fuel_loads.q(s)["thermal_contraction"]*(x1-x0)*1e3:.0f} mm on the historical length, '
                              f'{fuel_loads.q(s)["thermal_contraction"]*((x1-x0)+dL)*1e3:.0f} mm on the stretched barrel)',
                              keel='keel rails lengthen with the barrel', burn_axial_kN_total=sum(v['axial_kN'] for v in per_vessel)),
                interfaces=[f'Brow, EYE, lances and the forward hoop move forward {dL:.2f} m (x {141.75+dL:.2f}-{144.75+dL:.2f})',
                            'farm outlets, ring mains and the aft deck stay (aft end unchanged)', 'forward links and guides re-anchor at the new forward hoop',
                            'docking corridors 195/315 deg and the EVA lane 50 deg lengthen with the farm'])


# ============================================================================================================ cryogenics (7.4)
def cryo(s, area_m2):
    ts = fs.tanks(s); A0 = sum(mm.shell_area(t) for t in ts); fA = area_m2/A0
    c = fuel_loads.cooling(s); CR = P6['reconciliation']['cryo']; case = next(x for x in CR['cases'] if x['load'].startswith('full'))
    pf = (3.5e6/0.154)/CR['basis']['unit_thermal_W']
    he3_leak = c['he3_stage_lift_W']*fA; sh_leak = c['shield_lift_W']*fA; he3_n = case['he3_nuclear_W']*pf; sh_n = case['h_d_nuclear_W']*pf
    lift3 = he3_leak+he3_n; lift20 = sh_leak+sh_n
    in3 = lift3*CR['he3_W_per_W']; in20 = lift20*CR['shield_W_per_W']; inp = in3+in20; rej = inp+lift3+lift20
    inst = 1.25; existing_in = c['rejected_W']
    sens = [dict(nuclear=f, input_W=(he3_leak+he3_n*f)*CR['he3_W_per_W']+(sh_leak+sh_n*f)*CR['shield_W_per_W']) for f in (0.0, 0.5, 1.0, 2.0, 5.0)]
    stations = len(ts); heads = 2
    m_new = inp*inst/1e3*0.012; m_exist = existing_in*inst/1e3*0.012
    return dict(area_factor=fA, A0_m2=A0, area_m2=area_m2, power_factor=pf,
                stages=[dict(stage='3 K (helium-3 only, 6 vessels)', T_cold=3.0, leak_W=he3_leak, nuclear_W=he3_n, lift_W=lift3, W_per_W=CR['he3_W_per_W'], input_W=in3),
                        dict(stage='20 K shields (all 13 vessels)', T_cold=20.0, leak_W=sh_leak, nuclear_W=sh_n, lift_W=lift20, W_per_W=CR['shield_W_per_W'], input_W=in20)],
                operating_input_W=inp, installed_input_W=inp*inst, reject_operating_W=rej, reject_installed_W=(inp+lift3+lift20)*inst,
                existing_input_W=existing_in, sensitivity=sens, stations=stations, heads_per_station=heads,
                redundancy='two cooler heads per station, each 62.5 % of the station need (installed 125 %): one head lost keeps 62.5 %, so the vessel warms slowly '
                           'and its neighbours cannot help; recovery = head swap (ORU, LOG-G1 class) within the vessel\'s thermal hold time',
                hold_time_h=None, mass_new_t=m_new, mass_existing_t=m_exist, mass_increment_t=m_new-m_exist,
                flows=[('electrical input (L2 bus)', inp), ('heat lifted from the 3 K and 20 K stages', lift3+lift20), ('heat rejected to LOW (input + lift)', -rej)],
                explain=(f'CP4 quoted {RM["cryo"]["input_W"]/1e3:.0f} kW = the INSTALLED input (operating x 1.25) and {RM["cryo"]["low"]["cryo_reject_W"]/1e3:.0f} kW '
                         'for LOW, which mixed the production rejection (scaled) with installed nuclear terms: the two were different bases, not an energy loss. '
                         f'Here every watt has one destination: operating input {inp/1e3:.0f} kW from the L2 bus, plus {lift3+lift20:.0f} W lifted from the cold '
                         f'stages, leaves as {rej/1e3:.0f} kW into LOW; at full installed capacity (recovery cool-down) LOW sees {(inp+lift3+lift20)*inst/1e3:.0f} kW '
                         'for hours, inside its 20 % margin plus the tabs.'),
                radiation_note='nuclear heating comes from the Phase VI OpenMC surrogate (simplified source and structure): a sensitivity, not a validated shielding result')


# ============================================================================================================ electrical (7.1) and L2 loop failure (7.2)
def electrical(cryo_C, retired_hp_W):
    E6 = P6['reconciliation']['electrical']; sR = E6['sum_R']; hp = E6['heat_pump']; L2 = E6['L2']
    cont = sR['continuous_proactive_W']-retired_hp_W; react = sR['continuous_reactive_W']-retired_hp_W
    rows = []
    for r in E6['F']:
        sup = {'L1': 'direct (L1 pickup, FT-04)', 'pulse bank': 'buffered (pulse bank, own store)', 'A': 'L2 bus (charging)', 'L2 / ride-through': 'L2 / ride-through'}.get(r['bus'], r['bus'])
        c_pro = r['continuous_proactive_burn_W']-(retired_hp_W if r['id'] == 'TMS.BURN_HEAT_PUMPS' else 0.0)
        rows.append(dict(id=r['id'], title=r['title'], supply=sup, installed_W=r['installed_W'], proactive_W=max(0.0, c_pro), reactive_W=r['continuous_reactive_burn_W']
                         - (retired_hp_W if r['id'] == 'TMS.BURN_HEAT_PUMPS' else 0.0), peak_W=r['peak_W'], storage_W=r['storage_discharge_W']))
    rows.append(dict(id='DEF.ENGAGEMENT', title='Defense engagement burst (CP3 defense bus)', supply='buffered (defense buffer, 4 modules)', installed_W=21e6,
                     proactive_W=0.0, reactive_W=0.0, peak_W=21e6, storage_W=21e6))
    # conductor and converter
    V = 10e3; J_A = 1.5; L_bus = 60.0
    A_cont = cont/V/J_A; A_peak = react/V/J_A
    t_old = 2*A_cont*1e-6*L_bus*2700/1e3; t_new = 2*A_peak*1e-6*L_bus*2700/1e3
    eta = 0.65; pick_loss_cont = cont*(1/eta-1); pick_loss_peak = react*(1/eta-1)
    # storage charging from the L2 surplus with the revised cryo load
    extra_cryo = cryo_C['operating_input_W']-cryo_C['existing_input_W']
    surplus = {k: v-extra_cryo for k, v in L2['surplus_coast_W'].items()}
    buf_kWh = 58.0; rech_s = {k: buf_kWh*3.6e6/v for k, v in surplus.items()}
    pulse_J = 50e6*1.0                                                                     # 50 MW pulse discharge class, 1 s per ignition step (Phase V class)
    states = [dict(state='coast (L2 only)', L1='off', L2=f'{(L2["demand_W"][1]+extra_cryo)/1e6:.2f} MW of {L2["available_W"]["EOL"]/1e6:.2f} MW EOL', buffer='charged', ok=True),
              dict(state='proactive burn', L1=f'{cont/1e6:.1f} MW direct from the pickup (no heat-pump duty)', L2='as coast', buffer='charged', ok=True),
              dict(state='reactive defense at burnout (peak)', L1=f'{react/1e6:.1f} MW (heat pumps {hp["reactive_peak_W"]/1e6:.1f} MW) inside the 100 MWe FT-04 rating',
                   L2='as coast', buffer='21 MW x 10 s burst on top, from the defense bus', ok=react <= 1.0e8),
              dict(state='L1 pickup fault in a burn', L1='lost', L2=f'carries the drive services that fit its surplus ({surplus["EOL"]/1e6:.1f} MW EOL); heat pumps off -> the '
                   'reactive defense is limited to buffer bursts; H6a pumps fall back to ... (see note)', buffer='bursts only', ok=False),
              dict(state='L1 bus fault (one segment)', L1='the bus is two half-rated segments on separate routes: half the rating remains', L2='unchanged', buffer='as normal', ok=True),
              dict(state='defense burst during an L2 unit trip', L1='as before', L2='survivors ramp in 26 s (ride-through cells cover)', buffer='burst from its own store', ok=True)]
    h6a_pumps = next(r for r in E6['F'] if r['id'] == 'TMS.HOT_LOOP_PUMPS')['continuous_proactive_burn_W']
    return dict(continuous_W=cont, reactive_W=react, peak_with_buffer_W=react+21e6, ft04_rating_W=1.0e8, rows=rows,
                conductor=dict(V=V, J_A_mm2=J_A, length_m=L_bus, A_cont_mm2=A_cont, A_peak_mm2=A_peak, mass_old_t=t_old, mass_new_t=t_new,
                               rule='L1 conductors sized for the reactive peak (minutes at burnout), not the proactive continuous load; two half-rated segments on '
                                    'separate routes (az 30 and az 150)', within_distribution_line=True),
                converter=dict(rating_W=1.0e8, note='the 100 MWe FT-04 rating (CONDITIONAL) is the converter rating; it covers the reactive peak with '
                                                  f'{(1e8-react)/1e6:.1f} MW to spare; the defense burst comes from the buffer, not the pickup'),
                thermal=dict(pickup_loss_cont_W=pick_loss_cont, pickup_loss_peak_W=pick_loss_peak, sink='HOT loop (H6a), inside the HOT budget below',
                             peak_duration='the reactive peak lasts while a defense engagement runs at burnout; the buffer covers 10 s bursts; minutes-long peaks '
                                           'are HOT-limited (budget below), not conductor-limited'),
                surplus_W=surplus, extra_cryo_W=extra_cryo, buffer_recharge_s=rech_s,
                h6a_pump_W=h6a_pumps,
                note='The H6a pumps (10 MW) run from L1 in a burn. With the pickup lost they must come from L2 (8.7 MW EOL, demand ~5.5 MW): they cannot all run, so a '
                     'pickup fault means a controlled drive shutdown (decay heat goes to the H6a at part flow, 0.15 of the pump power, which L2 can carry). This is an '
                     'existing Phase V/VI rule and is stated here, not solved.')


def l2_failure():
    F = RD['failures']; Cap = F['design_W']*(1-F['pipe_loss_allowance']); eta = 0.154; Wf = 3.5e6/eta*(1-eta)
    # unit i feeds loop A of blade i and loop B of blade i+1; unit 1 loses loop B (blade 2 loses its B feed)
    # blade 2 = U2*s; blade 3 = U2*(1-s) + U3*u; blade 1 = U1 + U3*(1-u); maximise U1+U2+U3 with every blade <= Cap
    best = None
    for U2 in [i/100*Wf for i in range(101)]:
        for U3 in [i/100*Wf for i in range(101)]:
            s = min(1.0, Cap/U2) if U2 > 0 else 1.0
            r3 = Cap-U2*(1-s)
            if r3 < -1e-6: continue
            u = min(1.0, r3/U3) if U3 > 0 else 1.0
            U1 = max(0.0, min(Wf, Cap-U3*(1-u)))
            tot = U1+U2+U3
            if best is None or tot > best['tot']+1e-6: best = dict(U=(U1, U2, U3), s=s, u=u, tot=tot)
    Pe = [u*eta/(1-eta) for u in best['U']]
    demand = P6['reconciliation']['electrical']['L2']['demand_W']
    # thermal transient: stored heat of the overloaded blade's L2 section (heat pipes, headers, NaK, faces) vs the 25 % excess
    m_kg = sum(RD['mass']['per_blade_t'].values())*1e3; nak_kg = RD['nak']['header']['length_m']*math.pi*(RD['nak']['header']['D_m']/2)**2*780
    C = m_kg*450+nak_kg*900; excess = 0.25*F['design_W']; t50 = C*50/excess
    return dict(case='one NaK loop of unit 1 lost (unit feeds only its own blade): fixed split loads that blade to 125 %',
                usable_cap_W=Cap, unit_waste_full_W=Wf, safe_state=dict(unit_waste_W=best['U'], Pe_W=Pe, total_Pe_W=sum(Pe), split_unit2=best['s'], split_unit3=best['u']),
                derating=f'faulted unit to {100*best["U"][0]/Wf:.0f} % on its remaining loop, the other two at 100 % with biased splits: '
                         f'{sum(Pe)/1e6:.2f} MWe of 10.5',
                demand_W=demand, shed_W=max(0.0, demand[2]-sum(Pe)),
                transient=dict(heat_capacity_J_K=C, excess_W=excess, t_to_plus50K_s=t50,
                               sequence=['0 s: loop low-flow trip on the faulted unit', '< 2 s: flow-control valves rebias the neighbouring units (67/33 class)',
                                         f'< 5 s: TAC bypass sets the faulted unit back (turbine bypass to the recuperator); the overloaded blade gains < 50 K in {t50:.0f} s',
                                         '1-3 min: reactor ramp-down of the faulted unit to hot standby (decay heat on its own loop A)',
                                         'L2 load shedding of discretionary loads if the demand band is above the derated output']),
                recovery=['isolate the failed loop (isolation valves at the root and the gas cooler)', 'diagnose: EM pump ORU swap (robot, coast) or a leak (drain to the NaK '
                          'reserve, sectional repair = yard if the leak is in the casing-hull annulus)', 'refill, warm the loop with the unit\'s decay heat, rebias, return to '
                          'strategy C'],
                verdict='safe degraded state without full output: 2 units + standby carry the coast and burn demand bands except the highest, which sheds discretionary loads')


# ============================================================================================================ ECLSS (7.3)
def eclss():
    lay = next(x for x in P6['reconciliation']['eclss']['layouts'] if x['units'] == 7)
    fail = [k for k, v in lay['results'].items() if not v][0]
    over = 12-2*4                                                                          # ring B with two units for 12 people (four-person units)
    co2 = over*1.04; lioh = co2*1.25                                                       # kg/day CO2 and LiOH (ISS planning rates)
    days = 30
    return dict(matrix=lay['results'], passes=lay['passes'], of=lay['of'], failing=fail,
                failing_eval=dict(overload_persons=over, co2_kg_day=co2, lioh_kg_day=lioh, reserve_days=days, lioh_t=lioh*days/1e3, o2='O2 from the O2 reserve / '
                                  'generation (separate system), unaffected', repair='hub unit ORU swap (spares in the hub store, 4-24 h)',
                                  reliability='three concurrent losses (ring A + one B unit + hub unit) before a repair: with ORU repair times of hours this is a '
                                              'rare compound case; the emergency CO2 reserve bridges it, so an eighth unit is not required (it stays the alternative, '
                                              '+1.2 t)'),
                maintenance='hub unit: maintenance face on the hub aisle (1.0 m clear); ring units: ORUs <= 0.70 m through the ring aisle',
                rotating='both rotary couplings carry the hub ducts (D 0.28 m) through the transfer drums; seal leak 0.05-1.0 kg/d each',
                occupancy='emergency occupancy of the stationary hub: 12 people for the refuge time on the hub unit + CO2 reserve')


# ============================================================================================================ MRU transport (5)
def mru(s):
    parts = PW['unit']['parts']; c = LG4['carriage']
    def env(p):
        if p['shape'] == 'cyl': return dict(L=2*p['half'][0], D=2*p['half'][1])
        if p['shape'] == 'cone': return dict(L=2*p['half'][0], D=2*p['half'][2])
        if p['shape'] == 'ring': return dict(L=2*p['half'][0], D=2*p['half'][1])
        if p['shape'] == 'duct': return dict(L=2*p['half'][0], D=0.6, note='removed in duct segments (D 0.6 m), not as the wrapped assembly')
        return dict(L=2*p['half'][0], D=2*math.hypot(p['half'][1], p['half'][2]))
    items = []
    for p in parts:
        e = env(p); t = p['module_t']
        cls = ('YARD' if p['key'] in ('reactor_ihx', 'shield', 'structure') else 'IN-FLIGHT (restricted)' if p['key'] in ('tac', 'ducts') else 'IN-FLIGHT (ORU)')
        items.append(dict(name=p['name'], t=t, env=e, oru=p['oru'], handling='robot / LOG-G1' if t <= 3.0 else 'MRU carriage', service=cls))
    def sweep(R_sw, r_c):
        route = ((c['x'][0], *pz(270.0, r_c)), (c['x'][1], *pz(270.0, r_c))); near = []; ax = pz(270.0, r_c)
        def segdist(a0, a1, b0, b1, n=60):
            best = 9e9
            for i in range(n+1):
                p = [a0[k]+(a1[k]-a0[k])*i/n for k in range(3)]
                d = [b1[k]-b0[k] for k in range(3)]; L2 = sum(x*x for x in d) or 1e-12
                tt = max(0.0, min(1.0, sum((p[k]-b0[k])*d[k] for k in range(3))/L2)); q = [b0[k]+tt*d[k] for k in range(3)]
                best = min(best, math.dist(p, q))
            return best
        for g in EL['geometry']:
            if g['kind'] == 'seg': near.append((g['name'], segdist(route[0], route[1], g['p0'], g['p1'])-g['r']-R_sw))
            elif g['kind'] == 'poly':
                for j in range(len(g['points'])-1): near.append((g['name'], segdist(route[0], route[1], g['points'][j], g['points'][j+1])-g['r']-R_sw))
        for q in RD['loops']:
            if q['kind'] == 'seg': near.append((f'NaK U{q["unit"]} {q["leg"]}', segdist(route[0], route[1], q['p0'], q['p1'])-q['r']-R_sw))
            elif q['kind'] == 'poly':
                for j in range(len(q['points'])-1): near.append((f'NaK U{q["unit"]} {q["leg"]}', segdist(route[0], route[1], q['points'][j], q['points'][j+1])-q['r']-R_sw))
        for dc in fs.dry_containers(s)+LG4['module10']['containers']:
            if dc['x1'] < route[0][0] or dc['x0'] > route[1][0]: continue
            a = math.radians(dc['azimuth_deg']); er = (math.cos(a), math.sin(a)); et = (-er[1], er[0]); hw = dc['width']/2
            cs = [(er[0]*r_+et[0]*t_, er[1]*r_+et[1]*t_) for r_, t_ in ((dc['r0'], -hw), (dc['r1'], -hw), (dc['r1'], hw), (dc['r0'], hw))]
            dmin = min(fs._segdist2(ax, cs[i], cs[(i+1) % 4]) for i in range(4))
            near.append((dc['name'][:16], dmin-R_sw))
        for nm, a_ in LAY.items():
            if a_['shape'] == 'box' and a_['c'][0]-a_['d'][0]/2 < route[1][0] and a_['c'][0]+a_['d'][0]/2 > route[0][0] and nm != 'Workshop':
                dy = max(0.0, abs(a_['c'][1]-ax[0])-a_['d'][1]/2); dz = max(0.0, abs(a_['c'][2]-ax[1])-a_['d'][2]/2)
                near.append((nm, math.hypot(dy, dz)-R_sw))
        near.sort(key=lambda z: z[1]); return route, near
    flight = [i for i in items if i['handling'] == 'MRU carriage' and i['service'] != 'YARD']
    big_f = max(flight, key=lambda i: i['env']['D'])
    big = max((i for i in items if i['handling'] == 'MRU carriage' and 'shield' not in i['name'].lower() and 'mount' not in i['name'].lower()), key=lambda i: i['env']['D'])
    R_f = big_f['env']['D']/2+0.10; R_sw = big['env']['D']/2+0.10
    route_f, near_f = sweep(R_f, 2.9)
    route, near = sweep(R_sw, 3.6)
    yard_remove = sorted({n for n, d in near if d < 0.05})
    # rail: a single rail under the load (r 4.7) would sit 0.3 m under bus 3 (az 270, r 5.0): twin rails at az 270 +- 15 deg, r 4.6
    bus3 = pz(270.0, 5.0); single = math.dist(pz(270.0, 4.7), bus3)-0.25-0.09; twin = math.dist(pz(285.0, 4.6), bus3)-0.25-0.09
    rail = dict(single_rail_clear_to_bus3_m=single, twin_rail_clear_to_bus3_m=twin, layout='twin rails at az 255 and 285, r 4.6, 22 kg/m each',
                rail_t=2*22.0*c['rail_m']/1e3, supports=f'rail chairs every 2.0 m onto the body-bay ring frames and keel longerons (PSA), {int(c["rail_m"]/2.0)+1} per rail',
                chair_load_kN=(c['rating_t']+c['carriage_t'])*1e3*G0*A_PEAK_G/2/1e3)
    fixtures = [dict(id='MIF-A', name='heavy fixture adapter (reactor/IHX, TAC, gas ducts)', interface='four kinematic latch points (two cone, two flat) + two shear pins on the '
                     'equipment mount ring; the same pattern on the carriage cradle', mass_t=0.8),
                dict(id='MIF-B', name='ORU fixture (recuperator, gas cooler, cabinets)', interface='LOG-G1 grapple pattern (<= 3 t, robot)', mass_t=0.0),
                dict(id='MIF-C', name='module-10 container cradle', interface='dry-store rack rails, cargo restraint pins', mass_t=0.3)]
    sequence = ['shutdown, decay and radiation hold (weeks for the reactor/IHX: shutdown gamma, Phase III); crew outside line of sight',
                'carriage parks at the unit, cradle aligned by optical targets; equipment mount latches released one pair at a time while the cradle latches close '
                '(capture before release: the item is never free)', 'jacking rails slide the item from its mount onto the cradle (0.05 m/s)',
                'carriage moves at 5 cm/s on the twin rails, coast only; robot supervision from the hub consoles (data A/B), two independent brakes',
                'workshop transfer: cradle-to-stand latch exchange (capture before release)']
    burn = dict(rule=c['rule'], restraint='two park stations (district, workshop) with four shear-pin locks each; rated '
                f'{(c["rating_t"]+c["carriage_t"])*G0*A_PEAK_G*1.5:.0f} kN axial at 0.74 g x 1.5', mass_t=0.6)
    recovery = ['brake fault: the second brake holds; the carriage is winched to the nearest park station', 'latch fault: manual override from the cradle face (EVA-suited crew '
                'only after the radiation hold)', 'jammed load: the item is lashed in place and the ship flies with it restrained (no burn until locked)',
                'loss of supervision link: carriage stops (dead-man), restraint pins drop']
    decay = dict(unit_MWt=3.5/0.154, t_1h_W=3.5e6/0.154*0.066*(3600)**-0.2, t_1d_W=3.5e6/0.154*0.066*(86400)**-0.2, t_30d_W=3.5e6/0.154*0.066*(30*86400)**-0.2,
                 note='Way-Wigner decay heat (0.066 t^-0.2) on a long-run core: tens of kW after a month; the reactor/IHX needs active cooling during and after any move, '
                      'so its replacement is a yard operation')
    ext = dict(item='H6a EM pump modules (7.5 t, outside the hull at the aft manifold)', interface='EXT-TA: provisional external transfer arm on a short rail at the drive-bay '
               'hatch (two-joint luffing arm, 8 t at 6 m, PROTOTYPE, registered under FT-07)', mass_t=2.5,
               note='handled only in coast with the HOT loop drained at that section; the hatch is the existing drive-bay hatch (OPEN in production)')
    return dict(items=items, envelope_max=big, swept_radius_m=R_sw, route=route, nearest=near[:8], flight=dict(item=big_f['name'], swept_radius_m=R_f, route_r=2.9, route=route_f, nearest=near_f[:8], clear=near_f[0][1] > 0.05), yard=dict(item=big['name'], swept_radius_m=R_sw, route_r=3.6, remove_first=yard_remove,
                rule='the yard route for the reactor/IHX (and shield) runs on the lane centre r 3.6 after the sector-3 lane equipment listed is unbolted'), rail=rail, fixtures=fixtures, sequence=sequence, burn=burn,
                recovery=recovery, decay=decay, external=ext, rating_t=c['rating_t'], route_m=c['rail_m'],
                in_flight=[i['name'] for i in items if i['service'].startswith('IN-FLIGHT')], yard_items=[i['name'] for i in items if i['service'] == 'YARD'],
                claim='The carriage can move the reactor/IHX mass, but in-flight reactor servicing is NOT claimed: decay heat, activation and shutdown gamma make it a yard '
                      'operation; in flight the carriage serves the TAC (after a decay hold, restricted), and the ORU-class parts',
                mass_t=dict(fixtures=sum(f['mass_t'] for f in fixtures), second_rail=22.0*c['rail_m']/1e3, burn_restraint=burn['mass_t'], ext_arm=ext['mass_t']))


# ============================================================================================================ module 10 (6)
def module10(s):
    M = LG4['module10']; buf = [LAY[n] for n in sorted(LAY) if n.startswith('DefenseBuffer_')]; sh = M['defense_buffer_shift_m']
    # axial slide of the az-90 column forward (yard extraction direction): the shifted buffers sit in the same sector
    col = [cc for cc in M['containers'] if abs(cc['azimuth_deg']-90.0) < 1]
    hw = col[0]['width']/2; r0, r1 = col[0]['r0'], col[0]['r1']
    blocked = []
    for b in buf:
        y0, y1 = b['c'][1]-b['d'][1]/2, b['c'][1]+b['d'][1]/2; z0, z1 = b['c'][2]-b['d'][2]/2, b['c'][2]+b['d'][2]/2
        if y1 > -hw and y0 < hw and z1 > r0 and z0 < r1: blocked.append(dict(buffer=b['name'], x=(b['c'][0]-b['d'][0]/2+sh, b['c'][0]+b['d'][0]/2+sh)))
    std = [dict(interface='structural frame', what='two ring frames at the module ends (PSA), four rack longerons per sector; the module repeats the body-bay frame pitch '
                f'(module length {fs.cfg(s)["body"]["module_length_m"]} m)', owner='PSA (frames, longerons) / ISSA (rack brackets)'),
           dict(interface='equipment mounting', what='dry-store racks on the longerons, same rack as modules 1-9', owner='ISSA'),
           dict(interface='utilities', what='lighting, data A/B drops, 120 V service power from the sector bus; no fluids', owner='ISSA'),
           dict(interface='cargo restraints', what='rack rails + restraint pins rated for 0.74 g x 1.5 axial', owner='ISSA'),
           dict(interface='robotic handling', what='keel-lane manipulators (az 30/150/270) reach every container face', owner='ISSA'),
           dict(interface='maintenance access', what='keel lanes are the access aisles (item-level picking, soft bags <= 0.70 m)', owner='ISSA')]
    disp = PW['checks']['dry_store_displaced']
    return dict(x=M['x'], offset_m=M['offset_m'], containers=len(M['containers']), clearance_m=M['min_clear_m'], buffer_shift_m=sh,
                standard=std, removal=dict(in_flight='item-level: containers stay; goods leave through the keel lanes to the hub (LOG-G1 rule: no container crosses a '
                                                     'rotary seal)', yard_container='container-level exchange is a yard operation along the sector',
                                           yard_blocked_by=blocked,
                                           finding=(f'the az-90 column cannot slide forward out of module 10: the retained defense buffers ({len(blocked)}) occupy its '
                                                    'sector at r 3.1-4.5; the az-210/330 columns are clear. Yard extraction of the az-90 column goes aft '
                                                    'through modules 1-9 (empty them first) or the buffers are lowered to r 4.6-5.5 (option DR-C-05)')),
                ownership=dict(dry_store=f'{disp["containers"]} existing production containers ({disp["volume_m3"]:.0f} m3): MOVED, their mass stays in the historical '
                                         'dry mass and the mission payload', racks='4.0 t of new racks (ISSA, new)', frame='module 10 frames and longerons: PSA (OPEN)',
                               log_g1='LOG-G1 is a different system (8 x 3 t in the hub store, tare 4.81 t in the ledger): not duplicated'))


# ============================================================================================================ mass ledger (7.5, 10)
def ledger(s, rad, mr, cr):
    rows = []
    def add(item, t, cat, owner, cls, note=''):
        rows.append(dict(item=item, t=t, cat=cat, owner=owner, cls=cls, note=note))
    L2 = next(r for r in LD['items'] if r['item'].startswith('L2 (3 x'))
    restart = 3*next(p['module_t'] for p in PW['unit']['parts'] if p['key'] == 'restart')
    for r in LD['items']:
        it = r['item']; t = r['t']
        if it.startswith('L2 (3 x'):
            add(it+' (restart packs moved to the storage line)', t-restart, 'NEW', 'ISSA power', r['cls'], f'-{restart:.2f} t: the 3 restart packs were in both lines')
        elif it.startswith('cryocooler stations'):
            add('cryocooler stations (final T-A, increment over the existing coolers)', cr['mass_increment_t'], 'REPLACEMENT', 'ISSA cryo', 'NEW (PROTOTYPE)',
                f'new {cr["mass_new_t"]:.1f} t replaces the existing {cr["mass_existing_t"]:.1f} t (historical dry mass)')
        elif it.startswith('robots, crawlers, MRU'):
            add(it, t, 'NEW', 'ISSA MRO', r['cls'])
        elif it.startswith('bulkhead relocation'):
            add(it, t, 'HISTORICAL (moved)', 'ISSA thermal', r['cls'])
        elif it.startswith('LOG-G1 tare'):
            add(it, t, 'NEW', 'ISSA logistics', r['cls'], 'payload is mission payload, not dry mass')
        else:
            add(it, t, 'NEW', 'ISSA', r['cls'])
    add('HOT forward-pointing fin manifolds (DR-3D-04)', rad['mass_t']['fins'], 'NEW', 'ISSA thermal', 'FT-06 (APPROVED)')
    add('LOW forward tip extensions (3 blades)', rad['mass_t']['low_tabs'], 'NEW', 'ISSA thermal', 'NEW (PROTOTYPE)')
    add('WARM pump upgrade (451 K, +mass flow)', rad['mass_t']['warm_pump_upgrade'], 'NEW', 'ISSA thermal', 'NEW (PROTOTYPE)')
    add('MRU fixtures (MIF-A/C)', mr['mass_t']['fixtures'], 'NEW', 'ISSA MRO', 'FT-07 (APPROVED)')
    add('MRU second rail (twin rails clear of bus 3)', mr['mass_t']['second_rail'], 'NEW', 'ISSA MRO', 'FT-07 (APPROVED)')
    add('MRU burn restraints (two park stations)', mr['mass_t']['burn_restraint'], 'NEW', 'ISSA MRO', 'FT-07 (APPROVED)')
    add('EXT-TA external transfer arm (H6a EM pumps)', mr['mass_t']['ext_arm'], 'NEW', 'ISSA MRO', 'FT-07 (PROVISIONAL)')
    add('L1 conductors resized for the reactive peak', 0.0, 'NEW', 'ISSA electrical', 'within the 8 t distribution line', 'inside the existing line')
    dry = sum(r['t'] for r in rows)
    payload = [dict(item='ECLSS emergency CO2 reserve (LiOH, 30 d for 4 persons)', t=0.16, cat='MISSION PAYLOAD')]
    dry_with_payload = dry+sum(p['t'] for p in payload)
    m = mm.coupled_mission(s, CIRC+dry_with_payload*1e3)
    coolant = dict(NaK_t=RD['nak']['transport']['length_m']*3*math.pi*(RD['nak']['transport']['D_m']/2)**2*780/1e3,
                   note='NaK transport inventory (inside the loop line); Li of the H6a inside the 565 t H6a line; WARM water and LOW ammonia inside the production radiators')
    return dict(rows=rows, payload=payload, dry_added_t=dry, dry_with_payload_t=dry_with_payload, departure_t=m['departure_mass_kg']/1e3, propellant_t=m['propellant_kg']/1e3,
                tankage_t=m['added_tank_kg']/1e3, end_t=m['end_mass_kg']/1e3, coolant=coolant)


# ============================================================================================================ SSI handover (8)
def ssi(s, T, rad, mr, m10, cr):
    U = PW['unit']; items = []
    def it(id_, name, owner, mass_t, cg, env, mounts, loads, thermal, clear, removal, util, env_T, failure, cfg='F1', maturity='M2', register=''):
        items.append(dict(id=id_, name=name, owner=owner, config=cfg, maturity=maturity, register=register, mass_t=mass_t, cg=cg, envelope=env, mounts=mounts,
                          loads=loads, thermal_expansion=thermal, clearances=clear, removal=removal, utilities=util, environment=env_T, failure=failure))
    a = A_PEAK_G
    for d in PW['district']:
        m_u = sum(p['mass_t'] for p in U['parts'])
        it(f'PWR-L2U-{d["index"]}', f'L2 power unit {d["index"]} (az {d["azimuth_deg"]:.0f})', 'ISSA (machinery) / PSA (district frame)', m_u, d['centre'],
           dict(shape='unit envelope along x', x=(d['centre'][0]-1.0, d['centre'][0]+11.0), r=(0.0, 5.3), shield_cone_half_deg=12.5),
           [dict(id=f'U{d["index"]}-M{k}', type='anchor' if k == 1 else 'slide', x=d['centre'][0]+(0.0 if k == 1 else 6.0), az=d['azimuth_deg'], r=2.9,
                 dof='6-DOF' if k == 1 else 'radial + lateral (axial free)') for k in (1, 2)],
           dict(axial_kN=m_u*1e3*G0*a/1e3, lateral_kN=m_u*1e3*G0*0.05/1e3, stiffness='first mode > 15 Hz on its mount (PROTOTYPE target)',
                excitation=dict(TAC_rpm=(36000, 48000), TAC_Hz=(600, 800), imbalance='ISO 1940 G1.0 (gas bearings)', EM_pumps='no rotating parts; 50-400 Hz MHD ripple',
                                status='PROTOTYPE estimate')),
           'mount ring at the anchor; slide at the TAC end (unit grows ~12 mm hot)', 'district 1.4 m unit-to-unit, 1.29 m to the hull',
           dict(path='keel lane az 270 to the workshop (in flight r 2.9, yard r 3.6)', swept_radius_m=mr['swept_radius_m'], class_='MRU (reactor/IHX = yard)'),
           ['NaK supply/return to blades (2 loops)', 'HVDC feeder 3.5 MW', 'Li primary (H6a branch)', 'data A/B'], '1500 K inside the IHX; mount ring < 600 K',
           'one unit per failure domain; unit-to-unit 1.4 m; shadow-shield cone keeps crewed/cryogenic volume out', register='FT-03')
    S = H6['supports']
    it('TH-H6A-TRUNKS', 'H6a hot trunks (4 per blade) and saddles', 'ISSA (trunks, saddles, slides) / PSA (frames they bear on)', H6['mass_drawn_t'],
       (-40.0, 0.0, 0.0), dict(x=(H6['geometry']['x_hot0'], H6['geometry']['x_fwd']), r=(6.0, 8.2)),
       [dict(id=f'H6A-{az:.0f}-S{k}', type='anchor' if k % 4 == 2 else 'slide', x=H6['geometry']['x_hot0']+k*S['pitch_m'], az=az, r=H6['geometry']['r_trunk_axis'],
             dof='axial anchor' if k % 4 == 2 else 'radial/lateral') for az in (90.0, 210.0, 330.0) for k in range(int((H6['geometry']['x_fwd']-H6['geometry']['x_hot0'])/S['pitch_m'])+1)],
       dict(saddle_carried_t=S['saddle_carried_t'], anchor_axial_kN_per_saddle=S['anchor_axial_N_per_saddle']/1e3, a_peak_g=a),
       dict(growth_mm_per_m=S['growth_mm_per_m'], end_travel_mm=S['end_travel_mm']), 'hull 0.35 m', 'section replacement by MRU (sections 6 per blade)',
       ['Li branches to the L2 units', 'EM pump modules at the aft manifold'], '1840 K mean Li; saddles insulated', 'sectionalized: one section isolates', register='FT-01/FT-02')
    for az in (90.0, 210.0, 330.0):
        it(f'RAD-HOT-MAN-{az:.0f}', f'HOT forward-fin manifolds, blade {az:.0f}', 'ISSA', rad['fins']['extra_t']/3+0.0, (-46.0,)+pz(az, 22.0),
           dict(x=(H6['geometry']['x_hot0'], RD['section']['x0']), r=(6.5, 37.0), pitch_m=rad['fins']['pitch_m'], count=rad['fins']['manifolds_per_blade']),
           [dict(id=f'HOT-{az:.0f}-ROOT', type='slide', note='every manifold root on the trunk saddle line, radial slide; the blade root frame (PSA) carries the shear')],
           dict(burn_axial_note='fin and manifold inertia go to the blade root frames'), dict(growth='blade grows ~3 mm/m axially at 1800 K: root slides'), 'K-HOTVIEW',
           'manifold section with its trunk section', ['Li manifolds from H6a'], '1800 K', 'per-section isolation', register='FT-06')
        it(f'RAD-L2-{az:.0f}', f'L2 radiator section, blade {az:.0f}', 'ISSA', RD['mass']['gross_t']/3, (sum((RD['section']['x0'], RD['section']['x1']))/2,)+pz(az, 22.0),
           dict(x=(RD['section']['x0'], RD['section']['x1']), r=(6.5, 36.1)),
           [dict(id=f'L2-{az:.0f}-A', type='anchor', x=RD['section']['x0']), dict(id=f'L2-{az:.0f}-S', type='slide', x=RD['section']['x1'])],
           dict(axial_kN=RD['mass']['gross_t']/3*1e3*G0*a/1e3), dict(growth_mm=9.38*2.5), 'bulkhead 0.4 m', 'heat-pipe rows as ORUs', ['NaK headers A/B'], '896 K',
           'header A/B cross-strap')
        it(f'RAD-LOWTAB-{az:.0f}', f'LOW forward tip extension, blade {az:.0f}', 'ISSA (panel, spar) / PSA (root frame lugs)', rad['mass_t']['low_tabs']/3,
           (sum(rad['preferred']['low_tab_x'])/2,)+pz(az, 34.25), dict(x=rad['preferred']['low_tab_x'], r=rad['preferred']['low_tab_r']),
           [dict(id=f'LT-{az:.0f}-C{k}', type='clevis', x=93.4, r=31.5+k*5.5) for k in (0, 1)],
           dict(axial_kN=rad['mass_t']['low_tabs']/3*1e3*G0*a/1e3), dict(growth='300 K, none'), f'{rad["preferred"]["clear_to_ring_m"]:.1f} m to the ring rim (r 30)',
           'panel swap at a yard', ['ammonia A/B from the LOW header'], '300 K', 'A/B interleave', maturity='M2')
    for v in T['vessels']:
        it(f'FARM-{v["id"]}', f'Propellant vessel {v["id"]} ({v["species"]})', 'ISSA (vessel, contents) / PSA (deck, hoop, keel)', v['prop_t'], ((v['x0']+v['x1'])/2,)+pz(v['az'], v['R']),
           dict(x=(v['x0'], v['x1']), R=v['R'], a=v['a']), [dict(id=f'{v["id"]}-SKIRT', type='anchor', x=v['x0'], note='aft skirt on the thrust deck'),
                                                            dict(id=f'{v["id"]}-GUIDE', type='slide', x=v['x1'], note='forward guide on the hoop, axial slide')],
           dict(axial_kN=v['axial_kN']), dict(contraction_mm=fuel_loads.q(s)['thermal_contraction']*(v['x1']-v['x0'])*1e3), 'gap rule 1.0 m', 'yard', ['outlet', 'cryocooler station'],
           '20 K / 3 K', 'per-species isolation', maturity='M2')
    it('BROW-TRANSLATION', 'Brow, EYE and forward assembly (translated)', 'PSA (structure) / ISSA (interfaces)', None, (sum(T['brow_x'])/2, 0.0, 0.0),
       dict(x=T['brow_x'], r=(0.0, 45.0), translation_m=T['added_length_m']), [dict(id='BROW-HOOP', type='anchor', x=T['brow_x'][0])], {}, {}, 'K-BROW', 'n/a', ['EYE power', 'data'],
       'shield', 'n/a', maturity='M1')
    c = LG4['carriage']
    it('MRU-RAIL', 'MRU heavy-carriage twin rails and park stations', 'ISSA (rails, chairs, locks) / PSA (frames, longerons)', mr['rail']['rail_t']+mr['burn']['mass_t'],
       ((c['x'][0]+c['x'][1])/2,)+pz(270.0, 4.6), dict(x=c['x'], az=(255.0, 285.0), r=4.6),
       [dict(id='MRU-CHAIRS', type='slide', pitch_m=2.0, note='rail chairs on frames; rail joints slide'), dict(id='MRU-PARK-D', type='anchor', x=c['x'][0]+2.0),
        dict(id='MRU-PARK-W', type='anchor', x=c['x'][1]-2.0)], dict(chair_kN=mr['rail']['chair_load_kN'], park_lock_kN=(c['rating_t']+c['carriage_t'])*G0*a*1.5),
       dict(growth='casing temperature, joints every 12 m'), f'in-flight swept radius {mr["flight"]["swept_radius_m"]:.2f} m at r 2.9: nearest {mr["flight"]["nearest"][0][0]} {mr["flight"]["nearest"][0][1]:.2f} m',
       'n/a', ['carriage power 20 kW from sector 3', 'data A/B'], 'casing interior 250-320 K', 'dead-man stop, pins drop')
    M = LG4['module10']
    it('BODY-M10', 'Body-bay module 10 (relocated dry store)', 'PSA (frames, longerons) / ISSA (racks, restraints)', 4.0, (sum(M['x'])/2, 0.0, 0.0), dict(x=M['x'], r=(1.5, 4.3)),
       [dict(id='M10-F0', type='frame', x=M['x'][0]), dict(id='M10-F1', type='frame', x=M['x'][1])], dict(rack_axial_kN=6*44.8*0.35*G0*a),
       {}, f'{M["min_clear_m"]:.2f} m to data/buses', 'item-level in flight; container-level yard', ['lighting', 'data', 'service power'], 'casing interior',
       'n/a')
    it('HUB-ECLSS', 'Stationary hub ECLSS unit and both rotary interfaces', 'ISSA (unit, ducts) / PSA (hub frame, bearings)', EC['unit']['mass_t'], EC['hub']['c'],
       dict(box=EC['hub']['env']), [dict(id='HUB-ECL-4', type='4-point', note='frame posts on the hub deck')], dict(axial_kN=EC['unit']['mass_t']*1e3*G0*a/1e3),
       {}, 'maintenance face 1.0 m', 'ORU (<= 0.70 m)', ['air ducts D 0.28 m to couplings A/B', 'water', 'O2/N2', 'data A/B'], 'cabin', 'hub unit fails: rings carry 6+6')
    for nm in ('RotaryCoupling_A', 'RotaryCoupling_B'):
        a_ = LAY[nm]
        it(f'HUB-{nm.upper()}', f'{nm.replace("_", " ")} (rotating habitat interface)', 'PSA (bearing, drum) / ISSA (air, power, data passes)', None, a_['c'],
           dict(ring=a_['d']), [dict(id=f'{nm}-BRG', type='bearing', note='PSA')], {}, {}, 'transfer drum r 1.3-1.5', 'yard', ['air duct', 'power slip rings', 'data'],
           'cabin', 'seal leak 0.05-1.0 kg/d', maturity='M1')
    for q in cr_stations(T):
        it(f'CRYO-{q["tank"]}', f'Cryocooler station {q["tank"]}', 'ISSA', cr['mass_new_t']/len(T['vessels']), q['c'], dict(box=(1.6, 1.8, 1.8)),
           [dict(id=f'CRYO-{q["tank"]}-B', type='4-point', note='bracket on the vessel forward guide ring')], {}, {}, '0.4 m', 'ORU heads', ['L2 power', 'LOW ammonia'],
           '300 K warm end', 'two heads per station')
    return dict(version=SSI_VERSION, config=CONFIG, created='2026-11-28', frame='ship axes: +X bow, az from +Y toward +Z, metres, tonnes, kN',
                ownership_rule='ISSA owns machinery, its supports (saddles, slides, rack brackets, rail chairs) and utilities; PSA owns primary load-bearing structure '
                               '(frames, longerons, decks, hoops, bearings) and the loads they carry; a mount id is the boundary between them',
                load_cases=dict(burn_axial_g=a, burn_lateral_g=0.05, coast='0 g + spin interfaces', notes='operating values, not limit loads: PSA applies its factors'),
                items=items,
                disagreements=[dict(id='SSI-D1', topic='farm extension', issa=f'T-A +{T["added_length_m"]:.2f} m (current inventory)', psa='PSA Phase I worked with +18.2 m (CP1)',
                                    action='PSA to adopt the new value; no silent override'),
                               dict(id='SSI-D2', topic='propellant densification', issa='not adopted (owner)', psa='PSA prefers densify (T-C) for structure',
                                    action='owner decision stays T-A; T-C kept as research option'),
                               dict(id='SSI-D3', topic='L2 frame station', issa=f'L2 section x {RD["section"]["x0"]:.2f}-{RD["section"]["x1"]:.1f}', psa='frame ~40.8',
                                    action='PSA to place the frame at x 41.0 (aft edge of the L2 section) or report the conflict')])


def finalize_cryo(C, pr):
    lift = sum(st['lift_W'] for st in C['stages']); inp = pr['cryo_input_at_T_W']
    for st in C['stages']:
        st['input_at_T_W'] = st['lift_W']*st['W_per_W']*(pr['T_low_K']-st['T_cold'])/(300.0-st['T_cold'])
    C.update(T_reject_K=pr['T_low_K'], input_at_300K_W=C['operating_input_W'], operating_input_W=inp, installed_input_W=inp*1.25, reject_operating_W=inp+lift,
             reject_installed_W=(inp+lift)*1.25, mass_new_t=inp*1.25/1e3*0.012)
    C['mass_increment_t'] = C['mass_new_t']-C['mass_existing_t']
    C['flows'] = [('electrical input (L2 bus)', inp), ('heat lifted from the 3 K and 20 K stages', lift), (f'heat rejected to LOW at {pr["T_low_K"]:.0f} K (input + lift)', -(inp+lift))]
    C['explain'] = (f'CP4 quoted {RM["cryo"]["input_W"]/1e3:.0f} kW = the INSTALLED input (operating x 1.25) and {RM["cryo"]["low"]["cryo_reject_W"]/1e3:.0f} kW '
                    'for LOW, which mixed the scaled production rejection with installed nuclear terms: two bases, not a lost energy flow. Now every watt has one '
                    f'destination: {inp/1e3:.0f} kW of operating input from the L2 bus plus {lift:.0f} W lifted from the cold stages leave as {(inp+lift)/1e3:.0f} kW into '
                    f'LOW at {pr["T_low_K"]:.0f} K (the input is {100*(inp/C["input_at_300K_W"]-1):.0f} % above the 300 K value because the coolers reject warmer). '
                    f'At full installed capacity (re-cool after a fault) LOW sees {(inp+lift)*1.25/1e3:.0f} kW for hours, inside its 20 % margin.')


def cr_stations(T):
    out = []
    for v in T['vessels']:
        out.append(dict(tank=v['id'], c=(v['x1']+1.0,)+pz(v['az'], v['R'])))
    return out


# ============================================================================================================ drawings: sections
def svg_long(T, rad, mr, path):
    w, h = 1100, 420; sx = 2.55; X = lambda x: 40+(x+150)*sx; Y = lambda r: 210-r*4.2
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="Inter,system-ui,sans-serif" font-size="11" role="img" aria-label="Longitudinal section">',
         '<style>.t{fill:var(--fg,#223)} .m{fill:var(--muted,#667)}</style>',
         '<text x="14" y="18" class="t" font-weight="600">Longitudinal section, WF-F1-C1.0 (upper half: blade plane az 90; radius in m, x in m)</text>']
    zones = [(-144.75, -133.25, 0, 12, '#d23a6a', 'drive'), (-133.25, RD['section']['x0'], 6.5, 37, '#e0553a', 'HOT (forward fins, 1.47 m pitch)'),
             (RD['section']['x0'], RD['section']['x1'], 6.5, 36.1, '#c9852a', 'L2 896 K'), (50.4, 72.9, 6.5, 37, '#d9a43a', 'WARM 451 K'),
             (73.4, 93.4, 6.5, 37, '#3a8fd0', 'LOW'), (rad['preferred']['low_tab_x'][0], rad['preferred']['low_tab_x'][1], 31.5, 37, '#3a8fd0', 'LOW tabs'),
             (95.15, 99.45, 0, 30, '#2fa36b', 'ring A'), (101.15, 105.45, 0, 30, '#2fa36b', 'ring B'), (T['farm_x'][0], T['farm_x'][1], 7.75, 34.5, '#8a6fd8', 'farm T-A'),
             (T['brow_x'][0], T['brow_x'][1], 0, 45, '#777', 'Brow'), (-93.5, -77.5, 0.5, 5.3, '#e07b3a', 'L2 district'), (-89.75, 21.25, 1.5, 4.3, '#5aa0b8', 'body bay'),
             (LG4['module10']['x'][0], LG4['module10']['x'][1], 1.5, 4.3, '#3a6fd0', 'module 10')]
    for x0, x1, r0, r1, col, lab in zones:
        o.append(f'<rect x="{X(x0):.1f}" y="{Y(r1):.1f}" width="{(x1-x0)*sx:.1f}" height="{(r1-r0)*4.2:.1f}" fill="{col}" fill-opacity="0.28" stroke="{col}"/>')
    labs = [(-138, 14, 'drive'), (-60, 39, 'HOT'), (RD['section']['x0']-2, 41, 'L2'), (56, 41, 'WARM'), (78, 41, 'LOW'), (95, 41, 'tabs'), (95.5, 33, 'rings'),
            (115, 37, 'farm (T-A)'), (T['brow_x'][0]-6, 48, 'Brow'), (-95, -1.5, 'district'), (-40, -1.5, 'body bay'), (20, -1.5, 'M10')]
    for x, r, t in labs: o.append(f'<text x="{X(x):.0f}" y="{Y(r):.0f}" class="t" font-size="10">{t}</text>')
    c = LG4['carriage']; o.append(f'<line x1="{X(c["x"][0]):.0f}" y1="{Y(-3.6)+0:.0f}" x2="{X(c["x"][1]):.0f}" y2="{Y(-3.6):.0f}" stroke="#c9852a" stroke-width="3"/>')
    o.append(f'<text x="{X(-20):.0f}" y="{Y(-3.6)+14:.0f}" class="m" font-size="10">MRU twin rails (az 270, shown below the axis)</text>')
    o.append(f'<line x1="{X(-150):.0f}" y1="{Y(0):.0f}" x2="{X(T["brow_x"][1]+2):.0f}" y2="{Y(0):.0f}" stroke="#999" stroke-dasharray="4 3"/>')
    for x in range(-140, 181, 20): o.append(f'<text x="{X(x)-8:.0f}" y="{h-30}" class="m" font-size="10">{x}</text>')
    o.append(f'<text x="14" y="{h-10}" class="m">Ship {T["ship_length_m"]:.1f} m (farm +{T["added_length_m"]:.2f} m, Brow x {T["brow_x"][0]:.1f}); keep-outs: ring sweep x 93.65-106.95 r &lt; 31.5; Brow shadow r &lt; 37.</text>')
    o.append('</svg>'); path.write_text('\n'.join(o))


def svg_trans(T, mr, path):
    stations = [('x -84: L2 district', -84.0), ('x 28: module 10', 28.0), ('x 60: WARM', 60.0), ('x 125: farm', 125.0)]
    w, h = 1100, 330; o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="Inter,system-ui,sans-serif" font-size="11" role="img" aria-label="Transverse sections">',
                           '<style>.t{fill:var(--fg,#223)} .m{fill:var(--muted,#667)}</style>',
                           '<text x="14" y="18" class="t" font-weight="600">Transverse sections looking forward (y right, z up; casing r 6, blades at 90/210/330)</text>']
    for k, (lab, x) in enumerate(stations):
        cx, cy = 140+k*270, 175; sc = 12.5 if x < 100 else 3.6
        P = lambda y, z: (cx+y*sc, cy-z*sc)
        o.append(f'<text x="{cx-110}" y="45" class="t">{lab}</text>')
        if x < 100:
            o.append(f'<circle cx="{cx}" cy="{cy}" r="{6.0*sc:.0f}" fill="none" stroke="#999"/>')
            for az in (90.0, 210.0, 330.0):
                a = P(*pz(az, 6.5)); b = P(*pz(az, 9.5)); o.append(f'<line x1="{a[0]:.0f}" y1="{a[1]:.0f}" x2="{b[0]:.0f}" y2="{b[1]:.0f}" stroke="#e0553a" stroke-width="3"/>')
            for i in range(3):
                bp = P(*pz((30.0, 150.0, 270.0)[i], 5.0)); o.append(f'<circle cx="{bp[0]:.0f}" cy="{bp[1]:.0f}" r="{0.25*sc:.1f}" fill="#3a8fd0"/>')
            for yy in (4.6, -4.6):
                dp = P(yy, 0.0); o.append(f'<circle cx="{dp[0]:.0f}" cy="{dp[1]:.0f}" r="3" fill="#2fa36b"/>')
            for az in (255.0, 285.0):
                rp = P(*pz(az, 4.6)); o.append(f'<rect x="{rp[0]-3:.0f}" y="{rp[1]-3:.0f}" width="6" height="6" fill="#c9852a"/>')
            sw = P(*pz(270.0, 3.6)); o.append(f'<circle cx="{sw[0]:.0f}" cy="{sw[1]:.0f}" r="{mr["swept_radius_m"]*sc:.0f}" fill="none" stroke="#c9852a" stroke-dasharray="3 2"/>')
            if -93.5 <= x <= -77.5:
                for d in PW['district']:
                    q = P(d['centre'][1], d['centre'][2]); o.append(f'<circle cx="{q[0]:.0f}" cy="{q[1]:.0f}" r="{0.8*sc:.0f}" fill="#e07b3a" fill-opacity="0.5"/>')
            if -89.75 <= x <= 33.25:
                for az in (90.0, 210.0, 330.0):
                    er = (math.cos(math.radians(az)), math.sin(math.radians(az))); et = (-er[1], er[0])
                    pts = [P(er[0]*r_+et[0]*t_, er[1]*r_+et[1]*t_) for r_, t_ in ((1.5, -1.4), (4.3, -1.4), (4.3, 1.4), (1.5, 1.4))]
                    o.append('<polygon points="' + ' '.join(f'{p[0]:.0f},{p[1]:.0f}' for p in pts) + '" fill="#5aa0b8" fill-opacity="0.35" stroke="#5aa0b8"/>')
            if 33.6 <= x <= 46.0:
                pass
            for az in (10.0, 50.0, 130.0, 170.0, 250.0, 290.0):
                q = P(*pz(az, 5.8)); o.append(f'<circle cx="{q[0]:.0f}" cy="{q[1]:.0f}" r="{0.11*sc:.1f}" fill="#f08a2a"/>')
        else:
            for v in T['vessels']:
                q = P(*pz(v['az'], v['R'])); o.append(f'<circle cx="{q[0]:.0f}" cy="{q[1]:.0f}" r="{v["a"]*sc:.0f}" fill="#8a6fd8" fill-opacity="0.3" stroke="#8a6fd8"/>')
            o.append(f'<circle cx="{cx}" cy="{cy}" r="{45*sc:.0f}" fill="none" stroke="#999" stroke-dasharray="4 3"/>')
    o.append(f'<text x="14" y="{h-12}" class="m">Red: blade roots; blue dots: sector buses r 5; green: data A/B; orange: NaK loops r 5.8; amber squares: MRU twin rails; dashed amber: swept '
             f'tube of the largest MRU item (r {mr["swept_radius_m"]:.2f} m); teal: dry store; violet: farm vessels.</text>')
    o.append('</svg>'); path.write_text('\n'.join(o))


# ============================================================================================================ main
def main():
    s = spec.load()[0]
    E6 = P6['reconciliation']['electrical']; hp = E6['heat_pump']
    # iterate: dry mass -> propellant -> tank geometry -> cryo -> radiators -> dry mass
    prop = LD['propellant_t']; react0 = E6['sum_R']['continuous_reactive_W']-hp['proactive_W']
    for _ in range(6):
        T = tanks(s, prop); C = cryo(s, T['shell_area_m2']); RAD = radiators(C, react0); MR = mru(s); finalize_cryo(C, RAD['preferred'])
        LGR = ledger(s, RAD, MR, C)
        if abs(LGR['propellant_t']-prop) < 0.05: break
        prop = LGR['propellant_t']
    EL7 = electrical(C, hp['proactive_W']); L2F = l2_failure(); ECL = eclss(); M10 = module10(s)
    SSI = ssi(s, T, RAD, MR, M10, C)
    cp4 = dict(departure_t=LD['departure_t'], propellant_t=LD['propellant_t'], dry_added_t=LD['dry_added_t'], tankage_t=LD['tankage_t'],
               ship_length_m=TK['alternatives'][0]['ship_length_m'], farm_added_m=TK['alternatives'][0]['added_length_m'])
    reg = [('PWR-L2U', 'M3', 'M3'), ('PWR-DIST', 'M2', 'M2'), ('TH-H6A', 'M2', 'M2'), ('TH-H6A-AFT', 'M3', 'M3'), ('RAD-HOT', 'M2', 'M2 (forward fins drawn)'),
           ('RAD-L2', 'M3', 'M3'), ('RAD-WL', 'M2', 'M2 (451 K WARM, LOW tabs drawn)'), ('EPS-L1', 'M2', 'M2 (peak-rated)'), ('EPS-BUS', 'M2', 'M2'), ('EPS-STOR', 'M2', 'M2'),
           ('ECLSS-RING', 'M2', 'M2'), ('ECLSS-HUB', 'M3', 'M3'), ('LOG-G1', 'M3', 'M3'), ('MRO-WS', 'M2', 'M2'), ('MRO-ROB', 'M2', 'M2 (MRU architecture, EXT-TA)'),
           ('PROP-FARM', 'M2', 'M2 (final T-A)'), ('PROP-CRYO', 'M2', 'M2 (final T-A)'), ('GNC-CDH', 'M1', 'M1'), ('STRUCT-F1', 'M2', 'M2 (interfaces to PSA)')]
    problems = [dict(id='C-01', sev='OPEN', what='L1 pickup fault in a burn forces a controlled drive shutdown (H6a pumps exceed the L2 surplus)', owner='owner / Track R'),
                dict(id='C-02', sev='OPEN', what='WARM machinery at 451 K: power electronics on the WARM loop need ~200 C junction parts (SiC/GaN class)', owner='ISSA (next detail)'),
                dict(id='C-03', sev='OPEN', what='az-90 dry-store column cannot slide forward past the retained defense buffers (yard extraction aft or DR-C-05)', owner='owner'),
                dict(id='C-04', sev='OPEN', what='primary structure mass, frames and limit loads: PSA (not in this ledger)', owner='PSA'),
                dict(id='C-05', sev='OPEN', what='shielding: the OpenMC surrogate gives a sensitivity only; no crew dose or shielding approval', owner='Track R'),
                dict(id='C-06', sev='OPEN', what='EXT-TA external arm and the drive-bay hatch are provisional (FT-07 register note)', owner='owner'),
                dict(id='C-07', sev='MITIGATED', what='NaK loop loss: safe degraded state at ~7 MWe, highest demand band sheds 1.2 MW', owner='ISSA'),
                dict(id='C-08', sev='MITIGATED', what='ECLSS compound case (ring A + B unit + hub unit): 30-day CO2 reserve, no eighth unit', owner='ISSA'),
                dict(id='C-09', sev='OPEN', what='TAC / EM-pump excitation bands are PROTOTYPE estimates for PSA modal work', owner='ISSA/PSA'),
                dict(id='C-10', sev='CLOSED', what='restart packs were counted in both the L2 and the storage lines (-6.45 t)', owner='ISSA')]
    readiness = [dict(area='geometry (fictional development model)', state='READY for coordinated integration', note='all 19 systems at target maturity; review file regenerated'),
                 dict(area='mass', state='READY (ISSA side)', note='one owner per item; structure and shielding OPEN'),
                 dict(area='structure', state='WAITING on PSA Phase II', note='SSI-1.0 handed over; reactions and stiffness come back from PSA'),
                 dict(area='thermal', state='READY with C-02', note='every zone closes; HOT reserve positive at the reactive peak'),
                 dict(area='electrical', state='READY with C-01', note='peak-rated L1; pickup-fault doctrine stated'),
                 dict(area='canon / Drive', state='NOT STARTED (not authorized)', note='nothing written to Drive; production ship unchanged'),
                 dict(area='production generators', state='NOT STARTED', note='integration into src/ after owner review and PSA Phase II')]
    owner_q = [dict(id='DR-C-01', q='Accept WARM at 451 K (temperature redistribution) instead of new WARM area?', rec='yes: the only closure that keeps HOT at the reactive peak'),
               dict(id='DR-C-02', q='Accept the LOW forward tip extensions beside the rings (r 31.5-37)?', rec='yes'),
               dict(id='DR-C-03', q='Accept the pickup-fault doctrine (controlled drive shutdown)?', rec='yes for F1; Track R keeps it OPEN'),
               dict(id='DR-C-04', q='Register EXT-TA as a provisional FT-07 item?', rec='yes'),
               dict(id='DR-C-05', q='Lower the defense buffers to r 4.6-5.5 so the az-90 dry-store column can slide forward?', rec='yes, at the next detail pass')]
    out = dict(status=f'STUDY / PROTOTYPE, Track F1 working configuration {CONFIG}; noncanon; production unchanged', config=CONFIG,
               decisions=[dict(id='DR-3D-01', what='T-A reference, resized to the current inventory', state='IMPLEMENTED'),
                          dict(id='DR-3D-02', what='FT-03 component set (0.94 / 0.90 / 0.97 / 2 %), 896 K L2, 9.38 m', state='IMPLEMENTED (register)'),
                          dict(id='DR-3D-03', what='forward L2 kept; aft placement a research alternative', state='IMPLEMENTED'),
                          dict(id='DR-3D-04', what='forward-pointing HOT fins, 1.47 m manifold pitch', state='IMPLEMENTED (geometry, ledger, register)'),
                          dict(id='CP4-WL', what='WARM/LOW closure', state='IMPLEMENTED (preferred O5)'),
                          dict(id='CP4-MRU', what='heavy MRU transport architecture', state='IMPLEMENTED (M2)'),
                          dict(id='CP4-M10', what='body-bay module 10', state='IMPLEMENTED (interfaces; az-90 yard route finding)')],
               tanks=T, radiators=RAD, cryo=C, electrical=EL7, l2_failure=L2F, eclss=ECL, mru=MR, module10=M10, ledger=LGR, cp4=cp4, registry=reg,
               problems=problems, readiness=readiness, owner_questions=owner_q)
    (R/'i3d_consolidated.json').write_text(json.dumps(out, indent=1, default=str)); (R/'i3d_structure_interface.json').write_text(json.dumps(SSI, indent=1, default=str))
    svg_long(T, RAD, MR, R/'i3d_c_longitudinal.svg'); svg_trans(T, MR, R/'i3d_c_transverse.svg')
    print(f'propellant {LGR["propellant_t"]:.0f} t, dry {LGR["dry_added_t"]:.1f} t, departure {LGR["departure_t"]:.0f} t (CP4 {LD["departure_t"]:.0f}), farm +{T["added_length_m"]:.2f} m '
          f'(CP1 {T["cp1_added_length_m"]:.2f}), ship {T["ship_length_m"]:.1f} m')
    pr = RAD['preferred']
    print(f'cryo op input {C["operating_input_W"]/1e3:.0f} kW, reject {C["reject_operating_W"]/1e3:.0f} kW; LOW short {RAD["need"]["low_short_W"]/1e3:.0f} kW -> tabs '
          f'{pr["low_tab_length_m"]:.1f} m (alone {pr["tabs_needed_alone_m"]:.1f}) + LOW {pr["T_low_K"]:.1f} K (input {pr["cryo_input_at_T_W"]/1e3:.0f} kW); WARM {pr["T_warm_K"]:.1f} K')
    print(f'HOT reserve nominal {RAD["budget"]["reserve_nominal_W"]/1e9:.3f} GW, reactive {RAD["budget"]["reserve_reactive_W"]/1e9:.3f} GW; O1 after {RAD["options"][0]["reserve_reactive_after_W"]/1e9:.3f}')
    print(f'L1 cont {EL7["continuous_W"]/1e6:.2f} MW, reactive {EL7["reactive_W"]/1e6:.2f} MW, conductor {EL7["conductor"]["A_peak_mm2"]:.0f} mm2 {EL7["conductor"]["mass_new_t"]:.2f} t')
    print(f'L2 failure: {L2F["derating"]}; t+50K {L2F["transient"]["t_to_plus50K_s"]:.0f} s; shed {L2F["shed_W"]/1e6:.2f} MW')
    print('MRU flight', [(n, round(d, 2)) for n, d in MR['flight']['nearest'][:4]], 'yard remove', MR['yard']['remove_first'], 'rails', round(MR['rail']['single_rail_clear_to_bus3_m'], 2), round(MR['rail']['twin_rail_clear_to_bus3_m'], 2))
    print('M10', M10['removal']['finding']); print('SSI items', len(SSI['items']))


if __name__ == '__main__':
    main()
