"""FUT-004 First Ignition timeline: the induction, then the First Ignition burn, as keyed display channels. Standard library only.

[flight_timeline] orders the phases. The induction's steps come from [induction].sequence (IND-001 4.1) and are not restated. Each phase holds
a buildable configuration or is part of a transition between two; its rotor and drive key segments re-time the existing PROTOTYPE key tables
(rotor_interface WF_RING_STOP_LOCK, drive_manifold WF_DRIVE_STARTUP / WF_DRIVE_SHUTDOWN). The burn plays the sheet-computed route
([flight_timeline].route, imported from 23_ROUTE_FRAMES by tools/route_import.py) one row per frame; nothing here computes kinematics (NAV-027,
26_BLENDER_CONTRACT C-001/C-010). Only the burn and the spin-up (08!C27) have physical durations; every other phase is not to scale. A channel is one control property (bound to the vehicle control that shows it) or a label, keyed as
[frame, value, interp]; interp names the curve from that key to the next. Every channel carries its class:
SOURCED > DERIVED > PRESENTATION, the lowest of its inputs, and its authority: presentation or sheet-import. Nothing here is physics the
owner has not given: the unknown block lists the inputs a physical timeline still needs, and the checks keep the rotor and thrust rules
(08!A47, MEC-011) and the radiator order (07!A39). FRM-002-2026-10-10 (15!A125, refining FLIGHT-FRAMES 15!A117): the
time-tagged channels and the phase/event streams Sheets will release ([flight_timeline].frames, tools/frames_import.py) are bound as
frames.* channels, null until released; the presentation channels that
show those quantities say which they stand for and their status. The 1D route stays DIAGNOSTIC, never heliocentric (15!I117).
"""
from pathlib import Path
import argparse
import bisect
import json
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import functools
import rotor_interface
import drive_manifold
import forward_shield
import radiator_health

SCHEMA = 'WF_FLIGHT_TIMELINE'
DURATIONS = ('UNSCALED', 'OPEN', 'SOURCED', 'IMPORTED')
CLASSES = {'SOURCED': 'An owner value or rule as stated, or a row of the sheet-computed route as imported.',
           'DERIVED': 'Computed from sourced values by a shared formula.',
           'PRESENTATION': 'Display timing or shape chosen for the animation: endpoints follow the sourced configurations, the instants and curves do not.',
           'UNKNOWN': 'Declared by FRM-002-2026-10-10 (FLIGHT-FRAMES 15!A117) and not released by Sheets: no keys, the value is null, never a number (15!H125).'}
ROTOR_SEGMENTS = ('brake', 'lock', 'stop_lock', 'unlock', 'spin_up', 'unlock_spin_up')
DRIVE_SEGMENTS = ('startup', 'burn', 'shutdown')
LINEAR = {'rotor': {'spin_fraction'}, 'drive': set(drive_manifold.PROPS) | {'thrust_level'}}   # the drive actions are LINEAR keys only
EPS = 1e-9


def table(s):
    return s['flight_timeline']


def path_value(s, path):
    node = s
    for k in path.split('.'):
        node = node[k]
    return node


# ---------- kinematics ----------------------------------------------------------------------------------------------

@functools.lru_cache(maxsize=4)
def _route(path):
    return json.loads(Path(path).read_text())


def route(s):
    """The imported route ([flight_timeline].route; tools/route_import.py, gated on 25_ROUTE_VALIDATION rows 2:13)."""
    return _route(str(ROOT/table(s)['route']))


# Imported 23_ROUTE_FRAMES columns behind each kinematics channel.
ROUTE_COLUMNS = {'acceleration_g': 'accel_g', 'speed_c': 'speed_fraction_c', 'distance_AU': 'distance_traveled_AU', 'burn_elapsed_s': 'mission_t_s'}


def route_rows(s):
    """{channel: [value per route frame]} in route frame order."""
    r = route(s); col = {name: r['columns'].index(c) for name, c in ROUTE_COLUMNS.items()}
    return {name: [row[i] for row in r['frames']] for name, i in col.items()}


def frames(s):
    """The FRM-002-2026-10-10 contract (time-tagged channels and phase/event streams) ([flight_timeline].frames; tools/frames_import.py): UNKNOWN channels carry no values."""
    return _route(str(ROOT/table(s)['frames']))


