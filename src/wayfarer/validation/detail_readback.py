"""Module validation readback (docs/MODULES.md): the saved detail assets of some pack assemblies and their links in the hosts (Blender).

Per assembly: the detail asset exists and is current (spec hash, anchor frame, pack inputs), holds only its pack's production detail (finite
vertices, valid faces, a material on every slot) plus adopted hand-authored meshes authored against the current anchor frame; its host links
it once, at the anchor object, with an identity local transform, and the anchor object sits at its pure frame. Reads only; writes the JSON
report given by --out.
"""
from pathlib import Path
import argparse
import json
import math
import sys
import bpy
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build')]
from spec import load, digest
import modules


def identity(m, tol=1e-9):
    return all(abs(m[i][j]-(1.0 if i == j else 0.0)) < tol for i in range(4) for j in range(4))


def mesh_fails(obj):
    out = []
    data = obj.data
    if not data.polygons:
        out.append(f'{obj.name}: no faces')
    if any(not all(math.isfinite(c) for c in v.co) for v in data.vertices):
        out.append(f'{obj.name}: non-finite vertex')
    n = len(data.vertices)
    if any(i >= n for p in data.polygons for i in p.vertices):
        out.append(f'{obj.name}: face index out of range')
    if not data.materials or any(m is None for m in data.materials):
        out.append(f'{obj.name}: empty material slot')
    return out


