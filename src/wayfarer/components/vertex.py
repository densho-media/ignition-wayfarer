"""Vertex propulsion generators (owner brief 2026-11-14): WF_VERTEX_ENGINE (Asset B), WF_VERTEX_RESEARCH (Asset A) and the
WF_PROPULSION_CLUSTER subsystem (Asset C).

Every vertex and face comes from the pure modules (vertex_engine.parts/research_parts/effects/mesh_of, vertex_cluster.frame/distribution/
placements/drivers); this file only turns them into Blender objects, functional sub-collections, physical materials, metadata and cameras.
The cluster links WF_VERTEX_ENGINE four times (one collection instance per engine, ENGINE_N1..N4), so an engine change propagates
through the library link and no engine mesh is ever copied.
"""
import math
from pathlib import Path
import bpy
from mathutils import Matrix, Vector
from common import empty, material, driven_material, link_instance, tag, group, OWNER
import drive_manifold as dm
import vertex_engine as ve
import vertex_cluster as vc
from drive import add_driver, build_actions

SMOOTH = {'torus', 'tube', 'sphere', 'revolve', 'torus_section', 'plume'}


def physical(key):
    """Physical appearance material (vertex_engine.MATERIALS): separate from the functional review colours (obj.color)."""
    if key == 'field':
        return material('VTX_FIELD', (0.25, 0.55, 0.95), 0.6, 0.12)
    rgb, rough, metal, emit = ve.MATERIALS[key]
    m = material(f'VTX_{key.upper()}', rgb, emit)
    node = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    node.inputs['Roughness'].default_value = rough; node.inputs['Metallic'].default_value = metal
    m['vtx_material'] = key
    return m


def category_groups(gen, prefix='VTX'):
    """The functional sub-collections (owner brief 9), coloured with the existing functional palette tags. Each asset uses its own prefix
    (VTX engine, VRD research, CL cluster) so a file that links the engine never meets a linked collection of the same name."""
    import functional_colors as fc
    return {cat: group(gen, prefix+coll[3:], fc.PALETTE[fkey][2]) for cat, (coll, fkey) in ve.CATEGORIES.items()}


def make(c, p, prefix, owner_id, version, transform=None, mat=None, data=None):
    """One object from a part record. `transform` maps part-frame points to the object's parent frame."""
    if data is None:
        vs, fs = ve.mesh_of(p)
        if transform:
            vs = [transform(v) for v in vs]
        data = bpy.data.meshes.new(f'{p["name"]}_Mesh'); data.from_pydata(vs, [], fs); data.update()
        if p['shape'] in SMOOTH:
            data.polygons.foreach_set('use_smooth', [True]*len(data.polygons))
        data.materials.append(mat or physical(p['material']))
    obj = bpy.data.objects.new(p['name'], data); c.objects.link(obj)
    tag(obj, f'{prefix}.{p["name"]}', f'vtx_{p["category"].lower()}', status=p['evidence'] if p['evidence'] != 'RESEARCH' else 'RESEARCH', source='vertex')
    obj['wf_category'] = p['category']; obj['wf_material'] = p['material']; obj['wf_evidence'] = p['evidence']; obj['wf_note'] = p['note']
    obj['wf_asset_id'] = owner_id; obj['wf_asset_version'] = version
    return obj


