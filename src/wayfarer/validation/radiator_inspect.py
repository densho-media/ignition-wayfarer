"""Saved-geometry and control-state checks of the radiator health display (AFT-005).

Everything is compared with radiator_health.py (the one definition) at the saved pose and, for the control states, in memory through the linked
RADIATOR_HEALTH_CTRL. The display never moves the fixed blades: a snapshot of every blade, cell, mount, joint, coolant, boom and stay is taken at the saved
pose and compared after every posed state. Measured values are reported, never fed back into the spec.
"""
from pathlib import Path
import math
import bpy
from mathutils import Vector
import radiator_health as rh
import thermal_geometry
from spec import derived
from common import pose_radiator_state

LIBRARY = rh.SUBSYSTEM+'.blend'
OVERLAY_KINDS = {'radiator_health_marker', 'radiator_thermal_glow'}
FIXED_KINDS = {'radiator_cell', 'thermal_mount', 'expansion_joint', 'coolant_proxy', 'coolant_chase', 'datum_lug', 'joint_shoe', 'root_boom', 'thermal_support', 'deployed_lock', 'leading_edge_proxy', 'casing_boot', 'root_saddle', 'slide_stop'}
_saved = {}


def driven_value(obj, path, index, deps):
    ev = obj.evaluated_get(deps)
    if path in ('hide_viewport', 'hide_render'):
        return float(getattr(ev, path))
    raise ValueError(path)


def mismatch(s, values):
    """Pose the linked control in memory; the largest difference between evaluated drivers and radiator_health.display()."""
    pose_radiator_state(values); deps = bpy.context.evaluated_depsgraph_get()
    return max(abs(driven_value(bpy.data.objects[n], p, i, deps)-want) for (n, p, i), want in rh.display(s, values).items())


def fixed_snapshot():
    """Evaluated matrices, bounding boxes and centroids of every blade instance, cell, mount, joint, coolant, boom, stay and spar (sorted)."""
    rows = []
    for instance in bpy.context.evaluated_depsgraph_get().object_instances:
        obj = instance.object; kind = obj.get('kind'); m = instance.matrix_world
        if str(obj.get('component_id', '')).startswith('WF.RADIATOR.0'):
            rows.append((obj.original.name, 'blade', tuple(round(x, 9) for r in m for x in r), (), (), ()))
            continue
        # Thermal production detail (detail packs of module WF-THERMAL, docs/MODULES.md) is held to the same rule: fixed with its blade.
        thermal_detail = kind == 'production_detail' and obj.get('module') == 'WF-THERMAL'
        if (kind not in FIXED_KINDS and not thermal_detail) or obj.type not in {'MESH', 'CURVE'}:
            continue
        data = obj.to_mesh(); vs = [m@v.co for v in data.vertices]; obj.to_mesh_clear()
        if not vs:
            continue
        lo = tuple(min(v[i] for v in vs) for i in range(3)); hi = tuple(max(v[i] for v in vs) for i in range(3)); cen = tuple(sum(v[i] for v in vs)/len(vs) for i in range(3))
        rows.append((obj.original.name, kind, tuple(round(x, 9) for r in m for x in r), lo, hi, cen))
    return sorted(rows, key=lambda r: (r[0], r[1], r[2]))


def snapshot_difference(a, b):
    """Largest absolute difference between two snapshots (matrix, bounding box, centroid); inf when the object sets differ."""
    if len(a) != len(b) or any(x[:2] != y[:2] for x, y in zip(a, b)):
        return math.inf
    worst = 0.0
    for x, y in zip(a, b):
        for u, v in zip(x[2:], y[2:]):
            worst = max([worst]+[abs(p-q) for p, q in zip(u, v)])
    return worst


def measured_planform(deps=None):
    """Total planform of the evaluated radiator cells: half the area of the faces that lie in the sheet plane (the solidified sheet has two)."""
    total = 0.0; root = 0
    for instance in (deps or bpy.context.evaluated_depsgraph_get()).object_instances:
        obj = instance.object
        if obj.get('kind') != 'radiator_cell':
            continue
        data = obj.to_mesh(); total += sum(p.area for p in data.polygons if abs(p.normal.z) > .999)/2; obj.to_mesh_clear()
        root += obj.get('thermal_zone') == 'ROOT_TRANSITION'
    return total, root


