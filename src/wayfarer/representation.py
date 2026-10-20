"""FUT-002 representations and shot operations, independent of Blender.

A representation is another presentation of the same saved source component, never separate canon.
In a shot, each representation object is a shot-local object that reuses the source's linked geometry data, so the
shot references Wayfarer and never owns it. Identity is the instance path plus the component_id,
because components are reused (six ring sectors, three radiators): the same key names the same source instance in every
representation. The operations (isolate, reveal, conceal, highlight, explode, recombine) are key tables
over per-object presentation values; this module computes them so tests and the Blender tools share one definition.
"""
from fnmatch import fnmatch
from pathlib import Path
import math
import tomllib

ROOT = Path(__file__).resolve().parents[2]
FIXED = ''  # explode group of items that never move (e.g. debug overlays)
GROUP_RULES = ('drive_node', 'assembly', 'subassembly', 'fixed')

REPRESENTATIONS = {
    'REP_PROXY': dict(built=True, where='saved assets', note='Low-cost generated geometry; the only representation saved in the assets.'),
    'REP_STANDARD': dict(built=True, where='shots', geometry_basis='REP_PROXY',
                         note='Normal production look: source colours, bevelled mesh edges. Geometry is still the proxy '
                              'geometry; production topology, UVs and materials are FUT-003.'),
    'REP_HOLOGRAM': dict(built=True, where='shots', geometry_basis='REP_PROXY',
                         note='Technical exposition: emissive, see-through, wire-edged presentation of the real assembly.'),
    'REP_CUTAWAY': dict(built=True, where='shots', geometry_basis='REP_PROXY',
                        note='Internal engineering view: skins cut by a shot-local section plane; cut faces shown as caps.'),
    'REP_SIM': dict(built=True, where='saved assets (WF_SIMPROXY_*, P1-003)', note='Massless simulation proxies; not a shot representation.'),
    'REP_HERO': dict(built=True, where='saved assets, [production] assemblies only (M7)', geometry_basis='REP_PROXY + production layer',
                     note='Highest detail: the M7 production layer (production_detail.py, kind production_detail, layer PRODUCTION) over the '
                          'unchanged proxy geometry of the assemblies [production] builds; elsewhere the ship stays REP_PROXY.'),
}
SHOT_REPRESENTATIONS = ('REP_STANDARD', 'REP_HOLOGRAM', 'REP_CUTAWAY')
OPERATIONS = ('isolate', 'reveal', 'conceal', 'highlight', 'explode', 'recombine')
# Object kinds never represented: saved-hidden or non-geometric helpers.
SKIP_KINDS = {'sim_proxy', 'interface', 'sim_anchor', 'sim_root', 'state_control', 'drive_node'}


def identity(path, component_id):
    """Stable key of one source instance: collection-instance path (outermost first) and component_id."""
    return '/'.join([*path, str(component_id)])


def matches(item, selector):
    """selector 'field:pattern' (fnmatch) on key, id (component_id), kind, group, source, name or subsystem (the M5 id a shot with a
    subsystem table assigns, e.g. 'subsystem:S05'); bare text matches the key."""
    field, _, pattern = selector.partition(':') if ':' in selector else ('key', '', selector)
    if field not in ('key', 'id', 'kind', 'group', 'source', 'name', 'subsystem'):
        raise ValueError(f'Unknown selector field: {selector}')
    value = item['component_id'] if field == 'id' else item.get(field, '')
    return fnmatch(str(value), pattern)


def select(items, selectors):
    """Keys of the items matched by any selector (OR)."""
    selectors = [selectors] if isinstance(selectors, str) else list(selectors)
    return {item['key'] for item in items if any(matches(item, s) for s in selectors)}


def group_centers(items):
    groups = {}
    for item in items:
        if item['group'] != FIXED and item.get('solid', True):
            groups.setdefault(item['group'], []).append(item['center'])
    return {g: tuple(sum(p[i] for p in pts)/len(pts) for i in range(3)) for g, pts in groups.items()}


def explode_vectors(items, pivot=None, axial=1.0, radial=1.0):
    """Offset of each explode group at full explosion: its centre's distance from the pivot, scaled axially (X) and
    radially (YZ). A group moves rigidly, so recombining (factor 0) restores every object exactly. Fixed items stay."""
    centers = group_centers(items)
    if not centers:
        return {FIXED: (0.0, 0.0, 0.0)}
    if pivot is None:
        pivot = tuple(sum(c[i] for c in centers.values())/len(centers) for i in range(3))
    out = {g: (axial*(c[0]-pivot[0]), radial*(c[1]-pivot[1]), radial*(c[2]-pivot[2])) for g, c in sorted(centers.items())}
    out[FIXED] = (0.0, 0.0, 0.0)
    for item in items:  # a group with nothing solid (collapsed plasma only) stays put
        out.setdefault(item['group'], (0.0, 0.0, 0.0))
    return out


