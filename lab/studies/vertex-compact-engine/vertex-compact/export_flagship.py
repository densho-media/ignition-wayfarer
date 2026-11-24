#!/usr/bin/env python3
"""Copy the compact-direction results once into the Fusion Ignition lab study (lab/studies/fusion-ignition/imports/compact_<commit>.json):
the variant ledger (no sample points), the field-multiple scan, the engine source split (ron.source) and the problem register ENG-030..038.
Infinite values become null. Research, not canon."""
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / 'vertex-ron'))
import ron  # noqa: E402


def clean(x):
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean(v) for v in x]
    return x


def main():
    commit = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    C = json.loads((HERE / 'results/compact.json').read_text())
    keep = ('label', 'D_m', 'standoff_m', 'shield', 'shield_t', 'mult', 'eta', 'hit_share', 'piped_four_W', 'piped_over_budget', 'sky', 'ship_lit_W',
            'ship_lit_over_limit', 'ship_lit_parts', 'x_burn', 'ripple', 'winding_fluence', 'winding_over_limit', 'engine_t', 'dust_nominal_t',
            'dust_justified_t', 'departure_if_heat_closed_t', 'extra_radiator_t')
    k = ron.canon(); fuel = ron.variants()['A_compact']['fuel']; src = ron.source(k, fuel)
    out = dict(provenance=dict(branch='claude/project-thread-1p6mtu', commit=commit, files=['lab/studies/vertex-compact-engine/vertex-compact/results/compact.json',
                                                                                             'lab/studies/vertex-compact-engine/vertex-compact/results/field_scan.json',
                                                                                             'lab/studies/vertex-compact-engine/vertex-compact/results/problems_compact.json',
                                                                                             'lab/studies/vertex-compact-engine/vertex-ron/ron.py source()']),
               meta=C['meta'], variants={key: {f: v[f] for f in keep if f in v} for key, v in C['variants'].items()},
               field_scan=json.loads((HERE / 'results/field_scan.json').read_text()),
               source=dict(fuel=fuel, **{kk: src[kk] for kk in src if kk.endswith('_W')}, fusion_per_engine_W=k['fusion_per_engine_W'], drive_W=k['drive_W']),
               problems=json.loads((HERE / 'results/problems_compact.json').read_text()))
    dst = ROOT / 'lab/studies/fusion-ignition/imports' / f'compact_{commit}.json'
    dst.write_text(json.dumps(clean(out), indent=1))
    print(dst, json.dumps(out['source']))


if __name__ == '__main__':
    main()
