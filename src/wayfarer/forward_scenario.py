"""FWD-V2 scenario state contract (S&E 50 AG-014): one versioned frame format for every forward-defense replay. A frame carries time, ship
frame, relative velocity, target class, uncertainty, detection state, energy, permitted response and the thermal / pulse-bank / repair state.
Pure, standard library only. SIMULATION_ONLY: timing and energy come from the Eye owner formulas at the LOCKED 0.016 c (15_ACTIVE_LIDAR,
35_SCALING_LIMITS, 40_BROW_SHIELD); the hazard classes and the response order from 25_HAZARD_RESPONSE. No probability, cross section,
effector performance or survival is held anywhere: those stay OPEN and every outcome is UNKNOWN unless an owner row says otherwise.

    python3 src/wayfarer/forward_scenario.py        # print the reference tables
"""
import math
import forward_shield as fsh

CONTRACT = 'WF_FORWARD_SCENARIO'
VERSION = 1
SHIP_FRAME = 'WF_SHIP: metres, +X bow, +Z dorsal (Blender axes), origin at the model origin'
VELOCITY_BASIS = 'target stationary along the approach; real relative vectors and two-way lidar delay matter (Eye 45 FD-E13)'
SOURCES = ('fwd_scenario_contract', 'eye_lidar_horizon', 'eye_scaling_limits', 'eye_impact_scale', 'eye_hazard_response')

# Eye 25_HAZARD_RESPONSE A12:D15, rank order; passive protection is always active (Eye 45 FD-E12) and is not a ranked action.
RESPONSES = ('AVOID', 'DEFLECT', 'ABLATE', 'FRAGMENT')
PASSIVE = 'PASSIVE_LAYERS'
# Detection states named after the "Primary detection" column of Eye 25!C4:C8 (PROTOTYPE enumeration of that column).
DETECTION = ('UNDETECTED', 'STATISTICAL', 'PASSIVE_CUE', 'LIDAR_CONFIRMED', 'TRACKED', 'LOST')
# Eye 25!A4:G8: class, typical scale, detection, the ranked actions its preferred response names, the owner text, row status.
HAZARDS = {
    'MICRODUST': ('micron-sub-mm', 'STATISTICAL', (), 'veil where permitted -> disruptor layer(s) -> Dust Lance -> charged-ejecta diversion -> Brow',
                  'LOCKED doctrine / WORKING mechanism', 'A4'),
    'SMALL_FRAGMENT': ('mm-cm', 'PASSIVE_CUE', ('AVOID', 'ABLATE'), 'avoid if practical; Crown ablation/ionization if tracking permits; veil, '
                       'passive stack and Brow for late residuals', 'BASELINE', 'A5'),
    'PEBBLE_ROCK': ('cm-dm', 'LIDAR_CONFIRMED', ('AVOID', 'ABLATE'), 'course tweak or laser ablation', 'BASELINE', 'A6'),
    'METER_CLASS': ('~1-10 m', 'TRACKED', ('AVOID', 'ABLATE'), 'early course change; sustained ablation; interceptor backup', 'BASELINE', 'A7'),
    'LARGE_BODY': ('10 m+', 'TRACKED', ('AVOID', 'DEFLECT'), 'Wayfarer moves; long-duration deflection only', 'LOCKED', 'A8'),
}
# Eye 35_SCALING_LIMITS A4:A9 (15_ACTIVE_LIDAR B4:B6 repeats the last three); 1 AU as 35!B9.
HORIZON_M = (1e6, 1e7, 1e8, 1e9, 1e10, 149597870700.0)
# Eye 40_BROW_SHIELD A4:C7.
MASSES = ((1e-9, '1 ug'), (1e-6, '1 mg'), (1e-3, '1 g'), (1.0, '1 kg'))
FORBIDDEN = {'probability', 'p_hit', 'p_kill', 'hit_probability', 'cross_section_m2', 'shield_health', 'kill'}
FRAME_KEYS = ('t_s', 'ship_frame', 'relative_velocity_m_s', 'target', 'uncertainty', 'detection_state', 'range_m', 'time_to_impact_s',
              'energy_j', 'permitted_response', 'vehicle_state')


def speed_m_s(s):
    return s['mission']['target_speed']['value']*fsh.SPEED_OF_LIGHT


def gamma(s):
    return 1/math.sqrt(1-s['mission']['target_speed']['value']**2)


def impact_energy_j(s, mass_kg):
    """Eye 40!F4:F7: E = (gamma - 1) m c^2 at the LOCKED cruise speed."""
    return (gamma(s)-1)*mass_kg*fsh.SPEED_OF_LIGHT**2


def time_to_range_s(s, range_m):
    """Eye 35!F4:F9 (x60) and 15!F4:F6: flight time to a range at 0.016 c, target stationary along the approach."""
    return range_m/speed_m_s(s)


def round_trip_s(range_m):
    """Eye 35!E4:E9 and 15!E4:E6: two-way light time."""
    return 2*range_m/fsh.SPEED_OF_LIGHT


def open_value(note=''):
    return {'known': False, 'status': 'OPEN', 'note': note}


def value(v, unit, status, source_ref=''):
    return {'known': True, 'value': v, 'unit': unit, 'status': status, 'source_ref': source_ref}


def warning_horizon(s):
    return [{'range_m': r, 'round_trip_s': round_trip_s(r), 'time_to_range_s': time_to_range_s(s, r), 'status': 'DERIVED',
             'source_ref': 'eye_scaling_limits'} for r in HORIZON_M]