def color_for(item, colors, fallback=(0.7, 0.7, 0.7)):
    """First matching 'selector = [r, g, b]' entry wins; 'default' is the fallback."""
    for selector, rgb in colors.items():
        if selector != 'default' and matches(item, selector):
            return tuple(rgb)
    return tuple(colors.get('default', fallback))


CONTEXT = dict(id='CTX', name='Context: hull casing and unclassified', color=(0.30, 0.31, 0.33), sources='14_HULL_SERVICE (13 m body)',
               maturity='BASELINE envelope; casing PROTOTYPE')


def load_subsystems(root, name):
    """M5 subsystem table (shots/<name>): ordered entries with id, name, color, optional per-selector colors, select, fallback,
    sources, maturity and label."""
    with open(Path(root)/'shots'/name, 'rb') as f:
        subs = tomllib.load(f)['subsystem']
    if len({s['id'] for s in subs}) != len(subs):
        raise ValueError(f'{name}: subsystem ids repeat')
    return subs


def classify(item, subsystems):
    """Subsystem of a shot item: the first `select` match in file order, else the first `fallback` match, else CONTEXT."""
    for field in ('select', 'fallback'):
        for sub in subsystems:
            if any(matches(item, s) for s in sub.get(field, [])):
                return sub
    return CONTEXT


def subsystem_color(item, subsystems):
    sub = classify(item, subsystems)
    for selector, rgb in sub.get('colors', {}).items():
        if matches(item, selector):
            return tuple(rgb)
    return tuple(sub['color'])


def subsystem_labels(subsystems, show):
    """Shot labels from the subsystem table: one per subsystem that names a label, shown over `show`."""
    return [dict(lab, show=list(show)) for lab in (s.get('label') for s in subsystems) if lab]


def load_shots(root=ROOT):
    with open(Path(root)/'shots/shots.toml', 'rb') as f:
        data = tomllib.load(f)
    for name, shot in data['shot'].items():
        validate_shot(name, shot)
    return data


def validate_shot(name, shot):
    if not name.startswith('SH_'):
        raise ValueError(f'{name}: shot names start with SH_')
    if shot['representation'] not in SHOT_REPRESENTATIONS:
        raise ValueError(f'{name}: representation must be one of {SHOT_REPRESENTATIONS}')
    if not shot['sources'] or any(src['group'] not in GROUP_RULES for src in shot['sources']):
        raise ValueError(f'{name}: sources need a group rule in {GROUP_RULES}')
    if any(Path(src['asset']).is_absolute() or '..' in Path(src['asset']).parts for src in shot['sources']):
        raise ValueError(f'{name}: sources are paths under assets/<library>')
    if any(src.get('library', 'wayfarer') not in ('wayfarer', 'characters') for src in shot['sources']):
        raise ValueError(f'{name}: a source library is wayfarer or characters (assets/<library>)')
    if 'cuts' in shot and not (shot['cuts'][0]['frame'] == 1 and all(a['frame'] < b['frame'] for a, b in zip(shot['cuts'], shot['cuts'][1:]))
                               and shot['cuts'][-1]['frame'] <= shot['frame_end']):
        raise ValueError(f'{name}: camera cuts start at frame 1 and rise inside 1..frame_end')
    if shot.get('materials', 'shot') not in ('shot', 'source'):
        raise ValueError(f'{name}: materials is shot or source')
    if 'preset' in shot and not (isinstance(shot['preset'], str) and shot['preset']):
        raise ValueError(f'{name}: preset names a buildable configuration')
    if shot['representation'] == 'REP_CUTAWAY' and not (shot.get('section') and shot.get('cut')):
        raise ValueError(f'{name}: a cutaway needs a section plane and cut selectors')
    frames = [op['frame']+op.get('duration', 0) for op in shot['ops']]+[lab['show'][1] for lab in shot.get('labels', [])]
    if any(f > shot['frame_end'] for f in frames) or any(f < 1 or f > shot['frame_end'] for f in shot['review_frames']):
        raise ValueError(f'{name}: timing outside 1..frame_end')
    for op in shot['ops']:
        if op['op'] not in OPERATIONS:
            raise ValueError(f'{name}: unknown operation {op["op"]}')


