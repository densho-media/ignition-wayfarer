"""Small Blender helpers, adapted from the inspected workspace patterns."""
from datetime import datetime, timezone
from pathlib import Path
import math
import shutil
import bpy
from mathutils import Vector
from spec import digest

OWNER = 'wayfarer.p0'
GENERATOR = 'WF_PROXY_V3'


def source_inspected_on(source_text):
    """Latest inspected_on across the source-map records."""
    return max(r['inspected_on'] for r in __import__('tomllib').loads(source_text)['sources'].values() if 'inspected_on' in r)


def collection(name, parent):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
    if c.library:
        raise ValueError(f'Cannot edit linked collection {name}')
    if c.name not in parent.children:
        parent.children.link(c)
    return c


def begin(path, name):
    """Reopen an asset, preserving everything not explicitly generator-owned."""
    if path.exists():
        bpy.ops.wm.open_mainfile(filepath=str(path))
        if bpy.context.scene.get('wf_asset') != name:
            raise ValueError(f'Refusing foreign asset destination: {path}')
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene['wf_asset'] = name
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    root = collection(name, scene.collection)
    gen = collection(f'GEN_{name}', root)
    art = collection(f'ART_{name}', root)
    if gen.get('wf_owner') not in (None, OWNER):
        raise ValueError(f'Foreign collection owner: {gen.name}')
    for obj in list(gen.objects):
        if obj.get('wf_owner') == OWNER and len(obj.users_collection) == 1:
            bpy.data.objects.remove(obj, do_unlink=True)
        else:
            # Preserve unowned or multiply linked content even if placed in GEN.
            if obj.name not in art.objects:
                art.objects.link(obj)
            gen.objects.unlink(obj)
    if gen.children:
        raise ValueError('Nested collections in GEN are preserved: move them to ART before rebuilding')
    for table in [bpy.data.meshes, bpy.data.curves, bpy.data.materials]:
        for block in list(table):
            if block.users == 0 and block.get('wf_owner') == OWNER:
                table.remove(block)
    gen['wf_owner'] = OWNER
    root['representation'] = 'REP_PROXY'
    return root, gen


def tag(obj, ident, kind='geometry', status='PROTOTYPE', source='prototype'):
    obj['wf_owner'] = OWNER
    obj['component_id'] = ident
    obj['kind'] = kind
    obj['canon_status'] = status
    obj['geometry_status'] = 'PROTOTYPE'
    obj['source_ref'] = source
    obj['representation'] = 'REP_PROXY'
    obj['generator'] = GENERATOR
    if obj.data:
        obj.data['wf_owner'] = OWNER
    return obj


def empty(c, name, xyz=(0, 0, 0), ident=None, kind='interface'):
    obj = bpy.data.objects.new(name, None)
    c.objects.link(obj)
    obj.location = xyz
    obj.empty_display_type = 'ARROWS'
    obj.empty_display_size = 0.7
    return tag(obj, ident or name, kind)


def material(name, color, emission=0, alpha=1):
    name = f'WF_MAT_{name}'
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m['wf_owner'] = OWNER
    m.diffuse_color = (*color, alpha)
    m.use_nodes = True
    node = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    node.inputs['Base Color'].default_value = (*color, 1)
    node.inputs['Roughness'].default_value = 0.55
    if emission:
        node.inputs['Emission Color'].default_value = (*color, 1)
        node.inputs['Emission Strength'].default_value = emission
    if alpha < 1:
        # Debug/field layers: see-through overlays, never solid walls.
        node.inputs['Alpha'].default_value = alpha
        m.surface_render_method = 'BLENDED'
    return m


