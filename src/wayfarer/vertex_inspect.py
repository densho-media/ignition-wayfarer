"""Vertex Engine 1.1 part inspection (owner brief 2026-11-14). Pure, standard library only.

The built engine draws its logical parts merged into a few render objects (vertex_engine.families), so the play package stays inside
its download budget. This module keeps every logical part inspectable without exporting more nodes. It derives three things from the
same engine definition the generator draws:

  records(s)     one record per logical part: stable id, display name, category, material, evidence, purpose, note, mass estimate,
                 bounds, render object, interfaces, related parts and the research records (Weakest Links, Breakthrough Lab).
  geometry(s)    the parts' own meshes in one small raw buffer (engine frame, runtime axes, 1 mm int16 steps): the viewer loads it
                 only when someone inspects an engine, picks against it and draws the highlight from it. The play package never reads it.
  manifest(s)    the records, the categories with their anatomy text and colours, and the four engine instances; returns the buffer too.

Picking runs against the source part geometry, not the Draco-compressed render mesh, so a pick can sit about 1.5 cm off what is
drawn. A pick never claims more than the part whose surface the ray meets first.

`python3 src/wayfarer/vertex_inspect.py` prints a summary (parts, bytes, categories).
"""
import json
import math
import struct

import functional_colors
import vertex_cluster as vc
import vertex_engine as ve

CONTRACT = 'WF_VTX_INSPECT'
VERSION = 1
QUANTUM = 0.001                      # part glb position step, metres
TAGS = ('C1', 'C2', 'L1', 'L2', 'L3', 'L4')


def runtime(v):
    """Blender (x, y, z) -> runtime (x, z, -y), as the exported GLB."""
    return (v[0], v[2], -v[1])


def display_name(name):
    """'VTX_L2_Segment_03' -> 'L2 segment 03'; 'VTX_Shield_Tie_Rod_4' -> 'Shield tie rod 4'; 'VTX_C1_LiH_Nose' -> 'C1 LiH nose'."""
    words = name.removeprefix('VTX_').split('_')
    out = [w if (w in TAGS or w.isdigit() or w.isupper() and len(w) <= 4 or any(c.isupper() for c in w[1:])) else w.lower() for w in words]
    text = ' '.join(out)
    return text[0].upper()+text[1:]


def part_mass(s, p):
    mt = ve.config(s)['materials']
    key = p['material'] if p['material'] in mt['density_kg_m3'] else 'sensor'
    return ve._volume(p)*mt['density_kg_m3'][key]*mt['solid_fraction'][key]


def stem(name):
    head, _, tail = name.rpartition('_')
    return head if tail.isdigit() and head else name


def tag_of(name):
    return next((w for w in name.split('_') if w in TAGS), None)


def records(s):
    """One record per logical part of the compact engine, in vertex_engine.parts order."""
    parts = ve.parts(s)
    family_of = {p['name']: fam for fam, ps in ve.families(parts) for p in ps}
    by_stem, by_tag = {}, {}
    by_cat = {p['name']: p['category'] for p in parts}
    for p in parts:
        by_stem.setdefault(stem(p['name']), []).append(p['name'])
        t = tag_of(p['name'])
        if t:
            by_tag.setdefault(t, []).append(p['name'])
    out = []
    for i, p in enumerate(parts):
        vs = ve.mesh_of(p)[0]
        lo = [min(v[c] for v in vs) for c in range(3)]; hi = [max(v[c] for v in vs) for c in range(3)]
        units = by_stem[stem(p['name'])]
        if tag_of(p['name']):
            related = [n for n in by_tag[tag_of(p['name'])] if stem(n) != stem(p['name'])]
        else:
            related = [ns[0] for st_, ns in by_stem.items() if st_ != stem(p['name']) and by_cat[ns[0]] == p['category']]
        related = list(dict.fromkeys(stem(n) if len(by_stem[stem(n)]) > 1 else n for n in related))[:10]
        out.append(dict(
            index=i, id=f'WF.VTX.CE.{p["name"]}', name=p['name'], label=display_name(p['name']), category=p['category'],
            material=p['material'], evidence=p['evidence'], note=p['note'], mass_kg=round(part_mass(s, p), 1),
            render_object=family_of[p['name']], units=len(units), stem=stem(p['name']),
            bounds=[[round(lo[0], 3), round(lo[2], 3), round(-hi[1], 3)], [round(hi[0], 3), round(hi[2], 3), round(-lo[1], 3)]], related=related))
    return out


