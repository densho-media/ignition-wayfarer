"""ISSA spatial survey of the built vehicle (NONCANON diagnostic; reads assets/, saves nothing in assets/).

Voxel survey inside the service casing: every grid point inside the casing radius is classed as
    OCCUPIED  inside a closed solid of the built model, or within CLEAR of any surface (static fit + 'thermal/handling' skin)
    DRYSTORE  (D) inside a BODY-C3 dry-store module: reserved for cargo, contents unallocated, repurposable
    RESERVED  a function the survey protects even where the model shows air: the spine core and crew trunk bore, the three keel
              maintenance lanes (cage-to-skin corridors at 0/120/240 deg), and the skin standoff
    FREE      none of these
    USABLE    FREE and every point within ERODE metres also FREE: room for a machine plus a working gap, not a crack between parts
Method: one BVH over every evaluated instance of the vehicle (casing skin excluded from the solids so its interior is not 'inside');
inside-ness by the nearest surface's normal (exact for closed meshes, conservative for open ones: an open shell's near side counts as
occupied through CLEAR). It is a diagnostic of the proxy model: it overstates free space where systems have no geometry yet, which is
the point of the gap analysis. Writes work/ship-systems-architecture/results/survey.json and per-station section arrays.

    /snap/bin/blender -b assets/wayfarer/WF_WAYFARER_001.blend --python work/ship-systems-architecture/survey_blender.py
"""
import json
import math
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(bpy.data.filepath).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src' / 'wayfarer'))
import spec  # noqa: E402
import hull_geometry as hg  # noqa: E402
import layout  # noqa: E402

OUT = ROOT / 'work' / 'ship-systems-architecture' / 'results'
DX, DYZ = 1.0, 0.5
CLEAR = 0.30
ERODE = 1.0
LANES_DEG = (0.0, 120.0, 240.0)
LANE_HALF_M = 0.6          # half-width of a keel maintenance lane at its radius (PROTOTYPE survey reserve)
SKIN_STANDOFF = 0.25
DRY = 'Dry_Store_M'   # BODY-C3 dry-store modules: a reservation without contents since TANK-AXIAL, surveyed as class D


def instance_meshes():
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys, owner = [], [], []
    names = []
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type != 'MESH':
            continue
        lib = ob.original.library.filepath if ob.original.library else 'vehicle'
        sub = Path(lib).stem
        try:
            me = ob.to_mesh()
        except RuntimeError:
            continue
        if me is None or not me.polygons:
            ob.to_mesh_clear(); continue
        M = inst.matrix_world.copy()
        base = len(verts)
        verts.extend(M @ v.co for v in me.vertices)
        idx = len(names); names.append((ob.original.name, sub))
        for p in me.polygons:
            polys.append([base + i for i in p.vertices]); owner.append(idx)
        ob.to_mesh_clear()
    return verts, polys, owner, names


def is_skin(name, sub):
    n = name.lower()
    return sub in ('WF_HULL',) and ('casing' in n or 'hull' in n or 'skin' in n) and 'panel' not in n


def main():
    t0 = time.time()
    s = spec.load()[0]
    verts, polys, owner, names = instance_meshes()
    keep = [i for i, o in enumerate(owner) if not is_skin(*names[o])]
    vk = verts
    bvh = BVHTree.FromPolygons(vk, [polys[i] for i in keep], all_triangles=False, epsilon=0.0)
    kowner = [owner[i] for i in keep]
    print(f'{len(names)} mesh instances, {len(polys)} faces, solids BVH {len(keep)} faces, {time.time()-t0:.1f}s')
    core = s['prototype']['spine_core_radius_m'] + 0.25
    x0, x1 = layout.origin(s, 'AFT') + 8.0, layout.origin(s, 'FWD') - 3.0
    nx = int((x1 - x0) / DX)
    sections = []
    tally = {}
    by_owner = {}
    for ix in range(nx + 1):
        x = x0 + ix * DX
        R = hg.radius_at(s, x) - s['hull']['shell_thickness_m']
        n = int(R / DYZ) + 1
        grid = []
        for iy in range(-n, n + 1):
            row = []
            for iz in range(-n, n + 1):
                y, z = iy * DYZ, iz * DYZ
                r = math.hypot(y, z)
                if r > R:
                    row.append(' '); continue
                p = Vector((x, y, z))
                hit = bvh.find_nearest(p, CLEAR)
                cls = 'F'
                if hit[0] is not None:
                    o = names[kowner[hit[2]]]
                    cls = 'D' if o[0].startswith(DRY) else 'O'
                    by_owner[o[1]] = by_owner.get(o[1], 0) + 1
                else:
                    far = bvh.find_nearest(p, 30.0)
                    if far[0] is not None and (p - far[0]).dot(far[1]) < 0.0:
                        o = names[kowner[far[2]]]
                        cls = 'D' if o[0].startswith(DRY) else 'O'
                        by_owner[o[1]] = by_owner.get(o[1], 0) + 1
                if cls == 'F':
                    th = math.degrees(math.atan2(z, y)) % 360.0
                    lane = any(abs(((th - a + 180) % 360) - 180) * math.pi / 180 * r < LANE_HALF_M and r > core for a in LANES_DEG)
                    if r < core or r > R - SKIN_STANDOFF or lane:
                        cls = 'R'
                row.append(cls)
            grid.append(row)
        # erosion for USABLE
        k = int(round(ERODE / DYZ))
        N = len(grid)
        usable = 0
        src = [row[:] for row in grid]
        for a in range(N):
            for b in range(N):
                if src[a][b] != 'F':
                    continue
                ok = all(0 <= a + da < N and 0 <= b + db < N and src[a + da][b + db] == 'F'
                         for da in range(-k, k + 1) for db in range(-k, k + 1))
                if ok:
                    grid[a][b] = 'U'; usable += 1
        cnt = {c: sum(row.count(c) for row in grid) for c in 'OFRUD'}
        cnt['U'] = usable
        sections.append(dict(x=round(x, 2), R=round(R, 3), counts=cnt, grid=[''.join(r) for r in grid]))
    cell = DX * DYZ * DYZ
    res = dict(method=__doc__.split('\n\n')[0], dx=DX, dyz=DYZ, clear_m=CLEAR, erode_m=ERODE, lane_half_m=LANE_HALF_M,
               skin_standoff_m=SKIN_STANDOFF, cell_m3=cell, x_range=[x0, x1], occupied_by_subsystem_cells=by_owner,
               origins=layout.origins(s), sections=sections, seconds=time.time() - t0)
    OUT.mkdir(exist_ok=True)
    (OUT / 'survey.json').write_text(json.dumps(res))
    print(f'done {time.time()-t0:.0f}s, {len(sections)} sections')


main()