def kinematics(s):
    """The burn as the owner's sheet computed it: the last imported row and the scenario labels (no computation here)."""
    r = route(s); last = dict(zip(r['columns'], r['frames'][-1]))
    return {'scenario_id': r['scenario_id'], 'scenario_status': r['scenario_status'], 'frame_id': r['frame_id'], 'route_version': r['route_version'],
            'route_frames': r['frame_count'], 'legend': r['legend'], 'target_speed_c': last['speed_fraction_c'], 'max_accel_g': last['accel_g'],
            'burn_time_s': last['mission_t_s'], 'burn_duration_d': last['mission_t_days'], 'distance_m': last['local_x_m'],
            'distance_AU': last['distance_traveled_AU'], 'day_s': r['model']['day_s']['value'], 'class': 'SOURCED', 'status': 'DIAGNOSTIC', 'source_ref': 'route_frames',
            'basis': f"23_ROUTE_FRAMES rows 1..{r['frame_count']} ({r['scenario_id']}, {r['scenario_status']}), one row per timeline frame of the burn, "
                     'linear between them (26_BLENDER_CONTRACT C-003/C-010); computed by the owner\'s sheet (NAV-027), Newtonian V1.'}


# ---------- phases --------------------------------------------------------------------------------------------------

def phases(s):
    """Ordered phases with their frame spans [frame_start, frame_end]; an induction entry takes its step's state or transition and title."""
    seq = {st['key']: st for st in s['induction']['sequence']}; out = []; frame = 1
    for entry in table(s)['phases']['list']:
        p = dict(entry)
        if 'induction' in p:
            st = seq[p['induction']]
            p = {'id': 'IND_'+st['key'].upper(), 'title': st['title'], **({'configuration': st['state']} if 'state' in st else {'from': st['from'], 'to': st['to']}), **p}
        p.setdefault('duration', 'UNSCALED')
        p['frame_start'] = frame; p['frame_end'] = frame+p['frames']; frame = p['frame_end']
        out.append(p)
    return out


def duration_s(s, p):
    if p['duration'] == 'IMPORTED':
        return kinematics(s)['burn_time_s']
    if p['duration'] == 'SOURCED':
        return float(path_value(s, p['value_ref']))
    return None


def display(s, p):
    """How a phase reads on screen: its physical duration, seconds per frame, or why it is not to scale."""
    d = duration_s(s, p)
    if d is not None:
        return {'duration_s': d, 'seconds_per_frame': d/p['frames'], 'scale': 'LINEAR', 'label': f"1 frame = {d/p['frames']:.6g} s ({p['duration']})"}
    why = f"duration OPEN ({p['evidence_ref']})" if p['duration'] == 'OPEN' else 'a hold with no duration'
    return {'duration_s': None, 'seconds_per_frame': None, 'scale': 'NOT_TO_SCALE', 'label': f'NOT TO SCALE: {why}'}


def shown(p):
    """The configuration whose forward-defense, radiator and EYE states a phase shows."""
    return p.get('configuration') or p['display']


# ---------- key segments --------------------------------------------------------------------------------------------

def rotor_segment(s, name):
    """(fraction of the phase, ROTOR_n_MECH_CTRL state) keys. brake, lock and stop_lock re-time WF_RING_STOP_LOCK; unlock runs it backwards
    (ring-stop locks out, levitate off the touchdown cartridges, index lock out); spin_up starts the hub motor and drives spin 0 -> 1."""
    st = s['rotor_interface']['stop_lock_frames']
    keys = rotor_interface.actions(s)['WF_RING_STOP_LOCK']['slots'][rotor_interface.control(rotor_interface.rotors(s)[0]['index'])]
    R, L = rotor_interface.ROTATING, rotor_interface.STOPPED_LOCKED

    def part(f0, f1):
        return [((f-f0)/(f1-f0), dict(v)) for f, v in keys if f0 <= f <= f1]
    stopped = {**R, 'motor_driving': 0.0, 'spin_fraction': 0.0}
    levitated = {**stopped, 'index_lock_engaged': 1.0}
    set_down = {**levitated, 'levitation_active': 0.0, 'touchdown_contact': 1.0}
    unlock = [(0.0, dict(L)), (1/3, set_down), (2/3, levitated), (1.0, stopped)]
    spin = [(0.0, stopped), (.1, {**R, 'spin_fraction': 0.0}), (1.0, dict(R))]
    return {'brake': part(1, st['stopped']), 'lock': part(st['stopped'], st['end']), 'stop_lock': part(1, st['end']), 'unlock': unlock, 'spin_up': spin,
            'unlock_spin_up': [(.4*f, v) for f, v in unlock]+[(.4+.6*f, v) for f, v in spin[1:]]}[name]


