"""ISSA Phase III page sections (deliverables 1-14), inserted above Phase II into results/issa.html by build_report.py.
Reads results/phase3.json and results/phase3_eps_g1.json. Pure Python, inline SVG with the page's theme tokens.
"""
import html
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]/'results'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'phase2'))
from report2 import b, t3, table, bars, box, arrow, DEFS, section  # noqa: E402

E = html.escape
TAG = {'MODEL-DERIVED': 'c-model', 'STUDY': 'c-sim', 'PROTOTYPE': 'c-concept', 'SPECULATIVE': 'c-warn', 'OPEN': 'c-warn'}


def tag(c):
    k = c.split(' ')[0]
    return f'<span class="chip {TAG.get(k, "")}" style="padding:2px 5px;font-size:10px">{E(c)}</span>'


def ok(v, yes='pass', no='FAIL'):
    return f'<span class="good">{yes}</span>' if v else f'<span class="bad">{no}</span>'


def waterfall(cands, w=860):
    """stacked horizontal bars: dry added by category, then coupled propellant + tankage, per candidate (nominal)."""
    cats = [('L1', 'bad'), ('L2', 'action'), ('L3', 'good'), ('thermal', 'warn'), ('storage', 'info'), ('distribution', 'muted'),
            ('radiator_structure', 'accent'), ('cargo', 'line')]
    rows = [c for c in cands if c['name'] != cands[0]['name']]
    mx = max(c['extra_departure_t'][1] for c in rows)
    lw = 300; sc = (w-lw-70)/mx; bh = 26; H = len(rows)*(bh*2+16)+40
    s = [f'<svg viewBox="0 0 {w} {H}" role="img" aria-label="mass waterfall">']
    for i, c in enumerate(rows):
        y = 10+i*(bh*2+16); x = lw
        s.append(f'<text x="{lw-8}" y="{y+bh*0.7}" text-anchor="end" style="fill:var(--ink);font:12px IBM Plex Sans,sans-serif">{E(c["name"][:44])}</text>')
        for k, tone in cats:
            v = c['items_t'].get(k, [0, 0, 0])[1]
            if v <= 0: continue
            s.append(f'<rect x="{x:.1f}" y="{y}" width="{v*sc:.1f}" height="{bh}" style="fill:var(--{tone});opacity:.85"><title>{k} {v:.0f} t</title></rect>')
            x += v*sc
        s.append(f'<text x="{x+6:.1f}" y="{y+bh*0.7}" style="fill:var(--muted);font:11px IBM Plex Mono,monospace">dry +{c["dry_added_t"][1]:.0f} t</text>')
        yp = y+bh+4; p = c['extra_departure_t'][1]-c['dry_added_t'][1]
        s.append(f'<rect x="{lw}" y="{yp}" width="{c["dry_added_t"][1]*sc:.1f}" height="{bh-8}" style="fill:var(--line)"/>')
        s.append(f'<rect x="{lw+c["dry_added_t"][1]*sc:.1f}" y="{yp}" width="{p*sc:.1f}" height="{bh-8}" style="fill:var(--info);opacity:.45"><title>propellant + tankage {p:.0f} t</title></rect>')
        s.append(f'<text x="{lw-8}" y="{yp+bh*0.55}" text-anchor="end" style="fill:var(--muted);font:11px IBM Plex Mono,monospace">departure</text>')
        s.append(f'<text x="{lw+c["extra_departure_t"][1]*sc+6:.1f}" y="{yp+bh*0.55}" style="fill:var(--muted);font:11px IBM Plex Mono,monospace">+{c["extra_departure_t"][1]:,.0f} t</text>')
    ly = H-18; lx = lw
    for k, tone in cats:
        s.append(f'<rect x="{lx}" y="{ly}" width="10" height="10" style="fill:var(--{tone})"/><text x="{lx+14}" y="{ly+9}" style="fill:var(--muted);font:10px IBM Plex Mono,monospace">{k.replace("_", " ")}</text>')
        lx += 14+7*len(k)+14
    s.append('</svg>')
    return '<figure><div class="frame">'+''.join(s)+'</div><figcaption class="fn">Nominal tonnes. Upper bar: dry mass added by category. Lower bar: the same plus the coupled propellant and tankage it drags to departure (operating_point.mission closed form).</figcaption></figure>'


