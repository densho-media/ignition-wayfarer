"""IND-001 study (step 2.2-2.4): human-scale whitebox variants of a ring sector, rendered side by side for the user to pick.

Each variant replaces one function's [interior.layouts] blocks in memory, is screened by habitat_interior.check (envelopes), sector_whitebox.check
(human scale, both gravity vectors, 12A program) and human_entry.check (the landing's leaf sweep and well), and is rendered on the shared sector
component (WF_RING_SECTOR, the sector frame) with its review mannequins: a plan from the spin axis, a section looking aft, a section with aft
down (rings stopped and locked for major thrust) and two eye-level views in coast. Nothing is saved and no asset changes; the pick goes into
[interior.layouts]. Workbench renders, material colours.

    /snap/bin/blender -b --python src/wayfarer/studies/induction_sectors.py -- --function HABITATION --out runs/<stamp>-induction-sectors
"""
from pathlib import Path
import argparse
import copy
import json
import math
import sys
import bpy
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation'), str(ROOT/'src/wayfarer/components')]
from common import material
from spec import load
import habitat_interior as hi
import human_entry as he
import sector_whitebox as sw
from interior_preview import frame, label
from interior import COLORS

WALL = 9.0       # an outer z beyond the wall: the block runs to the wall


def stack(n0, side, x, z=None, open_='aisle', lifts=(0.22, 1.03, 1.84), h=0.81, base=0.22):
    """Three berth tiers (Bunk_n0..) over a drawer base, one envelope each (the platform inside its bottom)."""
    zz = {} if z is None else {'z': z}
    return [dict(name=f'Bunk_{n0+k}', zone='bunk', side=side, x=x, open=open_, lift_m=l, height_m=h, **zz) for k, l in enumerate(lifts)]+[
        dict(name=f'Bunk_Base_{n0}', zone='stowage', side=side, x=x, lift_m=0.0, height_m=base, **zz)]


# The aft couches (0.70 m wide, 0.45 m deep with the occupant, the 0.30 m in front kept free) and personal lockers beside them on the aft
# bulkhead are common to every HABITATION variant.
COUCHES = [dict(name='Burn_Couch_1', zone='burn_couch', side=1, x=[-1.60, -1.15], z=[0.55, 1.25], lift_m=0.0, height_m=2.0),
           dict(name='Couch_Lockers_1', zone='stowage', side=1, x=[-1.60, -1.15], z=[1.30, WALL], lift_m=0.0, height_m=2.1),
           dict(name='Burn_Couch_2', zone='burn_couch', side=-1, x=[-1.60, -1.15], z=[0.55, 1.25], lift_m=0.0, height_m=2.0),
           dict(name='Couch_Lockers_2', zone='stowage', side=-1, x=[-1.60, -0.60], z=[1.30, WALL], lift_m=0.0, height_m=2.1)]
