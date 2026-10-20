"""M5 functional ship cutaway, slice 1 (owner directive 2026-10-18): the BODY-001 tank architectures re-screened against
S&E 62_FUEL_STORAGE_STUDY, a reversible BODY-C prototype study asset and the subsystem map. NONCANON; nothing in the vehicle changes.

Function: show how the stationary body would hold fusion fuel and reaction mass, with every family, temperature regime and support
function as a separate measured envelope, and show what does not fit. Fixed: the measured bay X -57.5..81.25 m, r 1.025-4.721 m
(tank_bay_survey), the cage, keels, spine, aft equipment and all built assemblies (body_architecture.py). Source numbers (S&E 62,
2026-10-18): He-3 164.8 t, D 110.1 t (IDEAL MIN, 100 % reacting-pair burnup), first-burn other exhaust 145.1 t and 180 t unspent,
both as H2 (HYPOTHESIS); liquid densities H2 70.8, D2 175.2, He-3 58.61 kg/m3 (REFERENCE). Unknown (OPEN, never chosen here):
inventory, species split, burnup and recycle, storage state, tank and insulation mass, heat leak, cooler power, dose (15!A200).
Design freedom (PROTOTYPE judgment, this file): the family order, the per-family wall allowance, the support, lane, utility-frame
and equipment-bay subdivision. 62 warns not to apply a packing factor twice: the BODY-001 volumes are NET liquid (wall/insulation
allowance and 5 % ullage already removed), so they compare with 62's liquid volumes, and the tank envelopes with 62's envelopes.

    python3 src/wayfarer/studies/m5_cutaway.py                     # numbers -> references/m5_body_c.json
    /snap/bin/blender -b --python src/wayfarer/studies/m5_cutaway.py -- --asset   # + study asset assets/wayfarer/studies/WF_STUDY_BODY_C.blend
                                                                                  #   and the overlap screen against the saved vehicle
    python3 src/wayfarer/studies/m5_cutaway.py --map               # + references/m5_subsystem_map.json (needs a Blender --asset run first)
"""
from pathlib import Path
import argparse
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/studies'), str(ROOT/'src/wayfarer/shots')]
import body_architecture as ba

OUT_JSON = ROOT/'references/m5_body_c.json'
MAP_JSON = ROOT/'references/m5_subsystem_map.json'
ASSET = ROOT/'assets/wayfarer/studies/WF_STUDY_BODY_C.blend'
COLLECTION = 'WF_STUDY_BODY_C'

# S&E 62_FUEL_STORAGE_STUDY (read 2026-10-18): densities REFERENCE, masses as labelled there.
DENSITY = dict(HE3=58.61, D2=175.2, H2=70.8)
MASS_T = dict(HE3=164.8, D2=110.1, H2_FIRST=145.1, H2_RESERVE=180.0)
S62 = dict(liquid_total_m3=8032, envelope_075_m3=10710, first_ignition_liquid_m3=5490, first_ignition_envelope_m3=7320,
           no_recycle_liquid_m3=12250, utilization=0.75)
TEMP_K = dict(HE3=3.2, D2=20.0, H2=20.0)

# PROTOTYPE judgment (this file).
WALL = dict(HE3=0.30, D2=0.15, H2=0.15)   # He-3 at 3.2 K: vacuum jacket + 20 K thermal shield + MLI; D2/H2 as BODY-001
ORDER = ('HE3', 'D2', 'H2')               # fill order forward -> aft: He-3 farthest from the core (thermal-neutron absorber)
LANE_CLEAR_R = 3.90                       # crawler clear space in each keel lane, r_in..3.90; feed manifold r 4.00-4.55
MANIFOLD = (4.00, 4.55)
SUPPORT_T = 0.30                          # inter-module support bulkhead thickness (in the 1 m module gap, lanes only)
EQUIPMENT = (('power_conversion', 70.0, '34: power converters and battery pack envelopes'),
             ('nav_radio_lasercom', 40.0, '34: navigation computer / radio / lasercom'),
             ('rcs_propellant_valves', 45.0, '34: RCS propellant / valves (S02-Q3 OPEN)'),
             ('coolant_exchangers', 75.0, '34: warm/cold coolant exchangers and pumps'),
             ('power_data_trunks', 50.0, '34: power/data trunks and valves'),
             ('momentum_storage', None, 'CMG / wheels, ~100,800 N m s bound (S02 report); size OPEN, 2.0 m reserved'))
