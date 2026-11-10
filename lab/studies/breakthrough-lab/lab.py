"""Breakthrough Lab registries: load and validate (standard library only; research records, NOT canon).

Used by compute.py (which solves the scenarios), site.py (what the website shows) and the tests. validate() returns a list of errors; an
empty list means every record is well formed, every cross-reference resolves, the dependency graph is acyclic, every level stays inside
its breakthrough's declared parameters and limit, level L0 equals the scientific reference, and canon status is only APPROVED with an
owner decision. Nothing here computes a mass or a performance value.
"""
import hashlib
import json
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REG = HERE / 'registry'
IMPORTS = HERE / 'imports'
RESULTS = HERE / 'results' / 'scenarios.json'

LEVELS = {'A': 'Established technology', 'B': 'Advanced, physics-consistent extrapolation', 'C': 'Speculative technology'}
EVIDENCE = {'DEMONSTRATED': 'Demonstrated', 'LITERATURE_SUPPORTED': 'Literature-supported', 'CALCULATED': 'Calculated',
            'EXTRAPOLATED': 'Extrapolated', 'UNVERIFIED': 'Unverified', 'FICTIONAL_ASSUMPTION': 'Fictional assumption'}
DEVELOPMENT = {'PROPOSED': 'Proposed', 'UNDER_INVESTIGATION': 'Under investigation', 'SELECTED_FOR_EXPERIMENT': 'Selected for experiment',
               'REJECTED': 'Rejected', 'APPROVED_FOR_CANON': 'Approved for canon'}
CANON = {'NON_CANON': 'Not canon', 'CANDIDATE': 'Canon candidate', 'APPROVED': 'Approved IGNITION canon'}
TIERS = {1: 'Fundamental feasibility blocker', 2: 'Strongly coupled engineering blocker', 3: 'Major mass or dimensional penalty',
         4: 'Local mechanical engineering problem', 5: 'Secondary optimisation'}
RESOLUTION = {'OPEN': 'Open', 'PARTIAL': 'Partly addressed', 'CANDIDATE_FIX': 'Candidate fix, not demonstrated', 'RESOLVED': 'Resolved'}
CONFIDENCE = {'HIGH', 'MEDIUM', 'LOW'}
CONVENTIONAL = {'YES', 'POSSIBLY', 'UNLIKELY', 'NO'}
SPECULATIVE = {'NOT_NEEDED', 'MAY_HELP', 'LIKELY_REQUIRED', 'REQUIRED'}
INPUT_BASIS = {'MODEL', 'OWNER_DECISION', 'LITERATURE_SUPPORTED', 'CALCULATED'}
SOURCE_NATURE = {'SCIENTIFIC', 'PROJECT_MODEL', 'FICTIONAL'}
STATUS = {'CLOSES', 'DOES_NOT_CLOSE', 'NOT_COMPUTED', 'OUT_OF_RANGE'}
BT_FIELDS = ('id', 'name', 'summary', 'limitation', 'weakest_links', 'basis', 'level', 'evidence', 'development', 'canon', 'assumption',
             'modifies', 'unchanged', 'allowed', 'forbidden', 'energy', 'depends_on', 'risks', 'validation', 'references', 'atlas',
             'materials', 'penalties')
WL_FIELDS = ('id', 'name', 'subsystem', 'description', 'baseline', 'current', 'required', 'gap', 'evidence', 'confidence', 'uncertainty',
             'consequences', 'depends_on', 'candidates', 'conventional', 'speculative', 'resolution', 'questions', 'tier_reason',
             'breakthroughs', 'systems', 'metrics')
QUESTIONS = ('blocks_engine', 'non_convergence', 'major_penalty', 'local')


def _toml(name):
    with open(REG / name, 'rb') as f:
        return tomllib.load(f)


def load():
    """Every registry, the imported research snapshots' manifest and (if computed) the scenario results."""
    out = {'breakthroughs': _toml('breakthroughs.toml')['breakthrough'], 'links': _toml('weakest_links.toml')['link'],
           'scenarios': _toml('scenarios.toml'), 'sources': _toml('sources.toml')}
    out['atlas_sources'] = _atlas_sources()
    out['imports'] = [json.loads(p.read_text()) for p in sorted(IMPORTS.glob('*/MANIFEST.json'))]
    out['results'] = json.loads(RESULTS.read_text()) if RESULTS.exists() else None
    return out


