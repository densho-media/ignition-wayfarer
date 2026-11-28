"""3D integration Stage F: electrical architecture L1 / L2 / L3, buses, switchgear, ride-through, restart, defense storage, survival and data
(EPS-L1, EPS-BUS, EPS-STOR at M2). STUDY, PROTOTYPE, noncanon, Track F1.

Function: deliver L2 power to every load through three independent bus sectors (one per unit, one per failure domain), keep the drive's L1
power apart, keep the refuge alive on L3 with no shared energy, and ride through any single fault.
Calculated: conductor sizes and masses of the buses, feeders, ties, defense and L1 buses against the Phase VI distribution line; resistive
loss; storage energy and power against each duty (Phase V V-D storage table and transient); the single-fault matrix (what is left, what is
shed, how long storage bridges); separation distances between failure domains, including the Stage E NaK loops and the H6a trunks.
Writes ../results/i3d_electrical.json and i3d_electrical_oneline.svg, i3d_electrical_section.svg.
"""
import json
import math
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent; W = HERE.parent; R = W/'results'
CFG = tomllib.loads((HERE/'f1_integration.toml').read_text()); E = CFG['electrical']
P5 = json.loads((R/'phase5.json').read_text()); P6 = json.loads((R/'phase6.json').read_text())
PW = json.loads((R/'i3d_power.json').read_text()); RAD = json.loads((R/'i3d_radiators.json').read_text()); H6 = json.loads((R/'i3d_h6a.json').read_text())
LAY = {x['name']: x for x in P6['layout'] if x['family'] == 'ELECTRICAL'}
PE = 3.5e6; PMAD = 0.95


def pol(az, r): a = math.radians(az); return (r*math.cos(a), r*math.sin(a))


def conductor(P, V=None, J=None):
    V = V or E['voltage_V']; J = J or E['J_A_mm2']; I = P/V; A = I/J*1e-6           # m2 per pole
    kgm = 2*A*2700.0*E['duct_factor']; Rm = E['rho_al']/A
    return dict(P_W=P, I_A=I, A_mm2=A*1e6, kg_m=kgm, ohm_m_pole=Rm)


def buses():
    x0, x1 = E['bus_x']; L = x1-x0; rows = []
    sec = conductor(PE*PMAD)
    for i, az in enumerate(E['bus_az_deg'], 1):
        rows.append(dict(id=f'BUS-{i}', what=f'main HVDC bus sector {i}', az=az, r=E['bus_radius_m'], x=(x0, x1), length_m=L, **sec,
                         mass_t=sec['kg_m']*L/1e3, loss_W=sec['I_A']**2*sec['ohm_m_pole']*2*L/2, domain=f'sector {i}'))
    fd = conductor(PE)
    for u in PW['district']:
        bi = E['unit_to_bus'][str(u['index'])]; az = E['bus_az_deg'][bi-1]
        rows.append(dict(id=f'FDR-U{u["index"]}', what=f'unit {u["index"]} feeder (PMAD -> bus {bi})', az=az, length_m=8.0, **fd, mass_t=fd['kg_m']*8.0/1e3,
                         loss_W=fd['I_A']**2*fd['ohm_m_pole']*2*8.0, domain=f'sector {bi}'))
    tie = conductor(PE*PMAD/2); arc = 2*math.pi*E['bus_radius_m']/3
    for x in E['tie_x']:
        for i in range(3):
            rows.append(dict(id=f'TIE-{i+1}{(i+1) % 3+1}@{x:.0f}', what=f'tie {i+1}-{(i+1) % 3+1} at x {x:.0f} (normally open)', x=(x, x), length_m=arc, **tie,
                             mass_t=tie['kg_m']*arc/1e3, loss_W=0.0, domain='tie (both sectors)'))
    l1 = conductor(P6['direct_conversion']['F1']['rows'][0]['P_e_W'] if P6['direct_conversion'].get('F1') else 14.27e6, V=10e3)
    rows.append(dict(id='BUS-L1', what='L1 bus (drive services, burns only), 10 kV', x=(-140.0, -80.0), length_m=60.0, **l1, mass_t=l1['kg_m']*60.0/1e3,
                     loss_W=l1['I_A']**2*l1['ohm_m_pole']*2*60.0, domain='L1'))
    df = conductor(21e6, V=6e3, J=4.0)                                    # burst rating: 10 s pulses, higher current density allowed
    rows.append(dict(id='BUS-DEF', what='defense bus (switchgear -> buffers), 6 kV, burst-rated', x=(14.0, 42.0), length_m=28.0, **df, mass_t=df['kg_m']*28.0/1e3,
                     loss_W=0.0, domain='defense'))
    rf = conductor(0.1e6, V=270.0)
    rows.append(dict(id='BUS-REF', what='refuge bus (L3 + survival bridge), 270 V', x=(95.0, 106.0), length_m=11.0, **rf, mass_t=rf['kg_m']*11.0/1e3, loss_W=0.0,
                     domain='refuge'))
    total = sum(r['mass_t'] for r in rows); led = next(v['t'][1] for k, v in P6['mass']['F1']['items'].items() if k == 'distribution')
    return dict(rows=rows, total_t=total, ledger_t=led, loss_W=sum(r['loss_W'] for r in rows if r['id'].startswith('BUS-') and r['id'][4:].isdigit()))


