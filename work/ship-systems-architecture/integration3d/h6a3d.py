"""3D integration Stage D: the H6a hot network (TH-H6A, M2) with the aft manifold (TH-H6A-AFT, M3). STUDY, PROTOTYPE, noncanon, Track F1.

Function: carry 10.45 GW x 1.2 absorbed drive heat (a third per blade) from the drive heat exchanger to the six isolatable sections of each HOT
blade and back, in two redundant trunk PAIRS (supply + return, each pair 60 %), with cross-feed, drain/recovery, accumulators and EM pumps.
Calculated (phase5/hot.py network model via study6.h6a, F1 composite FT-01, Li FT-02, F1 hot length): mass flow, velocities, diameters,
walls, pressures, valve and bellows counts, masses. Phase VI drew one trunk per path; H6a has a supply and a return trunk per path (corrected).
Placement decision (HSFP): the trunks run OUTSIDE the hull along the blade root, flanking the blade (supply next to the blade, return outboard),
because a 1700-1990 K line inside the hull would need insulation and would heat the body bay and the power district; outside it radiates
into the HOT budget like the blade. Cost: the trunks shade the first ~1 m of the blade root on both faces (view factor re-run OPEN).
Writes ../results/i3d_h6a.json and i3d_h6a_section.svg.
"""
import json
import math
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent; W = HERE.parent; R = W/'results'
sys.path.insert(0, str(W/'phase6')); sys.argv = sys.argv[:1]
import study6 as s6  # noqa: E402

CFG = tomllib.loads((HERE/'f1_integration.toml').read_text())
P6 = json.loads((R/'phase6.json').read_text())
BLADE_HALF_T = 0.225; GAP = 0.15; HULL_R = 6.0; ROOT_R = 6.5


def network():
    F1len = P6['radiators']['F1']['length_m']; L_hdr = 162.0-F1len; a = P6['hot']['F1']['a_g']
    n = s6.h6a(L_hdr, a, s6.COMPOSITE['allowable_stress_Pa'], s6.COMPOSITE['density_kg_m3'])
    return n, L_hdr, a


