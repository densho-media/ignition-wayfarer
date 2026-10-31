"""Owner review file for the TODO modeling steps of project-thread-1ysr1f (owner brief 2026-10-30: "execute all the modeling steps"):
the built ship in the selected exterior grammar look, one Blender scene per step with its own framed cameras, made local and packed so the
file opens on the change with nothing to run. Review aid only: the vehicle is posed COAST and dressed in memory.

    /snap/bin/blender -b --python work/project-thread-1ysr1f/make_review.py -- --out work/project-thread-1ysr1f/REVIEW_PROJECT_THREAD_1YSR1F.blend [--render DIR]
"""
from pathlib import Path
import argparse
import math
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation')]

# scene: (title, [(camera name, view key)], note). View keys: p4_review frames/ring/blade cameras, p4_hero shots, or interior keys below.
CANDIDATES = [
    ('00_WHOLE_SHIP', 'Whole ship in the selected grammar (VC+ moderated)', [('ship_34', 'ship_34'), ('ship_side', 'ship_side')]),
    ('01_TORUS_BIPODS', 'F01: each torus support is a bipod to the forward collar (aft foot 5.6 m aft, forward foot 4.4 m forward of the torus '
                        'centre) instead of a radial strut that would bend at 4.9 GPa under thrust; worst leg 0.85 MN, +17 % buckling margin (PROTOTYPE)',
     [('torus_bipod', 'torus_bipod'), ('fuel_torus', 'fuel_torus')]),
]
SECTOR_VIEWS = {   # (pack object prefix, eye, focus, lens) in the sector frame (+X axial, +Y down, +Z tangential; deck y 0)
    'ra2_fab': ('Prod_RA2_WRK', (0.15, -1.6, -0.35), (1.25, -1.15, -1.95), 18.0),
    'rb2_fab': ('Prod_RB2_WRK', (0.15, -1.6, -0.35), (1.25, -1.15, -1.95), 18.0),
    'rb1_aisle': ('Prod_RB1_BRT', (-0.9, -1.6, -1.25), (1.0, -1.1, 1.3), 14.0),
    'rb2_ops': ('Prod_RB2_WRK', (0.6, -1.6, -0.6), (0.6, -1.25, 2.3), 14.0),
    'rb3_mess': ('Prod_RB3_GDN', (-1.05, -1.55, 1.79), (1.0, -0.95, 1.79), 14.0),
    'ra1_band': ('Prod_RA1_BRT', (-0.775, -1.6, -2.2), (-0.775, -1.0, 2.75), 16.0),
    'ra2_band': ('Prod_RA2_WRK', (-0.775, -1.6, 2.2), (-0.775, -1.0, -2.75), 16.0),
    'ra3_band': ('Prod_RA3_GDN', (-0.775, -1.6, -2.2), (-0.775, -1.0, 2.75), 16.0),
    'ra3_eclss4': ('Prod_RA3_GDN', (0.15, -1.5, -0.55), (1.16, -1.0, -1.5), 16.0),
    'ra3_eclss_top': ('Prod_RA3_GDN', (0.05, -1.25, -0.2), (1.16, -1.8, -1.5), 16.0),
    'rb3_eclss_top': ('Prod_RB3_GDN', (0.05, -1.25, -0.2), (1.16, -1.8, -1.5), 16.0),
    'rb3_eclss4': ('Prod_RB3_GDN', (0.15, -1.5, -0.55), (1.16, -1.0, -1.5), 16.0),
}


def world_objects(prefix):
    """World-space (object, matrix) for every object whose name starts with prefix, through collection instances."""
    import bpy
    out = []
    def walk(col, m):
        for o in col.objects:
            mw = m @ o.matrix_world
            if o.name.startswith(prefix):
                out.append((o, mw))
            if o.instance_type == 'COLLECTION' and o.instance_collection:
                walk(o.instance_collection, mw)
        for c in col.children:
            walk(c, m)
    from mathutils import Matrix
    walk(bpy.context.scene.collection, Matrix.Identity(4))
    return out


