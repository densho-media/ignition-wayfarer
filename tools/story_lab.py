"""Wayfarer website, Engineering 2.0: the Engineering Baseline, Weakest Links, Breakthrough Lab and Ship Evolution pages.

tools/story.py calls build() with the record that lab/studies/breakthrough-lab/site.py --json printed (story.py runs it as a separate
process, as it does for every lab entry; this module reads nothing from lab/ itself) and the canon ship numbers. It writes:

  engineering/baseline/          Layer A and Layer B, the reference configurations side by side, the reference inputs, provenance
  engineering/weakest-links/     the ranked bottleneck register, filterable (web/engineering/lab.js), readable without JavaScript
  engineering/breakthrough-lab/  the breakthrough registry and the experimental scenario builder over the precomputed grid
  engineering/evolution/         true-scale envelopes of the calculated configurations, changes and unresolved problems

Every number on these pages is copied from that record. JavaScript only selects among the precomputed cases and redraws the envelope
of a computed case; it never computes a mass or a performance value (web/engineering/lab.js).
"""
import html
import json
import math

import web_identity

REPO = 'https://github.com/densho-media/ignition-wayfarer'
AREAS = [('baseline', 'Engineering Baseline', 'What hard science says: the reference configurations and where they fail.'),
         ('weakest-links', 'Weakest Links', 'The ranked engineering bottlenecks, with the evidence behind each.'),
         ('breakthrough-lab', 'Breakthrough Lab', 'Switch on provisional breakthroughs and see what the calculators return.'),
         ('evolution', 'Ship Evolution', 'How the ship changes, at true scale, as the assumptions change.')]
CMP = ('departure_t', 'propellant_t', 'thrust_MN', 'peak_g', 'burn_years', 'min_round_trip_years', 'pellet_rate_Hz', 'gain', 'stand_off_m',
       'hot_GW', 'warm_GW', 'hot_km2', 'warm_km2', 'wing_tip_radius_m')
LABEL = {'departure_t': ('Departure mass', 't', '{:,.0f}'), 'propellant_t': ('Propellant', 't', '{:,.0f}'),
         'thrust_MN': ('Peak thrust', 'MN', '{:,.2f}'), 'peak_g': ('Peak acceleration', 'g', '{:.4f}'),
         'burn_years': ('Time under thrust', 'years', '{:.2f}'), 'min_round_trip_years': ('Shortest round trip', 'years', '{:.2f}'),
         'pellet_rate_Hz': ('Pulse rate', 'Hz', '{:,.0f}'), 'gain': ('Target gain', '', '{:,.0f}'),
         'stand_off_m': ('Burn stand-off behind the shield', 'm', '{:,.1f}'), 'hot_GW': ('Hot-loop heat', 'GW', '{:,.0f}'),
         'warm_GW': ('Warm-loop heat', 'GW', '{:,.0f}'), 'hot_km2': ('Hot radiator area', 'km²', '{:,.2f}'),
         'warm_km2': ('Warm radiator area', 'km²', '{:,.2f}'), 'wing_tip_radius_m': ('Radiator tip radius', 'km', '{:,.2f}')}
SCALE = {'wing_tip_radius_m': 1e-3}


def esc(s):
    return html.escape(str(s), quote=True)


def num(key, v):
    if not isinstance(v, (int, float)) or isinstance(v, bool) or (isinstance(v, float) and not math.isfinite(v)):
        return '–'
    return LABEL[key][2].format(v * SCALE.get(key, 1.0))


def badge(kind, value, text=None):
    return f'<span class="bt bt-{esc(kind)} bt-{esc(kind)}-{esc(value)}">{esc(text or value)}</span>'


def subnav(active, up):
    items = ''.join(f'<a href="{up}engineering/{k}/"{" aria-current=page" if k == active else ""}>{esc(t)}</a>' for k, t, _ in AREAS)
    return f'<nav class="subnav" aria-label="Engineering 2.0">{items}</nav>'


def src_link(s):
    nature = {'SCIENTIFIC': 'science', 'PROJECT_MODEL': 'Wayfarer model', 'FICTIONAL': 'IGNITION fiction'}[s['nature']]
    title = esc(s['title'])
    inner = f'<a href="{esc(s["url"])}" rel="noopener">{title}</a>' if s.get('url') else title
    return f'<li>{badge("src", s["nature"], nature)} <code>{esc(s["id"])}</code> {inner}</li>'


def principle():
    return '''<ol class="steps">
  <li><strong>Calculate</strong> the ship with hard science as accurately as reasonably possible.</li>
  <li><strong>Find</strong> the engineering constraints that stop the design from working.</li>
  <li><strong>Declare</strong> the smallest, most precisely defined speculative breakthroughs that would remove them.</li>
  <li><strong>Recalculate</strong> their consequences with the same engineering method, and keep the failures visible.</li>
</ol>'''


def teaser(d):
    """The Engineering 2.0 band on the Engineering start page."""
    blocked = sum(1 for w in d['links'] if w['tier'] == 1)
    cases = d['cases']
    closes = sum(1 for c in cases.values() if c['status'] == 'CLOSES')
    computed = sum(1 for c in cases.values() if c['status'] != 'NOT_COMPUTED')
    ref = case(d, named(d, 'SC-REF'))
    cards = ''.join(f'<a class="card" href="{k}/"><span class="kicker">Engineering 2.0</span><strong>{esc(t)}</strong><span>{esc(x)}</span></a>'
                    for k, t, x in AREAS)
    return f'''<section id="e2" class="e2band">
  <h2>Science-grounded speculative engineering</h2>
  <p>We calculate Wayfarer with hard science, find what stops it from working, and allow only the smallest, explicitly declared
    breakthroughs needed to get past those limits. Every breakthrough is recalculated with the same method. Today the scientific
    reference <strong>{esc(d["vocab"]["status"][ref["status"]].lower())}</strong>; {blocked} weakest links are fundamental blockers, and
    {closes} of the {computed} computed breakthrough scenarios close ({len(cases) - computed} more are not computed, by rule).</p>
  <div class="cards">{cards}</div>
</section>'''


