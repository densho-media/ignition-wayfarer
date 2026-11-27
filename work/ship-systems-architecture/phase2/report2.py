"""ISSA Phase II page sections (report items 1-17, comparisons and diagrams), inserted into results/issa.html by build_report.py.
Reads references/p1_power_loads.json, data/systems.toml and results/phase2_*.json. Pure Python, inline SVG with theme tokens.
"""
import html
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
R = Path(__file__).resolve().parents[1]/'results'
E = html.escape


def b(v, k=1e6, d=1, unit=''):
    return f'{v[0]/k:.{d}f}–{v[2]/k:.{d}f} <span class="nom">({v[1]/k:.{d}f})</span>{unit}'


def t3(v, d=0):
    return f'{v[0]:.{d}f}–{v[2]:.{d}f} <span class="nom">({v[1]:.{d}f})</span>'


def table(head, rows, cls=''):
    h = ''.join(f'<th>{x}</th>' for x in head)
    body = '\n'.join('<tr>'+''.join(f'<td{" class=num" if i and (isinstance(c, (int, float)) or (isinstance(c, str) and c[:1].isdigit())) else ""}>{c}</td>' for i, c in enumerate(r))+'</tr>' for r in rows)
    return f'<div class="scroll"><table class="{cls}"><tr>{h}</tr>{body}</table></div>'


def bars(items, unit, w=760, bh=22, max_v=None, cls=None):
    """horizontal low/nominal/high bars: items = [(label, (lo, nom, hi), tone)]"""
    max_v = max_v or max(v[2] for _, v, _ in items)
    lw = 250; sc = (w-lw-90)/max_v; H = len(items)*(bh+8)+28
    s = [f'<svg viewBox="0 0 {w} {H}" role="img" aria-label="{E(unit)}">']
    for i, (lab, v, tone) in enumerate(items):
        y = 8+i*(bh+8)
        s.append(f'<text x="{lw-8}" y="{y+bh*0.68}" text-anchor="end" style="fill:var(--ink);font:12px IBM Plex Sans,sans-serif">{E(lab)}</text>')
        s.append(f'<rect x="{lw+v[0]*sc:.1f}" y="{y+5}" width="{max(1, (v[2]-v[0])*sc):.1f}" height="{bh-10}" rx="3" style="fill:var(--{tone});opacity:.35"/>')
        s.append(f'<rect x="{lw+v[1]*sc-1.5:.1f}" y="{y}" width="3" height="{bh}" style="fill:var(--{tone})"/>')
        s.append(f'<text x="{lw+v[2]*sc+6:.1f}" y="{y+bh*0.68}" style="fill:var(--muted);font:11px IBM Plex Mono,monospace">{v[1]:,.1f}</text>')
    s.append(f'<line x1="{lw}" y1="{H-20}" x2="{w-90}" y2="{H-20}" style="stroke:var(--line)"/>')
    for f in (0, 0.25, 0.5, 0.75, 1.0):
        x = lw+f*max_v*sc
        s.append(f'<text x="{x:.0f}" y="{H-6}" text-anchor="middle" style="fill:var(--muted);font:10px IBM Plex Mono,monospace">{f*max_v:,.0f}</text>')
    s.append(f'<text x="{w-4}" y="{H-6}" text-anchor="end" style="fill:var(--muted);font:10px IBM Plex Mono,monospace">{E(unit)}</text></svg>')
    return '<figure><div class="frame">'+''.join(s)+'</div></figure>'


def box(x, y, w, h, title, sub='', tone='line', fill='surf2'):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" style="fill:var(--{fill});stroke:var(--{tone});stroke-width:1.5"/>'
            f'<text x="{x+w/2}" y="{y+18}" text-anchor="middle" style="fill:var(--ink);font:600 12px IBM Plex Sans,sans-serif">{E(title)}</text>'
            + (f'<text x="{x+w/2}" y="{y+34}" text-anchor="middle" style="fill:var(--muted);font:11px IBM Plex Mono,monospace">{E(sub)}</text>' if sub else ''))


