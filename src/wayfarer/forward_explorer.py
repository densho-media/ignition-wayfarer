"""FWD-V2 forward defense explorer (Tale 28 AVA-001..005/008/013, S&E 50 AG-014..AG-016, Eye 45 FD-E12..E15): the data the Ship
Navigator's forward hotspot shows in its three explorer modes, as one rig block. Pure, standard library only. SIMULATION_ONLY: nothing here
is a flight-safety statement, and no number is invented. Values are either owner formulas reproduced from LOCKED inputs (impact energy,
time to range), PROTOTYPE model geometry (named as such), or OPEN.

  OBSERVE         the Eye placement variants (r4 WORKING built, r16/r24 STUDY overlays) and the Crown sector states (display poses)
  DEFENSE_SIM     one scenario: unresolved microdust (AVA-005), the layer ladder of Eye 25!A4 step by step, outcome UNKNOWN
  DAMAGE_REPAIR   jammed and closed Eye lids, a degraded Crown bay; repair rates OPEN

    python3 src/wayfarer/forward_explorer.py        # print the block
"""
import math
import eye_placement
import forward_scenario as fsc
import forward_shield as fsh
from forward_scenario import speed_m_s, gamma, impact_energy_j, time_to_range_s

CONTRACT = 'WF_FORWARD_EXPLORER'
VERSION = 1
MODES = ('OBSERVE', 'DEFENSE_SIM', 'DAMAGE_REPAIR')
CROWN_STATES = (('STOWED', 'COAST'), ('PREPARED', 'CROWN_PREPARED'), ('ENGAGED', 'CROWN_ENGAGED'), ('RECOVERING', 'CROWN_RECOVERING'),
                ('DEGRADED', 'CROWN_DEGRADED'))
DAMAGE_STATES = ('EYE_F1_JAMMED', 'EYE_SHUTTERS_CLOSED', 'CROWN_DEGRADED')
REPLAY_STEP_S = 2.0          # IMPLEMENTATION: display seconds per scenario step
GRAIN_PATH = dict(radius_m=20.0, azimuth_deg=200.0, ahead_m=60.0)   # PROTOTYPE display path of the illustrative grain, off the Lance axis


def ref(source, rng, status):
    return {'source_ref': source, 'range': rng, 'source_status': status}


def eye_variants(s):
    out = []
    for v in eye_placement.screens(s):
        st = v['structure']; o = v['optics']; built = math.isclose(v['radius_m'], s['forward_defense']['eye_wells']['centre_radius_m'])
        well_r = s['forward_defense']['eye_wells']['diameter_m']/2
        out.append({'radius_m': v['radius_m'], 'status': v['status'], 'built': built,
                    'label': ('r%g m · WORKING, built' if built else 'r%g m · STUDY overlay, not built') % v['radius_m'],
                    'wells': [{'label': f['label'], 'y': f['y'], 'z': f['z'], 'x': f['local_face_x'], 'radius_m': well_r} for f in v['facets']],
                    'findings': [
                        {'label': 'geometric baseline opposite / adjacent', 'text': f"{v['separation']['diagonal_m']:g} / {v['separation']['adjacent_m']:g} m", 'status': 'DERIVED (FD-A03)'},
                        {'label': 'B_array', 'text': f"{v['separation']['b_array_m']:g} m, r4 calibration input only", 'status': 'WORKING'},
                        {'label': 'coherent baseline', 'text': 'not established', 'status': 'OPEN'},
                        {'label': 'outer port', 'text': 'radius 2.25 m, diameter 4.50 m', 'status': 'WORKING (FD-A04)'},
                        {'label': 'truss spoke margin', 'text': f"{st['spoke_m']:+g} m", 'status': 'PROTOTYPE layout'},
                        {'label': 'truss rings crossed', 'text': ', '.join(f'{x:g} m' for x in st['truss_rings_crossed']) or 'none', 'status': 'PROTOTYPE layout'},
                        {'label': 'Lance seen from boresight', 'text': f"{o['lance_clear_deg']:g} deg ({'inside' if o['lance_inside_unvignetted'] else 'outside'} the clear well field)", 'status': 'DERIVED geometry'},
                        {'label': 'support', 'text': st['support'], 'status': 'PROTOTYPE' if built else 'OPEN'},
                        {'label': 'service', 'text': st['service'], 'status': 'PROTOTYPE' if built else 'OPEN'},
                        {'label': 'field of view', 'text': 'not established', 'status': 'OPEN'}]})
    return out


