"""P1F drive-manifold review renders (brief section 47). Opens a vehicle, poses the drive in memory, saves nothing.

Two modes per target: cinematic (hardware, plasma, light; no debug layers) and engineering (the drive control's debug
toggles switched on in memory, share and couple labels). Schematic envelopes (core, common region, manifold, spine,
shield, engineering bay) and the WF_STRUCTURE cage are hidden and replaced by local translucent copies so the inside
reads without a section cut (a cut opens tubes and shows their dark interiors).
"""
from pathlib import Path
import argparse
import itertools
import math
import sys
import bpy
from mathutils import Matrix, Vector
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build')]
from common import material, pose_drive_state, pose_configuration, drive_debug_visibility
from spec import load
import drive_manifold as dm
import layout

GHOSTS = ['Fusion_Core', 'Common_Plasma_Region', 'Magnetic_Manifold', 'Structural_Spine', 'Reactor_Shadow_Shield_Envelope', 'Engineering_Envelope', 'SPINE_TERMINATION_HUB', 'OPTICAL_BORE_A', 'OPTICAL_BORE_B']
HIDE = ['Assembly_HULL', 'Assembly_STORAGE', 'Assembly_HABITAT', 'Assembly_SERVICE', 'Assembly_THERMAL', 'Assembly_EYE']
AFT_VIEW = (-1, 0, .0005)   # camera aft on -X looking +X, Z up: +Y is screen-left
LEGEND = 'green: control light (straight, unbent) | violet: charged plasma | blue: magnetic field | amber: Fiji lattice | orange: separatrix'


def box(x0, x1, r):
    """Framing corners around the drive axis."""
    return [Vector(p) for p in itertools.product((x0, x1), (-r, r), (-r, r))]


