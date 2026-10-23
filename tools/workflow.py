"""Wayfarer workflow CLI: input status, source lookup, Drive sync and the build pipeline.

Subcommands delegate to `drive_sync.py` (Drive drift/capture/delta/commit) and
`pipeline.py` (build, checks, previews, baseline); see AGENTS.md for the loop
and docs/IMPLEMENTATION.md for details.
"""
import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
sys.path.insert(0, str(ROOT / 'tools'))
from spec import load


def parameter_refs(value, path=''):
    """List explicit source/evidence references, including entries inside lists."""
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f'{path}.{key}' if path else key
            if key in ('source_ref', 'evidence_ref') and isinstance(child, str):
                yield child, child_path
            else:
                yield from parameter_refs(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from parameter_refs(child, f'{path}[{index}]')


def source_rows(root, query):
    # Read-only routing also works while inputs are being repaired; status validates.
    spec = tomllib.loads((root / 'data/wayfarer_3d.toml').read_text())
    sources = tomllib.loads((root / 'data/source_map.toml').read_text())['sources']
    consumers = defaultdict(list)
    for ref, path in parameter_refs(spec):
        consumers[ref].append(path)
    rows = []
    for ident, source in sources.items():
        row = {'source_id': ident}
        for key in ('workbook', 'workbook_id', 'url', 'sheet', 'range',
                    'canon_status', 'inspected_on', 'reverified_on', 'revision_id', 'capture'):
            if key in source:
                row[key] = source[key]
        row['parameter_refs'] = consumers[ident]
        searchable = json.dumps([ident, source, consumers[ident]], ensure_ascii=False).casefold()
        if query.casefold() in searchable:
            rows.append(row)
    return rows


def status(root):
    spec, sources, _, _ = load(root)
    hashes = {name: hashlib.sha256((root / 'data' / name).read_bytes()).hexdigest()
              for name in ('wayfarer_3d.toml', 'source_map.toml')}
    return {
        'validation': 'PASS',
        'scope': 'offline inputs only; Drive freshness and saved Blender assets NOT checked',
        'schema_version': spec['schema_version'],
        'representation': spec['representation'],
        'input_sha256': hashes,
        'source_records': len(sources['sources']),
        'source_statuses': dict(sorted(Counter(s['canon_status'] for s in sources['sources'].values()).items())),
        'capture_manifests': [str(p.relative_to(root)) for p in
                              sorted((root / 'references').glob('drive_capture_*/manifest.json'))],
    }


@contextmanager
def write_lock(root):
    """Hold the root's persistent lock inode (never unlink it); yields None when busy."""
    with (root / '.wayfarer-write.lock').open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield None
            return
        lock.seek(0)
        lock.truncate()
        lock.write(f'pid={os.getpid()}\n')
        lock.flush()
        yield lock


def positive_int(text):
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError('must be at least 1')
    return value


def dense_json(value, indent=0, width=170):
    """JSON that keeps any container fitting in `width` on one line (terse agent output)."""
    flat = json.dumps(value, ensure_ascii=False)
    if len(flat) + indent <= width or not isinstance(value, (dict, list)) or not value:
        return flat
    pad, inner = ' ' * indent, ' ' * (indent + 1)
    if isinstance(value, dict):
        items = [f'{inner}{json.dumps(k, ensure_ascii=False)}: {dense_json(v, indent + 1, width).lstrip()}'
                 for k, v in value.items()]
        return '{\n' + ',\n'.join(items) + f'\n{pad}}}'
    items = [f'{inner}{dense_json(v, indent + 1, width).lstrip()}' for v in value]
    return '[\n' + ',\n'.join(items) + f'\n{pad}]'


def emit(result):
    print(dense_json(result))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, default=ROOT, help='input / lock root and command cwd')
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('status', help='validate local inputs and print compact snapshot identity')
    readback_parser = commands.add_parser('readback', help='measure the saved vehicle for the owner (READBACK-001): CSV + summary')
    readback_parser.add_argument('--install', action='store_true', help='copy the result to references/p1_readback.*')
    route_parser = commands.add_parser('route-import', help='import the sheet-computed First Ignition route (NAV-001, 23_ROUTE_FRAMES)')
    route_parser.add_argument('--check', action='store_true', help='only report whether the written import is current')
    frames_parser = commands.add_parser('frames-import', help='FLIGHT-FRAMES-2026-10-10 channel contract: released Sheets channels, else UNKNOWN')
    frames_parser.add_argument('--check', action='store_true', help='only report whether the written contract is current')
    re_parser = commands.add_parser('runtime-export', help='build disposable COAST/DOCKED snapshots, export GLBs, verify in Godot and publish')
    re_parser.add_argument('--eye-layout', choices=['r24'], help='H03: publish a labelled STUDY package with this Eye layout (workspace only, '
                                                                  'whole-ship inspection added); a plain runtime-export restores canon')
    rc_parser = commands.add_parser('runtime-check', help='run Godot checks against the published package if its inputs are current')
    rc_parser.add_argument('names', nargs='*', help="check names (runtime_export.CHECKS), 'auto' for the change selection; default all")
    web_parser = commands.add_parser('web', help='WEB-001/002: the static website (start page, Explore Ship viewer, Enter Wayfarer Godot '
                                                  'Web build, review page, release.json) from the saved assets')
    web_parser.add_argument('--out', type=Path, help='site directory (default runs/<stamp>-web/site)')
    web_parser.add_argument('--pipeline-run', type=Path, help='the PASS pipeline run that built the assets; recorded in build.json')
    web_parser.add_argument('--no-draco', action='store_true', help='plain GLB (about 5x larger)')
    web_parser.add_argument('--no-play', action='store_true', help='leave out Enter Wayfarer (no Godot toolchain needed)')
    web_parser.add_argument('--native', action='store_true', help='also export the same Demonstrator 01 package as a native Linux build (zip in the run)')
    web_parser.add_argument('--no-native-check', action='store_true', help="skip Demonstrator 01's native check on the web package")
    web_parser.add_argument('--reuse-play', type=Path, help='a previous verified site: reuse its Enter Wayfarer files when the play '
                                                            'inputs are unchanged (web_play.input_key)')
    web_parser.add_argument('--reuse-native', type=Path, help='that release\'s native Linux zip (needed with --native to reuse)')
    prune_parser = commands.add_parser('prune', help='list run directories AGENTS.md step 6 would allow deleting (sizes); deletes nothing '
                                                     'unless --delete names approved candidates')
    prune_parser.add_argument('--delete', nargs='+', metavar='RUN', help='delete these listed candidates (only after the user approved them)')
    deps_parser = commands.add_parser('deps', help='external character dependencies (assets/external/manifest.toml)')
    deps_parser.add_argument('op', nargs='?', default='status', choices=['status', 'fetch', 'install'])
    deps_parser.add_argument('--optional', action='store_true', help='also fetch the optional references')
    char_parser = commands.add_parser('characters', help='build, review, export and Godot-check the MPFB humans; fit them in the vehicle')
    char_parser.add_argument('--only', nargs='*', help='[human.<id>] recipes of data/characters.toml (default all)')
    char_parser.add_argument('--no-fit', action='store_true', help='skip the in-vehicle fit (it reads the vehicle under the write lock)')
    char_parser.add_argument('--stages', nargs='+', metavar='STAGE', help='run only these stages (character_loop.STAGES); skipped ones must be current')
    eva_parser = commands.add_parser('eva', help='EVA-001: build the suited induction pair, check coverage/envelope/holds, render, export')
    eva_parser.add_argument('--no-renders', action='store_true'); eva_parser.add_argument('--no-route', action='store_true')
    eva_parser.add_argument('--only', nargs='+', metavar='STAGE', help='run only these stages; skipped ones must be current (eva_loop.STAGES)')
    source_parser = commands.add_parser('sources', help='find source rows and their explicit parameter references')
    source_parser.add_argument('query', nargs='?', default='')
    source_parser.add_argument('--limit', type=positive_int, default=12)

    drift_parser = commands.add_parser('drift', help='compare Drive metadata saved by the hook with data/source_sync.json')
    drift_parser.add_argument('--since', help='only metadata observed at/after this UTC time (run start)')
    capture_parser = commands.add_parser('capture', help='copy hook-saved workbook exports into an evidence capture')
    capture_parser.add_argument('capture_dir')
    capture_parser.add_argument('--since', help='only exports saved at/after this UTC time')
    capture_parser.add_argument('--keys', nargs='*', help='limit to these source_sync workbook keys')
    capture_parser.add_argument('--file', action='append', default=[], metavar='KEY=PATH',
                                help='ingest a saved connector response or xlsx for KEY instead')
    delta_parser = commands.add_parser('delta', help='cell-level delta of a capture against the sync baselines')
    delta_parser.add_argument('capture_dir')
    sync_parser = commands.add_parser('sync', help='record a capture as incorporated into the model data')
    sync_parser.add_argument('op', choices=['commit'])
    sync_parser.add_argument('capture_dir')
    sync_parser.add_argument('--workbooks', nargs='*', help='commit only these workbook keys')
    sync_parser.add_argument('--note', help='what was done with it, e.g. "no model change: editorial"')

    pipe = commands.add_parser('pipeline', help='spec → tests → build → inspect → fingerprint diff → report → previews')
    pipe.add_argument('--quick', action='store_true', help='modeling loop: spec → selected tests → build → geometry diff → draft COAST previews')
    pipe.add_argument('--run-dir', type=Path, help='default runs/<stamp>-pipeline')
    pipe.add_argument('--target', default='all', help="build.py --target (component, subsystem or vehicle); 'auto' (--quick) from the change selection")
    pipe.add_argument('--tests', choices=['auto', 'all', 'none'], help='--quick only: change-selected tests (default auto), all or none')
    pipe.add_argument('--inspect', nargs='+', help="--quick only: 'auto' (change-selected groups), 'all', 'none' (default) or inspect.py groups")
    pipe.add_argument('--quality', choices=['draft', 'material', 'review', 'look'], help='preview quality (default: draft with --quick, review otherwise)')
    pipe.add_argument('--base', default='HEAD', help='revision the change selection compares against')
    pipe.add_argument('--previews', nargs='*', default=['auto'],
                      help="'auto' (COAST when --quick, else COAST and HIGH_POWER if geometry changed), 'none', or presets")
    pipe.add_argument('--views', nargs='+', default=list(pipeline_views()))
    pipe.add_argument('--size', type=int, default=512)
    pipe.add_argument('--expect', nargs='*', default=[], help='object/file prefixes whose geometry may change; any other change fails the run')
    checks_parser = commands.add_parser('checks', help='which tests, build target, inspection groups and Godot checks a change needs')
    checks_parser.add_argument('paths', nargs='*', help='changed paths (default: working tree against --base, plus untracked files)')
    checks_parser.add_argument('--base', default='HEAD')
    checks_parser.add_argument('--run', action='store_true', help='run the selected unit tests')
    report_parser = commands.add_parser('report', help='compact scene report of a saved inspect JSON (no Blender)')
    report_parser.add_argument('--validation', type=Path, help='default references/p1_validation.json')
    module_parser = commands.add_parser('module', help='modular detail (docs/MODULES.md): list, show, contracts, build, validate, preview, '
                                                       'publish or rebind a module, detail pack or assembly')
    module_parser.add_argument('op', choices=['list', 'show', 'contracts', 'build', 'validate', 'preview', 'publish', 'rebind'])
    module_parser.add_argument('ident', nargs='?', help='a module ID (WF-RING-A), a pack name (m7_ra1) or an assembly ID (M7.RA1)')
    module_parser.add_argument('--integrate', action='store_true', help='build: also rebuild the hosts that link the detail, and the vehicle')
    module_parser.add_argument('--write', action='store_true', help='contracts: rewrite simulations/wf_module_contracts.json')
    module_parser.add_argument('--no-blender', action='store_true', help='validate: the pure screens only')
    module_parser.add_argument('--views', nargs='+', help="preview: views (default: the pack's declared views)")
    module_parser.add_argument('--quality', default='draft', choices=['draft', 'material', 'review', 'look'])
    assembly_parser = commands.add_parser('assembly', help='the assembled ship against the module publication records (docs/MODULES.md)')
    assembly_parser.add_argument('op', choices=['validate'])
    accept_parser = commands.add_parser('accept', help='make a PASS full production run the new geometry baseline')
    accept_parser.add_argument('run_dir', type=Path)
    accept_parser.add_argument('name')
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.action == 'status':
            emit(status(root))
        elif args.action == 'readback':
            import readback
            result = readback.run(root, args.install)
            emit(result)
            return {'PASS': 0, 'BUSY': 75}.get(result['result'], 1)
        elif args.action == 'route-import':
            import route_import
            try:
                result = route_import.run(root, args.check)
            except ValueError as e:
                result = {'result': 'REFUSED', 'reason': str(e)}
            emit(result)
            return 0 if result['result'] in ('PASS', 'CURRENT') else 1
        elif args.action == 'frames-import':
            import frames_import
            try:
                result = frames_import.run(root, args.check)
            except ValueError as e:
                result = {'result': 'REFUSED', 'reason': str(e)}
            emit(result)
            return 0 if result['result'] in ('PASS', 'CURRENT') else 1
        elif args.action == 'runtime-export':
            import runtime_export
            result = runtime_export.run(root, eye_layout=args.eye_layout)
            emit(result)
            return {'PASS': 0, 'BUSY': 75}.get(result['result'], 1)
        elif args.action == 'web':
            import web_export
            result = web_export.run(root, args.out, args.pipeline_run, draco=not args.no_draco, with_play=not args.no_play,
                                    native=args.native, native_check=not args.no_native_check,
                                    reuse=args.reuse_play, reuse_native=args.reuse_native)
            emit(result)
            return {'PASS': 0, 'BUSY': 75}.get(result['result'], 1)
        elif args.action == 'runtime-check':
            import runtime_export
            names = args.names
            if names == ['auto']:
                import checks
                names = checks.plan(root)['runtime_checks']
                if not names:
                    emit({'result': 'PASS', 'note': 'no Godot file in the change selection; nothing to check'})
                    return 0
            result = runtime_export.check(root, names)
            emit(result)
            return {'PASS': 0, 'BUSY': 75}.get(result['result'], 1)
        elif args.action == 'prune':
            import runtime_export
            candidates = runtime_export.prune_candidates(root)
            if args.delete:
                listed = {Path(c['path']).name: c for c in candidates}
                missing = [n for n in args.delete if Path(n).name not in listed]
                if missing:
                    raise ValueError(f'not current prune candidates: {missing}')
                with write_lock(root) as lock:
                    if lock is None:
                        emit({'result': 'BUSY', 'reason': 'never prune while a build or export runs'})
                        return 75
                    import shutil
                    for n in args.delete:
                        target = root / listed[Path(n).name]['path']
                        shutil.rmtree(target) if target.is_dir() else target.unlink()
                emit({'deleted': args.delete})
            else:
                emit({'candidates': len(candidates), 'total_mb': round(sum(c['bytes'] for c in candidates) / 1e6, 1),
                      'rule': 'AGENTS.md step 6: keeps the newest passing pipeline and runtime runs, runs named in TODO, docs, references or '
                              'memory, runs/drive_inbox and *-pre-* backups; runs/ is untracked, so deletion is not recoverable from Git',
                      'paths': [f"{c['path']} {c['bytes'] / 1e6:.1f} MB" for c in candidates]})
        elif args.action == 'eva':
            import eva_loop
            result = eva_loop.run(root, not args.no_renders, not args.no_route, args.only)
            emit(result)
            return {'PASS': 0, 'BUSY': 75}.get(result['result'], 1)
        elif args.action == 'deps':
            import external
            if args.op == 'status':
                emit(external.status())
            else:
                done = external.fetch(args.optional) + (external.install() if args.op == 'install' else [])
                emit({name: what for name, what in done})
        elif args.action == 'characters':
            import character_loop
            result = character_loop.run(root, args.only, not args.no_fit, args.stages)
            emit(result)
            return 0 if result['result'] == 'PASS' else 1
        elif args.action == 'sources':
            rows = source_rows(root, args.query)
            emit({'scope': 'offline index; explicit references only', 'query': args.query,
                  'total': len(rows), 'shown': min(args.limit, len(rows)), 'sources': rows[:args.limit]})
        elif args.action == 'checks':
            import checks
            result = checks.plan(root, args.paths or None, args.base)
            emit(result)
            if args.run:
                sys.stdout.flush()
                return checks.run_tests(root, result['tests'])
        elif args.action in ('module', 'assembly'):
            import module_flow
            if args.action == 'assembly':
                result = module_flow.run(root, 'assembly-validate')
            else:
                if args.op not in ('list', 'contracts') and not args.ident:
                    raise ValueError(f'module {args.op} needs a module, pack or assembly (module list)')
                result = module_flow.run(root, args.op, args.ident, integrate=args.integrate, write=args.write, views=args.views,
                                         quality=args.quality, blender=not args.no_blender)
            emit(result)
            return {'PASS': 0, 'BUSY': 75}.get(result['result'], 1)
        elif args.action in ('drift', 'capture', 'delta', 'sync'):
            import drive_sync
            if args.action == 'drift':
                emit(drive_sync.drift(root, args.since))
            elif args.action == 'capture':
                emit(drive_sync.capture(root, args.capture_dir, args.since, args.keys, args.file))
            elif args.action == 'delta':
                emit(drive_sync.delta_summary(drive_sync.delta(root, args.capture_dir)))
            else:
                emit(drive_sync.commit(root, args.capture_dir, args.workbooks, args.note))
        else:
            import pipeline
            if args.action == 'pipeline':
                previews = args.previews
                previews = 'auto' if previews == ['auto'] else [] if previews in ([], ['none']) else previews
                if not args.quick and (args.tests or args.inspect or args.target == 'auto'):
                    raise ValueError('--tests, --inspect and --target auto select a scoped --quick run; the full pipeline checks everything')
                inspect = args.inspect[0] if args.inspect and len(args.inspect) == 1 and args.inspect[0] in ('auto', 'all', 'none') else args.inspect
                summary = pipeline.run(root, args.run_dir, args.target, previews, args.views, args.size,
                                       args.expect, args.quick, tests=args.tests, inspect=inspect, quality=args.quality, base=args.base)
                emit(pipeline.compact(summary))
                return {'PASS': 0, 'BUSY': 75}.get(summary['result'], 1)
            if args.action == 'report':
                path = args.validation or root / 'references/p1_validation.json'
                emit(pipeline.scene_report(json.loads(path.read_text()), root=root))
            elif args.action == 'accept':
                emit(pipeline.accept(args.run_dir, args.name, root))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f'Wayfarer workflow failed: {error}', file=sys.stderr)
        return 1


def pipeline_views():
    import pipeline
    return pipeline.WHOLE_SHIP_VIEWS


if __name__ == '__main__':
    sys.exit(main())
