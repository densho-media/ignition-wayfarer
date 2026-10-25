"""Export the generated COAST snapshot, with explicit material and inclusion rules.

All conversion is in memory. Node IDs identify this static snapshot, not future
moving mechanisms; instance placement disambiguates reusable component IDs.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'src/wayfarer'), str(ROOT / 'src/wayfarer/build')]
from spec import load, digest
from common import apply_look, pose_configuration, pose_transfer, pose_timeline, pose_drive_state, pose_forward_state, pose_radiator_state, OWNER
import sim_rig
import flight_timeline
import human_entry
import look
import production_detail
import representation
import drive_manifold
import forward_shield
import radiator_health
import rotor_interface

TIMELINE = 'wf_first_ignition_timeline.json'
EXCLUDED = {'scale_reference', 'sim_proxy', 'magnetic_field', 'plasma', 'optical_beam'}


def surface(source, alpha, cache):
    """Resolve the existing object-alpha shader into static Principled values."""
    if source is None:
        if 'unassigned' not in cache:
            material = bpy.data.materials.new('Runtime_Unassigned')
            material.diffuse_color = (0.8, 0.8, 0.8, 1)
            cache['unassigned'] = material
        return cache['unassigned']
    key = (source.name, round(alpha, 6) if source.get('driven_by') else 1.0)
    if key in cache:
        return cache[key]
    out = bpy.data.materials.new('Runtime_' + source.name + '_' + str(len(cache)))
    out.use_nodes = True
    dst = next(n for n in out.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    src = next((n for n in source.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if src is None:
        raise ValueError(f'Unsupported material: {source.name}')
    for name in ('Base Color', 'Metallic', 'Roughness', 'Emission Color', 'Emission Strength', 'Alpha'):
        socket = src.inputs[name]
        value = socket.default_value
        if socket.is_linked:
            node = socket.links[0].from_node
            if not (source.get('driven_by') == 'object colour alpha' and node.type == 'MATH'
                    and node.operation == 'MULTIPLY'):
                raise ValueError(f'Unsupported shader link: {source.name}/{name}')
            value = alpha * node.inputs[1].default_value
        dst.inputs[name].default_value = value
    if dst.inputs['Alpha'].default_value < 1:
        out.surface_render_method = 'BLENDED'
    out.use_backface_culling = False
    cache[key] = out
    return out


# RT-003 display drivers the runtime replays as tracks: visibility, the object-alpha channel and scale.
DISPLAY_PATHS = {'hide_render', 'color', 'scale'}
DRIVER_NAMES = {n: getattr(math, n) for n in dir(math) if not n.startswith('_')} | {'min': min, 'max': max, 'abs': abs, 'round': round}


def timeline_controls(timeline, frame):
    """{control: {property: value}} at a frame, from the packaged timeline's bound channels (as flight_timeline.control_values)."""
    out = {}
    for name, channel in timeline['channels'].items():
        if channel.get('binding'):
            for control in channel['binding']['controls']:
                out.setdefault(control, {})[channel['binding']['property']] = float(flight_timeline.value_at(channel['keys'], frame))
    return out


def display_states(s):
    """RT-003 named poses outside the timeline, from the pure modules: every buildable configuration, then the preview display poses
    (forward defence, radiator health) on their base configuration. {name: {kind, base, status, spin_fraction, controls}}."""
    out = {}
    for name, cfg in s['configuration'].items():
        if isinstance(cfg, dict) and cfg.get('buildable'):
            out[name] = {'kind': 'configuration', 'base': name, 'status': cfg['canon_status'],
                         'spin_fraction': rotor_interface.configuration_state(s, name)['spin_fraction'],
                         'controls': {drive_manifold.CONTROL: drive_manifold.configuration_state(s, name),
                                      forward_shield.CONTROL: forward_shield.configuration_state(s, name),
                                      radiator_health.CONTROL: radiator_health.configuration_state(s, name)}}
    for module, poses in ((forward_shield, s['forward_defense']['display_poses']), (radiator_health, radiator_health.table(s)['display_poses'])):
        for name, pose in poses.items():
            if isinstance(pose, dict):
                base = out[pose['base']]
                out[name] = {**base, 'kind': 'display_pose', 'base': pose['base'], 'status': poses['status'],
                             'controls': {**base['controls'], module.CONTROL: module.display_pose(s, name)}}
    # The drive actions that settle away from both nominal and neutral (idle, laser, gate and flux-channel failures), at their last
    # key on HIGH_POWER; startup and shutdown are in the timeline, and the steering demos settle back to nominal.
    base = out['HIGH_POWER']
    for name, action in drive_manifold.actions(s).items():
        last = action['keys'][-1][1]
        if all(any(abs(last[k] - ref[k]) > 1e-9 for k in last) for ref in (drive_manifold.nominal(s), drive_manifold.neutral(s))):
            out[name] = {**base, 'kind': 'drive_action', 'base': 'HIGH_POWER', 'status': 'PROTOTYPE', 'description': action['description'],
                         'controls': {**base['controls'], drive_manifold.CONTROL: {**base['controls'][drive_manifold.CONTROL], **last}}}
    return out


