"""ISSA Phase IV page sections (deliverables 1-17), inserted above Phase III into results/issa.html by build_report.py.
Reads results/phase4.json. Pure Python, inline SVG with the page's theme tokens."""
import html
import json
import math
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]/'results'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'phase2'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'phase3'))
from report2 import t3, table, bars, box, arrow, DEFS, section  # noqa: E402
from report3 import tag, ok  # noqa: E402

E = html.escape
MONO = 'font:11px IBM Plex Mono,monospace'; SANS = 'font:12px IBM Plex Sans,sans-serif'


def fig(svg, cap):
    return f'<figure><div class="frame">{svg}</div><figcaption class="fn">{cap}</figcaption></figure>'


def txt(x, y, s, anchor='start', st=SANS, fill='ink'):
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" style="fill:var(--{fill});{st}">{E(s)}</text>'


def fig_viewfactor(T):
    """side view along the blades: hot region, bulkhead, WARM, LOW; F values and the baffle."""
    w, h = 900, 300; x0, x1 = -115.0, 130.0; sx = lambda x: 40+(x-x0)/(x1-x0)*(w-80)
    s = [f'<svg viewBox="0 0 {w} {h+20}" role="img" aria-label="View factors from radiator sections to the hot blades">', DEFS]
    y = 70; bh = 60
    s.append(f'<rect x="{sx(-111.6):.0f}" y="{y}" width="{sx(50.4)-sx(-111.6):.0f}" height="{bh}" style="fill:var(--bad);opacity:.35"/>')
    s.append(txt((sx(-111.6)+sx(50.4))/2, y+35, 'HOT 1800 K (other two blades seen at 120°)', 'middle'))
    s.append(f'<rect x="{sx(50.4):.0f}" y="{y}" width="{sx(72.9)-sx(50.4):.0f}" height="{bh}" style="fill:var(--warn);opacity:.45"/>')
    s.append(txt((sx(50.4)+sx(72.9))/2, y+35, 'WARM 440 K', 'middle'))
    s.append(f'<rect x="{sx(73.4):.0f}" y="{y}" width="{sx(93.4)-sx(73.4):.0f}" height="{bh}" style="fill:var(--info);opacity:.45"/>')
    s.append(txt((sx(73.4)+sx(93.4))/2, y+35, 'LOW 300 K', 'middle'))
    s.append(f'<rect x="{sx(93.9):.0f}" y="{y}" width="{sx(125)-sx(93.9):.0f}" height="{bh}" style="fill:none;stroke:var(--action);stroke-dasharray:5 4"/>')
    s.append(txt((sx(93.9)+sx(125))/2, y+35, 'G2: aft storage', 'middle', MONO, 'action'))
    s.append(f'<line x1="{sx(50.0):.0f}" y1="{y-30}" x2="{sx(50.0):.0f}" y2="{y+bh+30}" style="stroke:var(--good);stroke-width:4"/>')
    s.append(txt(sx(50.0), y-36, 'production graded bulkhead, 3 layers, r 6.1–37 m', 'middle', MONO, 'good'))
    s.append(f'<rect x="{sx(26.4):.0f}" y="{y+8}" width="{sx(50.4)-sx(26.4):.0f}" height="{bh-16}" style="fill:none;stroke:var(--action);stroke-width:2;stroke-dasharray:5 4"/>')
    s.append(f'<line x1="{sx(26.2):.0f}" y1="{y-14}" x2="{sx(26.2):.0f}" y2="{y+bh+14}" style="stroke:var(--action);stroke-width:3;stroke-dasharray:4 3"/>')
    s.append(txt(sx(26.2), y+bh+28, 'R4a: 700 K section, bulkhead moved aft', 'middle', MONO, 'action'))
    vf = {r['surface']: r for r in T['view_factors']}
    pick = [k for k in vf if k.startswith('WARM, production')] + [k for k in vf if k.startswith('WARM if')] + [k for k in vf if '29 m' in k] + [k for k in vf if k.startswith('700 K')]
    yy = y+bh+60
    for k, n in enumerate(pick):
        a = vf[n]
        s.append(txt(40, yy+k*20, f'{n[:80]}: F = {a["F_hot"]:.4f} → {a["ratio"]:.2f}× emission', st=MONO, fill='good' if a['works_in_burn'] else 'bad'))
    s.append(txt(40, 24, 'ship x (m) →  aft … bow', st=MONO, fill='muted'))
    for xv in (-100, -50, 0, 50, 100):
        s.append(f'<text x="{sx(xv):.0f}" y="{y+bh+14}" text-anchor="middle" style="fill:var(--muted);{MONO}">{xv}</text>')
    s.append('</svg>')
    return fig(''.join(s), 'Monte Carlo view factor (both faces, cosine-weighted rays, three planar blades at 120°, casing blocks rays). Text: what each '
               'section absorbs from the 1800 K faces of the other two blades during a burn, relative to what it emits at its own temperature.')


