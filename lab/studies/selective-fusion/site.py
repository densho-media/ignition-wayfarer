"""What the website's Fusion engine explainer (tools/story.py, engineering/fusion/) shows of the selective-fusion study. Standard library only.

Returns the committed results/fusion.json (written by model.py) with the page contract. It fails, and stops the site build, when the
result is older than its inputs (model.py, the shared reactivity and radiation code, the parameters).

    python3 lab/studies/selective-fusion/site.py --json
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import model  # noqa: E402


def story():
    d = json.loads((HERE / 'results/fusion.json').read_text())
    if d.get('inputs_hash') != model.inputs_hash():
        raise SystemExit('selective-fusion: results/fusion.json is stale; run python3 lab/studies/selective-fusion/model.py')
    d['contract'] = 'WF_SELECTIVE_FUSION'
    return d


if __name__ == '__main__':
    if '--json' in sys.argv:
        print(json.dumps(story(), separators=(',', ':')))
