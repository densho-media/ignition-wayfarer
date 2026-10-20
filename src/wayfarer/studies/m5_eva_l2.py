"""M5 slice 3: L2 comparison of exterior EVA handrails, tether anchors and service routes on stationary structure (owner directive
2026-10-18 §7). COMPARISON MODELS ONLY: no exterior rail is released (S&E 44 RUN-011), FLIGHT_EVA stays HOLD / LOCKED (45 O-07), every
EVA gate keeps its fail-closed status (eva_route.hazards), and nothing here enters the vehicle.

Function: show which service targets on the stationary exterior a suited crew member could reach by rail, by what path, and what each path
crosses (rotating ring sweeps, hot-blade sight lines, the shield shadow), so the owner can decide whether aft exterior service is crewed,
robotic, or needs a new opening. Fixed: the built hull (forward collar X 93.35-112.25 r 6.5; open rotor bay X 82.75-93.35 with only the
spine; aft casing X -101.75..82.75 r 6.0 in the blade-root band), the SP-11 airlock (X 101.85, 50 deg), the rings (ROTATING in the EVA
configuration), the blades, the S02 hardware, the S04 casing access panels, the measured suit (arm reach 0.58-0.62 m, operational envelope
1.07 m, eva_access). Unknown (OPEN): rail and anchor loads, tether length (SIM-03), ring keep-out (EVA-015), blade post-shutdown
temperature and view-factor release (45 H-01..H-13), debris and dose limits, any aft EVA hatch. Design freedom (PROTOTYPE, this file):
rail lines, standoff, anchor pitch (the training rail's 1.5 m), the working-reach rule.

Options:
  A  forward district: collar hoops and longitudinals from the airlock, plus shield-rear radials along the truss's aft chord to the rim RCS pods.
  B  A + a spine crossing of the rotor bay with the rings STOPPED_LOCKED, then aft casing rails on the access-panel azimuths to the thrust ring.
  C  aft casing rails from a hypothetical aft EVA hatch at the engineering bay (reached through the BODY-C spine tunnel): no crossing, but a
     new hull opening (outer-geometry change: owner decision).
  D  no crew rails aft: aft targets by DRONE-001 crawlers only (the existing robot-first answer).

    python3 src/wayfarer/studies/m5_eva_l2.py                                      # pure screen -> references/m5_eva_l2.json
    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/m5_eva_l2.py -- --asset   # + study asset, rotor-bay channel and
                                                                                                   #   suit-corridor clearances (measured)
"""
from pathlib import Path
import argparse
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/studies'), str(ROOT/'src/wayfarer/shots')]

OUT_JSON = ROOT/'references/m5_eva_l2.json'
ASSET = ROOT/'assets/wayfarer/studies/WF_STUDY_EVA_L2.blend'
COLLECTION = 'WF_STUDY_EVA_L2'

STANDOFF = 0.15            # rail axis off the skin (the training rail's rail_standoff_m)
PITCH = 1.5                # anchor pitch (the training rail's anchor_spacing_m)
ARM = 0.577                # smaller measured suited shoulder-to-palm reach (eva_access.arm_reach, newcomer)
SHOULDER = 0.45            # PROTOTYPE shoulder breadth: one hand on the rail, the other working
WORK = 2*ARM+SHOULDER      # working reach from a rail point (PROTOTYPE rule) = 1.60 m
TETHER = 2.0               # gameplay tether reach (tether_length_m OPEN, SIM-03): beyond WORK only with a portable foot restraint
SUIT_R = 1.074/2           # EVA_OPERATIONAL envelope radius (measured, instructor)
BODY_OFF = 0.70            # suit body centre off the rail, outward (hand on the rail, arm bent)
SAMPLE = 2.0               # hazard / clearance sample pitch along a rail (m)
ACCESS_AZ = (0.0, 120.0, 240.0)


def radial(x, r, a_deg):
    a = math.radians(a_deg); return (x, r*math.cos(a), r*math.sin(a))


def arc(x, r, a0, a1, step=5.0):
    n = max(2, int(abs(a1-a0)/step)+1); return [radial(x, r, a0+(a1-a0)*i/(n-1)) for i in range(n)]


