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
    return build_consolidation()+'\n'.join(out)+build_cp2()+build_cp3()+build_cp4()+build_ledger()


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


def build_consolidation():
    if not (R/'i3d_consolidated.json').exists():
        return ''
    C = json.loads((R/'i3d_consolidated.json').read_text()); S = json.loads((R/'i3d_structure_interface.json').read_text())
    T = C['tanks']; RA = C['radiators']; P = RA['preferred']; L = C['ledger']; CR = C['cryo']; EL = C['electrical']; LF = C['l2_failure']; EC = C['eclss']
    MR = C['mru']; M10 = C['module10']; cp4 = C['cp4']; out = []
    f0 = lambda v, d=0: f'{v:,.{d}f}'
    dec = [[E(d['id']), E(d['what']), E(d['state'])] for d in C['decisions']]
    cmp_ = [['Departure mass (t)', f0(cp4['departure_t']), f0(L['departure_t']), f'{L["departure_t"]-cp4["departure_t"]:+,.0f}'],
            ['Propellant (t)', f0(cp4['propellant_t']), f0(L['propellant_t']), f'{L["propellant_t"]-cp4["propellant_t"]:+,.0f}'],
            ['Added tankage (t)', f0(cp4['tankage_t']), f0(L['tankage_t']), f'{L["tankage_t"]-cp4["tankage_t"]:+,.0f}'],
            ['Dry additions over the historical ship (t)', f0(cp4['dry_added_t'], 1), f0(L['dry_added_t'], 1), f'{L["dry_added_t"]-cp4["dry_added_t"]:+,.1f}'],
            ['Farm stretch (m)', f'{cp4["farm_added_m"]:.2f}', f'{T["added_length_m"]:.2f}', f'{T["added_length_m"]-cp4["farm_added_m"]:+.2f}'],
            ['Ship length (m)', f'{cp4["ship_length_m"]:.1f}', f'{T["ship_length_m"]:.1f}', f'{T["ship_length_m"]-cp4["ship_length_m"]:+.1f}'],
            ['WARM / LOW', 'short 496 / 76 kW (pending)', f'closed: WARM {P["T_warm_K"]:.0f} K; LOW tabs {P["low_tab_length_m"]:.1f} m + {P["T_low_K"]:.0f} K', ''],
            ['HOT fins', 'aft-pointing halves (-0.77 GW in burns)', f'forward-pointing, {RA["fins"]["manifolds_per_blade"]} manifolds per blade', ''],
            ['L1 continuous / reactive peak (MW)', '14.3 / 93.5', f'{EL["continuous_W"]/1e6:.1f} / {EL["reactive_W"]/1e6:.1f}', 'proactive heat-pump duty retired']]
    rd = [[E(r['area']), E(r['state']), E(r['note'])] for r in C['readiness']]
    out.append(section('c0', 'Consolidation', 'ISSA consolidation: one fictional working configuration, WF-F1-C1.0',
                       f'<p>The owner accepted the 19 developed systems (2026-11-28 09:15Z) and asked for consolidation rather than another research phase. This section '
                       f'implements the owner decisions, closes the radiator shortfalls, develops the heavy maintenance transport, reconciles electrical, cryogenic and '
                       f'mass accounting and hands a versioned interface to the primary-structure work (PSA). Nominal departure <b>{L["departure_t"]:,.0f} t</b> '
                       f'(owner indicative ~8,671 t, not forced). Production ship unchanged; nothing written to Drive; Track R findings below stay as published evidence.</p>'
                       + '<h3>Implemented owner decisions</h3>' + table(['Id', 'Decision', 'State'], dec)
                       + '<h3>Comparison with Checkpoint 4</h3>' + table(['Quantity', 'Checkpoint 4', 'WF-F1-C1.0', 'Change'], cmp_)
                       + img('cam_i3d_x_ship', 'Consolidated ship', 'WF-F1-C1.0 whole ship: final T-A farm and translated Brow envelope, HOT manifolds, LOW tip extensions, '
                             'and every 3D-integration assembly.')
                       + svg('i3d_c_longitudinal.svg') + img('cam_i3d_x_long', 'Longitudinal section', 'Longitudinal section at the y = 0 plane (Blender).')
                       + svg('i3d_c_transverse.svg')
                       + img('cam_i3d_x_m84', 'Section at x -84', 'Transverse slab looking forward from x -84 (power district).')
                       + img('cam_i3d_x_p28', 'Section at x 27.75', 'Transverse slab looking forward from x 27.75 (body-bay module 10).')
                       + img('cam_i3d_x_p60', 'Section at x 60', 'Transverse slab looking forward from x 60 (WARM section and blades).')
                       + '<h3>Production-integration readiness</h3>' + table(['Area', 'State', 'Note'], rd)))
    # radiators
    op = [[E(o['id']), E(o['name']), f'{o["hot_cost_W"]/1e9:.2f}' if o.get('hot_cost_W') is not None else '–', E(o['geometry']), E(o['verdict'])] for o in RA['options']]
    bud = [[E(k), f'{v/1e9:+.3f}'] for k, v in RA['budget']['items']] + [['<b>HOT reserve at peak burn</b>', f'<b>{RA["budget"]["reserve_nominal_W"]/1e9:+.3f}</b>']] + \
          [[E(k), f'{v/1e9:+.3f}'] for k, v in RA['budget']['reactive']] + [['<b>HOT reserve at the reactive-defense peak (burnout)</b>', f'<b>{RA["budget"]["reserve_reactive_W"]/1e9:+.3f}</b>']]
    md = [[E(m['mode']), E(m['condensate']), 'OK' if m['ok'] else 'NO'] for m in RA['fins']['modes']]
    th = [['WARM load (kW)', f'{RA["need"]["warm_W"]/1e3:.0f} added (Phase VI burn shortfall + NaK insulation leak + bus loss)'],
          ['WARM closure', f'{P["T_warm_K"]:.1f} K on the existing 22.5 m (capacity x{(P["T_warm_K"]/440)**4:.3f}); after one loop lost {100*RA["degraded"]["warm_one_loop"]:.0f} %'],
          ['LOW need with the 20 % rule (kW)', f'{RA["need"]["low_capacity_W"]/1e3:.0f} at 300 K ({RA["need"]["avionics_W"]/1e3:.0f} avionics + {RA["need"]["cryo_reject_W"]/1e3:.0f} cryo)'],
          ['LOW tip extensions', f'x {P["low_tab_x"][0]:.1f}-{P["low_tab_x"][1]:.1f}, r 31.5-37, {P["low_tab_area_m2"]:.0f} m2 (both faces), {P["low_tab_capacity_W"]/1e3:.0f} kW at 300 K, '
                                  f'{P["low_tab_mass_t"]:.1f} t; alone they would need {P["tabs_needed_alone_m"]:.0f} m (the ring sweep stops them at 13 m)'],
          ['LOW closure', f'{P["T_low_K"]:.1f} K: capacity {P["low_have_at_T_W"]/1e3:.0f} kW vs need {P["low_need_at_T_W"]/1e3:.0f} kW (the warmer reject raises the cryo input)'],
          ['Heat pumps', E(RA['heat_pump']['after'])],
          ['Pumps (W)', f'WARM {RA["pumps"]["warm_W"][0]/1e3:.1f} -> {RA["pumps"]["warm_W"][1]/1e3:.1f} kW; LOW {RA["pumps"]["low_W"][0]/1e3:.1f} -> {RA["pumps"]["low_W"][1]/1e3:.1f} kW'],
          ['WARM/LOW joint', f'dT {RA["joint"]["dT_before_K"]:.0f} -> {RA["joint"]["dT_after_K"]:.0f} K: joint leak +{100*RA["joint"]["leak_increase"]:.0f} % (bulkhead positions unchanged)'],
          ['Expansion', E(RA['expansion']['note'])], ['Supports', E(RA['supports']['tab'])]]
    out.append(section('c1', 'Consolidation · thermal', 'Radiator geometry and the thermal ledger',
                       '<p>The shortfalls are closed without spending HOT. Moving L2/WARM/LOW aft into HOT fails the complete propulsion heat budget at the reactive-defense '
                       'peak; widening breaks the Brow shadow; extending forward at full span hits the ring sweep. WARM therefore runs 11 K warmer on its existing area, '
                       'LOW gains physical tip extensions where the rings leave room (r 31.5-37 m beside them) and runs 16 K warmer for the rest.</p>'
                       + '<h3>Options</h3>' + table(['Id', 'Option', 'HOT used (GW)', 'Geometry', 'Verdict'], op)
                       + '<h3>Complete HOT budget (GW)</h3>' + table(['Item', 'GW'], bud)
                       + '<h3>Preferred configuration</h3>' + table(['Item', 'Value'], th)
                       + img('cam_i3d_x_lowtabs', 'LOW tip extensions', 'LOW forward tip extensions beside the rings (blue), outside the ring sweep and inside the Brow shadow.')
                       + img('cam_i3d_x_hotfins', 'HOT manifolds', f'HOT forward-pointing fin manifolds ({RA["fins"]["pitch_m"]:.2f} m pitch) above the H6a trunks.')
                       + '<h3>Forward-pointing HOT fins (DR-3D-04) in every mode</h3>' + table(['Mode', 'Condensate', 'Result'], md)))
    # tanks
    vs = [[E(v['id']), E(v['species']), E(v['cls']), f'{v["x0"]:.2f}-{v["x1"]:.2f}', f'{v["volume_m3"]:,.0f}', f'{v["prop_t"]:,.0f}', f'{v["axial_kN"]:,.0f}'] for v in T['vessels']]
    fl = [[E(k), f'{T["need_m3"][k]:,.0f}', f'{T["capacity_m3"][k]:,.0f}', f'{100*T["fill"][k]:.1f} %'] for k in T['need_m3']]
    out.append(section('c2', 'Consolidation · tanks', 'T-A farm resized to the current coupled inventory',
                       f'<p>T-A is the reference (T-B mission-modular alternative, T-C research option, no densification). The stretch follows the coupled propellant '
                       f'{T["propellant_t"]:,.0f} t (CP1 sized for {T["cp1_propellant_t"]:,.0f} t): <b>+{T["added_length_m"]:.2f} m</b> (CP1 {T["cp1_added_length_m"]:.2f} m), '
                       f'vessels {T["vessel_length_m"]:.2f} m, farm x {T["farm_x"][0]:.2f}-{T["farm_x"][1]:.2f}, Brow x {T["brow_x"][0]:.2f}-{T["brow_x"][1]:.2f}, ship '
                       f'{T["ship_length_m"]:.1f} m; insulated shell {T["shell_area_m2"]:,.0f} m² (CP1 {T["cp1_shell_area_m2"]:,.0f}).</p>'
                       + table(['Species', 'Need m³', 'Capacity m³', 'Fill'], fl) + table(['Vessel', 'Species', 'Class', 'x', 'm³', 'Propellant t', 'Burn axial kN'], vs)
                       + '<p class="fn">' + E('; '.join(f'{k}: {v}' for k, v in T['supports'].items() if k != 'burn_axial_kN_total')) + '. Forward interfaces: '
                       + E('; '.join(T['interfaces'])) + '.</p>'))
    # MRU and module 10
    it = [[E(i['name']), f'{i["t"]:.1f}', f'{i["env"]["L"]:.1f} x {i["env"]["D"]:.1f}', E(i['handling']), E(i['service'])] for i in MR['items']]
    nf = [[E(n), f'{d:.2f}'] for n, d in MR['flight']['nearest'][:5]]
    fx = [[E(f['id']), E(f['name']), E(f['interface']), f'{f["mass_t"]:.1f}'] for f in MR['fixtures']]
    out.append(section('c3', 'Consolidation · maintenance', 'Heavy maintenance transport (MRU) and body-bay module 10',
                       f'<p>{E(MR["claim"])}. The carriage (rated {MR["rating_t"]:.1f} t) runs on twin rails at az 255/285 (a single rail under the load would sit '
                       f'{MR["rail"]["single_rail_clear_to_bus3_m"]:.2f} m from bus 3). Swept volumes use full envelopes: in flight the largest item is the '
                       f'{E(MR["flight"]["item"])} (tube r {MR["flight"]["swept_radius_m"]:.2f} m at lane radius 2.9), which clears everything; the yard route for the '
                       f'{E(MR["yard"]["item"])} (r {MR["yard"]["swept_radius_m"]:.2f} m) needs {", ".join(MR["yard"]["remove_first"])} unbolted first.</p>'
                       + table(['Item', 't', 'Envelope L x D (m)', 'Handling', 'Service'], it)
                       + '<h3>In-flight swept tube: nearest neighbours (m)</h3>' + table(['Neighbour', 'Clear m'], nf)
                       + '<h3>Fixtures and transfer</h3>' + table(['Id', 'Fixture', 'Interface', 't'], fx)
                       + '<ol>' + ''.join(f'<li>{E(x)}</li>' for x in MR['sequence']) + '</ol>'
                       + f'<p>Burn restraint: {E(MR["burn"]["restraint"])}. Recovery: ' + E('; '.join(MR['recovery'])) + '.</p>'
                       + f'<p>Decay heat of a unit: {MR["decay"]["t_1h_W"]/1e3:.0f} kW after 1 h, {MR["decay"]["t_1d_W"]/1e3:.0f} kW after a day, '
                       f'{MR["decay"]["t_30d_W"]/1e3:.0f} kW after 30 days. {E(MR["external"]["item"])}: {E(MR["external"]["interface"])}.</p>'
                       + img('cam_i3d_x_mru', 'MRU', 'MRU twin rails, cradle, park station and the two swept tubes (amber in flight, red yard) beside the power units.')
                       + f'<h3>Module 10</h3><p>x {M10["x"][0]:.2f}-{M10["x"][1]:.2f}, {M10["containers"]} containers, closest clearance {M10["clearance_m"]:.2f} m; defense buffers '
                       f'retained +{M10["buffer_shift_m"]:.0f} m. {E(M10["removal"]["in_flight"])}; {E(M10["removal"]["finding"])}.</p>'
                       + table(['Interface', 'What', 'Owner'], [[E(r['interface']), E(r['what']), E(r['owner'])] for r in M10['standard']])
                       + '<p class="fn">' + E('; '.join(f'{k}: {v}' for k, v in M10['ownership'].items())) + '.</p>'))
    # electrical, L2 failure, ECLSS, cryo
    er = [[E(r['id']), E(r['supply']), f'{r["installed_W"]/1e6:.1f}', f'{r["proactive_W"]/1e6:.2f}', f'{r["reactive_W"]/1e6:.2f}', f'{r["peak_W"]/1e6:.1f}'] for r in EL['rows']]
    st = [[E(s['state']), E(s['L1']), E(s['L2']), E(s['buffer']), 'OK' if s['ok'] else 'LIMIT'] for s in EL['states']] if 'states' in EL else []
    cr = [[E(s['stage']), f'{s["leak_W"]:.0f}', f'{s["nuclear_W"]:.0f}', f'{s["lift_W"]:.0f}', f'{s["W_per_W"]:.0f}', f'{s.get("input_at_T_W", s["input_W"])/1e3:.0f}'] for s in CR['stages']]
    fw = [[E(k), f'{v/1e3:+.1f}'] for k, v in CR['flows']]
    sens = [[f'x{s["nuclear"]:.1f}', f'{s["input_W"]/1e3:.0f}'] for s in CR['sensitivity']]
    ecl = [[E(k), 'pass' if v else '<b>FAIL</b>'] for k, v in EC['matrix'].items()]
    fe = EC['failing_eval']
    out.append(section('c4', 'Consolidation · power, cooling, life support', 'Electrical, L2 cooling redundancy, ECLSS and cryogenics',
                       f'<p><b>L1.</b> Continuous {EL["continuous_W"]/1e6:.1f} MW (proactive burn, heat-pump duty retired), reactive peak {EL["reactive_W"]/1e6:.1f} MW inside the '
                       f'100 MWe FT-04 converter rating; the 21 MW defense burst comes from the buffer. L1 conductors are sized for the peak: {EL["conductor"]["A_peak_mm2"]:,.0f} mm² per '
                       f'pole ({EL["conductor"]["mass_new_t"]:.2f} t, inside the 8 t distribution line). Pickup losses {EL["thermal"]["pickup_loss_peak_W"]/1e6:.0f} MW at the peak go '
                       f'to the HOT loop (in the budget above). Buffer recharge {EL["buffer_recharge_s"]["EOL"]:.0f} s from the L2 surplus ({EL["surplus_W"]["EOL"]/1e6:.2f} MW EOL '
                       f'after the cryo increase). {E(EL["note"])}</p>'
                       + table(['Load', 'Supply', 'Installed MW', 'Proactive MW', 'Reactive MW', 'Peak MW'], er)
                       + f'<p><b>NaK loop loss.</b> {E(LF["case"])}. Safe state: {E(LF["derating"])}. Highest demand band sheds {LF["shed_W"]/1e6:.2f} MW. The overloaded blade gains '
                       f'50 K in {LF["transient"]["t_to_plus50K_s"]:.0f} s, so the valve rebias (&lt; 2 s) and TAC bypass (&lt; 5 s) act long before. Recovery: '
                       + E('; '.join(LF['recovery'])) + '.</p>'
                       + f'<p><b>ECLSS.</b> Seven four-person units pass {EC["passes"]} of {EC["of"]} expanded cases. The failing case ({E(EC["failing"])}) leaves '
                       f'{fe["overload_persons"]} people over capacity: {fe["co2_kg_day"]:.1f} kg/d of CO2, bridged by a {fe["reserve_days"]}-day LiOH reserve '
                       f'({fe["lioh_t"]:.2f} t). {E(fe["reliability"])}.</p>' + table(['Case', 'Seven units'], ecl)
                       + f'<p><b>Cryogenics.</b> {E(CR["explain"])} {E(CR["redundancy"])}. {E(CR["radiation_note"])}.</p>'
                       + table(['Stage', 'Leak W', 'Nuclear W', 'Lift W', 'W/W', f'Input kW at {CR["T_reject_K"]:.0f} K'], cr)
                       + table(['Energy flow', 'kW'], fw) + '<h3>Nuclear-heating sensitivity (input kW at 300 K)</h3>' + table(['Nuclear heating', 'Input kW'], sens)))
    # ledger
    cats = {}
    for r in L['rows']: cats.setdefault(r['cat'], []).append(r)
    lr = [[E(r['item']), E(r['cat']), E(r['owner']), f'{r["t"]:.2f}', E(r['note'])] for r in L['rows']]
    hist = L['end_t']-L['dry_with_payload_t']-L['tankage_t']
    summ = [['Existing historical ship (production dry mass incl. payload, unchanged)', f'{hist:,.0f}'],
            ['New equipment', f'{sum(r["t"] for r in cats.get("NEW", [])):,.1f}'], ['Replacement equipment (increment)', f'{sum(r["t"] for r in cats.get("REPLACEMENT", [])):,.1f}'],
            ['Historical equipment moved', f'{sum(r["t"] for r in cats.get("HISTORICAL (moved)", [])):,.1f}'],
            ['Coolant inventory (NaK transport, inside the loop line)', f'{L["coolant"]["NaK_t"]:,.1f}'],
            ['Mission payload additions', f'{sum(p["t"] for p in L["payload"]):,.2f}'], ['Propellant', f'{L["propellant_t"]:,.0f}'], ['Added tankage', f'{L["tankage_t"]:,.0f}'],
            ['Structural additions confirmed by PSA', '0 (none confirmed yet)'], ['Structural additions OPEN', 'OPEN (PSA Phase II)'], ['Shielding additions OPEN', 'OPEN (Track R)'],
            ['<b>Nominal departure</b>', f'<b>{L["departure_t"]:,.0f}</b>']]
    out.append(section('c5', 'Consolidation · mass', 'Reconciled live mass ledger (supersedes Checkpoint 4)',
                       '<p>Every physical item has one owner. Audit results: restart packs were in both the L2 and the storage lines (removed from L2); new cryocooler stations '
                       'count only their increment over the existing coolers; pipe supports (saddles, slides) are ISSA machinery, the frames they bear on are PSA; module-10 '
                       'racks are ISSA, its frames PSA; displaced dry-store containers keep their historical mass; LOG-G1 tare is separate and not duplicated.</p>'
                       + table(['Category', 't'], summ) + table(['Item', 'Category', 'Owner', 't', 'Note'], lr)))
    # registers, SSI, problems
    rg = [[E(a), E(b), E(c)] for a, b, c in C['registry']]
    ss = [[E(i['id']), E(i['owner']), f'{i["mass_t"]:.1f}' if isinstance(i['mass_t'], (int, float)) else 'PSA', str(len(i['mounts'])), E(i['maturity'])] for i in S['items']]
    ds = [[E(d['id']), E(d['topic']), E(d['issa']), E(d['psa']), E(d['action'])] for d in S['disagreements']]
    pr = [[E(p['id']), E(p['sev']), E(p['what']), E(p['owner'])] for p in C['problems']]
    oq = [[E(q['id']), E(q['q']), E(q['rec'])] for q in C['owner_questions']]
    out.append(section('c6', 'Consolidation · handover', 'Registers, systems-to-structure interface and open problems',
                       '<p>Technology register v1.1 (<code>data/technology_register.toml</code>): FT-03 carries the approved component set (0.94 / 0.90 / 0.97 / 2 %, 872 K '
                       'compressor inlet, 896 K L2, 9.38 m); FT-06 the forward-pointing fins (1.47 m pitch, 106 manifolds per blade); FT-07 the 24.7 t MRU carriage and the '
                       'provisional EXT-TA arm, with the explicit limit that carrying a reactor-class mass is not in-flight reactor servicing.</p>'
                       + table(['System', 'Level (CP4)', 'Level (C1.0)'], rg)
                       + f'<h3>Systems-to-structure interface {E(S["version"])}</h3><p>{E(S["ownership_rule"])}. File: '
                       '<code style="overflow-wrap:anywhere">work/ship-systems-architecture/results/i3d_structure_interface.json</code> (position, mass, CG, envelope, mounts with anchor/slide type, load '
                       'cases, thermal growth, clearances, removal, utilities, environment, failure requirements; TAC and EM-pump excitation bands for PSA modal work).</p>'
                       + table(['Item', 'Owner', 't', 'Mounts', 'Maturity'], ss)
                       + '<h3>Disagreements with PSA (not overridden)</h3>' + table(['Id', 'Topic', 'ISSA', 'PSA', 'Action'], ds)
                       + '<h3>Problem register</h3>' + table(['Id', 'State', 'Problem', 'Owner'], pr)
                       + '<h3>Owner questions</h3>' + table(['Id', 'Question', 'Recommendation'], oq)
                       + '<p class="fn">Review file: view layers C1 complete, C2 exterior, C3 structure and interfaces, C4 thermal, C5 electrical, C6 habitat and life support, '
                       'C7 logistics and maintenance, C8 research and fiction comparison. Machinery is solid; reservations, swept tubes and the translated Brow are '
                       'translucent; SSI markers are red (anchor), blue (slide) and white (other). Software checks passing does not establish physical feasibility.</p>'))
    return '\n'.join(out)
