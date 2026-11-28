"""PSA Phase II interactive report: results/psa_phase2.html from the Phase II result files and the narrative in narrative_p2.toml.

    python3 work/primary-structural-architecture/phase2/build_report_p2.py
"""
import html
import json
import math
import tomllib
from pathlib import Path

H = Path(__file__).resolve().parent
WD = H.parent
RES = WD / 'results'
CSS_SRC = (WD / 'report_template.html').read_text()
CSS = CSS_SRC[CSS_SRC.index('<style>'):CSS_SRC.index('</style>')+8]
CSS = CSS.replace('</style>', '.sev{white-space:nowrap;display:inline-block}</style>')


def J(name):
    p = RES / name
    return json.loads(p.read_text()) if p.exists() else {}


def e(s):
    return html.escape(str(s))


def f(v, d=1):
    if v is None:
        return '—'
    if isinstance(v, str):
        return e(v)
    if isinstance(v, float) and (math.isinf(v) or math.isnan(v)):
        return '∞' if math.isinf(v) else '—'
    return f'{v:,.{d}f}'


def table(head, rows, num=()):
    th = ''.join(f'<th>{e(h)}</th>' for h in head)
    tr = ''.join('<tr>' + ''.join(f'<td class="num">{c}</td>' if i in num else f'<td>{c}</td>' for i, c in enumerate(r)) + '</tr>' for r in rows)
    return f'<div class="scroll"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


CLS = {'AN': ('ANALYTICAL', 'c-sim'), 'NUM': ('NUMERICAL SCREENING', 'c-sim'), 'PHYS': ('PHYSICALLY SUPPORTED', 'c-model'),
       'FIC': ('FICTIONAL / PROTOTYPE ASSUMPTION', 'c-concept'), 'OPEN': ('OPEN', 'c-warn')}


def chips(*k):
    return '<div class="chips">' + ''.join(f'<span class="chip {CLS[x][1]}">{CLS[x][0]}</span>' for x in k) + '</div>'


def section(id_, letter, title, body):
    return f'<section id="{id_}"><div class="wrap"><div class="letter">{e(letter)}</div><h2>{e(title)}</h2>{body}</div></section>'


def bars(rows, unit='t', ref=None, w=760):
    """Horizontal stacked bars: rows = [(label, [(value, css var, name)])]."""
    mx = max(sum(v for v, _, _ in segs) for _, segs in rows) or 1.0
    if ref:
        mx = max(mx, ref*1.05)
    h = 26*len(rows)+40; out = [f'<svg viewBox="0 0 {w} {h}" role="img">']
    x0 = 170; W = w-x0-70
    for i, (lab, segs) in enumerate(rows):
        y = 10+26*i; x = x0
        out.append(f'<text x="{x0-8}" y="{y+13}" text-anchor="end" class="t11 ink">{e(lab)}</text>')
        for v, col, nm in segs:
            ww = W*v/mx; out.append(f'<rect x="{x:.1f}" y="{y}" width="{max(ww, 0):.1f}" height="18" fill="var({col})"><title>{e(nm)} {v:,.0f} {unit}</title></rect>'); x += ww
        out.append(f'<text x="{x+6:.1f}" y="{y+13}" class="t11">{sum(v for v, _, _ in segs):,.0f} {unit}</text>')
    if ref:
        xr = x0+W*ref/mx; out.append(f'<line x1="{xr:.1f}" y1="4" x2="{xr:.1f}" y2="{h-24}" stroke="var(--warn)" stroke-dasharray="4 3"/>')
        out.append(f'<text x="{xr:.1f}" y="{h-10}" text-anchor="middle" class="t10">{ref:g} {unit} reference line</text>')
    out.append('</svg>'); return ''.join(out)


