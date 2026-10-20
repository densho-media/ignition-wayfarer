"""M4 slice 3 (TODO "Constructed exterior"): NONCANON review overlay of the shield rear construction, built in memory as ART_SR_* objects on
the saved vehicle from forward_shield.rear_construction (nothing is saved).

Function: the shield's rear face (what crew, drones and approaching craft see) must read as a jointed truss assembly behind a skin, with the
Crown housing's bays and their service access told apart. Fixed: the 90 m skin, ~3 m crown depth, the 3.5 m truss, the Crown housing r 41-44.5 m
with its windows, shutters, covers and carriage travel, the keels, ties and bypass collar (1.66 m docking-corridor clearance), the 15 m ring and
8 m radiator shadow margins; everything stays inside the truss envelope. Unknown: node, rib and hatch sizing, the hatch mechanism and the carriage
service path. Design freedom (PROTOTYPE judgment, forward_shield.rear_construction): node gussets, partition ribs, ochre service hatches.

    /snap/bin/blender -b --python src/wayfarer/studies/shield_rear_exterior.py -- --out runs/<stamp>-shield-rear
"""
from pathlib import Path
import argparse
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation')]
from spec import load
import forward_shield as fsh

PALETTE = dict(truss_node=(.30, .40, .48), crown_housing_rib=(.16, .19, .22), crown_service_hatch=(.78, .60, .24), scale=(1.0, .45, .1))
note = 'STUDY shield rear construction (ART_SR, NONCANON, PROTOTYPE gussets, ribs and hatches inside the truss envelope)'


def spec(s):
    return s


def apply(s, state=None):
    import bpy
    from mathutils import Matrix
    from common import material
    mats = {k: material(f'ART_SR_{k}', v) for k, v in PALETTE.items()}
    for p in fsh.rear_construction(s):
        me = bpy.data.meshes.new(p['name']); me.from_pydata(p['vertices'], [], p['faces']); me.update(); me.materials.append(mats[p['kind']])
        ob = bpy.data.objects.new(f"ART_SR_{p['name']}", me); bpy.context.scene.collection.objects.link(ob)
        ob['geometry_status'] = 'PROTOTYPE'; ob['study'] = 'shield_rear_exterior'
    # Non-diegetic 1.8 m figure on the housing aft plate of bay 1, beside its hatch.
    h = s['prototype']['human_height_m']; cr = fsh.crown(s)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.22, depth=h, location=(cr['x0']-h/2-.05, 42.75, 1.9), rotation=(0, math.pi/2, 0))
    fig = bpy.context.active_object; fig.name = 'ART_SR_Scale_Figure'; fig.data.materials.append(mats['scale']); fig['kind'] = 'scale_reference'


def close_ups(s, out, size, overlay=True):
    import bpy
    from mathutils import Vector, Matrix
    from common import pose_configuration
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
    pose_configuration(s, 'COAST'); bpy.context.scene.frame_set(1)
    if overlay:
        apply(s)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'; sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True; sh.cavity_type = 'WORLD'
    sh.show_backface_culling = False; sc.world.color = (.055, .075, .10)
    sc.render.resolution_x, sc.render.resolution_y = size, round(size*.75); sc.render.image_settings.file_format = 'PNG'
    cam = bpy.data.objects.new('ART_SR_Camera', bpy.data.cameras.new('ART_SR_Camera')); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.clip_start = 0.1; cam.data.clip_end = 900
    cr = fsh.crown(s); a = math.radians(30)
    P = lambda x, r, deg: Vector((x, r*math.cos(math.radians(deg)), r*math.sin(math.radians(deg))))
    views = {
        # the whole rear face from aft and outboard, past ring B
        'rear_face': (P(40, 70, 60), P(107, 20, 10), 28),
        # a truss sector: nodes on both chords between the r 15/25/35 rings
        'truss_sector': (P(96, 30, 32), P(108.5, 24, 15), 35),
        # two Crown bays from aft: ribs, hatches and the 1.8 m figure
        'housing_bays': (P(97, 40, 8), P(cr['x0'], 42.75, 2), 32),
    }
    paths = []
    for name, (loc, look, lens) in views.items():
        z = (loc-look).normalized(); up = Vector((1, 0, 0)) if abs(z.x) < .9 else Vector((0, 0, 1))
        x = up.cross(z).normalized(); y = z.cross(x)
        cam.location = loc; cam.rotation_euler = Matrix((x, y, z)).transposed().to_euler(); cam.data.lens = lens
        p = out/f'shield_rear_{name}.png'; sc.render.filepath = str(p); bpy.ops.render.render(write_still=True); paths.append(p.name)
        print('WF_SHIELD_REAR', name, flush=True)
    return paths


def main(out, size, whole, overlay=True):
    s = load(ROOT)[0]; out.mkdir(parents=True, exist_ok=True)
    result = dict(study='M4 slice 3: shield rear construction (NONCANON overlay, PROTOTYPE, nothing saved)', screen=fsh.rear_construction_screen(s),
                  parts=len(fsh.rear_construction(s)))
    print('WF_SHIELD_REAR screen', result['screen'], flush=True)
    if whole:
        import preview
        preview.render(ROOT, ['side', 'threequarter', 'shield_rear_detail'], size, 'COAST', out, study=sys.modules[__name__], quality='draft')
    result['renders'] = close_ups(s, out, size, overlay)
    (out/'shield_rear.json').write_text(json.dumps(result, indent=1)+'\n')
    print('WF_SHIELD_REAR done', out, flush=True)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); ap.add_argument('--size', type=int, default=1024)
    ap.add_argument('--no-whole', action='store_true'); ap.add_argument('--saved', action='store_true', help='render the saved generated shield, no overlay')
    a = ap.parse_args(argv)
    main(a.out if a.out.is_absolute() else ROOT/a.out, a.size, not a.no_whole, not a.saved)