def crown_states(s):
    """The AG-008 sector states as the display poses the runtime bakes: per state the pose, its control values and every bay's state."""
    out = []
    for name, pose in CROWN_STATES:
        values = fsh.configuration_state(s, pose) if pose in s['configuration'] else fsh.display_pose(s, pose)
        out.append({'state': name, 'pose': pose, 'bays': [r['state'] for r in fsh.crown_pose(s, values)],
                     'controls': {k: float(values[k]) for k in ('crown_prepare', 'crown_engage', 'crown_point', 'crown_azimuth', 'crown_fault')}})
    c = fsh.crown(s)
    marks = [[c['xc'], c['stowed_r']*math.cos(b['azimuth']), c['stowed_r']*math.sin(b['azimuth'])] for b in c['bays']]   # stowed carriage centres
    return {'states': out, 'bay_count': len(c['bays']), 'bay_marks': marks, 'azimuth_rule': 'bay k at 30 k degrees from +Y toward +Z; poses face 45 degrees (bays 1-4)',
            'status': 'PROTOTYPE display poses (AG-008); range, power, heat and effectiveness OPEN', 'head_max_deg': fsh.prototype(s)['crown_head_max_deg'],
            'source': ref('fwd5_crown', '15_MODEL_INTERFACES!A49:I49', 'WORKING')}


def damage(s):
    text = {'EYE_F1_JAMMED': 'F1 eyelid jammed part open: F1 is exposed and cannot close; the other three facets keep observing.',
            'EYE_SHUTTERS_CLOSED': 'All four eyelids closed: the facets are protected and the EYE is blind forward.',
            'CROWN_DEGRADED': 'Bay 2 degraded: shutter jammed half open, carriage stowed; three facing bays remain.'}
    return {'states': [{'pose': k, 'text': text[k]} for k in DAMAGE_STATES],
            'repair': [{'label': 'microrepair', 'text': 'local self-seal after damage, not extra impact absorption', 'status': 'WORKING', **ref('eye_brow_rules', '40_BROW_SHIELD!A23', 'WORKING')},
                       {'label': 'repair rates, feedstock', 'text': 'not established', 'status': 'OPEN'},
                       {'label': 'major damage', 'text': 'panel or cartridge replacement by crawler, drone or crew', 'status': 'WORKING'},
                       {'label': 'eyelid and window swap', 'text': 'mechanism and erosion life not designed (OD-020)', 'status': 'OPEN'}]}


