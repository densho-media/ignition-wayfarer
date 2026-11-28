"""3D Systems Integration page sections (Track F1), inserted above Phase VI into results/issa.html by build_report.py. Pure Python."""
import html
import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[1]; R = W/'results'
for p in ('phase2', 'phase3'):
    sys.path.insert(0, str(W/p))
from report2 import table, section  # noqa: E402

E = html.escape


def svg(name):
    f = R/name
    return f'<div class="tablewrap" style="overflow-x:auto">{f.read_text()}</div>' if f.exists() else ''


def img(name, alt, cap):
    return (f'<figure><img src="{name}.jpg" alt="{E(alt)}" loading="lazy" style="width:100%;border-radius:6px">'
            f'<figcaption class="fn">{cap}</figcaption></figure>') if (R/f'{name}.jpg').exists() else ''


def build():
    if not (R/'i3d_masterplan.json').exists():
        return ''
    M = json.loads((R/'i3d_masterplan.json').read_text()); T = json.loads((R/'i3d_tanks.json').read_text())
    out = []
    L = M['ledger']
    out.append(section('i1', '3D · A', 'Checkpoint 1: spatial masterplan',
                       f'<p>Reference {E(M["config"]["reference"])} (Track F1, 1500 K turbine approved as fiction), compared with {E(", ".join(M["config"]["comparisons"]))}. '
                       f'Nominal departure {L["departure_t"]:,.0f} t, a working estimate the checkpoints recompute. Production geometry is unchanged; every F1 zone is a separate, '
                       'regenerable layer (<code>integration3d/</code>, config <code>f1_integration.toml</code>).</p>'
                       + svg('i3d_masterplan_side.svg')
                       + table(['Zone', 'Function', 'x (m)', 'radius (m)', 'Maturity', 'Source'],
                               [[E(z['id']), E(z['name']), f'{z["x0"]:.1f} – {z["x1"]:.1f}', f'{z["r0"]:.1f} – {z["r1"]:.1f}', E(z['maturity']), E(z['source'])]
                                for z in M['production_zones']+M['f1_zones']])
                       + '<h3>Keep-outs</h3>' + table(['Id', 'Rule'], [[E(k['id']), E(k['what'])] for k in M['keepouts']])
                       + '<h3>Findings</h3><ul>' + ''.join(f'<li>{E(f)}</li>' for f in M['findings']) + '</ul>'))
    rows = []
    for a in T['alternatives']:
        if a['id'] == 'T-X':
            rows.append([E(a['id']), E(a['name']), '–', '–', '–', '–', E(a['reason'])]); continue
        rows.append([E(a['id']), E(a['name']), f'+{a["added_length_m"]:.1f}', f'{a["ship_length_m"]:.1f}', f'{a["tankage_t"]:.0f} ({a["tankage_delta_vs_A_t"]:+.0f})',
                     'yes' if a.get('modular') else 'no', E('; '.join(a['pros']))+'<br><span class="fn">'+E('; '.join(a['cons']))+'</span>'])
    need = T['need_m3']; hist = T['historical_capacity_m3']
    out.append(section('i2', '3D · B', 'Propellant volume: alternatives',
                       f'<p>F1 nominal needs {", ".join(f"{k} {need[k]:,.0f} m³ ({need[k]/hist[k]:.2f}×)" for k in need)} of the historical vessel volume. '
                       'The 13 vessels are at their packing limits (section below), so the volume has to come from length, a second segment or density.</p>'
                       + table(['Id', 'Alternative', 'Added length (m)', 'Ship length (m)', 'Tankage t (vs T-A)', 'Mission-modular', 'For / against'], rows)
                       + f'<p><b>Recommendation.</b> {E(T["recommendation"]["pick"])}: {E(T["recommendation"]["why"])}. {E(T["recommendation"]["owner_question"])}.</p>'
                       + ''.join(img(f'cam_i3d_farm_side_{k}', f'{k} side view', f'{k.upper()}: side view of the forward ship, the alternative in its engineering colours and the translated Brow envelope (amber).')
                                 + img(f'cam_i3d_farm_34_{k}', f'{k} three-quarter view', f'{k.upper()}: three-quarter view.') for k in ('ta', 'tb', 'tc'))
                       + svg('i3d_farm_section.svg')))
    sysrows = [[E(q['id']), E(q['name']), E(q['stage']), E(q['now']), E(q['target']), E(q['track']), E(', '.join(q['register']) or '–')] for q in M['registry']]
    out.append(section('i3', '3D · registry', 'Maturity registry',
                       '<p>' + ' · '.join(f'<b>{k}</b> {E(v)}' for k, v in M['maturity_scale'].items()) + '</p>'
                       + svg('i3d_maturity.svg')
                       + table(['Id', 'System', 'Stage', 'Now', 'Target', 'Track', 'Register'], sysrows)
                       + '<h3>Mass ledger (live, nominal)</h3>'
                       + table(['Item', 't', 'Class'], [[E(r['item']), f'{r["t"]:.1f}', E(r['cls'])] for r in L['items']]
                               + [['Propellant', f'{L["propellant_t"]:,.0f}', 'coupled'], ['Added tankage', f'{L["tankage_t"]:,.0f}', 'coupled'],
                                  ['<b>Departure</b>', f'<b>{L["departure_t"]:,.0f}</b>', E(L['note'])]])))
    return '\n'.join(out)+build_cp2()+build_cp3()+build_cp4()+build_ledger()