def check(root, assemblies):
    s, _, spec_text, _ = load(root)
    reg = modules.registry(root); anchors = modules.anchors(s, reg); asm = modules.assemblies(s['detail_packs'])
    assets = root/'assets/wayfarer'; report = {}
    for a in assemblies:
        t = asm[a]; q = anchors[t['anchor']]; name = modules.asset_name(a); fails = []; info = {}
        path = assets/modules.ASSET_DIR/f'{name}.blend'
        if not path.is_file():
            report[a] = dict(result='FAIL', fails=[f'{path.relative_to(root)} missing: python3 tools/workflow.py module build {t["pack"]}'])
            continue
        bpy.ops.wm.open_mainfile(filepath=str(path))
        scene = bpy.context.scene; coll = bpy.data.collections.get(name)
        if scene.get('wf_asset') != name or coll is None:
            fails.append(f'{name}: not a detail asset of {a}')
        else:
            if scene.get('spec_hash') != digest(spec_text):
                fails.append(f'{name}: stale spec (data/wayfarer_3d.toml changed): module build')
            if coll.get('anchor_hash') != modules.anchor_hash(reg, q):
                fails.append(f'{name}: built against another frame of {t["anchor"]}: module build')
            if coll.get('inputs_hash') != modules.inputs_hash(root, t['pack']):
                fails.append(f'{name}: pack {t["pack"]} changed since it was built: module build')
        owned = [o for o in bpy.data.objects if o.library is None and o.get('wf_owner') == 'wayfarer.p0']
        authored = [o for o in bpy.data.objects if o.library is None and o.get('wf_adopted')]
        # The local editable sources of exported authored meshes (module export-authored) stay in SRC_<asset>: never built or exported.
        sources = [o for o in bpy.data.objects if o.library is None and o.get('wf_authored_source')]
        loose = [o.name for o in bpy.data.objects if o.library is None and o.type == 'MESH' and o not in owned+authored+sources]
        if loose:
            fails.append(f'{name}: meshes neither generated nor adopted {loose[:6]}: module build adopts ART_ content')
        for o in owned:
            if o.get('kind') != 'production_detail' or o.get('detail_pack') != t['pack']:
                fails.append(f'{o.name}: not this pack\'s production detail')
            if o.parent is not None:
                fails.append(f'{o.name}: parented; detail sits unparented in the anchor frame')
            if o.type == 'MESH':
                fails += mesh_fails(o)
        # Committed authored meshes (imported from data/detail/<pack>/): one per manifest entry, inside the assembly's envelope.
        imported = [o for o in owned if o.get('family') == 'authored']; lo, hi = t['envelope_min'], t['envelope_max']
        if sorted(o.get('component_id') for o in imported) != sorted(f"{a}.AUTHORED.{e['id']}" for e in t.get('authored', [])):
            fails.append(f'{name}: imported authored meshes {[o.name for o in imported]} do not match the manifest entries: module build')
        for o in imported:
            out = [v.co for v in o.data.vertices if any(v.co[i] < lo[i]-1e-6 or v.co[i] > hi[i]+1e-6 for i in range(3))]
            if out:
                fails.append(f'{o.name}: {len(out)} vertices outside the envelope {lo}..{hi}, e.g. {[round(c, 4) for c in out[0]]}')
        for o in authored:
            fails += mesh_fails(o)
            if o.get('wf_authored_against') != modules.anchor_hash(reg, q):
                fails.append(f'{o.name}: authored against another frame of {t["anchor"]}: review it, then module rebind {t["pack"]}')
        info.update(generated=len(owned)-len(imported), imported=len(imported), authored=len(authored), faces=sum(len(o.data.polygons) for o in owned+authored if o.type == 'MESH'),
                    materials=sorted({m.name for o in owned+authored if o.type == 'MESH' for m in o.data.materials if m}))
        # The host links it at the anchor.
        host = f"WF_{q['host']}"
        hp = next((p for p in (assets/'subsystems'/f'{host}.blend', assets/'components'/f'{host}.blend') if p.is_file()), None)
        if hp is None:
            fails.append(f'{host} missing: build the ship once')
        else:
            bpy.ops.wm.open_mainfile(filepath=str(hp))
            inst = [o for o in bpy.data.objects if o.library is None and o.get('kind') == 'detail_instance' and o.get('detail_assembly') == a]
            if len(inst) != 1:
                fails.append(f'{host}: {len(inst)} instances of {name}: module build {t["pack"]} --integrate')
            else:
                o = inst[0]
                if o.instance_collection is None or o.instance_collection.name != name:
                    fails.append(f'{o.name}: links {o.instance_collection}')
                if (o.parent.name if o.parent else None) != q['object']:
                    fails.append(f'{o.name}: parent {o.parent} is not the anchor object {q["object"]}')
                if not (identity(o.matrix_basis) and identity(o.matrix_parent_inverse)):
                    fails.append(f'{o.name}: not at the anchor (local transform or parent inverse not identity)')
                if o.get('anchor_hash') != modules.anchor_hash(reg, q):
                    fails.append(f'{o.name}: linked against another anchor frame: module build {t["pack"]} --integrate')
                # A moving anchor (rotor, despun drum) is checked at its centre and for a pure +X turn; a fixed one at its whole frame.
                m = o.parent.matrix_basis if q['object'] and o.parent is not None else None
                if m is not None and q.get('motion'):
                    if not (all(abs(m[i][3]-q['matrix'][i][3]) < 1e-6 for i in range(3)) and abs(m[0][0]-1) < 1e-9
                            and all(abs(m[0][k]) < 1e-9 and abs(m[k][0]) < 1e-9 for k in (1, 2))):
                        fails.append(f'{q["object"]}: not at the centre of {t["anchor"]} or not turning about +X')
                elif m is not None and not all(abs(m[i][j]-q['matrix'][i][j]) < 1e-6 for i in range(4) for j in range(4)):
                    fails.append(f'{q["object"]}: not at the anchor frame of {t["anchor"]}')
        report[a] = dict(result='FAIL' if fails else 'PASS', asset=str(path.relative_to(root)), host=host, anchor=t['anchor'], fails=fails, **info)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--root', type=Path, default=ROOT); p.add_argument('--assemblies', nargs='+', required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    r = check(a.root.resolve(), a.assemblies)
    a.out.parent.mkdir(parents=True, exist_ok=True); a.out.write_text(json.dumps(r, indent=1, sort_keys=True)+'\n')
    print('WF_DETAIL_READBACK', {k: v['result'] for k, v in r.items()}, flush=True)
