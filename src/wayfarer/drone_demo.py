"""DRONE-001 L3 demonstration (S&E 54 DGT-013/014, Tale 29 DN-11, Eye 46 EYS-DR-10): one exterior spine utility crawler (DR-EVA-03) on its
DS-13 track, as a scenario the Ship Navigator plays. Pure, standard library only.

WF_DRONE_SCENARIO v1: a nominal service run (dock, precheck, release, traverse, inspect, tool, return, dock, charge) and three fault branches
(power loss, rail jam, lost link). Every frame names the crawler's place on the track (X on the casing), its state, the operating rule it
follows (53 DOP-xx) and what stays OPEN. Time is explainer time only: no traverse speed, energy, mass, torque or latch rating exists in the
owner rows, so none is held; validate() rejects them. The run is SIMULATION ONLY, not an operations procedure or a certification.

    python3 src/wayfarer/drone_demo.py
"""
import math

import drone_fleet as df
import survival_fit

CONTRACT = 'WF_DRONE_SCENARIO'
VERSION = 1
STEP_DISPLAY_S = 2.0          # explainer seconds per frame (display only)
STATUS = 'SIMULATION ONLY / STUDY FLEET (S&E 51-54 HOLD) / NOT CERTIFIED'
FORBIDDEN = {'speed_m_s', 'velocity_m_s', 'duration_s', 'mass_kg', 'power_W', 'energy_Wh', 'energy_J', 'torque_N_m', 'latch_load_N', 'certified',
             'probability'}
STATES = ('DOCKED_CHARGING', 'PRECHECK', 'RELEASE', 'TRAVERSE', 'INSPECT', 'TOOL', 'RETURN', 'DOCK', 'CHARGE', 'SAFE_HOLD', 'BRAKED', 'RETRIEVAL',
          'RETREAT', 'PARKED_LOCKED')
# 53 DOP-01..05 by ship configuration: what the crawler may do in it (PROPOSAL rows, never a release).
CONFIG_GATES = {
    'COAST': ('PERMITTED IF LOCALLY SAFE', 'DOP-01: outside anchored inspection if locally safe; needs verified free volume and thermal / dust state (OPEN, assumed here)'),
    'DOCKED': ('PERMITTED IF LOCALLY SAFE', 'DOP-05: inspection, module swap, recharge; no radiator or core touch while post-shutdown heat remains'),
    'LOW_THRUST': ('HOLD', 'DOP-02: external attached inspection only where separately certified; no certification exists'),
    'HIGH_POWER': ('LOCKED', 'DOP-03: robots parked and latched; dock latch at 1.5 g axial (rating OPEN, DGT-004)'),
    'EVA': ('HOLD', 'DOP-04: pre-EVA survey and tool handoff only with the crew EVA leader; FLIGHT_EVA HOLD'),
}


def _open(reason):
    return {'known': False, 'status': 'OPEN', 'reason': reason}


def target(s):
    """Inspection target: the foot of the SP-53 lasercom mast (Eye A25 terminal, existing exterior hardware) seen from the track, and the rail
    anchor beside it for the tool step."""
    mast = next(q for q in survival_fit.exterior(s) if q['name'] == 'Survival_Lasercom_Mast')
    foot = mast['points'][0]; r = df.spine_route(s)
    return {'name': 'Survival_Lasercom_Mast', 'label': 'SP-53 lasercom mast foot (Eye A25)', 'point_m': list(foot), 'x_m': foot[0],
            'stand_x_m': foot[0]+0.6, 'gap_m': math.dist(foot, (foot[0], r['surface_r'](foot[0])*math.cos(r['azimuth']), r['surface_r'](foot[0])*math.sin(r['azimuth'])))}


def _f(state, x, title, text, rule, open_items=(), unit='DR-EVA-03-U03', extra=None):
    return dict({'state': state, 'unit': unit, 'x_m': round(x, 4), 'title': title, 'text': text, 'rule': rule, 'open': list(open_items)}, **(extra or {}))


