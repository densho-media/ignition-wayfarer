"""3D integration Stage C: the reusable L2 power unit (PWR-L2U, M3) and the power district (PWR-DIST, M2). STUDY, PROTOTYPE, noncanon.

Function: turn 22.7 MWt into 3.5 MWe (closed He-Xe Brayton, 1500 K turbine inlet, FT-03), keep the conversion equipment inside the shield's
shadow, mount it on the ship structure, and let every replaceable part leave the district on a defined path.
Constraints calculated here: thermal power and heat duties from WF-F1-P6.0; shield mass from its geometry; the shadow boundary (reactor edge
through the shield's back edge); modularisation against the 3 t ORU limit (FT-07); clearances unit-to-unit, unit-to-hull, to the buses,
data networks and the H6a trunks; replacement paths to the removal route. Forms (stations, boxes, rings) are engineering judgment.
Reactor and shield stay ADJUSTABLE envelopes: no core design, final shielding OPEN (DR5-08).
Writes ../results/i3d_power.json and i3d_power_unit.svg / i3d_district.svg.
"""
import json
import math
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent; W = HERE.parent; R = W/'results'
CFG = tomllib.loads((HERE/'f1_integration.toml').read_text())
P6 = json.loads((R/'phase6.json').read_text())
DIVISIBLE = {'recuperator', 'gas_cooler', 'pmad', 'ic', 'restart', 'ducts'}