def named(d, nid):
    return next(n for n in d['named'] if n['id'] == nid)


def key(d, levels):
    return '|'.join(f'{b}:{levels[b]}' for b in d['order'])


def case(d, n):
    return d['cases'][key(d, n['levels'])]


def status_badge(d, st):
    return badge('st', st, d['vocab']['status'][st])


def levels_text(d, levels):
    by = {b['id']: b for b in d['breakthroughs']}
    on = [f'{b} {next(x["label"] for x in by[b]["levels"] if x["key"] == lv)}' for b, lv in levels.items() if lv != 'L0']
    return '; '.join(on) or 'none: every lever at its scientific reference'


# ------------------------------------------------------------------------------------------------------------- A. Baseline
def baseline_page(d, ship, page, revision, built, out):
    g = d['config']['generations']
    ref_n, ref_free = named(d, 'SC-REF'), named(d, 'SC-REF-FREE')
    ref, reff = case(d, ref_n), case(d, ref_free)
    cp = {c['label']: c for c in d['config']['coupled']}
    def gen(gid, label, what, verdict):
        x = g[gid]
        sm = x['summary']
        if sm.get('departure_t') is None:
            verdict = 'Does not close in T00: ' + (sm.get('reason') or 'not converged')
        return (label, x['status'], what, sm.get('departure_t'), sm.get('peak_g'), sm.get('wing_tip_radius_m'), verdict)

    def cpl(label, what, verdict):
        c = cp[label]
        return (label, c['status'], what, c['departure_t'] if c['status'] == 'CONVERGED' else None, None, None, verdict)

    def scen(label, c, what):
        sm = c.get('summary', {})
        return (label, c['status'], what, sm.get('departure_t'), sm.get('peak_g'), sm.get('wing_tip_radius_m'),
                'Closes' if c['status'] == 'CLOSES' else (c.get('reason') or c.get('inferred') or ''))
    rows = [
        ('Canon model on main', 'APPROVED MODEL', 'The approved 289.5 m ship. Its drive numbers are the canon operating point: requirements, '
         'not a closed drive design.', ship.get('departure_t'), ship.get('peak_g'), None, 'Requirements; the drive that meets them is OPEN'),
        gen('V0', 'FDP-1 / Vertex V0', g['V0']['consistency'], 'Energy-inconsistent target (coupling 1.68 needed)'),
        gen('V3', 'Vertex V3', g['V3']['definition'], 'Conditional on research targets'),
        gen('V4', 'Vertex V4', g['V4']['definition'], 'Conditional on research targets; items unbooked'),
        cpl('coils + launcher + axis A1, rate free', 'T00 gate fixed-point solve: closure-coil hardware, the B-ray launcher and the A1 tilt '
            're-sized on every pass.', 'Converged without the spine; launcher and A1 break at the coupled rates'),
        cpl('full: + spine cantilever 0.2 Hz (T05 basis), rate free', 'The same with the S5N spine sized for a 0.2 Hz cantilever.',
            'Does not converge (loop gain above 1)'),
        *[(f'Gate 2 {r["name"]}', r['status'], r['what'], r['departure_t'] if r['status'] == 'CONVERGED' else None, None, None,
           f'Shadow-cone rim {r["rim_deg"]:.1f} deg (A1 needs 7.5 or less); spine FE estimate {r["fe_Hz"]:.3f} Hz')
          for r in d['config'].get('gate2', []) if r['name'] in ('G0', 'G0-noA1', 'K1', 'T15')],
        gen('V5', 'Vertex V5', d['config']['v5_note'], 'A bound, never a design'),
        scen('Layer A: scientific reference', ref, d['reference']['definition']),
        scen('Layer A without the launcher limit', reff, 'The same reference with targets that always arrive (BT-005 at L2 only).'),
    ]
    trs = ''.join(f'<tr><th scope="row">{esc(a)}</th><td>{badge("cfg", st.split()[0].replace("-", "_"), st)}</td><td>{esc(why)}</td>'
                  f'<td class="num">{num("departure_t", dep)}</td><td class="num">{num("peak_g", pk)}</td>'
                  f'<td class="num">{num("wing_tip_radius_m", tip)}</td><td>{esc(verdict)}</td></tr>'
                  for a, st, why, dep, pk, tip, verdict in rows)
    inputs = ''.join(f'<tr><td><code>{esc(i["path"])}</code></td><td class="num">{esc(json.dumps(i["value"]))}</td>'
                     f'<td>{badge("basis", i["basis"], i["basis"].replace("_", " ").lower())}</td><td>{esc(i["why"])}</td></tr>'
                     for i in d['reference']['input'])
    levers = ''.join(f'<tr><td><code>{esc(b["id"])}</code> {esc(b["name"])}</td><td>{esc(b["levels"][0]["label"])}</td>'
                     f'<td>{badge("ev", b["levels"][0]["evidence"], d["vocab"]["evidence"][b["levels"][0]["evidence"]])}</td></tr>'
                     for b in d['breakthroughs'] if b['computed'])
    fails = ''.join(f'<li><a href="../weakest-links/#{w["id"]}"><code>{w["id"]}</code> {esc(w["name"])}</a>: {esc(w["gap"])}</li>'
                    for w in d['links'] if w['tier'] <= 2)
    prov = d['provenance'] or {}
    imports = ''.join(f'<tr><td>{esc(m["thread"])}: {esc(m["name"])}</td><td><code>{esc(m["branch"])}</code></td>'
                      f'<td><a href="{REPO}/tree/{m["commit"]}" rel="noopener"><code>{m["commit"][:7]}</code></a></td><td class="num">{m["files"]}</td></tr>'
                      for m in d['imports'])
    body = f'''<header><p class="eyebrow">Engineering 2.0 · A</p><h1>Engineering Baseline</h1>
<p class="lead">The scientific reference model: established physics, validated calculations, experimentally supported technology and
  justified extrapolations, with their failures left in. It is not a feasible spacecraft. It shows what present knowledge tells us.</p></header>
{subnav("baseline", "../../")}
<section><h2>The method</h2>{principle()}
<div class="grid2">
  <div class="panel layer-a"><h3>Layer A · Scientific engineering</h3><p>Established laws, validated calculations, supported technology,
    engineering extrapolations, known limitations and failed configurations. Uncertainties stay explicit. A configuration whose equations
    converge is not thereby validated.</p></div>
  <div class="panel layer-b"><h3>Layer B · Speculative engineering</h3><p>The same calculators with declared breakthroughs switched on. Each
    breakthrough names the limitation it addresses, the parameter it changes, what stays unchanged and what it costs. Switching one on
    in the <a href="../breakthrough-lab/">Breakthrough Lab</a> never makes it canon.</p></div>
</div></section>
<section id="configs"><h2>Configurations</h2>
<p>The approved ship, the historical and research generations of the Vertex drive, the coupled results of feasibility gates 1 and 2
  (Gate 2: the reference G0, G0 without A1, and two of the nine variants that hold A1's 7.5 deg cone, all of which diverge) and the
  Layer A reference, side by side. Status labels are the records' own. Masses are departure masses for the four-burn 0.016 c mission.</p>
<div class="scroll" tabindex="0"><table class="configs"><thead><tr><th>Configuration</th><th>Status</th><th>What it is</th><th>Departure (t)</th>
  <th>Peak g</th><th>Radiator tip (km)</th><th>Verdict</th></tr></thead><tbody>{trs}</tbody></table></div>
<p class="note">HISTORICAL_CONDITIONAL: kept as a record, energy-inconsistent under the later compression bound. RESEARCH_TARGET: every
  correction applied, still resting on targets nobody has demonstrated. BOUND: the lightest ship the physics allows in this model.
  CONVERGED means the coupled iteration settled, not that the ship is feasible.</p></section>
<section id="reference"><h2>What the scientific reference assumes</h2>
<p>{esc(d["reference"]["definition"])} Where no lever is declared it uses FDP-1's optimistic engineering tier; the central tier would be heavier.</p>
<h3>Fixed inputs</h3><div class="scroll" tabindex="0"><table><thead><tr><th>Calculator input</th><th>Value</th><th>Basis</th><th>Why</th></tr></thead><tbody>{inputs}</tbody></table></div>
<h3>Lever settings (each breakthrough at level L0)</h3><div class="scroll" tabindex="0"><table><thead><tr><th>Breakthrough lever</th><th>Reference value</th><th>Evidence</th></tr></thead><tbody>{levers}</tbody></table></div>
</section>
<section id="failures"><h2>Known failures</h2><p>The blockers of tiers 1 and 2 of the <a href="../weakest-links/">Weakest Links</a> register:</p><ul class="plain">{fails}</ul></section>
<section id="provenance"><h2>Provenance</h2>
<p>The Vertex research lives on two branches that are not merged into <code>main</code>. Their results reach this site only as versioned,
  read-only imports (<code>lab/studies/breakthrough-lab/imports/</code>, each with a manifest of file hashes). The scenario grid was solved with
  the T00 calculators at <code>{esc((prov.get("t00_commit") or "")[:7])}</code> on {esc(prov.get("computed_utc", ""))}.</p>
<div class="scroll" tabindex="0"><table><thead><tr><th>Import</th><th>Branch</th><th>Commit</th><th>Files</th></tr></thead><tbody>{imports}</tbody></table></div>
<p class="note">{esc(prov.get("method", ""))}</p></section>'''
    out.mkdir(parents=True, exist_ok=True)
    (out / 'index.html').write_text(page('Engineering Baseline · Wayfarer engineering', 'The scientific reference configurations of the Wayfarer '
                                         'drive, what they assume and where they fail.', body, 2, revision, built, head=LAB_HEAD))


