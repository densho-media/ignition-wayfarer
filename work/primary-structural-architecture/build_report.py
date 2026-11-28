"""Builds the PSA Phase I review page (results/psa.html) and its SVG figures from the data files and results/psa_phase1.json.
Pure Python standard library. Run after psa_study.py:

    python3 work/primary-structural-architecture/build_report.py
"""
import html
import json
import tomllib
from pathlib import Path

H = Path(__file__).resolve().parent
D = H / 'data'
R = H / 'results'
E = html.escape

X0, X1 = -150.0, 150.0
MAT_COL = {'AL': 'var(--al)', 'TI': 'var(--ti)', 'CF': 'var(--cf)', 'MMC': 'var(--mmc)', 'NI': 'var(--ni)', 'CER': 'var(--cer)', 'ST': 'var(--st)', 'GF': 'var(--gf)', 'CC': 'var(--cc)'}


def tml(n):
    return tomllib.loads((D / f'{n}.toml').read_text())


def sx(x, w=1100, pad=40):
    return pad + (x - X0) / (X1 - X0) * (w - 2 * pad)


def fig_loadpath(zones):
    w, h = 1100, 300
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Load path and mounting zones along the ship">']
    for i, z in enumerate(zones):
        a, b = sx(z['x_m'][0]), sx(z['x_m'][1])
        y = 40 + (i % 2) * 18
        out.append(f'<rect x="{a:.1f}" y="{y}" width="{b - a:.1f}" height="14" rx="2" fill="var(--surf2)" stroke="var(--line)"/>')
        out.append(f'<text x="{(a + b) / 2:.1f}" y="{y + 11}" text-anchor="middle" class="t9">{z["id"]}</text>')
    yc = 170
    out.append(f'<rect x="{sx(-144.75):.1f}" y="{yc - 26}" width="{sx(144.75) - sx(-144.75):.1f}" height="52" rx="6" fill="none" stroke="var(--muted)" stroke-dasharray="3 3"/>')
    blocks = [(-144.75, -113.2, 'Drive', 'var(--drive)'), (-92, -80, 'L2', 'var(--warn)'), (-133.25, 48.9, '', 'none'), (22, 49, 'Workshop', 'var(--occ)'),
              (96.3, 104.3, 'Rings', 'var(--hab)'), (109.25, 137.85, 'Tank farm', 'var(--info)'), (138.2, 144.8, 'Brow', 'var(--fwd)')]
    for a, b, n, c in blocks:
        if c == 'none':
            continue
        out.append(f'<rect x="{sx(a):.1f}" y="{yc - 18}" width="{sx(b) - sx(a):.1f}" height="36" rx="3" fill="{c}" opacity=".55"/>')
        out.append(f'<text x="{(sx(a) + sx(b)) / 2:.1f}" y="{yc + 4}" text-anchor="middle" class="t10 ink">{n}</text>')
    out.append(f'<rect x="{sx(-133.25):.1f}" y="{yc - 40}" width="{sx(48.9) - sx(-133.25):.1f}" height="8" fill="var(--therm)" opacity=".7"/>')
    out.append(f'<text x="{sx(-40):.1f}" y="{yc - 45}" text-anchor="middle" class="t10">radiator blades 1800 K (root band MZ-05)</text>')
    ya = 250
    out.append(f'<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0L10,5L0,10z" fill="var(--action)"/></marker></defs>')
    steps = [(-144.75, 'thrust 21.8 MN'), (-135.25, '12-node ring'), (-127, 'transition'), (60, '3 sectors + spine'), (100, 'Q45 collar'), (118, 'tank deck'), (141, 'Brow keels')]
    for (a, la), (b, _) in zip(steps, steps[1:]):
        out.append(f'<line x1="{sx(a) + 2:.1f}" y1="{ya}" x2="{sx(b) - 4:.1f}" y2="{ya}" stroke="var(--action)" stroke-width="2.5" marker-end="url(#ah)"/>')
    for i, (a, la) in enumerate(steps):
        out.append(f'<text x="{sx(a):.1f}" y="{ya + 18 + (i % 2) * 13}" text-anchor="middle" class="t10">{la}</text>')
    for x in (-144.75, -100, -50, 0, 50, 100, 144.75):
        out.append(f'<text x="{sx(x):.1f}" y="{yc + 44}" text-anchor="middle" class="t9">X {x:g}</text>')
    out.append('</svg>')
    return ''.join(out)