CMG_RESERVE_M = 2.0


def liquid_need():
    """62's liquid volumes per family from its masses and densities (checked against the 62 rows)."""
    v = {k: MASS_T[k]*1000/DENSITY['H2' if k.startswith('H2') else k] for k in MASS_T}
    v['H2'] = v['H2_FIRST']+v['H2_RESERVE']
    first = v['HE3']+v['D2']+v['H2_FIRST']
    return {k: round(x, 1) for k, x in v.items()} | dict(total=round(v['HE3']+v['D2']+v['H2'], 1), first_ignition=round(first, 1))


def envelope_volume(o):
    """Outer tank-envelope volume of an option (before wall/insulation and ullage): what 62's 75 % utilization would apply to."""
    L = ba.MODULE-ba.GAP
    if o['key'] == 'A':
        return sum(math.pi*t['R']**2*L for t in o['tanks'])
    span = 360.0 if o['key'] == 'B' else 120-ba.LANE_DEG
    return len(o['tanks'])*math.radians(span)/2*(o['r_out']**2-o['r_in']**2)*L


def conventions():
    """A/B/C in all three conventions against 62: bay gross, tank envelope, net liquid."""
    need = liquid_need(); b = ba.bay(); out = {}
    for k in 'ABC':
        o = ba.option(k); env = envelope_volume(o); net = o['usable_m3']
        gross = math.pi*(b['r_out']**2-b['r_in']**2)*(o['tank_x1']-o['tank_x0'])
        out[k] = dict(bay_gross_m3=round(gross), tank_envelope_m3=round(env), net_liquid_m3=net,
                      net_over_envelope=round(net/env, 3),
                      liquid_margin_m3=round(net-need['total']), first_ignition_liquid_margin_m3=round(net-need['first_ignition']),
                      envelope_margin_vs_62_m3=round(env-S62['envelope_075_m3']),
                      share_of_total_liquid=round(net/need['total'], 3), share_of_first_ignition=round(net/need['first_ignition'], 3),
                      net_excludes='walls+insulation allowance, 5 % ullage, head/end knuckles' + ('' if k == 'B' else ', lanes/gaps between tanks'),
                      not_in_any='supports, pumps, refrigeration, vents, access (utility frames and lanes are separate envelopes)')
    return out


def lobe(x0, x1, ri, ro, a0, a1, wall):
    """Inner vessel of a lobe envelope: wall allowance on every face, end knuckles as BODY-001; volume net of ullage."""
    a, c = ri+wall, ro-wall; x0, x1 = x0+ba.END_ALLOW, x1-ba.END_ALLOW
    da = math.degrees(wall/((a+c)/2))
    vol = math.radians(a1-a0-2*da)/2*(c*c-a*a)*(x1-x0)*(1-ba.ULLAGE)
    return dict(x0=x0, x1=x1, ri=a, ro=c, a0=a0+da, a1=a1-da, net_m3=vol)


