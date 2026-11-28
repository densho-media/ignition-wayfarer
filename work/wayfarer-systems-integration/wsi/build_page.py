"""WSI Phase I review page (artifact) and the register file: problem register, owner decisions, readiness, SSI-1.2 changes.

    python3 work/wayfarer-systems-integration/wsi/build_page.py     # -> results/wsi.html, results/wsi_register.json
"""
import html
import json

from common import R, J, REFS

E = html.escape


def f0(v):
    return '—' if v is None else f'{v:,.0f}'


def f1(v):
    return '—' if v is None else f'{v:,.1f}'


def f2(v):
    return '—' if v is None else f'{v:,.2f}'


def table(head, rows, cls=''):
    h = ''.join(f'<th>{E(x)}</th>' for x in head)
    b = ''.join('<tr>'+''.join(f'<td>{c}</td>' for c in r)+'</tr>' for r in rows)
    return f'<div class="tw"><table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'


def register(cp2, cp4, rem, mem):
    pref = cp4['preferred'] or {}
    pr = pref.get('reconverged', {})
    problems = [
        ('WSI-P01', 'OPEN', 'Global stability closure: strength-sized structure reaches lambda 0.63 static / 1.02 follower at departure (target 1.95). Closure costs '
         'stiffening mass: Al +313..516 t, CFRP-HM rails +187..260 t (round 1, not yet closed).', 'PSA (closure) + WSI (loop)'),
        ('WSI-P02', 'OPEN', 'I-08 spin resonance: first global mode 0.047 Hz (departure) to 0.072 Hz (end) crosses the 0.068 Hz ring spin during every burn; '
         'closure target f1 >= 0.095 Hz at all states.', 'PSA / owner rule'),
        ('WSI-P03', 'OPEN', 'Mass spiral: each tonne of dry mass costs ~3.9 t of departure; Al stability closure moves the point +6..10 % and must be resized.', 'WSI'),
        ('WSI-P04', 'RESOLVED', 'Hub-cone aft legs crossed the MRU flight lane (members 3091/3095, x 91.2): the two legs beside az 255/285 omitted; mru_violations() = 0.', 'PSA'),
        ('WSI-P05', 'OPEN', 'Hub path capped: the 1.9 m hub bore can only thicken; AL5083 fails (util 1.07), Ti-6Al-4V passes; the stability mode keeps returning '
         'to the hub. Favours the bypass interface if it closes.', 'PSA'),
        ('WSI-P06', 'RESOLVED (rule + area)', f'LOW at the joint point: nominal -103 kW, one loop lost -305 kW. Grow LOW tabs by '
         f'{rem["c14"]["low_growth"]["area_m2"]["one_loop_lost"]:.0f} m2 so one loop lost carries nominal; recovery capped at 100 %.', 'ISSA thermal'),
        ('C-01', 'PARTLY RESOLVED', f'Shutdown bridge vs defense buffer: dedicated {rem["c01"]["dedicated"]["mass_t"]:.1f} t store on the services bus; defense keeps '
         '209 MJ. Pump power at part flow depends on the EM-pump fixed losses (0.3-30 %); the shutdown transient (decay heat, Li freeze) stays OPEN.', 'ISSA + Track R'),
        ('C-11', 'RESOLVED (pending EOS check)', 'He-3 at 3.0 K with the consistent density (61.6, not 58.61 kg/m3) and 8 % ullage allows +0.3 K; bulk hold time '
         'with one head lost ~1 year; destratification pumps per vessel.', 'ISSA cryo'),
        ('C-14', 'RESOLVED', 'One LOW loop lost: cryocoolers capped at 100 %, re-cool at reduced rate; vessel hold times 244 d (H2) to 572 d (D2); no 332 K float.', 'ISSA'),
        ('I-01', 'IN PROGRESS', 'Operating point converged with the PSA structure (this phase); final closure pending.', 'WSI'),
        ('I-02', 'RESOLVED', 'L2 station x 41.0 carried by a module frame (PSA III.0: utilisation 0.81 H).', 'PSA'),
        ('I-03', 'OPEN', 'LOW tab lugs and spar (now with the grown tabs): first mode >= 1 Hz, tip <= 0.30 m.', 'PSA / ISSA'),
        ('I-04', 'OPEN', 'EXT-TA rail lugs EXT-L1..L4 on the aft frames.', 'PSA'),
        ('I-05', 'RESOLVED', f'H6a slides: FE axial span at departure {mem["checks"][-1]["axial_span_mm"]:.0f} mm whole ship, within the slide travel per section.', 'ISSA / PSA'),
        ('I-06 / J-01', 'CLOSED (not adopted)', 'Defense-buffer relocation not needed: the dedicated shutdown store removes the C-01 conflict; yard-only aft route stays.', 'ISSA'),
        ('I-07', 'OPEN (requirement set)', 'TAC 600-800 Hz and EM-pump 50-400 Hz: unit mounts isolated (5-10 Hz mount mode, transmissibility < 4 % at 50 Hz); frame local '
         'modes not tuned.', 'PSA / ISSA'),
        ('I-08', 'OPEN', 'See WSI-P02.', 'PSA / owner'),
        ('J-02', 'CLOSED', 'Concept G screened: no aft location outside the excluded x -70..-20 holds more than ~3 % of the H2 (G-HULL); annular storage between the '
         'HOT blades is not feasible (MW-class 20 K load, blocks HOT view).', 'WSI'),
        ('J-03', 'DONE', 'MRU forward end x 92.0 kept; cone legs adjusted (WSI-P04).', 'ISSA / PSA'),
        ('WSI-P07', 'OPEN', 'Thrust convention: with thrust on the four nozzle pickups (not the 12 ring nodes) the ring-node HM closures drop to 0.72-0.80; '
         'the nozzle-thrust reruns (a43e132) restore lambda 1.95: bypass HM 1,275.9 t FE (+171 t aft cage), hub HM 1,413.5 t; f1 at departure 0.091 / 0.084 Hz '
         'vs 0.095 (I-08 short ~4 %), both stopped at the 16-pass cap. The f1 continuation D_byp_ring_HM_nozf1 (a2d08ee) closes both: 1,284.9 t FE, lambda 1.95-2.01, f1 0.0950 / 0.121 / 0.141 Hz; '
         'reconverged point 13,649 t (+3.3 % over the sizing point, loads not yet re-sized); forward end frame:14/diag:14 still strength-short locally (radius cap). '
         'Original critical strain energy in the spine, tie:03, aft frames and rails. All ring-node lambda (Phase II, round 1) are unconservative screening values. '
         'Puller sensitivity (same thrust at the Brow) is stable to 12: the problem is the compression path (research finding, not a proposal).', 'PSA'),
        ('WSI-P08', 'OPEN', 'Closed-loop TVC: on the nozzle-thrust bypass point (1656bc4) stable at all states with a 0.004 Hz attitude loop and 0.03 Hz sensor roll-off (gain margin x2, delay x2-3); unstable with an aft IMU, 3x delay or damping 0.002 (slow, detectable). Earlier PD loop was only marginally stable (min damping 0.0006, negative at left 0.5/0); aft IMU unstable. A structural '
         'notch filter or IMU near the bending node is a design requirement. Ring spin 2x (0.133 Hz) sits on the second bending pair at left 0.5/0 (1-3 %).', 'PSA / ISSA GNC'),
        ('RAD-R', 'OPEN (Track R)', 'Radiation: independent Track R item; no crew-safety claim is made here.', 'Track R')]
    decisions = [
        ('WSI-D1', 'Structural interface at the rotor bay: hub path (capped, needs Ti) or bypass collar (closes better at left 0, heavier collar).',
         'Recommend bypass (TD-F): the only variant that closes lambda 1.95 and f1 0.095 Hz with nozzle thrust (1,284.9 t FE). It is a habitat-interface change and needs owner approval.'),
        ('WSI-D2', 'Rail material: CFRP-HM (Track R) for the primary longerons, Al-Li frames and Ti hub/pickups.', 'Recommend: saves ~270-350 t structure and ~1 kt '
         'departure against Al at equal lambda; no fictional material needed.'),
        ('WSI-D3', 'Propellant arrangement: keep T-A (stretched farm).', 'Recommend: T-B costs +0.8 kt for modularity; G is not feasible outside the excluded zone.'),
        ('WSI-D4', 'Which profile sizes the ship: 0.016 c maximum (13.2 kt) or a reference profile (0.014 c: 10.5 kt; 0.012 c: 8.4 kt).',
         'Owner choice; 0.016 c stays the maximum reference until decided.'),
        ('WSI-D5', 'I-08: stiffen to f1 >= 0.095 Hz, or an operating rule (spin-down / balance limits in burns).', 'Recommend stiffness if its mass is < 5 %; else the rule.'),
        ('WSI-D6', 'C-11: He-3 at 3.0 K, corrected density, 8 % ullage.', 'Recommend (after an EOS check).'),
        ('WSI-D7', 'C-01: dedicated 2.4 t shutdown store; defense buffer stays whole.', 'Recommend.'),
        ('WSI-D8', 'C-14: LOW tab growth (~350 m2) + 100 % recovery cap with one loop lost.', 'Recommend.')]
    ssi12 = ['Farm vessels, cryo stations and the Brow translation follow the WSI farm stretch (cg and masses from the WSI tanks block)',
             'Hub cone: the two aft legs beside az 255/285 omitted; MRU rail forward end stays x 92.0 (mru_violations = 0)',
             'Hub path material Ti-6Al-4V (AL5083 fails at 22 MN)', 'Primary longerons CFRP-HM (pending WSI-D2); frames Al; pickups and thrust ring Ti',
             'New item: dedicated shutdown store on the services bus x -92..-80 (LOW cold plate, cell limit 330 K)', 'LOW tabs grown ~350 m2 (lugs I-03 re-checked)',
             'Structural requirement f1 >= 0.095 Hz at all depletion states (I-08) next to lambda >= 1.95',
             'He-3 vessels: ullage 8 %, density 61.6 kg/m3 at 3.0 K; destratification pump per He-3 vessel']
    readiness = [('Shared configuration (WSI-0.1, one authority, regenerates)', 'READY'), ('Coupled convergence (numerical)', 'READY'),
                 ('Physical satisfaction: stability + I-08', 'NOT YET (closure runs)'), ('Propellant arrangement', 'READY (T-A)'),
                 ('Integrated 3D model and checks', 'READY (CP3 file)'), ('Thermal / electrical at the joint point', 'READY with WSI-D7/D8'),
                 ('Shutdown transient (C-01)', 'OPEN'), ('Radiation / crew dose', 'OPEN (Track R)'), ('Canon / Drive / production', 'UNCHANGED (not authorised)')]
    return dict(problems=problems, decisions=decisions, ssi_1_2=ssi12, readiness=readiness)