def categories(s):
    """The functional categories with their anatomy text, functional colour (review only) and part counts."""
    e = ve.config(s); counts = {}
    for p in ve.parts(s):
        counts[p['category']] = counts.get(p['category'], 0)+1
    out = []
    for cat, (_coll, fkey) in ve.CATEGORIES.items():
        if cat not in counts:
            continue
        a = e['anatomy'][cat]
        out.append(dict(id=cat, title=a['title'], color=list(functional_colors.PALETTE[fkey][1][:3]), function_key=fkey, parts=counts[cat],
                        purpose=a['purpose'], how=a['how'], physics=a['physics'], speculative=a['speculative'], open=a['open'],
                        interfaces=a['interfaces'], weakest_links=a['weakest_links'], breakthroughs=a['breakthroughs']))
    return out


def engines(s):
    """The four engine instances: name, stable instance id and the engine-frame -> ship placement in runtime axes (column-major 4x4)."""
    out = []
    for pl in vc.placements(s):
        m = vc.matrix(pl)                                   # Blender ship frame, rows
        C = [[1, 0, 0], [0, 0, 1], [0, -1, 0]]              # Blender -> runtime
        Ci = [[1, 0, 0], [0, 0, -1], [0, 1, 0]]
        R3 = [[sum(C[i][k]*m[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
        R3 = [[sum(R3[i][k]*Ci[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
        tr = runtime((m[0][3], m[1][3], m[2][3]))
        cols = [R3[0][0], R3[1][0], R3[2][0], 0, R3[0][1], R3[1][1], R3[2][1], 0, R3[0][2], R3[1][2], R3[2][2], 0, tr[0], tr[1], tr[2], 1]
        out.append(dict(name=pl['name'].removeprefix('ENGINE_'), ident=pl['ident'], matrix=[round(v, 6) for v in cols]))
    return out


def geometry(s):
    """The parts' own meshes as one raw little-endian buffer, and each part's [first vertex, vertices, first index, indices]: all
    positions first (int16 x, y, z in QUANTUM steps: engine frame, runtime axes; the engine lies within +-32.7 m), then every part's
    triangle indices (uint16, local to the part). No normals or materials: the viewer picks with these meshes and draws the highlight."""
    pos, idx, ranges = [], [], {}
    for p in ve.parts(s):
        vs, fs = ve.mesh_of(p)[:2]
        assert len(vs) < 65536, p['name']
        tris = [(f[0], f[j], f[j+1]) for f in fs for j in range(1, len(f)-1)]
        ranges[p['name']] = [len(pos)//3, len(vs), len(idx), 3*len(tris)]
        for v in vs:
            pos += [round(c/QUANTUM) for c in runtime(v)]
        idx += [i for tri in tris for i in tri]
    assert all(-32768 <= c <= 32767 for c in pos)
    return struct.pack(f'<{len(pos)}h', *pos)+struct.pack(f'<{len(idx)}H', *idx), ranges, len(pos)//3


def manifest(s):
    """(manifest, geometry bytes): the manifest's part records carry their geo ranges into the geometry buffer."""
    e = ve.config(s)
    data, ranges, nverts = geometry(s)
    parts_ = [dict(r, geo=ranges[r['name']]) for r in records(s)]
    return dict(contract=CONTRACT, version=VERSION, asset=e['id'], asset_version=e['version'], name=e['name'], status=e['status'],
                axes='runtime: metres, bow +X, dorsal +Y (Blender (x, y, z) -> (x, z, -y)); part geometry in the engine frame',
                picking='Rays meet the source part meshes (the geometry buffer), not the Draco render mesh: a pick can be about 1.5 cm off the drawn surface.',
                interfaces={i['name']: dict(at=[round(v, 3) for v in runtime(i['at'])], kind=i['kind'], note=i['note']) for i in ve.interfaces(s)},
                mass_basis='ENGINEERING_PROTOTYPE estimate per part: drawn volume x assumed density x solid fraction (vertex_engine.materials)',
                materials={k: dict(name=v, color=[round(c, 3) for c in ve.MATERIALS[k][0]]) for k, v in e['material_names'].items()},
                engines=engines(s), categories=categories(s), parts=parts_, speculative=e['speculative']['items'],
                geometry=dict(quantum_m=QUANTUM, vertices=nverts, layout='int16 positions (x, y, z) for every vertex, then uint16 indices; '
                              'part.geo = [first vertex, vertices, first index, indices]')), data


if __name__ == '__main__':
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load
    S = load(Path(__file__).resolve().parents[2])[0]
    m, b = manifest(S)
    print(f'{len(m["parts"])} parts, {len({p["render_object"] for p in m["parts"]})} render objects, {len(m["categories"])} categories, '
          f'{len(m["engines"])} engines; manifest {len(json.dumps(m, separators=(",", ":")))} B, part geometry {len(b)} B')
    for c in m['categories']:
        print(f'  {c["id"]:<17} {c["parts"]:>3}  {c["title"]}')
