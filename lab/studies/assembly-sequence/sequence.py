"""Assembly sequence of the approved model: load and check sequence.toml, book the mass model onto the steps, classify parts.

    python3 lab/studies/assembly-sequence/sequence.py                                       # the checks and the mass ledger
    python3 lab/studies/assembly-sequence/sequence.py --manifest <manifest.json> --holo <holo.json>   # plus which step every exported part lands in

Reads data/ and src/wayfarer (spec, mass_model, operating_point); writes nothing. The classifier here is the reference for the one in
web/engineering/build.js, which applies the same rules in the browser to the Explore Ship model.
"""
from fnmatch import fnmatch
import json
from pathlib import Path
import sys
import tomllib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))

FIELDS = ('id', 'kind', 'sub', 'group')
VIEWS = ('threequarter', 'side', 'top', 'front', 'aft')


def load():
    return tomllib.loads((HERE / 'sequence.toml').read_text())


def selector(s):
    field, sep, pattern = s.partition(':')
    if not sep or field not in FIELDS or not pattern:
        raise ValueError(f'bad selector {s!r}: field:pattern with field in {FIELDS}')
    return field, pattern


def validate(seq):
    """Structural checks: unique ids, known phases in order, `after` only to earlier steps, valid selectors and views."""
    errors = []
    phases = [p['id'] for p in seq['phase']]
    seen, last_phase = [], -1
    for st in seq['step']:
        sid = st['id']
        if sid in seen:
            errors.append(f'{sid}: duplicate step id')
        if st['phase'] not in phases:
            errors.append(f'{sid}: unknown phase {st["phase"]}')
        else:
            i = phases.index(st['phase'])
            if i < last_phase:
                errors.append(f'{sid}: phase {st["phase"]} after a later phase')
            last_phase = max(last_phase, i)
        for a in st.get('after', []):
            if a not in seen:
                errors.append(f'{sid}: after {a!r}, which is not an earlier step')
        for s in st.get('select', []) + st.get('fallback', []):
            try:
                selector(s)
            except ValueError as e:
                errors.append(f'{sid}: {e}')
        if st.get('view', 'threequarter') not in VIEWS:
            errors.append(f'{sid}: view {st["view"]!r} not in {VIEWS}')
        for k in ('title', 'why', 'rests_on'):
            if not st.get(k):
                errors.append(f'{sid}: no {k}')
        seen.append(sid)
    return errors


def ledger(seq, spec):
    """Every mass-model part (mass_model.dry_parts) and the mission propellant booked onto exactly one step, in step order.
    Returns the steps' added and cumulative masses, the departure-mass check and any booking errors."""
    import mass_model
    import operating_point
    parts = {p['name']: p['m'] for p in mass_model.dry_parts(spec)}
    mission = operating_point.mission(spec)
    parts['propellant'] = mission['propellant_kg']
    owner, errors = {}, []
    for st in seq['step']:
        for pat in st.get('mass', []):
            hits = [n for n in parts if fnmatch(n, pat)]
            if not hits:
                errors.append(f'{st["id"]}: mass {pat!r} matches no mass-model part')
            for n in hits:
                if n in owner:
                    errors.append(f'{n}: booked by {owner[n]} and {st["id"]}')
                owner[n] = st['id']
    for n in parts:
        if n not in owner:
            errors.append(f'{n}: mass-model part not booked on any step')
    total, rows = 0.0, []
    for st in seq['step']:
        mine = sorted((n for n, o in owner.items() if o == st['id']), key=lambda n: -parts[n])
        added = sum(parts[n] for n in mine)
        total += added
        rows.append({'id': st['id'], 'added_kg': added, 'cumulative_kg': total, 'parts': [[n, parts[n]] for n in mine]})
    dry = total - parts['propellant']
    # The placed mass model carries the CIRC-001 ring corridors on top of the operating point's protected-and-operational mass
    # (physics.mass_placement.include_circulation); the operating point's departure mass does not include them yet.
    circ = sum(m for n, m in parts.items() if n.startswith('circ001@'))
    return {'steps': rows, 'total_kg': total, 'dry_kg': dry, 'propellant_kg': parts['propellant'], 'circulation_kg': circ,
            'departure_kg': mission['departure_mass_kg'], 'end_kg': mission['end_mass_kg'],
            'closes': abs(total - circ - mission['departure_mass_kg']) < 1.0, 'errors': errors}


def classify(seq, item):
    """The step of one part (item: id, kind, sub, group): the first step whose select matches, else the first whose fallback does."""
    for field in ('select', 'fallback'):
        for st in seq['step']:
            for s in st.get(field, []):
                f, pat = selector(s)
                if fnmatch(str(item.get(f, '')), pat):
                    return st['id'], field
    return None, None


def items(manifest, holo):
    """The parts as the browser sees them: the Explore Ship nodes file fields plus the M5 subsystem and the component group."""
    out = []
    for r in manifest['nodes']:
        sub = holo['nodes'].get(r['node'], 'CTX')
        out.append({'node': r['node'], 'id': r['component_id'], 'kind': r['kind'], 'sub': sub[0] if isinstance(sub, list) else sub,
                    'group': holo.get('groups', {}).get(r['node'], '')})
    return out


def coverage(seq, parts):
    by, how = {}, {'select': 0, 'fallback': 0, None: 0}
    unplaced = []
    for it in parts:
        sid, field = classify(seq, it)
        how[field] += 1
        if sid is None:
            unplaced.append(it['id'])
        else:
            by[sid] = by.get(sid, 0) + 1
    return {'by_step': by, 'select': how['select'], 'fallback': how['fallback'], 'unplaced': unplaced,
            'empty_steps': [st['id'] for st in seq['step'] if st.get('select') and not by.get(st['id'])]}


def main():
    import argparse
    from spec import load as load_spec
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--manifest', type=Path)
    ap.add_argument('--holo', type=Path)
    a = ap.parse_args()
    seq = load()
    errors = validate(seq)
    led = ledger(seq, load_spec(ROOT)[0])
    errors += led['errors']
    print(f'{len(seq["step"])} steps in {len(seq["phase"])} phases; mass {led["dry_kg"] / 1e3:,.0f} t dry + {led["propellant_kg"] / 1e3:,.0f} t '
          f'propellant = {led["total_kg"] / 1e3:,.0f} t = departure {led["departure_kg"] / 1e3:,.0f} t + CIRC-001 {led["circulation_kg"] / 1e3:,.1f} t '
          f'({"closes" if led["closes"] else "DOES NOT CLOSE"})')
    if a.manifest:
        cov = coverage(seq, items(json.loads(a.manifest.read_text()), json.loads(a.holo.read_text()) if a.holo else {'nodes': {}}))
        print(json.dumps(cov['by_step']))
        print(f'{cov["select"]} parts by select, {cov["fallback"]} by subsystem fallback, {len(cov["unplaced"])} unplaced {cov["unplaced"][:20]}')
        if cov['empty_steps']:
            errors.append(f'steps with selectors but no parts: {cov["empty_steps"]}')
    for e in errors:
        print('ERROR', e)
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
