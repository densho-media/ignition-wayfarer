"""NAV-001: the saved navigation stage against the imported route (Blender). Run after build_nav_stage.py:
/snap/bin/blender --background --factory-startup --python-exit-code 1 shots/SH_NAV_STAGE.blend --python tests/verify_nav_stage.py

Import fidelity and frame correspondence only (NAV-027..031, 26_BLENDER_CONTRACT C-003..C-012): the import is current and released, both
scenes run 1..900 at the route's fps, every frame's marker position (through the reversible display transform) and readout equal the route
row of the same number, the ANALYTICAL scene holds no enlarged ship, both carry the DIAGNOSTIC 1D legend, and the vehicle is linked one way
by a relative path with no local source geometry.
"""
import json
import sys
from pathlib import Path
import bpy
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/shots'), str(ROOT/'tools')]
import hashlib
import spec
import flight_timeline as ft
import route_import
import build_nav_stage as nav

s, *_ = spec.load(ROOT)
assert route_import.run(ROOT, check=True)['result'] == 'CURRENT', 'the route import is stale: run workflow.py route-import'
r = nav.route(ROOT, s); cols = {c: i for i, c in enumerate(r['columns'])}; rows = r['frames']
digest = hashlib.sha256((ROOT/ft.table(s)['route']).read_bytes()).hexdigest()
close = lambda a, b: abs(a-b) <= 1e-6*max(1.0, abs(b))          # Blender keys are float32


def curves(obj):
    ad = obj.animation_data; bag = ad.action.layers[0].strips[0].channelbag(ad.action_slot)
    return {(fc.data_path, fc.array_index): fc for fc in bag.fcurves}


def one_key_per_frame(fc):
    pts = fc.keyframe_points
    return [p.co[0] for p in pts] == [float(n) for n in range(1, len(rows)+1)] and all(p.interpolation == 'LINEAR' for p in pts)


checked = {}
for mode in nav.SCENES:
    sc = bpy.data.scenes[f'{nav.NAME}_{mode}']
    assert sc.get('wf_shot') == nav.NAME and sc.get('wf_owner') == nav.OWNER and sc['nav_mode'] == mode, f'{sc.name}: not the generated stage'
    assert sc['route_sha256'] == digest and sc['route_version'] == r['route_version'], f'{sc.name}: built from another route import'
    assert (sc.render.fps, sc.render.fps_base, sc.frame_start, sc.frame_end) == (int(r['fps']), 1.0, 1, r['frame_count']), f'{sc.name}: not {r["fps"]} fps over 1..{r["frame_count"]}'
    names = {o.name for o in sc.objects}
    assert ('NAV_Ship_Presentation' in names) == (mode == 'PRESENTATION'), f'{sc.name}: the enlarged ship belongs to PRESENTATION only'
    legend = [o for o in sc.objects if o.name.startswith('NAV_Label_Legend')]
    assert legend and 'DIAGNOSTIC 1D' in legend[0].data.body and 'NOT a Sun or Earth distance' in legend[0].data.body, f'{sc.name}: legend (NAV-030)'
    readout = bpy.data.objects[json.loads(sc['readouts'])[mode]]; got = curves(readout)
    inputs = [sock.identifier for sock in readout.modifiers['Readout'].node_group.interface.items_tree if sock.in_out == 'INPUT' and sock.socket_type == 'NodeSocketFloat'][1:]
    worst = 0.0
    for ident, (*_, col) in zip(inputs, nav.READOUT):
        fc = got[(f'modifiers["Readout"].properties.inputs.{ident}.value', 0)]; assert one_key_per_frame(fc), (mode, col)
        for n, row in enumerate(rows, 1):
            assert close(fc.evaluate(n), row[cols[col]]), (mode, col, n, fc.evaluate(n), row[cols[col]])
            worst = max(worst, abs(fc.evaluate(n)-row[cols[col]])/max(1.0, abs(row[cols[col]])))
    checked[mode] = {'readout_worst_rel': worst}

marker = bpy.data.objects['NAV_Ship_Marker']; xf = bpy.data.objects['NAV_DisplayTransform']; mpu = xf['metres_per_unit']
assert mpu == nav.DISPLAY['metres_per_unit'] and xf['inverse'] == nav.DISPLAY['inverse'], 'display transform'
loc = curves(marker); worst = 0.0
for i, col in enumerate(('local_x_m', 'local_y_m', 'local_z_m')):
    fc = loc[('location', i)]; assert one_key_per_frame(fc), col
    for n, row in enumerate(rows, 1):
        back = fc.evaluate(n)*mpu                                   # the inverse transform returns the imported metres
        assert close(back, row[cols[col]]), (col, n, back, row[cols[col]]); worst = max(worst, abs(back-row[cols[col]])/max(1.0, abs(row[cols[col]])))
for n in (1, (len(rows)+1)//2, len(rows)):                           # the evaluated scene agrees with the keys (the scenes share the marker)
    bpy.context.scene.frame_set(n)
    assert close(marker.matrix_world.translation.x*mpu, rows[n-1][cols['local_x_m']]), n
assert all(lib.filepath.startswith('//') for lib in bpy.data.libraries), [lib.filepath for lib in bpy.data.libraries]
local = [d.name for d in [*bpy.data.meshes, *bpy.data.curves] if d.library is None and not d.override_library and d.get('wf_owner') != nav.OWNER]
assert not local, f'local source geometry {local[:5]}'
assert not any(o.override_library for o in bpy.data.objects), 'the vehicle is linked one way, never overridden'
checked['marker_worst_rel'] = worst; checked['frames'] = len(rows)
print('WF_VERIFY_NAV_STAGE PASS', json.dumps(checked), flush=True)
