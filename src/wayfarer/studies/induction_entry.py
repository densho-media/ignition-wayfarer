"""IND-001 study (phase 1): the airlock vertical slice, rendered as side-by-side variants for the user to pick.

Opens the saved vehicle, poses DOCKED with both hatches open, hides the zone-1 mannequin and builds one route_fitout scheme at a time in a
scratch ART_STUDY collection, in memory only: nothing is saved and no asset changes. Each scheme repaints the entry chamber and trunk node
shells with its palette (depiction only) and renders the eye-level cameras, plus a colourless silhouette still without signage (Art Style
Architecture!A16: remove colour, signage, logos and inhabitants; the culture must still read). Palettes are PROTOTYPE depiction choices
from Culture 31_ARCHITECTURE and the Fashion/Art Style grammars, not canon.

    /snap/bin/blender -b --python src/wayfarer/studies/induction_entry.py -- --schemes A B C --out runs/<stamp>-induction
"""
from pathlib import Path
import argparse
import math
import sys
import bpy
from mathutils import Matrix, Vector
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation'), str(ROOT/'src/wayfarer/components')]
from common import material, pose_configuration, revolve_mesh
from spec import load
import human_entry as he
import route_fitout as rf
from fitout import arc_mesh, text_mesh
from entry_preview import label

# PROTOTYPE study variants (step 1.1). Depths in m; 0 omits the element. The pick (D) lives in [route_fitout].
SCHEMES = {
    'A': dict(title='Great Union order', lead='GREAT_UNION', frame_depth_m=.015, frame_width_m=.05, stringer_depth_m=.010,
              deck_band=True, placards='full', chase='closed', locker='closed', hatch_marks=False, handholds=True, vents=True),
    'B': dict(title='Bolt-Sworn maintenance-forward', lead='BOLT_SWORN', frame_depth_m=.045, frame_width_m=.07, stringer_depth_m=.035,
              deck_band=False, placards='plates', chase='open', locker='open', hatch_marks=False, handholds=True, vents=True),
    'C': dict(title='Minimal Spacer', lead='SPACER', frame_depth_m=.025, frame_width_m=.06, stringer_depth_m=0.0,
              deck_band=True, placards='minimal', chase='closed', locker='closed', hatch_marks=True, handholds=True, vents=True),
    # Section 13 layered: each grammar in its own domain (Spacer shell and frames, Great Union wayfinding and interfaces, Bolt-Sworn
    # exposed service), colour carrying meaning (greys structure, blue wayfinding, orange safety, line colours in the service chase only).
    'D': dict(title='Layered (section 13)', lead='SPACER + GREAT_UNION + BOLT_SWORN', frame_depth_m=.035, frame_width_m=.06, stringer_depth_m=.025,
              deck_band=True, placards='full', chase='open', locker='closed', hatch_marks=True, handholds=True, vents=True),
}


VIEWS = {'port_eye': 'CAM_HUM_ENTRY_PORT', 'mannequin_eye': 'CAM_HUM_ENTRY_EYE', 'node_eye': 'CAM_HUM_NODE'}
# PROTOTYPE depiction palettes (linear RGB). Keys: route_fitout paint keys plus the shell and the placard text.
PALETTES = {
    'A': dict(shell=(.86, .86, .84), frame=(.74, .76, .79), band=(.07, .16, .42), grille=(.30, .33, .36), placard=(.93, .94, .95),
              text=(.06, .14, .40), bezel=(.70, .73, .77), handle=(.76, .78, .82), cover=(.82, .83, .83), locker=(.90, .90, .88),
              safety=(.92, .40, .08), chase=(.10, .10, .11), tag=(.85, .70, .20)),
    'B': dict(shell=(.48, .50, .53), frame=(.13, .14, .16), band=(.18, .19, .21), grille=(.09, .09, .10), placard=(.17, .18, .20),
              text=(.85, .86, .80), bezel=(.20, .21, .23), handle=(.20, .21, .23), cover=(.30, .31, .33), locker=(.25, .26, .28),
              safety=(.92, .40, .08), chase=(.07, .07, .08), tag=(.85, .66, .18), pipe_air=(.55, .70, .85), pipe_water=(.20, .40, .66),
              pipe_power=(.85, .52, .12), bottle_o2=(.90, .90, .90), extinguisher=(.70, .08, .06)),
    'C': dict(shell=(.40, .42, .45), frame=(.22, .23, .25), band=(.16, .17, .19), grille=(.10, .10, .11), placard=(.15, .16, .17),
              text=(.93, .93, .93), bezel=(.21, .22, .24), handle=(.90, .38, .07), cover=(.34, .36, .38), locker=(.90, .38, .07),
              safety=(.92, .40, .08), chase=(.07, .07, .08), tag=(.85, .66, .18)),
    'D': dict(shell=(.62, .64, .66), frame=(.20, .21, .23), band=(.07, .16, .42), grille=(.12, .12, .13), placard=(.93, .94, .95),
              text=(.06, .14, .40), bezel=(.70, .73, .77), handle=(.90, .38, .07), cover=(.34, .36, .38), locker=(.90, .90, .88),
              safety=(.92, .40, .08), chase=(.07, .07, .08), tag=(.85, .66, .18), pipe_air=(.55, .70, .85), pipe_water=(.20, .40, .66),
              pipe_power=(.85, .52, .12)),
}
SHELLS = ('Dock_Primary_Entry_Chamber', 'Dock_Primary_Trunk_Node')


def obj_from(c, name, vs, fs, mat):
    data = bpy.data.meshes.new(name); data.from_pydata(vs, [], fs); data.update()
    obj = bpy.data.objects.new(name, data); c.objects.link(obj); data.materials.append(mat); return obj


