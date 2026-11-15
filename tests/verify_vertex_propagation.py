"""Vertex single-source regression (owner brief 2026-11-14), run on demand like verify_rebuild.py: never touches production.

In a temporary copy of the project: change one shared engine parameter (closure coil C1 radius), ask tools/checks.py what to rebuild,
rebuild exactly that, then verify the change in all four linked engine instances of the vehicle, in the exported runtime GLB, in the
Explore Ship part-inspection manifest and geometry (vertex_inspect), in the Engineering page's Engine anatomy section, and that a part
link (part=N3.VTX_C1_Winding) resolves to the right engine: the inspection manifest's placement of each engine lands on that engine's GLB
node. Engine 1.2 extends the chain through the structural calculation: the changed coil changes the coil forces and the C1 strut loads
(vertex_structure), the inspection manifest's engineering records and the Engineering page's Structure section carry the new numbers, and
the production source still gives the old ones. The copy is discarded (the restore); the production TOML and assets are checked
unchanged afterwards.

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


def mat_mul(a, b):
    return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def local_matrix(node):
    """A glTF node's local 4x4 (rows): its matrix, or translation x rotation x scale."""
    if 'matrix' in node:
        m = node['matrix']; return [[m[c*4+r] for c in range(4)] for r in range(4)]
    x, y, z, w = node.get('rotation', [0, 0, 0, 1]); sx, sy, sz = node.get('scale', [1, 1, 1]); tx, ty, tz = node.get('translation', [0, 0, 0])
    R = [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]
    return [[R[r][0]*sx, R[r][1]*sy, R[r][2]*sz, (tx, ty, tz)[r]] for r in range(3)]+[[0, 0, 0, 1]]


