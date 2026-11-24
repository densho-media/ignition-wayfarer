"""What the website's Fusion Ignition simulation (tools/story.py, engineering/fusion-ignition/) shows of the fusion-ignition study.
Standard library only.

Returns the committed results/fusion_ignition.json (written by model.py) with the page contract. It fails, and stops the site build, when
the result is older than its inputs (model.py, the compact import, the ignition-failures and selective-fusion results, the shared Vertex
modules, the parameters).

    python3 lab/studies/fusion-ignition/site.py --json
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import model  # noqa: E402


def story():
    d = json.loads((HERE / 'results/fusion_ignition.json').read_text())
    if d.get('inputs_hash') != model.inputs_hash():
        raise SystemExit('fusion-ignition: results/fusion_ignition.json is stale; run python3 lab/studies/fusion-ignition/model.py')
    d['contract'] = 'WF_FUSION_IGNITION'
    return d


if __name__ == '__main__':
    if '--json' in sys.argv:
        print(json.dumps(story(), separators=(',', ':')))