def body_c(assign=None):
    """`assign` (optional): {(module index, keel deg): family} for a lobe-by-lobe layout (M5 BODY-C2); default the module rule below.
    The revised option C: families by module (fore -> aft He-3, D2, H2), each lobe an inner vessel inside its insulation envelope,
    supports, keel lanes with manifolds, utility frames split by function, the equipment bay by the 34 envelopes, the workshop
    fallback and the spine tunnel. Every part is a separate, non-overlapping envelope (screened in Blender)."""
    o = ba.option('C'); need = liquid_need(); mods = o['modules']; ri, ro = o['r_in'], o['r_out']
    span = 120-ba.LANE_DEG; parts = []

    def part(name, kind, sub, x0, x1, r0, r1, a0=0.0, a1=360.0, note='', **kw):
        parts.append(dict(name=name, kind=kind, subsystem=sub, x0=round(x0, 3), x1=round(x1, 3), ri=round(r0, 3), ro=round(r1, 3),
                          a0=round(a0, 3), a1=round(a1, 3), note=note, gross_m3=round(math.radians(a1-a0)/2*(r1*r1-r0*r0)*(x1-x0), 1), **kw))
    # family per module: fill He-3 then D2 from the forward module aft; whatever remains is H2
    per = {f: lobe(0, ba.MODULE-ba.GAP, ri, ro, 0, span, WALL[f])['net_m3']*3 for f in WALL}
    fam, left, i = [], dict(HE3=need['HE3'], D2=need['D2']), len(mods)-1
    for f in ('HE3', 'D2'):
        while left[f] > 0 and i >= 0:
            fam.insert(0, f); left[f] -= per[f]; i -= 1
    fam = ['H2']*(i+1)+fam
    cap = {f: 0.0 for f in WALL}
    for m, (mod, f0) in enumerate(zip(mods, fam)):
        for k in ba.KEELS:
            f = assign[(m, k)] if assign else f0
            mid = k+60; a0, a1 = mid-span/2, mid+span/2
            v = lobe(mod['x0'], mod['x1'], ri, ro, a0, a1, WALL[f]); cap[f] += v['net_m3']
            kind = dict(HE3='he3_cryostat', D2='d2_cryostat', H2='h2_tank')[f]
            part(f'Study_{f}_Vessel_{m:02}_{mid:.0f}', kind, 'S05' if f != 'H2' else 'S06', v['x0'], v['x1'], v['ri'], v['ro'], v['a0'], v['a1'],
                 f'{f} inner vessel at {TEMP_K[f]:g} K, net {v["net_m3"]:.1f} m3 at 5 % ullage', family=f, net_m3=round(v['net_m3'], 1))
            # insulation envelope: the wall/insulation allowance as a shell of four slabs round the vessel (no overlap with it)
            w = WALL[f]; tag = f'Study_{f}_Jacket_{m:02}_{mid:.0f}'; note = f'{f} insulation / vacuum jacket allowance {w:g} m (PROTOTYPE)'
            part(tag+'_Outer', 'insulation_envelope', 'S07', v['x0'], v['x1'], v['ro'], ro, a0, a1, note)
            part(tag+'_Inner', 'insulation_envelope', 'S07', v['x0'], v['x1'], ri, v['ri'], a0, a1, note)
            part(tag+'_Flank0', 'insulation_envelope', 'S07', v['x0'], v['x1'], v['ri'], v['ro'], a0, v['a0'], note)
            part(tag+'_Flank1', 'insulation_envelope', 'S07', v['x0'], v['x1'], v['ri'], v['ro'], v['a1'], a1, note)
            part(tag+'_Aft', 'insulation_envelope', 'S07', mod['x0'], v['x0'], ri, ro, a0, a1, note+'; bulkhead knuckle')
            part(tag+'_Fwd', 'insulation_envelope', 'S07', v['x1'], mod['x1'], ri, ro, a0, a1, note+'; bulkhead knuckle')
    # module gaps: support bulkheads in the lanes (lobes hang from the keels at frame stations), and the utility frames
    for a, c in zip(mods, mods[1:]):
        g0 = a['x1']
        if c['x0']-a['x1'] > ba.GAP+.1:
            u0, u1 = a['x1']+ba.GAP/2, c['x0']-ba.GAP/2
            for k, (kind, use) in zip(ba.KEELS, (('refrigeration_frame', 'cryocooler cold heads + He-3 / H2 refrigeration'),
                                                ('transfer_pump_frame', 'transfer and feed pumps, isolation valves'),
                                                ('vent_frame', 'relief vents, boil-off recovery, purge'))):
                part(f'Study_{kind}_{u0:.0f}', kind, 'S07', u0, u1, ri, ro, k+60-span/2, k+60+span/2, f'{use} (utility frame, 34 tank-bay overhead)')
        for k in ba.KEELS:
            part(f'Study_Support_{g0:.0f}_{k:.0f}', 'tank_support', 'S02', g0+(ba.GAP-SUPPORT_T)/2, g0+(ba.GAP+SUPPORT_T)/2, ri, LANE_CLEAR_R,
                 k-ba.LANE_DEG/2, k+ba.LANE_DEG/2, 'support bulkhead to the keel rail (lobe saddles), PROTOTYPE')
    x0, x1 = mods[0]['x0'], mods[-1]['x1']
    for k in ba.KEELS:
        part(f'Study_Lane_{k:.0f}', 'service_lane', 'S12', x0, x1, ri, LANE_CLEAR_R, k-ba.LANE_DEG/2, k+ba.LANE_DEG/2,
             'keel lane: crawler inspection clear space (support bulkheads are cut out of it)', segmented=True)
        part(f'Study_Manifold_{k:.0f}', 'transfer_manifold', 'S07', x0, x1, *MANIFOLD, k-ba.LANE_DEG/2, k+ba.LANE_DEG/2,
             'feed / fill / vent manifold bundle and cold-head lines in the lane')
    # equipment bay: the 34 fore envelopes as annulus slices, then the CMG reserve, then unallocated
    zones = {z['id']: z for z in o['zones']}; eq = zones['equipment_bay']; area = math.pi*(ro*ro-ri*ri); x = eq['x0']
    for name, vol, use in EQUIPMENT:
        L = CMG_RESERVE_M if vol is None else vol/area
        part(f'Study_Equip_{name}', 'equipment_envelope', 'S08', x, x+L, ri, ro, note=use+('' if vol is None else f', {vol:g} m3'), envelope_m3=vol)
        x += L
    part('Study_Equip_unallocated', 'equipment_envelope', 'S08', x, eq['x1']-.2, ri, ro, note='unallocated reserve (no qualified use, 15!A114)')
    ws = zones['workshop_fallback']
    part('Study_Workshop_Fallback', 'service_workshop', 'S12', ws['x0'], ws['x1']-.2, ri, ro, note=ws['use'])
    part('Study_Spine_Tunnel', 'spine_tunnel', 'S12', -72.0, 81.35, 0.80, ba.SPINE_TUNNEL_R,
         note='crew/robot tunnel, 0.80 m clear, in a 1.9 m spine core (spine r 0.875 -> 0.95 over the bay: documented conflict)')
    # shortfall at scale: the unhoused volumes as the length of C-section tank train they would need (NOT a location)
    per_m = (cap['HE3']+cap['D2']+cap['H2'])/(x1-x0)
    short = dict(HE3=max(0, need['HE3']-cap['HE3']), D2=max(0, need['D2']-cap['D2']))
    h2_first = max(0.0, need['H2_FIRST']-cap['H2']); h2_res = need['H2_RESERVE']-max(0.0, cap['H2']-need['H2_FIRST'])
    bars, xb = [], x1
    for key, vol in (('first_burn_H2', h2_first), ('reserve_H2', h2_res), ('HE3', short['HE3']), ('D2', short['D2'])):
        if vol > 1:
            L = vol/per_m
            bars.append(dict(id=key, volume_m3=round(vol), equivalent_C_length_m=round(L, 1), x0=round(xb-L, 2), x1=round(xb, 2)))
            xb -= L+2
    alloc = dict(modules=[dict(x0=m['x0'], x1=m['x1'], family=f if not assign else [assign[(n, k)] for k in ba.KEELS]) for n, (m, f) in enumerate(zip(mods, fam))],
                 capacity_m3={f: round(v) for f, v in cap.items()}, per_module_m3={f: round(v) for f, v in per.items()},
                 need_m3={k: need[k] for k in ('HE3', 'D2', 'H2_FIRST', 'H2_RESERVE')},
                 housed_first_ignition_m3=round(min(need['HE3'], cap['HE3'])+min(need['D2'], cap['D2'])+min(need['H2_FIRST'], cap['H2'])),
                 unhoused_first_ignition_m3=round(short['HE3']+short['D2']+h2_first), unhoused_reserve_m3=round(max(0.0, h2_res)),
                 net_per_train_metre_m3=round(per_m, 2), train_length_m=round(x1-x0, 2),
                 total_need_train_length_m=round(need['total']/per_m, 1), first_ignition_train_length_m=round(need['first_ignition']/per_m, 1))
    return dict(parts=parts, allocation=alloc, shortfall_bars=bars)