def rails(s):
    """Rail polylines per option (points in the vehicle frame), each with a kind, a surface normal rule and a purpose."""
    import forward_shield as fs
    import hull_geometry as hg
    import thermal_geometry as tg
    import exterior_hardware as eh
    rc = 6.5+STANDOFF; ra = hg.radius_at(s, 0.0)+STANDOFF; out = []
    def add(opt, name, kind, pts, normal, purpose):
        out.append(dict(option=opt, name=name, kind=kind, points=[tuple(round(v, 4) for v in p) for p in pts], normal=normal, purpose=purpose))
    # A: forward collar (hoops clear of the airlock and dock fittings, longitudinals off the dock corridors)
    for x in (96.5, 104.5):
        add('A', f'EVA_Collar_Hoop_{x:.1f}', 'eva_rail_forward', arc(x, rc, 0.0, 360.0), 'radial', 'collar hoop: links the airlock, both docks and the longitudinals')
    for az in (50.0, 175.0, 295.0):
        add('A', f'EVA_Collar_Long_{az:.0f}', 'eva_rail_forward', [radial(96.5, rc, az), radial(107.6, rc, az)], 'radial',
            'collar longitudinal: airlock azimuth (training rail line) and 20 deg off each dock corridor')
    for az in eh.table(s)['rcs_rim_deg']:
        r0 = 10.5 if az == 255 else 8.5                  # clear of the hub corner (255: of the forward mount strut, measured); the start is a
        rr = [r0+i*(42.5-r0)/24 for i in range(25)]      # hand-over transfer from the collar longitudinal; the end stops short of the rim pod
        pts = [radial(fs.truss_aft_at(s, r)-STANDOFF, r, az) for r in rr]
        add('A', f'EVA_Shield_Radial_{az:.0f}', 'eva_rail_forward', pts, 'aft', 'shield-rear radial on the truss aft chord to the rim RCS pod and beacon')
    add('A', 'EVA_Shield_Rim_Hoop', 'eva_rail_forward', [radial(fs.truss_aft_at(s, 43.5)-STANDOFF, 43.5, a) for a in [5.0*i for i in range(73)]], 'aft',
        'rim hoop on the truss aft chord: links the radials, rim pods and rim strobes (Crown bay housings measured as obstacles)')
    # B: rotor-bay crossing along the spine (azimuth set by the measured channel; default the airlock azimuth), then the aft casing rails
    add('B', 'EVA_Spine_Crossing', 'eva_rail_crossing', [radial(96.5, rc, 50.0), radial(93.6, 1.10, 50.0), radial(82.5, 1.10, 50.0), radial(81.8, ra, 50.0)],
        'radial', 'spine crossing of the rotor bay (rings STOPPED_LOCKED only): forward collar -> aft casing')
    d = tg.blade_of(s)
    for opt in ('B', 'C'):
        for az in ACCESS_AZ:
            add(opt, f'EVA_Casing_Long_{az:.0f}_{opt}', 'eva_rail_aft', [radial(81.8, ra, az), radial(-100.6, ra, az)], 'radial',
                'aft casing longitudinal on the access-panel azimuth (S04 panels), 30 deg from a blade root')
        for k, b in enumerate((30.0, 150.0, 270.0)):      # broken at the blade roots (root booms and boots at the keel azimuths)
            add(opt, f'EVA_Casing_Hoop_Aft_{k}_{opt}', 'eva_rail_aft', arc(-100.6, ra, b+14.0, b+106.0), 'radial',
                'aft hoop arc between two blade roots: links the longitudinals and the thrust-ring spurs')
        add(opt, f'EVA_Casing_Hoop_Fwd_{opt}', 'eva_rail_aft', arc(81.8, ra, 0.0, 360.0), 'radial', 'forward hoop at the casing front: links the longitudinals')
        for az in (30.0, 90.0, 150.0, 210.0, 270.0, 330.0):
            if az in (90.0, 210.0, 330.0):        # from the hoop arc aft and on up the comms boom toward its gimbal
                pts = [radial(-100.6, ra, az), radial(-101.6, ra, az), radial(-102.2, 6.25, az), radial(-103.6, 7.1, az)]
            else:                                  # keel azimuths: leave the hoop arc 14 deg off the blade root, then in to the RCS pod
                pts = [radial(-100.6, ra, az+14.0), radial(-101.9, ra, az+8.0), radial(-102.4, 6.35, az+5.0)]
            add(opt, f'EVA_Ring_Spur_{az:.0f}_{opt}', 'eva_rail_aft', pts, 'radial',
                'spur to a thrust-ring node: RCS pod (keel azimuths) or up the comms boom (90/210/330)')
    add('C', 'EVA_Aft_Hatch_Hypothetical', 'eva_rail_aft', [radial(-64.0, ra, 0.0), radial(-64.0, ra+0.6, 0.0)], 'radial',
        'HYPOTHETICAL aft EVA hatch at the engineering bay (via the BODY-C spine tunnel): a new hull opening, owner decision')
    return out