def build_cp2():
    if not (R/'i3d_power.json').exists():
        return ''
    PW = json.loads((R/'i3d_power.json').read_text()); H = json.loads((R/'i3d_h6a.json').read_text()); U = PW['unit']; C = PW['checks']; n = H['network']
    out = []
    prow = [[E(p['name']), f'{p["mass_t"]:.1f}', str(p['modules']), f'{p["module_t"]:.1f}', E(p['replacement']), E('; '.join(p['interfaces'])),
             (f'{p["shadow_margin_m"]:+.2f}' if 'shadow_margin_m' in p else '–'), E(p['note'])] for p in U['parts']]
    ck = [[E(k.replace('_', ' ')), f'{v:.2f}' if isinstance(v, float) else E(str(v))] for k, v in C.items() if k not in ('dry_store_displaced',)]
    out.append(section('i4', '3D · C', 'Checkpoint 2: L2 power unit (M3) and district (M2)',
                       f'<p>One reusable assembly, placed three times with shared mesh data (<code>integration3d/power_unit.py</code>, parameters in <code>[power_unit]</code> and '
                       f'<code>[district]</code>). Duties: {U["duty"]["thermal_W"]/1e6:.1f} MWt in, {U["duty"]["electric_W"]/1e6:.1f} MWe out, recuperator '
                       f'{U["duty"]["recuperator_W"]/1e6:.0f} MW, gas cooler {U["duty"]["gas_cooler_W"]/1e6:.1f} MW to the 950 K sections. Reactor and shield stay '
                       'ADJUSTABLE envelopes (no core design; shielding OPEN).</p>'
                       + svg('i3d_power_unit.svg')
                       + table(['Part', 't', 'Modules', 't each', 'Replacement', 'Interfaces', 'Shadow margin m', 'Note'], prow)
                       + img('cam_i3d_unit', 'L2 power unit', 'Unit 1 isolated: reactor envelope (red), shield (amber), mount ring, gas ducts around the shield, TAC, recuperator, gas cooler, PMAD.')
                       + svg('i3d_district.svg') + img('cam_i3d_district_end', 'District end view', 'District end view: three units, L1 bus slot, removal route and replacement paths.')
                       + '<h3>Clearances and paths</h3>' + table(['Check', 'Value'], ck)
                       + '<h3>Findings</h3><ul>' + ''.join(f'<li>{E(f)}</li>' for f in PW['findings']) + '</ul>'))
    cnt = H['counts_per_blade']; G = H['geometry']
    out.append(section('i5', '3D · D', 'H6a hot network (M2) and aft manifold (M3)',
                       f'<p>Four trunks per blade (pairs A and B, supply and return, each pair 60 %), six isolatable sections with headers, cross-feed, saddles and inspection ports, '
                       f'and an aft manifold with two EM pumps, bypasses, accumulator, drain/recovery and manifold valves (<code>integration3d/h6a3d.py</code>, from the Phase V '
                       f'network model with the F1 composite and hot length {H["hot_length_m"]:.1f} m). Drawn hardware {H["mass_drawn_t"]:.0f} t of the {H["mass_phase6_t"]:.0f} t '
                       f'line; valves {cnt["valves"]} and bellows {cnt["bellows"]} per blade match the model ({cnt["valves_model"]}, {cnt["bellows_model"]}).</p>'
                       + svg('i3d_h6a_section.svg')
                       + img('cam_i3d_h6a_section', 'H6a section', 'Transverse cut at x −100 looking forward: trunk quartets at the three blade roots and the district units inside the hull.')
                       + img('cam_i3d_aft_manifold', 'Aft manifold', 'Aft manifold of one blade: HX interface arc, EM pumps on the returns (blue), bypasses, bellows, valves, accumulator.')
                       + '<h3>Findings</h3><ul>' + ''.join(f'<li>{E(f)}</li>' for f in H['findings']+H['corrections']) + '</ul>'
                       + img('cam_i3d_cp2_ship', 'Ship with Checkpoint 2 layers', 'Whole ship with the Checkpoint 2 layers.')))
    return '\n'.join(out)