def drive_segment(s, name, p):
    """(fraction, DRIVE_MANIFOLD_CTRL state) keys. startup and shutdown re-time the drive actions; burn holds the nominal drive and ramps the
    display throttle with the acceleration (a / the highest drive-ACTIVE max_accel_g, drive_manifold.thrust_level)."""
    acts = drive_manifold.actions(s)

    def retime(action, level):
        # The display throttle takes the new level after the first key (the drive shows no output there), so the segment joins the state before it.
        keys = acts[action]['keys']; f0, f1 = keys[0][0], keys[-1][0]
        return [((f-f0)/(f1-f0), {**v, 'thrust_level': level if n else 1.0}) for n, (f, v) in enumerate(keys)]
    if name == 'burn':
        n = drive_manifold.nominal(s)
        return [(0.0, {**n, 'thrust_level': 0.0}), (1.0, {**n, 'thrust_level': drive_manifold.thrust_level(s, p['configuration'])})]
    return {'startup': lambda: retime('WF_DRIVE_STARTUP', 0.0), 'shutdown': lambda: retime('WF_DRIVE_SHUTDOWN', 1.0)}[name]()


def same(a, b):
    return a.keys() == b.keys() and all(abs(a[k]-b[k]) <= EPS for k in a)


def track(s, ps, kind, configured, segment):
    """[(frame, state)] for one control: each phase plays its segment from the state before it; a hold must end at its configuration's state."""
    first = ps[0].get('configuration') or ps[0]['from']; state = configured(first); keys = [(ps[0]['frame_start'], state)]
    for p in ps:
        name = p.get(kind)
        if name:
            seg = segment(name, p)
            if not same(seg[0][1], state):
                raise ValueError(f"flight_timeline {p['id']}: the {kind} segment {name} does not start from the state before it")
            frames = [p['frame_start']+round(f*p['frames']) for f, _ in seg]
            if len(set(frames)) < len(frames):
                raise ValueError(f"flight_timeline {p['id']}: {p['frames']} frames are too few for the {kind} segment {name}")
            keys += list(zip(frames, (v for _, v in seg))); state = seg[-1][1]
        if 'configuration' in p and not same(state, configured(p['configuration'])):
            raise ValueError(f"flight_timeline {p['id']}: the {kind} state does not reach {p['configuration']}")
    return keys


def channel_keys(track_keys, prop, linear):
    """Per-property keys from a state track, without repeats (a LINEAR key stays where a ramp starts or ends)."""
    raw = [[f, v[prop], 'LINEAR' if linear else 'CONSTANT'] for f, v in track_keys]
    out = []
    for k in raw:
        if out and out[-1][0] == k[0]:
            out[-1] = k
        else:
            out.append(k)
    return compress(out)


def compress(keys):
    out = []
    for i, k in enumerate(keys):
        prev = out[-1][1] if out else None; nxt = keys[i+1][1] if i+1 < len(keys) else None
        if out and k[1] == prev and (k[2] == 'CONSTANT' or nxt is None or nxt == k[1]):
            continue
        out.append(k)
    return out


def constant(ps, value):
    return compress([[p['frame_start'], value(p), 'CONSTANT'] for p in ps])


# ---------- channels ------------------------------------------------------------------------------------------------

def bindings(s):
    return {'rotor': [rotor_interface.control(r['index']) for r in rotor_interface.rotors(s)], 'drive': [drive_manifold.CONTROL],
            'forward_defense': [forward_shield.CONTROL], 'radiator': [radiator_health.CONTROL]}


def thermal_value(s, p):
    if 'thermal' in p:
        return radiator_health.step_value(s, radiator_health.steps(s).index(p['thermal']))
    return radiator_health.configuration_state(s, shown(p))['thermal_state']