def _atlas_sources():
    p = IMPORTS / 't00-030fc14' / 'registry' / 'sources.toml'
    if not p.exists():
        return {}
    with open(p, 'rb') as f:
        return tomllib.load(f)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def registry_hash():
    """One hash over the registries the scenarios depend on (the results record it; a change invalidates them)."""
    h = hashlib.sha256()
    for name in ('breakthroughs.toml', 'scenarios.toml'):
        h.update((REG / name).read_bytes())
    return h.hexdigest()


def key(levels, order):
    return '|'.join(f'{b}:{levels[b]}' for b in order)


def lever_ids(R):
    g = R['scenarios']['grid']
    return list(g['levers']) + [g['launcher']]


def reference_paths(R):
    return {i['path']: i['value'] for i in R['scenarios']['reference']['input']}


def _cycle(graph):
    seen, stack = set(), set()

    def visit(n):
        if n in stack:
            return True
        if n in seen:
            return False
        seen.add(n); stack.add(n)
        hit = any(visit(m) for m in graph.get(n, ()))
        stack.discard(n)
        return hit
    return [n for n in graph if visit(n)]


def validate(R):
    err = []
    bts, wls = R['breakthroughs'], R['links']
    sources = set(R['sources']) | set(R['atlas_sources'])
    bt_ids = [b['id'] for b in bts]
    wl_ids = [w['id'] for w in wls]
    for kind, ids, prefix in (('breakthrough', bt_ids, 'BT-'), ('weakest link', wl_ids, 'WL-')):
        for i in ids:
            if not (i.startswith(prefix) and len(i) == 6 and i[3:].isdigit()):
                err.append(f'{kind} id {i!r} is not {prefix}nnn')
        dup = {i for i in ids if ids.count(i) > 1}
        if dup:
            err.append(f'duplicate {kind} ids {sorted(dup)}')
    names = [b['name'] for b in bts]
    if len(set(names)) != len(names):
        err.append('duplicate breakthrough names')
    materials = _materials()
    atlas = _atlas_ids()
    ref = reference_paths(R)
    for s, v in R['sources'].items():
        if v.get('nature') not in SOURCE_NATURE:
            err.append(f'source {s}: nature {v.get("nature")!r}')
    for b in bts:
        i = b.get('id', '?')
        for f in BT_FIELDS:
            if f not in b:
                err.append(f'{i}: missing {f}')
        for f, voc in (('level', LEVELS), ('evidence', EVIDENCE), ('development', DEVELOPMENT), ('canon', CANON)):
            if b.get(f) not in voc:
                err.append(f'{i}: {f} {b.get(f)!r} not in {sorted(voc)}')
        if b.get('canon') == 'APPROVED' and (b.get('development') != 'APPROVED_FOR_CANON' or not b.get('canon_decision')):
            err.append(f'{i}: canon APPROVED needs development APPROVED_FOR_CANON and an owner canon_decision')
        if b.get('development') == 'APPROVED_FOR_CANON' and not b.get('canon_decision'):
            err.append(f'{i}: APPROVED_FOR_CANON needs an owner canon_decision')
        if b.get('level') == 'C' and b.get('evidence') in ('DEMONSTRATED', 'LITERATURE_SUPPORTED'):
            err.append(f'{i}: a Level C breakthrough cannot have {b["evidence"]} evidence')
        for w in b.get('weakest_links', []):
            if w not in wl_ids:
                err.append(f'{i}: unknown weakest link {w}')
        for d in b.get('depends_on', []):
            if d not in bt_ids:
                err.append(f'{i}: depends on unknown {d}')
        for s in b.get('references', []):
            if s not in sources:
                err.append(f'{i}: unknown reference {s}')
        for m in b.get('materials', []):
            if materials and m not in materials:
                err.append(f'{i}: unknown PMDS material {m}')
        for a in b.get('atlas', []):
            if atlas and a not in atlas:
                err.append(f'{i}: unknown Atlas technology {a}')
        pen = b.get('penalties', {})
        for f in ('power', 'heat', 'mass', 'maintenance', 'booked', 'unbooked'):
            if f not in pen:
                err.append(f'{i}: penalties.{f} missing')
        levels = b.get('levels', [])
        mods = set(b.get('modifies', []))
        if mods and not levels:
            err.append(f'{i}: modifies parameters but has no levels')
        keys = [lv.get('key') for lv in levels]
        if levels and keys[0] != 'L0':
            err.append(f'{i}: the first level must be L0 (the scientific reference)')
        if len(set(keys)) != len(keys):
            err.append(f'{i}: duplicate level keys')
        lim = b.get('limit')
        for lv in levels:
            if lv.get('evidence') not in EVIDENCE:
                err.append(f'{i} {lv.get("key")}: evidence {lv.get("evidence")!r}')
            st = lv.get('set', {})
            if set(st) != mods:
                err.append(f'{i} {lv.get("key")}: sets {sorted(st)} but the breakthrough modifies {sorted(mods)}')
            for p in st:
                if p in ref:
                    err.append(f'{i}: {p} is both a lever and a fixed reference input')
            if lim and isinstance(st.get(lim['path']), (int, float)) and st[lim['path']] > lim['max']:
                err.append(f'{i} {lv["key"]}: {lim["path"]} = {st[lim["path"]]} beyond the limit {lim["max"]} (must be OUT_OF_RANGE, not a level)')
    graph = {b['id']: b.get('depends_on', []) for b in bts}
    if _cycle(graph):
        err.append(f'breakthrough dependency cycle through {sorted(_cycle(graph))}')
    for w in wls:
        i = w.get('id', '?')
        for f in WL_FIELDS:
            if f not in w:
                err.append(f'{i}: missing {f}')
        q = w.get('questions', {})
        if set(q) != set(QUESTIONS) or not all(isinstance(v, bool) for v in q.values()):
            err.append(f'{i}: questions must answer {QUESTIONS} with true/false')
        for m in w.get('metrics', []):
            try:
                metric(m)
            except (KeyError, IndexError, ValueError, FileNotFoundError) as e:
                err.append(f'{i}: metric {m.get("label")!r} does not resolve ({type(e).__name__}: {e})')
        for f, voc in (('confidence', CONFIDENCE), ('conventional', CONVENTIONAL), ('speculative', SPECULATIVE), ('resolution', RESOLUTION)):
            if w.get(f) not in voc:
                err.append(f'{i}: {f} {w.get(f)!r} not in {sorted(voc)}')
        for d in w.get('depends_on', []):
            if d not in wl_ids:
                err.append(f'{i}: depends on unknown {d}')
        for d in w.get('breakthroughs', []):
            if d not in bt_ids:
                err.append(f'{i}: unknown breakthrough {d}')
        for e in w.get('evidence', []):
            if e.get('source') not in sources:
                err.append(f'{i}: unknown evidence source {e.get("source")}')
        if w.get('resolution') == 'RESOLVED':
            err.append(f'{i}: RESOLVED links leave the register (delete them; history is in Git)')
    if _cycle({w['id']: w.get('depends_on', []) for w in wls}):
        err.append('weakest-link dependency cycle')
    # A breakthrough naming a link must be named back by it (one relation, two views).
    for b in bts:
        for w in wls:
            if (w['id'] in b.get('weakest_links', [])) != (b['id'] in w.get('breakthroughs', [])):
                err.append(f'{b["id"]} and {w["id"]} disagree on their relation')
    S = R['scenarios']
    for inp in S['reference']['input']:
        if inp.get('basis') not in INPUT_BASIS:
            err.append(f'reference input {inp["path"]}: basis {inp.get("basis")!r}')
    by = {b['id']: b for b in bts}
    for lid in lever_ids(R):
        if lid not in by or not by[lid].get('levels'):
            err.append(f'grid lever {lid} has no levels')
    for n in S.get('named', []):
        if set(n['levels']) != set(lever_ids(R)):
            err.append(f'{n["id"]}: levels must name every lever')
        for b, lv in n['levels'].items():
            if b in by and lv not in [x['key'] for x in by[b].get('levels', [])]:
                err.append(f'{n["id"]}: {b} has no level {lv}')
        if n['layer'] == 'A' and any(v != 'L0' for v in n['levels'].values()):
            err.append(f'{n["id"]}: a Layer A scenario may only use L0 levels')
    if R['results']:
        err += validate_results(R)
    return err


