"""FUT-006: the saved First Ignition flight shot against the timeline (Blender). Run after build_flight.py:
/snap/bin/blender --background --factory-startup --python-exit-code 1 shots/SH_FIRST_IGNITION_FLIGHT.blend --python tests/verify_flight_shot.py

Reopened from disk: it is the generated shot, links the vehicle by relative path and owns no source geometry; at every mark frame each
overridden control evaluates to the timeline sample, each ring sits at phase + rate x spin_turned (at its index angle when at rest), and
the readout carries the kinematics.
"""
import json
import math
import sys
from pathlib import Path
import bpy
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/shots')]
import spec
import flight_timeline as ft
import rotor_interface
import build_flight

s, *_ = spec.load(ROOT); scene = bpy.context.scene
assert scene.get('wf_shot') == build_flight.NAME and scene.get('wf_owner') == build_flight.OWNER, 'not the generated flight shot'
assert ft.check(ROOT), 'stale timeline'
assert scene['timeline_sha256'] == build_flight.hashlib.sha256((ROOT/ft.table(s)['output']).read_bytes()).hexdigest(), 'the shot was built from another timeline'
assert all(lib.filepath.startswith('//') for lib in bpy.data.libraries), [lib.filepath for lib in bpy.data.libraries]
local = [d.name for d in [*bpy.data.meshes, *bpy.data.curves] if d.library is None and not d.override_library and d.get('wf_owner') != build_flight.OWNER]
assert not local, f'local source geometry {local[:5]}'
tl = json.loads((ROOT/ft.table(s)['output']).read_text())
rate = s['habitat']['rpm']*math.tau/60/24; rev = rotor_interface.frames_per_turn(s)
readout = bpy.data.objects['SHOT_Label_Readout']; checked = {}
for name, mark in tl['marks'].items():
    frame = int(mark['frame']); scene.frame_set(frame); deps = bpy.context.evaluated_depsgraph_get(); worst = 0.0
    for channel, c in tl['channels'].items():
        if c['binding']:
            for control in c['binding']['controls']:
                got = build_flight.overridden(control).evaluated_get(deps)[c['binding']['property']]
                worst = max(worst, abs(got-mark['values'][channel]))
    assert worst < 1e-4, f'{name}: controls off the timeline by {worst}'
    for j, phase in enumerate(s['prototype']['rotor_phase_deg'], 1):
        angle = build_flight.overridden(f'Rotor_{j}').evaluated_get(deps).rotation_euler.x
        want = math.radians(phase)+(1 if j == 1 else -1)*rate*mark['values']['rotor.spin_turned']
        assert abs(math.remainder(angle-want, math.tau)) < 1e-4, (name, j, angle, want)
        if mark['values']['rotor.spin_fraction'] == 0:
            assert abs(math.remainder(angle-math.radians(phase), math.tau)) < 1e-4, (name, j, 'off its index angle at rest')
    inputs = readout.modifiers['Readout'].properties.inputs
    values = [getattr(inputs, sock.identifier).value for sock in readout.modifiers['Readout'].node_group.interface.items_tree if sock.in_out == 'INPUT' and sock.socket_type == 'NodeSocketFloat'][1:]
    want = [mark['values']['kinematics.burn_elapsed_s']/86400, *(mark['values'][k] for k in build_flight.READOUT[1:])]
    assert all(abs(a-b) <= 1e-6*max(1, abs(b)) for a, b in zip(values, want)), (name, values, want)
    checked[name] = {'frame': frame, 'controls_worst': worst}
print('WF_VERIFY_FLIGHT_SHOT PASS', json.dumps(checked), flush=True)
