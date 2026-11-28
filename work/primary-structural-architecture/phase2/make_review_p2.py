"""Builds work/primary-structural-architecture/REVIEW_PSA_PHASE2.blend: the approved ship with PSA Phase II H and HC (hub path,
F1 configuration) and the ISSA CP4 envelopes in WORK_ collections, one collection per review view, a framed camera, packed.

    /snap/bin/blender -b assets/wayfarer/WF_WAYFARER_001.blend --python work/primary-structural-architecture/phase2/make_review_p2.py

Reads results/p2_review/*.json (post.py). Production GEN_ content is untouched (only hidden where a WORK view replaces it).
"""
import json
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = Path(bpy.path.abspath('//')).resolve() if bpy.data.filepath else Path.cwd()
ROOT = Path(__file__).resolve().parents[3]
WD = ROOT / 'work' / 'primary-structural-architecture'
RES = WD / 'results' / 'p2_review'
OUTF = WD / 'REVIEW_PSA_PHASE2.blend'
PINK = 'COLOR_06'

FAM_COL = {'rail': (0.85, 0.35, 0.2), 'trans': (0.85, 0.35, 0.2), 'ring': (0.6, 0.1, 0.1), 'pickup': (0.6, 0.1, 0.1), 'frame': (0.55, 0.55, 0.6),
           'modframe': (0.95, 0.75, 0.2), 'diag': (0.4, 0.6, 0.85), 'tie': (0.5, 0.5, 0.5), 'cone': (0.9, 0.2, 0.6), 'hubcone': (0.9, 0.2, 0.6),
           'spine': (0.2, 0.8, 0.5), 'hub': (0.2, 0.8, 0.5), 'collar': (0.6, 0.4, 0.9), 'keel': (0.85, 0.35, 0.2), 'deck': (0.95, 0.55, 0.1), 'iface': (0.3, 0.3, 0.3)}
MAT_COL = {'AL6061': (0.75, 0.78, 0.82), 'AL5083': (0.55, 0.62, 0.72), 'TI64': (0.55, 0.45, 0.85), 'ALAL2O3F': (0.95, 0.7, 0.25), 'CFPEEK': (0.12, 0.12, 0.14), 'IFACE': (0.3, 0.3, 0.3)}


def mat(name, rgb, alpha=1.0, emit=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*rgb, 1.0); b.inputs['Alpha'].default_value = alpha
    if emit:
        b.inputs['Emission Color'].default_value = (*rgb, 1.0); b.inputs['Emission Strength'].default_value = emit
    m.diffuse_color = (*rgb, alpha)
    if alpha < 1:
        m.blend_method = 'BLEND' if hasattr(m, 'blend_method') else None
    return m


def coll(name, parent, color=PINK, hide=False):
    c = bpy.data.collections.new(name); parent.children.link(c); c.color_tag = color
    if hide:
        lc = find_layer(bpy.context.view_layer.layer_collection, name); lc.hide_viewport = True; c.hide_render = True
    return c


def find_layer(lc, name):
    if lc.collection.name == name:
        return lc
    for ch in lc.children:
        r = find_layer(ch, name)
        if r:
            return r


def tubes(name, segs, c, m, sides=8):
    """One mesh object of many cylinders: segs = [(p0, p1, r)]."""
    bm = bmesh.new()
    for p0, p1, r in segs:
        p0, p1 = Vector(p0), Vector(p1); d = p1-p0; L = d.length
        if L < 1e-6:
            continue
        q = d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        M = Matrix.Translation((p0+p1)/2) @ q
        bmesh.ops.create_cone(bm, cap_ends=True, segments=sides, radius1=r, radius2=r, depth=L, matrix=M)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(m)
    o = bpy.data.objects.new(name, me); c.objects.link(o); o['wf_owner'] = 'work.psa_phase2'
    return o


def box(name, ctr, size, c, m):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(ctr) @ Matrix.Diagonal((*size, 1.0)))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(m)
    o = bpy.data.objects.new(name, me); c.objects.link(o); return o


