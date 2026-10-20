"""Ring B / refuge unified casualty-rescue survey (owner direction 2026-10-11; S&E 15!A135 RESCUE-004, Doc answer 12:33). NONCANON, PROTOTYPE,
DISPOSABLE: nothing here changes data/, a generator or a saved asset. Each variant is a workspace under runs/hum003/unified/<variant>/work (a copy of
data/ with the trunk ladder angle, the refuge port angle and one [human_entry.study] table changed), built by build.py --root through a wrapper that
patches crew_transfer.vestibule in memory (study knob `vestibule_shift_aft_m`: the whole despun vestibule moved aft along the spine; the production
module is untouched).

Question: can ring B's port/neck give the K attendant >= STUDY_MARGIN_M (0.05 m) WITHOUT the vestibule entering hub 1's forward withdrawal window
(0.20 m at the 1.10 m port), with the ladder turned to ~300 deg, the refuge entry turned 10-20 deg, the 1.00 x 2.30 m refuge slot and a hoist
line 0.20-0.25 m off the axis toward the side opposite the ladder? Legs measured with hum003_routes' machinery (carrier boxes/capsule + inline staff):
  rings  B2 (trunk <-> indexed sector 2, valid for B1/B3 stopped/indexed by symmetry), B2-M (landing -> couch), and the locked-ring annulus legs
         B1-B2, B3-B2, B1-B2-M, B3-B2-M (1.5 g, no re-index);
  slot   the carrier out of the trunk through the 1.00 x 2.30 m slot to an occupant station (local free-space model);
  hoist  the guided trunk hoist with the attendant on the ladder, e = 0.20 and 0.25 m;
  geom   hub-1 window and lock-pin distances of the variant's geometry, the ladder top, closure areas and ideal loads (DIAGNOSTIC).

    python3 src/wayfarer/studies/ringb_unified.py build <variant,...>
    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/ringb_unified.py -- legs --variant <v> [--parts rings,slot,hoist,geom]
    python3 src/wayfarer/studies/ringb_unified.py collect

SIM-027 (owner 2026-10-11 16:45, S&E 15!A159:A161 RINGB-005..007): worst-case survey. Variants V0, V1, G1 (comparison only) plus V0_rail150/165
(trunk handrail 1 moved, hoist-gap option) in the same disposable workspaces. Clearance = minimum over carrier injury classes (A rigid litter, C vacuum
mattress, K litter + kit, S suited), two body sizes (x1.00, x1.08), door states (leaves 1.00 and 0.90 open), search seeds (best-found poses, the spread is
a risk signal), six deterministic pose families with wobbles (hum003_routes.family_sweep) and two rescuers (one at each end, inline and +-0.10 m).

    python3 src/wayfarer/studies/ringb_unified.py survey-run [--workers 18] [--only <substr>]      # parallel Blender jobs -> <v>/survey/*.json
    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/ringb_unified.py -- survey --variant <v> --route B2 --carrier K
    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/ringb_unified.py -- slotsurvey --variant <v> --carrier S
    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/ringb_unified.py -- hoistopts --variant V0_rail150
    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/ringb_unified.py -- pins
    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/ringb_unified.py -- distributed        # sector free-volume fit of a protected care point (zone blocks; needs numpy)
    python3 src/wayfarer/studies/ringb_unified.py sim027             # writes references/p1_access_seg_ringb.json and p1_hum003.json sim027_worst_case_2026_10_11
"""
from pathlib import Path
import argparse
import json
import math
import re
import shutil
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/studies'), str(ROOT/'tools')]
BLENDER = '/snap/bin/blender'
UNI = ROOT/'runs/hum003/unified'
OUT_JSON = ROOT/'references/p1_hum003.json'
KEY = 'ring_b_unified_2026_10_11'

# name: (port clear radius m, vestibule shift aft m, trunk ladder deg, refuge entry turn deg off its radial)
VARIANTS = {
    'V0_1.06_aft0.16': dict(pc=0.53, shift=0.16, ladder=300.0, refuge=20.0,
                            note='1.06 m port, vestibule shifted aft 0.16 m: the largest port that respects BOTH hub 1\'s window and the lock-pin bound'),
    'V1_1.10_aft0.20': dict(pc=0.55, shift=0.20, ladder=300.0, refuge=20.0,
                            note='1.10 m port, whole vestibule shifted aft 0.20 m: window respected, lock-pin bound exceeded'),
    'V2_1.15_aft0.25': dict(pc=0.575, shift=0.25, ladder=310.0, refuge=20.0,
                            note='1.15 m port, vestibule shifted aft 0.25 m (window respected)'),
    'G1_1.10_guard0.10': dict(pc=0.55, shift=0.00, guard=0.10, ladder=300.0, refuge=20.0,
                              note='1.10 m port with the guard rings halved to 0.10 m (HAB-001 inter-seal cavity depth, a workspace value; ring A too): '
                                   'window AND lock-pin bound respected, no shift'),
    # SIM-027 (owner 2026-10-11 16:45): the trunk's 135 deg handrail moved in a disposable workspace (hoist line at ladder + 180 = 120 deg); ring B as V0
    'V0_rail150': dict(pc=0.53, shift=0.16, ladder=300.0, refuge=20.0, rail=150.0, note='V0 with trunk handrail 1 moved 135 -> 150 deg (hoist-gap option)'),
    'V0_rail165': dict(pc=0.53, shift=0.16, ladder=300.0, refuge=20.0, rail=165.0, note='V0 with trunk handrail 1 moved 135 -> 165 deg (hoist-gap option)'),
    'V3_1.20_aft0.30': dict(pc=0.60, shift=0.30, ladder=320.0, refuge=20.0,
                            note='1.20 m port, vestibule shifted aft 0.30 m (window respected)'),
}
ROUTES = 'B2,B2-M,B1-B2,B3-B2,B1-B2-M,B3-B2-M'


def patch_vestibule():
    """Study knob: [human_entry.study] vestibule_shift_aft_m = { "2" = d } moves rotor 2's whole vestibule aft by d (in memory only)."""
    import crew_transfer as ct
    if getattr(ct, '_unified_patched', False):
        return
    orig = ct.vestibule

    def vestibule(s, j):
        v = orig(s, j)
        sh = s['human_entry'].get('study', {}).get('vestibule_shift_aft_m', {}).get(str(j), 0.0)
        if sh and v['human']:
            v = dict(v)
            for k in ('u0', 'u1', 'cu0', 'cu1', 'port_u', 'hatch_u'):
                v[k] += sh
        return v
    ct.vestibule = vestibule
    ct._unified_patched = True


def edit(text, v):
    text, n = re.subn(r'^trunk_ladder_deg = .*$', f"trunk_ladder_deg = {v['ladder']:.1f}", text, flags=re.M); assert n == 1
    text, n = re.subn(r'^refuge_port_angle_deg = .*$', f"refuge_port_angle_deg = {v['refuge']:.1f}", text, flags=re.M); assert n == 1
    if 'rail' in v:
        text, n = re.subn(r'^trunk_handrail_deg = .*$', f"trunk_handrail_deg = [{v['rail']:.1f}, 255.0]", text, flags=re.M); assert n == 1
    if 'guard' in v:
        text, n = re.subn(r'^vestibule_guard_m = .*$', f"vestibule_guard_m = {v['guard']:.2f}", text, flags=re.M); assert n == 1
    text += ('\n# ring B / refuge unified survey workspace only (studies/ringb_unified.py)\n[human_entry.study]\n'
             f'port_clear_radius_m = {{ "2" = {v["pc"]} }}\nvestibule_shift_aft_m = {{ "2" = {v["shift"]} }}\n')
    return text


def work_of(name):
    return UNI/name/'work'


def fix_conflicts(d):
    for f in list(d.glob('* [[]conflicted[]]*')):
        f.rename(d/re.sub(r' \[conflicted( \d+)?\]', '', f.name))


