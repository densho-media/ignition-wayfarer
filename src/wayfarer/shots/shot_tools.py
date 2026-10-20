"""FUT-002 shot tools (Blender): representations of linked source assets and their shot operations.

A shot references Wayfarer and never becomes Wayfarer:
- sources are linked with relative paths, never appended or made local;
- each representation object is a shot-local object whose geometry data is the linked source data, so a rebuilt asset
  shows up in the shot on reopen;
- materials, section planes, explode groups, keys, labels, cameras and lights are shot-local presentation data.
Identity, selectors, explode offsets and key tables come from representation.py, which the tests share.
"""
import math
import sys
from pathlib import Path
import bpy
from mathutils import Matrix, Vector
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer')]
import representation as rp
import spec
import rotor_interface

OWNER = 'wayfarer.shot'
PREFIX = {'REP_STANDARD': 'STD', 'REP_HOLOGRAM': 'HOLO', 'REP_CUTAWAY': 'CUT'}
CONTROL = 'SHOT_CTRL'
SECTION = 'SHOT_SECTION'
CAP_COLOR = (0.92, 0.32, 0.22)


# ---------- sources ------------------------------------------------------------------------------------------------

def link_source(root, src):
    """Link (never append) one source collection with a relative path, from assets/<library> (default wayfarer)."""
    path = Path(root)/'assets'/src.get('library', 'wayfarer')/src['asset']
    if not path.is_file():
        raise FileNotFoundError(path)
    with bpy.data.libraries.load(str(path), link=True, relative=True) as (_, dst):
        dst.collections = [src['collection']]
    if dst.collections[0] is None:
        raise ValueError(f'{path.name} has no collection {src["collection"]}')
    return dst.collections[0]


def pose_preset(root, preset):
    """Shot-local preset: pose the linked ROTOR_n_MECH_CTRL values of a buildable configuration in memory, before the sources are gathered.
    The gathered matrices are the saved frame-1 ones, where every ring sits at its index angle (phase); a stopped ring never leaves it,
    so each linked Rotor_n basis angle must equal its phase. Drive plasma is not posed in shots (a static representation of the saved
    data); only the ring state follows the preset."""
    s, *_ = spec.load(root)
    if preset not in spec.buildable_configurations(s):
        raise ValueError(f'Shot preset {preset!r} is not a buildable configuration')
    state = rotor_interface.configuration_state(s, preset)
    for rot in rotor_interface.rotors(s):
        control = bpy.data.objects[rotor_interface.control(rot['index'])]
        for key, value in state.items():
            control[key] = float(value)
        angle = bpy.data.objects[f"Rotor_{rot['index']}"].rotation_euler.x
        if abs(angle-rot['phase']) > 1e-6:
            raise ValueError(f"Rotor_{rot['index']} is saved at {angle}, not at its index angle {rot['phase']}")
    return state


POSED = {}  # object name -> {(data_path, index): value} from pose_controls()


def pose_controls(controls):
    """Shot-local display controls (e.g. the entry hatches open): set the linked control objects' properties in memory and evaluate the
    drivers that read only them, so gather() sees the driven pose. Linked objects are never evaluated by Blender here (see world())."""
    POSED.clear()
    for name, values in controls.items():
        for key, value in values.items():
            bpy.data.objects[name][key] = float(value)
    for obj in bpy.data.objects:
        for d in (obj.animation_data.drivers if obj.animation_data else []):
            vs = d.driver.variables
            if vs and all(v.type == 'SINGLE_PROP' and v.targets[0].id is not None and v.targets[0].id.name in controls for v in vs):
                env = {v.name: v.targets[0].id.path_resolve(v.targets[0].data_path) for v in vs}
                POSED.setdefault(obj.name, {})[(d.data_path, d.array_index)] = eval(d.driver.expression, {'__builtins__': {}}, env)


def basis(obj):
    """The saved basis, with the channels pose_controls() drove."""
    if obj.name not in POSED:
        return obj.matrix_basis.copy()
    if obj.rotation_mode != 'XYZ':
        raise ValueError(f'{obj.name}: driven rotation mode {obj.rotation_mode} is not supported')
    ch = {'location': obj.location.copy(), 'rotation_euler': obj.rotation_euler.copy(), 'scale': obj.scale.copy()}
    for (path, i), value in POSED[obj.name].items():
        ch[path][i] = value
    return Matrix.LocRotScale(ch['location'], ch['rotation_euler'], ch['scale'])