def targets(s):
    """Service targets on the stationary exterior (centre points): what a crew member would come to inspect, adjust or replace."""
    import exterior_hardware as eh
    import hull_geometry as hg
    import casing_panels as cp
    import thermal_geometry as tg
    out = []
    def add(name, group, p, why):
        out.append(dict(name=name, group=group, p=tuple(round(v, 3) for v in p), why=why))
    for f in hg.service_fittings(s):
        add(f['name'], 'forward', radial(f['x'], f['r1'], math.degrees(f['theta'])), 'hatch / capture ring service')
    for p in eh.docking(s):
        if p['kind'] == 'exterior_hardware' and 'Target' in p['name'] and 'Post' not in p['name']:
            add(p['name'], 'forward', p.get('world_centre', p.get('a')), 'docking target')
    for p in eh.rcs_rim(s):
        if p.get('rcs'):
            add(p['name'], 'forward', p['world_centre'], 'rim RCS pod: valves, thrusters')
    for p in eh.rim_beacons(s):
        add(p['name'], 'forward', p['b'], 'rim strobe')
    for p in eh.rcs_aft(s):
        if p.get('rcs'):
            add(p['name'], 'aft', p['world_centre'], 'aft RCS pod')
    seen = set()
    for p in eh.comms(s):
        if p['antenna'] not in seen:
            seen.add(p['antenna']); add(f'Ext_{p["antenna"]}_Gimbal', 'aft', p['gimbal'], 'antenna gimbal / feed service')
    for q in cp.access_panels(s):
        add(q['name'], 'aft', radial(q['x'], 6.0, math.degrees(q['theta'])), 'casing access panel (cage-to-skin corridor)')
    d = tg.blade_of(s)
    for k in range(s['radiators']['count']):
        az = s['prototype']['radiator_phase_deg']+k*120
        for x in (d['aft_x_m'], d['front_x_m']):
            add(f'Radiator_Root_{k+1}_{x:.0f}', 'aft', radial(x, d['root_radius_m'], az), 'radiator root boot / boom (blade root datum or slide)')
    return out


def samples(rail, step=SAMPLE):
    pts = rail['points']; out = []
    for a, b in zip(pts, pts[1:]):
        L = math.dist(a, b); n = max(1, int(L/step))
        out += [tuple(a[i]+(b[i]-a[i])*k/n for i in range(3)) for k in range(n)]
    return out+[pts[-1]]


def anchors(rail):
    """Anchor points every PITCH along the rail (cumulative length), the first at its start."""
    pts = rail['points']; out = []; acc = 0.0; nxt = 0.0
    for a, b in zip(pts, pts[1:]):
        L = math.dist(a, b)
        while nxt <= acc+L+1e-9:
            t = (nxt-acc)/L if L else 0.0; out.append(tuple(a[i]+(b[i]-a[i])*t for i in range(3))); nxt += PITCH
        acc += L
    return out


def body_centre(s, p, normal):
    if normal == 'aft':
        return (p[0]-BODY_OFF, p[1], p[2])
    r = math.hypot(p[1], p[2]) or 1.0
    return (p[0], p[1]*(1+BODY_OFF/r), p[2]*(1+BODY_OFF/r))