def main():
    cfg = J(R/'wsi_config.json'); cp1 = J(R/'wsi_cp1.json'); cp2 = J(R/'wsi_cp2.json'); cp4 = J(R/'wsi_cp4.json'); rem = J(R/'wsi_remaining.json')
    mem = J(R/'wsi_members.json'); reg = register(cp2, cp4, rem, mem)
    (R/'wsi_register.json').write_text(json.dumps(reg, indent=1))
    pref = cp4['preferred']; pr = pref['reconverged'] if pref else {}
    sp = cp1['starting_points']
    hist_rows = [('Production main (approved)', '1,670 dry + propellant', '289.5', '150 (line)', '—'),
                 ('ISSA C1.0 (8b30b71 parent)', '8,655', '310.2', '150 (line)', '—')]
    hist_rows += [(E(s['name']), f0(s['departure_t']), f1(s['ship_length_m']), f0(s['structure_t']), f2(s['a_end_g'])) for s in sp]
    for c in cp4['candidates']:
        hist_rows.append((f'WSI closure round 1: {E(c["tag"])}', f0(c['departure_t']), f1(c['ship_length_m']), f0(c['structure_total_t']), f2(c['a_end_g'])))
    td = []
    for k in ('A', 'B', 'D', 'E', 'F'):
        try:
            d = J(f'{R.parents[1]}/primary-structural-architecture/results/p3_runs/H_hub_TD-{k}_full_wsi.json')
        except Exception:  # noqa: BLE001
            continue
        st = {(s['left'], s['case']): s for s in d['stability']}
        cell = lambda l: ' / '.join(f2((st.get((l, c)) or {}).get('lam')) for c in ('static', 'follower'))
        td.append((f'TD-{k}', f0(d['structure_t']), f0(d.get('deck_t')), cell(1.0), cell(0.5), cell(0.0)))
    clo = [(E(c['tag']), f0(c['strength_t']), f0(c['stiffening_t']), f0(c['structure_total_t']), f2(c['lam_min']), f'{(c["f1_min_Hz"] or 0):.3f}',
            'yes' if c['closed'] else 'no', f0(c['departure_t'])) for c in cp4['candidates']]
    mats = [(m['id'], m['track'], f0(m['rho']), f0(m['E_GPa']), f0(m['Fcy_MPa']), f1(m['specific_modulus_MJ_kg']), f2(m['rail_mass_for_AL_EI']), E(str(m['alpha_ppm_K'])),
             E(m['creep']), E(str(m['joint_efficiency'])), E(m['radiation'])) for m in cp2['materials']]
    gc = [(m['material'], m['track'], f0(m['rail_t']), f0(m['departure_t']), f2(m['rom_fixed_lambda']['lam'])) for m in cp2['global_closure']['options']]
    props = [(E(c['id']), f0(c['departure_t']), f1(c.get('ship_length_m')), f1(c['cg_x']), f'{c["I_pitch"]:.2e}', f2(c['rom_lambda']['0.0']), f2(c['rom_lambda']['1.0']),
              f0(c.get('shell_area_m2')), f0(c.get('cryo_input_kW'))) for c in cp2['propellant']['candidates']]
    gs = [(E(g['id']), E(g['what']), E(g['verdict'])) for g in cp2['propellant']['g_screens']]
    pmax = cp2['profiles'][0]
    prof = []
    for p in cp2['profiles']:
        Rn = p['departure_t']/p['end_t']; op_prop = pmax['end_t']*(Rn-1)
        prof.append((E(p['id']), f'{p["v_c"]:.3f} c', f0(p['departure_t']), f0(p['propellant_t']), f1(p['ship_length_m']), f1(p['burn_days_each']),
                     f2(p['cruise_time_ratio']), f0(pmax['end_t']+op_prop)))
    conv = [(h['it'], f0(h['structure_t']), f0(h['departure_t']), f0(h['propellant_t']), f1(h['ship_m'])) for h in pr.get('history', [])]
    led = [(E(r['item']), f1(r['t']), E(r['owner']), E(r['cat'])) for r in (pref['ledger']['rows'] if pref else [])]
    c11 = [(E(o['id']), f1(o['rho_kg_m3']), f2(o['beta_per_K']), f'{100*o["ullage"]:.1f} %', f2(o['allowed_warm_K']), f0(o['cooler_input_3K_W']/1e3),
            f0(o['hold_days_one_head_lost'])) for o in rem['c11']['options']]
    c01 = [(E(r['model']), f2(r['part_flow_power_W']/1e6), f0(r['bridge_J']/1e6), 'yes' if r['closes'] else 'no') for r in rem['c01']['cases']]
    low = [(E(r['case']), f0(r['load_W']/1e3), f0(r['capacity_W']/1e3), f0(r['margin_W']/1e3)) for r in rem['c14']['low_cases']['rows']]
    chk = [(E(c['check']), E(str(c.get('item', c.get('member', '')))), E(c['verdict'])) for c in mem['checks']]
    dfl = mem['checks'][-1]
    probs = [(E(a), E(b), E(c), E(d)) for a, b, c, d in reg['problems']]
    decs = [(E(a), E(b), E(c)) for a, b, c in reg['decisions']]
    rdy = [(E(a), E(b)) for a, b in reg['readiness']]
    imgs = [('cam_wsi_wsi_01_complete_complete.jpg', 'Complete joint ship (WSI-0.1): PSA structure, ISSA machinery, stretched farm, translated Brow'),
            ('cam_wsi_wsi_03_primary_structure_aft.jpg', 'Aft thrust structure: thrust ring, transition, rails, frames, SSI mounts'),
            ('cam_wsi_wsi_15_section_longitudinal_long.jpg', 'Longitudinal half-section, load paths: red compression, blue tension'),
            ('cam_wsi_wsi_13_research_alternatives_aft.jpg', 'Research alternatives: G-HULL (blue ghost) and the rejected G-ANNULAR sectors (red)')]
    fig = ''.join(f'<figure><img src="{i}" alt="{E(c)}" loading="lazy"><figcaption>{E(c)}</figcaption></figure>' for i, c in imgs)
    head_kpi = [('Joint departure (S-COMB)', f'{sp[2]["departure_t"]:,.0f} t'), ('Ship length', f'{sp[2]["ship_length_m"]:.1f} m'),
                ('Stability, nozzle thrust (bypass HM)', 'λ 1.95, f1 0.095 Hz: closed (end fitting open)'), ('Lead closure (round 1)', f'{pref["tag"] if pref else "—"}')]
    kpi = ''.join(f'<div class="k"><span>{E(a)}</span><b>{E(b)}</b></div>' for a, b in head_kpi)
    page = f'''<title>Wayfarer Systems Integration</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400;600&display=swap">
<style>
:root{{--bg:#f6f5f1;--fg:#1d1f22;--mut:#5d6168;--line:#d9d6cc;--card:#ffffff;--acc:#b4532a;--ok:#2f7a4a;--warn:#a0661a;--bad:#a8322a}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#14161a;--fg:#e8e6e0;--mut:#9aa0a8;--line:#2c3038;--card:#1b1e23;--acc:#e08a5a;--ok:#6cc08a;--warn:#e0a85a;--bad:#e07a6a;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#14161a;--fg:#e8e6e0;--mut:#9aa0a8;--line:#2c3038;--card:#1b1e23;--acc:#e08a5a;--ok:#6cc08a;--warn:#e0a85a;--bad:#e07a6a;color-scheme:dark}}
body{{background:var(--bg);color:var(--fg);font:15px/1.55 "IBM Plex Sans",system-ui,sans-serif;padding-block:24px 64px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}}
main{{max-width:1080px;margin:0 auto;display:flex;flex-direction:column;gap:28px}}
h1{{font-size:1.9rem;margin:0;text-wrap:balance}} h2{{font-size:1.2rem;margin:0 0 8px;border-bottom:2px solid var(--acc);padding-bottom:4px;text-wrap:balance}}
.eyebrow{{font:600 .75rem "IBM Plex Mono",monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--acc)}}
p{{margin:.4em 0;max-width:70ch}} .mut{{color:var(--mut);font-size:.9rem}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}}
.k{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;display:flex;flex-direction:column;gap:2px;min-width:0}}
.k span{{font-size:.8rem;color:var(--mut)}} .k b{{font:600 1.15rem "IBM Plex Mono",monospace}}
.tw{{overflow-x:auto;border:1px solid var(--line);border-radius:8px;background:var(--card)}}
table{{border-collapse:collapse;width:100%;font-size:.85rem}} th,td{{padding:6px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
th{{font:600 .72rem "IBM Plex Mono",monospace;letter-spacing:.04em;text-transform:uppercase;color:var(--mut);white-space:nowrap}}
td{{font-variant-numeric:tabular-nums}} tbody tr:last-child td{{border-bottom:0}}
.figs{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}} figure{{margin:0;min-width:0}} figure img{{width:100%;border-radius:6px;display:block}}
figcaption{{font-size:.8rem;color:var(--mut);margin-top:4px}}
details{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px}} summary{{cursor:pointer;font-weight:600}}
nav{{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:.85rem}} nav a{{color:var(--acc)}}
code{{font-family:"IBM Plex Mono",monospace;font-size:.85em;overflow-wrap:anywhere}}
</style>
<main>
<header><div class="eyebrow">WSI Phase I · joint ISSA–PSA · Track F working configuration · noncanon</div>
<h1>Wayfarer Systems Integration</h1>
<p>One authoritative joint configuration (WSI-0.1) now drives both the ISSA machinery and the PSA primary structure. The coupled loop converges numerically; physical closure is not yet reached, because the structure must be stiffened from λ 0.63 to 1.95 and lifted above the 0.068 Hz ring spin, and every tonne of that costs about 3.9 t at departure. Track R high-modulus CFRP rails carry the closure without fictional materials.</p>
<p class="mut">Branch <code>claude/cloud/wayfarer-systems-integration</code> · ISSA {REFS["issa"]} · PSA {REFS["psa_phase2"]}/{REFS["psa_phase3"]}+ · production main {REFS["main"]} unchanged · review file <code>REVIEW_WSI_CP3.blend</code></p></header>
<div class="kpis">{kpi}</div>
<nav><a href="#s1">Config</a><a href="#s2">Starting points</a><a href="#s3">Convergence</a><a href="#s4">Propellant</a><a href="#s5">Structure</a><a href="#s6">Materials</a><a href="#s7">Ledger</a><a href="#s8">Stability</a><a href="#s9">SSI-1.2</a><a href="#s10">Thermal & electrical</a><a href="#s11">3D model</a><a href="#s14">Profiles</a><a href="#s15">Problems</a><a href="#s16">Decisions</a><a href="#s17">Readiness</a></nav>
<section class="figs">{fig}</section>
<section id="s1"><h2>1 · Shared configuration</h2><p><code>results/wsi_config.json</code> ({E(cfg["id"])}) holds coordinates, dimensions, topology (PSA H, six paired rails, stationary hub), materials, propellant and the 13 T-A vessels, SSI-1.1 equipment and mounts, load cases, thermal interfaces, utility routes, maintenance envelopes, keep-outs and technology dependencies, each once. Both teams read it; PSA's <code>wsi_bodies.py</code> reproduces 11,989.1 t without structure exactly.</p></section>
<section id="s2"><h2>2 · Starting points and 14 · historical vs integrated</h2>{table(['Point', 'Departure t', 'Length m', 'Structure t', 'End accel. g'], hist_rows)}
<p class="mut">The combined point adds 19 t over C1.1's one-pass 13,193 t because cryo and radiators are re-iterated for the longer farm. The ledger closes to the departure once the 150 t line and the 329.5 t production tankage rows leave.</p></section>
<section id="s3"><h2>3 · Convergence history</h2><p>Numerical convergence is reached in a few iterations. It is not physical satisfaction: no closure run yet meets λ ≥ 1.95 and f1 ≥ 0.095 Hz. Each tonne of dry mass costs about 3.9 t of departure through propellant, tankage, cryo and radiators.</p>
{table(['Iteration', 'Structure t', 'Departure t', 'Propellant t', 'Ship m'], conv)}
<p class="mut">Preferred round-1 closure {E(pref["tag"]) if pref else ""}: reconverged departure {f0(pr.get("departure_t"))} t ({f1(pr.get("shift_vs_sizing_point_pct"))} % against the S-COMB sizing point).</p></section>
<section id="s4"><h2>4 · Propellant distribution trade</h2>{table(['Candidate', 'Departure t', 'Length m', 'CG x m', 'I pitch kg m²', 'ROM λ fixed', 'ROM λ follower', 'Shell m²', 'Cryo kW'], props)}
{table(['Concept G option', 'Where', 'Verdict'], gs)}<p>T-A stays the preferred arrangement. T-B adds 0.8 kt for its modularity. Concept G can only help where the owner excluded it (x −70..−20, +15 % λ in PSA's FE). Elsewhere it is either negligible (3 % of the H2 inside the aft hull) or not feasible.</p></section>
<section id="s5"><h2>5 · Structural comparison (PSA FE on S-COMB)</h2>{table(['Deck', 'PSA t', 'Deck t', 'λ left 1 (static / follower)', 'λ left 0.5', 'λ left 0'], td)}
<h3>Closure runs (round 1, λ only, 10 passes)</h3>{table(['Run', 'Strength t', 'Stiffening t', 'Total t', 'min λ', 'min f1 Hz', 'Closed', 'Reconverged departure t'], clo)}
<p class="mut">ROM (planar beam, frequency-matched to the FE 0.0956 Hz): the global beam mode gives 1.08 fixed-direction and 3.93 follower. The FE critical modes are local (farm walls and deck at departure, the aft thrust structure at end of burn), and they govern.</p></section>
<section id="s6"><h2>6 · Structural materials (WSI-D)</h2>{table(['Material', 'Track', 'ρ', 'E GPa', 'Fc MPa', 'E/ρ MJ/kg', 'Rail mass for Al EI', 'α ppm/K', 'Creep', 'Joint eff.', 'Radiation'], mats)}
{table(['Rail material (global EI ×1.8)', 'Track', 'Rails t', 'Departure t', 'ROM λ fixed'], gc)}
<p>The hot-loop composite properties (FT-01, 100 MPa at 2,000 K) are not reused for cold structure. FT-10 (CNT composite) is registered as a sensitivity only, and the closure path uses Track R CFRP-HM.</p></section>
<section id="s7"><h2>7 · Integrated ledger ({E(pref["tag"]) if pref else ""}, reconverged)</h2><details><summary>{E(pref["ledger"]["check"]) if pref else ""}: {len(led)} rows, one owner each</summary>{table(['Item', 't', 'Owner', 'Category'], led)}</details></section>
<section id="s8"><h2>8 · Load cases and stability</h2><p>Loads are thrust-bounded (PSA-D01): limit ×1.4 ultimate, with 1.5 g as a separate envelope. λ is a multiple of the operating thrust of 21.77 MN, and the target is 1.95 (1.87 on limit thrust). New closure criterion I-08: f1 ≥ 0.095 Hz at every depletion state (ring spin 0.068 Hz).</p></section>
<section id="s9"><h2>9 · SSI-1.2 changes</h2><ul>{''.join(f"<li>{E(x)}</li>" for x in reg["ssi_1_2"])}</ul></section>
<section id="s10"><h2>10 · Thermal and electrical ledgers (C-01, C-11, C-14)</h2>
<h3>C-14 · LOW at the joint point (320 K)</h3>{table(['Case', 'Load kW', 'Capacity kW', 'Margin kW'], low)}<p>LOW must grow about {rem["c14"]["low_growth"]["area_m2"]["one_loop_lost"]:.0f} m² (about 1.8 t) so that one lost loop still carries nominal load. Re-cool is capped at 100 % and no 332 K float is allowed. Vessel hold times are months.</p>
<h3>C-01 · Shutdown bridge after an L1 pickup fault</h3>{table(['EM-pump model', 'Part-flow power MW', 'Bridge MJ', 'Steady surplus holds'], c01)}<p>{E(rem["c01"]["dedicated"]["verdict"])}. {E(rem["c01"]["flow_vs_power"])}. The transient stays OPEN.</p>
<h3>C-11 · He-3 storage</h3>{table(['Option', 'ρ kg/m³', 'β /K', 'Ullage', 'Allowed warm K', '3 K-stage input kW', 'Hold d (head lost)'], c11)}<p>{E(rem["c11"]["recommendation"])}</p></section>
<section id="s11"><h2>11–13 · Integrated 3D model, views and sections</h2><p><code>REVIEW_WSI_CP3.blend</code> has 16 view layers: complete, exterior, primary structure, load paths, ISSA machinery, propellant, thermal, electrical, habitats, logistics and maintenance, structural interfaces, clearance envelopes, research alternatives, fictional reference, and longitudinal and transverse sections. Everything is regenerated from the JSON files; production parts that are replaced are hidden, not deleted.</p>
{table(['Check', 'Item', 'Verdict'], chk)}<p class="mut">Departure deflection: {dfl["max_radial_mm"]:.1f} mm radial (rule 50 mm), {dfl["max_lateral_mm"]:.1f} mm lateral, {dfl["axial_span_mm"]:.0f} mm axial (taken by the slides). The two hub-cone clashes were fixed by PSA after this check.</p></section>
<section id="s14"><h2>WSI-E · Mission profiles</h2>{table(['Profile', 'Cruise', 'Departure t (ship sized for it)', 'Propellant t', 'Length m', 'Burn d each', 'Cruise time ×', 'Departure t (0.016 c ship flown at it)'], prof)}
<p class="mut">These use strength-sized structure; the stability closure adds the same family of increments. Lower velocity is an operational trade: the maximum ship flown slower simply loads less propellant (last column).</p></section>
<section id="s15"><h2>15 · Problem register</h2>{table(['Id', 'State', 'What', 'Owner'], probs)}</section>
<section id="s16"><h2>16 · Owner decisions</h2>{table(['Id', 'Question', 'Recommendation'], decs)}</section>
<section id="s17"><h2>17 · Readiness</h2>{table(['Area', 'State'], rdy)}</section>
</main>'''
    (R/'wsi.html').write_text(page)
    print('page', len(page))


if __name__ == '__main__':
    main()