def storage():
    st = {s['store']: s for s in P5['electrical']['stores']}; tr = P5['electrical']['transient']; nom = next(t for t in tr if t['case'] == 'nom') if any(t['case'] == 'nom' for t in tr) else tr[0]
    rt = st['Ride-through cells']; rs = st['Independent restart pack (R1b)']; df = st['Defense buffer']; sv = st['Survival bridge (refuge)']; mb = st['Main battery (EPS-A)']
    load = nom['load_W']; cap2 = 2*PE*PMAD
    restart_need_kWh = 0.5e6*0.5/1e3                                         # TAC motoring + heaters 0.5 MW for 30 min, PROTOTYPE
    surplus = 3*PE*PMAD-load
    rows = [dict(store='Ride-through cells (4 per sector)', duty='unit trip: peak deficit until the survivors ramp', need_kWh=nom['storage_kWh_used'], need_W=nom['peak_deficit_W'],
                 have_kWh=4*rt['kWh'], have_W=4*rt['MW']*1e6, ok=nom['storage_power_ok'] and nom['storage_energy_ok'], note=f'restored in {nom["t_restored_s"]:.0f} s (Phase V transient)'),
            dict(store='Main battery (EPS-A, canon)', duty='coast black-start services', need_kWh=None, need_W=None, have_kWh=mb['kWh'], have_W=mb['MW']*1e6, ok=True, note='shared main bus'),
            dict(store='Restart pack R1b (one per unit)', duty='restart one L2 unit with no bus power', need_kWh=restart_need_kWh, need_W=0.5e6, have_kWh=rs['kWh'], have_W=rs['MW']*1e6,
                 ok=rs['kWh'] >= restart_need_kWh, note='own cells, converter and start bus; never tied to the refuge'),
            dict(store='Defense buffer (4 modules)', duty='engagement burst 21 MW', need_kWh=21e6*10/3.6e6, need_W=21e6, have_kWh=df['kWh'], have_W=df['MW']*1e6,
                 ok=df['kWh'] >= 21e6*10/3.6e6*0.99, note=f'{df["kWh"]*3.6e6/21e6:.0f} s burst; recharge {df["kWh"]*3.6e6/max(surplus, 1):.0f} s from the {surplus/1e6:.1f} MW L2 surplus'),
            dict(store='Survival bridge (refuge)', duty='crew survival until L3 runs', need_kWh=0.05e6*4/1e3, need_W=0.05e6, have_kWh=sv['kWh'], have_W=sv['MW']*1e6,
                 ok=sv['kWh'] >= 200, note=f'{sv["kWh"]/50:.0f} h at 50 kW; L3 start 4 h assumed (type OPEN)')]
    return dict(rows=rows, load_nominal_W=load, two_unit_capacity_W=cap2, three_unit_capacity_W=3*PE*PMAD, surplus_W=surplus)