VARIANTS = {
    'HABITATION': {
        # H1: the current arrangement at human scale: one stack of three berths across the sector on each side, entered from the aisle end,
        # a hygiene compartment with a shelf over it.
        'H1': dict(title='Berths across the sector', layout=COUCHES+stack(1, 1, [-0.80, 0.20])+stack(4, -1, [0.60, 1.60])+[
            dict(name='Hygiene', zone='hygiene', side=1, x=[0.30, 1.60], lift_m=0.0, height_m=2.1),
            dict(name='Crew_Stowage_Upper', zone='stowage', side=1, x=[0.30, 1.60], lift_m=2.15, height_m=0.50)]),
        # H2: six berths along the spin axis on side +1, two columns of three: the inner column opens on the aisle, the outer one at its aft end
        # onto a sub-aisle that is also the couches' free strip; the hygiene compartment moves forward of the landing well.
        'H2': dict(title='Berths along the spin axis', layout=COUCHES+stack(1, 1, [-0.40, 1.60], [0.45, 1.40])+stack(4, 1, [-0.40, 1.60], [1.45, WALL], 'aft')+[
            dict(name='Hygiene', zone='hygiene', side=-1, x=[0.60, 1.60], lift_m=0.0, height_m=2.1),
            dict(name='Crew_Stowage_Upper', zone='stowage', side=-1, x=[0.60, 1.60], lift_m=2.15, height_m=0.50)]),
    },
    # Zone 7 (2.3): the couches as in HABITATION, and the ECLSS service bay (SP-15, with the Garden service SP-44 in it, 12A I47) on the forward
    # bulkhead of side -1, served from the strip between it and the landing well. Garden racks face the aisle or a sub-aisle, so the gardener
    # faces tangentially and nods about an axis parallel to the spin axis; the trays run along X and are closed and partitioned for aft-down.
    'LIFE_SUPPORT_GARDEN_COMMON': {
        # G1: Garden first: two 0.70 m rack columns on side +1 (the inner on the aisle, the outer on a 0.60 m sub-aisle entered from the couch
        # strip); no mess (SP-26 moves to another sector or ring).
        'G1': dict(title='Garden first', layout=COUCHES+[
            dict(name='Garden_Rack_1', zone='garden', side=1, x=[-0.40, 1.60], z=[0.45, 1.15], lift_m=0.0, height_m=2.0),
            dict(name='Garden_Rack_2', zone='garden', side=1, x=[-0.40, 1.60], z=[1.75, 2.45], open='inner', lift_m=0.0, height_m=2.0),
            dict(name='ECLSS_Bay', zone='life_support', side=-1, x=[1.10, 1.60], z=[0.45, WALL], open='aft', lift_m=0.0, height_m=2.1)]),
        # G2: the common room: a booth for six (benches along the spin axis, so diners face tangentially) behind a 0.50 m Garden rack on the
        # aisle, entered from the couch strip.
        'G2': dict(title='Mess behind a Garden wall', layout=COUCHES+[
            dict(name='Garden_Rack_1', zone='garden', side=1, x=[-0.55, 1.60], z=[0.45, 0.95], lift_m=0.0, height_m=2.0),
            dict(name='Mess', zone='common', side=1, x=[-0.55, 1.25], z=[0.95, WALL], open='aft', lift_m=0.0, height_m=1.40),
            dict(name='ECLSS_Bay', zone='life_support', side=-1, x=[1.10, 1.60], z=[0.45, WALL], open='aft', lift_m=0.0, height_m=2.1)]),
    },
    # Zone 8 (2.4): the couches as in HABITATION (every couch now carries a harness and armrest burn-go consoles, so the sector's two couches
    # are the burn station), a treatment couch along the spin axis (feet aft), a row of three operations stations (SP-39 to SP-41) and, on
    # side -1 forward of the landing well, the lab bench on the aisle and the workshop bench behind a strip off the well; every worker faces
    # tangentially.
    'WORK_MEDICAL_OPS': {
        # W1: the treatment couch on the aisle (the medic works from the aisle), three seated stations along the outer wall entered from the
        # couch strip, medical stowage over their displays.
        'W1': dict(title='Treatment couch on the aisle', layout=COUCHES+[
            dict(name='Medical_Couch', zone='medical', side=1, x=[-0.40, 1.60], z=[0.45, 1.15], lift_m=0.0, height_m=1.20),
            dict(name='Ops_Stations', zone='operations', side=1, x=[-0.40, 1.60], z=[1.20, WALL], open='aft', lift_m=0.0, height_m=1.60),
            dict(name='Medical_Stowage', zone='stowage', side=1, x=[-0.40, 1.60], z=[2.00, WALL], lift_m=1.65, height_m=0.85),
            dict(name='Lab_Bench', zone='laboratory', side=-1, x=[0.60, 1.60], z=[0.45, 1.05], lift_m=0.0, height_m=2.0),
            dict(name='Workbench', zone='workshop', side=-1, x=[0.60, 1.60], z=[1.65, 2.35], open='inner', lift_m=0.0, height_m=2.0)]),
        # W2: three standing stations on the aisle (the specialist stops face the route), the treatment couch behind them on the outer wall
        # with its own 0.60 m strip, medical stowage above it.
        'W2': dict(title='Ops on the aisle, medical behind', layout=COUCHES+[
            dict(name='Ops_Stations', zone='operations', side=1, x=[-0.40, 1.60], z=[0.45, 1.05], lift_m=0.0, height_m=1.90),
            dict(name='Medical_Couch', zone='medical', side=1, x=[-0.40, 1.60], z=[1.75, 2.45], open='inner', lift_m=0.0, height_m=1.20),
            dict(name='Medical_Stowage', zone='stowage', side=1, x=[-0.40, 1.60], z=[2.00, WALL], lift_m=1.95, height_m=0.65),
            dict(name='Lab_Bench', zone='laboratory', side=-1, x=[0.60, 1.60], z=[0.45, 1.05], lift_m=0.0, height_m=2.0),
            dict(name='Workbench', zone='workshop', side=-1, x=[0.60, 1.60], z=[1.65, 2.35], open='inner', lift_m=0.0, height_m=2.0)]),
    },
}
STEP = {'HABITATION': ('2.2', 'HABITATION'), 'LIFE_SUPPORT_GARDEN_COMMON': ('2.3', 'LIFE SUPPORT/GARDEN'), 'WORK_MEDICAL_OPS': ('2.4', 'WORK/MEDICAL/OPS')}
# Per view: projection, ortho scale or lens, view direction, up, target (ortho; y None = mid-height) or eye (perspective), caption.
CAMERAS = {
    'HABITATION': {
        'plan': ('ORTHO', 7.2, (0, 1, 0), (1, 0, 0), (0, None, 0), 'plan from the spin axis, fore up'),
        'section': ('ORTHO', 7.2, (-1, 0, 0), (0, -1, 0), (-0.30, None, 0), 'section looking aft (coast: radial floor)'),
        'burn': ('ORTHO', 4.6, (0, 0, 1), (1, 0, 0), (0, None, .95), 'section, aft down: rings stopped and locked for major thrust'),
        'eye_side': ('PERSP', 16, (-.42, .25, 1), (0, -1, 0), (0.0, -1.65, -1.75), 'eye level from the landing (coast)'),
        'eye_aft': ('PERSP', 16, (-1, .25, .05), (0, -1, 0), (1.45, -1.65, 0.0), 'eye level looking aft at the couches (coast)')},
    'LIFE_SUPPORT_GARDEN_COMMON': {
        'plan': ('ORTHO', 7.2, (0, 1, 0), (1, 0, 0), (0, None, 0), 'plan from the spin axis, fore up'),
        'section': ('ORTHO', 7.2, (-1, 0, 0), (0, -1, 0), (0.90, None, 0), 'section through the racks looking aft (coast: radial floor)'),
        'burn': ('ORTHO', 4.6, (0, 0, 1), (1, 0, 0), (0, None, .65), 'section through the aisle rack, aft down: rings stopped and locked'),
        'eye_side': ('PERSP', 16, (.40, .25, 1), (0, -1, 0), (0.0, -1.65, -1.35), 'eye level from the landing (coast)'),
        'eye_fore': ('PERSP', 16, (1, .25, 0), (0, -1, 0), (-0.95, -1.65, 0.0), 'eye level looking fore from the couches (coast)')},
    'WORK_MEDICAL_OPS': {
        'plan': ('ORTHO', 7.2, (0, 1, 0), (1, 0, 0), (0, None, 0), 'plan from the spin axis, fore up'),
        'section': ('ORTHO', 7.2, (-1, 0, 0), (0, -1, 0), (0.90, None, 0), 'section looking aft (coast: radial floor)'),
        'burn': ('ORTHO', 4.6, (0, 0, 1), (1, 0, 0), (0, None, .62), 'section through couch 1 and its console, aft down: rings stopped and locked'),
        'eye_side': ('PERSP', 16, (.40, .25, 1), (0, -1, 0), (0.0, -1.65, -1.35), 'eye level from the landing (coast)'),
        'eye_fore': ('PERSP', 16, (1, .25, 0), (0, -1, 0), (-0.95, -1.65, 0.0), 'eye level looking fore from the couches (coast)')},
}
HIDE = {'aisle': ('eye_side', 'eye_aft'), 'garden': ('eye_aft',)}      # mannequins that would block a view


