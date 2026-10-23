"""Detail assets (docs/MODULES.md): one pack assembly per file, linked into its host at its anchor.

`build()` fills a detail asset (assets/wayfarer/detail/WF_DETAIL_<assembly>.blend) with the assembly's production families, in its anchor's
frame; a disabled pack leaves the file empty, so switching a pack never rewrites its host. `attach()` links every pack assembly anchored on a
host into that host's GEN collection as a collection instance (kind detail_instance) parented to the anchor object with an identity local
transform (plain parent, identity parent inverse), or at the collection origin. The host never builds the detail itself, so a detail-only
change rewrites only its own file and the vehicle sees it through the nested link.
"""
import bpy
from common import link_instance
import modules
import production


def build(c, s, assembly):
    """The assembly's production objects in collection c (empty when the pack or its scope is switched off)."""
    return production.build(c, s, assembly)


def stamp(coll, s, root, assembly):
    """Contract stamps on the detail asset's root collection: what it was built against (inspect and module validate compare them)."""
    reg = modules.registry(root); t = modules.assemblies(s['detail_packs'])[assembly]; anchor = modules.anchors(s, reg)[t['anchor']]
    coll['detail_assembly'] = assembly; coll['detail_pack'] = t['pack']; coll['module'] = t['module']; coll['anchor'] = t['anchor']
    coll['anchor_hash'] = modules.anchor_hash(reg, anchor); coll['inputs_hash'] = modules.inputs_hash(root, t['pack'])
    coll['contract_hash'] = modules.contracts(s, root, reg, s['detail_packs'])['modules'][t['module']]['hash']


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
