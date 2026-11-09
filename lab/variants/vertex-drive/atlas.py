"""Vertex Drive Technology Atlas: load, validate and render the registry.

  python3 lab/variants/vertex-drive/atlas.py validate     # exit 1 on any error
  python3 lab/variants/vertex-drive/atlas.py render       # validate, then write ATLAS.md, READINESS.md, figures/dependency_map.svg

Lab tool (AGENTS.md "Where things go"): nothing in src/, tests/, tools/, godot/, web/ or CI imports it. It reads the PMDS catalogue,
the PMDS purposes and the functional colour palette read-only to check references; it never writes outside lab/variants/vertex-drive/.
The registry (registry/*.toml) is the source; ATLAS.md and READINESS.md are generated from it and must not be edited by hand.
"""
import json
import re
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REG = HERE / 'registry'
RESULTS = HERE / 'results' / 'convergence.json'

CREDIBILITY = {'ESTABLISHED': 'A', 'PLAUSIBLE_FUTURE': 'B', 'FICTIONAL_BREAKTHROUGH': 'C'}
VERDICT = {'IMPOSSIBLE': 'Physically impossible', 'POSSIBLE_NOT_PRACTICAL': 'Possible but not practical',
           'PLAUSIBLE_FUTURE': 'Plausible future engineering', 'FICTIONAL_DEPENDENT': 'Dependent on a defined fictional breakthrough',
           'UNRESOLVED': 'Unresolved'}
RESEARCH = {'PROPOSED', 'UNDER_INVESTIGATION', 'SUPPORTED', 'CONTRADICTED', 'PARKED', 'RETIRED'}
CANON = {'NON_CANON', 'CANDIDATE', 'APPROVED'}
GEOM_STATUS = {'ENGINEERING_SUPPORTED': 'Engineering-supported', 'PARAMETRIC_PLACEHOLDER': 'Parametric placeholder',
               'CONCEPTUAL_ILLUSTRATION': 'Conceptual illustration', 'NONE': 'No geometry'}
REPRESENTATION = {'HARDWARE', 'VISUALIZATION', 'MIXED', 'NONE'}
CLAIM_BASIS = {'PUBLISHED', 'MODEL', 'ASSUMPTION', 'TARGET'}
LINK_KINDS = {'enables', 'improves', 'worsens', 'conflicts', 'shares'}
DECISION_TYPES = {'TECHNICAL_CONCLUSION', 'OWNER_APPROVAL_CANON', 'OWNER_APPROVAL_EXPERIMENT'}
DECISION_STATES = {'OPEN', 'DECIDED'}
SOURCE_KINDS = {'journal', 'conference', 'report', 'press', 'book', 'dataset', 'model', 'canon', 'patent', 'catalogue', 'lecture'}
GEN_STATUS = {'HISTORICAL_CONDITIONAL', 'RESEARCH_TARGET', 'BOUND'}
HISTORICAL = ['V0', 'V1', 'V2']                     # the 2026-11-08 generations: kept, never overwritten (T00 Phase 4)
VERIFICATION = {'PRIMARY_VERIFIED', 'SECONDARY_VERIFIED', 'TRANSCRIBED', 'UNVERIFIED'}   # PMDS evidence states
PRIORITY_WEIGHTS = {'feasibility': 3, 'credibility': 2, 'independence': 1, 'mass_thermal': 2, 'unlock': 2, 'design_3d': 1}

REQUIRED = ['id', 'name', 'kind', 'workstream', 'purpose', 'principle', 'ancestry', 'ancestry_note', 'limitations', 'breakthrough',
            'depends_on', 'materials', 'purposes', 'inputs', 'outputs', 'penalties', 'criteria', 'credibility', 'physics_verdict',
            'research_status', 'canon_status', 'prior_finding', 'evidence', 'uncertainties', 'next', 'stages', 'questions', 'geometry',
            'priority']
STAGES = ['present', 'advanced', 'wayfarer_era']
QUESTIONS = ['a', 'b', 'c']
GEOMETRY = ['components', 'envelope', 'location', 'connections', 'loads', 'radiation', 'thermal', 'maintenance', 'purposes', 'colour',
            'representation', 'status']
ID_RE = re.compile(r'^VTX-0[1-8][A-Z]?$')
SOURCE_REQUIRED = ['title', 'authors', 'date', 'locator', 'kind', 'finding', 'limits', 'relation', 'verification', 'checked']