def channels(s, ps=None):
    ps = ps or phases(s); b = bindings(s); k = kinematics(s); out = {}
    burn = next(p for p in ps if p.get('drive') == 'burn'); f0, f1 = burn['frame_start'], burn['frame_end']
    rot = track(s, ps, 'rotor', lambda c: rotor_interface.configuration_state(s, c), lambda n, p: rotor_segment(s, n))
    drv = track(s, ps, 'drive', lambda c: drive_manifold.configuration_state(s, c), lambda n, p: drive_segment(s, n, p))
    rotor_basis = 'Configuration endpoints from 11_OPERATING_CONFIGS and 08!A47; transition keys re-time WF_RING_STOP_LOCK (PROTOTYPE). Both rotors take the same keys (paired, 08!H27).'
    for prop in rotor_interface.PROPS:
        out[f'rotor.{prop}'] = {'class': 'PRESENTATION', 'basis': rotor_basis, 'unit': 'normalized', 'binding': {'controls': b['rotor'], 'property': prop},
                                'keys': channel_keys(rot, prop, prop in LINEAR['rotor'])}
    # FUT-007: the ring turn integrates the spin channel (rotor_interface.spin_turned), so the rings never reverse and rest at their index.
    spin = [(f, v) for f, v, _ in out['rotor.spin_fraction']['keys']]
    turned = rotor_interface.spin_turned(s, spin+([(ps[-1]['frame_end'], spin[-1][1])] if spin[-1][0] < ps[-1]['frame_end'] else []))
    out['rotor.spin_turned'] = {'class': 'PRESENTATION', 'unit': 'frames at full speed', 'binding': {'controls': b['rotor'], 'property': 'spin_turned'},
                                'basis': 'Integral of spin_fraction, scaled between two rests to whole turns so a ring rests at its index angle (display rate; spin-down law OPEN, S6).',
                                'keys': [[f, v, 'LINEAR'] for f, v in turned]}
    out['rotor.spin_integrated'] = {'class': 'PRESENTATION', 'unit': 'flag', 'binding': {'controls': b['rotor'], 'property': 'spin_integrated'},
                                    'basis': 'The Rotor_n driver reads spin_turned throughout the timeline.', 'keys': [[ps[0]['frame_start'], 1.0, 'CONSTANT']]}
    for prop in [*drive_manifold.PROPS, 'thrust_level']:
        derived_ = prop == 'thrust_level'
        out[f'drive.{prop}'] = {'class': 'DERIVED' if derived_ else 'PRESENTATION', 'unit': 'normalized', 'binding': {'controls': b['drive'], 'property': prop},
                                'basis': 'Display throttle a / 1.5 g during the burn (drive_manifold.thrust_level); exhaust length only, exhaust velocity and mass flow OPEN (S3).' if derived_ else
                                         'Drive display re-timed from WF_DRIVE_STARTUP / WF_DRIVE_SHUTDOWN (PROTOTYPE timing; durations OPEN, S7).',
                                'keys': channel_keys(drv, prop, prop in LINEAR['drive'])}
    for prop in forward_shield.PROPS:
        out[f'forward_defense.{prop}'] = {'class': 'PRESENTATION', 'unit': 'normalized', 'binding': {'controls': b['forward_defense'], 'property': prop},
                                          'basis': 'forward_shield.configuration_state of the configuration a phase shows (field_states, Q4); the switching instant is a display choice.',
                                          'keys': constant(ps, lambda p: forward_shield.configuration_state(s, shown(p))[prop])}
    out['radiator.thermal_state'] = {'class': 'PRESENTATION', 'unit': 'normalized', 'binding': {'controls': b['radiator'], 'property': 'thermal_state'},
                                     'basis': 'radiator_health presets (PROTOTYPE) and the 07!A39 step order; the radiators are fixed in every mode, so no geometry channel exists (15!A10).',
                                     'keys': constant(ps, lambda p: thermal_value(s, p))}
    for prop in [k for k in radiator_health.PROPS if k != 'thermal_state']:
        out[f'radiator.{prop}'] = {'class': 'PRESENTATION', 'unit': 'normalized', 'binding': {'controls': b['radiator'], 'property': prop},
                                   'basis': 'radiator_health preset of the configuration a phase shows (no preset isolates a cell).',
                                   'keys': constant(ps, lambda p: radiator_health.configuration_state(s, shown(p))[prop])}
    out['eye.mode'] = {'class': 'PRESENTATION', 'unit': 'label', 'binding': None, 'basis': 'eye_mode of the configuration a phase shows (eye_config_modes); the switching instant is a display choice.',
                       'keys': constant(ps, lambda p: s['configuration'][shown(p)]['eye_mode'])}
    out['configuration'] = {'class': 'PRESENTATION', 'unit': 'label', 'binding': None, 'basis': 'The buildable configuration a phase holds, or the transition it is part of (11_OPERATING_CONFIGS).',
                            'keys': constant(ps, lambda p: p.get('configuration') or f"{p['from']} -> {p['to']}")}
    # Kinematics: zero in the departure rest frame before ignition, one imported route row per burn frame (C-010), constant speed after it.
    # After the burn the distance grows by v times the coast time, which is OPEN, so it is only a lower bound.
    rows = route_rows(s)
    for name, unit in (('acceleration_g', 'g'), ('speed_c', 'c'), ('distance_AU', 'AU'), ('burn_elapsed_s', 's')):
        keys = [[1, 0.0, 'CONSTANT']] if f0 > 1 else []
        keys += [[f0+n, v, 'LINEAR'] for n, v in enumerate(rows[name])]
        keys[-1][2] = 'CONSTANT'
        if name == 'acceleration_g':
            keys.append([f1+1, 0.0, 'CONSTANT'])
        out[f'kinematics.{name}'] = {'class': 'SOURCED', 'status': 'DIAGNOSTIC', 'legend': k['legend'], 'unit': unit, 'binding': None, 'basis': k['basis'], 'source_ref': k['source_ref'],
                                     'route_column': ROUTE_COLUMNS[name], 'keys': keys, **({'lower_bound_after_frame': f1} if name == 'distance_AU' else {})}
    return bind_frames(s, out, f0, f1)