def fig_transmission(W):
    rows = W['S2']['rows']; w, h = 760, 280; lw = 70
    ys = lambda v: 30+(-math.log10(max(v, 1e-7)))/7*(h-70)
    xs = lambda t: lw+t/80*(w-lw-40)
    s = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="LiH shield transmission">']
    for d in range(0, 8):
        y = ys(10**-d); s.append(f'<line x1="{lw}" y1="{y:.0f}" x2="{w-40}" y2="{y:.0f}" style="stroke:var(--line)"/>'+txt(lw-6, y+4, f'1e-{d}', 'end', MONO, 'muted'))
    for key, tone, lab in (('n_number_T', 'bad', 'neutrons (number)'), ('n_energy_T', 'warn', 'neutron energy'), ('n_src_g_energy_T', 'info', 'secondary γ energy'),
                           ('g_energy_T', 'action', 'core γ energy')):
        pts = ' '.join(f'{xs(r["lih_cm"]):.0f},{ys(r[key]):.0f}' for r in rows if r[key] > 0)
        s.append(f'<polyline points="{pts}" style="fill:none;stroke:var(--{tone});stroke-width:2"/>')
        r = [r for r in rows if r[key] > 0][-1]; s.append(txt(xs(r['lih_cm'])-4, ys(r[key])-6, lab, 'end', MONO, tone))
    for t in (0, 20, 40, 60, 80):
        s.append(txt(xs(t), h-22, f'{t}', 'middle', MONO, 'muted'))
    s.append(txt(w-40, h-6, 'LiH thickness behind 5 cm W (cm)', 'end', MONO, 'muted'))
    s.append('</svg>')
    lam = W['S2']['relaxation_cm']
    return fig(''.join(s), f'OpenMC 0.15.3, ENDF/B-VIII.0, broad-beam slab, surrogate-core leakage spectra. Relaxation lengths in LiH: neutron number '
               f'{lam["neutron_number"]:.1f} cm, neutron energy {lam["neutron_energy"]:.1f} cm, secondary γ {lam["secondary_gamma"]:.0f} cm. '
               'The 80 cm neutron point is statistics-limited (one tally event in 6 × 10⁵ histories). TRANSPORT-INFORMED, not validated.')


def fig_tank_layers(D):
    w, h = 860, 220
    s = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="He-3 tank heating by layer">', DEFS]
    xs = [20, 190, 360, 530, 700]
    names = [('Outer shell ~300 K', 'γ ~55 %, n ~2 %'), ('MLI 40–80 K', 'by mass'), ('Stages 4–20 K', 'OPEN'), ('He-3 liquid 3 K', 'n ~100 % (1.01 MeV)'),
             ('Coolers', '3 K load = deposit')]
    tones = ['muted', 'line', 'line', 'bad', 'info']
    for x, (a, b), t in zip(xs, names, tones):
        s.append(box(x, 70, 150, 56, a, b, t))
    for a, b in zip(xs, xs[1:]):
        s.append(arrow(a+150, 98, b, 98))
    s.append(txt(20, 40, 'neutron →  passes the warm layers almost untouched, captured by He-3(n,p)T: Q = 764 keV deposited at 3 K', st=MONO))
    s.append(txt(20, 58, 'gamma →  He-3 is thin (0.082 g/cm³): most photon energy stays in the warm wall', st=MONO))
    bare = next(r for r in D['tank_rows'] if r['Pe_W'] == 3.5e6 and r['side_shield_cm_LiH_after_5cm_W'] == 0)
    s.append(txt(20, 160, f'Bare, one 3.5 MWe unit at {D["transport"]["d_m"]:.0f} m: {bare["he3_W_per_tank_per_unit"]:.0f} W per tank at 3 K '
                          f'(3 K lift {D["transport"]["lift_W"]:.0f} W for all tanks)', st=MONO, fill='bad'))
    s.append(txt(20, 180, f'Tanks sit ≤ {D["correction"]["actual_off_axis_deg_max"]:.0f}° off axis, inside the 12.5° shadow cone: the direct path closes; scatter is OPEN', st=MONO, fill='good'))
    s.append('</svg>')
    return fig(''.join(s), 'Layer split from the OpenMC S3 case (2 cm Al + 50 cm liquid He-3, 1-D). Intermediate stages need the real tank stack: OPEN.')


