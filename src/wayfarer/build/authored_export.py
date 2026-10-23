"""Export hand-authored detail to the committed authored path (docs/MODULES.md), Blender: `python3 tools/workflow.py module export-authored`.

Named meshes in a detail asset's ART_<asset> collection, authored in the anchor frame, are written as one self-contained glTF binary
(data/detail/<pack>/<id>.glb: +Y-up conversion, transforms and modifiers applied, materials as glTF PBR; no animation, camera, light or
custom property). The editable sources then move to SRC_<asset>, a collection outside the asset's root collection: they stay in the local
.blend for further editing, are never adopted, linked into the ship, exported or fingerprinted, and the next detail build imports the
committed file instead. Prints the file's sha256 and the manifest entry the pack session records (license, author and provenance filled in).

    blender -b --python src/wayfarer/build/authored_export.py -- --root . --assembly M7.RA1 --id SHELF_A --objects ShelfA [--out FILE]
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import bpy
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build')]
from spec import load
from common import save
import modules


def export(root, assembly, ident, names):
    s, _, spec_text, source_text = load(root)
    reg = modules.registry(root); t = modules.assemblies(s['detail_packs'])[assembly]
    if not ident or not all(c.isupper() or c.isdigit() or c == '_' for c in ident):
        raise SystemExit(f'WF_AUTHORED_EXPORT: id {ident!r} must be A-Z, 0-9 and _')
    name = modules.asset_name(assembly); path = root/'assets/wayfarer'/modules.ASSET_DIR/f'{name}.blend'
    if not path.is_file():
        raise SystemExit(f'WF_AUTHORED_EXPORT: {path.relative_to(root)} missing: module build {t["pack"]} first')
    bpy.ops.wm.open_mainfile(filepath=str(path))
    art = bpy.data.collections.get(f'ART_{name}')
    objs = [bpy.data.objects.get(n) for n in names]
    bad = [n for n, o in zip(names, objs) if o is None or o.type != 'MESH' or art is None or o.name not in art.all_objects]
    if bad:
        raise SystemExit(f'WF_AUTHORED_EXPORT: {bad} are not meshes in ART_{name}')
    rel = f'{modules.PACK_DIR}/{t["pack"]}/{ident.lower()}.glb'; out = root/rel; out.parent.mkdir(parents=True, exist_ok=True)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(filepath=str(out), export_format='GLB', use_selection=True, export_yup=True, export_apply=True,
                              export_animations=False, export_cameras=False, export_lights=False, export_extras=False,
                              export_materials='EXPORT', export_attributes=False, export_texcoords=True, export_normals=True,
                              export_tangents=False, export_draco_mesh_compression_enable=False, export_gpu_instances=False)
    sha = hashlib.sha256(out.read_bytes()).hexdigest(); size = out.stat().st_size
    src = bpy.data.collections.get(f'SRC_{name}') or bpy.data.collections.new(f'SRC_{name}')
    if src.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(src)          # outside the root collection: the host's instance never shows it
    for o in objs:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        src.objects.link(o)
        for k in [k for k in o.keys() if k.startswith('wf_') or k in ('kind', 'layer', 'detail_pack', 'detail_assembly', 'm7_assembly')]:
            del o[k]
        o['wf_authored_source'] = rel; o.hide_render = True
    save(path, bpy.data.collections[name], spec_text, source_text)
    against = modules.anchor_hash(reg, modules.anchors(s, reg)[t['anchor']])
    stanza = '\n'.join([f'[[assembly."{assembly}".authored]]', f'id = "{ident}"', f'file = "{Path(rel).name}"', f'sha256 = "{sha}"',
                        f'authored_against = "{against}"', 'license = "<fill in: e.g. CC0-1.0, or the owner\'s licence>"',
                        'author = "<fill in>"', 'provenance = "<fill in: how and from what it was made>"'])
    return dict(result='PASS', file=rel, bytes=size, sha256=sha, authored_against=against, sources=f'SRC_{name}', objects=names,
                over_cap=size > modules.AUTHORED_MAX_BYTES, manifest_entry=stanza)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--root', type=Path, default=ROOT); p.add_argument('--assembly', required=True)
    p.add_argument('--id', required=True); p.add_argument('--objects', nargs='+', required=True)
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    print('WF_AUTHORED_EXPORT', json.dumps(export(a.root.resolve(), a.assembly, a.id, a.objects)), flush=True)
