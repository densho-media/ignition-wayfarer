"""Module registry, detail packs and attachment contracts (docs/MODULES.md). Pure, standard library.

`data/modules.toml` is the one authoritative registry: the subsystem modules, the existing build targets and source files each owns,
their dependencies, inspection groups and the anchor families they expose. Detail packs are the unit a session owns: each is a manifest
and its parameters in `data/detail/<pack>.toml`, its builders and screens in `src/wayfarer/detail/pack_<pack>.py`, and one asset per
assembly, `assets/wayfarer/detail/WF_DETAIL_<assembly>.blend`, linked into its host at a declared anchor. Packs are discovered by glob, so
adding one edits no shared file.

Anchors are computed from the pure engineering formulas (never read back from a built file): an ID, the host asset, the host object a detail
instance is parented to (None: the host collection's origin) and that object's local matrix (for a moving anchor, a rotor or a despun drum,
its rest frame at the saved pose and its motion). A module's contract is its anchors; a pack's contract is the anchors its assemblies attach
to plus the envelopes and scope it claims. Each pack is stamped and published against its own contract, so a detail asset built (or
hand-authored) against an older frame is detected instead of silently entering the ship, while another pack joining the same module changes
nothing for it. Production detail never feeds engineering budgets: a pack carrying a mass, density or centre-of-mass key is refused.
"""
from fnmatch import fnmatch
import hashlib
import json
import math
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = 'data/modules.toml'
PACK_DIR = 'data/detail'
CODE_DIR = 'src/wayfarer/detail'
ASSET_DIR = 'detail'                   # under assets/wayfarer
CONTRACTS = 'simulations/wf_module_contracts.json'
CONTRACT, VERSION = 'WF_MODULE_CONTRACTS', 2
SCOPES = ('M7', 'M8', 'pack')          # which switch and maturity a pack's assemblies take: [production], [production.m8] or its own
DETAIL_CLASSES = ('BLOCKOUT', 'FUNCTIONAL', 'PRODUCTION', 'HERO')
FORBIDDEN = {'mass', 'mass_kg', 'mass_t', 'density', 'density_kg_m3', 'com', 'com_m', 'centre_of_mass', 'center_of_mass'}
IDENTITY = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]


def registry(root=ROOT):
    return tomllib.loads((Path(root)/REGISTRY).read_text())


def packs(root=ROOT):
    """{pack: manifest} of data/detail/*.toml, each with its name, manifest path and code path added."""
    out = {}
    for p in sorted((Path(root)/PACK_DIR).glob('*.toml')):
        q = tomllib.loads(p.read_text())
        q['name'] = p.stem; q['manifest'] = f'{PACK_DIR}/{p.name}'; q['code'] = f'{CODE_DIR}/pack_{p.stem}.py'
        out[p.stem] = q
    return out


def assemblies(packs_):
    """{assembly: its manifest table plus pack, module and scope}, over every pack."""
    out = {}
    for name, q in packs_.items():
        for a, t in q.get('assembly', {}).items():
            out[a] = dict(t, pack=name, module=q['pack']['module'], scope=q['pack']['scope'])
    return out


def safe(assembly):
    return assembly.replace('.', '_').replace('-', '_')


def asset_name(assembly):
    """The detail asset (scene wf_asset, root collection and file stem) of an assembly."""
    return 'WF_DETAIL_'+safe(assembly)


def target(assembly):
    """Its build target (build.py --target)."""
    return 'DETAIL_'+safe(assembly)


def instance_name(assembly):
    """The collection-instance empty that links the detail asset into its host."""
    return 'Detail_'+safe(assembly)


def anchor_host(anchor):
    """Host build target of an anchor ID: <module>.<TARGET>.ORIGIN, or one of ring module's HABITAT anchors <module>.SECTOR.<ring>.<sector>,
    <module>.ROTOR.<ring> and <module>.DRUM.<ring>."""
    parts = anchor.split('.')
    if parts[-1] == 'ORIGIN':
        return parts[-2]
    if len(parts) >= 3 and parts[-3] == 'SECTOR':
        return 'HABITAT'
    if len(parts) >= 2 and parts[-2] in ('ROTOR', 'DRUM'):
        return 'HABITAT'
    raise ValueError(f'Unknown anchor form {anchor}')


def ring_module(reg, j):
    return next(k for k, m in reg['module'].items() if m.get('ring') == j)


def rx(angle):
    c, s_ = math.cos(angle), math.sin(angle)
    return [[1.0, 0.0, 0.0], [0.0, c, -s_], [0.0, s_, c]]


