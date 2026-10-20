"""`workflow.py route-import`: import the sheet-computed First Ignition route (NAV-001, 26_BLENDER_CONTRACT C-001..C-017).

Reads 22_ROUTE_MODEL, 23_ROUTE_FRAMES, 24_ROUTE_EVENTS and 25_ROUTE_VALIDATION from the capture the `route_frames` source record names
and writes [flight_timeline].route (simulations/wf_route_v1.json). Values are copied as the sheet stores them: nothing is computed,
interpolated, smoothed or fixed here (NAV-027, C-001, C-017). The import is refused unless 25_ROUTE_VALIDATION rows 2:13 all read PASS
(C-009); the checks below are import fidelity only (frame count, one row per frame number, the scenario labels)."""
import hashlib
import json
from pathlib import Path
import sys
import tomllib

import drive_sync

SCHEMA = 'WF_ROUTE_IMPORT'
GATE_ROWS = range(2, 14)               # 25_ROUTE_VALIDATION!A2:G13 (C-009)


def column(cells, row, col):
    c = cells.get((row, col))
    return None if c is None else c.value


def table(cells, first_row, last_row, width):
    return [[column(cells, r, c) for c in range(1, width+1)] for r in range(first_row, last_row+1)]


def read(xlsx):
    wb = drive_sync.read_xlsx(Path(xlsx).read_bytes())
    model, frames, events, checks = (wb[n] for n in ('22_ROUTE_MODEL', '23_ROUTE_FRAMES', '24_ROUTE_EVENTS', '25_ROUTE_VALIDATION'))
    params = {r[0]: {'value': r[1], 'unit': r[2], 'authority': r[3], 'definition': r[4]} for r in table(model, 2, 36, 5) if r[0]}
    header = table(frames, 1, 1, 17)[0]
    rows = [r for r in table(frames, 2, max(r for r, _ in frames), 17) if r[0] is not None]
    keys = table(events, 1, 1, 11)[0]
    ev = [dict(zip(keys, r)) for r in table(events, 2, max(r for r, _ in events), 11) if r[0]]
    vkeys = table(checks, 1, 1, 7)[0]
    last = max(r for r, _ in checks)       # every check row the owner lists (the OPEN rows grow: 19:21 added after 2026-10-09)
    val = [dict(zip(vkeys, r), row=n) for n, r in zip(range(2, last+1), table(checks, 2, last, 7)) if r[0]]
    return params, header, rows, ev, val


def failures(params, header, rows, validation):
    """Why the route may not be imported (empty when it may)."""
    out = [f"25_ROUTE_VALIDATION!F{v['row']} {v['check_id']} is {v['result']}, not PASS" for v in validation
           if v['row'] in GATE_ROWS and v['result'] != 'PASS']
    count = params['frame_count']['value']
    if header[:2] != ['frame', 'mission_t_s'] or header[-1] != 'scenario_status':
        out.append(f'23_ROUTE_FRAMES header changed: {header}')
    if len(rows) != count or [r[0] for r in rows] != [float(n) for n in range(1, int(count)+1)]:
        out.append(f'23_ROUTE_FRAMES does not hold one row per frame 1..{count:g}')
    if {r[-1] for r in rows} != {params['scenario_status']['value']}:
        out.append('a frame row carries a different scenario_status than 22!B24')
    return out


def route(root):
    sources = tomllib.loads((root/'data/source_map.toml').read_text())
    rec = sources['sources']['route_frames']; xlsx = root/rec['capture']
    params, header, rows, events, validation = read(xlsx)
    bad = failures(params, header, rows, validation)
    if bad:
        raise ValueError(f'route import refused (26_BLENDER_CONTRACT C-009): {bad}')
    data = {'schema': SCHEMA, 'scenario_id': params['scenario_id']['value'], 'scenario_status': params['scenario_status']['value'],
            'frame_id': params['frame_id']['value'], 'fps': params['fps']['value'], 'clip_length_s': params['clip_length_s']['value'],
            'frame_count': int(params['frame_count']['value']),
            'legend': 'DIAGNOSTIC 1D: traveled displacement along local +X from the ignition origin, not a heliocentric or Earth distance (22!A36, NAV-030)',
            'source': {'source_ref': 'route_frames', 'workbook': rec['workbook'], 'workbook_id': rec['workbook_id'], 'modified_at_utc': rec['modified_at_utc'],
                       'capture': rec['capture'], 'capture_sha256': hashlib.sha256(xlsx.read_bytes()).hexdigest(),
                       'ranges': ['23_ROUTE_FRAMES!A1:Q901', '22_ROUTE_MODEL!A1:E36', '24_ROUTE_EVENTS!A1:K9', f"25_ROUTE_VALIDATION!A1:G{max(v['row'] for v in validation)}"]},
            'contract': '26_BLENDER_CONTRACT C-001..C-017: values as the sheet computed them; one row per render frame, linear or direct lookup; '
                        'display transforms are named and reversible and never fed back as physics.',
            'model': params, 'validation': validation, 'events': events, 'columns': header}
    data['route_version'] = hashlib.sha256(json.dumps([data['model'], rows], sort_keys=True).encode()).hexdigest()[:16]
    data['frames'] = rows
    return data


def text(data):
    head = json.dumps({k: v for k, v in data.items() if k != 'frames'}, indent=1, ensure_ascii=False)[:-2]
    return head+',\n "frames": [\n'+',\n'.join('  '+json.dumps(r) for r in data['frames'])+'\n ]\n}\n'


def output(root):
    return root/tomllib.loads((root/'data/wayfarer_3d.toml').read_text())['flight_timeline']['route']


def run(root, check=False):
    data = route(root); path = output(root); new = text(data)
    if check:
        return {'result': 'CURRENT' if path.exists() and path.read_text() == new else 'STALE', 'path': str(path.relative_to(root))}
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(new)
    return {'result': 'PASS', 'path': str(path.relative_to(root)), 'frames': data['frame_count'], 'route_version': data['route_version'],
            'scenario': data['scenario_id'], 'status': data['scenario_status']}


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    print(json.dumps(run(Path(__file__).resolve().parents[1], '--check' in sys.argv)))