def apply_look(s):
    """FUT-003: the S004 look (look.py) over the loaded materials, in memory only (stills, runtime export); never saved into an asset.
    Returns {material: class} of what it changed."""
    import look
    done = {}
    # Each linked subsystem or component file brings its own copy of a material: change every copy (linked data is editable in memory).
    copies = {}
    for m in bpy.data.materials:
        if m.name.startswith('WF_MAT_') and m.use_nodes:
            copies.setdefault(m.name[7:], []).append(m)
    for name, q in look.surfaces(s).items():
        for m in copies.get(name, ()):
            node = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
            node.inputs['Base Color'].default_value = (*q['color'], 1)
            node.inputs['Roughness'].default_value = q['roughness']
            node.inputs['Metallic'].default_value = q['metallic']
            m.diffuse_color = (*q['color'], m.diffuse_color[3])
            done[name] = q['cls']
    for name, q in look.lights(s).items():
        for m in copies.get(name, ()):
            node = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
            node.inputs['Base Color'].default_value = (*q['color'], 1)
            node.inputs['Emission Color'].default_value = (*q['color'], 1)
            node.inputs['Emission Strength'].default_value = q['strength']
            m.diffuse_color = (*q['color'], 1)
            done[name] = 'light_' + q['cls']
    return done


def driven_material(name, color, strength, alpha=1.0, base=0.12):
    """Emission and transparency scaled by the object's colour alpha, so one driver per object sets its intensity."""
    name = f'WF_MAT_{name}'
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m['wf_owner'] = OWNER
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    nodes, links = m.node_tree.nodes, m.node_tree.links
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial'); bsdf = nodes.new('ShaderNodeBsdfPrincipled'); info = nodes.new('ShaderNodeObjectInfo')
    bsdf.inputs['Base Color'].default_value = (*(base*x for x in color), 1)
    bsdf.inputs['Roughness'].default_value = 0.5
    bsdf.inputs['Emission Color'].default_value = (*color, 1)
    for socket, scale in [('Emission Strength', strength), ('Alpha', alpha)]:
        mul = nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = scale
        links.new(info.outputs['Alpha'], mul.inputs[0]); links.new(mul.outputs[0], bsdf.inputs[socket])
    links.new(bsdf.outputs[0], out.inputs['Surface'])
    m.surface_render_method = 'BLENDED'
    m['driven_by'] = 'object colour alpha'
    return m


def mesh(c, name, vertices, faces, mat, ident=None, kind='geometry'):
    data = bpy.data.meshes.new(f'{name}_Mesh')
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    c.objects.link(obj)
    if mat:
        data.materials.append(mat)
    return tag(obj, ident or name, kind)


def loft(c, name, rings, mat, center=(0, 0, 0), caps=True, segments=32, kind='geometry'):
    """Axis-X solid or open surface, rings = (x, radius)."""
    vertices = [(x+center[0], r*math.cos(a*2*math.pi/segments)+center[1], r*math.sin(a*2*math.pi/segments)+center[2]) for x,r in rings for a in range(segments)]
    faces = [(k*segments+j, k*segments+(j+1)%segments, (k+1)*segments+(j+1)%segments, (k+1)*segments+j) for k in range(len(rings)-1) for j in range(segments)]
    if caps:
        faces += [tuple(reversed(range(segments))), tuple((len(rings)-1)*segments+j for j in range(segments))]
    return mesh(c, name, vertices, faces, mat, kind=kind)


def cylinder(c, name, x, length, radius, mat, y=0, z=0, kind='geometry'):
    return loft(c, name, [(-length/2, radius), (length/2, radius)], mat, (x,y,z), kind=kind)


def annulus(c, name, x, length, outer, inner, mat):
    return loft(c, name, [(x-length/2, outer), (x+length/2, outer), (x+length/2, inner), (x-length/2, inner), (x-length/2, outer)], mat, caps=False)


def axis_frame(a, b):
    """Unit axis e from a to b, two unit normals across it (n2 = e x n1) and the length."""
    d = Vector(b)-Vector(a); e = d.normalized()
    ref = Vector((1, 0, 0)) if abs(e.x) < .9 else Vector((0, 1, 0))
    n1 = (ref-e*ref.dot(e)).normalized()
    return e, n1, e.cross(n1), d.length


def revolve_mesh(a, b, prof, n=64):
    """Closed (t, rho) profile (t = distance from a toward b, rho > 0) revolved about the axis a->b into a closed manifold: vertices and
    outward-wound quads (the profile is turned clockwise in (t, rho), as in loft())."""
    e, n1, n2, _ = axis_frame(a, b); a = Vector(a)
    area = sum(t0*r1-t1*r0 for (t0, r0), (t1, r1) in zip(prof, prof[1:]+prof[:1]))
    prof = list(reversed(prof)) if area > 0 else list(prof); m = len(prof)
    vs = [tuple(a+e*t+(n1*math.cos(2*math.pi*k/n)+n2*math.sin(2*math.pi*k/n))*r) for t, r in prof for k in range(n)]
    return vs, [(j*n+k, j*n+(k+1) % n, (j+1) % m*n+(k+1) % n, (j+1) % m*n+k) for j in range(m) for k in range(n)]


