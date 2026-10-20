"""M5 slice 5: restrained lettering and identification variants, revised to the owner's Year 155 direction (S&E 15!A216
OWN-M5-LETTER, 98!A119, Art Style Bible Spacecraft!A17, 2026-10-18): on-hull working label "GU WAYFARER 001" (GU, Y12-310, is the
Y155 institution; no G.U.C. on the hull), two monochrome off-white / charcoal treatments with no crest, and one annotated registry
proposal "GU-WF-001" that is strictly an ARTISTIC PROTOTYPE graphic test string, not an issued registry. Y155 LOOK DIRECTION /
REGISTRY NONCANON: nothing enters the vehicle, the exterior stays proxy grey with the M4 functional marks (15!H120). The legacy
project title "G.U.C. Wayfarer 001" is not changed here (pending the owner's naming review).

Function: let the owner compare how much identification the hull can carry before it stops reading as a working machine. Fixed: the
built hull (aft casing, forward collar), its seam lines (long seams every 30 deg from 15 deg), the blade roots at 30/150/270 deg, the
access panels, airlock and docks, and the two M4 grammar colours that already exist (off-white of the dishes and root boots, dark of the
joints). Unknown (OPEN, never chosen here): an issued registry or serial, any emblem or heraldry, the final typeface, a crew or
service-labelling standard.
Design freedom (PROTOTYPE, this file): where and how large; the typeface is Blender's built-in sans standing in for the owner's
"restrained uppercase modular industrial sans".

Variants:
  L1  Y155 name band: "GU WAYFARER 001" on one line, 2.0 m off-white letters, once on each face between the blade roots (90/210/330 deg).
  L2  Y155 stacked stencil: "GU" over "WAYFARER" (0.6 / 0.9 m charcoal) at the forward end of each face, a 2.5 m charcoal "001" aft.
  L3  service identification only: dark 0.2 m IDs beside the 45 casing access panels, "EVA AIRLOCK" at the airlock and "DOCK P" /
      "DOCK S" beside the two docks. No name.
  R1  annotated registry-format proposal: 0.15 m charcoal "GU-WF-001" production decals beside both docks and on the aft service
      casing, human-scale inspection only; every object carries the ARTISTIC PROTOTYPE / not-an-issued-registry annotation.

    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/m5_lettering.py   # placements on the measured skin, obstruction
        screen -> references/m5_lettering.json, study asset assets/wayfarer/studies/WF_STUDY_LETTERING.blend
"""
from pathlib import Path
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/studies'), str(ROOT/'src/wayfarer/shots')]

OUT_JSON = ROOT/'references/m5_lettering.json'
ASSET = ROOT/'assets/wayfarer/studies/WF_STUDY_LETTERING.blend'
COLLECTION = 'WF_STUDY_LETTERING'
COLOR = dict(offwhite=(.80, .78, .72), dark=(.16, .19, .22))   # the existing M4 grammar colours (exterior.py), no new colour
LIFT = 0.02                 # letters sit this far above the highest skin point under them (paint is ~0; lifted only to render)
OBSTRUCTION = 0.05          # anything under the footprint higher than the skin by more than this is an obstruction (straps are 0.015)
FACES = (90.0, 210.0, 330.0)
VARIANTS = ('L1', 'L2', 'L3', 'R1')
R_HULL = 6.3                # nominal skin radius for stacking lines (the wrap uses the measured skin)
REGISTRY_NOTE = 'GU-WF-001: ARTISTIC PROTOTYPE graphic test string, not an issued government registry (S&E 15!A216, 98!A119)'


def above(az, d):
    """Azimuth of a line d metres above (letter-up) a line at az, matching wrap(): up is decreasing azimuth unless the text is flipped."""
    up = 1.0 if math.cos(math.radians(az)) > 1e-6 else -1.0
    return az + up*math.degrees(d/R_HULL)