def world_centres(doc, names):
    """World-space centre of each named node's mesh bounds (the GLB scene frame is the runtime frame)."""
    parent = {c: i for i, n in enumerate(doc['nodes']) for c in n.get('children', [])}
    out = []
    for i, n in enumerate(doc['nodes']):
        if n.get('name', '') not in names or 'mesh' not in n:
            continue
        m, j = local_matrix(n), i
        while j in parent:
            j = parent[j]; m = mat_mul(local_matrix(doc['nodes'][j]), m)
        lo = [min(doc['accessors'][p['attributes']['POSITION']]['min'][k] for p in doc['meshes'][n['mesh']]['primitives']) for k in range(3)]
        hi = [max(doc['accessors'][p['attributes']['POSITION']]['max'][k] for p in doc['meshes'][n['mesh']]['primitives']) for k in range(3)]
        c = [(a+b)/2 for a, b in zip(lo, hi)]
        out.append([sum(m[r][k]*c[k] for k in range(3))+m[r][3] for r in range(3)])
    return out


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
        # Explore Ship's part inspection, from the same changed source: the record, its own mesh in the geometry buffer, the link per engine.
        import vertex_inspect as vi; importlib.reload(vi)
        man, geo = vi.manifest(s)
        rec = next(p for p in man['parts'] if p['name'] == 'VTX_C1_Winding')
        v0, nv = rec['geo'][:2]
        pts = struct.unpack_from(f'<{3*nv}h', geo, 6*v0)
        inspect_r = max(((pts[3*i+1]*vi.QUANTUM)**2+(pts[3*i+2]*vi.QUANTUM)**2)**0.5 for i in range(nv))    # runtime (x, z, -y): radius in y, z
        assert abs(inspect_r-want) < 2e-3, (inspect_r, want)
        assert abs(max(abs(rec['bounds'][0][2]), abs(rec['bounds'][1][2]))-want) < 2e-3, rec['bounds']
        centre_local = [(a+b)/2 for a, b in zip(*rec['bounds'])]
        drawn = world_centres(doc, nodes)
        links = {}
        for e in man['engines']:
            m = e['matrix']; at = [sum(m[k*4+r]*centre_local[k] for k in range(3))+m[12+r] for r in range(3)]
            near = min(drawn, key=lambda c: sum((a-b)**2 for a, b in zip(c, at)))
            links[e['name']] = dict(offset_m=round(sum((a-b)**2 for a, b in zip(near, at))**0.5, 4), node=drawn.index(near))
        assert len({v['node'] for v in links.values()}) == 4 and all(v['offset_m'] < 0.05 for v in links.values()), links
        sys.path.insert(0, str(root/'tools'))
        import story; importlib.reload(story)
        section = story.engine_anatomy(s, vi)
        assert 'id="anatomy-magnetic-coils"' in section and 'C1 winding' in section, 'Engine anatomy section lost the closure coil'
        # Engine 1.2: the structural calculation follows the same source change (coil forces -> strut loads -> manifest -> page).
        import vertex_structure as vs; importlib.reload(vs)
        prod = spec_mod.load(ROOT)[0]
        f_new = {c['name']: c['Fz_N'] for c in vs.coil_forces(s, 'NOMINAL')}; f_old = {c['name']: c['Fz_N'] for c in vs.coil_forces(prod, 'NOMINAL')}
        assert abs(f_new['C1']/f_old['C1']-1) > 0.05, (f_new['C1'], f_old['C1'])
        strut_new = next(r for r in vs.engine_members(s, 'NOMINAL')['strut']['rows'] if r['coil'] == 'C1')
        strut_old = next(r for r in vs.engine_members(prod, 'NOMINAL')['strut']['rows'] if r['coil'] == 'C1')
        assert abs(strut_new['N']-strut_old['N']) > 1e3 and abs(strut_new['L']-strut_old['L']) > 1e-3, (strut_new, strut_old)
        eng_new = next(p['eng'] for p in man['parts'] if p['name'] == 'VTX_C1_Strut_1')
        want_eng = next(r for r in vs.part_engineering(s) if r['name'] == 'VTX_C1_Strut_1')
        assert eng_new[0] == want_eng['status'] and abs(eng_new[2]-round(want_eng['u_nominal'], 3)) < 1e-9, (eng_new, want_eng)
        page_new = story.structure_section(s, vs); page_old = story.structure_section(prod, vs)
        row_new = page_new[page_new.index('<td>C1</td>'):][:200]; row_old = page_old[page_old.index('<td>C1</td>'):][:200]
        assert f'{f_new["C1"] / 1e6:,.1f}' in row_new and row_new != row_old, (row_new, row_old)
        structure = dict(c1_force_MN=dict(changed=round(f_new['C1']/1e6, 3), production=round(f_old['C1']/1e6, 3)),
                         c1_strut=dict(force_MN=round(strut_new['N']/1e6, 3), production_MN=round(strut_old['N']/1e6, 3),
                                       length_m=round(strut_new['L'], 3), production_length_m=round(strut_old['L'], 3)),
                         manifest_record=eng_new, engineering_page='Structure section coil table carries the changed C1 force')
        # The restore: the original source gives the original radius again (nothing generated stays behind).
        orig = vi.manifest(spec_mod.load(ROOT)[0])[0]
        restored = next(p for p in orig['parts'] if p['name'] == 'VTX_C1_Winding')['bounds']
        assert abs(max(abs(restored[0][2]), abs(restored[1][2]))-(want-DELTA)) < 2e-3, restored
    after = {p: digest(ROOT/p) for p in before}
    assert after == before, 'production files changed'
    report = dict(check='VERTEX single-source propagation', status='PASS', change=f'vertex_engine.geometry.closure_coils C1 r_m 2.5 -> 2.9 (+{DELTA} m)',
                  selection=dict(build_target=target, tests=sel['tests'], note=sel['note']), vehicle_instances=found, expected_radius_m=want,
                  glb=dict(file=glb.name, nodes=uses, radii_m=sorted(set(round(r, 4) for r in radii))),
                  inspection=dict(part='VTX_C1_Winding', geometry_radius_m=round(inspect_r, 4), part_links=links,
                                  engineering_page='engine_anatomy section names the C1 winding'),
                  structure=structure,
                  restore='temporary copy discarded; production hashes unchanged',
                  seconds=dict(targeted_build=round(build_s, 1), export=round(export_s, 1), total=round(time.time()-t0, 1)))
    if report_path:
        Path(report_path).write_text(json.dumps(report, indent=1)+'\n')
    print(json.dumps(report, indent=1))
    return report


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--report', type=Path)
    main(ap.parse_args().report)
