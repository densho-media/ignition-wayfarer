"""M5 AFT-R: robotic aft service access (owner 2026-10-18, S&E 15!A213 OWN-EVA-AFT-Q1, 98!A117: "ROBOTIC-ONLY AFT as present WORKING
operations direction (DRONE-001), not new human aft hatch ... Model service drone access to 55/57 aft targets, identify two unreachable
targets, fallback maintenance plan"). WORKING DIRECTION / FLIGHT_EVA HOLD: no new hull opening or pressure boundary, no crewed aft
service, rescue or thermal GO; DGT-009 stays HOLD (tool and arm reach, loads and the 53 operating gates OPEN).

Function: show how the aft exterior service targets are served by robots alone, which ones the robots cannot reach, and what keeps them
serviceable. Fixed: the 57 aft service targets of M5 slice 3 (aft RCS pods, antenna gimbals, the 45 S04 casing access panels, the six
blade-root datum / slide points), the DRONE-001 stations (DS-13 spine crawler track at 110 deg and its docks, DS-14 aft cradles at
X -99.5, DS-16 fixed aft manipulator base at X -97), the built hull, blades and comms booms. Unknown (OPEN): manipulator and tool reach
(15!A186), crawler speed, loads, the blade cooldown curve and robot thermal limits (45 H-01, DOP-08), the drive-zone release (DOP-09).
Design freedom (PROTOTYPE, this file): the robot-only aft track network (the slice 3 option C casing lines without the hypothetical
hatch, as crawler tracks), the working-reach rule, the boom spur.

    python3 src/wayfarer/studies/m5_aft_robotic.py                  # reach / path / gates per target -> references/m5_aft_robotic.json
    /snap/bin/blender -b --factory-startup --python-exit-code 1 --python src/wayfarer/studies/m5_aft_robotic.py -- --asset   # + study asset
        assets/wayfarer/studies/WF_STUDY_AFT_ROBOTIC.blend
"""
from pathlib import Path
import argparse
import heapq
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/studies'), str(ROOT/'src/wayfarer/shots')]
import m5_eva_l2 as ev

OUT_JSON = ROOT/'references/m5_aft_robotic.json'
ASSET = ROOT/'assets/wayfarer/studies/WF_STUDY_AFT_ROBOTIC.blend'
COLLECTION = 'WF_STUDY_AFT_ROBOTIC'

REACH = ev.WORK            # 1.60 m PROTOTYPE robot working reach from its track: the slice 3 crew rule, so the counts compare (15!A186: OPEN)
STEP = 0.5                 # track sampling (m)
JOIN = 0.6                 # tracks closer than this are one junction
DOCK_TRANSFER = 1.5        # a dock is on the network if its cradle centre lies this close to a track
SKIN_END_X = -101.75       # aft end of the casing skin; aft of it the drive zone (thrust ring, nozzles, comms booms)


def network(s):
    """Robot tracks: the slice 3 option C aft casing lines (longitudinals, hoops, thrust-ring spurs) without the hatch, plus the DS-13 spine
    crawler track (DRONE-001)."""
    import drone_fleet as df
    out = []
    for r in ev.rails(s):
        if r['option'] == 'C' and 'Hatch' not in r['name']:
            out.append(dict(name=r['name'].replace('EVA_', 'Robot_').removesuffix('_C'), points=r['points'], source='slice 3 option C line, as a crawler track'))
    for k, r in enumerate(df.spine_route(s)['rails']):
        out.append(dict(name=f'Robot_DS13_Track_{k}', points=[tuple(p) for p in r['points']], source='DS-13 spine crawler track (DRONE-001, 15!A184)'))
    return out


def graph(tracks):
    pts, adj = [], []
    def node(p):
        pts.append(p); adj.append([]); return len(pts)-1
    for t in tracks:
        prev = None
        for a, b in zip(t['points'], t['points'][1:]):
            n = max(1, int(math.dist(a, b)/STEP))
            for k in range(n+1):
                if prev is not None and k == 0:
                    continue
                p = tuple(a[i]+(b[i]-a[i])*k/n for i in range(3)); i = node(p)
                if prev is not None:
                    d = math.dist(pts[prev], p); adj[prev].append((i, d)); adj[i].append((prev, d))
                prev = i
    for i in range(len(pts)):                       # junctions between tracks
        for j in range(i+1, len(pts)):
            d = math.dist(pts[i], pts[j])
            if d < JOIN and not any(k == j for k, _ in adj[i]):
                adj[i].append((j, d)); adj[j].append((i, d))
    return pts, adj


