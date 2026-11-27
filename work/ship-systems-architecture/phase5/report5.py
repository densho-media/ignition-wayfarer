"""ISSA Phase V page sections (deliverables 1-17 + dual baseline), inserted above Phase IV into results/issa.html by build_report.py.
Reads results/phase5.json and results/phase5_config.json. Pure Python, inline SVG with the page's theme tokens."""
import html
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]/'results'
for p in ('phase2', 'phase3', 'phase4'):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/p))
from report2 import table, bars, section  # noqa: E402
from report3 import ok  # noqa: E402
from report4 import fig, txt, MONO  # noqa: E402

E = html.escape


def t3(v, d=0, k=1.0):
    return f'{v[0]/k:,.{d}f}–{v[2]/k:,.{d}f} <span class="nom">({v[1]/k:,.{d}f})</span>'


def img(name, alt, cap):
    return (f'<figure><img src="{name}.jpg" alt="{E(alt)}" loading="lazy" style="width:100%;border-radius:6px">'
            f'<figcaption class="fn">{cap}</figcaption></figure>') if (R/f'{name}.jpg').exists() else ''


def fig_profile(H):
    w, h = 760, 250; s = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Coolant and surface temperature along the radiating path">']
    sx = lambda a: 60+a*(w-120); sy = lambda T: h-30-(T-1500)/(2150-1500)*(h-60)
    tones = ('info', 'action', 'warn')
    for k, (name, prof) in enumerate(H['profiles'].items()):
        pts = ' '.join(f'{sx(p["area_frac"]):.0f},{sy(p["T_coolant"]):.0f}' for p in prof)
        pts2 = ' '.join(f'{sx(p["area_frac"]):.0f},{sy(p["T_surface"]):.0f}' for p in prof)
        s.append(f'<polyline points="{pts}" style="fill:none;stroke:var(--{tones[k]});stroke-width:2.5"/>')
        s.append(f'<polyline points="{pts2}" style="fill:none;stroke:var(--{tones[k]});stroke-width:1.5;stroke-dasharray:5 4"/>')
        s.append(txt(w-55, sy(prof[-1]['T_coolant'])-4-14*k, name, 'end', MONO, tones[k]))
    s.append(f'<line x1="60" y1="{sy(1800):.0f}" x2="{w-60}" y2="{sy(1800):.0f}" style="stroke:var(--muted);stroke-dasharray:2 3"/>')
    s.append(txt(64, sy(1800)-5, '1800 K uniform-surface basis', st=MONO, fill='muted'))
    for T in (1600, 1800, 2000):
        s.append(txt(54, sy(T)+4, str(T), 'end', MONO, 'muted'))
    s.append(txt(60, h-8, 'fraction of radiating area along the flow path →  (solid: coolant, dashed: surface)', st=MONO, fill='muted'))
    s.append('</svg>')
    return fig(''.join(s), 'Radiation-limited cooling along each radiating path: the coolant must enter well above 1800 K for the area to emit as '
               'much as a uniform 1800 K surface, and the surface falls below it toward the outlet.')


def fig_lscan(Rd):
    items = [(f'{x["T_K"]:.0f} K dedicated', (x['L_dedicated_m'],)*3, 'bad' if not x['fits_hot_rule_dedicated'] else 'good') for x in Rd['l2_scan']] + \
            [(f'{x["T_K"]:.0f} K cross-strapped', (x['L_cross_m'],)*3, 'bad' if not x['fits_hot_rule_cross'] else 'good') for x in Rd['l2_scan']]
    return bars(items, 'L2 section length on the hot blades, m') + f'<p class="fn">The 20 % HOT rule leaves {Rd["hot_free_m"]:.1f} m; green fits.</p>'


