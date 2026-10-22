"""Change-scoped check selection (DEV-FLOW): changed files -> unit tests, build target, inspection groups and Godot checks.

`plan()` reads the changed paths (the working tree against HEAD by default), follows the project's import graph (static and
function-level imports, plus `name.py` path literals) and an explicit table of shared modules and neighbouring interfaces, and
returns what to run with a reason per selection. Anything it cannot place (an unknown file, a TOML key no module names) widens to
the whole suite: selection may only narrow when the dependency is visible. A scoped selection is never a whole-ship PASS; the full
`pipeline` stays the pre-commit gate.
"""
from collections import defaultdict
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
CODE_DIRS = ('src/wayfarer', 'tools', 'tests')
# Modules whose change reaches every check: the spec loader and validation, the shared layout datums, the Blender build plumbing,
# the rig contract and the inspection itself. (Direct imports alone would under-select these.)
SHARED = {'spec', 'layout', 'common', 'recipes', 'build', 'rig', 'sim_rig', 'inspect', 'representation', 'geometry_fingerprint',
          'compare_fingerprint', 'modules', 'detail'}
# Detail packs (docs/MODULES.md): data/detail/<pack>.toml and src/wayfarer/detail/pack_<pack>.py select the pack's own detail targets, its
# screens' tests and its declared inspection groups; the pack code is loaded by path, so the import graph alone would not see it.
PACK_TESTS = ('test_production', 'test_modules')
# Build targets by the generator modules each recipe enters (src/wayfarer/components/recipes.py); a module reaching more than one
# target, or the dispatcher itself, needs the full build.
TARGET_ENTRIES = {
    'NOZZLE': ('drive',), 'STORAGE': ('drive',), 'PROPULSION': ('drive',), 'DEBUG_MAGNETICS': ('drive',),
    'DEBUG_SEPARATRICES': ('drive',), 'DEBUG_OPTICS': ('drive',),
    'RADIATOR': ('revision',), 'RING_SECTOR': ('revision',), 'STRUCTURE': ('revision',), 'HABITAT': ('revision',),
    'SHIELDING': ('revision',), 'THERMAL': ('revision',),
    'INTERIOR_HABITATION': ('interior',), 'INTERIOR_WORK': ('interior',), 'INTERIOR_GARDEN': ('interior',),
    'FORWARD_SHIELD': ('forward',), 'HULL': ('hull',), 'SERVICE': ('hull',), 'POWER_STORAGE': ('power',),
    'ROTOR_INTERFACE': ('rotor',), 'CREW_TRANSFER': ('crew',), 'DRONES': ('drones',), 'CHARACTERS': ('figures',),
}
# Inspection groups (validation/inspect.py GROUPS) by the modules whose geometry or state they check.
INSPECT_GROUPS = {
    'drive': {'drive_manifold', 'drive_hot_section', 'drive', 'first_ignition'},
    'rotation': {'habitat_ring', 'habitat_interior', 'rotor_interface', 'rotor', 'interior', 'sector_whitebox', 'route_fitout', 'revision',
                 'crew_transfer', 'crew', 'production_detail', 'production'},
    'hull': {'hull_geometry', 'hull', 'human_entry', 'survival', 'survival_fit', 'storeroom', 'power', 'power_storage', 'fitout'},
    'thermal': {'thermal_geometry', 'radiator_health', 'radiator_net_area', 'warm_panels', 'revision', 'radiator_inspect'},
    'forward': {'forward_shield', 'forward', 'eye_placement', 'forward_inspect', 'drones', 'drone_fleet'},
    'timeline': {'flight_timeline', 'drive_manifold', 'forward_shield', 'radiator_health'},
    'route': {'human_entry', 'crew_transfer', 'route_fitout', 'fitout', 'crew', 'hull', 'storeroom', 'production_detail', 'production'},
}
# Neighbouring interfaces: shared clearances, pressure boundaries and mechanisms. The hull contact check (every hull shell, fitting,
# refuge, hub mechanism and crew part against all other geometry) is the neighbour of every geometry group.
NEIGHBOURS = {'drive': {'hull'}, 'rotation': {'hull', 'route'}, 'thermal': {'hull'}, 'forward': {'hull'}, 'route': {'hull', 'rotation'},
              'hull': {'route'}, 'timeline': set()}
DOC_SUFFIXES = {'.md', '.txt', '.svg', '.png', '.jpg', '.webp', '.csv'}


def changed_paths(root=ROOT, base='HEAD'):
    """Paths changed in the working tree against `base`, plus untracked files (not ignored)."""
    git = lambda *a: subprocess.check_output(['git', '-C', str(root), *a], text=True).splitlines()
    return sorted({*git('diff', '--name-only', base), *git('ls-files', '--others', '--exclude-standard')})