def matrix(location, rotation=None):
    m = rotation or [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    return [[*m[i], float(location[i])] for i in range(3)]+[[0.0, 0.0, 0.0, 1.0]]


def anchors(s, reg=None, root=ROOT):
    """{anchor ID: dict(module, family, host, object, parent, matrix, ...)} from the pure formulas."""
    import habitat_ring
    import rotor_interface
    import crew_transfer
    reg = reg or registry(root); out = {}
    for mid, m in reg['module'].items():
        for t in m['targets']:
            if t not in ('vehicle', 'CHARACTERS'):
                out[f'{mid}.{t}.ORIGIN'] = dict(module=mid, family='asset_origin', host=t, object=None, parent=None, matrix=IDENTITY)
    for q in habitat_ring.sectors(s):
        # The sector instance in WF_HABITAT (components/revision.py habitat()): radial(0, deck, angle), rotated by angle about +X, under Rotor_j.
        a, d = q['angle'], q['deck_radius']
        mid = ring_module(reg, q['ring'])
        out[f"{mid}.SECTOR.{q['ring']}.{q['index']}"] = dict(module=mid, family='ring_sector', host='HABITAT', object=q['name'],
                                                             parent=f"Rotor_{q['ring']}", function=q['function'],
                                                             matrix=rounded(matrix((0.0, d*math.cos(a), d*math.sin(a)), rx(a)), 12))
    for r in rotor_interface.rotors(s):
        # Rotor_j (components/revision.py habitat()) at the ring centre, turned about +X by its driver; the rest frame is the saved index
        # angle (phase). Drum_j (components/crew.py drum()), the despun transfer drum of a human-entry rotor, sits at the same centre and phase
        # and turns with its ring only while drum_sync is 1. Detail on either inherits that motion through its instance.
        j = r['index']; mid = ring_module(reg, j); m = rounded(matrix((r['x'], 0.0, 0.0), rx(r['phase'])), 12)
        out[f'{mid}.ROTOR.{j}'] = dict(module=mid, family='rotor_frame', host='HABITAT', object=f'Rotor_{j}', parent=None, matrix=m,
                                       motion='ROTOR_SPIN_X', rest_deg=round(math.degrees(r['phase']), 9))
        if crew_transfer.vestibule(s, j)['human']:
            out[f'{mid}.DRUM.{j}'] = dict(module=mid, family='drum_frame', host='HABITAT', object=f'Drum_{j}', parent=None, matrix=m,
                                          motion='DRUM_DESPUN_X', rest_deg=round(math.degrees(r['phase']), 9))
    return out


def rounded(x, nd=9):
    if isinstance(x, float):
        return round(x, nd)+0.0
    if isinstance(x, list):
        return [rounded(v, nd) for v in x]
    if isinstance(x, dict):
        return {k: rounded(v, nd) for k, v in x.items()}
    return x


def digest(obj):
    return hashlib.sha256(json.dumps(rounded(obj), sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:16]


def anchor_hash(reg, anchor):
    """Hash of one anchor's frame: what hand-authored detail on it is pinned to (wf_authored_against)."""
    return digest([reg['interface_version'], anchor])


def contracts(s, root=ROOT, reg=None):
    """Every module's external interface, its anchors, with a hash per module. Integration-owned (simulations/wf_module_contracts.json): it
    changes only when an anchor or the registry does, never when a pack is added or edited, so pack sessions never touch it."""
    reg = reg or registry(root); anc = anchors(s, reg); out = {}
    for mid in reg['module']:
        mine = {k: dict(v, hash=anchor_hash(reg, v)) for k, v in anc.items() if v['module'] == mid}
        out[mid] = dict(anchors=mine, hash=digest([reg['interface_version'], mine]))
    return {'contract': CONTRACT, 'version': VERSION, 'interface_version': reg['interface_version'],
            'note': 'Generated by src/wayfarer/modules.py from the pure formulas and data/modules.toml; never edit by hand. Each pack\'s own '
                    'contract (its anchors, envelopes and scope) is in its publication record, references/modules/<pack>.json.',
            'modules': out}


def pack_terms(s, reg, packs_, pack, anc=None):
    """What a pack's assemblies are attached against: each one's anchor with its frame, its envelope and its scope."""
    anc = anchors(s, reg) if anc is None else anc
    return {a: dict(anchor=t['anchor'], frame=anc.get(t['anchor']), envelope=[t['envelope_min'], t['envelope_max']], scope=t['scope'],
                    host=anchor_host(t['anchor']), asset=asset_name(a))
            for a, t in sorted(assemblies(packs_).items()) if t['pack'] == pack}


def pack_contract(s, reg, packs_, pack, anc=None):
    """Hash of one pack's contract (pack_terms): stamped on its detail assets and kept in its publication record. It changes when one of its
    anchors moves, its envelopes or scope change, or the interface version is bumped; another pack, in the same module or not, never changes it."""
    return digest([reg['interface_version'], pack_terms(s, reg, packs_, pack, anc)])


def combined(s, root=ROOT, reg=None, packs_=None):
    """The integrated view (module contracts): every module's anchors plus every pack's contract, computed in a fixed order from the current
    inputs, so the result does not depend on the order in which packs were developed or merged."""
    reg = reg or registry(root); packs_ = packs(root) if packs_ is None else packs_; anc = anchors(s, reg)
    out = contracts(s, root, reg)
    out['packs'] = {n: dict(module=q['pack']['module'], hash=pack_contract(s, reg, packs_, n, anc), assemblies=pack_terms(s, reg, packs_, n, anc))
                    for n, q in sorted(packs_.items())}
    return out


def write(s, root=ROOT):
    path = Path(root)/CONTRACTS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contracts(s, root), indent=1, sort_keys=True)+'\n')
    return str(path.relative_to(root))