def _drive_node(obj):
    p = obj.parent
    while p is not None and p.get('kind') != 'drive_node':
        p = p.parent
    return p.name if p is not None else None


def world(obj):
    """World matrix composed from the parent chain. Linked objects outside the scene are never evaluated, and a stored
    matrix_world can predate a re-parent (the P1F drive nodes), so it is not trusted."""
    b = basis(obj)
    if obj.parent is None:
        return b
    if obj.parent_type != 'OBJECT':
        raise ValueError(f'{obj.name}: parent type {obj.parent_type} is not supported')
    return world(obj.parent)@obj.matrix_parent_inverse@b


def local_points(obj):
    """Object-space extent points read from the source data. Linked objects outside the scene are never evaluated, so
    their bound_box can be stale; curves add their bevel radius. Empty when nothing renders at the saved state
    (collapsed plasma: zero bevel)."""
    data = obj.data
    if obj.type == 'MESH':
        return [v.co.copy() for v in data.vertices]
    pad = data.bevel_depth+data.extrude if data.bevel_mode == 'ROUND' or data.bevel_object is None else 0.0
    if pad <= 0 and data.bevel_object is None:
        return []
    pts = [Vector(p.co[:3]) for sp in data.splines for p in sp.points]+[bp.co.copy() for sp in data.splines for bp in sp.bezier_points]
    return [q+Vector(d) for q in pts for d in ((pad, 0, 0), (-pad, 0, 0), (0, pad, 0), (0, -pad, 0), (0, 0, pad), (0, 0, -pad))]


def gather(collection, src):
    """Every visible mesh/curve instance of a source, flattened through collection instances, with its identity key,
    world matrix at the saved frame and explode group. Saved-hidden objects and instances stay out (debug layers,
    simulation proxies), as in the renders of the saved assets."""
    items = []

    def walk(col, M, path, chain):
        for obj in col.all_objects:
            if obj.hide_render:
                continue
            if obj.instance_type == 'COLLECTION' and obj.instance_collection is not None:
                inner = obj.instance_collection
                walk(inner, M@world(obj)@Matrix.Translation(-inner.instance_offset), path+[obj.name], chain+[obj])
                continue
            if obj.type not in {'MESH', 'CURVE'} or obj.get('kind') in rp.SKIP_KINDS:
                continue
            if src['group'] == 'fixed':
                group = rp.FIXED
            elif src['group'] == 'assembly':
                group = path[0] if path else src['collection']
            elif src['group'] == 'subassembly':
                group = '/'.join(path[:2]) if path else src['collection']
            else:
                group = _drive_node(obj) or next((g for g in map(_drive_node, reversed(chain)) if g), None) or src['collection']
            if obj.constraints:
                raise ValueError(f'{obj.name}: constrained source objects are not supported')
            W = M@world(obj)
            pts = [W@q for q in local_points(obj)] if abs(W.to_3x3().determinant()) > 1e-12 else []
            if pts:
                low = Vector([min(q[k] for q in pts) for k in range(3)]); high = Vector([max(q[k] for q in pts) for k in range(3)])
                center = (low+high)/2; radius = (high-low).length/2
            else:
                center, radius = W.translation.copy(), 0.0
            cid = str(obj.get('component_id', obj.name))
            items.append(dict(key=rp.identity([src['collection'], *path], cid), component_id=cid, kind=str(obj.get('kind', '')),
                              group=group, source=src['collection'], name=obj.name, center=tuple(center), radius=radius,
                              solid=bool(pts), matrix=W.copy(), obj=obj))
    walk(collection, Matrix(), [], [])
    keys = [i['key'] for i in items]
    if len(keys) != len(set(keys)):
        raise ValueError(f'{src["collection"]}: identity keys are not unique')
    return items


# ---------- shot-local materials -------------------------------------------------------------------------------------

def _attr(nt, name, socket='Fac'):
    node = nt.nodes.new('ShaderNodeAttribute'); node.attribute_type = 'OBJECT'; node.attribute_name = name
    return node.outputs[socket]