def build():
    P = json.loads((R/'phase5.json').read_text()); CF = json.loads((R/'phase5_config.json').read_text())
    H, Rd, L, D, M, Mf, EC, LG, AL, MS, CV = (P[k] for k in ('transport', 'radiators', 'ledgers', 'electrical', 'mass', 'mass_fictional', 'eclss',
                                                             'logistics', 'allocation', 'missions', 'convergence'))
    T = H['topologies']; RAD = P['radiation']; cid = f'<span class="chip c-sim">config {E(CF["id"])} · {E(CF["hash"])}</span>'
    out = []
    # 1 corrections
    rows = [[E(r['id']), E(r['item']), E(r['phase4']), E(r['cause']), E(r['phase5'])] for r in P['corrections']]
    g = CF['generation']['L2']; rad = CF['radiators']
    cfg_rows = [['L2', f'{g["units"]} × {g["rating_We"]/1e6:.1f} MWe, {E(g["strategy_operating"])}; maintenance {E(g["strategy_maintenance"])}; EOL {g["EOL_factor"]}'],
                ['Rejection', f'L2 {rad["L2"]["T_K"]:.0f} K on {rad["L2"]["length_m"]:.0f} m (Phase IV); HOT {rad["hot"]["T_K"]:.0f} K, ideal {rad["hot"]["ideal_W"]/1e9:.1f} GW, rule ×{rad["hot"]["margin_rule"]}'],
                ['Hot loop', E(CF['hot_loop']['reference'])], ['Storage', E('; '.join(f'{k}: {v}' for k, v in CF['storage'].items()))],
                ['Failure domains', E(', '.join(CF['failure_domains']))], ['Mission', E(CF['mission_loading']['standard'])],
                ['Mass base', f'historical {CF["mass_base"]["historical_departure_t"]:,.0f} t → coupled {CF["mass_base"]["coupled_departure_t"]:,.1f} t (CIRC-001 {CF["mass_base"]["CIRC001_t"]:.1f} t)']]
    out.append(section('v1', 'DELIVERABLE 1', 'Correction and reconciliation',
        f'<p>{cid} Phase V fixes one machine-readable configuration (<code>results/phase5_config.json</code>); every integrated Phase V result names it '
        'and nothing mixes phases. Cases are <b>correlated sensitivity cases</b> (opt / nom / cons: every uncertain input moved together), not '
        'statistical bounds.</p>'+table(['Field', 'N2-R4a-P5.0'], cfg_rows)+table(['ID', 'Item', 'Phase IV', 'Cause', 'Phase V'], rows)))
    # 2 H6
    keys = ['H1', 'H2', 'H3', 'H5', 'H6a', 'H6b', 'H6c', 'H6d', 'H6e', 'H6f']
    items_ = ['coolant', 'trunk_walls', 'manifold_walls', 'valves', 'bellows', 'section_hx', 'supports', 'accumulators', 'heat_pipe_fins', 'pumps', 'recovery', 'maintenance']
    crow = [[f'<b>{k}</b> {E(T[k]["name"][len(k)+1:])}', t3(T[k]['total_t']), t3(T[k]['pump_MW'], 1), f'{T[k]["inventory_t"][1]:,.0f}',
             str(T[k]['sections']), str(T[k]['paths']), E(T[k]['maturity']), ok(not T[k]['wall_limit'][1], 'within', 'over wall limit')] for k in keys]
    brk = [[k]+[f'{T[k]["by_item_t"][i][1]:,.0f}' for i in items_] for k in keys]
    n = T['H6a']['net'][1]
    out.append(section('v2', 'DELIVERABLE 2', 'H6 sectionalized hybrid heat transport',
        f'<p>{cid} {E(H["finding"])}</p>'
        + bars([(k, tuple(T[k]['total_t']), 'good' if k == 'H6a' else ('warn' if k.startswith('H6') else 'info')) for k in keys], 'hot-loop hardware, t (opt / nom / cons)')
        + table(['Topology', 'Hardware t', 'Pumps MW', 'Li t (nom)', 'Sections', 'Paths', 'Maturity', 'Wall T'], crow)
        + '<h3>Mass by item, nominal (t, three blades)</h3>'+table(['']+[i.replace('_', ' ') for i in items_], brk)
        + f'<p class="fn">H6a nominal: trunk velocity {n["v_trunk"]:.0f} m/s (erosion cap 10), manifolds {n["v_manifold"]:.0f} m/s, inlet {n["T_in"]:.0f} K, '
          f'outlet {n["T_out"]:.0f} K, peak pressure {n["p_trunk_max"]/1e6:.2f} MPa (vapour {n["p_sat"]/1e6:.2f}, head {n["head_full"]/1e6:.2f}), trunk '
          f'D {n["D_trunk"]:.2f} m with a {n["t_trunk"]*1e3:.0f} mm wall, {n["n_manifolds"]} radial manifolds, {n["valves"]} valves and {n["bellows"]} bellows per blade. '
          f'At the coupled end mass the power-limited drive peaks at {P["accel_coupled"][0]["a_end_g"]:.2f} g, the head falls and H6a becomes '
          f'{t3(P["accel_coupled"][0]["H6a_t"])} t; the comparison above keeps the 1.36 g design-load case.</p>'
        + '<h3>Fault cases (H6a, nominal)</h3>'+table(['Fault', 'Capacity lost', 'Inventory lost kg', 'Intervention', 'Drive power, no margin', 'with 20 %', 'Action'],
            [[E(f['case']), E(f['capacity_lost']), f'{f["inventory_lost_kg"]:,.0f}', E(f['intervention']), f'{100*f["remaining"]["drive_power_no_margin"]:.0f} %',
              f'{100*f["remaining"]["drive_power_with_margin"]:.0f} %', E(f['action'])] for f in T['H6a']['faults']])
        + '<h3>Same faults, H1 (one loop per blade)</h3>'+table(['Fault', 'Capacity lost', 'Action'], [[E(f['case']), E(f['capacity_lost']), E(f['action'])] for f in T['H1']['faults'][:4]])))
    # 3 coolant
    co = [[E(c['fluid']), f'{c["T_in"]:.0f}', f'{c["p_sat_MPa"]:.2f}', f'{c["p_max_MPa"]:.2f}', f'{c["inventory_t"]:,.0f}', f'{c["pump_MW"]:,.1f}',
           f'{c["hardware_t"]:,.0f}', f'{c["freeze_K"]:.0f}' if c['freeze_K'] else '–', E(c['compat']), E(c['trl']), E(c['failure'])] for c in H['coolants']]
    out.append(section('v3', 'DELIVERABLE 3', 'Coolant and transport assessment',
        '<p>Same H6a network, same heat and surface temperature, each fluid with its own density, heat capacity, vapour pressure and acceleration '
        'head. Lithium stays the study fluid on the whole picture, not on pump power: sodium and potassium are near their critical points at a '
        '~2000 K inlet, tin is light on vapour pressure but its density turns the 1.36 g head into ~14 MPa, and a He-Xe gas loop needs ~1 GW of '
        'circulator power.</p>'+table(['Fluid', 'Inlet K', 'p_sat MPa', 'p_max MPa', 'Inventory t', 'Pumps MW', 'Hardware t', 'Freezes K',
                                        'Containment', 'Maturity', 'Failure consequence'], co)))
    # 4 hydraulics/structure
    ms = [[E(x['material']), f'{x["sigma_MPa"]:.0f}', f'{x["wall_rho"]/1e3:.1f}', f'{x["total_t"]:,.0f}', f'{x["coast_only_head_t"]:,.0f}'] for x in H['material_sensitivity']]
    su = T['H6a']['startup']
    out.append(section('v4', 'DELIVERABLE 4', 'Hydraulic and structural improvements',
        fig_profile(H)
        + '<p>The 3 mm wall is replaced: every tube is sized by hoop stress at its local pressure (vapour pressure + 0.3 MPa subcooling + loop loss + '
          'the acceleration head, graded along x for manifolds) over a creep-limited allowable, with minimum gauge and a 0.3 mm corrosion allowance. '
          'Wall mass then scales with pressure × internal volume / allowable stress, independent of diameter, so the levers are coolant volume '
          '(velocity, dT), pressure (head, inlet temperature) and the material. Improvements adopted in Phase V: progressive startup fill from a '
          'low-pressure storage tank (the 30–35 % thermal swing no longer sits in pressurised accumulators), section valves sized for the section '
          'flow, tapered headers, optimised velocities, sliding supports and bellows for ~1.5 m of header growth.</p>'
        + '<h3>Inlet temperature needed for an 1800 K mean surface (30 K coolant-to-surface drop)</h3>'
        + table(['dT K']+list(H['inlet_T'].keys()), [['inlet K']+[f'{v:.0f}' for v in H['inlet_T'].values()]])
        + '<h3>Material is the dominant lever (H6a, nominal network)</h3>'+table(['Pressure boundary', 'Allowable MPa', 'Density t/m³', 'Hot loop t', 'without burn head t'], ms)
        + f'<p class="fn">Frozen start: thaw {su["thaw_J"]/1e9:.0f} GJ, blade preheat {su["blade_preheat_J"]/1e9:.0f} GJ, heat to operating {su["heat_to_operating_J"]/1e9:.0f} GJ '
          f'(from the drive); on 5 MW of L2 the thaw and preheat take ~{su["hours_on_5MW"]:.0f} h. Coast: the loop drains to its storage tanks (a 1800 K '
          'radiator cannot be kept above the 454 K melting point: it would radiate ~100 MW). Maintenance: section isolation, drain and robotic '
          'replacement of fins and manifolds in coast.</p>'))
    # 5 radiators
    vrow = [[f'<b>{E(v["key"])}</b> {E(v["name"])}', E(v['L2']), f'{v["L2_length_m"]:.1f}', f'{v["hot_length_m"]:.1f}', f'{100*v["hot_margin"]:.0f} %',
             ok(v['meets_20pct'], 'kept', 'broken'), E(v['geometry']), E(v['warm_low']), E('; '.join(v['issues']))] for v in Rd['variants']]
    em = [[f'{b}°', f'{e["F"]["space"]:.3f}', f'{e["F"]["fwd_blades"]:.3f}', f'{e["F"]["tanks"]:.4f}', f'{e["F"]["ring_A"]:.4f}',
           f'{e["capacity_W"]/1e6:.0f}', f'{e["need_W"]/1e6:.0f}', f'{e["tanks"]["leak_W_total"]:,.0f}', f'{e["lift_W"]:.0f}'] for b, e in Rd['emitter'].items()]
    sc = [[f'{x["T_K"]:.0f}', f'{x["eta"]:.3f}', f'{x["reactor_MWt"]:.1f}', f'{x["unit_t"]:.0f}', f'{x["L_dedicated_m"]:.1f}', f'{x["L_cross_m"]:.1f}',
           f'{x["displaced_hot_W_cross"]/1e9:.2f}', ok(x['fits_hot_rule_cross'], 'fits', 'no')] for x in Rd['l2_scan']]
    bk = Rd['bulkhead']
    out.append(section('v5', 'DELIVERABLE 5', 'Radiator variants R5-A to R5-E',
        f'<p>{cid} The 20 % HOT rule is kept. It leaves {Rd["hot_free_m"]:.1f} m of hot-blade length for anything else. Under strategy C a trip leaves '
        'two units at full load: dedicated sector sections must each carry a full unit (3 × one unit), which no temperature in the trade fits; '
        'cross-strapped dual-header sections (each section fed by two neighbouring units through independent headers) need only two units\' worth '
        'and fit from 750 K. R5-A is recommended; R5-C fails on cryogenic heating, R5-B on the fixed aft edge.</p>'
        + table(['Variant', 'L2 sink', 'L2 m', 'Hot m', 'Hot margin', '20 % rule', 'Geometry', 'WARM / LOW', 'Issues'], vrow)
        + '<h3>L2 rejection temperature trade (3 × 3.5 MWe)</h3>'+fig_lscan(Rd)
        + table(['T K', 'Brayton η', 'Reactor MWt', 'Unit t', 'Dedicated m', 'Cross-strapped m', 'Hot displaced GW', '20 % rule'], sc)
        + '<p class="fn">Beyond 750 K the gain flattens because the Brayton efficiency collapses toward the 1150 K turbine inlet. Bridging advance: a '
          + ', '.join(f'{a["T_K"]:.0f} K section shrinks to {a["L_cross_m"]:.1f} m' for a in Rd['advanced_turbine']) + ' with a 1500 K turbine inlet.</p>'
        + '<h3>R5-C: an L2 emitter on the bulkhead forward face (Monte Carlo, normal tilt)</h3>'
        + table(['Tilt', 'F space', 'F forward blades', 'F tanks', 'F ring A', 'Capacity MW', 'Need MW', 'Tank IR leak W', 'He-3 lift W'], em)
        + f'<h3>Relocated bulkhead: coupled radiation</h3><p>{E(bk["note"])}. Intact three-layer stack passes {bk["intact"]["q_W_m2"]:.0f} W/m² '
          f'(layers {", ".join(f"{t:.0f}" for t in bk["intact"]["layer_T_K"])} K); one layer lost {bk["one_layer_lost"]["q_W_m2"]:.0f} W/m²; '
          f'1 % holed {bk["holed_1pct"]["q_W_m2"]:.0f} W/m²; 5 % holed {bk["holed_5pct"]["q_W_m2"]:.0f} W/m². {E(Rd["penetrations"]["note"])}. '
          f'{E(Rd["expansion"]["note"])}.</p>'))
    # 6 ledgers
    zk = list(L['rows'][0]['zones'].keys())
    lr = [[E(r['state'])]+[f'<span class="{"good" if r["zones"][k]["ok"] else "bad"}">{r["zones"][k]["load_W"]/1e6:,.1f} / {r["zones"][k]["capacity_W"]/1e6:,.1f}</span>' for k in zk]
          + [ok(r['closes_R5D_except_L1'], 'yes', 'no'), f'{r["pcm_t_per_min"]:.1f}'] for r in L['rows']]
    out.append(section('v6', 'DELIVERABLE 6', 'Thermal ledgers',
        f'<p>{cid} Configuration {E(L["basis"]["config"])}; MW load / capacity per zone; WARM and LOW in both the R5-A and the re-zoned R5-D form. '
        f'{E(L["finding"])} The L1 rows carry no capacity because no L1 radiator exists in any variant: drive-specific L1 rejects '
        f'{L["basis"]["l1_reject_W"]/1e6:.0f} MW at ~900 K, and the canon burn heat pumps (an existing allocation) another '
        f'{L["basis"]["l1_reject_burn_heat_pumps_W"]/1e6:,.0f} MW.</p>'
        + table(['State']+[k.replace('_', ' ') for k in zk]+['Closes (R5-D, excl. L1)', 'PCM t / min over'], lr)))
    # 7 transient
    tr = [[c['case'], c['life'], f'{c["delay_s"]:.0f}', f'{100*c["ramp_per_s"]:.1f} %/s', f'{c["t_restored_s"]:.0f}' if c['t_restored_s'] else 'never',
           f'{c["peak_deficit_W"]/1e6:.2f}', f'{c["storage_kWh_used"]:.1f}', ok(c['storage_power_ok']), ok(c['steady_ok'])] for c in D['transient']]
    pl = [[p['control'], f'{p["load_frac"]:.2f}', f'{p["eta"]:.3f}', f'{p["waste_W"]/1e6:.1f}' if p['waste_W'] else '–'] for p in D['part_load'] if p['control'].startswith('nom')]
    out.append(section('v7', 'DELIVERABLE 7', 'Electrical transient after a unit trip',
        '<p>Strategy C, one unit trips at t = 0. Survivors hold their output for a control delay, then ramp at a fixed share of rating per second; '
        'the deficit comes from the main battery and the ride-through cells; non-essential loads (25 %) shed after the shedding delay. Steady '
        'capacity is not instantaneous availability: the table shows how long it takes. Conservative ramp and delay values stand in for the '
        'unknown plant dynamics.</p>'+table(['Case', 'Life', 'Delay s', 'Ramp', 'Restored s', 'Peak deficit MW', 'Storage kWh', 'Storage power', 'Steady'], tr)
        + '<h3>Partial load (nominal control)</h3>'+table(['Control', 'Load', 'η', 'Waste MW'], pl)))
    # 8 L1/L2/L3 storage
    st = [[E(x['store']), str(x['kWh']), str(x['MW']), E(x['converter']), E(x['charge']), str(x['heat_kW']), E(x['independent']), E(x['cls'])] for x in D['stores']]
    l1 = [[E(r['id']), E(r['title']), t3(r['W'], 2, 1e6), E(r['cls'])] for r in D['L1']['rows']]
    out.append(section('v8', 'DELIVERABLE 8', 'L1, L2, L3 and storage',
        '<p>L1 is rebuilt item by item: the canon L1 rows, the hot-loop pumps derived from H6a, an OPEN feed-pump estimate, the preheat energy and '
        f'the cooldown circulation. Drive-specific L1 is {t3(D["L1"]["drive_specific_W"], 1, 1e6)} MW; the existing allocations (burn heat pumps, '
        f'pulse discharge) add {t3(D["L1"]["existing_W"], 0, 1e6)} MW.</p>'+table(['ID', 'Load', 'MW', 'Class'], l1)
        + '<h3>Stores, kept independent</h3>'+table(['Store', 'kWh', 'MW', 'Converter', 'Charged by', 'Heat kW', 'Independence', 'Class'], st)))
    # 9 OpenMC
    if RAD.get('runs'):
        V = RAD['runs']['V']['rows']; Bc = RAD['runs']['B']['cells']; Sc = RAD['runs']['S']['cells']
        vr = [[v['tank'], f'{v["openmc"]:.3e}', f'{v["kernel"]:.3e}', f'{v["ratio"]:.3f}', f'{100*v["rel_err"]:.1f} %'] for v in V]
        keys9 = [k for k in Bc if not k.startswith('tank_')]+['tank_O1', 'tank_I1'] if 'tank_I1' in Bc else [k for k in Bc if not k.startswith('tank_')]+[k for k in Bc if k.startswith('tank_')][:3]
        cr = []
        for k in []:
            b, s_ = Bc[k], Sc[k]
            cr.append([E(k), f'{b["flux_n"]:.2e}', f'{(b["flux_n"]-b["unc_n"])/max(b["flux_n"], 1e-99):.2f}', f'{s_["flux_n"]:.2e} ± {100*s_["flux_n_rel"]:.0f} %',
                       f'{s_["flux_n"]/max(b["flux_n"], 1e-99):.3f}', f'{s_["flux_g"]/max(b["flux_g"], 1e-99):.3f}'])
        RS = P['radiation_summary']
        rg = [[E(k), f'{v["bare_n_cm2_s"]:.2e}', f'{v["shadowed_n_cm2_s"]:.2e} ± {100*v["rel"]:.0f} %', f'{v["shadowed_over_bare"]:.2f}', f'{v["g_shadowed_over_bare"]:.2f}']
              for k, v in RS['regions'].items()]
        body9 = (f'<p>{E(RS["finding"])}</p><p class="fn">Tank heating per unit at full power ({RS["Pt_per_unit_W"]/1e6:.1f} MWt): unshielded '
                 f'{RS["tank_heat_bare_W"]:.0f} W (±{100*RS["tank_heat_bare_rel"]:.0f} %), scatter only {RS["tank_heat_scatter_W"]:.0f} W '
                 f'(±{100*RS["tank_heat_scatter_rel"]:.0f} %); three units at strategy C (2/3 load): {100*RS["scatter_share_of_lift_C"]:.0f} % of the He-3 lift.</p>'
                 + table(['Region', 'Bare n/cm²/s (per unit, full power)', 'Shadowed n/cm²/s', 'Shadowed / bare n', 'Shadowed / bare γ'], rg)
                 + f'<p>{E(RAD["status"])}. {E(RAD["solver"])}, {E(RAD["library"])}; {RAD["particles"]:,} particles per run; runtimes '
                 f'{RAD["runs"]["V"]["runtime_s"]:.0f} / {RAD["runs"]["B"]["runtime_s"]:.0f} / {RAD["runs"]["S"]["runtime_s"]:.0f} s on 4 CPUs. The '
                 'verification run (every cell void) must reproduce the point kernel in each tank volume: it checks the ship frame, the CSG placement '
                 'and the tally normalisation. The shadowed run removes the 12.5° cone from the source, so what remains in the tanks and rings is '
                 'radiation that left outside the shield cone and scattered from the casing, blades and bulkhead.</p>'
                 + table(['Tank', 'OpenMC (cm per source)', 'Point kernel', 'Ratio', 'Rel. error'], vr)
                 + '<p class="fn">Not claimed: shield transmission (deep penetration needs weight windows), crew dose, tank safety. The shield\'s own side '
                   'scatter and the unit shields are not modelled. Benchmarks passing does not validate Wayfarer shielding.</p>')
    else:
        body9 = '<p>The 3-D run has not been executed in this build.</p>'
    out.append(section('v9', 'DELIVERABLE 9', 'OpenMC 3-D status', body9+img('cam_issa5_rad3d', 'OpenMC 3-D model regions over the ship', 'CSG regions of the OpenMC model drawn over the generated ship (verification of the frame).')))
    # 10 mass
    mrow = [[c['case'], f'{c["dry_added_t"]:,.0f}', f'{c["propellant_t"]:,.0f}', f'{c["tankage_t"]:,.0f}', f'{c["end_t"]:,.0f}', f'{c["departure_t"]:,.0f}',
             f'{c["extra_departure_t"]:,.0f}'] for c in M['cases']]
    mfr = [[c['case'], f'{c["dry_added_t"]:,.0f}', f'{c["departure_t"]:,.0f}'] for c in Mf['cases']]
    irow = [[E(k), t3(v['t'], 1), f'{v["x"][0]:.0f} to {v["x"][1]:.0f}', E(v['cls'])] for k, v in M['items'].items()]
    out.append(section('v10', 'DELIVERABLE 10', 'Coupled mass with the CIRC-001 correction',
        f'<p>{cid} The correction runs through the shared infrastructure: <code>mass_model.coupled_mission(s, extra_end_kg)</code> (re-solves operating_point.mission; production unchanged, '
        f'unchanged; new unit test). Historical reference {M["historical"]["departure_t"]:,.0f} t (kept); corrected base {M["corrected"]["departure_t"]:,.1f} t '
        '(CIRC-001 is an omitted existing component, not a new requirement). Increments below are coupled from the corrected base, fixed velocity '
        '(0.016 c, four burns), propellant and tankage re-solved.</p>'+table(['Item', 't (opt–cons, nom)', 'x m', 'Class'], irow)
        + '<h3>Research baseline</h3>'+table(['Case', 'Dry added t', 'Propellant t', 'Tankage t', 'End t', 'Departure t', 'Over corrected base t'], mrow)
        + '<h3>Fictional baseline (composite pressure boundary)</h3>'+table(['Case', 'Dry added t', 'Departure t'], mfr)))
    # 11 tanks/structure
    tk = [[t['case']]+[f'{t["fill"][k]:.2f}' for k in ('helium-3', 'deuterium', 'hydrogen')] for t in M['tanks']]
    a = M['accel']; at = M['attitude']
    out.append(section('v11', 'DELIVERABLE 11', 'Tankage and structural feasibility',
        '<p>Required liquid volume over today\'s tank-farm capacity, split like today\'s inventory (fixed velocity). Anything above 1.00 needs new '
        f'tanks: the research baseline does not fit the farm. Power-limited thrust stays {a["thrust_N"]/1e6:.1f} MN, so the heavier ship peaks at '
        f'{a["a_end_nom_g"]:.2f} g instead of {a["a_end_base_g"]:.2f} g and burns ×{a["burn_time_ratio"]:.1f} longer. Placing the nominal increments '
        f'moves the centre of mass {at["cg_shift_m"]:+.1f} m (from x {at["cg_base"]:.1f} to {at["cg_new"]:.1f}) and multiplies the pitch inertia by '
        f'{at["I_pitch_ratio"]:.2f}: CMG and RCS sizing, the thrust-structure load path and the ring balance are interface requirements for the '
        'propulsion owner, not redesigned here.</p>'+table(['Case', 'He-3 fill', 'D fill', 'H fill'], tk)))
    # 12 ECLSS
    u = EC['unit']
    ec = [[E(c['layout']), str(c['units']), f'{c["mass_t"]:.1f}']+[ok(v) for v in c['results'].values()] for c in EC['cases']]
    out.append(section('v12', 'DELIVERABLE 12', 'ECLSS-G1 four-person module',
        f'<p>One unit: {u["mass_t"]} t, {u["power_kW"]} kW, {u["cooling_kW"]} kW cooling, envelope {" × ".join(str(x) for x in u["envelope_m"])} m, '
        f'ORUs ≤ {u["orus_max_width_m"]} m wide (they pass the 0.75 m doors), {u["maint_clear_m"]} m service clearance, {u["air_flow_m3_s"]} m³/s air. '
        f'Functions: {E(", ".join(u["functions"]))}. Interfaces: {E("; ".join(u["interfaces"]))}. Hub unit: duct Ø {EC["hub_interface"]["duct_D_m"]:.2f} m; '
        f'{E(EC["hub_interface"]["rotary_seal"])}. {E(EC["hub_interface"]["verdict"])}.</p>'
        + table(['Layout', 'Units', 't']+list(EC['cases'][0]['results'].keys()), ec)))
    # 13 LOG
    lc = [[f'{c["gross_t"]:.1f}', f'{c["tare_t"]:.2f}', f'{100*c["tare_frac"]:.0f} %', f'{c["edge_m"]:.2f}', f'{c["volume_m3"]:.1f}', ok(c['fits_2p5m_hatch'], 'yes', 'no'), E(c['handling'])] for c in LG['containers']]
    lm = [[f'{m["months"]}', f'{m["payload_t"]:.1f}']+[f'{v["n"] or "–"} / {v["tare_t"]:.1f} t' for v in m['options'].values()] for m in LG['missions']]
    out.append(section('v13', 'DELIVERABLE 13', 'LOG-G1 container',
        '<p>The 6 t gross limit is replaced by a handling argument: in microgravity the limit is manipulator momentum and torque, not weight, and a '
        '3 t container still passes the 2.5 m airlock fitting with single-arm handling. Lighter containers cost tare; permanent racks with bags cost '
        f'structure once. {E(LG["accounting"])}.</p>'+table(['Gross t', 'Tare t', 'Tare share', 'Edge m', 'Volume m³', '2.5 m hatch', 'Handling'], lc)
        + table(['Months', 'Payload t']+list(LG['missions'][0]['options'].keys()), lm)))
    # 14 allocation
    out.append(section('v14', 'DELIVERABLE 14', 'Spatial allocation',
        f'<p>{E(AL["note"])}.</p>'+table(['Item', 'Zone', 'm³', 't', 'kW'], [[E(r['item']), E(r['zone']), f'{r["volume_m3"]:.1f}', f'{r["mass_t"]:.1f}', f'{r["power_kW"]:.1f}'] for r in AL['rows']])
        + table(['Zone', 'Free m³', 'Used m³', 'Fits'], [[E(z['zone']), f'{z["free_m3"]:.0f}', f'{z["used_m3"]:.0f}', ok(z['ok'])] for z in AL['zones']])
        + img('cam_issa5_district', 'Three-unit district with restart storage and service routes', 'District, restart storage and removal routes (review file).')))
    # 15 missions
    pr = {}
    for p in MS['pareto']:
        pr.setdefault(p['D_AU'], {})[p['defense_law']] = ', '.join(f'{v:.3f}' for v in p['pareto_v'])
    mrows = []
    for r in MS['rows']:
        if r['v_c'] in (0.004, 0.008, 0.012, 0.016):
            mrows.append([f'{r["D_AU"]:.0f}', f'{r["v_c"]:.3f}', f'{r["round_trip_d"]/30.44:.1f}', f'{r["departure_t"]:,.0f}', f'{r["consumables_t"]:.1f}', f'{r["burn_h"]:.0f}', f'{r["reliability"]:.3f}'])
    out.append(section('v15', 'DELIVERABLE 15', 'Mission trade-offs',
        f'<p>{E(MS["note"])}. Pareto-efficient cruise speeds (duration, departure mass, defense load) per destination and defense law:</p>'
        + table(['AU', 'v¹', 'v²', 'v³'], [[f'{d:.0f}', pr[d]['v1'], pr[d]['v2'], pr[d]['v3']] for d in sorted(pr)])
        + table(['AU', 'v / c', 'Months', 'Departure t', 'Consumables t', 'Burn h', 'Reliability (illustrative λ)'], mrows)))
    # 16 integrated comparison
    cvr = [[E(c['name']), t3(c['dry_added_t']), t3([x['departure_t'] for x in c['coupled']]), E(c['thermal']), E(c['electrical']), E(str(c['radiation'])),
            E(c['fault_tolerance']), E(c['maturity']), E('; '.join(c['problems']))] for c in CV]
    db = [[E(d['subsystem']), E(d['physics']), E(d['today']), E(d['unresolved']), E(d['advance']), E(d['fiction']), E(d['research_value']), E(d['fiction_value'])] for d in P['dual_baseline']]
    out.append(section('v16', 'DELIVERABLE 16', 'Integrated comparison and the two baselines',
        '<p>No candidate closes on contemporary engineering. The lightest rows are incomplete (no hot loop, or a hot loop on a wall that cannot hold '
        'the pressure), so they are not "best". The research baseline is R5-A + H6a + 3 × 3.5 MWe C: it closes electrically at the nominal band and thermally in '
        'coast and single failures; burns still miss the L1 900 K reject and ~0.4 MW of WARM, engagements need a thermal buffer, and its hot-loop mass makes the ship several times heavier. The fictional baseline adopts one '
        'named advance (a composite pressure boundary near 2000 K) and keeps every other number traceable to the research row.</p>'
        + table(['Candidate', 'Dry added t', 'Departure t', 'Thermal', 'Electrical', 'Radiation', 'Fault tolerance', 'Maturity', 'Problems'], cvr)
        + '<h3>Dual baseline (owner rule 2026-11-27)</h3>'
        + table(['Subsystem', 'Established physics', 'Today', 'Unresolved', 'Bridging advance', 'Adopted fictional assumption', 'Research', 'Fictional'], db)
        + img('cam_issa5_overview', 'Phase V review geometry over the whole ship', 'Phase V review geometry: R5-A sections, relocated bulkhead, H6a trunks and sections (review file).')))
    # 17 registers
    out.append(section('v17', 'DELIVERABLE 17', 'Problems and decisions',
        table(['ID', 'Severity', 'Problem'], [[p['id'], E(p['sev']), E(p['text'])] for p in P['problems']])
        + table(['ID', 'Decision', 'Recommendation'], [[d['id'], E(d['q']), E(d['rec'])] for d in P['decisions']])))
    return '\n'.join(out)