LAB_HEAD = '\n<link rel="stylesheet" href="../lab.css">\n<script src="../lab.js" defer></script>'


# ------------------------------------------------------------------------------------------------------------- B. Weakest Links
def link_card(d, w):
    by = {b['id']: b for b in d['breakthroughs']}
    metrics = ''.join(f'<tr><td>{esc(m["label"])}</td><td class="num">{esc(m["text"])} {esc(m.get("unit", ""))}</td>'
                      f'<td><a href="{REPO}/blob/main/lab/studies/breakthrough-lab/imports/{esc(m["file"])}" rel="noopener"><code>{esc(m["file"].split("/")[-1])}</code></a>'
                      f' <code class="ptr">{esc(m["pointer"])}</code></td></tr>' for m in w['metrics'])
    ev = ''.join(src_link(e) + '' for e in w['evidence'])
    deps = ', '.join(f'<a href="#{x}"><code>{x}</code></a>' for x in w['depends_on']) or 'none'
    bts = ', '.join(f'<a href="../breakthrough-lab/#{b}"><code>{b}</code> {esc(by[b]["name"])}</a>' for b in w['breakthroughs']) or 'none declared'
    sysl = ' '.join(f'<a href="../problems/fdp1-requirements/"><code>{s}</code></a>' if s.startswith('P') else f'<code>{esc(s)}</code>' for s in w['systems'])
    q = w['questions']
    qtext = ''.join(f'<li>{"Yes" if q[k] else "No"}: {t}</li>' for k, t in (
        ('blocks_engine', 'would no other change make the engine work if this stays unsolved?'),
        ('non_convergence', 'does it make the coupled mass loop diverge or fail to close?'),
        ('major_penalty', 'does it cost more than about 10 % of departure mass, or a dimension far beyond the frame?'),
        ('local', 'is it confined to one assembly with a known engineering fix?')))
    attrs = (f'data-tier="{w["tier"]}" data-subsystem="{esc(w["subsystem"].split(":")[0])}" data-speculative="{esc(w["speculative"])}" '
             f'data-conventional="{esc(w["conventional"])}" data-text="{esc((w["name"] + " " + w["description"]).lower())}"')
    return f'''<article class="wl topic {(web_identity.topic(w["id"]) or ("",))[0]}" id="{w["id"]}" {attrs}>
<h3><span class="rank">#{w["rank"]}</span> <code>{w["id"]}</code> {esc(w["name"])}</h3>
<p class="chips">{badge("tier", w["tier"], f"Tier {w['tier']}: {w['tier_label']}")} {badge("res", w["resolution"], d["vocab"]["resolution"][w["resolution"]])}
  {badge("conf", w["confidence"], "Confidence " + w["confidence"].lower())} {web_identity.topic_chip(w["id"])} <span class="sub">{esc(w["subsystem"])}</span></p>
<dl class="qa">
  <dt>What is wrong?</dt><dd>{esc(w["description"])}</dd>
  <dt>Why is it a problem?</dt><dd>{esc(w["consequences"])}</dd>
  <dt>How serious is it?</dt><dd>{esc(w["tier_reason"])} {f"{w['dependents']} other link(s) depend on it." if w["dependents"] else ""}</dd>
  <dt>Now / needed / gap</dt><dd><strong>Now:</strong> {esc(w["current"])}<br><strong>Needed:</strong> {esc(w["required"])}<br><strong>Gap:</strong> {esc(w["gap"])}</dd>
  <dt>Conventional engineering?</dt><dd>{badge("conv", w["conventional"], w["conventional"].lower())} {esc(w["candidates"])}</dd>
  <dt>Would a breakthrough help?</dt><dd>{badge("spec", w["speculative"], w["speculative"].replace("_", " ").lower())} {bts}</dd>
</dl>
<details><summary>Numbers, evidence and dependencies</summary>
<div class="scroll" tabindex="0"><table><thead><tr><th>Calculated value</th><th>Value</th><th>Read from</th></tr></thead><tbody>{metrics}</tbody></table></div>
<p><strong>Scientific baseline:</strong> {esc(w["baseline"])}</p>
<p><strong>Uncertainty:</strong> {esc(w["uncertainty"])}</p>
<p><strong>Depends on:</strong> {deps}. <strong>Touches:</strong> {sysl}</p>
<p><strong>Ranking answers:</strong></p><ul class="plain">{qtext}</ul>
<p><strong>Evidence:</strong></p><ul class="plain src">{ev}</ul></details>
</article>'''


