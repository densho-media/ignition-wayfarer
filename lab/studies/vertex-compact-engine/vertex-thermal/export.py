"""Copy the thermal study's results into the Fusion Ignition lab study (lab/studies/fusion-ignition/imports/thermal_<head>.json), once per
accepted run. Nothing in lab/ reads work/; the copy carries its provenance.

    python3 lab/studies/vertex-compact-engine/vertex-thermal/export.py
"""
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
d = json.loads((HERE / 'results' / 'thermal.json').read_text())
d['problems'] = json.loads((HERE / 'results' / 'problems_thermal.json').read_text())
head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
d['provenance'] = dict(study='lab/studies/vertex-compact-engine/vertex-thermal (thermal.py, problems.py)', branch_head=head,
                       note='Copied once by lab/studies/vertex-compact-engine/vertex-thermal/export.py; work/ is not read by lab/, tools/ or CI.')
dst = ROOT / 'lab/studies/fusion-ignition/imports'
for old in dst.glob('thermal_*.json'):
    old.unlink()
out = dst / f'thermal_{head}.json'
out.write_text(json.dumps(d, separators=(',', ':')))
print('wrote', out.relative_to(ROOT), out.stat().st_size, 'bytes')
src = json.loads((HERE.parent / 'vertex-source' / 'results' / 'source.json').read_text())
src['provenance'] = dict(study='lab/studies/vertex-compact-engine/vertex-source (source.py)', branch_head=head, note='Copied once by lab/studies/vertex-compact-engine/vertex-thermal/export.py.')
for old in dst.glob('source_*.json'):
    old.unlink()
o2 = dst / f'source_{head}.json'
o2.write_text(json.dumps(src, separators=(',', ':'), default=float))
print('wrote', o2.relative_to(ROOT), o2.stat().st_size, 'bytes')