def pose_state(state):
    """In-memory pose of the drive, forward-defence and radiator controls at a named state (never saved; the rotors keep their pose)."""
    pose_drive_state(state['controls'][drive_manifold.CONTROL])
    pose_forward_state(state['controls'][forward_shield.CONTROL])
    pose_radiator_state(state['controls'][radiator_health.CONTROL])


def display_tracks(timeline, states):
    """Bake every display driver that reads only timeline-bound control properties into keyed tracks over the timeline, by evaluating
    the driver's own expression (Blender's driver namespace: math, min, max) at the channels' keys and at every frame of their ramps,
    and into one value per named state (display_states). One track per object: `opacity` (hidden 0, else the driven object alpha) and
    `scale_x/y/z` in runtime local axes, relative to the staged pose. Objects that never change are left to the static export."""
    bound = {(control, ch['binding']['property']): name for name, ch in timeline['channels'].items() if ch.get('binding')
             for control in ch['binding']['controls']}
    channels = timeline['channels']
    out = {}
    for obj in bpy.data.objects:
        if obj.get('wf_owner') != OWNER or not obj.animation_data:
            continue
        drivers = []
        for fc in obj.animation_data.drivers:
            if fc.data_path not in DISPLAY_PATHS or (fc.data_path == 'color' and fc.array_index != 3):
                continue
            inputs, now = {}, {}
            for var in fc.driver.variables:
                target = var.targets[0]
                key = (target.id.name if target.id else None, target.data_path.strip('[]"'))
                if var.type != 'SINGLE_PROP' or key not in bound:
                    break
                inputs[var.name] = (bound[key], key)
                now[var.name] = float(target.id[key[1]])
            else:
                if inputs:
                    drivers.append((fc.data_path, fc.array_index, fc.driver.expression, inputs, now))
        if not drivers:
            continue
        used = {c for *_, inputs, _ in drivers for c, _ in inputs.values()}
        frames, ramps = set(), set()
        for c in used:
            keys = channels[c]['keys']
            frames |= {float(k[0]) for k in keys}
            for a, b in zip(keys, keys[1:]):
                if a[2] == 'LINEAR' and a[1] != b[1]:
                    span = range(int(a[0]), int(b[0]) + 1)
                    frames |= {float(f) for f in span}
                    ramps |= {float(f) for f in span[:-1]}
        frames = sorted(frames)
        scale_axes = sorted({i for path, i, *_ in drivers if path == 'scale'})

        def evaluate(names):
            hidden, alpha, scale = 0.0, 1.0, list(obj.scale)
            for path, index, expression, *_ in drivers:
                value = float(eval(expression, {'__builtins__': {}}, DRIVER_NAMES | names))
                if path == 'hide_render':
                    hidden = value
                elif path == 'color':
                    alpha = value
                else:
                    scale[index] = value
            return 0.0 if hidden >= 0.5 else max(0.0, min(1.0, alpha)), scale
        samples = [(f, *evaluate({v: flight_timeline.value_at(channels[c]['keys'], f) for *_, inputs, _ in drivers for v, (c, _) in inputs.items()}))
                   for f in frames]
        posed = {name: evaluate({v: float(state['controls'].get(k[0], {}).get(k[1], now[v])) for *_, inputs, now in drivers for v, (_, k) in inputs.items()})
                 for name, state in states.items()}
        # The static inspector shows the export's own pose (the saved preset), read from the controls as posed now.
        coast = evaluate({v: x for *_, now in drivers for v, x in now.items()})
        if len({(o, tuple(sc)) for _, o, sc in [*samples, *((n, *r) for n, r in posed.items())]}) == 1:
            continue
        # Stage where it shows at its fullest: the largest opacity, then the largest scale; a timeline frame before a named state.
        best = max([*samples, *((n, *r) for n, r in posed.items())], key=lambda r: (r[1], math.prod(r[2][i] for i in scale_axes) if scale_axes else 0.0))
        if best[1] <= 0.0 or any(best[2][i] <= 0.0 for i in scale_axes):
            continue

        def keyed(values):
            keys = []
            for (f, v) in values:
                interp = 'LINEAR' if f in ramps else 'CONSTANT'
                if keys and keys[-1][1] == v and keys[-1][2] == 'CONSTANT' and interp == 'CONSTANT':
                    continue
                keys.append([f, round(v, 6), interp])
            # A key between two equal neighbours changes nothing, whatever the interpolation.
            return [k for i, k in enumerate(keys) if not (0 < i < len(keys) - 1 and keys[i - 1][1] == k[1] == keys[i + 1][1])]
        # Blender local (x, y, z) are runtime local (x, -z, y): Blender y scales runtime z, Blender z scales runtime y.
        # Opacity and scale are relative to the staged pose, whose material and size the export already carries.
        track = {'object': obj.name, ('staged_state' if best[0] in states else 'staged_frame'): best[0],
                 'opacity': keyed([(f, o / best[1]) for f, o, _ in samples]), 'static_opacity': round(coast[0] / best[1], 6),
                 'states': {n: {'opacity': round(o / best[1], 6), **{'scale_' + 'xzy'[i]: round(sc[i] / best[2][i], 6) for i in scale_axes}}
                            for n, (o, sc) in posed.items()},
                 'drivers': [{'path': path, 'index': index, 'expression': expression, 'channels': sorted(set(inputs.values()))}
                             for path, index, expression, inputs, _ in drivers]}
        for index in scale_axes:
            track['scale_' + 'xzy'[index]] = keyed([(f, sc[index] / best[2][index]) for f, _, sc in samples])
        out[obj] = track
    return out


