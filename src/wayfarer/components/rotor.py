"""P1-008 rotor-interface recipes. Shapes, positions, interfaces and states come from rotor_interface.

WF_ROTOR_INTERFACE holds the stationary side: hub modules, fluid cartridges and spokes, and the retracted ring-stop lock pins.
The rotating side and the per-rotor mechanism controls live in WF_HABITAT; the vehicle is saved at the preset named by
[vehicle].saved_preset, and any other preset is posed in memory on the linked controls.
"""
import bpy
from common import empty, material, mesh, line, owned_action, drop_stale_actions
import rotor_interface as ri

COLORS = {'MAGNETIC_BEARING': ('MagneticBearing', (.20, .42, .80)), 'TOUCHDOWN_BEARING': ('TouchdownBearing', (.88, .52, .14)),
          'HUB_MOTOR': ('HubMotor', (.70, .40, .20)), 'CONTACTLESS_POWER': ('ContactlessPower', (.72, .76, .20)),
          'CONTACTLESS_DATA': ('ContactlessData', (.20, .74, .80)), 'EMERGENCY_POWER_PATH': ('EmergencyPower', (.82, .20, .22)),
          'FLUID_COUPLING': ('FluidCoupling', (.15, .43, .51)), 'HUB_DRUM': ('HabitatArms', (.46, .57, .63))}
STATUS = {'MAGNETIC_BEARING': 'OPEN OD-013: sizing and losses', 'TOUCHDOWN_BEARING': 'OPEN OD-013: rating, clearance and material',
          'HUB_MOTOR': 'OPEN MEC-004: topology, torque, gearing', 'CONTACTLESS_POWER': 'OPEN S5: rating', 'CONTACTLESS_DATA': 'OPEN: link type',
          'EMERGENCY_POWER_PATH': 'OPEN: source and rating', 'FLUID_COUPLING': 'OPEN OD-002: circuits, media, size', 'HUB_DRUM': 'OPEN OD-002: structure'}


def label(obj, s, function, **fields):
    obj['function'] = function; obj['source_ref'] = ri.SOURCES[function]
    obj['canon_status'] = 'WORKING'
    obj['geometry_basis'] = 'PROTOTYPE display proxy ([rotor_interface]); no size, gap, rating or loss is sourced'
    obj['engineering_status'] = STATUS.get(function, 'OPEN')
    for key, value in fields.items():
        obj[key] = value
    return obj


def rotor_interface(c, s):
    """WF_ROTOR_INTERFACE: stationary hub modules, fluid-coupling cartridges and spokes, stationary interfaces."""
    service = ri.withdrawal(s)
    for part in ri.stationary(s):
        name, color = COLORS[part['function']]
        obj = mesh(c, part['name'], part['vertices'], part['faces'], material(name, color), ident=part['ident'], kind=part['kind'])
        row = service[part['name']]
        label(obj, s, part['function'], module=part['module'], side='STATIONARY', rotor=part['rotor'], withdraw=row['direction'],
              removal_prerequisites=', '.join(row['prerequisites']) or 'none', module_form='SERVICEABLE_CARTRIDGE')
    mount = material('Structure', (.30, .40, .48))
    for sp in ri.spokes(s):
        label(line(c, sp['name'], [sp['a'], sp['b']], sp['radius'], mount, kind='rotor_mount'), s, 'FLUID_MOUNT', side='STATIONARY', rotor=sp['rotor'])
    # Ring-stop lock pins: retracted stationary housings at the three crew-spoke angles. Lock geometry, stroke, rotating strike fitting
    # and rating are OPEN (MEC-011, I5, OD-016).
    lock = material('Locks', (.69, .45, .16))
    for b in ri.ring_stop_locks(s):
        obj = line(c, b['name'], [b['a'], b['b']], b['radius'], lock, kind='ring_stop_lock')
        label(obj, s, 'RING_STOP_LOCK', side='STATIONARY', rotor=b['rotor'], load_path='spine -> lock -> ring (strike fitting not modelled); bypasses the hub bearings, motor and actuators')
        obj['engineering_status'] = 'OPEN MEC-011: lock geometry, stroke, rotating strike fitting and rating not designed'
        drive = empty(c, b['drive'], b['a']); drive['engineering_status'] = 'OPEN MEC-007/011: serviceable lock-drive cartridge; not a structural load path'
    for f in ri.interfaces(s):
        if f['side'] != 'STATIONARY':
            continue
        obj = empty(c, f['name'], f['at']); obj['engineering_status'] = f['status']; obj['rotor'] = f['rotor']
        if 'pairs_with' in f:
            obj['pairs_with'] = '; '.join(f'{a}:{b}' for a, b in f['pairs_with'])
        if 'channels' in f:
            obj['health_channels'] = ', '.join(f['channels'])


