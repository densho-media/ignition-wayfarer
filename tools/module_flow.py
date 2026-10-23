"""Module workflow (docs/MODULES.md): list, show, contracts, build, validate, preview, publish and rebind a module or detail pack, and validate
the assembled ship against the publication records. `python3 tools/workflow.py module|assembly ...` calls `run()`.

A module session builds only its own detail assets (`build`; `--integrate` also rebuilds the hosts that link them and the vehicle),
checks them (`validate`: the pure screens, envelopes and registry, then a Blender readback of the saved files), looks at them (`preview`) and
records a validated candidate (`publish` writes references/modules/<pack>.json: inputs, contract, anchors, git revision and the fingerprint
of its detail assets). `assembly validate` compares every pack's saved assets with its record, so an unpublished, stale or contract-
incompatible module is reported instead of silently entering the ship. Each Blender step logs under runs/<stamp>-module-<ident>/ and holds
the project's write lock, like the pipeline.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(TOOLS)]
import modules
import pipeline

RECORDS = 'references/modules'


def selection(root, ident):
    """(module, packs, assemblies) of a module ID, pack name or assembly ID."""
    mid, names = modules.module_of(root, ident)
    asm = {a: t for a, t in modules.assemblies(modules.packs(root)).items() if t['pack'] in names}
    if ident in asm:
        asm = {ident: asm[ident]}
    return mid, names, asm


def blender_step(run_dir, name, script, *args, lock=None, timeout=pipeline.STEP_TIMEOUT):
    run_dir.joinpath('logs').mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    code = pipeline.subprocess_runner(pipeline.blender(script, *args), run_dir/'logs'/f'{name}.log', ROOT, timeout,
                                      pass_fds=(lock.fileno(),) if lock else ())
    return code, round(time.monotonic()-t0, 1)


def log_tail(run_dir, name, n=6):
    lines = (run_dir/'logs'/f'{name}.log').read_text(errors='replace').splitlines()
    return [l for l in lines if any(w in l for w in ('WF_', 'Error', 'error', 'Traceback', 'assert'))][-n:] or lines[-n:]


def build(root, ident, integrate=False, rebind=False, run_dir=None, lock=None):
    """Rebuild the selection's detail assets; --integrate rebuilds each host that links them (its details, the host and the vehicle)."""
    mid, names, asm = selection(root, ident)
    run_dir = run_dir or root/'runs'/f'{pipeline.stamp()}-module-{ident}'
    steps = []
    script = root/'src/wayfarer/build/build.py'
    targets = sorted({modules.anchor_host(t['anchor']) for t in asm.values()}) if integrate else [modules.target(a) for a in sorted(asm)]
    for target in targets:
        code, secs = blender_step(run_dir, f'build-{target}', script, '--root', root, '--target', target, *(['--rebind'] if rebind else []), lock=lock)
        steps.append(dict(target=target, result='PASS' if code == 0 else 'FAIL', seconds=secs,
                          **({} if code == 0 else {'log': log_tail(run_dir, f'build-{target}')})))
        if code:
            break
    ok = all(q['result'] == 'PASS' for q in steps)
    return dict(result='PASS' if ok else 'FAIL', module=mid, packs=names, assemblies=sorted(asm), steps=steps, run_dir=str(run_dir),
                note='hosts and the vehicle rebuilt; run pipeline --quick --target auto for the diff and previews' if integrate else
                     'detail assets only; the hosts and vehicle see them through their links')


def validate_pure(root, ident):
    """Registry, contract, envelope and clearance screens of the selection, without Blender."""
    from spec import load
    import production_detail as pd
    s = load(root)[0]; mid, names, asm = selection(root, ident)
    fails = [f for f in modules.validate(s, root, legacy=pd.ASSEMBLIES) if any(n in f for n in [mid, *names, *asm]) or 'cycle' in f]
    out = {}
    for a in sorted(asm):
        screens = pd.check(s, a); env = modules.envelope_fails(s, a)
        out[a] = dict(elements=len(pd.elements(s, a)), enabled=pd.enabled(s, a), maturity=pd.scope(s, a)['maturity'],
                      screens=screens[:12], envelope=env[:12])
        fails += screens+env
    return dict(result='FAIL' if fails else 'PASS', fails=fails[:40], assemblies=out)


def validate(root, ident, run_dir=None, lock=None, blender=True):
    mid, names, asm = selection(root, ident)
    run_dir = run_dir or root/'runs'/f'{pipeline.stamp()}-module-{ident}'
    pure = validate_pure(root, ident)
    result = dict(module=mid, packs=names, pure=pure, run_dir=str(run_dir))
    ok = pure['result'] == 'PASS'
    if blender and asm:
        out = run_dir/'detail_readback.json'
        code, secs = blender_step(run_dir, 'detail-readback', root/'src/wayfarer/validation/detail_readback.py', '--root', root,
                                  '--assemblies', *sorted(asm), '--out', out, lock=lock)
        saved = json.loads(out.read_text()) if out.is_file() else {}
        result['saved'] = saved; result['readback_seconds'] = secs
        ok = ok and code == 0 and saved and all(v['result'] == 'PASS' for v in saved.values())
        if code and not saved:
            result['log'] = log_tail(run_dir, 'detail-readback')
    result['result'] = 'PASS' if ok else 'FAIL'
    return result