def bind_frames(s, out, f0, f1):
    """FRM-002-2026-10-10 (15!A125; FLIGHT-FRAMES 15!A117): every channel names its authority; each declared continuous channel becomes
    frames.<id>: a released one keys only its samples that carry a 23_ROUTE_FRAMES frame, CONSTANT for that frame and null on the next
    unsampled frame (C-010 direct lookup: nothing between samples or outside the burn, no resampling of mission time); an UNKNOWN one has no
    keys. Each phase/event stream (C-018) becomes frames.<id> with its rows and no keys: untimed rows stay unplaced. The presentation
    channels that show a quantity list it with its status (superseded once all are released)."""
    fr = frames(s)
    for name, c in out.items():
        c['authority'] = 'sheet-import' if name.startswith('kinematics.') else 'presentation'
    for cid, c in fr['channels'].items():
        keys = []
        if c['values'] is not None:
            placed = sorted((f, v) for f, v in zip(c['frame'], c['values']) if f is not None)
            for n, (f, v) in enumerate(placed):
                keys.append([f0+f-1, v, 'CONSTANT'])
                if n+1 == len(placed) or placed[n+1][0] != f+1:
                    keys.append([f0+f, None, 'CONSTANT'])
        out[f'frames.{cid}'] = {'class': 'UNKNOWN' if c['values'] is None else 'SOURCED', 'authority': 'sheet-import', 'status': c['status'],
                                'contract': fr['contract'], 'unit': c['unit'], 'binding': None, 'basis': c['quantity'], 'owner_range': c['owner_range'],
                                'scenario_id': c['scenario_id'], 'scenario_version': c['scenario_version'], 'sample_basis': c['sample_basis'],
                                'validation': c['validation'], 'keys': keys, **({'placeholder': c['placeholder']} if 'placeholder' in c else {})}
    for sid, c in fr['streams'].items():
        out[f'frames.{sid}'] = {'class': 'UNKNOWN' if c['values'] is None else 'SOURCED', 'authority': 'sheet-import', 'status': c['status'],
                                'contract': fr['contract'], 'kind': c['kind'], 'binding': None, 'basis': c['quantity'], 'owner_range': c['owner_range'],
                                'scenario_id': c['scenario_id'], 'scenario_version': c['scenario_version'], 'validation': c['validation'],
                                'rows': c['values'], 'keys': [], **({'placeholder': c['placeholder']} if 'placeholder' in c else {})}
    for cid, c in (*fr['channels'].items(), *fr['streams'].items()):
        for name in c['presented_by']:
            out[name].setdefault('stands_for', {})[f'frames.{cid}'] = c['status']
    for c in out.values():
        if 'stands_for' in c:
            c['status'] = min(c['stands_for'].values(), key=fr['statuses'].index); c['contract'] = fr['contract']
            if c['status'] != 'UNKNOWN':
                c['superseded_by'] = sorted(c['stands_for'])
    return out


def value_at(keys, frame):
    i = bisect.bisect_right([k[0] for k in keys], frame)-1
    if i < 0:
        return None
    f, v, interp = keys[i]
    if interp == 'LINEAR' and i+1 < len(keys):
        f_, v_, _ = keys[i+1]
        return v+(v_-v)*(frame-f)/(f_-f)
    return v


def phase_at(ps, frame):
    return next((p for p in ps if p['frame_start'] <= frame < p['frame_end']), ps[-1])


