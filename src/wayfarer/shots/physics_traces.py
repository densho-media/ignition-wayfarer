"""PHYS-001 phase 7 (SIM-003, SIM-016, DYN-021): bake recorded Godot physics traces onto Blender proxies and render review stills.

Input: runs/physics/<scenario>.json written by godot/scripts/physics/recorder.gd (SIMULATION_ONLY, fixed step, Godot axes, the zone's
frame: ship-local or ring-frame). Each body becomes a keyed object (one LINEAR key per recorded step, scene fps = the trace rate), so
the motion is the trace's and nothing else; the scene block (room, handholds, body sizes) rebuilds the proxies. A character, when given,
is a labelled ARTISTIC layer parented to the actor capsule: it may pose, never move the capsule. The check re-reads every keyed frame
and compares it with the trace (tolerance 1e-4 m). Writes <out>/<scenario>.blend, stills and physics_traces.json.

  blender -b --python src/wayfarer/shots/physics_traces.py -- --out runs/<stamp>-physics-shots runs/physics/push_drift_catch.json ...
"""
import argparse
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Matrix, Quaternion, Vector

TOL_M = 1e-4
G2B = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))          # Godot (x, y, z) -> Blender (x, -z, y)


def vec(a):
    return G2B @ Vector(a)


def quat(q):
    r = Quaternion((q[3], q[0], q[1], q[2])).to_matrix()
    return (G2B @ r @ G2B.transposed()).to_quaternion()


def material(name, color, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*color, 1.0)
    bsdf.inputs['Alpha'].default_value = alpha
    if alpha < 1.0:
        m.blend_method = 'BLEND' if hasattr(m, 'blend_method') else None
    return m


def box(name, centre, size, mat):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=centre)
    o = bpy.context.object
    o.name = name
    o.scale = size
    o.data.materials.append(mat)
    return o


def rod(name, a, b, radius, mat):
    a, b = Vector(a), Vector(b)
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=(b-a).length, location=(a+b)/2)
    o = bpy.context.object
    o.name = name
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference((b-a).normalized())
    o.data.materials.append(mat)
    return o


def room(scene_block):
    """The compartment as a translucent shell (the trace's PROTOTYPE room), handholds as rods with their anchor ids."""
    r = scene_block.get('room', {})
    size = r.get('interior_m', [4.0, 2.0, 2.0])
    centre = vec(r.get('centre_m', [0.0, 0.0, 0.0]))
    wall = material('PHYS_WALL', (0.55, 0.6, 0.66), 0.18)
    rail = material('PHYS_RAIL', (0.95, 0.55, 0.12))
    # Godot size (x, y, z) -> Blender extents (x, z, y)
    shell = box('PHYS_ROOM', centre, (size[0], size[2], size[1]), wall)
    shell.display_type = 'WIRE'
    for h in scene_block.get('handholds', []):
        a, b = h.get('rail_start', h['anchor_point']), h.get('rail_end', h['anchor_point'])
        r = rod(f"PHYS_RAIL_{h['anchor_id']}", vec(a), vec(b) + (Vector((0, 0, 1e-3)) if a == b else Vector()), 0.02, rail)
        r['anchor_id'] = h['anchor_id']


def body(name, info, mat):
    kind = info.get('kind', 'tool')
    if kind == 'actor':
        bpy.ops.mesh.primitive_cylinder_add(radius=info.get('capsule_radius_m', 0.22), depth=info.get('capsule_height_m', 1.75))
        # the cylinder's local Z is the capsule axis: Godot +Y maps to Blender +Z (G2B)
    else:
        s = info.get('box_size_m', [0.3, 0.1, 0.1])
        bpy.ops.mesh.primitive_cube_add(size=1.0)
        bpy.context.object.scale = (s[0], s[2], s[1])
    o = bpy.context.object
    o.name = f'PHYS_{name.upper()}'
    o.rotation_mode = 'QUATERNION'
    o.data.materials.append(mat)
    o['trace_body'] = name
    return o


def bake(trace, scene):
    rows = trace['rows']
    scene.render.fps = round(1.0/trace['step_s'])
    scene.frame_start, scene.frame_end = 1, len(rows)
    info = trace.get('scene', {}).get('bodies', {})
    colors = {'actor': (0.2, 0.55, 0.95), 'tool': (0.9, 0.85, 0.2)}
    objects = {}
    for name in rows[0]['b']:
        kind = info.get(name, {}).get('kind', 'actor' if 'actor' in name or 'body' in name else 'tool')
        objects[name] = body(name, info.get(name, {'kind': kind}), material(f'PHYS_{kind}_{name}', colors.get(kind, (0.8, 0.8, 0.8))))
    for i, row in enumerate(rows):
        for name, o in objects.items():
            st = row['b'].get(name)
            if st is None:
                continue
            o.location = vec(st['p'])
            o.rotation_quaternion = quat(st['q'])
            o.keyframe_insert('location', frame=i+1)
            o.keyframe_insert('rotation_quaternion', frame=i+1)
    for o in objects.values():
        for fc in o.animation_data.action.fcurves if hasattr(o.animation_data.action, 'fcurves') else []:
            for k in fc.keyframe_points:
                k.interpolation = 'LINEAR'
    return objects