def energy_orders(s):
    return [{'mass_kg': m, 'label': label, 'energy_j': impact_energy_j(s, m), 'status': 'DERIVED', 'source_ref': 'eye_impact_scale'}
            for m, label in MASSES]


def hazard_classes():
    return [{'class': k, 'scale': v[0], 'detection': v[1], 'responses': list(v[2]), 'passive_always': True, 'text': v[3], 'status': v[4],
             'source_ref': 'eye_hazard_response', 'row': v[5]} for k, v in HAZARDS.items()]


def time_scales(path_time_s, display_s):
    """AG-014 E: physical and slowed explanatory replay, each visibly identified."""
    expand = display_s/path_time_s
    return [{'mode': 'PHYSICAL', 'factor': 1.0, 'label': 'PHYSICAL TIME (0.016 c)'},
            {'mode': 'EXPLAINER', 'factor': expand, 'label': 'TIME EXPANDED x%d' % round(expand)}]


def frame(s, t_s, range_m, hazard, detection, permitted, mass_kg=None, uncertainty=None, note=''):
    v = speed_m_s(s)
    return {'t_s': t_s, 'ship_frame': SHIP_FRAME,
            'relative_velocity_m_s': {**value([-v, 0.0, 0.0], 'm/s', 'LOCKED 0.016 c (target_speed)'), 'basis': VELOCITY_BASIS},
            'target': {'class': hazard, 'scale': HAZARDS[hazard][0], 'mass_kg': open_value('no owner mass') if mass_kg is None else
                       value(mass_kg, 'kg', 'SIMULATION_ONLY'), 'size': open_value(), 'cross_section': open_value('no unsourced cross section (AG-014 D)')},
            'uncertainty': uncertainty or open_value('track and environment uncertainty not established'),
            'detection_state': detection, 'range_m': range_m, 'time_to_impact_s': range_m/v,
            'energy_j': open_value('mass unknown; see energy_orders') if mass_kg is None else
                        value(impact_energy_j(s, mass_kg), 'J', 'DERIVED', 'eye_impact_scale'),
            'permitted_response': list(permitted),
            'vehicle_state': {'thermal': open_value(), 'pulse_bank': open_value('no AG-009 fixture'), 'repair': open_value()},
            'note': note}


def source_snapshot(sources):
    rec = sources['sources']
    return {k: {'sheet': rec[k]['sheet'], 'range': rec[k]['range'], 'modified_at_utc': rec[k]['modified_at_utc']} for k in SOURCES}


def scenario(s, sources, ident, hazard, frames, tale, path_time_s, display_s, outcome='UNKNOWN', unknown=()):
    return {'contract': CONTRACT, 'version': VERSION, 'id': ident, 'status': 'SIMULATION_ONLY / PHYSICS OPEN', 'tale': tale,
            'hazard': hazard, 'source_snapshot': source_snapshot(sources), 'time_scales': time_scales(path_time_s, display_s),
            'frames': frames, 'unknown': list(unknown), 'outcome': outcome}


def _keys(node, out):
    if isinstance(node, dict):
        for k, v in node.items():
            out.add(k); _keys(v, out)
    elif isinstance(node, list):
        for v in node:
            _keys(v, out)
    return out


def validate(s, sc):
    """Problems with one scenario (empty when it holds the contract)."""
    bad = []
    if (sc.get('contract'), sc.get('version')) != (CONTRACT, VERSION):
        bad.append('contract/version')
    if not sc.get('source_snapshot') or any(not r.get('modified_at_utc') for r in sc['source_snapshot'].values()):
        bad.append('source snapshot')
    if {t['mode'] for t in sc.get('time_scales', [])} != {'PHYSICAL', 'EXPLAINER'} or not all(t.get('label') for t in sc['time_scales']):
        bad.append('time scales')
    if hits := FORBIDDEN & _keys(sc, set()):
        bad.append(f'forbidden keys {sorted(hits)}')
    if not str(sc.get('outcome', '')).startswith('UNKNOWN'):
        bad.append('outcome is not UNKNOWN')
    allowed = set(HAZARDS.get(sc.get('hazard'), ((), (), ()))[2]) | {PASSIVE}
    last = -math.inf
    for i, f in enumerate(sc.get('frames', [])):
        if missing := [k for k in FRAME_KEYS if k not in f]:
            bad.append(f'frame {i}: missing {missing}'); continue
        if f['t_s'] < last:
            bad.append(f'frame {i}: time runs backwards')
        last = f['t_s']
        if f['detection_state'] not in DETECTION:
            bad.append(f'frame {i}: detection {f["detection_state"]}')
        if extra := set(f['permitted_response'])-allowed:
            bad.append(f'frame {i}: response {sorted(extra)} not in the hazard row')
        if not math.isclose(f['time_to_impact_s'], f['range_m']/speed_m_s(s), rel_tol=1e-9):
            bad.append(f'frame {i}: time to impact')
        m, e = f['target']['mass_kg'], f['energy_j']
        if m['known'] != e['known'] or (m['known'] and not math.isclose(e['value'], impact_energy_j(s, m['value']), rel_tol=1e-9)):
            bad.append(f'frame {i}: energy')
        if any(v['known'] for v in f['vehicle_state'].values()):
            bad.append(f'frame {i}: vehicle state claims a value')
    return bad


if __name__ == '__main__':
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from spec import load
    s, *_ = load(Path(__file__).resolve().parents[2])
    print(json.dumps({'warning_horizon': warning_horizon(s), 'energy_orders': energy_orders(s), 'hazard_classes': hazard_classes()}, indent=1))