def hazard_point(s, c, faces):
    """Measured hazard values at a suit body centre: ring sweep distance (rotating rings), blade sight + view-factor readback, shield shadow."""
    import habitat_ring
    import eva_route as er
    import forward_shield as fs
    h = habitat_ring.sweep_half(s); R = s['habitat_ring']['sector_outer_radius_m']+.5; dmin = 1e9
    for xc in habitat_ring.centers(s):
        dx = max(0.0, abs(c[0]-xc)-h); dr = max(0.0, math.hypot(c[1], c[2])-R); dmin = min(dmin, math.hypot(dx, dr))
    sight = er.blade_sight(s, c, faces); vf = er.view_factor_readback(s, c, faces)['total']
    sh = fs.stations(s)
    return dict(ring_gap_m=round(dmin-SUIT_R, 2), in_ring_sweep=dmin-SUIT_R <= 0, blade_visible=max(b['visible_fraction'] for b in sight),
                nearest_blade_m=min((b['nearest_visible_m'] for b in sight if b['nearest_visible_m'] is not None), default=None),
                view_factor=vf, in_shield_shadow=math.hypot(c[1], c[2]) < sh['shield_r'])


def fast_body_radius(er, s):
    """eva_route.body_radius recomputes the layout per call; the occlusion test calls it ~10^4 times per point. Memoize it at 1 cm in X
    for this study (same formula, same values)."""
    if getattr(er, '_m5_cached', False):
        return
    orig = er.body_radius; cache = {}
    def cached(s_, x):
        k = round(x, 2)
        if k not in cache:
            cache[k] = orig(s_, k)
        return cache[k]
    er.body_radius = cached; er._m5_cached = True


def screen(s):
    import eva_route as er
    fast_body_radius(er, s)
    faces = er.blade_faces(s); R = rails(s); T = targets(s); opts = {}
    per_rail = {}
    for r in R:
        hz = [hazard_point(s, body_centre(s, p, r['normal']), faces) for p in samples(r)]
        per_rail[r['name']] = dict(option=r['option'], kind=r['kind'], length_m=round(sum(math.dist(a, b) for a, b in zip(r['points'], r['points'][1:])), 1),
                                   anchors=len(anchors(r)), purpose=r['purpose'],
                                   min_ring_gap_m=min(h['ring_gap_m'] for h in hz), crosses_ring_sweep=any(h['in_ring_sweep'] for h in hz),
                                   max_blade_visible=max(h['blade_visible'] for h in hz), max_view_factor=round(max(h['view_factor'] for h in hz), 4),
                                   min_blade_distance_m=min((h['nearest_blade_m'] for h in hz if h['nearest_blade_m'] is not None), default=None),
                                   outside_shield_shadow=any(not h['in_shield_shadow'] for h in hz))
    for opt in 'ABCD':
        use = [r for r in R if r['option'] == 'A' or (opt in 'BC' and r['option'] == opt)] if opt != 'D' else [r for r in R if r['option'] == 'A']
        anc = [a for r in use for a in anchors(r)]; pts = [p for r in use for p in samples(r, 0.25)]
        reach = []
        for t in T:
            d = min((math.dist(t['p'], p) for p in pts), default=1e9)
            cls = 'RAIL_REACH' if d <= WORK else ('FOOT_RESTRAINT_TETHER' if d <= WORK+TETHER else 'NOT_REACHED')
            if opt == 'D' and t['group'] == 'aft':
                cls = 'ROBOT_ONLY'
            reach.append(dict(target=t['name'], group=t['group'], distance_m=round(d, 2), access=cls))
        count = lambda g, c: sum(1 for q in reach if q['group'] == g and q['access'] == c)
        rs = [per_rail[r['name']] for r in use]
        opts[opt] = dict(rails=[r['name'] for r in use], rail_length_m=round(sum(x['length_m'] for x in rs), 1), anchors=len(anc),
                         forward={c: count('forward', c) for c in ('RAIL_REACH', 'FOOT_RESTRAINT_TETHER', 'NOT_REACHED')},
                         aft={c: count('aft', c) for c in ('RAIL_REACH', 'FOOT_RESTRAINT_TETHER', 'NOT_REACHED', 'ROBOT_ONLY')},
                         crosses_ring_sweep=any(x['crosses_ring_sweep'] for x in rs), max_view_factor=max(x['max_view_factor'] for x in rs),
                         min_blade_distance_m=min((x['min_blade_distance_m'] for x in rs if x['min_blade_distance_m'] is not None), default=None),
                         outside_shield_shadow=any(x['outside_shield_shadow'] for x in rs), reach=reach)
    opts['A']['configuration'] = 'EVA (rings ROTATING, drive OFF): ring gate measured, all limits OPEN'
    opts['B']['configuration'] = 'rings STOPPED_LOCKED and drive OFF for the crossing (no such EVA configuration is released; 11!5 EVA has rings ROTATING)'
    opts['C']['configuration'] = 'EVA (rings may rotate; the aft district never meets their sweep); needs a new aft hull opening'
    opts['D']['configuration'] = 'EVA forward district only; aft by DRONE-001 crawlers (DGT-009 HOLD)'
    return dict(study='M5 slice 3: EVA L2 handrail / tether-anchor comparison (COMPARISON MODELS; RUN-011, FLIGHT_EVA HOLD unchanged)',
                rules=dict(standoff_m=STANDOFF, anchor_pitch_m=PITCH, arm_reach_m=ARM, work_reach_m=round(WORK, 2), tether_gameplay_m=TETHER,
                           suit_radius_m=SUIT_R, body_offset_m=BODY_OFF, status='PROTOTYPE rules; tether_length_m, ring_keepout_m, rail loads OPEN'),
                rails=per_rail, options=opts, targets=len(T))