def p(x, r, az):
    t = math.radians(az); return (x, r*math.cos(t), r*math.sin(t))


def bins(members, key, edges, cols, nodes, label, c, rmin=0.04, scale_r=1.0, disp=None, dscale=0.0):
    groups = {}
    for mbr in members:
        v = key(mbr)
        if v is None:
            continue
        k = sum(1 for e in edges if v > e)
        a = Vector(nodes[mbr['a']]); b = Vector(nodes[mbr['b']])
        if disp is not None:
            a = a+Vector(disp[mbr['a']])*dscale; b = b+Vector(disp[mbr['b']])*dscale
        groups.setdefault(k, []).append((a, b, max(rmin, mbr['r']*scale_r)))
    for k, segs in sorted(groups.items()):
        lo = edges[k-1] if k else None; hi = edges[k] if k < len(edges) else None
        nm = f'{label}_{"" if lo is None else f"{lo:g}"}..{"" if hi is None else f"{hi:g}"}'
        tubes(nm, segs, c, mat('P2_'+nm, cols[k]))


def ramp(n, a=(0.15, 0.35, 0.9), b=(0.9, 0.9, 0.9), c_=(0.9, 0.15, 0.1)):
    out = []
    for i in range(n):
        t = i/(n-1)
        if t < 0.5:
            u = t/0.5; out.append(tuple(a[j]+(b[j]-a[j])*u for j in range(3)))
        else:
            u = (t-0.5)/0.5; out.append(tuple(b[j]+(c_[j]-b[j])*u for j in range(3)))
    return out