def fig_deps():
    """shared-dependency diagram for the redundancy model."""
    s = [f'<svg viewBox="0 0 900 300" role="img" aria-label="shared dependencies">', DEFS]
    units = [('U1', 90, 'A', 'M1'), ('U2', 210, 'B', 'M1'), ('U3', 330, 'A', 'M1'), ('U4', 210, 'B', 'M2')]
    for k, (u, bl, bus, mod) in enumerate(units):
        x = 60+k*200
        s.append(box(x, 120, 150, 44, f'{u} 1.75 MWe', f'{mod} · bus {bus}', 'action'))
    for j, bl in enumerate((90, 210, 330)):
        x = 110+j*270
        s.append(box(x, 20, 170, 44, f'Blade {bl} header', 'sector · repair 3-14 d', 'warn'))
    links = {0: 0, 1: 1, 2: 2, 3: 1}
    for k, j in links.items():
        s.append(arrow(195+j*270, 64, 135+k*200, 118, 'warn' if j == 1 else 'muted', 'd' if j == 1 else ''))
    s.append(box(60, 230, 230, 44, 'Bus A', 'cross-tie 1 h', 'info')); s.append(box(330, 230, 230, 44, 'Bus B', 'cross-tie 1 h', 'info'))
    s.append(box(600, 230, 260, 44, 'Common cause', 'software 1 d · design (perm.)', 'bad'))
    for k, (_, _, bus, _) in enumerate(units):
        s.append(arrow(135+k*200, 166, 175 if bus == 'A' else 445, 228, 'info'))
    s.append('<text x="450" y="296" text-anchor="middle" style="fill:var(--muted);font:11px IBM Plex Mono,monospace">C-lean: units 2 and 4 share blade 210 (dashed); four units on three blades always share one header</text></svg>')
    return '<figure><div class="frame">'+''.join(s)+'</div></figure>'


def fig_section_unit(G):
    """model-derived cross-section of the bay at a unit (looking forward): casing, bay, unit envelopes, slab, keel lane."""
    U = G['reference_unit']; B = G['bay']; sc = 40; cx, cy = 300, 260
    s = ['<svg viewBox="0 0 600 420" role="img" aria-label="unit cross-section">']
    s.append(f'<circle cx="{cx}" cy="{cy}" r="{B["casing_r"]*sc}" style="fill:none;stroke:var(--line);stroke-width:2"/>')
    s.append(f'<circle cx="{cx}" cy="{cy}" r="{B["r0"]*sc}" style="fill:var(--surf2);stroke:var(--line)"/>')
    for az, lab in ((90, 'unit + own blade'), (210, ''), (330, '')):
        import math
        a = math.radians(az)
        def P(r, t):
            return cx+(math.cos(a)*r-math.sin(a)*t)*sc, cy-(math.sin(a)*r+math.cos(a)*t)*sc
        pts = [P(B['r0'], -B['width']/2), P(B['r1'], -B['width']/2), P(B['r1'], B['width']/2), P(B['r0'], B['width']/2)]
        s.append('<polygon points="'+' '.join(f'{x:.0f},{y:.0f}' for x, y in pts)+'" style="fill:var(--dry);opacity:.35;stroke:var(--dry)"/>')
        x1, y1 = P(B['casing_r'], 0); x2, y2 = P(9.5, 0)
        s.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" style="stroke:var(--bad);stroke-width:5;opacity:.6"/>')
        if az == 90:
            vc = B['r0']+(B['r1']-B['r0'])/2; r = U['core_r_m']
            x, y = P(vc, 0); s.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r*sc:.0f}" style="fill:var(--bad);opacity:.8"/>')
            sl = next(e for e in U['envelopes'] if e['name'].startswith('Blade-facing'))
            q = [P(B['r0']+sl['v'][0], sl['w'][0]), P(B['r0']+min(sl['v'][1], B['casing_r']-B['r0']+0.6), sl['w'][0]),
                 P(B['r0']+min(sl['v'][1], B['casing_r']-B['r0']+0.6), sl['w'][1]), P(B['r0']+sl['v'][0], sl['w'][1])]
            s.append('<polygon points="'+' '.join(f'{x:.0f},{y:.0f}' for x, y in q)+'" style="fill:var(--muted);opacity:.55"/>')
    for az in (30, 150, 270):
        a = math.radians(az); x, y = cx+math.cos(a)*4.6*sc, cy-math.sin(a)*4.6*sc
        s.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="10" style="fill:none;stroke:var(--info);stroke-width:2"/>')
    s.append('<text x="12" y="20" style="fill:var(--ink);font:600 12px IBM Plex Sans,sans-serif">Section at a unit, looking forward (x ≈ −85 m)</text>')
    s.append('<text x="12" y="38" style="fill:var(--muted);font:11px IBM Plex Mono,monospace">casing r 5.6 · bays r 1.5–4.3 × 3.2 m at 90/210/330° · keel lanes (blue) 30/150/270°</text>')
    s.append('<text x="12" y="410" style="fill:var(--muted);font:11px IBM Plex Mono,monospace">red: core and blade roots · grey: blade-facing slab (1.6 m, reaches the casing gap)</text></svg>')
    return '<figure><div class="frame">'+''.join(s)+'</div></figure>'