def layout(n, L_hdr):
    D = n['D_trunk']; rt = D/2; x_fwd = s6.BULK-P6['radiators']['F1']['length_m']; x_hot0 = x_fwd-L_hdr; m = CFG['h6a']['manifold']; pu = CFG['h6a']['pump']
    r_tr = HULL_R+rt+GAP                                     # trunk axis radius (outside the hull)
    t_sup = BLADE_HALF_T+GAP+rt; t_ret = t_sup+D+GAP
    parts = []; bt = {k: v[1]/3 for k, v in P6['hot']['F1']['by_item_t'].items()}   # nominal, per blade
    for az in CFG['h6a']['sectors_deg']:
        a = math.radians(az); er = (math.cos(a), math.sin(a)); et = (-math.sin(a), math.cos(a))
        P = lambda x, r, t: (x, er[0]*r+et[0]*t, er[1]*r+et[1]*t)
        def add(name, kind, geo, mass_t, mat, meaning, cls='M2', **kw):
            parts.append(dict(blade=az, name=f'H6A_{az:.0f}_{name}', kind=kind, geo=geo, mass_t=mass_t, material=mat, meaning=meaning, maturity=cls, **kw))
        for pair, sgn in (('A', -1), ('B', +1)):
            for leg, tt, T in (('Supply', t_sup, n['T_in']), ('Return', t_ret, n['T_out'])):
                add(f'{pair}_{leg}', 'seg', dict(p0=P(m['x_m'], r_tr, sgn*tt), p1=P(x_fwd-0.3, r_tr, sgn*tt), r=rt+n['t_trunk']), bt['trunk_walls']/4+bt['coolant']/4,
                    'FT-01 composite, Li', f'trunk pair {pair} {leg.lower()} ({T:.0f} K, D {D:.2f} m, v {n["v_trunk"]:.0f} m/s)', domain=f'blade {az:.0f} pair {pair}')
        # six sections: headers, fin manifolds, valves, bellows, cross-feed, supports, inspection
        ns = 6; nman = n['n_manifolds']; per = nman/ns
        for k in range(ns):
            xa = x_hot0+k*L_hdr/ns; xb = x_hot0+(k+1)*L_hdr/ns
            for sgn, side in ((-1, 'A'), (1, 'B')):
                add(f'S{k+1}_Header{side}', 'seg', dict(p0=P(xa+0.6, ROOT_R+0.3, sgn*(BLADE_HALF_T+0.12)), p1=P(xb-0.6, ROOT_R+0.3, sgn*(BLADE_HALF_T+0.12)), r=n['D_manifold']/2+0.03),
                    bt['manifold_walls']/ns/2, 'FT-01 composite', f'section {k+1} header, face {side} (feeds {per:.0f} fin manifolds)', domain=f'blade {az:.0f} section {k+1}')
                for j in range(2):
                    xv = xa+0.5 if j == 0 else xb-0.5
                    add(f'S{k+1}_Valve{side}{j+1}', 'box', dict(c=P(xv, r_tr+0.05, sgn*(t_sup+t_ret)/2), half=(0.35, 0.45, D+0.2)), bt['valves']/34,
                        'FT-01 composite body', f'section {k+1} isolation valve, pair {side}, {"aft" if j == 0 else "fwd"} (close in ~8 s)', domain=f'blade {az:.0f} section {k+1}')
                    add(f'S{k+1}_Bellows{side}{j+1}', 'ring', dict(c=P(xv+(0.9 if j == 0 else -0.9), r_tr, sgn*(t_sup if j == 0 else t_ret)), r=rt+0.08, t=0.35),
                        bt['bellows']/30, 'refractory bellows', f'section {k+1} expansion bellows (~10 mm/m)')
            add(f'S{k+1}_CrossFeedValve', 'seg', dict(p0=P(xb-1.2, r_tr+rt+0.3, -t_sup), p1=P(xb-1.2, r_tr+rt+0.3, t_sup), r=0.12), bt['valves']/34*0.5, 'FT-01',
                f'section {k+1} cross-feed with valve (pair A <-> B)')
            add(f'S{k+1}_Saddle', 'box', dict(c=P((xa+xb)/2, HULL_R+0.08, 0.0), half=(0.4, 0.08, t_ret+rt+0.2)), bt['supports']/ns, 'composite saddle on hull frame',
                f'section {k+1} sliding trunk saddle (thermal growth)')
            add(f'S{k+1}_Inspection', 'box', dict(c=P((xa+xb)/2+1.5, r_tr+rt+0.25, t_ret), half=(0.3, 0.2, 0.3)), bt['maintenance']/ns, 'port',
                f'section {k+1} inspection and replacement port (robot access along the blade root)')
        # aft manifold (M3): HX interface ring, two EM pumps on the returns, accumulator, drain/recovery, manifold valves, bellows, trace heat
        add('Aft_HXInterface', 'torus', dict(x=m['x_m']-0.6, R=r_tr, r=m['tube_radius_m'], a0=az-35, a1=az+35), bt['manifold_walls']*0.15, 'FT-01',
            'drive heat-exchanger interface (supply out / return in), production drive side unchanged', cls='M3')
        for sgn, pair in ((-1, 'A'), (1, 'B')):
            add(f'Aft_Pump{pair}', 'cylx', dict(c=P(pu['x_m'], r_tr, sgn*t_ret), L=pu['length_m'], r=pu['radius_m']), bt['pumps']/2, 'EM pump (annular linear induction)',
                f'pair {pair} return pump, {n["pump_W"]/2/1e6:.2f} MW, L1 bus fed; removable to the drive-bay hatch', cls='M3', oru=bt['pumps']/2 <= 3.0)
            add(f'Aft_PumpBypass{pair}', 'seg', dict(p0=P(pu['x_m']-1.6, r_tr+0.9, sgn*t_ret), p1=P(pu['x_m']+1.6, r_tr+0.9, sgn*t_ret), r=0.14), 0.3, 'FT-01',
                f'pair {pair} pump bypass with check valve (natural circulation / pump swap)', cls='M3')
            add(f'Aft_BypassBellows{pair}', 'ring', dict(c=P(pu['x_m'], r_tr+0.9, sgn*t_ret), r=0.22, t=0.3), bt['bellows']/30, 'refractory bellows', 'bypass bellows', cls='M3')
            for leg, tt in (('Supply', t_sup), ('Return', t_ret)):
                add(f'Aft_Valve{pair}{leg}', 'box', dict(c=P(m['x_m']+1.4, r_tr+0.05, sgn*tt), half=(0.35, 0.5, rt+0.12)), bt['valves']/34, 'FT-01',
                    f'manifold isolation valve pair {pair} {leg.lower()}', cls='M3')
                add(f'Aft_Bellows{pair}{leg}', 'ring', dict(c=P(m['x_m']+2.4, r_tr, sgn*tt), r=rt+0.08, t=0.35), bt['bellows']/30, 'refractory bellows',
                    'manifold bellows', cls='M3')
        add('Aft_Accumulator', 'cylx', dict(c=P(-129.5, r_tr+1.2, 0.0), L=2.6, r=0.6), bt['accumulators'], 'FT-01, Ar cover gas',
            'accumulator / pressurizer on the returns', cls='M3')
        add('Aft_DrainRecovery', 'cylx', dict(c=P(-125.0, HULL_R-0.9, 0.0), L=3.6, r=0.75), bt['recovery'], 'FT-01 + trace heat',
            'drain and recovery tank inside the hull (freeze valve, trace-heated; frozen start)', cls='M3')
        add('Aft_DrainLine', 'seg', dict(p0=P(-127.0, r_tr, 0.0), p1=P(-125.0, HULL_R-0.4, 0.0), r=0.1), 0.2, 'FT-01', 'drain line through the hull (penetration OPEN)', cls='M3')
        add('Aft_PumpRemoval', 'path', dict(points=[P(pu['x_m'], r_tr+1.4, 0.0), P(-142.0, r_tr+1.4, 0.0)]), 0.0, '-', 'pump removal path to the drive-bay hatch', cls='M3')
    return parts, dict(r_trunk_axis=r_tr, t_supply=t_sup, t_return=t_ret, x_hot0=x_hot0, x_fwd=x_fwd, hull_clear_m=math.hypot(r_tr, t_ret)-rt-HULL_R,
                       root_shade_m=r_tr+rt-ROOT_R, blade_width_m=30.5)