def build(c, s, f, scheme, pal):
    """Scheme elements in collection c; returns {name: object} with signage objects flagged."""
    mats = {k: material(f'Study_{k}', v) for k, v in pal.items()}; made = {}
    for q in rf.elements(s, f, scheme):
        mat = mats.get(q['paint'], mats['frame'])
        if q['shape'] == 'arc':
            obj = obj_from(c, q['name'], *arc_mesh(f, q), mat)
        elif q['shape'] == 'box':
            obj = obj_from(c, q['name'], he.box_corners(f, q), [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)], mat)
        elif q['shape'] == 'ring':
            u, _ = he.axes(f); base = he.world(f, 0.0)
            obj = obj_from(c, q['name'], *revolve_mesh(base, tuple(base[i]+u[i] for i in range(3)), q['profile']), mat)
        elif q['shape'] in ('rod', 'cyl'):
            pts = q['points'] if q['shape'] == 'rod' else [q['a'], q['b']]
            data = bpy.data.curves.new(q['name'], 'CURVE'); data.dimensions = '3D'; data.bevel_depth = q['radius']; data.bevel_resolution = 3
            data.use_fill_caps = True; sp = data.splines.new('POLY'); sp.points.add(len(pts)-1)
            for p, co in zip(sp.points, pts):
                p.co = (*co, 1)
            obj = bpy.data.objects.new(q['name'], data); c.objects.link(obj); data.materials.append(mat)
        for key in ('layer', 'grammar', 'function', 'design_class', 'geometry_status'):
            obj[key] = q[key]
        obj['signage'] = q['signage']; made[q['name']] = obj
        if q.get('text'):
            made[q['name']+'_Text'] = text_mesh(c, f, q, mats['text']); made[q['name']+'_Text']['signage'] = True
    return made


def render(schemes, views, size, out):
    s, *_ = load(ROOT); f = he.ports(s)[0]
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
    scene = bpy.context.scene; pose_configuration(s, 'DOCKED')
    ctrl = bpy.data.objects['DOCK_ENTRY_CTRL']
    for which in ('outer', 'inner'):
        ctrl[f"{f['name']}_{which}_open"] = 1.0
    ctrl.update_tag(); scene.frame_set(scene.frame_current)
    for obj in bpy.data.objects:
        if obj.name.startswith('Human_Entry_'):
            obj.hide_render = True
    scene.render.resolution_x = size; scene.render.resolution_y = round(size*.75); scene.render.image_settings.file_format = 'PNG'
    scene.cycles.device = 'CPU'; scene.cycles.samples = 48; scene.cycles.use_denoising = True; scene.cycles.seed = 0
    scene.world.use_nodes = True; bg = next(n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = (.02, .025, .035, 1); bg.inputs['Strength'].default_value = .4
    out.mkdir(parents=True, exist_ok=True); aspect = scene.render.resolution_x/scene.render.resolution_y
    shells = {n: bpy.data.objects[n] for n in SHELLS}; original = {n: o.data.materials[0] for n, o in shells.items()}
    for key in schemes:
        scheme, pal = SCHEMES[key], PALETTES[key]
        fails = rf.check(s, f, scheme)
        if fails:
            raise ValueError(f'scheme {key}: {fails}')
        c = bpy.data.collections.new(f'ART_STUDY_FITOUT_{key}'); scene.collection.children.link(c)
        made = build(c, s, f, scheme, pal)
        for n, o in shells.items():
            o.data.materials[0] = material(f'Study_Shell_{key}', pal['shell'])
        head = f'WAYFARER 001 / IND-001 study 1.1: entry chamber fit-out, scheme {key}: {scheme["title"]} / DOCKED, hatches open'
        facts = f'lead grammar {scheme["lead"]} | {len(made)} elements | inside the existing walls, route clearance unchanged | PROTOTYPE depiction, not canon'
        for view in views:
            camera = bpy.data.objects[VIEWS[view]]; scene.camera = camera; scene.render.engine = 'CYCLES'
            width = 2*.25*math.tan(camera.data.angle_x/2)
            labels = label(scene, camera, [head, facts, camera.get('role', '')], width, aspect, .25)
            scene.render.filepath = str(out/f'fitout_{key}_{view}.png'); bpy.ops.render.render(write_still=True)
            for o in labels:
                bpy.data.objects.remove(o, do_unlink=True)
            print(f'WF_INDUCTION_STUDY {key} {view}', flush=True)
        # Silhouette test: one flat colour, no signage, no inhabitants.
        for o in made.values():
            o.hide_render = bool(o.get('signage'))
        scene.render.engine = 'BLENDER_WORKBENCH'; sh = scene.display.shading; sh.light = 'STUDIO'; sh.color_type = 'SINGLE'
        sh.single_color = (.8, .8, .8); sh.show_cavity = True; sh.show_shadows = True; sh.show_object_outline = False
        scene.camera = bpy.data.objects[VIEWS['port_eye']]; scene.render.filepath = str(out/f'fitout_{key}_silhouette.png')
        bpy.ops.render.render(write_still=True); print(f'WF_INDUCTION_STUDY {key} silhouette', flush=True)
        for o in list(c.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(c)
        for n, o in shells.items():
            o.data.materials[0] = original[n]


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--schemes', nargs='+', default=list(SCHEMES)); p.add_argument('--views', nargs='+', choices=list(VIEWS), default=list(VIEWS))
    p.add_argument('--size', type=int, default=640); p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    render(a.schemes, a.views, a.size, a.out if a.out.is_absolute() else ROOT/a.out)