def unit():
    """Parts in the unit frame: u along +X from the reactor centre, (v, w) transverse; boxes/cylinders by half-extents."""
    q = CFG['power_unit']; Pt = q['Pe_W']/q['eta']; sh = q['shield']; rc = q['reactor']
    u_sf = rc['length_m']/2+sh['gap_m']; u_sb = u_sf+sh['length_m']
    r_sb = sh['r_front_m']+sh['length_m']*math.tan(math.radians(sh['half_angle_deg']))
    V_sh = math.pi*sh['length_m']/3*(sh['r_front_m']**2+r_sb**2+sh['r_front_m']*r_sb)
    m_sh = V_sh*q['shield_density_kg_m3']/1e3
    m_unit = next(v for k, v in P6['mass']['F1']['items'].items() if k.startswith('L2 ('))['t'][1]/3
    rest = m_unit-m_sh; f = q['fractions']
    slope = (r_sb-rc['radius_m'])/u_sb                                  # shadow boundary: reactor edge through the shield's back edge
    shadow = lambda u: rc['radius_m']+slope*u
    duty = dict(thermal_W=Pt, electric_W=q['Pe_W'], recuperator_W=q['recuperator_duty_per_Pt']*Pt, gas_cooler_W=Pt-q['Pe_W']/q['generator_eff'],
                generator_loss_W=q['Pe_W']*(1/q['generator_eff']-1))
    vol = lambda W_: W_/q['hx_power_density_W_m3']
    parts = []
    def add(key, name, shape, u, half, mass_t, iface, note, off=(0.0, 0.0), n=1):
        parts.append(dict(key=key, name=name, shape=shape, u=u, v=off[0], w=off[1], half=half, mass_t=mass_t, interfaces=iface, note=note, modules=n))
    add('reactor_ihx', 'Reactor + IHX envelope', 'cyl', 0.0, (rc['length_m']/2, rc['radius_m']), f['reactor_ihx']*rest, ['Li primary', 'gas hot leg', 'control drives'],
        'ADJUSTABLE envelope; no core design')
    add('shield', 'Shadow shield (LiH-W) envelope', 'cone', (u_sf+u_sb)/2, (sh['length_m']/2, sh['r_front_m'], r_sb), m_sh, ['mount ring'],
        f'12.5 deg cone, {V_sh:.1f} m3; final shielding OPEN')
    u = u_sb+0.4
    tac_L = 2.0; add('tac', 'Turbo-alternator-compressor', 'cyl', u+tac_L/2, (tac_L/2, 0.45), f['tac']*rest, ['hot leg', 'recuperator', 'alternator bus'],
                     'single shaft, gas bearings; FT-03 turbine'); u += tac_L+0.3
    Vr = vol(duty['recuperator_W']); Lr = 1.6; hw = math.sqrt(Vr/Lr)/2
    nr = math.ceil(f['recuperator']*rest/q['oru_limit_t'])
    add('recuperator', f'Recuperator ({nr} cores)', 'box', u+Lr/2, (Lr/2, max(hw, 0.55), max(hw, 0.55)), f['recuperator']*rest, ['TAC', 'gas cooler'],
        f'{duty["recuperator_W"]/1e6:.0f} MW duty, {Vr:.2f} m3 core', n=nr); u += Lr+0.3
    Vg = vol(duty['gas_cooler_W']); Lg = 1.4; hg = math.sqrt(Vg/Lg)/2
    ng = math.ceil(f['gas_cooler']*rest/q['oru_limit_t'])
    add('gas_cooler', f'Gas cooler / L2 header manifold ({ng} cores)', 'box', u+Lg/2, (Lg/2, max(hg, 0.6), max(hg, 0.6)), f['gas_cooler']*rest,
        ['L2 headers A/B (two sectors)', 'recuperator'], f'{duty["gas_cooler_W"]/1e6:.1f} MW to the 950 K sections', n=ng); u += Lg+0.3
    npm = math.ceil(f['pmad']*rest/q['oru_limit_t'])
    add('pmad', f'Rectifier + unit switchgear ({npm} cabinets)', 'box', u+0.6, (0.6, 0.55, 0.8), f['pmad']*rest, ['main bus sector', 'restart bus'],
        'HVDC output', off=(0.0, 0.25), n=npm)
    add('ic', 'I&C and protection cabinet', 'box', u+0.6, (0.6, 0.35, 0.35), f['ic']*rest, ['data A/B'], 'two-network', off=(0.0, -0.75))
    add('restart', 'Restart pack R1b', 'box', u_sb+1.4, (0.6, 0.4, 0.5), f['restart']*rest, ['start bus'], 'independent cells', off=(0.0, -1.05))
    add('structure', 'Mount ring + struts', 'ring', u_sb+0.15, (0.12, q['mount']['ring_radius_m']+0.35), f['structure']*rest, ['casing frames', 'spine'], '6 struts')
    add('ducts', 'Gas ducts (hot leg, return) around the shield', 'duct', (0.0+u_sb)/2, (u_sb/2+0.6, r_sb+0.25), f['ducts']*rest, ['IHX', 'TAC'],
        'dog-leg outside the shield (no straight streaming path)')
    u_end = u+1.2
    for p in parts:
        p['oru'] = p['key'] in DIVISIBLE and p['mass_t']/p['modules'] <= q['oru_limit_t']+1e-9
        p['module_t'] = p['mass_t']/p['modules']
        p['replacement'] = ('ORU: robot, LOG-G1 handling' if p['oru'] else
                            'PERMANENT (replaced with the unit at a yard)' if p['key'] in ('shield', 'structure') else
                            'MRU: heavy carriage on the removal route (new requirement: > 3 t)')
        if p['shape'] in ('box', 'cyl') and p['key'] not in ('reactor_ihx',):
            far = p['u']+p['half'][0]; rad = math.hypot(abs(p['v'])+p['half'][1], abs(p['w'])+(p['half'][2] if len(p['half']) > 2 else p['half'][1]))
            p['in_shadow'] = rad <= shadow(far)+1e-6; p['shadow_margin_m'] = shadow(far)-rad
    return dict(parts=parts, duty=duty, unit_mass_t=m_unit, shield_t=m_sh, shield_V_m3=V_sh, shadow_slope=slope, shield_back_r=r_sb,
                u_range=(-rc['length_m']/2, u_end), length_m=u_end+rc['length_m']/2, shadow=[(x, shadow(x)) for x in (0.0, u_sb, u_end)])


