"""NAV-001: the stand-alone navigation stage, shots/SH_NAV_STAGE.blend, from the imported sheet-computed route (26_BLENDER_CONTRACT C-015).

Every number on the stage is a 23_ROUTE_FRAMES / 24_ROUTE_EVENTS value as tools/route_import.py imported it ([flight_timeline].route); nothing
here computes a trajectory (NAV-027, C-001). Frame n is route row n at the route's 30 fps (C-003, C-010), keyed LINEAR. Metres become display
units through one named, reversible transform (NAV_DISPLAY_GM: x_display = x_m / 1e9, C-004), recorded on the scene and on NAV_DisplayTransform.
Two scenes share the track: ANALYTICAL shows the true relative 1D geometry with a symbolic position marker; PRESENTATION adds the vehicle,
linked one way and labelled as enlarged, riding the marker (C-012). Events with a numeric epoch are ticks at the owner's displacement; OPEN
events are listed, never placed (C-008). No Sun, planets or ephemerides: the frame and ephemerides are OPEN (25!F14:F15, C-007). A permanent
legend says the track is traveled displacement, not heliocentric (NAV-030). The vehicle assets are only read; a rebuild replaces the file
wholesale and refuses a file that is not this generated stage.
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
from build_flight import owned, text, label_materials, asset_hashes

NAME = 'SH_NAV_STAGE'
OWNER = shot_tools.OWNER
DISPLAY = {'name': 'NAV_DISPLAY_GM', 'metres_per_unit': 1e9, 'axis': '+X local (22!B21)',
           'forward': 'x_display = x_m / metres_per_unit', 'inverse': 'x_m = x_display * metres_per_unit',
           'status': 'PRESENTATION: display only, never fed back as physics (C-004)'}
SHIP_ENLARGEMENT = 0.1           # PRESENTATION scene: display units per vehicle metre (the 237 m ship shows ~24 units long)
SCENES = ('ANALYTICAL', 'PRESENTATION')
# Readout: (prefix, decimals, unit, 23_ROUTE_FRAMES column); the frame number comes from the scene time.
READOUT = (('mission t ', 1, ' s', 'mission_t_s'), (' (', 4, ' d)', 'mission_t_days'), ('  |  a ', 4, ' g', 'accel_g'),
           ('  |  v ', 1, ' m/s', 'vx_mps'), (' = ', 6, ' c', 'speed_fraction_c'), ('  |  x ', 4, ' AU traveled', 'distance_traveled_AU'))


def route(root, s):
    r = json.loads((root/ft.table(s)['route']).read_text())
    gate = [v for v in r['validation'] if 2 <= v['row'] <= 13]
    if r['schema'] != 'WF_ROUTE_IMPORT' or len(gate) != 12 or any(v['result'] != 'PASS' for v in gate):
        raise RuntimeError('the imported route is not released: 25_ROUTE_VALIDATION rows 2:13 must all PASS (C-009)')
    return r


def key(idblock, slot_name, curves):
    """One stage-owned action on an ID: per data path the keys [frame, value] (LINEAR between route rows)."""
    action = owned(bpy.data.actions.new(f'{NAME}_{slot_name}')); slot = action.slots.new(id_type='OBJECT', name=slot_name)
    bag = action.layers.new('Route').strips.new(type='KEYFRAME').channelbag(slot, ensure=True)
    for (path, index), keys in curves.items():
        fc = bag.fcurves.new(data_path=path, index=index); fc.keyframe_points.add(len(keys))
        for kp, (frame, value) in zip(fc.keyframe_points, keys):
            kp.co = (frame, value); kp.interpolation = 'LINEAR'
        fc.extrapolation = 'CONSTANT'; fc.update()
    idblock.animation_data_create(); idblock.animation_data.action = action; idblock.animation_data.action_slot = slot


def emissive(name, colour, strength=2.0):
    mat = owned(bpy.data.materials.new(name)); node = mat.node_tree.nodes['Principled BSDF']
    node.inputs['Base Color'].default_value = (0, 0, 0, 1); node.inputs['Emission Color'].default_value = (*colour, 1)
    node.inputs['Emission Strength'].default_value = strength
    return mat


def readout_tree():
    """Geometry nodes printing 'frame n / N | mission t .. s (.. d) | a .. g | v .. m/s = .. c | x .. AU traveled' from keyed inputs."""
    nt = owned(bpy.data.node_groups.new('NAV_READOUT', 'GeometryNodeTree'))
    nt.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    size = nt.interface.new_socket('Size', in_out='INPUT', socket_type='NodeSocketFloat')
    values = [nt.interface.new_socket(col, in_out='INPUT', socket_type='NodeSocketFloat') for *_, col in READOUT]
    material = nt.interface.new_socket('Material', in_out='INPUT', socket_type='NodeSocketMaterial')
    gi = nt.nodes.new('NodeGroupInput'); go = nt.nodes.new('NodeGroupOutput'); join = nt.nodes.new('GeometryNodeStringJoin')
    lead = nt.nodes.new('FunctionNodeInputString'); lead.string = 'frame '
    frame = nt.nodes.new('FunctionNodeValueToString'); frame.inputs['Decimals'].default_value = 0
    nt.links.new(nt.nodes.new('GeometryNodeInputSceneTime').outputs['Frame'], frame.inputs['Value'])
    parts = [lead.outputs[0], frame.outputs[0]]
    for n, (prefix, decimals, unit, _) in enumerate(READOUT):
        a = nt.nodes.new('FunctionNodeInputString'); a.string = ('  =  route row  |  ' if n == 0 else '')+prefix
        conv = nt.nodes.new('FunctionNodeValueToString'); conv.inputs['Decimals'].default_value = decimals
        nt.links.new(gi.outputs[values[n].identifier], conv.inputs['Value'])
        b = nt.nodes.new('FunctionNodeInputString'); b.string = unit
        parts += [a.outputs[0], conv.outputs[0], b.outputs[0]]
    for socket in reversed(parts):        # the multi-input joins in reverse link order
        nt.links.new(socket, join.inputs['Strings'])
    curves = nt.nodes.new('GeometryNodeStringToCurves'); nt.links.new(join.outputs[0], curves.inputs['String'])
    nt.links.new(gi.outputs[size.identifier], curves.inputs['Size'])
    realize = nt.nodes.new('GeometryNodeRealizeInstances'); nt.links.new(curves.outputs['Curve Instances'], realize.inputs[0])
    fill = nt.nodes.new('GeometryNodeFillCurve'); nt.links.new(realize.outputs[0], fill.inputs['Curve'])
    setmat = nt.nodes.new('GeometryNodeSetMaterial'); nt.links.new(fill.outputs[0], setmat.inputs['Geometry'])
    nt.links.new(gi.outputs[material.identifier], setmat.inputs['Material']); nt.links.new(setmat.outputs[0], go.inputs[0])
    return nt, [v.identifier for v in values], size.identifier, material.identifier


def collection(name, parent):
    c = owned(bpy.data.collections.new(name)); parent.children.link(c)
    return c


def obj(name, data, coll):
    o = owned(bpy.data.objects.new(name, data)); coll.objects.link(o)
    return o


def polyline(name, points, depth, mat, coll):
    cu = owned(bpy.data.curves.new(name, 'CURVE')); cu.dimensions = '3D'; cu.bevel_depth = depth; cu.bevel_resolution = 2
    sp = cu.splines.new('POLY'); sp.points.add(len(points)-1)
    for p, (x, y, z) in zip(sp.points, points):
        p.co = (x, y, z, 1)
    cu.materials.append(mat)
    return obj(name, cu, coll)


def label(name, body, at, size, mat, coll, align='CENTER'):
    cu = owned(bpy.data.curves.new(name, 'FONT')); cu.body = body; cu.size = size; cu.align_x = align; cu.materials.append(mat)
    o = obj(name, cu, coll); o.location = at; o.rotation_euler = (math.pi/2, 0, 0)     # faces -Y, the analytical camera
    return o


def hud(scene, camera, coll, lines, mat, plate_mat, tree):
    """Camera-parented labels: title, legend, readout and notes (ortho or perspective camera)."""
    cam = camera.data; depth = 1.0
    width = cam.ortho_scale*depth/depth if cam.type == 'ORTHO' else 2*depth*math.tan(cam.angle_x/2)
    height = width*9/16; rows = lambda i: (-width*.47, height*(.44-i*.042), -depth)
    out = []
    for i, (name, body, size) in enumerate(lines):
        o = text(scene, camera, name, body, rows(i), width*size, mat); scene.collection.objects.unlink(o); coll.objects.link(o); out.append(o)
    nt, inputs, size_id, mat_id = tree
    ro = obj(f'NAV_Readout_{scene.name.split("_")[-1]}', owned(bpy.data.meshes.new(f'NAV_Readout_{scene.name}')), coll)
    ro.parent = camera; ro.location = rows(len(lines)); ro.visible_shadow = False
    mod = ro.modifiers.new('Readout', 'NODES'); mod.node_group = nt
    getattr(mod.properties.inputs, size_id).value = width*.0125; getattr(mod.properties.inputs, mat_id).value = mat
    plate = owned(bpy.data.meshes.new(f'NAV_Plate_{scene.name}')); w, h = width, height*(.08+.042*(len(lines)+1))
    plate.from_pydata([(-w/2, height/2-h, 0), (w/2, height/2-h, 0), (w/2, height/2, 0), (-w/2, height/2, 0)], [], [(0, 1, 2, 3)])
    plate.materials.append(plate_mat)
    p = obj(f'NAV_Plate_{scene.name}', plate, coll); p.parent = camera; p.location = (0, 0, -depth-.01); p.visible_shadow = False
    return ro, inputs


def link_vehicle(root, s, path):
    """The vehicle collection, linked one way (map -> ship, never ship -> map) by a path relative to the stage file."""
    lib = Path('//')/Path(*['..']*(len(path.parent.relative_to(root).parts)))/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')
    with bpy.data.libraries.load(str(root/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')), link=True, relative=True) as (_, dst):
        dst.collections = [s['vehicle']['asset']]
    return dst.collections[0], lib


def build(root=ROOT, size=768):
    s, *_ = spec.load(root); r = route(root, s)
    cols = {c: i for i, c in enumerate(r['columns'])}; rows = r['frames']; n_rows = r['frame_count']; mpu = DISPLAY['metres_per_unit']
    path = root/'shots'/f'{NAME}.blend'
    if path.exists():
        bpy.ops.wm.open_mainfile(filepath=str(path))
        if bpy.data.scenes[0].get('wf_shot') != NAME or bpy.data.scenes[0].get('wf_owner') != OWNER:
            raise RuntimeError(f'{path} is not a generated {NAME} stage; refusing to replace it')
    before = asset_hashes(root)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    base = bpy.context.scene; scenes = {}
    for mode in SCENES:
        sc = base if mode == SCENES[0] else bpy.data.scenes.new(f'{NAME}_{mode}')
        sc.name = f'{NAME}_{mode}'; scenes[mode] = sc
        sc['wf_shot'] = NAME; sc['wf_owner'] = OWNER; sc['nav_mode'] = mode
        sc['scenario_id'] = r['scenario_id']; sc['scenario_status'] = r['scenario_status']; sc['route_version'] = r['route_version']
        sc['route_file'] = ft.table(s)['route']; sc['route_sha256'] = hashlib.sha256((root/ft.table(s)['route']).read_bytes()).hexdigest()
        sc['display_transform'] = json.dumps(DISPLAY); sc['metres_per_unit'] = mpu
        sc.render.fps = int(r['fps']); sc.render.fps_base = 1.0; sc.frame_start, sc.frame_end = 1, n_rows
        world = owned(bpy.data.worlds.new(f'NAV_World_{mode}')); sc.world = world; world.use_nodes = True
        bg = world.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (.012, .014, .02, 1); bg.inputs['Strength'].default_value = 1
    shared = owned(bpy.data.collections.new('NAV_TRACK'))
    for sc in scenes.values():
        sc.collection.children.link(shared)
    text_mat, plate_mat = label_materials()
    track_mat = emissive('NAV_TRACK', (.35, .75, 1.0)); tick_mat = emissive('NAV_TICK', (.55, .6, .7), 1.2)
    event_mat = emissive('NAV_EVENT', (1.0, .72, .25)); marker_mat = emissive('NAV_MARKER', (1.0, .3, .2), 4.0)
    # The named, reversible display transform (an empty at the ignition origin carrying its definition).
    xf = obj('NAV_DisplayTransform', None, shared); xf.empty_display_type = 'ARROWS'; xf.empty_display_size = 20
    for k, v in DISPLAY.items():
        xf[k] = v
    # Track: every imported row, in display units (y and z are the sheet's zeros, kept as imported).
    disp = lambda row: (row[cols['local_x_m']]/mpu, row[cols['local_y_m']]/mpu, row[cols['local_z_m']]/mpu)
    track = [disp(row) for row in rows]
    analytical = collection('NAV_ANALYTICAL', scenes['ANALYTICAL'].collection)
    pres = owned(bpy.data.collections.new('NAV_PRESENTATION')); scenes['PRESENTATION'].collection.children.link(pres)
    polyline('NAV_Route_Track', track, 1.2, track_mat, analytical)            # readable across the whole track
    polyline('NAV_Route_Track_Thin', track, .08, track_mat, pres)             # under the enlarged ship
    # Whole-AU ticks along +X: a display reference of traveled displacement, from the sheet's AU_m (22!B7).
    au = r['model']['AU_m']['value']; last_au = rows[-1][cols['distance_traveled_AU']]
    for n in range(0, int(last_au)+1):
        x = n*au/mpu
        polyline(f'NAV_Tick_{n}AU', [(x, 0, -14), (x, 0, 14)], .5, tick_mat, shared)
        label(f'NAV_TickLabel_{n}AU', f'{n} AU', (x, 0, -40), 14, tick_mat, shared)
    # Events: placed only with a numeric displacement (24!D); OPEN events are listed, never placed (C-008).
    placed = [e for e in r['events'] if isinstance(e.get('displacement_x_m'), float)]
    symbolic = [f"{e['event_id']} ({e['physics_status']})" for e in r['events'] if e not in placed]
    for n, e in enumerate(placed):
        # The first and last labels read leftwards from their line and the others rightwards, so neighbours never overlap.
        x = e['displacement_x_m']/mpu; side = -1 if n in (0, len(placed)-1) else 1; top = 70+40*(n % 2)
        polyline(f"NAV_Event_{e['event_id']}", [(x, 0, 0), (x, 0, top)], .6, event_mat, shared)
        label(f"NAV_EventLabel_{e['event_id']}", f"{e['event_id']}\n{e['physics_status']} / {e['story_status']}", (x+4*side, 0, top-8), 11, event_mat,
              shared, 'RIGHT' if side < 0 else 'LEFT')
    placed = [e['event_id'] for e in placed]
    # The position marker, keyed one route row per frame (C-005, C-010); ANALYTICAL shows it as a symbolic sphere.
    marker = obj('NAV_Ship_Marker', None, shared); marker.empty_display_type = 'SPHERE'; marker.empty_display_size = 6
    key(marker, marker.name, {('location', i): [[n+1, disp(row)[i]] for n, row in enumerate(rows)] for i in range(3)})
    bpy.ops.mesh.primitive_uv_sphere_add(radius=6, segments=24, ring_count=12); glyph = bpy.context.active_object
    for c in list(glyph.users_collection):
        c.objects.unlink(glyph)
    analytical.objects.link(glyph); glyph.name = glyph.data.name = 'NAV_Marker_Glyph'; owned(glyph); owned(glyph.data)
    glyph.data.materials.append(marker_mat); glyph.parent = marker
    # PRESENTATION: the vehicle, linked one way and enlarged, riding the marker; labelled as enlarged (C-012).
    vehicle, lib = link_vehicle(root, s, path)
    ship = obj('NAV_Ship_Presentation', None, pres); ship.instance_type = 'COLLECTION'; ship.instance_collection = vehicle
    ship.parent = marker; ship.scale = (SHIP_ENLARGEMENT,)*3; ship['enlargement'] = f'{SHIP_ENLARGEMENT/(1/mpu):.3g}x true scale (PRESENTATION)'
    for i, (loc, energy) in enumerate([((70, -100, 180), 3.0), ((-90, 60, 100), 1.6)]):
        light = owned(bpy.data.lights.new(f'NAV_Sun_{i}', 'SUN')); light.energy = energy
        o = obj(light.name, light, pres); o.rotation_euler = (-Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    # Cameras: ANALYTICAL, orthographic from -Y over the whole track; PRESENTATION, following the marker.
    span = rows[-1][cols['local_x_m']]/mpu
    cam = owned(bpy.data.cameras.new('NAV_Camera_ANALYTICAL')); cam.type = 'ORTHO'; cam.ortho_scale = span*1.36; cam.clip_end = 10000
    ca = obj('NAV_Camera_ANALYTICAL', cam, scenes['ANALYTICAL'].collection); ca.location = (span/2, -3000, span*.12); ca.rotation_euler = (math.pi/2, 0, 0)
    scenes['ANALYTICAL'].camera = ca
    cam = owned(bpy.data.cameras.new('NAV_Camera_PRESENTATION')); cam.lens = 35; cam.clip_end = 20000
    cp = obj('NAV_Camera_PRESENTATION', cam, pres); cp.parent = marker
    direction = Vector((-.9, -1.4, .55)).normalized(); cp.location = direction*70; cp.rotation_euler = (-direction).to_track_quat('-Z', 'Y').to_euler()
    scenes['PRESENTATION'].camera = cp
    # Labels: the permanent legend in both modes (NAV-030), the readout, and the OPEN items.
    tree = readout_tree(); legend = ('DIAGNOSTIC 1D: traveled displacement along local +X from the ignition origin, NOT a Sun or Earth distance (22!A36, NAV-030); '
                                     'no Sun, planets or ephemerides: frame, epoch and ephemerides OPEN (25!F14:F15)')
    common = [('NAV_Label_Legend', 'DIAGNOSTIC 1D: traveled displacement along local +X from the ignition origin, NOT a Sun or Earth distance (22!A36, NAV-030)', .0105),
              ('NAV_Label_Ephemeris', 'No Sun, planets or ephemerides: inertial frame, epoch, heading and ephemerides are OPEN (25!F14:F15, C-007)', .0105),
              ('NAV_Label_Source', f"{r['scenario_id']} / {r['scenario_status']} / route {r['route_version']}: 23_ROUTE_FRAMES, sheet-computed, imported only (NAV-027)", .0105),
              ('NAV_Label_Time', f"{int(r['fps'])} fps, frame n = route row n; mission time advances {rows[1][cols['mission_t_s']]:.3f} s per frame, video time is not story time (C-011)", .0105),
              ('NAV_Label_Display', f"display {DISPLAY['name']}: 1 unit = {mpu:.0e} m ({DISPLAY['forward']}, reversible, C-004)", .0105),
              ('NAV_Label_Open', f"OPEN, not on the route (C-008): {', '.join(symbolic)}", .0105)]
    readouts = {}
    for mode, sc in scenes.items():
        coll = collection(f'NAV_HUD_{mode}', sc.collection)
        title = ('NAV_Label_Title', f"WAYFARER 001 / NAVIGATION STAGE (NAV-001) / {mode}" +
                 (' : true relative 1D geometry, the marker is a symbol' if mode == 'ANALYTICAL' else f" : ship enlarged {ship['enlargement']}, illustrative"), .016)
        lines = [(f'{n}_{mode}', b, z) for n, b, z in [title, *common]]
        ro, inputs = hud(sc, sc.camera, coll, lines, text_mat, plate_mat, tree)
        key(ro, ro.name, {(f'modifiers["Readout"].properties.inputs.{i}.value', 0): [[n+1, row[cols[col]]] for n, row in enumerate(rows)]
                          for i, (*_, col) in zip(inputs, READOUT)})
        readouts[mode] = ro.name
        shot_tools.render_settings(sc, 'REP_PROXY', size)
        sc.render.resolution_x, sc.render.resolution_y = size, size*9//16
    for sc in scenes.values():
        sc['readouts'] = json.dumps(readouts)
    local = [d.name for d in [*bpy.data.meshes, *bpy.data.curves] if d.library is None and not d.override_library and d.get('wf_owner') != OWNER]
    if local:
        raise RuntimeError(f'Local geometry would make the stage own source data: {local[:5]}')
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path), relative_remap=True, compress=True)
    if asset_hashes(root) != before:
        raise RuntimeError('Building the stage changed a vehicle asset')
    print(f'WF_SHOT {NAME} {n_rows} route rows at {int(r["fps"])} fps, scenes {list(scenes)}, events placed {placed} -> {path.relative_to(root)} (library {lib})', flush=True)
    return path


def render(root=ROOT, frames=None, size=768, out_dir=None):
    bpy.ops.wm.open_mainfile(filepath=str(root/'shots'/f'{NAME}.blend'))
    out = out_dir or root/'runs/renders/shots'/NAME; out.mkdir(parents=True, exist_ok=True)
    for mode in SCENES:
        sc = bpy.data.scenes[f'{NAME}_{mode}']
        for frame in frames or [1, (sc.frame_end+1)//2, sc.frame_end]:
            # The scenes share the animated marker, so every scene stands on the frame before one renders.
            for other in bpy.data.scenes:
                other.frame_set(frame)
            sc.render.filepath = str(out/f'{NAME}_{mode}_f{frame:04}.png')
            with bpy.context.temp_override(scene=sc):
                bpy.ops.render.render(write_still=True, scene=sc.name)
            print(f'WF_SHOT_RENDER {NAME} {mode} {frame}', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--root', type=Path, default=ROOT); p.add_argument('--render', action='store_true')
    p.add_argument('--render-only', action='store_true'); p.add_argument('--frames', nargs='+', type=int); p.add_argument('--size', type=int, default=768)
    p.add_argument('--out-dir', type=Path)
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    root = a.root.resolve()
    if not a.render_only:
        build(root, a.size)
    if a.render or a.render_only:
        render(root, a.frames, a.size, a.out_dir)