def build(names):
    for name in names:
        v = VARIANTS[name]; vd = UNI/name; work = work_of(name)
        if work.exists():
            shutil.rmtree(work)
        vd.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT/'data', work/'data')
        p = work/'data/wayfarer_3d.toml'; p.write_text(edit(p.read_text(), v))
        with open(vd/'build.log', 'w') as log:
            code = subprocess.call([BLENDER, '-b', '--factory-startup', '--python', str(Path(__file__).resolve()), '--', 'buildwrap', '--root', str(work)],
                                   stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
        print(name, 'build exit', code, flush=True)


def buildwrap(args):
    import runpy
    patch_vestibule()
    sys.argv = [str(ROOT/'src/wayfarer/build/build.py'), '--', '--root', str(args.root)]
    runpy.run_path(str(ROOT/'src/wayfarer/build/build.py'), run_name='__main__')


# ------------------------------------------------------------------------------------------------------------------------------------
def geom(s, records, name):
    """Window, lock-pin and closure figures of the variant, from the shared formulas and the built meshes."""
    import numpy as np
    import copy
    import crew_transfer as ct
    import human_entry as he
    import rotor_interface as ri
    from mathutils.bvhtree import BVHTree
    v = ct.vestibule(s, 2); rot = next(r for r in ri.rotors(s) if r['index'] == 2); x2 = rot['x']; p = s['prototype']; r_ = s['rotor_interface']
    out = dict(port_clear_m=round(2*v['port_clear'], 3), shift_aft_m=s['human_entry']['study']['vestibule_shift_aft_m']['2'],
               vestibule_u_m=[round(v['u0'], 3), round(v['u1'], 3)], port_x_m=round(x2+v['port_u'], 3))
    w = v['window']; wx = x2+w[0]
    out['window_edge_x_m'] = round(wx, 3); out['hub1_withdrawal_end_x_m'] = round(wx-p['mechanical_clearance_m'], 3)
    out['window_intrusion_m'] = round(max(0.0, wx-(x2+v['u0'])), 3)
    fam = lambda n: re.match(r'(Crew_Vestibule_2|Crew_Port_2_)', n)
    tubes = [q for q in records if q['name'].startswith('Crew_Tube_2_')]      # ring-side tubes: outside the drum radii, reported apart (built 0.90 m ring B has the same overhang)
    out['crew_tube_min_x_m'] = round(min(q['lo'][0] for q in tubes), 3) if tubes else None
    mine = [q for q in records if fam(q['name'])]
    mn = min(q['lo'][0] for q in mine); worst = min(mine, key=lambda q: q['lo'][0])
    out['geometry_min_x_m'] = round(mn, 3); out['geometry_min_x_object'] = worst['name']
    out['min_distance_to_window_edge_m'] = round(mn-wx, 3)          # >= 0: window (incl. 0.15 m mechanical clearance) respected
    out['min_distance_to_hub1_withdrawal_end_m'] = round(mn-(wx-p['mechanical_clearance_m']), 3)
    out['window_respected'] = mn-wx >= -0.002
    lx = x2+r_['ring_lock_u_m']; lr = r_['ring_lock_radius_m']
    out['ring_stop_lock_x_m'] = [round(lx-lr, 3), round(lx+lr, 3)]
    aft = max(q['hi'][0] for q in mine if q['name'] in ('Crew_Vestibule_2', 'Crew_Vestibule_2_Guard_Fwd'))
    out['vestibule_aft_end_x_m'] = round(aft, 3)
    out['lock_pin_axial_gap_m'] = round((lx-lr)-aft, 3)             # < 0: the vestibule's aft end passes the lock-pin bound
    # mesh overlaps of the vestibule family with everything that is not its own family / the trunk / spine
    skip = lambda n: bool(fam(n)) or n.startswith(('Crew_Tube_2_', 'Crew_Trunk', 'Structural_Spine', 'Crew_Refuge', 'Crew_Connector', 'Crew_Store', 'Crew_Port')) or n == 'Crew_Trunk'
    hits = {}
    for q in [q for q in mine if q['name'] in ('Crew_Vestibule_2', 'Crew_Vestibule_2_Guard_Fwd', 'Crew_Vestibule_2_Guard_Aft')]:
        tq = BVHTree.FromPolygons([tuple(x) for x in q['vs']], [tuple(f) for f in q['fs']])
        for o in records:
            if skip(o['name']) or any(o['lo'][i] > q['hi'][i] or o['hi'][i] < q['lo'][i] for i in range(3)):
                continue
            to = BVHTree.FromPolygons([tuple(x) for x in o['vs']], [tuple(f) for f in o['fs']])
            if tq.overlap(to):
                hits.setdefault(q['name'], []).append(o['name'])
    out['mesh_overlaps'] = {k: sorted(set(x))[:8] for k, x in hits.items()}
    # trunk ladder
    L = he.trunk_ladder(s); out['ladder'] = dict(deg=s['human_entry']['trunk_ladder_deg'], floor_x_m=round(L['floor'], 3), top_x_m=round(L['top'], 3),
                                                  height_m=round(L['top']-L['floor'], 3))
    table = {}
    for deg in (285, 295, 300, 305, 310):
        sc = copy.deepcopy(s); sc['human_entry']['trunk_ladder_deg'] = float(deg); table[str(deg)] = round(he.trunk_ladder(sc)['top'], 2)
    out['ladder_top_by_angle_deg'] = table
    ref = he.refuge_station(s); rl = L['rl']; W = 1.00
    lat = min(rl*abs(math.sin(ct.angle_diff(a, ref['th']))) if math.cos(ct.angle_diff(a, ref['th'])) > 0 else 9.9 for a in L['stiles'])
    out['refuge'] = dict(turn_deg=s['crew_transfer']['refuge_port_angle_deg'], port_x_m=round(ref['x'], 3),
                         ladder_stile_lateral_to_slot_axis_m=round(lat, 3), slot_half_width_m=W/2, ladder_clear_of_slot=lat > W/2+0.05)
    # closures (ideal static load = area x cabin pressure, DIAGNOSTIC)
    kpa = s['habitat']['atmosphere']['cabin_pressure_kpa']; rc = s['prototype']['spine_core_radius_m']; wall = s['crew_transfer']['passage_wall_m']
    area = math.pi*v['port_clear']**2
    out['closures'] = dict(cabin_pressure_kpa=kpa, ring_b_port_area_m2=round(area, 3), ring_b_port_load_kn=round(area*kpa, 1),
                           n_ring_b_closures_resized=7, spine_core_arc_deg=round(math.degrees(2*math.asin(min(1.0, (v['port_clear']+wall)/rc))), 1),
                           refuge_slot_area_m2=2.30, refuge_slot_load_kn=round(2.30*kpa, 1))
    out['closures']['note'] = ('DIAGNOSTIC ideal static load = clear area x cabin pressure; seals, latches, structure and the closure sets (port gate, 3 drum doors, '
                               '3 tube hatches) OPEN; no closure is modelled for the refuge slot (OD-011)')
    return out


def run_legs(args):
    import bpy
    import numpy as np
    import casualty_sweep as cs
    import hum003_routes as hr
    import human_entry as he
    import crew_transfer as ct
    from spec import load
    patch_vestibule()
    root = work_of(args.variant); parts = args.parts.split(','); carriers = args.carriers
    s = load(root)[0]; bpy.ops.wm.open_mainfile(filepath=str(root/'assets/wayfarer/WF_WAYFARER_001.blend')); ins = cs.load_inspect()
    rng = np.random.default_rng(17); records = cs.scene(s, ins, 1.0)
    vd = UNI/args.variant; vd.mkdir(parents=True, exist_ok=True); jf = vd/'unified.json'
    out = json.loads(jf.read_text()) if jf.exists() else {}
    out.update(variant=args.variant, spec=VARIANTS[args.variant])
    def save():
        jf.write_text(json.dumps(out, indent=1, default=str)+'\n')
    if 'geom' in parts:
        out['geom'] = geom(s, records, args.variant); save(); print('WF_UNI_GEOM', args.variant, json.dumps({k: out['geom'][k] for k in ('window_respected', 'min_distance_to_window_edge_m', 'lock_pin_axial_gap_m')}), flush=True)
    if 'rings' in parts:
        routes = hr.trunk_routes(s); out['rings'] = {}; out['lifts'] = {}
        for k in [k for k in args.routes.split(',') if k in routes]:
            walls = hr.Walls(records, [p for _, p in routes[k]['path']]); out['rings'][k] = {}; out['lifts'][k] = hr.lifts(routes[k])
            for cid in carriers:
                r = hr.sweep_route(walls, hr.CARRIERS[cid], routes[k]['path'], rng, couch=routes[k].get('couch', False)); out['rings'][k][cid] = r
                print('WF_UNI_RING', args.variant, k, cid, r['least_m'], r['status'], r['nearest'], 'staff', r['staff_least_m'], r['staff_nearest'], flush=True)
            save()
    if 'repeat' in parts:             # the staff pose search is random: repeat the port-limited legs with other seeds to show the spread
        routes = hr.trunk_routes(s); out['repeat'] = {}
        for k in ('B2', 'B2-M'):
            walls = hr.Walls(records, [p for _, p in routes[k]['path']])
            for cid in args.repeat_carriers:
                rows = []
                for seed in (101, 102, 103):
                    r = hr.sweep_route(walls, hr.CARRIERS[cid], routes[k]['path'], np.random.default_rng(seed), couch=routes[k].get('couch', False))
                    rows.append(dict(seed=seed, carrier_m=r['least_m'], carrier_nearest=r['nearest'], staff_m=r['staff_least_m'], staff_nearest=r['staff_nearest']))
                    print('WF_UNI_REPEAT', args.variant, k, cid, seed, r['least_m'], r['staff_least_m'], r['staff_nearest'], flush=True)
                out['repeat'][f'{k}/{cid}'] = rows
            save()
    if 'slot' in parts:
        out['slot'] = slot(s, records, rng, carriers); save()
    if 'hoist' in parts:
        out['hoist'] = hr.hoist(s, records, rng, carriers, offsets=(0.20, 0.25)); save()
    out['done'] = sorted(set(out.get('done', []))|set(parts)); save()


def slot(s, records, rng, carriers):
    """The 1.00 x 2.30 m axial refuge slot on the (turned) refuge radial, hum003_routes.run_local's model: a free-space union of the trunk, the refuge
    annulus and the slot; every built fixture of the region (the turned ladder, rails, frames, hoop and anchor rails, panel) as walls, with the faces
    inside the slot cut away; the carrier moved out sideways lying axially to an occupant station without turning."""
    import numpy as np
    import bpy
    import hum003_routes as hr
    import human_entry as he
    import crew_transfer as ct
    ref = he.refuge_station(s); xr = ref['x']; th0 = ref['th']; n_hat = (0.0, math.cos(th0), math.sin(th0)); t_hat = (0.0, -math.sin(th0), math.cos(th0))
    sg = 1 if s['human_entry']['refuge_panel_deg'] >= 0 else -1; berth_a = th0-sg*ref['pitch']*1.5; W, Ls, tr0 = 1.00, 2.30, 0.55
    opening = lambda: [hr.prim_box(ct.radial(xr, (tr0+1.25)/2, th0), ((1, 0, 0), t_hat, n_hat), (Ls, W, 1.25-tr0))]
    def cut(c):
        a = math.atan2(c[2], c[1]); r = math.hypot(c[1], c[2])
        return abs(ct.angle_diff(a, th0)) < math.atan2(W/2+.03, max(r, .3)) and abs(c[0]-xr) < Ls/2+.03 and .5 < r < 1.35
    obj, tree = hr.free_space(s, opening)
    fx = hr.fixtures(records, lambda q: q['name'].startswith('Crew_Trunk_Refuge_Rail'), cut)
    pts = [(x, y, z) for x in np.linspace(87.5, 102.4, 30) for y in (-3, 0, 3) for z in (-3, 0, 3)]
    walls = hr.Walls(fx, pts, free=tree); res = {}
    for cid in carriers:
        car = hr.CARRIERS[cid]; L = hr.length(car); x_head = xr+L/2; poses = []
        for rr in np.linspace(0.0, ref['circulation_r'], 18):
            poses.append(((x_head,)+tuple(np.asarray(n_hat[1:])*rr), (-1.0, 0.0, 0.0), 0.0, f'out r {rr:.2f}'))
        for a in np.linspace(th0, berth_a, 10):
            poses.append(((x_head,)+ct.radial(0, ref['circulation_r'], a)[1:], (-1.0, 0.0, 0.0), a-th0, f'round {math.degrees(a-th0):.0f} deg'))
        for rr in np.linspace(ref['circulation_r'], ref['body_r'], 6):
            poses.append(((x_head,)+ct.radial(0, rr, berth_a)[1:], (-1.0, 0.0, 0.0), berth_a-th0, f'berth r {rr:.2f}'))
        fixed = []
        for h, d, r, lab in poses:
            u, w0, t0 = hr.frame(d, 0.0); a = math.atan2(h[2], h[1]); tang = (0.0, -math.sin(a), math.cos(a))
            fixed.append((h, d, math.atan2(float(np.dot(tang, t0)), float(np.dot(tang, w0))), lab))
        r = hr.sweep_poses(walls, car, fixed, rng); res[cid] = r
        print('WF_UNI_SLOT', cid, r['least_m'], r['status'], r['at'], r['nearest'], flush=True)
    res['staff_margin_m'] = round(W/2-hr.STAFF_R_M, 3)
    bpy.data.objects.remove(obj)
    return res


# ------------------------------------------------------------------------------------------------------------------------------------
def collect():
    out = dict(study='ring B / refuge unified casualty-rescue survey (S&E 15!A135 RESCUE-004; Doc 12:33; owner direction 2026-10-11)',
               status='NONCANON PROTOTYPE disposable study; PERFORMANCE REQUIRED / ALL PRESSURE CUTOUTS HOLD; no re-index under 1.5 g, no spun-ring transport credited',
               method='variant workspaces under runs/hum003/unified/<v>/work (ladder angle, refuge port angle and [human_entry.study] changed; crew_transfer.vestibule patched in memory for vestibule_shift_aft_m)',
               variants={})
    for vd in sorted(UNI.glob('*/unified.json')):
        d = json.loads(vd.read_text()); out['variants'][d['variant']] = d
    data = json.loads(OUT_JSON.read_text()); data[KEY] = out
    OUT_JSON.write_text(json.dumps(data, indent=1, default=str)+'\n')
    print('wrote', OUT_JSON, KEY, list(out['variants']))


# ====================================================================================================================================
# SIM-027 worst-case survey
SURVEY_VARIANTS = ('V0_1.06_aft0.16', 'V1_1.10_aft0.20', 'G1_1.10_guard0.10')
SURVEY_ROUTES = ('B2', 'B2-M', 'B1-B2', 'B3-B2', 'B1-B2-M', 'B3-B2-M', 'B1')
SEEDS_NOMINAL = (17, 101, 102, 103)            # best-found search seeds at x1.00, doors open (the earlier spread 0.010-0.107 came from these streams)
SEEDS_LARGE = (201, 202)
DOOR_PARTIAL = 0.90                            # PROTOTYPE: leaves stop 10 % short of full open


def survey(args):
    import bpy
    import numpy as np
    import casualty_sweep as cs
    import hum003_routes as hr
    from spec import load
    patch_vestibule()
    root = work_of(args.variant); s = load(root)[0]
    bpy.ops.wm.open_mainfile(filepath=str(root/'assets/wayfarer/WF_WAYFARER_001.blend')); ins = cs.load_inspect()
    routes = hr.trunk_routes(s); route = routes[args.route]; car0 = hr.CARRIERS[args.carrier]
    out = dict(variant=args.variant, route=args.route, carrier=args.carrier, sweeps=[], families=[])
    spin = args.route in ('B1',)
    states = [(1.0, 1.0)] if spin else [(1.0, 1.0), (1.0, hr.BODY_SCALE_LARGE), (DOOR_PARTIAL, 1.0)]
    for door, scale in states:
        records = cs.scene(s, ins, door); walls = hr.Walls(records, [p for _, p in route['path']]); car = hr.scaled(car0, scale)
        seeds = SEEDS_NOMINAL[:2] if spin else (SEEDS_NOMINAL if (door, scale) == (1.0, 1.0) else (SEEDS_LARGE if scale != 1.0 else (301,)))
        for seed in seeds:
            r = hr.sweep_route(walls, car, route['path'], np.random.default_rng(seed), couch=route.get('couch', False))
            out['sweeps'].append(dict(door=door, scale=scale, seed=seed, carrier_m=r['least_m'], carrier_nearest=r['nearest'], staff_m=r['staff_least_m'],
                                      staff_nearest=r['staff_nearest'], by_zone={z: v['least_m'] for z, v in r['by_zone'].items()}))
            print('WF_SURVEY_SWEEP', args.variant, args.route, args.carrier, door, scale, seed, r['least_m'], r['nearest'], r['staff_least_m'], flush=True)
        f = hr.family_sweep(walls, car, route['path'], couch=route.get('couch', False)); f.update(door=door, scale=scale); out['families'].append(f)
        print('WF_SURVEY_FAM', args.variant, args.route, args.carrier, door, scale, f['worst_family_m'], f['worst_family'], f['worst_nearest'], f['best_family_m'], f['staff_least_m'], flush=True)
        sd = UNI/args.variant/'survey'; sd.mkdir(parents=True, exist_ok=True); (sd/f'{args.route}_{args.carrier}.json').write_text(json.dumps(out, indent=1, default=str)+'\n')
    out['done'] = True
    (UNI/args.variant/'survey'/f'{args.route}_{args.carrier}.json').write_text(json.dumps(out, indent=1, default=str)+'\n')


def slot_setup(s, records):
    import hum003_routes as hr
    import human_entry as he
    import crew_transfer as ct
    ref = he.refuge_station(s); xr = ref['x']; th0 = ref['th']; n_hat = (0.0, math.cos(th0), math.sin(th0)); t_hat = (0.0, -math.sin(th0), math.cos(th0))
    sg = 1 if s['human_entry']['refuge_panel_deg'] >= 0 else -1; berth_a = th0-sg*ref['pitch']*1.5; W, Ls, tr0 = 1.00, 2.30, 0.55
    opening = lambda: [hr.prim_box(ct.radial(xr, (tr0+1.25)/2, th0), ((1, 0, 0), t_hat, n_hat), (Ls, W, 1.25-tr0))]
    def cut(c):
        a = math.atan2(c[2], c[1]); r = math.hypot(c[1], c[2])
        return abs(ct.angle_diff(a, th0)) < math.atan2(W/2+.03, max(r, .3)) and abs(c[0]-xr) < Ls/2+.03 and .5 < r < 1.35
    import numpy as np
    obj, tree = hr.free_space(s, opening)
    fx = hr.fixtures(records, lambda q: q['name'].startswith('Crew_Trunk_Refuge_Rail'), cut)
    pts = [(x, y, z) for x in np.linspace(87.5, 102.4, 30) for y in (-3, 0, 3) for z in (-3, 0, 3)]
    return dict(ref=ref, xr=xr, th0=th0, n_hat=n_hat, berth_a=berth_a, W=W, walls=hr.Walls(fx, pts, free=tree), obj=obj)


def slot_poses(S, car):
    import numpy as np
    import hum003_routes as hr
    import crew_transfer as ct
    ref, xr, th0, n_hat, berth_a = S['ref'], S['xr'], S['th0'], S['n_hat'], S['berth_a']
    x_head = xr+hr.length(car)/2; poses = []
    for rr in np.linspace(0.0, ref['circulation_r'], 18):
        poses.append(((x_head,)+tuple(np.asarray(n_hat[1:])*rr), (-1.0, 0.0, 0.0), 0.0, f'out r {rr:.2f}'))
    for a in np.linspace(th0, berth_a, 10):
        poses.append(((x_head,)+ct.radial(0, ref['circulation_r'], a)[1:], (-1.0, 0.0, 0.0), a-th0, f'round {math.degrees(a-th0):.0f} deg'))
    for rr in np.linspace(ref['circulation_r'], ref['body_r'], 6):
        poses.append(((x_head,)+ct.radial(0, rr, berth_a)[1:], (-1.0, 0.0, 0.0), berth_a-th0, f'berth r {rr:.2f}'))
    fixed = []
    for h, d, r, lab in poses:
        u, w0, t0 = hr.frame(d, 0.0); a = math.atan2(h[2], h[1]); tang = (0.0, -math.sin(a), math.cos(a))
        fixed.append((h, d, math.atan2(float(np.dot(tang, t0)), float(np.dot(tang, w0))), lab))
    return fixed


def slotsurvey(args):
    """The 1.00 x 2.30 m slot (ladder 300, entry +20): per carrier class, body size and search seed the searched least over the sliding poses, and the
    deterministic family (each pose unsearched, nominal roll) with the six wobbles; the worst case is the minimum of everything."""
    import bpy
    import numpy as np
    import casualty_sweep as cs
    import hum003_routes as hr
    from spec import load
    patch_vestibule()
    root = work_of(args.variant); s = load(root)[0]
    bpy.ops.wm.open_mainfile(filepath=str(root/'assets/wayfarer/WF_WAYFARER_001.blend')); ins = cs.load_inspect()
    records = cs.scene(s, ins, 1.0); S = slot_setup(s, records); out = dict(variant=args.variant, carrier=args.carrier, rows=[])
    for scale in (1.0, hr.BODY_SCALE_LARGE):
        car = hr.scaled(hr.CARRIERS[args.carrier], scale); fixed = slot_poses(S, car); L = hr.length(car)
        seeds = []
        for seed in (17, 101, 102, 103):
            r = hr.sweep_poses(S['walls'], car, fixed, np.random.default_rng(seed)); seeds.append(dict(seed=seed, least_m=r['least_m'], at=r['at'], nearest=r['nearest']))
        fam = (math.inf, None, None); unad = (math.inf, None, None)
        for pi, (h, d, roll, lab) in enumerate(fixed):
            tl = np.asarray(h)+np.asarray(d)*L
            m0 = hr.margin(S['walls'], car, np.asarray(h), np.asarray(d), roll)          # the nominal pose, unadapted
            if m0[0] < unad[0]:
                unad = (round(m0[0], 3), m0[1], lab)
            m, name, hh, dd, rr = hr.best_pose(S['walls'], car, np.asarray(h), tl, roll, np.random.default_rng(500+pi), n=60, spread=.25)   # the pose is adapted as in the search, with its own fixed stream
            if m < hr.CAP_M and car['shape'] == 'capsule':
                m -= 0.035                       # capsule: the signed distance to the free-space wall is unreliable at corners; a wobble moves any point by at most 0.035 m
            elif m < hr.CAP_M:
                tl2 = np.asarray(hh)+np.asarray(dd)*L
                for j in hr.JITTER:
                    h2 = np.asarray(hh)+np.array(j[:3]); d2 = tl2+np.array(j[3:6])-h2; d2 = d2/np.linalg.norm(d2)
                    mj = hr.margin(S['walls'], car, h2, d2, rr+j[6], check_outside=False)      # the nearest-wall sign test is unreliable at free-space corners: wobbles use the overlap test
                    if mj[0] < m:
                        m, name = mj
            if m < fam[0]:
                fam = (round(m, 3), name, lab)
        out['rows'].append(dict(scale=scale, seeds=seeds, family_least_m=fam[0], family_nearest=fam[1], family_at=fam[2], unadapted_least_m=unad[0], unadapted_nearest=unad[1], unadapted_at=unad[2]))
        print('WF_SLOTSURVEY', args.variant, args.carrier, scale, [q['least_m'] for q in seeds], fam, unad, flush=True)
    bpy.data.objects.remove(S['obj'])
    sd = UNI/args.variant/'survey'; sd.mkdir(parents=True, exist_ok=True); (sd/f'slot_{args.carrier}.json').write_text(json.dumps(out, indent=1, default=str)+'\n')


HOIST_OPTIONS = (    # (workspace variant, line angle deg or None = ladder + 180 (120), offsets)
    ('V0_1.06_aft0.16', None), ('V0_1.06_aft0.16', 105.0), ('V0_1.06_aft0.16', 110.0), ('V0_1.06_aft0.16', 100.0), ('V0_1.06_aft0.16', 90.0),
    ('V0_rail150', None), ('V0_rail165', None), ('V0_rail150', 110.0))


def hoistopts(args):
    """The hoist line / trunk handrail gap options: for each workspace (handrail position) and line angle, e = 0.20 / 0.25 / 0.30 m, four classes, two body
    sizes, doors 1.00 and 0.90; the carrier's least clearance, its gap to the handrail alone and to the attendant on the ladder."""
    import bpy
    import numpy as np
    import casualty_sweep as cs
    import hum003_routes as hr
    from spec import load
    patch_vestibule()
    root = work_of(args.variant); s = load(root)[0]
    bpy.ops.wm.open_mainfile(filepath=str(root/'assets/wayfarer/WF_WAYFARER_001.blend')); ins = cs.load_inspect()
    rows = []; sd = UNI/args.variant/'survey'; sd.mkdir(parents=True, exist_ok=True)
    angles = [a for v, a in HOIST_OPTIONS if v == args.variant]
    if args.angle is not None:
        angles = [None if args.angle == 'ladder' else float(args.angle)]
    fname = 'hoist.json' if args.angle is None else f'hoist_{args.angle}.json'
    for ang in angles:
        for door in (1.0, DOOR_PARTIAL):
            records = cs.scene(s, ins, door)
            for scale in (1.0, hr.BODY_SCALE_LARGE):
                h = hr.hoist(s, records, np.random.default_rng(5), args.carriers, offsets=(0.20, 0.25, 0.30), guide_deg=ang, scale=scale)
                rows.append(dict(line_deg=h['guide_deg'], handrail_deg=h['handrail_deg'], door=door, scale=scale, offsets=h['offsets'], guide_rail_clear_spans_x=h['guide_rail_clear_spans_x']))
                (sd/fname).write_text(json.dumps(dict(variant=args.variant, rows=rows), indent=1, default=str)+'\n')


def pins(args):
    """Lock-pin relocation clash study (RINGB-005, disposable): in each variant workspace the three Ring_Stop_Lock_2_k housings are moved aft by d
    (0.04-0.14 m) in memory and their meshes tested against every other built mesh; clashes listed, plus the nearest aft neighbour distance."""
    import bpy
    import numpy as np
    import casualty_sweep as cs
    from mathutils.bvhtree import BVHTree
    from spec import load
    patch_vestibule(); res = {}
    for name in ('V0_1.06_aft0.16', 'V1_1.10_aft0.20', 'V2_1.15_aft0.25', 'V3_1.20_aft0.30', 'G1_1.10_guard0.10'):
        root = work_of(name); s = load(root)[0]
        bpy.ops.wm.open_mainfile(filepath=str(root/'assets/wayfarer/WF_WAYFARER_001.blend')); ins = cs.load_inspect(); records = cs.scene(s, ins, 1.0)
        pin = [q for q in records if q['name'].startswith('Ring_Stop_Lock_2_')]
        res[name] = dict(pin_objects=[q['name'] for q in pin], pin_x_m=[round(min(q['lo'][0] for q in pin), 3), round(max(q['hi'][0] for q in pin), 3)] if pin else None, shifts={})
        others = [q for q in records if not q['name'].startswith('Ring_Stop_Lock_2_')]
        import bisect
        lo_ = [min(q['lo'][i] for q in pin)-0.5 for i in range(3)]; hi_ = [max(q['hi'][i] for q in pin)+0.5 for i in range(3)]
        vs_, fs_, nearest_off, nearest_names = [], [], [], []
        for o in others:
            if all(o['lo'][i] <= hi_[i] and o['hi'][i] >= lo_[i] for i in range(3)):
                nearest_off.append(len(fs_)); nearest_names.append(o['name']); n_ = len(vs_)
                vs_ += [tuple(x) for x in o['vs']]; fs_ += [tuple(i+n_ for i in f) for f in o['fs']]
        nearest_tree = BVHTree.FromPolygons(vs_, fs_)
        for d in (0.0, 0.04, 0.06, 0.09, 0.10, 0.14):
            hits = {}; nearest_aft = None
            for q in pin:
                vs = [(v[0]+d, v[1], v[2]) for v in q['vs']]; tq = BVHTree.FromPolygons(vs, [tuple(f) for f in q['fs']])
                lo = [min(v[i] for v in vs) for i in range(3)]; hi = [max(v[i] for v in vs) for i in range(3)]
                for o in others:
                    if any(o['lo'][i] > hi[i] or o['hi'][i] < lo[i] for i in range(3)):
                        continue
                    to = BVHTree.FromPolygons([tuple(x) for x in o['vs']], [tuple(f) for f in o['fs']])
                    if tq.overlap(to):
                        hits.setdefault(q['name'], set()).add(o['name'])
            near = (math.inf, None)                  # least vertex-to-surface distance of the relocated pins to every other mesh (a fact, not a clearance claim)
            from mathutils import Vector
            for q in pin:
                for v_ in q['vs'][::7]:
                    hit = nearest_tree.find_nearest(Vector((v_[0]+d, v_[1], v_[2])))
                    if hit[0] is not None and hit[3] < near[0]:
                        near = (hit[3], nearest_names[bisect.bisect_right(nearest_off, hit[2])-1])
            res[name]['shifts'][f'{d:.2f}'] = {k: sorted(v)[:10] for k, v in hits.items()}
            res[name]['nearest_mesh'] = res[name].get('nearest_mesh', {}); res[name]['nearest_mesh'][f'{d:.2f}'] = [round(near[0], 4), near[1]]
            print('WF_PINS', name, d, {k: len(v) for k, v in hits.items()}, near, flush=True)
    sd = UNI/'_sim027'; sd.mkdir(parents=True, exist_ok=True); (sd/'pins.json').write_text(json.dumps(res, indent=1, default=str)+'\n')


def survey_run(args):
    """Run every survey / slot / hoist job as a separate Blender process, a pool of --workers."""
    from concurrent.futures import ThreadPoolExecutor
    jobs = []
    for v in SURVEY_VARIANTS:
        for r in SURVEY_ROUTES:
            for c in ('A', 'C', 'K', 'S'):
                jobs.append((f'survey {v} {r} {c}', ['survey', '--variant', v, '--route', r, '--carrier', c], UNI/v/'survey'/f'{r}_{c}.json'))
        for c in ('A', 'C', 'K', 'S'):
            jobs.append((f'slot {v} {c}', ['slotsurvey', '--variant', v, '--carrier', c], UNI/v/'survey'/f'slot_{c}.json'))
    for v in sorted({v for v, _ in HOIST_OPTIONS}):
        jobs.append((f'hoist {v}', ['hoistopts', '--variant', v, '--carriers', 'ACKS'], UNI/v/'survey'/'hoist.json'))
    jobs.append(('pins', ['pins'], UNI/'_sim027'/'pins.json'))
    jobs = [j for j in jobs if args.only in j[0]]
    # long routes first
    jobs.sort(key=lambda j: (0 if 'B1-B2' in j[0] or 'B3-B2' in j[0] else 1 if j[0].startswith('survey') else 2))
    def run(j):
        label, argv, _ = j; log = UNI/'_sim027'/(re.sub(r'[^A-Za-z0-9_.-]+', '_', label)+'.log'); log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, 'w') as f:
            code = subprocess.call(['timeout', '-s', 'KILL', '5400', BLENDER, '-b', '--factory-startup', '--python', str(Path(__file__).resolve()), '--']+argv,
                                   stdout=f, stderr=subprocess.STDOUT, cwd=ROOT)
        print('done', label, code, flush=True); return code
    with ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(run, jobs))