def overlay_instances():
    """{name: (kind, material rgba)} of the overlays that evaluate with faces (visible), from any library. The colour is the fixed material's."""
    out = {}
    for instance in bpy.context.evaluated_depsgraph_get().object_instances:
        obj = instance.object; kind = obj.get('kind')
        if kind in OVERLAY_KINDS:
            data = obj.to_mesh(); faces = len(data.polygons); obj.to_mesh_clear()
            if faces:
                mat = obj.original.data.materials[0]
                out[obj.original.name] = (kind, tuple(float(x) for x in mat.diffuse_color))
    return out


def library_cells():
    """Linked library cells by name (WF_RADIATOR.blend): the zone and id the markers must agree with."""
    return {o.name: o for o in bpy.data.objects if o.get('kind') == 'radiator_cell' and o.library is not None and Path(bpy.path.abspath(o.library.filepath)).name == 'WF_RADIATOR.blend'}


def check_saved(s):
    """Preset-independent checks at the saved (neutral) pose; records the fixed snapshot every posed state is compared with."""
    ob = bpy.data.objects; ctrl = ob[rh.CONTROL]
    assert all(math.isclose(ctrl[k], v, abs_tol=1e-12) for k, v in rh.neutral(s).items()) and ctrl.animation_data is None, 'Radiator health control must be saved neutral with no action'
    cells = rh.cells(s); n = 0
    for name, path, index, expression in rh.drivers(s):
        owner = ob[name]
        fc = next(f for f in owner.animation_data.drivers if f.data_path == path and (index == -1 or f.array_index == index))
        assert fc.driver.expression == expression and fc.driver.is_valid and fc.driver.is_simple_expression, (name, path, index)
        assert all(v.targets[0].id == ctrl and v.targets[0].data_path == f'["{rh.VARIABLES[v.name]}"]' for v in fc.driver.variables), (name, path)
        n += 1
    markers = [o for o in ob if o.get('kind') == 'radiator_health_marker']; glows = [o for o in ob if o.get('kind') == 'radiator_thermal_glow']
    assert len(markers) == 2*len(cells) == 2*rh.cell_count(s) and len(glows) == s['radiators']['count']*len(rh.glow_steps(s)), (len(markers), len(glows))
    assert not any(n.type == 'OBJECT_INFO' for m in bpy.data.materials if m.node_tree and m.name.startswith(('WF_MAT_RadiatorGlow', 'WF_MAT_RadiatorCell')) for n in m.node_tree.nodes), 'Overlay shaders must not read Object Info'
    assert not overlay_instances(), 'Health overlays must evaluate hidden in the saved state'
    lib = library_cells()
    for o in markers+glows:
        assert o.get('kind') != 'radiator_cell' and 'thermal_zone' not in o and not o.get('variable_emissivity_permitted') and o['planform_m2'] == 0.0 and o['display_only'], o.name
        assert o.parent is not None and str(o.parent.get('component_id', '')).startswith('WF.RADIATOR.0'), f'{o.name} must hang on its Radiator_0n instance'
    by_name = {o.name: o for o in markers}
    for c in cells:
        assert by_name[c['resurfaced_name']]['marker_state'] == 'RESURFACED'
        o = by_name[c['name']]
        cell = lib[f"Blade_Cell_{c['ribbon']}_{c['j']:02}_{c['k']:02}"]
        assert o['thermal_cell_id'] == c['thermal_cell_id'] == cell['thermal_cell_id'] and cell['thermal_zone'] == c['zone'] and o['cell_rank'] == c['rank'] and o['blade'] == c['blade']+1, c['name']
    _saved['snapshot'] = fixed_snapshot(); total, root = measured_planform()
    assert len(_saved['snapshot']) > rh.cell_count(s), 'Fixed snapshot must cover the blades, cells, mounts, joints, coolant, booms and stays'
    assert math.isclose(total, _expected_planform(s), rel_tol=1e-6) and root == thermal_geometry.root_band(s)['cells_per_blade']*s['radiators']['count'], (total, root)
    return {'markers': len(markers), 'glows': len(glows), 'drivers': n, 'control_saved': 'NEUTRAL (all controls 0)', 'cells': rh.cell_count(s)}