def detail_hosts(root=ROOT, packs_=None):
    """{detail asset stem: host asset stem}: a detail file belongs to the asset it is linked into (rotation, readback, inspection)."""
    packs_ = packs(root) if packs_ is None else packs_
    return {asset_name(a): 'WF_'+anchor_host(t['anchor']) for a, t in assemblies(packs_).items()}


def inputs_hash(root, pack):
    """The pack's own inputs (manifest and code): stamped on its detail assets so an edit is seen as stale without the spec hash."""
    # The manifest comes from the build root (a disposable --root copies data/ only); the code always runs from this source tree.
    h = hashlib.sha256()
    for rel, base in ((f'{PACK_DIR}/{pack}.toml', Path(root)), (f'{CODE_DIR}/pack_{pack}.py', ROOT)):
        p = base/rel
        h.update(rel.encode()); h.update(p.read_bytes() if p.is_file() else b'')
    return h.hexdigest()[:16]


def forbidden_keys(node, path=''):
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k.lower() in FORBIDDEN:
                out.append(f'{path}.{k}')
            out += forbidden_keys(v, f'{path}.{k}')
    elif isinstance(node, list):
        for v in node:
            out += forbidden_keys(v, path)
    return out


def check_packs(packs_, sources=None):
    """Structural problems of the pack manifests alone (spec.load refuses them): sections, scopes, classes, envelopes, unique assemblies,
    resolvable evidence and no mass/density/centre-of-mass key."""
    fails, seen = [], {}
    for name, q in packs_.items():
        p = q.get('pack', {})
        for key in ('module', 'version', 'scope', 'enabled', 'detail_class'):
            if key not in p:
                fails.append(f'{name}: [pack] lacks {key}')
        if p.get('scope') not in SCOPES:
            fails.append(f"{name}: scope {p.get('scope')!r} not in {SCOPES}")
        if p.get('scope') == 'pack':
            fails += [f'{name}: a scope "pack" needs [pack].{k}' for k in ('maturity', 'status', 'evidence_ref') if k not in p]
        if p.get('detail_class') not in DETAIL_CLASSES:
            fails.append(f"{name}: detail_class {p.get('detail_class')!r} not in {DETAIL_CLASSES}")
        if not q.get('assembly'):
            fails.append(f'{name}: no [assembly.<ID>] table')
        for a, t in q.get('assembly', {}).items():
            if a in seen:
                fails.append(f'{name}: assembly {a} already in pack {seen[a]}')
            seen[a] = name
            if 'anchor' not in t:
                fails.append(f'{name}: {a} has no anchor')
            lo, hi = t.get('envelope_min'), t.get('envelope_max')
            if not (isinstance(lo, list) and isinstance(hi, list) and len(lo) == len(hi) == 3 and all(x < y for x, y in zip(lo, hi))):
                fails.append(f'{name}: {a} needs envelope_min < envelope_max (three values, metres, anchor frame)')
        fails += [f'{name}: production detail carries no {k[1:]} (engineering budgets come from the owner workbooks)'
                  for k in forbidden_keys(q)]
        if sources is not None:
            for k in ('evidence_ref', 'source_ref'):
                if k in p and p[k] not in sources.get('sources', {}):
                    fails.append(f'{name}: [pack].{k} {p[k]} does not resolve in data/source_map.toml')
    fails += compatibility(packs_)
    return fails