def bounds(prefix):
    from mathutils import Vector
    pts = [mw @ Vector(c) for o, mw in world_objects(prefix) for c in o.bound_box]
    if not pts:
        raise SystemExit(f'no objects named {prefix}*')
    lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi


def interior(key):
    """(focus, eye, lens, clip_start) for the interior candidates: an eye-level look at an overhead layer, a cut through a drum."""
    from mathutils import Vector
    if key in SECTOR_VIEWS:
        pre, eye, focus, lens = SECTOR_VIEWS[key]; mw = world_objects(pre)[0][1]
        up = (mw.to_3x3() @ Vector((0, -1, 0))).normalized()
        return mw @ Vector(focus), mw @ Vector(eye), lens, 0.05, up
    if key.startswith('ra3_'):
        # Standing eye (1.6 m) views in the sector frame (+X axial, +Y down, +Z tangential), mapped through the sector instance.
        mw = world_objects('Prod_RA3_GDN_Mess')[0][1]
        eye, focus, lens = {'ra3_mess': ((-1.05, -1.55, 1.79), (1.0, -0.95, 1.79), 14.0),
                            'ra3_rack': ((0.55, -1.6, -0.42), (0.55, -1.0, 0.75), 13.0),
                            'ra3_eclss': ((-0.35, -1.6, -0.25), (1.15, -1.15, -1.45), 17.0)}[key]
        up = (mw.to_3x3() @ Vector((0, -1, 0))).normalized()
        return mw @ Vector(focus), mw @ Vector(eye), lens, 0.05, up
    prefix = {'ra2': 'Prod_RA2', 'ra2_section': 'Prod_RA2', 'rb_xfr': 'Prod_RB_XFR', 'rb_spk': 'Prod_RB_SPK', 'rb_sec': 'Prod_RB_SEC'}[key]
    lo, hi = bounds(prefix); c = (lo+hi)/2
    if key == 'rb_xfr':
        # Axial cut through the drum (camera clipping, like preview.py hub_section_detail): from -Y, near half clipped away.
        d = 14.0
        return c, c+Vector((0, -d, 0.0)), 24.0, d-0.05, None
    radial = Vector((0, c.y, c.z)).normalized(); up = -radial
    tang = Vector((1, 0, 0)).cross(radial).normalized()
    if key == 'rb_spk':
        size = (hi-lo).length
        return c, c+tang*size*0.9+Vector((-size*0.5, 0, 0)), 24.0, 0.1, radial
    # Overhead layers: deck is 'down' = radially outward from the ship axis; the overhead band sits ~2.9 m above the deck.
    eye_h = 1.6-2.9    # eye 1.6 m above the deck, measured from the overhead band
    if key == 'ra2_section':
        # Axial cut through the middle of the sector (camera clipping): deck, fit-out and the overhead band in section.
        d = 12.0; mid = c+up*eye_h*0.5
        return mid, mid+Vector((d, 0, 0)), 50.0, d, up
    return c, c+up*eye_h+tang*2.0+Vector((0.6, 0, 0)), 14.0, 0.05, up


def garden_lights(col):
    """The sector is closed, so the sun never reaches it: area lights at the pack's daylight panels and grow-light bars, and a dim aisle fill.
    Presentation only (the production materials carry no emission)."""
    import bpy
    from mathutils import Vector
    mw = world_objects('Prod_RA3_GDN_Mess')[0][1]; down = (mw.to_3x3() @ Vector((0, 1, 0))).normalized()
    rot = down.to_track_quat('-Z', 'Y').to_euler()
    for name, at, size, watts, rgb in (('Daylight_1', (-0.275, -2.84, 1.80), (0.35, 0.70), 120, (1.0, .95, .86)),
                                       ('Daylight_2', (0.325, -2.84, 1.80), (0.45, 0.70), 120, (1.0, .95, .86)),
                                       ('Aisle_Fill', (0.0, -2.80, 0.0), (2.8, 0.8), 160, (.92, .95, 1.0)),
                                       ('ECLSS_Fill', (0.8, -2.80, -1.5), (0.6, 1.6), 80, (.92, .95, 1.0)),
                                       *[(f'Grow_{k}', (0.55, y+.02, 0.70), (1.9, 0.3), 25, (1.0, .70, .95))
                                         for k, y in enumerate((-1.95, -1.51, -1.06, -0.61))]):
        ld = bpy.data.lights.new(f'WORK_RA3_Light_{name}', 'AREA'); ld.shape = 'RECTANGLE'; ld.size, ld.size_y = size; ld.energy = watts; ld.color = rgb
        ob = bpy.data.objects.new(ld.name, ld); ob.location = mw @ Vector(at); ob.rotation_euler = rot; col.objects.link(ob)