def build_variant(d, root, hide):
    nodes = d['nodes']; mem = d['members']
    top = coll(f'WORK_PSA_P2_{d["concept"]}_{d["rotor"]}_{d["config"]}', root, hide=hide)
    views = {}
    def V(name, h=True):
        c = coll(f'WORK_{d["concept"]}_{name}', top, hide=h); views[name] = c; return c
    c = V('01_primary_secondary', h=False)
    bins(mem, lambda m: 1 if m['primary'] else 0, [0.5], [(0.55, 0.58, 0.62), (0.9, 0.4, 0.15)], nodes, f'{d["concept"]}_structure', c)
    c = V('02_materials')
    for mid, rgb in MAT_COL.items():
        segs = [(nodes[m['a']], nodes[m['b']], max(0.04, m['r'])) for m in mem if m['mat'] == mid]
        if segs:
            tubes(f'{d["concept"]}_mat_{mid}', segs, c, mat('P2_mat_'+mid, rgb))
    c = V('03_axial_force_MN')
    bins(mem, lambda m: m['N'], [-8, -4, -2, -0.5, 0.5, 2, 4], ramp(8, (0.9, 0.1, 0.1), (0.85, 0.85, 0.85), (0.1, 0.3, 0.95)), nodes, f'{d["concept"]}_N', c)
    c = V('04_bending_engine_out_MNm')
    bins(mem, lambda m: m['Meo'], [0.1, 0.5, 1, 2, 5], ramp(6, (0.2, 0.3, 0.5), (0.9, 0.9, 0.3), (0.9, 0.1, 0.1)), nodes, f'{d["concept"]}_M', c)
    c = V('05_torsion_engine_out_MNm')
    bins(mem, lambda m: m['T'], [0.01, 0.05, 0.2, 0.5, 1.0], ramp(6, (0.2, 0.3, 0.5), (0.9, 0.9, 0.3), (0.9, 0.1, 0.1)), nodes, f'{d["concept"]}_T', c)
    c = V('06_utilisation')
    bins(mem, lambda m: m['util'] if m['mat'] != 'IFACE' else None, [0.5, 0.75, 0.9, 1.0], ramp(5, (0.2, 0.6, 0.3), (0.95, 0.85, 0.2), (0.9, 0.1, 0.1)), nodes, f'{d["concept"]}_util', c)
    c = V('07_thermal_zones')
    zones = sorted(set(m['thermal'] for m in mem)); zc = [(0.9, 0.2, 0.1), (0.95, 0.6, 0.1), (0.6, 0.8, 0.3), (0.3, 0.6, 0.95)]
    for i, z in enumerate(zones):
        segs = [(nodes[m['a']], nodes[m['b']], max(0.04, m['r'])) for m in mem if m['thermal'] == z]
        tubes(f'{d["concept"]}_zone_{z.split()[0]}', segs, c, mat('P2_zone_'+z.split()[0], zc[i % 4]))
    c = V('08_mounting_zones')
    bins(mem, lambda m: 0, [], [(0.4, 0.4, 0.45)], nodes, f'{d["concept"]}_base', c, rmin=0.03, scale_r=0.5)
    pts = [(nodes[n], Vector(nodes[n])+Vector((0.01, 0, 0)), 0.45) for n in d['mounts']['rail_hardpoints']]
    tubes(f'{d["concept"]}_hardpoints_rail', pts, c, mat('P2_hp', (1.0, 0.85, 0.1)), sides=6)
    tubes(f'{d["concept"]}_hardpoints_deck', [(nodes[n], Vector(nodes[n])+Vector((0.01, 0, 0)), 0.8) for n in d['mounts']['deck']], c, mat('P2_hpdeck', (1.0, 0.5, 0.1)), sides=6)
    c = V('10_deformation_engine_out_x200')
    bins(mem, lambda m: 0, [], [(0.9, 0.3, 0.6)], nodes, f'{d["concept"]}_deformed', c, rmin=0.05, disp=d['u_engine_out'], dscale=200.0)
    c = V('11_failed_members')
    bins(mem, lambda m: 2 if m['lost'] else (1 if m['overloaded'] else 0), [0.5, 1.5], [(0.45, 0.45, 0.5), (0.95, 0.6, 0.1), (0.95, 0.05, 0.05)], nodes, f'{d["concept"]}_damage', c)
    c = V('12_module_decomposition')
    pal = [(0.85, 0.35, 0.2), (0.3, 0.6, 0.9), (0.95, 0.8, 0.3), (0.4, 0.8, 0.5), (0.7, 0.4, 0.9), (0.9, 0.5, 0.7)]
    byk = {}
    for m in mem:
        byk.setdefault(m['module'], []).append((nodes[m['a']], nodes[m['b']], max(0.04, m['r'])))
    for k, segs in sorted(byk.items()):
        tubes(f'{d["concept"]}_module_{k:03d}', segs, c, mat(f'P2_mod{k % 6}', pal[k % 6]))
    return top


