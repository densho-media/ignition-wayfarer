"""Saved-geometry checks of the forward structure (FGR-006, FWD-001): conical shield and truss, sector keels and ties, the disruptor layer and its ports,
EYE wells, Dust Lance, displays and the Dustbreak Crown.

Everything is compared with forward_shield.py (the one definition) at the saved pose and, for the control states, in memory through the
linked FORWARD_DEFENSE_CTRL. The measured values (shield radius, Lance tip, envelope diameter) are reported, never fed back into the spec.
"""
from pathlib import Path
import math
import bpy
from mathutils import Vector
import forward_shield as fsh
import hull_geometry
import habitat_ring
import layout
from common import pose_forward_state

LIBRARY = fsh.SUBSYSTEM+'.blend'


def libraries():
    """The forward-shield library and the detail assets linked into it at its origin (docs/MODULES.md): read as one asset, in its frame."""
    import modules
    return {LIBRARY, *(f'{d}.blend' for d, h in modules.detail_hosts().items() if h == fsh.SUBSYSTEM)}
CUT_FLAT = math.cos(math.pi/64)      # common.cut cylinders are 64-gons: a cone well or port edge lies on its flats, r cos(pi/64)
SHIELD_KINDS = {'shield_skin', 'shield_hub', 'shield_rim', 'shield_truss', 'disruptor_layer', 'disruptor_post'}
SECTOR_KINDS = {'sector_keel', 'sector_frame', 'sector_tie'}
CROWN_KINDS = {'crown_housing', 'crown_shutter', 'crown_carriage', 'crown_emitter', 'crown_launcher'}
HARDWARE_KINDS = {'crown_carriage', 'crown_emitter', 'crown_launcher'}


def records():
    """World-space evaluated vertices of every visible object of the forward-shield library: name, kind, vertices, face count."""
    out = []; libs = libraries()
    for instance in bpy.context.evaluated_depsgraph_get().object_instances:
        obj = instance.object
        if obj.type not in {'MESH', 'CURVE'}:
            continue
        lib = obj.original.library
        if lib is None or Path(bpy.path.abspath(lib.filepath)).name not in libs:
            continue
        data = obj.to_mesh(); vs = [instance.matrix_world@v.co for v in data.vertices]; faces = len(data.polygons); obj.to_mesh_clear()
        if faces:      # collapsed displays (a bevel of 0) evaluate without faces and are not geometry
            out.append(dict(name=obj.original.name, kind=obj.get('kind'), vs=vs, faces=faces))
    return out


def world_matrices():
    """World matrix of every evaluated instance (empties included), keyed by the original object name."""
    return {i.object.original.name: i.matrix_world.copy() for i in bpy.context.evaluated_depsgraph_get().object_instances}


def kind_points(kind):
    """Evaluated world vertices of every visible mesh or curve of one kind, from any library."""
    out = []
    for instance in bpy.context.evaluated_depsgraph_get().object_instances:
        obj = instance.object
        if obj.type in {'MESH', 'CURVE'} and obj.get('kind') == kind:
            data = obj.to_mesh(); out += [instance.matrix_world@v.co for v in data.vertices]; obj.to_mesh_clear()
    return out


def named_points(name):
    """Evaluated world vertices of one object (by original name) from any library."""
    out = []
    for instance in bpy.context.evaluated_depsgraph_get().object_instances:
        obj = instance.object
        if obj.type in {'MESH', 'CURVE'} and obj.original.name == name:
            data = obj.to_mesh(); out += [instance.matrix_world@v.co for v in data.vertices]; obj.to_mesh_clear()
    assert out, f'{name} missing from the evaluated scene'
    return out


def radius(v):
    return math.hypot(v.y, v.z)


def distance_to_segment(point, a, b):
    ab = b-a; t = max(0.0, min(1.0, (point-a).dot(ab)/ab.dot(ab)))
    return (point-(a+ab*t)).length


def corridor_violations(s, vertices):
    """Vertices inside a docking-corridor cylinder (hull_geometry.dock_corridors)."""
    bad = []
    for c in hull_geometry.dock_corridors(s):
        u = Vector((0, math.cos(c['theta']), math.sin(c['theta'])))
        a = Vector((c['x'], 0, 0))+u*c['r0']; b = Vector((c['x'], 0, 0))+u*c['r1']
        bad += [c['name'] for v in vertices if distance_to_segment(v, a, b) < c['radius']]
    return sorted(set(bad))


