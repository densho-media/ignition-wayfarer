"""M4 visual identity (S&E 48 WF-006, 47 SIM-035, 15!G163 LOOK-005): two controlled hero-view comparisons and one inhabited-space proof,
physical light and conceptual fill labelled apart. Presentation only: renders in memory, saves nothing, changes no geometry or canon.

- `crew_physical` / `crew_fill`  the crew end at the working camera's azimuth (LOOK-004: 50 deg off aft, azimuth 120 deg), framed on the two
  rings, the spine and the primary docking port: the functional hierarchy at human scale. One non-diegetic 1.78 m scale figure (the MPFB
  instructor, captioned, not present at First Ignition) stands on the spine beside the port. Strict physical First Ignition light, then the
  same frame with the labelled illustrative fill (hero_look3.fill_light). The only variable is the fill.
- `aisle_physical` / `aisle_fill` ring A's habitation aisle (sector 1) in COAST with the induction pair (the MPFB instructor and newcomer in
  their S004 outfits), lit by the S004 emitters alone (light strips and berth reading lights, `[look]`), then the same frame with a labelled
  illustrative fill. The only variable is the fill.
- `aisle_pov`  the inhabited-space proof: the newcomer's eye at the instructor in the aisle, physical light, with the pair's measured fit
  (feet on the deck, least clearance of each body to every zone block, headroom) in the caption and in m4_look.json.

    /snap/bin/blender -b --python src/wayfarer/presentation/m4_look.py -- [--views ...] [--size 1600] [--samples 64] [--out-dir renders/p1/m4_look]
"""
from pathlib import Path
import argparse
import json
import math
import sys
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation')]
from common import apply_look, pose_configuration
from spec import load
import crew_transfer
import habitat_interior
import human_entry as he
import hero_preview as hp
import hero_look3 as hl3

VIEWS = ('crew_physical', 'crew_fill', 'aisle_physical', 'aisle_fill', 'aisle_pov')
STATUS = 'WF-006 / LOOK-005 (15!G163): PRESENTATION STUDY / FINAL VISUAL SIGNOFF OPEN'
FILL = hl3.FILL
# PROTOTYPE staging in ring A sector 1's frame (x along the aisle, deck at y 0, up -Y, z across; the aisle is |z| < 0.45 m):
# the instructor at the berths turns back to the newcomer, who has come aft along the aisle from the couches.
PAIR = {'INSTRUCTOR': ((1.05, 0.0, 0.0), (-0.94, 0.0, -0.34)), 'NEWCOMER': ((-0.55, 0.0, 0.06), (0.97, 0.0, 0.24))}   # at, facing
AISLE_EYE, AISLE_TARGET, AISLE_LENS = (-1.45, -1.55, -0.32), (1.35, -1.00, 0.20), 15.0
CREW_FRAME_M = (5.0, 12.0, 4.0, 8.0)             # PROTOTYPE framing round the figure: axial margin, radial in/out, across
CREW_OFF_AFT_DEG = 80.0                           # PROTOTYPE framing: the working camera's 50 deg puts the blades in front of the rings
SCALE_FIGURE = "scale figure 1.78 m on ring A's frame: NON-DIEGETIC, nobody is outside during the burn"


def sector(s, k=1):
    rot, _, la = he.vestibule_station(s, 1)
    pt = lambda v: Vector(he.at_index(rot, crew_transfer.sector_point(s, la[k], v)))
    return pt


def person(s, who, at, up, forward):
    """Append an MPFB body (assets/characters/WF_CHAR_HUMAN_<WHO>.blend) standing at `at` with its +Z along `up`, facing `forward` (the
    rig faces -Y), in its idle action at scene frame 1 (the frame that holds the rotors at their index angle)."""
    name = f'WF_CHAR_HUMAN_{who}'; before = set(bpy.data.actions)
    with bpy.data.libraries.load(str(ROOT/'assets/characters'/f'{name}.blend'), link=False) as (src, dst):
        dst.collections = [name]
    col = dst.collections[0]; bpy.context.scene.collection.children.link(col)
    arm = next(o for o in col.all_objects if o.type == 'ARMATURE')
    z = up.normalized(); y = -(forward-z*forward.dot(z)).normalized(); x = y.cross(z)
    arm.matrix_world = Matrix.Translation(at) @ Matrix((x, y, z)).transposed().to_4x4()
    act = next((a for a in bpy.data.actions if a not in before and a.name.split('.')[0] == 'idle'), None)
    if act is not None:
        arm.animation_data_create(); arm.animation_data.action = act
        if hasattr(arm.animation_data, 'action_slot') and act.slots:
            arm.animation_data.action_slot = act.slots[0]
    bpy.context.scene.frame_set(1); bpy.context.view_layer.update()
    return arm, [o for o in col.all_objects if o.type == 'MESH']