def fig_transport(Tr):
    items = [(r['name'][:2]+' '+r['name'].split(':')[0][3:40] if ':' in r['name'] else r['name'][:44], tuple(x/1e6 for x in r['pump_W']), 'warn') for r in Tr['rows']]
    inv = [(r['name'][:44], tuple(r['mass_t']), 'info') for r in Tr['rows']]
    return bars(items, 'pump work, MW') + bars(inv, 'transport hardware incl. lithium, t')


def fig_l2(L):
    rows = [r for r in L['rows'] if r['strategy'].startswith('C')]
    items = [(f'{r["Pe_W"]/1e6:.2f} MWe × 3, two left (EOL)', tuple(x/1e6+3 for x in r['margins']['EOL']['one_unit']), 'good' if r['margins']['EOL']['one_unit'][1] > 0 else 'bad') for r in rows]
    return bars(items, 'margin after one loss + 3 MW offset (3 = zero margin)', max_v=8) + '<p class="fn">Bars are offset by +3 MW so negative margins show: a value below 3 is a shortfall.</p>'


def fig_missions(M):
    Ds = sorted({r['D_AU'] for r in M['rows']}); Vs = sorted({r['v_c'] for r in M['rows']})
    w, cw, ch = 860, 160, 46; lw = 120
    s = [f'<svg viewBox="0 0 {w} {lw+len(Ds)*ch}" role="img" aria-label="mission matrix">']
    for j, v in enumerate(Vs):
        s.append(txt(lw+j*cw+cw/2, 30, f'{v} c', 'middle', MONO, 'muted'))
    for i, D in enumerate(Ds):
        y = 44+i*ch; s.append(txt(lw-10, y+28, f'{D:.0f} AU', 'end', MONO, 'muted'))
        for j, v in enumerate(Vs):
            r = next(r for r in M['rows'] if r['D_AU'] == D and r['v_c'] == v)
            tone = 'good' if r['months'] <= 18 else ('warn' if r['months'] <= 36 else 'bad')
            s.append(f'<rect x="{lw+j*cw+2}" y="{y}" width="{cw-4}" height="{ch-4}" rx="4" style="fill:var(--{tone});opacity:.25"/>')
            s.append(txt(lw+j*cw+cw/2, y+18, f'{r["months"]:.1f} mo', 'middle', 'font:600 12px IBM Plex Mono,monospace'))
            s.append(txt(lw+j*cw+cw/2, y+34, f'{r["departure_t"]:,.0f} t dep', 'middle', MONO, 'muted'))
    s.append('</svg>')
    return fig(''.join(s), 'Round-trip months and departure mass on one hardware set (N2-R4a, tanks sized once for 0.016 c). Green ≤ 18 months, '
               'amber ≤ 36, red beyond.')


def fig_candidates(CV):
    rows = [c for c in CV['candidates'] if c['dry_added_t'][1] > 0]
    items = [(c['name'][:46], tuple(x['extra_departure_t'] for x in c['coupled']), 'action' if 'R4' in c['name'] else 'muted') for c in rows]
    return bars(items, 'departure added, t (coupled, corrected base)')