def preview(root, ident, views=None, quality='draft', run_dir=None, lock=None):
    """The pack's declared views (or the given ones) plus the whole ship side view, from the saved assets."""
    mid, names, asm = selection(root, ident)
    packs_ = modules.packs(root)
    views = views or sorted({v for n in names for v in packs_[n]['pack'].get('views', [])}) or ['threequarter']
    views = ['side', *[v for v in views if v != 'side']]
    run_dir = run_dir or root/'runs'/f'{pipeline.stamp()}-module-{ident}'
    out = run_dir/'previews'
    from spec import load
    s = load(root)[0]; anc = modules.anchors(s)
    sector = sorted({anc[t['anchor']]['function'] for t in asm.values() if anc[t['anchor']]['family'] == 'ring_sector'})
    inner = [v for v in views if v in ('plan', 'section', 'cutaway', 'overhead')]
    if sector and inner:
        # A ring-sector pack: its sector and interior with the detail linked, in the sector frame (presentation/interior_preview.py).
        code, secs = blender_step(run_dir, 'interior-preview', root/'src/wayfarer/presentation/interior_preview.py', '--root', root,
                                  '--functions', *sector, '--views', *inner, '--details', '--size', '768', '--out-dir', out, lock=lock)
        if code:
            return dict(result='FAIL', views=inner, log=log_tail(run_dir, 'interior-preview'), run_dir=str(run_dir))
        views = [v for v in views if v not in inner]
    code, secs = blender_step(run_dir, 'preview', root/'src/wayfarer/presentation/preview.py', '--root', root, '--views', *views,
                              '--quality', quality, '--out-dir', out, lock=lock)
    return dict(result='PASS' if code == 0 else 'FAIL', views=views, seconds=secs,
                previews=[str(p.relative_to(root)) for p in sorted(out.rglob('*.png'))] if out.exists() else [], run_dir=str(run_dir))


def fingerprint_slice(root, assemblies, run_dir, lock=None):
    rel = [f'{modules.ASSET_DIR}/{modules.asset_name(a)}.blend' for a in sorted(assemblies)]
    out = run_dir/'detail_fingerprint.json'
    code, _ = blender_step(run_dir, 'fingerprint', root/'tests/geometry_fingerprint.py', '--root', root, '--output', out, '--only', *rel, lock=lock)
    if code:
        raise ValueError(f'fingerprint failed: {log_tail(run_dir, "fingerprint")}')
    return json.loads(out.read_text())


def record(root, pack, s, fp):
    """The publication record of one pack: what was validated, against which contract, at which revision."""
    reg = modules.registry(root); q = modules.packs(root)[pack]; anc = modules.anchors(s, reg)
    git = lambda *a: subprocess.check_output(['git', '-C', str(root), *a], text=True).strip()
    mine = {a: t for a, t in modules.assemblies(modules.packs(root)).items() if t['pack'] == pack}
    import production_detail as pd
    return {'contract': 'WF_MODULE_PUBLICATION', 'version': 2, 'pack': pack, 'module': q['pack']['module'], 'pack_version': q['pack']['version'],
            'published_utc': pipeline.utc_now(), 'git_revision': git('rev-parse', 'HEAD'), 'git_dirty': bool(git('status', '--porcelain')),
            'inputs_hash': modules.inputs_hash(root, pack), 'spec_sha256': pipeline.sha256(root/'data/wayfarer_3d.toml'),
            'contract_hash': modules.pack_contract(s, reg, modules.packs(root), pack),
            'contract_terms': modules.pack_terms(s, reg, modules.packs(root), pack),
            'assemblies': {a: dict(anchor=t['anchor'], anchor_hash=modules.anchor_hash(reg, anc[t['anchor']]), asset=modules.asset_name(a),
                                   enabled=pd.enabled(s, a), maturity=pd.scope(s, a)['maturity'], detail_class=q['pack']['detail_class'])
                           for a, t in sorted(mine.items())},
            'fingerprint': fp,
            'note': 'A publication makes the pack eligible for integration; it is not an owner acceptance and changes no maturity or canon.'}


def publish(root, ident, lock=None):
    from spec import load
    mid, names, asm = selection(root, ident)
    run_dir = root/'runs'/f'{pipeline.stamp()}-module-{ident}'
    v = validate(root, ident, run_dir, lock)
    if v['result'] != 'PASS':
        return dict(result='REFUSED', reason='module validate failed', validation=v)
    s = load(root)[0]; fp = fingerprint_slice(root, asm, run_dir, lock); written = []
    for pack in names:
        mine = {f'{modules.ASSET_DIR}/{modules.asset_name(a)}.blend' for a, t in asm.items() if t['pack'] == pack}
        path = root/RECORDS/f'{pack}.json'; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record(root, pack, s, {k: v for k, v in fp.items() if k in mine}), indent=1, sort_keys=True)+'\n')
        written.append(str(path.relative_to(root)))
    return dict(result='PASS', module=mid, published=written, run_dir=str(run_dir))