def fig_zoning():
    w, h = 1100, 250
    yc = 110
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Concept HC material zoning, side view">']
    bands = [(-144.75, -127, 'TI', 'Ti-6Al-4V thrust ring, nodes, transition (DED + HIP)'), (-127, 95, 'MMC', 'Al2O3f/Al cassettes (lunar)'),
             (95, 109, 'TI', 'Ti collar nodes'), (109.25, 137.85, 'CF', 'CF/PEEK cassettes + G-10 cryo struts'), (137.85, 144.75, 'TI', 'Ti Brow keel roots')]
    for a, b, m, _ in bands:
        out.append(f'<rect x="{sx(a):.1f}" y="{yc - 30}" width="{sx(b) - sx(a):.1f}" height="14" fill="{MAT_COL[m]}"/>')
        out.append(f'<rect x="{sx(a):.1f}" y="{yc + 16}" width="{sx(b) - sx(a):.1f}" height="14" fill="{MAT_COL[m]}"/>')
    for x in range(-127, 144, 8):
        out.append(f'<line x1="{sx(x):.1f}" y1="{yc - 16}" x2="{sx(x):.1f}" y2="{yc + 16}" stroke="var(--al)" stroke-width="2"/>')
    out.append(f'<rect x="{sx(-140):.1f}" y="{yc - 6}" width="{sx(30) - sx(-140):.1f}" height="4" fill="var(--bad)"/>')
    for x in range(-136, 30, 8):
        out.append(f'<rect x="{sx(x) - 2:.1f}" y="{yc - 12}" width="4" height="6" fill="var(--ni)"/>')
    out.append(f'<rect x="{sx(-133.25):.1f}" y="{yc - 52}" width="{sx(48.9) - sx(-133.25):.1f}" height="10" fill="var(--cc)"/>')
    leg = [('MMC', 'Al₂O₃f/Al longeron cassettes (lunar)'), ('CF', 'CF/PEEK cassettes (imported carbon)'), ('TI', 'Ti-6Al-4V nodes, rings, keels'),
           ('AL', 'Al 5083/6061 frames every 4 m'), ('NI', 'Inconel/YSZ hot-loop stand-offs'), ('CC', 'C/C blade backbone (thermal-owned)')]
    for i, (m, t) in enumerate(leg):
        x = 40 + (i % 3) * 350
        y = 190 + (i // 3) * 22
        out.append(f'<rect x="{x}" y="{y - 10}" width="12" height="12" fill="{MAT_COL[m]}"/><text x="{x + 18}" y="{y}" class="t11">{t}</text>')
    out.append(f'<text x="{sx(-55):.1f}" y="{yc + 2}" class="t9" fill="var(--bad)">H6a hot trunk 1990 K on stand-offs</text>')
    out.append('</svg>')
    return ''.join(out)


def fig_flow():
    w, h = 1100, 230
    nodes = [('Luna surface', 'regolith → electrolysis → Al, Ti, Si, Fe, O₂; rolling, extrusion, Al₂O₃ fibre, Ti wire', 40),
             ('Luna Lift', 'bulk plate, profiles, wire, fibre to orbit (ISM-29)', 250),
             ('Harbor', 'receiving, imports (carbon fibre, V, resin), QA (ISM-30)', 440),
             ('Yard', 'vertebra jig: FSW frames, DED nodes, NDT, proof load as class C modules', 640),
             ('Stack + fit', 'cassettes join vertebrae; ring, collar, Brow; kinematic mounts', 860)]
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Manufacturing flow from Luna to the Yard">',
           '<defs><marker id="af" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0L10,5L0,10z" fill="var(--muted)"/></marker></defs>']
    for i, (n, t, x) in enumerate(nodes):
        out.append(f'<rect x="{x}" y="40" width="185" height="110" rx="6" fill="var(--surf2)" stroke="var(--line)"/>')
        out.append(f'<text x="{x + 10}" y="62" class="t12 ink b">{n}</text>')
        words, line, y = t.split(), '', 82
        for wd in words:
            if len(line) + len(wd) > 30:
                out.append(f'<text x="{x + 10}" y="{y}" class="t10">{E(line)}</text>'); y += 14; line = ''
            line += wd + ' '
        out.append(f'<text x="{x + 10}" y="{y}" class="t10">{E(line)}</text>')
        if i < len(nodes) - 1:
            nx = nodes[i + 1][2]
            out.append(f'<line x1="{x + 187}" y1="95" x2="{nx - 3}" y2="95" stroke="var(--muted)" stroke-width="2" marker-end="url(#af)"/>')
    out.append('<text x="440" y="185" class="t10">Earth / asteroid imports: carbon fibre, V, resins (MX-H 11 %, MX-C 54 % of mass)</text>')
    out.append('<line x1="530" y1="172" x2="530" y2="153" stroke="var(--warn)" stroke-width="2" marker-end="url(#af)"/>')
    out.append('<text x="860" y="185" class="t10">→ ISM-31 proving ground thrust test</text>')
    out.append('</svg>')
    return ''.join(out)