def compatibility(packs_):
    """Problems between packs, whatever order they were developed or merged in: two assemblies claiming overlapping space on the same
    anchor, and a material key defined by two packs (the shared [production] tables are checked in validate)."""
    fails, asm, mats = [], assemblies(packs_), {}
    on = {}
    for a, t in sorted(asm.items()):
        on.setdefault(t.get('anchor'), []).append(a)
    for anchor, names in sorted(on.items()):
        for i, a in enumerate(names):
            for b in names[i+1:]:
                ta, tb = asm[a], asm[b]
                if ta['pack'] == tb['pack']:
                    continue                     # one pack arranges its own assemblies
                try:
                    lo = [max(x, y) for x, y in zip(ta['envelope_min'], tb['envelope_min'])]
                    hi = [min(x, y) for x, y in zip(ta['envelope_max'], tb['envelope_max'])]
                except (KeyError, TypeError):
                    continue
                if all(x < y for x, y in zip(lo, hi)):
                    fails.append(f"{ta['pack']} {a} and {tb['pack']} {b} claim overlapping space on {anchor} ({[round(v, 3) for v in lo]}.."
                                 f"{[round(v, 3) for v in hi]} m, anchor frame): shrink one envelope, or move both into one pack")
    for name, q in sorted(packs_.items()):
        for k in q.get('materials', {}):
            if k in mats:
                fails.append(f'{name}: material {k} is already defined by pack {mats[k]}: rename it (material keys are global)')
            mats.setdefault(k, name)
    return fails


def owned_files(root, m):
    return sorted({str(p.relative_to(root)) for g in m.get('owns', []) for p in Path(root).glob(g) if p.is_file()})


def validate(s, root=ROOT):
    """Registry and pack problems needing the spec: unknown or cyclic dependencies, a target or file owned twice, an owned glob matching
    nothing, a pack on an unknown module or anchor, its function guard and its code file."""
    root = Path(root); reg = registry(root); mods = reg['module']; fails = []
    shared = {*s.get('production', {}).get('materials', {}), *s.get('production', {}).get('m8', {}).get('materials', {})}
    owner = {}
    for mid, m in mods.items():
        for d in m.get('depends', []):
            if d not in mods:
                fails.append(f'{mid}: depends on unknown {d}')
        for t in m.get('targets', []):
            if t in owner:
                fails.append(f'target {t} owned by {owner[t]} and {mid}')
            owner[t] = mid
        for g in m.get('owns', []):
            if not any(p.is_file() for p in root.glob(g)):
                fails.append(f'{mid}: owns {g}, which matches no file')
    files = {}
    for mid, m in mods.items():
        for f in owned_files(root, m):
            if f in files:
                fails.append(f'{f} owned by {files[f]} and {mid}')
            files[f] = mid
    try:
        order(reg)
    except ValueError as e:
        fails.append(str(e))
    packs_ = packs(root); fails += check_packs(packs_)
    anc = anchors(s, reg)
    for a, t in assemblies(packs_).items():
        if t['module'] not in mods:
            fails.append(f"{t['pack']}: unknown module {t['module']}")
        if t.get('anchor') not in anc:
            fails.append(f"{t['pack']}: {a} anchor {t.get('anchor')} is not an anchor of the registry")
        elif 'function' in t and anc[t['anchor']].get('function') != t['function']:
            fails.append(f"{t['pack']}: {a} expects a {t['function']} sector, {t['anchor']} is {anc[t['anchor']].get('function')}")
        elif anc[t['anchor']]['module'] != t['module'] and t['module'] not in mods[anc[t['anchor']]['module']].get('shared_with', []):
            fails.append(f"{t['pack']}: {a} attaches to {t['anchor']}, an anchor of another module")
    for name, q in packs_.items():
        if not (root/q['code']).is_file():
            fails.append(f"{name}: missing {q['code']}")
        fails += [f'{name}: material {k} is already a shared [production] material: rename it' for k in q.get('materials', {}) if k in shared]
    return fails


def envelope_fails(s, assembly, els=None):
    """Elements of an assembly outside its declared envelope (anchor frame)."""
    import production_detail as pd
    t = assemblies(s.get('detail_packs', {}))[assembly]; lo, hi = t['envelope_min'], t['envelope_max']; out = []
    for q in pd.elements(s, assembly) if els is None else els:
        pts = [q['centre']] if 'text' in q else q['vs']
        bad = [p for p in pts if any(p[i] < lo[i]-1e-9 or p[i] > hi[i]+1e-9 for i in range(3))]
        if bad:
            out.append(f"{q['name']}: {len(bad)} point(s) outside the envelope {lo}..{hi}, e.g. {[round(v, 4) for v in bad[0]]}")
    return out