def curve(series, w=760, h=260, xr=(-140, 170), yl='N (MN)'):
    """Line chart of section load along X: series = [(name, css var, [(x, y)])]."""
    ys = [y for _, _, pts in series for _, y in pts] or [0, 1]
    y0, y1 = min(0.0, min(ys)), max(ys)*1.08 or 1.0
    L, R, T, B = 52, 20, 14, 36
    sx = lambda x: L+(x-xr[0])*(w-L-R)/(xr[1]-xr[0]); sy = lambda y: h-B-(y-y0)*(h-T-B)/(y1-y0)
    out = [f'<svg viewBox="0 0 {w} {h}" role="img">']
    for k in range(6):
        yv = y0+(y1-y0)*k/5; out.append(f'<line x1="{L}" x2="{w-R}" y1="{sy(yv):.1f}" y2="{sy(yv):.1f}" stroke="var(--line)"/><text x="{L-6}" y="{sy(yv)+4:.1f}" text-anchor="end" class="t10">{yv:.0f}</text>')
    for xv in range(-120, 171, 40):
        out.append(f'<text x="{sx(xv):.1f}" y="{h-18}" text-anchor="middle" class="t10">X {xv}</text>')
    out.append(f'<text x="{L}" y="{T-2}" class="t10">{e(yl)}</text>')
    for i, (nm, col, pts) in enumerate(series):
        d = ' '.join(f'{"M" if j == 0 else "L"}{sx(x):.1f},{sy(y):.1f}' for j, (x, y) in enumerate(pts))
        out.append(f'<path d="{d}" fill="none" stroke="var({col})" stroke-width="2"/>')
        out.append(f'<rect x="{L+10+i*190}" y="{h-10}" width="14" height="3" fill="var({col})"/><text x="{L+28+i*190}" y="{h-6}" class="t10">{e(nm)}</text>')
    out.append('</svg>'); return ''.join(out)


FAMC = {'rails/longerons': '--al', 'frames': '--st', 'diagonals': '--info', 'thrust ring + transition + pickups': '--drive', 'spine + ties': '--hab',
        'rotor bay (collar / hub cones)': '--accent', 'keels + deck': '--therm', 'joints': '--ti', 'casing + rotating': '--occ'}
FAMMAP = {'rail': 'rails/longerons', 'frame': 'frames', 'modframe': 'frames', 'diag': 'diagonals', 'ring': 'thrust ring + transition + pickups',
          'trans': 'thrust ring + transition + pickups', 'pickup': 'thrust ring + transition + pickups', 'spine': 'spine + ties', 'hub': 'spine + ties',
          'tie': 'spine + ties', 'cone': 'spine + ties', 'collar': 'rotor bay (collar / hub cones)', 'hubcone': 'rotor bay (collar / hub cones)',
          'keel': 'keels + deck', 'deck': 'keels + deck'}