# ---------------------------------------------------------------- Blender: study asset + measured clearances

COLOR = dict(eva_rail_forward=(.25, .85, .35), eva_rail_crossing=(.95, .85, .20), eva_rail_aft=(.95, .35, .15), eva_anchor=(.95, .95, .95),
             eva_target=(.95, .20, .85))


def tube_mesh(name, pts, r=0.03, n=8):
    import bpy
    from mathutils import Vector
    vs, fs = [], []
    for a, b in zip(pts, pts[1:]):
        a, b = Vector(a), Vector(b); d = (b-a)
        if d.length < 1e-6:
            continue
        d.normalize(); h = Vector((0, 0, 1)) if abs(d.z) < .9 else Vector((1, 0, 0)); e1 = d.cross(h).normalized(); e2 = d.cross(e1)
        base = len(vs)
        for p in (a, b):
            for k in range(n):
                t = 2*math.pi*k/n; vs.append(tuple(p+r*(math.cos(t)*e1+math.sin(t)*e2)))
        for k in range(n):
            fs.append((base+k, base+(k+1) % n, base+n+(k+1) % n, base+n+k))
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    return bpy.data.objects.new(name, me)


def cube(name, c, size):
    import bpy
    h = size/2; vs = [(c[0]+sx*h, c[1]+sy*h, c[2]+sz*h) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    return bpy.data.objects.new(name, me)


def build_asset(s):
    import bpy
    from common import material
    bpy.ops.wm.read_factory_settings(use_empty=True)
    col = bpy.data.collections.new(COLLECTION); bpy.context.scene.collection.children.link(col)
    col['study'] = 'm5_eva_l2'; col['status'] = 'COMPARISON MODEL: no exterior rail released (44 RUN-011); FLIGHT_EVA HOLD'
    mats = {k: material(f'STUDY_{k}', c) for k, c in COLOR.items()}; n = 0
    def tag(ob, kind, note):
        col.objects.link(ob); ob.data.materials.append(mats[kind]); ob['kind'] = kind; ob['note'] = note
        ob['geometry_status'] = 'PROTOTYPE'; ob['study'] = 'm5_eva_l2'; ob['component_id'] = f'WF.STUDY.EVA_L2.{ob.name}'
    for r in rails(s):
        # DISPLAY radius 0.12 m (about three times a handrail) so the lines read at ship scale; every measurement uses the centrelines
        tag(tube_mesh(f'{r["name"]}', r['points'], 0.12), r['kind'], f'option {r["option"]}: {r["purpose"]} (display radius exaggerated)')
        for k, a in enumerate(anchors(r)):
            tag(cube(f'{r["name"]}_Anchor_{k:03}', a, 0.28), 'eva_anchor', f'option {r["option"]} tether anchor (loads OPEN; display size)')
    for t in targets(s):
        tag(cube(f'EVA_Target_{t["name"]}', t['p'], 0.45), 'eva_target', f'{t["group"]} service target: {t["why"]}')
    ASSET.parent.mkdir(parents=True, exist_ok=True); bpy.ops.wm.save_as_mainfile(filepath=str(ASSET), compress=True)


def measure(s):
    """Rotor-bay channel along the spine (rings at their saved index pose = STOPPED_LOCKED geometry) and suit-corridor clearances of every
    rail sample to the built meshes (one BVH of the vehicle)."""
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    import shot_tools
    import representation as rp
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src = {'asset': 'WF_WAYFARER_001.blend', 'collection': 'WF_WAYFARER_001', 'group': 'assembly'}
    vs, fs = [], []; skip = ('scale_reference', 'plasma', 'magnetic_field', 'optical_beam', 'hull_envelope')
    for it in shot_tools.gather(shot_tools.link_source(ROOT, src), src):
        ob = it['obj']
        if ob.type != 'MESH' or it['kind'] in skip or it['name'].startswith(('Engineering_Envelope', 'Tank_Volume')):
            continue
        if math.hypot(*it['center'][1:]) > 60+it['radius']:
            continue
        W = it['matrix']; b = len(vs); vs += [W@v.co for v in ob.data.vertices]; fs += [tuple(b+i for i in p.vertices) for p in ob.data.polygons]
    bvh = BVHTree.FromPolygons(vs, fs)
    # rotor-bay channel: free radial height above r 0.95 along each azimuth, minimum over X
    chan = []
    for k in range(72):
        az = 5.0*k; a = math.radians(az); u = Vector((0, math.cos(a), math.sin(a))); h = 1e9
        x = 82.75
        while x <= 93.35:
            hit = bvh.ray_cast(Vector((x, 0, 0))+u*0.96, u, 40.0); h = min(h, (hit[3] if hit[0] is not None else 40.0)); x += 0.25
        chan.append(dict(azimuth_deg=az, free_height_m=round(h, 3)))
    best = max(chan, key=lambda c: c['free_height_m'])
    # suit corridor clearance per rail
    corr = {}
    for r in rails(s):
        worst = None
        for p in samples(r, 0.5):
            c = body_centre(s, p, r['normal']); near = bvh.find_nearest(Vector(c))
            d = (near[3] if near[0] is not None else 1e9)-SUIT_R; rail_d = bvh.find_nearest(Vector(p))
            rd = rail_d[3] if rail_d[0] is not None else 1e9
            if worst is None or d < worst['suit_clearance_m']:
                worst = dict(suit_clearance_m=round(d, 3), at=[round(v, 2) for v in p], rail_to_mesh_m=round(rd, 3))
        corr[r['name']] = worst
    return dict(rotor_bay_channel=dict(best=best, needed_m=round(2*SUIT_R+0.05, 3), per_azimuth=chan,
                                        note='free radial height above the spine surface (r 0.96), minimum over X 82.75-93.35, rings at the saved index pose'),
                corridor=corr)


def _blender():
    try:
        import bpy  # noqa: F401
        return True
    except ImportError:
        return False


def main(asset=False):
    from spec import load
    s = load(ROOT)[0]; res = screen(s)
    if asset and _blender():
        build_asset(s); res['measured'] = measure(s)
    elif OUT_JSON.exists() and 'measured' in json.loads(OUT_JSON.read_text()):
        res['measured'] = json.loads(OUT_JSON.read_text())['measured']
    OUT_JSON.write_text(json.dumps(res, indent=1)+'\n')
    for k, o in res['options'].items():
        print(k, o['rail_length_m'], 'm', o['anchors'], 'anchors | fwd', o['forward'], '| aft', o['aft'], '| ring', o['crosses_ring_sweep'],
              '| VF', o['max_view_factor'], 'blade d', o['min_blade_distance_m'], '| outside shadow', o['outside_shield_shadow'])
    if 'measured' in res:
        m = res['measured']; print('channel', m['rotor_bay_channel']['best'], 'needed', m['rotor_bay_channel']['needed_m'])
        for k, v in m['corridor'].items():
            if v['suit_clearance_m'] < 0.05 or v['rail_to_mesh_m'] < 0.06:
                print('  tight', k, v)
    return res


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser(); ap.add_argument('--asset', action='store_true')
    main(ap.parse_args(argv).asset)