def scenario(s):
    r = df.spine_route(s); tg = target(s); home = r['dock_x'][2]; mid = r['dock_x'][1]; at = tg['stand_x_m']
    half = (home+at)/2
    nominal = [
        _f('DOCKED_CHARGING', home, 'Docked, charging', 'Latched in the forward spine dock DS-13/3; charge and data through the dock.', 'DOP-12',
           ('dock energy and duty cycle (DOP-12 OPEN)',)),
        _f('PRECHECK', home, 'Precheck', 'Ship configuration, local thermal and dust state, track clear, tool cartridge seated. The run continues only '
           'in COAST or DOCKED with a released cold / clear local state.', 'DOP-01 / DOP-05 / DOP-08', ('blade cold-state release (DGT-007)',)),
        _f('RELEASE', home, 'Release', 'Dock latch opens with positive feedback; the crawler grips the twin rail.', 'DOP-11', ('latch rating (DGT-004)',)),
        _f('TRAVERSE', half, 'Traverse aft', 'Along the stationary casing at 110 deg, between two blades, clear of the 90 deg lasercom mast; the track '
           'never crosses ring A\'s sweep.', 'DOP-01', ('traverse speed', 'radiant view to the blades')),
        _f('INSPECT', at, 'Inspect', f"Camera on the {tg['label']} from {tg['gap_m']:.1f} m; imagery goes to the crew for review. No diagnosis is claimed.",
           'DOP-01 / EYS-DR-05', ('sensor limits',)),
        _f('TOOL', at, 'Tool interaction', 'Shared tool-changer cartridge: positive-latch check of the rail anchor beside the mast.', 'DOP-11 / DGT-012',
           ('fastener standard', 'torque', 'cartridge coupling')),
        _f('RETURN', half, 'Return', 'Back along the same track to the forward dock.', 'DOP-01', ('traverse speed',)),
        _f('DOCK', home, 'Dock', 'Latch closes with positive feedback; the crawler is secured for any configuration change.', 'DOP-03',
           ('latch rating at 1.5 g (DGT-004)',)),
        _f('CHARGE', home, 'Charge', 'Recharge and data offload; robot heat counted in the ship ledger.', 'DOP-12', ('charge energy', 'heat')),
    ]
    stop = (home+at)*0.5+(at-home)*0.15
    faults = [
        {'id': 'POWER_LOSS', 'title': 'Power loss on the track', 'gate': 'DGT-013', 'frames': [
            _f('TRAVERSE', stop, 'Power lost', 'Bus loss mid-traverse.', 'DOP-13'),
            _f('BRAKED', stop, 'Brake set', 'The latching brake sets without power; the unit holds on the rail (safe hold).', 'DOP-13', ('brake rating',)),
            _f('RETRIEVAL', stop, 'Retrieval', 'The mid-dock crawler DR-EVA-03-U02 runs forward, couples and tows the unit home. No crew EVA.', 'DOP-14',
               ('coupling standard', 'tow load'), unit='DR-EVA-03-U02', extra={'helper_from_x_m': round(mid, 4)}),
            _f('DOCK', home, 'Recovered', 'Both units docked; the fault goes to the repair log.', 'DOP-14 / DOP-15')]},
        {'id': 'RAIL_JAM', 'title': 'Rail jam', 'gate': 'DGT-013', 'frames': [
            _f('TRAVERSE', stop, 'Jam', 'A drive wheel binds at a rail joint.', 'DOP-14'),
            _f('SAFE_HOLD', stop, 'Section stopped', 'The track section is stopped and the unit holds; nothing is forced.', 'DOP-06 / DOP-14'),
            _f('RETRIEVAL', stop, 'Second robot survey', 'DR-EVA-03-U02 approaches from the mid dock and images the jam. If it cannot free the unit, '
               'the crew decide; no automatic EVA rescue, and none while the blades are hot.', 'DOP-14', ('stranded-object swept volume',),
               unit='DR-EVA-03-U02', extra={'helper_from_x_m': round(mid, 4)}),
            _f('SAFE_HOLD', stop, 'Awaiting crew decision', 'Unit parked on the rail; the section stays closed to other traffic.', 'DOP-14',
               ('work permit', 'secondary access'))]},
        {'id': 'LOST_LINK', 'title': 'Lost link / Seraph unavailable', 'gate': 'DGT-013', 'frames': [
            _f('INSPECT', at, 'Link lost', 'Telemetry to Seraph and the ship ops console drops during inspection.', 'DOP-13'),
            _f('SAFE_HOLD', at, 'Onboard stop', 'Onboard safety stops the task; no open-loop motion toward people or optics.', 'DOP-13'),
            _f('RETREAT', half, 'Retreat', 'Local sensors only: the unit retreats along the validated track.', 'DOP-13', ('low-power recovery',)),
            _f('DOCK', home, 'Docked, link pending', 'Latched at its validated dock; it waits for the crew service console.', 'DOP-13')]},
    ]
    return {'contract': CONTRACT, 'version': VERSION, 'id': 'DRONE_SPINE_SERVICE_RUN', 'status': STATUS,
            'unit': 'DR-EVA-03-U03', 'class': 'DR-EVA-03', 'station': 'DS-13', 'tale': 'Tale 29 DN-11 (WORKING / OPTIONAL)',
            'source_refs': list(df.SOURCES), 'step_display_s': STEP_DISPLAY_S,
            'time': 'EXPLAINER TIME: no traverse speed, energy or duration exists in the owner rows',
            'track': {'azimuth_deg': round(math.degrees(r['azimuth']), 4), 'x0_m': round(r['x0'], 4), 'x1_m': round(r['x1'], 4),
                      'dock_x_m': [round(x, 4) for x in r['dock_x']], 'surface_r_m': [[round(x, 4), round(r['surface_r'](x), 4)] for x in (r['x0'], r['x1'])],
                      'stop': 'ring A sweep less the keep-out margin (DGT-005)'},
            'target': tg, 'config_gates': {k: {'gate': v[0], 'rule': v[1]} for k, v in CONFIG_GATES.items()},
            'nominal': nominal, 'faults': faults,
            'unknown': ['unit mass', 'power and energy', 'traverse speed', 'latch and brake ratings', 'tool torque', 'thermal release', 'radiant dose'],
            'performance': _open('51-53 hold no performance; every value OPEN'),
            'not': ['not a playable EVA', 'not an operations procedure', 'not engineering validation (54 gates HOLD)']}