def points(objs):
    dg = bpy.context.evaluated_depsgraph_get(); out = []
    for o in objs:
        e = o.evaluated_get(dg); m = e.to_mesh(); out += [e.matrix_world @ v.co for v in m.vertices]; e.to_mesh_clear()
    return out


def fit(s, pt, bodies):
    """The pair's fit in the sector frame: each body's lowest point above the deck, head top, and the least distance of its vertices to every
    zone block (axis-aligned boxes of habitat_interior.zones), the worst block named."""
    o = pt((0, 0, 0)); X = pt((1, 0, 0))-o; Y = pt((0, 1, 0))-o; Z = pt((0, 0, 1))-o
    blocks = habitat_interior.zones(s, 'HABITATION'); out = {}
    for who, objs in bodies.items():
        loc = [((p-o).dot(X), (p-o).dot(Y), (p-o).dot(Z)) for p in points(objs)]
        least = {}
        for b in blocks:
            lo, hi = b['min'], b['max']
            d = min(math.sqrt(sum(max(lo[i]-q[i], 0.0, q[i]-hi[i])**2 for i in range(3))) for q in loc[::7])
            least[b['name']] = d
        worst = min(least, key=least.get)
        out[who] = dict(feet_above_deck_m=round(-max(q[1] for q in loc), 3), height_m=round(-min(q[1] for q in loc), 3),
                        least_block=worst, least_clearance_m=round(least[worst], 3), across_m=[round(min(q[2] for q in loc), 3), round(max(q[2] for q in loc), 3)])
    return out