def mesh_signature(mesh):
    """Hash of everything that makes two evaluated meshes render the same in the runtime: vertex positions, face corners, corner normals,
    UV and colour layers, face material slots and the runtime materials (RT-005 sharing)."""
    import numpy as np
    h = hashlib.sha256()

    def add(seq, attr, n, dtype=np.float64, digits=5):
        a = np.empty(len(seq)*n, dtype=dtype); seq.foreach_get(attr, a)
        h.update((np.round(a, digits) if dtype == np.float64 else a).tobytes())
    add(mesh.vertices, 'co', 3); add(mesh.loops, 'vertex_index', 1, np.int64); add(mesh.polygons, 'loop_start', 1, np.int64)
    add(mesh.polygons, 'material_index', 1, np.int64)
    if hasattr(mesh, 'corner_normals'):
        add(mesh.corner_normals, 'vector', 3, digits=4)
    for layer in mesh.uv_layers:
        add(layer.data, 'uv', 2)
    for layer in mesh.color_attributes:
        add(layer.data, 'color', 4, digits=4)
    h.update(json.dumps([m.name if m else '' for m in mesh.materials]).encode())
    return h.hexdigest()


def dupli_key(instance):
    return (instance.object.original.as_pointer(), instance.parent.original.name if instance.parent else '', tuple(instance.persistent_id))


def offset_states(states):
    """RT-003 location drivers (the Crown carriages and shutters) and FWD-V2 rotation drivers (the Crown head gimbals): pose Blender at each named
    state and record how every mesh under a driven object moves from the current pose: a runtime-axis offset of its origin and, when it turns, the
    runtime-axis turn (row-major 3x3) that pre-multiplies its rest basis. Scale drivers are refused."""
    movers = {o for o in bpy.data.objects if o.get('wf_owner') == OWNER and o.animation_data
              and any(fc.data_path in ('location', 'rotation_euler') for fc in o.animation_data.drivers)}

    def moved(obj):
        while obj is not None and obj not in movers:
            obj = obj.parent
        return obj is not None

    def sample():
        bpy.context.scene.frame_set(1)
        deps = bpy.context.evaluated_depsgraph_get()
        return {dupli_key(i): i.matrix_world.copy() for i in deps.object_instances
                if i.object.type in {'MESH', 'CURVE'} and moved(i.object.original)}
    rest, out = sample(), {}
    C = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))          # Blender (x, y, z) -> runtime (x, z, -y)
    for name, state in states.items():
        pose_state(state)
        for key, matrix in sample().items():
            r0, r1 = rest[key].to_3x3(), matrix.to_3x3()
            if any(abs(a.length - b.length) > 1e-6 for a, b in zip(r0.col, r1.col)):
                raise ValueError(f'A driven mesh scales in state {name}')
            d = matrix.translation - rest[key].translation
            move = {'offset': [round(d.x, 6), round(d.z, 6), round(-d.y, 6)]}
            turn = C @ (r1 @ r0.inverted()) @ C.transposed()
            if any(abs(turn[i][j] - (i == j)) > 1e-6 for i in range(3) for j in range(3)):
                move['turn'] = [round(turn[i][j], 6) for i in range(3) for j in range(3)]
            out.setdefault(key, {})[name] = move
    return {key: moves for key, moves in out.items() if any(any(m['offset']) or 'turn' in m for m in moves.values())}


def rotor_bindings(deps, fps):
    """RT-003: each Rotor_n turns its children about its own X axis by the driver's rate times the timeline's spin_turned
    (revision.py, FUT-007). The snapshot is posed at turn 0 (frame 1, spin_integrated 0), so the runtime adds rate x spin_turned."""
    out = {}
    for instance in deps.object_instances:
        obj = instance.object.original
        if obj.get('kind') != 'rotor':
            continue
        driver = next(d for d in obj.animation_data.drivers if d.data_path == 'rotation_euler')
        if 'turned' not in driver.driver.expression:
            raise ValueError(f'{obj.name}: the rotation driver no longer reads spin_turned')
        m = instance.matrix_world
        to_runtime = lambda v: [round(v.x, 6), round(v.z, 6), round(-v.y, 6)]
        out[obj['component_id']] = {
            'lineage': obj['component_id'], 'channel': 'rotor.spin_turned',
            'pivot_runtime_m': to_runtime(m.translation), 'axis_runtime': to_runtime(m.to_3x3().col[0].normalized()),
            'rad_per_unit': obj['rpm'] * 2 * math.pi / 60 / fps,
            'basis': f'Rotor driver {driver.driver.expression!r}; spin_turned is in frames at full speed ({fps} fps)'}
    if len(out) != 2:
        raise ValueError(f'Expected two rotor bindings, found {sorted(out)}')
    return out


def runtime_vector(v):
    return [round(v.x, 6), round(v.z, 6), round(-v.y, 6)]