def _toml(name):
    with open(REG / name, 'rb') as f:
        return tomllib.load(f)


def load():
    return {'technologies': _toml('technologies.toml').get('technology', []), 'sources': _toml('sources.toml'),
            'links': _toml('links.toml').get('link', []), 'generations': _toml('generations.toml').get('generation', []),
            'decisions': _toml('decisions.toml').get('decision', []),
            'results': json.loads(RESULTS.read_text()) if RESULTS.exists() else None}


def pmds_ids():
    with open(ROOT / 'data/materials/catalogue.toml', 'rb') as f:
        mats = set(tomllib.load(f).get('material', {}))
    with open(ROOT / 'data/materials/purposes.toml', 'rb') as f:
        purps = set(tomllib.load(f).get('purpose', {}))
    text = (ROOT / 'src/wayfarer/functional_colors.py').read_text()
    block = text.split('PALETTE = {', 1)[1].split('\n}', 1)[0]
    colours = set(re.findall(r"^\s+'([A-Z_0-9]+)':", block, re.M))
    return mats, purps, colours


def result_cases(results):
    if not results:
        return None
    return set(results.get('cases', {})) | set(results.get('generations', {}))


def validate(A, pmds=None):
    """Return a list of error strings; empty means the registry is consistent."""
    errs = []
    mats, purps, colours = pmds or pmds_ids()
    T = A['technologies']; S = A['sources']
    ids = [t.get('id') for t in T]
    seen = set()
    for i in ids:
        if i in seen:
            errs.append(f'duplicate technology id {i}')
        seen.add(i)
    byid = {t.get('id'): t for t in T}
    workstreams = {t['id'] for t in T if t.get('kind') == 'workstream'}
    cases = result_cases(A['results'])
    units = {}

    def src_ok(where, s):
        if s.startswith('case:'):
            if cases is not None and s[5:] not in cases:
                errs.append(f'{where}: case {s[5:]} not in results/convergence.json')
        elif s not in S:
            errs.append(f'{where}: unknown source {s}')

    for t in T:
        tid = t.get('id', '?')
        for k in REQUIRED:
            if k not in t or t[k] in ('', None):
                errs.append(f'{tid}: missing attribute {k}')
        if not ID_RE.match(str(tid)):
            errs.append(f'{tid}: id does not match VTX-0n or VTX-0nX')
        if t.get('kind') not in ('workstream', 'technology'):
            errs.append(f'{tid}: kind must be workstream or technology')
        if t.get('kind') == 'workstream' and t.get('workstream') != tid:
            errs.append(f'{tid}: a workstream must name itself as workstream')
        if t.get('kind') == 'technology' and str(tid)[:6] != t.get('workstream'):
            errs.append(f'{tid}: workstream {t.get("workstream")} does not match the id')
        if t.get('credibility') not in CREDIBILITY:
            errs.append(f'{tid}: invalid credibility {t.get("credibility")}')
        if t.get('physics_verdict') not in VERDICT:
            errs.append(f'{tid}: invalid physics_verdict {t.get("physics_verdict")}')
        if t.get('research_status') not in RESEARCH:
            errs.append(f'{tid}: invalid research_status {t.get("research_status")}')
        if t.get('canon_status') not in CANON:
            errs.append(f'{tid}: invalid canon_status {t.get("canon_status")}')
        if t.get('canon_status') == 'APPROVED' and 'S-CANON' not in t.get('evidence', []):
            errs.append(f'{tid}: APPROVED canon status needs S-CANON evidence (only the owner approves)')
        if t.get('credibility') == 'FICTIONAL_BREAKTHROUGH' and t.get('physics_verdict') != 'FICTIONAL_DEPENDENT':
            errs.append(f'{tid}: a Level C (fictional) record must have physics_verdict FICTIONAL_DEPENDENT')
        for d in t.get('depends_on', []):
            if d not in byid:
                errs.append(f'{tid}: depends_on unknown {d}')
            elif d == tid:
                errs.append(f'{tid}: depends on itself')
        for s in t.get('ancestry', []) + t.get('evidence', []):
            src_ok(tid, s)
        for m in t.get('materials', []):
            if m not in mats:
                errs.append(f'{tid}: material {m} not in the PMDS catalogue')
        for p in t.get('purposes', []) + t.get('geometry', {}).get('purposes', []):
            if p not in purps:
                errs.append(f'{tid}: purpose {p} not in PMDS purposes')
        for k in STAGES:
            if not t.get('stages', {}).get(k):
                errs.append(f'{tid}: missing stage {k}')
        for k in QUESTIONS:
            if not t.get('questions', {}).get(k):
                errs.append(f'{tid}: missing answer to question {k.upper()}')
        g = t.get('geometry', {})
        for k in GEOMETRY:
            if k not in g:
                errs.append(f'{tid}: geometry missing {k}')
        if g.get('status') not in GEOM_STATUS:
            errs.append(f'{tid}: invalid geometry status {g.get("status")}')
        if g.get('representation') not in REPRESENTATION:
            errs.append(f'{tid}: invalid geometry representation {g.get("representation")}')
        if g.get('colour') not in colours:
            errs.append(f'{tid}: colour {g.get("colour")} not in functional_colors.PALETTE')
        if g.get('status') == 'NONE' and g.get('components'):
            errs.append(f'{tid}: geometry status NONE but components listed')
        for k in PRIORITY_WEIGHTS:
            v = t.get('priority', {}).get(k)
            if not isinstance(v, int) or not 1 <= v <= 5:
                errs.append(f'{tid}: priority {k} must be an integer 1-5')
        for c in t.get('claims', []):
            q = c.get('quantity', '?')
            for k in ('quantity', 'value', 'unit', 'basis', 'source'):
                if k not in c:
                    errs.append(f'{tid}: claim {q} missing {k} (numerical claims need provenance)')
            if not isinstance(c.get('value'), (int, float)) or isinstance(c.get('value'), bool):
                errs.append(f'{tid}: claim {q} value is not a number')
            if c.get('basis') not in CLAIM_BASIS:
                errs.append(f'{tid}: claim {q} invalid basis {c.get("basis")}')
            if 'source' in c:
                src_ok(f'{tid} claim {q}', c['source'])
            if q in units and units[q][0] != c.get('unit'):
                errs.append(f'{tid}: claim {q} unit {c.get("unit")} conflicts with {units[q][1]} ({units[q][0]})')
            units.setdefault(q, (c.get('unit'), tid))
    for w in {t.get('workstream') for t in T if t.get('kind') == 'technology'}:
        if w not in workstreams:
            errs.append(f'workstream {w} has no workstream record')
    for n in range(1, 9):
        if f'VTX-0{n}' not in workstreams:
            errs.append(f'workstream VTX-0{n} missing')
    errs += [f'dependency cycle: {" -> ".join(c)}' for c in cycles(T)]
    for sid, s in S.items():
        for k in SOURCE_REQUIRED:
            if not s.get(k):
                errs.append(f'source {sid}: missing {k}')
        if s.get('kind') not in SOURCE_KINDS:
            errs.append(f'source {sid}: invalid kind {s.get("kind")}')
        if s.get('verification') not in VERIFICATION:
            errs.append(f'source {sid}: invalid verification {s.get("verification")}')
    for i, l in enumerate(A['links']):
        for k in ('from', 'to'):
            if l.get(k) not in byid:
                errs.append(f'link {i}: unknown {k} {l.get(k)}')
        if l.get('kind') not in LINK_KINDS:
            errs.append(f'link {i}: invalid kind {l.get("kind")}')
        if not l.get('effect'):
            errs.append(f'link {i}: missing effect')
        q = l.get('quantified')
        if not q:
            errs.append(f'link {i}: quantified must be a case name or UNKNOWN')
        elif q.startswith('study:'):                         # study:<folder>:<case> = a case in a thread study's committed results
            folder, case = q.split(':', 2)[1], q.split(':', 2)[2]
            texts = [f.read_text() for f in (HERE / 'studies' / folder).rglob('*.json')]
            if not any(f'"{c}"' in x for x in texts for c in (case, case.split('.')[0])):
                errs.append(f'link {i}: case {case} not in any committed JSON of studies/{folder}')
        elif q != 'UNKNOWN' and cases is not None and q not in cases:
            errs.append(f'link {i}: case {q} not in results/convergence.json')
    dids = [d.get('id') for d in A['decisions']]
    if len(dids) != len(set(dids)):
        errs.append('duplicate decision id')
    for d in A['decisions']:
        if d.get('type') not in DECISION_TYPES:
            errs.append(f'{d.get("id")}: invalid decision type')
        if d.get('state') not in DECISION_STATES:
            errs.append(f'{d.get("id")}: invalid decision state')
        for t in d.get('technologies', []):
            if t not in byid:
                errs.append(f'{d.get("id")}: unknown technology {t}')
    gids = [g.get('id') for g in A['generations']]
    if gids != [f'V{n}' for n in range(len(gids))] or gids[:3] != HISTORICAL:
        errs.append(f'generations must be V0, V1, V2, ... in order, found {gids}')
    for g in A['generations']:
        if g.get('status') not in GEN_STATUS:
            errs.append(f'{g.get("id")}: invalid generation status {g.get("status")}')
        if g.get('id') in HISTORICAL and g.get('status') != 'HISTORICAL_CONDITIONAL':
            errs.append(f'{g.get("id")}: the 2026-11-08 generations stay HISTORICAL_CONDITIONAL')
        if not g.get('consistency'):
            errs.append(f'{g.get("id")}: missing consistency statement')
        if g.get('id') == 'V0' and g.get('change'):
            errs.append('V0 must be FDP-1 unchanged')
        for c in g.get('change', []):
            if c.get('technology') not in byid:
                errs.append(f'{g["id"]}: change {c.get("path")} names unknown technology {c.get("technology")}')
            if c.get('basis') not in ('TARGET', 'MODEL'):
                errs.append(f'{g["id"]}: change {c.get("path")} basis must be TARGET or MODEL')
            if not c.get('rationale'):
                errs.append(f'{g["id"]}: change {c.get("path")} has no rationale')
            nd = c.get('needs_decision')
            if nd and nd not in dids:
                errs.append(f'{g["id"]}: change {c.get("path")} needs unknown decision {nd}')
    return errs