def arrow(x1, y1, x2, y2, tone='muted', dash=''):
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" style="stroke:var(--{tone});stroke-width:1.6{";stroke-dasharray:5 4" if dash else ""}" marker-end="url(#ah)"/>')


DEFS = '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0L10,5L0,10z" style="fill:var(--muted)"/></marker></defs>'


def fig_levels():
    s = ['<svg viewBox="0 0 900 330" role="img" aria-label="L1 L2 L3 sources and A B E buses">', DEFS]
    s.append(box(20, 20, 230, 48, 'L1 burn generation', 'drive hot loop, burns only', 'bad'))
    s.append(box(20, 120, 230, 48, 'L2 ship service, N+1 modular', '3+1 x ~1.75 MWe fission-Brayton', 'info'))
    s.append(box(20, 220, 230, 48, 'L3 survival source', 'RPS / small fission, ~10-40 kWe', 'good'))
    s.append(box(20, 275, 230, 40, 'Stores', 'battery, pulse bank, buffer', 'warn'))
    for i, (n, sub) in enumerate((('Bus A', 'keel lane 1'), ('Bus B', 'keel lane 2'), ('Bus E', 'essential, lane 3'))):
        s.append(box(360, 30+i*95, 160, 46, n, sub, 'accent'))
    for y in (44, 144):
        s.append(arrow(250, y, 358, 53)); s.append(arrow(250, y, 358, 148))
    s.append(arrow(250, 244, 358, 243)); s.append(arrow(250, 295, 358, 243, dash=True)); s.append(arrow(250, 295, 358, 53, dash=True))
    loads = (('Defense (proactive, triggered active)', 'A,B'), ('Cryocoolers N+1', 'A,B'), ('ECLSS strings x2', 'A,B,E'), ('Nav / comms beacon', 'E'),
             ('Burn heat pumps, hot-loop pumps', 'L1'), ('Hotel, MRO, Garden (sheddable)', 'A or B'))
    for i, (n, f) in enumerate(loads):
        y = 22+i*50; s.append(box(630, y, 250, 40, n, 'fed by '+f, 'line', 'surf'))
        s.append(arrow(520, 53 if 'A' in f else (243 if f == 'E' else 148), 628, y+20, 'line'))
    s.append('</svg>')
    return '<figure><div class="frame">'+''.join(s)+'</div><figcaption>L1 lives only in burns. L2 carries the ship. L3 and the protected battery reserve keep the crew alive and restart L2; the survival reserve never charges the pulse bank or restarts the drive.</figcaption></figure>'


def fig_modularity(archs):
    s = ['<svg viewBox="0 0 900 230" role="img" aria-label="generator modularity">']
    rows = [('B: 2 x 5.6 MWe', 2, 5.62, 1), ('C: 4 x 2.9 MWe (3+1)', 4, 2.88, 1), ('C-lean: 4 x 1.75 MWe (3+1)', 4, 1.75, 1), ('C2: 6 x 1.7 MWe (5+1)', 6, 1.73, 1)]
    sc = 55
    for i, (n, k, u, sp) in enumerate(rows):
        y = 20+i*50
        s.append(f'<text x="10" y="{y+20}" style="fill:var(--ink);font:12px IBM Plex Sans,sans-serif">{E(n)}</text>')
        for j in range(k):
            x = 240+j*(u*sc+8)
            tone = 'warn' if j == k-1 else 'info'
            s.append(f'<rect x="{x:.0f}" y="{y}" width="{u*sc:.0f}" height="30" rx="4" style="fill:var(--{tone});opacity:{.35 if j == k-1 else .7}"/>')
        s.append(f'<text x="890" y="{y+20}" text-anchor="end" style="fill:var(--muted);font:11px IBM Plex Mono,monospace">{k*u:.1f} MWe installed</text>')
    s.append('</svg>')
    return '<figure><div class="frame">'+''.join(s)+'</div><figcaption>Blue units run, amber is the standby. Smaller units lose less per trip and fit one dry-store module pair each; more units add shields and controls.</figcaption></figure>'


def fig_transitions():
    st = [('COAST_LOW_V', 60, 40), ('COAST_HV_PROACTIVE', 300, 40), ('COAST_HV_TRIGGERED', 560, 40), ('FIRST_IGNITION / LOW_THRUST', 60, 160),
          ('HIGH_THRUST', 300, 160), ('PROPULSION_SHUTDOWN', 560, 160), ('POST_BURN_COOLDOWN', 760, 100), ('BLACK_START', 60, 270),
          ('SURVIVAL_CREW / MISSION / PROTECTED', 330, 270), ('DOCKED / EVA / MAINTENANCE', 640, 270)]
    s = ['<svg viewBox="0 0 960 330" role="img" aria-label="operating state transitions">', DEFS]
    pos = {}
    for n, x, y in st:
        w = 190 if len(n) > 18 else 170; s.append(box(x, y, w, 40, n, '', 'accent' if 'SURV' in n or 'BLACK' in n else 'line')); pos[n] = (x+w/2, y+20, w)
    def link(a, c, dash=False, tone='muted'):
        ax, ay, aw = pos[a]; cx, cy, cw = pos[c]
        s.append(arrow(ax+(aw/2 if cx > ax else (-aw/2 if cx < ax else 0)), ay+(0 if cy == ay else (20 if cy > ay else -20)),
                       cx-(cw/2 if cx > ax else (-cw/2 if cx < ax else 0)), cy-(0 if cy == ay else (20 if cy > ay else -20)), tone, dash))
    for a, c in (('COAST_LOW_V', 'COAST_HV_PROACTIVE'), ('COAST_HV_PROACTIVE', 'COAST_HV_TRIGGERED'), ('COAST_LOW_V', 'FIRST_IGNITION / LOW_THRUST'),
                 ('FIRST_IGNITION / LOW_THRUST', 'HIGH_THRUST'), ('HIGH_THRUST', 'PROPULSION_SHUTDOWN'), ('PROPULSION_SHUTDOWN', 'POST_BURN_COOLDOWN'),
                 ('POST_BURN_COOLDOWN', 'COAST_HV_TRIGGERED')):
        link(a, c)
    for a, c in (('HIGH_THRUST', 'SURVIVAL_CREW / MISSION / PROTECTED'), ('COAST_HV_PROACTIVE', 'SURVIVAL_CREW / MISSION / PROTECTED'),
                 ('SURVIVAL_CREW / MISSION / PROTECTED', 'BLACK_START'), ('BLACK_START', 'FIRST_IGNITION / LOW_THRUST')):
        link(a, c, True, 'bad')
    s.append('</svg>')
    return '<figure><div class="frame">'+''.join(s)+'</div><figcaption>Normal path in grey; fault paths dashed red. Every burn drains the warm channels, so L2 drops to hot standby and L1 carries the ship; after a drive trip the WARM section alone supports about 1.0–1.3 MWe of L2 until the channels refill.</figcaption></figure>'


def fig_layouts(P):
    s = ['<svg viewBox="0 0 960 300" role="img" aria-label="candidate equipment layouts along the ship">']
    x0, x1 = -145.0, 145.0; sx = lambda x: 40+(x-x0)/(x1-x0)*880
    s.append(f'<rect x="{sx(-144.75)}" y="20" width="{sx(144.75)-sx(-144.75)}" height="16" rx="3" style="fill:var(--surf2);stroke:var(--line)"/>')
    for name, a, c, tone in (('drive', -144.75, -113.2, 'bad'), ('aft bay D2', -133.25, -89.5, 'warn'), ('dry store', -89.75, 21.25, 'dry'),
                             ('RAD-ZONE', 48.9, 93.4, 'warn'), ('rings', 96.3, 104.3, 'good'), ('refuge', 106.4, 109.2, 'good'), ('tanks', 109.2, 137.8, 'info')):
        s.append(f'<rect x="{sx(a):.0f}" y="20" width="{sx(c)-sx(a):.0f}" height="16" style="fill:var(--{tone});opacity:.55"/>')
        s.append(f'<text x="{(sx(a)+sx(c))/2:.0f}" y="50" text-anchor="middle" style="fill:var(--muted);font:10px IBM Plex Mono,monospace">{name}</text>')
    tones = {'L-A': 'info', 'L-B': 'action', 'L-C': 'accent', 'L-E': 'good', 'L-D': 'bad'}
    for i, (name, L) in enumerate(P['layouts'].items()):
        k = name.split()[0]; y = 72+i*44
        s.append(f'<text x="40" y="{y+4}" style="fill:var(--ink);font:600 12px IBM Plex Sans,sans-serif">{E(name)}</text>')
        for x in L['x']:
            s.append(f'<rect x="{sx(x)-4:.0f}" y="{y+10}" width="8" height="18" rx="2" style="fill:var(--{tones[k]})"/>')
        xa = min(L['x']); r = 28
        import math
        xe = sx(145); dy = math.tan(math.radians(L['cone_half_angle_needed_deg']))*(145-xa)/(290)*880/6
        s.append(f'<path d="M{sx(xa):.0f},{y+19} L{xe:.0f},{y+19-min(r, dy):.0f} L{xe:.0f},{y+19+min(r, dy):.0f}z" style="fill:var(--warn);opacity:.10"/>')
        s.append(f'<rect x="{sx(min(L["x"])-6):.0f}" y="{y+8}" width="{sx(max(L["x"])+6)-sx(min(L["x"])-6):.0f}" height="22" style="fill:none;stroke:var(--bad);stroke-dasharray:3 3"/>')
        s.append(f'<text x="920" y="{y+24}" text-anchor="end" style="fill:var(--muted);font:11px IBM Plex Mono,monospace">{L["cone_half_angle_needed_deg"]:.1f}°, {L["per_unit_shield_kg"][1]/1e3:.0f} t/unit</text>')
    s.append('</svg>')
    return '<figure><div class="frame">'+''.join(s)+'</div><figcaption>Unit positions (bars), the shadow cone each layout needs to cover rings, refuge, service zone and tanks (amber), and the crew exclusion around running units (red dashes). Shield per unit includes the blade-facing scatter band.</figcaption></figure>'


def fig_domains():
    s = ['<svg viewBox="0 0 900 200" role="img" aria-label="failure domains">']
    doms = [('DRIVE_AFT', 'drive, L1, hot-loop pumps', 'bad'), ('POWER_DISTRICT_A', 'L2 units 1, 3 · bus A', 'info'), ('POWER_DISTRICT_B', 'L2 units 2, 4 · bus B', 'accent'),
            ('MIDBODY_STORES', 'dry-store logistics', 'dry'), ('BLADES', 'warm channels x 3', 'warn'), ('RAD_ZONE', 'WARM / LOW sections', 'warn'),
            ('ROTOR_RINGS', 'ECLSS strings, crew', 'good'), ('FORWARD_SERVICE', 'refuge, L3, bus E', 'good')]
    for i, (n, sub, tone) in enumerate(doms):
        x = 10+(i % 4)*222; y = 12+(i//4)*92
        s.append(box(x, y, 210, 70, n, sub, tone, 'surf'))
    s.append('</svg>')
    return '<figure><div class="frame">'+''.join(s)+'</div><figcaption>Redundancy is credited only across domains. Two L2 units on the same blade header, or L1 with the drive, share one domain.</figcaption></figure>'


def fig_dependencies():
    s = ['<svg viewBox="0 0 960 250" role="img" aria-label="electrical and thermal dependencies">', DEFS]
    nodes = {'L2 unit': (20, 20, 'info'), 'Blade warm channels (550 K)': (20, 120, 'warn'), 'Buses A/B': (260, 20, 'accent'),
             'Cryocoolers': (500, 20, 'line'), 'LOW section 300 K, 1 MW': (500, 120, 'warn'), 'He-3 at 3 K': (740, 20, 'bad'),
             'ECLSS + ring loops': (260, 190, 'good'), 'WARM section 440 K, 5 MW': (500, 190, 'warn'), 'Defense': (740, 120, 'line')}
    for n, (x, y, tone) in nodes.items():
        s.append(box(x, y, 200, 44, n, '', tone, 'surf'))
    for a, c, tone in (('L2 unit', 'Buses A/B', 'muted'), ('L2 unit', 'Blade warm channels (550 K)', 'warn'), ('Buses A/B', 'Cryocoolers', 'muted'),
                       ('Cryocoolers', 'He-3 at 3 K', 'muted'), ('Cryocoolers', 'LOW section 300 K, 1 MW', 'warn'), ('Buses A/B', 'ECLSS + ring loops', 'muted'),
                       ('ECLSS + ring loops', 'WARM section 440 K, 5 MW', 'warn'), ('Buses A/B', 'Defense', 'muted'), ('Defense', 'WARM section 440 K, 5 MW', 'warn')):
        ax, ay, _ = nodes[a]; cx, cy, _ = nodes[c]
        if cx == ax:
            s.append(arrow(ax+100, ay+44, cx+100, cy, tone))
        elif cx > ax:
            s.append(arrow(ax+200, ay+22, cx, cy+22, tone))
        else:
            s.append(arrow(ax, ay+22, cx+200, cy+22, tone))
    s.append('</svg>')
    return '<figure><div class="frame">'+''.join(s)+'</div><figcaption>Grey: electric. Amber: heat. The He-3 stage depends on L2 through the buses and on the LOW section; the blades are both the L2 sink and a shared failure domain.</figcaption></figure>'


def section(id_, num, title, body):
    return f'<section id="{id_}"><div class="letter">{num}</div><h2>{title}</h2>{body}</section>'


def build():
    pl = json.loads((ROOT/'references/p1_power_loads.json').read_text())
    eb = json.loads((R/'phase2_eps_b.json').read_text()); em = json.loads((R/'phase2_eclss_mass.json').read_text())
    P = json.loads((R/'phase2_placement.json').read_text()); F = json.loads((R/'phase2_fmea.json').read_text())
    M = json.loads((R/'phase2_mission.json').read_text()); reg = tomllib.loads((ROOT/'data/systems.toml').read_text())
    S = pl['states']; st = pl['storage']; A = {a['name']: a for a in eb['architectures']}
    out = []
    # 1-2
    rows = [[f'<span class="mono">{k}</span>', b(v['continuous_W']), b(v['peak_W']), b(v['generation_W']),
             ('<span class="warn">PARAM duty</span>' if v['time_averaged_W'] is None else b(v['time_averaged_W'])), str(len(v['open']))]
            for k, v in S.items()]
    out.append(section('p1', '1 · EPS-A', 'A power-load model in the repository, not in a study',
        '<p>EPS-A adds <code>src/wayfarer/power_loads.py</code>, a PROTOTYPE <code>[power.loads]</code> table (34 loads, 17 states, 5 faults, storage rules) in '
        '<code>data/wayfarer_3d.toml</code>, the first EPS and TMS rows of <code>data/systems.toml</code> with <code>src/wayfarer/systems.py</code>, '
        '<code>references/p1_power_loads.json</code> and 12 invariant tests. Every load carries min, nominal and max, standby, peak, start energy, duty, bus, '
        'priority, heat loop, exported energy, dependencies, source and maturity. Doctrine duties stay PARAM and are never defaulted; unknown loads stay OPEN with '
        'a planning band that is never summed into a known total. The quick pipeline passes with an empty geometry diff.</p>'))
    out.append(section('p2', '2 · LOAD MODEL', 'Load by operating state (MW, low–high, nominal)',
        bars([(k, tuple(x/1e6 for x in v['continuous_W']), 'bad' if 'ACTIVE' in k or 'HIGH' in k else ('good' if 'SURV' in k else 'info'))
              for k, v in S.items() if k not in ('HIGH_THRUST', 'COAST_HV_CONTINUOUS_ACTIVE')], 'MW continuous')
        + '<p class="muted">HIGH_THRUST (' + b(S['HIGH_THRUST']['continuous_W']) + ' MW) and the continuous-active bound (' + b(S['COAST_HV_CONTINUOUS_ACTIVE']['continuous_W'])
        + ' MW) are off this scale.</p><details><summary>All states: continuous, peak, generation, time-averaged</summary>'
        + table(['State', 'Continuous MW', 'Peak MW', 'Generation MW', 'Time-averaged MW', 'OPEN'], rows) + '</details>'))
    # 3
    au = pl['audit']
    corr = [
        ('Coast demand', 'Phase I 0.8 / 3.6 / 26 MW', f'proactive coast {b(S["COAST_HV_PROACTIVE"]["continuous_W"])} MW known; field services and drive standby moved to OPEN planning bands (~1.35 MW nominal)'),
        ('Burn heat pumps', 'F02 rated 210 MW work for 35 MW lifted', f'running work {b(au["burn_heat_pumps"]["high_thrust_work_W"])} MW: the WARM section takes 5 MW in every mode and Crown light leaves the ship'),
        ('Defense heat band', '40_THERMAL routes 15–30 MW to the warm loop', 'same numbers as the electrical band: no credit for the 5 MW Crown light that leaves the ship (conservative)'),
        ('Cryocoolers', '395 kW "rejected"', 'that is input work; the lifted 3.8 kW adds 1 % at the rejector'),
        ('Avionics allowance', '0.3 MW on the LOW section', 'about ten times the computing estimate, but it covers PMAD losses at proactive coast; the LOW section is 1 MW'),
        ('Battery mass', '800 Wh/kg plus a packaging factor', '800 Wh/kg is already pack-level: 2.5 t, installed mass OPEN; Phase I counted packaging twice'),
        ('Battery ride-through', 'Phase I: hours', f'once the black-start reserve ({st["black_start_reserve_J"]/3.6e6:,.0f} kWh) is protected, coast ride-through is {S and pl["storage"]["endurance"]["COAST_HV_PROACTIVE"]["ride_through_h"][1]*60:.0f} min'),
        ('Deadship converters', '40 kW battery converters', 'cannot carry the coast load; they are survival hardware only'),
        ('Food', '48 t "shortfall"', 'a 12-person, six-year, conventional-food scenario; six years is narrative (owner 2026-11-27): provisioning is per mission'),
        ('ECLSS strings', '"a string serves six"', 'per string, one per ring: 12 is two strings at 1.0x; 12 in one ring or on one string needs 2.0x, above the 1.7x surge'),
    ]
    out.append(section('p3', '3 · CORRECTIONS', 'Corrected assumptions and inconsistencies found',
                       table(['Item', 'Was', 'Now'], [[E(a), E(c), d] for a, c, d in corr])))
    # 4
    du = eb['duty']; rows = []
    for r in du['rows']:
        if r['buffer_J'] == 1e9 and r['surplus_W'] == 2e6:
            rows.append([f'{r["t_eng_s"]:g} s', f'{r["interval_s"]/3600:g} h', f'{r["average_W"]/1e6:.2f}', f'{r["recharge_s"]:.0f} s',
                         '<span class="good">yes</span>' if r['sustainable'] else '<span class="bad">no</span>', f'{r["max_engagement_s"]:.0f} s'])
    bufs = du['buffers_kg']
    out.append(section('p4', '4 · DEFENSE DUTY', 'Triggered active defense is sustainable while engagements are short',
        f'<p>Proactive defense ({du["proactive_W"]/1e6:.1f} MW) runs continuously; the normal active band ({du["active_W"]/1e6:.1f} MW, of which '
        f'{du["active_exported_W"]/1e6:.0f} MW leaves as light) is triggered from a dedicated buffer, never the pulse bank. With a 1 GJ buffer and 2 MW of L2 '
        'surplus for recharge:</p>' + table(['Engagement', 'Interval', 'Average MW', 'Recharge', 'Sustainable', 'Max engagement'], rows)
        + '<p>A 1 GJ buffer weighs ' + ', '.join(f'{v["1 GJ"]/1e3:.1f} t ({E(k.split(" (")[0])})' for k, v in bufs.items()) + '. '
        f'Context only: the lab dust study (Vertex profile) gives mean intervals from {du["dust"]["mean_interval_s"]["HIGH"]:.0f} s (HIGH) to months (LOW); '
        'warning times are milliseconds to seconds and neutral dust ignores fields. Engagement frequency is the open driver; the continuous-active case stays as '
        'the bounding design (see 5).</p>'))
    # 5
    order = ['B-lean: 2 x 100 % at nominal demand', 'C-lean: 3+1 at nominal demand', 'B: 2 x 60 %, essentials on either', 'C: 3+1 modular (N+1)',
             'C2: 5+1 modular', 'D: generation + storage (4 x defense buffer)', 'A: 2 x 100 %', 'E: auxiliary fusion (speculative)', 'C-bound: continuous active, 3+1', 'A-bound: continuous active, 2 x 100 %']
    names = [n for n in order if n in A] + [n for n in A if n not in order]
    rows = []
    for n in names:
        a = A[n]; rel = a.get('reliability') or {}
        p = rel.get('u=0.05', {}).get('p_short_mission')
        rows.append([E(n), f'{a["units"]} x {a["unit_W"]/1e6:.2f}', t3([m/1e3 for m in a['mass_kg']]), f'{a["waste_at_design_W"]/1e6:.0f}',
                     f'{100*a["blade_fraction_at_design"]:.0f} %', f'{a["volume_m3"]:.0f}', '–' if p is None else f'{p:.4f}', E(a['tech']), E(a.get('note', ''))[:120]])
    out.append(section('p5', '5 · GENERATION', 'Generation architectures compared',
        bars([(n.split(':')[0], tuple(m/1e3 for m in A[n]['mass_kg']), 'bad' if 'bound' in n else ('good' if 'lean' in n else 'info')) for n in names if 'bound' not in n], 't installed L2 mass')
        + table(['Architecture', 'Units x MWe', 'Mass t', 'Waste MW', 'Blade area', 'Volume m³', 'P(short), u=0.05/yr', 'Tech', 'Note'], rows)
        + fig_modularity(A)
        + f'<p>The design demand is the must-keep set with proactive defense ({b(eb["demand"]["must_keep_with_proactive_W"])} MW) plus OPEN planning bands '
        f'({b(eb["demand"]["design_proactive_W"])} MW). Fission-Brayton at 550 K rejection (efficiency {A["C: 3+1 modular (N+1)"]["unit"][1]["eta"]:.2f}) is the reference; '
        'auxiliary fusion (E) is speculative and carries the widest band. The continuous-active bound costs 900–1,300 t nominal and is not a working case.</p>'))
    # 6
    out.append(section('p6', '6 · STORAGE', 'Energy storage: ride-through, black start, defense buffer',
        table(['Store', 'Energy', 'Role', 'Finding'], [
            ['Main battery', '2 MWh usable (2.5 t pack, installed OPEN)', 'ride-through + protected black-start reserve',
             f'reserve {st["black_start_reserve_J"]/3.6e6:,.0f} kWh; ride-through {st["ride_through_J"]/3.6e6:,.0f} kWh = {pl["storage"]["endurance"]["COAST_HV_PROACTIVE"]["ride_through_h"][1]*60:.0f} min at proactive coast; end-of-life {st["end_of_life_usable_J"][1]/3.6e6:,.0f} kWh'],
            ['Pulse bank', '200 kWh / 50 MW', 'drive start only', 'never charged from the survival reserve; never used for defense'],
            ['Defense buffer', '0.1–5 GJ (sizing by duty)', 'triggered active defense', 'new line; 0.5–12 t for 1 GJ by chemistry'],
            ['L3 source', '10–40 kWe continuous', 'crew survival 30 d', 'storage alone for 30 d weighs 48 t at 800 Wh/kg: L3 needs a source'],
        ])))
    # 7
    rows = [[E(t['arch']), f'{t["Pe_W"]/1e6:.1f}', f'{t["conversion_waste_W"]/1e6:.1f}', f'{100*t["blade_fraction_plant"]:.1f} %', f'{100*t["blade_fraction_defense_warm"]:.1f} %',
             f'{t["low_section_heat_W"]/1e6:.2f} / {t["low_section_W"]/1e6:.0f}', '<span class="good">yes</span>' if t['closes_in_coast'] else '<span class="bad">no</span>'] for t in eb['thermal']]
    out.append(section('p7', '7 · THERMAL', 'Coupled thermal ledger: the blades can take L2 in coast, not in burns',
        '<p>The 1800 K hot blades, 440 K warm channels, 300 K LOW section and the habitat loops stay distinct; the 550–650 K L2 reject is a proposal on the dark '
        'hot blades in coast. Area is counted once: plant share plus defense share of the blade warm channels.</p>'
        + table(['Architecture', 'MWe', 'Waste MW', 'Blade share, plant', 'Blade share, defense', 'LOW MW / capacity', 'Closes in coast'], rows)
        + '<div class="callout">Burns drain and purge the warm channels: no credit during a burn. L2 must go to hot standby and L1 carries the ship. After a drive '
        'trip the WARM section (5 MW) supports only about 1.0–1.3 MWe of L2, not proactive defense (2.5 MW). The continuous-active bound puts 1.6 MW on the 1 MW '
        'LOW section: a reported problem, not a resize.</div>' + fig_transitions()))
    # 8
    sc = eb['L3']['scenarios']; rows = []
    for k, v in sc.items():
        best = min(v['rows'].items(), key=lambda kv: kv[1]['30 d'])
        rows.append([E(k), f'{v["P_W"][1]/1e3:.0f} kW', f'{best[1]["72 h"]/1e3:.1f}', f'{best[1]["7 d"]/1e3:.1f}', f'{best[1]["30 d"]/1e3:.1f}', E(best[0].split(' (')[0])])
    out.append(section('p8', '8 · SURVIVAL', 'An independent survival level for the crew, not for the cryo',
        table(['Scenario (high band sizing)', 'Load, nominal', '72 h t', '7 d t', '30 d t', 'Lightest'], rows)
        + '<p>Crew-only for 30 days is light (an RPS or small fission-Stirling, 6–10 t). Crew plus cryo needs ~96 t of fission-Stirling and is not a survival source: '
        f'cryo preservation depends on L2 modularity. The sealed He-3 hold is {min(eb["cryo"]["sealed_hold_h"]):.0f}–{max(eb["cryo"]["sealed_hold_h"]):.0f} h; '
        f'afterwards ~{eb["cryo"]["loss_after_hold_t_per_day"]["helium_3"]:.0f} t/day boils off. A nuclear L3 beside the refuge needs its own shield and distance.</p>'))
    # 9
    s9 = em['strings']; led = em['ledger']
    out.append(section('p9', '9 · ECLSS-A', 'Crew-12 life support: two strings, one per ring',
        f'<p>{E(s9["reading"])}. {E(s9["finding"])}</p>'
        + table(['Case', 'People per string', 'Load', 'Within 1.7x'], [[E(k), f'{v["per_string"]:.0f}', f'{v["load"]:.1f}x', '<span class="good">yes</span>' if v['within_max'] else '<span class="bad">no</span>'] for k, v in s9['cases'].items()])
        + table(['Resource (12 crew, six-year reference)', 't'], [['O2 generated', f'{led["O2_generated_t"]:.1f}'], ['CO2 removed', f'{led["CO2_removed_t"]:.1f}'],
               ['Water turnover', f'{led["water_turnover_t"]:.0f}'], ['Water makeup at 98 % / 90 % recovery', f'{led["water_makeup_t"]["98 % recovery"]:.1f} / {led["water_makeup_t"]["90 % recovery"]:.1f}'],
               ['Water lost with vented methane (Sabatier)', f'{led["sabatier_methane_vent_water_loss_t"]:.1f}'], ['Waste', f'{led["waste_t"]:.0f}']])
        + f'<p><b>Shield water (DR-08):</b> {E(em["shield_water"]["verdict"])}</p><ul>' + ''.join(f'<li>{E(r)}</li>' for r in em['shield_water']['rules']) + '</ul>'))
    # 10 mission + provisioning
    dest_rows = []
    for d in M['destinations']:
        r = d['speeds']['0.016 c']; r4 = d['speeds']['0.004 c']
        dest_rows.append([E(d['name']), f'{d["one_way_AU"]:,.0f}', f'{r["constant_velocity_one_way_d"]:.0f} d', f'{r["one_way_d"]:.0f} d', f'{d["ops_d"]} d',
                          f'{r["mission_yr"]:.2f} yr', f'{r["propellant_t"]:,.0f} t', f'{r4["mission_yr"]:.2f} yr / {r4["propellant_t"]:,.0f} t', E(d['purpose'])])
    reach = [[E(k), f'{v["max_one_way_AU"]:,.0f} AU'] for k, v in M['reach'].items()]
    pv = M['provisioning']
    prov_rows = [[E(k)] + [f'{pv[k][c][f]["total_kg"]/1e3:.1f}' for c in ('6 crew', '12 crew') for f in ('conventional', 'dehydrated')]
                 + [str(pv[k]['12 crew']['conventional']['containers'])] for k in pv]
    fits = M['fits_10t']; fo = M['food_only_days_10t']
    out.append(section('p10', '10 · MISSIONS AND PROVISIONING', 'Six years is a story; provisioning is per mission',
        '<div class="callout k">Owner clarification 2026-11-27: design occupancy 12 stays; six people for about six years is a narrative scenario. '
        'Machinery is sized for 12; food, consumables, medical stock and spares are mission cargo loaded in standard dry-store containers.</div>'
        + '<h3>What 0.016 c reaches</h3><p>The canon ramp (0 to 1.5 g over 7.55 d, 6.97 AU) sets each of four burns. At 0.016 c the ship covers about '
        '1,012 AU a year; relativistic terms are below 10⁻⁴. Every trip that reaches cruise speed burns the full four-burn propellant load; a slower cruise saves most of it.</p>'
        + table(['Destination', 'AU', 'Const-v one way', 'With burns', 'Ops', 'Round trip', 'Propellant', 'At 0.004 c', 'Purpose'], dest_rows)
        + '<div class="two"><div>' + table(['Provisioning profile', 'Reach at 0.016 c'], reach) + '</div><div>'
        + table(['10 t line covers (12 crew)', 'Months'], [[E(k.split(', ')[1]) + ', all crew consumables', f'{fits[k]["months"]:.1f}'] for k in fits if k.startswith('12')]
                + [[E(k.split(', ')[1]) + ', food alone', f'{v/30.44:.1f}'] for k, v in fo.items() if k.startswith('12')]) + '</div></div>'
        + '<h3>Loaded consumables by profile (t, includes spares and the 30-day reserve)</h3>'
        + table(['Profile', '6 crew conv.', '6 crew dehydr.', '12 crew conv.', '12 crew dehydr.', 'Containers (12, conv.)'], prov_rows)
        + f'<p>The 10 t line is a 7–10 month load for 12 when it carries every crew consumable (water makeup, oxygen water, provisions, reserve), or 14–28 months '
        f'when read as food alone. A 12-month standard mission for 12 loads {M["standard_load"]["t"]:.0f} t in {M["standard_load"]["containers"]} of 54 containers. '
        'Garden production and shield water are not credited.</p>'))
    # 11 mass
    mm = em['mass']; rows = [[E(r['item']), E(r['budget']), t3(r['t'], 1), f'{r["x_m"]:.0f}'] for r in mm['adds']]
    pc = mm['pcsc']
    out.append(section('p11', '11 · MASS', 'Integrated mass ledger: no architecture closes in today\'s lines',
        table(['Item', 'Budget owner', 't (low–high, nominal)', 'x m'], rows)
        + f'<p>Added mass (machinery, plus RCS propellant and the standard crew load as departure cargo) {t3(mm["total_added_t"])} t on a {mm["dry_ship_t"]:,.0f} t dry ship. At the same mission delta-v it needs {t3(mm["extra_propellant_t"])} t more '
        f'propellant (with tankage); with propellant fixed the ship loses {100*mm["delta_v_fraction_lost_if_propellant_fixed"][1]:.0f} % of its delta-v. The dry centre of mass moves '
        f'{abs(mm["cg_shift_m"]):.0f} m aft (from x {mm["dry_cg_x_m"]:.0f} m to {mm["dry_cg_x_after_m"]:.0f} m). The 50 t power/computers/steering/comms item holds '
        f'{t3(pc["committed_t"], 1)} t today and has {pc["left_t"][1]:.1f} t left ({pc["left_t"][2]:.1f} to {pc["left_t"][0]:.1f}): none of the generation fits it. Power mass is kept apart from the Vertex drive mass; '
        'L1 and the burn heat pumps scale with the drive architecture. Empty dry-store volume is not unused mass.</p>'
        + '<div class="callout">Smallest credible architecture: C-lean L2 (3+1 x 1.75 MWe) with scatter shielding (~210 t), L1 sized by the drive (~230 t), running burn heat pumps '
        '(~120 t), a 30-day crew-only L3 (~12 t). Shortfall against today\'s lines: about 590 t nominal, owned by three proposed lines.</div>'))
    # 12 placement
    lay_rows = []
    for n, L in P['layouts'].items():
        lay_rows.append([E(n), E(L['districts']), f'{L["units"]}', f'{L["cone_half_angle_needed_deg"]:.1f}°', f'{L["shadow_shield_kg"][1]/1e3:.1f}',
                         f'{L["side_band_kg"][1]/1e3:.1f}', f'{L["per_unit_shield_kg"][1]/1e3:.1f}', 'yes' if L['repurposes_dry_store'] else 'no', E(L['note'])])
    env = P['envelopes']['C-lean']
    tg = P['layouts']['L-E aft cluster M1-M2 (3+1, aft of all crew spaces)']['targets']
    out.append(section('p12', '12 · PLACEMENT', 'Placement: the reactors belong aft of every crewed space',
        fig_layouts(P) + table(['Layout', 'Districts', 'Units', 'Cone', 'Shadow t/unit', 'Scatter band t/unit', 'Shield t/unit', 'Uses dry store', 'Note'], lay_rows)
        + '<h3>Dose screen, layout L-E (8 MWt unit, order of magnitude)</h3>'
        + table(['Region', 'Distance m', 'Off-axis', 'Bare Sv/h', 'e-folds needed', 'In cone'], [[E(r['target']), f'{r["d_m"]:.0f}', f'{r["off_axis_deg"]:.0f}°', f'{r["bare_Sv_h"]:.2g}',
                                                                                         '–' if r['efolds_needed'] is None else f'{r["efolds_needed"]:.1f}', 'yes' if r['in_shadow_cone'] else '<span class="bad">no</span>'] for r in tg])
        + f'<p>Assembly-specific envelopes replace the Phase I 1 m rule: a 1.75 MWe unit needs {t3(env["unit_total_m3"])} m³ with service faces and insulation, plus a '
        f'{env["removal_lane_m3"]:.0f} m³ removal lane, about {env["modules_needed"][1]:.2f} of a module pair. Blade single scatter returns '
        '0.1–1 % of the bare direct dose to the rings, so a shadow shield alone is not enough: each unit needs a blade-facing band (~19 t). '
        'Keel lanes, EVA and hands-on maintenance beside a running unit need 21–24 e-folds: no crew in line of sight of a running unit; drones only. '
        'The 12.5° cone is a geometric concept, not proof; this screen decides where a transport calculation is needed.</p>'))
    # 13 FMEA
    rows = [[f'<span class="mono">{s["id"]}</span>', E(s['scenario']), E(s['immediate']), E(s['time_to_irreversible']), E('; '.join(s['common_mode'])),
             E(s['crew_survival']), E(s['ship_and_mission'])] for s in F['scenarios']]
    out.append(section('p13', '13 · FAILURE MODES', 'Crew survival and ship survival are different questions',
        table(['ID', 'Scenario', 'Immediate', 'Time to irreversible', 'Common mode', 'Crew', 'Ship and mission'], rows, 'gap')
        + f'<p>{E(F["summary"]["crew"])} {E(F["summary"]["ship"])} {E(F["summary"]["not_credited"])}</p>'
        + '<details><summary>Shed, keep, recovery and uncertainty per scenario</summary>'
        + table(['ID', 'Independent resources', 'Shed', 'Keep', 'Recovery', 'Uncertainty'], [[s['id'], E('; '.join(s['independent_resources'])), E(', '.join(s['sheddable'])),
                                                                                        E(', '.join(s['must_keep'])), E(s['recovery']), E(s['uncertainty'])] for s in F['scenarios']])
        + '</details>' + fig_domains()))
    # 14 registry
    out.append(section('p14', '14 · REGISTRY', 'The registry in the repository',
        f'<p><code>data/systems.toml</code> holds {len(reg["system"])} assemblies (EPS and TMS first) with one physical owner, one mass-budget owner (a '
        '<code>physics.mass_budget</code> line or a PROPOSED line), its <code>power.loads</code> ids, heat loop, interfaces, failure domain, candidate districts, '
        'sources and maturity. Values owned elsewhere are referenced, not copied; an unsized assembly stays OPEN. The Phase I 56-row study registry stays the '
        'reference for the other families.</p>'
        + table(['ID', 'Assembly', 'Budget owner', 'Mass t', 'Domain', 'Maturity'], [[f'<span class="mono">{r["id"]}</span>', E(r['name']), E(r['budget_item']),
                ('OPEN' + (', planning ' + '–'.join(f'{x/1e3:.0f}' for x in (r['planning_kg'][0], r['planning_kg'][2])) if 'planning_kg' in r else '')) if r.get('mass_open') else t3([m/1e3 for m in r['mass_kg']], 1),
                E(r['failure_domain']), f'M{r["maturity"]}'] for r in reg['system']])
        + fig_levels() + fig_dependencies()))
    # 15 DR
    drs = [
        ('DR-01', 'Defense duty', 'Proactive continuous + triggered active from a dedicated buffer is sustainable for short engagements; frequency is OPEN (dust at 0.016 c).', 'Keep as working case; continuous active stays the bound (~940 t).'),
        ('DR-02', 'L1/L2/L3', 'Fission-Brayton L2, N+1 modular; fusion L2 speculative.', 'Adopt C-lean 3+1 as the working L2.'),
        ('DR-03', 'Blade reuse', 'Coast: plant takes ~13 % of the blade warm area. Burns: no credit.', 'Investigate further; no temperatures or coolants approved.'),
        ('DR-04', 'Mass lines', 'No architecture fits 50 t; three proposed lines needed.', 'Owner: create burn_generation, ship_service_generation, power_thermal_machinery.'),
        ('DR-05', 'Survival 30 d', 'Crew-only 30 d: 6–12 t source. Cryo is not an L3 job.', 'Keep 30 d crew-only; cryo on L2 N+1.'),
        ('DR-06', 'Cryo', '58–77 h sealed hold; 3 K stage critical.', 'N+1 trains on A and B; spare 3 K lift.'),
        ('DR-07', 'Food', 'Per-mission provisioning; 10 t ≈ 7–10 months for 12 (all consumables).', 'Owner: pick the nominal mission (12 months proposed).'),
        ('DR-08', 'Shield water', '10 % draw covers 98 %-recovery makeup with margin over six years.', 'Floor 90 % of ring areal density; refuge never.'),
        ('DR-09', 'RCS', '~10–16 t propellant for four flips + docking + trim; cold gas ~80 t.', 'Keep open; H2/O2 from boil-off and electrolysis is the lead.'),
        ('DR-10', 'ORUs', 'Unpressurized ORUs; no crew access beside running units.', 'Adopt; drones service the plant district.'),
        ('DR-11', 'Braking protection', 'Separate workstream; interfaces kept in the registry.', 'No change.'),
        ('DR-12', 'Dry store', 'Preferred layout L-E uses M1–M2 (12 of 54 containers); logistics need 2–12 per mission.', 'Owner: allow M1–M2 for L2 as a candidate.'),
        ('DR-13', 'Registry', 'EPS/TMS rows in data/systems.toml, references not copies.', 'Extend family by family.'),
        ('DR-14', 'Mission basis (new)', 'Six years is narrative; profiles 6 months to 10 years.', 'Owner: nominal 12 months, extended 24–36 by logistics modules, service life 10–20 yr.'),
        ('DR-15', 'Crew exclusion (new)', 'No crew in line of sight of a running unit; aft district drone-only.', 'Owner: accept the aft nuclear district.'),
    ]
    out.append(section('p15', '15 · DECISIONS', 'Decision register, updated', '<ol class="dr">' + ''.join(
        f'<li><b class="id">{a}</b><b>{E(c)}.</b> {E(d)} <span class="rec">Proposal:</span> {E(e)}</li>' for a, c, d, e in drs) + '</ol>'))
    # 16
    probs = [
        ('ENG-P2-01', 'Blade scatter defeats a shadow-only shield; +54 t across C-lean (transport calculation needed).'),
        ('ENG-P2-02', 'No crew route past a running unit: keel lanes, EVA and maintenance aft of L2 become drone-only.'),
        ('ENG-P2-03', 'Power machinery adds ~600 t dry (nominal): +1,150 t propellant or −18 % delta-v; centre of mass 31 m aft.'),
        ('ENG-P2-04', 'L2 has no sink in burns (drained channels); after a drive trip only ~1.0–1.3 MWe until refill.'),
        ('ENG-P2-05', 'LOW section is 1 MW; the active bound puts 1.6 MW on it.'),
        ('ENG-P2-06', 'Battery ride-through is ~10 minutes once the black-start reserve is protected.'),
        ('ENG-P2-07', '12 people in one ring, or on one ECLSS string, exceed the 1.7x surge.'),
        ('ENG-P2-08', 'Sabatier vents ~6 t of water over six years; close the loop or carry makeup.'),
        ('ENG-P2-09', 'Defense engagement frequency at 0.016 c is unknown; it sets the buffer.'),
        ('ENG-P2-10', 'Drive standby and restart energy are OPEN; they set L1 and the F03 gap.'),
        ('ENG-P2-11', 'L2 reliability falls with mission length: P(lose two of four) 1.3 % at 12 months, 21 % at 5 years (u = 0.05/yr).'),
        ('ENG-P2-12', 'Space reactor core life (7–15 full-power years) is shorter than a 20-year service life: plan module swaps.'),
    ]
    out.append(section('p16', '16 · NEW PROBLEMS', 'New engineering problems', table(['ID', 'Problem'], [[f'<span class="mono">{a}</span>', E(c)] for a, c in probs])))
    # 17
    out.append(section('p17', '17 · NEXT', 'Preferred working architecture and the first production-modelling task',
        '<div class="callout k"><p><b>Preferred working architecture:</b> L2 as four 1.75 MWe fission-Brayton units (3+1), rejecting at 550 K into the dark hot blades in '
        'coast, each with a shadow shield and a blade-facing scatter band, clustered aft of every crewed space (layout L-E, M1–M2, three blade sectors, buses A and B '
        'alternating). L1 from the drive hot loop for burns only. L3 a 10–40 kWe RPS or small fission-Stirling at the refuge with its own shield. Main battery '
        'for ride-through and black start; a dedicated defense buffer. Proactive defense continuous, active triggered. Consumables per mission in dry-store '
        'containers: 12-month standard mission for 12.</p>'
        '<p><b>Still not closed:</b> mass (~590 t beyond today\'s lines), scatter dose (needs transport), engagement frequency, drive standby energy, the burn-to-coast '
        'protection gap.</p></div>'
        '<div class="callout"><p><b>First production-modelling task (after owner approval):</b> EPS-G1, a parametric <code>power_plant</code> generator for one L2 unit '
        'envelope (reactor, shadow shield and scatter band, Brayton unit, recuperator, PCU) driven by <code>data/systems.toml</code> EPS-02, placed as REP_PROXY in '
        'the M1–M2 candidate with its crew exclusion and removal lane as inspection volumes. No silhouette change, no radiator change, one unit first, '
        'reviewed at whole-ship and human scale before repetition.</p></div>'))
    return '\n'.join(out)


if __name__ == '__main__':
    print(len(build()))
