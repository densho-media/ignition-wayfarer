"""M8.1 geometry readback on the saved assets (Blender): what the [production.m8] layer built, read back from the files, never fed into the spec.

- Tags: every M8 object is a production_detail of an M8 assembly with layer PRODUCTION, the [production.m8] maturity, a unique component ID,
  its evidence reference and a draw range; M7 objects keep the M7 maturity.
- Clashes: no M8 mesh overlaps (BVH triangle overlap) any engineering mesh of the forward assets (WF_FORWARD_SHIELD and WF_EYE), M8 meshes
  included against each other's assemblies only. The M8 meshes live in the detail assets linked into WF_FORWARD_SHIELD at its origin (pack
  m8_forward, docs/MODULES.md), so they are read in the same ship frame.
- Silhouette: largest radius of the forward assets with and without the M8 objects (the 90 m Brow), and the forward-most M8 vertex against
  the skin's aft face at its radius (nothing on the sunward side).
- Cost: objects, triangles and unique mesh data of the M8 layer.

    /snap/bin/blender -b --python src/wayfarer/validation/m8_readback.py -- [--out report.json]
"""
from pathlib import Path
import argparse
import json
import math
import sys
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer')]
from spec import load
import forward_shield as fsh
import modules

ASSETS = ('subsystems/WF_FORWARD_SHIELD.blend', 'subsystems/WF_EYE.blend')


def assets():
    """The forward assets plus every detail asset linked into them (at the host origin, so in the same frame)."""
    hosts = {Path(a).stem for a in ASSETS}
    return [*ASSETS, *(f'{modules.ASSET_DIR}/{d}.blend' for d, h in sorted(modules.detail_hosts(ROOT).items()) if h in hosts)]


def world_tris(o):
    me = o.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh(); me.calc_loop_triangles()
    vs = [o.matrix_world @ v.co for v in me.vertices]; tris = [tuple(t.vertices) for t in me.loop_triangles]
    o.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()
    return vs, tris


def main(out):
    s = load(ROOT)[0]; m8 = s['production']['m8']; st = fsh.stations(s)
    objs = []
    for rel in assets():
        with bpy.data.libraries.load(str(ROOT/'assets/wayfarer'/rel), link=False) as (src, dst):
            dst.objects = list(src.objects)
        for o in dst.objects:
            if o is not None and o.type == 'MESH':
                bpy.context.scene.collection.objects.link(o); objs.append((rel, o))
    prod = [o for _, o in objs if o.get('kind') == 'production_detail']
    mine = [o for o in prod if str(o.get('m7_assembly', '')).startswith('M8.')]
    eng = [o for _, o in objs if o.get('kind') != 'production_detail']
    fails = []
    ids = [o.get('component_id') for o in mine]
    if len(set(ids)) != len(ids):
        fails.append('duplicate component_id')
    for o in mine:
        for k, want in (('layer', 'PRODUCTION'), ('maturity', m8['maturity']), ('evidence_ref', m8['evidence_ref']), ('production_scope', 'M8')):
            if o.get(k) != want:
                fails.append(f'{o.name}: {k} {o.get(k)!r} != {want!r}')
        if 'detail_range_m' not in o or not o.get('component_id', '').startswith('M8.'):
            fails.append(f'{o.name}: draw range or component ID missing')
    for o in prod:
        if o not in mine and o.get('maturity') != s['production']['maturity']:
            fails.append(f'{o.name}: M7 maturity changed')
    trees = {}
    for o in mine+eng:
        vs, tris = world_tris(o)
        trees[o.name] = (BVHTree.FromPolygons(vs, tris, epsilon=0.0), vs)
    clashes = []
    box = lambda vs: (Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs))), Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs))))
    boxes = {n: box(vs) for n, (_, vs) in trees.items() if vs}
    for a in mine:
        la, ha = boxes[a.name]
        for b in eng+[o for o in mine if o.get('m7_assembly') != a.get('m7_assembly')]:
            if b.name not in boxes or b is a:
                continue
            lb, hb = boxes[b.name]
            if any(la[i] > hb[i] or lb[i] > ha[i] for i in range(3)):
                continue
            hits = trees[a.name][0].overlap(trees[b.name][0])
            if hits:
                clashes.append(dict(production=a.name, engineering=b.name, triangle_pairs=len(hits)))
    rad = lambda group: max(math.hypot(v.y, v.z) for o in group for v in trees[o.name][1])
    fwd = max(((v.x-fsh.skin_aft_at(s, min(math.hypot(v.y, v.z), st['shield_r'])), o.name) for o in mine for v in trees[o.name][1]
               if math.hypot(v.y, v.z) < st['shield_r']-1e-6), default=(None, None))
    tri = sum(len(world_tris(o)[1]) for o in mine)
    report = dict(maturity=m8['maturity'], crown_sectors=list(m8['crown_sectors']), objects=len(mine), triangles=tri,
                  unique_meshes=len({o.data.name for o in mine}), families={o.name: o.get('elements') for o in mine},
                  max_radius_m=dict(engineering=round(rad(eng), 4), with_m8=round(max(rad(eng), rad(mine)), 4), m8=round(rad(mine), 4)),
                  forwardmost_vs_skin_aft_face_m=None if fwd[0] is None else dict(offset=round(fwd[0], 4), object=fwd[1]),
                  clashes=clashes, failures=fails, engineering_meshes_checked=len(eng))
    report['verdict'] = 'PASS' if not clashes and not fails and (fwd[0] is None or fwd[0] < 0) and report['max_radius_m']['with_m8'] <= st['shield_r']+.005 else 'FAIL'
    print('WF_M8_READBACK', json.dumps(report), flush=True)
    if out:
        Path(out).write_text(json.dumps(report, indent=1))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--out')
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    main(a.out)
