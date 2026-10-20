"""`workflow.py frames-import`: the Sheets simulation-exchange contract FRM-002-2026-10-10 (S&E 15_MODEL_INTERFACES!A125:I125, WORKFLOW
LOCKED / CHANNEL NUMERICS OPEN; 26_BLENDER_CONTRACT C-017/C-018; 98_DECISION_LOG!A91), refining FLIGHT-FRAMES-2026-10-10 (15!A117).

Google Sheets owns every numeric value, state, assumption, unit, sample time and validation flag. Two products (15!C125):
(1) continuous state samples (C-017): one versioned scenario per table, row 1 field names, row 2 units, then time-tagged owner-computed
    samples with mission_t_s, the value, scenario_id and scenario_version, status, source and validation, and a frame only where the
    sample falls on a 23_ROUTE_FRAMES frame; CHANNELS declares them;
(2) discrete phase intervals and events (C-018): modes, transitions, isolations and faults, in separate versioned tables with
    start/end mission_t_s (or an event's mission_t_s), id, scenario, status, validation and source; STREAMS declares them.
Until its table is released a channel or stream stays UNKNOWN with null values, never a number. A released table is copied as the sheet
stores it: nothing is computed, interpolated, resampled onto the 30 fps frames, smoothed or filled; an empty time stays untimed (15!G125,
H125, C-018 G19). The checks are import fidelity only (TABLE, STREAM_TABLE); PASS is the owner's validation, never Claude's. Writes
[flight_timeline].frames (simulations/wf_flight_frames_v1.json), which flight_timeline binds to the timeline."""
import hashlib
import json
from pathlib import Path
import sys
import tomllib

import drive_sync
from route_import import column

SCHEMA = 'WF_FLIGHT_FRAMES'
CONTRACT = 'FRM-002-2026-10-10'
SOURCE = ('15_MODEL_INTERFACES!A125:I125 FRM-002 (WORKFLOW LOCKED / CHANNEL NUMERICS OPEN; 98_DECISION_LOG!A91; 26_BLENDER_CONTRACT C-017/C-018), '
          'refining 15!A117:I117 FLIGHT-FRAMES (98!A85)')
PENDING = 'to be released by Sheets'
PLACEHOLDER = 'UNKNOWN: awaiting Sheets release'
STATUSES = ('UNKNOWN', 'DIAGNOSTIC', 'WORKING', 'DERIVED')    # a released row carries one of the last three (15!G117)
MISSION_TIME = 'MISSION_TIME'
BASES = {MISSION_TIME: 'time-tagged owner samples at mission_t_s (C-017); a sample carries a frame only where its time is a 23_ROUTE_FRAMES '
                       'frame time, and only those are shown on the timeline (C-010 direct lookup, nothing between samples)'}
TABLE = ('A released continuous table (C-017): row 1 the field names, row 2 the units, then one row per owner sample. Columns: mission_t_s, '
         'the channel column, scenario_id, scenario_version, status, source, validation, and optionally frame. One scenario_id and one '
         'scenario_version; mission_t_s strictly increasing; a frame, where given, is the 23_ROUTE_FRAMES frame at that mission_t_s; status one '
         'of WORKING / DERIVED / DIAGNOSTIC; validation PASS (the owner\'s test result) on every row. Refused otherwise, never fixed.')
STREAM_TABLE = ('A released phase or event table (C-018): row 1 the field names, row 2 the units. Phases: phase_id, start_mission_t_s, '
                'end_mission_t_s; events: event_id, mission_t_s; both with scenario_id, scenario_version, status, source, validation. A time '
                'may be empty (an unknown onset or duration): the row stays untimed and unplaced, never interpolated. Refused otherwise.')
STREAM_COLUMNS = {'phase': ('phase_id', 'start_mission_t_s', 'end_mission_t_s'), 'event': ('event_id', 'mission_t_s')}
COMMON = ('scenario_id', 'scenario_version', 'status', 'source', 'validation')

# The declared continuous channels (FRM-002 (1)). owner_range: where the owner says the values come from (15!F117 and the S rows); sheet and
# source_ref name the released table and its source-map capture once Sheets releases it (None until then). presented_by: the PRESENTATION
# timeline channels that show the quantity today without its numbers. Every channel is time-tagged (MISSION_TIME); the first release is the
# mass, propellant and thrust working scenario (15!I125); rotor spin is a measured continuous rate, never a forced 900-frame curve (Doc 13:34).
S14 = (f'{PENDING} from the chosen physical scenario (15!C117); 15!A22:A26 S1-S4; the 28_BURN_ENVELOPE / 29_BURN_FRAMES 33-point '
       'study is PROVISIONAL and not a release (29!A2)')