def report():
    return dict(study='M5 slice 1: BODY architecture re-screen against S&E 62 (NONCANON; PROTOTYPE envelopes; nothing in the vehicle changed)',
                source='S&E 62_FUEL_STORAGE_STUDY 2026-10-18 (IDEAL MIN / HYPOTHESIS rows), 28 col E, 30, 34, 15!A200',
                density_kg_m3=DENSITY, mass_t=MASS_T, temperature_K=TEMP_K, s62=S62, wall_m=WALL, need_m3=liquid_need(),
                conventions=conventions(), body_c=body_c())


# ---------------------------------------------------------------- Blender: study asset + overlap screen

COLOR = dict(he3_cryostat=(.62, .38, .85), d2_cryostat=(.95, .52, .62), h2_tank=(.55, .78, .95), insulation_envelope=(.85, .82, .70),
             tank_support=(.45, .45, .48), service_lane=(.92, .92, .90), transfer_manifold=(.95, .56, .17), refrigeration_frame=(.95, .56, .17),
             transfer_pump_frame=(.95, .62, .25), vent_frame=(.95, .50, .12), equipment_envelope=(.35, .63, .31), service_workshop=(.80, .90, .80),
             spine_tunnel=(.92, .92, .90), shortfall_scale=(.85, .25, .22))