def schedule(items, ops, initial=None):
    """Key tables for a shot timeline.

    ops: dicts with op, frame, optional duration (frames, default 0) and select; highlight takes value (default 1),
    explode takes value (default 1). Values ramp linearly from `frame` to `frame+duration`.
    Returns {'alpha': {key: [(frame, value)]}, 'highlight': {...}, 'hidden': {key: [(frame, bool)]}, 'explode': [(frame, value)]}.
    An object is hidden (skipped by the renderer) exactly while its alpha rests at 0.
    """
    keys = [item['key'] for item in items]
    current = {'alpha': {k: 1.0 for k in keys}, 'highlight': {k: 0.0 for k in keys}}
    if initial:
        shown = select(items, initial)
        current['alpha'] = {k: float(k in shown) for k in keys}
    tables = {'alpha': {k: [(1, current['alpha'][k])] for k in keys}, 'highlight': {k: [(1, 0.0)] for k in keys}}
    explode = [(1, 0.0)]; factor = 0.0
    for op in sorted(ops, key=lambda o: o['frame']):
        name, f = op['op'], int(op['frame']); d = int(op.get('duration', 0))
        if name not in OPERATIONS:
            raise ValueError(f'Unknown operation: {name}')
        if f < 1 or d < 0:
            raise ValueError(f'Bad timing: {op}')
        if name in ('explode', 'recombine'):
            target = float(op.get('value', 1.0)) if name == 'explode' else 0.0
            if f < explode[-1][0]:
                raise ValueError(f'Overlapping explode keys at frame {f}')
            if target != factor:
                _change(explode, f, d, factor, target)
                factor = target
            continue
        chosen = select(items, op['select'])
        if not chosen:
            raise ValueError(f'Selector matches nothing: {op["select"]}')
        if name == 'isolate':
            channel, targets = 'alpha', {k: float(k in chosen) for k in keys}
        elif name in ('reveal', 'conceal'):
            channel, targets = 'alpha', {k: float(name == 'reveal') for k in chosen}
        else:
            channel, targets = 'highlight', {k: float(op.get('value', 1.0)) for k in chosen}
        for k, target in targets.items():
            table = tables[channel][k]
            if target == current[channel][k]:
                continue
            if f < table[-1][0]:
                raise ValueError(f'{k}: {name} at frame {f} overlaps an earlier {channel} change')
            _change(table, f, d, current[channel][k], target)
            current[channel][k] = target
    tables['explode'] = _dedupe(explode)
    tables['alpha'] = {k: _dedupe(v) for k, v in tables['alpha'].items()}
    tables['highlight'] = {k: _dedupe(v) for k, v in tables['highlight'].items()}
    tables['hidden'] = {k: hidden_keys(v) for k, v in tables['alpha'].items()}
    return tables


def _change(table, f, d, current, target):
    """Hold the current value up to the change, then ramp over d frames (d = 0: a one-frame step)."""
    start = f if d else f-1
    if start > table[-1][0]:
        table.append((start, current))
    table.append((f+d, target))


def _dedupe(keys):
    """Drop a key that repeats the previous frame; a later key at the same frame wins (instant change)."""
    out = []
    for frame, value in keys:
        if out and out[-1][0] == frame:
            out[-1] = (frame, value)
        else:
            out.append((frame, value))
    return out


def hidden_keys(alpha_keys):
    """Constant hide keys: hidden from the frame alpha comes to rest at 0 until the frame a ramp away from 0 starts."""
    out = []
    for i, (frame, value) in enumerate(alpha_keys):
        rising = i+1 < len(alpha_keys) and value == 0 and alpha_keys[i+1][1] > 0
        state = value == 0 and not rising
        if not out or out[-1][1] != state:
            out.append((frame, state))
    return out


def value_at(keys, frame):
    """Linear interpolation of a key table (constant before the first and after the last key)."""
    if frame <= keys[0][0]:
        return keys[0][1]
    for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
        if f0 <= frame <= f1:
            return v0 if f1 == f0 else v0+(v1-v0)*(frame-f0)/(f1-f0)
    return keys[-1][1]


def hidden_at(keys, frame):
    state = keys[0][1]
    for f, value in keys:
        if f <= frame:
            state = value
    return state


def fit_distance(radius, fov_deg):
    """Perspective camera distance that keeps a sphere of `radius` inside the vertical field of view."""
    return radius/math.sin(math.radians(fov_deg)/2)