def modules(root=ROOT):
    """{stem: [paths]} of the project's Python modules."""
    out = defaultdict(list)
    for d in CODE_DIRS:
        for p in sorted((root/d).rglob('*.py')):
            if '__pycache__' not in p.parts:
                out[p.stem].append(p.relative_to(root))
    return out


IMPORT = re.compile(r'^\s*(?:from\s+(\w+)[\w.]*\s+import|import\s+([\w.,\s]+?)(?:\s+as\s+\w+)?\s*(?:#.*)?$)', re.M)
PATH_LITERAL = re.compile(r"(\w+)\.py['\"]")
LOADS = re.compile(r'spec_from_file_location|load_module\(|with_name\(')


def graph(root=ROOT):
    """{path: {paths it depends on}} over the project's modules; a stem shared by two files resolves to the importer's own directory first,
    then src/wayfarer."""
    mods = modules(root); out = {}
    for paths in mods.values():
        for p in paths:
            text = (root/p).read_text(errors='replace')
            # Path literals count only where they load a module (importlib by path); subprocess paths are commands, not imports.
            names = {n for line in text.splitlines() if LOADS.search(line) for n in PATH_LITERAL.findall(line)}
            for a, b in IMPORT.findall(text):
                names.update([a] if a else [n.strip().split('.')[0] for n in b.split(',')])
            deps = set()
            for n in names:
                cands = [c for c in mods.get(n, []) if c != p]      # `import eva_suit` in build/eva_suit.py is the pure module
                if len(cands) > 1:
                    cands = [c for c in cands if c.parent == p.parent] or [c for c in cands if c.parent == Path('src/wayfarer')] or cands
                deps.update(cands)
            out[p] = deps
    return out


def closure(g, starts):
    seen, todo = set(), list(starts)
    while todo:
        p = todo.pop()
        if p not in seen:
            seen.add(p); todo.extend(g.get(p, ()))
    return seen


def toml_changes(root, rel, base='HEAD'):
    """Changed key paths (top-level table, second-level key) of a TOML file against `base`; None when it cannot be compared."""
    try:
        old = tomllib.loads(subprocess.check_output(['git', '-C', str(root), 'show', f'{base}:{rel}'], text=True))
    except (subprocess.CalledProcessError, tomllib.TOMLDecodeError):
        return None
    new = tomllib.loads((root/rel).read_text()); out = set()
    for k in set(old) | set(new):
        a, b = old.get(k), new.get(k)
        if a == b:
            continue
        if isinstance(a, dict) and isinstance(b, dict):
            out.update((k, j) for j in set(a) | set(b) if a.get(j) != b.get(j))
        else:
            out.add((k, None))
    return out


def godot_checks(root, changed):
    """Runtime check names (tools/runtime_export.CHECKS) whose scene or script closure contains a changed Godot file."""
    sys.path.insert(0, str(root/'tools'))
    import runtime_export
    files = [p for p in (root/'godot').rglob('*') if p.suffix in ('.gd', '.tscn') and '.godot' not in p.parts and 'generated' not in p.parts]
    classes = {}
    for p in files:
        m = re.search(r'^class_name\s+(\w+)', p.read_text(errors='replace'), re.M) if p.suffix == '.gd' else None
        if m:
            classes[m.group(1)] = p
    deps = {}
    for p in files:
        text = p.read_text(errors='replace')
        d = {root/'godot'/r for r in re.findall(r'res://([\w/.]+\.(?:gd|tscn))', text)}
        d.update(c for name, c in classes.items() if c != p and re.search(rf'\b{name}\b', text))
        deps[p] = d
    hit = {root/c for c in changed}
    out = []
    for check in runtime_export.CHECKS:
        entry = check.get('scene') or check.get('script')
        if entry and closure(deps, [root/'godot'/entry]) & hit:
            out.append(check['name'])
    return out


def pack_name(rel):
    """The detail pack a path belongs to (data/detail/<pack>.toml, src/wayfarer/detail/pack_<pack>.py), else None."""
    p = Path(rel)
    if p.parent == Path('data/detail') and p.suffix == '.toml':
        return p.stem
    if p.parent == Path('src/wayfarer/detail') and p.suffix == '.py' and p.stem.startswith('pack_'):
        return p.stem[len('pack_'):]
    return None