def segments(p, supports):
    """A lane's clear space between its support bulkheads (axial pieces)."""
    cuts = sorted((s['x0'], s['x1']) for s in supports if abs(((s['a0']+s['a1'])/2-(p['a0']+p['a1'])/2+180) % 360-180) < 1)
    out, x = [], p['x0']
    for a, b in cuts:
        out.append((x, a)); x = b
    return out+[(x, p['x1'])]


def build_asset(res, asset=ASSET, collection=COLLECTION, study='m5_body_c', status='STUDY / NONCANON: PROTOTYPE envelopes, not a released tank installation'):
    import bpy
    from common import material
    bpy.ops.wm.read_factory_settings(use_empty=True)
    col = bpy.data.collections.new(collection); bpy.context.scene.collection.children.link(col)
    col['study'] = study; col['status'] = status
    mats = {k: material(f'STUDY_{k}', c) for k, c in COLOR.items()}
    parts = res['body_c']['parts']; supports = [p for p in parts if p['kind'] == 'tank_support']; made = []

    def add(name, p, x0, x1, seg=None):
        span = p['a1']-p['a0']; seg = seg or max(2, int(span/6))
        ob = ba.lobe_mesh(name, x0, x1, p['ri'], p['ro'], p['a0'], p['a1'], seg); col.objects.link(ob)
        ob.data.materials.append(mats[p['kind']])
        for k in ('kind', 'subsystem', 'note'):
            ob[k] = p[k]
        ob['component_id'] = f'WF.STUDY.{collection[9:]}.{name}'; ob['geometry_status'] = 'PROTOTYPE'; ob['study'] = study
        ob['source_ref'] = 'S&E 62 / BODY-001 option C'; ob['envelope'] = [x0, x1, p['ri'], p['ro'], p['a0'], p['a1']]; made.append(ob)
    for p in parts:
        if p.get('segmented'):
            for n, (a, b) in enumerate(segments(p, supports)):
                add(f'{p["name"]}_{n}', p, a, b)
        else:
            add(p['name'], p, p['x0'], p['x1'], 48 if p['a1']-p['a0'] >= 360 else None)
    for b in res['body_c']['shortfall_bars']:
        p = dict(kind='shortfall_scale', subsystem='S06', ri=1.10, ro=4.721, a0=0.0, a1=360.0,
                 note=f'UNHOUSED {b["id"]}: {b["volume_m3"]} m3 = {b["equivalent_C_length_m"]} m of C tank train. Scale comparison only, NOT a tank location')
        add(f'Study_Shortfall_{b["id"]}', p, b['x0'], b['x1'], 48)
        made[-1].location.z = -52.0
    asset.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(asset), compress=True)
    return [o.name for o in made]


