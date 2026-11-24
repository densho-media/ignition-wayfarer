"""Experimental engine geometry for the moved burn and stronger closure coils (research geometry, NOT canon; owner brief 2026-11-24 12:16Z).

  /snap/bin/blender -b --factory-startup --python lab/studies/vertex-compact-engine/vertex-optimize/blender_optimize.py [-- --no-render]

Starts from the thermal review file (vertex-thermal/REVIEW_THERMAL.blend: the approved engine appended and made local, untouched, plus the
thermal hardware in WORK_THERMAL_*) and saves REVIEW_OPTIMIZE.blend with two scenes from the same camera:
  ORIGINAL   the engine as approved, burn at its drawn point, with the thermal hardware (the comparison baseline, kept unchanged)
  OPTIMIZED  the research geometry of results/coils.json:
     WORK_OPT_BURN      the burn moved aft (results/optimize.json best geometry), the drawn burn as a ghost, the target flight path
     WORK_OPT_CLOSURE   C1, C2 and L1 rewound for their closure current factor at the drawn current density (winding area x factor),
                        each with its hoop band (1.5 GPa allowable, coils.json) carrying embedded 20 K channels, cut away 70 deg; the
                        approved C1/C2 are hidden in this scene (never deleted)
     WORK_OPT_BLADES    the thermal study's source-aligned blades re-aimed edge-on at the moved burn (the approved ones hidden here)
     WORK_OPT_QUENCH    dump busbars from the three closure coils to a dump resistor at the cage root
     WORK_OPT_LABELS    labels
Every dimension comes from the study JSON; the geometry shows where the hardware would sit, never that it solves the physics (PROBLEMS in
vertex-optimize/NOTES.md: the capture field, forces and quench energy are not closed).
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
import vertex_engine as ve  # noqa: E402

RENDER = '--no-render' not in sys.argv
CO = json.loads((HERE / 'results' / 'coils.json').read_text())
TH = json.loads((HERE.parent / 'vertex-thermal' / 'results' / 'thermal.json').read_text())
PINK = 'COLOR_07'
BX0, BX1 = CO['burn_x_drawn'], CO['burn_x_moved']

bpy.ops.wm.open_mainfile(filepath=str(HERE.parent / 'vertex-thermal' / 'REVIEW_THERMAL.blend'))
orig = bpy.data.scenes['THERMAL']; orig.name = 'ORIGINAL'


def mat(name, rgba, emit=0.0, alpha=1.0, metal=0.0, rough=0.5):
    m = bpy.data.materials.new(name); m.diffuse_color = (rgba[0], rgba[1], rgba[2], alpha); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgba[:3], 1); b.inputs['Metallic'].default_value = metal; b.inputs['Roughness'].default_value = rough
    if emit:
        b.inputs['Emission Color'].default_value = (*rgba[:3], 1); b.inputs['Emission Strength'].default_value = emit
    if alpha < 1:
        b.inputs['Alpha'].default_value = alpha
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            m.blend_method = 'BLEND'
    return m


M = dict(wind=mat('WORK_OPT_winding', (0.72, 0.36, 0.12), metal=0.9, rough=0.35),
         cryo=mat('WORK_OPT_cryostat', (0.62, 0.66, 0.72), metal=0.8, rough=0.3),
         band=mat('WORK_OPT_hoop_band', (0.08, 0.08, 0.09), rough=0.6),
         chan=mat('WORK_OPT_20K_channel', (0.25, 0.65, 1.0), emit=1.5),
         burn=mat('WORK_OPT_burn', (1.0, 0.55, 0.2), emit=25.0),
         ghost=mat('WORK_OPT_burn_drawn', (0.6, 0.6, 0.6), emit=2.0, alpha=0.35),
         path=mat('WORK_OPT_target_path', (1.0, 0.85, 0.4), emit=3.0),
         quench=mat('WORK_OPT_quench', (0.95, 0.8, 0.1), metal=0.6, rough=0.4),
         blade=next((o.active_material for o in bpy.data.objects if o.name.startswith('WORK_THERMAL_mirror_B') and o.active_material),
                    None) or mat('WORK_OPT_blade', (0.8, 0.8, 0.85), metal=1.0, rough=0.15),
         text=mat('WORK_OPT_text', (0.95, 0.95, 0.95), emit=2.0))


def coll(name, parent):
    c = bpy.data.collections.new(name); parent.children.link(c); c.color_tag = PINK
    return c


def obj(name, vf, c, m, note):
    vs, fs = vf
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in vs], [], [tuple(f) for f in fs]); me.update()
    o = bpy.data.objects.new(name, me); c.objects.link(o); me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = True
    o['wf_note'] = note; o['wf_status'] = 'WORK / PROTOTYPE research geometry (vertex-optimize, not canon)'
    return o


def band_prof(x, R, w, t, n=4):
    return [(x - w / 2, R), (x + w / 2, R), (x + w / 2, R + t), (x - w / 2, R + t)]


opt = bpy.data.scenes.new('OPTIMIZED')
for a in ('engine', 'resolution_x', 'resolution_y', 'film_transparent'):
    setattr(opt.render, a, getattr(orig.render, a))
try:
    opt.eevee.taa_render_samples = orig.eevee.taa_render_samples
except Exception:
    pass
opt.world = orig.world
eng = bpy.data.collections['WF_VERTEX_ENGINE']; wt = bpy.data.collections['WORK_THERMAL']
SKIP = {'VTX_MAGNETIC_COILS', 'VTX_VISUAL_EFFECTS', 'WORK_THERMAL_BLADES', 'WORK_THERMAL_BLANKET_THIN', 'WORK_THERMAL_LABELS',
        'WORK_THERMAL_MIRRORS_A', 'WORK_THERMAL_MIRRORS_D', 'WORK_THERMAL_BLANKET_C_ARCHIVED'}
oe = bpy.data.collections.new('OPT_WF_VERTEX_ENGINE'); opt.collection.children.link(oe)        # the approved engine minus the rewound coils
for c in bpy.data.collections:
    if c.name.startswith('VTX_') and c.name not in SKIP:
        oe.children.link(c)
ow = bpy.data.collections.new('OPT_WORK_THERMAL'); ow.color_tag = PINK; opt.collection.children.link(ow)
for c in wt.children:
    if c.name not in SKIP and c.name not in ('WORK_THERMAL_CAMERAS', 'WORK_THERMAL_LIGHTS', 'WORK_THERMAL_SECTION'):
        ow.children.link(c)
for nm in ('WORK_THERMAL_CAMERAS', 'WORK_THERMAL_LIGHTS'):
    if bpy.data.collections.get(nm):
        opt.collection.children.link(bpy.data.collections[nm])
top = coll('WORK_OPT', opt.collection)
C = {k: coll(f'WORK_OPT_{k}', top) for k in ('BURN', 'CLOSURE', 'BLADES', 'BLANKET_KEPT', 'QUENCH', 'LABELS')}

# burn: moved, drawn ghost, the target's flight from the injector exit at the shield
for nm, x, m, r in (('WORK_OPT_BURN_POINT', BX1, M['burn'], 0.22), ('WORK_OPT_BURN_DRAWN', BX0, M['ghost'], 0.22)):
    o = obj(nm, ve.sphere_mesh((x, 0.0, 0.0), r, 16), C['BURN'], m,
            'moved burn point (optimize.json best)' if m is M['burn'] else 'drawn burn point (approved engine)')
o = obj('WORK_OPT_TARGET_PATH', ve.tube_mesh([(BX0 + 6.0, 0, 0), (BX1, 0, 0)], 0.03, 8), C['BURN'], M['path'],
        f'target flight extended {BX0 - BX1:.1f} m aft (injection timing and pointing: ENG-071)')

# closure coils rewound
ARC = (math.radians(35), math.radians(325))
for e in CO['research_geometry']:
    if e['factor'] == 1.0:
        continue
    x, R, wm, cm = e['x'], e['r'], e['winding_minor_m'], e['cryostat_minor_m']
    obj(f'WORK_OPT_{e["name"]}_winding', ve.torus_mesh(x, R, wm, None, 72, 16), C['CLOSURE'], M['wind'],
        f'{e["name"]} winding at x{e["factor"]:g} ampere-turns (drawn current density), peak field {e["B_peak_T"]:.1f} T')
    obj(f'WORK_OPT_{e["name"]}_cryostat', ve.torus_mesh(x, R, cm, ARC, 72, 16), C['CLOSURE'], M['cryo'],
        f'{e["name"]} cryostat, minor radius {cm:.2f} m (drawn {e["drawn_cryostat_minor_m"]:.2f} m), cut away to show the winding')
    if e['band_t_m'] > 0.005:
        prof = band_prof(x, R + wm, 1.6 * wm, e['band_t_m'])
        obj(f'WORK_OPT_{e["name"]}_hoop_band', ve._revolve(prof, 72, True, None), C['CLOSURE'], M['band'],
            f'{e["name"]} hoop band {e["band_t_m"] * 1000:.0f} mm, carries {e["hoop_MN"]:.0f} MN hoop tension at 1.5 GPa; also the cold-mass support')
        for j in (-1, 1):
            obj(f'WORK_OPT_{e["name"]}_20K_channel_{j:+d}', ve.torus_mesh(x + j * 0.5 * wm, R + wm + e['band_t_m'] / 2, min(0.05, e['band_t_m'] / 3 + 0.01), None, 72, 8),
                C['CLOSURE'], M['chan'], f'{e["name"]} 20 K channel embedded in the hoop band (multifunctional structure: hoop, support, cooling)')
    # quench busbar: from the coil bottom to the dump at the cage root, aft of the shield, below the axis
    obj(f'WORK_OPT_{e["name"]}_dump_bus', ve.tube_mesh([(x, 0.0, -(R + cm)), (x + 0.6, 0.0, -(R + cm + 0.8)), (-11.6, 0.0, -9.4)], 0.07, 8),
        C['QUENCH'], M['quench'], f'{e["name"]} quench dump busbar')
obj('WORK_OPT_DUMP_RESISTOR', ve.box_mesh((-11.0, 0.0, -9.8), (1.6, 1.2, 1.0), 0.0), C['QUENCH'], M['quench'],
    'dump resistor (radiates the dump at the cage root; 27 GJ at the research current, 286 GJ at capture: ENG-069)')

# blades re-aimed at the moved burn
for i, g in enumerate(TH['geometry']):
    if g['layer'] in ('mirror_B', 'blades') and g['kind'] == 'ribbon':
        b2 = []
        for a, b in zip(g['a'], g['b']):
            L = math.dist(a, b); t = [BX1 - a[0], -a[1], -a[2]]; Lt = math.sqrt(sum(q * q for q in t))
            b2.append([a[k] + L * t[k] / Lt for k in range(3)])
        vs = [tuple(p) for p in g['a']] + [tuple(p) for p in b2]; n = len(g['a'])
        obj(f'WORK_OPT_blade_{i:03}', (vs, [(k, k + 1, n + k + 1, n + k) for k in range(n - 1)]), C['BLADES'], M['blade'],
            f'thermal blade re-aimed edge-on at the moved burn (turned up to {CO["blades"]["max_turn_deg"]:.0f} deg)')
# thin blankets: keep those not on the rewound coils
for o in bpy.data.collections['WORK_THERMAL_BLANKET_THIN'].objects:
    if not any(f'_{n}_' in o.name for n in ('C1', 'C2', 'L1')):
        C['BLANKET_KEPT'].objects.link(o)


def text(name, body, loc, size):
    cu = bpy.data.curves.new(name, 'FONT'); cu.body = body; cu.size = size; cu.align_x = 'CENTER'
    o = bpy.data.objects.new(name, cu); C['LABELS'].objects.link(o); o.location = loc; o.rotation_euler = (math.pi / 2, 0, 0)
    cu.materials.append(M['text'])
    return o


text('LBL_burn_moved', f'burn {BX0 - BX1:.0f} m aft (research)', (BX1, 0, -2.4), 0.7)
text('LBL_burn_drawn', 'drawn burn', (BX0, 0, 1.6), 0.5)
text('LBL_closure', 'closure coils rewound', (-14.8, 0, 8.4), 0.7)

# hide in OPTIMIZED: the approved C1/C2, the approved blades, the full thin-blanket set, the old burn label set
vl = opt.view_layers[0]


def exclude(lc, names):
    if lc is None:
        return
    for ch in lc.children:
        if ch.name in names:
            ch.exclude = True
        exclude(ch, names)


for _vl in orig.view_layers:
    exclude(_vl.layer_collection, {'WORK_THERMAL_MIRRORS_A', 'WORK_THERMAL_MIRRORS_D', 'WORK_THERMAL_BLANKET_C_ARCHIVED'})

cams = {o.name: o for o in bpy.data.objects if o.type == 'CAMERA'}
cd = bpy.data.cameras.new('CAM_opt_closure'); cd.lens = 30
cc = bpy.data.objects.new('CAM_opt_closure', cd); C['LABELS'].objects.link(cc)
cc.location = (-4.0, -19.0, 8.0); cc.rotation_euler = (Vector((-17.5, 0, 1.0)) - cc.location).to_track_quat('-Z', 'Y').to_euler()
cs = bpy.data.cameras.new('CAM_opt_side'); cs.type = 'ORTHO'; cs.ortho_scale = 34
cso = bpy.data.objects.new('CAM_opt_side', cs); C['LABELS'].objects.link(cso)
cso.location = (-20.0, -60.0, 2.0); cso.rotation_euler = (math.pi / 2, 0, 0)
cso2 = cso.copy(); orig.collection.objects.link(cso2); cso2.name = 'CAM_orig_side'
cc2 = cc.copy(); orig.collection.objects.link(cc2); cc2.name = 'CAM_orig_closure'
opt.camera = cams.get('CAM_overview') or cc
orig.camera = cams.get('CAM_overview') or cc2
bpy.context.window_manager.windows[0].scene = opt if bpy.context.window_manager.windows else None
out = HERE / 'REVIEW_OPTIMIZE.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True); print('saved', out, flush=True)
if RENDER:
    rd = Path('/mnt/project-files/fusion-optimize'); rd.mkdir(parents=True, exist_ok=True)
    shots = [('overview', 'CAM_overview', 'CAM_overview'), ('closure', 'CAM_opt_closure', 'CAM_orig_closure'), ('side', 'CAM_opt_side', 'CAM_orig_side')]
    for nm, co, cor in shots:
        for sc, cn, tag in ((opt, co, 'optimized'), (orig, cor, 'original')):
            sc.camera = bpy.data.objects[cn]; sc.render.filepath = str(rd / f'{tag}_{nm}.png')
            bpy.ops.render.render(write_still=True, scene=sc.name); print('rendered', tag, nm, flush=True)
    opt.camera = cams.get('CAM_overview') or cc; orig.camera = cams.get('CAM_overview') or cc2
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