def family(groups, name, ps, prefix, owner_id, version, transform_of=lambda p: None):
    """One object for a family of parts (vertex_engine.families): one part keeps its own record; several share one mesh and list their
    names in wf_parts. `transform_of(part)` gives the part-frame to parent-frame map, or None."""
    if len(ps) == 1 and ps[0]['name'] == name:
        return make(groups[ps[0]['category']], ps[0], prefix, owner_id, version, transform=transform_of(ps[0]))
    vs, fs, smooth = [], [], []
    for p in ps:
        v, f = ve.mesh_of(p)[:2]; tf = transform_of(p)
        fs += [tuple(i+len(vs) for i in face) for face in f]; vs += [tf(x) for x in v] if tf else list(v); smooth += [p['shape'] in SMOOTH]*len(f)
    data = bpy.data.meshes.new(f'{name}_Mesh'); data.from_pydata(vs, [], fs); data.update()
    data.polygons.foreach_set('use_smooth', smooth)
    data.materials.append(physical(ps[0]['material']))
    stems = sorted({x['name'].rpartition('_')[0] if x['name'].rpartition('_')[2].isdigit() else x['name'] for x in ps})
    rec = dict(ps[0], name=name, note=f'{len(ps)} parts: ' + ', '.join(stems))
    obj = make(groups[ps[0]['category']], rec, prefix, owner_id, version, data=data)
    obj['wf_units'] = len(ps); obj['wf_parts'] = ', '.join(x['name'] for x in ps)
    return obj