def sector_lights(col, prefix):
    """Closed sector: area lights under the overhead band along the aisle (presentation only)."""
    import bpy
    from mathutils import Vector
    mw = world_objects(prefix)[0][1]; down = (mw.to_3x3() @ Vector((0, 1, 0))).normalized()
    rot = down.to_track_quat('-Z', 'Y').to_euler()
    for k, z in enumerate((-1.6, 0.0, 1.6)):
        ld = bpy.data.lights.new(f'WORK_{prefix}_Light_{k}', 'AREA'); ld.shape = 'RECTANGLE'; ld.size, ld.size_y = 1.8, 0.6; ld.energy = 140
        ld.color = (1.0, .95, .88); ob = bpy.data.objects.new(ld.name, ld); ob.location = mw @ Vector((0.6, -2.75, z)); ob.rotation_euler = rot
        col.objects.link(ob)


def fill_lights(col):
    """Presentation fill (labelled, not physical light): the torus sits in the Brow's shadow and the stations inside the hull, so the
    scene adds a soft fill sun from ahead-outboard and point lights along the body axis for the section views."""
    import bpy
    from mathutils import Vector
    sd = bpy.data.lights.new('WORK_FUEL_Fill_Sun', 'SUN'); sd.energy = 1.5; sd.angle = 0.3
    so = bpy.data.objects.new(sd.name, sd); so.rotation_euler = Vector((-0.4, 0.6, -0.7)).to_track_quat('-Z', 'Y').to_euler(); col.objects.link(so)
    for x in (-64, -50, -30, -10, 10, 30, 50):
        for deg in (90, 45):
            ld = bpy.data.lights.new(f'WORK_FUEL_Fill_{x}_{deg}', 'POINT'); ld.energy = 6000; ld.shadow_soft_size = 1.0; ld.use_shadow = False
            ob = bpy.data.objects.new(ld.name, ld); a = math.radians(deg); ob.location = (x, 5.9*math.cos(a), 5.9*math.sin(a)); col.objects.link(ob)
    for name, x, r, deg, watts in (('EVA_1', 99.0, 9.0, 55, 3000), ('EVA_2', 104.5, 9.0, 45, 3000), ('Torus', 100.6, 40.0, 300, 60000),
                                   ('H02_1', 104.0, 14.0, 37, 20000), ('H02_2', 103.0, 27.0, 37, 20000),
                                   ('Brow_1', 100.0, 24.0, 70, 40000), ('Brow_2', 106.0, 22.0, 90, 8000)):
        ld = bpy.data.lights.new(f'WORK_FILL_{name}', 'POINT'); ld.energy = watts; ld.use_shadow = False
        ob = bpy.data.objects.new(ld.name, ld); a = math.radians(deg); ob.location = (x, r*math.cos(a), r*math.sin(a)); col.objects.link(ob)