# ------------------------------------------------------------------------------------------------------------------------------------
# distributed protected care point (RINGB-007 "truly equivalent distributed protected alternative", PROTOTYPE study, geometry facts only)
CARE = dict(couch=(2.00, 0.70), attendant_w=0.60, head_end=0.60, stand_h=1.90, kneel_h=1.20, thick_deck=0.80, thick_floor=0.30, walk_w=0.60, grid=0.05)
# existing furniture that could serve as the care point without adding volume: (frame, block name, function filter or None, note)
EXISTING = (('deck', 'Medical_Couch', 'WORK_MEDICAL_OPS', 'the built treatment couch (SP-33)', ()),
            ('deck', 'Bunk_1', 'HABITATION', 'the lowest berth tier, open to the aisle (1.95 x 0.75 m minimum berth)', ('Bunk_Base_1', 'Bunk_2', 'Bunk_3')),
            ('aft', 'Burn_Couch_1', None, 'the aft-bulkhead burn couch (supine, aft down at 1.5 g), 2.0 x 0.7 m', ('Couch_Lockers_1',)),
            ('aft', 'Burn_Couch_2', None, 'the aft-bulkhead burn couch on the other side of the aisle', ('Couch_Lockers_2',)))
CARE_CAP_M = 0.30


def _gap(a, b):
    """Signed separation of two axis-aligned boxes: Euclidean distance when apart, minus the least overlap depth when they intersect."""
    g = [max(a[0][k]-b[1][k], b[0][k]-a[1][k]) for k in range(3)]
    if max(g) < 0:
        return max(g)
    return math.sqrt(sum(max(0.0, x)**2 for x in g))