def marks(s, ps=None):
    ps = ps or phases(s); by_id = {p['id']: p for p in ps}; out = {}
    for name, m in table(s)['marks'].items():
        if isinstance(m, dict):
            p = by_id[m['phase']]
            f = p['frame_start']+(m['offset'] if 'offset' in m else m['at']*p['frames'])
            out[name] = {**m, 'frame': int(f) if f == int(f) else f}
    return out


def sample(s, at, ch=None, ps=None):
    """Every channel's value at a frame or a mark."""
    ps = ps or phases(s); ch = ch or channels(s, ps)
    if isinstance(at, str):
        m = marks(s, ps)[at]; frame = m['frame']; p = next(q for q in ps if q['id'] == m['phase'])
    else:
        frame = at; p = phase_at(ps, frame)
    return {'frame': frame, 'phase': p['id'], 'display': display(s, p), 'values': {n: value_at(c['keys'], frame) for n, c in ch.items()}}


def control_values(ch, values):
    """{control: {property: value}} for a sample's values: each bound channel's value on every control it binds."""
    out = {}
    for name, c in ch.items():
        if c['binding']:
            for control in c['binding']['controls']:
                out.setdefault(control, {})[c['binding']['property']] = float(values[name])
    return out


def caption(s, at, ch=None, ps=None):
    """Header lines for a mark or frame: where it is, the kinematics with their classes, the shown states, and the time compression."""
    ps = ps or phases(s); r = sample(s, at, ch, ps); v = r['values']; k = kinematics(s); p = next(q for q in ps if q['id'] == r['phase'])
    where = p.get('configuration') or f"{p['from']} -> {p['to']}"
    bound = '>= ' if v['kinematics.burn_elapsed_s'] >= k['burn_time_s'] and r['phase'] != 'BURN' else ''
    rings = 'stopped and locked' if v['rotor.ring_locks_engaged'] else f"spin {v['rotor.spin_fraction']:.2f} of 4 rpm"
    return [f"{at if isinstance(at, str) else f'frame {at}'} / phase {r['phase']} / {where}",
            f"burn time {v['kinematics.burn_elapsed_s']/k['day_s']:.4f} d | a {v['kinematics.acceleration_g']:.3f} g | v {v['kinematics.speed_c']:.5f} c | x {bound}{v['kinematics.distance_AU']:.4f} AU traveled (SOURCED 23_ROUTE_FRAMES, DIAGNOSTIC 1D, not heliocentric)",
            f"rings {rings} | drive {v['drive.drive_active']:.2f}, display throttle {v['drive.thrust_level']:.2f} (a / 1.5 g) | radiators {radiator_health.steps(s)[radiator_health.step_index(s, v['radiator.thermal_state'])]} | EYE {v['eye.mode']} (PRESENTATION)",
            f"frame {r['frame']} of {ps[-1]['frame_end']} | {r['display']['label']} | phase order PROTOTYPE; unscaled phases carry no seconds"]


def unknown(s):
    out = {}
    for path in table(s)['unknown']['paths']:
        node = path_value(s, path)
        out[path] = {'known': False, 'canon_status': node.get('canon_status'), 'ref': node.get('source_ref') or node.get('evidence_ref'), 'reason': node.get('reason')}
        if path == 'physics.plume_boundary':
            out[path]['study_case'] = '15 deg half-angle (15!G3); do not canonize (15!H3). Not a timeline channel.'
    return out


# ---------- checks --------------------------------------------------------------------------------------------------