def detail_selection(root, names, base='HEAD'):
    """Build targets and inspection groups of the named packs: DETAIL_<assembly> for an edited pack, its anchor's host for a new pack or a
    changed anchor (the host must link it); a pack removed from the tree selects the hosts it was on."""
    sys.path.insert(0, str(root/'src/wayfarer'))
    import modules
    targets, groups = set(), set()
    for name in sorted(names):
        rel = f'{modules.PACK_DIR}/{name}.toml'
        try:
            old = tomllib.loads(subprocess.check_output(['git', '-C', str(root), 'show', f'{base}:{rel}'], text=True, stderr=subprocess.DEVNULL))
        except subprocess.CalledProcessError:
            old = None
        new = tomllib.loads((root/rel).read_text()) if (root/rel).is_file() else None
        cur = (new or old or {})
        groups.update(cur.get('pack', {}).get('inspect', []))
        for a, t in (cur.get('assembly') or {}).items():
            was = (old or {}).get('assembly', {}).get(a)
            moved = new is None or was is None or was.get('anchor') != t.get('anchor')
            targets.add(modules.anchor_host(t['anchor']) if moved else modules.target(a))
    return targets, groups & set(INSPECT_GROUPS)


def plan(root=ROOT, paths=None, base='HEAD'):
    root = Path(root).resolve(); paths = changed_paths(root, base) if paths is None else list(paths)
    g = graph(root); reverse = defaultdict(set)
    for p, ds in g.items():
        for d in ds:
            reverse[d].add(p)
    tests = sorted(p for p in g if p.parent == Path('tests') and p.name.startswith('test_'))
    widen = {}                      # reason -> True: run everything of that kind
    touched = set(); reasons = {}; godot_changed = []; data_files = []; data_values = False; packs_touched = set()
    for rel in paths:
        p = Path(rel)
        pack = pack_name(rel)
        if pack:
            packs_touched.add(pack); reasons[rel] = f'detail pack {pack}: its detail assets, {", ".join(PACK_TESTS)} and its inspection groups'
            if p in g:
                touched.add(p)
        elif p.suffix in DOC_SUFFIXES or p.parts[0] in ('references', 'renders', 'runs') or rel in ('TODO.md', 'README.md'):
            reasons[rel] = 'documentation or evidence: no check'
        elif p.parts[0] == 'godot':
            godot_changed.append(rel); reasons[rel] = 'Godot runtime: affected scene checks'
        elif p.suffix == '.py' and p in g:
            touched.add(p); reasons[rel] = 'Python module: its importers and their tests'
            if p.stem in SHARED:
                widen['shared module ' + rel] = True
        elif p.suffix == '.toml' and p.parts[0] == 'data':
            data_files.append(rel)
        elif p.suffix == '.json' and p.parts[0] == 'simulations':
            reasons[rel] = 'generated contract: tests that read it'; touched.update(t for t in tests if p.name in (root/t).read_text())
        else:
            widen[f'unplaced change {rel}'] = True; reasons[rel] = 'not placed by the dependency map: everything'
    # TOML: the modules that name a changed key (or its table) are the touched consumers; an unnamed key widens.
    for rel in data_files:
        keys = toml_changes(root, rel, base)
        if rel != 'data/wayfarer_3d.toml':
            users = {q for q in g if Path(rel).name in (root/q).read_text(errors='replace')}
            touched.update(users); reasons[rel] = f'data file read by {len(users)} modules'
            if rel == 'data/source_map.toml':
                touched.update(q for q in g if q.stem in ('spec', 'test_spec'))
            if not users:
                widen[f'no reader of {rel}'] = True
            continue
        if keys is None:
            widen[f'{rel} not comparable with {base}'] = True; reasons[rel] = 'new or unreadable at base: everything'; continue
        named = []
        for table, key in sorted(keys, key=str):
            needle = f"'{key}'" if key else f"'{table}'"
            users = {q for q in g if q.parts[0] == 'src' and needle in (root/q).read_text(errors='replace')}
            if not users and key:
                users = {q for q in g if q.parts[0] == 'src' and f"'{table}'" in (root/q).read_text(errors='replace')}
            if not users:
                widen[f'no module names {table}.{key}'] = True
            touched.update(users); named.append(f'{table}.{key}' if key else table)
        if named:
            touched.update(q for q in g if q.stem in ('test_spec', 'test_owner_targets'))      # owner numbers and spec validation
            data_values = True
        reasons[rel] = 'changed keys ' + ', '.join(named[:12]) + (' ...' if len(named) > 12 else '') if named else 'no value change'
    # Tests: a test is selected when its import closure reaches a touched module. The spec loader is a boundary: every test loads the
    # spec, whose validation imports the shared formulas, so a change there selects the spec and owner-target tests (and the pipeline's
    # spec step) rather than every test that merely loads the data.
    spec_paths = [q for q in g if q.stem == 'spec' and q.parts[0] == 'src']
    cut = {q: (set() if q in spec_paths else ds) for q, ds in g.items()}
    everything = bool(widen)
    selected = set(tests) if everything else {t for t in tests if closure(cut, [t]) & touched}
    if touched & closure(g, spec_paths):
        selected.update(t for t in tests if t.stem in ('test_spec', 'test_owner_targets'))
    stems = {q.stem for q in touched}
    # Inspection groups: the touched modules' groups and their neighbours; the generators importing a touched module count too
    # (the dispatching hubs recipes and revision only when touched themselves).
    users = {q.stem for q in closure(reverse, touched) if q.parts[:3] == ('src', 'wayfarer', 'components')} - {'recipes', 'revision'}
    groups = set(INSPECT_GROUPS) if everything else {k for k, v in INSPECT_GROUPS.items() if v & (stems | users)}
    for k in list(groups):
        groups |= NEIGHBOURS[k]
    # Build target: the recipe targets whose generators reach a touched module; none reached but the build uses it (rig contract,
    # timeline) -> the vehicle; several, or shared plumbing -> all.
    build_paths = [q for q in g if q.stem == 'build' and q.parts[:3] == ('src', 'wayfarer', 'build')]
    used_by_build = touched & closure(g, build_paths)
    reach = {k: {q.stem for q in closure(g, [q for q in g if q.stem in v and q.parts[:2] == ('src', 'wayfarer')])} for k, v in TARGET_ENTRIES.items()}
    targets = sorted(k for k, v in reach.items() if stems & v)
    # Packs: the edited ones and those whose code imports a touched module. An edit rebuilds only the pack's detail assets; a new pack or a
    # moved anchor rebuilds its host, which links it.
    reached = {pack_name(str(q)) for q in closure(reverse, touched)} - {None}
    pack_targets, pack_groups = detail_selection(root, packs_touched | reached, base)
    selected.update(t for t in tests if t.stem in PACK_TESTS and (packs_touched | reached))
    targets = sorted(set(targets) | pack_targets)
    groups |= pack_groups
    for k in list(groups):
        groups |= NEIGHBOURS[k]
    if (packs_touched | reached) and not used_by_build:
        used_by_build = {True}
    if everything or data_values:
        target = 'all'                  # a changed input value reaches every asset (AGENTS: shared input -> full build)
    elif not used_by_build:
        target = None
    elif stems & SHARED or len(targets) > 1:
        target = 'all'
    else:
        target = targets[0] if targets else 'vehicle'
    runtime = godot_checks(root, godot_changed) if godot_changed else []
    export_inputs = target is not None
    return {
        'changed': paths, 'reasons': reasons, 'widened_by': sorted(widen),
        'tests': sorted(t.stem for t in selected), 'tests_total': len(tests),
        'build_target': target, 'inspect_groups': sorted(groups) if target else [],
        'runtime_checks': runtime,
        'runtime_package': 'rebuild with runtime-export (geometry, exporter or rig inputs changed)' if export_inputs else
                           'reuse the published package if runtime-check reports it current' if runtime else None,
        'note': 'scoped selection; the full pipeline remains the pre-commit gate' if not everything else 'full selection',
    }