def build():
    P = json.loads((R/'phase4.json').read_text())
    RT, RM, Tr, Th, L, ST, D, EC, LG, MI, CV = (P[k] for k in ('reconcile_thermal', 'reconcile_mass', 'transport', 'thermal', 'l2', 'storage', 'district',
                                                               'eclss', 'logistics', 'missions', 'convergence'))
    RB = P['radiation']['bench']; W = P['radiation']['wayfarer']
    out = []
    # 1 reconciliation
    rows = [[E(r['figure']), E(r['origin']), E(r['relation']), f'{r["length_m"]:.1f}' if r.get('length_m') else f'{r.get("holds_W", 0)/1e6:.1f} MW held'] for r in RT['rows']]
    rec = [[r['band'], f'{r["F_hot"]:.4f}', f'{r["waste_W"]/1e6:.1f}', f'{r["geometric_area_m2"]:,.0f}' if r['geometric_area_m2'] else '∞',
            f'{r["length_m"]:.1f}' if r['length_m'] else '∞ (net flux ≤ 0)'] for r in RT['reconciled']]
    mrows = [[E(r['item']), '–' if r['t'] is None else f'{r["t"]:,.1f}', E(r['definition'])] for r in RM['rows']]
    l1 = [[E(r['case']), E(r['condition']), '–' if r['L1_W'] is None else f'{r["L1_W"]/1e6:.1f}'] for r in P['l1_conditional']['rows']]
    cl = P['closure_terms']
    clrows = [[E(a), E(b)]+[E(v[i]) for v in cl['status'].values()] for i, (a, b) in enumerate(cl['terms'])]
    out.append(section('r1', 'DELIVERABLE 1', 'Phase III reconciliation',
        f'<h3>3.1 One radiator relation</h3><p>{E(RT["finding"])}</p>'+table(['Figure', 'Origin', 'Relation', 'Length m'], rows)
        + '<p class="fn">Reconciled configuration: 2 running + 1 warm standby × 3.0 MWe at 550 K, f_space 0.9, 3 % standby heat, margin 1.2.</p>'
        + table(['Band', 'F to hot', 'Waste MW', 'Geometric m²', 'Length m'], rec)
        + f'<h3>3.2 Reference mass</h3><p>{E(RM["finding"])}</p>'+table(['Quantity', 't', 'Definition'], mrows)
        + f'<h3>3.3 L1 reduction is conditional</h3><p>{E(P["l1_conditional"]["finding"])}</p>'+table(['Case', 'Condition', 'L1 MW'], l1)
        + '<h3>3.4 What "closure" means</h3>'+table(['Term', 'Definition']+list(cl['status'].keys()), clrows)
        + f'<h3>3.5 ECLSS</h3><p>{E(EC["reconciliation"])}</p>'))
    # 2-3 radiation
    cases = RB['cases']
    brow = [[E(cases[0]['case']), f'k = {cases[0]["k_calc"]:.5f} ± {cases[0]["sigma"]:.5f}', f'{cases[0]["diff_pcm"]:+.0f} pcm (bench ±100)', ok(cases[0]['within'], 'pass')],
            [E(cases[1]['case']), f'{cases[1]["calc"]:.5f} vs {cases[1]["ref"]:.5f}', f'{100*cases[1]["rel_diff"]:+.2f} %', ok(abs(cases[1]['rel_diff']) < 0.01, 'pass')],
            [E(cases[2]['case']), f'{cases[2]["calc"]:.5f} vs {cases[2]["ref"]:.5f} (no coherent {cases[2]["ref_without_coherent"]:.5f})',
             f'{100*cases[2]["rel_diff"]:+.2f} % / {100*cases[2]["rel_diff_without_coherent"]:+.2f} %', 'explained (Rayleigh not a collision)']]
    levels = [['Installation', ok(True, 'done'), 'OpenMC 0.15.3 (conda-forge, Miniforge) in the cloud container; ENDF/B-VIII.0 NNDC HDF5, 46 files, 673 MB, sha256 manifest'],
              ['Benchmark execution', ok(True, 'done'), 'Godiva k-eigenvalue; uncollided neutron and photon slabs'],
              ['Convergence', ok(True, 'partial'), 'eigenvalue σ 49 pcm; slab tallies < 1 % relative error; deep-penetration points statistics-limited (no variance reduction yet)'],
              ['Applicability to Wayfarer', '<span class="warn">limited</span>', 'surrogate core (no design), 1-D slabs, no blade or structure scatter, no streaming'],
              ['Engineering validation', '<span class="bad">not done</span>', 'needs a 3-D model, a real core, shielding benchmarks (e.g. SINBAD/ICSBEP shielding sets) and independent review']]
    s1 = W['S1']
    out.append(section('r2', 'DELIVERABLE 2', 'Radiation infrastructure assessment',
        '<p>OpenMC runs here. It installs from conda-forge (no pip wheel exists), takes nuclear data from the openmc-data-storage GitHub mirror (the '
        'openmc.org and anl.box.com hosts are blocked by this container\'s network policy) and runs a Godiva benchmark in 5 s on 4 CPUs. Data '
        'and outputs stay out of Git; <code>radiation/fetch_data.py</code> rebuilds the library from a pinned manifest and <code>radiation/README.md</code> '
        'gives the procedure for a workstation or a CI job. Licensing: OpenMC is MIT; ENDF/B-VIII.0 is public (NNDC).</p>'
        + table(['Level', 'Status', 'Evidence'], levels)
        + '<h3>First Wayfarer workflow (TRANSPORT-INFORMED)</h3>'
        + f'<p>S1: a homogenised SP-100-class surrogate (UN 93 %, Li-7, Mo, BeO reflector; not a core design) gives k = {s1["k_eff"]:.3f}, '
          f'{s1["neutrons_leaking_per_fission"]:.2f} neutrons and {s1["photons_leaking_per_fission"]:.2f} photons leaking per fission, mean energies '
          f'{s1["mean_leak_energy_n_eV"]/1e6:.2f} and {s1["mean_leak_energy_g_eV"]/1e6:.2f} MeV. S2 and S3 below.</p>'
        + fig_transmission(W) + fig_tank_layers(D)))
    out.append(section('r3', 'DELIVERABLE 3', 'Benchmarks', table(['Case', 'Result', 'Difference', 'Status'], brow)
        + '<p class="fn">B1 is a published critical benchmark (ICSBEP HEU-MET-FAST-001); B2 verifies the code against the library\'s own total cross '
          'section; B3 checks photon data against NIST XCOM. None of these validates a spacecraft shield.</p>'))
    # 4 heat transport
    hrows = []
    for r in Tr['rows']:
        hrows.append([E(r['name']), tag(r['cls']), t3([x/1e6 for x in r['pump_W']], 1), t3(r['inventory_t']), t3(r['mass_t']),
                      E(r.get('failure', r.get('verdict', '')))])
    ph = Tr['rows'][0]['phases']
    out.append(section('r4', 'DELIVERABLE 4', 'Propulsion heat transport, H1–H5', f'<p>{E(Tr["finding"])}</p>'
        + table(['Candidate', 'Class', 'Pump MW', 'Li inventory t', 'Hardware t', 'Failure / verdict'], hrows) + fig_transport(Tr)
        + f'<p class="fn">Basis: {Tr["per_blade_W"]/1e9:.2f} GW per blade at peak, 162 m hot length, Li at 1800 K (vapour pressure {Tr["li_vapour_pressure_1800K_Pa"]/1e5:.1f} bar: '
          f'pressurised loop), {Tr["accel_max_m_s2"]/9.81:.2f} g peak. Drive-to-root: {E(Tr["separation"]["drive_to_root"])}. Distribution: {E(Tr["separation"]["distribution"])}.</p>'
        + table(['Phase', 'Pumped loops (H1–H3, H5)', 'Vapour trunk (H4)'], [[k, E(ph[k]), E(Tr['rows'][3]['phases'][k])] for k in ('accel', 'braking', 'coast', 'startup', 'postburn')])))
    # 5 radiator variants + 6 thermal ledger
    vrows = [[E(r['surface']), f'{r["F_hot"]:.4f}', f'{r["absorbed_W_m2"]:,.0f}', f'{r["emit_W_m2"]:,.0f}', f'{r["ratio"]:.2f}', ok(r['works_in_burn'], 'works' if r['ratio'] < 0.1 else f'works, −{100*r["ratio"]:.0f} %', 'no')] for r in Th['view_factors']]
    brows = [[f'{r["baffle_R_m"]:.1f}', r['surface'], f'{r["F_hot"]:.5f}', f'{100*r["ratio"]:.1f} %', ok(r['works_in_burn'], 'works', 'no')] for r in Th['baffle_scan']]
    bf = Th['baffle']; al = Th['hot_allowance']
    avail = Th['l2_cooling']
    arows = [[E(k)]+[E(v) for v in vals] for k, vals in avail['options'].items()]
    out.append(section('r5', 'DELIVERABLE 5', 'Radiator variants (isolated, research only)', f'<div class="callout">{E(Th["finding"])}</div>'
        + fig_viewfactor(Th)
        + '<div class="two"><div><img src="cam_issa4_sightlines.jpg" alt="Side view of the review file: the 700 K section in pink aft of the production bulkhead, WARM orange and LOW white ahead of it, green sight lines from the three power units to the He-3 tanks" style="border-radius:8px;border:1px solid var(--line);width:100%;height:auto;display:block"><p class="fn">Review geometry, side view: N2-R4a 700 K section (pink) on the hot-blade forward end, the production bulkhead, WARM and LOW, and the unit-to-tank sight lines (green, inside the shadow cone).</p></div>'
          '<div><img src="cam_issa4_baffle.jpg" alt="Three-quarter view from the bow side: the relocated bulkhead disk (cyan) aft of the production bulkhead and the radiator zone" style="border-radius:8px;border:1px solid var(--line);width:100%;height:auto;display:block"><p class="fn">Three-quarter view: the relocated bulkhead (cyan, review only) aft of the production bulkhead. Workbench, MODEL plus PROTOTYPE layers.</p></div></div>'
        + table(['Surface', 'F to hot', 'Absorbed W/m²', 'Emitted W/m²', 'Ratio', 'In a burn'], vrows)
        + '<h3>Why the bulkhead must reach the blade tips</h3>' + table(['Bulkhead outer R m', 'Section', 'F', 'Absorbed / emitted', 'In a burn'], brows)
        + f'<p>N2-R4a moves the existing bulkhead ({bf["area_m2"]:,.0f} m² per layer, ~{bf["existing_t"]:.1f} t, three layers) aft by the section length: '
          f'{t3(bf["mass_t"])} t for re-support and longer headers. {E(bf["silhouette"])}. {tag(bf["cls"])}</p>'
        + table(['Geometry option']+list(avail['states']), arows)))
    cfails = [[r['state'], r['band'], r['condition'], ok(r['closes'], 'closes', 'fails'), E('; '.join(f'{f["circuit"]} {f["load_W"]/1e6:.2f} > {f["capacity_W"]/1e6:.2f} MW' for f in r['fails']))]
              for r in Th['closure'] if r['band'] != 'low']
    out.append(section('r6', 'DELIVERABLE 6', 'Coupled thermal ledger', '<p>Zones: 1800 K propulsion (hot blades), L1 reject (~900 K, needs its own panel: '
        'no sink in the production geometry), L2 (550–700 K section), WARM/defense (440 K), LOW/cryo (300 K), habitat (ring cold loops), emergency '
        '(refuge storage). Coast closure from the Phase III ledger with a sector lost; burns depend on the bulkhead shadow (deliverable 5).</p>'
        + table(['State', 'Band', 'Condition', 'Result', 'Failing circuits'], cfails)
        + f'<p>Hot allowance, current-drive operating point only (Fiji/Vertex numbers not used): ideal {al["ideal_W"]/1e9:.2f} GW, peak absorbed '
          f'{al["peak_absorbed_W"]/1e9:.2f} GW, {al["per_m_W"]/1e6:.0f} MW per metre. Length available: {al["L_max_no_margin_m"]:.0f} m without margin, '
          f'{al["L_max_with_margin_m"]:.0f} m with the 20 % rule, {al["L_max_budget_m"]:.0f} m against the 10.8 GW budget. '
          f'LOW at the high band with a sector lost needs ~{Th["low_extension"]["added_length_m"]:.0f} m more LOW.</p>'))
    # 7 L2 sizing
    lrows = []
    for r in L['rows']:
        m = r['margins']['EOL']
        lrows.append([f'{r["Pe_W"]/1e6:.2f}', E(r['strategy']), t3([x/1e6 for x in m['immediate_after_loss']], 2), t3([x/1e6 for x in m['one_unit']], 2),
                      t3(list(r['restore_h']), 1), t3(r['mass_t'])])
    dp = L['demand_parts']
    out.append(section('r7', 'DELIVERABLE 7', 'L2 power sizing', f'<p>{E(L["finding"])}</p>'
        + f'<p class="fn">Demand per band (MW): {t3([x/1e6 for x in L["demand_W"]], 2)} = proactive coast state + OPEN planning loads + buffer recharge '
          f'+ standby; auxiliaries {100*dp["aux_frac"]:.0f} %, PMAD {100*dp["pmad"]:.0f} %, EOL {100*dp["eol"]:.0f} %. Optimum rating (two units carry it at EOL): '
          f'{t3([x/1e6 for x in L["optimum_Pe_W"]], 2)} MWe. Strategy D (mission switching) runs C in burns and high-velocity coast and A at low velocity.</p>'
        + fig_l2(L) + table(['MWe', 'Strategy', 'Margin at the trip, EOL MW', 'After restore MW', 'Restore h', 'Mass t (3 units)'], lrows)
        + table(['Reference', 'After one loss, EOL MW'], [[E(r['name']), t3([x/1e6 for x in r['after_one_loss_EOL_W']], 2)] for r in L['references']])))
    # 8 storage
    srows = [[E(r['pattern']), r['band'], f'{r["power_W"]/1e6:.0f}', f'{r["energy_kWh"]:.0f}', r['best'], f'{r["mass_t"]:.1f}', r['limited_by'], f'{r["recharge_W"]/1e6:.2f}']
             for r in ST['patterns'] if r['band'] == 'nominal']
    strow = [[E(s['store']), E(str(s['energy_kWh'])), E(str(s['power_MW'])), E(str(s['mass_t'])), E(s['role']), E(s['note'])] for s in ST['stores']]
    sc = ST['defense_scaling']
    out.append(section('r8', 'DELIVERABLE 8', 'Storage and black start', f'<p>{E(ST["finding"])}</p>'
        + table(['Engagement pattern', 'Band', 'Excess MW', 'Energy kWh', 'Best store', 't', 'Limited by', 'Recharge MW'], srows)
        + table(['Store', 'Energy kWh', 'Power MW', 'Mass t', 'Role', 'Note'], strow)
        + f'<p>Restart R1b: {E(ST["restart"]["sequence_R1b"])}. {E(ST["restart"]["note"])}.</p>'
        + f'<p>Defense scaling provenance: {E(sc["phase3"])}; {E(sc["provenance"])}. Band {E(" / ".join(sc["band"]))}; at 0.008 c the defense '
          f'power is {", ".join(f"{x:.3f}" for x in sc["at_0_008c"])} of the 0.016 c value. {tag("OPEN")}</p>'))
    # 9 district
    out.append(section('r9', 'DELIVERABLE 9', 'Three-unit district', table(['Aspect', 'Research configuration'], [[E(u['item']), E(u['value'])] for u in D['units']])
        + '<p class="fn">Placement and envelopes are the Phase III EPS-G1 bays; one unit per sector. Review geometry only; no permanent installation.</p>'))
    trows = [[f'{r["Pe_W"]/1e6:.1f}', f'{r["side_shield_cm_LiH_after_5cm_W"]:.0f}', f'{r["flux_n_m2_s"]:.2e}', f'{r["he3_W_per_tank_per_unit"]:.2f}', f'{r["wall_W_per_tank_per_unit"]:.2f}'] for r in D['tank_rows']]
    out.append(section('r10', 'DELIVERABLE 10', 'Cryogenic radiation heating', f'<p>{E(D["finding"])}</p>'
        + f'<div class="callout">Correction to Phase III: {E(D["correction"]["note"])} (Phase III: {D["correction"]["phase3_d_m"]:.0f} m, {D["correction"]["phase3_off_axis_deg"]:.0f}°; '
          f'built model: {D["correction"]["actual_d_m"]:.0f} m, ≤ {D["correction"]["actual_off_axis_deg_max"]:.0f}°.)</div>'
        + table(['Layer', 'Neutron share', 'Gamma share', 'Status'], [[E(l['layer']), E(l['neutron']), E(l['gamma']), E(l['status'])] for l in D['layers']])
        + table(['Unit MWe', 'Shield cm on the path', 'n flux at tank /m²s', 'He-3 3 K W per tank per unit', 'Wall W'], trows)
        + '<p class="fn">The last row per rating is the direct path through the 2.4 m shadow shield (treated as LiH; conservative for neutrons). Closure criterion (DR3-07): 3 K deposit from all units ≤ 25 % of the 3 K stage lift (PROTOTYPE allocation). Scatter is OPEN until 3-D transport.</p>'))
    # 11 ECLSS
    ech = list(EC['rows'][0]['checks'].keys())
    erows = [[E(r['option']), str(r['units']), t3(r['mass_t'], 1)]+[ok(r['checks'][k], 'yes', 'no') for k in ech] for r in EC['rows']]
    out.append(section('r11', 'DELIVERABLE 11', 'Modular ECLSS', f'<p>{E(EC["finding"])}</p>' + table(['Option', 'Units', 'Mass t']+[E(k) for k in ech], erows)
        + f'<p class="fn">Transfer: {E(EC["rows"][0]["transfer"])}. Hub unit: {E(EC["rows"][2]["transfer"])}.</p>'))
    # 12 logistics
    lgr = [[E(r['mission']), f'{r["payload_t"]:.1f}', str(r['phase3_count']), str(r['dedicated']), str(r['shared_by_compatibility']), f'{r["tare_t"]:.0f}', f'{r["gross_t"]:.1f}'] for r in LG['rows']]
    out.append(section('r12', 'DELIVERABLE 12', 'Logistics containers', f'<p>{E(LG["finding"])}</p>'
        + table(['Mission', 'Payload t', 'Phase III count', 'Dedicated', 'Shared by compatibility', 'Tare t', 'Gross t'], lgr)
        + f'<p class="fn">{E(LG["container"]["structural"])}. The six-person narrative case stays separate (Phase III narrative).</p>'))
    # 13 missions
    crow = [[f'{c["D_AU"]:.0f}', str(c['slowest_within_36mo'] or '–')]+[f'{x["days_saved"]:.0f} d / +{x["departure_added_t"]:,.0f} t ({x["days_per_100t"]:.1f} d per 100 t)' for x in c['steps']] for c in MI['crossover']]
    out.append(section('r13', 'DELIVERABLE 13', 'Missions, 45–1,000 AU', f'<p>{E(MI["finding"])}</p>' + fig_missions(MI)
        + table(['AU', 'Slowest ≤ 36 mo', '0.004→0.008 c', '0.008→0.012 c', '0.012→0.016 c'], crow)
        + f'<p class="fn">Hardware: N2-R4a (+{MI["hardware_added_t"]:.0f} t dry, incl. the H5 transport upper bound), tankage fixed at {MI["tankage_fixed_t"]:.0f} t for '
          f'{MI["P_max_t"]:,.0f} t maximum propellant; end mass changes only by consumables beyond the 10 t food line. Full table in results/phase4.json.</p>'))
    # 14 mass and closure
    cvr = []
    for c in CV['candidates']:
        cvr.append([E(c['name']), t3(c['dry_added_t']), t3([x['extra_departure_t'] for x in c['coupled']]),
                    t3(c['dry_added_without_transport_t']) if c.get('dry_added_without_transport_t') else '–',
                    E(c['status']['thermal']), E(c['status']['electrical']), E(c['status']['radiation']), E(c['still_valid'])])
    sc_ = [[f'{r["T_K"]:.0f}', f'{r["eta"]:.3f}', f'{r["length_m"]:.1f}', f'{r["hot_capacity_W"]/1e9:.2f}', f'{r["unit_t"]:.0f}'] for r in CV['T_scan']]
    items = next(c for c in CV['candidates'] if c['name'].startswith('N2-R4a'))['items_t']
    out.append(section('r14', 'DELIVERABLE 14', 'Mass and closure', f'<div class="callout">{E(CV["claim_283t"])}</div>' + fig_candidates(CV)
        + table(['Candidate', 'Dry added t', 'Departure added t', 'Dry without H5 transport t', 'Thermal', 'Electrical', 'Radiation', 'Standing'], cvr)
        + '<h3>N2-R4a line items (t)</h3>' + table(['Item', 't'], [[E(k.replace('_', ' ')), t3(v, 1)] for k, v in items.items()])
        + '<h3>L2 rejection temperature</h3>' + table(['T K', 'η', 'Section length m', 'Hot capacity used GW', 'Unit t'], sc_)
        + f'<p class="fn">Corrected base (CIRC-001 coupled): end {CV["base"]["end_t"]:,.0f} t, propellant {CV["base"]["propellant_t"]:,.0f} t, departure '
          f'{CV["base"]["departure_t"]:,.0f} t. 700 K is the study choice: a third shorter than 550 K for ~13 % more unit mass.</p>'))
    # 15-17
    out.append(section('r15', 'DELIVERABLE 15', 'Problem register', table(['ID', 'Severity', 'Problem', 'Consequence'],
        [[p['id'], f'<span class="{"bad" if p["severity"] == "BLOCKER" else ("warn" if p["severity"] == "MAJOR" else "")}">{p["severity"]}</span>', E(p['problem']), E(p['consequence'])] for p in P['problems']])))
    out.append(section('r16', 'DELIVERABLE 16', 'Decision register', table(['ID', 'Decision', 'Recommended'], [[d['id'], E(d['question']), E(d['recommended'])] for d in P['decisions']])))
    out.append(section('r17', 'DELIVERABLE 17', 'Next sequence', '<ol>'+''.join(f'<li>{E(x[3:])}</li>' for x in P['next_sequence'])+'</ol>'))
    return '\n'.join(out)
