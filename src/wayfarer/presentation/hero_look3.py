"""FUT-003-LOOK (S&E 15!A131, 2026-10-11): an engineering-grounded comparison for the owner's review of the First Ignition exterior stills.
The owner has not inspected the six stills (final aesthetics UNAPPROVED). Asked for: keep the actual sun and the outward burn attitude;
test a separately LABELLED illustrative fill in a non-diegetic concept view, or a separate off-burn orientation, never a fake sunward
burn; a camera azimuth that shows the three radiator blades distinctly; a strict-physical, EYE-dark shot. No invented exhaust, field glow
or mission-state claim (15!G131).

Reuses presentation/hero_preview.py (the same dress, sun, grey, hot face and captions); renders in memory, saves nothing:
- `tq_physical`  three-quarter at the blade-separating azimuth (scored here), strict physical light (the hero_preview look);
- `tq_fill`      the same camera with an ILLUSTRATIVE FILL light, labelled as not physical;
- `eye_physical` the Brow and EYE from ahead, strict physical: the forward face lies in its own shadow during the outward burn;
- `eye_fill`     the same with the labelled illustrative fill (non-diegetic concept view);
- `eye_offburn`  a separate off-burn orientation: COAST, the sun 30 deg off the nose (that attitude is OPEN), hot face off, labelled.
LOOK-005 next pass (M4, 2026-10-14), the same strict physical light, functional-mark variant (look.exterior.functional_materials):
- `tq_functional`    the tq_physical camera with the functional marks in colour (the controlled comparison against the all-grey tq_physical);
- `asm_shield_rear`  the shield rear face at the sun-side Crown bay: gussets, partition ribs, a service hatch, a 1.8 m figure;
- `asm_ring`         ring A's rim over a pressurized crew segment (amber band, joints, service covers), a 1.8 m figure;
- `asm_roots`        the sun-side blade's datum root: casing boots, chase plate, saddles, a 1.8 m figure.

    /snap/bin/blender -b --python src/wayfarer/presentation/hero_look3.py -- [--size 1280] [--samples 64] [--out-dir runs/renders/p1/hero_look3]
"""
from pathlib import Path
import argparse
import json
import math
import sys
import bpy
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation')]
from common import pose_configuration
from spec import load
import drive_manifold
import forward_shield
import hero_preview as hp

VIEWS = ('tq_physical', 'tq_fill', 'alt_physical', 'eye_physical', 'eye_fill', 'eye_offburn', 'tq_functional', 'asm_shield_rear', 'asm_ring', 'asm_roots')
FUNCTIONAL = ('tq_functional', 'asm_shield_rear', 'asm_ring', 'asm_roots')      # LOOK-005 next pass: functional marks keep their colour
SCALE = 'orange 1.8 m figure: NON-DIEGETIC scale reference'
STATUS = 'LOOK-004 (15!A140): WORKING CAMERA CHOICE / FINAL SIGNOFF OPEN'
ESTABLISHING = (-.62, -1.0, -.30)                 # the establishing still's view direction, kept as the alternative angle
FILL = 'ILLUSTRATIVE FILL - NOT PHYSICAL (a non-diegetic light added for the concept view; no such light exists at First Ignition)'


def blade_azimuths(s):
    p = s['prototype']['radiator_phase_deg']; n = s['radiators']['count']; return [(p+360.0*k/n) % 360 for k in range(n)]


def blade_score(s, d):
    """How distinctly the three blades read from view direction d (focus to camera). Each blade is a sheet in the plane of X and its
    radial: `face` is the smallest |cos| between d and a blade normal (0 = a blade edge-on); `spread` the smallest angle between two
    blades' radial directions projected on the image (120 deg = a perfect three-way fan, 0 = two blades on top of each other). The
    score is the weaker of the two, each against its best possible value (0.5 and 120 deg)."""
    d = d.normalized(); face = []; proj = []
    for b in blade_azimuths(s):
        a = math.radians(b); n = Vector((0.0, -math.sin(a), math.cos(a))); r = Vector((0.0, math.cos(a), math.sin(a)))
        face.append(abs(n.dot(d))); p = r-d*r.dot(d); proj.append(p.normalized() if p.length > 1e-6 else p)
    spread = min(math.degrees(proj[i].angle(proj[j])) for i in range(len(proj)) for j in range(i+1, len(proj)))
    return min(min(face)/.5, spread/120.0), dict(face=round(min(face), 3), spread_deg=round(spread, 1))


