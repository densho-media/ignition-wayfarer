"""FUT-003 step 2: the First Ignition exterior hero stills (15!C120 item 2; [look.exterior], look.exterior; docs/MODEL.md "Look").
The saved assembly is posed at FIRST_IGNITION and dressed in memory only, never saved: every surface proxy grey (the exterior is
physics-locked, 15!H120), one hard sun in the aft hemisphere, the radiator cells emitting as a grey body at the WORKING hot-face temperature
and emissivity, the display exhaust shown but casting no light, and the display-only layers (field, envelopes, scale figures, glow
overlays) hidden. Cameras frame the Art Style spacecraft shot (Spacecraft A14: full silhouette, propulsion, radiators and shielding) and
the owner's three subjects (Brow/EYE, drive, radiators); two flat silhouette views run the Art Style silhouette test (A16)."""
from pathlib import Path
import argparse
import itertools
import math
import sys
import bpy
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build')]
from common import pose_configuration
from spec import load, derived
import drive_manifold
import forward_shield
import look
import thermal_geometry

STATE = 'FIRST_IGNITION'
VIEWS = ('establishing', 'brow', 'drive', 'radiator', 'silhouette_side', 'silhouette_threequarter')


def surface(m, node, base, rough, wear=None, ram=None):
    """S9 shading on a Principled material (Blender linear colours; the Godot runtime exterior runs the same formulas with its own noise and
    hash): wear darkens and tints the base colour where a world-space noise of feature size scale_m passes its coverage threshold and raises
    the roughness; ram tiles the forward-facing ram face (running bond, dark seams, per-tile value jitter, repaired tiles, wear pitting)."""
    nt = m.node_tree; N, L = nt.nodes, nt.links

    def put(v, sock):
        if isinstance(v, (int, float)):
            sock.default_value = v
        else:
            L.new(v, sock)

    def op(kind, a, b=0.0):
        n = N.new('ShaderNodeMath'); n.operation = kind; put(a, n.inputs[0]); put(b, n.inputs[1]); return n.outputs[0]

    geo = N.new('ShaderNodeNewGeometry')
    pos = N.new('ShaderNodeSeparateXYZ'); L.new(geo.outputs['Position'], pos.inputs[0])
    nrm = N.new('ShaderNodeSeparateXYZ'); L.new(geo.outputs['Normal'], nrm.inputs[0])
    value, rgh, tint = 1.0, rough, None
    if wear:
        nz = N.new('ShaderNodeTexNoise'); L.new(geo.outputs['Position'], nz.inputs['Vector'])
        nz.inputs['Scale'].default_value = 1.0/wear['scale_m']; nz.inputs['Detail'].default_value = 3.0
        th = 0.55-0.3*wear['coverage']
        mask = op('MINIMUM', op('MAXIMUM', op('DIVIDE', op('SUBTRACT', nz.outputs['Fac'], th), 0.3), 0.0), 1.0)
        value = op('SUBTRACT', 1.0, op('MULTIPLY', mask, wear['grime']))
        rgh = op('ADD', rough, op('MULTIPLY', mask, wear['rough']))
        tint = N.new('ShaderNodeMix'); tint.data_type = 'RGBA'; put(mask, tint.inputs[0])      # sockets 6/7/2: the colour A, B, Result
        tint.inputs[6].default_value = (1, 1, 1, 1); tint.inputs[7].default_value = (*wear['tint'], 1)
    if ram:
        tw, th_ = ram['tile_m'], ram['tile_m']/2
        u = op('DIVIDE', pos.outputs['Y'], tw); v = op('DIVIDE', pos.outputs['Z'], th_)
        row = op('FLOOR', v); uu = op('ADD', u, op('MULTIPLY', op('MODULO', row, 2.0), 0.5))
        col = op('FLOOR', uu); fu = op('SUBTRACT', uu, col); fv = op('SUBTRACT', v, row)
        du = op('MULTIPLY', op('MINIMUM', fu, op('SUBTRACT', 1.0, fu)), tw); dv = op('MULTIPLY', op('MINIMUM', fv, op('SUBTRACT', 1.0, fv)), th_)
        seam = op('LESS_THAN', op('MINIMUM', du, dv), ram['seam_m']/2)
        cell = N.new('ShaderNodeCombineXYZ'); put(col, cell.inputs[0]); put(row, cell.inputs[1])
        wn = N.new('ShaderNodeTexWhiteNoise'); wn.noise_dimensions = '3D'; L.new(cell.outputs[0], wn.inputs['Vector'])
        h2 = N.new('ShaderNodeSeparateColor'); L.new(wn.outputs['Color'], h2.inputs[0])
        tile = op('ADD', op('ADD', 1.0, op('MULTIPLY', op('SUBTRACT', wn.outputs['Value'], 0.5), 2*ram['jitter'])),
                  op('MULTIPLY', op('LESS_THAN', h2.outputs[1], ram['repair_share']), ram['repair_value']-1.0))
        if ram.get('pitting'):
            pit = N.new('ShaderNodeTexWhiteNoise'); pit.noise_dimensions = '3D'
            sc = N.new('ShaderNodeVectorMath'); sc.operation = 'SCALE'; L.new(geo.outputs['Position'], sc.inputs[0]); sc.inputs['Scale'].default_value = 25.0
            L.new(sc.outputs[0], pit.inputs['Vector'])
            tile = op('MULTIPLY', tile, op('SUBTRACT', 1.0, op('MULTIPLY', op('LESS_THAN', pit.outputs['Value'], ram['pitting']), 0.45)))
        rv = op('ADD', tile, op('MULTIPLY', seam, op('SUBTRACT', ram['seam_value'], tile)))
        on = op('MULTIPLY', op('GREATER_THAN', nrm.outputs['X'], ram['normal_x_min']), op('GREATER_THAN', pos.outputs['X'], ram['x_min_m']))
        value = op('MULTIPLY', value, op('ADD', 1.0, op('MULTIPLY', on, op('SUBTRACT', rv, 1.0))))
    col = N.new('ShaderNodeVectorMath'); col.operation = 'SCALE'; col.inputs[0].default_value = base; put(value, col.inputs['Scale'])
    out = col.outputs[0]
    if tint is not None:
        mul = N.new('ShaderNodeVectorMath'); mul.operation = 'MULTIPLY'; L.new(out, mul.inputs[0]); L.new(tint.outputs[2], mul.inputs[1])
        out = mul.outputs[0]
    L.new(out, node.inputs['Base Color'])
    put(rgh, node.inputs['Roughness'])


