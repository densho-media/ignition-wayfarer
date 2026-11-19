"""FPS V1.1 release readiness, item 3: engine N1's whole extraction path (study code, work/fuel-propellant).

blender -b assets/wayfarer/WF_WAYFARER_001.blend --python work/fuel-propellant/extraction.py -- out.json

vertex_cluster.removal_sweep checks only that every engine part forward of the cradle passes the cradle bore. This screen checks the whole
path in the saved vehicle: the engine and everything it carries (the VTX instance on N1's placement and the FPS_N1_* objects) moves aft
along its own axis by any distance d >= 0; every other evaluated vertex (cluster frame and lines, the other three engines, the FPS lines,
the hull, the thrust ring) is static. A static vertex at engine-frame station x, azimuth a and radius r is swept by every moving station
x' >= x, so its clearance is r - R(x, a), with R the largest moving radius at stations >= x in the same azimuth sector (+- one sector).
Static vertices that the removal procedure itself takes away are classed, not hidden: the N1 trunnion pins (withdrawn first) and the
cluster line stubs that end on N1's service panel (their removable spools come out first). Everything else is the extraction clearance.
"""
import bpy, json, math, sys
from pathlib import Path
from mathutils import Vector

ROOT = Path(bpy.data.filepath).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src/wayfarer'))
from spec import load                                        # noqa: E402
import vertex_cluster as vc                                  # noqa: E402
import vertex_engine as ve                                   # noqa: E402

s = load(ROOT)[0]
pl = next(p for p in vc.placements(s) if p['n'] == 1)
O = Vector(pl['origin']); X, Y, Z = (Vector(a) for a in pl['axes'])
g = ve.config(s)['geometry']; sp = ve.service_panel(s); est = ve.stations(s); cfg = vc.config(s)
x_cr = (est['collar_fwd']+est['collar_aft'])/2
SECT = 3.0                                                   # deg per azimuth sector
DX = 0.05                                                    # m per station bin
SKIP = ('Engineering_Envelope', 'Plume', 'plume', 'Marker', 'marker', 'Keepout', 'KEEPOUT', 'Envelope', 'FX', 'Glow', 'Removal')


def local(v):
    d = v-O; x = d.dot(X); y = d.dot(Y); z = d.dot(Z)
    return x, math.hypot(y, z), math.degrees(math.atan2(z, y)) % 360.0


dg = bpy.context.evaluated_depsgraph_get()
moving, static = [], []
for inst in dg.object_instances:
    ob = inst.object
    if ob.type not in ('MESH', 'CURVE') or any(k in ob.name for k in SKIP):
        continue
    try:
        me = ob.to_mesh()
    except Exception:                                         # noqa: BLE001
        continue
    if me is None or not len(me.vertices):
        ob.to_mesh_clear(); continue
    mw = inst.matrix_world.copy()
    is_vtx = ob.name.startswith('VTX_')
    on_n1 = (mw.translation-O).length < 0.5 if is_vtx else False
    mov = on_n1 or ob.name.startswith('FPS_N1_')
    ws = [mw @ v.co for v in me.vertices]
    pts = [local(v) for v in ws]
    if not (on_n1 or ob.name.startswith('FPS_N1_')):         # static faces: edge midpoints too (a chord sags inside its vertices)
        pts += [local((ws[e.vertices[0]]+ws[e.vertices[1]])/2) for e in me.edges]
    ob.to_mesh_clear()
    (moving if mov else static).append((ob.name if not is_vtx else f'{ob.name}@N{next((p["n"] for p in vc.placements(s) if (mw.translation-Vector(p["origin"])).length < 0.5), "?")}', pts))

# moving envelope: per azimuth sector, max radius per station bin, then the running max from the forward end aft
nsec = int(360/SECT)
bins = {}; who = {}
x_min, x_max = 1e9, -1e9
for mname, pts in moving:
    for x, r, a in pts:
        k = (int(math.floor(x/DX)), int(a/SECT) % nsec)
        if r > bins.get(k, -1.0):
            bins[k] = r; who[k] = mname
        x_min, x_max = min(x_min, x), max(x_max, x)