def review_collection(name):
    """Review cameras live beside the asset collection (never inside it), so a linked instance never carries them."""
    scene = bpy.context.scene
    coll = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if coll.name not in scene.collection.children:
        scene.collection.children.link(coll)
    for obj in list(coll.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    coll['wf_owner'] = OWNER; coll.color_tag = 'NONE'
    return coll


def camera(coll, name, location, target, lens=35.0, clip=(0.5, 3000.0), purpose=''):
    data = bpy.data.cameras.new(name); data.lens = lens; data.clip_start, data.clip_end = clip
    obj = bpy.data.objects.new(name, data); coll.objects.link(obj)
    back = (Vector(location)-Vector(target)).normalized(); up0 = Vector((0, 0, 1)) if abs(back.z) < 0.95 else Vector((0, 1, 0))
    right = up0.cross(back).normalized(); up = back.cross(right)
    obj.matrix_world = Matrix([(right[i], up[i], back[i], location[i]) for i in range(3)]+[(0, 0, 0, 1)])
    tag(obj, name, 'review_camera'); obj['purpose'] = purpose
    return obj


def stamp(root, record, status):
    for k, v in record.items():
        root[k] = v
    root['wf_status'] = status


def engine(c, s):
    """Asset B: the Compact Vertex Engine in its own frame (origin at the forward face, +X forward)."""
    e = ve.config(s); groups = category_groups(c)
    for name, ps in ve.families(ve.parts(s)):
        family(groups, name, ps, 'WF.VTX.CE', e['id'], e['version'])
    for i in ve.interfaces(s):
        obj = empty(groups['SERVICE'] if i['kind'] == 'service' else groups['STRUCTURE'], i['name'], i['at'], ident=f'WF.VTX.CE.{i["name"]}', kind='interface')
        obj['note'] = i['note']; obj['interface_kind'] = i['kind']; obj.empty_display_size = 0.5
    root = bpy.data.collections['WF_VERTEX_ENGINE']
    env = ve.envelope(s); mass = ve.mass_estimate(s)
    stamp(root, dict(wf_asset_id=e['id'], wf_asset_version=e['version'], wf_derived_from=e['derived_from'], wf_evidence='ENGINEERING_PROTOTYPE',
                     envelope_length_m=env['length'], envelope_radius_m=env['max_radius'], mass_estimate_kg=mass['total_kg'],
                     speculative_items=', '.join(f'{x["id"]}->{x["extends"]}' for x in e['speculative']['items'])), 'SPECULATIVE_WORKING_REPRESENTATION')
    cams = review_collection('REVIEW_VERTEX_ENGINE'); mid = env['x0']/2
    camera(cams, 'CAM_VTX_MODULE_PERSPECTIVE', (mid+30, -34, 18), (mid, 0, 0), 35, purpose='module perspective')
    camera(cams, 'CAM_VTX_MODULE_CUTAWAY', (mid, -40, 0), (mid, 0, 0), 30, clip=(40.0, 400.0), purpose='cutaway: the near half is clipped at the axis plane')
    camera(cams, 'CAM_VTX_ENGINE_REAR', (env['x0']-38, -12, 10), (mid, 0, 0), 35, purpose='engine rear: burn face, loops and armour')


def research(c, s):
    """Asset A: the Vertex Research Demonstrator V4 (reference only; Gate 2 BLOCKED)."""
    r = s['vertex_research']; groups = category_groups(c, 'VRD')
    for p in ve.research_parts(s):
        mat = physical('field') if p.get('ghost') else None
        obj = make(groups[p['category']], p, 'WF.VTX.RD', r['id'], r['version'], mat=mat)
        if p.get('ghost'):
            obj.display_type = 'WIRE'
    root = bpy.data.collections['WF_VERTEX_RESEARCH']
    stamp(root, dict(wf_asset_id=r['id'], wf_asset_version=r['version'], gate2_verdict=r['gate2_verdict'], gate2_reason=r['gate2_reason'],
                     wf_evidence='RESEARCH (pinned imports)'), 'RESEARCH_REFERENCE_BLOCKED')
    cams = review_collection('REVIEW_VERTEX_RESEARCH')
    camera(cams, 'CAM_VRD_SIDE', (-110, -420, 60), (-110, 0, 0), 35, clip=(1, 5000), purpose='research demonstrator side')


def cluster(c, s, asset_dir):
    """Asset C: four linked engines, frame, distribution, cross-fire baffle, interfaces, per-engine effects and the drive control."""
    k = vc.config(s); groups = category_groups(c, 'CL'); e = ve.config(s)
    engines_g = group(c, 'CL_ENGINES', 'COLOR_07')
    root = bpy.data.collections['WF_PROPULSION_CLUSTER']
    pls = vc.placements(s)
    for pl in pls:
        obj = link_instance(engines_g, asset_dir/'components/WF_VERTEX_ENGINE.blend', 'WF_VERTEX_ENGINE', pl['name'], ident=pl['ident'])
        obj.matrix_world = Matrix(vc.matrix(pl))
        obj['engine'] = pl['label']; obj['azimuth_deg'] = pl['azimuth_deg']; obj['polarity'] = pl['polarity']
        obj['engine_asset'] = e['id']; obj['engine_version'] = e['version']; obj['owner_label'] = pl['label']
        obj['wf_evidence'] = 'SPECULATIVE'; obj['wf_status'] = 'SPECULATIVE_WORKING_REPRESENTATION'
    def ship_frame(p):
        j = p.get('placement')
        return (lambda v, pl=pls[j-1]: vc.to_ship(pl, v)) if j else None
    for name, ps in ve.families(vc.frame(s)+vc.distribution(s), prefix='CL'):
        family(groups, name, ps, 'WF.VTX.CL4', k['id'], k['version'], transform_of=ship_frame)
    for i in vc.interfaces(s):
        obj = empty(groups['STRUCTURE'], i['name'], i['at'], ident=f'WF.VTX.CL4.{i["name"]}', kind='interface')
        obj['note'] = i['note']; obj['axis'] = list(i['axis']); obj.empty_display_size = 0.8
    # --- shared effect definition: one mesh per effect, one object per engine (per-instance state through drivers) ---
    fx = groups['VISUAL_EFFECTS']; meshes = {}
    for o in vc.effect_objects(s):
        key = o['name']; origin = o.get('origin') or (0.0, 0.0, 0.0)
        if key not in meshes:
            vs, fs = ve.mesh_of(o)
            data = bpy.data.meshes.new(f'VTX_{key}_Mesh'); data.from_pydata([tuple(v[i]-origin[i] for i in range(3)) for v in vs], [], fs); data.update()
            data.polygons.foreach_set('use_smooth', [True]*len(data.polygons))
            data.materials.append(driven_material(f'VTX_{key}', o['color'], o['strength'], o.get('alpha', 1.0)))
            meshes[key] = data
        obj = bpy.data.objects.new(o['object'], meshes[key]); fx.objects.link(obj)
        tag(obj, f'WF.VTX.CL4.N{o["engine"]}.{key}', 'vtx_visual_effects', status='SPECULATIVE', source='vertex')
        obj.matrix_world = Matrix(vc.matrix(o['placement']))@Matrix.Translation(origin)
        obj['effect_layer'] = o['layer']; obj['effect_channel'] = o['channel']; obj['engine'] = f'N{o["engine"]}'; obj['wf_note'] = o['note']
        obj['wf_category'] = 'VISUAL_EFFECTS'; obj['wf_evidence'] = 'SPECULATIVE'; obj['display_emitter'] = True
        obj.color = (*o['color'], 0.0)
    fe = vc.field_envelope(s); vs, fs = ve.mesh_of(fe)
    fdata = bpy.data.meshes.new('VTX_FX_FIELD_ENVELOPE_Mesh'); fdata.from_pydata(vs, [], fs); fdata.update(); fdata.materials.append(physical('field'))
    for pl in pls:
        obj = bpy.data.objects.new(f'N{pl["n"]}_FX_FIELD_ENVELOPE', fdata); fx.objects.link(obj)
        tag(obj, f'WF.VTX.CL4.N{pl["n"]}.FX_FIELD_ENVELOPE', 'vtx_visual_effects', status='SPECULATIVE', source='vertex')
        obj.matrix_world = Matrix(vc.matrix(pl)); obj['effect_layer'] = 'field'; obj['wf_note'] = fe['note']
        obj.hide_viewport = obj.hide_render = True
    # --- control: the drive_manifold properties and actions on the cluster's own DRIVE_MANIFOLD_CTRL ---
    ctrl = empty(c, dm.CONTROL, (vc.stations(s)['engine_aft']-4, 0, -8), ident='WF.DRIVE.STATE_CONTROL', kind='state_control')
    ctrl.empty_display_type = 'CUBE'; ctrl.empty_display_size = .6
    for key, value in {**dm.neutral(s), **dm.SAVED_SETTINGS}.items():
        ctrl[key] = float(value)
        ctrl.id_properties_ui(key).update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, description={**dm.PROPS, **dm.DEBUG_TOGGLES, **dm.CONFIGURATION_SETTINGS}[key])
        ctrl.property_overridable_library_set(f'["{key}"]', True)
    ctrl['units'] = 'normalized 0-1; no physical rating'
    ctrl['nozzle_order'] = 'N1..N4 = ENGINE_N1..N4: +Y+Z, -Y+Z, +Y-Z, -Y-Z (owner nozzle map; flux_share_n is engine Nn level)'
    ctrl['causal_chain'] = 'flux_share_n -> engine Nn level; drive_active, plasma_visibility, nozzle_field_strength, lasers and lattice_activation set the shared effect channels'
    ctrl['engineering_status'] = 'SPECULATIVE display rig: no physical rating'
    objects = {o.name: o for o in c.all_objects}
    for name, path, index, expression in vc.drivers(s):
        add_driver(objects[name], path, index, expression, ctrl)
    build_actions(s, ctrl)
    bpy.context.scene.render.fps = s['drive_manifold']['fps']
    gp = vc.gaps(s)
    stamp(root, dict(wf_asset_id=k['id'], wf_asset_version=k['version'], engine_asset=e['id'], engine_version=e['version'], engine_count=k['engine_count'],
                     pitch_radius_m=k['pitch_radius_m'], cant_deg=k['cant_deg'], adjacent_gap_m=gp['adjacent_gap_m'], central_opening_m=gp['central_opening_m'],
                     outer_radius_m=gp['outer_radius_m'], wf_evidence='ENGINEERING_PROTOTYPE (layout); SPECULATIVE (performance)'), k['status'])
    cams = review_collection('REVIEW_PROPULSION_CLUSTER'); st = vc.stations(s)
    camera(cams, 'CAM_CLUSTER_FRONT', (-60, -70, 55), (-150, 0, 0), 30, purpose='cluster front three-quarter (engine fronts, hub, thrust struts)')
    camera(cams, 'CAM_CLUSTER_REAR', (-260, -55, 40), (-150, 0, 0), 30, purpose='cluster rear (four burn faces, baffle, loops)')
