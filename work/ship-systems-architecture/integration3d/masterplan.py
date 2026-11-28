"""3D integration Stage A: spatial masterplan of the Track F1 reference (WF-F1-P6.0). STUDY, PROTOTYPE, noncanon.

Reads the production geometry from the pure modules (stations, rings, blades, farm, Brow, body bay), the F1 assemblies from
results/phase6.json, the tank alternatives from results/i3d_tanks.json (run tanks3d.py first) and the registry in f1_integration.toml.
Writes results/i3d_masterplan.json (zones, keep-outs, maturity registry, mass/spatial ledger) and three drawings readable without Blender:
  results/i3d_masterplan_side.svg     side elevation (x vs radius): production zones, F1 zones, keep-outs, the T-A/T-B extensions
  results/i3d_farm_section.svg        transverse section through the farm: vessels by species, lanes, girders, rings, Brow silhouette
  results/i3d_maturity.svg            the maturity registry as a now -> target chart
"""
import json
import math
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent; W = HERE.parent; ROOT = W.parents[1]; R = W/'results'
sys.path.insert(0, str(ROOT/'src/wayfarer'))
import spec  # noqa: E402
import layout  # noqa: E402
import fuel_storage as fs  # noqa: E402
import habitat_ring as hr  # noqa: E402
import thermal_geometry as tg  # noqa: E402
import radiator_zones as rz  # noqa: E402
import forward_shield  # noqa: E402
import hull_geometry  # noqa: E402
import functional_colors as fc  # noqa: E402

CFG = tomllib.loads((HERE/'f1_integration.toml').read_text())


def hexc(key):
    r, g, b, _ = fc.PALETTE[key][1]; return '#%02x%02x%02x' % (int(r*255), int(g*255), int(b*255))


def extent(a):
    """(x0, x1, r0, r1) of a Phase VI layout assembly (make_review6 shape encodings)."""
    c, d, sh = a['c'], a['d'], a['shape']
    if sh == 'rod':
        return min(c[0], d[0]), max(c[0], d[0]), min(math.hypot(c[1], c[2]), math.hypot(d[1], d[2])), max(math.hypot(c[1], c[2]), math.hypot(d[1], d[2]))
    if sh == 'tube':
        return c[0], d[0], c[1], c[2]
    if sh == 'sector':
        return c[0], d[0], c[2], d[1]
    rc = math.hypot(c[1], c[2]); h = max(d[1], d[2])
    return c[0]-d[0], c[0]+d[0], max(0.0, rc-h), rc+h


def production_zones(s):
    O = layout.origins(s); b = tg.blade_at(s, O['RADIATOR_AFT']); rings = hr.centers(s); sw = hr.sweep_half(s); x0, x1 = fs.span(s)
    sec = {z['id']: z for z in rz.sections(s)}; bm = fs.body_modules(s); ts = fs.tanks(s)
    Z = [dict(id='P-DRIVE', name='Drive and thrust ring', x0=O['AFT'], x1=O['RADIATOR_AFT'], r0=0.0, r1=12.0, colour='MAIN_PROPULSION', maturity='M2', source='production'),
         dict(id='P-HOT', name='HOT blades (3 x 120 deg)', x0=O['RADIATOR_AFT'], x1=O['RADIATOR_FRONT'], r0=b['inner_radius_min_m'], r1=b['outer_radius_m'],
              colour='HOT_RADIATOR', maturity='M2', source='production'),
         dict(id='P-WARM', name='WARM section 440 K', x0=sec['WARM']['x0'], x1=sec['WARM']['x1'], r0=b['inner_radius_min_m'], r1=b['outer_radius_m'],
              colour='WARM_RADIATOR', maturity='M2', source='production'),
         dict(id='P-LOW', name='LOW section 300 K', x0=sec['LOW']['x0'], x1=sec['LOW']['x1'], r0=b['inner_radius_min_m'], r1=b['outer_radius_m'],
              colour='LOW_RADIATOR', maturity='M2', source='production'),
         dict(id='P-BODY', name='Body bay: dry store, CMGs, batteries', x0=bm[0]['x0'], x1=bm[-1]['x1'], r0=0.0, r1=hull_geometry.radius_at(s, 0.0),
              colour='SERVICE', maturity='M2', source='production'),
         dict(id='P-RINGA', name='Ring A (rotating)', x0=rings[0]-sw, x1=rings[0]+sw, r0=0.0, r1=30.0, colour='HABITAT', maturity='M2', source='production'),
         dict(id='P-RINGB', name='Ring B (rotating)', x0=rings[1]-sw, x1=rings[1]+sw, r0=0.0, r1=30.0, colour='HABITAT', maturity='M2', source='production'),
         dict(id='P-FARM', name='Propellant farm (13 vessels)', x0=x0, x1=x1, r0=min(t['R']-t['a_env'] for t in ts), r1=max(t['R']+t['a_env'] for t in ts),
              colour='HELIUM3', maturity='M2', source='production'),
         dict(id='P-BROW', name='Brow shield and EYE', x0=O['FWD']-forward_shield.face_depth(s) if hasattr(forward_shield, 'face_depth') else O['FWD']-3.0,
              x1=O['FWD'], r0=0.0, r1=forward_shield.shield_radius(s), colour='SHIELD', maturity='M2', source='production')]
    return Z, O