def faults(ST):
    load = ST['load_nominal_W']; c1 = PE*PMAD; ess = 0.6*load                       # essential share (ECLSS, thermal pumps, GNC, data, protection), PROTOTYPE
    rows = [
        dict(fault='one L2 unit trips', left=f'2 units, {2*c1/1e6:.2f} MW', shed='none (survivors to 100 %)', bridge='ride-through cells ~10 s', ok=2*c1 >= load),
        dict(fault='one bus sector faults (cable or switchgear)', left=f'2 sectors; the faulted sector\'s unit islands on its feeder', shed='loads on the faulted sector move to ties (normally open, closed in ~0.2 s)',
             bridge='ride-through on the healthy sectors', ok=2*c1 >= load),
        dict(fault='two units trip (N-2)', left=f'1 unit, {c1/1e6:.2f} MW', shed=f'non-essential ({(load-ess)/1e6:.1f} MW); essential {ess/1e6:.1f} MW', bridge='ride-through + main battery; restart packs restart a unit',
             ok=c1 >= ess),
        dict(fault='all L2 lost (district event)', left='main battery 2 MWh, restart packs, refuge on L3', shed='everything but essential coast loads, then refuge only', bridge=f'main battery {2000/(ess/1e3):.1f} h at the essential load',
             ok=False, note='restart from R1b; if all units are lost the crew retreat to the refuge (L3)'),
        dict(fault='L1 bus fault in a burn', left='L2 unchanged; the drive services fall back to L2 within its surplus', shed='L1 loads above the L2 surplus (burn heat pumps are an existing allocation)', bridge='none needed for L2',
             ok=True),
        dict(fault='data network A lost', left='network B (physically separated, 9.2 m)', shed='none', bridge='-', ok=True),
        dict(fault='defense buffer module fault', left='3 of 4 modules (75 % burst energy)', shed='burst length', bridge='-', ok=True),
        dict(fault='refuge bus fault', left='survival bridge or L3, not both', shed='refuge comfort loads', bridge=f'{250/50:.0f} h', ok=True)]
    return rows


def separation():
    x = lambda n: LAY[n]
    pts = {'BUS-1': pol(30, 5.0), 'BUS-2': pol(150, 5.0), 'BUS-3': pol(270, 5.0), 'L1': pol(CFG['district']['l1_bus']['azimuth_deg'], CFG['district']['l1_bus']['radius_m']),
           'DATA-A': (4.6, 0.0), 'DATA-B': (-4.6, 0.0)}
    for u in PW['district']:
        az = u['azimuth_deg']+60
        for sgn, leg in ((1, 'S'), (-1, 'R')): pts[f'NaK-U{u["index"]}{leg}'] = pol(az+sgn*CFG['radiators']['loop']['offset_deg'], CFG['radiators']['loop']['radius_m'])
    rad = {'BUS': 0.25, 'L1': 0.22, 'DATA': 0.08, 'NaK': RAD['nak']['transport']['D_m']/2+0.03}
    rr = lambda k: rad['BUS'] if k.startswith('BUS') else rad['L1'] if k == 'L1' else rad['DATA'] if k.startswith('DATA') else rad['NaK']
    dom = lambda k: k.split('-')[0] if not k.startswith('NaK') else 'NaK-U'+k[5]
    out = []
    keys = list(pts)
    for i, a in enumerate(keys):
        for b in keys[i+1:]:
            if dom(a) == dom(b) and not a.startswith('BUS'): continue
            d = math.dist(pts[a], pts[b])-rr(a)-rr(b)
            if d < 1.5: out.append(dict(a=a, b=b, clear_m=d, action=('arc/fire barrier + separate cable trays' if d < 1.0 else 'acceptable (> 1 m)')
                                       + ('; 1000 K line: multi-foil insulation and a thermal barrier' if 'NaK' in a+b else '')))
    return sorted(out, key=lambda r: r['clear_m'])


