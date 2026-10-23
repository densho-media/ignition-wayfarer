"""Detail assets (docs/MODULES.md): one pack assembly per file, linked into its host at its anchor.

`build()` fills a detail asset (assets/wayfarer/detail/WF_DETAIL_<assembly>.blend) with the assembly's production families, in its anchor's
frame; a disabled pack leaves the file empty, so switching a pack never rewrites its host. `attach()` links every pack assembly anchored on a
host into that host's GEN collection as a collection instance (kind detail_instance) parented to the anchor object with an identity local
transform (plain parent, identity parent inverse), or at the collection origin. The host never builds the detail itself, so a detail-only
change rewrites only its own file and the vehicle sees it through the nested link.
"""
import bpy
from common import link_instance, tag, OWNER
import modules
import production


def build(c, s, assembly):
    """The assembly's production objects in collection c (empty when the pack or its scope is switched off)."""
    return production.build(c, s, assembly)


AUTHORED_BASIS = ('PROTOTYPE authored mesh (committed glTF binary, docs/MODULES.md): depiction only; no load, pressure, interface, volume, '
                  'clearance or mass')


def import_authored(c, s, root, assembly):
    """Committed authored meshes ([[assembly.<A>.authored]], data/detail/<pack>/<file>.glb): each checked (present, its sha256, authored
    against the current anchor frame) and imported with fixed glTF options into collection c as one generated object Auth_<assembly>_<id>
    in the anchor frame (the importer's +Y-up conversion and node transforms baked into the mesh), tagged like generated detail, so the
    export, the fingerprint and inspect carry it with no special case and a fresh checkout rebuilds it exactly. Returns the objects."""
    import production_detail as pd
    from mathutils import Matrix
    reg = modules.registry(root); t = modules.assemblies(s['detail_packs'])[assembly]; pack = s['detail_packs'][t['pack']]
    current = modules.anchor_hash(reg, modules.anchors(s, reg)[t['anchor']]); sc = pd.scope(s, assembly); made = []
    for e in t.get('authored', []):
        path = modules.authored_path(root, t['pack'], e); rel = f"{modules.PACK_DIR}/{t['pack']}/{e['file']}"
        if not path.is_file():
            raise SystemExit(f"WF_DETAIL_MISSING {assembly} {e['id']}: {rel} is not in the checkout (commit it, or remove the manifest entry)")
        if modules.sha256_file(path) != e['sha256']:
            raise SystemExit(f"WF_DETAIL_STALE {assembly} {e['id']}: {rel} differs from its manifest sha256; review the mesh, then record "
                             f"sha256 = \"{modules.sha256_file(path)}\" in {t['pack']}.toml")
        if e['authored_against'] != current:
            raise SystemExit(f"WF_DETAIL_REVIEW {assembly} {e['id']}: authored against another frame of {t['anchor']} (now {current}); review "
                             f"it against the current anchor, then record authored_against = \"{current}\" in {t['pack']}.toml")
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(path), merge_vertices=False, import_shading='NORMALS', guess_original_bind_pose=False,
                                  import_pack_images=True, import_scene_extras=False, import_select_created_objects=False,
                                  import_scene_as_collection=False)
        new = [o for o in bpy.data.objects if o not in before]
        meshes = sorted((o for o in new if o.type == 'MESH'), key=lambda o: o.name)
        if not meshes:
            raise SystemExit(f"WF_DETAIL_EMPTY {assembly} {e['id']}: {rel} holds no mesh")
        name = f"Auth_{modules.safe(assembly)}_{e['id']}"
        if len(meshes) == 1:                # the usual case: the mesh itself, world transform applied (custom normals kept)
            data = meshes[0].data.copy(); data.transform(meshes[0].matrix_world); data.name = name+'_Mesh'
            mats = list(data.materials)
        else:                               # several meshes: joined in name order onto one material list (face smooth flags kept)
            import bmesh
            data = bpy.data.meshes.new(name+'_Mesh'); mats = []; bm = bmesh.new()
            for o in meshes:
                me = o.data.copy(); me.transform(o.matrix_world); slot = []
                for m in me.materials:
                    if m not in mats:
                        mats.append(m)
                    slot.append(mats.index(m))
                n0 = len(bm.faces); bm.from_mesh(me); bm.faces.ensure_lookup_table()
                for f in list(bm.faces)[n0:]:
                    f.material_index = slot[f.material_index] if f.material_index < len(slot) else 0
                bpy.data.meshes.remove(me)
            bm.to_mesh(data); bm.free()
            data.materials.clear()
            for m in mats:
                data.materials.append(m)
        for i, m in enumerate(mats):
            if m is not None:               # generator-owned, so begin() drops it unused on the next build and the name stays stable
                m.name = f"WF_MAT_Auth_{e['id']}_{i}"; m['wf_owner'] = OWNER
        for o in new:
            old = o.data if o.type == 'MESH' else None
            bpy.data.objects.remove(o, do_unlink=True)
            if old is not None and old.users == 0:
                bpy.data.meshes.remove(old)
        obj = bpy.data.objects.new(name, data); c.objects.link(obj); obj.matrix_world = Matrix.Identity(4)
        tag(obj, f"{assembly}.AUTHORED.{e['id']}", 'production_detail', source=sc['evidence_ref'])
        obj['layer'] = 'PRODUCTION'; obj['representation'] = s['production']['representation']; obj['m7_assembly'] = assembly
        obj['maturity'] = sc['maturity']; obj['family'] = 'authored'; obj['detail_pack'] = t['pack']; obj['module'] = t['module']
        obj['detail_class'] = e.get('detail_class', pack['pack']['detail_class']); obj['surface_class'] = e.get('surface_class', 'ARTISTIC')
        obj['function'] = e.get('function', 'authored production detail'); obj['elements'] = 1; obj['geometry_basis'] = AUTHORED_BASIS
        obj['evidence_ref'] = sc['evidence_ref']; obj['wf_authored_against'] = e['authored_against']
        obj['authored_file'] = rel; obj['authored_sha256'] = e['sha256']
        obj['license'] = e['license']; obj['author'] = e['author']; obj['provenance'] = e['provenance']
        if 'detail_range_m' in pack['pack']:
            obj['detail_range_m'] = float(pack['pack']['detail_range_m'])
        made.append(obj)
    return made


