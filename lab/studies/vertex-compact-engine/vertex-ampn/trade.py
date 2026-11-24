"""AMPN Phase 7: integrated trade. Reads optimize.json and coilpack.json; writes results/trade.json, results/tables.md, figures/pareto.svg.
Fixed nozzle = the optimum without the carriage (no stow); adaptive = with carriage, locks and actuators. Dust sensitivity: JUSTIFIED envelope."""
import json, math, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'vertex-ron')); sys.path.insert(0, str(HERE))
import ron, dust
k = ron.canon()
opt = json.loads((HERE/'results'/'optimize.json').read_text()); cp = json.loads((HERE/'results'/'coilpack.json').read_text())
rows = []
for key, c in cp.items():
    b = opt[key]
    eng_ad = c['engine_full_t']; eng_fix = eng_ad - c['extra_t']['carriage_locks_actuators_t']
    def ship(e, extra_dust_t=0.0):
        return ron.ship(k, e + extra_dust_t/4, 4*b['piped_W'], max(0.05, b['eta']), cant_deg=b['cant_deg'])
    R, kap, D, S = b['x'][:4]
    dj, _ = dust.dust_mass_t(R, b['plug_r_m'], S, D, case='JUSTIFIED')
    dn = b['add_t']['dust_protection_t']*4
    sf, sa, sj = ship(eng_fix), ship(eng_ad), ship(eng_fix, dj - dn)
    rows.append(dict(key=key, fam=key[0], tape=key.split('_')[1], R=R, kappa=kap, D=D, S=S, mult=b['x'][4], mirror=b['x'][5] if len(b['x']) > 5 else None,
                     eta=b['eta'], cant=b['cant_deg'], engine_fixed_t=eng_fix, engine_adaptive_t=eng_ad, dust_ship_t=dn, dust_justified_ship_t=dj,
                     dep_fixed_t=sf['departure_t'], dep_adaptive_t=sa['departure_t'], dep_fixed_justified_t=sj['departure_t'],
                     dry_t=sf['dry_t'], prop_t=sf['propellant_t'], ve=sf['ve_eff_m_s'], thrust_MN=sf['thrust_N']/1e6, a0_mg=sf['accel_g_departure']*1e3,
                     burn1_d=sf['burn1_days'], ratio_to_canon=sf['departure_t']/4426.07))
(HERE/'results'/'trade.json').write_text(json.dumps(rows, indent=1))
L = ['| Design | Tape | R m | kappa | D m | S m | eta | cant deg | engine fixed t | engine adaptive t | dust ship t (NOM / JUST) | departure fixed t | adaptive t | fixed, JUSTIFIED dust t | x canon |',
     '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
for r in rows:
    L.append(f"| {r['fam']} | {r['tape']} | {r['R']:.0f} | {r['kappa']:.2f} | {r['D']:.0f} | {r['S']:.0f} | {r['eta']:.3f} | {r['cant']:.1f} | {r['engine_fixed_t']:.0f} | "
             f"{r['engine_adaptive_t']:.0f} | {r['dust_ship_t']:.0f} / {r['dust_justified_ship_t']:.0f} | {r['dep_fixed_t']:,.0f} | {r['dep_adaptive_t']:,.0f} | {r['dep_fixed_justified_t']:,.0f} | {r['ratio_to_canon']:.2f} |")
L += ['', '| Design | Tape | dry t | propellant t | ve km/s | thrust MN | a0 mg | burn 1 d |', '| --- | --- | --- | --- | --- | --- | --- | --- |']
for r in rows:
    L.append(f"| {r['fam']} | {r['tape']} | {r['dry_t']:,.0f} | {r['prop_t']:,.0f} | {r['ve']/1e3:,.0f} | {r['thrust_MN']:.1f} | {r['a0_mg']:.0f} | {r['burn1_d']:.1f} |")
(HERE/'results'/'tables.md').write_text('\n'.join(L)+'\n')
print('\n'.join(L))
# Pareto: every optimiser evaluation, engine mass (x) vs departure (y), B and E, plus the full-account optima
pts = []
for key, v in opt.items():
    if key.endswith('_cloud'):
        for c in v:
            if c.get('engine_t') and c['departure_t'] < 3e4:
                pts.append((key[0], c['engine_t'], c['departure_t']))
W, H, m = 760, 460, 60
xs = [p[1] for p in pts]+[r['engine_fixed_t'] for r in rows]; ys = [p[2] for p in pts]+[r['dep_fixed_t'] for r in rows]+[4426]
x0, x1 = 0, max(xs)*1.05; y0, y1 = 0, max(ys)*1.05
X = lambda x: m+(x-x0)/(x1-x0)*(W-2*m); Y = lambda y: H-m-(y-y0)/(y1-y0)*(H-2*m)
col = {'B': '#2a7fd4', 'E': '#d4732a'}
s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif" font-size="12"><rect width="100%" height="100%" fill="#fff"/>']
s.append(f'<line x1="{m}" y1="{H-m}" x2="{W-m}" y2="{H-m}" stroke="#555"/><line x1="{m}" y1="{m}" x2="{m}" y2="{H-m}" stroke="#555"/>')
for t in range(0, int(y1)+1, 5000):
    s.append(f'<line x1="{m}" y1="{Y(t):.1f}" x2="{W-m}" y2="{Y(t):.1f}" stroke="#eee"/><text x="{m-6}" y="{Y(t)+4:.1f}" text-anchor="end" fill="#555">{t:,}</text>')
for t in range(0, int(x1)+1, 250):
    s.append(f'<text x="{X(t):.1f}" y="{H-m+16}" text-anchor="middle" fill="#555">{t}</text>')
for f, x, y in pts:
    s.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="2.5" fill="{col[f]}" fill-opacity="0.35"/>')
for r in rows:
    s.append(f'<circle cx="{X(r["engine_fixed_t"]):.1f}" cy="{Y(r["dep_fixed_t"]):.1f}" r="5" fill="{col[r["fam"]]}" stroke="#111"/>'
             f'<text x="{X(r["engine_fixed_t"])+7:.1f}" y="{Y(r["dep_fixed_t"])-6:.1f}" fill="#222">{r["fam"]} {r["tape"]}</text>')
s.append(f'<line x1="{m}" y1="{Y(4426):.1f}" x2="{W-m}" y2="{Y(4426):.1f}" stroke="#2a9d4b" stroke-dasharray="5,4"/><text x="{W-m}" y="{Y(4426)-6:.1f}" text-anchor="end" fill="#2a9d4b">canon departure 4,426 t</text>')
s.append(f'<text x="{W/2}" y="{H-14}" text-anchor="middle" fill="#222">engine mass, t (per engine, full account, fixed nozzle for the optima)</text>')
s.append(f'<text x="16" y="{H/2}" transform="rotate(-90 16 {H/2})" text-anchor="middle" fill="#222">departure mass, t</text>')
s.append(f'<text x="{m}" y="24" fill="#222" font-size="14">AMPN optimiser evaluations (B blue, E orange) and full-account optima</text></svg>')
(HERE/'figures').mkdir(exist_ok=True); (HERE/'figures'/'pareto.svg').write_text('\n'.join(s))