def dress(s, functional=False, emit=True, grammar=False, wear=False):
    """Hide the display-only layers and put the exterior look on every WF_MAT_ material copy (linked copies included). functional: the
    look.exterior.functional_materials keep their own base colour (the LOOK-005 functional-mark variant); the light is unchanged.
    grammar: the Phase 4 exterior grammar ([production.exterior], owner S1 selection 2026-10-24): each generated material takes its family
    (production_detail.ship_family; the dark COAST blade depiction included), 'none' keeps its own colour, the production layers keep their
    pack finishes, and the ram face takes its tile-and-repair shading (S9). wear (grammar only): the post-voyage wear layer
    ([production.exterior.wear]) on the families it names, the exterior production materials (Prod_xf_*) included."""
    import production_detail as pd
    x = s['look']['exterior']; e = look.exterior(s); X = s['production']['exterior']; fam = X['families']
    # Some display layers are shown by hide drivers (the glow steps), so their materials also go fully transparent.
    clear = set()
    for o in bpy.data.objects:
        if o.get('kind') in x['hidden_kinds'] or o.name.startswith(('Preview_', *x['hidden_prefixes'])):
            o.hide_render = o.hide_viewport = True
            clear |= {sl.material for sl in o.material_slots if sl.material}
    for m in bpy.data.materials:
        name = m.name[7:].split('.')[0] if m.name.startswith('WF_MAT_') else None
        if name is None or name in x['display_emitters'] or not m.use_nodes:
            continue
        if m in clear:
            node = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            for key in ('Alpha', 'Emission Strength'):
                for link in list(node.inputs[key].links):
                    m.node_tree.links.remove(link)
                node.inputs[key].default_value = 0.0
            continue
        node = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if node is None:
            continue
        if grammar and name.startswith('Prod_'):
            if wear and name[5:] in X['wear'] and name[5:] in fam:      # an exterior pack material in a worn family
                r, g, b, rough, metal = fam[name[5:]]
                surface(m, node, (r, g, b), rough, X['wear'][name[5:]])
            continue
        for key in ('Base Color', 'Roughness', 'Metallic', 'Emission Color', 'Emission Strength', 'Alpha'):
            for link in list(node.inputs[key].links):
                m.node_tree.links.remove(link)
        rule = pd.ship_rule(s, name) if grammar else None
        if rule in fam:
            r, g, b, rough, metal = fam[rule]
            node.inputs['Base Color'].default_value = (r, g, b, 1)
            node.inputs['Roughness'].default_value = rough
            node.inputs['Metallic'].default_value = metal
            ram = X['ram_face'] if name in X['ram_face']['ram_materials'] else None
            if ram or wear and rule in X['wear']:
                surface(m, node, (r, g, b), rough, X['wear'].get(rule) if wear else None,
                        ram and dict(ram, **(X['wear']['ram_face'] if wear else {})))
        elif rule == 'none':
            pass                                        # keeps its own display colour and finish (the exterior lights' lenses)
        else:
            if not (functional and name in x['functional_materials']):
                node.inputs['Base Color'].default_value = (*x['grey'], 1)
            node.inputs['Roughness'].default_value = x['roughness']
            node.inputs['Metallic'].default_value = 0.0
        node.inputs['Alpha'].default_value = 1.0
        hot = emit and name in x['hot_face']            # emit False: off-burn COAST, the blade temperature there is OPEN
        node.inputs['Emission Color'].default_value = (*e['color'], 1) if hot else (0, 0, 0, 1)
        node.inputs['Emission Strength'].default_value = e['strength'] if hot else 0.0
    for o in bpy.data.objects:
        if any(sl.material and sl.material.name[7:].split('.')[0] in x['display_emitters'] for sl in o.material_slots):
            o.visible_diffuse = o.visible_glossy = o.visible_transmission = o.visible_volume_scatter = o.visible_shadow = False
    return e