def geometry(BU):
    g = []
    for i, az in enumerate(E['bus_az_deg'], 1):
        y, z = pol(az, E['bus_radius_m']); g.append(dict(kind='seg', name=f'EL_Bus{i}', p0=(E['bus_x'][0], y, z), p1=(E['bus_x'][1], y, z), r=0.25, dom=f'S{i}',
                                                           meaning=f'main HVDC bus sector {i} ({E["voltage_V"]/1e3:.0f} kV, {BU["rows"][i-1]["A_mm2"]:.0f} mm2 Al per pole)'))
        for x in E['tie_x']:
            g.append(dict(kind='box', name=f'EL_Breaker{i}_{x:.0f}', c=(x, *pol(az, E['bus_radius_m']-0.45)), half=(0.5, 0.35, 0.35), dom=f'S{i}', meaning=f'sector {i} breaker / tie station at x {x:.0f}'))
            a0 = az; a1 = E['bus_az_deg'][i % 3]; n = 8
            for k in range(n):
                p = pol(a0+(((a1-a0) % 360))*k/n, E['bus_radius_m']-0.45); q = pol(a0+(((a1-a0) % 360))*(k+1)/n, E['bus_radius_m']-0.45)
                g.append(dict(kind='seg', name=f'EL_Tie{i}{i % 3+1}_{x:.0f}_{k}', p0=(x, *p), p1=(x, *q), r=0.06, dom='TIE', meaning=f'normally-open tie {i}-{i % 3+1} at x {x:.0f}'))
        for lc in E['load_centres']:
            g.append(dict(kind='box', name=f'EL_{lc["id"]}_{i}', c=(lc['x'], *pol(az, E['bus_radius_m']-1.0)), half=(0.8, 0.45, 0.6), dom=f'S{i}', meaning=f'{lc["id"]} sector {i}: {lc["what"]}'))
    for u in PW['district']:
        bi = E['unit_to_bus'][str(u['index'])]; pm = next(p for p in PW['unit']['parts'] if p['key'] == 'pmad')
        a = math.radians(u['azimuth_deg']); xp = u['centre'][0]+pm['u']; r0 = CFG['district']['unit_radius_m']+0.6
        g.append(dict(kind='poly', name=f'EL_Feeder_U{u["index"]}', points=[(xp, r0*math.cos(a), r0*math.sin(a)), (xp+1.5, *pol(E['bus_az_deg'][bi-1], E['bus_radius_m']))], r=0.09,
                      dom=f'S{bi}', meaning=f'unit {u["index"]} feeder to bus {bi}'))
    y, z = pol(CFG['district']['l1_bus']['azimuth_deg'], CFG['district']['l1_bus']['radius_m'])
    g.append(dict(kind='seg', name='EL_L1Bus', p0=(-140.0, y, z), p1=(-80.0, y, z), r=0.22, dom='L1', meaning='L1 bus 10 kV (burns only), own slot'))
    g.append(dict(kind='plate', name='EL_Barrier_L1_Bus1', c=(-110.0, *pol(30.0, 4.3)), half=(30.0, 0.02, 0.5), az=30.0, dom='BAR', meaning='arc/fire barrier between L1 and bus 1 (0.96 m apart)'))
    g.append(dict(kind='seg', name='EL_DefenseBus', p0=(14.0, 0.0, 3.6), p1=(42.0, 0.0, 3.6), r=0.12, dom='DEF', meaning='defense bus 6 kV, burst-rated, defense loads only'))
    g.append(dict(kind='box', name='EL_L3Source', c=(CFG['electrical']['l3']['x'], 0.0, -3.0), half=(1.2, 0.9, 0.8), dom='REF', meaning=CFG['electrical']['l3']['what']))
    g.append(dict(kind='seg', name='EL_RefugeBus', p0=(95.0, 0.0, -2.2), p1=(106.0, 0.0, -2.2), r=0.05, dom='REF', meaning='refuge bus 270 V (L3 + survival bridge), no tie to the main buses'))
    for nm, y in (('A', 4.6), ('B', -4.6)):
        g.append(dict(kind='seg', name=f'EL_Data{nm}', p0=(-140.0, y, 0.0), p1=(140.0, y, 0.0), r=0.05, dom=f'D{nm}', meaning=f'data and control network {nm} (fibre)'))
    return g