def validate_results(R):
    """Provenance and integrity of results/scenarios.json against the registries it was computed from."""
    err = []
    res = R['results']
    prov = res.get('provenance', {})
    for f in ('t00_commit', 't00_branch', 'calculator_files', 'registry_sha256', 'computed_utc', 'method'):
        if f not in prov:
            err.append(f'results: provenance.{f} missing')
    if prov.get('registry_sha256') != registry_hash():
        err.append('results: registries changed since the scenarios were computed (rerun compute.py)')
    if prov.get('t00_commit') not in [m.get('commit') for m in R['imports']]:
        err.append('results: computed against a T00 commit with no import manifest')
    by = {b['id']: b for b in R['breakthroughs']}
    order = lever_ids(R)
    ref = reference_paths(R)
    for k, c in res.get('cases', {}).items():
        if c.get('status') not in STATUS:
            err.append(f'{k}: status {c.get("status")!r}')
        levels = dict(x.split(':') for x in k.split('|'))
        if list(levels) != order:
            err.append(f'{k}: key does not name the levers in grid order')
        # Exactly the reference plus the enabled levels' declared parameters: no unsupported parameter change.
        expect = dict(ref)
        for b, lv in levels.items():
            expect.update(next(x for x in by[b]['levels'] if x['key'] == lv)['set'])
        if c.get('inputs') != json.loads(json.dumps(expect)):
            err.append(f'{k}: inputs differ from reference + declared levels')
        if c['status'] in ('CLOSES', 'DOES_NOT_CLOSE') and not c.get('computed'):
            err.append(f'{k}: {c["status"]} without a calculator record')
        if c['status'] in ('NOT_COMPUTED', 'OUT_OF_RANGE') and c.get('summary'):
            err.append(f'{k}: {c["status"]} must not carry numbers')
        if c['status'] == 'CLOSES':
            s = c.get('summary', {})
            for f in ('departure_t', 'hot_GW', 'warm_GW', 'warm_km2', 'hot_km2', 'wing_tip_radius_m', 'pellet_rate_Hz'):
                if not isinstance(s.get(f), (int, float)):
                    err.append(f'{k}: CLOSES without {f}')
            if isinstance(s.get('hot_GW'), (int, float)) and s['hot_GW'] <= 0 or isinstance(s.get('warm_GW'), (int, float)) and s['warm_GW'] <= 0:
                err.append(f'{k}: a heat load vanished')
    return err