def order(reg):
    """Modules in dependency order (dependencies first); a cycle raises."""
    mods = reg['module']; done, out, active = set(), [], set()

    def visit(m):
        if m in done:
            return
        if m in active:
            raise ValueError(f'module dependency cycle through {m}')
        active.add(m)
        for d in mods[m].get('depends', []):
            if d in mods:
                visit(d)
        active.discard(m); done.add(m); out.append(m)
    for m in mods:
        visit(m)
    return out


def module_of(root, ident):
    """A module ID, a pack name or an assembly ID -> (module ID, [pack names])."""
    reg = registry(root); packs_ = packs(root); asm = assemblies(packs_)
    if ident in reg['module']:
        return ident, [n for n, q in packs_.items() if q['pack']['module'] == ident]
    if ident in packs_:
        return packs_[ident]['pack']['module'], [ident]
    if ident in asm:
        return asm[ident]['module'], [asm[ident]['pack']]
    raise KeyError(f'{ident} is neither a module, a pack nor an assembly (python3 tools/workflow.py module list)')


def handoff(s, root, ident):
    """The session handoff for a module or pack (docs/MODULES.md template), filled from the registry and the manifests."""
    root = Path(root); reg = registry(root); mid, names = module_of(root, ident); m = reg['module'][mid]; packs_ = packs(root)
    con = contracts(s, root, reg)['modules'][mid]
    deps = sorted({f for d in m.get('depends', []) for f in owned_files(root, reg['module'][d])})
    owned = [f for n in names for f in (packs_[n]['manifest'], packs_[n]['code'])]
    asm = {a: t for a, t in assemblies(packs_).items() if t['pack'] in names}
    pack_only = ident != mid
    return {
        'MODULE': f"{mid}: {m['title']}" + (f" (pack {', '.join(names)})" if pack_only else ''),
        'TASK': '<fill in: the one visible result this session delivers>',
        'SOURCE CONTRACT': dict(file=f'references/modules/{names[0]}.json', hash=pack_contract(s, reg, packs_, names[0]),
                                anchors={k: con['anchors'][k] for k in sorted({t['anchor'] for t in asm.values()})})
                           if pack_only and len(names) == 1 else dict(file=CONTRACTS, hash=con['hash'], anchors=sorted(con['anchors'])),
        'OWNED FILES': owned+([] if pack_only else owned_files(root, m))+[f'assets/wayfarer/{ASSET_DIR}/{asset_name(a)}.blend (local, generated)' for a in asm],
        'READ-ONLY DEPENDENCIES': ['data/modules.toml', 'data/wayfarer_3d.toml', 'src/wayfarer/production_detail.py (shared detail core)',
                                   *(owned_files(root, m) if pack_only else []), *deps],
        'PERMITTED CHANGES': 'the owned files; PROTOTYPE visual choices inside each assembly envelope; new families and materials in the pack',
        'FORBIDDEN CHANGES': 'engineering geometry, anchors, the registry, data/wayfarer_3d.toml canon values, other modules\' files, mass or '
                             'thermal budgets, OPEN/HOLD statuses; physical radiator area never shrinks',
        'DELIVERABLE': {a: dict(asset=asset_name(a), anchor=t['anchor'], envelope=[t['envelope_min'], t['envelope_max']]) for a, t in asm.items()},
        'LOCAL TESTS': [f'python3 tools/workflow.py module validate {ident}', 'python3 -m unittest discover -s tests -k production',
                        f"python3 src/wayfarer/production_detail.py"],
        'INTEGRATION TESTS': [f'python3 tools/workflow.py module build {ident} --integrate',
                              f"python3 tools/workflow.py pipeline --quick --target auto --inspect {' '.join(m.get('inspect', [])) or 'auto'} "
                              f"--expect Prod_ Detail_ WF_DETAIL", f'python3 tools/workflow.py module publish {ident}'],
        'ACCEPTANCE CRITERIA': 'module validate PASS; only the expected prefixes in the geometry diff; previews reviewed whole ship first; '
                               'publication record written; maturity stays a candidate until the owner reviews it',
    }


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load
    s = load()[0]
    print(json.dumps({'problems': validate(s), 'modules': {k: v['hash'] for k, v in contracts(s)['modules'].items()}}, indent=1))
