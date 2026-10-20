"""P1-007 POWER_STORAGE recipe: layered-storage proxies, OPEN interfaces, ride-through markers and the black-start rig.

Shapes, positions and interfaces come from power_storage (PROTOTYPE [power_storage] table); energies, power and
rules from the sourced [power.storage] tables. The control carries display flags only and is saved at step 0.
"""
import bpy
from common import empty, material, mesh, owned_action
import power_storage as ps
import layout

FACES = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
COLORS = {'MAIN_BATTERY': ('MainBattery', (.18, .52, .62)), 'PULSE_BANK': ('PulseBank', (.52, .34, .78)), 'SURVIVAL_RESERVE': ('SurvivalReserve', (.30, .62, .32))}


def layer_fields(s, layer):
    st = s['power']['storage']
    if layer == 'MAIN_BATTERY':
        m = st['main_battery']
        return m, {'usable_energy_Wh': m['usable_energy_Wh'], 'specific_energy_Wh_kg': m['specific_energy_Wh_kg'], 'installed_mass': 'OPEN', 'fusion_off_endurance': 'OPEN'}
    if layer == 'PULSE_BANK':
        m = st['pulse_bank']
        return m, {'energy_Wh': m['energy_Wh'], 'power_W': m['power_W'], 'charge_sources': ', '.join(m['charge_sources']), 'ignition_energy': 'OPEN'}
    m = st['survival_reserve']
    return m, {'capacity': 'OPEN', 'endurance': 'OPEN', 'isolated_from': ', '.join(m['isolated_from']), 'loads': ', '.join(m['loads'])}


def power_storage(c, s):
    for p in ps.packs(s):
        name, color = COLORS[p['layer']]
        obj = mesh(c, p['name'], p['corners'], FACES, material(name, color), ident=p['ident'], kind='power_storage')
        field, values = layer_fields(s, p['layer'])
        obj['layer'] = p['layer']; obj['technology'] = field['technology']
        obj['canon_status'] = field['canon_status']; obj['source_ref'] = field['source_ref']
        for key, value in values.items():
            obj[key] = value
        obj['display_volume_m3'] = p['volume_m3']
        obj['geometry_basis'] = 'PROTOTYPE display envelope ([power_storage]); no volumetric energy density, containment or thermal design is sourced'
        empty(c, p['interface'], p['center'])['layer'] = p['layer']
    for f in ps.pack_interfaces(s):
        empty(c, f['name'], f['at'])['engineering_status'] = f['status']
    for r in ps.ride_through_points(s):
        obj = empty(c, r['name'], r['at'], kind='ride_through')
        obj['load'] = r['load']; obj['pairs_with'] = ':'.join(r['pairs_with'])
        obj['canon_status'] = 'BASELINE'; obj['source_ref'] = 'power_storage_ride_through'
        obj['engineering_status'] = 'OPEN: device-level UPS / local capacitor ride-through; capacity OPEN (17_POWER_STORAGE D7)'
    # Black-start state control: display flags only, saved at step 0 (cold ship). Configuration power states stay OPEN.
    ctrl = empty(c, ps.CONTROL, (layout.at(s, s['power_storage']['main_battery']['x0'])-1.0, 0.0, -4.5), ident='WF.POWER.STATE_CONTROL', kind='state_control')
    ctrl.empty_display_type = 'CUBE'; ctrl.empty_display_size = .4
    for key, value in ps.step_state(0).items():
        ctrl[key] = float(value)
        ctrl.id_properties_ui(key).update(min=0.0, max=9.0 if key == 'black_start_step' else 1.0, description=ps.PROPS[key])
        ctrl.property_overridable_library_set(f'["{key}"]', True)
    ctrl['canon_status'] = s['power']['black_start']['canon_status']; ctrl['source_ref'] = s['power']['black_start']['source_ref']
    ctrl['state'] = 'STEP 0 (cold ship); a display state, not a configuration power state'
    ctrl['units'] = 'step number and 0/1 flags; no state of charge'
    ctrl['rule'] = 'Survival power does not imply restart power: the survival reserve never charges the pulse bank'
    ctrl['engineering_status'] = 'OPEN: hotel source (S7/OD-009), survival capacity/endurance, generator ratings and ignition energy'
    tables = ps.action(s); action = owned_action(ps.ACTION)
    slot = action.slots.new(id_type='OBJECT', name=ctrl.name)
    bag = action.layers.new('BlackStart').strips.new(type='KEYFRAME').channelbag(slot, ensure=True)
    for prop in ps.PROPS:
        fc = bag.fcurves.new(data_path=f'["{prop}"]'); fc.keyframe_points.add(len(tables['keys']))
        for kp, (frame, values) in zip(fc.keyframe_points, tables['keys']):
            kp.co = (frame, values[prop]); kp.interpolation = 'CONSTANT'
        fc.extrapolation = 'CONSTANT'; fc.update()
    action.use_frame_range = True; action.frame_start, action.frame_end = tables['frame_range']
    action['description'] = tables['description']; action['status'] = 'PROTOTYPE timing; owner step order'; action['target'] = ctrl.name
    return ctrl