def frame(name, s):
    """(focus, view direction from the focus to the camera, corners to fit, lens mm) from the shared stations, never fixed X numbers."""
    fs = forward_shield.stations(s); dm = drive_manifold.stations(s); b = thermal_geometry.blade_of(s)
    a = math.radians(s['prototype']['radiator_phase_deg']); out = Vector((0, math.cos(a), math.sin(a))); nrm = Vector((0, -math.sin(a), math.cos(a)))
    box = lambda x0, x1, r: [Vector(p) for p in itertools.product((x0, x1), (-r, r), (-r, r))]
    R = fs['shield_r']
    if name == 'establishing':
        # Aft and below on the sun side: the thrust axis runs as a diagonal from the nozzles in front to the Brow, with space ahead of it.
        return Vector(((dm['exit']+fs['lance_tip'])/2+12, 0, 0)), Vector((-.62, -1.0, -.30)), box(dm['exit'], fs['lance_tip'], R), 35.0
    if name == 'brow':
        # Ahead and well to the sun side: the forward face lies in its own shadow (the burn points away from the sun), so the Brow reads as
        # a dark disc against the glowing blades and hull behind it, with the sunlit rim and Lance.
        return Vector((fs['face']-25, 0, 0)), Vector((.62, -1.0, .20)), box(fs['face']-60, fs['lance_tip'], R), 50.0
    if name == 'drive':
        # Behind and below: the four nozzles and their exhaust run, the blade roots and the aft hull.
        return Vector((dm['exit']+8, 0, 0)), Vector((-1.0, -.42, -.30)), box(dm['exit']-6, dm['exit']+28, 14.0), 40.0
    if name == 'radiator':
        # Low along blade 0's sunlit face from outboard of its aft corner: the emitting cells receding forward, the dark 0.125 m seams, the
        # unlit root band along the hull and the rings beyond. An explicit camera (location, target) rather than a fit.
        eye = Vector((b['aft_x_m']-14, 0, 0))+out*(b['outer_radius_m']+7)+nrm*7.5
        target = Vector((b['aft_x_m']+.42*b['blade_length_m'], 0, 0))+out*(b['root_radius_m']+.45*b['ribbon_width_m'])
        return target, eye, None, 24.0
    if name == 'silhouette_side':
        return Vector(((dm['exit']+fs['lance_tip'])/2, 0, 0)), Vector((0, -1.0, 0)), box(dm['exit']-6, fs['lance_tip'], R), None
    return Vector(((dm['exit']+fs['lance_tip'])/2, 0, 0)), Vector((1.0, -1.4, .9)), box(dm['exit']-6, fs['lance_tip'], R), 50.0