def placements(s):
    import casing_panels as cp
    out = []
    for a in FACES:
        out.append(dict(variant='L1', name=f'Letter_L1_Name_{a:03.0f}', text='GU WAYFARER 001', x=10.0, az=a, height=2.0, color='offwhite',
                        why='Y155 working label (15!A216), one line, once per face between the blade roots'))
        out.append(dict(variant='L2', name=f'Letter_L2_Registry_{a:03.0f}', text='WAYFARER', x=66.0, az=a, height=0.9, color='dark',
                        why='Y155 stacked stencil (15!A216): the name line at the forward end of the face'))
        lead = 2.65 if math.cos(math.radians(a)) <= 1e-6 else -2.65     # left-aligned with WAYFARER in its reading direction
        out.append(dict(variant='L2', name=f'Letter_L2_GU_{a:03.0f}', text='GU', x=66.0-lead, az=above(a, 0.9), height=0.6, color='dark',
                        why='Y155 stacked stencil: the institution line (GU, Y12-310) above the name'))
        out.append(dict(variant='L2', name=f'Letter_L2_Number_{a:03.0f}', text='001', x=-86.0, az=a, height=2.5, color='dark',
                        why='hull number at the aft end of the face, readable from the thrust-ring service side'))
    for p in cp.access_panels(s):
        st, az = p['name'].split('_')[-2:]
        out.append(dict(variant='L3', name=f'Letter_L3_{p["name"]}', text=f'AP {st}-{az}', x=p['x']+p['size'][0]/2+0.55, az=math.degrees(p['theta']),
                        height=0.2, color='dark', why='access-panel identification beside the cover'))
    out.append(dict(variant='L3', name='Letter_L3_Airlock', text='EVA AIRLOCK', x=104.6, az=50.0, height=0.3, color='dark',
                    why='airlock identification forward of the SP-11 hatch keep-out'))
    out.append(dict(variant='L3', name='Letter_L3_Dock_P', text='DOCK P', x=96.2, az=195.0, height=0.4, color='dark',
                    why='primary dock identification aft of its corridor keep-out'))
    out.append(dict(variant='L3', name='Letter_L3_Dock_S', text='DOCK S', x=96.2, az=315.0, height=0.4, color='dark',
                    why='service dock identification aft of its corridor keep-out'))
    # The dock stencils sit on the 195/315 deg long seams; the decal goes one line below them, clear of the seam.
    for name, x, az, why in (('Dock_P', 96.2, above(195.0, -0.55), 'beside the primary dock, below its DOCK P stencil'),
                             ('Dock_S', 96.2, above(315.0, -0.55), 'beside the service dock, below its DOCK S stencil'),
                             ('Aft_Casing', -98.0, above(0.0, -0.35), 'aft service casing, beside the access-panel row')):
        out.append(dict(variant='R1', name=f'Letter_R1_Registry_{name}', text='GU-WF-001', x=x, az=az, height=0.15, color='dark',
                        why=f'registry-format proposal decal {why}; human-scale inspection only', annotation=REGISTRY_NOTE))
    return out


def text_mesh(name, text, height):
    """Flat text mesh in local XY (reading along +X, letters up +Y), centred; cap height ~ `height`."""
    import bpy
    cu = bpy.data.curves.new(name, 'FONT'); cu.body = text; cu.size = height/0.72; cu.align_x = 'CENTER'; cu.align_y = 'CENTER'
    cu.extrude = 0.004
    ob = bpy.data.objects.new(name+'_tmp', cu); bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get(); me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob); bpy.data.curves.remove(cu); me.name = name
    xs = [v.co.x for v in me.vertices]; ys = [v.co.y for v in me.vertices]
    return me, (max(xs)-min(xs), max(ys)-min(ys))


def wrap(me, x, az, r):
    """Paint the flat text onto the hull cylinder in ship coordinates: local X -> ship +X, local Y (letter up) -> arc length toward
    n x X (decreasing azimuth, so the text reads upright from outside), local Z -> radius r + z. Where n x X points ventral the text
    is turned 180 deg in the surface: every side marking stands dorsal-up, reading forward on the -Y side and aft on the +Y side."""
    flip = math.cos(math.radians(az)) > 1e-6   # n x X points ventral here: turn the text 180 deg so letters stand dorsal-up (reads aft)
    for v in me.vertices:
        lx, ly, lz = v.co
        if flip:
            lx, ly = -lx, -ly
        a = math.radians(az)-ly/r; rr = r+lz
        v.co = (x+lx, rr*math.cos(a), rr*math.sin(a))
    me.update()


