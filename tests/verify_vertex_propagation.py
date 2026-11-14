"""Vertex single-source regression (owner brief 2026-11-14), run on demand like verify_rebuild.py: never touches production.

In a temporary copy of the project: change one shared engine parameter (closure coil C1 radius), ask tools/checks.py what to rebuild,
rebuild exactly that, then verify the change in all four linked engine instances of the vehicle and in the exported runtime GLB. The
copy is discarded (the restore); the production TOML and assets are checked unchanged afterwards.

    python3 tests/verify_vertex_propagation.py [--report references/evidence/vertex_propagation.json]
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
BLENDER = os.environ.get('WAYFARER_BLENDER', '/snap/bin/blender')
DELTA = 0.4
OLD = '{ name = "C1", dx_from_shield_m = -1.0, r_m = 2.5,'
NEW = '{ name = "C1", dx_from_shield_m = -1.0, r_m = 2.9,'
PROBE = '''import bpy, json, math, sys
bpy.ops.wm.open_mainfile(filepath=sys.argv[sys.argv.index('--')+1])
deps = bpy.context.evaluated_depsgraph_get(); out = []
engines = [o for o in bpy.data.objects if o.name.startswith('ENGINE_N')]
for inst in deps.object_instances:
    if inst.is_instance and inst.object.original.name == 'VTX_C1_Winding':
        # the part sits at the engine origin, so its instance matrix is the placed engine's matrix
        eng = min(engines, key=lambda o: (o.matrix_world.translation - inst.matrix_world.translation).length)
        assert (eng.matrix_world.translation - inst.matrix_world.translation).length < 1e-3
        out.append(dict(engine=eng.name, radius=max(math.hypot(v.co.y, v.co.z) for v in inst.object.data.vertices)))
print('WF_PROBE', json.dumps({'instances': out}))
'''


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def blender(*args, cwd=ROOT, timeout=1800):
    r = subprocess.run([BLENDER, '--background', '--factory-startup', '--python-exit-code', '1', *map(str, args)], cwd=cwd, capture_output=True,
                       text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(r.stdout[-3000:]+r.stderr[-3000:])
    return r.stdout


def glb_radii(path, nodes):
    """Max radius about the local X axis of every glTF mesh primitive of the named nodes (runtime frame x, z, -y; the radius is the same)."""
    data = Path(path).read_bytes(); length = struct.unpack_from('<I', data, 12)[0]
    doc = json.loads(data[20:20+length]); out = []
    for node in doc['nodes']:
        if node.get('name', '') in nodes and 'mesh' in node:
            for prim in doc['meshes'][node['mesh']]['primitives']:
                acc = doc['accessors'][prim['attributes']['POSITION']]
                lo, hi = acc['min'], acc['max']
                out.append(max(abs(lo[1]), abs(hi[1]), abs(lo[2]), abs(hi[2])))
    return out, doc


def main(report_path=None):
    t0 = time.time()
    before = {p: digest(ROOT/p) for p in ('data/wayfarer_3d.toml', 'assets/wayfarer/components/WF_VERTEX_ENGINE.blend', 'assets/wayfarer/WF_WAYFARER_001.blend')}
    with tempfile.TemporaryDirectory(prefix='wayfarer-vertex-') as temp:
        root = Path(temp)/'w'
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('runs', '.godot', 'milestones', '__pycache__', 'web_dist', 'node_modules'), symlinks=True)
        toml = root/'data/wayfarer_3d.toml'; text = toml.read_text()
        assert text.count(OLD) == 1, 'C1 line not found'
        toml.write_text(text.replace(OLD, NEW))
        sys.path.insert(0, str(root/'tools'))
        import checks
        sel = checks.plan(root, paths=['data/wayfarer_3d.toml'])
        target = sel['build_target']
        assert target and target != 'all' and target.startswith('VERTEX_ENGINE'), f'selection did not scope the engine change: {target}'
        t1 = time.time(); blender('--python', root/'src/wayfarer/build/build.py', '--', '--root', root, '--target', target); build_s = time.time()-t1
        probe = Path(temp)/'probe.py'; probe.write_text(PROBE)
        raw = blender('--python', probe, '--', root/'assets/wayfarer/WF_WAYFARER_001.blend')
        found = json.loads(next(l for l in raw.splitlines() if l.startswith('WF_PROBE'))[9:])['instances']
        sys.path.insert(0, str(root/'src/wayfarer'))
        import importlib
        import spec as spec_mod; importlib.reload(spec_mod)
        import vertex_engine as ve; importlib.reload(ve)
        s = spec_mod.load(root)[0]
        part = next(p for p in ve.parts(s) if p['name'] == 'VTX_C1_Winding'); want = part['R']+part['a']
        engines = sorted(i['engine'] for i in found if i['engine'])
        assert engines == ['ENGINE_N1', 'ENGINE_N2', 'ENGINE_N3', 'ENGINE_N4'], found
        assert all(abs(i['radius']-want) < 2e-3 for i in found), (found, want)
        pkg = Path(temp)/'pkg'; ident = Path(temp)/'build_identity.json'
        ident.write_text(json.dumps({'purpose': 'verify_vertex_propagation (temporary copy)'}))
        t2 = time.time(); blender('--python', root/'src/wayfarer/export/godot.py', '--', '--root', root, '--out', pkg, '--identity', ident, timeout=3600); export_s = time.time()-t2
        glb = next(pkg.glob('*.glb'))
        # the export names nodes WF_<hash>; the manifest maps each node back to its source object
        nodes = {r['node'] for r in json.loads((pkg/'manifest.json').read_text())['nodes'] if r['source_name'] == 'VTX_C1_Winding'}
        radii, doc = glb_radii(glb, nodes)
        uses = sum(1 for n in doc['nodes'] if n.get('name', '') in nodes)
        assert uses >= 4 and radii and all(abs(r-want) < 2e-3 for r in radii), (uses, radii, want)
    after = {p: digest(ROOT/p) for p in before}
    assert after == before, 'production files changed'
    report = dict(check='VERTEX single-source propagation', status='PASS', change=f'vertex_engine.geometry.closure_coils C1 r_m 2.5 -> 2.9 (+{DELTA} m)',
                  selection=dict(build_target=target, tests=sel['tests'], note=sel['note']), vehicle_instances=found, expected_radius_m=want,
                  glb=dict(file=glb.name, nodes=uses, radii_m=sorted(set(round(r, 4) for r in radii))), restore='temporary copy discarded; production hashes unchanged',
                  seconds=dict(targeted_build=round(build_s, 1), export=round(export_s, 1), total=round(time.time()-t0, 1)))
    if report_path:
        Path(report_path).write_text(json.dumps(report, indent=1)+'\n')
    print(json.dumps(report, indent=1))
    return report


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--report', type=Path)
    main(ap.parse_args().report)
