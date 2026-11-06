"""Configuration: fdp1.toml deep-merged with a variant, and the four-burn scenario it overrides. Canon comes from data/ through the
repository's own pure modules (spec, layout, fuel_storage, habitat_ring, mass_model); nothing canon is typed here."""
import copy
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]          # lab/variants/fdp1
ROOT = HERE.parents[2]                              # repository root
CONFIG = HERE/'config'


def _merge(a, b):
    """Deep merge: plain tables merge key by key; a leaf table ({value = ...} or {source = ...}) replaces the whole leaf."""
    out = copy.deepcopy(a)
    for k, val in b.items():
        if isinstance(val, dict) and isinstance(out.get(k), dict) and not ('value' in val or 'source' in val):
            out[k] = _merge(out[k], val)
        else:
            out[k] = copy.deepcopy(val)
    return out


def load(variant=None, overrides=None):
    cfg = tomllib.loads((CONFIG/'fdp1.toml').read_text())
    cfg['variant'] = 'baseline'
    if variant and variant != 'baseline':
        cfg = _merge(cfg, tomllib.loads((CONFIG/'variants'/f'{variant}.toml').read_text()))
        cfg['variant'] = variant
    if overrides:
        cfg = _merge(cfg, overrides)
    return cfg


def variants():
    return ['baseline']+sorted(p.stem for p in (CONFIG/'variants').glob('*.toml'))


def v(entry, default=None):
    """The value of a config entry: {value = x, status = ...} tables or bare values."""
    if isinstance(entry, dict):
        return entry.get('value', default)
    return entry if entry is not None else default


def fourburn(cfg):
    """Import the four-burn calculator package (the one authoritative propulsion engine)."""
    path = str(ROOT/cfg['base']['calculator'])
    if path not in sys.path:
        sys.path.insert(0, path)
    import fourburn                                  # noqa: F401
    from fourburn import canon, closure, architectures, kinematics, rocket, tanks, thermal, plasma, const
    return {'canon': canon, 'closure': closure, 'architectures': architectures, 'kinematics': kinematics, 'rocket': rocket,
            'tanks': tanks, 'thermal': thermal, 'plasma': plasma, 'const': const}


def scenario(cfg, fb):
    sc = fb['canon'].scenario(cfg['base']['scenario'])
    return _merge(sc, cfg['base'].get('overrides', {}))


def spec():
    """Canon spec through the repository's own loader (validated inputs, derived quantities)."""
    p = str(ROOT/'src/wayfarer')
    if p not in sys.path:
        sys.path.insert(0, p)
    import spec as wspec
    return wspec.load()[0]


def wayfarer_modules():
    p = str(ROOT/'src/wayfarer')
    if p not in sys.path:
        sys.path.insert(0, p)
    import layout, fuel_storage, habitat_ring, mass_model, functional_colors
    return {'layout': layout, 'fuel_storage': fuel_storage, 'habitat_ring': habitat_ring, 'mass_model': mass_model,
            'functional_colors': functional_colors}