def check_state(s, name, values):
    """One control state posed in memory (a preset, a display pose or a sweep point): evaluated drivers against radiator_health.display(), the shown markers
    and their alpha against cell_states, the glow colour against the step, and every fixed object unchanged from the saved snapshot."""
    worst = mismatch(s, values); assert worst < 1e-6, f'{name}: radiator health drivers off by {worst}'
    cells = rh.cells(s); states = rh.cell_states(s, values); shown = overlay_instances()
    want = {c['name']: st for c, st in zip(cells, states) if st in ('ISOLATED', 'RESURFACED')}       # a requalified cell shows no marker
    want.update({c['resurfaced_name']: 'RESURFACED' for c, st in zip(cells, states) if st == 'RESURFACED'})
    got = {k: v for k, v in shown.items() if v[0] == 'radiator_health_marker'}
    assert set(got) == set(want), f'{name}: markers shown {len(got)}, expected {len(want)}'
    for k in got:       # the dark marker is the isolated colour, the one above it the resurfaced colour
        want_rgb = s['radiator_health']['display']['resurfaced_rgb' if k.endswith('_R') else 'isolated_rgb']
        assert max(abs(a-b) for a, b in zip(got[k][1][:3], want_rgb)) < 1e-6, f'{k}: marker colour'
    glows = {k: v for k, v in shown.items() if v[0] == 'radiator_thermal_glow'}
    step = rh.step_index(s, values['thermal_state']); rgba = rh.glow_rgba(s, values['thermal_state'])
    assert set(glows) == (set() if step == 0 else {rh.glow_name(b, step) for b in range(s['radiators']['count'])}), f'{name}: glows shown {sorted(glows)} at step {step}'
    assert all(max(abs(a-b) for a, b in zip(v[1], rgba)) < 1e-6 for v in glows.values()), f'{name}: glow colour'
    lib = library_cells(); by = {c['name']: c for c in cells}; by.update({c['resurfaced_name']: c for c in cells})
    for k in want:
        c = by[k]; assert lib[f"Blade_Cell_{c['ribbon']}_{c['j']:02}_{c['k']:02}"]['thermal_zone'] == c['zone'], k
    diff = snapshot_difference(_saved['snapshot'], fixed_snapshot())
    assert diff <= 1e-9, f'{name}: fixed radiator objects moved by {diff}'
    total, root = measured_planform()
    assert math.isclose(total, _expected_planform(s), rel_tol=1e-6), f'{name}: measured planform {total}'
    band = thermal_geometry.root_band(s)['cells_per_blade']*s['radiators']['count']
    assert root == band, f'{name}: ROOT_TRANSITION cells {root}'
    tagged = [o for o in bpy.data.objects if o.get('variable_emissivity_permitted')]       # library cells exist once and are instanced per blade
    assert len(tagged) == band//s['radiators']['count'] and all(o.get('kind') == 'radiator_cell' and o.get('thermal_zone') == 'ROOT_TRANSITION' for o in tagged), f'{name}: variable-emissivity tags'
    return {'drivers_worst_error': worst, 'isolated': sum(x == 'ISOLATED' for x in states), 'resurfaced': sum(x == 'RESURFACED' for x in states),
            'requalified': sum(x == 'REQUALIFIED' for x in states),
            'glow_step': rh.steps(s)[step], 'available_cell_fraction': rh.available_cell_fraction(s, values), 'fixed_objects_max_change': diff,
            'measured_planform_m2': round(total, 3)}


def _expected_planform(s):
    return thermal_geometry.emitting_planform(s)*s['radiators']['count']      # AFT-009: the cells stop at the non-emitting joints


def sweep(s):
    """Control sweep: thermal_state through every step and the extremes of isolation, repair and requalification."""
    out = {}
    for th in (0.0, .25, .5, .75, 1.0):
        for iso, res, req in ((0.0, 0.0, 0.0), (1.0, .5, .25)):
            out[f'th={th} iso={iso} res={res} req={req}'] = check_state(s, f'sweep th={th} iso={iso} res={res} req={req}',
                                                                        {'thermal_state': th, 'cell_isolation': iso, 'cell_resurface': res, 'cell_requalify': req})
    return out