def driven_value(obj, path, index, deps):
    ev = obj.evaluated_get(deps)
    if path == 'data.bevel_depth':
        return ev.data.bevel_depth
    if path in ('hide_viewport', 'hide_render'):
        return float(getattr(ev, path))
    if path == 'location':
        return ev.location[index]
    if path == 'scale':
        return ev.scale[index]
    if path == 'rotation_euler':
        return ev.rotation_euler[index]
    raise ValueError(path)


def mismatch(s, values):
    """Pose the linked control in memory; the largest difference between evaluated drivers and forward_shield.display()."""
    pose_forward_state(values); deps = bpy.context.evaluated_depsgraph_get()
    return max(abs(driven_value(bpy.data.objects[n], p, i, deps)-want) for (n, p, i), want in fsh.display(s, values).items())


def check_saved(s, ctx):
    """Preset-independent checks at the saved (neutral) pose. ctx: body_min_x, thermal, blade_cells, spinning, interfaces (library IF_ translations)."""
    st = fsh.stations(s); p = fsh.prototype(s); clr = s['prototype']['mechanical_clearance_m']; ob = bpy.data.objects
    rec = records(); kinds = {}
    for r in rec:
        kinds.setdefault(r['kind'], []).append(r)
    layers = fsh.disruptor_layers(s); keels = fsh.sector_keels(s); ties = fsh.sector_ties(s); posts = fsh.disruptor_posts(s); n_bays = len(fsh.crown(s)['bays'])
    expected = {'shield_skin': 1, 'shield_hub': 1, 'shield_rim': 1, 'eye_well': 4, 'dust_lance': 1, 'dust_lance_tip': 1, 'shield_spine_column': 1, 'shield_mount': 2*len(fsh.mount_struts(s)),     # bevelled curves evaluate as two instances each
                'sector_keel': 2*len(keels), 'sector_tie': 2*len(ties), 'sector_frame': 4, 'disruptor_layer': len(layers), 'disruptor_post': 2*len(posts),
                'crown_shutter': n_bays, 'crown_carriage': n_bays, 'crown_emitter': n_bays, 'crown_launcher': n_bays}
    for q in fsh.rear_construction(s):          # M4 slice 3: gussets, ribs and hatches as forward_shield.rear_construction defines them
        expected[q['kind']] = expected.get(q['kind'], 0)+1
        o = ob[q['name']]; assert all(max(abs(a-b) for a, b in zip(v.co, w)) <= 1e-5 for v, w in zip(o.data.vertices, q['vertices'])), q['name']
    for kind, n in expected.items():
        assert len(kinds.get(kind, [])) == n, f'{kind}: {len(kinds.get(kind, []))} evaluated objects, expected {n}'
    pts = lambda *ks: [v for k in ks for r in kinds.get(k, []) for v in r['vs']]
    # HSFP: every forward object kind carries its design class from forward_shield.design_classes (98!A58).
    classes = fsh.design_classes(s); libs = libraries()
    for o in ob:
        # A detail_instance only links a detail asset; the production objects inside it are checked here with the rest.
        if o.library is not None and Path(bpy.path.abspath(o.library.filepath)).name in libs and o.get('kind') not in (None, 'interface', 'detail_instance'):
            assert o.get('kind') in classes, f"{o.name}: kind {o.get('kind')} has no design class"
            assert o.get('design_class') == classes[o['kind']], f"{o.name}: design_class {o.get('design_class')} != {classes[o['kind']]}"
    # Shield: measured radius, conical profile, face and Lance tip against the stations. Every skin vertex lies on the face or its 0.10 m aft sheet.
    skin = pts('shield_skin', 'shield_rim')
    measured_r = max(radius(v) for v in skin); face_x = max(v.x for v in pts('shield_skin', 'shield_hub')); tip_x = max(v.x for v in pts('dust_lance_tip'))
    assert abs(measured_r-st['shield_r']) <= 1e-3, ('Measured shield radius', measured_r)
    assert abs(face_x-st['face']) <= 1e-3 and abs(tip_x-st['lance_tip']) <= 1e-3, (face_x, tip_x)
    skin_pts = pts('shield_skin')
    # Outer Eye layout: the well cuts leave vertices on the faceted sheets between profile rings (chord sag), held to a sag band instead.
    outer = [w for w in fsh.wells(s) if not fsh.in_hub(s, w)]
    at_well = lambda v, extra=0.0: any(math.hypot(v.y-w['y'], v.z-w['z']) <= w['radius']+extra+1e-3 for w in outer)
    sag = st['shield_r']*(1-math.cos(math.pi/96))*abs(fsh.face_x_at(s, st['shield_r'])-fsh.face_x_at(s, st['cone_r']))/max(st['shield_r']-st['cone_r'], 1e-9)+1e-4
    worst = max((min(abs(v.x-fsh.face_x_at(s, radius(v))), abs(v.x-fsh.skin_aft_at(s, radius(v)))) for v in skin_pts if not at_well(v)), default=0.0)
    assert worst <= 1e-4, ('Skin vertex off the conical profile', worst)       # float32 vertices at X ~ 112 m resolve ~8e-6 m
    cut_pts = [v for v in skin_pts if at_well(v)]
    assert all(fsh.skin_aft_at(s, radius(v))-sag <= v.x <= fsh.face_x_at(s, radius(v))+sag for v in cut_pts), 'A cone well cut leaves the skin band'
    for w in outer:
        assert not [v for v in skin_pts if math.hypot(v.y-w['y'], v.z-w['z']) < w['radius']*CUT_FLAT-1e-3], f"Cone well {w['index']} is not open in the skin"
    rim_face_x = max(v.x for v in skin_pts if radius(v) >= st['shield_r']-1e-4)
    measured_depth = face_x-rim_face_x
    assert abs(rim_face_x-st['rim_face']) <= 1e-3 and abs(measured_depth-s['forward_defense']['shield_profile']['crown_depth_m']) <= 1e-3, ('Measured crown depth', measured_depth)
    assert len([v for v in skin_pts if radius(v) < st['cone_r']-1e-4 and abs(v.x-st['face']) > 1e-4 and abs(v.x-st['skin_aft']) > 1e-4]) == 0, 'The hub stays flat'
    overall = tip_x-ctx['body_min_x']
    assert abs(overall-fsh.overall_length(s)) <= 2e-3 and overall <= s['ship']['length']['max'], ('Overall length', overall)
    shield_all = pts(*SHIELD_KINDS, *CROWN_KINDS, 'eye_well')
    assert max(radius(v) for v in shield_all) <= st['shield_r']+1e-3, 'Shield, truss, layer, Crown and wells stay inside r 45'
    # Radiators and rings sit inside the shield silhouette with their own limits.
    assert max(radius(v) for v in ctx['blade_cells']) <= s['radiators']['outer_radius']['value']+1e-3 <= st['shield_r'], 'Radiator cells leave r 37'
    assert max(radius(v) for v in ctx['thermal']) <= st['shield_r'], 'Radiator members leave the shield silhouette'
    assert max(radius(v) for v in ctx['spinning']) <= habitat_ring.outer(s)+1e-5 <= st['shield_r'], 'Rings leave their outer radius'
    # +X order: Lance tip >= field zone front > layer front > shield face > EYE facet faces > truss aft (rim girder) > ring B sweep front.
    facet_x = max(v.x for v in kind_points('eye_facet'))
    rim_x = min(v.x for v in pts('shield_rim'))
    layer_front = max(v.x for v in pts('disruptor_layer'))
    ring_b = max(v.x for v in ctx['spinning'])
    chain = [('Lance tip', tip_x), ('layer front', layer_front), ('shield face', face_x), ('EYE facet faces', facet_x), ('truss aft (rim girder)', rim_x), ('ring B sweep front', ring_b)]
    assert all(a[1] > b[1] for a, b in zip(chain, chain[1:])), f'+X order: {chain}'
    assert tip_x >= st['field'][1]-1e-3 and st['field'][0] >= face_x-1e-3 and st['field'][1] > layer_front, 'Field zone spans the Brow face to the Lance tip'
    local_face = max(w['x1'] for w in fsh.wells(s))          # the flat hub face, or the local cone face of an outer Eye layout
    assert abs((local_face-facet_x)-st['well_depth']) <= 1e-3, ('Well depth', local_face-facet_x)
    assert abs(rim_x-st['truss_aft']) <= 1e-3, ('Truss aft at the rim', rim_x)
    # Wells clear each other and the Lance; the Lance root meets the EYE shared mount.
    wells = [fsh.well_centres(s)]
    axes = []
    for r in sorted(kinds['eye_well'], key=lambda r: r['name']):
        ys = [v.y for v in r['vs']]; zs = [v.z for v in r['vs']]; axes.append(((max(ys)+min(ys))/2, (max(zs)+min(zs))/2))
        assert min(radius(v) for v in r['vs']) >= p['lance_base_radius_m']+clr, f"{r['name']} touches the Dust Lance"
    assert all(math.dist(a, b)-p['well_diameter_m'] >= clr for i, a in enumerate(axes) for b in axes[i+1:]), 'Wells overlap'
    assert all(math.dist(a, b) < 1e-3 for a, b in zip(axes, wells[0])), 'Wells sit on the EYE facet centres'
    # Load path (14!H15, 15!I30): the column starts on the forward end of the Momentum Spine, passes through the EYE mount bore without touching it,
    # bears on the hub, and four struts tie it to the truss hub ring. Nothing here runs through the EYE mount or relies on the 0.10 m skin alone.
    spine = named_points('Structural_Spine'); column = pts('shield_spine_column')
    mount = named_points('EYE_Shared_Mount') if not outer else None
    assert abs(max(v.x for v in spine)-min(v.x for v in column)) <= 1e-3 and abs(min(v.x for v in column)-st['spine_end']) <= 1e-3, 'The column must start on the spine end'
    assert abs(max(v.x for v in column)-st['face']) <= 1e-3 and max(radius(v) for v in column) <= p['lance_base_radius_m']+1e-3, 'The column bears on the hub and carries the Lance'
    assert (ctx['interfaces'][LIBRARY]['IF_SHIELD_SPINE_JOINT']-Vector((st['spine_end'], 0, 0))).length < 1e-5, 'Spine joint interface'
    for name in ('IF_SHIELD_FACE', 'IF_SHIELD_SPINE_JOINT', 'IF_DISRUPTOR_LAYER', *[f"IF_SHIELD_SECTOR_{k['index']}" for k in keels], *[f"IF_SHIELD_SECTOR_AFT_{k['index']}" for k in keels]):
        obj = next(o for o in bpy.data.objects if o.name == name and o.library is not None and Path(bpy.path.abspath(o.library.filepath)).name == LIBRARY)
        status = str(obj.get('engineering_status', ''))
        assert status.startswith('OPEN'), f'{name} must be flagged OPEN'
        if name in ('IF_SHIELD_FACE', 'IF_SHIELD_SPINE_JOINT'):
            assert all(ref in status for ref in fsh.ATTACHMENT_REFS.split(', ')), f'{name} must cite {fsh.ATTACHMENT_REFS}'
    if mount is not None:
        assert min(radius(v) for v in mount) >= fsh.eye_mount_bore(s)-1e-3 and min(radius(v) for v in mount) >= p['lance_base_radius_m']+clr-1e-3, 'The EYE mount bore must clear the column'
        assert min(v.x for v in mount) < st['spine_end']+1.0 and max(v.x for v in column) > max(v.x for v in mount) > min(v.x for v in column), 'The column passes through the EYE mount'
    else:          # outer Eye layout: no shared hub mount; each facet sits on its own frame plate directly behind it
        assert not [o for o in bpy.data.objects if o.name == 'EYE_Shared_Mount'], 'An outer Eye layout has no shared hub mount'
        plates = [r for r in kinds.get('eye_facet_frame', []) if r['name'].endswith('_Facet_Frame_Plate')]
        for w in outer:
            pv = [v for r in plates if r['name'] == f"Alt_Eye{w['index']}_Facet_Frame_Plate" for v in r['vs']]
            assert pv and max(math.hypot(v.y-w['y'], v.z-w['z']) for v in pv) <= p['well_diameter_m']/2+1e-3 and max(v.x for v in pv) <= w['x0']+1e-3, f"EYE facet {w['index']}: frame plate behind the facet"
    hub_ring = [v for r in kinds['shield_truss'] if r['name'] == 'Shield_Truss_Hub_Ring' for v in r['vs']]
    for strut in fsh.mount_struts(s):
        sv = [v for r in kinds['shield_mount'] if r['name'] == strut['name'] for v in r['vs']]
        assert sv and min(radius(v) for v in sv) <= p['lance_base_radius_m']+.05 and max(radius(v) for v in sv) >= st['hub_opening_r']-.05, f"{strut['name']} must join the column and the hub ring"
        assert all(st['truss_aft_hub'] <= v.x <= st['skin_aft'] for v in sv) and max(radius(v) for v in sv) <= max(radius(v) for v in hub_ring), f"{strut['name']} stays inside the truss"
    assert min(radius(v) for v in hub_ring) >= st['hub_opening_r']-1e-3, 'Hub ring inner radius'
    # Brow-side sector frame (Q1 on the Brow side only; aft ends free, draft Q45): three keels at the sourced radius and azimuths, nine ties into the truss; none enters a docking corridor or the ring sweep.
    for k in keels:
        kv = [v for r in kinds['sector_keel'] if r['name'] == k['name'] for v in r['vs']]
        cy = sum(v.y for v in kv)/len(kv); cz = sum(v.z for v in kv)/len(kv)
        assert abs(math.hypot(cy, cz)-k['r']) <= 1e-3 and abs(((math.atan2(cz, cy)-k['theta']+math.pi) % (2*math.pi))-math.pi) <= 1e-5, f"{k['name']}: sector radius and azimuth"
        assert abs(min(v.x for v in kv)-k['x0']) <= 1e-3 and abs(max(v.x for v in kv)-k['x1']) <= 1e-3, f"{k['name']}: X span"
    assert len({t['sector'] for t in ties}) == len(keels) and fsh.sector_truss_count(s) == s['forward_defense']['shield_load_path']['primary_sectors'], 'Brow-side tie set: a complete tie set for each primary sector keel'
    sector_pts = pts(*SECTOR_KINDS)
    assert ring_b+2*clr <= min(v.x for v in sector_pts), 'Sector keels start ahead of the ring B sweep'
    assert max(v.x for v in sector_pts) <= max(t['b'][0]+t['radius'] for t in ties)+1e-3 < st['skin_aft'], 'Keels and ties stay inside the hub truss depth'      # a bevelled end cap reaches one member radius past the node
    # Disruptor layer (FWD1): full radius, parallel to the face, ahead of it, with the EYE ports, the Lance hole and the Crown ports.
    for layer in layers:
        lv = [v for r in kinds['disruptor_layer'] if r['name'] == layer['name'] for v in r['vs']]
        assert abs(max(radius(v) for v in lv)-layer['outer_r']) <= 1e-3, ('Layer outer radius', max(radius(v) for v in lv))
        port_r = fsh.eye_port_outer_radius(s, layer)          # a hexagonal port's cut reaches its corners
        assert all(layer_x_ok(s, layer, v) for v in lv if not at_well(v, port_r-fsh.prototype(s)['well_diameter_m']/2)), f"{layer['name']}: a vertex is off the conical layer surface"
        assert min(v.x-fsh.face_x_at(s, radius(v)) for v in lv) >= layer['standoff']-1e-4-sag, 'Layer lies ahead of the face by its standoff'
        assert max(v.x for v in lv) < tip_x, 'Layer centre lies behind the Lance tip'
        for q in fsh.eye_ports(s, layer):
            hub_port = math.hypot(q['y'], q['z'])+q['radius'] < st['cone_r']
            assert min(math.hypot(v.y-q['y'], v.z-q['z']) for v in lv if radius(v) < st['cone_r']+1e-6 or not hub_port) >= q['radius']*(1.0 if hub_port else CUT_FLAT)-1e-3, f"EYE port {q['index']} is not open"
        flat = [v for v in lv if radius(v) < st['cone_r']-1e-3]
        assert min(radius(v) for v in flat) >= fsh.lance_hole_radius(s, layer)-1e-3, 'Lance hole'
        for w in fsh.crown_ports(s):
            inside = [v for v in lv if w['r0']+1e-3 < radius(v) < w['r1']-1e-3 and abs(((math.atan2(v.z, v.y)-w['azimuth']+math.pi) % (2*math.pi))-math.pi) < w['half_angle']-1e-5]
            assert not inside, f"Crown port {w['index']} is not open in {layer['name']}"
    pv = pts('disruptor_post')
    assert max(v.x for v in pv) <= max(fsh.layer_x(s, layer, 0.0)[0] for layer in layers)+1e-3 and min(v.x for v in pv) >= st['rim_face']-1e-3, 'Posts stand between the face and the layer'
    # Docking corridors and ring sweeps stay clear of the shield, the layer, the keels and the ties.
    shield_sector = shield_all+sector_pts
    assert not corridor_violations(s, shield_sector), f'Shield, layer, keel, tie or Crown inside a docking corridor: {corridor_violations(s, shield_sector)}'
    assert ring_b+clr <= min(v.x for v in shield_all), 'Shield geometry reaches the ring sweep'
    # Crown: stowed inside the housing depth; every Crown vertex inside r 45 here and in every state.
    crown_pts = pts(*CROWN_KINDS); cr = fsh.crown(s)
    assert all(cr['x0']-1e-3 <= v.x <= cr['x1']+1e-3 for v in crown_pts), 'Crown leaves the housing depth in the saved state'
    assert max(radius(v) for v in crown_pts) <= st['shield_r']+1e-3, 'Crown vertex beyond r 45'
    # Control: saved neutral, no action, drivers exactly as forward_shield.drivers() defines them.
    ctrl = ob[fsh.CONTROL]
    assert all(math.isclose(ctrl[k], v, abs_tol=1e-12) for k, v in fsh.neutral(s).items()) and ctrl.animation_data is None, 'Forward control must be saved neutral with no action'
    count = 0
    for name, path, index, expression in fsh.drivers(s):
        owner = ob[name].data if path.startswith('data.') else ob[name]; prop = path[5:] if path.startswith('data.') else path
        fc = next(f for f in owner.animation_data.drivers if f.data_path == prop and (index == -1 or f.array_index == index))
        assert fc.driver.expression == expression and fc.driver.is_valid and fc.driver.is_simple_expression, (name, path)
        assert all(v.targets[0].id == ctrl and v.targets[0].data_path == f'["{fsh.VARIABLES[v.name]}"]' for v in fc.driver.variables), (name, path)
        count += 1
    # Saved neutral: the field zone and the damage cells render nothing; the Crown is stowed with closed shutters.
    assert not kinds.get('field_display'), 'Field zone must be hidden at field_on = 0'
    assert len([o for o in ob if o.get('kind') == 'field_display']) == 1, 'One field zone object'
    assert not kinds.get('damage_cell') and len([o for o in ob if o.get('kind') == 'damage_cell']) == len(fsh.damage_cells(s)), 'Damage cells are state only: present in the file, hidden at neutral'
    mats = world_matrices()
    for b in cr['bays']:
        j = b['index']
        t = mats[f'Crown_Carriage_{j:02}'].translation
        assert abs(radius(t)-cr['stowed_r']) < 1e-5 and abs(t.x-cr['carriage_x']) < 1e-5 and abs(ob[f'Crown_Shutter_{j:02}'].location.z) < 1e-9 and abs(ob[f'Crown_Port_Cover_{j:02}'].location.z) < 1e-9, f'Crown bay {j} is not stowed and closed'
    for o in ob:
        if o.library is not None and str(o.get('kind', '')) in ('field_display', 'damage_cell'):
            assert o['canon_status'] in ('OPEN', 'WORKING') and o.get('geometry_status') == 'PROTOTYPE', o.name
    return {'measured_shield_radius_m': round(measured_r, 4), 'shield_face_x_m': round(face_x, 4), 'measured_crown_depth_m': round(measured_depth, 4), 'lance_tip_x_m': round(tip_x, 4),
            'overall_length_m': round(overall, 4), 'layer_front_x_m': round(layer_front, 4), 'x_order': {k: round(v, 3) for k, v in chain}, 'wells': 4, 'crown_bays': n_bays,
            'sector_keels': len(keels), 'sector_ties': len(ties), 'disruptor_layers': len(layers), 'disruptor_posts': len(posts), 'drivers': count, 'control_saved': 'NEUTRAL (all controls 0)'}


