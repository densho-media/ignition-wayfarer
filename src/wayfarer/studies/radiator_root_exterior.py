"""M4 slice 2 (TODO "Constructed exterior"): NONCANON review overlay of the radiator root construction, built in memory as ART_RR_*
objects on the saved vehicle from thermal_geometry.root_construction (nothing is saved).

Function: the root must read as construction: where each boom, stay and coolant chase leaves the service casing, how the root post
sits on its boom, and how far each slide may travel. Fixed: the as-built 4,978.2 m2 net per blade, root r 6.5 m, the r 6.0 m casing,
the aft-root datum, the 0.20 m local travel, the 0.125 m seams, ring A's 1.5 m sweep clearance and the >= 0.24 m feed/return
clearances; nothing may lie on the emitting sheet or the root band. Unknown: boot material and sealing, member and saddle sizing,
actual growth (OD-007). Design freedom (PROTOTYPE judgment, radiators.root_construction): casing boots, saddle cradles, slide stops,
and the colour hierarchy (structure grey booms, off-white boots, dark steel saddles and stops; red and yellow stay the only signals).

    /snap/bin/blender -b --python src/wayfarer/studies/radiator_root_exterior.py -- --out runs/<stamp>-rad-roots
"""
from pathlib import Path
import argparse
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation')]
from spec import load
import thermal_geometry as tg

PALETTE = dict(casing_boot=(.80, .78, .72), root_saddle=(.22, .25, .28), slide_stop=(.22, .25, .28), scale=(1.0, .45, .1))
note = 'STUDY radiator root construction (ART_RR, NONCANON, PROTOTYPE boots, saddles and stops off the emitting sheet)'


def spec(s):
    return s


def blade_matrices():
    import bpy
    return [o.matrix_world.copy() for o in sorted(bpy.data.objects, key=lambda o: o.name) if str(o.get('component_id', '')).startswith('WF.RADIATOR.0')]


def apply(s, state=None):
    import bpy
    from mathutils import Matrix
    from common import material
    d = tg.blade_of(s); mats = {k: material(f'ART_RR_{k}', v) for k, v in PALETTE.items()}
    for o in bpy.data.objects:          # the study's colour hierarchy: booms and stays as structure
        if o.get('kind') in ('root_boom',) and o.data and hasattr(o.data, 'materials') and o.data.materials:
            o.data.materials[0] = material('Structure', (.30, .40, .48))
    for i, world in enumerate(blade_matrices()):
        for p in tg.root_construction(s, d):
            me = bpy.data.meshes.new(p['name']); me.from_pydata(p['vertices'], [], p['faces']); me.update(); me.materials.append(mats[p['kind']])
            ob = bpy.data.objects.new(f'ART_RR_{i}_{p["name"]}', me); bpy.context.scene.collection.objects.link(ob); ob.matrix_world = world
            ob['geometry_status'] = 'PROTOTYPE'; ob['study'] = 'radiator_root_exterior'
    # Non-diegetic 1.8 m scale figure standing on the casing beside the datum root of blade 1.
    world = blade_matrices()[0]; h = s['prototype']['human_height_m']; m = next(q for q in tg.mounts(s, d) if q['role'] == 'FIXED_DATUM')
    v0 = tg.casing_surface_v(s, d, 1.2, 1.6)[1]
    bpy.ops.mesh.primitive_cylinder_add(radius=0.22, depth=h, location=(0, 0, 0))
    fig = bpy.context.active_object; fig.name = 'ART_RR_Scale_Figure'; fig.data.materials.append(mats['scale']); fig['kind'] = 'scale_reference'
    fig.matrix_world = world @ Matrix.Translation((m['u']-1.6, v0+h/2, 1.4)) @ Matrix.Rotation(math.pi/2, 4, 'X')
    return world


def close_ups(s, out, size, overlay=True):
    import bpy
    from mathutils import Vector, Matrix
    from common import pose_configuration
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
    pose_configuration(s, 'COAST'); bpy.context.scene.frame_set(1)
    world = apply(s) if overlay else blade_matrices()[0]
    for o in bpy.data.objects:
        if o.name.startswith('Hull_'):
            o.hide_render = False
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'; sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True; sh.cavity_type = 'WORLD'
    sh.show_backface_culling = False; sc.world.color = (.055, .075, .10)
    sc.render.resolution_x, sc.render.resolution_y = size, round(size*.75); sc.render.image_settings.file_format = 'PNG'
    cam = bpy.data.objects.new('ART_RR_Camera', bpy.data.cameras.new('ART_RR_Camera')); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.clip_start = 0.05; cam.data.clip_end = 600
    d = tg.blade_of(s); local = lambda u, v, z: world @ Vector((u, v, z))
    views = {
        # both roots, the coolant chases and the first stay, from outboard and aft
        'root_pair': (local(-16, 7, 11), local(-1, 0, 0), 30),
        # the datum root, its lugs, saddle and the feed/return boots, with the 1.8 m figure
        'datum_root': (local(-10.5, 2.4, 4.6), local(-6.5, -0.2, 0.3), 32),
        # the slide root: block on its rail between two stops, saddle and boom boot
        'slide_root': (local(9.5, 1.6, 3.4), local(6, -0.2, 0), 35),
        # a bay stay with its boot and stops
        'stay': (local(-14.5, 1.6, 3.4), local(-18.2, -0.2, 0), 35),
    }
    paths = []
    for name, (loc, look, lens) in views.items():
        z = (loc-look).normalized(); up = (world.to_3x3() @ Vector((0, 1, 0))).normalized()
        x = up.cross(z).normalized(); y = z.cross(x)
        cam.location = loc; cam.rotation_euler = Matrix((x, y, z)).transposed().to_euler(); cam.data.lens = lens
        p = out/f'rad_root_{name}.png'; sc.render.filepath = str(p); bpy.ops.render.render(write_still=True); paths.append(p.name)
        print('WF_RAD_ROOT', name, flush=True)
    return paths


def main(out, size, whole, overlay=True):
    s = load(ROOT)[0]; out.mkdir(parents=True, exist_ok=True); d = tg.blade_of(s)
    result = dict(study='M4 slice 2: radiator root construction (NONCANON overlay, PROTOTYPE, nothing saved)', screen=tg.root_construction_screen(s, d),
                  compliance=tg.compliance(s, d)['checks'])
    print('WF_RAD_ROOT screen', result['screen']['fails'], flush=True)
    if whole:
        import preview
        preview.render(ROOT, ['side', 'threequarter', 'root_detail'], size, 'COAST', out, study=sys.modules[__name__], quality='draft')
    result['renders'] = close_ups(s, out, size, overlay)
    (out/'rad_root.json').write_text(json.dumps(result, indent=1)+'\n')
    print('WF_RAD_ROOT done', out, flush=True)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); ap.add_argument('--size', type=int, default=1024)
    ap.add_argument('--no-whole', action='store_true'); ap.add_argument('--saved', action='store_true', help='render the saved generated roots, no overlay')
    a = ap.parse_args(argv)
    main(a.out if a.out.is_absolute() else ROOT/a.out, a.size, not a.no_whole, not a.saved)