def links_page(d, page, revision, built, out):
    subs = sorted({w['subsystem'].split(':')[0] for w in d['links']})
    tiers = ''.join(f'<option value="{t}">Tier {t}: {esc(n)}</option>' for t, n in d['vocab']['tiers'].items() if any(w['tier'] == int(t) for w in d['links']))
    rows = ''.join(f'<tr><td class="num">{w["rank"]}</td><td><a href="#{w["id"]}"><code>{w["id"]}</code> {esc(w["name"])}</a></td>'
                   f'<td>{badge("tier", w["tier"], str(w["tier"]))}</td><td>{web_identity.topic_chip(w["id"])}<br>{esc(w["subsystem"])}</td>'
                   f'<td>{badge("conv", w["conventional"], w["conventional"].lower())}</td><td>{badge("spec", w["speculative"], w["speculative"].replace("_", " ").lower())}</td></tr>'
                   for w in d['links'])
    body = f'''<header><p class="eyebrow">Engineering 2.0 · B</p><h1>Weakest Links</h1>
<p class="lead">Wayfarer's most significant engineering limitations, ranked by what they do to feasibility, not by mass. Every number is
  read from a committed research result; each card says what is wrong, why, how serious it is and what would have to change.</p></header>
{subnav("weakest-links", "../../")}
<section id="method"><h2>How the ranking works</h2>
<p>Four yes/no questions per link; the tier is the first one answered yes. Inside a tier, links with no conventional path come first,
  then links that more other links depend on, then higher confidence. There is no weighted score: a fatal target-physics problem ranks above an oversized radiator because
  fixing the radiator cannot make the engine work.</p>
<ol class="tiers"><li><strong>Fundamental feasibility blocker</strong>: if unsolved, no other change makes the engine work.</li>
<li><strong>Strongly coupled engineering blocker</strong>: it makes the coupled mass loop diverge or fail to close.</li>
<li><strong>Major mass or dimensional penalty</strong>: more than about 10 % of departure mass, or a dimension far beyond the frame.</li>
<li><strong>Local mechanical engineering problem</strong>: one assembly, a known fix.</li><li><strong>Secondary optimisation</strong>.</li></ol></section>
<section id="register"><h2>The register</h2>
<form class="filters" data-filter="wl" aria-label="Filter the register" hidden>
  <label>Tier <select name="tier"><option value="">All</option>{tiers}</select></label>
  <label>System <select name="subsystem"><option value="">All</option>{"".join(f'<option>{esc(s)}</option>' for s in subs)}</select></label>
  <label>Breakthrough needed <select name="speculative"><option value="">Any</option><option value="REQUIRED">required</option>
    <option value="LIKELY_REQUIRED">likely required</option><option value="MAY_HELP">may help</option><option value="NOT_NEEDED">not needed</option></select></label>
  <label>Search <input type="search" name="q" placeholder="e.g. coil"></label>
  <output name="count" aria-live="polite"></output>
</form>
<div class="scroll" tabindex="0"><table class="register-summary"><thead><tr><th>#</th><th>Link</th><th>Tier</th><th>System</th><th>Conventional?</th><th>Breakthrough?</th></tr></thead><tbody>{rows}</tbody></table></div>
<div class="wl-list">{"".join(link_card(d, w) for w in d["links"])}</div>
<p class="note">The FDP-1 problem map's register (<a href="../problems/fdp1-requirements/">P01-P11</a>) remains the record for the canon-scale
  FDP-1 drive; these links are the Vertex-generation bottlenecks from the T00 and T05 feasibility gates.</p></section>'''
    out.mkdir(parents=True, exist_ok=True)
    (out / 'index.html').write_text(page('Weakest Links · Wayfarer engineering', 'The ranked engineering bottlenecks of the Wayfarer drive, with '
                                         'their evidence.', body, 2, revision, built, head=LAB_HEAD))