def svg_oneline(BU, ST, FA, path):
    w, h = 1000, 470
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="Inter,system-ui,sans-serif" font-size="12" role="img" aria-label="Electrical one-line">',
         '<style>.t{fill:var(--fg,#223)} .m{fill:var(--muted,#667)}</style>',
         '<text x="20" y="22" class="t" font-weight="600">One-line: three L2 sectors, normally-open ties, L1 apart, refuge on L3</text>']
    col = ['#3f6fd8', '#2fa36b', '#c9852a']
    for i in range(3):
        y = 90+i*80
        o.append(f'<rect x="30" y="{y-18}" width="135" height="36" rx="5" fill="{col[i]}" fill-opacity="0.2" stroke="{col[i]}"/><text x="38" y="{y+4}" class="t">L2 unit {i+1} 3.5 MWe</text>')
        o.append(f'<line x1="165" y1="{y}" x2="900" y2="{y}" stroke="{col[i]}" stroke-width="5"/><text x="910" y="{y+4}" class="m">bus {i+1}</text>')
        for j, x in enumerate((260, 520, 780)):
            o.append(f'<rect x="{x-8}" y="{y-8}" width="16" height="16" fill="#fff" stroke="#333"/>')
        for j, (x, lab) in enumerate(((330, 'district'), (590, 'mid / WARM-LOW'), (850, 'habitat'))):
            o.append(f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y+24}" stroke="#555"/><text x="{x-30}" y="{y+36}" class="m" font-size="10">{lab}</text>')
        o.append(f'<rect x="190" y="{y-30}" width="40" height="12" fill="#8a6fd8"/><text x="236" y="{y-20}" class="m" font-size="10">ride-through</text>')
    for x in (260, 520, 780):
        o.append(f'<line x1="{x}" y1="98" x2="{x}" y2="242" stroke="#333" stroke-dasharray="4 3"/>')
    o.append('<text x="270" y="300" class="m">dashed: normally-open ties at x -78 / 14 / 98 (close in ~0.2 s on a sector fault)</text>')
    o.append('<rect x="40" y="320" width="150" height="34" rx="5" fill="#e0553a" fill-opacity="0.2" stroke="#e0553a"/><text x="48" y="342" class="t">L1 (drive, burns) 10 kV</text>')
    o.append('<rect x="230" y="320" width="190" height="34" rx="5" fill="#d23a6a" fill-opacity="0.2" stroke="#d23a6a"/><text x="238" y="342" class="t">defense bus + 4 buffers 21 MW</text>')
    o.append('<rect x="460" y="320" width="200" height="34" rx="5" fill="#777" fill-opacity="0.2" stroke="#777"/><text x="468" y="342" class="t">refuge: L3 + survival bridge</text>')
    o.append('<rect x="700" y="320" width="200" height="34" rx="5" fill="#5aa0b8" fill-opacity="0.2" stroke="#5aa0b8"/><text x="708" y="342" class="t">data A / B (fibre, 9.2 m apart)</text>')
    o.append(f'<text x="40" y="390" class="m">Conductors: {BU["total_t"]:.1f} t drawn (Phase VI distribution line {BU["ledger_t"]:.1f} t); bus loss {BU["loss_W"]/1e3:.0f} kW at full load.</text>')
    o.append(f'<text x="40" y="410" class="m">Single faults: {sum(1 for f in FA if f["ok"])} of {len(FA)} ride through; the district-loss case falls back to the main battery, restart packs and the refuge.</text>')
    o.append('</svg>'); path.write_text('\n'.join(o))