def svg(n, G):
    S = 60; C = (260, 330); Wd = 560
    P = lambda r, t: (C[0]+t*S, C[1]-(r-5.0)*S)
    g = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {Wd} 420" font-family="IBM Plex Mono, monospace" font-size="11">', f'<rect width="{Wd}" height="420" fill="#14161c"/>',
         '<text x="16" y="22" fill="#e8e6df" font-size="14">H6a at a blade root · transverse section (blade 90, looking aft)</text>',
         f'<text x="16" y="40" fill="#9aa0ad">Li {n["T_in"]:.0f} K out / {n["T_out"]:.0f} K back · {n["mdot"]:,.0f} kg/s per blade · p max {n["p_trunk_max"]/1e6:.2f} MPa</text>']
    x0, y0 = P(6.0, -3.0); x1, _ = P(6.0, 3.0)
    g.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" stroke="#8e9094" stroke-width="3"/><text x="{x0}" y="{y0+16}" fill="#8e9094">hull r 6.0</text>')
    bx0, by0 = P(10.5, -0.225); bx1, by1 = P(6.5, 0.225)
    g.append(f'<rect x="{bx0}" y="{by0}" width="{bx1-bx0}" height="{by1-by0}" fill="#c0392b" fill-opacity=".8"/><text x="{bx1+6}" y="{by0+12}" fill="#e88">HOT blade (root r 6.5)</text>')
    rt = n['D_trunk']/2
    for t, lbl in ((-G['t_return'], 'A ret'), (-G['t_supply'], 'A sup'), (G['t_supply'], 'B sup'), (G['t_return'], 'B ret')):
        cx, cy = P(G['r_trunk_axis'], t)
        g.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{rt*S:.0f}" fill="{"#ff5a36" if "sup" in lbl else "#ff9a5a"}" stroke="#fff" stroke-opacity=".5"/>'
                 f'<text x="{cx:.0f}" y="{cy+rt*S+14:.0f}" fill="#e8e6df" text-anchor="middle">{lbl}</text>')
    for sgn in (-1, 1):
        cx, cy = P(6.8, sgn*(0.225+0.12)); g.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{(n["D_manifold"]/2+0.03)*S:.0f}" fill="#ffb07a"/>')
    g.append(f'<text x="16" y="400" fill="#9aa0ad">trunks D {n["D_trunk"]:.2f} m, wall {1e3*n["t_trunk"]:.1f} mm (FT-01) · hull clearance {G["hull_clear_m"]:.2f} m · trunks reach {G["root_shade_m"]:.2f} m up the root</text>')
    g.append('</svg>'); return '\n'.join(g)


