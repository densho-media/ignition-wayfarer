"""IND-001 study (step 1.2-1.3): instructor and newcomer proxies, rendered for the user to pick.

turnaround: the picked figures and the study variants standing, front / side / back, shaded (Workbench, material colours) and as a black silhouette
on white (the Art Style silhouette test applied to people: identity must survive without colour, logos or effects).
greeting: S004A in the entry chamber, in memory on the saved vehicle (DOCKED, hatches open, zone-1 mannequin hidden) with one route_fitout
scheme, the instructor variant anchored on the deck band and the newcomer coming through the outer hatch; a third-person study camera and
the newcomer's point of view (fore up). Nothing is saved. Palettes are PROTOTYPE depiction choices (Fashion Bible 08 Spacer, 03 Great Union).

    /snap/bin/blender -b --python src/wayfarer/studies/induction_characters.py -- --mode turnaround --out runs/<stamp>-induction
    /snap/bin/blender -b --python src/wayfarer/studies/induction_characters.py -- --mode greeting --scheme D --out runs/<stamp>-induction
"""
from pathlib import Path
import argparse
import math
import sys
import bpy
from mathutils import Matrix, Vector
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation'), str(ROOT/'src/wayfarer/studies'),
                str(ROOT/'src/wayfarer/components')]
import characters as ch
from figures import build, look

# Study variants beside the picked [characters] figures (I1 = [characters.instructor], N = [characters.newcomer]).
VARIANTS = {
    'I2': dict(title='Instructor, Spacer close suit', role='instructor', stature=1.78, build=1.0, suit='suit', over=None,
               kit=('collar', 'harness', 'mask', 'wrist', 'marks', 'seams')),
    'I3': dict(title='Instructor, test-flight kit', role='instructor', stature=1.78, build=1.0, suit='suit', over=None,
               kit=('collar', 'harness', 'mask', 'comms', 'wrist', 'marks', 'seams', 'pockets', 'helmet')),
}


def figures():
    from spec import load
    s = load(ROOT)[0]
    return {'I1': ch.figure(s, 'instructor'), **VARIANTS, 'N': ch.figure(s, 'newcomer')}


def turnaround(out, size):
    bpy.ops.wm.read_factory_settings(use_empty=True); scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'; scene.render.resolution_x = size; scene.render.resolution_y = round(size*1.4)
    scene.render.image_settings.file_format = 'PNG'; scene.world = bpy.data.worlds.new('W'); scene.world.color = (1, 1, 1)
    sh = scene.display.shading; cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); scene.collection.objects.link(cam)
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 2.15; scene.camera = cam
    for key, fig in figures().items():
        c = bpy.data.collections.new(key); scene.collection.children.link(c)
        j = ch.skeleton(fig, ch.STAND); made = build(c, key, ch.parts(fig, j)); mid = Vector((0, 0, (j['head'][2]+j['sole_right'][2])/2+.06))
        for view, d in (('front', (0, 1, 0)), ('side', (1, 0, 0)), ('back', (0, -1, 0))):
            look(cam, mid+Vector(d)*6, mid, (0, 0, 1))
            for mode in ('shaded', 'silhouette'):
                if mode == 'shaded':
                    sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True; sh.show_shadows = False; scene.display.shading.background_type = 'WORLD'
                    scene.world.color = (.93, .93, .94)
                else:
                    sh.light = 'FLAT'; sh.color_type = 'SINGLE'; sh.single_color = (0, 0, 0); sh.show_cavity = False; scene.world.color = (1, 1, 1)
                scene.render.filepath = str(out/f'char_{key}_{view}_{mode}.png'); bpy.ops.render.render(write_still=True)
        print(f'WF_INDUCTION_STUDY turnaround {key}', flush=True)
        for o in made:
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(c)


