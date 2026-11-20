"""Build lab/studies/vertex-closure/vertex-1-8/REVIEW_VTX18.blend: the owner review file of Vertex 1.8 Phase F (Adaptive Vertex A+). Work, not canon.

  /snap/bin/blender -b --factory-startup --python lab/studies/vertex-closure/vertex-1-8/make_review.py [-- --no-render]

The approved ship (assets/wayfarer, this branch) is appended and made local. Its four linked engines (ENGINE_N1..N4) are hidden, never
deleted; WORK_VTX18 holds the A+ engines in their place (same placements, same parts plus the A+ machinery). The ship's own
DRIVE_MANIFOLD_CTRL keeps its drivers and gains the nine proposed properties; the whole nine-state sequence is keyframed on it from
aplus.py (one source for the file and the browser review), and the moving parts follow it through drivers. Press play: the camera
CAM_VTX18_CINEMATIC cuts through the states, its HUD shows each state's physical duration beside the compressed playback.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
import blend_aplus as ba  # noqa: E402
import aplus  # noqa: E402
import vertex_cluster as vc  # noqa: E402
import drive_manifold as dm  # noqa: E402

RENDER = '--no-render' not in sys.argv
s, R = aplus.load(); T = aplus.timeline(s, R); FPS = aplus.PROTO['fps']
PINK = 'COLOR_07'


def append_vehicle(blend):
    with bpy.data.libraries.load(str(blend), link=False) as (src, dst):
        dst.collections = ['WF_WAYFARER_001']
    return dst.collections[0]


def make_all_local():
    for _ in range(5):
        n = 0
        for attr in ('collections', 'objects', 'meshes', 'curves', 'materials', 'node_groups', 'actions', 'images', 'texts', 'lights', 'cameras', 'fonts', 'worlds'):
            for idb in list(getattr(bpy.data, attr)):
                if idb.library is not None:
                    try:
                        idb.make_local(); n += 1
                    except Exception:
                        pass
        if n == 0:
            break
    for lib in list(bpy.data.libraries):
        try:
            bpy.data.libraries.remove(lib)
        except Exception:
            pass


def text_mat(name, rgba, strength=1.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = rgba; m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = rgba; em.inputs['Strength'].default_value = strength
    out = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(em.outputs[0], out.inputs[0])
    return m


def text(coll, name, body, loc, size, rgba, parent=None):
    cu = bpy.data.curves.new(name, 'FONT'); cu.body = body; cu.size = size; cu.align_x = 'LEFT'
    o = bpy.data.objects.new(name, cu); coll.objects.link(o); o.parent = parent; o.location = loc; o.color = rgba
    o.data.materials.append(text_mat('WORK_VTX18_TEXT_'+('DIM' if rgba[0] < 0.8 else 'WHITE'), rgba))
    return o


def driver(obj, path, index, expr, ctrl, props):
    fc = obj.driver_add(path, index) if index >= 0 else obj.driver_add(path)
    d = fc.driver; d.type = 'SCRIPTED'
    for p in props:
        v = d.variables.new(); v.name = p; v.type = 'SINGLE_PROP'; v.targets[0].id = ctrl; v.targets[0].data_path = f'["{p}"]'
    d.expression = expr
    return fc


# ---------- the ship ----------------------------------------------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.use_scripts_auto_execute = True     # the ship's effect drivers are scripted expressions
scene = bpy.context.scene; scene.name = 'VTX18_REVIEW'
ship = append_vehicle(ROOT/'assets/wayfarer/WF_WAYFARER_001.blend')
make_all_local()
top_ship = bpy.data.collections.new('WF_APPROVED_SHIP'); scene.collection.children.link(top_ship); top_ship.children.link(ship)
for c in ship.children_recursive:
    if c.name.split('.')[0] in ('40_SIM_RIG', '30_CAMERAS', '20_HUMAN_SCALE'):
        c.hide_viewport = True; c.hide_render = True
assembly = bpy.data.objects['Assembly_PROPULSION_CLUSTER']; base = assembly.matrix_world.copy()
hidden = []
for n in range(1, 5):
    o = bpy.data.objects[f'ENGINE_N{n}']; o.hide_viewport = True; o.hide_render = True; o['wf_review_note'] = 'hidden (replaced by WORK_VTX18 A+ engine), not deleted'
    hidden.append(o.name)
ctrl = bpy.data.objects[dm.CONTROL]
# the effect drivers pointed at the cluster library's control; after the libraries are made local, point them at the local one
retargeted = 0
for o in bpy.data.objects:
    if o.animation_data:
        for d in o.animation_data.drivers:
            for v in d.driver.variables:
                for tg in v.targets:
                    if v.type == 'SINGLE_PROP' and (tg.id is None or (tg.id.name.startswith(dm.CONTROL) and tg.id != ctrl)):
                        tg.id_type = 'OBJECT'; tg.id = ctrl; retargeted += 1
print('WF_REVIEW retargeted drivers', retargeted, [o.name for o in bpy.data.objects if o.name.startswith(dm.CONTROL)], [l.filepath for l in bpy.data.libraries][:3], flush=True)

# ---------- A+ engines ------------------------------------------------------------------------------------------------------------------
work = bpy.data.collections.new('WORK_VTX18'); scene.collection.children.link(work); work.color_tag = PINK
eng = bpy.data.collections.new('WORK_VTX18_A_PLUS_ENGINES'); work.children.link(eng); eng.color_tag = PINK
rigs, objs = ba.build(s, R, eng, 'aplus', base=base)
fly = bpy.data.collections.new('WORK_VTX18_OPTIONAL_FLYWHEEL'); work.children.link(fly); fly.color_tag = PINK
fw = ba.build_flywheel(s, fly, base=base)
fly.hide_viewport = True; fly.hide_render = True
hud = bpy.data.collections.new('WORK_VTX18_HUD'); work.children.link(hud); hud.color_tag = PINK

# ---------- controller: nine proposed properties + the review state on the ship's DRIVE_MANIFOLD_CTRL ---------------------------------
PROPOSED = R['sequence']['proposed_properties']
for k, desc in PROPOSED.items():
    ctrl[k] = 0.0
    ctrl.id_properties_ui(k).update(min=-1.0 if k == 'induction_rotor_speed' else 0.0, max=9.0 if k == 'fault_code' else 1.0, description=f'PROPOSED (Vertex 1.8, review only): {desc}')
ctrl['review_state'] = 1.0; ctrl.id_properties_ui('review_state').update(min=1.0, max=9.0, description='Nine-state review sequence (1 dormant .. 9 shutdown)')
ctrl['alignment_display_gain'] = 1.0
ctrl.id_properties_ui('alignment_display_gain').update(min=1.0, max=100.0, description='1 = true scale; raise to see the alignment offset (survey 10 mm -> 0.5 mm)')
ctrl['wf_review'] = 'Vertex 1.8 Phase F: nine states keyframed from lab/studies/vertex-closure/vertex-1-8/aplus.py; physical durations on the HUD'

# keyframes: every control value from aplus at 12 keys per playback second (linear)
bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
keys = list(T['states'][0]['start']); frame = 1; step = 2; markers = []
for st in T['states']:
    n = int(round(st['play_s']*FPS)); markers.append((frame, st))
    for i in range(0, n, step):
        u = i/n
        for k in keys:
            if k in ctrl.keys():
                ctrl[k] = aplus.value_at(T, st, k, u); ctrl.keyframe_insert(f'["{k}"]', frame=frame+i)
    frame += n
end_frame = frame-1
bpy.context.preferences.edit.keyframe_new_interpolation_type = 'CONSTANT'
for f0, st in markers:
    ctrl['review_state'] = float(st['n']); ctrl.keyframe_insert('["review_state"]', frame=f0)
bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
scene.frame_start = 1; scene.frame_end = end_frame; scene.render.fps = FPS
for f0, st in markers:
    scene.timeline_markers.new(f'{st["n"]} {st["state"]} | {st["physical_label"]}', frame=f0)

# ---------- moving parts follow the controller ---------------------------------------------------------------------------------------
D = T['diagnostics']; al = D['alignment']
for n, groups in rigs.items():
    l4 = groups['L4']
    driver(l4, 'location', 0, f'{D["stroke_m"]}*(1-nozzle_deployment)', ctrl, ['nozzle_deployment'])
    for i in (1, 2):
        driver(l4, 'location', i, f'({al["fine_m"]}+{al["survey_m"]-al["fine_m"]}*(1-field_ring_trim))*alignment_display_gain*0.7071',
               ctrl, ['field_ring_trim', 'alignment_display_gain'])
    for gname, e in groups.items():
        if gname.startswith('PETAL_'):
            for ch in e.children:
                vec = e['armour_dir'] if ch.get('wf_material') == 'armour' else e['shell_dir']
                for i in range(3):
                    driver(ch, 'location', i, f'{vec[i]!r}*service_petals', ctrl, ['service_petals'])
def vis_keys(ob, shown):
    """Constant visibility keys at the state starts (shown(state) -> bool)."""
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'CONSTANT'
    for f0, st in markers:
        ob.hide_viewport = ob.hide_render = not shown(st)
        ob.keyframe_insert('hide_viewport', frame=f0); ob.keyframe_insert('hide_render', frame=f0)
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
for ob in objs:
    if ob.get('lock_lamp'):
        # amber while the carriage travels, green at a station, bright green from Vertex Lock (keyed from the same timeline)
        f = 1
        for st in T['states']:
            n = int(round(st['play_s']*FPS))
            for i in range(0, n, 2):
                d = aplus.value_at(T, st, 'nozzle_deployment', i/n); lk = aplus.value_at(T, st, 'vertex_lock', i/n)
                at_station = d < 0.002 or d > 0.998
                ob.color = (0.2, 0.6+0.4*lk, 0.15, 1.0) if at_station else (1.0, 0.6, 0.1, 1.0); ob.keyframe_insert('color', frame=f+i)
            f += n
    if ob.get('effect') == 'metrology':
        vis_keys(ob, lambda st: st['n'] == 3)
# rotor spin: integrate the keyed speed (a driver cannot integrate); baked keyframes, two per playback second x display revolutions
ang = 0.0; spin = 0.0; f = 1
for st in T['states']:
    n = int(round(st['play_s']*FPS))
    for i in range(n):
        w = aplus.value_at(T, st, 'induction_rotor_speed', i/n)
        ang += 2*math.pi*aplus.PROTO['rotor_display_rev']*w/FPS
        spin += (2*math.pi*0.8/FPS) if 1 < st['n'] < 6 else 0.0      # optional flywheel: spun up in 2-5, discharged into the first pulses
        if f % 2 == 1:
            for groups in rigs.values():
                for gname, e in groups.items():
                    if gname.startswith('ROTOR_'):
                        e.rotation_euler = (ang, 0, 0); e.keyframe_insert('rotation_euler', index=0, frame=f)
            rot = fw['CL_Ignition_Flywheel_Rotor']; rot.rotation_euler = (spin, 0, 0); rot.keyframe_insert('rotation_euler', index=0, frame=f)
        f += 1

# ---------- cinematic camera and HUD ------------------------------------------------------------------------------------------------------
pl = {p['n']: p for p in vc.placements(s)}
def ship(n, v):
    return base@Vector(vc.to_ship(pl[n], v))
def look(cam, loc, tgt):
    cam.location = loc; cam.rotation_euler = (Vector(tgt)-Vector(loc)).to_track_quat('-Z', 'Z').to_euler()
camd = bpy.data.cameras.new('CAM_VTX18_CINEMATIC'); camd.lens = 30; camd.clip_start = 0.3; camd.clip_end = 6000
cam = bpy.data.objects.new('CAM_VTX18_CINEMATIC', camd); work.objects.link(cam); scene.camera = cam
centre = base@Vector((-150.0, 0.0, 0.0))
SHOTS = aplus.SHOTS
def at(spec):
    if spec[0] == 'C':
        return base@Vector(spec[1]), base@Vector(spec[2])
    return ship(1, spec[0]), ship(1, spec[1])
for f0, st in markers:
    a, b = SHOTS[st['state']]; n = int(round(st['play_s']*FPS))
    for f, sp in ((f0, a), (f0+n-1, b)):
        loc, tgt = at(sp); look(cam, loc, tgt)
        cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
W = (0.95, 0.95, 0.95, 1.0); DIM = (0.7, 0.72, 0.75, 1.0); Z = -0.4; K = 0.2      # HUD 0.4 m in front of the lens (clip 0.3 m), nothing nearer
def hud_line(name, body, y, size=0.045, rgba=W):
    return text(hud, name, body, (-1.12*K, y*K, Z), size*K, rgba, parent=cam)
hud_line('HUD_TITLE', 'G.U. WAYFARER 001 - Vertex 1.8 Adaptive Vertex A+ - PROTOTYPE review, not canon', 0.66, 0.04, DIM)
hud_line('HUD_OPEN', 'OPEN: capture/detachment, source radiation, driver power and gain, coil survival, mass closure, thermal closure.\n'
         'A+ is a mechanical and visual architecture, not yet a propulsion solution. Flywheel optional (hidden).', -0.6, 0.032, DIM)
for f0, st in markers:
    end = aplus.diagnostics_at(T, st, 1.0, st['end'])
    lines = {
        'DORMANT': f'L4 stowed {abs(end["l4_position_m"]):.1f} m forward and locked; coils at zero; service petals open for inspection (cold, field down)',
        'MECHANICAL_PREPARATION': f'L4 carriage runs {D["stroke_m"]:.1f} m aft at 10 mm/s on the cylindrical rails; locks engage; dynamo rotors spin up',
        'DIGITAL_ALIGNMENT': f'Loop offsets {al["survey_m"]*1e3:.0f} mm -> {al["fine_m"]*1e3:.1f} mm; {al["loop"]} field tilt {al["survey_m"]*al["tilt_per_m"]*1e3:.2f} -> {end["field_tilt_mrad"]:.3f} mrad '
                             f'(side force {al["survey_m"]*al["tilt_per_m"]*D["thrust_engine_N"]/1e3:.1f} -> {end["side_force_kN"]:.2f} kN)',
        'FIELD_FORMATION': f'Stop field 0 -> {D["stop_field_T"]:.2f} T; stored 0 -> {D["stored_J"]/1e9:.2f} GJ per engine; no current leads ({D["lead_heat_avoided_W"]/1e6:.1f} MW lead heat avoided)',
        'PLASMA_CALIBRATION': 'Low-power test pulses; trim coils shape the field; predicted vs measured plume converge (display of the AI loop)',
        'FIRST_IGNITION': 'Driver pulses start the burn; exhaust appears. Bootstrap energy source OPEN (optional flywheel or ship storage)',
        'VERTEX_LOCK': 'Locks, alignment and calibration residual in tolerance: lock lamps close round each engine, then across the four',
        'SUSTAINED_MODULATION': f'Thrust {D["thrust_engine_N"]/1e6:.2f} MN per engine ({4*D["thrust_engine_N"]/1e6:.2f} MN cluster) at the display throttle; nothing mechanical moves',
        'SHUTDOWN_OR_FAILURE': 'Pulses stop; dynamos run backwards to discharge; after cool-down L4 stows forward',
    }
    body = (f'{st["n"]}/9  {st["state"].replace("_", " ")}   (existing state: {st["maps_to"]})\n'
            f'Physical duration: {st["physical_label"]}   |   playback {st["play_s"]:.0f} s\n{lines[st["state"]]}')
    o = hud_line(f'HUD_STATE_{st["n"]}', body, 0.56, 0.05)
    vis_keys(o, lambda x, n=st['n']: x['n'] == n)

# ---------- notes, look, renders, save ----------------------------------------------------------------------------------------------------
t = bpy.data.texts.new('README_VTX18_REVIEW'); t.write((HERE/'NOTES.md').read_text() if (HERE/'NOTES.md').exists() else __doc__)
scene.world = scene.world or bpy.data.worlds.new('WF_World'); scene.world.color = (0.02, 0.022, 0.03)
scene.render.engine = 'BLENDER_WORKBENCH'
sh = scene.display.shading; sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_shadows = False; sh.show_cavity = True; sh.cavity_type = 'WORLD'
scene.render.resolution_x, scene.render.resolution_y = 1600, 900
summary = dict(end_frame=end_frame, fps=FPS, hidden=hidden, objects=len(objs), markers=[(f, st['state']) for f, st in markers])
if RENDER:
    out = ROOT/'runs/renders/vertex18'; out.mkdir(parents=True, exist_ok=True)
    for f0, st in markers:
        n = int(round(st['play_s']*FPS)); f = f0+int(n*{'DORMANT': 0.5, 'MECHANICAL_PREPARATION': 0.6}.get(st['state'], 0.7))
        scene.frame_set(f); scene.render.filepath = str(out/f'vtx18_{st["n"]}_{st["state"].lower()}.png')
        bpy.ops.render.render(write_still=True)
scene.frame_set(1)
for scr in bpy.data.screens:
    for area in scr.areas:
        if area.type == 'VIEW_3D':
            for sp in area.spaces:
                if sp.type == 'VIEW_3D':
                    sp.shading.type = 'SOLID'; sp.shading.color_type = 'MATERIAL'; sp.clip_end = 6000; sp.region_3d.view_perspective = 'CAMERA'
bpy.context.preferences.filepaths.save_version = 0
path = HERE/'REVIEW_VTX18.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
(HERE/'review_summary.json').write_text(json.dumps(summary, indent=1))
print('WF_REVIEW saved', path, summary, flush=True)