# ------------------------------------------------------------------------------------------------------------- C. Breakthrough Lab
def bt_card(d, b):
    v = d['vocab']
    lv = ''.join(f'<tr><td><code>{x["key"]}</code></td><td>{esc(x["label"])}</td><td>{badge("ev", x["evidence"], v["evidence"][x["evidence"]])}</td>'
                 f'<td>{"; ".join(f"<code>{esc(p)}</code> = {esc(json.dumps(val))}" for p, val in x["set"].items())}</td></tr>' for x in b['levels'])
    lim = b.get('limit')
    pen = b['penalties']
    refs = ''.join(src_link(s) for s in b['references'])
    wl = ', '.join(f'<a href="../weakest-links/#{w}"><code>{w}</code></a>' for w in b['weakest_links'])
    return f'''<article class="btc topic {(web_identity.topic(b["id"]) or ("",))[0]}" id="{b["id"]}">
<h3><code>{b["id"]}</code> {esc(b["name"])} {web_identity.topic_chip(b["id"])}</h3>
<p class="chips">{badge("lvl", b["level"], "Level " + b["level"] + ": " + b["level_label"])} {badge("ev", b["evidence"], v["evidence"][b["evidence"]])}
  {badge("dev", b["development"], v["development"][b["development"]])} {badge("canon", b["canon"], v["canon"][b["canon"]])}
  {'' if b["computed"] else badge("st", "NOT_COMPUTED", "No calculator lever yet")}</p>
<p>{esc(b["summary"])}</p>
<dl class="qa">
  <dt>Limitation addressed</dt><dd>{esc(b["limitation"])} ({wl})</dd>
  <dt>Speculative assumption</dt><dd>{esc(b["assumption"])}</dd>
  <dt>Changes</dt><dd>{", ".join(f"<code>{esc(m)}</code>" for m in b["modifies"]) or "nothing yet"}</dd>
  <dt>Unchanged</dt><dd>{esc(b["unchanged"])}</dd>
  <dt>Forbidden effects</dt><dd>{esc(b["forbidden"])}</dd>
  <dt>Energy and momentum</dt><dd>{esc(b["energy"])}</dd>
  {f'<dt>Materials (PMDS)</dt><dd>{" ".join(web_identity.material_chip(m) for m in b["materials"])}</dd>' if b["materials"] else ''}
</dl>
<details><summary>Levels, costs, risks, validation, sources</summary>
{f'<div class="scroll" tabindex="0"><table><thead><tr><th>Level</th><th>Setting</th><th>Evidence</th><th>Calculator input</th></tr></thead><tbody>{lv}</tbody></table></div>' if lv else ''}
{f'<p><strong>Validity limit:</strong> <code>{esc(lim["path"])}</code> ≤ {lim["max"]}. {esc(lim["why"])} Beyond it a scenario is OUT OF RANGE, never computed.</p>' if lim else ''}
<p><strong>Allowed effects:</strong> {esc(b["allowed"])}</p>
<p><strong>Existing basis:</strong> {esc(b["basis"])}</p>
<p><strong>Costs.</strong> Power: {esc(pen["power"])} Heat: {esc(pen["heat"])} Mass: {esc(pen["mass"])} Maintenance: {esc(pen["maintenance"])}</p>
<p><strong>Recomputed on every solve:</strong> {esc(", ".join(pen["booked"]) or "nothing")}. <strong>Not computed (open):</strong> {esc("; ".join(pen["unbooked"]) or "none")}</p>
<p><strong>Depends on:</strong> {", ".join(f'<a href="#{x}"><code>{x}</code></a>' for x in b["depends_on"]) or "none"}.
  <strong>Atlas:</strong> {", ".join(f"<code>{esc(a)}</code>" for a in b["atlas"]) or "none"}. <strong>PMDS materials:</strong> {" ".join(web_identity.material_chip(m) for m in b["materials"]) or "none"}</p>
<p><strong>Engineering risks:</strong> {esc(b["risks"])}</p>
<p><strong>Required validation:</strong> {esc(b["validation"])}</p>
<ul class="plain src">{refs}</ul></details>
</article>'''


def lever_fieldset(d, b):
    v = d['vocab']
    opts = ''.join(f'<label class="lv"><input type="radio" name="{b["id"]}" value="{x["key"]}"{" checked" if x["key"] == "L0" else ""}>'
                   f'<span>{esc(x["label"])}</span> {badge("ev", x["evidence"], v["evidence"][x["evidence"]])}</label>' for x in b['levels'])
    lim = b.get('limit')
    custom = ''
    if lim:
        path = lim['path']
        custom = (f'<label class="custom">Other value of <code>{esc(path.split(".")[-1])}</code> '
                  f'<input type="number" step="any" inputmode="decimal" data-bt="{b["id"]}" data-path="{esc(path)}" data-max="{lim["max"]}" '
                  f'aria-describedby="lim-{b["id"]}"></label><small id="lim-{b["id"]}">Limit {lim["max"]}: beyond it the result is out of range. '
                  'A value between table points is not computed: nothing is interpolated.</small>')
    return (f'<fieldset class="lever topic {(web_identity.topic(b["id"]) or ("",))[0]}" data-bt="{b["id"]}"><legend><code>{b["id"]}</code> {esc(b["name"])} '
            f'{badge("lvl", b["level"], "Level " + b["level"])} {web_identity.topic_chip(b["id"])}</legend>{opts}{custom}</fieldset>')


def result_table(d, c, label):
    s = c.get('summary', {})
    rows = ''.join(f'<tr><td>{LABEL[k][0]}</td><td class="num">{num(k, s.get(k))} {LABEL[k][1] if s.get(k) is not None else ""}</td></tr>' for k in CMP)
    why = (f'<p class="note">Calculator: {esc(c["reason"])}' + (f'; the most it reaches is {c["max_a0_g"]:.4f} g' if c.get('max_a0_g') is not None else '')
           + '.</p>') if c.get('reason') else ''
    return f'<div class="panel"><h3>{esc(label)}</h3><p>{status_badge(d, c["status"])}</p>{why}<table>{rows}</table></div>'