def main(out, render=None, only=()):
    import bpy
    from mathutils import Vector
    from common import pose_configuration
    from spec import load
    import hero_preview as hp
    import production_detail as pd
    import p4_review as pr
    import p4_hero as ph
    from m8_exterior import sun_vector
    s = load(ROOT)[0]; pd.load_packs()
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
    base = bpy.context.scene
    pose_configuration(s, 'COAST'); base.frame_set(base.frame_current)
    hp.dress(s, functional=True, emit=False, grammar=True, wear=False); x = s['look']['exterior']
    # Lights' look pass ([look.lights]): the exterior strobes and approach lights and the Garden/mess panels emit by their class.
    import look as _look
    for m in bpy.data.materials:
        q = _look.lights(s).get(m.name[7:].split('.')[0]) if m.name.startswith('WF_MAT_') and m.use_nodes else None
        if q and q['cls'] in ('daylight', 'grow', 'beacon', 'approach'):
            n = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
            n.inputs['Base Color'].default_value = (*q['color'], 1); n.inputs['Emission Color'].default_value = (*q['color'], 1)
            n.inputs['Emission Strength'].default_value = q['strength']
    # Cameras need the posed world before anything is made local.
    sv = sun_vector(*pr.SUN); fr = pr.frames(s); w = pr.rotor_world(1); sg = pr.ring_aft_sign(); tc = pr.clear_sector(s, w)
    rc = pr.ring_cameras(s, tc); bc = pr.blade_cameras(s, sv); hc = ph.cameras(s)
    aspect = 16/9
    shots = {}
    for _, _, cams in CANDIDATES:
        for _, key in cams:
            if key in fr:
                shots[key] = ('fit', fr[key])
            elif key in rc:
                eye, tgt, lens = rc[key]
                shots[key] = ('eye', (w @ Vector((tgt.x*sg, tgt.y, tgt.z)), w @ Vector((eye.x*sg, eye.y, eye.z)), lens, .1))
            elif key in bc:
                eye, tgt, lens = bc[key]; shots[key] = ('eye', (tgt, eye, lens, .1))
            elif key in hc:
                shots[key] = ('fit', hc[key])
            elif key.startswith('nav_'):
                rad = lambda x, r, deg: Vector((x, r*math.cos(math.radians(deg)), r*math.sin(math.radians(deg))))
                shots[key] = {'nav_close': ('eye', (rad(20, 6.6, 330), rad(17.0, 9.8, 348), 30.0, .05)),
                              'nav_body': ('eye', (rad(20, 6, 330), rad(-6, 24, 350), 30.0, .1))}[key]
            elif key == 'torus_bipod':
                import fuel_storage as _fst
                st = next(q for q in _fst.torus_struts(s) if q['name'] == 'Fuel_Torus_Strut_1_1_Aft'); a = st['azimuth']
                rv = Vector((0, math.cos(a), math.sin(a))); tv = Vector((0, -math.sin(a), math.cos(a)))
                focus = Vector((100.3, 0, 0))+rv*11.5
                shots[key] = ('eye', (focus, focus+tv*30.0, 30.0, 21.0, rv))
            elif key.startswith('fuel_'):
                rad = lambda x, r, deg: Vector((x, r*math.cos(math.radians(deg)), r*math.sin(math.radians(deg))))
                Z = Vector((0, 0, 1))
                shots[key] = {'fuel_torus_axial': ('eye', (Vector((100.6, 0, 0)), Vector((160, 0, 0)), 22.0, 59.4, Vector((0, 0, 1)))),
                              'fuel_torus': ('eye', (Vector((100.6, 0, 0)), rad(100.6, 64, 300), 20.0, 27.0, Vector((1, 0, 0)))),
                              'fuel_gap': ('eye', (rad(100.6, 18, 195), rad(118, 50, 205), 28.0, .3, Z)),
                              'fuel_slot': ('eye', (rad(84, 18, 36), rad(62, 52, 50), 28.0, .3, Z)),
                              # body section: the camera clips through the hull skin and casing to show the stations
                              'fuel_body': ('eye', (rad(-2, 0, 90), rad(-2, 30, 90), 14.0, 23.7, Vector((0, 0, -1)))),
                              'fuel_aft': ('eye', (rad(-60, 0, 45), rad(-48, 30, 45), 22.0, 23.6, Vector((0, 1, -1)).normalized()))}[key]
            elif key in ('brow_fix', 'brow_fix_close'):
                rad = lambda x, r, deg: Vector((x, r*math.cos(math.radians(deg)), r*math.sin(math.radians(deg))))
                shots[key] = {'brow_fix': ('eye', (rad(109.5, 26, 80), rad(84, 40, 55), 26.0, .3, Vector((1, 0, 0)))),
                              'brow_fix_close': ('eye', (rad(110.8, 23, 92), rad(104.5, 26, 80), 30.0, .1, Vector((1, 0, 0))))}[key]
            elif key == 'ring_portal':
                mw = world_objects('Ring_1_Fill_1')[0][1]; tn = 1.047; r = 27.1
                lp = lambda u, rr, tt: mw @ Vector((u, rr*math.cos(tt), rr*math.sin(tt)))
                up = (mw.to_3x3() @ Vector((0, -math.cos(tn), -math.sin(tn)))).normalized()
                shots[key] = ('eye', (lp(-0.8, r, tn-0.10), lp(-9.0, r, tn-0.10), 20.0, 7.45, up))
            elif key in ('cmg_fwd', 'cmg_aft', 'body_long', 'thrust_aft'):
                rad = lambda x, r, deg: Vector((x, r*math.cos(math.radians(deg)), r*math.sin(math.radians(deg))))
                shots[key] = {'cmg_fwd': ('eye', (rad(17, 2.0, 90), rad(23, 22, 120), 22.0, 16.8, Vector((1, 0, 0)))),
                              'cmg_aft': ('eye', (rad(-21, 2.0, 210), rad(-15, 22, 240), 22.0, 16.8, Vector((1, 0, 0)))),
                              'body_long': ('eye', (rad(-2, 0, 90), rad(-2, 30, 90), 14.0, 23.7, Vector((0, 0, -1)))),
                              'thrust_aft': ('eye', (Vector((-103, 0, 0)), rad(-118, 14, 60), 24.0, .3, Vector((1, 0, 0))))}[key]
            else:
                shots[key] = ('eye', interior(key))
    # Make every linked datablock local so the file is self-contained, then pack images.
    bpy.ops.object.make_local(type='ALL')
    left = [i.name for c in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.collections, bpy.data.node_groups) for i in c if i.library]
    if left:
        raise SystemExit(f'still linked: {left[:10]}')
    for lib in list(bpy.data.libraries):
        bpy.data.libraries.remove(lib)
    # Shared render settings and sun on the base scene; the other scenes link the base scene's collections.
    base.render.engine = 'BLENDER_EEVEE'; base.render.resolution_x = 1920; base.render.resolution_y = 1080
    base.view_settings.view_transform = 'AgX'; base.view_settings.exposure = x['exposure_ev']+2.0
    base.world.use_nodes = True; bg = next(n for n in base.world.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = (0, 0, 0, 1); bg.inputs['Strength'].default_value = 0.0
    sun = bpy.data.lights.new('REVIEW_Sun', 'SUN'); sun.energy = x['sun_strength']; sun.angle = math.radians(x['sun_angular_deg'])
    so = bpy.data.objects.new(sun.name, sun); so.rotation_euler = (-sv).to_track_quat('-Z', 'Y').to_euler()
    shared = list(base.collection.children); loose = list(base.collection.objects)
    base_name = base.name
    for i, (name, title, cams) in enumerate(CANDIDATES):
        sc = base if i == 0 else bpy.data.scenes.new(name)
        if i:
            for c in shared:
                sc.collection.children.link(c)
            for o in loose:
                sc.collection.objects.link(o)
            sc.world = base.world; sc.render.engine = base.render.engine
            sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
            sc.view_settings.view_transform = 'AgX'; sc.view_settings.exposure = base.view_settings.exposure
        else:
            sc.name = name
        sc.collection.objects.link(so)
        wc = bpy.data.collections.new(f'WORK_{name}'); sc.collection.children.link(wc); wc.color_tag = 'COLOR_06'
        if name == '09_RA3_GARDEN':
            garden_lights(wc)
        if name in ('01_BROW_FIXTURES', '03_RING_PORTALS'):
            fill_lights(wc)
        if name == '01_DOOR_BAND':
            for pre in ('Prod_RA1_BRT', 'Prod_RA2_WRK', 'Prod_RA3_GDN'):
                sector_lights(wc, pre)
        if name == '01_TORUS_BIPODS':   # the section faces forward, away from the sun: a soft key light from the camera side
            ld = bpy.data.lights.new('REVIEW_TorusKey', 'SUN'); ld.energy = 4.0; ld.angle = math.radians(20)
            lo = bpy.data.objects.new(ld.name, ld); lo.rotation_euler = (math.radians(35), math.radians(80), 0); wc.objects.link(lo)
        if name == '02_ECLSS_LINES':
            garden_lights(wc); sector_lights(wc, 'Prod_RB3_GDN')
        first = None
        for cname, key in cams:
            cd = bpy.data.cameras.new(f'CAM_{cname}'); cam = bpy.data.objects.new(cd.name, cd); wc.objects.link(cam)
            kind, v = shots[key]
            if kind == 'fit':
                a, b, corners, lens = v; hp.place(cam, a, b, corners, lens, aspect)
                if corners is None:
                    cd.clip_start = .1
            else:
                focus, eye, lens, clip = v[:4]; hp.place(cam, focus, eye, None, lens, aspect); cd.clip_start = clip
                if len(v) > 4 and v[4] is not None:
                    # Roll so the picture's up is the local 'up' (toward the ring axis inside a rotating sector).
                    fwd = (focus-eye).normalized(); upv = (v[4]-fwd*v[4].dot(fwd)).normalized(); right = fwd.cross(upv)
                    from mathutils import Matrix
                    cam.rotation_euler = Matrix((right, upv, -fwd)).transposed().to_euler()
            cd.sensor_fit = 'HORIZONTAL'
            first = first or cam
        sc.camera = first
        note = bpy.data.texts.new(f'README_{name}')
        note.write(f'{title}\n\nOpens through CAM_{cams[0][0]}. Other cameras of this scene are in WORK_{name}: select one, '
                   'View > Cameras > Set Active Object as Camera (Ctrl+Numpad 0). Switch candidates with the scene selector (top right).\n'
                   'Every candidate stays L4_VISUAL_CANDIDATE until you accept it. Depiction only: no physics-locked value changed.\n')
    bpy.data.texts.new('README_REVIEW').write(
        'WAYFARER 001: pass 6 review (2026-10-31)\n\n'
        + '\n'.join(f'{n}: {t}' for n, t, _ in CANDIDATES)
        + '\n\nAnswer per candidate: accept, revise (what), or reject.\n')
    # Viewports: material preview, looking through the scene camera.
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == 'VIEW_3D':
                for sp in area.spaces:
                    if sp.type == 'VIEW_3D':
                        sp.shading.type = 'MATERIAL'; sp.shading.use_scene_lights = True; sp.clip_start = 0.05; sp.clip_end = 5000
                        sp.region_3d.view_perspective = 'CAMERA'
    for wm in bpy.data.window_managers:
        for win in wm.windows:
            win.scene = bpy.data.scenes[CANDIDATES[0][0]]
    bpy.context.window_manager  # noqa
    bpy.ops.file.pack_all()
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True, relative_remap=False)
    print('WF_REVIEW_SAVED', out, [sc.name for sc in bpy.data.scenes], 'libraries', len(bpy.data.libraries), flush=True)
    if render:
        render.mkdir(parents=True, exist_ok=True)
        for sc in bpy.data.scenes:
            sc.render.engine = 'BLENDER_EEVEE'; sc.eevee.taa_render_samples = 16
            sc.render.resolution_x, sc.render.resolution_y = 960, 540
            for cam in [o for c in sc.collection.children if c.name.startswith('WORK_') for o in c.objects if o.type == 'CAMERA'
                        and (not only or o.name[4:] in only)]:
                sc.camera = cam; sc.render.filepath = str(render/f'{sc.name}__{cam.name}.png')
                bpy.ops.render.render(write_still=True, scene=sc.name)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); ap.add_argument('--render', type=Path); ap.add_argument('--only', nargs='*', default=[])
    a = ap.parse_args(argv); main(a.out.resolve(), a.render.resolve() if a.render else None, set(a.only))