CHANNELS = {
    'ship_mass':         {'quantity': 'Ship mass history (S1, S2)', 'unit': 'kg', 'sample_basis': MISSION_TIME, 'presented_by': [],
                          'owner_range': f'{S14}; 10_WAYFARER_MASS; 02_SHIP_INPUTS!H21:H22'},
    'propellant_remaining': {'quantity': 'Reaction mass and fusion fuel remaining (S2)', 'unit': 'kg', 'sample_basis': MISSION_TIME, 'presented_by': [],
                          'owner_range': f'{S14}; 02_SHIP_INPUTS!H21:H22; Fiji 02_DRIVE_INPUTS'},
    'mass_flow':         {'quantity': 'Exhaust mass flow (S3)', 'unit': 'kg/s', 'sample_basis': MISSION_TIME, 'presented_by': ['drive.plasma_visibility'],
                          'owner_range': f'{S14}; Fiji 20_PROPULSION!A3:F12'},
    'thrust':            {'quantity': 'Total flight thrust over time (S3, S3a: from the mass history)', 'unit': 'N', 'sample_basis': MISSION_TIME,
                          'presented_by': ['drive.thrust_level'], 'owner_range': f'{S14}; Fiji 20_PROPULSION!A3:F12; 35_SCALING_LIMITS!A33:F34'},
    'reactor_power':     {'quantity': 'Reactor (fusion) power', 'unit': 'W', 'sample_basis': MISSION_TIME, 'presented_by': ['drive.drive_active'],
                          'owner_range': f'{PENDING} (15!C117); 40_THERMAL; Fiji 30_DRIVE_THERMAL'},
    'nozzle_power':      {'quantity': 'Magnetic-nozzle power', 'unit': 'W', 'sample_basis': MISSION_TIME, 'presented_by': ['drive.nozzle_field_strength'],
                          'owner_range': f'{PENDING} (15!C117); Fiji 25_MAGNETIC_MANIFOLD'},
    'heat_hot_loop':     {'quantity': 'Hot-loop heat to reject', 'unit': 'W', 'sample_basis': MISSION_TIME, 'presented_by': ['radiator.thermal_state'],
                          'owner_range': f'{PENDING} (15!C117); 15!A26 S4; 40_THERMAL'},
    'heat_warm_loop':    {'quantity': 'Warm-loop heat to reject', 'unit': 'W', 'sample_basis': MISSION_TIME, 'presented_by': ['radiator.thermal_state'],
                          'owner_range': f'{PENDING} (15!C117); 15!A26 S4; 40_THERMAL'},
    'heat_cold_loop':    {'quantity': 'Cold-loop heat to reject', 'unit': 'W', 'sample_basis': MISSION_TIME, 'presented_by': ['radiator.thermal_state'],
                          'owner_range': f'{PENDING} (15!C117); 15!A26 S4; 40_THERMAL'},
    'rotor_spin_ring_a': {'quantity': 'Ring A spin rate (S6: spin-down and spin-up timing)', 'unit': 'rpm', 'sample_basis': MISSION_TIME,
                          'presented_by': ['rotor.spin_fraction', 'rotor.spin_turned'],
                          'owner_range': f'{PENDING}; 15!A28 S6; 16_SPACE_MECHANISMS!A2:I11; OD-003/004/013'},
    'rotor_spin_ring_b': {'quantity': 'Ring B spin rate (S6: spin-down and spin-up timing)', 'unit': 'rpm', 'sample_basis': MISSION_TIME,
                          'presented_by': ['rotor.spin_fraction', 'rotor.spin_turned'],
                          'owner_range': f'{PENDING}; 15!A28 S6; 16_SPACE_MECHANISMS!A2:I11; OD-003/004/013'},
    'bus_power':         {'quantity': 'A/B bus power per configuration (S5, S7)', 'unit': 'W', 'sample_basis': MISSION_TIME, 'presented_by': [],
                          'owner_range': f'{PENDING}; 15!A27:A29 S5/S7; 08_ROTATING_HABITAT!A49:H52; OD-009'},
}
for _c in CHANNELS.values():
    _c.setdefault('sheet', None); _c.setdefault('source_ref', None)
# The declared phase and event streams (FRM-002 (2), C-018): modes, transitions and faults with possibly unknown onsets.
STREAMS = {
    'degraded_mode':     {'quantity': 'Degraded-mode phases (radiator, ring, generator, coolant loop, nozzle)', 'kind': 'phase',
                          'presented_by': [], 'owner_range': f'{PENDING}; 09_OPEN_DESIGN_ITEMS!A11:J11 OD-010; 15!A29 S7; 26 C-018'},
    'radiator_failure':  {'quantity': 'Radiator-failure events (cell-loss onset, isolation, fraction)', 'kind': 'event',
                          'presented_by': ['radiator.cell_isolation'],
                          'owner_range': f'{PENDING}; 09_OPEN_DESIGN_ITEMS!A29 OD-028; 20_FIRST_IGNITION!A27; 40_THERMAL!A71 (Q53); 26 C-018'},
}
for _c in STREAMS.values():
    _c.setdefault('sheet', None); _c.setdefault('source_ref', None)