def _keys(node, out):
    if isinstance(node, dict):
        for k, v in node.items():
            out.add(k); _keys(v, out)
    elif isinstance(node, list):
        for v in node:
            _keys(v, out)
    return out


def validate(s, sc):
    """Problems with a scenario (empty when it holds the contract): known states, frames on the track, no invented performance keys."""
    bad = []
    if (sc.get('contract'), sc.get('version')) != (CONTRACT, VERSION):
        bad.append('contract/version')
    if hits := FORBIDDEN & _keys(sc, set()):
        bad.append(f'forbidden keys {sorted(hits)}')
    if 'SIMULATION ONLY' not in sc.get('status', ''):
        bad.append('status must say SIMULATION ONLY')
    tr = sc['track']
    frames = sc['nominal']+[f for fl in sc['faults'] for f in fl['frames']]
    for f in frames:
        if f['state'] not in STATES:
            bad.append(f"{f['title']}: state {f['state']}")
        if not tr['x0_m']-1e-6 <= f['x_m'] <= tr['x1_m']+1e-6:
            bad.append(f"{f['title']}: X {f['x_m']} off the track")
    if [f['state'] for f in sc['nominal']][0] != 'DOCKED_CHARGING' or sc['nominal'][-1]['state'] != 'CHARGE':
        bad.append('nominal run must start docked and end charging')
    if len(sc['faults']) < 3:
        bad.append('DGT-013 asks for at least three fault replays')
    for fl in sc['faults']:
        if fl['frames'][-1]['state'] not in ('DOCK', 'SAFE_HOLD', 'PARKED_LOCKED'):
            bad.append(f"{fl['id']}: does not end in a safe state")
    if set(sc['config_gates']) != set(CONFIG_GATES) or sc['config_gates']['HIGH_POWER']['gate'] != 'LOCKED':
        bad.append('configuration gates')
    return bad


def contract(s):
    sc = scenario(s); bad = validate(s, sc)
    assert not bad, bad
    return sc


if __name__ == '__main__':
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import spec
    s, *_ = spec.load()
    sc = scenario(s); bad = validate(s, sc)
    print(json.dumps({'target': sc['target'], 'track': sc['track'], 'nominal': [(f['state'], f['x_m']) for f in sc['nominal']],
                      'faults': {fl['id']: [(f['state'], f['x_m']) for f in fl['frames']] for fl in sc['faults']}, 'problems': bad}, indent=1))
    sys.exit(1 if bad else 0)
