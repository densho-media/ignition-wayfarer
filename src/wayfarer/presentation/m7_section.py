"""M7 production reference section: production stills and before/after comparisons of the L4 visual layer ([production]).

Every view renders the saved vehicle twice from one build, the production layer hidden (`before`, the engineering and route fit-out
as reviewed) and shown (`after`), with the S004 look applied in memory, the MPFB instructor and newcomer staged for human scale and the
review mannequins hidden. Physical light is the route's own emitters inside; outside, one labelled illustrative key and fill (no
mission sun is claimed for a docked view). Presentation only: renders in memory, saves nothing, changes no geometry or canon.

Views:
- `ent_exterior`  the primary port from outside, DOCKED, outer hatch open: capture ring, approach aids, the M7.EXT.PORT covers and ID.
- `ent_chamber`   the entry chamber from beside the outer hatch toward the inner hatch: the instructor waits on the aft (deck) side, the
                  newcomer has just come through; M7.ENT panels, trays, bulkhead faces and light housings.
- `ent_node`      from the inner hatch down into the trunk node toward the neck.
- `xfr_vestibule` ring A's despun drum from the vestibule mannequin's eye: M7.XFR lining and housings; closures physics-locked grey.
- `spk_tube`      down ring A's sector-1 crew tube from the top of the run: M7.SPK ring frames and cladding beside the ladder.
- `ra1_aisle`     ring A sector 1 (HABITATION) in COAST spin gravity: the M4 aisle staging of the pair, the camera raised toward the
                  overhead: M7.RA1 overhead service panels and aisle-light housings over the berths.
- `trk_trunk`     along the stationary trunk aft toward the hubs, the newcomer moving along the handrail (microgravity, head fore):
                  M7.TRK panels, trays and light housings between the route fit-out frames, the route stripe and the ladder.
- `ent_closeup`   M7.1 material and mechanical close-up: an entry-chamber light housing with the panels, seams and fasteners round it.
- `ext_hero`      M7.1 boarding hero: the primary port on the hull from a wider, low raking angle (labelled illustrative key and fill).

Modes (M7.1, presentation only):
- `beforeafter`   the default: each view with the production layer hidden and shown.
- `xray`          one image per view: engineering geometry in neutral clay, the production layer in amber (what M7 added, over what it
                  left unchanged).
- `material`      one pair per view: the exported flat Principled values, and a NONCANON study of restrained surface character (roughness
                  variation, micro-bump, darker edge wear) on the production materials only, to judge whether texture work earns its cost.

    /snap/bin/blender -b --python src/wayfarer/presentation/m7_section.py -- [--views ...] [--size 1280] [--samples 64] [--out-dir DIR]
                                                                         [--mode beforeafter|xray|material]
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
from common import apply_look, pose_configuration, pose_transfer
from spec import load
import human_entry as he
import m4_look
from entry_preview import frame, label

VIEWS = ('ent_exterior', 'ent_chamber', 'ent_node', 'trk_trunk', 'xfr_vestibule', 'spk_tube', 'ra1_aisle', 'ent_closeup', 'ext_hero')
MODES = ('beforeafter', 'xray', 'material')
# Eye-level points of view saved in the vehicle (human_entry.cameras): the crew member's eye is the human scale.
SAVED = {'spk_tube': 'CAM_HUM_SPOKE_TOP'}
SAVED_SHIFT = {'spk_tube': (0.0, -0.3, 0.0)}
STATUS = 'M7 production layer: L4_VISUAL_ACCEPTED (S&E 48!A23, owner 2026-10-20), not engineering GO'


def setup(s, state='DOCKED'):
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
    scene = bpy.context.scene; pose_configuration(s, state); f = he.ports(s)[0]
    ctrl = bpy.data.objects['DOCK_ENTRY_CTRL']
    for which in ('outer', 'inner'):
        ctrl[f"{f['name']}_{which}_open"] = 1.0
    ctrl.update_tag()
    for obj in bpy.data.objects:
        if obj.name.endswith('_Hatch_Hinge'):
            obj.update_tag()
        if obj.get('kind') in ('scale_reference', 'entry_camera') or obj.name.startswith(('Human_Entry_', 'Human_Ind_')):
            obj.hide_render = True
    pose_transfer(s, 1.0); scene.frame_set(scene.frame_current)
    apply_look(s); scene.view_settings.view_transform = 'AgX'
    # M7.1 interior exposure: the emitter-lit interiors clipped toward white; a medium-high-contrast AgX look and -0.4 EV keep the value steps
    # of the production materials apart (display grading, labelled in the captions; emission is unchanged).
    try:
        scene.view_settings.look = 'AgX - Medium High Contrast'
    except TypeError:
        pass
    scene.view_settings.exposure = -0.4
    scene.render.engine = 'CYCLES'; scene.cycles.samples = 64; scene.cycles.use_denoising = True; scene.cycles.seed = 0
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences; prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type != 'CPU'
        scene.cycles.device = 'GPU'
    except Exception:
        scene.cycles.device = 'CPU'
    scene.world.use_nodes = True; bg = next(n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = (.010, .012, .018, 1); bg.inputs['Strength'].default_value = .25
    return scene, f


def production(show):
    for obj in bpy.data.objects:
        if obj.get('kind') == 'production_detail':
            obj.hide_render = not show


def stage_pair(s, f, view):
    """The MPFB pair in the chamber, standing on its aft (deck) side, up = ship +X (aft is down under thrust; the induction greets in
    microgravity with a foot restraint, so the standing pose is the deck-referenced posture of the S004A greeting)."""
    st = he.stations(s, f); u, w = he.axes(f); deck = st['chamber_r']-.012
    up = Vector((1.0, 0.0, 0.0)); U = Vector(u); W = Vector(w); bodies = []
    feet = lambda a, side: Vector(he.world(f, a, 0.0))+Vector((-deck, 0.0, 0.0))+W*side
    if view in ('ent_chamber', 'ent_node'):
        bodies.append(m4_look.person(s, 'INSTRUCTOR', feet(4.45, -.30), up, U+W*.35)[1])
        bodies.append(m4_look.person(s, 'NEWCOMER', feet(5.30, .28), up, -U-W*.2)[1])
    if view == 'ra1_aisle':
        pt = m4_look.sector(s, 1); up = (pt((0.0, -1.0, 0.0))-pt((0.0, 0.0, 0.0))).normalized()
        for who, (at, face) in m4_look.PAIR.items():
            bodies.append(m4_look.person(s, who, pt(at), up, pt(face)-pt((0.0, 0.0, 0.0)))[1])
    if view == 'trk_trunk':
        import route_fitout as rf
        R = rf.trunk_extent(s)[0]; a = math.radians(s['human_entry']['trunk_handrail_deg'][0]); out = Vector((0.0, math.cos(a), math.sin(a)))
        # microgravity: the body along the trunk axis, head aft, facing the handrail wall it moves along (a 1.6 m bore admits no
        # standing posture across it)
        bodies.append(m4_look.person(s, 'NEWCOMER', Vector((95.6, 0.0, 0.0))+out*(R-.42), Vector((-1.0, 0.0, 0.0)), out)[1])
    return bodies


def camera(scene, s, f, view):
    st = he.stations(s, f); data = bpy.data.cameras.new('M7_Camera'); cam = bpy.data.objects.new(data.name, data)
    scene.collection.objects.link(cam); scene.camera = cam; data.clip_start = .03; data.clip_end = 800
    if view in SAVED:
        src = bpy.data.objects[SAVED[view]]; cam.matrix_world = src.matrix_world.copy(); data.lens = src.data.lens
        data.clip_start = src.data.clip_start
        # M7.1: off the saved eye point by SAVED_SHIFT (camera-local metres), so the tube's blue deck band (a wall strip) reads as a thin wedge
        # in perspective instead of filling the frame edge beside the eye
        cam.matrix_world.translation = cam.matrix_world @ Vector(SAVED_SHIFT.get(view, (0.0, 0.0, 0.0)))
        return cam, data
    if view == 'ra1_aisle':
        pt = m4_look.sector(s, 1); up = pt((0.0, -1.0, 0.0))-pt((0.0, 0.0, 0.0))
        eye = pt((-1.55, -1.45, -0.28)); target = pt((1.25, -2.55, 0.30))
        cam.location = eye; cam.rotation_euler = frame(target-eye, up); data.lens = 12; return cam, data
    if view == 'xfr_vestibule':
        import crew_transfer as ct
        rot, v, la = he.vestibule_station(s, s['induction']['ring']); M = bpy.data.objects[f"Drum_{s['induction']['ring']}"].matrix_world
        mid = (v['cu0']+v['cu1'])/2; R = v['clear']
        eye = M@Vector(ct.radial(mid+.15, R-.55, math.radians(-20))); target = M@Vector(ct.radial(mid-.1, R-.25, math.radians(70)))
        cam.location = eye; cam.rotation_euler = frame(target-eye, (M.to_3x3()@Vector((1.0, 0.0, 0.0))))
        data.lens = 14; return cam, data
    if view == 'ent_closeup':
        # the largest light-housing face in the chamber, seen from 0.75 m toward the chamber axis and a little aft and outboard
        o = bpy.data.objects['Prod_ENT_Housings']; M = o.matrix_world; p = max(o.data.polygons, key=lambda q: q.area)
        c = M@p.center; a0 = Vector(he.world(f, 0.0, 0.0)); d = Vector(he.vec(f, 1.0, 0.0, 0.0)).normalized()
        inward = (a0+d*(c-a0).dot(d)-c).normalized()
        eye = c+inward*1.05+Vector((.55, 0.0, 0.0))+Vector(he.axes(f)[1])*.35; target = c+Vector((-.45, 0.0, 0.0))-inward*.02
        data.lens = 30; up = Vector((1.0, 0.0, 0.0))
    elif view == 'ext_hero':
        target = Vector(he.world(f, st['port_face'], 0.0))+Vector((-.6, 0.0, 0.0))
        import os
        eye = target+Vector(tuple(float(x) for x in os.environ.get('M7_HERO', '-4,-14,6').split(','))); data.lens = 40; up = Vector((0.0, 0.0, 1.0))
    elif view == 'ent_exterior':
        target = Vector(he.world(f, st['port_face']-.2, .3, math.radians(-90))); eye = Vector(he.world(f, st['port_face']+6.0, 4.2, math.radians(-120)))
        data.lens = 28; up = Vector(he.vec(f, 1.0, 0.0, 0.0))
    elif view == 'ent_chamber':
        deck = Vector((-st['chamber_r'], 0.0, 0.0))
        eye = Vector(he.world(f, st['a_out']-.25, 0.0))+deck+Vector((1.62, 0.0, 0.0))+Vector(he.axes(f)[1])*-.45
        target = Vector(he.world(f, 4.2, 0.0))+deck+Vector((1.25, 0.0, 0.0))+Vector(he.axes(f)[1])*-.05
        data.lens = 16; up = Vector((1.0, 0.0, 0.0))
    elif view == 'trk_trunk':
        import crew_transfer as ct
        h = math.radians(s['human_entry']['trunk_handrail_deg'][0])
        eye = Vector(ct.radial(98.4, .35, h+math.pi)); target = Vector(ct.radial(92.0, .05, h))
        data.lens = 18; up = -Vector(ct.radial(0.0, 1.0, h))
    else:
        eye = Vector(he.world(f, st['a_in']-.35, .45, math.radians(30))); target = Vector(he.world(f, st['node_in']+.1, .2, math.radians(200)))
        data.lens = 14; up = Vector((1.0, 0.0, 0.0))
    cam.location = eye; cam.rotation_euler = frame(target-eye, up)
    return cam, data


def exterior_light(scene):
    """Labelled illustrative key and fill for a docked exterior (no mission attitude or sun is claimed)."""
    out = []
    for name, direction, energy in (('M7_Key', (.35, -.75, -.55), 3.0), ('M7_Fill', (-.6, .5, -.3), .6)):
        d = bpy.data.lights.new(name, 'SUN'); d.energy = energy; d.angle = .02 if name == 'M7_Key' else .3
        o = bpy.data.objects.new(name, d); scene.collection.objects.link(o); o.rotation_euler = frame(direction, (1, 0, 0)); out.append(o)
    return out


def xray(keep=()):
    """In memory, for an xray-only run: every production material (`WF_MAT_Prod_*`) becomes amber and every other material neutral clay (the
    linked vehicle objects keep their slots; their materials are recoloured). Emitters go dark with them, so xray views carry a labelled
    analysis headlamp."""
    skip = {sl.material for o in keep for sl in o.material_slots}
    for mat in bpy.data.materials:
        if mat in skip:
            continue
        mat.use_nodes = True; nt = mat.node_tree; nt.nodes.clear()
        b = nt.nodes.new('ShaderNodeBsdfPrincipled'); o = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(b.outputs[0], o.inputs['Surface'])
        prod = 'Prod_' in mat.name
        b.inputs['Base Color'].default_value = (.95, .5, .06, 1) if prod else (.55, .57, .6, 1); b.inputs['Roughness'].default_value = .45 if prod else .7


def _principled(mat, rgb, rough):
    mat.use_nodes = True; b = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (*rgb, 1); b.inputs['Roughness'].default_value = rough


def material_study(on):
    """NONCANON presentation study on the production materials only: roughness varied +-0.08 by a 2-3 cm noise, a 0.15 mm micro-bump and
    darker, smoother wear on convex edges (Pointiness). Off restores the exported values (the nodes are removed again)."""
    for mat in {sl.material for o in bpy.data.objects if o.get('kind') == 'production_detail' for sl in o.material_slots if sl.material}:
        nt = mat.node_tree; b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
        if not on:
            for n in [n for n in nt.nodes if n.name.startswith('M7S_')]:
                nt.nodes.remove(n)
            if 'm7s_rough' in mat:
                b.inputs['Roughness'].default_value = mat['m7s_rough']; b.inputs['Base Color'].default_value = mat['m7s_base']
            continue
        mat['m7s_rough'] = b.inputs['Roughness'].default_value; mat['m7s_base'] = tuple(b.inputs['Base Color'].default_value)
        r0 = mat['m7s_rough']; base = mat['m7s_base']
        tc = nt.nodes.new('ShaderNodeTexCoord'); tc.name = 'M7S_tc'
        nz = nt.nodes.new('ShaderNodeTexNoise'); nz.name = 'M7S_noise'; nz.inputs['Scale'].default_value = 40.0; nz.inputs['Detail'].default_value = 6.0
        nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
        rr = nt.nodes.new('ShaderNodeMapRange'); rr.name = 'M7S_rough'; rr.inputs['To Min'].default_value = max(0.05, r0-.08); rr.inputs['To Max'].default_value = min(1.0, r0+.08)
        nt.links.new(nz.outputs['Fac'], rr.inputs['Value'])
        geo = nt.nodes.new('ShaderNodeNewGeometry'); geo.name = 'M7S_geo'
        ed = nt.nodes.new('ShaderNodeMapRange'); ed.name = 'M7S_edge'; ed.inputs['From Min'].default_value = .52; ed.inputs['From Max'].default_value = .60
        nt.links.new(geo.outputs['Pointiness'], ed.inputs['Value'])
        mix = nt.nodes.new('ShaderNodeMix'); mix.name = 'M7S_mix'; mix.data_type = 'RGBA'
        mix.inputs[6].default_value = base; mix.inputs[7].default_value = tuple(c*.62 for c in base[:3])+(1,)
        nt.links.new(ed.outputs['Result'], mix.inputs['Factor']); nt.links.new(mix.outputs[2], b.inputs['Base Color'])
        mr = nt.nodes.new('ShaderNodeMath'); mr.name = 'M7S_wear'; mr.operation = 'MULTIPLY_ADD'; mr.inputs[1].default_value = -.25
        nt.links.new(ed.outputs['Result'], mr.inputs[0]); nt.links.new(rr.outputs['Result'], mr.inputs[2]); nt.links.new(mr.outputs[0], b.inputs['Roughness'])
        bm = nt.nodes.new('ShaderNodeBump'); bm.name = 'M7S_bump'; bm.inputs['Strength'].default_value = .15; bm.inputs['Distance'].default_value = .00015
        nt.links.new(nz.outputs['Fac'], bm.inputs['Height']); nt.links.new(bm.outputs['Normal'], b.inputs['Normal'])


def render(views=VIEWS, size=1280, samples=64, out_dir=None, mode='beforeafter'):
    s, *_ = load(ROOT); scene, f = setup(s); scene.cycles.samples = samples
    scene.render.resolution_x = size; scene.render.resolution_y = round(size*9/16); scene.render.image_settings.file_format = 'PNG'
    out = Path(out_dir or ROOT/'runs/renders/m7'); out.mkdir(parents=True, exist_ok=True); report = {}
    counts = {o.name: dict(assembly=o.get('m7_assembly'), elements=o.get('elements'), faces=len(o.data.polygons)) for o in bpy.data.objects
              if o.get('kind') == 'production_detail'}
    for view in views:
        made = []
        bodies = stage_pair(s, f, view)
        cam, data = camera(scene, s, f, view)
        lights = exterior_light(scene) if view in ('ent_exterior', 'ext_hero') else []
        states = {'beforeafter': (('before', False), ('after', True)), 'xray': (('xray', True),),
                  'material': (('flat', True), ('study', True))}[mode]
        for tag, show in states:
            production(show)
            if mode == 'material':
                material_study(tag == 'study')
            what = {'before': 'BEFORE: engineering + route fit-out', 'after': 'AFTER: production layer',
                    'xray': 'clay: engineering (unchanged) / amber: M7 production layer', 'flat': 'exported flat material values',
                    'study': 'NONCANON surface-character study (roughness, micro-bump, edge wear)'}[tag]
            caption = [f"WAYFARER 001 / M7 / {view} / "+what,
                       STATUS+' / '+('analysis headlamp only (emitters off), not a lighting design' if mode == 'xray' else
                                     'illustrative key + fill, labelled' if lights else 'lit by the route emitters only')+' / AgX medium-high contrast, -0.4 EV',
                       'MPFB instructor and newcomer: PROTOTYPE technical rigs, not casting (K01)' if bodies else
                       (('drum annulus at eye height' if view == 'xfr_vestibule' else 'eye-level point of view of the HUM-001 review mannequin')
                        +'; closures PROTOTYPE (I5/Q46 OPEN); ring A: no certified rescue route (15!A221)'
                        if view in SAVED or view == 'xfr_vestibule' else 'no figure: docked, no EVA rail released')]
            dl = max(.05, data.clip_start*1.5); labels = label(scene, cam, caption, dl*data.sensor_width/data.lens, 16/9, dl)
            if mode == 'xray':
                xray(labels)
                hd = bpy.data.lights.new('M7_XRay_Headlamp', 'POINT'); hd.energy = 120.0 if view == 'ext_hero' else 25.0; hd.shadow_soft_size = .3
                lamp = bpy.data.objects.new(hd.name, hd); scene.collection.objects.link(lamp); lamp.parent = cam; lamp.location = (.15, .25, 0)
                labels.append(lamp)
            path = out/f"{view}_{tag}.png"; scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True); made.append(str(path))
            for o in labels:
                bpy.data.objects.remove(o, do_unlink=True)
        material_study(False)
        report[view] = dict(images=made, figures=len(bodies), illustrative_light=bool(lights))
        for o in lights+[cam]:
            bpy.data.objects.remove(o, do_unlink=True)
        for col in [c for c in bpy.data.collections if c.name.startswith('WF_CHAR_HUMAN_')]:
            for o in list(col.all_objects):
                bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.collections.remove(col)
        print('WF_M7_VIEW', view, flush=True)
    (out/f'm7_section_{mode}.json').write_text(json.dumps(dict(status=STATUS, mode=mode, production_objects=counts, views=report), indent=1))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--views', nargs='+', choices=VIEWS, default=list(VIEWS)); p.add_argument('--size', type=int, default=1280)
    p.add_argument('--samples', type=int, default=64); p.add_argument('--out-dir', type=Path); p.add_argument('--mode', choices=MODES, default='beforeafter')
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    render(a.views, a.size, a.samples, a.out_dir, a.mode)
