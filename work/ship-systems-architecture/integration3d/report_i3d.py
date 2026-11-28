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
    return '\n'.join(out)+build_cp2()


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