def microdust(s, sources=None):
    """AVA-005 unresolved microdust, one off-axis grain on a PROTOTYPE display path through the Eye 25!A4 ladder. Every step carries its owner
    status; the outcome is UNKNOWN (no flux, no layer performance, no survival evidence at 0.016 c)."""
    st = fsh.stations(s); layer = fsh.disruptor_layers(s)[0]; r = GRAIN_PATH['radius_m']; a = math.radians(GRAIN_PATH['azimuth_deg'])
    face = fsh.face_x_at(s, r); y, z = r*math.cos(a), r*math.sin(a); v = speed_m_s(s)
    x_layer = fsh.layer_x(s, layer, r)[1]; x0 = face+GRAIN_PATH['ahead_m']
    steps = [
        dict(id='EYE_WARNING', x=x0, title='EYE / Seraph: statistical warning only',
             text='Unresolved grains are not tracked one by one; the EYE gives a statistical environment warning.', status='LOCKED',
             **ref('eye_brow_rules', '40_BROW_SHIELD!A11', 'LOCKED'), open='detection range for unresolved dust'),
        dict(id='CROWN_NOT_ENGAGED', x=x0, title='Crown: not engaged',
             text='Crown optics act on resolvable local targets only; an untracked grain cannot be shot individually.', status='LOCKED doctrine / WORKING mechanism',
             **ref('eye_microdust_response', '25_HAZARD_RESPONSE!A4:G4', 'WORKING'), open=''),
        dict(id='DUSTBREAK_VEIL', x=x0, title='Dustbreak Veil: hypothesis',
             text='A pre-positioned sacrificial cloud far ahead, where mission state permits; drawn here as a hypothesis, not to scale.', status='WORKING direction',
             **ref('eye_dustbreak_veil', '40_BROW_SHIELD!A34', 'WORKING'), open='cloud density, distance, dispersion and EYE interference'),
        dict(id='DISRUPTOR_LAYER', x=x_layer, title='Disruptor layer: full-area sacrificial bumper',
             text='The grain meets the full-area layer ahead of the Brow; vaporizing it does not remove its momentum or energy.', status='WORKING existence',
             **ref('eye_brow_rules', '40_BROW_SHIELD!A33', 'WORKING'), open='material, thickness, count, spacing; no validation at 0.016 c'),
        dict(id='LANCE_IONIZATION', x=x_layer, title='Dust Lance: central axis only',
             text='The Lance and its ionization structures work on the central axis; this off-axis grain does not pass it.', status='WORKING / BASELINE direction',
             **ref('eye_brow_rules', '40_BROW_SHIELD!A21', 'WORKING'), open='Lance material, taper and tip life'),
        dict(id='MAGNETIC_DIVERSION', x=x_layer, title='Field: charged ejecta only',
             text='A pre-energized field can divert charged ejecta; neutral dust is not diverted.', status='LOCKED boundary',
             **ref('eye_brow_rules', '40_BROW_SHIELD!A22', 'LOCKED'), open='field topology, strength and power'),
        dict(id='BROW', x=face, title='Brow: residual impacts',
             text='The Brow takes what the layers leave; microrepair after damage is maintenance, not extra impact absorption.', status='LOCKED role',
             **ref('eye_brow_rules', '40_BROW_SHIELD!A11', 'LOCKED'), open='shield architecture and stack'),
    ]
    span = x0-face
    # AG-014: one contract frame per step, on the grain's own clock (physical seconds from the start of the display path).
    frames = [fsc.frame(s, (x0-st['x'])/v, st['x']-face, 'MICRODUST', 'STATISTICAL', [fsc.PASSIVE], note=st['id']) for st in steps]
    state = fsc.scenario(s, sources, 'MICRODUST_UNRESOLVED', 'MICRODUST', frames, 'Tale 28 AVA-005', span/v, REPLAY_STEP_S*len(steps),
                         unknown=('dust flux', 'grain size distribution', 'detection range for unresolved dust', 'veil and layer performance',
                                  'survival at 0.016 c')) if sources else None
    return {'id': 'MICRODUST_UNRESOLVED', 'status': 'SIMULATION_ONLY / PHYSICS OPEN', 'tale': 'Tale 28 AVA-005', 'grain_path': {**GRAIN_PATH, 'status': 'PROTOTYPE display'},
            'start': [x0, y, z], 'end': [face, y, z], 'steps': steps, 'step_display_s': REPLAY_STEP_S,
            'physical': {'speed_m_s': v, 'speed_status': 'LOCKED 0.016 c (target_speed)', 'path_m': span, 'path_time_s': span/v,
                         'time_expansion': REPLAY_STEP_S*len(steps)/(span/v), 'per_metre_s': 1/v,
                         'energy_1ug_j': impact_energy_j(s, 1e-9), 'energy_source': ref('eye_impact_scale', '40_BROW_SHIELD!F4', 'DERIVED'),
                         'time_1000km_s': time_to_range_s(s, 1e6), 'time_source': ref('eye_scaling_limits', '35_SCALING_LIMITS!A3:H9', 'DERIVED')},
            'unknown': ['dust flux', 'grain size distribution', 'detection range for unresolved dust', 'veil and layer performance', 'survival at 0.016 c'],
            'outcome': 'UNKNOWN: survival is not established; no flight-safety statement (AVA-005, FD-E09, FD-E16)', 'state': state}


def contract(s, sources):
    return {'contract': CONTRACT, 'version': VERSION, 'status': 'SIMULATION_ONLY / PROTOTYPE', 'modes': list(MODES),
            'remote_view_only': 'remote observation; never EVA or flight permission (AVA-001, NAV-014)',
            'eye_variants': eye_variants(s), 'crown': crown_states(s), 'damage': damage(s), 'scenario': microdust(s, sources),
            'reference': {'warning_horizon': fsc.warning_horizon(s), 'energy_orders': fsc.energy_orders(s), 'hazard_classes': fsc.hazard_classes(),
                          'responses': list(fsc.RESPONSES), 'detection_states': list(fsc.DETECTION)}}


if __name__ == '__main__':
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from spec import load
    s, src, *_ = load(Path(__file__).resolve().parents[2])
    print(json.dumps(contract(s, src), indent=1))