def structure_failures(s, sources=None):
    t = table(s); ps = phases(s); out = []; cfg = s['configuration']; seq = [st['key'] for st in s['induction']['sequence']]
    ind = [i for i, e in enumerate(t['phases']['list']) if 'induction' in e]
    if [t['phases']['list'][i]['induction'] for i in ind] != seq or ind != list(range(ind[0], ind[0]+len(ind))):
        out.append('the induction steps appear once each, together and in [induction].sequence order')
    if t['fps'] != s['drive_manifold']['fps']:
        out.append('fps equals [drive_manifold].fps')
    ids = [p['id'] for p in ps]
    if len(set(ids)) != len(ids):
        out.append('phase ids are unique')
    for n, p in enumerate(ps):
        tag = p['id']
        if not (isinstance(p['frames'], int) and p['frames'] > 0):
            out.append(f'{tag}: frames is a positive integer')
        if p['duration'] not in DURATIONS:
            out.append(f'{tag}: duration is one of {DURATIONS}')
        if any(k in p for k in ('seconds', 'duration_s', 'time_s')):
            out.append(f'{tag}: no seconds are typed for a phase')
        if p['duration'] == 'OPEN' and not (p.get('evidence_ref') and (sources is None or p['evidence_ref'] in sources['sources'])):
            out.append(f'{tag}: an OPEN phase names its evidence_ref in the source map')
        if p['duration'] == 'SOURCED' and not isinstance(path_value(s, p['value_ref']), float):
            out.append(f'{tag}: a SOURCED phase names a value_ref')
        if (p['duration'] == 'IMPORTED') != (p.get('drive') == 'burn'):
            out.append(f'{tag}: only the burn has an IMPORTED duration')
        if p.get('drive') == 'burn' and p['frames'] != route(s)['frame_count']-1:
            out.append(f"{tag}: the burn spans the {route(s)['frame_count']} imported route rows, one per frame (C-010)")
        if p.get('rotor', ROTOR_SEGMENTS[0]) not in ROTOR_SEGMENTS or p.get('drive', DRIVE_SEGMENTS[0]) not in DRIVE_SEGMENTS:
            out.append(f'{tag}: unknown rotor or drive segment')
        if 'thermal' in p and p['thermal'] not in radiator_health.steps(s):
            out.append(f'{tag}: thermal is a radiators.operating_sequence step')
        if 'configuration' in p:
            if not cfg.get(p['configuration'], {}).get('buildable'):
                out.append(f'{tag}: holds a buildable configuration')
        else:
            if not all(cfg.get(p.get(k), {}).get('buildable') for k in ('from', 'to', 'display')):
                out.append(f'{tag}: a transition joins buildable configurations and names the one it displays')
            prev, nxt = (ps[n-1] if n else None), (ps[n+1] if n+1 < len(ps) else None)
            if not (prev and (prev.get('configuration') == p['from'] or (prev.get('from'), prev.get('to')) == (p['from'], p['to']))):
                out.append(f'{tag}: a transition follows its from configuration')
            if not (nxt and (nxt.get('configuration') == p['to'] or (nxt.get('from'), nxt.get('to')) == (p['from'], p['to']))):
                out.append(f'{tag}: a transition leads to its to configuration')
    burns = [p for p in ps if p.get('drive') == 'burn']
    if len(burns) != 1 or burns[0].get('configuration') is None or cfg[burns[0]['configuration']].get('acceleration_profile') != 'mission.first_ignition':
        out.append('one burn phase holds the configuration flown on mission.first_ignition')
    reserved = set(cfg) | {n for tb in (s['forward_defense']['display_poses'], s['radiator_health']['display_poses']) for n, v in tb.items() if isinstance(v, dict)}
    by_id = {p['id']: p for p in ps}
    for name, m in t['marks'].items():
        if not isinstance(m, dict):
            continue
        if name in reserved:
            out.append(f'mark {name}: never a configuration or display pose name')
        p = by_id.get(m['phase'])
        at = m.get('offset', m.get('at', -1)*(p['frames'] if p else 0))
        if p is None or ('offset' in m) == ('at' in m) or not 0 <= at <= p['frames'] or (p['frame_start']+at) % 1:
            out.append(f'mark {name}: a phase fraction or frame offset on a whole frame of the phase')
    for path in t['unknown']['paths']:
        node = path_value(s, path)
        if node.get('known') is not False or 'value' in node:
            out.append(f'unknown {path}: still known = false with no value')
    fr = frames(s)
    for cid, c in (*fr['channels'].items(), *fr['streams'].items()):
        if (c['status'] == 'UNKNOWN') != (c['values'] is None):
            out.append(f'frames {cid}: UNKNOWN exactly when Sheets has released no values (15!H125)')
    return out