def tq_direction(s):
    """The three-quarter direction: aft of the ship (the establishing shot's thrust-axis diagonal), on the sun side (the hero stills look
    from the sun's side), azimuth and elevation scanned in 5 deg steps for the best blade score."""
    x = s['look']['exterior']; old = Vector(ESTABLISHING); best = None
    for k in range(72):
        a = math.radians(5.0*k)
        if math.cos(a-math.radians(x['sun_azimuth_deg'])) < 0.3:              # keep the camera on the sunlit side
            continue
        for el in range(10, 75, 5):                                         # angle of the view direction off the ship axis (from aft)
            e_ = math.radians(el); d = Vector((-math.cos(e_), math.sin(e_)*math.cos(a), math.sin(e_)*math.sin(a))); sc, det = blade_score(s, d)
            if best is None or sc > best[0]+1e-9:
                best = (sc, 5.0*k, d, el, det)
    o, det = blade_score(s, old)
    return best, (o, round(math.degrees(math.atan2(old.z, old.y)) % 360, 1), det)


def eye_frame(s):
    """Ahead of the Brow, a little off axis toward the sun side: the EYE facets and wells, the Lance, the dark forward face."""
    fs = forward_shield.stations(s); x = s['look']['exterior']; z = math.radians(x['sun_azimuth_deg'])
    focus = Vector((fs['face'], 0, 0)); d = Vector((1.0, .32*math.cos(z), .32*math.sin(z)))
    R = 6.0; corners = [focus+Vector((dx, dy, dz)) for dx in (-4, fs['lance_tip']-fs['face']) for dy in (-R, R) for dz in (-R, R)]
    return focus, d, corners, 50.0


def fill_light(scene, camera, distance, irradiance=1.5):
    """A large soft area light beside the camera: obviously a studio fill, strength set to lift the shadowed face to a mid grey."""
    L = bpy.data.lights.new('Illustrative_Fill', 'AREA'); L.shape = 'DISK'; L.size = max(20.0, distance*.4); L.energy = irradiance*math.pi*distance**2   # on-axis irradiance in sun-strength units (the sun is 3)
    o = bpy.data.objects.new(L.name, L); scene.collection.objects.link(o)
    o.location = camera.location+camera.matrix_world.to_3x3()@Vector((distance*.25, distance*.15, 0)); o.rotation_euler = camera.rotation_euler
    return o


def sun_unit(s):
    a = math.radians(s['look']['exterior']['sun_azimuth_deg']); return Vector((0.0, math.cos(a), math.sin(a)))


def figure(scene, foot, up):
    """Non-diegetic 1.8 m scale figure (a capsule) standing on `foot` along `up`."""
    h = 1.8; bpy.ops.mesh.primitive_cylinder_add(radius=.22, depth=h-.44, location=(0, 0, 0)); body = bpy.context.active_object
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.22, location=(0, 0, h/2-.22+.0)); head = bpy.context.active_object
    m = bpy.data.materials.new('Look_Scale_Figure'); m.use_nodes = True
    n = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'); n.inputs['Base Color'].default_value = (1.0, .45, .1, 1)
    q = Vector((0, 0, 1)).rotation_difference(up.normalized())
    for o, off in ((body, (h-.44)/2), (head, h-.22)):
        o.data.materials.append(m); o.rotation_euler = q.to_euler(); o.location = foot+up.normalized()*off; o['kind'] = 'look_scale_figure'


def ring_band(s):
    """World centroid of ring A's pressure-segment band nearest the sun side, its outward radial and the ring axis X."""
    deps = bpy.context.evaluated_depsgraph_get(); sun = sun_unit(s); xa = min(__import__('habitat_ring').centers(s)); best = None
    for inst in deps.object_instances:
        o = inst.object
        if o.type != 'MESH' or not any(m and m.name.startswith('WF_MAT_RingPressureBand') for m in o.data.materials):
            continue
        idx = [i for i, m in enumerate(o.data.materials) if m and m.name.startswith('WF_MAT_RingPressureBand')]
        me = o.data; mw = inst.matrix_world
        for poly in me.polygons:
            if poly.material_index not in idx:
                continue
            c = mw @ poly.center
            if abs(c.x-xa) > 3:
                continue
            r = Vector((0, c.y, c.z)).normalized(); k = r.dot(sun)
            if best is None or k > best[0]:
                best = (k, c.copy(), r)
    return best[1], best[2]