def svg_section(SEP, path):
    w, h = 560, 560; c = 280; s = 38
    P = lambda y, z: (c+y*s, c-z*s)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" style="max-width:100%;height:auto" font-family="Inter,system-ui,sans-serif" font-size="11" role="img" aria-label="Electrical cross-section">',
         '<style>.t{fill:var(--fg,#223)} .m{fill:var(--muted,#667)}</style>', '<text x="14" y="20" class="t" font-weight="600">Cross-section at x -80 (looking forward): failure domains</text>']
    o.append(f'<circle cx="{c}" cy="{c}" r="{6.0*s}" fill="none" stroke="#999"/><circle cx="{c}" cy="{c}" r="{5.6*s}" fill="none" stroke="#bbb" stroke-dasharray="3 3"/>')
    col = {'BUS': '#3f6fd8', 'L1': '#e0553a', 'DATA': '#5aa0b8', 'NaK': '#e0762f', 'UNIT': '#999'}
    for u in PW['district']:
        y, z = pol(u['azimuth_deg'], CFG['district']['unit_radius_m']); x, yy = P(y, z)
        o.append(f'<circle cx="{x:.1f}" cy="{yy:.1f}" r="{1.0*s:.1f}" fill="#d9d4c8" stroke="#999"/><text x="{x-12:.1f}" y="{yy+4:.1f}" class="m">U{u["index"]}</text>')
    for i, az in enumerate(E['bus_az_deg'], 1):
        x, yy = P(*pol(az, 5.0)); o.append(f'<circle cx="{x:.1f}" cy="{yy:.1f}" r="{0.25*s:.1f}" fill="{col["BUS"]}"/><text x="{x+10:.1f}" y="{yy-8:.1f}" class="t">bus {i}</text>')
    x, yy = P(*pol(30, 3.6)); o.append(f'<circle cx="{x:.1f}" cy="{yy:.1f}" r="{0.22*s:.1f}" fill="{col["L1"]}"/><text x="{x-30:.1f}" y="{yy+20:.1f}" class="t">L1</text>')
    for y, nm in ((4.6, 'A'), (-4.6, 'B')):
        x, yy = P(y, 0); o.append(f'<circle cx="{x:.1f}" cy="{yy:.1f}" r="4" fill="{col["DATA"]}"/><text x="{x-8:.1f}" y="{yy+16:.1f}" class="m">data {nm}</text>')
    for u in PW['district']:
        for sgn in (1, -1):
            x, yy = P(*pol(u['azimuth_deg']+60+sgn*CFG['radiators']['loop']['offset_deg'], 5.8)); o.append(f'<circle cx="{x:.1f}" cy="{yy:.1f}" r="{RAD["nak"]["transport"]["D_m"]/2*s:.1f}" fill="{col["NaK"]}"/>')
    o.append('<text x="14" y="520" class="m">orange: L2 NaK loops (Stage E) in the casing-hull annulus; red: L1; blue: main buses</text>')
    o.append(f'<text x="14" y="538" class="m">closest pairs: ' + '; '.join(f'{r["a"]}/{r["b"]} {r["clear_m"]:.2f} m' for r in SEP[:3]) + '</text>')
    o.append('</svg>'); path.write_text('\n'.join(o))


def main():
    BU = buses(); ST = storage(); FA = faults(ST); SEP = separation(); G = geometry(BU)
    findings = [f'Conductors and ducts: {BU["total_t"]:.1f} t for three {E["voltage_V"]/1e3:.0f} kV sectors ({BU["rows"][0]["A_mm2"]:.0f} mm2 Al per pole), feeders, nine '
                f'normally-open ties, the 10 kV L1 bus, the 6 kV defense bus and the refuge bus; the Phase VI distribution line is {BU["ledger_t"]:.1f} t '
                f'({"covers it" if BU["total_t"] <= BU["ledger_t"] else "does not cover it"}). Bus loss {BU["loss_W"]/1e3:.0f} kW at full load (a WARM load).',
                f'Single faults: {sum(1 for f in FA if f["ok"])} of {len(FA)} ride through with storage; the district-loss case is the design case for the refuge.',
                'Storage: ' + '; '.join(f'{r["store"]} {"OK" if r["ok"] else "SHORT"} ({r["note"]})' for r in ST['rows']) + '.',
                'Separation: ' + '; '.join(f'{r["a"]}/{r["b"]} {r["clear_m"]:.2f} m -> {r["action"]}' for r in SEP[:4]) + '.',
                'L3 stays a type-OPEN refuge source (radioisotope-Stirling or fuel cell, Phase IV); it has its own bus and no tie to the main buses (owner rule).']
    out = dict(status='STUDY / PROTOTYPE / NONCANON (Track F1, M2)', buses=BU, storage=ST, faults=FA, separation=SEP, geometry=G, findings=findings,
               ledger_add=[dict(item='distribution above the Phase VI line (Stage F)', t=max(0.0, BU['total_t']-BU['ledger_t']), cls='NEW', x=E['bus_x'])])
    (R/'i3d_electrical.json').write_text(json.dumps(out, indent=1))
    svg_oneline(BU, ST, FA, R/'i3d_electrical_oneline.svg'); svg_section(SEP, R/'i3d_electrical_section.svg')
    for f in findings: print('-', f)


if __name__ == '__main__':
    main()