def cycles(T):
    graph = {t.get('id'): list(t.get('depends_on', [])) for t in T}
    out, state = [], {}

    def visit(n, path):
        state[n] = 1
        for m in graph.get(n, []):
            if state.get(m) == 1:
                out.append(path[path.index(m):] + [m] if m in path else [n, m])
            elif m in graph and not state.get(m):
                visit(m, path + [m])
        state[n] = 2
    for n in graph:
        if not state.get(n):
            visit(n, [n])
    return out


def score(t):
    p = t['priority']
    return sum(PRIORITY_WEIGHTS[k] * p[k] for k in PRIORITY_WEIGHTS) / sum(PRIORITY_WEIGHTS.values())


# ----------------------------------------------------------------------------------------------------------------------------------
# rendering
# ----------------------------------------------------------------------------------------------------------------------------------

def _cell(s):
    return str(s).replace('|', '/').replace('\n', ' ')


def render_atlas(A):
    T = A['technologies']; S = A['sources']; R = A['results']
    W = [t for t in T if t['kind'] == 'workstream']
    out = ['# Vertex Drive Technology Atlas', '',
           '_Generated by `atlas.py render` from `registry/*.toml`; do not edit by hand. Research records, not canon: nothing here changes the',
           'canonical Fiji Drive, the production model or the Drive workbooks._', '',
           'Classifications are independent. **Credibility** (Atlas level, not PMDS material level): A established, B plausible future,',
           'C fictional breakthrough. **Verdict**: the brief\'s five outcome classes. **Research status** and **canon status** are tracked',
           'separately; only the owner moves a record past NON_CANON.', '',
           '## Index', '', '| ID | Name | Cred. | Verdict | Research | Canon | Geometry | Priority |', '|---|---|---|---|---|---|---|---|']
    for t in T:
        out.append(f'| {t["id"]} | {_cell(t["name"])} | {CREDIBILITY[t["credibility"]]} | {VERDICT[t["physics_verdict"]]} | '
                   f'{t["research_status"]} | {t["canon_status"]} | {GEOM_STATUS[t["geometry"]["status"]]} | {score(t):.2f} |')
    out += ['', '## Priority ranking', '',
            'Weighted score (weights: mission feasibility 3, credibility 2, independence from unmet prerequisites 1, mass/thermal 2,',
            'unlocking 2, 3D value 1; scores 1-5 in each record). The ranking orders research effort, not adoption.', '',
            '| Rank | ID | Name | Score | Feasibility | Credibility | Independence | Mass/thermal | Unlock | 3D |', '|---|---|---|---|---|---|---|---|---|---|']
    for i, t in enumerate(sorted(T, key=lambda t: -score(t)), 1):
        p = t['priority']
        out.append(f'| {i} | {t["id"]} | {_cell(t["name"])} | {score(t):.2f} | {p["feasibility"]} | {p["credibility"]} | '
                   f'{p["independence"]} | {p["mass_thermal"]} | {p["unlock"]} | {p["design_3d"]} |')
    out += ['', '## Dependency and synergy map', '', '![dependency map](figures/dependency_map.svg)', '',
            'Hard prerequisites (`depends_on`, acyclic):', '']
    for t in T:
        if t['depends_on']:
            out.append(f'- {t["id"]} requires {", ".join(t["depends_on"])}')
    out += ['', 'Interactions (`registry/links.toml`); a quantified case is in `results/convergence.json`:', '',
            '| From | To | Kind | Effect | Quantified |', '|---|---|---|---|---|']
    for l in A['links']:
        out.append(f'| {l["from"]} | {l["to"]} | {l["kind"]} | {_cell(l["effect"])} | {l["quantified"]} |')
    for w in W:
        out += ['', f'## {w["id"]} {w["name"]}', '']
        for t in [w] + [t for t in T if t['kind'] == 'technology' and t['workstream'] == w['id']]:
            out += record(t, S)
    out += ['', '## Decision register', '', '| ID | Type | State | Technologies | Question | Conclusion |', '|---|---|---|---|---|---|']
    for d in A['decisions']:
        out.append(f'| {d["id"]} | {d["type"]} | {d["state"]} | {", ".join(d["technologies"])} | {_cell(d["question"])} | {_cell(d["conclusion"])} |')
    out += ['', '## Sources', '', 'Verification uses the PMDS evidence states. UNVERIFIED means the primary text could not be opened from this',
            'session; the finding is then quoted from a secondary description and must not be read as more than that.', '']
    for sid, s in S.items():
        out += [f'- **{sid}** {s["authors"]} ({s["date"]}). _{s["title"]}_. {s["locator"]}. [{s["verification"]}, checked {s["checked"]}]',
                f'  Finding: {s["finding"]} Limits: {s["limits"]} Relation: {s["relation"]}']
    if R:
        out += ['', f'Convergence results: `results/convergence.json`, summary in `results/CONVERGENCE.md` (FDP-1 calculator {R.get("fdp1_version", "?")}).']
    return '\n'.join(out) + '\n'