def issa_envelopes(root):
    c = coll('WORK_PSA_P2_09_ISSA_envelopes_CP4', root)
    hot = mat('P2_issa_hot', (0.95, 0.25, 0.05), emit=0.5); nak = mat('P2_issa_nak', (0.9, 0.6, 0.1)); log = mat('P2_issa_log', (0.2, 0.8, 0.9))
    l2 = mat('P2_issa_l2', (0.6, 0.3, 0.8)); farm = mat('P2_issa_farm', (0.4, 0.6, 0.95), alpha=0.25); ecl = mat('P2_issa_eclss', (0.3, 0.9, 0.4))
    tubes('ISSA_H6a_hot_trunks_r6.52', [(p(-111.6, 6.52, a), p(41.0, 6.52, a), 0.35) for a in (90, 210, 330)], c, hot)
    tubes('ISSA_NaK_lanes_r5.8', [(p(-81.6, 5.8, a), p(40.4, 5.8, a), 0.1115) for a in (10, 50, 130, 170, 250, 290)], c, nak)
    tubes('ISSA_MRU_rail_az270_r3.6', [(p(-88.0, 3.6, 270), p(98.0, 3.6, 270), 0.08)], c, log)
    tubes('ISSA_MRU_carriage_envelope', [(p(-20.0, 3.6, 270), p(-16.0, 3.6, 270), 0.6)], c, mat('P2_issa_carr', (0.2, 0.8, 0.9), alpha=0.4))
    for i, a in enumerate((90, 210, 330)):
        box(f'ISSA_L2_unit_{i+1}_96.9t', p(-86.0, 3.0, a), (12.0, 2.6, 2.6), c, l2)
    box('ISSA_ECLSS_hub_unit', (100.3, 0.0, 3.2), (2.0, 2.2, 1.4), c, ecl)
    tubes('ISSA_ECLSS_ducts', [((99.2, 0, 1.3), (99.2, 0, 1.5), 0.14), ((101.4, 0, 1.3), (101.4, 0, 1.5), 0.14)], c, ecl)
    tubes('ISSA_bulkhead_X40.8', [((40.7, 0, 0), (40.9, 0, 0), 37.0)], c, mat('P2_issa_bulk', (0.95, 0.9, 0.6), alpha=0.25), sides=48)
    tubes('ISSA_TA_farm_envelope_F1', [((109.25, 0, 0), (156.06, 0, 0), 14.0)], c, farm, sides=32)
    tubes('ISSA_cryocoolers_X157', [((156.5, 0, 0), (157.5, 0, 0), 9.0)], c, mat('P2_issa_cryo', (0.6, 0.9, 1.0), alpha=0.5), sides=24)
    tubes('F1_Brow_envelope_X160-163', [((160.0, 0, 0), (163.0, 0, 0), 20.0)], c, mat('P2_brow', (0.5, 0.5, 0.55), alpha=0.35), sides=32)


def note(root):
    c = coll('WORK_PSA_P2_00_README', root)
    txt = ('PSA PHASE II REVIEW (STUDY / NONCANON)\nH and HC, hub path, F1 configuration (ISSA CP4 9faee26)\n'
           'Toggle the WORK_ view collections (01 shown). Production structure and radiators hidden, not deleted.\n'
           '03 axial: red compression, blue tension (MN, steady x DLF)\n04/05 engine-out bending/torsion  06 utilisation (red > 1)\n'
           '10 engine-out deformation x200  11 worst damage case: red lost, orange overloaded\nF1 tank farm and Brow lie forward of the production Brow')
    cu = bpy.data.curves.new('P2_readme', 'FONT'); cu.body = txt; cu.size = 4.0
    o = bpy.data.objects.new('P2_README', cu); c.objects.link(o); o.location = (-140.0, 0.0, 60.0); o.rotation_euler = (math.radians(90), 0, 0)
    o.data.materials.append(mat('P2_text', (1, 1, 1), emit=1.0))


def camera(root):
    c = coll('WORK_PSA_P2_cameras', root)
    cam = bpy.data.cameras.new('P2_CAM'); cam.lens = 35; cam.clip_end = 5000
    o = bpy.data.objects.new('P2_CAM_three_quarter', cam); c.objects.link(o)
    o.location = (120.0, -230.0, 130.0)
    d = Vector((10.0, 0.0, 0.0))-o.location; o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = o


def main():
    sc = bpy.context.scene
    root = coll('WORK_PSA_PHASE2', sc.collection)
    note(root)
    files = sorted(RES.glob('*.json'))
    for i, f in enumerate(files):
        d = json.loads(f.read_text())
        build_variant(d, root, hide=(d['concept'] != 'H'))
    issa_envelopes(root); camera(root)
    # the PSA truss replaces the production structure and sits inside the radiator blades: hide (never delete) both
    for c in bpy.data.collections:
        if any(c.name.startswith(k) for k in ('11_STRUCTURE', '13_THERMAL')):
            lc = find_layer(bpy.context.view_layer.layer_collection, c.name)
            if lc:
                lc.hide_viewport = True
            c.hide_render = True
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTF), compress=True)
    print('saved', OUTF)


main()