def main():
    N = tomllib.loads((H / 'narrative_p2.toml').read_text())
    V = J('p2_variants.json'); L = J('p2_ledger.json'); B = J('p2_bench.json'); P = J('p2_pickup.json'); T = J('p2_thermal.json')
    BB = J('p2_backbone.json'); I = J('p2_interface.json'); HI = J('p2_hierarchy.json'); FS = J('p2_failsafe.json')
    import tomllib as tl
    AL = tl.loads((H / 'allowables.toml').read_text())
    S = []
    # ---- A review gate
    gate = N['gate']
    cards = ''.join(f'<div class="card"><h4>{e(c[0])}</h4><div class="big">{e(c[1])}</div><div class="fn">{e(c[2])}</div></div>' for c in gate['cards'])
    S.append(section('gate', 'A · REVIEW GATE', 'Most promising morphology', f'<p class="lede">{gate["lede"]}</p><div class="grid">{cards}</div>' +
                     ''.join(f'<h3>{e(h)}</h3><p>{t}</p>' for h, t in gate['why']) + chips('NUM', 'OPEN')))
    # ---- B loads
    Lb = N['loads']
    rows = []
    for k in ('H:hub:F1', 'H:hub:P', 'H:hub:R'):
        v = V.get(k)
        if v:
            rows.append((v['config'], [(x['x'], x['N_MN']) for x in v['section_loads']]))
    ser = []
    cols = ['--action', '--info', '--good']
    for i, (nm, pts) in enumerate(rows):
        ser.append((f'{nm} departure, steady x DLF', cols[i], [(x, -y) for x, y in pts]))
    v = V.get('H:hub:F1')
    if v:
        ser.append(('F1 end of burn', '--warn', [(x['x'], -x['N_MN']) for x in v['section_loads_end']]))
    lc = table(['Class', 'Definition', 'Factor', 'Use'], [[e(a), b_, e(c), e(d)] for a, b_, c, d in Lb['classes']])
    S.append(section('loads', 'B · D01 LOADS', 'Thrust-bounded, configuration-specific loads',
                     f'<p>{Lb["intro"]}</p>{lc}<figure><div class="frame">{curve(ser, yl="compression through the section (MN)")}</div><figcaption>{Lb["fig"]}</figcaption></figure>'
                     f'<h3>Section-load reconciliation (63.5 / 64.5 MN)</h3><p>{Lb["recon"]}</p>' + table(['Figure', 'What it is', 'Value'], Lb['recon_rows'], num=(2,)) + chips('AN', 'NUM')))
    # ---- C solver
    rowsb = []
    for k, lab in (('cantilever', 'Cantilever tip deflection'), ('euler_pinned', 'Euler pinned-pinned buckling'), ('cantilever_f1', 'Cantilever first frequency'),
                   ('freefree_f1', 'Free-free first frequency'), ('beck_follower', 'Beck follower column (20.05)'), ('beal_free_free_follower', 'Beal free-free follower (109.9)')):
        for r in B.get(k, []):
            rowsb.append([e(lab), str(r['n']), f(r['value'], 4), f(r['exact'], 4), f'{r["err"]:.1e}' if r.get('err') is not None else '—'])
    th = B.get('thermal', {})
    S.append(section('solver', 'C · SECTION 6', 'Verified solver', f'<p>{N["solver"]["intro"]}</p>' + table(['Benchmark', 'Elements', 'Solver', 'Exact', 'Rel. error'], rowsb, num=(1, 2, 3, 4)) +
                     f'<p class="fn">Thermal: clamped stress {f(th.get("clamped_sigma", 0)/1e6, 2)} MPa vs {f(th.get("clamped_exact", 0)/1e6, 2)}; free growth {f(th.get("free_growth", 0)*1e3, 3)} mm vs {f(th.get("growth_exact", 0)*1e3, 3)}. '
                     f'Legacy fe_frame.py difference {B.get("legacy_fe_frame_rel_diff", 0):.1e}. Inertia relief exact to {max((r["max_err_over_P"] for r in B.get("inertia_relief", [{"max_err_over_P": 0}])), default=0):.1e}.</p>'
                     f'<p>{N["solver"]["limits"]}</p>' + chips('PHYS')))
    # ---- D variants
    rowsv = []; bar_rows = []
    for k, v in V.items():
        st = v.get('stability', {})
        g = lambda n: (st.get(n) or {}).get('lam')
        stiff = v.get('stiffness', [])
        rowsv.append([f'<b>{e(k)}</b>', str(v['rails']), f(v['strength_members_t'] if 'strength_members_t' in v else v['members_t']), f(v.get('stiffness_increment_t', 0)), f(v['joints_t']),
                      f(v['structure_t']), f(v['f_axial_Hz'], 3), f(g('fixed-direction (static)'), 2), f(g('follower'), 2), f(g('partial follower 0.5'), 2),
                      ', '.join(v['failing']) or '—'])
        fam = {}
        for k2, m in v['by_family_t'].items():
            fam[FAMMAP.get(k2, k2)] = fam.get(FAMMAP.get(k2, k2), 0)+m
        fam['joints'] = v['joints_t']
        bar_rows.append((k, [(fam.get(n, 0.0), c, n) for n, c in FAMC.items() if n != 'casing + rotating']))
    legend = ''.join(f'<span class="mono" style="margin-right:12px"><span class="sw" style="background:var({c})"></span> {e(n)}</span>' for n, c in FAMC.items() if n != 'casing + rotating')
    S.append(section('concepts', 'D · D02 D06', 'Sized concepts and variants',
                     f'<p>{N["concepts"]["intro"]}</p>' + table(['Variant', 'Rails', 'Strength-sized members t', '+ stiffness t', 'Joints t', 'Primary structure t', 'f1 Hz', 'λ static', 'λ follower', 'λ partial 0.5', 'Groups at max size'], rowsv, num=(1, 2, 3, 4, 5, 6, 7, 8, 9)) +
                     f'<figure><div class="frame">{bars(bar_rows, ref=150)}</div><figcaption>{legend}<br>{N["concepts"]["fig"]}</figcaption></figure>' +
                     ''.join(f'<h3>{e(h)}</h3><p>{t}</p>' for h, t in N['concepts']['findings']) + chips('NUM', 'OPEN')))
    # ---- E stability
    stb = N['stability']
    rows_s = []
    for k, v in V.items():
        for nm, r in (v.get('stability') or {}).items():
            if isinstance(r, dict) and 'lam' in r:
                rows_s.append([e(k), e(nm), f(r.get('lam'), 2) if r.get('lam') is not None else f'> 12', e(r.get('kind', '')), ', '.join(f'{g} {s:.0%}' for g, s in list((r.get('mode_groups') or {}).items())[:3])])
    conv = (V.get('H:hub:F1', {}).get('stability') or {})
    S.append(section('stability', 'E · SECTION 3.3', 'Global stability and modes', f'<p>{stb["intro"]}</p>' +
                     ''.join(f'<h3>{e(h)}</h3><p>{t}</p>' for h, t in stb['findings']) +
                     f'<details><summary>All stability results ({len(rows_s)})</summary>' + table(['Variant', 'Case', 'λ (x limit thrust)', 'Kind', 'Mode lives in'], rows_s, num=(2,)) + '</details>' +
                     f'<p class="fn">Basis convergence (H hub F1): follower {e(conv.get("basis convergence (follower)"))}; static {e(conv.get("basis convergence (static)"))}.</p>' + chips('NUM', 'OPEN')))
    # ---- F rails and damage
    dmg_rows = []
    for k in ('H:hub:F1', 'H3:hub:F1', 'HC:hub:F1', 'A:hub:F1', 'C:hub:F1'):
        v = V.get(k)
        for d in (v or {}).get('damage', []):
            dmg_rows.append([e(k), e(d['name']), f'<span class="sev {"MINOR" if d["class"] == "NOMINAL" else "MAJOR" if d["class"] == "REDUCED THRUST" else "CRITICAL"}">{e(d["class"])}</span>',
                             f(d.get('u_nom'), 2), f(d.get('f_emer'), 2), e(' → '.join(d.get('collapse_chain', [])[:4]) or 'arrested')])
    S.append(section('rails', 'F · D03 SECTION 8', 'Three versus six rails, damage and repair', f'<p>{N["rails"]["intro"]}</p>' +
                     ''.join(f'<h3>{e(h)}</h3><p>{t}</p>' for h, t in N['rails']['findings']) +
                     table(['Variant', 'Damage case', 'Class', 'Ultimate util. at full thrust', 'Emergency thrust fraction', 'Progressive chain at full thrust'], dmg_rows, num=(3, 4)) +
                     '<h3>Redundancy penalty: fail-safe resizing (D03)</h3>' + table(['Variant | target', 'Intact members t', 'Fail-safe members t', 'Change t', 'Groups at max size', 'Rail-bay losses after resizing', 'Rail-joint losses after resizing'],
                       [[e(k), f(r['intact_members_t']), f(r['failsafe_members_t']), f(r['penalty_t']), e(', '.join(r['passes'][-1]['at_max']) or '—'),
                         e(', '.join(sorted({c['class'] for c in r['verify'] if 'bay' in c['name']}))), e(', '.join(sorted({c['class'] for c in r['verify'] if 'joint' in c['name']})))] for k, r in FS.items()], num=(1, 2, 3)) +
                     f'<p>{N["rails"]["failsafe"]}</p>' +
                     '<h3>Repair procedure</h3>' + table(['Step', 'What happens', 'Structural condition'], N['rails']['repair']) + chips('NUM', 'FIC', 'OPEN')))
    # ---- G pickups
    rowsp = [[e(r['name']), f(r['angle_deg'], 1), f(r['strut_N_over_T'], 2), f(r['strut_MN_at_canon_29.42MN'], 1), f(r['strut_MN_at_flight_21.77MN'], 1), f(r['ring_M_kNm_per_MN'], 0), f(r['nozzle_dx_mm_per_MN'], 1)] for r in P]
    S.append(section('pickup', 'G · SECTION 3.2', 'Drive pickup audit', f'<p>{N["pickup"]["intro"]}</p>' + table(['Configuration (one change from baseline)', 'Strut angle from axis °', 'Max strut force / nozzle thrust', 'Strut MN at 29.42 MN', 'Strut MN at 21.77 MN', 'Ring moment kN m per MN', 'Nozzle axial give mm per MN'], rowsp, num=(1, 2, 3, 4, 5, 6)) +
                     ''.join(f'<h3>{e(h)}</h3><p>{t}</p>' for h, t in N['pickup']['findings']) + chips('NUM', 'AN')))
    # ---- H thermal and backbone
    rows_t = []
    for k, lst in T.items():
        for r in lst:
            rows_t.append([e(k), e(r['ties']), e(r['case']), f(r['max_util'], 2), e(r['at']), f(r['growth_mm'], 1), f(r['brow_bow_mm'], 1), f(r['spine_slip_mm_at_x60'], 1)])
    rows_bb = [[e(o['option']), f(o['backbone_kg_per_m'], 1), f(o['leak_W_per_m'], 0), f(o['cool_radiator_m2_per_m'], 2), f(o['three_planes_t'], 1), f(o['growth_mm_per_section'], 0), e(o['note'])] for o in BB.get('options', [])]
    S.append(section('thermal', 'H · SECTIONS 3.5 3.6', 'Thermal compliance and the radiator backbone', f'<p>{N["thermal"]["intro"]}</p>' +
                     table(['Variant', 'Spine ties', 'Case', 'Peak thermal util.', 'At', 'Growth mm', 'Brow bow mm', 'Spine slip mm (X 60)'], rows_t, num=(3, 5, 6, 7)) +
                     ''.join(f'<h3>{e(h)}</h3><p>{t}</p>' for h, t in N['thermal']['findings']) +
                     '<h3>Radiator backbone alternatives</h3>' + table(['Option', 'Backbone kg/m', 'Heat leak W/m', 'Cool radiator m²/m', 'Three planes t', 'Growth per 25.4 m mm', 'Basis'], rows_bb, num=(1, 2, 3, 4, 5)) +
                     f'<p>{N["thermal"]["backbone"]}</p>' + chips('AN', 'NUM', 'OPEN')))
    # ---- I allowables
    rows_a = [[f'<b>{e(m["id"])}</b>', e(m['name']), f'{m["E"][1] if isinstance(m["E"], list) else m["E"]}', e(m['Fcy']), e(m['Ftu']), e(m['class']), e(m['uncertainty'])] for m in AL['material']]
    S.append(section('materials', 'I · SECTION 3.4', 'Allowables and uncertainty register', f'<p>{N["materials"]["intro"]}</p>' + table(['ID', 'Material', 'E GPa', 'Compression design MPa [low, nom, high]', 'Tension MPa', 'Class', 'Uncertainty / bridging advance'], rows_a) +
                     ''.join(f'<h3>{e(h)}</h3><p>{t}</p>' for h, t in N['materials']['findings']) + chips('AN', 'FIC', 'OPEN')))
    # ---- J ledger and mission
    own = table(['Item', 'Owner', 'Basis'], [[e(a), e(b_), e(c)] for a, b_, c in L.get('owners', [])])
    rows_l = []
    for k, v in L.get('variants', {}).items():
        rows_l.append([e(k), f(v['psa_total_t']), f(v['delta_vs_line_t']), f(v['coupled_departure_delta_t'], 0), f(v['coupled_departure_t'], 0),
                       f'{f(-v["uncertainty_t"]["high_allowables"], 0)} / +{f(v["uncertainty_t"]["low_allowables"], 0)}'])
    cp = L.get('coupling', {})
    hs = L.get('hand_sized', {})
    S.append(section('ledger', 'J · D04 D05 SECTION 10', 'Mass ownership and mission coupling', f'<p>{N["ledger"]["intro"]}</p>{own}' +
                     f'<p class="fn">Hand-sized parts: protective casing {f(hs.get("casing_t"))} t ({f(hs.get("casing_area_m2"), 0)} m², 2.6 kg/m²); rotating ring structure {f((hs.get("rotating_per_ring") or {}).get("total_t"))} t per ring; spine pressure liner {f(hs.get("spine_liner_t"))} t (habitat-owned, {f(hs.get("spine_liner_t_mm"), 1)} mm).</p>' +
                     table(['Variant', 'PSA total t (members + joints + casing + rotating)', 'vs 150 t line', 'Coupled departure change t', 'Coupled departure t', 'Allowable band t (high / low)'], rows_l, num=(1, 2, 3, 4)) +
                     table(['Configuration', 'Mass ratio R', 'Tankage per propellant k', 'Coupling dM_dep/dM_dry', 'ISSA figure'], [[e(c), f(x['R'], 3), f(x['k'], 3), f(x['coupling'], 3), f(x.get('issa_coupling'), 3)] for c, x in cp.items()], num=(1, 2, 3, 4)) +
                     ''.join(f'<h3>{e(h)}</h3><p>{t}</p>' for h, t in N['ledger']['findings']) + chips('AN', 'NUM')))
    # ---- K sourcing
    rows_i = []
    for k, v in L.get('variants', {}).items():
        if v['config'] != 'F1':
            continue
        for sc, im in v['imports'].items():
            c = im['by_category_t']
            rows_i.append([e(k), e(sc)] + [f(c[x], 1) for x in ('carbon fibres', 'polymer matrices', 'alloying elements', 'specialty metals', 'ceramic precursors', 'manufacturing consumables', 'finished specialist components')] +
                          [f(im['total_t'], 1), f(100*im['longeron_fraction'], 1), f(100*im['structure_fraction'], 1), f(100*im['whole_ship_fraction_psa_only'], 2)])
    S.append(section('sourcing', 'K · D07', 'Imports by category and supply scenario', f'<p>{N["sourcing"]["intro"]}</p>' +
                     table(['Variant', 'Scenario', 'Carbon fibre t', 'Polymer t', 'Alloying t', 'Specialty metal t', 'Ceramic precursor t', 'Consumables t', 'Specialist parts t', 'Total t', 'Longerons %', 'Structure %', 'Whole ship % (PSA share)'], rows_i, num=tuple(range(2, 13))) +
                     ''.join(f'<h3>{e(h)}</h3><p>{t}</p>' for h, t in N['sourcing']['findings']) + chips('AN', 'FIC')))
    # ---- L interface
    rows_r = []; rows_c = []
    for k, x in I.get('variants', {}).items():
        if k != 'H:hub:F1':
            continue
        for r in x['reactions']:
            rows_r.append([e('departure' if r['left'] == 1.0 else 'end of burn'), e(r['cls']), f(r['a_axial_g'], 3), f(r['anchor_axial_kN'], 0), f(r['slide_lateral_kN'], 1), f(r['shutdown_reversal_anchor_kN'], 0)])
        for c in x.get('lanes', []):
            rows_c.append([e(c['lane']), f(c['min_clear_m'], 2), e(c['member']), f(c.get('at_x'), 1), '<span class="good">clear</span>' if c['ok'] else '<span class="bad">CLASH</span>'])
        tr = x.get('support_travel') or []
    S.append(section('interface', 'L · SECTION 2', 'ISSA interface refresh (CP4 9faee26)', f'<p>{N["interface"]["intro"]}</p>' +
                     '<h3>Hot-loop support reactions per section (H hub F1)</h3>' + table(['State', 'Class', 'Axial a (g)', 'Anchor axial kN', 'Slide lateral kN', 'Shutdown reversal kN'], rows_r, num=(2, 3, 4, 5)) +
                     '<h3>Interference checks against the H hub F1 members</h3>' + table(['Lane', 'Min clearance m', 'Nearest member group', 'At X', 'Result'], rows_c, num=(1, 3)) +
                     (f'<p class="fn">Structure-induced shortening of each 25.4 m hot-loop section under steady thrust: {", ".join(f(s["shortening_mm"], 1)+" mm" for s in tr)} (adds to the ±38..127 mm thermal travel at the slides).</p>' if tr else '') +
                     ''.join(f'<h3>{e(h)}</h3><p>{t}</p>' for h, t in N['interface']['findings']) + chips('NUM', 'OPEN')))
    # ---- M hierarchy
    rows_h = [[e(k), str(v['distinct_cassettes']), f(v['members_t']), f(v['penalty_t']), f(v['penalty_pct'], 1)] for k, v in HI.get('variants', {}).items()]
    S.append(section('hierarchy', 'M · SECTIONS 4 5 9', 'Vertebral hierarchy, morphology and cassettes', f'<p>{N["hierarchy"]["intro"]}</p>' +
                     table(['Level', 'Definition'], N['hierarchy']['levels']) + table(['District', 'X range', 'Specialisation'], [[e(d['name']), f'{d["x"][0]:g} .. {d["x"][1]:g}', e(d['note'])] for d in HI.get('L4', [])]) +
                     table(['Variant', 'Distinct cassettes', 'Members t', 'Standardisation penalty t', '%'], rows_h, num=(1, 2, 3, 4)) +
                     ''.join(f'<h3>{e(h)}</h3><p>{t}</p>' for h, t in N['hierarchy']['findings']) + chips('NUM', 'FIC')))
    # ---- N problems, roadmap, decisions
    pr = table(['ID', 'Severity', 'Problem', 'Next step'], [[f'<span class="mono">{e(a)}</span>', f'<span class="sev {e(b_)}">{e(b_)}</span>', c, d] for a, b_, c, d in N['problems']['rows']])
    rd = ''.join(f'<div class="phase"><div class="n">{e(a)}</div><div><p><b>{e(b_)}</b></p><p>{c}</p></div></div>' for a, b_, c in N['roadmap']['rows'])
    dec = '<ol class="dr">' + ''.join(f'<li><b class="id">{e(a)}</b>{b_}</li>' for a, b_ in N['decisions']['rows']) + '</ol>'
    S.append(section('problems', 'N · SECTION 12.19', 'Problem register', pr))
    S.append(section('roadmap', 'O · PHASE III', 'Roadmap', rd))
    S.append(section('decisions', 'P · OWNER', 'Decisions requested', f'<p>{N["decisions"]["intro"]}</p>{dec}'))
    nav = ''.join(f'<a href="#{i}">{e(t)}</a>' for i, t in (('gate', 'Gate'), ('loads', 'Loads'), ('solver', 'Solver'), ('concepts', 'Concepts'), ('stability', 'Stability'), ('rails', 'Rails & damage'),
                  ('pickup', 'Pickups'), ('thermal', 'Thermal'), ('materials', 'Materials'), ('ledger', 'Ledger'), ('sourcing', 'Sourcing'), ('interface', 'ISSA'), ('hierarchy', 'Hierarchy'),
                  ('problems', 'Problems'), ('roadmap', 'Phase III'), ('decisions', 'Decisions')))
    head = N['head']
    page = (f'<title>Wayfarer Primary Structure</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
            '<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600&family=Space+Grotesk:wght@500;600&display=swap">\n'
            + CSS + f'<header class="top"><div class="wrap"><div class="eyebrow">{e(head["eyebrow"])}</div><h1>{e(head["title"])}</h1><p class="lede">{head["lede"]}</p>'
            + '<div class="chips">' + ''.join(f'<span class="chip">{e(c)}</span>' for c in head['chips']) + f'</div><p class="fn">{head["phase1"]}</p></div></header>'
            + f'<nav class="toc"><div class="wrap" style="display:flex;gap:4px">{nav}</div></nav>' + ''.join(S)
            + f'<footer><div class="wrap"><p class="fn">{head["footer"]}</p></div></footer>')
    (RES / 'psa_phase2.html').write_text(page)
    print('wrote', RES / 'psa_phase2.html', len(page)//1024, 'kB')


if __name__ == '__main__':
    main()