def record(t, S):
    st, q, g = t['stages'], t['questions'], t['geometry']
    hdr = 'Workstream' if t['kind'] == 'workstream' else 'Technology'
    o = [f'### {t["id"]} {t["name"]}', '',
         f'{hdr}. Credibility **{CREDIBILITY[t["credibility"]]}** ({t["credibility"]}); verdict **{VERDICT[t["physics_verdict"]]}**; '
         f'research {t["research_status"]}; canon {t["canon_status"]}.', '',
         '| Attribute | Record |', '|---|---|',
         f'| Purpose | {_cell(t["purpose"])} |', f'| Physical principle | {_cell(t["principle"])} |',
         f'| Scientific ancestry | {_cell(t["ancestry_note"])} ({", ".join(t["ancestry"])}) |',
         f'| Current limitations | {_cell(t["limitations"])} |',
         f'| Future advancement | Present: {_cell(st["present"])} Advanced: {_cell(st["advanced"])} Wayfarer era: {_cell(st["wayfarer_era"])} |',
         f'| Required breakthrough | {_cell(t["breakthrough"])} |',
         f'| Dependencies | {", ".join(t["depends_on"]) or "none"} |',
         f'| Input resources | {_cell(t["inputs"])} |', f'| Expected output | {_cell(t["outputs"])} |',
         f'| Potential penalties | {_cell(t["penalties"])} |', f'| Performance criteria | {_cell(t["criteria"])} |',
         f'| Materials (PMDS) | {", ".join(t["materials"]) or "none"}; purposes {", ".join(t["purposes"]) or "none"} |',
         f'| A. Today? | {_cell(q["a"])} |', f'| B. Future engineering? | {_cell(q["b"])} |', f'| C. Benefit to Wayfarer? | {_cell(q["c"])} |',
         f'| Earlier finding | {_cell(t["prior_finding"])} |',
         f'| Geometry | {GEOM_STATUS[g["status"]]}, {g["representation"]}, colour {g["colour"]}: {_cell(", ".join(g["components"]) or "none")} |',
         f'| Evidence | {", ".join(t["evidence"])} |', f'| Uncertainties | {_cell(t["uncertainties"])} |',
         f'| Next experiments | {_cell("; ".join(t["next"]))} |']
    for c in t.get('claims', []):
        extra = (f', range {c["range"]}' if c.get('range') else '') + (f', case {c["study_case"]}' if c.get('study_case') else '')
        o.append(f'| Claim | {c["quantity"]} = {c["value"]:g} {c["unit"]} ({c["basis"]}, {c["source"]}{_cell(extra)}) |')
    return o + ['']