def mechanism_frames(s, closures=False):
    """RT-004: which placements each ring and despun drum carries, found by turning it in Blender rather than from names (linked sector
    contents carry no rotor lineage): set the rotor control's spin_turned (one second of turn at full speed), then also drum_sync 1, and see
    which instances move. Every moved placement must match a turn about the mover's exported pivot and axis. With closures (DOCKED, staged
    open): how each Q46 closure closes in Blender (pose_transfer 0), as a slide or as a turn about its frame's axis, checked the same way.
    Also the primary port's hinged leaves and the induction route's sector leaves. Restores the staged pose. Returns ({dupli_key: mechanism id},
    rotors, drums, closures, {dupli_key: closure name})."""
    import crew_transfer
    scene = bpy.context.scene; fps = scene.render.fps

    def sample():
        scene.frame_set(1); deps = bpy.context.evaluated_depsgraph_get()
        return {dupli_key(i): (i.matrix_world.copy(), i.object.original.name) for i in deps.object_instances}

    def named(state, name):
        return next(m for m, n in state.values() if n == name)

    def turn(pivot, axis, angle):
        return Matrix.Translation(pivot) @ Matrix.Rotation(angle, 4, axis) @ Matrix.Translation(-pivot)

    def signed_angle(before, after, axis):
        q = (after.to_3x3() @ before.to_3x3().inverted()).to_quaternion(); a, ang = q.to_axis_angle()
        return ang if a.dot(axis) >= 0 else -ang

    def moved(a, b):
        return {k for k in b if k in a and any(abs(x-y) > 1e-6 for ra, rb in zip(a[k][0], b[k][0]) for x, y in zip(ra, rb))}

    def require(state, keys, motion, what):
        for k in keys:
            want = motion @ rest[k][0]
            if any(abs(x-y) > 1e-4 for ra, rb in zip(want, state[k][0]) for x, y in zip(ra, rb)):
                raise ValueError(f'{what}: {state[k][1]} does not move as the runtime binding says')

    def pose(j, turned, sync):
        ctrl = bpy.data.objects[rotor_interface.control(j)]
        ctrl['spin_integrated'], ctrl['spin_turned'] = (1.0, float(turned)) if turned else (0.0, 0.0)
        ctrl.update_tag(); bpy.data.objects[f'Rotor_{j}'].update_tag()
        transfer = bpy.data.objects.get(f'TRANSFER_{j}_CTRL')
        if transfer is not None:
            transfer['drum_sync'] = float(sync); transfer.update_tag(); bpy.data.objects[f'Drum_{j}'].update_tag()
    rest = sample(); frames, rotors, drums, plates = {}, {}, {}, {}
    for rot in rotor_interface.rotors(s):
        j = rot['index']; obj = bpy.data.objects[f'Rotor_{j}']; m0 = named(rest, obj.name); pivot, axis = m0.translation, m0.to_3x3().col[0].normalized()
        pose(j, fps, 0.0); spun = sample(); angle = signed_angle(m0, named(spun, obj.name), axis); keys = moved(rest, spun)
        require(spun, keys, turn(pivot, axis, angle), obj.name)
        rotors[obj['component_id']] = {'pivot_runtime_m': runtime_vector(pivot), 'axis_runtime': runtime_vector(axis), 'rad_per_s': round(angle, 9),
                                       'basis': f'Rotor_{j} turned by its driver for one second at full speed in Blender'}
        frames.update({k: obj['component_id'] for k in keys if spun[k][1] != obj.name})
        drum = bpy.data.objects.get(f'Drum_{j}')
        if drum is not None:
            pose(j, fps, 1.0); synced = sample(); d0 = named(rest, drum.name); dpivot, daxis = d0.translation, d0.to_3x3().col[0].normalized()
            dangle = signed_angle(d0, named(synced, drum.name), daxis); keys = moved(spun, synced)
            if abs(dangle-angle) > 1e-6 or (dpivot-pivot).length > 1e-6 or daxis.dot(axis) < 1-1e-9:
                raise ValueError(f'{drum.name}: not coaxial with and synchronized to Rotor_{j}')
            require(synced, keys, turn(dpivot, daxis, dangle), drum.name)
            drums[drum['component_id']] = {'pivot_runtime_m': runtime_vector(dpivot), 'axis_runtime': runtime_vector(daxis), 'rotor': obj['component_id'],
                                           'basis': 'drum_sync 1 turns it with its ring about the same axis (Q46); 0 holds it despun at the index'}
            frames.update({k: drum['component_id'] for k in keys if synced[k][1] != drum.name})
        pose(j, 0, 0.0)
    members = {}

    def bind(name, keys, shut, **extra):
        # A closure's travel from the staged (open) pose to closed: a slide, or a turn about the axis line it keeps fixed (pivot: the point
        # of that line nearest the origin's projection, (w + cot(a/2) axis x w) / 2 for the translation w across the axis), checked on every key.
        k = keys[0]; d = shut[k][0] @ rest[k][0].inverted(); q = d.to_quaternion()
        if q.angle < 1e-9:
            require(shut, keys, Matrix.Translation(d.translation), name)
            out = {'kind': 'slide', 'closed_offset_runtime_m': runtime_vector(d.translation)}
        else:
            axis, a = q.to_axis_angle(); w = d.translation-axis*axis.dot(d.translation)
            pivot = (w+axis.cross(w)/math.tan(a/2))/2
            require(shut, keys, turn(pivot, axis, a), name)
            out = {'kind': 'turn', 'pivot_runtime_m': runtime_vector(pivot), 'axis_runtime': runtime_vector(axis), 'closed_angle_rad': round(a, 9)}
        members.update({key: name for key in keys}); plates[name] = {**out, 'frame': frames.get(k, 'STATIONARY'), **extra}
    if closures:
        # Q46: the spine-port gates, drum doors and tube hatches, closed together by pose_transfer.
        pose_transfer(s, 0.0); shut = sample(); pose_transfer(s, 1.0)
        for j in s['human_entry']['vestibule_rotors']:
            for q in crew_transfer.closures(s, j):
                keys = [k for k in rest if rest[k][1] == q['name'] and k in shut]
                if not keys:
                    raise ValueError(f"{q['name']}: no placement")
                bind(q['name'], keys, shut, function=q['kind'], clear_radius_m=q['clear'], basis='pose_transfer closed (Blender drivers)')
        # The primary port's hinged leaves (DOCK_ENTRY_CTRL), one at a time.
        port = human_entry.ports(s)[0]['name']; control = bpy.data.objects['DOCK_ENTRY_CTRL']
        for which in ('outer', 'inner'):
            control[f'{port}_{which}_open'] = 0.0; control.update_tag(); bpy.data.objects[f'{port}_{which.title()}_Hatch_Hinge'].update_tag()
            shut = sample(); keys = [k for k in moved(rest, shut) if bpy.data.objects[shut[k][1]].type == 'MESH']
            control[f'{port}_{which}_open'] = 1.0; control.update_tag(); bpy.data.objects[f'{port}_{which.title()}_Hatch_Hinge'].update_tag()
            if not keys:
                raise ValueError(f'{port} {which} hatch: nothing moves')
            bind(f'{port}_{which.title()}_Hatch', keys, shut, function=f'DOCK_{which.upper()}_HATCH', basis='DOCK_ENTRY_CTRL closed (Blender driver)')
        # The sector leaves on the induction route have no driver: each slides from its open pose to its seat (human_entry.landing), carried
        # into the vehicle by its sector's placement. The leaf is the Sector_Hatch_Leaf placement nearest to the route's opening.
        L = human_entry.landing(s); local = Vector((0.0, L['leaf_closed'][0]-L['leaf_open'][0], L['z']-L['leaf_open_z']))
        for leg in human_entry.induction_graph(s)['legs']:
            for opening in leg['openings']:
                for name in (n for n in opening['closures'] if n.startswith('Sector_Hatch_Leaf') and n not in plates):
                    k = min((k for k in rest if rest[k][1] == 'Sector_Hatch_Leaf'), key=lambda k: (rest[k][0].translation-Vector(opening['point_m'])).length)
                    d = rest[k][0].to_3x3() @ local
                    shut = {k: (Matrix.Translation(d) @ rest[k][0], rest[k][1])}
                    bind(name, [k], shut, function='SECTOR_LEAF', basis='human_entry.landing leaf_open -> leaf_closed in its sector frame (no Blender driver)')
    sample()
    return frames, rotors, drums, plates, members