def distributed():
    """Does a protected care / stabilisation point (couch + attendant strip 0.60 m wide + 0.60 m airway end, PROTOTYPE sizes in CARE) fit inside the free
    volume of each ring sector, reachable from the sector's hatch landing over a 0.60 m path, without leaving the sector? Two frames: `deck` (0 g,
    spinning, stopped: the deck is the floor, a 0.80 m couch on it) and `aft` (locked 1.5 g, aft down: the aft bulkhead is the floor, a 0.30 m stretcher on it,
    zone blocks hang above it). (1) A new couch anywhere: couch centre on a 0.05 m grid, long axis along either floor axis, strip on either long side,
    airway space at either end, attendant standing (1.90 m) or kneeling (1.20 m). (2) Existing furniture used as the care point (EXISTING). The metric is
    the least gap from the envelope to the fixed zone blocks, the side walls, the ends and the landing well / ladder (maximised over placements); it
    is a fit screen of the zone blocks only (thin fit-out is not modelled), PROTOTYPE, and no medical or protection qualification."""
    import numpy as np
    import habitat_interior as hi
    import human_entry as he
    from spec import load
    s = load(ROOT)[0]; sec = hi.section(s); L = he.landing(s); skin = s['habitat_ring']['sector_skin_m']; wall = s['interior']['wall_allowance_m']
    ln = sec['length_m']; xlo, xhi = -ln/2+skin, ln/2-skin; ceil = sec['ceiling_y_m']; ts = he.thrust_step(s); c = CARE; g = c['grid']
    res = dict(params=c, sector_length_m=ln, deck_width_m=round(sec['deck_width_m'], 3), headroom_m=round(sec['headroom_m'], 3), aisle_m=s['interior']['aisle_m'],
               landing_well_x_m=L['well_x'], landing_well_z_m=list(L['well_z']), chase_z_m=list(L['chase_z']), functions={})
    keep = [((L['well_x'][0], ceil, min(L['well_z'][0], L['chase_z'][0])), (L['well_x'][1], 0.0, max(L['well_z'][1], L['chase_z'][1]))),
            ((L['stile_x'][0]-.1, ceil, L['stile_z']-.1), (L['stile_x'][1]+.1, 0.0, L['stile_z']+.1))]
    half = lambda y: hi.wall_half_width(s, y)-wall
    f_ = lambda v: float(round(float(v), 3))
    for fn in s['habitat']['layout']['functions']:
        blocks = [(tuple(b['min']), tuple(b['max']), b['name']) for b in hi.zones(s, fn)]
        out = {}
        for frame in ('deck', 'aft'):
            if frame == 'deck':
                P = lambda lo, hi_: ((lo[0], lo[2]), (hi_[0], hi_[2]), (-hi_[1], -lo[1]))
                u_rng = (xlo, xhi); thick = c['thick_deck']
                zhalf = lambda u0, u1, h: half(-h)
            else:
                P = lambda lo, hi_: ((lo[1], lo[2]), (hi_[1], hi_[2]), (lo[0]-xlo, hi_[0]-xlo))
                u_rng = (ceil, 0.0); thick = c['thick_floor']
                zhalf = lambda u0, u1, h: min(half(u0), half(u1))
            rects = [(*P(lo, hi_), n) for lo, hi_, n in blocks] + [(*P(lo, hi_), 'landing_well') for lo, hi_ in keep]
            def assess(env, exclude=()):
                """env: [(u0, u1, z0, z1, h0, h1)] -> (clearance, nearest): least gap to the other blocks (capped at CARE_CAP_M); a side wall or an end counts
                only if the envelope pokes through it (a flush fit is not a clash)."""
                best = (CARE_CAP_M, None)
                for e in env:
                    for (a0, a1, hh, n) in rects:
                        if n in exclude:
                            continue
                        gg = _gap(((e[0], e[2], e[4]), (e[1], e[3], e[5])), ((a0[0], a0[1], hh[0]), (a1[0], a1[1], hh[1])))
                        if gg < best[0]:
                            best = (gg, n)
                    zh = zhalf(e[0], e[1], e[5])
                    for gg, n in ((e[0]-u_rng[0], 'end_wall'), (u_rng[1]-e[1], 'end_wall'), (e[2]+zh, 'side_wall'), (zh-e[3], 'side_wall')):
                        if gg < -1e-9 and gg < best[0]:
                            best = (gg, n)
                return best
            def reach(env, exclude=()):
                """0.60 m wide path (cells eroded by 0.30 m) from the landing to the attendant strip (env[1]), over the floor plane, around blocks that
                intersect a standing body column and around the couch and airway space."""
                us = np.arange(u_rng[0], u_rng[1]+1e-9, g); zs = np.arange(-2.65, 2.65+1e-9, g)
                occ = np.zeros((len(us), len(zs)), bool)
                for a0, a1, hh, n in rects:
                    if n == 'landing_well' or n in exclude:
                        continue
                    if hh[1] > 0.05 and hh[0] < c['stand_h']:
                        occ[np.ix_((us > a0[0]+1e-9) & (us < a1[0]-1e-9), (zs > a0[1]+1e-9) & (zs < a1[1]-1e-9))] = True
                for e in (env[0], env[2]):
                    occ[np.ix_((us > e[0]+1e-9) & (us < e[1]-1e-9), (zs > e[2]+1e-9) & (zs < e[3]-1e-9))] = True
                for i, u in enumerate(us):
                    zh = zhalf(u, u, 0.0)
                    occ[i, np.abs(zs) > zh+1e-9] = True
                r = int(round(c['walk_w']/2/g)); big = occ.copy()
                for di in range(-r, r+1):
                    for dj in range(-r, r+1):
                        if di*di+dj*dj <= r*r:
                            big |= np.roll(np.roll(occ, di, 0), dj, 1)
                start = (((L['well_x'][0]+L['well_x'][1])/2, (L['well_z'][0]+L['well_z'][1])/2) if frame == 'deck' else (ts['y']-0.35, ts['z']))
                goal = ((env[1][0]+env[1][1])/2, (env[1][2]+env[1][3])/2)
                def near(p):
                    i0 = int(np.argmin(abs(us-p[0]))); j0 = int(np.argmin(abs(zs-p[1])))
                    for rad in range(0, 8):
                        for di in range(-rad, rad+1):
                            for dj in range(-rad, rad+1):
                                i, j = i0+di, j0+dj
                                if 0 <= i < len(us) and 0 <= j < len(zs) and not big[i, j]:
                                    return i, j
                    return None
                a_, b_ = near(start), near(goal)
                if not (a_ and b_):
                    return False
                seen = {a_}; stack = [a_]
                while stack:
                    i, j = stack.pop()
                    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        q = (i+di, j+dj)
                        if 0 <= q[0] < len(us) and 0 <= q[1] < len(zs) and q not in seen and not big[q]:
                            seen.add(q); stack.append(q)
                return b_ in seen
            res_frame = dict(new_couch={}, existing=[])
            clen, cw = c['couch']
            for stance, hatt in (('standing', c['stand_h']), ('kneeling', c['kneel_h'])):
                best = (-math.inf, None)
                for axis in (0, 1):
                    lu, lz = (clen, cw) if axis == 0 else (cw, clen)
                    for uc in np.arange(u_rng[0]+lu/2, u_rng[1]-lu/2+1e-9, g):
                        for zc in np.arange(-2.6, 2.6+1e-9, g):
                            cu0, cu1, cz0, cz1 = uc-lu/2, uc+lu/2, zc-lz/2, zc+lz/2
                            for side in (-1, 1):
                                for end in (-1, 1):
                                    if axis == 0:
                                        st = (cu0, cu1, *((cz1, cz1+c['attendant_w']) if side > 0 else (cz0-c['attendant_w'], cz0)))
                                        hd = (*((cu1, cu1+c['head_end']) if end > 0 else (cu0-c['head_end'], cu0)), cz0, cz1)
                                    else:
                                        st = (*((cu1, cu1+c['attendant_w']) if side > 0 else (cu0-c['attendant_w'], cu0)), cz0, cz1)
                                        hd = (cu0, cu1, *((cz1, cz1+c['head_end']) if end > 0 else (cz0-c['head_end'], cz0)))
                                    env = [(cu0, cu1, cz0, cz1, 0.0, thick), (*st, 0.0, hatt), (*hd, 0.0, hatt)]
                                    gm = assess(env)
                                    if gm[0] > best[0]:
                                        best = (gm[0], dict(couch_centre_uz=[f_(uc), f_(zc)], long_axis='u' if axis == 0 else 'z', attendant_side=side, airway_end=end,
                                                            nearest=gm[1], env=[[f_(x) for x in e] for e in env]))
                if best[1] is not None:
                    rch = reach(best[1]['env'])
                    res_frame['new_couch'][stance] = dict(clearance_m=f_(best[0]), fits=bool(best[0] >= 0.0), meets_0_05=bool(best[0] >= 0.05), reachable_by_0_60_path=bool(rch), **best[1])
                else:
                    res_frame['new_couch'][stance] = dict(clearance_m=None, fits=False, meets_0_05=False, reachable_by_0_60_path=None)
            # existing furniture
            for fr, bname, func, note, own in EXISTING:
                if fr != frame or (func and func != fn):
                    continue
                b = next((q for q in blocks if q[2] == bname), None)
                if b is None:
                    continue
                (r0, r1, hh) = P(b[0], b[1])[0], P(b[0], b[1])[1], P(b[0], b[1])[2]
                u0, z0, u1, z1 = r0[0], r0[1], r1[0], r1[1]
                aisle_side_z = 0.0
                for stance, hatt in (('standing', c['stand_h']), ('kneeling', c['kneel_h'])):
                    cand = []
                    # the strip on the side facing the aisle (|z| < aisle/2) for the deck berth, on either long side for a burn couch
                    for side in (-1, 1):
                        for end in (-1, 1):
                            if frame == 'deck':          # long axis u (x)
                                st = (u0, u1, *((z1, z1+c['attendant_w']) if side > 0 else (z0-c['attendant_w'], z0)))
                                hd = (*((u1, u1+c['head_end']) if end > 0 else (u0-c['head_end'], u0)), z0, z1)
                            else:                        # burn couch: long axis y (plane u), strip beside it in z; airway end along u
                                st = (u0, u1, *((z1, z1+c['attendant_w']) if side > 0 else (z0-c['attendant_w'], z0)))
                                hd = (*((u1, u1+c['head_end']) if end > 0 else (u0-c['head_end'], u0)), z0, z1)
                            env = [(u0, u1, z0, z1, hh[0], hh[1]), (*st, 0.0, hatt), (*hd, 0.0, hatt)]
                            gm = assess(env[1:], exclude=(bname,)+own)         # the strip and airway space only: the furniture touches its own structure by design
                            cand.append((gm[0], gm[1], side, end, env))
                    gm = max(cand, key=lambda q: q[0])
                    res_frame['existing'].append(dict(block=bname, note=note, stance=stance, clearance_m=f_(gm[0]), fits=bool(gm[0] >= 0.0), meets_0_05=bool(gm[0] >= 0.05),
                                                      nearest=gm[1], attendant_side=gm[2], airway_end=gm[3], reachable_by_0_60_path=bool(reach(gm[4], exclude=(bname,)+own)),
                                                      env=[[f_(x) for x in e] for e in gm[4]]))
            out[frame] = res_frame
            print('WF_DISTRIBUTED', fn, frame, {k: v.get('clearance_m') for k, v in res_frame['new_couch'].items()}, [(q['block'], q['stance'], q['clearance_m'], q['reachable_by_0_60_path']) for q in res_frame['existing']], flush=True)
        res['functions'][fn] = out
    res['status'] = 'PROTOTYPE fit screen of the zone blocks; no medical or protection qualification; not a generator change'
    sd = UNI/'_sim027'; sd.mkdir(parents=True, exist_ok=True); (sd/'distributed.json').write_text(json.dumps(res, indent=1, default=str)+'\n')
    return res