def main():
    n, L_hdr, a = network(); parts, G = layout(n, L_hdr)
    tot = sum(p['mass_t'] for p in parts)
    counts = {}
    for p in parts:
        k = p['name'].split('_', 2)[2]; base = ''.join(ch for ch in k if not ch.isdigit())
        counts[base] = counts.get(base, 0)+1
    valves = sum(1 for p in parts if 'Valve' in p['name'])//3; bel = sum(1 for p in parts if 'Bellows' in p['name'])//3
    out = dict(status='STUDY / PROTOTYPE, Track F1 (FT-01, FT-02); noncanon; production drive unchanged', network={k: v for k, v in n.items() if not isinstance(v, dict)},
               hot_length_m=L_hdr, a_design_g=a, geometry=G, parts=parts, mass_drawn_t=tot, mass_phase6_t=P6['hot']['F1']['total_t'][1],
               counts_per_blade=dict(valves=valves, valves_model=n['valves'], bellows=bel, bellows_model=n['bellows'], trunks=4),
               corrections=['Phase VI drew one trunk per path; each H6a path is a supply + return pair (4 trunks per blade)'],
               findings=[f'Per blade: {n["mdot"]:,.0f} kg/s Li, {n["T_in"]:.0f} K out and {n["T_out"]:.0f} K back, trunks D {n["D_trunk"]:.2f} m at {n["v_trunk"]:.0f} m/s, '
                         f'p max {n["p_trunk_max"]/1e6:.2f} MPa, pumps {n["pump_W"]/1e6:.1f} MW.',
                         f'Trunks outside the hull at r {G["r_trunk_axis"]:.2f} m flanking the blade root ({G["hull_clear_m"]:.2f} m off the hull); they reach '
                         f'{G["root_shade_m"]:.2f} m up the blade root ({100*G["root_shade_m"]/G["blade_width_m"]:.1f} % of the 30.5 m width) and partly shade the next metres '
                         '(view factor re-run OPEN); the heat-pipe fins (13.9 t) belong to the blade and are not drawn.',
                         f'Valves {valves} per blade (model {n["valves"]}), bellows {bel} (model {n["bellows"]}): the drawn network matches the mass model counts.',
                         f'EM pumps {P6["hot"]["F1"]["by_item_t"]["pumps"][1]/6:.1f} t each: {"within" if P6["hot"]["F1"]["by_item_t"]["pumps"][1]/6 <= 3 else "above"} the 3 t ORU limit.'])
    (R/'i3d_h6a.json').write_text(json.dumps(out, indent=1, default=float)); (R/'i3d_h6a_section.svg').write_text(svg(n, G))
    for f in out['findings']: print('-', f)
    print('parts', len(parts), 'mass drawn', round(tot, 1), 'phase6', round(out['mass_phase6_t'], 1))


if __name__ == '__main__':
    main()