def place(camera, focus, direction, corners, lens, aspect):
    """Perspective fit of the corners (or orthographic for lens None), looking at the focus from `direction`."""
    data = camera.data
    if corners is None:
        # `direction` is the camera location itself.
        data.type = 'PERSP'; data.lens = lens; data.clip_start = .5; data.clip_end = 3000
        quat = (focus-direction).to_track_quat('-Z', 'Y'); camera.location = direction; camera.rotation_euler = quat.to_euler()
        return quat, (focus-direction).length
    direction = direction.normalized(); quat = (-direction).to_track_quat('-Z', 'Y')
    local = [quat.inverted() @ (p-focus) for p in corners]
    if lens is None:
        data.type = 'ORTHO'
        w = max(p.x for p in local)-min(p.x for p in local); h = max(p.y for p in local)-min(p.y for p in local)
        data.ortho_scale = max(w, h*aspect)*1.12; distance = 600.0
    else:
        data.type = 'PERSP'; data.lens = lens
        tanx = math.tan(data.angle_x/2); tany = tanx/aspect
        distance = max(max(abs(p.x)/tanx+p.z, abs(p.y)/tany+p.z) for p in local)*1.08
    camera.location = focus+direction*distance; camera.rotation_euler = quat.to_euler()
    data.clip_start = .5; data.clip_end = 3000
    return quat, distance