# ------------------------------------------------------------------------------------------------------------------------------------
# SIM-027 aggregation (system python): survey files -> references/p1_access_seg_ringb.json and p1_hum003.json[sim027_worst_case_2026_10_11]
SEG_JSON = ROOT/'references/p1_access_seg_ringb.json'
SIM_KEY = 'sim027_worst_case_2026_10_11'
UNSUITED = 'ACK'
STATUS_ORDER = {'FAIL': 0, 'OPEN': 1, 'MARGINAL': 2, 'PASS': 3}


def _st(m):
    return 'OPEN' if m is None else ('FAIL' if m < 0 else ('MARGINAL' if m < 0.05 else 'PASS'))


def _worse(*sts):
    return min(sts, key=lambda s: STATUS_ORDER[s])


def _entries(d, cls, zones=None):
    """All clearance values of one survey file: (value, nearest, label). zones: restrict the sweeps to those by-zone minima (families are not zoned)."""
    out = []
    for sw in d['sweeps']:
        lab = f"{cls} x{sw['scale']:.2f} doors {sw['door']:.2f} seed {sw['seed']}"
        if zones:
            for z in zones:
                v = sw['by_zone'].get(z)
                if v is not None:
                    out.append((v, None, lab+f' zone {z}'))
            continue
        out.append((sw['carrier_m'], sw['carrier_nearest'], lab+' carrier'))
        if sw['staff_m'] is not None:
            out.append((sw['staff_m'], sw['staff_nearest'], lab+' staff'))
    if not zones:
        for f in d['families']:
            lab = f"{cls} x{f['scale']:.2f} doors {f['door']:.2f}"
            if f['best_family_m'] is not None:
                out.append((f['best_family_m'], f['best_family_nearest'], lab+' best family (+-0.02 m wobble)'))
            if f['staff_least_m'] is not None:
                out.append((f['staff_least_m'], f['staff_nearest'], lab+' staff families'))
    return out