def f1_zones(P, T):
    LAY = P['layout']; out = []
    for z in CFG['zone']:
        kind, key = z['ref'].split(':')
        if kind == 'layout':
            ex = [extent(a) for a in LAY if a['family'] == key and a['shape'] not in ('tube', 'rod')] or [extent(a) for a in LAY if a['family'] == key]
            out.append(dict(z, x0=min(e[0] for e in ex), x1=max(e[1] for e in ex), r0=min(e[2] for e in ex), r1=max(e[3] for e in ex), source='F1',
                            assemblies=sum(1 for a in LAY if a['family'] == key)))
        else:
            a = next(t for t in T['alternatives'] if t['id'] == key)
            out.append(dict(z, x0=T['farm']['x1'], x1=T['farm']['x1']+a['added_length_m'], r0=6.5, r1=34.5, source='F1', added_length_m=a['added_length_m']))
    return out


def keepouts(s, O, T):
    rings = hr.centers(s); sw = hr.sweep_half(s); svc = s['habitat']['ring_service_clearance']['min_m']
    return [dict(id='K-RING', what='ring sweep + service clearance', x0=rings[0]-sw-svc, x1=rings[1]+sw+svc, r1=30.0+svc),
            dict(id='K-BROW', what='Brow silhouette (shadow rule: rings and vulnerable radiators inside; 15 m ring / 8 m radiator margin)', r1=45.0),
            dict(id='K-L2CONE', what='L2 reactor shadow cone 12.5 deg half-angle forward of each shield (no crewed or cryogenic volume in the direct path)',
                 half_angle_deg=12.5),
            dict(id='K-LANES', what='EVA airlock lane 50 deg, docking corridors 195 and 315 deg, full farm length'),
            dict(id='K-HOTVIEW', what='HOT blade view: no equipment in the blade planes outside the root radius 6.5 m (view factor and 1800 K surface)'),
            dict(id='K-DRIVE', what='drive exhaust and plume keep-out aft of the thrust ring')]


def ledger(P, T):
    M = P['mass']['F1']; c = next(x for x in M['cases'] if x['case'] == 'nom')
    rows = [dict(item=k, t=v['t'][1], cls=v['cls'], x=v.get('x')) for k, v in M['items'].items()]
    ta = next(a for a in T['alternatives'] if a['id'] == 'T-A')
    return dict(config=CFG['config']['reference'], departure_t=c['departure_t'], dry_added_t=c['dry_added_t'], propellant_t=c['propellant_t'], tankage_t=c['tankage_t'],
                end_t=c['end_t'], items=rows, ship_length_m=dict(production=289.5, F1_T_A=ta['ship_length_m']),
                note='nominal case; the 8,190 t figure is the working estimate the owner named; each checkpoint recomputes this ledger')