def _math(nt, op, a, b=None, clamp=False):
    node = nt.nodes.new('ShaderNodeMath'); node.operation = op; node.use_clamp = clamp
    for socket, value in zip(node.inputs, (a, b)):
        if value is None:
            continue
        if isinstance(value, (int, float)):
            socket.default_value = value
        else:
            nt.links.new(value, socket)
    return node.outputs[0]


def _mix_color(nt, fac, a, b):
    node = nt.nodes.new('ShaderNodeMix'); node.data_type = 'RGBA'
    nt.links.new(fac, node.inputs['Factor'])
    sa = next(s for s in node.inputs if s.name == 'A' and s.type == 'RGBA'); sb = next(s for s in node.inputs if s.name == 'B' and s.type == 'RGBA')
    for socket, value in ((sa, a), (sb, b)):
        if isinstance(value, tuple):
            socket.default_value = (*value, 1)
        else:
            nt.links.new(value, socket)
    return next(s for s in node.outputs if s.type == 'RGBA')


def _new_material(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; m['wf_owner'] = OWNER
    m.surface_render_method = 'BLENDED'
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return m, nt, nt.nodes.new('ShaderNodeOutputMaterial')


def material(rep, highlight, section=None, cap_from_color=False):
    """One shot-local material per representation; per-object colour, alpha, highlight and cut come from the object's
    custom properties (wf_color, wf_alpha, wf_highlight, wf_cut), so a single material serves every object."""
    m, nt, out = _new_material(f'SHOT_{rep}')
    alpha, hl, color = _attr(nt, 'wf_alpha'), _attr(nt, 'wf_highlight'), _attr(nt, 'wf_color', 'Color')
    tint = _mix_color(nt, hl, color, tuple(highlight))
    transparent = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(transparent.outputs[0], mix.inputs[1]); nt.links.new(mix.outputs[0], out.inputs['Surface'])
    if rep == 'REP_HOLOGRAM':
        rim = nt.nodes.new('ShaderNodeLayerWeight'); rim.inputs['Blend'].default_value = .35
        wire = nt.nodes.new('ShaderNodeWireframe'); wire.use_pixel_size = True; wire.inputs['Size'].default_value = 1.0
        glow = _math(nt, 'ADD', _math(nt, 'MULTIPLY', rim.outputs['Facing'], .55), _math(nt, 'MULTIPLY', wire.outputs[0], .9))
        glow = _math(nt, 'ADD', glow, .12)
        emission = nt.nodes.new('ShaderNodeEmission')
        nt.links.new(tint, emission.inputs['Color'])
        nt.links.new(_math(nt, 'MULTIPLY', _math(nt, 'ADD', _math(nt, 'MULTIPLY', hl, 1.5), 1.0), 1.6), emission.inputs['Strength'])
        nt.links.new(_math(nt, 'MULTIPLY', alpha, glow, clamp=True), mix.inputs[0])
        nt.links.new(emission.outputs[0], mix.inputs[2])
        return m
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(tint, bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = .42
    bsdf.inputs['Metallic'].default_value = .3 if rep == 'REP_STANDARD' else .1
    bsdf.inputs['Emission Color'].default_value = (*highlight, 1)
    nt.links.new(_math(nt, 'MULTIPLY', hl, 1.2), bsdf.inputs['Emission Strength'])
    if rep == 'REP_STANDARD':
        nt.links.new(alpha, mix.inputs[0]); nt.links.new(bsdf.outputs[0], mix.inputs[2])
        return m
    # Cutaway: objects with wf_cut lose the half-space on the section's +Z side. Solid volumes (wf_cap) show their back
    # faces, seen through the cut, as flat caps; thin shells keep their shaded inner surface.
    coords = nt.nodes.new('ShaderNodeTexCoord'); coords.object = section
    xyz = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(coords.outputs['Object'], xyz.inputs[0])
    cut = _attr(nt, 'wf_cut')
    removed = _math(nt, 'MULTIPLY', cut, _math(nt, 'GREATER_THAN', xyz.outputs['Z'], 0.0))
    keep = _math(nt, 'MULTIPLY', alpha, _math(nt, 'SUBTRACT', 1.0, removed), clamp=True)
    geometry = nt.nodes.new('ShaderNodeNewGeometry')
    cap = nt.nodes.new('ShaderNodeEmission'); cap.inputs['Color'].default_value = (*CAP_COLOR, 1); cap.inputs['Strength'].default_value = .9
    if cap_from_color:  # M5 overlay: a cut face shows its subsystem colour, so species and functions stay readable in section
        nt.links.new(color, cap.inputs['Color']); cap.inputs['Strength'].default_value = .55
    capped = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(_math(nt, 'MULTIPLY', geometry.outputs['Backfacing'], _attr(nt, 'wf_cap')), capped.inputs[0])
    nt.links.new(bsdf.outputs[0], capped.inputs[1]); nt.links.new(cap.outputs[0], capped.inputs[2])
    nt.links.new(keep, mix.inputs[0]); nt.links.new(capped.outputs[0], mix.inputs[2])
    return m


def label_material():
    m, nt, out = _new_material('SHOT_LABEL')
    emission = nt.nodes.new('ShaderNodeEmission'); emission.inputs['Color'].default_value = (.85, .95, 1, 1); emission.inputs['Strength'].default_value = 2.5
    transparent = nt.nodes.new('ShaderNodeBsdfTransparent'); mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(_attr(nt, 'wf_alpha'), mix.inputs[0]); nt.links.new(transparent.outputs[0], mix.inputs[1])
    nt.links.new(emission.outputs[0], mix.inputs[2]); nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return m


def source_color(obj):
    mats = [m for m in getattr(obj.data, 'materials', []) if m is not None]
    return tuple(mats[0].diffuse_color[:3]) if mats else (.6, .6, .6)


# ---------- representation -------------------------------------------------------------------------------------------

def _owned(idblock):
    idblock['wf_owner'] = OWNER
    return idblock


def control(scene):
    ctrl = _owned(bpy.data.objects.new(CONTROL, None)); scene.collection.objects.link(ctrl)
    ctrl.empty_display_type = 'CUBE'; ctrl.empty_display_size = .5
    ctrl['explode'] = 0.0
    ctrl.id_properties_ui('explode').update(min=0.0, max=2.0, description='Explode factor: 0 = recombined (saved source pose), 1 = the shot explode offsets')
    return ctrl


def section_empty(scene, section):
    obj = _owned(bpy.data.objects.new(SECTION, None)); scene.collection.objects.link(obj)
    obj.empty_display_type = 'SINGLE_ARROW'; obj.empty_display_size = 3
    obj.location = section['point']
    obj.rotation_euler = Vector(section['normal']).to_track_quat('Z', 'Y').to_euler()
    obj['note'] = 'Cutaway section: objects with wf_cut lose the half-space on this empty\'s +Z side'
    return obj


def represent(scene, items, rep, shot, ctrl, colors, highlight, section=None):
    """Shot-local representation objects over the linked source data, parented to driven explode-group empties."""
    tag = PREFIX[rep]
    coll = _owned(bpy.data.collections.new(f'{tag}_{scene["wf_shot"]}')); scene.collection.children.link(coll)
    coll['representation'] = rep
    ex = shot.get('explode', {})
    vectors = rp.explode_vectors(items, axial=ex.get('axial', 1.0), radial=ex.get('radial', 1.0))
    groups = {}
    for g, v in vectors.items():
        e = _owned(bpy.data.objects.new(f'{tag}_GROUP_{g or "FIXED"}', None)); coll.objects.link(e)
        e.empty_display_size = .5; e['explode_group'] = g; e['explode_vector'] = list(v)
        for i in range(3):
            fc = e.driver_add('location', i); fc.driver.type = 'SCRIPTED'
            var = fc.driver.variables.new(); var.name = 'e'; var.targets[0].id = ctrl; var.targets[0].data_path = '["explode"]'
            fc.driver.expression = f'e*({v[i]!r})'
        groups[g] = e
    # materials = "source" keeps the saved look: the linked materials (lit fixtures stay emissive) and no bevel; alpha ops then only hide.
    saved = shot.get('materials') == 'source'
    mat = None if saved else material(rep, highlight, section, cap_from_color=bool(shot.get('_subsystems')))
    cut = rp.select(items, shot.get('cut', [])) if rep == 'REP_CUTAWAY' else set()
    cap = rp.select(items, shot.get('cap', [])) & cut
    objects = {}
    for n, item in enumerate(items):
        o = _owned(bpy.data.objects.new(f'{tag}_{n:04}_{item["name"]}'[:63], item['obj'].data)); coll.objects.link(o)
        o.parent = groups[item['group']]; o.matrix_parent_inverse = Matrix(); o.matrix_basis = item['matrix']
        for slot in ([] if saved else o.material_slots):
            slot.link = 'OBJECT'; slot.material = mat
        o['wf_key'] = item['key']; o['component_id'] = item['component_id']; o['representation'] = rep
        o['source_object'] = item['name']; o['source_library'] = item['obj'].library.filepath if item['obj'].library else ''
        o['kind'] = item['kind']; o['group'] = item['group']
        subs = shot.get('_subsystems')
        if subs:  # M5 functional overlay: explanatory subsystem colours in any representation (never a ship material)
            o['subsystem'] = item['subsystem']
        o['wf_color'] = list(rp.subsystem_color(item, subs) if subs else rp.color_for(item, colors) if rep == 'REP_HOLOGRAM'
                             else source_color(item['obj']))
        o['wf_alpha'] = 1.0; o['wf_highlight'] = 0.0; o['wf_cut'] = float(item['key'] in cut); o['wf_cap'] = float(item['key'] in cap)
        if rep == 'REP_STANDARD' and o.type == 'MESH' and not saved:
            bevel = o.modifiers.new('STD_Bevel', 'BEVEL'); bevel.width = .03; bevel.segments = 2; bevel.limit_method = 'ANGLE'
            bevel.angle_limit = math.radians(30); bevel.harden_normals = True
        objects[item['key']] = o
    return coll, objects, groups, vectors


def _keys(owner, prop, keys, interpolation):
    """Insert the keys, then set their interpolation on the F-curve itself (the new-key preference is not reliable)."""
    path = prop if prop in {'hide_render', 'hide_viewport'} else f'["{prop}"]'
    for frame, value in keys:
        if prop in {'hide_render', 'hide_viewport'}:
            setattr(owner, prop, bool(value))
        else:
            owner[prop] = float(value)
        owner.keyframe_insert(path, frame=frame)
    action = owner.animation_data.action
    curves = [fc for layer in action.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves
              if fc.data_path == path and bag.slot == owner.animation_data.action_slot]
    for kp in curves[0].keyframe_points:
        kp.interpolation = interpolation


def apply_schedule(objects, ctrl, tables):
    """Key the operation tables: alpha and highlight linear, hide flags constant, explode on the shot control."""
    for key, o in objects.items():
        for channel, prop in (('alpha', 'wf_alpha'), ('highlight', 'wf_highlight')):
            keys = tables[channel][key]
            if len(keys) > 1:
                _keys(o, prop, keys, 'LINEAR')
            else:
                o[prop] = float(keys[0][1])
        hidden = tables['hidden'][key]
        if len(hidden) > 1:
            for prop in ('hide_render', 'hide_viewport'):
                _keys(o, prop, hidden, 'CONSTANT')
        else:
            o.hide_render = o.hide_viewport = bool(hidden[0][1])
    if len(tables['explode']) > 1:
        _keys(ctrl, 'explode', tables['explode'], 'LINEAR')


def labels(scene, shot, items, groups, camera):
    made = []
    mat = label_material()
    for n, lab in enumerate(shot.get('labels', [])):
        chosen = rp.select(items, lab['select'])
        pts = [Vector(i['center']) for i in items if i['key'] in chosen]
        group = next(i['group'] for i in items if i['key'] in chosen)
        data = _owned(bpy.data.curves.new(f'SHOT_LABEL_{n}', 'FONT')); data.body = lab['text']; data.size = lab.get('size', 1.2)
        data.align_x = 'CENTER'; data.materials.append(mat)
        o = _owned(bpy.data.objects.new(data.name, data)); scene.collection.objects.link(o)
        o.parent = groups[group]; o.matrix_parent_inverse = Matrix()
        o.location = sum(pts, Vector())/len(pts)+Vector(lab.get('offset', (0, 0, 0)))
        track = o.constraints.new('TRACK_TO'); track.target = camera; track.track_axis = 'TRACK_Z'; track.up_axis = 'UP_Y'
        a, b = lab['show']; end = scene.frame_end; fade = 12
        keys = [(1, 0.0)] if a > 1 else [(1, 1.0)]
        if a > 1:
            keys += [(a, 0.0), (a+fade, 1.0)]
        if b < end:
            keys += [(b-fade, 1.0), (b, 0.0)]
        _keys(o, 'wf_alpha', keys, 'LINEAR') if len(keys) > 1 else o.__setitem__('wf_alpha', keys[0][1])
        o['label_for'] = list(lab['select'])
        made.append(o)
    return made


# ---------- stage ----------------------------------------------------------------------------------------------------

def cut_view(s, stop):
    """IND-001: an induction stop's eye-level view (characters.stop_views) as eye, target, up and lens."""
    import characters
    v = characters.stop_views(s)[stop]; eye = Vector(v['at'])
    return eye, eye+Vector(v['look']), Vector(v['up']), v['lens']


def cut_text(s, stop):
    """IND-001 4.2: the caption of an induction stop: its place in the sequence, scenes and operating state (human_entry.induction_sequence)."""
    import human_entry as he
    seq = he.induction_sequence(s); q = next(q for q in s['induction']['stops'] if q['key'] == stop); o = seq['stops'][stop]
    order = [q['key'] for q in s['induction']['stops']]
    where = 'in the drum, synchronized with ring A' if q['at'] == 'vestibule' else 'at the deck'
    spin = f"rings at {o['rpm']:g} rpm, {o['g']:.2f} g {where}" if o['habitat'] == 'ROTATING' else 'rings stopped and locked'
    return [f"{order.index(stop)+1}/{len(order)} {q['title']} ({', '.join(q['scenes'])})",
            f"{o['state']}, step '{o['step']}': {spin} | sequence: owner Q48, identities open (Q49)"]


def plate_material():
    m, nt, out = _new_material('SHOT_LABEL_PLATE')
    dark = nt.nodes.new('ShaderNodeEmission'); dark.inputs['Color'].default_value = (0, 0, 0, 1)
    transparent = nt.nodes.new('ShaderNodeBsdfTransparent'); mix = nt.nodes.new('ShaderNodeMixShader'); mix.inputs[0].default_value = .85
    nt.links.new(transparent.outputs[0], mix.inputs[1]); nt.links.new(dark.outputs[0], mix.inputs[2]); nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return m


def cuts(root, scene, shot):
    """Camera cuts: per cut a shot-local camera (a copy of a saved source camera at its saved pose, or "stop" for an induction stop's view)
    bound to a timeline marker at its frame, with a caption parented to it and shown only during the cut."""
    s, *_ = spec.load(root); mat = label_material(); plate = plate_material(); out = []
    frames = [c['frame'] for c in shot['cuts']]+[scene.frame_end+1]
    for n, c in enumerate(shot['cuts']):
        data = bpy.data.cameras.new(f'SHOT_Cut_{n}'); cam = _owned(bpy.data.objects.new(data.name, data)); scene.collection.objects.link(cam)
        data.clip_start = .05; data.clip_end = 600
        if c['camera'] == 'stop':
            eye, target, up, data.lens = cut_view(s, c['stop'])
            z = (eye-target).normalized(); x = up.cross(z).normalized(); cam.matrix_world = Matrix.Translation(eye)@Matrix((x, z.cross(x), z)).transposed().to_4x4()
        else:
            src = bpy.data.objects[c['camera']]
            data.lens = src.data.lens; data.sensor_width = src.data.sensor_width; cam.matrix_world = world(src)
        cam['cut'] = c.get('stop', c['camera']); cam['source_camera'] = c['camera']
        marker = scene.timeline_markers.new(f"CUT_{n}_{cam['cut']}", frame=c['frame']); marker.camera = cam
        if 'stop' in c:
            depth = .25; width = 2*depth*math.tan(data.angle_x/2); h = width*.75; lines = cut_text(s, c['stop'])
            y0, y1 = h*(.44-.055*(len(lines)-1))-width*.012, h*.44+width*.034
            md = _owned(bpy.data.meshes.new(f'SHOT_CUT_PLATE_{n}'))
            md.from_pydata([(-width*.48, y0, 0), (width*.48, y0, 0), (width*.48, y1, 0), (-width*.48, y1, 0)], [], [(0, 1, 2, 3)]); md.materials.append(plate)
            made = [_owned(bpy.data.objects.new(md.name, md))]; made[0].location = (0, 0, -depth*1.002)
            for i, text in enumerate(lines):
                td = _owned(bpy.data.curves.new(f'SHOT_CUT_LABEL_{n}_{i}', 'FONT')); td.body = text; td.size = width*(.026 if i == 0 else .018)
                td.materials.append(mat); o = _owned(bpy.data.objects.new(td.name, td)); o.location = (-width*.47, h*(.44-i*.055), -depth); o['wf_alpha'] = 1.0
                made.append(o)
            for o in made:
                scene.collection.objects.link(o); o.parent = cam; o.visible_shadow = False
                _keys(o, 'hide_render', [(1, True), (c['frame'], False), (frames[n+1], True)] if c['frame'] > 1 else [(1, False), (frames[n+1], True)], 'CONSTANT')
        out.append(cam)
    scene.camera = out[0]
    return out


def stage(scene, shot, items, vectors, rep, root=ROOT):
    """Camera fitted to the fully exploded extent (or the camera cuts, see cuts()), lights and world. All shot-local."""
    if 'cuts' in shot:
        camera = cuts(root, scene, shot)[0]
        world = bpy.data.worlds.new('SHOT_World'); scene.world = world; world.use_nodes = True
        bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
        bg.inputs['Color'].default_value = (.02, .025, .035, 1); bg.inputs['Strength'].default_value = .4
        for i, (direction, energy) in enumerate([((.3, -.8, -.6), 2.5), ((-.5, .6, -.4), 1.2)]):
            light = bpy.data.lights.new(f'SHOT_Sun_{i}', 'SUN'); light.energy = energy; light.angle = .15
            o = _owned(bpy.data.objects.new(light.name, light)); scene.collection.objects.link(o)
            o.rotation_euler = (-Vector(direction)).to_track_quat('Z', 'X').to_euler()
        return camera
    cam_spec = shot['camera']; aspect = 4/3
    data = bpy.data.cameras.new('SHOT_Camera'); camera = _owned(bpy.data.objects.new('SHOT_Camera', data)); scene.collection.objects.link(camera)
    data.sensor_fit = 'VERTICAL'; data.angle = math.radians(cam_spec['fov_deg']); data.clip_start = .1; data.clip_end = 5000
    direction = Vector(cam_spec['direction']).normalized(); quat = (-direction).to_track_quat('-Z', 'Y')
    if 'focus' in cam_spec:
        target = Vector(cam_spec['focus']); distance = rp.fit_distance(cam_spec['radius']*cam_spec.get('margin', 1.05), cam_spec['fov_deg'])
    else:
        # Fit the assembled and the fully exploded extents in the frame, projected into the camera's axes.
        peak = max([v for _, v in rp.schedule(items, shot['ops'])['explode']]+[0.0])
        fit = rp.select(items, cam_spec['fit']) if cam_spec.get('fit') else None   # frame only these items (an isolated subsystem)
        pts = [(Vector(i['center'])+Vector(vectors[i['group']])*f, i['radius']) for i in items if i['solid'] and (fit is None or i['key'] in fit)
               for f in {0.0, peak}]
        for lab in shot.get('labels', []):  # labels ride with their group; keep their text in frame too
            chosen = [i for i in items if i['key'] in rp.select(items, lab['select'])]
            anchor = sum((Vector(i['center']) for i in chosen), Vector())/len(chosen)+Vector(lab.get('offset', (0, 0, 0)))
            half = .32*lab.get('size', 1.2)*len(lab['text'])
            pts += [(anchor+Vector(vectors[chosen[0]['group']])*f, half) for f in {0.0, peak}]
        low = Vector([min(c[k]-r for c, r in pts) for k in range(3)]); high = Vector([max(c[k]+r for c, r in pts) for k in range(3)])
        target = (low+high)/2; inv = quat.inverted()
        local = [(inv@(c-target), r) for c, r in pts]
        cx = (max(q.x+r for q, r in local)+min(q.x-r for q, r in local))/2; cy = (max(q.y+r for q, r in local)+min(q.y-r for q, r in local))/2
        target = target+quat@Vector((cx, cy, 0)); local = [(inv@(c-target), r) for c, r in pts]
        tv = math.tan(data.angle/2); th = tv*aspect
        distance = cam_spec.get('margin', 1.05)*max(max(q.z+r+(abs(q.x)+r)/th, q.z+r+(abs(q.y)+r)/tv) for q, r in local)
    camera.location = target+direction*distance
    camera.rotation_euler = quat.to_euler()
    scene.camera = camera
    world = bpy.data.worlds.new('SHOT_World'); scene.world = world; world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
    if rep == 'REP_HOLOGRAM':
        bg.inputs['Color'].default_value = (.004, .007, .014, 1); bg.inputs['Strength'].default_value = 1
        scene.view_settings.view_transform = 'Standard'  # keep the hologram hues saturated
    else:
        bg.inputs['Color'].default_value = (.05, .07, .095, 1); bg.inputs['Strength'].default_value = .7
        for i, (loc, energy) in enumerate([((70, -100, 180), 2.6), ((-90, 60, 100), 1.6), ((20, 100, -100), .9)]):
            light = bpy.data.lights.new(f'SHOT_Sun_{i}', 'SUN'); light.energy = energy; light.angle = .15
            o = _owned(bpy.data.objects.new(light.name, light)); scene.collection.objects.link(o); o.location = loc
            o.rotation_euler = (-o.location).to_track_quat('-Z', 'Y').to_euler()
    return camera


def render_settings(scene, rep, size=768, samples=None):
    scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.use_denoising = True; scene.cycles.seed = 0
    scene.cycles.samples = samples or (32 if rep == 'REP_HOLOGRAM' else 24)
    scene.cycles.transparent_max_bounces = 128; scene.cycles.max_bounces = 8
    scene.render.resolution_x = size; scene.render.resolution_y = round(size*.75); scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'


# ---------- one shot ------------------------------------------------------------------------------------------------

def build(root, name, shot, config, size=768):
    """Build one shot from scratch in the current (empty) file. Returns the scene, the items and the key tables."""
    scene = bpy.context.scene; scene.name = name
    scene['wf_shot'] = name; scene['wf_owner'] = OWNER; scene['representation'] = shot['representation']
    scene['description'] = shot['description']
    scene['ownership'] = 'References the saved assets through linked data; never saved into them'
    scene['wf_sources'] = [f'{s["asset"]}:{s["collection"]}' for s in shot['sources']]
    scene.frame_start = 1; scene.frame_end = shot['frame_end']; scene.render.fps = config.get('fps', 24)
    if shot.get('subsystems'):
        subs = rp.load_subsystems(root, shot['subsystems'])
        shot = dict(shot, _subsystems=subs, labels=shot.get('labels', [])+(rp.subsystem_labels(subs, (1, shot['frame_end'])) if shot.get('subsystem_labels', True) else []))
        scene['wf_subsystems'] = shot['subsystems']
    linked = [(src, link_source(root, src)) for src in shot['sources']]
    if shot.get('preset'):
        pose_preset(root, shot['preset']); scene['wf_preset'] = shot['preset']
    pose_controls(shot.get('controls', {}))
    items = []
    for src, collection in linked:
        items += gather(collection, src)
    for item in items if shot.get('_subsystems') else []:   # 'subsystem:Sxx' selectors in ops and labels
        item['subsystem'] = rp.classify(item, shot['_subsystems'])['id']
    ctrl = control(scene)
    section = section_empty(scene, shot['section']) if shot['representation'] == 'REP_CUTAWAY' else None
    coll, objects, groups, vectors = represent(scene, items, shot['representation'], shot, ctrl, shot.get('colors', {}),
                                               config['highlight_color'], section)
    tables = rp.schedule(items, shot['ops'], shot.get('initial'))
    apply_schedule(objects, ctrl, tables)
    camera = stage(scene, shot, items, vectors, shot['representation'], root)
    labels(scene, shot, items, groups, camera)
    render_settings(scene, shot['representation'], size)
    scene.frame_set(1)
    return scene, items, tables, objects


def save(path):
    """Save the shot only; every library path is written relative, and no source datablock is made local."""
    local = [d.name for d in [*bpy.data.meshes, *bpy.data.curves] if d.library is None and d.get('wf_owner') != OWNER]
    if local:
        raise RuntimeError(f'Local geometry would make the shot own source data: {local[:5]}')
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path), relative_remap=True, compress=True)