EPS = 0.01


def shell(x0, x1, ri, ro, a0, a1, seg=24):
    """Closed annular-sector solid (vertices, quads) for the overlap screen."""
    n = seg+1; vs = [(x, r*math.cos(math.radians(a0+(a1-a0)*i/seg)), r*math.sin(math.radians(a0+(a1-a0)*i/seg)))
                     for x in (x0, x1) for r in (ri, ro) for i in range(n)]
    idx = lambda e, rr, i: e*2*n+rr*n+i; fs = []
    for i in range(seg):
        fs += [(idx(0, 0, i), idx(0, 0, i+1), idx(1, 0, i+1), idx(1, 0, i)), (idx(0, 1, i), idx(1, 1, i), idx(1, 1, i+1), idx(0, 1, i+1)),
               (idx(0, 0, i), idx(0, 1, i), idx(0, 1, i+1), idx(0, 0, i+1)), (idx(1, 0, i), idx(1, 0, i+1), idx(1, 1, i+1), idx(1, 1, i))]
    fs += [(idx(0, 0, 0), idx(1, 0, 0), idx(1, 1, 0), idx(0, 1, 0)), (idx(0, 0, seg), idx(0, 1, seg), idx(1, 1, seg), idx(1, 0, seg))]
    return vs, fs


def overlap_screen(res, asset='studies/WF_STUDY_BODY_C.blend', collection=COLLECTION):
    """Measured overlaps: every study envelope against every built mesh near the bay, and the study envelopes against each other.
    Surface intersection (BVH) plus containment of a sample vertex. Shortfall bars are scale objects and stay out."""
    import bpy
    import bmesh
    from mathutils.bvhtree import BVHTree
    from mathutils import Vector
    import shot_tools
    bpy.ops.wm.read_factory_settings(use_empty=True)
    items = []
    for src in ({'asset': 'WF_WAYFARER_001.blend', 'collection': 'WF_WAYFARER_001', 'group': 'assembly'},
                {'asset': asset, 'collection': collection, 'group': 'fixed'}):
        items += [dict(i, study=src['group'] == 'fixed') for i in shot_tools.gather(shot_tools.link_source(ROOT, src), src)]

    def tree(i):
        ob = i['obj']
        if i['study']:   # the parameter envelope shrunk by EPS on every face: study parts that only touch do not count
            x0, x1, r0, r1, a0, a1 = ob['envelope']; full = a1-a0 >= 359.9
            vs, fs = shell(x0+EPS, x1-EPS, r0+EPS, r1-EPS, a0 if full else a0+math.degrees(EPS/r1), a1 if full else a1-math.degrees(EPS/r1))
            return BVHTree.FromPolygons([i['matrix']@Vector(v) for v in vs], fs), [i['matrix']@Vector(v) for v in vs]
        if ob.type != 'MESH' or not len(ob.data.polygons):
            return None
        W = i['matrix']; vs = [W@v.co for v in ob.data.vertices]
        return BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in ob.data.polygons]), vs
    study = [i for i in items if i['study'] and i['kind'] != 'shortfall_scale']
    near = [i for i in items if not i['study'] and i['solid'] and -60 < i['center'][0] < 84 and math.hypot(*i['center'][1:]) < 6.0+i['radius']]
    trees = {}
    def get(i):
        if i['key'] not in trees:
            trees[i['key']] = tree(i)
        return trees[i['key']]
    hits = []
    def inside(t, p):
        """p inside a closed mesh: odd count of ray hits along +X."""
        bvh, n, q = t[0], 0, Vector(p)
        while True:
            loc, _, _, _ = bvh.ray_cast(q, Vector((1, 0, 0)))
            if loc is None:
                return n % 2 == 1
            n += 1; q = loc+Vector((1e-4, 0, 0))
            if n > 50:
                return False
    for a in study:
        ta = get(a)
        for b in near+[s for s in study if s['key'] > a['key']]:
            if (Vector(a['center'])-Vector(b['center'])).length > a['radius']+b['radius']:
                continue
            tb = get(b)
            if ta is None or tb is None:
                continue
            pairs = ta[0].overlap(tb[0])
            if pairs or inside(ta, tb[1][0]) or inside(tb, ta[1][0]):
                hits.append(dict(study=a['name'], other=b['name'], other_kind=b['kind'], faces=len(pairs)))
    return dict(study_parts=len(study), built_near=len(near), conflicts=hits)