def layer_x_ok(s, layer, v):
    """A layer vertex lies on its aft or front sheet at its own radius (the flat hub counts as the cone's inner part)."""
    aft, front = fsh.layer_x(s, layer, radius(v))
    return min(abs(v.x-aft), abs(v.x-front)) <= 1e-4


def check_state(s, name, values, ray_vector=Vector((1, 0, 0))):
    """One control state posed in memory (a preset or a display pose): evaluated drivers against forward_shield.display(), the Crown inside r 45 and its
    depth unless engaged, only the open bays translated forward, the field zone shown exactly when the preset says, emitter rays clear and past the layer."""
    st = fsh.stations(s); clr = s['prototype']['mechanical_clearance_m']; ob = bpy.data.objects; cr = fsh.crown(s)
    worst = mismatch(s, values); assert worst < 1e-5, f'{name}: forward drivers off by {worst}'
    rows = fsh.crown_pose(s, values); engaged = any(r['open'] for r in rows)
    rec = records()
    shown = sorted(int(r['name'].rsplit('_', 2)[1])*100+int(r['name'].rsplit('_', 1)[1]) for r in rec if r['kind'] == 'damage_cell')
    want = sorted(c['ring']*100+c['sector'] for c in fsh.damage_cells(s) if c['index'] in fsh.damage_visible(s, values))
    assert shown == want, f'{name}: damage cells shown {len(shown)}, expected {len(want)}'
    # Field zone: shown exactly when the state's field is on (the presets follow forward_defense.field_states), between the Brow face and the Lance tip.
    zone = [v for r in rec if r['kind'] == 'field_display' for v in r['vs']]
    on = values['field_on'] > 0 and values['field_strength'] > 0
    assert bool(zone) == on, f'{name}: field zone shown = {bool(zone)}, field_on = {values["field_on"]}'
    if zone:
        z = fsh.field_zone(s); scale = min(1.0, max(0.0, values['field_strength']))
        assert min(v.x for v in zone) >= st['face']-1e-3 and max(v.x for v in zone) <= st['lance_tip']+1e-3, f'{name}: field zone leaves [face, Lance tip]'
        assert abs(max(radius(v) for v in zone)-z['max_r']*scale) <= 1e-3*max(scale, 1e-3)+1e-6 and z['aspect'] > 1.0, f'{name}: field zone radius'
    crown_pts = [v for r in rec if r['kind'] in CROWN_KINDS for v in r['vs']]
    mats = world_matrices(); deps = bpy.context.evaluated_depsgraph_get()
    for r in rows:
        t = mats[f"Crown_Carriage_{r['index']:02}"].translation
        assert abs(radius(t)-r['carriage_r']) < 1e-5, f"{name}: bay {r['index']} carriage radius (no radial travel)"
        assert abs(t.x-r['carriage_x']) < 1e-5, f"{name}: bay {r['index']} carriage X"
        assert abs(ob[f"Crown_Shutter_{r['index']:02}"].evaluated_get(deps).location.z-r['shutter_travel']) < 1e-5, f"{name}: bay {r['index']} shutter"
        assert abs(ob[f"Crown_Port_Cover_{r['index']:02}"].evaluated_get(deps).location.z-r['cover_travel']) < 1e-5, f"{name}: bay {r['index']} port cover"
        hr = ob[f"Crown_Head_{r['index']:02}"].evaluated_get(deps).rotation_euler
        assert abs(hr.z-r['head'][0]) < 1e-5 and abs(hr.y-r['head'][1]) < 1e-5 and abs(hr.x) < 1e-9, f"{name}: bay {r['index']} head gimbal"
    assert max(radius(v) for v in crown_pts) <= st['shield_r']+1e-3, f'{name}: a Crown vertex leaves r 45'
    # FD-E03 eyelids: each leaf at its driven travel; a fully closed pair blocks its facet's boresight, an open pair leaves it to eye_rays.
    for e in fsh.eye_shutters(s):
        k = values[f"eye_shutter_{e['index']}"]
        for leaf in e['leaves']:
            want = leaf['sign']*(e['open_t']-e['travel']*k)
            assert abs(ob[leaf['name']].evaluated_get(deps).location.z-want) < 1e-5, f"{name}: {leaf['name']} travel"
        if k >= 1.0:
            hit, *_ = bpy.context.scene.ray_cast(deps, Vector((e['window']['x']+.1, e['y'], e['z'])), Vector((1, 0, 0)), distance=10)
            assert hit, f"{name}: closed eyelid {e['index']} leaves the boresight open"
    if not engaged:
        assert all(cr['x0']-1e-3 <= v.x <= cr['x1']+1e-3 for v in crown_pts), f'{name}: concealed Crown leaves the housing'
    metric = None
    if engaged:
        assert len([r for r in rows if r['open']])+sum(r['faulted'] for r in rows) == s['forward_defense']['crown_inputs']['active_sectors'], f'{name}: open bays'
        hardware = [v for r in rec if r['kind'] in HARDWARE_KINDS for v in r['vs']]
        metric = 2*max(radius(v) for v in hardware)      # carriage bodies, emitters and launchers: the owner's engaged hardware radius (<= 45 m)
        assert abs(metric-fsh.envelope_diameter(s, values)) < 1e-3 and metric/2 <= s['forward_defense']['crown']['geometry']['engaged_radius_max_m']+1e-9, (name, metric)
        assert max(radius(v) for v in crown_pts) <= s['forward_defense']['crown']['geometry']['engaged_radius_max_m']+1e-3, f'{name}: Crown beyond r 45 m'
        # The engaged muzzles fire past the layer; each emitter's forward ray is clear (the layer has a port for it).
        layer_front = fsh.layer_front_at_port(s)
        for r in rows:
            if r['weight'] >= 1.0:        # fully engaged (a RECOVERING carriage is part way back behind the layer)
                mine = [v for q in rec if q['name'] == f"Crown_Emitter_{r['index']:02}" for v in q['vs']]
                centre = sum(mine, Vector())/len(mine)
                assert max(v.x for v in mine) >= layer_front+clr-1e-3, f"{name}: bay {r['index']} muzzle is not ahead of the layer"
                bore = (mats[f"Crown_Head_{r['index']:02}"].to_3x3() @ ray_vector).normalized()      # along the gimballed head boresight
                tip = centre+bore*(max((v-centre).dot(bore) for v in mine)+.01)
                hit, *_ = bpy.context.scene.ray_cast(deps, tip, bore, distance=40)
                assert not hit, f"{name}: bay {r['index']} emitter ray is blocked"
        assert not corridor_violations(s, crown_pts), f'{name}: Crown inside a docking corridor'
    return {'drivers_worst_error': worst, 'sector_states': {r['index']: r['state'] for r in rows if r['state'] != 'STOWED'}, 'eyelids_closed': [e['index'] for e in fsh.eye_shutters(s) if values[f"eye_shutter_{e['index']}"] >= 1.0], 'open_bays': [r['index'] for r in rows if r['open']], 'field_zone': on, 'engaged_envelope_diameter_m': None if metric is None else round(metric, 3)}


def eye_rays(s, state):
    """EYE sightlines with the field display switched off (a display layer, not a solid): clear for every facet sample."""
    r = s['eye']['aperture']['value']/2*.90
    pose_forward_state({**state, 'field_on': 0.0}); deps = bpy.context.evaluated_depsgraph_get(); clear = 0
    for w in fsh.wells(s):          # each facet face at its well bottom (r4 hub, or a cone well of the study layout)
        front = w['x0']
        for dy, dz in [(0, 0), (r, 0), (-r, 0), (0, r), (0, -r)]:
            origin = Vector((front+.05, w['y']+dy, w['z']+dz))
            while True:     # the window cartridge in the well is optical, not an obstruction: continue past it
                hit, loc, _, _, obj, _ = bpy.context.scene.ray_cast(deps, origin, Vector((1, 0, 0)), distance=40-(origin.x-front))
                if not (hit and obj.get('kind') == 'eye_window'):
                    break
                origin = loc+Vector((1e-3, 0, 0))
            assert not hit, 'Blocked EYE aperture sightline (well, skin, Lance or eyelid)'
            clear += 1
    pose_forward_state(state)
    return clear