def build_cp3():
    if not (R/'i3d_radiators.json').exists():
        return ''
    RD = json.loads((R/'i3d_radiators.json').read_text()); EL = json.loads((R/'i3d_electrical.json').read_text()); LG = json.loads((R/'i3d_ledger.json').read_text())
    S = RD['section']; HP = RD['heat_pipes']; NK = RD['nak']; CY = RD['cycle']; B = RD['hot_budget']; out = []
    cyc = [[E(r['components']), f'{r["eta_at_950K"]:.3f}', f'{r["Tci_for_0154"]:.0f}', f'{r["PR"]:.2f}', f'{r["T_gc_in"]:.0f}'] for r in CY['rows']]
    lim = [[f'{r["T_K"]:.0f}', E(r['state']), f'{r["load_W"]/1e3:.1f}', f'{r["sonic_W"]/1e3:.1f}', f'{r["capillary_W"]/1e3:.1f}' if r['capillary_W'] else '–',
            f'{r["entrainment_W"]/1e3:.1f}', f'{r["margin"]:.2f}'] for r in HP['limits'] if r['state'] != 'burn, lowest acceleration']
    fl = [[E(r['case']), ' / '.join(f'{w/1e6:.1f}' for w in r['blade_W']), E(r['header_split']), f'{r["use"]*100:.0f} %'] for r in RD['failures']['rows']]
    bud = [['HOT headroom (Phase VI, 20 % rule)', f'{B["hot_headroom_W"]/1e9:+.2f}'], ['L2 section growth', f'{B["l2_growth_W"]/1e9:+.2f}'],
           ['H6a trunk shading (bound, insulated trunks)', f'{B["trunk_shading_W"]/1e9:+.2f}'], ['<b>Remaining with forward-pointing HOT fins</b>', f'<b>{B["remaining_mitigated_W"]/1e9:+.2f}</b>'],
           ['Aft-pointing HOT fins at peak burn (if not changed)', f'{B["fins_unmitigated_W"]/1e9:+.2f}'], ['Remaining without the fin change', f'{B["remaining_unmitigated_W"]/1e9:+.2f}']]
    mass = [[E(k.replace('_', ' ')), f'{v:.1f}'] for k, v in RD['mass']['per_blade_t'].items()] + [['NaK transport loops (3)', f'{RD["mass"]["loops_t"]:.1f}'], ['EM pumps', f'{RD["mass"]["pumps_t"]:.1f}'],
           ['<b>Gross (3 blades)</b>', f'<b>{RD["mass"]["gross_t"]:.1f}</b>'], ['Phase VI ledger line', f'{RD["mass"]["phase6_ledger_t"]:.1f}']]
    out.append(section('i6', '3D · E', 'Checkpoint 3: radiators with internal cross-sections',
                       f'<p>The L2 section of each blade is now an engineering assembly at M3 (<code>integration3d/radiators3d.py</code>, <code>[radiators]</code>): '
                       f'NaK loops from each unit\'s gas cooler, dual header serpentines at the aft edge of two chord bays, and {HP["per_blade"]} potassium heat pipes per blade '
                       f'on both face sheets. Section {S["length_m"]:.2f} m (x {S["x0"]:.2f} – {S["x1"]:.1f}), Phase VI {S["length_phase6_m"]:.2f} m.</p>'
                       + '<h3>1 · The cycle behind FT-03</h3><p>' + E(CY['finding']) + '</p>'
                       + table(['Components', 'eta at 950 K compressor inlet', 'Compressor inlet for eta 0.154 (K)', 'Pressure ratio', 'Gas-cooler inlet (K)'], cyc)
                       + svg('i3d_l2_section.svg') + svg('i3d_l2_plan.svg')
                       + img('cam_i3d_l2_cutaway', 'L2 section cutaway', 'L2 section of blade 90 with the + face of bay 1 left open: heat-pipe rows, headers, the closed face of bay 2.')
                       + img('cam_i3d_l2_evap_detail', 'Evaporator detail', 'Chordwise cut at mid-span through the aft edge of bay 1: headers A and B between the two saddle strips, pipe rows on the face sheets.')
                       + img('cam_i3d_loops', 'NaK loops', 'NaK transport loops arriving at the L2 sections: each unit feeds loop A of its own blade and loop B of the next.')
                       + '<h3>2 · Heat-pipe limits</h3>' + table(['Vapour T (K)', 'State', 'Load kW', 'Sonic kW', 'Capillary kW', 'Entrainment kW', 'Margin'], lim)
                       + '<h3>3 · Failure cases</h3>' + table(['Case', 'Blade loads MW', 'Header split', 'Use of design'], fl)
                       + '<h3>4 · HOT, WARM and LOW (M2)</h3>' + svg('i3d_blade_sections.svg')
                       + '<h3>5 · HOT budget at peak burn (GW)</h3>' + table(['Item', 'GW'], bud)
                       + '<h3>6 · Mass</h3>' + table(['Item', 't'], mass)
                       + '<h3>Findings</h3><ul>' + ''.join(f'<li>{E(f)}</li>' for f in RD['findings']) + '</ul>'
                       + '<h3>Owner questions</h3>' + table(['Id', 'Question', 'Recommendation'], [[E(d['id']), E(d['q']), E(d['rec'])] for d in RD['decisions']])))
    bu = [[E(r['id']), E(r['what']), f'{r["P_W"]/1e6:.2f}', f'{r["A_mm2"]:.0f}', f'{r["length_m"]:.0f}', f'{r["mass_t"]:.2f}'] for r in EL['buses']['rows'] if not r['id'].startswith('TIE')]
    st = [[E(r['store']), E(r['duty']), f'{r["need_kWh"]:.1f}' if r['need_kWh'] is not None else '–', f'{r["have_kWh"]:.0f}', 'OK' if r['ok'] else 'SHORT', E(r['note'])] for r in EL['storage']['rows']]
    fa = [[E(r['fault']), E(r['left']), E(r['shed']), E(r['bridge']), 'rides through' if r['ok'] else 'refuge case'] for r in EL['faults']]
    sp = [[E(r['a']), E(r['b']), f'{r["clear_m"]:.2f}', E(r['action'])] for r in EL['separation']]
    out.append(section('i7', '3D · F', 'Electrical L1 / L2 / L3, storage and data (M2)',
                       '<p>Three HVDC sectors, one per L2 unit and failure domain, with normally-open ties at three stations; L1 on its own 10 kV bus for burns; the refuge on L3 '
                       'with its own bus and no tie (<code>integration3d/electrical3d.py</code>, <code>[electrical]</code>).</p>'
                       + svg('i3d_electrical_oneline.svg') + svg('i3d_electrical_section.svg')
                       + img('cam_i3d_elec_overview', 'Electrical layer', 'Electrical layer only: three sector buses (blue, green, amber), breakers and load centres, L1 (red), defense bus and buffers (magenta), data A/B.')
                       + img('cam_i3d_elec_section', 'Electrical section', 'Looking forward from x −76: buses, data networks and the NaK loops (orange) in the casing-hull annulus, each in its own domain.')
                       + '<h3>Conductors</h3>' + table(['Id', 'What', 'MW', 'mm² per pole', 'm', 't'], bu)
                       + '<h3>Storage against duty</h3>' + table(['Store', 'Duty', 'Need kWh', 'Have kWh', 'Result', 'Note'], st)
                       + '<h3>Single faults</h3>' + table(['Fault', 'Left', 'Shed', 'Bridge', 'Result'], fa)
                       + '<h3>Separation between failure domains (&lt; 1.5 m)</h3>' + table(['A', 'B', 'Clear m', 'Action'], sp)
                       + '<h3>Findings</h3><ul>' + ''.join(f'<li>{E(f)}</li>' for f in EL['findings']) + '</ul>'))
    return '\n'.join(out)