def dijkstra(adj, sources):
    dist = [math.inf]*len(adj); h = []
    for s0, d0 in sources:
        dist[s0] = min(dist[s0], d0); heapq.heappush(h, (d0, s0))
    while h:
        d, u = heapq.heappop(h)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            if d+w < dist[v]:
                dist[v] = d+w; heapq.heappush(h, (d+w, v))
    return dist


def nearest(pts, p):
    i = min(range(len(pts)), key=lambda k: math.dist(pts[k], p)); return i, math.dist(pts[i], p)


def screen(s):
    import drone_fleet as df
    tracks = network(s); pts, adj = graph(tracks)
    st = {x['id']: x for x in df.stations(s)}
    docks = {}
    for sid in ('DS-13', 'DS-14'):
        for q in st[sid]['docks']:
            i, d = nearest(pts, q['world_centre']); docks[q['name']] = dict(station=sid, node=i, transfer_m=round(d, 2), on_network=d <= DOCK_TRANSFER)
    src = [(v['node'], 0.0) for v in docks.values() if v['on_network']]
    dist = dijkstra(adj, src)
    arm = st['DS-16']['docks'][0]['a']
    T = [t for t in ev.targets(s) if t['group'] == 'aft']; rows = []
    for t in T:
        i, d = nearest(pts, t['p']); zone = 'DRIVE_ZONE' if t['p'][0] < SKIN_END_X else 'CASING_BLADE_ROOT_BAND'
        gates = ['BLADES_COLD (DOP-08; blade cooldown curve OPEN, 45 H-01)']
        if zone == 'DRIVE_ZONE':
            gates.append('DRIVE_SAFE: drive off, field, plume, radiation and cryo states released (DOP-09, DGT-008 keep-out)')
        rows.append(dict(target=t['name'], why=t['why'], zone=zone, track_distance_m=round(d, 2), access='ROBOT_REACH' if d <= REACH else 'UNREACHABLE',
                         path_from_dock_m=None if math.isinf(dist[i]) else round(dist[i], 1), from_track_point=[round(v, 2) for v in pts[i]],
                         arm_DS16_distance_m=round(math.dist(arm, t['p']), 2), gates=gates, point=list(t['p'])))
    # the blade roots cut the aft hoop into three sectors; the 150-270 deg sector has no aft cradle (DS-14 is at 90 / 330): a PROTOTYPE third
    # cradle at 210 deg beside the DS-16 arm base, at the DS-14 station
    import exterior_hardware as eh
    extra = eh.radial(st['DS-14']['docks'][0]['world_centre'][0], math.hypot(*st['DS-14']['docks'][0]['world_centre'][1:]), math.radians(210.0))
    i3, d3 = nearest(pts, extra); dist3 = dijkstra(adj, src+[(i3, 0.0)])
    for r in rows:
        k, _ = nearest(pts, r['point']); r['path_with_third_cradle_m'] = None if math.isinf(dist3[k]) else round(dist3[k], 1)
    reach = [r for r in rows if r['access'] == 'ROBOT_REACH']; miss = [r for r in rows if r['access'] == 'UNREACHABLE']
    # fallback geometry for each unreachable target: a robot spur extended from the nearest track point straight toward it
    fallback = []
    for r in miss:
        a = r['from_track_point']; b = r['point']; L = math.dist(a, b); ext = max(0.0, L-REACH)
        tip = tuple(a[k]+(b[k]-a[k])*ext/L for k in range(3))
        fallback.append(dict(target=r['target'], spur_extension_m=round(ext, 2), spur=[a, [round(v, 3) for v in tip]],
                             DS16_arm_reach_needed_m=r['arm_DS16_distance_m']))
    lengths = {t['name']: round(sum(math.dist(a, b) for a, b in zip(t['points'], t['points'][1:])), 1) for t in tracks}
    oru = oru_concept(s, pts, dist, dist3)
    cradle = third_cradle(s, extra, st, rows)
    return dict(status='WORKING DIRECTION (robotic-only aft, 15!A213 / 98!A117) / FLIGHT_EVA HOLD / DGT-009 HOLD',
                rules=dict(working_reach_m=round(REACH, 2), step_m=STEP, join_m=JOIN, dock_transfer_m=DOCK_TRANSFER,
                           note='PROTOTYPE: robot working reach = the slice 3 crew rule (1.60 m) so the counts compare; manipulator / tool reach OPEN (15!A186)'),
                network=dict(tracks=lengths, total_m=round(sum(lengths.values()), 1), nodes=len(pts)), docks=docks,
                summary=dict(targets=len(rows), robot_reach=len(reach), unreachable=[r['target'] for r in miss],
                             drive_zone=sum(r['zone'] == 'DRIVE_ZONE' for r in rows),
                             longest_path_m=max(r['path_from_dock_m'] for r in reach if r['path_from_dock_m'] is not None),
                             max_reach_needed_m=max(r['track_distance_m'] for r in reach),
                             longest_path_with_third_cradle_m=max(r['path_with_third_cradle_m'] for r in reach if r['path_with_third_cradle_m'] is not None),
                             third_cradle=dict(at=[round(v, 2) for v in extra], transfer_m=round(d3, 2),
                                               note='PROTOTYPE DS-14 style cradle at 210 deg beside the DS-16 arm: the 150-270 deg aft sector has no aft dock')),
                targets=rows, fallback=fallback, hga_oru=oru, third_cradle_study=cradle)