def targets(s):
    """(name, title, state source, camera direction, focus x, corners, overlays, options). Options: solid = name prefixes of ghosted
    structure members drawn solid in this view; open_nozzle = hide the nozzle field envelope so the coils and strike modules show; storage = show the cryogenic storage assembly (tanks ghosted)."""
    st = dm.stations(s); A = layout.origin(s, 'AFT')   # drive views follow the AFT datum (nozzle exit)
    return [
        ('core_to_throat', 'Fusion core -> solid common plasma column -> convergence throat', ('config', None), (.25, -1, .35), (st['core_fwd']+st['throat_exit'])/2, box(st['throat_exit']-.5, st['core_fwd']+.5, 5), 'magnetics', {}),
        ('optical_routes', 'Two independent routes: lasers -> turn and entry mirrors -> dog-leg bores through the hub and shield -> splitters -> corridor legs -> heads', ('config', None), (.15, -1, .55), A+26, box(A+14.5, A+37.5, 6.0), 'optics', {}),
        ('spine_termination', 'Structural_Spine ends on the terminated hub at the shield bulkhead; the two dog-leg bores pass beside the spine end, the core column starts aft of the slab', ('config', None), (.3, -1, .35), (st['shield_aft']+layout.at(s, s['drive_manifold']['hub_forward_x']))/2, box(st['shield_aft']-3.0, layout.at(s, s['drive_manifold']['hub_forward_x'])+2.5, 6.0), 'optics', {}),
        ('distributor_heads', 'Distributor-head cartridges in the lattice gaps: two chords from each head, one A and one B chord into each gate L1-L4', ('config', None), (.35, -1, .8), A+15.5, box(A+13, A+18, 6.0), 'optics', {}),
        ('lattice_sectors', 'Fiji lattice sectors L1-L4 with gate illumination and seed coils', ('config', None), (.35, -.8, 1), A+14.3, box(A+12.3, A+16.7, 3.8), 'optics', {}),
        ('four_way_split', 'One common flux domain separating into four flux channels', ('config', None), (.2, -1, .7), A+14.5, box(A+7.5, A+22, 4.5), 'magnetics', {}),
        ('branch_to_nozzle', 'Branch -> nozzle interfaces, nozzle expansion and exhaust (-X)', ('config', None), (-.8, -1, .55), A+4.5, box(A-1.5, A+10.5, 4.8), 'magnetics', {}),
        ('nominal_balanced', 'Nominal 25/25/25/25 straight acceleration', ('action', 'WF_MANIFOLD_BALANCED', 24), (.3, -1, .45), A+17.5, box(A-1.5, A+37.5, 5.2), 'both', {}),
        ('steering_pitch', 'Asymmetric steering: pitch demo, gates trim then shares follow', ('action', 'WF_MANIFOLD_PITCH', 84), (.3, -1, .45), A+12.5, box(A-1.5, A+22.5, 5.0), 'both', {}),
        ('laser_a_fail', 'Laser A failed: laser B carries all four gate channels', ('action', 'WF_LASER_A_FAIL', 100), (.15, -1, .55), A+26, box(A+14.5, A+37.5, 6.0), 'optics', {}),
        ('flux_channel_fault', 'Flux channel F3 fault (oblique): F3 isolated and F2 derated together; N1/N4 hold at drive 0.5, couple 0', ('action', 'WF_FLUX_CHANNEL_FAIL', 100), (.2, -1, .7), A+10.5, box(A-1.5, A+22, 5.0), 'magnetics', {}),
        ('nozzle_map', 'Owner nozzle map 06!A48 / 15!C71 (WORKING), seen from aft: N1 +Y+Z, N2 -Y+Z, N3 +Y-Z, N4 -Y-Z, the EYE F1-F4 quadrants (+Y is screen-left)', ('config', None), AFT_VIEW, A+4.5, box(A-1.0, A+10.0, 5.8), 'magnetics', {'nozzle_labels': True}),
        ('owner_example_yaw', 'Owner example 20/30/20/30 (WF_MANIFOLD_IMBALANCE) is a yaw couple under the owner map: N2/N4 at 30%, N1/N3 at 20%, no pitch', ('action', 'WF_MANIFOLD_IMBALANCE', 84), AFT_VIEW, A+4.5, box(A-1.0, A+10.0, 5.8), 'magnetics', {'nozzle_labels': True}),
        ('flux_channel_fault_aft', 'Channel-loss recovery from aft (06!A51): F3 failed and F2 sacrificed (dark N2/N3 diagonal), N1/N4 at normal branch width, drive 0.5, couple 0', ('action', 'WF_FLUX_CHANNEL_FAIL', 100), AFT_VIEW, A+4.5, box(A-1.0, A+10.0, 5.8), 'magnetics', {'nozzle_labels': True}),
        ('vector_limits', 'Steering limits (15!G76), no pose keyed: +-5 deg normal WORKING (green) | +-8 deg emergency DIAGNOSTIC (orange) | authority OPEN (06!E52)', ('config', None), (-.45, -1, .3), A-2.0, box(A-8.5, A+3.0, 5.8), 'magnetics', {'nozzle_labels': 'exhaust_end', 'cones': True, 'note': 'emergency +-8 deg is a study limit, not qualified continuous operation (Fiji 25!E64); no gimbal hardware is modelled; vector authority OPEN (06!E52)'}),
        ('hot_section', 'Plasma-facing liners on the outer side of the solid plasma column: core and throat refractory tiles, seed coils and gate beams', ('config', None), (.25, -1, .35), (st['core_fwd']+st['throat_exit'])/2, box(st['throat_exit']-.5, st['core_fwd']+.5, 5), 'optics', {}),
        ('nozzle_hot_face', 'Nozzle strike modules (Q40) on the throat-side HTS coil inner faces, warm yoke rings and straps standing off the coils, pickups leaving the inlet yoke for the thrust ring (MagneticNozzle_FieldEnvelope hidden in this view)', ('config', None), (-.8, -1, .55), A+4.5, box(A-1.0, A+10.0, 5.8), 'magnetics', {'solid': ('Nozzle_Pickup_', 'Nozzle_Yoke_', 'Thrust_Node_', 'Hub_Web_'), 'open_nozzle': True}),
        ('cryo_feed', 'Cryogenic feed lines (drawn 3x thick, bright, preview only): D and 3He lines: tank aft caps -> stepped shield sleeves -> fusion-core forward face; hydrogen lines: out to the corridor -> injection ring', ('config', None), (.25, -1, .5), A+36, box(A+20, A+52.5, 6.0), 'both', {'storage': True}),
        ('cryo_feed_sleeves', 'Stepped (dog-leg) feed sleeves through the shadow-shield slab: each line jogs outward mid-slab, the hydrogen lines out to the cage-to-skin corridor, no straight line of sight (lines drawn 3x thick, preview only)', ('config', None), (.35, -1, .0), (st['shield_aft']+st['shield_fwd'])/2, box(st['shield_aft']-3.5, st['shield_fwd']+3.5, 6.0), 'both', {'storage': True}),
    ]