def setup(scene, size, samples):
    scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = samples; scene.cycles.use_denoising = True; scene.cycles.seed = 0
    scene.render.resolution_x = size; scene.render.resolution_y = round(size*9/16); scene.render.image_settings.file_format = 'PNG'
    scene.world.use_nodes = True; bg = next(n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = (0, 0, 0, 1); bg.inputs['Strength'].default_value = 0.0
    scene.view_settings.view_transform = 'AgX'
    return scene.render.resolution_x/scene.render.resolution_y


def crew_view(s, name, size, samples, out):
    x = s['look']['exterior']
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
    scene = bpy.context.scene; pose_configuration(s, hp.STATE); e = hp.dress(s); aspect = setup(scene, size, samples)
    sun = bpy.data.lights.new('Hero_Sun', 'SUN'); sun.energy = e['sun_strength']; sun.angle = math.radians(x['sun_angular_deg'])
    so = bpy.data.objects.new(sun.name, sun); scene.collection.objects.link(so); so.rotation_euler = (-Vector(e['sun'])).to_track_quat('-Z', 'Y').to_euler()
    best, _ = hl3.tq_direction(s); az = math.radians(best[1]); el = math.radians(CREW_OFF_AFT_DEG)
    d = Vector((-math.cos(el), math.sin(el)*math.cos(az), math.sin(el)*math.sin(az)))
    rA, rB = he.vestibule_station(s, 1)[0], he.vestibule_station(s, 2)[0]; R = s['habitat_ring']['sector_outer_radius_m']
    # The scale figure: on ring A's outer shell at the limb (seen in profile, toward the sun's side), standing along the radial, facing
    # forward. The frame holds both rings' rims around it: the rings at the scale of a person.
    az = math.atan2(d.z, d.y)+math.pi/2; radial = Vector((0, math.cos(az), math.sin(az))); side = d.cross(radial).normalized()
    corners = [Vector((xx, 0, 0))+radial*rr+side*ss for xx in (rA['x']-CREW_FRAME_M[0], rB['x']+CREW_FRAME_M[0])
               for rr in (R-CREW_FRAME_M[1], R+CREW_FRAME_M[2]) for ss in (-CREW_FRAME_M[3], CREW_FRAME_M[3])]
    focus = sum(corners, Vector())/len(corners)
    cam = bpy.data.objects.new('Hero_Camera', bpy.data.cameras.new('Hero_Camera')); scene.collection.objects.link(cam); scene.camera = cam
    quat, dist = hp.place(cam, focus, d, corners, 50.0, aspect)
    bpy.context.view_layer.update()                       # the feet on the first surface met from outside along the radial
    hit, at, *_ = scene.ray_cast(bpy.context.evaluated_depsgraph_get(), Vector((rA['x'], 0, 0))+radial*(R+40.0), -radial)
    fig, _ = person(s, 'INSTRUCTOR', at if hit else Vector((rA['x'], 0, 0))+radial*R, radial, Vector((1, 0, 0)))
    bpy.context.view_layer.update(); feet = fig.matrix_world.translation
    figure = dict(feet=[round(v, 2) for v in feet], radius_m=round(feet.yz.length, 2), image=[round(v, 3) for v in world_to_camera_view(scene, cam, feet)][:2])
    if name.endswith('fill'):
        hl3.fill_light(scene, cam, dist, 3.0)
    scene.view_settings.exposure = x['exposure_ev']
    # hp.caption fits four lines: the title, the light, the camera and the scale figure, then the light class with the status.
    lines = [f"WAYFARER 001 / FIRST IGNITION / CREW END: rings A and B at the scale of a person / {name.upper()}",
             f"actual light: one sun {x['sun_from_aft_deg']:g} deg from aft (outward burn, pointing OPEN) | hot face {e['kelvin']:g} K grey body | no plume | REP_PROXY grey | {x['exposure_ev']:g} EV, {samples} spp",
             f"azimuth {best[1]:g} deg (LOOK-004), {CREW_OFF_AFT_DEG:g} deg off aft so the blades clear the rings, 50 mm | {SCALE_FIGURE}",
             ('ILLUSTRATIVE FILL - NOT PHYSICAL (no such light at First Ignition)' if name.endswith('fill') else 'strict physical light, nothing added')+f' | {STATUS}']
    hp.caption(scene, cam, quat, dist, lines, aspect)
    scene.render.filepath = str(out/f'm4_{name}.png'); bpy.ops.render.render(write_still=True)
    return dict(file=f'm4_{name}.png', state=hp.STATE, physical=not name.endswith('fill'), label=lines[1:], camera=[round(v, 2) for v in cam.location], scale_figure=figure)


def aisle_view(s, name, size, samples, out):
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
    scene = bpy.context.scene; pose_configuration(s, 'COAST'); apply_look(s); aspect = setup(scene, size, samples)
    for o in bpy.data.objects:                                # no review mannequins in an inhabited still
        if o.get('kind') == 'scale_reference' or o.name.startswith('Human_'):
            o.hide_render = True
    pt = sector(s); up = pt((0, -1, 0))-pt((0, 0, 0)); along = pt((1, 0, 0))-pt((0, 0, 0)); bodies = {}; arms = {}
    for who, (at, facing) in PAIR.items():
        arms[who], bodies[who] = person(s, who, pt(at), up, pt(facing)-pt((0, 0, 0)))
    cam = bpy.data.objects.new('Aisle_Camera', bpy.data.cameras.new('Aisle_Camera')); scene.collection.objects.link(cam); scene.camera = cam
    cam.data.lens = AISLE_LENS; cam.data.clip_start = .05; cam.data.clip_end = 200
    if name == 'aisle_pov':
        dg = bpy.context.evaluated_depsgraph_get()
        head = lambda who: max(points(bodies[who]), key=lambda p: (p-pt((0, 0, 0))).dot(up))
        top_n, top_i = head('NEWCOMER'), head('INSTRUCTOR')
        eye = top_n-up.normalized()*.11+along.normalized()*.10; target = top_i-up.normalized()*.14
        cam.data.lens = 24.0
    else:
        eye, target = pt(AISLE_EYE), pt(AISLE_TARGET)
    cam.location = eye; quat = (target-eye).to_track_quat('-Z', 'Y')
    # Keep the deck's up as the image's up.
    look = (target-eye).normalized(); xr = look.cross(up).normalized(); yr = xr.cross(look)
    quat = Matrix((xr, yr, -look)).transposed().to_quaternion(); cam.rotation_euler = quat.to_euler()
    bpy.context.view_layer.update()
    if name.endswith('fill'):
        L = bpy.data.lights.new('Illustrative_Fill', 'AREA'); L.shape = 'DISK'; L.size = 1.2; L.energy = 120.0
        lo = bpy.data.objects.new(L.name, L); scene.collection.objects.link(lo)
        lo.location = eye+quat@Vector((.45, .25, .2)); lo.rotation_euler = cam.rotation_euler
    scene.view_settings.exposure = 0.0
    fits = fit(s, pt, bodies); lt = s['look']['lights']
    fl = ' | '.join(f"{w.lower()}: {v['height_m']:.2f} m, feet {v['feet_above_deck_m']:+.3f} m, {v['least_clearance_m']:.2f} m to {v['least_block']}" for w, v in fits.items())
    lines = [f"WAYFARER 001 / COAST / RING A SECTOR 1 HABITATION AISLE: the induction pair (S004A tour) / {name.upper()}",
             "actual light: the S004 emitters only: cool 6500 K light strips, warm 2900 K berth reading lights ([look], PROTOTYPE depiction) | 0.5 g at the deck, drawn at the index angle",
             f"fit: {fl}",
             "instructor and newcomer (MPFB, S004 outfits: material zones, no garment geometry) | identities open (Q49) | staging PROTOTYPE"]
    if name.endswith('fill'):
        lines += ['ILLUSTRATIVE FILL - NOT PHYSICAL (a soft key beside the camera for the concept view; no such light is in the sector)']
    lines += [f"{STATUS} | Cycles {samples} spp"]
    width = 2*.25*math.tan(cam.data.angle_x/2); hp_lines = []
    for i, text in enumerate(lines):
        c = bpy.data.curves.new(f'M4_Label_{i}', 'FONT'); c.body = text; c.size = width*(.020 if i == 0 else .0135)
        m = bpy.data.materials.new('M4_Label'); m.use_nodes = True; n = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        n.inputs['Base Color'].default_value = (0, 0, 0, 1); n.inputs['Emission Color'].default_value = (.70, .80, .88, 1); n.inputs['Emission Strength'].default_value = 1.0
        c.materials.append(m); o = bpy.data.objects.new(c.name, c); scene.collection.objects.link(o)
        o.rotation_euler = quat.to_euler(); o.location = eye+quat@Vector((-width*.48, width/aspect*(.45-i*.032), -.25))
        o.visible_shadow = o.visible_diffuse = o.visible_glossy = False
    h = width/aspect*(.032*len(lines)+.03); w = width*1.02; top = width/aspect*.5
    bar = bpy.data.meshes.new('M4_Label_Bar'); bar.from_pydata([(0, 0, 0), (w, 0, 0), (w, h, 0), (0, h, 0)], [], [(0, 1, 2, 3)])
    m = bpy.data.materials.new('M4_Label_Black'); m.use_nodes = True; n = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    n.inputs['Base Color'].default_value = (0, 0, 0, 1); n.inputs['Roughness'].default_value = 1.0; n.inputs['Specular IOR Level'].default_value = 0.0
    bar.materials.append(m); o = bpy.data.objects.new(bar.name, bar); scene.collection.objects.link(o); o.rotation_euler = quat.to_euler()
    o.location = eye+quat@Vector((-width*.51, top-h, -.2505)); o.visible_shadow = o.visible_diffuse = o.visible_glossy = False
    scene.render.filepath = str(out/f'm4_{name}.png'); bpy.ops.render.render(write_still=True)
    return dict(file=f'm4_{name}.png', state='COAST', physical=not name.endswith('fill'), label=lines[1:], fit=fits,
                camera=[round(v, 3) for v in cam.location])


def render(views=VIEWS, size=1600, out_dir=None, samples=64):
    s, *_ = load(ROOT); out = out_dir or ROOT/'renders'/'p1'/'m4_look'; out.mkdir(parents=True, exist_ok=True)
    path = out/'m4_look.json'
    report = json.loads(path.read_text()) if path.exists() else dict(study='M4 visual identity (WF-006, SIM-035, LOOK-005); presentation only, nothing saved', views={})
    for name in views:
        report['views'][name] = (crew_view if name.startswith('crew') else aisle_view)(s, name, size, samples, out)
        print('WF_M4', name, json.dumps(report['views'][name].get('fit', '')), flush=True)
    path.write_text(json.dumps(report, indent=1)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--views', nargs='+', default=list(VIEWS), choices=VIEWS)
    p.add_argument('--size', type=int, default=1600); p.add_argument('--samples', type=int, default=64); p.add_argument('--out-dir', type=Path)
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    render(a.views, a.size, a.out_dir, a.samples)