# ---------------------------------------------------------------------------------------------------------- drawings
def svg_side(Z, F, K, T, O):
    xmin, xmax = O['AFT']-6, O['FWD']+30; rmax = 48.0; Wd, H = 1500, 560; sx = (Wd-120)/(xmax-xmin); sy = (H-170)/rmax
    X = lambda x: 70+(x-xmin)*sx; Y = lambda r: H-80-r*sy
    g = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {Wd} {H}" font-family="IBM Plex Mono, monospace" font-size="11">',
         f'<rect width="{Wd}" height="{H}" fill="#14161c"/>',
         f'<text x="70" y="26" fill="#e8e6df" font-size="15">G.U. WAYFARER 001 · Track F1 masterplan · side elevation (x vs radius), STUDY, noncanon</text>',
         f'<text x="70" y="44" fill="#9aa0ad">Solid: production zones (M2). Hatched: F1 zones (M0/M1). Dashed: tank extension alternatives. Engineering colours, not materials.</text>',
         '<defs><pattern id="h" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" stroke="#fff" stroke-opacity=".35" stroke-width="2"/></pattern></defs>']
    for x in range(-140, int(xmax), 20):
        g.append(f'<line x1="{X(x):.1f}" y1="{Y(0):.1f}" x2="{X(x):.1f}" y2="{Y(0)+5:.1f}" stroke="#9aa0ad"/><text x="{X(x):.1f}" y="{Y(0)+18:.1f}" fill="#9aa0ad" text-anchor="middle">{x}</text>')
    for r in (10, 20, 30, 40):
        g.append(f'<line x1="66" y1="{Y(r):.1f}" x2="70" y2="{Y(r):.1f}" stroke="#9aa0ad"/><text x="62" y="{Y(r)+4:.1f}" fill="#9aa0ad" text-anchor="end">{r}</text>')
    g.append(f'<line x1="70" y1="{Y(0):.1f}" x2="{X(xmax):.1f}" y2="{Y(0):.1f}" stroke="#9aa0ad"/><text x="70" y="62" fill="#9aa0ad">axes: x (m, +X bow) along the bottom, radius (m) on the left</text>')
    g.append(f'<line x1="70" y1="{Y(45):.1f}" x2="{X(O["FWD"]):.1f}" y2="{Y(45):.1f}" stroke="#d9a33a" stroke-dasharray="2 4"/><text x="74" y="{Y(45)-4:.1f}" fill="#d9a33a">Brow silhouette r 45 m</text>')
    for z in Z:
        c = hexc(z['colour']); g.append(f'<rect x="{X(z["x0"]):.1f}" y="{Y(z["r1"]):.1f}" width="{max(1.5, X(z["x1"])-X(z["x0"])):.1f}" height="{Y(z["r0"])-Y(z["r1"]):.1f}" fill="{c}" fill-opacity=".55" stroke="{c}"><title>{z["id"]} {z["name"]} x {z["x0"]:.1f}..{z["x1"]:.1f}</title></rect>')
    lab = {'P-HOT': (0, 0.55), 'P-BODY': (0, 0.5), 'P-FARM': (0, 0.5), 'P-DRIVE': (0, 0.5)}
    for z in Z:
        if z['id'] in lab:
            g.append(f'<text x="{(X(z["x0"])+X(z["x1"]))/2:.1f}" y="{Y(z["r0"]+(z["r1"]-z["r0"])*lab[z["id"]][1]):.1f}" fill="#fff" text-anchor="middle" font-size="10">{z["name"]}</text>')
    g.append(f'<text x="{X(100.3):.1f}" y="{Y(31.5):.1f}" fill="#9fe0a8" text-anchor="middle">rings A, B</text>')
    for zid, txt in (('P-WARM', 'WARM 440 K'), ('P-LOW', 'LOW 300 K')):
        z = next(q for q in Z if q['id'] == zid); xc = (X(z['x0'])+X(z['x1']))/2; yc = Y(22)
        g.append(f'<text x="{xc:.1f}" y="{yc:.1f}" fill="#fff" text-anchor="middle" font-size="10" transform="rotate(-90 {xc:.1f} {yc:.1f})">{txt}</text>')
    g.append(f'<text x="{X(O["FWD"])+3:.1f}" y="{Y(46.5):.1f}" fill="#d9a33a">Brow</text>')
    for z in F:
        c = hexc(z['colour'])
        dash = ' stroke-dasharray="6 4"' if z['id'] == 'Z-FARM-X' else ''
        g.append(f'<rect x="{X(z["x0"]):.1f}" y="{Y(z["r1"]):.1f}" width="{max(1.5, X(z["x1"])-X(z["x0"])):.1f}" height="{max(2, Y(z["r0"])-Y(z["r1"])):.1f}" fill="url(#h)" stroke="{c}" stroke-width="1.6"{dash}><title>{z["id"]} {z["name"]} ({z["maturity"]})</title></rect>')
    for a in T['alternatives']:
        if not a.get('added_length_m'): continue
        x1 = T['farm']['x1']+a['added_length_m']; yy = {'T-A': 36.5, 'T-B': 38.5, 'T-C': 40.5}[a['id']]
        g.append(f'<line x1="{X(T["farm"]["x1"]):.1f}" y1="{Y(yy):.1f}" x2="{X(x1):.1f}" y2="{Y(yy):.1f}" stroke="#c8a8ff" stroke-width="2"/>'
                 f'<text x="{X(x1)+4:.1f}" y="{Y(yy)+4:.1f}" fill="#c8a8ff">{a["id"]} +{a["added_length_m"]:.1f} m</text>')
    # legend of F1 zones
    for i, z in enumerate(F):
        xx = 70+(i % 3)*420; y0 = H-30+(i//3)*18
        g.append(f'<rect x="{xx}" y="{y0-9}" width="12" height="10" fill="url(#h)" stroke="{hexc(z["colour"])}"/><text x="{xx+16}" y="{y0}" fill="#e8e6df">{z["name"]} ({z["maturity"]})</text>')
    g.append('</svg>'); return '\n'.join(g)


def svg_farm(s, T):
    ts = fs.tanks(s); f = fs.farm_cfg(s); S = 7.0; C = 360; Wd = 720
    P = lambda y, z: (C+y*S, C-z*S)
    col = {'helium-3': hexc('HELIUM3'), 'hydrogen': hexc('HYDROGEN'), 'deuterium': hexc('DEUTERIUM')}
    g = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {Wd} {Wd+40}" font-family="IBM Plex Mono, monospace" font-size="11">',
         f'<rect width="{Wd}" height="{Wd+40}" fill="#14161c"/>',
         '<text x="16" y="22" fill="#e8e6df" font-size="14">Farm section (looking aft) · 13 vessels at their packing limits</text>']
    for r, lbl, c in ((45, 'Brow silhouette r 45', '#d9a33a'), (30, 'ring sweep r 30 (aft)', '#9fe0a8'), (37, 'blade / girder r 37', '#e06a5a')):
        g.append(f'<circle cx="{C}" cy="{C}" r="{r*S}" fill="none" stroke="{c}" stroke-dasharray="3 4"/><text x="{C+4}" y="{C-r*S-4}" fill="{c}">{lbl}</text>')
    for deg in f['girder']['azimuth_deg']:
        c_, s_ = fs.unit(deg); a = P(f['girder']['r0_m']*c_, f['girder']['r0_m']*s_); b = P(f['girder']['r1_m']*c_, f['girder']['r1_m']*s_)
        g.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="#e06a5a" stroke-width="6"/>')
    W2 = fs.lane_halfwidth(s); lanes = {'airlock 50': 50.0}
    for q in hull_geometry.dock_corridors(s): lanes[q['name']] = math.degrees(q['theta']) % 360
    for name, deg in lanes.items():
        c_, s_ = fs.unit(deg); e = P(40*c_, 40*s_)
        g.append(f'<line x1="{C}" y1="{C}" x2="{e[0]:.1f}" y2="{e[1]:.1f}" stroke="#f3e8c2" stroke-opacity=".35" stroke-width="{2*W2*S:.1f}"/>'
                 f'<text x="{e[0]:.1f}" y="{e[1]:.1f}" fill="#f3e8c2" font-size="10">{name}</text>')
    for t in ts:
        p = P(t['y'], t['z'])
        g.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="{t["a_env"]*S:.1f}" fill="{col[t["species"]]}" fill-opacity=".7" stroke="#fff" stroke-opacity=".6"/>'
                 f'<text x="{p[0]:.1f}" y="{p[1]+4:.1f}" fill="#fff" text-anchor="middle">{t["id"]}</text>')
    g.append(f'<circle cx="{C}" cy="{C}" r="{6.5*S}" fill="#3a3d46" stroke="#888"/><text x="{C}" y="{C+4}" fill="#ccc" text-anchor="middle">collar</text>')
    y = Wd+10
    for i, (k, v) in enumerate(col.items()):
        g.append(f'<rect x="{16+i*170}" y="{y}" width="12" height="12" fill="{v}"/><text x="{32+i*170}" y="{y+11}" fill="#e8e6df">{k}</text>')
    g.append(f'<text x="16" y="{y+30}" fill="#9aa0ad">gap {T["packing"]["clearances_m"]["vessel_to_vessel"]:.2f} m (rule 1.0) · lanes 0.00 m · girder panels {T["packing"]["clearances_m"]["girder_panels"]:.2f} m (rule 0.5)</text>')
    g.append('</svg>'); return '\n'.join(g)


