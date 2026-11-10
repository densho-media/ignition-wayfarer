"""Shared setup for Vertex Feasibility Gate 2 (T00, research only, NON-CANON).

Gate 2 reuses the gate (studies/gate), T03 (studies/nozzle) and Revision 4 (studies/rev4) code without changing it: V4, Rev 4 and the
gate stay reproducible reference configurations. Frame as T03: origin at the burn point, +z toward the bow (ship +X), metres.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATE = HERE.parent / 'gate'
sys.path.insert(0, str(GATE))

import gate_common as G          # noqa: E402,F401  (also puts studies/nozzle and studies/rev4 on the path)

RESULTS = HERE / 'results'


def write(name, obj):
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / name).write_text(json.dumps(obj, indent=1, default=lambda x: float(x) if hasattr(x, '__float__') else str(x)))


def read(name):
    return json.loads((RESULTS / name).read_text())


def gate(name):
    return json.loads((GATE / 'results' / name).read_text())