STAGE_STATE = '.wayfarer-stages.json'     # local, untracked: per-loop stage input identities (tools/eva_loop.py, character_loop.py)


def stage_inputs(root, scripts, g=None):
    """{path: sha256} of what a loop stage reads: its scripts' import closure, every data TOML, the saved production and character
    assets and the reference JSON the EVA and character loops exchange. Conservative: any rebuild of an asset makes the stage stale."""
    import hashlib
    g = g or graph(root)
    paths = closure(g, [Path(s) for s in scripts])
    files = [*(root/p for p in paths), *sorted((root/'data').glob('*.toml')),
             *(p for p in sorted((root/'assets').rglob('*.blend')) if 'milestones' not in p.parts and 'studies' not in p.parts),
             *sorted((root/'references').glob('p1_eva_*.json')), *sorted((root/'references').glob('p1_human_*.json'))]
    return {str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files if f.is_file()}


def stage_state(root, loop):
    try:
        return json.loads((root/STAGE_STATE).read_text()).get(loop, {})
    except (OSError, ValueError):
        return {}


def save_stage_state(root, loop, identities):
    path = root/STAGE_STATE
    try:
        state = json.loads(path.read_text())
    except (OSError, ValueError):
        state = {}
    state[loop] = identities
    path.write_text(json.dumps(state, indent=1) + '\n')


def stale_stages(root, loop, stage_scripts, skipped, g=None):
    """Skipped stages whose inputs changed since they last ran (or that never ran): they cannot be reused."""
    g = g or graph(root); recorded = stage_state(root, loop)
    return [n for n in skipped if recorded.get(n) != stage_inputs(root, stage_scripts[n], g)]


def run_tests(root, names):
    """Run the named test modules in one process; returns the unittest exit code."""
    if not names:
        return 0
    argv = [sys.executable, '-m', 'unittest', '-q', *names]
    return subprocess.call(argv, cwd=root/'tests')


if __name__ == '__main__':
    print(json.dumps(plan(paths=sys.argv[1:] or None), indent=1))