def fig_transition(T):
    s = ['<svg viewBox="0 0 900 170" role="img" aria-label="burn to coast transition">']
    xs = [(0, 0.02, 'trip', 'bad'), (0.02, 0.2, 'battery (power-limited)', 'warn'), (0.2, 3.8, 'channel refill (OPEN 0.5–4 h)', 'bad'),
          (1.0, 4.5, 'L2 warm restart', 'info')]
    sc = 800/5.0
    for k, (a, b_, lab, tone) in enumerate(xs):
        y = 20+k*30
        s.append(f'<rect x="{50+a*sc:.0f}" y="{y}" width="{max(4, (b_-a)*sc):.0f}" height="20" rx="3" style="fill:var(--{tone});opacity:.55"/>')
        s.append(f'<text x="{56+b_*sc:.0f}" y="{y+15}" style="fill:var(--ink);font:11px IBM Plex Sans,sans-serif">{E(lab)}</text>')
    s.append(f'<rect x="50" y="142" width="{3.8*sc:.0f}" height="8" style="fill:var(--bad)"/><text x="{56+3.8*sc:.0f}" y="150" style="fill:var(--bad);font:600 11px IBM Plex Mono,monospace">no proactive defense: 0.3–3.8 h</text>')
    for h in range(6):
        s.append(f'<text x="{50+h*sc:.0f}" y="166" text-anchor="middle" style="fill:var(--muted);font:10px IBM Plex Mono,monospace">{h} h</text>')
    s.append('</svg>')
    return '<figure><div class="frame">'+''.join(s)+'</div><figcaption class="fn">Today\'s radiators, drive trip at velocity. With thermal option F (550 K section) L2 keeps running and the red bar disappears.</figcaption></figure>'