def cylinder_mesh(a, b, radius, n=64):
    """Closed cylinder from a to b: vertices and outward-wound faces."""
    e, n1, n2, L = axis_frame(a, b); a = Vector(a)
    vs = [tuple(a+e*t+(n1*math.cos(2*math.pi*k/n)+n2*math.sin(2*math.pi*k/n))*radius) for t in (0.0, L) for k in range(n)]
    return vs, [(k, (k+1) % n, n+(k+1) % n, n+k) for k in range(n)]+[tuple(reversed(range(n))), tuple(n+k for k in range(n))]


def cut(obj, cutters, n=64, operation='DIFFERENCE'):
    """Applies EXACT boolean differences (or, with operation INTERSECT, intersections) of closed cylinders (a, b, radius), boxes (8 corners) or
    X-axis prisms (dict x0, x1, polygon) to a mesh object; the cutters are temporary (HUM-001 openings and trims, CIRC-001 door openings)."""
    scene = bpy.context.scene; tools = []
    for k, cutter in enumerate(cutters):
        if isinstance(cutter, dict):
            # a prism along X from x0 to x1 over a convex (y, z) polygon, counter-clockwise seen from +X (the hexagonal EYE ports)
            poly = cutter['polygon']; m = len(poly)
            vs = [(x, y, z) for x in (cutter['x0'], cutter['x1']) for y, z in poly]
            fs = [tuple(reversed(range(m))), tuple(range(m, 2*m))]+[(i, (i+1) % m, m+(i+1) % m, m+i) for i in range(m)]
        elif len(cutter) == 8:
            # CIRC-001: a box cutter, 8 corners indexed 4*i + 2*j + k along a right-handed frame (the interior box winding)
            vs, fs = list(cutter), [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        else:
            a, b, r = cutter
            vs, fs = cylinder_mesh(a, b, r, n)
        data = bpy.data.meshes.new(f'WF_Cutter_{k}'); data.from_pydata(vs, [], fs); data.update()
        tool = bpy.data.objects.new(data.name, data); scene.collection.objects.link(tool); tools.append(tool)
        mod = obj.modifiers.new(f'Cut_{k}', 'BOOLEAN'); mod.operation = operation; mod.solver = 'EXACT'; mod.object = tool
    data = bpy.data.meshes.new_from_object(obj.evaluated_get(bpy.context.evaluated_depsgraph_get())); old = obj.data; name = old.name
    obj.modifiers.clear(); obj.data = data; bpy.data.meshes.remove(old); data.name = name; data['wf_owner'] = OWNER
    for tool in tools:
        data = tool.data; bpy.data.objects.remove(tool, do_unlink=True); bpy.data.meshes.remove(data)
    return obj


def line(c, name, points, radius, mat, kind='geometry'):
    data = bpy.data.curves.new(f'{name}_Curve', 'CURVE')
    data.dimensions = '3D'
    data.resolution_u = 1
    data.bevel_depth = radius
    data.bevel_resolution = 1
    spline = data.splines.new('POLY')
    spline.points.add(len(points)-1)
    for p, co in zip(spline.points, points):
        p.co = (*co, 1)
    obj = bpy.data.objects.new(name, data)
    c.objects.link(obj)
    data.materials.append(mat)
    return tag(obj, name, kind)


def ring(c, name, x, radius, thickness, mat, kind='geometry'):
    return line(c, name, [(x, radius*math.cos(t*2*math.pi/64), radius*math.sin(t*2*math.pi/64)) for t in range(65)], thickness, mat, kind)


def link_instance(c, filepath, collection_name, name, xyz=(0,0,0), rx=0, ident=None):
    filepath = filepath.resolve()
    linked = next((x for x in bpy.data.collections if x.library and x.name == collection_name and Path(bpy.path.abspath(x.library.filepath)).resolve() == filepath), None)
    if linked is None:
        with bpy.data.libraries.load(str(filepath), link=True) as (available, result):
            if collection_name not in available.collections:
                raise ValueError(f'Missing library collection {collection_name}')
            result.collections = [collection_name]
        linked = result.collections[0]
    obj = empty(c, name, xyz, ident, 'instance')
    obj.instance_type = 'COLLECTION'
    obj.instance_collection = linked
    obj.rotation_euler.x = rx
    return obj


def save(path, root_collection, spec_text, source_text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        directory = path.parent/'milestones'
        directory.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        shutil.copy2(path, directory/f'{path.stem}_{stamp}.blend')
        # Keep the newest three backups per asset; *_RETIRED_* files never match this pattern.
        backups = sorted(directory.glob(f'{path.stem}_[0-9]*T*Z.blend'))
        for old in backups[:-3]:
            old.unlink()
    for name, content in [('WF_SOURCE_SNAPSHOT', spec_text), ('WF_PROVENANCE_SNAPSHOT', source_text)]:
        text = bpy.data.texts.get(name) or bpy.data.texts.new(name)
        text.clear()
        text.write(content)
    holders=[bpy.context.scene, root_collection]
    if bpy.data.objects.get('WF_ROOT') is not None:
        holders.append(bpy.data.objects['WF_ROOT'])
    for holder in holders:
        holder['spec_hash'] = digest(spec_text)
        holder['source_map_hash'] = digest(source_text)
        holder['spec_version'] = __import__('tomllib').loads(spec_text)['schema_version']
        holder['source_inspected_on'] = source_inspected_on(source_text)
        holder['generated_by'] = GENERATOR
    # Direct links are always relative to the file being saved. Indirect library
    # paths belong to their owning libraries and must not be rewritten here.
    for library in bpy.data.libraries:
        if library.parent is None:
            absolute = Path(bpy.path.abspath(library.filepath)).resolve()
            import os
            library.filepath = '//' + os.path.relpath(absolute, path.parent)
    bpy.context.scene.world = bpy.context.scene.world or bpy.data.worlds.new('WF_World')
    bpy.context.scene.world.color = (0.08, 0.08, 0.08)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(path), relative_remap=False)
    print(f'WF_SAVED {path.name}', flush=True)


def owned_action(name):
    """Fresh generator-owned action; begin() does not purge fake-user actions, so replace ours and refuse foreign ones."""
    old = bpy.data.actions.get(name)
    if old is not None:
        if old.get('wf_owner') != OWNER or old.library:
            raise ValueError(f'Refusing to replace foreign action {name}')
        bpy.data.actions.remove(old)
    action = bpy.data.actions.new(name)
    action['wf_owner'] = OWNER
    action.use_fake_user = True
    return action


def drop_stale_actions(keep):
    """Remove generator-owned local actions that the generator no longer makes (a renamed or retired action in a reopened file).
    Foreign and linked actions are never touched."""
    for action in list(bpy.data.actions):
        if action.library is None and action.get('wf_owner') == OWNER and action.name not in keep:
            bpy.data.actions.remove(action)


def pose_drive_state(values):
    """In-memory P1F pose: set the (usually linked) drive manifold control and re-evaluate its drivers. Never saved."""
    control = bpy.data.objects['DRIVE_MANIFOLD_CTRL']
    for key, value in values.items():
        control[key] = float(value)
    control.update_tag()
    for obj in bpy.data.objects:
        if obj.get('drive_driven'):
            obj.update_tag()
            if obj.data is not None:
                obj.data.update_tag()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    return control


def pose_forward_state(values):
    """In-memory forward-defence pose: set the (usually linked) FORWARD_DEFENSE_CTRL values and re-evaluate its drivers. Never saved."""
    control = bpy.data.objects['FORWARD_DEFENSE_CTRL']
    for key, value in values.items():
        control[key] = float(value)
    control.update_tag()
    for obj in bpy.data.objects:
        if obj.get('forward_driven'):
            obj.update_tag()
            if obj.data is not None:
                obj.data.update_tag()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    return control


def pose_radiator_state(values):
    """In-memory radiator-health pose: set the (usually linked) RADIATOR_HEALTH_CTRL values and re-evaluate its drivers. Never saved."""
    control = bpy.data.objects['RADIATOR_HEALTH_CTRL']
    for key, value in values.items():
        control[key] = float(value)
    control.update_tag()
    for obj in bpy.data.objects:
        if obj.get('radiator_driven'):
            obj.update_tag()
            if obj.data is not None:
                obj.data.update_tag()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    return control


def pose_transfer(s, value=1.0, sync=None):
    """Q46 in-memory pose of the despun transfer (never saved): every spine-port gate, drum door and crew-tube hatch opened to `value` (1 open,
    0 closed, the saved state) and, if given, each drum's drum_sync (0 despun at the index, 1 turning with its ring). At the index angle (the
    docked pose) all three of a drum's openings line up with their tubes, so an open pose there is the indexed transfer of 15!I87."""
    import crew_transfer
    gate = bpy.data.objects.get('CREW_PORT_GATE_CTRL')
    for j in s['human_entry']['vestibule_rotors']:
        ctrl = bpy.data.objects[f'TRANSFER_{j}_CTRL']
        for q in crew_transfer.closures(s, j):
            if q['kind'] == 'PORT_GATE':
                gate[f"{q['name']}_open"] = float(value)
            else:
                ctrl[f"{'door' if q['kind'] == 'DRUM_DOOR' else 'hatch'}_open_{q['sector']}"] = float(value)
        if sync is not None:
            ctrl['drum_sync'] = float(sync)
        ctrl.update_tag()
    gate.update_tag()
    for obj in bpy.data.objects:
        if obj.get('kind') in ('transfer_closure', 'transfer_drum'):
            obj.update_tag()


def pose_configuration(s, name):
    """In-memory pose of the one vehicle for a buildable preset (never saved): set the linked ROTOR_n_MECH_CTRL values the preset names
    (ring spin and locks), tag the rotors for re-evaluation, and pose the drive display through the drive control. The rotor
    rotation drivers then follow spin_fraction; the saved file keeps its saved preset."""
    import rotor_interface
    state = rotor_interface.configuration_state(s, name)
    for rot in rotor_interface.rotors(s):
        control = bpy.data.objects[rotor_interface.control(rot['index'])]
        for key, value in {**state, **{k: 0.0 for k in rotor_interface.TURN_PROPS}}.items():      # a preset turns by the product form
            control[key] = float(value)
        control.update_tag()
        bpy.data.objects[f"Rotor_{rot['index']}"].update_tag()
        drum = bpy.data.objects.get(f"Drum_{rot['index']}")      # Q46: the despun drum's driver reads the rotor control too
        if drum is not None:
            drum.update_tag()
    import drive_manifold
    pose_drive_state(drive_manifold.configuration_state(s, name))
    import forward_shield
    pose_forward_state(forward_shield.configuration_state(s, name))
    import radiator_health
    pose_radiator_state(radiator_health.configuration_state(s, name))
    return state


def pose_timeline(s, values):
    """In-memory pose of the one vehicle at a First Ignition timeline sample (flight_timeline.control_values: {control: {property: value}}):
    the rotor, drive, forward-defense and radiator controls take the sample's values. Never saved; it generalizes pose_configuration."""
    import rotor_interface
    for rot in rotor_interface.rotors(s):
        name = rotor_interface.control(rot['index']); control = bpy.data.objects[name]
        for key, value in values[name].items():
            control[key] = float(value)
        control.update_tag()
        bpy.data.objects[f"Rotor_{rot['index']}"].update_tag()
        drum = bpy.data.objects.get(f"Drum_{rot['index']}")      # Q46: the despun drum's driver reads the rotor control too
        if drum is not None:
            drum.update_tag()
    pose_drive_state(values['DRIVE_MANIFOLD_CTRL'])
    pose_forward_state(values['FORWARD_DEFENSE_CTRL'])
    pose_radiator_state(values['RADIATOR_HEALTH_CTRL'])
    return values


def drive_debug_visibility(magnetics=False, optics=False, separatrices=None):
    """In-memory debug toggles (never saved): set the drive control's switches; the DRIVE_DEBUG_* hide drivers follow."""
    separatrices = magnetics if separatrices is None else separatrices
    return pose_drive_state({'magnetic_field_debug': float(magnetics), 'optical_debug': float(optics), 'separatrix_debug': float(separatrices)})