def oru_concept(s, pts, dist, dist3):
    """Owner 2026-10-19 (preferred for comparison): the HGA gimbal, dish and feed as one replaceable unit (ORU) whose mechanical,
    power and RF interface is a flange at the boom root on the thrust-ring node, inside robot reach; the boom-top gimbal is never
    serviced in place. Interface reach, ORU envelope and path from the docks; mass and interface design UNKNOWN."""
    import exterior_hardware as eh
    q = eh.table(s); xm, rm = eh.thrust_ring(s); out = []
    for k, deg in enumerate(q['hga_deg'], 1):
        a = math.radians(deg); root = eh.radial(xm, rm, a); top = eh.radial(q['comms_x_m'], q['hga_boom_top_r_m']+q['hga_gimbal_m'], a)
        i, d = nearest(pts, root)
        D = q['hga_dish_diameter_m']
        out.append(dict(antenna=f'HGA_{k}', azimuth_deg=deg, interface_flange=[round(v, 2) for v in root], flange_track_distance_m=round(d, 2),
                        flange_in_reach=d <= REACH, oru_length_m=round(math.dist(root, top)+D/2, 2), oru_dish_diameter_m=D,
                        path_from_dock_m=None if math.isinf(dist[i]) else round(dist[i], 1),
                        path_with_third_cradle_m=None if math.isinf(dist3[i]) else round(dist3[i], 1), mass_kg=None,
                        gates=['DRIVE_SAFE', 'BLADES_COLD', 'link handed to the other HGA / OPT first (15!A210 store and forward)']))
    return dict(status='PREFERRED CONCEPT FOR COMPARISON (owner 2026-10-19); interface, mass, latch and RF rotary joint UNKNOWN', units=out,
                compare=dict(spur=dict(change='0.64 m robot spur up each boom', risk='more track hardware near the dish sweep; gimbal still serviced in place'),
                             oru=dict(change='boom-root flange (mechanical, power, RF) + spare unit stowage', risk='spare mass and flange design UNKNOWN; '
                                      'exchange needs a manipulator that can carry the boom-length unit (reach / load OPEN, 15!A186)')))


def third_cradle(s, at, st, rows):
    """Owner 2026-10-19: study the third DS-14 style aft cradle at 210 deg: clearances to its neighbours and the path savings."""
    import exterior_hardware as eh
    import hull_geometry as hg
    q = eh.table(s); xm, rm = eh.thrust_ring(s)
    o = eh.obstacles(s); r = math.hypot(at[1], at[2])
    az = math.atan2(at[2], at[1]); dif = [abs((az-b+math.pi) % (2*math.pi)-math.pi) for b in o['blades']]
    blade_gap = min(r*math.sin(d) if d < math.pi/2 else r for d in dif)                # to the half-plane of the nearest blade
    pod = eh.radial(-92.0, hg.radius_at(s, -92.0)+q['rcs_pod_m'][2]/2, math.radians(210.0))        # RCS-B aft pod at 210 deg (study)
    hga2 = eh.radial(xm, rm, math.radians(210.0))
    saved = [dict(target=x['target'], before_m=x['path_from_dock_m'], after_m=x['path_with_third_cradle_m'])
             for x in rows if x['path_from_dock_m'] is not None and x['path_with_third_cradle_m'] is not None
             and x['path_from_dock_m']-x['path_with_third_cradle_m'] > 20.0]
    return dict(at=[round(v, 2) for v in at], azimuth_deg=210.0, clearances_m=dict(
                    DS16_arm_base=round(math.dist(at, st['DS-16']['docks'][0]['a']), 2), nearest_blade_plane=round(blade_gap, 2),
                    rcs_b_aft_pod_210=round(math.dist(at, pod), 2), hga2_boom_root=round(math.dist(at, hga2), 2)),
                targets_saved=len(saved), largest_saving=max(saved, key=lambda x: x['before_m']-x['after_m']) if saved else None, saved=saved,
                status='STUDY / PROTOTYPE: not on the DRONE-001 station list until the owner adds it; dock hardware, power and mass UNKNOWN')


