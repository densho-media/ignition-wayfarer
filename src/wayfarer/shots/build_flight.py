"""FUT-006: the animated First Ignition flight file, shots/SH_FIRST_IGNITION_FLIGHT.blend, generated from the flight timeline.

The shot links the saved vehicle (relative path) through a fully editable library-override hierarchy, nested subsystem instances
included, and keys the overridden controls (both ROTOR_n_MECH_CTRL, DRIVE_MANIFOLD_CTRL, FORWARD_DEFENSE_CTRL, RADIATOR_HEALTH_CTRL) from
simulations/wf_first_ignition_timeline.json, so the vehicle's own drivers pose it: the rings turn by the integrated spin_turned and never
reverse (FUT-007). Camera, lights, world and the labels are shot-local; a phase caption per phase is shown only in its phase, and a
geometry-nodes readout prints the keyed kinematics. The vehicle assets are only read (their hashes are checked before and after).
Like the other shots, a rebuild replaces the file wholesale and refuses a file that is not this generated shot.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/shots')]
import spec
import flight_timeline as ft
import shot_tools

NAME = 'SH_FIRST_IGNITION_FLIGHT'
OWNER = shot_tools.OWNER
READOUT = ('kinematics.burn_elapsed_s', 'kinematics.acceleration_g', 'kinematics.speed_c', 'kinematics.distance_AU')


def owned(idblock):
    idblock['wf_owner'] = OWNER
    return idblock


def asset_hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'assets/wayfarer').rglob('*.blend'))}


def link_vehicle(root, s, scene, path):
    """Link the vehicle collection relative to the shot file and override it, with every nested subsystem instance, as fully editable."""
    lib = Path('//')/Path(*['..']*(len(path.parent.relative_to(root).parts)))/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')
    with bpy.data.libraries.load(str(root/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')), link=True, relative=True) as (_, dst):
        dst.collections = [s['vehicle']['asset']]
    linked = dst.collections[0]
    reference = bpy.data.objects.new('WF_VEHICLE_LINK', None); reference.instance_type = 'COLLECTION'; reference.instance_collection = linked
    scene.collection.objects.link(reference)
    vehicle = linked.override_hierarchy_create(scene, bpy.context.view_layer, reference=reference, do_fully_editable=True)
    # Nested Assembly_* instances: override each instanced subsystem and point the overridden instance at it, so the override survives a reload.
    for inst in [o for o in vehicle.all_objects if o.instance_type == 'COLLECTION' and o.instance_collection and o.instance_collection.library]:
        sub = inst.instance_collection.override_hierarchy_create(scene, bpy.context.view_layer, reference=inst, do_fully_editable=True)
        inst.instance_collection = sub
        if sub.name in scene.collection.children:
            scene.collection.children.unlink(sub)
    if reference.name in bpy.data.objects:
        bpy.data.objects.remove(reference)
    return vehicle, lib


def overridden(name):
    return next(o for o in bpy.data.objects if o.name == name and o.override_library and o.library is None)


def key_curves(idblock, slot_name, curves):
    """One shot-owned action on an ID: per data path the timeline keys [frame, value, interp] (interp from that key to the next)."""
    action = owned(bpy.data.actions.new(f'{NAME}_{slot_name}')); slot = action.slots.new(id_type='OBJECT', name=slot_name)
    strip = action.layers.new('Timeline').strips.new(type='KEYFRAME'); bag = strip.channelbag(slot, ensure=True)
    for path, keys in curves.items():
        fc = bag.fcurves.new(data_path=path); fc.keyframe_points.add(len(keys))
        for kp, (frame, value, interp) in zip(fc.keyframe_points, keys):
            kp.co = (frame, value); kp.interpolation = interp
        fc.extrapolation = 'CONSTANT'; fc.update()
    idblock.animation_data_create(); idblock.animation_data.action = action; idblock.animation_data.action_slot = slot
    return action


def label_materials():
    text = owned(bpy.data.materials.new('SHOT_FLIGHT_LABEL'))
    node = text.node_tree.nodes['Principled BSDF']; node.inputs['Base Color'].default_value = (0, 0, 0, 1)
    node.inputs['Emission Color'].default_value = (.80, .92, 1, 1); node.inputs['Emission Strength'].default_value = 1.5
    plate = owned(bpy.data.materials.new('SHOT_FLIGHT_PLATE'))
    node = plate.node_tree.nodes['Principled BSDF']; node.inputs['Base Color'].default_value = (.008, .01, .016, 1); node.inputs['Roughness'].default_value = 1
    return text, plate


def text(scene, camera, name, body, at, size, mat):
    data = owned(bpy.data.curves.new(name, 'FONT')); data.body = body; data.size = size; data.materials.append(mat)
    obj = owned(bpy.data.objects.new(name, data)); scene.collection.objects.link(obj); obj.parent = camera; obj.location = at
    obj.visible_shadow = False
    return obj


def readout_tree():
    """Geometry nodes that print 'burn time .. d | a .. g | v .. c | x .. AU' from four keyed float inputs (no Python at render time)."""
    nt = owned(bpy.data.node_groups.new('SHOT_FLIGHT_READOUT', 'GeometryNodeTree'))
    nt.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    size = nt.interface.new_socket('Size', in_out='INPUT', socket_type='NodeSocketFloat')
    values = [nt.interface.new_socket(n, in_out='INPUT', socket_type='NodeSocketFloat') for n in ('Burn days', 'Acceleration g', 'Speed c', 'Distance AU')]
    material = nt.interface.new_socket('Material', in_out='INPUT', socket_type='NodeSocketMaterial')
    gi = nt.nodes.new('NodeGroupInput'); go = nt.nodes.new('NodeGroupOutput')
    join = nt.nodes.new('GeometryNodeStringJoin')
    parts = []
    for n, (prefix, decimals, unit) in enumerate((('burn time ', 4, ' d'), ('  |  a ', 3, ' g'), ('  |  v ', 5, ' c'), ('  |  x ', 4, ' AU'))):
        lead = nt.nodes.new('FunctionNodeInputString'); lead.string = prefix
        conv = nt.nodes.new('FunctionNodeValueToString'); conv.inputs['Decimals'].default_value = decimals
        nt.links.new(gi.outputs[values[n].identifier], conv.inputs['Value'])
        tail = nt.nodes.new('FunctionNodeInputString'); tail.string = unit
        parts += [lead.outputs[0], conv.outputs[0], tail.outputs[0]]
    for socket in reversed(parts):        # the multi-input joins in reverse link order
        nt.links.new(socket, join.inputs['Strings'])
    curves = nt.nodes.new('GeometryNodeStringToCurves'); nt.links.new(join.outputs[0], curves.inputs['String'])
    nt.links.new(gi.outputs[size.identifier], curves.inputs['Size'])
    realize = nt.nodes.new('GeometryNodeRealizeInstances'); nt.links.new(curves.outputs['Curve Instances'], realize.inputs[0])
    fill = nt.nodes.new('GeometryNodeFillCurve'); nt.links.new(realize.outputs[0], fill.inputs['Curve'])
    setmat = nt.nodes.new('GeometryNodeSetMaterial'); nt.links.new(fill.outputs[0], setmat.inputs['Geometry'])
    nt.links.new(gi.outputs[material.identifier], setmat.inputs['Material']); nt.links.new(setmat.outputs[0], go.inputs[0])
    return nt, [v.identifier for v in values], size.identifier, material.identifier


def build(root=ROOT, size=768):
    s, _, spec_text, source_text = spec.load(root)
    if not ft.check(root):
        raise RuntimeError('simulations/wf_first_ignition_timeline.json is stale: rebuild it first (flight_timeline.py)')
    tl = json.loads((root/ft.table(s)['output']).read_text())
    path = root/'shots'/f'{NAME}.blend'
    if path.exists():
        bpy.ops.wm.open_mainfile(filepath=str(path))
        if bpy.context.scene.get('wf_shot') != NAME or bpy.context.scene.get('wf_owner') != OWNER:
            raise RuntimeError(f'{path} is not a generated {NAME} shot; refusing to replace it')
    before = asset_hashes(root)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene; scene.name = NAME
    scene['wf_shot'] = NAME; scene['wf_owner'] = OWNER; scene['timeline_sha256'] = hashlib.sha256((root/ft.table(s)['output']).read_bytes()).hexdigest()
    scene['description'] = 'First Ignition flight (FUT-006): the induction, then the burn, keyed from the flight timeline; PROTOTYPE phase order, unscaled phases not to scale.'
    scene.render.fps = tl['fps']; scene.frame_start, scene.frame_end = tl['frame_range']
    vehicle, lib = link_vehicle(root, s, scene, path)
    # Controls: each bound channel keyed on its overridden control.
    per_control = {}
    for name, c in tl['channels'].items():
        if c['binding']:
            for control in c['binding']['controls']:
                per_control.setdefault(control, {})[f'["{c["binding"]["property"]}"]'] = c['keys']
    for control, curves in per_control.items():
        key_curves(overridden(control), control, curves)
    for n, (m, mark) in enumerate(tl['marks'].items()):
        scene.timeline_markers.new(m, frame=int(mark['frame']))
    # World, lights and camera (shot-local), framed on the whole ship from three-quarter aft-high.
    world = owned(bpy.data.worlds.new('SHOT_World')); scene.world = world; world.use_nodes = True
    bg = world.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (.03, .04, .055, 1); bg.inputs['Strength'].default_value = .6
    for i, (loc, energy) in enumerate([((70, -100, 180), 2.5), ((-90, 60, 100), 1.8), ((20, 100, -100), 1.0)]):
        light = owned(bpy.data.lights.new(f'SHOT_Sun_{i}', 'SUN')); light.energy = energy; light.angle = .15
        obj = owned(bpy.data.objects.new(light.name, light)); scene.collection.objects.link(obj); obj.location = loc
        obj.rotation_euler = (-obj.location).to_track_quat('-Z', 'Y').to_euler()
    cam = owned(bpy.data.cameras.new('SHOT_Camera')); cam.lens = 50; cam.clip_start = .1; cam.clip_end = 3000; cam.sensor_fit = 'HORIZONTAL'
    camera = owned(bpy.data.objects.new('SHOT_Camera', cam)); scene.collection.objects.link(camera); scene.camera = camera
    # Fit the whole ship (evaluated bounds at frame 1) into the lower three quarters of the frame, under the label plate.
    scene.frame_set(scene.frame_start); points = []
    for item in bpy.context.evaluated_depsgraph_get().object_instances:
        if item.object.type in {'MESH', 'CURVE'} and not item.object.name.startswith('SHOT_'):
            points += [item.matrix_world@Vector(c) for c in item.object.bound_box]
    low = Vector([min(q[i] for q in points) for i in range(3)]); high = Vector([max(q[i] for q in points) for i in range(3)])
    direction = Vector((-.55, -1.2, .7)).normalized(); quat = (-direction).to_track_quat('-Z', 'Y'); centre = (low+high)/2
    local = [quat.inverted()@(c-centre) for c in [Vector((x, y, z)) for x in (low.x, high.x) for y in (low.y, high.y) for z in (low.z, high.z)]]
    half_w = max(abs(q.x) for q in local); half_h = max(abs(q.y) for q in local); tan_w = math.tan(cam.angle_x/2)
    distance = max(half_w/(tan_w*.92), half_h/(tan_w*.75*.70))+max(q.z for q in local)
    camera.location = centre+direction*distance+quat@Vector((0, distance*tan_w*.75*.22, 0)); camera.rotation_euler = quat.to_euler()
    # Labels in front of the camera: a title, one caption per phase shown only in its phase, the kinematics readout, and notes.
    depth = 1.0; width = 2*depth*math.tan(cam.angle_x/2); height = width*.75; text_mat, plate_mat = label_materials()
    rows = lambda i: (-width*.47, height*(.44-i*.045), -depth)
    text(scene, camera, 'SHOT_Label_Title', 'WAYFARER 001 / FIRST IGNITION TIMELINE (FUT-006) / classes SOURCED > DERIVED > PRESENTATION', rows(0), width*.019, text_mat)
    for p in tl['phases']:
        where = p.get('configuration') or f"{p['from']} -> {p['to']}"
        label = text(scene, camera, f"SHOT_Label_Phase_{p['id']}", f"{p['id']}: {p['title']}\n{where} | {p['label']} | phase order PROTOTYPE", rows(1), width*.0135, text_mat)
        start, end = tl['frame_range']      # hidden (1) outside its phase; a boundary frame shows the phase that starts there
        keys = ([[start, 1.0, 'CONSTANT']] if p['frame_start'] > start else [])+[[p['frame_start'], 0.0, 'CONSTANT']]+([[p['frame_end'], 1.0, 'CONSTANT']] if p['frame_end'] < end else [])
        key_curves(label, label.name, {'hide_render': keys, 'hide_viewport': keys})
    readout = owned(bpy.data.objects.new('SHOT_Label_Readout', owned(bpy.data.meshes.new('SHOT_Label_Readout')))); scene.collection.objects.link(readout)
    readout.parent = camera; readout.location = rows(3); readout.visible_shadow = False
    tree, inputs, size_id, mat_id = readout_tree(); mod = readout.modifiers.new('Readout', 'NODES'); mod.node_group = tree
    getattr(mod.properties.inputs, size_id).value = width*.0135; getattr(mod.properties.inputs, mat_id).value = text_mat   # Blender 5 modifier inputs
    scale = {'kinematics.burn_elapsed_s': 1/86400}
    key_curves(readout, readout.name, {f'modifiers["Readout"].properties.inputs.{i}.value': [[f, v*scale.get(n, 1), interp] for f, v, interp in tl['channels'][n]['keys']] for n, i in zip(READOUT, inputs)})
    after = tl['channels']['kinematics.distance_AU']['lower_bound_after_frame']
    note = text(scene, camera, 'SHOT_Label_Note', 'x: DIAGNOSTIC 1D traveled, not heliocentric (23_ROUTE_FRAMES, row per frame) | after the burn a lower bound: coast OPEN | rings: integrated spin', rows(4), width*.012, text_mat)
    plate = owned(bpy.data.meshes.new('SHOT_Label_Plate')); w, h = width, height*.27
    plate.from_pydata([(-w/2, height/2-h, 0), (w/2, height/2-h, 0), (w/2, height/2, 0), (-w/2, height/2, 0)], [], [(0, 1, 2, 3)]); plate.materials.append(plate_mat)
    obj = owned(bpy.data.objects.new('SHOT_Label_Plate', plate)); scene.collection.objects.link(obj); obj.parent = camera; obj.location = (0, 0, -depth-.01); obj.visible_shadow = False
    scene['distance_lower_bound_after_frame'] = after
    shot_tools.render_settings(scene, 'REP_PROXY', size)
    scene.frame_set(scene.frame_start)
    local = [d.name for d in [*bpy.data.meshes, *bpy.data.curves] if d.library is None and not d.override_library and d.get('wf_owner') != OWNER]
    if local:
        raise RuntimeError(f'Local geometry would make the shot own source data: {local[:5]}')
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path), relative_remap=True, compress=True)
    if asset_hashes(root) != before:
        raise RuntimeError('Building the shot changed a vehicle asset')
    print(f'WF_SHOT {NAME} {len(per_control)} controls keyed, {len(tl["phases"])} phases, frames {tl["frame_range"]} -> {path.relative_to(root)} (library {lib})', flush=True)
    return path


def render(root=ROOT, frames=None, size=512, out_dir=None):
    bpy.ops.wm.open_mainfile(filepath=str(root/'shots'/f'{NAME}.blend'))
    scene = bpy.context.scene; shot_tools.render_settings(scene, 'REP_PROXY', size)
    out = out_dir or root/'renders/shots'/NAME; out.mkdir(parents=True, exist_ok=True)
    for frame in frames or [m.frame for m in sorted(scene.timeline_markers, key=lambda m: m.frame)]:
        scene.frame_set(frame); scene.render.filepath = str(out/f'{NAME}_f{frame:04}.png')
        bpy.ops.render.render(write_still=True)
        print(f'WF_SHOT_RENDER {NAME} {frame}', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--root', type=Path, default=ROOT); p.add_argument('--render', action='store_true')
    p.add_argument('--render-only', action='store_true'); p.add_argument('--frames', nargs='+', type=int); p.add_argument('--size', type=int, default=512)
    p.add_argument('--out-dir', type=Path)
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    root = a.root.resolve()
    if not a.render_only:
        build(root, a.size)
    if a.render or a.render_only:
        render(root, a.frames, a.size, a.out_dir)