def seg_stats(v, route, classes, zones=None):
    """Worst case of one route in one variant over the classes: dict(least_m, nearest, case, spread, per_class, search_min, unadapted)."""
    per = {}; allv = []; spread = None; search = []; unad = []
    for c in classes:
        f = UNI/v/'survey'/f'{route}_{c}.json'
        if not f.exists():
            continue
        d = json.loads(f.read_text()); e = _entries(d, c, zones)
        if not e:
            continue
        w = min(e, key=lambda q: q[0]); per[c] = dict(least_m=round(w[0], 3), nearest=w[1], case=w[2]); allv += e
        nom = [min([sw['carrier_m']]+([sw['staff_m']] if sw['staff_m'] is not None else [])) if not zones else min(sw['by_zone'].get(z, 9) for z in zones)
               for sw in d['sweeps'] if sw['scale'] == 1.0 and sw['door'] == 1.0]
        if nom and (spread is None or min(nom) < spread[0]):
            spread = [round(min(nom), 3), round(max(nom), 3)]
        search += [(min([sw['carrier_m']]+([sw['staff_m']] if sw['staff_m'] is not None else [])), c) for sw in d['sweeps']]
        unad += [f_['worst_family_m'] for f_ in d['families'] if f_['worst_family_m'] is not None]
    if not allv:
        return None
    w = min(allv, key=lambda q: q[0])
    return dict(least_m=round(w[0], 3), nearest=w[1], case=w[2], spread=spread, per_class=per, search_min=round(min(search)[0], 3) if search else None,
                unadapted=round(min(unad), 3) if unad else None)


WORST_OVER = {'U': ['injury classes A rigid litter, C vacuum mattress, K litter + kit', 'body size x1.00 and x1.08', 'doors open 1.00 and 0.90', 'search seeds 17,101,102,103 (+201,202 large, 301 doors 0.90)',
                    '6 pose families (axis seed x roll -30/0/+30 deg) with six +-0.02 m / +-0.05 rad wobbles', 'two rescuers (both ends, inline and +-0.10 m lateral)'],
              'S': ['suited casualty S (0.857 m capsule on a litter frame)', 'body size x1.00 and x1.08', 'doors open 1.00 and 0.90', 'search seeds',
                    '6 pose families with wobbles', 'two rescuers']}