def tier(w):
    """The register's ranking rule: the first of the four questions answered yes (5 if none)."""
    q = w['questions']
    return next((n for n, k in enumerate(QUESTIONS, 1) if q.get(k)), 5)


def dependents(links):
    """How many links depend on each link, directly or through others."""
    up = {w['id']: set(w.get('depends_on', [])) for w in links}

    def closure(i, seen):
        for d in up.get(i, ()):
            if d not in seen:
                seen.add(d)
                closure(d, seen)
        return seen
    count = {w['id']: 0 for w in links}
    for w in links:
        for d in closure(w['id'], set()):
            count[d] += 1
    return count


def ranked(links):
    """The register order: tier; then how far conventional engineering is from a fix (no path first); then transitive dependents
    (more first); then confidence; then id."""
    dep = dependents(links)
    conf = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
    conv = {'NO': 0, 'UNLIKELY': 1, 'POSSIBLY': 2, 'YES': 3}
    return sorted(links, key=lambda w: (tier(w), conv[w['conventional']], -dep[w['id']], conf[w['confidence']], w['id']))


_FILES = {}


def metric(m):
    """Resolve one register metric: a JSON pointer into an imported result file, scaled. Raises if it does not resolve."""
    path = IMPORTS / m['file']
    if path not in _FILES:
        _FILES[path] = json.loads(path.read_text())
    node = _FILES[path]
    for part in m['pointer'].lstrip('/').split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        node = node[int(part)] if isinstance(node, list) else node[part]
    if isinstance(node, (int, float)) and not isinstance(node, bool):
        node = node * m.get('scale', 1.0)
    elif not isinstance(node, str):
        raise ValueError(f'{m["pointer"]} is not a number or text')
    return node


def _materials():
    p = ROOT / 'data/materials/catalogue.toml'
    if not p.exists():
        return set()
    with open(p, 'rb') as f:
        return set(tomllib.load(f).get('material', {}))


def _atlas_ids():
    p = IMPORTS / 't00-030fc14' / 'registry' / 'technologies.toml'
    if not p.exists():
        return set()
    with open(p, 'rb') as f:
        return {t['id'] for t in tomllib.load(f)['technology']}


def levels_of(R, bid):
    b = next(x for x in R['breakthroughs'] if x['id'] == bid)
    return b.get('levels', [])


if __name__ == '__main__':
    e = validate(load())
    print('\n'.join(e) if e else 'registries OK')
    raise SystemExit(1 if e else 0)