def fig_concept_mass(cm):
    keys = list(cm)
    w, h, pad, bh = 1100, 40 + 34 * len(keys), 160, 12
    mx = 750
    s = lambda v: pad + v / mx * (w - pad - 40)
    out = [f'<svg viewBox="0 0 {w} {h + 30}" role="img" aria-label="Primary structure mass per concept">']
    for v in range(0, mx + 1, 100):
        out.append(f'<line x1="{s(v):.1f}" y1="20" x2="{s(v):.1f}" y2="{h}" stroke="var(--line)"/><text x="{s(v):.1f}" y="{h + 16}" text-anchor="middle" class="t10">{v} t</text>')
    out.append(f'<line x1="{s(150):.1f}" y1="14" x2="{s(150):.1f}" y2="{h}" stroke="var(--action)" stroke-width="2" stroke-dasharray="5 3"/><text x="{s(150) + 4:.1f}" y="14" class="t10" fill="var(--action)">150 t line</text>')
    for i, k in enumerate(keys):
        y = 30 + i * 34
        f, c = cm[k]['P_flight']['total_t'], cm[k]['P_canon_1p5g']['total_t']
        out.append(f'<text x="{pad - 10}" y="{y + 15}" text-anchor="end" class="t12 ink b">{k}</text>')
        out.append(f'<rect x="{pad}" y="{y}" width="{s(f) - pad:.1f}" height="{bh}" fill="var(--info)"/><text x="{s(f) + 4:.1f}" y="{y + 10}" class="t10">{f:.0f}</text>')
        out.append(f'<rect x="{pad}" y="{y + bh + 2}" width="{s(c) - pad:.1f}" height="{bh}" fill="var(--muted)" opacity=".55"/><text x="{s(c) + 4:.1f}" y="{y + 2 * bh}" class="t10">{c:.0f}</text>')
    out.append('</svg>')
    return ''.join(out)


def rows(items, cols):
    return '\n'.join('<tr>' + ''.join(f'<td>{E(str(it.get(c, "")))}</td>' for c in cols) + '</tr>' for it in items)