def stamp(coll, s, root, assembly):
    """Contract stamps on the detail asset's root collection: what it was built against (inspect and module validate compare them)."""
    reg = modules.registry(root); t = modules.assemblies(s['detail_packs'])[assembly]; anchor = modules.anchors(s, reg)[t['anchor']]
    coll['detail_assembly'] = assembly; coll['detail_pack'] = t['pack']; coll['module'] = t['module']; coll['anchor'] = t['anchor']
    coll['anchor_hash'] = modules.anchor_hash(reg, anchor); coll['inputs_hash'] = modules.inputs_hash(root, t['pack'])
    coll['contract_hash'] = modules.pack_contract(s, reg, s['detail_packs'], t['pack'])


def adopt(name, s, root, assembly, rebind=False):
    """Hand-authored detail (docs/MODULES.md): every mesh in ART_<asset> is adopted on its first build (wf_adopted, the pack's labels and
    wf_authored_against = the anchor hash) and checked on every later one. Detail authored against another anchor frame stops the build
    (WF_DETAIL_REVIEW) until someone reviews it and rebuilds with --rebind. Adopted objects keep no wf_owner, so begin() never deletes them.
    Returns the adopted object names."""
    import production_detail as pd
    reg = modules.registry(root); t = modules.assemblies(s['detail_packs'])[assembly]
    current = modules.anchor_hash(reg, modules.anchors(s, reg)[t['anchor']]); pack = s['detail_packs'][t['pack']]
    art = bpy.data.collections.get(f'ART_{name}'); out, stale = [], []
    for obj in (art.all_objects if art else []):
        if obj.library is not None or obj.type != 'MESH':
            continue
        if obj.get('wf_adopted') and obj.get('wf_authored_against') != current and not rebind:
            stale.append(obj.name); continue
        if not obj.get('wf_adopted') or rebind:
            obj['wf_authored_against'] = current
        obj['wf_adopted'] = True; obj['kind'] = 'production_detail'; obj['layer'] = 'PRODUCTION'
        obj['detail_pack'] = t['pack']; obj['detail_assembly'] = assembly; obj['m7_assembly'] = assembly
        obj['detail_class'] = obj.get('detail_class') if obj.get('detail_class') in modules.DETAIL_CLASSES else pack['pack']['detail_class']
        obj['maturity'] = pd.scope(s, assembly)['maturity']; obj['representation'] = 'REP_HERO'
        for key, value in (('component_id', f'{assembly}.AUTHORED.{obj.name}'), ('canon_status', 'PROTOTYPE'),
                           ('geometry_status', 'PROTOTYPE'), ('source_ref', 'prototype')):
            if key not in obj:
                obj[key] = value
        out.append(obj.name)
    if stale:
        raise SystemExit(f'WF_DETAIL_REVIEW {name}: {stale} were authored against another frame of {t["anchor"]} (now {current}). '
                         f'Review them against the new anchor, then rebuild with --rebind (python3 tools/workflow.py module rebind {t["pack"]}).')
    return out


def attach(c, s, assets, host, root):
    """Link every pack assembly anchored on `host` (a build target) into collection c; returns the instance empties."""
    reg = modules.registry(root); anchors = modules.anchors(s, reg); made = []
    for a, t in sorted(modules.assemblies(s['detail_packs']).items()):
        q = anchors[t['anchor']]
        if q['host'] != host:
            continue
        name = modules.asset_name(a)
        obj = link_instance(c, assets/modules.ASSET_DIR/f'{name}.blend', name, modules.instance_name(a), ident=f'WF.DETAIL.{a}')
        obj['kind'] = 'detail_instance'; obj['detail_assembly'] = a; obj['detail_pack'] = t['pack']; obj['module'] = t['module']
        obj['anchor'] = t['anchor']; obj['anchor_hash'] = modules.anchor_hash(reg, q)
        if q['object']:
            parent = next((o for o in bpy.data.objects if o.library is None and o.name == q['object']), None)
            if parent is None:
                raise ValueError(f'{a}: anchor {t["anchor"]} needs object {q["object"]} in {host}, which has none')
            obj.parent = parent
        made.append(obj)
    return made