# ---------------------------------------------------------------- study asset (Blender)

# display sizes (study markers, not hardware): tracks r 0.10 m, target cubes 0.6 m, reach gaps r 0.08 m
COLOR = dict(robot_track_aft=(.25, .75, .95), robot_target_reach=(.30, .85, .40), robot_target_unreachable=(.95, .20, .85),
             robot_spur_fallback=(.95, .62, .15), robot_reach_gap=(.95, .20, .85))


def build_asset(s, res):
    import bpy
    from common import material
    from m5_eva_l2 import tube_mesh, cube
    bpy.ops.wm.read_factory_settings(use_empty=True)
    col = bpy.data.collections.new(COLLECTION); bpy.context.scene.collection.children.link(col)
    col['study'] = 'm5_aft_robotic'; col['status'] = 'WORKING DIRECTION robotic-only aft (15!A213) / DGT-009 HOLD: robot tracks are L2 study lines'
    mats = {k: material(f'STUDY_{k}', c) for k, c in COLOR.items()}
    def tag(ob, kind, note):
        col.objects.link(ob); ob.data.materials.append(mats[kind]); ob['kind'] = kind; ob['note'] = note; ob['study'] = 'm5_aft_robotic'
        ob['geometry_status'] = 'PROTOTYPE'; ob['canon_status'] = 'STUDY / NONCANON (15!A213 WORKING DIRECTION)'
    for t in network(s):
        if t['name'].startswith('Robot_DS13'):
            continue                                   # the DS-13 track is already built (WF_SERVICE drones)
        tag(tube_mesh(f'Study_{t["name"]}', t['points'], 0.10, 8), 'robot_track_aft', t['source'])
    for r in res['targets']:
        kind = 'robot_target_reach' if r['access'] == 'ROBOT_REACH' else 'robot_target_unreachable'
        tag(cube(f'Study_Target_{r["target"]}', tuple(r['point']), 0.6), kind, f'{r["access"]}: {r["track_distance_m"]} m from a robot track; {r["why"]}')
        if r['access'] == 'UNREACHABLE':
            tag(tube_mesh(f'Study_Reach_Gap_{r["target"]}', [tuple(r['from_track_point']), tuple(r['point'])], 0.08, 6), 'robot_reach_gap',
                f'{r["track_distance_m"]} m from the nearest track against {REACH:.2f} m working reach')
    for f in res['fallback']:
        tag(tube_mesh(f'Study_Spur_Fallback_{f["target"]}', [tuple(p) for p in f['spur']], 0.10, 8), 'robot_spur_fallback',
            f'fallback: robot track spur extended {f["spur_extension_m"]} m up the boom so the gimbal is within working reach (PROTOTYPE)')
    ASSET.parent.mkdir(parents=True, exist_ok=True); bpy.ops.wm.save_as_mainfile(filepath=str(ASSET), compress=True)


def main(asset=False):
    from spec import load
    s = load(ROOT)[0]; res = screen(s)
    OUT_JSON.write_text(json.dumps(res, indent=1)+'\n')
    if asset:
        build_asset(s, res)
    print(json.dumps(res['summary'], indent=1)); print('docks', json.dumps(res['docks']))
    for r in res['targets']:
        if r['access'] != 'ROBOT_REACH' or r['zone'] == 'DRIVE_ZONE':
            print(r['target'], r['zone'], r['track_distance_m'], r['access'], r['path_from_dock_m'], 'DS16', r['arm_DS16_distance_m'])
    print('fallback', res['fallback']); print('network', res['network']['total_m'], 'm')
    print('oru', json.dumps(res['hga_oru']['units'])); print('cradle', json.dumps({k: v for k, v in res['third_cradle_study'].items() if k != 'saved'}))
    return res


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser(); ap.add_argument('--asset', action='store_true')
    main(ap.parse_args(argv).asset)
