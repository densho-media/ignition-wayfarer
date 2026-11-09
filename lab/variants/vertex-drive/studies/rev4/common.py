"""Shared helpers for the Revision 4 T00 studies (research only, NON-CANON).

Every ship number comes from the FDP-1 calculator through the Vertex adapter (convergence.py). Nothing here changes FDP-1, the four-burn
engine, data/ or src/. Constants marked PROTOTYPE are T00 engineering choices; SOURCE values carry their reference in the docstring.
"""
import copy
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VX = HERE.parents[1]                      # lab/variants/vertex-drive
sys.path.insert(0, str(VX))
import convergence as C                   # noqa: E402

MU0 = 4e-7 * math.pi
SIGMA_SB = 5.670374419e-8
G0 = 9.80665
YEAR = 3.15576e7


def v4_overrides():
    return C.generations()['V4']['overrides']


def core(ov):
    return {k: v for k, v in ov.items() if k != 'vertex'}


def solve_full(ov):
    """Full FDP-1 record for an override tree (no launcher cap)."""
    return C.fdp1.solve('baseline', core(ov))


def write_json(name, obj):
    p = HERE / 'results' / name
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, default=float) + '\n')
    return p


def read_json(name):
    return json.loads((HERE / 'results' / name).read_text())


def attenuation():
    return json.loads((HERE / 'data/xray_attenuation.json').read_text())


def deep(x):
    return copy.deepcopy(x)