ix0, ix1 = int(math.floor(x_min/DX)), int(math.floor(x_max/DX))
R = {}; RW = {}
for sec in range(nsec):
    run = -1.0; rw = None
    for ix in range(ix1, ix0-1, -1):
        b = bins.get((ix, sec), -1.0)
        if b > run:
            run, rw = b, who.get((ix, sec))
        R[(ix, sec)] = run; RW[(ix, sec)] = rw


def env(x, a, owner=False):
    ix = int(math.floor(x/DX)); sec = int(a/SECT) % nsec
    if ix > ix1:
        return (-1.0, None) if owner else -1.0               # forward of the whole engine: never swept
    ix = max(ix, ix0)
    k = max(((ix, (sec+d) % nsec) for d in (-1, 0, 1)), key=lambda q: R[q])
    return (R[k], RW[k]) if owner else R[k]


# classes the procedure removes first
pin_az = [a % 360 for a in g['trunnion_azimuths_deg']]
def is_pin(x, r, a):
    return abs(x-x_cr) < 0.6 and any(min(abs(a-p), 360-abs(a-p)) < 6.0 for p in pin_az) and r < cfg['cradle_radius_m']+0.2
def is_panel_stub(name, x, r, a):
    if name == 'FPS_H2_Branch_N1':                           # the H2 branch's inlet stub (its spool comes out with the panel spools)
        return True
    return name.startswith('CL_') and min(abs(a-sp['azimuth']), 360-abs(a-sp['azimuth'])) < 14.0 and r < sp['r_out']+1.2 and sp['x_aft']-0.3 < x < sp['x_fwd']+1.6

worst = {}; classed = {'pins': [1e9, 0], 'panel_stubs': [1e9, 0]}
for name, pts in static:
    for x, r, a in pts:
        e = env(x, a)
        if e < 0:
            continue
        c = r-e
        if c > 2.0:
            continue
        if is_pin(x, r, a):
            classed['pins'][0] = min(classed['pins'][0], c); classed['pins'][1] += c < 0.2
            continue
        if is_panel_stub(name, x, r, a):
            classed['panel_stubs'][0] = min(classed['panel_stubs'][0], c); classed['panel_stubs'][1] += c < 0.2
            continue
        w = worst.get(name)
        if w is None or c < w[0]:
            worst[name] = (c, round(x, 2), round(r, 2), round(a, 1), env(x, a, True)[1])
rows = sorted(({'name': k, 'clearance_m': round(v[0], 3), 'x': v[1], 'r': v[2], 'az': v[3], 'against': v[4]} for k, v in worst.items()), key=lambda r: r['clearance_m'])
# the stubs: how far each must be withdrawn (the longest stretch of stub path inside the swept envelope plus the clearance)
stub = {}
for name, pts in static:
    if not (name == 'FPS_H2_Branch_N1' or name.startswith('CL_')):
        continue
    for x, r, a in pts:
        e = env(x, a)
        if e >= 0 and is_panel_stub(name, x, r, a) and r-e < 0.2:
            q = stub.setdefault(name, dict(x=[1e9, -1e9], r=[1e9, -1e9], worst=1e9))
            q['x'] = [min(q['x'][0], x), max(q['x'][1], x)]; q['r'] = [min(q['r'][0], r), max(q['r'][1], r)]; q['worst'] = min(q['worst'], r-e)
res = dict(engine=1, sector_deg=SECT, station_bin_m=DX, moving=[n for n, _ in moving], moving_x_range=[x_min, x_max],
           static_objects=len(static), min_clearance_m=rows[0]['clearance_m'] if rows else None, under_0_2=[r for r in rows if r['clearance_m'] < 0.2],
           worst=rows[:20], removed_first={k: dict(min_clearance_m=round(v[0], 3), vertices_under_0_2=v[1]) for k, v in classed.items()},
           stubs_inside={k: dict(x=[round(a, 2) for a in v['x']], r=[round(a, 2) for a in v['r']], worst_m=round(v['worst'], 3)) for k, v in stub.items()})
args = [a for a in sys.argv[sys.argv.index('--')+1:] if not a.startswith('--')] if '--' in sys.argv else []
if args:
    json.dump(res, open(args[0], 'w'), indent=1)
print('EXTRACTION', json.dumps({k: res[k] for k in ('static_objects', 'min_clearance_m', 'removed_first', 'stubs_inside')}), json.dumps(rows[:8]))