def build_ledger():
    if not (R/'i3d_ledger.json').exists():
        return ''
    LG = json.loads((R/'i3d_ledger.json').read_text()); out = []
    lr = [[E(r['item']), E(r['stage']), f'{r["t"]:.1f}', E(r['cls'])] for r in LG['items']]
    pe = [[E(p['id']), E(p['item']), f'{p["t"]:+.1f}', f'{p["departure_t"]:+.0f}'] for p in LG['pending']]
    out.append(section('i8', '3D · ledger', 'Live mass ledger after Checkpoint 4',
                       f'<p>Dry additions {LG["dry_added_t"]:,.1f} t give a nominal departure of <b>{LG["departure_t"]:,.0f} t</b> ({LG["change_t"]:+,.0f} t against Phase VI; '
                       f'{LG["coupling_t_per_t"]:.2f} t of departure per tonne of dry mass). Propellant {LG["propellant_t"]:,.0f} t, added tankage {LG["tankage_t"]:,.0f} t.</p>'
                       + table(['Item', 'Stage', 't', 'Class'], lr)
                       + '<h3>Waiting for owner decisions (not added)</h3>' + table(['Decision', 'Item', 'Dry t', 'Departure t'], pe)))
    return '\n'.join(out)


def build_cp4():
    if not (R/'i3d_eclss.json').exists():
        return ''
    EC = json.loads((R/'i3d_eclss.json').read_text()); LG = json.loads((R/'i3d_logistics.json').read_text()); RM = json.loads((R/'i3d_remaining.json').read_text()); out = []
    oru = [[E(o['name']), f'{o["mass_kg"]}', f'{o["power_W"]}', ' x '.join(f'{v:.2f}' for v in o['size']), 'yes' if o['width_ok'] else 'NO'] for o in EC['hub']['orus']]
    cs = [[E(k), 'pass' if v else 'FAIL'] for k, v in EC['cases']['results'].items()]
    out.append(section('i9', '3D · G', 'Checkpoint 4: ECLSS hub unit (M3) and ring units (M2)',
                       f'<p>Seven ECLSS-G1 units: three per ring and one in the hub that serves both rings through the rotary couplings '
                       f'(<code>integration3d/systems3d.py</code>). The hub unit is drawn as replaceable units (ORUs) inside its envelope, with the maintenance face on the hub aisle.</p>'
                       + svg('i3d_eclss_hub.svg')
                       + img('cam_i3d_eclss_hub', 'Hub ECLSS unit', 'Hub ECLSS unit: eight ORUs on two levels inside the 2.0 x 2.2 x 1.4 m frame, and the two air ducts down to the rotary couplings.')
                       + '<h3>ORUs</h3>' + table(['ORU', 'kg', 'W', 'Size m', 'Fits 0.70 m aisle'], oru)
                       + '<h3>Failure cases (Phase V, seven units)</h3>' + table(['Case', 'Result'], cs)
                       + '<h3>Findings</h3><ul>' + ''.join(f'<li>{E(f)}</li>' for f in EC['findings']) + '</ul>'))
    G1 = LG['container']; c = LG['carriage']
    hv = [[E(h['name']), f'{h["t"]:.1f}'] for h in LG['heavy_items']]
    rb = [[E(r['kind']), f'{r["n"]}', f'{r["t_each"]:.2f}', E(r['base'])] for r in LG['robots']]
    out.append(section('i10', '3D · H', 'LOG-G1 container (M3), workshop, robots and the heavy carriage (M2)',
                       f'<p>The 3 t LOG-G1 container is a parametric part: <code>container(gross_t)</code> gives edge, tare split, grapples and latches from the Phase V relation. '
                       f'Eight sit in the hub store on a transfer rail. The six dry-store containers that the L2 district displaced now have a tenth body-bay module.</p>'
                       + svg('i3d_log_g1.svg')
                       + img('cam_i3d_log_g1', 'LOG-G1 containers', f'Hub store: eight LOG-G1 containers ({G1["edge_m"]:.2f} m), frames, panels, grapple fixtures (magenta) and corner latches (amber).')
                       + img('cam_i3d_module10', 'Body-bay module 10', 'Body-bay module 10 with the six relocated dry-store containers (blue) between the buses and data networks.')
                       + svg('i3d_mro_routes.svg')
                       + img('cam_i3d_mro_route', 'MRU carriage', 'The MRU heavy carriage on its rail along keel lane az 270, beside the three power units it must remove.')
                       + '<h3>Items that need the heavy carriage (&gt; 3 t, the single-arm limit)</h3>' + table(['Item', 't per module'], hv)
                       + '<h3>Robots</h3>' + table(['Kind', 'Number', 't each', 'Base'], rb)
                       + f'<p class="fn">Supervision: {E(LG["supervision"]["where"])}; {E(LG["supervision"]["note"])}.</p>'
                       + '<h3>Findings</h3><ul>' + ''.join(f'<li>{E(f)}</li>' for f in LG['findings']) + '</ul>'))
    cr = RM['cryo']; wa = RM['warm']
    ct = [['He-3 stage lift (3 K), incl. nuclear', f'{cr["he3_W"]:.0f} W', f'{cr["installed_he3_W"]:.0f} W'], ['Shield lift (20 K), incl. nuclear', f'{cr["shield_W"]/1e3:.2f} kW', f'{cr["installed_shield_W"]/1e3:.2f} kW'],
          ['Input power', '', f'{cr["input_W"]/1e3:.0f} kW'], ['Cooler mass', '', f'{cr["mass_t"]:.1f} t'], ['LOW reject', f'{cr["low"]["cryo_reject_W"]/1e3:.0f} kW', f'margin {cr["low"]["margin_W"]/1e3:+.0f} kW']]
    wt = [[E(k.replace('_W', '').replace('_', ' ')), f'{v/1e3:.0f}'] for k, v in wa['adds'].items()] + [['<b>WARM short</b>', f'<b>{wa["short_W"]/1e3:.0f}</b>']]
    gn = [[E(g['name']), E(g['level'])] for g in RM['gnc']]
    out.append(section('i11', '3D · I', 'Cryocoolers, heat sinks, farm, structure and GNC',
                       '<p>The cryocooler stations are sized from the T-A vessel area and the OpenMC nuclear heating, and the WARM and LOW sections are checked against every '
                       'heat load that Checkpoints 3 and 4 added.</p>'
                       + img('cam_i3d_cryo', 'Cryocooler stations', 'T-A stretched farm with one cryocooler station at the forward end of each of the 13 vessels.')
                       + svg('i3d_heat_sinks.svg')
                       + '<h3>Cryogenics</h3>' + table(['Item', 'Load', 'Installed / result'], ct)
                       + '<h3>WARM section shortfall (kW)</h3>' + table(['Item', 'kW'], wt)
                       + '<h3>GNC / C&amp;DH placeholders</h3>' + table(['Block', 'Level'], gn)
                       + f'<p class="fn">{E(RM["structure"]["note"])}.</p>'
                       + '<h3>Findings</h3><ul>' + ''.join(f'<li>{E(f)}</li>' for f in RM['findings']) + '</ul>'))
    return '\n'.join(out)