def tether(trace, objects):
    """scene.tether: a wire sphere of radius L about the anchor and a rod anchor -> actor, keyed per step (presentation of the trace; not in the key check)."""
    t = trace.get('scene', {}).get('tether')
    actor = next((o for o in objects.values() if o.get('trace_body') == 'actor'), None) if t else None
    if not t or actor is None:
        return None
    anchor = vec(t['anchor_point'])
    bpy.ops.mesh.primitive_uv_sphere_add(radius=t['length_m'], location=anchor, segments=24, ring_count=12)
    sph = bpy.context.object
    sph.name = 'PHYS_TETHER_LIMIT'
    sph.display_type = 'WIRE'
    sph.data.materials.append(material('PHYS_TETHER_LIMIT', (0.3, 0.9, 0.5), 0.15))
    sph['status'] = t.get('status', 'PROTOTYPE')
    bpy.ops.mesh.primitive_cylinder_add(radius=0.02, depth=1.0)
    line = bpy.context.object
    line.name = 'PHYS_TETHER'
    line.rotation_mode = 'QUATERNION'
    line.data.materials.append(material('PHYS_TETHER', (1.0, 0.8, 0.2)))
    for i, row in enumerate(trace['rows']):
        b = vec(row['b']['actor']['p'])
        d = b - anchor
        line.location = (anchor + b) / 2
        line.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized()) if d.length > 1e-9 else Quaternion()
        line.scale = (1, 1, max(d.length, 1e-6))
        for path in ('location', 'rotation_quaternion', 'scale'):
            line.keyframe_insert(path, frame=i+1)
    for fc in line.animation_data.action.fcurves if hasattr(line.animation_data.action, 'fcurves') else []:
        for k in fc.keyframe_points:
            k.interpolation = 'LINEAR'
    return line


def verify(trace, scene, objects):
    worst = 0.0
    for i, row in enumerate(trace['rows']):
        scene.frame_set(i+1)
        for name, o in objects.items():
            st = row['b'].get(name)
            if st is not None:
                worst = max(worst, (o.matrix_world.translation - vec(st['p'])).length)
    return worst


def camera_and_light(scene, objects, back=1.0):
    """A three-quarter view of the room (the trace's frame: the camera rides the ring in a ring zone)."""
    shell = bpy.data.objects['PHYS_ROOM']
    centre, size = shell.matrix_world.translation.copy(), max(shell.dimensions)
    bpy.ops.object.camera_add(location=centre + Vector((-0.45, -1.05, 0.4))*size*back)
    cam = bpy.context.object
    cam.rotation_euler = (centre - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = 30
    scene.camera = cam
    bpy.ops.object.light_add(type='SUN', location=centre + Vector((0, 0, 5)))
    bpy.context.object.data.energy = 3.0
    bpy.context.object.rotation_euler = (0.6, 0.2, 0.4)
    scene.world = scene.world or bpy.data.worlds.new('PHYS_WORLD')
    scene.world.color = (0.02, 0.025, 0.035)


def character(path, actor):
    """ARTISTIC layer: import a glTF character and parent it to the actor capsule; its pose is presentation, the capsule is the trace."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        if o.parent is None:
            o.parent = actor
            o.matrix_parent_inverse = Matrix.Identity(4)
            o.location = (0, 0, -actor.dimensions.z/2)
        o['layer'] = 'ARTISTIC (pose only; motion from the trace)'
    actor.hide_render = bool(new)
    return len(new)


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--character', default='')
    ap.add_argument('--size', type=int, default=640)
    ap.add_argument('--stills', type=int, default=3)
    ap.add_argument('traces', nargs='+')
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {'status': 'SIMULATION_ONLY', 'tolerance_m': TOL_M, 'shots': []}
    for path in a.traces:
        trace = json.loads(Path(path).read_text())
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        room(trace.get('scene', {}))
        objects = bake(trace, scene)
        tether(trace, objects)
        actor = next((o for n, o in objects.items() if trace.get('scene', {}).get('bodies', {}).get(n, {}).get('kind') == 'actor'), None)
        chars = character(a.character, actor) if a.character and actor else 0
        camera_and_light(scene, objects, 1.9 if trace.get('scene', {}).get('tether') else 1.0)
        worst = verify(trace, scene, objects)
        scene.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items} else 'BLENDER_EEVEE'
        scene.render.resolution_x = scene.render.resolution_y = a.size
        stills = []
        n = len(trace['rows'])
        for j in range(a.stills):
            f = 1 + round(j*(n-1)/max(a.stills-1, 1))
            scene.frame_set(f)
            scene.render.filepath = str(out/f"{trace['scenario']}_{f:05d}.png")
            bpy.ops.render.render(write_still=True)
            stills.append(scene.render.filepath)
        blend = out/f"{trace['scenario']}.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
        report['shots'].append({'scenario': trace['scenario'], 'trace': str(path), 'source': trace.get('source'), 'frames': n,
                                'fps': scene.render.fps, 'bodies': sorted(objects), 'max_key_error_m': worst, 'pass': worst <= TOL_M,
                                'character_objects': chars, 'blend': str(blend), 'stills': stills})
    (out/'physics_traces.json').write_text(json.dumps(report, indent=1)+'\n')
    print('WF_PHYSICS_TRACES ' + json.dumps({'result': 'PASS' if all(s['pass'] for s in report['shots']) else 'FAIL',
                                             'shots': [(s['scenario'], s['max_key_error_m']) for s in report['shots']]}))


if __name__ == '__main__':
    main()