def grid_table(d):
    rows = []
    by = {b['id']: b for b in d['breakthroughs']}
    for k, c in d['cases'].items():
        cells = ''.join(f'<td><code>{c["levels"][b]}</code></td>' for b in d['order'])
        s = c.get('summary', {})
        cpl = c.get('coupled', {})
        rows.append(f'<tr><td><a href="#{esc(k)}" data-case="{esc(k)}">{status_badge(d, c["status"])}</a></td>{cells}'
                    f'<td class="num">{num("departure_t", s.get("departure_t"))}</td><td class="num">{num("wing_tip_radius_m", s.get("wing_tip_radius_m"))}</td>'
                    f'<td>{esc(cpl.get("status", ""))} {num("departure_t", cpl.get("summary", {}).get("departure_t")) if cpl.get("summary") else ""}</td></tr>')
    head = ''.join(f'<th title="{esc(by[b]["name"])}">{b}</th>' for b in d['order'])
    return (f'<div class="scroll" tabindex="0"><table class="grid"><thead><tr><th>Status</th>{head}<th>Departure (t)</th><th>Tip (km)</th>'
            f'<th>Coupled check (t)</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def lab_page(d, page, revision, built, out):
    levers = [b for b in d['breakthroughs'] if b['computed']]
    others = [b for b in d['breakthroughs'] if not b['computed']]
    ref = case(d, named(d, 'SC-REF'))
    v4n = named(d, 'SC-V4')
    v4 = case(d, v4n)
    presets = ''.join(f'<a class="preset" href="#{esc(key(d, n["levels"]))}" data-case="{esc(key(d, n["levels"]))}">'
                      f'<strong>{esc(n["name"])}</strong><span>{esc(n["note"])}</span>'
                      f'<span>{status_badge(d, case(d, n)["status"])} Layer {n["layer"]}</span></a>' for n in d['named'])
    mins = ''.join(f'<li><a href="#{esc(m["key"])}" data-case="{esc(m["key"])}">{", ".join(f"<code>{b}</code>" for b in m["enabled"])}</a>: '
                   f'{m["count"]} breakthroughs, {m["fictional"]} fictional and {m["unverified"]} unverified levels, {num("departure_t", m["departure_t"])} t · '
                   f'{esc(levels_text(d, d["cases"][m["key"]]["levels"]))}</li>' for m in d['minimal'])
    repro = ''.join(f'<li><code>{esc(k)}</code> reproduces T00 {esc(r["generation"])}: {num("departure_t", r["computed_departure_t"])} t against '
                    f'{num("departure_t", r["t00_departure_t"])} t, {"match" if r["match"] else "MISMATCH"}</li>' for k, r in d['reproduces'].items())
    data = lab_data(d)
    body = f'''<header><p class="eyebrow">Engineering 2.0 · C</p><h1>Breakthrough Lab</h1>
<p class="lead">Choose provisional breakthroughs and compare what the engineering calculators return with the hard-science reference.
  Every result was computed beforehand by the T00 calculators; this page only looks them up.</p></header>
{subnav("breakthrough-lab", "../../")}
<p class="warn" role="note"><strong>Experimental scenario, not canon.</strong> Switching a breakthrough on here establishes nothing. Canon
  changes only by an owner decision recorded in the registry (<code>canon = APPROVED</code>); today every breakthrough is NON_CANON.</p>
<section id="builder"><h2>Build a scenario</h2>
<div class="presets">{presets}</div>
<form class="builder" data-lab aria-label="Breakthrough scenario">{"".join(lever_fieldset(d, b) for b in levers)}
  {"".join(f'<fieldset class="lever off"><legend><code>{b["id"]}</code> {esc(b["name"])}</legend><p>No calculator lever yet: reported as not computed in every scenario. <a href="#{b["id"]}">Record</a></p></fieldset>' for b in others)}
</form>
<div class="result" aria-live="polite" data-result>
  <div class="grid2">{result_table(d, ref, "Scientific reference (Layer A)")}{result_table(d, v4, "Selected scenario: " + v4n["name"])}</div>
  <noscript><p class="note">Without JavaScript the builder cannot select; every computed case is in the table below.</p></noscript>
</div>
</section>
<section id="minimal"><h2>The smallest breakthrough sets that close</h2>
<p>A closing case is minimal when no other closing case uses the same or lower level of every breakthrough. Sorted by the number of
  fictional assumptions among the chosen levels, then the number of breakthroughs, then mass. This is a set relation over the computed grid, not a score.</p>
<ul class="plain">{mins or "<li>No computed case closes.</li>"}</ul>
<p class="note">Every closing case still carries the unbooked items listed with its breakthroughs, and the coupled check (closure-coil
  hardware and the A1 axis fix) adds mass or fails to converge; the spine, target survival and D-3He ignition remain unresolved in all of them.</p></section>
<section id="grid"><h2>Every computed case</h2>
<p>{len(d["cases"])} cases. Levers {", ".join(f"<code>{b}</code>" for b in d["order"])} at the level shown; <code>L0</code> is the scientific
  reference. Cases with a finite launcher are solved only where the unconstrained case closes (a pulse-rate cap only adds a constraint);
  the others are listed as not computed, never filled. The named scenarios are always solved. The coupled check runs for every closing
  case; a finite launcher enters it as the pulse-rate cap of its own uncoupled solve, held fixed.</p>
<details><summary>Show the full grid</summary>{grid_table(d)}</details>
<ul class="plain">{repro}</ul></section>
<section id="registry"><h2>The breakthrough registry</h2>
<p>Each record is a research candidate. Level (A/B/C) is the shared PMDS and Atlas scale; evidence, development status and canon status
  are separate fields, so a calculated result is never shown as demonstrated and a Level C proposal is never shown as canon.</p>
{"".join(bt_card(d, b) for b in d["breakthroughs"])}</section>
<script type="application/json" id="bt-data">{data}</script>'''
    out.mkdir(parents=True, exist_ok=True)
    (out / 'index.html').write_text(page('Breakthrough Lab · Wayfarer engineering', 'Explore provisional breakthroughs for the Wayfarer drive '
                                         'against the hard-science reference.', body, 2, revision, built, head=LAB_HEAD))


def lab_data(d):
    """The compact record lab.js needs: precomputed cases, lever levels, the breakthrough-to-link relation, vocabularies."""
    bts = [{'id': b['id'], 'name': b['name'], 'level': b['level'], 'evidence': b['evidence'], 'weakest_links': b['weakest_links'],
            'unbooked': b['penalties']['unbooked'], 'computed': b['computed'], 'limit': b.get('limit'),
            'levels': [{'key': x['key'], 'label': x['label'], 'evidence': x['evidence'], 'set': x['set']} for x in b['levels']]}
           for b in d['breakthroughs']]
    links = [{'id': w['id'], 'name': w['name'], 'tier': w['tier'], 'breakthroughs': w['breakthroughs']} for w in d['links']]
    rec = {'order': d['order'], 'cases': d['cases'], 'breakthroughs': bts, 'links': links, 'vocab': d['vocab'],
           'reference_key': key(d, named(d, 'SC-REF')['levels']), 'v4_key': key(d, named(d, 'SC-V4')['levels']),
           'named': [{'id': n['id'], 'name': n['name'], 'key': key(d, n['levels'])} for n in d['named']], 'labels': LABEL, 'cmp': CMP}
    return json.dumps(rec, separators=(',', ':'), default=float).replace('</', '<\\/')


# ------------------------------------------------------------------------------------------------------------- D. Ship Evolution
def envelope_svg(env, ship, scale, label):
    """Side elevation of a calculator envelope (half-plane above the axis), true scale. scale: 'ship' (metres near the hull) or 'span'."""
    if scale == 'ship':
        x0, x1, rmax = -420.0, 460.0, 180.0
    else:
        x0, x1 = -1500.0, 1500.0
        rmax = max(12000.0, (env or {}).get('wing_tip_m', 0) * 1.05)
    W, H = 880.0, 300.0 if scale == 'ship' else 320.0
    sx = W / (x1 - x0)
    sy = sx if scale == 'ship' else (H - 30) / rmax
    X = lambda x: (x - x0) * sx
    Y = lambda r: H - 20 - r * sy
    parts = [f'<line x1="0" y1="{Y(0):.1f}" x2="{W}" y2="{Y(0):.1f}" class="axis"/>']
    # canon hull for scale (from the canon parameters)
    h = ship['hull']
    parts.append(f'<rect class="hull" x="{X(h["x_aft"]):.1f}" y="{Y(h["r"]):.1f}" width="{(h["x_fwd"] - h["x_aft"]) * sx:.1f}" height="{h["r"] * sy:.1f}"/>')
    parts.append(f'<rect class="hull" x="{X(h["ring_x"] - 2):.1f}" y="{Y(h["ring_r"]):.1f}" width="{max(1.5, 6 * sx):.1f}" height="{h["ring_r"] * sy:.1f}"/>')
    if env:
        e = env
        parts.append(f'<rect class="wing" x="{X(e["wing_x_m"][0]):.1f}" y="{Y(min(e["wing_tip_m"], rmax)):.1f}" width="{(e["wing_x_m"][1] - e["wing_x_m"][0]) * sx:.1f}" '
                     f'height="{(min(e["wing_tip_m"], rmax) - 10) * sy:.1f}"><title>radiator wing to r {e["wing_tip_m"] / 1e3:.2f} km</title></rect>')
        parts.append(f'<rect class="shield" x="{X(e["x_shield_aft_m"]):.1f}" y="{Y(e["shield_r_m"]):.1f}" width="{max(1.5, (e["x_shield_fwd_m"] - e["x_shield_aft_m"]) * sx):.1f}" height="{e["shield_r_m"] * sy:.1f}"><title>shadow shield r {e["shield_r_m"]:.1f} m</title></rect>')
        parts.append(f'<rect class="module" x="{X(e["x_shield_fwd_m"]):.1f}" y="{Y(6.5):.1f}" width="{(e["x_module_fwd_m"] - e["x_shield_fwd_m"]) * sx:.1f}" height="{6.5 * sy:.1f}"/>')
        if e['x_bow_m'] > h['x_fwd']:
            parts.append(f'<rect class="stretch" x="{X(h["x_fwd"]):.1f}" y="{Y(h["r"]):.1f}" width="{(e["x_bow_m"] - h["x_fwd"]) * sx:.1f}" height="{h["r"] * sy:.1f}"><title>tank stretch to x {e["x_bow_m"]:.0f} m</title></rect>')
        for L in e['loops']:
            if L['r_m'] <= rmax:
                parts.append(f'<circle class="loop" cx="{X(L["x_m"]):.1f}" cy="{Y(L["r_m"]):.1f}" r="3"><title>{esc(L["name"])} r {L["r_m"]:.0f} m</title></circle>')
        parts.append(f'<circle class="burn" cx="{X(e["x_burn_m"]):.1f}" cy="{Y(0):.1f}" r="4"><title>burn point, {e["stand_off_m"]:.0f} m behind the shield</title></circle>')
    else:
        parts.append(f'<text x="{W / 2:.0f}" y="{H / 2:.0f}" class="none" text-anchor="middle">No configuration: this case does not close, so there is no geometry to draw.</text>')
    bar = 100.0 if scale == 'ship' else 5000.0
    parts.append(f'<g class="bar"><line x1="12" y1="{H - 6}" x2="{12 + bar * sx:.1f}" y2="{H - 6}"/><text x="{16 + bar * sx:.1f}" y="{H - 3}">'
                 f'{"100 m" if scale == "ship" else "5 km along the axis"}</text></g>')
    if scale != 'ship':
        parts.append(f'<text x="{W - 6}" y="14" text-anchor="end" class="ax">radial scale compressed: top = {rmax / 1e3:.1f} km</text>')
    return (f'<svg class="env" viewBox="0 0 {W:.0f} {H:.0f}" role="img" aria-label="{esc(label)}"><title>{esc(label)}</title>{"".join(parts)}</svg>')


def env_of(c):
    e = c.get('envelope')
    if not e:
        return None
    return dict(e, wing_tip_m=c['summary']['wing_tip_radius_m'])


def evolution_page(d, ship, page, revision, built, out):
    ref_n, v4_n = named(d, 'SC-REF'), named(d, 'SC-V4')
    ref, v4 = case(d, ref_n), case(d, v4_n)
    pick = d['minimal'][0]['key'] if d['minimal'] else key(d, v4_n['levels'])
    sel = d['cases'][pick]
    cols = [('Scientific reference', ref), ('Vertex V4 equivalent', v4), ('Smallest closing set', sel)]

    def cell(c, f):
        return num(f, c.get('summary', {}).get(f))
    env_rows = []
    for lbl, getter, unit in (('Ship length (calculator layout)', lambda c: (c.get('envelope') or {}).get('length_m'), 'm'),
                              ('Shadow shield radius', lambda c: (c.get('envelope') or {}).get('shield_r_m'), 'm'),
                              ('Outer nozzle loop radius', lambda c: max((L['r_m'] for L in (c.get('envelope') or {}).get('loops', [])), default=None), 'm'),
                              ('Hardware shadow cone', lambda c: (c.get('envelope') or {}).get('hardware_cone_deg'), 'deg')):
        vals = [getter(c) for _, c in cols]
        env_rows.append(f'<tr><td>{lbl}</td>' + ''.join(f'<td class="num">{"–" if v is None else f"{v:,.1f}"} {unit if v is not None else ""}</td>' for v in vals) + '</tr>')
    rows = ''.join(f'<tr><td>{LABEL[f][0]} ({LABEL[f][1]})</td>' + ''.join(f'<td class="num">{cell(c, f)}</td>' for _, c in cols) + '</tr>'
                   for f in ('departure_t', 'propellant_t', 'pellet_rate_Hz', 'warm_km2', 'hot_km2', 'wing_tip_radius_m', 'stand_off_m'))
    coupled = ''.join(f'<td>{esc(c.get("coupled", {}).get("status", "not run (the case does not close)" if c["status"] != "CLOSES" else "not run"))} '
                      f'{num("departure_t", c.get("coupled", {}).get("summary", {}).get("departure_t")) + " t" if c.get("coupled", {}).get("summary") else ""}</td>' for _, c in cols)
    svgs = ''.join(f'<figure class="figure"><figcaption><strong>{esc(lbl)}</strong> {status_badge(d, c["status"])} · {esc(levels_text(d, c["levels"]))}</figcaption>'
                   f'{envelope_svg(env_of(c), ship, "ship", lbl + " near the hull")}{envelope_svg(env_of(c), ship, "span", lbl + " with the radiator span")}</figure>'
                   for lbl, c in cols)
    body = f'''<header><p class="eyebrow">Engineering 2.0 · D</p><h1>Ship Evolution</h1>
<p class="lead">How the drive end of the ship changes as the engineering assumptions change, drawn at true scale from the calculator's
  own layout of each computed case. These are labelled envelopes, not models: where a case does not close, nothing is drawn.</p></header>
{subnav("evolution", "../../")}
<section id="compare"><h2>Reference, V4 and the smallest closing set</h2>
<div class="scroll" tabindex="0"><table class="evo"><thead><tr><th></th>{"".join(f"<th>{esc(l)}</th>" for l, _ in cols)}</tr></thead><tbody>
<tr><td>Status</td>{"".join(f"<td>{status_badge(d, c['status'])}</td>" for _, c in cols)}</tr>{rows}{"".join(env_rows)}
<tr><td>Coupled check (coils + A1 axis fix)</td>{coupled}</tr></tbody></table></div>
<p class="note">Grey: the approved hull for scale (canon parameters). Dark band: the calculator's shadow shield and equipment module.
  Orange: radiator wings (in the plane of the drawing; real wings are edge-on planes through the axis). Dots: nozzle loops and the burn point.
  The near-hull view is at one scale in both directions; the span view compresses the radial scale.</p>
{svgs}</section>
<section id="pick"><h2>Draw another computed case</h2>
<p>Pick any computed case in the <a href="../breakthrough-lab/">Breakthrough Lab</a>; its envelope is drawn here from the same record.</p>
<form class="builder compact" data-evo aria-label="Choose a case to draw" hidden><label>Case <select name="case"></select></label></form>
<div data-evo-out aria-live="polite"></div></section>
<section id="unresolved"><h2>What no envelope shows</h2><ul class="plain">
<li>The axial plasma leak (<a href="../weakest-links/#WL-002">WL-002</a>): the A1 tilt is analytically promising only while the shadow cone stays at or below about 7.5°.</li>
<li>The spine (<a href="../weakest-links/#WL-006">WL-006</a>): no case books it at an accepted stiffness criterion.</li>
<li>Target survival and ignition (<a href="../weakest-links/#WL-004">WL-004</a>, <a href="../weakest-links/#WL-001">WL-001</a>).</li>
<li>Drawn geometry of V4 and the feasibility-gate layouts exists only in the T05 Blender review files (research branch); the
  <a href="../compare/">3D comparison</a> shows today's ship beside the FDP-1 blockout. It loads a large model and needs WebGL; everything on this page works without it.</li>
</ul></section>
<script type="application/json" id="bt-data">{lab_data(d)}</script>
<script type="application/json" id="ship-data">{json.dumps(ship)}</script>'''
    out.mkdir(parents=True, exist_ok=True)
    (out / 'index.html').write_text(page('Ship Evolution · Wayfarer engineering', 'True-scale envelopes of the Wayfarer drive under the hard-science '
                                         'reference and provisional breakthroughs.', body, 2, revision, built, head=LAB_HEAD))


def build(site, d, ship, page, revision, built):
    """Write the four Engineering 2.0 areas; returns their page paths."""
    eng = site / 'engineering'
    baseline_page(d, ship, page, revision, built, eng / 'baseline')
    links_page(d, page, revision, built, eng / 'weakest-links')
    lab_page(d, page, revision, built, eng / 'breakthrough-lab')
    evolution_page(d, ship, page, revision, built, eng / 'evolution')
    return [f'engineering/{k}/index.html' for k, _, _ in AREAS]