def hub(c, s, parent, j):
    """Rotating side of rotor j in its local frame, parented to the rotor so it follows the ring rotation."""
    for part in (p for p in ri.rotating(s) if p['rotor'] == j):
        name, color = COLORS[part['function']]
        obj = mesh(c, part['name'], part['vertices'], part['faces'], material(name, color), ident=part['ident'], kind=part['kind'])
        obj.parent = parent
        label(obj, s, part['function'], side='ROTATING', rotor=j)
    for f in (f for f in ri.interfaces(s) if f['rotor'] == j and f['side'] == 'ROTATING'):
        obj = empty(c, f['name'], f['at']); obj.parent = parent; obj['engineering_status'] = f['status']


def controls(c, s, j):
    """Rotor j's mechanism control (its ring asset, WF_HABITAT_<A|B>), saved at the vehicle's saved preset."""
    preset = s['vehicle']['saved_preset']; saved = ri.configuration_state(s, preset); objs = {}
    for rot in (r for r in ri.rotors(s) if r['index'] == j):
        ctrl = empty(c, ri.control(rot['index']), (rot['x'], 0.0, 0.0), ident=f"WF.HUB.{rot['index']}.STATE_CONTROL", kind='state_control')
        ctrl.empty_display_type = 'CUBE'; ctrl.empty_display_size = .3
        for key, value in saved.items():
            ctrl[key] = float(value)
            ctrl.id_properties_ui(key).update(min=0.0, max=1.0, description=ri.PROPS[key])
            ctrl.property_overridable_library_set(f'["{key}"]', True)
        for key, description in ri.TURN_PROPS.items():
            ctrl[key] = 0.0
            ctrl.id_properties_ui(key).update(min=0.0, description=description)
            ctrl.property_overridable_library_set(f'["{key}"]', True)
        ctrl['canon_status'] = 'WORKING'; ctrl['source_ref'] = 'rotor_interface_i5'
        ctrl['state'] = f"{preset} (rings {s['configuration'][preset]['habitat']}): PROTOTYPE display state, not a control law"
        ctrl['engineering_status'] = 'OPEN: spin-down duration, braking torque, touchdown thermal case and control law (MEC-010, OD-013)'
        objs[ctrl.name] = ctrl
    return objs


def actions(s):
    """The unassigned whole-habitat stop-lock, touchdown and seal-fault actions (WF_HABITAT), one slot per rotor control by name: matched
    spin-down of both rings keeps the counter-rotating momenta cancelled, so each action spans both ring assets."""
    drop_stale_actions(set(ri.ACTIONS))
    for name, spec in ri.actions(s).items():
        action = owned_action(name); strip = action.layers.new('Mechanism').strips.new(type='KEYFRAME')
        for slot_name, keys in spec['slots'].items():
            slot = action.slots.new(id_type='OBJECT', name=slot_name)
            bag = strip.channelbag(slot, ensure=True)
            for prop in ri.PROPS:
                fc = bag.fcurves.new(data_path=f'["{prop}"]'); fc.keyframe_points.add(len(keys))
                for kp, (frame, values) in zip(fc.keyframe_points, keys):
                    kp.co = (frame, values[prop]); kp.interpolation = 'LINEAR' if prop == 'spin_fraction' else 'CONSTANT'
                fc.extrapolation = 'CONSTANT'; fc.update()
            # FUT-007: the integrated ring turn, so the ring slows to rest at its index angle without reversing.
            turned = ri.spin_turned(s, [(f, v['spin_fraction']) for f, v in keys])
            fc = bag.fcurves.new(data_path='["spin_turned"]'); fc.keyframe_points.add(len(turned))
            for kp, (frame, value) in zip(fc.keyframe_points, turned):
                kp.co = (frame, value); kp.interpolation = 'LINEAR'
            fc.extrapolation = 'CONSTANT'; fc.update()
            fc = bag.fcurves.new(data_path='["spin_integrated"]'); fc.keyframe_points.add(1)
            fc.keyframe_points[0].co = (keys[0][0], 1.0); fc.keyframe_points[0].interpolation = 'CONSTANT'; fc.update()
        action.use_frame_range = True; action.frame_start, action.frame_end = spec['frame_range']
        action['description'] = spec['description']; action['status'] = 'PROTOTYPE timing; spin-down duration OPEN'
        action['targets'] = ', '.join(spec['slots'])