def rule_failures(s, ps, ch):
    """Sampled at every frame: rotor display rules, rings stopped and locked whenever the drive shows output or the ship accelerates
    (08!A47, MEC-011), high-power rejection whenever the drive runs, and the 07!A39 step order (up one step at a time; cooldown only after
    high-power rejection)."""
    out = set(); props = rotor_interface.PROPS; steps = radiator_health.steps(s)
    for frame in range(ps[0]['frame_start'], ps[-1]['frame_end']+1):
        state = {k: value_at(ch[f'rotor.{k}']['keys'], frame) for k in props}
        for rule in rotor_interface.state_rules(state):
            out.add(f'frame {frame}: rotor {rule}')
        active = value_at(ch['drive.drive_active']['keys'], frame) > 0 or value_at(ch['kinematics.acceleration_g']['keys'], frame) > 0
        if active and not (state['spin_fraction'] == 0 and state['index_lock_engaged'] and state['ring_locks_engaged']):
            out.add(f'frame {frame}: thrust with the rings not stopped and locked')
        if value_at(ch['drive.drive_active']['keys'], frame) > 0 and steps[radiator_health.step_index(s, value_at(ch['radiator.thermal_state']['keys'], frame))] != radiator_health.HIGH_POWER_STEP:
            out.add(f'frame {frame}: the drive runs without high-power rejection')
    rev = rotor_interface.frames_per_turn(s); turned = [v for _, v, _ in ch['rotor.spin_turned']['keys']]
    if any(b < a-1e-9 for a, b in zip(turned, turned[1:])):
        out.add('the ring turn decreases: a ring reverses')
    for f, v, _ in ch['rotor.spin_fraction']['keys']:
        r = value_at(ch['rotor.spin_turned']['keys'], f) % rev
        if v == 0 and min(r, rev-r) > 1e-6:
            out.add(f'frame {f}: a ring at rest is {r:.3f} frames of turn off its index angle')
    seen = [radiator_health.step_index(s, v) for _, v, _ in ch['radiator.thermal_state']['keys']]
    for a, b in zip(seen, seen[1:]):
        if (b > a and b != a+1) or (steps[b] == 'POST_SHUTDOWN_COOLDOWN' and steps[a] != radiator_health.HIGH_POWER_STEP):
            out.add(f'radiator steps {steps[a]} -> {steps[b]} break the 07!A39 order')
    return sorted(out)


def validate(s, sources=None):
    bad = structure_failures(s, sources)
    if not bad:
        ps = phases(s); bad = rule_failures(s, ps, channels(s, ps))
    if bad:
        raise ValueError(f'flight_timeline: {bad}')


# ---------- output --------------------------------------------------------------------------------------------------

def timeline(s, spec_text, source_text):
    import hashlib
    t = table(s); ps = phases(s); ch = channels(s, ps); mk = marks(s, ps)
    digest = lambda text: hashlib.sha256(text.encode()).hexdigest()
    keep = ('id', 'title', 'induction', 'configuration', 'from', 'to', 'display', 'thermal', 'rotor', 'drive', 'duration', 'evidence_ref', 'value_ref', 'frames', 'frame_start', 'frame_end')
    return {'schema': SCHEMA, 'timeline_version': t['timeline_version'], 'spec_hash': digest(spec_text), 'source_map_hash': digest(source_text),
            'reference_frame': t['reference_frame'], 'status': t['phases']['status'], 'rationale': t['phases']['rationale'], 'open_question': t['phases']['open_question'],
            'classes': CLASSES, 'fps': t['fps'], 'frame_range': [ps[0]['frame_start'], ps[-1]['frame_end']],
            'kinematics': kinematics(s), 'bindings': bindings(s),
            'frame_channels': {'contract': frames(s)['contract'], 'file': t['frames'], 'source': frames(s)['source'], 'rules': frames(s)['rules'],
                               'status': {cid: c['status'] for g in ('channels', 'streams') for cid, c in frames(s)[g].items()}},
            'phases': [{**{k: p[k] for k in keep if k in p}, **display(s, p)} for p in ps],
            'channels': ch, 'marks': {n: {**m, **{k: v for k, v in sample(s, n, ch, ps).items() if k != 'frame'}} for n, m in mk.items()},
            'unknown': unknown(s)}


def text(s, spec_text, source_text):
    return json.dumps(timeline(s, spec_text, source_text), indent=1)+'\n'


def write(root=ROOT):
    import spec
    s, sources, spec_text, source_text = spec.load(root)
    validate(s, sources)
    path = root/table(s)['output']; path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text(s, spec_text, source_text))
    return path


def check(root=ROOT):
    import spec
    s, _, spec_text, source_text = spec.load(root)
    path = root/table(s)['output']
    return path.exists() and json.loads(path.read_text()) == json.loads(json.dumps(timeline(s, spec_text, source_text)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--root', type=Path, default=ROOT); p.add_argument('--check', action='store_true')
    a = p.parse_args()
    if a.check:
        ok = check(a.root.resolve()); print(SCHEMA, 'CURRENT' if ok else 'STALE'); sys.exit(0 if ok else 1)
    print(SCHEMA, 'written', write(a.root.resolve()))
