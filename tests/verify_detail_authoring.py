"""Hand-authored detail in a detail asset (docs/MODULES.md), end to end on a disposable copy of data/ and the saved assets (Blender).

A script-made fixture stands in for a mesh someone modelled by hand in ART_WF_DETAIL_M7_RA1:
1. the detail build keeps it and adopts it (wf_adopted, the pack's labels, pinned to the anchor frame's hash);
2. a second build regenerates the pack's generated detail and keeps the fixture unchanged;
3. a changed contract (interface_version) stops the build with WF_DETAIL_REVIEW;
4. --rebind after review accepts it against the new frame;
5. the export carries it as a production node of the pack.
The geometry baseline never sees it (adopted objects stay outside the fingerprint's `objects`). Prints JSON; exit 0 on PASS.
Usage: python3 tests/verify_detail_authoring.py [--keep]
"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
BLENDER = os.environ.get('WAYFARER_BLENDER', '/snap/bin/blender')
ASSET = 'WF_DETAIL_M7_RA1'
FIXTURE = 'Fixture_Authored_Bracket'


def blender(*args, script=None, expr=None):
    cmd = [BLENDER, '--background', '--factory-startup', '--python-exit-code', '1']
    cmd += ['--python', str(script)] if script else ['--python-expr', expr]
    return subprocess.run(cmd+['--', *map(str, args)], capture_output=True, text=True, timeout=1800)


PROBE = '''
import bpy, json, sys
bpy.ops.wm.open_mainfile(filepath=sys.argv[sys.argv.index("--")+1])
o = bpy.data.objects.get("{fixture}")
print("PROBE", json.dumps(None if o is None else dict(adopted=bool(o.get("wf_adopted")), against=o.get("wf_authored_against"), owner=o.get("wf_owner"),
      pack=o.get("detail_pack"), layer=o.get("layer"), vertices=len(o.data.vertices), collections=[c.name for c in o.users_collection],
      generated=len([x for x in bpy.data.objects if x.get("wf_owner") == "wayfarer.p0"]))))
'''.replace('{fixture}', FIXTURE)

ADD = '''
import bpy, bmesh, sys
path = sys.argv[sys.argv.index("--")+1]
bpy.ops.wm.open_mainfile(filepath=path)
me = bpy.data.meshes.new("{fixture}_Mesh"); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=0.08); bm.to_mesh(me); bm.free()
me.materials.append(bpy.data.materials.new("Fixture_Material"))
o = bpy.data.objects.new("{fixture}", me); o.location = (0.0, -2.87, 0.0)
bpy.data.collections["ART_{asset}"].objects.link(o)
bpy.ops.wm.save_as_mainfile(filepath=path)
'''.replace('{fixture}', FIXTURE).replace('{asset}', ASSET)


def probe(path):
    r = blender(path, expr=PROBE)
    line = next((l for l in r.stdout.splitlines() if l.startswith('PROBE ')), None)
    return json.loads(line[6:]) if line else {'error': r.stdout[-800:]+r.stderr[-800:]}


def anchor_hash(root):
    sys.path.insert(0, str(ROOT/'src/wayfarer'))
    import importlib
    import modules
    importlib.reload(modules)
    from spec import load
    s = load(root)[0]; reg = modules.registry(root)
    return modules.anchor_hash(reg, modules.anchors(s, reg)['WF-RING-A.SECTOR.1.1'])


def main(keep=False):
    tmp = Path(tempfile.mkdtemp(prefix='wf-authoring-'))
    steps = {}; ok = True
    try:
        shutil.copytree(ROOT/'data', tmp/'data')
        shutil.copytree(ROOT/'assets/wayfarer', tmp/'assets/wayfarer', ignore=shutil.ignore_patterns('milestones'))
        path = tmp/'assets/wayfarer/detail'/f'{ASSET}.blend'
        build = lambda *extra: blender('--root', tmp, '--target', 'DETAIL_M7_RA1', *extra, script=ROOT/'src/wayfarer/build/build.py')
        r = blender(path, expr=ADD); steps['add_fixture'] = r.returncode == 0
        r = build(); p = probe(path); h1 = anchor_hash(tmp)
        steps['probe'] = dict(p, anchor=h1, build=r.returncode)
        steps['adopted_on_build'] = r.returncode == 0 and p and p.get('adopted') and p['against'] == h1 and p['owner'] is None and p['pack'] == 'm7_ra1' \
            and p['layer'] == 'PRODUCTION' and p['collections'] == [f'ART_{ASSET}'] and p['generated'] == 4
        r = build(); p2 = probe(path)
        steps['survives_regeneration'] = r.returncode == 0 and p2 == p
        reg = (tmp/'data/modules.toml').read_text()
        (tmp/'data/modules.toml').write_text(reg.replace('interface_version = 1', 'interface_version = 2', 1))
        r = build(); h2 = anchor_hash(tmp)
        steps['contract_change_stops_the_build'] = r.returncode != 0 and 'WF_DETAIL_REVIEW' in (r.stdout+r.stderr) and h2 != h1 \
            and probe(path)['against'] == h1
        r = build('--rebind'); p3 = probe(path)
        steps['probe_rebind'] = dict(p3, anchor=h2, build=r.returncode)
        steps['rebind_after_review'] = r.returncode == 0 and p3['against'] == h2 and p3['vertices'] == p['vertices']
        # The host links the detail at the new contract only after its own rebuild; the export walks the saved files as they are.
        r = blender('--root', tmp, '--target', 'HABITAT', script=ROOT/'src/wayfarer/build/build.py')
        out = tmp/'export'; (tmp/'identity.json').write_text(json.dumps({'fixture': 'verify_detail_authoring'}))
        r = blender('--root', tmp, '--out', out, '--identity', tmp/'identity.json', script=ROOT/'src/wayfarer/export/godot.py')
        nodes = json.loads((out/'manifest.json').read_text())['nodes'] if (out/'manifest.json').is_file() else []
        mine = [n for n in nodes if n.get('source_name') == FIXTURE]
        steps['exported_as_production'] = r.returncode == 0 and len(mine) == 1 and mine[0].get('layer') == 'PRODUCTION' \
            and mine[0].get('pack') == 'm7_ra1' and mine[0].get('detail_class') == 'PRODUCTION'
        if not steps['exported_as_production']:
            steps['export_log'] = (r.stdout+r.stderr)[-1500:]
        ok = all(v is True for k, v in steps.items() if k not in ('export_log', 'probe', 'probe_rebind'))
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps({'result': 'PASS' if ok else 'FAIL', 'steps': steps, 'workspace': str(tmp) if keep else 'removed'}, indent=1))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main('--keep' in sys.argv))