def variant(s, function, layout):
    v = copy.deepcopy(s); v['interior']['layouts'][function] = layout; return v


def screen(s, function):
    env = hi.check(s); human = sw.check(s, function); entry = he.check(s)
    landing = [f for f in entry['failures'] if 'eaf' in f or 'anding' in f or 'well' in f]
    return dict(envelope=env['pass'], envelope_failures=env['failures'], human=human, landing_failures=landing,
                passed=env['pass'] and human['passed'] and not landing)


def rod(c, name, pts, r, mat):
    data = bpy.data.curves.new(name, 'CURVE'); data.dimensions = '3D'; data.bevel_depth = r; data.bevel_resolution = 3; data.use_fill_caps = True
    sp = data.splines.new('POLY'); sp.points.add(len(pts)-1)
    for p, co in zip(sp.points, pts):
        p.co = (*co, 1)
    obj = bpy.data.objects.new(name, data); c.objects.link(obj); data.materials.append(mat); return obj


def box(c, name, lo, hi_, mat):
    vs = [(x, y, z) for x in (lo[0], hi_[0]) for y in (lo[1], hi_[1]) for z in (lo[2], hi_[2])]
    fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update(); me.materials.append(mat)
    obj = bpy.data.objects.new(name, me); c.objects.link(obj); return obj