def main():
    res = json.loads((R / 'psa_phase1.json').read_text())
    iface, prob, road, conc, lc, mo, mats = tml('interface'), tml('problems'), tml('roadmap'), tml('concepts'), tml('load_cases'), tml('mass_ownership'), tml('materials')
    figs = {'loadpath': fig_loadpath(iface['zone']), 'zoning': fig_zoning(), 'flow': fig_flow(), 'mass': fig_concept_mass(res['concept_mass']['by_concept'])}
    for k, v in figs.items():
        (R / f'fig_{k}.svg').write_text(v.replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" ', 1))
    ax = res['axial']
    axial = {'x': ax['grid_m'], 'states': {k: {'N': [round(n, 2) for n in v['N_MN']], 'M': round(v['M_t']), 'a': round(v['a_g'], 3)} for k, v in ax['states'].items()}}
    cdata = {'criteria': conc['criteria'], 'weights': conc['weights'], 'scores': res['concepts']['scores'], 'pareto': res['concepts']['pareto'],
             'mass': {k: {s: round(x['total_t']) for s, x in v.items()} for k, v in res['concept_mass']['by_concept'].items()},
             'names': {c['id']: c['name'] for c in conc['concept']}}
    mtab = []
    for mid, m in res['materials'].items():
        src = next((x for x in mats.get('material', []) if x.get('id') == mid), {})
        mtab.append({'id': mid, 'name': m['name'], 'track': m['track'], 'family': m.get('family', ''), 'lunar': m.get('lunar', ''), 'mag': m.get('magnetic', ''),
                     'Tmax': m.get('T_max', ''), 'sig': round(m['allow_293']['compression_MPa']) if m.get('allow_293') else '',
                     'Erho': round(m['indices']['E_rho'], 1) if m.get('indices') else '', 'col': round(m['indices']['column'], 1) if m.get('indices') else '',
                     'mP': round(res['longeron_screening'].get(mid, {}).get('P_flight_3rail_t', 0)) or 'n/a', 'alpha': src.get('alpha', ''), 'status': src.get('evidence', src.get('status', ''))})
    prob_rows = '\n'.join(f'<tr data-sev="{p["severity"]}"><td class="mono">{p["id"]}</td><td><b>{E(p["title"])}</b><div class="fn">{E(p["finding"])}</div></td><td><span class="sev {p["severity"]}">{p["severity"]}</span></td><td class="mono">{p["kind"]}</td><td>{E(p["closure"])}</td></tr>' for p in prob['problem'])
    lc_rows = '\n'.join(f'<tr><td class="mono">{c["id"]}</td><td><b>{E(c["name"])}</b><div class="fn">{E(c.get("note", ""))}</div></td><td class="mono">{" ".join(c["configs"])}</td><td>{E(c["magnitude"])}</td><td class="fn">{E(c["evidence"])}</td></tr>' for c in lc['case'])
    zone_rows = '\n'.join(f'<tr><td class="mono">{z["id"]}</td><td><b>{E(z["name"])}</b><div class="fn">{E(z["function"])}</div></td><td class="num">{z["x_m"][0]:g} … {z["x_m"][1]:g}</td><td>{E(str(z.get("capacity", "")))}</td><td>{E(str(z.get("temperature_K", "")))}</td></tr>' for z in iface['zone'])
    eq_rows = '\n'.join(f'<tr><td class="mono">{q["id"]}</td><td><b>{E(q["name"])}</b><div class="fn">{E(q.get("owner", ""))} · {E(q.get("approval", ""))}</div></td><td>{E(str(q.get("mass_t", "")))}</td><td>{E(str(q.get("position", "")))}</td><td>{E(str(q.get("attachment", "")))}</td></tr>' for q in iface['equipment'])
    ho_rows = '\n'.join(f'<tr><td class="mono">{q["id"]}</td><td><b>{E(q["topic"])}</b></td><td>{E(q["ask"])}</td><td class="fn">{E(q["impact"])}</td></tr>' for q in iface['handoff'])
    mo_rows = '\n'.join(f'<tr><td class="mono">{i["id"]}</td><td><b>{E(i["name"])}</b></td><td>{E(i["current_owner"])}</td><td>{E(i["proposed_owner"])}</td><td>{E(json.dumps(i["psa_estimate_t"]) if not isinstance(i["psa_estimate_t"], str) else i["psa_estimate_t"])}</td><td class="{"bad" if i["double_count_risk"].startswith("HIGH") else ""}">{E(i["double_count_risk"])}</td></tr>' for i in mo['item'])
    road_html = '\n'.join(f'<div class="phase"><div class="n">Phase {p["id"]}</div><div><p><b>{E(p["name"])}</b></p><p class="fn">Needs: {E("; ".join(p["needs"]))}</p><p>{E("; ".join(p["tasks"]))}</p><p class="fn">Gate: {E(p["gate"])}</p></div></div>' for p in road['phase'])
    st = ax['stations_MN'] if 'stations_MN' in ax else {}
    page = (H / 'report_template.html').read_text()
    rep = {'{{FIG_LOADPATH}}': figs['loadpath'], '{{FIG_ZONING}}': figs['zoning'], '{{FIG_FLOW}}': figs['flow'], '{{FIG_MASS}}': figs['mass'],
           '{{PROBLEMS}}': prob_rows, '{{LOADCASES}}': lc_rows, '{{ZONES}}': zone_rows, '{{EQUIP}}': eq_rows, '{{HANDOFF}}': ho_rows, '{{OWNERSHIP}}': mo_rows, '{{ROADMAP}}': road_html,
           '{{AXIAL_JSON}}': json.dumps(axial, separators=(',', ':')), '{{CONCEPT_JSON}}': json.dumps(cdata, separators=(',', ':')), '{{MAT_JSON}}': json.dumps(mtab, separators=(',', ':')),
           '{{MAIN}}': res['consulted']['main'][:7], '{{ISSA}}': res['consulted']['issa'][:7], '{{STATIONS}}': E(json.dumps(st))}
    for k, v in rep.items():
        page = page.replace(k, v)
    assert '{{' not in page, [l for l in page.splitlines() if '{{' in l][:3]
    (R / 'psa.html').write_text(page)
    print('wrote', R / 'psa.html', len(page), 'bytes')


if __name__ == '__main__':
    main()