def assembly_validate(root, lock=None):
    """Every pack against its publication record: unpublished, stale inputs, a changed contract or anchor, or saved geometry that differs from
    the published fingerprint fail. Packs switched off are still checked (their files are empty but linked)."""
    from spec import load
    compare = pipeline.load_module(ROOT/'tests/compare_fingerprint.py', 'compare_fingerprint').compare
    s = load(root)[0]; reg = modules.registry(root); anc = modules.anchors(s, reg); packs_ = modules.packs(root)
    run_dir = root/'runs'/f'{pipeline.stamp()}-assembly'
    allasm = modules.assemblies(packs_)
    fp = fingerprint_slice(root, allasm, run_dir, lock) if allasm else {}
    out = {}
    for pack, q in packs_.items():
        path = root/RECORDS/f'{pack}.json'; fails = []
        if not path.is_file():
            out[pack] = dict(result='FAIL', fails=[f'unpublished: python3 tools/workflow.py module publish {pack}']); continue
        rec = json.loads(path.read_text())
        if rec['inputs_hash'] != modules.inputs_hash(root, pack):
            fails.append('pack inputs changed since publication: module validate, then module publish')
        if rec['contract_hash'] != modules.pack_contract(s, reg, packs_, pack, anc):
            fails.append(f"the pack's contract (anchor frames, envelopes, scope) changed since publication: review the pack against it, then publish")
        for a, t in rec['assemblies'].items():
            if a not in allasm:
                fails.append(f'{a}: published but no longer in the pack')
            elif t['anchor_hash'] != modules.anchor_hash(reg, anc[allasm[a]['anchor']]):
                fails.append(f'{a}: anchor {t["anchor"]} moved since publication')
        files = set(rec['fingerprint'])|{f'{modules.ASSET_DIR}/{modules.asset_name(a)}.blend' for a, t in allasm.items() if t['pack'] == pack}
        mine = {k: fp[k] for k in files if k in fp}
        diff = compare(rec['fingerprint'], mine)
        if diff['result'] != 'PASS':
            fails.append(f"saved detail differs from the published fingerprint: {sum(len(diff[k]) for k in ('changed', 'added', 'removed', 'files_added', 'files_removed'))} differences")
        out[pack] = dict(result='FAIL' if fails else 'PASS', module=q['pack']['module'], published_utc=rec['published_utc'],
                         git_revision=rec['git_revision'][:10], fails=fails)
    return dict(result='PASS' if all(v['result'] == 'PASS' for v in out.values()) else 'FAIL', packs=out, run_dir=str(run_dir))


def listing(root):
    from spec import load
    import production_detail as pd
    s = load(root)[0]; reg = modules.registry(root); packs_ = modules.packs(root)
    out = {}
    for mid in modules.order(reg):
        m = reg['module'][mid]
        out[mid] = dict(title=m['title'], targets=m['targets'], depends=m.get('depends', []), inspect=m.get('inspect', []),
                        packs={n: dict(assemblies={a: dict(anchor=t['anchor'], enabled=pd.enabled(s, a), maturity=pd.scope(s, a)['maturity'])
                                                   for a, t in q['assembly'].items()},
                                       published=(root/RECORDS/f'{n}.json').is_file())
                               for n, q in packs_.items() if q['pack']['module'] == mid})
    return out


def run(root, op, ident=None, integrate=False, write=False, rebind=False, views=None, quality='draft', blender=True):
    from workflow import write_lock
    from spec import load
    if op == 'list':
        return dict(result='PASS', modules=listing(root))
    if op == 'show':
        return dict(result='PASS', handoff=modules.handoff(load(root)[0], root, ident))
    if op == 'contracts':
        s = load(root)[0]
        if write:
            return dict(result='PASS', written=modules.write(s, root))
        current = json.loads((root/modules.CONTRACTS).read_text()) if (root/modules.CONTRACTS).is_file() else None
        fresh = json.loads(json.dumps(modules.contracts(s, root), sort_keys=True))
        both = modules.combined(s, root)
        return dict(result='PASS' if current == fresh else 'STALE', hashes={k: v['hash'] for k, v in fresh['modules'].items()},
                    packs={k: v['hash'] for k, v in both['packs'].items()},
                    note=None if current == fresh else 'regenerate with --write (a build also rewrites it)')
    if op == 'validate' and not blender:
        return validate(root, ident, blender=False)
    with write_lock(root) as lock:
        if lock is None:
            return dict(result='BUSY', reason='another session holds the build lock')
        if op == 'build':
            return build(root, ident, integrate, lock=lock)
        if op == 'rebind':
            return build(root, ident, rebind=True, lock=lock)
        if op == 'validate':
            return validate(root, ident, lock=lock)
        if op == 'preview':
            return preview(root, ident, views, quality, lock=lock)
        if op == 'publish':
            return publish(root, ident, lock=lock)
        if op == 'assembly-validate':
            return assembly_validate(root, lock=lock)
    raise ValueError(f'unknown module operation {op}')