def svg_maturity(sys_):
    lv = ['M0', 'M1', 'M2', 'M3', 'M4']; Wd = 760; rh = 22; H = 70+rh*len(sys_)
    X = lambda m: 330+lv.index(m)*95
    g = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {Wd} {H}" font-family="IBM Plex Mono, monospace" font-size="11">', f'<rect width="{Wd}" height="{H}" fill="#14161c"/>',
         '<text x="16" y="22" fill="#e8e6df" font-size="14">Maturity registry · now (open dot) to target (filled)</text>']
    for m in lv:
        g.append(f'<text x="{X(m)}" y="46" fill="#9aa0ad" text-anchor="middle">{m}</text><line x1="{X(m)}" y1="52" x2="{X(m)}" y2="{H-8}" stroke="#2c303a"/>')
    for i, q in enumerate(sys_):
        y = 66+i*rh; c = hexc(q['colour'])
        g.append(f'<text x="16" y="{y+4}" fill="#e8e6df">{q["id"]} · {q["name"][:34]}</text>'
                 f'<line x1="{X(q["now"])}" y1="{y}" x2="{X(q["target"])}" y2="{y}" stroke="{c}" stroke-width="3"/>'
                 f'<circle cx="{X(q["now"])}" cy="{y}" r="5" fill="#14161c" stroke="{c}" stroke-width="2"/><circle cx="{X(q["target"])}" cy="{y}" r="5" fill="{c}"/>')
    g.append('</svg>'); return '\n'.join(g)