def build():
    P = json.loads((R/'phase3.json').read_text()); G = json.loads((R/'phase3_eps_g1.json').read_text())
    out = []
    bat = P['battery']; k = bat['kWh']
    # 1 correction report
    corr = [
        ['Battery labels', 'MWh values printed as kWh (J/3.6e9)', f'2,000 kWh usable; {k["black_start_reserve"]:,.0f} kWh protected; {k["ride_through"]:,.0f} kWh ride-through', 'fixed in report2/fmea'],
        ['Separate blades', '"or len(x) > 3" marked every 4-unit layout as separated', 'separated only if no two units share a blade; shared count reported', 'fixed in placement'],
        ['Coast closure', 'closes_in_coast ignored the LOW section', 'blades AND LOW both checked; one architecture now fails', 'fixed in eps_b'],
        ['Kinematics', 'ramp burn (7.55 d, 6.97 AU)', f'power-limited flight: burn 1 {P["missions"]["burns"][0]["duration_d"]:.2f} d, {P["missions"]["burns"][0]["distance_AU"]:.2f} AU; burns 2–4 shorter', 'study re-based'],
        ['Propellant coupling', '1.67 x (mass ratio - 1) x 1.15 multiplier', f'closed form: {P["convergence"]["dP_dM"]:.2f} t propellant per dry t (≈3.7 t at departure)', 'III-E'],
        ['L1 waste heat', 'not counted', '~900 K conversion reject has no production radiator', 'P3-02'],
        ['Shield density/volume', '1.6 t/m³ and a 2.8 m³ envelope for 27.9 t', '1.9 t/m³ (LiH + 6 % W); mass = ρ·V of drawn envelopes', 'EPS-G1'],
        ['Buffer', '"D-variant only" yet in the C-lean ledger; energy-sized', 'one power-sized line counted once (~14 t nominal)', 'ledger'],
        ['Cryocoolers', 'counted in the registry and again as a new line', 'registry row only', 'ledger'],
        ['Provisions', '20 t load, only 4.1 t added', 'departure loading ledger carries the whole load', 'ledger'],
        ['Duty surplus', '2 MW surplus assumed', 'C-lean surplus 0.5 MW BOL, ~0 EOL with planning loads', 'III-A 3.2'],
    ]
    out.append(section('q1', '1 · CORRECTION REPORT', 'What Phase II got wrong, and what changed',
        table(['Item', 'Phase II', 'Phase III', 'Where'], [[E(a), E(b_), E(c), E(d)] for a, b_, c, d in corr])))
    # 2 battery
    orows = [[E(n), t3(o['protected_kWh']), t3([100*x for x in o['fraction_BOL']]) + ' %', t3(o['ride_through_BOL_kWh']), E(o['note'])] for n, o in bat['options'].items()]
    brows = [[E(n.replace('_', ' ')), t3(v['kWh']), tag(v['cls']), E(v['basis'])] for n, v in bat['budgets'].items()]
    out.append(section('q2', '2 · BATTERY', 'Separate budgets instead of one 72 % reserve',
        f'<div class="callout k">{E(bat["corrected_note"])}</div>'
        + table(['Budget', 'kWh', 'Class', 'Basis'], brows)
        + table(['Option', 'Protected kWh', 'Share of 2,000 kWh', 'Ride-through kWh', 'Note'], orows)
        + f'<p>{E(bat["finding"])}</p><p class="muted">Discharge limit at 0.7/1/2 C: {", ".join(f"{x:.1f}" for x in bat["discharge_limit_MW"])} MW against a coast load of '
          f'{t3(bat["coast_load_MW"], 1)} MW. End-of-life usable: {bat["eol_usable_kWh"][0]:,.0f}–{bat["eol_usable_kWh"][2]:,.0f} kWh. Cryo on the battery for 58 h would need '
          f'{bat["cryo_on_battery_kWh"][1]/1e3:,.0f} MWh: cryo is paused in the sealed hold, never battery-fed.</p>'))
    # 3 buffer
    srows = [[E(r['demand']), E(r['case']), r['life'], t3(r['surplus_MW'], 2), ' '.join(ok(x, 'yes', 'no') for x in r['sustainable']),
              t3([100*x for x in r['max_duty']], 1) + ' %'] for r in P['buffer']['summary']]
    ch = P['buffer']['chemistries']
    out.append(section('q3', '3 · COUPLED BUFFER', 'Surplus, buffer and recharge in one calculation',
        table(['Demand', 'Running set', 'Life', 'Surplus MW', '10 s every 10 min sustainable (low nom high)', 'Max sustainable duty'], srows)
        + table(['Chemistry', 'Wh/kg', 'kW/kg', 'Class'], [[E(n), f'{v["e"]:.0f}', f'{v["p"]:.1f}', tag(v['cls'])] for n, v in ch.items()])
        + f'<p>{E(P["buffer"]["finding"])}</p>'))
    # 4 thermal closure
    th = P['thermal_closure']
    trows = []
    for r in th['rows']:
        if r['condition'] != 'intact' and r['band'] != 'nominal':
            continue
        cells = '; '.join(f'{E(c["circuit"].split(" (")[0])} {c["load_W"]/1e6:.2f}/{c["capacity_W"]/1e6:.2f} {"✓" if c["ok"] else "✗"}' for c in r['circuits'])
        trows.append([f'<span class="mono">{r["state"]}</span>', E(r['condition']), r['band'], ok(r['closes'], 'closes', 'no'), f'<span class="fn">{cells}</span>'])
    out.append(section('q4', '4 · THERMAL CLOSURE', 'Every circuit must pass; one failure means no closure',
        f'<p class="muted">{E(th["rule"])} Usable after the 20 % margin: WARM {th["warm_usable_W"]/1e6:.1f} MW at 440 K, LOW {th["low_usable_W"]/1e6:.2f} MW at 300 K. '
        'OPEN planning loads are added to the WARM circuit; standby units add ~1 % of their thermal power to the channels; buffer losses go to LOW.</p>'
        + table(['State', 'Condition', 'Band', 'Result', 'Circuits (load / capacity MW)'], trows) + f'<p>{E(th["finding"])}</p>'))
    # 5 shielding
    sh = P['shielding']; g1 = sh['eps_g1']
    tk = [[E(t['tank']), E(t['species']), f'{t["off_axis_deg"]:.0f}°', ok(t['in_shadow'], 'in shadow', 'outside'), f'{t["bare_deposit_W"]:.0f}'] for t in sh['tanks']]
    el = [[E(n), f'{v["Gy_20yr"]:.3g}', ok(v['ok'])] for n, v in sh['electronics'].items()]
    sd = [[n, f'{v["decay_W"]/1e3:.0f} kW', f'{v["bare_Sv_h_at_5m"]:.3g}', f'{v["crew_minutes_to_50mSv"]:.2g} min'] for n, v in sh['shutdown'].items()]
    out.append(section('q5', '5 · SHIELDING', 'Shield mass now follows from its volume, and the tanks need a shadow too',
        f'<div class="callout">{E(sh["blocker"])}</div>'
        + table(['', 'Shadow t', 'Blade slab t', 'Per unit t', 'Density t/m³', 'Volume check'],
                [['Phase II', '–', '–', f'{sh["phase2"]["mass_t"]:.1f}', f'{sh["phase2"]["rho"]:.1f}', f'<span class="bad">{sh["phase2"]["implied_m3"]:.1f} m³ needed in a {sh["phase2"]["envelope_m3"]} m³ envelope</span>'],
                 ['EPS-G1 (nominal)', f'{g1["shadow_t"]:.1f}', f'{g1["slab_t"]:.1f}', f'{g1["per_unit_t"]:.1f}', f'{g1["rho"]:.1f}', f'<span class="good">{g1["shadow_m3"]:.1f} + {g1["slab_m3"]:.1f} m³ drawn</span>']])
        + table(['Tank', 'Species', 'Off axis', 'Shadow (12.5°)', 'Bare deposit W (3 units, upper bound)'], tk)
        + f'<p>A shadow wide enough for every tank needs a {sh["wide_cone"]["half_angle_deg"]:.0f}° half-angle: {sh["wide_cone"]["shadow_t"]:.0f} t per unit and '
          f'{2*sh["wide_cone"]["outer_radius_m"]:.1f} m across, which does not fit a 2.8 m bay depth. The He-3 3 K stage lifts {sh["he3_stage_lift_W"]:.0f} W in total.</p>'
        + '<div class="two"><div>' + table(['After shutdown (1 yr run)', 'Decay heat', 'Bare Sv/h at 5 m', 'Time to 50 mSv'], sd) + '</div><div>'
        + table(['Electronics (20 yr)', 'Gy', '≤ 1 kGy'], el) + '</div></div>'
        + f'<p>Combined exposure: n running units add ln n e-folds (3 units: {sh["combined_efolds"]["3"]:.2f}). {E(sh["finding"])}</p>'))
    # 6 redundancy
    mc = P['redundancy']['mc']; rrows = []
    for cfg, d in mc.items():
        for case in ('u=0.05', 'u=0.05, no repair', 'u=0.1'):
            v = d[case]
            rrows.append([E(cfg), case] + [f'{100*v[y]["P_any_shortfall"]:.1f} % / {100*v[y]["P_permanent_shortfall"]:.1f} %' for y in ('1 yr', '3 yr', '5 yr')]
                         + [f'{100*v["3 yr"]["unavailability"]:.2f} %', f'{v["3 yr"]["shortfall_events_per_yr"]:.3f}'])
    out.append(section('q6', '6 · REDUNDANCY', 'Shared dependencies, repair and mission probability',
        fig_deps() + f'<p class="muted">{E(P["redundancy"]["model"])}. Need: proactive coast load {P["redundancy"]["need_W"]/1e6:.2f} MW; units at end-of-life output (0.9).</p>'
        + table(['Configuration', 'Unit rate /yr', 'P(any shortfall) / P(lasting) 1 yr', '3 yr', '5 yr', 'Unavailability (3 yr)', 'Shortfall events/yr'], rrows)
        + f'<p>{E(P["l2"]["finding"])}</p>'))
    # 7 mass ledgers
    L = P['ledgers']
    i_rows = [[E(r['item']), E(r['line']), t3(r['t'], 1), tag(r['cls'])] for r in L['installed']]
    n_rows = [[E(r['line']), '–' if r['allocation_t'] is None else f'{r["allocation_t"]:.0f}', t3(r['new_t'], 1), t3(r['increment_t'], 1)] for r in L['increment']]
    d_rows = [[E(r['mission']), f'{r["total_t"]:.1f}', f'{r["crew_consumables_t"]:.1f}', f'{r["spares_t"]:.1f}', f'{r["beyond_10t_line_t"]:.1f}', t3(r['rcs_propellant_t'], 1), str(r['containers'])] for r in L['departure']]
    out.append(section('q7', '7 · MASS LEDGERS', 'Installed, increment beyond allocations, departure loading: each item once',
        '<h3>1 · Installed equipment (working candidate N1 basis)</h3>' + table(['Item', 'Budget line', 't', 'Class'], i_rows)
        + '<h3>2 · Increment beyond allocations</h3>' + table(['Line', 'Allocation t', 'New t', 'Increment t'], n_rows)
        + f'<p>Total increment {t3(L["increment_total_t"])} t.</p>'
        + '<h3>3 · Departure loading per mission (not dry mass)</h3>' + table(['Mission', 'Total t', 'Crew consumables', 'Spares', 'Beyond the 10 t line', 'RCS propellant t', 'Containers'], d_rows)
        + '<ul>' + ''.join(f'<li>{E(x)}</li>' for x in L['reconciliation']) + '</ul>'))
    # 8 thermal architectures
    TA = P['thermal_architectures']
    ta = [[E(r['doctrine']), f'<b>{r["key"]}</b> {E(r["name"])}', f'{r["pump_work_W"]/1e6:.1f}', f'{r["L1_W"]/1e6:.1f}',
           '–' if r.get('L1_waste_W') is None else f'{r["L1_waste_W"]/1e6:.1f}', f'{r["added_area_m2"]:,.0f}',
           f'{r["added_t"]:,.0f}' if r['added_t'] < 1e4 else '<span class="bad">infeasible</span>', 'yes' if r['L2_in_burn'] else '<span class="bad">no</span>',
           f'<span class="fn">{E(r["interference"])}</span>'] for r in TA['rows']]
    out.append(section('q8', '8 · THERMAL ARCHITECTURES', 'A–F under both doctrines',
        table(['Doctrine', 'Architecture', 'Pump work MW', 'L1 MWe', 'L1 waste MW', 'Added area m²', 'Added t', 'L2 in burns', 'Interference'], ta)
        + f'<p>{E(TA["finding"])}</p><p class="muted">Production radiators stay the baseline (DR-03). B, C, D and F are isolated research variants; the 550 K section is drawn in '
          'the review file (WORK_ISSA3_RADIATOR_VARIANT_550K, hidden by default).</p>'))
    # 9 L1 + L2 + district
    L1 = P['l1']
    l1rows = [[E(r['demand']), E(r['conversion'].split(' (')[0]), f'{r["Pe_W"]/1e6:.1f}', f'{r["area_m2"]:,.0f}', f'{r["mass_t"]:,.0f}', tag(r['cls'])]
              for r in L1['rows'] if r['band'] == 'nominal']
    L2 = P['l2']
    l2rows = [[E(r['name']), E(r['strategy']), t3(r['mass_t']), t3([x/1e6 for x in r['after_one_loss_W']], 2), t3([x/1e6 for x in r['surplus_with_planning_EOL_W']], 2)] for r in L2['rows']]
    di = [[E(r['option']), f'{r["shield_t"]:,.0f}', ok(r['fits'], 'fits', 'no'), E(r['notes'])] for r in P['district']['rows']]
    out.append(section('q9', '9 · ELECTRICAL', 'L1 shrinks with demand; L2 wants fewer, larger units',
        '<h3>L1 at the propulsion interface (nominal band)</h3>' + table(['Demand case', 'Conversion', 'MWe', '900/450/700 K area m²', 't', 'Class'], l1rows)
        + f'<p>{E(L1["finding"])}</p>'
        + '<h3>L2 options</h3>' + table(['Option', 'Strategy', 'Mass t (EPS-G1 shields)', 'Surplus after one loss MW (BOL, known)', 'Surplus at EOL with planning MW'], l2rows)
        + f'<p>{E(L2["finding"])}</p>'
        + '<h3>Nuclear district</h3>' + table(['Option', 'Shield t', 'Fits', 'Notes'], di) + f'<p>{E(P["district"]["finding"])}</p>'))
    # 10 EPS-G1
    U = G['reference_unit']
    erows = [[E(e['name']), e['cls'], e['family'], f'{e["volume_m3"]:.1f}', '–' if not e['mass_kg'] else f'{e["mass_kg"]/1e3:.1f}', tag(e['status'])] for e in U['envelopes']]
    drows = []
    for n, D in G['districts'].items():
        o = D['physical_overlap']; Uu = G['units'][n]
        drows.append([E(n), str(len(D['units'])), f'{Uu["length_m"]:.1f}', ok(Uu['fits_one_module'], 'yes', 'no'), f'{100*o["free"]:.0f} %', f'{100*o["dry_store"]:.0f} %',
                      f'<span class="{"bad" if o["occupied"] + o["reserved"] > 0.05 else ""}">{100*(o["occupied"]+o["reserved"]):.1f} %</span>',
                      E(', '.join(f'{h}: {u}' for h, u in D['shared_headers'].items()) or 'none'), f'{(Uu["shadow_kg"]+Uu["slab_kg"])/1e3:.1f}'])
    bandrows = [[b_, f'{v["length_m"]:.1f}', f'{v["shadow_kg"]/1e3:.1f}', f'{v["slab_kg"]/1e3:.1f}', f'{v["physical_mass_kg"]/1e3:.1f}', f'{v["physical_volume_m3"]:.1f}'] for b_, v in G['bands'].items()]
    out.append(section('q10', '10 · EPS-G1', 'One parametric power unit, its envelopes and four districts',
        '<div class="two"><div><img src="cam_issa3_unit.jpg" alt="EPS-G1 unit envelopes in the M1 bays (Workbench render)" style="border-radius:8px;border:1px solid var(--line);width:100%;height:auto;display:block">'
        '<p class="fn">MODEL-DERIVED placement, PROTOTYPE envelopes. Red: reactor envelope; grey: shadow frustum and blade slab; amber/yellow: heat transport and conversion; blue: electrical; green/yellow/blue translucent: maintenance, removal and robotic envelopes.</p></div>'
        f'<div>{fig_section_unit(G)}</div></div>'
        + table(['Envelope (1.75 MWe reference)', 'Class', 'Family', 'm³', 't', 'Status'], erows)
        + table(['Band', 'Length m', 'Shadow t', 'Slab t', 'Physical t', 'Physical m³'], bandrows)
        + table(['District variant', 'Units', 'Unit length m', 'Fits one module', 'Free', 'Dry store', 'Conflicts (occupied + reserved)', 'Shared headers', 'Shield t/unit'], drows)
        + '<p class="muted">Conflict screen: physical, maintenance, robotic and removal envelopes sampled every 0.3 m against the 0.5 m survey grid of the built ship. '
          'Overlaps with occupied (O) and reserved (R) cells are the casing frames, keel-lane edges and the removal path crossing the casing; dry store (D) is '
          'repurposed only in isolated review geometry (DR-12). The 2 × 100 % unit (11.2 m) does not fit one 10.2 m module.</p>'
        + '<div class="two"><div><img src="cam_issa3_district.jpg" alt="district variant V2 in M1-M2" style="border-radius:8px;border:1px solid var(--line);width:100%;height:auto;display:block"><p class="fn">District V2 (2+1 × 2.66 MWe) with the 12.5° shadow and the needed ~28° cone.</p></div>'
          '<div><img src="cam_issa3_tank_sightlines.jpg" alt="tank sight lines" style="border-radius:8px;border:1px solid var(--line);width:100%;height:auto;display:block"><p class="fn">Sight lines to the tank farm: green inside the 12.5° shadow (inner ring), red outside (outer-ring He-3).</p></div></div>'
        + table(['Thermal machinery envelope', 'Family', 'MW', 'm³', 't', 'District', 'Status'],
                [[E(t['name']), t['family'], f'{t["capacity_W"]/1e6:.1f}', f'{t["volume_m3"]:.0f}', f'{t["mass_kg"]/1e3:.0f}', E(t['district']), tag(t['status'])] for t in G['thermal_machinery']])))
    # 11 transition
    T = P['transition']
    out.append(section('q11', '11 · BURN-TO-COAST', 'A drive trip at velocity opens a protection gap',
        fig_transition(T) + table(['Time', 'Event', 'Consequence'], [[E(a), E(b_), E(c)] for a, b_, c in T['steps']])
        + f'<p>{E(T["finding"])}</p><p class="muted">Probability of a damaging strike during the gap (flux OPEN, 10⁻³–10⁻¹ per hour): {t3([100*x for x in T["strike_probability"]], 2)} %.</p>'))
    # 12 missions
    M = P['missions']
    brow = [[str(x['burn']), f'{x["m0_t"]:,.0f}', f'{x["duration_d"]:.2f}', f'{x["distance_AU"]:.2f}', f'{x["accel_g"][0]:.2f}–{x["accel_g"][1]:.2f}'] for x in M['burns']]
    tr = [[f'{r["D_AU"]:.0f}', f'{r["v_c"]:.3f}', f'{r["round_trip_months"]:.1f}', f'{r["propellant_t"]:,.0f}', f'{r["departure_t"]:,.0f}', f'{r["defense_W"]/1e6:.2f}',
           f'{r["consumables_t"]:.0f}', f'{r["dust_fluence_rel"]:.2f}', f'{100*r["P_unit_loss2"]:.1f} %'] for r in M['speed_trade']]
    LG = P['logistics']; EC = P['eclss']; NA = P['narrative']
    lrows = []
    for r in LG['rows']:
        lrows.append([E(r['mission']), f'{r["total_t"]:.1f}', str(r['containers'])] + [str(c['containers']) for c in r['categories']])
    out.append(section('q12', '12 · MISSIONS AND LOGISTICS', 'Speed is a per-mission choice; the dry store carries the mission',
        f'<div class="callout k">{E(M["correction"])}</div>'
        + table(['Burn', 'Start mass t', 'Days', 'AU', 'Accel g'], brow)
        + '<h3>Speed versus distance (12 crew, round trip, 30 d on station)</h3>'
        + table(['AU', 'Cruise c', 'Months', 'Propellant t', 'Departure t', 'Proactive defense MW', 'Consumables t', 'Dust fluence/yr (rel.)', 'P(lose 2 of 4 units)'], tr)
        + f'<p>{E(M["finding"])}</p>'
        + '<h3>Logistics containers (5.0 × 2.8 × 3.2 m, 44.8 m³, 6 t gross nominal)</h3>'
        + table(['Mission', 't', 'Containers'] + [c['category'] for c in LG['rows'][0]['categories']], lrows)
        + f'<p class="muted">Restraint: {E(LG["container"]["restraint"])}. Load path: {E(LG["container"]["load_path"])} ({LG["container"]["axial_kN_at_6t"]:.0f} kN axial at 6 t, 1.5 g). '
          f'Transfer: {E(LG["container"]["transfer"])}.</p>'
        + '<h3>ECLSS: twelve people in one ring</h3>' + table(['Option', 'Capacity', 'Added t', 'Note'], [[E(r['option']), str(r['capacity_persons']), t3(r['added_t'], 1), E(r['note'])] for r in EC['rows']])
        + f'<p>Recommendation: {E(EC["recommendation"])}.</p>'
        + f'<h3>Narrative case: six people on a 36-month load for twelve ({NA["load_t"]:.0f} t)</h3>'
        + table(['Case', 'Years'], [[E(r['case']), f'{r["years"]:.2f}'] for r in NA['rows']])
        + f'<p class="muted">{E(NA["note"])} C-lean without repair: P(lasting shortfall) {100*NA["l2"]["u=0.05, no repair"]["5 yr"]["P_permanent_shortfall"]:.0f} % over 5 years.</p>'))
    # 13 convergence
    CV = P['convergence']
    crow = []
    for c in CV['candidates']:
        it = c['items_t']; f = lambda kk: f'{it.get(kk, [0, 0, 0])[1]:.0f}'
        crow.append([E(c['name']), f('L1'), f('L2'), f('L3'), f('thermal'), f('storage'), f('distribution'), f('radiator_structure'), f'<b>{c["dry_added_t"][1]:.0f}</b>',
                     f'{c["coupled"][1]["propellant_t"]:,.0f}', f'{c["coupled"][1]["departure_t"]:,.0f}', f'{c["cg_x_m"]:.1f}',
                     f'{c["coupled"][1]["first_burn_d"]:.1f}', f'{c["coupled"][1]["accel_g"][0]:.3f}', E(c['redundancy']), f'<span class="fn">{E("; ".join(c["open"]))}</span>'])
    out.append(section('q13', '13 · CONVERGENCE', 'Candidates on coupled mass equations',
        waterfall(CV['candidates'])
        + table(['Candidate', 'L1', 'L2 (incl. shield)', 'L3', 'Thermal', 'Storage', 'Distribution', 'Radiator / structure', 'Dry added t', 'Propellant t', 'Departure t', 'Dry CoM x m',
                 'Burn 1 d', 'Start accel g', 'Redundancy', 'Open'], crow)
        + f'<p class="muted">{E(CV["note"])} Baseline: {CV["base"]["dry_t"]:,.0f} t dry, {CV["base"]["propellant_t"]:,.0f} t propellant, {CV["base"]["departure_t"]:,.0f} t at departure, dry CoM x {CV["base"]["dry_cg_x_m"]:.1f} m. '
          'Shield mass is inside the L2 column. Ranges (low–high) are in results/phase3.json.</p>'))
    # 14 recommendation, decisions, problems, next
    best = next(c for c in CV['candidates'] if c['name'].startswith('N2'))
    out.append(section('q14', '14 · RECOMMENDATION', 'Recommended research architecture (not a selection)',
        f'<div class="callout k"><b>N2 hybrid F:</b> working doctrine DR-01 in burns and coast; L2 as 2+1 × 2.66 MWe fission-Brayton (one unit per blade, no shared header), '
        f'running through burns on a ~{CV["section550"]["N2"]["length_m"][1]:.0f} m 550 K section at the forward end of the hot blades (research variant); L1 reduced to drive-specific loads with heat-pipe hot blades '
        f'(a propulsion-interface request); power-sized defense buffer and a 1 GJ engagement thermal buffer; L3 in the 50 t line; R1 black start. '
        f'About {best["dry_added_t"][1]:.0f} t dry ({best["dry_added_t"][0]:.0f}–{best["dry_added_t"][2]:.0f}), +{best["extra_departure_t"][1]:,.0f} t at departure. '
        'It does not close: radiation transport (BLOCKER), the He-3 tank shadow, LOW at the high band and the hot-allowance budget remain.</div>'
        + '<h3>Decision register</h3>' + table(['ID', 'Question', 'Recommended'], [[d['id'], E(d['question']), E(d['recommended'])] for d in P['decisions']])
        + '<h3>Problem register</h3>' + table(['ID', 'Severity', 'Problem', 'Consequence'], [[p['id'], f'<span class="{"bad" if p["severity"] == "BLOCKER" else ("warn" if p["severity"] == "MAJOR" else "")}">{p["severity"]}</span>', E(p['problem']), E(p['consequence'])] for p in P['problems']])
        + '<h3>What prevents closure</h3><p>P3-01 radiation transport, P3-02 L1 rejection, P3-03 LOW margin, P3-05 He-3 tank shadow; then the hot-loop pumps (P3-06) and the coupled propellant growth (P3-10).</p>'
        + '<h3>Next implementation sequence</h3><ol>'
          '<li>Owner decisions DR3-01…09; radiation-transport assessment commissioned (outside this container).</li>'
          '<li>LOW section: +20–30 % area or a second 300 K circuit in the existing RAD-ZONE (research variant), then re-run closure.</li>'
          '<li>Radiator research variant F in <code>lab/variants/</code> with its own thermal ledger and hot-allowance check.</li>'
          '<li>Propulsion interface question: heat-pipe hot blades and the L1 900 K reject.</li>'
          '<li>EPS-G1 as a generator (<code>REP_PROXY</code>, M1–M2) only after the owner picks a district and the transport result exists.</li>'
          '<li>Registry: PROPOSED budget lines into <code>data/systems.toml</code> after DR-04; Drive rows only with authorization.</li></ol>'))
    return '\n'.join(out)