def render_readiness(A):
    T = A['technologies']; R = A['results'] or {}
    out = ['# Vertex 3D Integration Readiness Report', '',
           '_Generated by `atlas.py render` from the `geometry` block of each record; do not edit by hand. Nothing here is drawn yet:',
           'Blender work needs the owner\'s go-ahead (decision D-10) and would live in `work/` as pink `VAR_vertex` collections, never in',
           'production assets._', '',
           'Geometry status: **Engineering-supported** (sized by a Wayfarer calculation), **Parametric placeholder** (placed and sized from',
           'parameters the calculation does not yet constrain), **Conceptual illustration** (shows an idea; not a design). Representation:',
           'HARDWARE is physical equipment, VISUALIZATION is an overlay (fields, flows, cones), MIXED is both.', '']
    gens = R.get('generations', {})
    if gens:
        out += ['## Envelopes by generation', '', '| Generation | Departure t | Loops r (m) | Hardware cone (deg) | Shield t | Warm km2 | Wing tip r (m) | Burn aft of shield (m) |',
                '|---|---|---|---|---|---|---|---|']
        for k, g in gens.items():
            s = g.get('summary', {})
            if s.get('converged'):
                out.append(f'| {k} | {s["departure_t"]:,.0f} | {", ".join(f"{r:.1f}" for r in g.get("loop_radii_m", []))} | '
                           f'{g.get("hardware_cone_deg", float("nan")):.1f} | {s["shield_t"]:,.0f} | {s["warm_km2"]:.2f} | {s["wing_tip_radius_m"]:,.0f} | '
                           f'{g.get("burn_aft_of_shield_m", float("nan")):.1f} |')
            else:
                out.append(f'| {k} | does not close | | | | | | |')
        out.append('')
    for st in GEOM_STATUS:
        rows = [t for t in T if t['geometry']['status'] == st]
        if not rows:
            continue
        out += [f'## {GEOM_STATUS[st]}', '', '| ID | Components | Envelope | Location | Connections | Loads | Radiation | Thermal | Maintenance | PMDS purposes | Colour | Repr. |',
                '|---|---|---|---|---|---|---|---|---|---|---|---|']
        for t in rows:
            g = t['geometry']
            out.append(f'| {t["id"]} | {_cell(", ".join(g["components"]) or "none")} | {_cell(g["envelope"])} | {_cell(g["location"])} | '
                       f'{_cell(g["connections"])} | {_cell(g["loads"])} | {_cell(g["radiation"])} | {_cell(g["thermal"])} | '
                       f'{_cell(g["maintenance"])} | {", ".join(g["purposes"]) or "-"} | {g["colour"]} | {g["representation"]} |')
        out.append('')
    out += ['## What a blockout would show first', '',
            '1. Engineering-supported: burn point and X-ray stand-off sphere, three loops at the generation radii, shadow shield and hardware cone (VTX-01, VTX-02, VTX-06).',
            '2. Parametric placeholders: driver galleries inside the hull cone, equipment module, split warm wings at the generation tip radius, bumpers on loop faces (VTX-01B, VTX-01C, VTX-07A, VTX-07D, VTX-08A).',
            '3. Overlays: clocked-sector helical harmonic, braking-orientation dust exposure, droplet sheet (VTX-03A, VTX-08D, VTX-07B), each labelled ILLUSTRATIVE.', '']
    return '\n'.join(out) + '\n'