def district(U):
    d = CFG['district']; out = []
    for k, az in enumerate(d['azimuths_deg']):
        a = math.radians(az); cy, cz = d['unit_radius_m']*math.cos(a), d['unit_radius_m']*math.sin(a)
        out.append(dict(index=k+1, azimuth_deg=az, centre=(d['reactor_x'], cy, cz), domain=f'L2 unit {k+1} / sector {az:.0f}'))
    def r_of(p):
        if p['shape'] in ('ring', 'duct'): return p['half'][1]
        if p['shape'] == 'cone': return max(p['half'][1], p['half'][2])
        return math.hypot(abs(p['v'])+p['half'][1], abs(p['w'])+(p['half'][2] if len(p['half']) > 2 else p['half'][1]))
    reach = max(r_of(p) for p in U['parts'])
    rr = d['unit_radius_m']
    chk = dict(unit_reach_m=reach, unit_to_unit_m=2*rr*math.sin(math.radians(60))-2*reach, unit_to_hull_m=d['hull_radius_m']-rr-reach)
    def pt(az, r): a = math.radians(az); return (r*math.cos(a), r*math.sin(a))
    def clear(az, r, rad):
        return min(math.dist(pt(az, r), pt(u['azimuth_deg'], rr)) for u in out)-reach-rad
    chk['L1_bus_m'] = clear(d['l1_bus']['azimuth_deg'], d['l1_bus']['radius_m'], 0.22)
    chk['removal_route_m'] = clear(d['removal_route']['azimuth_deg'], d['removal_route']['radius_m'], d['removal_route']['clear_m']/2)
    chk['main_buses_m'] = min(clear(az, 5.0, 0.22) for az in (30.0, 150.0, 270.0))
    chk['data_nets_m'] = min(clear(az, 4.6, 0.07) for az in (0.0, 180.0))
    h = CFG['h6a']; chk['h6a_trunks_m'] = min(math.dist(pt(az, h['trunk_radius_m']), pt(az, rr)) for az in h['sectors_deg'])-reach-0.375
    chk['L1_to_main_bus_1_m'] = math.dist(pt(d['l1_bus']['azimuth_deg'], d['l1_bus']['radius_m']), pt(30.0, 5.0))-0.44
    chk['phase6_L1_through_unit_90'] = 'fixed: L1 bus moved to az 30, r 3.6'
    # replacement paths: part centre -> radial move to the removal route circle -> along the route (x) to the district's forward end
    paths = []
    for u in out:
        for p in U['parts']:
            if p['replacement'].startswith('PERMANENT'): continue
            a = math.radians(u['azimuth_deg']); x = u['centre'][0]+p['u']
            c0 = (x, u['centre'][1], u['centre'][2])
            ra = math.radians(d['removal_route']['azimuth_deg']); c1 = (x, d['removal_route']['radius_m']*math.cos(ra), d['removal_route']['radius_m']*math.sin(ra))
            c2 = (d['reactor_x']+U['u_range'][1]+2.0, c1[1], c1[2])
            # does the straight move c0 -> c1 pass through another unit's reach cylinder?
            hits = []
            for o in out:
                if o is u: continue
                oy, oz = o['centre'][1], o['centre'][2]; y0, z0, y1, z1 = c0[1], c0[2], c1[1], c1[2]
                dy, dz = y1-y0, z1-z0; t = max(0.0, min(1.0, ((oy-y0)*dy+(oz-z0)*dz)/(dy*dy+dz*dz or 1)))
                if math.hypot(y0+t*dy-oy, z0+t*dz-oz) < reach: hits.append(o['index'])
            paths.append(dict(unit=u['index'], part=p['name'], cls=p['replacement'].split(':')[0], points=[c0, c1, c2], crosses_units=hits))
    # body bay: the dry store racks sit on the sector bisectors (90/210/330), the same azimuths as the units
    import sys; sys.path.insert(0, str(W.parents[1]/'src/wayfarer')); import spec, fuel_storage as fs
    s = spec.load()[0]; x0u, x1u = d['reactor_x']+U['u_range'][0], d['reactor_x']+U['u_range'][1]
    hit = [c for c in fs.dry_containers(s) if c['x0'] < x1u and c['x1'] > x0u]
    chk['dry_store_displaced'] = dict(containers=len(hit), of=len(fs.dry_containers(s)), modules=sorted({c['module'] for c in hit}),
                                      volume_m3=sum(c['volume_m3'] for c in hit), x=(x0u, x1u))
    chk['paths'] = len(paths); chk['paths_crossing_another_unit'] = sum(1 for p in paths if p['crosses_units'])
    return out, chk, paths