def asm_frame(s, name):
    """focus, direction (focus to camera), corners, lens, figure foot and up for an assembly view."""
    sun = sun_unit(s); X = Vector((1, 0, 0))
    if name == 'asm_shield_rear':
        cr = forward_shield.crown(s); k = round(math.degrees(math.atan2(sun.z, sun.y)) % 360/30) % len(cr['bays']); a = cr['bays'][k]['azimuth']
        rad = Vector((0, math.cos(a), math.sin(a))); tan = X.cross(rad); focus = Vector((forward_shield.truss_aft_at(s, 37.0), 0, 0))+rad*37.0
        foot = Vector((cr['x0'], 0, 0))+rad*42.75+tan*1.9; d = -.85*X+.30*rad+.45*tan; size = 9.0; up = -X
    elif name == 'asm_ring':
        focus, rad = ring_band(s); tan = X.cross(rad); foot = focus+tan*3.5; d = -.55*X+.75*rad+.35*tan; size = 7.0; up = rad
    else:
        import thermal_geometry as tg
        dd = tg.blade_of(s); a = min((math.radians(b) for b in blade_azimuths(s)), key=lambda b: -math.cos(b-math.atan2(sun.z, sun.y)))
        m = next(q for q in tg.mounts(s, dd) if q['role'] == 'FIXED_DATUM'); focus = Vector(tg.local_to_ship(dd, a, m['u']-1.5, -.3, 0))
        rad = Vector((0, math.cos(a), math.sin(a))); tan = X.cross(rad)
        foot = Vector(tg.local_to_ship(dd, a, m['u']-1.6, tg.casing_surface_v(s, dd, 2.2, 2.6)[1], 2.4)); d = -.6*X+.6*rad+.5*tan; size = 4.0; up = rad
    corners = [focus+Vector((dx, dy, dz)) for dx in (-size, size) for dy in (-size, size) for dz in (-size, size)]
    return focus, d, corners, 35.0, foot, up