def cage():
    """Every drawable WF_STRUCTURE member that is not already an envelope ghost (frames, rails, braces, ring, webs, hubs)."""
    return [o.name for o in bpy.data.objects if o.library and Path(o.library.filepath).name == 'WF_STRUCTURE.blend'
            and o.type in {'MESH', 'CURVE'} and o.name not in GHOSTS and o.get('kind') != 'hull_envelope']


def ghost(names, mat=None):
    mat = mat or material('Preview_Ghost', (.55, .7, .8), .15, alpha=.07)
    dg = bpy.context.evaluated_depsgraph_get(); made = []
    for name in names:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.hide_render:
            continue
        copy = bpy.data.objects.new(f'Preview_Ghost_{name}', bpy.data.meshes.new_from_object(obj.evaluated_get(dg)))
        copy.matrix_world = obj.matrix_world; copy.data.materials.clear(); copy.data.materials.append(mat)
        bpy.context.scene.collection.objects.link(copy); made.append(copy)
        obj.hide_render = obj.hide_viewport = True
    return made


def labels(scene, camera, lines, width, aspect, depth):
    for obj in [o for o in scene.objects if o.name.startswith('Preview_Label')]:
        bpy.data.objects.remove(obj, do_unlink=True)
    # Dark backing plate so labels stay legible over emissive plasma.
    top = width/aspect*.5; bottom = width/aspect*(.45-(len(lines)-.2)*.036)
    plate = bpy.data.meshes.new('Preview_Label_Plate'); plate.from_pydata([(-width*.5, bottom, 0), (width*.5, bottom, 0), (width*.5, top, 0), (-width*.5, top, 0)], [], [(0, 1, 2, 3)])
    plate.materials.append(material('LabelPlate', (.01, .012, .018), 0, alpha=.72))
    obj = bpy.data.objects.new('Preview_Label_Plate', plate); scene.collection.objects.link(obj); obj.parent = camera; obj.location = (0, 0, -depth-.02)
    for i, text in enumerate(lines):
        data = bpy.data.curves.new(f'Preview_Label_{i}', 'FONT'); data.body = text; data.size = width*(.022 if i == 0 else .0145)
        data.materials.append(material('Label', (.70, .85, .93), 1))
        obj = bpy.data.objects.new(data.name, data); scene.collection.objects.link(obj); obj.parent = camera
        obj.location = (-width*.48, width/aspect*(.45-i*.036), -depth)
    return bottom


