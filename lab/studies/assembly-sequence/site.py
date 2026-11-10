"""What the website's build-sequence page (tools/story.py, engineering/build/) shows of the assembly sequence. Standard library only.

story() checks sequence.toml (any error stops the site build) and returns one JSON record: the phases, the steps with their selectors
(web/engineering/build.js classifies the Explore Ship parts with them in the browser) and the mass ledger booked from the placed mass
model and the operating point.

    python3 lab/studies/assembly-sequence/site.py --json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sequence  # noqa: E402

KEYS = ('id', 'phase', 'title', 'select', 'fallback', 'after', 'rests_on', 'why', 'detail', 'open', 'view')


def story():
    from spec import load
    seq = sequence.load()
    errors = sequence.validate(seq)
    led = sequence.ledger(seq, load(sequence.ROOT)[0])
    errors += led['errors']
    if errors or not led['closes']:
        raise SystemExit('assembly sequence: ' + '; '.join(errors or ['the mass ledger does not reach the departure mass']))
    mass = {r['id']: r for r in led['steps']}
    steps = []
    for i, st in enumerate(seq['step'], 1):
        rec = {k: st.get(k, [] if k in ('select', 'fallback', 'after', 'detail', 'open') else '') for k in KEYS}
        rec['n'] = i
        rec['why'] = ' '.join(rec['why'].split())
        rec['view'] = rec['view'] or 'threequarter'
        m = mass[st['id']]
        rec['mass'] = {'added_t': round(m['added_kg'] / 1e3, 1), 'cumulative_t': round(m['cumulative_kg'] / 1e3, 1),
                       'parts': [[n, round(kg / 1e3, 1)] for n, kg in m['parts']]}
        steps.append(rec)
    return {'contract': 'WF_ASSEMBLY_SEQUENCE', 'version': 1, 'status': 'PROTOTYPE',
            'phases': seq['phase'], 'steps': steps,
            'ledger': {k[:-3] + '_t': round(led[k] / 1e3, 1) for k in ('dry_kg', 'propellant_kg', 'total_kg', 'departure_kg', 'circulation_kg')}}


if __name__ == '__main__':
    if '--json' not in sys.argv:
        raise SystemExit(__doc__)
    print(json.dumps(story(), separators=(',', ':')))