def render(views=VIEWS, size=1280, out_dir=None, samples=64):
    s, *_ = load(ROOT); x = s['look']['exterior']
    out = out_dir or ROOT/'runs'/'renders'/'p1'/'hero_look3'; out.mkdir(parents=True, exist_ok=True)
    (best, old) = tq_direction(s)
    report = dict(study='FUT-003-LOOK comparison (15!A131); presentation only, nothing saved, no geometry or canon change',
                  blades_deg=blade_azimuths(s), establishing=dict(azimuth_deg=old[1], blade_score=round(old[0], 3), **old[2]),
                  three_quarter=dict(azimuth_deg=best[1], off_axis_deg=best[3], blade_score=round(best[0], 3), direction=[round(v, 3) for v in best[2]], **best[4]),
                  views={})
    for name in views:
        offburn = name == 'eye_offburn'
        bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
        scene = bpy.context.scene; pose_configuration(s, 'COAST' if offburn else hp.STATE); e = hp.dress(s, name in FUNCTIONAL)
        if offburn:                                       # COAST: the hot-face temperature is OPEN, so the cells do not emit
            for m in bpy.data.materials:
                if m.name.startswith('WF_MAT_') and m.name[7:].split('.')[0] in x['hot_face'] and m.use_nodes:
                    n = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
                    if n:
                        n.inputs['Emission Strength'].default_value = 0.0
        scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = samples; scene.cycles.use_denoising = True; scene.cycles.seed = 0
        scene.render.resolution_x = size; scene.render.resolution_y = round(size*9/16); scene.render.image_settings.file_format = 'PNG'
        aspect = scene.render.resolution_x/scene.render.resolution_y; scene.world.use_nodes = True
        bg = next(n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND'); bg.inputs['Color'].default_value = (0, 0, 0, 1); bg.inputs['Strength'].default_value = 0.0
        sun_dir = Vector(e['sun'])
        if offburn:
            a, z = math.radians(150.0), math.radians(x['sun_azimuth_deg']); sun_dir = Vector((-math.cos(a), math.sin(a)*math.cos(z), math.sin(a)*math.sin(z)))
        sun = bpy.data.lights.new('Hero_Sun', 'SUN'); sun.energy = e['sun_strength']; sun.angle = math.radians(x['sun_angular_deg'])
        so = bpy.data.objects.new(sun.name, sun); scene.collection.objects.link(so); so.rotation_euler = (-sun_dir).to_track_quat('-Z', 'Y').to_euler()
        cam = bpy.data.objects.new('Hero_Camera', bpy.data.cameras.new('Hero_Camera')); scene.collection.objects.link(cam); scene.camera = cam
        if name.startswith(('tq', 'alt')):
            fs = forward_shield.stations(s); dm = drive_manifold.stations(s)
            focus = Vector(((dm['exit']+fs['lance_tip'])/2+12, 0, 0)); R = fs['shield_r']
            corners = [Vector((xx, yy, zz)) for xx in (dm['exit'], fs['lance_tip']) for yy in (-R, R) for zz in (-R, R)]
            quat, dist = hp.place(cam, focus, best[2] if name.startswith('tq') else Vector(ESTABLISHING).normalized(), corners, 35.0, aspect)
        elif name.startswith('asm'):
            focus, d, corners, lens, foot, up = asm_frame(s, name); quat, dist = hp.place(cam, focus, d, corners, lens, aspect); figure(scene, foot, up)
        else:
            quat, dist = hp.place(cam, *eye_frame(s), aspect)
        bpy.context.view_layer.update()
        if name.endswith('fill'):
            fill_light(scene, cam, dist, 3.0 if name.startswith('tq') else 1.5)   # the wide view is exposed for the hot face
        scene.view_settings.view_transform = 'AgX'; scene.view_settings.exposure = x['exposure_ev'] if not offburn else -1.5
        head = f"WAYFARER 001 / {'COAST (OFF-BURN ORIENTATION STUDY)' if offburn else 'FIRST IGNITION'} / {name.upper()}"
        lines = [head]
        if offburn:
            lines += ['separate off-burn orientation: COAST, sun 30 deg off the nose (this attitude is OPEN); NOT the First Ignition burn',
                      'hot face not emitting (COAST temperature OPEN) | no exhaust | REP_PROXY grey']
        else:
            lines += [f"actual light: one sun {x['sun_from_aft_deg']:g} deg from aft (outward burn, pointing OPEN) | hot face {e['kelvin']:g} K grey body | no plume drawn"]
            if name.startswith('alt'):
                lines += [f"alternative angle: the establishing camera, azimuth {old[1]:g} deg: blades {math.degrees(math.asin(min(1.0, old[2]['face']))):.0f} deg off "
                          f"edge-on, fanned {old[2]['spread_deg']:.0f} deg (for comparison with the working camera)"]
            elif name.startswith('tq'):
                lines += [f"camera {best[3]} deg off the aft axis at azimuth {best[1]:g} deg: blades {math.degrees(math.asin(min(1.0, best[4]['face']))):.0f}+ deg off "
                          f"edge-on, fanned {best[4]['spread_deg']:.0f}+ deg apart (establishing: {math.degrees(math.asin(min(1.0, old[2]['face']))):.0f} deg, "
                          f"{old[2]['spread_deg']:.0f} deg)"]
            elif name.startswith('asm'):
                lines += [{'asm_shield_rear': 'shield rear at the sun-side Crown bay: truss gussets, partition ribs, ochre service hatch (M4 slice 3)',
                           'asm_ring': "ring A rim over a pressurized crew segment: amber band, assembly joints, service covers (M4 slice 1)",
                           'asm_roots': 'sun-side blade datum root: casing boots, chase plate, post saddles (M4 slice 2)'}[name], SCALE]
            else:
                lines += ['the Brow and EYE face forward, away from the sun during the outward burn: strictly physical, they read dark']
            if name in FUNCTIONAL:
                lines += ['FUNCTIONAL-MARK VARIANT (PROTOTYPE art call, Doc 2026-10-14T16:58): pressure band, service covers and hatches, boots and steel fittings keep their colour; all else proxy grey']
        if name.endswith('fill'):
            lines += [FILL]
        lines += [f"{STATUS} | config {'COAST' if offburn else hp.STATE}, sun {x['sun_from_aft_deg'] if not offburn else 150:g} deg from aft at azimuth {x['sun_azimuth_deg']:g} deg, exposure {scene.view_settings.exposure:g} EV, Cycles {samples} spp"]
        labels = hp.caption(scene, cam, quat, dist, lines, aspect)
        scene.render.filepath = str(out/f'look3_{name}.png'); bpy.ops.render.render(write_still=True)
        report['views'][name] = dict(file=f'look3_{name}.png', state='COAST' if offburn else hp.STATE, physical=not name.endswith('fill') and not offburn, functional=name in FUNCTIONAL,
                                     label=lines[1:], camera=list(cam.location), status=STATUS)
        print('WF_LOOK3', name, flush=True)
    (out/'look3.json').write_text(json.dumps(report, indent=1)+'\n')
    print('WF_LOOK3 done', json.dumps(report['three_quarter']), json.dumps(report['establishing']), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--views', nargs='+', default=list(VIEWS), choices=VIEWS)
    p.add_argument('--size', type=int, default=1280); p.add_argument('--samples', type=int, default=64); p.add_argument('--out-dir', type=Path)
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    render(a.views, a.size, a.out_dir, a.samples)