def sim027():
    built_a = json.loads((ROOT/'runs/hum003/built_A/hum003_rings.json').read_text())['routes']
    segs = []; res = dict(study='SIM-027 worst-case survey (owner 2026-10-11 16:45, RINGB-005..007)', variants={})
    VLAB = {'V0_1.06_aft0.16': 'V0 1.06 m port, vestibule 0.16 m aft, guards 0.20 m (window and pins respected)',
            'V1_1.10_aft0.20': 'V1 1.10 m port, vestibule 0.20 m aft (pins overlap 0.04 m; lock-pin relocation study)',
            'G1_1.10_guard0.10': 'G1 1.10 m port, guards 0.10 m (comparison only, not authorized)'}
    ring_routes = {'B2': ('ringB_B2->trunk', ['0g', 'stopped', 'locked_1.5g'], 'indexed sector 2 to the trunk (valid for an indexed B1/B3 by symmetry)'),
                   'B2-M': ('ringB_B2->couch', ['0g', 'spin', 'stopped', 'locked_1.5g'], 'trunk to the indexed sector 2 landing and the medical couch'),
                   'B1-B2': ('B1->B2', ['stopped', 'locked_1.5g', 'spin'], 'sector 1 to sector 2 landing through the drum annulus (no re-index)'),
                   'B3-B2': ('B3->B2', ['stopped', 'locked_1.5g', 'spin'], 'sector 3 to sector 2 landing through the drum annulus (no re-index)'),
                   'B1-B2-M': ('B1->B2->couch', ['stopped', 'locked_1.5g', 'spin'], 'sector 1 through the annulus to the sector 2 couch'),
                   'B3-B2-M': ('B3->B2->couch', ['stopped', 'locked_1.5g', 'spin'], 'sector 3 through the annulus to the sector 2 couch'),
                   'B1': ('ringB_spin_port_turn', ['spin'], 'trunk to a non-indexed sector through the spine-port turn (ring turning)')}
    leg = {}
    for v in SURVEY_VARIANTS:
        for r, (rid, states, desc) in ring_routes.items():
            for grp, classes in (('U', UNSUITED), ('S', 'S')):
                st = seg_stats(v, r, classes)
                if not st:
                    continue
                leg[(v, r, grp)] = st
                spun = r in ('B1-B2', 'B3-B2', 'B1-B2-M', 'B3-B2-M')
                status = _st(st['least_m'])
                note = (f"{desc}. Per-class worst {json.dumps({c: x['least_m'] for c, x in st['per_class'].items()})}; search-best minimum over seeds {st['search_min']}; "
                        f"unadapted worst family {st['unadapted']} (a bound, not a pose rescuers keep). Worst: {st['case']}.")
                sstates = list(states)
                if spun and 'spin' in sstates:
                    note += ' In spin the annulus legs are geometry only: tube transport under 0.10-0.45 g and Coriolis is not credited (OPEN).'
                segs.append(dict(id=f"{rid}|{v.split('_')[0]}|{grp}", route=rid, states=sstates, variant=v, case=('unsuited A/C/K, worst: ' if grp == 'U' else 'suited S, worst: ')+st['case'],
                                 least_m=st['least_m'], status=status, worst_case_over=WORST_OVER[grp], seed_spread_m=st['spread'], nearest=st['nearest'], note=note))
    # slot (trunk -> refuge occupant station)
    slotv = {}
    for v in SURVEY_VARIANTS:
        for grp, classes in (('U', UNSUITED), ('S', 'S')):
            rows = []
            for c in classes:
                f = UNI/v/'survey'/f'slot_{c}.json'
                if f.exists():
                    d = json.loads(f.read_text())
                    for r_ in d['rows']:
                        sd = [q['least_m'] for q in r_['seeds']]
                        rows.append(dict(cls=c, scale=r_['scale'], seeds=sd, family=r_['family_least_m'], family_nearest=r_['family_nearest'], family_at=r_['family_at'], unadapted=r_.get('unadapted_least_m'),
                                         nearest=[q['nearest'] for q in r_['seeds'] if q['least_m'] == min(sd)][0]))
            if not rows:
                continue
            cand = []
            for q in rows:
                cand += [(min(q['seeds']), q['nearest'], f"{q['cls']} x{q['scale']:.2f} searched poses"), (q['family'], q['family_nearest'], f"{q['cls']} x{q['scale']:.2f} adapted poses '{q['family_at']}' with wobbles")]
            w = min(cand, key=lambda q: q[0]); nominal = [x for q in rows if q['scale'] == 1.0 for x in q['seeds']]
            slotv[(v, grp)] = dict(least_m=w[0], nearest=w[1], case=w[2], spread=[min(nominal), max(nominal)], rows=rows)
            segs.append(dict(id=f"trunk->refuge slot|{v.split('_')[0]}|{grp}", route='trunk->refuge', states=['0g', 'spin', 'stopped', 'locked_1.5g'], variant=v,
                             case=('unsuited A/C/K, worst: ' if grp == 'U' else 'suited S, worst: ')+w[2], least_m=round(w[0], 3), status=_st(w[0]),
                             worst_case_over=['injury classes '+('A, C, K' if grp == 'U' else 'S'), 'body size x1.00 and x1.08', 'search seeds 17,101,102,103', 'sliding pose family locally adapted with six wobbles',
                                              'two rescuers (analytic: 0.25 m beside each side of the 1.00 m slot)'], seed_spread_m=[round(min(nominal), 3), round(max(nominal), 3)], nearest=w[1],
                             note='1.00 x 2.30 m axial slot at +20 deg, ladder 300 deg; the carrier is slid out sideways lying axially to an occupant station (local free-space model); at 1.5 g it stands upright after the hoist. Doors: the slot has no closure (OD-011), OPEN.'))
    # hoist options
    hoist = {}
    for hf in sorted(UNI.glob('*/survey/hoist*.json')):
        d = json.loads(hf.read_text())
        for row in d['rows']:
            for cid, offs in row['offsets'].items():
                for k, o in offs.items():
                    key = (d['variant'], row['line_deg'], o['offset_m'], 'S' if cid == 'S' else 'U')
                    h = hoist.setdefault(key, dict(handrail_deg=row['handrail_deg'], carrier=[], rail=[], attendant=[]))
                    lab = f"{cid} x{row['scale']:.2f} doors {row['door']:.2f} {o['roll']}"
                    h['carrier'].append((o['carrier_least_m'], o['nearest'], lab, row['scale']))
                    if o.get('handrail_gap_m') is not None:
                        h['rail'].append((o['handrail_gap_m'], o.get('handrail_nearest'), lab, row['scale']))
                    h['attendant'].append((o['attendant_gap_m'], 'attendant on the trunk ladder', lab, row['scale']))
    hoist_rows = []
    for (var, line, e, grp), h in sorted(hoist.items()):
        allv = h['carrier']+h['attendant']; w = min(allv, key=lambda q: q[0]); rg = min(h['rail'], key=lambda q: q[0]) if h['rail'] else (None, None, None)
        cg = min(h['carrier'], key=lambda q: q[0]); ag = min(h['attendant'], key=lambda q: q[0])
        by_scale = {}
        for sc_ in sorted({q[3] for q in h['carrier']}):
            mn = lambda lst: (round(min(q[0] for q in lst if q[3] == sc_), 3) if any(q[3] == sc_ for q in lst) else None)
            by_scale[f'x{sc_:.2f}'] = dict(carrier_least_m=mn(h['carrier']), handrail_gap_m=mn(h['rail']), attendant_gap_m=mn(h['attendant']))
        hoist_rows.append(dict(workspace=var, line_deg=line, handrail_deg=h['handrail_deg'], e_m=e, group=grp, by_scale=by_scale, least_m=round(w[0], 3), case=w[2], nearest=w[1],
                               carrier_least_m=round(cg[0], 3), carrier_nearest=cg[1], handrail_gap_m=rg[0], handrail_case=rg[2], attendant_gap_m=round(ag[0], 3), attendant_case=ag[2]))
        segs.append(dict(id=f"hoist|{var.split('_')[0] if var.startswith('V0_rail') is False else var}|line{line:g}|e{e:.2f}|{grp}", route='hoist', states=['0g', 'spin', 'stopped', 'locked_1.5g'], variant=var,
                         case=f"line {line:g} deg, offset {e:.2f} m, handrail(s) at {h['handrail_deg']}, "+('unsuited A/C/K' if grp == 'U' else 'suited S')+f", worst: {w[2]}",
                         least_m=round(w[0], 3), status=_st(w[0]), worst_case_over=['injury classes '+('A, C, K' if grp == 'U' else 'S'), 'body size x1.00 and x1.08', 'doors 1.00 and 0.90',
                                                                                  'two roll families (thin side / flat to the ladder)', 'attendant on the trunk ladder at every height'],
                         seed_spread_m=None, nearest=w[1], note=f"carrier least {round(cg[0], 3)} ({cg[1]}); gap to handrail alone {rg[0]} ({rg[1]}); gap to the ladder attendant {round(ag[0], 3)}. Deterministic scan, no search seeds."))
    # ring A, quoted from built_A (single seed, no scale / door / family variants)
    def ra(key):
        r = built_a[key]; vals = [(min(x for x in (q['least_m'], q['staff_least_m']) if x is not None), q['nearest'] or q['staff_nearest'], c) for c, q in r.items()]
        return min(vals, key=lambda q: q[0])
    ringA = {}
    for key, rid, states, desc in (('A1', 'ringA_A1->trunk', ['0g', 'stopped', 'locked_1.5g'], 'sector 1 (indexed) to the trunk'),
                                   ('A2', 'ringA_A2->trunk', ['spin'], 'trunk to a non-indexed sector through the spine-port turn (ring turning)'),
                                   ('A3', 'ringA_A3->trunk', ['spin'], 'trunk to a non-indexed sector through the spine-port turn (ring turning)'),
                                   ('A1-A2', 'A1->A2', ['stopped', 'locked_1.5g'], 'annulus leg'), ('A3-A2', 'A3->A2', ['stopped', 'locked_1.5g'], 'annulus leg'),
                                   ('A1-A2-M', 'A1->A2->couch', ['stopped', 'locked_1.5g'], 'annulus leg and couch'), ('A3-A2-M', 'A3->A2->couch', ['stopped', 'locked_1.5g'], 'annulus leg and couch')):
        m = ra(key); ringA[key] = m
        segs.append(dict(id=f'{rid}|built_A', route=rid, states=states, variant='built (ring A as built, 0.95 m annulus)', case=f'quoted from runs/hum003/built_A: {desc}; worst class {m[2]}',
                         least_m=round(m[0], 3), status=_st(m[0]), worst_case_over=['injury classes A, C, K (carrier and staff)'], seed_spread_m=None, nearest=m[1],
                         note='QUOTED existing single-seed result (HUM-003, no body-size, door or family variants); a minimum over the classes only.'))
    res['segments_n'] = len(segs)
    # ---- sector coverage -------------------------------------------------------------------------------------------------------------
    P = 'V0_1.06_aft0.16'
    g = lambda r, grp='U', v=P: leg.get((v, r, grp))
    gm = lambda r, v=P: g(r, 'U', v)['least_m'] if g(r, 'U', v) else None
    zmin = lambda r, zs, v=P: (lambda s_: s_['least_m'] if s_ else None)(seg_stats(v, r, UNSUITED, zones=zs))
    H = [x for x in hoist_rows if x['workspace'] == 'V0_1.06_aft0.16' and x['group'] == 'U' and x['line_deg'] == 120 and x['e_m'] == 0.25]
    Hm = H[0]['least_m'] if H else None
    T = slotv.get((P, 'U'))['least_m'] if slotv.get((P, 'U')) else None
    lo = lambda *xs: None if any(x is None for x in xs) else min(xs)
    cov = {}
    def entry(spec):
        return {k: v for k, v in spec.items()}
    # ring B
    b_idx = gm('B2'); b_c = gm('B2-M'); b_l1 = gm('B1-B2'); b_l3 = gm('B3-B2'); b_m1 = gm('B1-B2-M'); b_m3 = gm('B3-B2-M'); b_spin = gm('B1')
    b2_land_couch = zmin('B2-M', ['M', '5'])
    def put(sec, st, basis):
        cov[sec] = dict(st, basis=basis)
    refuge_tail = lo(Hm, T)
    # B2: indexed
    ref0 = lo(b_idx, refuge_tail); care0 = lo(b_c)
    put('Sector_2_2', {'0g': _worse(_st(ref0), _st(care0)), 'spin': _worse('FAIL' if (b_spin is not None and b_spin < 0) else 'OPEN', _st(b2_land_couch)),
                       'stopped': _worse(_st(ref0), _st(care0)), 'locked_1.5g': _worse(_st(ref0), _st(care0))},
        f"V0 (1.06 m). Sector 2 is the indexed sector with the couch. Care = trunk-or-landing to couch B2-M worst {b_c}; in-sector landing to couch (zones 5, M) {b2_land_couch}. Refuge = B2 to trunk {b_idx}, hoist {Hm} (line 120, e 0.25), slot {T}. "
        f"Spin: the ring-turning port turn B1 is {b_spin} (rigid carrier FAIL), so refuge access needs the ring stopped/indexed; spun-ring transport not credited.")
    for sec, rl, ml in (('Sector_2_1', b_l1, b_m1), ('Sector_2_3', b_l3, b_m3)):
        two_index_care = lo(b_idx, b_c)               # 0 g: re-index to this sector, up the trunk, re-index to sector 2
        care_0g = max(x for x in (two_index_care, ml) if x is not None); ref_0g = lo(b_idx, refuge_tail)
        care_lk = ml; ref_lk = lo(rl, b_idx, refuge_tail)
        put(sec, {'0g': _worse(_st(care_0g), _st(ref_0g)), 'spin': 'FAIL' if (b_spin is not None and b_spin < 0) else 'OPEN',
                  'stopped': _worse(_st(care_lk), _st(ref_lk)), 'locked_1.5g': _worse(_st(care_lk), _st(ref_lk))},
            f"V0 (1.06 m). 0 g: re-index to this sector (B2 geometry {b_idx}) and go straight to the trunk; care by two indexings {two_index_care} or by the annulus {ml}; refuge {ref_0g}. "
            f"Stopped / locked 1.5 g (no re-index, CALC-R05): annulus to sector 2 {rl}, annulus to the couch {ml}; refuge = annulus {rl} then B2 {b_idx}, hoist {Hm}, slot {T}. "
            f"Spin: the port turn is {b_spin} (FAIL); the annulus legs are not credited under spin.")
    # ring A (existing built_A data)
    a1 = ringA['A1'][0]; a_turn = min(ringA['A2'][0], ringA['A3'][0]); a_l1 = ringA['A1-A2'][0]; a_l3 = ringA['A3-A2'][0]; a_m1 = ringA['A1-A2-M'][0]; a_m3 = ringA['A3-A2-M'][0]
    tail = lo(Hm, T)
    put('Sector_1_1', {'0g': _worse(_st(lo(a1, tail)), _st(max(lo(a1), a_m1))), 'spin': 'FAIL' if a_turn < 0 else 'OPEN',
                       'stopped': _worse(_st(lo(a_l1, a1, tail)), _st(a_m1)), 'locked_1.5g': _worse(_st(lo(a_l1, a1, tail)), _st(a_m1))},
        f"Quoted built_A (ring A stop/index only, owner). A1 indexed to trunk {a1}; annulus A1-A2 {a_l1}, A1-A2-M {a_m1}; port turn A2/A3 {a_turn}; refuge tail hoist {Hm} + slot {T}.")
    put('Sector_1_2', {'0g': _worse(_st(lo(a1, tail)), 'PASS'), 'spin': 'FAIL' if a_turn < 0 else 'OPEN', 'stopped': _worse(_st(lo(a1, tail)), 'PASS'),
                       'locked_1.5g': _worse(_st(lo(a1, tail)), 'PASS')},
        f"Quoted built_A. A2 indexed (A1 geometry by symmetry) {a1}; landing to couch PASS (zone M >= 0.10 in built_A); refuge tail hoist {Hm} + slot {T}. Spin: port turn {a_turn} FAIL.")
    put('Sector_1_3', {'0g': _worse(_st(lo(a1, tail)), _st(max(lo(a1), a_m3))), 'spin': 'FAIL' if a_turn < 0 else 'OPEN',
                       'stopped': _worse(_st(lo(a_l3, a1, tail)), _st(a_m3)), 'locked_1.5g': _worse(_st(lo(a_l3, a1, tail)), _st(a_m3))},
        f"Quoted built_A. A3 indexed {a1}; annulus A3-A2 {a_l3}, A3-A2-M {a_m3}; port turn {a_turn}; refuge tail hoist {Hm} + slot {T}.")
    res.update(variants_legs={f"{k[0]}|{k[1]}|{k[2]}": {kk: vv for kk, vv in v.items()} for k, v in leg.items()},
               slot={f"{k[0]}|{k[1]}": v for k, v in slotv.items()}, hoist=hoist_rows, ringA_quoted={k: list(v) for k, v in ringA.items()},
               method=dict(seeds_nominal=SEEDS_NOMINAL, seeds_large=SEEDS_LARGE, door_partial=DOOR_PARTIAL, body_scale_large=1.08, families='axis seed {tail, chord} x roll {-30,0,+30} deg, local adaptation, six wobbles',
                           note='search seeds subsampled: 4 nominal, 2 large, 1 partial-door; deterministic family sweeps at every 0.10 m step; the earlier K/B2 spread 0.010-0.107 used 4 seeds'))
    try:
        dist = json.loads((UNI/'_sim027'/'distributed.json').read_text())
    except FileNotFoundError:
        dist = None
    if dist:
        fnames = ['HABITATION', 'WORK_MEDICAL_OPS', 'LIFE_SUPPORT_GARDEN_COMMON']; by_sector = {}
        for ring, rn in ((1, 'A'), (2, 'B')):
            for k, fn in enumerate(fnames, 1):
                e = {}
                for frame, label in (('deck', '0g/spin/stopped (deck frame)'), ('aft', 'locked_1.5g (aft-floor frame)')):
                    fr = dist['functions'][fn][frame]; ex = fr['existing']; nc = fr['new_couch']
                    best = max(ex, key=lambda q: (q['clearance_m'], q['reachable_by_0_60_path'])) if ex else None
                    newc = max(nc.values(), key=lambda q: -9 if q['clearance_m'] is None else q['clearance_m'])
                    use = best if best and best['clearance_m'] >= (newc['clearance_m'] if newc['clearance_m'] is not None else -9) else newc
                    e[frame] = dict(frame=label, candidate=(use.get('block') or 'new couch'), stance=use.get('stance', 'standing/kneeling best'), clearance_m=use['clearance_m'],
                                    reachable_by_0_60_path=use['reachable_by_0_60_path'], status=_st(use['clearance_m']), nearest=use.get('nearest'))
                by_sector[f'Sector_{ring}_{k}'] = dict(function=fn, **e)
        dist['by_sector'] = by_sector
    out = dict(study='SIM-027 ring B / refuge casualty rescue worst-case survey (owner 2026-10-11 16:45, S&E 15!A159:A161 RINGB-005..007); NONCANON PROTOTYPE disposable',
               source=['src/wayfarer/studies/ringb_unified.py', 'src/wayfarer/studies/hum003_routes.py', 'runs/hum003/unified/*/survey/*.json', 'runs/hum003/built_A/hum003_rings.json',
                       'references/p1_hum003.json', 'references/HUM003_CASUALTY_ROUTES.md'],
               segments=segs, sector_coverage=cov, distributed_alternative=dist)
    SEG_JSON.write_text(json.dumps(out, indent=1, default=str)+'\n')
    data = json.loads(OUT_JSON.read_text()); res['segments'] = segs; res['sector_coverage'] = cov; res['distributed_alternative'] = dist
    try:
        res['lock_pin_relocation'] = json.loads((UNI/'_sim027'/'pins.json').read_text())
    except FileNotFoundError:
        res['lock_pin_relocation'] = None
    data[SIM_KEY] = res; OUT_JSON.write_text(json.dumps(data, indent=1, default=str)+'\n')
    print('wrote', SEG_JSON, len(segs), 'segments;', OUT_JSON, SIM_KEY)