def nozzle_labels(scene, camera, s, scale, depth, ceiling, at_exhaust_end=False):
    """Preview-only text N1-N4 beside each nozzle exit on its outer side, or past the end of its exhaust run in an oblique view, drawn in
    front of the scene on an opaque plate, so neither the hardware nor the debug lines cover it, and below the header plate (ceiling,
    camera-local). Nothing is saved."""
    st = dm.stations(s); q = s['prototype']['nozzle_offset_m']; r = s['prototype']['nozzle_exit_radius_m']; facets = s['propulsion']['manifold']['nozzle_map']['labels']
    to_camera = (Matrix.Translation(camera.location) @ camera.rotation_euler.to_matrix().to_4x4()).inverted()
    size = scale*.032
    for k, (yy, zz) in enumerate(dm.quadrants(s), 1):
        centre = to_camera @ Vector((st['exit'], yy*q, zz*q))
        at = to_camera @ (Vector((st['exit']-s['drive_manifold']['exhaust_length_m']-.5, yy*q, zz*q)) if at_exhaust_end else Vector((st['exit'], yy*(q+r+.4), zz*q)))
        at.y = min(at.y, ceiling-size*1.1)
        right = at.x >= centre.x; body = f'{facets[k-1]}  F{k}  {"+" if yy > 0 else "-"}Y{"+" if zz > 0 else "-"}Z'
        data = bpy.data.curves.new(f'Preview_Label_N{k}', 'FONT'); data.body = body; data.size = size
        data.align_x = 'LEFT' if right else 'RIGHT'; data.align_y = 'CENTER'; data.materials.append(material('Label', (.70, .85, .93), 1))
        obj = bpy.data.objects.new(data.name, data); scene.collection.objects.link(obj); obj.parent = camera; obj.location = (at.x, at.y, -depth)
        w = len(body)*size*.62+size*.6; h = size*1.5; x0 = at.x-size*.3 if right else at.x-w+size*.3
        plate = bpy.data.meshes.new(f'Preview_Label_NPlate{k}'); plate.from_pydata([(x0, at.y-h/2, 0), (x0+w, at.y-h/2, 0), (x0+w, at.y+h/2, 0), (x0, at.y+h/2, 0)], [], [(0, 1, 2, 3)])
        plate.materials.append(material('NozzleLabelPlate', (.01, .012, .018), 0))   # opaque: a plume behind it is far brighter than the text
        obj = bpy.data.objects.new(plate.name, plate); scene.collection.objects.link(obj); obj.parent = camera; obj.location = (0, 0, -depth-.01)


def vector_cones(scene, s):
    """Preview-only +-5 deg (WORKING) and +-8 deg (DIAGNOSTIC) steering cones at each exit; limits only, nothing is saved."""
    normal = material('Preview_VectorNormal', (.3, 1.0, .5), 6); emergency = material('Preview_VectorEmergency', (1.0, .5, .1), 6)
    for cone in dm.vector_limit_cones(s):
        for tag, deg, mat in (('normal', cone['normal_deg'], normal), ('emergency', cone['emergency_deg'], emergency)):
            r = cone['length']*math.tan(math.radians(deg)); ax, ay, az = cone['apex']; n = 32
            verts = [(ax, ay, az)]+[(ax-cone['length'], ay+r*math.cos(math.tau*i/n), az+r*math.sin(math.tau*i/n)) for i in range(n)]
            faces = [(0, 1+i, 1+(i+1) % n) for i in range(n)]
            mesh = bpy.data.meshes.new(f'Preview_VectorLimit_{tag}_N{cone["nozzle"]}'); mesh.from_pydata(verts, [], faces); mesh.materials.append(mat)
            obj = bpy.data.objects.new(mesh.name, mesh); scene.collection.objects.link(obj)
            wire = obj.modifiers.new('Preview_Wire', 'WIREFRAME'); wire.thickness = .05; wire.use_replace = True   # outline only, so the plume stays visible


