"""ISSA Phase VI page sections (dual-baseline integration, deliverables 1-15), inserted above Phase V into results/issa.html by
build_report.py. Reads results/phase6.json, the two configs and data/technology_register.toml. Pure Python."""
import html
import json
import sys
import tomllib
from pathlib import Path

W = Path(__file__).resolve().parents[1]; R = W/'results'; ROOT = W.parents[1]
for p in ('phase2', 'phase3', 'phase4', 'phase5'):
    sys.path.insert(0, str(W/p))
from report2 import table, section  # noqa: E402
from report3 import ok  # noqa: E402

E = html.escape
TR = '<span class="chip c-model">TRACK R · RESEARCH</span>'
TF = '<span class="chip c-warn">TRACK F · FICTIONAL</span>'


def t3(v, d=0, k=1.0):
    return f'{v[0]/k:,.{d}f}–{v[2]/k:,.{d}f} <span class="nom">({v[1]/k:,.{d}f})</span>'


def img(name, alt, cap):
    return (f'<figure><img src="{name}.jpg" alt="{E(alt)}" loading="lazy" style="width:100%;border-radius:6px">'
            f'<figcaption class="fn">{cap}</figcaption></figure>') if (R/f'{name}.jpg').exists() else ''


def build():
    P = json.loads((R/'phase6.json').read_text()); REG = tomllib.loads((ROOT/'data/technology_register.toml').read_text())
    C = P['configs']; RC = P['reconciliation']; RF = P['radiators']; DC = P['direct_conversion']; M = P['mass']; T = P['tanks']; A = P['accel']
    out = []
    ids = ' · '.join(f'<span class="chip c-sim">{E(C[k]["id"])} · {E(C[k]["hash"])}</span>' for k in ('R', 'F0', 'F1'))
    # w1 reconciliation
    m = RC['mass']
    rows = [[E(d['item']), f'{d["convergence_t"]:.1f}', f'{d["mass_fictional_t"]:.1f}', f'{d["delta_t"]:+.1f}', E(d['cause'])] for d in m['items']]
    corr = [[E(c['id']), E(c['item']), E(c['fix'])] for c in RC['corrections']]
    out.append(section('w1', 'VI-A · 1', 'Phase V reconciliation', f'{ids}<p>The two nominal fictional departures were two configurations, not one ship: '
                       f'{m["convergence_departure_t"]:,.0f} t (convergence row) and {m["mass_fictional_departure_t"]:,.0f} t (full item list). The difference '
                       f'is {m["sum_delta_t"]:.0f} t of dry mass:</p>'
                       + table(['Item', 'Convergence row (t)', 'Mass list (t)', 'Δ (t)', 'Cause'], rows)
                       + f'<p class="fn">{E(m["verdict"])}</p><h3>All Phase VI corrections</h3>' + table(['Id', 'Item', 'Correction'], corr)))
    # w2 configurations
    def cfgrow(k):
        c = C[k]; g = c['generation']['L2']
        return [E(c['id']), E(c['track']), f'{g["turbine_inlet_K"]:.0f} / {g["reject_K"]:.0f} K, η {g["eta"]:.3f}', E(c['generation']['L1']['type']),
                f'{c["radiators"]["L2"]["length_m"]:.1f} m', E(c['hot_loop']['wall']), t3(c['mass']['departure_t']), E(', '.join(c['register_refs']) or '–')]
    out.append(section('w2', 'VI-A · 2', 'Two baselines, machine-readable', '<p>Files: <code>results/phase6_config_R.json</code> (Track R) and '
                       '<code>results/phase6_config_F.json</code> (F1 = Track F reference, owner 2026-11-28; F0 = without FT-03). Each carries its id, hash, item list '
                       'and register references; production geometry and canon are unchanged.</p>'
                       + table(['Config', 'Track', 'L2 turbine inlet / reject', 'L1', 'L2 section', 'Hot-loop wall', 'Departure (t)', 'Register'], [cfgrow(k) for k in ('R', 'F0', 'F1')])))
    # w3 electrical
    E6 = RC['electrical']; hp = E6['heat_pump']
    erows = [[E(r['id']), E(r['title']), f'{r["installed_W"]/1e6:.2f}', f'{r["continuous_proactive_burn_W"]/1e6:.2f}', f'{r["continuous_reactive_burn_W"]/1e6:.2f}',
              f'{r["intermittent_W"]/1e6:.2f}', f'{r["peak_W"]/1e6:.2f}', f'{r["storage_discharge_W"]/1e6:.1f}', E(r['cls'])] for r in E6['R']]
    out.append(section('w3', 'VI-A · 3', 'Electrical demand by kind', f'<p>Phase V summed {E6["sum_R"]["phase5_counted_W"]/1e6:.0f} MW of L1 because it counted the installed '
                       f'{hp["installed_W"]/1e6:.0f} MW heat-pump rating and the 50 MW pulse discharge as continuous. Under the working proactive doctrine the continuous L1 '
                       f'load in a burn is <b>{E6["sum_R"]["continuous_proactive_W"]/1e6:.1f} MW</b>; a reactive defense in a burn peaks at '
                       f'{E6["sum_R"]["continuous_reactive_W"]/1e6:.0f} MW at burnout (heat pumps {hp["reactive_peak_W"]/1e6:.0f} MW, burn mean ~{hp["reactive_mean_W"]/1e6:.0f} MW). '
                       f'The 210 MW rating stays installed canon equipment. The WARM shortfall ({P["warm_shortfall_W"]/1e6:.2f} MW) is lifted into HOT by those pumps for '
                       f'{hp["proactive_W"]/1e6:.1f} MW of work.</p>'
                       + table(['Id', 'Item', 'Installed MW', 'Continuous, proactive burn', 'Continuous, reactive burn', 'Intermittent', 'Peak', 'Storage discharge', 'Class'], erows)))
    # w4 radiators
    rc = RC['radiators']
    f_rows = [[E(f['case']), f'{f["capacity_W"]/1e6:.1f}', f'{f["load_W"]/1e6:.1f}', f'{100*f["margin"]:+.0f} %', f'{f["max_output_W"]/1e6:.1f}', E(f['note'])] for f in rc['l2_failures']]
    h_rows = [[E(f['case']), f'{f["capacity_W"]/1e9:.2f}', f'{100*f["margin"]:+.0f} %', ok(f['meets_20pct'], 'yes', 'no'), f'{100*f["drive_power_at_20pct"]:.0f} %'] for f in rc['hot_failures']]
    found = [[E(f['where']), E(f['was']), E(f['now']), E(f['effect'])] for f in rc['found']]
    scan = [[f'{x["T_K"]:.0f}', f'{x["eta"]:.3f}', f'{x["reactor_MWt"]:.1f}', f'{x["length_m"]:.1f}', ok(x['within_research_reactor_power'], 'yes', 'no')] for x in RF['scan']]
    out.append(section('w4', 'VI-A · 4 / VI-C', 'Radiators: 750 K consistency and the F1 section',
                       '<h3>700 K values removed from the 750 K configuration</h3>' + table(['Where', 'Was', 'Now', 'Effect'], found)
                       + '<h3>L2 sections after a failure (strategy C, part-load efficiency)</h3>' + table(['Case', 'Capacity MW', 'Load MW', 'Margin', 'Max L2 output MWe', 'Note'], f_rows)
                       + '<h3>HOT after a cooling-section failure (R5-A length)</h3>' + table(['Case', 'Capacity GW', 'Margin', '≥ 20 %', 'Drive power at 20 %'], h_rows)
                       + f'<h3>{TF} FT-03: 1500 K turbine inlet</h3><p>F1 takes the rejection temperature that frees the most hot length while the reactor stays at or below the '
                         f'research thermal power: <b>{RF["F1"]["T_K"]:.0f} K, {RF["F1"]["length_m"]:.1f} m</b> instead of {RF["R"]["length_m"]:.1f} m. HOT headroom under the 20 % rule: '
                         f'{RF["R"]["hot_headroom_W"]/1e6:.0f} MW (R, F0) → <b>{RF["F1"]["hot_headroom_W"]/1e6:,.0f} MW</b> (F1).</p>'
                       + table(['Reject K', 'η', 'Reactor MWt', 'Section m', 'Reactor ≤ research'], scan)))
    # w5 direct conversion
    lg = DC['F1']['ledger']
    drows = [[E(r['state']), r['case'], f'{r["eta"]:.2f}', f'{r["P_e_W"]/1e6:.1f}', f'{r["loss_to_hot_loop_W"]/1e6:.1f}', f'{r["thrust_change_rel"]:.1e}',
              ok(r['fits_hot_headroom'], 'fits', 'exceeds')] for v in ('F0', 'F1') for r in DC[v]['rows'] if r['case'] == 'nom']
    labels = ['F0', 'F0', 'F1', 'F1']
    drows = [[labels[i]]+r for i, r in enumerate(drows)]
    phys = [[E(x['principle']), E(x['precedent']), E(x['limit'])] for x in DC['F1']['physics']]
    buf = [[f'{b["rate_Hz"]:.0f}', f'{b["P_e_W"]/1e6:.0f}', f'{b["energy_per_pulse_J"]/1e6:.2f}', f'{b["capacitor_t"]:.2f}'] for b in DC['F1']['buffer']]
    lr = P['l1_research_reject']
    out.append(section('w5', 'VI-C', f'{TF} L1 direct conversion (FT-04, conditional)',
                       f'<p>Ledger per second of burn: fusion {lg["fusion_W"]/1e12:.0f} TW = jet {lg["jet_W"]/1e12:.0f} TW + absorbed {lg["absorbed_W"]/1e9:.1f} GW + other '
                       f'{lg["other_W"]/1e12:.0f} TW. The pickup takes P<sub>e</sub>/η from the jet; at constant mass flow thrust falls by half that share. {E(lg["note"])}.</p>'
                       + table(['Config', 'State', 'Case', 'η', 'P_e MW', 'Loss to HOT MW', 'ΔF/F', 'HOT headroom'], drows)
                       + f'<p>{E(DC["F1"]["thermal"])}</p><p>{TR} Thermal L1 rejects {lr["reject_W"]/1e6:.0f} MW at 900 K; a 900 K section would need {lr["section_900K_m"]:.1f} m of '
                         f'hot length: {ok(lr["fits"], "fits", "does not fit")} after R5-A. {E(DC["F1"]["startup"]["rule"])}.</p>'
                       + '<h3>Physical principles and precedent</h3>' + table(['Principle', 'Precedent', 'Limit'], phys)
                       + '<h3>Pulse buffer (pulse rate OPEN in canon)</h3>' + table(['Rate Hz', 'P_e MW', 'Energy per pulse MJ', 'Capacitor t'], buf)))
    # w6 register
    rr = [[E(t['id']), E(t['name']), E(t['status']), E(t['level']), E(t['limitation']), E(t['advance']), E(', '.join(t.get('dependents', []))), E(t['consequence'])]
          for t in REG['technology']]
    out.append(section('w6', 'VI-B', 'Fictional technology register', f'<p>{E(REG["register"]["civilization"])}</p><p class="fn">Persistent file: '
                       '<code>data/technology_register.toml</code> (noncanon working register; principle, precedent and adopted properties are in the file).</p>'
                       + table(['Id', 'Technology', 'Status', 'Level', "Today's limit", 'Advance', 'Depends on it', 'If not met'], rr)))
    # w7 mass
    def mrow(k):
        cs = M[k]['cases']
        return [E(C[k]['id']), t3([c['dry_added_t'] for c in cs]), t3([c['propellant_t'] for c in cs]), t3([c['tankage_t'] for c in cs]), t3([c['departure_t'] for c in cs]),
                f'{A[k][1]["a_departure_g"]:.2f} → {A[k][1]["a_end_g"]:.2f} g', f'{A[k][1]["burn_days_total"]:.0f} d', f'{M[k]["attitude"]["cg_shift_m"]:+.0f} m',
                f'×{M[k]["attitude"]["I_pitch_ratio"]:.2f}']
    items = [[E(k), t3(v['t'], 1), E(v['cls'])] for k, v in M['F1']['items'].items()]
    trow = [[E(C[k]['id']), f'{r["max_fill"]:.2f}', f'{r["extension_m"]:.1f} m', f'{r["ship_length_m"]:.1f} m'] for k in ('R', 'F0', 'F1') for r in T[k]['rows'] if r['case'] == 'nom']
    out.append(section('w7', 'VI-D', 'Mass, tanks and acceleration (coupled)', '<p>Power-limited drive: the heavier ship accelerates less, so the head in the hot loop and its walls '
                       'fall; the H6a line is iterated on the coupled peak acceleration. Thrust is constant, so the thrust structure carries the same 21.8 MN; tank supports carry the '
                       'propellant share of it.</p>' + table(['Config', 'Dry added (t)', 'Propellant (t)', 'Tankage (t)', 'Departure (t)', 'Acceleration', 'Burn time', 'Dry CoM shift', 'Pitch inertia'],
                                                              [mrow(k) for k in ('R', 'F0', 'F1')])
                       + '<h3>F1 added items</h3>' + table(['Item', 't', 'Class'], items)
                       + '<h3>Tank farm (nominal)</h3>' + table(['Config', 'Max fill', 'Vessel extension', 'Ship length if lengthened'], trow)
                       + f'<p class="fn">Options: {E("; ".join(T["F1"]["options"]))}. The 3D integration stage compares them before any extension is chosen.</p>'))
    # w8 ECLSS + logistics
    EC = RC['eclss']; LG = RC['logistics']
    cases = list(EC['layouts'][0]['results'])
    erows = [[E(l['layout']), f'{l["mass_t"]:.1f}'] + [ok(l['results'][c], 'ok', 'fail') for c in cases] for l in EC['layouts']]
    out.append(section('w8', 'VI-C', 'Life support and logistics', f'<p>{E(EC["rotary"]["verdict"])}</p>'
                       + table(['Layout', 't'] + [E(c) for c in cases], erows)
                       + f'<p class="fn">{E(EC["bug_fixed"])}. Rotary interfaces per ring: {E("; ".join(EC["rotary"]["per_ring"]))}. {E(EC["rotary"]["consumables"])}.</p>'
                       + f'<p>LOG-G1: {E(LG["container"]["fittings"])}; {E(LG["container"]["hatch"])}; {E(LG["container"]["route"])}. {E(LG["accounting"]["note"])}.</p>'))
    # w9 cryo / preheat
    CR = RC['cryo']; pre = RC['preheat']
    crow = [[E(c['load']), f'{c["he3_nuclear_W"]:.0f}', f'{c["he3_required_W"]:.0f}', f'{c["he3_installed_W"]:.0f}', f'{c["h_d_nuclear_W"]:.0f}', f'{c["added_input_W"]/1e3:.0f}']
            for c in CR.get('cases', [])]
    out.append(section('w9', 'VI-A · 4', 'Cryogenic cooling and startup', f'<p>{E(CR["note"])}</p>'
                       + (table(['Load', 'He-3 nuclear W', 'He-3 required W', 'He-3 installed W (×1.25)', 'H/D nuclear W', 'Added input kW'], crow) if crow else '<p>OpenMC species heating not run.</p>')
                       + f'<p>Preheat (thaw + blade): {pre["R"]["hours_on_L2"]["BOL"]:.0f}–{pre["R"]["hours_on_L2"]["EOL"]:.0f} h on the L2 coast surplus, '
                         f'{pre["R"]["hours_one_unit_black_start"]:.0f} h on one unit after a black start; melt point to operating temperature from the drive at 10 % power in '
                         f'{pre["R"]["drive_10pct_minutes"]:.0f} min. {E(pre["note"])}</p>'))
    # w10 OpenMC
    rad = P['radiation']
    if rad.get('runs'):
        V = rad['runs']['V6']; Dd = rad['runs']['D']
        vrows = [[k, f'{v["mean"]:.3f}', f'{v["min"]:.2f}–{v["max"]:.2f}', ok(v['passes'])] for k, v in V.items()]
        def _v(x, e): return f'{x:.2e} ±{100*e:.0f} %' if x and e == e else '0 (no score)'
        drow = [[f'{d["t_cm"]:.0f}', 'yes' if d['weight_windows'] else 'no', f'{d["analytic"]:.2e}', _v(d['openmc'], d['rel_err']),
                 f'{d["ratio"]:.2f}' if d.get('ratio') else '–', _v(d.get('total', 0), d.get('total_rel_err', float('nan'))),
                 f'{d["fom"]:.2g}' if d.get('fom') else '–', f'{d["runtime_s"]:.0f}'] for d in Dd]
        sp = rad.get('summary', {})
        srows = [[E(k), f'{v["W"]:.1f}', f'±{100*v["rel"]:.0f} %'] for k, v in sp.get('components', {}).items()]
        body = (f'{TR}<p>{E(rad["status"])}. Source provenance: {E(rad["source_provenance"]["spectrum"])}, k<sub>eff</sub> {rad["source_provenance"]["k_eff"]:.3f}.</p>'
                + '<h3>Void verification</h3>' + table(['Particle', 'Mean ratio', 'Range', 'Pass'], vrows)
                + '<h3>Deep-penetration benchmark (2 MeV pencil, shield material)</h3>' + table(['Thickness cm', 'Weight windows', 'Uncollided exp(−Σt·t)', 'Uncollided OpenMC', 'Ratio', 'Total transmission', 'FOM', 's'], drow)
                + '<p class="fn">Uncollided transmission checks the data and normalisation where it is measurable; deep penetration is the collided flux, which the analog runs stop scoring at 60 cm and the MAGIC weight windows (split cap 20) carry further. A zero is a missing score, not a zero flux.</p>'
                + ('<h3>Tank heating by component (three units, C load)</h3>' + table(['Component', 'W', 'Statistical'], srows) if srows else '')
                + f'<p class="fn">{E(sp.get("finding", ""))}</p>')
    else:
        body = '<p>Not run.</p>'
    out.append(section('w10', 'VI-E', 'OpenMC research status', body))
    # w11 integration geometry
    LAY = P['layout']; fams = {}
    for a in LAY: fams[a['family']] = fams.get(a['family'], 0)+1
    chk = json.loads((R/'phase6_review_checks.json').read_text()) if (R/'phase6_review_checks.json').exists() else {}
    figs = ''.join(img(n, a, c) for n, a, c in (
        ('cam_issa6_overview', 'Whole ship with the Track F1 assemblies', 'Track F1 development configuration, whole ship: production model plus the ISSA assemblies (engineering colours).'),
        ('cam_issa6_district', 'Power district close-up', 'Three L2 units: reactor and shield envelopes (yellow, adjustable), TAC, recuperator, gas cooler, PMAD, mount rings, restart packs.'),
        ('cam_issa6_hot_network', 'H6a network aft end', 'H6a aft end: trunk pairs, EM pumps, accumulators, drain/recovery tanks, section valves.'),
        ('cam_issa6_hub', 'Stationary hub', 'Hub: ECLSS hub unit and duct to both rotary couplings, LOG-G1 containers, rail, workshop, spares.'),
        ('cam_issa6_section_x86', 'Transverse section at x -85.5', 'Transverse section through the district at x −85.5 (looking aft).'),
        ('cam_issa6_section_x40', 'Transverse section at x 40', 'Transverse section at x 40: the three blades and the F1 L2 sections.'),
        ('cam_issa6_section_long', 'Longitudinal section', 'Longitudinal section at y 0: district, trunks, buses, hub and tank extension envelope.')))
    out.append(section('w11', 'VI-C', f'{TF} Integration geometry', f'<p>{len(LAY)} assemblies in {len(fams)} families, built from <code>phase6.json</code> by '
                       f'<code>make_review6.py</code> into <code>REVIEW_ISSA_PHASE6.blend</code> (WORK_ISSA6_F1_* collections, one per family). '
                       f'Families: {E(", ".join(f"{k} {v}" for k, v in fams.items()))}. Screens: {chk.get("objects", "–")} objects, unique ids '
                       f'{ok(chk.get("unique_ids"), "yes", "no")}, {chk.get("production_overlaps", "–")} bounding-box overlaps with production meshes and '
                       f'{chk.get("cross_family_overlaps", "–")} across families (screens, not collision proofs).</p>' + figs))
    # w12 problems + decisions
    pr = [[E(p['id']), E(p['track']), E(p['sev']), E(p['text'])] for p in P['problems']]
    dr = [[E(d['id']), E(d['q']), E(d['rec'])] for d in P['decisions']]
    out.append(section('w12', 'VI', 'Problems and decisions', table(['Id', 'Track', 'Severity', 'Problem'], pr) + table(['Id', 'Question', 'Recommendation'], dr)))
    return '\n'.join(out)
