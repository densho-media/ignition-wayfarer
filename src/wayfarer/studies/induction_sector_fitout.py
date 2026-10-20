"""IND-001 study (step 3.2): the cultural fit-out of ring A's three sectors, rendered side by side for the user to pick.

Two schemes over the human-scale whitebox, both carrying fit-out D's grammar per domain (route_fitout.sector_elements):
- A "Layered": Spacer overhead frames and ventilation, Great Union route band and room placards, Bolt-Sworn service lines on the service
  block's face (hygiene, workbench, life-support bay) and a tool rail.
- B "Service spine": A plus an exposed utility spine along the overhead (Robocracy, Systemize: maintenance access defines the layout), duct,
  cable tray and lines, dropping to each sector's service block.
And Seraph's space (12A SP-31, route_fitout.seraph_elements) two ways: Sa 'post', the first operations station as Seraph's work post and dock;
Sb 'berth', an outer-column berth as Seraph's docked berth. Seraph is a generic envelope here (its chassis is Q49(c) and step 3.3).

Each sector is drawn on the shared sector component (WF_RING_SECTOR, with the landing and its fit-out) with its whitebox furniture, review
mannequins and the scheme's elements, and seen from its induction stop camera (human_entry.induction_stations). A colourless still without
signage or people is the Art Style silhouette test (Architecture!A16). A screen keeps every element out of the aisle, the access strips, the
couches' free strips and the landing well below the overhead zone (route_fitout.sector_check). Nothing is saved. Picked 2026-10-07:
A and Sa, now the [route_fitout] defaults built with each interior.

    /snap/bin/blender -b --python src/wayfarer/studies/induction_sector_fitout.py -- --out runs/<stamp>-induction-sector-fitout
"""
from pathlib import Path
import argparse
import json
import math
import sys
import bmesh
import bpy
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation'), str(ROOT/'src/wayfarer/components')]
from common import material
from spec import load
import habitat_interior as hi
import human_entry as he
import route_fitout as rf
import sector_whitebox as sw
import fitout
from interior_preview import frame
from entry_preview import label
from interior import COLORS

SCHEMES = {'A': dict(title='Layered', frame_pitch_m=0.70, spine=False), 'B': dict(title='Service spine', frame_pitch_m=0.70, spine=True)}
STOPS = {'HABITATION': 'habitat', 'LIFE_SUPPORT_GARDEN_COMMON': 'garden', 'WORK_MEDICAL_OPS': 'specialists'}


def rod(c, name, pts, r, mat):
    data = bpy.data.curves.new(name, 'CURVE'); data.dimensions = '3D'; data.bevel_depth = r; data.bevel_resolution = 3; data.use_fill_caps = True
    sp = data.splines.new('POLY'); sp.points.add(len(pts)-1)
    for p, co in zip(sp.points, pts):
        p.co = (*co, 1)
    obj = bpy.data.objects.new(name, data); c.objects.link(obj); data.materials.append(mat); return obj


def box(c, name, lo, hi_, mat):
    vs = [(x, y, z) for x in (lo[0], hi_[0]) for y in (lo[1], hi_[1]) for z in (lo[2], hi_[2])]
    fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs)
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()   # outward normals
    me.update(); me.materials.append(mat)
    obj = bpy.data.objects.new(name, me); c.objects.link(obj); return obj


def seraph_figure(s, meta):
    """A generic envelope for Seraph (not a chassis design): standing at its post facing the console, or lying in its berth's cradle."""
    H = s['prototype']['human_height_m']
    if 'stand' in meta:
        (x0, _, z0), f = meta['stand'], meta['face']; a = (-f[2], 0, f[0])
        at = lambda x, y, z: (x0+x*a[0]+y*f[0], -z, z0+x*a[2]+y*f[2])
        th = s['sector_whitebox']['table_height_m']
        return sw.rods(at, H, {'Desk_1': at(-.18, .42, th+.03), 'Desk_2': at(.18, .42, th+.03)})[0]
    (x0, y0, z0), d = meta['lie']
    lie = lambda t, up=0.0: (x0+d[0]*t, y0-up, z0)
    return [('Torso', [lie(.38*H), lie(.78*H)], .13), ('Head', [lie(H-.20), lie(H-.11)], .11), ('Leg_1', [lie(.07), lie(.40*H)], .07),
            ('Arm_1', [lie(.75*H), lie(.45*H, .12)], .055)]