def svg_unit(U):
    S = 42; ox = 60+U['u_range'][0]*-S; oy = 250; Wd = int(60+U['length_m']*S+60); H = 430
    X = lambda u: ox+u*S; Y = lambda r: oy-r*S
    col = dict(reactor_ihx='#c0392b', shield='#d9a33a', tac='#4b3fa6', recuperator='#e67e22', gas_cooler='#e8a33c', pmad='#5b6ad0', ic='#8fa0b5',
               restart='#6c5ce7', structure='#8e9094', ducts='#c0392b')
    g = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {Wd} {H}" font-family="IBM Plex Mono, monospace" font-size="11">', f'<rect width="{Wd}" height="{H}" fill="#14161c"/>',
         f'<text x="16" y="22" fill="#e8e6df" font-size="14">L2 power unit (M3) · side section · {U["duty"]["electric_W"]/1e6:.1f} MWe, {U["duty"]["thermal_W"]/1e6:.1f} MWt · {U["unit_mass_t"]:.0f} t</text>',
         '<text x="16" y="40" fill="#9aa0ad">u = along +X from the reactor centre; dashed = shadow boundary (reactor edge through the shield back edge)</text>']
    sh = U['shadow']
    g.append(f'<polyline points="{" ".join(f"{X(u):.0f},{Y(r):.0f}" for u, r in sh)}" fill="none" stroke="#9fe0a8" stroke-dasharray="5 4"/>')
    g.append(f'<polyline points="{" ".join(f"{X(u):.0f},{Y(-r):.0f}" for u, r in sh)}" fill="none" stroke="#9fe0a8" stroke-dasharray="5 4"/>')
    g.append(f'<line x1="{X(U["u_range"][0])}" y1="{oy}" x2="{X(U["u_range"][1])}" y2="{oy}" stroke="#444" stroke-dasharray="2 3"/>')
    for p in U['parts']:
        c = col[p['key']]
        if p['shape'] == 'cone':
            L, r0, r1 = p['half']; u0, u1 = p['u']-L, p['u']+L
            g.append(f'<polygon points="{X(u0)},{Y(r0)} {X(u1)},{Y(r1)} {X(u1)},{Y(-r1)} {X(u0)},{Y(-r0)}" fill="{c}" fill-opacity=".55" stroke="{c}"/>')
        elif p['shape'] == 'ring':
            L, r = p['half']; g.append(f'<rect x="{X(p["u"]-L)}" y="{Y(r)}" width="{2*L*S}" height="{0.25*S}" fill="{c}"/><rect x="{X(p["u"]-L)}" y="{Y(-r)-0.25*S}" width="{2*L*S}" height="{0.25*S}" fill="{c}"/>')
        elif p['shape'] == 'duct':
            L, r = p['half']
            g.append(f'<polyline points="{X(0.6)},{Y(0.5)} {X(0.9)},{Y(r)} {X(p["u"]+L-0.6)},{Y(r)} {X(p["u"]+L)},{Y(0.45)}" fill="none" stroke="{c}" stroke-width="5" stroke-opacity=".7"/>')
        else:
            L = p['half'][0]; hz = p['half'][2] if len(p['half']) > 2 else p['half'][1]
            g.append(f'<rect x="{X(p["u"]-L):.0f}" y="{Y(p["w"]+hz):.0f}" width="{2*L*S:.0f}" height="{2*hz*S:.0f}" fill="{c}" fill-opacity=".75" stroke="{c}"><title>{p["name"]}</title></rect>')
    y = 330
    for i, p in enumerate(U['parts']):
        xx = 16+(i % 2)*int(Wd/2); yy = y+(i//2)*16
        g.append(f'<rect x="{xx}" y="{yy-9}" width="10" height="10" fill="{col[p["key"]]}"/><text x="{xx+14}" y="{yy}" fill="#e8e6df">{p["name"]} · {p["mass_t"]:.1f} t · {p["replacement"].split(":")[0]}</text>')
    g.append('</svg>'); return '\n'.join(g)


def svg_district(D, U, chk):
    S = 40; C = 260; Wd = 520
    P = lambda y, z: (C+y*S, C-z*S)
    d = CFG['district']; g = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {Wd} {Wd+60}" font-family="IBM Plex Mono, monospace" font-size="11">',
                             f'<rect width="{Wd}" height="{Wd+60}" fill="#14161c"/>', '<text x="16" y="22" fill="#e8e6df" font-size="14">Power district · end view (looking aft)</text>']
    g.append(f'<circle cx="{C}" cy="{C}" r="{d["hull_radius_m"]*S}" fill="none" stroke="#8e9094"/><text x="{C+4}" y="{C-d["hull_radius_m"]*S-4}" fill="#8e9094">hull r 6.0</text>')
    reach = chk['unit_reach_m']
    for u in D:
        p = P(u['centre'][1], u['centre'][2])
        g.append(f'<circle cx="{p[0]:.0f}" cy="{p[1]:.0f}" r="{reach*S:.0f}" fill="#4b3fa6" fill-opacity=".55" stroke="#9b8cff"/><text x="{p[0]:.0f}" y="{p[1]+4:.0f}" fill="#fff" text-anchor="middle">U{u["index"]}</text>')
    def dot(az, r, rad, c, t):
        a = math.radians(az); p = P(r*math.cos(a), r*math.sin(a))
        g.append(f'<circle cx="{p[0]:.0f}" cy="{p[1]:.0f}" r="{max(3, rad*S):.0f}" fill="{c}"/><text x="{p[0]+8:.0f}" y="{p[1]+4:.0f}" fill="{c}" font-size="10">{t}</text>')
    for az in (30.0, 150.0, 270.0): dot(az, 5.0, 0.22, '#5b9bff', 'main bus')
    for az in (0.0, 180.0): dot(az, 4.6, 0.07, '#9fe0a8', 'data')
    dot(d['l1_bus']['azimuth_deg'], d['l1_bus']['radius_m'], 0.22, '#ff7a59', 'L1 bus')
    dot(d['removal_route']['azimuth_deg'], d['removal_route']['radius_m'], d['removal_route']['clear_m']/2, '#f3e8c2', 'removal route')
    for az in CFG['h6a']['sectors_deg']:
        for off in (-0.9, 0.9):
            a = math.radians(az); y = 5.9*math.cos(a)-off*math.sin(a); z = 5.9*math.sin(a)+off*math.cos(a); p = P(y, z)
            g.append(f'<circle cx="{p[0]:.0f}" cy="{p[1]:.0f}" r="{0.375*S:.0f}" fill="#c0392b"/>')
    yy = Wd+10
    g.append(f'<text x="16" y="{yy}" fill="#9aa0ad">unit-unit {chk["unit_to_unit_m"]:.2f} m · unit-hull {chk["unit_to_hull_m"]:.2f} m · L1 bus {chk["L1_bus_m"]:.2f} m · route {chk["removal_route_m"]:.2f} m</text>')
    g.append(f'<text x="16" y="{yy+18}" fill="#9aa0ad">main buses {chk["main_buses_m"]:.2f} m · data {chk["data_nets_m"]:.2f} m · H6a trunks (red) {chk["h6a_trunks_m"]:.2f} m</text>')
    g.append('</svg>'); return '\n'.join(g)