def render(root=ROOT, names=None, state='HIGH_POWER', size=768, modes=('cinematic', 'engineering'), out_dir=None):
    s, *_ = load(root)
    cfg = s['configuration'][state]
    if not cfg['buildable']:
        raise ValueError(f'Not buildable: {state}')
    bpy.ops.wm.open_mainfile(filepath=str(root/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
    scene = bpy.context.scene
    for name in HIDE:
        obj = bpy.data.objects.get(name)
        if obj is not None:
            obj.hide_render = obj.hide_viewport = True
    pose_configuration(s, state)
    ghost(GHOSTS)
    cage_ghosts = {c.name[len('Preview_Ghost_'):]: c for c in ghost(cage(), material('Preview_Cage', (.42, .52, .6), .05, alpha=.2))}
    tank_ghosts = ghost([f'Feed_Run_Tank_{j:02}' for j in range(1, 5)], material('Preview_Tank', (.5, .66, .78), .1, alpha=.12))
    for copy in tank_ghosts:
        copy.hide_render = copy.hide_viewport = True
    # Preview-only legibility: the 0.08 m feed lines are redrawn 3x thick in a bright emissive material (the saved assets are untouched).
    feed_mat = material('Preview_Feed', (.4, 1.0, .9), 6)
    feed_copies = []
    for src_obj in [o for o in bpy.data.objects if o.name.startswith('CRYO_FEED_LINE_') and o.type == 'CURVE']:
        data = src_obj.data.copy(); data.bevel_depth = src_obj.data.bevel_depth*3; data.materials.clear(); data.materials.append(feed_mat)
        copy = bpy.data.objects.new(f'Preview_Feed_{src_obj.name}', data); copy.matrix_world = src_obj.matrix_world
        bpy.context.scene.collection.objects.link(copy); feed_copies.append(copy)
        src_obj.hide_render = src_obj.hide_viewport = True
    scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = 24; scene.cycles.use_denoising = True; scene.cycles.seed = 0
    scene.cycles.transparent_max_bounces = 256; scene.cycles.max_bounces = 256
    scene.render.resolution_x = size; scene.render.resolution_y = round(size*.75); scene.render.image_settings.file_format = 'PNG'
    scene.world.use_nodes = True
    bg = next(n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = (.02, .025, .035, 1); bg.inputs['Strength'].default_value = .5
    for i, (loc, energy) in enumerate([((70, -100, 180), 1.6), ((-90, 60, 100), 1.0), ((20, 100, -100), .5)]):
        data = bpy.data.lights.new(f'Preview_Sun_{i}', 'SUN'); data.energy = energy; data.angle = .15
        obj = bpy.data.objects.new(data.name, data); scene.collection.objects.link(obj); obj.location = loc
        obj.rotation_euler = (-obj.location).to_track_quat('-Z', 'Y').to_euler()
    cam_data = bpy.data.cameras.new('Preview_Camera'); camera = bpy.data.objects.new(cam_data.name, cam_data); scene.collection.objects.link(camera); scene.camera = camera
    cam_data.type = 'ORTHO'; cam_data.clip_start = .1; cam_data.clip_end = 2000
    out = out_dir or root/'runs/renders/p1/drive'; out.mkdir(parents=True, exist_ok=True)
    aspect = scene.render.resolution_x/scene.render.resolution_y
    written = []
    for name, title, source, direction, fx, corners, overlay, options in targets(s):
        if names and name not in names:
            continue
        if source[0] == 'config':
            values = dm.configuration_state(s, state); where = f'{state} configuration'
        else:
            values = dm.action_state(s, source[1], source[2]); where = f'{source[1]} frame {source[2]}'
        pose_drive_state(values)
        shares = dm.normalize([values[f'flux_share_{j}'] for j in range(1, 5)])
        arm = dm.couple_arm(s, shares)
        direction = Vector(direction).normalized(); focus = Vector((fx, 0, 0))
        quat = (-direction).to_track_quat('-Z', 'Y')
        projected = [quat.inverted()@(p-focus) for p in corners]
        width = max(max(p.x for p in projected)-min(p.x for p in projected), (max(p.y for p in projected)-min(p.y for p in projected))*aspect)*1.12
        cam_data.ortho_scale = width
        # Per-view visibility: some structure members solid, the storage assembly shown with ghosted tanks.
        solid = [n for n in cage_ghosts if n.startswith(options.get('solid', ('\0',)))]
        for n in solid:
            cage_ghosts[n].hide_render = cage_ghosts[n].hide_viewport = True; bpy.data.objects[n].hide_render = bpy.data.objects[n].hide_viewport = False
        envelopes = [o for o in bpy.data.objects if o.name == 'MagneticNozzle_FieldEnvelope']
        for o in envelopes:
            o.hide_render = o.hide_viewport = bool(options.get('open_nozzle'))
        storage = bpy.data.objects.get('Assembly_STORAGE')
        if storage is not None:
            storage.hide_render = storage.hide_viewport = not options.get('storage')
        for copy in tank_ghosts + feed_copies:
            copy.hide_render = copy.hide_viewport = not options.get('storage')
        camera.location = focus+direction*400; camera.rotation_euler = quat.to_euler()
        for mode in modes:
            engineering = mode == 'engineering'
            drive_debug_visibility(magnetics=engineering and overlay in {'magnetics', 'both'}, optics=engineering and overlay in {'optics', 'both'},
                                   separatrices=engineering and overlay in {'magnetics', 'both'})
            scene.frame_set(scene.frame_current)
            lines = [f'WAYFARER 001 / P1F DRIVE / {name.upper().replace("_", " ")} / {mode.upper()}', title,
                     f'{where} | drive {values["drive_active"]:.2f} | seed field {values["manifold_field_strength"]:.2f} | lattice {values["lattice_activation"]:.2f} | laser A {values["laser_A_power"]:.2f} B {values["laser_B_power"]:.2f} (normalized; ratings OPEN)',
                     'flux shares N1-N4 ' + ' / '.join(f'{x*100:.0f}%' for x in shares) + f' | couple arm pitch {arm["pitch_arm_m"]:+.2f} m, yaw {arm["yaw_arm_m"]:+.2f} m, roll 0 | gates ' + ' '.join(f'{values[f"optical_gate_{j}"]:.2f}' for j in range(1, 5))]
            if engineering:
                lines += [LEGEND, 'exhaust leaves along -X; thrust on the ship is +X | geometry PROTOTYPE; separatrices are field boundaries, not walls']
            else:
                lines += ['exhaust -X, thrust +X | schematic envelopes and structure cage ghosted; hull, radiators, EYE, habitat hidden | geometry PROTOTYPE']
            if options.get('note'):
                lines.append(options['note'])
            ceiling = labels(scene, camera, lines, width, aspect, cam_data.clip_start+.05)
            for o in [o for o in scene.objects if o.name.startswith('Preview_VectorLimit_')]:
                bpy.data.objects.remove(o, do_unlink=True)
            if options.get('nozzle_labels'):
                nozzle_labels(scene, camera, s, width, cam_data.clip_start+.06, ceiling, options['nozzle_labels'] == 'exhaust_end')
            if options.get('cones'):
                vector_cones(scene, s)
            path = out/f'{name}_{mode}.png'; scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True); written.append(path)
            print(f'WF_DRIVE_PREVIEW {name} {mode}', flush=True)
        for n in solid:
            cage_ghosts[n].hide_render = cage_ghosts[n].hide_viewport = False; bpy.data.objects[n].hide_render = bpy.data.objects[n].hide_viewport = True
    return written


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--root', type=Path, default=ROOT); p.add_argument('--targets', nargs='+')
    p.add_argument('--state', default='HIGH_POWER'); p.add_argument('--size', type=int, default=768)
    p.add_argument('--modes', nargs='+', choices=['cinematic', 'engineering'], default=['cinematic', 'engineering']); p.add_argument('--out-dir', type=Path)
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if a.size < 128 or a.size > 1024:
        raise ValueError('Use inexpensive 128-1024 px previews')
    render(a.root.resolve(), a.targets, a.state, a.size, tuple(a.modes), a.out_dir)
