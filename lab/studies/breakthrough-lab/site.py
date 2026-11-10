"""What the website's Engineering 2.0 pages (tools/story.py) show of the Breakthrough Lab. Standard library only.

story() validates every registry and the computed scenario grid (lab.validate; any error stops the site build) and returns one JSON
record: the ranked Weakest Links with their metrics read from the imported result files, the breakthrough registry with its sources
resolved, the scientific reference, the scenario cases as compute.py recorded them, the minimal closing breakthrough sets, the
configurations for the Engineering Baseline page and the research imports' provenance. It derives orderings and set relations only;
every number is copied from a result file.

    python3 lab/studies/breakthrough-lab/site.py --json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab  # noqa: E402

CASE_KEYS = ('departure_t', 'propellant_t', 'thrust_MN', 'peak_g', 'a0_g', 'burn_years', 'min_round_trip_years', 'warm_km2', 'hot_km2',
             'wing_tip_radius_m', 'pellet_rate_Hz', 'hot_GW', 'warm_GW', 'gain', 'stand_off_m', 'shield_t', 'radiator_t', 'drive_t',
             'structure_t', 'tank_t', 'payload_t', 'fusion_TW', 'yield_t_TNT')


def fmt(m, v):
    if isinstance(v, str):
        return v
    try:
        return m.get('fmt', '{:,.3g}').format(v)
    except (ValueError, TypeError):
        return str(v)


def source(R, sid):
    if sid in R['sources']:
        s = R['sources'][sid]
        return {'id': sid, 'title': s['title'], 'url': s.get('url', ''), 'locator': s.get('locator', ''), 'nature': s['nature']}
    a = R['atlas_sources'][sid]
    kind = a.get('kind', '')
    nature = 'FICTIONAL' if kind == 'canon' else 'PROJECT_MODEL' if kind == 'model' else 'SCIENTIFIC'
    loc = a.get('url') or a.get('locator') or ''
    url = loc if loc.startswith('http') else ''
    return {'id': sid, 'title': a.get('title', sid), 'url': url, 'locator': loc, 'nature': nature, 'kind': kind}


def minimal_sets(R, cases):
    """Closing cases that no other closing case dominates (every lever at the same or a lower level, one strictly lower)."""
    order = R['results']['order']
    rank = {b: [x['key'] for x in lab.levels_of(R, b)] for b in order}
    closing = [(k, [rank[b].index(c['levels'][b]) for b in order]) for k, c in cases.items() if c['status'] == 'CLOSES']
    out = []
    for k, v in closing:
        if not any(all(a <= b for a, b in zip(w, v)) and w != v for _, w in closing):
            out.append(k)
    by = {b['id']: b for b in R['breakthroughs']}

    def cost(k):
        lv = cases[k]['levels']
        on = [b for b in order if lv[b] != 'L0']
        ev = [next(x for x in by[b]['levels'] if x['key'] == lv[b])['evidence'] for b in on]
        return {'key': k, 'enabled': on, 'count': len(on), 'fictional': ev.count('FICTIONAL_ASSUMPTION'),
                'unverified': ev.count('UNVERIFIED'), 'level_c': sum(by[b]['level'] == 'C' for b in on),
                'departure_t': cases[k]['summary']['departure_t']}
    return sorted((cost(k) for k in out), key=lambda r: (r['fictional'], r['count'], r['departure_t']))


def story():
    R = lab.load()
    errors = lab.validate(R)
    if errors:
        raise SystemExit('Breakthrough Lab registries invalid:\n' + '\n'.join(errors))
    dep = lab.dependents(R['links'])
    links = []
    for n, w in enumerate(lab.ranked(R['links']), 1):
        x = dict(w)
        x['rank'] = n
        x['tier'] = lab.tier(w)
        x['tier_label'] = lab.TIERS[x['tier']]
        x['dependents'] = dep[w['id']]
        x['metrics'] = [{**m, 'value': lab.metric(m), 'text': fmt(m, lab.metric(m))} for m in w['metrics']]
        x['evidence'] = [{**e, **source(R, e['source'])} for e in w['evidence']]
        links.append(x)
    bts = []
    for b in R['breakthroughs']:
        x = dict(b)
        x['references'] = [source(R, s) for s in b['references']]
        x['level_label'] = lab.LEVELS[b['level']]
        x['levels'] = b.get('levels', [])
        x['computed'] = b['id'] in lab.lever_ids(R)
        bts.append(x)
    res = R['results']
    cases = {}
    if res:
        for k, c in res['cases'].items():
            y = {'levels': c['levels'], 'status': c['status']}
            for f in ('reason', 'inferred', 'deficit_factor', 'max_a0_g', 'launcher', 'envelope'):
                if f in c:
                    y[f] = c[f]
            if c.get('summary'):
                y['summary'] = {f: c['summary'][f] for f in CASE_KEYS if f in c['summary']}
            if c.get('coupled'):
                cp = c['coupled']
                y['coupled'] = {f: cp[f] for f in ('status', 'iterations', 'items', 'loop_gain', 'reason', 'added_t', 'rate_cap_Hz') if f in cp}
                if cp.get('summary'):
                    y['coupled']['summary'] = cp['summary']
            unmet = [f'{b} needs {dep}' for b in res['order'] if c['levels'][b] != 'L0'
                     for dep in next(x for x in R['breakthroughs'] if x['id'] == b).get('depends_on', [])
                     if dep in c['levels'] and c['levels'][dep] == 'L0']
            if unmet:
                y['dependency_unmet'] = unmet
            cases[k] = y
    gens = json.loads((lab.IMPORTS / 't00-43fac75/results/convergence.json').read_text())['generations']
    coupled = json.loads((lab.IMPORTS / 't00-43fac75/studies/gate/results/coupled.json').read_text())
    config = {
        'generations': {g: {'name': v['record']['name'], 'status': v['record']['status'], 'definition': v['record']['definition'],
                            'consistency': v['record'].get('consistency', ''), 'summary': {f: v['summary'].get(f) for f in CASE_KEYS if f in v['summary']},
                            'hot_GW': v.get('hot_GW'), 'warm_GW': v.get('warm_GW'), 'gain': v.get('gain')}
                        for g, v in gens.items()},
        'coupled': [{'label': c['label'], 'status': c['status'], 'iterations': c['iterations'],
                     'departure_t': c.get('summary', {}).get('departure_t'), 'rate_Hz': c.get('fusion', {}).get('pellet_rate_Hz'),
                     'warm_km2': c.get('heat_rejection', {}).get('warm_km2')} for c in coupled['cases']],
        'v5_note': 'V5 is a bound (ideal compression), never a design or a target.',
    }
    data = {
        'vocab': {'levels': lab.LEVELS, 'evidence': lab.EVIDENCE, 'development': lab.DEVELOPMENT, 'canon': lab.CANON, 'tiers': lab.TIERS,
                  'resolution': lab.RESOLUTION, 'status': {'CLOSES': 'Closes', 'DOES_NOT_CLOSE': 'Does not close',
                                                           'NOT_COMPUTED': 'Not computed', 'OUT_OF_RANGE': 'Out of range'}},
        'reference': R['scenarios']['reference'], 'grid': R['scenarios']['grid'], 'named': R['scenarios'].get('named', []),
        'links': links, 'breakthroughs': bts, 'cases': cases,
        'order': res['order'] if res else lab.lever_ids(R),
        'provenance': res['provenance'] if res else None, 'reproduces': res['reproduces'] if res else {},
        'minimal': minimal_sets(R, cases) if res else [],
        'config': config,
        'imports': [{k: m[k] for k in ('thread', 'name', 'branch', 'commit', 'status')} | {'files': len(m['files'])} for m in R['imports']],
    }
    return data


if __name__ == '__main__':
    print(json.dumps(story(), default=float))