def read_table(cells):
    """(header, units, rows) of a released table: row 1 names, row 2 units, rows 3.. one per sample or record."""
    width = max(c for _, c in cells); last = max(r for r, _ in cells)
    line = lambda r: [column(cells, r, c) for c in range(1, width+1)]
    header = line(1)
    return header, line(2), [dict(zip(header, line(r))) for r in range(3, last+1) if any(v is not None for v in line(r))]


def number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def common_failures(sheet, rows):
    """The C-017/C-018 metadata every released table carries: one scenario and version, an allowed status, a source, the owner's PASS."""
    out = []
    for k in ('scenario_id', 'scenario_version'):
        if len({r[k] for r in rows}) != 1 or rows[0][k] in (None, ''):
            out.append(f'{sheet}: not one {k}')
    if len({r['status'] for r in rows}) != 1 or rows[0]['status'] not in STATUSES[1:]:
        out.append(f'{sheet}: status is not one of {STATUSES[1:]} on every row')
    if any(r['source'] in (None, '') for r in rows):
        out.append(f'{sheet}: a row has no source')
    if any(r['validation'] != 'PASS' for r in rows):
        out.append(f'{sheet}: a row is not validation PASS')
    return out


def route_times(route):
    return [f[route['columns'].index('mission_t_s')] for f in route['frames']]


def failures(cid, c, header, units, rows, route):
    """Why a released continuous table may not be imported for channel cid (empty when it may). Import fidelity only."""
    need = ['mission_t_s', cid, *COMMON]
    if missing := [n for n in need if n not in header]:
        return [f'{c["sheet"]}: columns {missing} missing']
    if not rows:
        return [f'{c["sheet"]}: no rows']
    out = common_failures(c['sheet'], rows)
    if c['sample_basis'] not in BASES:
        out.append(f'{cid}: no sample basis declared ({PENDING}); not imported')
    if units[header.index(cid)] != c['unit']:
        out.append(f'{c["sheet"]}: {cid} unit {units[header.index(cid)]!r}, the contract declares {c["unit"]!r}')
    if units[header.index('mission_t_s')] != 's':
        out.append(f'{c["sheet"]}: mission_t_s unit {units[header.index("mission_t_s")]!r}, not \'s\'')
    t = [r['mission_t_s'] for r in rows]
    if not all(number(x) for x in t) or any(b <= a for a, b in zip(t, t[1:])):
        out.append(f'{c["sheet"]}: mission_t_s missing or not strictly increasing')
    elif 'frame' in header:
        rt = route_times(route)
        for r in rows:
            f = r['frame']
            if f is not None and (not number(f) or f != int(f) or not 1 <= f <= len(rt) or abs(rt[int(f)-1]-r['mission_t_s']) > 1e-6):
                out.append(f'{c["sheet"]}: frame {f!r} is not the 23_ROUTE_FRAMES frame at mission_t_s {r["mission_t_s"]}'); break
    kind = str if c['unit'] == 'label' else (int, float)
    if any(not isinstance(r[cid], kind) or isinstance(r[cid], bool) for r in rows):
        out.append(f'{c["sheet"]}: {cid} holds an empty or wrong-typed value')
    return out


def stream_failures(sid, c, header, units, rows):
    """Why a released phase or event table may not be imported (empty when it may). Empty times are allowed (untimed); present ones are
    numbers in s and a phase never ends before it starts."""
    cols = STREAM_COLUMNS[c['kind']]
    if missing := [n for n in (*cols, *COMMON) if n not in header]:
        return [f'{c["sheet"]}: columns {missing} missing']
    if not rows:
        return [f'{c["sheet"]}: no rows']
    out = common_failures(c['sheet'], rows)
    ids = [r[cols[0]] for r in rows]
    if any(i in (None, '') for i in ids) or len(set(ids)) != len(ids):
        out.append(f'{c["sheet"]}: {cols[0]} empty or repeated')
    for k in cols[1:]:
        if units[header.index(k)] != 's':
            out.append(f'{c["sheet"]}: {k} unit {units[header.index(k)]!r}, not \'s\'')
        if any(r[k] is not None and not number(r[k]) for r in rows):
            out.append(f'{c["sheet"]}: {k} holds a non-numeric time')
    if c['kind'] == 'phase' and any(number(r['start_mission_t_s']) and number(r['end_mission_t_s']) and r['end_mission_t_s'] < r['start_mission_t_s'] for r in rows):
        out.append(f'{c["sheet"]}: a phase ends before it starts')
    return out