def main():
    s = spec.load()[0]; P = json.loads((R/'phase6.json').read_text()); T = json.loads((R/'i3d_tanks.json').read_text())
    Z, O = production_zones(s); F = f1_zones(P, T); K = keepouts(s, O, T); L = ledger(P, T)
    sys_ = CFG['system']
    cnt = {m: sum(1 for q in sys_ if q['target'] == m) for m in ('M1', 'M2', 'M3')}
    out = dict(status='STUDY / PROTOTYPE, Track F1 (WF-F1-P6.0); noncanon; production geometry unchanged', config=CFG['config'], maturity_scale=CFG['maturity'],
               production_zones=Z, f1_zones=F, keepouts=K, registry=sys_, targets=cnt, ledger=L,
               findings=[f'The F1 additions sit in three bands: the aft power district and H6a network inside the HOT blade roots (x {F[0]["x0"]:.0f}..{F[0]["x1"]:.0f} incl. buses), '
                         'the hub between and around the rings (ECLSS hub, LOG, workshop), and the farm extension ahead of the farm.',
                         f'Propellant extension (T-A) is {T["alternatives"][0]["added_length_m"]:.1f} m with exact vessel volumes; Phase VI quoted 20.1 m from a linear fill '
                         'estimate that also stretched the heads (superseded).',
                         'Every F1 radial band stays inside the Brow silhouette (r 45 m); the farm and the rings keep their production margins.',
                         'The L1 bus runs through the district envelope (bounding-box screen in the Phase VI review); Stage C gives it a dedicated routing slot.'])
    (R/'i3d_masterplan.json').write_text(json.dumps(out, indent=1, default=float))
    (R/'i3d_masterplan_side.svg').write_text(svg_side(Z, F, K, T, O))
    (R/'i3d_farm_section.svg').write_text(svg_farm(s, T))
    (R/'i3d_maturity.svg').write_text(svg_maturity(sys_))
    print('zones', len(Z), len(F), 'targets', cnt, 'departure', round(L['departure_t']), 'T-A', round(T['alternatives'][0]['added_length_m'], 1))


if __name__ == '__main__':
    main()