def render(out, size, views):
    s, *_ = load(ROOT); sec = hi.section(s); out.mkdir(parents=True, exist_ok=True); report = {}
    bpy.ops.wm.read_factory_settings(use_empty=True); scene = bpy.context.scene
    with bpy.data.libraries.load(str(ROOT/'assets/wayfarer/components/WF_RING_SECTOR.blend'), link=True) as (_, dst):
        dst.collections = ['WF_RING_SECTOR']
    inst = bpy.data.objects.new('Study_Sector', None); inst.instance_type = 'COLLECTION'; inst.instance_collection = dst.collections[0]
    scene.collection.objects.link(inst)
    scene.render.engine = 'BLENDER_WORKBENCH'; scene.render.resolution_x = size; scene.render.resolution_y = round(size*.75)
    scene.render.image_settings.file_format = 'PNG'; sh = scene.display.shading
    sh.light = 'FLAT'; sh.cavity_type = 'BOTH'; sh.show_cavity = True; sh.show_object_outline = True; sh.cavity_ridge_factor = 1.5; sh.cavity_valley_factor = 1.5; sh.show_shadows = False     # the skin would shadow the whole overhead
    scene.world = bpy.data.worlds.new('W'); scene.world.color = (.05, .06, .08); sh.background_type = 'WORLD'
    cam = bpy.data.objects.new('Study_Camera', bpy.data.cameras.new('Study_Camera')); scene.collection.objects.link(cam); scene.camera = cam
    cam.data.lens = s['human_entry']['mannequin']['camera_lens_mm']; cam.data.clip_start = .05; cam.data.clip_end = 100
    aspect = scene.render.resolution_x/scene.render.resolution_y; human = material('Study_Human', (1.0, .45, .05)); seraph = material('Study_Seraph', (.42, .62, .86))
    crop, rack = material('Study_Crop', COLORS['garden']), material('Study_Garden_Rack', (.74, .76, .72))
    dark = material('Study_Console', (.16, .19, .23)); strap = material('Study_Strap', (.85, .62, .12))
    plate_mat = {z: material(f'Interior_{z.title()}', COLORS[z]) for z in ('deck', 'overhead')}
    stations = he.induction_stations(s)
    for view in views:
        key, fn, sil, where = view['scheme'], view['function'], view.get('silhouette', False), view.get('seraph')
        c = bpy.data.collections.new('ART_STUDY'); scene.collection.children.link(c)
        els = rf.sector_elements(s, fn, SCHEMES[key])+rf.sector_sign(s, fn); extra, meta = rf.seraph_elements(s, fn, where) if where else ([], {})
        fails = rf.sector_check(s, fn, els+extra); report[view['name']] = dict(scheme=key, function=fn, seraph=where, elements=len(els+extra), screen=fails)
        for b in hi.plates(s):
            box(c, b['name'], b['min'], b['max'], plate_mat[b['zone']])
        blocks = hi.zones(s, fn); recess = rf.service_recess(s, fn)
        for b in blocks:
            for q in sw.shapes(s, b):
                if recess and b['name'] == recess[0]:     # the service block's open face recessed (Bolt-Sworn exposure)
                    lo, hi_ = list(q['min']), list(q['max']); _, k, at, at_max = recess
                    if at_max:
                        hi_[k] = min(hi_[k], at)
                    else:
                        lo[k] = max(lo[k], at)
                    q = dict(q, min=tuple(lo), max=tuple(hi_))
                if q['part'] in meta.get('drop', []) and b['name'] == meta['block']:
                    continue
                mat = (crop if q['part'].startswith('Crop') else rack if b['zone'] == 'garden' else dark if q['part'].startswith(('Console', 'Display'))
                       else strap if q['part'].startswith(('Strap', 'Lap_Belt')) else material(f'Interior_{b["zone"].title()}', COLORS.get(b['zone'], (.6, .6, .6))))
                box(c, q['name'], q['min'], q['max'], mat)
        made = fitout.build(c, els+extra)
        people = []
        if not sil:
            for pose, fg in sw.figures(s, blocks).items():
                people += [rod(c, f'Human_{pose}_{n}', pts, rr, human) for n, pts, rr in fg['rods']]
            if meta:
                people += [rod(c, f'Seraph_{n}', pts, rr, seraph) for n, pts, rr in seraph_figure(s, meta)]
        else:
            for o in made:
                o.hide_render = bool(o.get('signage'))
        sh.color_type = 'SINGLE' if sil else 'MATERIAL'; sh.single_color = (.72, .72, .72)
        envelope = bpy.data.objects.get('Sector_Pressure_Envelope')
        cam.data.lens = view.get('lens', s['human_entry']['mannequin']['camera_lens_mm'])
        if view.get('camera'):
            at, look = view['camera']
        else:
            q = stations[STOPS[fn]]; at, look = q['camera'], q['look']
        cam.location = Vector(at); cam.rotation_euler = frame(Vector(look)-Vector(at), (0, -1, 0))
        for o in [o for o in scene.objects if o.name.startswith('Preview_Label')]:
            bpy.data.objects.remove(o, do_unlink=True)
        width = 2*.25*math.tan(cam.data.angle_x/2)
        title = (f"WAYFARER 001 / IND-001 3.2 study: {key} {SCHEMES[key]['title']}" + (f", Seraph {'Sa post' if where == 'post' else 'Sb berth'}" if where else '')
                 + f" / {fn.replace('_', ' ')}")
        note = ('silhouette test: no colour, signage or people | ' if sil else '') + ('screen passes' if not fails else f'{len(fails)} screen failures') + ' | PROTOTYPE, not canon'
        label(scene, cam, [title, view['caption'], note], width, aspect, .25, dark=True)
        scene.render.filepath = str(out/f"{view['name']}.png"); bpy.ops.render.render(write_still=True)
        print(f"WF_SECTOR_FITOUT {view['name']}", flush=True)
        for o in list(c.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(c)
    (out/'sector_fitout_screens.json').write_text(json.dumps(report, indent=1)+'\n')


AISLE = ((-1.25, -1.55, 0.0), (1.75, -2.45, 0.0))     # eye at the aft end of the aisle, looking fore and a little up (overhead and both sides)


def views():
    out = []
    for key in SCHEMES:
        for fn in ('HABITATION', 'LIFE_SUPPORT_GARDEN_COMMON', 'WORK_MEDICAL_OPS'):
            out.append(dict(name=f'{key}_{fn.lower()}', scheme=key, function=fn, camera=AISLE, lens=14.0,
                            caption='eye at the aft end of the aisle looking fore, 14 mm (side +1 left, the service block forward on the right)'))
        out.append(dict(name=f'{key}_silhouette', scheme=key, function='LIFE_SUPPORT_GARDEN_COMMON', silhouette=True, camera=AISLE, lens=14.0,
                        caption='eye at the aft end of the aisle looking fore, 14 mm'))
    out.append(dict(name='Sa_post', scheme='A', function='WORK_MEDICAL_OPS', seraph='post', caption="Seraph at its post: from the 'specialists' stop camera"))
    out.append(dict(name='Sb_berth', scheme='A', function='HABITATION', seraph='berth', camera=((-1.10, -1.25, 1.75), (0.60, -0.55, 1.95)),
                    caption='Seraph in its berth: from the sub-aisle by the couch lockers, looking fore into Bunk_4'))
    return out


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--size', type=int, default=640); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--views', nargs='+')
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    out = a.out if a.out.is_absolute() else ROOT/a.out
    render(out, a.size, [v for v in views() if not a.views or v['name'] in a.views])