def entry(cid, c):
    keys = ('quantity', 'unit', 'owner_range', 'presented_by', 'sheet', 'source_ref') if 'unit' in c else ('quantity', 'kind', 'owner_range', 'presented_by', 'sheet', 'source_ref')
    extra = {'sample_basis': BASES.get(c['sample_basis'], PENDING), 'mission_t_s': None, 'frame': None} if 'unit' in c else {'rows': None}
    return {**{k: c[k] for k in keys}, **extra, 'status': 'UNKNOWN', 'scenario_id': None, 'scenario_version': None, 'validation': None,
            'values': None, 'placeholder': PLACEHOLDER}


def released(cid, c, wb, rec, xlsx, route):
    """The channel or stream from its released sheet, or the UNKNOWN entry when the sheet is not in the capture."""
    if c['sheet'] not in wb:
        return {**entry(cid, c), 'placeholder': f'{PLACEHOLDER} ({c["sheet"]} not in {rec["capture"]})'}
    header, units, rows = read_table(wb[c['sheet']])
    stream = 'kind' in c
    if bad := (stream_failures(cid, c, header, units, rows) if stream else failures(cid, c, header, units, rows, route)):
        raise ValueError(f'frames import refused ({CONTRACT}): {bad}')
    out = entry(cid, c); del out['placeholder']
    meta = {'status': rows[0]['status'], 'scenario_id': rows[0]['scenario_id'], 'scenario_version': rows[0]['scenario_version'], 'validation': 'PASS',
            'source': {'source_ref': c['source_ref'], 'workbook': rec['workbook'], 'capture': rec['capture'],
                       'capture_sha256': hashlib.sha256(xlsx.read_bytes()).hexdigest(), 'sheet': c['sheet']}}
    if stream:
        cols = STREAM_COLUMNS[c['kind']]
        return {**out, **meta, 'values': [{k: r[k] for k in (*cols, 'status', 'source')} for r in rows], 'rows': len(rows)}
    return {**out, **meta, 'values': [r[cid] for r in rows], 'mission_t_s': [r['mission_t_s'] for r in rows],
            'frame': [None if r.get('frame') is None else int(r['frame']) for r in rows]}


def frames(root, channels=CHANNELS, streams=STREAMS):
    spec = tomllib.loads((root/'data/wayfarer_3d.toml').read_text())['flight_timeline']
    route = json.loads((root/spec['route']).read_text())
    sources = tomllib.loads((root/'data/source_map.toml').read_text())['sources']; books = {}; out = {}
    for group, declared in (('channels', channels), ('streams', streams)):
        out[group] = {}
        for cid, c in declared.items():
            if not (c['sheet'] and c['source_ref']):
                out[group][cid] = entry(cid, c); continue
            rec = sources[c['source_ref']]; xlsx = root/rec['capture']
            if xlsx not in books:
                books[xlsx] = drive_sync.read_xlsx(xlsx.read_bytes())
            out[group][cid] = released(cid, c, books[xlsx], rec, xlsx, route)
    return {'schema': SCHEMA, 'contract': CONTRACT, 'source': SOURCE,
            'rules': 'Sheets owns the numbers, states, units, sample times and validation flags; Claude imports, stages and replays only. '
                     'UNKNOWN channels and streams carry null, never a number; no interpolation, resampling onto the 30 fps frames, smoothing or '
                     'derived physics; untimed phases and events stay unplaced (15!G125, H125; C-017/C-018). Mission time is independent of '
                     'the 24/30 fps presentation. The 1D route frames stay DIAGNOSTIC and not heliocentric (15!I117).',
            'table': TABLE, 'stream_table': STREAM_TABLE, 'statuses': list(STATUSES), 'route_version': route['route_version'], **out}


def output(root):
    return root/tomllib.loads((root/'data/wayfarer_3d.toml').read_text())['flight_timeline']['frames']


def run(root, check=False):
    data = frames(root); path = output(root); new = json.dumps(data, indent=1, ensure_ascii=False)+'\n'
    if check:
        return {'result': 'CURRENT' if path.exists() and path.read_text() == new else 'STALE', 'path': str(path.relative_to(root))}
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(new)
    return {'result': 'PASS', 'path': str(path.relative_to(root)), 'contract': CONTRACT,
            'released': sorted(k for g in ('channels', 'streams') for k, v in data[g].items() if v['status'] != 'UNKNOWN'),
            'unknown': sorted(k for g in ('channels', 'streams') for k, v in data[g].items() if v['status'] == 'UNKNOWN')}


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    print(json.dumps(run(Path(__file__).resolve().parents[1], '--check' in sys.argv)))
