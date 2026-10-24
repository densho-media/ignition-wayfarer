"""M7 production layer recipe: the production_detail elements of one assembly as a few joined meshes in the asset that hosts it.

One object per (assembly, family), named production_detail.object_name, tagged kind = production_detail, layer = PRODUCTION,
representation = REP_HERO, with its assembly, maturity and surface class; materials are [production.materials] (WF_MAT_Prod_<key>), so
the saved asset and the runtime carry the same finish. A family with a bevel width gets a chamfer (Bevel modifier, angle-limited), which
the export evaluates. Built only when production_detail.enabled(s, assembly); otherwise nothing, so the engineering assets stay as they were.
"""
from collections import OrderedDict
import bpy
from common import material, tag
import production_detail as pd

GEOMETRY_BASIS = ('PROTOTYPE [production] (M7 L4 visual layer): depiction, panel mounting and service access only; no load, pressure, '
                  'interface, volume or clearance change')


def prod_material(s, key):
    r, g, b, rough, metal = pd.material_value(s, key)
    m = material(f'Prod_{key}', (r, g, b))
    node = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    node.inputs['Roughness'].default_value = rough
    node.inputs['Metallic'].default_value = metal
    return m


def text_geometry(c, q):
    """World vertices and faces of a lettering element: a font curve converted to a mesh on the plane right x up, centred at centre."""
    from mathutils import Matrix, Vector
    right, up = Vector(q['right']).normalized(), Vector(q['up']).normalized(); normal = right.cross(up)
    m = Matrix.Translation(Vector(q['centre']))@Matrix((right, up, normal)).transposed().to_4x4()
    data = bpy.data.curves.new(q['name']+'_Text', 'FONT'); data.body = q['text']; data.align_x = 'CENTER'; data.align_y = 'CENTER'
    data.size = q['height']; data.extrude = .0008
    tmp = bpy.data.objects.new(data.name, data); c.objects.link(tmp)
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    if 'wrap_max_edge_m' in q:     # S9: on a tight cylinder, triangulate and split long edges first, so no chord sags into the surface below
        import bmesh
        bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.triangulate(bm, faces=bm.faces[:])
        for _ in range(12):
            long = [e for e in bm.edges if e.calc_length() > q['wrap_max_edge_m']]
            if not long:
                break
            bmesh.ops.subdivide_edges(bm, edges=long, cuts=1, use_grid_fill=False)
            bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.to_mesh(me); bm.free()
    vs = [tuple(m@v.co) for v in me.vertices]; fs = [tuple(poly.vertices) for poly in me.polygons]
    if 'wrap_r' in q:     # M8: lettering on a cylinder about +X (the rim girder): bend the plane onto radius wrap_r, arc length kept
        import math
        c0 = Vector(q['centre']); a0 = math.atan2(c0.z, c0.y); u0 = Vector((0.0, math.cos(a0), math.sin(a0))); t0 = Vector((0.0, -math.sin(a0), math.cos(a0)))
        bentv = []
        for v in vs:
            d = Vector(v)-c0; a = a0+d.dot(t0)/q['wrap_r']; rr = q['wrap_r']+d.dot(u0)
            bentv.append((v[0], rr*math.cos(a), rr*math.sin(a)))
        vs = bentv
    bpy.data.objects.remove(tmp, do_unlink=True); bpy.data.curves.remove(data); bpy.data.meshes.remove(me)
    return vs, fs


def build(c, s, assembly, parent=None):
    """Builds the assembly's families into collection c (parented to parent if given); returns the objects."""
    if not pd.enabled(s, assembly):
        return []
    made = []
    for (a, family), els in pd.families(pd.elements(s, assembly)).items():
        keys = list(OrderedDict.fromkeys(q['material'] for q in els))
        vs, fs, idx = [], [], []
        for q in els:
            qv, qf = text_geometry(c, q) if 'text' in q else (q['vs'], q['fs'])
            base = len(vs); vs += qv; fs += [tuple(base+i for i in f) for f in qf]; idx += [keys.index(q['material'])]*len(qf)
        name = pd.object_name(a, family)
        data = bpy.data.meshes.new(name+'_Mesh'); data.from_pydata(vs, [], fs); data.update()
        for k in keys:
            data.materials.append(prod_material(s, k))
        for poly, i in zip(data.polygons, idx):
            poly.material_index = i
        obj = bpy.data.objects.new(name, data); c.objects.link(obj)
        sc = pd.scope(s, a)
        tag(obj, f'{a}.{family.upper()}', 'production_detail', source=sc['evidence_ref'])
        widths = {q['bevel'] for q in els}
        if max(widths) > 0:
            mod = obj.modifiers.new('Prod_Chamfer', 'BEVEL'); mod.width = max(widths); mod.segments = 1
            mod.limit_method = 'ANGLE'; mod.angle_limit = 0.6; mod.use_clamp_overlap = True
        obj['layer'] = 'PRODUCTION'; obj['representation'] = s['production']['representation']
        obj['m7_assembly'] = a; obj['maturity'] = sc['maturity']; obj['family'] = family
        if a.startswith('M8.'):       # M8 exterior: Godot draw range by family (fasteners and lettering only close)
            obj['production_scope'] = 'M8'
            obj['design_class'] = 'ARTISTIC'   # forward_shield.design_classes: presentation layer over the shield (HSFP, 98!A58)
            obj['detail_range_m'] = float(sc['fine_range_m'] if family in ('fasteners', 'markings') else sc['detail_range_m'])
        pack = pd.pack_of(s, a)
        if pack is not None:          # a detail pack's assembly (docs/MODULES.md): its pack and geometry-detail class travel with it
            obj['detail_pack'] = pack['name']; obj['detail_class'] = pack['pack']['detail_class']; obj['module'] = pack['pack']['module']
            if 'detail_range_m' in pack['pack']:     # exterior packs: the Godot draw range (production_layer.gd; default 28 m)
                obj['detail_range_m'] = float(pack['pack']['detail_range_m'])
            tiers = pack['pack'].get('detail_tiers')   # Phase 4 exterior packs: each family drawn to its scale tier's range
            if tiers:
                obj['detail_tier'] = tiers.get(family, tiers['default'])
                obj['detail_range_m'] = float(s['production']['exterior']['tier_range_m'][obj['detail_tier']])
        obj['surface_class'] = '/'.join(sorted({q['surface_class'] for q in els}))
        obj['function'] = '; '.join(OrderedDict.fromkeys(q['function'] for q in els))
        obj['elements'] = len(els); obj['geometry_basis'] = GEOMETRY_BASIS; obj['evidence_ref'] = sc['evidence_ref']
        if parent is not None:
            obj.parent = parent
        made.append(obj)
    return made