# ---------------------------------------------------------------- subsystem map (pure: reads the shot gather dump)

def subsystem_map(dump):
    import representation as rp
    subs = rp.load_subsystems(ROOT, 'm5_subsystems.toml'); out = {}
    for it in dump:
        sub = rp.classify(it, subs)
        e = out.setdefault(sub['id'], dict(name=sub['name'], sources=sub.get('sources', ''), maturity=sub.get('maturity', ''),
                                            color=list(sub['color']), objects=0, kinds={}))
        e['objects'] += 1; e['kinds'][it['kind'] or '-'] = e['kinds'].get(it['kind'] or '-', 0)+1
    return dict(schema=1, note='M5 subsystem map: shot items of WF_WAYFARER_001 + WF_STUDY_BODY_C classified by shots/m5_subsystems.toml '
                               '(overlay colours are explanatory, never ship materials)', subsystems=dict(sorted(out.items())))


def legend(src, dst, title, note=None, lines=()):
    """Annotated copy of a shot render: the subsystem legend (overlay colour, id, name, maturity), optional finding lines under the title
    and the study status note (PIL)."""
    from PIL import Image, ImageDraw, ImageFont
    import representation as rp
    subs = rp.load_subsystems(ROOT, 'm5_subsystems.toml'); im = Image.open(src).convert('RGB'); W = im.width
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', max(11, W//120)); big = ImageFont.truetype('DejaVuSans-Bold.ttf', max(13, W//90))
    except OSError:
        font = big = ImageFont.load_default()
    import textwrap
    chars = int(W/(font.size*.56)); lines = [w for line in lines for w in textwrap.wrap(line, chars)]
    note = textwrap.wrap(note or ('Overlay colours are explanatory, never ship materials. BODY-C storage = STUDY / NONCANON PROTOTYPE envelopes (S&E 62, '
                                  '15!A200 HOLD); light-blue bars under the ship = unhoused volume at C-train scale, NOT a tank location.'), chars)
    lh = int(font.size*1.55); cols = 2; rows = (len(subs)+2)//cols+len(lines)+len(note)-1; H = im.height+lh*(rows+3)
    out = Image.new('RGB', (W, H), (12, 14, 18)); out.paste(im, (0, 0)); d = ImageDraw.Draw(out); y0 = im.height+lh//2
    d.text((16, y0), title, font=big, fill=(240, 240, 240))
    for n, line in enumerate(lines):
        d.text((16, y0+lh*(1+n)+4), line, font=font, fill=(240, 220, 150))
    y0 += lh*len(lines)
    gamma = lambda c: tuple(int(255*min(1, max(0, v))**(1/2.2)) for v in c)
    entries = [(s['id'], s['name'], s.get('maturity', ''), s['color']) for s in subs]+[('CTX', rp.CONTEXT['name'], rp.CONTEXT['maturity'], rp.CONTEXT['color'])]
    for n, (i, name, mat, col) in enumerate(entries):
        x = 16+(n % cols)*(W//cols); y = y0+lh*(1+n//cols)+4
        d.rectangle((x, y+2, x+lh-6, y+lh-4), fill=gamma(col))
        d.text((x+lh, y), f'{i}  {name}  -  {mat}'[:int(W/cols/(font.size*.55))], font=font, fill=(215, 215, 215))
    for n, line in enumerate(note):
        d.text((16, H-lh*(len(note)-n)), line, font=font, fill=(170, 170, 170))
    out.save(dst)


def _blender():
    try:
        import bpy  # noqa: F401
        return True
    except ImportError:
        return False


def main(asset=False, make_map=False):
    res = report()
    if asset and _blender():
        res['asset_objects'] = len(build_asset(res))
        res['overlap'] = overlap_screen(res)
        import bpy
        import shot_tools
        dump = []
        for src in ({'asset': 'WF_WAYFARER_001.blend', 'collection': 'WF_WAYFARER_001', 'group': 'assembly'},
                    {'asset': 'studies/WF_STUDY_BODY_C.blend', 'collection': COLLECTION, 'group': 'fixed'}):
            dump += [{k: i[k] for k in ('key', 'component_id', 'kind', 'group', 'source', 'name')}
                     for i in shot_tools.gather(bpy.data.collections[src['collection']], src)]
        (ROOT/'runs').mkdir(exist_ok=True); (ROOT/'runs/m5_gather.json').write_text(json.dumps(dump))
    elif OUT_JSON.exists():
        old = json.loads(OUT_JSON.read_text())
        res.update({k: old[k] for k in ('asset_objects', 'overlap') if k in old})
    if make_map:
        MAP_JSON.write_text(json.dumps(subsystem_map(json.loads((ROOT/'runs/m5_gather.json').read_text())), indent=1)+'\n')
    OUT_JSON.write_text(json.dumps(res, indent=1)+'\n')
    a = res['body_c']['allocation']
    print(json.dumps(res['need_m3'])); print(json.dumps(res['conventions'], indent=0)[:1500])
    print('C families', [m['family'] for m in a['modules']], 'capacity', a['capacity_m3'], 'per module', a['per_module_m3'])
    print('housed FI', a['housed_first_ignition_m3'], 'unhoused FI', a['unhoused_first_ignition_m3'], 'unhoused reserve', a['unhoused_reserve_m3'],
          'train m', a['train_length_m'], 'need m', a['total_need_train_length_m'], 'FI m', a['first_ignition_train_length_m'])
    print('bars', res['body_c']['shortfall_bars']); print('parts', len(res['body_c']['parts']))
    if 'overlap' in res:
        from collections import Counter
        c = Counter((x['other'] if not x['other'].startswith('Study_') else 'study:'+x['other'].split('_')[1], x['study'].split('_')[1])
                    for x in res['overlap']['conflicts'])
        print('overlap', res['overlap']['study_parts'], 'parts vs', res['overlap']['built_near'], 'built;', len(res['overlap']['conflicts']), 'conflicts')
        for k, v in sorted(c.items()):
            print('  ', k, v)
    return res


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser(); ap.add_argument('--asset', action='store_true'); ap.add_argument('--map', action='store_true')
    ap.add_argument('--legend', nargs=3, metavar=('SRC', 'DST', 'TITLE'))
    a = ap.parse_args(argv)
    if a.legend:
        legend(Path(a.legend[0]), Path(a.legend[1]), a.legend[2])
    else:
        main(a.asset, a.map)
