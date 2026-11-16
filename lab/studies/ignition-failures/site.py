"""What the website's ignition page (tools/story.py, engineering/ignition/) shows of the ignition-failures study. Standard library only.

Returns the committed results/ignition.json (written by model.py) with the page contract. It fails, and stops the site build, when the
result is older than its inputs (model.py, the import, the 1.5 radiation evidence).

    python3 lab/studies/ignition-failures/site.py --json
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def inputs_hash():
    h = hashlib.sha256()
    for p in [HERE / 'model.py', *sorted((HERE / 'imports').glob('vertex_*.json')), ROOT / 'references/evidence/vertex_radiation.json']:
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def story():
    d = json.loads((HERE / 'results/ignition.json').read_text())
    if d.get('inputs_hash') != inputs_hash():
        raise SystemExit('ignition-failures: results/ignition.json is stale; run python3 lab/studies/ignition-failures/model.py')
    d['contract'] = 'WF_IGNITION_FAILURES'
    return d


if __name__ == '__main__':
    if '--json' in sys.argv:
        print(json.dumps(story(), separators=(',', ':')))