def export(root, preset='COAST', out=None, identity=None, draco=False):
    """out/identity default to the Godot package (runtime-export); web_export.py passes its own and draco for the browser copy."""
    s, _, spec_text, source_text = load(root)
    bpy.ops.wm.open_mainfile(filepath=str(root / 'assets/wayfarer' / (s['vehicle']['asset'] + '.blend')))
    # FUT-003: the runtime shows the S004 look ([look]); the saved assets keep their review colours.
    looked = apply_look(s)
    lamps = look.lights(s)
    pose_configuration(s, preset)
    if preset == 'DOCKED':
        # Match entry_preview's open-leaf study, never save this pose back.
        control = bpy.data.objects['DOCK_ENTRY_CTRL']
        port = human_entry.ports(s)[0]
        for which in ('outer', 'inner'):
            control[f"{port['name']}_{which}_open"] = 1.0
        control.update_tag()
        for obj in bpy.data.objects:
            if obj.name.endswith('_Hatch_Hinge'):
                obj.update_tag()
        pose_transfer(s, 1.0)      # Q46: indexed transfer, the despun drums' openings on the tubes with every closure open
        # IND-001 5.2: the induction characters as static proxies, appended in memory from their own asset (never saved into the
        # vehicle); a runtime shows each stop's scenes from the node records.
        name = s['characters']['asset']
        with bpy.data.libraries.load(str(root / 'assets/characters' / f'{name}.blend'), link=False) as (_, dst):
            dst.collections = [name]
        bpy.context.scene.collection.children.link(dst.collections[0])
    # RT-004: the ring and drum each placement turns with (node `frame`), and in DOCKED how each Q46 closure closes.
    frames, rotors, drums, plates, members = mechanism_frames(s, closures=preset == 'DOCKED')
    bpy.context.scene.frame_set(1)
    deps = bpy.context.evaluated_depsgraph_get()
    mechanisms = rotor_bindings(deps, bpy.context.scene.render.fps) if preset == 'COAST' else {}
    staged, excluded, materials = [], Counter(), {}
    seen = set()
    low, high = Vector((float('inf'),) * 3), Vector((-float('inf'),) * 3)
    timeline = json.loads((root / 'simulations' / TIMELINE).read_text()) if preset == 'COAST' else None
    # RT-003: objects whose visibility, alpha or scale a timeline channel or a named state drives are staged in their own pass below;
    # meshes the Crown's location drivers move carry offsets per state from the static pass.
    states = display_states(s) if timeline else {}
    displays = display_tracks(timeline, states) if timeline else {}
    offsets = offset_states(states) if timeline else {}
    if timeline:
        pose_configuration(s, preset)
        bpy.context.scene.frame_set(1)
        deps = bpy.context.evaluated_depsgraph_get()

    shared, reused = {}, [0]

    def stage(instance, deps, display=None):
        obj = instance.object
        if obj.type not in {'MESH', 'CURVE'}:
            return
        kind = obj.get('kind', '')
        if obj.original in displays and display is None:
            excluded['timeline_display'] += 1
            return
        # Hand-authored detail adopted into a detail asset (wf_adopted, docs/MODULES.md) exports like generated detail.
        if ((obj.get('wf_owner') != OWNER and not obj.get('wf_adopted')) or (kind in EXCLUDED and display is None) or obj.hide_render
                or (instance.parent and instance.parent.hide_render)):
            excluded[kind or 'unowned'] += 1
            return
        if obj.original.library and 'DEBUG_' in obj.original.library.filepath:
            excluded['debug_library'] += 1
            return
        if display is None and dupli_key(instance) in offsets:
            display = {'object': obj.original.name, 'staged_state': preset, 'static_opacity': 1.0,
                       'states': {n: dict(v) for n, v in offsets[dupli_key(instance)].items()}}
        matrix = instance.matrix_world.copy()
        owner = instance.parent.name if instance.parent else ('Characters' if obj.get('layer') == 'CHARACTER' else 'Vehicle')
        placement = [round(v, 8) for row in matrix for v in row]
        # Blender 5.2 exposes a bevelled curve both as CURVE and as its generated
        # MESH instance. They share the original object and placement: export once.
        instance_key = (obj.original.as_pointer(), owner, tuple(placement))
        if instance_key in seen:
            excluded['duplicate_evaluated_geometry'] += 1
            return
        seen.add(instance_key)
        mesh = bpy.data.meshes.new_from_object(obj, depsgraph=deps)
        if not mesh.polygons:
            bpy.data.meshes.remove(mesh)
            return
        # The evaluated parent is the outer collection instancer; keep that group.
        lineage = [owner]
        ancestor = obj.original.parent
        while ancestor:
            lineage.append(ancestor.get('component_id', ancestor.name))
            ancestor = ancestor.parent
        ident = '/'.join([*lineage, obj.get('component_id', obj.name), obj.original.name])
        uid = hashlib.sha256(json.dumps([ident, placement]).encode()).hexdigest()[:16]
        name = 'WF_' + uid
        source_mats = [slot.material for slot in obj.material_slots]
        # FUT-003: an emitting surface of a light class carries its runtime point light: the class and the area-weighted centre of
        # its emitting faces in the node's frame (runtime axes). The runtime places and culls the lights; no lighting design or power.
        emitter = next(((k, lamps[m.name[7:]]) for k, m in enumerate(source_mats) if m and m.name[7:] in lamps), None)
        light = None
        if emitter:
            faces = [p for p in mesh.polygons if p.material_index == emitter[0]]
            area = sum(p.area for p in faces)
            if area > 0:
                centre = sum((p.center * p.area for p in faces), Vector()) / area
                q = emitter[1]
                light = {'class': q['cls'], 'kelvin': q['kelvin'], 'color': list(q['color']), 'energy': q['energy'], 'range_m': q['range_m'],
                         'offset_m': q['offset_m'], 'centre_local_runtime_m': runtime_vector(centre)}
        mesh.materials.clear()
        for mat in source_mats:
            mesh.materials.append(surface(mat, obj.color[3], materials))
        # RT-005: placements whose evaluated meshes are equal (positions, faces, corner normals, UVs, per-face materials and the
        # runtime materials themselves) share one mesh, so the GLB stores it once; each placement keeps its node, transform and record.
        key = mesh_signature(mesh) if os.environ.get('WF_EXPORT_SHARE_MESHES', '1') != '0' else name     # '0': no sharing (RT-005 A/B only)
        if key in shared:
            bpy.data.meshes.remove(mesh); mesh = shared[key]; reused[0] += 1
        else:
            shared[key] = mesh
        for v in mesh.vertices:
            p = matrix @ v.co
            q = Vector((p.x, p.z, -p.y))
            for axis in range(3):
                low[axis] = min(low[axis], q[axis]); high[axis] = max(high[axis], q[axis])
        staged.append((mesh, matrix, name, owner, {
            'node': name, 'component_id': obj.get('component_id', obj.name),
            'source_name': obj.name, 'lineage': lineage, 'kind': kind,
            'source_ref': obj.get('source_ref', 'prototype'),
            'canon_status': obj.get('canon_status', 'PROTOTYPE'),
            'geometry_status': obj.get('geometry_status', 'PROTOTYPE'),
            # Geometry-detail class (docs/MODULES.md), orthogonal to maturity and canon status; production detail names its pack.
            'detail_class': representation.detail_class({'detail_class': obj.get('detail_class'), 'layer': obj.get('layer'), 'kind': kind}),
            **({'pack': obj['detail_pack']} if 'detail_pack' in obj else {}),
            **({'layer': 'CHARACTER', 'scene': obj.get('scene', '')} if obj.get('layer') == 'CHARACTER' else {}),
            # M7 (manifest v2): the presentation layer, representation, assembly and maturity of production-layer nodes.
            **({'layer': 'PRODUCTION', 'representation': obj.get('representation', 'REP_HERO'), 'assembly': obj.get('m7_assembly', ''),
                'maturity': obj.get('maturity', ''), 'surface_class': obj.get('surface_class', ''),
                **({'detail_range_m': float(obj['detail_range_m'])} if 'detail_range_m' in obj else {})} if obj.get('layer') == 'PRODUCTION' else {}),
            **({'frame': frames[dupli_key(instance)]} if dupli_key(instance) in frames else {}),
            **({'closure': members[dupli_key(instance)]} if dupli_key(instance) in members else {}),
            **({'display': display} if display else {}),
            **({'light': light} if light else {}),
        }))

    for instance in deps.object_instances:
        stage(instance, deps)
    # Each display object is staged once, posed at a timeline frame where it shows at its fullest; its tracks are relative to that pose.
    by_frame = {}
    for obj, track in displays.items():
        by_frame.setdefault(track.get('staged_frame', track.get('staged_state')), []).append(obj)
    for frame in sorted(by_frame, key=str):
        if frame in states:
            pose_state(states[frame])
        else:
            pose_timeline(s, timeline_controls(timeline, frame))
        bpy.context.scene.frame_set(1)
        deps = bpy.context.evaluated_depsgraph_get()
        before = len(staged)
        for instance in deps.object_instances:
            if instance.object.original in by_frame[frame]:
                stage(instance, deps, displays[instance.object.original])
        if len(staged) == before:
            raise ValueError(f'No display object staged at frame {frame}: {[o.name for o in by_frame[frame]]}')
    if not staged or len({r[2] for r in staged}) != len(staged):
        raise ValueError('Empty export or duplicate snapshot node IDs')
    scene = bpy.data.scenes.new('RuntimeExport')
    bpy.context.window.scene = scene
    groups, records = {}, []
    for mesh, matrix, name, owner, record in sorted(staged, key=lambda r: r[2]):
        if owner not in groups:
            group = bpy.data.objects.new(owner, None)
            scene.collection.objects.link(group)
            groups[owner] = group
        obj = bpy.data.objects.new(name, mesh)
        scene.collection.objects.link(obj)
        obj.parent = groups[owner]
        obj.matrix_world = matrix
        obj['wf_runtime_id'] = name
        records.append(record)
    out = Path(out) if out else root / 'godot/generated'
    out.mkdir(parents=True, exist_ok=True)
    filename = 'wayfarer.glb' if preset == 'COAST' else 'wayfarer_docked.glb'
    bpy.ops.export_scene.gltf(filepath=str(out / filename), export_format='GLB',
        use_active_scene=True, export_animations=False, export_extras=True,
        export_cameras=False, export_lights=False, export_yup=True,
        export_draco_mesh_compression_enable=draco)
    sim_rig.write(root, out / 'wf_sim_rig.json')
    rig = json.loads((out / 'wf_sim_rig.json').read_text())
    packaged = [filename, 'wf_sim_rig.json']
    if preset == 'COAST':
        # RT-003: the runtime plays the First Ignition timeline from this copy, checked against the rig's hash.
        timeline = root / rig['flight_timeline']['file']
        if digest(timeline.read_text()) != rig['flight_timeline']['sha256']:
            raise ValueError('The First Ignition timeline does not match the rig; rebuild')
        (out / TIMELINE).write_bytes(timeline.read_bytes())
        packaged.append(TIMELINE)
        # PHYS-001 phase 9: the imported NAV-001 route (26 C-001..C-011) for the rebased flight playback, the copy the rig names.
        route = root / rig['flight_timeline']['route']['file']
        if route.exists():
            if json.loads(route.read_text())['route_version'] != rig['flight_timeline']['route']['route_version']:
                raise ValueError('The imported route does not match the rig; rerun route-import')
            (out / route.name).write_bytes(route.read_bytes())
            packaged.append(route.name)
    triangles = sum(len(poly.vertices) - 2 for mesh, *_ in staged for poly in mesh.polygons)
    manifest = {'contract': 'WF_RUNTIME_EXPORT', 'contract_version': 2,
        'representation': 'REP_PROXY', 'preset': preset, 'frame': 1, 'static': True,
        'spec_hash': digest(spec_text), 'source_map_hash': digest(source_text),
        'blender': bpy.app.version_string,
        'coordinates': {'unit': 'm', 'from_blender': '(x,z,-y)', 'bow': '+X', 'dorsal': '+Y'},
        'bounds_runtime_m': {'min': list(low), 'max': list(high), 'size': list(high-low)},
        'triangles': triangles, 'groups': sorted(groups), 'excluded': dict(excluded),
        'nodes': records, 'identity': json.loads(Path(identity or root / 'build_identity.json').read_text()),
        'production': dict(production_detail.standard(s), nodes=sum(r.get('layer') == 'PRODUCTION' for r in records)),
        'look': {'name': 'S004', 'status': s['look']['status'], 'source_ref': s['look']['evidence_ref'], 'materials': dict(sorted(looked.items())),
                 'lights': sum('light' in r for r in records),
                 'rule': 'FUT-003 presentation layer: materials carry the [look] surface classes; node records with `light` are emitting '
                         'surfaces with their light class (colour, energy, range) and emitter centre in the node frame. Not a lighting '
                         'design, power or heat allocation.',
                 # FUT-003 step 2 in the runtime: the flight timeline's First Ignition look (hero_preview.dress), applied at run time.
                 'exterior': dict(look.runtime_exterior(s, radiator_health.configuration_state(s, 'FIRST_IGNITION')['thermal_state']),
                     grammar=look.runtime_grammar(s),
                     rule='One hard sun from sun_runtime (ship to sun), black sky, every material proxy grey; the hot_face materials emit '
                          'hot_color x hot_energy while radiator.thermal_state equals hot_thermal_state (other steps: temperature OPEN, '
                          'not lit); display_emitters keep their material; hidden_kinds and hidden_prefixes (source_name) are not drawn. '
                          'Exposure is a linear factor. Presentation only.')},
        'files': {name: hashlib.sha256((out / name).read_bytes()).hexdigest()
                  for name in packaged}}
    if preset == 'COAST':
        manifest['timeline'] = {'file': TIMELINE, 'schema': rig['flight_timeline']['schema'], 'sha256': rig['flight_timeline']['sha256'],
            'mechanisms': mechanisms,
            'displays': {'nodes': sum('display' in r for r in records), 'objects': len(displays),
                         'moving_nodes': sum('offset' in next(iter(r['display']['states'].values()), {}) for r in records if 'display' in r),
                         'kinds': sorted({r['kind'] for r in records if 'display' in r}),
                         'rule': 'Node records with `display` carry values baked from their Blender drivers: `opacity` (0 hidden) and '
                                 'runtime-local `scale_*` tracks over the timeline, and per named state the same values or an `offset` '
                                 '(runtime metres), relative to the staged pose; static_opacity is the export pose.'},
            'states': {name: {k: v for k, v in state.items()} for name, state in states.items()},
            'limits': 'The rings turn and the display objects show, fade, scale and move as their drivers do; colours and emission are the '
                      'static materials of the staged pose, faded by opacity. A named state holds the timeline-free poses (Crown, '
                      'damage, cell health) and each configuration; the timeline itself keeps them at COAST.'}
    if preset == 'DOCKED':
        # RT-004: a static character proxy turns with the frame of the route zone nearest to it (a crew member in a sector rides the ring).
        route = rig['induction_route']; zone_frame = route['frames']
        for mesh, matrix, name, owner, record in staged:
            if record.get('layer') == 'CHARACTER':
                c = matrix @ (sum((v.co for v in mesh.vertices), Vector()) / len(mesh.vertices))
                near = min(route['rail'], key=lambda w: (Vector(w['position_m'])-c).length)
                f = zone_frame['zones'][near['zone']]
                if f != 'STATIONARY':
                    record['frame'] = zone_frame[f]
        # IND-001 5.1: the runtime reads the route graph from the rig (wf_sim_rig.json `induction_route`) and computes nothing.
        manifest['induction'] = {
            'route': 'wf_sim_rig.json induction_route', 'hatch_display': 'OPEN: entry_preview display pose, not an airlock procedure',
            'characters': {'group': 'Characters', 'nodes': sum(r.get('layer') == 'CHARACTER' for r in records),
                           'shown': 'per stop, the nodes whose scene is one of the stop scenes; static proxies (IND-001 3.3)'},
            'mechanisms': {'rotors': rotors, 'drums': drums, 'closures': plates,
                           'rule': 'Node records with `frame` turn with that ring or drum about its pivot and axis (runtime metres); every other node is '
                                   'stationary. The snapshot is at the index angle with every closure open; the nodes with `closure` close by its slide '
                                   'offset or its turn about its pivot and axis (runtime metres, in the index pose), checked against Blender poses at '
                                   'export (the sector leaves against human_entry.landing). rad_per_s is the ring at full speed.'},
            'limits': 'Camera rail and route envelope only. No body collision, gravity or pressure cycling; the closures and the drum sync run as a '
                      'display sequence, not a procedure or an interlock design.'}
    manifest_name = 'manifest.json' if preset == 'COAST' else 'manifest_docked.json'
    (out / manifest_name).write_text(json.dumps(manifest, indent=2) + '\n')
    print('WF_RUNTIME_EXPORT', len(records), 'meshes;', triangles, 'triangles;', len(records)-reused[0], 'distinct meshes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--preset', choices=['COAST', 'DOCKED'], default='COAST')
    parser.add_argument('--out', type=Path, help='package directory (default <root>/godot/generated)')
    parser.add_argument('--identity', type=Path, help='build identity JSON (default <root>/build_identity.json)')
    parser.add_argument('--draco', action='store_true', help='Draco mesh compression (browser copy only; Godot reads the plain GLB)')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    export(args.root.resolve(), args.preset, args.out, args.identity, args.draco)