def caption(scene, camera, quat, distance, lines, aspect):
    """Small status text in the lower left, unlit by the scene and invisible to rays."""
    data = camera.data; depth = 3.0
    width = 2*depth*math.tan(data.angle_x/2) if data.type == 'PERSP' else data.ortho_scale
    height = width/aspect; out = []
    mat = bpy.data.materials.new('Hero_Caption'); mat.use_nodes = True
    node = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    node.inputs['Base Color'].default_value = (0, 0, 0, 1); node.inputs['Emission Color'].default_value = (.62, .68, .74, 1)
    node.inputs['Emission Strength'].default_value = .9
    for i, text in enumerate(lines):
        curve = bpy.data.curves.new(f'Hero_Caption_{i}', 'FONT'); curve.body = text; curve.size = width*(.016 if i == 0 else .0115)
        curve.materials.append(mat)
        obj = bpy.data.objects.new(curve.name, curve); scene.collection.objects.link(obj)
        obj.rotation_euler = quat.to_euler()
        obj.location = camera.location+quat@Vector((-width*.475, -height*.40-height*.032*i, -depth if data.type == 'PERSP' else -distance+5))
        obj.visible_shadow = obj.visible_diffuse = obj.visible_glossy = False
        out.append(obj)
    # A black bar behind the text, so the caption reads over a bright blade.
    rows = len(lines); h = height*(.032*rows+.035); w = width*1.02
    bar = bpy.data.meshes.new('Hero_Caption_Bar'); bar.from_pydata([(0, 0, 0), (w, 0, 0), (w, h, 0), (0, h, 0)], [], [(0, 1, 2, 3)])
    black = bpy.data.materials.new('Hero_Caption_Black'); black.use_nodes = True
    node = next(n for n in black.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'); node.inputs['Base Color'].default_value = (0, 0, 0, 1)
    node.inputs['Roughness'].default_value = 1.0; node.inputs['Specular IOR Level'].default_value = 0.0; bar.materials.append(black)
    obj = bpy.data.objects.new(bar.name, bar); scene.collection.objects.link(obj); obj.rotation_euler = quat.to_euler()
    obj.location = camera.location+quat@Vector((-width*.51, -height*.51, (-depth if data.type == 'PERSP' else -distance+5)-.01))
    obj.visible_shadow = obj.visible_diffuse = obj.visible_glossy = False
    out.append(obj)
    return out


def render(views=VIEWS, size=1024, out_dir=None, samples=64, state=STATE, functional=False, editorial_ev=0.0):
    s, *_ = load(ROOT); d = derived(s)
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
    scene = bpy.context.scene
    # OWN-M4 (15!A202): IGNITION with physical 1800 K-class blade emission; COAST off-burn with the same sun, exposure and cameras, the
    # blades unlit (their COAST temperature is OPEN), so the shield / Crown / rings / radiator / drive order reads in reflected light.
    burn = state == 'FIRST_IGNITION'
    # OWN-M4-C01 (15!A222, 98!A123): a separate COAST readability still may raise the exposure (+1 / +2 EV); emission is unchanged and
    # the caption says it is not comparable with the matched pair. The matched pair stays at the shared exposure.
    if editorial_ev and burn:
        raise ValueError('The editorial exposure applies to the COAST set only (15!A222)')
    pose_configuration(s, state)
    e = dress(s, functional, emit=burn); x = s['look']['exterior']
    scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = samples; scene.cycles.use_denoising = True
    scene.cycles.seed = 0
    scene.render.resolution_x = size; scene.render.resolution_y = round(size*9/16); scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'; scene.render.film_transparent = False
    aspect = scene.render.resolution_x/scene.render.resolution_y
    scene.world.use_nodes = True
    bg = next(n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = (0, 0, 0, 1); bg.inputs['Strength'].default_value = 0.0
    sun = bpy.data.lights.new('Hero_Sun', 'SUN'); sun.energy = e['sun_strength']; sun.angle = math.radians(x['sun_angular_deg'])
    sun_obj = bpy.data.objects.new(sun.name, sun); scene.collection.objects.link(sun_obj)
    sun_obj.rotation_euler = (-Vector(e['sun'])).to_track_quat('-Z', 'Y').to_euler()
    cam_data = bpy.data.cameras.new('Hero_Camera'); camera = bpy.data.objects.new(cam_data.name, cam_data)
    scene.collection.objects.link(camera); scene.camera = camera
    out = out_dir or ROOT/'renders'/'p1'/'hero_first_ignition'; out.mkdir(parents=True, exist_ok=True)
    status = (f"PROTOTYPE hero still | REP_PROXY grey, no hero finish (15!H120) | sun 1 AU-class, {x['sun_from_aft_deg']:g} deg from aft "
              f"(outward departure; pointing OPEN)")
    heat = (f"hot face: grey body at {e['kelvin']:g} K, emissivity {e['emissivity']:g} (WORKING), uniform (temperature map OPEN), "
            f"{e['sunlit_ratio']:.1f}x a sunlit hull | root band unlit") if burn else \
           ("OFF-BURN COAST: blades unlit (their COAST temperature is OPEN), drive off; same sun, exposure and cameras as the IGNITION set"
            if not editorial_ev else f"OFF-BURN COAST: blades unlit (their COAST temperature is OPEN), drive off; same sun and cameras as the "
            f"IGNITION set, exposure {editorial_ev:+g} EV (editorial; emission unchanged)")
    drive = ("exhaust plume not drawn (boundary and luminosity OPEN) | plasma inside the nozzles in its display colour, casting no light" if burn
             else "rings spinning (pose only) | M4 functional marks" + (" shown (amber bands, ochre covers, off-white boots)" if functional else " not shown")) + \
            " | NOT A FINAL RENDER: owner review pending"
    labels = []
    for name in views:
        for obj in labels:
            bpy.data.objects.remove(obj, do_unlink=True)
        focus, direction, corners, lens = frame(name, s)
        quat, distance = place(camera, focus, direction, corners, lens, aspect)
        flat = name.startswith('silhouette')
        if flat:
            # Art Style A16: colour, signage and inhabitants removed; the shape alone must read. Black on white, flat.
            scene.render.engine = 'BLENDER_WORKBENCH'; sh = scene.display.shading
            sh.light = 'FLAT'; sh.color_type = 'SINGLE'; sh.single_color = (0, 0, 0); sh.background_type = 'WORLD'
            scene.world.color = (1, 1, 1); scene.view_settings.view_transform = 'Standard'; scene.view_settings.exposure = 0.0
            labels = []
        else:
            scene.render.engine = 'CYCLES'; scene.view_settings.view_transform = 'AgX'; scene.view_settings.look = 'None'
            scene.view_settings.exposure = x['exposure_ev']+editorial_ev
            title = f"WAYFARER 001 / {'FIRST IGNITION' if burn else 'COAST (OFF-BURN)'} / {name.upper()}"
            if editorial_ev:
                title = f"COAST — {editorial_ev:+g} EV editorial exposure, not comparable brightness / {name.upper()}"
            labels = caption(scene, camera, quat, distance, [title, status, heat, drive], aspect)
        scene.render.filepath = str(out/f'hero_{name}.png')
        bpy.ops.render.render(write_still=True)
        print(f'WF_HERO {name} exposure_ev {scene.view_settings.exposure:g} (editorial {editorial_ev:+g})', flush=True)
    print(f"WF_HERO_LIGHT hot face {e['kelvin']:g} K strength {e['strength']:.3f} colour {e['color']} sunlit ratio {e['sunlit_ratio']:.2f}",
          flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--views', nargs='+', default=list(VIEWS), choices=VIEWS)
    p.add_argument('--size', type=int, default=1024); p.add_argument('--samples', type=int, default=64); p.add_argument('--out-dir', type=Path)
    p.add_argument('--state', default=STATE, choices=(STATE, 'COAST')); p.add_argument('--functional', action='store_true')
    p.add_argument('--editorial-ev', type=float, default=0.0, help='COAST readability still: EV above the matched exposure (15!A222)')
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if a.size < 128 or a.size > 1920:
        raise ValueError('Use 128-1920 px stills')
    render(a.views, a.size, a.out_dir, a.samples, a.state, a.functional, a.editorial_ev)