def render(function, keys, size, out):
    s, *_ = load(ROOT); sec = hi.section(s); out.mkdir(parents=True, exist_ok=True); report = {}
    bpy.ops.wm.read_factory_settings(use_empty=True); scene = bpy.context.scene
    with bpy.data.libraries.load(str(ROOT/'assets/wayfarer/components/WF_RING_SECTOR.blend'), link=True) as (_, dst):
        dst.collections = ['WF_RING_SECTOR']
    inst = bpy.data.objects.new('Study_Sector', None); inst.instance_type = 'COLLECTION'; inst.instance_collection = dst.collections[0]
    scene.collection.objects.link(inst)
    scene.render.engine = 'BLENDER_WORKBENCH'; scene.render.resolution_x = size; scene.render.resolution_y = round(size*.75)
    scene.render.image_settings.file_format = 'PNG'; sh = scene.display.shading
    sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True; sh.cavity_type = 'BOTH'; sh.show_shadows = True; sh.shadow_intensity = .35
    scene.world = bpy.data.worlds.new('W'); scene.world.color = (.05, .06, .08); sh.background_type = 'WORLD'
    cam = bpy.data.objects.new('Study_Camera', bpy.data.cameras.new('Study_Camera')); scene.collection.objects.link(cam); scene.camera = cam
    aspect = scene.render.resolution_x/scene.render.resolution_y; human = material('Study_Human', (1.0, .45, .05))
    crop, rack = material('Study_Crop', COLORS['garden']), material('Study_Garden_Rack', (.74, .76, .72))
    dark = material('Study_Console', (.16, .19, .23)); strap = material('Study_Strap', (.85, .62, .12))
    plate_mat = {z: material(f'Interior_{z.title()}', COLORS[z]) for z in ('deck', 'overhead')}
    for key in keys:
        spec_v = VARIANTS[function][key]; v = variant(s, function, spec_v['layout']); r = screen(v, function); report[key] = r
        c = bpy.data.collections.new(f'ART_STUDY_{key}'); scene.collection.children.link(c)
        plates = {b['zone']: box(c, b['name'], b['min'], b['max'], plate_mat[b['zone']]) for b in hi.plates(v)}
        blocks = hi.zones(v, function); tags = []
        for b in blocks:
            for q in sw.shapes(v, b):
                mat = (crop if q['part'].startswith('Crop') else rack if b['zone'] == 'garden' else dark if q['part'].startswith(('Console', 'Display'))
                       else strap if q['part'].startswith(('Strap', 'Lap_Belt')) else material(f'Interior_{b["zone"].title()}', COLORS.get(b['zone'], (.6, .6, .6))))
                box(c, q['name'], q['min'], q['max'], mat)
        hidden = []
        for pose, fg in sw.figures(v, blocks).items():
            for n, pts, rr in fg['rods']:
                o = rod(c, f'Human_{pose}_{n}', pts, rr, human)
                hidden += [(o, HIDE[pose])] if pose in HIDE else []
        for b in blocks:
            if b['name'] in ('Bunk_1', 'Bunk_4') or b['zone'] != 'bunk' and not b['name'].startswith(('Bunk_Base', 'Crew_Stowage_Upper', 'Medical_Stowage')):
                text = {'Bunk_1': 'Berths 1-3', 'Bunk_4': 'Berths 4-6'}.get(b['name'], b['name'].replace('_', ' ').replace('Burn ', ''))
                data = bpy.data.curves.new(f'Tag_{b["name"]}', 'FONT'); data.body = text; data.size = .13
                data.align_x = 'CENTER'; data.materials.append(material('Study_Tag', (1, 1, 1))); o = bpy.data.objects.new(data.name, data); c.objects.link(o)
                o.location = ((b['min'][0]+b['max'][0])/2, sec['ceiling_y_m']+.06, (b['min'][2]+b['max'][2])/2); o.rotation_euler = frame((0, 1, 0), (1, 0, 0))
                tags.append(o)
        h = r['human']; fails = r['envelope_failures']+h['failures']+r['landing_failures']
        if h['berths']:
            facts = (f"{len(h['berths'])} berths ({next(iter(h['berths'].values()))['axis']} axis), "
                     f"{len(h['couches'])} couches, envelopes {h['envelope_m3']:.1f} of {h['usable_m3']:.0f} m3 usable, "
                     f"12A fitted {', '.join(h['program_fitted']) or '-'}; missing {', '.join(h['program_missing']) or '-'}")
        elif h['operations'] or h['medical']:
            o = next(iter(h['operations'].values()), {}); m = next(iter(h['medical'].values()), {})
            facts = (f"{o.get('stations', 0)} {'standing' if o.get('standing') else 'seated'} ops stations; treatment couch {m.get('axis', '-')} axis; "
                     f"{sum(1 for r in h['racks'].values() if r['zone'] in ('workshop', 'laboratory'))} benches; burn-go console {h['burn_console']['reach_m']:.2f} m "
                     f"from the shoulder; 12A missing {', '.join(h['program_missing']) or '-'}")
        else:
            g = h['garden']; seats = sum(m['seats'] for m in h['mess'].values())
            facts = (f"Garden racks {g['racks_m3']:.1f} m3, {g['growing_m2']:.0f} m2 of trays ({g['ring_share_as_racks']:.0%} of "
                     f"{g['owner_per_ring_m3']:.0f} m3/ring read as racks); mess {seats} seats; 12A missing {', '.join(h['program_missing']) or '-'}")
        envelope = bpy.data.objects.get('Sector_Pressure_Envelope')       # translucent: it hazes the cut views
        for view in CAMERAS[function]:
            if envelope:
                envelope.hide_render = view in ('section', 'burn')
            for o in [o for o in scene.objects if o.name.startswith('Preview_Label')]:
                bpy.data.objects.remove(o, do_unlink=True)
            plates['overhead'].hide_render = view in ('plan',)
            for o in tags:
                o.hide_render = view != 'plan'
            for o, views in hidden:
                o.hide_render = view in views
            mid_y = (sec['deck_y_m']+sec['ceiling_y_m'])/2; d = cam.data
            kind, size, direction, up, target, caption = CAMERAS[function][view]
            if kind == 'ORTHO':
                d.type, d.ortho_scale = 'ORTHO', size; target = Vector((target[0], mid_y if target[1] is None else target[1], target[2]))
                cam.location = target-Vector(direction)*30; d.clip_start = 30+(sec['ceiling_y_m']-mid_y+.03 if view == 'plan' else 0)
            else:
                d.type, d.lens = 'PERSP', size; cam.location = Vector(target); d.clip_start = .05
            d.clip_end = 200; cam.rotation_euler = frame(direction, up)
            width = d.ortho_scale if d.type == 'ORTHO' else 2*.25*math.tan(d.angle_x/2)
            label(scene, cam, [f'WAYFARER 001 / IND-001 {STEP[function][0]}: {STEP[function][1]} {key}, {spec_v["title"].lower()}',
                               facts, f'{caption} | PROTOTYPE, not canon | ' + ('screens pass' if r['passed'] else f'{len(fails)} screen failures')],
                  width, aspect, d.clip_start+.05 if d.type == 'ORTHO' else .25)
            scene.render.filepath = str(out/f'sector_{function.lower()}_{key}_{view}.png'); bpy.ops.render.render(write_still=True)
            print(f'WF_INDUCTION_STUDY {function} {key} {view}', flush=True)
        for o in list(c.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(c)
    (out/f'sector_{function.lower()}_screens.json').write_text(json.dumps(report, indent=1, default=float)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--function', default='HABITATION'); p.add_argument('--variants', nargs='+')
    p.add_argument('--size', type=int, default=640); p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    out = a.out if a.out.is_absolute() else ROOT/a.out
    render(a.function, a.variants or list(VARIANTS[a.function]), a.size, out)