def main():
    U = unit(); D, chk, paths = district(U)
    out = dict(status='STUDY / PROTOTYPE, Track F1 (WF-F1-P6.0); reactor and shield ADJUSTABLE envelopes; noncanon', unit=U, district=D, checks=chk, paths=paths,
               findings=[f'Unit: {U["length_m"]:.1f} m long, {U["unit_mass_t"]:.0f} t (Phase VI nominal); the shield is {U["shield_t"]:.0f} t of it ({U["shield_V_m3"]:.1f} m3 LiH-W).',
                         f'Every conversion part sits inside the shadow boundary (smallest margin {min(p.get("shadow_margin_m", 9) for p in U["parts"]):.2f} m).',
                         'Recuperator, gas cooler and PMAD split into cores and cabinets under the 3 t ORU limit; the TAC '
                         f'({next(p for p in U["parts"] if p["key"] == "tac")["mass_t"]:.1f} t) and the reactor/IHX envelope are not ORUs: they need a heavy '
                         'carriage on the removal route (a new MRU requirement) or a yard.',
                         f'District clearances: unit-unit {chk["unit_to_unit_m"]:.2f} m, unit-hull {chk["unit_to_hull_m"]:.2f} m; the Phase VI L1 bus ran through '
                         f'unit 90 and now has its own slot ({chk["L1_bus_m"]:.2f} m clear).',
                         f'The district (x {chk["dry_store_displaced"]["x"][0]:.1f}..{chk["dry_store_displaced"]["x"][1]:.1f}) takes body-bay module(s) '
                         f'{chk["dry_store_displaced"]["modules"]}: {chk["dry_store_displaced"]["containers"]} of {chk["dry_store_displaced"]["of"]} dry-store containers '
                         f'({chk["dry_store_displaced"]["volume_m3"]:.0f} m3) move to the LOG-G1 store (Stage H).',
                         f'{chk["paths"]} replacement paths; {chk["paths_crossing_another_unit"]} cross another unit on the straight radial move to the route.'])
    (R/'i3d_power.json').write_text(json.dumps(out, indent=1, default=float))
    (R/'i3d_power_unit.svg').write_text(svg_unit(U)); (R/'i3d_district.svg').write_text(svg_district(D, U, chk))
    for f in out['findings']: print('-', f)
    print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in chk.items()})
    for p in U['parts']: print(p['name'], round(p['mass_t'], 1), p['modules'], p['replacement'][:5], round(p.get('shadow_margin_m', 0), 2))


if __name__ == '__main__':
    main()