def greeting(out, size, scheme, instructors):
    import induction_entry as ie
    import human_entry as he
    import route_fitout as rf
    from common import material, pose_configuration
    from spec import load
    from entry_preview import label
    s, *_ = load(ROOT); f = he.ports(s)[0]
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
    scene = bpy.context.scene; pose_configuration(s, 'DOCKED'); ctrl = bpy.data.objects['DOCK_ENTRY_CTRL']
    for which in ('outer', 'inner'):
        ctrl[f"{f['name']}_{which}_open"] = 1.0
    ctrl.update_tag(); scene.frame_set(scene.frame_current)
    for obj in bpy.data.objects:
        if obj.name.startswith('Human_Entry_'):
            obj.hide_render = True
    scene.render.resolution_x = size; scene.render.resolution_y = round(size*.75); scene.render.image_settings.file_format = 'PNG'
    scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = 64; scene.cycles.use_denoising = True; scene.cycles.seed = 0
    bg = next(n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND'); bg.inputs['Color'].default_value = (.02, .025, .035, 1); bg.inputs['Strength'].default_value = .4
    c = bpy.data.collections.new('ART_STUDY_INDUCTION'); scene.collection.children.link(c)
    ie.build(c, s, f, ie.SCHEMES[scheme], ie.PALETTES[scheme])
    for n in ie.SHELLS:
        bpy.data.objects[n].data.materials[0] = material(f'Study_Shell_{scheme}', ie.PALETTES[scheme]['shell'])
    g = ch.greeting(s, f); u, w = he.axes(f); pt = lambda a, p, q: Vector((f['x']+p, a*u[1]+q*w[1], a*u[2]+q*w[2]))
    figs = figures(); newcomer, nj = ch.staged(g['newcomer'], figs['N']); body = build(c, 'N', newcomer)
    # First person: the newcomer's own head, torso and upper arms are hidden; the reaching forearms and hands stay.
    own = [o for o in body if not any(k in o.name for k in ch.OWN_VIEW)]
    cam = bpy.data.objects.new('Study_Camera', bpy.data.cameras.new('Study_Camera')); scene.collection.objects.link(cam); cam.data.clip_start = .05
    aspect = scene.render.resolution_x/scene.render.resolution_y
    for key in instructors:
        fig = figs[key]; parts, ij = ch.staged(g['instructor'], fig); made = build(c, key, parts)
        hu = Vector(nj['head_up']); hf = Vector(nj['face']); eye = Vector(nj['head'])+hf*.09+hu*.02
        views = {'third': (pt(5.35, .30, -1.02), pt(5.62, -.10, .40), (1, 0, 0), 18.0),
                 'pov': (eye, Vector(ij['head'])+Vector((-.1, 0, 0)), (1, 0, 0), 18.0)}
        for view, (at, target, up, lens) in views.items():
            look(cam, at, target, up); cam.data.lens = lens; scene.camera = cam
            for o in own:
                o.hide_render = view == 'pov'
            width = 2*.25*math.tan(cam.data.angle_x/2)
            lines = [f'WAYFARER 001 / IND-001 study 1.2-1.3: S004A greeting, {fig["title"]} and newcomer / fit-out {scheme} / DOCKED',
                     'instructor anchored on the deck band (fore up), newcomer head-first through the outer hatch | PROTOTYPE, identities open (Q49)',
                     'third-person study camera' if view == 'third' else "newcomer's point of view (camera up = fore, for readability)"]
            labels = label(scene, cam, lines, width, aspect, .25)
            scene.render.filepath = str(out/f'greeting_{scheme}_{key}_{view}.png'); bpy.ops.render.render(write_still=True)
            for o in labels:
                bpy.data.objects.remove(o, do_unlink=True)
            print(f'WF_INDUCTION_STUDY greeting {key} {view}', flush=True)
        for o in made:
            bpy.data.objects.remove(o, do_unlink=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--mode', choices=['turnaround', 'greeting'], required=True); p.add_argument('--scheme', default='D')
    p.add_argument('--instructors', nargs='+', default=['I1', *VARIANTS])
    p.add_argument('--size', type=int, default=640); p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    out = a.out if a.out.is_absolute() else ROOT/a.out; out.mkdir(parents=True, exist_ok=True)
    turnaround(out, 320) if a.mode == 'turnaround' else greeting(out, a.size, a.scheme, a.instructors)