def render_svg(A):
    T = A['technologies']
    W = [t for t in T if t['kind'] == 'workstream']
    colw, rowh, top, left = 190, 46, 105, 20
    pos = {}
    for i, w in enumerate(W):
        col = [w] + [t for t in T if t['kind'] == 'technology' and t['workstream'] == w['id']]
        for j, t in enumerate(col):
            pos[t['id']] = (left + i * colw + 85, top + j * rowh + (0 if j == 0 else 18))
    H = top + max(len([t for t in T if t['workstream'] == w['id']]) for w in W) * rowh + 110
    Wd = left * 2 + len(W) * colw
    kc = {'requires': '#666666', 'enables': '#2f8f4e', 'improves': '#2f6fbf', 'worsens': '#c0392b', 'conflicts': '#8e44ad', 'shares': '#b07d2b'}
    cc = {'ESTABLISHED': '#d8ecd8', 'PLAUSIBLE_FUTURE': '#dde6f5', 'FICTIONAL_BREAKTHROUGH': '#f3dcf3'}
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {Wd} {H}" font-family="Helvetica, Arial, sans-serif">',
         '<defs>' + ''.join(f'<marker id="m{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">'
                            f'<path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>' for k, c in kc.items()) + '</defs>',
         f'<rect width="{Wd}" height="{H}" fill="#ffffff"/>',
         f'<text x="{left}" y="32" font-size="20" font-weight="700" fill="#111">Vertex Drive Technology Atlas: dependencies and interactions</text>',
         f'<text x="{left}" y="54" font-size="13" fill="#444">Columns are workstreams; box fill is credibility (green A, blue B, violet C); a red outline is a contradicted or impossible record.</text>']
    edges = [(d, t['id'], 'requires') for t in T for d in t['depends_on']] + [(l['from'], l['to'], l['kind']) for l in A['links']]
    for a, b, k in edges:
        (x0, y0), (x1, y1) = pos[a], pos[b]
        mx = (x0 + x1) / 2
        dash = ' stroke-dasharray="5,3"' if k != 'requires' else ''
        s.append(f'<path d="M{x0},{y0} C{mx},{y0 - 30} {mx},{y1 - 30} {x1},{y1}" fill="none" stroke="{kc[k]}" stroke-width="1.4" '
                 f'stroke-opacity="0.7"{dash} marker-end="url(#m{k})"/>')
    for t in T:
        x, y = pos[t['id']]
        bad = t['research_status'] == 'CONTRADICTED' or t['physics_verdict'] == 'IMPOSSIBLE'
        w = 170 if t['kind'] == 'workstream' else 160
        s.append(f'<rect x="{x - w / 2}" y="{y - 15}" width="{w}" height="30" rx="5" fill="{cc[t["credibility"]]}" '
                 f'stroke="{"#c0392b" if bad else "#333"}" stroke-width="{2.2 if bad or t["kind"] == "workstream" else 1}"/>')
        label = t['name'] if len(t['name']) <= 30 else t['name'][:29] + '…'
        s.append(f'<text x="{x}" y="{y - 2}" text-anchor="middle" font-size="11" font-weight="700" fill="#111">{t["id"]}</text>')
        s.append(f'<text x="{x}" y="{y + 11}" text-anchor="middle" font-size="9" fill="#222">{label.replace("&", "and")}</text>')
    ly = H - 50
    for i, (k, c) in enumerate(kc.items()):
        s.append(f'<line x1="{left + i * 160}" y1="{ly}" x2="{left + i * 160 + 40}" y2="{ly}" stroke="{c}" stroke-width="2.5"'
                 f'{"" if k == "requires" else " stroke-dasharray=\"5,3\""}/>'
                 f'<text x="{left + i * 160 + 48}" y="{ly + 4}" font-size="13" fill="#222">{k}</text>')
    s.append('</svg>')
    return '\n'.join(s) + '\n'


def main(argv):
    cmd = argv[1] if len(argv) > 1 else 'validate'
    A = load()
    errs = validate(A)
    for e in errs:
        print('ERROR', e)
    T = A['technologies']
    print(f'{len(T)} records ({sum(t["kind"] == "workstream" for t in T)} workstreams), {len(A["sources"])} sources, {len(A["links"])} links, '
          f'{len(A["decisions"])} decisions; results {"present" if A["results"] else "absent"}; {len(errs)} errors')
    if errs:
        return 1
    if cmd == 'render':
        (HERE / 'ATLAS.md').write_text(render_atlas(A))
        (HERE / 'READINESS.md').write_text(render_readiness(A))
        (HERE / 'figures').mkdir(exist_ok=True)
        (HERE / 'figures' / 'dependency_map.svg').write_text(render_svg(A))
        print('wrote ATLAS.md, READINESS.md, figures/dependency_map.svg')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