def measure(s, plist):
    """Skin radius under each footprint (5 x 9 radial rays into one BVH of the vehicle) and the highest obstruction above it."""
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    import shot_tools
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sizes = {}
    for p in plist:
        me, wh = text_mesh(p['name'], p['text'], p['height']); sizes[p['name']] = wh; bpy.data.meshes.remove(me)
    src = {'asset': 'WF_WAYFARER_001.blend', 'collection': 'WF_WAYFARER_001', 'group': 'assembly'}
    vs, fs, names = [], [], []
    skip = ('scale_reference', 'plasma', 'magnetic_field', 'optical_beam', 'hull_envelope', 'eva_*')
    for it in shot_tools.gather(shot_tools.link_source(ROOT, src), src):
        ob = it['obj']
        if ob.type != 'MESH' or it['kind'] in skip or it['name'].startswith(('Engineering_Envelope', 'Tank_Volume')):
            continue
        if math.hypot(*it['center'][1:]) > 14+it['radius']:
            continue
        W = it['matrix']; b = len(vs); vs += [W@v.co for v in ob.data.vertices]
        for poly in ob.data.polygons:
            fs.append(tuple(b+i for i in poly.vertices)); names.append(it['name'])
    bvh = BVHTree.FromPolygons(vs, fs)
    res = {}
    for p in plist:
        w, h = sizes[p['name']]; hits = []
        for i in range(9):
            for j in range(5):
                dx = -w/2+w*i/8; dt = -h/2+h*j/4
                a = math.radians(p['az'])+dt/6.3; n = Vector((0, math.cos(a), math.sin(a)))
                o = Vector((p['x']+dx, 0, 0))+12.0*n
                hit = bvh.ray_cast(o, -n, 12.0)
                if hit[0] is not None:
                    hits.append((12.0-hit[3], names[hit[2]]))
        rs = sorted(r for r, _ in hits); skin = rs[len(rs)//2] if rs else None
        top = max(hits) if hits else (None, None)
        res[p['name']] = dict(width_m=round(w, 3), height_m=round(h, 3), rays=len(hits), skin_r_m=None if skin is None else round(skin, 3),
                              top_r_m=None if top[0] is None else round(top[0], 3), top_object=top[1],
                              obstructed=bool(skin is not None and top[0]-skin > OBSTRUCTION) or len(hits) < 45)
    return res


def build_asset(plist, meas):
    import bpy
    from common import material
    bpy.ops.wm.read_factory_settings(use_empty=True)
    root = bpy.data.collections.new(COLLECTION); bpy.context.scene.collection.children.link(root)
    root['study'] = 'm5_lettering'; root['status'] = 'Y155 LOOK DIRECTION / REGISTRY NONCANON (15!A216): GU WAYFARER 001 working label; GU-WF-001 artistic prototype only'
    cols = {}
    for v in VARIANTS:
        cols[v] = bpy.data.collections.new(f'{COLLECTION}_{v}'); root.children.link(cols[v])
    mats = {k: material(f'STUDY_Lettering_{k}', c) for k, c in COLOR.items()}
    for p in plist:
        m = meas[p['name']]
        if m['top_r_m'] is None:
            continue
        me, _ = text_mesh(p['name'], p['text'], p['height']); me.materials.append(mats[p['color']])
        wrap(me, p['x'], p['az'], m['top_r_m']+LIFT)
        ob = bpy.data.objects.new(p['name'], me); cols[p['variant']].objects.link(ob)
        ob['kind'] = f'lettering_{p["variant"].lower()}'; ob['variant'] = p['variant']; ob['text'] = p['text']; ob['note'] = p['why']
        ob['geometry_status'] = 'PROTOTYPE'; ob['canon_status'] = 'NONCANON review variant'; ob['study'] = 'm5_lettering'
        ob['component_id'] = f'WF.STUDY.LETTERING.{p["name"]}'
        if 'annotation' in p:
            ob['annotation'] = p['annotation']
    ASSET.parent.mkdir(parents=True, exist_ok=True); bpy.ops.wm.save_as_mainfile(filepath=str(ASSET), compress=True)


def main():
    from spec import load
    s = load(ROOT)[0]; plist = placements(s); meas = measure(s, plist); build_asset(plist, meas)
    rows = [dict(p, **meas[p['name']]) for p in plist]
    summary = {v: dict(items=sum(r['variant'] == v for r in rows), obstructed=[r['name'] for r in rows if r['variant'] == v and r['obstructed']],
                       letter_area_m2=round(sum(r['width_m']*r['height_m'] for r in rows if r['variant'] == v), 1)) for v in VARIANTS}
    OUT_JSON.write_text(json.dumps(dict(status='Y155 LOOK DIRECTION / REGISTRY NONCANON (S&E 15!A216, 98!A119, Art Style Spacecraft!A17)',
                                        registry=REGISTRY_NOTE, colors=COLOR, summary=summary, placements=rows), indent=1)+'\n')
    print(json.dumps(summary, indent=1))
    for r in rows:
        if r['obstructed']:
            print('obstructed', r['name'], r['skin_r_m'], r['top_r_m'], r['top_object'], r['rays'])


if __name__ == '__main__':
    main()