# ------------------------------------------------------------------------------------------------------------------------------------
# SVG figures from the aggregated JSON (system python)
FIG_DIR = ROOT/'references'
COL = {'PASS': '#2e7d32', 'MARGINAL': '#e0a800', 'FAIL': '#c62828', 'OPEN': '#777'}


def figures():
    d = json.loads(SEG_JSON.read_text()); segs = d['segments']
    # 1. worst case and seed spread of the ring B / slot legs (unsuited A/C/K and suited S), per variant
    rows = [s_ for s_ in segs if s_['route'] not in ('hoist',) and not s_['route'].startswith('ringA') and s_['variant'] in SURVEY_VARIANTS]
    rows.sort(key=lambda s_: (SURVEY_VARIANTS.index(s_['variant']), s_['route'], s_['id'].endswith('|S')))
    W, rh, x0, x1 = 980, 20, 330, 940; lo, hi = -0.16, 0.12; X = lambda v: x0+(max(lo, min(hi, v))-lo)/(hi-lo)*(x1-x0)
    H = 70+rh*len(rows); o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif" font-size="11">', '<rect width="100%" height="100%" fill="#fff"/>',
                              '<text x="10" y="18" font-size="13" font-weight="bold">SIM-027 worst case per leg (dot) and seed spread of the best-found poses (bar), m</text>',
                              f'<text x="10" y="34" fill="#555">status colour from the worst case; dashed 0.05 m target, solid 0; values below -0.16 clipped at the left edge</text>']
    for v in (-0.15, -0.10, -0.05, 0.0, 0.05, 0.10):
        o.append(f'<line x1="{X(v):.1f}" y1="44" x2="{X(v):.1f}" y2="{H-8}" stroke="{"#000" if v == 0 else "#c62828" if v == 0.05 else "#ddd"}" {"stroke-dasharray=\"4 3\"" if v == 0.05 else ""}/>')
        o.append(f'<text x="{X(v):.1f}" y="{H-0}" text-anchor="middle" fill="#555">{v:g}</text>')
    for i, s_ in enumerate(rows):
        y = 56+i*rh; c = COL[s_['status']]
        o.append(f'<text x="8" y="{y+4}">{s_["variant"].split("_")[0]} {s_["route"]} {"S" if s_["id"].endswith("|S") else "A/C/K"}</text>')
        if s_['seed_spread_m']:
            a, b = s_['seed_spread_m']; o.append(f'<rect x="{X(a):.1f}" y="{y-4}" width="{max(2, X(b)-X(a)):.1f}" height="8" fill="{c}" opacity="0.28"/>')
        o.append(f'<circle cx="{X(s_["least_m"]):.1f}" cy="{y}" r="4.5" fill="{c}"/><text x="{x0-6}" y="{y+4}" text-anchor="end" fill="{c}">{s_["least_m"]:+.3f}</text>')
    o.append('</svg>'); (FIG_DIR/'SIM027_WORST_CASE.svg').write_text('\n'.join(o)+'\n')
    # 2. hoist options: trunk section with handrails, the ladder, and the suited casualty capsule on each line option
    import math as m
    hs = [s_ for s_ in segs if s_['route'] == 'hoist' and s_['id'].endswith('|S')]
    tr = 0.80; sc = 150; cx, cy = 200, 200
    P = lambda r, deg: (cx+r*sc*m.cos(m.radians(deg)), cy-r*sc*m.sin(m.radians(deg)))
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="420" font-family="sans-serif" font-size="11"><rect width="100%" height="100%" fill="#fff"/>',
         '<text x="10" y="18" font-size="13" font-weight="bold">Trunk section (X-axis toward the viewer): handrails, ladder and the hoist line options</text>']
    for k, (ws, ang) in enumerate((('V0_1.06_aft0.16', None), ('V0_rail150', None), ('V0_rail165', None))):
        cxk = 120+k*280; o.append(f'<circle cx="{cxk}" cy="190" r="{tr*sc*0.9:.1f}" fill="none" stroke="#333"/>')
        rails = {'V0_1.06_aft0.16': [135, 255], 'V0_rail150': [150, 255], 'V0_rail165': [165, 255]}[ws]
        Q = lambda r, deg, cxk=cxk: (cxk+r*sc*0.9*m.cos(m.radians(deg)), 190-r*sc*0.9*m.sin(m.radians(deg)))
        for rd in rails:
            x, y = Q(0.73, rd); o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#1565c0"/>')
        for ld in (75, 315):
            x, y = Q(0.77, ld); o.append(f'<rect x="{x-5:.1f}" y="{y-5:.1f}" width="10" height="10" fill="#f9a825"/>')
        x, y = Q(0.60, 300); o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#6a1b9a"/><text x="{x+8:.1f}" y="{y+4:.1f}" fill="#6a1b9a">ladder 300</text>')
        # S capsule on the 120 deg line, e 0.25 m
        for e, col in ((0.25, '#c62828'),):
            x, y = Q(e, 120); o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{0.4285*sc*0.9:.1f}" fill="{col}" fill-opacity="0.12" stroke="{col}"/>')
        o.append(f'<text x="{cxk-100}" y="{190+tr*sc*0.9+22:.0f}">workspace {ws}: handrail 1 at {rails[0]} deg</text>')
        rr = [h for h in hs if h['variant'] == ws and 'line120' in h['id'] and 'e0.25' in h['id']]
        if rr:
            o.append(f'<text x="{cxk-100}" y="{190+tr*sc*0.9+38:.0f}" fill="{COL[rr[0]["status"]]}">S, line 120 deg, e 0.25 m: worst {rr[0]["least_m"]:+.3f} m</text>')
    o.append('<text x="10" y="410" fill="#555">blue: handrails (r 0.73), amber: light strips, violet: ladder, red circle: suited casualty S (0.857 m) on the 120 deg line at e = 0.25 m</text></svg>')
    (FIG_DIR/'SIM027_HOIST_SECTION.svg').write_text('\n'.join(o)+'\n')
    # 3. care point plan (deck frame, sector frame x up the page, z across): blocks, landing well, existing care furniture with its attendant strip
    dist = d.get('distributed_alternative')
    if dist:
        import habitat_interior as hi
        from spec import load
        s = load(ROOT)[0]; sc = 70; X0, Z0 = 20, 20; sections = []
        o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="400" font-family="sans-serif" font-size="10"><rect width="100%" height="100%" fill="#fff"/>',
             '<text x="10" y="14" font-size="13" font-weight="bold">Protected care point in each sector (deck frame, plan; x along the ring axis, z tangential)</text>']
        for k, fn in enumerate(s['habitat']['layout']['functions']):
            ox = 40+k*320; oy = 40
            tX = lambda x, ox=ox: ox+(x+1.75)*0  # placeholder
            Xs = lambda z, ox=ox: ox+(z+2.7)*sc*0.55
            Ys = lambda x, oy=oy: oy+(x+1.75)*sc*0.95
            o.append(f'<rect x="{Xs(-2.62):.1f}" y="{Ys(-1.75):.1f}" width="{5.24*sc*0.55:.1f}" height="{3.5*sc*0.95:.1f}" fill="none" stroke="#333"/>')
            for b in hi.zones(s, fn):
                o.append(f'<rect x="{Xs(b["min"][2]):.1f}" y="{Ys(b["min"][0]):.1f}" width="{(b["max"][2]-b["min"][2])*sc*0.55:.1f}" height="{(b["max"][0]-b["min"][0])*sc*0.95:.1f}" fill="#bbb" stroke="#888"/>')
                o.append(f'<text x="{Xs(b["min"][2])+2:.1f}" y="{Ys(b["min"][0])+10:.1f}" fill="#444">{b["name"][:14]}</text>')
            o.append(f'<rect x="{Xs(-2.07):.1f}" y="{Ys(-0.5):.1f}" width="{(2.07-0.45)*sc*0.55:.1f}" height="{1.0*sc*0.95:.1f}" fill="#42a5f5" fill-opacity="0.3" stroke="#1565c0"/>')
            ex = dist['functions'][fn]['deck']['existing']
            if ex:
                q = ex[0]
                for j, e in enumerate(q['env'][:3]):
                    o.append(f'<rect x="{Xs(e[2]):.1f}" y="{Ys(e[0]):.1f}" width="{(e[3]-e[2])*sc*0.55:.1f}" height="{(e[1]-e[0])*sc*0.95:.1f}" fill="{["#2e7d32", "#a5d6a7", "#c8e6c9"][j]}" fill-opacity="0.65" stroke="#2e7d32"/>')
                o.append(f'<text x="{ox}" y="{oy+3.5*sc*0.95+16:.0f}">{fn[:12]}: {q["block"]} + strip {q["clearance_m"]:+.2f} m</text>')
            else:
                o.append(f'<text x="{ox}" y="{oy+3.5*sc*0.95+16:.0f}" fill="#c62828">{fn[:12]}: no berth/couch; new couch {dist["functions"][fn]["deck"]["new_couch"]["standing"]["clearance_m"]:+.2f} m</text>')
        o.append('<text x="10" y="390" fill="#555">grey: zone blocks; blue: hatch landing well and chase; green: care furniture, attendant strip (0.60 m) and airway end (0.60 m)</text></svg>')
        (FIG_DIR/'SIM027_CARE_POINT.svg').write_text('\n'.join(o)+'\n')
    print('figures written')


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    a = argparse.ArgumentParser(); a.add_argument('mode', choices=('build', 'buildwrap', 'legs', 'collect', 'survey', 'slotsurvey', 'hoistopts', 'pins', 'survey-run', 'distributed', 'sim027', 'figures')); a.add_argument('names', nargs='?', default='')
    a.add_argument('--root', type=Path); a.add_argument('--variant'); a.add_argument('--parts', default='geom,rings,slot,hoist')
    a.add_argument('--carriers', default='ACKS'); a.add_argument('--route'); a.add_argument('--carrier'); a.add_argument('--angle'); a.add_argument('--workers', type=int, default=18); a.add_argument('--only', default=''); a.add_argument('--routes', default=ROUTES); a.add_argument('--repeat-carriers', dest='repeat_carriers', default='KS')
    args = a.parse_args(argv)
    if args.mode == 'build':
        build([n for n in (args.names.split(',') if args.names else VARIANTS)])
    elif args.mode == 'buildwrap':
        buildwrap(args)
    elif args.mode == 'legs':
        run_legs(args)
    elif args.mode == 'distributed':
        distributed()
    elif args.mode == 'sim027':
        sim027()
    elif args.mode == 'figures':
        figures()
    elif args.mode in ('survey', 'slotsurvey', 'hoistopts', 'pins', 'survey-run'):
        {'survey': survey, 'slotsurvey': slotsurvey, 'hoistopts': hoistopts, 'pins': pins, 'survey-run': survey_run}[args.mode](args)
    else:
        collect()


if __name__ == '__main__':
    main()
