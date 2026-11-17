"""What the website's dust page (tools/story.py, engineering/dust/) shows of the dust-impacts study. Standard library only.

Returns the committed results/dust.json (written by model.py) with the page contract. It fails, and stops the site build, when the
result is older than its inputs (model.py and the imported Vertex 2.6 model).

    python3 lab/studies/dust-impacts/site.py --json
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def inputs_hash():
    h = hashlib.sha256()
    for p in [HERE / 'model.py', *sorted((HERE / 'imports' / 'vertex_2_6_874dca7').glob('*.py'))]:
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def story():
    d = json.loads((HERE / 'results/dust.json').read_text())
    if d.get('inputs_hash') != inputs_hash():
        raise SystemExit('dust-impacts: results/dust.json is stale; run python3 lab/studies/dust-impacts/model.py')
    d['contract'] = 'WF_DUST_IMPACTS'
    return d


if __name__ == '__main__':
    if '--json' in sys.argv:
        print(json.dumps(story(), separators=(',', ':')))
